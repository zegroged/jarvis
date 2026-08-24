# Sorgu Optimizasyonu: EXPLAIN, Planlar, Tarama ve Join Stratejileri

## Giriş: Sorgu Optimizasyonu Nedir?

Bir veritabanına yazdığınız SQL, ne yapılmasını istediğinizi tarif eder ama nasıl yapılacağını söylemez. `SELECT ... WHERE ... JOIN ...` cümlesi bildirimseldir (declarative): sonucun ne olması gerektiğini belirtir, hangi tabloya önce erişileceğini, hangi index'in kullanılacağını, join'lerin hangi algoritmayla yapılacağını değil. İşte bu boşluğu dolduran bileşen **sorgu optimizatörüdür** (query optimizer).

Optimizatör, aynı sonucu üreten birçok farklı yürütme yolunu (execution path) değerlendirir ve tahmini en ucuz olanı seçer. Bu seçilen yola **yürütme planı** (execution plan / query plan) denir. Sorgu optimizasyonu, hem optimizatörün doğru planı seçmesini sağlamak hem de gerektiğinde bizim müdahale etmemizdir.

Bir sorgunun neden yavaş olduğunu anlamanın tek dürüst yolu, tahmin yürütmek değil, planı okumaktır. Bu yüzden konunun kalbinde `EXPLAIN` durur.

## Kök Neden: Optimizatör Neden Böyle Çalışır?

Modern ilişkisel veritabanlarının çoğu **maliyet tabanlı optimizatör** (cost-based optimizer, CBO) kullanır. Optimizatör her aday plan için bir "maliyet" sayısı hesaplar. Bu maliyet gerçek bir zaman birimi değildir; okunacak tahmini sayfa (page) sayısı, işlenecek satır sayısı, CPU işlemleri gibi faktörleri birleştiren soyut bir skordur. Amaç mutlak doğruluk değil, planları birbiriyle karşılaştırılabilir kılmaktır.

Bu maliyet hesabının temel girdisi **istatistiklerdir** (statistics). Veritabanı, her tablo ve sütun için şu tür bilgileri saklar:

- Tablodaki yaklaşık satır sayısı (cardinality).
- Bir sütundaki farklı (distinct) değer sayısı.
- Değerlerin dağılımını gösteren histogramlar (bazı değerler diğerlerinden çok daha sık geçebilir; bu "veri çarpıklığı" / data skew).
- NULL oranları.

Optimizatörün yaptığı en kritik iş **cardinality estimation** yani "bu filtre uygulandıktan sonra kaç satır kalır?" tahminidir. Çünkü sonraki bütün kararlar buna dayanır. Eğer optimizatör bir join'in 10 satır üreteceğini sanıyorsa nested loop seçer; 10 milyon satır üreteceğini bilseydi hash join seçerdi. Bu yüzden **plan kalitesi, istatistik kalitesine bağlıdır.** Kötü plan denen şeylerin çok büyük bir kısmı, aslında bayat (stale) veya yanlış istatistiklerin sonucudur.

Buradaki temel gerilim şudur: optimizatör, sorguyu gerçekten çalıştırmadan, sadece özet istatistiklere bakarak karar vermek zorundadır. İstatistikler gerçeği kabaca temsil eder. Gerçek dağılım karmaşık olduğunda (özellikle korelasyonlu sütunlar, örneğin `sehir = 'Istanbul' AND ulke = 'Turkiye'` gibi birbirine bağımlı koşullarda), tahmin sapabilir. Optimizasyonu anlamak, bu tahmin mekanizmasının nerede iyi nerede kör olduğunu anlamaktır.

## EXPLAIN: Planı Okumak

`EXPLAIN`, optimizatörün seçtiği planı bize gösteren komuttur. Kritik ayrım şudur:

