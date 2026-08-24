# Performans Profilleme

## Giriş: Neden "Tahmin Etme, Ölç" Bir Mühendislik Disiplinidir

Performans profilleme, bir programın çalışma zamanında kaynakları (CPU zamanı, bellek, I/O, kilit beklemeleri) nasıl harcadığını **ölçerek** ortaya koyan yöntemler bütünüdür. Amaç tek bir cümleyle özetlenebilir: yavaşlığın gerçek kaynağını (darboğazı) bulmak için sezgiye değil veriye dayanmak. Deneyimli mühendislerin en sık tekrarladığı ilke buradan gelir: **"Measure, don't guess"** (ölç, tahmin etme).

Bu ilke boş bir slogan değildir; çünkü insan sezgisi performans konusunda sistematik olarak yanılır. Bir kod parçasına baktığımızda gözümüze en "pahalı" görünen şey (iç içe döngüler, karmaşık matematik) çoğu zaman toplam sürenin küçük bir kısmını harcar; asıl zaman ise beklemediğimiz yerde (bir serialization çağrısında, gereksiz bir bellek kopyasında, bir log satırında, senkron bir DNS çözümlemesinde) kaybolur. Modern donanımda önbellek (cache) davranışı, branch prediction, bellek erişim gecikmeleri gibi katmanlar durumu daha da öngörülemez kılar. Bu yüzden profilleme, kod okumanın veya "burası yavaş olmalı" demenin yerine geçen ampirik bir disiplindir.

Bu makale önce profillemenin temel mantığını ve neden işe yaradığını, sonra profiler türlerini (sampling ve instrumentation), ardından flamegraph okumayı, darboğaz analizini ve premature optimization tuzağını derinlemesine ele alır.

## Temel Kavram: Ölç, Optimize Et, Tekrar Ölç Döngüsü

### Döngünün Mantığı

Profilleme tek seferlik bir işlem değil, kapalı bir geri besleme döngüsüdür:

1. **Ölç (baseline):** Optimizasyona başlamadan önce mevcut durumu ölç. Bu referans (baseline) olmadan yaptığın değişikliğin işe yarayıp yaramadığını bilemezsin.
2. **Analiz et:** Ölçüm verisini incele, en çok zamanı/bellegi harcayan noktayı (hot path) belirle.
3. **Hipotez kur ve optimize et:** Yalnızca darboğaz olduğunu kanıtladığın noktayı değiştir.
4. **Tekrar ölç:** Değişikliğin gerçekten iyileştirme sağlayıp sağlamadığını aynı koşullarda ölçerek doğrula. Çoğu zaman "iyileştirme" hiçbir şeyi değiştirmez veya başka bir yeri kötüleştirir.

Bu döngünün neden bu kadar önemli olduğunu anlamak için düşünelim: kanıt olmadan yapılan bir "optimizasyon" aslında bir varsayımdır. Varsayımın doğruluğunu ancak öncesi/sonrası ölçümüyle test edebilirsin. Ölçüm olmadan optimizasyon, körlemesine ilaç vermeye benzer; belki iyileştirir, belki zarar verir, ama bilemezsin.

### Neden Baseline Kritiktir

Baseline'ın (referans ölçüm) önemi çoğu zaman hafife alınır. İyi bir baseline şu özelliklere sahip olmalıdır:

- **Tekrarlanabilir (reproducible):** Aynı girdi, aynı donanım, aynı yapılandırma. Aksi halde ölçtüğün fark, senin değişikliğinden değil gürültüden (noise) kaynaklanabilir.
- **Temsili (representative):** Gerçek üretim yükünü (production workload) yansıtmalı. 10 kayıtla yaptığın test, 10 milyon kayıtta ortaya çıkan darboğazı göstermez. Karmaşıklık (complexity) sınıfları girdi büyüdükçe değişen etkiler doğurur.
- **İzole:** Ölçüm sırasında sistemde başka ağır işler çalışmamalı; yoksa CPU ve bellek rekabeti sonucu bozar.

