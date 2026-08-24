# SQL İleri Seviye — Derin Dalış

Bu metin bir özet değil. Amacı, gerçek bir raporlama sisteminde ortaya çıkan somut bir performans/doğruluk sorununu adım adım söküp yeniden kurmak; sonra o dersleri gerçek bir mimari senaryoda derinleştirmek, tasarım seçeneklerinin takaslarını açıkça tartmak ve sahada tekrar tekrar görülen hataları katalogla­maktır. Kod örnekleri çalışır niteliktedir; ağırlıklı olarak PostgreSQL sözdizimi kullanılır, motor farkları geçtikleri yerde belirtilir.

---

## 1. Çözümlü yürüyüş: "Doğru görünen" bir rapor sorgusunun üç ölümcül hatası

Senaryo somut: Bir e-ticaret firmasında "her müşterinin son 30 gündeki toplam harcamasını ve o müşterinin ait olduğu segmentin ortalamasına göre durumunu" veren bir dashboard sorgusu var. Şema:

```sql
CREATE TABLE musteriler (
    id          BIGINT PRIMARY KEY,
    ad          TEXT NOT NULL,
    segment     TEXT NOT NULL,          -- 'bronz','gumus','altin'
    kayit_tarih TIMESTAMPTZ NOT NULL
);

CREATE TABLE siparisler (
    id          BIGINT PRIMARY KEY,
    musteri_id  BIGINT NOT NULL REFERENCES musteriler(id),
    tutar       NUMERIC(12,2) NOT NULL,
    durum       TEXT NOT NULL,          -- 'tamam','iptal','iade'
    olusturma   TIMESTAMPTZ NOT NULL
);
```

### Zafiyetli/hatalı kod

Ekibin ürettiği ilk sürüm şuydu:

```sql
SELECT
    m.ad,
    m.segment,
    SUM(s.tutar) AS toplam_harcama,
    (SELECT AVG(s2.tutar)
     FROM siparisler s2
     JOIN musteriler m2 ON m2.id = s2.musteri_id
     WHERE m2.segment = m.segment) AS segment_ort
FROM musteriler m
LEFT JOIN siparisler s ON s.musteri_id = m.id
WHERE s.olusturma >= NOW() - INTERVAL '30 days'
  AND s.durum = 'tamam'
GROUP BY m.id, m.ad, m.segment
ORDER BY toplam_harcama DESC;
```

Bu sorgu üç ayrı seviyede yanlış — ve üçü de "çalışıyor gibi" göründüğü için testte kolayca gözden kaçar.

### Sorun neden oluşuyor?

**Hata 1 — `LEFT JOIN`'in `WHERE` yüzünden sessizce `INNER JOIN`'e çürümesi.** Niyet, hiç siparişi olmayan müşterileri de raporda (0 harcama ile) göstermekti. Ama `WHERE s.olusturma >= ... AND s.durum = 'tamam'` koşulları, `LEFT JOIN`'in ürettiği `NULL` satırlar üzerinde çalışır. Siparişi olmayan müşterinin `s.olusturma` değeri `NULL`'dır; `NULL >= herhangi_bir_şey` sonucu `UNKNOWN`'dır ve `WHERE` bu satırı eler. Sonuç: outer join anlamını tamamen kaybeder. Bu, ileri SQL'deki en yaygın "sessiz doğruluk hatasıdır" — sorgu hata vermez, sadece yanlış sayıda satır döndürür.

**Hata 2 — Korelasyonlu alt sorgunun yanlış popülasyonu ölçmesi ve N kez çalışması.** `segment_ort` alt sorgusu, o segmentteki **tüm zamanların, her durumdaki** siparişlerinin ortalamasını alıyor. Oysa dış sorgu son 30 günün yalnızca `tamam` siparişlerini topluyor. İki taraf farklı evreni ölçtüğü için karşılaştırma anlamsız. Üstüne, bu korelasyonlu alt sorgu her dış satır için yeniden değerlendirilebilir; büyük tabloda bu, `EXPLAIN`'de iç içe bir tarama olarak patlar.

**Hata 3 — Ortalama tanımının kayması.** İş tarafı "segmentin müşteri başına ortalama harcaması" istiyordu. Alt sorgu ise "sipariş başına ortalama tutar" hesaplıyor. Müşteri başına toplam ile sipariş başına ortalama, elmayla armuttur. Bu, SQL hatası değil, **granülerlik (grain) hatasıdır** — ileri seviyede en pahalıya patlayan sınıf, çünkü sorgu teknik olarak kusursuz çalışır ama iş kararını yanlış yönlendirir.

