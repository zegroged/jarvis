# Greedy (Açgözlü) ve Böl-Yönet Algoritma Tasarım Paradigmaları

Algoritma tasarımında "paradigma" dediğimiz şey, farklı problemlere uygulanabilen genel bir çözüm iskeletidir. Greedy (açgözlü) ve divide-and-conquer (böl-yönet), en çok kullanılan iki paradigmadır. İkisi de bir problemi daha küçük parçalara indirgeyerek çözer; ama parçalara bakış açıları temelden farklıdır. Bu makale her iki paradigmanın da nasıl çalıştığını, neden çalıştığını (ya da çalışmadığını) ve doğru kullanımını derinlemesine inceler. Özellikle greedy'nin ne zaman doğru sonuç verdiğini kanıtlama tekniklerine, MST (Minimum Spanning Tree) örneğine ve böl-yönet'in çalışma süresi analizine yoğunlaşacağız.

## Greedy (Açgözlü) Paradigması

### Tanım ve Temel Fikir

Greedy algoritma, bir çözümü adım adım inşa eder ve her adımda o an için **en iyi görünen yerel seçimi** (locally optimal choice) yapar; bu seçimi bir daha geri almaz. "Açgözlü" adı buradan gelir: algoritma gelecekteki sonuçları düşünmeden, o anki kazancı maksimize eder. Umut şudur: yerel olarak optimal seçimlerin dizisi, global olarak optimal (globally optimal) bir çözüme ulaştırır.

Bir örnek olarak Türk parası bozdurma problemini düşünelim. 87 kuruşu en az sayıda madeni parayla vermek isteyelim; elimizde 50, 25, 10, 5, 1 kuruşluk paralar olsun. Greedy yaklaşım: mümkün olan en büyük parayı seç, tekrarla. 50 → 25 → 10 → 1 → 1 = 5 madeni para. Bu, bu para sistemi için gerçekten de optimaldir. Ama dikkat: greedy'nin **her para sisteminde** çalışmadığını birazdan göreceğiz. İşte greedy'nin can alıcı noktası tam da budur.

### Kök Neden: Greedy Neden Bazen Çalışır, Bazen Çalışmaz?

Greedy'nin kalbinde iki özellik yatar. Bir problem greedy ile **doğru** çözülebiliyorsa, o problem şu iki koşulu sağlamak zorundadır:

**1. Greedy-choice property (açgözlü seçim özelliği):** Global optimal çözümlerden en az birine, her adımda yerel açgözlü seçim yaparak ulaşılabilir. Yani "şu an en iyi olanı seçmek" bizi asla optimal çözümün dışına atmaz. Bu, greedy'nin var oluş sebebidir. Dynamic programming'de tüm alt problemleri çözüp aralarından en iyisini seçeriz; greedy'de ise "seçimi önce yapar, sonra kalan tek alt problemi çözeriz". Fark budur: greedy geriye dönüp bakmaz.

**2. Optimal substructure (optimal alt yapı):** Problemin optimal çözümü, alt problemlerinin optimal çözümlerini içerir. Yani ilk açgözlü seçimi yaptıktan sonra geriye kalan problem, aynı türden daha küçük bir problemdir ve onun optimal çözümü, orijinalin optimal çözümüne katkıda bulunur.

Şimdi kök nedene inelim: **greedy neden başarısız olur?** Çünkü çoğu problemde yerel olarak en iyi seçim, global olarak kötü bir tuzağa götürür. Para bozdurma örneğine dönelim ama bu kez sistemimiz {1, 3, 4} kuruş olsun ve 6 kuruş vermek isteyelim. Greedy: en büyük olan 4'ü seç, kalan 2 için iki tane 1'lik → toplam 3 para (4+1+1). Oysa optimal çözüm 3+3 = 2 paradır. Greedy burada patladı, çünkü {1,3,4} sistemi greedy-choice property'yi sağlamıyor. 4'ü seçmek yerel olarak cazipti ama global tuzaktı.

Bu, greedy hakkında öğrenilmesi gereken en önemli derstir: **Greedy'nin sezgisel kolaylığı, doğruluk garantisi değildir.** Bir greedy algoritma yazmak beş dakika sürer; onun doğru olduğunu kanıtlamak ise işin asıl zor kısmıdır. Sezgi ile doğruluk burada birbirinden ayrılır.

