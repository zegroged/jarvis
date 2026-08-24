# Entra ID Conditional Access Atlatma ve Keşif: Device Registration/Join Kötüye Kullanımı, Legacy Auth, Named Location Spoofing

## Giriş: Neden Bu Konu Kritik

Microsoft Entra ID (eski adıyla Azure AD), günümüzde çoğu kurumsal ortamın kimlik omurgasıdır. Conditional Access (CA — Koşullu Erişim), bu omurganın üzerine oturan karar motorudur: "kim, hangi cihazdan, nereden, hangi risk seviyesiyle" giriş yapıyor sorusuna göre erişimi izin ver, MFA iste, engelle ya da sınırlı oturum ver şeklinde karar üretir. Sorun şu ki CA bir *duvar* değil, bir *if-then kural motorudur*. Kural motorları, tanım gereği, tanımlanmamış ya da yanlış tanımlanmış durumlar karşısında şeffaf biçimde "izin ver" tarafına düşebilir. Saldırganlar CA'yı doğrudan kırmaz; CA'nın karar verirken güvendiği sinyalleri (cihaz kimliği, kimlik doğrulama protokolü, ağ konumu) taklit ederek motoru kendi lehlerine "doğru" karar vermeye ikna ederler.

Bu makale üç ayrı ama birbirini besleyen atlatma yüzeyini ele alır: (1) cihaz kaydı/katılımı (device registration/join) istismarı yoluyla "uyumlu/yönetilen cihaz" sinyalinin taklit edilmesi, (2) legacy authentication protokolleri üzerinden modern MFA/CA kontrollerinin devre dışı bırakılması, (3) named location (adlandırılmış konum) tanımlarının zayıflıklarından yararlanarak "güvenilir ağ" sinyalinin sahtelenmesi. Bu konunun bir eğitim korpusunda yer almaması ciddi bir boşluktur çünkü bu üç teknik, gerçek saldırı zincirlerinde (özellikle post-phishing / token çalma senaryolarında) CA'yı by-pass etmenin en yaygın üç yoludur ve savunma tarafında da en çok yanlış yapılandırılan alanlardır.

---

## 1. Conditional Access'in Karar Mantığını Anlamak (Kök Model)

CA politikaları özünde şu formülü çalıştırır:

```
Sinyaller (kim, ne, nereden, ne ile) --> Koşullar (assignments) --> Kontroller (grant/session controls)
```

Kritik nokta: CA, kimlik doğrulamanın *sonrasında* devreye giren bir katmandır. Kullanıcı adı/parola veya token zaten doğrulanmış olmalı ki CA motoru "şimdi ek kontrol gerekiyor mu" diye karar versin. Bu sıralama, saldırganlara şu genel stratejiyi verir: **kimlik doğrulamayı öyle bir yoldan geçir ki CA motoru hiç devreye girmesin ya da devreye girdiğinde zaten "güvenilir" bir sinyal görsün.**

CA'nın güvendiği başlıca sinyaller:
- **Kullanıcı/grup üyeliği** — kime uygulanacağı.
- **Cihaz durumu** — Entra'ya kayıtlı mı (registered), katılmış mı (joined/hybrid joined), uyumlu mu (Intune compliant), Trusted mı.
- **Uygulama/protokol** — hangi istemci, hangi auth protokolü (modern OAuth2/OIDC vs. legacy).
- **Ağ konumu** — IP adresinin bir "named location" içinde olup olmadığı.
- **Oturum riski / kullanıcı riski** — Identity Protection sinyalleri.

Bu sinyallerden herhangi biri sahte biçimde üretilebiliyorsa, CA motoru yanlış girdiyle doğru (ama saldırgan lehine) bir karar üretir. Bu, klasik "garbage in, garbage out" probleminin kimlik güvenliğindeki yansımasıdır.

---

## 2. Device Registration / Device Join Kötüye Kullanımı

### 2.1 Kavram ve Kök Neden

