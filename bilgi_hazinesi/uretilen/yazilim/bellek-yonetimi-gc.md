# Bellek Yönetimi ve Garbage Collection

Bellek yönetimi, bir programın çalışma süresince ihtiyaç duyduğu belleği nasıl talep ettiğini, kullandığını ve serbest bıraktığını yöneten mekanizmaların bütünüdür. Yüzeyde basit görünen bu konu, aslında modern yazılımın en derin tasarım kararlarından birini barındırır: belleğin ne zaman geri verileceğine kim karar verecek? Programcı mı, yoksa çalışma zamanı (runtime) mı? Bu tek soru; C ile Java'yı, Rust ile Python'u, gerçek zamanlı sistemlerle web sunucularını birbirinden ayıran temel çatlaktır. Bu makale, belleğin fiziksel ve mantıksal katmanlarından başlayıp manuel yönetim, referans sayımı (reference counting), mark-sweep tabanlı garbage collection ve Rust'ın ownership modeline kadar uzanan tüm yelpazeyi, "neden böyle" sorusuna cevap vererek ele alır.

## Belleğin İki Yüzü: Stack ve Heap

Bir programın adres uzayı (address space) çeşitli bölgelere ayrılır; ancak dinamik veri açısından en kritik ikisi **stack** ve **heap**'tir. Bu ayrım keyfi değildir; iki farklı ihtiyaca iki farklı çözüm sunar.

### Stack: Hız ve Disiplin

Stack, adı üstünde bir yığın (LIFO — last in, first out) veri yapısıdır. Her fonksiyon çağrısında bir **stack frame** (yığın çerçevesi) oluşur: fonksiyonun yerel değişkenleri, parametreleri, dönüş adresi burada tutulur. Fonksiyon döndüğünde bu çerçeve topluca atılır.

Stack'in olağanüstü hızlı olmasının kök nedeni, tahsis (allocation) işleminin tek bir işlemci komutuna indirgenmesidir: stack pointer denen bir register'ı belirli bir miktar kaydırmak yeterlidir. Bellek talep etmek, aslında "işaretçiyi 32 byte aşağı kaydır" demektir. Serbest bırakmak da işaretçiyi geri kaydırmaktır. Arama, boşluk yönetimi, parçalanma (fragmentation) hesabı yoktur. Ayrıca stack, sürekli erişilen sıcak bir bölge olduğu için genellikle işlemci cache'inde durur; bu da erişimi bir kat daha hızlandırır.

Bu hızın bedeli disiplindir. Stack'te tutulan bir verinin boyutu **derleme zamanında (compile time)** bilinmeli ve ömrü, onu oluşturan fonksiyonun ömrüyle sınırlı olmalıdır. Fonksiyon döndükten sonra onun stack frame'ine ait bir adrese erişmek klasik bir hatadır (dangling pointer, aşağıda ele alınacak). Stack boyutu da tipik olarak sınırlıdır (birkaç megabyte mertebesinde); kontrolsüz özyineleme (recursion) bu sınırı aşınca **stack overflow** oluşur.

### Heap: Esneklik ve Sorumluluk

Heap, ömrü ve boyutu çalışma zamanında belirlenen veriler içindir. Kullanıcının gireceği metnin uzunluğunu, ağ üzerinden gelecek listenin eleman sayısını veya bir fonksiyondan dönüp çağıran tarafta yaşamaya devam edecek bir nesneyi önceden bilemezsiniz. İşte bunlar heap'te yaşar.

Heap'in esnekliği, karmaşıklığının da kaynağıdır. Heap bir yığın disiplini izlemez; herhangi bir bloğu herhangi bir sırada tahsis edip serbest bırakabilirsiniz. Bu yüzden altında bir **allocator** (tahsis edici) çalışır: `malloc`/`free` (C) ya da işletim sisteminin `mmap`/`brk` çağrıları üzerine kurulu bir yönetici. Allocator, boş blokların bir listesini (free list) tutar, uygun boyutta boşluk arar, blokları böler ve birleştirir. Bu arama ve muhasebe, stack tahsisinden onlarca kat pahalıdır.

Heap'in iki kronik derdi vardır. Birincisi **fragmentation** (parçalanma): sürekli tahsis-serbest bırakma döngüsü, belleği delik deşik bırakır; toplam boş alan yeterli olsa bile ardışık büyük bir blok bulunamayabilir. İkincisi ise ömür yönetimidir: heap'teki bir bloğun ne zaman artık kimsenin işine yaramadığını heap kendisi bilmez. Bu bilgiyi ya programcı sağlamalı, ya da bir garbage collector çıkarsamalıdır. Bu makalenin geri kalanı, esasen bu ikinci derdin farklı çözümlerinin hikayesidir.

