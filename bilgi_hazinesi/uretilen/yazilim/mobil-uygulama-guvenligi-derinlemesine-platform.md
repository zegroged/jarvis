# Mobil Uygulama Güvenliği Derinlemesine: Platform-Özgü Saldırı Yüzeyi

Mobil uygulama güvenliği genellikle tek bir şemsiye başlık altında ("mobil güvenlik") ele alınır, ama bu yaklaşım yanıltıcıdır. Masaüstü veya sunucu tarafı uygulamalardan farklı olarak, mobil uygulamalar saldırganın fiziksel olarak elinde bulunan, tersine mühendislik yapılabilen, üzerinde tam kontrol sahibi olduğu bir cihazda çalışır. Sunucu tarafında "istemciye asla güvenme" ilkesi bir slogan değil, mobilde hayatta kalma stratejisidir. Bu makale dört somut alt yüzeyi derinlemesine işler: yerel veri depolama (Keychain/Keystore), Deep Link/Intent hijacking, certificate pinning ve bypass'ı, WebView JavaScript bridge zafiyetleri; ayrıca kod obfuskasyon ile root/jailbreak tespitinin gerçekte ne işe yarayıp yaramadığını tartışır.

## Temel Zihniyet: İstemci Tarafı Asla Güvenilir Değildir

Kök neden şudur: mobil uygulama ikili dosyası (APK/IPA) kullanıcının cihazına tamamen teslim edilir. Saldırgan bu dosyayı indirebilir, açabilir (unzip), decompile edebilir (APK için `jadx`, `apktool`; iOS için `class-dump`, Hopper, IDA), çalışma zamanında hafızasını dump edebilir (Frida, Objection), ve hatta cihazı root/jailbreak yaparak işletim sisteminin güvenlik sınırlarını devre dışı bırakabilir. Bu nedenle mobil güvenlikte savunmanın temel felsefesi şudur: istemci tarafındaki hiçbir kontrol "kesin" güvenlik sağlamaz, sadece saldırı maliyetini yükseltir (defense in depth / "raise the bar"). Gerçek yetkilendirme ve doğrulama her zaman sunucuda yapılmalıdır; istemci tarafı kontroller (root tespiti, obfuskasyon, pinning) ek katmanlardır, tek başına yeterli değildir.

OWASP MASVS (Mobile Application Security Verification Standard) ve MASTG (Mobile Application Security Testing Guide) bu alanın endüstri standardı referans dokümanlarıdır; aşağıdaki konuların büyük kısmı bu standartların kapsadığı ama çoğu genel listede "mobil güvenlik" diye tek satırda geçiştirilen somut tekniklerdir.

## 1. Güvensiz Yerel Veri Depolama: Keychain ve Keystore Yanlış Kullanımı

### Tanım ve Kök Neden

iOS'ta **Keychain**, Android'de **Keystore** (ve API seviyesine göre EncryptedSharedPreferences/Jetpack Security), hassas verileri (token, şifre, kriptografik anahtar) düz metin dosya sisteminden ayrı, işletim sistemi tarafından korunan bir depoda tutmak için tasarlanmıştır. Kök neden problemi şudur: geliştiriciler çoğu zaman "kolay olan" `SharedPreferences` (Android) veya `UserDefaults` / düz dosya (iOS) kullanır, çünkü Keychain/Keystore API'leri daha karmaşıktır. Bu, root/jailbreak yapılmış bir cihazda (veya yedekleme dosyası üzerinden) hassas verinin düz metin olarak okunabilmesine yol açar.

**Android tarafında çalışma mantığı**: Android Keystore, anahtarların uygulama sürecinin belleğine hiç girmemesini sağlayabilir; kriptografik işlemler (imzalama, şifre çözme) donanım destekli güvenli bir bölgede (TEE - Trusted Execution Environment veya StrongBox varsa Secure Element) gerçekleşir. Anahtar "dışa aktarılamaz" (non-exportable) olarak işaretlenebilir; bu, anahtarın ham baytlarının hiçbir API ile çekilemeyeceği, sadece "bu anahtarla şunu şifrele/imzala" komutlarının verilebileceği anlamına gelir. Yaygın hata: geliştiricilerin AES anahtarını kendi ürettiği bir string'den türetip (`MessageDigest` ile hash'leyip) SharedPreferences'a yazması — bu, Keystore'un donanım izolasyonunu tamamen atlayan, sahte bir "şifreleme" yanılsamasıdır.

