# TLS İç Yapısı ve Saldırıları

## Giriş: TLS Neden Var ve Neyi Çözer?

TLS (Transport Layer Security), güvenilmez bir ağ üzerinde iki taraf arasında **gizlilik** (confidentiality), **bütünlük** (integrity) ve **kimlik doğrulama** (authentication) sağlayan bir protokoldür. Temelde çözdüğü problem şudur: İnternet, paketlerinizi gören, kaydeden, hatta değiştirebilen düşman aktörlerle dolu bir ortamdır. Klasik tehdit modelinde bir saldırgan ağ yolunun ortasında oturur; buna **MITM** (man-in-the-middle) denir. TLS'in tüm tasarımı, bu ortadaki saldırgan varken bile iki ucun güvenli konuşabilmesini hedefler.

TLS'i doğru anlamak için üç ayrı güvenlik hedefini birbirinden ayırmak gerekir çünkü saldırıların çoğu bu hedeflerden **yalnızca birini** kırmayı amaçlar. Gizlilik, verinin okunamamasıdır (şifreleme). Bütünlük, verinin fark edilmeden değiştirilememesidir (MAC / AEAD). Kimlik doğrulama ise "konuştuğum taraf gerçekten iddia ettiği kişi mi?" sorusudur (sertifikalar). İlginç olan şu: Şifreleme mükemmel olsa bile kimlik doğrulama zayıfsa saldırgan araya girip **kendi** şifreli tünelini kurabilir. Bu yüzden sertifika doğrulaması, TLS güvenliğinin en kritik ve pratikte en sık hatalı uygulanan parçasıdır.

---

## Handshake: TLS'in Kalbi

### Handshake Neden Gereklidir?

Şifreli konuşma yapmak için iki tarafın ortak bir anahtar üzerinde anlaşması gerekir. Ama bu anlaşmayı, dinleyen bir saldırgan varken yapmak zorundalar. İşte handshake'in çözdüğü paradoks budur: **Açık bir kanal üzerinden, kimsenin öğrenemeyeceği bir ortak sır üretmek.** Bunu mümkün kılan matematiksel araç asimetrik kriptografidir, özellikle de **Diffie-Hellman** anahtar değişimidir.

Diffie-Hellman'ın çalışma mantığı şudur: Her iki taraf birer gizli değer (private) seçer ve bundan türetilmiş bir açık değeri (public) karşıya gönderir. Açık değerler ağ üzerinde görünür olsa da, bunlardan ortak sırrı hesaplamak matematiksel olarak zordur (ayrık logaritma / eliptik eğri problemi). Sonuçta iki taraf da aynı ortak sırra ulaşır ama dinleyen biri ulaşamaz. Bu yüzden modern TLS, RSA anahtar taşıma (key transport) yerine **ephemeral Diffie-Hellman** (ECDHE) kullanır: Her oturum için yeni bir geçici anahtar üretilir.

### Forward Secrecy Neden Bu Kadar Önemli?

Eski TLS'te sunucu, oturum anahtarını kendi RSA private key'iyle çözebilecek şekilde alırdı. Bunun büyük bir zaafı vardır: Saldırgan bugün trafiği kaydeder, yıllar sonra sunucunun private key'ini bir şekilde ele geçirirse **geçmiş tüm kayıtlı trafiği** çözebilir. Buna "store now, decrypt later" saldırısı denir. Ephemeral Diffie-Hellman bunu engeller çünkü geçici anahtar oturum bitince silinir ve hiçbir yerde saklanmaz. Sunucunun uzun ömürlü anahtarı ele geçse bile geçmiş oturumlar çözülemez. Bu özelliğe **forward secrecy** (PFS) denir ve TLS 1.3'te artık zorunludur.

### TLS 1.2 Handshake Akışı

TLS 1.2'de handshake kabaca şöyle ilerler:

1. **ClientHello**: İstemci desteklediği TLS sürümlerini, cipher suite listesini ve rastgele bir değeri (client random) gönderir.
2. **ServerHello**: Sunucu ortak bir cipher suite seçer, kendi random değerini gönderir.
3. **Certificate**: Sunucu sertifikasını (ve zincirini) sunar.
4. **ServerKeyExchange**: ECDHE parametreleri, sunucunun private key'iyle imzalanmış olarak gönderilir. Bu imza kritiktir; kimlik doğrulamayı anahtar değişimine bağlar.
5. **Finished** mesajları: Her iki taraf, o ana kadarki tüm handshake mesajlarının bir hash'ini (transcript hash) şifreli olarak gönderir ve doğrular.

