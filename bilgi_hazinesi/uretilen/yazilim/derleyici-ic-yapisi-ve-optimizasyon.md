# Derleyici İç Yapısı ve Optimizasyon (Lexer/Parser/AST/IR/Backend, LLVM)

## Giriş: Neden Bir Mühendis Derleyici İç Yapısını Bilmeli

Çoğu yazılımcı derleyiciyi bir "kara kutu" gibi görür: kaynak kod girer, çalışabilir program çıkar. Ama profesyonel seviyede performans mühendisliği, güvenlik analizi, debug edilebilirlik ve dahi "compiler neden bu kodu böyle optimize etti/etmedi" sorularına cevap vermek için derleyicinin iç katmanlarını anlamak şarttır. Bir derleyici, birbirine bağlı, her biri kendi hata sınıflarına ve optimizasyon fırsatlarına sahip bir boru hattı (pipeline) dizisidir: **Lexer -> Parser -> AST -> Semantik Analiz -> IR (Intermediate Representation) -> Optimizasyon Geçişleri -> Backend (Kod Üretimi) -> Register Allocation -> Assembly/Makine Kodu**. Bu makale, LLVM ve GCC gibi gerçek dünya sistemlerinin izlediği bu boru hattını, SSA formunu, kritik optimizasyon tekniklerini ve register allocation problemini derinlemesine ele alacak.

## 1. Lexer (Sözcüksel Analiz): Karakter Akışından Token'lara

### Tanım ve Kök Neden

Kaynak kod, derleyici için başlangıçta düz bir karakter dizisidir (`"int x = 5 + y;"`). Parser'ın bu diziyi doğrudan işlemesi hem yavaş hem de mantıksal olarak yanlış katmandadır; sözdizimi kuralları (grammar) karakterler üzerinde değil, anlamlı birimler (token) üzerinde tanımlanır. Lexer'in kök görevi budur: karakter akışını, her biri bir tür (`IDENTIFIER`, `INTEGER_LITERAL`, `PLUS`, `SEMICOLON` vb.) taşıyan token'lara dönüştürmek.

Bu işlem genellikle **sonlu durum otomatları (finite state automata, FSM)** ile modellenir. Her token türü için bir düzenli ifade (regular expression) tanımlanır, bunlar birleştirilip tek bir DFA'ya (deterministic finite automaton) derlenir. Lexer, bu DFA'yı karakter karakter yürürken "en uzun eşleşme" (maximal munch) kuralını uygular: örneğin `==` görünce bunu iki ayrı `=` token'ı değil, tek bir `EQ` token'ı olarak tanır, çünkü DFA daha uzun eşleşmeyi tercih eder.

### Doğru Kullanım ve Tuzaklar

- **Maximal munch tuzağı**: `a+++b` ifadesi `a++ + b` mi yoksa `a + ++b` mi? Lexer bunu saf aç gözlülükle `a++`, `+`, `b` olarak parçalar; bu C'de klasik bir belirsizlik kaynağıdır ve derleyiciler arasında bile tarihsel farklılıklar görmüştür.
- **Bağlam duyarlı lexing**: Bazı diller (C++'daki `>>` template kapanışı vs. bit kaydırma operatörü gibi) lexer'in tek başına karar veremeyeceği durumlar yaratır; bu yüzden modern derleyiciler lexer ile parser arasında geri besleme (lexer hack) veya "lexer state" paylaşımı kullanır.
- **Hata kurtarma (error recovery)**: Gerçek dünya lexer'ları ilk hatalı karakterde durmaz; senkronizasyon noktalarına (satır sonu, noktalı virgül) atlayarak devam eder ve tek geçiş içinde birden fazla hatayı raporlar. Bu, IDE entegrasyonu için kritik bir en iyi pratiktir.

## 2. Parser: Token'lardan AST'ye

### Tanım ve Çalışma Mantığı

Parser, token akışını dilin grameri (genellikle context-free grammar, CFG) ile eşleştirerek bir **Soyut Sözdizim Ağacı (Abstract Syntax Tree, AST)** üretir. İki temel yaklaşım vardır:

1. **Top-down (LL) parsing**: Kök düğümden yapraklara doğru, sol-en-önce türetim yapar. Elle yazılan "recursive descent" parser'lar bu kategoridedir ve okunabilirliği yüksek olduğu için GCC'nin C++ front-end'i ve Clang bu yaklaşımı kullanır.
2. **Bottom-up (LR) parsing**: Yapraklardan köke doğru, shift-reduce otomatı ile çalışır. Yacc/Bison gibi parser generator'lar LALR(1) varyantını kullanır.

Recursive descent'in tercih edilmesinin kök nedeni: hata mesajlarının kalitesi ve dilin karmaşık, bağlam duyarlı kurallarının (örneğin C++'daki "most vexing parse") elle kontrol edilebilir olmasıdır. LR parser'lar teorik olarak daha geniş bir gramer sınıfını kabul eder ama hata mesajları ve özel durum yönetimi daha zordur.

