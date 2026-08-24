# Normalizasyon ve Denormalizasyon

İlişkisel veritabanı tasarımının kalbinde tek bir soru yatar: **veriyi nasıl bölmeliyiz?** Aynı gerçeği kaç yerde saklarsak, o kadar çok yerde güncellememiz, o kadar çok yerde tutarsızlığa düşme riskimiz olur. Normalizasyon, bu riski matematiksel bir disiplinle azaltan tasarım yöntemidir. Denormalizasyon ise tersine, bilinçli olarak biraz veri tekrarını geri getirerek performans kazanma takasıdır. Bu makale, 1NF'ten 3NF'e kadar normal formları kök nedenleriyle açıklar, anomali kavramını somutlaştırır ve denormalizasyon takasını mühendislik gözüyle ele alır.

## Temel Fikir: Neden Bölüyoruz?

Bir veritabanı tablosunu, her satırı bir gerçeği ifade eden bir defter gibi düşünün. Sorun, tek bir satıra birbirinden bağımsız birden fazla gerçeği tıkıştırdığımızda başlar. Örneğin bir sipariş satırına hem müşterinin adresini hem ürünün fiyatını hem de kargo firmasının telefonunu yazarsak, bu bilgilerin her biri aslında farklı bir "varlığa" (entity) ait olduğu hâlde aynı yerde tutuluyor demektir.

Bunun neden kötü olduğunu anlamak için şu gerçeği kavramak gerekir: **veri tekrarı, tek başına bir estetik sorun değildir; güncelleme tutarlılığını bozan yapısal bir kusurdur.** Müşteri adresini yüz siparişte tekrarladıysanız, müşteri taşındığında yüz satırı güncellemeniz gerekir. Bir tanesini unutursanız, veritabanınız artık aynı müşteri için iki farklı gerçek söyler. İşte normalizasyon, "her gerçek tek bir yerde yaşasın" ilkesini sistematik kurallara dönüştürür.

Normalizasyonun teorik temeli **fonksiyonel bağımlılık** (functional dependency) kavramıdır. `A → B` bağımlılığı şu demektir: A'nın değerini bilirsem, B'nin değeri kesin olarak belirlenir. Örneğin `ogrenci_no → ogrenci_adi` doğrudur; bir öğrenci numarasını bilirsem adı tektir. Normal formlar, aslında bu bağımlılıkların tabloda "doğru yere" yerleştirilip yerleştirilmediğini denetleyen kurallardan ibarettir. Bu yüzden normalizasyonu ezberlenecek bir kurallar listesi değil, bağımlılıkları düzene sokan bir mantık zinciri olarak görmek gerekir.

## Anomali: Normalizasyonun Var Olma Sebebi

Normal formları anlamadan önce, onların hangi hastalığı tedavi ettiğini görmek gerekir. Kötü tasarlanmış tablolar üç tür **anomaliye** yol açar. Bu anomaliler soyut değildir; her biri gerçek üretim ortamında veri bozulması olarak karşımıza çıkar.

Aşağıdaki tablo, tek bir tabloda müşteri, ürün ve sipariş bilgisini birleştiren kötü bir tasarımı gösteriyor:

| siparis_no | musteri_adi | musteri_sehir | urun_adi | urun_fiyati |
|-----------|-------------|---------------|----------|-------------|
| 1001 | Ayşe Yılmaz | İstanbul | Klavye | 450 |
| 1002 | Ayşe Yılmaz | İstanbul | Fare | 200 |
| 1003 | Mehmet Kaya | Ankara | Klavye | 450 |

**Ekleme anomalisi** (insertion anomaly): Henüz hiç sipariş vermemiş yeni bir ürünü sisteme eklemek istediğinizde ne yaparsınız? Bu tabloda ürün, ancak bir siparişle birlikte var olabilir. Sipariş olmadan "Monitör" adlı ürünü kaydetmek istiyorsanız, `siparis_no` ve `musteri_adi` alanlarını boş bırakmak zorunda kalırsınız. Yani mevcut olmayan bir gerçeği (sipariş) uydurmadan yeni bir gerçeği (ürün) kaydedemezsiniz.