Bu son adım, handshake bütünlüğünün temelidir. Saldırgan araya girip herhangi bir handshake mesajını değiştirdiyse, transcript hash'leri uyuşmaz ve bağlantı kopar. Bu mekanizmayı akılda tutun; downgrade saldırılarını anlamanın anahtarı burasıdır.

---

## TLS 1.3: Neyi Değiştirdi ve Neden?

TLS 1.3, önceki sürümlerin yıllar içinde biriken tasarım hatalarına ve kırılmış özelliklerine verilen köklü bir cevaptır. Felsefesi şudur: **Güvensiz olan her şeyi protokolden tamamen sil.** İsteğe bağlı bırakma, çünkü isteğe bağlı bırakılan zayıf seçenekler eninde sonunda saldırı yüzeyi olur.

### Ne Kaldırıldı ve Neden?

- **RSA key transport kaldırıldı.** Forward secrecy'yi imkânsız kıldığı ve Bleichenbacher tarzı oracle saldırılarına açık olduğu için. Artık yalnızca (EC)DHE var.
- **Zayıf şifreler tamamen atıldı.** RC4, 3DES, CBC modundaki bloklu şifreler, MD5/SHA-1 tabanlı imzalar kaldırıldı. TLS 1.3 yalnızca **AEAD** (Authenticated Encryption with Associated Data) şifrelerine izin verir: AES-GCM, ChaCha20-Poly1305 gibi. AEAD, şifreleme ve bütünlüğü tek atomik işlemde birleştirir; bu da CBC'deki "önce şifrele mi, önce doğrula mı" karmaşasından doğan padding oracle saldırılarını kökten yok eder.
- **Sıkıştırma (compression) kaldırıldı.** TLS seviyesinde sıkıştırma, CRIME sınıfı saldırıların temel sebebiydi (aşağıda açıklanıyor).
- **Renegotiation kaldırıldı**, yerine daha kontrollü mekanizmalar kondu.

### Handshake Neden Daha Hızlı?

TLS 1.3 handshake'i **1-RTT**'ye (tek gidiş-dönüş) indirir. Bunu şöyle başarır: İstemci, ClientHello ile birlikte tahmin ettiği anahtar değişim gruplarının kendi public key'ini (key_share) **hemen** gönderir. Sunucu, ServerHello'da kendi key_share'ini döndüğü anda iki taraf da ortak sırrı hesaplayabilir. Böylece TLS 1.2'deki fazladan gidiş-dönüş ortadan kalkar. Ayrıca cipher suite kavramı sadeleştirildi; artık kimlik doğrulama ve anahtar değişimi handshake'in ayrı parçalarında müzakere edilir, cipher suite sadece simetrik şifre + hash'i belirtir.

### 0-RTT ve Onun İnce Riski

TLS 1.3, daha önce bağlanılmış bir sunucuya **0-RTT** ile veri göndermeye izin verir: İstemci, ilk pakette bile uygulama verisini, önceki oturumdan türetilen bir anahtarla şifreleyip yollayabilir. Bu, gecikmeyi sıfırlar ama bir güvenlik ödünü vardır ve bunu bilerek yönetmek gerekir. 0-RTT verisi **replay saldırısına** açıktır: Saldırgan, yakaladığı ilk paketi sunucuya tekrar tekrar gönderebilir. Çünkü bu veri, tam handshake'in sağladığı tazelik (freshness) garantisinden yoksundur. Bu yüzden temel kural şudur: **0-RTT yalnızca idempotent (tekrarı zararsız) isteklerde kullanılmalıdır.** Bir GET isteği genelde güvenlidir; "hesaptan para çek" gibi durum değiştiren bir işlem asla 0-RTT ile taşınmamalıdır. Uygulama katmanının bu farkı bilmesi gerekir.

---

## Downgrade Saldırıları: Zayıfa Zorlamak

### Kök Neden: Geriye Dönük Uyumluluk

Downgrade saldırılarının varlık sebebi tek kelimeyle **uyumluluktur**. İnternette hâlâ eski istemci ve sunucular olduğu için protokoller uzun süre eski sürümleri de desteklemek zorunda kaldı. Saldırganın stratejisi de burada yatar: Tarafları, aralarında müzakere edebilecekleri **en zayıf** ortak paydaya zorlamak. Zayıf sürüm veya zayıf cipher, çözülmesi daha kolay demektir.