## Manuel Bellek Yönetimi: Tam Kontrol, Tam Sorumluluk

Manuel modelde belleği programcı açıkça talep eder ve açıkça iade eder. C'de `malloc`/`free`, C++'ta `new`/`delete` bunun tipik örnekleridir.

```c
char *buffer = malloc(1024);   // 1024 byte iste
if (buffer == NULL) { /* tahsis basarisiz, ele al */ }
// ... buffer kullanilir ...
free(buffer);                  // belleği geri ver
buffer = NULL;                 // sarkan işaretçiyi engelle
```

Bu modelin cazibesinin kök nedeni **belirlenebilirliktir (determinism)**. Bellek, siz `free` dediğiniz anda serbest kalır; ne bir saniye önce ne bir saniye sonra. Araya beklenmedik bir duraklama giren bir çalışma zamanı yoktur. Bu yüzden gerçek zamanlı sistemler, işletim sistemi çekirdekleri, gömülü cihazlar ve oyun motorlarının sıcak döngüleri manuel yönetimi tercih eder: gecikme (latency) öngörülebilir olmalıdır.

Bu kontrolün bedeli ise, insan hafızasının hataya açıklığıdır. Manuel yönetimin üç büyük tuzağı şunlardır:

- **Bellek sızıntısı (memory leak):** `free` çağrısını unutmak. Program çalıştıkça heap şişer, sonunda bellek tükenir. Uzun ömürlü sunucularda bu, saatler içinde çökmeye yol açar.
- **Sarkan işaretçi (dangling pointer) ve use-after-free:** Serbest bıraktığınız bir bloğa erişmeye devam etmek. Blok başka bir amaç için yeniden tahsis edilmiş olabileceğinden, veri bozulur; daha kötüsü, saldırganlar use-after-free zafiyetlerini kod çalıştırmaya çevirebilir. Bu, gerçek dünyadaki güvenlik açıklarının büyük bir dilimini oluşturur.
- **Çift serbest bırakma (double free):** Aynı bloğu iki kez `free` etmek. Allocator'ın iç muhasebesini bozar, çoğu zaman istismar edilebilir bir çökmeyle sonuçlanır.

Bu hataların ortak kök nedeni tektir: **ömür (lifetime) bilgisi kodun içine dağılmıştır ve derleyici bunu doğrulamaz.** Bir bloğun kime ait olduğu, kimin onu serbest bırakmakla yükümlü olduğu, hangi işaretçilerin hâlâ geçerli olduğu — bunların hepsi programcının zihnindedir. Kod büyüdükçe bu zihinsel model tutarlılığını yitirir. Manuel yönetimin tarihi, bir bakıma bu zihinsel yükü araçlara devretme çabasının tarihidir.

## Otomatik Yönetim: Sorumluluğu Çalışma Zamanına Devretmek

Otomatik bellek yönetiminin temel fikri şudur: hangi belleğin artık **erişilebilir (reachable)** olmadığını tespit etmeyi çalışma zamanına yaptır ve onu programcının müdahalesi olmadan geri kazan. Buradaki anahtar kavram **erişilebilirliktir**: eğer programın kök kümesinden (root set — global değişkenler, aktif stack frame'lerdeki yerel değişkenler, register'lar) başlayarak işaretçileri takip ederek bir nesneye ulaşamıyorsanız, o nesne artık kullanılamaz demektir; çünkü ona ulaşacak hiçbir yol kalmamıştır. Dolayısıyla güvenle geri kazanılabilir.

İki büyük otomatik yaklaşım vardır: referans sayımı ve izleyici (tracing) toplayıcılar. İkisi de aynı hedefe farklı yollardan varır.

### Referans Sayımı (Reference Counting)

Referans sayımında her nesne, kendisine kaç işaretçinin işaret ettiğini tutan bir sayaç (refcount) taşır. Bir referans oluştuğunda sayaç bir artar, bir referans yok olduğunda bir azalır. Sayaç sıfıra düştüğü an, nesneye ulaşacak kimse kalmamış demektir; nesne hemen serbest bırakılır.

```
p = new Nesne()      // Nesne.refcount = 1
q = p                // refcount = 2
p = null             // refcount = 1
q = null             // refcount = 0  -> nesne yikilir
```

