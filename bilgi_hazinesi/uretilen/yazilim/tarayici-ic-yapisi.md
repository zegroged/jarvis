# Tarayıcı İç Yapısı: Render Pipeline, DOM/CSSOM, Event Loop ve Reflow

## Giriş: Tarayıcı Aslında Ne Yapar?

Bir tarayıcıya `https://example.com` yazdığınızda geri dönen şey, sıradan bir metin dosyasıdır: HTML kaynağı. Ekranda gördüğünüz renkli, tıklanabilir, kaydırılabilir, animasyonlu arayüz ise bu metnin uzun bir dönüşüm zincirinden geçmesinin sonucudur. Bu zincire **rendering pipeline** (görüntüleme hattı) denir ve modern tarayıcı mühendisliğinin kalbini oluşturur.

Bu makale, bir tarayıcının bir byte akışını ekrandaki piksellere nasıl çevirdiğini derinlemesine inceler. Sırasıyla şu soruların "neden" ve "nasıl"ını cevaplayacağız: HTML nasıl DOM ağacına dönüşür? CSS neden ayrı bir CSSOM ağacı gerektirir? Render pipeline'ın aşamaları (layout, paint, composite) hangi işi yapar? JavaScript'in tek thread'li dünyasında **event loop** nasıl çalışır? Ve en önemli performans kavramı: **reflow** (yeniden yerleşim) neden bu kadar pahalıdır ve nasıl kaçınılır?

Modern örneklerimizde çoğunlukla Blink (Chrome/Edge) ve Gecko (Firefox) motorlarının davranışına atıfta bulunacağız; temel mimari her ikisinde de benzerdir.

---

## Tarayıcının Ana Bileşenleri

Bir tarayıcının içine baktığımızda birkaç ayrı sorumluluk alanı görürüz:

- **Kullanıcı arayüzü (browser chrome)**: Adres çubuğu, sekmeler, geri/ileri düğmeleri. Görüntülenen sayfanın kendisi dışındaki her şey.
- **Tarayıcı motoru (browser engine)**: UI ile render motoru arasındaki koordinasyonu sağlar.
- **Render motoru (rendering engine)**: HTML/CSS'i ayrıştırıp ekrana çizen çekirdek. Blink, Gecko, WebKit bunlardır.
- **JavaScript motoru**: JavaScript kodunu ayrıştırıp çalıştırır. V8 (Chrome), SpiderMonkey (Firefox), JavaScriptCore (Safari).
- **Ağ katmanı (networking)**: HTTP istekleri, TLS handshake, önbellekleme.
- **Veri depolama**: Cookie'ler, localStorage, IndexedDB, disk cache.

Önemli bir mimari gerçek: modern tarayıcılar **multi-process** (çok süreçli) çalışır. Chrome'un site isolation modeli her origin'i (ya da grubu) ayrı bir renderer process'te izole eder. Bunun kök nedeni hem güvenlik (bir sekmenin exploit'inin diğerlerine sızmasını engellemek) hem de kararlılıktır (bir sekmenin çökmesi tüm tarayıcıyı düşürmemeli). Ana koordinasyonu yapan **browser process** ayrı bir süreçtir ve renderer'lar kum havuzu (sandbox) içinde, kısıtlı yetkilerle koşar.

---

## HTML'den DOM'a: Ayrıştırma (Parsing)

### DOM Nedir?

**DOM (Document Object Model)**, HTML belgesinin bellekteki nesne tabanlı, ağaç yapılı temsilidir. Her HTML etiketi bir düğüm (node), iç içe geçmiş etiketler ise ebeveyn-çocuk ilişkileri hâlinde bir ağaç oluşturur. DOM sadece bir veri yapısı değil, aynı zamanda JavaScript'in sayfayla etkileşime girdiği programlanabilir arayüzdür (`document.getElementById`, `element.appendChild` gibi).

### Ayrıştırma Neden Adım Adım İlerler?

HTML ayrıştırıcısı byte akışını şu aşamalardan geçirir:

1. **Byte → karakter dönüşümü**: Ham byte'lar, belirtilen karakter kodlamasına (genellikle UTF-8) göre karakterlere çözülür.
2. **Tokenization (belirteçleme)**: Karakter akışı, `<html>`, `<body>`, başlangıç/bitiş etiketleri, öznitelikler gibi anlamlı token'lara bölünür.
3. **Tree construction (ağaç kurma)**: Token'lar HTML'in katı kurallarına göre DOM ağacına yerleştirilir.

