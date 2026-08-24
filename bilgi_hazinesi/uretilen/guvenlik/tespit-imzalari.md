# Belirli Saldırıların Tespiti: Kerberoasting, Pass-the-Hash ve DCSync İmzaları

Active Directory (AD) ortamlarında saldırganların en sık başvurduğu üç teknik olan **Kerberoasting**, **Pass-the-Hash** (PtH) ve **DCSync**, kimlik doğrulama protokollerinin doğasında var olan tasarım kararlarını istismar eder. Bu üç teknik de "sıfır gün" bir açıktan değil, Kerberos ve NTLM protokollerinin normal, tasarlanmış davranışından beslenir. Bu yüzden tespitleri de klasik "imza tabanlı antivirüs" mantığıyla değil, davranışsal ve protokol seviyesinde anlam çıkaran bir gözlemle yapılır. Bu makale, her tekniğin neden çalıştığını, saldırganın onu nasıl kullandığını ve savunmacının hangi telemetriye bakarak onu yakalayabileceğini derinlemesine ele alır.

Konuya girmeden önce ortak bir zemin kurmak gerekir: AD içinde parolalar açık metin olarak taşınmaz; bunların **hash** ve **anahtar (key)** türevleri dolaşır. Kerberos'ta bir kullanıcının veya servis hesabının parolasından türetilen anahtar, biletleri (ticket) imzalamak ve şifrelemek için kullanılır. NTLM'de ise parolanın NT hash'i, "parolayı bilmenin" fiili kanıtıdır. Bu üç saldırının hepsi, bu türevlerin ele geçirilmesi veya offline kırılması etrafında döner.

---

## Kerberoasting

### Tanım

Kerberoasting, bir servis hesabının (service account) Kerberos servis biletinin (**TGS**, Ticket Granting Service ticket) ele geçirilip, bu biletin şifreli kısmının **offline** olarak kaba kuvvetle (brute-force) kırılarak servis hesabının açık parolasının elde edilmesi tekniğidir. Kritik nokta şudur: saldırgan bu işlemi yaparken hedef servise hiç bağlanmaz, yönetici yetkisine ihtiyaç duymaz ve ağ üzerinde neredeyse hiç "gürültü" çıkarmaz.

### Kök neden ve çalışma mantığı

Kerberos'ta bir kullanıcı bir servise erişmek istediğinde, Key Distribution Center'dan (KDC) o servis için bir TGS bileti ister. Bu biletin bir bölümü, **hedef servis hesabının parolasından türetilen anahtarla** şifrelenir. Bunun sebebi mantıklıdır: bileti alan servis, kendi parolasıyla bileti çözebilmeli ki içindeki yetki bilgisine güvenebilsin.

Sorun, protokolün şu iki özelliğinin birleşmesinden doğar. Birincisi, herhangi bir kimliği doğrulanmış (authenticated) alan kullanıcısı, **SPN** (Service Principal Name) tanımlı herhangi bir servis için TGS bileti isteyebilir; KDC bu kullanıcının o servise gerçekten erişip erişemeyeceğini bilet verirken kontrol etmez, yetki kontrolü servisin kendisine bırakılmıştır. İkincisi, biletin şifreli kısmı, saldırganın eline geçtiğinde artık tamamen offline analiz edilebilir. Yani saldırgan biletin şifresini çözmeyi denemek için sürekli KDC'ye soru sormaz; kırma işlemi kendi makinesinde, ağdan bağımsız olarak yürür.

Tehlikenin asıl büyüğü **şifreleme türünde** yatar. Kerberos, eski uyumluluk için hâlâ **RC4** tabanlı şifrelemeyi (etype 23) destekleyebilir. RC4 ile şifrelenmiş bir TGS bileti, doğrudan NT hash'ten türeyen bir anahtar kullandığı için offline kırmaya çok daha açıktır. AES tabanlı şifreleme (etype 17/18) hem daha güçlü bir anahtar türetme (salt + iterasyon) kullandığı için kaba kuvveti çok daha maliyetli hale getirir. Saldırganlar bu yüzden mümkünse **RC4 bileti talep etmeye zorlar**.

