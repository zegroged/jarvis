# Veri Ambarı / OLAP Mimarisi ve Kolon-Yönelimli Depolama

## Neden Bu Konu Ayrı Bir Başlık Olmayı Hak Ediyor

Veritabanı dünyasının büyük çoğunluğu tek bir varsayımla düşünülür: "az sayıda satır oku/yaz, çok sayıda kullanıcı aynı anda işlem yapsın." Bu, OLTP (Online Transaction Processing) dünyasıdır — bankacılık işlemi, e-ticaret siparişi, kullanıcı kaydı gibi işler. İlişkisel modelin normalizasyonu, B-Tree indeksleri, satır-yönelimli (row-oriented) depolama ve kilitleme/MVCC mekanizmaları hep bu senaryoyu optimize eder.

Ama modern veri mühendisliğinin devasa bir kısmı tam ters bir soruna cevap verir: "milyarlarca satır üzerinde birkaç kolonu topla, filtrele, grupla" (OLAP — Online Analytical Processing). Bu soruyu OLTP mimarisiyle çözmeye çalışmak felakettir; bir e-ticaret veritabanında "son 2 yılda, bölgeye göre, ürün kategorisine göre toplam ciro" sorgusu çalıştırmak, satır-yönelimli bir tabloda diskteki her satırın tamamını okumayı gerektirir, oysa ihtiyacınız olan sadece 3 kolondur. Bu yüzden analitik yük için tamamen farklı bir depolama felsefesi doğdu: **kolon-yönelimli (columnar) depolama** ve onun etrafında şekillenen **veri ambarı (data warehouse) mimarisi**.

Bu makale, Snowflake, BigQuery, ClickHouse, Redshift gibi sistemlerin altında yatan ortak mimari mantığı; star/snowflake şema tasarımını; slowly changing dimension (SCD) problemini ve kolon-yönelimli depolamanın neden bu kadar hızlı olduğunu kök nedenlerine inerek açıklar.

## OLTP ile OLAP Arasındaki Kök Fark

Bu ayrımı sathi bir "biri işlem içindir biri raporlama içindir" cümlesiyle geçiştirmek yanlış olur; asıl fark **erişim deseni (access pattern)**dedir.

- **OLTP erişim deseni**: Tek bir satırın tamamına (veya az sayıda satıra) erişim. "Bu müşterinin adresini güncelle", "bu siparişi ekle." Satırın tüm kolonları birlikte lazımdır ve genellikle bir anahtar (primary key) üzerinden nokta sorgusu (point query) yapılır.
- **OLAP erişim deseni**: Az sayıda kolonun, çok sayıda satır üzerinde toplanması (aggregation). "Tüm siparişlerin toplam tutarı, ay ay, bölgeye göre." Satırın kimliği önemsizdir; önemli olan belirli kolonların taranmasıdır (full veya kısmi column scan).

Bu iki erişim deseni birbirine o kadar zıttır ki, aynı fiziksel depolama düzeni ikisini de iyi hizmet edemez. Satır-yönelimli depolama (bir satırın tüm kolonları diskte yan yana) OLTP için idealdir çünkü bir satırı bir I/O ile çekersiniz. Ama OLAP'ta bu düzen israftır: 50 kolonlu bir tablodan 3 kolonu toplamak için diskten 50 kolonun hepsini okumuş olursunuz — I/O bant genişliğinin ~%94'ü çöpe gider.

**Kök neden**: Depolama düzeni ile sorgu deseni arasındaki uyumsuzluk, performans kaybının asıl kaynağıdır. Kolon-yönelimli depolama bu uyumsuzluğu tersine çevirir.

## Kolon-Yönelimli Depolamanın Çalışma Mantığı

### Satır-yönelimli (row store) vs kolon-yönelimli (column store)

Satır-yönelimli depoda fiziksel disk düzeni şöyledir:

```
Satır1: [id=1, ad="Ali", yas=30, sehir="Ankara"]
Satır2: [id=2, ad="Ayşe", yas=25, sehir="İzmir"]
```

Kolon-yönelimli depoda ise her kolon kendi bitişik (contiguous) bloğunda saklanır:

```
id sütunu:    [1, 2, ...]
ad sütunu:    ["Ali", "Ayşe", ...]
yas sütunu:   [30, 25, ...]
sehir sütunu: ["Ankara", "İzmir", ...]
```

Bu basit değişim üç büyük kazanç doğurur:

