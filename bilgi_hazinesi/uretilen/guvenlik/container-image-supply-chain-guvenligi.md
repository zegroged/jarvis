# Container Image Supply Chain Güvenliği: SBOM, İmza ve Provenance

## Giriş: Neden Bu Konu Ayrı Bir Başlıktır

CI/CD supply chain güvenliği genel başlık altında konuşulduğunda genellikle pipeline yapılandırması, secrets yönetimi ve build sunucusu izolasyonu ele alınır. Ancak bunun bir alt katmanı vardır ve o katman kendine has araç ekosistemi, tehdit modeli ve savunma pratikleriyle ayrı bir uzmanlık alanı oluşturur: **container image'in kendisinin bütünlüğü ve kökeni**.

Bir organizasyon build sunucusunu ne kadar iyi izole ederse izole etsin, eğer üretilen container image'in içinde ne olduğunu bilmiyorsa (SBOM eksikliği), o image'in gerçekten kendi pipeline'ından gelip gelmediğini doğrulayamıyorsa (imza eksikliği) ve o image'in hangi kaynak kod, hangi build adımları, hangi builder ile üretildiğini kanıtlayamıyorsa (provenance/attestation eksikliği), o zaman "güvenli CI/CD" iddiası boş bir iddiadır. SolarWinds vakası (2020) sanayiye net bir ders verdi: saldırgan build sürecinin içine sızıp meşru bir imzalı binary'nin içine kötü amaçlı kod enjekte edebildi ve bu binary müşteri ortamlarına "güvenilir" olarak dağıtıldı. Bu olay sonrasında ABD Başkanlık kararnamesi (EO 14028) ve NIST SSDF gibi çerçeveler SBOM'u ve imza doğrulamasını fiilen endüstri standardı haline getirdi. Kubernetes ve container ekosisteminde bu, Sigstore/Cosign ve SLSA çerçevesi etrafında somutlaştı.

Bu makale, container image'in "inşa edilmesinden" (build) "çalıştırılmasına" (runtime deploy) kadar olan zincirde hangi güven boşluklarının oluştuğunu, bunların nasıl kapatıldığını ve kapatılmadığında neyin yanlış gidebileceğini derinlemesine ele alır.

## Tehdit Modeli: Supply Chain'de Nerede Kırılır

Bir container image'in yaşam döngüsünü şu aşamalara ayıralım: kaynak kod -> bağımlılıklar (dependencies) -> build (derleme/paketleme) -> registry'ye push -> registry'den pull -> cluster'da çalıştırma (runtime). SLSA çerçevesi bu zinciri "source", "build", "dependencies" ve "artifact" olarak kategorize eder ve her aşamada farklı bir saldırgan profili tanımlar:

1. **Kaynak kod seviyesinde tehdit**: Bir geliştiricinin hesabı ele geçirilir veya kötü niyetli bir katkıda bulunan (malicious insider/contributor) repo'ya doğrudan zararlı kod ekler. Kod inceleme (code review) süreci bunu yakalayamazsa, zararlı kod meşru bir commit olarak build'e girer.
2. **Bağımlılık seviyesinde tehdit**: Dependency confusion, typosquatting veya ele geçirilmiş bir upstream paket (bkz. `event-stream`, `ua-parser-js`, `xz-utils/liblzma` gibi geçmiş vakalar) üzerinden zararlı kod, doğrudan sizin kodunuza dokunulmadan projeye girer. Bu, "sizin yazmadığınız ama sizin image'inizde çalışan kod" problemidir.
3. **Build seviyesinde tehdit**: Build sunucusunun kendisi ele geçirilir (örneğin CI runner'da zayıf izolasyon, önce çalışan bir job'ın sonraki job'u zehirlemesi - "poisoned pipeline execution") ve build çıktısına, kaynak kodda hiç olmayan bir kod enjekte edilir. SolarWinds tam olarak bu katmanda gerçekleşti: kaynak kod deposu temizdi, ama build süreci sırasında enjeksiyon oldu.
4. **Artifact/dağıtım seviyesinde tehdit**: Build doğru ve temiz olsa bile, registry'ye push edilen image ile kullanıcının pull ettiği image aynı mı? Registry ele geçirilip image değiştirilebilir mi (image tampering)? Bir "confused deputy" saldırısıyla farklı bir image, aynı tag altında mı servis ediliyor (tag mutability sorunu)?

Bu dört katmanın her biri için farklı bir savunma mekanizması gerekir: kod için imzalı commit'ler ve branch protection; bağımlılık için SBOM ve zafiyet tarama; build için izole/hermetic build ortamları ve provenance üretimi; dağıtım için ise **kriptografik imza** ve **admission control** ile doğrulama zorunluluğu.

## SBOM: Software Bill of Materials

### Tanım ve Kök Neden

SBOM, bir yazılım artifact'ının (burada: container image) içinde hangi bileşenlerin (paketler, kütüphaneler, işletim sistemi paketleri, dil-spesifik bağımlılıklar) hangi sürümlerde bulunduğunun makine-okunabilir envanteridir. En yaygın formatlar SPDX (Linux Foundation kökenli) ve CycloneDX'tir (OWASP kökenli).

Kök neden şudur: bir container image, genellikle taban imaj (base image) + işletim sistemi paketleri + dil paket yöneticisi (npm, pip, maven, go modules) bağımlılıkları + uygulamanın kendi kodunun katmanlarından oluşur. Bu katmanların her biri kendi bağımlılık ağacına sahiptir ve derinlik genellikle onlarca-yüzlerce transitive (dolaylı) bağımlılığa ulaşır. Log4Shell (Log4j zafiyeti, CVE-2021-44228) sonrasında ortaya çıkan gerçek problem, şirketlerin "log4j'i nerede kullanıyoruz?" sorusuna hafta süren manuel araştırmalarla cevap verebilmesiydi -- çünkü hiçbir yerde bu envanterin makine-okunabilir bir kaydı yoktu. SBOM olmadan bir CVE duyurusuna tepki süresi, ölçek büyüdükçe doğrusal değil üssel olarak kötüleşir.

### Nasıl Üretilir (Kavramsal)

SBOM üretimi iki temel yaklaşımla yapılır:

- **Build-time üretim**: Build süreci sırasında kullanılan her paket yöneticisi çağrısı izlenir ve bağımlılık ağacı doğrudan build araçlarından çıkarılır (örneğin Maven/Gradle/npm lock dosyalarından). Bu yaklaşım en doğru sonucu verir çünkü "gerçekte ne indirildi" bilgisine build sisteminin kendisi sahiptir.
- **Image tarama (post-build) üretimi**: Zaten oluşturulmuş bir image'in dosya sistemi katmanları taranarak (paket veritabanları, dil-spesifik manifest dosyaları, binary imza desenleri okunarak) bağımlılık listesi çıkarılır. Bu yöntemin en bilinen açık kaynak aracı **Syft**'tir; Syft bir image'i veya dosya sistemini tarayıp SPDX/CycloneDX formatında SBOM üretir.

İki yaklaşım da tek başına yeterli değildir: build-time SBOM, build sonrası image'e sonradan eklenen veya değiştirilen bir dosyayı yakalayamayabilir; tarama-tabanlı SBOM ise bazı dil ekosistemlerinde (statik link edilmiş binary'ler, gömülü/vendored kod) görünürlüğü kaybedebilir. Olgun bir pipeline ikisini birleştirir.

### SBOM Doğrulama ve Zafiyet Eşleştirme