### Düzeltilmiş/doğru kod

Doğru yaklaşım: (a) filtreyi `LEFT JOIN`'in doğru tarafına yerleştir, (b) önce müşteri granülerliğine indir, (c) segment ortalamasını **aynı** filtrelenmiş kümeden bir window function ile hesapla; böylece hem tek geçiş, hem tutarlı evren.

```sql
WITH musteri_harcama AS (
    SELECT
        m.id,
        m.ad,
        m.segment,
        COALESCE(SUM(s.tutar) FILTER (
            WHERE s.durum = 'tamam'
              AND s.olusturma >= NOW() - INTERVAL '30 days'
        ), 0) AS toplam_harcama
    FROM musteriler m
    LEFT JOIN siparisler s ON s.musteri_id = m.id
    GROUP BY m.id, m.ad, m.segment
)
SELECT
    ad,
    segment,
    toplam_harcama,
    AVG(toplam_harcama) OVER (PARTITION BY segment) AS segment_ort_musteri_basi,
    toplam_harcama - AVG(toplam_harcama) OVER (PARTITION BY segment) AS ort_fark
FROM musteri_harcama
ORDER BY toplam_harcama DESC;
```

Burada üç düzeltme birden var. Birincisi, filtreyi `WHERE`'den çıkarıp `SUM(...) FILTER (WHERE ...)` içine koyduk; artık siparişi olmayan (veya son 30 günde `tamam` siparişi olmayan) müşteri de kümede kalıyor ve `COALESCE` ile 0 alıyor. `FILTER` yan tümcesi standart SQL'dir (PostgreSQL, SQLite destekler); MySQL/SQL Server'da eşdeğeri `SUM(CASE WHEN ... THEN s.tutar END)`'dir. İkincisi, önce `musteri_harcama` CTE'siyle müşteri granülerliğine indik — dolayısıyla `AVG(...) OVER (PARTITION BY segment)` artık "müşteri başına toplam harcamaların segment ortalaması"nı, yani iş tarafının istediği şeyi hesaplıyor. Üçüncüsü, korelasyonlu alt sorguyu tamamen elediğimiz için motor tabloyu bir kez tarayıp segment ortalamasını bölüm içinde üretiyor; N-kez-tekrar sorunu ortadan kalkıyor.

Bir incelik: `AVG` window'unu CTE'nin dışına aldık. İçeri, aynı `SELECT`'e koyamazdık; çünkü `toplam_harcama` bir aggregate ve window function aggregate'lerin **üzerine** çalışmalı — bu da mantıksal işlem sırasında ancak gruplama bittikten sonra mümkün. CTE bu iki katmanı temiz ayırır.

---

## 2. Gerçek sistem örneği: Zamana bağlı "en güncel durum" tablosu ve deduplikasyon

Gerçek sistemlerde en sık karşılaşılan ileri-SQL problemi, "olay akışından (event stream) her varlığın en güncel durumunu çıkarma"dır. Örnek: Bir kargo takip sistemi, her paket için birden çok durum güncellemesi (`hazirlaniyor`, `yolda`, `teslim`) yazar. Dashboard "her paketin **en son** durumu"nu ister; ama ham tablo aynı pakete ait onlarca satır içerir.

```sql
CREATE TABLE kargo_olay (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    paket_id   BIGINT NOT NULL,
    durum      TEXT NOT NULL,
    olay_zaman TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_kargo_paket_zaman ON kargo_olay (paket_id, olay_zaman DESC);
```

### Naif (ve tuzaklı) çözüm

Çok yaygın ilk deneme, bir korelasyonlu `MAX` alt sorgusudur:

```sql
SELECT k.*
FROM kargo_olay k
WHERE k.olay_zaman = (
    SELECT MAX(k2.olay_zaman)
    FROM kargo_olay k2
    WHERE k2.paket_id = k.paket_id
);
```

İki sorunu var. Birincisi, aynı paket için iki olay **aynı** `olay_zaman` değerine sahipse (yüksek hacimli sistemlerde milisaniye çakışması gerçektir), bu sorgu o paket için iki satır döndürür — deduplikasyon başarısız. İkincisi, korelasyonlu alt sorgu okunabilirlik ve bazı motorlarda performans açısından zayıftır.

