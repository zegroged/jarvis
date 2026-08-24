# Sıralama Algoritmaları: Quicksort, Mergesort, Heapsort, Kararlılık ve Timsort

## Giriş ve Kapsam

Sıralama (sorting), bilgisayar bilimlerinin en çok çalışılmış problemlerinden biridir. Yüzeyden bakıldığında "elemanları küçükten büyüğe diz" gibi basit görünse de, altında hesaplama karmaşıklığı (computational complexity), bellek erişim düzeni (memory access pattern), önbellek dostluğu (cache friendliness) ve pratik mühendislik kararlarını içeren derin bir konu yatar. Bu makale, üç temel karşılaştırmalı sıralama algoritmasını (quicksort, mergesort, heapsort), kararlılık (stability) kavramını, modern kütüphanelerde standart hâline gelmiş Timsort'u ve gerçek dünyada hangi durumda hangisini seçmeniz gerektiğini akıl yürüterek anlatır.

Önce temel bir gerçeği netleştirelim: **Karşılaştırmaya dayalı hiçbir sıralama algoritması, ortalama ve en kötü durumda O(n log n)'den daha iyisini yapamaz.** Bunun nedeni, n elemanlı bir dizinin n! olası dizilişi bulunması ve her karşılaştırmanın olasılık uzayını en fazla ikiye bölmesidir. Bu karar ağacının (decision tree) yaprak sayısı en az n! olmak zorundadır; ağacın yüksekliği ise log₂(n!) ≈ n log n mertebesindedir. Bu alt sınır (lower bound), "neden hep O(n log n) görüyoruz?" sorusunun kökündeki cevaptır. Bu sınırın altına inmenin tek yolu, karşılaştırma yapmamaktır; counting sort veya radix sort gibi dağıtıma dayalı yöntemler bunu yapar ama yalnızca belirli veri türlerinde.

## Karşılaştırmalı Sıralamanın Kök Mantığı

Neden karşılaştırma tabanlı algoritmalar bu duvara çarpar? Çünkü genel amaçlı bir karşılaştırıcı (comparator) yalnızca "a, b'den küçük mü, büyük mü, eşit mi?" sorusunu sorabilir. Elemanların iç yapısı hakkında hiçbir varsayım yapmaz. Her karşılaştırma bir bit bilgi üretir. n! olasılığı ayırt etmek için en az log₂(n!) bite ihtiyaç vardır. Stirling yaklaşımıyla log₂(n!) ≈ n log₂ n - n log₂ e olduğundan, asimptotik olarak Θ(n log n) karşılaştırma zorunludur.

Bu, teorik bir merak değil, pratik bir pusuladır. Bir algoritmanın O(n log n)'den daha hızlı olduğunu iddia eden biri varsa, ya karşılaştırma yapmıyordur (veri hakkında ek bilgi kullanıyordur) ya da yanlış ölçüm yapmıştır. Mühendis olarak bu sınırı bilmek, abartılı iddiaları eleyen bir zihinsel filtre sağlar.

## Quicksort

### Tanım

Quicksort, Tony Hoare tarafından 1959-1961 yıllarında geliştirilmiş, böl-ve-yönet (divide and conquer) prensibine dayanan bir sıralama algoritmasıdır. Temel fikir şudur: diziden bir **pivot** eleman seçilir, dizi bu pivot etrafında ikiye ayrılır (partition) — pivottan küçük olanlar sola, büyük olanlar sağa — ve iki alt parça özyinelemeli (recursive) olarak aynı şekilde sıralanır.

### Kök Neden: Neden Bu Kadar Hızlı Çalışır?

Quicksort'un pratikteki üstünlüğü asimptotik karmaşıklığından değil, **sabit çarpanının (constant factor) küçüklüğünden** ve **önbellek davranışından** gelir. Partition işlemi, diziyi ardışık (sequential) olarak baştan sona tarar. Modern işlemcilerde bellek, önbellek satırları (cache line) hâlinde çekilir; ardışık erişim, önbellek isabet oranını (cache hit rate) maksimize eder. Ayrıca partition, ek bir dizi ayırmadan **yerinde (in-place)** çalışır; yalnızca eleman takasları (swap) yapar. Bu, mergesort'un gerektirdiği ek bellek trafiğini ortadan kaldırır.

