# Eşzamanlılık Bug'ı Teşhisi (Race / Deadlock)

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Eşzamanlılık bug'ları, birden fazla yürütme akışının (thread, goroutine, async task, ayrı süreç, hatta ayrı makine) paylaşılan bir kaynağa aynı anda dokunmasından doğar. Tek başına çalışan bir fonksiyon doğrudur; ikinci bir akış araya girdiği anda yanlışa döner. Bu yüzden bu bug sınıfı diğerlerinden temelde farklıdır: **kod satırı yanlış değildir, iki doğru satırın araya girme (interleaving) sırası yanlıştır.**

Pratikte üç aile ile karşılaşırsın:

- **Race condition / data race:** İki akış, en az biri yazan, senkronizasyonsuz aynı belleğe erişir. Sonuç interleaving'e bağlı, yani deterministik değil. Bozuk sayaç, kaybolan güncelleme (lost update), yarı yazılmış nesne.
- **Deadlock:** İki veya daha fazla akış, karşılıklı olarak birbirinin tuttuğu kilidi bekler. Sistem tümüyle veya kısmen donar. İş parçacığı canlı ama hiç ilerlemiyor.
- **Livelock / starvation:** Akışlar çalışıyor, CPU yakıyor ama net iş üretmiyor; ya da bir akış sürekli kaynağa erişemiyor.

Ne zaman devreye girer? Tekil isteklerde asla göremezsin. Yük altında, çok çekirdekli üretim makinesinde, "ayda bir" veya "Black Friday'de" ortaya çıkar. Klasik cümle: "Lokalde tekrar üretemiyorum ama üretimde günde 3 kez oluyor." İşte bu cümle, %90 ihtimalle eşzamanlılık bug'ının imzasıdır. Testte görünmemesinin sebebi tesadüf değil, doğası: teşhis işi, **düşük olasılıklı ve deterministik olmayan bir olayı gözlemlenebilir ve tekrarlanabilir hale getirmektir.**

## 2. Metodoloji ve karar ağacı (asıl değer)

Kıdemli birinin kafasındaki akış, aracı açmadan önce çalışan bir sınıflandırma refleksidir. Sıra önemli.

### Adım 0: "Bu gerçekten eşzamanlılık mı?" filtresi

Her flaky (kararsız) bug eşzamanlılık değildir. Önce şu üçünü ele:
- **Test sırası bağımlılığı:** Testler paylaşılan global state bırakıyor olabilir. Testi tek başına çalıştır, geçiyorsa → izolasyon sorunu, race değil.
- **Dış bağımlılık:** Ağ zaman aşımı, saat kayması, DNS. Bunlar kararsız ama tek-thread'de de olur.
- **Belleğe/diske bağlı davranış:** GC duraklaması, disk doluluğu.

Eşzamanlılık lehine güçlü sinyaller: çekirdek sayısı arttıkça hata oranı artıyor; hata yük/eşzamanlılıkla ölçekleniyor; log'da "imkânsız" bir state var (mesela bir nesne hem null hem init edilmiş görünüyor); yeniden başlatınca düzeliyor ama geri geliyor.

### Adım 1: Belirtiden aileye — karar ağacı

**Belirti: Sistem/endpoint donuyor, CPU düşük (yakın sıfır), istekler birikiyor.**
→ Bu neredeyse kesin **deadlock** veya sonsuz bekleme. CPU'nun düşük olması kritik ipucu: akışlar bekliyor, dönmüyor. İlk hamle: **thread dump al.** (Neyi beklediklerini birebir gösterir.) Bir sonraki adıma atla.

**Belirti: CPU %100, iş ilerlemiyor veya çok yavaş.**
→ **Livelock** ya da spin/kilit çekişmesi (lock contention). Thread dump'ta akışlar RUNNABLE ama hep aynı retry/CAS döngüsünde. Profiler'a git.

**Belirti: Sonuç bazen yanlış, çökme yok, donma yok. Değerler tutarsız.**
→ **Data race / lost update.** En sinsi aile. Burada thread dump işe yaramaz (olay anlıktır, yakalayamazsın). Statik/dinamik race detector'a (ThreadSanitizer, Go `-race`, Java'da jcstress/FindBugs) ve kod incelemesine git.