### Greedy Doğruluğunu Kanıtlama Teknikleri

Greedy bir algoritmanın gerçekten optimal sonuç verdiğini göstermek için kabaca üç standart yöntem vardır. Bunları bilmek, "greedy'im doğru mu?" sorusuna disiplinli cevap verebilmek demektir.

**Exchange argument (değişim/takas argümanı):** En yaygın ve en güçlü tekniktir. Fikir şudur: Herhangi bir optimal çözüm alın (OPT). Greedy'nin çözümü (GREEDY) ile OPT'un ilk farklılaştığı noktaya bakın. OPT'taki o elemanı, greedy'nin seçtiği elemanla "takas edin" ve gösterin ki bu takas çözümü kötüleştirmez — en fazla eşit kalır. Bu takası tekrarlayarak OPT'u adım adım GREEDY'ye dönüştürebilirsiniz, kalitesini hiç düşürmeden. Sonuç: GREEDY de en az OPT kadar iyidir, yani optimaldir. Bu argümanın gücü, "greedy'nin seçimi asla zararlı değildir" fikrini formel olarak yakalamasıdır.

**"Greedy stays ahead" (greedy önde kalır):** Greedy çözümünün her adımda, herhangi bir alternatif çözümden en az bir metrik açısından "önde" ya da eşit olduğunu tümevarımla gösterirsiniz. Örneğin faaliyet seçimi (activity selection) probleminde, greedy'nin seçtiği i'nci faaliyetin bitiş zamanı, herhangi bir başka çözümün i'nci faaliyetinin bitiş zamanından her zaman erken ya da eşittir. Greedy hep önde olduğu için sonda en az bu kadar faaliyet sığdırabilir.

**Matroid teorisi:** Daha soyut ve teorik bir çerçevedir. Bir problemin yapısı bir "matroid" oluşturuyorsa, üzerinde greedy algoritmanın optimal sonuç vereceği matematiksel olarak garantidir. MST'nin greedy ile çözülebilmesinin altındaki derin sebep, spanning tree'lerin bir "grafik matroidi" oluşturmasıdır. Pratikte her gün kullanmasanız da, "greedy neden burada işe yarıyor?" sorusunun en temeldeki cevabı çoğu zaman matroid yapısıdır.

Bu tekniklerin ortak mesajı: **bir greedy algoritmayı yayınlamadan / production'a almadan önce doğruluğunu kanıtlayın ya da en azından karşı örnek arayarak sağlamlaştırın.** Kanıtlayamıyorsanız, muhtemelen dynamic programming gibi geriye bakabilen bir yönteme ihtiyacınız vardır.

### Somut Örnek: Faaliyet Seçimi (Activity Selection)

Elimizde başlangıç ve bitiş zamanları olan bir dizi faaliyet var; aynı anda tek faaliyet yapabiliyoruz ve maksimum sayıda çakışmayan (non-overlapping) faaliyet seçmek istiyoruz. Sezgi bize "en kısa faaliyeti seç" veya "en erken başlayanı seç" dedirtebilir — ama ikisi de yanlıştır, karşı örnekleri vardır.

Doğru greedy kural: **en erken biten faaliyeti seç.** Neden? Çünkü bir faaliyet ne kadar erken biterse, geriye kalan zaman dilimi o kadar geniş kalır, dolayısıyla gelecekte o kadar çok faaliyet için yer açılır. Bu, "greedy stays ahead" argümanıyla kanıtlanabilir: erken biten seçimimiz, kaynağı (zamanı) her adımda mümkün olan en verimli şekilde serbest bırakır. Algoritma faaliyetleri bitiş zamanına göre sıralar, sonra sırayla gezer ve son seçilenle çakışmayan ilk faaliyeti seçer. Karmaşıklık, sıralama nedeniyle O(n log n)'dir.

Buradaki ders: **doğru greedy kuralı bulmak, çoğu zaman problemin en zor kısmıdır.** Aynı probleme üç farklı greedy kural uygulanabilir, ama sadece biri doğrudur.

### Diğer Klasik Greedy Örnekleri

**Huffman kodlama:** Veri sıkıştırmada, sık geçen karakterlere kısa bit dizileri, seyrek geçenlere uzun diziler atayarak toplam uzunluğu minimize eder. Greedy kuralı: her adımda en düşük frekanslı iki düğümü birleştir. Bu, kanıtlanabilir biçimde optimal önek-serbest (prefix-free) kod üretir.

