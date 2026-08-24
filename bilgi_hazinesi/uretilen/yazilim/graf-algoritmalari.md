# Graf Algoritmaları

Graf (graph), bir problemi "nesneler" ve "nesneler arasındaki ilişkiler" biçiminde modelleyen en genel veri yapılarından biridir. Nesnelere düğüm (vertex/node), ilişkilere kenar (edge) denir. Yol bulma, bağımlılık çözümleme, sosyal ağ analizi, derleyici tasarımı, ağ yönlendirmesi ve daha yüzlerce alanda karşımıza çıkan problemler aslında birer graf problemidir. Bu makale grafların nasıl temsil edildiğini, temel gezinme algoritmalarını (BFS/DFS), en kısa yol için Dijkstra'yı, bağımlılık sıralaması için topolojik sıralamayı ve küme birleştirme için union-find yapısını; her birinin *neden* böyle çalıştığına odaklanarak ele alır.

## Temel Kavramlar ve Sınıflandırma

Bir graf `G = (V, E)` biçiminde tanımlanır: `V` düğüm kümesi, `E` kenar kümesidir. Kenarların yönü olup olmamasına göre graf **yönlü (directed)** veya **yönsüz (undirected)** olur. Yönsüz bir grafta `(u, v)` kenarı hem `u`'dan `v`'ye hem de tersine gidilebildiğini söyler; yönlü grafta ise `u → v` kenarı yalnızca tek yönü ifade eder.

Kenarlara sayısal bir ağırlık (weight) atanırsa graf **ağırlıklı (weighted)** olur. Ağırlık; mesafe, maliyet, süre, kapasite gibi bir büyüklüğü temsil edebilir. Ağırlıksız grafta her kenarın örtük olarak 1 maliyeti olduğunu düşünebiliriz.

İki büyüklük, algoritma karmaşıklıklarını konuşurken sürekli karşımıza çıkar: `V` düğüm sayısı ve `E` kenar sayısı. Bir grafın **yoğun (dense)** mu yoksa **seyrek (sparse)** mi olduğu, `E`'nin `V`'ye göre büyüklüğüyle belirlenir. En fazla kenar sayısı yönsüz grafta `V(V-1)/2` mertebesindedir; yani `E`, `V²` mertebesine kadar çıkabilir. Bu ayrım, aşağıda göreceğimiz gibi hangi temsilin ve hangi algoritmanın uygun olduğunu doğrudan etkiler.

## Temsil: Neden Doğru Temsil Her Şeyi Belirler

Grafı bilgisayarda nasıl sakladığınız, algoritmanızın hem hızını hem de bellek tüketimini kökten belirler. İki temel temsil vardır.

### Komşuluk Matrisi (Adjacency Matrix)

`V × V` boyutunda bir matris tutulur. `M[i][j]` hücresi, `i`'den `j`'ye kenar varsa 1 (veya ağırlığı), yoksa 0 (veya sonsuz) olur. Yönsüz grafta matris simetriktir.

Bu temsilin *kök mantığı* rastgele erişimdir: "`i` ile `j` arasında kenar var mı?" sorusuna `O(1)`'de yanıt verir; çünkü doğrudan bir dizi hücresine bakarsınız. Bunun bedeli bellektir: kaç kenar olursa olsun `O(V²)` yer kaplar. Bir milyon düğümlü seyrek bir graf için bu, terabaytlarca bellek demektir ve pratikte imkânsızdır. Ayrıca "bir düğümün tüm komşularını gez" işlemi, gerçekte az komşusu olsa bile tüm satırı taramayı gerektirir: `O(V)`.

Dolayısıyla komşuluk matrisi yalnızca **yoğun** graflarda veya düğüm sayısı küçük olduğunda mantıklıdır.

### Komşuluk Listesi (Adjacency List)

Her düğüm için, o düğümün komşularını tutan bir liste saklanır. Toplam bellek `O(V + E)`'dir; yani yalnızca var olan kenarlar kadar yer kaplar. Bir düğümün komşularını gezmek, tam olarak o düğümün derecesi (degree) kadar sürer.

