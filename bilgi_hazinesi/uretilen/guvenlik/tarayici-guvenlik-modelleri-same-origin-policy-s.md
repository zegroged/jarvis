# Tarayıcı Güvenlik Modelleri: Same-Origin Policy, Sandboxing, Site Isolation

## Giriş: Neden Bu Konu Ayrı Ele Alınmalı

Web güvenliği literatüründe genellikle uygulama katmanı zafiyetleri (XSS, CSRF, CORS yanlış yapılandırması) öne çıkar; bunlar önemlidir ama hepsi aslında tarayıcının sunduğu **temel izolasyon garantilerinin** üzerine inşa edilir. CORS'un "neden" var olduğunu, bir `postMessage` mesajının neden tehlikeli olabileceğini veya bir iframe'in neden bazı işlemleri yapamadığını anlamak için önce tarayıcının çekirdek izolasyon modelini -- Same-Origin Policy (SOP) -- ve bunun üzerine sonradan eklenen katmanları (sandboxing, process isolation, cross-origin isolation) kavramak gerekir. Bu makale, bir güvenlik mühendisinin "WAF kuralı yazmak" yerine "tarayıcı neden böyle davranıyor" sorusuna cevap bulmasını hedefler.

## Same-Origin Policy (SOP): Kök Mekanizma

### Tanım ve Origin Kavramı

**Origin** (köken), bir kaynağın kimliğini belirleyen üçlüdür: **scheme (protokol) + host (alan adı) + port**. `https://example.com:443` ile `http://example.com` farklı origin'lerdir (scheme farklı); `https://example.com` ile `https://api.example.com` farklı origin'lerdir (host farklı, subdomain dahi olsa); `https://example.com:8080` ile `https://example.com` farklı origin'lerdir (port farklı).

SOP'un temel kuralı basittir: **bir origin'deki script, başka bir origin'in verisine (DOM içeriği, cookie, localStorage, response body vb.) doğrudan erişemez.** Bu, tarayıcının 1990'ların ortasından beri taşıdığı ve tüm modern web güvenliğinin üzerine oturduğu bir izolasyon sözleşmesidir.

### Kök Neden: SOP Neden Var

Tarayıcı, kullanıcı adına aynı anda onlarca farklı güven seviyesindeki siteyi (bankanız, e-posta sağlayıcınız, rastgele bir haber sitesi, kötü niyetli bir reklam ağı) aynı process/bellek alanında (tarihsel olarak) çalıştırır. Eğer izolasyon olmasaydı, `kotu-site.com` üzerindeki bir script, aynı anda açık olan `banka.com` sekmesinin DOM'unu okuyabilir, cookie'lerini çalabilir veya form verilerini ele geçirebilirdi. SOP, "her origin kendi bahçesinde oynar" ilkesini uygulayarak bunu engeller.

SOP'un kapsamı üç ana etkileşim türünü kısıtlar:

1. **DOM erişimi**: `window.open()` ile açılan farklı origin'deki bir pencerenin `document`'ına erişim engellenir.
2. **XMLHttpRequest / fetch**: Farklı origin'e yapılan istekler varsayılan olarak engellenir (CORS bunu gevşetmek için var olan bir istisna mekanizmasıdır).
3. **Cookie/storage erişimi**: `localStorage`, `sessionStorage`, `IndexedDB` origin bazlı izole edilir (cookie'ler ise tarihsel nedenlerle *domain* bazlı çalışır, bu da SOP'tan farklı ve daha gevşek bir modeldir -- `Domain=example.com` bir cookie'yi tüm subdomain'lere yayabilir).

### SOP'un Kapsamadığı Şeyler (Yaygın Yanlış Anlama)

SOP, **her şeyi** engellemez. Şu üç şey SOP dışında kalır ve genellikle kafa karışıklığına yol açar:

- **Cross-origin script/CSS/image dahil etme (`<script src>`, `<img src>`, `<link>`)**: Bu kaynaklar dahil edilebilir; sadece içerikleri okunamaz. Bu yüzden `<script src="https://evil.com/x.js">` çalışır -- bu web'in temel çalışma mantığıdır (CDN'ler bu sayede işler) ama aynı zamanda tedarik zinciri saldırılarının da temelidir.
- **Form gönderimi**: Bir form başka bir origin'e `POST` yapabilir; yanıtı okuyamasa da işlem gerçekleşir. Bu, CSRF'in kök nedenidir.
- **Navigasyon**: `window.location` değiştirilerek başka bir origin'e yönlendirme yapılabilir.

