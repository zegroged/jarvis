# Mobil Native Geliştirme: iOS (Swift/SwiftUI) ve Android (Kotlin/Jetpack Compose) Mimarisi

## Neden Bu Konu Ayrı Bir Kategori Gerektirir

Sunucu tarafı bir Python veya Go servisi yazarken sistemin sahibi sizsiniz: süreci siz başlatır, siz sonlandırır, belleği siz yönetir, ağ hatasını siz karşılarsınız. Mobil native geliştirme bu varsayımın tam tersidir. Uygulamanız kendi sürecinizin sahibi değildir; işletim sistemi (iOS'ta Darwin/XNU tabanlı, Android'de Linux tabanlı) sizin process'inizi istediği an askıya alabilir, bellek baskısı altında öldürebilir, arka plana atabilir. Bu yüzden mobil mimarinin merkezinde iki kavram vardır: **yaşam döngüsü (lifecycle)** ve **kısıtlı kaynak yönetimi**. Genel amaçlı dillerde (C++, Rust, Java) öğrendiğiniz bellek yönetimi modelleri burada doğrudan uygulanmaz çünkü Swift'in ARC'i (Automatic Reference Counting) ne Java/Kotlin'in JVM/ART tracing garbage collector'u ile aynı davranışsal profile sahiptir, ne de ikisi de "programcı istediği zaman belleği serbest bırakır" mantığıyla çalışır. Ayrıca UI katmanı (SwiftUI, Jetpack Compose) declarative/reactive bir paradigmaya geçmiştir; bu, on yıllarca hakim olan imperative UI (UIKit, Android View sistemi) mantığından köklü bir sapmadır. Bu makale, bu iki platformun mimarisini, neden böyle tasarlandıklarını ve pratikte hangi tuzaklara düşüldüğünü ele alır.

## 1. Uygulama Yaşam Döngüsü: İşletim Sistemi Sizin Patronunuz

### 1.1 Kök Neden: Mobil Cihazlar Kaynağı Paylaştırır

Masaüstünde bir uygulamayı kapatmadığınız sürece çalışmaya devam eder. Mobil cihazlarda pil, RAM ve termal bütçe sınırlıdır; aynı anda onlarca uygulama "açık" görünse de gerçekte çoğu askıdadır. İşletim sistemi, kullanıcının gördüğü uygulamaya (foreground) kaynak ayırır, geri kalanını dondurur veya sonlandırır. Bu nedenle uygulamanız "ben ne zaman çalışıyorum, ne zaman durduruluyorum" sorusuna cevap verecek bir state machine'e sahip olmak zorundadır. Bu state machine platformun size dayattığı lifecycle callback'leridir.

### 1.2 iOS Tarafında: UIApplication ve Scene Lifecycle

iOS'ta klasik model `UIApplicationDelegate` üzerinden `applicationDidBecomeActive`, `applicationWillResignActive`, `applicationDidEnterBackground`, `applicationWillTerminate` gibi callback'lerdi. iOS 13 ile **Scene** kavramı geldi (`UISceneDelegate`), çünkü iPad'de aynı uygulamanın birden fazla penceresi (multi-window/Split View) aynı anda var olabilir. Yani "uygulama" seviyesindeki durum ile "sahne/pencere" seviyesindeki durum ayrıştırıldı: uygulama arka planda olabilir ama bir sahne hala görünür olabilir (örneğin Slide Over).

SwiftUI'da bu callback'ler `ScenePhase` environment değeri üzerinden soyutlanır: `.active`, `.inactive`, `.background`. Önemli olan şu kök mantık: **inactive** kısa geçiş durumudur (örnek: bildirim merkezi açıldığında, çağrı geldiğinde), **background**'a geçince uygulamanın çalışma süresi çok kısıtlıdır (tipik olarak birkaç saniye, özel arka plan görevleri dışında). Bu pencerede bitirilmemiş iş (yazılmamış dosya, tamamlanmamış network çağrısı) kaybolabilir.

