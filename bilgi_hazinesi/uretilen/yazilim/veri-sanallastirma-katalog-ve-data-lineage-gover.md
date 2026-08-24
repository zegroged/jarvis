# Veri Sanallaştırma/Katalog ve Data Lineage/Governance

## Giriş: Neden Bu Konu Önemli?

Büyük bir veri mühendisliği organizasyonunda, aylar veya yıllar geçtikçe elinizde binlerce tablo, yüzlerce pipeline, onlarca kaynak sistem ve dağınık bir şekilde çoğalan raporlar birikir. Bir noktada kimse şu soruların cevabını net olarak bilemez: "Bu tablo nereden geliyor?", "Bu sütun hangi kaynaktan besleniyor?", "Bu veri içinde kişisel veri (PII) var mı?", "Bu raporu bozmadan şu kaynağı silebilir miyim?". İşte **data governance** (veri yönetişimi) ve onun teknik ayakları olan **data catalog**, **data lineage** ve **PII discovery** tam bu sorulara cevap vermek için vardır.

Bu üç kavram, veriyi "kaotik bir dosya yığını" olmaktan çıkarıp "aranabilir, izlenebilir, uyumlu (compliant) bir varlık" haline getirir. KVKK, GDPR gibi düzenlemeler bu yeteneklerin bir kısmını yasal olarak zorunlu hale getirdiği için de konu, güvenlik ve uyum (compliance) ile doğrudan kesişir.

---

## 1. Data Catalog (Veri Kataloğu)

### Tanım