**Dijkstra en kısa yol:** Negatif kenar olmayan graflarda kaynaktan tüm düğümlere en kısa yolu bulur. Her adımda "henüz kesinleşmemiş, en yakın düğümü" kesinleştirir. Negatif kenar olduğunda bu greedy mantık çöker, çünkü ileride negatif bir kenar mesafeyi düşürebilir — greedy'nin "geri alamama" doğası burada onu yanlış yapar.

## Minimum Spanning Tree (MST): Greedy'nin Zaferi

### Problem ve Neden Önemli

Ağırlıklı, bağlı, yönsüz bir grafta MST, tüm düğümleri birbirine bağlayan (spanning), döngü içermeyen (tree) ve toplam kenar ağırlığı minimum olan alt graftır. Fiziksel sezgi: N şehri birbirine en az kablo/yol maliyetiyle bağlamak. MST, greedy paradigmasının en zarif ve kanıtlanabilir doğru uygulamalarından biridir, bu yüzden ders kitaplarının vazgeçilmezidir.

### Kök Neden: Cut Property (Kesit Özelliği)

MST'de greedy'nin neden çalıştığının tek cümlelik özü **cut property**'dir. Bir "cut" (kesit), düğümleri iki boş olmayan gruba ayırmaktır. Bir kesiti "geçen" (crossing) kenarlar, iki grup arasında köprü kuran kenarlardır. Cut property şunu söyler:

> Herhangi bir kesit için, o kesiti geçen kenarlar arasında **en hafif (minimum ağırlıklı) kenar, mutlaka bir MST'ye dahildir.** (Ağırlıklar benzersizse bu kenar her MST'de vardır.)

Neden doğru? Exchange argümanıyla: Diyelim en hafif geçen kenar e, bir MST T'de yok. T'ye e'yi eklersek bir döngü oluşur (çünkü T zaten spanning tree). Bu döngü, kesiti geçen başka bir f kenarı içermek zorundadır. e en hafif geçen kenar olduğundan, ağırlığı f'ten küçük ya da eşittir. f'i atıp e'yi koyarsak, hâlâ spanning tree elde ederiz ve toplam ağırlık artmamıştır. Yani e'yi içeren bir MST de vardır. İşte MST greedy algoritmalarının tamamı, bu tek teoremin farklı uygulamalarıdır.

### Kruskal Algoritması

Kruskal, kenar-merkezli düşünür. Tüm kenarları ağırlığa göre artan sırada sıralar, sonra en hafiften başlayarak sırayla gezer. Bir kenarı, **döngü oluşturmuyorsa** MST'ye ekler; oluşturuyorsa atlar. Döngü kontrolü için **Union-Find (Disjoint Set Union)** veri yapısı kullanılır: her kenarın iki ucu zaten aynı bileşende mi diye bakar. Aynı bileşendeyse eklemek döngü yaratır, atlanır.

Kruskal'ın cut property ile bağlantısı şudur: en hafif kenarı seçtiğimizde, o kenarın bağladığı iki bileşen bir kesit tanımlar ve seçtiğimiz kenar bu kesitin en hafif geçen kenarıdır — yani güvenle eklenebilir. Karmaşıklık, sıralama baskın olduğundan O(E log E) (eşdeğer olarak O(E log V)) düzeyindedir. Union-Find işlemleri, path compression ve union by rank ile neredeyse sabit zamanlıdır (ters Ackermann fonksiyonu, pratikte 4-5'i geçmez).

### Prim Algoritması

Prim, düğüm-merkezli düşünür. Tek bir başlangıç düğümünden başlar ve büyüyen bir ağaç tutar. Her adımda, ağaçtaki düğümler ile ağaç dışındaki düğümler arasındaki **en hafif kenarı** ekler, böylece ağaca bir düğüm daha katar. Burada kesit doğrudan görünür: "ağaçtaki düğümler" bir grup, "dışarıdakiler" diğer grup; Prim tam da bu kesitin en hafif geçen kenarını seçer. Cut property gereği bu seçim daima güvenlidir.

Verimli uygulama için priority queue (öncelik kuyruğu / min-heap) kullanılır. Binary heap ile karmaşıklık O(E log V)'dir. Fibonacci heap kullanılırsa teorik olarak O(E + V log V)'ye iner, ama Fibonacci heap'in sabit çarpanları büyük olduğu için pratikte çoğu zaman binary heap tercih edilir.

