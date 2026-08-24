# Kotlin / Android Güvenliği: Null Safety Bypass, Coroutine Güvenlik Tuzakları ve JNI Interop

## Giriş ve Kapsam

Kotlin, Android platformunun birinci sınıf dili olmasına rağmen çalışma zamanında hâlâ **JVM bytecode**'una derlenir ve dev bir Java ekosistemiyle iç içe (interop) çalışır. Kotlin'in derleme zamanı garantileri (özellikle `null` güvenliği) güçlüdür; ancak bu garantilerin **çalışma zamanında (runtime)** her zaman geçerli olmadığı sınır bölgeleri vardır. Bu makale üç kritik boşluğu inceler:

1. **Null safety bypass**: Kotlin'in `null` güvenliğinin Java interop, platform tipleri, reflection ve serileştirme kanallarıyla nasıl delindiği.
2. **Coroutine güvenlik tuzakları**: Yapısal eşzamanlılık (structured concurrency) ihlalleri, context sızıntıları, iptal (cancellation) güvenliği ve veri yarışları.
3. **JNI / native köprü riskleri**: Kotlin/Java'dan native koda (C/C++) geçişte oluşan bellek güvenliği ve güven sınırı (trust boundary) sorunları.

Amaç, mekanizmayı **anlamak** ve buna karşı **savunma/tespit** kurmaktır; canlı saldırı talimatı değildir.

---

## 1. Null Safety Bypass

### 1.1 Tanım ve Kök Neden

Kotlin tip sistemi, tipleri **nullable** (`String?`) ve **non-null** (`String`) olarak ayırır. Derleyici, non-null bir değişkene `null` atanmasını engeller. Bu, `NullPointerException` (NPE) sınıfının büyük çoğunluğunu derleme zamanında ortadan kaldırır. Ancak bu güvence, **yalnızca tamamen Kotlin dünyası içinde** ve **derleyicinin gördüğü** sınırlar içinde geçerlidir. Kök neden şudur: JVM bytecode seviyesinde nullability yoktur; non-null bir tip, çalışma zamanında pekâlâ `null` referans tutabilir. Kotlin bunu ancak stratejik yerlere yerleştirdiği **çalışma zamanı kontrolleriyle** (intrinsic checks) telafi eder.

### 1.2 Platform Tipleri (Platform Types)

Java'dan gelen bir değer, Kotlin tarafında `@Nullable`/`@NonNull` gibi annotation'larla işaretlenmemişse **platform tipi** olarak görülür ve `String!` şeklinde gösterilir. Platform tipi, "derleyici burada garanti veremiyorum, sorumluluğu sana bırakıyorum" demektir. Geliştirici onu non-null olarak kullanırsa ve değer gerçekte `null` ise, çalışma zamanında NPE fırlar.

```kotlin
// Java tarafı: public String getName() { return null; }
val user = javaService.getName()   // tipi String! (platform tipi)
val length = user.length           // runtime'da NPE — derleyici uyarı VERMEZ
```

Bu, "null safety bypass"in en yaygın ve masum görünen biçimidir: Kotlin'in vaadi burada sessizce askıya alınır.

### 1.3 Bilinçli Delme Mekanizmaları

Kotlin, non-null sözünü **bilerek** kırmanın yollarını sunar. Bunlar bug değildir; ama kötüye kullanıldıklarında güvenlik ve kararlılık sorunlarına dönüşür:

- **`!!` (not-null assertion operatörü)**: "Bu değer `null` değil, garanti ediyorum" der. Yanılırsa NPE fırlatır. Kod tabanında yaygın `!!` kullanımı, tip sisteminin sağladığı güvenliği elle iptal etmek demektir.
- **`lateinit var`**: Non-null bir property'nin başlatılmasını erteler. İlk kullanımından önce atanmazsa `UninitializedPropertyAccessException` fırlar. Saldırgan kontrollü bir akış (örneğin bir Activity'nin beklenmeyen sırada yaşam döngüsü olayları) `lateinit` alanını başlatılmamış durumda yakalayabilir.
- **`Unsafe` / reflection**: Reflection ile private ya da non-null alanlara `null` yazmak mümkündür. `field.isAccessible = true` sonrası `field.set(obj, null)`, tip sistemini tamamen atlar.
- **Serileştirme / deserialize**: Gson, Jackson gibi kütüphaneler nesneyi genellikle constructor'ı **çağırmadan** (veya `Unsafe` ile) üretir; JSON'da eksik bir alan, non-null Kotlin property'sini `null` bırakabilir. Bu, "geçerli görünen ama tip sözleşmesini ihlal eden" nesneler yaratır — güvenilmeyen girdiden (untrusted input) gelen deserialize işlemlerinde ciddi bir risktir.

### 1.4 Güvenlik Etkisi

Null safety bypass'in tehlikesi çift yönlüdür:

- **Kararlılık/DoS**: Beklenmeyen `null`, kritik yolda NPE'ye ve dolayısıyla çökmeye/servis reddine yol açabilir.
- **Mantık atlatma**: Bir yetki kontrolü non-null bir "kullanıcı" nesnesine dayanıyorsa ve deserialize/reflection ile o nesne kısmen `null` alanlarla üretilirse, `if (user.role != null && user.role == ADMIN)` gibi kontroller beklenmedik dallara girebilir. Yani null, doğrudan bir **authorization bypass** vektörüne dönüşebilir.

### 1.5 Doğru Kullanım ve Tuzaklar

- Java API'lerini `@Nullable`/`@NonNull` (JSpecify, Android'in androidx.annotation'ları) ile işaretleyin; platform tipini nullable-bilinçli gerçek tiplere dönüştürün.
- `!!` yerine `?.`, `?:` (Elvis) ve `requireNotNull(x) { "anlamlı mesaj" }` kullanın. `requireNotNull`/`checkNotNull` en azından **anlamlı** ve **niyetli** bir hata üretir.
- Deserialize edilen nesnelerde **giriş doğrulaması (input validation)** yapın; tip sisteminin non-null vaadine güvenmeyin. Deserialize edilen sınıfların invariant'larını bir `init` bloğunda veya bir validasyon katmanında zorunlu kılın.
- **Yaygın hata**: Detekt/lint kurallarını `!!` için sessize almak. Bunun yerine `!!` sayısını bir kod kalitesi metriği olarak izleyin.

---

## 2. Coroutine Güvenlik Tuzakları

### 2.1 Tanım ve Kök Neden

Kotlin Coroutines, asenkron kodu senkron görünümlü yazmayı sağlar. Merkezinde **structured concurrency** (yapısal eşzamanlılık) vardır: her coroutine bir `CoroutineScope` altında yaşar; scope iptal edilirse çocukları da iptal olur. Güvenlik tuzaklarının kök nedeni, bu yapının **elle bozulabilir** olması ve iptal (cancellation) ile bağlamın (context) doğru yönetilmemesidir. Coroutine hataları çoğunlukla "sessiz" tehlikelerdir: derleme geçer, testler geçebilir, ama üretimde sızıntı/veri yarışı olarak ortaya çıkar.

### 2.2 GlobalScope ve Structured Concurrency İhlali

`GlobalScope`, uygulamanın ömrü boyunca yaşayan, hiçbir yaşam döngüsüne bağlı olmayan bir scope'tur.

```kotlin
// TUZAK: yaşam döngüsüne bağlı değil
GlobalScope.launch {
    val token = fetchSecretToken()
    updateUi(token)   // Activity çoktan yok edilmiş olabilir
}
```

