# C# ve .NET: Async, LINQ, GC, Span, Güvenli Kod ve Deserialization Tuzakları

C# ve onun çalıştığı .NET platformu, üzerine kurulduğu iki temel soyutlama sayesinde hem üretkenlik hem de performans vaat eder: **managed memory** (yönetilen bellek) ve **JIT/AOT derleme**. Kod, doğrudan makine koduna değil önce **IL** (Intermediate Language) denen ara dile derlenir; çalışma anında JIT (Just-In-Time) derleyici bunu native koda çevirir. Bu katman, taşınabilirlik ve güvenlik sağlar ama aynı zamanda performans ve doğruluk açısından anlamanız gereken bir dizi davranışı beraberinde getirir. Bu makale, kıdemli bir mühendisin günlük olarak karşılaştığı en kritik altı konuyu, yüzeysel tarif yerine "neden böyle çalışıyor" ekseninde ele alır.

---

## Async ve await: Eşzamansızlığın Gerçek Mekaniği

### Tanım

`async`/`await`, senkron görünen bir kod yazıp altında eşzamansız (asynchronous) yürütme elde etmenizi sağlayan dil düzeyi bir soyutlamadır. Amaç, uzun süren I/O işlemleri (ağ, disk, veritabanı) sırasında çağıran thread'i bloke etmeden serbest bırakmaktır.

### Kök neden: neden thread bloke etmek pahalı?

Bir web sunucusunda her istek genellikle thread pool'dan bir thread ile karşılanır. Eğer o thread bir veritabanı sorgusunun dönmesini `Thread.Sleep` benzeri senkron biçimde beklerse, thread hiçbir iş yapmadan meşgul kalır. Yük altında thread pool tükenir (**thread pool starvation**) ve sunucu yeni istekleri karşılayamaz hâle gelir. `await`, işte bu beklemeyi "thread'i geri iade ederek" yapar: I/O tamamlanana kadar thread havuza döner, tamamlanınca yürütme kaldığı yerden devam eder.

Bunun altındaki mekanizma bir **state machine**'dir. Derleyici, `async` bir metodu, `await` noktalarında duraklayıp devam edebilen bir durum makinesine dönüştürür. `await` gördüğü yerde, beklenen `Task` henüz tamamlanmamışsa metot bir **continuation** (devam) kaydeder ve kontrolü çağırana bırakır. Task tamamlanınca continuation zamanlanır. Önemli nokta: **async, otomatik olarak yeni bir thread yaratmaz.** Sadece mevcut thread'lerin daha verimli kullanılmasını sağlar. Gerçek paralellik istiyorsanız `Task.Run` gibi araçlarla açıkça CPU işini havuza atmalısınız.

### Somut örnek

```csharp
public async Task<string> KullaniciAdiGetirAsync(int id)
{
    // await noktasında thread serbest kalır; I/O bitince devam eder.
    await using var conn = new SqlConnection(_connectionString);
    await conn.OpenAsync();
    var ad = await conn.QuerySingleAsync<string>(
        "SELECT Ad FROM Kullanicilar WHERE Id = @id", new { id });
    return ad;
}
```

### Tuzaklar ve doğru kullanım

**1. `async void` kullanmayın.** İstisna olarak yalnızca event handler'larda mecburdur. `async void` bir metotta oluşan exception, çağırana `Task` üzerinden iletilemez; doğrudan `SynchronizationContext`'e fırlar ve çoğu zaman uygulamayı çökertir. Yakalanamayan bir hata hâline gelir. Kural: `async` bir metot ya `Task`, `Task<T>` ya da `ValueTask` döndürsün.

**2. Senkron kod içinde `.Result` veya `.Wait()` ile async çağırmayın.** Bu, klasik **deadlock** kaynağıdır. Eski ASP.NET ve masaüstü uygulamalarında `SynchronizationContext` tek bir bağlama devam etmeyi zorlar; ana thread `.Result` ile bloke olurken continuation da aynı thread'e dönmeye çalışır, iki taraf birbirini sonsuza dek bekler. Çözüm: async'i baştan sona yayın ("async all the way").

**3. Kütüphane kodunda `ConfigureAwait(false)`.** Kütüphane yazıyorsanız, continuation'ın çağıranın context'ine dönmesine gerek yoktur. `await foo.ConfigureAwait(false)` yazmak, hem gereksiz context sıçramasını önler hem de yukarıdaki deadlock riskini azaltır. Uygulama kodunda (özellikle UI) ise context'e dönmek isteyebilirsiniz.

