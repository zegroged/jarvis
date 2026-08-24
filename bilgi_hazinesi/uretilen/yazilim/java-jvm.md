# Java ve JVM: Bellek, Çöp Toplama, Thread'ler, Class Loading ve Deserialization

Java'nın gücü de zorluğu da aynı yerden gelir: yazdığınız kod doğrudan işlemcide değil, **JVM (Java Virtual Machine)** adı verilen bir soyutlama katmanının üzerinde çalışır. Bu katman size otomatik bellek yönetimi, taşınabilirlik ("write once, run anywhere") ve zengin bir runtime sunar; karşılığında sizden runtime'ın nasıl davrandığını anlamanızı ister. Bu makale, uzman seviyesinde iş yapmak isteyen bir mühendisin JVM iç mekaniğine dair bilmesi gereken beş kritik alanı derinlemesine ele alıyor: bellek modeli, garbage collection, thread'ler, class loading ve deserialization.

## JVM Bellek Modeli

### Tanım ve temel bölümler

JVM çalışırken belleği mantıksal olarak birkaç bölgeye ayırır. En önemlileri **heap** ve **stack**'tir, ama tablo bundan ibaret değildir.

- **Heap**: Tüm nesnelerin (object) ve dizilerin yaşadığı yer. Tüm thread'ler tarafından paylaşılır. Garbage collector'ın çalıştığı asıl alan burasıdır.
- **Stack (thread stack)**: Her thread'in kendine ait bir stack'i vardır. Metot çağrıları burada birer **stack frame** olarak yığılır; yerel değişkenler (local variables), primitive değerler ve nesnelere işaret eden referanslar (referansın kendisi, nesne değil) burada tutulur.
- **Metaspace**: Sınıf metadata'sı (class metadata) burada tutulur. Java 8 öncesinde bu bilgi heap içindeki "PermGen" bölgesindeydi; Java 8 ile birlikte native belleğe taşınan Metaspace'e geçildi. Bu değişikliğin kök nedeni, PermGen'in sabit ve kolay dolan boyutuydu — sınıf yükleme yoğun uygulamalarda `OutOfMemoryError: PermGen space` klasik bir dertti.
- **Program Counter (PC) register** ve **native method stack**: Her thread için ayrı tutulan, çalışmakta olan bytecode adresini ve JNI (native) çağrılarını yöneten alanlar.

### Kök neden: neden heap ve stack ayrımı var?

Bu ayrım keyfi değil, yaşam süresi (lifetime) ve erişim deseni farkından doğar. Bir metodun yerel değişkenleri, metot bittiğinde anlamını yitirir; dolayısıyla stack'in LIFO (last-in-first-out) doğası mükemmel uyar: metot dönünce frame pop edilir, temizlik "bedava" olur. Nesneler ise metot sınırlarını aşarak yaşayabilir (bir metotta oluşturup başka yere döndürebilirsiniz), bu yüzden yaşam süreleri belirsizdir ve merkezi, GC tarafından yönetilen bir heap gerektirir.

Kritik bir ayrım şudur: Java'da nesneler **her zaman** heap'te yaşar, referanslar ise stack'te (veya başka bir nesnenin alanı olarak heap'te) durabilir. `String s = new String("x")` yazdığınızda `s` referansı stack'te, asıl `String` nesnesi heap'tedir. Bu nedenle "pass by value" tartışması Java'da netleşir: Java daima değeri kopyalayarak geçirir; nesnelerde kopyalanan şey referansın değeridir, nesnenin kendisi değil.

### Yaygın hatalar ve tuzaklar

- **`StackOverflowError` ile `OutOfMemoryError`'ı karıştırmak**: İlki genellikle sonsuz/derin recursion yüzünden thread stack'inin dolmasıdır; ikincisi heap veya Metaspace'in dolmasıdır. Çözümleri tamamen farklıdır. Recursion'ı iteration'a çevirmek stack sorununu çözer; `-Xmx` artırmak çözmez.
- **`-Xmx` değerini fiziksel RAM'in tamamına yakın vermek**: JVM heap dışında da bellek kullanır (Metaspace, thread stack'ları, JIT kod cache, native buffer'lar). Konteyner ortamlarında (container) heap limitini RAM'in tamamına ayarlarsanız, OS "OOM killer" sürecini native bellek baskısı yüzünden öldürebilir — üstelik bu bir Java exception'ı bile üretmez.
- **Konteynerde JVM'in belleği yanlış algılaması**: Eski JVM sürümleri cgroup limitlerini görmez, host'un RAM'ini görürdü. Modern sürümler konteyner-farkındalıklıdır (container-aware), ama yine de `-XX:MaxRAMPercentage` gibi bir ayarla heap oranını açıkça belirtmek en güvenli yoldur.