Sorunlar: Activity/Fragment yok edilse bile coroutine çalışmaya devam eder → **context leak** (yok edilmiş Activity'ye referans tutulur, bellek sızıntısı) ve yarış hâlinde eski/yeni ekranların karışması. Güvenlik açısından, iptal edilmeyen bir arka plan işi hassas veriyi (token, PII) beklenenden uzun süre bellekte tutar ve yanlış (belki artık kilitlenmiş) bir UI bağlamına yazabilir.

**Doğru kullanım**: Android'de `viewModelScope`, `lifecycleScope`, `repeatOnLifecycle` kullanın. Bu scope'lar yaşam döngüsüyle otomatik iptal edilir.

### 2.3 Cancellation (İptal) Güvenliği

Coroutine iptali **kooperatif**tir: iptal, çalışan koda bir `CancellationException` olarak yansır, ancak yalnızca **suspend noktalarında** kontrol edilir. İki büyük tuzak:

**a) Yutulmuş CancellationException**: Genel bir `try/catch (e: Exception)`, iptal sinyalini de yakalar ve yutar. Bu, structured concurrency'yi bozar — coroutine iptal edilmesi gerekirken çalışmaya devam eder.

```kotlin
try {
    doSuspendingWork()
} catch (e: Exception) {   // TUZAK: CancellationException'ı da yakalar
    log(e)
}
```

Doğrusu: `CancellationException`'ı yeniden fırlatın (`if (e is CancellationException) throw e`) veya daha spesifik tipler yakalayın. `kotlinx.coroutines` `runCatching` kullanımında da aynı tuzak vardır — `runCatching` her `Throwable`'ı yakalar.

**b) İptal sonrası temizlik (cleanup)**: İptal olduğunda `finally` bloğu çalışır, ancak `finally` içinde tekrar suspend fonksiyon çağrılırsa (örneğin bir kaynağı serbest bırakmak için ağ çağrısı) bu, coroutine iptal edildiği için hemen başarısız olur. Kritik temizliği (dosya/kilit/şifreleme anahtarı serbest bırakma) `withContext(NonCancellable) { ... }` içinde yapın — ama bunu **yalnızca** kısa, garanti gereken temizlik için kullanın; genel kaçış kapısı olarak değil.

Güvenlik etkisi: Yarım kalan işlemler tutarsız duruma yol açabilir; bir kilit ya da geçici şifre çözülmüş veri temizlenmeden kalabilir.

### 2.4 Coroutine Context Leak ve Dispatcher Yanlış Kullanımı

`CoroutineContext`, dispatcher, job ve `ThreadLocal` benzeri elemanları taşır. Tuzaklar:

- **ThreadLocal ile güvenlik bağlamı taşıma**: Java'da yaygın olan `ThreadLocal` tabanlı güvenlik bağlamları (örneğin oturum/kullanıcı kimliği) coroutine'ler thread'ler arasında serbestçe atlayabildiği için **kırılır**. Bir suspend noktasından sonra coroutine başka bir thread'de sürebilir ve `ThreadLocal` yanlış kullanıcının bağlamını gösterebilir — bu, ciddi bir **yetki karışması (identity confusion)** riskidir. Çözüm: bağlamı `ThreadContextElement` ile senkronize etmek veya güvenlik kimliğini açıkça parametre olarak taşımak.
- **Yanlış dispatcher seçimi**: Ağ/dosya (blocking) işleri `Dispatchers.IO`'da; CPU-yoğun işler `Dispatchers.Default`'ta çalışmalı. `Dispatchers.Main`'de bloklama, ANR (Application Not Responding) üretir. Bir suspend fonksiyonun hangi dispatcher'ı beklediğini yanlış varsaymak, hem performans hem güvenlik (zamanlama yan kanalları, ANR ile DoS) sonuçları doğurur.

### 2.5 Mutable Paylaşımlı Durum ve Veri Yarışları

Coroutine kodu "senkron görünür" ama gerçekte eşzamanlıdır. Farklı coroutine'ler aynı `MutableList`/`var`'a suspend noktaları arasında erişirse **data race** oluşur. Kotlin'in tip sistemi bunu yakalamaz.

