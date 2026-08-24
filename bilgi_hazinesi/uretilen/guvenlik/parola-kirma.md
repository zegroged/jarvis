# Parola Kırma (Password Cracking): hashcat ve John the Ripper ile Derin Bir Bakış

## Tanım

Parola kırma, bir sisteme sızmak için parolanın *kendisini* değil, o paroladan matematiksel olarak türetilmiş bir izin — genellikle bir **hash** değerinin — tersine çevrilmesi ya da tahmin edilmesi işlemidir. Modern sistemler parolayı düz metin (plaintext) olarak asla saklamaz; bunun yerine tek yönlü (one-way) bir fonksiyondan geçirip elde edilen sabit uzunluktaki çıktıyı depolar. Saldırgan bir veritabanı sızıntısı, bir bellek dökümü ya da bir ağ yakalaması yoluyla bu hash'lere ulaştığında, elindeki tek yönlü çıktıdan orijinal parolayı geri getirmeye çalışır.

Buradaki kilit nokta şudur: hash fonksiyonu matematiksel olarak *tersine çevrilemez* olduğu için, saldırgan hash'i "çözmez"; bunun yerine milyarlarca aday parolayı sırayla aynı hash fonksiyonundan geçirir ve çıktıları elindeki hedef hash ile karşılaştırır. Eşleşme bulunduğunda, o adayın parola olduğu anlaşılır. **hashcat** ve **John the Ripper** (kısaca *John* ya da *JtR*), bu tahmin-ve-karşılaştır döngüsünü olabildiğince hızlı çeviren iki endüstri standardı araçtır.

Bu makale hash türlerini, kırma tekniklerini (sözlük, mask, rule), donanım hızlandırmayı ve — en önemlisi — hem saldırının hem de savunmanın mantığını "neden böyle" sorusuna cevap verecek şekilde ele alır.

## Kök Neden: Neden Parola Kırma Mümkün?

Parola kırmanın mümkün olmasının tek bir kök nedeni vardır: **insanların seçtiği parolaların entropisi düşüktür.** Teorik olarak, saldırgan tüm olası kombinasyonları denemek zorunda olsaydı (yani gerçek *brute force*), makul uzunluktaki bir parola bile evrenin ömründen daha uzun süre dayanırdı. Ama insanlar `Ankara2023!`, `parola123` ya da `Ahmet.1985` gibi tahmin edilebilir örüntüler kullanır. Kırma araçlarının tüm zekâsı, bu tahmin edilebilirliği matematiksel bir avantaja çevirmekten ibarettir.

Bunun altında yatan üç yapısal gerçek şudur:

**Birincisi, hash fonksiyonu hızlı olduğunda saldırgan da hızlı olur.** MD5 veya SHA-1 gibi fonksiyonlar aslında dosya bütünlüğü kontrolü için tasarlanmıştı; saniyede milyarlarca kez çalışacak kadar hızlıdırlar. Parola saklamak için bu hızları bir *kusurdur*, çünkü saldırganın da saniyede milyarlarca tahmin yapmasını sağlar. Modern bir GPU üzerinde MD5 için saniyede on milyarlarca hash hesaplanabilir.

**İkincisi, aynı parola aynı hash'i üretiyorsa saldırgan önceden hesaplayabilir.** Eğer `123456` her sistemde aynı hash'e dönüşüyorsa, saldırgan bir kez hesaplayıp bir tabloda saklar (bkz. rainbow table) ve bir daha hiç hesaplamaz. **Salt** (tuz) mekanizması tam da bunu kırmak için vardır.

**Üçüncüsü, parola alanı (keyspace) düzgün dağılmamıştır.** Olası tüm parolaların uzayında insanların gerçekten kullandığı parolalar minik, yoğun kümeler halinde toplanır. Saldırgan tüm uzayı taramak yerine bu yoğun kümelere odaklanır — sözlük saldırısının ve rule tabanlı dönüşümlerin özü budur.

## Hash Türleri ve Neden Önemli Oldukları

Bir hash'i kırma hızı, neredeyse tamamen o hash'in *türüne* bağlıdır. Saldırgan için ilk iş, elindeki hash'in hangi algoritmayla üretildiğini tespit etmektir; çünkü hashcat ve John, her algoritma için farklı bir "mod" ile çalışır.

### Hızlı, tuzsuz hash'ler: MD5, SHA-1, SHA-256 (çıplak)

