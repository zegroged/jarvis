# Entra ID Token/Kimlik Bilgisi Hırsızlığı ve Kötüye Kullanımı

## Giriş: Neden Bu Konu Kritik

Kurumsal ortamların bulut kimliğine göçü, saldırganların hedefini de değiştirdi. Klasik Active Directory saldırılarında (Kerberoasting, DCSync, Golden Ticket) amaç bir "bilet" (ticket) veya karma (hash) elde etmekti; bulutta ise karşılığı **token**'dır. Microsoft Entra ID (eski adıyla Azure AD), kurumsal kimlik doğrulamanın merkezi haline geldikçe, kimlik doğrulama akışlarını kırmak veya atlatmak artık saldırganlar için parola kırmaktan çok daha verimli bir yol oldu. Bunun nedeni basit: **modern kimlik doğrulama, MFA (multi-factor authentication) dahil, sonunda bir token üretir; o token'ı çalarsanız, MFA'nın kendisini kırmanıza gerek kalmaz.**

Bu makale dört ilişkili ama farklı saldırı yüzeyini ele alıyor: Primary Refresh Token (PRT) çıkarma, Device Code Phishing, İzin (consent) kimlik avı yoluyla kalıcı erişim, ve token/claim manipülasyonu (nOAuth dahil). Bunların hepsinin ortak noktası, kimlik doğrulamanın "sonucunu" (token) hedef almaları ve genellikle MFA'yı by-pass etmeleridir — bu yüzden günümüz saldırı zincirlerinde AD'den buluta geçişin (hybrid pivot) en yaygın başlangıç noktalarındandır.

---

## Kavramsal Temel: Token Tabanlı Kimlik Doğrulamanın Anatomisi

Entra ID, OAuth 2.0 ve OpenID Connect (OIDC) standartlarını kullanır. Bir kullanıcı oturum açtığında ortaya üç tür token çıkabilir:

- **ID token**: Kullanıcının kim olduğunu ispatlayan OIDC token'ı (JWT formatında).
- **Access token**: Belirli bir kaynağa (Microsoft Graph, SharePoint, özel bir API) erişim için kullanılan, kaynağa özgü, kısa ömürlü (tipik olarak ~1 saat) token.
- **Refresh token**: Access token süresi dolduğunda kullanıcıyı yeniden parola/MFA girmeye zorlamadan yeni access token almak için kullanılan, daha uzun ömürlü token.

Windows 10/11'de Entra ID'ye katılmış (Azure AD joined) veya hibrit katılmış cihazlarda bu mantık bir adım öteye taşınır: **Primary Refresh Token (PRT)**. PRT, cihazın kendisine bağlı (cihaz sertifikasıyla kriptografik olarak imzalı), kullanıcının o cihazdaki tüm SSO (single sign-on) deneyimini besleyen özel bir refresh token türüdür. PRT bir kez elde edildiğinde, o kullanıcı adına neredeyse tüm bulut kaynaklarına — yeniden MFA istemeden — token türetilebilir.

Bunu anlamak neden önemli? Çünkü klasik "parola hırsızlığı" savunmaları (MFA zorunluluğu, Conditional Access) token hırsızlığına karşı **kör noktalar** bırakır: token zaten "MFA yapılmış" durumunu temsil eder. Saldırgan parolayı hiç bilmeden, MFA'yı hiç görmeden, doğrudan sonucu çalar.

---

## 1) Primary Refresh Token (PRT) Çıkarma

### Tanım ve Kök Neden

PRT, cihazda `lsass.exe` benzeri bir korumalı süreç olan **CloudAP (Cloud Authentication Provider)** ve **dsreg** bileşenleri tarafından yönetilir, TPM (Trusted Platform Module) varsa ona bağlanabilir ve DPAPI (Data Protection API) ile şifrelenmiş olarak diskte/bellekte tutulur. PRT'nin kendisi AES ile şifrelenmiştir ve bir **oturum anahtarı (session key)** ile korunur; bu oturum anahtarı da genellikle cihazın TPM'i veya kullanıcı bağlamına bağlı DPAPI master key'i ile korunur.

