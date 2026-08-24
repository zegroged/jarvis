# Ağaçlar: BST, Dengeli Ağaçlar ve B-Tree

Ağaç veri yapıları, bilgisayar biliminin en temel taşlarından biridir. Bir dizinin doğrusal yapısını kırıp hiyerarşik bir düzen kurdukları için, arama, ekleme ve silme işlemlerini logaritmik zamana indirmenin en yaygın yolunu sunarlar. Bu makale, arama ağaçlarını (BST) temelden ele alıp dengeli ağaçlara (AVL, Red-Black) ve nihayet veritabanı indekslerinin bel kemiği olan B-Tree / B+ Tree yapılarına kadar uzanan bir yolculuk sunuyor. Her adımda sadece "ne olduğunu" değil, "neden böyle tasarlandığını" ve "nasıl yanlış kullanıldığını" da açıklamaya çalışacağım.

## Binary Search Tree (BST): Temel

### Tanım

Binary Search Tree (ikili arama ağacı), her düğümün en fazla iki çocuğu (sol ve sağ) olan ve şu değişmez kurala (invariant) uyan bir ağaçtır: bir düğümün sol alt ağacındaki tüm anahtarlar (key) o düğümün anahtarından küçük, sağ alt ağacındaki tüm anahtarlar ise büyüktür. Bu kural, ağacın her düzeyinde geçerlidir; yani sadece doğrudan çocuklar için değil, tüm alt ağaç için tutar.

Bu tek kural, ağaca bir "arama" niteliği kazandırır. Kökten başlayıp aradığınız anahtarı düğümdekiyle karşılaştırdığınızda, gitmeniz gereken yönü (sol mu sağ mı) tek bir kıyaslamayla belirleyebilirsiniz. Bu, ikili aramanın (binary search) ağaç üzerindeki karşılığıdır.

### Kök neden: neden logaritmik?

BST'nin cazibesi, her karşılaştırmada arama uzayını yarıya bölebilme potansiyelinden gelir. Dengeli bir ağaçta n düğüm varsa, ağacın yüksekliği yaklaşık log₂(n) olur. Dolayısıyla arama, ekleme ve silme işlemleri ortalama O(log n) zamanda tamamlanır. Bir milyon elemanlı dengeli bir ağaçta bir anahtarı bulmak için yaklaşık 20 karşılaştırma yeterlidir.

Ancak burada kritik bir kelime var: "potansiyel". BST bu dengeyi kendiliğinden garanti etmez. Ağacın şeklini tamamen ekleme sırası belirler. Verileri sıralı olarak eklerseniz (örneğin 1, 2, 3, 4, 5...), her yeni eleman hep sağa gider ve ağaç bir bağlı listeye (linked list) dönüşür. Bu durumda yükseklik O(n) olur ve tüm avantaj kaybolur. İşte dengeli ağaçların doğuş sebebi tam olarak budur: sıradan bir BST'nin bu dejenerasyona karşı hiçbir savunması yoktur.

### Somut örnek

Şu anahtarları bu sırayla ekleyelim: 50, 30, 70, 20, 40, 60, 80.

```
        50
       /  \
     30    70
    / \    / \
   20 40  60 80
```

Burada 40'ı aradığımızda: 50 ile karşılaştır (40 < 50, sola git), 30 ile karşılaştır (40 > 30, sağa git), 40'ı bulduk. Üç karşılaştırma. Şimdi aynı verileri sıralı ekleseydik (20, 30, 40, 50, 60, 70, 80), sağa doğru uzayan bir zincir elde eder ve 80'i bulmak için 7 karşılaştırma yapardık. Aynı veriler, tamamen farklı performans.

### In-order dolaşım: gizli bir güç

BST'nin sıklıkla göz ardı edilen bir özelliği in-order dolaşımdır (sol alt ağaç, kök, sağ alt ağaç sırasıyla ziyaret). Bu dolaşım, BST'nin değişmezi gereği anahtarları her zaman artan sıralı olarak verir. Bu yüzden bir BST aynı zamanda "sıralı bir koleksiyon" olarak da düşünülebilir; aralık sorguları (range query), en küçük/en büyük eleman, ardıl (successor) ve öncül (predecessor) bulma gibi işlemler bu yapıdan doğal olarak akar. Hash tablolarının veremediği tam da bu sıralılıktır ve ağaçların hash'lere karşı ayakta kaldığı temel sebeplerden biridir.

