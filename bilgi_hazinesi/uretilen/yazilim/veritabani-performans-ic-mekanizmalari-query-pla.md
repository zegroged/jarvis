# Veritabanı Performans İç Mekanizmaları: Query Planner/Optimizer Internals ve Execution Plan Analizi

## Giriş: "İndeks Ekle" Tavsiyesinin Ötesi

Query optimizasyonu üzerine çoğu kaynak yüzeyseldir: "şu kolona indeks ekle", "SELECT * kullanma", "N+1 sorgusundan kaçın". Bu tavsiyeler faydalıdır ama **neden** işe yaradıklarını açıklamazlar. Gerçek uzmanlık, veritabanının bir SQL metnini nasıl fiziksel bir çalıştırma planına dönüştürdüğünü anlamaktan geçer. Bu makale, `query optimizer` (sorgu iyileştirici) iç mekanizmalarını, `cost-based optimization` (maliyet tabanlı iyileştirme) mantığını, istatistik/histogram yapılarını, `join order` (birleştirme sırası) seçimini ve `execution plan` (çalıştırma planı) okumayı derinlemesine ele alır.

Deklaratif bir dil olan SQL'de siz **ne** istediğinizi söylersiniz; veritabanı **nasıl** getireceğine kendisi karar verir. İşte o kararı veren bileşen `query optimizer`'dır ve modern ilişkisel veritabanlarının en karmaşık parçasıdır.

## Sorgu İşleme Boru Hattı (Query Processing Pipeline)

Bir SQL sorgusu çalıştırılana kadar birkaç aşamadan geçer:

1. **Parser (Ayrıştırıcı):** SQL metnini sözdizimsel olarak kontrol eder ve bir `parse tree` (ayrıştırma ağacı) üretir.
2. **Rewriter / Binder (Yeniden Yazıcı / Bağlayıcı):** View'ları açar, isimleri gerçek tablo/kolon nesnelerine bağlar, bazı mantıksal dönüşümler uygular (örneğin subquery flattening).
3. **Optimizer (İyileştirici):** Mantıksal ağaçtan çok sayıda alternatif fiziksel plan üretir, her birinin maliyetini tahmin eder ve en ucuzunu seçer.
4. **Executor (Çalıştırıcı):** Seçilen planı gerçekten çalıştırır, satırları getirir.

Kritik nokta: Optimizer, planı **çalıştırmadan önce** tahminlerle karar verir. Bu tahminler yanlışsa, seçilen plan felakete dönüşebilir. Optimizer'ı anlamak, aslında bu tahminlerin nereden geldiğini ve nasıl yanılabileceğini anlamaktır.

## Logical Plan ve Physical Plan Ayrımı

Optimizer iki katmanda düşünür:

- **Logical plan (mantıksal plan):** Ne yapılacağını ifade eder. Örneğin "A ve B tablolarını `join` et, sonra filtrele". Cebirsel (relational algebra) düzeydedir.
- **Physical plan (fiziksel plan):** Nasıl yapılacağını belirtir. Aynı `join` için `Nested Loop Join`, `Hash Join` veya `Merge Join` seçilebilir; aynı tablo erişimi için `Sequential Scan` (tam tarama) veya `Index Scan` kullanılabilir.

Tek bir mantıksal sorgu, yüzlerce hatta binlerce fiziksel plana karşılık gelebilir. Optimizer'ın işi bu uzayda arama yapmaktır.

## Cost-Based Optimization (Maliyet Tabanlı İyileştirme)

### Temel Fikir

Modern optimizer'lar (PostgreSQL, Oracle, SQL Server, MySQL/InnoDB) çoğunlukla **cost-based**tir. Her fiziksel operatöre soyut bir **maliyet** sayısı atanır. Bu maliyet, gerçek saniye değil, göreli bir birimdir; genellikle disk I/O ve CPU işlemlerinin ağırlıklı toplamıdır.

Örneğin PostgreSQL'de maliyet modeli şu tür parametrelere dayanır (kavramsal isimlerle):
- Ardışık (sequential) bir sayfa okumanın maliyeti taban alınır (1.0 kabul edilir).
- Rastgele (random) sayfa okuma daha pahalıdır, çünkü disk head hareketi/gecikme içerir.
- CPU başına satır işleme, operatör değerlendirme, tuple kopyalama maliyetleri ayrı ayrı hesaba katılır.