**iOS tarafında çalışma mantığı**: Keychain, `kSecAttrAccessible` özelliği ile korunur. Kritik ayrım şudur:
- `kSecAttrAccessibleAlways` (artık deprecated) — cihaz kilitliyken bile erişilebilir, jailbreak'li cihazda kolayca dump edilir.
- `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` — sadece cihaz açıkken VE sadece bu cihazda (iCloud yedeğine dahil edilmez, başka cihaza geri yüklenemez) erişilebilir; hassas token'lar için doğru seçim genelde budur.
- `Secure Enclave` (iPhone 5s ve sonrası) donanım tabanlı bir yardımcı işlemcidir; biyometrik (Face ID/Touch ID) korumalı anahtarlar burada saklanır ve ana işletim sistemi çekirdeği bile bu anahtarların ham değerine erişemez.

### Yaygın Hatalar ve Tuzaklar

1. **Yanlış accessibility sınıfı seçimi**: `Always` sınıfını kullanmak, cihaz kilitliyken bile Keychain girdisinin okunabilir olması demektir — çalınan/kaybedilen kilitli bir cihazda bile risk oluşturur.
2. **"Şifreleme" yanılsaması**: Anahtarı kodun içine gömmek (hardcoded key) veya basit bir XOR/obfuskasyonla "şifrelemek", saldırgan APK'yı decompile ettiğinde anlık olarak kırılır. Anahtar yönetimi, anahtarın *hiçbir zaman* uygulama ikilisinde sabit olarak bulunmaması ilkesine dayanır.
3. **Backup'a dahil etme**: Android'de `android:allowBackup="true"` (varsayılan) ile birlikte hassas veriyi `SharedPreferences`'ta tutmak, `adb backup` ile (bazı senaryolarda root gerekmeden) verinin dışarı çıkarılmasına izin verebilir. iOS'ta ise iTunes/Finder yedeği şifresizse Keychain'in bir kısmı (Always sınıfındakiler) yedeğe dahil olabilir.
4. **Root/Jailbreak sonrası varsayım hatası**: Geliştiriciler "cihaz root'lanmışsa zaten her şey kaybedilir" diyerek Keystore/Keychain kullanmayı gereksiz görebilir; oysa TEE/Secure Enclave tabanlı anahtarlar, kök erişimi olsa bile (donanım seviyesinde saldırı gerektirmedikçe) ham anahtar baytını sızdırmaz — bu yüzden doğru API kullanımı root sonrası bile bir savunma katmanı sağlar.

### En İyi Pratikler