Bu fonksiyonlar tek geçişte (single-pass) çalışır ve tuz içermez. Bir saldırgan için en kolay hedeftirler. `5f4dcc3b5aa765d61d8327deb882cf99` gördüğünüzde bu klasik olarak `password` kelimesinin MD5'idir. Bu tür hash'ler kelimenin tam anlamıyla saniyeler içinde büyük sözlüklerle taranabilir. Ham SHA-256 bile, tuzsuz ve tek geçişli olduğu için parola saklama açısından güvenli sayılmaz — güçlü bir kriptografik hash olması onu *yavaş* yapmaz.

### Tuzlanmış (salted) hash'ler

Salt, her parolaya eklenen rastgele bir dizedir. Aynı parola iki farklı kullanıcıda farklı hash üretir. Bu, önceden hesaplanmış tabloları (rainbow table) işe yaramaz hale getirir ve saldırganı her hash için tahminleri *yeniden* hesaplamaya zorlar. Salt hızı düşürmez ama toplu (önceden hesaplama) avantajını yok eder.

### Kasıtlı olarak yavaşlatılmış hash'ler: bcrypt, scrypt, Argon2, PBKDF2

Bunlar *parola saklama için tasarlanmış* modern fonksiyonlardır ve temel özellikleri **kasıtlı yavaşlıktır**. bcrypt bir "cost factor" (maliyet katsayısı) alır; bu katsayı her artırıldığında hesaplama süresi katlanır. Argon2 ve scrypt buna ek olarak **bellek-zorluğu (memory-hardness)** getirir: hash'i hesaplamak yalnızca CPU değil, ciddi miktarda RAM de gerektirir. Bu, GPU'ların paralel gücünü etkisiz kılar, çünkü bir GPU'da binlerce çekirdek olsa da her birine yetecek hızlı bellek yoktur.

Sonuç şudur: MD5 üzerinde saniyede milyarlarca deneme yapan bir saldırgan, iyi yapılandırılmış bir bcrypt üzerinde saniyede belki yalnızca birkaç bin, Argon2 üzerinde daha da az deneme yapabilir. Bu, saldırının ekonomisini tamamen değiştirir.

### Kimlik doğrulama protokollerinden gelen hash'ler

Ham parola hash'lerinin yanında, ele geçirilen ağ trafiğinden ya da işletim sisteminden çıkan formatlar da vardır: Windows'un **NTLM** hash'leri, kablosuz ağlardan yakalanan **WPA/WPA2 handshake**'leri, Active Directory'den **Kerberos** biletleri (Kerberoasting saldırısının hedefi) ve `/etc/shadow` içindeki Linux parola formatları. Her biri hashcat ve John'da ayrı bir moda karşılık gelir. NTLM'in hızlı ve tuzsuz oluşu, onu iç ağ saldırılarında öncelikli bir hedef yapar.

Doğru modu seçmek kritiktir: yanlış modda çalıştırılan bir kırma denemesi ya hiç eşleşme bulamaz ya da tamamen zaman kaybıdır. hashcat'te bu mod bir sayı ile (`-m` bayrağı ile bir hash türü numarası) seçilir; John genellikle formatı otomatik algılamaya çalışır ama `--format` ile açıkça belirtmek daha güvenilirdir. (Buradaki tam numaraları ezberden vermek yerine, aracın kendi hash türü listesine — hashcat için `--help` çıktısına — bakmanızı öneririm; bu liste sürümle birlikte değişir.)

## Kırma Teknikleri: Sözlük, Mask ve Rule

Aday parolaların nasıl üretildiği, bir kırma kampanyasının başarısını belirleyen asıl stratejik karardır. Üç temel yaklaşım vardır ve deneyimli bir saldırgan bunları katmanlı biçimde birleştirir.

### Sözlük (dictionary / wordlist) saldırısı

En temel yaklaşım, bilinen parolalardan oluşan büyük bir metin dosyasını (wordlist) sırayla denemektir. Buradaki en meşhur liste, gerçek bir sızıntıdan türetilmiş olan `rockyou.txt`'tir. Sözlük saldırısının mantığı doğrudan kök nedene bağlıdır: madem insanlar tahmin edilebilir parolalar seçiyor, o halde geçmişte sızmış gerçek parolaların listesi, gelecekteki parolaların da güçlü bir tahminidir. İnsan davranışı zaman içinde tutarlıdır.

Sözlük saldırısı, iyi bir listeyle, tüm keyspace'i taramaktan milyonlarca kat verimlidir çünkü doğrudan yoğun kümelere gider.

### Rule tabanlı dönüşümler

Saf sözlük çoğu zaman yetmez, çünkü kullanıcılar `password` yazmaz — `Password1!`, `P@ssw0rd` ya da `password2023` yazar. **Rule** (kural) mekanizması işte bu insan davranışını modeller. Bir kural, sözlükteki her kelimeye uygulanacak bir dönüşüm tanımlar: ilk harfi büyük yap, sonuna rakam ekle, `a` harfini `@` ile değiştir (leetspeak), kelimeyi tersine çevir, sonuna yıl ekle gibi.