Optimizer her aday plan için tahmini toplam maliyeti hesaplar ve en düşük maliyetli olanı seçer. **Amaç en hızlı planı bulmak değil, maliyet modeline göre en ucuz görünen planı seçmektir** — bu ikisi arasındaki fark, çoğu performans probleminin köküdür.

### Cardinality Estimation: İşin Kalbi

Maliyetin doğruluğu, **cardinality estimation** (kardinalite tahmini) doğruluğuna bağlıdır. Kardinalite, bir operatörün üreteceği tahmini satır sayısıdır.

Örnek: `WHERE status = 'active'` filtresinden kaç satır geçecek? Eğer tablo 10 milyon satırsa ve optimizer 5.000 satır geçeceğini tahmin ederse, `Index Scan` mantıklıdır. Ama gerçekte 8 milyon satır geçiyorsa, `Index Scan` her satır için rastgele I/O yaparak `Sequential Scan`'den çok daha yavaş olur. Yani **hatalı kardinalite tahmini, yanlış plan seçimine yol açar.**

Kardinalite tahminleri boru hattı boyunca çarpılarak ilerler. Bir `join`'in çıktı tahmini, girdi tahminlerine dayanır. Erken bir hata, sonraki operatörlerde **katlanarak büyür** (error propagation). Bu yüzden derin `join` zincirlerinde tahminler dramatik biçimde sapabilir.

## İstatistikler ve Histogramlar

### İstatistik Nedir?

Optimizer gerçek veriyi okumadan kardinalite tahmin edemez; bunun yerine **istatistiklere** başvurur. İstatistikler, tablo ve kolonlar hakkında önceden hesaplanmış özet bilgilerdir:

- **Satır sayısı (row count)** ve tablo/blok boyutu.
- **NDV (Number of Distinct Values):** Bir kolondaki farklı değer sayısı. `n_distinct` olarak da geçer.
- **NULL oranı (null fraction).**
- **Most Common Values (MCV):** En sık görülen değerler ve onların frekansları.
- **Histogram:** Değer dağılımının özeti.

Bu istatistikler tam tarama ile değil, genellikle **örnekleme (sampling)** ile hesaplanır. PostgreSQL'de `ANALYZE`, SQL Server'da istatistik güncellemesi, Oracle'da `DBMS_STATS` bu işi yapar. Örnekleme olduğu için istatistikler her zaman yaklaşıktır.

### Histogramların Çalışma Mantığı

Bir kolonun değer aralığını düşünün. Optimizer `WHERE age BETWEEN 30 AND 40` için kaç satır olduğunu bilmek ister. Histogram, değer aralığını **kova (bucket)** dilimlere böler:

- **Equi-width histogram:** Her kova eşit **değer genişliğine** sahiptir. Çarpık (skewed) dağılımlarda kötü çalışır.
- **Equi-depth (equi-height) histogram:** Her kova yaklaşık **eşit sayıda satır** içerir. Çarpık dağılımlara çok daha dayanıklıdır ve modern veritabanlarında tercih edilen budur. Yoğun bölgelerde kova sınırları sıklaşır, seyrek bölgelerde seyrekleşir.

MCV listesi ile histogram birlikte çalışır: En sık değerler MCV listesinde ayrı tutulur (kesin frekanslarıyla), geri kalan "kuyruk" dağılımı histogramla temsil edilir. Böylece hem popüler değerler hem genel dağılım iyi modellenir.

### Uniformity ve Independence Varsayımları — En Büyük Tuzaklar

Klasik optimizer'ların iki tehlikeli varsayımı vardır:

1. **Uniformity (tekdüzelik):** Histogram kovası içinde değerlerin eşit dağıldığı varsayılır. Kova içi çarpıklık varsa hata oluşur.
2. **Independence (bağımsızlık):** Farklı kolonlardaki koşulların istatistiksel olarak bağımsız olduğu varsayılır. `WHERE city = 'İstanbul' AND country = 'Türkiye'` için optimizer iki koşulun seçiciliğini çarpar. Ama bu kolonlar **korelasyonludur** (İstanbul zaten Türkiye'dir), dolayısıyla gerçek seçicilik tahminden çok farklı olur. Optimizer bu iki koşulu bağımsız kabul edip seçicilikleri çarpınca satır sayısını ciddi biçimde **olduğundan az** tahmin eder.

Bu korelasyon problemine karşı modern sistemler **extended statistics** / **multi-column statistics** sunar (PostgreSQL'de `CREATE STATISTICS`, SQL Server'da multi-column istatistikler). Bunlar kolonlar arası fonksiyonel bağımlılıkları ve birleşik NDV'yi modelleyerek tahminleri düzeltir.

## Access Path Seçimi: Scan vs. Index

Tek bir tabloya erişim için bile birden çok fiziksel yol vardır:

- **Sequential / Full Table Scan:** Tüm tabloyu baştan sona okur. Büyük oranda satır dönecekse (yüksek seçicilik değeri) **daha ucuzdur**, çünkü ardışık I/O yapar.
- **Index Scan:** İndeks üzerinden gider, sonra her eşleşme için tabloya (heap) rastgele erişir. Az satır dönecekse (yüksek selectivity, düşük satır oranı) hızlıdır.
- **Index-Only Scan / Covering Index:** İhtiyaç duyulan tüm kolonlar indekste varsa, tabloya hiç gitmeden sadece indeksten okur. Çok verimlidir.
- **Bitmap Index Scan:** Birden çok indeksin sonuçlarını bit haritasında birleştirir, sonra heap'i sıralı biçimde okur. Orta seçicilikte iyi bir orta yoldur.

Kritik sezgi: **İndeks her zaman iyi değildir.** Eğer bir sorgu tablonun büyük bir kısmını döndürecekse, indeks üzerinden rastgele erişim yapmak tam taramadan yavaştır. Optimizer bu kırılma noktasını (tipik olarak tablonun belli bir oranı, örneğin yaklaşık %5-20 civarı; sisteme ve dağılıma göre değişir) maliyet modeliyle bulmaya çalışır. Bu yüzden düşük seçicilikli bir kolona eklenen indeks kullanılmayabilir — bu bir hata değil, doğru karardır.

## Join Algoritmaları ve Join Order

### Üç Temel Join Algoritması

1. **Nested Loop Join:** Dış tablonun her satırı için iç tabloyu (tercihen indeksle) tarar. Küçük dış tablo + iç tarafta indeks olduğunda çok hızlıdır. Büyük tablolarda O(n×m) yüzünden felaket olur.
2. **Hash Join:** Küçük tablodan bellekte bir `hash table` kurar, büyük tabloyu tarayıp hash'te eşleştirir. Büyük, indekssiz eşitlik (`equi-join`) birleştirmeleri için idealdir. Bellek yetmezse diske taşar (`batches`/`spill`), performans düşer.
3. **Merge Join (Sort-Merge):** Her iki tarafı `join` anahtarına göre sıralar, sonra paralel yürüyüşle birleştirir. Girdiler zaten sıralıysa (örneğin indeks sırasında geliyorsa) çok verimlidir; değilse sıralama maliyeti eklenir.

Optimizer, her `join` için bu üçünden hangisinin en ucuz olduğunu kardinalite tahminlerine göre seçer. Yanlış kardinalite, yanlış algoritma seçimine yol açar: Optimizer 100 satır bekleyip `Nested Loop` seçer ama gerçekte 10 milyon satır gelirse, sorgu saatlerce sürer.

### Join Order Problemi

Birden fazla tabloyu birleştirirken **hangi sırayla** birleştirileceği devasa fark yaratır. `A ⋈ B ⋈ C ⋈ D` için ara sonuçların boyutu, sıraya göre binlerce kat değişebilir. Amaç, ara sonuç kümelerini (intermediate result sets) mümkün olduğunca küçük tutmaktır — çünkü büyük ara küme sonraki her adımı pahalılaştırır.

Sorun şu ki, olası `join order` sayısı tablo sayısıyla **üstel** (faktöriyel) büyür. n tablo için olası ağaç sayısı astronomik olur. Optimizer bu uzayı tam olarak tarayamaz, bu yüzden:

- **Dynamic programming (System R yaklaşımı):** Az sayıda tabloda (tipik olarak belli bir eşiğe kadar) optimal sırayı DP ile bulur. PostgreSQL'in klasik yaklaşımıdır.
- **Genetic / heuristic arama:** Tablo sayısı eşiği aşınca (PostgreSQL'de GEQO gibi) tam arama yerine sezgisel/olasılıksal arama devreye girer; optimal olmayan ama makul planlar üretir.

Bu yüzden çok tablolu (örneğin 15+ tablo `join`) sorgular optimizer için özellikle risklidir; hem tahmin hataları birikir hem de arama uzayı tam taranamaz.

## Execution Plan Analizi: EXPLAIN ve EXPLAIN ANALYZE

### EXPLAIN vs EXPLAIN ANALYZE

- **EXPLAIN:** Sorguyu **çalıştırmadan**, optimizer'ın seçtiği planı ve **tahmini** maliyet/satır sayılarını gösterir.
- **EXPLAIN ANALYZE:** Sorguyu **gerçekten çalıştırır** ve tahminlerin yanında **gerçek** süreleri ve satır sayılarını da gösterir. (Dikkat: yazma sorgularında gerçekten veriyi değiştirir; genelde transaction içinde çalıştırıp `ROLLBACK` yapılır.)

Uzman analizde altın kural: **Estimated rows ile actual rows'u karşılaştır.** Aralarındaki büyük fark (örneğin tahmin 100, gerçek 5.000.000), kötü istatistik veya korelasyon probleminin kanıtıdır. Bu fark, kötü plan seçiminin **kök nedenini** işaret eder.

### Plan Ağacını Okumak

Execution plan bir **ağaçtır** ve içten dışa / aşağıdan yukarı okunur. En içteki (en girintili) operatörler önce çalışır, sonuçlarını üstteki operatöre besler.

Bir PostgreSQL `EXPLAIN ANALYZE` satırında tipik olarak şunlar bulunur:
- Operatör tipi (örn. `Hash Join`, `Seq Scan`, `Index Scan`).
- `cost=X..Y`: Başlangıç maliyeti (ilk satırı üretme) ve toplam maliyet.
- `rows=`: Tahmini satır sayısı.
- `actual time=X..Y`: Gerçek başlangıç ve toplam süre (ms).
- `rows=` (actual): Gerçek satır sayısı.
- `loops=`: Operatörün kaç kez çalıştırıldığı. **Önemli tuzak:** Nested loop'un iç tarafında gösterilen `actual time` ve `rows` değerleri **tek bir loop içindir**; gerçek toplam maliyet için `loops` ile çarpılır.

### Analiz Sırasında Aranacak Kırmızı Bayraklar

1. **Tahmin/gerçek satır uçurumu:** En güçlü teşhis sinyali. Estimated 10, actual 1.000.000 → istatistik/korelasyon sorunu.
2. **Beklenmedik Sequential Scan:** Filtrelenmiş, seçici bir sorguda tam tarama görüyorsanız; indeks eksik olabilir, ya da fonksiyon/tip uyumsuzluğu indeksi kullanılamaz kılıyordur (aşağıya bakın).
3. **Nested Loop üzerinde büyük loop sayısı:** İç taraf çok kez çalışıyorsa ve iç taraf pahalıysa, muhtemelen `Hash Join` daha iyi olurdu — kardinalite az tahmin edilmiş demektir.
4. **Hash join / sort'ta disk'e taşma (spill):** `Sort Method: external merge Disk` veya hash batch artışı, `work_mem`/çalışma belleği yetersizliğini gösterir. Bellek ayarı veya daha az satır getiren bir plan gerekir.
5. **Rescan / materialize:** Aynı alt ağacın tekrar tekrar hesaplanması.
6. **Filter'da atılan satır sayısı (Rows Removed by Filter):** İndeksin işi yapmadığını, satırların erişimden sonra elenmiş olduğunu gösterir.

## Yaygın Hatalar ve Doğru Kullanım

### 1. SARGability'yi Bozmak

**SARGable** (Search ARGument able) bir koşul, indeksin doğrudan kullanılabildiği koşuldur. Kolonun üzerine fonksiyon veya hesap uygulamak SARGability'yi bozar:

- `WHERE YEAR(created_at) = 2026` → indeks kullanılamaz (kolon fonksiyona sarılı).
- `WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01'` → aralık indeksi kullanılabilir.

Aynı şekilde `WHERE status || '' = 'x'`, implicit tip dönüşümleri (kolon `varchar`, karşılaştırma `int`) veya `WHERE col + 0 = 5` gibi ifadeler indeksi kör eder. Doğru yaklaşım koşulu kolonu **yalın** bırakacak biçimde yeniden yazmaktır; alternatif olarak `functional / expression index` (ifade indeksi) oluşturmaktır.

### 2. Bayat İstatistikler (Stale Statistics)

Tabloya büyük bir toplu yükleme yapıp istatistikleri güncellememek, optimizer'ı eski gerçeklikle plan yapmaya zorlar. Sonuç: eskiden mükemmel olan plan artık felakettir. Doğru pratik, büyük veri değişikliklerinden sonra istatistikleri yenilemek (`ANALYZE` / istatistik güncelleme) ve otomatik istatistik toplamayı (autovacuum/auto-update stats) etkin tutmaktır.

### 3. Parameter Sniffing / Plan Caching Tuzağı

Veritabanları prepared statement / plan cache kullanır. İlk çalıştırmadaki parametreye göre plan derlenip önbelleğe alınır. Eğer o parametre atipikse (örneğin çok az satır getiren bir değerken plan `Nested Loop` seçildiyse), sonraki farklı parametreler (çok satır getirenler) aynı kötü planı miras alır. Bu **parameter sniffing** problemidir. Çözümler arasında sorgu ipuçları, plan yeniden derlemeye zorlama veya sorguyu yeniden yazma bulunur.

### 4. İndeksi "Ekle Gitsin" Sanmak

Her indeks yazma (INSERT/UPDATE/DELETE) maliyetini artırır ve disk/bellek tüketir. Kullanılmayan veya düşük seçicilikli indeksler net zarardır. Doğru pratik: gerçek sorgu iş yükünü ölçmek, plan çıktısında indeksin **gerçekten kullanıldığını** doğrulamak ve kullanılmayanları temizlemektir.

### 5. OR ve Fonksiyonel Koşulların Yayılması

`WHERE a = 1 OR b = 2` çoğu zaman tek bir indeksle verimli çözülemez; optimizer tam tarama veya bitmap birleşimi seçebilir. Bazen sorguyu `UNION` ile iki seçici parçaya bölmek çok daha iyi plan verir.

## Optimizer'ı Yönlendirmek: İpuçları ve Sınırları

Bazı sistemler (Oracle, MySQL) doğrudan **optimizer hints** (`/*+ INDEX(...) */`, `USE INDEX`) sunar. PostgreSQL çekirdeği felsefe gereği doğrudan hint sunmaz; bunun yerine istatistikleri iyileştirmeyi, planlayıcı parametrelerini ayarlamayı ve sorguyu yeniden yazmayı önerir.

Uzman tavrı: **Hint bir son çaredir.** Kök neden çoğu zaman kötü kardinalite tahminidir. Hint ile planı sabitlemek, veri dağılımı değiştiğinde yeni bir tuzak yaratır. Önce istatistikleri, korelasyonları ve sorgu yapısını düzeltmek daha kalıcı çözümdür.

## Güvenlik ve Gözlemlenebilirlik Açısından Bir Not

Execution plan analizi bir savunma/gözlem aracıdır. Anormal derecede pahalı sorgular (`slow query log`, `pg_stat_statements` benzeri özet görünümler) hem performans hem güvenlik açısından değerlidir: Beklenmedik tam taramalar veya patlayan `join`'ler bazen kötü niyetli/kaçak sorguların (örneğin filtresiz veri sızdırma denemeleri) da işaretidir. Plan bazlı izleme (baseline plan'lardan sapmayı tespit etmek), hem regresyonları hem anormal erişim desenlerini yakalamak için savunmacı bir katman sağlar. Buradaki amaç saldırı değil, **normal davranışın modelini kurup sapmayı tespit etmektir.**

## Özet: Uzmanın Zihinsel Modeli

1. Optimizer, planı **tahminlerle** ve **maliyet modeline** göre seçer; gerçeği çalıştırmadan görmez.
2. Tahminlerin kalbi **kardinalite tahminidir**; o da **istatistik ve histogramlara** dayanır.
3. En sık kök nedenler: **bayat istatistik**, **kolonlar arası korelasyon** (independence varsayımının çöküşü) ve **kova içi çarpıklık** (uniformity varsayımının çöküşü).
4. Hataları teşhis etmenin altın yolu: `EXPLAIN ANALYZE` ile **tahmini ve gerçek satır sayılarını karşılaştırmak**; sapma büyükse istatistik/korelasyon sorununu aramak.
5. İndeks, `join` algoritması ve `join order`, hepsi bu tahminlerin türevidir. Tahmini düzeltirseniz plan çoğu zaman kendiliğinden düzelir.

Query optimizasyonunda gerçek ustalık, "indeks ekle" reçetelerini ezberlemek değil; optimizer'ın **neye göre karar verdiğini** ve **nerede yanıldığını** okuyabilmektir. Execution plan, bu iç dünyaya açılan penceredir.
