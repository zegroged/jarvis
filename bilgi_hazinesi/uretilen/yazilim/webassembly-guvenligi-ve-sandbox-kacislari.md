# WebAssembly (Wasm) Güvenliği ve Sandbox Kaçışları

## Giriş: Wasm neden bir güvenlik konusu?

WebAssembly (Wasm), tarayıcıda ve tarayıcı dışında (server-side, edge, plugin sistemleri) neredeyse native hıza yakın kod çalıştırmak için tasarlanmış, taşınabilir bir binary komut formatıdır. Rust, C, C++, Go, Zig, AssemblyScript ve benzeri dillerden derlenir. Amacı JavaScript'in yerini almak değil, JavaScript'in yetersiz kaldığı CPU-yoğun işleri (video kodlama, oyun motorları, kriptografi, veri sıkıştırma, emülatörler) güvenli ve hızlı şekilde çalıştırmaktır.

Güvenlik açısından Wasm çift yönlü bir konudur. Bir yandan tasarımı gereği **sandbox** içinde çalışır ve klasik bellek güvenliği açıklarının ana makineye (host) sızmasını zorlaştırır. Öte yandan, güçlü ve hızlı bir kod çalıştırma yüzeyi olması onu saldırganlar için cazip bir hedef ve araç yapar: kripto madenciliği (cryptojacking), obfuscation (karartma) katmanı, ve nadir de olsa sandbox kaçışı denemeleri. Bu makale mekanizmayı anlamayı ve savunma/tespit kurmayı amaçlar; canlı saldırı talimatı vermez.

## Wasm Sandbox Modelinin Temelleri

### İki katmanlı izolasyon

Wasm'ın güvenlik modelini anlamak için iki farklı izolasyon katmanını ayırmak gerekir:

1. **Host ile modül arasındaki izolasyon (dıştaki duvar):** Wasm modülü, host ortamına (tarayıcı, Node.js, Wasmtime gibi bir runtime) yalnızca açıkça verilen **import** fonksiyonları üzerinden erişebilir. Modülün doğrudan sistem çağrısı (syscall), dosya erişimi, ağ erişimi yoktur. Ne verirseniz onu yapar. Bu, **capability-based** (yetenek tabanlı) güvenlik modelinin özüdür.

2. **Modülün kendi içindeki bellek güvenliği (içteki durum):** Modülün belleği tek bir doğrusal (linear) bellek bloğudur ve bu blok host'un adres uzayından mantıksal olarak ayrılmıştır. Modül kendi belleğinin dışına yazamaz; okuma/yazma erişimleri sınır kontrolüne (bounds check) tabidir.

Kritik nokta şudur: Bu iki katman birbirinden bağımsızdır. **Wasm içindeki bir bellek bozulması (memory corruption), modülün kendi içinde felakete yol açsa bile, otomatik olarak host'u ele geçirmez.** Bu ayrım, Wasm güvenliğini anlamanın anahtarıdır.

### Doğrusal bellek (linear memory) modeli

Wasm modülünün belleği, `0`'dan başlayan, sayfa (page = 64 KiB) birimleriyle büyüyen tek bir byte dizisidir. Modül içindeki tüm pointer'lar aslında bu dizideki **offset** değerleridir; gerçek host adresleri değildir.

Bunun güvenlik açısından iki büyük sonucu vardır:

- **Sınır kontrolü ucuzdur ve garantidir.** Her bellek erişimi `offset < memory.size` koşuluna tabidir. Runtime bunu ya açık kontrolle ya da guard page'ler (koruma sayfaları) ve donanım MMU trap'leriyle uygular. 32-bit Wasm'da (memory32) runtime çoğu zaman belleğin üstünü ve altını erişilemez sayfalarla çevreleyerek out-of-bounds erişimi bir CPU fault'una çevirir; böylece her erişimde yazılım kontrolü yapmaya gerek kalmaz.
- **İşaretçi, host adresi değildir.** Modül içinde bir "pointer" bozulsa bile bu sadece linear memory içinde başka bir offset'e işaret eder. Modül, ASLR'yi bypass edip host'un yığınına (stack) veya kod segmentine ulaşamaz, çünkü o adres uzayına hiç erişimi yoktur.

