# Sistem Sıkılaştırma (Hardening)

## Tanım

Sistem sıkılaştırma (hardening), bir işletim sistemini, uygulamayı ya da altyapı bileşenini "kutudan çıktığı" varsayılan halinden alıp, saldırı yüzeyini (attack surface) mümkün olan en küçük seviyeye indirecek şekilde yeniden yapılandırma sürecidir. Amaç, sistemin işini görmesi için gereken minimum yetenek dışındaki her şeyi kapatmak, kısıtlamak veya izlenebilir hale getirmektir.

Buradaki anahtar kavram "attack surface" yani saldırı yüzeyidir. Bir sistemin açık her portu, çalışan her servisi, kurulu her paketi, tanımlı her kullanıcı hesabı ve her yazma izni verilmiş dizin, bir saldırgan için potansiyel bir giriş ya da ayrıcalık yükseltme (privilege escalation) noktasıdır. Hardening, bu yüzeyi bilinçli olarak daraltma disiplinidir.

Varsayılan yapılandırmaların neredeyse hiçbiri güvenlik için optimize edilmemiştir; kolay kurulum ve geniş uyumluluk için optimize edilmiştir. Bir işletim sistemi üreticisi, ürününün en fazla senaryoda "çalışmasını" ister, bu yüzden pek çok servis, protokol ve özellik açık gelir. Sıkılaştırma tam da bu varsayılan cömertliği geri almaktır.

## Kök Neden / Çalışma Mantığı: Neden Hardening'e İhtiyaç Var?

Sıkılaştırmanın neden gerekli olduğunu anlamak için saldırganın ekonomisini anlamak gerekir. Bir saldırgan sisteme genellikle tek bir "sihirli" zafiyetle girmez; bir zafiyet zinciri (exploit chain) kurar. Tipik zincir şöyle işler: önce bir giriş noktası (bir açık servis, phishing ile çalınan bir kimlik bilgisi, savunmasız bir web uygulaması), ardından yerel keşif (enumeration), sonra ayrıcalık yükseltme, ardından kalıcılık (persistence) ve yanal hareket (lateral movement).

Hardening bu zincirin her halkasını hedef alır. Mantık şudur: Tek bir kontrol saldırıyı durduramayabilir, ama zincirin yeterince halkasını kırarsanız saldırı ekonomik olarak sürdürülemez hale gelir veya tespit edilecek kadar gürültü çıkarır. Bu yüzden hardening, tek bir "sihirli ayar" değil, katmanlı savunmanın (defense in depth) sistem seviyesindeki uygulamasıdır.

Kök nedeni şu üç kuvvet oluşturur:

**Varsayılan güven fazlalığı.** Sistemler, yönetilebilirlik uğruna bileşenlerine geniş güven verir. Örneğin bir servis çoğu zaman `root`/`SYSTEM` yetkisiyle çalışır çünkü bu, geliştiricinin izin sorunlarıyla uğraşmasını engeller. Bu güven, o servis ele geçirildiğinde doğrudan saldırgana devrolur.

**Bileşen fazlalığı.** Kurulu ama kullanılmayan her şey bakımsız kalır; güncellenmez, izlenmez, ama hâlâ sömürülebilir. Kullanmadığınız bir bileşen, sizin için değeri sıfır, saldırgan için değeri tam olan bir varlıktır.

**Yanlış varsayılan güven sınırları.** Sistemler çoğu zaman "iç ağ = güvenli" gibi eski varsayımlarla tasarlanmıştır. Bir saldırgan çevre savunmasını (perimeter) bir kez geçtiğinde, iç tarafın gevşekliği ona bedava bir oyun alanı sunar.

## En Az Yetki (Least Privilege) Prensibi

### Tanım ve mantık

En az yetki prensibi (Principle of Least Privilege, PoLP), her özne (kullanıcı, servis, süreç, token) yalnızca görevini yerine getirmek için kesinlikle gereken minimum yetkiye sahip olmalı der. Ne bir fazlası, ne de bir eksiği.

