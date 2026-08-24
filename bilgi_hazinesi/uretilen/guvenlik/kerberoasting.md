# Kerberoasting ve AS-REP Roasting

Active Directory ortamlarında saldırganların en sık başvurduğu iki kimlik doğrulama saldırısı Kerberoasting ve AS-REP Roasting'dir. Her ikisi de Kerberos protokolünün tasarımındaki meşru davranışları kötüye kullanır. Bu iki teknik, ortada bir açık (exploit) veya yamalanmamış bir zafiyet olmadan, protokolün kendi normal akışından yararlanarak çalıştıkları için özellikle tehlikelidir. Bu makale, bu saldırıların neden mümkün olduğunu, nasıl işlediğini, saldırganın bakış açısını ve savunma tarafındaki tedbirleri kök nedenlere inerek açıklar.

## Kerberos'a Kısa Bir Hatırlatma

İki saldırıyı da anlamak için Kerberos'un temel akışını netleştirmek gerekir. Kerberos, parolayı ağ üzerinde açıkça göndermeden kimlik doğrulaması yapan bir bilet (ticket) tabanlı protokoldür. Domain Controller üzerinde çalışan KDC (Key Distribution Center) iki mantıksal bileşenden oluşur: AS (Authentication Service) ve TGS (Ticket Granting Service).

Akış kabaca şöyledir:

1. **AS-REQ / AS-REP:** İstemci kimliğini kanıtlar ve KDC'den bir TGT (Ticket Granting Ticket) alır. Kimlik kanıtı normalde "pre-authentication" ile yapılır: istemci, kendi parolasından türetilen bir anahtarla o anki zaman damgasını (timestamp) şifreler ve KDC'ye gönderir. KDC bunu çözebiliyorsa istemcinin parolayı bildiğine ikna olur.
2. **TGS-REQ / TGS-REP:** İstemci elindeki TGT'yi göstererek belirli bir servise erişim için servis bileti (service ticket) ister. KDC bu bileti, hedef servisin hesabına ait anahtarla şifreler.
3. **AP-REQ:** İstemci servis biletini hedef servise sunar.

Kritik nokta şudur: KDC, servis biletini o servisin hesabının parola hash'inden türetilen anahtarla şifreler. İşte Kerberoasting bu ayrıntıdan doğar.

## Kerberoasting

### Tanım

Kerberoasting, bir SPN (Service Principal Name) tanımlı domain hesabına ait servis biletini KDC'den talep edip, bu biletin şifreli kısmını offline ortamda kaba kuvvetle (brute force) veya sözlük saldırısıyla kırarak servis hesabının açık parolasını elde etme tekniğidir. Saldırı, geçerli bir alan (domain) kullanıcısı olarak kimlik doğrulaması yapabilen herhangi bir hesapla gerçekleştirilebilir.

### Kök Neden: SPN Biletinin Servis Hesabı Anahtarıyla Şifrelenmesi

Kerberoasting'in çalışma mantığı tek bir tasarım gerçeğine dayanır: KDC bir servis bileti ürettiğinde, biletin içindeki bir kısmı hedef servisin hesabının parolasından türetilmiş bir anahtarla şifreler. Bunun mantıklı bir nedeni vardır: bileti alan servis, kendi parolasını bildiği için bileti çözebilmeli ve içindeki oturum anahtarını, yetkileri okuyabilmelidir. Yani şifreleme anahtarının kaynağı servis hesabının parolasıdır.

Buradaki güvenlik varsayımı şudur: "Bileti çözebilen sadece servis hesabıdır, çünkü sadece o parolayı bilir." Ancak bu varsayımda bir çatlak vardır. KDC, servis biletini üretmeden önce istemcinin o servise erişim yetkisi olup olmadığını **kontrol etmez**. Kerberos'un yetkilendirme modeli, "önce bileti al, sonra servise sun, yetkilendirmeyi servis yapsın" şeklindedir. Dolayısıyla herhangi bir geçerli domain kullanıcısı, sisteme hiç bağlanmayacağı bir servis için bile servis bileti isteyebilir. KDC bu bileti sorgusuz üretir ve şifreli haliyle istemciye teslim eder.