## Garbage Collection (Çöp Toplama)

### Tanım

Garbage collection, artık erişilemeyen (unreachable) nesnelerin belleğini otomatik olarak geri kazanma sürecidir. "Artık kimsenin referans tutmadığı nesne çöptür" ilkesine dayanır.

### Kök neden: erişilebilirlik ve nesil hipotezi

GC'nin temel sorusu "bu nesne çöp mü?" değil, aslında **"bu nesne hâlâ erişilebilir mi?"** sorusudur. JVM, **GC root** adı verilen bir dizi başlangıç noktasından (aktif thread stack'lerindeki yerel değişkenler, statik alanlar, JNI referansları vb.) başlayarak nesne grafiğini gezer. Bu köklerden ulaşılabilen her nesne canlıdır; ulaşılamayan her şey toplanabilir. Bu yüzden `null` atamak GC'yi "tetiklemez"; sadece bir referansı koparır. Nesne, ona giden **tüm** yollar koptuğunda çöp olur.

GC tasarımının belkemiği **weak generational hypothesis**'tir: "Çoğu nesne genç ölür." Ampirik gözlem şudur — nesnelerin büyük çoğunluğu oluşturulduktan çok kısa süre sonra erişilemez hale gelir (bir döngü içinde yaratılan geçici nesneler gibi), az bir kısmı ise uzun yaşar. Bu gözlem heap'i nesillere (generation) ayırmayı mantıklı kılar:

- **Young generation** (Eden + iki Survivor alanı): Yeni nesneler burada doğar. "Minor GC" burada sık ama hızlı çalışır.
- **Old (tenured) generation**: Birkaç minor GC'den sağ çıkan nesneler buraya terfi eder (promotion). Burada "Major/Full GC" seyrek ama pahalıdır.

Bu ayrımın kazancı şudur: eğer nesnelerin çoğu genç ölüyorsa, sadece küçük Young bölgesini sık taramak, tüm heap'i taramaktan çok daha ucuzdur.

### Somut örnek: allocation ve promotion akışı

Bir web isteğini işlerken oluşturduğunuz onlarca geçici nesne (DTO'lar, string'ler) Eden'de doğar. İstek bitince erişilemez olurlar. Bir sonraki minor GC, Eden'deki canlı nesneleri Survivor'a kopyalar, gerisini siler — sizin geçici nesneleriniz "silinen gerisi" tarafındadır, dolayısıyla toplanmaları neredeyse bedavadır (kopyalanan sadece canlılardır). Uzun yaşayan bir cache nesnesi ise birkaç GC turunu atlattıktan sonra Old generation'a terfi eder.

### GC algoritmaları ve seçim mantığı

Modern JVM'ler birden fazla collector sunar ve doğru seçim iş yüküne bağlıdır:

- **G1 (Garbage-First)**: Uzun süredir varsayılan collector. Heap'i eşit boyutlu bölgelere ayırır, "duraklamada en çok çöp içeren bölgeyi önce topla" mantığıyla öngörülebilir pause hedefleri sunmaya çalışır. Genel amaçlı, dengeli seçim.
- **ZGC ve Shenandoah**: Çok düşük duraklama süresi (low-latency) hedefleyen, concurrent çalışan collector'lar. Çok büyük heap'lerde bile pause'ları milisaniye altında tutmayı amaçlar. Karşılığında biraz throughput ve CPU maliyeti alırlar.
- **Parallel GC**: Throughput odaklı; toplam işi bitirme hızını, tekil pause süresinden daha çok önemseyen batch işler için uygun.
- **Serial GC**: Tek thread'li; küçük heap'ler ve tek çekirdekli/konteyner-kısıtlı ortamlar için.

