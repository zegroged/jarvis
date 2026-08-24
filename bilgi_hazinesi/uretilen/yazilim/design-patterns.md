# Tasarım Kalıpları (Design Patterns)

## Tanım

Tasarım kalıbı (design pattern), yazılım tasarımında sık karşılaşılan bir soruna karşı, zamanla test edilmiş, tekrar tekrar uygulanabilir bir çözüm şablonudur. Kalıp bir kütüphane ya da hazır kod parçası değildir; belirli bir bağlamda hangi sınıfların, nesnelerin ve sorumlulukların nasıl düzenlenmesi gerektiğini tarif eden bir *fikir*, bir *reçete*dir. Aynı kalıp Java'da, C#'ta, Python'da veya Go'da bambaşka satırlarla hayata geçebilir; ortak olan şey, çözümün yapısal iskeletidir.

Kavram 1994'te dört yazarın ("Gang of Four", GoF) yayımladığı *Design Patterns: Elements of Reusable Object-Oriented Software* kitabıyla popülerleşti. Bu kitap 23 kalıbı üç aileye ayırdı: **creational** (yaratımsal), **structural** (yapısal) ve **behavioral** (davranışsal). Bu üçlü ayrım hâlâ referans çerçevesidir ve bu makalenin de omurgasıdır.

Kalıpların asıl değeri koddan çok iletişimdedir. "Burada bir Observer kullandım" cümlesi, bir ekip arkadaşına onlarca satırlık açıklama yapmadan tasarım niyetini aktarır. Yani kalıplar, mühendisler arasında ortak bir kelime dağarcığı (shared vocabulary) oluşturur.

## Kök Neden: Kalıplar Neden Var?

Bir kalıbın neden var olduğunu anlamadan onu doğru kullanmak mümkün değildir. Her GoF kalıbının arkasında tek bir temel gerilim yatar: **değişime karşı direnç.** Yazılım yaşayan bir şeydir; gereksinimler değişir, yeni tipler eklenir, davranışlar farklılaşır. Kötü tasarlanmış kodda küçük bir değişiklik dalga dalga yayılır ve onlarca yeri kırar. Kalıplar tam da bu yayılmayı sınırlamak için icat edilmiştir.

GoF'un kitabın girişinde vurguladığı iki ilke bu gerilimi yönetir:

1. **"Program to an interface, not an implementation."** Somut sınıflara değil, soyutlamalara (interface / abstract type) bağımlı ol. Böylece somut sınıf değiştiğinde ona bağlı kodun değişmesi gerekmez.
2. **"Favor object composition over class inheritance."** Kalıtım (inheritance) yerine bileşimi (composition) tercih et. Kalıtım derleme zamanında sabitlenir ve sıkı bağ (tight coupling) yaratır; bileşim ise çalışma zamanında esneklik verir.

Neredeyse tüm kalıplar bu iki ilkenin somut uygulamalarıdır. Örneğin Strategy kalıbı, bir davranışı kalıtımla alt sınıflara gömmek yerine, o davranışı ayrı bir nesneye (interface arkasında) taşıyarak "composition over inheritance" ilkesini uygular. Bunu bilmek, kalıbı ezberlemekten çok daha kalıcıdır: kalıbın adını unutsanız bile, hangi problemi çözdüğünü hatırlarsınız.

İkinci bir kök neden **bağımlılığın yönüdür** (dependency direction). İyi tasarımda üst seviye (business logic) alt seviye ayrıntıya (veritabanı, dosya, ağ) bağımlı olmaz; ikisi de soyutlamaya bağımlı olur. Factory, Abstract Factory ve Dependency Injection gibi yaratımsal teknikler tam olarak bu yön çevirmeyi (dependency inversion) mümkün kılmak için vardır. Nesnenin *nasıl* yaratıldığını, onu *kullanan* koddan ayırırlar.

## Creational (Yaratımsal) Kalıplar

