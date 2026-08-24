# Runtime İç Yapısı: VM Tasarımı, JIT Derleme, Bytecode Yorumlayıcılar

## Giriş: Neden Bu Konu Ayrı Bir Başlık Hak Ediyor

Java Virtual Machine (JVM) ve JavaScript motorları (V8, SpiderMonkey, JavaScriptCore) hakkında bolca yüzeysel bilgi vardır: "JIT hızlandırır", "bytecode taşınabilirdir" gibi. Ancak bu ifadeler, bir mühendisin gerçekten ihtiyaç duyduğu şeyi vermez: **runtime'ın içinde ne olduğunu, neden o şekilde tasarlandığını ve nerede güvenlik sınırlarının kırılabileceğini anlamak.**

Bu makale üç eksen üzerinde ilerliyor:

1. Bytecode yorumlayıcı tasarımı — neden bytecode var, nasıl çalıştırılır, hangi tasarım kararları performansı belirler.
2. JIT (Just-In-Time) derleme stratejileri — tiered compilation, inline caching, deoptimization, spekülatif optimizasyon.
3. VM güvenlik sınırları — sandbox modeli neden kırılabilir, JIT spraying gibi teknikler nasıl çalışır, ve bunlara karşı savunma nasıl kurulur.

Amaç bir "exploit tarifi" değil; bu mekanizmaları anlayan bir mühendisin hem doğru performans kararları alabilmesi hem de güvenlik açısından doğru şeyleri denetleyebilmesidir.

## Bytecode Yorumlayıcı Tasarımı

### Bytecode Neden Var

Bir kaynak dili doğrudan makine koduna derlemek yerine ara bir temsile (bytecode) derlemenin üç temel gerekçesi vardır:

- **Taşınabilirlik**: Bytecode, donanımdan bağımsız soyut bir talimat setidir. JVM'in `.class` dosyaları veya V8'in ürettiği ara temsil, farklı CPU mimarilerinde aynı şekilde yorumlanabilir.
- **Hızlı başlangıç (startup) maliyeti**: Tam optimize edici bir derleyici çalıştırmak pahalıdır. Bytecode'a derleme hızlıdır; program hemen çalışmaya başlar, optimizasyon sonradan (JIT ile) gelir.
- **Analiz ve enstrümantasyon kolaylığı**: Bytecode seviyesinde tip kontrolü (JVM bytecode verifier gibi), profilleme sayaçları ekleme, güvenlik denetimleri yapma makine koduna göre çok daha kolaydır.

Kök neden budur: **derleme zamanı maliyetini çalışma zamanına yayarak, hem taşınabilirlik hem de kademeli optimizasyon imkânı elde edersin.** Bu bir mühendislik ödünleşimidir — statik derlenmiş dillerin (C, Rust) sahip olmadığı bir esneklik, ama başlangıçta yorumlama yavaşlığı bedeliyle.

### Yorumlayıcı Türleri

**1. Switch-dispatch yorumlayıcı (naive interpreter)**

En basit tasarım: bir `while` döngüsü içinde bytecode'u oku, `switch` ifadesiyle opcode'a göre dallan, işlemi yap, sıradaki talimata geç. Basit ama iki maliyeti var:

- Dal tahmini (branch prediction) her adımda `switch` içindeki jump table'a bağımlı kalır; CPU'nun dal tahmincisi burada zayıf çalışır çünkü hedef adres her seferinde veriye bağlı olarak değişir (indirect branch).
- Döngü/switch overhead'i her bytecode talimatı için tekrarlanır.

**2. Threaded dispatch (computed goto / direct threading)**

Her bytecode talimatının sonunda, bir sonraki talimatın işleyicisine doğrudan atlarsın (goto ile), merkezi bir switch'e dönmeden. GCC'nin `&&label` (labels-as-values) uzantısı klasik örnektir. Bu, dal tahmincisinin her opcode çifti için ayrı bir geçmiş tutabilmesini sağlar, dolayısıyla tahmin isabeti artar. CPython'un bytecode yorumlayıcısı ve Lua'nın referans implementasyonu bu tekniği kullanır.

