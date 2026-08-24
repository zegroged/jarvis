# İleri Graf Algoritmaları: Max-Flow/Min-Cut, Bağlılık/SCC, En Kısa Yol Varyantları, Eşleşme

## Giriş: Neden "temel" graf algoritmaları yetmiyor

BFS, DFS ve Dijkstra bir mühendisin ilk graf araçlarıdır; ama gerçek dünya problemlerinin büyük kısmı bu üç aracın doğrudan çözemediği yapıdadır. Bir ağ mühendisi kapasite planlarken, bir eşleştirme motoru iş-aday atarken, bir derleyici SCC (strongly connected components) ile döngü tespiti yaparken ya da bir finans sistemi negatif faiz oranlarıyla en kısa yolu hesaplarken, klasik algoritmalar ya yanlış sonuç verir ya da problemi hiç modelleyemez.

Bu makale dört ana başlığı ele alır: **maksimum akış/minimum kesit (max-flow/min-cut)**, **güçlü bağlı bileşenler (SCC)**, **negatif ağırlıklı ve tüm-çiftler en kısa yol algoritmaları (Bellman-Ford, Johnson)**, ve **iki parçalı eşleşme (bipartite matching, Hopcroft-Karp)**. Her biri için kök mantığı, doğru kullanımı, tuzakları ve savunma/tasarım açısından önemini anlatıyorum. Amaç ezberletmek değil, "bu algoritma neden bu şekilde çalışıyor" sorusuna cevap verip mühendisin doğru araç seçimini yapmasını sağlamak.

---

## 1. Maksimum Akış / Minimum Kesit (Max-Flow / Min-Cut)

### 1.1 Problem tanımı ve sezgi

Bir yönlü graf düşünün: her kenarın bir **kapasitesi** var (örneğin bir borunun litre/saniye taşıma limiti, bir ağın bant genişliği, bir lojistik hattının günlük taşıma kapasitesi). Bir **kaynak** düğüm (source, s) ve bir **hedef** düğüm (sink, t) var. Soru: s'den t'ye, kenar kapasitelerini aşmadan, kaç birim "akış" gönderebilirsiniz?

Bu soyut gibi görünse de şaşırtıcı derecede genel bir modeldir: iş atama problemleri, görüntü segmentasyonu (min-cut/max-flow görüntü işleme), proje planlamada kaynak tahsisi, dağıtım ağları, hatta bazı iki parçalı eşleşme problemleri max-flow'a indirgenebilir.

**Min-Cut Teoremi (Max-Flow Min-Cut Theorem)**: Bir ağdaki maksimum akış değeri, o ağı s ve t'yi ayıran iki parçaya bölen (kaynak tarafı ve hedef tarafı) en küçük toplam kapasiteli kesime (cut) eşittir. Bu, LP dualitesinin (doğrusal programlama ikilik teoremi) klasik bir örneğidir: birincil problem (maksimize akış) ile ikincil problem (minimize kesit) aynı optimal değere yakınsar. Bunu sezgisel olarak anlamak için: akış, "darboğaz" (bottleneck) tarafından sınırlanır; o darboğaz da tam olarak min-cut'tir. Daha fazla akış göndermek istediğinizde, mutlaka o en dar kesitten geçmeniz gerekir.

### 1.2 Ford-Fulkerson: kök mantık

Ford-Fulkerson yöntemi kavramsal olarak basittir ama detayları kritiktir:

1. Akışı sıfırla.
2. **Artık graf** (residual graph) oluştur: her kenar (u,v, kapasite c, mevcut akış f) için ileri yönde `c-f` kalan kapasite, geri yönde ise `f` kadar "geri alma" kapasitesi ekle.
3. s'den t'ye artık grafta bir **artırma yolu** (augmenting path) bul (DFS/BFS ile).
4. Yol bulunursa, o yol üzerindeki minimum artık kapasite kadar akış ekle (hem ileri kenarları azalt/artır hem karşıt kenarları güncelle).
5. Artırma yolu kalmayana kadar tekrar et.