- Hassas veriyi (oturum token'ı, refresh token, biyometrik ile korunan sırlar) yalnızca platformun güvenli deposunda (Keystore/Keychain, gerekirse StrongBox/Secure Enclave destekli) tutun.
- Anahtarları "non-exportable" (dışa aktarılamaz) olarak oluşturun; şifreleme/imzalama işlemini anahtarı çekmeden, API çağrısı olarak yaptırın.
- iOS'ta varsayılan olarak `WhenUnlockedThisDeviceOnly` gibi kısıtlayıcı bir accessibility sınıfı seçin, gerçekten gerekmiyorsa `Always` kullanmayın.
- Uzun ömürlü sırları (refresh token gibi) mümkünse hiç istemcide tutmayın; kısa ömürlü access token + sunucu tarafı oturum modeli tercih edin.
- Statik analiz araçlarıyla (MobSF gibi) uygulamanın hangi API'leri kullandığını ve düz metin depolama olup olmadığını düzenli denetleyin.

## 2. Deep Link ve Intent Hijacking

### Tanım

**Deep link**, bir URL şeması (`myapp://profil/123` gibi) veya **App Link/Universal Link** (HTTPS tabanlı, domain doğrulamalı) üzerinden doğrudan uygulama içindeki bir ekrana yönlendirme mekanizmasıdır. Android'de bu mekanizmanın alt yapısı **Intent** sistemidir; bir Intent, bileşenler arası (Activity, Service, BroadcastReceiver) mesajlaşma nesnesidir.

### Kök Neden / Çalışma Mantığı

Sorun, bu yönlendirme mekanizmalarının **doğası gereği güvenilmeyen girdi kanalları** olmasıdır — deep link'i tetikleyen taraf, uygulamanın kendisi değil, potansiyel olarak kötü niyetli bir web sayfası, başka bir uygulama veya SMS/e-posta içindeki bir bağlantı olabilir.

**Android Intent hijacking** iki ana biçimde ortaya çıkar:
1. **Implicit Intent kapma**: Bir uygulama `ACTION_VIEW` gibi örtük (implicit) bir Intent yayınladığında, sistem bu Intent'i işleyebilecek tüm uygulamaları listeler. Kötü niyetli bir uygulama, aynı intent-filter'ı (aynı scheme, aynı action) tanımlayarak kullanıcının seçici diyaloğunda görünebilir ve kullanıcıyı kandırıp trafiği kendine yönlendirebilir — özellikle özel URL şemaları (`myapp://`) birden fazla uygulama tarafından claim edilebildiği için bu risklidir.
2. **Exported component istismarı**: Android Manifest'te `exported="true"` olarak işaretlenmiş (veya intent-filter içerdiği için örtük olarak exported sayılan, eski hedef SDK'larda) Activity/Service/Receiver'lar, herhangi bir uygulama tarafından doğrudan başlatılabilir. Eğer bu bileşen, gelen Intent'in extra verilerini (`getIntent().getExtras()`) doğrulamadan işlerse (örneğin bir WebView'a doğrudan URL yükleme, bir dosya yolu açma, bir yetkilendirme adımını atlama), saldırgan uygulama bu bileşeni doğrudan tetikleyip mantığı kötüye kullanabilir. Bunun klasik örneği, parola sıfırlama veya OAuth "redirect" ekranını işleyen bir Activity'nin exported olması ve saldırganın sahte bir Intent ile bu ekranı manipüle edebilmesidir.

**iOS tarafında Universal Link hijacking** biraz farklı çalışır: Apple, custom URL scheme'lerin (`myapp://`) birden fazla uygulama tarafından kayıt edilebilmesi sorununu çözmek için **Universal Links** getirmiştir. Bunlar normal `https://` bağlantılarıdır ve hangi uygulamanın hangi domain için link'leri işleyebileceği, sunucuda barındırılan `apple-app-site-association` (AASA) dosyasıyla kriptografik olarak (domain sahipliği üzerinden) doğrulanır. Yanlış yapılandırılmış AASA (örneğin `paths` alanının çok geniş tanımlanması, `/*` gibi) veya AASA dosyasının hiç yayınlanmaması, linklerin beklenmedik şekilde Safari'ye düşmesine ya da (eski/yanlış yapılandırmalarda) beklenmeyen path'lerin uygulama içinde işlenmesine yol açabilir. Ayrıca uygulama hem custom scheme hem Universal Link destekliyorsa, saldırgan genelde daha zayıf doğrulamalı olan custom scheme'i tercih eder çünkü bu, herhangi bir domain doğrulaması gerektirmez.

**OAuth akışlarında özel risk**: Deep link'ler OAuth "implicit" veya "authorization code" akışlarında redirect URI olarak sıkça kullanılır (`myapp://oauth/callback?code=...`). Eğer scheme başka bir kötü niyetli uygulama tarafından da claim edilebiliyorsa, yetkilendirme kodu/token o uygulamaya sızdırılabilir. Bu yüzden OAuth için Universal Link/App Link (domain doğrulamalı) kullanmak, custom scheme kullanmaktan çok daha güvenlidir; PKCE (Proof Key for Code Exchange) eklemek ek bir savunma katmanıdır çünkü kod çalınsa bile code_verifier olmadan token'a çevrilemez.

### Tespit ve Savunma

- **Android**: Manifest'te gerçekten dışarıya açılması gerekmeyen bileşenleri `android:exported="false"` yapın (Android 12+ zaten intent-filter'lı bileşenler için bu alanın açıkça belirtilmesini zorunlu kılar). Exported bileşenlerde gelen Intent verisini kesinlikle güvensiz kabul edip doğrulayın (tip kontrolü, izin verilen değer aralığı, imza doğrulaması). Mümkünse App Links (domain doğrulamalı, `autoVerify="true"`) kullanın, salt custom scheme'e güvenmeyin.
- **iOS**: Universal Links'i tercih edin, AASA dosyasını doğru ve dar kapsamlı (`paths` alanını gereksiz genişletmeden) yapılandırın. Uygulama içinde gelen URL'nin path/parametrelerini asla doğrudan güvenilir kabul etmeyin; bir yetkilendirme veya durum değişikliği tetikleyecekse ek doğrulama (sunucu tarafı token doğrulaması gibi) ekleyin.
- Her iki platformda da **deep link ile tetiklenen her ekran/işlemin, kullanıcı kimlik doğrulaması ve yetki kontrolünü kendi içinde tekrar yapması** gerekir; deep link "zaten güvenli bir kaynaktan geldi" varsayımı yapılmamalıdır.
- Statik/dinamik test araçlarıyla (MobSF, `adb shell am start` ile manuel Intent fuzzing) exported bileşenlerin listesini çıkarıp her birinin girdi doğrulamasını gözden geçirin.