### Somut örnek

Bir saldırganın tipik akışı şöyledir: Önce alan içindeki SPN tanımlı hesapları listeler (bir LDAP sorgusuyla `servicePrincipalName` özniteliği dolu olan hesaplar aranır). Ardından bu hesaplar için TGS biletleri talep eder. Talep sırasında, mümkünse RC4 şifreleme türünü tercih ettiğini belirtir. Elde ettiği biletlerin şifreli bloklarını diske döker ve Hashcat veya John the Ripper gibi araçlarla, bir parola sözlüğü kullanarak offline kırmaya başlar. Zayıf veya sözlükte bulunan bir parolaya sahip servis hesabı saatler içinde ele geçirilebilir.

Neden servis hesapları hedeflenir? Çünkü servis hesapları çoğu zaman insan kullanıcılardan farklı olarak parolaları nadiren değişen, bazen aşırı yetkilendirilmiş (hatta Domain Admins üyesi) hesaplardır. Zayıf bir parolaya sahip, aynı zamanda yüksek yetkili bir servis hesabı, saldırgan için "altın anahtar" demektir.

### İstismar ve savunma birlikte

İstismar tarafında saldırganın en sinsi yanı, talep aşamasının **tamamen meşru** görünmesidir; bir TGS bileti istemek, günlük normal AD trafiğinin sıradan bir parçasıdır. Anormallik, biletin *nasıl* ve *ne ölçekte* istendiğindedir.

Savunma tarafında ana telemetri kaynağı, Domain Controller üzerindeki **Kerberos servis bileti isteme olayıdır** (Windows güvenlik günlüklerinde bu, TGS talebi olaylarına karşılık gelir; ilgili olay kimliği tipik olarak 4769'dur). Bu olayda bakılması gereken kritik alanlar şunlardır:

- **Ticket Encryption Type**: RC4 (0x17) talepleri, özellikle AES destekleyen bir ortamda modern istemcilerden gelmemesi gereken bir işarettir. Ortamınız AES'e geçmişse bir hesap için ansızın RC4 bileti talep edilmesi güçlü bir kırmızı bayraktır.
- **Talep hacmi ve çeşitliliği**: Tek bir kullanıcı hesabının kısa süre içinde çok sayıda farklı SPN için bilet talep etmesi, insan davranışına uymaz; bir enumerasyon (numaralandırma) belirtisidir.
- **Hedef SPN**: Kullanıcının işiyle hiç ilgisi olmayan servisler için bilet talebi.

Savunmanın asıl gücü tespitten önce **önlemede** yatar. En etkili karşı önlem, servis hesapları için **grup yönetilen servis hesaplarını** (gMSA, Group Managed Service Accounts) kullanmaktır. gMSA parolaları çok uzun, karmaşık ve otomatik döner (rotate); offline kırma pratikte imkânsız hale gelir. İkinci önemli önlem, ortamdan RC4'ü kademeli olarak kaldırıp yalnızca AES'i zorlamaktır. Ancak burada dikkatli olunmalı; RC4'ü aniden kapatmak, ona bağımlı eski sistemleri kırabilir, bu yüzden önce audit yapılıp bağımlılıklar haritalanmalıdır.

---

## Pass-the-Hash (PtH)

### Tanım

Pass-the-Hash, bir kullanıcının açık parolasını hiç bilmeden, yalnızca parolasının **NT hash** değerini kullanarak o kullanıcı adına kimlik doğrulaması yapma tekniğidir. NTLM kimlik doğrulamasında "parolayı bilmenin kanıtı" fiilen NT hash'e sahip olmaktır; dolayısıyla hash'i çalan saldırgan, onu kırmaya bile gerek duymadan doğrudan kimlik yerine kullanabilir.

### Kök neden ve çalışma mantığı

NTLM, bir **challenge-response** protokolüdür. Sunucu istemciye rastgele bir challenge yollar, istemci bu challenge'ı NT hash'ten türetilen bir anahtarla işleyip yanıtı geri gönderir. Sunucu (veya Domain Controller) aynı işlemi kendi tarafındaki hash ile yapıp sonuçları karşılaştırır. Dikkat edilirse, bu akışın hiçbir yerinde açık parola geçmez. Protokolün kalbindeki gerçek "sır" NT hash'in kendisidir. Bu, tasarımın temel bir sonucudur: eğer hash'e sahipseniz, açık parolaya sahip olmakla fiilen aynı şeye sahipsinizdir.

Hash'ler nereden çalınır? Windows, oturum açmış kullanıcıların kimlik bilgilerini **LSASS** (Local Security Authority Subsystem Service) sürecinin belleğinde tutar; bu, tek oturum açışla birçok kaynağa erişimi (single sign-on) mümkün kılmak içindir. Yerel yönetici (veya SYSTEM) yetkisine ulaşan bir saldırgan, LSASS belleğinden bu hash'leri çıkarabilir. Mimikatz gibi araçların meşhur olma sebebi tam olarak budur. Bir kez hash elde edildiğinde, saldırgan onu yeni bir oturum bağlamına "enjekte edip" o kullanıcı gibi ağ kaynaklarına bağlanabilir.

PtH'yi bu kadar tehlikeli yapan şey **yanal hareket** (lateral movement) potansiyelidir. Bir makinede yerel yönetici parolası (veya hash'i) başka makinelerle aynıysa (parola yeniden kullanımı), saldırgan tek bir hash'le onlarca makineye zincirleme yayılabilir.