**Neden geri kenarlar gerekli?** Çünkü Ford-Fulkerson açgözlü (greedy) bir algoritmadır; ilk başta yanlış bir yol seçebilir. Geri kenarlar algoritmaya "pişman olma" ve o kararı iptal etme imkanı tanır. Bu, algoritmanın doğruluğunun temelidir — geri kenarlar olmadan algoritma yerel optimumda takılabilir ve global maksimuma ulaşamaz.

**Tuzak — irrasyonel kapasitelerle sonlanmama**: Kapasiteler rasyonel değilse (teorik olarak), Ford-Fulkerson sonsuza kadar küçük artışlarla ilerleyip hiç sonlanmayabilir. Pratikte kapasiteler tamsayı olduğunda algoritma sonlanır, ama **kötü yol seçimiyle** (her adımda sadece 1 birimlik artış sağlayan yol seçilirse) adım sayısı kapasite değerine (O(E * max_flow)) bağlı kalır — bu pseudo-polinom zaman demektir ve kapasiteler büyükse (örneğin 2^32) pratik olarak çalışmaz.

### 1.3 Edmonds-Karp: BFS ile garanti

Edmonds-Karp, Ford-Fulkerson'un artırma yolunu **BFS ile (en kısa yol, kenar sayısı olarak)** seçen versiyonudur. Bu basit değişiklik zaman karmaşıklığını O(V*E^2) olarak garanti eder — kapasite değerlerinden bağımsız. Kök neden: en kısa artırma yolunu seçmek, her kenarın "doygunlaşma" (saturation) sayısını sınırlar; bir kenarın en fazla O(V) kere darboğaz olabileceği kanıtlanabilir.

### 1.4 Dinic Algoritması: pratikte tercih edilen

Dinic (Dinitz) algoritması, Edmonds-Karp'in fikrini genişletir:

1. BFS ile **seviye grafi** (level graph) oluştur — her düğümün s'ye olan mesafesini hesapla, sadece "ileri" (mesafe artan) kenarları tut.
2. Bu seviye grafinda DFS ile **bloke akış** (blocking flow) bul — yani tüm artırma yolları tükenene kadar çoklu yol boyunca akış it (bir DFS çağrısında birden fazla yol bulunabilir, "scaling" ile).
3. Seviye grafini yeniden oluştur, tekrarla.

Dinic O(V^2 * E) genel durumda, iki parçalı eşleşmede ise O(E * sqrt(V)) gibi çok daha iyi sınırlar verir (unit-capacity graf özel durumunda). Bu yüzden pratikte (rekabetçi programlama, gerçek dünya optimizasyon motorları) Ford-Fulkerson yerine hemen hemen her zaman Dinic ya da onun türevleri (örneğin ISAP, push-relabel/Goldberg-Tarjan) kullanılır.

**Push-Relabel (Goldberg-Tarjan)** farklı bir felsefe kullanır: global BFS/DFS yerine, her düğümde lokal olarak "fazla akışı" (excess flow) komşulara "iter" (push) ve gerektiğinde düğümün yüksekliğini (height/label) artırır. Yoğun graflarda (dense graphs) ve paralel/dağıtık ortamlarda Dinic'ten daha iyi performans gösterebilir.

### 1.5 Kullanım alanları ve savunma perspektifi

- **Kapasite planlama**: Bir ağ mimarisinde, s'den t'ye maksimum taşınabilir trafiği hesaplamak = max-flow. Min-cut ise "bu ağın en zayıf noktası nerede" sorusuna cevap verir — yani hangi kenar setini güçlendirirsen toplam kapasiteyi artırırsın. Bu, DDoS dayanıklılık planlamasında ve ağ darboğazı analizinde doğrudan kullanılır: bir savunmacı ağın min-cut'ini bulup o kesitteki bantgenişliğini/redundansiyi artırarak tek-nokta-hata (single point of failure) riskini azaltabilir.
- **Erişebilirlik/izolasyon analizi**: Min-cut, bir ağı iki parçaya ayırmanın en ucuz yolunu bulur; bu, segmentasyon (network segmentation) tasarlarken "bu iki bölgeyi ayırmak için en az kaç bağlantıyı kesmeliyim" sorusuna cevap verir — mikro-segmentasyon ve zero-trust mimarilerinde kullanılan bir düşünce çerçevesidir.
- **Proje/kaynak atama**: İş-makina atama, ders-sınıf atama gibi problemler max-flow'a indirgenebilir (kapasiteli iki parçalı eşleşme).

