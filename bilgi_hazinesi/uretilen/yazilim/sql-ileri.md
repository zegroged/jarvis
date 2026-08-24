# SQL İleri Seviye: JOIN, Window Function, CTE, Query Plan ve İndeks Kullanımı

Bu makale, SQL'de temel `SELECT` seviyesini geçmiş, ancak sorgularının neden yavaş çalıştığını, veritabanının onları nasıl yürüttüğünü ve daha ifade gücü yüksek sorguları nasıl yazacağını anlamak isteyenler için yazıldı. Amacım kuru bir sözdizimi listesi vermek değil; her konunun **kök nedenini** ve motorun kaputun altında ne yaptığını açıklamak. Çünkü SQL'de gerçek ustalık, komutları ezberlemekten değil, sorgu iyileştiricisinin (query optimizer) nasıl "düşündüğünü" öngörebilmekten gelir.

---

## 1. JOIN'ler: Kümeleri Nasıl Birleştiriyoruz ve Motor Bunu Nasıl Yapıyor?

### Tanım

`JOIN`, iki (veya daha fazla) tablodaki satırları, aralarındaki bir ilişki koşuluna göre yan yana getirme işlemidir. En sık kullanılan türleri `INNER JOIN`, `LEFT/RIGHT OUTER JOIN`, `FULL OUTER JOIN` ve `CROSS JOIN`'dir. Kavramsal olarak bir `JOIN`, iki kümenin kartezyen çarpımını alıp (`CROSS JOIN`) sonra `ON` koşulunu bir filtre olarak uygulamaya eşdeğerdir. Bu zihinsel model önemli; çünkü join'lerin neden bazen patlayarak büyüdüğünü açıklar.

### Kök Neden: JOIN Fiziksel Olarak Nasıl Çalışır?

SQL bir **bildirimsel (declarative)** dildir: siz "ne" istediğinizi yazarsınız, "nasıl" yapılacağına motor karar verir. `A JOIN B ON A.id = B.a_id` yazdığınızda, iyileştirici bunu üç temel fiziksel algoritmadan biriyle gerçekleştirir. Bu algoritmaların ne zaman seçildiğini bilmek, performans sezginizin temelidir:

**Nested Loop Join (İç içe döngü):** Dış tablodaki her satır için, iç tablo taranır veya bir indeks üzerinden aranır. Sözde kod:

```
for dış_satır in A:
    for iç_satır in B where B.a_id = dış_satır.id:
        eşleşenleri döndür
```

İç tarafta uygun bir indeks varsa bu son derece verimlidir: dış tablo `N` satırsa ve iç arama indeksli `log(M)` maliyetliyse, toplam `N * log(M)` olur. Bu yüzden nested loop, **küçük bir dış kümeyi büyük ve indeksli bir iç tabloya** bağlarken idealdir. İç tarafta indeks yoksa maliyet `N * M`'e çıkar ve felakete döner.

**Hash Join:** Motor önce küçük tablodan (build tarafı) bellekte bir hash tablosu kurar, join anahtarını hash'ler. Sonra büyük tabloyu (probe tarafı) tarayıp her satırın anahtarını aynı hash fonksiyonuyla arar. Maliyet yaklaşık `N + M`'dir; yani her iki tabloyu birer kez okur. Bu, **büyük tabloları eşitlik (`=`) koşuluyla** birleştirirken en iyi seçenektir. Dezavantajı: build tarafı belleğe sığmazsa diske taşar (spill) ve yavaşlar. Ayrıca yalnızca eşitlik join'lerinde çalışır; `A.x > B.y` gibi bir koşulda kullanılamaz.

**Merge Join (Sort-Merge):** Her iki tablo da join anahtarına göre sıralıysa (veya sıralanırsa), iki sıralı listeyi zip'ler gibi tek geçişte birleştirir. İki taraf da zaten sıralı geliyorsa (örneğin bir indeks sayesinde) bu çok ucuzdur. Sıralama gerekiyorsa, sıralama maliyeti (`N log N`) devreye girer.

**Neden bu bilgi kritik?** Sorgunuz yavaşsa, `EXPLAIN` çıktısında hangi join tipinin seçildiğine bakarsınız. Büyük tablolarda nested loop görüyorsanız ve iç tarafta indeks yoksa, orada kırmızı alarm var demektir.

