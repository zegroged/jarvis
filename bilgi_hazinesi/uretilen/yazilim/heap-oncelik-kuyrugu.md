# Heap ve Öncelik Kuyruğu

## Tanım: Öncelik Kuyruğu Nedir, Heap Nedir?

Bir **öncelik kuyruğu** (priority queue), her elemanın bir *önceliğe* sahip olduğu ve her çıkarma işleminde önceliği en yüksek (ya da tanıma göre en düşük) elemanın verildiği soyut bir veri tipidir (abstract data type). Sıradan bir kuyruğun (FIFO) aksine, çıkma sırasını ekleme sırası değil, elemanların öncelik değeri belirler. İki temel işlemi vardır: yeni bir eleman *ekleme* (`insert` / `push`) ve en öncelikli elemanı *çıkarma* (`extract-min` / `extract-max` / `pop`).

Öncelik kuyruğu bir *arayüzdür*; bunu somut olarak gerçekleştiren birden fazla veri yapısı vardır. En yaygın ve pratikte en çok kullanılan gerçekleştirme **binary heap** (ikili yığın) yapısıdır. Bu makalede önce binary heap'in nasıl ve neden çalıştığını kökten anlatacağım, sonra işlemleri, ardından Dijkstra ve top-k gibi gerçek uygulamaları ele alacağım.

Bir **binary heap**, iki koşulu aynı anda sağlayan bir ikili ağaçtır:

1. **Şekil özelliği (shape / completeness):** Ağaç *tam* (complete) bir ikili ağaçtır. Yani en alt seviye hariç bütün seviyeler tamamen doludur, ve en alt seviye soldan sağa doğru boşluksuz doldurulur.
2. **Heap özelliği (heap property):** Bir **min-heap**'te her düğümün değeri, çocuklarının değerinden küçük veya eşittir; dolayısıyla en küçük eleman *daima* köktedir. Bir **max-heap**'te tersine her düğüm çocuklarından büyük veya eşittir ve en büyük eleman köktedir.

Dikkat edilmesi gereken kritik nokta: heap özelliği *global bir sıralama değildir*. Binary heap **kısmen sıralıdır** (partially ordered). Sadece ata-torun (ancestor-descendant) ilişkisi boyunca bir düzen garanti edilir; kardeş düğümler arasında hiçbir sıra garantisi yoktur. Bu, heap'in neden hızlı olduğunun da anahtarıdır: tam sıralama tutmak zorunda olmadığı için daha az iş yapar.

## Kök Neden: Neden Dizi Üzerinde ve Neden log(n)?

### Şekil özelliği diziyle temsili mümkün kılar

Binary heap'in en zarif tarafı, ağaç yapısını *hiç pointer kullanmadan* düz bir dizi (array) üzerinde temsil edebilmesidir. Bunun kök nedeni tam ikili ağaç olma zorunluluğudur. Ağaç tam olduğu için, seviyeleri soldan sağa gezerek elemanları 0'dan başlayarak dizinlersek, indeks aritmetiğiyle ebeveyn-çocuk ilişkisini hesaplayabiliriz. 0-tabanlı bir dizide, `i` indeksindeki düğüm için:

- Sol çocuk: `2*i + 1`
- Sağ çocuk: `2*i + 2`
- Ebeveyn: `(i - 1) / 2` (tam sayı bölmesi)

Neden bu formüller çalışır? Çünkü tam ağaçta hiç "boşluk" yoktur; her seviye önceki seviyenin iki katı düğüm barındırır (son seviye hariç) ve düğümler kesintisiz sıralanır. Bu kesintisizlik, konumdan matematiksel olarak akrabalık çıkarmayı olanaklı kılar. Eğer ağaç tam olmasaydı bu aritmetik çöker, ortada boş hücreler tutmak zorunda kalırdık ve bellek israfı olurdu.