### Kod ve veri ayrımı: W^X garantisi

Klasik native istismarların çoğu, veriyi koda dönüştürmeye dayanır (shellcode injection, ROP/JOP). Wasm bunu yapısal olarak engeller:

- **Kod, veriden ayrı ve değiştirilemezdir.** Fonksiyonlar linear memory'de değildir; ayrı bir kod alanındadır ve modül kendi kodunu okuyamaz veya yazamaz. Yani doğrusal bellekteki hiçbir byte "çalıştırılamaz". Bu, W^X (Write XOR eXecute) ilkesinin doğuştan uygulanmış halidir.
- **Kontrol akışı yapılandırılmıştır (structured control flow).** Wasm'da rastgele adrese atlama (arbitrary jump) yoktur. Dallanmalar yalnızca iyi tanımlı blok/loop yapıları içinde yapılır. Bu, geleneksel ROP zinciri kurmayı temelde imkânsızlaştırır.
- **Çağrılar tip-güvenlidir.** Dolaylı çağrılar (indirect call) bir **table** üzerinden ve **type signature** kontrolüyle yapılır. Bozuk bir fonksiyon indeksi rastgele koda değil, yalnızca aynı imzaya sahip tablo girdisine gidebilir; imza uyuşmazsa trap oluşur.

Bu üç garanti (izole kod, yapılandırılmış akış, tip kontrolü) bir arada, Wasm'ı native binary'lere kıyasla istismar edilmesi çok daha zor bir hedef yapar.

## Wasm İçi İstismar: Sınırlar Nereden Geçer?

Burada önemli ve sık yanlış anlaşılan bir gerçek var: **Wasm, modülün kendi içindeki bellek güvenliğini garanti etmez.** Wasm yalnızca bu güvensizliğin *sandbox dışına* taşmasını engeller.

### Linear memory içi corruption gerçektir

Rust'ın güvenli alt kümesi dışında, C/C++'tan derlenen Wasm modülleri klasik hataların hepsini içerebilir: buffer overflow, use-after-free, double-free, integer overflow. Bunlar linear memory *içinde* gerçekleşir ve şu sonuçları doğurabilir:

- Aynı modül içindeki başka bir veri yapısının bozulması (örn. bir uygulama seviyesi yetki bayrağının ezilmesi).
- Modül içinde saklanan hassas verinin (parola, token) sızması.
- Indirect call table üzerinden, aynı tip imzasına sahip **başka bir fonksiyona** yönlendirme yaparak beklenmedik davranış üretme.

Bu, "in-sandbox exploitation" olarak adlandırılır. Saldırgan sandbox'tan çıkamasa bile, modülün *kendi işine* zarar verebilir. Örneğin bir Wasm ile yazılmış PDF görüntüleyici, kötü niyetli bir PDF ile kendi içinde bozulup yanlış içerik gösterebilir; ama tarayıcının geri kalanını ele geçiremez.

### Neden ROP/shellcode çalışmaz, ama mantık istismarı çalışır

Yukarıda anlattığımız W^X ve structured control flow yüzünden saldırgan linear memory'ye shellcode koyup atlayamaz. Bunun yerine gerçekçi in-sandbox saldırılar **veri odaklıdır** (data-only attacks): var olan meşru kod yollarını, bozulmuş verilerle beklenmedik biçimde tetiklemek. Savunma perspektifinden çıkarım şudur: Wasm'a derlediğiniz kod hâlâ bellek-güvenli yazılmalıdır; Wasm sizi sandbox içinde korumaz.

## Sandbox Kaçışı: Nerede ve Nasıl Gerçekleşir?