### Somut Örnek ve Tuzaklar

```sql
SELECT m.ad, s.tutar
FROM musteriler m
LEFT JOIN siparisler s ON s.musteri_id = m.id
WHERE s.tutar > 100;
```

Bu sorgu bir **klasik tuzak** içerir. `LEFT JOIN` yazıp siparişi olmayan müşterileri de görmek istediğinizi belirttiniz; ancak `WHERE s.tutar > 100` koşulu, siparişi olmayan müşterilerin `s.tutar` değerini `NULL` yaptığı için onları eler. `NULL > 100` sonucu `UNKNOWN`'dır, `WHERE` `UNKNOWN` satırları geçirmez. Sonuç: `LEFT JOIN`'iniz sessizce `INNER JOIN`'e dönüşür. Niyetiniz siparişsiz müşterileri de tutmaksa koşul `ON` yan tümcesine taşınmalı:

```sql
LEFT JOIN siparisler s ON s.musteri_id = m.id AND s.tutar > 100
```

Buradaki ince ayrım: `ON` koşulu join sırasında değerlendirilir (dış tarafın satırları korunur), `WHERE` koşulu join tamamlandıktan sonra tüm sonuca uygulanır.

### Yaygın Hatalar

- **Kartezyen patlaması:** `ON` koşulunu unutmak veya join anahtarının iki tarafta da benzersiz olmadığı bir sütun kullanmak. İki tablonun her birinde anahtar 10 kez tekrarlıyorsa, o anahtar için 100 satır üretilir. Sonuç satır sayınız beklediğinizden çok büyükse önce join çokluğunu (cardinality) sorgulayın.
- **`NULL` ile eşleştirme:** `A.x = B.x` koşulu, iki taraf da `NULL` olduğunda **eşleşmez**, çünkü `NULL = NULL` sonucu `UNKNOWN`'dır. Gerekiyorsa `IS NOT DISTINCT FROM` (destekleyen motorlarda) kullanın.
- **Veri tipi uyuşmazlığı:** Join anahtarları farklı tiplerse (örneğin `VARCHAR` ile `INT`), motor örtük dönüşüm yapar ve genellikle indeksi kullanamaz. Bu, sessiz bir performans katilidir.

### En İyi Pratikler

Join anahtarlarını her zaman indeksli tutun (yabancı anahtar sütunları çoğu motorda otomatik indekslenmez — bunu elle yapmanız gerekir). Join'i mümkün olduğunca erken filtreleyin: iyileştirici genellikle bunu kendisi yapar, ama karmaşık sorgularda alt sorgu veya CTE ile veri kümesini küçültmek yardımcı olabilir.

---

## 2. Window Function'lar: Satırları Gruplamadan Bağlam Kazanmak

### Tanım

Window function (pencere fonksiyonu), her satır için, o satırla ilişkili bir satır kümesi (**pencere**) üzerinden bir hesaplama yapar — **ama satırları birleştirmez**. `GROUP BY` her grubu tek bir satıra indirger; window function ise her satırı korur ve yanına toplu/sıralı bir değer ekler. Sözdiziminin kalbi `OVER (...)` yan tümcesidir:

```sql
fonksiyon() OVER (
    PARTITION BY sütun    -- pencereyi bölümlere ayır
    ORDER BY sütun        -- bölüm içinde sırala
    ROWS/RANGE ...        -- çerçeve (frame): pencerenin sınırları
)
```

### Kök Neden: Neden `GROUP BY` Yetmiyor?

Diyelim ki her çalışanın maaşını, kendi departmanının ortalama maaşıyla **aynı satırda** görmek istiyorsunuz. `GROUP BY departman` yaparsanız departman başına tek satır kalır, çalışan detayını kaybedersiniz. Klasik çözüm, ortalamayı ayrı bir alt sorguda hesaplayıp geri join'lemekti — hem okunması zor hem de tabloyu iki kez tarayan bir yaklaşım. Window function bu ihtiyacı tam olarak karşılamak için var: tabloyu bir kez tarar, her satır için bölüm bağlamını hesaplar.