Rule'ların gücü, tek bir kelimeyi yüzlerce varyanta genişletmesindedir. `hashcat`'in `best64.rule` gibi hazır kural setleri, en yaygın insan parola örüntülerini damıtılmış biçimde içerir. Böylece 10 milyonluk bir sözlük, iyi bir kural setiyle etkin olarak milyarlarca aday üretir — ama bunlar rastgele milyarlar değil, *gerçekçi* milyarlardır. İşte verimlilik burada yatar.

### Mask (brute force ama akıllısı)

Mask saldırısı, aslında kısıtlanmış bir brute force'tur. Saf brute force her karakteri her pozisyonda dener; bu, uzun parolalar için imkânsızdır. Mask ise parolanın *yapısı* hakkında bir tahmine dayanır. Örneğin çoğu parolanın "büyük harf + küçük harfler + rakamlar + bir sembol" düzeninde olduğunu bildiğinizde, yalnızca o düzendeki kombinasyonları denersiniz.

hashcat'te karakter kümeleri sembollerle ifade edilir: bir yer tutucu küçük harfleri, bir başkası büyük harfleri, bir başkası rakamları temsil eder. `?u?l?l?l?l?l?d?d` gibi bir mask, "bir büyük harf, beş küçük harf, iki rakam" düzenindeki tüm parolaları dener — bu, `Ankara2023` benzeri Türkçe parolalar için tipik bir örüntüdür. Mask, keyspace'i insan örüntülerine göre budayarak brute force'u ulaşılabilir kılar.

Deneyimli bir saldırgan bunları katmanlar: önce hızlı bir sözlük, sonra sözlük + rule, sonra hedeflenmiş mask'ler, en son da parası varsa geniş brute force. Ucuz ve olası olandan pahalı ve olası olmayana doğru ilerlenir.

## GPU ve Donanım: Neden Hız Bu Kadar Önemli?

Parola kırma **utanç verici derecede paralel (embarrassingly parallel)** bir problemdir: her aday parolanın hash'i, diğerlerinden tamamen bağımsız olarak hesaplanabilir. Bu, işi binlerce çekirdeğe dağıtmak için mükemmel bir zemindir — ve tam olarak modern GPU'ların (grafik işlemcilerin) yaptığı şey budur.

Bir CPU'da az sayıda güçlü çekirdek varken, bir GPU'da binlerce basit çekirdek bulunur. Hash hesaplama gibi basit ama tekrarlı bir iş için GPU, bir CPU'dan yüzlerce kat daha hızlı olabilir. hashcat özellikle GPU üzerinde çalışmak için optimize edilmiştir ve bu yüzden ham hız gerektiren senaryolarda tercih edilir. John the Ripper ise geleneksel olarak CPU üzerinde güçlüdür, çok geniş format desteğine ve akıllı otomatik algılama yeteneklerine sahiptir; GPU desteği de vardır ama hashcat'in ham GPU verimliliği çoğu benchmark'ta öne çıkar.

Bu donanım gerçeği, savunma tarafında doğrudan bir sonuç doğurur: **savunma, saldırganın hızını düşürecek algoritmalar seçmek zorundadır.** MD5 gibi GPU-dostu bir fonksiyon seçtiğinizde, saldırgana milyar-kat hız hediyesi vermiş olursunuz. bcrypt/Argon2 gibi GPU-düşmanı (bellek-zorluğu olan) fonksiyonlar seçtiğinizde ise GPU'nun paralel gücünü büyük ölçüde etkisizleştirirsiniz. Kırma araçlarının GPU'ya bu kadar bağımlı olması, aslında savunma stratejisini yazan asıl faktördür.

Bir diğer nokta, ölçeklenebilirliktir: saldırgan bir bulut sağlayıcısından saatlik ücretle çok sayıda GPU kiralayabilir. Yani "benim tek GPU'm bunu kıramaz" mantığı yanıltıcıdır; belirlenmiş bir saldırganın erişebileceği hesaplama gücü neredeyse süreklidir. Savunma bu varsayımla tasarlanmalıdır.

## Sömürü Mantığı ve Savunma: İki Yüz Bir Arada

### Sömürü tarafında saldırının anatomisi