Bu diziyle temsilin iki büyük pratik faydası vardır. Birincisi, ekstra pointer belleği harcanmaz. İkincisi ve çoğu zaman daha önemlisi, veri bellekte bitişik (contiguous) durur; bu da **cache locality** (önbellek yerelliği) demektir. Modern CPU'larda bitişik belleğe erişim, işaretçilerle rastgele bellek gezmekten kat kat hızlıdır. Bu yüzden binary heap, teorik olarak benzer karmaşıklığa sahip pointer tabanlı yapılardan (ör. dengeli arama ağaçları) sabit-çarpan olarak genelde daha hızlı çalışır.

### Neden yükseklik log(n) ve işlemler O(log n)?

Tam bir ikili ağaçta `n` düğüm varsa, ağacın yüksekliği `⌊log₂ n⌋` mertebesindedir. Sezgisi basittir: her seviye bir öncekinin iki katı düğüm alır, yani `n` düğümü barındırmak için yaklaşık `log₂ n` seviye gerekir. Heap işlemlerinin ana maliyeti, bir elemanı ağaç boyunca yukarı veya aşağı taşımaktır; bu taşımalar en fazla ağacın yüksekliği kadar adım sürer. Dolayısıyla ekleme ve çıkarma **O(log n)**'dir. Kök nedeni budur: tam ağacın logaritmik yüksekliği, tüm "düzeltme" işlemlerine bir tavan koyar.

## Temel İşlemler: Sift-up ve Sift-down

Heap'i doğru tutan iki temel iç işlem vardır. Bunlara literatürde çeşitli isimler verilir: **sift-up** (yukarı süzme; ayrıca *bubble-up*, *swim*, *heapify-up*) ve **sift-down** (aşağı süzme; ayrıca *bubble-down*, *sink*, *heapify-down*). Bütün genel heap operasyonları bu ikisinin üstüne kurulur. Aşağıdaki açıklamalar min-heap içindir; max-heap için karşılaştırmaların yönünü tersine çevirmek yeterlidir.

### Ekleme (insert / push) — sift-up

Neden böyle çalışır? Şekil özelliğini bozmamak için yeni eleman *tek doğru yere*, yani dizinin sonuna (ağacın en alt seviyesinde en soldaki boş konuma) eklenir. Bu ekleme şekil özelliğini korur ama heap özelliğini geçici olarak bozabilir: yeni eleman ebeveyninden küçük olabilir. Bunu düzeltmek için eleman ebeveyniyle karşılaştırılır; ondan küçükse yer değiştirilir ve bu işlem, eleman ebeveyninden büyük/eşit olana veya köke ulaşana kadar tekrarlanır. Buna sift-up denir.

```
def push(heap, x):
    heap.append(x)          # sona ekle, sekil ozelligi korunur
    i = len(heap) - 1
    while i > 0:
        parent = (i - 1) // 2
        if heap[i] < heap[parent]:   # min-heap kurali
            heap[i], heap[parent] = heap[parent], heap[i]
            i = parent
        else:
            break
```

En fazla kökten yaprağa kadar olan yol boyunca ilerlediği için maliyet **O(log n)**.

### En öncelikli elemanı çıkarma (extract-min / pop) — sift-down

Kök her zaman minimumdur, yani cevabımız `heap[0]`'dır. Ama kökü çıkarınca ağacın tepesinde bir boşluk oluşur; bunu düzgün doldurmak gerekir. Burada zarif bir hile vardır: dizinin *son* elemanını alıp köke koyarız. Neden son eleman? Çünkü onu çekip çıkarmak şekil özelliğini bozmaz (yaprakların en sağdakini kaldırmış oluruz). Sonra bu yanlış yere konmuş kökü sift-down ile aşağı süzeriz: her adımda düğümü *iki çocuğundan küçük olanıyla* karşılaştırıp gerekiyorsa takas ederiz, ta ki heap özelliği geri gelene kadar.

