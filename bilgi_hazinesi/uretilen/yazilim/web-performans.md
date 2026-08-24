# Web Performans Optimizasyonu

Web performansı, bir sayfanın kullanıcının ekranında ne kadar hızlı görünür, kullanılabilir ve tepkisel hâle geldiğini belirleyen mühendislik disiplinidir. Sadece "site hızlı açılsın" isteğinden çok daha derindir: tarayıcının bir URL'yi işleyip pikselleri ekrana boyayana kadar geçirdiği her aşamayı (ağ, çözümleme/parse, render, script yürütme, layout, paint) anlayıp bu aşamalardaki gecikmeleri sistematik olarak ölçmek ve azaltmaktır. Bu makale dört ana eksene odaklanır: **critical rendering path** (kritik oluşturma yolu), **lazy loading** (tembel yükleme), **caching** (önbellekleme) ve **Core Web Vitals** ölçütleri. Amaç kuru bir kontrol listesi vermek değil; neden bu tekniklerin işe yaradığını, tarayıcının içinde ne olduğunu ve nerelerde yanılgıya düşüldüğünü akıl yürüterek göstermektir.

## Neden performans bir mimari meselesidir

Performans, çoğu zaman "en sona bırakılan" bir optimizasyon zannedilir; oysa yükleme davranışı mimarinin kendisiyle iç içedir. Bir sayfanın ilk boyanma hızı; hangi kaynağın ne zaman istendiğine, hangi script'in render'ı bloklayıp bloklamadığına, verinin nereden (edge, origin, cache) geldiğine bağlıdır. Bu kararlar HTML/CSS/JS yazılırken alınır, sonradan "sıkıştırıp küçültmekle" tam olarak telafi edilemez.

Kök neden şu: tarayıcı tek bir ana thread (main thread) üzerinde hem JavaScript'i çalıştırır hem de layout ve paint işlemlerini yapar. Bu thread meşgulse kullanıcı etkileşimleri (tıklama, kaydırma) gecikir. Aynı şekilde ağ katmanında her kaynak için latency (RTT — round trip time) ödenir. Dolayısıyla performansın iki temel düşmanı vardır: **ana thread'in bloklanması** ve **gereksiz/sıralı ağ istekleri**. Optimizasyon tekniklerinin hemen hepsi bu iki köke iner.

## Critical Rendering Path (Kritik Oluşturma Yolu)

### Tanım ve çalışma mantığı

Critical rendering path, tarayıcının aldığı HTML, CSS ve JavaScript'i alıp ilk anlamlı pikseli ekrana boyayana kadar izlediği adımlar zinciridir. Kabaca şu sırayla ilerler:

1. **HTML parse → DOM**: Tarayıcı HTML byte akışını okurken bir DOM (Document Object Model) ağacı kurar.
2. **CSS parse → CSSOM**: CSS indirilip CSSOM (CSS Object Model) ağacına dönüşür.
3. **Render tree**: DOM ve CSSOM birleşerek gerçekten görünecek elemanların ağacı oluşur (`display: none` olanlar dışarıda kalır).
4. **Layout (reflow)**: Her elemanın ekrandaki geometrisi (konum, boyut) hesaplanır.
5. **Paint**: Pikseller katmanlara boyanır.
6. **Composite**: Katmanlar birleştirilip ekrana basılır.

Buradaki kritik kavram şu: **CSS, render-blocking bir kaynaktır.** Tarayıcı CSSOM tamamlanmadan render tree'yi kuramaz, çünkü bir elemanın nasıl görüneceğini (hatta görünüp görünmeyeceğini) bilmeden onu boyamak yanlış olur. Benzer şekilde, **script'ler varsayılan olarak parser-blocking'tir**: `<script>` etiketiyle karşılaşan parser, script indirilip yürütülene kadar DOM inşasını durdurur, çünkü script `document.write` yapabilir veya DOM'u değiştirebilir.

### Kök neden: neden senkron script HTML'i durdurur