*Neden pratikte varsayılan tercih budur?* Gerçek dünya graflarının ezici çoğunluğu seyrektir. Bir sosyal ağda milyarlarca kullanıcı olabilir ama her kullanıcının birkaç yüz arkadaşı vardır; bir yol ağında her kavşak yalnızca birkaç yola bağlıdır. Komşuluk listesi bu seyrekliği doğrudan bellek tasarrufuna çevirir. Bu makaledeki BFS, DFS, Dijkstra ve topolojik sıralama örneklerinin hepsi komşuluk listesini varsayar.

Tek dezavantajı, "`u` ile `v` arasında kenar var mı?" sorusunun `u`'nun komşu listesini taramayı gerektirmesidir: `O(derece)`. Bu ihtiyaç sıksa, her düğümün komşularını bir hash set içinde tutarak bu sorguyu ortalama `O(1)`'e indirebilirsiniz.

Pratik bir kural: aksi bir gerekçe yoksa komşuluk listesi kullanın. Matrisi yalnızca graf gerçekten yoğunsa ya da matris çarpımı gibi lineer cebir işlemleri yapacaksanız seçin.

## Graf Gezinme: BFS ve DFS

Neredeyse tüm ileri graf algoritmalarının temelinde iki gezinme (traversal) stratejisi yatar: genişlik öncelikli arama (BFS) ve derinlik öncelikli arama (DFS). İkisi de her düğümü tam bir kez ziyaret eder ve `O(V + E)` zamanda çalışır; farkları ziyaret **sırasında**, ve bu sıra farkı hangi problemi çözebildiklerini belirler.

### Breadth-First Search (BFS)

BFS, başlangıç düğümünden başlayarak grafı katman katman keşfeder: önce başlangıcın tüm komşuları (1 uzaklıktakiler), sonra onların komşuları (2 uzaklıktakiler), diye devam eder. Bu davranışı sağlayan mekanizma bir **kuyruktur (queue, FIFO)**.

```python
from collections import deque

def bfs(graf, baslangic):
    ziyaret = {baslangic}
    kuyruk = deque([baslangic])
    while kuyruk:
        dugum = kuyruk.popleft()
        for komsu in graf[dugum]:
            if komsu not in ziyaret:
                ziyaret.add(komsu)
                kuyruk.append(komsu)
```

*Kök neden — BFS neden en kısa yolu bulur?* Kuyruk, düğümleri keşfedildikleri sıraya göre işler. Bir düğüm ilk kez kuyruğa girdiğinde, ona giden en az kenarlı yol bulunmuş olur. Çünkü katman `k`'daki tüm düğümler, katman `k+1`'deki düğümlerden *önce* işlenir; dolayısıyla bir düğüme daha kısa bir yol olsaydı, o yol daha önceki bir katmanda zaten keşfedilmiş olurdu. Bu, BFS'i **ağırlıksız graflarda en kısa yol** için doğru araç yapar.

Kritik bir ayrıntı: bir düğümü `ziyaret` kümesine kuyruğa eklerken (yani ilk keşfedildiğinde) ekleyin, kuyruktan çıkarırken değil. Aksi hâlde aynı düğüm birden çok kez kuyruğa girebilir; bu hem gereksiz iş yapar hem de en kısa yol garantisini bozabilir. Bu, BFS'te en sık yapılan hatadır.

### Depth-First Search (DFS)

DFS ise bir yolu gidebildiği kadar derine kadar takip eder; çıkmaza girince bir adım geri döner (backtrack) ve keşfedilmemiş başka bir dal dener. Mekanizması bir **yığındır (stack, LIFO)** — özyinelemeli (recursive) yazıldığında bu yığın, çağrı yığınının (call stack) kendisidir.

```python
def dfs(graf, dugum, ziyaret):
    ziyaret.add(dugum)
    for komsu in graf[dugum]:
        if komsu not in ziyaret:
            dfs(graf, komsu, ziyaret)
```

