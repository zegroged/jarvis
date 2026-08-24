# Kablosuz İleri Saldırılar: Evil Twin, KARMA, WPS, 802.1X/EAP ve Bluetooth/BLE

> Bu makale **eğitim ve savunma** amaçlıdır. Amaç saldırıların **mekanizmasını anlamak**, kök nedenlerini görmek ve bunlara karşı **tespit (detection)** ile **savunma (mitigation)** mimarisi kurmaktır. Operasyonel canlı saldırı talimatı değildir.

## Giriş: Neden "İleri" Kablosuz Saldırılar?

Temel WPA2/WPA3 tartışması, kablosuz güvenliğin yalnızca **şifreleme katmanını** (encryption/authentication of the link) kapsar. Oysa gerçek saldırı yüzeyi çok daha geniştir. Bir saldırgan, parolayı hiç kırmadan da hedefe ulaşabilir:

- İstemciyi **sahte bir erişim noktasına** (rogue AP) çekerek trafiği ortaya alabilir.
- İstemci cihazın **kayıtlı ağ isimlerini (Preferred Network List, PNL)** sömürerek onu kandırabilir.
- **WPS** gibi kolaylık özelliklerindeki tasarım hatalarından PIN'i bruteforce edebilir.
- **Kurumsal (Enterprise) WiFi / 802.1X** ortamında kimlik doğrulama zincirinin (EAP) zayıf yapılandırmasını istismar edebilir.
- **Bluetooth/BLE** üzerinden eşleşme (pairing) ve reklam (advertising) katmanındaki zaafları kullanabilir.

Bu yazının ortak teması şudur: **Bu saldırıların çoğu şifrelemeyi kırmaz; güveni (trust) istismar eder.** İstemci "hangi ağa/cihaza güveneceğine" yanlış karar verir. Savunma da bu yüzden çoğunlukla "kriptografi" değil, "kimlik doğrulama ve doğrulama (verification) disiplini" ile kurulur.

---

## 1. Evil Twin (Sahte Erişim Noktası)

### Tanım

**Evil Twin**, meşru bir erişim noktasının (AP) **SSID'sini, güvenlik ayarlarını ve görünürlüğünü taklit eden** sahte bir AP'dir. Kurban cihaz, meşru ağa bağlandığını sanırken aslında saldırganın kontrol ettiği AP'ye bağlanır. Bu andan itibaren saldırgan **man-in-the-middle (MITM)** konumundadır.

### Kök Neden / Çalışma Mantığı

Kablosuz istemcinin "hangi AP'ye bağlanacağını" belirleyen temel kriterler tarihsel olarak zayıftır:

1. **SSID eşleşmesi**: İstemci, kayıtlı ağ ismini (örneğin "OfisWiFi") duyduğunda bağlanmaya meyillidir.
2. **Sinyal gücü (RSSI)**: Aynı isimde iki AP varsa, istemci genellikle **daha güçlü sinyalli** olana yönelir. Saldırgan kurbana fiziksel olarak yaklaşarak veya güç artırarak bunu istismar eder.
3. **Zayıf/eksik AP kimlik doğrulaması**: Açık (open) ağlarda ve tek yönlü doğrulamalı ağlarda, istemci AP'nin gerçekliğini kanıtlayamaz.

Saldırının klasik akışı: saldırgan meşru AP'nin SSID'siyle bir AP ayağa kaldırır; genellikle kurbanı meşru AP'den koparmak için **deauthentication/disassociation** çerçeveleri kullanılır (802.11 yönetim çerçevelerinin korumasız olduğu ortamlarda). Kurban yeniden bağlanırken daha güçlü sahte AP'ye düşer. Açık ağlarda sıklıkla bir **captive portal** (sahte giriş sayfası) gösterilerek kullanıcıdan parola veya kurumsal kimlik bilgisi toplanır.

### Örnek Senaryo

Bir kafede "Ucretsiz_WiFi" adlı açık bir ağ vardır. Saldırgan aynı isimle daha güçlü bir AP kurar ve sahte bir "giriş için e-posta/parolanızı girin" portalı sunar. Kullanıcı, gerçek portal ile sahte portalı ayırt edemez; girilen kimlik bilgileri saldırgana gider. Bu, teknik olarak hiçbir şifreyi kırmadan çalışan bir **kimlik avı (phishing)** + **rogue AP** kombinasyonudur.