İşte kritik sonuç: Saldırgan artık elinde, hedef servis hesabının parolasından türetilmiş bir anahtarla şifrelenmiş bir veri parçası tutmaktadır. Bu şifreli veri, offline bir hash gibi davranır. Saldırgan bileti aldıktan sonra KDC ile hiç konuşmadan, ağdan tamamen kopuk halde, olası parolaları tek tek deneyip biletin şifresini çözmeye çalışabilir. Doğru parolayı bulduğunda çözme işlemi anlamlı, beklenen yapıda bir sonuç verir ve saldırgan parolayı ele geçirir.

### Neden Servis Hesapları Hedef?

Rastgele bir kullanıcının parolasını değil de SPN'li servis hesaplarını hedeflemenin nedeni pratiktir. SPN, bir hesabın bir servis çalıştırdığını gösterir (örneğin bir SQL Server, IIS, veya özel bir uygulama servisi). Bu hesaplar çoğu zaman:

- İnsanlar tarafından yönetildiği için zayıf veya yıllardır değişmemiş parolalara sahip olur.
- Genellikle yüksek ayrıcalıklara (bazen Domain Admin veya benzeri) sahip olacak şekilde yanlış yapılandırılmıştır.
- Parola politikası zorlaması dışında tutulmuş, statik parolalarla çalışır.

Yani saldırgan sadece "kırılabilir bir hash" değil, aynı zamanda "kırıldığında değerli" bir hedef bulur.

### Şifreleme Türünün Önemi (RC4 vs AES)

Kerberoasting'in ne kadar kolay olduğu, servis biletinin hangi şifreleme algoritmasıyla üretildiğine doğrudan bağlıdır. Tarihsel olarak Kerberos, RC4 tabanlı bir şifreleme türünü desteklemiştir ve bu türde biletin şifreleme anahtarı, servis hesabı parolasının NT hash'inden türetilir. NT hash, tuzlanmamış (unsalted) ve nispeten hızlı hesaplanabilen bir yapı olduğu için, saldırgan saniyede çok sayıda parola denemesi yapabilir. Bu, RC4 ile şifrelenmiş biletleri offline kırma açısından çok elverişli kılar.

AES tabanlı şifreleme türlerinde ise anahtar türetme işlemi daha maliyetlidir ve tuzlama içerir; bu da kaba kuvvet denemelerini kayda değer ölçüde yavaşlatır. Bu yüzden saldırganlar mümkün olduğunca biletleri RC4 ile almaya çalışır. Bazı araçlar, talep sırasında istemcinin desteklediği şifreleme türlerini manipüle ederek KDC'yi RC4 bilet üretmeye "ikna etmeyi" dener. Bu nedenle ortamdaki hesapların hangi şifreleme türlerini desteklediği, saldırının başarı ihtimalini belirleyen önemli bir faktördür.

### Sömürü Mantığı (Saldırgan Bakışı)

Saldırının adımları kavramsal olarak şöyle ilerler:

1. **Keşif:** Saldırgan, geçerli bir domain kullanıcısı olarak dizinde (LDAP üzerinden) `servicePrincipalName` özniteliği dolu olan hesapları listeler. Bu, sıradan bir okuma sorgusudur; herhangi bir kimliği doğrulanmış kullanıcı bunu yapabilir. Özellikle yüksek ayrıcalıklı gruplara üye SPN'li hesaplar önceliklendirilir.
2. **Bilet talebi:** Bulunan SPN'ler için KDC'den servis biletleri istenir. Bu tamamen meşru bir TGS-REQ akışıdır; ağ trafiği normal Kerberos trafiğinden ayırt edilmesi zor görünür.
3. **Çıkarma:** Alınan biletlerin şifreli kısmı, offline kırma araçlarının anlayacağı bir formata (hash formatına) dönüştürülüp diske yazılır.
4. **Offline kırma:** Bu hash'ler, saldırganın kendi donanımında sözlük listeleri ve kurallarla denenir. Bu aşama tamamen kurumun ağının dışında gerçekleşebilir, dolayısıyla hesap kilitlenmesi (account lockout) tetiklenmez ve kurumun tarafında doğrudan bir "başarısız giriş" izi bırakmaz.
5. **Kullanım:** Parola kırıldığında saldırgan, o servis hesabının kimliğine bürünerek yanal harekete (lateral movement) veya ayrıcalık yükseltmeye (privilege escalation) geçer.