SBOM tek başına bir envanterdir, güvenlik kontrolü değildir. Değeri, bir zafiyet veritabanına (NVD, OSV, vendor-spesifik feed'ler) karşı sürekli eşleştirilmesinden gelir. Bu iş için **Grype** gibi araçlar SBOM'u (veya doğrudan image'i) girdi olarak alıp bilinen CVE'lerle eşleştirir ve severity/etkilenen sürüm bilgisiyle rapor üretir.

**Tespit**: CI pipeline'ında "SBOM üret -> zafiyet tara -> policy eşiğini uygula (örneğin critical severity varsa build'i durdur)" adımı olmayan bir pipeline, zafiyetli bir bağımlılığın production'a kadar gitmesine izin verir. Registry tarafında da image'lar periyodik olarak yeniden taranmalıdır çünkü bir image build edildiğinde temiz olabilir ama sonradan yeni bir CVE açıklanabilir (bu, "geçmişe dönük zafiyet" - retroactive vulnerability durumudur). Bu yüzden SBOM arşivlenmeli ve zafiyet veritabanı güncellendikçe mevcut SBOM'lara karşı yeniden sorgulanabilmelidir; her seferinde image'i yeniden taramaya gerek kalmaz.

**Yaygın hata**: SBOM'u sadece "compliance kutusu işaretlemek" için üretip hiçbir zaman okunmayan bir dosya olarak arşivlemek. SBOM'un değeri aktif kullanımda: yeni bir CVE duyurulunca "hangi image'lerimiz etkileniyor" sorusuna dakikalar içinde cevap verebilmektir. İkinci yaygın hata, SBOM'u yalnızca işletim sistemi paket seviyesinde üretip dil-spesifik (npm/pip/go) katmanı atlamaktır -- oysa gerçek dünyada zafiyetlerin büyük kısmı uygulama seviyesi bağımlılıklardan gelir.

## İmzalama: Sigstore/Cosign ve Notary v2

### Tanım ve Kök Neden

SBOM "içinde ne var" sorusunu cevaplar; imzalama ise "bu image gerçekten iddia ettiği yerden mi geldi, değiştirildi mi" sorusunu cevaplar. Kök neden, container registry'lerin varsayılan olarak bütünlük garantisi vermemesidir: bir registry'ye kim push edebiliyorsa, aynı tag'i (örneğin `myapp:latest`) başka bir içerikle değiştirebilir; registry'nin kendisi ele geçirilirse (veya registry ile kullanıcı arasındaki aktarım manipüle edilirse) kullanıcı farklı bir image'i "orijinal" sanıyor olabilir. TLS, aktarım sırasındaki bütünlüğü korur ama "registry'deki içeriğin doğru yayıncı tarafından onaylandığını" kanıtlamaz -- bu farklı bir garanti katmanıdır ve dijital imza gerektirir.

Geleneksel imzalama modelleri (örneğin Notary v1/TUF tabanlı Docker Content Trust) uzun süreli anahtar yönetimi gerektirir: özel anahtar güvenli şekilde saklanmalı, rotasyon yapılmalı, sızıntı durumunda iptal (revocation) mekanizması çalışmalıdır. Bu operasyonel yük, pratikte pek çok organizasyonun imzalamayı hiç devreye almamasına yol açtı.

**Sigstore** projesi (Cosign, Fulcio, Rekor bileşenlerinden oluşur) bu problemi "keyless signing" (anahtarsız imzalama) modeliyle çözmeyi hedefler:

- **Fulcio**: Kısa ömürlü (short-lived), OpenID Connect (OIDC) kimlik doğrulamasına bağlanmış sertifikalar veren bir Certificate Authority'dir. Kullanıcı/CI sistemi bir OIDC sağlayıcısı (örneğin GitHub Actions'ın kendi OIDC token'ı, Google) üzerinden kimliğini kanıtlar, Fulcio buna karşılık dakikalar süren geçerlilikte bir imzalama sertifikası verir. Uzun süreli özel anahtar saklama ihtiyacı ortadan kalkar.
- **Rekor**: Değiştirilemez (append-only) bir şeffaflık günlüğüdür (transparency log, Certificate Transparency mantığının benzeri). Her imzalama işlemi burada zaman damgalı olarak kayıt altına alınır; bu sayede "bu imza gerçekten o tarihte, o kimlikle atıldı" sonradan kanıtlanabilir ve inkar edilemez (non-repudiation) hale gelir.
- **Cosign**: Bu ekosistemi kullanan komut satırı aracı; image'i imzalar, imzayı registry'ye (OCI artifact olarak) veya Rekor'a yazar, doğrulama tarafında ise "bu image şu public key / şu OIDC kimliğiyle imzalanmış mı" kontrolünü yapar.

**Notary v2 / Notation** ise CNCF ekosisteminde OCI spesifikasyonuna daha doğrudan entegre, PKI-tabanlı (geleneksel sertifika zinciri) bir alternatif olarak gelişti; kurumsal PKI altyapısı olan organizasyonlar için daha tanıdık bir model sunar.

### Nasıl Çalışır (Kavramsal Akış) ve Tespit

İmzalama akışı kabaca şöyledir: build tamamlanır -> image'in içerik-adresli hash'i (digest, örneğin sha256) hesaplanır -> bu digest imzalanır (anahtar veya keyless sertifika ile) -> imza, image'in yanında (registry'de ayrı bir OCI artifact olarak veya Rekor gibi harici bir log'da) saklanır. Kritik nokta: **imza tag'i değil digest'i imzalar**. Tag (`v1.2.3`, `latest`) değiştirilebilir bir işaretçi olduğu için güven temeli olamaz; digest ise içeriğin kriptografik özeti olduğundan tek bir byte değişse tamamen farklı bir digest üretir.

**Tespit ve doğrulama tarafı**: Deploy zamanında (örneğin Kubernetes admission controller seviyesinde - Kyverno, Sigstore'un kendi policy-controller'ı, veya OPA/Gatekeeper) her pull edilen image'in imzası doğrulanmalıdır: "bu digest, beklenen imzalayıcı kimliğiyle (belirli bir OIDC identity, belirli bir key) imzalanmış mı?" Bu kontrol başarısız olursa pod'un oluşturulması reddedilmelidir (fail-closed). Rekor gibi bir şeffaflık günlüğü kullanılıyorsa, ayrıca "bu imza gerçekten log'da var mı, sonradan uydurulmuş mu" da doğrulanabilir -- bu, bir saldırganın sadece bir anahtar çalarak sessizce imza üretmesini zorlaştırır çünkü imza kamuya açık, değiştirilemez bir kayıt bırakır.

**Yaygın hatalar**:
- İmzalamayı yapıp **doğrulamayı zorunlu kılmamak**: Cosign ile image'lar imzalanıyor ama cluster'da hiçbir admission policy bu imzayı kontrol etmiyor. Bu durumda imzalama sadece "teorik" bir kontrol olur, saldırgan imzasız bir image'i rahatlıkla deploy edebilir.
- **Tag'i imzalamak/doğrulamak, digest'i değil**: Tag mutable olduğu için bu yaklaşım TOCTOU (time-of-check to time-of-use) benzeri bir boşluk yaratır -- doğrulama anındaki tag ile pull anındaki tag farklı içeriğe işaret edebilir.
- Özel anahtar tabanlı (keyed) imzalamada anahtarın CI değişkenlerinde açık metin saklı tutulması; bu, anahtar tabanlı modelin tam önlemeye çalıştığı zayıflıktır ve keyless modelin popülerleşmesinin ana sebeplerinden biridir.
- İmza doğrulamasını yalnızca CI/CD pipeline içinde yapıp **runtime/cluster seviyesinde tekrarlamamak**: bir image CI'da doğrulanıyor olsa bile, birisi registry'den doğrudan farklı/imzasız bir image pull edip cluster'a deploy edebiliyorsa, kontrol nokta atlanmış olur. Savunma "defense in depth" ile hem CI'da hem admission control'de tekrarlanmalıdır.

## Provenance ve SLSA Çerçevesi

### Tanım ve Kök Neden

İmzalama "kim imzaladı" sorusuna cevap verir ama tek başına "hangi kaynak koddan, hangi build talimatlarıyla, hangi ortamda üretildi" sorusuna cevap vermez -- bir saldırgan meşru imzalama kimliğini ele geçirirse (örneğin CI sistemine sızarak), meşru görünen ama zararlı bir image'i meşru imzayla imzalatabilir. Bu tam olarak SolarWinds senaryosudur: imzalama alt yapısı vardı, ama build sürecinin kendisi güvenilir değildi.

**Provenance** (köken bilgisi), bir artifact'ın nasıl üretildiğine dair yapılandırılmış, doğrulanabilir metadata'dır: hangi kaynak kod commit'i, hangi build tanımı (pipeline yaml'ı), hangi builder (hangi CI sistemi, hangi sürüm), hangi girdi parametreleriyle bu çıktıyı üretti. **Attestation**, bu provenance bilgisinin kriptografik olarak imzalanmış halidir -- yani "bu iddiayı ben (belirli bir builder kimliği) atıyorum ve imzalıyorum" şeklinde kanıtlanabilir bir beyandır. In-toto ve SLSA'nın kullandığı attestation formatı (`in-toto` statement formatı) bu amaca hizmet eder.