Gerçek "sandbox escape" (kaçış), Wasm modülünün host'un adres uzayına, ayrıcalıklarına veya sistem kaynaklarına yetkisiz erişim kazanmasıdır. Bu, Wasm'ın kendi bytecode semantiğinde tasarım gereği yoktur; kaçış neredeyse her zaman **runtime'ın (motorun) implementasyon hatasından** kaynaklanır. Ana kategoriler:

### 1. JIT derleyicisi hataları

Wasm'ı hızlı çalıştırmak için runtime, bytecode'u native makine koduna derler (JIT/AOT). Bu derleyici, Wasm'ın soyut güvenlik garantilerini native koda "çevirmekle" yükümlüdür. Eğer derleyici bir optimizasyon sırasında hata yaparsa (örneğin gereksiz olduğunu "sandığı" bir bounds check'i kaldırırsa, ya da bir tip kontrolünü atlarsa) o zaman üretilen native kod, Wasm'ın vaat ettiği izolasyonu artık uygulamaz. Bu, gerçek bir out-of-bounds erişimin *host* belleğine dokunmasına yol açabilir.

Tarayıcı motorlarının Wasm JIT'leri (V8/TurboFan, SpiderMonkey, JavaScriptCore) bu tür hataların en yoğun avlandığı yerlerdir. Buradaki kök neden Wasm değil, **derleyicinin doğruluğudur** (compiler correctness). Bir bounds check elimination hatası, milyonlarca satırlık optimize edici içinde tek bir yanlış varsayımdan doğabilir.

### 2. Host binding / import katmanı hataları

Modül host'a import fonksiyonları üzerinden konuşur. Eğer host, kendisine gelen argümanları (özellikle linear memory'ye işaret eden pointer + length çiftlerini) yeterince doğrulamazsa, modül host'u kendi belleğinin dışını okumaya/yazmaya kandırabilir. Örneğin bir host fonksiyonu "linear memory'nin şu offset'inden şu kadar byte oku" derken offset+length taşmasını kontrol etmezse, host modül belleğinin ötesine erişebilir. Bu, WASI ve JS glue kodu implementasyonlarında en sık görülen sınıflardandır.

### 3. WASI ve capability sınırlarının yanlış yapılandırılması

Tarayıcı dışı Wasm (server, edge, plugin) WASI (WebAssembly System Interface) üzerinden dosya, saat, rastgelelik, ağ gibi kaynaklara erişir. WASI'nin güvenlik modeli **capability-based**'tir: modül yalnızca kendisine önceden açılıp verilen (preopened) dizin ve kaynaklara erişebilir. Buradaki tehlike bir "Wasm açığı" değil, **yanlış konfigürasyondur**: host, modüle kök dizini (`/`) preopen olarak verirse ya da fazla geniş yetki tanırsa, modül tasarım gereği o yetkiyi kullanır. Bu bir kaçış değil, aşırı yetkilendirmedir; ama sonuç kaçışa benzer.

### 4. Spectre / mikroişlemci yan kanalları

Wasm'ın sağladığı mantıksal izolasyon, spekülatif yürütme (Spectre türü) yan kanallarına karşı doğrudan koruma sağlamaz. Yeterince kontrollü bir Wasm modülü, spekülatif okumalarla kendi sandbox'ının mantıksal sınırlarının ötesindeki host belleğini *dolaylı olarak* (timing üzerinden) çıkarsayabilir. Tarayıcılar buna karşı çok katmanlı önlemler alır (site isolation, saat hassasiyetinin düşürülmesi, `SharedArrayBuffer` için COOP/COEP zorunlulukları). Bu, mimari değil mikromimari bir sorundur ve Wasm'a özgü değildir, ama Wasm ölçülebilir zamanlama ve tam kontrol sunduğu için ilgili bir yüzeydir.

## Wasm'ın Saldırı Aracı Olarak Kullanımı

Kaçıştan ayrı bir başlık: Wasm bazen *hedef* değil, saldırganın *aracıdır*.