**View Controller yaşam döngüsü** ayrı bir katmandır ve UIKit mirasından gelir: `viewDidLoad` (bir kez, view hiyerarşisi bellekte oluşturulduğunda), `viewWillAppear`/`viewDidAppear` (her görünür olduğunda, birden fazla kez tetiklenebilir), `viewWillDisappear`/`viewDidDisappear`. SwiftUI kullansanız bile, çoğu uygulama hala UIKit host'u (`UIHostingController`) üzerinde çalışır, dolayısıyla bu iki katman (Scene + ViewController) eş zamanlı var olabilir ve karıştırılmamalıdır: biri sürecin/pencerenin durumu, diğeri ekrandaki bir görünümün durumudur.

### 1.3 Android Tarafında: Activity ve Fragment Lifecycle

Android'in klasik `Activity` yaşam döngüsü: `onCreate` → `onStart` → `onResume` (kullanıcı etkileşimde) → `onPause` (kısmi kesinti, örnek: diyalog açıldı) → `onStop` (tamamen görünmez) → `onDestroy`. Buradaki kök neden iOS'takiyle aynı: sistem herhangi bir noktada, özellikle `onStop` sonrasında, bellek geri kazanımı için process'i **hiç uyarmadan** sonlandırabilir. `onDestroy` çağrılacağı garanti değildir — bu, çok yeni geliştiricilerin düştüğü en büyük tuzaklardan biridir: "onDestroy'da temizlik yaparım" varsayımı yanlıştır çünkü sistem process'i kill ettiğinde hiçbir callback çalışmaz.

Bunun çözümü **`onSaveInstanceState`** / durum kurtarma mekanizmasıdır: Android, configuration change (ekran dönmesi gibi) veya arka planda process kill öncesinde, küçük bir `Bundle` içinde durumu saklamanıza izin verir; process yeniden oluşturulduğunda bu bundle geri verilir. Bu, "sürecin öldüğünü varsayarak tasarla" felsefesinin somut API karşılığıdır.

Jetpack Compose ile birlikte gelen **`ViewModel`** sınıfı bu sorunu daha temiz çözer: ViewModel, configuration change'lerde (ekran dönmesi) hayatta kalır çünkü Activity/Fragment yeniden oluşturulsa da ViewModel referansı `ViewModelStore` üzerinden korunur; sadece process tamamen öldüğünde ViewModel de kaybolur (bu durumda `SavedStateHandle` devreye girer). Compose'da `remember` ile tutulan state ise recomposition'da hayatta kalır ama configuration change'de kalmaz (aksi belirtilmedikçe); `rememberSaveable` bu farkı kapatır.

### 1.4 Ortak Kök Neden ve Karşılaştırma

Her iki platformda da aynı felsefe var: **"Sürecinizin herhangi bir noktada, herhangi bir sebeple sonlandırılabileceğini varsayarak tasarlayın."** Bu, sunucu tarafı geliştiricilerin alışkın olmadığı bir kısıttır. Pratik sonuç: kritik veriyi mümkün olduğunca erken diske/veritabanına yazın, "bellekte tut, sonra kaydederim" stratejisinden kaçının.

## 2. Bellek Yönetimi: ARC vs Tracing Garbage Collection

### 2.1 Swift/Objective-C: Automatic Reference Counting (ARC)

ARC, derleme zamanında çalışır — çalışma zamanında arka planda tarama yapan bir GC değildir. Derleyici, her nesne için referans sayacını artıran/azaltan (`retain`/`release`) kodu otomatik olarak enjekte eder. Bir nesnenin referans sayacı sıfıra düştüğü an, belleği **deterministik olarak ve anında** serbest bırakılır. Bu, GC'li dillerin aksine "ne zaman serbest kalacağını" tam olarak bilebilmenizi sağlar — dosya tanıtıcı (file handle) veya kilit (lock) gibi kaynakların da nesne yaşam süresine bağlanabilmesinin (RAII benzeri desen) nedeni budur.

