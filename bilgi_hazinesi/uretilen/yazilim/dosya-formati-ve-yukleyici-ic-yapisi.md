# Dosya Formatı ve Yükleyici İç Yapısı (ELF/PE/Mach-O Derinlemesine)

## Giriş: Neden İkili Format İç Yapısını Bilmek Gerekir?

Bir derleyici kaynak koddan makine kodu ürettiğinde, ortaya çıkan çıktı ham talimat baytlarından ibaret değildir. İşletim sistemine "bu programı belleğe nasıl yerleştireceğini, hangi kütüphanelere bağlanacağını, hangi bölgeyi çalıştırılabilir hangi bölgeyi salt-okunur yapacağını" anlatan yapısal bir **konteyner** (container) üretilir. Bu konteynerin Linux ve çoğu Unix türevinde adı **ELF** (Executable and Linkable Format), Windows'ta **PE** (Portable Executable), macOS/iOS'ta **Mach-O** (Mach Object) biçimidir.

Bu formatları anlamak yalnızca akademik bir merak değildir. Malware analizi, tersine mühendislik (reverse engineering), zafiyet araştırması ve en önemlisi **tespit/savunma** kurmak için zorunlu bir temeldir. Bir antivirüs motorunun neden belirli imzaları aradığını, bir EDR'ın (Endpoint Detection and Response) neden `.text` bölümüne yazma iznini şüpheli saydığını, bir paketleyicinin (packer) formatı nasıl bozduğunu ancak bu iç yapıyı bilerek anlarsınız. Bu makale mekanizmayı öğretmeyi ve buradan tespit/savunma sezgisi kurmayı amaçlar; canlı saldırı talimatı değil, çalışma mantığı sunar.

## Ortak Zihinsel Model: Linking-Time ve Loading-Time İkiliği

Üç format da aynı temel gerilimi çözer: aynı dosya iki farklı bakış açısıyla okunur.

- **Section (bölüm) görünümü** — Linker ve derleme araçlarının bakışıdır. Kodu ve veriyi mantıksal parçalara böler: `.text` (kod), `.data` (başlatılmış veri), `.bss` (sıfırlanmış veri), `.rodata` (salt-okunur sabitler), `.symtab` (semboller). Bu görünüm **derleme/bağlama zamanında** anlamlıdır.
- **Segment (bölüt) görünümü** — Loader'ın (yükleyici) bakışıdır. Birden fazla section'ı, aynı bellek izinlerine sahip oldukları için tek bir bellek eşlemesinde (memory mapping) gruplar. Loader section adlarını umursamaz; yalnızca "şu dosya aralığını şu sanal adrese, şu izinlerle (RWX) eşle" komutlarına bakar.

Bu ikilik en açık ELF'te görülür: ELF'te **Section Header Table** linking görünümünü, **Program Header Table** loading görünümünü tanımlar. Kritik bir güvenlik sonucu şudur: **section header table çalışma zamanı için gerekli değildir.** Bir ELF dosyasının section header'larını tamamen silebilirsiniz; program yine çalışır çünkü loader yalnızca program header'lara bakar. Bu, birçok tersine mühendislik aracını kör eden yaygın bir gizleme (obfuscation) tekniğinin temelidir ve bir analistin neden `readelf -l` (program headers) ile `readelf -S` (section headers) çıktısını çapraz kontrol etmesi gerektiğini açıklar.

## ELF Derinlemesine

### Yapı Hiyerarşisi

Bir ELF dosyası şu bileşenlerden oluşur:

1. **ELF Header** — Dosyanın başındaki sabit boyutlu yapı. `e_ident` sihirli baytlarla (`0x7F 'E' 'L' 'F'`) başlar. Devamında 32/64-bit sınıfı (`EI_CLASS`), endianness, dosya tipi (`ET_EXEC` sabit yürütülebilir, `ET_DYN` konumdan bağımsız yürütülebilir/paylaşımlı kütüphane, `ET_REL` yer değiştirilebilir nesne), giriş noktası adresi (`e_entry`), ve program/section header table'ların dosya içi konumları (`e_phoff`, `e_shoff`) bulunur.
2. **Program Header Table** — Her girdi bir `PT_LOAD` (belleğe eşlenecek segment), `PT_DYNAMIC` (dinamik bağlama bilgisi), `PT_INTERP` (yorumlayıcı/dinamik linker yolu), `PT_TLS` (Thread Local Storage şablonu), `PT_GNU_STACK` (yığın izinleri) gibi bir tip taşır.
3. **Section'lar** — Asıl içerik.
4. **Section Header Table** — Her section'ın adı, tipi, adresi, dosya ofseti, izinleri.