### Tespit ve Savunma

**Tespit:**
- **Wireless Intrusion Detection/Prevention System (WIDS/WIPS)**: Aynı SSID'yi yayınlayan beklenmedik BSSID'leri (AP MAC), yetkisiz kanal/güç değişimlerini ve anormal deauth trafiğini işaretler.
- **BSSID allowlist / rogue AP tespiti**: Kurumsal ortamda meşru AP'lerin BSSID ve konum haritası bilinir; listede olmayan bir AP aynı SSID'yi yayınlıyorsa alarm üretilir.
- **Deauth flood tespiti**: Yönetim çerçevelerinde ani artış, Evil Twin hazırlığının klasik göstergesidir.

**Savunma:**
- **802.11w (Management Frame Protection, MFP/PMF)**: Yönetim çerçevelerini (deauth/disassoc dahil) koruyarak kurbanı zorla koparma saldırısını büyük ölçüde engeller. WPA3'te zorunludur.
- **WPA3-Enterprise veya doğru yapılandırılmış WPA2-Enterprise**: İstemcinin AP/sunucu kimliğini **sertifika ile** doğrulaması sağlanır (bkz. 802.1X bölümü).
- **Açık ağlardan kaçınma; OWE (Opportunistic Wireless Encryption)**: Açık ağlarda bile en azından pasif dinlemeyi zorlaştırır, ancak Evil Twin'e tam çözüm değildir.
- **Kullanıcı eğitimi**: Captive portal üzerinden parola isteyen sayfalara karşı şüphe; kurumsal kimlik bilgilerinin asla rastgele portala girilmemesi.

### Yaygın Hatalar

- "Ağ parolalı, o zaman Evil Twin çalışmaz" yanılgısı. Parola paylaşımlı (PSK) ise ve saldırgan parolayı biliyorsa, ya da açık ağ ise, taklit mümkündür.
- MFP/PMF'yi kapalı bırakmak; deauth saldırısına kapı açar.

---

## 2. KARMA ve PNL İstismarı

### Tanım

**KARMA** saldırısı, istemci cihazların **daha önce bağlandığı ağları hatırlama** davranışını istismar eder. Birçok cihaz, kayıtlı ağları ararken **probe request** çerçeveleri gönderir ("OfisWiFi orada mı?", "EvWiFi orada mı?"). KARMA yaklaşımında sahte AP, istemcinin sorduğu **her SSID'ye "evet, buradayım" yanıtı** vererek istemciyi kendine çeker.

### Kök Neden / Çalışma Mantığı

Sorunun kaynağı istemcinin **Preferred Network List (PNL)** yönetimidir:

- Cihaz, geçmişte bağlandığı ağların isimlerini saklar ve bunları **aktif olarak yayınlar** (özellikle "hidden network" olarak kaydedilmiş ağlar için).
- **Auto-join (otomatik bağlan)** açıksa, cihaz tanıdık bir isim duyduğunda kullanıcıya sormadan bağlanabilir.
- Klasik KARMA, AP'nin "her isme evet" demesine dayanır. Modern cihazlar bunu büyük ölçüde kısıtladı; bunun üzerine geliştirilen **MANA** gibi yaklaşımlar, gözlemlenen probe'ları ve yönlendirilmiş/broadcast probe davranışını daha akıllıca sömürerek PNL'deki isimleri hedefler.

Kritik nokta: **Açık (parolasız) ağlar KARMA'ya en açık olanlardır**, çünkü istemci bu ağlar için AP kimliğini doğrulayamaz. Parolalı ağlarda saldırgan doğru PSK'yı bilmeden 4-way handshake'i tamamlayamaz.

### Örnek Senaryo

Bir dizüstü, geçmişte bir otelin açık "Hotel_Guest" ağına bağlanmıştı ve auto-join açık. Cihaz sokakta "Hotel_Guest" için probe atar; sahte AP bu ismi anında sunar ve cihaz otomatik bağlanır. Kullanıcı hiçbir şey yapmadan saldırganın ağına düşer.

### Tespit ve Savunma