DFS'in gücü, gezinme sırasında düğümlere iki zaman damgası atayabilmenizden gelir: bir düğüme *girme* (discovery) ve o düğümden *çıkma* (finish) anı. Bu iki an, döngü tespiti, topolojik sıralama, güçlü bağlı bileşenler (strongly connected components) ve köprü/eklem noktası bulma gibi problemleri çözer.

*Önemli tuzak:* Derin veya zincir biçiminde bir grafta özyinelemeli DFS, çağrı yığınını taşırabilir (stack overflow). Örneğin bir milyon düğümlük düz bir zincirde özyineleme derinliği bir milyon olur ve çoğu dilin varsayılan yığın sınırını aşar. Böyle durumlarda DFS'i açık bir yığın (explicit stack) ile döngüsel (iterative) olarak yazmak gerekir.

### BFS mi DFS mi?

Seçim probleme bağlıdır. **En az kenarlı yol** istiyorsanız BFS. **Tüm yolları keşfetmek**, **döngü tespiti** veya **bağımlılık sıralaması** istiyorsanız DFS. Bellek açısından, geniş ama sığ graflarda BFS'in kuyruğu büyük olabilir; derin graflarda DFS'in yığını büyük olabilir. İkisi de kör aramadır: hedefe doğru bir "yön" bilgisi kullanmazlar.

## Dijkstra: Ağırlıklı Graflarda En Kısa Yol

BFS ağırlıksız grafta en kısa yolu bulur, ama kenarların farklı maliyetleri olduğunda "en az kenar" ile "en düşük toplam maliyet" artık aynı şey değildir. Üç kenarlı ucuz bir yol, tek kenarlı pahalı bir yoldan daha iyi olabilir. Dijkstra algoritması tam bu problemi çözer: **negatif olmayan** ağırlıklı bir grafta, tek bir kaynaktan diğer tüm düğümlere en kısa yolu bulur.

### Çalışma Mantığı

Dijkstra bir **greedy (açgözlü)** algoritmadır. Her düğüm için o ana kadar bilinen en kısa mesafeyi (`dist`) tutar; başlangıçta kaynak `0`, diğerleri sonsuzdur. Her adımda, henüz kesinleşmemiş düğümler arasından mesafesi *en küçük* olanı seçer, onu kesinleşmiş kabul eder ve komşularının mesafesini "gevşetme (relaxation)" ile günceller: `dist[komsu] = min(dist[komsu], dist[dugum] + agirlik)`.

En küçük mesafeli düğümü verimli seçebilmek için bir **öncelik kuyruğu (priority queue / min-heap)** kullanılır.

```python
import heapq

def dijkstra(graf, baslangic):
    dist = {d: float('inf') for d in graf}
    dist[baslangic] = 0
    yigin = [(0, baslangic)]
    while yigin:
        d, dugum = heapq.heappop(yigin)
        if d > dist[dugum]:
            continue  # bayatlamis kayit, atla
        for komsu, agirlik in graf[dugum]:
            yeni = d + agirlik
            if yeni < dist[komsu]:
                dist[komsu] = yeni
                heapq.heappush(yigin, (yeni, komsu))
    return dist
```

*Kök neden — greedy seçim neden doğrudur?* Bir düğümü min-heap'ten en küçük mesafeyle çıkardığınızda, o mesafenin nihai (kesin en kısa) olduğunu garanti edebilirsiniz. Neden? Çünkü tüm kenar ağırlıkları negatif değildir. Henüz işlenmemiş başka bir yol üzerinden bu düğüme daha kısa gelmenin tek yolu, o an mesafesi daha küçük bir düğümden geçmek olurdu; ama biz zaten en küçük mesafeliyi seçtik. Negatif ağırlık olsaydı bu mantık çökerdi: daha uzun görünen bir yol, ilerideki negatif bir kenarla toplamda daha kısa olabilirdi. İşte bu yüzden **Dijkstra negatif ağırlıklı graflarda çalışmaz** — bu, en sık yapılan kavramsal hatadır. Negatif kenarlar için Bellman-Ford gibi başka bir algoritma gerekir.