Bu yaklaşımın en büyük avantajı **belirlenebilirlik ve dağıtılmış maliyettir**. Nesne, artık kullanılmaz olduğu anda yıkılır; uzun bir toplama duraklaması beklemez. Maliyet, programın normal akışına küçük parçalar halinde yayılır. Python'ın CPython yorumlayıcısı ve C++'ın `shared_ptr`'ı bu modeli kullanır.

Ancak referans sayımının iki ciddi zaafı vardır ve ikisi de kök nedenlerinden doğar:

**Döngüsel referanslar (reference cycles).** İki nesne birbirini işaret ediyorsa, dış dünyadan ikisine de ulaşılamasa bile sayaçları asla sıfıra düşmez. A, B'yi; B de A'yı tutuyorsa, her ikisinin sayacı 1'de takılı kalır ve ikisi de sızar. Bu, referans sayımının doğuştan gelen kör noktasıdır; çünkü "sayaç sıfır mı" testi yereldir, oysa döngü küresel bir olgudur. Bunun için ya programcı döngüleri kırmak üzere **zayıf referanslar (weak references)** kullanır — sayacı artırmayan, dolayısıyla ömür üzerinde söz sahibi olmayan işaretçiler — ya da çalışma zamanı, döngüleri yakalamak için ayrıca bir tracing toplayıcı çalıştırır. CPython tam olarak bunu yapar: temel mekanizması referans sayımı olsa da, döngüleri temizlemek için ek bir döngü toplayıcısı (cycle collector) barındırır.

**Sayaç güncellemenin maliyeti.** Her referans atamasında sayacı değiştirmek, özellikle çok çekirdekli sistemlerde pahalıdır. Sayaç güncellemeleri atomik (thread-safe) olmak zorundaysa, her atama bir senkronizasyon işlemine dönüşür ve cache tutarlılığı trafiği yaratır. Bu yüzden yoğun paralel iş yüklerinde saf referans sayımı, iyi ayarlanmış bir tracing toplayıcıdan yavaş kalabilir.

### İzleyici Toplama: Mark-Sweep

Tracing (izleyici) toplayıcılar farklı bir felsefeyi benimser: sayaç tutmak yerine, belleği geri kazanma zamanı geldiğinde tüm nesne grafiğini kök kümesinden başlayarak dolaş ve erişilebilir olanları işaretle. Bunun klasik biçimi **mark-sweep** (işaretle-süpür) algoritmasıdır ve iki aşamadan oluşur:

1. **Mark (işaretleme):** Kök kümesinden başlayarak işaretçiler takip edilir; ulaşılan her nesne "canlı" olarak işaretlenir. Bu, aslında nesne grafiği üzerinde bir graf gezintisidir (genellikle derinlik-öncelikli).
2. **Sweep (süpürme):** Heap'in tamamı baştan sona taranır; işaretlenmemiş her nesne serbest bırakılır, işaretlenmiş olanların işareti bir sonraki tur için sıfırlanır.

Mark-sweep'in referans sayımına göre büyük üstünlüğü, **döngüleri hiç zahmetsiz halletmesidir.** Erişilebilirlik köklerden hesaplandığı için, birbirini işaret eden ama dışarıdan ulaşılamayan bir nesne kümesi doğal olarak işaretlenmez ve süpürülür. Ayrıca normal program akışında sayaç güncelleme yükü yoktur.

Bunun bedeli ise **duraklamadır (pause).** Naif mark-sweep, çalışırken programı durdurmak zorundadır; buna **stop-the-world** denir. Kök nedeni şudur: toplayıcı nesne grafiğini gezerken program aynı anda grafiği değiştirirse (bir işaretçiyi yeniden atarsa), toplayıcı yanlış bir anlık görüntü üzerinde çalışır ve canlı bir nesneyi ölü sanıp süpürebilir — ki bu felaket olur. Heap büyüdükçe bu duraklamalar uzar; işte bu, otomatik yönetimin "beklenmedik takılma" itibarının kaynağıdır.

### Fragmentation ve Kopyalayan/Sıkıştıran Toplayıcılar

Mark-sweep, süpürdüğü boşlukları serbest listeye ekler ama nesneleri yerinde bırakır; dolayısıyla parçalanma sorununu çözmez. Bunu aşmak için **kopyalayan (copying)** ve **sıkıştıran (compacting)** toplayıcılar geliştirilmiştir. Bir kopyalayan toplayıcı, canlı nesneleri belleğin bir yarısından diğerine yan yana taşır; süpürme aşaması bir bütün olarak eski yarıyı geçersiz kılmaya indirgenir ve parçalanma tümüyle ortadan kalkar. Bedeli, aynı anda belleğin yaklaşık yarısının yedekte tutulmasıdır.