**Tespit:**
- Anormal derecede **çok sayıda farklı SSID'ye yanıt veren** bir AP, KARMA/MANA göstergesidir; WIDS bunu davranışsal olarak yakalar.
- İstemci tarafında beklenmedik otomatik bağlanmaların loglanması.

**Savunma:**
- **Auto-join'i açık ağlar için kapatmak**; hassas cihazlarda "sadece bilinen ve doğrulanmış ağlara bağlan" politikası.
- **PNL temizliği**: Kullanılmayan/eski açık ağ kayıtlarını silmek. Modern işletim sistemleri "unutulan" açık ağları otomatik yaymayı azaltmıştır; yine de hijyen önemlidir.
- **Hidden SSID kullanımından kaçınmak**: Gizli ağlar istemciyi ismi aktif yaymaya zorlar, bu da KARMA yüzeyini büyütür. "Gizli SSID = güvenlik" yaygın ve yanlış bir inançtır.
- Mümkün olan her yerde **doğrulamalı ağlar** (Enterprise/sertifika) kullanmak.

### Yaygın Hatalar

- "SSID'yi gizlersem güvenli olurum" yanılgısı; tam tersi, KARMA yüzeyini artırır.
- Otomatik bağlanmayı her yerde açık bırakmak.

---

## 3. WPS Bruteforce

### Tanım

**Wi-Fi Protected Setup (WPS)**, kullanıcının uzun WPA parolasını girmeden cihaz eklemesini kolaylaştırmak için tasarlanmış bir özelliktir. **PIN tabanlı** yöntemi, kablosuz güvenliğin en bilinen tasarım hatalarından birini içerir.

### Kök Neden / Çalışma Mantığı

WPS PIN'i 8 haneli bir sayıdır, ancak son hane bir **sağlama (checksum)** olduğu için gerçek entropi 7 hanedir. Asıl kritik hata şudur: doğrulama **PIN'i iki yarıya bölerek** yapar. AP, ilk yarıyı ve ikinci yarıyı **ayrı ayrı** doğru/yanlış olarak geri bildirir. Bu, arama uzayını yaklaşık 10^7'den (10 milyon) çok daha küçük bir toplam denemeye indirir: ilk yarı için ~10^4, ikinci yarı için ~10^3 mertebesinde denemeyle PIN bulunabilir. Bu, **online bruteforce**'u pratikte uygulanabilir kılar.

Ek olarak bazı üreticilerin WPS uygulamalarında PIN üretimi için kullanılan nonce/entropy zayıftı; bu, tek bir handshake'ten PIN'in **offline** hesaplanabildiği (genel olarak "Pixie Dust" adıyla bilinen) bir sınıf saldırıya yol açtı. Buradaki kök neden yine zayıf rastgelelik (weak randomness) ve kötü protokol tasarımıdır.

### Örnek Senaryo

Rate-limiting/lockout uygulamayan eski bir ev yönlendiricisinde, saldırgan WPS PIN'ini yukarıdaki iki-yarı zafiyeti sayesinde makul sürede dener ve bulur. PIN bulununca AP, **WPA parolasını (PSK)** saldırgana teslim eder; artık ağın parolası ele geçmiştir.

### Tespit ve Savunma

**Tespit:**
- AP loglarında/WIDS'te **yoğun WPS kayıt (registration) denemeleri**.
- Aynı istemciden art arda başarısız EAP-WSC alışverişleri.

**Savunma:**
- **WPS'i tamamen kapatın** (özellikle PIN yöntemini). En temiz çözüm budur.
- WPS gerekiyorsa yalnızca **push-button (PBC)** modunu, kısa zaman pencereleriyle kullanın; PIN modunu devre dışı bırakın.
- **Lockout / rate-limiting**: Belirli sayıda başarısız denemeden sonra WPS'i geçici kilitleyen firmware kullanın.
- **Firmware güncellemesi**: Zayıf entropi ve eksik lockout içeren eski sürümleri yükseltin.

### Yaygın Hatalar

- Güçlü WPA2 parolası koyup WPS PIN'i açık bırakmak: Parola ne kadar güçlü olursa olsun, WPS PIN kırılırsa parola sızar. **Güçlü parola, açık WPS'i kurtarmaz.**

---