```
def pop(heap):
    top = heap[0]
    last = heap.pop()             # son elemani cikar
    if heap:
        heap[0] = last            # koke koy
        i, n = 0, len(heap)
        while True:
            l, r = 2*i + 1, 2*i + 2
            smallest = i
            if l < n and heap[l] < heap[smallest]:
                smallest = l
            if r < n and heap[r] < heap[smallest]:
                smallest = r
            if smallest == i:
                break             # heap ozelligi saglandi
            heap[i], heap[smallest] = heap[smallest], heap[i]
            i = smallest
    return top
```

Kritik bir tuzak: sift-down'da düğümü *daha küçük olan çocukla* takas etmek zorunludur. Eğer büyük olan çocukla takas ederseniz heap özelliğini hemen bozarsınız, çünkü yeni ebeveyn diğer çocuktan büyük kalır. Yeni başlayanların en sık yaptığı hata budur.

### Tepeye bakma (peek)

En öncelikli elemanı *çıkarmadan* okumak, sadece `heap[0]`'ı döndürmektir; **O(1)**. Öncelik kuyruğunun cazibesinin büyük kısmı budur: minimuma sabit zamanda bakabilirsiniz.

### Bir diziyi heap'e çevirme (build-heap / heapify) — neden O(n)?

Elinizde `n` elemanlı hazır bir dizi varsa, bunu tek tek `push` ile heap'e çevirmek `O(n log n)` sürer. Ama daha iyisi mümkündür ve bu, çoğu kişinin şaşırdığı bir sonuçtur: **build-heap işlemi O(n)'dir**.

Yöntem şudur: diziyi olduğu gibi kabul edin ve *son iç düğümden* köke doğru geriye giderek her düğüme sift-down uygulayın. Yaprakları atlarız çünkü onların altında düzeltilecek bir şey yoktur; ilk iç düğüm indeksi `n/2 - 1`'dir.

```
def build_heap(a):
    n = len(a)
    for i in range(n // 2 - 1, -1, -1):
        sift_down(a, i, n)
```

Neden O(n)? Sezgi şudur: düğümlerin yarısı yapraktır ve hiç iş yapmaz; çeyreği en fazla 1 adım, sekizde biri en fazla 2 adım iner, ve bu böyle gider. Yani *çok* düğüm var ama onlar *az* iş yapıyor; *az* düğüm (köke yakın olanlar) *çok* iş yapıyor. Bu ters ilişki, toplam işi `Σ (h / 2^h)` biçiminde bir seriye dönüştürür ki bu seri sabite yakınsar. Sonuç doğrusaldır. Buna karşılık tek tek ekleme yönteminde işin çoğu, en pahalı katman olan yapraklarda yapılır; o yüzden O(n log n) olur. Bir diziden heap kuracaksanız daima build-heap kullanın.

## Somut Örnek: Adım Adım Bir Min-Heap

`[5, 3, 8, 1]` elemanlarını boş bir min-heap'e sırayla eklediğimizi izleyelim (dizi gösterimiyle):

- `push(5)` → `[5]`
- `push(3)` → sona eklendi `[5, 3]`; 3 < 5 olduğu için sift-up, takas → `[3, 5]`
- `push(8)` → `[3, 5, 8]`; 8 ebeveyni 3'ten büyük, takas yok
- `push(1)` → `[3, 5, 8, 1]`; 1 indeks 3'te, ebeveyni indeks 1'deki 5. 1 < 5, takas → `[3, 1, 8, 5]`; şimdi 1 indeks 1'de, ebeveyni indeks 0'daki 3. 1 < 3, takas → `[1, 3, 8, 5]`

Sonuç `[1, 3, 8, 5]`. Kök 1, doğru şekilde minimum. Şimdi `pop()`:

- Cevap `heap[0] = 1`. Son eleman 5'i köke taşı → `[5, 3, 8]`. Sift-down: 5'in çocukları 3 ve 8; küçük olan 3, 5'ten küçük, takas → `[3, 5, 8]`. 5'in artık çocuğu yok, dur.
- Dönen değer 1; kalan heap `[3, 5, 8]`, yeni minimum 3.

Bu örnek, heap'in *sıralı bir dizi olmadığını* net gösterir: `[1, 3, 8, 5]` içinde 8'in 5'ten önce gelmesi tamamen geçerlidir, çünkü sadece ata-torun düzeni korunur.

