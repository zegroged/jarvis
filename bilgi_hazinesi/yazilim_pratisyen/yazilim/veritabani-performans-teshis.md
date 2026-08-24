# Veritabanı Performans Teşhisi: Yavaş Sorgu Avı

## 1. Problem ve bağlam

Bir sabah destek kanalına "sistem yavaş" mesajı düşer. Bu cümle neredeyse hiçbir şey anlatmaz ama arkasında çoğu zaman tek bir gerçek yatar: veritabanı bir yerlerde nefes alamıyor. Uygulama katmanı log'ları temiz görünür, CPU grafikleri masum durur, ama kullanıcı checkout sayfasında 8 saniye bekler. Veritabanı performans teşhisi tam da bu boşluğu kapatan iştir: "sistem yavaş" gibi belirsiz bir şikâyeti, "şu sorgu, şu tabloda, şu yüzden, şu koşulda yavaşlıyor" gibi ölçülebilir bir cümleye çevirmek.

Bu iş ne zaman devreye girer? Üç tipik anda. Birincisi, bir olay (incident) yaşandığında — p99 gecikmesi tavan yapmış, timeout'lar artmış, kuyruk şişmiştir. İkincisi, kapasite planlaması yaparken — "bu tablo 100 milyona çıkarsa bu sorgu ayakta kalır mı" sorusu. Üçüncüsü ise en sinsi olan: yavaş yavaş kötüleşen, kimsenin tek bir deploy'a bağlayamadığı, "eskiden hızlıydı" dedikleri sürüklenme (drift). Bu üçünün teşhis refleksi farklıdır ve deneyimli mühendisi acemiden ayıran ilk şey, hangi durumda olduğunu daha ilk dakikada anlamasıdır.

Şunu baştan söyleyeyim: performans teşhisi bir arama problemidir, tahmin problemi değil. Acemi tahmin eder ("indeks ekleyelim bakalım"), usta daraltır. Aşağıda anlatacağım her şey aslında arama uzayını sistematik olarak küçültmenin yollarıdır.

## 2. Metodoloji ve karar ağacı — asıl değer burada

### 2.1 Önce belirtiyi konumlandır: yavaş olan ne?

İlk hata, hipotezle başlamaktır. Doğru başlangıç ölçümle başlamaktır. "Sistem yavaş" dendiğinde sorduğum ilk üç soru şudur:

- **Her şey mi yavaş, yoksa belirli bir uç nokta mı?** Her şey yavaşsa sorun büyük ihtimalle veritabanının kendisindedir (bağlantı havuzu tükenmiş, lock birikmiş, disk doymuş, replica gecikmiş). Tek bir sayfa yavaşsa sorun neredeyse kesin o sayfanın attığı belirli bir sorgudadır.
- **Ne zaman başladı ve neyle çakışıyor?** Bir deploy'la mı, bir kampanyayla mı (trafik), bir veri büyümesiyle mi, bir cron job'la mı çakışıyor? Zaman ekseninde çakışma, nedenselliğin en ucuz ipucudur.
- **Ortalama mı yavaş, yoksa kuyruk mu?** Ortalama (mean) yükseldiyse sistemik bir yavaşlama var. Ortalama iyi ama p99 berbatsa, bu genelde kilitlenme (lock contention), soğuk cache, ya da ara sıra devreye giren kötü bir plan demektir. Kuyruk problemleri ortalamada kaybolur; bu yüzden ortalamaya asla güvenmem.

Bu üç sorunun cevabı, teşhisin geri kalanını yönlendiren karar ağacının köküdür.

### 2.2 "Yavaş olan sorguyu" bulmak: içeriden dışarıya