En kötü durumu O(n²)'dir ve bu, pivot seçiminin her seferinde en kötü (en küçük veya en büyük) elemana denk gelmesiyle ortaya çıkar. Örneğin zaten sıralı bir dizide her zaman ilk elemanı pivot seçerseniz, her partition diziyi 1 ve n-1 boyutunda iki parçaya böler; özyineleme derinliği n olur ve toplam iş O(n²)'ye çıkar. Bu, "sıralı veriyi tekrar sıralamak neden çökertir?" sorusunun cevabıdır.

### Somut Örnek ve Partition Şemaları

[3, 8, 1, 5, 2] dizisini, son elemanı (2) pivot seçen Lomuto şemasıyla düşünelim. Tarama sırasında 2'den küçük elemanlar sol tarafa itilir: 1 tek küçük elemandır, sola geçer, sonra pivot onun sağına yerleşir → [1, 2, ...] ve geri kalan büyük elemanlar sağda kalır. Sol ve sağ parçalar ayrı ayrı sıralanır.

İki klasik partition şeması vardır. **Lomuto şeması** basittir ve öğretimde tercih edilir, ama tekrarlı (duplicate) elemanlarda verimsizdir. **Hoare şeması** iki uçtan içeri doğru ilerleyen iki işaretçi (pointer) kullanır; ortalama daha az takas yapar ve genellikle daha hızlıdır. Çok sayıda eşit eleman içeren dizilerde ise **üç yönlü partition (three-way partition, "Dutch National Flag")** kullanılır: dizi "küçük", "eşit", "büyük" olarak üçe ayrılır, böylece eşit elemanlar tekrar tekrar işlenmez.

### Doğru Kullanım, Tuzaklar ve Yaygın Hatalar

En büyük tuzak, **kötü pivot seçimidir.** Sabit bir pozisyondan (ilk/son eleman) pivot seçmek, sıralı veya ters sıralı girdide O(n²) çöküşe yol açar. Bu, yalnızca performans sorunu değil, aynı zamanda bir **güvenlik açığı** olabilir: bir saldırgan, sunucuya kasıtlı olarak en kötü durumu tetikleyen veri göndererek CPU'yu tüketip hizmet reddi (denial of service) oluşturabilir. Bu sınıf saldırılara "algorithmic complexity attack" denir. Savunma olarak iki teknik yaygındır:

1. **Randomize pivot:** Pivotu rastgele seçmek, saldırganın en kötü durumu deterministik biçimde zorlamasını olasılıksal olarak imkânsız kılar. Beklenen çalışma süresi O(n log n)'de kalır.
2. **Median-of-three / median-of-medians:** İlk, orta ve son elemanın medyanını pivot almak, sıralı girdilerdeki patolojik davranışı büyük ölçüde giderir.

İkinci önemli tuzak **özyineleme derinliği ve stack taşmasıdır (stack overflow).** Naif quicksort, en kötü durumda O(n) derinliğinde özyineler; büyük dizilerde çağrı yığını (call stack) taşabilir. Doğru pratik: **her zaman küçük parçayı özyinele, büyük parçayı döngüyle (tail call elimination) işle.** Böylece yığın derinliği O(log n) ile sınırlanır.

Bunların birleşimi olan **introsort (introspective sort)**, quicksort ile başlar, özyineleme derinliği bir eşiği (genellikle ~2 log n) aşarsa heapsort'a geçer ve küçük alt dizilerde (genellikle ~16 eleman altı) insertion sort'a düşer. Böylece hem quicksort'un ortalama hızını, hem heapsort'un O(n log n) en kötü durum garantisini, hem de insertion sort'un küçük dizilerdeki düşük sabit çarpanını birlikte elde eder. C++ standart kütüphanesindeki `std::sort` tipik olarak introsort tabanlıdır.

## Mergesort

### Tanım

Mergesort da böl-ve-yönet yaklaşımını kullanır, ama farklı bir eksende: dizi ortadan ikiye bölünür, iki yarı ayrı ayrı sıralanır ve ardından **birleştirme (merge)** adımıyla iki sıralı yarı tek bir sıralı diziye tarak dişi gibi geçirilir (interleave). John von Neumann'a atfedilir (1945).

### Kök Neden: Neden Garantili O(n log n)?