**Kök sorun: güçlü referans döngüleri (retain cycle).** Referans sayımı (reference counting) tabanlı her sistemin Aşil topuğu aynı: iki nesne birbirini güçlü (strong) referansla tutarsa, dışarıdan erişim kalmasa bile sayaçları asla sıfıra inmez, bellek sızar. Klasik örnek: bir `ViewController`, bir closure'ı property olarak tutar; closure da `self`'i yakalar (capture). `self -> closure -> self` döngüsü oluşur.

Çözüm: **`weak`** ve **`unowned`** referanslar. `weak`, referans sayacını artırmaz ve işaret ettiği nesne yok edildiğinde otomatik olarak `nil` olur (bu yüzden sadece Optional tiplerle kullanılabilir). `unowned` de sayacı artırmaz ama nesne yok olduğunda `nil` olmaz — sonraki erişim crash'e (genelde EXC_BAD_ACCESS) yol açar; sadece yaşam süresi garantili olduğunuzda kullanılmalıdır. Pratikte closure capture list'lerinde `[weak self]` yazıp fonksiyon gövdesinde `guard let self = self else { return }` deseni standarttır.

ARC'in bir diğer inceliği: **çok iş parçacığında (multithreading) referans sayacı artırma/azaltma işlemleri atomiktir**, bu da performans maliyeti getirir; aşırı küçük nesne oluşturma/yok etme döngülerinde bu maliyet gözle görülür hale gelebilir.

### 2.2 Kotlin/JVM ve ART: Tracing Garbage Collector