**SLSA (Supply-chain Levels for Software Artifacts)**, bu provenance garantisinin olgunluğunu kademeli seviyelerle tanımlayan bir çerçevedir (Google kökenli, sonra OpenSSF/CNCF şemsiyesine taşındı). Mantık kabaca şöyledir:

- **Düşük seviye**: Provenance üretiliyor ama otomatik/doğrulanmış değil; build süreci elle veya güvenilir olmayan bir ortamda çalışıyor olabilir.
- **Orta seviye**: Provenance otomatik olarak, build sisteminin kendisi tarafından üretiliyor ve imzalanıyor; böylece "birisi provenance'i sonradan uydurdu" riski azalıyor.
- **Yüksek seviye**: Build, **hermetic** (ağ erişimi build sırasında kısıtlı, tüm girdiler önceden bildirilmiş) ve **izole** (bir build'in bir diğerini etkileyememesi, "poisoned pipeline" riskinin azaltılması) bir ortamda gerçekleşiyor; provenance'in sahteciliği (forgery) pratik olarak build sisteminin kendisini ele geçirmeden mümkün değil.

Kök neden, seviyeler arttıkça "saldırganın sahte provenance üretebilmesi için ne kadar derine inmesi gerektiği" artmasıdır -- en üst seviyede saldırganın build platformunun altyapısını ele geçirmesi gerekir, bu da tek bir CI job'unu ele geçirmekten çok daha zordur.

### Nasıl Çalışır (Kavramsal) ve Tespit

Pratikte provenance üretimi build sistemi tarafından otomatik yapılır (örneğin GitHub Actions'ın kendi native attestation özelliği, veya SLSA generator araçlarıyla): build tamamlanınca "bu digest, şu repo/commit'ten, şu workflow tanımından, şu builder'da üretildi" şeklinde bir attestation oluşturulur ve Sigstore/Rekor gibi bir mekanizmayla imzalanıp yayınlanır.

**Tespit/doğrulama**: Deploy öncesi veya admission control seviyesinde sadece imza değil, provenance da politika motoruna sorulabilir: "bu image, beklenen repo'dan mı geldi? Beklenen workflow dosyasıyla mı build edildi? Bilinmeyen/onaylanmamış bir fork'tan gelen bir build mi?" Bu, özellikle **tedarik zinciri saldırılarında "doğru görünen ama farklı yerden gelen" imajları** yakalamada kritik bir katmandır. Örneğin bir saldırgan CI/CD yapılandırmasında küçük bir değişiklik yaparak (bir pull request aracılığıyla, "poisoned pipeline execution" tekniğinin bir varyantı) build script'ine zararlı bir adım eklerse, imzalama tek başına bunu yakalayamaz (çünkü meşru pipeline meşru anahtar ile imzalar), ama provenance doğrulaması "bu build beklenen workflow tanımından saptı mı" sorusunu sorabilirse riski azaltır -- tabii provenance içeriği workflow tanımını da kapsıyorsa.

**Yaygın hatalar**:
- Provenance'i üretip hiç doğrulamamak (SBOM'daki aynı hata deseni burada tekrarlanıyor: üretim var, tüketim/kontrol yok).
- Build ortamını hermetic yapmadan yüksek SLSA seviyesi iddia etmek: eğer build sırasında internetten rastgele script indirilebiliyorsa ("curl | bash" desenleri), provenance "hangi girdilerle üretildi" konusunda eksik/yanlış bir tablo çizer -- çünkü build'in gerçek girdisi sadece deklare edilen kaynak kod değil, indirilen ek script de olmuş olur.
- Provenance doğrulamasını yalnızca "var mı yok mu" şeklinde yapıp içeriğini (beklenen repo, beklenen builder kimliği) kontrol etmemek; bu, "birisi herhangi bir provenance üretti, demek ki güvenli" gibi yanlış bir güvenlik hissi (false sense of security) yaratır.

## Bütün Zincirin Birlikte Çalışması ve Savunma Mimarisi

Bu üç mekanizma (SBOM, imza, provenance) birbirini tamamlar, birbirinin yerine geçmez:

- SBOM olmadan: bir CVE açıklandığında hangi image'lerin etkilendiğini bilemezsiniz (görünürlük sorunu).
- İmza olmadan: bir image'in gerçekten iddia edilen kaynaktan geldiğini kanıtlayamazsınız (kimlik/bütünlük sorunu).
- Provenance olmadan: imzalayan kimlik meşru olsa bile, o kimliğin *nasıl* bir build süreciyle bu çıktıyı ürettiğini bilemezsiniz (süreç bütünlüğü sorunu).

Olgun bir savunma mimarisi bu üçünü de pipeline'ın doğal bir parçası haline getirir ve en kritik olarak **tüketim tarafında zorunlu kılar**:

1. Build aşamasında: SBOM üret (Syft benzeri), zafiyet tara (Grype benzeri), eşik aşılırsa build'i durdur.
2. İmzalama aşamasında: image digest'ini imzala (Cosign/keyless), provenance/attestation üret ve ekle.
3. Registry aşamasında: mümkünse tag immutability (tag'in sonradan değiştirilememesi) zorunlu kılınsın.
4. Deploy aşamasında: admission controller seviyesinde imza doğrulaması, provenance/builder kimliği kontrolü ve güncel SBOM'a göre açık kritik zafiyet kontrolü **fail-closed** olarak uygulansın -- yani doğrulama başarısız olursa varsayılan davranış "reddet" olmalı, "izin ver ve logla" değil.
5. Runtime sonrası: SBOM arşivi periyodik olarak yeni CVE feed'lerine karşı yeniden sorgulanmalı; bu, "geçmişte temiz olan ama bugün zafiyetli hale gelen" image'leri yakalamanın tek yolu.

## Sonuç

Container image supply chain güvenliğinin özü, "bu image'i çalıştırdığımızda ne çalışıyor, kim üretti, nasıl üretti" sorularına makine-doğrulanabilir, sahtesi zor cevaplar verebilmektir. SBOM görünürlük katmanıdır, imza kimlik/bütünlük katmanıdır, provenance/SLSA ise süreç güveni katmanıdır. Bu üçünün herhangi biri eksik olduğunda zincirde bir kör nokta kalır ve SolarWinds tarzı saldırılarda tam olarak istismar edilen şey bu kör noktalardır. Savunma tarafında en önemli ilke, bu kontrollerin sadece "üretilmesi" değil, deploy zincirinin en az bir noktasında (tercihen admission control seviyesinde) **zorunlu doğrulanması**dır -- aksi halde en iyi tasarlanmış SBOM/imza/provenance altyapısı bile sadece kağıt üzerinde var olan bir güvenlik teatrosuna dönüşür.