Ölçümlerde tek bir sayıya değil dağılıma bakmak gerekir. Ortalama (mean) yanıltıcıdır; kuyruk gecikmeleri (tail latency) için p50, p95, p99 gibi yüzdelik dilimler (percentiles) çok daha bilgilendiricidir. Bir servisin ortalaması iyi görünürken p99'u felaket olabilir ve kullanıcı deneyimini asıl bu uç durumlar belirler.

## Profiler Türleri: Sampling ve Instrumentation

Profillemenin nasıl çalıştığını anlamak, sonuçları doğru yorumlamak için şarttır. İki temel yaklaşım vardır ve her birinin farklı bir maliyet/doğruluk dengesi (trade-off) vardır.

### Sampling (Örnekleme) Profillemesi

Sampling profiler, programı belirli aralıklarla (örneğin saniyede birkaç bin kez) durdurup o an hangi fonksiyonun çalıştığını, yani o anki **call stack**'i (çağrı yığını) kaydeder. Sonunda bu anlık görüntüler (samples) istatistiksel olarak toplanır. Mantık şudur: bir fonksiyon toplam sürenin %40'ında çalışıyorsa, alınan örneklerin de yaklaşık %40'ında o fonksiyon yığında görünecektir.

**Neden bu yöntem güçlüdür:** Programa kod eklemeden, dışarıdan ve düşük ek yükle (low overhead) çalışır. Bu sayede üretim ortamında (production) bile çalışan sistemleri fazla yavaşlatmadan profillemek mümkündür. İşletim sistemi seviyesinde çekirdek (kernel) yardımıyla veya donanım sayaçlarıyla (hardware performance counters) yapıldığında, ölçümün programa etkisi minimuma iner.

**Sınırı:** İstatistikseldir. Çok kısa çalışan ama çok sık çağrılan fonksiyonlar örneklemeye tam yakalanmayabilir; ayrıca çağrı sayısını (kaç kez çağrıldı) doğrudan vermez, yalnızca zaman payını verir. Örnekleme frekansı düşükse nadir ama kritik olaylar kaçabilir.

### Instrumentation (Enstrümantasyon) Profillemesi

Instrumentation profiler ise koda ölçüm noktaları yerleştirir: her fonksiyonun girişine ve çıkışına zaman damgası (timestamp) alan kod enjekte edilir (derleme zamanında veya çalışma zamanında). Böylece her fonksiyonun tam olarak kaç kez çağrıldığı ve ne kadar sürdüğü kesin olarak bilinir.

**Neden değerlidir:** Kesin çağrı sayıları ve tam çağrı grafiği (call graph) verir. "Bu fonksiyon tam 1.245.000 kez çağrılmış" gibi kesin bilgi verebilir; bu, algoritmik bir sorunu (örneğin bir döngü içinde yanlışlıkla yapılan pahalı çağrıyı) yakalamak için paha biçilmezdir.

**Ciddi tuzağı:** Yüksek ek yük (overhead). Her fonksiyon çağrısına ölçüm eklendiği için, özellikle çok sayıda küçük fonksiyon çağıran kodda program birkaç kat yavaşlayabilir. Bu da **probe effect** (gözlemci etkisi) denen çarpıtmayı doğurur: ölçüm eylemi, ölçtüğün şeyi değiştirir. Çok kısa fonksiyonların göreli maliyeti şişer, çünkü ölçümün kendi maliyeti fonksiyonun gerçek maliyetinin yanında büyük kalır. Sonuç: yanıltıcı bir tablo.

### Hangisini Ne Zaman

Genel kural: geniş resmi görmek, "zaman nereye gidiyor" sorusunu cevaplamak ve üretim ortamında ölçüm yapmak için **sampling**; belirli bir bölgenin çağrı sayısını ve tam davranışını mikroskop altında incelemek için **instrumentation** tercih edilir. Olgun ekipler ikisini birlikte kullanır: önce sampling ile darboğaz bölgesini daraltır, sonra o dar bölgeyi instrumentation ile detaylandırır.