## 3. Certificate Pinning ve Bypass Teknikleri

### Tanım ve Kök Neden

**Certificate/Public Key Pinning**, uygulamanın TLS bağlantısı kurarken sunucudan gelen sertifikayı (veya sertifikanın public key'ini) yalnızca sistemin güvendiği CA zincirine değil, uygulamaya gömülü (pinned) belirli bir sertifika/anahtara karşı da doğrulamasıdır. Kök neden şudur: standart TLS doğrulaması, cihazın güvendiği CA deposundaki *herhangi bir* CA'nın imzaladığı sertifikayı kabul eder. Bir saldırgan, kurumsal bir MITM proxy sertifikasını kullanıcıya kurdurabilir, sahte bir CA'yı cihaza (özellikle yönetilen/kurumsal cihazlarda MDM üzerinden veya kullanıcıyı kandırarak) yükleyebilir, ya da (root/jailbreak'li cihazda) sistem CA deposunu doğrudan değiştirebilir. Pinning, bu senaryoların hepsinde "CA zinciri geçerli olsa bile, benim beklediğim spesifik sertifika/anahtar değilse bağlantıyı reddet" diyerek Man-in-the-Middle saldırılarına karşı ek bir katman sağlar.

**Nasıl çalışır**: Uygulama, sunucu sertifikasının SPKI (Subject Public Key Info) hash'ini veya tüm sertifikanın hash'ini kodun içine (ya da yapılandırma dosyasına) gömer. TLS handshake sırasında sunucudan gelen sertifika bu gömülü değerle karşılaştırılır; eşleşmezse bağlantı sonlandırılır. Public key pinning, sertifika pinning'e göre daha esnektir çünkü sertifika yenilendiğinde (aynı anahtar çiftiyle) pin değişmez, ama sertifikanın kendisi pinlendiyse her yenilemede uygulama güncellemesi gerekir — bu operasyonel bir tuzaktır (pin rotasyonu planlanmazsa, sertifika süresi dolduğunda uygulamanın eski sürümleri sunucuya hiç bağlanamaz hale gelir, "pinning kendi kendini DoS'lar").

### Bypass Teknikleri (Savunmacı Perspektiften Anlama Amaçlı)

Pinning bypass'ının nasıl çalıştığını anlamak, savunmayı doğru kurmak için gereklidir. Saldırgan/pentester tarafında en yaygın yaklaşım, **çalışma zamanında uygulamanın pinning kontrolünü yapan kod yolunu enstrümante edip (hooking) her zaman "geçerli" dönmesini sağlamaktır**. Bunun için tipik araç **Frida**'dır: Frida, hedef sürece JavaScript ile yazılmış bir "hook" enjekte ederek belirli bir fonksiyonun (örneğin Android'de `X509TrustManager.checkServerTrusted` veya OkHttp'nin `CertificatePinner.check`) çalışma zamanı davranışını değiştirebilir — fonksiyon çağrılır ama hep başarı döner. Hazır script koleksiyonları (`objection`, çeşitli topluluk "universal SSL pinning bypass" script'leri) bu işlemi otomatikleştirir. Bunun çalışabilmesi için genelde cihazın root/jailbreak olması (Frida server'ın sistem seviyesinde çalışabilmesi için) veya uygulamanın Frida gadget'ı ile yeniden paketlenmesi gerekir.

