# Process, Thread ve Scheduling: İzolasyon, Context Switch, Preemption ve Öncelik

## Giriş ve Kavramsal Çerçeve

Modern işletim sistemlerinin en temel görevi, sınırlı sayıdaki fiziksel CPU çekirdeğini binlerce çalışma birimi arasında adil, güvenli ve verimli biçimde paylaştırmaktır. Bu paylaşımın merkezinde üç kavram durur: **process** (süreç), **thread** (iş parçacığı) ve **scheduling** (zamanlama). Bu üç kavramı doğru anlamak, yalnızca teorik bir egzersiz değildir; performans darboğazlarını teşhis etmek, kilitlenmeleri (deadlock) çözmek, güvenlik sınırlarını doğru çizmek ve ölçeklenebilir sistemler tasarlamak için zorunlu bir temeldir.

Bu makale dört odak ekseni etrafında ilerler: **izolasyon** (birimlerin birbirinden ne kadar ayrıştığı), **context switch** (CPU'nun bir birimden diğerine geçerken ödediği bedel), **preemption** (bir birimin isteği dışında CPU'dan alınması) ve **öncelik** (kimin önce çalışacağı). Bu eksenlerin her biri, "neden böyle tasarlandı" sorusuna verilen mühendislik cevaplarıyla anlam kazanır.

## Process Nedir ve Neden İzolasyon Gerekir

### Tanım

Bir **process**, çalışan bir programın işletim sistemi tarafından yönetilen örneğidir. Bir program diskte duran pasif bir bayt dizisiyken, process o programın belleğe yüklenmiş, bir yürütme bağlamına (register değerleri, program counter, yığın) sahip, işletim sisteminin kaynak tahsis ettiği aktif halidir. Her process'in kendine ait bir **sanal adres uzayı** (virtual address space) vardır.

İşletim sistemi her process için bir **PCB** (Process Control Block) tutar. Bu yapı; process kimliği (PID), süreç durumu (running, ready, blocked), register kopyaları, sanal bellek eşleme bilgileri (page table işaretçisi), açık dosya tanıtıcıları (file descriptor tablosu), öncelik değeri ve muhasebe verilerini barındırır. PCB, işletim sisteminin bir process hakkında bildiği her şeyin çekirdek belleğindeki toplandığı yerdir.

### Kök Neden: İzolasyon Neden Vardır

Process izolasyonunun asıl amacı, bir process'in hatasının veya kötü niyetinin başka bir process'i çökertmesini ya da onun verisini okumasını engellemektir. Bu izolasyon iki katmanda sağlanır ve her ikisi de donanım desteğine dayanır.

Birincisi **bellek izolasyonudur**. Modern CPU'lardaki **MMU** (Memory Management Unit) sayesinde her process, kendi sanal adres uzayında yaşar. Process'in gördüğü `0x400000` adresi, başka bir process'in gördüğü aynı sanal adresle aynı fiziksel belleğe karşılık gelmez. İşletim sistemi, her process için ayrı bir **page table** (sayfa tablosu) kurar; MMU bu tabloyu kullanarak sanal adresleri fiziksel adreslere çevirir. Bir process, page table'ında eşlemesi olmayan bir adrese erişmeye çalışırsa donanım bir **page fault** üretir ve çekirdek devreye girer. Böylece bir process, diğerinin belleğine "sızamaz". Bu, buffer overflow gibi hataların etkisini o process'in sınırları içinde tutmanın da temelidir.

İkincisi **ayrıcalık izolasyonudur**. CPU'lar en az iki ayrıcalık seviyesiyle çalışır: **kullanıcı modu** (user mode) ve **çekirdek modu** (kernel mode). x86 mimarisinde bunlar "ring" olarak adlandırılır; kullanıcı kodu Ring 3'te, çekirdek Ring 0'da çalışır. Disk yazma, page table değiştirme veya donanım kesmesi yapılandırma gibi ayrıcalıklı işlemler yalnızca çekirdek modunda yürütülebilir. Bir process böyle bir işlemi doğrudan yapamaz; bunun yerine kontrollü bir kapıdan, yani **system call** (sistem çağrısı) üzerinden çekirdekten rica eder. Bu kapı, izolasyonun delinmeden korunmasını sağlayan denetim noktasıdır.

