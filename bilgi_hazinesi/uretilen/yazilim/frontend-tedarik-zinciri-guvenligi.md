# Frontend Tedarik Zinciri Güvenliği

## Giriş ve Tanım

Modern bir frontend uygulaması, geliştiricinin yazdığı kodun çok ötesinde bir yapıdır. Tipik bir `node_modules` klasörü binlerce transitive (dolaylı) bağımlılık içerir; tarayıcıda çalışan `bundle.js` dosyanız onlarca farklı yazarın kodunu birleştirir. **Software Supply Chain Security** (yazılım tedarik zinciri güvenliği), uygulamanızın nihai haline katkıda bulunan her adımı — paket kayıt defterleri (registry), CDN'ler, build araçları, CI/CD pipeline'ları — bir güven zinciri olarak ele alır ve bu zincirin herhangi bir halkasının ele geçirilme riskini yönetir.

Frontend'in bu konudaki özgün durumu şudur: yazdığınız kod **kullanıcının tarayıcısında**, sizin kontrolünüzdeki sunucunun dışında çalışır. Bu, zincire sızan zararlı kodun doğrudan son kullanıcının oturumunda — kredi kartı formunun, oturum token'ının, DOM'un yanı başında — çalışması demektir. Backend'de bir supply chain saldırısı sunucunuzu ele geçirir; frontend'de ise her ziyaretçinin tarayıcısını potansiyel bir hedefe dönüştürür.

Bu makale zincirin dört kritik halkasını inceler: paket kayıt defteri saldırıları (typosquatting, dependency confusion, hesap ele geçirme), CDN riskleri ve Subresource Integrity ile savunma, build-time enjeksiyon saldırıları ve genel tespit/savunma stratejileri.

## Neden Frontend'e Özgü ve Ayrı Bir Risk?

Prototype Pollution, XSS veya CSRF gibi zafiyetler **sizin yazdığınız kodun** hatalarıdır. Tedarik zinciri saldırıları ise farklı bir tehdit modelidir: kod mükemmel yazılmış olsa bile, **güvendiğiniz üçüncü taraf** kötü niyetli veya ele geçirilmiş olabilir. Buradaki fark savunma yaklaşımını tamamen değiştirir — kendi kodunuzu denetlemek yetmez, güvendiğiniz herkesi denetlemeniz gerekir.

Frontend ekosisteminin bu saldırılara özellikle açık olmasının yapısal nedenleri var:

- **Aşırı derin bağımlılık ağaçları:** Küçük bir React uygulaması bile 1000+ paket çekebilir. `left-pad` olayı, tek satırlık bir paketin kaldırılmasının binlerce projeyi kırdığını göstermişti — bu bağımlılık yoğunluğunun bir kanıtıdır.
- **Otomatik güncelleme kültürü:** `^1.2.3` gibi semver aralıkları, siz farkında olmadan yeni sürümlerin çekilmesine izin verir. Ele geçirilen bir paketin yeni sürümü, bir sonraki `npm install`'da otomatik gelebilir.
- **Install-time script çalıştırma:** npm paketleri `postinstall` gibi lifecycle hook'larla, siz kodu import etmeden bile, kurulum anında geliştirici makinesinde veya CI'da kod çalıştırabilir.
- **Tarayıcıya doğrudan teslim:** Build çıktısı denetimsiz olarak son kullanıcıya gider.

## Paket Kayıt Defteri Saldırıları

### Typosquatting

**Tanım:** Saldırgan, popüler bir paketin adına çok benzeyen bir isimle (`crossenv` yerine `cross-env`, `lodash` yerine `1odash`) zararlı bir paket yayınlar. Yazım hatası yapan veya kopyala-yapıştır sırasında karakteri karıştıran geliştirici, farkında olmadan zararlı paketi kurar.

**Çalışma mantığı:** İnsan hatası saldırının motorudur. Bilinen kalıplar şunlardır: harf değişimi (`react` → `raect`), tire ekleme/çıkarma (`node-fetch` → `nodefetch`), scope taklidi (`@company/utils` yerine public `company-utils`), yaygın typo'lar (`babel` → `bable`). Zararlı paket genellikle gerçek paketin işlevini de kopyalar (böylece kurulum "çalışıyor" görünür) ama arka planda `postinstall` script'i ile veri sızdırır.

