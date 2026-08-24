# Veritabanı İndeksleme: B-tree, Composite, Covering ve Yazma Maliyeti

## Giriş ve Tanım

Bir veritabanı **indeksi**, tabloya ait satırları belirli sütun değerlerine göre hızlı bulmayı sağlayan yardımcı bir veri yapısıdır. İndeks, kitabın sonundaki dizin gibidir: kelimeyi tek tek sayfalarda aramak yerine, dizinden kelimeyi bulur ve doğrudan sayfa numarasına gidersiniz. İndeks olmadan bir sorgu, tabloyu baştan sona tarar; buna **full table scan** (tam tablo taraması) denir ve satır sayısı büyüdükçe maliyeti doğrusal olarak (O(n)) artar. İyi tasarlanmış bir indeks ile aynı arama, milyonlarca satırlık tabloda bile logaritmik (O(log n)) zamanda tamamlanabilir.

İndeksleme, çoğu zaman "sorgu yavaş, o zaman indeks ekleyelim" gibi mekanik bir refleks olarak öğrenilir. Oysa indeks, ücretsiz bir hızlanma değildir; **okuma hızını yazma hızından ve disk alanından satın alan** bir takas (trade-off) mekanizmasıdır. Bu makale, en yaygın kullanılan indeks türü olan **B-tree** yapısının nasıl çalıştığını, **composite** (bileşik) ve **covering** (kapsayan) indekslerin ne işe yaradığını ve indekslerin görünmeyen bedeli olan **yazma maliyetini** kök nedenleriyle birlikte açıklar.

## B-tree İndeksin Çalışma Mantığı

### Neden özel bir ağaç yapısına ihtiyaç var?

Bir sütunu sıralı tutup ikili arama (binary search) yapmak akla ilk gelen çözümdür. Ancak veritabanları veriyi RAM'de değil, disk üzerinde (blok/sayfa bazlı) tutar. Diskten okuma, RAM'e kıyasla kat kat pahalıdır; asıl darboğaz CPU karşılaştırmaları değil, **kaç disk sayfasına (I/O) erişildiğidir**. Sıralı bir dizide klasik binary search yapmak O(log n) karşılaştırma gerektirir ama her karşılaştırma potansiyel olarak ayrı bir disk erişimine yol açabilir. İşte B-tree'nin varlık nedeni budur: karşılaştırma sayısını değil, **disk erişim sayısını** en aza indirmek.

B-tree (ve pratikte çoğu veritabanının kullandığı varyantı olan **B+ tree**), her düğümü bir disk sayfasına denk gelecek şekilde tasarlanmış, **çok yollu (multi-way) dengeli** bir ağaçtır. İkili ağaçtaki gibi her düğümün 2 çocuğu değil, yüzlerce hatta binlerce çocuğu olabilir. Bu yüksek dallanma katsayısı (fan-out) sayesinde ağacın **yüksekliği çok düşük** kalır.

### Somut sezgi: neden bu kadar sığ?

Diyelim ki her düğüm 1000 anahtar tutabiliyor (gerçekçi bir değer). O zaman:

- 1 seviye: ~1.000 satır
- 2 seviye: ~1.000.000 satır
- 3 seviye: ~1.000.000.000 satır
- 4 seviye: ~1 trilyon satır

Yani bir milyar satırlık tabloda aradığınız değere ulaşmak için yalnızca **3-4 disk erişimi** yeterlidir. Kök düğüm ve genellikle üst seviyeler zaten RAM'de (buffer cache) tutulduğundan gerçekte diske inen erişim sayısı çoğu zaman 1-2'ye düşer. İndeksin gücü buradan gelir: satır sayısı 1000 kat artsa bile erişim maliyeti yalnızca 1 seviye artar.

### B+ tree'nin ayırt edici özelliği

Klasik B-tree ile B+ tree arasındaki en önemli fark şudur: **B+ tree'de gerçek veri (veya satır işaretçileri) yalnızca yaprak (leaf) düğümlerde tutulur**; iç (internal) düğümler sadece yol gösterici anahtarlardan oluşur. Ayrıca yaprak düğümler birbirine **çift yönlü bağlı liste** ile zincirlenir.

Bu tasarımın iki büyük pratik faydası vardır:

1. **Aralık sorguları (range scan) çok verimlidir.** `WHERE created_at BETWEEN ... AND ...` gibi bir sorguda, önce aralığın başlangıcı ağaçta bulunur, sonra yaprak zinciri boyunca ileri doğru okunarak ağaca tekrar inmeden sıralı veri toplanır.
2. **Sıralı okuma (ORDER BY) neredeyse bedavadır.** İndeks zaten sıralı olduğundan, indeksin taradığı sırayı `ORDER BY` için doğrudan kullanabilir; ayrı bir sort adımı gerekmez.