**Güncelleme anomalisi** (update anomaly): Klavyenin fiyatı 450'den 500'e çıktığında, bu değeri tabloda kaç yerde tekrarlandıysa o kadar satırda güncellemeniz gerekir. Örnekte klavye iki satırda geçiyor; ikisini de değiştirmeyi unutursanız, veritabanınız aynı ürün için iki farklı fiyat söyler. Bu, sistemin gördüğü "gerçeğin" hangi satırı okuduğunuza göre değişmesi demektir.

**Silme anomalisi** (deletion anomaly): Mehmet Kaya'nın 1003 numaralı siparişini iptal edip satırı sildiğinizde, farkında olmadan "Ankara'da Mehmet Kaya adlı bir müşteri olduğu" bilgisini de yok edersiniz. İki bağımsız gerçek aynı satırda yaşadığı için, birini silince diğeri de gider.

Bu üç anomali, normalizasyonun neden var olduğunu tek başına açıklar: **birbirinden bağımsız gerçekleri aynı satırda tuttuğumuz için, birinin yaşam döngüsü diğerini rehin alır.** Normal formlar, bu bağımsız gerçekleri ayrı tablolara taşıyarak birbirlerinden kurtarır.

## Birinci Normal Form (1NF): Atomiklik

1NF, en temel kuraldır ve şunu söyler: **her hücre tek ve bölünmez (atomik) bir değer içermelidir; tekrarlayan gruplar olmamalıdır.**

Bu kuralın kök nedeni, ilişkisel modelin matematiğidir. İlişkisel cebir, her hücrenin tek bir değer içerdiği varsayımı üzerine kuruludur. Bir hücreye virgülle ayrılmış birden fazla değer koyduğunuzda, `WHERE` koşulları, `JOIN`'ler ve indeksler bu değerlerin içine bakamaz; hücreyi tek bir metin bloğu olarak görür.

1NF'i ihlal eden klasik örnek, tek bir hücrede birden çok değer tutmaktır:

| siparis_no | urunler |
|-----------|---------|
| 1001 | Klavye, Fare, Mouse Pad |

Burada `urunler` sütunu atomik değildir. "1001 numaralı siparişte Fare var mı?" sorusunu verimli soramazsınız; metin içinde arama yapmak zorunda kalırsınız ki bu indekslenemez ve `LIKE '%Fare%'` gibi sorgular hem yavaştır hem hataya açıktır ("Fare" ile "Fareli Kalem" karışır). Doğru çözüm, her ürünü ayrı bir satıra taşımaktır:

| siparis_no | urun_adi |
|-----------|----------|
| 1001 | Klavye |
| 1001 | Fare |
| 1001 | Mouse Pad |

Dikkat edilmesi gereken bir tuzak: 1NF sadece "virgülle ayrılmış listeler" ile ilgili değildir. `adres1`, `adres2`, `adres3` gibi tekrarlayan sütun grupları da 1NF ihlalidir; sadece yatay yerine dikey tekrar yapmışsınızdır. Sabit sayıda tekrarlayan sütun, "kaç tane olacağını önceden bilme" varsayımına dayanır ve bu varsayım neredeyse her zaman er ya da geç çöker.

## İkinci Normal Form (2NF): Kısmi Bağımlılığın Ortadan Kaldırılması

2NF, ancak **bileşik anahtarı** (composite key, birden fazla sütundan oluşan birincil anahtar) olan tablolarda anlam kazanır. Kuralı şudur: tablo 1NF'te olmalı ve **anahtar olmayan her sütun, birincil anahtarın tamamına bağlı olmalıdır; anahtarın sadece bir parçasına değil.**

Bunun kök nedenini bir örnekle görelim. Bir sipariş kaleminde birincil anahtarın `(siparis_no, urun_no)` olduğunu düşünün:

| siparis_no | urun_no | adet | urun_adi | urun_fiyati |
|-----------|---------|------|----------|-------------|
| 1001 | K-01 | 2 | Klavye | 450 |
| 1001 | F-02 | 1 | Fare | 200 |
| 1002 | K-01 | 3 | Klavye | 450 |

Burada `adet` gerçekten anahtarın tamamına bağlıdır: hangi üründen hangi siparişte kaç tane alındığı ancak ikisini birlikte bilirsek belirlenir. Ancak `urun_adi` ve `urun_fiyati` yalnızca `urun_no`'ya bağlıdır; `siparis_no` ile hiçbir ilgileri yoktur. Yani `urun_no → urun_adi` bağımlılığı, anahtarın sadece bir parçasına yaslanır. Buna **kısmi bağımlılık** (partial dependency) denir.