**Belirti: Ara sıra çökme, "imkânsız" NullPointer/segfault, bozuk koleksiyon (ConcurrentModification, HashMap sonsuz döngüsü).**
→ **Senkronize edilmemiş paylaşılan veri yapısı.** Genellikle thread-safe olmayan bir yapı (düz HashMap/ArrayList/dict) birden çok yazar tarafından kullanılıyor.

### Adım 2: Deadlock kolunda derinleşme — "kilit sıralaması" merceği

Deadlock gördüğünde tek soru vardır: **hangi akış hangi kilidi tutuyor ve hangisini bekliyor?** Bunu thread dump verir. İki thread'in birbirini beklediği bir döngü (cycle) ararsın. Çözüm neredeyse her zaman aynı ilkeye iner: **global bir kilit edinme sırası (lock ordering) tanımla ve her yerde ona uy.** İki kilit A ve B varsa, herkes önce A'yı sonra B'yi alacak; kimse tersini yapmayacak. Döngü oluşamaz.

Takas: Kaba (coarse) tek bir kilit deadlock'u tamamen ortadan kaldırır ama paralelliği öldürür (throughput düşer). İnce (fine-grained) çok kilit performans verir ama deadlock riski ve karmaşıklık getirir. Kıdemli karar: **önce doğruluk, sonra ölç, gerekiyorsa inceye geç.** Prematüre fine-grained kilitleme, ürettiği deadlock'lara değmez.

### Adım 3: Data race kolunda derinleşme — "paylaşılan yazılabilir state" avı

Data race'te düşünme kalıbı şudur: **"Bu değişkeni kim yazıyor, aynı anda kim okuyor/yazıyor, aralarında hangi happens-before ilişkisi var?"** Happens-before yoksa race var. Aradığın şey mutable + shared + senkronizasyonsuz üçlüsüdür. Üçünden birini kaldırırsan bug ölür:
- **Shared'i kaldır:** thread-local yap, kopya ver, akışa özel state.
- **Mutable'ı kaldır:** immutable yap. En güçlü ve en az hata yapılan çözüm. Immutable veride race olmaz.
- **Senkronizasyonsuzu kaldır:** kilit, atomik, kanal (channel) ekle.

Kıdemli tercih sırası genelde: önce paylaşımı yok et → olmuyorsa immutability → olmuyorsa mesajlaşma (channel/actor) → en son manuel kilit. Manuel kilit en güçlü ama en çok ayağa dolanan araçtır.

Burada gözden kaçan bir incelik var: bellek görünürlüğü (memory visibility). Bir thread'in yazdığı değeri diğer thread'in görmesi otomatik değildir. Modern CPU'lar ve derleyiciler yeniden sıralama (reordering) yapar; her çekirdeğin kendi cache'i vardır. Senkronizasyon primitifleri (kilit, atomik, volatile, kanal) sadece "aynı anda girme"yi değil, aynı zamanda **"benim yazdığımı sen gör" garantisini** (happens-before) kurar. Bu yüzden "aslında iki thread aynı anda dokunmuyor, biri yazıp bitiriyor sonra öteki okuyor" gibi görünen kod bile, arada bir bellek bariyeri yoksa bozuktur: okuyan thread eski (bayat) değeri görebilir, hatta sonsuza dek görebilir. Acemi "sıra hiç çakışmıyor ki" der ve bariyeri atlar; pro **sıralama garantisi olmayan her paylaşımı race sayar**, çakışma olasılığına bakmaz.

### Adım 4: Tekrar üretilebilirlik — en kritik pratik beceri