Bu tekniğin en sinsi yanı, kırma işleminin offline oluşudur. Saldırgan tek bir bilet talebi yaptıktan sonra saatlerce, günlerce parola denemesi yapabilir ve savunma tarafı bunu göremez; çünkü denemeler KDC'ye hiç ulaşmaz.

## AS-REP Roasting

### Tanım

AS-REP Roasting, Kerberos ön kimlik doğrulaması (pre-authentication) devre dışı bırakılmış hesapları hedefleyen bir tekniktir. Bu tür hesaplar için KDC, istemciden herhangi bir kimlik kanıtı istemeden AS-REP yanıtı üretir. Bu yanıtın bir kısmı, hedef kullanıcının parola hash'inden türetilen anahtarla şifrelenmiştir. Saldırgan bu şifreli parçayı alıp offline olarak kırarak kullanıcının parolasını elde edebilir.

### Kök Neden: Pre-authentication'ın Kapalı Olması

Kerberos'ta pre-authentication'ın var oluş amacı tam olarak bu tür saldırıları engellemektir. Normal akışta istemci, AS-REQ içinde parolasından türettiği anahtarla şifrelenmiş bir zaman damgası gönderir. KDC bunu çözemezse istemcinin parolayı bilmediğini anlar ve **AS-REP üretmez**. Böylece bir saldırgan, rastgele bir kullanıcı adı için "bana şifreli yanıt ver de kırayım" diyemez; çünkü önce parolayı kanıtlaması gerekir.

Pre-authentication kapatıldığında bu koruma ortadan kalkar. KDC, "bu kullanıcı gerçekten parolayı biliyor mu?" sorusunu sormadan, sadece kullanıcı adına bakarak bir AS-REP üretir. Bu yanıtın içinde, o kullanıcının parola hash'iyle şifrelenmiş bir kısım vardır. Yani saldırgan, hedefin parolasını hiç bilmeden, sadece geçerli bir kullanıcı adı bilerek, kırılmaya hazır bir şifreli veri elde eder.

Dikkat çekici bir nokta: AS-REP Roasting için saldırganın **kimliği doğrulanmış bir kullanıcı olması bile gerekmeyebilir**. Eğer saldırgan pre-auth kapalı bir hesabın adını biliyorsa, ağdan bu hesap için doğrudan AS-REQ gönderip AS-REP alabilir. Bu, saldırıyı Kerberoasting'den bile daha "önce" gerçekleştirilebilir hale getirir; çünkü Kerberoasting için en azından geçerli bir domain kimliği gerekir, AS-REP Roasting için ise bazen sadece kullanıcı adı listesi yeterlidir.

### Pre-authentication Neden Kapatılır?

Bu ayarın kötü niyetle değil, çoğunlukla uyumluluk (compatibility) sebebiyle açık bırakıldığını anlamak önemlidir. Bazı eski uygulamalar veya Kerberos'u tam desteklemeyen istemciler pre-authentication ile sorun yaşayabilir. Yönetici, "çalışsın" diye ilgili hesapta "Kerberos pre-authentication gerektirme" ayarını devre dışı bırakır ve zamanla bu unutulur. İşte bu unutulmuş ayarlar, AS-REP Roasting'in yem havuzunu oluşturur. Bu yüzden savunmada asıl mesele, bu ayarın hangi hesaplarda ve neden açık olduğunu bilmektir.

### Sömürü Mantığı (Saldırgan Bakışı)

1. **Keşif:** Saldırgan, dizinde `userAccountControl` özniteliğinde "pre-authentication gerektirme" bayrağı (DONT_REQUIRE_PREAUTH) set edilmiş hesapları arar. Eğer domain erişimi yoksa, elindeki olası kullanıcı adı listesini kaba kuvvetle deneyerek pre-auth kapalı hesapları tespit etmeye çalışır.
2. **AS-REQ gönderimi:** Hedef hesap için pre-auth verisi olmadan AS-REQ gönderilir.
3. **AS-REP alımı:** KDC, pre-auth kapalı olduğu için şifreli parçayı içeren AS-REP'i döner.
4. **Offline kırma:** Şifreli kısım hash formatına dönüştürülür ve tıpkı Kerberoasting'deki gibi offline kırılır.