Kök neden şudur: Windows, kullanıcı deneyimini kesintisiz tutmak (SSO) için PRT'yi ve onu deşifre edecek anahtar malzemesini **çalışan bir oturumda erişilebilir** tutmak zorundadır. Bu, "kullanılabilirlik ile güvenlik" arasındaki klasik gerilimin somut örneğidir: PRT bir yerde, bir şekilde, işletim sistemi tarafından kullanılabilir halde bulunmalıdır — ve yönetici (veya SYSTEM) ayrıcalığına sahip bir saldırgan da nihayetinde aynı erişime sahiptir.

### Nasıl Çalışır (Kavramsal)

Saldırgan açısından tipik zincir:

1. **Yerel yönetici / SYSTEM ayrıcalığı elde etme** (bu genellikle önkoşuldur — PRT çıkarma "sıfırdan uzaktan" bir saldırı değil, çoğunlukla **post-exploitation**'dır).
2. CloudAP eklentisinin bellek içi durumundan veya DPAPI korumalı depodan PRT'yi ve ilişkili oturum anahtarını çıkarma.
3. TPM korumalı ise, doğrudan anahtar dışa aktarımı engellenir; ancak saldırgan TPM'i "bypass" etmek yerine genelde **TPM'in kendisini bir imzalama/şifre çözme oracle'ı olarak kullanır** — yani anahtarı dışarı çıkarmadan, TPM'e imzalatarak yeni token türetir (bu, "PRT cookie" veya türetilmiş token üretimi olarak anılır).
4. Elde edilen PRT + oturum anahtarı ile, cihazdan bağımsız bir makineden (attacker-controlled) Entra ID token uç noktalarına istek gönderilip **taze access/refresh token** talep edilir — bu genellikle MFA istemez çünkü PRT zaten "device + user" doğrulamasını temsil eder.

Bu alanda halka açık bilgi ve araçlar (ör. **ROADtools** ve **AADInternals** projeleri; isimlerini genel bilgi düzeyinde anıyorum, kesin komut/parametre iddiasında bulunmuyorum) PRT çıkarma, PRT'den token türetme ve Entra ID nesnelerini PRT ile numaralandırma gibi işlevleri araştırmacılara/mavi takıma göstermek amacıyla var. Bu makalede bu araçların işlevini **kavramsal düzeyde** anıyorum; tam komut satırları veya sürüme özgü bayraklar vermiyorum çünkü bunlar hızla değişir ve yanlış/eski bilgi vermek riskli olur.

### Tespit

- **Windows olay günlükleri**: LSASS'a (veya CloudAP barındıran süreçlere) anormal bellek erişimi (ör. Sysmon Event ID 10 - ProcessAccess, `GrantedAccess` değerlerinde `0x1010` / tam okuma izinleri; Microsoft Defender for Endpoint'in "credential access" imzaları).
- **Entra ID sign-in log'larında** aynı kullanıcı için, coğrafi olarak tutarsız ve **yeni/bilinmeyen bir cihaz kimliğinden (device ID)** gelen "token issued" olayları; özellikle `deviceId` claim'i beklenen cihazla eşleşmiyorsa.
- **"Token protection" (token binding) uyumsuzlukları**: Conditional Access'te token protection etkinse, çalınan (cihaza bağlı olmayan) bir PRT'den türetilen token'lar reddedilir ve bu reddedilme günlüklenir — bu sinyal başlı başına bir tespit fırsatıdır.
- Sign-in log'larında **"Session ID" veya "Token issuer"** alanlarında beklenmeyen tutarsızlıklar; aynı PRT session key'inin farklı IP/user-agent kombinasyonlarından kullanılması.
- EDR tarafında `dsregcmd.exe /status` gibi tanılama araçlarının veya bilinmeyen ikili dosyaların CloudAP DLL'lerine (`aadcloudap.dll` benzeri bileşenler — tam isim sürüme göre değişebilir) enjekte olması/erişmesi.

### Savunma