## Karmaşıklık Özeti ve Neden Değiş Tokuşları

| İşlem | Binary heap |
|---|---|
| peek (min/max) | O(1) |
| push (insert) | O(log n) |
| pop (extract) | O(log n) |
| build-heap | O(n) |
| arbitrary search | O(n) |
| decrease-key (konum biliniyorsa) | O(log n) |

Bu tablodaki en öğretici satır **arbitrary search**'tür: heap içinde rastgele bir değeri aramak O(n)'dir, çünkü heap sıralı değildir. Heap'in *bir tek işi* vardır — en öncelikli elemana hızlı erişim — ve onun dışında iyi olmadığını kabul etmek gerekir. Aradığınız şey "içinde x var mı" ise heap yanlış yapıdır; hash set veya arama ağacı gerekir.

**Neden bir arama ağacı yerine heap?** Dengeli bir arama ağacı da ekleme, silme ve min bulmayı O(log n)'de yapar. Ama heap daha basittir, sabit-çarpanı düşüktür (dizi + cache locality), O(1) peek verir ve O(n) build-heap sunar. Buna karşılık ağaç sıralı gezinme (in-order traversal) ve rastgele arama sağlar, heap sağlamaz. "En küçüğü/en büyüğü tekrar tekrar isteyeceksin ama global sıralamaya ihtiyacın yok" senaryosunda heap açık kazanandır.

## Uygulama 1: Dijkstra En Kısa Yol Algoritması

Öncelik kuyruğunun belki de en ünlü kullanımı Dijkstra'nın tek kaynaklı en kısa yol (single-source shortest path) algoritmasıdır. Negatif olmayan kenar ağırlıklı bir grafta, bir başlangıç düğümünden tüm diğer düğümlere en kısa mesafeyi bulur.

### Neden öncelik kuyruğu?

Dijkstra'nın özü açgözlü (greedy) bir seçimdir: her adımda, *henüz kesinleşmemiş* düğümler arasından başlangıca en yakın olanı seç, onu kesinleştir ve komşularının mesafelerini güncelle (buna **relaxation** / gevşetme denir). Buradaki "en yakın olanı seç" tam olarak bir extract-min işlemidir. Öncelik değeri, düğümün o ana kadar bilinen en kısa mesafesidir. İşte bu yüzden min-heap tabanlı öncelik kuyruğu doğal araçtır.

```
import heapq

def dijkstra(graph, source):
    # graph: dugum -> [(komsu, agirlik), ...]
    dist = {source: 0}
    pq = [(0, source)]          # (mesafe, dugum)
    visited = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:        # bayat kayit, atla
            continue
        visited.add(u)
        for v, w in graph[u]:
            nd = d + w
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist
```

### Bayat kayıt (stale entry) sorunu ve kök nedeni

Yukarıdaki koddaki `if u in visited: continue` satırı çok önemlidir ve buradaki tasarım kararının nedenini anlamak gerekir. Bir düğümün mesafesi geliştiğinde, ideal olarak öncelik kuyruğundaki eski önceliğini *düşürmek* isteriz (decrease-key). Ama standart binary heap'te bir elemanı içeride bulup önceliğini değiştirmek O(n) arama gerektirir, çünkü heap aranabilir değildir. Bunu çözmenin iki yolu vardır:

1. **Lazy deletion (tembel silme):** decrease-key yerine, düğümün yeni ve daha iyi mesafesini kuyruğa *yeni bir kayıt* olarak ekleriz. Aynı düğümün birden çok kaydı olur. Bir düğümü çıkardığımızda, eğer onu zaten kesinleştirmişsek (visited), bu bayat bir kayıttır ve atlanır. Bu, pratikte en yaygın ve en basit yaklaşımdır. Yukarıdaki kod budur. Maliyeti biraz daha fazla bellek ve kuyrukta gereksiz kayıtlardır, ama uygulaması kolaydır ve Python'un `heapq` gibi decrease-key sunmayan kütüphaneleriyle uyumludur.