Önemli nokta: "En iyi GC" diye bir şey yoktur. Latency'e mi yoksa throughput'a mı öncelik verdiğinize göre seçim yaparsınız. Düşük latency isteyen bir trading sistemi ZGC'ye yönelirken, gece çalışan bir batch işi Parallel GC ile daha fazla toplam iş bitirir.

### Yaygın hatalar

- **`System.gc()` çağırmak**: Bu sadece bir "öneri"dir, üstelik genellikle tam bir Full GC tetikleyerek uygulamayı gereksiz yere durdurur. Üretimde neredeyse hiçbir zaman elle GC çağırmamalısınız. Çoğu ekip `-XX:+DisableExplicitGC` ile bunu tamamen devre dışı bırakır.
- **"Memory leak Java'da olmaz" yanılgısı**: GC erişilemeyen nesneleri toplar; ama yanlışlıkla **erişilebilir** tuttuğunuz nesneler asla toplanmaz. Klasik sızıntı kaynağı: sürekli büyüyen bir statik `Map`/`List`, kaldırılmayan listener'lar, veya kapatılmayan `ThreadLocal` değerleri. Bunlar teknik olarak "canlı" oldukları için GC dokunmaz; heap yavaşça dolar.
- **GC'yi tuning ile "düzeltmeye" çalışmak**: Sık Full GC görüyorsanız kök neden çoğu zaman yetersiz heap veya bir bellek sızıntısıdır; GC bayraklarını değiştirmek semptomu maskeler. Önce heap dump ve GC log'unu analiz edin.

### En iyi pratikler

- GC loglarını üretimde açık tutun ve düzenli inceleyin; pause süresi ve frekans trendlerini izleyin.
- Bellek sorunlarında heap dump alıp (örneğin bir bellek analiz aracıyla) "dominator tree"yi inceleyerek belleği kimin tuttuğunu bulun.
- Nesne havuzlaması (object pooling) modern GC'lerde çoğunlukla anti-pattern'dir; kısa ömürlü nesne allocation'ı zaten çok ucuzdur. İstisna: çok pahalı kurulan kaynaklar (bağlantılar, thread'ler).

## Thread'ler ve Java Memory Model

### Tanım

Thread, bir process içinde bağımsız çalışabilen en küçük yürütme birimidir. JVM'de her thread'in kendi stack'i ve PC register'ı vardır, ama heap'i tüm thread'lerle paylaşır. İşte concurrency zorluğunun kaynağı tam olarak bu paylaşımdır.

### Kök neden: neden concurrency zor?

Naif beklenti şudur: "Bir thread bir değişkeni yazınca, diğer thread hemen görür." Gerçek bundan çok uzaktır. Modern donanım ve derleyiciler performans için üç şey yapar:

1. **Cache'leme**: Her CPU çekirdeğinin kendi cache'i vardır; bir thread'in yazdığı değer o çekirdeğin cache'inde kalıp ana belleğe hemen yansımayabilir.
2. **Yeniden sıralama (reordering)**: Derleyici ve işlemci, tek thread'li sonucu bozmadığı sürece komutların sırasını değiştirebilir.
3. **Optimizasyon**: Derleyici, "değişmiyor" varsaydığı bir değeri register'da tutup her seferinde okumayabilir.

Tek thread'de bu optimizasyonlar görünmezdir. Çok thread'de ise bir thread'in "gerçeği" başka thread'in gördüğünden farklı olabilir. **Java Memory Model (JMM)**, bu kaosa kural getirir: hangi yazmanın hangi okuma tarafından **görülmesinin garanti edildiğini** tanımlar. Merkezi kavram **happens-before** ilişkisidir: eğer A eylemi B'den önce "happens-before" ilişkisindeyse, A'nın etkileri B'de görünür.

### `volatile`, `synchronized` ve atomicity