**1) Gereksiz I/O'nun elenmesi (column pruning).** Sorgu sadece `yas` ve `sehir` kolonlarına bakıyorsa, motor diskten/depodan sadece o iki kolonun bloklarını okur. Diğer kolonlar hiç dokunulmaz. Geniş tablolarda (100+ kolon) bu, okunacak veri hacmini onlarca kata kadar azaltabilir.

**2) Sıkıştırma (compression) verimliliği.** Aynı tipteki, genellikle benzer veya tekrarlı değerlere sahip veriler yan yana durunca sıkıştırma algoritmaları çok daha etkili çalışır. Bir `sehir` kolonunda binlerce satırda sadece birkaç farklı değer (Ankara, İzmir, İstanbul...) tekrar ediyorsa:
   - **Dictionary encoding**: Her benzersiz değere küçük bir tam sayı kodu atanır, kolon bu kodların dizisi olarak saklanır.
   - **Run-length encoding (RLE)**: Sıralı/tekrarlı veride "bu değer şu kadar kez tekrar etti" şeklinde kodlama.
   - **Delta encoding**: Sayısal/zaman serisi verisinde ardışık farklar saklanır (genellikle küçük sayılardır, az yer kaplar).
   
   Satır-yönelimli depoda bu teknikler bu kadar etkili olamaz çünkü bir satır içinde yan yana duran değerler (id, ad, yas, sehir) birbirinden tamamen farklı tiplerde ve dağılımdadır — sıkıştırıcı örüntü bulamaz.

**3) Vektörize işlem (vectorized execution) ve SIMD.** Bir kolonun ardışık belleğe dizilmiş olması, CPU'nun SIMD (Single Instruction, Multiple Data) komutlarıyla aynı anda birden çok değeri işlemesini mümkün kılar. Modern kolon motorları (ClickHouse, DuckDB, Snowflake'in çalıştırma motoru) satır satır değil, "batch" (binlerce değerlik vektör) halinde işlem yapar; bu, fonksiyon çağrısı başına düşen CPU dallanma (branch) ve önbellek (cache) kaçırma maliyetini büyük ölçüde azaltır.

**Kök neden özet**: Kolon-yönelimli depolama, "birlikte okunan verinin birlikte depolanması" ilkesini OLAP erişim desenine göre optimize eder; bunun doğal sonuçları column pruning, yüksek sıkıştırma oranı ve SIMD dostu işlemedir.

### Bedeli nedir?

Bu tasarımın maliyeti tam satır ekleme/güncellemede ortaya çıkar. Tek bir satır eklemek için mantıken her kolonun ayrı bloğuna dokunmak gerekir — bu, satır-yönelimli depoda tek bir yazma iken kolon-yönelimlide N kolon kadar yazma anlamına gelebilir. Bu yüzden kolon motorları genelde:
- Küçük, sık tekil INSERT/UPDATE için optimize değildir (OLTP değildir).
- Veriyi toplu (batch/bulk) olarak, genelde immutable (değişmez) segmentler/parçalar halinde yazarlar; güncellemeler genelde "eski segmenti işaretle, yeni segment ekle" (merge-on-read) veya periyodik sıkıştırma (compaction) ile yönetilir.
- Bu yüzden "upsert ağırlıklı", satır-satır değişen uygulama verisi kolon deposunda değil, OLTP veritabanında tutulur; oradan ETL/ELT ile ambara akıtılır.

## Veri Ambarı Mimarisinin Katmanları

Klasik bir veri ambarı boru hattı şu katmanlardan oluşur:

1. **Kaynak sistemler**: OLTP veritabanları, uygulama logları, üçüncü parti API'ler, IoT akışları.
2. **Alım (ingestion) / ETL-ELT**: Veriyi kaynaktan ambara taşıma. Klasik ETL (Extract-Transform-Load), veriyi ambara yazmadan önce dönüştürür; modern ELT (Extract-Load-Transform) ham veriyi önce ambara yükler, dönüşümü ambarın kendi hesaplama gücüyle (ör. SQL, dbt) sonradan yapar. ELT'nin yaygınlaşmasının nedeni, bulut ambarlarının (Snowflake, BigQuery) hesaplama ve depolamayı ayrıştırıp (bkz. aşağıda) ucuz ve esnek hale getirmesidir.
3. **Ham/staging katmanı**: Kaynağa en yakın, minimum dönüşümlü veri (genelde "bronze" katman da denir).
4. **Model/ısıtılmış (curated) katman**: İş mantığına göre temizlenmiş, birleştirilmiş, boyutsal modele (dimensional model) oturtulmuş veri ("silver"/"gold" katmanları — Medallion mimarisi bu isimlendirmeyi kullanır).
5. **Sunum/erişim katmanı**: BI araçları (Looker, Tableau, Power BI), ad-hoc SQL, makine öğrenmesi özellik depoları (feature store) bu katmandan beslenir.