**4. `ValueTask`'ı dikkatli kullanın.** Sıklıkla senkron tamamlanan (örneğin cache'ten dönen) sıcak yollarda `ValueTask`, `Task` allocation'ından kaçınarak GC baskısını azaltır. Ama bir `ValueTask` birden fazla kez `await` edilemez, `.Result` ile paralel okunamaz. Yanlış kullanımı sessiz bozulmalara yol açar; emin değilseniz `Task` kullanın.

**5. `CancellationToken`'ı zincir boyunca taşıyın.** İptal edilebilirlik, sonradan eklenen değil baştan tasarlanan bir özelliktir. Token'ı en dış API'den en iç I/O çağrısına kadar geçirin.

---

## LINQ: Deklaratif Sorgu ve Ertelenmiş Yürütme

### Tanım

LINQ (Language Integrated Query), koleksiyonlar, veritabanları ve XML gibi kaynaklar üzerinde deklaratif (ne istediğinizi söyleyen, nasıl yapılacağını söylemeyen) sorgular yazmanızı sağlar. `Where`, `Select`, `GroupBy` gibi operatörler, verinizi dönüştürmenin okunabilir bir yolunu sunar.

### Kök neden: deferred execution (ertelenmiş yürütme)

LINQ'un en çok yanlış anlaşılan davranışı **lazy evaluation**'dır. `IEnumerable<T>` döndüren operatörler (örneğin `Where`, `Select`) çağrıldığı anda hiçbir şey hesaplamaz. Sadece bir sorgu tanımı (bir iterator zinciri) kurarlar. Gerçek yürütme, sorgu **enumerate** edildiğinde olur: bir `foreach`, `ToList()`, `Count()`, `First()` gibi bir terminal işlemde. Bunun nedeni, LINQ'un `yield return` tabanlı iterator'lar üzerine kurulu olmasıdır; her eleman talep edildikçe üretilir.

Bu tasarım güçlüdür (gereksiz hesaplama yapmaz, sonsuz dizileri destekler) ama iki büyük tuzak doğurur.

### Tuzak 1: Çoklu enumeration

```csharp
IEnumerable<Kullanici> aktifler = kullanicilar.Where(k => PahaliKontrol(k));

if (aktifler.Any())              // sorgu 1. kez çalışır
    Console.WriteLine(aktifler.Count());  // sorgu 2. kez çalışır!
foreach (var k in aktifler) { } // sorgu 3. kez çalışır!
```

Aynı `IEnumerable`'ı birden çok kez enumerate ederseniz, `Where` filtresi ve içindeki `PahaliKontrol` her seferinde yeniden çalışır. Kaynak bir veritabanıysa aynı sorgu ağ üzerinden defalarca gider. Çözüm: sonucu bir kez `ToList()` ile materialize edip onun üzerinde çalışmak.

### Tuzak 2: Kapanış (closure) ve gecikmeli değişken yakalama

Sorgu, dışarıdaki bir değişkeni **referansla** yakalar. Sorgu tanımı ile yürütmesi arasında değişken değişirse, yürütme anındaki güncel değeri kullanılır — tanım anındaki değil. Bu, döngü içinde sorgu kurarken beklenmedik sonuç verir.

### IEnumerable vs IQueryable: kritik ayrım

Aynı LINQ sözdizimi iki farklı dünyada çalışır. `IEnumerable<T>` üzerinde operatörler **delegate** (derlenmiş kod) alır ve bellekte, LINQ-to-Objects olarak yürür. `IQueryable<T>` (örneğin Entity Framework) ise **expression tree** alır: sorgunuz bir veri yapısına çevrilir, provider bunu analiz edip SQL'e tercüme eder ve veritabanında çalıştırır.

Bu ayrım performans açısından hayatidir. Şu satır tehlikelidir:

```csharp
var sonuc = db.Kullanicilar.AsEnumerable().Where(k => k.Yas > 30).ToList();
```

`AsEnumerable()` çağrısı, sorguyu erken bir noktada LINQ-to-Objects'e düşürür. Sonuç: `Where` filtresi SQL'e çevrilmez, **tüm tablo** belleğe çekilip filtre C# tarafında uygulanır. Doğru yol, `AsEnumerable`'ı sona bırakıp filtreyi veritabanına ittirmektir. EF ile çalışırken, hangi operatörlerin SQL'e çevrilebildiğine dikkat edin; çevrilemeyen bir metot kullanmak ya bir çalışma zamanı hatasına ya da sessiz client-side evaluation'a yol açar.