Bunun mantığı, tarayıcının garanti veremeyeceği bir belirsizliktir. Parser, `<script>` gördüğünde script'in DOM'a ne yapacağını önceden bilemez. Script indirilirken parse'a devam edip sonra script DOM'u bozarsa çelişki doğar. Bu yüzden güvenli varsayılan davranış "dur ve bekle"dir. Üstelik senkron script CSSOM'a da bağımlıdır: script `element.style` okuyabileceği için tarayıcı, bekleyen CSS varsa script'i CSSOM hazır olana dek geciktirir. Yani yanlış konumlanmış tek bir CSS + script kombinasyonu, ilk boyamayı ciddi biçimde geciktirebilir.

### Somut örnek

`<head>` içine konmuş büyük bir üçüncü parti analytics script'i düşünün:

```html
<head>
  <link rel="stylesheet" href="app.css">
  <script src="https://cdn.example.com/analytics.js"></script>
</head>
```

Burada tarayıcı `analytics.js`'i indirip çalıştırana kadar `<body>`'yi parse etmeye başlamaz bile. Kullanıcı boş ekrana bakar. Çözüm, script'in tarayıcıya nasıl davranacağını `async` veya `defer` ile bildirmektir:

```html
<script src="analytics.js" async></script>   <!-- indirme paralel, geldiği an çalışır -->
<script src="app.js" defer></script>          <!-- indirme paralel, DOM bitince sırayla çalışır -->
```

Aradaki fark önemlidir ve sık karıştırılır:

- **`async`**: Script arka planda indirilir, indiği an yürütülür — bu yüzden yürütme anı belirsizdir ve script'ler arası sıra garanti edilmez. Birbirinden bağımsız, DOM'a bağımlı olmayan script'ler (izleme kodu gibi) için uygundur.
- **`defer`**: Script arka planda indirilir ama yürütme, HTML parse tamamlandıktan sonra ve yazıldıkları **sırayı koruyarak** gerçekleşir. Uygulama kodu ve birbirine bağımlı script'ler için doğru seçimdir.

### Doğru kullanım ve tuzaklar

Kritik yolu kısaltmanın temel stratejileri şunlardır:

- **Critical CSS'i inline etmek**: Sayfanın ilk görünen kısmını (above-the-fold) boyamak için gereken minimum CSS'i doğrudan `<head>` içine `<style>` olarak gömmek, geri kalan CSS'i ise ertelemek. Böylece render'ı bloklayan ağ isteği ortadan kalkar. Tuzak: inline CSS önbelleklenemez, bu yüzden yalnızca gerçekten kritik olan küçük bir dilimi inline edin; tümünü gömmek her istekte HTML'i şişirir.
- **Kritik olmayan CSS'i ertelemek**: `media` niteliğiyle veya küçük bir script hile'siyle CSS'i render-blocking olmaktan çıkarmak.
- **Script'leri body sonuna almak veya defer kullanmak**: Böylece DOM inşası bloklanmaz.

En yaygın hata, "önce her şeyi indirsin, sonra göstersin" varsayımıdır. Modern tarayıcılar **incremental rendering** (aşamalı boyama) yapar; HTML akarken kısmi içeriği gösterebilir. Kritik yolu tıkayan bir kaynak bu aşamalılığı bozar. İkinci yaygın hata, üçüncü parti script'lerin ölçülmemesidir: kendi kodunuz kusursuz olsa bile senkron yüklenen bir widget tüm kazanımı silebilir.

## Lazy Loading (Tembel Yükleme)

### Tanım ve mantık

Lazy loading, bir kaynağın ancak gerçekten ihtiyaç duyulduğu anda — tipik olarak kullanıcının görüş alanına (viewport) yaklaştığında — yüklenmesidir. Kök mantık basittir: kullanıcı sayfanın çok altındaki bir görseli belki hiç görmeyecektir; onu ilk yüklemede indirmek hem bant genişliğini hem de kritik yolu boşuna meşgul eder. İlk yüklemede yalnızca gereken minimumu getirip gerisini talebe bağlı çekmek, hem ilk boyamayı hızlandırır hem de toplam veri transferini düşürür.

### Çalışma mantığı ve somut örnekler

Görseller için tarayıcı seviyesinde native destek vardır:

```html
<img src="urun.jpg" loading="lazy" width="800" height="600" alt="Ürün">
```

`loading="lazy"` niteliği, tarayıcıya görseli ancak viewport'a yaklaşınca indirmesini söyler. Buradaki kritik ama sık atlanan ayrıntı `width` ve `height` (veya CSS `aspect-ratio`) vermektir: boyut belirtilmezse görsel geç geldiğinde çevresindeki içeriği iterek layout shift yaratır — bu doğrudan Core Web Vitals'ı bozar.