```sql
SELECT
    ad,
    departman,
    maas,
    AVG(maas) OVER (PARTITION BY departman) AS departman_ort,
    maas - AVG(maas) OVER (PARTITION BY departman) AS ortalamadan_fark
FROM calisanlar;
```

Her satır korunur, yanına departman ortalaması eklenir. `PARTITION BY` olmadan yazarsanız pencere tüm tablodur (genel ortalama).

### Sıralama Fonksiyonları ve Aralarındaki İnce Fark

`ROW_NUMBER`, `RANK` ve `DENSE_RANK` sık karıştırılır. Farkları eşitlik (ties) durumunda ortaya çıkar:

- `ROW_NUMBER()`: Eşitlik olsa bile her satıra benzersiz, kesintisiz numara verir (1, 2, 3, 4).
- `RANK()`: Eşit değerlere aynı rütbeyi verir ama sonraki rütbede **atlar** (1, 2, 2, 4).
- `DENSE_RANK()`: Eşit değerlere aynı rütbeyi verir, **atlamaz** (1, 2, 2, 3).

Her departmanda en yüksek maaşlı ilk 3 çalışanı bulmak için tipik desen:

```sql
WITH siralanmis AS (
    SELECT ad, departman, maas,
           ROW_NUMBER() OVER (PARTITION BY departman ORDER BY maas DESC) AS sira
    FROM calisanlar
)
SELECT ad, departman, maas
FROM siralanmis
WHERE sira <= 3;
```

Neden `WHERE sira <= 3`'ü aynı `SELECT` içine yazamıyoruz? Çünkü window function'lar **`WHERE`'den sonra, ama `SELECT` çıktısından önce** değerlendirilir. `WHERE` çalışırken `sira` sütunu henüz hesaplanmamıştır. Bu yüzden window function'ı bir CTE veya alt sorguya sarıp dıştan filtrelemek zorundayız. Bu, mantıksal işlem sırasını bilmenin doğrudan pratik sonucudur.

### Çerçeve (Frame): En Çok Kaçırılan Detay

`ORDER BY` kullanan bir window function'da, varsayılan çerçeve çoğu zaman `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`'dur. Bu, kümülatif toplam gibi çalışır — pencerenin başından o anki satıra kadar. Kümülatif (running total) toplam bu yüzden şöyle yazılır:

```sql
SUM(tutar) OVER (ORDER BY tarih ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
```

Burada **`ROWS` ile `RANGE` arasındaki fark** kritik bir tuzaktır. `ROWS` fiziksel satır sayar. `RANGE` ise `ORDER BY` değeri aynı olan tüm satırları tek "peer grup" olarak ele alır. Aynı tarihte birden çok kayıt varsa, `RANGE` hepsini birden çerçeveye alır, `ROWS` almaz. Beklenmedik kümülatif toplamlar aldığınızda ilk bakılacak yer budur.

`LAG()` ve `LEAD()` ise bir önceki / sonraki satırın değerini getirir — zaman serisinde "geçen aya göre değişim" hesaplamanın en temiz yoludur:

```sql
tutar - LAG(tutar) OVER (ORDER BY ay) AS aylik_degisim
```

### Yaygın Hatalar ve En İyi Pratikler

- `PARTITION BY`'ı `GROUP BY` ile karıştırmak. Bunlar tamamen farklı işlerdir; window function grupları çökertmez.
- `ORDER BY` gerektiren bir fonksiyonda (örn. `LAG`, sıralama fonksiyonları) `ORDER BY`'ı unutmak — sonuç deterministik olmaz.
- Aynı `OVER (...)` tanımını defalarca tekrarlamak yerine `WINDOW` yan tümcesiyle isimlendirmek (destekleyen motorlarda) hem okunurluğu hem de bakımı artırır.

---

## 3. CTE (Common Table Expression): Sorguyu Okunur Parçalara Bölmek

### Tanım

CTE, `WITH` anahtar sözcüğüyle tanımlanan, o sorgunun ömrü boyunca geçerli olan geçici, isimlendirilmiş bir sonuç kümesidir. Karmaşık bir sorguyu, iç içe alt sorgu yığını yerine yukarıdan aşağı okunan mantıksal adımlara böler.