### Performans ve "Lazy Deletion" Tuzağı

Yukarıdaki min-heap tabanlı gerçekleştirimin karmaşıklığı yaklaşık `O(E log V)`'dir. Standart heap'ler bir öğenin önceliğini yerinde düşürmeyi (decrease-key) doğrudan desteklemediğinden, yaygın ve pratik yöntem aynı düğümü daha küçük mesafeyle yeniden heap'e eklemektir. Bu, heap'te "bayatlamış (stale)" kayıtlar bırakır. Yukarıdaki koddaki `if d > dist[dugum]: continue` satırı tam da bunu ele alır: bir düğümü zaten kesinleşmiş mesafesinden daha büyük bir değerle çıkardıysanız, o kayıt bayattır ve atlanmalıdır. Bu kontrolü unutmak, algoritmanın yanlış sonuç değil ama gereksiz tekrar iş yapmasına yol açar; bazı hatalı gerçekleştirimlerde ise düğümleri tekrar işleyerek bozulmaya neden olabilir.

Bir başka pratik ihtiyaç, yalnızca mesafeyi değil **yolu** da bulmaktır. Bunun için her gevşetmede "bu düğüme en kısa yolu hangi düğümden geldik" bilgisini bir `onceki` (predecessor) tablosunda tutun; sonda hedeften geriye doğru bu tabloyu izleyerek yolu yeniden inşa edin.

## Topolojik Sıralama: Bağımlılıkları Doğru Sıraya Dizmek

Bazı problemlerde düğümler arası kenarlar bir "önce/sonra" ilişkisini temsil eder: bir dersi almadan diğerini alamazsınız, bir yazılım paketini kurmadan ona bağımlı paketi kuramazsınız, bir hücreyi hesaplamadan ona dayanan formülü çözemezsiniz. **Topolojik sıralama**, böyle bir grafın düğümlerini, her kenar `u → v` için `u`'nun `v`'den önce geldiği bir doğrusal sıraya dizer.

Bu ancak grafta **döngü yoksa** mümkündür; yani graf bir **DAG (Directed Acyclic Graph — yönlü çevrimsiz graf)** olmalıdır. Sezgi açık: A, B'ye bağımlıysa ve B de A'ya bağımlıysa, hangisini önce yapacağınıza dair tutarlı bir sıra yoktur. Dolayısıyla topolojik sıralama, aynı zamanda bir döngü tespiti aracıdır.

İki klasik yöntem vardır.

### Kahn'ın Algoritması (Giren Derece / In-degree)

Her düğümün **giren derecesini (in-degree)** — yani ona gelen kenar sayısını — hesaplayın. Giren derecesi sıfır olan düğümlerin hiçbir ön koşulu yoktur; bunlar hemen sıraya alınabilir. Bir düğümü sıraya aldığınızda, ondan çıkan kenarları "kaldırın", yani komşularının giren derecesini bir azaltın; yeni sıfıra düşen komşular da işlenmeye hazır hâle gelir.

```python
from collections import deque

def topolojik_kahn(graf):
    giren = {d: 0 for d in graf}
    for d in graf:
        for komsu in graf[d]:
            giren[komsu] += 1
    kuyruk = deque([d for d in graf if giren[d] == 0])
    sira = []
    while kuyruk:
        d = kuyruk.popleft()
        sira.append(d)
        for komsu in graf[d]:
            giren[komsu] -= 1
            if giren[komsu] == 0:
                kuyruk.append(komsu)
    if len(sira) != len(graf):
        raise ValueError("Graf döngü içeriyor, topolojik sıralama yok")
    return sira
```

