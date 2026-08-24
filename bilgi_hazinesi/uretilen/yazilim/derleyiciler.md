# Derleyiciler ve Yorumlayıcılar

## Giriş: Bir Metni Çalıştırılabilir Anlama Dönüştürmek

Bir programlama dili, insanın okuyabildiği bir metindir; işlemci ise yalnızca ikili makine kodunu (opcode'ları) çalıştırabilir. Aradaki bu uçurumu kapatan yazılım katmanına **derleyici** (compiler) ya da **yorumlayıcı** (interpreter) denir. İkisi de aynı temel işi yapar: kaynak metni okur, anlamlandırır ve o anlamı ya makine koduna çevirir ya da doğrudan yürütür. Fark, *ne zaman* çeviri yaptıklarındadır.

Bir derleyici, kaynağı önceden (ahead-of-time) alıp hedef bir gösterime (makine kodu, bytecode, başka bir dil) çevirir; çıktı ayrı bir artefakt olarak kalır. Bir yorumlayıcı ise programı satır satır ya da düğüm düğüm gezerek anında çalıştırır. Modern sistemlerde bu ayrım bulanıklaşmıştır: Java, C#, Python, JavaScript gibi diller kaynağı önce **bytecode**'a derler, sonra bir sanal makine (VM) bu bytecode'u yorumlar; sıcak (hot) kod parçaları ise **JIT** (Just-In-Time) derleyici tarafından çalışma anında makine koduna çevrilir. Yani "derleyici mi yorumlayıcı mı" sorusu genellikle yanlış sorudur; gerçek soru, çevirinin hangi aşamalarda ve ne zaman yapıldığıdır.

Bu makale, kaynak metinden çalıştırmaya giden boru hattını (pipeline) sırayla ele alır: **lexing** (sözcüksel çözümleme), **parsing** (sözdizimsel çözümleme), **AST** (soyut sözdizim ağacı), **semantik analiz**, **kod üretimi** ve **JIT** temelleri. Her aşamada yalnızca *ne* olduğunu değil, *neden* öyle tasarlandığını da açıklamaya çalışacağım.

## Genel Boru Hattı (Pipeline)

Klasik bir derleyici genellikle iki büyük kısma ayrılır: **ön uç** (front end) ve **arka uç** (back end). Ön uç dile bağımlıdır; kaynağı okur, doğrular ve dilden bağımsız bir **ara gösterime** (IR — Intermediate Representation) çevirir. Arka uç ise hedef makineye bağımlıdır; IR'yi alıp optimize eder ve hedef mimari için makine kodu üretir.

Bu ayrımın kök nedeni pratiktir: N dili M mimariye derlemek istiyorsanız, ön uç/arka uç ayrımı sayesinde N + M bileşen yazarsınız, N × M değil. LLVM'in tüm mimarisi tam olarak bu içgörüye dayanır: her dil kendi ön ucuyla LLVM IR üretir, LLVM arka ucu ise bu ortak IR'yi onlarca farklı mimariye çevirir.

Tipik akış şöyledir:

```
Kaynak metin
   -> Lexer (token akışı)
   -> Parser (AST)
   -> Semantik analiz (tip kontrolü, isim çözümleme)
   -> Ara gösterim (IR)
   -> Optimizasyon geçişleri (passes)
   -> Kod üretimi (makine kodu / bytecode)
```

Yorumlayıcılarda bu zincirin sonu farklıdır: IR yerine genellikle AST doğrudan gezilir (tree-walking) ya da bytecode üretilip bir sanal makinede yürütülür.

## Lexing (Sözcüksel Çözümleme)

### Tanım

**Lexer** (ya da scanner, tokenizer), ham karakter akışını anlamlı en küçük birimlere, yani **token**'lara böler. `x = 42 + y` metni, lexer'dan `IDENT(x)`, `EQUALS`, `NUMBER(42)`, `PLUS`, `IDENT(y)` gibi bir token dizisi olarak çıkar. Boşluklar, sekmeler ve yorumlar bu aşamada genellikle atılır (bazı dillerde girinti anlamlı olduğu için istisna vardır).

### Kök Neden: Neden Ayrı Bir Aşama?

Parser'ı doğrudan karakterler üzerinde çalıştırmak teknik olarak mümkündür ama pratikte kötü bir fikirdir. Ayrımın nedeni **soyutlama katmanlaması**dır: parser, `if` anahtar sözcüğünün "i", "f" harflerinden oluştuğunu bilmek zorunda kalmaz; ona tek bir `IF` token'ı gelir. Bu, gramerin çok daha sade olmasını sağlar. Ayrıca lexing, **düzenli diller** (regular languages) düzeyinde bir problemdir ve **sonlu durum otomatı** (finite automaton) ile çözülebilir; oysa parsing **bağlamdan bağımsız diller** (context-free languages) düzeyinde bir iştir ve daha güçlü, dolayısıyla daha yavaş makine gerektirir. Ucuz olan işi (karakterleri gruplama) ayrı ve hızlı bir aşamada yapmak, pahalı olanı (yapı çıkarma) rahatlatır.

### Çalışma Mantığı

Lexer'ın kalbinde çoğu zaman bir **DFA** (Deterministic Finite Automaton) vardır. Her token türü bir düzenli ifadeyle (regular expression) tanımlanır; bu ifadeler bir DFA'ya derlenir. Lexer, girişteki karakterleri okurken durumlar arasında geçer ve genellikle **maximal munch** (en uzun eşleşme) kuralını uygular: mümkün olan en uzun token'ı alır. Bu yüzden `>=` iki ayrı token değil, tek bir `GREATER_EQUAL` olur; lexer `>` gördükten sonra bir sonraki karakteri de kontrol eder.

Bir başka klasik örnek: `1..10` gibi bir aralık ifadesi. Naif bir lexer `1.` kısmını ondalık sayı başlangıcı sanabilir. Doğru davranış, sayısal literalleri okurken ileriye bakış (lookahead) yaparak ikinci noktayı görünce sayıyı `1` ve operatörü `..` olarak ayırmaktır.

### Yaygın Hatalar ve Tuzaklar

- **Anahtar sözcük ve tanımlayıcı karışıklığı:** Çoğu dilde `while`, `return` gibi anahtar sözcükler aslında geçerli birer tanımlayıcı biçimindedir. Lexer önce bunları `IDENT` olarak okuyup, ardından bir tablo araması (lookup) ile anahtar sözcük olup olmadığını belirlemelidir. Her anahtar sözcük için ayrı bir düzenli ifade tanımlamak DFA'yı gereksiz büyütür.
- **Girinti duyarlı diller:** Python gibi dillerde girinti bloğu belirler. Bunun için lexer, girinti seviyelerini bir yığında (stack) tutup sanal `INDENT` ve `DEDENT` token'ları üretmelidir. Bu, saf düzenli dil modelini aşan, durum tutan (stateful) bir lexer gerektirir.
- **Konum bilgisini kaybetmek:** Token'lar yalnızca türlerini değil, kaynak dosyadaki satır ve sütun bilgilerini de taşımalıdır. Aksi halde ilerideki aşamalarda anlamlı hata mesajı üretmek imkânsız hale gelir. Konum bilgisini en baştan token'a iliştirmemek, sonradan telafisi çok zor bir eksikliktir.

## Parsing (Sözdizimsel Çözümleme)

### Tanım

**Parser**, düz token akışını, dilin gramerine göre hiyerarşik bir yapıya dönüştürür. `2 + 3 * 4` token dizisi, çarpmanın toplamadan önce geldiği bir ağaç yapısına çevrilir; böylece `*` düğümü `+` düğümünün altında değil, çocuğunda yer alır. Parser'ın görevi, "bu token dizisi dilin grameri açısından geçerli mi ve yapısı nedir?" sorusunu yanıtlamaktır.

### Kök Neden: Neden Gramer ve Ağaç?

Programlar özyinelemeli (recursive) yapılardır: bir ifade başka ifadeler içerir, bir blok başka bloklar içerir. Düz bir liste bu iç içeliği ifade edemez. **Bağlamdan bağımsız gramer** (context-free grammar), tam da bu özyinelemeli iç içeliği tanımlamak için doğru araçtır. Gramer, terminaller (token'lar) ve terminal olmayanlar (kurallar) üzerinden üretim kuralları tanımlar; parser bu kuralları kullanarak token akışının o gramerden türetilip türetilemeyeceğini gösterir.

### İki Ana Yaklaşım

**Yukarıdan aşağıya (top-down) — Recursive Descent ve LL:** Her gramer kuralı için bir fonksiyon yazılır; `parseExpression`, `parseTerm`, `parseFactor` gibi. Parser en üstteki kuraldan başlar ve token'ları tükettikçe alt kurallara iner. Elle yazması ve okuması en kolay yöntem budur; birçok üretim düzeyi dil (örneğin bazı C ve C++ derleyicileri) elle yazılmış recursive descent parser kullanır çünkü hata mesajları üzerinde tam kontrol sağlar. Zorluğu, **sol özyineleme** (left recursion) ile başa çıkamamasıdır: `expr -> expr + term` gibi bir kural doğrudan sonsuz döngüye yol açar ve gramerin yeniden yazılmasını gerektirir.

**Aşağıdan yukarıya (bottom-up) — LR, LALR:** Bu yaklaşım token'ları bir yığında biriktirir (shift) ve gramer kurallarıyla eşleşince indirger (reduce). Yacc, Bison, ANTLR gibi **parser üreteçleri** (parser generators) genellikle bu ailedendir. LR parser'lar daha geniş bir gramer sınıfını, sol özyineleme dahil, doğrudan işleyebilir. Bedeli, üretilen tabloların ("shift-reduce" tabloları) karmaşıklığı ve çakışma (conflict) çıktığında hata ayıklamanın zorluğudur.

**Operatör önceliği (Pratt parsing):** İfade ayrıştırma için özellikle zarif bir teknik, her operatöre bir "bağlama gücü" (binding power) atayan Pratt parser'dır. `2 + 3 * 4` gibi ifadelerde önceliği ve birleşmeyi (associativity) tablo bakışıyla temiz biçimde çözer ve recursive descent iskeletine kolayca oturur.

### Somut Örnek: Öncelik Neden Önemli?

`2 + 3 * 4` ifadesini düşünün. Gramer, önceliği doğru kodlamazsa parser bunu `(2 + 3) * 4 = 20` olarak yapılandırabilir. Doğru sonuç `2 + (3 * 4) = 14`'tür. Çözüm, grameri katmanlamaktır: toplama seviyesi çarpma seviyesini çağırır, çarpma seviyesi ise en alttaki temel ifadeleri (sayı, parantez) çağırır. Böylece çarpma her zaman ağacın daha derinine, yani daha önce hesaplanacak konuma yerleşir.

### Yaygın Hatalar ve Tuzaklar

- **Sol özyinelemeyi görmezden gelmek:** Recursive descent yazarken gramer kuralını doğrudan koda çevirip sol özyinelemeli kuralı fark etmemek, anında yığın taşmasına (stack overflow) yol açar. Kuralı yinelemeli (iterative) bir döngüye dönüştürmek gerekir.
- **Belirsiz gramerler:** Klasik "dangling else" problemi (`if a then if b then x else y` içindeki `else` hangi `if`'e ait?) gramerin belirsiz olmasından doğar. Çözüm, dilin kuralını netleştirip (genellikle en yakın `if`'e bağlamak) grameri buna göre yazmaktır.
- **Hata kurtarma eksikliği:** İyi bir parser ilk hatada durmaz; anlamlı bir mesaj üretip, güvenli bir noktaya (örneğin bir sonraki `;` veya `}`) atlayarak ayrıştırmaya devam eder (panic-mode recovery). Bu sayede kullanıcı tek çalıştırmada birden çok hatayı görür.

## AST (Soyut Sözdizim Ağacı)

### Tanım

**AST** (Abstract Syntax Tree), programın anlamlı yapısını temsil eden ağaç veri yapısıdır. "Soyut" olmasının nedeni, kaynaktaki her ayrıntıyı (parantezler, noktalı virgüller, boşluklar) taşımamasıdır; yalnızca anlam için gerekli olanı tutar. Bunun karşıtı **somut sözdizim ağacıdır** (parse tree ya da concrete syntax tree), gramerin her adımını, gereksiz düğümler dahil birebir yansıtır.

### Kök Neden: Neden Somut Değil de Soyut?

`(2 + 3)` ifadesindeki parantezler, ayrıştırma sırasında gruplamayı belirlemek için gereklidir; ama ağaç yapısı bir kez kurulunca gruplama zaten ağacın şeklinde kodlanmıştır. Parantez düğümünü ağaçta tutmak, sonraki her aşamayı (tip kontrolü, optimizasyon, kod üretimi) gereksiz yere zorlaştırır. AST, "artık ihtiyaç kalmayan sözdizimsel gürültüyü at" ilkesidir. Böylece `2 + 3` ile `(2 + 3)` ile `((2 + 3))` aynı AST'yi üretir; anlamları da aynıdır zaten.

### AST Neden Merkezî?

AST, derleyicinin geri kalanının üzerinde çalıştığı ana veri yapısıdır. Semantik analiz AST'yi gezerek tip hataları arar; optimizasyonların bir kısmı AST üzerinde yapılır; kod üretimi AST'yi (ya da ondan türeyen IR'yi) tarayarak talimat üretir. Bu yüzden AST'nin tasarımı, tüm derleyicinin ergonomisini belirler.

Pratikte AST düğümleri genellikle bir taban tip ve alt tipler hiyerarşisi olarak modellenir: `Expr`, `Stmt` gibi taban tipler; `BinaryExpr`, `CallExpr`, `IfStmt`, `WhileStmt` gibi alt tipler. AST üzerinde işlem yapmak için sıklıkla **Visitor** tasarım deseni kullanılır: her düğüm türü için ne yapılacağını ayrı ayrı tanımlayan bir gezici (visitor), ağacı dolaşırken doğru işlemi çağırır. Bunun kök nedeni, "ağaç yapısını gezme" mantığını "her düğümde ne yapılacağı" mantığından ayırmaktır; böylece tip kontrolü, kod üretimi ve yazdırma gibi farklı işlemler aynı ağaç üzerinde bağımsız birer visitor olarak yazılabilir.

### Somut Örnek

`x = 2 + 3 * 4` ifadesinin AST'si kabaca şöyledir:

```
Assign
├── target: Ident("x")
└── value: Binary(+)
            ├── left:  Number(2)
            └── right: Binary(*)
                       ├── left:  Number(3)
                       └── right: Number(4)
```

Bu ağaçta öncelik zaten yapının içine gömülüdür. Çarpma, toplamanın çocuğu olduğu için doğal olarak önce değerlendirilir. Yorumlayıcı bu ağacı sonradan (post-order) gezerse, önce yaprakları hesaplar, sonra yukarı doğru birleştirir ve doğru sonucu üretir.

## Semantik Analiz

Parsing yalnızca *yapının* geçerli olduğunu doğrular; anlamın tutarlılığını değil. `x = y + 1` sözdizimsel olarak kusursuzdur, ama `y` hiç tanımlanmamışsa ya da bir string ise anlamsızdır. **Semantik analiz** bu tür kontrolleri yapar.

İki temel görevi vardır. Birincisi **isim çözümleme** (name resolution): her tanımlayıcının hangi bildirime (declaration) karşılık geldiğini bulmak. Bunun için genellikle iç içe **kapsam** (scope) yapılarını modelleyen bir **sembol tablosu** (symbol table) kullanılır; her blok kendi kapsamını açar, içteki isimler dıştakileri gölgeleyebilir (shadowing). İkincisi **tip denetimi** (type checking): işlemlerin tiplerinin uyumlu olduğunu doğrulamak. `"metin" + 5` gibi bir ifade, dilin kurallarına göre ya hata verir ya da örtük dönüşümle (implicit conversion) yorumlanır; bu kararı semantik analiz verir.

Bu aşamanın kök nedeni, gramerin ifade edemediği kısıtları yakalamaktır. "Bir değişken kullanılmadan önce tanımlanmalıdır" ya da "fonksiyon çağrısındaki argüman sayısı imzayla eşleşmelidir" gibi kurallar bağlamdan bağımsız gramerle ifade edilemez; bunlar bağlam gerektirir. Semantik analiz, AST'yi gezerek bu bağlamsal kuralları uygular ve çoğu zaman AST'yi tip bilgisiyle zenginleştirir (annotated AST).

## Ara Gösterim (IR) ve Optimizasyon

Karmaşık derleyiciler AST'den doğrudan makine kodu üretmez; araya bir ya da birkaç **ara gösterim** (IR) katmanı koyar. IR, AST'den daha düşük seviyeli ama makine kodundan daha soyut bir temsildir. Yaygın bir biçim **SSA**'dır (Static Single Assignment): her değişkene tam olarak bir kez değer atanır; sonraki atamalar yeni sürümler yaratır (`x1`, `x2`...). Bunun kök nedeni, veri akışını (data flow) analiz etmeyi kolaylaştırmasıdır. Bir değişkenin değerinin nereden geldiği tek bir tanımla belli olduğunda, "bu değer sabit mi", "bu hesaplama gereksiz mi" gibi sorular çok daha kolay yanıtlanır.

Optimizasyonlar IR üzerinde **geçişler** (passes) hâlinde uygulanır. Klasik örnekler:

- **Sabit katlama** (constant folding): `2 + 3` derleme anında `5`'e indirgenir.
- **Ölü kod eleme** (dead code elimination): sonucu hiç kullanılmayan hesaplamalar atılır.
- **Ortak alt ifade eleme** (common subexpression elimination): aynı hesaplama iki kez yapılıyorsa bir kez yapılıp sonucu paylaşılır.
- **Satır içine alma** (inlining): küçük bir fonksiyonun gövdesi çağrı yerine kopyalanarak çağrı yükü ortadan kaldırılır ve başka optimizasyonlara kapı açılır.

Bu geçişlerin sırası önemlidir ve birbirini besler: inlining, ardından constant folding için yeni fırsatlar açabilir. Bu yüzden gerçek derleyiciler aynı geçişleri birden çok kez, belli bir çizelgeye göre çalıştırır.

## Kod Üretimi

### Tanım

**Kod üretimi** (code generation), optimize edilmiş IR'yi hedef gösterime çevirir. Hedef, gerçek bir mimarinin makine kodu (x86-64, ARM), bir sanal makinenin bytecode'u (JVM bytecode, Python bytecode) ya da bazen başka bir kaynak dil (transpilation) olabilir.

### Kök Neden ve Zorluklar

Kod üretiminin zor kısmı, sınırlı fiziksel kaynakları soyut IR'ye eşlemektir. İki klasik problem öne çıkar:

**Talimat seçimi** (instruction selection): IR'deki bir işlem, hedef mimaride birden çok talimat dizisiyle gerçekleştirilebilir. Örneğin bir çarpmayı bazı mimarilerde kaydırma (shift) ile yapmak daha ucuz olabilir. Kod üreteci, IR ağacını hedef talimatlara eşleyen en verimli örüntüyü seçmeye çalışır.

**Kayıt tahsisi** (register allocation): CPU'da sınırlı sayıda register vardır (örneğin x86-64'te genel amaçlı register sayısı tek hanelidir). Program ise keyfi sayıda değişken kullanır. Kod üreteci, hangi değişkenin ne zaman register'da tutulacağına, register'lar dolduğunda hangi değerin belleğe taşınacağına (spilling) karar vermelidir. Bu problem, **graf boyama** (graph coloring) problemine indirgenir ve genelde NP-zor olduğundan sezgisel (heuristic) yöntemlerle çözülür. Kök neden basittir: register erişimi bellek erişiminden çok daha hızlıdır, dolayısıyla sık kullanılan değerleri register'da tutmak performansı doğrudan belirler.

### Bytecode ve Sanal Makineler

Birçok dil doğrudan makine kodu yerine **bytecode** üretir. Bytecode, hayali bir "yığın makinesi" (stack machine) ya da "register makinesi" için tasarlanmış kompakt bir talimat setidir. Örneğin bir toplama işlemi, yığın tabanlı bir VM'de "iki değeri yığından çek, topla, sonucu yığına it" biçiminde birkaç bytecode talimatına dönüşür. Bunun kök nedeni **taşınabilirliktir**: aynı bytecode, üzerinde VM bulunan her platformda çalışır. Bedeli, VM'in her talimatı yorumlaması gereken çalışma anı yüküdür; işte tam bu yükü azaltmak için JIT devreye girer.

## JIT Temelleri (Just-In-Time Derleme)

### Tanım

**JIT** (Just-In-Time) derleme, programı çalışma anında, çalıştıkça makine koduna çeviren tekniktir. Saf yorumlama ile önceden derleme (AOT — Ahead-of-Time) arasında bir orta yoldur. Program başlar, yorumlanarak çalışmaya devam eder; runtime hangi kod parçalarının sık çalıştığını gözlemler ve bu "sıcak" (hot) parçaları makine koduna derleyip bir daha yorumlamak yerine doğrudan çalıştırır.

### Kök Neden: Neden Çalışma Anında?

İki kazanç bir arada elde edilir. Birincisi, AOT derleyicinin sahip olmadığı bir avantaj: **çalışma anı bilgisi**. JIT, programın gerçekte hangi tipleri kullandığını, hangi dalların (branch) gerçekte alındığını, hangi fonksiyonların gerçekte çağrıldığını gözlemler. Bu bilgiyle, statik bir derleyicinin yapamayacağı **spekülatif optimizasyonlar** uygulanabilir. Örneğin dinamik tipli bir dilde bir fonksiyon her zaman tamsayıyla çağrılıyorsa, JIT o fonksiyonu tamsayıya özelleştirilmiş (specialized) hızlı makine koduna derler.

İkincisi, **80/20 kuralı**: bir programın çalışma zamanının büyük çoğunluğu, kodun küçük bir kısmında geçer. Her şeyi önceden derlemek yerine yalnızca gerçekten sıcak olan kısmı derlemek, derleme maliyetini yatırım getirisi en yüksek yere yoğunlaştırır. Soğuk (cold) kod yorumlanmaya devam eder; onu derlemek zaman kaybı olurdu.

### Çalışma Mantığı: Katmanlı Derleme

Modern JIT'ler genellikle **katmanlı** (tiered) çalışır. Kod ilk çalıştığında yorumlanır; bu en hızlı başlangıcı verir ama en yavaş yürütmedir. Runtime, her fonksiyon ve döngü için bir sayaç (counter) tutar. Sayaç bir eşiği aştığında, o kod bir "baseline" JIT tarafından hızlıca, az optimizasyonla derlenir. Kod daha da sıcaklaşırsa, agresif optimizasyon yapan bir "optimizing" JIT devreye girer ve en hızlı makine kodunu üretir. Bu kademeleme, başlangıç gecikmesi (startup latency) ile en yüksek performans (peak performance) arasındaki gerilimi dengeler.

### Spekülasyon ve Deoptimizasyon

JIT'in gücü **spekülatif** varsayımlarında yatar, ama varsayımlar yanılabilir. JIT "bu değişken hep tamsayıdır" varsayıp kodu buna göre derledikten sonra, program bir gün o değişkene string atarsa ne olur? Burada **deoptimizasyon** (deoptimization) devreye girer: JIT, ürettiği optimize makine kodundan çıkıp yürütmeyi güvenli yorumlayıcıya geri devreder. Bunun için derlenmiş kodun içine, varsayımı doğrulayan **guard** (koruma) kontrolleri yerleştirilir; guard başarısız olursa deoptimizasyon tetiklenir. Bu mekanizma, dinamik dillerde spekülatif hızın nasıl güvenli biçimde elde edildiğinin kalbidir.

### Yaygın Hatalar ve Tuzaklar (JIT)

- **Isınma (warm-up) maliyetini görmezden gelmek:** JIT kullanan bir sistemi (örneğin JVM tabanlı bir servisi) yeni başladığı ilk saniyelerde ölçüp "yavaş" demek yanıltıcıdır; henüz sıcak kod derlenmemiştir. Kıyaslama (benchmark) yaparken ısınma süresini ayırmak gerekir.
- **Megamorfik çağrı yerleri:** JIT, bir çağrı yerinde hep aynı birkaç tip görürse (monomorfik/polimorfik) hızlı yol üretir; ama çok farklı tip görürse (megamorfik) optimizasyondan vazgeçer. Aşırı genel, her tipi kabul eden tasarımlar farkında olmadan JIT'i sabote edebilir.
- **JIT'in olmadığı bağlamları unutmak:** Kısa ömürlü süreçlerde (örneğin komut satırı araçları) program, JIT ısınmadan bitebilir; bu senaryolarda AOT derleme ya da başlangıç odaklı katmanlar daha uygundur.

## Derleyici mi, Yorumlayıcı mı? Doğru Çerçeve

Baştaki soruya dönelim. "X dili derlenir mi yorumlanır mı?" sorusu genellikle dilin değil, *uygulamasının* (implementation) özelliğidir. Aynı dilin hem yorumlayıcısı hem AOT derleyicisi hem JIT'li bir runtime'ı olabilir. Doğru çerçeve şu takasları düşünmektir:

- **Başlangıç hızı:** Yorumlayıcı ve JIT anında başlar; AOT derleme bir ön maliyet ister ama tekrar tekrar ödenmez.
- **En yüksek performans:** AOT ve optimizing JIT en hızlı yürütmeyi verir; saf yorumlayıcı en yavaşıdır.
- **Taşınabilirlik:** Bytecode + VM her yerde çalışır; AOT üretilen makine kodu tek mimariye bağlıdır.
- **Dinamiklik:** JIT, çalışma anı bilgisiyle statik derleyicinin ulaşamayacağı özelleştirmeler yapabilir.

## En İyi Pratikler

- **Aşamaları temiz ayırın.** Lexer'ın parser'a, parser'ın semantik analize sızmadığı katmanlı bir tasarım, hata ayıklamayı ve test etmeyi kökten kolaylaştırır. Her aşamanın girdisi ve çıktısı net tanımlı olmalıdır.
- **Konum bilgisini en baştan taşıyın.** Token'dan AST düğümüne kadar her yapıya kaynak konumu (satır, sütun, dosya) iliştirin. İyi hata mesajları, sonradan eklenebilen değil, en baştan tasarlanan bir özelliktir.
- **AST'yi anlam için tasarlayın, sözdizim için değil.** Gereksiz sözdizimsel gürültüyü (parantez, ayraç) ağaca sokmayın; sonraki her aşama bunun karşılığını öder.
- **Hata kurtarmayı ciddiye alın.** İlk hatada duran bir derleyici sinir bozucudur. Güvenli senkronizasyon noktalarına atlayarak birden çok hatayı tek seferde raporlayın.
- **Elle yazılmış recursive descent'i küçümsemeyin.** Parser üreteçleri güçlüdür ama üretim dillerinin çoğu, hata mesajları ve kenar durumları üzerindeki tam kontrol için elle yazılmış parser tercih eder. Basit ile güçlü arasındaki seçimi bilinçli yapın.
- **Ölçmeden optimize etmeyin.** Özellikle JIT'li sistemlerde ısınmayı hesaba katan, gerçekçi kıyaslamalar kurun; sezgiye değil profillemeye (profiling) güvenin.

## Sonuç

Bir derleyici ya da yorumlayıcı, özünde bir dizi iyi tanımlı dönüşümdür: karakterler token'lara, token'lar ağaca, ağaç anlama, anlam ara gösterime, ara gösterim makine koduna. Her aşamanın var olma nedeni, bir öncekinin bıraktığı sorunu ucuzlatmaktır — lexing parsing'i sadeleştirir, AST sonraki analizleri kolaylaştırır, IR optimizasyonu mümkün kılar. JIT ise bu klasik zincire zamanı bir boyut olarak ekler: kararı çalışma anına erteleyerek, statik derleyicinin hiç sahip olamayacağı bilgiyle daha akıllı kod üretir. Bu boru hattını anlamak, yalnızca derleyici yazmak isteyenler için değil, çalıştırdıkları dillerin performans davranışını gerçekten kavramak isteyen her yazılımcı için temel bir yetkinliktir.