Entra ID'de bir cihaz üç farklı durumda olabilir:
- **Entra registered (Azure AD registered)**: Kullanıcı kendi kişisel cihazını (BYOD) bir Microsoft hesabıyla kaydeder. Kimlik doğrulaması sonrası düşük sürtünmeli bir işlemdir — çoğu kiracıda varsayılan olarak *herhangi bir kullanıcı, herhangi bir cihazı kendi adına register edebilir*, çünkü "Cihazlar" ayarlarındaki "Users may register their devices with Microsoft Entra ID" seçeneği çoğu zaman "All" olarak bırakılır.
- **Entra joined**: Cihaz doğrudan Entra ID'ye kurumsal cihaz olarak katılır (genelde Autopilot/OOBE üzerinden ya da kurumsal imaj ile).
- **Hybrid Entra joined**: On-prem AD'ye katılı cihaz, Entra Connect senkronizasyonu ile Entra'da da bir cihaz nesnesi kazanır.

**Kök neden**, CA politikalarının çoğu zaman "Require device to be marked as compliant" yerine daha zayıf bir kontrol olan **"Require Hybrid Azure AD joined device"** ya da hatta hiçbir cihaz kontrolü koymadan sadece MFA istemesidir. Daha da kritik olan zaaf şudur: register edilmiş bir cihaz, compliant olmasa bile, bazı politikalarda "bilinen cihaz" olarak değerlendirilip risk skorunu düşürebilir ya da "cihaza güven" temelli session control'lerin (örneğin persistent browser session, token'ların cihaza bağlanması) tetiklenmesine neden olabilir.

### 2.2 Saldırı Mantığı (Kavramsal)

Saldırganın elinde geçerli bir kullanıcı adı/parola (veya çalınmış bir refresh token) olduğunu varsayalım, ancak hedef kiracıda "Require compliant device" politikası var. Saldırgan doğrudan bu politikayı kıramaz çünkü kendi cihazı Intune'a kayıtlı/compliant değildir. Ancak şu zincir mümkün olabilir:

1. Çalınan kimlik bilgileriyle **kendi kontrolündeki bir cihazı** o kullanıcı adına Entra'ya **register** eder (çoğu kiracıda bu, ekstra bir onay gerektirmeyen self-servis bir akıştır ve MFA politikası "device registration" akışını kapsamıyorsa tek faktörle bile tamamlanabilir).
2. Register edilen cihaz artık kullanıcının "Devices" listesinde görünür ve bir cihaz nesnesi (device object) ile bir **Primary Refresh Token (PRT)** alma potansiyeli kazanır.
3. Eğer hedef politika sadece "registered" seviyesini değil "joined/compliant" seviyesini istiyorsa, saldırgan bu adımı tek başına aşamaz — ama pratikte gözlemlenen hata, kurumların bazı düşük riskli uygulamalar (örn. iç portal, bazı SaaS entegrasyonları) için sadece "registered device" ya da "MFA OR compliant device" gibi **OR mantığı** kuran politikalar yazmasıdır. OR mantığı, saldırganın en zayıf şartı sağlaması yeterli olduğu için CA'yı fiilen "en zayıf halkaya" indirger.
4. Ayrıca, cihaz kaydı sırasında elde edilen **device key**'in çalınması (örneğin ele geçirilmiş bir cihazdan) veya bir **PRT + session key** çalınması (adversary-in-the-middle / token çalma araçlarıyla), saldırganın kendi makinesinde o cihazı taklit ederek ("PRT cloning" olarak bilinen kavram) sonraki oturumlarda "bilinen/güvenilir cihaz" sinyali üretmesine yol açabilir. Burada net olmak gerekir: PRT'nin cihaza bağlanması (TPM tabanlı anahtarlarla) bu klonlamayı zorlaştırmak için tasarlanmıştır; ancak TPM olmayan/yanlış yapılandırılmış cihazlarda veya session key sızıntısı senaryolarında bu koruma zayıflar. Kesin başarı oranı ve spesifik araç davranışları ortama göre değişir; burada iddia edilen şey somut bir "şu araç şunu yapar" değil, mekanizmanın neden kırılgan olabileceğidir.