Teşhisin gerçek darboğazı bug'ı istediğinde tetikleyebilmektir. Kıdemli kişi buna zaman harcar:
- **Stres/tekrar:** testi 10.000 kez, paralel, farklı çekirdek sayılarında koştur. Race sıklığı çekirdekle artar.
- **Zamanlamayı çarpıt:** şüpheli iki satır arasına yapay `sleep`/`yield` koy. Race varsa gizli pencere büyür, hata patlar. Bu "kirli ama etkili" bir doğrulama tekniğidir — hipotezini saniyeler içinde kanıtlar.
- **Deterministik hale getir:** mümkünse race detector'ı aç; o tek koşuda bile "olabilecek" race'i statik happens-before analiziyle yakalar, gerçekten çakışmasını beklemene gerek kalmaz.

## 3. Gerçek kod üzerinden yürüyüş: zafiyetli → teşhis → düzeltilmiş

### Senaryo A: Klasik lost update (data race)

Bir web servisinde her isteğin işlenme sayısını tutan bir sayaç. Yükte sayaç hep gerçekten düşük çıkıyor.

**Zafiyetli (dil-bağımsız, Java benzeri):**

```
class Metrics {
    private long count = 0;          // paylaşılan, mutable, senkronizasyonsuz

    void record() {
        count = count + 1;           // ATOMİK DEĞİL
    }
}
```

`count = count + 1` tek satır görünür ama makine düzeyinde üç işlemdir: **oku → artır → yaz.** İki thread aynı anda 5 okur, ikisi de 6 yazar. Bir artış kaybolur. 1.000.000 istekte binlerce kayıp. Test tek-thread olduğu için asla görünmez.

**Teşhis yürüyüşü:** Belirti "sonuç yanlış, çökme yok" → data race kolu. Thread dump işe yaramaz. `record()` içindeki `count` paylaşılan yazılabilir state; happens-before yok. Doğrulamak için oku ile yaz arasına yapay gecikme koyarsan kayıp oranı fırlar → hipotez kanıtlandı. Bir race detector da bu satırı doğrudan işaretler.

**Düzeltilmiş — üç meşru seçenek, takasıyla:**

```
// Seçenek 1: Atomik. En dar, en hızlı. Tek değişken için ideal.
private AtomicLong count = new AtomicLong();
void record() { count.incrementAndGet(); }   // tek atomik oku-artır-yaz

// Seçenek 2: Kilit. Birden çok alanı birlikte tutarlı güncellemen gerekirse.
private long count = 0;
synchronized void record() { count++; }

// Seçenek 3: Paylaşımı yok et. Her thread kendi sayacını tutar,
// okuma anında toplanır. En yüksek throughput, sıfır çekişme.
```

Kıdemli karar: tek bir sayaç için Seçenek 1. Ama `count` ile birlikte "son güncelleme zamanı" gibi ikinci bir alan da tutarlı değişecekse, iki atomik yetmez (aralarında yine race olur) → Seçenek 2, tek kilit altında ikisini birlikte güncelle. **"Atomik atomik demektir ama iki atomiğin bileşkesi atomik değildir"** — acemilerin en sık düştüğü çukur.

### Senaryo B: check-then-act (kontrol et sonra davran) yarışı

```
if (!cache.containsKey(key)) {   // kontrol
    cache.put(key, expensiveLoad(key));   // davran
}
```

İki thread aynı anda `containsKey` → ikisi de false görür → ikisi de `expensiveLoad` çağırır (pahalı işi iki kez yapar, belki iki farklı nesne yazar, tüketici hangisini gördü belirsiz). Kontrol ile davranış arasındaki pencere race'in evidir. `ConcurrentHashMap` kullansan bile bu **birleşik işlem** atomik değildir. Doğru çözüm işlemi atomik yapan API'dir (mesela `computeIfAbsent`) ya da tüm bloğu bir kilit altına almak. Ders: **thread-safe koleksiyon, thread-safe iş mantığı demek değildir.**

### Senaryo C: Klasik deadlock (kilit sırası)

Para transferi. Her hesabın kendi kilidi var.

**Zafiyetli:**

```
void transfer(Account from, Account to, long amount) {
    synchronized (from) {           // önce 'from' kilidi
        synchronized (to) {         // sonra 'to' kilidi
            from.balance -= amount;
            to.balance   += amount;
        }
    }
}
```