Bu üç istisna, "SOP veri okumayı engeller ama işlemi (side-effect) engellemez" ilkesini gösterir -- CSRF, clickjacking gibi saldırı sınıflarının kavramsal kökeni tam olarak buradadır.

## postMessage Güvenliği

### Çalışma Mantığı

Farklı origin'ler arasında **meşru** iletişim gerektiğinde (örneğin bir iframe ile onu barındıran sayfa arasında veri aktarımı), `window.postMessage(message, targetOrigin)` API'si SOP'u kontrollü şekilde delen resmi bir kanaldır. Gönderen taraf hedef origin'i belirtir, alıcı taraf ise `message` event handler'ında gelen mesajın kaynağını (`event.origin`) doğrulamakla yükümlüdür.

### Kök Neden / Yaygın Hata

`postMessage` API'sinin tehlikesi, **tarayıcının alıcı adına doğrulama yapmamasıdır** -- doğrulama sorumluluğu tamamen uygulama koduna bırakılmıştır. İki klasik hata:

1. **`event.origin` kontrolünün eksik veya gevşek olması**: Geliştirici `if (event.origin.indexOf("example.com") > -1)` gibi bir substring kontrolü yazarsa, `evil-example.com` veya `example.com.evil.com` gibi origin'ler bu kontrolü geçer. Doğru yaklaşım tam eşitlik (`===`) veya bir izin listesiyle karşılaştırmadır.
2. **`targetOrigin` olarak `"*"` kullanımı**: Gönderen taraf mesajı herhangi bir origin'e gönderirse (`postMessage(data, "*")`), eğer iframe/pencere navigasyonla başka bir origin'e yönlendirilmişse (veya saldırgan `window.open` ile araya girmişse) hassas veri yanlış alıcıya sızabilir.

### Tespit ve Savunma

- **Kod incelemesinde** her `message` event listener'ında `event.origin` kontrolünün varlığını ve tam eşleşme mantığını doğrulayın; regex kullanılıyorsa `^https://example\.com$` gibi çapalanmış (anchored) ifadeler olmalı.
- **`postMessage` çağrılarında** `targetOrigin` parametresinin `"*"` olmadığını, açık bir origin string'i olduğunu doğrulayın.
- Statik analiz araçlarıyla (semgrep vb.) `addEventListener("message", ...)` kalıplarını tarayıp origin kontrolü olmayanları işaretlemek pratik bir tespit yöntemidir.
- Gelen mesaj verisinin **yapısını da** doğrulayın (`event.data` içeriğinin beklenen şema ile uyuşması) -- origin doğru olsa bile veri güvenilir formatta olmayabilir.

## Iframe Sandbox Özniteliği

### Tanım ve Çalışma Mantığı

`<iframe sandbox>` özniteliği, gömülü içeriğe normalde tarayıcının verdiği bir dizi yeteneği **varsayılan olarak kapatan** bir kısıtlama mekanizmasıdır. Boş `sandbox=""` en kısıtlayıcı moddur: script çalıştırma, form gönderme, popup açma, üst çerçeveye (top-level) navigasyon, aynı origin muamelesi görme gibi yetenekler kapanır. İhtiyaç duyulan yetenekler token'larla tek tek geri açılır:

- `allow-scripts`: JavaScript çalıştırmaya izin verir.
- `allow-same-origin`: Iframe içeriğinin kendi origin'i ile aynı origin muamelesi görmesine (dolayısıyla kendi cookie/storage'ına erişmesine) izin verir.
- `allow-forms`, `allow-popups`, `allow-top-navigation` vb.

### Kök Neden: Neden Var