Bunun kök nedeni "blast radius" yani patlama yarıçapı kavramıdır. Bir hesap veya süreç ele geçirildiğinde, saldırganın eline geçen yetki, o hesabın sahip olduğu yetkidir. Eğer bir web sunucusu süreci `root` olarak çalışıyorsa ve o süreçte bir remote code execution (RCE) zafiyeti sömürülürse, saldırgan anında tüm makineye sahip olur. Ama aynı süreç, sadece belirli portlara bağlanabilen, sadece kendi dizinine yazabilen, ayrıcalıksız bir servis hesabıyla çalışıyorsa, aynı RCE saldırgana çok daha az verir ve saldırgan bir sonraki ayrıcalık yükseltme adımına mecbur kalır ki bu da yeni bir gürültü ve yeni bir başarısızlık ihtimalidir.

### Somut örnek

Bir veritabanına bağlanan bir web uygulaması düşünün. Yaygın (ve yanlış) uygulama, uygulamanın veritabanına yönetici (admin) hesabıyla bağlanmasıdır çünkü "her şeyi yapabilsin" istenir. Doğru uygulama şöyledir: uygulama yalnızca gerçekten kullandığı tablolar üzerinde `SELECT`, `INSERT`, `UPDATE` yetkisine sahip olur; `DROP TABLE`, şema değiştirme veya diğer veritabanlarına erişim yetkisi olmaz. Böylece bir SQL injection zafiyeti bile veritabanını tamamen silemez ya da başka müşterilerin verisine dokunamaz; hasar, uygulamanın zaten eriştiği veriyle sınırlı kalır.

### İstismar mantığı (saldırgan tarafı)

Saldırgan, aşırı yetkiyi arar. Bir sisteme sızdıktan sonra ilk yaptığı şeylerden biri "hangi yetkilerim var, hangi hesaplar aşırı yetkili" sorusunu yanıtlamaktır. Windows'ta token'ların ayrıcalıklarını (`SeImpersonatePrivilege`, `SeDebugPrivilege` gibi güçlü ayrıcalıklar), servis hesaplarının haklarını, zayıf yapılandırılmış zamanlanmış görevleri; Linux'ta `sudo` kurallarındaki gevşeklikleri, SUID/SGID bit'i olan binary'leri, gereksiz yere geniş dosya izinlerini ve `root` olarak çalışan servisleri arar. Bunların her biri, düşük yetkiden yüksek yetkiye geçiş için birer basamaktır. Aşırı yetki, saldırganın en sevdiği hediyedir.

### Savunma tarafı

Savunmada least privilege şu şekilde uygulanır: kullanıcılar günlük işlerini yönetici olmayan hesaplarla yapar; yönetim işleri ayrı, yükseltilmiş ve loglanmış hesaplarla yürütülür (Windows'ta ayrı admin hesabı, Linux'ta `sudo` ile denetlenen geçiş). Servisler ayrıcalıksız, kendine özel hesaplarla çalıştırılır. Dosya sistemi izinleri "gerekeni ver" mantığıyla sıkılaştırılır. Ağ seviyesinde de aynı ilke geçerlidir: bir sunucu yalnızca konuşması gereken hedeflere ve portlara ulaşabilmelidir (mikro segmentasyon). Bulut ortamlarında ise IAM rolleri wildcard izinler yerine kaynak ve eylem bazında daraltılır.

## Servis Kapatma ve Saldırı Yüzeyi Azaltma

### Mantık

Bir servis çalışıyorsa, bir dinleyici (listener) vardır; bir dinleyici varsa, ona konuşulabilir; konuşulabiliyorsa, sömürülebilir. Bu basit zincir, servis kapatmanın neden en yüksek getirili hardening adımlarından biri olduğunu açıklar. Kapalı olan bir servis sömürülemez; var olmayan zafiyetin patch'ini uygulamak gerekmez.

Saldırı yüzeyini azaltmanın somut hedefleri şunlardır: gereksiz ağ servislerini kapatmak, gereksiz portları kapatmak, kullanılmayan protokolleri (örneğin eski ve zayıf SMB sürümleri, gereksiz uzaktan yönetim protokolleri) devre dışı bırakmak ve kurulu ama kullanılmayan paketleri kaldırmak.

### Somut örnek ve çalışma mantığı