**3. Register-based vs stack-based bytecode**

JVM bytecode'u yığın tabanlıdır (stack-based): her talimat operandlarını sanal bir yığından alır, sonucu yığına koyar (`iadd` gibi). Bu tasarım basit ve kompakttır ama fazladan push/pop talimatı üretir. Lua 5.x ve Android'in Dalvik/ART'ı register tabanlı bytecode kullanır: talimatlar sanal register'lar üzerinde çalışır (`ADD r1, r2, r3` gibi), bu da daha az talimat sayısı ve daha az bellek trafiği demektir, ama bytecode encoding'i biraz daha karmaşıktır.

Kök neden mantığı şu: **yığın tabanlı tasarım derleyiciyi (bytecode üretimini) basitleştirir, register tabanlı tasarım ise yorumlama/JIT performansını artırır.** İkisi arasındaki seçim, dilin öncelik verdiği şeye (basitlik mi, ham hız mı) bağlıdır.

### Inline Caching'in Temeli Burada Atılır

Dinamik dillerde (`obj.field` veya `obj.method()`) her erişimde tipin ne olduğu çalışma zamanında belli olur. Bytecode yorumlayıcı seviyesinde bile "monomorphic inline cache" fikri uygulanabilir: bir talimatın yanına, "son çağrıldığında bu obje şu şekildeydi, offset şuydu" bilgisini gizlice yazarsın. Bu, JIT'in daha gelişmiş halinin temelini oluşturur (aşağıda detaylandırılıyor).

## JIT Derleme Stratejileri

### Neden Salt Yorumlama Yetmez, Salt Derleme de Yetmez

Statik derleme (AOT - Ahead Of Time) en hızlı çalışan kodu üretebilir ama iki dezavantajı vardır: (1) çalışma zamanı tip bilgisine erişemez, dolayısıyla dinamik dillerde agresif optimizasyon yapamaz; (2) her fonksiyonu optimize etmek derleme süresini şişirir, oysa bir programın kodunun büyük kısmı hiç ya da az çalışır (Pareto ilkesi: kodun %10'u zamanın %90'ını tüketir — "hot path").

JIT'in kök mantığı: **çalışma zamanında hangi kodun sık çalıştığını (hot) gözlemle, sadece onu optimize et, geri kalanı yorumlayarak veya hafif derleyerek geç.** Bu, derleme maliyetini gerçek faydaya göre dağıtır.

### Tiered Compilation (Katmanlı Derleme)

Modern VM'ler (HotSpot JVM, V8) tek adımda "yorumla → tam optimize et" yapmaz; birden fazla katman kullanır:

- **Tier 0 — Yorumlayıcı**: Kod hemen çalışmaya başlar, hiç derleme maliyeti yok. Aynı zamanda profil bilgisi toplanır: hangi dallar alınıyor, hangi tipler görülüyor, hangi metodlar kaç kez çağrılıyor.
- **Tier 1 — Hızlı JIT (baseline/client compiler, V8'de "Sparkplug" veya eski "Full-codegen")**: Basit, hızlı derleme yapan, az optimizasyonlu bir derleyici. Amaç: yorumlamadan daha hızlı kod üretmek ama derleme süresini düşük tutmak.
- **Tier 2 — Optimize edici JIT (HotSpot'ta C2, V8'de "TurboFan", JavaScriptCore'da "DFG/FTL")**: Profil verisini kullanarak agresif, spekülatif optimizasyonlar uygular (inlining, tip özelleştirme, loop unrolling, escape analysis).

Bir metod "sıcak" (hot) hale geldikçe (çağrı sayacı bir eşiği aşınca) bir üst katmana terfi eder (bu sürece "on-stack replacement" / OSR de dahildir — çalışmakta olan bir döngü bile ortasında optimize edilmiş koda geçebilir).

Kök neden: **derleme maliyeti ile kod kalitesi arasında sürekli bir ödünleşim vardır; katmanlama bu ödünleşimi statik değil dinamik hale getirir**, yani karar "bu kod gerçekten sık çalışıyor mu" sorusuna göre çalışma zamanında verilir.

### Inline Caching (IC) — Dinamik Tip Çözümlemesini Hızlandırma

Dinamik dillerde `obj.x` gibi bir erişim, tipik olarak bir hash tablosu araması gerektirir (JavaScript'te obje şekli / property bulma). Bu her erişimde tekrarlanırsa çok yavaştır. Inline caching şu fikre dayanır:

- **Monomorphic IC**: "Bu çağrı noktası (call site) şimdiye kadar hep aynı 'shape' (V8 terminolojisinde hidden class/map) ile karşılaştı" varsayımıyla, bulunan offset'i doğrudan çağrı noktasına gömersin. Bir sonraki çağrıda shape kontrolü (tek bir pointer karşılaştırması) yapılır, tutarsa doğrudan önbelleğe alınmış offset kullanılır — hash arama tamamen atlanır.
- **Polymorphic IC**: Aynı çağrı noktası 2-4 farklı shape ile karşılaşıyorsa, küçük bir dispatch tablosu tutulur.
- **Megamorphic**: Çok fazla farklı shape görülürse IC pes eder, genel (yavaş) yola düşer.

Bu, V8'in "hidden class" sisteminin (obje şekillerini sınıf gibi ele alma) temel motivasyonudur: JavaScript'te objeler dinamik olsa da, **pratikte çoğu obje aynı sırayla aynı property'lerle oluşturulur**, dolayısıyla runtime bunu tespit edip statik dillerdeki gibi sabit offset erişimi simüle edebilir.

Kök neden: **spekülasyon + doğrulama modeli.** "Genelde böyle olur" varsayımı yapılır, ama her seferinde ucuz bir doğrulama (guard) eklenir. Varsayım tutmazsa yavaş yola veya deoptimize etmeye düşülür.

### Spekülatif Optimizasyon ve Deoptimization

JIT'in en agresif kazançları spekülasyondan gelir: "bu değişken hep integer olarak geldi, öyleyse integer varsayıp kod üreteyim", "bu metod hiç override edilmedi, öyleyse virtual call yerine doğrudan çağrı (devirtualization) yapayım", "bu dizi sınırları hep aşılmadı, bounds check'i kaldırayım."

Bu varsayımlar bir **guard** (koruma kontrolü) ile korunur: üretilen makine kodunun başında ucuz bir kontrol vardır ("gerçekten integer mı, gerçekten override edilmemiş mi"). Varsayım bozulursa (örneğin fonksiyon artık string de alıyor, ya da bir alt sınıf metodu override etti), VM **deoptimization** yapar:

1. Optimize edilmiş makine kodundan çıkılır.
2. Register ve yığın durumu, yorumlayıcının anlayacağı bytecode seviyesindeki duruma "yeniden yapılandırılır" (deoptimization her zaman güvenli bir noktada, genellikle "deopt point" olarak önceden hesaplanmış eşlemeler sayesinde yapılabilir).
3. Yürütme yorumlayıcıya (veya alt bir tier'e) geri düşer.
4. Sık deopt olan kod, bazen "artık optimize etme, hep yorumla" diye işaretlenebilir (aksi halde optimize-et → deopt-et döngüsü tekrar tekrar performansı yer, buna "deopt loop" denir).

Kök neden mantığı: **spekülasyon olmadan agresif optimizasyon mümkün değildir çünkü dinamik dillerde statik garanti yoktur; ama spekülasyon güvenlik ağı (deoptimization) olmadan da imkânsızdır çünkü yanlış varsayım programı bozardı.** JIT tasarımının kalbi bu iki mekanizmanın (guard + deopt) doğru ve ucuz şekilde birlikte çalışmasıdır.

### Escape Analysis ve Diğer Optimizasyonlar

- **Escape analysis**: Bir objenin metod dışına "kaçıp kaçmadığını" (referansının saklanıp saklanmadığını) analiz eder. Kaçmıyorsa, heap'te ayırmak yerine stack'te ayrılabilir (stack allocation) ya da tamamen elenip alanları register'a dönüştürülebilir (scalar replacement). Bu, GC baskısını azaltır.
- **Loop-invariant code motion, unrolling, vectorization**: Klasik derleyici optimizasyonları, JIT bağlamında da uygulanır ama derleme süresi bütçesi kısıtlı olduğu için hangi metodlara uygulanacağı profil verisiyle seçilir.
- **Inlining**: Küçük, sık çağrılan fonksiyonları çağrı yerine gömmek, hem çağrı overhead'ini kaldırır hem de sonraki optimizasyonlara (ör. sabitleme, dead code elimination) daha büyük bir görüş alanı açar. Aşırı inlining ise kod şişmesine (code bloat) ve komut önbelleği (I-cache) baskısına yol açabilir — bu yüzden VM'ler bütçe/heuristik sınırları koyar.

## VM Güvenlik Sınırları

### Sandbox Modeli Neden Var, Neden Kırılabilir

Tarayıcıdaki JavaScript motoru veya JVM'in "sandboxed" (bir sistem çağrısına, dosya sistemine doğrudan erişemeyen) çalışması, güvenin **derleyici/yorumlayıcının doğruluğuna** dayandığı anlamına gelir. Yani: "bu dil bellek güvenlidir" iddiası, aslında "bu VM implementasyonu bellek güvenliğini doğru uyguluyor" iddiasına indirgenir. VM'in kendisi genelde C++ ile (bellek güvensiz bir dille) yazıldığı için, **VM implementasyonundaki bir hata, üstteki dilin tüm güvenlik garantilerini geçersiz kılabilir.**

Bu, konunun neden derin bir güvenlik alanı olduğunun kök nedenidir: sandbox, güvenlik sınırını uygulama mantığından runtime'a taşır, ama runtime'ın kendisi mükemmel değildir.

### JIT Kaynaklı Saldırı Yüzeyi: Neden JIT Özellikle Riskli

JIT derleyiciler, klasik AOT derleyicilere göre ekstra bir saldırı yüzeyi açar çünkü:

1. **Çalışma zamanında kod üretirler**: Bellekte "yazılabilir ve çalıştırılabilir" (W^X ilkesinin ihlali riski taşıyan) bölgeler gerekir. Normalde işletim sistemleri bir sayfanın hem yazılabilir hem çalıştırılabilir olmasını (W^X) engellemeye çalışır, ama JIT tam olarak bunu yapmak zorundadır (kod üret, sonra çalıştır). Bu, JIT motorlarının W^X'i "JIT sayfası üret → yaz → salt-okunur ve çalıştırılabilir yap → çalıştır" şeklinde bir yaşam döngüsüyle simüle etmesini gerektirir. Bu döngüde bir hata (örneğin sayfa hâlâ yazılabilirken çalıştırılması, ya da başka bir thread'in o anda yazması) exploit için pencere açar.
2. **Spekülatif optimizasyonlar tip karışıklığına (type confusion) yol açabilir**: Guard mantığında bir mantık hatası varsa (örneğin bir guard'ın kapsamadığı bir edge-case), optimize edilmiş kod "bu hep integer" varsayımıyla üretilmiş olsa da çalışma zamanında farklı bir tip gelebilir; bu tip karışıklığı bellek bozulmasına (memory corruption) dönüşebilir. JavaScript motorlarındaki güvenlik açıklarının önemli bir kısmı tarihsel olarak JIT compiler'daki (V8'in TurboFan'ı, JSC'nin DFG/FTL'i gibi) mantık hatalarından kaynaklanmıştır.
3. **JIT spraying**: Bu, saldırganın kontrol edebildiği veri değerlerini (örneğin JavaScript'teki sabit sayılar) JIT'in makine koduna çevirmesinden yararlanan bir tekniktir. Fikir şu: eğer saldırgan "hangi sabit değerlerin JIT çıktısında hangi makine kodu baytlarına dönüştüğünü" tahmin edebiliyorsa, dikkatlice seçilmiş sabitler içeren çok sayıda ifade yazarak bellekte kendi seçtiği bir bayt dizisini (shellcode'a benzer) çalıştırılabilir sayfalara "püskürtebilir" (spray). Bu teknik, ASLR/DEP gibi savunmaları JIT'in kendisini bir "kod enjeksiyon kanalı" olarak kullanarak dolanmayı hedefler. (Burada spesifik bir araç veya komut vermiyorum — kavram bu, savunma tarafında önemli olan mekanizmayı anlamak.)

### Savunma ve Tespit

Bir mühendis/savunmacı gözüyle bakıldığında öne çıkan savunma katmanları:

- **W^X'in katı uygulanması + Control-Flow Integrity (CFI)**: JIT sayfalarının yaşam döngüsü boyunca aynı anda hem yazılabilir hem çalıştırılabilir olmaması (örn. "double-mapping": aynı fiziksel belleğe iki farklı sanal adresten, biri yazılabilir biri çalıştırılabilir olacak şekilde erişim) modern motorlarda (V8'in bazı yapılandırmaları, JIT-hardening çalışmaları) uygulanan bir tekniktir.
- **Sabit değer rastgeleştirme / sabitlerin JIT çıktısında öngörülemez hale getirilmesi**: JIT spraying'in temel ön koşulu, saldırganın sabitin makine koduna nasıl çevrileceğini tahmin edebilmesidir. Bu tahmini zorlaştıran (constant blinding gibi) teknikler, bu kanalı daraltır.
- **Pointer/tip etiketleme ve doğrulama katmanları**: V8'in "sandbox" projeleri gibi girişimler, heap içindeki pointer'ları harici belleğe doğrudan erişim yerine bir tablo üzerinden dolaylı (indirection) hale getirerek, bir type confusion bulunsa bile bunun keyfi bellek okuma/yazmaya dönüşmesini zorlaştırmayı hedefler.
- **Fuzzing + differential testing**: JIT derleyicileri, farklı optimizasyon seviyelerinde (yorumlayıcı vs Tier 1 vs Tier 2) aynı sonucu üretip üretmediğini karşılaştıran (differential fuzzing) araçlarla sürekli test edilir; bir "optimize edilmiş kod, yorumlanan koddan farklı sonuç verdi" bulgusu genelde ciddi bir güvenlik hatasının işaretidir.
- **Deoptimization yollarının doğruluğunun test edilmesi**: Guard'ların gerçekten kapsaması gereken her durumu kapsadığından emin olmak (özellikle nadir/exotic JavaScript semantiklerinde — proxy'ler, getter/setter'lar, `Object.defineProperty` gibi dinamik obje değişiklikleri) JIT güvenliğinin en kırılgan noktasıdır; birçok gerçek dünya açığı, "guard'ın unuttuğu bir edge case" şeklindedir.
- **Süreç düzeyinde izolasyon (site isolation, process sandboxing)**: VM içi bir açık bulunsa bile, tarayıcı süreç mimarisinin (her sekme/origin ayrı süreçte) bu açığı sistem genelinde bir ihlale dönüştürmesini engellemesi, savunmayı katmanlı hale getirir (defense in depth) — VM'in kendisi kırılsa bile hasar sınırlanır.

Kök neden mantığı burada da tekrar eder: **VM ne kadar çok "akıllı" (JIT, spekülasyon, dinamik optimizasyon) davranırsa, doğruluğu kanıtlanması gereken kod yüzeyi o kadar büyür.** Performans ile denetlenebilirlik/güvenlik arasında burada da bir ödünleşim vardır; modern motorlar bunu katmanlı savunma (sandboxing + pointer indirection + fuzzing + CFI) ile dengeler.

## Yaygın Hatalar ve Tuzaklar

- **"JIT her zaman daha hızlıdır" varsayımı**: Kısa ömürlü script'lerde (ör. CLI aracı, tek seferlik çalışan kod) JIT'in derleme maliyeti, kazanacağı süreyi aşabilir; bu yüzden bazı runtime'lar kısa çalışan işlemler için hep yorumlayıcıda kalmayı tercih eder ya da düşük eşiklerle çalışır.
- **Megamorphic call site'ları görmezden gelmek**: Bir fonksiyonu kasıtsızca çok farklı tiplerle çağırmak (örneğin bir yardımcı fonksiyonu hem sayılarla hem objelerle kullanmak) IC'yi monomorphic'ten megamorphic'e düşürür, bu da JIT'in üretebileceği en optimize kodun asla üretilememesi anlamına gelir — performans profillemesinde sık görülen, fark edilmesi zor bir yavaşlama nedenidir.
- **Deopt döngülerini fark etmemek**: Bir fonksiyon sürekli optimize edilip sonra deoptimize ediliyorsa (örneğin tip her seferinde değişiyorsa), bu sürekli optimize-et/geri-al döngüsü saf yorumlamadan daha yavaş olabilir; profilleyicilerin "deopt count" gibi metrikleri bu yüzden önemlidir.
- **Bytecode'un "güvenli" olduğunu düşünmek**: Bytecode verifier (JVM'de olduğu gibi) tip güvenliğini büyük ölçüde sağlasa da, JIT'in kendisi (özellikle spekülatif optimizasyon mantığı) ayrı bir güven sınırıdır; verifier'ın onayladığı bytecode'dan üretilen JIT kodu, JIT'teki bir hata yüzünden yine de güvensiz olabilir.
- **JIT'i "kara kutu" olarak görüp performans sorunlarını profillemeden tahmin etmek**: Gerçek üretim sistemlerinde, bir yavaşlamanın kaynağı sıkça "bu fonksiyon hiç JIT edilmemiş" ya da "sürekli deopt oluyor" gibi runtime içi durumlardır; VM'lerin sağladığı tracing/log bayrakları (ör. JIT compilation log'ları) olmadan bu görünmez kalır.

## Sonuç

Bytecode yorumlayıcılar, "taşınabilirlik + hızlı başlangıç" ihtiyacından doğar; dispatch tekniği (threaded vs switch) ve bytecode modeli (stack vs register) performans/basitlik ödünleşimini belirler. JIT derleme, "kodun küçük bir kısmı zamanın çoğunu tüketir" gözlemine dayanan katmanlı bir stratejidir; inline caching ve spekülatif optimizasyon, dinamik dillerde statik dillerin performansına yaklaşmanın yoludur, ama her spekülasyon bir guard ve bir deoptimization yolu gerektirir. Güvenlik tarafında ise JIT'in çalışma zamanında kod üretmesi, sandbox modelinin en kırılgan noktasıdır: W^X ihlali riski, tip karışıklığı ve JIT spraying gibi teknikler buradan doğar. Savunma, tek bir önlemle değil; katmanlı bir yaklaşımla (memory isolation, pointer indirection, fuzzing, süreç izolasyonu) kurulur. Bu üç eksenin (yorumlayıcı tasarımı, JIT stratejisi, güvenlik sınırları) birbirine bağlı olduğunu görmek — performans kazandıran her mekanizmanın aynı zamanda yeni bir güvenlik sorumluluğu getirdiğini fark etmek — bu alanda derinleşen bir mühendisin en önemli kazanımıdır.