Quicksort'tan farkı, bölmenin **her zaman dengeli (balanced)** olmasıdır. Dizi tam ortadan bölündüğü için özyineleme ağacının yüksekliği koşulsuz olarak log n'dir; pivot şansına bağlı değildir. Her seviyede birleştirme toplamda O(n) iş yapar, log n seviye vardır, dolayısıyla **her durumda** — en iyi, ortalama, en kötü — O(n log n). Bu determinizm, gerçek zamanlı (real-time) veya en kötü durum garantisinin sözleşmesel olarak gerektiği sistemlerde mergesort'u değerli kılar.

### Somut Örnek

[3, 1, 4, 2] → ortadan böl → [3, 1] ve [4, 2] → her biri bölünüp sıralanır → [1, 3] ve [2, 4] → merge adımı iki listenin başlarını karşılaştırarak ilerler: 1<2 → 1 al; 3>2 → 2 al; 3<4 → 3 al; 4 kalır → [1, 2, 3, 4]. Merge adımının kalbi tam olarak bu "iki sıralı listenin başını karşılaştır, küçüğünü çıktıya al" döngüsüdür.

### Doğru Kullanım, Tuzaklar ve Yaygın Hatalar

Mergesort'un başlıca dezavantajı **ek bellek gereksinimidir.** Standart merge, çıktı için O(n) ek alan kullanır. Bellek kısıtlı gömülü (embedded) sistemlerde bu bir engeldir. Yerinde birleştiren (in-place merge) varyantları vardır, ancak ya karmaşıktır ya da sabit çarpanı büyür; pratikte genellikle O(n) tampon (buffer) kullanmaya razı olunur.

Buna karşılık mergesort'un iki büyük üstünlüğü vardır. **Birincisi kararlılıktır (stability)** — bunu birazdan ayrıntılandıracağız. **İkincisi, bağlı listelerde (linked list) mükemmel çalışmasıdır:** bağlı listede merge, yalnızca işaretçileri yeniden bağlayarak yapılır, hiç ek bellek gerektirmez ve rastgele erişim (random access) gerektirmediği için bağlı listenin doğal zayıflığından etkilenmez. Quicksort ise bağlı listelerde beceriksizdir çünkü verimli partition için rastgele erişime yaslanır.

Ayrıca mergesort **doğal olarak paralelleştirilebilir (parallelizable)** ve **harici sıralamaya (external sort)** çok uygundur: belleğe sığmayan devasa dosyaları sıralarken, parçaları tek tek sıralayıp diske yazmak ve ardından bu sıralı parçaları merge etmek klasik yaklaşımdır. Büyük veri sistemlerinde disk-tabanlı sıralamanın omurgası mergesort mantığıdır.

Yaygın bir hata, merge fonksiyonunu yazarken **kararlılığı bozan bir karşılaştırma kullanmaktır.** Sol yarının bir elemanı ile sağ yarının elemanı eşit olduğunda, kararlılığı korumak için **soldakini önce almanız** gerekir (`sol <= sağ` değil, `sol > sağ` ise sağı al mantığı). Karşılaştırma operatörünü yanlış yönde yazmak, sıralamayı doğru ama kararsız (unstable) hâle getirir; bu, testlerde kolayca fark edilmeyen sinsi bir hatadır.

## Heapsort

### Tanım

Heapsort, **ikili yığın (binary heap)** veri yapısını kullanan bir sıralama algoritmasıdır. Dizi önce bir max-heap'e dönüştürülür (heapify); ardından kökteki en büyük eleman tekrar tekrar sondaki elemanla takas edilip heap'in aktif boyutu bir azaltılır ve kök yeniden aşağı süzülür (sift-down). Böylece en büyük elemanlar sondan başa doğru yerleşir.

### Kök Neden: Yığın Neden İşe Yarar?

İkili yığın, bir diziyi örtük (implicit) bir tam ikili ağaç (complete binary tree) gibi ele almanın zekice bir yoludur: indeks i'deki elemanın çocukları 2i+1 ve 2i+2'dedir. İşaretçi kullanmadan ağaç yapısını dizide taşırız. Max-heap özelliği "her ebeveyn çocuklarından büyük veya eşittir" der; bu, en büyük elemanın daima kökte olmasını garanti eder. Kökü çıkarıp yığını yeniden düzenlemek O(log n) sürer (ağaç yüksekliği kadar süzme), n eleman için toplam O(n log n).