Bir web sunucusu düşünün. Bu makinede gerçekte yalnızca HTTPS (443) portunun dışarıya açık olması gerekir. Ama varsayılan kurulumda üzerinde bir dosya paylaşım servisi, bir yazıcı servisi, eski bir uzak masaüstü protokolü ya da bir yönetim arayüzü de dinliyor olabilir. Bunların her biri bir giriş kapısıdır. Saldırgan, hedefi bulduğunda ilk iş port taraması (port scan) yapar ve açık her portu bir fırsat olarak değerlendirir. Örneğin dışarıya açık kalmış bir uzaktan yönetim servisi, zayıf parola veya bilinen bir kimlik doğrulama zafiyeti ile ilk erişimi sağlamanın klasik yoludur.

Burada önemli bir kavram, protokolün kendisinin güvenliğidir. Bazı eski protokoller, tasarımları gereği kimlik bilgilerini yeterince korumaz veya downgrade saldırılarına açıktır. Bunları tamamen kapatmak, tek tek zafiyet yamamaktan daha köklü bir çözümdür çünkü zafiyet sınıfını ortadan kaldırır.

### İstismar / savunma dengesi

Saldırgan tarafında keşif (reconnaissance) her şeyin başıdır. Az servis, az bilgi, az fırsat demektir; sıkılaştırılmış bir sistem saldırgana keşif aşamasında çok az geri döner. Savunma tarafında ilke şudur: "Varsayılan olarak kapalı" (default deny). Yani bir servisi açık bırakmak için gerekçe gösterilir, kapatmak için değil. Her açık port ve servis, "buna neden ihtiyacımız var?" sorusuna net bir cevabı olmalıdır. Cevap yoksa kapatılır.

Servis kapatırken kritik bir mantık, bağımlılıkları anlamaktır. Bazı servisler başka servisler tarafından dolaylı kullanılır. Bu yüzden sıkılaştırma, körlemesine kapatma değil; önce envanter çıkarma, sonra gerekçe sorgulama, sonra kontrollü kapatma ve nihayet gözlemleyerek doğrulama adımlarını izler.

## CIS Benchmark: Sıkılaştırmanın Endüstri Referansı

### Nedir ve neden var

CIS Benchmark, Center for Internet Security tarafından yayımlanan, belirli işletim sistemleri, uygulamalar ve bulut platformları için detaylı, tek tek doğrulanabilir sıkılaştırma önerileri bütünüdür. Temel değeri, hardening'i "bir uzmanın sezgisi" olmaktan çıkarıp, üzerinde uzlaşılmış (consensus-based) ve denetlenebilir bir kontrol listesine dönüştürmesidir.

CIS Benchmark'ın en önemli kavramsal katkılarından biri profil ayrımıdır. Genellikle iki seviye tanımlanır: bir birinci seviye, sistemin işlevselliğini büyük ölçüde bozmadan uygulanabilecek makul, temel sıkılaştırma önerilerini içerir; daha yüksek bir ikinci seviye ise savunma derinliğini artıran ama işlevselliği daha çok kısıtlayabilecek, dolayısıyla dikkatli test gerektiren önerileri içerir. Bu ayrım önemlidir çünkü her ortam için en agresif ayar doğru değildir; hardening her zaman "güvenlik ile işlevsellik" arasında bilinçli bir denge kurma işidir.

### Çalışma mantığı ve doğru kullanımı

CIS Benchmark'ın her önerisi tipik olarak şu bileşenleri içerir: önerinin gerekçesi (rationale), sömürülme senaryosu, olası olumsuz etkisi (impact), nasıl denetleneceği (audit) ve nasıl uygulanacağı (remediation). Bu yapı, bir kontrolü körü körüne uygulamak yerine "bu neden var, kapattığımda ne bozulur" diye düşünmeyi mümkün kılar.

Buradaki en kritik uzman tavsiyesi şudur: CIS Benchmark'ı bir üretim ortamına test etmeden, olduğu gibi toptan uygulamak tehlikelidir. Bazı öneriler, ortamınızdaki meşru bir iş akışını kırabilir. Doğru yöntem, benchmark'ı bir hedef durum olarak almak, önce izole bir test ortamında uygulamak, etkiyi ölçmek, gerekçesiz kalan istisnaları belgelemek ve ancak sonra kademeli yaymaktır.