- **Token Protection (Conditional Access)**: Mümkün olan Graph/Exchange gibi kaynaklarda token'ı cihaza kriptografik olarak bağlayan politikaları etkinleştirmek — bu, çalınan bir token'ın başka bir makinede kullanılmasını doğrudan engeller.
- **Credential Guard**: LSA'yı sanallaştırılmış bir konteynerde izole ederek, yerel yönetici ayrıcalığı olsa dahi bazı kimlik bilgisi türlerinin çıkarılmasını zorlaştırmak.
- **Uç nokta sertleştirme**: Yerel yönetici sayısını azaltmak (en büyük tek kontrol — PRT çıkarma çoğunlukla zaten-ayrıcalıklı bir saldırgan gerektirir), LSASS koruması (PPL - Protected Process Light), EDR ile bellek erişim izleme.
- **Conditional Access ile "cihaz uyumluluğu" zorunluluğu**: Yönetilmeyen/uyumsuz cihazlardan gelen oturum açmaları kısıtlamak, çalınan token'ın değerini düşürür.
- **Sürekli erişim değerlendirmesi (Continuous Access Evaluation - CAE)**: Riskli oturum tespit edildiğinde token'ları anında iptal edebilme yeteneği.

### Yaygın Hatalar

- "MFA var, güvendeyiz" varsayımı: PRT saldırısı MFA'yı atlamaz, MFA'nın **sonucunu** çalar. MFA tek başına yeterli savunma değildir.
- PRT çıkarmayı "uzaktan, sıfır ayrıcalıkla mümkün" sanmak: gerçekte bu çoğunlukla zaten bir düzeyde erişim (yerel admin) gerektiren bir post-exploitation tekniğidir; savunma önceliği bu yüzden **ilk erişimi ve yatay hareketi (lateral movement) engellemek** olmalıdır.
- Token protection'ı yalnızca "yüksek riskli" hesaplara uygulamak; PRT hırsızlığı hedef seçmeden, ele geçirilen her uç noktada değerlidir.

---

## 2) Device Code Phishing

### Tanım ve Kök Neden

OAuth 2.0 **Device Authorization Grant** (device code flow), ekranı/klavyesi kısıtlı cihazlar (akıllı TV, IoT, CLI araçları) için tasarlanmıştır: cihaz bir kod üretir, kullanıcı bu kodu **başka bir cihazda** (telefon/bilgisayar tarayıcısında) bir Microsoft giriş sayfasına girer, orada normal şekilde kimlik doğrular (parola + MFA dahil), ve arka planda ilk cihaz token alır.

Kök neden: Bu akış, tasarım gereği **kullanıcının hangi "cihazı" onayladığını doğrulayacak bağlamsal bir işareti yoktur.** Kullanıcı sadece bir kodu bir sayfaya yapıştırıyor; o kodun arkasında meşru bir akıllı TV mi yoksa saldırganın script'i mi olduğunu ayırt edemez. Kimlik doğrulama sayfası tamamen gerçek (`login.microsoftonline.com`) olduğu için, klasik "sahte giriş sayfası" kimlik avı tespitleri (URL kontrolü, sertifika kontrolü) burada işe yaramaz.

### Nasıl Çalışır (Kavramsal)

1. Saldırgan, device code flow'u başlatarak meşru bir Microsoft uç noktasından geçerli bir kullanıcı kodu ve doğrulama URL'si alır.
2. Bu kodu/URL'yi bir kimlik avı e-postası, sahte "Teams toplantısı" daveti veya "hesabınızı doğrulayın" mesajı içine gömerek hedefe gönderir ("normalde bu kodu bir cihaza girersiniz" bahanesiyle).
3. Kullanıcı **gerçek** Microsoft sayfasında, **gerçek** parolasıyla ve **gerçek** MFA'sıyla oturum açar ve kodu onaylar.
4. Saldırganın script'i arka planda bekliyordur; kullanıcı onayladığı an, saldırgan geçerli bir access/refresh token alır — genellikle geniş kapsamlarla (mail okuma, dosyalara erişim vb., istenen `scope`'a bağlı).

Bu saldırının etkileyiciliği, **kullanıcının aslında hiçbir "yanlış" şey görmemesidir** — sayfa gerçek, MFA istemi gerçek, sadece "neyi" onayladığı yanlıştır (bilmediği bir oturumu).

### Tespit