## 4. Kurumsal WiFi / 802.1X ve EAP Saldırıları

### Tanım

**802.1X**, kurumsal ağlarda **port tabanlı erişim kontrolü** sağlar. Kimlik doğrulama, taşıyıcı olarak **EAP (Extensible Authentication Protocol)** kullanır ve genellikle bir **RADIUS** sunucusuna karşı yapılır. Roller: **supplicant** (istemci), **authenticator** (switch/AP), **authentication server** (RADIUS). "Enterprise" WiFi'nin PSK'ya üstünlüğü, her kullanıcının **ayrı kimliğe** sahip olması ve merkezî doğrulamadır. Ancak yanlış yapılandırma bu üstünlüğü tersine çevirebilir.

### Kök Neden / Çalışma Mantığı

EAP bir **çerçeve**dir; güvenlik seçilen **EAP yöntemine** ve yapılandırmaya bağlıdır.

**a) EAP-MD5 zayıflığı:** EAP-MD5, karşılıklı doğrulama sağlamaz ve challenge/response'u MD5 tabanlıdır. Yakalanan challenge-response çifti **offline sözlük/bruteforce** ile kırılabilir; ayrıca sunucu kimliğini doğrulamadığı için MITM'e açıktır. Kablosuz ortamda kullanılmaması gerekir.

**b) PEAP / EAP-TTLS ve "sunucu sertifikası doğrulamama" hatası:** PEAP ve TTLS, içteki zayıf kimlik alışverişini (örneğin MSCHAPv2) bir **TLS tüneli** içinde korur. Güvenlik tümüyle şu ön koşula bağlıdır: **istemci, RADIUS sunucusunun sertifikasını doğrulamalıdır** (doğru CA, doğru sunucu adı). Eğer istemcide "sunucu sertifikasını doğrulama" kapalıysa veya "her sertifikayı kabul et" ayarlıysa, saldırgan **sahte bir RADIUS/AP** kurup kendi sertifikasını sunar; istemci tüneli sahte sunucuyla kurar ve **iç kimlik alışverişini (MSCHAPv2 challenge/response) saldırgana teslim eder**. Bu, "evil twin + sahte RADIUS" ile kurumsal kimlik hasadının temel mantığıdır. Yakalanan MSCHAPv2 alışverişi daha sonra offline kırılabilir; MSCHAPv2'nin kriptografik zayıflıkları bunu kolaylaştırır.

**c) "Downgrade" ve iç yöntem zaafı:** İstemci politikası gevşekse, saldırgan istemciyi **daha zayıf bir iç yönteme** (ör. korumasız veya kolay kırılan bir mekanizmaya) yönlendirmeye çalışabilir. Kök neden: istemcinin **hangi yöntemi/sunucuyu kabul edeceğini katı biçimde sabitlememesi**.

### Örnek Senaryo

Bir şirkette PEAP-MSCHAPv2 kullanılıyor ama cihazlar elle "WiFi parolamı gir" diyerek yapılandırılmış ve sertifika doğrulaması kapalı. Saldırgan, aynı kurumsal SSID ile sahte AP ve sahte RADIUS ayağa kaldırır. Bir çalışanın cihazı bağlanmayı denerken kullanıcı adını ve MSCHAPv2 yanıtını sahte sunucuya gönderir. Saldırgan bunu offline kırarak **Active Directory kimlik bilgilerini** ele geçirir; bu, WiFi'den çok daha büyük bir tehdittir çünkü aynı kimlik başka sistemlerde de geçerlidir.

### Tespit ve Savunma

**Tespit:**
- **Sahte RADIUS/AP tespiti**: Aynı SSID'yi yayınlayan yetkisiz BSSID'ler için WIDS.
- RADIUS loglarında **başarısız EAP alışverişlerinin ani artışı**, bilinmeyen NAS/authenticator kaynakları.
- Beklenmedik EAP yöntemi kullanımı (ör. EAP-MD5 denemeleri) alarm konusu olmalı.