CIS ayrıca uyumluluğu ölçmek için makine tarafından okunabilir kontrol tanımları sağlar ve otomatik değerlendirme araçlarıyla bir sistemin benchmark'a ne kadar uyduğu skorlanabilir. Bu, hardening'i tek seferlik bir olay olmaktan çıkarıp sürekli ölçülen bir duruma (posture) dönüştürür ki asıl değer buradadır: sistemler zamanla "sürüklenir" (configuration drift), bugün sıkılaştırılan sistem yarın bir değişiklikle gevşer.

### CIS ile diğer çerçevelerin ilişkisi

CIS Benchmark, "bir sistemi nasıl sıkılaştırırım" sorusuna teknik ve somut cevap verir. Bunu daha üst seviye çerçevelerle (örneğin geniş güvenlik kontrol kataloglarıyla) karıştırmamak gerekir; o çerçeveler "hangi kontrollere sahip olmalıyım" sorusuna organizasyonel düzeyde cevap verirken, CIS Benchmark bu kontrollerin belirli bir platformdaki uygulama detayını verir. İkisi birbirini tamamlar: biri neyi, diğeri nasılı söyler.

## AppLocker ve Uygulama Kontrolü (Application Allowlisting)

### Tanım ve kök neden

AppLocker, Windows üzerinde hangi uygulamaların ve script'lerin çalıştırılabileceğini kural bazında kontrol eden bir uygulama kontrol mekanizmasıdır. Temel felsefesi, geleneksel antivirüs mantığının tam tersidir. Antivirüs "kötü bilinenleri engelle" (denylist) mantığıyla çalışır; AppLocker ise "iyi bilinenlere izin ver, gerisini engelle" (allowlist) mantığıyla çalışabilir.

Bu ayrım kök nedeni açısından kritiktir. Denylist yaklaşımı, bilinmeyen ve yeni (zero-day) kötü amaçlı yazılımlara karşı yapısal olarak geride kalır çünkü henüz imzası bilinmeyeni tanıyamaz. Allowlist yaklaşımı ise problemi tersine çevirir: kötü olanı tanımaya çalışmak yerine iyi olanı tanımlar; tanımlı iyi listesinde olmayan her şey, bilinmese bile çalıştırılamaz. Böylece bir saldırgan meşru bir yola kötü amaçlı bir çalıştırılabilir bıraksa dahi, o dosya izinli değilse çalışmaz.

### Çalışma mantığı

AppLocker kuralları genellikle üç tür ölçüte dayanır. Bunlardan en zayıfı yol (path) tabanlı kurallardır: belirli bir dizindeki şeylerin çalışmasına izin verilir. En güçlüsü ise yayıncı (publisher) tabanlı kurallardır: dijital olarak imzalanmış, belirli bir yazılım yayıncısına ait dosyalara izin verilir; bu, dosya güncellense bile kuralın geçerli kalmasını sağlar. Bir ara seçenek ise dosya hash'ine dayalı kurallardır: tam olarak belirli bir dosya içeriğine izin verilir, dosya bir bit bile değişirse kural artık eşleşmez.

### İstismar mantığı: neden yol tabanlı kurallar tehlikeli

Burada uzman seviyesinde çok önemli bir nokta var. Uygulama kontrolünün en yaygın atlatma (bypass) yöntemi, kullanıcının yazabildiği ama izin verilmiş bir yolu suistimal etmektir. Eğer bir kural "şu sistem dizinindeki her şey çalışabilir" diyorsa ve o dizinin altında normal kullanıcının yazabildiği bir alt klasör varsa, saldırgan kötü amaçlı dosyasını oraya koyup izin kuralının şemsiyesi altında çalıştırabilir. Bu yüzden yol tabanlı izinlerde altın kural şudur: izin verilen bir yola sıradan kullanıcı yazamamalıdır; aksi halde izin, saldırgana da açıktır.