- Entra ID sign-in log'larında `signInEventTypes` veya benzeri alanlarda **device code flow kullanımını** filtreleyip, bu akışın kurumda **beklenen/meşru kullanım senaryolarıyla** (ör. Azure CLI, belirli headless araçlar) eşleşip eşleşmediğini kontrol etmek.
- Anormal **user-agent / istemci uygulaması kombinasyonları**: device code flow normalde belirli CLI/IoT senaryolarında görülür; genel kullanıcı popülasyonunda ani bir artış şüphelidir.
- Aynı oturum açmadan hemen sonra **coğrafi olarak tutarsız IP'den** token kullanımı (kullanıcı bir yerden onaylıyor, token başka yerden kullanılıyor).
- **Riskli oturum açma (risky sign-in) sinyalleri** ile korelasyon; Identity Protection bu akışı da değerlendirebilir.

### Savunma

- **Device code flow'u Conditional Access ile kısıtlamak/engellemek**: Kurumda gerçekten ihtiyaç yoksa (çoğu kurumsal kullanıcı için yoktur), bu authentication flow'u tamamen devre dışı bırakmak veya yalnızca bilinen/onaylı uygulamalara/gruplara izin vermek en etkili kontroldür.
- **Kullanıcı farkındalığı**: "Bir kodu bir web sayfasına girmenizi isteyen" senaryoların, özellikle beklenmedik bağlamlarda (e-posta linki, sahte toplantı daveti) risk taşıdığını eğitmek.
- **Named locations ve cihaz uyumluluğu** gereksinimleriyle token'ın kullanılabileceği bağlamı daraltmak.
- **Sign-in frequency** politikalarıyla token ömrünü kısaltıp, kötüye kullanım penceresini daraltmak.

### Yaygın Hatalar

- Device code flow'un varlığından habersiz olmak / kurumda hangi meşru senaryolarda kullanıldığını bilmemek — bu da onu tamamen kapatmayı "riskli" sanıp açık bırakmaya yol açar.
- Bu saldırıyı klasik kimlik avı eğitimindeki "şüpheli URL'e bakın" tavsiyesiyle karşılamaya çalışmak: URL gerçekten şüpheli değildir, gerçek Microsoft domainidir. Eğitim mesajı farklı olmalı: "neyi onayladığınızı" sorgulayın.

---

## 3) İzin (Consent) Kimlik Avı ile Kalıcı Kiracı Erişimi — Illicit Consent Grant

### Tanım ve Kök Neden

Entra ID / Microsoft Graph ekosisteminde, bir kullanıcı bir uygulamayı (multi-tenant OAuth uygulaması) ilk kez kullanırken, o uygulamanın istediği **izinleri (permissions/scopes)** onaylamasını isteyen bir "consent" (izin) ekranı çıkar. Kök neden: Bu mekanizma, üçüncü taraf uygulamaların self-servis şekilde entegre olabilmesi için **kullanıcı bazlı onaya** izin verir (yönetici onayı olmadan). Saldırgan meşru bir Azure AD uygulaması kaydı oluşturup (kendi kiracısında, tamamen "yasal" görünen bir OAuth app), bunu kimlik avı ile hedefe sunarsa, kullanıcı "Kabul Et" dediği anda saldırgana **kalıcı, parola-bağımsız olmayan** bir erişim vermiş olur.

Bunun parola kimlik avından farkı ve neden bu kadar tehlikeli olduğu: Kurbanın parolasını değiştirmesi, hatta MFA eklemesi bu erişimi **iptal etmez**. Verilen izin (refresh token + consent grant) kayıtlı kalır; saldırgan periyodik olarak yeni access token türetmeye devam edebilir — ta ki izin açıkça iptal edilene veya uygulama kiracıdan engellenene kadar. Bu onu **kalıcılık (persistence)** tekniği yapar, sadece ilk erişim tekniği değil.

### Nasıl Çalışır (Kavramsal)

1. Saldırgan bir Azure AD uygulaması kaydeder (kendi kiracısında veya güvenliği zayıf bir ortamda), meşru görünen bir isim ve logo ile (ör. "Şirket Belge Görüntüleyici").
2. Uygulamaya `Mail.Read`, `Files.ReadWrite.All`, `offline_access` gibi kapsamlar tanımlar. `offline_access` kritik: bu, refresh token alınmasını sağlar, yani tek seferlik değil **süregelen** erişim demektir.
3. Kimlik avı e-postasıyla ("belgeyi görüntülemek için giriş yapın" gibi) kullanıcıyı, uygulamanın OAuth yetkilendirme URL'sine yönlendirir.
4. Kullanıcı **kendi meşru kimlik bilgileriyle** Microsoft'ta oturum açar (parola + MFA — bunlar hiç tehlikeye girmez) ve izin ekranında "Kabul Et"e tıklar.
5. Saldırgan artık kullanıcı adına, onaylanan kapsamlarda, uzun ömürlü erişime sahiptir — mailbox'ı okuyabilir, dosyalara erişebilir, hatta kapsamlara bağlı olarak yeni izinler/kurallar oluşturabilir (ör. gelen kutusu yönlendirme kuralları — klasik BEC/iş e-postası ele geçirme senaryosu).

