# Süreçler Arası İletişim (IPC)

## Tanım

Süreçler Arası İletişim (Inter-Process Communication, IPC), birbirinden bağımsız çalışan süreçlerin (process) veri alışverişi yapmasını ve eylemlerini eşgüdümlemesini (senkronize etmesini) sağlayan mekanizmaların tümüne verilen addır. Buradaki "bağımsızlık" kavramı kritiktir: modern işletim sistemleri her sürece kendi izole bellek alanını (address space) verir. Bir sürecin `malloc` ile ayırdığı bir işaretçiyi başka bir sürece verseniz bile o adres karşı tarafta hiçbir anlam ifade etmez, çünkü sanal bellek (virtual memory) sayesinde her sürecin gördüğü adresler kendine özeldir. İşte tam da bu izolasyon nedeniyle süreçler birbirleriyle "doğrudan" konuşamaz; araya işletim sisteminin sağladığı bir köprünün girmesi gerekir. IPC, bu köprünün ta kendisidir.

IPC'yi tek bir şeymiş gibi düşünmek yanıltıcıdır. Aslında farklı ihtiyaçlara cevap veren bir mekanizma ailesidir: bazıları basit bir bayt akışı (byte stream) sunar (pipe, socket), bazıları en yüksek hızı hedefler (shared memory), bazıları yapısal mesaj sınırlarını korur (message queue), bazıları ise sadece "bir şey oldu" bilgisini iletir (signal). Doğru mekanizmayı seçmek, çoğu zaman performans, doğruluk ve karmaşıklık arasında bilinçli bir denge kurmak demektir.

## Kök Neden: IPC Neden Var ve Neden Zordur?

IPC'nin varlık nedenini anlamak için önce izolasyonun neden var olduğunu anlamak gerekir. Eğer tüm süreçler aynı belleği paylaşsaydı, bir programdaki bir hata (örneğin bir null pointer dereference ya da buffer overflow) tüm sistemi çökertebilirdi. İzolasyon bir güvenlik ve kararlılık kalkanıdır. Ancak her kalkan aynı zamanda bir duvardır. IPC, bu duvarda işletim sisteminin denetlediği, kontrollü kapılar açar.

Buradaki en derin gerçek şudur: **her IPC işlemi, verinin bir güvenlik sınırından (kullanıcı alanı ile çekirdek alanı arasından) geçmesini gerektirir.** Bir süreç veri gönderdiğinde, o veri tipik olarak önce kullanıcı alanından (user space) çekirdek alanına (kernel space) kopyalanır; alıcı süreç okuduğunda ise çekirdekten tekrar kendi kullanıcı alanına kopyalanır. Bu iki kopyalama (double copy) ve beraberindeki sistem çağrısı (system call) maliyeti, pipe ve socket gibi mekanizmaların temel performans tavanını belirler. Shared memory'nin neden bu kadar hızlı olduğunu ancak bu bağlamda gerçekten kavrayabilirsiniz: shared memory bu kopyalamayı tamamen ortadan kaldırır, çünkü iki süreç aynı fiziksel bellek sayfalarını (physical memory pages) kendi sanal adres alanlarına eşler (map eder).

IPC'yi zorlaştıran ikinci kök neden **eşzamanlılıktır (concurrency)**. İki süreç aynı kaynağa aynı anda eriştiğinde, işlemlerin sırası önceden garanti edilemez. Bu belirsizlik, kötü tasarlanmış IPC'de race condition'lara, veri bozulmasına ve kilitlenmelere (deadlock) yol açar. Bu yüzden IPC mekanizmalarının çoğu, sadece "veri taşıma" değil, aynı zamanda "eşgüdüm" (synchronization) sorununu da çözmek zorundadır. Kimi mekanizma bu eşgüdümü kendi içinde hazır sunar (bir message queue'da mesaj atomiktir), kimisi ise (shared memory) size sadece belleği verir ve eşgüdümü tamamen sizin sorumluluğunuza bırakır. Bu ayrımı içselleştirmek, hangi mekanizmanın neden "kolay ama yavaş" ya da "hızlı ama tehlikeli" olduğunu açıklar.

