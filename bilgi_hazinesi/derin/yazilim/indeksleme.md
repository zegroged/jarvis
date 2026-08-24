# Veritabanı İndeksleme — Derin Dalış

Bu metin, indekslemenin "ne olduğunu" değil, gerçek kod üzerinde **nasıl yanlış gittiğini ve nasıl doğrulandığını** işler. Özet makalede B-tree, composite ve covering indekslerin mantığı anlatıldı; burada bir sorgunun neden indeksi kullanamadığını, planı okuyarak nasıl teşhis edildiğini ve üretimde hangi tuzaklara düşüldüğünü uygulamalı olarak ele alıyoruz. Örnekler PostgreSQL sözdizimi ağırlıklıdır; ilkeler MySQL/InnoDB, SQL Server ve SQLite için de geçerlidir, farklılıklar belirtilir.

---

## 1. Çözümlü yürüyüş: "İndeks var ama sorgu neden hâlâ full scan yapıyor?"

Gerçekçi bir senaryo. Bir e-ticaret uygulamasında `orders` tablosu var ve müşteri hizmetleri ekibi "bir müşterinin belli bir aydaki siparişleri" sorgusunu çok sık çalıştırıyor. Geliştirici indeksi eklemiş, yine de sorgu yavaş.

### Başlangıç: tablo ve "doğru göründüğü" hâliyle indeks

```sql
CREATE TABLE orders (
    id           BIGSERIAL PRIMARY KEY,
    customer_id  BIGINT      NOT NULL,
    status       VARCHAR(20) NOT NULL,
    total_cents  BIGINT      NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Geliştiricinin eklediği indeks
CREATE INDEX idx_orders_created_at ON orders (created_at);
CREATE INDEX idx_orders_customer   ON orders (customer_id);
```

Ve sorgu, ORM'in ürettiği tipik hâliyle:

```sql
-- ZAFİYETLİ SORGU
SELECT id, total_cents, created_at
FROM orders
WHERE customer_id = 91827
  AND date_trunc('month', created_at) = date '2026-06-01';
```

Geliştirici şöyle düşünüyor: "`customer_id` indeksli, `created_at` indeksli, ikisi de var, o hâlde hızlı olmalı." Oysa `EXPLAIN ANALYZE` şunu gösteriyor:

```
Bitmap Heap Scan on orders  (rows=41 ...)
  Recheck Cond: (customer_id = 91827)
  Filter: (date_trunc('month', created_at) = '2026-06-01')
  Rows Removed by Filter: 5872
  ->  Bitmap Index Scan on idx_orders_customer  (rows=5913 ...)
```

### Sorun nerede — iki ayrı kök neden

**Birinci sorun: `date_trunc(created_at)` sütunu non-sargable yapıyor.** İndeks ham `created_at` değerine göre sıralıdır. Motor "hangi satırların `date_trunc`'ı 2026-06-01'e eşit?" sorusunu indeks üzerinde cevaplayamaz; çünkü indekste `date_trunc` değerleri diye bir sıralama yoktur. Bu yüzden `created_at` indeksi tamamen atlandı, plandaki `Filter` ve `Rows Removed by Filter: 5872` bunu ele veriyor: 5913 satır `customer_id` üzerinden çekildi, sonra 5872'si tek tek fonksiyon hesaplanıp elendi. Yani indeks aramanın değil, sadece ilk daraltmanın işine yaradı.

**İkinci sorun: iki tekil indeks, bir composite'in yerini tutmuyor.** Motor `idx_orders_customer` ile 5913 satır buldu ve tarihi filtre olarak uyguladı. `created_at` üzerindeki tekil indeks bu sorguda pratikte ölü yük.

### Düzeltme adım 1: koşulu sargable hâle getir

Sütuna fonksiyon uygulamak yerine, aralığı sütunun **ham hâline** çevir. `date_trunc('month', created_at) = '2026-06-01'` matematiksel olarak şuna eşittir:

```sql
created_at >= '2026-06-01' AND created_at < '2026-07-01'
```

Aradaki fark kritik: ikinci biçimde `created_at` çıplak duruyor, indeks bir **range scan** ile doğrudan aralığı bulabilir.

### Düzeltme adım 2: doğru composite indeks