Yine kritik özellik offline kırmadır: KDC ile tek bir etkileşim yeterlidir, geri kalan tüm parola denemeleri ağ dışında yapılır ve hesap kilitlenmesini tetiklemez.

## İki Saldırının Karşılaştırması

Bu iki teknik akrabadır ama önemli farklar taşır:

- **Hedef anahtar:** Kerberoasting'de kırılan şey, **servis hesabının** parola hash'idir (TGS-REP içinden). AS-REP Roasting'de kırılan şey, **kullanıcı hesabının** parola hash'idir (AS-REP içinden).
- **Ön koşul:** Kerberoasting normalde geçerli bir domain kullanıcısı gerektirir. AS-REP Roasting bazen sadece geçerli bir kullanıcı adı bilmeyi gerektirir.
- **Tetikleyen yanlış yapılandırma:** Kerberoasting, SPN atanmış (çoğu zaman zayıf parolalı) hesapların varlığından beslenir. AS-REP Roasting, pre-authentication'ın kapalı olmasından beslenir.
- **Ortak nokta:** Her ikisi de KDC'nin ürettiği, parola hash'iyle şifrelenmiş bir veriyi offline kırmaya dayanır. Her ikisi de protokolün meşru davranışını kullanır, bir "zafiyet" sömürmez. Her ikisinin de nihai çaresi **güçlü, uzun, tahmin edilemez parolalardır**; çünkü offline kırmanın tek gerçek düşmanı entropidir.

## Ortak Zayıf Halka: Offline Kırma ve Parola Entropisi

Her iki saldırının kalbindeki gerçek şudur: KDC, parola tabanlı bir anahtarla şifrelenmiş bir çıktıyı saldırgana teslim eder ve saldırgan bunu sınırsız süreyle, izlenmeden deneyebilir. Bu noktada tüm güvenlik, parolanın kırılamaz kadar güçlü olmasına indirgenir.

Bu neden bu kadar önemli? Çünkü offline kırmada saldırganın deneme hızı sadece kendi donanımıyla sınırlıdır. Modern GPU'larla, özellikle RC4 tabanlı zayıf türlerde, saniyede milyarlarca deneme mümkün olabilir. Bu yüzden:

- 8-10 karakterlik, tahmin edilebilir kalıplı bir servis parolası pratikte "açık" sayılmalıdır.
- Buna karşılık 25+ karakterlik, rastgele üretilmiş bir parola, mevcut hesaplama gücüyle makul sürede kırılamaz. Saldırgan biletle ne kadar uğraşırsa uğraşsın, entropi yeterince yüksekse offline kırma başarısız olur.

Bu yüzden savunmanın temel taşı, kriptografik değil, operasyoneldir: doğru parolalar ve doğru hesap yönetimi.

## Savunma

Savunmayı katmanlı düşünmek gerekir: bazı önlemler saldırıyı imkânsıza yaklaştırır, bazıları ise saldırıyı tespit edilebilir kılar.

### 1. Güçlü ve Uzun Parolalar (Özellikle gMSA Kullanımı)

Servis hesapları için en etkili çözüm, insan tarafından yönetilen statik parolalar yerine **Group Managed Service Account (gMSA)** kullanmaktır. gMSA hesaplarında parola, Active Directory tarafından otomatik olarak üretilir, çok uzun ve yüksek entropilidir ve düzenli aralıklarla otomatik döndürülür (rotate edilir). Böyle bir hesabın servis bileti Kerberoast edilse bile, offline kırma pratikte başarısız olur; çünkü kırılacak parola tahmin edilebilir değildir. gMSA'ya geçilemeyen durumlarda, servis hesaplarına en az 25-30 karakterlik, rastgele üretilmiş parolalar atanmalı ve bunlar düzenli olarak değiştirilmelidir. Bu tek önlem bile Kerberoasting'in çoğunu etkisiz kılar.