Bunun sonucu doğrudan güncelleme anomalisidir: Klavye her siparişte tekrarlandığı için, fiyatı değiştirdiğinizde tüm satırları dolaşmanız gerekir. Çözüm, ürünle ilgili bilgiyi ayrı bir tabloya taşımaktır:

**siparis_kalemi** tablosu:

| siparis_no | urun_no | adet |
|-----------|---------|------|
| 1001 | K-01 | 2 |
| 1001 | F-02 | 1 |

**urun** tablosu:

| urun_no | urun_adi | urun_fiyati |
|---------|----------|-------------|
| K-01 | Klavye | 450 |
| F-02 | Fare | 200 |

Artık klavyenin fiyatı tek bir yerde yaşar. 2NF'in mantığını tek cümlede özetlersek: **bir olgu, kendisini belirleyen anahtarla aynı tabloda yaşamalıdır.** Ürün adı ürün numarasına aittir, o hâlde ürün tablosunda olmalıdır.

## Üçüncü Normal Form (3NF): Geçişli Bağımlılığın Ortadan Kaldırılması

3NF şunu söyler: tablo 2NF'te olmalı ve **anahtar olmayan hiçbir sütun, anahtar olmayan başka bir sütuna bağlı olmamalıdır.** Bu tür dolaylı bağımlılığa **geçişli bağımlılık** (transitive dependency) denir.

Geçişli bağımlılık şu zincirle oluşur: `anahtar → A → B`. Yani anahtar A'yı belirler, A da B'yi belirler; dolayısıyla B, anahtara doğrudan değil, A üzerinden dolaylı olarak bağlıdır. Örnek:

| calisan_no | calisan_adi | departman_no | departman_adi |
|-----------|-------------|--------------|---------------|
| E-1 | Ali | D-10 | Yazılım |
| E-2 | Veli | D-10 | Yazılım |
| E-3 | Zeynep | D-20 | Pazarlama |

Burada birincil anahtar `calisan_no`'dur ve `calisan_no → departman_no` doğrudur. Ancak `departman_adi`, aslında `departman_no`'ya bağlıdır: `departman_no → departman_adi`. Yani zincir şudur: `calisan_no → departman_no → departman_adi`. `departman_adi` çalışana değil, departmana aittir.

Sonuç yine tanıdık: "Yazılım" departmanının adı "Yazılım Geliştirme" olarak değişirse, o departmandaki her çalışan satırını güncellemeniz gerekir. Ayrıca içinde hiç çalışan olmayan bir departmanı (silme/ekleme anomalisi) kaydetmeniz imkânsızlaşır. Çözüm, departmanı ayrı tabloya çıkarmaktır:

**calisan** tablosu:

| calisan_no | calisan_adi | departman_no |
|-----------|-------------|--------------|
| E-1 | Ali | D-10 |
| E-2 | Veli | D-10 |

**departman** tablosu:

| departman_no | departman_adi |
|--------------|---------------|
| D-10 | Yazılım |
| D-20 | Pazarlama |

3NF'i akılda tutmak için pratik bir söz vardır: **"Her anahtar olmayan sütun, anahtara, tüm anahtara ve yalnızca anahtara bağlı olmalıdır."** Bu cümledeki üç vurgu tam olarak üç normal forma karşılık gelir: "anahtara" (1NF'in bir anahtar gerektirmesi), "tüm anahtara" (2NF, kısmi bağımlılık yok), "yalnızca anahtara" (3NF, geçişli bağımlılık yok).

### BCNF: 3NF'in Sıkılaştırılmış Hâli

3NF'in nadir ama gerçek bir açığı vardır: bir tabloda birden fazla **aday anahtar** (candidate key) örtüştüğünde 3NF bazı anomalileri yakalayamaz. **Boyce-Codd Normal Form (BCNF)**, "her belirleyici (determinant) bir aday anahtar olmalıdır" diyerek bu boşluğu kapatır. Pratikte çoğu tasarım 3NF'te zaten BCNF'i sağlar; ancak birden çok bileşik aday anahtarın çakıştığı özel durumlarda BCNF'e ihtiyaç duyulur. Çoğu uygulama için hedef 3NF/BCNF seviyesidir; daha yüksek formlar (4NF, 5NF) çok-değerli ve birleştirme bağımlılıklarını ele alır ve günlük tasarımda nadiren gündeme gelir.