JavaScript modülleri için lazy loading, **dynamic import** ile yapılır:

```javascript
button.addEventListener('click', async () => {
  const { openEditor } = await import('./editor.js');
  openEditor();
});
```

Burada ağır editör kodu, kullanıcı butona basana kadar hiç indirilmez. Bu, bundler'ların **code splitting** (kod bölme) yeteneğiyle birleşir: uygulama tek dev bir bundle yerine, gerektikçe yüklenen küçük parçalara (chunk) ayrılır.

Görsel dışı, viewport'a bağlı tembel yükleme için doğru araç **IntersectionObserver**'dır. Eski `scroll` olayını dinleyip pozisyon hesaplama yöntemi ana thread'i sürekli meşgul ettiği için hem yanlış hem yavaştır; IntersectionObserver bu gözlemi tarayıcıya, ana thread dışında yaptırır.

### Tuzaklar ve yaygın hatalar

- **Above-the-fold içeriği lazy yapmak**: İlk ekranda görünen ana görseli (özellikle LCP elemanını) `loading="lazy"` yapmak felakettir; tarayıcı onu geç keşfeder ve LCP kötüleşir. İlk ekrandaki kritik görsel **eager** yüklenmeli, hatta `fetchpriority="high"` ile önceliklendirilmelidir.
- **Boyut rezervasyonu yapmamak**: Yukarıda değinildiği gibi, yer ayırmadan lazy yüklemek layout shift üretir.
- **Aşırı bölme**: Kodu gereğinden fazla parçaya ayırmak, her etkileşimde yeni bir ağ isteği (ve yeni RTT) demektir. Sık kullanılan yolları eager tutmak, nadir yolları lazy yapmak dengesi kurulmalıdır.
- **SEO ve erişilebilirlik**: Kritik içeriğin yalnızca script çalışınca gelmesi, arama motorları veya JavaScript'i geç çalışan istemciler için içeriğin görünmemesine yol açabilir.

## Caching (Önbellekleme)

### Tanım ve neden en güçlü optimizasyon olduğu

Caching, bir kaynağı bir kez getirdikten sonra kopyasını saklayıp tekrar tekrar aynı ağ yolculuğunu ödememektir. Performansta çoğu zaman en yüksek getiriyi caching verir, çünkü **en hızlı istek, hiç yapılmayan istektir.** Bir dosya tarayıcı diskinden veya yakındaki bir edge sunucusundan geldiğinde, origin sunucuya gidip gelen yüzlerce milisaniyelik latency tamamen ortadan kalkar.

Önbellekleme birçok katmanda çalışır ve bunları karıştırmamak gerekir:

- **Browser cache (HTTP cache)**: Tarayıcının kendi diskinde tuttuğu kaynaklar.
- **CDN / edge cache**: Kullanıcıya coğrafi olarak yakın ara sunucularda tutulan kopyalar.
- **Application/data cache**: Sunucu tarafında hesaplanmış sonuçların veya sorgu çıktılarının tutulması.

### Çalışma mantığı: HTTP cache başlıkları

Tarayıcı önbelleğinin davranışını HTTP yanıt başlıkları belirler. En merkezî olanı `Cache-Control`'dür. Mantığı iki temel eksene ayrılır:

**1. Ne kadar süre taze (fresh) sayılacak?** `Cache-Control: max-age=<saniye>` ile tanımlanır. Bu süre içinde tarayıcı sunucuya hiç sormadan yerel kopyayı kullanır. `immutable` eklenirse tarayıcı, süre dolana kadar koşullu doğrulama bile denemez.

**2. Süre dolunca ne olacak?** Kaynak "bayat" (stale) hâle geldiğinde tarayıcı sunucuya bir **conditional request** (koşullu istek) yapar. Bunun için iki mekanizma vardır:

- **ETag / If-None-Match**: Sunucu kaynağa bir sürüm etiketi (ETag) verir. Tarayıcı tekrar sorarken bu etiketi `If-None-Match` ile gönderir. İçerik değişmediyse sunucu gövdesiz bir `304 Not Modified` döner — büyük dosya yeniden inmez, yalnızca küçük bir doğrulama yapılır.
- **Last-Modified / If-Modified-Since**: Aynı fikrin zaman damgası tabanlı sürümü.