Sorgu `customer_id`'yi **eşitlikle**, `created_at`'i **aralıkla** filtreliyor. Özet makaledeki "eşitlik önce, aralık sonra" kuralı tam da bunun için var:

```sql
DROP INDEX idx_orders_created_at;
DROP INDEX idx_orders_customer;

CREATE INDEX idx_orders_customer_created
    ON orders (customer_id, created_at)
    INCLUDE (total_cents);
```

`customer_id` başta çünkü eşitlik; `created_at` sonra çünkü aralık. `total_cents` `INCLUDE` içinde çünkü sadece `SELECT` çıktısında lazım, filtrelemede değil — böylece sorgu **index-only scan** olur (`id` zaten PK olarak InnoDB'de leaf'te, PostgreSQL'de heap'te; PostgreSQL için index-only scan'in tam çalışması `VACUUM` ile visibility map'in güncel olmasına bağlıdır).

### Düzeltilmiş sorgu ve plan

```sql
-- DOĞRU SORGU
SELECT id, total_cents, created_at
FROM orders
WHERE customer_id = 91827
  AND created_at >= '2026-06-01'
  AND created_at <  '2026-07-01';
```

```
Index Only Scan using idx_orders_customer_created on orders  (rows=41 ...)
  Index Cond: ((customer_id = 91827)
               AND (created_at >= '2026-06-01') AND (created_at < '2026-07-01'))
  Heap Fetches: 0
```

`Rows Removed by Filter` kayboldu, `Index Cond` içinde her iki koşul da var, `Heap Fetches: 0` tabloya hiç inilmediğini söylüyor. Aynı mantıksal sorgu, iki farklı yazımla iki ayrı dünyaya çıkıyor. Ders: **indeksin "var olması" değil, sorgunun onu kullanabilir biçimde yazılmış olması** önemlidir.

### İfade indeksi ne zaman kaçınılmazdır

Yukarıda tarih koşulunu aralığa çevirebildik çünkü `date_trunc` cebirsel olarak bir aralığa denk düşüyordu. Ama her fonksiyon böyle çevrilemez. Klasik örnek büyük/küçük harf duyarsız e-posta araması:

```sql
-- Bu koşulu aralığa çeviremezsiniz
SELECT id FROM users WHERE lower(email) = 'ayse@example.com';
```

`lower(email)` bir aralığa dönüşmez. Burada tek doğru çözüm **ifade (functional) indeksi** kurmaktır — indeksin kendisi de aynı ifadeye göre sıralanır:

```sql
CREATE INDEX idx_users_email_lower ON users (lower(email));
```

Kritik kural: planlayıcının bu indeksi kullanabilmesi için `WHERE` koşulundaki ifadenin indekstekiyle **birebir** eşleşmesi gerekir. `WHERE lower(email) = ...` çalışır; `WHERE email = ...` çalışmaz (o düz indeks ister); `WHERE lower(email || '')` gibi ufak bir sapma bile indeksi kaçırtır. Aynı prensip `WHERE (data->>'country') = 'TR'` gibi JSON çıkarımları ve generated column'lar için de geçerlidir: neyi sorguluyorsan onu indeksle.

### Fiziksel gerçek: yazma yolunun bir INSERT sırasında ne yaptığı

Şimdiye kadar okuma tarafına baktık. Aynı `idx_orders_customer_created` indeksinin yazmaya maliyetini somutlaştıralım. Tek bir `INSERT INTO orders (...)`:

1. Yeni satır heap'e (veya InnoDB'de kümeli indeksin yaprağına) yazılır.
2. Motor `(customer_id, created_at)` anahtarının indekste **hangi yaprak sayfaya** ait olduğunu bulmak için ağaçta kökten yaprağa iner (3-4 sayfa okuma).
3. Anahtar o yaprağa eklenir. Yaprak doluysa **page split** tetiklenir: yeni sayfa ayrılır, anahtarların ~yarısı taşınır, üst düğüme yeni bir işaretçi eklenir, gerekirse bu bölünme yukarı doğru yayılır.
4. Tüm bu değişiklikler WAL/redo log'a yazılır (dayanıklılık için).

