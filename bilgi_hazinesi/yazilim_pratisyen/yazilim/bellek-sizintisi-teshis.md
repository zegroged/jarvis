# Bellek Sızıntısı Teşhisi — Saha Notları

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Bellek sızıntısı, bir programın artık kullanmadığı belleği geri vermemesi ya da veremeyecek durumda tutmasıdır. Ama sahada "sızıntı" dediğimiz şeyin yarısı klasik anlamda sızıntı bile değildir. Gerçek dünyada üç ayrı hastalığı aynı torbaya atarız:

- **Gerçek sızıntı (leak):** Ayrılan bellek artık hiçbir yerden erişilemez ama serbest de bırakılmamıştır (C/C++'ta `malloc` edip `free` etmemek). GC'li dillerde bu klasik anlamda olmaz.
- **Mantıksal sızıntı (drift / retention):** Nesneler hâlâ bir yerden referanslanır, dolayısıyla GC onları toplayamaz, ama program aslında onlara bir daha dokunmayacaktır. Java, C#, Python, JavaScript'te sızıntıların ezici çoğunluğu budur. Statik bir liste, bir cache, bir event listener, bir ThreadLocal... bir yerden tutulur ve bırakılmaz.
- **Fragmentasyon ve gerçek olmayan sızıntı:** Bellek serbest bırakılmıştır ama allocator işletim sistemine geri vermemiştir (glibc malloc arena'ları, jemalloc), ya da RSS şişer ama heap aslında boştur. Buna sızıntı deyip saatlerce yanlış yerde arayan çok mühendis gördüm.

Bu iş ne zaman devreye girer? Tipik tetikleyici: **RSS/working set zamanla monoton artıyor ve trafik sabitken düşmüyor.** Servis her gece 03:00'te OOMKilled oluyor, sonra pod restart olup sayaç sıfırlanıyor. Ya da uzun süren bir batch job saatlerce çalışıp yavaşça şişiyor. Anahtar kelime **monoton artış**: trafikle inip çıkan bellek sızıntı değildir, testere dişi (sawtooth) grafiği sağlıklıdır. Düz bir yükseliş rampası ise alarmdır.

Neden önemli: bellek sızıntısı nadiren "patlayıp" görünür. Genelde haftalarca sinsi ilerler, sonra en kötü zamanda (Black Friday, ay sonu kapanışı) OOM ile servisi düşürür. Ve OOM'un bıraktığı iz genelde suçluyu göstermez — belleği son isteyen ölür, sızdıran değil. Bu yüzden teşhis bir dedektiflik işidir, log okuma işi değil.

## 2. Metodoloji ve karar ağacı — asıl değer burada

Deneyimli birinin kafasındaki akış, panik hâlinde heap dump almak değildir. Sıra şudur:

### Adım 0: Bu gerçekten sızıntı mı? (En çok atlanan adım)

Önce **grafiğe bak, dump alma.** Bir mühendisi acemi yapan ilk şey, RSS'i bir kez yüksek görüp "sızıntı var" demesidir. Sormam gereken sorular:

- Bellek **monoton** mu artıyor, yoksa yükte artıp yükte azalıyor mu? Sawtooth ise büyük ihtimalle normal GC davranışı.
- Bir **plato'ya** oturuyor mu? Çoğu cache, connection pool, JIT kod cache'i başta şişer sonra sabitlenir. 2 saat izleyip plato görürsen sızıntı yok, sadece steady-state büyük.
- Artış **trafikle korele** mi, yoksa **zamanla** mı? Zamanla artıyorsa (istek sayısından bağımsız) daha kötü — bir zamanlayıcı/scheduler ya da arka plan birikimi işaret eder.

Pratik takas: bir servisi yeniden başlatınca "düzeliyor" diye sızıntı olduğuna karar vermek yaygın hatadır. Restart her şeyi düzeltir; bu bilgi vermez. Asıl soru, **sabit yük altında sabit zaman diliminde** belleğin ne yaptığıdır.

### Adım 1: Sınırla — hangi bellek?

Bir sürecin belleği tek bir sayı değil. Ayrımı yapamayan mühendis yanlış yerde arar:

- **Heap içi mi, heap dışı mı?** JVM'de heap dolmuyor ama RSS artıyorsa: direct ByteBuffer, Netty off-heap, JNI, thread stack'leri, Metaspace, ya da glibc arena. Heap dump alıp saatlerce bakarsın, orada yoktur.
- **Native mi, managed mı?** .NET'te `GC.GetTotalMemory` sabit ama işlem belleği artıyorsa: unmanaged handle (dosya, socket, GDI object), P/Invoke, native kütüphane.
- **Uygulama mı, allocator mı?** RSS yüksek ama heap kullanımı düşük → allocator OS'e geri vermiyor olabilir (`MALLOC_ARENA_MAX`, jemalloc `background_thread`).

Karar kuralı: **Önce heap'in tavan yapıp yapmadığına bak.** Heap kullanımı (allocated live set) zamanla artıyorsa managed sızıntı; heap sabit ama RSS artıyorsa native/off-heap tarafına geç. Bu tek ayrım, teşhis süresini 10'a böler.

### Adım 2: İki nokta arası fark al (differential)

Sızıntı avının kalbi budur: **tek bir dump işe yaramaz, iki dumpun farkı işe yarar.** Bir anlık heap görüntüsünde milyonlarca nesne vardır, hepsi normal görünür. Ama:

1. Servisi kararlı hâle getir (warmup bitsin).
2. `t0`'da bir snapshot al (heap histogram / dump).
3. Bilinen bir yükü N kez çalıştır (aynı isteği 10.000 kez).
4. Zorla GC tetikle (managed dillerde), böylece toplanabilecek her şey toplansın.
5. `t1`'de ikinci snapshot al.
6. **Farka bak: hangi nesne türü sayısı, çalıştırdığın yük miktarıyla orantılı arttı?**

10.000 istek attın ve `char[]` sayısı 10.000 arttıysa, suçlu istek başına tutulan bir string'tir. Bu orantı ("grow rate per operation") altın bilgidir. Tek dumptan asla çıkmaz.

### Adım 3: Dominator / retention yolunu bul

Sayının arttığını gördün. Şimdi **neden GC toplayamıyor?** sorusu. Bu, "bu nesneyi hayatta tutan referans zinciri nedir?" sorusudur — profiler dilinde **GC root'a giden path** ya da **dominator tree**.

Pratik zihinsel model: nesne A hayatta çünkü B onu tutuyor, B hayatta çünkü C tutuyor... zinciri bir GC root'ta bitiyor (statik alan, canlı thread stack'i, JNI global ref). Çoğu sızıntıda bu zincirin tepesinde şunlardan biri çıkar:

- **Statik/global bir koleksiyon** (sürekli `add`, hiç `remove`).
- **Bir cache** (unbounded, TTL yok, eviction yok).
- **Event listener / callback / observer** kaydı bırakılmamış.
- **ThreadLocal** (özellikle thread pool ile — thread ölmediği için ThreadLocal hiç temizlenmez).
- **Kapanmamış kaynak** (stream, connection) ve onu tutan finalizer kuyruğu.

### Karar ağacı özeti

```
Bellek zamanla artıyor mu (sabit yük)?
├─ Hayır (sawtooth/plato) → sızıntı değil, kapasite/tuning işi. DUR.
└─ Evet
   ├─ Heap kullanımı (live set) da artıyor mu?
   │   ├─ Evet → MANAGED sızıntı
   │   │        → iki snapshot farkı al
   │   │        → orantılı artan türü bul
   │   │        → GC root path / dominator'a bak
   │   │        → koleksiyon/cache/listener/ThreadLocal'e in
   │   └─ Hayır (heap sabit, RSS artıyor) → NATIVE/OFF-HEAP
   │            ├─ Direct buffer / mmap / JNI → native profiler (jemalloc, ASan)
   │            ├─ Thread sayısı artıyor mu? → thread leak (her stack MB'lar)
   │            ├─ Metaspace/classloader artıyor mu? → classloader leak
   │            └─ Hepsi normal ama RSS yüksek → allocator fragmentasyonu
   └─ Yeniden üretemiyorsan → production'da düşük örnekleme hızıyla
            continuous profiling aç, saatlerce topla, sonra farkı al.
```

## 3. Somut örnek üzerinden yürüyüş — zafiyetli → teşhis → düzeltilmiş

En sık gördüğüm iki gerçek desen üzerinden gideyim. Dil önemli değil, mantık evrensel.

### Örnek A: Statik cache'in unbounded büyümesi (managed dünyanın 1 numaralı sızıntısı)

**Zafiyetli kod (Java benzeri, mantık her dilde aynı):**

```java
public class UserService {
    // Sınıf yükleyici hayatta oldukça bu map yaşar → statik = GC root
    private static final Map<String, User> CACHE = new HashMap<>();

    public User getUser(String id) {
        return CACHE.computeIfAbsent(id, this::loadFromDb);
    }
}
```

Bu kod incelemede masumdur. "Cache koydum, performans arttı." Ama: her yeni benzersiz `id` map'e bir giriş ekler ve **hiçbir şey silmez.** Kullanıcı sayısı milyonlarsa, ya da `id` request'ten gelen serbest bir string ise (arama sorgusu, session token), map sonsuza kadar büyür. Statik olduğu için GC asla toplayamaz.

**Teşhis yürüyüşü:**

1. Grafik: RSS gece boyu düz rampa, trafik sabit ama üye tabanı çeşitleniyor. → gerçek sızıntı şüphesi.
2. `t0` histogram, 50.000 farklı kullanıcıya istek at, GC tetikle, `t1` histogram.
3. Fark: `User` instance sayısı ~50.000 arttı, `HashMap$Node` sayısı da paralel arttı. Orantı birebir → suçlu bir map.
4. Dominator tree'de bu `User`'ların ortak atası: `UserService.CACHE`. GC root'a giden path tek satırda görünür.
5. Kod'a bak: `static final Map`, eviction yok. Teşhis tamam.

**Düzeltilmiş:**

```java
public class UserService {
    // Sınırlı boyut + LRU eviction. Boyut sabit → sızıntı imkânsız.
    private final Cache<String, User> cache = Caffeine.newBuilder()
        .maximumSize(10_000)
        .expireAfterWrite(Duration.ofMinutes(30))
        .build();

    public User getUser(String id) {
        return cache.get(id, this::loadFromDb);
    }
}
```

İki değişiklik kritik: (a) `static` kalktı — gerçekten global paylaşım gerekmiyorsa instance'a bağla; (b) sınır ve TTL kondu. Kural: **her cache'in bir tavanı ve bir eviction politikası olmalı.** Sınırsız cache, cache değil, gecikmeli OOM'dur.

### Örnek B: Event listener / callback sızıntısı (frontend ve backend, her ikisi)

**Zafiyetli (JavaScript benzeri):**

```javascript
class Widget {
  constructor(store) {
    this.store = store;
    // store bir singleton (global) → uzun ömürlü
    store.on('update', this.onUpdate.bind(this));
  }
  onUpdate = () => { /* this.someBigData'ya dokunur */ }
  destroy() {
    // listener kaldırılmadı!
  }
}
```

Her `Widget` oluşturulup `destroy` edildiğinde, DOM'dan kalkar ama `store` hâlâ onun `onUpdate`'ini (dolayısıyla tüm `this`'ini, dolayısıyla `someBigData`'sını) referanslar. Widget'lar açılıp kapandıkça store'un listener listesi ve arkasındaki widget'lar birikir. SPA'larda sayfa geçişleri arttıkça tarayıcı sekmesi şişer.

**Teşhis:** Chrome DevTools'ta Memory sekmesi → iki heap snapshot al (sayfayı 20 kez aç-kapa arasında). "Comparison" görünümünde `Widget` sayısının 20 arttığını görürsün — oysa hepsi destroy edildi, 0 olmalıydı. Detached DOM node'ları ve `onUpdate` closure'ları retainer olarak çıkar. Retainer path store'un event listener dizisini gösterir.

**Düzeltilmiş:**

```javascript
class Widget {
  constructor(store) {
    this.store = store;
    this.handler = this.onUpdate.bind(this); // referansı sakla
    store.on('update', this.handler);
  }
  destroy() {
    this.store.off('update', this.handler); // simetrik temizlik
  }
}
```

Evrensel kural: **her `subscribe`/`on`/`addListener`/`register` çağrısının bir ömür sahibi ve simetrik bir `unsubscribe`'ı olmalı.** Kaydı yapan, iptalinden de sorumludur. Dile göre `try/finally`, RAII, `defer`, `using`, `WeakRef`, ya da lifecycle hook kullanılır ama prensip aynı.

### Örnek C: ThreadLocal + thread pool (sinsi olanı)

Bir `ThreadLocal<HeavyContext>` set edip `remove()` etmezsen, normal şartlarda thread ölünce temizlenir. Ama uygulama sunucuları **thread pool** kullanır — thread'ler asla ölmez, yeniden kullanılır. Böylece her istekte `ThreadLocal` set edilir, hiç silinmez, ve pool'daki her thread bir `HeavyContext` tutar. 200 thread × büyük context = sessiz sızıntı. Düzeltme her zaman `finally { threadLocal.remove(); }`.

## 4. Acemi vs pro — tuzaklar ve gözden kaçanlar

**Acemi:** RSS yüksek görünce hemen heap dump alır ve en büyük nesneye bakar.
**Pro:** En büyük nesne genelde suçlu değildir — o normal olarak büyük olan cache/pool'dur. Suçlu **en hızlı büyüyendir.** Fark (differential) bakılır, mutlak boyuta değil.

**Acemi:** Tek snapshot alır, "bak `byte[]` çok fazla" der.
**Pro:** Her heap'te en çok `byte[]`, `String`, `char[]` vardır — bu bilgi değildir. İki snapshot arasında **hangi türün orantılı arttığı** bilgidir.

**Acemi:** Managed dilde "GC var, sızıntı olmaz" sanır.
**Pro:** GC sadece **erişilemez** belleği toplar. Erişilebilir ama gereksiz tutulan bellek (retention) GC'nin göremediği sızıntıdır ve en yaygın olanıdır.

**Acemi:** `System.gc()` / manuel GC çağırıp "belleği temizledim" sanır.
**Pro:** Manuel GC teşhis aracıdır (snapshot öncesi gürültüyü temizlemek için), çözüm değil. Sızdıran referans duruyorsa GC hiçbir şey toplamaz.

**Acemi:** Development'ta üretemeyince "sızıntı yok" der.
**Pro:** Çoğu sızıntı **ölçek ve zamanla** ortaya çıkar — 100 istekte görünmez, 10 milyon istekte OOM olur. Local'de küçük görünen orantı, production'da ölümcüldür. Testi yük ve süreyle yaparsın.

**"İşe yarar gibi görünüp production'da patlayan" klasikler:**

- **Logger'a nesne biriktirmek:** Bir in-memory log buffer ya da metrics listesi "son 1000 satır" diye başlar, sınır konmadan büyür.
- **`String.substring` / view semantiği:** Bazı dillerde/sürümlerde bir substring, dev bir string'in tamamını arka planda tutabilir (eski Java). 5 karakter için 5 MB tutulur.
- **Kapanmayan kaynaklar + finalizer:** `close()` edilmeyen stream'ler finalizer kuyruğunda birikir; finalizer thread yetişemezse kuyruk şişer. `try-with-resources` / `using` / `defer` yoksa tehlike.
- **Static'e sızan `this`:** İç sınıf (inner class) ya da lambda, dıştaki nesneyi kapalıca (implicitly) tutar. Bir listener'ı statik bir yere kaydettiğinde tüm dış nesne asılı kalır.
- **Unbounded kuyruk (queue):** Producer, consumer'dan hızlıysa `LinkedBlockingQueue` (sınırsız) sonsuza büyür. Bu bellek sızıntısı gibi görünür ama aslında **backpressure eksikliğidir** — sınırlı kuyruk kullan.
- **Connection/DbContext leak:** Her istekte açılıp kapanmayan bağlantılar hem pool'u hem native belleği yer.

**Fragmentasyon tuzağı:** glibc `malloc`, çok thread'li bir uygulamada thread başına arena açar ve serbest belleği OS'e geri vermeyebilir. RSS yüksek görünür, heap boştur. Saatlerce "kod sızdırıyor" diye ararsın; oysa `MALLOC_ARENA_MAX=2` ya da jemalloc'a geçiş çözer. Managed heap sabitken RSS büyüyorsa bunu şüphelen.

## 5. Araçlar ve saha notları

Araç seçimi **hangi katmanda arandığına** bağlıdır. Yanlış araç, doğru yerde bile bulamaz.

**Genel gözlem (nereye bakacağını bulmak için):**
- **RSS/working set zaman serisi:** İşin başlangıcı. Prometheus + Grafana, `container_memory_working_set_bytes`, ya da basitçe `ps`, `top`, `/proc/<pid>/smaps`. Grafiği görmeden dump alma.
- **Continuous profiling:** Production'da yeniden üretilemeyen sızıntılar için altın standart. Düşük örnekleme ile sürekli allocation profili tutar; saatler sonra "hangi call-site zamanla büyüyor" diye bakarsın. (pprof tabanlı çözümler, Java'da async-profiler'ın allocation modu.)

**JVM / Java:**
- `jcmd <pid> GC.heap_info`, `GC.class_histogram` — hızlı histogram, dump almadan tür sayıları.
- Heap dump: `jmap -dump:live` ya da `jcmd GC.heap_dump`. `live` önemli — GC sonrası canlı seti alır, ölüleri eler.
- **Eclipse MAT (Memory Analyzer):** Dominator tree ve "leak suspects" raporu. Retention path'i tek tıkla verir. Büyük dump'ları da açar. Sahada en çok işe yarayan tek araç.
- Off-heap için: Native Memory Tracking (`-XX:NativeMemoryTracking=detail`, `jcmd VM.native_memory`). Heap sabit ama RSS artıyorsa buraya bak.
- async-profiler: `--alloc` modu ile allocation hotspot'ları; hangi kod satırı ne kadar ayırıyor.

**.NET:**
- `dotnet-counters` — canlı bellek/GC sayaçları, ilk bakış.
- `dotnet-gcdump` — hafif GC dump, üretime dostu.
- `dotnet-dump` + `dumpheap -stat` / `gcroot` (SOS) — tür istatistiği ve bir nesnenin GC root'unu bulma. `gcroot` retention path için birebir.
- Unmanaged handle sızıntısı için: handle sayacı (Performance Monitor), `!finalizequeue`.

**Python:**
- `tracemalloc` — snapshot alıp iki snapshot farkı (`compare_to`) verir; hangi dosya/satır ne kadar ayırdı. Yerleşik ve çok iyi.
- `objgraph` — bir türün örnek sayısını izler ve referans zincirini çizer (`show_backrefs`). Referans döngülerini görmek için ideal.
- `gc` modülü — `gc.garbage` ile toplanamayan döngüleri, `gc.get_referrers` ile kim tutuyor'u.

**JavaScript / Node / tarayıcı:**
- Chrome DevTools Memory: **Heap snapshot** + Comparison (iki snapshot farkı), **Allocation instrumentation on timeline** (hangi allocation kalıcı), detached DOM node avı.
- Node: `--inspect` ile aynı DevTools; `node --heapsnapshot-signal`, ya da `heapdump`. `process.memoryUsage()` ile `heapUsed` vs `rss` ayrımı.

**Native C/C++:**
- **Valgrind (memcheck):** Kesin ama yavaş (10-50x). Test/CI için; production'da değil.
- **AddressSanitizer / LeakSanitizer (ASan/LSan):** Derleme zamanı enstrümantasyon, çok daha hızlı. Modern akış budur — `-fsanitize=address`. Stack trace ile sızan alokasyonu verir.
- **jemalloc/tcmalloc heap profiling:** Production'da düşük maliyetle allocation profili; fragmentasyon teşhisinde de birinci sınıf.

**Pratik saha tüyoları (deneyimin damıtılmış hâli):**

1. **Her zaman iki nokta al, farka bak.** Tek dump seni yanıltır. "Delta thinking" bu işin tamamıdır.
2. **Snapshot öncesi GC tetikle.** Yoksa henüz toplanmamış ama toplanacak çöp, sızıntı gibi görünür ve seni yanlış ize sürükler.
3. **Mutlak boyuta değil, büyüme hızına bak.** En büyük değil, en hızlı büyüyen suçludur.
4. **Önce heap mi off-heap mi ayır.** Bu ilk çatal, saatler kazandırır. Heap dump'ta olmayan bir sızıntıyı heap dump'ta arama.
5. **Reprodüksiyonu otomatikleştir.** Aynı isteği N kez atan bir script, differential'ı temiz yapar; N ile orantılı büyüyen türü net görürsün.
6. **Production'da örnekleme profili kullan, dump alma.** Full heap dump servisi dondurur (stop-the-world), OOM'a yakın bir servide onu daha da hızlı öldürebilir. Continuous/sampling profiler risksizdir.
7. **Bounded her şey.** Cache, queue, buffer, pool, retry listesi — sınırsız olan her koleksiyon gelecekteki bir OOM'dur. Kod incelemede "bunun tavanı ne?" diye sor.
8. **OOM'un kimi öldürdüğüne aldanma.** OOM killer, belleği son isteyeni öldürür; sızdıranı değil. Suçlu, kurbanın kendisi olmayabilir.
9. **Container limitlerini oku.** Kubernetes'te heap limitini container memory limitine göre ayarla; JVM eski sürümlerde cgroup limitini görmeyip host belleğini sanır ve limitin çok üstünde heap ister → OOMKilled. `-XX:MaxRAMPercentage` ya da modern JDK'nın cgroup farkındalığı.
10. **RSS düşmüyorsa allocator'ı şüphelen.** Uygulama belleği bıraktığını söylüyor ama OS düşürmüyor → arena/fragmentasyon. `MALLOC_ARENA_MAX`, `malloc_trim`, ya da jemalloc.

**Gerçek bir vaka anatomisi (saha hikâyesi):** Bir ödeme servisi her 40 saatte bir OOMKilled oluyordu, restart sonrası sayaç sıfırlanıyordu. İlk refleks "heap dump al, MAT'e ver" oldu; dump temizdi, heap kullanımı 2 GB'da plato yapmıştı. Ama container RSS 6 GB'a tırmanıyordu. Yani **heap suçlu değildi.** Native Memory Tracking açtık: `Thread` kategorisi sürekli büyüyordu. Sebep: her gelen mesaj için bir `ExecutorService` oluşturulup asla `shutdown()` edilmiyordu. Her executor kendi thread'lerini açıyor, iş bitince thread'ler park hâlinde kalıyordu (daemon değil, non-daemon). Binlerce thread × ~1 MB stack = GB'larca native bellek, heap'te sıfır iz. Ders: heap dump ilk araç değildir; **grafiği okuyup katmanı seçmek** ilk iştir. Yanlış katmanda dünyanın en iyi aracı bile boş döner.

**Bir başka desen — döngüsel referans + zayıf finalizer:** Python'da iki nesne birbirini referanslayıp ayrıca `__del__` tanımlıyorsa, eski sürümlerde GC bu döngüyü toplayamaz ve `gc.garbage`'a atardı. Modern Python bunu büyük ölçüde çözdü ama C uzantıları (native extension) tuttuğunda hâlâ görülür. `objgraph.show_backrefs` ile döngüyü görselleştirmek, kâğıt üstünde saatlerce kafa yormaktan hızlıdır. Genel ilke: sızıntı avında **referans grafiğini gözle görmek**, hayal etmekten daima üstündür — bu yüzden retainer path / backref çizen araçlar bu kadar değerlidir.

**Ölçüm hijyeni:** Bir teşhis oturumunda ölçtüğün şeyin ne olduğunu bil. `heapUsed` (managed live set) ile `rss` (işletim sisteminin gördüğü) farklı hikâyeler anlatır. Bir sayının arttığını görüp diğerini kontrol etmeden karar vermek, en pahalı yanlış yönlendirmedir. Her zaman ikisini yan yana grafiğe koy: ikisi birlikte artıyorsa managed retention; sadece RSS artıyorsa off-heap/native/allocator. Bu iki çizgi, teşhisin pusulasıdır.

Son bir çerçeve: bellek sızıntısı teşhisi bir **daraltma** oyunudur, arama değil. Her adım aday alanı yarıya böler — sızıntı mı değil mi, heap mi off-heap mi, hangi tür, hangi referans zinciri, hangi kod satırı. Acemi rastgele dump açıp içinde kaybolur; pro her adımda bir soruyu cevaplayıp uzayı küçültür. Aracın ne yaptığını bilmek değil, **hangi soruyu sorduğunu bilmek** bu işi yapan şeydir.