**Tespit:** Kurulumdan önce paket adını gerçek olanla karakter karakter karşılaştırın. `npm install`'da paketin haftalık indirme sayısına, yayın tarihine ve yazarına bakın — meşru bir paketin milyonlarca indirmesi varken taklit çok düşük sayıda olur. Bağımlılık ekleyen PR'lar mutlaka insan gözüyle incelenmelidir.

### Dependency Confusion

**Tanım:** Bir organizasyon, kendi private registry'sinde `@sirket/internal-tool` gibi dahili bir paket barındırır. Saldırgan aynı isimde bir paketi **public** npm registry'sine, daha yüksek bir sürüm numarasıyla yayınlar. Yanlış yapılandırılmış bir paket yöneticisi "en yüksek sürüm" mantığıyla public'teki zararlı paketi çeker.

**Kök neden:** Paket yöneticisi birden fazla kaynağı sorguladığında, hangi kaynağın öncelikli olduğu net değilse, çoğu zaman en yüksek semver sürümü kazanır. Public registry herkese açık olduğundan saldırgan istediği kadar yüksek sürüm (`99.0.0`) yayınlayabilir. Bu saldırı vektörü Alex Birsan tarafından kamuoyuna duyurulduğunda birçok büyük şirketin dahili paket isimlerinin public'te "rezerve edilmemiş" olduğu görüldü.

**Savunma:**
- **Scope kullanımı:** Tüm dahili paketleri `@sirket/` scope'u altına alın ve bu scope'u registry'nizle eşleyin (`.npmrc` içinde `@sirket:registry=https://internal.registry`).
- **İsim rezervasyonu:** Dahili paket isimlerini public registry'de placeholder olarak rezerve edin (saldırganın alamaması için).
- **Lockfile ve integrity:** `package-lock.json`/`yarn.lock` her paketin tam kaynağını ve integrity hash'ini sabitler. Lockfile'a bağlı kalmak (`npm ci`) beklenmedik kaynak değişimini engeller.

### Hesap Ele Geçirme ve Bakımcı Devri (event-stream vakası)

**Tanım:** Meşru, popüler bir paketin **kendisi** ele geçirilir. Saldırgan bakımcının npm hesabını çalar (phishing, sızmış şifre) veya sosyal mühendislikle bakım yetkisini devralır, sonra paketin yeni bir sürümüne zararlı kod ekler.

**Klasik örnek — event-stream:** Yaygın kullanılan `event-stream` paketinin bakımını sürdürmeye vakti kalmayan orijinal geliştirici, gönüllü olan bir kişiye yetkiyi devretti. Yeni "bakımcı" önce zararsız katkılar yaptı, güven kazandıktan sonra `flatmap-stream` adlı yeni bir bağımlılık ekledi. Bu bağımlılık, yalnızca **belirli bir kripto cüzdan uygulamasının** build ortamında aktifleşen, kod obfuscation ile gizlenmiş, özel anahtarları çalmayı hedefleyen bir payload içeriyordu. Payload hedef dışındaki ortamlarda hiçbir şey yapmadığından uzun süre fark edilmedi.

**Bu vakadan çıkarılan dersler:**
- Güven **statik değildir**. Bugün güvenli bir paketin bakımcısı yarın değişebilir.
- Zararlı payload **koşullu ve hedefli** olabilir; genel testlerde görünmez.
- Transitive bağımlılıklar (bağımlılığın bağımlılığı) çoğu zaman hiç incelenmez; asıl risk oradadır.
- Obfuscation, minified koda gömülen zararlı yükün gözden kaçmasını sağlar.

**Savunma:**
- **Lockfile'ı sabitle:** `npm ci` yeni sürümleri otomatik çekmez, tam olarak lockfile'daki sürümü kurar.
- **Yayın gecikmesi (cooldown):** Yeni yayınlanan bir sürümü hemen değil, birkaç gün bekledikten sonra alan politikalar, tespit edilmiş zararlı sürümlerin kaldırılmasına zaman tanır.
- **Bakımcı değişikliği izleme:** Kritik bağımlılıkların bakımcı listesindeki değişiklikleri takip etmek, event-stream tipi devirleri erken yakalar.

## CDN Riskleri ve Subresource Integrity (SRI)

### CDN Neden Bir Risktir?