### AST vs Parse Tree Farkı

Parse tree (somut sözdizim ağacı), gramerin her kuralını bire bir yansıtır ve gereksiz ara düğümler içerir (`(`, `)`, noktalı virgül gibi). AST ise bunları atar, yalnızca **anlamsal olarak önemli yapıyı** tutar: `BinaryExpr(Add, Literal(5), Identifier(y))` gibi. Bu soyutlama, sonraki aşamaların (semantik analiz, IR üretimi) daha temiz çalışmasını sağlar.

### Yaygın Hatalar

- Operatör önceliği (precedence) ve ilişkilendirmeyi (associativity) recursive descent'te yanlış katmanlamak, `2 + 3 * 4` gibi ifadelerin yanlış ağaçlanmasına yol açar. Doğru pratik, her öncelik seviyesi için ayrı bir parse fonksiyonu yazmak (precedence climbing / Pratt parsing).
- Hata mesajlarında token konumunu (satır/sütun) kaybetmek; her AST düğümüne kaynak konum bilgisi (source location) eklemek, sonraki tüm diagnostic'lerin kalitesini belirler.

## 3. Semantik Analiz: AST'nin Anlam Kazanması

AST sözdizimsel olarak doğru olabilir ama anlamsal olarak geçersiz olabilir (`int x = "merhaba";`). Bu aşamada:

- **Sembol tablosu (symbol table)** oluşturulur: her değişken/fonksiyon adı, kapsam (scope), tür (type) ve bellek konumuyla eşleşir.
- **Tür kontrolü (type checking)** yapılır: ifade türleri çıkarılır (type inference) ve uyumsuzluklar raporlanır.
- **Kapsam çözümleme (scope resolution)**: lexical scoping kurallarına göre hangi `x`'in hangi tanıma atıfta bulunduğu belirlenir.

Bu katman, derleyicinin "doğruluk" garantilerinin büyük kısmını üstlenir; IR'a geçmeden önce yakalanmayan bir tür hatası, sonraki aşamalarda tanımsız davranışa (undefined behavior) dönüşebilir.

## 4. IR (Intermediate Representation): Neden Ara Katman Şart

### Kök Neden: N x M Problemi

Bir derleyici K farklı kaynak dili (C, C++, Rust, Swift...) M farklı hedef mimariye (x86-64, ARM, RISC-V...) derlemek isterse, doğrudan AST'den her mimariye kod üretmek K*M ayrı backend gerektirir. IR, bu problemi **K + M**'ye indirger: her front-end kaynak dilini ortak bir IR'a çevirir, her backend bu aynı IR'dan kod üretir. LLVM'in başarısının temel nedeni tam olarak budur: LLVM IR, Clang'den Rust'a, Swift'ten Julia'ya kadar onlarca front-end tarafından üretilir ve x86'dan RISC-V'e, GPU'lara kadar onlarca backend tarafından tüketilir.

IR ayrıca optimizasyonun doğal alanıdır: kaynak dile özgü detaylardan arınmış, hedef mimariden bağımsız, ama yine de yapısal analiz yapılabilecek kadar zengin bir temsildir.

### SSA Formu (Static Single Assignment)

