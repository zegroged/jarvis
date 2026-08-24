# Modern Frontend State Yönetimi ve Reaktivite (React/Vue/Signals, Hydration, Sunucu Bileşenleri)

## Giriş: Neden Bu Konu Ayrı Bir Başlık Hak Ediyor

"Frontend Mimari" ya da "Web Performansı" gibi şemsiye başlıklar altında bu konu genelde yüzeysel geçilir; oysa 2022-2024 arası frontend dünyasının en köklü kırılması tam olarak burada yaşandı: **render'ın nerede olduğu** (client mi, server mı, ikisi birden mi) ve **reaktivitenin nasıl hesaplandığı** (virtual DOM diffing mi, fine-grained signals mı) sorularının cevabı değişti. Bu değişim sadece performans meselesi değil; yeni bir hata sınıfı (hydration mismatch), yeni bir güvenlik yüzeyi (sunucu state'inin client'a sızması) ve yeni bir zihinsel model (React Server Components'ta "bu kod nerede çalışıyor?" sorusu) getirdi. Bir mühendisin bu katmanı savunma ve teşhis edebilmesi için mekanizmayı gerçekten anlaması gerekiyor — sadece "kullanmayı" değil.

Bu makale üç ekseni birlikte ele alıyor: (1) reaktivite modelleri nasıl çalışır (React'in yeniden-render'ı vs. signal tabanlı fine-grained reaktivite), (2) hydration nedir, neden kırılır, nasıl teşhis edilir, (3) sunucu bileşenleri (RSC) mimarisinin getirdiği yeni state sınırları ve güvenlik riskleri.

## 1. Reaktivite Modelleri: İki Temel Felsefe

### 1.1 Virtual DOM ve "Yeniden Render Et, Sonra Karşılaştır" Modeli (React)

React'in kök mantığı şudur: state değiştiğinde, ilgili component fonksiyonu **baştan sona yeniden çalıştırılır**, yeni bir Virtual DOM (JS nesneleri ağacı) üretilir, bu ağaç bir önceki ağaçla karşılaştırılır (reconciliation/diffing) ve sadece farklılaşan gerçek DOM node'ları güncellenir.

Kök neden — neden bu tasarım seçildi: DOM manipülasyonu pahalıdır (layout, reflow, repaint tetikler); React bu maliyeti "hafızada ucuz nesne karşılaştırması" ile "gerçek DOM'a dokunma" arasına bir tampon koyarak azaltmayı hedefledi. Ayrıca "UI = f(state)" saf fonksiyon modeli, state yönetimini tahmin edilebilir kılar: aynı state her zaman aynı UI'ı üretir, bu da debug edilebilirliği artırır.

