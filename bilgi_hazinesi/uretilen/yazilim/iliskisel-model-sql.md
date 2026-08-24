# İlişkisel Model ve SQL

## Giriş: Neden İlişkisel Model?

İlişkisel model (relational model), 1970 yılında Edgar F. Codd'un ortaya koyduğu, verinin nasıl saklanacağını ve sorgulanacağını **matematiksel küme teorisi** üzerine oturtan bir soyutlamadır. Codd'un getirdiği asıl devrim teknik değil, felsefiydi: veriye erişimin, verinin fiziksel olarak diskte nasıl du_rduğundan tamamen bağımsız hale gelmesi. Buna **data independence** (veri bağımsızlığı) denir.

Codd'dan önce hâkim olan hiyerarşik ve network veritabanlarında, bir kaydı bulmak için programcının pointer'ları elle takip etmesi, verinin fiziksel yolunu bilmesi gerekirdi. Uygulama kodu, depolama düzenine sıkı sıkıya bağlıydı; disk düzeni değişince kod da kırılırdı. Codd'un modeli bu bağı kopardı: siz **ne** istediğinizi bildirirsiniz (declarative), sistem **nasıl** getireceğine kendi karar verir. SQL'in bildirimsel (declarative) doğası tam olarak buradan gelir; `SELECT` yazarken diski nasıl tarayacağınızı söylemezsiniz, sadece istediğiniz sonuç kümesini tarif edersiniz.

Bu makale, ilişkisel modelin temel yapı taşlarını (tablo, ilişki, foreign key), verileri birleştiren JOIN mekanizmasını ve tüm bunların altında yatan küme mantığını, "neden böyle" sorusuna cevap verecek derinlikte ele alıyor.

## Tablo ve İlişki (Relation) Kavramı

### Tanım ve terminolojinin kökü

İlişkisel modelde temel yapı, günlük dilde "tablo" dediğimiz şeydir; ama teorideki adı **relation** (bağıntı/ilişki)'dır. Buradaki terminoloji karışıklığı çok yaygın bir kafa karışıklığına yol açar, o yüzden önce doğru zihinsel modeli kuralım:

- **Relation (relation / tablo):** Belirli bir yapıya sahip satırlar kümesi. Örneğin `Musteriler` tablosu.
- **Tuple (tuple / satır / row):** Tablonun bir satırı; tek bir varlığı (entity) temsil eder. Örneğin tek bir müşteri.
- **Attribute (attribute / sütun / column):** Bir özellik; her tuple'ın o özelliğe dair bir değeri vardır. Örneğin `ad`, `email`.
- **Domain (domain / etki alanı):** Bir attribute'un alabileceği geçerli değerler kümesi. Örneğin `yas` attribute'unun domain'i "0 ile 130 arası tam sayılar" olabilir.
- **Degree (derece):** Tablodaki sütun sayısı.
- **Cardinality (kardinalite):** Tablodaki satır sayısı.

Buradaki en kritik nokta şudur: matematiksel olarak bir relation, satırların **kümesidir (set)**. Kümenin iki temel özelliği vardır ve bunlar veritabanı davranışını doğrudan açıklar:

1. **Kümede sıra yoktur.** Bu yüzden bir tabloda satırların "doğal bir sırası" yoktur. `ORDER BY` yazmadan `SELECT` yaptığınızda satırların gelme sırası garanti değildir. Kişiler "bir kez böyle geldi, hep böyle gelir" sanır; bu tehlikeli bir yanılgıdır. Sıra garantisi ancak `ORDER BY` ile gelir.
2. **Kümede tekrar eden eleman yoktur.** Bu yüzden saf ilişkisel teoride iki özdeş satır olamaz. Pratikte SQL bu kuralı gevşetir (bir tablo teknik olarak duplicate satır barındırabilir, `SELECT` de default olarak duplicate döndürür — bu yüzden SQL tabloları katı anlamda "relation" değil "multiset/bag"tir), ama iyi tasarımda her satırı benzersiz kılan bir **primary key** ile bu teorik saflığı geri getiririz.