- **Cryptojacking:** Wasm'ın native'e yakın hızı, ziyaretçinin CPU'sunda izinsiz kripto madenciliği için idealdir. Sayfa açıkken CPU'yu doyurur, sekme kapanınca durur.
- **Obfuscation / evasion:** Kötü niyetli mantık (fingerprinting, skimmer, redirect zincirleri) JavaScript yerine Wasm binary'sine gömülerek imza tabanlı statik tespitten kaçmaya çalışılır. Wasm'ın binary ve derlenmiş yapısı, JS deobfuscation araçlarını atlatır.
- **Magecart tarzı skimmer'lar:** Ödeme formu verisini çalan mantığın Wasm'a taşınması, tespit ve analizi zorlaştırma amaçlıdır.

Bu kullanımlarda "sandbox" kırılmaz; saldırgan zaten sayfa içinde meşru şekilde çalışan Wasm'ı kötüye kullanır.

## Tespit ve Savunma

### Uygulama / site sahibi için

- **CSP ile Wasm'ı kısıtlayın.** İçerik Güvenliği Politikasında (Content Security Policy) script/Wasm derleme kaynaklarını daraltın. Modern tarayıcılarda `wasm-unsafe-eval` veya `unsafe-eval` gibi direktifler Wasm derlemesini etkiler; yalnızca gerçekten Wasm kullanan sayfalarda izin verin. Kural: Wasm'a ihtiyacı olmayan sayfada Wasm derlemesine izin vermeyin.
- **Kaynak bütünlüğü (SRI) ve tedarik zinciri kontrolü.** Üçüncü parti Wasm modüllerini pinleyin, hash doğrulayın, güncellemelerde diff'leyin. Birçok cryptojacking olayı, ele geçirilmiş bir üçüncü parti script/Wasm bağımlılığından gelir.
- **Runtime davranış izleme.** Beklenmedik ve sürekli yüksek CPU kullanımı, tab görünürlüğü değişince tetiklenen throttling paternleri, tanımadığınız origin'lerden `.wasm` yüklemeleri cryptojacking için güçlü sinyallerdir. `WebAssembly.instantiate`/`compile` çağrılarını ve indirilen `.wasm` MIME tiplerini (`application/wasm`) izleyin.

### Host / runtime işleten için (server-side, edge, plugin)

- **En az yetki (least privilege) ve capability minimizasyonu.** Modüle yalnızca ihtiyacı olan import'ları ve preopen dizinleri verin. Kök dizini preopen etmeyin. Ağ, saat, rastgelelik gibi yetkileri gerekmedikçe kapatın. WASI'nin gücü tam da bu ince taneli reddedilebilirliktir; kullanın.
- **Runtime'ı güncel tutun.** Sandbox kaçışlarının ezici çoğunluğu runtime (V8, Wasmtime, Wasmer vb.) hatasıdır. Yama gecikmesi doğrudan risk demektir. Güvenlik bültenlerini takip edin.
- **Kaynak limitleri koyun.** Bellek büyüme tavanı (max pages), yürütme süresi/yakıt (fuel/epoch) limitleri, stack derinliği sınırları koyun. Bu, in-sandbox bir DoS'un host'u yormasını engeller. Wasmtime gibi motorlar fuel ve epoch tabanlı kesme mekanizmaları sunar.
- **Process/OS düzeyinde ikinci bir sandbox katmanı.** Wasm izolasyonuna tek başına güvenmeyin. Runtime'ı ayrı bir işlemde, düşük yetkili kullanıcıyla, seccomp/AppArmor/container ile çevreleyin. Böylece bir runtime kaçışı bile OS sandbox'ına çarpar. "Defense in depth" burada kritiktir.
- **Modülleri güvenilmez varsayın.** Kullanıcı tarafından yüklenen Wasm'ı (plugin marketplace vb.) her zaman düşman girdisi olarak ele alın; import yüzeyinizi dar tutun ve host fonksiyonlarınızdaki her pointer+length çiftini titizlikle doğrulayın.

### Host binding kodu için altın kural