- **`EXPLAIN`** (tek başına): Sorguyu çalıştırmaz, sadece tahmini planı ve tahmini maliyetleri gösterir. Ucuzdur ve güvenlidir.
- **`EXPLAIN ANALYZE`** (PostgreSQL terminolojisi; MySQL'de de benzer, Oracle'da `DBMS_XPLAN` ve gerçek çalıştırma istatistikleri farklı yollarla alınır): Sorguyu **gerçekten çalıştırır** ve tahmini değerlerin yanında gerçek satır sayılarını ve gerçek süreleri gösterir.

Bu ikisi arasındaki farkı vurgulamak önemlidir çünkü optimizasyonun en güçlü tekniği **tahmini satır sayısı ile gerçek satır sayısını karşılaştırmaktır.** Plan bir düğüm için "estimated rows: 50" diyorsa ama gerçekte "actual rows: 2.000.000" ise, optimizatör kör uçmuştur ve seçtiği plan büyük ihtimalle yanlıştır. Bu sapma, sorunun kök nedenine giden en değerli ipucudur.

### Plan Nasıl Okunur?

Yürütme planı bir ağaçtır (tree). En **içteki / en girintili** düğümler önce çalışır, sonuçlarını üstteki düğümlere besler. Yani plan yukarıdan aşağıya değil, yapraklardan köke doğru akar. Bir planı okurken şu düğüm tiplerini ararsınız:

- **Seq Scan / Full Table Scan**: Tablonun tamamı satır satır okunuyor.
- **Index Scan**: Bir index üzerinden gidilip, eşleşen satırların tablodaki asıl verisi (heap) getiriliyor.
- **Index Only Scan**: İhtiyaç duyulan tüm sütunlar index'in içinde olduğu için tabloya hiç dokunulmuyor. Çok verimlidir.
- **Bitmap Index Scan / Bitmap Heap Scan**: Orta seçicilikteki (selectivity) sorgular için, önce eşleşen satır konumları bir bitmap'te toplanır, sonra tablo sıralı bir şekilde okunur.
- **Nested Loop / Hash Join / Merge Join**: Join algoritmaları (aşağıda ayrıntılı).
- **Sort, Aggregate, Hash, Materialize**: Ara işlem düğümleri.

Her düğümde şu sayılara bakılır: tahmini maliyet aralığı (başlangıç maliyeti .. toplam maliyet), tahmini satır sayısı, satır genişliği ve `ANALYZE` ile birlikte gerçek süre ve gerçek satır sayısı ile bir düğümün kaç kez tekrar çalıştığı (loops).

## Full Scan (Sequential Scan) mı, Index Scan mı?

Yeni başlayanların en yaygın yanılgısı şudur: "Full scan her zaman kötü, index her zaman iyi." Bu yanlıştır ve nedeni öğretici olduğu için üzerinde durmak gerekir.

### Neden Full Scan Bazen Daha Hızlıdır?

Disk (ve büyük ölçüde SSD dahil), **ardışık okumada** (sequential read) rastgele okumadan çok daha hızlıdır. Full table scan, tabloyu diskteki fiziksel sırasıyla, blok blok, ardışık olarak okur. Index scan ise index'te eşleşmeleri bulur, sonra her eşleşme için tabloda o satırın olduğu yere **rastgele** atlar (random I/O). Bu atlamaların her biri, ardışık bir okumadan pahalıdır.

Şimdi kritik hesap: eğer sorgunuz tablonun büyük bir yüzdesini (kaba bir eşik olarak, sistem ve donanıma göre değişmekle birlikte tablonun onda birinden fazlasını) döndürecekse, o kadar çok rastgele atlama yaparsınız ki, tablonun tamamını ardışık okumak toplamda daha ucuz olur. Optimizatör tam olarak bu hesabı yapar: **seçicilik** (selectivity), yani filtrenin satırların ne kadar küçük bir kısmını geçireceği, kararı belirler.

