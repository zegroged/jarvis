# Swift Güvenliği ve iOS Bellek/ARC Modeli

## Giriş

Swift, Apple ekosisteminde (iOS, macOS, watchOS, tvOS) uygulama geliştirmenin ana dilidir ve "güvenli varsayılanlar" (safe by default) felsefesiyle tasarlanmıştır. Optional tipler, sınır denetimli diziler ve otomatik bellek yönetimi sayesinde C ve Objective-C'ye kıyasla bütün bir hata sınıfını (null pointer dereference, buffer overflow, manuel `retain`/`release` dengesizliği) büyük ölçüde ortadan kaldırır. Ancak "büyük ölçüde" ifadesi kritiktir: Swift'in bellek modelinin merkezinde **ARC (Automatic Reference Counting)** vardır ve ARC bir çöp toplayıcı (garbage collector) değildir. Bu ayrım, retain-cycle'lardan kaynaklanan bellek sızıntılarına, `unowned` referanslarla oluşan use-after-free benzeri çökme senaryolarına ve `Unsafe*Pointer` API'leriyle yeniden ortaya çıkan klasik bellek güvenliği açıklarına kapı aralar. Buna bir de mobil platforma özgü sırlar yönetimi (Keychain) ve serileştirme (Codable) tuzakları eklendiğinde, Swift'in "güvenli" imajının altında hâlâ dikkat gerektiren bir güvenlik yüzeyi olduğu görülür.

Bu makale ARC'nin çalışma mantığını, dile özgü bellek güvenliği risklerini, `Unsafe` pointer API'lerini, Codable serileştirme tuzaklarını ve Keychain kullanım hatalarını mekanizma düzeyinde açıklar. Amaç saldırı reçetesi vermek değil; bu mekanizmaları anlayarak sızıntıları, çökmeleri ve veri sızmalarını **tespit ve savunma** yeteneği kazanmaktır.

## ARC: Otomatik Referans Sayımı Nasıl Çalışır?

### Tanım ve kök mantık

ARC, bir class örneğinin (reference type) ne zaman bellekten atılacağına karar veren bir mekanizmadır. Her heap üzerindeki nesne, kendisine kaç adet **strong** (güçlü) referans işaret ettiğini tutan bir sayaca sahiptir. Bu sayaç sıfıra düştüğü an nesne `deinit` çağrılır ve belleği serbest bırakılır.

Kritik nokta: ARC bu `retain`/`release` çağrılarını **derleme zamanında (compile time)** koda ekler. Yani ayrı bir arka plan çöp toplayıcı iş parçacığı çalışmaz; deterministic (belirlenimci) ve düşük gecikmeli bir yıkım vardır. Bu, gerçek zamanlı UI ve düşük bellek bütçeli mobil ortam için avantajdır. Fakat bedeli şudur: ARC **döngüsel referansları çözemez**. Bir çöp toplayıcı, ulaşılamayan nesne kümelerini tespit edebilir; sadece sayaca bakan ARC ise iki nesne birbirini güçlü tuttuğunda ikisinin de sayacı asla sıfıra inmediği için hiçbirini serbest bırakamaz.

Önemli ayrım: ARC yalnızca **class**, **closure** ve actor gibi reference type'lar için geçerlidir. `struct` ve `enum` gibi value type'lar kopyalanarak taşınır ve referans sayımına tabi değildir (içlerinde reference type barındırmadıkları sürece).

### Strong, weak ve unowned

Swift referans türleri:

- **strong** (varsayılan): Sayacı artırır, nesneyi hayatta tutar.
- **weak**: Sayacı artırmaz. Nesne yok olduğunda referans otomatik olarak `nil` olur; bu yüzden daima Optional'dır (`weak var delegate: SomeDelegate?`). Runtime, `weak` referansları bir yan tablo (side table) üzerinden izler ve nesne yıkıldığında bunları sıfırlar (zeroing weak reference).
- **unowned**: Sayacı artırmaz, Optional değildir ve nesne yok olduğunda **otomatik sıfırlanmaz**. Referans edilen nesnenin, referansı elinde tutandan her zaman daha uzun yaşayacağını "garanti ettiğinizde" kullanılır. Bu garanti yanlışsa, serbest bırakılmış belleğe erişilir.