Heapify adımının tamamının O(n) olması ilk bakışta şaşırtıcıdır — n eleman × log n değil de neden O(n)? Çünkü ağacın çoğu düğümü yapraklara yakındır ve kısa mesafe süzülür; yüksekten süzülen düğüm sayısı azdır. Katmanların işlerinin toplamı geometrik bir seri oluşturur ve O(n)'e yakınsar. Ancak sıralamanın tamamı yine O(n log n)'dir çünkü çıkarma fazı baskındır.

### Doğru Kullanım, Tuzaklar ve Yaygın Hatalar

Heapsort'un iki cazip özelliği vardır: **yerinde çalışır (O(1) ek bellek)** ve **en kötü durumda dahi O(n log n) garantisi verir.** Bu ikisinin birleşimi onu, hem bellek kısıtlı hem de en kötü durum garantisi gereken senaryolar için değerli kılar. Nitekim introsort, quicksort patolojik davranışa kaydığında güvenlik ağı olarak tam da heapsort'a düşer.

Peki neden heapsort her yerde varsayılan değil? Çünkü **önbellek düşmanıdır (cache-unfriendly).** Sift-down işlemi, dizide 2i+1, 2i+2 gibi giderek uzaklaşan indekslere zıplar; bu erişim düzeni ardışık değildir, önbellek satırlarını israf eder ve önbellek ıskalamalarını (cache miss) artırır. Aynı asimptotik sınıfta olmalarına rağmen heapsort, pratikte iyi ayarlanmış bir quicksort'tan tipik olarak birkaç kat yavaştır. Ayrıca heapsort **kararsızdır (unstable)**; uzak takaslar eşit elemanların göreli sırasını bozar.

Yaygın bir hata, heapify'ı yanlış yönden başlatmaktır: heap'i kurmak için diziyi **son iç düğümden köke doğru (aşağıdan yukarı)** sift-down ile işlemeniz gerekir. Yapraklardan başlayıp yukarı doğru "sift-up" ile kurmaya çalışmak, hem yanlış hem de daha yavaştır (O(n log n)).

## Kararlılık (Stability)

### Tanım

Bir sıralama algoritması, **eşit anahtara (key) sahip elemanların göreli sırasını koruyorsa kararlıdır (stable).** Yani girdide A elemanı B'den önce geliyor ve ikisinin sıralama anahtarı eşitse, çıktıda da A, B'den önce kalmalıdır.

### Kök Neden: Kararlılık Neden Önemli?

Kararlılık, tek bir alan üzerinden sıralanan veride görünmezdir — iki eşit sayı birbirinden ayırt edilemez, sırasının değişmesi umursanmaz. Kararlılığın hayati önem kazandığı yer **çok anahtarlı (multi-key), aşamalı sıralamadır.** Diyelim ki bir çalışan tablosunu önce "ada göre", sonra "departmana göre" sıralamak istiyorsunuz. Kararlı bir algoritmayla şunu yapabilirsiniz: önce ada göre sırala, sonra departmana göre sırala. İkinci sıralama, aynı departmandaki çalışanların ilk sıralamadan gelen alfabetik sırasını **bozmaz.** Sonuç: departmana göre gruplu, her grup içinde ada göre sıralı bir tablo. Bu, "kompozisyonla sıralama" olarak bilinen güçlü bir tekniktir ve yalnızca kararlı algoritmalarla çalışır.

Kararsız bir algoritmayla aynı sonucu elde etmek için, karşılaştırıcıya ikincil anahtarı elle katıp bileşik (composite) bir karşılaştırma yazmanız gerekir — yapılabilir ama daha karmaşık ve hataya açıktır. Bu yüzden kullanıcı arayüzlerindeki tablo sütun başlıklarına tıklayarak yapılan sıralamalar neredeyse her zaman kararlı algoritma bekler: kullanıcı önce bir sütuna, sonra başka bir sütuna göre sıralar ve önceki düzenin korunmasını sezgisel olarak umar.

### Hangisi Kararlı?