### Kruskal mı, Prim mi? Doğru Seçim

İkisi de aynı MST'yi (ağırlıklar benzersizse) üretir, seçim graf yoğunluğuna bağlıdır. **Seyrek graflarda (sparse, E ≈ V)** Kruskal genellikle rahat ve etkilidir; kenarları sıralamak yeterlidir. **Yoğun graflarda (dense, E ≈ V²)** Prim, özellikle adjacency matrix ile, daha iyi olabilir. Kruskal ayrıca graf en baştan bağlı değilse doğal olarak minimum spanning **forest** üretir. Buradaki ders: paradigma aynı (greedy + cut property) olsa bile, veri yapısı seçimi performansı belirler.

## Böl-Yönet (Divide and Conquer) Paradigması

### Tanım ve Üç Adım

Böl-yönet, bir problemi tekrarlı (recursive) olarak şu üç adımla çözer:

1. **Divide (Böl):** Problemi, aynı türden daha küçük alt problemlere ayır.
2. **Conquer (Yönet/Çöz):** Alt problemleri tekrarlı olarak çöz. Alt problem yeterince küçükse (base case) doğrudan çöz.
3. **Combine (Birleştir):** Alt problemlerin çözümlerini birleştirerek orijinal problemin çözümünü elde et.

Greedy'den temel farkı: greedy tek bir yolda ilerler ve geri dönmez; böl-yönet ise problemi genellikle **birden fazla bağımsız alt probleme** böler ve hepsini çözer. Ayrıca alt problemler birbirinden bağımsızdır (dynamic programming'den farkı budur — DP'de alt problemler örtüşür/overlap eder).

### Kök Neden: Neden Bölmek Hızlandırır?

Böl-yönet'in gücü, çoğu zaman "combine" adımının, problemi sıfırdan çözmekten daha ucuz olmasından gelir. Bir örnekle bunu somutlaştıralım. n elemanlı bir diziyi sıralamak istiyoruz.

**Naif (kaba kuvvet) yaklaşım** — örneğin insertion sort — her elemanı yerine yerleştirmek için O(n) iş yapar, toplam O(n²). Peki neden bölmek işe yarar? Diziyi ikiye böldüğümüzde, her yarıyı sıralamak (n/2)² ≈ n²/4 iş demektir; iki yarı için n²/2. Zaten kaba kuvvetin yarısı! Bunu tekrar tekrar böldükçe, her seviyede yapılan toplam iş azalır. İşte kök neden budur: **O(n²) gibi süper-lineer bir maliyet fonksiyonu, girdiyi ikiye böldüğünüzde dörtte bire iner; bölmenin kendisi bu tasarruftan ucuzsa, net kazanç elde edilir.**

Merge sort'ta bölme bedava (sadece ortadan ikiye), birleştirme (merge) ise O(n). Her seviyede toplam O(n) merge işi yaparız ve log n seviye vardır, dolayısıyla toplam **O(n log n)**. O(n²)'den O(n log n)'e geçiş, büyük n için devrimseldir.

### Çalışma Süresi Analizi: Rekürans Bağıntıları ve Master Teoremi

Böl-yönet algoritmalarının süresi, bir **recurrence relation (yineleme bağıntısı)** ile ifade edilir. Genel form:

    T(n) = a · T(n/b) + f(n)

Burada:
- **a** = üretilen alt problem sayısı,
- **n/b** = her alt problemin boyutu (girdi b kat küçülür),
- **f(n)** = bölme ve birleştirme adımlarının maliyeti.

Master Theorem (Ana Teorem), bu formdaki reküransların çözümünü, f(n) ile n^(log_b a) ifadesini karşılaştırarak verir. Sezgisel açıklaması: rekürsiyon ağacında, yapraklarda yapılan iş (~n^(log_b a)) ile kökte/üst seviyelerde yapılan iş (~f(n)) yarışır; hangisi baskınsa toplam süreyi o belirler. Üç durum vardır:

- **Durum 1:** f(n), n^(log_b a)'dan polinom olarak küçükse, iş yapraklarda toplanır → **T(n) = Θ(n^(log_b a))**.
- **Durum 2:** f(n) ile n^(log_b a) aynı büyüklükteyse, her seviye eşit iş yapar (log n seviye) → **T(n) = Θ(n^(log_b a) · log n)**.
- **Durum 3:** f(n), n^(log_b a)'dan polinom olarak büyük ve düzenlilik koşulunu sağlıyorsa, iş kökte toplanır → **T(n) = Θ(f(n))**.

