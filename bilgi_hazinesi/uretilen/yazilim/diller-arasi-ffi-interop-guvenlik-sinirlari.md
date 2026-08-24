# Diller Arası FFI/Interop Güvenlik Sınırları (Python-C, Node.js Native Addons, JNI, P/Invoke)

## Tanım ve Kapsam

**FFI (Foreign Function Interface)** ve daha genel adıyla **interop**, bir programlama dilinde yazılmış kodun, başka bir dilde (çoğunlukla C/C++ gibi native diller) yazılmış bir fonksiyonu çağırabilmesini sağlayan mekanizmadır. Python'un `ctypes`/`cffi`'si, Node.js'in N-API tabanlı native addon'ları, Java'nın **JNI (Java Native Interface)**'ı ve .NET'in **P/Invoke (Platform Invoke)** mekanizması bu köprülerin en yaygın örnekleridir.

Bu köprüler pratikte kaçınılmazdır: kriptografi kütüphaneleri, veritabanı sürücüleri, GPU/ML runtime'ları, sıkıştırma kütüphaneleri, işletim sistemi API'leri hep bu sınırdan geçer. Ancak her FFI çağrısı bir **güven ve güvenlik sınırı ihlali**dir. Yönetilen (managed) tarafın sağladığı garantiler -- bellek güvenliği, tip güvenliği, sınır kontrolü, garbage collection -- bu sınırı geçtiğiniz anda **askıya alınır**. Sınırın öbür tarafında, çıplak pointer aritmetiği ve manuel bellek yönetimi ile baş başa kalırsınız.

Bu makale, bu geçiş noktalarında oluşan **tip güvenliği kaybı**, **bellek sahiplik (ownership) hataları** ve **hata/exception yayılım kopmaları**nın kök nedenlerini, bunların nasıl açığa dönüştüğünü ve tespit/savunma yöntemlerini ele alır.

## Kök Neden: İki Dünyanın Sözleşmesiz Buluşması