### İndeksin doğal olarak hızlandırdığı işlemler

B-tree indeks, sıralı yapısı gereği şu erişim biçimlerinde işe yarar:

- Eşitlik: `WHERE user_id = 42`
- Aralık: `WHERE age > 18`, `WHERE price BETWEEN 10 AND 50`
- Önek (prefix) araması: `WHERE name LIKE 'Ah%'` (sondan joker olan LIKE)
- Sıralama: `ORDER BY created_at`
- En küçük/en büyük: `MIN()`, `MAX()`

Buna karşılık B-tree, sıralamanın bozulduğu durumlarda **işe yaramaz**. Örneğin `WHERE name LIKE '%met'` (baştan joker) indeksi kullanamaz, çünkü sıralı yapıda "sonu met ile bitenler" bir arada değildir. Aynı şekilde `WHERE UPPER(email) = '...'` gibi sütuna fonksiyon uygulayan koşullar da düz indeksi devre dışı bırakır; çünkü indeks ham `email` değerine göre sıralıdır, `UPPER(email)` değerine göre değil. (Bu durumların çözümü, birçok veritabanında desteklenen **functional/expression index** yani ifade indeksidir.)

## Composite (Bileşik) İndeks

### Tanım ve temel kural

**Composite index**, birden fazla sütun üzerinde tanımlanan tek bir indekstir; örneğin `(last_name, first_name)`. Kritik nokta şudur: composite indeks, sütunları bağımsız değil, **sözlük sırasıyla (lexicographic)** birlikte sıralar. Yani önce `last_name`'e göre, eşitlik durumunda `first_name`'e göre sıralanmış tek bir birleşik anahtar oluşturulur. Telefon rehberi tam olarak böyle çalışır: önce soyada göre, aynı soyad içinde ada göre sıralıdır.

### En sol önek (leftmost prefix) kuralı ve kök neden

Composite indeksin en çok yanlış anlaşılan yönü, sütun sırasının kritik olmasıdır. `(a, b, c)` şeklinde tanımlı bir indeks yalnızca şu **önek** kombinasyonlarında kullanılabilir:

- `a`
- `a, b`
- `a, b, c`

Ancak `b` tek başına, `c` tek başına ya da `b, c` için bu indeks **kullanılamaz**.