- **`volatile`**: Bir değişkenin her okumasının ana bellekten, her yazmasının ana belleğe yapılmasını ve reordering'in engellenmesini garanti eder (visibility + ordering). Ama **atomicity garanti etmez**. Bu yüzden `volatile int x; x++;` hâlâ race condition içerir — çünkü `x++` aslında oku-artır-yaz şeklinde üç adımdır ve iki thread araya girebilir.
- **`synchronized`**: Hem karşılıklı dışlama (mutual exclusion — aynı anda tek thread) hem de visibility sağlar. Kilidi bırakan thread'in yaptığı tüm yazmalar, aynı kilidi alan sonraki thread'de görünür.
- **`java.util.concurrent.atomic`** (örn. `AtomicInteger`): `compareAndSet` gibi işlemlerle kilit kullanmadan atomik güncelleme sağlar; sayaç gibi senaryolarda `synchronized`'a göre daha ölçeklenebilirdir.

### Somut örnek: kırık double-checked locking

Klasik bir tuzak, tembel başlatmada (lazy initialization) singleton oluşturmaktır:

```java
private static Resource instance;
public static Resource get() {
    if (instance == null) {            // 1. kontrol (kilitsiz)
        synchronized (Resource.class) {
            if (instance == null) {    // 2. kontrol (kilitli)
                instance = new Resource();
            }
        }
    }
    return instance;
}
```

Bu kod, `instance` **`volatile` olmadan** bozuktur. Neden? `new Resource()` üç adımdan oluşur: bellek ayır, constructor'ı çalıştır, referansı ata. Reordering yüzünden referans atanması, constructor bitmeden görünebilir. O anda başka bir thread ilk `if`'te `instance`'ı "null değil" görür ve **henüz tam kurulmamış** bir nesneyi kullanır. Çözüm: `instance`'ı `volatile` yapmak. Bu, happens-before garantisi verir ve reordering'i engeller.

### Yaygın hatalar

- **`Thread.sleep()` ile senkronizasyon**: "Diğer thread'in bitmesini bekle" diye sleep koymak; timing'e güvenmek daima kırılgandır. Bunun yerine `CountDownLatch`, `Future`, `join()` gibi gerçek senkronizasyon araçları kullanın.
- **Deadlock**: İki thread'in iki kilidi ters sırayla alması. Kök neden tutarsız kilit sıralamasıdır. Önlem: tüm kod yollarında kilitleri **aynı global sırada** alın.
- **Paylaşılan mutable state'e kilitsiz erişim**: En yaygın ve en sinsi hata. `HashMap`'e çok thread'den yazmak yalnızca yanlış sonuç değil, sonsuz döngü/bozulma bile üretebilir. Çok thread'li senaryoda `ConcurrentHashMap` kullanın.

### En iyi pratikler