Bunun bedeli: component fonksiyonunun **tamamı** yeniden çalışır. Bir input'a her tuş vuruşunda, o input'u içeren component (ve React.memo ile korunmadıysa alt component'leri) yeniden render edilir. Bu yüzden React ekosisteminde `useMemo`, `useCallback`, `React.memo`, ve daha yeni olarak **React Compiler** (otomatik memoization) gibi araçlar var — hepsi aynı köke iniyor: gereksiz yeniden-render'ı önlemek.

Yaygın tuzak: "state closure'ı" (stale closure) hatası. `useEffect` veya event handler içinde bir state değişkenini kullanıp dependency array'e eklemeyi unutmak, eski (stale) değeri closure'da hapsedilmiş halde kullanmaya yol açar. Kök neden: her render yeni bir fonksiyon kapsamı (closure) yaratır; önceki render'ın closure'ı hâlâ "eski" state'e referans tutar ama React o eski closure'ı bir yerlerde (event listener, timer callback) canlı tutuyorsa, kullanıcı güncel olmayan veriyle karşılaşır.

### 1.2 Fine-Grained Reaktivite: Signals (SolidJS, Vue 3, Preact Signals, Angular Signals)

Signal tabanlı modelin felsefesi taban tabana zıt: **component fonksiyonu sadece bir kere çalışır** (setup/kurulum aşamasında); state bir "signal" (gözlemlenebilir kap) içinde tutulur ve bu signal'e bağımlı olan **sadece o spesifik DOM ifadesi veya efekt** güncellenir. Component ağacında "yeniden render" diye bir kavram yoktur — ilk render'dan sonra, güncellemeler doğrudan ilgili DOM node'una noktasal (surgical) olarak uygulanır.

Kök neden / çalışma mantığı: Bu, **bağımlılık izleme (dependency tracking)** ile mümkün olur. Bir signal okunduğunda (`count()` gibi), o okumanın hangi "reaktif kapsam" (effect, computed, veya JSX ifadesi) içinde gerçekleştiği otomatik olarak kaydedilir. Signal değeri değiştiğinde, sadece o kaydı tutan abonelere bildirim gider. Bu, Virtual DOM diffing'e ihtiyaç bırakmaz çünkü hangi DOM node'unun güncelleneceği zaten baştan biliniyor — çalışma zamanında karşılaştırma yapılmıyor, doğrudan bağlantı var.

Vue 3'ün Composition API'si (`ref`, `reactive`) aslında Proxy tabanlı bir signal implementasyonudur: `reactive()` bir nesneyi Proxy ile sarar, property okumaları `track()` ile bağımlılık kaydeder, yazmalar `trigger()` ile bildirim tetikler. Vue şablon derleyicisi (compiler), hangi DOM parçasının hangi reaktif ifadeye bağlı olduğunu derleme zamanında analiz ederek (`compiler-sfc` ile "block tree" optimizasyonu) çalışma zamanı maliyetini daha da düşürür.

**Doğru kullanım ve tuzaklar:** Signal modelinde en yaygın hata, **reaktiviteyi bozan destructuring**'dir. Örneğin Vue'da `const { count } = reactive({ count: 0 })` yazmak, `count`'u ilkel bir sayıya kopyalar ve Proxy bağlantısını koparır — artık reaktif değildir. Doğru kullanım `toRefs()` ile veya doğrudan `ref()` kullanmaktır. SolidJS'te benzer şekilde, bir signal'i JSX dışında erken çağırmak (`const value = count();` sonra `value`'yu JSX'te kullanmak) bağımlılık izlemeyi kırar, çünkü izleme yalnızca reaktif bir kapsam **içinde çalışan** okumalarda işler; kapsam dışına "kaçırılmış" bir değer artık statiktir.

### 1.3 İki Model Arasındaki Ödünleşim

| Boyut | Virtual DOM (React) | Signals (Solid/Vue) |
|---|---|---|
| Güncelleme birimi | Component (yeniden render) | Tekil DOM ifadesi |
| Çalışma zamanı maliyeti | Diffing + reconciliation | Doğrudan güncelleme, diffing yok |
| Zihinsel model | "UI = f(state)", saf fonksiyon | Bağımlılık grafiği, imperatif izleme |
| Yaygın performans tuzağı | Gereksiz re-render zinciri | Reaktivite kaybı (destructuring vb.) |
| Debug edilebilirlik | Render nedenini izlemek zor olabilir (neden bu component tekrar render oldu?) | Bağımlılık grafiği net ama "neden bu efekt hiç tetiklenmedi" tarzı sessiz hatalar olur |

Bu ödünleşimi anlamak, hangi framework'te hangi performans sorununu arayacağınızı belirler: React'te "waterfall re-render" ve gereksiz component ağacı taraması ararsınız; signal tabanlı sistemlerde "kırık bağımlılık zinciri" (bir şey güncellenmiyor çünkü izleme kapsamı dışında okundu) ararsınız.

## 2. Hydration: Sunucu ile İstemcinin Buluşma Noktası

### 2.1 Tanım ve Kök Mekanizma

Server-Side Rendering (SSR) sürecinde sunucu, component ağacını çalıştırıp düz HTML üretir ve tarayıcıya gönderir. Bu HTML statiktir — tıklama, input, hiçbir JS davranışı çalışmaz. **Hydration**, tarayıcıda indirilen JavaScript'in bu statik HTML üzerine "canlanma" sürecidir: framework, mevcut DOM node'larını sıfırdan yaratmak yerine **yeniden kullanır**, üzerlerine event listener'ları takar ve kendi iç sanal ağacını (React'te Fiber ağacı gibi) bu mevcut DOM'la eşleştirir.