Kök nedeni anlamak önemli: HTML ayrıştırma **streaming** (akış hâlinde) çalışır, yani ayrıştırıcı belgenin tamamını beklemek zorunda değildir. Ağdan gelen ilk chunk'larla ağacı kurmaya başlar. Bu, "progressive rendering" (aşamalı görüntüleme) dediğimiz, sayfanın parça parça belirmesini mümkün kılar.

HTML ayrıştırma ayrıca hata toleranslıdır (fault-tolerant). Kapatılmamış bir `<p>` etiketi ya da yanlış yuvalanmış öğeler ayrıştırmayı durdurmaz; spesifikasyon, tarayıcının bu tür hataları nasıl "düzelteceğini" tam olarak tanımlar. Bu yüzden aynı bozuk HTML tüm tarayıcılarda aynı DOM'u üretir. Bu, XML'in aksine bilinçli bir tasarım kararıdır: web'in gerçek dünyadaki HTML'i çoğunlukla kusurludur.

### Ayrıştırmayı Bloke Eden Kaynaklar

Kritik bir davranış: `<script>` etiketi varsayılan olarak **parser-blocking**'dir. Ayrıştırıcı bir script'e rastladığında, script indirilip çalıştırılana kadar DOM kurmayı durdurur. Kök nedeni, script'in `document.write` ile belge akışını değiştirebilmesidir; ayrıştırıcı script'in DOM'u ne yönde değiştireceğini önceden bilemez.

Bu tıkanıklığı çözmek için iki öznitelik vardır:

- **`defer`**: Script arka planda indirilir ama çalıştırılması, DOM tamamen kurulana kadar ertelenir. Belge sırasını korur.
- **`async`**: Script arka planda indirilir ve indirilir indirilmez, sıra gözetmeksizin çalıştırılır.

Benzer şekilde CSS de render'ı bloke eder — ama neden? Çünkü bir script CSSOM'a (aşağıda) erişebilir ve stil bilgisini okuyabilir. Tarayıcı, stil hesaplanmadan JavaScript'in yanlış değer okumasını istemez. Bu yüzden CSS "render-blocking" kabul edilir.

Modern tarayıcılar bir de **preload scanner** (ön yükleme tarayıcısı) çalıştırır: ana ayrıştırıcı bir script'te bloke olsa bile, ikincil bir hafif tarayıcı belgeyi ileri doğru tarayıp `<img>`, `<link>`, `<script src>` gibi kaynakları önceden keşfeder ve indirmeye başlar. Bu, ağ gecikmesini gizleyen önemli bir optimizasyondur.

---

## CSS'ten CSSOM'a: Neden Ayrı Bir Ağaç?

### CSSOM Nedir?

**CSSOM (CSS Object Model)**, sayfanın tüm stil kurallarının ağaç yapılı temsilidir. DOM "ne var" (yapı) sorusunu, CSSOM ise "nasıl görünecek" (stil) sorusunu cevaplar.

### Neden DOM'a Gömülmüyor da Ayrı Duruyor?

Kök neden CSS'in **cascade** (basamaklanma) ve **inheritance** (kalıtım) doğasıdır. Bir öğenin nihai stili; tarayıcı varsayılanları (user agent stylesheet), yazar stilleri, satır içi stiller, özgüllük (specificity) ve kaynak sırası gibi kuralların birleştirilmesiyle hesaplanır. Örneğin `body { font-size: 16px }` kuralı, alt öğeler kendi değerini belirtmedikçe onlara miras kalır. Bu hesaplamayı yapmak için tarayıcının önce tüm kural setine sahip olması gerekir.

İşte bu yüzden CSSOM **inkremental (kısmi) kurulamaz** ve DOM gibi streaming değildir. Bir öğenin stilini kesin olarak bilmek için, o öğeyi ezebilecek tüm CSS'in görülmüş olması gerekir. Sonradan yüklenen bir `<link>` stylesheet, sayfanın başındaki bir öğenin rengini değiştirebilir. Tarayıcı, tüm blocking CSS gelene kadar güvenli bir şekilde render edemez.

CSS seçicileri (selectors) **sağdan sola** eşleştirilir. `div.container p span` seçicisi için tarayıcı önce tüm `span`'ları bulur, sonra yukarı doğru ebeveynleri kontrol eder. Bunun kök nedeni verimliliktir: soldan gitseydi her `div` altındaki tüm olası yolları denemek gerekirdi; sağdan gidince aday küme hızla daralır. Bu yüzden çok derin ve genel (`* > *`) seçiciler stil hesaplamasını yavaşlatabilir.