## Dengeli Ağaçlar: AVL ve Red-Black

Sıradan BST'nin dejenerasyon problemine çözüm, ağacı her değişiklikten sonra yeniden dengeleyen kendini dengeleyen (self-balancing) ağaçlardır. Buradaki temel araç rotasyondur (rotation): ağacın in-order sırasını (yani BST değişmezini) bozmadan yerel şeklini değiştiren, sabit sayıda pointer güncellemesiyle yapılan O(1) bir işlem. Sol rotasyon ve sağ rotasyon, dengeleme mekanizmalarının yapı taşıdır.

### AVL Ağaçları

#### Tanım ve çalışma mantığı

AVL ağacı (adını mucitleri Adelson-Velsky ve Landis'ten alır), her düğüm için katı bir denge koşulu dayatır: bir düğümün sol ve sağ alt ağaçlarının yükseklik farkı en fazla 1 olabilir. Bu farka "denge faktörü" (balance factor) denir ve -1, 0 veya +1 değerlerini alabilir.

Bir ekleme ya da silme bu koşulu bozduğunda, AVL ağacı yolun üzerinde yukarı çıkarak dengesizliği yakalar ve bir ya da iki rotasyonla düzeltir. Dört temel dengesizlik durumu vardır: sol-sol, sağ-sağ (tek rotasyonla çözülür) ve sol-sağ, sağ-sol (çift rotasyonla çözülür). Bu katı koşul sayesinde AVL ağacının yüksekliği her zaman yaklaşık 1.44 × log₂(n) sınırının altında kalır.

#### Neden bu kadar katı?

AVL'nin felsefesi şudur: dengeyi olabildiğince sıkı tut ki aramalar mümkün olan en sığ ağaçta gerçekleşsin. Bu, arama-ağırlıklı (read-heavy) iş yükleri için idealdir çünkü daha sığ ağaç, daha az karşılaştırma demektir. Bedeli ise şudur: sıkı denge, ekleme ve silmede daha çok yeniden dengeleme ve dolayısıyla daha çok rotasyon gerektirir.

### Red-Black Ağaçları

#### Tanım

Red-Black (kırmızı-siyah) ağacı, dengeyi renklerle kodlanmış bir kurallar kümesiyle sağlayan bir BST'dir. Her düğüm kırmızı veya siyah olarak işaretlenir ve şu değişmezler tutar:

- Kök her zaman siyahtır.
- Kırmızı bir düğümün çocukları siyah olmalıdır (yani art arda iki kırmızı düğüm olamaz).
- Herhangi bir düğümden ona bağlı yaprak (null) düğümlere giden her yol, aynı sayıda siyah düğüm içerir (buna "siyah yükseklik" / black-height denir).

#### Kök neden: bu kurallar dengeyi nasıl sağlıyor?

İlk bakışta bu renk kuralları keyfî görünür. Ama arkasındaki mantık zariftir. "Siyah yükseklik her yolda eşit" kuralı, en kısa yol ile en uzun yol arasındaki oranı sınırlar. En kısa olası yol tümüyle siyah düğümlerden oluşur; en uzun olası yol ise siyah-kırmızı-siyah-kırmızı şeklinde alternans yapar ve "iki kırmızı yan yana olamaz" kuralı yüzünden en fazla iki katı uzun olabilir. Sonuç: en uzun yol, en kısa yolun en fazla iki katıdır. Bu da yüksekliği 2 × log₂(n+1) sınırında tutar.

Red-Black ağacı AVL'ye göre daha "gevşek" dengelenir. Yüksekliği biraz daha fazla olabilir, ama yeniden dengeleme için gereken rotasyon sayısı daha azdır; bir eklemede en fazla 2, bir silmede en fazla 3 rotasyon yeter (renk değişiklikleri yolda yukarı yayılabilse de rotasyonlar sabittir).

#### AVL mi, Red-Black mi?

Bu, pratikte en sık karşılaşılan tasarım sorularından biridir ve cevap iş yüküne bağlıdır:

- **AVL**: daha sıkı dengeli, daha sığ ağaç. Aramaların ekleme/silmeye baskın olduğu durumlarda daha hızlıdır.
- **Red-Black**: daha az yeniden dengeleme. Ekleme ve silmenin sık olduğu, mutasyon-ağırlıklı (write-heavy) durumlarda daha az iş yapar.

Pratikte çoğu genel amaçlı standart kütüphane Red-Black ağacını tercih eder. Örneğin C++ standart kütüphanesindeki `std::map` ve `std::set`, Java'daki `TreeMap` ve `TreeSet` tipik olarak Red-Black ağaç üzerine kuruludur. Bunun sebebi, gerçek dünyadaki karışık iş yüklerinde Red-Black'in daha iyi bir ortalama ödünleşim (trade-off) sunması ve yeniden dengeleme maliyetinin daha öngörülebilir olmasıdır. Linux çekirdeği de zamanlayıcı ve bellek yönetimi gibi yerlerde Red-Black ağacını yoğun kullanır.

## B-Tree ve B+ Tree: Diskin Ağacı

### İkili ağaçların diskteki problemi

AVL ve Red-Black ağaçları bellekte (RAM) mükemmel çalışır. Ama veritabanı indeksleri gibi milyarlarca kaydı diskte (ya da SSD'de) tutmanız gereken durumlarda bu ikili ağaçlar acımasızca yavaştır. Sebebini anlamak, B-Tree'nin neden var olduğunu anlamaktır.

Kök neden şudur: **disk erişimi, bellek erişiminden mertebelerce yavaştır.** Bir dönen diskte rastgele bir okuma milisaniye mertebesindeyken, RAM erişimi nanosaniye mertebesindedir; aradaki fark yüz binlerce kattır. Dahası, disk veriyi bayt bayt değil, sabit boyutlu bloklar (block) ya da sayfalar (page) halinde okur; tipik bir sayfa 4 KB, 8 KB ya da 16 KB'dir. Bir baytı okumak için de tüm sayfayı getirirsiniz.

Şimdi problemi görelim: bir milyar elemanlı Red-Black ağacının yüksekliği yaklaşık 60'tır. Bu, kötü senaryoda 60 disk erişimi demektir; çünkü her düğüm ayrı bir sayfada olabilir. 60 disk okuması, saniyeler sürebilir. Bir indeks lookup'ının milisaniyeler içinde bitmesi gereken bir dünyada bu kabul edilemez.

### B-Tree'nin çözümü: geniş ve sığ ağaç

B-Tree'nin fikri dâhice basittir: eğer disk zaten koca bir sayfayı tek seferde getiriyorsa, o sayfaya iki değil yüzlerce anahtar sığdıralım. B-Tree, her düğümü bir disk sayfasına denk gelecek şekilde tasarlanmış çok yollu (multi-way) bir arama ağacıdır. Her düğüm onlarca hatta yüzlerce anahtar ve buna karşılık gelen çocuk pointer'ları tutar.

Bir düğümün sahip olabileceği çocuk sayısına ağacın "derecesi" (order) ya da dallanma faktörü (branching factor) denir. Dallanma faktörü çok yüksek olduğu için ağaç son derece sığ kalır. Örneğin dallanma faktörü 100 olan bir B-Tree'de üç seviye (100³ = bir milyon), dört seviye ise yüz milyonlarca anahtarı adresler. Bu, bir kaydı bulmak için sadece 3-4 disk erişimi demektir; ikili ağacın 60'ına karşı devrim niteliğinde bir kazanç.

### B-Tree'nin değişmezleri

B-Tree, dengesini rotasyonlarla değil, düğüm bölme (split) ve birleştirme (merge) işlemleriyle korur ve şu kurallara uyar:

- Kök hariç her düğüm en az yarı doludur (minimum doluluk kuralı). Bu, ağacın boşa yer harcamamasını ve dengeli kalmasını sağlar.
- Tüm yapraklar aynı derinliktedir. B-Tree "aşağıdan yukarı" büyür; kök bölündüğünde ağacın yüksekliği artar. Bu yüzden her zaman mükemmel dengelidir.
- Bir düğümün içindeki anahtarlar sıralıdır ve çocuk pointer'ları anahtarlar arasındaki aralıkları işaret eder.

Bir ekleme sırasında bir düğüm taşarsa (overflow), ortadaki anahtar üst düğüme (parent) çıkarılır ve düğüm ikiye bölünür. Bu bölme yukarı doğru yayılabilir; en tepede kök bölünürse yeni bir kök oluşur ve ağaç bir seviye yükselir.

### B-Tree ile B+ Tree farkı

Bu ayrım, veritabanı mühendisliğinin kalbindedir ve çoğu kişinin karıştırdığı bir noktadır.

**B-Tree**: Anahtarlar ve onlara bağlı gerçek veriler (ya da veriye pointer) hem iç düğümlerde (internal node) hem de yapraklarda bulunabilir. Bir anahtarı iç düğümde bulursanız aramayı orada bitirirsiniz.

**B+ Tree**: Tüm gerçek veriler (ya da veri pointer'ları) sadece yaprak düğümlerde tutulur. İç düğümler yalnızca yönlendirme (routing) için kullanılan anahtarların kopyalarını içerir; veri taşımazlar. Ayrıca yaprak düğümler birbirlerine bir bağlı liste ile zincirlenmiştir.

#### B+ Tree neden veritabanlarında kazanır?

B+ Tree'nin bu iki tasarım kararı, veritabanları için belirleyicidir:

1. **İç düğümler veri taşımadığı için daha çok anahtar sığdırırlar.** Bu, dallanma faktörünü artırır ve ağacı daha da sığ yapar. Daha sığ ağaç, daha az disk erişimi demektir.

2. **Yapraklar zincirlenmiş olduğu için aralık taramaları (range scan) çok verimlidir.** `WHERE age BETWEEN 25 AND 40` gibi bir sorguda, alt sınırın bulunduğu yaprağa inersiniz, sonra yaprak zincirini takip ederek üst sınıra kadar yatay olarak yürürsünüz. Ağaçta yukarı-aşağı zıplamaya gerek kalmaz. Sıralı okuma (sequential scan), diskin en iyi yaptığı şeydir; işte bu yüzden B+ Tree tam sıralı sorgular ve `ORDER BY` için idealdir.

Bu iki sebepten dolayı, gerçek dünyadaki neredeyse tüm ilişkisel veritabanı indeksleri (ve birçok NoSQL depolama motoru) B+ Tree kullanır; saf B-Tree değil.

## Veritabanı İndeksi Bağı

### İndeks nedir ve neden bir ağaçtır?

Bir veritabanı tablosunda `WHERE email = 'ahmet@ornek.com'` sorgusu çalıştırdığınızda, indeks yoksa veritabanı tüm tabloyu satır satır taramak (full table scan) zorunda kalır; milyonlarca satır için bu O(n) bir işlemdir. İndeks, tam olarak bu problemi çözmek için o sütun üzerine kurulan bir B+ Tree'dir. İndeks sayesinde arama O(log n)'e iner; milyonlarca satırlık tabloda bile birkaç sayfa okumasıyla sonuca ulaşılır.

İndeksin ağaç olması tesadüf değildir. Hash indeksleri de vardır ve tam eşitlik (`=`) sorgularında B+ Tree'den bile hızlı olabilirler. Ama hash indeksleri sıralılık koruyamadıkları için aralık sorgularını (`>`, `<`, `BETWEEN`), sıralamayı (`ORDER BY`) ve önek aramalarını (`LIKE 'abc%'`) destekleyemezler. B+ Tree'nin sıralı yaprak zinciri tam da bu yeteneği verir. Bu yüzden çoğu veritabanının varsayılan indeks türü B+ Tree'dir.

### Clustered ve Non-Clustered indeks

Burada önemli bir kavramsal ayrım var:

- **Clustered index (kümelenmiş indeks)**: Tablonun satırları fiziksel olarak indeksin sıralamasına göre diskte saklanır. Yani B+ Tree'nin yaprakları doğrudan satırların kendisidir. Bir tabloda yalnızca bir clustered index olabilir çünkü veriyi fiziksel olarak yalnızca bir şekilde sıralayabilirsiniz. Örneğin bazı veritabanı motorlarında (InnoDB gibi) primary key otomatik olarak clustered index'tir.

- **Non-clustered index (ikincil indeks / secondary index)**: B+ Tree'nin yaprakları satırın kendisini değil, satıra ulaşmak için bir işaretçi (primary key değeri ya da satır kimliği) tutar. Bu yüzden ikincil indeksle bir arama yaptığınızda önce indeks ağacına, sonra satırı almak için ikinci bir yapıya (genellikle clustered index'e) bakılır; buna ikili arama ya da "bookmark lookup" denir.

Bu ayrımı anlamak, indeks tasarımının neden zor olduğunu açıklar. Bir sorgunun ihtiyaç duyduğu tüm sütunlar indeksin içinde bulunuyorsa (covering index / kapsayan indeks), veritabanı satırın kendisine hiç gitmeden sadece indeksten cevap verebilir; bu ciddi bir hızlanmadır.

## Yaygın Hatalar ve Tuzaklar

### BST'yi dengeli sanmak

En sık yapılan kavramsal hata, "ikili arama ağacı O(log n)'dir" diye ezberleyip bunun her zaman doğru olduğunu varsaymaktır. Değildir. Sıradan bir BST'ye sıralı veri eklerseniz O(n)'e düşer. Üretimde gerçek bir arama ağacına ihtiyacınız varsa, ya kendi kendini dengeleyen bir yapı (AVL/Red-Black) kullanın ya da dilinizin standart kütüphanesindeki dengeli haritayı tercih edin. Kendi elinizle yazdığınız naif BST'yi kritik yola koymayın.

### İndeksi her yere eklemek

İndeksler bedava değildir. Her indeks, her `INSERT`, `UPDATE` ve `DELETE` işleminde güncellenmek zorundadır; çünkü B+ Tree'nin yeniden dengelenmesi gerekir. Bir tabloya on tane indeks eklerseniz, yazma işlemleriniz belirgin şekilde yavaşlar ve disk alanı şişer. İndeks, okumayı hızlandırırken yazmayı yavaşlatan bir ödünleşimdir. Kural: gerçekten sorgulanan sütunlara indeks koyun, "belki lazım olur" diye değil.

### Yanlış sütun sırasıyla bileşik indeks

Bileşik (composite / multi-column) bir indeks `(a, b, c)` üzerine kuruluysa, bu indeks `WHERE a = ?` ve `WHERE a = ? AND b = ?` sorgularında kullanılabilir ama `WHERE b = ?` (a olmadan) sorgusunda genellikle kullanılamaz. Buna "en soldaki önek" (leftmost prefix) kuralı denir ve arkasındaki sebep basittir: indeks önce a'ya, sonra b'ye, sonra c'ye göre sıralanmıştır; tıpkı bir telefon rehberinin önce soyada, sonra ada göre sıralanması gibi. Soyadını bilmeden sadece adla arama yapamazsınız. Bu yüzden bileşik indekslerde sütun sırası, en seçici ve en sık filtrelenen sütunların önce gelmesine göre dikkatle seçilmelidir.

### Fonksiyon uygulanan sütunda indeks kaybı

`WHERE YEAR(tarih) = 2024` gibi bir sorgu, `tarih` sütununda indeks olsa bile onu kullanamaz; çünkü indeks ham `tarih` değerlerine göre sıralanmıştır, `YEAR(tarih)` sonucuna göre değil. Veritabanı her satırda fonksiyonu çalıştırmak zorunda kaldığından full scan'e döner. Çözüm, sorguyu indeksi kullanacak şekilde yeniden yazmak (`WHERE tarih >= '2024-01-01' AND tarih < '2025-01-01'`) ya da ifade indeksi (functional index) oluşturmaktır.

### Silme işleminin karmaşıklığını hafife almak

Dengeli ağaçlarda ve B-Tree'lerde silme, eklemeden çok daha karmaşıktır. Bir B-Tree'de bir düğüm minimum doluluğun altına düşerse (underflow), ya kardeş düğümden anahtar ödünç alınır (borrow) ya da kardeşle birleştirilir (merge), bu da yukarı doğru yayılabilir. Kendi ağaç yapısını yazan çoğu geliştirici silme mantığını yanlış yapar. Mümkünse test edilmiş bir kütüphane kullanın.

## En İyi Pratikler

**Doğru aracı seçin.** Eğer sadece hızlı anahtar-değer erişimi istiyorsanız ve sıralılığa ihtiyacınız yoksa, hash tablosu ağaçtan hızlıdır (ortalama O(1)). Sıralı erişim, aralık sorgusu, en yakın komşu ya da min/max gerekiyorsa ağaç seçin. Diskte büyük veri indeksliyorsanız B+ Tree'yi tercih edin. Bellekte dengeli bir sıralı harita gerekiyorsa standart kütüphanenin Red-Black tabanlı yapısını kullanın.

**Kendi dengeli ağacınızı yazmayın (üretimde).** Öğrenmek için AVL veya Red-Black yazmak paha biçilmez bir egzersizdir ve şiddetle tavsiye edilir. Ama üretim kodunda, on yıllardır test edilmiş standart kütüphane yapılarını kullanın. Denge mantığındaki tek bir kenar durum (edge case) hatası, sessizce bozuk bir ağaç ve zor yakalanan performans regresyonları üretir.

**İndeksleri ölçerek ekleyin.** Bir indeksin gerçekten işe yarayıp yaramadığını tahmin etmeyin; sorgu planlayıcısının (query planner) çıktısını inceleyin. Çoğu veritabanı `EXPLAIN` benzeri bir komut sunar; bu komut sorgunun indeksi kullanıp kullanmadığını, full scan mı yoksa index seek mi yaptığını gösterir. İndeks eklemeden önce ve sonra bu çıktıyı karşılaştırın.

**Sayfa boyutu ve dallanma faktörünün farkında olun.** B-Tree performansının anahtarı düğüm boyutunun disk sayfa boyutuyla hizalanmasıdır. Anahtarlar ne kadar küçükse, bir sayfaya o kadar çok anahtar sığar, dallanma faktörü o kadar yüksek olur ve ağaç o kadar sığ kalır. Bu yüzden çok geniş (örneğin uzun metin) sütunlar üzerine indeks kurmak, dar sayısal sütunlara göre çok daha az verimlidir.

**Yazma-okuma dengesini düşünün.** Arama-ağırlıklı sistemlerde sıkı dengeli yapılar (AVL, çok indeksli tablolar) mantıklıdır. Yazma-ağırlıklı sistemlerde ise fazla indeks ve fazla sıkı denge bir yüktür; hatta bazı modern sistemler B-Tree yerine LSM-Tree (Log-Structured Merge Tree) gibi yazma-optimize yapıları tercih eder. Doğru veri yapısı her zaman iş yükünüzün şeklinden çıkar.

## Kapanış

Bu makalede gördüğümüz zincir aslında tek bir problemin evrimidir: "sıralı veriyi verimli aramak". Sıradan BST bu problemi bellekte çözer ama dengesizliğe savunmasızdır. AVL ve Red-Black, rotasyonlarla dengeyi garanti ederek bu açığı kapatır. B-Tree ve B+ Tree ise problemi bellekten diske taşıyıp dallanma faktörünü şişirerek disk erişimini minimize eder ve böylece modern veritabanı indekslerinin temelini oluşturur. Her yapının kendine has bir ödünleşimi vardır ve mühendisliğin özü, bu ödünleşimleri iş yükünüze göre bilinçli seçmektir. Ezber değil, "neden" bilgisi doğru kararı verdirir.