**Savunma:**
- **EAP-TLS'i tercih edin**: İstemci ve sunucu **karşılıklı sertifika** ile doğrulanır; parola yoktur, dolayısıyla "kimlik hasadı" saldırısının hedefi kalmaz. En güçlü seçenektir ancak sertifika/PKI yönetimi gerektirir.
- PEAP/TTLS kullanılıyorsa: **sunucu sertifikası doğrulamasını zorunlu kılın**, kabul edilecek **CA'yı ve RADIUS sunucu adını sabitleyin (pinning)**, "kullanıcı yeni sertifikayı kabul edebilir" seçeneğini kapatın. Bunu **merkezî yapılandırma/MDM/GPO** ile dayatın; kullanıcıya bırakmayın.
- **EAP-MD5'i devre dışı bırakın**; zayıf iç yöntemlere düşüşe izin vermeyin.
- **802.11w (PMF)** ve güncel WPA3-Enterprise; mümkünse yüksek güvenlik profili (192-bit suite).
- **NAC/RADIUS tarafında**: authenticator (NAS) allowlist, güçlü RADIUS shared secret, ve EAP identity gizliliği (dış kimlikte gerçek kullanıcı adını sızdırmama).

### Yaygın Hatalar

- **Sunucu sertifikası doğrulamasını kapatmak** en yaygın ve en tehlikeli hatadır; kurumsal WiFi'nin tüm güvenlik modelini çökertir.
- Cihazları kullanıcıların elle yapılandırmasına bırakmak (her cihaz farklı ve çoğu yanlış olur). Doğrusu MDM/GPO ile tek tip, doğrulamalı profil dağıtmaktır.
- "Enterprise = otomatik güvenli" varsayımı; yapılandırma yanlışsa PSK'dan daha kötü olabilir çünkü AD kimliği sızar.

---

## 5. Bluetooth ve BLE Güvenliği

### Tanım

**Bluetooth Classic (BR/EDR)** ve **Bluetooth Low Energy (BLE)** ayrı yığınlar (stack) ve ayrı eşleşme (pairing) modelleridir. Saldırı yüzeyi üç ana katmanda toplanır: **eşleşme/anahtar kurulumu**, **reklam/keşif (advertising/discovery)** ve **uygulama/GATT** katmanı.

### Kök Neden / Çalışma Mantığı

**a) Eşleşme (pairing) zaafları:** BLE'nin eski **"Legacy Pairing"** modeli zayıf anahtar üretimi içerir; **"Just Works"** eşleşme yöntemi ise **MITM koruması sağlamaz** çünkü kullanıcı doğrulaması (numeric comparison/passkey) yoktur. Cihazlar Just Works'e düşebiliyorsa, saldırgan araya girebilir. **Secure Connections (LE SC)**, eliptik eğri tabanlı anahtar değişimiyle bunu güçlendirir; ancak her iki taraf da desteklemeli ve zayıf moda düşüş engellenmelidir.

**b) Düşürme (downgrade) saldırıları:** Genel bir sınıf olarak, eşleşme sırasında **daha zayıf yönteme veya daha kısa anahtar entropisine** zorlama girişimleri vardır. Tarihsel olarak Bluetooth anahtar entropisi pazarlığındaki zayıflıklar (ör. anahtar uzunluğunu çok düşük değere indirme) araştırmalarda gösterilmiştir. Kök neden: iki cihazın güvenlik parametrelerini pazarlarken **alt sınırı yeterince yüksek tutmaması**.

**c) Reklam/keşif katmanı:** BLE cihazları çevreye **advertising** paketleri yayar. Statik/rastgele olmayan adresler **cihaz takibine (tracking)** yol açar; bu yüzden modern cihazlar **rastgele değişen (resolvable private) adres** kullanır. Ayrıca reklam verisi çoğu zaman şifresiz olduğundan, hassas bilgi yayınlamak (cihaz adı, kullanıcı ipuçları) mahremiyet sızıntısıdır.

**d) Uygulama/GATT katmanı:** Birçok BLE cihazı (IoT, giyilebilir) **GATT servislerinde kimlik doğrulama/yetkilendirme uygulamaz**; komutları düz gönderir. Saldırgan menzildeyken bu servislere yazarak cihazı kontrol edebilir. Kök neden: geliştiricinin güvenliği "eşleşme var" varsayımına bırakıp **uygulama seviyesinde doğrulama koymaması**.