### En iyi pratikler

- Sorgu sonucunu birden çok kez kullanacaksanız bir kez materialize edin.
- Sıcak yollarda çok küçük koleksiyonlar için LINQ yerine düz `for` döngüsü, delegate allocation ve iterator maliyetini elediğinden daha hızlı olabilir. Ama okunabilirliği erken feda etmeyin; önce ölçün.
- `Select(...).Where(...)` sırası önemlidir; filtreyi mümkün olduğunca öne alarak sonraki adımların işleyeceği eleman sayısını azaltın.

---

## Garbage Collector (GC): Otomatik Bellek Yönetiminin Bedeli ve Gücü

### Tanım

.NET, belleği elle serbest bırakmanıza gerek kalmadan, artık erişilemeyen (unreachable) nesneleri otomatik olarak toplayan bir **garbage collector** kullanır. Bu, use-after-free ve çoğu bellek sızıntısı sınıfını ortadan kaldırır.

### Kök neden: generational ve mark-sweep-compact

.NET GC'si **generational** (kuşak bazlı) bir toplayıcıdır. Temel gözlem şudur: çoğu nesne ya çok kısa ömürlüdür (bir metot içinde doğar ve ölür) ya da çok uzun ömürlüdür. GC bu nesneleri kuşaklara ayırır: Gen 0 (yeni), Gen 1 (bir toplamayı atlatmış), Gen 2 (uzun ömürlü). GC en sık Gen 0'ı toplar; çünkü orada ölü nesne bulma olasılığı en yüksek ve maliyet en düşüktür. Bir Gen 0 toplaması hayatta kalan nesneleri Gen 1'e terfi ettirir.