İkinci büyük bypass sınıfı "living off the land" yani sistemde zaten var olan ve imzalı, dolayısıyla çoğu zaman izinli olan meşru araçların kötüye kullanılmasıdır. Bir saldırgan, kendi binary'sini çalıştırmak yerine, sistemde hâlihazırda bulunan ve script/kod çalıştırabilen meşru bir bileşeni aracı olarak kullanabilir. Bu yüzden ciddi bir uygulama kontrolü, yalnızca çalıştırılabilir dosyaları değil, script motorlarını ve kötüye kullanılabilen yardımcı sistem binary'lerini de kapsam altına almalı; bilinen kötüye kullanım araçlarını açıkça engellemelidir.

### Savunma tarafı ve doğru konumlandırma

AppLocker'ı doğru kullanmanın yolu şu aşamalardan geçer. Önce bir denetim (audit) modu vardır: kurallar uygulanmaz ama neyin engelleneceği loglanır. Bu aşama hayati önemdedir çünkü doğrudan zorlama moduna geçmek meşru iş uygulamalarını bir anda kırabilir. Audit modunda toplanan veriyle meşru uygulama envanteri çıkarılır, kurallar buna göre şekillendirilir, ve ancak yeterince olgunlaştıktan sonra zorlama (enforce) moduna geçilir.

Ayrıca AppLocker'ın bir savunma katmanı olduğunu, tek başına aşılamaz bir duvar olmadığını unutmamak gerekir. Değeri, saldırganın işini zorlaştırması, onu bilinen ve tespit edilebilir tekniklere zorlaması ve gürültü çıkarmaya mecbur bırakmasıdır. Bu yüzden uygulama kontrolü, güçlü loglama ve tespit (detection) ile birlikte konumlandırıldığında en yüksek değeri verir. Daha yeni ve güçlü Windows uygulama kontrol çözümleri de aynı allowlist felsefesini daha güçlü politika ve çekirdek seviyesi zorlama ile taşır; kavram aynıdır, uygulama daha sağlamdır.

## Yaygın Hatalar

**Varsayılanı güvenli sanmak.** En temel hata, "kurdum, çalışıyor, demek ki güvenli" varsayımıdır. Varsayılan yapılandırma neredeyse hiçbir zaman güvenli değildir; kullanışlı olması için geniş tutulmuştur.

**Toptan ve test etmeden benchmark uygulamak.** CIS gibi bir referansı üretime doğrudan, izole test olmadan uygulamak, güvenliği artırmak isterken üretimi durdurabilir. Hardening bir mühendislik işidir; her ayar etkisi ölçülerek uygulanır.

**Least privilege'i "çalışması için" kolayca çiğnemek.** Bir izin sorunuyla karşılaşınca hesaba yönetici yetkisi verip geçmek en yaygın ayrıcalık şişmesi (privilege creep) kaynağıdır. Doğru olan, tam olarak eksik olan yetkiyi teşhis edip yalnızca onu vermektir.

**Yol tabanlı allowlist kurallarında yazılabilir dizin bırakmak.** Uygulama kontrolünün en sık atlatıldığı hata budur; izinli bir yola kullanıcının yazabilmesi, tüm kontrolü işlevsiz bırakır.

**Konfigürasyon sürüklenmesini (drift) izlememek.** Bir sistemi bir kez sıkılaştırıp unutmak. Zamanla yapılan değişiklikler, geçici açılan servisler, "sadece bugünlük" verilen yetkiler birikir ve sistem sessizce gevşer. Hardening süreklidir, olay değildir.

**Loglama ve tespit olmadan sıkılaştırmak.** Sıkılaştırma önlemedir; ama hiçbir önlem kusursuz değildir. Loglama ve tespit olmadan yapılan hardening, bir saldırı gerçekleştiğinde kör kalır. İkisi birlikte tasarlanmalıdır.

**Kullanılmayanı kaldırmak yerine sadece "kapatmak".** Bir bileşeni devre dışı bırakmak, çoğu zaman onu kaldırmaktan zayıftır; devre dışı bir şey yeniden etkinleştirilebilir. Gerçekten gerekmiyorsa kaldırmak, kapatmaktan üstündür.

## En İyi Pratikler