- Yüksek seçicilik (az satır dönüyor, örneğin bir e-posta ile tek kullanıcı): index kazanır.
- Düşük seçicilik (çok satır dönüyor, örneğin `WHERE aktif = true` ve satırların %80'i aktifse): full scan kazanır.

Yani full scan'i planda görmek başlı başına bir sorun değildir. Sorun, **yüksek seçicilikli bir sorguda** full scan görmektir. İşte o zaman "index var mı, varsa neden kullanılmıyor?" sorusunu sorarsınız.

### Index Neden Kullanılmıyor Olabilir?

İndex'inizin olması, kullanılacağı anlamına gelmez. En yaygın nedenler:

**1. Sütunun bir fonksiyonla sarılması.** `WHERE YEAR(siparis_tarihi) = 2024` yazarsanız, index `siparis_tarihi` üzerinde tanımlı olsa bile kullanılamaz; çünkü index ham sütun değerini saklar, `YEAR(...)` sonucunu değil. Çözüm ya sorguyu aralık haline getirmek (`siparis_tarihi >= '2024-01-01' AND siparis_tarihi < '2025-01-01'`) ya da fonksiyon üzerine index (functional/expression index) tanımlamaktır.

**2. Implicit tip dönüşümü (implicit conversion).** Sütun sayısal, ama sorguda `WHERE hesap_no = '12345'` gibi string ile karşılaştırıyorsanız, veritabanı bir tarafı dönüştürmek zorunda kalır ve bu genellikle index'i devre dışı bırakır. Bu sinsi bir hatadır çünkü sorgu doğru sonuç verir, sadece yavaştır.

**3. Leading column kuralının ihlali.** `(musteri_id, tarih)` şeklinde bir composite (bileşik) index, `WHERE tarih = ...` sorgusunda tek başına verimli kullanılamaz. Çünkü index bir telefon rehberi gibi önce ilk sütuna göre sıralıdır. Soyisme (ilk sütun) göre sıralı rehberde, ismi (ikinci sütun) verilen birini aramak için yine tüm rehberi taramanız gerekir.

**4. Yanlış istatistikler.** Optimizatör index'in çok satır döndüreceğini sanıyorsa (istatistikler bayatsa) full scan'i tercih edebilir.

## Join Stratejileri

Bir join, iki tablodaki satırları eşleştirmektir. Optimizatörün seçtiği fiziksel algoritma, performansı belki de en çok belirleyen faktördür. Üç ana strateji vardır ve her birinin kendine göre parladığı bir senaryo vardır.

### Nested Loop Join

En basit algoritma: dış tablonun (outer) her satırı için, iç tabloda (inner) eşleşen satır aranır. Kaba biçimiyle iki iç içe döngüdür. Maliyeti yaklaşık olarak "dış satır sayısı × iç tabloda arama maliyeti" kadardır.

**Ne zaman parlar?** Dış taraf **çok az satır** içerdiğinde ve iç tarafta join sütununda bir **index** olduğunda. O zaman her dış satır için iç tabloda hızlı bir index lookup yapılır. Küçük-büyük join'lerin ve OLTP tipi noktasal sorguların doğal seçimidir.

**Ne zaman felaket olur?** Dış taraf büyük olduğunda. 1 milyon dış satır × her biri için iç tabloda arama = ölümcül. Optimizatör dış tarafın küçük olacağını tahmin edip nested loop seçmiş ama gerçekte dış taraf devasa çıkmışsa (yine cardinality estimation hatası), sorgu saatlerce sürebilir. Planda `EXPLAIN ANALYZE` ile nested loop'un `loops` sayısının milyonlara ulaştığını görmek klasik bir kötü-plan sinyalidir.

### Hash Join

İki fazlıdır. **Build fazında** küçük tablo taranır ve join sütunundan bellekte bir hash tablosu kurulur. **Probe fazında** büyük tablo taranır, her satırın join anahtarı hash'lenir ve build tarafındaki hash tablosunda eşleşme aranır. Hash lookup ortalama sabit zamanlı (O(1)) olduğu için bu çok verimlidir.

**Ne zaman parlar?** İki büyük tabloyu, eşitlik koşuluyla (`=`) join ederken. Analitik / OLAP sorgularının belkemiğidir. Index'e ihtiyaç duymaz, tam da bu yüzden index olmayan büyük join'lerde optimizatörün doğal tercihidir.

**Zayıf noktaları:** Yalnızca eşitlik join'lerinde çalışır (`<`, `>` gibi aralık join'lerinde kullanılamaz). Hash tablosu belleğe sığmalıdır; sığmazsa diske taşar (disk spill) ve performans düşer. Planda hash join'in bellek yerine geçici dosya kullandığını görmek, `work_mem` benzeri bellek ayarlarını gözden geçirme sinyalidir.

