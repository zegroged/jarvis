# WebAssembly (WASM): Çalışma Modeli, Güvenlik Sandbox'ı ve Saldırı Yüzeyi

## Giriş: Neden Bu Konu Kritik

WebAssembly (WASM), tarayıcıda ve giderek daha fazla sunucu tarafında native'e yakın hızda kod çalıştırmak için tasarlanmış, taşınabilir bir bytecode formatı ve çalışma zamanı modelidir. C, C++, Rust, Go gibi dillerden derlenip tarayıcıda veya bağımsız bir runtime (Wasmtime, Wasmer, WasmEdge gibi) içinde çalıştırılabilir. Popülerleşmesinin temel nedeni şudur: JavaScript motorlarının JIT (just-in-time) derleme maliyetini ve dinamik tip belirsizliğini atlayarak, önceden derlenmiş, tip açısından statik olarak doğrulanmış bir bytecode ile öngörülebilir performans sunar.

Bu konunun bir güvenlik/eğitim korpusunda kritik olmasının nedeni açık: WASM, "sandbox içinde native hız" vaadiyle geliyor ve bu vaat büyük ölçüde doğru olsa da, sandbox'ın sınırları, bellek modelinin varsayımları ve WASM'i konak (host) ortamla birleştiren arayüzler (WASI, JS-glue kodu, host fonksiyonları) yeni ve genellikle yanlış anlaşılan bir tehdit yüzeyi yaratıyor. Mühendisler sıklıkla "WASM sandbox'lıdır, o yüzden güvenlidir" gibi basitleştirilmiş bir zihinsel modelle çalışıyor; bu makalenin amacı bu modeli kırıp, savunma amaçlı doğru bir zihinsel model kurmaktır.

## WASM Nedir, Çalışma Modeli Nasıl İşler

WASM iki temel bileşenden oluşur: **modül** (module) — derlenmiş, doğrulanmış bytecode; ve **instance** — bu modülün çalışma zamanındaki somutlaşmış hali (kendi belleği, tabloları ve durumuyla). Bir WASM modülü şunları içerir:

- **Lineer bellek (linear memory)**: Tek, bitişik, byte-adreslenebilir bir bayt dizisi (`ArrayBuffer` benzeri). WASM programının "RAM"i budur.
- **Tablo (table)**: Fonksiyon referanslarını (indirect call hedeflerini) tutan, tip etiketli bir dizi. Fonksiyon işaretçileri doğrudan bellek adresi değil, bu tablodaki indekslerdir.
- **Global değişkenler**: Modül dışına açık olabilen tipli sabit/değişken değerler.
- **Import/export arayüzü**: Modülün host'tan (JS, WASI, başka bir runtime) çağırabileceği fonksiyonlar ve host'a sunduğu fonksiyonlar.

Çalışma modelinin kök nedeni **statik doğrulama (validation)** üzerine kuruludur: bir modül çalıştırılmadan önce, her talimatın tip açısından tutarlı olduğu, yığın (stack) taşmalarının/eksikliklerinin olmadığı, kontrol akışının (branch hedefleri) yapılandırılmış blok sınırları içinde kaldığı tek geçişte doğrulanır. Bu, WASM'in x86/ARM native koddan temel farkıdır: native kodda "goto herhangi bir yere" mümkünken, WASM'de kontrol akışı yapılandırılmış (structured control flow) olmak zorundadır — `block`, `loop`, `if` gibi iç içe geçmiş yapılar dışına rastgele atlama yoktur. Bu kısıtlama, kod-enjeksiyonu tabanlı klasik saldırıların (return-oriented programming/ROP zincirleri gibi) WASM bytecode seviyesinde anlamsız olmasını sağlar; çünkü çalıştırılabilir talimat akışı doğrulama tarafından önceden sabitlenmiştir ve rastgele bir bellek konumuna atlayıp onu "kod" olarak yorumlatmak mümkün değildir.

### Sandbox'ın gerçek sınırı: lineer bellek izolasyonu

