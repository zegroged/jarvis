# Linker ve Loader: Bağlayıcı ve Yükleyici

## Giriş ve Tanım

Bir kaynak dosyayı derleyip çalıştırdığımızda aslında birkaç bağımsız aşamadan geçen bir zincir işler. Derleyici (compiler) kaynak kodu makine koduna çevirir, ama tek bir `.c` dosyasından üretilen makine kodu genellikle kendi başına çalışamaz: `printf` gibi başka dosyalarda tanımlı fonksiyonlara, global değişkenlere, kütüphane çağrılarına referans verir ama bunların gerçek adreslerini bilmez. İşte bu boşluğu **linker** (bağlayıcı) ve **loader** (yükleyici) doldurur.

**Linker**, derleyicinin ürettiği birden çok nesne dosyasını (object file) ve kütüphaneyi alıp, aralarındaki sembolik referansları çözerek tek bir yürütülebilir dosya (executable) veya paylaşımlı kütüphane üreten programdır. **Loader** ise işletim sisteminin bir parçasıdır; yürütülebilir dosyayı diskten okuyup belleğe (process address space) yerleştiren, gerekli düzeltmeleri yapan ve programın giriş noktasına (entry point) sıçrayan bileşendir.

Kısaca: linker "derleme zamanında" (build-time) parçaları birleştirir; loader "çalışma zamanında" (runtime) o birleşmiş ürünü belleğe taşır ve çalışabilir hale getirir. Bu ikisi arasındaki iş bölümü, modern yazılımın nasıl paketlendiğini, dağıtıldığını ve güvenlik açısından nasıl davrandığını anlamanın anahtarıdır.

## Kök Neden: Neden Ayrı Bir Bağlama Adımına İhtiyaç Var?

Derleyicinin neden tek başına çalıştırılabilir üretemediğini anlamak, tüm konunun temelidir.

### Ayrık derleme (separate compilation) zorunluluğu

Büyük bir projede yüzlerce kaynak dosya bulunur. Eğer derleyici her seferinde tüm programı tek parça olarak işlemek zorunda olsaydı, tek bir satır değiştirdiğinizde milyonlarca satırı yeniden derlemeniz gerekirdi. Ayrık derleme sayesinde her dosya bağımsız olarak `.o` (Unix) veya `.obj` (Windows) nesne dosyasına çevrilir; sonra sadece değişen dosyalar yeniden derlenir ve linker hepsini birleştirir. Bu, `make` gibi build sistemlerinin var olma sebebidir.

Fakat ayrık derlemenin bir bedeli vardır: `dosya_a.c` içindeki kod, `dosya_b.c` içindeki `hesapla()` fonksiyonunu çağırdığında, derleyici `dosya_a.c`'yi işlerken `hesapla()`'nın bellekteki adresini **bilemez**, çünkü o fonksiyon henüz derlenmemiş veya derlense bile nihai yerleşimi belli değildir. Derleyici bu durumda adres yerine bir **yer tutucu (placeholder)** koyar ve "burada `hesapla` adında bir sembole ihtiyaç var" diye bir kayıt bırakır. İşte bu kayıtları çözmek linker'ın asıl görevidir.

### Yer değiştirme (relocation) sorunu

Derleyici kod üretirken, her fonksiyonun ve değişkenin belleğin en başından (adres 0) başladığını varsayar. Ama gerçekte iki nesne dosyasını yan yana koyduğunuzda ikisi birden adres 0'da olamaz. Linker, her parçayı nihai bir adrese yerleştirirken içindeki tüm adres referanslarını bu yeni konuma göre düzeltmek (relocate etmek) zorundadır. Bu düzeltme bilgisi, nesne dosyasındaki **relocation table** (yer değiştirme tablosu) içinde saklanır.

## Semboller: Bağlamanın Para Birimi

Linker'ın çalışabilmesi için her nesne dosyası iki liste taşır ve bunlar **symbol table** (sembol tablosu) içinde tutulur:

- **Tanımlanan semboller (defined / exported):** Bu dosyanın başkalarına sunduğu isimler. Örneğin `hesapla()` fonksiyonunu tanımlayan dosya, `hesapla` sembolünü "burada, şu offset'te" diye dışa açar.
- **Tanımlanmayan semboller (undefined / imported):** Bu dosyanın başka yerden beklediği isimler. `printf` çağıran bir dosyada `printf` tanımsız bir semboldür.