Bunun kök nedeni şudur: pinning kontrolü *istemci kodunun içinde* çalışır, ve istemci kodu saldırganın tam kontrolündeki bir ortamda (kendi cihazı) çalıştığı için, kontrol mantığının kendisi manipüle edilebilir. Bu, "istemci tarafı kontrol asla mutlak güvenlik sağlamaz" ilkesinin somut bir örneğidir — pinning, casual/ağ seviyesi MITM saldırılarına karşı çok etkilidir ama kararlı, cihaza fiziksel/root erişimi olan bir saldırgana karşı "zaman kazandırır", mutlak engel değildir.

### En İyi Pratikler

- Pinning'i **yalnızca** en hassas kanallar için değil (auth, ödeme gibi) mümkünse genel API trafiği için de düşünün, ama pin rotasyon stratejisi (birden fazla pin: mevcut + yedek/gelecek sertifika) olmadan asla üretime almayın.
- Public key pinning'i sertifika pinning'e tercih edin; sertifika yenilemesi anahtar rotasyonu gerektirmiyorsa uygulama güncellemesi zorunlu olmaz.
- Pinning'i **tek savunma katmanı olarak görmeyin**; root/jailbreak tespiti, anti-tampering (kod bütünlüğü kontrolü) ve sunucu tarafı anomali tespitiyle birlikte kullanın — bunların hiçbiri tek başına yeterli değildir ama birlikte saldırı maliyetini ciddi biçimde artırır.
- Sunucu tarafında, istemci sertifikasız/anormal davranışları (örneğin beklenmeyen User-Agent, TLS parmak izi anomalisi) izleyerek bypass edilmiş istemcilerden gelen trafiği ayrı bir risk sinyali olarak değerlendirin.

## 4. WebView JavaScript Bridge Zafiyetleri

### Tanım ve Kök Neden

Birçok mobil uygulama, tam yerel arayüz yazmak yerine (veya hibrit yaklaşımla) uygulama içinde bir **WebView** (Android'de `WebView`, iOS'ta `WKWebView`) barındırır ve web içeriği ile yerel kod arasında iletişim kurmak için bir **JavaScript Bridge/Interface** açar. Bu köprü, web sayfasındaki JavaScript'in yerel (Java/Kotlin/Swift/Objective-C) fonksiyonları doğrudan çağırabilmesini sağlar — örneğin `window.AndroidBridge.getUserToken()` gibi bir çağrı, yerel tarafta gerçek bir metodu tetikler.

Kök neden problemi şudur: **WebView içinde çalışan JavaScript, sunucu tarafından kontrol edilen (ya da XSS ile enjekte edilebilen) bir kod parçasıdır**, ve eğer bridge, hangi JavaScript kodunun onu çağırabileceğini kısıtlamıyorsa, kötü niyetli/ele geçirilmiş bir web sayfası bridge üzerinden yerel API'lere (dosya sistemi, konum, kişi listesi, kimlik bilgileri) erişebilir. Bu özellikle WebView içinde **üçüncü taraf/kontrol edilemeyen içerik** (reklamlar, harici linkler, kullanıcı tarafından girilen URL) yükleniyorsa kritik hale gelir.

Android'de klasik ve tarihsel olarak çok bilinen zafiyet, `addJavascriptInterface()` API'sinin eski Android sürümlerinde (API seviyesi 17 öncesi) **Java Reflection** üzerinden istismar edilebilmesiydi: JavaScript, bridge nesnesinin `getClass()` metoduna erişip reflection zinciriyle `Runtime.exec()` gibi tamamen ilgisiz, tehlikeli metodları çağırabiliyordu — bu da uzaktan kod çalıştırmaya kadar gidebiliyordu. Google bunu API 17'de `@JavascriptInterface` annotation zorunluluğu getirerek kısmen çözdü (yalnızca bu annotation ile işaretlenmiş metodlar JS'e açılır), ama bu da geliştiricinin annotation'ı doğru/dar kapsamlı kullanmasına bağlıdır.

### Yaygın Hatalar

