# İleri Veri Yapıları: Trie, Segment Tree, Fenwick/BIT, Union-Find, Skip List, Bloom Filter, Suffix Yapıları

## Neden Bu Konu Önemli

Temel veri yapıları (dizi, bağlı liste, ikili arama ağacı, heap) çoğu problemi çözer ama gerçek dünyanın "ölçek" ve "gecikme" baskısı altındaki sistemlerinde yetersiz kalır. Bir güvenlik mühendisi veya sistem tasarımcısı için şu sorular sürekli karşımıza çıkar: Milyonlarca IP adresi arasında "bu daha önce görüldü mü?" sorusunu mikrosaniyeler içinde, bellek patlamadan nasıl cevaplarız (Bloom Filter)? Bir ağdaki milyonlarca düğüm arasında hangi ikisinin aynı bileşende olduğunu, sürekli değişen bir topolojide nasıl hızlıca söyleriz (Union-Find)? Bir zaman serisinde "şu aralıktaki toplam/maksimum nedir" sorusunu, veri sürekli güncellenirken nasıl loglaritmik zamanda cevaplarız (Segment Tree, Fenwick/BIT)? Parola listelerinde veya IDS imzalarında ortak önekleri nasıl verimli eşleriz (Trie)? Bir metin içinde belirli bir alt diziyi, tüm dosyayı taramadan nasıl buluruz (Suffix Array/Tree)? Bu yapılar, savunma sistemlerinin (IDS/IPS, SIEM, tehdit istihbaratı platformları, WAF, ağ izleme) performans omurgasını oluşturur. Bu yapıları anlamayan bir mühendis, "neden bu sorgu saniyeler sürüyor" ya da "neden bellek bitiyor" sorularına asla doğru cevap veremez; sadece donanım ekleyerek sorunu erteler.

---

## 1. Trie (Önek Ağacı)

### Tanım ve Kök Neden

Trie (İngilizce "retrieval" kelimesinden), karakter dizilerini (string) düğümler arası kenarlarda karakter tutarak saklayan bir ağaçtır. Her düğüm bir "önek"i (prefix) temsil eder; kökten bir düğüme giden yol, o düğüme kadar olan karakter dizisini oluşturur. Bir hash tablosu string'i tek parça olarak hashler; Trie ise string'i karakter karakter, ortak önekleri **paylaşarak** saklar.

Kök neden şudur: Eğer elinizde binlerce string varsa ve bunların çoğu ortak önekler paylaşıyorsa (parolalar, domain adları, dosya yolları, IDS imzaları, IP prefiksleri), bu ortaklığı bir hash tablosunda ifade edemezsiniz — her string bağımsız bir hash girdisidir. Trie bu ortaklığı yapısal olarak sıkıştırır: "administrator", "admin123", "administrare" önekleri "admin" düğümünde birleşir.

### Çalışma Mantığı

- Ekleme: Kökten başlayarak string'in her karakteri için bir alt düğüm var mı bakılır, yoksa oluşturulur. Sona "kelime sonu" bayrağı konur.
- Arama: Aynı şekilde karakter karakter ilerlenir; yol tamamlanamıyorsa string yoktur.
- Önek sorgusu (`startsWith`): Trie'nin doğal gücüdür — O(k) zamanda (k = önek uzunluğu), o önekle başlayan tüm kelimeleri bulacak alt ağaca ulaşılır.

Zaman karmaşıklığı ekleme/arama için O(k), k anahtar uzunluğu — veri kümesi büyüklüğünden (n) bağımsızdır. Bu, hash tablosunun ortalama O(k) karmaşıklığına yakındır ama Trie ayrıca **sıralı önek sorgusu** ve **en uzun ortak önek** gibi hash tablosunun yapamadığı işlemleri sunar.

### Güvenlik ve Savunma Bağlamı