### Kritik desen: content hashing ile "cache busting"

Buradaki en önemli ve en çok işe yarayan desen şudur: **değişmeyecek varlıkları çok uzun süre önbelleklerken, değiştiklerinde dosya adını değiştirmek.** Build aracı çıktı dosyasının adına içeriğinin hash'ini gömer:

```
app.9f8c2a1b.js
styles.4d7e0f33.css
```

Böylece bu dosyalara `Cache-Control: max-age=31536000, immutable` (bir yıl) verebilirsiniz; çünkü içerik değişirse dosya adı da (hash da) değişir ve tarayıcı bunu tamamen yeni bir kaynak olarak görüp indirir. Eski adı çağıran hiçbir şey kalmaz. Bu, "hem uzun cache hem anında güncelleme" ikilemini zarifçe çözer.

Peki bu dosyalara işaret eden HTML? HTML **kısa cache'lenmeli veya `no-cache` olmalıdır**, çünkü hash'li dosya adlarının yeni sürümlerini kullanıcıya bildiren yer HTML'dir. HTML bayatlarsa kullanıcı eski varlık adlarına takılı kalır.

### Somut örnek: no-cache ile no-store farkı

Bu ikisi sürekli karıştırılır ve anlamları çok farklıdır:

- **`no-cache`**: "Önbelleğe al, ama kullanmadan önce her seferinde sunucuya doğrulat." Yani kopya saklanır; conditional request ile taze olup olmadığı kontrol edilir. Değişmemişse 304 döner, hızlı olur.
- **`no-store`**: "Hiç saklama." Her seferinde tam yeniden indirme. Yalnızca gerçekten hassas, asla diskte tutulmaması gereken veriler için uygundur.

`no-cache` performans açısından `no-store`'dan çok daha iyidir; sık yapılan hata, "her zaman güncel olsun" niyetiyle `no-store` yazıp gereksiz tam indirmelere yol açmaktır.

### Yaygın hatalar

- **Versiyonlanmamış varlıklara uzun cache vermek**: `main.js` gibi sabit adlı bir dosyaya bir yıllık cache verirseniz, güncelleme yaptığınızda kullanıcılar eski sürümde takılı kalır. Bu klasik ve acı verici bir hatadır.
- **CDN cache ile browser cache'i karıştırmak**: Bir CDN kaynağı önbelleklediğinde, origin'de yaptığınız değişiklik CDN'i temizleyene (purge/invalidate) kadar yansımaz.
- **Kişiye özel içeriği yanlışlıkla paylaşımlı cache'e koymak**: Kullanıcıya özel yanıtları `public` işaretlemek, bir kullanıcının verisinin başkasına gösterilmesine yol açabilir. Kişisel yanıtlar `private` olmalıdır.
- **Vary başlığını unutmak**: İçerik `Accept-Encoding` veya dil gibi başlıklara göre değişiyorsa, `Vary` ile bunu belirtmemek yanlış varyantın sunulmasına neden olur.

## Core Web Vitals

### Tanım ve neden bu ölçütler seçildi

Core Web Vitals, Google'ın gerçek kullanıcı deneyimini ölçmek için standartlaştırdığı bir metrik kümesidir. Amaç, "sayfa yüklendi mi" gibi teknik ama kullanıcıyı yansıtmayan olaylar yerine, kullanıcının *hissettiği* üç boyutu ölçmektir: **ne zaman içerik görünür oldu, ne zaman etkileşimli oldu, görünüm ne kadar kararlı kaldı.** Üç temel metrik şunlardır:

- **LCP — Largest Contentful Paint (En Büyük İçerikli Boyama)**: Viewport'taki en büyük içerik öğesinin (genellikle ana görsel veya başlık bloğu) boyanma anı. *Algılanan yükleme hızını* temsil eder. İyi kabul edilen eşik, kabaca **2,5 saniyenin altıdır**.
- **CLS — Cumulative Layout Shift (Kümülatif Düzen Kayması)**: Sayfa yüklenirken öğelerin beklenmedik biçimde kaymasının birikimli ölçüsü; *görsel kararlılığı* temsil eder. Birimsiz bir skordur ve iyi kabul edilen eşik kabaca **0,1'in altıdır**.
- **INP — Interaction to Next Paint (Etkileşimden Sonraki Boyamaya Kadar Süre)**: Kullanıcının bir etkileşiminden (tıklama, tuş) sonra ekranın görsel olarak yanıt vermesine kadar geçen süre; *tepkiselliği* temsil eder. INP, daha önce kullanılan **FID (First Input Delay)** metriğinin yerini almıştır; çünkü FID yalnızca ilk etkileşimin *gecikmesini* ölçerken, INP sayfa boyunca tüm etkileşimlerin toplam tepkiselliğini daha bütünsel yakalar. İyi kabul edilen eşik kabaca **200 milisaniyenin altıdır**.

Bu eşik değerlerinin zaman içinde revize edilebildiğini ve Google'ın güncel dokümantasyonunun bağlayıcı kaynak olduğunu belirtmek gerekir; buradaki rakamlar yaygın kabul gören yaklaşık sınırlardır.

### Kök nedenler: her metriği ne bozar

**LCP'yi ne kötüleştirir?** Genellikle üç şey: (1) LCP öğesinin geç keşfedilmesi — örneğin CSS `background-image` veya lazy yapılmış bir hero görsel; (2) yavaş sunucu yanıtı (yüksek TTFB — Time To First Byte); (3) render-blocking CSS/JS. Çözüm mantığı: LCP kaynağını erken keşfettirmek (`<link rel="preload">`, `fetchpriority="high"`), TTFB'yi düşürmek (caching, CDN) ve kritik yolu temizlemek.

**CLS'yi ne kötüleştirir?** Öğelerin yer kaplayacağı alanın önceden rezerve edilmemesi. Boyutsuz görseller, geç gelen reklamlar/embed'ler, geç yüklenen web font'ları (FOIT/FOUT) ve mevcut içeriğin üstüne DOM'a sokulan bannerlar. Çözüm mantığı: her medyaya `width`/`height` veya `aspect-ratio` vermek, dinamik içerik için önceden yer ayırmak, font yüklemede `font-display` stratejisini bilinçli seçmek ve yeni içeriği mevcut içeriğin üstüne değil altına/ayrılmış alana eklemek.

**INP'yi ne kötüleştirir?** Uzun süren main thread görevleri (long tasks). Bir etkileşim geldiğinde ana thread ağır bir JavaScript görevini işliyorsa, tarayıcı olayı işleyip yeni kareyi boyayamaz. Kök neden yine ana thread'in tıkanmasıdır. Çözüm mantığı: uzun görevleri bölmek (task yielding), ağır hesaplamaları Web Worker'a taşımak, gereksiz re-render'ları azaltmak ve event handler'ları hafifletmek.

### Lab veri ile saha verisi ayrımı — kritik bir kavram

Performansı ölçerken iki farklı veri türü vardır ve bunları karıştırmak yanlış sonuçlara götürür:

- **Lab data (sentetik ölçüm)**: Kontrollü bir ortamda, sabit cihaz ve ağ koşullarıyla yapılan ölçüm (örneğin Lighthouse). Tekrarlanabilir ve hata ayıklamak için idealdir, ama tek bir yapay senaryoyu yansıtır.
- **Field data (RUM — Real User Monitoring)**: Gerçek kullanıcıların gerçek cihaz ve ağlarında toplanan veri. Gerçeği yansıtır ama gürültülüdür.

Önemli bir gerçek: **INP ve CLS gibi metrikler kullanıcı etkileşimine ve sayfa yaşam döngüsüne bağlı olduğu için lab ortamında tam ölçülemez.** Lighthouse bir sayfayı otomatik açar ama gerçek bir kullanıcı gibi tıklamaz, kaydırmaz. Bu yüzden INP'yi gerçekten anlamak için saha verisine ihtiyaç vardır. Yalnızca lab skoruna bakıp "INP'im iyi" demek yanıltıcıdır.

### Yaygın hatalar