En sık gerçek dünya kaçış/sızıntısı, JIT hatasından değil, **kendi yazdığınız host fonksiyonlarınızdan** gelir. Linear memory'ye işaret eden her `(ptr, len)` için: `ptr`, `len` ve `ptr + len` değerlerinin taşmadığını ve modülün mevcut bellek boyutu içinde kaldığını erişimden *önce* doğrulayın. Integer overflow'a dikkat: `ptr + len` toplamı sarabilir. Bu tek disiplin, host tarafı Wasm açıklarının büyük kısmını kapatır.

## Yaygın Hatalar ve Yanlış İnançlar

- **"Wasm bellek-güvenlidir, o yüzden C kodum Wasm'da güvenli olur."** Yanlış. Wasm sandbox'ın *dışını* korur, modülün *içini* değil. C/C++ hataları linear memory içinde canlıdır. Bellek-güvenli sonuç istiyorsanız bunu kaynak dilde (örn. Rust'ın güvenli alt kümesi) sağlamalısınız.
- **"Wasm tarayıcıda çalıştığı için ekstra önlem gerekmez."** Yanlış. Cryptojacking, skimmer ve fingerprinting Wasm'ı meşru sandbox içinde kötüye kullanır; sandbox onları durdurmaz. CSP, SRI ve davranış izleme gerekir.
- **"Wasm modülü sisteme erişemez."** Kısmen. Tarayıcıda büyük ölçüde doğru; ama WASI ile host'ta, verdiğiniz *tüm* capability'lere erişir. Kök dizin preopen'i, geniş ağ izni tehlikelidir. Erişim sizin verdiğinizle sınırlıdır; az verin.
- **"Wasm binary'sini analiz edemem, o yüzden görmezden gelirim."** Yanlış. `wasm2wat` ile textual forma çevirebilir, import/export listesini, string tablolarını ve çağrı yapısını inceleyebilirsiniz. Import listesi tek başına modülün *ne yapmaya çalıştığını* (ağ mı, DOM mu, crypto mu) büyük ölçüde ele verir.
- **"Runtime izolasyonu yeterlidir, OS sandbox'ı fazlalık."** Riskli. Tek katmanlı savunma, tek bir JIT hatasında çöker. Katmanlayın.
- **"Structured control flow ROP'u önlediği için Wasm istismar edilemez."** Aşırı iyimser. ROP zorlaşır ama data-only saldırılar ve runtime JIT hataları gerçektir.

## Özet

WebAssembly'nin güvenlik gücü, sağlam tasarımlı bir sandbox'tan gelir: doğrusal bellek offset izolasyonu, veriden ayrı ve değiştirilemez kod (W^X), yapılandırılmış kontrol akışı ve tip-güvenli dolaylı çağrılar. Bu tasarım, klasik native istismar tekniklerini (shellcode, ROP) yapısal olarak zorlaştırır ve modül içindeki bir bozulmanın host'a taşmasını engeller.

Ancak bu koruma iki önemli sınıra sahiptir. Birincisi, sandbox modülün *kendi içindeki* bellek güvenliğini garanti etmez; C/C++ hataları linear memory içinde yaşamaya devam eder. İkincisi, gerçek sandbox kaçışları neredeyse her zaman Wasm'ın kendisinden değil, onu çalıştıran runtime'ın (özellikle JIT'in) veya host binding katmanının implementasyon hatalarından, ya da aşırı geniş WASI yetkilerinden doğar.

Bu yüzden pratik savunma üç ayak üzerinde durur: runtime'ı güncel tutmak, en az yetki ilkesiyle capability'leri daraltmak ve Wasm izolasyonunun üstüne OS düzeyinde ikinci bir sandbox katmanı koymak. Tarayıcı tarafında ise CSP, tedarik zinciri bütünlüğü ve davranış izleme, Wasm'ın bir saldırı aracı (cryptojacking, obfuscation) olarak kötüye kullanımını yakalamanın yoludur. Wasm'ı ne sihirli bir güvenlik kalkanı ne de kara kutu bir tehdit olarak görün; sınırlarını bilinen, izlenebilir ve katmanlı savunulabilir bir çalıştırma yüzeyi olarak ele alın.