### 2.3 Neden Bu Çalışıyor (Kök Neden Özeti)

- Self-servis cihaz kaydı **varsayılan olarak geniş** izinlidir; çoğu kurum bunu kısıtlamaz çünkü BYOD kolaylığı önceliklidir.
- CA politikaları çoğunlukla "compliant OR MFA" gibi **zayıflatılmış OR kombinasyonları** kullanır; oysa hassas kaynaklar için "compliant AND MFA" (AND mantığı) gerekir.
- Cihaz durumu bir kere kazanıldıktan sonra **uzun ömürlü** bir güven sinyaline dönüşür (cihaz nesnesi silinene/re-set edilene kadar), bu da tek seferlik bir kayıt işleminin kalıcı bir arka kapıya dönüşmesine izin verir.

### 2.4 Tespit

- **Cihaz kayıt olaylarının anomali analizi**: Entra ID sign-in logs ve audit logs içinde "Register device" / "Join device" olaylarını, özellikle normalin dışı IP/coğrafya/user-agent kombinasyonlarıyla birlikte izleyin.
- **Aynı kullanıcı adına kısa sürede çoklu cihaz kaydı**: Bir kullanıcının birkaç saat içinde birden fazla yeni cihaz register etmesi güçlü bir IOC'dir.
- **Yeni register edilen cihazdan hemen ardından hassas kaynağa erişim**: Kayıt ile ilk hassas erişim arasındaki süre çok kısaysa (dakikalar), bu meşru bir kurumsal onboarding akışına benzemez.
- **Identity Protection risky sign-in / risky user sinyalleri** ile cihaz kaydı olaylarını korele edin (SIEM/Sentinel içinde bir korelasyon kuralı olarak).
- **Cihaz uyumluluk durumunun sign-in log'larındaki `deviceDetail` alanı** üzerinden izlenmesi: `isCompliant: false` olan cihazlardan hassas kaynağa erişim denemelerini raporlayın.

### 2.5 Savunma