### Hesaplama ve depolamanın ayrıştırılması (compute-storage separation)

Modern bulut OLAP sistemlerinin (Snowflake, BigQuery, ve büyük ölçüde Redshift/Databricks) mimari çekirdek yeniliği budur: geleneksel veritabanlarında hesaplama (sorgu motoru) ile depolama (disk) aynı makinede sıkıca bağlıydı; ölçeklendirmek için ikisini birlikte büyütmek gerekiyordu. Bulut ambarları bunu ayırır:
- Veri, ucuz nesne depolamada (S3, GCS benzeri) kolon formatında (Parquet, ORC veya motöre özel format) durur.
- Hesaplama, ihtiyaç anında bağımsız "sanal depo/cluster" olarak ölçeklenir, sorgu bitince kapatılabilir.

**Kök neden / bunun sağladığı şey**: Depolama maliyeti neredeyse sabitken, hesaplama talebe göre elastik ve olay-bazlı (sorgu başına) fiyatlandırılabilir hale gelir. Bu da çoklu takımın aynı veriye farklı hesaplama kümeleriyle (birbirini yavaşlatmadan) erişmesini mümkün kılar — "workload isolation."

## Boyutsal Modelleme: Star Schema ve Snowflake Schema

OLTP dünyasında normalizasyon (3NF) veri bütünlüğünü ve yazma verimliliğini optimize eder. OLAP dünyasında ise asıl amaç **sorgu basitliği ve okuma performansı**dır; bu yüzden Ralph Kimball'ın öncülük ettiği **boyutsal modelleme (dimensional modeling)** kullanılır.

### Star Schema (Yıldız Şema)

Merkezde bir **fact table (olgu tablosu)** bulunur — ölçülebilir olayları tutar (satış tutarı, tıklama sayısı, sipariş adedi). Fact tablosunun kolonları genelde iki türdür:
- **Ölçüler (measures)**: sayısal, toplanabilir değerler (tutar, miktar).
- **Yabancı anahtarlar (foreign keys)**: boyut tablolarına işaret eder.

Etrafında **dimension table (boyut tablosu)**lar bulunur — "kim, ne, ne zaman, nerede" bağlamını taşır (müşteri, ürün, tarih, mağaza). Boyutlar denormalize edilir; yani bir `urun_boyutu` tablosu kategori, alt kategori, marka gibi bilgileri tek bir düz tabloda tutar, ayrı normalize tablolara bölünmez.

```
        dim_musteri
             |
dim_tarih -- fact_satis -- dim_urun
             |
        dim_magaza
```

**Neden denormalize edilir?** Çünkü OLAP sorgusunda amaç, mümkün olduğunca az JOIN ile geniş bir tabloya ulaşmaktır. Her JOIN, sorgu motoruna ek maliyet (hash join, shuffle) getirir. Denormalize bir boyut tablosu, "kategoriye göre satış" sorgusunu tek bir JOIN'e indirger.

### Snowflake Schema

Snowflake şema, boyut tablolarının kendisinin de normalize edilmesidir — ör. `dim_urun` tablosu `kategori_id` üzerinden ayrı bir `dim_kategori` tablosuna bağlanır. Bu, veri tekrarını azaltır (depolama tasarrufu, güncelleme tutarlılığı) ama sorgu başına JOIN sayısını artırır.