**Envanterle başla.** Neyi koruduğunu ve üzerinde ne çalıştığını bilmeden sıkılaştıramazsın. Açık portların, çalışan servislerin, kurulu paketlerin, kullanıcı ve servis hesaplarının, yükseltilmiş yetkilerin envanterini çıkar. Görünmeyen sıkılaştırılamaz.

**Default deny'i temel ilke yap.** Ağda, uygulama kontrolünde, izinlerde ve bulut politikalarında varsayılan "reddet" olmalı; istisnalar gerekçeyle açılmalıdır. Bu, saldırı yüzeyini yapısal olarak küçük tutar.

**Kabul edilmiş bir referansa (CIS Benchmark) dayan ama körü körüne değil.** Referansı hedef durum olarak al; her kontrolün gerekçesini anla, ortamına uyarla, test et, istisnaları belgele. Belgelenmiş bilinçli bir sapma, belgelenmemiş bir uyumdan iyidir.

**Least privilege'i her katmanda uygula.** Kullanıcı hesapları, servis hesapları, dosya izinleri, ağ erişimi ve bulut IAM rolleri; hepsinde aynı ilke geçerlidir. Ayrıcalıklı erişimi ayır, yükselt-ve-logla modeliyle yönet, düzenli olarak gözden geçir.

**Yönetimsel işlemleri ayrı, izlenen bir yolda tut.** Günlük iş ile yönetim işini aynı hesapta karıştırma. Ayrıcalıklı erişim yönetimi, saldırganın en çok istediği "anahtarlar"ı en iyi koruduğun yerdir.

**Uygulama kontrolünü audit modda başlat, güçlü kural türlerini tercih et.** AppLocker ya da eşdeğerini önce gözlemle, envanter çıkar, sonra zorla. Yol tabanlı yerine yayıncı tabanlı kuralları tercih et; script motorlarını ve kötüye kullanılabilir meşru araçları da kapsa.

**Sıkılaştırmayı sürekli ölçülen bir durum haline getir.** Otomatik değerlendirme ile sistemlerin referansa uyum skorunu düzenli ölç, sürüklenmeyi yakala. Mümkünse yapılandırmayı kod olarak (configuration as code) yönet ki sistemler tutarlı ve tekrarlanabilir şekilde kurulsun.

**Sıkılaştırmayı tespit ve müdahale ile birlikte tasarla.** Önleme (hardening) ve tespit (detection) birbirini tamamlar. Sıkılaştırma saldırganı bilinen, gürültülü, tespit edilebilir tekniklere zorlar; loglama ve izleme bu gürültüyü yakalar. Katmanlı düşün: hiçbir tek kontrol yeterli değildir, ama iyi seçilmiş kontroller birlikte saldırıyı ekonomik olarak sürdürülemez kılar.

**Değişiklik yönetimi ve geri alma planıyla ilerle.** Her sıkılaştırma değişikliğini kontrollü uygula, etkisini ölç, ve bir şeyi kırdığında hızla geri alabileceğin bir plana sahip ol. Güvenlik uğruna erişilebilirliği yanlışlıkla yok etmek, saldırganın işini görmektir.

## Kapanış Notu

Sistem sıkılaştırma, tek seferlik bir ayar listesi değil, süregelen bir mühendislik disiplinidir. Özü şudur: saldırgana verilen her fazladan yetki, açık bırakılan her gereksiz servis ve gevşetilen her varsayılan, saldırı zincirinin bir halkasını saldırgana hediye eder. Least privilege ile yetkiyi daraltır, servis kapatma ile yüzeyi küçültür, CIS Benchmark ile bunu ölçülebilir ve tutarlı kılar, AppLocker gibi uygulama kontrolüyle çalıştırılabileni sınırlarsın. Bunların hiçbiri tek başına yeterli değildir; birlikte, katmanlı ve sürekli ölçülen bir savunma duruşu oluşturduklarında değer kazanır. Hardening'in nihai amacı, mükemmel güvenlik değil (ki bu mümkün değildir), saldırının maliyetini savunulan varlığın değerinin üzerine çıkarmak ve saldırgan hareket ettiğinde bunu görebilmektir.