- **"Users may register their devices" ayarını kısıtlayın**: Mümkünse sadece belirli gruplara (ör. BYOD onaylı kullanıcılar) izin verin, "All" yerine "Selected" kullanın.
- **CA politikalarında AND mantığı**: Hassas kaynaklar için "Require compliant device" **AND** "Require MFA" birlikte zorunlu kılınmalı; asla sadece OR ile birbirinin yerine geçebilir kontroller kurulmamalı.
- **Compliant device zorunluluğu, sadece registered değil**: Politika yazarken "Require Hybrid Azure AD joined or compliant" seçeneğinin, salt "registered" durumundaki cihazları kapsamadığından emin olun.
- **Device cleanup / stale device politikası**: Kullanılmayan cihaz nesnelerini düzenli olarak temizleyin (Entra'nın "stale devices" yönetimi), çünkü eski/unutulmuş kayıtlı cihazlar sessiz bir saldırı yüzeyidir.
- **Sign-in frequency ve token yaşam süresi kontrolleri**: Session control'lerde "Sign-in frequency" değerini düşürerek çalınmış bir PRT/token'ın ömrünü kısaltın.
- **Continuous Access Evaluation (CAE)** etkinleştirin: Kullanıcı devre dışı bırakıldığında veya risk tespit edildiğinde token'ların gerçek zamana yakın iptal edilmesini sağlar.

---

## 3. Legacy Authentication ile MFA/CA Atlatma

### 3.1 Kavram ve Kök Neden

"Legacy authentication", modern OAuth2/OIDC + interactive tarayıcı akışları yerine, kullanıcı adı ve parolayı doğrudan istemci üzerinden protokole gömen eski yöntemleri kapsar: **IMAP, POP3, SMTP AUTH, MAPI, EAS (Exchange ActiveSync eski sürümler), eski Office masaüstü istemcilerinin "Basic Authentication" modu**. Bu protokollerin ortak özelliği: **interactive MFA prompt'u gösterecek bir kullanıcı arayüzü mekanizmasına sahip olmamalarıdır.** Protokol tasarımı, kullanıcı adı+parola dışında bir "ikinci adım" için hazırlanmamıştır.

**Kök neden** şudur: CA ve MFA, modern authentication'ın interactive/redirect tabanlı doğası üzerine inşa edilmiştir (kullanıcıyı bir web sayfasına yönlendirip orada ek doğrulama istemek). Legacy protokoller bu redirect modelini desteklemediği için, kimlik sağlayıcısının önünde iki seçenek kalır: ya bu protokolü tamamen reddet, ya da onu **tek faktörlü** (sadece parola) olarak kabul et. Tarihsel olarak birçok kurum, eski cihazlar/uygulamalar (ör. eski yazıcı tarama-to-email, eski CRM entegrasyonları, eski mobil mail istemcileri) hâlâ bu protokolleri kullandığı için legacy auth'u tamamen kapatamamış, bu da saldırganlara "parolayı bilen ama MFA'sı olmayan" bir giriş kapısı bırakmıştır.

### 3.2 Saldırı Mantığı (Kavramsal)

1. Saldırgan, phishing / credential stuffing / bilgi hırsızı (infostealer) yoluyla bir kullanıcının parolasını ele geçirir.
2. Kullanıcının hesabında MFA zorunlu olsa bile, saldırgan MFA istemi göstermeyen bir protokolle (ör. IMAP ile bir posta istemcisi simülasyonu, ya da EAS ile eski bir mobil profil) kimlik doğrulamayı dener.
3. Eğer kiracıda bu protokol için CA/Security Defaults tarafından **"Block legacy authentication"** politikası yoksa, ve kullanıcının parolası doğruysa, kimlik doğrulama **MFA sorulmadan** başarılı olur — çünkü protokol MFA sorabilecek bir arayüze sahip değildir ve Azure AD/Entra bu durumda "modern auth koşulu sağlanamıyor, bu yüzden MFA adımını atla" davranışına düşebilir (bu, tarihsel olarak Basic Auth + legacy protokollerde gözlemlenen genel davranış biçimidir; kesin davranış protokole ve kiracı yapılandırmasına göre değişir).
4. Bu şekilde saldırgan, doğrudan posta kutusuna (IMAP/EAS) ya da SMTP üzerinden gönderim yapabilecek bir erişim kazanır — bu genelde **veri sızdırma (mailbox exfiltration)** veya **iç phishing / BEC (business email compromise)** için yeterlidir, hatta CA'nın "engellediği" web tabanlı OWA erişimine hiç ihtiyaç duymadan.
5. Ayrıca legacy auth genelde **named location** ve **cihaz durumu** koşullarını da taşımaz ya da farklı şekilde değerlendirir; bu da CA'nın "sadece belirli ülkelerden/cihazlardan izin ver" kurallarının bu protokol için etkisiz kalmasına yol açabilir.

### 3.3 Neden Bu Çalışıyor (Kök Neden Özeti)

- Legacy protokoller **tasarım gereği** ikinci faktör taşıyamaz; bu bir "hata" değil mimari bir kısıtlamadır.
- Kurumlar geriye dönük uyumluluk (backward compatibility) için bu protokolleri tamamen kapatmakta gecikir.
- Password spray / credential stuffing saldırılarında legacy auth uç noktaları, başarısız girişlerin MFA tarafından yakalanmadığı için **sessiz brute-force yüzeyi** sunar — saldırgan binlerce denemeyi MFA tetiklemeden yapabilir.

### 3.4 Tespit

- **Sign-in log'larında `clientAppUsed` alanı**: "Other clients", "IMAP4", "POP3", "SMTP", "Exchange ActiveSync" gibi değerler için ayrı bir izleme/alarm hattı kurun.
- **Legacy auth üzerinden başarısız/başarılı giriş oranları**: Aynı kullanıcı için modern auth'ta MFA reddi olurken legacy auth'ta başarı varsa bu güçlü bir anomalidir.
- **Password spray imzası**: Kısa sürede çok sayıda kullanıcı adına karşı legacy protokolle düşük hacimli deneme paterni (spray saldırılarının tipik imzası).
- **Entra ID Workbook: "Sign-ins using legacy authentication"** raporunu düzenli izleyin; bu rapor halen aktif legacy trafiği olan hesap/uygulamaları gösterir.

### 3.5 Savunma

- **Legacy authentication'ı tamamen engelleyin**: CA politikası ile "Block legacy authentication" (client apps koşulunda "Exchange ActiveSync clients" ve "Other clients" için Block) uygulayın. Bu, tek başına en yüksek etkili önlemlerden biridir.
- **Security Defaults veya CA ile kademeli geçiş**: Önce raporlama modunda (report-only) çalıştırıp hangi hesap/uygulamaların hâlâ legacy auth kullandığını tespit edin, sonra aşamalı olarak engelleyin.
- **Modern Authentication'a zorunlu geçiş**: Exchange Online'da Basic Auth'un kiracı genelinde devre dışı bırakılması (Microsoft'un kendisi de bunu varsayılan olarak kapatma yönünde adımlar atmıştır) ve istemcilerin OAuth2/Modern Auth destekleyen sürümlere yükseltilmesi.
- **İstisna yönetimi minimal ve izlenebilir olmalı**: Legacy protokole gerçekten ihtiyaç duyan servis hesapları varsa, bunları ayrı, sıkı IP kısıtlamalı, düşük yetkili hesaplara izole edin ve sürekli izleyin.