## Pipe (Boru)

### Çalışma Mantığı

Pipe, en eski ve en zarif IPC mekanizmalarından biridir. Adı bir su borusunu çağrıştırır ve mantığı da tam olarak budur: bir uçtan bayt yazarsınız, diğer uçtan aynı baytlar aynı sırayla çıkar. Pipe tek yönlüdür (unidirectional): bir ucu yazma, diğer ucu okuma içindir. Çekirdek, arada sabit boyutlu bir tampon (kernel buffer) tutar.

Pipe'ı asıl büyülü kılan, süreçlerin çekirdeğin yönettiği bu tamponu bir tür üretici-tüketici (producer-consumer) kuyruğu olarak kullanmasıdır. Yazan taraf tamponu doldurursa `write` çağrısı bloke olur (bekler); okuyan taraf tamponu boşaltırsa `read` çağrısı bloke olur. Bu otomatik akış denetimi (flow control), pipe'ı bu kadar güvenilir kılan şeydir; hiçbir taraf diğerini ezip geçemez.

İki türü vardır. **Anonim (isimsiz) pipe**, yalnızca akrabalık ilişkisi olan süreçler (bir ana süreç ve `fork` ile ürettiği alt süreç) arasında kullanılır, çünkü paylaşım dosya tanımlayıcılarının (file descriptor) miras yoluyla aktarılmasına dayanır. **Named pipe (FIFO)** ise dosya sisteminde bir isme sahiptir ve akraba olmayan, birbirinden habersiz süreçler bile aynı ismi açarak haberleşebilir.

### Somut Örnek

Kabuktaki (shell) `|` operatörü, doğrudan anonim pipe'tır. `ls | grep txt` yazdığınızda kabuk şunları yapar: bir pipe oluşturur, `fork` ile iki alt süreç yaratır, `ls`'in standart çıktısını (stdout) pipe'ın yazma ucuna, `grep`'in standart girdisini (stdin) pipe'ın okuma ucuna yönlendirir (dup2 ile). `ls` çıktı ürettikçe `grep` onu tüketir. İşte kabukların gücünün çekirdeğinde yatan mekanizma budur.

### Doğru Kullanım ve Tuzaklar

Pipe kullanırken en sık düşülen tuzak, **kullanılmayan uçları kapatmayı unutmaktır.** Bunun neden kritik olduğunu anlamak için akış mantığını hatırlayın: okuyan süreç, yazma ucunun tümü kapandığında EOF (dosya sonu) alır ve `read` çağrısı 0 döndürür. Ancak yazma ucunu tutan bir dosya tanımlayıcı hâlâ açıksa (örneğin ana sürecin unuttuğu bir kopya), okuyan süreç sonsuza kadar bekler; program asılı kalır. Simetrik biçimde, okuyan tüm uçlar kapalıyken bir yazma denemesi `SIGPIPE` sinyali doğurur ve varsayılan olarak yazan süreci öldürür. Bu iki davranış, "neden programım kilitlendi" ya da "neden aniden öldü" sorularının en yaygın cevabıdır.

## Socket (Yuva)

### Çalışma Mantığı

Socket, IPC'nin en genel ve en güçlü soyutlamasıdır. Temel fikri, iletişimin bir "uç nokta" (endpoint) üzerinden yapılmasıdır. Socket'i pipe'tan ayıran iki temel üstünlük vardır. Birincisi, socket iki yönlüdür (full-duplex): tek bir bağlantı üzerinden her iki taraf da aynı anda okuyup yazabilir. İkincisi ve daha önemlisi, socket'ler makine sınırını aşabilir; aynı API ile hem aynı makinedeki süreçler hem de ağ üzerindeki farklı makinelerdeki süreçler haberleşir. Bu tekdüzelik, socket'i modern dağıtık sistemlerin (distributed systems) temel taşı yapar.