```sql
WITH aylik_satis AS (
    SELECT musteri_id, DATE_TRUNC('month', tarih) AS ay, SUM(tutar) AS toplam
    FROM siparisler
    GROUP BY musteri_id, DATE_TRUNC('month', tarih)
),
ortalama AS (
    SELECT musteri_id, AVG(toplam) AS ort_aylik
    FROM aylik_satis
    GROUP BY musteri_id
)
SELECT a.*, o.ort_aylik
FROM aylik_satis a
JOIN ortalama o ON o.musteri_id = a.musteri_id;
```

### Kök Neden: CTE Ne İşe Yarar, Ne İşe Yaramaz?

CTE'nin birincil değeri **okunabilirlik ve tekrar kullanımdır**, ille de performans değil. Bir alt sorguyu bir kez tanımlayıp aynı sorguda birkaç kez adıyla çağırabilirsiniz. Ancak yaygın bir yanılgı, CTE'nin her zaman "materialize" edildiği (sonucunun geçici bir tabloya yazılıp öyle kullanıldığı) inancıdır. Gerçek, motora ve sürüme göre değişir:

- Bazı motorlar CTE'yi **optimizasyon sınırı (optimization fence)** olarak ele alır: CTE ayrı hesaplanır, dıştaki filtreler içeri itilemez. Bu, bazen istenir (bir kez hesaplayıp defalarca kullanma), bazen istenmez (gereksiz büyük ara sonuç).
- Modern PostgreSQL sürümleri, yalnızca bir kez kullanılan ve yan etkisiz CTE'leri satır içine alabilir (inline), yani alt sorgu gibi davranır ve filtreleri içeri itebilir. Yine de bunu garanti saymayın; `MATERIALIZED` / `NOT MATERIALIZED` gibi ipuçlarıyla davranışı açıkça belirtmek mümkündür.

**Pratik sonuç:** CTE'yi okunabilirlik için kullanın. Performans açısından "CTE mi alt sorgu mu daha hızlı?" sorusunun cevabı motora ve `EXPLAIN` çıktısına bakmadan verilemez. Emin değilseniz iki yazımı da `EXPLAIN` ile karşılaştırın.

### Recursive CTE: Hiyerarşi ve Graf Gezintisi

CTE'nin gerçekten benzersiz gücü, kendi kendine referans verebilen **özyinelemeli (recursive)** biçimindedir. Ağaç yapıları (organizasyon şeması, kategori ağacı, malzeme listesi) gezmek için tasarlanmıştır:

```sql
WITH RECURSIVE ast AS (
    -- Çıpa (anchor): başlangıç satırı
    SELECT id, ad, yonetici_id, 1 AS seviye
    FROM calisanlar
    WHERE yonetici_id IS NULL

    UNION ALL

    -- Özyineli adım: bir önceki seviyenin çocukları
    SELECT c.id, c.ad, c.yonetici_id, a.seviye + 1
    FROM calisanlar c
    JOIN ast a ON c.yonetici_id = a.id
)
SELECT * FROM ast ORDER BY seviye;
```

Çalışma mantığı: Çıpa sorgusu bir kez çalışır ve başlangıç kümesini üretir. Sonra özyineli kısım, bir önceki adımın **yalnızca yeni gelen** satırlarına join'lenerek tekrar tekrar çalışır, ta ki yeni satır üretilmeyene kadar. `UNION ALL` biriktirilmiş tüm satırları döndürür.

En büyük tehlike **sonsuz döngüdür**: verinizde bir çevrim (cycle) varsa — örneğin A'nın yöneticisi B, B'nin yöneticisi A ise — özyineleme durmaz. Bunun için ya gezilen düğümleri bir dizide takip edip tekrarları eleyin, ya da bir `seviye < N` sınırı koyun. Bazı motorlar `CYCLE` yan tümcesiyle bunu yerleşik olarak sunar.

### En İyi Pratikler