*Kök neden ve döngü tespiti:* Algoritma, giren derecesi sıfır olan düğüm kaldığı sürece ilerler. Eğer bir noktada işlenmemiş düğümler varken hiçbirinin giren derecesi sıfıra düşmemişse, bu düğümler birbirine dairesel biçimde bağımlıdır — yani bir döngü vardır. Sonuçtaki sıranın uzunluğunun toplam düğüm sayısına eşit olup olmadığını kontrol etmek, bu döngüyü yakalamanın temiz yoludur. Bu kontrolü atlamak, döngülü grafta sessizce eksik bir sıra döndürmenize yol açar — yaygın ve sinsi bir hatadır.

### DFS Tabanlı Topolojik Sıralama

Alternatif olarak DFS kullanabilirsiniz: her düğümün DFS'i *bittiğinde* (finish anı, yani tüm alt ağacı işlendikten sonra) düğümü bir yığına ekleyin. Sonunda yığını ters çevirdiğinizde topolojik sıra elde edilir. Bunun mantığı, bir düğümün DFS'inin ancak tüm bağımlı-sonrasındaki düğümler bittikten sonra bitmesidir; dolayısıyla en son biten düğüm sırada en başa gelmelidir. Bu yöntemde döngü tespiti için, hâlen işlenmekte olan (gri) bir düğüme geri kenar (back edge) rastlayıp rastlamadığınızı kontrol edersiniz.

Her iki yöntem de `O(V + E)`'dir. Kahn daha sezgisel ve döngü tespitinde daha nettir; DFS tabanlı yöntem başka DFS işleriyle birleştirilebildiği için bazen tercih edilir.

## Union-Find: Ayrık Kümeleri Verimli Yönetmek

Union-Find (Disjoint Set Union — DSU), doğrudan bir "gezinme" algoritması değil, bir veri yapısıdır; ama graf problemlerinde o kadar merkezîdir ki bu başlığı hak eder. İki temel soruyu çok hızlı yanıtlar: "bu iki eleman aynı kümede mi?" ve "bu iki kümeyi birleştir." Tipik kullanım alanları: bir grafın **bağlı bileşenlerini (connected components)** bulmak, döngü tespiti ve özellikle Kruskal'ın minimum kapsayan ağaç (minimum spanning tree) algoritması.

### Temel Fikir ve İki Kritik Optimizasyon

Her küme, bir ağaç olarak temsil edilir; her elemanın bir "ebeveyni (parent)" vardır ve ağacın kökü kümenin temsilcisidir. `find(x)` işlemi kökü bulur; `union(a, b)` iki ağacı birleştirir. İki eleman aynı köke sahipse aynı kümededir.

Naif hâliyle bu ağaçlar uzun zincirlere dönüşüp `find`'ı `O(n)`'e kadar yavaşlatabilir. İki optimizasyon bunu neredeyse sabit zamana indirir:

1. **Union by rank/size (rütbeye/boyuta göre birleştirme):** Birleştirirken küçük ağacı büyüğün altına asın. Bu, ağacın gereksiz yere derinleşmesini engeller.

2. **Path compression (yol sıkıştırma):** `find(x)` çalışırken kökü bulurken, yol üzerindeki tüm düğümleri doğrudan köke bağlayın. Böylece bir sonraki `find` çok daha hızlı olur.

```python
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # yol sikistirma
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False  # zaten ayni kumede -> birlestirilirse dongu olusur
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True
```

*Kök neden — bu iki optimizasyon neden bu kadar güçlü?* Her ikisi birlikte kullanıldığında, `m` işlemin toplam maliyeti neredeyse doğrusaldır; işlem başına ortalama maliyet, pratikte sabit sayılabilecek kadar küçük olan ters Ackermann fonksiyonu `α(n)` mertebesindedir. Bunun anlamı şudur: gerçekçi tüm girdi boyutlarında `α(n)` 5'in altında kalır. Yani union ve find işlemlerini pratikte sabit zamanlı kabul edebilirsiniz. Bu, union-find'ı milyonlarca kenarlı graflarda bile son derece hızlı yapar.