1. **Gereğinden geniş bridge yüzeyi**: Bridge'e "her ihtimale karşı" çok sayıda güçlü metod (dosya okuma/yazma, kimlik bilgisi döndürme, ayarları değiştirme) eklemek, saldırı yüzeyini gereksiz büyütür.
2. **Kaynak doğrulaması eksikliği**: WebView'a yüklenen URL'nin hangi origin'den geldiği kontrol edilmeden (`shouldOverrideUrlLoading` / navigation delegate ile) herhangi bir sayfanın yüklenmesine izin vermek, XSS veya açık yönlendirme (open redirect) zincirinin bridge'e kadar ulaşmasını kolaylaştırır.
3. **`setJavaScriptEnabled(true)` gereksiz yere global açmak**: Statik/salt görüntüleme amaçlı içerik için JavaScript'i etkinleştirmek gereksiz risktir.
4. **iOS'ta `evaluateJavaScript` ile iki yönlü veri akışının doğrulanmaması**: `WKScriptMessageHandler` ile kurulan köprüde gelen mesajın (`message.body`) tipi ve içeriği doğrulanmadan işlenmesi, enjeksiyon zincirine kapı açar.
5. **File scheme (`file://`) erişiminin kapatılmamış olması**: Android'de `setAllowFileAccess` gibi ayarların gereksiz açık bırakılması, yerel dosya sistemine WebView içinden erişimi kolaylaştırabilir.

### En İyi Pratikler

- Bridge'i mümkün olduğunca **dar kapsamlı** tutun: yalnızca kesinlikle gerekli, düşük riskli metodları expose edin (örneğin "kullanıcı adını göster" gibi salt-okunur, zararsız bilgi).
- WebView'a yüklenecek içeriği (özellikle bridge etkinken) yalnızca **kendi kontrolünüzdeki, HTTPS ile servis edilen, kaynağı doğrulanmış origin'lerle** sınırlayın; navigation delegate/`shouldOverrideUrlLoading` ile origin whitelisting uygulayın.
- Bridge üzerinden gelen tüm girdiyi (parametre tipleri, uzunluk, format) sunucu API'sine gönderilen bir girdi kadar güvensiz kabul edip doğrulayın.
- Android'de minimum desteklenen API seviyesi izin veriyorsa `@JavascriptInterface` dışındaki hiçbir metodun JS'ten erişilemeyeceğinden emin olun; reflection tabanlı eski istismarların artık desteklenmeyen API seviyelerinde olduğunu doğrulayın.
- Mümkünse hassas işlemleri (oturum açma, ödeme) WebView içinde değil, tam yerel ekranlarda gerçekleştirin; WebView'ı yalnızca statik/düşük riskli içerik için kullanın.

## 5. Kod Obfuskasyon ve Root/Jailbreak Tespiti: Ne İşe Yarar, Ne Yaramaz

### Kod Obfuskasyonun Gerçek Rolü

Obfuskasyon (Android'de ProGuard/R8, iOS'ta daha sınırlı ticari araçlar), sınıf/metod/değişken isimlerini anlamsızlaştırarak, kontrol akışını karmaşıklaştırarak veya string'leri şifreleyerek decompile edilmiş kodun **okunmasını zorlaştırır**. Kök neden mantığı: derlenmiş bir ikili, matematiksel olarak her zaman "geri çevrilebilir" durumdadır (CPU onu yürütebiliyorsa, bir insan da onu anlayabilir, zaman ve çaba verildiğinde) — obfuskasyon bunu **imkansız değil, maliyetli** hale getirir. Bu yüzden obfuskasyon "güvenlik kontrolü" değil, **saldırı maliyetini artıran bir gecikme mekanizmasıdır**. Kritik iş mantığını (örneğin lisans doğrulama, kripto anahtar türetme) obfuskasyona güvenerek "gizli" tutmaya çalışmak temelde yanlış bir güvenlik modelidir (security through obscurity); gerçek gizli olması gereken şeyler (anahtarlar, sırlar) hiçbir zaman istemci ikilisinde bulunmamalıdır, obfuske edilmiş olsa bile.

### Root/Jailbreak Tespitinin Gerçek Rolü ve Sınırları