### Merge Join (Sort-Merge Join)

Her iki tablo da join sütununa göre **sıralı** hale getirilir, sonra iki sıralı liste tek geçişte, fermuar gibi birleştirilir. İki işaretçi sıralı listeler boyunca ilerler.

**Ne zaman parlar?** Girdiler zaten sıralıysa (örneğin join sütununda bir index sayesinde sıralı geliyorsa) sıralama maliyeti ortadan kalkar ve merge join çok verimli olur. Ayrıca aralık koşullu join'leri ve büyük veri kümelerini, hash tablosunu belleğe sığdırma zorunluluğu olmadan işleyebilir.

**Maliyeti:** Girdiler sıralı değilse, önce sıralama gerekir; sıralama pahalı bir işlemdir. Bu yüzden merge join genellikle "verinin zaten sıralı geldiği" durumlarda kazanır.

### Join Sırası (Join Order): Görünmez Ama En Kritik Karar

Üçten fazla tabloyu join ettiğinizde, optimizatörün asıl zor işi hangi algoritma değil, **tabloları hangi sırayla birleştireceğidir.** Çünkü ara sonuçların (intermediate result) boyutu her şeyi belirler. Önce en çok filtreleyen, yani en küçük ara sonucu üreten join'i yapmak, sonraki tüm adımların işleyeceği satır sayısını küçültür.

Buradaki kombinatorik patlama gerçektir: n tablo için olası sıralama sayısı faktöriyel gibi büyür. Bu yüzden optimizatörler tüm olasılıkları denemez; belirli bir tablo sayısının üzerinde (her sistemin bir eşiği vardır) sezgisel (heuristic) yöntemlere veya genetik algoritmalara geçerler. Çok fazla tabloyu tek sorguda join ettiğinizde, optimizatör optimal olmayan bir sıra seçmeye başlayabilir; bu, çok-tablolu dev sorguların neden bazen aniden yavaşladığının bir açıklamasıdır.

## Somut Örnek: Bir Planı Yorumlamak

Şöyle bir sorgu düşünelim:

```sql
SELECT m.ad, s.tutar
FROM musteriler m
JOIN siparisler s ON s.musteri_id = m.id
WHERE m.sehir = 'Ankara'
  AND s.tarih >= '2024-01-01';
```

Sağlıklı bir plan kabaca şöyle olabilir (PostgreSQL üslubuyla):

```
Nested Loop
  ->  Index Scan using musteriler_sehir_idx on musteriler m
        Index Cond: (sehir = 'Ankara')
        (estimated rows=120  actual rows=118)
  ->  Index Scan using siparisler_musteri_idx on siparisler s
        Index Cond: (musteri_id = m.id)
        Filter: (tarih >= '2024-01-01')
        (loops=118)
```

Bu planın mantığı şudur: `sehir = 'Ankara'` yüksek seçicilikli olduğu için önce bu filtre uygulanır ve yalnızca ~118 müşteri kalır. Az sayıda dış satır olduğu için nested loop mantıklıdır; her müşteri için `siparisler` tablosunda `musteri_id` index'i üzerinden hızlı arama yapılır. Tahmini (120) ve gerçek (118) satır sayılarının yakın olması, istatistiklerin sağlıklı olduğunu ve planın güvenilir olduğunu gösterir.

Şimdi patolojik hali: eğer `sehir = 'Ankara'` filtresi gerçekte 500.000 müşteri döndürüyorsa ama plan hâlâ 120 tahmin ediyorsa, nested loop 500.000 kez iç index araması yapar ve sorgu çöker. Burada gerçek/tahmin sapması bize istatistiklerin bayat olduğunu ya da `sehir` sütununda ciddi bir veri çarpıklığı olduğunu söyler. Doğru davranış: istatistikleri güncellemek ve optimizatörün hash join'e geçmesini sağlamaktır.

