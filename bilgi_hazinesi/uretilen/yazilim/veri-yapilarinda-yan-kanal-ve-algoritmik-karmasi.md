# Veri Yapılarında Yan-Kanal ve Algoritmik Karmaşıklık Saldırıları

## Giriş: Karmaşıklık Analizi Neden Bir Güvenlik Konusudur

Standart bir Veri Yapıları ve Algoritmalar (DSA) müfredatı, karmaşıklık analizini genellikle *performans* meselesi olarak öğretir: "bu algoritma ortalama durumda O(n log n) çalışır, en kötü durumda O(n²)". Bu çerçeve, en kötü durumu nadir görülen, "şanssız" bir girdi olarak ele alır. Güvenlik mühendisliğinde ise bu varsayım çöker: bir saldırgan girdiyi *seçebiliyorsa*, en kötü durum artık istatistiksel bir kaza değil, hedef alınabilen bir zafiyettir. Bu sınıf saldırılara **Algorithmic Complexity Attack (ACA)** denir — sistemin kendi tasarım varsayımını (ortalama durum tipiktir) silah haline getirerek CPU, bellek veya zaman kaynağını tüketen bir Denial of Service (DoS) türüdür.

Bu makalenin kapsadığı üç somut örnek — hash flooding, quicksort'un O(n²)'ye düşürülmesi ve ReDoS (Regular Expression Denial of Service) — aynı kök nedenin farklı tezahürleridir: **girdiye bağımlı dallanma davranışı gösteren ve en kötü durumu ortalama durumdan çok daha pahalı olan bir algoritma, güvenilmeyen (untrusted) girdiyle beslendiğinde, karmaşıklık farkının kendisi bir saldırı yüzeyi haline gelir.** Yan-kanal (side-channel) boyutu ise bunun ikiz kardeşidir: aynı girdiye-bağımlı davranış, sadece kaynak tüketimini değil, *zamanlamayı* da sızdırabilir ve bu sızıntı gizli verinin (parola, kriptografik anahtar) çıkarılmasında kullanılabilir.

## Kök Neden: Ortalama Durum ile En Kötü Durum Arasındaki Uçurum

Bir algoritmanın güvenlik açısından tehlikeli olması için üç koşulun aynı anda sağlanması gerekir:

1. **Girdiye bağımlı performans**: Algoritmanın çalışma süresi veya bellek kullanımı, girdinin *değerine* (sadece boyutuna değil) bağlıdır.
2. **Saldırgan kontrolü**: Saldırgan, bu girdiyi kısmen veya tamamen kontrol edebilir (HTTP body, form alanı, dosya adı, JSON anahtarı, log satırı vb.).
3. **Büyük karmaşıklık farkı**: Ortalama durum ile en kötü durum arasındaki fark pratik olarak anlamlı (O(n) yerine O(n²), ya da O(n) yerine O(2ⁿ)).

Bu üç koşul birlikte var olduğunda, saldırgan küçük bir girdiyle orantısız derecede büyük bir işlem yükü tetikleyebilir — bu asimetri (asymmetric cost), DoS saldırılarının klasik tanımıdır: az kaynakla çok kaynak tüketmek.

Kritik nokta şudur: Bu bir "bug" değil, çoğu zaman **doğru çalışan, iyi test edilmiş kodun** yan etkisidir. Hash tablosu doğru hash'liyor, quicksort doğru sıralıyor, regex motoru doğru eşleştiriyor — sorun *doğruluk* değil, *öngörülemeyen maliyet dağılımı*dır.

## Hash Flooding: Hash Tablolarında Collision DoS

### Çalışma Mantığı

Hash tabloları, ortalama durumda O(1) ekleme/arama/silme sağlar; bu, hash fonksiyonunun anahtarları bucket'lara (veya açık adresleme slotlarına) *yaklaşık olarak eşit* dağıttığı varsayımına dayanır. Ancak birden fazla anahtar aynı hash değerine (veya aynı bucket indeksine) düşerse, bu bir **collision**'dır ve çoğu implementasyon collision'ları bir bağlı liste (chaining) veya prob dizisi ile çözer.

