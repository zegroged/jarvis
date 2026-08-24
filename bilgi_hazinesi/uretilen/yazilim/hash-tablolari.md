# Hash Tabloları Derinlemesine

## Giriş ve Tanım

Hash tablosu (hash table, bazı dillerde hash map, dictionary veya associative array), anahtar–değer (key–value) çiftlerini saklayan ve ortalama durumda sabit zamanlı — yani `O(1)` — arama, ekleme ve silme sunan bir veri yapısıdır. Bir sözlükteki kelimeye anlamıyla ulaşmak gibi, elinizdeki anahtarı doğrudan bir bellek konumuna eşleyerek değere erişirsiniz. Bu "doğrudan eşleme" işini yapan matematiksel fonksiyona **hash fonksiyonu** denir.

Temel fikir şudur: elimizde bir dizi (array) vardır ve `hash(anahtar) mod N` işlemiyle her anahtarı bu dizinin `0` ile `N-1` arasındaki bir indeksine (bucket, kova) yerleştiririz. Diziye erişim zaten `O(1)` olduğu için, eğer hash fonksiyonu anahtarları düzgün dağıtıyorsa, aradığımız değeri neredeyse tek adımda buluruz.

Ancak burada gizli bir gerilim vardır ve bu makalenin çekirdeği tam olarak budur: **sonsuz sayıda olası anahtarı, sonlu sayıda kovaya sığdırmaya çalışıyoruz.** Bu matematiksel olarak imkânsız bir birebir eşlemedir. Kaçınılmaz olarak iki farklı anahtar aynı kovaya düşer. Bu duruma **çakışma (collision)** denir ve hash tablolarının tüm mühendislik inceliği, bu çakışmaları nasıl yönettiğinizde saklıdır.

## Kök Neden: Çakışmalar Neden Kaçınılmazdır?