### Union-Find ile Döngü Tespiti

Yönsüz bir grafta döngü tespiti union-find ile zariftir: her kenar `(u, v)` için, `find(u) == find(v)` ise bu iki düğüm zaten aynı bileşendedir; onları birleştiren yeni kenar bir döngü oluşturur. Değilse `union` yapıp devam edersiniz. Yukarıdaki koddaki `union`'ın `False` döndürmesi tam olarak bu durumu işaret eder. Kruskal algoritması da tam bu prensiple çalışır: kenarları ağırlığa göre sıralar ve döngü oluşturmayan kenarları teker teker ekler.

## Yaygın Hatalar ve En İyi Pratikler

Aşağıdaki hatalar, deneyimli geliştiricilerde bile sık görülür; her biri yukarıda açıkladığımız *kök nedenlerin* ihlaline dayanır.

**Ziyaret işaretini yanlış anda koymak.** BFS'te düğümü kuyruğa eklerken değil çıkarırken işaretlemek, aynı düğümün defalarca kuyruğa girmesine ve en kötü hâlde algoritmanın yavaşlamasına ya da sonsuz döngüye yaklaşmasına yol açar. Kural: bir düğümü ilk *gördüğünüz* anda ziyaret edilmiş sayın.

**Dijkstra'yı negatif ağırlıklı grafta kullanmak.** Bu, hatalı sonucun sessizce üretildiği tehlikeli bir hatadır; kod çalışır ama yanlış mesafeler döndürür. Negatif kenar ihtimali varsa Bellman-Ford'a geçin.

**Bayat heap kayıtlarını atlamamak.** Dijkstra'da `if d > dist[dugum]: continue` kontrolünü unutmak, gereksiz iş ve bazı gerçekleştirimlerde bozulma demektir. Her zaman heap'ten çıkardığınız kaydın hâlâ güncel olduğundan emin olun.

**Topolojik sıralamada döngü kontrolünü atlamak.** Çıktının uzunluğunu düğüm sayısıyla karşılaştırmadan sonuç döndürmek, döngülü graflarda eksik ve tutarsız sıra üretir. DAG olduğunu varsaymak yerine *doğrulayın*.

**Union-Find'i optimizasyonsuz kullanmak.** Yalnızca naif `find`/`union` ile büyük graflarda ağaçlar dejenere olur ve performans çöker. Path compression ve union by rank'i birlikte kullanın; ikisi de birkaç satırdır ama etkileri devasadır.

**Yanlış temsili seçmek.** Seyrek grafta komşuluk matrisi kullanmak `O(V²)` bellek israfıdır; yoğun grafta veya `O(1)` kenar sorgusu gerektiğinde komşuluk listesinde ısrar etmek de gereksiz yavaşlıktır. Grafın yoğunluğunu ve erişim desenini önce analiz edin.

**Yönlü/yönsüz ayrımını karıştırmak.** Yönsüz bir grafı oluştururken her kenarı iki yönde de eklemeyi unutmak, sık ve sinsi bir hatadır: graf yarı bağlı görünür ve gezinme beklenmedik biçimde eksik kalır.

Genel bir prensip olarak, bir graf problemini çözerken önce şu soruları sırayla yanıtlayın: Graf yönlü mü, ağırlıklı mı? Yoğun mu seyrek mi? Aradığım şey bir yol mu, bir sıra mı, bir bileşen mi, bir döngü mü? Bu soruların yanıtları, doğru temsili ve doğru algoritmayı neredeyse mekanik biçimde belirler. Graf algoritmalarının çoğu, bu makalede gördüğümüz beş yapı taşının — komşuluk listesi, BFS/DFS gezinmesi, greedy en kısa yol, topolojik sıralama ve union-find — birer varyasyonu ya da bileşimidir. Bu temelleri *neden* çalıştıklarıyla birlikte kavradığınızda, karşınıza çıkan yeni bir graf problemini tanımak ve doğru araca eşlemek büyük ölçüde doğal hâle gelir.