### Kök Neden: İzolasyonun Bedeli

İzolasyon bedava değildir. Ayrı adres uzayları, iki process'in veri paylaşmasını zorlaştırır; bunun için **IPC** (Inter-Process Communication) mekanizmaları gerekir: pipe, socket, paylaşımlı bellek (shared memory), message queue gibi. Ayrıca process oluşturmak pahalıdır: yeni bir adres uzayı kurulmalı, page table'lar hazırlanmalı, kaynak yapıları tahsis edilmelidir. Bu maliyet, thread kavramının neden doğduğunu açıklar.

## Thread Nedir ve Process ile Farkı

### Tanım

Bir **thread**, bir process içindeki bağımsız bir yürütme akışıdır. Aynı process içindeki thread'ler ortak bir adres uzayını, ortak file descriptor'ları, ortak global değişkenleri ve heap'i paylaşır. Buna karşılık her thread'in kendine ait bir **yığını** (stack), kendi register kümesi ve kendi program counter'ı vardır. Yani thread'ler "neyi paylaştıkları" ve "neyi ayrı tuttukları" ile tanımlanır: kod ve veri paylaşılır, yürütme durumu ayrıdır.

### Kök Neden: Thread'ler Neden İcat Edildi

Thread'lerin var olma nedeni iki ihtiyaçtan doğar. Birincisi **paralellik**: çok çekirdekli bir makinede tek bir process'in işi birden fazla çekirdekte aynı anda yürütülebilmelidir. İkincisi **paylaşımın ucuzluğu**: aynı adres uzayını paylaştıkları için thread'ler arası veri aktarımı, IPC'ye gerek kalmadan doğrudan bellek üzerinden yapılır. Bu, hem daha hızlıdır hem de programlaması daha kolaydır.

Ancak bu ucuzluğun karşılığı **zayıf izolasyondur**. Bir thread'in bozduğu bellek, aynı process içindeki tüm thread'leri etkiler; tek bir thread'in çökmesi çoğu zaman tüm process'i düşürür. Paylaşılan veriye eşzamanlı erişim ise **race condition** ve veri bozulması riskini getirir. Bu yüzden thread programlamanın kalbinde senkronizasyon (mutex, semaphore, condition variable) yer alır.

### Kernel Thread ve User Thread

Thread'lerin işletim sistemi tarafından nasıl görüldüğü de önemlidir. **Kernel-level thread**'ler çekirdeğin bildiği ve doğrudan zamanladığı thread'lerdir; gerçek paralellik ve bağımsız bloklama bunlarla mümkün olur. **User-level thread**'ler ise tamamen kullanıcı alanındaki bir kütüphane tarafından yönetilir ve çekirdek onları görmez. User thread'ler çok hafiftir ama bir tanesi bloklayan bir sistem çağrısı yaptığında, çekirdek tüm process'i bloke edebilir. Modern runtime'lar (örneğin Go'nun goroutine'leri veya çeşitli dillerdeki "green thread" / "virtual thread" yaklaşımları) çok sayıda hafif kullanıcı thread'ini az sayıda kernel thread üzerine eşleyen M:N modelleri kullanarak bu iki dünyanın avantajlarını birleştirmeye çalışır.

## Context Switch: CPU'nun Bağlam Değiştirmesi

### Tanım

**Context switch** (bağlam değiştirme), CPU'nun bir yürütme biriminden (thread veya process) diğerine geçerken mevcut birimin durumunu kaydedip yeni birimin durumunu yüklemesi işlemidir. Bu, tek bir CPU'nun birçok işi "aynı anda yürütüyormuş gibi" görünmesini sağlayan illüzyonun temel mekanizmasıdır.

### Nasıl Çalışır ve Neden Maliyetlidir