### Tespit

- **Enterprise Applications / App Registrations** envanterinde düzenli tarama: özellikle **kullanıcı onaylı (user-consented), doğrulanmamış yayıncıya (unverified publisher) ait, geniş kapsamlı** uygulamaları listelemek.
- Microsoft Graph/Entra denetim günlüklerinde **"Consent to application"** olaylarını izlemek; özellikle toplu/anormal zamanlı onaylar (bir phishing kampanyasının işareti olabilir).
- Şüpheli uygulama izinlerinde `Mail.Read`, `Mail.ReadWrite`, `Files.ReadWrite.All`, `Directory.ReadWrite.All` gibi yüksek etkili kapsamların, düşük itibarlı/yeni kayıtlı uygulamalarla eşleşmesi.
- Kullanıcı posta kutusu kurallarında ani, açıklanamayan **otomatik yönlendirme/silme kuralları** (izin sonrası tipik kötüye kullanım göstergesi).

### Savunma

- **Kullanıcı onayını (user consent) kısıtlamak/devre dışı bırakmak**: Entra ID'de "kullanıcılar uygulamalara izin verebilir" ayarını kapatıp, tüm izinleri yönetici onayına (admin consent workflow) bağlamak — bu tek başına en güçlü kontroldür.
- **Admin consent workflow** kurmak: Kullanıcı bir uygulamaya ihtiyaç duyduğunda, yöneticiye inceleme için istek düşer; kritik izinler kör onay almaz.
- **Düzenli izin denetimi (periodic access review)**: Var olan tüm üçüncü taraf uygulama izinlerini, özellikle `offline_access` ve yüksek ayrıcalıklı Graph izinlerini periyodik gözden geçirmek ve gereksizleri iptal etmek.
- **Doğrulanmış yayıncı (verified publisher)** zorunluluğu getirerek, yalnızca kimliği doğrulanmış geliştiricilerin uygulamalarına izin akışını açık bırakmak.
- Kullanıcı eğitimi: "İzin ekranı" da bir kimlik doğrulama sayfası kadar dikkat gerektirir; hangi uygulamanın hangi veriye erişim istediğini okumadan "Kabul Et"e basmamak.

### Yaygın Hatalar

- Bu saldırıyı "parola kimlik avı" ile karıştırıp, MFA'nın bunu engelleyeceğini düşünmek — engellemez, çünkü kullanıcı gerçekten kendisi giriş yapar; çalınan şey parola değil **yetki**dir.
- İzin iptalini "kullanıcı parolasını sıfırlamak" ile eş tutmak: Parola sıfırlama consent grant'ı geçersiz kılmaz; uygulamanın izninin açıkça iptal edilmesi (service principal silme/izin kaldırma) gerekir.
- Sadece yeni uygulama kayıtlarına bakıp, **var olan** (tarihsel olarak onaylanmış, unutulmuş) uygulamaları denetlememek — kalıcılık tam olarak burada yaşar.

---

## 4) Token Manipülasyonu / Tampering ve nOAuth

### Tanım ve Kök Neden

Bu kategori, token'ın **çalınmasından** değil, token içindeki **iddiaların (claims)** güvenilirliğinin yanlış değerlendirilmesinden kaynaklanan zafiyetleri kapsar. En bilinen örnek **nOAuth** olarak adlandırılan sınıf: Bazı üçüncü taraf uygulamalar/SaaS servisleri, "Microsoft ile Giriş Yap" (Sign in with Microsoft) OIDC entegrasyonunda kullanıcıyı **yalnızca `email` claim'ine** (bazen doğrulanmamış/değiştirilebilir bir alana) göre tanımlar ve eşleştirir.