Bir saldırgan için parola kırma nadiren bağımsız bir eylemdir; genellikle daha büyük bir saldırı zincirinin halkasıdır. Tipik akış şöyledir: önce hash'ler ele geçirilir (veritabanı sızıntısı, `/etc/shadow` erişimi, bellek dökümü, ağ yakalaması ya da Active Directory'den Kerberoasting ile). Sonra hash türü tespit edilir. Ardından ucuzdan pahalıya doğru — sözlük, rule, mask — kırma denemeleri sıralanır. Kırılan parolalar sadece o hesabı değil, **parola tekrar kullanımı (password reuse)** yüzünden başka sistemleri de açar; bu, *credential stuffing* saldırılarının temelidir.

İç ağ senaryosunda kırılan bir NTLM ya da Kerberos parolası, yanal harekete (lateral movement) ve ayrıcalık yükseltmeye (privilege escalation) kapı açar. Bu yüzden tek bir zayıf parola bile, tüm bir kurumsal ağın düşmesine giden zincirin ilk halkası olabilir.

### Savunma tarafında her saldırı adımına karşı önlem

Savunmanın güzelliği, saldırının her adımına karşılık gelen bir katman sunmasıdır:

**Yavaş, bellek-zorlu hash kullanın.** En temel savunma budur. Yeni sistemlerde **Argon2** (özellikle Argon2id), bulunamıyorsa **scrypt** ya da **bcrypt** kullanın. MD5, SHA-1 ve ham SHA-256'yı parola saklama için asla kullanmayın. Bu tek karar, saldırganın deneme hızını milyarlarca kattan binlere düşürür — kırmanın ekonomisini kökten değiştirir.

**Her parolaya benzersiz salt ekleyin.** Bu, önceden hesaplanmış tabloları ve toplu kırmayı imkânsızlaştırır. Modern algoritmalar (bcrypt, Argon2) salt'ı zaten otomatik yönetir; kendi elinizle hash yazmaya çalışmayın.

**Pepper (biber) ekleyin.** Salt'tan farklı olarak pepper, veritabanında değil ayrı ve korunan bir yerde (ideal olarak bir HSM ya da gizli anahtar deposunda) tutulan gizli bir değerdir. Böylece yalnızca veritabanı sızarsa, saldırganın elinde hash'leri kırmak için gereken sırrın *bir kısmı* eksik kalır.

**Parola politikasını entropiye göre kurun, keyfi kurallara göre değil.** Uzunluk, karmaşıklıktan daha değerlidir; `?u?l?l?l?l?l?d?d` mask'inin neden bu kadar etkili olduğunu hatırlayın — çünkü zorunlu karmaşıklık kuralları insanları tahmin edilebilir örüntülere iter. Uzun parola cümleleri (passphrase) hem hatırlanabilir hem de mask/rule saldırılarına dirençlidir.

**Sızmış parolaları engelleyin.** Kullanıcı kayıt olurken parolasını bilinen sızıntı listelerine karşı kontrol edin (örneğin bir "have I been pwned" tipi kontrol). Bu, sözlük saldırısının temel dayanağını — gerçek sızmış parolaları — daha en baştan devre dışı bırakır.

**Çok faktörlü kimlik doğrulama (MFA) uygulayın.** Bu en önemli katmandır: parola kırılsa bile, ikinci faktör olmadan giriş yapılamaz. MFA, parola kırmanın etkisini büyük ölçüde nötralize eder ve bu yüzden savunma önceliklerinin en üstünde olmalıdır.

**Hız sınırlama ve hesap kilitleme uygulayın.** Bu, hash'i ele geçirmiş bir saldırganın *çevrimdışı* kırmasına engel olmaz — ama *çevrimiçi* (canlı sisteme karşı) tahmin saldırılarını, credential stuffing'i ve brute force giriş denemelerini durdurur.

**Sızıntı tespitini ve rotasyonu hazırlayın.** Bir hash sızıntısı olduğunu varsayarak plan yapın: parola sıfırlama akışları, anomali tespiti ve gerektiğinde toplu rotasyon süreçleri önceden tasarlanmalıdır.

Dikkat edin: savunma tekil bir sihirli çözüm değil, katmanlı bir yaklaşımdır (defense in depth). Yavaş hash saldırganı yavaşlatır, salt toplu avantajı yok eder, MFA kırılan parolayı işe yaramaz kılar, sızıntı kontrolü kötü parolaları baştan eler. Hiçbiri tek başına yeterli değildir; birlikte etkilidirler.

## Yaygın Hatalar

**Kriptografik olarak güçlü ama hızlı hash'i "güvenli" sanmak.** En sık yapılan hata budur. SHA-256 mükemmel bir kriptografik hash'tir, ama parola saklama için *yanlış araçtır* çünkü hızlıdır. Güçlülük ile yavaşlık farklı özelliklerdir; parola için ikisi birden gerekir.