Yerel IPC için özel bir tür vardır: **Unix domain socket (UDS)**. Bu socket ağ yığınını (TCP/IP stack) hiç kullanmaz; veri çekirdek içinde doğrudan taşınır. Bu yüzden aynı makinedeki iki süreç için Unix domain socket, `localhost` üzerinden TCP kullanmaktan belirgin biçimde daha hızlı ve daha az yüklüdür (checksum, paket başlıkları, üç aşamalı el sıkışma gibi ağ katmanı maliyetleri yoktur). Ayrıca dosya sistemi izinleriyle (file permissions) erişim denetimi sağlanabilir ve dosya tanımlayıcıları bir süreçten diğerine geçirme (fd passing) gibi güçlü özellikler sunar.

Socket'lerin iki temel aktarım (transport) modeli önemlidir. **Stream socket** (TCP ya da UDS-stream), güvenilir, sıralı, sınırsız bir bayt akışı verir; tıpkı pipe gibi mesaj sınırları yoktur. **Datagram socket** (UDP ya da UDS-datagram) ise ayrık mesajlar taşır; her mesaj korunur ama teslim ve sıra garanti edilmez.

### Neden Bayt Akışında Mesaj Sınırı Yoktur (Kritik Kavram)

Burada, geliştiricilerin en sık yanıldığı bir noktayı vurgulamak gerekir. Stream socket ya da pipe ile "mesaj" gönderdiğinizi sanırsınız, ama aslında sadece bayt gönderiyorsunuzdur. Karşı taraf üç ayrı `send` çağrınızı tek bir `recv` ile birleşik olarak alabilir ya da tek bir `send`'inizi birden fazla parçada okuyabilir. Buna genelde **TCP'de "message framing" sorunu** denir. Kök nedeni, TCP'nin mesaj değil akış protokolü olmasıdır; veriyi ağ verimliliği için birleştirir veya böler. Bu yüzden akış tabanlı iletişimde mesaj sınırlarını **kendiniz** tanımlamak zorundasınız: ya her mesajın başına uzunluğunu yazarak (length-prefixing) ya da özel bir ayraç (delimiter) kullanarak. Bu adımı atlamak, düşük trafikte çalışıp yük altında bozulan, teşhisi zor hatalara yol açar.

### Doğru Kullanım ve Tuzaklar

Socket programlamanın en sinsi tuzaklarından biri **kısmi yazma/okuma (partial read/write)** durumudur. Bir `write` çağrısının, gönderdiğiniz baytların tamamını değil bir kısmını yazması tamamen normaldir; dönüş değeri gerçekte kaç bayt işlendiğini söyler. Bunu kontrol etmeyip "hepsi yazıldı" varsaymak, veri kaybına yol açar. Doğru yaklaşım, geriye kalan baytları bir döngüde tekrar göndermektir.

## Shared Memory (Paylaşımlı Bellek)

### Çalışma Mantığı ve Neden En Hızlısıdır

Shared memory, IPC mekanizmaları arasında ham hız bakımından zirvededir ve bunun nedeni yukarıda değindiğimiz kök gerçekte yatar. Diğer tüm mekanizmalar (pipe, socket, message queue) veriyi çekirdek üzerinden kopyalar. Shared memory ise iki ya da daha fazla sürecin aynı fiziksel bellek sayfalarını kendi sanal adres alanlarına eşlemesini (map) sağlar. Bir süreç o belleğe bir değer yazdığında, diğer süreç aynı anda o değeri hiçbir sistem çağrısı ya da kopyalama olmadan görür; çünkü ikisi de gerçekte aynı RAM'e bakmaktadır. İşte bu "sıfır kopya" (zero-copy) doğası, onu büyük veri blokları için ideal kılar.

