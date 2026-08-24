# macOS Güvenliği ve Privilege Escalation (TCC, SIP, Entitlements, Codesigning Bypass)

## Giriş ve Neden Önemli

Kurumsal ortamlarda macOS endpoint sayısı hızla artıyor; mühendislik, tasarım ve yönetim ekipleri giderek daha fazla Mac kullanıyor. Bu da macOS'un güvenlik mimarisini anlamayı bir lüks olmaktan çıkarıp zorunluluk haline getirdi. Windows ve Linux güvenliği geniş biçimde belgelenmişken macOS'a özgü mekanizmalar (TCC, SIP, entitlements, code signing zinciri, launch daemon persistence) çoğu kurumsal savunma ekibinde kör nokta olarak kalır.

Bu makale bu mekanizmaları **anlamak** ve bunlara karşı **tespit/savunma** kurmak için yazılmıştır. Amaç, macOS'un katmanlı güvenlik modelinin nasıl çalıştığını, saldırganların bu katmanları neden ve nasıl aşındırmaya çalıştığını, savunma tarafının nereye bakması gerektiğini kavramaktır. Bu bir canlı saldırı reçetesi değildir; kavramsal ve savunma odaklıdır.

## macOS Güvenlik Modelinin Temel Katmanları

macOS güvenliği tek bir duvar değil, iç içe geçmiş birkaç bağımsız kontrol mekanizmasıdır. Bunları birbirinden ayırmak kritik; çünkü her biri farklı bir tehdit modeline hizmet eder ve biri aşılsa bile diğeri devrede kalabilir.

- **UNIX izin modeli ve POSIX ACL'ler:** Klasik kullanıcı/grup/diğerleri izinleri. Temel katman ama tek başına yetersiz.
- **SIP (System Integrity Protection):** root olsanız bile sistem dosyalarına dokunamamanızı sağlayan kernel seviyesi bir kilit.
- **TCC (Transparency, Consent, and Control):** Uygulamaların kameraya, mikrofona, dosyalara, ekran kaydına erişimi için kullanıcı onayı zorunluluğu.
- **Code Signing ve Notarization:** Çalışan kodun kimliğinin doğrulanması ve Apple tarafından tarandığının garantisi.
- **Entitlements:** İmzalı bir binary'nin hangi ayrıcalıklı yeteneklere sahip olabileceğini tanımlayan izin listesi.
- **Gatekeeper ve Quarantine:** İnternetten indirilen kodun ilk çalıştırılmasında yapılan kontroller.

Bu katmanların ortak felsefesi şudur: **root olmak artık her şeyi yapabilmek anlamına gelmez.** Modern macOS'ta root bile SIP korumalı alanlara veya TCC korumalı verilere doğrudan erişemez. Privilege escalation'ın anlamı burada değişir; artık sadece "root olmak" değil, bu ek katmanları da aşındırmak gerekir.

## SIP (System Integrity Protection)

### Tanım

SIP, El Capitan ile gelen ve "rootless" olarak da anılan bir korumadır. Kernel düzeyinde uygulanır ve `/System`, `/usr` (bazı alt dizinler hariç), `/bin`, `/sbin` gibi kritik dizinlerdeki dosyaların değiştirilmesini, silinmesini; korumalı process'lere debugger bağlanmasını; imzasız kernel extension yüklenmesini engeller. Kritik nokta: bu kısıtlamalar **root için bile** geçerlidir.

### Kök Neden / Çalışma Mantığı

SIP'in temel fikri, uid=0 (root) ile sistem bütünlüğünü ayrıştırmaktır. Klasik UNIX modelinde root = tanrı modudur. Apple, tek bir uid 0 ele geçirmenin tüm sistemi çökertmesini istemedi. Bu yüzden korumayı kullanıcı-alanı izinlerinin **üstünde**, kernel'de konumlandırdı. Dosyalara ek bir "restricted" bayrağı (extended attribute / flag) atanır ve kernel bu bayraklı nesneler üzerindeki değişiklikleri, çağıran uid ne olursa olsun reddeder.

SIP'in durumu NVRAM'de saklanır ve normal çalışan sistemden değiştirilemez. Ancak Recovery ortamında `csrutil` aracıyla kapatılabilir. Bu tasarımın sonucu: SIP'i kapatmak, saldırganın hedef makinede **fiziksel erişim ve yeniden başlatma** yeteneği gerektirir; uzaktan sessizce kapatmak tasarım gereği zordur.

### Saldırgan Perspektifi (Kavramsal)