### Nasıl Çalışır?

Klasik downgrade senaryosu şöyledir: İstemci ClientHello'da "TLS 1.2 destekliyorum" der. Ortadaki saldırgan bu mesajı yakalar ve "TLS 1.0 destekliyorum" olarak değiştirir ya da handshake'i düşürerek istemcinin daha düşük sürümü tekrar denemesine yol açar. Tarafların eski, kırık bir protokolde anlaşmasını sağlar. TLS 1.2'nin transcript doğrulaması bunu bir ölçüde yakalar ama tarihte **POODLE** gibi saldırılar, istemcilerin bağlantı başarısız olunca otomatik olarak daha eski sürüme "düşme" (downgrade dance) davranışını sömürerek SSL 3.0'a zorlamayı başardı. Bir kez SSL 3.0'a inildiğinde, o sürümün CBC padding'indeki zaaf sömürülebiliyordu.

Cipher suite düşürme de benzerdir: **FREAK** ve **Logjam** sınıfı saldırılar, tarafları eski ihracat-sınıfı (export-grade) zayıf anahtarlara zorlayarak çalıştı. Bu zayıf anahtarlar, o dönemin ihracat kısıtlamaları yüzünden bilinçli olarak kırılabilir tutulmuştu ve protokolde artık kaldıkları için saldırı yüzeyi oldular.

### Savunma: Downgrade'i Nasıl Engelleriz?

TLS 1.3, downgrade'e karşı akıllıca bir sinyal koydu. Sunucu, eğer istemci daha yeni bir sürüm istemesine rağmen kendisi daha eskiye "düşüyorsa", ServerHello'daki **server random**'ın son baytlarına özel bir sabit değer (downgrade sentinel) yerleştirir. Gerçek bir TLS 1.3 istemcisi bu sabiti görürse, "bir saldırgan beni düşürmeye çalışıyor" diye anlar ve bağlantıyı keser. Bu değer transcript'in imzalı kısmına dahil olduğu için saldırgan onu fark ettirmeden silemez.

Pratik savunma katmanları şunlardır:
- **Eski protokolleri tamamen kapatın.** SSL 3.0, TLS 1.0, TLS 1.1 sunucunuzda devre dışı olmalı. Var olmayan bir protokole düşürülemezsiniz.
- **Zayıf cipher suite'leri kaldırın.** Export-grade, RC4, 3DES gibi şeyler yapılandırmadan çıkmalı.
- **TLS_FALLBACK_SCSV** mekanizması, istemci bir fallback denemesi yaptığında bunu sunucuya bildiren özel bir sinyal cipher değeridir; sunucu bunu görüp gerçekten daha düşük bir sürüme mi düştüğünü kontrol edebilir ve şüpheli fallback'i reddeder.
- **HSTS** (HTTP Strict Transport Security): Tarayıcının siteye sadece HTTPS ile bağlanmasını zorlayarak, "önce HTTP'ye düşür sonra araya gir" tarzı **SSL stripping** saldırılarını engeller.

---

## Sertifika Doğrulama Hataları: En Sık Kırılan Halka

### Sertifikalar Neden Var?

Diffie-Hellman size gizlilik verir ama tek başına bir şey vermez: **Kiminle** anahtar değiştirdiğinizi bilemezsiniz. Ortadaki saldırgan da sizinle mükemmel bir DH değişimi yapabilir. İşte sertifikalar bu boşluğu doldurur. Bir sertifika, güvenilen bir üçüncü taraf olan **CA**'nın (Certificate Authority) imzasıyla, "bu public key gerçekten example.com'a aittir" diyen bir belgedir. Güven, bir zincir halinde ilerler: Sunucu sertifikası bir ara CA tarafından, o da bir kök CA (root) tarafından imzalanır. İstemci, işletim sistemine/tarayıcıya gömülü **kök güven deposundaki** (trust store) köklere kadar bu zinciri doğrular.

### Doğru Doğrulama Neyi İçerir?

Bir sertifikayı doğru doğrulamak dört bağımsız kontrolü gerektirir ve bunların **hepsi** yapılmalıdır. Pratikteki hataların çoğu, bunlardan birinin atlanmasından doğar:

1. **Zincir/imza doğrulaması**: Sertifika, güvenilen bir köke kadar giden geçerli imzalarla mı bağlanıyor?
2. **Geçerlilik süresi**: `notBefore` ve `notAfter` tarihleri arasında mıyız? Süresi dolmuş sertifika reddedilmeli.
3. **Hostname eşleşmesi**: Sertifikanın **SAN** (Subject Alternative Name) alanı, bağlandığınız alan adıyla eşleşiyor mu? Bu, en sık atlanan kontroldür.
4. **İptal kontrolü**: Sertifika CRL veya OCSP ile iptal edilmiş mi?

### Kök Neden: Neden Bu Kadar Sık Yanlış Yapılır?

Sertifika doğrulaması pratikte felaket derecede sık hatalı uygulanır. Sebebi psikolojiktir: **Yanlış doğrulama, testte "çalışıyor" gibi görünür.** Bir geliştirici hostname kontrolünü atlarsa, uygulama mükemmel çalışır, sayfalar yüklenir, hiçbir hata çıkmaz. Zafiyet ancak bir saldırgan araya girdiğinde ortaya çıkar; o da normal testlerde asla olmaz. Yani "yeşil kilit" görüntüsü, güvenliğin kanıtı değildir. En tehlikeli anti-pattern'ler şunlardır:

- **Zincir doğrulamasını tamamen kapatmak.** Geliştiriciler, kendi imzaladıkları (self-signed) sertifikalarla test ederken "sertifika hatası" aldıklarında, çözüm olarak doğrulamayı komple kapatırlar (`verify=False`, `InsecureSkipVerify: true`, `TrustAllCerts` gibi). Sonra bu kod production'a sızar. Bu, TLS'i **tamamen anlamsız** hale getirir çünkü saldırgan artık istediği sertifikayı sunabilir.
- **Zincir doğrulanır ama hostname doğrulanmaz.** Bu daha sinsi bir hatadır. Kütüphane sertifikanın geçerli bir CA'dan geldiğini kontrol eder ama sertifikanın **hangi** siteye ait olduğunu kontrol etmez. Saldırgan, tamamen geçerli ama `attacker.com` için düzenlenmiş bir sertifika sunar; kod bunu kabul eder çünkü zincir geçerlidir. Oysa `bank.com`'a bağlandığınızı sanıyordunuz. Tarihte pek çok mobil uygulama ve kütüphane tam bu hatayı yaptı.
- **Sertifika hatalarını kullanıcıya "devam et" seçeneğiyle geçiştirmek.** Kullanıcılar uyarıları rutin olarak tıklayıp geçer (click-through), dolayısıyla bu bir savunma sayılmaz.
- **CN'e (Common Name) güvenmek.** Modern doğrulama hostname'i SAN'dan okur; sadece CN'e bakan eski kod, SAN uyumsuzluğunu kaçırır.

### Sömürü Mantığı

Saldırgan açısından süreç şudur: MITM konumundasınız, kurban `https://bank.com`'a bağlanmak istiyor. Kurbanın istemcisi doğrulamayı düzgün yapıyorsa, sizin sunacağınız her sertifika ya geçerli bir CA'dan gelmez (zincir kırılır) ya da `bank.com` için değildir (hostname uyuşmaz). İkisi de reddedilir; işte TLS'in koruması budur. Ama istemci doğrulamanın herhangi bir adımını atlıyorsa, o adımı sömürürsünüz: Hostname kontrolü yoksa geçerli ama başka domain için bir sertifika sunarsınız; zincir kontrolü yoksa doğrudan kendi self-signed sertifikanızı sunarsınız. Her iki durumda da kurbanla aranızda kusursuz bir TLS tüneli kurulur ve kurban hiçbir uyarı görmez. Bu yüzden saldırı tespiti çok zordur.

### Savunma: Doğrulamayı Sağlamlaştırmak