WASM'in sandbox garantisinin özü şudur: bir WASM instance'ı yalnızca **kendi lineer belleğine** erişebilir; host'un belleğine, diğer instance'ların belleğine veya işletim sistemi kaynaklarına doğrudan erişemez. Bellek erişimleri (`i32.load`, `i32.store` vb.) her zaman bu lineer belleğin sınırları içinde **runtime bound-check** ile denetlenir — modül dışı bir adrese erişim denemesi native bir segfault değil, WASM seviyesinde bir trap (kontrollü hata) üretir.

Bunun kök nedeni önemli: WASM belleği native pointer'lardan farklı olarak **taban adresten göreli bir ofsettir** (32-bit modda genelde 0 ile 4GB arası bir tamsayı ofset). Yani bir WASM programı içindeki "bellek bozulması" (örneğin C'den derlenmiş kodda klasik bir buffer overflow) gerçekleşse bile, bu bozulma **kendi lineer belleği içinde** kalır — dışarıya, host process belleğine sızmaz. Bu, C/C++'ın native derlenmiş halinde bir stack overflow'un doğrudan komşu bellek sayfalarını (return address, diğer stack frame'ler, hatta kod segmentini) bozabilmesiyle taban tabana zıttır.

Bu, WASM'in gerçekten sunduğu şeyin ne olduğunu netleştirir: **bellek güvenliği (memory safety) değil, bellek izolasyonu (memory isolation)** sağlar. WASM içindeki C kodu hâlâ buffer overflow yazabilir, hâlâ use-after-free yaşayabilir, hâlâ tip karışıklığı (type confusion) içerebilir — ama bunların etkisi *o modülün kendi lineer belleği* ile sınırlıdır. Bu ayrım, tehdit modellemesinde kritik: "WASM'e derledim, artık güvenliyim" varsayımı yanlıştır; sadece "bu güvensizlik host'a sıçramaz" varsayımı (doğru sandbox implementasyonu koşuluyla) geçerlidir.

## Sandbox Kaçışları: Gerçek Saldırı Yüzeyi Nerede

WASM sandbox'ının kendisi (doğrulayıcı + bounds-checked lineer bellek modeli) matematiksel olarak sağlam bir tasarımdır, ama gerçek dünyadaki kaçışlar neredeyse hiçbir zaman "WASM spesifikasyonunda mantık hatası" değildir. Saldırı yüzeyi tipik olarak şu katmanlarda yoğunlaşır:

### 1. Runtime implementasyon hataları (motor bugları)

Spesifikasyon doğru olsa da, onu uygulayan motor (V8, SpiderMonkey, JavaScriptCore, Wasmtime, Wasmer) C++/Rust ile yazılmış karmaşık yazılımdır ve kendi bug'larına sahiptir. Kök neden: bounds-check optimizasyonları. Motorlar performans için sınır kontrollerini bazen "kanıtlanmış güvenli" durumlarda atlar (örneğin JIT'in bir döngüde erişimin sınırlar içinde kalacağını statik olarak ispatladığı durumlarda). Bu optimizasyon mantığındaki bir hata, gerçek bir out-of-bounds erişime, yani sandbox kaçışına dönüşebilir. Tarihsel olarak V8'in WASM JIT katmanında (Liftoff/TurboFan benzeri katmanlarda) bu tür sınır-kontrolü eleme hataları güvenlik açıklarının kaynağı olmuştur — spesifik CVE numaralarını burada uydurmuyorum, ama kalıp olarak "JIT optimizasyonu bounds-check'i yanlış eledi" tekrar eden bir tema.

Savunma açısından çıkarım: WASM motorunu güncel tutmak, tarayıcı/runtime güncellemelerini geciktirmemek, bu saldırı sınıfına karşı en etkili tedbirdir çünkü savunmacı olarak motorun iç JIT mantığını denetleyemezsiniz — üretici yamalarına bağımlısınız.

### 2. Host-guest arayüzü: "glue code" güvensizliği

Bu, pratikte en sık istismar edilen katmandır ve WASM'in kendisiyle ilgili değildir. Bir WASM modülü tek başına hiçbir şey yapamaz — dosya okuyamaz, ağa bağlanamaz, ekrana yazamaz. Bunların hepsi **import edilen host fonksiyonları** aracılığıyla olur (JS tarafında `WebAssembly.instantiate` ile geçirilen import objesi, ya da WASI'de host tarafından sağlanan sistem çağrıları).