- **Otomatik tamamlama / parola politikası kontrolü**: Bilinen zayıf parolaların (rockyou.txt benzeri listeler) öneklerini Trie'de tutup, kullanıcı parola seçerken "bu bilinen bir parolanın öneki/varyasyonu mu" kontrolü hızlıca yapılabilir.
- **IDS/IPS imza eşleştirme**: Çoklu desen eşleştirme algoritmalarının (Aho-Corasick gibi) temeli bir Trie'dir. Aho-Corasick, bir Trie üzerine "başarısızlık bağlantıları" (failure links, KMP'nin genellemesi) ekleyerek, binlerce imzayı **tek geçişte** metin üzerinde arar — her imza için ayrı ayrı tarama yapmak yerine. Bu, Snort/Suricata gibi araçların çoklu imza eşleştirmesinin performans temelidir.
- **IP prefix / routing tablosu**: Trie'nin ikili (bit-bazlı) versiyonu olan **Patricia Trie / Radix Tree**, IP yönlendirme tablolarında "en uzun önek eşleşmesi" (longest prefix match) için kullanılır — güvenlik duvarı kural tabanları ve CIDR blok eşleştirme de bu mantığı kullanır.
- **Domain / URL kara liste kontrolü**: Kötü amaçlı domain listeleri Trie'de tutulursa, alt domain varyasyonları (`evil.com`, `sub.evil.com`) tek yapıda hızlıca sorgulanabilir.

### Tuzaklar ve En İyi Pratikler

- **Bellek maliyeti**: Naif bir Trie implementasyonu (her düğümde 26 veya 256 boyutlu dizi) çok fazla bellek harcar, özellikle seyrek (sparse) veri kümelerinde. Çözüm: düğüm başına dizi yerine hash map veya sıralı liste kullanmak (bellek/hız dengesi).
- **Patricia Trie / Radix Tree ile sıkıştırma**: Tek çocuğu olan zincir düğümleri birleştirerek bellek israfını azaltır — büyük ölçekli IP/URL tablolarında standarttır.
- **Unicode/çok baytlı karakterler**: Karakter tabanlı Trie'ler ASCII varsayımıyla yazılırsa, UTF-8 çok baytlı karakterlerde (Türkçe "ı", "ğ", "ş" dahil) bozulur. Byte-bazlı Trie tasarımı daha güvenlidir.
- **Case sensitivity**: Güvenlik kontrollerinde (domain, kullanıcı adı) normalize etmeden (lowercase) Trie'ye eklemek, `Evil.com` ile `evil.com`'un farklı yollara düşmesine ve kontrolün atlanmasına yol açar — bu **gerçek bir bypass tekniğidir**.

---

## 2. Segment Tree

### Tanım ve Kök Neden

Segment Tree, bir dizinin elemanlarını yapraklarda tutan, iç düğümlerin ise alt aralıkların "birleştirilmiş" (toplam, min, max, gcd vb.) sonucunu tuttuğu ikili bir ağaçtır. Kök neden: Bir dizi üzerinde hem **nokta güncelleme** (bir elemanı değiştir) hem de **aralık sorgusu** ("şu aralıktaki toplam/min/max nedir") sık sık ve karışık sırada yapılıyorsa, düz dizi ile aralık sorgusu O(n), önceden hesaplanmış prefix-sum ile güncelleme O(n) olur. Segment Tree her ikisini de **O(log n)**'e indirir — çünkü her aralık sorgusu, ağacı O(log n) derinlikte "kırılan" en fazla O(log n) alt segmente ayrıştırılabilir.

### Çalışma Mantığı

Dizi boyutu n ise ağaç 2n-1 civarı düğümden oluşur (dizi ile temsil edilirse genelde 4n boyutunda alan ayrılır, güvenlik payı için). Her iç düğüm, iki çocuğunun birleşimidir (örneğin toplamı topla, ya da minimumu al). Sorgu, istenen aralığı ağaç üzerinde özyinelemeli olarak üç duruma ayırır: tamamen dışarıda (yoksay), tamamen içeride (düğüm değerini direkt kullan), kısmen örtüşüyor (iki çocuğa in). Güncelleme ise kökten yaprağa inip, dönüşte etkilenen tüm ataları yeniden hesaplar.