### 2. Pre-authentication'ı Her Yerde Zorunlu Kılmak

AS-REP Roasting'in kökündeki neden pre-auth'un kapalı olmasıdır. Dolayısıyla savunma nettir: dizindeki tüm hesaplar düzenli olarak taranmalı ve "pre-authentication gerektirme" bayrağı set edilmiş hesaplar tespit edilmelidir. Gerçekten gerekli olmadıkça bu ayar kapatılmalıdır. Eğer bir hesapta uyumluluk nedeniyle bu ayar gerekiyorsa, o hesabın parolası özellikle güçlü olmalı ve hesap sıkı izlenmelidir. Bu tarama periyodik bir hijyen görevi olarak kurumsal süreçlere yerleştirilmelidir; çünkü yeni yanlış yapılandırmalar zamanla sızabilir.

### 3. RC4'ü Devre Dışı Bırakmak / AES'e Geçmek

Zayıf RC4 tabanlı şifreleme türleri, offline kırmayı büyük ölçüde kolaylaştırdığından, ortamda mümkün olduğunca AES şifreleme türlerine geçilmeli ve RC4 devre dışı bırakılmalıdır. Bu değişiklik dikkatli planlanmalıdır: RC4'ü aniden kapatmak eski istemcilerde veya güven ilişkilerinde (trust) kimlik doğrulama arızalarına yol açabilir. Bu yüzden önce hangi hesapların ve istemcilerin hâlâ RC4'e bağımlı olduğunu tespit eden bir gözlem dönemi uygulanmalı, sonra kademeli geçiş yapılmalıdır. RC4'ü tamamen kaldırmak Kerberoasting'i imkânsız yapmaz ama kırma maliyetini ciddi biçimde artırır.

### 4. En Az Ayrıcalık İlkesi

SPN'li servis hesaplarının yüksek ayrıcalıklı gruplara (özellikle Domain Admins gibi) üye olmaması sağlanmalıdır. Bir servis hesabının parolası kırılsa bile, o hesabın yetkisi düşükse saldırganın kazancı sınırlı olur. Kerberoasting'i asıl yıkıcı yapan şey, kırılan hesabın yüksek ayrıcalıklı olmasıdır. Servis hesaplarına yalnızca gerçekten ihtiyaç duydukları izinler verilmelidir. Ayrıca gereksiz veya artık kullanılmayan SPN'ler dizinden temizlenmeli, saldırı yüzeyi küçültülmelidir.

### 5. Tespit ve İzleme

Bu saldırıların offline kısmı görünmez olsa da, KDC ile yapılan **ilk etkileşim** iz bırakır ve savunma bu izlere odaklanmalıdır:

- **Anormal servis bileti talepleri:** Kısa süre içinde çok sayıda farklı SPN için servis bileti (TGS) talep edilmesi, özellikle bunların RC4 türünde istenmesi güçlü bir Kerberoasting işaretidir. Bilet talep olaylarında şifreleme türünün loglanması ve RC4 taleplerinin dikkatle izlenmesi önemlidir. Normal bir kullanıcının kısa sürede onlarca farklı servise bilet istemesi beklenmez.
- **Pre-auth olmadan AS-REP üretimi:** Pre-authentication olmadan gerçekleşen kimlik doğrulama olayları AS-REP Roasting'e işaret edebilir. Bu olayların ayrıca değerlendirilmesi gerekir.
- **Bal küpü (honeypot) hesaplar:** Kasıtlı olarak SPN atanmış ama hiçbir gerçek servisi olmayan bir "tuzak" hesap oluşturmak etkili bir tespit yöntemidir. Bu hesabın servis bileti hiçbir meşru sebeple talep edilmemelidir; herhangi bir talep neredeyse kesinlikle bir Kerberoasting keşfidir. Aynı mantıkla, kasıtlı pre-auth kapalı bir tuzak hesap AS-REP Roasting keşfini yakalamak için kullanılabilir. Bu tuzak hesapların parolası güçlü olmalıdır ki saldırgan kırıp gerçekten kullanamasın.