Kök neden/mantık: sandbox modeli "WASM kod host'a zarar veremez" der, ama bunu host'un *kendisinin* sağladığı fonksiyonlar aracılığıyla dolaylı olarak yapabilir. Örnek zihinsel model: WASM modülü bir dosya yolu string'ini host'a bir bellek ofseti+uzunluk çifti olarak geçirir; host bu ofseti kendi (native) belleğinden okuyup path'i çözümler. Eğer host tarafı bu ofset/uzunluk değerlerini WASM'in bildirdiği lineer bellek sınırlarına göre doğrulamazsa (ör. `offset + length` toplamı integer overflow yaparsa ya da host, WASM belleğinin dışına taşan bir okuma yapılmasına izin verirse), WASM kodu host'un kendi adres alanından veri okuyabilir/yazabilir hale gelir. Bu bir "WASM açığı" değil, **host-guest arayüz sınır denetimi hatasıdır** — ama pratikte gerçek saldırıların büyük kısmı burada yaşanır.

Bu yüzden savunma amaçlı en önemli ilke: **her host fonksiyonu, WASM'den gelen her pointer/length çiftini kendi lineer bellek sınırları içinde yeniden doğrulamalıdır.** WASM'in "ben zaten sandbox'lıyım" güvencesine host tarafı asla güvenmemelidir; host, guest'ten gelen her veriyi güvenilmez (untrusted) input olarak ele almalıdır — tıpkı bir web sunucusunun kullanıcı input'una güvenmemesi gibi.

### 3. WASI ve capability modelinin yanlış yapılandırılması

WASI (WebAssembly System Interface), WASM'e dosya sistemi, saat, rastgele sayı gibi sistem kaynaklarına erişim sağlayan standardize arayüzdür. WASI'nin güvenlik modeli **capability-based**dir: bir WASM instance'ı varsayılan olarak hiçbir dosyaya erişemez; host, instance'a açıkça hangi dizinlerin (preopened directories) hangi haklarla (okuma/yazma) verildiğini belirtir.

Kök neden/tuzak: bu model doğru tasarlanmıştır ama yapılandırma hatasına çok açıktır. Bir geliştirici "kolaylık olsun" diye kök dizini (`/`) tam yazma hakkıyla preopen ederse, capability modeli teorik olarak var olsa da pratikte hiçbir izolasyon sağlamamış olur — WASI'nin "en az ayrıcalık" felsefesi, onu kullanan mühendisin disiplinine bağımlıdır. Bu, chroot/jail mekanizmalarında görülen klasik "yanlış yapılandırılmış sandbox" hatasının WASI'deki yansımasıdır. Ayrıca WASI'nin sembolik bağlantı (symlink) çözümlemesi, path traversal (`../../` kalıpları) gibi klasik dosya sistemi saldırılarına karşı da dikkatli implementasyon gerektirir; WASI runtime'ının bu path normalizasyonunu doğru yapmaması, preopen edilen dizin dışına çıkışa (sandbox escape) yol açabilir.

### 4. Side-channel ve Spectre-sınıfı saldırılar

WASM, aynı JavaScript gibi, paylaşılan bir CPU üzerinde spekülatif çalıştırma (speculative execution) donanımının üzerinde koşar. Kök neden: WASM'in kendi bellek modeli (bounds-checked lineer bellek) *mantıksal* izolasyon sağlar, ama CPU'nun spekülatif yürütme sırasında bounds-check sonucunu beklemeden ileriye giden okumaları (Spectre variant 1 tarzı) yapması, bu mantıksal izolasyonu **mikroarkitektürel düzeyde** delebilir. Yani teorik olarak, dikkatlice hazırlanmış bir WASM kodu, bounds-check'in "yasaklayacağı" bir belleği spekülatif olarak okutup, bu okumanın yan etkisini (cache timing farkı gibi) bir side-channel üzerinden dışarı sızdırabilir.

Bu nedenle tarayıcı üreticileri WASM'i de kapsayan azaltmalar uyguladı: **site isolation** (her origin'i ayrı process'te çalıştırmak, böylece sızdırılabilecek "ilginç" veri aynı process'te bulunmaz) ve **düşük çözünürlüklü zamanlayıcılar** (`performance.now()` hassasiyetinin kısıtlanması, timing saldırılarını zorlaştırmak için). Savunma açısından çıkarım: side-channel'lara karşı WASM seviyesinde bir "düzeltme" yoktur; bu bir donanım/mikroarkitektür sorunudur ve azaltma katman katman (process izolasyonu, timer hassasiyeti azaltma, spekülatif yürütme bariyerleri) yapılır.