- **Doğrulamayı asla kapatmayın.** Self-signed sertifikayla test etmeniz gerekiyorsa, o sertifikayı test ortamının trust store'una **açıkça ekleyin**; global doğrulamayı kapatmayın. Bu, doğru yapılmış ve yanlış yapılmışın ayrım çizgisidir.
- **Certificate pinning** (sertifika sabitleme): Yüksek riskli uygulamalarda (mobil bankacılık gibi) istemci, yalnızca belirli bir sertifikayı veya public key'i kabul eder. Böylece saldırgan geçerli bir CA'dan sertifika almış olsa bile reddedilir. Pinning güçlüdür ama dikkatli yönetilmelidir; sertifika yenilenince pin de güncellenmezse uygulama erişilemez hale gelir. Bu yüzden genelde public key pinning ve yedek pin'ler tercih edilir.
- **Kısa ömürlü sertifikalar ve otomasyon**: Modern yaklaşım (ACME / otomatik yenileme), sertifikaları kısa ömürlü tutup iptal problemini büyük ölçüde azaltır. Süresi zaten hızlıca dolacak bir sertifikanın iptal edilmesine daha az ihtiyaç duyulur.
- **CT (Certificate Transparency)**: Yanlış veya hileli düzenlenmiş sertifikaları herkese açık günlüklerde tespit edebilmek için CA'lar sertifikaları CT log'larına kaydeder. Bir CA hileyle sizin domaininiz için sertifika düzenlerse, bunu CT log'larını izleyerek fark edebilirsiniz.
- **İptal kontrolünü ciddiye alın**: OCSP stapling, iptal durumunu handshake sırasında sunucunun taze bir OCSP yanıtı ekleyerek iletmesini sağlar; bu hem gizliliği korur hem de gecikmeyi azaltır.

---

## Şifreleme Katmanına Yönelik Saldırılar: Yan Kanallar

TLS'in matematiği sağlam olsa bile **uygulaması** yan kanal (side-channel) zaafları barındırabilir. Bunlar TLS'in en öğretici kısmıdır çünkü "teorik olarak güvenli" ile "pratikte güvenli" arasındaki farkı gösterir.

### Padding Oracle ve CBC Zaafları

TLS 1.2 ve öncesinde CBC modundaki şifreler, mesajı blok boyutuna tamamlamak için **padding** kullanırdı. Sorun şu: Eğer sunucu, geçersiz padding ile geçersiz MAC durumlarında **farklı** davranır (farklı hata mesajı ya da farklı zamanlama) ise, saldırgan bu farkı bir "oracle" olarak kullanıp şifreli metni bayt bayt çözebilir. **Lucky Thirteen** sınıfı saldırılar tam olarak bu zamanlama farkını sömürdü. **POODLE** ise SSL 3.0'ın padding'inin içeriğinin doğrulanmamasını sömürdü. Bunların kök nedeni, CBC'nin "MAC-then-encrypt" yapısıydı: Bütünlük, şifre çözüldükten sonra kontrol edildiği için, çözme aşamasındaki davranış sızıntı yapıyordu. **Çözüm**, AEAD'ye geçmektir; AEAD'de bütünlük ve şifreleme atomik olarak birleşiktir ve TLS 1.3 zaten yalnızca AEAD'ye izin verdiği için bu sınıf saldırıyı tasarımdan siler.

### Sıkıştırma Tabanlı Saldırılar: CRIME ve BREACH

Sıkıştırma, tekrar eden verileri küçültür. Ama eğer şifrelenen veri, saldırganın kontrol ettiği bir kısım ile gizli bir sırrı (örneğin bir oturum çerezi) **birlikte** içeriyorsa, saldırgan sıkıştırılmış çıktının **boyutuna** bakarak tahminlerini ayarlayabilir. Saldırganın tahmini gizli değere yaklaştıkça sıkıştırma daha iyi çalışır ve çıktı küçülür. Bu boyut sızıntısıyla sır bayt bayt çözülebilir. **CRIME**, TLS seviyesindeki sıkıştırmayı sömürdü; savunması TLS sıkıştırmasını kapatmaktır ve TLS 1.3 zaten kaldırmıştır. **BREACH** ise HTTP yanıt gövdesindeki sıkıştırmayı sömürür; bu TLS katmanında değil uygulama katmanında olduğu için TLS'i kapatmakla çözülmez. BREACH savunması uygulama tarafındadır: Gizli değerleri (CSRF token gibi) yanıt başına rastgeleleştirmek, sıkıştırmayı hassas yanıtlarda kapatmak, istek oranını sınırlamak.

---

## Yaygın Hatalar (Özet)