Yani "tek satır ekledim" dediğin işlem, N indeks varsa **1 heap yazması + N ağaç inişi + olası N page split + WAL** demektir. Bu, özet makaledeki write amplification'ın fiziksel karşılığıdır. `customer_id` rastgele dağıldığı için bu indekste ekleme noktası her yere düşer — bu da bir sonraki bölümdeki anahtar-sıra tartışmasını doğrudan gündeme getirir.

---

## 2. Gerçek sistem örneği: keyset pagination ve "derin OFFSET" felaketi

En sık üretim yavaşlaması yaratan indeks-ilişkili hatalardan biri sayfalamadır. Bir aktivite akışı düşünelim: `feed` tablosu, kullanıcıya en yeniden eskiye doğru olaylar gösteriyor, "daha fazla yükle" ile sayfalanıyor.

### Yaygın (ve ölçekte çöken) yaklaşım: OFFSET

```sql
CREATE TABLE feed (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    event_type SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_feed_user_created ON feed (user_id, created_at DESC, id DESC);

-- 500. sayfa, sayfa başına 20 kayıt
SELECT id, event_type, created_at
FROM feed
WHERE user_id = 4471
ORDER BY created_at DESC, id DESC
OFFSET 10000 LIMIT 20;
```

İndeks doğru — `(user_id, created_at DESC, id DESC)` sıralı erişimi karşılıyor. Ama `OFFSET 10000` şu demek: motor indeks üzerinde ilk 10.000 satırı **okumak, saymak ve atmak** zorunda, sadece 20 tanesini döndürmek için. `EXPLAIN ANALYZE` bunu net gösterir:

```
Limit  (actual rows=20 ...)
  ->  Index Scan using idx_feed_user_created on feed
        (actual rows=10020 ...)     <-- 10020 satır gerçekten okundu
```

Sayfa numarası büyüdükçe maliyet doğrusal artar; 5000. sayfada 100.000 satır taranır. İndeks var ama OFFSET onu boşa harcatıyor.

### Çözüm: keyset (seek) pagination

Sayfayı numarayla değil, **son görülen satırın anahtarıyla** iste. Bu, indeksin sıralı yapısını gerçekten kullanır:

```sql
-- Önceki sayfanın son satırı: created_at = :last_ts, id = :last_id
SELECT id, event_type, created_at
FROM feed
WHERE user_id = 4471
  AND (created_at, id) < (:last_ts, :last_id)   -- satır-değer karşılaştırması
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

`(created_at, id) < (:last_ts, :last_id)` bir **row-value constructor** karşılaştırmasıdır. `created_at` eşit olduğunda `id`'ye kırılan bileşik "önce/sonra" ilişkisini tek koşulda ifade eder ve `(user_id, created_at DESC, id DESC)` indeksinin başladığı yeri doğrudan bulur. Plan:

```
Limit  (actual rows=20 ...)
  ->  Index Scan using idx_feed_user_created on feed
        (actual rows=20 ...)     <-- yalnızca 20 satır okundu
```

500. sayfa da 1. sayfa da aynı maliyette. Trade-off: keyset ile "doğrudan 500. sayfaya atla" yapamazsınız (rastgele sayfa erişimi kaybolur), ama sonsuz kaydırma / "daha fazla yükle" akışları için ideal ve ölçeklenebilir.

Uyarı: `WHERE created_at < :last_ts OR (created_at = :last_ts AND id < :last_id)` yazımı mantıken doğrudur ama bazı planlayıcılar bu `OR`'lu biçimi tek bir temiz index range'e çeviremez; satır-değer biçimi (`(a,b) < (x,y)`) hem daha okunur hem de planlayıcı için daha dost.

### İkinci vaka: kısmi (partial) indeks ile "soft delete" temizliği

Aynı sistemde satırlar `deleted_at` ile mantıksal siliniyor ve neredeyse tüm sorgular `WHERE deleted_at IS NULL` içeriyor. Tam indeks, silinmiş satırları da taşır ve boşuna büyür. Kısmi indeks bu yükü keser:

```sql
CREATE INDEX idx_feed_active_user_created
    ON feed (user_id, created_at DESC, id DESC)
    WHERE deleted_at IS NULL;