## Retain Cycle (Referans Döngüsü) ve Bellek Sızıntısı

### Kök neden

En yaygın senaryo, closure'ların referansları güçlü tutmasıdır. Bir closure, gövdesinde eriştiği `self`'i varsayılan olarak **strong** yakalar (capture). Eğer bu closure aynı zamanda `self`'in bir property'sinde saklanıyorsa, döngü kapanır: `self` → closure → `self`.

```swift
final class ImageLoader {
    var onComplete: (() -> Void)?
    var data: Data?

    func load() {
        // self, closure'u güçlü tutuyor; closure da self'i güçlü yakalıyor -> DÖNGÜ
        onComplete = {
            self.data = Data()
            print("Yüklendi: \(self.data?.count ?? 0)")
        }
    }
}
```

Burada `ImageLoader` örneği artık hiçbir yerden erişilemese bile `deinit`'i çağrılmaz; bellekte kalır. Mobilde bu tür sızıntılar birikerek uygulamanın belleği aşmasına ve işletim sistemi tarafından sonlandırılmasına (jetsam / OOM kill) yol açar.

### Doğru kullanım: capture list

Çözüm, closure'un yakalama listesinde referansı `weak` veya `unowned` yapmaktır:

```swift
onComplete = { [weak self] in
    guard let self else { return }   // güvenli açılım
    self.data = Data()
}
```

`[weak self]` ile closure `self`'i zayıf tutar; `self` yok olmuşsa `guard let self` başarısız olur ve closure sessizce çıkar. Bu en güvenli varsayılandır.

### weak ile unowned arasındaki tehlikeli seçim

`unowned` daha performanslıdır ve Optional açımı gerektirmez, bu yüzden cazip görünür. Ancak yanlış kullanımı **use-after-free** benzeri bir çökmeye yol açar:

```swift
onComplete = { [unowned self] in
    self.data = Data()   // self bu ana kadar yok olduysa -> ÇÖKME
}
```

Eğer `self`, closure çağrılmadan önce serbest bırakılmışsa, `unowned` referans artık geçersiz belleğe işaret eder. Swift runtime bunu genellikle bir trap ile yakalar (`Fatal error: Attempted to read an unowned reference but object was already deallocated`) ve uygulama çöker. Bu, C'deki dangling pointer'ın Swift'teki denetimli karşılığıdır: çoğunlukla sessiz bir bellek bozulması yerine kontrollü bir crash olur, ama yine de kullanılabilirlik açığıdır. **Kural:** referans edilen nesnenin ömrünün, referansı tutandan kesinlikle uzun olduğunu ispatlayamıyorsanız `weak` kullanın.

### Klasik retain-cycle desenleri

- **Delegate**: Delegate property'leri daima `weak var delegate: XDelegate?` olmalıdır. Aksi halde delegating ve delegate nesneler birbirini tutar.
- **Parent-child**: Ağaç yapılarında (ör. bir `Node` ağacı) parent → child strong, child → parent `weak` olmalıdır.
- **Timer**: `Timer.scheduledTimer(...)` hedefini (target) güçlü tutar. `self`'i target veren bir timer invalidate edilmezse döngü oluşur. Modern çözüm block-tabanlı API'de `[weak self]` kullanmak ve `deinit`/`viewDidDisappear` içinde `invalidate()` çağırmaktır.
- **NotificationCenter / Combine**: Kapanışlarda `[weak self]`, abonelikleri (`AnyCancellable`) ise nesne yok olurken temizlemek gerekir.

### Tespit yöntemleri

Retain cycle'ları avlamak için savunma araç seti:

- **Xcode Memory Graph Debugger**: Çalışan uygulamada bellek grafiğini alır; beklenmedik şekilde canlı kalan nesneleri ve onları tutan döngüsel kenarları görsel olarak gösterir.
- **Instruments – Leaks ve Allocations**: Zaman içinde sürekli artan ve düşmeyen ayırma (allocation) grafiği bir sızıntı işaretidir. Leaks aracı klasik döngüleri işaretler.
- **`deinit` log'u**: Basit ama güçlü. Şüpheli sınıflara `deinit { print("X yıkıldı") }` ekleyin; ekran/nesne kapandığında bu satır tetiklenmiyorsa sızıntı vardır.
- **Statik analiz ve kod inceleme**: Closure gövdesinde `self`'e erişip capture list'i olmayan yerleri gözden geçirin.

