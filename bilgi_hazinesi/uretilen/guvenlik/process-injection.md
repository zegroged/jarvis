# Process Injection Teknikleri

## Tanım

**Process injection** (süreç enjeksiyonu), bir saldırganın kendi kötü amaçlı kodunu, kendisine ait olmayan ve halihazırda çalışan başka bir sürecin (process) adres alanı içine yerleştirip o sürecin bağlamında (context) çalıştırdığı tekniklerin genel adıdır. Amaç, kodu meşru bir sürecin kimliği ve güven ilişkileri altında icra etmektir.

Bu teknik ailesi, saldırgan açısından birkaç somut kazanç sağlar. Birincisi **kaçınma (evasion)**: kötü amaçlı kod `explorer.exe`, `svchost.exe` veya bir tarayıcı gibi güvenilir bir sürecin içinde çalıştığında, süreç listesine bakan bir analist ya da basit bir tespit kuralı için görünmez hale gelir. İkincisi **yetki/erişim devralma**: hedef süreç belli bir kullanıcı bağlamında, belli token'larla ya da belli ağ bağlantılarıyla çalışıyorsa, enjekte edilen kod bu bağlamı bedavaya miras alır. Üçüncüsü **kalıcılık ve gizlilik**: diske kötü amaçlı bir çalıştırılabilir bırakmadan, yalnızca bellekte yaşayan (fileless / memory-resident) bir varlık kurmak mümkün olur.

Process injection'ı MITRE ATT&CK çerçevesi tek bir üst teknik (T1055) altında toplar; altında DLL injection, process hollowing, thread execution hijacking, APC injection gibi alt teknikleri sıralar. Aşağıda bu ailenin en önemli üyelerini kök nedenleriyle birlikte ele alacağız.

## Kök Neden: Neden Process Injection Mümkün?

Bir teknik ailesinin savunmasını tasarlayabilmek için önce onun *neden var olduğunu* anlamak gerekir. Process injection, modern işletim sistemlerinin üç temel tasarım gerçeğinin doğal bir yan ürünüdür.

**Birincisi, süreçler arası bellek erişimi bilinçli olarak desteklenen bir özelliktir.** Windows, bir sürecin başka bir sürecin belleğini okumasına, yazmasına ve o süreçte iş parçacığı (thread) yaratmasına izin veren bir API yüzeyi sunar: `OpenProcess`, `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread` gibi çağrılar bunun için vardır. Bu API'ler kötü niyet için değil, hata ayıklayıcılar (debugger), profil çıkarıcılar, erişilebilirlik araçları ve ana-alt süreç (parent-child) etkileşimi gerektiren meşru yazılımlar için tasarlandı. Saldırgan yeni bir kapı açmaz; zaten açık olan meşru kapıyı kullanır. Bu yüzden process injection'ın "kök nedeni" bir güvenlik açığı (vulnerability) değil, bir *tasarım özelliğinin kötüye kullanımıdır* — ve bu ayrım savunma stratejisini baştan sona belirler.

**İkincisi, kod ve veri aynı adres alanında yaşar.** Von Neumann mimarisinin doğrudan bir sonucu olarak, belleğe yazılan baytlar hem veri hem de çalıştırılabilir talimat olabilir. Bir bölgeye kod yazıp o bölgeyi çalıştırılabilir (executable) işaretlemek, işletim sistemi için sıradan bir istektir. DEP/NX (Data Execution Prevention) gibi korumalar "veri olarak ayrılan bölge çalıştırılamaz" kuralını getirse de, saldırgan bölgeyi baştan `PAGE_EXECUTE_READWRITE` gibi bir izinle ayırır ya da sonradan `VirtualProtect` ile korumayı gevşetir. Yani bellek koruması enjeksiyonu tamamen imkânsız kılmaz, yalnızca belirli izleri gözlemlenebilir hale getirir.

**Üçüncüsü, işletim sistemi güveni sürece göre değil, token'a ve kullanıcıya göre atar.** Bir süreç bir kez `WINWORD.EXE` olarak başlatıldığında, işletim sistemi onun içinde çalışan her thread'e aynı güveni verir; o thread'in kodunun aslında kim tarafından yazıldığını sorgulamaz. Kod imzalama (code signing) yalnızca *diskteki dosyanın* imzasını doğrular; bellekte sonradan belirmiş baytların imzası yoktur. Bu boşluk, enjekte edilen kodun "imzalı sürecin çocuğu" gibi davranmasına imkân verir.