### Nesillere Dayalı Toplama (Generational GC)

Modern toplayıcıların çoğu, ampirik bir gözleme dayanan **nesil hipotezine (generational hypothesis)** yaslanır: "Nesnelerin büyük çoğunluğu genç ölür." Yani yeni tahsis edilen nesnelerin ezici bir kısmı çok kısa ömürlüdür (bir döngüdeki geçici nesneler, ara sonuçlar), buna karşılık uzun süre yaşayanlar genellikle daha da uzun yaşar.

Bu gözlem güçlü bir optimizasyona kapı açar: heap'i nesillere (genç ve yaşlı) böl ve toplama işini ağırlıklı olarak genç nesil üzerinde, sık ama küçük çaplı yap. Genç nesil küçüktür, çoğu nesne zaten ölmüştür, dolayısıyla bu "minor GC" hızlı ve ucuzdur. Nadiren, tüm heap'i tarayan pahalı bir "major GC" yapılır. Bu strateji, ortalama toplama maliyetini ciddi biçimde düşürür ve JVM ile .NET'in yüksek verimli toplayıcılarının temelini oluşturur. İnceliklerinden biri, yaşlı bir nesnenin genç bir nesneyi işaret ettiği durumları kaydeden bir yapıdır (write barrier ile beslenen "remembered set"); böylece genç nesil, tüm yaşlı nesli taramadan doğru şekilde toplanabilir.

### Eşzamanlı ve Artımlı Toplayıcılar

Stop-the-world duraklamalarını azaltmak için modern toplayıcılar (JVM'de G1, ZGC, Shenandoah; Go'nun toplayıcısı) işi programla **eşzamanlı (concurrent)** ve **artımlı (incremental)** yürütmeye çalışır. Buradaki temel zorluk, yukarıda değinilen tutarlılık sorunudur: program çalışırken grafiği değiştirdiği için, toplayıcının "canlı bir nesneyi kaçırmama" garantisini koruması gerekir. Bunu sağlamak için **write barrier** denen küçük kod parçaları, program bir işaretçiyi güncellediğinde toplayıcıyı haberdar eder. Böylece toplama, kısa duraklamalarla veya neredeyse duraklamasız yürütülebilir — ama karşılığında normal program akışına küçük bir sürekli maliyet biner. Burada temel bir denge (trade-off) vardır: verimi (throughput) mü yoksa gecikme tutarlılığını mı (latency) önceliyorsunuz? Toplu veri işleyen bir arka uç ile düşük gecikme gerektiren bir işlem sistemi bu soruya farklı cevaplar verir ve farklı toplayıcı seçer.

## Ownership: Üçüncü Yol

Manuel yönetim tam kontrol verir ama güvenliği insana bırakır; garbage collection güvenliği garanti eder ama çalışma zamanı maliyeti ve duraklama getirir. Rust'ın **ownership** (sahiplik) modeli, üçüncü bir yol önerir: **ömür kurallarını derleyiciye doğrulattır, hiçbir çalışma zamanı toplayıcı olmasın.** Bu, "sıfır maliyetli soyutlama" (zero-cost abstraction) felsefesinin bellek yönetimine uygulanmış halidir.

Rust'ın ownership sistemi üç kurala dayanır:

1. Her değerin tam olarak bir **sahibi (owner)** vardır.
2. Aynı anda yalnızca tek bir sahip olabilir.
3. Sahip kapsam dışına çıktığında (scope'tan düştüğünde), değer otomatik olarak yıkılır (drop edilir).

Bu üçüncü kural aslında C++'taki RAII (Resource Acquisition Is Initialization) fikrinin ta kendisidir: bir kaynağın ömrünü bir nesnenin ömrüne bağlamak. Nesne yok olduğunda kaynağı serbest bırakan yıkıcı (destructor) çalışır. RAII, C++'ta `unique_ptr` ile de kullanılan güçlü bir kalıptır; Rust bunu dilin varsayılan ve zorunlu davranışı yapar.

Ownership'in kök gücü, ömür bilgisini programcının zihninden alıp **tip sistemine** yerleştirmesidir. Böylece use-after-free, double-free ve veri yarışları (data races) gibi hataların büyük kısmı, program çalışmadan önce, derleme zamanında yakalanır.

```rust
let s1 = String::from("merhaba");
let s2 = s1;              // sahiplik s1'den s2'ye TASINIR (move)
// println!("{}", s1);   // DERLEME HATASI: s1 artik gecerli degil
```

Burada `s1 = s2` bir kopya değil bir **taşımadır (move)**: sahiplik devredilir ve `s1` geçersiz kılınır. Bu sayede iki değişken aynı bellek bloğunu sahiplenip sonunda ikisi de onu serbest bırakmaya (double free) kalkışamaz. Sorun, tasarımdan silinmiştir.

Her şeyi taşımak pratik olmayacağından, Rust **ödünç alma (borrowing)** kavramını getirir: bir değere sahiplenmeden geçici referans almak. Borrow checker denen derleyici bileşeni burada iki kuralı zorlar: aynı anda ya birden çok değişmez (immutable) referans, ya da tek bir değiştirilebilir (mutable) referans olabilir; ikisi bir arada olamaz. Bu kuralın kök amacı, bir yerde okuma yapılırken başka bir yerde yazma yapılmasını — yani veri yarışlarını ve fark edilmeden geçersizleşen referansları — engellemektir.

```rust
let mut v = vec![1, 2, 3];
let ilk = &v[0];         // degismez odunc
v.push(4);               // DERLEME HATASI: v'yi degistirmek icin
                         // aktif bir odunc varken mutable erisim alinamaz
println!("{}", ilk);
```

Bu örnekteki hata kritiktir: `push`, vektörün kapasitesini aşarsa iç tamponu yeni bir bellek bölgesine taşıyabilir; bu durumda `ilk` referansı serbest bırakılmış eski belleği gösterir hale gelirdi — klasik bir use-after-free. C++'ta bu sessizce derlenir ve çalışma zamanında patlar; Rust'ta derleyici baştan reddeder.

Ownership'in bedeli ise **öğrenme eğrisi ve ifade kısıtıdır.** Borrow checker'ı memnun etmek, özellikle döngüsel veri yapıları veya paylaşımlı durum içeren tasarımlarda zahmetli olabilir. Gerçekten paylaşımlı sahiplik gerektiğinde Rust, referans sayımlı `Rc` (tek iş parçacığı) ve atomik `Arc` (çok iş parçacığı) tiplerini sunar — yani ihtiyaç halinde referans sayımına açıkça geri döner. Döngüsel referans sorunu burada yeniden belirir ve `Weak` tipiyle çözülür. Yani ownership, referans sayımını yok etmez; onu varsayılan olmaktan çıkarıp yalnızca gerçekten gerektiğinde ödenen bir seçeneğe dönüştürür.

## Yaygın Hatalar ve Yanlış Kanılar

Bellek yönetiminde en sık düşülen hatalar, çoğu zaman modellerin sınırlarını yanlış anlamaktan kaynaklanır:

- **"GC var, o yüzden sızıntı olmaz" yanılgısı.** Garbage collection yalnızca *erişilemez* belleği toplar. Erişilebilir ama artık işe yaramayan bellek — örneğin bir listeye eklenip hiç çıkarılmayan nesneler, temizlenmeyen cache'ler, kaldırılmayan event listener'lar — pekala sızar. Bunlar "mantıksal sızıntılardır" ve GC bunları göremez, çünkü teknik olarak hâlâ erişilebilirler.
- **Bitişik olmayan kaynakları GC'ye emanet etmek.** GC yalnızca *belleği* yönetir; dosya tanıtıcıları (file descriptor), ağ soketleri, veritabanı bağlantıları, kilitler (lock) gibi bellek dışı kaynakları yönetmez. Bunların ne zaman serbest kalacağı, toplayıcının ne zaman çalışacağına bağlı bırakılırsa öngörülemez olur. Bu yüzden bu kaynaklar açık (explicit) biçimde — `try-with-resources`, `using`, `defer`, `with` gibi yapılarla — kapatılmalıdır. RAII/ownership dilleri bu sorunu doğal çözer.
- **Yıkıcı (finalizer) mantığına güvenmek.** GC dillerindeki finalizer'lar ne zaman, hatta çalışıp çalışmayacakları belirsiz olduğu için kaynak temizliği için güvenilmezdir. Kritik temizlik hiçbir zaman finalizer'a bırakılmamalıdır.
- **Manuel yönetimde sahiplik belirsizliği.** Bir C API'sinden dönen işaretçiyi kimin serbest bırakacağı belirsizse hata kaçınılmazdır. İyi tasarlanmış API'ler sahiplik sözleşmesini belgeler: "çağıran serbest bırakır" mı, "kütüphane serbest bırakır" mı?
- **GC'yi elle tetiklemeye çalışmak.** Çoğu ortamda toplayıcıyı zorla çağırmak (örneğin `System.gc()`) çoğunlukla zararlıdır; toplayıcının kendi buluşsal yöntemlerini bozar ve gereksiz bir tam duraklamaya yol açar.

## En İyi Pratikler

Bellek yönetiminde doğru yaklaşım, tek bir "en iyi" modele bağlanmak değil, işin gereğine göre model seçmektir:

- **Doğru aracı seçin.** Öngörülebilir düşük gecikme ve tam kontrol gerektiğinde (çekirdek, gömülü, gerçek zamanlı) manuel yönetim veya ownership; geliştirici verimliliği ve güvenliğin öncelikli olduğu iş uygulamalarında GC mantıklıdır. Ownership, bu ikilinin dışına çıkıp "hem güvenlik hem sıfır çalışma zamanı maliyeti" isteyenler için güçlü bir seçenektir.
- **Ömrü mümkün olduğunca stack'e taşıyın.** Heap tahsisi pahalı ve yönetimi risklidir. Kısa ömürlü, boyutu bilinen veriyi stack'te tutmak hem hızlıdır hem de ömür yönetimini tümüyle ortadan kaldırır.
- **RAII / kapsam tabanlı temizlik kullanın.** Kaynağın ömrünü bir kapsamın ömrüne bağlamak (C++ `unique_ptr`, Rust ownership, Python `with`, C# `using`) sızıntıları ve unutulan serbest bırakmaları yapısal olarak engeller.
- **Sahipliği açıkça ifade edin.** Manuel yönetimli kodda bile "bu belleğin sahibi kim" sorusunun her zaman net bir cevabı olmalı. Akıllı işaretçiler (`unique_ptr`, `shared_ptr`) bu niyeti tip düzeyinde belgeler.
- **Döngüsel referanslara karşı zayıf referans kullanın.** Referans sayımlı sistemlerde (Python, `shared_ptr`, `Rc`) ebeveyn-çocuk gibi geri işaret eden ilişkilerde zayıf referans kullanarak döngü sızıntılarını önleyin.
- **Araçlarla doğrulayın.** Bellek hatalarını gözle bulmak çok zordur. Sanitizer'lar (adres ve sızıntı denetleyicileri) ve profil çıkarma araçları, sızıntıları ve use-after-free hatalarını çalışma zamanında yakalar. GC ortamlarında heap profil araçları, mantıksal sızıntıların kaynağını ortaya çıkarır.
- **Tahsis desenlerini ölçün.** Sıcak yollarda aşırı tahsis, hem manuel hem GC sistemlerinde en büyük performans sorunudur. Nesne havuzları (object pooling) ve tahsisi azaltan tasarımlar, GC baskısını ve allocator maliyetini birlikte düşürür.

## Sonuç

Bellek yönetiminin bütün hikayesi, tek bir gerilimin farklı çözümleridir: **kontrol ile güvenlik arasındaki denge.** Manuel yönetim en yüksek kontrolü verir ama ömür doğrulamasını kırılgan insan hafızasına bırakır. Referans sayımı, ömür kararını yerel ve belirlenebilir kılar ama döngüler karşısında kör kalır ve sayaç maliyeti taşır. Mark-sweep tabanlı garbage collection, erişilebilirliği köklerden hesaplayarak döngüleri de çözer ve programcıyı tümüyle sorumluluktan kurtarır — ama duraklama ve çalışma zamanı maliyetini geri getirir; modern nesil-tabanlı ve eşzamanlı toplayıcılar bu bedeli büyük ölçüde ehlileştirir. Ownership ise ömür kurallarını derleyiciye taşıyarak hem güvenliği hem de sıfır çalışma zamanı maliyetini aynı anda hedefler; bedeli, geliştiriciden daha disiplinli bir düşünce talep etmesidir.

Uzman gözüyle asıl mesaj şudur: bu yaklaşımlar birbirinin rakibi değil, farklı kısıtlar altında doğru olan farklı cevaplardır. İyi bir mühendis, elindeki işin gecikme, güvenlik, verim ve geliştirme hızı gereksinimlerini okuyup doğru modeli — ya da modellerin doğru bileşimini — seçer. Belleğin ne zaman geri verileceğine kimin karar vereceği sorusunun evrensel bir cevabı yoktur; yalnızca bağlama en uygun cevabı vardır.