Saldırının özü şudur: eğer saldırgan, kullanılan hash fonksiyonunun *iç durumunu* (iyi bilinen, sabit bir seed kullanıyorsa) biliyorsa veya tahmin edebiliyorsa, hepsi aynı bucket'a düşecek şekilde tasarlanmış N tane anahtar üretebilir. Bu durumda hash tablosu, O(1) ortalama davranışından O(n) en kötü davranışa (chaining'de tek bir bucket'ta n elemanlı liste araması) düşer. N tane böyle anahtarı art arda eklemek toplamda O(n²) işlem gerektirir — normalde O(n) sürecek bir işlem.

Bunun klasik saldırı yüzeyi: web sunucularının HTTP POST body'sinde veya form-encoded/JSON verisinde gelen **anahtar isimlerini** (form alanı adları, JSON key'leri) bir hash tabloya (örn. `Dictionary`, `HashMap`, PHP associative array) koyduğu senaryodur. Saldırgan, aynı bucket'a çakışan binlerce form alanı adı içeren tek bir HTTP isteği gönderir; sunucu bu isteği parse ederken CPU'sunu tek çekirdekte tüketir ve tek bir istekle hizmet dışı kalabilir.

### Kök Neden — Neden Mümkün?

Klasik hash fonksiyonları (basit polinomsal hash'ler, eski `String.hashCode()` implementasyonları gibi) **deterministiktir ve seed'siz/sabit seed'lidir**. Yani aynı programın her çalıştırılışında aynı girdi için aynı hash çıkar. Bu, hash fonksiyonunun iç yapısı bilinen bir saldırgan için, ters mühendislik yaparak "hepsi çakışan" bir anahtar kümesi (collision kümesi) hesaplamayı *mümkün* kılar — bu tamamen offline yapılabilir, hedef sisteme dokunmadan.

### Savunma / Tespit

- **Keyed / randomized hashing (SipHash ve benzerleri)**: Modern dil çalışma zamanları (Python, Rust, Ruby, Java bir ölçüde, Go map'leri) hash fonksiyonuna işlem başına rastgele bir **seed** (secret key) katar. Bu, saldırganın collision kümesini süreç başlamadan önce hesaplamasını imkânsız hale getirir çünkü hash fonksiyonu artık deterministik değil, süreç-özel bir gizli anahtara bağlıdır. SipHash bu amaç için özellikle tasarlanmış, kriptografik olmayan ama DoS-dirençli bir keyed hash fonksiyonudur (kriptografik hash gibi çarpışma direnci hedeflemez, sadece tahmin edilemezlik hedefler).
- **Denge/dönüşüm stratejisi**: Java'nın `HashMap`'i, tek bir bucket'taki eleman sayısı bir eşiği (ör. 8) aştığında o bucket'ı bağlı listeden dengeli bir ağaca (red-black tree) dönüştürür; bu, en kötü durumu O(n)'den O(log n)'e indirir — kökten önlemez ama zarar tavanını düşürür.
- **Giriş boyutu sınırlama**: HTTP framework'lerinde form alanı/parametre sayısına üst sınır koymak (bazı framework'ler varsayılan olarak bunu yapar), saldırı yüzeyini n'in büyüklüğünü sınırlayarak daraltır.
- **Tespit**: Aşırı CPU tüketimiyle beraber tek bir isteğin/bağlantının anormal derecede uzun sürmesi, request boyutu küçükken işlem süresinin orantısız uzun olması (asimetrik maliyet imzası) izlenmesi gereken bir metriktir. WAF/rate-limiting katmanında "aynı bucket'a düşen çok sayıda anahtar" desenini tespit etmek zordur çünkü hash iç durumu uygulama katmanında saklıdır; bu yüzden savunma çoğunlukla *algoritma seviyesinde* olmalıdır, ağ katmanında değil.

### Yaygın Hatalar

- "Biz TLS kullanıyoruz, güvendeyiz" gibi yanlış bir güven aktarımı — hash flooding tamamen uygulama katmanı bir sorundur, ağ güvenliğiyle ilgisi yoktur.
- Kendi hash fonksiyonunu (ör. basit `sum(bytes) % table_size`) yazıp production'da kullanmak; bu fonksiyonlar hem çarpışma hem de tahmin edilebilirlik açısından zayıftır.
- Rastgele seed'i süreç her yeniden başladığında sabit tutmak (ör. test kolaylığı için "deterministic mode" bırakılması) — bu, savunmayı sessizce devre dışı bırakır.

## Quicksort'un O(n²)'ye Düşürülmesi: Pivot Seçimi Saldırısı

### Çalışma Mantığı

Quicksort'un ortalama karmaşıklığı O(n log n)'dir, ancak bu, pivot seçiminin diziyi *makul dengeli* iki alt parçaya böldüğü varsayımına dayanır. En kötü durum, her adımda pivotun ya en küçük ya da en büyük eleman olarak seçilmesidir; bu durumda bölme dengesiz olur (bir parça n-1 eleman, diğeri 0 eleman) ve rekürsiyon derinliği O(n)'e çıkar, toplam işlem O(n²) olur.

Klasik, naif pivot seçim stratejileri ("her zaman ilk eleman", "her zaman son eleman", "her zaman ortanca *indeks*") **deterministik ve girdiden önceden tahmin edilebilir**dir. Eğer saldırgan sıralama fonksiyonunun hangi pivot stratejisini kullandığını biliyorsa (kaynak kodu açık, ya da yaygın bir kütüphane implementasyonu), bu bilgiye dayanarak **özel olarak inşa edilmiş, zaten neredeyse-sıralı veya belirli bir desende olan bir girdi** üretebilir; bu girdi her adımda en kötü pivot bölünmesini tetikler. Bu, 2000'lerin başında bazı dillerin/kütüphanelerin standart kütüphane sort implementasyonlarına karşı gösterilen, halka açık bir saldırı sınıfıdır (ilk kez akademik literatürde "algorithmic complexity attacks" başlığı altında formelleştirilmiştir).

Pratik sonuç: n=100.000 gibi makul bir girdi boyutunda, O(n log n) beklenirken gerçek çalışma süresi O(n²)'ye sıçrar; bu, sunucu tarafı bir sıralama işlemini (ör. kullanıcı tarafından yüklenen bir CSV'yi sıralamak, bir API'de "sort by" parametresi) saatler süren bir işleme dönüştürebilir.

### Kök Neden

Sorunun temeli, **pivot seçiminin girdiden bağımsız rastgelelik içermemesi**dir. Deterministik pivot seçimi, saldırganın "kötü girdi" alanını offline hesaplayabilmesini sağlar çünkü algoritmanın karar ağacı tamamen öngörülebilirdir.

### Savunma / Tespit

- **Rastgele pivot seçimi (randomized quicksort)**: Pivotu diziden rastgele (kriptografik olması gerekmez, ancak öngörülemez bir PRNG ile) seçmek, saldırganın belirli bir kötü girdi tasarlamasını anlamsız hale getirir çünkü aynı girdi, farklı çalıştırmalarda farklı pivot dizileri üretir — saldırgan artık "en kötü durumu garantileyen" değil, sadece "en kötü durum olasılığını" etkileyen bir girdi tasarlayabilir, bu da saldırıyı pratik olarak anlamsızlaştırır.
- **Median-of-three / median-of-medians**: Pivotu ilk, orta ve son elemanın medyanı olarak seçmek bazı basit saldırı desenlerini engeller, ancak *tek başına* yeterli değildir — bu stratejiye özel olarak tasarlanmış kötü girdiler de literatürde gösterilmiştir. Rastgelelik olmadan hiçbir deterministik pivot stratejisi tam güvenlik sağlamaz.
- **Introsort (introspective sort) yaklaşımı**: Bu, gerçek dünyadaki en sağlam çözümdür. Rekürsiyon derinliği beklenen O(log n) sınırını (ör. 2·log₂(n)) aştığında, algoritma quicksort'tan **heapsort'a** geçer (heapsort'un garantili O(n log n) en kötü durumu vardır). Bu, "en kötü durumda dahi tavan garantisi" sağlayan bir hibrit stratejidir ve C++ STL `std::sort`, .NET `Array.Sort` gibi birçok modern standart kütüphane implementasyonunun temelini oluşturur.
- **Tespit**: Sıralama operasyonlarının süresini girdi boyutuna göre izlemek (beklenen n log n eğrisinden sapma), zaman aşımı (timeout) ve kaynak kotası (resource quota) koymak, kullanıcı kontrollü büyük veri kümelerinin sıralanmasını arka planda/izole kaynaklarda (sandbox, ayrı worker, CPU limiti olan konteyner) çalıştırmak.

### Yaygın Hatalar

- Kendi "hızlı" sıralama fonksiyonunu yazıp pivotu her zaman ilk/son eleman olarak sabitlemek — eğitim amaçlı kodlarda çok yaygın, üretimde tehlikeli.
- "Biz zaten standart kütüphane kullanıyoruz, güvendeyiz" varsayımı — kullanılan dilin/sürümün *hangi* stratejiyi kullandığını (introsort mu, saf quicksort mu) doğrulamadan bu varsayımı yapmak risklidir.
- Kullanıcı girdisini doğrudan büyük ölçekte sıralamaya sokup girdi boyutuna veya işlem süresine üst sınır koymamak.

## ReDoS: Catastrophic Backtracking ile Regex'i Silahlandırmak

### Çalışma Mantığı

Çoğu genel amaçlı regex motoru (PCRE, Python `re`, JavaScript, Java `Pattern` vb.) **backtracking tabanlı** çalışır: motor, deseni girdi üzerinde denerken bir alternatifin başarısız olduğu noktada geri dönüp (backtrack) başka bir eşleşme yolunu dener. Bu yaklaşım regex dilini çok esnek (geri referanslar, lookahead/lookbehind gibi) kılar, ama **üstel zaman karmaşıklığına** açık kapı bırakır.

Klasik "tehlikeli desen" ailesi, **iç içe veya bitişik nicelik belirteçleridir (nested/adjacent quantifiers)**: örneğin `(a+)+$` veya `(a|aa)+$` gibi bir desen düşünün. Böyle bir desende, girdideki her `a` karakteri dizisini *birden fazla farklı şekilde* iç ve dış gruplara bölüştürmek mümkündür (ör. "aaa" dizisi iç gruba (a)(a)(a) olarak da, (aa)(a) olarak da, (aaa) olarak da bölünebilir). Girdi regex'i **tam olarak eşleştirmediğinde** (ör. sonunda eşleşmeyi bozan bir karakter varsa, `$` demirlemesi tutmuyorsa), motor bu bölüştürme kombinasyonlarının **hepsini** dener — kombinasyon sayısı girdi uzunluğuyla üstel olarak büyür (yaklaşık O(2ⁿ)).

Saldırı senaryosu tipik olarak şudur: bir web uygulaması kullanıcı girdisini (e-posta doğrulama, log satırı ayrıştırma, URL parse etme gibi) "zararsız görünen" bir regex ile doğrular; regex yazarı, deseni normal/geçerli girdilerle test eder ve sorun görmez çünkü geçerli girdilerde backtracking gerekmez (desen hemen eşleşir). Ancak saldırgan, deseni **kasıtlı olarak eşleşmeyen** ama neredeyse-eşleşen bir girdi (ör. `"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!"` — yani $30$ tane 'a' ardından eşleşmeyi bozan bir karakter) gönderir; bu, motoru üstel backtracking'e sürükler ve tek bir istek tüm işlemi (çoğu zaman tek-thread'li event loop mimarilerinde — ör. Node.js — tüm sunucuyu) tıkar.

### Kök Neden

Kök neden, backtracking motorunun **belirsiz (ambiguous) gramerler için üstel arama alanı** taşımasıdır. Deterministik olmayan sonlu otomat (NFA) tabanlı backtracking motorları, bir girdinin desene *birden fazla farklı şekilde* uyup uymadığını ayırt edemediğinde tüm yolları dener. Regex yazarının niyeti "bu karakterlerden bir ya da daha fazlası" iken, iç içe `+`/`*` kullanımı yanlışlıkla "bu alt-deseni farklı şekillerde gruplamanın tüm yolları" anlamına gelen bir belirsizlik yaratır.

### Savunma / Tespit

- **Desen incelemesi (statik analiz)**: İç içe nicelik belirteçlerinden kaçınmak — `(a+)+`, `(a*)*`, `(a|a)*`, `(a|ab)*` gibi desenler kırmızı bayraktır. Bir alt grup zaten bir nicelik belirteci taşıyorsa, onu saran dış nicelik belirteci genellikle gereksiz belirsizlik yaratır.
- **Atomic grouping / possessive quantifiers**: Bazı regex motorları (PCRE, Java) `(?>...)` (atomic group) veya `a++` (possessive quantifier) sözdizimini destekler; bunlar motora "bu grup için bir kez eşleştikten sonra asla geri backtrack yapma" der. Bu, belirsizliği kaynağında keser.
- **Linear-time / non-backtracking motorlar**: RE2 (Google) ve Rust'ın `regex` crate'i gibi kütüphaneler, backtracking yerine **Thompson NFA simülasyonu** kullanarak girdi uzunluğuyla *doğrusal* zaman garantisi verir (geri referans gibi bazı ileri özelliklerden feragat ederek). Girdi güvenilmeyen kaynaklardan geliyorsa, bu motorları tercih etmek en sağlam yapısal çözümdür.
- **Zaman aşımı / adım sınırı**: Regex motoruna bir çalışma süresi veya "adım sayısı" bütçesi koymak (birçok modern regex kütüphanesi bunu destekler); bu, kökten önlemez ama zarar tavanını sınırlar.
- **Test/tarama araçları**: Regex desenlerini canlıya almadan önce catastrophic backtracking için otomatik tarayan statik analiz araçları ve fuzzing yaklaşımları (desene "neredeyse eşleşen ama eşleşmeyen" uzun girdiler besleyerek çalışma süresini gözlemlemek) code review sürecine dahil edilmelidir.
- **Tespit (runtime)**: Belirli bir endpoint'te CPU kullanımının girdi boyutuyla orantısız şekilde sıçraması, event-loop tabanlı sunucularda (Node.js gibi) tek bir isteğin event loop'u bloke ettiğinin gözlemlenmesi (diğer tüm isteklerin aynı anda yavaşlaması) tipik bir ReDoS imzasıdır.

### Yaygın Hatalar

- Regex'i sadece "geçerli" test girdileriyle test edip "geçersiz ama neredeyse geçerli" girdilerle test etmemek — ReDoS tam olarak bu kör noktada saklanır.
- Kullanıcıdan gelen regex desenlerinin kendisini çalıştırmak (ör. "arama filtresi" özelliği kullanıcının kendi regex'ini yazmasına izin veriyorsa) — bu durumda saldırgan hem deseni hem girdiyi kontrol eder, saldırı yüzeyi ikiye katlanır.
- Üçüncü parti kütüphanelerden (ör. e-posta/URL doğrulama için kopyala-yapıştır regex'ler) gelen desenleri sorgulamadan güvenmek; bazı yaygın "e-posta doğrulama regex'leri" tarihsel olarak ReDoS'a açık bulunmuştur.

## Ortak İplik: Zamanlama Yan-Kanalı Boyutu

Yukarıdaki üç örnek doğrudan kaynak tüketimi (DoS) üzerine odaklanır, ama aynı kök mekanizmanın ikinci bir yüzü vardır: **girdiye bağımlı çalışma süresi, kaynak tüketmese bile bilgi sızdırabilir.** Bir algoritmanın çalışma süresi gizli bir değere (ör. karşılaştırılan bir parola, bir kriptografik anahtarın biti) bağlıysa, dışarıdan ölçülebilen bu süre farkı bir **timing side-channel**'dır.

Klasik örnek: iki byte dizisini karşılaştırırken ilk farklı byte'ta erken çıkan (`return false` diyen) naif bir `equals()` fonksiyonu. Bu, karşılaştırma için ortalama durumda hızlıdır (iyi bir optimizasyon gibi görünür) ama doğru byte'ları adım adım tahmin etmeye çalışan bir saldırgan, "doğru prefiks ne kadar uzunsa fonksiyon o kadar (mikrosaniyeler mertebesinde) daha uzun sürer" farkını istatistiksel olarak ölçerek, karşılaştırılan gizli değeri (ör. bir HMAC imzası veya API anahtarı) byte byte çıkarabilir. Bu yüzden kriptografik karşılaştırmalarda **sabit zamanlı karşılaştırma (constant-time comparison)** kullanılır: fonksiyon, sonucu ne olursa olsun *her zaman* tüm byte'ları gezer ve girdiye bağlı erken çıkış yapmaz.

Aynı mantık veri yapılarına da uzanır: bir hash tablosunda arama süresi (collision zincirinin uzunluğuna bağlı), bir ağaçta arama derinliği (dengesiz bir ağaçta belirli anahtarlara erişim süresi farklı), hatta bir cache'in hit/miss davranışı (CPU cache timing side-channel'ları, ör. Spectre/Meltdown ailesi saldırıların temelini oluşturan mikro-mimari yan kanallar) gizli bilgiyi zamanlama farkı üzerinden sızdırabilir. Prensip birdir: **eğer bir işlemin süresi kısmen gizli bir değere bağlıysa ve saldırgan bu süreyi yeterli hassasiyetle ölçebiliyorsa, süre kendisi bir kanal (channel) olur.**

### Savunma İlkesi

Zamanlama yan-kanallarına karşı genel savunma stratejisi, **girdiden/gizli değerden bağımsız sabit davranış** sağlamaktır: sabit zamanlı karşılaştırma, sabit zamanlı arama (branch'siz veya her durumda aynı sayıda işlem yapan implementasyonlar), gerektiğinde yapay gecikme (jitter/blinding) eklemek. Ancak jitter eklemek kesin bir çözüm değildir — yeterli sayıda ölçüm istatistiksel olarak gürültüyü ortalayıp gerçek sinyali yine ortaya çıkarabilir; asıl sağlam çözüm algoritmanın *kendisini* girdiden bağımsız sabit-zamanlı tasarlamaktır.

## Savunma Mimarisi: Katmanlı Yaklaşım

Tek bir "gümüş kurşun" yoktur; sağlam bir savunma şu katmanları birleştirir:

1. **Algoritma seviyesi (kök neden düzeltmesi)**: Randomize edilmiş hash seed'leri, randomize edilmiş/introspective pivot seçimi, backtracking'den kaçınan veya sınırlanan regex motorları, sabit-zamanlı kriptografik karşılaştırmalar. Bu katman en etkilisidir çünkü saldırı yüzeyini *matematiksel olarak* daraltır.
2. **Kaynak kotası ve zaman aşımı**: Her işleme (bir istek, bir regex eşleştirme, bir sıralama) üst sınır koymak — "en kötü durum ne kadar sürerse sürsün, sistem çökmeden önce kesilir" garantisi.
3. **İzolasyon**: Güvenilmeyen girdiyle çalışan hesaplamaları (kullanıcı regex'i çalıştırma, büyük kullanıcı verisini sıralama) ayrı bir worker/process/konteynerde, sınırlı CPU/bellek kotasıyla çalıştırmak; bu, bir tek isteğin tüm sunucuyu (özellikle tek-thread'li mimarilerde) kilitlemesini önler.
4. **İzleme ve anomali tespiti**: Girdi boyutu ile işlem süresi arasındaki beklenen ilişkiden (ör. beklenen O(n log n) eğrisi) sapmaları izlemek; asimetrik maliyet imzası (küçük girdi, büyük CPU/süre) bir erken uyarı sinyalidir.
5. **Kod incelemesi ve statik analiz**: Yeni regex desenlerini, özel veri yapısı implementasyonlarını, kullanıcı girdisiyle beslenen karşılaştırma fonksiyonlarını bu mercekten (girdiye bağımlı dallanma var mı, en kötü durum nedir, saldırgan bu en kötü durumu tetikleyebilir mi) gözden geçirmek.

## Sonuç

Algorithmic complexity attacks ve zamanlama yan-kanalları, güvenlik ile performans mühendisliğinin kesiştiği bir alanı temsil eder: bir algoritmanın "ortalama durumda hızlı" olması, güvenilmeyen girdiyle çalışırken yeterli bir güvence değildir. Güvenlik odaklı bir mühendis için doğru soru her zaman şudur: *"Bu algoritmanın en kötü durumu nedir, ve bir saldırgan bu en kötü durumu tetikleyecek bir girdi üretebilir mi?"* Hash tablolarında rastgele seed'leme, sıralamada rastgele/introspective pivot stratejileri, regex motorlarında backtracking kontrolü ve kriptografik karşılaştırmalarda sabit zamanlı işlemler — hepsi aynı disiplinin farklı uygulamalarıdır: **girdiye bağımlı en kötü durumu, saldırganın erişemeyeceği bir rastgelelik veya yapısal garanti ile örtmek.** Bu disiplin, DSA öğreniminin "Big-O yeterlidir" varsayımının ötesine geçmeyi ve karmaşıklık analizini bir tehdit modeli parçası olarak görmeyi gerektirir.