### Dinamik Bağlama Mekanizması: PLT/GOT

Modern bir ELF çalıştırılabilirinin en kritik ve en çok istismar edilen parçası dinamik bağlama altyapısıdır. Bir program `printf` çağırdığında, `printf`'in adresi derleme anında bilinmez çünkü `libc` çalışma anında rastgele bir adrese yüklenebilir (ASLR). Çözüm iki tablodur:

- **GOT (Global Offset Table)** — `.got` / `.got.plt` section'ında yer alan, çözümlenmiş fonksiyon adreslerini tutan bir işaretçi (pointer) dizisi.
- **PLT (Procedure Linkage Table)** — `.plt` section'ındaki küçük "trampolin" kod parçacıkları.

**Çalışma mantığı (lazy binding):** İlk `printf` çağrısında kod aslında `printf@plt`'ye atlar. Bu trampolin, GOT girdisine bakar; girdi henüz çözülmemiştir ve dinamik linker'ın (`ld.so`) çözümleyici rutinine yönlendirir. Linker gerçek `printf` adresini bulur, GOT girdisine yazar ve fonksiyona atlar. İkinci çağrıda GOT zaten doğru adresi içerdiğinden çözümleme atlanır. Bu tembel (lazy) bağlama başlatma maliyetini dağıtır.