Üçüncü taraf içerik (reklamlar, kullanıcı tarafından oluşturulan HTML önizlemeleri, ödeme widget'ları) barındıran siteler, bu içeriğin ana sayfanın güvenlik bağlamına sızmasını istemez. Sandbox, iframe'i **kendi origin'inden bile daha kısıtlı** bir "opak origin" (her yüklemede benzersiz, boş bir origin) olarak ele alarak, script çalışsa bile üst sayfaya veya kalıcı depolamaya zarar verme yeteneğini keser.

### Yaygın Hata: `allow-scripts` + `allow-same-origin` Birlikte Kullanımı

Bu, sandbox öznitelğinin en bilinen zayıf noktasıdır. Tek başına her ikisi de güvenlidir, ama **birlikte** kullanıldığında sandbox'ın kendisini etkisiz kılan bir kaçış yolu doğar: `allow-same-origin` iframe'e kendi gerçek origin'i olarak DOM erişim hakkı verirken, `allow-scripts` script çalıştırmaya izin verir. Script, `allow-same-origin` sayesinde artık kendi origin'inin çerçevesi içinde çalıştığından, sandbox'ın attribute'unu DOM üzerinden manipüle ederek (örneğin üst çerçeveye kendi iframe elementinin `sandbox` özniteliğini kaldıracak bir istek) veya doğrudan kendi origin ayrıcalıklarını kullanarak kısıtlamaları fiilen aşabilir. Kısacası bu iki flag'in kombinasyonu, "scripti çalıştır ama izole tut" amacını büyük ölçüde geçersiz kılar.

### Tespit ve Savunma

- Kod/konfigürasyon taramasında `sandbox` özniteliği içinde **aynı anda** `allow-scripts` ve `allow-same-origin` geçen iframe'leri işaretleyin; bu genellikle bilinçsiz bir yapılandırma hatasıdır.
- Güvenilmeyen içerik için mümkün olduğunca **ayrı bir origin** (örneğin `usercontent.example.com` gibi bir "sandbox domain") kullanmak, `allow-same-origin` ihtiyacını tamamen ortadan kaldırır çünkü izolasyon zaten SOP seviyesinde sağlanır.
- `allow-top-navigation` ve `allow-popups` gibi nadiren gerekli yetenekleri varsayılan olarak kapalı tutun; her token'ı "neden gerekli" sorusuyla gerekçelendirin.

## CORS: Kısa Hatırlatma ve Bu Makaledeki Yeri

CORS (Cross-Origin Resource Sharing), SOP'un XMLHttpRequest/fetch kısıtlamasını **sunucunun izniyle** gevşeten bir mekanizmadır (`Access-Control-Allow-Origin` header'ı ile). Burada derinlemesine işlenmiyor çünkü CORS yanlış yapılandırması ayrı bir konu olarak zaten kapsanmış durumda; ancak kavramsal olarak önemli olan şu: CORS, SOP'u **iptal etmez**, sadece sunucu tarafının açıkça izin verdiği durumlarda tarayıcıya "bu yanıtı JavaScript'in okumasına izin ver" der. SOP hâlâ varsayılan davranıştır; CORS bir istisna kapısıdır.

## COOP, COEP, CORP: Cross-Origin Isolation

Bu üç header, tarayıcının 2018 sonrası (Spectre açıklamasından sonra) geliştirdiği, process-level izolasyonu güçlendiren bir header ailesidir.

### CORP (Cross-Origin-Resource-Policy)

Bir kaynağın (resim, script, font vb.) **başka origin'ler tarafından gömülmesini** kısıtlayan response header'ıdır. `Cross-Origin-Resource-Policy: same-origin` denirse, kaynak sadece kendi origin'inden yüklenebilir; `same-site` biraz daha gevşektir (aynı site, farklı subdomain'e izin verir). Bu, side-channel saldırılarda (örneğin bir resmin varlığını/boyutunu ölçerek bilgi sızdırma) kaynağın izinsiz gömülmesini engelleyen bir savunma katmanıdır.

### COEP (Cross-Origin-Embedder-Policy)

