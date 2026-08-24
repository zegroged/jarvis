# Gömülü Sistemler ve RTOS: Bare-Metal Programlama ve Gerçek Zamanlı İşletim Sistemleri

## Giriş: Neden Bu Konu Farklı Düşünmeyi Gerektirir

Masaüstü veya sunucu tarafı yazılım geliştirme, altında zengin bir işletim sistemi (Linux, Windows) olduğunu varsayar: sanal bellek, çöp toplama (garbage collection) yoksa bile bol miktarda heap, önleyici (preemptive) çok görevlilik, dosya sistemi, ve hata durumunda "process çöker, OS temizler" güvencesi vardır. Gömülü sistemler dünyasında bu varsayımların çoğu ya yoktur ya da tam tersi geçerlidir. Bir mikrodenetleyici (microcontroller) üzerinde çalışan firmware, birkaç KB RAM ile, MMU (Memory Management Unit) olmadan, çoğu zaman heap tahsisi olmadan, ve "az önce bir donanım kesmesi geldi, 2 mikrosaniye içinde cevap vermezsen bir motor yanacak" gibi zaman garantileriyle çalışır.

Bu makale, gömülü sistemlerin savunma ve güvenlik mühendisliği açısından neden önemli olduğunu, bare-metal (işletim sistemi olmadan doğrudan donanım üzerinde) programlamanın kök nedenlerini, RTOS'un (Real-Time Operating System) çözdüğü problemi ve bu ortamlarda ortaya çıkan kendine özgü güvenlik açıklarını ele alır. Amaç, bir güvenlik mühendisinin veya firmware geliştiricisinin "bu sistem neden böyle davranıyor" sorusuna cevap verebilmesidir.

## Bare-Metal Programlama Nedir, Neden Var

"Bare-metal" terimi, işlemci üzerinde bir işletim sistemi katmanı olmadan, yazılımın doğrudan donanım kayıtlarını (registers) programladığı modeli tanımlar. Kök neden ekonomiktir: bir mikrodenetleyici (örneğin bir ARM Cortex-M serisi çip) genellikle birkaç on KB ile birkaç MB arası flash bellek ve çok daha az RAM'e sahiptir. Bir Linux çekirdeği bile bu kaynaklara sığmaz; sığsa da açılış (boot) süresi ve enerji tüketimi kabul edilemez olur. Bu yüzden basit görevler (bir sensörü okumak, bir motoru sürmek, bir LED'i yakıp söndürmek) için işletim sistemi maliyetine katlanmak anlamsızdır.

### Bare-Metal'in Çalışma Mantığı

Güç verildiğinde (power-on / reset), işlemci belirli bir bellek adresinden (reset vector) yürütmeye başlar. Bu adreste genellikle bir "başlatma kodu" (startup code / crt0 benzeri) bulunur: yığın işaretçisini (stack pointer) ayarlar, `.bss` bölümünü (başlangıç değeri olmayan global değişkenler) sıfırlar, `.data` bölümünü (başlangıç değeri olan globaller) flash'tan RAM'e kopyalar, ve sonunda `main()` fonksiyonuna atlar. Bu noktadan sonra tipik bir bare-metal program şu iki desenden birini kullanır:

1. **Süper-döngü (super-loop) modeli**: `while(1) { sensörü_oku(); karar_ver(); aktüatörü_sür(); }` şeklinde sonsuz bir ana döngü. Basit, öngörülebilir, ama tüm görevler sırayla çalıştığı için biri yavaşlarsa diğerleri gecikir.
2. **Kesme güdümlü (interrupt-driven) model**: Ana döngü çoğunlukla uyku (sleep/idle) modunda bekler; gerçek iş, donanım kesmeleri (interrupt) tetiklendiğinde Kesme Servis Rutinlerinde (ISR - Interrupt Service Routine) yapılır.

### Kesme İşleme (Interrupt Handling): Kök Mekanizma

Kesmeler, gömülü sistemlerin "gerçek zamanlılığının" temelidir. Bir donanım olayı (bir buton basımı, bir UART'a veri gelmesi, bir zamanlayıcının dolması) olduğunda, işlemci o an yürüttüğü kodu durdurur, mevcut bağlamı (context: register'lar, program sayacı) otomatik veya yazılımla kaydeder, önceden tanımlanmış bir ISR adresine dallanır, ISR'ı çalıştırır, ve sonra kesintiye uğrayan koda geri döner.

Neden bu kadar kritik? Çünkü CPU'nun sürekli "veri geldi mi diye soru sorması" (polling) hem CPU zamanını israf eder hem de gecikmeyi artırır. Kesmeler, olay olduğunda anında (donanımın izin verdiği en kısa sürede) tepki verir. Ancak bu, ciddi tuzaklar da getirir:

- **ISR'lar kısa ve deterministik olmalı**: Bir ISR içinde uzun süren işlem (örneğin bir döngü, bir I/O bekleme) yaparsanız, o kesme seviyesindeki (veya daha düşük öncelikli) diğer tüm kesmeler bekler — buna **kesme gecikmesi (interrupt latency)** denir. Bir motor kontrol sisteminde ISR'ın 10 mikrosaniyeden uzun sürmesi, bir sonraki PWM (Pulse Width Modulation) güncellemesini kaçırıp fiziksel hasara yol açabilir.
- **Re-entrancy ve yarış koşulları (race conditions)**: Ana döngü bir global değişkeni güncellerken bir kesme araya girip aynı değişkeni değiştirirse, veri bozulur (data race). Bu, "atomic access" gerektiren klasik bir problemdir; çözüm genellikle kritik bölgelerde kesmeleri geçici olarak kapatmaktır (`disable_interrupts()` / `enable_interrupts()`), ama bu da kesme gecikmesini artırır — klasik bir mühendislik dengelemesi (trade-off).
- **Kesme önceliklendirme (interrupt priority/nesting)**: Çoğu mikrodenetleyicide kesmelerin öncelik seviyeleri vardır; yüksek öncelikli bir kesme, düşük öncelikli birinin ISR'ını kesebilir (nested interrupts). Yanlış yapılandırılmış öncelikler, düşük öncelikli ama kritik bir görevin (örneğin bir güvenlik kesme sinyali) sonsuza kadar ertelenmesine (starvation) yol açabilir.

## RTOS'un Çözdüğü Problem: Zamanlama Garantisi

