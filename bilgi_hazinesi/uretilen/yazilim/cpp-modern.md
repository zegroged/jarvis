# Modern C++: RAII, Akıllı İşaretçiler, Move Semantiği, Şablonlar ve STL

Modern C++ (C++11 ve sonrası: C++14, C++17, C++20, C++23) yalnızca dile eklenen bir avuç yeni anahtar kelimeden ibaret değildir. Kaynak yönetimi, sahiplik (ownership), kopyalama maliyeti ve tür güvenliği konularında düşünme biçimini kökten değiştiren bir felsefe kaymasıdır. Bu makale, "neden böyle" sorusuna cevap veren bir bakış açısıyla modern C++'ın çekirdek kavramlarını ele alıyor: RAII, akıllı işaretçiler, move semantiği, şablonlar, STL ve bunların etrafındaki en sinsi tuzaklar.

Bu araçların ortak paydası tek bir problemdir: **C++'ta bir garbage collector yoktur.** Bellek, dosya tanıtıcıları (file handle), soket, mutex kilidi gibi kaynakları elle yönetmeniz gerekir. Modern C++'ın tüm bu araçları, "elle yönetmeyi" derleyicinin ve tip sisteminin sırtına yükleyerek, insan hatasını en aza indirmek için tasarlanmıştır.

## RAII: Kaynak Edinme Başlatmadır

### Tanım

RAII (Resource Acquisition Is Initialization), bir kaynağın ömrünü bir nesnenin ömrüne bağlayan tekniktir. Kaynak, nesne inşa edilirken (constructor) edinilir; nesne kapsam (scope) dışına çıkıp yok edilirken (destructor) serbest bırakılır. İsmi biraz talihsizdir; asıl vurgu "edinme" tarafında değil, **serbest bırakmanın otomatikliğindedir.**

### Kök neden: Deterministik yıkım ve stack unwinding

RAII'nin çalışmasının temelinde C++'ın iki garantisi yatar. Birincisi, yerel (otomatik ömürlü) nesnelerin destructor'ının, kapsamdan çıkıldığında **kesin olarak (deterministically)** ve tanımlandıkları sıranın **tersine** çağrılmasıdır. İkincisi, bir exception fırlatıldığında devreye giren **stack unwinding** mekanizmasıdır: exception, yakalayıcıya (catch) doğru yol alırken, o ana kadar tam olarak inşa edilmiş tüm yerel nesnelerin destructor'ları çağrılır.

İşte bu ikinci garanti, RAII'yi manuel `try/finally` benzeri desenlerden üstün kılan şeydir. C++'ta `finally` bloğu yoktur, çünkü ihtiyaç yoktur: temizlik kodunu destructor'a koyduğunuzda, ister fonksiyon normal biterse, ister `return` ile erken çıkarsa, ister bir exception ile fırlarsa temizlik **her yolda** garantilenir. Manuel temizlikte ise her erken çıkış noktasında `cleanup()` çağırmayı unutma riski vardır ve exception'lar bunu neredeyse imkânsız kılar.

### Somut örnek

```cpp
class DosyaTutucu {
    std::FILE* f_;
public:
    explicit DosyaTutucu(const char* yol)
        : f_(std::fopen(yol, "r")) {
        if (!f_) throw std::runtime_error("dosya acilamadi");
    }
    ~DosyaTutucu() {
        if (f_) std::fclose(f_);   // kapsam sonunda kesinlikle calisir
    }
    // Kopyalamayi yasakla; iki nesne ayni handle'i kapatmasin
    DosyaTutucu(const DosyaTutucu&) = delete;
    DosyaTutucu& operator=(const DosyaTutucu&) = delete;

    std::FILE* get() const { return f_; }
};

void isle() {
    DosyaTutucu d("veri.txt");
    // ... burada exception firlasa bile fclose cagrilir ...
    parse(d.get());
}   // <- d yikilir, dosya kapanir
```

Burada dikkat edilmesi gereken kritik nokta, kopya constructor ve atama operatörünün `= delete` ile yasaklanmasıdır. Aksi hâlde nesnenin bir kopyası, aynı ham `FILE*` işaretçisini tutar ve **her iki destructor da aynı handle'ı kapatmaya çalışır** — bu bir double-free / double-close hatasıdır.

