# Fuzzing Metodolojisi: Coverage-Guided Fuzzing, Sanitizer'lar ve Corpus Yönetimi

## Tanım

Fuzzing, bir programa çok sayıda beklenmedik, bozuk veya rastgele türetilmiş girdi (input) besleyerek yazılımdaki hataları, çökmeleri (crash) ve güvenlik açıklarını otomatik olarak bulmaya çalışan bir dinamik test yöntemidir. Temel fikir sade: bir insan test mühendisinin asla düşünemeyeceği kadar çok girdi varyasyonunu, saniyede binlerce hatta on binlerce kez çalıştırıp hedef programın "kırıldığı" anı yakalamak.

Ancak modern fuzzing artık "rastgele byte'lar besle ve bekle" değildir. Bugünkü etkili yaklaşım **coverage-guided fuzzing** (kapsama güdümlü fuzzing) olarak adlandırılır. Burada fuzzer, hedef programın hangi kod yollarını (code path) çalıştırdığını ölçer ve yeni kod bölgelerine ulaşan girdileri "değerli" kabul edip bunları saklayarak sonraki girdilerin temelini oluşturur. Bu makalede AFL++ ve libFuzzer gibi araçları, coverage geri besleme mantığını, sanitizer'ların rolünü ve corpus (girdi kümesi) yönetimini derinlemesine ele alacağız.

## Kök Neden: Neden Fuzzing Bu Kadar Etkili?

Fuzzing'in neden işe yaradığını anlamak için önce şunu kavramak gerekir: yazılım hatalarının büyük çoğunluğu **girdi işleme sınırlarında** ortaya çıkar. Bir parser, bir dosya format okuyucu, bir protokol çözümleyici (protocol decoder) veya bir deserialization rutini... Bunların hepsi dış dünyadan gelen ve programcının tam olarak öngöremediği veriyi işler. Programcı "iyi niyetli" girdiyi düşünür; kötü niyetli veya bozuk girdiyi ise genellikle eksik ele alır. İşte `buffer overflow`, `integer overflow`, `use-after-free`, `out-of-bounds read/write` gibi bellek güvenliği (memory safety) hataları tam bu noktalarda doğar.

Klasik "kör" (blind/dumb) fuzzing'in temel zaafı şudur: rastgele üretilen bir girdinin, programın derin bir kod yoluna ulaşma olasılığı astronomik derecede düşüktür. Örneğin bir dosya formatının önce 4 byte'lık sihirli imzasını (magic bytes) doğru geçmesi gerekiyorsa, tamamen rastgele byte'ların bu 4 byte'ı tutturma ihtimali 1/2^32'dir. Program daha ilk kontrolde girdiyi reddeder ve fuzzer hiçbir zaman asıl karmaşık ve hatalı kod bölgelerine ulaşamaz.

**Coverage-guided yaklaşımın dâhiyane çözümü** budur: fuzzer, her girdi çalıştırıldığında hangi kod bloklarının/kenarların (edge) çalıştığını bir bitmap'te izler. Eğer yeni bir girdi daha önce hiç görülmemiş bir kod kenarını tetiklerse, bu girdi "ilginç" sayılır ve corpus'a eklenir. Böylece fuzzer, tesadüfen magic bytes'ı yarım tutturan bir girdiyi ödüllendirir, onu mutasyona uğratarak (mutation) yavaş yavaş daha derin yollara "tırmanır". Bu, aslında bir tür yönlendirilmiş evrimsel arama algoritmasıdır: rastgele mutasyon + kapsama tabanlı doğal seçilim. İşte bu geri besleme döngüsü, fuzzing'i son on yılda güvenlik araştırmasının en verimli otomatik hata bulma tekniği hâline getiren şeydir.

### Coverage Nasıl Ölçülür? Instrumentation Mantığı

Coverage bilgisini elde etmenin yolu **instrumentation**'dır: derleme (compile) aşamasında hedef programın koduna, her temel blok (basic block) veya kenar geçişinde çalışan küçük sayaç kancaları (hooks) yerleştirilir. AFL++ ve libFuzzer genellikle bunu LLVM'nin `SanitizerCoverage` altyapısı üzerinden yapar; kaynak kod mevcutsa `clang` ile derleme sırasında `-fsanitize-coverage=trace-pc-guard` benzeri bir mekanizma devreye girer.

