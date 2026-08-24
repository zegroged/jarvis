# İşletim Sistemi Çekirdek İç Yapısı: Kernel Modülleri, Syscall Uygulaması, Kernel Exploitation

## Giriş: Neden Kernel'in Kendisini Anlamak Gerekir

System call arayüzü, sanal bellek yönetimi ve process/thread scheduling gibi konular genellikle "kullanıcı programının kernel'den ne istediği" perspektifinden anlatılır. Bu bakış açısı eksiktir, çünkü bir güvenlik açığının veya bir performans sorununun gerçek kök nedeni çoğu zaman kernel'in *kendi* iç veri yapılarında, kendi bellek tahsis mekanizmalarında ve kendi ayrıcalık modelinde yatar. Kullanıcı seviyesinde bir buffer overflow en kötü ihtimalle o process'i çökertir; kernel seviyesinde aynı sınıf hata tüm makineyi (privilege ring 0) ele geçirilebilir hale getirir. Bu makalenin amacı, kernel'i "kutunun içi" olarak incelemek: modüller nasıl yüklenir ve çalışır, syscall bir kullanıcı isteğini nasıl gerçekten işler, kernel kendi belleğini nasıl yönetir (slab/slub allocator) ve bu mekanizmalardaki zayıflıklar nasıl istismar edilir/edilmez, hangi savunma katmanları bunu zorlaştırır.

Anlatı Linux merkezlidir çünkü açık kaynaklı olması, iç yapının somut kod üzerinden tartışılmasına izin verir; ancak kavramlar (privilege ring, syscall table, slab allocator, ROP/JOP) Windows ve diğer modern çekirdekler için de büyük ölçüde geçerlidir.

## Ayrıcalık Modeli: Ring 0 ve Kernel/Kullanıcı Sınırı

### Kök neden: donanım neden bu ayrımı zorunlu kılar

x86-64 mimarisi dört ayrıcalık seviyesi (ring 0-3) tanımlar; modern işletim sistemleri sadece ikisini kullanır: ring 0 (kernel) ve ring 3 (kullanıcı). Bu ayrım yazılımsal bir "kibarlık" değil, CPU'nun donanımsal olarak zorladığı bir sınırdır. Belirli komutlar (örneğin sayfa tablosu register'ı `CR3`'ü değiştirmek, kesme denetleyicisini programlamak, I/O portlarına doğrudan erişmek) sadece ring 0'da çalışırken denenebilir; ring 3'te denenirse CPU bir genel koruma hatası (`#GP`) üretir.

Bu ayrımın **kök nedeni** basit bir güven modelidir: kullanıcı kodu güvenilmezdir, çünkü herhangi bir kullanıcı rastgele kod çalıştırabilir. Eğer kullanıcı kodu doğrudan donanımı veya başka process'lerin belleğini manipüle edebilseydi, izolasyon (bir process'in diğerini bozamaması, bir kullanıcının diğerinin dosyalarını okuyamaması) diye bir kavram olmazdı. Kernel, bu güvenin merkezi olarak tasarlanmıştır: tüm donanıma, tüm fiziksel belleğe ve tüm process'lerin durumuna erişebilen tek kod.

Bunun doğal sonucu: **kernel'de bulunan herhangi bir bellek bozulması hatası, ring 0 ayrıcalığıyla çalışır.** Kullanıcı seviyesinde ASLR, stack canary, DEP gibi savunmalar bir process'i korur; ama kernel'e sızan bir hata bu izolasyon modelinin *kendisini* kırar. Bu yüzden kernel exploitation, kullanıcı seviyesi exploitation'dan niteliksel olarak daha tehlikelidir — hedef artık bir process değil, tüm sistemdir.

### Syscall: Ring geçişinin kontrollü kapısı

Kullanıcı kodu kernel'den hizmet istediğinde (dosya açma, bellek tahsisi, ağ soketi) rastgele bir kernel fonksiyonuna atlayamaz — bu, kernel'in iç yapısını bilerek keyfi kod çalıştırmaya izin verirdi. Bunun yerine, CPU'nun sağladığı özel bir komutla (x86-64'te `syscall`, eski sistemlerde `int 0x80`) kontrollü bir geçiş yapılır. Bu komut:

1. Kullanıcı kodunun ring 3'ten ring 0'a geçmesini sağlar,
2. Ama atlanacak adresi **kernel önceden belirler** (bir model-specific register, `MSR_LSTAR`, syscall giriş noktasının adresini tutar),
3. Kullanıcı sadece bir syscall numarası (register'da, x86-64'te `rax`) ve argümanlar verebilir.

Bu, "kapıcı" modelidir: kullanıcı hangi kapıdan gireceğini seçemez, sadece hangi hizmeti istediğini bir numarayla belirtir; kernel bu numarayı kendi **syscall tablosunda** (`sys_call_table` Linux'ta) arar ve ilgili fonksiyonu çağırır.

```
kullanıcı: rax = __NR_write; syscall komutu çalıştır
   ↓ (CPU ring 0'a geçer, MSR_LSTAR adresine atlar)
kernel: entry_SYSCALL_64 (assembly giriş noktası)
   → kullanıcı register'larını kernel stack'ine kaydet
   → syscall numarasını doğrula (sınır kontrolü!)
   → sys_call_table[rax] çağır → örn. sys_write()
   → dönüş değerini rax'e koy, kullanıcı register'larını geri yükle
   → sysret ile ring 3'e dön
```

**Neden bu kadar dikkatli tasarlanmış:** syscall tablosu sabit boyutlu bir dizi, numara sınır dışıysa kernel geçersiz bir fonksiyon pointer'ını çağırmamalıdır (bu kontrol atlanırsa kontrolsüz dallanma / arbitrary code execution olur). Ayrıca kullanıcıdan gelen her pointer argümanı (`write(fd, buf, len)` içindeki `buf` gibi) kernel tarafından asla doğrudan güvenilmez — kernel `copy_from_user`/`copy_to_user` gibi özel fonksiyonlar kullanır. Bu fonksiyonlar hem adresin gerçekten kullanıcı adres alanında olduğunu doğrular hem de sayfa hatası (page fault) oluşursa güvenli şekilde başarısız olur, kernel'i çökertmez.

**Yaygın hata / güvenlik dersi:** Eğer bir kernel modülü (özellikle üçüncü parti bir sürücü) kullanıcıdan gelen bir pointer'ı `copy_from_user` yerine doğrudan dereference ederse, kullanıcı kernel adres alanına işaret eden bir pointer vererek kernel belleğini okuyabilir/yazabilir hale gelir. Bu sınıf hata (arbitrary read/write primitive) kernel exploit zincirlerinin en değerli yapı taşıdır.

## Kernel Modülleri: Genişletilebilirlik ile Güven Arasındaki Denge

### Modüllerin var oluş nedeni

Kernel, tüm donanım sürücülerini ve dosya sistemlerini statik olarak derleyip yüklemek zorunda kalsaydı hem devasa hem esneksiz olurdu — her yeni donanım için yeniden derleme gerekirdi. **Loadable Kernel Module (LKM)** mekanizması, çalışan bir kernel'e dinamik olarak kod ekleme/çıkarma imkânı verir (Linux'ta `insmod`/`rmmod`, Windows'ta driver yükleme benzer bir modeldir).

Bir modül temelde bir ELF nesne dosyasıdır; kernel onu yüklerken:

1. **Sembol çözümlemesi (symbol resolution)** yapar: modülün çağırdığı `printk`, `kmalloc` gibi kernel fonksiyonlarının gerçek adreslerini bağlar (bu, kullanıcı seviyesinde dinamik linker'ın `.so` dosyalarıyla yaptığına benzer, ama kernel adres alanında).
2. Modülün `init_module`/`module_init` fonksiyonunu **ring 0'da, tam kernel ayrıcalığıyla** çalıştırır.
3. Modülün tahsis ettiği bellek, kaydettiği syscall hook'ları veya değiştirdiği veri yapıları artık kernel'in bir parçasıdır.

**Kök neden — güven modelinin kırılganlığı:** Modül yükleme yetkisi genellikle root/administrator gerektirir, çünkü **bir kernel modülü yüklemek kernel'e keyfi kod eklemekle eşdeğerdir.** Burada kritik bir kavramsal nokta var: eğer bir saldırgan zaten root ise ve bir kernel modülü yükleyebiliyorsa, bu genellikle "privilege escalation" değil zaten en yüksek yetkidedir — asıl tehlike **imzasız/kötü niyetli modüllerin** rootkit olarak kullanılmasıdır (syscall tablosunu değiştirip dosya/process gizleme, `/proc` çıktısını manipüle etme).

Bu yüzden modern kernel'ler **modül imzalama (module signing)** zorunlu kılar: kernel sadece güvenilir bir anahtarla imzalanmış modülleri yükler. Bu, "root güvenlik sınırı değildir" varsayımını kısmen değiştirip "sadece imzalı kod kernel'e girebilir" ilkesine yaklaşır — Secure Boot ile birleştiğinde zincirleme bir güven modeli oluşturur.

### Modül-tabanlı saldırı yüzeyi ve savunma

- **Lockdown modu (Linux kernel lockdown):** İmzasız modül yüklemeyi, `/dev/mem` üzerinden fiziksel bellek erişimini ve kernel'i doğrudan manipüle edebilecek diğer arayüzleri (kexec, hibernation ile kod enjeksiyonu gibi) kapatır. Amaç: root olsanız bile kernel'in bütünlüğünü (integrity) korumak — özellikle Secure Boot etkinken "root ele geçirme" ile "kernel ele geçirme" arasına bir duvar koymak.
- **`CONFIG_MODULE_SIG_FORCE`:** İmzasız modülleri tamamen reddeder.
- **En iyi pratik (savunma mühendisi gözüyle):** Üretim sistemlerinde gereksiz modül yüklemeyi kapatmak, çekirdek imzalama zincirini doğrulamak, ve üçüncü parti sürücüleri (özellikle donanım üreticilerinden gelen closed-source driver'ları) minimum ayrıcalıkla, mümkünse sınırlı bir sanal ortamda test etmek.

**Yaygın hata:** Bir modülün "sadece belirli bir donanım için sürücü" olması onu güvenli yapmaz — modül kodu kernel adres alanında çalıştığı an, o kod tabanındaki *herhangi bir* bellek hatası (özellikle kullanıcıdan alınan input'u işlerken) tüm kernel'i etkiler. Sürücüler, tarihsel olarak kernel exploit'lerinin en verimli kaynağı olmuştur çünkü genellikle daha az denetlenir, daha hızlı yazılır ve kullanıcı kontrolündeki veriyi (USB cihaz tanımlayıcıları, ağ paketleri, dosya sistemi metadata'sı) doğrudan işler.

## Kernel Bellek Yönetimi: Slab/Slub Allocator

### Kök neden: Genel amaçlı allocator neden yetersiz kalır

Kullanıcı seviyesinde `malloc` genel amaçlıdır ve keyfi boyutta blokları yönetir. Kernel'de ise bellek tahsisinin büyük kısmı **sabit boyutlu, sık tekrar eden nesneler** içindir: her yeni process için bir `task_struct`, her açık dosya için bir `file` yapısı, her ağ paketi için bir `sk_buff`. Bu nesneleri her seferinde genel amaçlı bir allocator'dan (sayfa tahsisçisinden, buddy allocator) almak hem yavaştır (fragmantasyon, hizalama maliyeti) hem de kernel gibi performans-kritik bir ortamda kabul edilemez.

**Slab allocator** (ve onun modern varyantı **SLUB**, Linux'ta varsayılan), bu soruna doğrudan cevaptır: sık kullanılan nesne türleri için önceden ayrılmış, aynı boyutta "yuva" (slot) havuzları tutar. Bir `task_struct` serbest bırakıldığında bellek işletim sistemine geri verilmez, aynı türde bir sonraki tahsis için havuzda bekletilir. Bu:

- Tahsis/serbest bırakma işlemini O(1)'e yakın yapar (havuzdan bir yuva almak/koymak),
- Nesnenin önceki verisinin kalıntılarını (cache içeriği) bir dereceye kadar koruyarak cache locality sağlar,
- Fragmantasyonu azaltır çünkü aynı boyuttaki nesneler hep aynı bölgede yaşar.

```
kmem_cache (örn. "task_struct" için)
  ├─ slab #1 (bir veya birkaç fiziksel sayfa)
  │    ├─ obje yuvası [dolu: process A]
  │    ├─ obje yuvası [boş, havuzda]
  │    └─ obje yuvası [dolu: process B]
  └─ slab #2 ...
```

### Use-After-Free'nin kök nedeni burada yatıyor

Slab allocator'ın **serbest bırakılan belleği hemen işletim sistemine iade etmeyip aynı türde bir sonraki tahsis için saklaması**, kernel'deki en yaygın istismar sınıflarından biri olan **Use-After-Free (UAF)**'nin neden bu kadar güçlü bir primitive olduğunu açıklar:

1. Bir kod yolu bir nesneyi (örn. bir soket yapısı) serbest bırakır ama ona giden bir pointer'ı bir yerde tutmaya devam eder (dangling pointer) — genellikle bir race condition veya referans sayımı hatası yüzünden.
2. Slab allocator bu belleği hemen başka bir amaçla yeniden kullanılabilir hale getirir — bellek fiziksel olarak hâlâ aynı yerdedir, sadece "boş" işaretlenmiştir.
3. Saldırgan, **aynı slab cache'inden**, kontrol edebileceği içerikle yeni bir nesne tahsis ettirir (heap spraying/grooming: belirli boyutta çok sayıda nesne tahsis ederek slab'ın boş yuvasının saldırganın kontrolündeki veriyle dolmasını sağlamak).
4. Eski dangling pointer hâlâ kullanılırsa, artık saldırganın kontrol ettiği veriyi "orijinal nesne" sanarak işler — bu genellikle bir fonksiyon pointer'ı çağırma (`vtable`/callback) veya bir boyut/index alanının üzerine yazılmasıyla **kontrol akışını ele geçirme** veya **arbitrary read/write** primitive'ine dönüşür.

Bunun **kök nedeni ne allocator'ın "kötü" tasarlanmış olması ne de UAF'nin kernel'e özgü olmasıdır** — asıl kök neden, C dilinde manuel bellek yönetiminin (bir nesnenin ne zaman "artık kullanılmayacağının" derleyici tarafından değil, programcı tarafından doğru izlenmesi gerektiği) kernel gibi karmaşık, çok sayıda eşzamanlı yürütme yoluna (interrupt handler, farklı CPU çekirdekleri, farklı process'ler) sahip bir ortamda son derece hataya açık olmasıdır. Referans sayımı hataları, kilit sırası (lock ordering) hataları ve serbest bırakma sırası varsayımları, kernel'in eşzamanlılık modelinin doğal karmaşıklığından kaynaklanır.

### Savunma: allocator seviyesinde sertleştirme

- **SLAB_FREELIST_HARDENED / özgür liste bütünlüğü:** Serbest yuvaların birbirine bağlandığı "freelist" pointer'larını kodlayarak (XOR ile bir gizli değerle karıştırarak), bir heap overflow'un bu pointer'ları doğrudan öngörülebilir şekilde manipüle etmesini zorlaştırır.
* **Cache ayrıştırma / dedicated cache'ler:** Güvenlik açısından hassas nesne türlerini (örneğin bazı kritik yapıları) genel amaçlı `kmalloc` havuzlarından ayırıp kendi özel cache'lerine koymak, saldırganın "aynı boyuttaki herhangi bir nesneyle" grooming yapmasını zorlaştırır — çünkü artık hedef nesneyle aynı cache'i paylaşan aday nesne sayısı azalır.
- **KASAN (Kernel Address Sanitizer) ve benzeri araçlar:** Geliştirme/test aşamasında UAF ve out-of-bounds erişimleri çalışma zamanında yakalar; üretimde performans maliyeti nedeniyle genelde kapalıdır ama fuzzing (örn. syzkaller ile kernel fuzzing) sırasında kritik önemdedir.
- **En iyi pratik:** Kernel/sürücü geliştirirken referans sayımını (`refcount_t`) atomically ve dikkatle yönetmek, kilitleri her zaman aynı sırada almak, ve "serbest bırak, sonra pointer'ı NULL'a çek" disiplinini (use-after-free'yi NULL pointer dereference'a indirger — kernel'de bu genellikle exploit edilebilirliği ciddi şekilde azaltır) uygulamak.

## Kernel Exploitation: Mantık ve Savunma Perspektifi

Bu bölüm, saldırı adımlarını "nasıl yaparım" diye değil, **bir savunmacının bu zincirin her halkasında neyi kırabileceğini anlaması için** ele alır.

### Tipik zincirin mantığı

Kernel exploit'leri genellikle şu soyut adımları izler (spesifik CVE veya komut ayrıntısı vermeden, sadece mantık):

1. **Bir bellek bozulması hatası bulma:** UAF, heap/stack overflow, race condition (TOCTOU — time-of-check-to-time-of-use), tip karışıklığı (type confusion) veya bir referans sayımı hatası. Kaynak genellikle syscall handler'ları, sürücüler veya dosya sistemi kodudur çünkü bunlar doğrudan kullanıcı kontrolündeki veriyi işler.
2. **Bir primitive'e dönüştürme:** Ham hatayı (örn. "bu alan bir bayt taşabiliyor") kullanışlı bir yeteneğe çevirmek — genellikle "arbitrary read", "arbitrary write" veya "kontrol akışını ele geçirme" (bir fonksiyon pointer'ını veya dönüş adresini kontrol etme).
3. **Bilgi sızdırma (info leak):** Modern savunmalar (KASLR — Kernel Address Space Layout Randomization) kernel'in bellekte nereye yüklendiğini rastgele hale getirdiği için, saldırganın önce "kernel şu anda hangi adreste" bilgisini sızdırması gerekir. Bu genellikle bir arbitrary read primitive'i veya yan kanal (side-channel) ile yapılır.
4. **Kontrol akışını ele geçirme:** Klasik "shellcode'u kernel stack'ine yaz ve oraya atla" yaklaşımı, **SMEP (Supervisor Mode Execution Prevention)** ve **SMAP (Supervisor Mode Access Prevention)** gibi donanım savunmaları yüzünden artık pratik değildir — bu mekanizmalar CPU'nun ring 0'dayken kullanıcı adres alanındaki kodu çalıştırmasını (SMEP) veya kullanıcı belleğine doğrudan erişmesini (SMAP) engeller. Bu yüzden saldırganlar **ROP (Return-Oriented Programming)** veya **JOP (Jump-Oriented Programming)** kullanır: kernel'in kendi içindeki mevcut kod parçacıklarını (gadget'lar) zincirleyerek istenen mantığı (genellikle "mevcut process'in ayrıcalıklarını root'a yükselt" fonksiyonunu çağırmak) yeni kod enjekte etmeden inşa ederler.
5. **Ayrıcalık yükseltme mantığı:** Amaç genellikle yeni kod çalıştırmak değil, mevcut process'in `task_struct` içindeki kimlik bilgilerini (credentials — UID/GID, capability bitleri) doğrudan kernel belleğinde root'a eşdeğer bir değerle değiştirmektir. Bu, "kernel'de zaten var olan meşru bir fonksiyonu (credential'ları ayarlayan) çağırmak" olduğu için tespiti zorlaştırır.
6. **Temizlik:** Sistemi kararlı bırakmak için bozulan veri yapılarının tutarlı bir duruma geri getirilmesi (aksi halde kernel panic/çökme olur, bu da saldırıyı "gürültülü" ve tespit edilebilir yapar).

### Savunma katmanları — her adımı neden zorlaştırırlar

| Savunma | Hangi adımı hedefler | Mantığı |
|---|---|---|
| **KASLR** | Bilgi sızdırma | Kernel'in yükleme adresini rastgeleleştirerek, saldırganın önceden bilinen sabit adreslere güvenerek gadget/fonksiyon bulmasını engeller — ama sadece bir bilgi sızıntısı yoksa etkilidir. |
| **SMEP** | Kontrol akışı ele geçirme | CPU'nun ring 0'dayken kullanıcı sayfası olarak işaretli belleği *kod olarak çalıştırmasını* engeller; klasik "kullanıcı belleğine shellcode koy, kernel'i oraya atlat" tekniğini geçersiz kılar. |
| **SMAP** | Veri manipülasyonu | Ring 0'dayken kullanıcı belleğine *veri erişimini de* (okuma/yazma, sadece çalıştırma değil) kısıtlar; `copy_from_user` gibi meşru yollar dışında kullanıcı verisine dokunmayı zorlaştırır. |
| **CFI (Control Flow Integrity)** | ROP/JOP | Dolaylı çağrıların (indirect call/jump) sadece derleme zamanında belirlenmiş meşru hedeflere gitmesine izin vererek, gadget zincirlemeyi kısıtlar. |
| **`kptr_restrict`, dmesg kısıtlaması** | Bilgi sızdırma | Kernel pointer değerlerinin `/proc`, log çıktısı gibi kanallardan sızmasını engeller — saldırganın adres bulma kolaylığını kısıtlar. |
| **Grsecurity/PaX benzeri sertleştirmeler, `CONFIG_HARDENED_USERCOPY`** | Bellek bozulması | `copy_from_user`/`copy_to_user` çağrılarında hedef nesnenin gerçek sınırlarını çalışma zamanında doğrulayarak, sürücü hatalarının doğrudan overflow'a dönüşmesini engeller. |

**Kök neden dersinin özeti:** Hiçbir tek savunma tam koruma sağlamaz; bunlar **derinlemesine savunma (defense in depth)** katmanlarıdır. KASLR olmadan da SMEP olmadan da exploit yazılabilir, ama ikisi birlikte + CFI + bilgi sızıntısı olmaması, saldırgan için gereken adım sayısını ve zorluğu katlanarak artırır. Modern kernel exploit'leri artık çoğunlukla "tek bir bellek hatası" değil, **birden fazla zayıf noktanın zincirlenmesiyle** (bir bilgi sızıntısı + bir yazma primitive'i + bir CFI bypass'ı) oluşur.

### Tespit (detection) perspektifinden bakış

Savunmacı/mühendis olarak asıl değerli olan, exploit yazmayı öğrenmek değil, şu sinyalleri izlemektir:

- **Beklenmeyen kernel panik/oops olayları:** Başarısız exploit denemeleri sıklıkla kernel'i tutarsız duruma sokup panik'e yol açar; log'larda tekrarlayan, açıklanamayan kernel oops'ları bir istismar denemesinin belirtisi olabilir.
- **Anormal capability/UID değişiklikleri:** Bir process'in beklenmedik şekilde ayrıcalık kazandığı (örneğin normalde sınırlı bir servis process'inin aniden root capability'lerine sahip olması), EDR/runtime security araçlarının izlediği klasik bir göstergedir.
- **Syscall tablosu bütünlüğü izleme:** Rootkit'ler genellikle syscall tablosunu değiştirir; bütünlük izleme araçları (kernel modülünün kendisi güvenilir bir taban üzerinden) bu değişikliği yakalayabilir.
- **Fuzzing ve statik analiz yatırımı:** syzkaller gibi kernel fuzzer'ları, KASAN ile birleştirildiğinde UAF/overflow sınıfı hataları üretime girmeden yakalar — bu, "istismar sonrası tespit" yerine "istismar edilebilir hatayı baştan bulma" stratejisidir ve çok daha maliyet-etkindir.

## Sonuç: Savunma Mühendisliği Açısından Çıkarımlar

Kernel iç yapısını anlamanın pratik değeri şudur: syscall arayüzü ve slab allocator gibi mekanizmalar, hem performans hem esneklik için tasarlanmış olsa da, aynı tasarım kararları (kullanıcı girdisinin doğrudan işlenmesi, belleğin hızlı yeniden kullanımı, dinamik kod yükleme) istismar yüzeyinin de kaynağıdır. Bir savunma mühendisi için çıkarımlar nettir:

1. **Saldırı yüzeyini küçültmek en ucuz savunmadır** — gereksiz kernel modüllerini/sürücüleri kapatmak, lockdown modunu etkinleştirmek, kullanılmayan syscall'ları (seccomp ile) kısıtlamak.
2. **Kullanıcı girdisini işleyen her kod yolu (syscall handler'lar, sürücüler) en yüksek inceleme önceliğine sahip olmalıdır**, çünkü bunlar kernel'e giden tek meşru kapıdır ve dolayısıyla saldırganın da tek giriş noktasıdır.
3. **Derinlemesine savunma katmanlarının (KASLR, SMEP/SMAP, CFI, hardened usercopy) hepsini etkinleştirmek**, tek bir hatanın doğrudan tam sistem ele geçirilmesine dönüşmesini engeller — amaç mükemmel önleme değil, saldırganın maliyetini ve iz bırakma olasılığını artırmaktır.
4. **Fuzzing ve statik analiz, üretim sonrası tespitten çok daha değerlidir** — kernel'de bir istismar tespit edildiğinde genellikle zarar çoktan gerçekleşmiştir; asıl kazanç hatayı hiç var olmadan bulmaktır.

Kernel, işletim sisteminin güven merkezi olduğu için, buradaki her tasarım kararı doğrudan bir güvenlik varsayımıdır — bu varsayımları bilmek, hem daha iyi sürücü/modül yazmak hem de bir sistemi gerçekten savunmak için zorunludur.