**Data catalog**, bir organizasyondaki tüm veri varlıklarının (tablolar, view'lar, dosyalar, dashboard'lar, ML feature'ları) merkezi, aranabilir bir envanteridir. Kütüphane kataloğu benzetmesi doğrudur: Kütüphanedeki her kitabın konumunu, yazarını, konusunu bir katalog fişi tutar; siz raflarda tek tek aramazsınız. Data catalog da veri için aynı işi yapar.

Katalog sadece "veri nerede" sorusuna değil, **metadata** (üstveri) katmanında zenginleştirilmiş şu bilgilere de cevap verir:

- **Teknik metadata**: Şema, sütun tipleri, satır sayısı, boyut, partition yapısı.
- **İş metadata (business metadata)**: Bu tablonun iş anlamı nedir, hangi departman sahibi, hangi KPI'ı besler.
- **Operasyonel metadata**: En son ne zaman güncellendi, hangi job tarafından yazıldı, tazelik (freshness) durumu.
- **Sosyal metadata**: Kim en çok kullanıyor, popülerlik, kullanıcı yorumları, "onaylı/deprecated" etiketi.

### Kök Neden / Çalışma Mantığı

Kataloglar tipik olarak **metadata harvesting** (üstveri toplama) mekanizmasıyla çalışır. Bir crawler veya connector, kaynak sistemlere (Snowflake, BigQuery, PostgreSQL, S3, Kafka, dbt, Airflow) bağlanır ve onların **information_schema** benzeri sistem kataloglarını okur. Elde edilen üstveri, kataloğun kendi merkezi deposunda normalize edilir ve indekslenir.

Modern kataloglar iki yaklaşımı birleştirir:

1. **Pull (çekme)**: Katalog periyodik olarak kaynakları tarar. Basit ama gecikmeli; üstveri her zaman biraz eskidir.
2. **Push / event-driven (olay tabanlı)**: Kaynak sistem veya pipeline, bir değişiklik olduğunda katalog API'sine olay gönderir. Daha güncel ama entegrasyon maliyeti yüksektir.

Katalog değerinin çoğu **arama ve keşif** deneyimindedir. Kullanıcı "müşteri gelir" yazınca, alakalı tabloları popülerliğe, güvenilirliğe ve sahipliğe göre sıralanmış görmelidir. Bu yüzden iyi kataloglar bir arama motoru (örneğin Elasticsearch benzeri bir indeks) üzerine kurulur.

### Örnek

Diyelim ki bir veri analisti "aktif kullanıcı sayısı" raporunu yapacak. Katalogsuz dünyada Slack'te "hangi tablo doğru aktif kullanıcıyı veriyor?" diye sorar, üç farklı cevap alır, yanlış tabloyu seçip hatalı rapor üretir. Katalog varsa: Arama kutusuna yazar, "certified" (onaylı) rozeti olan `analytics.daily_active_users` tablosunu bulur, sahibinin veri platformu ekibi olduğunu, günlük 06:00'da güncellendiğini, 40 kişinin bu tabloyu kullandığını görür ve güvenle seçer.

### Doğru Kullanım + Tuzaklar

**Doğru:**
- Kataloğu **kaynak-of-truth** haline getirin, wiki sayfalarını değil. Wiki'ler kaçınılmaz olarak eskir; otomatik harvest edilen katalog güncel kalır.
- **Sahiplik (ownership)** alanını zorunlu kılın. Sahibi olmayan tablo, kimsenin bakmadığı tablodur.
- **Data contract** ve sertifikasyon katmanı ekleyin: hangi tablolar üretim-kalitesinde, hangileri deneysel.

**Tuzaklar:**
- **"Kur ve unut" tuzağı**: Katalog kurmak kolay, canlı tutmak zordur. İnsanlar açıklama alanlarını doldurmazsa katalog sadece teknik şema deposu olur, iş değeri kaybolur.
- **Aşırı üstveri**: Her alanı zorunlu yapmak, kimsenin veri girmemesine yol açar. Az ama tutarlı üstveri, çok ama boş üstveriden iyidir.

---

## 2. Data Lineage (Veri Soy İzleme)

### Tanım

**Data lineage**, bir veri parçasının kaynağından son kullanım noktasına kadar geçtiği tüm dönüşüm yolunun haritasıdır. "Bu sütundaki değer nereden geldi, hangi işlemlerden geçti, sonunda hangi raporda göründü?" sorusunun grafiksel/programatik cevabıdır.

İki temel granülerlik seviyesi vardır:

- **Table-level lineage (tablo seviyesi)**: `tablo A` → `tablo B` → `dashboard C`. Kabaca akışı gösterir.
- **Column-level lineage (sütun seviyesi)**: `A.email` → `B.hashed_email` → `report.user_id`. Çok daha güçlü ama üretmesi zor. Etki analizi (impact analysis) ve PII izleme için asıl değerli olan budur.

### Kök Neden / Çalışma Mantığı

Lineage üretmek için sistem, veriyi üreten **dönüşümleri anlamak** zorundadır. Üç ana teknik vardır:

1. **SQL / kod parse etme (statik analiz)**: Pipeline'lardaki SQL sorguları veya dbt modelleri parse edilir. Bir `INSERT INTO b SELECT ... FROM a` ifadesinden, sistem "b, a'dan besleniyor" çıkarımını yapar. Sütun seviyesi lineage için sorgunun **AST**'si (Abstract Syntax Tree) analiz edilip her hedef sütunun hangi kaynak sütun(lar)dan türediği izlenir. Güçlü ama dinamik SQL, saklı yordamlar (stored procedure) ve kod içi string birleştirmeleri kör noktalardır.

2. **Runtime / query log analizi**: Veritabanının çalıştırdığı sorguların loglarını (örneğin query history) okuyup, gerçekte çalışan sorgulardan lineage çıkarılır. Statik analizin kaçırdığı dinamik durumları yakalar.

3. **Orchestration entegrasyonu ve OpenLineage**: Airflow, Spark, dbt gibi araçlar, çalışırken lineage olaylarını yayınlar. **OpenLineage** bu alanda yaygınlaşan açık bir standarttır; "hangi job, hangi input dataset'lerden hangi output dataset'i üretti" bilgisini standart bir formatla iletir. Bu yaklaşım, tahmine değil gerçekleşen çalışmaya dayandığı için genellikle en güvenilir olanıdır.

### Örnek: Etki Analizi

Bir mühendis, `raw.legacy_orders` tablosunu silmek istiyor. Lineage grafiği olmadan bu bir kumar oynamaktır. Column-level lineage varsa, mühendis grafiği açar ve görür ki `legacy_orders.amount` sütunu → `staging.orders` → `finance.revenue_daily` → CFO'nun izlediği "Aylık Gelir" dashboard'ına kadar akıyor. Silme işlemi finans raporlamasını bozacaktır. Lineage bu felaketi silmeden önce ortaya çıkarır. Buna **downstream impact analysis** denir. Ters yön (**upstream**) ise "bu raporda yanlış rakam var, kök neden hangi kaynakta?" için kullanılır (**root cause analysis**).

### Doğru Kullanım + Tuzaklar

**Doğru:**
- Lineage'i **veri kalitesi** ve **incident müdahalesi** ile entegre edin. Bir tablonun freshness'i bozulunca, downstream'de neyin etkilendiğini otomatik uyarın.
- Mümkünse **OpenLineage** gibi runtime tabanlı yaklaşımı tercih edin; statik parse'a %100 güvenmeyin.

**Tuzaklar:**
- **Yanlış tam olma hissi (false completeness)**: Lineage grafiği %80 kapsamlıysa ama kullanıcı %100 sanıyorsa tehlikelidir. Kör noktalardaki bir bağımlılığı "yok" sanıp veriyi siler. Kapsamın nerede eksik olduğunu şeffaf gösterin.
- **BI katmanının kopukluğu**: Lineage çoğu zaman warehouse'da biter, dashboard katmanına ulaşmaz. Oysa gerçek "son kullanım" BI aracındadır; bu boşluk kritik etkileri gizler.

---

## 3. PII Discovery ve Data Governance

### Tanım

**PII (Personally Identifiable Information)**, bir gerçek kişiyi tanımlayan veya tanımlanabilir kılan veridir: ad-soyad, TC kimlik numarası, e-posta, telefon, IP adresi, konum, sağlık verisi gibi. **PII discovery**, bir veri ortamındaki tüm bu hassas alanları otomatik olarak **tespit etme, sınıflandırma (classification) ve etiketleme** sürecidir.

**Data governance** ise bunun üzerine kurulan politika katmanıdır: Kim hangi veriye erişebilir, hassas veri nasıl maskelenir, ne kadar süre saklanır (retention), silinme talebi (right to erasure / KVKK'da silme hakkı) nasıl işletilir.

### Kök Neden / Çalışma Mantığı

Otomatik PII tespiti tipik olarak katmanlı çalışır, çünkü tek bir yöntem yetersizdir:

1. **İsim/şema tabanlı tarama (metadata scanning)**: Sütun adları taranır. `email`, `phone`, `ssn`, `tckn`, `dogum_tarihi` gibi isimler güçlü sinyaldir. Hızlı ve ucuz ama yanıltıcıdır: `notes` adlı bir serbest metin sütunu içinde gizli PII olabilir; `id` adlı sütun PII olmayabilir.

2. **İçerik/desen tabanlı tarama (regex + pattern matching)**: Verinin bir örneği (sample) alınıp içeriği taranır. E-posta, kredi kartı (Luhn algoritması ile doğrulama), telefon, IBAN gibi yapısal desenler regex ve doğrulama kurallarıyla yakalanır. Kredi kartı için Luhn checksum, IBAN için ülke kodu + kontrol hanesi doğrulaması, salt regex'in yanlış pozitiflerini azaltır.

3. **Sözlük / referans eşleştirme (dictionary matching)**: Bilinen değer listeleriyle (örneğin şehir adları, ülke listeleri) eşleştirme.

4. **NLP / ML tabanlı NER (Named Entity Recognition)**: Serbest metin içindeki kişi adı, adres gibi yapısal olmayan PII'yı, eğitilmiş modellerle tespit etme. Regex'in yapamadığı "Ahmet Yılmaz, Kadıköy'de oturuyor" gibi cümleleri yakalar. Güçlü ama yanlış pozitif/negatif oranı ve maliyeti yüksektir.

Bu katmanlar bir **confidence score** (güven skoru) üretir. Örneğin hem sütun adı `email` hem de içerik e-posta desenine uyuyorsa güven yüksektir; sadece biri uyuyorsa insan onayına düşen bir "aday" olarak işaretlenir.

Tespit sonrası governance eylemleri devreye girer:

- **Sınıflandırma etiketleri**: `PII`, `Sensitive`, `Confidential`, `Public`.
- **Masking / anonymization**: Görüntüleme sırasında maskeleme (dynamic data masking), hash'leme, tokenization veya k-anonymity gibi anonimleştirme.
- **Access control**: Etikete bağlı erişim politikaları (attribute-based access control). "PII etiketli sütunlar sadece `pii_reader` rolüne görünür."

### Örnek

Bir e-ticaret şirketi, analistlerin geniş erişimi olduğu bir data warehouse işletiyor. PII discovery taraması, `logs.raw_events` tablosunun `payload` adlı JSON sütununda, hiç beklenmedik şekilde ham e-posta ve telefon numaraları bulunduğunu ortaya çıkarır: geliştirici, debug amacıyla tüm event gövdesini loglamış. İsim tabanlı tarama bunu asla yakalayamazdı (`payload` masum bir isim); ancak içerik tabanlı tarama yakaladı. Governance ekibi bu sütunu `PII` olarak etiketler, maskeleme uygular ve retention süresini kısaltır. Bu, KVKK/GDPR açısından ciddi bir veri sızıntısı riskini kapatır.

### Güvenlik/Uyum ile Kesişim (Savunma Bakışı)

Bu konu bir "saldırı" konusu değil, tam tersine bir **savunma ve tespit** konusudur. Governance'ın güvenlik değeri şudur:

- **Attack surface (saldırı yüzeyi) küçültme**: Nerede hassas veri olduğunu bilmiyorsanız koruyamazsınız. Discovery, korunması gerekeni görünür kılar.
- **Least privilege (en az yetki)** uygulanması: Etiketlenmiş PII sayesinde erişim politikaları otomatik uygulanır; herkesin her şeye eriştiği geniş yetki modeli daraltılır.
- **Uyum kanıtı (audit)**: Bir denetimde "kişisel verilerinizi nasıl envanterliyorsunuz ve koruyorsunuz?" sorusuna, discovery + catalog + lineage kombinasyonu somut cevap verir.
- **Silme hakkının işletilmesi**: KVKK/GDPR'daki "unutulma/silme hakkı" için, bir kişinin verisinin hangi tablolara yayıldığını lineage + PII haritası olmadan bulmak neredeyse imkansızdır.

### Doğru Kullanım + Tuzaklar

**Doğru:**
- Tespiti **tek seferlik değil sürekli** yapın. Yeni pipeline'lar sürekli yeni hassas veri sızdırabilir; tarama periyodik ve olay tabanlı olmalıdır.
- **Sampling stratejisini** dikkatli seçin. Milyarlarca satırı tam taramak pahalıdır; ama örnek çok küçükse nadir PII kaçar.
- Tespit sonucunu her zaman **insan doğrulamasıyla** (human-in-the-loop) birleştirin; tam otomatik etiketleme yanlış pozitiflerle güveni yok eder.

**Tuzaklar:**
- **False positive yorgunluğu**: Sistem çok fazla yanlış PII alarmı üretirse, ekip alarmları görmezden gelmeye başlar; bu gerçek bir PII'nın kaçmasından daha tehlikeli olabilir.
- **Quasi-identifier körlüğü**: Tek başına PII olmayan alanlar (posta kodu + doğum tarihi + cinsiyet) birleştiğinde kişiyi tanımlanabilir kılar. Sütun bazlı tespit bunu kaçırır; bağlamsal (kombinasyon) risk analizi gerekir.
- **Örnekleme yanlılığı**: İlk N satırdan sample almak, verinin başında olmayan PII'yı kaçırır (örneğin tarihe göre sıralı bir tabloda). Rastgele örnekleme tercih edilmelidir.

---

## 4. Üçünün Birlikte Çalışması

Bu üç bileşen ayrı ürünler gibi görünse de, gerçek değer **birleştiklerinde** ortaya çıkar:

- **Catalog**, "ne var" sorusunun cevabıdır (envanter).
- **Lineage**, "nereden geliyor, nereye gidiyor" sorusunun cevabıdır (akış).
- **PII discovery**, "hangisi hassas" sorusunun cevabıdır (sınıflandırma).

Birleşince güçlü bir senaryo doğar: PII discovery bir kaynak sütunu `PII` olarak etiketler; lineage bu etiketi **downstream'e otomatik yayar** (**tag propagation**). Yani `raw.users.email` PII ise, ondan türeyen `staging.users.email_hash` ve `report.contacts` da otomatik olarak "PII kökenli" işaretlenir. Böylece hassas verinin türevleri gözden kaçmaz. Catalog ise bu zenginleştirilmiş, etiketli, izlenebilir görünümü tek bir aranabilir arayüzde sunar.

---

## 5. Yaygın Hatalar (Özet)

1. **Governance'ı araç sanmak**: Tek başına katalog aracı kurmak governance sağlamaz. Governance bir **süreç ve sahiplik meselesidir**; araç sadece onu mümkün kılar. Politikasız, sahipsiz bir katalog ölü bir envanterdir.

2. **Manuel üstveriye bel bağlamak**: İnsanların elle doldurduğu açıklamalar kaçınılmaz olarak eskir. Mümkün olan her şeyi (şema, freshness, lineage, PII) otomatik harvest edin; manueli sadece iş anlamı gibi otomatikleşmeyen kısımlara ayırın.

3. **Lineage kapsamını abartmak**: %100 lineage neredeyse hiçbir gerçek ortamda yoktur. Dinamik SQL, BI katmanı, harici scriptler kör noktalardır. Kapsamı olduğundan büyük göstermek, yanlış güvenle veri silmeye yol açar.

4. **PII tespitini yalnızca sütun adına dayamak**: En sık ve en tehlikeli hata. Serbest metin, JSON payload, log sütunları isimlerinden masum görünür ama en riskli PII depolarıdır. İçerik tabanlı tarama şarttır.

5. **Quasi-identifier'ları ihmal etmek**: Anonimleştirme yaptığını sanıp, birleşimle yeniden kimliklendirilebilir (re-identification) veri bırakmak. Gerçek anonimlik, tekil alanları değil kombinasyonları düşünmeyi gerektirir.

6. **Tek seferlik proje muamelesi**: Governance canlı bir sistemdir. Bir kez tarayıp "tamam" demek, ertesi hafta eklenen pipeline'la geçersizleşir. Sürekli, olay tabanlı çalışması gerekir.

7. **Erişim politikasını etiketlerden ayrı tutmak**: PII etiketleri, erişim kontrolüne otomatik bağlı değilse sadece dekoratif kalır. Değerli olan, etiketin gerçekten erişimi kısıtlamasıdır (policy-as-code).

---

## Sonuç

Data catalog, lineage ve PII discovery; olgun bir veri organizasyonunun sinir sistemini oluşturur. Catalog **keşfi**, lineage **izlenebilirliği**, PII discovery **hassasiyet farkındalığını** sağlar. Governance ise bunların üzerine oturan, politikaları uygulayan ve uyumu (KVKK/GDPR) kanıtlayan yönetişim katmanıdır.

Bu yeteneklerin ortak felsefesi şudur: **Göremediğin veriyi ne yönetebilir ne de koruyabilirsin.** Bu sistemlerin asıl görevi veriyi görünür, izlenebilir ve hesap verebilir kılmaktır. Doğru kurulduğunda; yanlış bir tablo silmenin bir raporu çökertmesini önler, bir denetimde soğukkanlı cevap vermenizi sağlar ve en önemlisi, bir kişinin verisinin sistemin karanlık köşelerinde korumasız durmasının önüne geçer.