## Denormalizasyon: Bilinçli Bir Takas

Normalizasyon yazma bütünlüğünü mükemmelleştirir, ama bunu okuma performansı pahasına yapar. Veriyi çok sayıda tabloya böldüğünüzde, bir raporu oluşturmak için bu tabloları tekrar `JOIN` ile birleştirmeniz gerekir. Çok tablolu `JOIN`'ler, özellikle büyük veri hacimlerinde ve yüksek okuma trafiğinde maliyetli olabilir.

**Denormalizasyon**, performans için bilinçli olarak biraz veri tekrarını geri getirmektir. Kritik nokta şudur: denormalizasyon, normalizasyonu *bilmemek* değildir; onu bilip, ölçülmüş bir performans sorununu çözmek için *bilinçli olarak* ihlal etmektir. Bu ayrım hayatidir. Tasarımı hiç normalize etmeden bırakmak bir kusurdur; normalize edip sonra ölçülü şekilde geri açmak bir mühendislik kararıdır.

### Denormalizasyonun Tipik Biçimleri

**Türetilmiş/önceden hesaplanmış değerler:** Bir siparişin toplam tutarını her seferinde kalemlerden `SUM` ile hesaplamak yerine `siparis` tablosunda `toplam_tutar` sütununda saklamak. Okuma hızlanır, ama artık kalem eklendiğinde/silindiğinde bu toplamı güncel tutma sorumluluğu size geçer.