### Sağlam çözüm — `DISTINCT ON` (PostgreSQL) veya `ROW_NUMBER` (taşınabilir)

PostgreSQL'in `DISTINCT ON`'u tam bu iş için vardır ve yukarıdaki indeksi doğrudan kullanır:

```sql
SELECT DISTINCT ON (paket_id)
    paket_id, durum, olay_zaman
FROM kargo_olay
ORDER BY paket_id, olay_zaman DESC, id DESC;
```

`ORDER BY`'daki `id DESC`, zaman çakışmasında bile deterministik tek satır garantisi verir — beraberliği en büyük `id` (en son eklenen) lehine bozar. Bu satır kritik; onsuz "en son durum" kararsız hale gelir.

Motor-bağımsız istiyorsanız `ROW_NUMBER` deseni her yerde çalışır:

```sql
WITH sirali AS (
    SELECT paket_id, durum, olay_zaman,
           ROW_NUMBER() OVER (
               PARTITION BY paket_id
               ORDER BY olay_zaman DESC, id DESC
           ) AS rn
    FROM kargo_olay
)
SELECT paket_id, durum, olay_zaman
FROM sirali
WHERE rn = 1;
```

Neden `WHERE rn = 1` dış katmanda? Çünkü window function'lar `WHERE`'den **sonra** değerlendirilir; `rn` daha `WHERE` çalışırken mevcut değildir, dolayısıyla CTE/alt sorgu sarması zorunludur. Bu, mantıksal işlem sırasının (FROM → WHERE → GROUP BY → HAVING → window → SELECT → ORDER BY → LIMIT) doğrudan pratik sonucudur.

### Ölçekte gerçek dert: en-son-durum'u sürekli sorgulamak pahalı

Bu sorgu her dashboard yenilemesinde milyonlarca satırı tarıyorsa, mimari bir karar gerekir. İki yaygın çözüm var. **Materialized view** ile sonucu periyodik önceden hesaplayabilirsiniz:

```sql
CREATE MATERIALIZED VIEW paket_guncel AS
SELECT DISTINCT ON (paket_id) paket_id, durum, olay_zaman
FROM kargo_olay
ORDER BY paket_id, olay_zaman DESC, id DESC;

CREATE UNIQUE INDEX ON paket_guncel (paket_id);   -- CONCURRENTLY refresh için şart
-- Yenileme:  REFRESH MATERIALIZED VIEW CONCURRENTLY paket_guncel;
```

`CONCURRENTLY` yenileme, view üzerinde `UNIQUE` indeks olmasını gerektirir; karşılığında yenileme sırasında okuyucuları kilitlemez. Alternatif, yazma anında bir "current state" tablosunu upsert ile güncel tutmaktır:

```sql
CREATE TABLE paket_guncel_tbl (
    paket_id   BIGINT PRIMARY KEY,
    durum      TEXT NOT NULL,
    olay_zaman TIMESTAMPTZ NOT NULL
);
-- Her yeni olayda (trigger ya da uygulama katmanında) çalışır:
INSERT INTO paket_guncel_tbl (paket_id, durum, olay_zaman)
VALUES ($1, $2, $3)
ON CONFLICT (paket_id) DO UPDATE
    SET durum = EXCLUDED.durum,
        olay_zaman = EXCLUDED.olay_zaman
    WHERE EXCLUDED.olay_zaman > paket_guncel_tbl.olay_zaman;
```

Buradaki `WHERE EXCLUDED.olay_zaman > paket_guncel_tbl.olay_zaman` şartı kritik: geç gelen (out-of-order) bir eski olayın, daha yeni durumu ezmesini engeller. Bu satır olmadan, ağdan sırasız gelen bir güncelleme "güncel durum"u geçmişe döndürebilir — dağıtık sistemlerde gerçek bir hata sınıfı.

**Kararın somut takası:** Okuma anlık hızlanır (tek satır primary key araması), karşılığında her yazmaya küçük bir upsert maliyeti biner ve iki yerde tutulan veri arasında tutarlılık sorumluluğu doğar. Materialized view ise yazmayı hiç etkilemez ama okuma "en fazla yenileme aralığı kadar bayat" olur. Kural: Gerçek-zamanlılık şartsa ve okuma/yazma oranı yüksekse (çok okuma, az yazma) upsert'lenen tablo; dakikalık tazelik yeterliyse ve yazma trafiği yoğunsa materialized view daha ucuzdur.