- **Doğrulamayı test kolaylığı için kapatıp production'a taşımak.** En yıkıcı ve en yaygın hata.
- **Hostname/SAN kontrolünü atlamak.** Zincir doğru diye rahatlamak; oysa kimin sertifikası olduğu kontrol edilmemiş olur.
- **Eski protokol ve cipher'ları "uyumluluk için" açık bırakmak.** Kullanılmayan bir şey bile açık kaldıkça downgrade hedefidir.
- **0-RTT'yi durum değiştiren isteklerde kullanmak.** Replay riski göz ardı edilir.
- **Sertifika süresini ve iptalini izlememek.** Süresi dolan sertifika kesinti yaratır; iptal edilen ama hâlâ kabul edilen sertifika güvenlik açığıdır.
- **Kendi kriptografini yazmak veya kütüphaneyi yanlış konfigüre etmek.** TLS'i elle kurmaya çalışmak neredeyse her zaman yan kanal ya da doğrulama zaafı doğurur.
- **Private key'i yetersiz korumak.** Forward secrecy olsa bile, ele geçen anahtar gelecekteki kimlik taklidini mümkün kılar.

---

## En İyi Pratikler

**Sürüm ve şifre seçimi.** Mümkün olan her yerde TLS 1.3'ü tercih edin, en azından TLS 1.2'yi zorunlu tutun ve altındaki her şeyi kapatın. Yalnızca AEAD cipher suite'lerine ve forward secrecy sağlayan ECDHE anahtar değişimine izin verin. Konfigürasyonunuzu, güncel ve saygın referans yapılandırmalara (örneğin yaygın kabul gören "modern" profillere) göre ayarlayın ve düzenli olarak gözden geçirin; kripto önerileri zamanla değişir.

**Doğrulamayı asla gevşetmeyin.** Sertifika doğrulaması ya tam yapılır ya da TLS güvenliğinden söz edemezsiniz. Test ortamında güven eklemek gerekiyorsa açıkça ve dar kapsamlı ekleyin; global "hepsine güven" bayraklarını kod tabanınızdan yasaklayın ve CI'da bunları arayan otomatik kontroller koyun.

**Derinlemesine savunma.** Tek bir mekanizmaya güvenmeyin. HSTS ile HTTPS'i zorunlu kılın, kritik uygulamalarda pinning düşünün, CT log izlemesiyle hileli sertifikaları yakalayın, OCSP stapling ile iptali güncel tutun. Bu katmanlar birbirinin açığını kapatır.

**Anahtar ve sertifika hijyeni.** Private key'leri sıkı koruyun, mümkünse HSM veya güvenli enclave'de tutun. Sertifika yenilemeyi otomatikleştirin (ACME) ki insan hatası ve süre dolması kesintisi ortadan kalksın. Kısa ömürlü sertifikalar iptal problemini de hafifletir.

**Uygulama katmanını unutmayın.** TLS taşımayı korur ama BREACH gibi saldırılar uygulama davranışını sömürür. Hassas yanıtlarda sıkıştırma ve token yönetimine dikkat edin; 0-RTT'yi yalnızca güvenli, idempotent işlemlerde kullanın.

**Sürekli test ve gözlem.** TLS konfigürasyonunuzu düzenli olarak tarama araçlarıyla denetleyin, zayıf sürüm/cipher kalıntılarını yakalayın, sertifika son kullanma tarihlerini izleyin. Güvenlik statik değildir; bugün güçlü olan bir konfigürasyon, yarın çıkan bir saldırıyla zayıflayabilir.

---

## Sonuç

TLS'in gücü, üç ayrı güvenlik hedefini (gizlilik, bütünlük, kimlik doğrulama) tek bir protokolde birleştirmesinden gelir; zafiyetleri de genellikle bu hedeflerden birinin ihmal edilmesinden doğar. Handshake, açık bir kanalda gizli anahtar üretmenin zarif çözümüdür; TLS 1.3 ise yılların birikmiş hatalarını temizleyerek "güvensiz seçeneği hiç sunma" felsefesini benimser. Downgrade saldırıları uyumluluğun bedelidir ve eski protokolleri kapatmakla büyük ölçüde nötralize edilir. Ama tüm bu makinenin en kırılgan halkası, neredeyse her zaman **sertifika doğrulamasıdır**; çünkü yanlış yapıldığında hiçbir belirti vermez, sadece bir saldırgan geldiğinde çöker. Bu yüzden TLS güvenliğini gerçekten sağlamanın özü şudur: Doğrulamayı asla gevşetme, eskiyi kapat, katmanla savun ve sürekli gözlemle.