**Güvenlik sonucu:** GOT yazılabilir bir bellek bölgesindeyse (klasik durumda `.got.plt`), bir bellek yazma zafiyetini ele geçiren saldırgan bir GOT girdisini kendi kodunun adresiyle değiştirerek kontrol akışını ele geçirebilir — buna **GOT overwrite** denir. Savunma olarak **RELRO** (Relocation Read-Only) geliştirilmiştir: `partial RELRO` GOT'un bir kısmını, `full RELRO` ise tüm GOT'u (lazy binding'i devre dışı bırakıp her şeyi başlangıçta çözerek) salt-okunur yapar. Bir analist, `checksec` benzeri bir araçla RELRO durumunu görerek binary'nin bu sınıf saldırıya ne kadar açık olduğunu değerlendirebilir.

### Relocation (Yer Değiştirme)

Relocation'lar, "şu adres henüz belli değil, yükleme sırasında düzelt" talimatlarıdır. `.rela.dyn` ve `.rela.plt` section'ları bu girdileri taşır. Her girdi bir ofset (nerede düzeltilecek), bir tip (nasıl hesaplanacak) ve bazen bir sembol referansı içerir. Konumdan bağımsız kod (PIC/PIE) yaygınlaştıkça relocation'lar merkezi hale geldi; loader binary'yi rastgele bir taban adrese yerleştirdikten sonra tüm mutlak referansları bu relocation tablolarına göre düzeltir.

### Parazit Enfeksiyon Kavramı ve Tespiti

"ELF parasite infection" (parazit enfeksiyon), kötü amaçlı kodun mevcut bir yürütülebilir dosyaya, dosyanın normal işlevini bozmadan eklenmesini tanımlayan bir kavramdır. Klasik yaklaşımların **çalışma mantığı** şöyledir: yeni kod için bir `PT_LOAD` segmentinde boşluk (genellikle segmentler arası hizalama boşluğu, "code cave") bulunur veya dosya sonuna yeni bir segment eklenir; ardından ELF header'ın giriş noktası (`e_entry`) enjekte edilen koda yönlendirilir; bu kod işini bittikten sonra orijinal giriş noktasına atlayarak normal akışı sürdürür.

**Tespit sezgisi (savunma odağı):** Bu tür manipülasyonlar karakteristik anomaliler bırakır — giriş noktasının `.text` dışında bir segmente işaret etmesi, çalıştırılabilir ve yazılabilir (WX) bir segmentin varlığı, program header'ların dosya sonuna eklenmiş görünmesi, section header table ile program header table arasındaki tutarsızlık, `PT_GNU_STACK` benzeri girdilerin beklenmedik durumu. Bir savunma analisti bu göstergeleri tarayarak enfeksiyonu meşru derleyici çıktısından ayırt eder.

## PE (Portable Executable) Derinlemesine

Windows'un PE formatı, tarihsel olarak COFF'tan (Common Object File Format) türemiştir ve DOS uyumluluğu için ilginç bir başlangıç taşır.

### Yapı Hiyerarşisi

1. **DOS Header** — `MZ` sihirli baytlarıyla başlar (Mark Zbikowski'nin baş harfleri). Amacı geriye dönük uyumluluktur: DOS'ta çalıştırılırsa "bu program DOS modunda çalıştırılamaz" mesajını basan küçük bir stub içerir. Kritik alan `e_lfanew`'dur — gerçek PE header'ın dosya ofsetini gösterir.
2. **PE Signature + COFF File Header** — `PE\0\0` imzası, ardından makine tipi, section sayısı, ve karakteristik bayraklar.
3. **Optional Header** — Adına rağmen yürütülebilirler için zorunludur. Giriş noktası (`AddressOfEntryPoint`), tercih edilen yükleme adresi (`ImageBase`), section hizalaması, subsystem (GUI/konsol), ve en önemlisi **Data Directory** dizisini içerir. Data Directory, import table, export table, resource, relocation, TLS gibi özel yapıların yerlerine işaret eder.
4. **Section Table** — `.text`, `.data`, `.rdata`, `.rsrc` (kaynaklar), `.reloc` gibi section'ların RVA (Relative Virtual Address), sanal boyut, ham dosya ofseti ve boyutu, ve izin karakteristiklerini tanımlar.

### RVA Kavramı

PE'yi anlamanın anahtarı **RVA**'dır: neredeyse tüm adresler, `ImageBase`'e göreli ofset olarak ifade edilir. Bir yapının dosya içindeki fiziksel konumunu bulmak için RVA'yı, içinde bulunduğu section'ın sanal-fiziksel eşlemesini kullanarak dosya ofsetine çevirmeniz gerekir. Bu "RVA-to-file-offset" dönüşümü, her PE ayrıştırıcısının (parser) kalbindeki işlemdir ve hatalı yapılırsa analiz araçları kolayca kandırılır.

### Import Adres Çözümleme: IAT

PE'de dinamik bağlamanın karşılığı **Import Directory** ve **IAT (Import Address Table)**'tir. Import Directory, hangi DLL'lerin ve o DLL'lerden hangi fonksiyonların gerektiğini listeler. Windows loader, her gerekli DLL'i belleğe eşler, istenen fonksiyonların adreslerini çözer ve **IAT**'yi bu adreslerle doldurur. Program `CreateFileW` çağırdığında aslında IAT'deki ilgili girdi üzerinden dolaylı çağrı yapar.

**Güvenlik sonucu:** IAT, bir binary'nin niyeti hakkında zengin bilgi taşır. `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread` üçlüsünün import edilmesi klasik bir kod enjeksiyonu (code injection) parmak izidir. Bu yüzden malware yazarları import'ları gizlemek için **dynamic import resolution** kullanır: import table'ı boş bırakıp çalışma anında `LoadLibrary` + `GetProcAddress` ile fonksiyon adreslerini elle çözerler. Bir analist için import table'ın anormal derecede küçük olması veya yalnızca bu iki fonksiyonu içermesi başlı başına bir kırmızı bayraktır. IAT hooking ise EDR'ların ve rootkit'lerin IAT girdilerini kendi kancalarıyla değiştirerek API çağrılarını izlemesi/yönlendirmesidir.

### PE Enjeksiyon Ailesi Kavramı

"PE injection" terimi bir yürütülebilirin başka bir sürecin adres alanına yerleştirilmesini tanımlar. Kavramsal aile şunları içerir (savunma anlayışı için):

- **DLL injection** — Hedef sürece bir DLL yükleten en klasik yöntem; genellikle `LoadLibrary` çağrısını uzak süreçte tetiklemekle olur.
- **Reflective loading** — DLL'in diskteki bir dosya olmadan, doğrudan bellekten kendi loader mantığıyla eşlenmesi. Windows loader devreye girmediği için diskte iz bırakmaz; tespit bellek taramasına kaymak zorunda kalır.
- **Process hollowing** — Meşru bir süreç askıya alınmış (suspended) başlatılır, bellek içeriği boşaltılıp kötü amaçlı image ile değiştirilir, sonra devam ettirilir. Süreç adı meşru görünür ama içerik değişmiştir.

Bu tekniklerin ortak **tespit izi**, süreç belleğinde diskteki bir modüle karşılık gelmeyen çalıştırılabilir (executable) bölgelerdir. Bu yüzden modern EDR'lar "unbacked executable memory" (bir dosyayla desteklenmeyen çalıştırılabilir bellek) ararlar — kavramı bilmek, tespitin neden bu şekilde tasarlandığını açıklar.

## Mach-O Derinlemesine

Apple'ın Mach-O formatı, ELF ve PE'den bazı önemli mimari farklarla ayrılır.

### Yapı Hiyerarşisi

1. **Mach Header** — Sihirli bayt (`0xFEEDFACE` 32-bit, `0xFEEDFACF` 64-bit), CPU tipi/alt tipi, dosya tipi, ve **load command** sayısı ile toplam boyutu.
2. **Load Commands** — Mach-O'nun ayırt edici parçası. Section header ve program header'ı ayrı tutan ELF'in aksine, Mach-O tüm yapısal talimatları tek bir load command dizisinde toplar. `LC_SEGMENT_64` bir segment (ve içindeki section'ları) tanımlar; `LC_LOAD_DYLIB` bir paylaşımlı kütüphane bağımlılığı; `LC_MAIN` giriş noktası; `LC_DYLD_INFO` dinamik bağlama meta verisi; `LC_CODE_SIGNATURE` kod imzalama verisi.
3. **Segment ve Section'lar** — Segment adları geleneksel olarak büyük harflidir: `__TEXT` (kod ve salt-okunur veri), `__DATA` (yazılabilir veri), `__LINKEDIT` (semboller, relocation, imza). İçlerindeki section'lar `__text`, `__cstring` gibi adlanır.

### Fat/Universal Binary

Mach-O'nun kendine özgü bir kavramı **fat binary** (universal binary)'dir: tek bir dosya birden fazla mimari (örneğin x86_64 ve arm64) için ayrı Mach-O image'lar içerebilir. Dosyanın başındaki `fat_header` her mimarinin dosya içindeki ofsetini listeler; loader çalışan donanıma uygun olanı seçer. Bu, Intel'den Apple Silicon'a geçişte kritik olmuştur ama analiz araçlarının her dilimi (slice) ayrı incelemesi gerektiği için bir karmaşıklık kaynağıdır.

### Dinamik Bağlama ve Kod İmzalama

Mach-O'da dinamik bağlama `dyld` (dynamic linker) tarafından yürütülür ve modern sürümlerde bağlama bilgisi `LC_DYLD_INFO` / `LC_DYLD_EXPORTS_TRIE` içinde sıkıştırılmış opcode akışları olarak kodlanır. Fonksiyon çözümlemesinin ELF PLT/GOT'una benzeyen karşılığı **stub** ve **lazy/non-lazy pointer** section'larıdır (`__stubs`, `__la_symbol_ptr`, `__got`).

Mach-O'nun güvenlik açısından en belirgin özelliği **code signing**'in derinlemesine entegrasyonudur. `LC_CODE_SIGNATURE`, `__LINKEDIT` içindeki bir imza bloğuna (Code Signing Blob) işaret eder; bu blok sayfa sayfa (page hash) bütünlük özetleri içerir. macOS/iOS çekirdeği, sayfa belleğe alınırken bu özetleri doğrular. Sonuç: bir Mach-O'yu yamalayan (patch) herhangi bir manipülasyon imzayı geçersiz kılar. Bu, ELF/PE'de olmayan güçlü bir savunmadır ve saldırganları imzayı bozmayan (bellekte, imza doğrulaması sonrası) veya imza zorlamasının zayıf olduğu yollara iter. Bu mekanizmayı bilmek, macOS malware'inin neden farklı davranmak zorunda kaldığını açıklar.

## Kesişen Kavram: TLS (Thread Local Storage) İmplementasyonu

TLS, her thread'in aynı global değişkenin kendi özel kopyasına sahip olmasını sağlar. Formatlardaki implementasyonu incedir ve güvenlik açısından ilginçtir.

- **ELF'te**, `PT_TLS` program header'ı ve `.tdata`/`.tbss` section'ları thread'e özel verinin **şablonunu** tanımlar. Her yeni thread oluşturulduğunda bu şablon kopyalanarak thread'in TLS bloğu üretilir. Erişim, mimariye göre bir segment register (x86-64'te `fs`) üzerinden yapılır.
- **PE'de**, `.tls` section'ı ve Data Directory'deki TLS girdisi benzer bir şablon tanımlar. PE'nin dikkat çekici özelliği **TLS callback**'leridir: TLS Directory, thread her oluşturulduğunda/yok edildiğinde çağrılacak fonksiyon işaretçileri listesi taşır. **Kritik nokta:** TLS callback'leri programın `AddressOfEntryPoint`'inden **önce** çalışır. Bu yüzden malware, asıl mantığını bir TLS callback'e koyarak giriş noktasına breakpoint koyan basit debugger'ları atlatabilir (anti-debugging). Bir analist bunu bilerek TLS Directory'yi giriş noktasından önce incelemelidir — yaygın bir yeni başlayan hatası burayı atlamaktır.
- **Mach-O'da** thread-local değişkenler `__DATA` içindeki `__thread_vars` / `__thread_data` section'larıyla ve `dyld`'in çözdüğü thread-local variable descriptor'larıyla ele alınır.