---

## 4. Named Location Spoofing (Adlandırılmış Konum Sahtekârlığı)

### 4.1 Kavram ve Kök Neden

Named location, CA'da "bu IP aralığı bizim ofisimiz/güvenilir VPN çıkışımız" diye tanımlanan bir yapıdır. CA politikaları sıkça şu mantığı kurar: "Eğer kullanıcı güvenilir named location dışından geliyorsa MFA iste" ya da tam tersi "Güvenilir konumdan geliyorsa MFA'dan muaf tut." **Kök neden**, bu kontrolün tamamen **IP adresine dayalı, kimlik doğrulama katmanından bağımsız bir sinyal** olmasıdır. IP adresi, ağ katmanında kolayca değişebilen, sahiplik kanıtı taşımayan bir değerdir — bir named location "güvenilir" olarak işaretlendiğinde, o IP aralığından gelen **herhangi bir trafik** (meşru çalışan da olsa saldırgan da olsa) aynı güveni miras alır.

Bunun ikinci ve daha incelikli bir kök nedeni de şudur: named location tanımları genelde **statik IP listeleri veya coğrafi konum (GeoIP) veritabanlarına** dayanır. GeoIP veritabanları %100 doğru değildir ve VPN/proxy/hosting IP'leri zamanla el değiştirir; bir zamanlar "bilinmeyen/riskli" olarak sınıflanan bir IP bloğu, GeoIP sağlayıcısının veritabanı güncellemesiyle "güvenli ülke" kategorisine kayabilir ya da tam tersi.

### 4.2 Saldırı Mantığı (Kavramsal)