```

İndeks yalnızca canlı satırları içerir: daha küçük, daha hızlı, daha az yazma maliyeti. Kritik detay — planlayıcının bu indeksi kullanabilmesi için sorgudaki koşulun indeksin `WHERE` predikatını **kapsaması** gerekir; sorgu `deleted_at IS NULL` demezse indeks devreye girmez. (Partial index: PostgreSQL, SQLite'ta var; MySQL 8'de doğrudan yok, "filtered index" SQL Server'da var.)

### Üçüncü vaka: anahtar sırasının yazma throughput'una etkisi

Aynı sistemde `feed` tablosuna saniyede binlerce olay yazılıyor. Birincil anahtar seçimi burada okumadan çok **yazma throughput'unu** belirler. İki tasarımı karşılaştıralım:

```sql
-- Tasarım A: rastgele UUID PK
CREATE TABLE feed_a (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  -- v4, rastgele
    ...
);

-- Tasarım B: zaman-sıralı anahtar
CREATE TABLE feed_b (
    id BIGSERIAL PRIMARY KEY,   -- monotonik artan
    ...
);
```

Tasarım A'da her yeni `id` indeksin **rastgele bir noktasına** düşer. Bu, çalışma seti (working set) büyük olduğunda her ekleme için farklı bir yaprak sayfayı buffer cache'e getirmeyi, kirletmeyi ve geri yazmayı gerektirir; sürekli dağınık page split ve fragmantasyon yaratır. Tasarım B'de yeni `id`'ler hep en sağdaki yaprağa eklenir — o yaprak sıcak kalır, cache dostudur, split'ler öngörülebilir ve seyrektir.

Trade-off: Tasarım B'nin bir dezavantajı, çok yüksek eşzamanlılıkta o en-sağ sayfanın bir **hotspot** olması — tüm INSERT'ler aynı sayfa için kilitlenmeye çalışır (özellikle InnoDB'de kümeli indeks üzerinde). Modern çözüm ikisinin ortası: **UUIDv7 / ULID** gibi zaman-öneki taşıyan tanımlayıcılar. Bunlar kabaca sıralıdır (fragmantasyon düşük) ama sonuna gömülü rastgelelik sayesinde tek bir sayfaya tam yığılmayı da yumuşatır. Karar kuralı: dağıtık üretim gereksinimi UUID zorunlu kılıyorsa v4 yerine v7/ULID seç; aksi halde `bigserial` en ucuz yazma yolunu verir.

---

## 3. Karşılaştırma / karar: hangi indeks yapısı ne zaman?

İndeksleme "B-tree ekle geç" değildir. Erişim biçimi yapıyı belirler.

### B-tree vs. Hash

- **B-tree**: eşitlik + aralık + sıralama + prefix. Varsayılan tercih, çünkü aralık ve `ORDER BY`'ı da kapsar.
- **Hash**: yalnızca eşitlik (`=`). Aralık, sıralama, prefix desteklemez. Çok yüksek kardinaliteli, sadece eşitlikle sorgulanan sütunlarda teoride daha kompakt ve O(1) olabilir. Pratikte PostgreSQL'de B-tree çoğu iş yükünde yeterince iyi olduğundan hash indeks nadiren kazandırır; ayrıca aralık ihtiyacı doğduğunda tamamen işe yaramaz hâle gelir. **Karar: emin değilsen B-tree.** Hash'i yalnızca ölçülmüş, saf eşitlik, aralık ihtiyacı asla olmayacak bir kolonda düşün.

### Tek geniş composite vs. birden çok tekil indeks

- Sorgular sütunları **birlikte** filtreliyorsa: composite kazanır. `(a, b)` tek geçişte daraltır.
- Sütunlar **ayrı ayrı, farklı sorgularda** filtreleniyorsa: iki tekil indeks daha esnektir. Motor gerektiğinde bitmap index scan ile ikisini birleştirebilir (intersection), ama bu tek composite'ten yavaştır.
- Trade-off: her composite yalnızca kendi **leftmost prefix**'lerini karşılar. `(a,b,c)` indeksi `(a)` ve `(a,b)` sorgularını da karşıladığı için ayrıca `(a)` indeksi tutmak çoğu zaman israftır — hem yer hem yazma maliyeti. Ama `(b)` tek başına sorgulanıyorsa ayrı indeks şart.

### Covering (INCLUDE) vs. dar indeks

- **Covering**: sıcak, çok satır dönen, tabloya git-gel maliyeti yüksek sorgular için index-only scan sağlar; en pahalı işi (random heap I/O) eler.
- **Dar indeks**: daha küçük, daha ucuz yazma, cache dostu.
- Trade-off: her `INCLUDE` sütunu indeksi büyütür ve her yazmada güncellenir. "Her ihtimale karşı tüm sütunları koy" yaklaşımı indeksi tablonun kopyasına çevirir. **Karar: sadece kanıtlanmış sıcak sorguları cover et, mümkün olan en dar sütun setiyle.**

### Ne zaman HİÇ indekslememek doğru karardır

- Düşük kardinaliteli sütun (`status` 3 değerli) tek başına: motor zaten tablonun büyük kısmını okuyacaksa full scan daha ucuzdur. (Kısmi indeks — "sadece `status='pending'` olanlar" — bu durumda mantıklı olabilir çünkü nadir değeri hedefler.)
- Ağır yazma / düşük okuma tablosu (event log, audit trail): her indeks write amplification'ı artırır; okunmuyorsa yükümlülük.
- Küçük tablo (birkaç yüz satır): full scan zaten bir-iki sayfa; indeksin bakım maliyeti faydasını aşar, planlayıcı çoğu zaman indeksi yok sayar.

### B-tree vs. özel yapılar: GIN, GiST, BRIN

Erişim düz skalar eşitlik/aralık değilse B-tree yetmez:

- **GIN** (Generalized Inverted Index): bir sütunun içinde **çok değer** olan durumlar — dizi üyeliği (`tags @> ARRAY['sql']`), JSONB anahtar araması, full-text arama (`to_tsvector`), trigram ile `LIKE '%orta%'`. B-tree bunların hiçbirini yapamaz çünkü "satır → tek sıralı anahtar" modeline sığmazlar. Trade-off: GIN okuma için güçlüdür ama yazması pahalıdır ve `fastupdate` kuyruğu nedeniyle bakım ister.
- **GiST**: aralık tipleri, coğrafi/geometrik "yakınlık" ve overlap sorguları (PostGIS'in temeli). "Şu dikdörtgenle kesişen kayıtlar" B-tree ile ifade edilemez.
- **BRIN** (Block Range Index): fiziksel olarak sıralı, çok büyük tablolarda (zaman serisi log'ları) her blok aralığı için min/max özetini tutar. B-tree'nin yüzde biri kadar yer kaplar. Trade-off: yalnızca fiziksel sıralama ile kolon değeri **korelasyonu yüksekse** işe yarar; veri karışıksa neredeyse hiç daraltmaz.

Karar: sorgunun şekli yapıyı seçer. "Bir satırda birden çok değer aranıyor" → GIN; "geometrik/aralık overlap" → GiST; "devasa, doğal sıralı, aralık taraması" → BRIN; geri kalan her şey → B-tree.

### OLTP vs. OLAP eğilimi

- **OLTP** (çok yazma, noktasal okuma): indeksi cömert kullanmaktan kaçın; her indeksin write maliyetini ciddiye al; dar ve az sayıda.
- **OLAP / raporlama** (ağır okuma, seyrek toplu yükleme): daha cömert indeksleme, covering indeksler ve — motora göre — B-tree yerine columnar / BRIN gibi yapılar mantıklı olabilir. PostgreSQL'de zaman-sıralı, çok büyük tablolarda **BRIN** indeks, B-tree'nin küçük bir kesri kadar yer kaplayıp geniş aralık taramalarını hızlandırabilir (fiziksel sıralama korelasyonu yüksekse).

---

## 4. Hata-modu kataloğu

Sahada en sık görülen indeks hataları. Her biri gerçek bir yavaşlamanın veya bozuk davranışın kökü.

1. **Sütuna fonksiyon/dönüşüm uygulamak (non-sargable).** `WHERE YEAR(created_at)=2024`, `WHERE UPPER(email)=...`, `WHERE created_at::date = ...` düz indeksi kapatır çünkü indeks ham değere göre sıralıdır. Çözüm: koşulu aralığa çevir ya da ifade indeksi (`CREATE INDEX ... ON t (lower(email))`) tanımla.

2. **Örtük tip dönüşümü (implicit conversion).** İndeksli kolon `VARCHAR`, sorguda `WHERE phone = 5551234` gibi sayı verilirse motor kolonu dönüştürüp indeksi atlayabilir. Özellikle MySQL'de sessizce full scan'e döner. Parametre tipini kolon tipiyle eşleştir.

3. **Composite'te yanlış sütun sırası / leftmost prefix ihlali.** `(a,b)` indeksi varken sorgunun yalnızca `b`'yi filtrelemesi indeksi kullanılamaz kılar; `b` değerleri indeks boyunca dağılmıştır. Sıra, sorgu kalıbına göre seçilmelidir.

4. **Eşitlik-aralık sırasını ters koymak.** `(created_at, customer_id)` indeksinde `created_at`'i aralıkla, `customer_id`'yi eşitlikle sorgulamak: aralık en solda olunca sonraki kolon etkin daraltma yapamaz. Doğrusu eşitlik kolonu önce: `(customer_id, created_at)`.

5. **Baştan joker LIKE.** `LIKE '%metin'` B-tree kullanamaz çünkü prefix yok. Sadece `LIKE 'metin%'` sargable. Ortadan/sondan arama için full-text index, trigram (pg_trgm GIN) veya ayrı bir arama motoru gerekir.

6. **`OR` ile indeksi öldürmek.** `WHERE a = 1 OR b = 2` çoğu zaman tek indeksle karşılanamaz ve full scan'e döner. Çözüm: her koşula ayrı indeks + planlayıcının bitmap `OR` birleştirmesi, ya da `UNION` ile iki ayrı indekslenebilir sorguya bölmek.

7. **`NULL` ve `IS NULL` varsayımları.** Bazı motorlarda/indeks tiplerinde `NULL`'lar indekslenmez veya farklı ele alınır; `WHERE col IS NULL` beklenenden yavaş olabilir. Kısmi indeks (`WHERE col IS NULL`) hedefli çözüm sunar.

8. **Fazla ve çakışan indeks.** `(a)`, `(a,b)`, `(a,b,c)`'yi birlikte tutmak: `(a,b,c)` ilk ikisinin işini zaten görür. Fazlalık = boşa yazma maliyeti + disk + cache kirliliği. Redundant indeksleri periyodik ayıkla.

9. **Rastgele UUID'yi birincil/kümeli anahtar yapmak.** Rastgele `uuid_v4` indeksin her yerine ekleme yapar → sürekli page split, fragmantasyon, kötü cache lokalitesi, yüksek write amplification. Zaman-sıralı varyant (UUIDv7 / ULID) veya `bigserial` bu sorunu hafifletir.

10. **Hiç kullanılmayan (ölü) indeksleri taşımak.** Sorgular değişir, indeks kalır; okunmuyor ama her yazmada güncelleniyor. `pg_stat_user_indexes.idx_scan = 0` gibi istatistiklerle avla ve kaldır (önce staging'de doğrula).

11. **İstatistikleri güncel tutmamak.** Planlayıcı, kardinalite tahminini istatistiklere dayanır. Toplu yükleme sonrası `ANALYZE` çalıştırılmazsa motor satır sayısını yanlış tahmin edip indeksi olması gerekirken kullanmayabilir (ya da tersi). Otomatik `ANALYZE`/`auto-vacuum` eşiklerini büyük tablolarda gözden geçir.

12. **Migration'da eş zamanlı olmayan indeks oluşturma.** Üretimde `CREATE INDEX` (PostgreSQL) tabloya yazma kilidi alır ve trafiği durdurabilir. Çözüm: `CREATE INDEX CONCURRENTLY` (daha yavaş ama kilitsiz). MySQL'de online DDL, SQL Server'da `ONLINE = ON` karşılığıdır. Bunu atlamak canlı kesintiye yol açar.

---

## Kapanış

İndeks, bedava hız değil; okumayı yazma ve disk karşılığında satın alan bilinçli bir takastır. Bu derin dalışın özü tek cümlede: **indeksin var olması yetmez — sorgunun onu kullanabilir biçimde yazılmış olması, doğru sütun sırasıyla kurulmuş olması ve planla doğrulanmış olması gerekir.** Her indeks kararını `EXPLAIN ANALYZE` üzerinde ölç; `Rows Removed by Filter`, `Heap Fetches` ve gerçekte okunan satır sayısı sana gerçeği söyler, varsayımın değil. Ekle, ölç, gereksizse kaldır.