## Bellek Güvenliği İhlalleri: Exclusive Access ve Unsafe Pointer'lar

### Exclusivity enforcement

Swift, bir bellek konumuna aynı anda çakışan (biri yazma olan) erişimleri yasaklar; buna **exclusive access to memory** denir. Bu kural, `inout` parametrelerde ve `mutating` metotlarda görünür; ihlali genellikle derleme zamanında, bazen runtime'da yakalanır. Amaç, aynı değişkenin eşzamanlı değiştirilip okunmasından kaynaklanan tanımsız davranışı engellemektir.

### Unsafe pointer API'leri

Swift, C ile birlikte çalışabilirlik ve performans için bilinçli olarak güvensiz bir kaçış kapısı sunar: `UnsafePointer`, `UnsafeMutablePointer`, `UnsafeRawPointer`, `UnsafeBufferPointer` ve `withUnsafeBytes` gibi API'ler. Bu tiplerin adındaki **Unsafe** kelimesi bir uyarıdır: bu API'ler kullanıldığında Swift'in bellek güvenliği garantilerinin **çoğu askıya alınır**. Sorumluluk programcıya geçer.

Riskler klasik C hatalarının aynısıdır:

- **Dangling pointer / use-after-free**: Bir pointer'ın işaret ettiği bellek serbest bırakıldıktan sonra pointer'ı kullanmak.
- **Buffer overflow / out-of-bounds**: Ayrılan bloğun sınırları dışında okuma/yazma. `UnsafeMutablePointer`'da manuel `advanced(by:)` aritmetiği ile kolayca sınır aşılır.
- **Yaşam süresi (lifetime) hatası**: `withUnsafeBytes` closure'undan pointer'ı dışarı kaçırmak. Pointer yalnızca closure gövdesi süresince geçerlidir; dışarı taşınırsa geçersiz belleğe işaret eder.

```swift
var sayilar = [Int](repeating: 0, count: 4)
sayilar.withUnsafeMutableBufferPointer { buffer in
    // GÜVENLİ: closure içinde ve sınır içinde
    buffer[2] = 42
    // TEHLİKE: buffer[10] = 1  -> sınır dışı yazma, tanımsız davranış
}
```

### Doğru kullanım ve savunma

- Unsafe API'leri **yalnızca gerektiğinde** (C kütüphanesi köprüleme, yüksek performanslı veri işleme) ve mümkün olan en dar kapsamda kullanın.
- Pointer'ları closure sınırının dışına asla kaçırmayın.
- Elle ayırdığınız (`allocate`) belleği mutlaka `deallocate` ile eşleyin; `initialize`/`deinitialize` dengesini koruyun.
- Sınır (bounds) kontrollerini elle yapın; buffer boyutunu bir kaynaktan alıp ayrı bir yerde varsaydığınız durumlardan kaçının.
- **AddressSanitizer (ASan)** ve **UndefinedBehaviorSanitizer** derleme seçeneklerini test/CI aşamasında etkinleştirin. Bu araçlar heap overflow, use-after-free ve out-of-bounds erişimleri çalışma anında yakalar ve Unsafe API kullanan kodun testinde vazgeçilmezdir.
- Mümkünse Unsafe bloğunu güvenli, iyi test edilmiş bir Swift API arkasına sarın (encapsulation) ki kullanan taraf güvensiz aritmetiğe maruz kalmasın.

## Codable ve Serileştirme Tuzakları

### Mekanizma