> Not: Bu alanda çok sayıda isimlendirilmiş zafiyet (BlueBorne, KNOB, BLESA, Sweyntooth gibi aileler) araştırma literatüründe geçer. Kesin CVE numaralarını ve etkilenen tam sürümleri burada uydurmuyorum; önemli olan **sınıf**: uzaktan kod/DoS (stack implementation bugları), anahtar entropisi düşürme, ve yeniden bağlanmada kimlik doğrulama atlatma.

### Örnek Senaryo

Bir akıllı kilit, telefonla "Just Works" ile eşleşiyor ve GATT komutlarında ek doğrulama yok. Saldırgan menzildeyken eşleşme trafiğini gözlemler veya doğrudan GATT servisine "aç" komutunu yazar. MITM koruması olmadığından cihaz komutu kabul edebilir. Burada kriptografi değil, **eşleşme modeli ve uygulama katmanı** hatası istismar edilmiştir.

### Tespit ve Savunma

**Tespit:**
- Kurumsal ortamda **Bluetooth aktivite izleme**; beklenmedik eşleşme denemeleri ve bilinmeyen cihazların advertising'i.
- IoT cihazlarda anormal GATT yazma trafiği (cihaz üreticisi telemetri sağlıyorsa).

**Savunma:**
- **LE Secure Connections zorunlu**; **Just Works'ü hassas işlevler için reddet**, numeric comparison/passkey ile MITM koruması iste.
- **Minimum anahtar entropisini yüksek tut**; düşürme pazarlığına izin veren eski modları kapat.
- **Uygulama katmanında kimlik doğrulama**: GATT komutlarını cihaz kimliği/oturum anahtarı ile doğrula; "eşleşme yeterli" varsayma.
- **Resolvable private address** kullan; gereksiz advertising ve hassas veri yayınını kes; cihazı gerekmeyince **non-discoverable** yap.
- **Firmware güncellemesi**: Stack seviyesindeki (RCE/DoS) hatalar için yamaları uygula.
- **Menzil ve maruziyet azaltma**: Kritik cihazlarda Bluetooth'u gerekmedikçe kapalı tut; eşleşmeyi kontrollü ortamda yap.

### Yaygın Hatalar

- "Menzil kısa, o yüzden güvenli" yanılgısı; yönlü antenlerle menzil beklenenden çok daha uzun olabilir.
- Eşleşme yapıldı diye uygulama katmanı doğrulamasını atlamak.
- Sabit/statik Bluetooth adresi ve gereksiz keşfedilebilirlik (discoverability) bırakmak.

---

## Genel Savunma Mimarisi ve Çıkarımlar

Bu beş saldırı ailesinin ortak dersleri:

1. **Kimlik doğrulama tek yönlü olmamalı.** Evil Twin, KARMA ve sahte-RADIUS saldırılarının hepsi, istemcinin **karşı tarafı doğrulamamasından** beslenir. Çözüm: karşılıklı doğrulama (EAP-TLS, sertifika pinning, LE Secure Connections).
2. **Kolaylık özellikleri saldırı yüzeyidir.** WPS PIN, auto-join, Just Works, hidden SSID — hepsi "kullanıcıyı rahatlatmak" için tasarlandı ve hepsi güvenlik zafiyeti doğurdu. Gerekmeyeni kapatın.
3. **Yönetim/kontrol katmanını koruyun.** 802.11w (PMF), MFP; deauth ve düşürme saldırılarını engeller.
4. **Merkezî yapılandırma dayatın.** Kurumsal WiFi güvenliği kullanıcının elindeki ayara bırakılamaz; MDM/GPO ile doğrulamalı profil zorunludur.
5. **İzleme (WIDS/WIPS + RADIUS/Bluetooth logları) olmadan tespit yoktur.** Bu saldırıların çoğu sessizdir; yalnızca davranışsal anormallik izlemesiyle yakalanır.

Son ilke: **Katmanlı güvenlik.** Tek bir kontrol (güçlü parola, veya sadece şifreleme) yeterli değildir. Şifreleme + karşılıklı kimlik doğrulama + yönetim çerçevesi koruması + izleme + kullanıcı hijyeni birlikte çalıştığında bu ileri kablosuz saldırıların çoğu ya imkânsızlaşır ya da hızla tespit edilir.