Yaratımsal kalıplar tek bir soruyla ilgilenir: **nesneler nasıl ve nerede yaratılmalı?** Kulağa basit gelir, ama `new SomutSinif()` ifadesini kodun her yerine serpiştirmek en yaygın kırılganlık kaynaklarından biridir. Çünkü `new` ile bir somut sınıfa doğrudan bağ kurarsınız; o sınıfın adı değişse, yapıcısına (constructor) yeni bir parametre eklense ya da onun yerine bir alt tip kullanmak isteseniz, tüm çağrı noktalarını tek tek düzeltmeniz gerekir. Yaratım mantığını tek bir yere toplamak, bu bağı gevşetir.

### Factory Method ve Abstract Factory

**Factory Method**, nesne yaratımını bir metoda devreder ve alt sınıfların "hangi somut ürünü üreteceğine" karar vermesine izin verir. Çağıran kod ürünü interface üzerinden kullanır, somut sınıfın adını hiç görmez. Klasik örnek: bir belge uygulaması `Document` üretir; `PdfApp` alt sınıfı `PdfDocument`, `WordApp` ise `WordDocument` döndürür. Üst seviye "belge aç/kapat" akışı hiç değişmez.

**Abstract Factory** bunu bir üst basamağa taşır: birbiriyle uyumlu bir *ürün ailesini* birlikte üretir. Örneğin bir arayüz kütüphanesinde `WindowsFactory` düğme, kaydırma çubuğu ve pencereyi Windows temasında; `MacFactory` aynılarını macOS temasında üretir. Kritik fayda: bir ailenin parçalarının yanlışlıkla karışmasını (Windows düğmesi + Mac penceresi) engellersiniz.

### Builder

**Builder**, çok sayıda opsiyonel parametresi olan karmaşık nesnelerin adım adım kurulmasını sağlar. Kök neden: uzun yapıcı listeleri (telescoping constructor) okunmaz ve hataya açıktır. `new User("Ali", null, null, 30, null, true)` gibi bir çağrıda hangi `null`'ın ne olduğu belirsizdir. Builder ise `User.builder().isim("Ali").yas(30).aktif(true).build()` gibi okunabilir, isimlendirilmiş bir kurulum verir ve nesneyi `build()` çağrılana kadar tutarsız bir ara durumda tutmaz.

### Singleton — Dikkatli Olun

**Singleton**, bir sınıftan tüm uygulamada tek bir örnek (instance) bulunmasını garanti eder ve ona global erişim noktası sunar. Yapılandırma yöneticisi, log kaydedici gibi durumlar için akla yatkın görünür.

Ancak Singleton, kalıplar arasında en çok kötüye kullanılan ve en çok eleştirilenidir. Nedeni şudur: aslında kılık değiştirmiş bir *global değişkendir*. Global durum (global state) kodun her yerinden gizlice erişilebildiği için bağımlılıkları görünmez kılar; hangi sınıfın neye bağlı olduğunu imzalara bakarak anlayamazsınız. Ayrıca test edilebilirliği ciddi biçimde bozar: birim testlerinde Singleton'ı sahte (mock) bir nesneyle değiştirmek zordur, ve testler arasında taşınan durum sinsi hatalara yol açar. Çok iş parçacıklı ortamda Singleton'ın tembel (lazy) kurulumu ayrıca bir race condition kaynağıdır; doğru yapmak için double-checked locking veya dilin sunduğu güvenli başlatma mekanizmalarını bilmek gerekir.

Modern pratik, Singleton yerine çoğunlukla **dependency injection** (bağımlılık enjeksiyonu) önerir: "tek örnek" garantisini bir DI konteynerinin yaşam döngüsü (lifecycle) yönetimine bırakır, ama nesneyi hâlâ açıkça yapıcıdan geçirir; böylece test sırasında yerine başka bir örnek koymak kolaydır.

### Prototype