- **Mergesort:** Doğal olarak kararlıdır (merge'de eşitlikte soldakini önce alarak).
- **Insertion sort ve bubble sort:** Kararlıdır.
- **Quicksort:** Standart hâliyle kararsızdır — partition sırasındaki uzak takaslar göreli sırayı bozar.
- **Heapsort:** Kararsızdır.

Kararsız bir algoritmayı yapay olarak kararlı hâle getirmenin klasik hilesi, her elemana orijinal indeksini eklemek ve eşitlik durumunda bu indekse göre karar vermektir. Ancak bu, ek bellek ve karşılaştırma maliyeti getirir.

## Timsort

### Tanım

Timsort, Tim Peters tarafından 2002'de Python için tasarlanmış hibrit bir sıralama algoritmasıdır. **Mergesort ile insertion sort'un** akıllı bir birleşimidir. Python'un `list.sort()` ve `sorted()` fonksiyonlarının, ayrıca Java'nın nesne dizileri için `Arrays.sort()` çağrısının varsayılan algoritmasıdır. Kararlı ve en kötü durumda O(n log n)'dir.

### Kök Neden: Neden Gerçek Dünya Verisi İçin Tasarlandı?

Timsort'un dâhiyane sezgisi şudur: **gerçek dünyadaki veri nadiren tamamen rastgeledir; genellikle kısmen sıralıdır.** Loglar zamana göre neredeyse sıralıdır, birleştirilmiş listelerde uzun artan veya azalan bölümler bulunur. Klasik algoritmalar bu yapıyı görmezden gelir; Timsort ise onu **istismar eder.**

Timsort, diziyi tarayarak zaten sıralı ardışık bölümleri — **"run"** adı verilir — tespit eder. Artan run'ları olduğu gibi alır, azalan run'ları ters çevirir. Doğal run'lar bir minimum uzunluğun (minrun, tipik olarak 32-64) altındaysa, insertion sort ile o uzunluğa tamamlanır; çünkü insertion sort küçük ve neredeyse-sıralı diziler için son derece hızlıdır (düşük sabit çarpan, az veri hareketi). Sonra bu run'lar, dengeyi koruyan kurallara göre merge edilir.

Tamamen sıralı bir girdide Timsort **O(n)'e yaklaşır** — tek bir dev run bulur ve neredeyse hiç iş yapmaz. Bu, "en iyi durum O(n)" özelliğidir ve klasik mergesort'un sunamadığı bir avantajdır.

### Merge Değişmezleri (Invariants) ve Galloping

Timsort, tespit ettiği run'ları bir yığında (stack) tutar ve boyutları arasında belirli **değişmezleri (invariant)** korur; bu kurallar merge'lerin dengeli kalmasını, yani birbirine yakın boyuttaki run'ların birleştirilmesini sağlar. Dengeli merge, toplam çalışmayı O(n log n)'de tutar. (Not: Timsort'un ilk sürümlerinde bu değişmezlerin belirli bir durumda tam olarak korunmadığı, biçimsel doğrulama çalışmalarıyla ortaya çıkmış ve minimum yığın boyutu düzeltilmiştir; ayrıntılarını burada kesin sayılarla vermekten kaçınıyorum çünkü uygulamaya göre değişebilir.)

İkinci akıllı optimizasyon **"galloping" (dörtnala) modudur.** İki run merge edilirken, bir run'dan sürekli olarak elemanlar seçiliyorsa (yani biri diğerine kıyasla tutarlı biçimde küçükse), Timsort tek tek karşılaştırma yapmayı bırakıp ikili arama (binary search) benzeri sıçramalarla büyük bloklar hâlinde kopyalamaya geçer. Bu, bir listenin diğerinin tamamen önünde/arkasında olduğu durumları O(n) yerine O(log n)'e yaklaştırır.

### Doğru Kullanım ve Tuzaklar

Timsort'u çoğu programcı doğrudan yazmaz; dilin standart kütüphanesi üzerinden kullanır. Buradaki asıl "doğru kullanım" meselesi, **iyi bir karşılaştırıcı (comparator) yazmaktır.** Java'da `Comparator`'ın sözleşmesini ihlal etmek — örneğin geçişli (transitive) olmayan veya tutarsız bir karşılaştırıcı yazmak — Timsort'un "Comparison method violates its general contract!" istisnası fırlatmasına yol açar. Bu, algoritmanın bir hatası değil, sizin karşılaştırıcınızın matematiksel bir sıralama bağıntısı tanımlamadığının teşhisidir: karşılaştırıcı, tam sıralama (total order) aksiyomlarını (dönüşsüzlük, antisimetri, geçişlilik) sağlamalıdır.

Bir başka incelik: Java'da **ilkel tip dizileri (int[], double[]) için `Arrays.sort` Timsort değil, ikili-pivot quicksort (dual-pivot quicksort) kullanır.** Bunun mantığı, ilkel tiplerin kararlılığa ihtiyaç duymamasıdır (iki eşit int ayırt edilemez), dolayısıyla yerinde ve önbellek-dostu quicksort daha uygundur. Nesneler için ise kararlılık önemli olabileceğinden Timsort seçilir. Bu ayrım, "aynı dilde neden iki farklı sıralama var?" sorusunun cevabıdır ve kararlılık ile veri türünün seçimi nasıl belirlediğini güzel özetler.

## Seçim Kriteri: Hangi Durumda Hangisi?

Şimdi tüm bu bilgiyi karar verilebilir bir çerçeveye oturtalım. Doğru algoritmayı seçmek, tek bir "en iyi" olmadığını, seçimin kısıtlara bağlı olduğunu kabul etmekle başlar.

**Genel amaçlı, in-memory, nesne sıralaması ve kararlılık gerekiyorsa → Timsort (yani dilin varsayılanı).** Modern dillerde `sort()` çağrısı zaten Timsort veya eşdeğeri bir hibrittir; kendi elinizle bir şey yazmaya kalkışmanız neredeyse her zaman hatadır. Standart kütüphane, on yılların mühendislik birikimini içerir.

**En kötü durum O(n log n) garantisi sözleşmesel olarak zorunluysa (gerçek zamanlı sistemler, saldırıya açık genel API'ler) → mergesort veya heapsort ya da introsort.** Quicksort'un O(n²) kuyruğu bir güvenlik ve öngörülebilirlik riski taşır.

**Bellek son derece kısıtlıysa ve en kötü durum garantisi de gerekiyorsa → heapsort.** O(1) ek bellek ve O(n log n) garantisini birlikte veren tek klasik seçenektir; önbellek yavaşlığını kabul etmeniz gerekir.

**Ham hız önemliyse, ortalama durum yeterliyse, veri ilkel tip ve önbellek-dostluğu kritikse → quicksort (tercihen randomize pivot + median-of-three + küçük dizilerde insertion sort, yani introsort).** Pratikte en hızlı in-place seçenektir.

**Bağlı liste (linked list) sıralıyorsanız → mergesort.** İşaretçi yeniden bağlamayla ek bellek gerektirmeden, rastgele erişim ihtiyacı olmadan çalışır; quicksort burada zayıftır.

**Veri belleğe sığmıyorsa (harici sıralama, terabaytlarca dosya) → mergesort tabanlı external sort.** Parçala, her parçayı sırala, sıralı parçaları merge et.

**Anahtar aralığı küçük ve tamsayı/sabit uzunlukta ise → counting sort veya radix sort.** Karşılaştırma yapmadıkları için O(n) mertebesine inebilirler; ama yalnızca uygun veri türlerinde ve bellek maliyetini göze alarak.

**Küçük diziler (birkaç düzine eleman) → insertion sort.** Düşük sabit çarpan, önbellek-dostu, kararlı. Bu yüzden tüm gelişmiş algoritmalar küçük alt dizilerde insertion sort'a düşer.

### En İyi Pratikler Özeti

Deneyimli mühendisin yaklaşımı şudur: **Önce standart kütüphanenin sıralamasını kullan.** Kendi sıralama algoritmanı yazma; ölçmeden optimize etme. Eğer profil çıkarınca sıralama gerçekten darboğaz (bottleneck) çıkarsa, o zaman kısıtlarını (bellek, kararlılık, veri türü, en kötü durum, veri yapısı) netleştir ve bu makaledeki karar çerçevesine göre seç. Karşılaştırıcı yazarken tam sıralama aksiyomlarına sadık kal; tutarsız karşılaştırıcı, en sinsi ve teşhisi zor hatalardan biridir. Güvenlik sınırında çalışan sistemlerde quicksort'un patolojik durumunu bir saldırı yüzeyi olarak değerlendir ve randomizasyon ya da introsort ile koru.

Son olarak, sıralama algoritmalarını öğrenmenin asıl değeri belirli bir dizini sıralamak değil, **böl-ve-yönet, veri yerelliği (data locality), en kötü duruma karşı ortalama durum, uzay-zaman ödünleşimi (space-time tradeoff) ve teorik alt sınırlar** gibi bilgisayar biliminin çekirdek fikirlerini tek bir somut problem üzerinde bir arada görmektir. Bu fikirler, karşınıza çıkacak sayısız başka problemde de pusulanız olacaktır.