Ancak bu hızın bir bedeli vardır ve bu bedel felsefi olarak önemlidir: **shared memory size sadece belleği verir, eşgüdümü vermez.** İşletim sistemi burada bir hakem rolü üstlenmez. İki süreç aynı bölgeye aynı anda yazarsa ne olacağını hiçbir şey garanti etmez; sonuç bozuk, yarı yazılmış veridir. Dolayısıyla shared memory neredeyse hiçbir zaman tek başına kullanılmaz; her zaman bir eşgüdüm mekanizmasıyla (semaphore, mutex ya da bellek içi atomik işlemler) birlikte kullanılır. Shared memory "otoyol", semaphore ise o otoyoldaki "trafik ışığıdır"; ışık olmadan otoyol bir kaza mahalline döner.

### Somut Örnek ve Tuzaklar

Tipik kullanım şöyledir: bir süreç isimlendirilmiş bir paylaşımlı bellek nesnesi oluşturur, belirli bir boyuta ayarlar, kendi adres alanına eşler ve içine bir veri yapısı yerleştirir. Diğer süreç aynı ismi açıp aynı bölgeyi eşler. Artık ikisi de aynı struct'ı görür. Aralarına bir semaphore koyarak "ben yazarken sen okuma" kuralını dayatırlar.

Buradaki en tehlikeli tuzaklar şunlardır. Birincisi, **eşgüdümü unutmak** (yukarıda anlatıldı) ve race condition yaşamak. İkincisi, paylaşımlı belleğe **doğrudan işaretçi (pointer) yazmak.** Neden yanlış? Çünkü her sürecin sanal adresleri farklıdır; bir süreçte geçerli olan bir işaretçi diğerinde bambaşka (ve muhtemelen geçersiz) bir yeri gösterir. Paylaşımlı bellekte yalnızca kendi kendine yeten (self-contained) veriler ya da bölge başına göreli ofsetler (offset) saklanmalıdır. Üçüncüsü, **kaynak temizliği**: paylaşımlı bellek nesneleri, onları oluşturan süreç ölse bile sistemde kalıcı olabilir ("kalıntı" nesneler); açıkça silinmezlerse sistem kaynaklarını sızdırırlar.

## Message Queue (Mesaj Kuyruğu)

### Çalışma Mantığı

Message queue, pipe ve socket'in aksine, **mesaj sınırlarını koruyan** bir IPC mekanizmasıdır. Bir mesaj gönderdiğinizde, alıcı o mesajı tam olarak bir bütün halinde alır; asla yarım ya da başka bir mesajla birleşik almaz. Bu, akış tabanlı mekanizmalardaki framing sorununu kökten ortadan kaldırır. Çekirdek, mesajları bir kuyrukta tutar ve alıcı hazır olduğunda teker teker teslim eder.

Message queue'nun sunduğu iki değerli özellik daha vardır. Birincisi, gönderici ile alıcının aynı anda hazır olması gerekmez (asynchronous / decoupling). Gönderen mesajı bırakıp yoluna devam eder; alıcı sonra gelip alır. Bu gevşek bağlılık (loose coupling), sistem tasarımında büyük esneklik sağlar. İkincisi, bazı message queue türleri **öncelik (priority)** destekler; acil mesajlar kuyrukta öne geçer.

Burada bir kavram ayrımı önemlidir. İşletim sisteminin çekirdek düzeyinde sağladığı message queue'lar (örneğin POSIX message queue) genellikle **aynı makinedeki** süreçler içindir ve boyut olarak sınırlıdır. Bunları, ağ üzerinden çalışan ve ayrı birer sunucu ürünü olan **message broker** sistemleriyle (örneğin kuyruk tabanlı mesajlaşma altyapıları) karıştırmamak gerekir; ikincisi çok daha büyük, kalıcı ve dağıtık bir katmandır. Kavram benzese de ölçek ve kullanım alanı farklıdır.

### Doğru Kullanım ve Tuzaklar