Yönetilen bir dil (Python, JavaScript, Java, C#) çalışma zamanında birçok görünmez garanti sunar:

- **Bellek güvenliği**: bir dizinin sınırlarını aşamazsınız, serbest bırakılmış belleğe erişemezsiniz.
- **Tip güvenliği**: bir `str`'i yanlışlıkla bir `int*` olarak yorumlayamazsınız.
- **Otomatik yaşam döngüsü**: nesneler siz işiniz bittiğinde toplanır; kim serbest bırakacak sorusu genellikle sorulmaz.

Native taraf (C/C++) ise bunların **hiçbirini** bilmez. C tarafı için her şey bir adres ve bir bayt sayısıdır. FFI köprüsü bu iki dünya arasında bir **ABI (Application Binary Interface)** sözleşmesi kurar: hangi argüman hangi register/stack konumunda, hangi tipte, hangi çağrı kuralıyla (calling convention) geçilecek. Sorun şu ki bu sözleşme çoğunlukla **derleyici tarafından denetlenmez**. Yönetilen tarafta elle yazdığınız imza (signature) ile native tarafın gerçek imzası birbirini tutmazsa, hiçbir hata mesajı almazsınız -- sadece bozuk davranış, bellek yolsuzluğu (memory corruption) veya sessiz veri bozulması alırsınız.

İşte "en az denetlenen ve en riskli kod yolu" olmasının nedeni budur: **derleyici size yardım edemez, çünkü sözleşmenin iki ucu iki ayrı derleme biriminde ve çoğu zaman iki ayrı dilde yaşar.**

## Ana Sorun Sınıfı 1: Tip ve İmza Uyumsuzluğu

### Python `ctypes` örneği

`ctypes` ile bir C fonksiyonunu çağırırken argüman ve dönüş tiplerini elle bildirirsiniz. Bildirmezseniz `ctypes` her şeyi `int` (C `int`, tipik olarak 32-bit) varsayar.

```python
import ctypes
lib = ctypes.CDLL("./libhesap.so")

# TEHLİKELİ: argtypes/restype bildirilmedi
sonuc = lib.pointer_dondur()   # gerçekte void* döner (64-bit)
# ctypes bunu int (32-bit) sanar -> pointer'ın üst 32 biti KESİLİR
kullan(sonuc)                  # bozuk adres -> segfault veya yanlış veri
```

Doğru kullanım, sözleşmeyi açıkça yazmaktır:

```python
lib.pointer_dondur.restype = ctypes.c_void_p
lib.pointer_dondur.argtypes = []

lib.topla.argtypes = [ctypes.c_int, ctypes.c_int]
lib.topla.restype = ctypes.c_int
```

Buradaki kök tuzak: 64-bit sistemde bir pointer'ın `int`'e sığmaması. `restype` bildirmezseniz üst yarısı sessizce atılır ve program bazen çalışır (adres düşük bölgedeyse), bazen çökebilir. Bu tür "bazen çalışan" hatalar, üretim ortamında en pahalı olanlardır.

### P/Invoke ve calling convention / marshalling

.NET'te P/Invoke ile bir Windows API veya C DLL fonksiyonunu çağırırken `[DllImport]` (veya yeni `[LibraryImport]`) ile imzayı bildirirsiniz. Buradaki klasik tuzaklar:

- **Calling convention** uyumsuzluğu (`Cdecl` vs `StdCall`): yanlışsa stack dengesizleşir. Eski platformlarda bu anında bozulmaya, yeni runtime'larda genellikle bir çalışma zamanı hatasına yol açar.
- **`bool` marshalling**: C tarafında `bool` genelde 1 bayt, ama Win32 `BOOL` 4 bayttır. Yanlış eşleme bitişik belleği yanlış okutur.
- **String encoding**: `char*` (ANSI/UTF-8) ile `wchar_t*` (UTF-16) karışması. `CharSet` yanlış ayarlanırsa metin bozulur veya taşma olur.
- **`struct` layout**: `[StructLayout(LayoutKind.Sequential)]` ve doğru `Pack` değeri şart. Alan hizalaması (alignment/padding) native tarafla birebir aynı olmalıdır; aksi halde alanlar kayar.

```csharp
[DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
static extern IntPtr CreateFileW(
    string lpFileName, uint dwDesiredAccess, uint dwShareMode,
    IntPtr lpSecurityAttributes, uint dwCreationDisposition,
    uint dwFlagsAndAttributes, IntPtr hTemplateFile);
```

Modern .NET'te derleme zamanında marshalling kodu üreten `[LibraryImport]` tercih edilir; bu, hataların bir kısmını erken yakalar ama **imzanın doğruluğunu hâlâ programcı garanti eder**.

### Ortak ders

Tüm bu mekanizmalarda imza, native başlık dosyasından (`.h`) **elle çevrilir**. C başlığı değişirse -- örneğin bir alan eklenirse, bir `int` `long`'a dönerse, bir enum genişlerse -- yönetilen taraftaki bildirim eskir ve **sessizce yanlış** hale gelir. Bu, bakımın en kırılgan noktasıdır.

## Ana Sorun Sınıfı 2: Bellek Sahipliği (Ownership) ve Yaşam Döngüsü

Bu, FFI hatalarının en yaygın ve en tehlikeli sınıfıdır. Temel soru her zaman şudur: **Bu belleği kim ayırdı ve kim serbest bırakacak?**

### Sahiplik senaryoları

Bir native fonksiyon bir pointer döndürdüğünde, sözleşmenin (dokümantasyonun) net olması gerekir:

1. **Callee-allocates, caller-frees**: Native taraf ayırır, çağıran serbest bırakmalı -- ve **doğru allocator ile**. C tarafında `malloc` ile ayrılan belleği, yönetilen tarafta yanlış bir `free` fonksiyonuyla serbest bırakırsanız heap bozulur. Genellikle kütüphane kendi `xxx_free()` fonksiyonunu sağlar ve o kullanılmalıdır.
2. **Callee owns, borrow only**: Native taraf pointer'ın sahibidir; siz sadece "ödünç" okursunuz. Serbest bırakırsanız **double-free**; sakladıysanız ve native taraf serbest bıraktıysa **use-after-free**.
3. **Caller-allocates**: Siz bir buffer ayırır, native tarafa doldurması için verirsiniz. Buffer'ın boyutunu yanlış bildirirseniz **buffer overflow**.

### Yönetilen tarafın GC'si ile çatışma

En ince hata sınıfı, **garbage collector'ın** bir nesneyi native çağrı sürerken taşıması veya toplamasıdır.

**Python (`ctypes`) tuzağı**: Geçici bir nesnenin pointer'ını alıp sakladığınızda, Python nesneyi toplayabilir ve pointer artık geçersiz belleği gösterir.

```python
# TEHLİKELİ
buf = ctypes.create_string_buffer(b"veri")
p = ctypes.cast(buf, ctypes.c_void_p)
del buf                 # buffer artık toplanabilir
lib.isle(p)             # dangling pointer -> use-after-free
```

`ctypes`, bir çağrı **süresince** argüman olarak verilen nesneleri canlı tutar; ancak siz pointer'ı çağrı dışına taşırsanız bu koruma kaybolur. `keepalive` referanslarını elle tutmak gerekir.

**JNI tuzağı**: JNI'da `GetStringUTFChars`, `GetPrimitiveArrayCritical`, `NewGlobalRef` gibi fonksiyonların hepsinin bir sahiplik/serbest bırakma sözleşmesi vardır:

- `GetStringUTFChars` ile aldığınız pointer'ı mutlaka `ReleaseStringUTFChars` ile geri vermelisiniz; aksi halde **native memory leak**.
- **Local reference**'lar bir JNI çağrısının kapsamıyla sınırlıdır. Bir Java nesnesine olan referansı native tarafta saklayıp sonraki çağrıda kullanmak isterseniz `NewGlobalRef` ile global referans oluşturmalısınız; local referansı saklamak bir **stale reference** hatasıdır.
- `GetPrimitiveArrayCritical`/`ReleasePrimitiveArrayCritical` arasındaki bölgede GC etkin biçimde durdurulur veya kısıtlanır; bu blokta JNI çağrısı yapmak ya da uzun iş yapmak deadlock ve performans felaketine yol açar.
- Her JNI çağrısından sonra `ExceptionCheck`/`ExceptionOccurred` ile pending exception kontrol edilmelidir; edilmezse davranış tanımsızlaşır.

**Node.js N-API tuzağı**: Eski `nan`/doğrudan V8 API'sinde nesne yaşam döngüsü ve GC etkileşimi çok kırılgandı. **N-API (node-addon-api)** bu yüzden geliştirildi: `napi_ref` ile referans sayımı, `Napi::ObjectWrap` ile yaşam döngüsü yönetimi, finalizer'lar ile native kaynağın JS nesnesi toplandığında serbest bırakılması. Yine de klasik hata, native tarafta ayrılan belleği bir `Buffer`'a sarıp **finalizer tanımlamamaktır** -- bu, JS GC'si Buffer'ı topladığında sızıntı veya çift serbest bırakma yaratır.

### Kök neden özeti

Her iki tarafın da **birbirinin yaşam döngüsü kurallarını bilmemesi**. Yönetilen taraf "ben toplarım" der, native taraf "ben serbest bırakırım" der; ikisi aynı belleğe sahip çıkarsa double-free, ikisi de sahip çıkmazsa leak, biri erken bırakırsa use-after-free oluşur.

## Ana Sorun Sınıfı 3: Hata ve Exception Yayılımının Kopması

Yönetilen diller exception fırlatır; C hata kodu döndürür veya `errno` set eder. Bu iki model sınırda buluşmaz.

- **C++ exception'ının FFI sınırını geçmesi tanımsız davranıştır.** Bir native addon içinde bir C++ exception, `extern "C"` sınırından yönetilen tarafa "sızarsa" süreç çöker veya bozulur. Native kodda tüm exception'ları sınırda yakalayıp bir hata koduna/JS exception'ına çevirmek gerekir.
- **JNI'da pending exception** varken başka JNI fonksiyonu çağırmak tanımsızdır. Native kod her adımda kontrol etmeli, gerekiyorsa erken dönmeli.
- **`SetLastError`/`errno` yarışı**: P/Invoke'ta `SetLastError=true` demezseniz veya araya başka bir çağrı girerse, `Marshal.GetLastWin32Error` yanlış değeri okur. Hata kodu, çağrının hemen ardından, başka hiçbir şey araya girmeden okunmalıdır.

Bunların güvenlik boyutu: yutulmuş hatalar (swallowed errors) bir işlemin **başarısız olmasına rağmen başarılı sanılmasına** yol açar. Örneğin bir imza doğrulama fonksiyonu native tarafta hata döndürür ama yönetilen taraf bunu kontrol etmezse, doğrulama atlanmış olur.

## Bu Sınırların Güvenlik Açığına Dönüşmesi

Neden bu sınırlar özellikle saldırgan açısından değerlidir?

- **Bellek güvenliği açıkları burada yeniden doğar.** Rust/Java/Python gibi bellek-güvenli dillerin verdiği güvence, FFI çağrısında biter. Bir uygulamanın tek `unsafe`/native yolu, tüm bellek-güvenli mimariyi baypas edebilir. Bu yüzden native kütüphaneler, güvenli dillerdeki uygulamaların **saldırı yüzeyinin en yoğun bölgesidir**.
- **Deserialization + FFI**: Dışarıdan gelen veriyi (uzunluk, offset, boyut alanları) doğrudan native fonksiyona uzunluk/boyut parametresi olarak geçirmek klasik bir **integer overflow -> heap overflow** zinciri açar. Örneğin `uint32` bir uzunluğu native tarafta `int`'e çevirirken işaret/taşma hatası, olması gerekenden küçük buffer ayrılmasına ve ardından taşmaya yol açabilir.
- **Confused deputy**: Yönetilen katmandaki yetki kontrolleri (örn. path doğrulama, sandbox) çoğu zaman native çağrıdan **önce** yapılır; native taraf ham parametreyi yeniden doğrulamaz. TOCTOU (time-of-check to time-of-use) ve doğrulama-atlama saldırıları bu boşlukta yaşar.
- **Supply chain**: Native addon'lar derlenmiş ikili (binary) içerir. `npm install` sırasında build script'i veya önceden derlenmiş `.node`/`.so`/`.dll` dosyası indirmek, kaynağı denetlenemeyen kod çalıştırmak demektir. Bu, tedarik zinciri saldırılarının bilinen bir vektörüdür.

## Tespit ve Savunma

### Geliştirme ve derleme zamanı

- **Bindings'i elle yazmayın, üretin.** `cffi`'nin API modu (C başlığını derleyiciyle doğrular), `bindgen` (Rust), `SWIG`, veya `[LibraryImport]` source generator gibi araçlar, imzayı native başlıktan türeterek elle çeviri hatalarını büyük ölçüde eler. Elle `ctypes`/`ctypes.CDLL` yazmak zorundaysanız, `argtypes` ve `restype`'ı **her fonksiyon için** eksiksiz bildirin.
- **Sanitizer'larla derleyin.** Native tarafı **ASan (AddressSanitizer)**, **UBSan (UndefinedBehaviorSanitizer)** ve mümkünse **MSan** ile derleyip test edin. FFI sınırındaki use-after-free, buffer overflow ve tanımsız davranışların çoğu bu araçlarla çalışma zamanında yakalanır. Yönetilen tarafı da bu sanitizer'lı native kütüphaneyle çalıştırmak, sınır hatalarını en iyi ortaya çıkaran yöntemdir.
- **Fuzzing.** FFI sınırına giren tüm dış girdiyi fuzz'layın (örn. libFuzzer/AFL native tarafta, veya yönetilen taraftan property-based test ile). Uzunluk/offset/boyut alanlarını özellikle zorlayın.
- **Compile-time kontroller**: `.NET`'te marshalling analyzer'ları, `clang -Wall -Wextra`, Node addon'larında N-API'nin tip kontrollü sarmalayıcılarını kullanın.

### Kod inceleme kontrol listesi (sınır-özel)

Her FFI çağrısı için şu soruları yanıtlayın:

1. **İmza doğru mu?** Argüman sayısı, tipleri, genişlikleri (32/64-bit), calling convention, struct layout/padding native başlıkla birebir mi?
2. **Sahiplik kimde?** Dönen pointer'ı kim, hangi fonksiyonla serbest bırakacak? Ödünç mü, sahiplik mi devrediliyor?
3. **Yaşam döngüsü korunuyor mu?** Yönetilen nesne, native çağrı süresince (ve pointer saklanıyorsa sonrasında da) canlı tutuluyor mu? (`keepalive`, `NewGlobalRef`, `napi_ref`, `GCHandle.Alloc(..., Pinned)`.)
4. **Boyut/uzunluk güvenli mi?** Dışarıdan gelen boyutlar native'e geçmeden önce doğrulanıp taşma kontrolünden geçiyor mu?
5. **Hata kontrol ediliyor mu?** Dönüş kodu / pending exception / `errno` / `GetLastError` çağrının hemen ardından okunuyor mu?
6. **Encoding doğru mu?** String encoding ve null-termination iki tarafta uyumlu mu?

### Çalışma zamanı ve mimari savunma

- **Sınırı daraltın**: FFI yüzeyini olabildiğince küçük, iyi tanımlı bir "kapı"ya indirgeyin. Ham pointer'ları uygulama geneline yaymak yerine, güvenli bir sarmalayıcı (wrapper) katmanı arkasına kapatın. Sahiplik, sarmalayıcının context manager / `IDisposable` / RAII / finalizer'ında yönetilsin.
- **Yeniden doğrulama**: Native tarafın da girdiyi yeniden doğruladığından emin olun; yönetilen taraftaki kontrolleri "yeterli" saymayın (confused deputy'ye karşı).
- **İzolasyon**: Yüksek riskli veya güvenilmeyen native kodu ayrı bir süreçte (out-of-process) çalıştırıp IPC ile konuşmak, bir çöküşün/istismarın ana süreci düşürmesini engeller. Mümkünse seccomp/AppContainer/sandbox ile native tarafı kısıtlayın.
- **Tedarik zinciri denetimi**: Native addon bağımlılıklarını sabit sürümle (lockfile), imza/hash doğrulamasıyla, mümkünse kaynaktan yeniden derleyerek kullanın. Prebuilt binary indiren install script'lerini denetleyin.

### Tespit sinyalleri (üretimde)

- Aralıklı, tekrarlanamayan segfault/çökme -- klasik dangling pointer/uyumsuz imza belirtisi.
- Yavaş büyüyen native heap (yönetilen heap sabitken) -- release/free unutulmuş bir sahiplik sızıntısı.
- 32/64-bit sınırında değeri kesilmiş görünen adresler.
- Belirli platform/derleyici kombinasyonunda ortaya çıkan bozulmalar -- ABI/struct padding uyumsuzluğu işareti.

## Yaygın Hatalar (Özet)

- `ctypes`'ta `argtypes`/`restype` bildirmemek; pointer'ı `int` sanmak.
- Bir çağrı boyunca canlı tutulan nesneyi çağrı dışına taşıyıp GC'ye toplatmak.
- JNI'da `Release*` çağrısını unutmak, local referansı saklamak, pending exception'ı kontrol etmemek.
- N-API'de native kaynağa finalizer tanımlamamak; double-free/leak.
- P/Invoke'ta yanlış calling convention, `CharSet`, `bool` genişliği, `SetLastError` unutmak.
- Dışarıdan gelen boyut/offset'i doğrulamadan native tarafa geçirmek.
- Yanlış allocator ile `free` (bir tarafta `malloc`, diğer tarafta uyumsuz free).
- C++ exception'ının veya native abort'un FFI sınırını geçmesine izin vermek.
- İmzayı native başlık değiştikten sonra güncellememek (sessiz eskime).

## Sonuç

Diller arası FFI/interop sınırı, modern yazılımın kaçınılmaz ama en az denetlenen bölgesidir. Buradaki hataların ortak kökü tektir: **derleyicinin ve çalışma zamanının garantilerinin, sözleşmesi elle yazılan bir ikili sınırda askıya alınması.** Tip genişlikleri, sahiplik, yaşam döngüsü ve hata yayılımı -- dört eksenin dördü de bu sınırda elle doğru kurulmak zorundadır. Savunmanın özü de tektir: sınırı küçült, sözleşmeyi otomatik türet ve doğrula, sahipliği açıkça bir sarmalayıcıya emanet et, native tarafı sanitizer/fuzzing/izolasyon ile denetle ve dış girdiyi her iki tarafta da yeniden doğrula. Bu sınıra "burada bellek-güvenli değiliz" gözüyle bakmak, doğru güvenlik zihniyetinin başlangıcıdır.