Bu üç gerçek birleştiğinde ortaya çıkan sonuç şudur: enjeksiyonu bütünüyle yasaklamak, meşru araç ekosistemini kırmak anlamına gelir. Bu yüzden savunma, enjeksiyonu "yasaklamaya" değil, onun *ayırt edici davranışlarını gözlemlemeye ve kısıtlamaya* dayanır.

## Teknik 1: Klasik DLL Injection

### Çalışma Mantığı

En eski ve en anlaşılır teknik, hedef sürece diskteki (ya da hafızadaki) bir DLL'i yükletmektir. Klasik akış şöyle işler: saldırgan `OpenProcess` ile hedef sürece bir handle açar; `VirtualAllocEx` ile hedefin belleğinde küçük bir bölge ayırır; `WriteProcessMemory` ile bu bölgeye yüklenecek DLL'in *yolunu* (bir metin dizesini) yazar; ardından `CreateRemoteThread` ile hedef süreçte yeni bir thread başlatır ve bu thread'in başlangıç adresi olarak `LoadLibraryA` fonksiyonunun adresini, argümanı olarak da az önce yazdığı yol dizesini verir.

İşin zarafeti şurada: `LoadLibrary` `kernel32.dll` içindedir ve bu DLL neredeyse her süreçte aynı sanal adrese yüklenir. Dolayısıyla saldırganın kendi sürecindeki `LoadLibrary` adresi, hedef süreçteki adresle çoğu durumda aynıdır. Böylece saldırgan hedefe "şu yoldaki DLL'i yükle" komutunu yürütmüş olur ve DLL'in `DllMain` fonksiyonu, hedef sürecin bağlamında kendiliğinden çalışır.

### Somut Örnek ve İstismar Mantığı

Bir Cobalt Strike ya da özel bir loader'ın tipik davranışı: hedef olarak uzun ömürlü, çok sayıda modül yükleyen ve dolayısıyla ek bir DLL'in dikkat çekmeyeceği bir süreç seçmek — örneğin bir tarayıcı ya da bir Office uygulaması. Saldırgan bu süreçte kendi DLL'ini yükleterek, sürecin ağ çıkışına (proxy ayarları, güvenlik duvarı istisnaları) ve kullanıcı token'ına konar. Kırmızı takım açısından bunun cazibesi, teknik olarak basit ve güvenilir olmasıdır.