Ayrıca yalnızca CPU değil, farklı boyutlar için farklı profiler'lar gerekir: **memory profiler** (bellek ayırma ve kaçaklar/leak), **allocation profiler**, **lock/contention profiler** (kilit beklemeleri), **I/O ve off-CPU profiler** (programın çalışmadığı, beklediği zaman). Bir servis CPU'da hiç yorulmadan yavaş olabilir; çünkü zamanının çoğunu I/O veya kilit beklerken geçiriyordur. Bu durumu klasik CPU profiler göremez; **off-CPU profiling** tam da bunun içindir.

## Flamegraph: Yığın Verisini Görünür Kılmak

### Flamegraph Nedir ve Nasıl Okunur

Flamegraph (alev grafiği), sampling profiler'ın topladığı yüzlerce/binlerce call stack'i tek bir görselde özetleyen bir tekniktir. Görünüşü alev katmanlarına benzediği için bu adı almıştır. Okuma kuralları basittir ama sık yanlış anlaşılır:

- **Yatay eksen (x): zamanı/örnek sayısını temsil eder, akış yönünü DEĞİL.** Bir kutunun genişliği, o fonksiyonun (kendisi ve altındaki çağrılar dahil) örneklerde ne kadar yer kapladığını, yani toplam süredeki payını gösterir. Ne kadar geniş, o kadar çok zaman. **Yataydaki sıralama alfabetik veya keyfîdir; zaman ekseni değildir** — bu en sık yapılan yorumlama hatasıdır.
- **Dikey eksen (y): çağrı derinliği (stack depth).** Alttaki fonksiyon üsttekini çağırmıştır. En alt genellikle giriş noktası (main / event loop), yukarı çıktıkça daha derin çağrılar gelir. (Bazı araçlar ters çizer; buna icicle graph denir, ama mantık aynıdır.)

### Genişliği Doğru Yorumlamak: Self vs Total

Kritik ayrım şudur: bir kutunun genişliği **total** (kendisi + altındaki tüm çağrılar) zamanı gösterir. Asıl işi nerede yaptığını anlamak için **self time**'a (yalnızca o fonksiyonun kendi gövdesinde, alt çağrılar hariç geçen zaman) bakman gerekir. Flamegraph'ta bunu şöyle görürsün: geniş ama **tepe/plato** oluşturan (üstünde başka geniş kutu olmayan) bir bölge, self time'ın yoğunlaştığı yerdir. İşte gerçek darboğaz oradadır. Geniş ama üstünde yine geniş kutular taşıyan bir fonksiyon ise sadece pahalı şeyleri çağıran bir "geçiş noktası"dır; onu optimize etmek genellikle işe yaramaz, çünkü zaman onun içinde değil çağırdıklarının içinde geçiyordur.

Pratik okuma stratejisi: **en geniş düz platolara bak.** Bunlar toplam sürenin en büyük parçasını tek başına harcayan kod bölgeleridir ve optimizasyonun en yüksek getiri sağlayacağı yerler bunlardır.

### Flamegraph Türleri

- **CPU flamegraph:** Standart; CPU üzerinde geçen zamanı gösterir.
- **Off-CPU flamegraph:** Programın beklerken (I/O, kilit, uyku) harcadığı zamanı gösterir. CPU flamegraph'ta boş görünen ama yine de yavaş olan sistemler için hayati.
- **Differential flamegraph:** İki ölçümün (örneğin optimizasyon öncesi/sonrası, veya iki sürüm) farkını renkle vurgular. Bir regresyonun (performansın kötüleşmesi) tam olarak nerede oluştuğunu bulmak için çok güçlüdür.

## Darboğaz Analizi: Zaman Gerçekten Nereye Gidiyor

### Darboğazın Tanımı ve Amdahl Yasası