1. **Ticari/rezidansiyel proxy hizmetleri veya VPN çıkış noktaları üzerinden yönlendirme**: Saldırgan, hedef kurumun "güvenilir" olarak işaretlediği ülke/bölgeden çıkış yapan bir proxy/VPN kullanarak, CA'nın "eğer güvenilen ülkeden geliyorsa MFA sorma" gibi zayıf bir kuralını tetikler. Bu, IP'nin kendisini "sahtelemek" değil, **coğrafi olarak o IP havuzuna dahil olmaktır** — teknik olarak IP spoofing (paket başlığında sahte kaynak adresi) TCP tabanlı web trafiğinde pratik değildir çünkü three-way handshake tamamlanamaz; gerçek saldırı vektörü, saldırganın **o coğrafyadan gerçekten çıkış yapan bir aracı sunucu kiralamasıdır.**
2. **Kurumsal named location tanımının eksik/geniş olması**: Bazı kurumlar named location'ı çok geniş CIDR blokları ile tanımlar (örneğin bir bulut sağlayıcısının koca bir IP aralığını "ofis VPN'i" sanarak dahil eder) ya da eski bir ofis/VPN çıkışını kapatmayı unutur. Saldırgan, hedef kurumun kullandığı bulut/hosting sağlayıcısında (ör. aynı sağlayıcıda bir VM kiralayarak) o IP aralığına denk gelen bir çıkış noktası elde edebilir.
3. **"Compliant Network" / GPS tabanlı konum sinyali ile eşleşmeme**: Bazı gelişmiş CA yapılandırmaları "Global Secure Access" gibi ağ sinyali doğrulamaları kullanır; bunlar klasik IP tabanlı named location'dan daha güçlüdür. Ancak IP tabanlı klasik named location hâlâ en yaygın kullanılan yöntemdir ve yukarıdaki zaaflara açıktır.
4. Named location sahtelemesi tek başına nadiren yeterlidir; genelde **legacy auth atlatması veya çalıntı kimlik bilgileriyle birleştirilerek** kullanılır — örneğin "MFA sadece güvenilmeyen konumdan gelindiğinde istenir" politikasında, saldırgan güvenilir sayılan bir çıkış noktası bulduğunda MFA'yı tamamen es geçebilir.

### 4.3 Neden Bu Çalışıyor (Kök Neden Özeti)

- IP adresi **kimlik kanıtı değildir**; sahiplik/coğrafya bilgisinin doğrulanabilirliği zayıftır.
- Named location tanımları **nadiren gözden geçirilir**, zamanla genişler veya güncelliğini yitirir (stale configuration).
- "Güvenilir konum = MFA muafiyeti" mantığı, tek bir zayıf sinyali **tüm ikinci faktör kontrolünün yerine** koyar — bu, savunma derinliği ilkesine aykırıdır.

### 4.4 Tespit

- **Impossible travel / atypical travel** sinyalleri (Identity Protection): Aynı kullanıcının kısa sürede coğrafi olarak imkânsız iki konumdan giriş yapması.
- **Named location içindeki giriş hacminde ani artış**: Belirli bir "güvenilir" IP aralığından beklenmedik kullanıcı/cihaz kombinasyonlarında giriş artışı.
- **ASN/hosting-provider analizi**: Named location'a dahil IP'lerin gerçekten kurumsal/ISP ASN'lerine mi yoksa bulut/hosting/VPN sağlayıcı ASN'lerine mi ait olduğunu periyodik olarak doğrulayın; bulut ASN'lerinden gelen "güvenilir" trafik şüpheli kabul edilmelidir.
- **MFA muafiyetinin kullanıldığı oturumların sonradan denetimi**: "Trusted location + no MFA" ile açılan oturumların sonrasında yapılan hassas işlemleri (rol değişikliği, mail yönlendirme kuralı ekleme, OAuth app onayı gibi) ayrıca izleyin.

### 4.5 Savunma

- **Named location listelerini düzenli denetleyin**: CIDR blokları minimum gerekli genişlikte tutulmalı, kullanılmayan/eski VPN çıkışları çıkarılmalı.
- **"Trusted location = MFA muafiyeti" mantığından kaçının**: Konum sinyalini MFA'nın *tek* belirleyicisi yapmak yerine, ek bir katman olarak (defense in depth) kullanın — örneğin "trusted location dışından MFA + compliant device" gibi katmanlı kurallar.
- **Global Secure Access / Network Access sinyalleri** gibi daha güçlü ağ doğrulama mekanizmalarına geçişi değerlendirin; bunlar salt kaynak IP'sinden daha zor taklit edilebilen sinyaller sunar.
- **Sürekli risk tabanlı politika**: Identity Protection risk sinyalleriyle named location'ı birlikte değerlendiren politikalar kurun; tek boyutlu güven asla yeterli değildir.
- **Named location değişikliklerini audit log'da izleyin**: Bu tanımlara yapılan her değişiklik (ekleme/genişletme) ayrıcalıklı bir işlem olarak ele alınmalı ve onay akışına tabi tutulmalıdır — saldırganın yönetici yetkisi ele geçirip named location'ı kendi lehine genişletmesi de olası bir senaryodur.