## Bellek Güvenliği Yanılgısı: "WASM = Memory Safe" Değildir

Bu, eğitim korpusu için en önemli kavramsal düzeltmelerden biri. Sıkça karışan iki kavram:

- **Bellek izolasyonu (memory isolation)**: WASM instance'ı host belleğine ya da diğer instance'lara erişemez. **Bunu WASM gerçekten sağlar.**
- **Bellek güvenliği (memory safety)**: Program kendi belleği içinde de buffer overflow, use-after-free, dangling pointer gibi hatalar yapmaz. **Bunu WASM sağlamaz** — bu, kaynak dilin (C/C++ vs Rust) ve derleyicinin sorumluluğundadır.

C/C++'tan WASM'e derlenen bir kod, kaynak dildeki tüm bellek güvenliği açıklarını miras alır; sadece bu açıkların *blast radius*'u (etki alanı) kendi lineer belleğiyle sınırlanır. Örnek: WASM içinde çalışan bir C kütüphanesinde klasik bir heap buffer overflow, o modülün kendi lineer belleğindeki komşu verileri (örneğin başka bir nesnenin alanlarını, fonksiyon tablosundaki bir işaretçiyi değil ama veri yapılarını) bozabilir ve bu, modülün kendi mantığını (örn. bir yetkilendirme bayrağını) çalıştırma zamanında değiştirebilir — host'a sızmadan bile ciddi bir mantıksal güvenlik açığına yol açabilir (örneğin bir sanal makine/eklenti motorunun kendi iç durumunun bozulması).

Rust gibi bellek güvenli dillerden derlenen WASM, bu sınıf hatalara karşı derleme zamanında zaten korumalıdır; bu nedenle "WASM + Rust" kombinasyonu "WASM + C" kombinasyonundan belirgin şekilde daha güçlü bir güvenlik duruşu sunar — WASM'in kendisi değil, kaynak dilin garantileri bu farkı yaratır.

## Fonksiyon Tablosu ve Control-Flow Integrity

WASM'de fonksiyon işaretçileri doğrudan bellek adresleri değil, tablo indeksleridir (`call_indirect` talimatı). Kök neden/güvenlik faydası: bu tasarım, native kodda görülen klasik "fonksiyon işaretçisi üzerine yazıp rastgele koda atlama" saldırısını zorlaştırır, çünkü:

1. Tablo, WASM'in lineer belleğinden **ayrı** bir alandır — normal bellek yazma talimatlarıyla (`i32.store`) tabloya doğrudan yazılamaz, sadece özel tablo talimatlarıyla (WASM motoru tarafından kontrollü şekilde) değiştirilebilir.
2. Her `call_indirect` çağrısında, hedef fonksiyonun **tip imzası** (parametre/dönüş tipleri) çalışma zamanında doğrulanır; tabloda o indekste beklenen tipte bir fonksiyon yoksa trap oluşur.

Bu, native kodun ROP/JOP (jump/return-oriented programming) saldırılarına karşı sahip olmadığı, yapısal bir CFI (control-flow integrity) biçimidir. Ancak tuzak şu: bu koruma yalnızca WASM'in *kendi* çağrı disiplinine uygulanır; host tarafından WASM'e geçirilen bir fonksiyon referansı (örneğin bir callback), host tarafında yanlış doğrulanırsa yine tip karışıklığına yol açabilir.

## En İyi Pratikler (Savunma Perspektifi)

**Host-guest sınırında sıfır güven ilkesi.** Her host fonksiyonunun, WASM'den gelen tüm pointer/length parametrelerini kendi bilinen lineer bellek sınırlarına göre yeniden doğrulaması gerekir. Bu doğrulamayı "WASM zaten sandbox'lı" varsayımıyla atlamak, en yaygın gerçek dünya açığının kök nedenidir.