## Doğru Kullanım ve Tuzaklar

**İstatistikleri güncel tutun.** Toplu veri yükleme (bulk load), büyük silme/güncelleme veya bir tablonun aniden büyümesinden sonra istatistikler bayatlayabilir. Çoğu sistemde otomatik istatistik toplama vardır ama eşikleri kaçıran durumlar olur. Açıklanamayan bir yavaşlamada ilk şüpheli her zaman istatistiklerdir. İstatistikleri elle yenileme komutu (PostgreSQL'de `ANALYZE`, diğer sistemlerde eşdeğerleri) çoğu zaman tek başına sorunu çözer.

**Plan'ı gerçek veriyle test edin.** Boş ya da küçük bir test tablosunda çıkan plan, üretimdeki milyonlarca satırlı tablonunkiyle taban tabana zıt olabilir. Optimizatör satır sayısına göre karar verdiği için, temsili veri hacmi olmadan yapılan plan analizi yanıltıcıdır.

**Covering index kullanın.** Sorgunun ihtiyaç duyduğu tüm sütunları içeren bir index (bazı sistemlerde `INCLUDE` sütunlarıyla) tanımlanırsa, Index Only Scan mümkün olur ve tabloya hiç gidilmez. Sık çalışan kritik sorgular için bu büyük bir kazançtır.

**Parametre sniffing / plan cache tuzağı.** Bazı sistemler bir sorgu planını ilk çalıştırıldığındaki parametre değerine göre derler ve cache'ler (parameter sniffing). Eğer ilk parametre atipik bir değerse (örneğin çok az satır döndüren bir müşteri), sonraki tipik çağrılar bu kötü planı miras alır. Bu, "sorgu bazen hızlı bazen çok yavaş, ama SQL hep aynı" şikayetinin klasik nedenidir.

## Yaygın Hatalar

**`SELECT *` alışkanlığı.** Gereğinden fazla sütun çekmek, Index Only Scan imkânını yok eder (çünkü index'te olmayan sütunlar için tabloya gidilmesi gerekir), ağdan ve bellekten gereksiz veri taşır. Sadece ihtiyaç duyulan sütunları isteyin.

**Filtrelenebilir sütunu fonksiyona sarmak.** Yukarıda değinilen `YEAR(tarih)`, `UPPER(ad)`, `tutar + 0` gibi ifadeler index'i öldürür. Kural: WHERE koşulunda sütunu mümkün olduğunca **çıplak** bırakın, dönüşümü sabit tarafa yapın.

**Aşırı indeksleme.** Her yavaş sorgu için yeni bir index eklemek cazip gelir, ama her index yazma işlemlerini (INSERT/UPDATE/DELETE) yavaşlatır ve disk tüketir; çünkü her yazmada index'lerin de güncellenmesi gerekir. Kullanılmayan index'ler saf yüktür. İndex portföyünü periyodik olarak gözden geçirip kullanılmayanları temizlemek gerekir.

**OR koşullarının seçiciliği bozması.** `WHERE a = 1 OR b = 2` ifadesi çoğu zaman index kullanımını zorlaştırır; optimizatör iki farklı sütunu tek index'le karşılayamaz. Bazen sorguyu `UNION` ile iki ayrı, her biri kendi index'ini kullanabilen sorguya bölmek çok daha hızlıdır.

**Leading wildcard.** `WHERE ad LIKE '%mehmet%'` gibi başında joker olan aramalar B-tree index kullanamaz (çünkü sıralama baştan başlar). Bu tür aramalar için full-text search ya da trigram index gibi özel yapılara ihtiyaç vardır.

**Gereksiz `DISTINCT` ve `ORDER BY`.** Bunlar sıralama veya hash işlemi ekler; gerekmiyorsa çıkarın. Özellikle join'lerdeki kartezyen çoğalmayı (duplicate) `DISTINCT` ile bastırmak, altta yatan yanlış join koşulunu gizleyen kötü bir alışkanlıktır.

## En İyi Pratikler

**Önce ölç, sonra optimize et.** Hangi sorgunun gerçekten yavaş olduğunu, sistemin yavaş sorgu kaydından (slow query log) veya sorgu istatistiği toplayan eklentilerden öğrenin. Sezgiyle değil, veriyle çalışın. En çok toplam süre tüketen sorguları hedefleyin; nadiren çalışan bir sorguyu milisaniyelerle uğraşarak hızlandırmak yerine, saniyede binlerce kez çalışan bir sorguyu iyileştirmek katbekat değerlidir.

**`EXPLAIN ANALYZE`'ı reflekse dönüştürün.** Bir sorguyu optimize etmeye başlamadan önce mutlaka gerçek planı alın. Optimize edecek olduğunuz şeyin gerçekten darboğaz olduğundan emin olun. Tahmini ve gerçek satır sayılarındaki en büyük sapmayı bulun; sorunun kaynağı neredeyse her zaman orada gizlidir.

**İndex'i sorguya göre tasarlayın, sorguyu index'e göre yazın.** WHERE, JOIN ve ORDER BY'da sık geçen sütunları composite index'lerde doğru sırayla (en seçici ve eşitlik koşullu sütun başta) yerleştirin. Aynı zamanda sorguları, mevcut index'lerin leading column kuralına uyacak şekilde ifade edin.

**Büyük veri kümelerini erkenden daraltın.** Filtreleri mümkün olduğunca aşağıya, veri kaynağına yakın itin ki üst katmanlar daha az satırla çalışsın. Bu ilke "predicate pushdown" olarak bilinir ve modern optimizatörler bunu otomatik yapmaya çalışsa da, sorguyu bu ilkeye uygun yazmak işlerini kolaylaştırır.

**Optimizatöre güvenin, ama körlemesine değil.** Modern optimizatörler çok iyidir; çoğu durumda elle "hint" vermekten (planı zorla değiştirmekten) kaçınmak doğrudur, çünkü veriler değiştikçe zorladığınız plan bir gün optimal olmaktan çıkar. Ama optimizatörün kör olduğu yerleri (korelasyonlu sütunlar, aşırı çarpık veri, çok-tablolu devasa join'ler) tanıyın. Bu durumlarda çok sütunlu istatistikler oluşturmak, sorguyu yeniden yazmak veya son çare olarak yönlendirme vermek gerekebilir.

**Değişikliği ölçerek doğrulayın.** Bir index ekledikten veya sorguyu yeniden yazdıktan sonra, planı ve gerçek süreyi tekrar alın. "Daha hızlı olmalı" varsayımıyla yetinmeyin; optimizatör bazen beklediğiniz index'i kullanmayı reddeder ve bunu ancak yeni planı okuyarak fark edersiniz.

## Özet Zihinsel Model

Sorgu optimizasyonu, özünde optimizatörün karar verme sürecini anlamaktır. Optimizatör, istatistiklere dayanarak satır sayılarını tahmin eder; bu tahminlere göre tarama yöntemini (full scan mı, index mi) ve join stratejisini (nested loop, hash, merge) seçer. Bizim işimiz üç şeydir: (1) `EXPLAIN ANALYZE` ile planı okuyup tahmin-gerçek sapmasını yakalamak, (2) istatistikleri ve index tasarımını sağlıklı tutarak optimizatöre doğru karar verebileceği zemini hazırlamak, (3) sorguları optimizatörün yeteneklerinden faydalanacak biçimde yazmak. Full scan'in her zaman kötü, index'in her zaman iyi olmadığını; her join algoritmasının bir bağlamda doğru seçim olduğunu; ve nihayetinde her şeyin seçiciliğe ve doğru cardinality tahminine dayandığını içselleştirdiğinizde, çoğu performans sorununu artık tahminle değil, planı okuyarak çözebilirsiniz.