**Yaygın hata**: Max-flow'u doğrudan "en güvenilir yol" ya da "en düşük gecikmeli yol" problemiyle karıştırmak. Max-flow toplam kapasiteyi maksimize eder, gecikmeyi (latency) hiç hesaba katmaz — bu farklı bir optimizasyon hedefidir (genelde min-cost max-flow ile birleştirilir, kenar başına hem kapasite hem maliyet tanımlanır ve toplam maliyeti minimize ederken max akışı bulmaya çalışılır).

---

## 2. Bağlılık ve Güçlü Bağlı Bileşenler (SCC)

### 2.1 Neden önemli

Yönsüz graflarda "bağlantılı bileşen" (connected component) kavramı basittir: DFS/BFS ile ulaşılabilen düğümler aynı bileşendedir. Ama **yönlü** graflarda iş farklıdır: A'dan B'ye yol olması, B'den A'ya yol olduğu anlamına gelmez. **Güçlü Bağlı Bileşen (Strongly Connected Component, SCC)**, içindeki her düğüm çiftinin birbirine (her iki yönde de) ulaşabildiği maksimal alt kümedir.

SCC analizi, derleyicilerde döngü tespiti (data flow analysis, dependency cycles), sosyal ağ analizinde "karşılıklı etkileşim kümeleri" bulma, ve **paket/modül bağımlılık graflarında dairesel bağımlılığı (circular dependency) tespit etmede** kritik bir araçtır. Bir yazılım mimarisinde modül A modül B'ye, B de A'ya bağımlıysa, bu bir SCC'dir ve genelde kötü mimarinin işaretidir — SCC tespiti statik analiz araçlarının (build sistemleri, linter'lar) temel yapıtaşıdır.

### 2.2 Tarjan Algoritması: kök mantık

Tarjan algoritması tek bir DFS geçişinde tüm SCC'leri bulur — bu onu pratikte çok verimli yapar (O(V+E)). Mantık:

- Her düğüm için iki değer tutulur: **discovery time** (dfs sırasında keşfedilme sırası, `disc[]`) ve **low-link değeri** (`low[]`) — low-link, o düğümden DFS ağacı üzerinden (veya bir geri kenar/back-edge üzerinden) ulaşılabilecek en küçük discovery time'dir.
- Bir yığın (stack) tutulur; DFS'te her düğüm yığına itilir.
- Bir düğümün DFS'i bittiğinde, eğer `low[u] == disc[u]` ise (yani o düğüm kendi alt-ağacında hiçbir yerden daha erken keşfedilmiş bir ataya geri dönemiyor), o düğüm bir **SCC kökü**dür (root). Yığından o düğüme kadar olan tüm elemanlar patlatılarak (pop) bir SCC oluşturulur.

**Neden `low[u]==disc[u]` koşulu doğru çalışır?** Çünkü bu koşul, "bu düğümden aşağıda keşfedilen hiçbir düğüm, bu düğümden daha eski bir ataya geri-kenar (back-edge) ile bağlanamıyor" anlamına gelir — yani bu alt-ağaç dışarıya "kaçamıyor", kendi içinde kapalı bir döngü (veya tek başına bir düğüm) oluşturuyor. Yığın, "hala aktif SCC adayı" olan düğümleri tutar; bir düğüm tamamen işlenip yığından çıkarılmadıysa hala bir üst SCC'ye dahil olabilir potansiyeli taşır.

### 2.3 Kosaraju Algoritması: alternatif yaklaşım

Kosaraju iki DFS geçişi kullanır ve kavramsal olarak daha kolay anlaşılır (ama pratikte Tarjan kadar hızlı, cache-friendly değildir çünkü grafi tersine çevirmeyi gerektirir):

1. Orijinal grafta DFS yap, her düğümün **bitiş zamanına** (finish time) göre bir yığına/listeye ekle.
2. Grafın **tersini** (transpose graph, tüm kenarları ters çevir) al.
3. Ters grafta, bitiş zamanına göre azalan sırayla (en son biten önce) DFS yap; her yeni DFS ağacı bir SCC'dir.