---

## Render Ağacı, Layout ve Paint

### Render Ağacı (Render Tree / Layout Tree)

DOM ve CSSOM hazır olduğunda tarayıcı bu ikisini birleştirerek **render tree**'yi (Blink'te "layout tree") oluşturur. Render ağacı yalnızca ekranda gerçekten görünecek öğeleri içerir. 

Kritik ayrım: `display: none` olan bir öğe render ağacında **yer almaz**, çünkü hiç yerleştirilmez ve çizilmez. Buna karşılık `visibility: hidden` olan öğe render ağacında **kalır** ve yerini işgal eder — sadece görünmez. Bu fark, neden `display: none` ile `visibility: hidden` arasında hem görsel hem performans açısından ciddi ayrım olduğunu açıklar: birincisi layout'tan tamamen çıkarken ikincisi hâlâ hesaplanır.

### Layout (Reflow / Yerleşim)

**Layout** aşamasında tarayıcı her render ağacı düğümünün ekrandaki tam geometrisini hesaplar: genişlik, yükseklik, x/y konumu, kutu modeli (margin, border, padding). Bu aşamaya Gecko'da tarihsel olarak **reflow**, Blink/WebKit'te **layout** denir.

Layout neden pahalıdır? Çünkü geometri **birbirine bağımlıdır**. Bir öğenin genişliğini değiştirmek, kardeş öğelerin, çocukların ve hatta ebeveynin konumunu etkileyebilir. Yüzde tabanlı genişlikler, `flexbox`, `grid` gibi düzenlerde bir değişiklik tüm bir alt ağacın yeniden ölçülmesini gerektirebilir. Layout, tanım gereği ağaç üzerinde gezinen ve çoğu zaman yukarı-aşağı bağımlılık taşıyan bir hesaplamadır.

### Paint (Boyama)

**Paint** aşamasında tarayıcı, hesaplanmış geometriyi kullanarak her öğe için çizim komutları listesi (display list / paint records) üretir: "şu dikdörtgeni şu renkle doldur", "şu metni şu fontla çiz", "şu kenarlığı çiz". Bu aşama henüz ekrana piksel basmaz; çizim talimatlarını hazırlar.

Paint, öğeleri **paint order** (z-index, stacking context) kurallarına göre katmanlar hâlinde sıralar. Bu yüzden `z-index` ve `position` değerleri hangi öğenin diğerinin üstünde çizileceğini belirler.

### Compositing (Katman Birleştirme)

Modern tarayıcılar sayfayı tek bir bitmap olarak çizmez; **layers** (katmanlar) hâlinde böler ve bunları GPU üzerinde birleştirir (**compositing**). Bir öğe kendi katmanına "yükseltilebilir" (promotion) — örneğin `transform`, `opacity` animasyonları, `will-change` ipucu ya da `<video>` gibi öğeler.

Compositing'in dâhice yanı şudur: bir katmanı kaydırmak, döndürmek ya da opaklığını değiştirmek, o katmanı **yeniden boyamayı gerektirmez**. GPU sadece mevcut bitmap'i farklı bir konumda/opaklıkta birleştirir. İşte bu yüzden `transform: translate()` ile yapılan animasyon, `left`/`top` ile yapılana göre çok daha akıcıdır — birincisi layout ve paint'i tamamen atlar, sadece compositing aşamasına dokunur.

---

## Pipeline'ın Bütünsel Akışı

Tüm zinciri özetlersek:

1. **Parse HTML → DOM**
2. **Parse CSS → CSSOM**
3. **DOM + CSSOM → Render Tree**
4. **Layout** (geometri hesaplama)
5. **Paint** (çizim komutları)
6. **Composite** (katmanları GPU'da birleştirip ekrana basma)

Bu pipeline'ın kritik özelliği **kısmi geçerlilik yitimi** (invalidation) yapabilmesidir. Bir stil değişikliği yaptığınızda tarayıcı, o değişikliğin pipeline'ın hangi aşamasından itibaren yeniden çalışması gerektiğini belirler:

- **Layout'u tetikleyen** değişiklikler (genişlik, konum, font-size): 4 → 5 → 6 aşamalarının tümü yeniden çalışır. En pahalısı.
- **Sadece paint'i tetikleyen** değişiklikler (renk, `background-color`, `box-shadow`): 5 → 6 çalışır, layout atlanır.
- **Sadece composite'i tetikleyen** değişiklikler (`transform`, `opacity`): sadece 6 çalışır. En ucuzu.

Performans mühendisliğinin özü, mümkün olduğunca aşağıdaki (ucuz) aşamalarda kalmaktır.

---

## Event Loop: Tek Thread'in Sihri

### Sorun: JavaScript Tek Thread'lidir

Bir sayfadaki JavaScript, **tek bir main thread** üzerinde çalışır. Aynı thread hem JavaScript'i çalıştırır, hem stil/layout hesaplar, hem de kullanıcı etkileşimlerini işler. Peki tek thread ile nasıl aynı anda ağ isteği bekleyip, tıklamaya yanıt verip, animasyon oynatabiliyoruz? Cevap **event loop**'tur.

### Çalışma Mantığı

Event loop kavramsal olarak sonsuz bir döngüdür: "Yapılacak bir iş (task) var mı? Varsa al ve bitene kadar çalıştır. Bittiğinde bir sonrakine geç." Kritik nokta, JavaScript'in **run-to-completion** (bitene kadar çalışma) semantiğidir: bir task başladığında, o task tamamen bitmeden başka bir task araya giremez. Bu, geliştiricinin bir fonksiyonun ortasında beklenmedik bir şekilde başka kodun çalışmayacağından emin olmasını sağlar — race condition'ların bir sınıfını baştan ortadan kaldırır.

Event loop iki tür kuyruğu yönetir:

- **Macrotask kuyruğu (task queue)**: `setTimeout`, `setInterval` callback'leri, kullanıcı olayları (click, keydown), ağ olayları. Her tur bir macrotask alınır.
- **Microtask kuyruğu**: Promise `.then/.catch/.finally` callback'leri, `queueMicrotask`, `MutationObserver`. 

Kritik ve sık karıştırılan kural: **her bir macrotask'tan sonra, bir sonraki macrotask'a geçmeden önce, microtask kuyruğu TAMAMEN boşaltılır.** Yani bir microtask başka microtask üretirse, onlar da hemen aynı turda çalışır. Bunun kök nedeni, Promise zincirlerinin senkron kodun hemen ardından, ama render'dan önce çözülmesini garantilemektir.

### Somut Örnek: Çıktı Sırası

```javascript
console.log('1: senkron başlangıç');

setTimeout(() => console.log('2: macrotask (setTimeout)'), 0);

Promise.resolve().then(() => console.log('3: microtask (promise)'));

console.log('4: senkron son');
```

Çıktı sırası: `1`, `4`, `3`, `2`. Neden? Önce tüm senkron kod çalışır (1 ve 4). Ardından mevcut task biter ve microtask kuyruğu boşaltılır (3). Ancak bundan sonra event loop bir sonraki macrotask'a geçer (2). `setTimeout(fn, 0)` bile "hemen" değildir; sadece "en erken sonraki macrotask turunda" demektir ve microtask'lardan sonra gelir.

### Event Loop ve Render İlişkisi

Render (layout + paint) da event loop'un bir parçasıdır ama her turda çalışmaz. Tarayıcı genellikle ekran yenileme hızına (çoğunlukla 60 Hz, yani ~16.6 ms) senkronize olarak render fırsatı yaratır. Bu döngü içinde `requestAnimationFrame` (rAF) callback'leri, tam olarak **layout/paint'ten hemen önce** çalışacak şekilde zamanlanır. 

Bunun pratik sonucu şudur: bir animasyonu `setTimeout` yerine `requestAnimationFrame` ile yapmalısınız, çünkü rAF tarayıcının çizim ritmine kilitlenir, frame atlamalarını (jank) azaltır ve sekme arka plandayken otomatik durur (batarya tasarrufu).

### Ana Thread'i Bloke Etmek Neden Ölümcüldür?

Event loop tek thread üzerinde döndüğü için, uzun süren senkron bir JavaScript (örneğin 200 ms'lik ağır bir döngü) o süre boyunca event loop'u kilitler. Bu esnada hiçbir click işlenmez, hiçbir animasyon ilerlemez, sayfa "donar". İşte "long task" dediğimiz bu bloklama, kullanıcı deneyiminin baş düşmanıdır. Çözümler: işi küçük parçalara bölmek (chunking), `Web Worker`'a taşımak (ayrı thread), ya da işi ertelemek.

---

## Reflow: En Pahalı Kavram ve Ondan Kaçınmak

### Reflow Neden Pahalı?

Reflow'un (layout) pahalı olmasının kök nedenini tekrar vurgulayalım: geometri bağımlılıkları. Tek bir öğenin boyutunu değiştirmek, komşularını, çocuklarını ve ebeveynlerini etkileyebildiği için tarayıcı geniş bir alt ağacı yeniden hesaplamak zorunda kalabilir. Karmaşık sayfalarda tek bir reflow milisaniyeler sürebilir ve 16 ms bütçesini aşarak frame düşürebilir.

### Layout Thrashing: En Yaygın Hata

En sinsi performans hatası **layout thrashing** (forced synchronous layout / zorunlu senkron layout) olarak bilinir. Tarayıcı normalde stil değişikliklerini **batch'ler** (biriktirir) ve tek seferde işler. Ancak siz JavaScript'te bir geometri değeri **okursanız** (örneğin `offsetHeight`, `offsetWidth`, `getBoundingClientRect`, `scrollTop`, `getComputedStyle`), tarayıcı size güncel değeri vermek için bekleyen tüm stil değişikliklerini **hemen, senkron olarak** uygulamak (yani reflow yapmak) zorunda kalır.

Sorun, okuma ve yazmayı bir döngü içinde iç içe geçirdiğinizde ortaya çıkar:

```javascript
// KÖTÜ: her yineleme zorunlu senkron layout tetikler
const boxes = document.querySelectorAll('.box');
for (const box of boxes) {
  // Okuma: layout'u zorlar (bekleyen yazmaları uygular)
  const w = box.offsetWidth;
  // Yazma: layout'u geçersiz kılar (invalidate eder)
  box.style.width = (w + 10) + 'px';
}
```

Bu döngüde her yinelemede önce yazma layout'u geçersiz kılar, sonraki yinelemedeki okuma ise güncel değeri istediği için tarayıcıyı yeniden layout yapmaya zorlar. N öğe için N kez reflow tetiklenir — kuadratik yavaşlığa kadar gidebilir.

### Doğru Yaklaşım: Read/Write Ayrımı

Çözüm, tüm **okumaları** ve tüm **yazmaları** ayırmaktır. Önce oku, sonra yaz:

```javascript
// İYİ: önce tüm okumalar (tek reflow), sonra tüm yazmalar
const boxes = document.querySelectorAll('.box');
const widths = [];
for (const box of boxes) {
  widths.push(box.offsetWidth);   // sadece okuma
}
boxes.forEach((box, i) => {
  box.style.width = (widths[i] + 10) + 'px';  // sadece yazma
});
```

Burada tüm okumalar tek bir batch'te yapıldığı için en fazla bir reflow olur; yazmalar ise biriktirilip tek seferde uygulanır. Bu "read-then-write" deseni, `FastDOM` gibi kütüphanelerin de temelidir.

### DOM Değişikliklerini Batch'lemek

Çok sayıda DOM düğümü ekleyecekseniz, her `appendChild` çağrısı canlı DOM'a dokunup potansiyel reflow tetikleyebilir. `DocumentFragment` kullanarak değişiklikleri bellekte biriktirip tek seferde ekleyebilirsiniz:

```javascript
const fragment = document.createDocumentFragment();
for (let i = 0; i < 1000; i++) {
  const li = document.createElement('li');
  li.textContent = 'Öğe ' + i;
  fragment.appendChild(li);   // canlı DOM'a dokunmaz
}
list.appendChild(fragment);   // tek seferde, tek reflow
```

Benzer şekilde, bir öğede çok sayıda stil değişikliği yapacaksanız, öğeyi `display: none` yapıp değişiklikleri uygulayıp geri açmak (iki reflow) ya da bir CSS `class` değiştirmek, tek tek satır içi stil atamaktan daha ucuzdur.

---

## Yaygın Hatalar ve Yanlış Anlamalar

**"`setTimeout(fn, 0)` fonksiyonu hemen çalıştırır."** Yanlış. Sadece mevcut senkron kod ve tüm microtask'lar bittikten sonra, bir sonraki macrotask turunda çalışır. Ayrıca tarayıcılar iç içe timer'lar için minimum bir gecikme (tarihsel olarak ~4 ms) uygular.

**"CSS animasyonları her zaman JavaScript animasyonlarından daha hızlıdır."** Kısmen. `transform` ve `opacity` üzerinden giden CSS animasyonları compositor thread'de çalışabilir ve main thread bloke olsa bile akıcı kalır. Ama `width`, `top`, `margin` gibi layout tetikleyen özellikleri CSS ile animasyonlamak yine reflow üretir ve hızlı olmaz.

**"`display: none` ile `visibility: hidden` aynı şeydir."** Değildir. İlki öğeyi render ağacından çıkarır ve layout'tan tamamen çıkarır; ikincisi öğeyi yerinde tutar, yer kaplar, sadece görünmez kılar.

**"Ağır işi ana thread'te yapmak sorun değildir çünkü asenkrondur."** `async`/`await` ya da Promise kullanmak işi sihirli biçimde başka thread'e taşımaz. Bir Promise callback'i hâlâ main thread'de, event loop üzerinde çalışır. Gerçek paralellik için `Web Worker` gerekir.

**"Her stil okuması ucuzdur."** `offsetTop`, `getBoundingClientRect`, `scrollHeight` gibi geometri okumaları bekleyen layout'u zorlayarak beklenmedik reflow'a yol açabilir. Okumaların da bir maliyeti vardır.

---

## En İyi Pratikler

**Kritik render yolunu (critical rendering path) kısaltın.** İlk boyamayı geciktiren şey render-blocking CSS ve parser-blocking JavaScript'tir. Kritik olmayan CSS'i ayırın, script'lere `defer`/`async` verin, kritik CSS'i satır içi (inline) ekleyin.

**Animasyonları `transform` ve `opacity` ile yapın.** Bu özellikler layout ve paint'i atlar, sadece compositing aşamasında çalışır. `left/top/width/height` üzerinden animasyondan kaçının.

**`requestAnimationFrame` kullanın.** Görsel güncellemeleri tarayıcının çizim ritmine kilitleyin; `setTimeout` ile manuel animasyon yapmayın.

**Okuma ve yazmayı ayırın.** DOM geometrisi okumalarını bir grupta, yazmalarını başka grupta toplayarak layout thrashing'i önleyin.

**Ağır hesaplamayı Web Worker'a taşıyın.** Uzun süren, main thread'i bloke eden işleri ayrı thread'e alarak event loop'u serbest bırakın. Long task'ları küçük parçalara bölün.

**`will-change` ipucunu bilinçli kullanın.** Tarayıcıya bir öğenin yakında değişeceğini söyleyerek onu önceden kendi katmanına yükseltebilirsiniz — ama aşırı kullanım bellek tüketir ve ters teper; sadece gerçekten animasyonlanan öğelerde kullanın.

**Geniş, genel CSS seçicilerinden kaçının.** Çok derin ve `*` içeren seçiciler stil eşleştirmeyi yavaşlatır. Seçicileri sade ve spesifik tutun.

**DOM değişikliklerini batch'leyin.** `DocumentFragment` ile toplu ekleme yapın; canlı DOM'a döngü içinde tekrar tekrar dokunmaktan kaçının.

---

## Sonuç

Tarayıcı, basit bir metin dosyasını akıcı bir arayüze çeviren, katmanlı ve dikkatle optimize edilmiş bir makinedir. HTML akış hâlinde DOM'a dönüşür; CSS, cascade doğası gereği tam olarak toplanmadan güvenle uygulanamayan CSSOM'a dönüşür; ikisi birleşip render ağacını oluşturur; layout geometriyi hesaplar, paint çizim komutlarını üretir, compositing GPU'da katmanları birleştirir. Tüm bunlar tek bir main thread üzerinde, event loop'un macrotask ve microtask kuyruklarını çevirmesiyle koordine edilir.

Bir web performans mühendisi olarak asıl kavramanız gereken sezgi şudur: **pipeline'da ne kadar yukarıda (layout'ta) bir değişiklik tetiklerseniz o kadar pahalıya mal olur; ne kadar aşağıda (compositing'te) kalırsanız o kadar ucuzdur.** Reflow'dan kaçınmak, okuma-yazmayı ayırmak, main thread'i bloke etmemek ve compositor-dostu özellikler kullanmak — bu ilkeler, tarayıcının iç mimarisinin doğrudan bir sonucudur. Mimariyi anladığınızda, performans reçeteleri ezberlenmesi gereken kurallar olmaktan çıkıp mantıksal zorunluluklar hâline gelir.