**Prototype**, yeni bir nesneyi sıfırdan kurmak yerine mevcut bir örneği klonlayarak (copy) üretir. Kurulumu pahalı nesnelerde ya da çalışma zamanında hangi tipin gerektiği belli olmadığında işe yarar. Buradaki en yaygın tuzak derin/sığ kopya ayrımıdır: sığ kopya (shallow copy) iç referansları paylaşır ve orijinali değiştirdiğinizde klonu da beklenmedik şekilde etkiler.

## Structural (Yapısal) Kalıplar

Yapısal kalıplar nesnelerin ve sınıfların **birbirine nasıl bağlanıp daha büyük yapılar oluşturduğuyla** ilgilenir. Temel motivasyon: iki parçayı, birbirlerinin iç ayrıntısına bağımlı hale getirmeden bir araya getirmek.

### Adapter

**Adapter**, uyumsuz iki arayüzü birbirine bağlar. Elinizde beklenen `A` interface'i, ama işlevi sağlayan `B` sınıfı farklı bir imzayla var; Adapter araya girip `B`'yi `A` gibi gösterir. Gerçek hayatta en çok üçüncü parti kütüphaneleri ya da eski (legacy) kodu, yeni sisteminizin beklediği sözleşmeye uydururken kullanılır. Kök neden: kaynak koda dokunamadığınız (ya da dokunmak istemediğiniz) bir bileşeni kendi soyutlamanıza sokmak.

### Decorator

**Decorator**, bir nesneye çalışma zamanında, onu sarmalayarak (wrapping) yeni davranışlar ekler; hem de aynı interface'i koruyarak. Kalıtımla her kombinasyon için ayrı alt sınıf üretmek (sıkıştırılmış + şifreli + tamponlu akış...) kombinatoryal patlamaya yol açar. Decorator bunun yerine küçük sarmalayıcıları üst üste dizmenize izin verir: `new Buffered(new Encrypted(new FileStream(...)))`. Java'nın `InputStream` hiyerarşisi bunun kanonik örneğidir. Fayda: her sarmalayıcı tek bir işten sorumludur ve serbestçe birleştirilebilir.

### Facade

**Facade**, karmaşık bir alt sistemin önüne basit, tek bir arayüz koyar. Alt sistemin onlarca sınıfını doğrudan çağırmak yerine, istemci tek bir kolay yüzeyle konuşur. Kök neden: bağımlılığı ve öğrenme yükünü azaltmak. Facade alt sistemi *gizlemez* (isteyen hâlâ derine inebilir), sadece en yaygın senaryoyu kolaylaştırır.

### Proxy

**Proxy**, gerçek bir nesnenin yerine geçen ve ona erişimi denetleyen bir vekildir; aynı interface'i sunar. Farklı amaçlarla kullanılır: gerçek nesneyi ihtiyaç anına kadar yaratmama (lazy loading / virtual proxy), erişim kontrolü (protection proxy), uzak bir nesneye ağ üzerinden erişim (remote proxy) ya da sonuçları önbelleğe alma. Decorator'la yapısal olarak benzer görünür ama niyet farklıdır: Decorator davranış *ekler*, Proxy erişimi *denetler*.

### Composite

**Composite**, tekil nesneleri ve nesne gruplarını aynı şekilde ele almanıza olanak tanır; ağaç yapıları (dosya sistemi klasör/dosya, arayüz bileşenleri) için idealdir. İstemci bir yaprakla (leaf) bir dalı (branch) ayırt etmek zorunda kalmaz; ikisine de aynı işlemi (`render()`, `boyutHesapla()`) uygular ve özyineleme (recursion) doğal biçimde çalışır.

## Behavioral (Davranışsal) Kalıplar

Davranışsal kalıplar nesneler arasındaki **sorumluluk dağılımı ve iletişim** ile ilgilenir. Yani "kim neyi bilmeli, kim kime nasıl haber vermeli" sorusunu çözerler.

### Strategy