Somut kontroller:
- **Merge sort:** a=2, b=2, f(n)=Θ(n). log_2 2 = 1, yani n^1 = n. f(n)=n ile eşit → Durum 2 → **Θ(n log n)**. Rakamlar sezgiyle örtüşüyor.
- **Binary search:** a=1, b=2, f(n)=Θ(1). log_2 1 = 0, n^0 = 1. f(n)=1 ile eşit → Durum 2 → **Θ(log n)**.
- **Naif matris çarpımı (böl-yönet):** a=8, b=2, f(n)=Θ(n²). log_2 8 = 3, n³ baskın → Durum 1 → **Θ(n³)**. Buradan yola çıkarak Strassen algoritması alt problem sayısını 8'den 7'ye düşürür (a=7); log_2 7 ≈ 2.807, yani **Θ(n^2.807)** — bölme sayısını azaltmanın karmaşıklığı nasıl düşürdüğünün güzel bir örneği.

Master Theorem'in **sınırı** şudur: sadece a·T(n/b) formundaki, alt problemlerin eşit boyutta olduğu reküranslara uygulanır. Alt problemler farklı boyutlardaysa (örneğin quicksort'un dengesiz bölünmeleri) veya f(n) üç duruma da girmiyorsa (aradaki "gap" durumları), teoremi kullanamazsınız; Akra-Bazzi yöntemi ya da rekürsiyon ağacı / substitution yöntemiyle elle çözmek gerekir.

### Somut Örnekler ve İnce Noktalar

**Quicksort — ortalama vs. en kötü durum:** Quicksort bir pivot seçer, diziyi pivottan küçük ve büyük olarak ikiye bölerek (partition) tekrarlı sıralar. Pivot dengeli bölerse rekürans T(n)=2T(n/2)+O(n) → O(n log n). Ama pivot her seferinde en küçük/en büyük elemansa (örneğin zaten sıralı diziye sabit pivot seçimi), bölünme 1'e n-1 olur, T(n)=T(n-1)+O(n) → **O(n²)**. Ders: böl-yönet'in kazancı, bölmenin **dengeli** olmasına bağlıdır. Bu yüzden pratikte randomized pivot ya da median-of-three kullanılır — dengesizlik olasılığını yok etmek için.

**Merge sort'un tuzağı — bellek:** Merge sort O(n log n) garantisi verir ama tipik uygulamada birleştirme için O(n) ek bellek (auxiliary array) ister. Bellek kısıtlı ortamlarda bu bir dezavantajdır; quicksort in-place çalışabildiği için genellikle daha az bellek kullanır.

**Karatsuba çarpımı:** İki n-basamaklı sayının çarpımı okulda öğrettiğimiz yöntemle O(n²)'dir. Karatsuba, dört yerine üç alt çarpım yaparak (a=3, b=2) bunu **Θ(n^1.585)**'e indirir. Yine aynı ilke: alt problem sayısını azalt.

## Yaygın Hatalar

Her iki paradigmada da tekrar tekrar görülen tuzaklar şunlardır:

**Greedy'yi kanıtsız kullanmak.** En sık ve en tehlikeli hata. Bir greedy kural sezgisel olarak doğru "hissettiriyor" diye onu doğrulanmış saymak. Para bozdurma {1,3,4} örneği tam da bu tuzağın kanıtıdır. Kural: greedy yazdıysanız ya exchange argümanı ile kanıtlayın ya da bilinçli olarak karşı örnek arayın.

**Yanlış greedy kriterini seçmek.** Faaliyet seçiminde "en kısa süreliyi seç" gibi makul görünen ama yanlış kriterler. Doğru kriteri bulmak, birkaç aday kriteri küçük karşı örneklerle elemekten geçer.

**Greedy ile dynamic programming'i karıştırmak.** Alt problemler örtüşüyorsa ve ileri seçimler geçmişi etkiliyorsa, greedy genellikle yetersizdir; DP gerekir. 0/1 knapsack (sırt çantası) problemi greedy ile çözülemez (kesirli knapsack çözülebilir), çünkü bir eşyayı almak/almamak kararı bütünü etkiler.