Darboğaz (bottleneck), toplam performansı sınırlayan tekil (veya birkaç) noktadır. Bir sistemin hızı en yavaş bileşeni kadardır; tıpkı bir zincirin en zayıf halkası gibi. Bu yüzden optimizasyonun matematiği **Amdahl Yasası** ile açıklanır: bir programın yalnızca bir kısmını hızlandırıyorsan, elde edebileceğin toplam hızlanma o kısmın toplam içindeki payıyla sınırlıdır.

Somut örnek: bir işlem toplam sürenin %5'ini alan bir fonksiyonu sonsuz hızlandırsan bile en fazla %5 kazanırsın. Buna karşılık %70'ini alan bir bölgeyi yarıya indirirsen %35 kazanırsın. **Bu yüzden büyük olan darboğaza saldırmak, küçük bir yeri kusursuzlaştırmaktan çok daha değerlidir.** Profillemenin asıl işlevi de tam olarak bu büyük payı bulmaktır. Sezgiyle küçük bir yeri parlatıp saatler harcamak, mühendislik zamanının en yaygın israfıdır.

### Darboğazın Türü Çözümü Belirler

Zamanın nereye gittiğini sınıflandırmak, doğru çözüme yönlendirir:

- **CPU-bound (işlemci sınırlı):** Zaman hesaplamada geçiyor. Çözüm: daha iyi algoritma (karmaşıklık sınıfını düşürmek, örn. O(n²)'den O(n log n)'e), daha az iş, veri yapısı değişikliği, paralelleştirme, vektörleştirme (SIMD), cache-dostu bellek düzeni.
- **Memory-bound (bellek sınırlı):** Zaman bellek erişimini beklemekte geçiyor; işlemci veri gelsin diye boş duruyor (cache miss'ler). Çözüm: veri yerelliğini (locality) artırmak, veri yapılarını sıkıştırmak, gereksiz kopyaları (copy) kaldırmak.
- **I/O-bound:** Zaman disk/ağ/veritabanı beklemekte geçiyor. Çözüm: batching, caching, asenkron (async) I/O, gereksiz round-trip'leri azaltmak. Bu durumda CPU'yu optimize etmek hiçbir işe yaramaz.
- **Lock-bound / contention:** Thread'ler kilit için birbirini bekliyor. Çözüm: kilit granülaritesini düşürmek, lock-free yapılar, kilit tutma süresini kısaltmak.

Bu ayrımın önemi: yanlış türe uygun çözüm boşa emektir. I/O-bound bir sistemi paralelleştirmek genellikle sadece daha fazla thread'in aynı diski beklemesine yol açar.

### N+1 ve Gizli Döngüler

Uygulama profillemesinde en sık yakalanan somut darboğaz kalıbı **N+1 problem**'idir: bir listeyi işlerken her eleman için ayrı bir veritabanı sorgusu veya ağ çağrısı yapmak. Kod okunduğunda masum görünür (bir döngü içinde basit bir çağrı), ama profiler bu çağrının binlerce kez tekrarlandığını ve toplam sürenin çoğunu yediğini anında gösterir. Çözüm çoğunlukla toplu sorgu (batch/eager loading) ile N+1 çağrıyı tek çağrıya indirmektir. Bu, profillemenin kod incelemesinden neden üstün olduğunun tipik örneğidir: çağrı sayısı, statik okumayla görünmez.

## Premature Optimization: Erken Optimizasyon Tuzağı

### İlkenin Doğru Anlamı

Donald Knuth'un çok sık alıntılanan (ve çok sık yanlış anlaşılan) sözü şudur: **"Premature optimization is the root of all evil"** — erken (vaktinden önce yapılan) optimizasyon tüm kötülüklerin köküdür. Buradaki kilit kelime "premature"dır, yani "henüz gerekli olduğu kanıtlanmamış". Söz, "optimizasyon kötüdür" demek DEĞİLDİR; "ölçmeden, gerçek darboğazı bilmeden yapılan optimizasyon zararlıdır" demektir.

Knuth'un aynı bağlamda söylediği ama daha az alıntılanan kısım da önemlidir: küçük verimliliklerin peşinde koşmayı çoğu zaman bırakmalıyız, ama o kritik %3'lük bölgede fırsatı da kaçırmamalıyız. Yani mesele optimizasyonu reddetmek değil, onu **doğru yere, doğru zamanda** yapmaktır. Doğru yer ise ancak profillemeyle bulunur.

### Erken Optimizasyon Neden Zararlıdır

Bu bir üslup meselesi değil, somut maliyetler doğuran bir hatadır:

- **Karmaşıklık maliyeti:** Optimize edilmiş kod neredeyse her zaman daha karmaşık, okunması ve bakımı daha zor olur. Bu karmaşıklığı henüz gerek yokken eklersen, kalıcı bir bakım (maintenance) yükü, daha çok bug ve daha yavaş geliştirme satın almış olursun; karşılığında ise çoğu zaman ölçülebilir hiçbir kazanç almazsın çünkü optimize ettiğin yer darboğaz bile değildi.
- **Yanlış hedef maliyeti:** Ölçmeden yapılan optimizasyonun büyük olasılıkla darboğaz olmayan bir yeri hedeflediğini Amdahl Yasası zaten söylüyor. Emek harcanır, kazanç sıfıra yakındır.
- **Fırsat maliyeti:** Yanlış yerde harcanan zaman, gerçek darboğazı bulup çözmek için kullanılamayan zamandır.
- **Doğruluk riski:** Erken ve gereksiz mikro-optimizasyonlar (elle döngü açma, akıllıca ama okunmaz numaralar) çoğu zaman ince hatalar (subtle bug) ekler ve modern derleyicilerin (compiler) zaten yapacağı işleri elle yaparak işleri kötüleştirir.

### Doğru Denge

Erken optimizasyondan kaçınmak, performansı tamamen görmezden gelmek anlamına gelmez; buna **premature pessimization** (erken kötümserleştirme) denen ters hata düşmek de yanlıştır. Yani "sonra optimize ederiz" diyerek bilinçli olarak açıkça saçma, gereksiz yere pahalı seçimler yapmak (mesela her iterasyonda gereksiz kopya, uygunsuz veri yapısı) da hata olur. Doğru tutum:

1. **Önce doğru, temiz, anlaşılır kod yaz.** Makul algoritmik seçimleri baştan yap (doğru veri yapısı seçmek erken optimizasyon değildir, iyi tasarımdır).
2. **Açıkça israf olan şeyleri baştan yapma** ama mikro-optimizasyona girme.
3. **Performans bir gereksinim (requirement) hâline geldiğinde profille**, darboğazı bul, yalnızca orayı optimize et, tekrar ölç.

## Yaygın Hatalar ve Kaçınma Yolları

**Yanlış ortamda profillemek.** Debug build'de veya optimizasyon kapalıyken (compiler optimizations off) profil almak yanıltıcıdır; derleyici optimizasyonlarıyla profil tamamen değişir. Gerçek performansı ölçmek için üretimdekine benzer bir **release/optimized build** kullan.

**Temsili olmayan yükle ölçmek.** Küçük veya yapay girdilerle ölçüm yapmak, gerçek darboğazları gizler. Ölçek etkileri (cache, bellek baskısı, algoritmik karmaşıklık) ancak gerçekçi boyutta görünür.

**Isınmayı (warm-up) yok saymak.** JIT-derlemeli ortamlarda (JVM, çeşitli VM'ler) veya cache'in dolması gereken sistemlerde ilk çalışmalar yavaştır. Isınma turlarını dahil edip ortalamaya karıştırmak yanıltır; ilk soğuk (cold) ve sonraki sıcak (warm/hot) durumları ayrı değerlendir.

**Ortalamaya takılıp kuyruğu görmezden gelmek.** Yalnızca ortalamaya bakmak p99'daki felaketi gizler. Kullanıcı deneyimini genellikle uç gecikmeler belirler.

**Gözlemci etkisini (probe effect) unutmak.** Ağır instrumentation, özellikle çok küçük fonksiyonların maliyetini şişirir ve yanlış hedef gösterir. Bu yüzden ince taramaya girmeden önce sampling ile genel resmi al.

**Ölçmeden "iyileştirme" yapıp doğrulamamak.** Bir değişikliğin gerçekten iyileştirme sağladığını öncesi/sonrası ölçümüyle kanıtlamamak; belki hiçbir şey değişmemiş, hatta kötüleşmiştir.

**Yanlış boyutu profillemek.** CPU profiler ile I/O-bound bir sistemi incelemeye çalışmak; program CPU'da yorulmuyor ama yine de yavaşsa, off-CPU/I/O profillemesine geçmek gerekir.

**Tek bir ölçüme güvenmek.** Performans ölçümleri gürültülüdür (arka plan işleri, termal durum, frekans ölçekleme). Birden çok kez çalıştır, dağılıma bak, kararlı sonuçlar üret.

## En İyi Pratikler

- **Baseline'ı önce al ve sakla.** Her optimizasyonun değerini, karşılaştıracak bir referans olmadan gösteremezsin.
- **Yukarıdan aşağıya çalış.** Önce geniş sampling ile "zaman nereye gidiyor" sorusunu cevapla, en büyük payı bul (Amdahl), sonra o bölgeye zoom yap. Küçük şeyleri baştan kurcalama.
- **Flamegraph'ı self time için oku.** Geniş platolara odaklan; sadece geniş görünen ama üstünde yine geniş kutular taşıyan "geçiş" fonksiyonlarına aldanma.
- **Darboğazın türünü teşhis et** (CPU / memory / I/O / lock) ve çözümü türe göre seç. Yanlış türe çözüm uygulamak boşa emektir.
- **Üretim-benzeri koşullarda ölç:** optimized build, gerçekçi yük, izole ortam, ısınma sonrası, birden çok tekrar, yüzdelik dilimlerle raporla.
- **Her değişiklikten sonra tekrar ölç.** Döngüyü kapat; kazancı doğrula, regresyon oluşmadığını kontrol et. Mümkünse performans testlerini otomatikleştirip regresyonları CI'da yakala.
- **Önce algoritma, sonra mikro-optimizasyon.** En büyük kazançlar genellikle karmaşıklık sınıfını düşürmekten (daha iyi algoritma/veri yapısı) gelir, tek tek satırları kurcalamaktan değil.
- **Optimizasyonu ölçülebilir bir hedefe bağla.** "Daha hızlı" belirsizdir; "p99 gecikme 200 ms'nin altına" ölçülebilir bir hedeftir. Hedefe ulaştığında dur; sonsuza kadar optimize etmek de bir israf biçimidir.
- **Kararı ve veriyi belgelendir.** Hangi ölçümle, neyi, neden değiştirdiğini kaydet; böylece sonraki mühendis (ve gelecekteki sen) neyin kanıta dayandığını bilir.

## Sonuç

Performans profilleme, özünde bir alçakgönüllülük disiplinidir: sezgimizin yanılabileceğini kabul edip kararı veriye bırakırız. Döngü basittir ama demir gibi katıdır: **ölç, darboğazı bul, sadece orayı optimize et, tekrar ölç.** Sampling profiler'lar bize düşük maliyetle büyük resmi verir, instrumentation gerektiğinde mikroskobu sağlar, flamegraph ise yüzlerce yığın verisini tek bakışta anlaşılır kılar. Amdahl Yasası bize nereye yatırım yapacağımızı söyler; Knuth ise ne zaman yapmayacağımızı hatırlatır. Erken optimizasyondan kaçınmak tembellik değil, mühendislik zamanını gerçekten önemli olan yere yönlendirme bilgeliğidir. Sonuçta iyi bir performans mühendisi, en hızlı kodu yazan değil, **hangi kodun hızlanması gerektiğini kanıtla bilen** kişidir.