---

## 3. Karşılaştırma / karar: Tasarım seçenekleri ve takasları

İleri SQL, çoğunlukla "bunu şöyle de yazabilirdim" gerginliğidir. Aşağıda sık karşılaşılan dört kararı, ne zaman hangisinin doğru olduğuyla açıyorum.

### CTE mi, alt sorgu mu, geçici tablo mu?

- **CTE (`WITH`)**: Okunabilirlik için varsayılan tercih. PostgreSQL 12+ tek-kullanımlık, yan etkisiz CTE'leri satır içine alır (inline eder); yani filtreleri içeri itebilir. Ama `MATERIALIZED` ile açıkça bir optimizasyon bariyeri de kurabilirsiniz — pahalı bir alt sonucu **bir kez** hesaplayıp defalarca kullanacaksanız bu istenir. Eski MySQL sürümlerinde CTE'ler türetilmiş tablo gibi materialize edilebilir; davranışı `EXPLAIN` ile doğrulayın.
- **Alt sorgu (derived table)**: Motorun en özgür optimize edebildiği biçim; tek kullanımda ve iyileştiricinin filtre-itmesini (predicate pushdown) istediğinizde iyi. Bedeli okunabilirlik.
- **Geçici tablo (`CREATE TEMP TABLE`)**: Ara sonucu birden çok **ayrı** sorguda kullanacaksanız, ya da üzerine indeks kurup istatistik toplatmak istiyorsanız devreye girer. Karşılığında transaction/temizlik yükü ve iyileştiricinin bütünsel plan yapamaması.

Karar kuralı: Önce CTE ile yaz (okunurluk). Yavaşsa `EXPLAIN ANALYZE` ile bariyer mi problem, filtre-itme mi eksik bak; gerekirse `NOT MATERIALIZED` ipucu ver ya da alt sorguya dön.

### `EXISTS` vs `IN` vs `JOIN` (yarı-join için)

"Şu koşula uyan bir alt kaydı olan ana kayıtlar" sorusunda üç yol var, ve takasları önemlidir:

```sql
-- Sipariş vermiş müşteriler:
SELECT * FROM musteriler m WHERE EXISTS
    (SELECT 1 FROM siparisler s WHERE s.musteri_id = m.id);      -- (a)
SELECT * FROM musteriler m WHERE m.id IN
    (SELECT musteri_id FROM siparisler);                          -- (b)
SELECT DISTINCT m.* FROM musteriler m
    JOIN siparisler s ON s.musteri_id = m.id;                     -- (c)
```

- `EXISTS` (a): İlk eşleşmede durur (short-circuit); alt tarafta `NULL` sorunu yoktur. Genelde en güvenli varsayılan.
- `IN` (b): Modern iyileştiriciler çoğunlukla `EXISTS` ile aynı plana çevirir — **ama** alt sorgu `NULL` üretebiliyorsa `NOT IN` felakete döner (aşağıda hata kataloğunda). `IN` için bu risk daha düşüktür ama alışkanlığı `NOT IN`'e taşımak tehlikeli.
- `JOIN + DISTINCT` (c): Eşleşme çokluysa satırları çoğaltır, sonra `DISTINCT` ile toparlarsınız — bu ekstra sıralama/hash maliyetidir. Yarı-join (varlık kontrolü) için genelde en pahalısı; ama alt tablodan **sütun da seçecekseniz** join zaten gereklidir.

Kural: Sadece varlık kontrolü → `EXISTS`. Alt taraftan veri de lazım → `JOIN`. `NOT IN`'den, alt taraf nullable ise, kaçının.

### Normalizasyon vs denormalizasyon (okuma-ağırlıklı raporlama)

Bölüm 2'deki "en-son-durum" problemi bunun somut hali. Tam normalize event tablosundan her seferde hesaplamak yazmayı ucuz, okumayı pahalı tutar. Denormalize "current state" tablosu tam tersi. Karar tamamen orana bağlı: OLTP çekirdeğinde (çok yazma, tekil okuma) normalize kalın; okuma-ağırlıklı analitik/dashboard katmanında materialized view veya upsert'lenen özet tablosu haklıdır. "Her ihtimale karşı denormalize edelim" bir anti-patterndir — tutarsızlık riski ve yazma maliyeti getirir; ölçülmüş bir okuma darboğazı olmadan yapılmamalı.