Modern optimize edici derleyicilerin (LLVM, GCC'nin GIMPLE/RTL boru hattı, JVM'in bazı JIT'leri) kalbi **SSA formudur**. SSA'nın kuralı basittir: her değişken tam olarak bir kez atanır. Aynı "kaynak değişken" birden fazla kez atanacaksa, her atama yeni bir SSA ismi alır (`x1`, `x2`, `x3`...).

**Neden SSA?** Geleneksel IR'da bir değişkenin hangi atamadan geldiğini bulmak için geriye doğru veri akış analizi (reaching definitions) gerekir - bu pahalıdır ve her optimizasyon geçişi için tekrar tekrar hesaplanır. SSA'da ise her kullanım, tanım ile lexical olarak doğrudan ilişkilidir (use-def zinciri açıktır); bu da constant propagation, dead code elimination gibi analizleri O(n) yakınında, tek geçişli hale getirir.

**Phi (φ) düğümleri**: Kontrol akışının birleştiği noktalarda (örneğin bir if-else sonrası), hangi dalın hangi SSA değişkenini "kazandığını" temsil etmek için phi fonksiyonu kullanılır:

```
if (cond) { x1 = 5; } else { x2 = 10; }
x3 = phi(x1, x2)   // hangi dalden geldiyse o deger
```

Derleyici, phi düğümünü gerçek makine koduna çevirirken (SSA'dan çıkış / "out of SSA" aşaması) bunu genellikle move (kopyalama) talimatlarına dönüştürür; bu aşama register allocation ile yakından etkileşir ve yanlış yapılırsa gereksiz kopyalar ("copy bloat") üretebilir.

### Doğru Kullanım ve Tuzaklar

- SSA inşası için **dominance frontier** hesabı gerekir (Cytron ve diğerlerinin klasik algoritması); bu, phi düğümlerinin nereye yerleştirileceğini belirler. Yanlış/eksik dominance analizi, optimizasyonların yanlış kod üretmesine yol açabilir.
- SSA "tek atama" kuralını korumak için döngülerde (loop) değişkenler her iterasyonda kavramsal olarak yeni bir SSA ismi alır; bu, loop-carried dependency analizini kolaylaştırır ama saf halde bellek/karmaşıklık maliyeti getirir - pratikte derleyiciler bunu kompakt gösterimlerle yönetir.

## 5. IR Optimizasyon Geçişleri: Çalışma Mantığı ve Sırası

Optimize edici derleyiciler onlarca "pass" (geçiş) çalıştırır, her biri IR'i okuyup dönüştürür. Bu geçişler genellikle belirli bir sırada, hatta bazen birbirini tekrar tetikleyecek şekilde (fixed-point iterasyon) çalışır. En kritik olanları:

### 5.1 Constant Folding ve Constant Propagation

**Constant folding**: Derleme zamanında hesaplanabilen ifadeleri (`3 + 4`) doğrudan sonuca (`7`) indirger. **Constant propagation**: Bir değişkenin sabit bir değer taşıdığı biliniyorsa, kullanıldığı her yerde bu değerle değiştirir. SSA formu bunu kolaylaştırır çünkü her SSA değeri tam olarak bir tanıma sahiptir - "bu değer her zaman sabittir" önermesi kanıtlaması kolaydır. **Sparse Conditional Constant Propagation (SCCP)**, hem sabitleri yayar hem de ulaşılamayan kod dallarını (unreachable branches) aynı geçiste tespit eder - bu, sadelik ve etkinliğin klasik bir örneğidir.

**Kök neden - neden önemli**: Bu, sonraki tüm geçişler için "temizlik" katmanıdır; şablon kod (template/generic instantiation), inline edilmiş fonksiyonlar genellikle çok sayıda sabit ifade bırakır, bunları erken temizlemek sonraki analizlerin arama uzayını küçültür.

### 5.2 Dead Code Elimination (DCE)

Sonucu hiçbir yerde kullanılmayan (ve yan etkisi olmayan) hesaplamaları siler. SSA'da bu, use-def zincirlerinde "sıfır kullanımı olan tanım" tespiti kadar basittir. **Aggressive DCE**, önce her şeyi "ölü" varsayar, sonra canlı olduğu kanıtlanabilenleri işaretler (mark-sweep benzeri); bu, döngüsel bağımlılıklarda (örneğin birbirine referans veren ölü kod) daha güçlü sonuç verir.

**Tuzak**: Yan etkili çağrıları (I/O, volatile bellek erişimi, sistem çağrıları) yanlışlıkla silmek felaket sonuçlara yol açar; bu yüzden derleyiciler "saf" (pure/no side-effect) fonksiyonları özel olarak işaretler (LLVM'de `readnone`, `readonly` attribute'leri gibi).

### 5.3 Inlining

Bir fonksiyon çağrısını, çağrılan fonksiyonun gövdesiyle değiştirme işlemidir. **Neden kritik**: Inlining, tek başına bir optimizasyon olmaktan çok, diğerlerinin **etkinleştiricisidir**. Bir fonksiyon inline edildikten sonra, çağıran bağlamdaki sabit değerler fonksiyon gövdesine sızabilir, bu da constant folding, dead code elimination gibi geçişlerin daha önce görmediği fırsatları açar.

**Maliyet-fayda dengesi**: Agresif inlining kod boyutunu (code bloat) patlatır, bu da instruction cache başarısızlığını artırıp performansı *düşürebilir*. Derleyiciler bunun için sezgisel maliyet modelleri kullanır: fonksiyon gövdesinin "küçüklüğü", çağrı sıklığı (profil rehberli optimizasyonda - PGO - gerçek çalışma zamanı verisiyle), özyinelemeli (recursive) olup olmadığı gibi faktörlere göre karar verir. LLVM'in inline cost modeli, sanal talimat sayısı üzerinden bir eşik değeri kullanır ve bu eşik `-O2` / `-O3` seviyelerinde farklıdır.

**Yaygın hata**: Özyinelemeli fonksiyonların sınırsız inline edilmeye çalışılması derleme süresini patlatır; derleyiciler bunun için derinlik sınırı (inline recursion limit) koyar.

### 5.4 Loop Unrolling (Döngü Açma)

Bir döngü gövdesini N kez kopyalayıp döngü sayacını N'e bölerek döngü-kontrol overhead'ini (sayaç artırma, sınır kontrolü, dallanma) azaltır. Ayrıca ardışık komut işleme hatlarının (pipeline) daha iyi doldurulmasını ve komut seviyesi paralelliğin (ILP) ortaya çıkmasını sağlar.

**Kök neden**: Modern CPU'lar derin pipeline ve superscalar yürütmeye sahiptir; küçük döngü gövdeleri her iterasyonda dallanma tahmini (branch prediction) riski taşır ve pipeline'i yeterince dolduramaz. Unrolling, bağımsız işlemleri yan yana getirerek derleyicinin/işlemcinin bunları paralel yürütmesine izin verir.

**Tuzaklar**:
- Aşırı unrolling, kod boyutunu büyütür, instruction cache miss oranını artırabilir - bu da "unrolling paradoksu" olarak bilinir: teorik ILP kazancı pratikte cache kaybına yenilebilir.
- Döngü sınırları derleme zamanında bilinmiyorsa (değişken uzunluklu diziler), "artık döngü" (remainder loop) için ek kod üretilmesi gerekir, bu da karmaşıklığı artırır.
- Vektorizasyon (SIMD) ile birlikte düşünülmelidir; bazen unrolling'in asıl amacı vektör birimlerini (AVX, NEON) doldurmaktır.

### 5.5 Diğer Önemli Geçişler (Kısaca)

- **Common Subexpression Elimination (CSE)**: Aynı hesaplamanın tekrarını tespit edip tek seferde hesaplayıp sonucu paylaşır.
- **Loop-Invariant Code Motion (LICM)**: Döngü içinde değişmeyen hesaplamaları döngü dışına taşır.
- **Strength Reduction**: Pahalı işlemleri (çarpma) ucuz eşdeğerleriyle (toplama, kaydırma) değiştirir - klasik örnek, döngü indeksi çarpımlarını artımlı toplamaya çevirmek.
- **Tail Call Optimization**: Kuyruk özyinelemesini döngü haline getirip yığın (stack) büyümesini engeller.

Bu geçişlerin sırası önemlidir: örneğin inlining genellikle erken çalıştırılır çünkü sonraki geçişler için fırsat açar; DCE ise hem erken hem geç, birden fazla kez çalıştırılır çünkü her geçiş yeni "ölü kod" ortaya çıkarabilir.

## 6. Backend: IR'dan Makine Koduna

IR optimize edildikten sonra, hedef mimariye özgü backend devreye girer. Bu aşama önce IR'i **hedefe daha yakın bir temsile** (LLVM'de `SelectionDAG` -> `MachineIR`, GCC'de GIMPLE -> RTL) çevirir, sonra **komut seçimi (instruction selection)** yapar: soyut IR işlemlerini gerçek makine talimatlarına eşleştirir (örneğin bir çarpma+toplama ifadesini tek bir FMA - fused multiply-add - talimatına birleştirmek, "peephole" veya "pattern matching" tabanlı seçimle).

## 7. Register Allocation: NP-Zor Problemin Pratik Çözümü

### Kök Neden

IR seviyesinde sınırsız sayıda "sanal register" (virtual register) vardır - her SSA değeri kendi register'ına sahip gibi davranılır. Ama gerçek CPU'larda sınırlı sayıda fiziksel register vardır (x86-64'te genel amaçlı ~16, ARM'de benzer sayılar). Register allocation, sanal register'ları fiziksel register'lara (veya register yetersizse belleğe - "spill") eşleyen işlemdir.

### Graph Coloring Yaklaşımı

En klasik model: her sanal register bir graf düğümüdür, aynı anda "canlı" (live) olan (yani değerleri çakışan) iki register arasında kenar (edge) çizilir. Bu **interference graph**'i K renkle (K = fiziksel register sayısı) boyamak, register allocation'a eşdeğerdir - ve graf boyama genel olarak NP-zor bir problemdir.

Chaitin-Briggs algoritması pratikte kullanılan klasik yaklaşımdır: düşük dereceli (K'dan az komşusu olan) düğümleri yığına atıp graftan çıkar, kalan yüksek dereceli düğümler için "olası spill adayları" işaretle, yığını tersten boyayarak geri yükle. Boyanamayan düğümler belleğe "spill" edilir (yani her erişimde bellekten yükleme/belleğe yazma talimatı eklenir - bu, performans maliyetlidir ve register allocation'in temel amacı spill sayısını minimize etmektir).

### Linear Scan: Hız-Kalite Denge Noktası

Graph coloring yüksek kaliteli tahsis yapar ama pahalıdır (JIT derleyiciler için çok yavaş olabilir). **Linear scan register allocation**, canlılık aralıklarını (live intervals) bir doğru üzerinde sıralayıp açgözlü (greedy) şekilde register atar - graf inşa etmez, bu yüzden çok daha hızlıdır. JIT ortamlarında (JVM'in bazı katmanları, bazı WebAssembly motorları) tercih edilir çünkü derleme süresi çalışma zamanının bir parçasıdır. LLVM'in varsayılan allocator'ı ("greedy" register allocator) ikisinin fikirlerini karıştıran, öncelik kuyruğuna dayalı daha gelişmiş bir yaklaşımdır.

### SSA'nın Register Allocation'a Katkısı

SSA formunda her değerin tek bir tanıma sahip olduğu için canlılık aralıkları (live ranges) hesaplaması klasik IR'a göre çok daha basittir - bu, "SSA-based register allocation" (örneğin SSA grafiğinin bir kordal graf - chordal graph - olduğu gözlemine dayanan yaklaşımlar) modern derleyicilerin tercih ettiği yöntemdir, çünkü kordal graflar polinom zamanda optimal boyanabilir.

### Yaygın Hatalar ve En İyi Pratikler

- **Spill maliyetini yanlış hesaplamak**: Sık kullanılan (döngü içinde) bir değeri spill etmek, nadir kullanılan bir değeri spill etmekten çok daha pahalıdır; iyi bir allocator kullanım sıklığını (loop nesting depth ağırlıklı) maliyet fonksiyonuna dahil eder.
- **Calling convention ihlali**: Register allocation, fonksiyon çağrı kurallarına (hangi register'lar caller-saved/callee-saved) uymak zorundadır; bu kural yanlış uygulanırsa fonksiyon sınırlarında veri bozulması (miscompilation) oluşur - bu tür hatalar tespit etmesi en zor derleyici hatalarındandır.
- **Register pressure farkındalığı**: Bazı optimizasyonlar (aşırı agresif unrolling, aşırı inlining) SSA değerlerinin sayısını artırıp register baskısını yükseltir, bu da daha fazla spill'e ve net performans kaybına yol açabilir - optimizasyon geçişleri arasındaki bu gerilim, "phase ordering problemi" olarak bilinir ve tek doğru çözümü yoktur.

## 8. LLVM ve GCC Boru Hattı: Pratik Karşılaştırma

**LLVM**: Clang (front-end) kaynak kodu LLVM IR'a çevirir. IR üzerinde `opt` aracıyla çalıştırılan optimizasyon geçişleri (pass manager, yeni "New Pass Manager" mimarisiyle modülerdir) sırayla uygulanır. Sonra `llc` (veya JIT için `MCJIT`/`ORC`) hedefe özgü SelectionDAG üzerinden makine koduna çeviri yapar. LLVM IR'in metin formatında okunabilir olması (`.ll` dosyaları), eğitim ve hata ayıklama açısından büyük avantajdır - bir geliştirici `clang -S -emit-llvm` ile ara adımı gözlemleyebilir.

**GCC**: Farklı bir iç mimariye sahiptir - önce GENERIC (dilden bağımsız ağaç formu), sonra **GIMPLE** (SSA benzeri, sadeleştirilmiş üç-adresli koda yakın form) üretilir, optimizasyonların çoğu GIMPLE üzerinde SSA formunda çalışır, son aşamada **RTL** (Register Transfer Language) hedefe daha yakın bir temsile geçer ve register allocation/instruction scheduling burada yapılır.

Her iki sistem de temelde aynı felsefeyi paylaşır: **çok katmanlı IR, her katmanda uygun soyutlama seviyesinde optimizasyon**. Fark, katmanların isimlendirilmesi ve modülerlik derecesindedir - LLVM'in tek, iyi belgelenmiş IR'i onu kütüphane olarak yeniden kullanılabilir kılarken (bu yüzden Rust, Swift, Julia gibi diller LLVM'i backend olarak seçmiştir), GCC'nin çok aşamalı dahili temsilleri tarihsel olarak daha az dışa açık olmuştur.

## 9. Savunma ve Tespit Perspektifi: Bir Mühendis Neden Bunu Bilmeli

Derleyici iç yapısını anlamak, savunma/güvenlik mühendisliği açısından somut faydalar sağlar:

- **Undefined Behavior (UB) istismarı**: Optimizasyon geçişleri, dilin UB tanımladığı durumlarda (imzalı taşma - signed overflow, null pointer dereference sonrası kod) "bu asla olmaz" varsayımıyla kod silebilir veya yeniden düzenleyebilir. Bir güvenlik kontrolü (örneğin taşma kontrolü) UB'ye dayanıyorsa, derleyici bunu optimize ederek tamamen kaldırabilir - bu, "compiler optimized away my security check" sınıflandırmasının kök nedenidir. Savunma: UB'den bağımsız, tanımlanmış davranışa (defined behavior) dayanan kontroller yazmak (örneğin overflow kontrolü için derleyici intrinsics veya `checked` aritmetik kullanmak).
- **Side-channel analizi**: Sabit zamanlı (constant-time) kriptografik kod yazarken, derleyici optimizasyonlarının (dallanmayı elemine etme, dead code elimination'in "gizli" sıfırlama kodunu silmesi) zamanlama side-channel'ları yeniden açabileceğini bilmek kritiktir. Bu yüzden kriptografik kütüphaneler genellikle `volatile` işaretleri veya derleyiciye özgü bariyerler (compiler barrier) kullanır.
- **Reverse engineering ve binary analiz**: Bir binary'nin optimize edilmiş halini analiz ederken (malware analizi, zafiyet araştırması), inlining ve loop unrolling gibi dönüşümlerin kaynak kod yapısını nasıl gizlediğini/değiştirdiğini bilmek, disassembly'i doğru yorumlamak için şarttır. Örneğin agresif inlining sonrası tek bir fonksiyon gibi görünen kod aslında onlarca küçük fonksiyonun birleşimidir.
- **Tedarik zinciri güvenliği (reproducible builds)**: Optimizasyon geçişlerinin deterministik olmaması (örneğin paralel derleme sırasında register allocation'in hash tablosu iterasyon sırasına bağlı olması) aynı kaynaktan farklı binary üretebilir; bu, "reproducible build" doğrulama sistemlerinin (kaynak kod ile binary'nin eşleştiğini kanıtlama) karşılaştığı temel teknik zorluktur.

## Sonuç

Derleyici boru hattı, her katmanının kendi soyutlama seviyesinde çalıştığı, birbirini besleyen bir sistem mühendisliği harikasıdır: lexer/parser sözdizimini yakalar, semantik analiz anlamı doğrular, IR ve özellikle SSA formu optimizasyonları verimli kılar, sıralı optimizasyon geçişleri (constant folding, inlining, loop unrolling gibi) performans fırsatlarını ortaya çıkarır, register allocation ise sınırlı fiziksel kaynaklarla bu soyut IR'i gerçek makine koduna sığdırır. Bu katmanların her biri kendi tuzaklarına sahiptir ve bir mühendis için bu iç yapıyı anlamak, sadece merak değil; performans hata ayıklama, güvenlik analizi ve doğru, sağlam kod yazma becerisinin temelini oluşturur.