**Strategy**, birbirinin yerine geçebilen algoritmaları ayrı nesnelere kapsüller (encapsulate) ve çalışma zamanında birini seçmenize izin verir. Klasik örnek: bir sıralama, ödeme ya da sıkıştırma algoritmasını `if/else` zinciriyle seçmek yerine, her algoritmayı ortak bir interface'i uygulayan ayrı bir sınıfa koymak. Kök neden: davranışı kullanan koddan ayırıp, yeni bir algoritma eklerken mevcut kodu değiştirmemek (Open/Closed ilkesi). Strategy, kalıtım yerine bileşim ilkesinin en saf örneğidir.

### Observer

**Observer**, bir nesnenin durumundaki değişikliği ona abone olan (subscribe) diğer nesnelere otomatik bildirir. Bir "özne" (subject) ve birden çok "gözlemci" (observer) vardır; özne kimin dinlediğini somut olarak bilmez, sadece bir listeye haber salar. Kök neden: yayıncı ile abonelerin birbirinden gevşek bağlı (loosely coupled) olması. Olay tabanlı (event-driven) sistemlerin, kullanıcı arayüzü bağlamalarının (data binding) ve pub/sub mimarilerinin temelidir. Tuzak: gözlemciler aboneliklerini bırakmazsa bellek sızıntısı (memory leak) olur; ayrıca bildirim zincirleri beklenmedik biçimde uzayıp performans sorunları yaratabilir.

### Command

**Command**, bir isteği (yapılacak işi) bir nesne olarak paketler. Böylece istekleri parametre gibi geçirebilir, kuyruğa alabilir, günlüğe yazabilir ve en önemlisi geri alınabilir (undo/redo) hale getirebilirsiniz. Metin editörlerindeki geri-al mekanizması, iş kuyrukları ve makro kayıtları bu kalıba dayanır. Kök neden: "ne yapılacağı" bilgisini "ne zaman/kimin tarafından yapılacağı" bilgisinden ayırmak.

### State

**State**, bir nesnenin iç durumu değiştiğinde davranışının da değişmesini, her durumu ayrı bir sınıfa koyarak sağlar. Devasa `switch(durum)` bloklarının yerini alır. Örneğin bir sipariş nesnesi "Beklemede", "Kargoda", "Teslim Edildi" durumlarında farklı davranır; her durum kendi geçiş kurallarını bilir. Bu, durum makinelerini (state machine) okunabilir ve genişletilebilir kılar.

### Diğerleri: Template Method, Iterator, Chain of Responsibility, Mediator, Visitor

- **Template Method**: Bir algoritmanın iskeletini üst sınıfta sabitler, değişen adımları alt sınıflara bıraktırır. Strategy'nin kalıtım tabanlı akrabasıdır.
- **Iterator**: Bir koleksiyonun elemanlarını, iç yapısını açığa çıkarmadan tek tek gezmenizi sağlar. Bugün çoğu dilde (foreach, generator) dile gömülüdür.
- **Chain of Responsibility**: Bir isteği, onu işleyebilecek biri bulunana kadar bir işleyiciler zincirinden geçirir. Middleware ve olay yakalama sistemlerinde yaygındır.
- **Mediator**: Çok sayıda nesnenin doğrudan birbirine bağlanmasını engelleyip iletişimi merkezî bir aracıdan geçirir; "herkes herkesi tanıyor" karmaşasını çözer.
- **Visitor**: Bir nesne yapısına, o nesnelerin sınıflarını değiştirmeden yeni işlemler eklemenizi sağlar. Güçlü ama karmaşıktır; genişleme ekseni "işlemler" tarafındaysa değerlidir.

## Ne Zaman Kullanmalı, Ne Zaman Kaçınmalı

Kalıp seçimindeki altın kural: **kalıp çözümdür, ama önce bir probleminizin olması gerekir.** Kalıplar, kodda tekrar eden bir değişim baskısı ("bu tipi sürekli değiştiriyoruz", "her yeni durumda buraya `if` ekliyoruz", "bu somut sınıfa bağımlıyız") fark ettiğinizde devreye girmelidir. Doğru sinyaller şunlardır:

- Aynı `new SomutSinif()` çağrısı kodun her yerine dağılmışsa → bir yaratımsal kalıp (Factory) düşünün.
- Bir davranışı seçmek için büyüyen bir `if/else` ya da `switch` zinciriniz varsa → Strategy veya State.
- Bir nesnedeki değişikliği birçok yerin duyması gerekiyorsa → Observer.
- Uyumsuz bir kütüphaneyi sisteminize sokuyorsanız → Adapter.

Buna karşılık, **henüz olmayan bir esnekliği önceden kurmayın.** "İleride belki üç farklı veritabanı destekleriz" diye baştan Abstract Factory kurmak, çoğu zaman asla gelmeyecek bir gelecek için bugünün kodunu karmaşıklaştırır. YAGNI ilkesi ("You Aren't Gonna Need It") tam da bunu söyler: gerçek bir ikinci uygulama ortaya çıkana kadar soyutlamayı ertelemek genellikle daha ucuzdur. İyi mühendis, kalıbı *baştan* değil, tekrar (duplication) kendini üçüncü kez gösterdiğinde, yani ihtiyaç kanıtlandığında ekler ("refactor to patterns").

## Aşırı Kullanım Tehlikesi

Tasarım kalıplarının en büyük tehlikesi, çözdükleri problemden bağımsız olarak *statü sembolü* gibi kullanılmalarıdır. Kalıpları yeni öğrenen mühendis, her yere kalıp serpme eğilimine kapılır; buna literatürde bazen "pattern hastalığı" denir. Sonuç, basit bir işi yirmi sınıfa yayan, izlenmesi imkânsız bir mimaridir. Unutmayın: **kalıp bir maliyettir.** Her ek soyutlama katmanı, kodu okuyan bir sonraki kişinin zihninde tutması gereken bir dolaylılık (indirection) ekler. Bu maliyet ancak gerçek bir esneklik ihtiyacı karşılığında haklı çıkar.

Somut bir aşırı kullanım örneği: iki satırlık bir hesaplama için Strategy interface'i, bir factory, bir de konfigürasyon sınıfı kurmak. Kod artık "esnek" görünür ama esneklik hiç kullanılmaz; sadece dört dosya arasında zıplayarak basit bir toplamayı bulmaya çalışırsınız. Basit bir fonksiyon çoğu zaman doğru cevaptır. Kalıp, karmaşıklığı *yönetmek* için vardır; olmayan karmaşıklığı *icat etmek* için değil.

İkinci bir tehlike, **kalıbı yanlış problemde uygulamaktır.** Örneğin Singleton'ı sadece "her yerden erişmek kolay olsun" diye kullanmak, aslında global durum sokmaktır ve az önce anlattığımız test/eşzamanlılık sorunlarını davet eder. Ya da Visitor'ı, sınıf hiyerarşisi sık sık değişen bir yerde kullanmak: Visitor yeni *işlem* eklemeyi kolaylaştırır ama yeni *tip* eklemeyi zorlaştırır; ekseni yanlış seçerseniz kalıp size karşı çalışır.

Üçüncü tehlike, kalıp isimlerini bir *tören diline* çevirmektir. Her sınıfı `XxxManager`, `XxxFactory`, `XxxStrategy` diye adlandırmak, aslında kalıbı uygulamadan sadece etiketini yapıştırmaktır. İsim niyeti taşımalı; ama gerçek yapı isimle örtüşmüyorsa isim yalan söyler ve okuyucuyu yanıltır.

## Yaygın Hatalar