**WASI capability'lerini en az ayrıcalıkla yapılandırmak.** Preopen edilen dizinleri, verilen hakları (salt-okunur mü, yazma var mı) mümkün olan en dar kapsamda tutmak; "kolaylık için geniş izin" antipatern'inden kaçınmak.

**Runtime/motor güncellemelerini geciktirmemek.** JIT bounds-check optimizasyon hataları gibi motor seviyesi açıklar yalnızca üretici yamalarıyla kapanır; savunmacı olarak asıl kontrol edilebilir değişken budur.

**Kaynak dil seçimi bir güvenlik kararıdır.** Güvenlik kritik WASM modülleri için, mümkünse bellek güvenli bir kaynak dil (Rust gibi) tercih etmek, WASM'in sağladığı izolasyonun üzerine gerçek bellek güvenliği eklemenin en pratik yoludur.

**Kaynak sınırlaması (resource limiting) uygulamak.** WASM instance'larına bellek büyüme üst sınırı, çalışma süresi/fuel (adım sayısı) limiti, stack derinliği sınırı koymak; bu, hem hizmet reddi (DoS, sonsuz döngü veya bellek tüketimi) senaryolarına karşı hem de bir istismarın etkisini sınırlamak için gereklidir. Çoğu üretim WASM runtime'ı (Wasmtime, Wasmer) bu tür limitleri yapılandırma seçeneği sunar; bunları varsayılan (sınırsız) bırakmak yaygın bir yapılandırma hatasıdır.

**Multi-tenant senaryolarda ek izolasyon katmanları.** Eğer aynı process içinde birden fazla güvenilmeyen WASM modülü çalıştırılıyorsa (örneğin bir edge compute platformu), yalnızca WASM'in mantıksal izolasyonuna güvenmemek; process seviyesi izolasyon, container/VM tabanlı ek katmanlar (özellikle çok kiracılı/multi-tenant bulut ortamlarında side-channel risklerine karşı) değerlendirilmelidir.

## Yaygın Hatalar (Anti-Patterns)

- **"WASM sandbox'lı, o yüzden input doğrulamaya gerek yok" varsayımı.** Sandbox host'u korur, WASM modülünün kendi mantıksal güvenliğini (örn. bir parser'ın kötü niyetli girdiye karşı dayanıklılığını) korumaz.
- **Host fonksiyonlarında pointer/length doğrulamasını atlamak.** "WASM zaten kendi sınırları içinde kalır" diye host tarafında ayrıca sınır kontrolü yapmamak, en kritik hata sınıfıdır.
- **WASI dizin izinlerini gereğinden geniş vermek.** Kök dizine tam erişim vermek, capability modelinin tüm faydasını sıfırlar.
- **Runtime güncellemelerini ihmal etmek.** Eski bir WASM motoru kullanmak, bilinen JIT/bounds-check açıklarına karşı korumasız kalmak demektir.
- **Yalnızca "memory-safe dilden derledim" diye host güvenliğini garanti sanmak.** Rust'tan derlenen WASM bile, `unsafe` bloklar, host'a yanlış geçirilen veri, ya da WASI yanlış yapılandırması yoluyla güvenlik açığı taşıyabilir — dil güvenliği yalnızca bir katmandır, tüm tehdit modelini kapatmaz.
- **Fuel/zaman/bellek limiti koymadan güvenilmeyen kod çalıştırmak.** Bu, hizmet reddi saldırılarına açık kapı bırakır.

## Sonuç: Doğru Zihinsel Model

WASM'i değerlendirirken doğru soru "WASM güvenli mi?" değil, "WASM *neyi* izole ediyor, *neyi* izole etmiyor?" olmalıdır. WASM güçlü bir **izolasyon sınırı** sunar (lineer bellek + yapılandırılmış kontrol akışı + tip doğrulama sayesinde host ve diğer instance'lara sızmayı zorlaştırır), ama bu sınır üç yerde delinebilir: (1) runtime'ın kendi implementasyon hataları, (2) host-guest arayüzünün yanlış doğrulanması, (3) donanım seviyesi side-channel'lar. Savunma amaçlı mühendislik, bu üç katmanın her birini ayrı ayrı ele almayı gerektirir — WASM'in "sandbox" etiketine güvenip bu katmanları atlamak, profesyonel bir güvenlik değerlendirmesinde kabul edilemez bir basitleştirmedir.