Kök neden: bir SCC'nin "en geç biten" düğümü, o SCC'yi diğerlerinden ayıran topolojik bir sınır gibi davranır. Ters grafta bu sırayla DFS yapmak, farklı SCC'ler arasındaki yönlü bağlantıların "yanlışlıkla" birleştirilmesini engeller.

### 2.4 Uygulama ve tuzaklar

- **2-SAT problemi**: Boolean tatmin edilebilirlik probleminin özel bir hali (her klozde 2 literal), SCC ile polinom zamanda çözülür — bir değişken ve onun değili aynı SCC'deyse formül tatmin edilemez. Bu, kısıtlama çözücü (constraint solver) motorlarında kullanılır.
- **Yaygın hata**: SCC algoritmasını yönsüz graflarda kullanmak anlamsızdır (yönsüz graflarda zaten adı "bağlantılı bileşen"dir, basit DFS/Union-Find yeter). SCC'nin değerini yönlü graflarda görürsünüz.
- **Recursive DFS stack overflow**: Büyük graflarda (milyonlarca düğüm) recursive Tarjan/Kosaraju gerçek stack taşmasına (stack overflow) yol açabilir; production kodda iteratif (explicit stack kullanan) versiyonlar tercih edilmelidir.
- **Condensation graph**: Her SCC'yi tek bir düğüme "sıkıştırarak" (condense) elde edilen graf her zaman bir **DAG**'dir (Directed Acyclic Graph) — döngü içermez. Bu, karmaşık bağımlılık graflarını önce SCC ile sadeleştirip sonra topolojik sıralama uygulamanın (örneğin build sistemlerinde derleme sırası belirleme) standart yaklaşımıdır.

---

## 3. Negatif Ağırlıklı ve Tüm-Çiftler En Kısa Yol: Bellman-Ford ve Johnson

### 3.1 Dijkstra neden yetmiyor

Dijkstra algoritması **açgözlü** çalışır: en küçük mesafeli düğümü "kesinleşmiş" kabul edip bir daha geri dönmez. Bu varsayım, **negatif ağırlıklı kenar** olduğunda çökebilir — çünkü daha sonra keşfedilecek negatif bir kenar, "kesinleşmiş" sanılan bir mesafeyi daha da küçültebilir. Dijkstra bunu asla doğrulayamaz çünkü o düğüme bir daha bakmaz. Sonuç: negatif kenarlı graflarda Dijkstra **yanlış** (yanlış pozitif/negatif değil, doğrudan hatalı) sonuç üretebilir, hata da sessizce oluşur — algoritma "çalışır" ama yanlış mesafe döndürür.

### 3.2 Bellman-Ford: kök mantık ve gevşeme (relaxation)

Bellman-Ford, tüm kenarları **V-1 kez** gevşeterek (relax) çalışır. Gevşeme işlemi: `eğer dist[u] + weight(u,v) < dist[v] ise, dist[v] = dist[u] + weight(u,v)`.

**Neden V-1 tekrar yeterli?** Bir en kısa yolun en fazla V-1 kenardan oluşabileceği gerçeğine dayanır (V düğümlü bir grafta, döngü içermeyen bir yol en fazla V-1 kenar içerir). Her tam geçiş (pass), en kısa yolun "bir kenar daha uzunu"nu doğru hesaplamayı garanti eder; V-1 geçişten sonra tüm en kısa yollar (eğer negatif döngü yoksa) doğru şekilde hesaplanmış olur.