Belirti bir uç noktaya inince, ikinci adım suçlu sorguyu isimlendirmektir. Burada acemi doğrudan uygulama koduna dalar ve sorguları gözle okumaya çalışır. Usta ise veritabanının kendi muhasebesine sorar. Her ciddi veritabanının, hangi sorgunun ne kadar toplam zaman harcadığını tutan bir mekanizması vardır (PostgreSQL'de `pg_stat_statements`, MySQL'de performance schema ve slow query log, SQL Server'da Query Store gibi).

Kritik yargı şudur: **tek bir çağrıda en yavaş sorgu değil, toplamda en çok zaman yiyen sorgu önemlidir.** 2 saniye süren ama günde 3 kez çalışan bir raporlama sorgusu, 40 milisaniye süren ama saniyede 500 kez çalışan bir sorgudan çok daha az önemlidir. `toplam_süre = ortalama_süre × çağrı_sayısı` — teşhiste altın metrik budur. Acemi en büyük tek süreyi kovalar; usta toplam süreyi sıralar ve listenin tepesindeki üç sorguya odaklanır. Sistem yükünün %80'i genelde 2-3 sorgudan gelir.

### 2.3 Suçlu sorgu elde; şimdi neden yavaş?

Sorguyu isimlendirdikten sonra tek bir aracı çıkarırım: **sorgu planı (execution plan / EXPLAIN).** Bu, teşhisin kalbidir. Ama burada en yaygın ve en pahalı hata yatıyor, o yüzden altını kalınca çiziyorum:

**Tahmini planı (EXPLAIN) değil, gerçekleşen planı (EXPLAIN ANALYZE / gerçek çalıştırma istatistikleri) okuyun.** Salt `EXPLAIN` size optimizer'ın *tahminlerini* verir. Gerçek felaket, tahminle gerçeğin ayrıştığı yerdedir: planlayıcı "bu adımdan 10 satır dönecek" der, gerçekte 4 milyon satır döner. İşte performans hatalarının belki de yarısı bu tahmin sapmasından (cardinality misestimation) doğar. Planı okurken gözüm ilk olarak şuraya gider: *tahmini satır sayısı ile gerçek satır sayısı hangi düğümde birbirinden kopuyor?* O düğüm, kötü kararın verildiği yerdir.

Plan okurken zihnimdeki karar ağacı kabaca şöyle işler:

- **Seq Scan / Full Table Scan görüyorum, üstelik büyük tabloda ve seçici bir WHERE ile mi?** → İndeks eksik ya da mevcut indeks kullanılamıyor. Ama dur — küçük tabloda full scan *doğru* karardır; optimizer haklıdır, indeks eklemek zarar verir. Yargı: tablo boyutuna ve seçiciliğe bak.
- **İndeks var ama kullanılmıyor mu?** → Genelde üç sebepten: (a) WHERE koşulunda sütunun üzerine fonksiyon uygulanmış (`WHERE lower(email) = ...` ama indeks düz `email` üzerinde), (b) veri tipi uyuşmazlığı ve gizli tip dönüşümü, (c) sorgu o kadar çok satır döndürüyor ki optimizer indeksi kullanmanın full scan'den pahalı olacağına karar vermiş (ve genelde haklıdır).
- **Nested Loop join'de iç tarafta milyonlarca satır mı dönüyor?** → Küçük olduğu tahmin edilen bir set aslında dev; join sırası ya da yöntemi yanlış seçilmiş. Kök neden neredeyse her zaman güncel olmayan ya da yetersiz istatistiklerdir.
- **Sort ya da Hash düğümü diske mi taşıyor (spill)?** → Çalışma belleği yetersiz; ya sorgu gereğinden fazla veriyi sıralıyor (erken filtreleme yapılmalı) ya da bellek ayarı düşük.

### 2.4 Nedensellik zinciri: belirtiden köke

Deneyimli teşhisin özü, belirtiyi kök nedene bağlayan zinciri kurmaktır. Yavaş bir sorgunun ardındaki gerçek kökler genelde şunlardır ve ben bu sırayla kontrol ederim, çünkü ucuzdan pahalıya doğru gider:

1. **Bayat istatistikler.** En ucuz ve en sık atlanan. Tablo hızla büyüdü ya da toplu bir veri yüklendi, ama optimizer'ın istatistikleri eski. Optimizer eski dünyaya göre plan yapıyor. `ANALYZE` çalıştırmak dakikalar içinde çözer. Herhangi bir indeks eklemeden önce buna bakarım.
2. **Eksik ya da yanlış indeks.** Klasik. Ama "indeks ekle" bir refleks değil, bir karar olmalı (aşağıda ayrıntı var).
3. **Yazılmış kötü sorgu.** Gereksiz join, `SELECT *`, filtrelenmeden çekilip uygulamada elenen veri, N+1 deseni.
4. **Kilitlenme / eşzamanlılık.** Sorgu tek başına hızlı ama üretimde başka bir işlemin tuttuğu kilidi bekliyor. Bu, izole test ortamında asla görünmez ve acemiyi çıldırtır.
5. **Kaynak doygunluğu.** Disk IOPS tavan yapmış, bağlantı havuzu tükenmiş, bellek yetersiz. Bu durumda tek bir sorguyu optimize etmek yara bandıdır.

Yargı kuralı: **soru sormadan indeks ekleme.** Her indeks bir takas: okumayı hızlandırır ama her INSERT/UPDATE/DELETE'i yavaşlatır, disk yer, bakım maliyeti getirir. Yazma ağırlıklı bir tabloya düşünmeden atılan indeks, bir sorunu çözerken üç tane doğurur.

## 3. Gerçek senaryo üzerinden yürüyüş

Somut olalım. Elimizde bir e-ticaret sistemi var. Kullanıcı "siparişlerim" sayfasında sürekli yavaşlık yaşıyor. `orders` tablosu 60 milyon satıra ulaşmış. Uygulama şu sorguyu atıyor:

```sql
SELECT *
FROM orders
WHERE customer_id = 48213
  AND status = 'shipped'
ORDER BY created_at DESC
LIMIT 20;
```

### Adım 1: Ölçüm

`pg_stat_statements`'a bakıyorum. Bu sorgu ortalama 1.9 saniye sürüyor ve günde on binlerce kez çağrılıyor — toplam süre listesinin tepesinde. Suçlu isimlendi.

### Adım 2: Gerçekleşen planı oku

```
EXPLAIN (ANALYZE, BUFFERS)
SELECT ... (yukarıdaki sorgu)
```

Çıktı kabaca şöyle bir şey gösteriyor:

```
Limit  (actual time=1876.4..1876.5 rows=20)
  ->  Sort  (actual time=1876.4..1876.4 rows=20)
        Sort Key: created_at DESC
        Sort Method: top-N heapsort  Memory: 34kB
        ->  Seq Scan on orders
              (actual time=0.3..1810.2 rows=1128 loops=1)
              Filter: (customer_id = 48213 AND status = 'shipped')
              Rows Removed by Filter: 59998872
              Buffers: shared read=1240000
```

Bu çıktıda usta gözü şuraya kilitlenir: **`Seq Scan` var ve `Rows Removed by Filter: 59998872`.** Yani veritabanı 60 milyon satırı tek tek okuyup, işine yarayan 1128 tanesini bulmak için 59.998.872 tanesini çöpe atmış. `Buffers: shared read=1240000` de diskten kaç blok okuduğunu gösteriyor — dev bir rakam. Belirti ile kök neden arasındaki zincir netleşti: uygun bir indeks yok, tam tablo taraması yapılıyor.

### Adım 3: Doğru düzeltmeyi tasarla — ve burada acemiyle usta ayrışır

Acemi refleksi: "customer_id'ye indeks atalım." Kötü değil ama eksik. Sorguyu düşünelim: iki koşul (`customer_id`, `status`) *ve* bir sıralama (`created_at DESC`) *ve* bir limit var. Sadece `customer_id` indekslersek, veritabanı o müşterinin tüm siparişlerini bulur (diyelim 5000 tane), sonra bunların hepsini belleğe alıp `status`'e göre filtreler ve `created_at`'e göre sıralar. İyileşir ama optimal değil.

Doğru düzeltme, sorgunun *şeklini* karşılayan bir bileşik indekstir:

```sql
CREATE INDEX idx_orders_customer_status_created
ON orders (customer_id, status, created_at DESC);
```

Bu indeksin sütun sırası tesadüf değil, bir karardır. Kural: **önce eşitlik koşulları (customer_id, status), sonra sıralama/aralık sütunu (created_at).** Böylece veritabanı indekste doğrudan doğru müşteri + doğru statüye atlar, ve o noktadan itibaren kayıtlar zaten `created_at DESC` sırasında dizili olduğu için `LIMIT 20`'yi hiç sıralama yapmadan, ilk 20 kaydı okuyup bırakarak karşılar. Sort düğümü tamamen kaybolur.

### Adım 4: Doğrula

Aynı `EXPLAIN ANALYZE`'ı tekrar çalıştırınca artık:

```
Limit  (actual time=0.05..0.14 rows=20)
  ->  Index Scan using idx_orders_customer_status_created on orders
        (actual time=0.04..0.11 rows=20)
        Index Cond: (customer_id = 48213 AND status = 'shipped')
        Buffers: shared hit=24
```

`Seq Scan` gitti, `Sort` gitti, `Rows Removed by Filter` gitti. 1.9 saniye 0.14 milisaniyeye indi, disk okuması 1.240.000 bloktan 24 bloğa düştü. Bu, teşhisin kapandığı andır: belirti ölçüldü, kök neden planla kanıtlandı, düzeltme yine planla doğrulandı.

Ama iş burada bitmez. Usta son bir soru sorar: **bu indeksin bedeli ne?** `orders` yazma ağırlıklı bir tablo; her yeni sipariş artık bu indeksi de güncelleyecek. Üç sütunlu indeks makul, yazma maliyeti kabul edilebilir. Ama eğer `SELECT *` yerine sadece birkaç sütun gerekiyorsa, bu sütunları indekse `INCLUDE` ederek "covering index" (kapsayan indeks) yapabilir ve tabloya hiç dönmeden sorguyu bitirebilirdik. Bu takası — indeks genişliği vs. tabloya dönme maliyeti — veriye ve okuma/yazma oranına bakarak veririm.

### İkinci senaryo: gizli tip dönüşümü

Daha sinsi bir örnek. `customer_id` sütunu veritabanında `bigint`, ama uygulama onu string olarak gönderiyor (ORM bazen bunu yapar). Sorgu şuna dönüşüyor:

```sql
WHERE customer_id = '48213'
```

Kullanıcı "ama indeksim var!" der ve haklıdır — indeks orada durur. Ama plan yine `Seq Scan` gösterir. Neden? Çünkü veritabanı `customer_id`'yi (bigint) string ile karşılaştırmak için her satırda bir *dönüşüm* uygular, ve indeks ham `bigint` değeri üzerine kuruludur; dönüştürülmüş değer üzerine değil. İndeks kullanılamaz hale gelir. Bu tür hatalar planı okumadan asla anlaşılmaz; kod gözle bakınca kusursuz görünür. Ders: **WHERE koşulundaki sütunun üzerinde herhangi bir işlem (fonksiyon, tip dönüşümü, aritmetik) varsa, o sütunun indeksi büyük ihtimalle devre dışıdır.**

## 4. Acemi vs pro: tuzaklar

**"İndeks ekleyince hızlandı, iş bitti" yanılgısı.** Acemi bir indeks ekler, sorgu hızlanır, sevinir. Usta sorar: bu indeks başka hangi sorguları etkiledi? Yazma performansı ne oldu? Belki aynı işi zaten yapan başka bir indeks vardı ve şimdi çakışan iki indeks var. Üretimde indeks sayısı sinsice şişer; her biri yazmayı yavaşlatır ve hiç kimse hangisinin gerçekten kullanıldığını bilmez. Kullanılmayan indeksleri düzenli avlamak, eklemek kadar önemli bir disiplindir.

**Test verisinde hızlı, üretimde yavaş.** En klasik tuzak. Geliştirici 10 bin satırlık test veritabanında sorguyu çalıştırır, 5 milisaniye, "sorun yok" der. Üretimde 60 milyon satır vardır ve optimizer tamamen farklı bir plan seçer — çünkü plan seçimi veri hacmine ve dağılımına bağlıdır. **Plan, veri boyutuyla değişir.** Bu yüzden performans testini üretim ölçeğine yakın bir veri hacminde yapmayan ekip, sürekli aynı sürprizle karşılaşır. Sadece satır sayısı da değil; verinin *dağılımı* da önemli. Test verisinde her müşterinin 5 siparişi vardır (düzgün dağılım), üretimde bir toptancı müşterinin 2 milyon siparişi vardır (çarpık dağılım) ve o müşteri için plan çöker.

**Ortalamaya güvenmek.** Acemi ortalama süreye bakar ve rahatlar. Ama kullanıcı deneyimini p95/p99 belirler. Ortalama 40ms, p99 4 saniye olan bir sorgu, kullanıcıların %1'ine — ki bu genelde en aktif, en çok veriye sahip kullanıcılardır — berbat bir deneyim yaşatır. Kuyruğa (tail latency) bakmayan teşhis eksiktir.

**N+1 sorgu deseni.** Uygulama 100 siparişi listeler, sonra her sipariş için ayrı bir sorguyla müşteri adını çeker. Tek tek her sorgu 2 milisaniye, "hızlı" görünür. Ama 101 gidiş-dönüş, ağ gecikmesiyle çarpınca 300 milisaniye eder ve `pg_stat_statements`'ta bile parçalı göründüğü için gizlenir. ORM'lerin varsayılan tembel yükleme (lazy loading) davranışı bu deseni sessizce üretir. Teşhis: veritabanı log'unda aynı şablonun ardışık yüzlerce kez tekrarlandığını görürsün. Çözüm join ya da toplu yükleme (eager loading), indeks değil.

**`EXPLAIN`'i `EXPLAIN ANALYZE` sanmak.** Salt `EXPLAIN` sorguyu çalıştırmaz, sadece tahmini planı gösterir. Gerçek satır sayılarını ve gerçek süreleri göremezsin, dolayısıyla tahmin sapmasını yakalayamazsın — ki en değerli ipucu odur. (Not: `EXPLAIN ANALYZE` sorguyu *gerçekten çalıştırır*; UPDATE/DELETE üzerinde çalıştırırken transaction içinde yapıp geri almak gerekir, yoksa veriyi değiştirirsin. Bu, üretimde acemiyi vuran bir ayrıntıdır.)

**Kilitlenmeyi izole ortamda aramak.** Sorgu tek başına çalıştırınca uçar, üretimde tıkanır. Acemi sorguyu suçlar, saatlerce optimize eder, hiçbir şey değişmez. Çünkü sorgu yavaş değil — *bekliyor.* Başka bir uzun transaction'ın tuttuğu kilidi bekliyor. Bunu ancak üretimde, eşzamanlı yük altında, aktif kilitleri ve bekleyen sorguları gösteren sistem görünümlerine bakarak yakalarsın. Belirti "sorgu yavaş", kök neden "başka bir yerde uzun süren, commit etmeyen bir transaction."

**Bağlantı havuzu tükenmesi performans sorunu sanmak.** Uygulama yavaşlar, ama veritabanının kendisi boştadır. Sebep: bağlantı havuzu (connection pool) dolmuştur, uygulama yeni sorgu atmak için boş bağlantı bekler. Veritabanı grafikleri masumdur çünkü sorun veritabanında değil, ona ulaşan kapıdadır. Bu yüzden teşhiste "bekleme nerede oluşuyor" sorusu "hangi sorgu yavaş" sorusundan önce gelir bazen.

## 5. Araçlar ve saha notları

**Sorgu istatistikleri toplayıcıları.** Her veritabanının bir tane vardır ve ilk açtığın kapı burasıdır: PostgreSQL'de `pg_stat_statements` uzantısı, MySQL'de performance_schema ve slow query log, SQL Server'da Query Store, Oracle'da AWR raporları. Bunlar "hangi sorgu toplamda en çok yük yaratıyor" sorusunu cevaplar. Üretimde `pg_stat_statements`'ı açık tutmak neredeyse bedavadır ve bir olay anında elindeki en değerli veridir. Kapalıysa, olay anında açman gerekir ve tarihsel veriyi kaybedersin — bu yüzden önceden aç.

**EXPLAIN / execution plan görselleştiricileri.** Ham `EXPLAIN ANALYZE` çıktısı büyük sorgularda okunması zor, iç içe bir metindir. Planı ağaç olarak görselleştiren ve en pahalı düğümü kırmızıyla işaretleyen görselleştirme araçları (PostgreSQL için explain.dalibo.com / pev tarzı görselleştiriciler yaygındır) teşhisi hızlandırır. Ama araca bağımlı olma; planı ham haliyle okuyabilmek temel beceridir. Okurken içeriden dışarıya, en derin düğümden köke doğru okunur; zaman aşağıdan yukarıya birikir.

**`EXPLAIN (ANALYZE, BUFFERS)` — BUFFERS'ı unutma.** `BUFFERS` seçeneği kaç bloğun cache'ten (`hit`), kaçının diskten (`read`) geldiğini gösterir. `read` yüksekse sorgu diske gidiyor demektir — asıl maliyet oradadır. Aynı sorgu ikinci çalıştırmada cache ısındığı için hızlanabilir; bu seni yanıltmasın, `read` sayısı gerçek maliyeti söyler.

**Observability / APM.** Uygulama tarafında dağıtık izleme (distributed tracing) araçları, bir isteğin zamanının ne kadarını veritabanında geçirdiğini gösterir. "Sayfa 8 saniye" derken 7 saniyesi tek bir sorguda mı, yoksa 400 küçük sorguda (N+1) mı geçiyor — bunu ancak trace söyler. Veritabanı metriklerini (aktif bağlantı sayısı, kilit bekleme süresi, replica gecikmesi, cache isabet oranı, disk IOPS) sürekli izleyen dashboard'lar, olay anında "ne zaman ve neyle başladı" sorusunu saniyeler içinde cevaplar.

**Aktif sorgu ve kilit görünümleri.** Canlı bir olay sırasında en pratik hamlelerden biri, o an çalışan sorguları ve kimin kimi kilitlediğini gösteren sistem görünümlerine bakmaktır (PostgreSQL'de `pg_stat_activity` ve `pg_locks`). "Şu an 40 saniyedir çalışan şu sorgu, şu tabloyu kilitlemiş, arkasında 30 sorgu bekliyor" — bu tabloyu görmek, saatlerce spekülasyondan iyidir. Uzun süren, `idle in transaction` durumunda takılı kalmış bağlantılar en sık bulunan katildir.

**İstatistik tazeleme ve otomatik bakım.** `ANALYZE` (istatistik güncelleme) ve autovacuum/otomatik bakım süreçlerinin sağlığını izle. Büyük toplu veri yüklemelerinden sonra istatistiklerin bayatlaması, planların bir gecede çökmesinin en yaygın "gizemli" sebebidir. Otomatik bakım yükü kaldıramıyorsa geride kalır ve tablolar şişer (bloat); şişmiş tablo, aynı sorguyu giderek yavaşlatan sinsi bir sürüklenme yaratır.

**Yük testi araçları.** Bir düzeltmeyi üretime çıkarmadan önce, üretim ölçeğine yakın veriyle ve eşzamanlı yük altında test et. `pgbench` gibi araçlar ya da uygulama seviyesinde yük üreticiler, "tek sorgu hızlı ama 200 eşzamanlı istekte ne olur" sorusunu cevaplar. Çünkü performansın çoğu sorunu eşzamanlılıkta ortaya çıkar, tekil çalıştırmada değil.

### Kapanış: teşhis disiplini

Saha notu olarak biriktirdiğim birkaç kural şunlar. Birincisi: **her zaman ölçerek başla, tahminle değil.** Hipotez ucuzdur, herkes bir tanesine sahiptir; veri pahalıdır ve haklı olanı gösterir. İkincisi: **her düzeltmeyi düzeltmeden önceki ve sonraki planla kanıtla.** "Sanırım düzeldi" bir mühendislik cümlesi değildir. Üçüncüsü: **bir düzeltmenin bedelini sor.** İndeks yazmayı yavaşlatır, denormalizasyon tutarlılığı zorlaştırır, cache bayatlama riski getirir — bedava öğle yemeği yoktur, sadece takaslar vardır. Dördüncüsü: **üretim, test ortamı değildir.** Ölçek, veri dağılımı, eşzamanlılık ve cache durumu planı değiştirir; teşhisi mümkün olduğunca üretime yakın koşullarda yap.

En sonda, deneyimin öğrettiği şu: yavaş sorgu teşhisi teknik bir iş gibi görünür ama aslında bir düşünme disiplinidir. Belirtiden köke giden zinciri sabırla kurabilen, en ucuz kontrolü en pahalıdan önce yapan, ve "hızlandı" ile "neden hızlandığını kanıtladım" arasındaki farkı bilen mühendis, bu işi çözer. Gerisi araç kullanmayı öğrenmektir.