### Tuzaklar ve doğru kullanım

En önemli kural: **destructor asla exception fırlatmamalıdır.** Kök neden şudur: eğer stack unwinding zaten bir exception yüzünden çalışıyorsa ve bu sırada bir destructor ikinci bir exception fırlatırsa, C++ çalışma zamanı iki eşzamanlı exception'ı yönetemez ve `std::terminate` çağırarak programı anında sonlandırır. Bu yüzden standart kütüphanenin destructor'ları `noexcept`tir ve sizinkiler de öyle olmalıdır. Temizlik sırasında hata olabiliyorsa (örneğin `fclose` başarısızlığı), bunu ya yutun ya loglayın ama fırlatmayın.

## Akıllı İşaretçiler: Sahipliği Tip Sistemine Kodlamak

### Tanım ve neden gerekli

Akıllı işaretçiler (smart pointer), RAII'yi heap belleğine uygulayan sınıflardır. Ham `new`/`delete` ikilisinin en büyük sorunu, sahipliğin kodda **görünmez** olmasıdır: bir fonksiyon size `Widget*` döndürdüğünde, bunu `delete` etmek sizin sorumluluğunuz mu, yoksa fonksiyon bir dâhili nesneye referans mı verdi? İmza bunu söylemez. Akıllı işaretçiler sahipliği **tipin içine kodlar**, böylece niyet hem okuyucuya hem derleyiciye açık olur.

### `std::unique_ptr` — tekil sahiplik