**Ödünleşim (trade-off)**: Star schema daha hızlı sorgu + daha fazla depolama/tekrar; snowflake schema daha az tekrar + daha yavaş (daha çok JOIN'li) sorgu. Modern kolon motorlarında depolama ucuz ve sıkıştırma güçlü olduğundan, pratikte star schema çoğunlukla tercih edilir; snowflake şema genelde çok büyük, sık değişen, yüksek kardinaliteli boyutlarda (ör. çok seviyeli coğrafi hiyerarşi) gerekçelendirilir.

### Fact tablosu türleri (kısaca)

- **Transaction fact**: her olay bir satır (her satış işlemi).
- **Periodic snapshot fact**: düzenli aralıklarla durumun anlık görüntüsü (ay sonu stok seviyesi).
- **Accumulating snapshot fact**: bir sürecin aşamalarını tek satırda, aşama tamamlandıkça güncelleyerek tutar (sipariş → kargo → teslimat tarihleri).

## Slowly Changing Dimensions (SCD): Zaman İçinde Değişen Bağlam Problemi

Boyut verisi zamanla değişir: bir müşteri şehir değiştirir, bir ürün kategori değiştirir. Sorun şu: geçmişteki bir satışı raporlarken, **o satış anındaki** boyut değerini mi yoksa **şu anki** değeri mi göstermeliyiz? Bu, iş mantığına bağlı bir karardır ve SCD türleri bu kararı standartlaştırır.

- **SCD Type 0**: Değer hiç değişmez (ör. doğum tarihi). Basit.
- **SCD Type 1**: Eski değerin üzerine yazılır (overwrite). Geçmiş kaybolur. Basit ama tarihsel doğruluk yoktur — "müşteri her zaman şu anki şehrindeymiş gibi" görünür.
- **SCD Type 2**: Yeni bir satır eklenir; eski satır `gecerlilik_baslangic`/`gecerlilik_bitis` tarihleriyle (veya `is_current` bayrağıyla) "kapatılır". Tam tarihsel doğruluk sağlar — her fact satırı, o zamanki doğru boyut satırına (surrogate key ile) bağlanır. En yaygın ve en "doğru" yöntemdir ama tablo büyür ve sorgular "en güncel" satırı bulmak için ekstra filtre gerektirir.
- **SCD Type 3**: Sadece "önceki değer" için ayrı bir kolon eklenir (ör. `eski_sehir`, `yeni_sehir`). Sınırlı geçmiş (genelde sadece bir önceki durum) tutar; nadir kullanılır çünkü çok seviyeli değişikliği tutamaz.
- **Hibrit yaklaşımlar (Type 4, 6...)**: Ayrı bir geçmiş tablosu (mini-dimension) veya Type 1+2+3 kombinasyonları da literatürde geçer; bunlar spesifik ihtiyaçlara göre kurumsal uygulamalarda türetilir.

**Kök neden anlayışı**: SCD, "boyut kimliği (doğal anahtar/natural key)" ile "boyutun o andaki hali (surrogate key)" arasındaki farkı yönetme problemidir. Fact tablosu doğal anahtara değil, surrogate key'e (genelde sıralı, anlamsız bir tamsayı) referans vermelidir — böylece geçmişteki bir olay, o olay anındaki boyut satırına sabitlenmiş kalır ve boyut değişse bile geçmiş rapor bozulmaz.

## Yaygın Tuzaklar ve En İyi Pratikler

**Tuzak 1: OLTP şemasını olduğu gibi ambara kopyalamak.** Normalize 3NF şema doğrudan BI aracına bağlanırsa, her rapor 10-15 JOIN gerektirir; hem yavaştır hem analistler için anlaşılmazdır. Çözüm: boyutsal modele dönüştür (ELT ile "gold" katman inşa et).

**Tuzak 2: Surrogate key kullanmadan doğal anahtarla SCD Type 2 yapmaya çalışmak.** Doğal anahtar (ör. müşteri_no) zamanla birden fazla boyut satırına karşılık geldiğinde (çünkü Type 2 yeni satır ekliyor), fact tablosunun hangi satıra bağlanacağı belirsizleşir. Her zaman ayrı, tekil bir surrogate key üretin.

**Tuzak 3: Kolon deposunda satır-satır sık UPDATE/DELETE yapmak.** Kolon motorları toplu yazım için tasarlanmıştır; sık tekil güncelleme "small file problem" (çok sayıda küçük segment/parça, sorgu motorunun taraması gereken dosya sayısını artırır) veya pahalı merge-on-read maliyetine yol açar. Batch/micro-batch yazım deseni kullanın; gerekirse periyodik "compaction/OPTIMIZE" işlemleri planlayın.

**Tuzak 4: Yanlış partition/clustering anahtarı seçmek.** Kolon motorlarında partition (ör. tarihe göre) ve sıralama/clustering anahtarı (ör. ClickHouse'ta `ORDER BY`, Snowflake'te clustering key), motorun hangi veri bloklarını atlayabileceğini (**data skipping / zone maps / min-max pruning**) belirler. Sorgu deseniyle uyumsuz bir anahtar seçilirse, kolon deposu bile gereksiz yere tüm veriyi tarar. En iyi pratik: en sık filtrelenen/aralık sorgusu yapılan kolonu (genelde tarih) birincil partition/sıralama anahtarı yapmak.

**Tuzak 5: Yüksek kardinaliteli kolonlarda yanlış encoding beklemek.** Dictionary encoding, düşük-orta kardinaliteli kolonlarda (şehir, kategori, durum) çok etkilidir; her satırda benzersiz olan bir kolonda (ör. UUID, zaman damgası) sözlük şişer ve avantaj azalır. Bu tür kolonlar için delta/bit-packing gibi farklı encoding'ler daha uygundur — çoğu motor bunu otomatik seçer ama şema tasarlarken bilinçli olmak gerekir.

**Tuzak 6: "Tek büyük geniş tablo (one big table / OBT)" ile star schema'yı karıştırmak.** Bazı modern kolon motorlarında (özellikle JOIN maliyeti yüksekse) tüm boyutları fact'e önceden JOIN'leyip tek geniş, denormalize bir tablo (OBT) oluşturmak performans için tercih edilebilir. Bu geçerli bir optimizasyondur ama veri tekrarını ve güncelleme karmaşıklığını artırır; genelde "sunum katmanı" optimizasyonu olarak, temel boyutsal model üzerine türetilmiş bir görünüm (materialized view) şeklinde yapılır — temel modelin yerine geçmez.

**Tuzak 7: Ambarı gerçek zamanlı OLTP gibi kullanmaya çalışmak.** "Kullanıcı arayüzünde tek kayıt sorgusu ambardan gelsin" isteği, kolon motorlarının nokta-sorgu (point lookup) maliyetinin satır motorlarına göre çoğu zaman daha yüksek olması nedeniyle yanlış araç seçimidir. Nokta sorgular için OLTP/anahtar-değer deposu, analitik toplamalar için OLAP ambarı — ayrı araçlar, ayrı amaçlar.

## Tespit ve Gözlemlenebilirlik Açısından Önemli Noktalar

Bir veri mühendisi/güvenlik gözüyle bakıldığında, ambar mimarisinde izlenmesi gereken sinyaller şunlardır:

- **Sorgu maliyeti/tarama hacmi izleme**: Bulut ambarlarında (BigQuery bytes-scanned, Snowflake credit kullanımı) beklenmedik şekilde büyük tam tablo taramaları hem maliyet hem performans sorununun erken işaretidir; genelde eksik partition pruning veya yanlış filtre kullanımına işaret eder.
- **Veri tazeliği (freshness) izleme**: ELT boru hattında gecikme, "gold" katmanın ne kadar güncel olduğunu etkiler; SLA'ların (ör. "veri en fazla 1 saat gecikmeli") izlenmesi kritik.
- **Şema sürüklenmesi (schema drift)**: Kaynak sistemde beklenmeyen bir kolon eklenmesi/kaldırılması, ELT'yi sessizce bozabilir; şema doğrulama (schema validation) adımları erken tespit sağlar.
- **Erişim kontrolü**: Ambarda tüm kurumsal veri tek bir yerde toplandığından, satır/kolon seviyesinde erişim kontrolü (row-level security, column masking) OLTP'dekinden daha kritik hale gelir — tek bir yanlış yapılandırılmış rol, tüm şirketin hassas verisine erişim açabilir.

## Özet

OLAP mimarisi, OLTP'nin çözdüğü problemin ayna görüntüsünü çözer: az satır/çok kolon yerine çok satır/az kolon erişimi. Bu farklı erişim deseni, kolon-yönelimli fiziksel depolamayı (column pruning, yüksek sıkıştırma, SIMD/vektörize işlem), hesaplama-depolama ayrıştırılmış bulut mimarisini ve boyutsal modellemeyi (star/snowflake schema, SCD) doğuran kök nedendir. Bu mimariyi doğru anlamanın pratik değeri, doğru araç seçiminde (OLTP mi OLAP mı), doğru şema tasarımında (ne zaman denormalize etmeli) ve doğru performans ayarında (partition/clustering anahtarı, batch yazım deseni) ortaya çıkar. Modern veri mühendisliğinin çoğu pratik sorunu — yavaş rapor, şişen bulut faturası, tutarsız tarihsel veri — bu temel ilkelerden birinin ihlal edilmesinden kaynaklanır.