`transfer(A, B)` A'yı kilitler B'yi bekler; aynı anda `transfer(B, A)` B'yi kilitler A'yı bekler. Kilitlenme. Belirti: sistem donar, CPU sıfır, transfer thread'leri BLOCKED. Thread dump'ta iki thread'in birbirini beklediği döngü net görünür.

**Düzeltilmiş — global kilit sırası:**

```
void transfer(Account from, Account to, long amount) {
    // Her zaman düşük id'li hesabı ÖNCE kilitle. Sıra evrensel → döngü oluşamaz.
    Account first  = from.id < to.id ? from : to;
    Account second = from.id < to.id ? to   : from;
    synchronized (first) {
        synchronized (second) {
            from.balance -= amount;
            to.balance   += amount;
        }
    }
}
```

Tüm çağrılar kilitleri aynı sırada (id'ye göre) aldığı için karşılıklı bekleme döngüsü matematiksel olarak imkânsızlaşır. Alternatif: `tryLock` + zaman aşımı (kilidi alamazsan bırak, geri çekil, tekrar dene) — deadlock'u kırar ama livelock riski getirir ve daha karmaşıktır. Kıdemli varsayılan: **mümkünse kilit sıralaması, sıralama tanımlanamıyorsa tryLock/timeout.**

Sahada deadlock'un dört koşulu (Coffman koşulları) düşünme çerçevesi olarak işe yarar: karşılıklı dışlama (mutual exclusion), tut-ve-bekle (hold and wait), önalınamazlık (no preemption) ve döngüsel bekleme (circular wait). Deadlock oluşması için dördünün **aynı anda** sağlanması gerekir. Çözüm demek, bu dörtten en az birini kırmak demektir. Kilit sıralaması "döngüsel bekleme"yi kırar. Tüm kilitleri tek seferde ya hep ya hiç alma (all-or-nothing) "tut-ve-bekle"yi kırar. tryLock+timeout+geri çekilme "önalınamazlık"ı kırar. Bir kaynağa tek erişim gerektirmeyen tasarım (immutable paylaşım, kopya) "karşılıklı dışlama"yı kırar. Kıdemli kişi bir deadlock'a baktığında "hangi koşulu en ucuza kırabilirim" diye düşünür; çoğu üretim kodunda en ucuzu ve en dayanıklısı kilit sıralamasıdır çünkü kod okunabilir kalır ve ek retry mantığı gerektirmez.

## 4. Acemi vs pro: yaygın hatalar ve sinsi tuzaklar

**"volatile ile thread-safe oldu" yanılgısı.** Acemi `volatile` görünürlüğü çözer sanır ve compound işlemi korunmuş sanır. `volatile int x; x++` hâlâ race'tir — volatile görünürlük verir, atomiklik vermez. Pro, volatile'ı yalnızca bir bayrağın (flag) görünürlüğü için kullanır, sayaç için asla.

**"Lokalde geçti, kapat gitsin" tuzağı.** Race testte %0.01 ihtimalle patlar. Acemi 20 kez koşar, geçer, "düzeldi" der. Pro bilir ki **eşzamanlılık bug'ında testin geçmesi kanıt değildir; sadece o interleaving'in o an olmadığını gösterir.** Kanıt, ya race detector'ın temiz raporu ya da paylaşımın yapısal olarak yok edilmesidir.

**Kilidi geniş atıp performansı, dar atıp doğruluğu kaybetmek.** Acemi ya her şeyi tek dev kilitle sarar (sistem seri hale gelir, throughput çöker) ya da kilidi sadece bir satıra koyup ilişkili ikinci satırı dışarıda bırakır (yine race). Pro **kritik bölümü invariant'a göre çizer:** birlikte tutarlı kalması gereken tüm alanlar tek kilit altında, gerisi dışarıda.

**Kilit tutarken dışarı çağrı yapmak (alien call).** Kilit tutarken bilmediğin bir callback/dinleyici çağırırsan, o kod başka bir kilit alabilir → beklenmedik deadlock. Pro kilidi mümkün olan en kısa süre tutar ve **kilit içinde dış/geri çağrı yapmaz.**

**Double-checked locking'i yanlış yazmak.** Bellek modeli olmadan yazılmış "önce kilitsiz kontrol et, sonra kilitle" deseni yarım-init edilmiş nesne sızdırır. İşe yarar gibi görünür, üretimde nadiren yarı-kurulu nesne verir. Pro ya dilin garanti ettiği idiyomu (initialization-on-demand holder, `Lazy`) kullanır ya da bu optimizasyonu hiç yapmaz.

**"async single-thread olduğu için race yok" yanılgısı.** Tek thread'li event loop'ta (Node, tek-thread async) klasik data race olmaz ama **`await` her noktada interleaving penceresidir.** İki `await` arasında oku, `await` et, döndüğünde yaz → arada başka task state'i değiştirmiş olabilir. "Check-then-act" yarışı burada da yaşar. Acemi async'i sihirli koruma sanır; pro her `await`'i "başka her şey araya girebilir" işareti olarak okur.

**Kaybolan wakeup ve `if` ile bekleme.** Koşul beklerken `while` yerine `if` kullanmak (spurious wakeup + koşulun tekrar bozulması) klasik tuzaktır. Bekleme koşulu **her zaman `while` döngüsünde** tekrar kontrol edilmelidir.

**Log'un kendisinin race'i gizlemesi.** Acemi araya `print`/`log` koyar, bug kaybolur, "düzeldi" sanır. Gerçekte log I/O yaptığı için zamanlamayı değiştirdi ve pencereyi kapadı. Bu bir **heisenbug**'dur — gözlemek olayı değiştirir. Pro bunu tersine çevirip teşhis aracı yapar: log koyunca kaybolan bug, güçlü bir race sinyalidir.

**Havuzdan alınan nesneyi paylaşmak (thread-pool / connection sızıntısı).** Acemi bir thread-local'ı ya da bir bağlantı/buffer nesnesini bir görevin ömrünün ötesine taşır; nesne havuza geri döner, başka bir istek onu alır, ikisi aynı nesneye yazar. Belirti: bir kullanıcının verisi başka kullanıcıda görünür — ciddi bir güvenlik ve tutarlılık hatası. Pro, paylaşılan mutable nesnenin ömrünü (lifecycle) tam olarak bilir: kim sahibi, ne zaman devrediliyor, geri verildikten sonra kimse dokunamaz.

**`ThreadLocal` ile async/virtual thread karışımı.** ThreadLocal, işin baştan sona aynı thread'de kalacağını varsayar. Async/reaktif kodda iş thread'den thread'e sıçrar; ThreadLocal ya yanlış değeri taşır ya kaybolur. Acemi "context'i ThreadLocal'da tutarım" der; pro bağlamı açıkça (explicit) parametre veya yapılandırılmış eşzamanlılık scope'u ile taşır.

## 5. Araçlar ve saha notları

**Thread dump — deadlock'un ilk ve en güçlü aracı.** Süreç donduğunda anlık yığın (stack) görüntüsü al. Java'da `jstack <pid>` veya SIGQUIT; Go'da panic'te tüm goroutine dökümü veya `SIGABRT`; Python'da `faulthandler`/`py-spy dump`. Modern JVM thread dump'ları döngüyü açıkça "Found one Java-level deadlock" diye yazar — sana kilit döngüsünü hediye eder. Saha kuralı: **donma gördüğünde önce thread dump, tahmin sonra.** Tek bir dump bazen yeterli olmaz; birkaç saniye arayla iki-üç dump al, hep aynı satırda bekleyen thread ilerlemediğini kanıtlar.

**Race detector — data race'in altın standardı.** Go'da `go test -race` / `go run -race`, C/C++/Rust'ta ThreadSanitizer (`-fsanitize=thread`), Java'da jcstress (interleaving'leri sistematik zorlar) ve statik analiz. Bunlar happens-before ilişkisini izler; race gerçekten patlamasa bile "buradaki iki erişim arasında sıralama garantisi yok" der. **CI'da race detector'ı açık tutmak, üretimde 3 ay sonra çıkacak bir bug'ı bugün yakalar.** Maliyeti: 2-10x yavaşlama, bu yüzden ayrı bir CI job'ında koşturulur, prod'da değil.

**Stres / tekrar araçları.** Testi binlerce kez, paralel, farklı çekirdek/GOMAXPROCS ile koştur. Go'da `go test -race -count=1000 -parallel`, genel olarak `stress`/`stress-ng` benzeri sarmalayıcılar. Amaç düşük olasılıklı interleaving'i olasılık kanunuyla zorla ortaya çıkarmak.

**Profiler ve observability — livelock/çekişme için.** CPU %100 ama iş yoksa profiler (perf, async-profiler, pprof) sana zamanın hangi spin/CAS döngüsünde yandığını gösterir. Lock contention profiling (JFR'de "Java Monitor Blocked", pprof'ta mutex/block profili) hangi kilidin darboğaz olduğunu ölçer — **kilidi tahminle değil, ölçüyle daralt.** Üretimde ise dağıtık iz sürme (tracing) ve metrikler: "isteklerin p99'u aniden fırladı ama hata yok" grafiği çoğu zaman bir kilit çekişmesinin ilk görünen yüzüdür.

**Yapay gecikme / yield enjeksiyonu.** En ucuz ve en hızlı doğrulama. Şüpheli kritik bölgenin ortasına geçici `sleep(10ms)`/`yield` koy. Race varsa pencere büyür, bug her koşuda patlar; hipotezini saniyeler içinde kanıtlar veya çürütür. Bazı test çerçeveleri bunu sistemli yapar (interleaving/schedule fuzzing). Kullandıktan sonra mutlaka geri al — bu bir teşhis aracıdır, çözüm değil.

**Statik analiz ve tip sistemi.** Rust'ın ownership/`Send`+`Sync` modeli data race'i derleme zamanında engeller — mümkünse veri-yarışını dille imkânsız kılmak, sonradan avlamaktan üstündür. Diğer dillerde annotation tabanlı araçlar (`@GuardedBy`, thread-safety linter'ları) "bu alan bu kilit altında korunmalı" niyetini kodda belgeleyip ihlali işaretler.

**Saha notu — post-mortem disiplini.** Üretim deadlock'unda süreci hemen öldürüp restart etmeden **önce thread dump'ı al.** Restart bug'ı gizler, kanıtı yok eder. Aynı şekilde core dump / heap dump, "imkânsız" state'in fotoğrafıdır. Bir eşzamanlılık olayı çözüldüğünde eklenen ilk şey **regresyon testi olmalı**: race detector altında, çok tekrarlı, ideali interleaving'i zorlayan bir test. Aksi halde aynı bug altı ay sonra farklı bir yerden geri gelir; çünkü kod düzelse de o interleaving'i yasaklayan hiçbir bekçi kalmamıştır.

**Bir cümlelik özet karar refleksi:** Donma + düşük CPU → thread dump → kilit döngüsü → kilit sıralaması. Yanlış sonuç + çökme yok → race detector + paylaşımı yok et (önce immutability, sonra atomik/kilit). Ve her zaman: testin geçmesi kanıt değil; kanıt ya detector'ın temiz raporu ya da bug'ın yapısal olarak imkânsız kılınmasıdır.

Son bir saha bilgeliği: eşzamanlılık bug'ları çözülürken en büyük hata, "yamayı" (bir yere kilit ekleyip geçmek) çözüm sanmaktır. Kıdemli kişi bug'ı gördükten sonra bir adım geri çekilip **"bu paylaşımı en baştan neden yapıyorum"** diye sorar. Çoğu zaman en sağlam çözüm kilit eklemek değil, mimariyi paylaşımsız hale getirmektir: her isteğe kendi state'ini vermek, mutable global'ı immutable snapshot'a çevirmek, iletişimi paylaşılan bellek yerine mesajlaşmaya (channel/queue) taşımak. "Belleği paylaşarak iletişim kurma; iletişim kurarak belleği paylaş" ilkesi tam da bunu söyler. Kilit, kaçınamadığın paylaşım için son çaredir; ilk çare değil.