Derin iç içe alt sorgular yerine CTE zinciri kullanın — hata ayıklaması ve okunması kat kat kolaydır. Ama bir CTE'yi tek seferde tek yerde kullanıyorsanız ve motor onu materialize ediyorsa, performans için basit alt sorgu daha iyi olabilir. Recursive CTE'lerde daima bir sonlanma koşulu tasarlayın.

---

## 4. Query Plan (Sorgu Planı): Motorun Zihnini Okumak

### Tanım

Query plan, iyileştiricinin sorgunuzu yürütmek için seçtiği fiziksel operatörlerin ağacıdır: hangi tablo nasıl taranacak, join'ler hangi algoritmayla ve hangi sırayla yapılacak, sıralama/gruplama nerede olacak. `EXPLAIN` komutu bu planı gösterir; `EXPLAIN ANALYZE` ise sorguyu gerçekten çalıştırıp tahmini değerlerin yanında **gerçek** süre ve satır sayılarını da verir.

### Kök Neden: İyileştirici Neden ve Nasıl Karar Verir?

İyileştirici, aynı sonucu üretebilecek çok sayıda alternatif plan arasından **maliyeti en düşük** olanı seçmeye çalışır. Bu maliyet, tahmini disk/CPU işine dayanan soyut bir sayıdır. Kararın kalbinde **istatistikler** yatar: her sütunun kaç farklı değeri var (cardinality), veri nasıl dağılmış, tablo kaç satır. Motor bu istatistiklerle "bu filtre yaklaşık kaç satır döndürür?" tahminini yapar ve buna göre join algoritması ile join sırasını seçer.

**En kritik içgörü:** Kötü planların baş nedeni yanlış **satır sayısı tahminidir (cardinality estimation)**. Motor bir adımdan 10 satır çıkacağını sanıp nested loop seçer; gerçekte 10 milyon satır çıkarsa sorgu saatlerce sürer. Bu yüzden `EXPLAIN ANALYZE` çıktısında **tahmini satır (estimated rows) ile gerçek satır (actual rows) arasındaki büyük sapmalar** aradığınız ilk şeydir. Büyük sapma, ya istatistiklerin bayat olduğunu ya da iyileştiricinin göremediği bir korelasyon olduğunu gösterir.

### Bir Planı Nasıl Okumalı?

Plan bir ağaçtır ve **içten dışa, alttan yukarı** çalışır: en girintili (en derin) düğümler önce yürütülür, sonuçları yukarıya akar. Okurken şunlara bakın:

- **Sequential Scan (Seq Scan) vs. Index Scan:** Küçük tablolarda veya tablonun büyük kısmını okuyan sorgularda seq scan normaldir, hatta indeksten hızlıdır. Ama çok büyük bir tablodan tek satır çekerken seq scan görüyorsanız, muhtemelen kullanılabilir bir indeks yok veya WHERE koşulunuz indeksi kullanamaz halde.
- **Join tipi:** Yukarıda anlatılan nested loop / hash / merge. Büyük-büyük tablo join'inde nested loop görmek çoğunlukla kötüye işarettir.
- **Satır tahmini sapması:** Yukarıda vurgulandı — en önemli sinyal.
- **Maliyetin büyük kısmının nerede toplandığı:** En pahalı düğümü bulun ve iyileştirme çabanızı oraya yoğunlaştırın.

### Somut Örnek

```sql
EXPLAIN ANALYZE
SELECT * FROM siparisler WHERE musteri_id = 42;
```

Çıktıda `Index Scan using idx_musteri on siparisler` görürseniz iyi; `Seq Scan on siparisler` görüp tablo büyükse, `musteri_id` üzerine indeks eklemeyi düşünün. `EXPLAIN ANALYZE`'daki `rows=... actual rows=...` kısmını karşılaştırıp tahminin ne kadar isabetli olduğunu kontrol edin.

### Yaygın Hatalar