Message queue'nun rahatlığı, onu "bedava" sanmaya iter, oysa değildir. Her mesaj yine çekirdek üzerinden kopyalanır; yani shared memory kadar hızlı değildir. Büyük veri blokları için message queue kullanmak verimsizdir; bu durumda yaygın bir desen, asıl büyük veriyi shared memory'de tutup message queue ile sadece "veri hazır, şu bölgede" gibi küçük bir bildirim göndermektir.

Diğer bir tuzak, **kuyruğun dolmasıdır.** Kuyrukların sonlu bir kapasitesi vardır. Alıcı, göndericiden yavaşsa kuyruk dolar; bu durumda gönderme çağrısı ya bloke olur ya da (non-blocking modda) hata döner. Bu "backpressure" davranışını görmezden gelmek, ya asılı kalan ya da sessizce mesaj kaybeden sistemlere yol açar.

## Signal (Sinyal)

### Çalışma Mantığı

Signal, diğer tüm IPC mekanizmalarından temelde farklıdır çünkü **veri taşımaz; sadece bir olayı haber verir.** Signal, bir sürece yapılan yazılımsal bir kesme (software interrupt) gibidir. Çekirdek ya da başka bir süreç, hedef sürece bir sinyal gönderir; hedef sürecin normal akışı anında durur ve önceden tanımlanmış bir sinyal işleyicisi (signal handler) çalışır, sonra akış kaldığı yerden devam eder.

Signal'lerin varlık nedeni asenkron olaylardır: kullanıcının Ctrl+C'ye basması (kesme sinyali), bir alt sürecin sonlanması, geçersiz bir bellek erişimi (segmentation fault aslında bir sinyaldir), ya da bir zamanlayıcının dolması. Bunlar programın akışıyla eşzamanlı değildir; "her an" olabilirler. Signal, işletim sisteminin bu "her an olabilecek" olayları programa bildirme yöntemidir.

### Neden Signal Handler İçinde Dikkatli Olmak Zorundasınız (En Derin Tuzak)

Signal'lerin en yanlış anlaşılan ve en tehlikeli yönü, sinyal işleyicilerinin çalıştığı bağlamdır. Bir sinyal, sürecin herhangi bir anında, hatta bir kütüphane fonksiyonunun tam ortasında gelebilir. İşleyici çalışırken, kesintiye uğrattığı kod yarım kalmış durumdadır. Eğer işleyici içinde, kesilen kodun kullandığı bir kaynağa (örneğin bellek ayırma kilitleri) dokunan bir fonksiyon çağırırsanız, kilitlenme ya da bellek bozulması yaşarsınız.

İşte bu yüzden signal handler içinde yalnızca **"async-signal-safe"** olarak tanımlanmış, sınırlı bir fonksiyon kümesi güvenle çağrılabilir. Örneğin işleyici içinde bellek ayırmak, konsola karmaşık çıktı basmak ya da çoğu standart kütüphane fonksiyonunu çağırmak güvenli değildir; kulağa masum gelse de nadir ve teşhisi çok zor çökmelere yol açar. Doğru desen, işleyicinin işini asgariye indirmesidir: genellikle sadece bir bayrak (flag) değerini `volatile sig_atomic_t` tipinde bir değişkende ayarlamak ve asıl işi ana döngüye bırakmak en güvenli yaklaşımdır.

İkinci önemli nokta, bazı sinyallerin (örneğin durdurma amaçlı olanların) **yakalanamaz ya da yok sayılamaz** olmasıdır; bunlar sistem yöneticisine sürecin kesin biçimde sonlandırılabilmesi için bir garanti sunar. Ayrıca, klasik sinyaller **kuyruklanmaz**; aynı sinyal işlenmeden önce birkaç kez gelirse, çoğu durumda tek bir sinyal olarak görünür. Yani signal, "kaç kez oldu" bilgisini güvenilir biçimde taşımaz, yalnızca "en az bir kez oldu" bilgisini taşır. Bu yüzden signal, sayaç ya da veri kanalı olarak değil, yalnızca bir uyarı ziliyle olarak kullanılmalıdır.

## Doğru Mekanizmayı Seçmek: Karşılaştırmalı Akıl Yürütme