AFL'nin klasik yaklaşımında her kenar, kaynak blok ve hedef blok kimliklerinin bir fonksiyonu olarak (kabaca `hash(prev_block, cur_block)`) 64 KB'lık paylaşımlı bir bitmap'e (shared memory bitmap) yansıtılır. Çalışma sonunda fuzzer bu bitmap'e bakıp "yeni kenar gördüm mü?" sorusunu yanıtlar. Bu tasarımın zarafeti, kenar bazlı (edge coverage) ölçümün, sadece blok bazlı ölçüme göre çok daha zengin bilgi taşımasıdır: aynı blokları farklı sırayla çalıştıran iki yol birbirinden ayırt edilebilir. Not: bitmap sabit boyutlu olduğu için farklı kenarların aynı hücreye düşmesi (hash collision) mümkündür; bu, büyük programlarda kapsama çözünürlüğünü bir miktar bozan bilinen bir ödünleşimdir.

Kaynak kodun olmadığı durumlarda (binary-only hedefler) instrumentation, QEMU modu, dinamik ikili çevirme (dynamic binary translation) veya Intel PT (Processor Trace) gibi donanım destekli izleme yöntemleriyle çalışma zamanında yapılır. Bu yöntemler kaynak-kod derlemesine göre belirgin şekilde yavaştır, ama kapalı kaynak yazılımı fuzzlamanın tek yoludur.

## AFL++ ve libFuzzer: İki Farklı Felsefe

### libFuzzer: In-Process Fuzzing

libFuzzer, LLVM projesinin bir parçasıdır ve **in-process** (süreç-içi) çalışır. Yani ayrı bir hedef süreç başlatıp öldürmek yerine, tek bir süreç içinde fuzzing döngüsünü döndürür. Kullanıcı, `LLVMFuzzerTestOneInput` adlı bir fonksiyon yazar:

```c
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // Test edilecek fonksiyonu burada çağır
    parse_config(data, size);
    return 0;
}
```

Bu fonksiyona **fuzz target** (fuzz harness) denir. libFuzzer, sürekli olarak bu fonksiyonu farklı `data` girdileriyle çağırır. In-process olduğu için process fork/exec maliyeti yoktur; bu da onu son derece hızlı yapar (saniyede yüz binlerce çalıştırma mümkündür). Derleme genellikle `clang -fsanitize=fuzzer,address` gibi bir komutla yapılır.

Bunun ödünü şudur: hedef fonksiyon global durumu (global state) kirletiyor veya süreci çökertmeden bozuyorsa, in-process model sorun yaşayabilir. Bir çökme olduğunda tüm süreç ölür ve fuzzer'ın yeniden başlaması gerekir. Bu yüzden iyi bir fuzz target **durum bırakmayan (stateless)**, **deterministik** ve girdiden bağımsız yan etkileri (dosya yazma, ağ çağrısı) olmayan bir yapıda olmalıdır.

### AFL++: Out-of-Process ve Fork Server