**Negatif döngü tespiti**: V. geçişi (yani V-1'inci tekrardan sonra bir kez daha) yapıp hala bir gevşeme mümkünse, grafta s'den ulaşılabilen bir **negatif ağırlıklı döngü** vardır — bu durumda "en kısa yol" kavramının matematiksel olarak bir anlamı kalmaz (döngüde sonsuza kadar dolanıp mesafeyi sonsuza kadar azaltabilirsiniz). Bu tespit kabiliyeti, finans sistemlerinde **arbitraj tespiti** (döviz kurları graf olarak modellenip kenar ağırlıkları -log(kur) alınırsa, negatif döngü = kar fırsatı) gibi gerçek dünya uygulamalarında doğrudan kullanılır.

Zaman karmaşıklığı O(V*E) — Dijkstra'nın O(E log V) veya O(E + V log V)'sine göre yavaştır, ama negatif kenarlarla çalışabilme yeteneği bunun bedelidir.

### 3.3 SPFA ve pratik optimizasyonlar

SPFA (Shortest Path Faster Algorithm), Bellman-Ford'un kuyruk tabanlı (queue-based) bir optimizasyonudur — sadece mesafesi değişen düğümlerin komşularını tekrar gevşetmeye çalışır. Ortalama durumda hızlıdır ama **kötü durumda (worst case) hala O(V*E)** kalır ve bazı adversarial (kötü niyetli/düşman) graf yapılarında kolayca bu kötü duruma düşürülebilir — bu yüzden rekabetçi programlama dışında, garantili performans gereken production sistemlerde dikkatli kullanılmalıdır.

### 3.4 Johnson Algoritması: tüm-çiftler en kısa yol + negatif kenarlar

Floyd-Warshall (klasik tüm-çiftler algoritması, O(V^3)) negatif kenarlarla çalışabilir ama yoğun olmayan (sparse) graflarda gereksiz yavaştır. Johnson algoritması, **negatif kenarlı seyrek graflarda** tüm-çiftler en kısa yolu daha verimli (O(V^2 log V + VE)) hesaplamak için Bellman-Ford ve Dijkstra'yı birleştirir:

1. Grafa yeni bir "hayali" düğüm `q` ekle, `q`'dan her düğüme 0 ağırlıklı kenar çek.
2. `q`'dan Bellman-Ford çalıştırarak her düğüm için bir `h(v)` değeri (potansiyel) hesapla. (Bu adım negatif döngü varlığını da tespit eder.)
3. Her kenar ağırlığını **yeniden ağırlıklandır** (reweight): `w'(u,v) = w(u,v) + h(u) - h(v)`. Bu dönüşüm, matematiksel olarak (üçgen eşitsizliği sayesinde) tüm kenar ağırlıklarını **negatif olmayan** hale getirir, ama iki düğüm arasındaki en kısa yolun **hangi yol olduğunu** değiştirmez (sadece toplam değeri kaydırır, sıralamayı korur).
4. Artık negatif kenar olmadığı için her düğümden Dijkstra çalıştırılabilir (V kere) — bu Floyd-Warshall'dan çok daha hızlıdır seyrek graflarda.
5. Gerçek mesafeleri geri elde etmek için `dist(u,v) = dist'(u,v) - h(u) + h(v)` formülüyle "un-reweight" yapılır.

**Kök neden bu iş oluyor**: Potansiyel fonksiyonu `h(v)`, tüm kenarlar üzerinde "telafi edici" bir dönüşüm uygular; bu, A* algoritmasındaki heuristik fonksiyon mantığına çok benzer (aslında Johnson'in reweighting'i ile A*'in potansiyel fonksiyonları matematiksel olarak akrabadır).

### 3.5 Güvenlik ve mühendislik perspektifi

- **Ağ yönlendirme protokolleri**: BGP/OSPF gibi protokollerde, "en kısa yol" hesaplarının manipüle edilmesi (route hijacking, kötü niyetli düşük-maliyetli rota reklamı) bir saldırı vektörüdür. Bellman-Ford tabanlı protokoller (distance-vector, örneğin RIP) **count-to-infinity** problemine açık olabilir — bir döngü oluştuğunda mesafeler yavaş yavaş sonsuza doğru artar; savunma olarak split-horizon, poison-reverse gibi teknikler kullanılır. Bu, saf Bellman-Ford'un dağıtık/gerçek-zamanlı ağ ortamlarında neden dikkatli uygulanması gerektiğini gösterir.
- **Girdi doğrulama**: Kullanıcıdan gelen kenar ağırlıklarıyla çalışan sistemlerde (fiyatlandırma motorları, rota planlayıcıları), negatif değer enjekte edilerek döngü oluşturulup oluşturulamayacağı düşünülmelidir — doğrulama katmanı, negatif döngü tespiti (Bellman-Ford'un doğal yan ürünü) ile birlikte tasarlanmalıdır.

---

## 4. İki Parçalı Eşleşme (Bipartite Matching) ve Hopcroft-Karp

### 4.1 Problem ve motivasyon

İki parçalı graf: düğümler iki ayrı kümeye (L ve R) bölünür, kenarlar sadece L-R arasında olur (L-L veya R-R kenar yok). **Eşleşme (matching)**, hiçbir düğümün birden fazla kenara dahil olmadığı bir kenar altkümesidir. **Maksimum eşleşme**, mümkün olan en çok kenarı içeren eşleşmedir.

Gerçek dünya örnekleri: iş-aday atama, öğrenci-okul yerleştirme, görev-işlemci atama, reklam-slot eşleştirme. Bu problemler doğrudan "kim kime atansın ki toplam atama sayısı (veya toplam değer) maksimal olsun" sorusudur.

### 4.2 Artırma yolu (augmenting path) mantığı

Temel algoritma fikri (Kuhn's algorithm / Hungarian method'un basitleştirilmiş hali): Mevcut bir eşleşme varken, eşlenmeyen bir L düğümünden başlayıp **eşlenmeyen bir kenar - eşlenmiş bir kenar - eşlenmeyen bir kenar - ...** şeklinde alternatif giden bir yol bulunursa (bu yol eşlenmemiş bir R düğümünde biterse), bu yoldaki eşlenmiş/eşlenmemiş durumları **ters çevirerek** (flip) eşleşme sayısını bir artırabilirsiniz.

**Berge Teoremi**: Bir eşleşme maksimaldir ancak ve ancak grafta artırma yolu kalmamışsa. Bu teorem, tüm bipartite matching (ve genel graf matching) algoritmalarının doğruluk temelidir — algoritma "artırma yolu bulamıyorum" diyene kadar durmaz, ve bulamadığında matematiksel olarak maksimum olduğunu kanıtlar.

Naif yaklaşım: her eşlenmemiş L düğümünden DFS ile bir artırma yolu ara, bulursan ters çevir. Bu O(V*E) zaman alır (V kere DFS, her biri O(E)).

### 4.3 Hopcroft-Karp: neden daha hızlı

Hopcroft-Karp, Dinic'in bloke akış (blocking flow) fikrine çok benzer bir strateji kullanır:

1. BFS ile, tüm eşlenmemiş L düğümlerinden başlayarak **en kısa** artırma yollarının uzunluğunu bul (katmanlı/level yapısı oluştur).
2. DFS ile, bu en kısa uzunluktaki **birden fazla ayrık (vertex-disjoint) artırma yolunu aynı fazda** bul ve hepsini birden uygula (maksimal set of shortest augmenting paths).
3. Artırma yolu kalmayana kadar tekrarla.

**Kök neden bu daha hızlı**: Kanıtlanabilir ki, bu algoritma en fazla O(sqrt(V)) fazda tamamlanır (her fazda en kısa artırma yolu uzunluğu kesinlikle artar, ve bir noktadan sonra kalan maksimum eşleşmeye olan "mesafe" sqrt(V) ile sınırlanır). Her faz O(E) zaman alır, toplamda O(E*sqrt(V)) — bu, büyük ve yoğun graflarda naif O(V*E)'ye göre ciddi bir iyileştirmedir.

Bu, Dinic'in max-flow'daki unit-capacity özel durumuyla matematiksel olarak doğrudan ilişkilidir: aslında bipartite matching, kaynak-L-R-hedef şeklinde bir max-flow problemine indirgenebilir (her kenar kapasitesi 1), ve Hopcroft-Karp bu özel yapıdaki Dinic'in bir varyantıdır.

### 4.4 Genellemeler ve tuzaklar

- **Ağırlıklı eşleşme (assignment problem)**: Eğer amaç sadece eşleşme sayısını değil, toplam "değer"i (örneğin iş-aday atamasında toplam uyum skorunu) maksimize etmekse, bu **Macar Algoritması (Hungarian Algorithm / Kuhn-Munkres)** ile çözülür — O(V^3). Basit Hopcroft-Karp ağırlıksız problem içindir; ağırlıklı versiyonla karıştırmak yaygın bir hatadır.
- **Genel graf eşleşme (non-bipartite)**: İki parçalı olmayan graflarda (örneğin herkesin herkesle eşleşebildiği bir sosyal ağ) Edmonds' Blossom algoritması gerekir — çünkü tek-sayıda düğümden oluşan tek-çevrimler (odd cycles) artırma yolu mantığını bozar ("çiçek/blossom" oluşur ve bu yapı özel olarak "sıkıştırılmalıdır"). Bipartite algoritmaları genel graflara doğrudan uygulamak yanlış sonuç üretir.
- **Kapasiteli/çoklu-eşleşme durumları**: Bir L düğümünün birden fazla R düğümüyle eşleşebildiği (örneğin bir sunucu birden fazla isteği karşılayabiliyor) durumlarda, problem max-flow'a (kapasiteli kenarlarla) genellenir; saf bipartite matching yetersiz kalır.

### 4.5 Sistem tasarımı açısından önemi

Kaynak tahsis motorları (scheduler'lar, load balancer'lar, iş atama sistemleri) sıkça bu algoritmaların üzerine inşa edilir. Yanlış algoritma seçimi (örneğin ağırlıklı problem için ağırlıksız algoritma kullanmak, ya da genel graf için bipartite algoritma kullanmak) **sessizce yanlış** (suboptimal ama "çalışıyor gibi görünen") sonuçlar üretir — bu tür hatalar test edilmesi en zor hata sınıflarıdır çünkü kod "crash" etmez, sadece optimal olmayan bir çözüm döndürür.

---

## 5. Özet Karşılaştırma ve Seçim Rehberi

| Problem | Algoritma | Zaman Karmaşıklığı | Kullanım Anında Karar Kriteri |
|---|---|---|---|
| Max akış | Edmonds-Karp | O(V*E^2) | Basit, garantili, küçük-orta graf |
| Max akış | Dinic | O(V^2*E), unit-cap O(E*sqrt(V)) | Pratikte varsayılan tercih |
| SCC | Tarjan | O(V+E) | Tek geçiş, production tercih |
| SCC | Kosaraju | O(V+E) | Kavramsal netlik, eğitim |
| En kısa yol (negatif kenar) | Bellman-Ford | O(V*E) | Negatif kenar + döngü tespiti gerekli |
| Tüm-çiftler (seyrek, negatif) | Johnson | O(V^2 log V + VE) | Seyrek graf + negatif kenar |
| Tüm-çiftler (yoğun) | Floyd-Warshall | O(V^3) | Küçük/yoğun graf, basitlik |
| Bipartite eşleşme | Hopcroft-Karp | O(E*sqrt(V)) | Ağırlıksız, büyük iki parçalı graf |
| Ağırlıklı eşleşme | Hungarian (Kuhn-Munkres) | O(V^3) | Toplam değer maksimizasyonu |

## Kapanış: Ortak Tema

Bu dört başlığın hepsinde tekrar eden bir desen var: **açgözlü (greedy) yaklaşımların ne zaman başarısız olduğunu anlamak**, doğru algoritma seçiminin anahtarıdır. Dijkstra'nın açgözlülüğü negatif kenarda kırılır (Bellman-Ford gerekir); naif DFS/BFS'in "tek yönlü ulaşılabilirlik" varsayımı yönlü graflarda kırılır (SCC gerekir); açgözlü ilk-bulunan-yolu-kullan yaklaşımı max-flow'da yanlış olabilir (residual/geri kenar gerekir); ve tek-tek eşleşme aramak büyük ölçekte yavaştır (katmanlı/BFS-tabanlı toplu işleme gerekir). İleri seviye graf algoritmalarını öğrenmek, aslında "bu açgözlü varsayım ne zaman geçerli, ne zaman değil" sorusunu sistemli şekilde sormayı öğrenmektir — bu da hem doğru mühendislik kararlarının hem de sistem güvenliği/dayanıklılık analizinin temelini oluşturur.