Bunun kök nedeni doğrudan sıralamadadır. İndeks `a`'ya göre birinci derecede sıralı olduğundan, `a` üzerinden aramak veriyi ağaçta tek bir bitişik bölgeye daraltır. Ama sorgu yalnızca `b`'yi verirse, aynı `b` değerine sahip satırlar indeks boyunca **her yere dağılmış** durumdadır (çünkü önce `a`'ya göre gruplanmışlardır). Telefon rehberi analojisiyle: rehberde sadece "adı Mehmet olan herkesi" bulmak istediğinizde rehber işe yaramaz, çünkü Mehmet'ler tüm soyadlar arasına serpiştirilmiştir; baştan sona taramanız gerekir.

Önemli bir incelik: en soldaki sütun bir **aralık (range)** koşuluyla kullanıldığında, ondan sonraki sütunlar artık sıralı erişim için kullanılamaz. Örneğin `(a, b)` indeksinde `WHERE a > 10 AND b = 5` sorgusunda indeks `a > 10` kısmını daraltır, ama `b = 5` koşulu indeks içinde etkin bir daraltma yapamaz; çünkü `a`'nın birden çok farklı değeri arasında `b` artık sıralı değildir. Bu yüzden pratik bir kural vardır: **eşitlik koşullu sütunları indekste önce, aralık koşullu sütunu sona koyun.**

### Sütun sırasını nasıl seçmeli?

Doğru sıra, sorgu kalıplarına bağlıdır ama iki temel sezgi işe yarar:

1. **Eşitlik koşulları önce, aralık koşulları sonra.** Yukarıda açıklanan nedenle.
2. **Seçiciliği (selectivity) yüksek sütunu genellikle öne almak** faydalıdır. Seçicilik, bir sütunun ne kadar çeşitli değer içerdiğidir. `cinsiyet` gibi 2 değerli bir sütun düşük seçicidir (aramayı ancak yarıya indirir), `user_id` gibi neredeyse benzersiz bir sütun yüksek seçicidir (aramayı tek satıra indirir). Ancak bu kuralın önceliği, sorguların hangi kombinasyonları kullandığından sonra gelir; hiçbir sorgunun tek başına kullanmadığı seçici bir sütunu en sola koymak fayda sağlamaz.

### İki ayrı indeks mi, bir composite mi?

Sık yapılan bir soru: `(a)` ve `(b)` diye iki ayrı indeks mi, yoksa `(a, b)` diye tek bir composite mi? Genel cevap, sorguların `a` ve `b`'yi **birlikte** filtrelemesi durumunda composite indeksin çok daha verimli olduğudur. İki ayrı indeks kullanıldığında, bazı motorlar **index intersection** (indeks kesişimi) yapabilir ama bu genellikle tek bir composite indeksten daha yavaştır ve daha fazla iş gerektirir. Buna karşılık, sorgular `a` ve `b`'yi ayrı ayrı filtreliyorsa, iki ayrı indeks daha esnek olabilir.

## Covering (Kapsayan) İndeks

### Tanım ve kök neden

Normal bir indeks aramasında iki adım vardır. Önce indeks taranıp aranan satırların **işaretçisi** bulunur; sonra bu işaretçi kullanılarak asıl tablo satırına gidilip istenen diğer sütunlar okunur. Bu ikinci adıma çeşitli sistemlerde **bookmark lookup**, **key lookup** ya da (PostgreSQL bağlamında) **heap fetch** denir. Bu ikinci erişim, ayrı bir rastgele disk I/O'su gerektirdiği için pahalıdır ve çok satır dönen sorgularda maliyetin büyük kısmını oluşturur.

**Covering index**, sorgunun ihtiyaç duyduğu **tüm sütunların indeksin kendisinde bulunduğu** durumdur. Bu durumda motor, aranan cevabı doğrudan indeksten üretir ve **asıl tabloya hiç gitmez**. İkinci adım tamamen ortadan kalkar. Bu erişime **index-only scan** (yalnızca indeks taraması) denir. Kök neden basittir: en pahalı iş olan tabloya rastgele erişimi tümüyle eleyerek sorguyu hızlandırmak.

### Somut örnek

Şu sorguyu düşünelim:

```sql
SELECT first_name FROM users WHERE last_name = 'Yilmaz';
```

- Yalnızca `(last_name)` indeksi varsa: motor indeksten `Yilmaz` satırlarını bulur, sonra her biri için tabloya gidip `first_name`'i okur. Rastgele I/O maliyeti vardır.
- `(last_name, first_name)` indeksi varsa: motor `last_name = 'Yilmaz'` bölgesini bulur ve `first_name` zaten indeksin içinde olduğu için doğrudan oradan okur. Tabloya gitmeye gerek kalmaz. Bu indeks bu sorguyu **cover** eder.

### Anahtar sütun mu, ek (include) sütun mu?

Bazı veritabanları (örneğin SQL Server ve PostgreSQL), yalnızca kapsama amacıyla taşınan sütunları indeksin sıralı anahtarına eklemek yerine, yaprak düğümlere **ek yük (payload)** olarak koyma imkânı sunar; bu genellikle `INCLUDE` sözdizimiyle yapılır. Aradaki fark önemlidir:

- Anahtar sütun (key column) hem sıralamaya katılır hem yer kaplar; arama/aralık/sıralama için kullanılabilir.
- `INCLUDE` sütunu sıralamaya katılmaz, yalnızca yaprakta saklanır; aramada işe yaramaz ama sorguyu **cover** ederek tablo erişimini önler.

Bu yüzden, bir sütuna yalnızca `SELECT` çıktısında ihtiyaç varsa (filtrelemede veya sıralamada değil), onu anahtara değil `INCLUDE` listesine koymak daha doğrudur; böylece indeksin sıralı kısmı gereksiz yere şişmez ve arama verimi korunur.

### Covering indeksin bedeli

Covering, ücretsiz değildir. İndekse ne kadar çok sütun eklerseniz indeks o kadar büyür; bu hem disk alanını hem de her yazma işleminde güncellenmesi gereken veri miktarını artırır. Ayrıca "her ihtimale karşı tüm sütunları covering indekse koyalım" yaklaşımı, indeksi neredeyse tablonun bir kopyası haline getirir ve yazma maliyetini katlar. Doğru yaklaşım, gerçekten sıcak (sık çalışan, performans açısından kritik) sorguları hedef alan dar covering indeksler kurmaktır.

## Yazma Maliyeti: İndekslerin Görünmeyen Bedeli

### Kök neden: indeks de güncellenmek zorundadır

İndeksler okumayı hızlandırır ama bunu bedava yapmaz. Bir tabloda **her `INSERT`, `UPDATE` ve `DELETE`**, o tabloya ait ilgili indekslerin de güncellenmesini gerektirir. Bunun nedeni tutarlılıktır: indeks, tablonun sıralı bir kopyasıdır ve tablo değişince indeks de aynı anda güncel tutulmalıdır; aksi halde indeks yanlış sonuç döndürür.

Bu şu anlama gelir: bir tabloda 5 indeks varsa, tek bir satır eklemek aslında **1 tablo yazması + 5 indeks güncellemesi** demektir. İndeks sayısı arttıkça yazma işlemleri doğrusal olarak yavaşlar. Bu, indekslemenin en sık gözden kaçan maliyetidir; çünkü geliştirici indeksin okuma faydasını hemen görür ama yazma bedelini ancak yük altında fark eder.

### UPDATE'in özel durumu

Bir `UPDATE`'in indekse maliyeti, hangi sütunların değiştiğine bağlıdır. Yalnızca indekste yer almayan sütunları güncelleyen bir `UPDATE`, ilgili indeksi hiç dokundurmayabilir. Ama indekslenmiş bir sütun değişirse, o değerin indeksteki **eski konumdan çıkarılıp yeni konuma eklenmesi** gerekir (çünkü sıralı yerdeki yeri değişmiştir). Bu, tek bir mantıksal güncellemenin indekste iki fiziksel işleme (sil + ekle) dönüşmesi demektir.

### Sayfa bölünmesi (page split) ve fragmantasyon

Yazma maliyetinin daha derin bir katmanı **page split**'tir. B-tree yaprak sayfaları belirli bir doluluğa ulaştığında, araya yeni bir anahtar eklemek için sayfanın **ikiye bölünmesi** gerekir. Sayfa bölünmesi pahalı bir işlemdir: yeni sayfa ayrılır, anahtarların yarısı taşınır, üst düğümdeki işaretçiler güncellenir ve bu işlem loglanır.

Burada anahtarın **sırasının** büyük etkisi vardır:

- **Artan (monotonic) anahtarlar** (örneğin auto-increment ID veya zaman damgası) hep en sona eklenir. Bu, çoğu zaman en sağdaki yaprağı büyütür; bölünmeler daha öngörülebilir ve genelde daha ucuzdur, ancak yoğun eşzamanlı yazmada bu son sayfa bir **hotspot** (sıcak nokta) haline gelip çekişme (contention) yaratabilir.
- **Rastgele anahtarlar** (örneğin rastgele UUID) indeksin ortasına, her yere eklenir. Bu, sürekli ve dağınık sayfa bölünmelerine, indekste **fragmantasyona** ve buffer cache'in daha kötü kullanılmasına yol açar. Bu yüzden birincil anahtar olarak rastgele UUID kullanmak, artan bir anahtara kıyasla yazma performansını gözle görülür biçimde düşürebilir. (Zaman-sıralı UUID varyantları bu sorunu hafifletmek için tasarlanmıştır.)

### Write amplification ve genel sistem etkisi

Sonuç olarak indeksler, bir yazma işleminin gerçekte kaç fiziksel işleme dönüştüğünü artırır; buna genel olarak **write amplification** denir. Fazla indeks; disk alanını şişirir, yazma işlemlerini yavaşlatır, buffer cache'te daha fazla yer kaplayarak diğer verilerin cache'ten atılmasına neden olur ve yedekleme/geri yükleme sürelerini uzatır. Bu yüzden "indeks eklemek her zaman iyidir" cümlesi yanlıştır; **her indeks, faydasını kanıtlamak zorunda olan bir yükümlülüktür.**

## Yaygın Hatalar

Aşağıdaki hatalar sahada en çok görülenlerdir ve çoğu, indeksin nasıl çalıştığını anlamamaktan kaynaklanır.

- **Sütuna fonksiyon/işlem uygulamak.** `WHERE YEAR(created_at) = 2024` veya `WHERE UPPER(email) = '...'` gibi koşullar düz indeksi devre dışı bırakır, çünkü indeks ham değere göre sıralıdır. Çözüm ya koşulu sargable (indeks kullanabilir) hale getirmek (`created_at >= '2024-01-01' AND created_at < '2025-01-01'`) ya da bir ifade indeksi tanımlamaktır.
- **Örtük tip dönüşümü (implicit conversion).** İndeksli sütun `VARCHAR` iken sorguda sayısal değer verilmesi gibi durumlar, motorun sütunu dönüştürmesine ve indeksi kullanamamasına yol açabilir. Sorgu parametrelerinin tipini sütun tipiyle eşleştirin.
- **Composite indekste yanlış sütun sırası.** `(a, b)` varken sorgunun yalnızca `b`'yi filtrelemesi, indeksi kullanılamaz hale getirir. Sütun sırası sorgu kalıplarına göre seçilmelidir.
- **Baştan joker LIKE.** `LIKE '%metin'` B-tree indeks kullanamaz. Böyle aramalar için full-text index veya farklı bir yaklaşım gerekir.
- **Gereğinden fazla, çakışan indeks.** `(a)`, `(a, b)`, `(a, b, c)` indekslerinin üçünü birden tutmak çoğu zaman gereksizdir; `(a, b, c)` zaten `(a)` ve `(a, b)` öneklerini karşılar. Fazlalık, yazma maliyeti ve alan israfı demektir.
- **Düşük seçicilikli tek sütuna indeks.** `cinsiyet` gibi 2-3 değerli bir sütuna tek başına indeks koymak genelde işe yaramaz; motor zaten tablonun yarısını okuyacaksa indeks yerine full scan'i tercih eder.
- **Hiç kullanılmayan indeksleri taşımak.** Zamanla sorgular değişir, bazı indeksler ölü yük haline gelir ama yazma maliyetini yaratmaya devam eder. Kullanım istatistiklerini periyodik olarak gözden geçirmek gerekir.

## En İyi Pratikler

**Sorgudan indekse doğru tasarlayın, tersine değil.** İndeksi tabloya bakarak değil, uygulamanın gerçekte çalıştırdığı sorgulara bakarak tasarlayın. Yavaş çalışan ve sık çalışan sorguları belirleyin; indeksleme kararlarını bu sıcak sorgular yönlendirsin.

**Execution plan'ı okumayı öğrenin.** Her ciddi veritabanı, bir sorgunun nasıl çalıştırılacağını gösteren bir açıklama komutu sunar (birçok sistemde `EXPLAIN`, bazılarında `EXPLAIN ANALYZE` gerçek çalışma süresini de verir). İndeksin gerçekten kullanılıp kullanılmadığını, full scan mi yoksa index scan mi yapıldığını, tahmini satır sayısının gerçekle uyumlu olup olmadığını buradan doğrulayın. İndeks eklemenin işe yaradığını varsaymayın; plan üzerinde ölçerek doğrulayın.

**Eşitlik-sonra-aralık kuralına uyun.** Composite indekslerde eşitlik koşullu sütunları başa, aralık koşullu sütunu sona koyun; kapsanacak `SELECT` sütunlarını mümkünse `INCLUDE` ile ekleyin.

**Covering'i seçici kullanın.** Sıcak sorguları index-only scan yapacak şekilde dar covering indeksler kurun; ama her sütunu her indekse doldurma dürtüsüne direnin.

**Yazma-okuma dengesini bilinçli kurun.** Ağırlıklı okuma yapan (OLAP, raporlama) sistemlerde daha cömert indekslenebilirsiniz. Ağırlıklı yazma yapan (yüksek hacimli OLTP, event/log tabloları) sistemlerde her indeksin write amplification maliyetini ciddiye alın; gereksiz indeksten kaçının.

**Anahtar seçimini yazma davranışına göre yapın.** Yüksek hacimli ekleme yapılan tablolarda, rastgele UUID gibi indeks fragmantasyonu yaratan anahtarlardan mümkünse kaçının; artan veya zaman-sıralı anahtarları tercih edin, ama son-sayfa hotspot çekişmesine de dikkat edin.

**İndeksleri düzenli olarak denetleyin.** Kullanım istatistiklerine bakarak hiç kullanılmayan indeksleri kaldırın, fragmante olmuş indeksleri periyodik olarak yeniden düzenleyin (rebuild/reorganize). İndeksler kurulup unutulacak nesneler değil, yaşam döngüsü olan varlıklardır.

## Özet

İndeksleme, veritabanı performansının kalbindedir ama sihir değildir. B-tree yapısı, disk erişim sayısını en aza indiren sığ ve dallanmış bir ağaç sayesinde büyük tablolarda bile aramayı logaritmik zamana indirir. Composite indeksler birden çok sütunu sözlük sırasıyla birleştirir ve en sol önek kuralına tabidir; sütun sırası performansı belirler. Covering indeksler, sorgunun tüm sütunlarını içererek pahalı tablo erişimini tümüyle ortadan kaldırır. Ancak bütün bu okuma faydalarının karşılığında ödenen bedel, her yazmada indekslerin de güncellenmesi zorunluluğundan doğan **yazma maliyetidir**. İyi bir mühendis, indeksi ücretsiz bir hızlanma değil, bilinçli olarak yönetilen bir okuma-yazma takası olarak görür; ekler, ölçer ve gereksizse kaldırır.