`Codable` (`Encodable` + `Decodable`), Swift'in tip güvenli serileştirme protokolüdür; çoğunlukla `JSONDecoder`/`JSONEncoder` ile kullanılır. Derleyici, uygun tipler için `init(from:)` ve `encode(to:)` metotlarını otomatik türetir. Güvenlik açısından güzel yanı, hedef tipin şeklinin sabit olmasıdır: gelen veri beklenen alanlara map edilir, eşleşmeyen yapı decode hatası fırlatır. Bu, Objective-C `NSKeyedUnarchiver`'ın eski `NSCoding` kullanımındaki gibi keyfi sınıf örnekleme (object graph deserialization) risklerine kıyasla önemli bir savunmadır.

### Yaygın tuzaklar

- **Güvenilmeyen kaynaktan gelen JSON'un kör decode edilmesi**: Codable tip güvenliği sağlar ama **iş kuralı doğrulaması yapmaz**. Bir `Int`'in negatif olmaması, bir `url` alanının izinli şemada olması, bir dizinin makul boyutta olması gibi kısıtları siz kontrol etmelisiniz. Ağdan gelen veriyi decode edip doğrulamadan kullanmak, mantık düzeyinde saldırı yüzeyi açar.
- **`decodeIfPresent` vs zorunlu alan**: Eksik alanları sessizce varsayılana çevirmek, güvenlik kararlarını (ör. `isAdmin`) beklenmedik değerlere düşürebilir. Zorunlu güvenlik alanlarını `decodeIfPresent` ile isteğe bağlı yapmayın.
- **Kaynak tüketimi (DoS)**: Çok büyük veya derin iç içe JSON, bellek/CPU tüketerek uygulamayı çökertebilir. Ağ katmanında yanıt boyutu sınırı koyun.
- **Eski `NSCoding`/`NSKeyedUnarchiver` kullanımı**: Güvenilmeyen veriyi `NSKeyedUnarchiver` ile açarken mutlaka **secure coding** (`requiresSecureCoding = true`, `decodeObject(of:forKey:)` ile izinli sınıf listesi) kullanın. Aksi halde gelen arşiv beklenmeyen sınıfları örnekletebilir. Yeni kod için mümkünse Codable/JSON tercih edin.
- **Hassas verinin diske/log'a serileştirilmesi**: Token, parola gibi alanları içeren bir modeli olduğu gibi log'lamak veya korumasız dosyaya yazmak yaygın bir sızma yoludur. `CodingKeys`'ten hassas alanları çıkarmak veya ayrı bir DTO kullanmak iyi bir pratiktir.

## Keychain: iOS'ta Sırları Doğru Saklamak

### Neden Keychain?

iOS'ta token, parola, şifreleme anahtarı gibi hassas verilerin doğru yeri **Keychain**'dir. Keychain, işletim sistemi tarafından yönetilen, donanım destekli (Secure Enclave ile ilişkili) ve cihaz kilidi/biyometri politikalarına bağlanabilen şifreli bir depodur. `UserDefaults`, düz dosya veya plist bunun yerine **kesinlikle kullanılmamalıdır**: bunlar şifresizdir, yedeklemeye dahil olur ve jailbreak'li ya da yedeği ele geçirilmiş bir cihazda düz metin okunabilir.

### Yaygın hatalar

- **`kSecAttrAccessible` sınıfının yanlış seçimi**: Bu attribute, sırra ne zaman erişilebileceğini belirler. En sık hata `kSecAttrAccessibleAlways` benzeri gevşek bir politika kullanmaktır (bu değer zaten kullanımdan kaldırılmıştır). Genel öneri: sır yalnızca bu cihazda gerekiyorsa ve yedeğe taşınmamalıysa `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` gibi mümkün olan en kısıtlayıcı sınıfı seçin. `ThisDeviceOnly` ekleri, sırrın şifresiz yedek veya başka cihaza geçişini engeller.
- **Access control ve biyometri**: Yüksek değerli sırlar için `SecAccessControlCreateWithFlags` ile `.biometryCurrentSet` veya `.userPresence` gibi bayraklar kullanarak erişimi Face ID/Touch ID'ye bağlamak savunmayı güçlendirir. `.biometryCurrentSet`, kayıtlı biyometri değişince sırrın geçersiz olmasını sağlar.
- **Access group ve paylaşım hataları**: Yanlış yapılandırılmış Keychain access group, sırrın niyetlenmeyen uygulamalarla paylaşılmasına yol açabilir.
- **Hata yönetimi**: Keychain API'leri OSStatus döndürür. `errSecDuplicateItem` (zaten var), `errSecItemNotFound` gibi durumları ele almamak, "güncelle" niyetiyle yazarken sessizce eski sırrın kalmasına ya da mantık hatalarına yol açar. Kayıt varsa `SecItemUpdate`, yoksa `SecItemAdd` mantığı doğru kurulmalıdır.
- **Silme/rotasyon eksikliği**: Oturum kapanışında (logout) token'ı Keychain'den silmemek yaygın bir hatadır; bir sonraki kullanıcı eski oturumu devralabilir.
- **Sırrı belleğe/log'a sızdırma**: Keychain'den okunan sırrı log'lamak veya crash raporuna dahil etmek, güvenli depolamanın anlamını yok eder.