Bir **sayfanın**, gömdüğü tüm cross-origin kaynakların açıkça izin vermesini (CORP header'ı veya CORS ile) zorunlu kılan header'dır. `Cross-Origin-Embedder-Policy: require-corp` ayarlandığında, sayfa CORP/CORS ile işaretlenmemiş hiçbir cross-origin kaynağı yükleyemez. Bu, sayfanın kendi güvenlik bağlamını "sıkılaştırmasına" izin veren bir öz-disiplin mekanizmasıdır.

### COOP (Cross-Origin-Opener-Policy)

Bir pencerenin, açtığı veya kendisini açan diğer pencerelerle **aynı browsing context group** içinde paylaşılmasını engelleyen header'dır. `Cross-Origin-Opener-Policy: same-origin` ayarlandığında, farklı origin'den açılan bir pencere artık `window.opener` referansı üzerinden bu pencereye erişemez ve tarayıcı bu iki pencereyi **ayrı process'lere** yerleştirebilir.

### Kök Neden: Neden Bu Üçü Birlikte Gerekli

Spectre, process içindeki **farklı origin'lere ait belleğin aynı adres alanında bulunmasını** side-channel timing saldırılarıyla istismar eden bir donanım zafiyeti sınıfıdır (spekülatif yürütme). Yazılım seviyesinde bunu tam kapatmak mümkün olmadığından, tarayıcıların savunma stratejisi **farklı origin'lerin verisini aynı process'e hiç koymamak** oldu -- yani process isolation. Ancak bir sayfanın gerçekten kendi process'inde "izole" sayılabilmesi için, o process'e giren hiçbir cross-origin verinin sızıntı riski taşımaması gerekir. COOP+COEP birlikte etkinleştirildiğinde tarayıcı sayfayı **"cross-origin isolated"** kabul eder ve bunun karşılığında `SharedArrayBuffer`, yüksek çözünürlüklü `performance.now()` gibi Spectre için özellikle riskli, hassas timing API'lerini tekrar kullanıma açar (bu API'ler Spectre sonrası varsayılan olarak kısıtlanmış veya çözünürlüğü düşürülmüştü).

Yani mantık zinciri şöyle işler: Spectre → process içi izolasyon garantisi zayıflar → tarayıcı hassas API'leri varsayılan kapatır → geliştirici bu API'lere ihtiyaç duyarsa COOP+COEP ile "gerçekten izole olduğumu kanıtlıyorum" der → tarayıcı buna güvenip API'leri geri açar.

### Tespit ve Savunma

- `crossOriginIsolated` global boolean'ı (JavaScript'te `self.crossOriginIsolated`) sayfanın gerçekten izole modda çalışıp çalışmadığını runtime'da doğrulamak için kullanılabilir; güvenlik testlerinde bu değerin beklenen durumla eşleştiğini kontrol edin.
- Response header taramasında COOP/COEP/CORP header'larının varlığını ve değerlerini (`same-origin`, `require-corp` vb.) otomatik denetleyin; özellikle `SharedArrayBuffer` kullanan uygulamalarda bu header'ların eksikliği API'nin çalışmamasına (fonksiyonel hata) veya yanlışlıkla gevşek bırakılmasına (güvenlik açığı) yol açar.
- CORP'u tüm statik kaynaklarda (özellikle CDN'den servis edilenlerde) varsayılan politika haline getirmek, ileride COEP gerektiren bir özellik eklendiğinde "kırık" entegrasyonları önler.

## Site Isolation: Process Sınırında Savunma

### Kavramsal Çalışma Mantığı

Site Isolation, tarayıcının **her farklı site'ı (eTLD+1 -- effective top-level domain + 1, örn. `example.com`) ayrı bir işletim sistemi process'inde çalıştırması** ilkesidir. Modern çok işlemli (multi-process) tarayıcı mimarilerinde bu, SOP'un yazılım seviyesindeki mantıksal izolasyonunu, işletim sisteminin sağladığı **donanım destekli process izolasyonuyla** güçlendirir: bir process'in belleğine başka bir process doğrudan erişemez (MMU/sayfa tablosu sınırları sayesinde).