Süper-döngü modeli büyüdükçe (10'larca görev, karmaşık bağımlılıklar) yönetilemez hale gelir. Bir **RTOS (Real-Time Operating System)** — FreeRTOS, Zephyr, VxWorks, QNX gibi — bu karmaşıklığı, her biri kendi yığınına (stack) sahip bağımsız "task" (görev) veya "thread" soyutlamasıyla yönetir ve bir zamanlayıcı (scheduler) bu görevler arasında CPU zamanını paylaştırır.

### Gerçek Zamanlılığın Anlamı: Hız Değil, Determinizm

Yaygın bir yanlış anlama: "gerçek zamanlı" = "hızlı" demek değildir. Gerçek zamanlılık, bir görevin **garantili bir son tarihe (deadline) kadar** tamamlanacağının **matematiksel olarak kanıtlanabilir** olmasıdır. Bir "hard real-time" sistemde (örneğin bir hava yastığı kontrolcüsü), deadline'ın kaçırılması sistem hatası sayılır — ne kadar nadir olursa olsun kabul edilemez. "Soft real-time" sistemlerde (örneğin video akışı) ara sıra kaçırılan deadline performans düşüşüne yol açar ama felaket değildir.

Bu yüzden RTOS zamanlayıcıları genellikle **önceliğe dayalı önleyici zamanlama (priority-based preemptive scheduling)** kullanır: her göreve sabit bir öncelik atanır, zamanlayıcı her zaman en yüksek öncelikli "çalışabilir" (ready) görevi çalıştırır, ve daha yüksek öncelikli bir görev hazır hale gelirse (örneğin bir kesme onu uyandırırsa), düşük öncelikli olan anında kesilir (preempt edilir).

### Kök Neden Analizi: Zamanlanabilirlik (Schedulability) Teorisi

RTOS tasarımının temelinde şu soru yatar: "N görev, belirli periyot ve yürütme süreleriyle, hepsi deadline'larını kaçırmadan tek bir CPU'da çalışabilir mi?" Bunun cevabı **Rate Monotonic Scheduling (RMS)** gibi analitik modellerle verilir: kısa periyotlu görevlere yüksek öncelik verilirse ve toplam CPU kullanımı belirli bir eşiğin (yaklaşık %69, Liu & Layland sınırı) altındaysa, tüm deadline'ların karşılanacağı matematiksel olarak garanti edilir. Bu, gömülü mühendisliğin "deneyerek görürüz" değil "kanıtla" yaklaşımının özüdür.

### Öncelik Ters Dönmesi (Priority Inversion): Klasik Tuzak

Bir düşük öncelikli görev bir kaynağı (mutex/semaphore ile korunan bir kaynak) kilitlerken, orta öncelikli bir görev onu keserse ve yüksek öncelikli bir görev de aynı kilidi bekliyorsa, yüksek öncelikli görev — teorik olarak en önemli görev — dolaylı olarak orta öncelikli görev tarafından süresiz bloke edilebilir. Bu fenomen **priority inversion** olarak bilinir ve gerçek dünyada meşhur bir olayla ilişkilendirilir: 1997'de Mars Pathfinder görevinde yazılım periyodik olarak yeniden başlıyordu; kök neden tam olarak buydu. Çözüm, **priority inheritance** (kilidi tutan düşük öncelikli görevin, geçici olarak onu bekleyen en yüksek önceliğe yükseltilmesi) gibi protokollerdir. Modern RTOS'ların çoğu mutex implementasyonunda bunu varsayılan olarak sunar, ama yanlış API kullanımı (örneğin sıradan bir semaphore'u mutex yerine kullanmak) bu korumayı devre dışı bırakabilir.

## Bellek Kısıtlı Ortamlarda Güvenlik: Stack ve Heap Sorunu

Gömülü sistemlerin güvenlik profili, masaüstü/sunucu dünyasından köklü biçimde farklıdır çünkü savunma katmanlarının çoğu (ASLR, DEP/NX, sanal bellek izolasyonu, MMU tabanlı process ayrımı) ya yoktur ya da opsiyoneldir.

### Heap Yokluğu veya Kısıtlılığı

Birçok firmware, dinamik bellek tahsisini (`malloc`/`free`) tamamen yasaklar veya çok sınırlı kullanır. Kök neden: heap parçalanması (fragmentation). Uzun süre (aylarca, yıllarca kesintisiz) çalışması beklenen bir gömülü cihazda, tekrarlanan malloc/free döngüleri belleği parçalayabilir; sonunda toplam boş bellek yeterli olsa bile büyük bir bitişik blok bulunamaz ve tahsis başarısız olur. Bir masaüstü uygulamasında bu bir çökme ve yeniden başlatmayla çözülür; bir kalp pili veya uçak kontrol sisteminde bu kabul edilemez. Bu yüzden yaygın pratik: statik tahsis (compile-time'da boyutu belli diziler) veya sabit boyutlu havuz tahsisi (memory pool / fixed-size block allocator) kullanmaktır — çalışma zamanında tahsis/serbest bırakma olur ama parçalanma riski olmadan, çünkü tüm bloklar aynı boyuttadır.

### Stack Taşması (Stack Overflow) — Farklı Bir Tehdit Modeli

Masaüstünde bir stack overflow genellikle bir process'i çökertir (segmentation fault) ve OS bunu izole eder. Gömülü sistemde çoğu zaman **tüm görevler ve hatta çekirdek (kernel) aynı fiziksel adres alanını, MMU koruması olmadan paylaşır**. Bir görevin stack'i taşarsa, bitişik bellekteki başka bir görevin stack'ine, global değişkenlere, hatta kesme vektör tablosuna yazabilir — bu sessiz bir bellek bozulmasıdır (memory corruption), çoğu zaman çökme bile üretmez, sadece garip ve izlenmesi imkansız davranışlara yol açar.

Kök nedenler:
- Derin fonksiyon çağrı zincirleri veya rekürsiyon (recursion) — gömülü kodda rekürsiyon genellikle "en iyi pratik" listesinde yasaklıdır çünkü çağrı derinliği çalışma zamanında veriye bağlı olabilir ve statik analiz edilemez.
- Her RTOS görevine ayrılan stack boyutunun yanlış tahmin edilmesi (çok küçük ayrılırsa taşar, çok büyük ayrılırsa toplam RAM tükenir).
- ISR'ların kendi stack alanı yerine kesintiye uğrattıkları görevin stack'ini kullanması (bazı mimarilerde varsayılan budur), ISR'ın derin çağrı yapması durumunda o görevin stack'ini de taşırabilmesi.

**Savunma pratikleri**: Stack kullanımını derleme zamanında statik analiz araçlarıyla (worst-case stack usage analysis) tahmin etmek; RTOS'ların sunduğu "stack watermark/high-water-mark" API'leriyle çalışma zamanında gerçek kullanılan stack derinliğini izlemek; stack'in sonuna "guard bölgesi" (canary/guard pattern — bilinen bir bit deseniyle doldurulmuş bölge) koyup periyodik olarak bu desenin bozulup bozulmadığını kontrol etmek; MPU (Memory Protection Unit — MMU'nun daha basit, sayfalama yapmayan kardeşi) destekleyen çiplerde her görev stack'inin etrafına donanımsal erişim sınırları koymak.

### Neden Klasik İstismar Teknikleri Burada Daha Tehlikeli Olabilir

Bir buffer overflow, masaüstünde ASLR + stack canary + DEP/NX + process izolasyonu gibi birçok savunma katmanıyla karşılaşır. Kaynağı kısıtlı bir mikrodenetleyicide bu katmanların çoğu ya yoktur (ASLR anlamsızdır çünkü bellek haritası sabittir ve genellikle kamuya açık bir datasheet'te belgelidir) ya da performans/bellek maliyeti nedeniyle kapatılmıştır. Bu, aynı sınıf zafiyetin (örneğin bir UART üzerinden gelen komut ayrıştırıcısındaki bir buffer overflow) gömülü bir cihazda çok daha doğrudan ve güvenilir bir şekilde istismar edilebilir hale gelmesi anlamına gelir. Bu yüzden gömülü kodda girdi doğrulama (input validation) ve sınır kontrolü (bounds checking) disiplini, savunma katmanlarının yokluğunu telafi eden **tek** hat olabilir.

## Firmware Güvenliği: Secure Boot, UEFI, TPM ile Kesişim ve Ayrım

Soru bağlamında belirtildiği gibi bu konu ICS/OT (Industrial Control Systems / Operational Technology) başlığıyla kısmen örtüşür ama farklıdır: ICS/OT, gömülü cihazların *endüstriyel süreçlerde kullanımının* güvenliğine odaklanırken, burada firmware'in *kendisinin* bütünlüğü ele alınır.

### Secure Boot'un Kök Mantığı

Bir cihaz açıldığında, ilk çalıştırdığı kodun (bootloader) meşru ve değiştirilmemiş olduğunu nasıl bilebilir? **Secure boot**, bir "güven zinciri" (chain of trust) kurar: çipin üzerine üretim sırasında yakılmış, değiştirilemez bir ilk aşama (genellikle salt-okunur bir ROM, "Root of Trust") bir sonraki aşamanın (bootloader) kriptografik imzasını, çipe gömülü bir açık anahtar (veya bu anahtarın hash'i) ile doğrular. Doğrulama başarılıysa çalıştırır ve bu aşama da bir sonrakini (işletim sistemi/uygulama firmware'i) doğrular — böylece her halka bir sonrakini doğrulayan bir zincir oluşur. Zincirin herhangi bir halkası atlanır veya devre dışı bırakılırsa (downgrade / bypass), tüm zincir anlamsızlaşır.

Kök neden/tehdit modeli: fiziksel erişimi olan bir saldırgan, firmware'i kötü niyetli bir sürümle değiştirip cihazı kalıcı olarak ele geçirebilir (persistent implant). Secure boot bunu, imzasız veya geçersiz imzalı kodun çalışmasını reddederek engeller.

### UEFI ve TPM ile İlişki (ve Nerede Farklılaşır)

**UEFI (Unified Extensible Firmware Interface)**, kişisel bilgisayar/sunucu dünyasında BIOS'un yerini almış, kendi "Secure Boot" mekanizmasına sahip bir firmware arayüzü standardıdır — burada bahsedilen zincir mantığı UEFI Secure Boot'ta da aynıdır (Microsoft/OEM imzalı bootloader'lar, imza veritabanları — db/dbx). **TPM (Trusted Platform Module)**, bu güveni ölçüp saklayan ayrı bir donanım bileşenidir: her önyükleme aşaması, bir sonrakini çalıştırmadan önce onun hash'ini TPM'in PCR (Platform Configuration Register) kayıtlarına "genişletir" (extend) — bu tek yönlü bir işlemdir, geriye alınamaz. Böylece TPM, "bu makine tam olarak beklenen yazılım yığınıyla açıldı" iddiasını uzaktan kanıtlanabilir hale getirir (remote attestation).

Küçük bir mikrodenetleyicide (bir sensör düğümü, bir IoT cihazı) tam bir TPM veya UEFI genellikle yoktur — bunlar PC-sınıfı donanım için tasarlanmıştır. Bunun yerine gömülü dünya benzer güvenceleri çok daha hafif mekanizmalarla sağlar: çipe gömülü tek kullanımlık yakılabilir anahtar depoları (OTP fuses / eFUSE), donanım kriptografik hızlandırıcılar, ve ARM TrustZone gibi "güvenli dünya / güvenli olmayan dünya" ayrımı yapan mimari uzantılar. Kavramsal olarak amaç aynıdır (değiştirilemez bir kök güven + kriptografik doğrulama zinciri) ama uygulama, kaynak kısıtları nedeniyle çok daha minimalisttir.

### Yaygın Firmware Güvenlik Hataları

- **Geri alınabilir (downgrade edilebilir) secure boot**: Eski, bilinen zafiyetli bir firmware sürümüne "geri yükseltmeye" (downgrade) izin verilmesi — imza geçerli ama sürüm eski olduğu için bilinen bir açığı yeniden açar. Savunma: sürüm numarası izleme (anti-rollback counter), genellikle OTP fuse'larda tutulur.
- **Debug arayüzlerinin (JTAG/SWD) üretimde açık bırakılması**: Geliştirme sırasında hata ayıklama için kullanılan bu donanım arayüzleri, üretime giden cihazlarda kapatılmaz/kilitlenmezse, fiziksel erişimi olan biri belleği doğrudan okuyup/yazabilir, tüm secure boot zincirini bypass edebilir.
- **Sabit kodlanmış (hardcoded) kriptografik anahtarlar**: Aynı anahtarın tüm cihaz serisinde paylaşılması; bir cihazdan anahtar çıkarılırsa (örneğin side-channel analiziyle veya fiziksel sökme yoluyla) tüm filo (fleet) etkilenir. Savunma: her cihaza üretim sırasında benzersiz anahtar (per-device key) yakmak.
- **Şifrelenmemiş firmware güncellemeleri**: İmza doğrulaması olsa bile (bütünlük), şifreleme olmadan (gizlilik) firmware ağ üzerinden dinlenip tersine mühendislik yapılabilir; bu doğrudan bir zafiyet değildir ama saldırı yüzeyini araştırmayı kolaylaştırır.

## Yaygın Hatalar ve En İyi Pratikler Özeti

**Yaygın hatalar:**
- ISR içinde bloke edici işlemler (uzun döngüler, I/O bekleme) yapmak.
- Kesme/görev arası paylaşılan veriye kilitleme olmadan (veya yanlış kilitleme ile) erişmek — data race.
- Rekürsif fonksiyonlar veya derin/öngörülemez çağrı zincirleriyle stack boyutunu tahmin edilemez kılmak.
- Öncelik miras alma (priority inheritance) desteklemeyen senkronizasyon ilkelleri kullanarak priority inversion riskini görmezden gelmek.
- Debug/JTAG arayüzlerini üretim cihazlarında kilitlemeyi unutmak.
- Girdi doğrulamasını (özellikle seri port / ağ üzerinden gelen komut ayrıştırıcılarında) atlamak — masaüstü savunma katmanları olmadığı için bu tek hat savunma haline gelir.
- Anti-rollback koruması olmadan secure boot kurmak (eski, açık bir sürüme downgrade'e izin vermek).

**En iyi pratikler:**
- Görev/ISR tasarımında "en kötü durum yürütme süresi" (WCET - Worst-Case Execution Time) analiziyle zamanlanabilirliği matematiksel olarak doğrulamak.
- Statik bellek tahsisini tercih etmek; dinamik tahsis şartsa sabit boyutlu havuz (memory pool) kullanmak.
- Her görev stack'i için watermark izleme ve guard bölgeleri kurmak; MPU varsa donanımsal stack sınırları koymak.
- Kritik bölgeleri (critical section) mümkün olduğunca kısa tutmak; kesme devre dışı bırakma süresini minimize etmek.
- Priority inheritance destekleyen mutex'leri kullanmak, sıradan semaphore'ları karşılıklı dışlama (mutual exclusion) için kullanmamak.
- Donanım destekli güven kökü (hardware root of trust) + imza doğrulama + anti-rollback sayaçlarıyla tam bir secure boot zinciri kurmak.
- Üretime giden cihazlarda debug arayüzlerini kalıcı olarak kilitlemek (fuse yakarak).
- Her cihaza benzersiz kriptografik anahtar sağlamak, paylaşılan/sabit anahtarlardan kaçınmak.

## Sonuç

Gömülü sistemler ve RTOS mühendisliği, güvenliği "eklenen bir katman" olarak değil, kaynak kısıtları ve zaman garantileri etrafında şekillenen bir tasarım disiplini olarak ele almayı gerektirir. Masaüstü/sunucu dünyasının bolca sahip olduğu savunma katmanları (MMU izolasyonu, ASLR, bol heap) burada ya yoktur ya da bilinçli olarak feragat edilmiştir; bunun yerine determinizm, öngörülebilirlik ve donanım destekli güven kökleri devreye girer. Bir savunmacı veya firmware mühendisi için kritik içgörü şudur: bu ortamda en ufak bir bellek bozulması veya zamanlama ihlali, başka bir katman tarafından yakalanmayabilir — bu yüzden doğru olan, "hatasız kod" değil, "hata olduğunda bile öngörülebilir ve sınırlı biçimde başarısız olan kod" yazmaktır.