### `OFFSET` sayfalama vs keyset (cursor) sayfalama

Derin sayfalamada `LIMIT 20 OFFSET 100000` motoru 100020 satır üretip 100000'ini atmaya zorlar — offset büyüdükçe lineer yavaşlar. Keyset sayfalama son görülen anahtardan devam eder ve indeksi doğrudan kullanır:

```sql
-- OFFSET (derinlikte yavaş):
SELECT * FROM siparisler ORDER BY olusturma DESC, id DESC LIMIT 20 OFFSET 100000;
-- Keyset (sabit maliyet):
SELECT * FROM siparisler
WHERE (olusturma, id) < ('2026-01-01 00:00:00+00', 987654)
ORDER BY olusturma DESC, id DESC
LIMIT 20;
```

Takas: Keyset "N. sayfaya atla" yapamaz (yalnızca ileri/geri akış) ve tuple karşılaştırması için bileşik indeksle sıralamanın hizalı olması gerekir. Sonsuz-scroll/API sayfalamada keyset neredeyse her zaman doğru; klasik numaralı sayfalama arayüzü şartsa `OFFSET` kabul edilir ama sayfa derinliğini sınırlayın.

### `UNION` vs `UNION ALL`

Sık yapılan sessiz maliyet: iki sonucu birleştirmek için otomatik `UNION` yazmak. `UNION` **duplikatları eler**, bu da motoru tüm sonucu sıralamaya veya hash'lemeye zorlar — pahalı bir ek adım. İki küme zaten ayrık olduğunu biliyorsanız (örneğin farklı tablolardan, çakışmayan koşullarla), `UNION ALL` kullanın; dedup adımı olmadığı için çok daha ucuzdur. Kural: Duplikat gerçekten mümkün ve elenmesi şartsa `UNION`; aksi her durumda `UNION ALL`. "Emin olmak için `UNION`" alışkanlığı, farkında olmadan büyük tablolarda tam bir sıralama maliyeti ekler.

### Aggregate `FILTER` vs `CASE WHEN`

Koşullu toplama iki biçimde yazılır. Standart `FILTER` (PostgreSQL, SQLite) niyeti net gösterir:

```sql
SELECT
    COUNT(*) FILTER (WHERE durum = 'tamam')  AS tamam_sayi,
    SUM(tutar) FILTER (WHERE durum = 'iade')  AS iade_tutar
FROM siparisler;
```

MySQL/SQL Server'da eşdeğeri `SUM(CASE WHEN durum='iade' THEN tutar END)` desenidir. İkisi aynı planı üretir; `FILTER` yalnızca okunabilirlik kazandırır. Takas mimari değil, taşınabilirlik: motorlar arası çalışacak kod yazıyorsanız `CASE`, tek motora bağlıysanız `FILTER` daha temizdir. Her ikisinde de tek tablo taramasında çok sütunlu koşullu metrik üretebildiğiniz için, aynı işi ayrı ayrı sorgularla yapmaktan kat kat ucuzdur.

---

## 4. Hata-modu kataloğu: Sahada tekrar tekrar görülen 12 tuzak

**1. `NOT IN` + `NULL` = boş sonuç.** Alt sorgu tek bir `NULL` bile döndürürse, `x NOT IN (..., NULL)` her satır için `UNKNOWN` üretir ve tüm sonuç kümesi sessizce boşalır. `NOT EXISTS` kullanın; o `NULL`'a karşı bağışıktır.

**2. `LEFT JOIN`'i `WHERE` ile öldürmek.** Dış tablonun sütununa `WHERE` koşulu koymak outer join'i inner join'e çevirir (Bölüm 1). Koşul, korunan tarafa aitse `ON`'a taşınmalı.

**3. Granülerlik (grain) çoğaltması.** Bir-çok bir join'e ikinci bir bir-çok join eklemek satırları çarpar; ardından `SUM` şişer. İki detay tablosunu ayrı ayrı topla, sonra ana tabloya join'le — ya da fan-out'u fark et.