- Paylaşımlı durumu `Mutex` (`mutex.withLock { }`), atomikler veya tek bir aktör (channel/actor) ile serileştirin.
- Değişmez (immutable) veri ve `StateFlow`/`SharedFlow` tercih edin.
- **Yaygın hata**: `@Volatile`'ın veya `synchronized`'ın coroutine'lerde yeterli olduğunu sanmak — `synchronized` bloğu içinde suspend edilemez ve suspend noktaları etrafındaki mantık yine yarışabilir.

### 2.6 Flow ve Hata Yayılımı

`Flow` içinde `try/catch` yerine `catch` operatörü kullanılmalı; yukarı akış (upstream) hatalarını `catch` yakalar, downstream'i etkilemez. Ham `try/catch`, yukarıdaki cancellation-yutma tuzağına düşer. Ayrıca `flowOn` ile context değiştirirken üretici (emitter) tarafının hangi dispatcher'da çalıştığını doğru anlamak gerekir.

---

## 3. JNI / Native Interop Riskleri

### 3.1 Tanım ve Kök Neden

**JNI (Java Native Interface)**, Kotlin/Java kodunun C/C++ ile yazılmış native kütüphanelerle (`.so` dosyaları) konuşmasını sağlar. Android'de bu genellikle NDK ile yapılır. Kök neden: JNI sınırı, **güvenli (managed) bellek dünyası** ile **güvensiz (manual) bellek dünyası** arasındaki bir **güven sınırıdır**. Kotlin'in null güvenliği, tip güvenliği ve otomatik bellek yönetimi bu sınırın **öte tarafında geçerli değildir**. Native koddaki bir hata, JVM'in tüm güvenlik garantilerini çökertebilir.

### 3.2 Bellek Güvenliği Sorunları

Native kod C/C++ olduğu için klasik bellek güvenliği açıklarına açıktır ve bunlar Kotlin katmanından **görünmez**:

- **Buffer overflow / out-of-bounds**: JNI ile Kotlin'den geçirilen bir `ByteArray`, native tarafta `GetByteArrayElements`/`GetArrayLength` ile okunur. Uzunluk kontrolü native tarafta yanlış yapılırsa taşma olur. Kotlin tarafındaki tip güvenliği burada koruma sağlamaz.
- **Use-after-free / dangling pointer**: Native kod, bir Java nesnesine `GlobalRef` tutmadan yerel referansı (local reference) saklarsa, JNI çağrısı bittiğinde referans geçersizleşir; sonraki kullanım tanımsız davranıştır.
- **Referans tablosu taşması**: Her JNI local reference'ı serbest bırakılmazsa (`DeleteLocalRef`) referans tablosu dolar ve çökme olur — uzun döngülerde klasik hata.

### 3.3 Null ve Tip Sözleşmesinin İhlali

JNI, Java/Kotlin'in tip ve null sözleşmelerini **zorlamaz**. Native kod, non-null olması beklenen bir alana `null` (`NULL` jobject) döndürebilir veya yanlış tipte bir nesne teslim edebilir. Kotlin tarafı bunu non-null varsaydığında, 1.2'de anlatılan bypass'in native kaynaklı bir çeşidi oluşur. Ayrıca JNI'de bir **pending exception** temizlenmeden (`ExceptionClear`) başka JNI çağrısı yapmak tanımsız davranışa yol açar; bu, hataların sessizce yutulup tutarsız duruma dönüşmesine neden olur.

### 3.4 Güven Sınırı ve Girdi Doğrulama

En önemli ilke: **native koda giren her veri untrusted kabul edilmelidir.** Kotlin tarafında yapılan doğrulamalar (uzunluk, format, sınır) native tarafta **tekrarlanmalıdır**, çünkü:

- Native fonksiyon başka çağıranlar tarafından da (reflection, başka `.so`, doğrudan) çağrılabilir.
- Managed tarafta yapılan kontrol, native tarafın gördüğü ham belleği garanti etmez.

`.so` kütüphaneleri ayrıca **tersine mühendisliğe** açıktır; içine gömülü sırlar (API anahtarları, şifreleme anahtarları) "gizlenmiş" değil sadece "biraz zorlaştırılmış" sayılmalıdır. Native tarafa sır gömmek bir güvenlik önlemi değil, olsa olsa hafif bir engeldir.