- Mümkünse paylaşılan mutable state'ten kaçının; immutable nesneler thread-safe'tir çünkü değişmezler.
- Yüksek seviyeli soyutlamaları (`ExecutorService`, `java.util.concurrent` koleksiyonları) tercih edin; elle thread yönetmek ve `wait/notify` yazmak hataya açıktır.
- Modern Java'daki **virtual thread**'ler (Project Loom ile gelen hafif thread'ler), I/O ağırlıklı iş yüklerinde milyonlarca eşzamanlı görevi ucuza taşıyabilir. Ama CPU-bound işte sihir yapmazlar ve paylaşılan state kuralları hâlâ geçerlidir.

## Class Loading

### Tanım

Class loading, bir `.class` dosyasındaki bytecode'un JVM'e yüklenip, doğrulanıp, çalıştırılabilir hale getirilmesi sürecidir. Bu, Java'nın en güçlü ama en yanlış anlaşılan mekanizmalarından biridir.

### Kök neden: neden delegasyon modeli var?

JVM sınıfları **class loader** adı verilen bileşenlerle yükler ve bunlar hiyerarşik çalışır. Klasik hiyerarşi: Bootstrap (çekirdek Java sınıfları) → Platform/Extension → Application (sizin classpath'iniz). Kural **parent-first delegation**'dır: bir loader bir sınıfı yüklemesi istendiğinde, önce ebeveynine sorar; ebeveyn bulamazsa kendisi yükler.

Bu delegasyonun kök nedeni **güvenlik ve tutarlılıktır**. Eğer herhangi bir kod kendi `java.lang.String`'ini yükleyebilseydi, çekirdek sınıfları taklit ederek sistemi ele geçirebilirdi. Delegasyon sayesinde `java.*` sınıfları daima güvenilir Bootstrap loader'dan gelir. Ayrıca bir sınıfın kimliği (identity) yalnızca adıyla değil, **onu yükleyen loader ile birlikte** tanımlanır. Yani aynı `com.example.Foo` sınıfı iki farklı loader tarafından yüklenirse, JVM bunları **iki farklı sınıf** olarak görür — birinden bir örneği diğerinin tipine atamak `ClassCastException` üretir.

### Yükleme aşamaları

1. **Loading**: Bytecode bulunur ve `Class` nesnesi oluşturulur.
2. **Linking**: Doğrulama (verification — bytecode'un güvenli ve geçerli olduğunun kontrolü), hazırlık (statik alanlara varsayılan değer), çözümleme (sembolik referansların çözülmesi).
3. **Initialization**: Statik başlatıcılar (`static {}` blokları) ve statik alan atamaları çalışır. Bu, sınıf **ilk aktif kullanıldığında** olur (lazy) — sadece referans vermek her zaman initialization tetiklemez.

### Somut örnekler ve nerede karşımıza çıkar

- **Uygulama sunucuları ve plugin sistemleri**: Her web uygulaması kendi class loader'ında izole çalışır; böylece iki uygulama aynı kütüphanenin farklı sürümlerini kullanabilir.
- **Hot reload**: Sınıfı yeni bir loader'la yeniden yükleyip eskisini çöpe çıkararak "kod değişikliğini yeniden başlatmadan" uygulamak.

### Yaygın hatalar ve tuzaklar

- **`ClassNotFoundException` ile `NoClassDefFoundError` karışıklığı**: İlki, kod (genellikle reflection ile) çalışma anında bir sınıfı isteyip classpath'te bulamadığında olur. İkincisi, sınıf **derleme anında** vardı ama çalışma anında yok, veya ilk yüklenişinde initialization başarısız olduğu için sonraki kullanımlarda ortaya çıkar. İkincisinin kök nedeni çoğu zaman gizli bir `static` blok hatasıdır.
- **Class loader leak**: Bir uygulama kaldırılıp yeniden dağıtıldığında (redeploy), eski class loader'ının çöpe atılamaması. Genellikle bir `ThreadLocal`, static referans veya kayıtlı bir callback eski loader'ı tutar; bu loader tüm sınıflarını ve dolayısıyla Metaspace'i tutmaya devam eder. Sonuç: tekrarlanan redeploy'larda `OutOfMemoryError: Metaspace`.
- **"JAR hell" / sürüm çakışması**: Classpath'te aynı sınıfın iki sürümü varsa, hangisinin yükleneceği sıraya bağlıdır ve sessizce yanlış sürüm gelebilir.

### En iyi pratikler

- Sınıf kimliğinin loader'a bağlı olduğunu unutmayın; çok loader'lı sistemlerde tip uyumsuzluğu hatalarında ilk bakılacak yer budur.
- Redeploy senaryolarında `ThreadLocal.remove()` çağırmayı ve global kayıtlardan (registry) temizlik yapmayı ihmal etmeyin.

## Deserialization ve Güvenlik

### Tanım

Serialization, bir nesneyi byte dizisine çevirip diske/ağa yazma; deserialization ise bu byte'lardan nesneyi geri kurmadır. Java'nın yerleşik `Serializable` mekanizması bunu neredeyse otomatik yapar. Bu kolaylık, aynı zamanda Java'nın **en tehlikeli güvenlik açığı sınıflarından birinin** kaynağıdır.

### Kök neden: neden deserialization tehlikelidir?

Sezgisel beklenti şudur: "Deserialization sadece veriyi geri okur, kod çalıştırmaz." Bu **yanlıştır** ve tüm sorunun özü buradadır. Java deserialization sırasında:

- Nesneler **constructor çağrılmadan** yeniden kurulur (normal kurulum yolu atlanır).
- `readObject`, `readResolve`, `validateObject` gibi özel metotlar **otomatik çağrılır**.
- Deserialize edilen nesne grafiğindeki her sınıfın bu metotları tetiklenebilir.

Asıl tehlike şudur: saldırgan, kötü niyetli ama **geçerli** bir byte akışı oluşturur. Bu akış deserialize edilirken, classpath'te bulunan bazı sınıfların `readObject` metotlarının zincirleme tetiklenmesiyle, saldırganın seçtiği bir işlem gerçekleştirilir. Bu zincirlere **gadget chain** denir. Sonuç çoğu zaman **remote code execution (RCE)** — yani saldırganın sunucuda komut çalıştırmasıdır. Kritik nokta: uygulamanızın kendi kodu hiç "kötü" olmasa bile, classpath'inizdeki popüler bir kütüphane uygun gadget'ları içeriyorsa savunmasız olabilirsiniz.

Kök neden özetle: **güvenilmeyen veriyi deserialize etmek, o veriye kod akışınızın kontrolünü kısmen devretmektir.** Serialization mekanizması tip bilgisini ve davranış tetikleyicilerini verinin içine gömdüğü için, "sadece veri" diye bir şey yoktur.

### Somut örnek

Bir uygulama, HTTP isteğinin gövdesinde gelen base64 kodlu bir Java serialized nesnesini `ObjectInputStream` ile okuyorsa (örneğin bir cache anahtarı, bir cookie veya bir mesaj kuyruğu payload'u olarak), saldırgan bu alana özel hazırlanmış bir gadget chain gönderebilir. Sunucu bunu deserialize ettiği anda saldırganın komutu çalışır. Bu desen, geçmişte çok sayıda yüksek etkili güvenlik olayının temelini oluşturmuştur.

### Yaygın hatalar

- **"İçeriden gelen veri güvenilirdir" varsayımı**: Bir mesaj kuyruğundan, cache'ten veya "iç" bir servisten gelen serialized veriyi güvenilir saymak. Saldırgan bu ara katmanlara erişebiliyorsa senaryo çöker.
- **Sadece tip kontrolü yapmaya çalışmak**: `readObject`'ten sonra tipi kontrol etmek çok geçtir — zarar deserialization sırasında zaten oluşmuştur.
- **Java native serialization'ı uzaktan iletişim formatı olarak kullanmak**: En temel hata. Native serialization asla dış dünyaya açık bir veri formatı olmamalıdır.

### En iyi pratikler

- **En iyi çözüm: güvenilmeyen veriyi hiç deserialize etmeyin.** Native Java serialization yerine JSON, Protocol Buffers gibi veri-odaklı (kod tetiklemeyen) formatlar kullanın ve bunları katı şemalarla parse edin.
- Java serialization'ı zorunlu tutmanız gerekiyorsa, **allow-list tabanlı filtreleme** uygulayın: yalnızca beklediğiniz belirli sınıfların deserialize edilmesine izin verin, gerisini reddedin. Modern Java, `ObjectInputFilter` gibi bir serialization filtreleme mekanizması sunar; bunu sınıf adı bazında bir izin listesiyle yapılandırın.
- Bağımlılıklarınızı güncel tutun; bilinen gadget chain içeren kütüphane sürümlerinden kaçının.
- Hassas sınıflara `serialVersionUID` verin ve deserialization'a girmesini istemediğiniz alanları `transient` yapın; ancak bunların **güvenlik değil, uyumluluk/doğruluk** önlemleri olduğunu unutmayın.

## Kapanış: Ortak İzlek

Bu beş konunun ortak bir teması var: **JVM size soyutlama sunar, ama soyutlama sızar (leaky abstraction).** Bellek otomatik yönetilir — ta ki bir referansı yanlışlıkla tutup sızıntı yaratana kadar. GC nesneleri sizin için toplar — ama neyin canlı olduğunu siz belirlersiniz. Thread'ler paylaşımlı belleğe erişir — ama görünürlük garantilerini JMM kurallarıyla siz sağlamalısınız. Class loader'lar izolasyon verir — ama kimlik ve leak kurallarını bilmezseniz sizi şaşırtır. Serialization nesneleri kolayca geri kurar — ama bu kolaylık güvenilmeyen veri karşısında bir saldırı yüzeyidir.

Uzman seviyesi, bu mekanizmaların "sihir" olmadığını, belirli tasarım kararlarının sonucu olduğunu görmekle başlar. "Nasıl" sorusunu "neden" sorusuyla birleştirdiğinizde, hata mesajlarını ezberlemek yerine kök nedeni okuyabilir; tuning bayraklarını kopyalamak yerine sisteminizin gerçekte ne yaptığını anlayabilirsiniz.