## Yaygın Hatalar ve Doğru Yaklaşımlar

- **Section adlarına güvenmek.** Section adları (`.text`, `.data`) sadece bir gelenektir; hiçbir güvenlik garantisi vermez. Kod `.data` adlı bir section'da, veri `.text`'te olabilir. Loader adları değil izin bitlerini ve segment/program header'ları dikkate alır. Doğru yaklaşım her zaman izinlere ve loading görünümüne bakmaktır.
- **Section ve segment görünümünü karıştırmak.** ELF'te bir dosyanın "gerçekte ne yükleneceğini" section header'lardan çıkarmak hatalıdır; program header'lar otoritedir. İkisi çeliştiğinde bu başlı başına bir anomali sinyalidir.
- **RVA/ofset dönüşümünü ihmal etmek.** PE'de dosya ofseti ile RVA farklıdır; ham dosyada bir yapı ararken RVA'yı doğrudan dosya ofseti sanmak yanlış konuma götürür.
- **Fat binary'nin tek dilimini incelemek.** Mach-O evrensel binary'de yalnızca bir mimariyi analiz edip diğerini atlamak, kötü amaçlı yükü kaçırmaya yol açabilir; her slice ayrı incelenmelidir.
- **WX segmentini normal saymak.** Hem yazılabilir hem çalıştırılabilir (Write+Execute) bir bellek bölgesi meşru derleyici çıktısında neredeyse hiç görülmez. W^X (Write XOR Execute) ilkesi modern sistemlerin temelidir; bir formatta WX izni görmek güçlü bir şüphe göstergesidir.
- **İmza doğrulamasını atlamak (Mach-O).** Bir Mach-O'yu incelerken kod imzasının geçerliliğini kontrol etmemek, yamalanmış bir binary'yi meşru sanmaya yol açar.

## Sonuç

ELF, PE ve Mach-O aynı problemi — "kod ve veriyi belleğe doğru izinlerle yerleştirip dış bağımlılıkları çözmek" — farklı tasarım kararlarıyla çözer. Üçünde de tekrarlanan tema, **linking görünümü ile loading görünümünün ayrılması**, **dinamik bağlamanın bir dolaylılık tablosu (GOT/IAT/stubs) üzerinden yürümesi**, ve **relocation ile başlatma sırasında adreslerin düzeltilmesidir**. Bu mekanizmaları anlamak, saldırı tekniklerini ezberlemekten çok daha değerlidir: GOT overwrite'ın neden RELRO ile engellendiğini, IAT'nin neden bir niyet imzası olduğunu, TLS callback'lerin neden bir anti-debug yüzeyi olduğunu, Mach-O imzasının neden savunmayı güçlendirdiğini bir kez kavradığınızda, tespit ve savunma kuralları kendi kendine anlam kazanır. Bir savunmacı için nihai hedef her zaman aynıdır: meşru derleyici çıktısının bıraktığı düzenli izler ile manipülasyonun bıraktığı anomalileri ayırt edebilmek.