### 3.5 Doğru Kullanım ve Tuzaklar

- Native tarafta **tüm** dizi/string uzunluklarını yeniden doğrulayın; `GetArrayLength` sonucuna güvenerek sabit tampon kullanmayın.
- Uzun ömürlü Java referanslarını `NewGlobalRef`/`DeleteGlobalRef` ile yönetin; local referansları döngülerde açıkça silin.
- Her JNI çağrısından sonra `ExceptionCheck`/`ExceptionOccurred` ile hata kontrolü yapın ve gerekirse temizleyin.
- Native koddan dönen değerleri Kotlin tarafında **nullable** olarak modelleyin (`external fun getData(): ByteArray?`), non-null varsaymayın.
- **Yaygın hata**: Native tarafı "hızlı yol" sanıp güvenlik kontrollerini yalnızca Kotlin'de bırakmak. Güven sınırının her iki yakasında da doğrulama gerekir.

---

## 4. Tespit ve Savunma (Genel Çerçeve)

### 4.1 Statik Analiz

- **Android Lint** ve **Detekt**: `!!` kullanımı, `GlobalScope` kullanımı, yakalanan `CancellationException`, platform tipi güvenli olmayan kullanımlar için kurallar tanımlayın. Detekt'in coroutine kuralları (örn. `GlobalCoroutineUsage`, `SuspendFunWithFlowReturnType`) özellikle değerlidir.
- **Nullability annotation zorunluluğu**: Java sınırında `@Nullable`/`@NonNull` denetimini CI'da zorunlu kılın (örn. NullAway benzeri araçlar veya JSpecify tabanlı denetim).
- **Native tarafı**: C/C++ için derleyici uyarılarını `-Wall -Wextra` ile açın; statik analizciler (clang-tidy, cppcheck) ve sanitizer'ları (ASan/UBSan) debug/test build'lerinde çalıştırın.

### 4.2 Çalışma Zamanı Sertleştirme

- **StrictMode** (Android): ana thread'de disk/ağ işlemlerini ve bazı sızıntıları geliştirme sırasında yakalar.
- **LeakCanary**: context leak'leri (özellikle GlobalScope/lifecycle uyumsuzluğu kaynaklı) otomatik tespit eder.
- **AddressSanitizer / HWASan**: native bellek hatalarını çalışma zamanında yakalamak için NDK build'lerinde etkinleştirin.

### 4.3 Mimari İlkeler

- Yaşam döngüsüne bağlı scope'ları (`viewModelScope`, `lifecycleScope`) standart yapın; `GlobalScope`'u yasak listeye alın.
- Güvenlik/kimlik bağlamını `ThreadLocal` yerine açık parametre veya `CoroutineContext` elemanı olarak taşıyın.
- Güven sınırlarını (deserialize girişi, JNI girişi, IPC/Intent girişi) haritalayın ve her birinde bağımsız doğrulama katmanı kurun.
- Native kodu minimumda tutun; kritik güvenlik mantığını yalnızca "gizlemek için" native'e taşımayın.

---

## Sonuç

Kotlin'in derleme zamanı güvencesi güçlüdür ama **mutlak değildir**. Null safety, yalnızca derleyicinin gördüğü saf-Kotlin sınırları içinde gerçektir; Java interop, platform tipleri, reflection, deserialize ve JNI bu sınırı deler. Coroutine'ler, "senkron görünen eşzamanlı" doğaları nedeniyle sessiz sızıntı, iptal-yutma ve veri yarışı tuzakları taşır ve structured concurrency ancak elle korunduğu sürece anlamlıdır. JNI sınırı ise Kotlin'in tüm garantilerinin dışında kalan bir güven sınırıdır ve her iki yakada da bağımsız doğrulama ister. Savunmanın özü tek cümlede: **tip sisteminin ve dilin verdiği sözlere güven, ama her güven sınırında yeniden doğrula.**