Zayıflığı da tam burada: **DLL diskten yüklendiği için bir yol izi bırakır** ve `LoadLibrary` çağrısı, yüklenen modülü sürecin modül listesine (PEB'deki loaded-module listesine) ekler. Yani DLL "kayıtlı" bir modül olarak görünür; süreç modüllerini denetleyen herhangi bir araç onu görür. Bu yüzden ileri saldırganlar klasik DLL injection'dan uzaklaşıp aşağıda anlatılan reflective yönteme geçer.

### Savunma

Savunma açısından üç katman vardır. **Birincisi tespit**: `CreateRemoteThread` çağrısının başlangıç adresinin `LoadLibrary` olması, EDR'lar için güçlü bir imzadır — meşru yazılım nadiren başka bir süreçte uzaktan thread yaratıp onu doğrudan `LoadLibrary`'ye yönlendirir. **İkincisi kısıtlama**: Windows'un *Code Integrity Guard* / *Blocked non-Microsoft binaries* politikaları, imzasız ya da beklenmedik DLL'lerin kritik süreçlere yüklenmesini engelleyebilir. **Üçüncüsü sertleştirme**: hassas süreçlerin (ör. LSASS) korumalı süreç (Protected Process Light) olarak çalıştırılması, düşük ayrıcalıklı süreçlerin onlara handle açmasını çekirdek düzeyinde reddeder.

## Teknik 2: Process Hollowing (RunPE)

### Çalışma Mantığı

Process hollowing, adını "içini boşaltma" fikrinden alır. Saldırgan meşru bir çalıştırılabilir dosyayı (ör. `svchost.exe`) **askıya alınmış (suspended)** durumda başlatır. Bu haldeyken sürecin ana thread'i henüz bir talimat çalıştırmamıştır. Saldırgan sonra sürecin bellekteki asıl imajını *boşaltır* — genellikle `NtUnmapViewOfSection` ile orijinal imajın eşlemesini kaldırır — ve o boşluğa kendi kötü amaçlı PE (Portable Executable) imajını yazar. Ardından sürecin thread bağlamını (`GetThreadContext` / `SetThreadContext`) değiştirerek giriş noktasını (entry point) kendi kodunu gösterecek şekilde yeniden yönlendirir ve `ResumeThread` ile süreci başlatır.

Sonuç çarpıcıdır: Süreç adı, komut satırı, ana süreç (parent) ilişkisi ve diskteki imzalı dosya tamamen meşru görünür; ama bellekte çalışan kod tamamen saldırgana aittir. Bu, "meşru bir kabuğun içinde yabancı bir beyin" durumudur.

### Kök Neden

Bu tekniğin mümkün olmasının nedeni, Windows'ta bir sürecin *bellek eşlemesinin* çalıştıktan sonra bile değiştirilebilir olmasıdır. Suspended başlatma özelliği — normalde meşru olarak başlatıcı bir sürecin çocuğunu yapılandırması için var olan bir özellik — saldırgana "süreç doğdu ama henüz yaşamadı" penceresini verir. İşte bu pencere hollowing'in tüm dayanağıdır.

### İstismar ve Savunma

İstismar mantığı, klasik injection'ın disk izi sorununu çözmektir: kötü kod diske hiç düşmez, meşru bir sürecin içinde belirir. Ancak hollowing kendine has, *gözlemlenebilir bir anomali* üretir: sürecin bellekteki imajı ile *diskteki dosyası eşleşmez*. Meşru bir `svchost.exe`'nin bellekteki `.text` bölümü, diskteki dosyanın `.text` bölümüyle bayt bayt aynı olmalıdır (image-backed / dosya destekli bellek). Hollowing'de ise bellekteki kod ya dosya-destekli olmayan (private) bir bölgeye taşınmıştır ya da içeriği diskle uyuşmaz.

Savunma tarafında bu, çok değerli bir tespit kancasıdır. EDR'lar ve bellek adli analizi (memory forensics) araçları — Volatility'nin bu amaca yönelik eklentileri gibi — şu anomalileri arar: (1) sürecin giriş noktasının dosya-destekli olmayan bir bölgeyi göstermesi; (2) çalıştırılabilir ama private (dosyaya bağlı olmayan) bellek bölgeleri; (3) bellekteki imaj ile diskteki dosya arasındaki uyuşmazlık; (4) `NtUnmapViewOfSection` ardından `WriteProcessMemory` ve `SetThreadContext` çağrı zincirinin bir arada görülmesi. Ayrıca ana-alt süreç ilişkisi mantıksızsa (ör. `WINWORD.EXE`'nin çocuğu olarak beliren bir `svchost.exe`) bu da güçlü bir sinyaldir.

## Teknik 3: Reflective DLL Injection

### Çalışma Mantığı

Klasik DLL injection'ın en büyük zaafı, `LoadLibrary`'ye bağımlı olması ve dolayısıyla DLL'i diske yazıp modül listesine kaydettirmesiydi. **Reflective DLL injection** bu bağımlılığı ortadan kaldırır: DLL'i işletim sisteminin yükleyicisine (loader) hiç sormadan, DLL'in *kendisi* kendini belleğe yükler.

Bunun için DLL'e küçük bir *reflective loader* fonksiyonu gömülür. Saldırgan DLL'in ham baytlarını hedef sürecin belleğine yazdıktan sonra, bu loader fonksiyonunu çalıştırır. Loader şunları elle yapar: PE başlıklarını ayrıştırır; DLL'i doğru hizada belleğe yerleştirir; **relocation** (yeniden konumlandırma) düzeltmelerini uygular; **import** tablosunu gezerek gereken fonksiyonların adreslerini (`GetProcAddress` benzeri bir mantıkla) çözer; ve son olarak `DllMain`'i çağırır. Bütün bu iş, `LoadLibrary`'yi hiç kullanmadan, DLL bir dosya olarak diskte hiç bulunmadan yapılır.

### Neden Bu Kadar Etkili?

Fark, tespit yüzeyinde ortaya çıkar. Reflective yöntemde DLL işletim sisteminin loaded-module listesine *eklenmez*; çünkü onu ekleyen mekanizma (`LoadLibrary`) hiç çalışmamıştır. Yani süreç modüllerini listeleyen klasik bir araç, orada bir DLL göremez. Bu teknik, in-memory / fileless saldırıların temel taşıdır ve Meterpreter gibi payload'ların uzun süre bu yöntemle yayılmasının sebebidir.

### Savunma

Reflective injection modül listesinden kaçsa da, bellekteki fiziksel izinden kaçamaz. Bir yerde çalıştırılabilir, dosya-destekli olmayan (private, RX ya da RWX) bir bellek bölgesi vardır ve o bölge geçerli bir PE başlığı içerir. Savunma bunu hedefler:

- **Bellek taraması**: EDR'lar süreçlerin private + executable bölgelerini periyodik olarak tarar ve bu bölgelerin başında `MZ`/`PE` imzası, şüpheli şablonlar (shellcode desenleri) arar.
- **RWX bölge tespiti**: Meşru kod nadiren hem yazılabilir hem çalıştırılabilir (RWX) bir bölgeye ihtiyaç duyar. RWX bir private bölge, tek başına yüksek şüphe uyandırır.
- **API telemetrisi**: `VirtualAllocEx` ile RWX bölge ayrılması, ardından `WriteProcessMemory` ve uzak bir thread'in bu bölgeye girmesi zinciri izlenir.
- **ETW ve AMSI**: Modern Windows'ta bellek içi kodun taranmasını sağlayan mekanizmalar (AMSI, ETW üzerinden .NET ve script yüklemeleri) reflective yüklenen yönetilen (managed) kodu bile görünür kılabilir; bu yüzden saldırganlar sıklıkla AMSI/ETW'yi devre dışı bırakmaya çalışır — ve bu devre dışı bırakma girişiminin *kendisi* güçlü bir tespit sinyalidir.

## Teknik 4: APC Injection (Asynchronous Procedure Call)

### Çalışma Mantığı

APC injection, kod çalıştırmak için `CreateRemoteThread` gibi gürültülü bir yol yerine, Windows'un **Asynchronous Procedure Call (APC)** mekanizmasını kullanır. Windows'ta her thread'in bir APC kuyruğu vardır; bu kuyruğa konan fonksiyonlar, thread *alertable* (uyarılabilir) bir bekleme durumuna girdiğinde otomatik olarak çalıştırılır. Bir thread `SleepEx`, `WaitForSingleObjectEx`, `MsgWaitForMultipleObjectsEx` gibi çağrılarla alertable bekleme durumuna girer.

Saldırgan hedef sürecin mevcut bir thread'ini seçer, belleğine kendi kodunu (shellcode) yazar ve `QueueUserAPC` ile bu koda işaret eden bir APC'yi thread'in kuyruğuna ekler. Thread bir sonraki alertable bekleme anında saldırganın kodunu çalıştırır. Böylece *yeni bir thread yaratılmaz* — ki bu, `CreateRemoteThread`'e dayalı tespitlerden kaçmanın yoludur.

### Early Bird Varyantı

Özellikle etkili bir varyant, kodu bir sürecin thread'i *ilk talimatını çalıştırmadan önce* kuyruğa koymaktır. Saldırgan bir süreci suspended başlatır, ana thread'ine bir APC kuyruklar ve thread'i devam ettirir. Windows'ta ana thread, kullanıcı kodundan önce yükleyici başlatma aşamasında zaten alertable bir noktadan geçer; bu nedenle enjekte edilen APC, sürecin asıl kodu ve dolayısıyla güvenlik ürünlerinin kancaları (hook) tam olarak devreye girmeden çalışabilir. Bu erken pencere, "Early Bird" adını taşır ve birçok güvenlik ürününün geç kurulan kancalarını atlatmayı hedefler.

### Savunma

APC injection, thread yaratmadığı için `CreateRemoteThread` odaklı tespitleri atlar; ama başka izler bırakır. `QueueUserAPC` çağrısının kendisi, özellikle *başka bir sürecin* thread'ine yapıldığında, EDR telemetrisinde nadir ve dikkat çekicidir. Bunun `WriteProcessMemory` ve RWX bir hedef bölgeyle birlikte görülmesi güçlü bir korelasyon oluşturur. Early Bird varyantına karşı, suspended başlatılan süreçlerin ve onlara yapılan bellek yazımlarının izlenmesi kritiktir. Ayrıca güvenlik ürünlerinin kancalarını *çekirdek düzeyinde* (kernel callback'ler, ör. process/thread yaratma bildirimleri) kurması, kullanıcı modundaki Early Bird kancasız penceresini kapatmaya yardımcı olur.

## Diğer Önemli Varyantlar (Kısaca)

- **Thread Execution Hijacking (Suspend-Inject-Resume)**: Var olan bir thread `SuspendThread` ile durdurulur; `GetThreadContext` ile mevcut talimat işaretçisi (instruction pointer, RIP) okunur; shellcode belleğe yazılır ve `SetThreadContext` ile RIP saldırganın koduna çevrilir; `ResumeThread` ile thread saldırganın kodunu çalıştırmaya başlar. Yeni thread yaratmadan var olanı "kaçırır".
- **PE Injection**: Reflective mantığa benzer biçimde, bir PE imajı diske hiç yazılmadan doğrudan başka bir sürecin belleğine kopyalanır ve elle çözümlenerek çalıştırılır.
- **Atom Bombing / benzeri veri-kanalı teknikleri**: Windows'un global atom tablosu gibi meşru IPC mekanizmaları, shellcode'u hedef sürece "meşru" bir kanaldan taşımak için kötüye kullanılır; ardından APC gibi bir tetikleyiciyle çalıştırılır. Amaç, `WriteProcessMemory` gibi doğrudan yazma çağrılarından bile kaçınmaktır.
- **Process Doppelgänging / Ghosting**: Windows'un işlem (transaction) tabanlı dosya sistemi (TxF) ya da silinmekte olan dosyalardan imaj oluşturma davranışı kötüye kullanılarak, güvenlik ürünlerinin tarayamadığı geçici bir dosyadan süreç oluşturulur. Amaç, hollowing'in disk-bellek uyuşmazlığı izini bile ortadan kaldırmaktır.

Bu varyantların ortak evrimsel çizgisi nettir: her yeni teknik, bir öncekinin bıraktığı *belirli bir tespit izini* kapatmaya çalışır. Klasik injection disk izi bırakır → reflective onu siler; hollowing disk-bellek uyuşmazlığı bırakır → doppelgänging onu maskeler; `CreateRemoteThread` gürültü yapar → APC ve thread hijacking onu atlar. Savunmacının işi bu koşuyu görüp *değişmeyen* ortak paydaları (bellek anomalisi, süreç ilişkisi anomalisi, çekirdek düzeyi olay zincirleri) yakalamaktır.

## Tespit: Katmanlı Bir Bakış

Tek bir sihirli tespit yoktur; sağlam tespit birbirini destekleyen katmanlardan oluşur.

**API/davranış korelasyonu.** En verimli katman, tek tek çağrıları değil *zincirleri* izler. `OpenProcess` (yazma/thread hakkıyla) → `VirtualAllocEx` (RX/RWX) → `WriteProcessMemory` → `CreateRemoteThread` / `QueueUserAPC` / `SetThreadContext` zinciri, klasik enjeksiyon parmak izidir. Bu çağrıların *cross-process* (bir sürecin başka bir sürece) yapılması, meşru yazılımda enderdir ve şüpheyi katlar.

**Bellek anomalisi taraması.** Enjeksiyon türü ne olursa olsun, kod eninde sonunda bellektedir. Dosya-destekli olmayan (private) + çalıştırılabilir bölgeler, özellikle RWX olanlar, taranmalıdır. Bu bölgelerin başında PE/shellcode desenleri aranır; sürecin giriş noktasının ya da aktif thread'lerin başlangıç adreslerinin dosya-destekli olmayan bölgeleri göstermesi anomalidir. Bellek adli analizi araçları (Volatility ve türevleri) bu anomalileri offline imajlarda da yakalar.

**Süreç köken (provenance) ve ilişki analizi.** Beklenmeyen ana-alt ilişkiler (ör. bir Office uygulamasının bir sistem ikilisini doğurması), imzalı ama bellekteki içeriği kendi diskindeki dosyayla uyuşmayan süreçler, komut satırı boş olması gereken yerde dolu (ya da tersi) olan süreçler güçlü ipuçlarıdır.

**Çekirdek telemetrisi (ETW, kernel callback'ler).** Kullanıcı modu kancaları saldırgan tarafından kaldırılabilir (unhooking) ya da Early Bird ile atlanabilir. Bu yüzden ciddi tespit, süreç/thread/imaj-yükleme olaylarını *çekirdekten* bildiren mekanizmalara dayanır. Bu telemetri, saldırganın kullanıcı modundaki oyunundan bağımsızdır ve manipülasyonu çok daha zordur.

## Yaygın Hatalar

**Savunmacı tarafında:**

- **Yalnızca disk imzalarına güvenmek.** Reflective ve fileless teknikler tam olarak disk tabanlı antivirüsü atlamak için vardır. Bellek görünürlüğü olmayan bir savunma, en yaygın modern enjeksiyona kördür.
- **Yalnızca `CreateRemoteThread` aramak.** Bu, ailenin en eski üyesidir. APC, thread hijacking ve manuel loader'lar bu tek imzayı rutin olarak atlar. Tek bir API'ye kilitlenmiş kural, sahte bir güven duygusu verir.
- **Kritik süreçleri sertleştirmemek.** LSASS gibi süreçleri Protected Process olarak çalıştırmamak, `Credential Guard`'ı etkinleştirmemek, saldırgana hem hedef hem araç sunar.
- **AMSI/ETW manipülasyonunu izlememek.** Saldırganların bu telemetriyi susturma girişimi, aslında en yüksek değerli erken uyarı sinyallerinden biridir; bunu izlememek bir fırsatı kaçırmaktır.

**Kırmızı takım / araştırmacı tarafında (kavramsal hatalar):**

- **RWX bellek kullanmak.** RWX bir private bölge, avcı için parlayan bir işaret fişeğidir. Olgun teknikler bellek izinlerini ihtiyaç anına göre (önce RW ile yaz, sonra RX'e çevir) ayarlayarak bu izi azaltır — bu ayrım tekniğin ne kadar "gürültülü" olduğunu belirler.
- **Süreç ilişkisini mantıksız bırakmak.** Enjeksiyon başarılı olsa bile, mantıksız bir parent-child zinciri tekniği ele verir. Kaçınmanın yükü yalnızca enjeksiyon anında değil, sonrasındaki bütün davranıştadır.

## En İyi Pratikler (Savunma Odaklı)

1. **En küçük ayrıcalık (least privilege) ve saldırı yüzeyi azaltma.** Kullanıcıları ve servisleri gereksiz `SeDebugPrivilege` gibi haklardan yoksun bırakın; enjeksiyon için gereken cross-process handle'ları açma yeteneği çoğu hesap için gereksizdir.

2. **Kritik süreçleri sertleştirin.** LSASS'ı korumalı süreç olarak çalıştırın, Credential Guard'ı devreye alın; hassas servisleri mümkün olduğunca kısıtlı bütünlük düzeylerinde tutun. Attack Surface Reduction (ASR) kurallarıyla Office gibi uygulamaların süreç enjeksiyonu ve alt süreç doğurma davranışlarını engelleyin.

3. **Bellek görünürlüğü olan EDR kullanın.** Yalnızca dosya taraması yapan değil; private/executable bellek bölgelerini tarayan, API çağrı zincirlerini koreleye eden ve çekirdek telemetrisine dayanan bir çözüm şart. Bir EDR'ın enjeksiyona karşı değeri, doğrudan bellek görünürlüğüyle ölçülür.

4. **Çekirdek düzeyi telemetriyi merkeze koyun.** Kullanıcı modu kancaları atlatılabildiği için, ETW ve kernel callback tabanlı süreç/thread/imaj olaylarını toplayın ve merkezî olarak korelasyon kurun. Bu, Early Bird ve unhooking gibi gelişmiş kaçınmalara karşı temel dayanaktır.

5. **AMSI/ETW/güvenlik ürünü manipülasyonunu bir olay olarak izleyin.** Bu bileşenlerin devre dışı bırakılma girişimlerini yüksek öncelikli alarma bağlayın; bunlar enjeksiyonun kendisinden bile daha erken uyarı verebilir.

6. **Anomali temelli avcılık (threat hunting) yapın.** Kural tabanlı tespiti, "imzalı ama bellekte-diskle-uyuşmayan süreç", "dosya-destekli olmayan başlangıç adresine sahip thread", "beklenmedik parent-child zinciri" gibi anomali sorgularıyla düzenli olarak tamamlayın. Enjeksiyon ailesi hızla evrildiği için, imza avcılığının tek başına yetmediği yer burasıdır.

7. **Uygulama kontrolü (application control).** WDAC / AppLocker gibi mekanizmalarla imzasız ve beklenmedik ikililerin ve DLL'lerin yüklenmesini kısıtlamak, klasik ve bazı reflective senaryolarda yükleme kanalını daraltır.

Özetle, process injection'a karşı savunmanın kalbinde şu kavrayış yatar: **bu teknikler bir hatayı değil, işletim sisteminin meşru esnekliğini sömürür.** Bu yüzden onları tek bir yamayla kapatamayız. Bunun yerine, ailenin değişse de kaybolmayan ortak izlerini — belleğe belirmiş yabancı kodu, mantıksız süreç ilişkilerini ve manipüle edilen güvenlik telemetrisini — çok katmanlı, çekirdeğe dayanan bir görünürlükle avlamamız gerekir.