Bir context switch şu adımları içerir. Önce mevcut thread'in CPU register'ları (genel amaçlı register'lar, program counter, stack pointer, durum bayrakları) PCB veya thread kontrol yapısına kaydedilir. Ardından scheduler, çalışacak sonraki thread'i seçer. Son olarak seçilen thread'in kaydedilmiş durumu register'lara geri yüklenir ve yürütme oradan devam eder.

Buradaki maliyeti anlamak kritik. **Doğrudan maliyet**, register'ların kaydedilip yüklenmesi ve scheduler'ın karar vermesidir; bu görece küçüktür. Asıl pahalı olan **dolaylı maliyettir**. İki noktada ortaya çıkar:

Birincisi **cache etkileridir**. Her thread çalışırken CPU'nun L1/L2/L3 cache'lerini kendi sık kullandığı verilerle doldurur (cache "sıcak" hale gelir). Başka bir thread'e geçildiğinde bu cache içerikleri yeni thread için işe yaramaz; yeni thread kendi verilerini yavaş ana bellekten çekmek zorunda kalır. Bu "cache soğuması", context switch'in görünmeyen ama çoğu zaman en büyük maliyetidir.

İkincisi, **farklı process'ler arası** geçişte devreye giren **TLB** (Translation Lookaside Buffer) etkisidir. TLB, sanal-fiziksel adres çevirilerini önbelleğe alan küçük ama kritik bir donanımdır. Adres uzayı değiştiğinde, yani farklı bir process'e geçildiğinde, eski çevrimler artık geçersizdir ve TLB'nin ilgili girişleri boşaltılır (flush) ya da geçersiz kılınır. Yeni process çalışmaya başladığında adres çevrimleri yeniden yavaşça öğrenilir. İşte bu yüzden **iki thread arası** context switch, **iki process arası** context switch'ten genellikle daha ucuzdur: aynı process'in thread'leri aynı adres uzayını paylaştığından TLB flush gerekmez.

### Somut Örnek

Bir web sunucusu düşünün: 10.000 eşzamanlı bağlantıyı her biri ayrı thread ile karşılamaya kalkarsanız, CPU zamanının büyük kısmı işi yapmaya değil thread'ler arasında gidip gelmeye harcanabilir. Bu olguya bazen **thrashing**'e benzer bir "scheduling overhead" denir. Bu, event-driven (olay güdümlü) mimarilerin (epoll, kqueue tabanlı reactor desenleri) ve asenkron I/O'nun neden popüler olduğunu açıklar: bunlar context switch sayısını azaltarak aynı çekirdekle çok daha fazla bağlantı taşırlar.

### Voluntary ve Involuntary Switch

Context switch iki sebeple olur. **Gönüllü (voluntary)** switch, thread bir kaynağı beklemek için (örneğin bir I/O tamamlanana kadar veya bir mutex serbest kalana kadar) kendini bloke ettiğinde olur; thread CPU'yu kendi isteğiyle bırakır. **İstem dışı (involuntary)** switch ise scheduler'ın thread'i zorla CPU'dan almasıdır ki bu bizi preemption kavramına götürür. Linux'ta `/proc/<pid>/status` benzeri arayüzlerde bu iki switch türünün sayaçları ayrı ayrı izlenebilir; yüksek involuntary switch sayısı CPU üzerinde yoğun rekabet olduğunun, yüksek voluntary switch sayısı ise sık bloklama (çoğunlukla I/O) olduğunun işaretidir.

## Preemption: CPU'yu Zorla Geri Almak

### Tanım

**Preemption** (kesme/el koyma), işletim sisteminin çalışan bir thread'i, o thread razı olmasa bile CPU'dan alıp başka bir thread'e verme yeteneğidir. Preemptive olmayan (cooperative / non-preemptive) bir sistemde ise thread, CPU'yu ancak kendi isteğiyle bıraktığında el değiştirir.

### Kök Neden: Preemption Neden Zorunlu

Preemption olmadan tek bir hatalı veya kötü niyetli thread, sonsuz döngüye girip CPU'yu asla bırakmayarak tüm sistemi kilitleyebilir. Kooperatif zamanlama, her thread'in "iyi vatandaş" olup düzenli aralıklarla CPU'yu gönüllü bırakmasına güvenir; bu güven gerçek dünyada tehlikelidir. Preemption, işletim sistemine son sözü söyleme gücü verir ve **adaleti** (fairness) ile **yanıt verebilirliği** (responsiveness) garanti altına alır.

### Nasıl Çalışır: Timer Interrupt

Preemption'ın kalbinde donanım **timer interrupt** (zamanlayıcı kesmesi) yatar. İşletim sistemi, donanım zamanlayıcısını periyodik olarak (klasik olarak birkaç milisaniyede bir; modern çekirdeklerde "tickless" tasarımlarla daha esnek biçimde) kesme üretecek şekilde programlar. Her kesme geldiğinde CPU otomatik olarak çekirdek moduna geçer ve kesme işleyicisini (interrupt handler) çalıştırır. Bu anda çekirdek şunu sorabilir: "Bu thread ayrılan zaman dilimini (time slice / quantum) tüketti mi? Daha yüksek öncelikli bir thread çalışmaya hazır mı?" Cevap evetse, çekirdek çalışan thread'i preempt eder ve bir context switch tetikler.

Buradaki incelik şudur: preemption'ın gerçekleşebilmesi için CPU'nun kontrolü periyodik olarak çekirdeğe dönmelidir. Timer interrupt, bu dönüşü garantileyen mekanizmadır. Timer olmasaydı, CPU tamamen kullanıcı kodunun insafına kalırdı.

### Kernel Preemption İnceliği

Kullanıcı kodunun preempt edilmesi görece basittir. Asıl zor soru, çekirdeğin kendi kodu çalışırken preempt edilip edilemeyeceğidir. Eski çekirdekler çekirdek içinde preemption'a izin vermezdi; bu, gerçek zamanlı yanıt sürelerini kötüleştirirdi. Modern çekirdekler, dikkatlice tanımlanmış güvenli noktalarda çekirdek kodunun da preempt edilmesine izin verecek biçimde tasarlanmıştır. Ancak bir çekirdek, kritik bir kilit tutarken veya kesmeleri devre dışı bıraktığı bir bölümde preempt edilmemelidir; aksi halde tutarsızlık ve deadlock doğar. Bu yüzden çekirdekler "preemption disable" sayaçlarıyla, hangi anlarda el koymanın güvenli olduğunu titizlikle yönetir.

## Öncelik ve Scheduling Algoritmaları

### Tanım

**Scheduling** (zamanlama), birden fazla çalışmaya hazır (ready) thread arasından hangisinin CPU'yu alacağına karar verme sürecidir. Bu kararı veren çekirdek bileşenine **scheduler** denir. **Öncelik** (priority), scheduler'a "kimin daha önemli olduğunu" söyleyen sayısal bir değerdir.

### Scheduling'in Çelişen Hedefleri

Scheduler tasarımı bir denge sanatıdır çünkü hedefler birbiriyle çatışır. **Throughput** (birim zamanda tamamlanan iş) yüksek olmalı; **latency / response time** (bir işin başlaması veya tamamlanmasına kadar geçen süre) düşük olmalı; **fairness** (hiçbir thread'in aç kalmaması) sağlanmalı; ve **verimlilik** için context switch overhead'i düşük tutulmalıdır. Etkileşimli bir masaüstünde düşük gecikme önemliyken, bir batch hesaplama sunucusunda throughput önceliklidir. Bu yüzden tek bir "en iyi" algoritma yoktur; iş yüküne göre değişir.

### Temel Algoritmalar ve Mantıkları

**FCFS (First-Come, First-Served)** en basitidir: gelen sırayla çalıştırır. Ancak uzun bir iş, arkasındaki kısa işleri bekletir; bu "convoy effect" (konvoy etkisi) latency'yi berbat eder.

**Round Robin**, her thread'e sabit bir quantum verir ve süre dolunca sıranın sonuna atar. Bu, adaleti sağlar ve etkileşimli sistemler için iyidir. Quantum seçimi kritiktir: çok küçük quantum, aşırı context switch overhead'i doğurur; çok büyük quantum, sistemi FCFS'e yaklaştırıp yanıt süresini bozar.

**Priority Scheduling**, en yüksek öncelikli hazır thread'i seçer. Gerçekçi sistemlerin çoğu bunun bir türevidir. Ancak saf öncelik zamanlaması, düşük öncelikli thread'lerin hiç çalışamadığı **starvation** (açlık) sorununu doğurur.

Modern genel amaçlı sistemler bunları harmanlar. Bir yaklaşım **MLFQ** (Multi-Level Feedback Queue): thread'ler önceliğe göre kuyruklara ayrılır ve davranışlarına göre kuyruklar arasında hareket ederler. CPU'yu çok tüketen (CPU-bound) bir thread zamanla daha düşük önceliğe iner; sık bloklayan, etkileşimli (I/O-bound) bir thread yüksek öncelikte kalır. Böylece sistem, thread'lerin niyetini önceden bilmeden davranışlarından öğrenir ve etkileşimli işlere düşük gecikme sağlar. Linux'un uzun süredir kullanılan **CFS** (Completely Fair Scheduler) yaklaşımı ise farklı bir felsefe izler: her thread'in aldığı CPU zamanını "virtual runtime" olarak izler ve en az almış olana CPU verir; böylece adaleti sürekli dengede tutmaya çalışır. Öncelik değerleri (nice değeri) burada, virtual runtime'ın hangi hızla ilerleyeceğini ayarlayan bir ağırlık gibi çalışır.

### I/O-Bound ve CPU-Bound Ayrımı

İyi bir scheduler'ın en önemli sezgisi, **I/O-bound** ve **CPU-bound** thread'leri ayırt etmesidir. I/O-bound thread'ler kısa süre CPU kullanıp uzun süre I/O bekler (örneğin klavye girdisi bekleyen bir editör). Bunlara yüksek öncelik ve hızlı yanıt vermek, hem kullanıcı deneyimini iyileştirir hem de sistem genel verimliliğini artırır; çünkü bu thread'ler nasılsa çabucak I/O'ya dönüp CPU'yu bırakacaktır. CPU-bound thread'ler ise CPU'yu uzun süre tutar ve gecikmeye daha az duyarlıdır. Bu ayrımı davranıştan çıkarmak, MLFQ gibi algoritmaların temel dehasıdır.

## Yaygın Hatalar ve Tuzaklar

### Priority Inversion

En ünlü ve öğretici tuzak **priority inversion** (öncelik tersine dönmesi): yüksek öncelikli bir thread (H), düşük öncelikli bir thread'in (L) tuttuğu bir kilidi bekler. Bu sırada orta öncelikli bir thread (M) devreye girip L'yi preempt eder. Sonuç şudur: H, aslında kendisinden düşük olan M yüzünden dolaylı olarak bloke olur; öncelik sırası fiilen tersine döner. Bu, gerçek zamanlı sistemlerde felaketle sonuçlanabilir; nitekim geçmişte bir uzay görevinde bu türden bir sorunun sistem sıfırlamalarına yol açtığı iyi bilinen bir mühendislik dersidir. Çözüm genellikle **priority inheritance** (öncelik kalıtımı): L, H'nin beklediği kilidi tuttuğu sürece geçici olarak H'nin önceliğine yükseltilir, böylece M onu preempt edemez ve kilit çabucak serbest kalır.

### Race Condition ve Yetersiz Senkronizasyon

Thread'lerin paylaşılan veriye senkronizasyon olmadan erişmesi, **race condition**'a yol açar; sonuç, thread'lerin zamanlamasına bağlı olarak değişen ve tekrar üretilmesi çok zor olan hatalardır. Buradaki tuzak, "nadiren oluyor, önemli değildir" yanılgısıdır; oysa üretim yükü altında zamanlama desenleri değişir ve hata beklenmedik anda patlar.

### Aşırı Thread Oluşturma

Her isteğe bir thread açmak sezgisel görünse de, binlerce thread context switch overhead'i ve bellek tüketimi (her thread'in kendi stack'i vardır) nedeniyle sistemi yavaşlatır. Doğru yaklaşım genellikle **thread pool** (iş parçacığı havuzu) kullanmaktır: sabit sayıda thread önceden oluşturulur ve işler bir kuyruğa alınıp bu thread'lere dağıtılır.

### Busy-Waiting

Bir kaynağın serbest kalmasını bir döngüde CPU'yu boşa yakarak beklemek (busy-wait / spin), kısa beklemeler için (özellikle çok çekirdekli sistemlerde) yerinde olabilir; ancak uzun beklemelerde bu, CPU'yu israf eder ve başka thread'lerin çalışmasını engeller. Uzun beklemeler için thread'i bloke edip CPU'yu bırakan (sleep/wait) yöntemler tercih edilmelidir. Modern kilitler çoğu zaman ikisini birleştiren "adaptive" davranış sergiler.

### CPU Affinity'yi Yok Saymak

Bir thread'i sürekli farklı çekirdeklere taşımak, o çekirdeğin cache'inde biriken sıcak veriyi işe yaramaz hale getirir. Yoğun performans gerektiren sistemlerde **CPU affinity** (bir thread'i belirli çekirdeklere bağlama) ve NUMA (Non-Uniform Memory Access) topolojisine saygı, cache lokalitesini koruyarak ciddi kazanç sağlayabilir.

## En İyi Pratikler

**İzolasyon ihtiyacına göre birim seç.** Bileşenler arasında güçlü güvenlik/hata izolasyonu gerekiyorsa ayrı process'ler kullan; sıkı ve hızlı veri paylaşımı gerekiyorsa aynı process içinde thread'ler kullan. Modern tarayıcılar sekmeleri ayrı process'lerde çalıştırarak bir sekmenin çökmesinin diğerlerini etkilemesini önler; bu, izolasyon-performans dengesinin bilinçli bir örneğidir.

**Paylaşılan durumu en aza indir.** Concurrency hatalarının çoğu paylaşılan değiştirilebilir (mutable) durumdan doğar. Mümkün olduğunca immutable veri, mesaj geçişi (message passing) veya thread-local depolama kullanarak paylaşımı azalt. "Paylaşarak iletişim kurma; ileterek paylaş" ilkesi bu felsefeyi özetler.

**Kilitleri kısa tut ve tutarlı sırala.** Bir kilit ne kadar uzun tutulursa, o kadar çok thread bekler ve preemption ile birleşince priority inversion riski artar. Ayrıca birden fazla kilit alınıyorsa, tüm thread'ler kilitleri hep aynı global sırayla almalıdır; aksi halde klasik deadlock (döngüsel bekleme) doğar.

**Context switch'i ölç, tahmin etme.** Yüksek CPU kullanımının nedeni gerçek iş mi yoksa scheduling overhead'i mi olduğunu ayırt etmek için voluntary/involuntary switch sayaçlarını, run queue uzunluğunu ve cache miss oranlarını izle. Optimizasyon kararları ölçüme dayanmalıdır.

**Önceliği dikkatli kullan.** Bir thread'e yüksek öncelik vermek, başka bir thread'i aç bırakmak demektir. Öncelikleri yalnızca gerçek gecikme gereksinimi olan (örneğin ses/video işleme) yollar için yükselt ve starvation'a karşı yaşlandırma (aging) veya adalet mekanizmalarının devrede olduğundan emin ol.

**Doğru concurrency modelini seç.** Çok sayıda I/O-bound bağlantı için thread yerine asenkron/event-driven modeller genellikle daha ölçeklenebilirdir. CPU-bound paralel hesaplama için ise çekirdek sayısı kadar worker thread ile veri paralelliği daha uygundur. Aracı thread yerine iş yükünün doğasına bakmak, doğru mimariye götüren pusuladır.

## Sonuç

Process, thread ve scheduling üçlüsü, aslında tek bir mühendislik gerilimin farklı yüzleridir: **paylaşım ile izolasyon**, **verimlilik ile adalet**, **yanıt hızı ile throughput** arasındaki denge. İzolasyon güvenlik ve dayanıklılık verir ama paylaşımı ve performansı zorlaştırır. Context switch çoklu görevi mümkün kılar ama görünmez bir cache/TLB bedeli taşır. Preemption sistemin kontrolü elde tutmasını sağlar ama çekirdek içi tutarlılığı korumak için titiz bir tasarım ister. Öncelik önemli işleri öne çıkarır ama yanlış kullanılırsa starvation ve priority inversion üretir. Bu kavramları "neden böyle" sorusuyla anlayan bir mühendis, yalnızca sistemleri hızlandırmakla kalmaz; onların neden yavaşladığını, neden kilitlendiğini ve neden çöktüğünü de doğru teşhis eder.