### Doğru kullanım ilkeleri

- En kısıtlayıcı `kSecAttrAccessible` sınıfını seçin; varsayılan olarak `ThisDeviceOnly` düşünün.
- Yüksek riskli sırları access control + biyometri ile koruyun.
- Her OSStatus'u kontrol edin; add/update ayrımını doğru kurun.
- Logout'ta ilgili öğeleri `SecItemDelete` ile temizleyin.
- Simülatör ve gerçek cihaz davranış farklarını (özellikle biyometri) test edin.

## Ek Platform Notları

- **App Transport Security (ATS)**: iOS varsayılan olarak HTTPS zorlar. `NSAllowsArbitraryLoads = true` ile ATS'yi tümden kapatmak yaygın bir hatadır ve man-in-the-middle riskini açar; istisna gerekiyorsa yalnızca ilgili host için dar tanımlayın.
- **Concurrency ve data race**: `async/await`, `actor` ve Swift'in yeni **strict concurrency** denetimleri, paylaşılan durumdaki veri yarışlarını (data race) derleme zamanında yakalamayı hedefler. `@Sendable` ve actor izolasyonu, closure'lardaki paylaşılan mutable state hatalarını azaltır; bu denetimleri `nonisolated(unsafe)` gibi kaçışlarla susturmak yeni riskler doğurabilir.
- **Force unwrap (`!`)**: Optional'ı `!` ile zorla açmak `nil` durumunda çökme üretir. Bu bellek bozulması değildir ama kullanılabilirlik açığıdır; kullanıcı girdisi veya ağ verisi kaynaklı Optional'larda `guard let`/`if let` tercih edin.

## Özet ve Savunma Kontrol Listesi

Swift, hafızayı güvenli kılan güçlü varsayılanlar sunar; asıl riskler bu varsayılanların dışına çıkıldığında ortaya çıkar. Pratik savunma özeti:

- Closure'larda `self` erişiminde varsayılan olarak `[weak self]` kullanın; `unowned`'ı yalnızca ömür garantisi ispatlanabildiğinde tercih edin.
- Delegate'leri `weak`, parent-child'da child→parent bağını `weak` yapın; timer ve abonelikleri temizleyin.
- Retain cycle'ları Memory Graph Debugger, Instruments Leaks ve `deinit` log'larıyla düzenli avlayın.
- `Unsafe*Pointer` kullanımını en aza indirin, dar kapsamda tutun, pointer'ları closure dışına kaçırmayın ve testte ASan çalıştırın.
- Codable ile decode ettiğiniz güvenilmeyen veriyi ayrıca iş kuralına göre doğrulayın; eski `NSKeyedUnarchiver`'da secure coding kullanın; hassas alanları serileştirme/log dışında tutun.
- Sırları yalnızca Keychain'de, en kısıtlayıcı erişim sınıfıyla, gerektiğinde biyometriyle saklayın; OSStatus'ları ele alın; logout'ta silin.
- ATS'yi kapatmayın; strict concurrency uyarılarını susturmak yerine düzeltin.

Bu ilkeler, Swift'in "güvenli varsayılanlar" vaadini gerçekten güvenli koda dönüştürmenin temelidir: mekanizmayı anlamak, tuzağı tanımak ve tespit araçlarını rutine sokmak.