Kök neden: Entra ID (multi-tenant bir IdP olarak) her kiracıda **kullanıcı profil alanlarının (ör. e-posta adresi) idari olarak değiştirilebilir** olmasına izin verir. Eğer bir SaaS uygulaması "bu e-postaya sahip kullanıcı = bu hesap" mantığıyla hesap eşleştirmesi/hesap ele geçirme (account takeover) yapıyorsa ve bu e-posta alanının **doğrulanmış (verified) olup olmadığını kontrol etmiyorsa**, saldırgan kendi kontrolündeki bir Entra ID kiracısında, kurbanın e-posta adresini **kendi hesabının profil alanına** yazıp, o kimlikle hedef SaaS uygulamasına "Microsoft ile giriş yap" diyerek kurbanın hesabını ele geçirebilir — kurbanın Microsoft parolasına hiç dokunmadan.

Bu, klasik bir **"guvenilir olmayan girdiye güvenme"** (trusting unverified input) zafiyetidir; sadece bulut kimlik federasyonu bağlamında ortaya çıkar. Daha geniş "token tampering" kavramı da benzer bir mantığa dayanır: İmzası doğrulanmamış veya yanlış doğrulanmış (ör. `alg=none` kabulü, yanlış `aud`/`iss` kontrolü, JWKS anahtar karışıklığı) bir JWT'nin, saldırganın istediği claim'lerle (ör. `roles`, `groups`, `upn`) kabul edilmesidir.

### Nasıl Çalışır (Kavramsal)