Çakışmaların neden var olduğunu anlamak için Güvercin Yuvası İlkesi'ni (Pigeonhole Principle) hatırlamak yeterlidir: `N` yuvanız ve `N`'den fazla güverciniz varsa, en az bir yuvaya iki güvercin düşmek zorundadır. Hash tablosunda anahtar uzayı (örneğin tüm olası string'ler) pratikte sonsuzdur, kova sayısı ise sonludur. Dolayısıyla çakışma bir "hata" değil, sistemin doğasında var olan bir gerçekliktir.

İşin sezgiye aykırı yanı, çakışmaların düşündüğünüzden çok daha erken ortaya çıkmasıdır. Burada **Doğum Günü Paradoksu (Birthday Paradox)** devreye girer. 365 günlük bir yılda, yalnızca 23 kişilik bir grupta iki kişinin aynı gün doğmuş olma olasılığı yüzde 50'yi geçer. Benzer şekilde, `N` kovalı bir tabloda çakışma beklentisi, tablo dolmaya yakın değil, kabaca `√N` civarında eleman eklediğinizde belirginleşir. Bu yüzden "tablom yarı bile dolu değil, çakışma olmaz" varsayımı baştan yanlıştır.

Buradan çıkan pratik sonuç: iyi bir hash tablosu çakışmayı **önlemeye** değil, çakışmayı **ucuza yönetmeye** odaklanır. İki temel strateji vardır: zincirleme ve açık adresleme.

## Çakışma Çözümü — Zincirleme (Chaining)

Zincirlemede her kova aslında bir değer değil, bir **bağlı listenin (linked list) başıdır**. Aynı kovaya düşen tüm anahtarlar o listeye eklenir. Arama yaparken önce hash ile doğru kovayı bulur, sonra o kovadaki kısa listeyi tarayarak anahtarı ararsınız.

### Neden Çalışır ve Ne Zaman Bozulur

Zincirlemenin güzelliği kavramsal basitliğidir: tablo "dolamaz", çünkü her kova istediği kadar uzayabilir. Silme işlemi de temizdir — listeden bir düğümü çıkarırsınız, başka hiçbir yeri etkilemez.

Fakat performansı tamamen zincirlerin kısa kalmasına bağlıdır. Eğer `M` eleman ve `N` kova varsa, ortalama zincir uzunluğu `M/N` olur; bu orana **load factor (doluluk oranı)** denir ve genellikle `α` ile gösterilir. Ortalama arama maliyeti `O(1 + α)`'dır. `α` küçük kaldığı sürece bu pratik olarak sabit zamandır. Ama `α` büyürse — diyelim 10'a çıkarsa — her arama ortalama 10 düğüm gezmek anlamına gelir ve `O(1)` vaadi çöker.

En kötü durum ise şudur: kötü bir hash fonksiyonu (veya birazdan göreceğimiz kasıtlı bir saldırı) tüm anahtarları **tek bir kovaya** yığarsa, hash tablosu dejenere olur ve `O(n)` karmaşıklıkta bir bağlı listeye dönüşür. Sabit zaman vaadi bir anda doğrusal zamana düşer.

### İyileştirilmiş Zincirleme

Modern bazı implementasyonlar, bir kovadaki zincir belirli bir eşiği aştığında, o bağlı listeyi bir dengeli ikili arama ağacına (örneğin kırmızı-siyah ağaç) dönüştürür. Böylece en kötü durumda bile kova içi arama `O(log k)` olur, `O(k)` değil. Java'nın `HashMap` implementasyonu bu yaklaşımı benimseyerek, çakışma bazlı saldırılara karşı bir savunma katmanı ekler. Bu, birazdan tartışacağımız DoS riskinin doğrudan bir azaltıcısıdır.

## Çakışma Çözümü — Açık Adresleme (Open Addressing)

Açık adreslemede bağlı liste yoktur; her şey doğrudan dizinin içinde saklanır. Bir anahtarın gitmesi gereken kova doluysa, belirli bir **sonda (probing)** kuralına göre başka bir boş kova aranır. Bu yaklaşıma "açık adresleme" denmesinin nedeni, bir elemanın nihai adresinin yalnızca hash'ine değil, tablonun o anki doluluk durumuna da bağlı ("açık") olmasıdır.

### Sondalama Stratejileri ve Kök Mantığı

**Doğrusal sondalama (linear probing):** Kova doluysa bir sonrakine, o da doluysa bir sonrakine bakılır (`h`, `h+1`, `h+2`, ...). Uygulaması en basit ve CPU önbelleği (cache) açısından en dosttur, çünkü ardışık bellek konumlarına erişir. Ancak **birincil kümelenme (primary clustering)** sorunu vardır: dolu hücreler uzun ardışık bloklar oluşturmaya eğilimlidir ve bu bloklar birbirini besler; sonda mesafeleri kötüleşir.

**Karesel sondalama (quadratic probing):** Adım aralıkları karesel olarak büyür (`h+1`, `h+4`, `h+9`, ...). Birincil kümelenmeyi kırar, ama **ikincil kümelenme (secondary clustering)** kalır: aynı ilk hash'e sahip anahtarlar aynı sonda dizisini izler.

**Çift hash'leme (double hashing):** Sonda adımı ikinci bir hash fonksiyonuyla belirlenir. Her anahtar farklı bir sonda "ritmi" izlediği için kümelenme büyük ölçüde ortadan kalkar. Dağıtım kalitesi en iyisidir, ama iki hash hesaplaması ve daha zayıf cache davranışı bedeliyle gelir.

### Açık Adreslemenin Kritik Zayıflığı: Silme

Açık adreslemede silme sinsi bir tuzaktır. Bir hücreyi silip "boş" işaretlerseniz, o hücrenin arkasındaki sonda zincirini koparırsınız. Örneğin `A`, `B`, `C` sırayla sondalanarak yerleşmişse ve ortadaki `B`'yi boşaltırsanız, `C`'yi ararken boş hücreye rastlayıp "yok" diye erken durabilirsiniz — hâlbuki `C` oradadır.

Bu yüzden açık adreslemede silinen hücreler genellikle özel bir **tombstone (mezar taşı)** işaretiyle işaretlenir: "burası artık boş ama sonda zincirini kırma, arayışa devam et" anlamına gelir. Tombstone'lar zamanla birikir, tabloyu şişirir ve aramaları yavaşlatır; bu yüzden periyodik olarak tablonun yeniden inşası (rehash) gerekebilir. Bu, açık adreslemenin gizli bakım maliyetidir.

Ayrıca açık adreslemede `α` **asla 1'i geçemez**, çünkü eleman sayısı kova sayısını aşamaz. Uygulamada performans, `α` daha 0.7–0.8'e ulaşmadan hızla bozulmaya başlar; çünkü tablo dolduça boş kova bulmak giderek pahalılaşır.

## Load Factor — Performansın Gizli Kadranı

Load factor `α = M/N`, hash tablosunun kalp atışıdır. İki temel maliyet arasında bir denge (trade-off) ayarlar:

- **Düşük `α` (örn. 0.3):** Az çakışma, hızlı işlemler, ama çok boş kova — yani **bellek israfı**.
- **Yüksek `α` (örn. 0.9):** Yoğun bellek kullanımı, ama sık çakışma ve yavaş işlemler.

Bu yüzden implementasyonlar bir **eşik load factor** belirler ve `α` bu eşiği aştığında **yeniden boyutlandırma (resizing / rehashing)** yapar: genellikle kova sayısını iki katına çıkarır ve tüm elemanları yeni tabloya yeniden hash'ler.

### Rehashing Neden Pahalıdır ama Yine de "Ucuzdur"

Rehashing sırasında tüm `M` eleman yeniden hesaplanıp taşınır; bu tek seferlik `O(M)` maliyettir. Buradan çıkan kritik nokta: bir tek `insert` işlemi en kötü durumda `O(M)` sürebilir. O hâlde nasıl `O(1)` diyoruz?

Cevap **amortize edilmiş analiz (amortized analysis)** kavramındadır. Boyutu ikiye katlama stratejisi sayesinde, pahalı rehash işlemleri giderek daha seyrek olur (`N`, `2N`, `4N` ... eşiklerinde). Toplam maliyet, yapılan işlem sayısına bölündüğünde işlem başına sabit bir değere yakınsar. Yani bireysel bir ekleme bazen pahalı olsa da, **ortalama** ekleme maliyeti `O(1)`'dir. Bu, gerçek zamanlı (real-time) sistemler için önemli bir uyarıdır: hash tablosunun genel throughput'u mükemmel olsa da, tek bir işlemin gecikme (latency) sıçraması yapması, düşük-gecikme garantisi gereken senaryolarda kabul edilemez olabilir.

Tipik eşik değerleri şöyledir: zincirleme için `α ≈ 0.75` yaygın bir varsayılandır; açık adresleme için genellikle daha muhafazakâr bir değer (0.5–0.7) tercih edilir, çünkü açık adreslemede performans dolulukla çok daha keskin bozulur.

## Somut Örnek: Adım Adım Bir Ekleme ve Çakışma

Diyelim ki `N = 8` kovalı bir zincirleme tablomuz var ve basitleştirilmiş bir hash fonksiyonu kullanıyoruz.

```
hash("elma")  = 143 -> 143 mod 8 = 7  -> kova 7
hash("armut") = 201 -> 201 mod 8 = 1  -> kova 1
hash("kiraz") = 79  -> 79  mod 8 = 7  -> kova 7  (ÇAKIŞMA!)
```

`"elma"` ve `"kiraz"` aynı kovaya (7) düşüyor. Zincirlemede kova 7 artık iki düğümlü bir liste tutar: `[elma] -> [kiraz]`. `"kiraz"` aramak istediğimizde önce `hash("kiraz") mod 8 = 7` ile kovayı buluruz, sonra listede gezip anahtarı **tam olarak** karşılaştırarak (çünkü hash aynı olsa da anahtarlar farklı) doğru düğümü buluruz.

Aynı senaryo açık adreslemede (doğrusal sonda) şöyle işlerdi: `"kiraz"` kova 7'yi dolu bulur, `(7+1) mod 8 = 0`'a bakar, boşsa oraya yerleşir. Artık `"kiraz"` fiziksel olarak kova 0'da yaşar, ama mantıksal olarak 7'ye aittir. Bu ayrım, silme ve arama mantığını neden dikkatli kurmak gerektiğini açıklar.

## Güvenlik: Hash Flooding ve Algoritmik Karmaşıklık DoS Saldırısı

Şimdi bu makalenin en önemli güvenlik konusuna geliyoruz. Hash tablosunun tüm `O(1)` vaadi tek bir varsayıma dayanır: **anahtarlar kovalara düzgün dağılır.** Peki ya bir saldırgan bu varsayımı kasıtlı olarak bozarsa?

### Kök Neden: Öngörülebilir Hash

Birçok programlama dilinin standart string hash fonksiyonu, tarihsel olarak **deterministik ve gizli olmayan** bir algoritmaydı. Yani saldırgan, kullanılan hash fonksiyonunu bilerek, hepsi **aynı kovaya** düşecek binlerce farklı anahtar hesaplayabilir. Bu tür anahtarlara **collision (çakışma) anahtarları** denir.

Saldırgan bu anahtarları bir HTTP isteğinin form alanlarına, JSON gövdesine, query string parametrelerine ya da HTTP başlıklarına doldurup sunucuya gönderir. Sunucu bunları otomatik olarak bir hash tablosuna (örneğin request parametre sözlüğüne) eklemeye çalışır. Normalde `O(1)` olması gereken her ekleme, hepsi tek kovaya düştüğü için `O(k)` olur; `k` eleman eklemenin toplam maliyeti `O(k²)`'ye fırlar.

### Neden Yıkıcıdır

Sayılarla düşünelim: normalde 10.000 anahtar eklemek 10.000 işlem alır. Çakışma saldırısında ise bu, kabaca 10.000² = 100 milyon işlem düzeyine çıkar. Tek bir küçük HTTP isteği, tek bir CPU çekirdeğini saniyelerce meşgul edebilir. Yeterli sayıda böyle istek, sunucuyu tamamen kilitleyerek bir **Denial of Service (DoS)** oluşturur. Bunun adı **algoritmik karmaşıklık saldırısı (algorithmic complexity attack)** ya da yaygın adıyla **hash flooding**'dir.

Bu saldırının sinsiliği, klasik DoS'tan farklı olmasıdır: devasa trafik hacmi gerektirmez. Küçük ama kötü niyetle üretilmiş bir yük (payload), asimetrik biçimde büyük bir CPU maliyeti yaratır. Yani saldırgan az kaynakla savunmacıya çok pahalıya patlatır.

2011 yılı civarında bu sınıf saldırı geniş çapta gündeme geldi ve birçok popüler web çatısı ile dilin (PHP, Java, Python, Ruby, ASP.NET ve diğerleri) varsayılan hash tablosu implementasyonlarının bu saldırıya açık olduğu gösterildi. Bu, o dönem birden fazla dil ve platformu etkileyen koordineli bir güvenlik açığı bildirimine yol açtı. (Burada belirli bir CVE numarası vermekten kaçınıyorum, çünkü bu tek bir zafiyet değil, birçok üründe ayrı ayrı numaralandırılan bir açık sınıfıdır; kavram numaradan daha önemlidir.)

### Savunma: Anahtarlanmış (Keyed) ve Rastgeleleştirilmiş Hash

Ana savunma, hash fonksiyonunu **öngörülemez** hâle getirmektir. Bunun iki katmanı vardır:

**1. Hash seed rastgeleleştirmesi (randomization):** Program her başladığında rastgele, gizli bir tohum (seed) üretir ve hash hesabına bu tohumu karıştırır. Saldırgan tohumu bilmediği için, hepsi tek kovaya düşecek anahtarları önceden hesaplayamaz. Python bu savunmayı bir ortam değişkeni aracılığıyla hash rastgeleleştirmesi olarak sunmaya başlamış ve modern sürümlerde bunu varsayılan davranış hâline getirmiştir.

**2. Kriptografik olarak güçlü, anahtarlanmış hash:** Basit rastgele tohum bazı zayıf hash fonksiyonlarında yine kırılabilir. Daha sağlam çözüm, gizli bir anahtar alan ve tersine mühendisliğe dirençli olacak şekilde tasarlanmış bir hash algoritması kullanmaktır. Bu amaçla geliştirilen **SipHash**, kısa girdiler için hızlı olması ve anahtarlı (keyed) yapısıyla tam olarak hash flooding'e karşı tasarlanmıştır. Bugün birçok dil ve çalışma zamanı (örneğin Rust'ın standart `HashMap`'i ve Python) string anahtarları için SipHash ya da benzeri anahtarlanmış bir yapıyı varsayılan olarak kullanır.

Ek olarak, daha önce bahsettiğimiz **kova içi ağaçlaştırma** (zinciri en kötü durumda `O(log k)`'ya indirmek) da ikinci bir savunma hattı sağlar: saldırgan çakışmayı zorlasa bile maliyet karesel değil, log'lu olur.

### Uygulamada Ne Yapmalı

- Kullanıcıdan gelen **kontrolsüz girdiyi** doğrudan hash tablosu anahtarı yapıyorsanız, altta yatan implementasyonun rastgeleleştirilmiş/anahtarlanmış bir hash kullandığından emin olun.
- Kabul edilecek maksimum anahtar/parametre sayısına bir **üst sınır** koyun. Birçok web çatısı, tam da bu saldırı sonrası, tek istekte işlenebilecek parametre sayısına varsayılan bir tavan getirdi. Böylece `O(k²)` bile olsa `k` sınırlıdır.
- Güvenlik açısından kritik yollarda, kullanıcı girdisini anahtar olarak kullanan hash tablolarının worst-case davranışını bilerek tasarım yapın.

## Yaygın Hatalar ve Tuzaklar

**Zayıf ya da elle yazılmış hash fonksiyonu kullanmak.** İyi bir hash fonksiyonu tüm bit'leri "karıştırır" (avalanche etkisi: girdideki tek bir bit değişikliği çıktının yarısını değiştirmeli). Naif bir "karakterleri topla" hash'i, anagram'ları aynı kovaya düşürür ve dağılımı berbat eder. Kendi hash fonksiyonunuzu icat etmek yerine, kütüphanenin kanıtlanmış fonksiyonunu kullanın.

**`hashCode`/`equals` sözleşmesini bozmak.** Nesneleri anahtar olarak kullanan dillerde altın kural şudur: iki nesne eşitse (`equals`), hash değerleri de **kesinlikle** eşit olmalıdır. Bunu ihlal ederseniz, eklediğiniz nesneyi geri bulamazsınız — çünkü arama önce hash'e göre kovayı bulur, yanlış kovaya bakar ve nesne "kaybolur". Bunun tersi (eşit hash ama eşit olmayan nesneler) sadece çakışmadır ve normaldir.

**Değişebilir (mutable) nesneleri anahtar yapmak.** Bir nesneyi tabloya ekledikten sonra hash'ini etkileyen bir alanını değiştirirseniz, nesne yanlış kovada "sıkışıp kalır". Onu artık bulamazsınız çünkü yeni hash'i başka bir kovayı işaret eder. Anahtarlar mümkün olduğunca **immutable** olmalıdır.

**Load factor'ı görmezden gelmek ve önceden boyut ayırmamak.** Kaç eleman ekleyeceğinizi biliyorsanız, tabloyu baştan yeterli kapasiteyle oluşturun. Aksi hâlde büyüme sırasında defalarca rehash yaşarsınız; her biri tüm elemanları yeniden taşır. Küçük başlayıp milyonlarca eleman eklemek, gereksiz onlarca rehash demektir.

**Sıra (ordering) varsaymak.** Klasik bir hash tablosu ekleme sırasını korumaz ve rehash sonrası kova dağılımı değişebilir. İterasyon sırasına güvenen kod, farklı çalıştırmalarda (özellikle hash rastgeleleştirmesi açıkken) farklı davranır ve bu, yakalanması zor hatalara yol açar. Sıra gerekiyorsa, sırayı koruyan bir varyant (örneğin insertion-ordered map) kullanın.

**Açık adreslemede tombstone yönetimini atlamak.** Silmeyi "hücreyi boşalt" olarak uygularsanız, sonda zincirlerini kırar ve var olan elemanları "kayıp" yaparsınız. Tombstone mantığı olmadan açık adreslemede silme neredeyse her zaman hatalıdır.

## En İyi Pratikler

**Kanıtlanmış standart kütüphaneyi kullanın.** Modern dillerin yerleşik hash tablosu implementasyonları; iyi hash fonksiyonu, otomatik yeniden boyutlandırma, çakışma çözümü ve çoğunlukla DoS koruması gibi onlarca yıllık mühendislik birikimini içerir. Özel bir gereksinim olmadıkça kendi hash tablonuzu yazmayın.

**Anahtarları immutable seçin.** String, sayı ve değişmez değer nesneleri ideal anahtarlardır. Anahtar olarak kullanılan bir nesnenin hash'ini etkileyen durumunu, tabloda dururken asla değiştirmeyin.

**Güvenlik sınırındaki hash tablolarını sertleştirin.** Kullanıcı kontrolündeki veriyi anahtar yapan her yerde: rastgeleleştirilmiş/anahtarlanmış hash kullanan bir implementasyon seçin, girdi boyutuna tavan koyun ve mümkünse worst-case'i `O(log n)`'e sınırlayan ağaçlaştırılmış çakışma çözümünü tercih edin.

**Load factor'ı iş yüküne göre ayarlayın.** Bellek boldu ve hız kritikse düşük eşik seçin; bellek kısıtlıysa dengeyi kabul edin. Çok büyük ve boyutu tahmin edilebilir koleksiyonlarda önceden kapasite ayırarak rehash fırtınalarını önleyin.

**Doğru varyantı seçin.** Cache dostluğu ve bellek yoğunluğu kritikse, kısa değerli, sık okunan tablolarda açık adresleme genellikle daha hızlıdır. Sık silme, büyük değerler ya da öngörülemez büyüme varsa zincirleme daha güvenlidir ve daha az sürprizlidir. Karar, "hangisi daha iyi" değil, "benim erişim örüntüm ne" sorusunun cevabıdır.

**Gecikme hassas sistemlerde amortize maliyete dikkat edin.** Ortalama `O(1)` mükemmeldir, ama rehash anındaki `O(M)` sıçraması gerçek zamanlı bir sistemde bir kaçırılmış deadline anlamına gelebilir. Bu tür sistemlerde ya kapasiteyi önceden ayırın ya da artımlı (incremental) rehash yapan bir yapı tercih edin.

## Özet

Hash tablosu, sonlu belleğe sonsuz anahtar uzayını sığdırma pazarlığının zarif bir çözümüdür ve gücünü tek bir varsayımdan alır: iyi dağıtılmış hash. Çakışmalar kaçınılmazdır; onları zincirleme ya da açık adreslemeyle yönetiriz. Load factor, hız ile bellek arasındaki kadranı ayarlar ve amortize edilmiş yeniden boyutlandırma sayesinde ortalama maliyeti sabit tutar. En kritik ders ise güvenliktedir: `O(1)` vaadi, anahtarların düzgün dağıldığı varsayımına dayanır ve bir saldırgan bu varsayımı hash flooding ile kasıtlı olarak bozarak performansı `O(n²)`'ye çökertebilir. Bu yüzden modern implementasyonlar rastgeleleştirilmiş, anahtarlanmış hash fonksiyonları (örneğin SipHash) ve worst-case'i sınırlayan ağaçlaştırma gibi savunmalarla gelir. Hash tablosunu gerçekten anlamak, onun ortalama durumdaki hızını değil, kötü durumdaki davranışını ve o durumu kimin tetikleyebileceğini anlamaktır.