Bir IPC mekanizması seçerken sormanız gereken sorular, mekanizmaların kök özelliklerinden doğrudan türer:

**Veri mi yoksa sadece bir bildirim mi taşıyorum?** Eğer sadece "bir olay oldu" demek istiyorsanız signal yeterli ve en hafif çözümdür. Veri taşıyacaksanız signal dışı bir mekanizma gerekir.

**Ne kadar hız gerekiyor ve veri ne kadar büyük?** Küçük ya da orta boyutlu, akış tabanlı veri için pipe ya da Unix domain socket idealdir; hem basit hem de akış denetimi hazır gelir. Çok büyük veri blokları ya da mikrosaniye düzeyinde gecikme istiyorsanız, kopyalamayı ortadan kaldıran shared memory kaçınılmazdır; ama eşgüdüm yükünü göze almanız gerekir.

**Mesaj sınırları benim için önemli mi?** Eğer her mesajın bütünlüğü korunmalıysa ve framing kodu yazmak istemiyorsanız, message queue ya da datagram socket doğal seçimdir. Akış tabanlı bir çözüm seçerseniz framing'i kendiniz halletmek zorundasınız.

**Aynı makinede mi, ağ üzerinde mi?** Aynı makinede en verimli çözüm Unix domain socket ya da shared memory'dir. Farklı makinelere yayılacaksanız, ağ socket'leri (TCP/UDP) ya da bir message broker katmanı gerekir. Burada önemli bir tasarım ilkesi vardır: bugün aynı makinede olan iki bileşen yarın ayrılabilir; socket API'sini kullanmak, yerelden ağa geçişi neredeyse ücretsiz kılar. Bu ileri görüşlülük, socket'in neden bu kadar yaygın tercih edildiğini açıklar.

## Yaygın Hatalar (Toplu Değerlendirme)

Farklı mekanizmalarda tekrar eden, sistemik hata örüntüleri vardır ve bunları bir arada görmek öğreticidir.

**Kaynak sızıntısı.** Pipe uçlarını, socket bağlantılarını, paylaşımlı bellek nesnelerini ve mesaj kuyruklarını açtıktan sonra kapatmayı ya da silmeyi unutmak en yaygın hatadır. Özellikle isimlendirilmiş kaynaklar (named pipe, POSIX shared memory, POSIX message queue), süreç ölse bile sistemde kalabilir. Bu kalıntılar zamanla kaynak tükenmesine yol açar.

**Eşgüdümün ihmal edilmesi.** Özellikle shared memory'de, ama aynı zamanda paylaşılan her kaynakta, eşzamanlı erişim denetimi olmadan race condition kaçınılmazdır. "Şimdilik çalışıyor" tuzağı sinsidir çünkü hata yalnızca belirli zamanlama koşullarında ortaya çıkar; test ortamında görünmez, üretimde yük altında patlar.

**Kısmi işlem varsayımı.** Socket ve pipe'ta bir `read`/`write` çağrısının istenen bayt sayısının tamamını işlediğini varsaymak yanlıştır. Dönüş değerini kontrol etmemek, sessiz veri bozulmasının başlıca kaynağıdır.

**Framing eksikliği.** Akış tabanlı iletişimde mesaj sınırlarını kendiniz tanımlamamak, düşük yükte gizlenip yüksek yükte ortaya çıkan hatalara neden olur.

**Signal handler'da güvenli olmayan işlemler.** İşleyici içinde async-signal-safe olmayan fonksiyonlar çağırmak, nadir ama ölümcül kilitlenmelere yol açar.

**Bloklanma davranışını yanlış yönetmek.** Dolu bir kuyruğa yazmak, boş bir pipe'tan okumak, hazır olmayan bir bağlantıdan veri beklemek; bunların hepsi bloke olabilir. Bu blokların ne zaman olacağını anlamamak, deadlock'un temel kaynağıdır. Örneğin iki süreç karşılıklı olarak birbirinin okumasını beklerken ikisi de yazmaya çalışırsa, klasik bir pipe/socket deadlock'u oluşur.