Linker'ın çekirdek mantığı basittir ama güçlüdür: tüm nesne dosyalarındaki tanımsız sembolleri, başka dosyalardaki tanımlı sembollerle **eşleştirmek**. Her tanımsız sembol için bir tanım bulunması gerekir; bulunamazsa meşhur `undefined reference to 'hesapla'` hatası alırsınız. Aynı sembolün iki farklı yerde tanımlanması ise `multiple definition` (çoklu tanım) hatasına yol açar.

### Güçlü ve zayıf semboller (strong / weak symbols)

C/C++ dünyasında her sembol "güçlü" ya da "zayıf" olabilir. Kaba bir kural olarak: başlatılmış (initialized) global değişkenler ve fonksiyonlar güçlü, başlatılmamış globaller ise geleneksel olarak zayıf sayılır. Bir güçlü ve bir zayıf sembol çakışırsa güçlü olan kazanır; iki güçlü sembol çakışırsa hata verilir. Bu davranış, C'de aynı isimli global değişkeni yanlışlıkla iki dosyada tanımladığınızda ortaya çıkan sinsi hataların kök nedenidir; bu yüzden global değişkenlerin `extern` ile bir başlık dosyasında bildirilip yalnızca tek bir `.c` dosyasında tanımlanması gerekir.

### Sembol karıştırma (name mangling)

C++'ta fonksiyon aşırı yükleme (overloading) olduğu için `topla(int,int)` ve `topla(double,double)` aynı isme sahip ama farklı fonksiyonlardır. Linker sembolleri düz metin olarak eşleştirdiğinden, derleyici bu iki fonksiyonu ayırt etmek için isimlerini tip bilgisiyle **karıştırır (mangle eder)**. Bu yüzden `nm` ile bir C++ nesne dosyasına baktığınızda `_Z5toplaii` gibi okunması zor semboller görürsünüz. `extern "C"` bildirimi bu karıştırmayı kapatır ve C tarafıyla uyumu sağlar; C kütüphanelerini C++'tan çağırırken bu yüzden `extern "C"` kullanılır.

## Nesne Dosya Formatları: ELF ve PE

Nesne dosyaları ve yürütülebilirler, platforma göre standart bir formata sahiptir. İki büyük format vardır:

- **ELF (Executable and Linkable Format):** Linux, BSD ve çoğu Unix benzeri sistemde kullanılır.
- **PE (Portable Executable):** Windows'ta `.exe` ve `.dll` dosyalarının formatıdır; COFF formatının bir uzantısıdır. macOS ise bunlardan farklı olarak **Mach-O** formatını kullanır.

### ELF'in yapısı

ELF dosyası bir **ELF header** ile başlar; bu başlık dosyanın 32 mi 64 bit mi olduğunu, hedef mimariyi, giriş noktası adresini ve iki önemli tablonun konumunu belirtir. İçerik **section** (bölüm) ve **segment** kavramları etrafında düzenlenir ve bu ayrım linker/loader iş bölümünü çok güzel yansıtır:

- **Section'lar** linker'a hitap eder ve derleme/bağlama zamanında anlamlıdır. Tipik bölümler: `.text` (çalıştırılabilir makine kodu), `.data` (başlatılmış global veriler), `.bss` (başlatılmamış, sıfırla dolacak veriler — dosyada yer kaplamaz, sadece boyutu tutulur), `.rodata` (salt-okunur veriler, string sabitleri), `.symtab` (sembol tablosu), `.rela.text` gibi relocation bölümleri.
- **Segment'ler** loader'a hitap eder ve **program header table** ile tanımlanır. Loader dosyayı bölüm bölüm değil, segment segment belleğe haritalar (map eder). Her segment'in bir izin kümesi vardır: kod segmenti okunur+çalıştırılır (r-x), veri segmenti okunur+yazılır (rw-).

`.bss`'in dosyada yer kaplamaması güzel bir optimizasyondur: bir milyon elemanlık sıfırlanmış bir global dizi tanımlarsanız, bu diskteki dosyayı bir megabayt büyütmez; loader çalışma zamanında o bölgeyi sıfırlarla doldurur. Bu, "neden sıfır başlatılmış globaller çalıştırılabilir dosyayı şişirmiyor?" sorusunun cevabıdır.