2. **Gerçek decrease-key:** Her düğümün heap içindeki konumunu ayrı bir tabloda (index map) tutan bir "indexed heap" gerçekleştirirsek, decrease-key'i O(log n)'de yapabiliriz. Bu bellek olarak daha sıkı çalışır ama uygulaması daha karmaşıktır.

### Karmaşıklık ve Fibonacci heap notu

Binary heap ile Dijkstra'nın karmaşıklığı, `E` kenar ve `V` düğüm için tipik olarak **O((V + E) log V)** biçiminde ifade edilir (lazy yaklaşımda çıkarılan bayat kayıtlar da sabit-çarpana girer). Teorik literatürde **Fibonacci heap** ile amortize O(1) decrease-key sağlanarak `O(E + V log V)` sınırına inilebileceği gösterilmiştir. Ancak dürüst olmak gerekirse: Fibonacci heap'in sabit-çarpanları büyük ve uygulaması karmaşıktır; pratikte çoğu üretim kodu binary heap (veya d-ary heap) kullanır ve gerçek dünyada genelde binary heap daha hızlıdır. Bu, "teorik olarak daha iyi" ile "pratikte daha hızlı" ayrımının klasik bir örneğidir.

### d-ary heap ile ince ayar

Dijkstra gibi *ekleme/decrease ağırlıklı* iş yüklerinde, her düğümün 2 yerine `d` çocuğu olan bir **d-ary heap** faydalı olabilir. Daha fazla çocuk demek daha *sığ* ağaç demektir (yükseklik `log_d n`), bu da sift-up'ı (ve dolayısıyla insert/decrease-key'i) hızlandırır; karşılığında sift-down her seviyede `d` çocuğa baktığı için biraz yavaşlar. Kenar sayısı düğüm sayısından çok fazlaysa (yoğun graf) `d`'yi 4 gibi bir değere çekmek ölçülebilir hızlanma sağlayabilir.

## Uygulama 2: Top-K Problemi

Bir başka çok yaygın kullanım: `n` elemanlık bir akış veya diziden **en büyük (veya en küçük) k elemanı** bulmak. Örnekler: bir arama motorunda en alakalı k sonuç, log'larda en sık geçen k IP, bir öneri sisteminde en yüksek skorlu k ürün.

### Naif yöntem ve neden yetersiz

En bariz yol: tüm diziyi sırala, ilk k'yı al. Bu `O(n log n)`'dir ve tüm veriyi bellekte tutmayı gerektirir. Ama k, n'den çok küçükse (ki genelde öyledir, ör. bir milyar log satırından en sık 10 IP) bütün diziyi sıralamak israftır. Ayrıca veri bir *akış* (stream) ise ve hepsi belleğe sığmıyorsa, sıralama hiç mümkün olmayabilir.

### Heap'li yöntem: neden ters heap kullanılır?

En büyük k elemanı bulmak için sezgiye aykırı ama doğru olan yol, **boyutu k'da sabitlenmiş bir min-heap** kullanmaktır. Neden max değil de min-heap? Çünkü heap'te *en kolay erişilen ve atılan* eleman köktür. Elimizdeki k adayın *en küçüğünü* kökte tutarsak, yeni gelen bir elemanı bu en küçük adayla tek karşılaştırmada eleyip elemeyeceğimize karar verebiliriz.

Mantık şudur: heap'i ilk k elemanla doldur. Sonra gelen her yeni eleman için, eğer yeni eleman heap'in kökünden (yani mevcut k adayın en küçüğünden) büyükse, kökü çıkar ve yeni elemanı ekle; değilse yeni elemanı görmezden gel, çünkü en büyük k'ya asla giremez.

```
import heapq

def top_k(stream, k):
    heap = []                 # min-heap, boyutu <= k
    for x in stream:
        if len(heap) < k:
            heapq.heappush(heap, x)
        elif x > heap[0]:     # kok = mevcut adaylarin en kucugu
            heapq.heapreplace(heap, x)   # pop + push tek islemde
    return heap               # en buyuk k eleman (sirasiz)
```