**Kendi hash şemasını yazmaya çalışmak.** "Ben SHA-256'yı üç kez arka arkaya çalıştırırım, daha güvenli olur" mantığı bir yanılgıdır. Ev yapımı şemalar neredeyse her zaman ince kusurlar içerir. Test edilmiş, standart kütüphaneleri (bcrypt, Argon2 implementasyonları) kullanın.

**Salt'ı sabit ya da tahmin edilebilir yapmak.** Tüm kullanıcılar için aynı salt kullanmak, salt'ın tüm amacını boşa çıkarır. Salt kullanıcı başına benzersiz ve rastgele olmalıdır.

**Karmaşıklık kurallarını uzunluğun önüne koymak.** "En az bir büyük harf, bir rakam, bir sembol" zorunluluğu kullanıcıları `Parola1!` gibi tahmin edilebilir örüntülere iter — ki bunlar tam da mask ve rule saldırılarının hedeflediği örüntülerdir. Uzunluğu önceliklendirin.

**Parola politikasının çevrimdışı kırmayı durdurduğunu sanmak.** Hesap kilitleme ve hız sınırlama yalnızca canlı sisteme karşı işe yarar. Saldırgan hash'i ele geçirdiyse, sizin sunucunuza hiç dokunmadan kendi donanımında istediği kadar deneme yapabilir. Çevrimdışı savunmanın tek yolu yavaş hash + güçlü entropidir.

**Yetkisiz kırma yapmak.** hashcat ve John güçlü araçlardır ve yalnızca *kendi* sistemlerinizde, sızma testi sözleşmeleri kapsamında ya da açık yazılı izinle kullanılmalıdır. Başkasının hash'lerini izinsiz kırmak birçok hukuk düzeninde suçtur. Bu araçların meşru yeri, savunmayı test etmek ve zayıf parolaları saldırgandan önce bulmaktır.

## En İyi Pratikler

Bir güvenlik uzmanı olarak, hem savunmayı kurarken hem de yetkili bir sızma testinde bu araçları kullanırken şu ilkeleri benimseyin:

**Savunma için:** Yeni bir sistemde parola saklarken varsayılan tercihiniz **Argon2id** olsun; uygun parametrelerle (yeterli bellek ve iterasyon maliyeti) yapılandırın. Salt'ı kütüphaneye bırakın, pepper'ı ayrı saklayın, MFA'yı zorunlu kılın ve kayıt anında sızmış-parola kontrolü yapın. Parametreleri zamanla artırın — donanım hızlandıkça bugünkü "yeterince yavaş" ayar yarın yetersiz kalır; bu yüzden maliyet katsayınızı periyodik gözden geçirin.

**Kendi savunmanızı test etmek için:** Kendi kullanıcı hash'lerinizi (yetkiyle) hashcat ya da John ile taramak, zayıf parolaları saldırgandan önce bulmanın en etkili yoludur. Önce hızlı bir `rockyou.txt` + `best64` denemesi, hangi hesapların anında düştüğünü gösterir; bu hesaplara zorunlu parola sıfırlama uygularsınız. Bu, teorik bir risk değerlendirmesinden çok daha ikna edicidir.

**Doğru aracı doğru işe seçin:** Ham GPU hızı ve modern hash türleri için hashcat; çok geniş ve egzotik format desteği, otomatik algılama ve CPU esnekliği için John the Ripper güçlüdür. İkisini birlikte kullanan pratisyenler yaygındır.

**Katmanlı düşünün:** Hiçbir tek önlem yeterli değildir. Yavaş hash saldırganın hızını, MFA kırılan parolanın etkisini, sızıntı kontrolü kötü parola girişini, hız sınırlama canlı saldırıyı hedefler. Güvenlik bu katmanların birleşiminden doğar.

**Ölçüp güncelleyin:** Hash algoritma parametreleriniz statik olmamalıdır. Donanımın her yıl ucuzlayıp hızlandığı bir dünyada, bugün güvenli olan maliyet ayarı birkaç yıl içinde zayıflar. Parola güvenliğini "bir kez ayarla, unut" değil, süregelen bir mühendislik disiplini olarak ele alın.

Özetle: parola kırmanın matematiği saldırganın lehine değil — asıl açık, insanların düşük entropili parola seçmesi ve sistemlerin hızlı hash kullanmasıdır. Bu iki kök nedeni ortadan kaldırdığınızda (yavaş/bellek-zorlu hash + güçlü entropi + MFA), hashcat ve John gibi araçların önündeki matematiksel duvar, kırılamayacak kadar yükselir.