### PE'nin yapısı

PE dosyası tarihsel nedenlerle bir MS-DOS başlığıyla başlar (o meşhur "This program cannot be run in DOS mode" mesajını basan stub), ardından PE imzası, COFF başlığı ve **section table** gelir. PE'nin kendine has kavramları vardır: **import table** (bu dosyanın hangi DLL'lerden hangi fonksiyonları çağırdığını listeler) ve **export table** (bir DLL'in dışa açtığı fonksiyonlar). Ayrıca PE, tercih edilen bir yükleme adresi (`ImageBase`) taşır; eğer o adres doluysa loader dosyayı başka yere taşımak zorunda kalır ve bu **base relocation** ihtiyacını doğurur.

## Statik Bağlama (Static Linking)

Statik bağlamada, programın kullandığı kütüphane kodu **derleme zamanında** doğrudan yürütülebilir dosyanın içine kopyalanır. Bir `.a` (Unix arşivi) veya `.lib` (Windows) statik kütüphanesi, aslında bir sürü `.o` dosyasının bir araya getirilmiş arşividir.

Statik kütüphanelerde ince ama önemli bir davranış vardır: linker bir arşivi işlerken, arşivin **tamamını** değil, yalnızca o an çözülmemiş sembolleri karşılayan üye dosyaları çeker. Bu yüzden komut satırında kütüphanelerin **sırası önemlidir**: linker soldan sağa ilerler ve bir kütüphaneyi geçtikten sonra ortaya çıkan yeni bir tanımsız sembol o kütüphaneden karşılanamaz. Klasik `undefined reference` hatalarının önemli bir kısmı, kütüphanenin onu kullanan nesne dosyasından önce yazılmasından kaynaklanır; kural olarak kütüphaneler bağımlılık zincirinde onları kullananlardan **sonra** gelir.

### Statik bağlamanın avantajları ve bedeli

Avantajı, ürünün kendine yeterli (self-contained) olmasıdır: çalıştırılabilir, ihtiyaç duyduğu tüm kodu içinde taşır, hedef makinede doğru kütüphane sürümünün kurulu olup olmadığına bağlı değildir. Bu, dağıtım kolaylığı ve sürüm çakışması ("DLL hell") riskinin ortadan kalkması demektir.

Bedeli ise şudur: her program aynı kütüphane kodunun kendi kopyasını taşır. Yüz farklı program `libc`'yi statik bağlarsa, diskte ve bellekte yüz kopya `libc` bulunur. Ayrıca kütüphanede kritik bir güvenlik açığı kapatıldığında, statik bağlı tüm programların **yeniden derlenip yeniden dağıtılması** gerekir; sadece kütüphaneyi güncellemek yetmez. Bu, statik bağlamanın en ciddi bakım ve güvenlik dezavantajıdır.

## Dinamik Bağlama (Dynamic Linking)

Dinamik bağlamada kütüphane kodu yürütülebilirin içine kopyalanmaz. Bunun yerine, çalıştırılabilir dosyada yalnızca "şu kütüphaneden şu sembollere ihtiyacım var" bilgisi tutulur; gerçek kod, çalışma zamanında ayrı bir paylaşımlı kütüphaneden (Unix'te `.so` — shared object, Windows'ta `.dll` — dynamic link library) yüklenir.

### Neden dinamik bağlama tercih edilir

Kök mantığı, **paylaşımdır**. Sistemdeki tüm programlar tek bir `libc.so`'yu kullanır. İşletim sistemi bu kütüphanenin kod segmentini fiziksel bellekte **bir kez** tutup, onu kullanan tüm process'lerin adres uzayına haritalar (memory-mapped, copy-on-write ile). Böylece elli program çalışsa da `libc`'nin salt-okunur kod sayfaları bellekte tek kopya durur. Bu, dinamik bağlamanın bellek verimliliği argümanıdır.

İkinci büyük avantaj güvenliktir: `libc`'de bir açık kapatıldığında, sadece paylaşımlı kütüphaneyi güncellersiniz; ona bağlı tüm programlar bir sonraki çalıştırılışlarında düzeltilmiş kodu otomatik olarak kullanır. Yeniden derleme gerekmez. Modern işletim sistemlerinin güvenlik güncellemelerinin bu kadar etkili olmasının bir nedeni budur.

### PIC, GOT ve PLT: dinamik bağlamanın makinesi

Paylaşımlı kütüphane bellekte hangi adrese yükleneceğini önceden bilemez (aynı `.so` farklı process'lerde farklı adreslere düşebilir). Bu yüzden paylaşımlı kütüphane kodu **PIC (Position Independent Code — konumdan bağımsız kod)** olarak derlenir; yani mutlak adreslere değil, göreli (relative) adreslemeye dayanır. Bunu çözmek için iki tablo devreye girer:

- **GOT (Global Offset Table):** Global veri ve dış sembollerin gerçek adreslerinin tutulduğu, çalışma zamanında doldurulan bir tablo. Kod, bir sembolün adresini doğrudan gömmez; GOT üzerinden dolaylı olarak erişir. Loader, yükleme sırasında gerçek adresleri bu tabloya yazar.
- **PLT (Procedure Linkage Table):** Fonksiyon çağrıları için bir dolaylandırma katmanı. Bir fonksiyonu ilk kez çağırdığınızda PLT, dinamik linker'ı çağırıp sembolü çözdürür ve sonucu GOT'a yazar; sonraki çağrılar doğrudan çözülmüş adrese gider. Buna **lazy binding** (tembel bağlama) denir: her sembol ancak gerçekten çağrıldığında çözülür, program başlangıcında hepsi birden çözülmez, bu da başlangıcı hızlandırır.

### Dinamik bağlamanın bedelleri

Dinamik bağlamanın da maliyetleri vardır. Birincisi başlangıç maliyeti: program çalışırken dinamik linker (Linux'ta genelde `ld.so` veya `ld-linux.so` benzeri bir bileşen) devreye girip bağımlılıkları bulmalı, yüklemeli ve sembolleri çözmelidir. İkincisi çalışma zamanı bağımlılığı: hedef makinede uyumlu kütüphane bulunmazsa program hiç başlamaz (`error while loading shared libraries` mesajı). Üçüncüsü meşhur bağımlılık cehennemi: farklı programlar aynı kütüphanenin uyumsuz sürümlerini isteyebilir. Unix dünyası bunu **soname** ve sürüm numaralı sembol mekanizmalarıyla, birden çok sürümü yan yana bulundurarak yönetir.

## Yükleme (Loading): Program Belleğe Nasıl Girer?

Bir yürütülebilir dosyayı çalıştırdığınızda kabaca şu adımlar işler. İşletim sistemi çekirdeği (kernel) yeni bir process için sanal adres uzayı oluşturur ve dosyanın başlığını okuyup formatı doğrular. Ardından program header'daki segment'leri belleğe **haritalar**: kod segmentini salt-okunur+çalıştırılabilir, veri segmentini okunur+yazılır olarak. Burada önemli bir nokta, modern sistemlerin **demand paging** kullanmasıdır: tüm dosya baştan belleğe okunmaz; sayfalara ilk erişildiğinde diskten getirilir (page fault ile). Bu yüzden büyük bir program bile neredeyse anında "başlar" gibi görünür.

Eğer dosya dinamik bağlıysa, kernel doğrudan programın giriş noktasına atlamaz; önce **dinamik linker/loader**'ı belleğe alır ve kontrolü ona verir. Dinamik linker gerekli tüm paylaşımlı kütüphaneleri (ve onların bağımlılıklarını, özyinelemeli olarak) bulup haritalar, GOT'u doldurur (veya lazy binding için hazırlar), gerekli relocation'ları uygular ve ancak ondan sonra kontrolü asıl programa devreder. Program çalışmaya `main`'den değil, `_start` gibi bir başlangıç kodundan (C runtime, "crt0") başlar; bu kod global constructor'ları çalıştırıp ortamı hazırladıktan sonra `main`'i çağırır.

### ASLR ve güvenlik boyutu

Modern loader'lar güvenlik için **ASLR (Address Space Layout Randomization — adres uzayı düzeni rastgeleleştirme)** uygular: yığın (stack), öbek (heap), paylaşımlı kütüphaneler ve mümkünse ana yürütülebilir her çalıştırılışta rastgele adreslere yerleştirilir. Mantığı şudur: bir saldırgan buffer overflow gibi bir açığı sömürürken genellikle belirli bir kod parçasının veya fonksiyonun adresini bilmek zorundadır (örneğin return-oriented programming saldırılarında). Adresler rastgele olduğunda bu tahmin çok zorlaşır. ASLR'nin ana yürütülebilir için de çalışabilmesi, kodun konumdan bağımsız olmasını gerektirir; bu yüzden derlenen tam-konumdan-bağımsız yürütülebilirlere **PIE (Position Independent Executable)** denir ve birçok modern dağıtım varsayılan olarak PIE üretir. ASLR, veriyi çalıştırılamaz yapan **DEP/NX (No-eXecute)** bitiyle birlikte, çağdaş bellek güvenliği savunmasının temel iki taşından biridir.

## Somut Örnek: `hello.c`'nin Yolculuğu

Basit bir örnekle zinciri toparlayalım. `printf` çağıran bir `hello.c` dosyanız var.

1. **Derleme:** `hello.c` derlenip `hello.o` üretilir. Bu nesne dosyasında `main` tanımlı bir sembol, `printf` ise tanımsız bir semboldür. Kodda `printf`'in adresi yerine bir yer tutucu ve bir relocation kaydı vardır.
2. **Bağlama:** Linker `hello.o`'yu C çalışma zamanı başlangıç nesneleri ve C kütüphanesiyle birleştirir. `printf` sembolünü çözer. Statik bağlarsanız `printf`'in kodu doğrudan çıktıya kopyalanır; dinamik bağlarsanız (varsayılan davranış budur) çıktıya sadece "`libc`'ye bağımlıyım ve `printf`'e ihtiyacım var" bilgisi ile PLT/GOT altyapısı eklenir.
3. **Yükleme:** Çalıştırdığınızda loader dosyayı haritalar; dinamik durumda dinamik linker `libc.so`'yu bulup yükler, `printf` çağrısı ilk yapıldığında PLT üzerinden gerçek adres çözülür.

Bu farkı gözle görebilirsiniz: Linux'ta `ldd` komutu bir dosyanın hangi paylaşımlı kütüphanelere bağlı olduğunu listeler; statik bağlı bir dosyada "not a dynamic executable" benzeri bir çıktı alırsınız. `nm` sembolleri, `readelf` ve `objdump` ise ELF başlıklarını, bölümleri ve relocation tablolarını incelemek için kullanılır. (Windows tarafında Dependency Walker benzeri araçlar ve `dumpbin` aynı işi görür.) Bu araçların kesin bayraklarını hatırlamadığınızda man sayfasına bakmak en doğrusudur; ezberden bayrak uydurmak yerine aracın kendi belgesine güvenin.

## Yaygın Hatalar ve Tuzaklar

**"Undefined reference" hataları.** En sık karşılaşılan linker hatasıdır. Sebepleri: kütüphaneyi hiç bağlamamak (`-l` bayrağını unutmak), kütüphaneyi komut satırında yanlış sırada yazmak, ya da C++'ta bir başlıkta bildirilen ama hiçbir yerde tanımlanmayan bir fonksiyon. C ile C++ karıştırıldığında `extern "C"` unutmak da name mangling yüzünden bu hataya yol açar.

**"Multiple definition" hataları.** Aynı güçlü sembolün iki yerde tanımlanması. Sık rastlanan kök neden, bir başlık dosyasında `static` veya `inline` olmayan bir değişken/fonksiyon tanımı bulunması ve bu başlığın birden çok `.c` dosyasına dahil edilmesidir. Değişkenler başlıkta `extern` ile bildirilmeli, tanım tek bir kaynak dosyada olmalıdır.

**Çalışma zamanında "shared library not found".** Program derlenip bağlanır ama çalışırken kütüphane bulunamaz. Sebep genelde kütüphanenin loader'ın aradığı yollarda olmamasıdır. Kütüphane arama yolunu ortam değişkenleriyle geçici olarak değiştirmek mümkündür, ama üretimde bunun yerine kütüphaneyi standart konuma kurmak veya çalıştırılabilire gömülü arama yolu (RPATH/RUNPATH) kullanmak daha sağlıklıdır.

**Yanlış mimari / ABI uyuşmazlığı.** 32-bit bir nesne dosyasını 64-bit ile bağlamaya çalışmak, ya da farklı derleyici/standart-kütüphane sürümleriyle üretilmiş nesneleri karıştırmak sinsi hatalar üretir. Özellikle C++'ta ABI (Application Binary Interface) uyumsuzlukları — struct düzeni, isim karıştırma şeması veya standart kütüphane sürümü farkları — çalışma zamanında zor teşhis edilen çökmelere yol açabilir.

**Statik ve dinamik bağlamanın lisans boyutu.** Bir kütüphaneyi statik bağlamak bazen o kütüphanenin lisansı gereği tüm ürününüzü etkileyebilir (özellikle güçlü copyleft lisanslarda). Bu teknik değil ama pratikte gerçek bir tuzaktır; dağıtım kararı verirken kütüphanenin lisansına bakmak gerekir.

## En İyi Pratikler

**Doğru bağlama modelini bilinçli seçin.** Sistem geneline yayılacak, sık güncellenecek ve birçok programın paylaştığı kütüphaneler için dinamik bağlama; kendine yeterli, taşınabilir, bağımlılık ortamı öngörülemeyen dağıtımlar için (örneğin tek dosyalık bir araç ya da container imajını küçültme amacı) statik bağlama mantıklıdır. Karar, "hangisi daha iyi" değil, "hangi ödünleşim önceliğim" sorusudur: paylaşım ve güncellenebilirlik mi, yoksa taşınabilirlik ve bağımsızlık mı.

**Global durumdan kaçının.** Sembol çakışmalarının çoğu gereksiz global değişkenlerden doğar. Değişkenleri mümkün olan en dar kapsamda tutmak, dosyaya özel olanları `static` yapmak hem çakışmaları hem de istemsiz sembol sızıntısını engeller.

**Paylaşımlı kütüphanelerde sürümlemeye özen gösterin.** Bir `.so` yayınlıyorsanız soname ve sürüm numaralandırmasını doğru kullanmak, geriye dönük uyumluluğu (backward compatibility) korumak, ABI'yi bozan değişikliklerde ana sürüm numarasını artırmak, bağımlılık cehennemini önlemenin temelidir. ABI'yi bozmak (bir struct'ın alanını değiştirmek gibi) API'yi bozmaktan farklıdır ve çok daha sinsidir.

**Güvenlik korumalarını açık bırakın.** Modern derleyici ve linker'lar ASLR/PIE, NX ve stack koruma gibi savunmaları varsayılan olarak sunar. Performans için bunları kapatmak, ölçülebilir bir kazanç yoksa yapılmamalıdır; bu korumalar gerçek dünyada sömürülen açık sınıflarını önemli ölçüde zorlaştırır.

**Bağımlılıkları görünür kılın.** Bir çıktının hangi kütüphanelere bağlı olduğunu, hangi sembolleri dışa açtığını `ldd`, `nm`, `readelf`/`objdump` (Windows'ta `dumpbin`) ile düzenli olarak denetleyin. Beklenmedik bir bağımlılık, hem güvenlik hem de dağıtım açısından erken yakalanması gereken bir sinyaldir.

## Kapanış

Linker ve loader, "derleme başarılı" ile "program çalışıyor" arasındaki görünmez köprüdür. Linker derleme zamanında parçaları birleştirip sembolleri çözer ve adresleri yerleştirir; loader çalışma zamanında bu ürünü belleğe taşır, dinamik bağımlılıkları çözer ve programı hayata geçirir. Statik ile dinamik bağlama arasındaki seçim, semboller ile relocation'ın nasıl çalıştığı, ELF/PE formatlarının linker'a ve loader'a nasıl ayrı ayrı hitap ettiği, ve ASLR gibi loader düzeyi güvenlik mekanizmaları — bunların tümü, aslında tek bir temel sorunun farklı yüzleridir: bağımsız üretilmiş kod parçalarını, bellekte tutarlı ve güvenli bir bütün haline nasıl getiririz? Bu soruyu anlamak, çözemediğiniz bir bağlama hatasıyla karşılaştığınızda ya da bir programın neden başlamadığını çözmeye çalışırken elinizdeki en güçlü araçtır.