---

## 5. Üç Tekniğin Birlikte Değerlendirilmesi: Zincirleme Risk

Bu üç teknik izole değil, birbirini güçlendiren bir zincir oluşturabilir: Saldırgan phishing ile parolayı çalar (adım 0) → legacy auth ile MFA'sız ilk erişimi dener, başarısız olursa modern auth + named location spoofing ile MFA muafiyetini tetiklemeye çalışır → başarılı girişten sonra kendi cihazını hedef kullanıcı adına register ederek kalıcı, "bilinen cihaz" sinyali taşıyan bir arka kapı kurar. Her adım tek başına düşükten-orta şiddete bir bulgu gibi görünse de, zincirlenmiş haliyle tam bir CA atlatma senaryosu ortaya çıkar. Bu nedenle savunma tarafında **tek bir kontrolü güçlendirmek yeterli değildir**; üçünün de aynı anda ele alınması (legacy auth kapatma + device compliance zorunluluğu + named location hijyeni) gerekir.

---

## 6. Yaygın Yapılandırma Hataları (Anti-Pattern'ler)

- **"Report-only" modda bırakılıp unutulan politikalar**: Birçok kurum CA politikasını test için report-only yapar ve asla "On" durumuna geçirmez; bu durumda politika hiçbir koruma sağlamaz ama panolarda "var" görünür (yanlış güven duygusu).
- **Sadece belirli uygulamalara politika uygulamak**: "All cloud apps" yerine sadece Exchange/SharePoint gibi birkaç uygulamayı hedefleyen politikalar, kapsam dışı kalan üçüncü parti OAuth uygulamaları veya eski API'ler üzerinden atlatılabilir.
- **Break-glass (acil durum) hesaplarının CA'dan tamamen muaf tutulması ve unutulması**: Bu hesaplar genelde hem legacy auth hem de MFA'dan muaftır ve izlenmezse saldırganın en sevdiği kalıcı hedef haline gelir.
- **Cihaz uyumluluğunu tanımlarken sadece "registered" ile "compliant"i karıştırmak**: Politika yazarken yanlışlıkla daha zayıf koşulu seçmek (örneğin "Require Azure AD joined" yerine sadece cihaz nesnesi var olduğu için geçen bir kural yazmak).
- **Named location'ı sadece "block" için kullanıp "require MFA" ile birlikte katmanlamamak**: Tek boyutlu coğrafi engellemeler, kolayca proxy/VPN ile aşılır; katman eksikliği asıl zaafı oluşturur.

---

## 7. Sonuç: Savunmacı Zihniyeti

Conditional Access'i güvenli kılan şey politikanın var olması değil, **girdi olarak aldığı sinyallerin ne kadar sahteye dayanıklı olduğudur.** Bir savunma mühendisi için doğru soru "CA politikamız var mı" değil, "CA politikamızın güvendiği her sinyal (cihaz durumu, protokol, IP/konum) bağımsız olarak sahtelenebilir mi, ve sahtelenirse tespit edebiliyor muyuz" sorusudur. Bu üç teknik — cihaz kaydı istismarı, legacy auth, named location spoofing — aslında aynı ilkenin üç farklı yüzüdür: **güven, kanıtlanabilir olmadığı sürece bir zaaftır.** Savunma stratejisi bu yüzden tekil kontrol eklemek değil, her sinyali çapraz doğrulayan, katmanlı (defense-in-depth) ve sürekli izlenen bir CA mimarisi kurmaktır.