Saldırganlar SIP'i doğrudan "kapatmaya" çalışmak yerine, SIP kapsamı **dışında** kalan ama yine de ayrıcalıklı olan yollar arar: SIP korumalı olmayan yazılabilir konumlar, SIP'ten muaf tutulmuş (exempt) belirli Apple binary'lerinin kötüye kullanımı, ya da SIP kontrolündeki bir mantık hatası. Tarihsel olarak birkaç araştırma, belirli sistem servislerinin SIP muafiyetini kötüye kullanarak korumalı alanlara yazma imkânı bulduğunu göstermiştir. Bu tür zafiyetler genellikle Apple tarafından hızla yamalanır.

### Tespit ve Savunma

- **SIP durumunu izleyin:** `csrutil status` ile SIP'in etkin olduğunu doğrulayın. MDM/endpoint yönetimiyle filoda SIP'i "enabled" olarak zorunlu tutun; "disabled" gören her makineyi olay olarak işleyin.
- **NVRAM/Recovery erişimini kısıtlayın:** Fiziksel güvenlik ve firmware password (Apple Silicon'da farklı çalışır) SIP kapatma saldırılarını zorlaştırır.
- **Güncel kalın:** SIP bypass'ları neredeyse her zaman OS güncellemeleriyle kapatılır. Yama gecikmesi en büyük risktir.

## TCC (Transparency, Consent, and Control)

### Tanım

TCC, hangi uygulamanın hangi hassas kaynağa (kamera, mikrofon, ekran kaydı, Kişiler, Takvim, Fotoğraflar, Full Disk Access, Accessibility vb.) erişebileceğini yöneten izin çerçevesidir. Bir uygulama korunan bir kaynağa ilk eriştiğinde kullanıcıya çıkan "... uygulaması kameranıza erişmek istiyor" diyaloğu TCC'nin görünen yüzüdür.

### Kök Neden / Çalışma Mantığı

Kararlar bir SQLite veritabanında saklanır. İki tür TCC deposu vardır: kullanıcı başına (kullanıcının home dizini altında) ve sistem geneli. Bu veritabanlarının kendisi de TCC ve SIP tarafından korunur; yani bir uygulama doğrudan bu dosyayı düzenleyip kendine izin veremez (en azından tasarım hedefi budur).

TCC'nin en önemli ve en çok kötüye kullanılan yeteneği **Full Disk Access (FDA)** ve **Accessibility** izinleridir. FDA'ya sahip bir uygulama, pratikte diğer uygulamaların TCC-korumalı verilerine ve TCC veritabanının kendisine dahi erişebilir. Accessibility izni, bir uygulamanın diğer uygulamaların arayüzünü kontrol etmesine (tıklama, tuş gönderme) izin verir; bu, ekran otomasyonu için gerekli ama kötüye kullanıldığında güçlü bir yetenektir.

### Saldırgan Perspektifi (Kavramsal)

TCC bypass'ları genellikle şu kalıplarda görülür:

- **Zaten yetkili bir uygulamanın devralınması:** Kullanıcı Terminal'e, bir yedekleme aracına ya da bir geliştirici aracına FDA verdiyse, o process'e enjeksiyon veya o aracın script yeteneklerinin kötüye kullanımı TCC duvarını dolaylı olarak aşar. Saldırgan izni "almak" yerine izni **zaten olan** bir bağlamda çalışmayı hedefler.
- **TCC veritabanını doğrudan yazma:** SIP zayıfsa veya bir yol bulunursa saldırgan `TCC.db`'ye kendi izin kaydını eklemeye çalışır.
- **Kullanıcıyı yanıltma:** Meşru görünen bir diyalogla kullanıcıdan Accessibility veya FDA izni istemek. Bu teknik olmaktan çok sosyal mühendisliktir ama pratikte çok etkilidir.
- **Muafiyet ve mantık hatalarının kullanımı:** Belirli Apple bileşenlerinin veya app-bundle ilişkilerinin TCC değerlendirmesindeki köşe durumları.

### Tespit ve Savunma

- **FDA ve Accessibility izinlerini envanterleyin:** Hangi uygulamalara bu iki güçlü iznin verildiğini MDM üzerinden düzenli olarak toplayın. Beklenmeyen bir binary'nin FDA/Accessibility izni alması yüksek öncelikli alarmdır.
- **TCC.db değişikliklerini izleyin:** FSEvents/EndpointSecurity ile TCC veritabanı dosyalarına yazma girişimlerini izleyin. Meşru akışta bu dosyayı sadece sistem servisleri değiştirir.
- **Terminal/Script araçlarına FDA vermekten kaçının:** Terminal.app'e Full Disk Access vermek, o Terminal'de çalışan her şeye FDA vermek demektir; bu, savunma açısından geniş bir saldırı yüzeyidir.
- **MDM ile PPPC profilleri:** Privacy Preferences Policy Control profilleriyle hangi uygulamaların hangi izinlere sahip olacağını merkezi olarak yönetin ve kullanıcı onayına bağımlılığı azaltın.

## Code Signing, Notarization ve Gatekeeper

### Tanım

**Code signing**, bir binary'nin belirli bir geliştirici kimliğiyle imzalandığını ve imzalandıktan sonra değiştirilmediğini kriptografik olarak garanti eder. **Notarization**, geliştiricinin binary'yi Apple'a gönderip otomatik zararlı yazılım taramasından geçirdiğinin kanıtıdır. **Gatekeeper**, indirilen ve karantina bayrağı taşıyan bir uygulamayı ilk çalıştırmada bu imza ve notarization kontrollerinden geçiren mekanizmadır.

### Kök Neden / Çalışma Mantığı

Code signature, binary'nin kod sayfalarının hash'lerini içeren bir yapı olan Code Directory üzerine kurulur. Kernel, imzalı bir binary çalışırken bu hash'leri doğrular; sayfalar değiştirilmişse imza geçersiz olur. İmza aynı zamanda **entitlements**'ı da taşır (aşağıya bakınız) ve bir **Team Identifier** içerir.

Karantina mekanizması `com.apple.quarantine` adlı bir extended attribute ile çalışır. İnternetten indirilen dosyaya tarayıcı/indirici bu bayrağı ekler; Gatekeeper ilk çalıştırmada bu bayrağı görünce doğrulama yapar. Bayrak yoksa (ör. dosya bir arşivden düzgün çıkarılmadıysa veya komut satırıyla oluşturulduysa) Gatekeeper devreye girmeyebilir.

### Saldırgan Perspektifi (Kavramsal)

- **Quarantine bayrağından kaçınma:** Karantina attribute'unu taşımayan yollarla kod teslim etmek (belirli arşiv formatları, mount edilen imajlar, karantina yaymayan araçlar) Gatekeeper'ın atlanmasına yol açabilir. Apple bu yolları zaman içinde tek tek kapatmıştır.
- **İmza/notarization mantık hataları:** İmza doğrulamasının bir bileşeni tam kapsamlı yapmadığı köşe durumlar (ör. bundle içindeki bazı kaynakların doğrulanmaması, sembolik bağ/yol hileleri). Bunlar tipik olarak CVE ile yamalanır.
- **Meşru imzalı araçların kötüye kullanımı ("Living off the Land"):** Apple imzalı, notarize edilmiş yerleşik araçların (script yorumlayıcıları, indirme araçları) kötü amaçlı zincirlerde kullanılması. Burada imza gerçek ve geçerlidir; kötüye kullanılan şey aracın yeteneğidir.
- **Çalınmış/kötüye kullanılan Developer ID:** Saldırganın geçerli bir geliştirici sertifikası edinip zararlıyı imzalaması. Apple bu sertifikaları tespit edince iptal eder (revocation), ama tespit öncesi bir pencere olur.

### Tespit ve Savunma

- **İmza ve notarization doğrulaması:** Filodaki binary'lerin imza durumunu ve Team ID'lerini toplayın. `codesign` ve `spctl` mantığıyla imzasız veya iptal edilmiş imza taşıyan yürütülebilirleri işaretleyin.
- **Quarantine bayrağını izleyin:** İndirilen ama karantina bayrağı taşımayan yürütülebilir dosyalar şüphelidir; bayrağı silen işlemleri (`xattr -d` benzeri davranış) tespit edin.
- **Allowlisting:** Kritik ortamlarda sadece bilinen Team ID'lere ait imzalı uygulamaların çalışmasına izin veren politika kurun.
- **Revocation'a güvenmeyin ama izleyin:** İptal edilen sertifikalar bir savunma katmanıdır fakat tek başına yeterli değildir.

## Entitlements

### Tanım

Entitlements, imzalı bir binary'nin code signature'ına gömülü olan ve o binary'nin hangi özel yeteneklere sahip olabileceğini tanımlayan anahtar/değer listesidir. Örneğin bir uygulamanın belirli bir TCC korumalı kaynağa erişebilmesi, sandbox dışına çıkabilmesi veya belirli ayrıcalıklı sistem servisleriyle konuşabilmesi entitlements ile belirlenir.

### Kök Neden / Çalışma Mantığı

Entitlements imzanın parçası olduğu için değiştirilemez: bir binary'nin entitlements'ını düzenlerseniz imzası bozulur. Bu, entitlements'ı güçlü bir güven mekanizması yapar. Kritik ve tehlikeli entitlements'lara örnekler (kavramsal):

- **Sandbox'tan muafiyet** veya sandbox'ı gevşeten anahtarlar.
- **`get-task-allow`** benzeri, process'e debugger bağlanmasına izin veren geliştirme amaçlı anahtarlar. Üretim binary'sinde bu anahtarın bulunması, kod enjeksiyonu için kapı açar.
- **`com.apple.security.cs.disable-library-validation`:** Bu entitlement, binary'nin farklı Team ID'lere ait (yani "yabancı") kütüphaneleri yüklemesine izin verir. Library validation'ı kapatmak, dylib injection saldırıları için klasik bir zemindir.
- Belirli özel/private Apple entitlements'ları güçlü sistem yeteneklerine erişim verir.

### Saldırgan Perspektifi (Kavramsal)

Saldırgan, filoda **tehlikeli entitlements taşıyan meşru imzalı bir binary** arar. Örneğin library validation kapalı ve aynı zamanda güçlü bir TCC iznine sahip bir uygulama bulursa, o uygulamaya kendi dylib'ini yüklettirerek (dylib hijacking/injection) o uygulamanın **kimliğini ve izinlerini devralabilir.** Burada saldırganın kendi kodu imzasız veya düşük yetkili olsa bile, kurbanın entitlements'ları sayesinde yüksek yetkili bir bağlamda çalışır. Buna bazen "entitlement borrowing" veya güven zincirinin kötüye kullanımı denir.

### Tespit ve Savunma

- **Tehlikeli entitlements envanteri:** `disable-library-validation`, `get-task-allow`, `allow-dyld-environment-variables` gibi anahtarları taşıyan uygulamaları filoda tespit edin. Özellikle üçüncü parti uygulamalarda bunlar risk sinyalidir.
- **Dylib hijacking'e açık uygulamaları arayın:** Uygulama, imzasız/eksik dylib'leri arama yollarından (search path) yüklüyor mu? Bu klasik bir zafiyet kalıbıdır.
- **Kod enjeksiyonu telemetrisi:** EndpointSecurity ile process'e yapılan task_for_pid/debugger bağlantılarını ve anormal dylib yüklemelerini izleyin.

## Launch Daemon / Launch Agent Persistence

### Tanım

macOS'ta arka plan servisleri ve otomatik başlatma `launchd` ile yönetilir. **Launch Daemons** sistem genelinde ve root olarak (kullanıcı oturumundan bağımsız) çalışır; **Launch Agents** ise kullanıcı oturumu bağlamında çalışır. Yapılandırmaları `LaunchDaemons` ve `LaunchAgents` dizinlerindeki plist dosyalarıyla tanımlanır.

### Kök Neden / Çalışma Mantığı

Bir saldırganın en çok istediği şey **kalıcılık (persistence)**: yeniden başlatmadan sonra kodun tekrar çalışması. `launchd`, macOS'ta bunun en doğal ve en yaygın yoludur; çünkü meşru yazılımlar da aynı mekanizmayı kullanır. Bir plist'i `/Library/LaunchDaemons` altına yerleştirmek (yazma için root gerekir) her açılışta root olarak kod çalıştırmayı sağlar. Kullanıcı düzeyinde persistence için `~/Library/LaunchAgents` kullanılır ve buraya yazmak root bile gerektirmez.

Persistence için kötüye kullanılan diğer meşru mekanizmalar: login items, configuration profiles (MDM benzeri), cron/`at` (giderek daha az), belirli sistem servislerinin plugin dizinleri ve kabuk profil dosyaları.

### Saldırgan Perspektifi (Kavramsal)

Saldırgan kod çalıştırma (execution) elde ettikten sonra, kalıcılık için tipik olarak `LaunchAgents`/`LaunchDaemons`'a bir plist bırakır. Root varsa daemon, yoksa agent tercih edilir. Meşru görünen bir isim ve `com.apple.` gibi taklit label'lar kullanmak tespitten kaçınma amacı taşır.

### Tespit ve Savunma

- **Plist dizinlerini izleyin:** `/Library/LaunchDaemons`, `/Library/LaunchAgents`, `~/Library/LaunchAgents` ve sistem karşılıklarındaki yeni/değişen plist'leri FSEvents/EndpointSecurity ile alarma bağlayın. Yeni bir persistence noktası en değerli tespit sinyallerinden biridir.
- **`ProgramArguments` içeriğine bakın:** Plist'in çalıştırdığı yürütülebilirin konumu (kullanıcı yazılabilir bir dizinde mi?), imzalı mı, bilinen bir üründen mi geldiği önemlidir. `/tmp`, home altındaki gizli dizinler veya imzasız binary'ler kırmızı bayraktır.
- **Baseline oluşturun:** Temiz bir filoda beklenen tüm launch item'ları bir referans (allowlist) olarak tutun; sapmaları araştırın.
- **Login items ve profilleri de kapsayın:** Persistence sadece launchd değildir; configuration profiles ve login items da izlenmelidir.

## Yaygın Hatalar ve Yanlış Anlamalar

- **"root oldum, her şeyi yapabilirim" varsayımı:** Modern macOS'ta root, SIP ve TCC duvarlarına takılır. Root'u savunmanın sonu sanmak yanlıştır; asıl mesele bu ek katmanların durumudur.
- **TCC'yi sadece diyalog kutusu sanmak:** TCC bir veritabanı ve politika sistemidir. FDA/Accessibility gibi izinler bir kez verildiğinde geniş yetki taşır; bunları envanterlemeyen ekipler en kritik saldırı yüzeyini görmez.
- **Code signing'i "var/yok" ikili durumu sanmak:** Önemli olan sadece imzalı olup olmaması değil; **kimin** imzaladığı (Team ID), notarize edilip edilmediği, iptal durumu ve taşıdığı **entitlements**'tır. Geçerli imza her zaman güvenli demek değildir.
- **Entitlements'ı görmezden gelmek:** Çoğu savunma ekibi entitlements'a hiç bakmaz. Oysa `disable-library-validation` gibi tek bir anahtar, meşru bir uygulamayı saldırgan için ideal bir taşıyıcı haline getirir.
- **Quarantine'e fazla güvenmek:** Karantina bayrağı bazı teslim yollarında hiç oluşmaz. "Gatekeeper zaten korur" varsayımı, bayrağın olmadığı senaryolarda geçersizdir.
- **Persistence'i sadece cron/login item'da aramak:** macOS'ta persistence'in kalbi `launchd`'dir; plist dizinlerini izlemeyen bir tespit stratejisi eksiktir.
- **Windows/Linux telemetrisini yeterli sanmak:** EDR'niz macOS için EndpointSecurity framework'ünü kullanmıyorsa, yukarıdaki olayların çoğunu göremezsiniz. macOS görünürlüğü ayrı bir yatırımdır.

## Savunma İçin Öncelik Sırası (Özet)

1. **Görünürlük kurun:** EndpointSecurity tabanlı telemetri; process yürütme, dosya olayları, TCC.db erişimi, launch item oluşturma.
2. **Envanter çıkarın:** FDA/Accessibility izinleri, tehlikeli entitlements taşıyan binary'ler, tüm persistence noktaları.
3. **Sertleştirin:** SIP'i zorunlu tutun, Terminal'e FDA vermekten kaçının, allowlisting ve PPPC profilleriyle merkezi kontrol kurun.
4. **Güncel kalın:** SIP/TCC/Gatekeeper bypass'larının ezici çoğunluğu OS güncellemeleriyle kapanır; yama gecikmesi en büyük tek risktir.
5. **Baseline + sapma:** Temiz durumu referans alın, sapmaları olay olarak işleyin.

## Kapanış

macOS güvenliği, tek bir root kontrolüne değil, birbirinden bağımsız katmanlara (SIP, TCC, code signing, entitlements, Gatekeeper) dayanır. Saldırganların modern hedefi çoğu zaman "root olmak" değil, bu katmanları tek tek aşındırmaktır; en sık yol da **zaten yetkili meşru bir bileşeni devralmaktır**. Savunma tarafında kazanan yaklaşım, her katmanın durumunu görünür kılmak, güçlü izinleri ve tehlikeli entitlements'ları envanterlemek, launchd tabanlı persistence'i izlemek ve OS'u güncel tutmaktır. Bu makaledeki mekanizmaları doğru kavramak, macOS filosunu Windows ve Linux ile eşit derinlikte savunabilmenin ön koşuludur.