- **Yalnızca `EXPLAIN`'e güvenip `ANALYZE` kullanmamak.** `EXPLAIN` yalnızca tahmindir; gerçek darboğazı görmek için (dikkatli olmak kaydıyla, çünkü `ANALYZE` sorguyu gerçekten çalıştırır — `INSERT/UPDATE/DELETE` için transaction içinde deneyin) `ANALYZE` gerekir.
- **Bayat istatistikler.** Büyük veri yüklemesinden sonra istatistikleri güncellemezseniz iyileştirici karanlıkta karar verir. Çoğu motorda istatistik toplama komutu (`ANALYZE` / `UPDATE STATISTICS` benzeri) vardır; otomatik toplama açık olsa bile büyük değişikliklerden sonra elle tetiklemek işe yarar.
- **Tek bir çalıştırmanın süresine bakıp sonuç çıkarmak.** İlk çalıştırma diskten okur (cold cache), ikincisi bellekten (warm cache). Karşılaştırma yaparken bu farkı hesaba katın.

---

## 5. İndeks Kullanımı: Neden Hızlandırır, Ne Zaman İşe Yaramaz?

### Tanım ve Kök Neden

İndeks, bir tablonun bir veya birden çok sütunu üzerine kurulan, aramayı hızlandıran yardımcı bir veri yapısıdır. En yaygın türü **B-tree**'dir: dengeli, sıralı bir ağaç. Bir kitabın arka dizini gibi düşünün — tüm kitabı okumak yerine dizinden aradığınız terime gidip sayfayı buluyorsunuz. İndeks sayesinde motor, tabloyu baştan sona taramak (`O(N)`) yerine ağaçta logaritmik zamanda (`O(log N)`) ilgili satırlara ulaşır.

B-tree'nin **sıralı** olması kritiktir: bu yüzden eşitlik aramalarını (`=`), aralık aramalarını (`>`, `<`, `BETWEEN`) ve `ORDER BY` sıralamasını hızlandırabilir. Değerler ağaçta zaten sıralı durduğundan, motor sıralama işini indeksten "bedavaya" alabilir.

### İndeks Ne Zaman Kullanılamaz? (En Önemli Bölüm)

İndeksin var olması, kullanılacağı anlamına gelmez. En sık karşılaşılan **indeks körlüğü** nedenleri:

**1. Sütuna fonksiyon uygulamak.** `WHERE YEAR(tarih) = 2024` yazarsanız, motor `tarih` sütunundaki ham değerleri değil, fonksiyonun sonucunu araması gerekir; ham sütun üzerine kurulu indeks işe yaramaz. Çözüm ya koşulu **sargable** (search-argument-able) hale getirmektir:

```sql
WHERE tarih >= '2024-01-01' AND tarih < '2025-01-01'
```

ya da fonksiyonun kendisi üzerine bir **ifade indeksi (expression/functional index)** kurmaktır.

**2. Örtük tip dönüşümü.** `WHERE telefon = 5551234` gibi bir sorguda `telefon` sütunu `VARCHAR` ise, motor sütunu sayıya (veya sayıyı stringe) çevirmek zorunda kalır ve indeksi atlar. Sorgudaki sabitin sütunla aynı tipte olmasına dikkat edin.

**3. Baştaki joker.** `WHERE ad LIKE '%mehmet'` — B-tree soldan sağa sıralıdır; başta `%` varsa nereden başlanacağı belli olmadığından indeks kullanılamaz. `LIKE 'mehmet%'` ise indeks dostudur.

**4. Düşük seçicilik (low selectivity).** Bir sütunda yalnızca birkaç farklı değer varsa (örneğin `cinsiyet`, `aktif_mi`), indeks üzerinden gitmek çoğu zaman seq scan'den yavaştır; çünkü motor zaten satırların büyük kısmını okuyacaktır ve indeksten tabloya rastgele erişim (random I/O) pahalıdır. İyileştirici bu durumda bilerek indeksi kullanmaz — bu bir hata değil, doğru karardır.

### Bileşik (Composite) İndeksler ve Sol Ön Ek Kuralı

Birden çok sütun üzerine kurulu indekste **sütun sırası kritiktir**. `(a, b, c)` indeksi kavramsal olarak önce `a`'ya, eşitlerde `b`'ye, sonra `c`'ye göre sıralıdır. Bu yüzden yalnızca bir **sol ön eki (leftmost prefix)** kullanan sorgular indeksten yararlanabilir:

- `WHERE a = ?` → kullanır
- `WHERE a = ? AND b = ?` → kullanır
- `WHERE a = ? AND b = ? AND c = ?` → tam kullanır
- `WHERE b = ?` (a olmadan) → **kullanamaz** (soldaki sütun atlanmış)