AFL (American Fuzzy Lop) ve onun topluluk tarafından güçlendirilmiş sürümü AFL++, geleneksel olarak **out-of-process** çalışır: hedef programı ayrı bir süreç olarak çalıştırır. AFL'nin en önemli performans yeniliği **fork server**'dır. Program her seferinde baştan `execve` ile başlatılmak yerine, ağır başlatma işini (dynamic linker, kütüphane yükleme, `main`'e kadarki hazırlık) bir kez yapıp o noktada durur; sonra her yeni girdi için hızlıca `fork()` ile klonlanır. Bu, çalıştırma başına maliyeti dramatik ölçüde düşürür.

AFL++, orijinal AFL'nin üzerine birçok gelişmiş özellik ekler: farklı mutation stratejileri, CmpLog/RedQueen benzeri karşılaştırma bilgisini kullanan teknikler (girdi içindeki sabit değerleri "kopyalayıp" magic-byte kontrollerini otomatik geçme), farklı instrumentation backend'leri (LLVM, QEMU, Unicorn) ve persistent mode. **Persistent mode**, AFL++'ı libFuzzer'a benzetir: fork yerine bir döngü içinde aynı süreçte defalarca girdi işlenir, bu da hızı ciddi biçimde artırır. Aslında AFL++ ve libFuzzer arasındaki çizgiler bugün epeyce bulanıklaşmıştır; AFL++ libFuzzer-uyumlu harness'ları da çalıştırabilir.

**Hangisini seçmeli?** Kaba bir sezgi: kütüphane fonksiyonu düzeyinde, hızlı ve deterministik hedefler için libFuzzer çok pratiktir. Tüm bir programı, dosya girdisi alan bir komut satırı aracını veya karmaşık/kirli durumlu hedefleri fuzzlarken AFL++'ın out-of-process modeli ve zengin araç ekosistemi genellikle daha dayanıklıdır. Modern projelerde ikisini birden kullanmak ve corpus'u paylaştırmak yaygın bir pratiktir.

## Sanitizer'lar: Sessiz Hataları Görünür Kılmak

Fuzzing'in en kritik ama sıklıkla küçümsenen tarafı şudur: fuzzer bir hatayı ancak **gözlemleyebildiği** takdirde raporlar. Pek çok bellek güvenliği hatası aslında programı hemen çökertmez. Örneğin bir dizinin sınırının bir byte dışına yazma (`off-by-one` overflow) işlemi, çoğu zaman bitişikteki masum bir belleği bozar ama program çalışmaya devam eder; çökme çok sonra, alakasız bir yerde veya hiç olmaz. Bu tür "sessiz" bellek bozulmaları (silent memory corruption) klasik fuzzing için görünmezdir.

İşte **sanitizer'lar** bu boşluğu doldurur. Sanitizer, derleme zamanında eklenen ve çalışma zamanında bellek/davranış ihlallerini anında tespit edip programı hemen çökerten bir enstrümantasyon katmanıdır:

- **AddressSanitizer (ASan):** `heap-buffer-overflow`, `stack-buffer-overflow`, `use-after-free`, `use-after-return`, `double-free` gibi bellek erişim hatalarını yakalar. Bellek çevresine "redzone" (kırmızı bölge) adı verilen zehirlenmiş (poisoned) alanlar yerleştirir; bu bölgelere herhangi bir erişim anında hata olarak raporlanır. ASan, fuzzing'de neredeyse zorunlu bir eştir çünkü aksi hâlde bulunabilecek çökmelerin büyük kısmı sessizce kaçar.
- **UndefinedBehaviorSanitizer (UBSan):** `integer overflow`, hatalı hizalanmış (misaligned) pointer erişimi, geçersiz enum değerleri, sıfıra bölme gibi C/C++ standardına göre tanımsız davranışları yakalar.
- **MemorySanitizer (MSan):** İlklendirilmemiş (uninitialized) bellek okumalarını tespit eder. Bu hatalar bilgi sızıntısına (`information disclosure`) yol açabilir. MSan'ın doğru çalışması için tüm bağımlılıkların da MSan ile derlenmesi gerekir; bu yüzden kurulumu daha zahmetlidir.
- **ThreadSanitizer (TSan):** `data race` ve `race condition` türü eşzamanlılık hatalarını yakalar. Çok iş parçacıklı (multithreaded) kod için değerlidir ama tek başlığa yönelik klasik fuzzing ile birlikte kullanımı sınırlıdır.

Önemli bir uyarı: ASan ve MSan aynı derlemede birlikte kullanılamaz; TSan da diğerleriyle çakışır. Genel pratik ASan+UBSan'ı birlikte kullanıp, ayrı bir kampanyada MSan çalıştırmaktır. Ayrıca sanitizer'lar programı yavaşlatır (ASan tipik olarak 2x mertebesinde) ve bellek tüketimini artırır; bu, fuzzing hızıyla hata görünürlüğü arasında bilinçli bir ödünleşimdir. Yavaşlama olsa bile sanitizer'sız fuzzing çoğu zaman "kör" fuzzing demektir; bulunan çökme sayısı düşük görünür ama bu araç iyi çalıştığı için değil, hataları göremediği içindir.

## Corpus: Fuzzing'in Yakıtı

**Corpus**, fuzzer'ın mutasyon için kullandığı girdi örneklerinin (seed) kümesidir. Corpus yönetimi, bir fuzzing kampanyasının başarısını doğrudan belirleyen, çoğu zaman araç seçiminden bile önemli bir faktördür.

### Seed Corpus'un Önemi ve Kök Mantık

Coverage-guided fuzzer sıfırdan (boş girdiden) de başlayabilir, ama iyi bir **seed corpus** (başlangıç örnek kümesi) ile başlamak devasa fark yaratır. Neden? Çünkü fuzzer mutasyonla evrimleşir; ne kadar zengin ve geçerli örnekle başlarsa, o kadar derin kod yollarını daha baştan çalıştırır. Bir JPEG parser'ı fuzzlıyorsanız, elinizdeki birkaç geçerli JPEG dosyası, fuzzer'ın format yapısını "keşfetme" aşamasını atlamasını sağlar. Boş girdiden başlarsa fuzzer'ın önce geçerli bir JPEG başlığını tesadüfen türetmesi gerekir ki bu pratikte imkânsıza yakındır.

İyi seed'lerin nitelikleri: küçük olmalı (küçük girdiler daha hızlı çalışır ve mutasyonları daha odaklıdır), çeşitli olmalı (farklı format özelliklerini, farklı kod yollarını tetiklemeli) ve gerçekçi olmalıdır. Format spesifikasyonundaki her farklı özelliği (opsiyonel alanlar, farklı sıkıştırma modları, uç durumlar) örnekleyen bir seed seti idealdir.

### Corpus Minimization ve Distillation

Zamanla corpus şişer: fuzzer binlerce girdi biriktirir ama bunların çoğu aynı kod kapsamasını sağlar, yani gereksizdir. **Corpus minimization** (küçültme), aynı toplam kapsamayı sağlayan en küçük girdi alt kümesini bulma işlemidir. AFL++ ekosisteminde `afl-cmin` corpus'u kapsama açısından, `afl-tmin` ise tek tek girdileri byte düzeyinde küçültür (test case minimization). libFuzzer'da `-merge=1` bayrağı benzer bir birleştirme/damıtma işi yapar.

Bunun kök mantığı verimlilikle ilgilidir: fuzzer her mutasyon turunda corpus'tan bir girdi seçer. Corpus'ta 50.000 fazlalık girdi varsa, fuzzer zamanının çoğunu gereksiz kopyaları mutasyona uğratarak harcar. Damıtılmış küçük bir corpus, aynı kapsama çeşitliliğini koruyarak fuzzer'ın enerjisini daha verimli dağıtmasını sağlar. Uzun kampanyalarda periyodik minimization önemli bir bakım işidir.

### Structure-Aware Fuzzing ve Dictionary'ler

Çok yapılandırılmış girdiler (örneğin bir programlama dili, bir ağ protokolü, ASN.1 veya Protobuf mesajları) için ham byte mutasyonu yetersiz kalır; rastgele byte değişimleri girdiyi hemen sözdizimsel olarak geçersiz kılar ve program erken reddeder. İki çözüm vardır. Birincisi **dictionary** kullanımıdır: dile/formata özgü anahtar kelimeleri, magic value'ları ve token'ları (örneğin `<script>`, `SELECT`, format imzaları) fuzzer'a bir sözlük olarak vermek, mutasyonların anlamlı yapı taşları üretmesini sağlar. İkincisi **structure-aware / grammar-based fuzzing**'dir: girdinin gramerini tanımlayıp (ör. libFuzzer için `libprotobuf-mutator` ile Protobuf tabanlı mutasyon) yalnızca yapısal olarak geçerli ama semantik olarak sıra dışı girdiler üretmektir. Bu, derleyici, JSON/XML işleyici, SQL motoru gibi hedeflerde çok daha derine iner.

## Sömürü/İstismar Perspektifi: Fuzzing ile Bulunan Bir Açık Nasıl Silaha Dönüşür?

Saldırgan gözünden fuzzing bir keşif motorudur, ama bir çökme raporu tek başına bir exploit değildir. Süreç şöyle işler: önce fuzzer bir çökme (crash) üretir; bu çökme, ASan çıktısıyla birlikte "burada bir `heap-buffer-overflow` var" der. Saldırgan bundan sonra **triage** (ayıklama) yapar: aynı hataya yol açan farklı çökmeleri kök nedene göre gruplar (crash deduplication), test case'i minimuma indirir (`afl-tmin`) ve hatanın gerçekten sömürülebilir (exploitable) olup olmadığını değerlendirir.

Sömürülebilirlik değerlendirmesinin kalbindeki soru şudur: saldırgan bu hata üzerinden **kontrol** kazanabiliyor mu? Bir `out-of-bounds read` genellikle bilgi sızıntısına (bellek içeriğini okuma, ASLR'yi kırmak için pointer sızdırma) yarar. Bir `use-after-free` veya `heap overflow` ise, eğer saldırgan heap düzenini (heap grooming/feng shui) yönlendirebiliyorsa, serbest bırakılmış bir nesnenin yerine kendi kontrol ettiği veriyi yerleştirip bir fonksiyon pointer'ını veya vtable'ı ele geçirebilir; bu da nihayetinde kod çalıştırma (`code execution`) yolunu açar. Fuzzing burada "hangi girdi programı bozuyor" sorusunu yanıtlar; gerisi klasik exploit geliştirme (control-flow hijacking, modern korumaların (`ASLR`, `DEP/NX`, stack canary, CFI) atlatılması) alanına girer.

Kritik bir gerçek: fuzzing ile bulunan çökmelerin önemli bir kısmı doğrudan sömürülebilir değildir (örneğin sadece bir `assert` başarısızlığı veya null pointer dereference kaynaklı bir denial-of-service). Ancak bir DoS bile, ağa açık bir serviste ciddi bir güvenlik sorunudur. Dolayısıyla saldırgan için fuzzing çıktısı; sömürülebilir bellek bozulmalarından basit çökme tabanlı DoS'lara kadar uzanan bir hata yelpazesi sunar.

## Savunma Perspektifi: Fuzzing'i Kendi Lehinize Çevirmek

Aynı araç savunmanın da en güçlü silahıdır ve buradaki temel prensip şudur: **saldırgan sizin kodunuzu fuzzlamadan önce siz kendi kodunuzu fuzzlayın.** Savunma odaklı fuzzing'in pratiği:

- **Fuzzing'i CI/CD'ye entegre edin.** Her kod değişikliğinde kısa süreli fuzzing çalıştırmak (regression fuzzing) ve daha uzun sürekli kampanyaları arka planda döndürmek en iyi sonucu verir. OSS-Fuzz gibi sürekli fuzzing altyapıları tam da bu felsefeyle, açık kaynak projelerde on binlerce hatayı otomatik bulmuştur.
- **Sanitizer'larla derleyin.** Üretim (production) derlemesinde değil ama test/fuzzing derlemesinde ASan+UBSan (ve ayrıca MSan) çalıştırmak, hataların yakalanma oranını kat kat artırır.
- **Harness kalitesine yatırım yapın.** İyi bir fuzz target, saldırı yüzeyinin (attack surface) doğru noktasına yerleştirilmiş olmalıdır: gerçekte dış girdiyi işleyen fonksiyonu hedeflemeli, gerçekçi girdi biçimini yansıtmalı ve yapay engeller (checksum doğrulaması gibi) fuzzing modunda gevşetilmelidir; aksi hâlde fuzzer derin koda hiç ulaşamaz.
- **Bulunan her hatayı kök nedene inip düzeltin ve o girdiyi regresyon corpus'una ekleyin.** Böylece aynı hata bir daha sızarsa anında yakalanır.
- **Uzun vadeli çözüm bellek güvenli dillerdir.** Fuzzing bellek hatalarını bulmakta muazzam iyidir, ama bu hataların kaynağı çoğunlukla C/C++'ın manuel bellek yönetimidir. Kritik parser bileşenlerini `Rust` gibi bellek güvenli (memory-safe) dillere taşımak, bu hata sınıfını büyük ölçüde kökten ortadan kaldırır.

Savunmacı için fuzzing, tehdit modelini somutlaştırır: "parser'ımız kötü niyetli girdiye dayanıklı mı?" sorusunu spekülasyonla değil, on milyonlarca gerçek çalıştırmayla test eder.

## Yaygın Hatalar

**1. Sanitizer olmadan fuzzlamak.** En sık yapılan hata. Sanitizer'sız fuzzing, çökmelerin çoğunu sessizce kaçırır ve size yanlış bir güvenlik hissi verir. "Bir hafta fuzzladık, hiç çökme yok" demek, ASan olmadan neredeyse hiçbir şey ifade etmez.

**2. Zayıf veya boş seed corpus.** Karmaşık bir formatı boş girdiden başlatarak fuzzlamak, fuzzer'ı ilk yapısal engellerde tıkar. Kapsama grafiği (coverage plot) hızla düzleşir ve kampanya boşa döner. Her zaman gerçekçi, çeşitli, küçük seed'lerle başlayın.

**3. Kötü tasarlanmış harness.** Girdiyi yanlış katmandan besleyen, deterministik olmayan, global durum sızdıran veya her çağrıda dosya/ağ I/O yapan bir harness fuzzing'i hem yavaşlatır hem de sahte çökmeler (false positive) veya çoğaltılamayan (non-reproducible) hatalar üretir. Harness, saf ve tekrarlanabilir olmalıdır.

**4. Kapsamayı izlememek.** Fuzzer çalışıyor diye işin bittiğini sanmak. Eğer coverage saatlerdir artmıyorsa fuzzer bir engele takılmıştır (magic bytes, checksum, karmaşık bir koşul) ve müdahale gerekir: dictionary ekleme, CmpLog benzeri teknikleri açma veya harness'ı düzenleme. Kapsama, kampanyanın sağlık göstergesidir.

**5. Checksum/magic kontrollerini görmezden gelmek.** Girdinin başında bir CRC veya hash doğrulaması varsa, rastgele mutasyonlar bu kontrolü asla geçemez ve tüm kod kilitli kalır. Çözüm, fuzzing derlemesinde bu kontrolü atlamak (bypass) veya girdi üretiminde hesaplamaktır.

**6. Çökmeleri gruplamadan (deduplication) her birini ayrı sanmak.** Tek bir hata binlerce farklı çökme girdisi üretebilir. Kök nedene göre gruplamadan raporlara boğulursunuz.

**7. Kampanyayı çok erken sonlandırmak.** Coverage hâlâ artıyorsa fuzzer hâlâ yeni yollar buluyordur. Ciddi kampanyalar günler/haftalar sürer; bazı derin hatalar ancak uzun çalışmalarda ortaya çıkar.

## En İyi Pratikler

Etkili bir fuzzing metodolojisi şu ilkeler üzerine kurulur. Öncelikle **her zaman sanitizer ile derleyin** — ASan+UBSan varsayılan olmalı, mümkünse ayrı bir MSan kampanyası ekleyin. İkincisi, **corpus'a yatırım yapın**: zengin ve gerçekçi seed'lerle başlayın, periyodik olarak minimize edin (`afl-cmin`/`-merge`), ve regresyon corpus'unu sürüm kontrolünde (version control) tutun.

Üçüncüsü, **hedefe göre araç seçin ve gerekirse birden fazla kullanın**: kütüphane fonksiyonları için libFuzzer'ın in-process hızı, program/CLI hedefleri ve zengin mutasyon stratejileri için AFL++. İkisinin corpus'unu paylaştırarak sinerjiden yararlanın. Dördüncüsü, **yapılandırılmış hedeflerde structure-aware yaklaşımı benimseyin**: dictionary'ler ve grammar/protobuf tabanlı mutasyon, ham byte fuzzing'in ulaşamadığı derinliklere iner.

Beşincisi, **kapsamayı sürekli izleyin ve platoları teşhis edin**; fuzzer'ın takıldığı yeri bulup dictionary, CmpLog veya harness düzenlemesiyle açın. Altıncısı, **fuzzing'i sürekli hâle getirin**: CI'da regresyon fuzzing, arka planda uzun kampanyalar. Yedincisi, **triage sürecini disiplinli yürütün**: çökmeleri deduplike edin, `afl-tmin` ile küçültün, kök nedeni bulun, düzeltin ve testi corpus'a ekleyin.

Son olarak, **fuzzing'i tek başına bir gümüş kurşun sanmayın**. Fuzzing özellikle bellek güvenliği ve parser hatalarında olağanüstüdür, ama karmaşık iş mantığı (business logic) hataları, yetkilendirme (authorization) açıkları veya kriptografik zayıflıklar gibi "anlamsal" sorunları genellikle bulamaz. Fuzzing'i statik analiz (static analysis), manuel kod incelemesi (code review), tehdit modelleme ve bellek güvenli dillere geçiş ile birlikte, katmanlı bir güvenlik yaklaşımının bir parçası olarak kullanın. En güçlü sonucu, otomatik makine üretkenliğini insan uzmanlığıyla birleştirdiğinizde alırsınız.