Bir script'i `<script src="https://cdn.example.com/lib.js">` şeklinde harici bir CDN'den yüklediğinizde, o CDN'e **tam güven** vermiş olursunuz. Eğer:

- CDN ele geçirilirse,
- CDN hesabınız çalınırsa,
- DNS veya BGP hijacking ile trafik başka bir sunucuya yönlendirilirse,
- CDN'deki dosya sessizce değiştirilirse (versiyonsuz URL kullanıyorsanız),

o CDN, kullanıcılarınızın tarayıcısında **istediği JavaScript'i** çalıştırabilir. Sayfanız ne kadar güvenli olursa olsun, harici tek bir `<script>` etiketi bu güveni delebilir. Magecart tipi saldırılarda bu yöntemle e-ticaret sitelerine kart çalan kod enjekte edilmiştir.

### Subresource Integrity (SRI) — Çalışma Mantığı

**Tanım:** SRI, harici bir kaynağın (script veya stylesheet) beklenen içeriğinin **kriptografik hash**'ini HTML'e gömme mekanizmasıdır. Tarayıcı dosyayı indirdikten sonra hash'ini hesaplar; beklenen hash ile eşleşmezse dosyayı **çalıştırmayı reddeder**.

```html
<script
  src="https://cdn.example.com/library@1.2.3.js"
  integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC"
  crossorigin="anonymous"></script>
```

**Nasıl çalışır:**
1. `integrity` özniteliği, dosyanın SHA-256/384/512 hash'ini base64 kodlu olarak taşır.
2. Tarayıcı dosyayı indirir, aynı algoritmayla hash'ini hesaplar.
3. Hesaplanan hash `integrity` değeriyle **birebir** eşleşmezse tarayıcı kaynağı yüklemez, konsola hata basar.
4. `crossorigin="anonymous"` özniteliği, CORS gereği SRI kontrolünün yapılabilmesi için genellikle zorunludur.

Böylece CDN'deki dosya bir bayt bile değişirse (zararlı kod enjekte edilirse), hash değişir ve tarayıcı çalıştırmayı reddeder. SRI, güveni "CDN'e güven"den "içeriğe güven"e taşır.

### SRI'nin Sınırları ve Tuzakları

SRI güçlü ama sihirli değildir; sınırlarını bilmek şart:

- **Sabit sürüm gerektirir:** SRI ancak dosya içeriği değişmezse işe yarar. `library@latest` gibi otomatik güncellenen bir URL kullanırsanız, meşru bir güncelleme bile hash'i bozar ve sayfanız kırılır. SRI, **sürümü sabitlemeye** zorlar — bu aslında bir güvenlik avantajıdır.
- **Yalnızca script ve link:** SRI `<script>` ve `<link rel="stylesheet">` için tanımlıdır. Görseller, `fetch`, dinamik `import()` gibi durumları kapsamaz.
- **Zincirleme yükleme problemi:** SRI ile doğruladığınız script kendi içinde başka bir script'i dinamik olarak yüklerse, o ikinci script SRI kapsamı dışındadır. Doğrulanan script'in "temiz" olması bunu telafi eder ama dolaylı güven zinciri devam eder.
- **Hash güncelleme yükü:** Her sürüm değişiminde hash'i manuel güncellemek gerekir; bu genellikle build aracına otomatikleştirilir.
- **Yaygın hata:** `crossorigin` özniteliğini unutmak. CDN uygun CORS başlığı döndürmezse tarayıcı integrity kontrolünü yapamaz ve kaynak bloklanabilir.

**En güvenli uygulama:** Kritik üçüncü taraf script'leri mümkünse CDN yerine kendi build'inize dahil edin (self-host / bundle). Böylece kaynak sizin CI/CD ve integrity kontrolünüzden geçer. CDN kullanımı kaçınılmazsa mutlaka SRI + sabit sürüm + `crossorigin` kullanın.

### Content Security Policy (CSP) ile Katmanlı Savunma

CSP, hangi kaynaklardan script yüklenebileceğini kısıtlayan bir HTTP başlığıdır. SRI "içerik doğru mu?" sorusuna, CSP "bu kaynağa izin var mı?" sorusuna cevap verir. İkisi birlikte kullanıldığında güçlü bir katman oluşur: CSP `script-src` direktifi ile yalnızca güvendiğiniz origin'lere izin verirsiniz; `require-sri-for` (destek durumu değişkendir) gibi mekanizmalarla SRI'yi zorunlu kılabilirsiniz. CSP ayrıca beklenmedik bir origin'e veri sızdırma girişimini de (`connect-src`) sınırlar.