**Lazy propagation**: Aralık güncellemesi (örneğin "şu aralıktaki her elemana X ekle") gerektiğinde, her yaprağı tek tek güncellemek O(n) olur. Lazy propagation, güncellemeyi bir düğümde "ertelenmiş" olarak işaretler, sadece o alt ağaca gerçekten inildiğinde işler — bu sayede aralık güncelleme de O(log n)'e iner.

### Güvenlik ve Savunma Bağlamı

- **Zaman serisi anomali tespiti**: Ağ trafiği hacmi, saniye başına istek sayısı gibi metrikler zaman içinde tutulur; "son 5 dakikadaki maksimum istek oranı" gibi kayan pencere (sliding window) sorguları Segment Tree ile hızlıca cevaplanır — DDoS tespiti ve rate-limiting motorlarının temelidir.
- **Log analitiği ve SIEM**: Büyük log akışlarında "şu zaman aralığında kaç hata/uyarı oldu" tipi aralık toplamları, veri sürekli akarken (streaming) verimli hesaplanmalıdır.
- **Erişim kontrol aralıkları**: Port aralıkları, IP aralıkları üzerinde "bu aralık başka bir kuralla çakışıyor mu" analizleri aralık ağaçlarının (interval tree, Segment Tree'nin akrabası) klasik kullanım alanıdır.

### Tuzaklar ve En İyi Pratikler

- **Aşırı mühendislik**: Veri statikse (hiç güncellenmiyorsa), sadece prefix-sum yeterlidir; Segment Tree gereksiz karmaşıklıktır. Segment Tree'nin gerekçesi **dinamik güncelleme + aralık sorgusu** kombinasyonudur.
- **Birleştirme fonksiyonunun birleşebilir (associative) olması şart**: Toplam, min, max, gcd, xor uygundur; medyan gibi birleşebilir olmayan fonksiyonlar doğrudan desteklenmez, ek yapı (örneğin merge sort tree) gerekir.
- **Bellek düzeni**: Dizi tabanlı (2*i, 2*i+1 çocuk indeksleme) implementasyon önbellek (cache) dostu değildir; çok büyük veri kümelerinde segment ağacı yerine Fenwick Tree (aşağıda) tercih edilebilir çünkü daha az bellek/overhead ile benzer işi yapar.
- **Lazy propagation hatası**: Ertelenmiş güncellemenin doğru sırada (önce mevcut düğümü uygula, sonra çocuklara aktar) işlenmemesi klasik ve tespiti zor bir hata kaynağıdır.

---

## 3. Fenwick Tree (Binary Indexed Tree, BIT)

### Tanım ve Kök Neden

Fenwick Tree, Segment Tree'nin **sadece prefix-toplam** (veya benzeri birleşebilir işlemler) için özelleşmiş, çok daha az bellek ve kod karmaşıklığıyla aynı O(log n) güncelleme/sorgu performansını veren versiyonudur. Kök neden: Segment Tree genel amaçlıdır ama fazladan bellek ve sabit çarpan (constant factor) taşır; eğer ihtiyaç sadece "prefix toplam" ve "nokta güncelleme" ise, BIT'in bit manipülasyonu temelli zarif yapısı (her indeksin ikili gösterimindeki en düşük bit'i kullanarak sorumlu olduğu aralığı belirlemesi) aynı işi tek bir n boyutlu dizi ile yapar.

### Çalışma Mantığı

Her `i` indeksi, `i & (-i)` işlemiyle bulunan "en düşük anlamlı bit" kadar bir aralığın sorumluluğunu üstlenir. Güncelleme, `i += i & (-i)` ile yukarı doğru ilerleyerek etkilenen tüm üst-toplamları günceller. Sorgu (prefix toplam), `i -= i & (-i)` ile aşağı inerek O(log n) parçayı toplar. Bu bit hilesi sayesinde açık bir ağaç yapısı (pointer, node) gerekmez — tek bir dizi yeterlidir, bu da bellek verimliliği ve önbellek performansı açısından Segment Tree'ye üstünlük sağlar.

### Güvenlik ve Savunma Bağlamı

- **Ters sıralama sayımı (inversion count)**: Ağ paket sıralarındaki anomalileri (paketlerin beklenen sıradan sapması, olası saldırı/yeniden sıralama belirtisi) tespit etmede kullanılabilecek klasik bir algoritmik araçtır.
- **Sıklık/frekans sayaçları**: "Şu ana kadar şu IP'den kaç istek geldi" gibi kümülatif sayaçların aralık bazlı sorgulanması (örneğin "1000-2000. istekler arasında bu IP'den kaç tanesi") rate-limiting ve anomali tespiti sistemlerinde işe yarar.
- **Bellek kısıtlı gömülü/ağ cihazları**: Fenwick Tree'nin düşük bellek ayak izi, güvenlik duvarı/IDS gibi performans-kritik, bellek kısıtlı ortamlarda Segment Tree'ye tercih edilme sebebidir.

### Tuzaklar ve En İyi Pratikler

- **1-indeksleme zorunluluğu**: BIT'in bit hilesi 1'den başlayan indekslemeyle çalışır (`i & (-i)` sıfırda tanımsız davranır); 0-indeksli dizilerle doğrudan kullanılırsa kaydırma hatası (off-by-one) klasik bir hatadır.
- **Sadece birleşebilir ve tersinir (invertible) işlemler kolay**: Toplam gibi tersinir işlemler (çıkarma ile "aralık toplamı" prefix farkından bulunabilir) idealdir; min/max gibi tersinir olmayan işlemler için BIT'in standart hali yetersizdir, ek teknikler gerekir.
- **2D BIT**: Matris/ızgara verileri (örneğin coğrafi/ağ topolojisi ızgaraları) üzerinde aralık sorgusu gerekiyorsa BIT iki boyuta genişletilebilir, ama karmaşıklık ve bellek O(n*m log n log m) civarına çıkar — büyük ızgaralarda dikkatli tasarım gerekir.

---

## 4. Union-Find (Disjoint Set Union, DSU)

### Tanım ve Kök Neden

Union-Find, elemanları ayrık kümelere (disjoint sets) ayıran ve iki temel işlemi — `find` (bir elemanın hangi kümede olduğunu bul) ve `union` (iki kümeyi birleştir) — neredeyse sabit zamanda yapan bir yapıdır. Kök neden: Bir ağ/grafikte "bu iki düğüm bağlı mı" veya "kaç ayrı bileşen var" sorusu, her sorguda BFS/DFS ile O(V+E) yapılırsa, dinamik olarak sürekli yeni bağlantılar (kenar) eklenen bir sistemde çok pahalıdır. Union-Find, bağlantı bilgisini artımlı (incremental) olarak, her `union` işleminde neredeyse O(1) amortize maliyetle günceller.

### Çalışma Mantığı

Her küme bir "temsilci" (root) etrafında bir ağaç olarak tutulur. **Union by rank/size**: iki küme birleştirilirken, küçük ağaç büyük ağacın altına eklenir (rastgele birleştirme ağaçların dengesiz, derin zincirler haline gelmesine yol açar). **Path compression**: `find` çağrısı sırasında, yol üzerindeki her düğüm doğrudan köke bağlanır — böylece sonraki `find` çağrıları neredeyse O(1) olur. Bu iki optimizasyon birlikte kullanıldığında, amortize karmaşıklık **O(α(n))** olur — α, ters Ackermann fonksiyonu, pratikte 4-5'ten büyük hiçbir gerçek girdi için olmayan, sabit kabul edilebilecek kadar yavaş büyüyen bir fonksiyondur.

### Güvenlik ve Savunma Bağlamı

- **Ağ bağlantı/kümeleme analizi**: Bir ağ trafiği grafiğinde (kim kiminle konuşuyor) hangi düğümlerin aynı bağlı bileşende olduğunu bulmak, botnet kümeleri veya lateral movement (yanal hareket) analizinde IP'lerin/host'ların hangi "adacıklara" ayrıldığını göstermede kullanılır.
- **Kruskal algoritması ile minimum yayılma ağacı**: Ağ topolojisi optimizasyonu, en düşük maliyetli güvenli bağlantı ağı kurulumu gibi senaryolarda Kruskal, kenarları maliyete göre sıralayıp Union-Find ile "bu kenar döngü oluşturuyor mu" kontrolü yaparak çalışır — döngü kontrolü tam olarak Union-Find'ın `find` işlemidir.
- **Sahtekârlık halkası (fraud ring) tespiti**: Ortak telefon numarası, IP, ödeme yöntemi gibi bağlantılarla ilişkilendirilen hesapları kümelemek için kullanılır — birbirine bağlı hesaplar aynı kümeye düşer, büyük kümeler şüpheli halka olarak işaretlenebilir.
- **Bağlantı bileşeni sayımı ile parçalanma tespiti**: Bir ağda beklenmedik şekilde bileşen sayısının artması (örneğin bir saldırı sonucu ağın parçalanması) veya beklenmedik birleşmeler (segmentasyon ihlali — izole olması gereken iki ağ segmentinin birleşmesi) izlenebilir.

### Tuzaklar ve En İyi Pratikler

- **Sadece union/find yapar, "unyon" (ayırma) yapamaz**: Standart Union-Find kümeleri birleştirebilir ama **ayıramaz**. Eğer bir bağlantının kaldırılması (örneğin bir ağ kuralının iptali) modellenmesi gerekiyorsa, standart DSU yetersizdir; zaman içinde geri alınabilir yapı (offline işleme, "kesme" (cutting) destekleyen link-cut tree gibi ileri yapılar) gerekir.
- **Path compression olmadan performans kaybı**: Sadece union yapıp path compression uygulanmazsa, kötü durumda `find` O(n) olabilir — zincirleme (chain) yapısına dönüşür.
- **Amortize O(α(n)) ile tekil O(1) karıştırılmamalı**: α(n) sabit gibi davranır ama teknik olarak amortizedir; kötü niyetli veya patolojik girdi sırasıyla tek bir işlemin maliyeti garantili sabit değildir (pratikte önemsiz ama teorik kesinlik için not edilmeli).

---

## 5. Skip List

### Tanım ve Kök Neden

Skip List, sıralı bir bağlı listenin üstüne rastgelelik (randomization) ile "hızlandırma katmanları" (express lanes) ekleyen bir olasılıksal (probabilistic) veri yapısıdır. Kök neden: Dengeli ağaçlar (AVL, kırmızı-siyah ağaç) O(log n) arama/ekleme/silme sağlar ama implementasyonu karmaşıktır (döndürme/rotation mantığı, denge invariant'ları). Skip List, **rastgelelik** kullanarak aynı beklenen O(log n) performansı, çok daha basit ve anlaşılır bir kodla, kilitleme (locking) açısından da eşzamanlı (concurrent) ortamlarda daha kolay yönetilebilir şekilde sunar.

### Çalışma Mantığı

Taban katman tüm elemanları sıralı tutan normal bir bağlı listedir. Her eleman, madeni para atışı gibi bir olasılıkla (genelde 1/2) bir üst katmana da "terfi eder". Üst katmanlar, alt katmanın "seyreltilmiş" halidir, arama yaparken önce en üst katmandan başlanır, hedefi geçmeyecek şekilde ilerlenir, geçilecekse bir alt katmana inilir. Bu, ikili aramaya benzer bir "atlama" mantığı sağlar — beklenen O(log n) katman sayısı ve her katmanda O(1) beklenen adımla toplam O(log n) beklenen zaman.

### Güvenlik ve Savunma Bağlamı

- **Redis gibi bellek-içi veri depolarının sıralı küme (sorted set) implementasyonu**: Redis'in `ZSET` yapısı Skip List tabanlıdır; güvenlik operasyon merkezlerinde (SOC) olay skorlarını (event score/severity) sıralı tutup "en yüksek riskli ilk N olay" sorgusu için kullanılır.
- **Eşzamanlı (concurrent) sistemlerde kilitsiz/az kilitli yapı**: Yüksek trafikli ağ izleme sistemlerinde çoklu iş parçacığının aynı sıralı yapıya erişmesi gerektiğinde, Skip List'in katmanlı yapısı, dengeli ağaçlara göre daha ince taneli (fine-grained) kilitleme veya lock-free implementasyonlara daha uygundur.

### Tuzaklar ve En İyi Pratikler

- **Olasılıksal garanti, kesin değil**: Kötü şans eseri (çok düşük olasılıkla) performans O(n)'e yaklaşabilir; bu teorik risktir ama kriptografik olarak güvenli rastgelelik kullanılmazsa, saldırgan girdiyi seçebiliyorsa (adversarial input) bu olasılığı zorlamaya çalışabilir — rastgelelik kaynağının öngörülemez olması önemlidir.
- **Bellek overhead'i**: Her eleman birden fazla katmanda pointer tutabilir; ortalama katman sayısı sabit olsa da (genelde ~2x pointer/eleman), dengeli ağaca göre biraz daha fazla bellek kullanabilir.

---

## 6. Bloom Filter

### Tanım ve Kök Neden

Bloom Filter, "bu eleman kümede var mı" sorusuna **olasılıksal** cevap veren, çok az bellek kullanan bir yapıdır. Cevap iki türdür: "kesinlikle yok" (%100 doğru) veya "muhtemelen var" (yanlış pozitif olabilir, ama asla yanlış negatif olmaz). Kök neden: Milyarlarca elemanı (URL, hash, IP) tam olarak (hash tablosu veya set ile) saklamak devasa bellek gerektirir. Bloom Filter, her elemanı **saklamadan**, sadece "izini" bit dizisinde bırakarak, gerçek boyutunun çok küçük bir kesriyle aynı sorguyu (yaklaşık olarak) cevaplar.

### Çalışma Mantığı

Sabit boyutlu bir bit dizisi (başlangıçta hepsi 0) ve k adet bağımsız hash fonksiyonu kullanılır. Ekleme: elemanı k hash fonksiyonundan geçir, elde edilen k pozisyondaki bitleri 1 yap. Sorgu: aynı k pozisyona bak — hepsi 1 ise "muhtemelen kümede", herhangi biri 0 ise "kesinlikle kümede değil". Yanlış pozitif olasılığı, bit dizisi boyutu (m), eleman sayısı (n) ve hash fonksiyon sayısı (k) ile matematiksel olarak hesaplanabilir; k'nin optimal değeri yaklaşık `(m/n) * ln(2)`'dir. **Silme desteklenmez** çünkü bir biti 0'a çevirmek, o bitin katkıda bulunduğu başka bir elemanı da "silebilir" (yanlış negatife yol açar) — bu problem **Counting Bloom Filter** (her pozisyonda bit yerine sayaç tutarak) ile çözülür.

### Güvenlik ve Savunma Bağlamı

- **Büyük ölçekli tekrar kontrolü (deduplication)**: Zaten görülmüş dosya hash'lerini, işlenmiş log kayıtlarını, taranmış URL'leri devasa ölçekte, tam listeyi bellekte tutmadan kontrol etmek — tehdit istihbaratı (threat intelligence) besleme hatlarında "bu IOC (indicator of compromise) daha önce işlendi mi" kontrolü klasik kullanımdır.
- **Kötü amaçlı URL/domain ön-filtreleme**: Tarayıcı güvenlik özellikleri (örneğin Google Safe Browsing'in istemci tarafı ön kontrolü) devasa kötü amaçlı URL listesini cihazda tam olarak tutmak yerine bir Bloom Filter ile "muhtemelen kötü amaçlı mı" ön kontrolü yapar; pozitif çıkarsa ancak o zaman sunucuya tam sorgu (kesin kontrol) gönderilir — bu **iki aşamalı filtreleme mimarisinin** temelidir ve gizlilik açısından da avantajlıdır (tüm URL geçmişi sunucuya gönderilmez).
- **Rate-limiting ve tekrarlayan istek tespiti**: Aynı kaynaktan tekrar eden isteklerin (replay, brute-force denemeleri) hızlı ön-filtrelenmesi.
- **Yanlış pozitif kabul edilebilir, yanlış negatif KRİTİK**: Güvenlik bağlamında bu asimetri çok önemlidir — Bloom Filter "kesinlikle temiz" derse buna güvenilebilir (hiç kaçırmaz), ama "şüpheli" derse bu ancak bir **ön filtre** olarak kullanılmalı, kesin karar için ek doğrulama (tam veritabanı sorgusu) şarttır. Bloom Filter'ı **tek başına** güvenlik kararı vermek için kullanmak (örneğin "muhtemelen zararlı" çıktığında otomatik engelleme, ikinci doğrulama olmadan) yanlış pozitiflerin meşru trafiği/erişimi engellemesine yol açar.

### Tuzaklar ve En İyi Pratikler

- **Boyutlandırma hatası**: Beklenen eleman sayısı (n) hafife alınırsa, bit dizisi doyuma ulaşır (çoğu bit 1 olur) ve yanlış pozitif oranı hızla %100'e yaklaşır — filtre işe yaramaz hale gelir. Kapasite planlaması (n tahmini + kabul edilebilir yanlış pozitif oranı) baştan yapılmalı.
- **Hash fonksiyonu kalitesi ve bağımsızlığı**: Zayıf/ilişkili hash fonksiyonları, teorik yanlış pozitif oranını ciddi şekilde aşabilir.
- **Silme gerekiyorsa Counting Bloom Filter veya Cuckoo Filter**: Standart Bloom Filter'da silme yoktur; bu ihtiyaç varsa doğru varyant seçilmeli (Cuckoo Filter, ayrıca silme destekler ve genelde daha iyi alan verimliliği sunar, pratikte popülerdir).
- **Dağıtık sistemlerde senkronizasyon**: Birden fazla düğümün kendi Bloom Filter'ı varsa, bunların birleştirilmesi (aynı boyutta ve aynı hash fonksiyonlarıyla oluşturulmuşlarsa bitwise OR ile) mümkündür; farklı parametrelerle oluşturulmuş filtreler birleştirilemez.

---

## 7. Suffix Array ve Suffix Tree

### Tanım ve Kök Neden

Bir metnin tüm sonekleri (suffix) — metnin her pozisyonundan sona kadar olan alt dizeler — üzerine kurulu yapılardır. **Suffix Tree**, tüm sonekleri bir sıkıştırılmış Trie'de (ortak önekler paylaşılarak) tutar. **Suffix Array**, aynı bilgiyi çok daha az bellekle, sonek başlangıç indekslerini **sözlük sırasına göre sıralanmış bir dizi** olarak tutarak sağlar (genelde bir LCP — Longest Common Prefix — dizisiyle birlikte). Kök neden: "Bu metinde şu alt dize var mı / kaç kez geçiyor / en uzun tekrar eden alt dize nedir" gibi sorular, metni her seferinde baştan taramak yerine (O(n*m), m arama dizisi uzunluğu), metni **bir kez** ön işleyip (Suffix Array/Tree inşa ederek) sonraki her sorguyu O(m log n) veya O(m) gibi çok daha hızlı cevaplamayı mümkün kılar.

### Çalışma Mantığı

Suffix Tree inşası naif olarak O(n²) ama Ukkonen algoritması gibi yöntemlerle O(n) yapılabilir (implementasyonu karmaşıktır). Suffix Array inşası da verimli algoritmalarla (örneğin DC3/skew algoritması) O(n) veya O(n log n) yapılabilir ve **çok daha az bellek** kullanır (Suffix Tree'nin pointer-ağırlıklı yapısına kıyasla düz bir tamsayı dizisidir) — bu yüzden pratikte (biyoinformatik, arama motorları, disk-tabanlı log analizi) Suffix Array + LCP dizisi tercih edilir. Bir alt dize arama, sıralı diziler üzerinde ikili arama ile O(m log n)'de yapılabilir.

### Güvenlik ve Savunma Bağlamı

- **IDS imza eşleştirme / derin paket incelemesi (DPI)**: Ağ trafiğinde belirli bayt dizilerinin (exploit imzaları, kötü amaçlı yük parçaları) aranması, özellikle **birden fazla desenin** aynı anda arandığı senaryolarda suffix yapıları (veya Aho-Corasick ile birlikte) devreye girer.
- **Log/adli bilişim (forensics) analizi**: Büyük log dosyalarında veya disk imajlarında tekrar eden dizilerin, gizlenmiş komutların, kod parçalarının aranması — suffix yapıları "bu dize dosyanın neresinde geçiyor" sorusunu tüm dosyayı tekrar tekrar taramadan cevaplar.
- **Kötü amaçlı yazılım (malware) benzerlik analizi**: İki ikili dosya arasındaki en uzun ortak alt dizeyi bulmak (kod klonlama/varyant tespiti), suffix yapılarının (genellikle genelleştirilmiş suffix tree, iki string birleştirilip inşa edilir) klasik uygulamasıdır — malware ailesi sınıflandırmasında kullanılır.
- **Veri sızıntısı tespiti (DLP)**: Hassas veri parçalarının (örneğin bir kaynak kodun veya belgenin parçalarının) büyük veri akışları içinde (giden trafik, dosya paylaşımları) aranması.

### Tuzaklar ve En İyi Pratikler

- **Suffix Tree bellek maliyeti çok yüksektir**: Teorik olarak O(n) düğüm olsa da, gerçek implementasyonlarda sabit çarpan büyüktür (her düğümde pointer'lar, karakter aralıkları); büyük metinlerde (genom dizileri, büyük log dosyaları) pratik değildir. Bu yüzden endüstride genelde **Suffix Array + LCP** tercih edilir.
- **Suffix Tree/Array statik yapılardır**: Metin değiştiğinde (ekleme/çıkarma) yeniden inşa gerekir (ya da pahalı güncelleme algoritmaları); sürekli değişen (streaming) veri için doğrudan uygun değildir — bu tür senaryolarda Trie tabanlı veya pencere bazlı (sliding window) yaklaşımlar tercih edilir.
- **FM-Index gibi ileri yapılar**: Biyoinformatik ve büyük ölçekli metin aramada, Suffix Array'in Burrows-Wheeler Transform (BWT) ile sıkıştırılmış hali olan FM-Index, hem aramayı hem bellek ayak izini daha da iyileştirir — bu, ilgili alanda "bir sonraki adım" olarak bilinmelidir.
- **Karşılaştırma yapılırken doğru yapı seçilmeli**: Basit "bu alt dize var mı" sorusu için tam bir Suffix Tree inşa etmek aşırı mühendisliktir; tek seferlik arama için KMP/Boyer-Moore gibi doğrusal zamanlı string eşleştirme algoritmaları yeterlidir. Suffix yapıları, **aynı metin üzerinde tekrar tekrar farklı sorgular** yapılacaksa (ön işleme maliyetini amorti edecek kadar çok sorgu varsa) mantıklıdır.

---

## Kapanış: Doğru Yapıyı Seçme Mantığı

Bu yedi yapının ortak teması, hepsinin **belirli bir erişim örüntüsündeki (access pattern) darboğazı** hedeflemesidir: Trie ortak önek paylaşımını, Segment Tree/Fenwick dinamik aralık sorgusunu, Union-Find dinamik bağlantı sorgusunu, Skip List basit-ama-hızlı sıralı erişimi, Bloom Filter bellek-verimli olasılıksal üyelik testini, Suffix yapıları tekrarlı alt dize aramasını çözer. Bir savunma mühendisi için doğru soru şudur: "Verim üzerinde hangi işlemler, ne sıklıkla, hangi büyüklükte yapılıyor?" Yanlış yapı seçimi (örneğin statik veri için Segment Tree kullanmak, ya da silme gerektiren bir senaryoda standart Bloom Filter kullanmak) genelde çalışır ama gereksiz karmaşıklık, bellek israfı veya — güvenlik bağlamında daha vahim olarak — yanlış negatif/pozitif kabul edilemez risk olarak geri döner. Bu yapıları "ezbere" değil, **hangi kök sorunu çözdüklerini** anlayarak öğrenmek, yeni karşılaşılan bir performans veya ölçek probleminde doğru aracı seçme yeteneğini kazandırır.