**Sütun kopyalama (JOIN'den kaçınma):** Sık gösterilen `musteri_adi`'nı `siparis` tablosuna kopyalamak, böylece sipariş listesini gösterirken müşteri tablosuna `JOIN` atmaya gerek kalmaz. Bedeli: müşteri adı değişince bu kopyayı senkron tutmak.

**Özet/toplam tabloları:** Günlük satış toplamları gibi ağır analitik sorguların sonucunu ayrı bir özet tablosunda periyodik olarak biriktirmek. Bu genellikle raporlama ve OLAP dünyasında yıldız şeması (star schema) biçiminde bilinçli bir denormalizasyondur.

### Takasın İki Yüzü

Denormalizasyonun ne kazandırıp ne kaybettirdiğini net görmek gerekir:

**Kazanç:** Daha az `JOIN`, daha hızlı okuma, daha basit sorgular, bazen daha az CPU/IO.

**Bedel:** Geri gelen güncelleme anomalisi riski. Kopyalanan her veri parçası artık iki yerde yaşar ve bunları senkron tutmak *sizin* sorumluluğunuzdur. Bu senkronizasyonu genellikle uygulama kodu, trigger'lar veya periyodik toplu işler (batch job) üstlenir; her biri yeni karmaşıklık ve yeni hata yüzeyi ekler. Yazma işlemleri de yavaşlar, çünkü tek bir değişiklik artık birden çok yeri güncellemek zorundadır.

Bu takasın temel dengesi şudur: **normalizasyon yazmayı basit ve güvenli tutar, okumayı pahalılaştırır; denormalizasyon okumayı hızlandırır, yazmayı ve tutarlılığı sizin omuzunuza yükler.** Okuma ağırlıklı bir sistemde (örneğin bir haber sitesi) denormalizasyon mantıklıyken, yazma ağırlıklı ve tutarlılığın kritik olduğu bir sistemde (örneğin bankacılık) normalizasyondan taviz vermek tehlikelidir.

## Yaygın Hatalar

**"Her şeyi tek tabloda tutmak basittir" yanılgısı.** Başlangıçta tek büyük tablo (god table) hızlı görünür, ama anomaliler ilk gerçek güncellemeyle su yüzüne çıkar. Basitlik yanılsamadır; karmaşıklık ertelenmiştir, yok edilmemiştir.

**Erken denormalizasyon.** "İleride yavaş olur" korkusuyla, henüz ölçülmemiş bir sorun için tasarımı baştan denormalize etmek. Bu, olmayan bir hastalığa ilaç vermektir. Doğru yaklaşım önce normalize etmek, sonra gerçek bir performans darboğazı ölçüldüğünde ve hedeflenmiş şekilde denormalize etmektir.

**Denormalizasyonu senkronizasyon planı olmadan yapmak.** Bir sütunu kopyalayıp "kaynağı değiştiğinde kopyayı kim güncelleyecek?" sorusunu cevaplamamak, sessizce tutarsızlaşan verinin en yaygın nedenidir. Her denormalizasyon kararı, beraberinde bir senkronizasyon mekanizması *ve* onu doğrulayan bir kontrol gerektirir.

**1NF'i "liste yasak" olarak dar yorumlamak.** Modern PostgreSQL gibi sistemlerde `JSONB` veya dizi (array) tipleri vardır. Bunları kullanmak her zaman 1NF ihlali sayılmaz; eğer o yapının içine sorgu atmıyor, onu atomik bir bütün olarak (örneğin bir yapılandırma bloğu) kullanıyorsanız kabul edilebilir. Hata, ilişkisel olarak sorgulamanız gereken veriyi JSON içine gömüp sonra performansla boğuşmaktır.

**Doğal anahtarlara aşırı bağlanmak.** T.C. kimlik no gibi "gerçek dünya" anahtarları değişebilir ya da tekrar edebilir; birçok tasarımcı bu yüzden değişmez yapay anahtarlar (surrogate key, örneğin otomatik artan `id`) tercih eder. Bu normalizasyonun bir kuralı değildir ama tasarım sağlamlığı için sık başvurulan bir pratiktir.

## En İyi Pratikler

**Önce 3NF'i hedefleyin, sonra ölçün.** Neredeyse tüm işlemsel (OLTP) veritabanları için doğru başlangıç noktası 3NF'tir. Denormalizasyonu bir varsayılan değil, kanıta dayalı bir istisna olarak ele alın: gerçek bir sorgu yavaş olduğunda, profilleme ile darboğazı doğruladığınızda ve `JOIN`'in gerçekten suçlu olduğunu gördüğünüzde denormalize edin.

**Denormalizasyonu belgeleyin ve gerekçelendirin.** Kopyaladığınız her veri parçasının yanına, "bu neden burada, kaynağı nerede, nasıl senkron tutuluyor" bilgisini yazın. Belgelenmemiş bir denormalizasyon, altı ay sonra sizi bile şaşırtan bir tutarsızlığa dönüşür.

**Türetilmiş verinin güncelliğini otomatikleştirin.** Elle senkronizasyona güvenmeyin. Veritabanı trigger'ları, materialized view'lar veya iyi kapsüllenmiş bir veri erişim katmanı, kopyalanmış veriyi güncel tutmayı insan hatasından arındırır.

**Okuma ve yazma yüklerini ayırın.** Modern sistemlerde sık kullanılan bir desen, normalize edilmiş bir "yazma modeli" ile denormalize edilmiş bir "okuma modeli" tutmaktır (CQRS mantığı). Böylece iki dünyanın avantajını da alırsınız: yazma tarafı temiz ve güvenli, okuma tarafı hızlı kalır.

**Normal formları anlamları için öğrenin, isimleri için değil.** "3NF'te mi?" sorusundan çok "bu tabloda birbirine ait olmayan iki gerçek aynı satırda mı yaşıyor?" sorusunu sorun. Normal formlar bu sezginin resmileştirilmiş hâlidir; sezgiyi kazandığınızda kuralları çoğu zaman türetebilirsiniz.

## Özet

Normalizasyon, "her gerçek tek bir yerde yaşasın" ilkesini fonksiyonel bağımlılıklar üzerinden sistematikleştirir. 1NF atomikliği (hücrede tek değer), 2NF kısmi bağımlılığın (anahtarın parçasına bağlılık) kaldırılmasını, 3NF ise geçişli bağımlılığın (anahtar olmayan sütuna dolaylı bağlılık) kaldırılmasını sağlar. Bu formların ortak amacı ekleme, güncelleme ve silme anomalilerini önlemektir. Denormalizasyon ise bu bütünlüğün bir kısmını, ölçülmüş bir okuma performansı sorununu çözmek için bilinçli olarak takas eder; ama bu takasın bedeli, senkronizasyon sorumluluğunun ve tutarlılık riskinin tasarımcıya geçmesidir. Sağlam tasarımın özü, önce doğru şekilde normalize etmek, sonra yalnızca kanıtla denormalize etmektir.