Bunun önemi şuradan gelir: SOP salt yazılımsal bir kuraldır -- tarayıcı motorunda bir bellek okuma zafiyeti (örneğin bir renderer engine bug'ı) varsa, aynı process içinde başka origin'lerin verisi teoride okunabilir olurdu. Site Isolation, bu riski "aynı process'te birden fazla origin'in hassas verisi hiç bulunmasın" ilkesiyle mimari düzeyde azaltır. Böylece bir sitedeki JavaScript motoru zafiyeti istismar edilse bile, saldırgan sadece kendi process'inin belleğine erişebilir; başka bir origin'in (banka sitesi gibi) verisi fiziksel olarak o process'te bulunmaz.

### Spectre ile İlişkisi

Spectre öncesinde process isolation zaten savunma amaçlı vardı (bug/crash izolasyonu, kararlılık). Spectre sonrasında önemi katlanarak arttı çünkü **spekülatif yürütme side-channel'ları process sınırlarını aşamaz** (aşabildiği durumlar ayrı ve daha karmaşık senaryolardır) -- yani Site Isolation, Spectre'ın "aynı process içindeki farklı origin verisini okuma" riskine karşı en pratik yazılım-mimarisi savunmasıdır. Bu yüzden büyük tarayıcı motorları Site Isolation'ı varsayılan olarak devreye almış ve önceliklendirmiştir.

### Tespit ve Savunma (Mühendis/Savunmacı Perspektifi)

Site Isolation büyük ölçüde tarayıcı tarafında yönetilen bir özelliktir; uygulama geliştiricisi/güvenlik mühendisi için buradaki sorumluluk şudur:

- **Enterprise ortamlarda** tarayıcı politikalarının (grup politikası / yönetilen tarayıcı ayarları) Site Isolation'ı devre dışı bırakmadığından emin olun -- bazı eski/uyumluluk odaklı kurumsal ayarlar performans kaygısıyla bunu kapatabilir, bu da savunma katmanını tamamen kaldırır.
- Uygulama tarafında Site Isolation'ın etkinliğini **artıran** en önemli katkı, doğru COOP/COEP/CORP header'larını göndermektir -- bu header'lar tarayıcıya izolasyon sınırlarını netleştirir ve bazı ek izolasyon optimizasyonlarının (örneğin belirli process paylaşım kararlarının) doğru verilmesini sağlar.
- Güvenlik değerlendirmelerinde "tarayıcı sürüm politikası" bir kontrol maddesi olmalı: güncel tarayıcı sürümleri kullanmak, sadece bilinen CVE'leri kapatmakla kalmaz, Site Isolation gibi mimari savunmaların en son iyileştirmelerinden (örneğin daha granüler process ayrımı) faydalanmayı sağlar.

## Yaygın Hatalar: Özet

1. **CORS'u SOP'un yerine geçen bir güvenlik kontrolü sanmak**: CORS bir gevşetme mekanizmasıdır, SOP'un kendisi değildir; `Access-Control-Allow-Origin: *` ile hassas, kimlik doğrulamalı endpoint'leri açmak klasik bir hatadır.
2. **`postMessage` alıcı tarafında origin kontrolünü atlamak veya gevşek (substring) yapmak.**
3. **Iframe sandbox'ta `allow-scripts` ve `allow-same-origin`'i birlikte, gerekçesiz kullanmak.**
4. **Cookie izolasyonunu origin izolasyonuyla karıştırmak**: Cookie'ler domain bazlıdır (subdomain'ler arası paylaşılabilir), SOP ise origin (scheme+host+port) bazlıdır -- bu fark, subdomain devralma (subdomain takeover) senaryolarında kritik hale gelir.
5. **COOP/COEP eklemeden `SharedArrayBuffer` veya yüksek hassasiyetli timing API bekleyip "neden çalışmıyor" diye şaşırmak** -- bu aslında tarayıcının kasıtlı Spectre savunmasıdır, bug değildir.
6. **Site Isolation'ın "her şeyi otomatik hallettiği" varsayımıyla uygulama seviyesi izolasyon header'larını (COOP/COEP/CORP) hiç düşünmemek** -- process isolation ve header tabanlı izolasyon birbirini tamamlar, biri diğerinin yerini almaz.

## Sonuç

SOP, tarayıcı güvenliğinin temel taşıdır ve ondan sonra gelen her mekanizma (CORS, postMessage, sandbox, COOP/COEP/CORP, Site Isolation) ya SOP'u kontrollü şekilde gevşetir ya da SOP'un yazılımsal doğasını donanım/mimari düzeyde güçlendirir. Bir güvenlik mühendisi için pratik çıkarım şudur: her yeni "cross-origin izin veren" mekanizma eklerken (CORS header'ı, postMessage kanalı, sandbox token'ı) "bu izin SOP'un hangi garantisini deliyor ve karşılığında hangi doğrulamayı üstleniyorum" sorusunu sormak; her izolasyon header'ı (COOP/COEP/CORP) eklerken de "bu, tarayıcının bana sunduğu process-level savunmayı nasıl güçlendiriyor" sorusunu sormak gerekir. Tespit tarafında ise bu kontrollerin **varlığını ve doğru yapılandırıldığını** otomatik taramalarla (header denetimi, sandbox attribute analizi, postMessage origin kontrolü statik analizi) sürekli doğrulamak, tek seferlik bir "audit" değil, CI/CD içine gömülü kalıcı bir kontrol olmalıdır.