- **Tek bir skora saplanmak**: Lighthouse'un 0-100 performans skoru faydalı bir özettir ama nihai hedef değildir. Skoru değil, gerçek kullanıcı metriklerini iyileştirmek esastır.
- **Ortalamaya bakmak**: Web Vitals genellikle **75. persentil** ile değerlendirilir, çünkü ortalama, yavaş cihazlardaki kötü deneyimi gizler. Kullanıcıların dörtte üçünün iyi deneyim yaşaması hedeflenir.
- **CLS'i sadece yüklemede aramak**: Layout shift, sayfa açıldıktan sonra da (örneğin bir "daha fazla yükle" etkileşiminde) oluşabilir; sadece ilk yüklemeyi düzeltmek yetmez.

## Bütünsel en iyi pratikler ve ölçüm disiplini

Tekniklerin tek tek doğru olması yetmez; birlikte, bir öncelik sırasıyla uygulanması gerekir. Önerilen zihinsel çerçeve şudur:

**Önce ölç, sonra optimize et.** Tahminle optimizasyon en sık yapılan hatadır. Gerçek darboğazı bulmadan yapılan iyileştirme çoğu zaman görünmez kazanç sağlar. Chrome DevTools'un Performance paneli, Lighthouse ve saha için bir RUM çözümü birlikte kullanılmalıdır. Kural: değiştirdiğin şeyi ölç, iddia etme.

**Kritik yolu önce temizle.** İlk boyamayı bloklayan render-blocking kaynakları (senkron CSS/JS) ele almak, genellikle en görünür kazancı verir çünkü doğrudan LCP ve ilk deneyimi etkiler.

**En hızlı kaynak, hiç istenmeyen kaynaktır.** Bu yüzden önce gereksiz kaynakları eleyin (kullanılmayan CSS/JS'i kaldırın — tree shaking, dead code elimination), sonra kalanları küçültün (minify, compression — Brotli/Gzip), sonra kalanları önbellekleyin. Sıra önemlidir: silinebilecek bir şeyi optimize etmek boşa emektir.

**Kaynak önceliklendirmesini tarayıcıya doğru sinyallerle bildirin.** `preload` ile erken keşfedilmesi gereken kritik kaynağı öne çekin, `preconnect` ile üçüncü parti origin'lere bağlantıyı erken kurun, `defer`/`async` ile script davranışını netleştirin, `fetchpriority` ile önemli/önemsiz istekleri işaretleyin. Bunlar tarayıcının zaten yaptığı önceliklendirmeyi yönlendiren ipuçlarıdır — ama aşırı `preload` her şeyi öncelikli yaparak hiçbir şeyi öncelikli yapmama tuzağına düşer.

**Layout stabilitesini baştan tasarlayın.** CLS bir "sonradan düzeltme" konusu değildir; her medyaya boyut, her dinamik içeriğe ayrılmış alan vermek en baştan alınacak bir tasarım kararıdır.

**Üçüncü parti kodu bir performans riski olarak yönetin.** Analytics, reklam, chat widget'ları çoğu performans faciasının kaynağıdır çünkü sizin kontrolünüz dışında ana thread'i ve ağı kullanırlar. Bunları mümkün olduğunca ertelemek (defer/lazy), gerekirse bir web worker'a taşımak veya facade (önce hafif bir yer tutucu, tıklanınca gerçek widget) deseniyle yüklemek gerekir.

**Bütçe koyun ve regresyonu engelleyin.** Performans bir kez kazanılıp bırakılan bir savaş değildir; her yeni özellik onu erozyona uğratır. **Performance budget** (örneğin "JS bundle 200 KB'yi geçmesin", "LCP 2,5 sn altında kalsın") tanımlayıp CI/CD hattında otomatik kontrol etmek, kazanımların kalıcı olmasını sağlar.

Sonuç olarak web performansı, tek bir sihirli ayar değil; tarayıcının çalışma mantığını (tek ana thread, render-blocking kaynaklar, ağ latency'si) anlayıp critical path'i temizlemek, gereksiz işi lazy loading ile ertelemek, tekrar eden işi caching ile ortadan kaldırmak ve tüm bunların etkisini Core Web Vitals ile gerçek kullanıcı üzerinden ölçmekten oluşan bütünsel bir mühendislik disiplinidir. Doğru yapıldığında sonuç yalnızca daha yüksek bir skor değil; daha hızlı görünen, daha erken kullanılabilen ve daha kararlı bir deneyimdir.