Ayrıca bir **aralık koşulu** bir sütunda kullanıldığında, ondan sonraki sütunlar eşitlik için indeksi verimli kullanamaz. Yani `WHERE a = ? AND b > ? AND c = ?` sorgusunda `c` kısmı indeksle sınırlanamaz; çünkü `b` üzerindeki aralık, `c`'nin sıralı ardışıklığını bozar. Bu yüzden bileşik indeks tasarlarken **önce eşitlik koşullu sütunlar, sonra aralık koşullu sütun** kuralı iyi bir başlangıç noktasıdır.

### Kapsayan İndeks (Covering Index)

Eğer bir indeks, sorgunun ihtiyaç duyduğu **tüm** sütunları içeriyorsa, motor cevabı doğrudan indeksten üretir ve asıl tabloya hiç gitmez. Buna **index-only scan** denir ve pahalı tablo erişimlerini tamamen ortadan kaldırdığı için çok hızlıdır. Bazı motorlarda `INCLUDE` yan tümcesiyle, aramaya girmeyen ama sonuçta gereken sütunları indeksin yaprağına ekleyebilirsiniz.

### İndeksin Bedeli

İndeks bedava değildir. Her `INSERT`, `UPDATE`, `DELETE` işleminde, ilgili indekslerin de güncellenmesi gerekir. Bir tabloya on tane indeks koyarsanız, her yazma işlemi on ek yapıyı da bakımlı tutmak zorundadır — yazma performansı düşer, disk alanı artar. Bu yüzden indeks stratejisi bir **okuma-yazma dengesi** meselesidir: yalnızca gerçekten sorgulanan ve seçiciliği yüksek sütunlara, ölçülmüş bir ihtiyaç üzerine indeks ekleyin.

### Yaygın Hatalar ve En İyi Pratikler

- **Rastgele, "ne olur ne olmaz" indeksleri.** Her sütuna indeks atmak yazmaları yavaşlatır ve iyileştiriciyi de yormaz ama diski şişirir. Ölçün, sonra ekleyin.
- **Yabancı anahtarları indekslemeyi unutmak.** `JOIN` ve silme (`ON DELETE`) performansı doğrudan bundan etkilenir.
- **İndeks tasarımını sorgu desenine göre değil, tablo yapısına göre yapmak.** İndeks, tablonun nasıl **sorgulandığını** yansıtmalıdır; hangi sütunlar `WHERE`, `JOIN` ve `ORDER BY`'da geçiyorsa onlar adaydır.
- **Değişiklikten sonra doğrulamamak.** İndeks ekledikten sonra `EXPLAIN` ile gerçekten kullanıldığını teyit edin. İyileştirici indeksi görmezden geliyorsa, muhtemelen yukarıdaki körlük nedenlerinden biri veya seçicilik sorunu vardır.

---

## Kapanış: Bütünü Görmek

Bu beş konu birbirinden kopuk değil, aynı bütünün parçalarıdır. Bir sorgu yavaş çalıştığında izleyeceğiniz zincir hep aynıdır: `EXPLAIN ANALYZE` ile **query plan**'i okursunuz; orada uygunsuz bir **join** algoritması veya bir **seq scan** görürsünüz; bunun kök nedeninin ya eksik/kullanılamaz bir **indeks** ya da yanlış satır tahmini olduğunu anlarsınız; sorguyu **CTE**'lerle okunur adımlara bölerek ve **window function**'larla gereksiz self-join'leri eleyerek hem netleştirir hem hızlandırırsınız.

SQL'de ustalık, sözdizimini ezberlemek değil, "motor bu sorguyu gördüğünde ne yapar?" sorusuna güvenle cevap verebilmektir. Bir sorgu yazdığınızda zihninizde onun planını canlandırabiliyorsanız — hangi tablonun taranacağını, hangi join'in seçileceğini, indeksin devreye girip girmeyeceğini öngörebiliyorsanız — ileri seviyeye geçmişsiniz demektir. Gerisi, `EXPLAIN` çıktısıyla sezginizi sürekli sınamaktan ibarettir.