Kök neden — bu neden bu kadar kırılgan: Hydration algoritması, sunucunun ürettiği HTML yapısı ile client'ın **ilk render'da üreteceğini varsaydığı** yapının **birebir aynı** olduğunu varsayar. Framework bu eşleşmeyi doğrulamak için (performans nedeniyle) tam bir DOM karşılaştırması yapmaz; sırayla ilerleyip node'ları eşler. Sunucu ve client farklı bir ağaç üretirse, bu "hydration mismatch" hatasıdır.

### 2.2 Hydration Mismatch: Neden Olur, Nasıl Tespit Edilir

**Yaygın kök nedenler:**

1. **Ortam farklılıkları (environment divergence):** Sunucuda `Date.now()`, `Math.random()`, `window` nesnesi (yok), zaman dilimi, locale gibi değerler kullanmak. Sunucu bir HTML üretir (örneğin sunucu saatiyle), client farklı bir zamanda hydrate olurken farklı bir değer hesaplar → metin içeriği uyuşmaz.
2. **Tarayıcıya özgü API'lere erken erişim:** `localStorage`, `window.innerWidth` gibi yalnızca client'ta var olan değerlere dayanan koşullu render, sunucuda "yok" varsayımıyla bir dal, client'ta "var" varsayımıyla başka bir dal render eder.
3. **Geçersiz HTML iç içe yerleşimi:** Tarayıcı, geçersiz HTML'i (örneğin `<p>` içine `<div>`) parse ederken otomatik olarak "düzeltir" (DOM'u farklı şekilde kurar). Sunucunun gönderdiği string ile tarayıcının fiilen kurduğu DOM ağacı bu yüzden ayrışabilir — bu, framework'ün hiçbir kontrolü olmayan bir kaynaktır.
4. **Tarayıcı uzantıları (extensions):** Bazı tarayıcı eklentileri DOM'a hydration'dan önce müdahale edip node ekler/değiştirir (örn. form doldurma eklentileri, reklam engelleyiciler); framework bunu "beklenmedik" bir ağaç olarak görür.
5. **Zaman/veri kayması (race condition):** Sunucu render anındaki veri ile client'ın hydrate anında yeniden fetch ettiği (veya farklı cache'den okuduğu) veri arasında tutarsızlık.

**Tespit:** React geliştirme modunda konsola özel uyarı verir (metin içeriği uyuşmazlığı, attribute uyuşmazlığı). Üretimde bu uyarılar genelde bastırılır veya sessizce "client kazanır" mantığıyla düzeltilir (React, mismatch tespit ettiğinde client tarafındaki hesaplamayı esas alıp DOM'u onunla değiştirir) — bu da kullanıcı arayüzünde bir "flicker" (ilk gösterilen içerik aniden değişmesi) olarak görülür. Vue benzer şekilde geliştirme modunda uyarı loglar. Üretim ortamında bu sorunları **yakalamanın** en güvenilir yolu: gerçek kullanıcı tarayıcılarından hata/uyarı loglarını toplayan bir izleme (RUM/error tracking) kurmak ve SSR çıktısı ile client render'ı arasındaki farkları CI'da (örneğin snapshot testleriyle, sunucu HTML'i ile hydrate sonrası DOM'u karşılaştırarak) otomatik doğrulamak.

**Savunma / en iyi pratik:**
- Zamana, rastgeleliğe veya `window`'a bağlı hesaplamaları render fonksiyonunun dışına çıkarın; bunları yalnızca `useEffect` (client-only, mount sonrası) içinde hesaplayıp state'e yazın. Bu, ilk render'ın hem sunucuda hem client'ta aynı (örneğin placeholder) değeri üretmesini garanti eder; gerçek değer hydration'dan **sonra** bir güncelleme olarak gelir (kontrollü bir "flash" — kontrolsüz mismatch'ten farklı).
- Framework'lerin sağladığı "yalnızca client'ta render et" kaçış kapılarını (React'te dinamik `import()` + `ssr:false` yapılandırması, Next.js'te benzer mekanizmalar) yalnızca gerçekten sunucuda anlamsız olan bileşenler için kullanın (örn. bir canvas kütüphanesi, tarayıcıya özgü bir widget).
- HTML iç içe yerleşim kurallarına uyun (örneğin blok elemanları satır içi elemanların içine koymayın).

