# Konteyner Kaçışı ve Docker Güvenliği

## Giriş: Konteyner Neden "Tam Bir Sanal Makine" Değildir?

Konteyner teknolojisini (özellikle Docker'ı) doğru anlamak için önce bir yanlış anlamayı düzeltmek gerekir: Konteyner, sanal makine (VM) değildir. Bir VM'de misafir işletim sistemi kendi kernel'ine sahiptir ve hypervisor donanım seviyesinde katı bir izolasyon sağlar. Konteynerde ise durum tamamen farklıdır. Aynı makinede çalışan tüm konteynerler host'un **aynı Linux kernel'ini paylaşır**. Konteyner dediğimiz şey, aslında host üzerinde çalışan sıradan bir process'tir; sadece kernel'in sunduğu birtakım izolasyon mekanizmalarıyla "sanki kendi başına bir sistemdeymiş gibi" hissettirilir.

Bu tek cümle, konteyner güvenliğinin tüm mantığını açıklar. İzolasyon bir donanım duvarı değil, kernel'in tutmayı seçtiği bir dizi kuraldır. Kural gevşetilirse veya kernel'de bir açık bulunursa, konteynerdeki process host'a "kaçabilir" (container escape). İşte "konteyner kaçışı" dediğimiz şey budur: Konteyner sınırlarının dışına çıkıp host üzerinde, çoğu zaman root yetkileriyle işlem yapabilmek.

## Konteyner İzolasyonu Nasıl Çalışır? (Kök Neden)

Konteynerin izolasyonu üç temel kernel özelliğine dayanır. Kaçış tekniklerinin hepsi bu üçünden birini veya birkaçını hedefler, dolayısıyla bunları iyi anlamak şarttır.

### Namespaces (Ad Alanları)

Namespace'ler, bir process'in sistemin geri kalanını nasıl "gördüğünü" sınırlar. Her namespace türü bir kaynağı izole eder: `pid` namespace process listesini (konteyner içinde `ps` çalıştırınca sadece kendi process'lerini görürsün), `mnt` dosya sistemi bağlama noktalarını, `net` ağ arayüzlerini, `user` ise kullanıcı ve grup kimliklerini izole eder. `user` namespace özellikle önemlidir: Konteyner içinde UID 0 (root) olarak görünen bir process, host tarafında yetkisiz sıradan bir kullanıcıya (örneğin UID 100000) eşlenebilir. Bu eşleme (mapping) yapılmazsa, konteynerdeki root doğrudan host'un root'u olur ki tehlikenin büyük kısmı buradan doğar.

### Cgroups (Control Groups)

Cgroups, bir process grubunun ne kadar kaynak (CPU, bellek, disk I/O) kullanabileceğini sınırlar. Cgroups doğrudan bir "güvenlik" mekanizması gibi düşünülmese de, geçmişte cgroups'un belirli sürümlerindeki mekanizmalar (özellikle `release_agent` özelliği) kaçış için kötüye kullanılmıştır. Kaynak sınırlaması aynı zamanda bir DoS savunmasıdır: Sınır yoksa tek bir konteyner tüm host belleğini tüketip diğer her şeyi çökertebilir.

### Capabilities (Yetenekler)

Klasik Unix modelinde bir process ya root'tur (her şeyi yapabilir) ya da değildir. Linux capabilities bu "hep ya da hiç" modelini parçalara böler. Örneğin `CAP_NET_BIND_SERVICE` 1024 altındaki portlara bağlanma yetkisidir, `CAP_SYS_ADMIN` ise neredeyse "yeni root" diyebileceğimiz devasa bir yetki kümesidir. Docker, konteynerlere varsayılan olarak yeteneklerin yalnızca sınırlı bir alt kümesini verir ve tehlikelileri (örneğin `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`, `CAP_SYS_MODULE`) düşürür. Bu düşürme (drop) işlemi, konteyner root'unun host root'undan neden daha zayıf olduğunun temel sebebidir.

Bu üçlüye ek olarak Docker, **seccomp** (izin verilen syscall'ları filtreleyen bir beyaz/kara liste), **AppArmor/SELinux** (Mandatory Access Control profilleri) ve okunabilir/yazılabilir dosya sistemi kısıtlamaları gibi katmanlar ekler. Güvenlik, bu katmanların toplamıdır; herhangi birinin gevşetilmesi zinciri zayıflatır.

## Kaçışın Üç Büyük Kapısı

Pratikte konteyner kaçışlarının ezici çoğunluğu üç kategoriden birine girer. Bunlar bir kernel exploit'i gerektirmez; çoğu zaman **yanlış yapılandırma** sonucudur. Yani saldırgan sofistike bir 0-day kullanmaz, sadece açık bırakılmış kapıdan yürür.

### 1. `--privileged` Bayrağı: Kapının Tümüyle Açılması

`docker run --privileged` komutu, konteyner güvenliğinin neredeyse tamamını devre dışı bırakan tek bir bayraktır. Bu bayrak verildiğinde konteynere **tüm capabilities** verilir, seccomp ve AppArmor profilleri kaldırılır ve en kritik olarak host'un tüm aygıtlarına (`/dev` altındaki her şeye) erişim tanınır.

**Kök neden neden bu kadar tehlikeli?** Çünkü privileged bir konteyner host'un ham disk aygıtlarını (örneğin `/dev/sda`) görebilir. Konteyner ne kadar izole edilmiş olursa olsun, host'un fiziksel diskini doğrudan mount edebilen bir process host'un tüm dosya sistemine erişebilir demektir. İzolasyonun "dosya sistemi görünürlüğü" katmanı, altındaki blok aygıtına doğrudan erişimle tamamen anlamsızlaşır.

**İstismar mantığı (kavramsal):** Privileged bir konteynerde saldırganın izleyeceği yol tipik olarak şudur: Host'un blok aygıtlarını listelemek, host'un kök dosya sistemini barındıran aygıtı konteyner içinde bir dizine mount etmek, ve artık host'un `/etc`, kök kullanıcısının SSH anahtarları, hatta `/etc/shadow` dosyasına yazma erişimine sahip olmak. Buradan sonra bir cron job eklemek ya da bir SUID binary yerleştirmek host'ta kalıcı root elde etmek için yeterlidir. Ayrıca privileged mod, tarihsel olarak cgroups `release_agent` mekanizması üzerinden de kaçışa izin vermiştir: `release_agent`, bir cgroup boşaldığında host'ta çalıştırılacak bir betiğin yolunu tutar; privileged konteyner bu yolu kendi kontrolündeki bir betiğe ayarlayabildiği için host bağlamında kod çalıştırabilir.

**Savunma:** En basit ve en güçlü savunma, `--privileged` bayrağını **asla kullanmamaktır.** Gerçek dünyada bu bayrağa neredeyse hiç gerek yoktur; çoğu geliştirici bunu "bir şey çalışmadığında hızlı çözüm" olarak kullanır ve devasa bir açık bırakır. Eğer konteynerin gerçekten belirli bir aygıta erişmesi gerekiyorsa, tüm cihaz evrenini açan `--privileged` yerine yalnızca o aygıtı veren `--device=/dev/xxx` kullanılmalıdır. İhtiyaç duyulan tek bir yetenek varsa, o tek yetenek `--cap-add` ile eklenmeli, gerisi kapalı bırakılmalıdır.

### 2. Docker Socket'inin (`docker.sock`) Konteyner İçine Verilmesi

Docker daemon'ı (`dockerd`), Unix domain socket'i olan `/var/run/docker.sock` üzerinden komut alır. `docker` komut satırı aracı, aslında bu socket'e HTTP istekleri gönderen bir istemciden ibarettir. Bu socket'e erişebilen herkes, Docker API'sinin tamamına erişebilir.

Yaygın ve tehlikeli bir kalıp, bu socket'i bir konteynerin içine bind-mount etmektir: `-v /var/run/docker.sock:/var/run/docker.sock`. Bu genellikle "konteyner içinden Docker'ı yönetmek isteyen" araçlar (CI/CD runner'ları, Portainer benzeri yönetim panelleri, monitoring ajanları) için yapılır.

**Kök neden:** Docker daemon host'ta **root** olarak çalışır. Socket'e erişebilen bir konteyner, daemon'a "bana host'un kök dizinini mount eden, privileged, yeni bir konteyner başlat" diyebilir. Yani socket'e erişim, dolaylı ama tam bir host root erişimine eşdeğerdir. Konteynerin kendisi ne kadar sıkılaştırılmış olursa olsun fark etmez; socket üzerinden yaratacağı **yeni** konteynerin kısıtlamalarını saldırganın kendisi belirler.

**İstismar mantığı (kavramsal):** Saldırgan konteyner içine bir Docker istemcisi kurar (veya doğrudan socket'e HTTP istekleri yollar), host'un kök dosya sistemini (`/`) bir dizine mount eden yeni bir konteyner oluşturur, bu yeni konteyner içinde host'un dosya sistemine tam erişim elde eder. Sonuç yine host'ta root. Bu, `--privileged` kadar tehlikelidir, hatta daha sinsidir çünkü konteynerin kendisi masum görünür.

**Savunma:** Docker socket'ini bir konteynere vermek, o konteynere host root'u vermekle eşdeğerdir; bu şekilde düşünülmelidir. Eğer mutlaka gerekiyorsa: (a) Socket'i **salt okunur** vermek yeterli değildir, çünkü API'nin okuma çağrıları bile bilgi sızdırır ve bazı işlemler yine mümkün olabilir; asıl çözüm bunu hiç yapmamaktır. (b) Socket erişimine ihtiyaç duyan araçları izole bir host'ta çalıştırmak veya `docker-socket-proxy` gibi API çağrılarını filtreleyen bir ara katman kullanarak yalnızca gereken (örneğin salt okunur listeleme) endpoint'lere izin vermek. (c) **Rootless Docker** kullanmak: Bu modda daemon root yerine sıradan bir kullanıcı olarak çalışır, dolayısıyla socket ele geçirilse bile saldırgan host root'u değil sadece o kullanıcının yetkilerini elde eder. Bu, saldırının etki alanını dramatik biçimde küçültür.

### 3. Tehlikeli Capability'lerin Eklenmesi

Bazen `--privileged` kullanılmaz ama tek bir tehlikeli yetenek eklenerek benzer bir sonuca ulaşılır. En kritik örnek `CAP_SYS_ADMIN`'dir. Bu yetenek o kadar geniştir ki güvenlik topluluğunda yarı şaka "yeni root" olarak anılır; mount işlemleri, namespace manipülasyonu ve daha pek çok ayrıcalıklı işlemi mümkün kılar.

**Kök neden ve istismar mantığı:** `CAP_SYS_ADMIN` verilen bir konteyner, dosya sistemlerini mount edebilir. Bu, `--privileged`'da gördüğümüz mount tabanlı kaçış senaryolarının kapısını aralar. Benzer şekilde:

- **`CAP_SYS_MODULE`**: Kernel'e modül yükleme yeteneği. Bir saldırgan kötü amaçlı bir kernel modülü yükleyerek doğrudan kernel bağlamında, yani tüm izolasyon katmanlarının altında kod çalıştırabilir. Bu neredeyse anında ve tam bir kaçıştır.
- **`CAP_SYS_PTRACE`**: Diğer process'lerin belleğini okuma/yazma yeteneği. Eğer konteyner host process'lerini görebiliyorsa (örneğin `pid` namespace paylaşılmışsa, yani `--pid=host`), bu yetenek host process'lerine kod enjekte etmeye kapı açar.
- **`CAP_DAC_READ_SEARCH`**: Dosya izin kontrollerini atlayarak okuma. Bu, geçmişte `open_by_handle_at` gibi syscall'ları kötüye kullanan Shocker benzeri tekniklerle host dosya sistemine erişimde kullanılmıştır.

**Savunma:** Yeteneklerde temel ilke, **varsayılanı da güvenmemektir.** İyi bir sıkılaştırma, önce tüm yetenekleri düşürüp (`--cap-drop=ALL`) sonra uygulamanın gerçekten ihtiyaç duyduğu bir veya iki yeteneği tek tek geri eklemektir. Örneğin sadece ayrıcalıklı porta bağlanması gereken bir web sunucusu için `--cap-drop=ALL --cap-add=NET_BIND_SERVICE` deseni idealdir. Bir uygulamanın hangi yeteneklere ihtiyaç duyduğunu bilmiyorsanız, hepsini düşürüp çalıştırın; hata verirse eksik yeteneği ekleyin. Bu "en az ayrıcalık" (least privilege) yaklaşımı, saldırı yüzeyini en aza indirir.

## Kernel Açıkları Yoluyla Kaçış

Yanlış yapılandırmaların dışında, ikinci büyük kategori kernel veya container runtime'ının kendisindeki güvenlik açıklarıdır. Konteynerler kernel'i paylaştığı için, kernel'de ayrıcalık yükseltmeye (privilege escalation) izin veren bir açık, çoğu zaman doğrudan bir konteyner kaçışına dönüşebilir.

Tarihsel olarak container ekosisteminde çok etkili olmuş bir açık türü, `runc` (Docker ve Kubernetes'in altında çalışan düşük seviyeli runtime) ile ilgili olanlardır. Bunlardan en bilineni, kötü amaçlı bir konteyner imajının veya process'inin, host üzerinde çalışan `runc` binary'sinin kendisini `/proc/self/exe` üzerinden yeniden yazarak host bağlamında kod çalıştırmasına izin veren sınıftaki açıklardır. Bu sınıfın temel mantığı şudur: Konteyner içindeki bir process, host'ta çalışan güvenilir bir binary'nin dosya tanıtıcısına (file descriptor) eriştiğinde, o binary'nin üzerine yazarak bir sonraki çalışmasında host'ta kendi kodunu tetikleyebilir.

Burada dürüst olmak gerekir: Bu tür açıkların **tam CVE numaralarını, kesin etkilenen sürüm aralıklarını ve exploit'in birebir kod detayını** ezberden vermek yanlış bilgi riski taşır. Önemli olan **mekanizma**: Container runtime host'ta ayrıcalıklı çalışır ve konteyner ile host arasında paylaşılan herhangi bir kaynak (bir file descriptor, bir binary yolu, bir bellek bölgesi) potansiyel bir kaçış vektörüdür. Somut sürüm ve yama bilgisi için her zaman resmi güvenlik danışma metinlerine (Docker, runc, kernel dağıtımınızın güvenlik bültenleri) başvurulmalıdır.

**Bu kategoriye karşı savunma tek ve nettir: Yama yönetimi.** Kernel, Docker Engine, containerd ve runc güncel tutulmalıdır. Kaçış açıklarının önemli bir kısmı yayınlandıktan sonra yamalanır; güncelliğini yitirmiş bir host, bilinen ve halka açık exploit'lere karşı savunmasız kalır. Otomatik güvenlik güncellemeleri ve düzenli imaj yeniden inşası (rebuild), bu riski büyük ölçüde azaltır.

## Yaygın Hatalar

Sahada tekrar tekrar görülen, kaçışa zemin hazırlayan hatalar şunlardır:

**"Çalışması için privileged yaptım."** En sık ve en yıkıcı hata. Bir uygulama bir izin hatası verdiğinde, sorunun kökünü (hangi tek yetenek veya aygıt gerekiyor) araştırmak yerine `--privileged` eklenir. Bu, kilidi açmak yerine kapıyı menteşesinden söküp atmaktır.

**Konteyner içinde root olarak çalışmak.** Çoğu imaj varsayılan olarak process'i UID 0 ile çalıştırır. Bir uygulama güvenliği açığı (örneğin bir RCE) ele geçirildiğinde, saldırgan konteyner içinde root olur ve bu, kaçış zincirinin ilk halkasını hediye eder. Uygulamanın root olmaya ihtiyacı yoktur.

**`docker.sock`'u "pratik olsun diye" mount etmek.** Yönetim veya CI araçları için socket paylaşmak, farkında olmadan host root'u dağıtmaktır.

**Host namespace'lerini paylaşmak.** `--pid=host`, `--net=host`, `--ipc=host` gibi bayraklar izolasyonun ilgili katmanını tamamen kaldırır. Örneğin `--pid=host`, konteynerin host'un tüm process'lerini görmesini ve (uygun yeteneklerle) onlara müdahale etmesini sağlar.

**İmajlara körü körüne güvenmek.** Bilinmeyen kaynaklardan çekilen imajlar kötü amaçlı olabilir veya bilinen açıkları olan kütüphaneler içerebilir. İmaj taraması yapılmadan production'a alınması yaygın bir zafiyettir.

**Secret'ları imaj katmanlarına veya ortam değişkenlerine gömmek.** Bir kaçış gerçekleşmese bile, imaj katmanlarında kalan API anahtarları veya parolalar yanal harekete zemin hazırlar.

## En İyi Pratikler: Savunma Sıkılaştırma

Sağlam bir konteyner güvenliği, tek bir ayara değil, birbirini destekleyen katmanlara (defense in depth) dayanır. Aşağıdaki pratikler öncelik sırasına yakın biçimde verilmiştir.

**En az ayrıcalık ilkesini uygulayın.** `--cap-drop=ALL` ile başlayın, sadece gerekeni ekleyin. `--privileged` kullanmayın. Aygıt gerekiyorsa `--device` ile tek tek verin.

**Root olmayan kullanıcıyla çalışın.** Dockerfile içinde bir kullanıcı oluşturup `USER` direktifiyle ona geçin. Ayrıca `--user` bayrağı veya orchestration seviyesinde bir güvenlik bağlamı ile UID 0'ı yasaklayın. Bu, uygulama ele geçirilse bile saldırganın elini kolunu bağlar.

**Rootless Docker'ı değerlendirin.** Daemon'ı root yerine sıradan bir kullanıcı olarak çalıştırmak, bir kaçış durumunda saldırganın elde edeceği yetkiyi host root'undan sıradan kullanıcıya indirir. Bu, etki alanını kökten daraltan mimari bir savunmadır.

**Dosya sistemini salt okunur yapın.** `--read-only` bayrağı konteynerin kök dosya sistemine yazmasını engeller; yazması gereken dizinler için ise geçici `tmpfs` mount'ları tanımlanır. Yazamayan bir saldırgan kalıcılık kazanmakta ve araçlarını yerleştirmekte zorlanır.

**`no-new-privileges` bayrağını açın.** `--security-opt=no-new-privileges` ile, konteyner içindeki hiçbir process'in SUID binary'ler yoluyla yeni ayrıcalık kazanamamasını garanti edersiniz. Bu, birçok ayrıcalık yükseltme tekniğini doğrudan kesen basit ama güçlü bir ayardır.

**Seccomp ve MAC profillerini koruyun ve güçlendirin.** Docker'ın varsayılan seccomp profili tehlikeli syscall'ları zaten kısıtlar; bunu `--security-opt seccomp=unconfined` ile **kapatmayın.** Mümkünse uygulamanıza özel, daha da dar bir seccomp profili yazın. AppArmor veya SELinux profillerini production'da aktif tutun.

**User namespace remapping'i etkinleştirin.** Daemon seviyesinde user namespace remap yapılandırıldığında, konteyner içindeki root host'ta yetkisiz bir kullanıcıya eşlenir. Böylece bir dosya sistemi kaçışı bile host'ta root yetkisi vermez.

**Host namespace'lerini paylaşmayın.** `--pid=host`, `--net=host`, `--ipc=host` bayraklarından kaçının. Gerçekten gerekliyse, bu konteynere host'a yakın bir güven seviyesi atfedin ve ekstra izleyin.

**İmaj hijyeni uygulayın.** Yalnızca güvenilir kayıt defterlerinden (registry) ve mümkünse imza doğrulamasıyla imaj çekin. İmajları Trivy, Grype veya Clair gibi araçlarla açıklar için tarayın. Minimal temel imajlar (distroless veya Alpine) kullanarak saldırı yüzeyini küçültün; içinde `bash`, paket yöneticisi veya derleyici olmayan bir imaj, kaçış sonrası saldırgana çok daha az araç sunar.

**Kaynak sınırları koyun.** Bellek ve CPU sınırlarıyla (`--memory`, `--cpus`) hem DoS'u hem de bazı cgroups kötüye kullanım senaryolarını sınırlarsınız.

**Yama disiplinini sürdürün.** Kernel, Docker Engine, containerd ve runc'u güncel tutun. Kaçış açıklarının büyük kısmı yamalanmıştır; savunmasız kalmak yalnızca güncelleme yapmamakla olur.

**İzleme ve tespit ekleyin.** Falco gibi runtime güvenlik araçları, bir konteyner içinden beklenmedik mount işlemleri, `docker.sock`'a erişim, host dosya sistemine yazma veya beklenmedik process spawn gibi kaçış belirtisi davranışları yakalar. Önleme başarısız olursa, tespit son savunma hattınızdır.

## Sonuç

Konteyner kaçışının kalbindeki gerçek, en başta söylediğimiz cümledir: Konteyner, host kernel'ini paylaşan bir process'tir ve izolasyonu kernel'in tuttuğu kurallardan ibarettir. Kaçış tekniklerinin ezici çoğunluğu egzotik kernel exploit'leri değil, açık bırakılmış kapılardır: gereksiz yere verilen `--privileged`, konteynere sızdırılan `docker.sock`, elle eklenen `CAP_SYS_ADMIN` ve paylaşılan host namespace'leri. Bunların hepsinin ortak paydası, izolasyon katmanlarından birinin bilinçli olarak gevşetilmesidir.

Savunmanın felsefesi bu yüzden nettir: En az ayrıcalık, katmanlı savunma ve güncel yamalar. Konteyneri "içinde ele geçirileceği varsayımıyla" tasarlayın; öyle ki bir saldırgan uygulamayı ele geçirse bile ne root olabilsin, ne yazabilsin, ne host'u görebilsin, ne de yeni ayrıcalık kazanabilsin. Her katman aşıldığında bir sonraki katmanın onu durdurması gerektiği fikri, sağlam konteyner güvenliğinin özüdür.