`unique_ptr`, bir kaynağın **tek** sahibidir. Kopyalanamaz (kopya constructor'ı silinmiştir) ama taşınabilir (movable). Kök tasarım fikri şudur: sahiplik tek olduğu için, kaynağın kimin sorumluluğunda olduğu her an belirsizliğe yer bırakmaz. Ve en güzeli, `unique_ptr` **sıfır ek maliyetlidir (zero-overhead)** — varsayılan silici (deleter) ile boyutu ham işaretçiyle aynıdır ve ürettiği makine kodu, doğru yazılmış manuel `delete` kadar hızlıdır.

```cpp
std::unique_ptr<Widget> olustur() {
    return std::make_unique<Widget>(42);  // sahiplik cagirana tasinir
}

void kullan() {
    auto w = olustur();      // w artik sahibi
    w->cizim();
    // auto w2 = w;          // DERLEME HATASI: kopyalanamaz (iyi!)
    auto w2 = std::move(w);  // sahiplik w2'ye tasinir; w artik nullptr
}   // w2 yikilir, Widget delete edilir
```

`make_unique` tercih edilmelidir (C++14). Neden? Hem `new` anahtar kelimesini kodunuzdan uzak tutar, hem de exception güvenliği açısından belirli eski tuzakları kapatır. `std::make_unique<Widget>(...)` tek bir atomik adımda hem belleği ayırır hem nesneyi kurar.

### `std::shared_ptr` — paylaşımlı sahiplik ve referans sayımı

`shared_ptr`, bir kaynağın birden çok sahibi olduğu durumlar içindir. Çalışma mantığı **referans sayımına (reference counting)** dayanır: her kopya bir sayacı artırır, her yıkım azaltır; sayaç sıfıra düştüğünde kaynak serbest bırakılır.

Kök neden ve maliyet burada önemli. Bu sayaç, birden çok thread'ten güvenle artırılıp azaltılabilmesi için **atomik (atomic)** işlemlerle güncellenir. Bu atomiklik bedavaya gelmez; `shared_ptr` kopyalamak, `unique_ptr` kopyalamaktan (ki o zaten yasak) veya taşımaktan gözle görülür şekilde pahalıdır. Bu yüzden pratik kural: **varsayılan seçiminiz `unique_ptr` olsun, paylaşımlı sahipliğe gerçekten ihtiyacınız olduğunu kanıtlayana kadar `shared_ptr` kullanmayın.** Çok kişinin `shared_ptr`'ı "güvenli işaretçi" diye her yere serpmesi, hem performansı hem de sahiplik netliğini bozan yaygın bir hatadır.

`shared_ptr` oluştururken de `std::make_shared` tercih edilir. Sebep somuttur: `make_shared`, nesnenin kendisini ve kontrol bloğunu (sayaçların tutulduğu yapı) **tek bir bellek ayırmayla** yan yana yerleştirir. `shared_ptr<T>(new T(...))` ise iki ayrı ayırma yapar. Tek ayırma hem hızlıdır hem cache dostudur. (Küçük bir nüans: `make_shared` kullanıldığında, nesneye hâlâ zayıf referanslar varken bile nesnenin belleği kontrol bloğuyla birlikte tutulur; devasa nesnelerde ve uzun ömürlü `weak_ptr`'larda bu bir dezavantaj olabilir.)

### `std::weak_ptr` — döngüleri kırmak

Referans sayımının bir Aşil topuğu vardır: **döngüsel referanslar (cyclic references).** İki nesne birbirini `shared_ptr` ile tutarsa, sayaçları asla sıfıra düşmez ve ikisi de sızar (memory leak). Klasik örnek, ebeveyn-çocuk ilişkisidir.

```cpp
struct Dugum {
    std::shared_ptr<Dugum> sonraki;
    std::weak_ptr<Dugum>   onceki;   // geriye referans SAHIPLENMEZ
};
```

`weak_ptr`, işaret ettiği nesneye **sahiplik iddia etmeyen** bir gözlemcidir; sayacı artırmaz. Nesneye erişmek için `lock()` çağrılır: bu, nesne hâlâ hayattaysa geçerli bir `shared_ptr`, değilse boş bir `shared_ptr` döndürür. Böylece "nesne yaşıyorsa kullan, ölmüşse sorun etme" mantığını tip düzeyinde güvenle ifade edersiniz. Kural: döngüsel ilişkilerde **bir yön** `weak_ptr` olmalıdır ki döngü kırılsın.

### Yaygın akıllı işaretçi hataları

Bir ham işaretçiden **iki ayrı** `shared_ptr` oluşturmak felakettir:

```cpp
Widget* ham = new Widget;
std::shared_ptr<Widget> a(ham);
std::shared_ptr<Widget> b(ham);  // HATA: iki ayri kontrol blogu!
// Her ikisi de nesneyi delete etmeye calisir -> double free
```

İki farklı `shared_ptr`, aynı ham işaretçiden kurulduklarında birbirinden habersiz iki ayrı sayaç oluşturur; her biri sayacı bağımsız yönetir ve ikisi de nesneyi siler. Her zaman `make_shared` kullanın ya da tek bir `shared_ptr`'ı kopyalayın. (Bir nesnenin kendisinin `shared_ptr` üretmesi gerekiyorsa `std::enable_shared_from_this` vardır.)

## Move Semantiği: Kopyalamadan Taşımak

### Tanım

Move semantiği (C++11), bir nesnenin sahip olduğu kaynakları **kopyalamak yerine "çalarak"** başka bir nesneye aktarma mekanizmasıdır. Bir `std::vector`'ü kopyalamak, içindeki tüm elemanları yeni bir bellek bloğuna teker teker kopyalamak demektir — büyük bir vektör için pahalıdır. Taşımak ise sadece iç işaretçiyi (bellek bloğunun adresi, boyut, kapasite) yeni nesneye devretmek ve kaynağı boş bırakmaktır. Milyonlarca elemanlı bir vektörün taşınması, üç-beş işaretçi ataması kadar ucuzdur.

### Kök neden: rvalue referansları ve değer kategorileri

Move'un çalışabilmesi için derleyicinin "bu nesne birazdan zaten yok olacak, kaynaklarını çalmam güvenli" durumunu ayırt edebilmesi gerekir. Bunu **değer kategorileri (value categories)** ve **rvalue reference** (`T&&`) ile yapar.

Kabaca: bir **lvalue**, adı olan, hâlâ kullanılacak bir nesnedir (`x` gibi). Bir **rvalue**, geçici (temporary) veya artık gerekmeyen bir nesnedir — bir fonksiyonun döndürdüğü isimsiz sonuç ya da `std::move(x)` ile "bununla işim bitti" diye işaretlediğiniz nesne. Derleyici, elinde bir rvalue varsa, `T&&` alan overload'ı (move constructor / move assignment) seçer ve kaynağı güvenle çalar.

Burada en çok yanlış anlaşılan nokta şudur: **`std::move` aslında hiçbir şeyi taşımaz.** İsmi yanıltıcıdır. `std::move`, sadece bir `static_cast`'tir; nesnesini rvalue referansına dönüştürür, yani "artık bunu taşıyabilirsin" izni verir. Asıl taşıma işini, o rvalue'yu alan move constructor veya move assignment operatörü yapar. Eğer bir tipin move constructor'ı yoksa, `std::move` ile işaretleseniz bile derleyici sessizce kopyaya geri düşer.

### Somut örnek ve moved-from durumu

```cpp
std::vector<int> buyuk = kocamanVektorUret();   // milyonlarca eleman
std::vector<int> hedef = std::move(buyuk);      // O(1) tasima, kopya YOK
// Artik 'buyuk' "moved-from" durumunda:
// gecerli ama belirsiz (valid but unspecified). Boyutu 0 varsayilmaz!
buyuk.clear();          // GUVENLI: yeniden atamadan once temizle
buyuk.push_back(1);     // GUVENLI: yeni durum kur
int x = buyuk[0];       // TEHLIKELI olabilir: icerigi hakkinda varsayim yapma
```

Kritik kavram **moved-from durumudur (moved-from state).** Standart kütüphane tipleri için, bir nesne taşındıktan sonra "geçerli ama belirsiz (valid but unspecified)" bir durumdadır. Bu ne demek? Nesne üzerinde **ön koşul gerektirmeyen** işlemler (yeniden atama, `clear()`, boyut sorgulama) güvenlidir; ama içeriğinin ne olduğuna dair **hiçbir varsayımda bulunamazsınız.** Bir `std::vector`'ün taşındıktan sonra boş olması tipik ama garanti değildir. `std::move`'dan sonra nesneyi ya terk edin ya da yeni bir değer atayın.

### Doğru kullanım: Beşli/Sıfır Kuralı

Move semantiği, "Üçlü Kural"ı "Beşli Kural (Rule of Five)"a genişletir: eğer destructor, kopya constructor, kopya atama, move constructor veya move atamadan **herhangi birini** elle yazıyorsanız, muhtemelen beşini birden düşünmeniz gerekir; çünkü elle kaynak yönetiyorsunuz demektir.

Ama modern C++'ın asıl önerdiği **Sıfır Kuralıdır (Rule of Zero):** kaynaklarınızı doğrudan yönetmeyin. Bunun yerine `unique_ptr`, `vector`, `string` gibi zaten doğru davranan üye tipler kullanın. O zaman derleyicinin ürettiği varsayılan special member function'lar tam olarak doğru çalışır ve **hiçbirini yazmanıza gerek kalmaz.** En iyi kaynak yönetim kodu, yazmadığınız koddur.

### Move ile ilgili tuzaklar

**Tuzak 1 — `const` nesne taşınamaz.** `std::move(const_nesne)`, bir `const T&&` üretir; move constructor `T&&` (const olmayan) beklediği için seçilmez ve **sessizce kopya constructor'a düşer.** Kod derlenir, doğru çalışır ama beklediğiniz performansı asla vermez. Bu yüzden taşımak istediğiniz üyeleri gereksiz yere `const` yapmayın.

**Tuzak 2 — dönüş değerinde `std::move` kullanmak genelde zararlıdır.**

```cpp
std::vector<int> uret() {
    std::vector<int> v = ...;
    return std::move(v);   // YANLIS: RVO'yu engeller!
    // return v;           // DOGRU: derleyici zaten optimize eder
}
```

Derleyici, yerel bir nesneyi `return` ederken zaten **kopya elizyonu / RVO (Return Value Optimization)** uygular; nesne doğrudan çağıranın belleğinde inşa edilir, ne kopya ne taşıma olur — sıfır maliyet. `return std::move(v)` yazdığınızda ifadeyi rvalue'ya zorlarsınız ama aynı zamanda RVO'yu **imkânsız kılarsınız**, geriye zorunlu bir taşıma bırakırsınız. Yani optimizasyon niyetiyle tam tersini yaparsınız. Kural: yerel değişkeni sade `return v;` ile döndürün.

**Tuzak 3 — move'dan sonra nesneyi kullanmak.** Yukarıda anlatılan moved-from durumu. Statik analiz araçları (clang-tidy'nin ilgili kontrolleri gibi) bunu yakalamaya çalışır ama derleyici çoğunlukla uyarmaz.

## Şablonlar: Derleme Zamanı Genelleme

### Tanım ve kök mantık

Şablonlar (templates), tek bir kod parçasını **birçok tip için** yazmanıza olanak tanır. Çalışma mantığı çok özeldir: şablon bir tip için kullanıldığında (instantiation), derleyici o tipe özel somut kodu **derleme zamanında** üretir. Yani `std::vector<int>` ve `std::vector<std::string>` birbirinden tamamen bağımsız iki sınıfa derlenir.

Bu, Java/C# generics'ten temelde farklıdır. Orada tek bir jenerik kod tip silme (type erasure) ile çalışır. C++'ta ise her tip için ayrı kod üretilir. Faydası: **sıfır çalışma zamanı maliyeti** ve tam optimizasyon (inline'lama, tipe özel makine kodu). Bedeli: kod şişmesi (code bloat) potansiyeli ve genellikle her şeyin başlık dosyasında (header) olması gerekliliği, dolayısıyla daha uzun derleme süreleri.

### Duck typing ve gecikmiş hata mesajları

Şablonlar "yapısal (structural)" tip kontrolü yapar; bir tür derleme zamanı **duck typing**'idir. `template<typename T> void f(T x) { x.foo(); }` yazdığınızda, `T`'nin hangi arayüzü desteklemesi gerektiğini açıkça belirtmezsiniz — sadece kullanırsınız. `T`'nin gerçekten bir `foo()` metodu olup olmadığı, ancak şablon o tiple **kullanıldığında (instantiated)** kontrol edilir.

Bunun pratikteki en can sıkıcı sonucu, tarihsel olarak **korkunç hata mesajlarıdır.** Bir tip şablonun beklediği bir işlemi desteklemediğinde, derleyici hatayı kütüphanenin derinliklerinde, sizin kodunuzdan çok uzakta, sayfalarca instantiation izi ile birlikte raporlar.

### Concepts: C++20'nin çözümü

C++20, bu problemi **concepts** ile büyük ölçüde çözer. Concept, bir şablon parametresinin sağlaması gereken kısıtlamaları (constraints) **isimlendirilmiş, okunabilir** biçimde ifade etmenizi sağlar.

```cpp
#include <concepts>

template<typename T>
concept Toplanabilir = requires(T a, T b) {
    { a + b } -> std::convertible_to<T>;
};

template<Toplanabilir T>
T topla(T a, T b) { return a + b; }
```

Faydası ikilidir. Birincisi, bir tip kısıtlamayı sağlamıyorsa hata mesajı artık kütüphanenin içinde değil, **çağrı noktasında** ve anlamlıdır: "bu tip `Toplanabilir` kavramını karşılamıyor." İkincisi, kısıtlamalar niyeti belgeler ve overload çözümlemesine katılır. Concepts'ten önce aynı iş `std::enable_if` ve SFINAE ile yapılırdı; bu teknikler işe yarasa da okunması ve yazması çok zordu. Concepts, aynı gücü çok daha temiz bir sözdizimiyle sunar.

### Şablon tuzakları

En sinsi tuzaklardan biri, C++11 öncesi bir söz dizimi kalıntısıdır: iki kapalı köşeli parantezin (`>>`) yan yana gelmesi eski derleyicilerde sağ-kaydırma operatörüyle karıştırılırdı (`vector<vector<int>>` yerine `> >` yazmak gerekirdi). Bu, C++11'de düzeltilmiştir.

Daha güncel bir tuzak, **template kod şişmesidir.** Aynı davranışı yüzlerce tip için instantiate ederseniz, çıktı ikili dosyası (binary) beklenmedik biçimde büyüyebilir. Tipe bağımlı olmayan mantığı, şablon olmayan bir yardımcı fonksiyona çıkarmak bu şişmeyi azaltır.

## STL: Konteynerler, Iteratörler ve Algoritmalar

### Tasarım felsefesi

STL (Standard Template Library), üç ortogonal bileşen etrafında kurulmuştur: **konteynerler** (veriyi tutar: `vector`, `map`, `unordered_map`, `list`...), **iteratörler** (konteyner elemanlarına genelleştirilmiş erişim sağlar) ve **algoritmalar** (`sort`, `find`, `transform`... — konteynerden bağımsız çalışır). Bu ayrımın dâhiyane yanı şudur: `M` algoritma ve `N` konteyner için `M×N` ayrı fonksiyon yazmak yerine, algoritmalar iteratörler üzerinden çalıştığından `M+N` parça yazılır. Iteratör, ikisini birbirine bağlayan tutkaldır.

### Konteyner seçimi: neden `vector` varsayılandır

`std::vector`, neredeyse her zaman ilk tercih olmalıdır — hatta araya ekleme/silme gerektiren durumlarda bile. Kök neden **cache locality**'dir. Modern CPU'larda bellek erişimi, aritmetikten kat kat yavaştır ve CPU veriyi cache'e satır satır (cache line) çeker. `vector` elemanları bellekte bitişik (contiguous) tuttuğu için, üzerinde gezinmek cache dostudur. `std::list` (bağlı liste) ise elemanları bellekte dağınık düğümlerde tutar; her erişim potansiyel bir cache miss'tir. Sonuç: teoride `list`'in O(1) araya ekleme avantajı olsa bile, pratikte `vector`'de linear arama + kaydırma bile çoğu gerçek iş yükünde `list`'i geçer. "Big-O her şeyi anlatmaz; sabit çarpanlar ve bellek erişim deseni belirleyicidir" ilkesinin en somut örneğidir.

`map` (dengeli ağaç, sıralı, O(log n)) ile `unordered_map` (hash tablosu, sırasız, ortalama O(1)) arasındaki seçim de benzer düşünmeyi gerektirir: sıra önemliyse veya anahtar aralık sorguları yapıyorsanız `map`; salt anahtar-değer araması ve sıra umursanmıyorsa genellikle `unordered_map` hızlıdır (ama hash çarpışmalarına ve kötü hash fonksiyonlarına dikkat).

### İterator geçersizleşmesi (iterator invalidation)

STL'in en tehlikeli ve en yaygın tuzağı budur. Bir konteyneri değiştirdiğinizde, ona işaret eden mevcut iteratörler, işaretçiler ve referanslar **geçersizleşebilir.** Kök neden `vector`'de çok somuttur: `vector` kapasitesi dolduğunda `push_back`, daha büyük yeni bir bellek bloğu ayırır, elemanları oraya taşır ve eski bloğu serbest bırakır (reallocation). Eski bloğa işaret eden her iteratör artık serbest bırakılmış belleği gösterir — bu bir **dangling pointer**'dır ve kullanımı tanımsız davranıştır (undefined behavior).

```cpp
std::vector<int> v = {1, 2, 3};
auto it = v.begin();
v.push_back(4);      // reallocation olabilir -> 'it' gecersiz!
// *it;              // TANIMSIZ DAVRANIS

// Doguru silme deseni (erase-remove degil, dongude silme):
for (auto i = v.begin(); i != v.end(); ) {
    if (*i % 2 == 0) i = v.erase(i);  // erase, yeni gecerli iterator dondurur
    else ++i;
}
```

Yukarıdaki döngüdeki klasik hata, `erase` çağırdıktan sonra `++i` yapmaktır; `erase` çağrılan iteratörü geçersizleştirir. Doğrusu, `erase`'in döndürdüğü yeni geçerli iteratörü kullanmaktır. Her konteynerin hangi işlemlerde hangi iteratörleri geçersizleştirdiği standartta tanımlıdır; `vector` en agresif olanıdır, `list` ve `map` (düğüm tabanlı oldukları için) çok daha az geçersizleştirir.

### Algoritmalar ve Ranges

Ham döngüler yerine STL algoritmalarını tercih etmek modern bir alışkanlıktır. `std::sort`, `std::find_if`, `std::accumulate` gibi algoritmalar hem niyeti daha net ifade eder hem de kütüphane yazarları tarafından iyi optimize edilmiştir. C++20 ile gelen **Ranges**, bunu bir adım öteye taşır: algoritmalar artık `begin()/end()` çiftleri yerine doğrudan konteynerler üzerinde çalışabilir ve **view**'ler ile tembel (lazy), zincirlenebilir dönüşümler yazılabilir:

```cpp
#include <ranges>
auto sonuc = v | std::views::filter([](int x){ return x % 2 == 0; })
               | std::views::transform([](int x){ return x * x; });
// tembel degerlendirme: gezinene kadar hicbir sey hesaplanmaz
```

### Sık yapılan STL hataları

**`[]` operatörü `map`'te eleman ekler.** `std::map` üzerinde `m[anahtar]` ile bir okuma yaptığınızı sanırken, anahtar yoksa onu **varsayılan değerle oluşturur.** Salt sorgu için `find` veya (C++20) `contains` kullanın. Aksi hâlde const olmayan bir `map`'i "okumak" onu sessizce büyütür.

**İşaretçileri/iteratörleri konteyner değişikliği üzerinden saklamak.** Yukarıda anlatıldı; bir referansı veya iteratörü uzun süre saklıyorsanız, o arada konteynerin değişmediğinden emin olun.

**`std::endl` gereksiz kullanımı.** `std::endl`, satır sonu eklemenin yanında akışı da **flush** eder (tampon boşaltma). Bir döngüde her satırda `endl` kullanmak, gereksiz flush'larla I/O performansını ciddi düşürür. Sadece newline istiyorsanız `'\n'` kullanın; flush'a gerçekten ihtiyacınız olduğunda `endl` kullanın.

## Bütünü Bağlamak: Genel En İyi Pratikler

Modern C++'ın tüm bu parçaları tek bir zihniyette buluşur: **sahipliği ve ömrü belirsizliğe yer bırakmayacak şekilde tip sistemine kodla, gerisini derleyiciye bırak.**

Pratik bir öncelik sıralaması şöyle özetlenebilir. Kaynak yönetiminde önce **Sıfır Kuralını** deneyin: standart tipleri üye yapın, hiç special member yazmayın. Yazmanız gerekirse **Beşli Kuralı** bütün olarak uygulayın. Heap sahipliğinde varsayılanınız **`unique_ptr`** olsun; paylaşımı kanıtlayana kadar `shared_ptr`'a geçmeyin; döngü riskinde `weak_ptr` ile bir yönü kırın. Ham `new`/`delete`'i uygulama kodunuzdan tamamen sürün; `make_unique`/`make_shared` kullanın. Değer döndürürken RVO'ya güvenin, `return std::move(local)` yazmayın. Konteyner olarak aksini kanıtlayana kadar **`vector`** seçin. İteratör geçersizleşmesini her değiştirme işleminde aklınızda tutun. Ve mümkün olan her yerde **`const`** kullanın: bir şeyin değişmeyeceğini derleyiciye söylemek hem hataları önler hem de optimizasyona kapı açar.

Son olarak, bu araçlar güvenliği **kolaylaştırır ama garanti etmez.** C++ hâlâ, moved-from nesneleri, dangling referansları, veri yarışlarını (data race) ve tanımsız davranışı mümkün kılan bir dildir. Modern C++'ın vaadi, "doğru olanı yapmayı en kolay yol hâline getirmektir" — yanlışı imkânsız kılmak değil. Derleyici uyarılarını açık tutmak (`-Wall -Wextra` benzeri), sanitizer'ları (address ve undefined behavior sanitizer gibi) test aşamasında çalıştırmak ve statik analiz kullanmak, dilin size bıraktığı bu boşlukları kapatan vazgeçilmez tamamlayıcılardır.