### "İlişki" nerede? İki farklı anlam

Türkçede "ilişki" kelimesi iki bambaşka şeyi karşıladığı için çok kafa karıştırır:

- **Relation = tablonun kendisi.** (Codd'un matematiksel terimi.)
- **Relationship = tablolar arasındaki bağ.** (İki tablonun foreign key ile birbirine bağlanması.)

Modelin adı ("relational model") aslında birincisinden, yani her tablonun bir matematiksel bağıntı olmasından gelir. Ama pratik veri tasarımında bizi asıl ilgilendiren, ikincisi: tablolar arası **relationship**'lerdir. İşte foreign key'ler tam bu noktada devreye girer.

## Foreign Key (Yabancı Anahtar): Verinin Tutkalı

### Primary key'den foreign key'e

Her tablonun, her satırını benzersiz olarak tanımlayan bir **primary key**'i olmalıdır (örneğin `Musteriler.musteri_id`). Primary key iki şey garanti eder: **benzersizlik** (UNIQUE) ve **boş olmama** (NOT NULL). Neden ikisi de zorunlu? Çünkü bir satırı güvenilir biçimde işaret edebilmemiz için, o işaretin (a) tek bir satıra gitmesi ve (b) hiç var olmayan bir "hiçlik"e gitmemesi gerekir.

**Foreign key (FK)**, bir tablodaki bir sütunun (veya sütun grubunun), başka bir tablonun primary key'ine işaret etmesidir. Örnek:

```sql
CREATE TABLE Musteriler (
    musteri_id  INT PRIMARY KEY,
    ad          VARCHAR(100) NOT NULL,
    email       VARCHAR(255) UNIQUE
);

CREATE TABLE Siparisler (
    siparis_id   INT PRIMARY KEY,
    musteri_id   INT NOT NULL,
    tutar        DECIMAL(10,2) NOT NULL,
    tarih        DATE NOT NULL,
    FOREIGN KEY (musteri_id) REFERENCES Musteriler(musteri_id)
);
```

Burada `Siparisler.musteri_id`, `Musteriler.musteri_id`'ye işaret eden bir foreign key'dir. Bu satır, "her siparişin ait olduğu müşteri, mutlaka `Musteriler` tablosunda var olan bir müşteri olmalıdır" kuralını **veritabanı seviyesinde** dayatır.

### Kök neden: Referential Integrity (Referans bütünlüğü)

Foreign key'in var olma sebebi tek kelimeyle **referential integrity**'dir: veritabanının hiçbir zaman "yetim" (orphan) kayıt barındırmaması. Yani var olmayan bir müşteriye ait bir sipariş olmamalıdır. FK olmadan da uygulama kodunda "önce müşteri var mı diye kontrol et, sonra siparişi ekle" yazabilirsiniz. Peki neden FK'yi veritabanına koyalım?

Cevap **eşzamanlılık ve çokluk** ile ilgilidir. Uygulama seviyesindeki kontrol iki nedenle yetersizdir:

1. **Race condition:** İki eşzamanlı işlem düşünün. Biri müşteriyi silerken, diğeri aynı anda o müşteriye sipariş ekliyor. Uygulama kodundaki "müşteri var mı" kontrolü ile ekleme arasındaki minik zaman aralığında müşteri silinebilir. Sonuç: yetim sipariş. FK constraint'i ise veritabanı motorunun transaction ve locking mekanizmalarıyla bütünleşik çalıştığı için bu boşluğu kapatır.
2. **Tek doğruluk kaynağı:** Aynı veritabanına birden fazla uygulama, script, admin paneli ve elle yazılan SQL erişir. Kuralı sadece bir uygulamanın koduna gömerseniz, diğer erişim yolları bu kuralı bilmez ve ihlal edebilir. Kural veritabanının içinde olduğunda, veriye **hangi kapıdan girilirse girilsin** geçerlidir. Bütünlük kurallarının doğru yeri, veriye en yakın katmandır.

### Referential action'lar: silme ve güncellemede ne olur?

FK tanımlarken en çok atlanan ama en kritik karar, "işaret edilen satır silinir veya güncellenirse ne olsun?" sorusudur. SQL bunu `ON DELETE` ve `ON UPDATE` cümlecikleriyle çözer:

- **`RESTRICT` / `NO ACTION` (varsayılan davranış genelde budur):** Müşteriyi silmeye çalışırsanız, ona bağlı sipariş varken silme **reddedilir**. En güvenli, en muhafazakâr seçenek. "Önce siparişleri hallet, sonra müşteriyi sil" der.
- **`CASCADE`:** Müşteri silinince, ona bağlı tüm siparişler de **otomatik silinir**. Güçlü ama tehlikeli. Yanlış yerde kullanılırsa tek bir silme, zincirleme biçimde beklenmedik bir tablo yığınını süpürebilir. `ON DELETE CASCADE`'i "sahiplik" (ownership) ilişkilerinde kullanın: alt kayıt, üst kayıt olmadan hiçbir anlam ifade etmiyorsa (örneğin bir siparişin satır kalemleri, sipariş silinince gitmelidir).
- **`SET NULL`:** Müşteri silinince siparişin `musteri_id`'si `NULL` yapılır. Bunu kullanabilmek için FK sütununun `NULL` kabul etmesi gerekir; `NOT NULL` ise bu seçenek çelişkilidir. Bağın "opsiyonel" olduğu durumlar için uygundur.

Doğru action seçimi, iş kuralınızın verideki yansımasıdır. Bu, teknik bir tercih değil, **anlamsal (semantic)** bir karardır.

### İlişki türleri (relationship cardinality)

Foreign key'ler üç temel ilişki türünü modellemenin aracıdır:

- **Bire-çok (one-to-many):** En yaygın. Bir müşterinin çok siparişi olur; bir siparişin tek müşterisi. FK, "çok" tarafına konur (`Siparisler.musteri_id`). Neden çok tarafına? Çünkü her sipariş tam olarak bir müşteriye ait — tek bir değer tutması yeterli. Tersine, bir müşterinin siparişlerini tek bir sütunda tutmaya kalksanız, kaç sipariş olacağını bilemez, kümeyi bir hücreye sıkıştırmaya çalışır ve normalizasyonu bozardınız.
- **Bire-bir (one-to-one):** Daha nadir. Genellikle bir tabloyu ikiye bölme (örneğin sık kullanılan alanlar bir tabloda, nadir/hacimli alanlar başka tabloda) veya opsiyonel bilgi ayırma amacıyla. FK, taraflardan birine konur ve UNIQUE kısıtıyla desteklenir.
- **Çoka-çok (many-to-many):** Bir öğrencinin çok dersi, bir dersin çok öğrencisi olur. Bunu doğrudan FK ile modelleyemezsiniz; araya bir **junction table** (bağlantı/kavşak tablosu, ara tablo) koyarsınız. Bu ara tablo, iki tarafın da primary key'lerine birer FK ile işaret eder ve genellikle bu ikisinin birleşimi composite primary key olur:

```sql
CREATE TABLE Ogrenci_Ders (
    ogrenci_id  INT NOT NULL,
    ders_id     INT NOT NULL,
    kayit_tarihi DATE,
    PRIMARY KEY (ogrenci_id, ders_id),
    FOREIGN KEY (ogrenci_id) REFERENCES Ogrenciler(ogrenci_id),
    FOREIGN KEY (ders_id)    REFERENCES Dersler(ders_id)
);
```

Çoka-çok ilişkinin neden mutlaka ara tablo gerektirdiği, ilişkisel modelin en öğretici derslerinden biridir: tek bir hücreye birden fazla değer koyamazsınız (bu **first normal form** — 1NF — ihlalidir), dolayısıyla çokluğu ancak satırlar halinde açarak temsil edebilirsiniz.

## JOIN: Tabloları Yeniden Birleştirmek

### Neden JOIN'e ihtiyaç var?

İlişkisel tasarımın özü **normalizasyon**dur: veriyi tekrardan arındırmak için bilgiyi mantıksal parçalara bölüp ayrı tablolara koyarız. Müşteri bilgisini her siparişte tekrar tekrar yazmak yerine bir kez `Musteriler`'de tutarız. Bu, güncelleme anomalilerini (aynı bilginin bir yerde değişip başka yerde eski kalması) önler ve tutarlılığı garanti eder.

Ama bölmenin bir bedeli vardır: bir rapor için hem sipariş hem müşteri bilgisi lazım olduğunda, bu parçaları **tekrar birleştirmemiz** gerekir. İşte **JOIN** budur — normalizasyonla ayırdığımızı, sorgu anında geçici olarak yeniden birleştiren işlem. JOIN olmasaydı normalizasyon işe yaramaz olurdu; ikisi bir madalyonun iki yüzüdür.

### JOIN'in matematiksel kökü: Cartesian product

Her JOIN'in altında yatan temel işlem **Cartesian product** (kartezyen çarpım / cross join)'tir. İki tablonun kartezyen çarpımı, birinci tablonun her satırını, ikinci tablonun her satırıyla eşleştirir. `A` tablosunun 100, `B`'nin 50 satırı varsa, `A × B` **5000** satır üretir. Bu genellikle anlamsız, dev bir sonuçtur.

JOIN'i anlamanın en berrak yolu şudur: **JOIN, bir kartezyen çarpımın ardından bir filtreleme (koşul) uygulanmasıdır.**

```sql
-- Aşağıdaki iki sorgu mantıksal olarak eşdeğerdir:

SELECT *
FROM Siparisler s
JOIN Musteriler m ON s.musteri_id = m.musteri_id;

SELECT *
FROM Siparisler s, Musteriler m   -- kartezyen çarpım
WHERE s.musteri_id = m.musteri_id; -- sonra filtrele
```

Yani JOIN, "önce tüm olası satır kombinasyonlarını üret, sonra sadece bağdaşanları (join koşulunu sağlayanları) tut" demektir. Bu zihinsel model, JOIN sonuçlarını doğru öngörmenizi sağlar. (Gerçekte veritabanı optimizer'ı bunu asla kaba kuvvetle çarpıp filtreleyerek yapmaz — hash join, merge join, nested loop gibi verimli algoritmalar kullanır — ama **sonucun anlamı** tam olarak budur.)

### JOIN türleri ve her birinin mantığı

**INNER JOIN** — Yalnızca her iki tarafta da eşleşme bulunan satırları döndürür. En çok kullanılan tür. Müşterisi olmayan sipariş veya siparişi olmayan müşteri sonuçta yer almaz.

```sql
SELECT m.ad, s.siparis_id, s.tutar
FROM Musteriler m
INNER JOIN Siparisler s ON m.musteri_id = s.musteri_id;
```

**LEFT (OUTER) JOIN** — Sol tablonun **tüm** satırlarını korur; sağ tarafta eşleşme yoksa, sağ tablonun sütunları `NULL` gelir. Kullanım amacı çok önemlidir: "eksik olanı bulmak". Örneğin **hiç siparişi olmayan müşterileri** bulmak:

```sql
SELECT m.ad
FROM Musteriler m
LEFT JOIN Siparisler s ON m.musteri_id = s.musteri_id
WHERE s.siparis_id IS NULL;
```

Buradaki mantık zarif: LEFT JOIN önce tüm müşterileri getirir; siparişi olmayanların sipariş sütunları `NULL` olur; sonra `WHERE s.siparis_id IS NULL` ile tam da o eşleşmeyenleri süzeriz. Bu deseni ("anti-join") çok öğrenin, çok işe yarar.

**RIGHT (OUTER) JOIN** — LEFT'in aynadaki yansıması; sağ tabloyu korur. Pratikte nadir kullanılır çünkü tabloların yerini değiştirip LEFT JOIN yazmak hemen her zaman daha okunaklıdır.

**FULL (OUTER) JOIN** — Her iki tablonun da tüm satırlarını korur; eşleşmeyen taraflar `NULL` olur. İki kümenin simetrik farkını da içeren birleşimini görmek istediğinizde kullanılır.

**CROSS JOIN** — Doğrudan kartezyen çarpım, koşul yok. Bilinçli kullanıldığı yerler vardır (örneğin her ürünü her bedenle eşleştirip bir kombinasyon tablosu üretmek), ama çoğu zaman `ON` koşulunu unutmanın kazara sonucudur.

### Küme operatörleri: JOIN'in kardeşi ama farkı

JOIN'i, satırları **yan yana** (sütun ekleyerek) birleştiren bir işlem olarak düşünün. Buna karşılık **küme operatörleri** satırları **alt alta** (aynı sütun yapısıyla) birleştirir:

- **`UNION`** — İki sorgunun sonuçlarını birleştirir ve **duplicate'leri eler**. Tam da bir matematiksel kümenin "tekrarsız" özelliğini uygular. Duplicate elemek bir sıralama/karşılaştırma maliyeti getirir.
- **`UNION ALL`** — Birleştirir ama **duplicate'leri elemez**. Bu yüzden çok daha hızlıdır. "Zaten çakışma olmayacağını biliyorum" diyorsanız `UNION ALL` tercih edin; gereksiz `UNION` kullanmak yaygın bir performans hatasıdır.
- **`INTERSECT`** — Her iki sorguda da ortak olan satırları döndürür (kesişim).
- **`EXCEPT`** (bazı sistemlerde `MINUS`) — Birinci sorguda olup ikincide olmayan satırlar (fark).

Bu operatörlerin çalışması için iki sorgunun **aynı sayıda ve uyumlu tipte sütun** döndürmesi gerekir; çünkü kümenin elemanları (satırlar) aynı "şekilde" olmalıdır ki karşılaştırılabilsinler. Bu kısıt keyfi değil, küme mantığının doğrudan sonucudur.

## Küme Mantığı: Modelin Görünmez İskeleti

İlişkisel modelin gücü, tüm bu işlemlerin **küme cebri (relational algebra)** üzerine oturmasından gelir. SQL'in `SELECT`'i aslında birkaç temel küme operasyonunun bileşimidir:

- **Selection (σ):** Satırları koşula göre süzme → SQL'de `WHERE`.
- **Projection (π):** Belirli sütunları seçme → SQL'de `SELECT`'teki sütun listesi.
- **Join (⋈):** Tabloları birleştirme → SQL'de `JOIN`.
- **Union, Intersection, Difference:** Küme operatörleri → `UNION`, `INTERSECT`, `EXCEPT`.

Bunun **neden önemli** olduğu şuradadır: bu operasyonlar **kapalıdır (closure)**. Yani her operasyonun girdisi de çıktısı da bir relation'dır. Bir sorgunun sonucu yine bir tablodur; onu başka bir sorguya girdi yapabilirsiniz. Alt sorguların (subquery), view'ların ve CTE'lerin (Common Table Expression) mümkün olmasının kökeni budur. Legolar gibi: her parçanın çıktısı, başka bir parçanın girdisi olabildiği için karmaşık sorguları basit parçalardan inşa edebilirsiniz.

### NULL: Üç değerli mantık (three-valued logic)

Küme mantığından bahsedince en sık tökezlenen konuyu atlamamak gerekir: **NULL**. NULL, "değer yok / bilinmiyor" anlamına gelir ve klasik iki değerli mantığı (true/false) **üç değerliye** (true / false / **unknown**) çevirir. Bu, sezgiye aykırı sonuçlar doğurur:

- `NULL = NULL` sonucu **true değil, unknown**'dur. "İki bilinmeyen birbirine eşit mi?" sorusunun cevabı bilinemez.
- Bu yüzden NULL kontrolü `= NULL` ile **yapılamaz**; `IS NULL` / `IS NOT NULL` kullanmak **zorunludur**. Yeni başlayanların en klasik sessiz hatası budur: `WHERE email = NULL` yazar, hiç satır dönmez, sebebini anlayamaz.
- `WHERE` cümlesi yalnızca **true** olan satırları geçirir; unknown olanları eler. Bu yüzden `WHERE tutar > 100` sorgusu, `tutar` NULL olan satırları **dışarıda bırakır** — çünkü `NULL > 100` unknown'dur.
- `NOT IN (alt sorgu)` içinde NULL varsa, tüm sonuç beklenmedik biçimde boş dönebilir. Bu, deneyimli geliştiricileri bile yakalayan sinsi bir tuzaktır; `NOT EXISTS` genelde daha güvenli davranır.

NULL'ı "sıfır" veya "boş string" ile karıştırmak da ayrı bir hatadır. Sıfır bir değerdir; NULL değerin **yokluğudur**. `0` ile `NULL` toplamı `NULL`'dır (bilinmeyen bir şeye bir şey eklemek yine bilinmeyendir).

## Yaygın Hatalar ve Tuzaklar

**1. JOIN koşulunu unutup kazara kartezyen çarpım üretmek.** Çok tablolu eski usul virgüllü FROM sözdiziminde (`FROM a, b, c`) bir `WHERE` bağını atlamak, milyonlarca satırlık patlamaya yol açar. Modern `JOIN ... ON` sözdizimi bu riski azaltır çünkü `ON` koşulunu unutmak göze batar.

**2. `SELECT *` ile JOIN yapıp sütun çakışmasında kaybolmak.** İki tabloda da `id` sütunu varsa, sonuçta hangisinin hangisi olduğu belirsizleşir. Üretim kodunda sütunları açıkça ve tablo takma adıyla (`m.ad`, `s.tutar`) yazın. `SELECT *` ayrıca gereksiz veri taşır ve tablo yapısı değişince sessizce bozulur.

**3. Filtreyi yanlış yere koyup LEFT JOIN'i INNER JOIN'e çevirmek.** LEFT JOIN yaptıktan sonra sağ tablonun bir sütununu `WHERE`'de filtrelerseniz (örneğin `WHERE s.tutar > 100`), NULL satırlar elenir ve LEFT JOIN'in tüm amacı boşa gider. Sağ tabloya ait ek koşulları `ON` cümlesine koymalısınız, `WHERE`'e değil. Bu ayrım, outer join'lerin en ince ve en çok hata yapılan noktasıdır.

**4. NULL'ı `=` ile karşılaştırmak.** Yukarıda anlatıldı; `IS NULL` kullanın.

**5. Foreign key index'ini unutmak.** Çoğu veritabanı primary key'e otomatik index koyar ama **FK sütununa otomatik index koymaz** (bu davranış sisteme göre değişir). FK üzerinden sık JOIN yapıyorsanız ve o sütun index'siz ise, her JOIN full table scan'e dönüşür ve performans çöker. FK sütunlarını index'lemek neredeyse her zaman doğru bir reflekstir.

**6. Gereksiz `DISTINCT` veya `UNION` ile duplicate ezmeye çalışmak.** Sorgu duplicate üretiyorsa, çoğu zaman sebep hatalı bir JOIN'dir (örneğin bire-çok ilişkide çokluğun sonucu şişirmesi). `DISTINCT` yapıştırmak semptomu gizler ama kök nedeni çözmez ve maliyet ekler. Önce "neden duplicate çıkıyor?" diye sorun.

## En İyi Pratikler

**Bütünlük kurallarını veritabanına gömün.** Primary key, foreign key, `NOT NULL`, `UNIQUE`, `CHECK` — bunlar sadece belge değil, dayatılan garantilerdir. Uygulama kodu hata yapsa bile veritabanı son savunma hattıdır. "Uygulama zaten kontrol ediyor" güvenilmez bir varsayımdır çünkü tek erişim yolu uygulama değildir.

**Her tabloya anlamlı bir primary key koyun.** Doğal bir anahtar (natural key, örneğin TC kimlik no) yoksa veya değişkense, yapay bir **surrogate key** (otomatik artan `id` veya UUID) kullanın. Değişebilecek bir alanı primary key yapmak, ona bağlı tüm FK'leri kırma riski taşır — çünkü primary key değişince cascade zinciri tetiklenir.

**JOIN'lerde her zaman tablo takma adı (alias) kullanın.** Sorguyu hem kısaltır hem de sütunların hangi tablodan geldiğini netleştirir. Çok tablolu sorgularda okunabilirlik doğrudan doğruluk demektir.

**Referential action'ları bilinçli seçin.** `CASCADE`'i sadece gerçek sahiplik ilişkilerinde kullanın; gerisinde `RESTRICT` daha güvenlidir. Yanlış bir `CASCADE`, tek bir DELETE'in veritabanının yarısını süpürmesine yol açabilir.

**Normalize edin, ama körü körüne değil.** 3NF (üçüncü normal form) çoğu OLTP (transactional) sistem için doğru varsayılan hedeftir; veri tekrarını ve anomalileri önler. Ancak ağır okuma yapılan raporlama/analitik senaryolarda, çok fazla JOIN performansı düşürüyorsa **bilinçli denormalizasyon** meşrudur. Kural şudur: önce doğru (normalize) tasarla, sonra **ölçülmüş** bir performans ihtiyacı varsa denormalize et — tersini değil.

**NULL'ı bir tasarım kararı olarak ele alın.** Bir sütun neden NULL olabilmeli? "Değer henüz girilmedi" mi, "uygulanamaz" mı, yoksa "bilinmiyor" mu? Bu ayrımları netleştirin; gereksiz NULL'lardan kaçının çünkü her NULL, sorgu mantığınıza üç değerli mantığın karmaşıklığını sokar.

**Sorguyu değil, sonucu tarif edin.** SQL bildirimseldir; ne istediğinizi net söyleyin, "nasıl"ı optimizer'a bırakın. Ama `EXPLAIN` / `EXPLAIN ANALYZE` ile execution plan'ı okumayı öğrenin — optimizer'ın sizin JOIN'inizi nasıl gerçekleştirdiğini görmek, yavaş sorguları anlamanın tek yoludur.

## Kapanış

İlişkisel model, yarım asrı aşkın süredir hâkim olan bir tasarımdır ve bu tesadüf değildir. Gücü, verinin **kümeler ve bağıntılar** olarak modellenmesinin sağladığı matematiksel sağlamlıktan gelir: küme cebri sayesinde sorgular öngörülebilir, birleştirilebilir (composable) ve optimize edilebilirdir. Foreign key'ler bütünlüğü garanti eder, JOIN'ler normalizasyonla ayrılanı yeniden birleştirir, küme operatörleri de sonuçları küme mantığıyla harmanlar.

Bu üç kavramı — tablo/ilişki, foreign key ile referential integrity, ve JOIN ile küme mantığı — gerçekten anladığınızda, SQL sadece bir sözdizimi ezberi olmaktan çıkar; verinin doğasını ifade eden tutarlı bir dile dönüşür. "Neden böyle" sorusuna verilen her cevap, aslında Codd'un elli yıl önce kurduğu o zarif matematiksel temele geri gider.