Android tarafında (Kotlin, Java) bellek yönetimi tamamen farklı bir modelle çalışır: **tracing GC**. Referans sayımı yerine, GC periyodik olarak "kök" (root) referanslardan (stack, static alanlar, JNI referansları) başlayarak erişilebilir tüm nesneleri işaretler (mark), erişilemeyenleri toplar (sweep/compact). Bu model, referans döngüleriyle **hiçbir sorun yaşamaz** — döngüsel referanslar erişilebilir kök kümesinden kopuksa otomatik toplanır. Bu, ARC'e göre temel bir avantajdır ama bedeli vardır: GC'nin çalıştığı an öngörülemez (nispeten), ve tarihsel olarak "stop-the-world" duraklamaları (GC çalışırken tüm thread'lerin durması) UI donmalarına (jank) neden olabiliyordu.

Android Runtime (ART, eski Dalvik'in yerini almıştır) modern sürümlerde generational, concurrent ve compacting GC algoritmaları kullanarak bu duraklamaları ağır biçimde azaltmıştır, ama kavram olarak "GC bir noktada devreye girer ve çalışma zamanı maliyeti vardır" gerçeği değişmez.

**Android'de asıl bellek tuzağı context sızıntısıdır**, ARC'teki retain cycle'in kabaca eşdeğeri ama farklı bir mekanizmayla: Bir `Activity` context'i, ondan daha uzun yaşayan bir nesneye (statik alan, singleton, uzun ömürlü thread/handler) referans olarak verilirse, Activity yok edilmiş olsa bile (kullanıcı geri tuşuna basmış olsa bile) GC o Activity'yi ve bütün View hiyerarşisini toplayamaz — çünkü hala erişilebilir kök kümesinden bir yol vardır. Sonuç: Activity "hayalet" olarak bellekte kalır, tekrarlayan yaratım/yok etme döngülerinde (ekran dönmesi gibi) OutOfMemoryError'a kadar gidebilir. Bu, GC'li bir dilde de bellek sızıntısının mümkün olduğunu gösteren klasik örnektir: GC "erişilemeyen" nesneleri toplar, ama "artık mantıksal olarak gereksiz ama hala erişilebilir" nesneleri toplayamaz.

### 2.3 Karşılaştırmalı Kök Çıkarım

| Boyut | Swift ARC | Kotlin/ART GC |
|---|---|---|
| Mekanizma | Derleme zamanı referans sayımı | Çalışma zamanı tarama (mark-sweep/compact) |
| Determinizm | Yüksek (sayaç sıfıra düştüğü an) | Düşük (GC ne zaman çalışacağını kesin bilemezsiniz) |
| Tipik sızıntı nedeni | Güçlü referans döngüsü (retain cycle) | Uzun ömürlü nesneden kısa ömürlü context'e referans |
| Çözüm deseni | `weak` / `unowned` | `WeakReference`, lifecycle-aware bileşenler, context sızmasını önlemek |
| Performans maliyeti | Atomik retain/release, sık nesne oluşumu maliyetlidir | GC duraklamaları (büyük ölçüde azaltılmış) |

Bir mühendis olarak çıkarılacak genel ders: hangi platformda çalışırsanız çalışın, "nesne kimin sahip" sorusunu (ownership) açıkça modelleyin. ARC'te sahiplik grafiğinde döngü oluşturmayın; GC'li sistemlerde sahiplik ömrünün (lifetime) yanlışlıkla uzatılmasına izin vermeyin.

## 3. Declarative UI Paradigması: SwiftUI ve Jetpack Compose

### 3.1 Neden Imperative'den Declarative'e Geçildi

UIKit ve klasik Android View sisteminde UI, imperative bir biçimde güncellenirdi: bir veri değiştiğinde, geliştirici hangi View'in hangi özelliğinin (`label.text = ...`, `view.setVisibility(...)`) güncelleneceğini elle yazardı. Bu, uygulama büyüdükçe **durum-görüntü senkronizasyon sorununu** (state-UI senkronizasyonu) yönetilemez hale getirir: bir veri değiştiğinde onu gösteren her yerin manuel güncellendiğinden emin olmak geliştiricinin sorumluluğundaydı, ve bu genellikle unutulan güncellemeler (stale UI) ile sonuçlanırdı.

SwiftUI (2019) ve Jetpack Compose (2021) aynı kök fikri paylaşır: **UI, durumun bir fonksiyonudur** (`UI = f(State)`). Geliştirici View'i "nasıl güncelleyeceğini" değil, "belirli bir durumda nasıl görünmesi gerektiğini" tanımlar. Durum değiştiğinde framework, hangi kısmın yeniden çizilmesi gerektiğini kendisi hesaplar (SwiftUI'da view diffing, Compose'da **recomposition**).

### 3.2 Compose'da Recomposition Mekaniği

Compose'un çalışma mantığı: her `@Composable` fonksiyon, okuduğu state'lere (`State<T>`, `mutableStateOf`) "abone" olur. Bir state değiştiğinde, Compose runtime sadece o state'i okuyan composable'ları yeniden çalıştırır (recompose), tüm ağacı değil — bu **akıllı yeniden hesaplama (smart recomposition)** olarak adlandırılır ve performansın temelidir.

**Yaygın tuzak:** Bir composable fonksiyon içinde `mutableStateOf(...)` doğrudan çağırmak, her recomposition'da state'in sıfırdan oluşturulmasına yol açar (yeni bir kutu, değeri hep baştaki değere döner). Çözüm `remember { mutableStateOf(...) }` deseni: `remember`, değeri composition belleğine kaydeder ve sonraki recomposition'larda aynı örneği geri verir. Bunun da bir sınırı var: composable'in kendisi composition'dan çıkarsa (ekrandan tamamen kalkarsa) `remember` değeri de kaybolur; configuration change'de hayatta kalması gerekiyorsa `rememberSaveable` kullanılmalıdır.

Diğer klasik tuzak: **yan etkileri (side effect) doğrudan composable gövdesinde çalıştırmak** (örnek: composable içinde doğrudan network çağrısı başlatmak). Composable fonksiyonlar herhangi bir zamanda, herhangi bir sırada, birden fazla kez çağrılabilir (recomposition, hatta bazen "iptal edilen" recomposition'lar da olabilir) — bu yüzden yan etkiler `LaunchedEffect`, `SideEffect`, `DisposableEffect` gibi özel API'lerle, açıkça belirtilen bir "anahtar" (key) değiştiğinde tetiklenecek şekilde izole edilmelidir. Bu kural ihlal edildiğinde network çağrısının gereksiz yere tekrar tekrar tetiklenmesi veya UI'nin tutarsız durumlar göstermesi gibi hatalar ortaya çıkar.

### 3.3 SwiftUI'da Eşdeğer Mekanizma

SwiftUI'da durum yönetimi property wrapper'lar üzerinden yapılır: `@State` (view'a lokal, değer tipli durum), `@Binding` (bir üst view'daki state'e iki yönlü bağlantı), `@ObservedObject`/`@StateObject` (referans tipli, `ObservableObject` protokolüne uyan sınıflar için — `@Published` ile işaretlenen alan değiştiğinde view yeniden çizilir), ve daha yeni `@Observable` makrosu (Swift'in gözlemlenebilirlik modelini sadeleştirir).

**`@State` vs `@StateObject` karışıklığı** yaygın bir hatadır: `@State`, değer tipleri (struct) için view'in **sahip olduğu** kaynağı temsil eder; view yeniden oluşturulduğunda SwiftUI bu değeri korur (view struct'i her recompute'ta yeniden yaratılsa da, `@State` değeri dışarıdaki bir depoda tutulur). `@StateObject`, bir referans tipi nesnenin **yaşam döngüsünü view'a bağlar** ve view'in kendisi oluşturulunca nesneyi bir kez yaratır; eğer yanlışlıkla `@ObservedObject` kullanılırsa (ki bu, sahiplik olmadan dışarıdan alınan bir nesneyi belirtir) ve o nesneyi oluşturan üst view yeniden çizildiğinde nesne yanlışlıkla sıfırdan yaratılabilir — bu, "kaybolan state" bug'larının klasik nedenidir.

SwiftUI'nin view güncelleme modeli, Compose'daki gibi diffing tabanlıdır: `body` her çağrıldığında yeni bir view ağacı "tarifi" oluşturulur, SwiftUI bunu bir önceki ağaçla karşılaştırır ve sadece değişen kısımları gerçek ekran çıktısına uygular. Bu yüzden `body` içindeki hesaplamaların **yan etkisiz (pure/idempotent)** olması kritik bir varsayımdır; `body` içinde durum değiştirmek (mutasyon) tanımsız/döngüsel davranışlara yol açabilir.

### 3.4 Declarative UI'nin Kök Getirdiği Disiplin

Her iki framework de aynı temel prensibi zorunlu kılar: **render fonksiyonu (body / composable gövdesi) saf olmalı, yan etkiler açıkça izole edilmiş API'ler aracılığıyla yönetilmelidir.** Bu, fonksiyonel programlamadaki "saf fonksiyon" disiplininin UI katmanına taşınmasıdır ve mobil geliştiricilerin en çok direndiği ama en çok fayda gördüğü zihniyet değişimidir.

## 4. Concurrency: Yapısal Eş Zamanlılık

### 4.1 Neden Önemli

Mobil UI, tek bir ana iş parçacığında (main thread) çalışır; bu thread bloklanırsa kullanıcı arayüzü donar (ANR — Application Not Responding — Android'de, benzer şikayetler iOS'ta "beach ball" yerine app'in yanıtı kesilmesi şeklinde görülür). Network çağrısı, disk I/O, ağır hesaplama gibi işler ana thread dışına taşınmalıdır; ama sonucun geri ana thread'e güvenli şekilde taşınması gerekir.

### 4.2 Swift Concurrency (async/await, Actors)

Swift 5.5+ ile gelen yapısal eş zamanlılık modeli, `async`/`await` sözdizimini callback tabanlı (completion handler) kodun yerine koyar; bu, "callback hell" ve hata yönetiminin dağıtılması sorununu çözer. **Actor** tipi, bir veri kümesine aynı anda yalnızca bir görevin (task) erişebilmesini derleyici seviyesinde garanti ederek veri yarışı (data race) sınıfını önler. `@MainActor` özel işaretlemesi, bir fonksiyonun veya sınıfın her zaman ana thread'de çalışmasını derleme zamanında zorunlu kılar — bu, UI güncellemesinin yanlışlıkla arka plan thread'inden yapılması hatasını (klasik "UI donduruldu/crash oldu" şikayeti) büyük ölçüde ortadan kaldırır.

### 4.3 Kotlin Coroutines

Kotlin tarafında eş değer yapı **coroutine**'lerdir: `suspend` fonksiyonlar, thread'i bloklamadan "askıya alınabilen" hesaplamaları ifade eder. `Dispatchers.Main`, `Dispatchers.IO`, `Dispatchers.Default` gibi dispatcher'lar hangi thread havuzunda çalışılacağını belirler. Compose'a özel `LaunchedEffect` ve `rememberCoroutineScope`, coroutine'lerin composable yaşam döngüsüne bağlanmasını sağlar — composable ekrandan kalktığında ilgili coroutine otomatik iptal edilir (structured concurrency), bu da "artık görünmeyen bir ekranın arka planda hala çalışması ve geçersiz state güncellemesi denemesi" sınıfındaki hataları engeller.

### 4.4 Ortak Tuzak: Yaşam Döngüsü ile Uyumsuz İş

Hem Swift Task'ları hem Kotlin coroutine'leri, başlatıldıkları view/composable/screen yok edildiğinde **iptal edilmezlerse** sızan kaynaklar ve geçersiz state'e yazma girişimleri (crash veya sessiz veri bozulması) ile sonuçlanır. Doğru pratik: görevleri, onları başlatan bileşenin yaşam döngüsüne (view lifecycle, ViewModel scope, `viewModelScope`, SwiftUI `.task` modifier'ı) açıkça bağlamak — asla "serbest çalışan" (fire-and-forget) global görevler oluşturmamak.

## 5. Savunma ve Tespit Perspektifi

Bir mühendis/inceleyici gözüyle, mobil native kod tabanında şu noktalar sistematik olarak denetlenmelidir:

- **Bellek sızıntısı tespiti:** iOS'ta Xcode Instruments'in "Leaks" ve "Allocations" araçları retain cycle'ları görselleştirir; Android'de LeakCanary gibi araçlar Activity/Fragment context sızıntılarını otomatik yakalar. Kod incelemesinde her closure/lambda'nın `self`/`this` yakalayıp yakalamadığına ve capture'in `weak` olup olmadığına bakılmalıdır.
- **Ana thread blokajları:** Uzun süren I/O veya hesaplamanın `Dispatchers.IO`/arka plan kuyruğuna taşındığından emin olun; StrictMode (Android) ve Time Profiler (Xcode) bu ihlalleri tespit eder.
- **State restorasyon eksikliği:** `onSaveInstanceState`/`SavedStateHandle` kullanılmadan tutulan kritik state, process death sonrası veri kaybına yol açar; test için geliştirici seçeneklerinde "Don't keep activities" (Android) ile zorlanabilir.
- **Yan etkilerin composable/body içinde izole edilmemesi:** Kod incelemesinde `LaunchedEffect`/`.task` dışı network/IO çağrısı, ya da body içinde durum mutasyonu aranmalıdır.
- **Retain cycle önleme disiplini:** delegate pattern'lerde delegate referansının `weak` tanımlanıp tanımlanmadığı (Objective-C/Swift mirası) klasik bir statik analiz kontrol noktasıdır.

## Sonuç

iOS ve Android native geliştirme, sunucu tarafı veya masaüstü geliştirmeden farklı bir mühendislik zihniyeti gerektirir: kaynakların kısıtlı olduğu, sürecin her an sonlandırılabileceği ve UI'nin durumun saf bir yansıması olması gerektiği bir ortam. ARC ile tracing GC arasındaki fark, "ne zaman bellek serbest kalır" sorusuna verilen iki farklı cevaptır ve her biri kendi sınıf hata modunu (retain cycle vs context sızıntısı) beraberinde getirir. SwiftUI ve Compose'un declarative modeli, UI geliştirmeyi fonksiyonel programlama disiplinine yaklaştırarak durum-görüntü tutarsızlığı sorununu yapısal olarak azaltır, ama yan etki yönetimi konusunda yeni, özenle öğrenilmesi gereken kurallar getirir. Bu iki platformu anlamak, sadece sözdizimi öğrenmek değil, işletim sisteminin kaynak yönetimi felsefesini ve derleyici/runtime'in bellek modelini kavramaktır.