**Böl-yönet'te base case'i yanlış kurmak.** Rekürsiyonun durma koşulunu unutmak ya da yanlış boyutta durdurmak, ya sonsuz rekürsiyona (stack overflow) ya da yanlış sonuca yol açar. n=1 veya n=0 durumunu her zaman açıkça ele alın.

**Combine adımının maliyetini küçümsemek.** Bölme ve tekrar çözme akılda kalırken, birleştirmenin maliyeti gözden kaçar. Oysa Master Theorem'de f(n) çoğu zaman toplam karmaşıklığı belirleyen taraftır. Combine O(n²) ise, akıllıca bölmenin faydası buharlaşır.

**Master Theorem'i uygulanamadığı yerde uygulamak.** Alt problemler eşit boyutta değilse ya da f(n) hiçbir duruma tam oturmuyorsa, teoremi zorlamak yanlış sonuç verir. Bu durumda rekürsiyon ağacı veya Akra-Bazzi gerekir.

**Dengesiz bölünmeyi görmezden gelmek.** Quicksort'un en kötü durumu gibi, "ortalama iyi" diye en kötü durumu ihmal etmek, adversarial (kötücül) girdilerle karşılaşınca üretimde performans çöküşüne (hatta DoS'a) yol açabilir. Randomizasyon bu yüzden önemlidir.

## En İyi Pratikler

**Önce doğruluk, sonra performans.** Bir greedy algoritma için doğruluk kanıtı, kodun kendisinden daha değerlidir. Kanıtlayamıyorsanız DP'ye geçin ya da küçük girdilerde brute-force ile çıktıyı karşılaştırın (property-based testing).

**Küçük karşı örneklerle test edin.** Hem greedy kriterlerini hem de böl-yönet birleştirmesini, elle çözülebilecek küçük girdilerde doğrulayın. Greedy'nin yanlışlığı genellikle çok küçük örneklerde ortaya çıkar.

**Reküransı yazmayı alışkanlık edinin.** Bir böl-yönet algoritması tasarlarken T(n) = a·T(n/b) + f(n) bağıntısını açıkça yazın; a, b ve f(n)'i doğru belirlemek, karmaşıklığı ve tasarım tercihlerini netleştirir. "Alt problem sayısını azaltabilir miyim?" (Strassen, Karatsuba) ve "combine'ı ucuzlatabilir miyim?" soruları optimizasyonun ana eksenleridir.

**Dengeyi koruyun.** Böl-yönet'te bölünmeyi mümkün olduğunca dengeli tutun; dengesizlik karmaşıklığı süper-lineere itebilir. Pivot seçiminde randomizasyon veya median stratejileri kullanın.

**Doğru veri yapısını seçin.** MST'de Kruskal için Union-Find, Prim için priority queue kritiktir; yanlış veri yapısı doğru paradigmayı yavaşlatır. Graf yoğunluğuna göre Kruskal/Prim seçimini bilinçli yapın.

**Paradigmayı probleme uydurun, tersini değil.** Greedy her yerde işe yaramaz; böl-yönet her problemde hızlandırmaz (bölme maliyeti kazançtan büyük olabilir). Problemin yapısını (greedy-choice property, optimal substructure, bağımsız alt problemler) analiz edip ona uygun paradigmayı seçmek, gücel ezberden çok daha değerlidir.

## Kapanış

Greedy ve böl-yönet, algoritma tasarımının iki temel refleksidir. Greedy, "her adımda en iyisini seç ve geri dönme" der; gücü sadeliğinde, tehlikesi ise kanıtsız kullanıldığında sessizce yanlış sonuç vermesindedir. Doğruluğu exchange argümanı, "stays ahead" ve nihayetinde matroid yapısıyla güvence altına alınır; MST bunun en temiz vitrinidir ve tüm MST algoritmalarının altında tek bir teorem — cut property — yatar. Böl-yönet ise "problemi böl, parçaları çöz, birleştir" der; gücü süper-lineer maliyetlerin bölünerek düşmesinden gelir, ve maliyeti rekürans bağıntıları ile — çoğu zaman Master Theorem ile — kesin biçimde analiz edilir. Her iki paradigmada da esas ustalık, algoritmayı yazmakta değil, **neden doğru ve ne zaman uygun olduğunu** kanıtlayabilmektedir.