### Neden bu yaklaşım üstün

Bu yöntemin zaman karmaşıklığı **O(n log k)**'dir: her eleman için en fazla bir O(log k) heap işlemi. Bellek karmaşıklığı ise sadece **O(k)**'dir — heap her zaman en fazla k eleman tutar. İki büyük kazanç var:

1. **k ≪ n olduğunda hız:** `log k`, `log n`'den çok küçük olabilir. Bir milyar elemandan en büyük 10'u için `log 10` ile `log(10⁹)` arasındaki fark önemlidir.
2. **Akış / sınırlı bellek:** Tüm veriyi asla bir arada tutmayız; tek geçişte (single pass), sabit O(k) bellekle çalışırız. Bu, veri diske sığmayacak kadar büyükken ya da gerçek zamanlı bir akışta hayati bir özelliktir.

`heapreplace`, bir `pop` ve bir `push`'u tek işlemde yapar ve iki ayrı çağrıdan biraz daha verimlidir (heap yalnızca bir kez yeniden dengelenir). Sonuç heap'i k elemanı içerir ama *sıralı değildir*; kesin sıralı sonuç isteniyorsa çıktı heap'i ayrıca sıralanır, ki bu sadece `O(k log k)` ek maliyettir — n'ye değil, k'ya bağlıdır.

### Quickselect ile karşılaştırma

Eğer tüm veri bellekteyse ve akış değilse, **quickselect** (introselect) algoritması top-k'yı ortalama O(n)'de bulabilir; bu heap yönteminden asimptotik olarak daha hızlıdır. Peki neden hâlâ heap? Çünkü quickselect tüm veriye rastgele erişim ister (akışta çalışmaz), en kötü durumu O(n²)'dir (iyi pivot seçimiyle önlenir), ve veriyi yerinde karıştırır. Heap yöntemi ise tek geçişli, akış-dostu ve sabit belleklidir. Kısacası: bellekteki sabit diziler için quickselect, akışlar ve sınırlı bellek için heap.

## Yaygın Hatalar ve Tuzaklar

**Min-heap ile max-heap karıştırmak.** Python'un `heapq` modülü *yalnızca min-heap* sağlar. Max-heap davranışı istiyorsanız yaygın hile değerleri negatiflemektir (`-x` ekleyip çıkarırken tekrar negatiflemek). Bu, sayısal olmayan veya karmaşık nesnelerde işe yaramaz; o durumda bir sarmalayıcı (wrapper) sınıf veya `(-öncelik, sıra_no, nesne)` demeti kullanmak gerekir.

**Karşılaştırılamayan nesneleri kuyruğa koymak.** `(öncelik, nesne)` demetleri koyarken iki elemanın önceliği eşit olursa, heap ikinci öğeyi (nesneyi) karşılaştırmaya çalışır ve nesne karşılaştırılabilir değilse çalışma zamanında hata verir. Standart çözüm, araya monoton artan bir *tie-breaker* sıra numarası koymaktır: `(öncelik, sayaç, nesne)`. Sayaç asla eşit olmayacağı için nesneye hiç bakılmaz.

**Sift-down'da yanlış çocukla takas.** Daha önce vurgulandı: min-heap'te daima *daha küçük* çocukla takas edilmelidir. Yeni başlayanlar sadece "bir çocuk küçükse takas et" mantığı kurup diğer çocuğu unutur ve heap özelliğini bozar.

**Heap'i sıralı sanmak.** Heap'i baştan sona gezerek sıralı veri beklemek klasik bir yanılgıdır. Yalnızca kök garantilidir. Sıralı çıktı için elemanları tek tek `pop` etmek gerekir (bu zaten **heapsort** algoritmasıdır: build-heap O(n) + n kez pop O(log n) = O(n log n)).