- **Kalıbı problemi anlamadan uygulamak.** Kitaptaki UML diyagramını kopyalamak, o kalıbın hangi değişim baskısını çözdüğünü anlamak değildir. Önce "neyi esnek tutmak istiyorum?" sorusunu yanıtlayın.
- **Proxy ile Decorator'ı, Strategy ile State'i karıştırmak.** Yapıları benzer, niyetleri farklıdır. Decorator davranış ekler / Proxy erişim denetler; Strategy'de seçimi dışarıdan istemci yapar / State'te durumlar geçişi kendi içinde yönetir. Niyeti değil yapıyı taklit ederseniz yanlış kalıbı seçersiniz.
- **Singleton'ı reflekssel kullanmak.** "Tek örnek gerek" düşüncesi doğrudan Singleton'a atlamaktır; oysa çoğu durumda dependency injection ile tek örnek yaşam döngüsü daha temiz ve test edilebilir olur.
- **Observer'da abonelikleri temizlememek.** Gözlemci artık gerekmediğinde aboneliğini bırakmazsa (unsubscribe) hem bellek sızar hem de ölü nesnelere bildirim gider.
- **Kalıtımı bileşime tercih etmek.** Sorunu her zaman yeni bir alt sınıfla çözmeye çalışmak, kırılgan ve derin hiyerarşiler üretir. GoF'un temel öğüdü tersidir.
- **Dile gömülü çözümü görmezden gelip elle kalıp yazmak.** Modern diller Iterator, Strategy (birinci sınıf fonksiyonlar), Observer (event/reactive kütüphaneleri) gibi birçok kalıbı zaten sunar. Bunları elle yeniden inşa etmek gereksiz koddur.

## En İyi Pratikler

Kalıpları sağlıklı kullanmanın özü, onları amaç değil *araç* olarak görmektir. Birkaç yol gösterici ilke:

**Problemden başlayın, kalıptan değil.** Önce kodun neresinin sık değiştiğini, neyin kırılgan olduğunu tespit edin. Kalıp, bu teşhisin *ardından* gelen tedavidir. "Elimde çekiç var, her şey çivi görünüyor" tuzağına düşmeyin.

**En basit çözümle başlayın, gerektiğinde kalıba yükseltin (refactor to patterns).** Tekrarın veya değişim baskısının kanıtı ortaya çıkana kadar sade kodu tercih edin. Kalıba geçiş, testleriniz varken güvenli bir refactoring adımıdır; bu yüzden testler kalıpların önkoşuludur.

**Niyeti isimle ve arayüzle iletin.** Kalıp kullandığınızda, ekip arkadaşınızın onu tanıması için isimlendirme yardımcı olur; ama isim gerçek yapıyı yansıtmalı. Kalıbın adı, gereksiz bir tören değil, doğru kullanıldığında bir belgeleme aracıdır.

**"Composition over inheritance" ve "program to an interface" ilkelerini pusula yapın.** Hangi kalıbı seçeceğinizde tereddüt ederseniz, bu iki ilke sizi neredeyse her zaman doğru yöne çeker; çünkü kalıpların çoğu bu ilkelerin özel biçimleridir.

**Kalıbın maliyetini bilinçli tartın.** Her soyutlama katmanı okunabilirlikten bir şeyler alır, esneklikten bir şeyler verir. Bu takası açıkça yapın: "Bu esnekliğe bugün gerçekten ihtiyacım var mı?" Cevabı hayırsa, kalıbı ertelemek çoğu zaman doğru mühendislik kararıdır.

**Dilin ve çerçevenin sunduğunu önce kontrol edin.** Uygulayacağınız kalıp muhtemelen dilinizde ya da kullandığınız framework'te hazır ve daha iyi test edilmiş bir biçimde vardır. Kendi Iterator'ınızı yazmadan önce dilin sunduğuna bakın.

Özetle, tasarım kalıpları deneyimli mühendislerin damıtılmış bilgeliğidir; ama bu bilgelik ancak *problemi* anladığınızda işe yarar. Kalıpları ezberlenecek 23 kalıp listesi olarak değil, her biri belirli bir değişim baskısına verilmiş bir yanıt olarak görün. O zaman hem doğru kalıbı doğru yerde seçer hem de en önemli beceriyi kazanırsınız: bazen hiçbir kalıp kullanmamanın en iyi tasarım olduğunu bilmek.