**4. `SELECT` içinde `GROUP BY`'da olmayan sütun.** Standart SQL bunu reddeder; eski MySQL (`ONLY_FULL_GROUP_BY` kapalı) rastgele bir değer döndürürdü — determinizmi olmayan, hata ayıklaması cehennem bir davranış. Ya grupla ya bir aggregate/`ANY_VALUE` kullan.

**5. Window function'ı `WHERE`'de kullanmaya çalışmak.** `WHERE rn = 1` aynı seviyede yazılamaz; window'lar `WHERE`'den sonra hesaplanır. CTE/alt sorguya sarıp dıştan filtrele.

**6. `ROWS` yerine varsayılan `RANGE` çerçevesi.** `ORDER BY`'lı bir window'da varsayılan çerçeve `RANGE ... CURRENT ROW`'dur; aynı sıralama değerine sahip "peer" satırları hepsini çerçeveye alır. Kümülatif toplam beklerken tekrarlı tarihlerde şişik sonuç verir. Fiziksel satır istiyorsan `ROWS` yaz.

**7. İndeksi fonksiyonla köreltmek.** `WHERE DATE(olusturma) = '2026-07-06'` ham sütun indeksini kullanamaz. Aralığa çevir (`>= gün AND < ertesi_gün`) ya da ifade indeksi kur.

**8. Örtük tip dönüşümü.** `VARCHAR` telefon sütununu sayı sabitiyle karşılaştırmak (veya `bigint` id'yi string ile) indeksi atlatır ve sessizce seq scan'e düşürür. Sabitin tipi sütunla eşleşmeli.

**9. Bileşik indekste sol ön ek ihlali.** `(a, b)` indeksi `WHERE b = ?` tek başına kullanılamaz. Ayrıca aralık koşulundan sonraki sütunlar indekste sınırlanamaz — eşitlikler önce, aralık sonra sıralanmalı.

**10. `COUNT(sutun)` ile `COUNT(*)` karışımı.** `COUNT(sutun)` `NULL`'ları saymaz; `COUNT(*)` tüm satırları sayar. Nullable bir sütunda yanlışlıkla `COUNT(sutun)` yazmak eksik sayı verir ve fark testte kolayca gözden kaçar.

**11. Kayan nokta / para için yanlış tip.** Parayı `FLOAT`/`DOUBLE` ile tutmak yuvarlama sapması biriktirir (`0.1 + 0.2 != 0.3`). Para her zaman `NUMERIC`/`DECIMAL` olmalı; aksi halde `SUM` toplamları cent düzeyinde tutmaz.

**12. Transaction/izolasyon körlüğü.** İki adımda "oku, sonra ona göre yaz" mantığı (örn. stok kontrolü sonra düşme) `READ COMMITTED` altında yarış koşuluna açıktır: iki işlem aynı stoğu okuyup ikisi de düşürebilir. Çözüm `SELECT ... FOR UPDATE` ile satır kilidi ya da uygun izolasyon seviyesi; "SQL doğru ama eşzamanlılık yanlış" hatası bu sınıftandır.

**Bonus — `EXPLAIN`'e güvenip `ANALYZE` yapmamak.** `EXPLAIN` yalnızca iyileştiricinin tahminidir. Gerçek darboğazı ancak `EXPLAIN ANALYZE` gösterir; özellikle **estimated rows ile actual rows** arasındaki büyük sapma, bayat istatistik veya görülemeyen korelasyona işaret eder ve kötü planların bir numaralı kök nedenidir. Yazan sorguları test ederken transaction içinde `ANALYZE` çalıştırıp `ROLLBACK` yapın.

---

## Kapanış

İleri SQL'de ustalık iki eksende toplanır. Birincisi **doğruluk**: outer join semantiği, `NULL`'ın üç-değerli mantığı, granülerlik ve eşzamanlılık — bunlar sorgu hata vermeden yanlış cevap üretebildiği için en tehlikeli olanlardır. İkincisi **performans**: iyileştiricinin plan seçimini, indeks körlüğü nedenlerini ve satır-tahmini sapmalarını okuyabilmek. İkisi de tek bir alışkanlıkta buluşur: bir sorgu yazdığında zihninde önce **anlamının** (hangi evreni, hangi granülerlikte ölçüyorum?) sonra **planının** (motor bunu nasıl yürütür, indeks devreye girer mi?) canlanması. Bu iki soruyu refleks haline getirdiğinde, `EXPLAIN ANALYZE` sadece bu sezgiyi doğrulayan bir araç olur.