**Dijkstra'yı negatif kenarlarda kullanmak.** Dijkstra'nın açgözlü mantığı, bir düğüm kesinleştikten sonra ona daha kısa bir yol bulunamayacağı *varsayımına* dayanır. Negatif kenarlar bu varsayımı çürütür, çünkü sonradan gelen negatif bir kenar mesafeyi düşürebilir. Negatif kenar varsa Bellman-Ford (veya negatif çevrim yoksa uygun bir varyant) gerekir. Bu bir heap hatası değil, algoritma seçim hatasıdır ama sık yapılır.

**Var olan bir diziyi tek tek push ederek heap kurmak.** O(n) build-heap yerine O(n log n) döngü kurmak, büyük verilerde gereksiz yavaşlıktır.

## En İyi Pratikler

**Dilin standart heap'ini kullanın.** Python'da `heapq`, C++'ta `std::priority_queue` (varsayılan max-heap!) ve `std::make_heap`/`push_heap`/`pop_heap`, Java'da `PriorityQueue` iyi test edilmiş, hızlı gerçekleştirimlerdir. Kendi heap'inizi yazmak sadece öğrenme amaçlı ya da özel gereksinim (indexed / decrease-key destekli heap gibi) olduğunda anlamlıdır. C++'ta varsayılanın max-heap olduğunu unutmayın; min-heap için karşılaştırıcıyı (`std::greater`) belirtmeniz gerekir — dil arası bu fark sık hata kaynağıdır.

**Doğru işi doğru yapıya verin.** Sadece "en öncelikli"ye tekrar tekrar erişecekseniz heap idealdir. Rastgele arama, aralık sorgusu (range query) veya sıralı gezinme gerekiyorsa dengeli arama ağacı ya da başka yapı düşünün. Sabit veri kümesinde tek seferlik top-k için quickselect değerlendirin.

**decrease-key gerekiyorsa lazy deletion tercih edin.** Dijkstra, Prim gibi algoritmalarda çoğu zaman gerçek decrease-key gerçekleştirmek yerine yeni kayıt ekleyip bayatları atlamak hem daha basit hem yeterince hızlıdır. Ancak kuyruğun aşırı şişip belleği doldurabileceği patolojik durumlarda indexed heap'e geçmeyi düşünün.

**top-k'da heap boyutunu k'da sabitleyin.** Tüm veriyi bir heap'e atıp sonra k kez pop etmek O(n log n) ve O(n) bellektir. Boyutu k'da sabit tutulan heap ise O(n log k) zaman ve O(k) bellektir — özellikle akışlarda ve k ≪ n olduğunda çok daha iyidir.

**tie-breaker koyun.** Öncelik demetlerinde karşılaştırılamayan nesne riskine karşı daima monoton bir sıra sayacı ekleyin; ayrıca bu, eşit öncelikli elemanlar arasında *stabil* ve öngörülebilir (genelde FIFO) bir sıra da sağlar.

**Ölçün, varsaymayın.** d-ary heap, Fibonacci heap gibi "teorik olarak daha iyi" yapılar pratikte cache davranışı ve sabit-çarpanlar yüzünden düz binary heap'i geçemeyebilir. Performans kritikse gerçek veri üzerinde profilleyin. Çoğu durumda dilin standart binary heap'i en doğru varsayılan seçimdir.

## Özet

Binary heap, tam ikili ağacın diziyle temsil edilebilmesi sayesinde pointer'sız, cache-dostu, O(log n) ekleme/çıkarma ve O(1) peek sunan zarif bir yapıdır. Kısmen sıralı olduğu için hızlıdır ama rastgele aramada zayıftır — bu bir kusur değil, tasarım tavizidir. Öncelik kuyruğunun temel gerçekleştirimi olarak Dijkstra'da "en yakın düğümü seç" adımını, top-k'da ise sabit bellekle akış üzerinde en iyi k elemanı bulmayı mümkün kılar. Doğru yerde kullanıldığında sade ve son derece etkilidir; yanlış yerde (arama, sıralı gezinme) ise yanlış araçtır. Ustalık, hangi işin heap'e ait olduğunu bilmekte yatar.