**nOAuth senaryosu:**
1. Saldırgan kendi (ücretsiz/kendi kontrolündeki) Entra ID kiracısında bir hesap oluşturur.
2. Bu hesabın e-posta/UPN alanını, saldırının hedeflediği kurbanın (savunmasız SaaS'taki) e-posta adresiyle aynı yapar (kiracı yöneticisi olarak buna izin verilir).
3. Savunmasız SaaS uygulamasına gidip "Microsoft ile giriş yap" der; OIDC akışı tamamlanır ve token içinde `email: kurban@sirket.com` claim'i gelir.
4. SaaS uygulaması, bu e-postayı **doğrulanmış bir kimlik iddiası** sanıp, "bu e-postaya sahip zaten var olan hesap budur" diyerek saldırgana kurbanın hesabına oturum açtırır.

**Genel token tampering senaryosu:** Bir API/uygulama, gelen JWT'nin imzasını, `issuer`/`audience` alanlarını veya token türünü (id token mi access token mı) yeterince katı doğrulamıyorsa, saldırgan farklı bir amaçla verilmiş ama yapısal olarak benzer bir token'ı yeniden kullanabilir (**token substitution/confused deputy** türü sorunlar) veya claim'leri (özellikle imzasız/az korunan bölümleri) değiştirerek yetkisini yükseltebilir.

### Tespit

- Uygulama tarafında (savunmacı/geliştirici bakış açısıyla): Kimlik doğrulama entegrasyon loglarında, aynı e-posta adresiyle **farklı `tid` (tenant ID) veya `oid`/`sub` (nesne kimliği) değerlerinden** gelen giriş denemelerini işaretlemek — bu, "aynı e-posta, farklı Entra kiracısı" durumunun doğrudan göstergesidir ve nOAuth'un imzasıdır.
- Kimlik sağlayıcı tarafında normalde bu bir "saldırı" olarak görünmez (her şey geçerli bir OIDC akışıdır); bu yüzden tespit büyük ölçüde **entegre eden uygulamanın sorumluluğundadır**.
- JWT doğrulama loglarında imza doğrulama hatalarının sessizce yutulup yutulmadığını (fail-open) denetlemek; güvenlik testlerinde `alg=none`, anahtar karışıklığı (RS256→HS256 downgrade tarzı) ve `kid` (key ID) manipülasyonu senaryolarını test etmek.

### Savunma

- **Kullanıcı eşleştirmesini asla yalnızca `email` claim'ine dayandırmamak.** Entra ID'nin **değişmez (immutable)** ve kiracıya özgü tanımlayıcısı olan `oid` (object ID) + `tid` (tenant ID) çiftini birincil eşleştirme anahtarı olarak kullanmak.
- `email_verified` (varsa) claim'ini kontrol etmek ve doğrulanmamış e-postaya güvenmemek.
- Hesap bağlama (account linking) akışlarında, yeni bir federe kimliği var olan bir hesaba bağlamadan önce **ek doğrulama** (ör. mevcut hesaba önceden giriş yapmış olma zorunluluğu) istemek — "ilk gelen kazanır" (first-writer-wins) e-posta eşleştirmesinden kaçınmak.
- JWT doğrulamada: imzayı her zaman doğrulamak, `iss`/`aud`/`exp`/`nbf` alanlarını katı kontrol etmek, `alg` alanını sunucu tarafında sabitlemek (istemcinin/token'ın beyan ettiği algoritmaya güvenmemek), id token ile access token'ı karıştırmamak (her birinin amacı farklıdır).
- Mümkünse **tek kiracı (single-tenant)** kısıtlaması veya izin verilen kiracı allowlist'i uygulamak; multi-tenant OIDC entegrasyonlarında hangi kiracılara güvenildiğini açıkça sınırlamak.

### Yaygın Hatalar

- "OIDC/OAuth kullanıyoruz, güvenliyiz" varsayımı: Protokolün doğruluğu, **uygulamanın claim'leri nasıl yorumladığından** bağımsızdır. Standardı doğru uygulamak yetmez, iş mantığını (business logic) da doğru kurmak gerekir.
- `email` alanını benzersiz/güvenilir bir kimlik anahtarı sanmak — federasyonda e-posta bir **görüntüleme alanı**dır, bir **güvenlik sınırı** değildir.
- Access token'ı bir kimlik doğrulama kanıtı (id token yerine) olarak kullanmak; access token'ın amacı yetkilendirmedir, kimlik ispatı için tasarlanmamıştır.

---

## Bu Dört Tekniğin Ortak Zinciri ve Bütünsel Savunma

Bu dört teknik ayrı ayrı görünse de, gerçek saldırı zincirlerinde birbirini besler: Bir saldırgan device code phishing veya consent phishing ile ilk erişimi kazanır; ele geçirilen bir uç noktada yerel ayrıcalık yükseltip PRT çıkarır; PRT ile MFA'sız token türetip kalıcılığını nOAuth benzeri bir hesap bağlama zaafıyla üçüncü taraf SaaS'lara da yayar. Her aşamada ortak tema aynıdır: **kimlik doğrulamanın "kanıtı" (token), kimlik doğrulamanın "kendisinden" (parola+MFA anı) ayrılabilir bir nesnedir, ve bu nesne çalınabilir, taklit edilebilir veya yanlış yorumlanabilir.**

Bütünsel savunma önceliklendirmesi şöyle özetlenebilir:

1. **Token'ın değerini azaltmak**: Token protection, kısa sign-in frequency, Continuous Access Evaluation (CAE) ile çalınan token'ın işe yaraması penceresini daraltmak.
2. **Rıza/izin yüzeyini daraltmak**: Kullanıcı consent'ini kapatmak, admin consent workflow zorunlu kılmak, düzenli izin denetimi yapmak.
3. **Alternatif akışları kısıtlamak**: Device code flow gibi az kullanılan ama yüksek riskli akışları, ihtiyaç yoksa kapatmak.
4. **Uç nokta hijyeni**: Yerel yönetici sayısını azaltmak, Credential Guard/LSA koruması, EDR ile bellek erişimi izlemek — çünkü PRT çıkarma çoğu zaman zaten bir düzey ayrıcalık gerektirir.
5. **Geliştirici disiplini**: Federasyon entegrasyonu yazan/kuran ekiplerin, `email` yerine `oid+tid` gibi değişmez tanımlayıcıları kullanmasını, JWT doğrulamasını eksiksiz yapmasını sağlamak (kod incelemesi ve güvenlik testi kapsamına dahil etmek).

Sonuç olarak, Entra ID'ye özgü bu saldırı sınıfı, savunmacılara net bir mesaj verir: MFA ve parola politikaları hâlâ gereklidir ama **yeterli değildir**. Modern kimlik savunmasının ağırlık merkezi, token'ın yaşam döngüsünü (issuance, binding, validation, revocation) ve rıza/izin yönetimini kapsayacak şekilde genişlemek zorundadır.