Tespit stratejisinin özü şudur: offline kırmayı göremeyiz, ama saldırganı ganimeti toplarken (bilet talep ederken) yakalayabiliriz.

## Yaygın Hatalar

Sahada tekrar tekrar görülen ve bu saldırıları mümkün kılan hatalar şunlardır:

- **Servis hesaplarına zayıf, kısa veya yıllardır değişmeyen parolalar vermek.** Bu, Kerberoasting'in bir numaralı sebebidir. "Nasılsa Kerberos parolayı ağda göndermiyor" diye düşünülür, ama offline kırma bu güveni geçersiz kılar.
- **Servis hesaplarını Domain Admins gibi gruplara koymak.** Kolaylık olsun diye verilen bu ayrıcalık, kırılan bir servis hesabını tüm alanın anahtarına dönüştürür.
- **Pre-authentication'ı kapatıp unutmak.** Bir uyumluluk sorununu çözmek için geçici diye kapatılan ayar kalıcı bir açık kapı olur.
- **RC4'e bağımlılığı bilmeden sürdürmek.** Ortamın hangi kısımlarının hâlâ RC4 kullandığını izlememek, hem saldırıyı kolaylaştırır hem de AES geçişini geciktirir.
- **Ölü SPN'leri temizlememek.** Artık var olmayan servislere ait SPN'ler saldırı yüzeyini boşuna genişletir.
- **Sadece "başarısız giriş" loglarına güvenmek.** Bu saldırılar başarısız giriş üretmez; başarılı ama anormal bilet talepleri üretir. Tespit stratejisini yanlış sinyale kurmak, saldırıyı tamamen görünmez kılar.
- **Tespit için honeypot hesabına zayıf parola koymak.** Tuzak işe yarar ama parolası zayıfsa saldırgan onu da kırıp gerçek bir dayanak noktası edinebilir.

## En İyi Pratikler (Özet)

1. Servis hesapları için mümkünse **gMSA** kullanın; değilse çok uzun, rastgele ve düzenli döndürülen parolalar atayın.
2. Dizini periyodik olarak tarayarak **pre-authentication kapalı** hesapları bulun ve gerekmiyorsa bu ayarı geri açın.
3. **RC4'ü kademeli olarak devre dışı bırakıp AES'e geçin**; önce bağımlılıkları tespit edin, sonra planlı geçiş yapın.
4. **En az ayrıcalık** ilkesini servis hesaplarına titizlikle uygulayın; hiçbir servis hesabı gereğinden fazla yetkiye sahip olmamalı.
5. **Ölü ve gereksiz SPN'leri** düzenli olarak temizleyin.
6. Tespit stratejinizi **anormal bilet talebi** ve **şifreleme türü** üzerine kurun; sadece başarısız girişlere güvenmeyin.
7. **Honeypot hesaplar** yerleştirerek keşif aşamasını erken yakalayın; bu hesapların parolalarını güçlü tutun.
8. Bu kontrolleri tek seferlik bir proje değil, **süreklilik gerektiren bir hijyen** olarak ele alın; çünkü yeni yanlış yapılandırmalar zamanla ortama sızar.

## Sonuç

Kerberoasting ve AS-REP Roasting, yamalanacak bir yazılım hatası değil, Kerberos'un tasarımındaki meşru davranışların kötüye kullanımıdır. İkisinin de kalbinde aynı gerçek yatar: KDC, parola tabanlı bir anahtarla şifrelenmiş bir veriyi saldırgana teslim eder ve saldırgan bunu offline, izlenmeden, sınırsızca kırmayı deneyebilir. Bu yüzden asıl savunma kriptografik bir numara değil, disiplinli operasyondur: güçlü ve otomatik yönetilen parolalar, gereksiz açık bırakılan ayarların kapatılması, zayıf şifreleme türlerinin emekliye ayrılması, en az ayrıcalık ve akıllı tespit. Bu saldırıların "sessiz" doğasını anlayan bir savunmacı, saldırganı kıramayacağı bir parolayla ya da ganimeti toplarken bıraktığı izle yakalar. Nihayetinde, offline kırmanın tek gerçek düşmanı entropidir; ve entropiyi de yalnızca doğru parola ve hesap hijyeni sağlar.