### 2.3 Kısmi/Aşamalı Hydration Stratejileri

Büyük sayfalarda tüm JavaScript'i indirip tüm ağacı tek seferde hydrate etmek ("tam hydration") başlangıç gecikmesine (Time to Interactive) zarar verir. Bunun çözümü olarak ortaya çıkan yaklaşımlar:

- **Islands Architecture (Astro, Fresh gibi):** Sayfanın çoğu statik HTML kalır; yalnızca etkileşim gerektiren küçük "adalar" (component'ler) ayrı ayrı hydrate edilir. Kök mantık: her component'in kendi bağımsız JS paketi ve hydration zaman çizelgesi vardır, birbirini bloklamaz.
- **Progressive/Selective Hydration (React 18 Suspense ile):** Ağaç, öncelik sırasına göre parça parça hydrate edilir; kullanıcı bir bölüme etkileşimde bulunursa (örn. tıklarsa), React o bölümün hydration'ını öne alır (concurrent rendering'in getirdiği zamanlama esnekliği sayesinde).

## 3. React Server Components (RSC): State'in Sunucuya Taşınması

### 3.1 Tanım ve SSR'dan Farkı

SSR ile RSC karıştırılır ama farklı kavramlardır. SSR, client component'lerinin **ilk render çıktısını** sunucuda hesaplayıp HTML olarak gönderme tekniğidir — component kodu sonunda client'a da gönderilir ve hydrate edilir. RSC ise bir component kategorisidir: **"Server Component"** olarak işaretlenen (veya varsayılan kabul edilen, `"use client"` direktifiyle işaretlenmemiş) component'ler **hiçbir zaman client'a JavaScript olarak gönderilmez**. Sunucuda çalışır, çıktısını özel bir serileştirilmiş format (RSC payload, JSON'a benzer ama fonksiyon referansları ve Suspense sınırlarını da kodlayan bir akış) olarak client'a yollar; client bu payload'ı kendi ağacına "birleştirir" (mount eder), hydrate etmez çünkü zaten interaktif JS içermez.

Kök neden — bu mimari neden var: (1) Bundle boyutunu küçültmek — veritabanı sorgusu yapan, büyük bir markdown parser kullanan bir component'in kodu ve bağımlılıkları client'a hiç gönderilmez. (2) Sunucu kaynaklarına (veritabanı, dosya sistemi, gizli API anahtarları) doğrudan, ayrı bir API katmanı yazmadan erişim. (3) Veri çekme (data fetching) ile render'ı aynı yerde, network round-trip'i olmadan birleştirmek (client'ta `useEffect` içinde fetch edip loading state yönetmek yerine).

### 3.2 State Sınırı: Server Component ile Client Component Arasındaki Duvar

Kök mantık burada kritik: Server Component'ler **state tutamaz** (`useState`, `useEffect` kullanamaz), çünkü bir kere sunucuda render edilip sonucu gönderilirler — yeniden render edilecekleri bir "yaşam döngüsü" client'ta yoktur. Etkileşim (state, event handler, effect) gerektiren her şey `"use client"` ile işaretlenmiş bir Client Component'e taşınmalıdır.

Bu sınır, props geçişinde de bir kurala yol açar: Server Component'ten Client Component'e geçirilen her prop, **serileştirilebilir** olmalıdır (fonksiyonlar genel olarak geçirilemez — Server Action'lar için özel bir mekanizma dışında; class instance'ları, Symbol'ler, doğrudan geçirilemez). Bu kısıtlama sık karşılaşılan bir hata kaynağıdır: "Functions cannot be passed directly to Client Components" tarzı derleme/çalışma zamanı hataları, geliştiricinin bu sınırı ihlal ettiğinin işaretidir.

### 3.3 Güvenlik Riski: Sunucu State'inin Client'a Sızması

Bu, RSC modelinin en can alıcı ve en az anlaşılan güvenlik yüzeyidir.

**Kök neden:** Bir Server Component, sunucu tarafında veritabanından tam bir kullanıcı nesnesi çeker (örneğin `{ id, email, passwordHash, internalRiskScore, ssn }` gibi alanlar içeren bir obje). Geliştirici bu objeyi **doğrudan** bir Client Component'e prop olarak geçirirse (`<ClientProfile user={user} />`), RSC serileştirme mekanizması bu objenin **tüm alanlarını** client'a giden payload'a gömer — çünkü serileştirici hangi alanın "hassas" olduğunu bilmez, sadece "bu prop client'a gidiyor, serileştir" der. Client component sadece `user.email`'i render etse bile, `passwordHash` ve `ssn` tarayıcının aldığı ham veri içinde (genelde bir `<script>` içine gömülü JSON olarak) bulunur ve tarayıcı geliştirici araçlarından (Network sekmesi, "View Source", veya React DevTools ile) görülebilir.

Bu, klasik bir "over-fetching sunucuda gizli kalıyordu, artık gizli kalmıyor" sorunudur: geleneksel bir REST/GraphQL API modelinde geliştirici zaten "response'a ne koyuyorum" sorusunu API sınırında sorardı; RSC modelinde bu sınır bulanıklaştığı için (çünkü component ağacı sunucudan client'a "doğal" bir şekilde uzanıyor gibi görünüyor) geliştirici bu API tasarımı disiplinini unutabilir ve tüm veritabanı nesnesini prop olarak taşımanın bir "network sınırı" geçtiğinin farkına varamayabilir.

**Tespit:** Üretimde bunu yakalamanın yolu, tarayıcıdan gelen ilk HTML/RSC payload'ını (View Source veya `curl` ile sayfa kaynağını çekerek) manuel veya otomatik taramaktan geçer: yanıt içinde e-posta dışı kimlik bilgisi deseni (hash benzeri uzun hex/base64 string'ler, "secret", "token", "internal" gibi alan adları) arayan bir CI adımı veya statik/dinamik güvenlik taraması eklemek makul bir savunma katmanıdır. Ayrıca kod incelemesinde "bir Server Component'ten Client Component'e geçen her prop'un şemasını (tip tanımını) açıkça daraltıp daraltmadığını" (`{ id, displayName }` gibi minimal bir DTO mu yoksa ham entity mi) kontrol etmek, bu sınıf hatanın en pratik yakalama noktasıdır.

**Savunma / en iyi pratik:**
1. **Veri erişim katmanında daraltma (data access layer projection):** Veritabanı sorgusunun kendisi zaten yalnızca ihtiyaç duyulan alanları seçmeli (`SELECT id, display_name` gibi, `SELECT *` değil). Bu, "sızacak veri sunucu belleğinde bile en baştan yok" ilkesidir — savunmanın en güçlü katmanı, çünkü bir sonraki adımda geliştirici hata yapsa bile sızacak alan zaten mevcut değildir.
2. **Explicit prop mapping:** Server Component, Client Component'e ham entity yerine bilinçli şekilde inşa edilmiş küçük bir obje geçirmeli: `<ClientProfile name={user.displayName} avatarUrl={user.avatarUrl} />`. Ham `user` objesini asla doğrudan yaymayın (spread etmeyin).
3. **"use server" ve Server Action sınırlarını da aynı disiplinle ele almak:** Server Action'lardan client'a dönen sonuçlar için de aynı minimal-veri ilkesi geçerlidir; bir action'ın hata mesajında iç sistem detaylarını (stack trace, SQL hatası) doğrudan client'a döndürmek benzer bir bilgi sızıntısı sınıfıdır.
4. **Ortam değişkenlerinde ayrım:** Bazı framework'ler (Next.js gibi) `NEXT_PUBLIC_` benzeri bir önek olmadıkça ortam değişkenlerini client bundle'ına dahil etmez; ama bu korumanın yalnızca **build-time** statik erişim (`process.env.X`) için işlediğini, çalışma zamanında bir Server Component içinde okunup bir client prop'una konan bir gizli değerin bu korumadan **faydalanamayacağını** bilmek önemlidir — çünkü sızıntı build-time bundling değil, çalışma zamanı serileştirme yoluyla oluyor.

### 3.4 Suspense, Streaming ve State Tutarlılığı

RSC modeli genelde React Suspense ile birlikte "streaming SSR" yapar: sayfanın hazır olan kısmı hemen gönderilir, yavaş bir veri kaynağına bağlı kısım (`<Suspense fallback={...}>` ile sarılmış) hazır olduğunda ayrı bir parça (chunk) olarak akışa eklenir. Kök mekanizma: HTTP yanıtı chunked transfer encoding ile açık tutulur, sunucu her Suspense sınırının verisi hazır olduğunda o parçanın HTML'ini ve onu doğru yere yerleştirecek küçük bir inline script'i akışa yazar.

Buradaki state tutarlılığı tuzağı: streaming sırasında farklı Suspense sınırları farklı zamanlarda, potansiyelen farklı bir "anlık görüntü" (snapshot) veriyle çözülürse, kullanıcı sayfada birbiriyle tutarsız iki veri parçası görebilir (örneğin üstte "5 bildirim" yazan bir sayaç, altta akışla gelen listede 4 öğe göstermesi — çünkü aralarında bir yazma işlemi gerçekleşti). Savunma: mümkün olduğunca tek bir tutarlı veri okuma anına (bir transaction snapshot'ı veya tek bir request-scoped cache) dayanmak, farklı Suspense sınırlarının aynı temel veriyi ayrı ayrı sorgulamasını önlemek (React'in `cache()` fonksiyonu veya eşdeğer bir request-level memoization mekanizması bu amaç için var).

## 4. Bütüncül Savunma Kontrol Listesi

Bir sistemi bu açılardan denetlerken sorulacak somut sorular:

- **Reaktivite:** Component'ler gereksiz yere mi yeniden render oluyor (React DevTools Profiler ile ölçün)? Signal tabanlı bir sistemde, destructuring nedeniyle sessizce reaktivitesi kırılan bir state var mı?
- **Hydration:** Render fonksiyonlarında `Date`, `Math.random`, `window`/`document` doğrudan kullanılıyor mu? Geliştirme konsolunda hydration uyarısı bastırılmış mı (üretimde de görünür bir izleme var mı)?
- **RSC state sınırı:** Server Component'lerden Client Component'lere geçen her prop, minimal ve bilinçli şekilde seçilmiş mi, yoksa ham veritabanı/servis nesnesi mi taşınıyor? Sayfa kaynağında (View Source / ilk yükleme network yanıtı) beklenmedik alan adları var mı?
- **Veri erişim katmanı:** Sorgular en baştan yalnızca gereken alanları mı çekiyor, yoksa "SELECT *” sonra filtreleme mi yapılıyor?

## Sonuç

Bu üç konu (reaktivite modeli, hydration, RSC) yüzeyde birbirinden bağımsız görünse de aslında tek bir soruyu farklı açılardan cevaplıyor: **state nerede yaşıyor, ne zaman hesaplanıyor, ve sınırı kim koruyor?** React'in yeniden-render modeli ile signal'lerin fine-grained izlemesi, "ne zaman hesaplanıyor" sorusuna iki farklı cevap verir. Hydration, "sunucu hesabı ile client hesabı aynı mı" sorusunun garantisidir ve bu garanti bozulduğunda kullanıcı arayüzü tutarsızlaşır. RSC ise "hangi state sunucuda kalmalı, hangisi client'a geçmeli" sınırını mimariye gömer — ama bu sınırı geliştiricinin bilinçli şekilde çizmesi gerekir, yoksa framework onu sizin yerinize güvenli çizmez. Modern frontend mühendisliğinin bu katmanda ustalaşması, yeni API'leri ezberlemekten çok, bu üç sorunun kök nedenini kavrayıp her yeni framework/kütüphanede aynı soruları tekrar sormaktan geçiyor.