### Somut örnek

Saldırgan A makinesinde yerel yönetici yetkisi elde eder. LSASS'tan orada oturum açmış bir alan yöneticisinin NT hash'ini çıkarır. Bu hash'i kullanarak, açık parolayı hiç bilmeden, uzaktaki B sunucusuna bir yönetim protokolü (örneğin uzak servis yürütme veya WMI) üzerinden bağlanır ve orada da SYSTEM yetkisi kazanır. Zincir böyle büyür.

### İstismar ve savunma birlikte

İstismarın özü, NTLM'in "hash = kimlik" varsayımıdır ve saldırgan kırma yapmadığı için **hesaplama açısından anlıktır**. Bu yüzden PtH tespiti, "birisi parolamı kırmaya çalışıyor mu" değil, "hash sanki çalınmış gibi anormal bir yerden/şekilde mi kullanılıyor" sorusuna odaklanır.

Savunma tarafında bakılacak sinyaller:

- **NTLM oturum açma olayları** (Domain Controller ve hedef sunucularda oturum açma olayları, tipik olarak olay kimliği 4624/4625; özellikle logon type 3 ağ oturumları). PtH'nin karakteristik izi, kimlik doğrulama paketinin **NTLM** olması ve oturumun beklenmedik bir kaynak makineden gelmesidir. Kerberos'un baskın olduğu bir ortamda yüksek yetkili hesaplar için ani NTLM kullanımı şüphelidir.
- **Yanal hareket paterni**: Aynı hesabın kısa süre içinde çok sayıda farklı makinede ağ oturumu açması, özellikle bu hesap bir yönetici hesabıysa.
- **LSASS'a erişim**: Belki de en değerli erken tespit, hash *kullanılmadan önce çalındığı* andır. LSASS sürecine olağan dışı bir süreç tarafından yapılan bellek okuma erişimi (process access olayları) güçlü bir göstergedir. Modern EDR ve Windows'un kimlik bilgisi koruma özellikleri bu erişimi izler ve engeller.

Önleme katmanları burada tespitten daha kritiktir çünkü PtH'yi "olaydan sonra" yakalamak zordur:

- **Credential Guard**: LSASS'taki sırları sanallaştırma tabanlı güvenlikle (VBS) izole eder; yönetici bile belleği okuyamaz. Bu, hash'in çalınmasını temelden zorlaştırır.
- **Yönetici katmanlama (tiering) modeli**: Yüksek yetkili hesapların düşük güvenli iş istasyonlarında hiç oturum açmamasını sağlamak. Bir alan yöneticisi normal bir kullanıcı makinesine RDP ile bağlanırsa, hash'i o makinenin belleğine düşer ve orayı ele geçiren saldırgana teslim olur.
- **Yerel yönetici parolalarının benzersizleştirilmesi** (örneğin LAPS gibi bir çözümle). Her makinenin farklı ve dönen bir yerel yönetici parolası varsa, bir hash tüm ortamı açan bir ana anahtar olmaktan çıkar; yanal hareket zinciri kırılır.

---

## DCSync

### Tanım

DCSync, bir saldırganın **meşru bir Domain Controller taklidi yaparak**, gerçek bir DC'den kullanıcıların parola hash'lerini (NTLM hash'ler ve Kerberos anahtarları dahil) çoğaltma (replication) protokolü üzerinden talep etmesi tekniğidir. Saldırgan fiziksel olarak DC'ye dokunmadan, hatta DC'de kod çalıştırmadan, sanki başka bir DC ile normal bir senkronizasyon yapıyormuş gibi tüm alanın kimlik bilgilerini sızdırabilir. Bu tekniğin nihai hedefi genellikle `krbtgt` hesabının hash'idir; çünkü o hash ele geçerse saldırgan **Golden Ticket** üreterek alan üzerinde kalıcı, tam kontrol sağlayabilir.

### Kök neden ve çalışma mantığı

Active Directory çok-DC'li (multi-master) bir mimaridir. Bir ortamda birden fazla Domain Controller varsa, bunların birbiriyle sürekli senkronize olması gerekir; bir kullanıcının parolası bir DC'de değiştiğinde, bu değişiklik **DRS** (Directory Replication Service) protokolü, özellikle `DRSGetNCChanges` çağrısı üzerinden diğer DC'lere aktarılır. Yani DC'lerin birbirinden parola sırlarını istemesi, protokolün **tasarlanmış ve gerekli** bir davranışıdır.

DCSync'in dehası, saldırganın bu meşru mekanizmayı taklit etmesidir. Saldırgan bir DC değildir; ama yeterli yetkiye sahip bir hesabı ele geçirmişse, ağ üzerinden bir DC'ye "ben de bir DC'yim, bu kullanıcının sırlarını bana çoğalt" der ve DC bunu yerine getirir. Bu yüzden DCSync ayrı bir "açık" değil, aşırı yetkinin istismarıdır.

Peki hangi yetki? DCSync yapabilmek için hesabın alan nesnesi üzerinde belirli çoğaltma haklarına sahip olması gerekir; başlıcaları **DS-Replication-Get-Changes** ve **DS-Replication-Get-Changes-All** genişletilmiş haklarıdır (extended rights). Normalde bu haklar yalnızca Domain Controllers, Domain Admins, Enterprise Admins ve Administrators gibi çok dar bir gruba aittir. Ama yanlış yapılandırma ile sıradan bir hesaba bu haklar verilmişse, o hesap sessizce bir DCSync silahına dönüşür. Bu yüzden saldırganlar önce PtH veya Kerberoasting ile yeterince yetki toplar, sonra DCSync ile "her şeyi" alır.

### Somut örnek

Saldırgan, önceki tekniklerle Domain Admins seviyesinde bir hesabı ele geçirmiştir. Mimikatz'in ilgili modülüyle (örneğin `lsadump::dcsync` benzeri bir işlev) hedef olarak `krbtgt` hesabını belirtir. Araç, bir DC'ye DRS çoğaltma talebi gönderir; DC talebi meşru sanıp `krbtgt` hesabının anahtarını döner. Artık saldırganın elinde alanın "master anahtarı" vardır ve istediği kadar geçerli Kerberos TGT'si üretebilir, yani Golden Ticket'a sahiptir. Bu noktadan sonra saldırganı ortamdan tamamen sökmek, sıklıkla `krbtgt` parolasını iki kez sıfırlamayı gerektiren zorlu bir olay müdahalesine dönüşür.

### İstismar ve savunma birlikte

İstismarın en tehlikeli yanı, DCSync'in **DC üzerinde herhangi bir iz bırakan bir süreç çalıştırmamasıdır**; işlem tamamen ağ protokolü seviyesinde, meşru bir çoğaltma gibi görünerek gerçekleşir. Bu yüzden host tabanlı süreç izleme genellikle yetersiz kalır; tespit **ağ ve dizin seviyesinde** yapılmalıdır.

Ana tespit fikri şudur: **DC olmayan bir kaynaktan gelen çoğaltma (replication) talebi neredeyse her zaman kötü niyetlidir.** Meşru `DRSGetNCChanges` trafiği yalnızca DC'ler arasında akmalıdır. Bakılacak sinyaller:

- **Dizin hizmeti erişim/çoğaltma olayları**: Windows, dizin çoğaltma haklarının kullanıldığı bir olay üretebilir (dizin hizmeti erişimiyle ilgili olay kimlikleri, tipik olarak 4662 civarındadır). Kritik olan, bu olaydaki **erişilen hakkın çoğaltma genişletilmiş haklarına karşılık gelen GUID'i içermesi** ve talebi yapan hesabın bir DC bilgisayar hesabı **olmamasıdır**. Bir kullanıcı hesabının çoğaltma hakkı kullanması, güçlü bir DCSync göstergesidir.
- **Ağ tabanlı tespit**: DRS/RPC trafiğini izleyen bir sistem, kaynağı bilinen DC listesinde olmayan bir `DRSGetNCChanges` çağrısı gördüğünde alarm üretmelidir. Bu, belki de en güvenilir tespit yöntemidir çünkü meşru DC kümesi bilinen ve dar bir kümedir.

Önleme ve sınırlama tarafında:

- **Çoğaltma haklarının denetimi**: Alan nesnesi üzerindeki DS-Replication-Get-Changes ve -All haklarına *tam olarak* kimlerin sahip olduğu düzenli olarak denetlenmelidir. Buraya sızmış beklenmedik bir hesap veya grup, DCSync için açık kapıdır.
- **Ayrıcalıklı hesap hijyeni**: DCSync bir "son aşama" tekniği olduğundan, ona ulaşmayı sağlayan yetki birikimini (Domain Admins üyeliğinin gereksiz dağıtılması, aşırı yetkili servis hesapları) baştan engellemek en etkili savunmadır.
- **krbtgt yönetimi**: `krbtgt` parolasının periyodik ve doğru şekilde (iki aşamalı) döndürülmesi, çalınmış bir anahtarın süresiz kullanılmasını engeller.

---

## Üç Tekniğin Ortak İzleri ve Zincir Mantığı

Bu üç teknik izole olaylar değil, çoğu zaman **tek bir saldırı zincirinin** halkalarıdır. Tipik bir senaryo şöyle akar: Saldırgan bir son kullanıcı makinesinde tutunur, oradan **Kerberoasting** ile zayıf parolalı bir servis hesabını kırar, o hesabın yetkisiyle veya **Pass-the-Hash** ile yanal hareket ederek daha yetkili hesaplara ulaşır, sonunda Domain Admins seviyesine çıkıp **DCSync** ile alanın tüm kimlik sırlarını (özellikle `krbtgt`) ele geçirir ve kalıcılık sağlar. Bu yüzden savunmacı, olayları tek tek değil, **korelasyon** içinde okumalıdır: kısa bir zaman diliminde aynı hesabın çok sayıda TGS talebi + ardından beklenmedik NTLM yanal hareketi + ardından bir çoğaltma talebi, tek başına her biri belirsizken birlikte çok net bir saldırı hikâyesi anlatır.

---

## Yaygın Hatalar

Savunma kurarken sık düşülen tuzaklar şunlardır:

- **RC4'ü kapattığını sanmak ama zorlamamak.** Ortamda AES etkin olsa bile RC4 hâlâ *destekleniyorsa*, saldırgan biletini RC4 olarak talep edebilir. AES'i "tercih edilen" yapmak yetmez; RC4'ü fiilen devre dışı bırakmak (bağımlılıklar haritalandıktan sonra) gerekir.
- **Sadece başarısız oturumlara (4625) bakmak.** Bu saldırıların çoğu **başarılı** kimlik doğrulamalarla gerçekleşir; PtH ve DCSync başarısız denemeler üretmez. Yalnızca hatalı girişlere odaklanan bir izleme, bu teknikleri tamamen kaçırır.
- **DCSync'i host günlüklerinde aramak.** DC üzerinde bir süreç çalışmadığı için EDR süreç telemetrisi çoğu zaman boş döner; tespit dizin erişim olayı ve ağ seviyesinde yapılmalıdır.
- **Servis hesabı parolalarını "bir kere kur, unut" yönetmek.** Yıllarca değişmeyen, zayıf, insan tarafından belirlenmiş servis hesabı parolaları Kerberoasting'in en verimli hedefidir.
- **Yüksek yetkili hesaplarla her yere oturum açmak.** Bir alan yöneticisinin sıradan iş istasyonlarında oturum açması, hash'ini o makinelere dağıtır ve PtH için hazır avantaj yaratır.
- **Uyarı yorgunluğu (alert fatigue).** RC4 bileti veya NTLM oturumu tek başına her zaman kötü değildir; ince ayar yapılmamış kurallar o kadar çok yanlış pozitif üretir ki gerçek olay gürültüde kaybolur. Doğru yaklaşım, sinyalleri bağlam (hesap yetkisi, kaynak, hacim, zamanlama) ile zenginleştirmektir.

---

## En İyi Pratikler

Özet olarak, bu üç tekniğe karşı katmanlı ve birbirini tamamlayan bir duruş şöyle kurulur:

1. **Önce yüzey alanını daralt.** gMSA kullan, RC4'ü kaldır, `krbtgt` ve servis hesabı parolalarını düzenli döndür, yerel yönetici parolalarını benzersizleştir. En iyi tespit, hiç gerçekleşmeyen saldırıdır.
2. **Kimlik bilgisi belleğini koru.** Credential Guard / VBS ile LSASS sırlarını izole et; hash çalınmasını temelden zorlaştır.
3. **Yetkiyi katmanla.** Ayrıcalıklı hesapların düşük güvenli varlıklarda oturum açmasını engelle (tiering). Domain Admins üyeliğini gerçekten gereken en dar kümeye indir.
4. **Doğru telemetriyi topla ve korele et.** Kerberos bilet olaylarında şifreleme türünü ve hacmi, oturum olaylarında kimlik doğrulama paketi ve kaynağı, dizin erişim olaylarında çoğaltma hakkı kullanımını izle. Bunları hesap yetkisi ve zamanlama bağlamıyla birleştir.
5. **DC olmayan kaynaktan gelen çoğaltmayı sıfır tolerans olarak ele al.** Meşru çoğaltma kümesi dar ve bilinen olduğundan, dışındaki her talep incelenmelidir.
6. **Denetimi süreklileştir.** Çoğaltma haklarına kimin sahip olduğunu, hangi hesapların aşırı yetkili olduğunu ve hangi servislerin hâlâ zayıf yapılandırıldığını periyodik olarak gözden geçir. Bu saldırılar statik yapılandırma hatalarından beslenir; denetim onları hareket etmeden yakalar.

Sonuç olarak Kerberoasting, Pass-the-Hash ve DCSync, Windows kimlik altyapısının meşru mekanizmalarının istismarıdır. Bu yüzden onları yenmenin yolu tek bir "yama" değil; protokol davranışını anlayan bir izleme, sıkı bir yetki hijyeni ve kimlik bilgilerini bellekte ve diskte koruyan katmanlı bir mimaridir.