Toplama sırasında GC, kök referanslardan (stack, statik alanlar, register'lar) ulaşılabilen nesneleri işaretler (**mark**), ulaşılamayanları geri kazanır (**sweep**) ve bölünmeyi azaltmak için genellikle belleği sıkıştırır (**compact**). Sıkıştırma, referansların hareket etmesi demektir; bu yüzden managed nesnenin adresine güvenip pointer tutamazsınız (bkz. `fixed`/pinning).

Büyük nesneler (eşik değerin üzerindekiler, tipik olarak ~85 KB) ayrı bir **LOH** (Large Object Heap) alanında tutulur. LOH varsayılan olarak sıkıştırılmaz; bu yüzden büyük dizileri sık sık ayırıp bırakmak LOH parçalanmasına ve bellek büyümesine yol açabilir.

### Tuzaklar ve neden'leri

**1. `IDisposable` ve unmanaged kaynaklar.** GC yalnızca managed bellekle ilgilenir. Dosya handle'ları, socket'ler, veritabanı bağlantıları gibi işletim sistemi kaynaklarını GC bilmez. Bunları `using` ile deterministik biçimde serbest bırakmalısınız. `Dispose` çağırmayı unutmak, GC bir finalizer çalıştırana kadar (belki hiç) kaynağın sızmasına yol açar.

**2. Finalizer'lar pahalıdır.** Finalizer'ı olan bir nesne toplanırken iki GC döngüsü gerektirir ve bir finalizer kuyruğundan geçer. Modern kodda genellikle finalizer yerine `SafeHandle` tercih edilir. Elle finalizer yazmak nadiren doğru cevaptır.

**3. Gizli sızıntılar.** GC olmasına rağmen bellek sızdırabilirsiniz — çünkü sızıntı "hâlâ erişilebilen ama artık gereksiz" nesnelerdir. Klasik kaynak: bir statik event'e abone olup unsubscribe etmemek. Event, dinleyiciyi referansla tutar; dinleyici asla toplanmaz. Uzun ömürlü cache'ler, statik koleksiyonlar da aynı sınıftadır.

**4. Server GC vs Workstation GC.** Sunucu iş yüklerinde Server GC, her CPU çekirdeği için ayrı heap ve toplama thread'i kullanarak throughput'u artırır ama daha fazla bellek ve CPU tüketir. Latency'ye duyarlı senaryolarda GC modunu ve pause davranışını iş yükünüze göre yapılandırmanız gerekir. Doğru seçim iş yükünüzü ölçmeden yapılamaz.

### En iyi pratikler

- Sıcak yollarda gereksiz allocation'dan kaçının; GC'yi en iyi optimizasyon, çöp üretmemektir.
- `IDisposable` implemente eden her şeyi `using` ile sarın.
- Bellek profili çıkarın; "sanırım sızdırıyor" yerine bir memory profiler ile hangi nesnelerin köke tutulduğunu görün.

---

## Span<T> ve Bellek: Kopyalamadan Yüksek Performans

### Tanım

`Span<T>` ve `ReadOnlySpan<T>`, bir bellek bölgesine — managed dizi, stack üzerinde ayrılmış bir tampon veya unmanaged bellek — **kopya olmadan** güvenli, tipli bir pencere sunan yapılardır. Bir dizinin bir dilimini (slice), yeni bir dizi ayırmadan temsil ederler.

### Kök neden: allocation ve kopyalamayı elemek

Klasik string/array işlemlerinde her `Substring`, her dizi dilimi yeni bir tahsisat üretir. Bir parser veya serileştirici, girdiyi işlerken binlerce küçük geçici string yaratabilir; bunların hepsi Gen 0 çöpü olur ve GC baskısı doğurur. `Span<T>`, aynı bellek üzerinde bir "görünüm" oluşturarak bu kopyaları tamamen ortadan kaldırır. Örneğin `str.AsSpan(5, 10)`, karakterleri kopyalamaz; yalnızca başlangıç ve uzunluğu tutan bir pencere döndürür.

`Span<T>`'ın güvenliği bir **ref struct** olmasından gelir. Ref struct'lar yalnızca stack'te yaşayabilir. Bu kısıt kasıtlıdır: eğer bir span heap'e (bir sınıfın alanına) veya bir closure'a kaçabilseydi, işaret ettiği stack belleği veya taşınabilir managed bellek geçersiz olabilirdi. Derleyici bu kaçışları derleme zamanında engeller.

### Somut örnek

```csharp
// Bir tarih string'ini kopya üretmeden ayrıştırma
ReadOnlySpan<char> s = "2026-07-05".AsSpan();
int yil  = int.Parse(s.Slice(0, 4));
int ay   = int.Parse(s.Slice(5, 2));
int gun  = int.Parse(s.Slice(8, 2));
// Hiç Substring, hiç ara string tahsisatı yok.
```

Küçük tamponlar için `stackalloc` ile `Span` birleşimi, heap'e hiç dokunmadan geçici alan sağlar:

```csharp
Span<byte> tampon = stackalloc byte[256]; // stack'te, GC dışı
```

### Tuzaklar

**1. `stackalloc` boyutunu sabitleyin.** Kullanıcı girdisine bağlı büyüklükte `stackalloc` yapmak **stack overflow** riskidir. Stack sınırlıdır (tipik olarak birkaç yüz KB — thread'e ve platforma göre değişir). Küçük ve öngörülebilir boyutlar için kullanın; büyük veya değişken boyutta `ArrayPool<T>` düşünün.

**2. `Span<T>`'ı async metotta yaşatamazsınız.** Ref struct olduğu için `await` sınırını geçemez; çünkü async state machine heap'e kaydedilir. Async gereken yerde `Memory<T>`/`ReadOnlyMemory<T>` kullanın — bunlar heap'te yaşayabilir ve gerektiğinde `.Span` ile span'e dönüştürülür.

**3. Ömür (lifetime) kuralları.** Bir `Span`, işaret ettiği tampondan daha uzun yaşamamalıdır. `stackalloc` ile aldığınız bir span'i metottan döndürmek geçersizdir; derleyici çoğu durumu yakalar ama mimarinizi span ömürlerine göre kurmanız gerekir.

### En iyi pratikler

- Sıcak, allocation-yoğun yollarda (parsing, serialization, buffer işleme) `Span`'e geçin; ama önce profilleyerek gerçekten darboğaz olduğunu doğrulayın.
- Yeniden kullanılabilir büyük tamponlar için `ArrayPool<T>.Shared` ile ödünç alıp iade edin; iade etmeyi `try/finally` ile garantileyin.

---

## Güvenli Kod: Managed Ortamda da Tehdit Yüzeyi Vardır

### Tanım

Managed bellek, buffer overflow ve use-after-free gibi bütün bir hata sınıfını büyük ölçüde ortadan kaldırır. Ama "memory-safe" olmak "güvenli" olmak demek değildir. Uygulama düzeyi güvenlik açıkları — injection, zayıf kriptografi, hassas veri sızıntısı — dile aldırmaz.

### SQL injection ve parametrizasyon

En yaygın ve en önlenebilir açık. String birleştirerek SQL kurmak felakettir:

```csharp
// ASLA: kullanıcı girdisi doğrudan sorguya giriyor
var q = "SELECT * FROM Users WHERE Name = '" + ad + "'";
```

Buradaki kök neden, kod (SQL) ile verinin (kullanıcı girdisi) aynı string içinde karışmasıdır. Saldırgan `ad` alanına SQL sözdizimi yazarak sorgunun anlamını değiştirir. Çözüm **parametrize sorgu**dur: veriyi sorgudan ayrı bir kanaldan gönderirsiniz, veritabanı onu asla kod olarak yorumlamaz.

```csharp
cmd.CommandText = "SELECT * FROM Users WHERE Name = @ad";
cmd.Parameters.AddWithValue("@ad", ad);
```

Aynı ilke komut çalıştırma (command injection), yol birleştirme (path traversal) ve şablon motorları için de geçerlidir: **girdiyi asla koda karıştırma.**

### Kriptografi: kendi şifrenizi yazmayın

- Parola saklarken şifreleme değil, tuzlanmış (salted) ve yavaş bir **password hashing** algoritması kullanın. Genel amaçlı hızlı hash'ler (parola için) yanlıştır; amaç bilerek yavaş olmaktır.
- Rastgele değer üretirken güvenlik amaçlıysa `System.Random` değil, kriptografik güvenli üreteci (`RandomNumberGenerator`) kullanın. `System.Random` tahmin edilebilirdir.
- String karşılaştırmalarında gizli/token karşılaştırırken **constant-time** karşılaştırma kullanın; erken çıkış yapan `==`, zamanlama (timing) sızıntısı verebilir.

### Hassas veri ve loglar

Managed bellekte `string` **immutable**'dır; bir parolayı string olarak tuttuğunuzda onu güvenilir biçimde sıfırlayamazsınız ve GC bir kopyasını bellekte bırakabilir. Aşırı hassas senaryolarda `SecureString` veya kullanır kullanmaz temizlenen `byte[]`/`Span<byte>` tercih edilir. Ayrıca en yaygın gerçek sızıntı basittir: hassas veriyi (token, parola, PII) loga yazmak. Loglama katmanında maskeleme uygulayın.

### En iyi pratikler

- Girdiyi sınırda doğrulayın (allowlist tercih edin, denylist değil).
- Bağımlılıklarınızı güncel tutun; bilinen açıklar en çok güncel olmayan paketlerden gelir. Bir tedarik zinciri (supply chain) taraması, transitive bağımlılıklardaki riskleri yüzeye çıkarır.
- En az yetki (least privilege) ilkesini veritabanı kullanıcısından dosya izinlerine kadar uygulayın.

---

## Deserialization Tuzağı: En Sinsi .NET Güvenlik Sorunu

### Tanım

**Deserialization**, dışarıdan gelen bir veri akışını (JSON, XML, ikili) tekrar nesnelere dönüştürme işlemidir. Tehlike, verinin yalnızca "veri" olmaktan çıkıp, hangi tiplerin oluşturulacağını ve hangi kodun çalışacağını **etkileyebilmesinden** doğar.

### Kök neden: neden bir deserializer kod çalıştırabilir?

Bazı serileştiriciler, akışın içine gömülü **tip bilgisine** güvenir. Yani veri yalnızca "şu alanlar şu değerlerde" demez, "şu .NET tipini oluştur" da diyebilir (type name handling / polymorphic deserialization). Deserializer bu tipi yansıma (reflection) ile örnekleyip alanlarını doldurduğunda, bazı tiplerin oluşturulması veya alanlarının atanması yan etkiler tetikler — bir setter, bir constructor, bir `IDisposable`, dosya/işlem başlatan bir nesne. Saldırgan, bu tipleri zincirleyerek (**gadget chain**) deserializer'ı, hiç niyet etmediğiniz bir kodu çalıştırmaya kandırabilir. Sonuç, en kötü hâlde **remote code execution**'dır.

Kritik içgörü: açık, çoğu zaman sizin kodunuzda değil, deserializer'ın "güvenilmeyen veriye tip yaratma yetkisi vermesindedir". Yani hata mesajınız temiz görünürken bile mimari yanlıştır.

### Tarihsel örnek: tehlikeli formatlayıcılar

.NET'in eski `BinaryFormatter` sınıfı bu sorunun kitap örneğidir. Güvenilmeyen veriyle kullanıldığında güvenli hâle getirilmesi pratikte mümkün olmadığı için Microsoft bunu resmen tehlikeli ilan etmiş, kullanımını uyarılarla işaretlemiş ve modern .NET sürümlerinde varsayılan olarak devre dışı bırakma/kaldırma yönünde ilerlemiştir. Aynı ruhla, bir tipi akıştan okuyup türünü verinin belirlemesine izin veren her mekanizma (bazı `SoapFormatter`, `NetDataContractSerializer` ve gevşek yapılandırılmış JSON senaryoları dâhil) aynı sınıfa girer.

> Dürüstlük notu: Bu sorunla ilişkili spesifik CVE numaralarını buraya güvenerek yazamam; kavramsal olarak sınıf "insecure deserialization" (OWASP tarafından uzun süre ilk on riskten biri olarak listelenmiştir) başlığı altındadır. Belirli bir kütüphane sürümünün açığını doğrulamanız gerekiyorsa resmî güvenlik danışmanlarına (advisory) bakın.

### JSON tarafındaki tuzak

Modern kodda `System.Text.Json` varsayılan olarak polymorphic type resolution'ı akıştan gelen tip adına göre yapmaz; bu güvenli bir varsayılandır. Ama:

- `Newtonsoft.Json` (Json.NET) kullanıp `TypeNameHandling`'i `Auto`/`All`/`Objects` gibi bir değere açarsanız, aynı "veri tip seçiyor" tehlikesini geri getirirsiniz. Bu ayarı güvenilmeyen girdiyle **açmayın**; açmanız gerekiyorsa sıkı bir `SerializationBinder` ile hangi tiplerin oluşturulabileceğini beyaz listeyle sınırlayın.
- `System.Text.Json`'da polymorphic deserialization'ı elle etkinleştirdiğinizde de aynı disiplin geçerlidir: izin verilen tip kümesini açıkça, kapalı bir liste olarak tanımlayın.

### Doğru yaklaşım ve savunma katmanları

1. **Güvenilmeyen veriyi tip-taşıyan formatlarla deserialize etmeyin.** Girdiyi, önceden bildiğiniz somut ve basit bir **DTO** (Data Transfer Object) tipine bağlayın. Deserializer'ın türü seçmesine değil, sizin sabit türünüze veri akmasına izin verin.
2. **Şema/sözleşme doğrulaması.** Deserialize'dan sonra iş kuralı doğrulaması yapın; tip bağlama tek başına doğrulama değildir.
3. **En az yetki.** Deserialization yapan servis, tehlikeli işlemler (dosya, süreç başlatma) için gereksiz yetkiye sahip olmasın; bir gadget zinciri bile sınırlı bir bağlamda daha az zarar verir.
4. **Tip beyaz listesi.** Polymorphism gerçekten gerekliyse, oluşturulabilir tipleri kapalı bir izin listesiyle sınırlayın; asla "gelen ne derse o tip" demeyin.
5. **Girdi boyutu ve derinlik limitleri.** Aşırı büyük veya derin iç içe yapılar bir **DoS** (denial of service) vektörüdür; deserializer'ın derinlik/uzunluk sınırlarını yapılandırın.

### Yaygın hatalar

- "İçeriden gelen veri güvenlidir" varsayımı. Bir mesaj kuyruğundan, cache'ten veya başka bir servisten gelen veri de saldırganın kontrolüne geçmiş olabilir; güven sınırını (trust boundary) net çizin.
- Bir formatlayıcıyı "hızlı ve pratik" diye seçip güvenilmeyen veriyle beslemek. Format seçimini tehdit modeliyle birlikte yapın.
- Type handling'i debug sırasında açıp production'da kapatmayı unutmak.

---

## Kapanış: Ortak İlke

Bu altı konunun altında tek bir mühendislik disiplini yatar: **soyutlamanın altında ne olduğunu bilmek.** `await` bir thread yaratmaz; LINQ hemen çalışmaz; GC unmanaged kaynağı bilmez; `Span` stack'ten kaçamaz; managed bellek uygulama açıklarını kapatmaz; ve bir deserializer güvenilmeyen veriye tip yaratma yetkisi verdiğinde artık yalnızca veri okumaz, kod çalıştırabilir. Kıdemli mühendisliğin özü, kolaylık sağlayan bu soyutlamaları körlemesine kullanmak değil, sınırlarını ve bedellerini bilerek — ve ölçerek — kullanmaktır.