## Build-time Supply Chain Saldırıları

### Tanım ve Tehdit Yüzeyi

En tehlikeli halkalardan biri **build zamanıdır**. Modern frontend build'i (Webpack, Vite, Rollup, esbuild) yüzlerce plugin, loader ve bağımlılık çalıştırır. Bu araçların ve npm lifecycle script'lerinin hepsi, build makinesinde (geliştirici laptopu veya CI runner) **tam yetkiyle kod çalıştırır**. Zararlı bir bağımlılık, tarayıcıya giden nihai bundle'a fark edilmeden kod enjekte edebilir veya build ortamındaki secret'ları çalabilir.

**Saldırı yüzeyleri:**
- **npm lifecycle script'leri:** `preinstall`, `install`, `postinstall`. Bunlar `npm install` anında otomatik çalışır. Zararlı bir paket burada ortam değişkenlerini (`process.env` içindeki API anahtarları, tokenlar) sızdırabilir.
- **Build plugin'leri:** Ele geçirilmiş bir Webpack/Vite plugin'i, üretilen bundle'a analytics kılığında bir keylogger ekleyebilir. Kaynak kodunuzda görünmez, çünkü enjeksiyon derleme sırasında yapılır.
- **CI/CD ortamı:** CI runner'ları genellikle deployment credential'ları, imzalama anahtarları ve registry token'ları barındırır. Build sürecine sızan kod bu sırları hedef alır.

### Örnek Senaryo (kavramsal)

Bir geliştirici popüler bir build plugin'inin ele geçirilmiş sürümünü çeker. Plugin'in `postinstall` script'i çalışır, CI ortamındaki `NPM_TOKEN` ve `AWS_ACCESS_KEY` değerlerini uzak bir sunucuya gönderir. Aynı zamanda plugin, build sırasında bundle'a bir satır ekler: sayfadaki form gönderimlerini dinleyip saldırganın sunucusuna kopyalayan bir kod. Kaynak repository'de hiçbir değişiklik yoktur, code review bir şey yakalamaz, çünkü kötü kod `node_modules` içinde ve nihai `dist/` çıktısındadır. Bu, event-stream mantığının build katmanına taşınmış halidir.

### Savunma ve Sertleştirme

- **Lifecycle script'leri kısıtla:** `npm install --ignore-scripts` (veya yarn/pnpm eşdeğerleri) install-time script çalışmasını engeller. CI'da güvenilmeyen bağımlılıklar için bunu değerlendirin; bazı paketlerin çalışmak için script'e ihtiyacı olduğundan bilinçli izin listesi (allowlist) yaklaşımı tercih edilir.
- **En az yetkili CI:** Build runner'ına yalnızca gereken minimum secret'ı verin. Deployment credential'larını build aşamasından ayrı, ayrıcalıklı bir aşamaya taşıyın. Secret'ları kısa ömürlü tutun.
- **İzole ve tekrarlanabilir build:** Build'i konteyner içinde, ağ erişimi kısıtlı, ephemeral (tek kullanımlık) ortamda çalıştırın. Beklenmedik outbound bağlantıları (veri sızdırma) tespit etmek için ağ trafiğini izleyin.
- **Deterministik build ve doğrulama:** Reproducible build'ler, aynı girdiden aynı çıktının üretildiğini garanti eder; beklenmedik bir çıktı farkı enjeksiyon işareti olabilir.
- **SBOM (Software Bill of Materials):** Build çıktısına dahil olan tüm bileşenlerin envanterini (CycloneDX/SPDX formatı) üretin. Bir zafiyet açıklandığında etkilenip etkilenmediğinizi hızlıca görürsünüz.
- **Pinned tooling:** Build araçlarının ve container image'larının sürümlerini digest ile sabitleyin (`node:20@sha256:...`), tag'e güvenmeyin.

## Tespit ve Genel Savunma Stratejisi

### Otomatik Denetim Araçları