## En İyi Pratikler

**En basit yeterli mekanizmayı seçin.** Shared memory çok hızlıdır ama en karmaşık ve en hataya açık olanıdır. Eğer pipe ya da socket işinizi görüyorsa, sırf hız cazibesiyle shared memory'e atlamak çoğu zaman erken optimizasyondur. Önce doğruluk, sonra ölçülmüş bir ihtiyaç varsa hız.

**Mesaj protokolünüzü açıkça tanımlayın.** Akış tabanlı bir kanal kullanıyorsanız, mesaj sınırlarını ilk günden itibaren length-prefixing ya da net bir ayraçla belirleyin. Bu, en pahalıya patlayan hatalardan birini baştan engeller.

**Her zaman dönüş değerlerini ve hata durumlarını kontrol edin.** IPC çağrıları, ağ ve kaynak sınırlarıyla iç içe olduğundan, "her şey yolunda gidecek" varsayımı burada özellikle tehlikelidir. Kısmi işlemleri, kesilen sistem çağrılarını ve karşı tarafın aniden kapanmasını (broken pipe, connection reset) açıkça ele alın.

**Eşgüdümü mekanizmadan ayrı düşünmeyin.** Shared memory kullanıyorsanız, hangi semaphore ya da mutex'in hangi bölgeyi koruduğunu tasarımın ilk aşamasında netleştirin. Kilitlenme sırasını (lock ordering) tutarlı tutarak deadlock'u yapısal olarak önleyin.

**Kaynak yaşam döngüsünü sahiplenin.** Her açtığınız IPC kaynağının kim tarafından ve ne zaman temizleneceğini net biçimde belirleyin. İsimlendirilmiş kaynakları program başlangıcında olası kalıntılara karşı kontrol edin ve düzgün kapanışta (graceful shutdown) mutlaka temizleyin.

**Signal'i sade tutun.** Sinyal işleyicilerini olabildiğince küçük yapın; ideali sadece bir bayrak ayarlamaktır. Karmaşık iş mantığını asla işleyici içine koymayın. Modern kod tabanlarında, sinyalleri bir dosya tanımlayıcısı üzerinden okunabilir olaylara çeviren desenler, sinyal güvenliği sorununu ana olay döngüsüyle bütünleştirerek zarifçe çözer.

**Güvenlik sınırını unutmayın.** IPC, farklı ayrıcalık düzeylerine sahip süreçler arasında bir köprü olabilir. Karşı taraftan gelen veriyi asla körü körüne güvenmeyin; boyutları doğrulayın, tampon sınırlarını denetleyin. Bir IPC kanalı, doğrulanmamış girdiyle beslenen bir buffer overflow ya da injection açığının taşıyıcısına dönüşebilir. Yerel IPC'de dosya sistemi izinleriyle erişim denetimini bilinçli tasarlayın.

## Kapanış

IPC'nin tüm çeşitliliğinin altında tek bir gerilim yatar: izolasyonun getirdiği güvenlik ile iletişimin gerektirdiği açıklık arasındaki denge. Pipe ve socket bu dengeyi basitlik ve güvenli akış denetimiyle kurar; shared memory hızı en üst düzeye çıkarmak için eşgüdüm sorumluluğunu size devreder; message queue mesaj bütünlüğü ve gevşek bağlılık sunar; signal ise en hafif haberleşme biçimi olarak yalnızca "bir şey oldu" der. Her mekanizmanın gücü de zayıflığı da aynı kök tasarım kararından doğar. Doğru IPC seçimi, bu kök kararları anlayıp kendi probleminizin gereksinimleriyle eşleştirmekten ibarettir. Mekanizmayı ezberlemek yerine neden öyle davrandığını kavradığınızda, hem doğru aracı seçer hem de o aracın klasik tuzaklarına düşmeden sağlam sistemler kurarsınız.