Root (Android) ve jailbreak (iOS), kullanıcının işletim sisteminin normalde uyguladığı izin/sandbox sınırlarını kaldırmasıdır. Uygulamalar genelde çeşitli sezgisel kontrollerle (belirli dosyaların varlığı — `su` binary, Cydia/Substrate izleri; belirli sistem özelliklerinin değeri; `su` komutunu çalıştırmayı deneme; SafetyNet/Play Integrity API gibi Google'ın sağladığı bütünlük doğrulama servisleri) cihazın root'lu olup olmadığını tahmin etmeye çalışır.

Kök neden ve temel sınırlama şudur: **bu tespit mekanizmasının kendisi de istemci tarafında, yani saldırganın tam kontrolündeki ortamda çalışır**. Root'lu bir cihazda çalışan bir kullanıcı, Magisk gibi araçlarla (Magisk Hide / Zygisk modülleri) root varlığını belirli uygulamalardan gizleyebilir; Frida ile tespit fonksiyonunun dönüş değerini doğrudan hook'layıp "root yok" döndürtebilir. Bu yüzden root/jailbreak tespiti **kararlı bir saldırgana karşı kesin bir engel değildir**; amacı, düşük-orta seviye tehdit aktörlerini (otomatik botlar, casual hile yapan kullanıcılar) engellemek ve tespit edilirse riskli işlemleri (örneğin bankacılık uygulamasında yüksek limitli işlem, DRM korumalı içerik oynatma) kısıtlamak veya ek doğrulama istemektir.

Google'ın **Play Integrity API**'si (eski adıyla SafetyNet) burada önemli bir ayrım getirir: bu servis, cihazın bütünlüğünü yalnızca istemci tarafı bir kontrolle değil, Google'ın sunucularıyla iletişime geçip donanım destekli bir attestation (doğrulama imzası) alarak yapar — bu, saf istemci tarafı sezgisel kontrollerden daha güvenilirdir çünkü sonucu üreten mantık saldırganın cihazında değil, Google'ın sunucusunda çalışır. Benzer şekilde iOS'ta **DeviceCheck / App Attest**, uygulamanın gerçek, değiştirilmemiş bir Apple cihazında çalıştığını sunucu tarafında doğrulamayı sağlayan bir mekanizmadır. Kavramsal ders şudur: **doğrulama mantığı ne kadar istemciden uzaklaşıp sunucu/donanım köküne (hardware root of trust) dayanırsa, o kadar güvenilir olur.**

### En İyi Pratikler (Sentez)

- Obfuskasyonu bir "gizlilik" aracı değil, tersine mühendislik maliyetini artıran bir katman olarak konumlandırın; gerçek sırları koda hiç gömmeyin.
- Root/jailbreak tespitini tek başına bir güvenlik duvarı değil, **risk sinyali** olarak kullanın: tespit edilirse işlemi tamamen engellemek yerine, sunucu tarafında ek doğrulama/daha sıkı limit uygulamak genelde daha sağlam bir stratejidir.
- Mümkün olduğunda platform sağlayıcının sunduğu attestation servislerini (Play Integrity, App Attest/DeviceCheck) kullanın; bunlar istemci tarafı sezgisel kontrollerden çok daha güvenilirdir çünkü doğrulama sonucu sunucu tarafında, saldırganın erişemediği bir kökten üretilir.
- Anti-tampering (kod imzası doğrulama, çalışma zamanı kendi kendini kontrol) ve root tespiti gibi kontrolleri **birden fazla, birbirinden bağımsız noktada** dağıtık uygulayın; tek bir merkezi "isRooted()" fonksiyonu, saldırganın tek bir hook noktasıyla tüm savunmayı atlamasına izin verir.

## Kapanış: Savunma Katmanlarının Bütünsel Mantığı

Bu dört alanın (Keychain/Keystore, deep link/Intent, certificate pinning, WebView bridge) ve iki destekleyici mekanizmanın (obfuskasyon, root/jailbreak tespiti) ortak paydası şudur: mobil güvenlik, **hiçbir istemci tarafı kontrolün mutlak olmadığı ama her katmanın saldırganın maliyetini ve riskini artırdığı** bir "defense in depth" oyunudur. Sağlam bir mimari; hassas veriyi doğru API'lerle (donanım destekli) saklar, dış tetikleyicilerden gelen her girdiyi (deep link, Intent, bridge mesajı) güvensiz kabul edip yeniden doğrular, ağ katmanında pinning ile MITM'i zorlaştırır, ve en kritik doğrulamaları (kimlik, yetki, bütünlük) her zaman istemcinin ötesinde, sunucuda veya donanım köklü bir attestation sisteminde tutar. Bu ilkeyi içselleştirmiş bir mühendis, hangi yeni saldırı tekniği ortaya çıkarsa çıksın (ve mutlaka çıkacaktır), doğru soruyu sorabilir: "Bu kontrol kırılırsa, arkasında başka hangi katman duruyor?"