- **`npm audit` / `yarn audit`:** Bağımlılıklarınızı bilinen zafiyet veritabanlarıyla karşılaştırır. Faydalı ama sınırlı: yalnızca **bilinen** (açıklanmış) zafiyetleri yakalar, sıfır-gün typosquatting'i değil. Ayrıca false positive üretebilir; her uyarının exploit edilebilirliği ayrı değerlendirilmelidir.
- **SCA (Software Composition Analysis) araçları:** Snyk, Dependabot, Renovate gibi araçlar bağımlılıkları sürekli tarar, zafiyet bildirimlerini ve otomatik güncelleme PR'larını yönetir.
- **Lockfile denetimi:** Lockfile değişikliklerini code review'da özel dikkatle inceleyin. Beklenmedik bir yeni transitive bağımlılık veya kaynak URL değişimi kırmızı bayraktır.

### Süreçsel Savunmalar

- **`npm ci` kullanın:** Development'ta `npm install` lockfile'ı değiştirebilir; CI'da `npm ci` kesinlikle lockfile'a sadık kalır, deterministik kurulum sağlar.
- **Bağımlılık ekleme disiplini:** Her yeni bağımlılık bir güven kararıdır. "Bu paketi gerçekten kendim yazamaz mıyım?" sorusu, `left-pad` tipi gereksiz bağımlılıkları eler. Bağımlılık sayısını azaltmak saldırı yüzeyini azaltır.
- **Sürüm sabitleme:** Kritik bağımlılıklarda `^` yerine tam sürüm (`1.2.3`) veya lockfile disiplini kullanın.
- **Cooldown politikası:** Yeni yayınlanan sürümleri hemen production'a almayın; olgunlaşma süresi tanıyın.
- **Vendoring:** En kritik bağımlılıkları kendi repository'nize kopyalayarak (vendor) registry'ye olan runtime bağımlılığını kesebilirsiniz.

### Runtime Tespiti

Frontend özelinde, çalışan sayfada beklenmedik davranışları izlemek son savunma hattıdır:

- **CSP raporlama:** `report-uri`/`report-to` ile CSP ihlallerini toplayın; beklenmedik bir origin'e giden istek (veri sızdırma) burada görünür.
- **Beklenmedik network isteği izleme:** Sayfanızın normalde konuşmadığı bir sunucuya giden istekler Magecart tipi saldırının işaretidir.
- **Bundle diffing:** Her deploy'da üretilen bundle'ı önceki sürümle karşılaştırıp beklenmedik kod eklenmesini tespit etmek.

## Yaygın Hatalar (Özet)

- **CDN script'ini SRI olmadan kullanmak:** Harici script'e kör güven; CDN ele geçirilirse tüm kullanıcılar etkilenir.
- **`latest` veya geniş semver aralığı kullanmak:** Otomatik güncelleme, ele geçirilen bir sürümü sessizce production'a taşır.
- **Lockfile'ı commit etmemek veya `npm install`'ı CI'da kullanmak:** Deterministik olmayan, öngörülemez kurulum.
- **`postinstall` script'lerine sorgusuz izin vermek:** Kurulum anında kod çalışmasının riskini görmezden gelmek.
- **Transitive bağımlılıkları hiç incelememek:** Asıl risk çoğu zaman doğrudan değil, bağımlılığın bağımlılığındadır.
- **Dahili paket isimlerini public'te rezerve etmemek:** Dependency confusion'a açık kapı.
- **CI runner'ına gereğinden fazla secret vermek:** Build'e sızan kodun ganimetini büyütür.
- **`npm audit` temiz diye rahatlamak:** Audit yalnızca bilinen zafiyetleri görür; typosquatting ve sıfır-gün'ü kaçırır.

## Sonuç

Frontend tedarik zinciri güvenliği, "kendi kodum güvenli mi?" sorusundan "güvendiğim herkes güvenli mi?" sorusuna geçiştir. Zincirin dört halkası — registry, CDN, build, deployment — her biri ayrı bir güven kararı ve ayrı bir savunma gerektirir. Temel prensipler tekrarlanabilir: **güveni sabitle** (lockfile, sürüm, SRI hash), **güveni doğrula** (integrity, SBOM, audit), **yetkiyi kısıtla** (least privilege CI, ignore-scripts), ve **davranışı izle** (CSP raporlama, network monitoring). Tek bir araç yeterli değildir; katmanlı savunma (defense in depth) esastır. event-stream, dependency confusion ve Magecart vakalarının ortak dersi nettir: güven statik değildir, sürekli doğrulanması gerekir.
