# Linux Yetki Yükseltme (Privilege Escalation)

## Tanım

Yetki yükseltme (privilege escalation), bir saldırganın sınırlı yetkili bir hesapla (örneğin `www-data`, `nobody` veya sıradan bir kullanıcı) elde ettiği erişimi, sistem üzerinde daha yüksek ayrıcalıklara sahip bir kimliğe (çoğunlukla `root`) dönüştürme sürecidir. Sızma testlerinde bu aşama genellikle "initial foothold" sonrası gelir: bir web açığı ya da sızdırılmış bir parola ile sisteme düşük yetkiyle girersiniz, ardından hedefin tam kontrolünü ele geçirmek için yetki yükseltirsiniz.

Kavramsal olarak iki ana tür vardır. **Yatay yükseltme (horizontal)**, aynı yetki seviyesindeki başka bir kullanıcının kimliğine geçmektir; örneğin `alice` hesabından `bob` hesabına. **Dikey yükseltme (vertical)** ise yetki seviyesini artırmaktır; sıradan kullanıcıdan `root`'a çıkmak buna örnektir. Savunma tarafında amaç, bu geçişlerin mümkün olduğu yolları ("attack surface") daraltmak ve gözlemlenebilir hale getirmektir.

## Kök Neden: Neden Yetki Yükseltme Mümkün Olur

Linux'ta yetki modeli tarihsel olarak basit bir ikili ayrıma dayanır: `root` (UID 0) her şeyi yapabilir, geri kalan herkes çekirdeğin (kernel) ve dosya izinlerinin çizdiği sınırlar içinde hareket eder. Yetki yükseltme açıkları neredeyse her zaman şu temel gerilimden doğar: **bir işlemin yüksek yetkiyle çalışması gerekir, ama o işlemin kontrolü kısmen düşük yetkili bir kullanıcının eline geçer.**

Bu gerilim birkaç yerde ortaya çıkar:

- Bir program `root` yetkisiyle çalışması gerektiği için `SUID` biti ile işaretlenmiştir, ama tasarımı gereği kullanıcıya komut çalıştırma ya da dosya yazma imkânı verir.
- Bir yönetici, bir kullanıcıya belirli bir komutu `sudo` ile çalıştırma izni verir, ama o komut "kaçış" (breakout) imkânı sunar.
- Çekirdeğin kendisinde bir bellek güvenliği hatası (memory safety bug) vardır ve düşük yetkili kod bunu tetikleyerek çekirdek bağlamında (kernel context) kod çalıştırır.
- Yüksek yetkiyle çalışan bir zamanlanmış görev (cron job), düşük yetkili kullanıcının değiştirebildiği bir betiği ya da dosyayı okur.

Ortak payda şudur: **güven sınırı (trust boundary) yanlış yerde çizilmiştir.** Saldırgan bu yanlış çizilmiş sınırı bulup istismar eder. Savunmacı ise sınırı doğru yere çekmeye, yani en az yetki ilkesini (principle of least privilege) uygulamaya çalışır.

## SUID İkilileri ve GTFOBins

### Çalışma Mantığı

Normalde bir programı çalıştırdığınızda, işlem sizin kullanıcı kimliğinizle (effective UID) çalışır. Ancak dosya izinlerinde `SUID` (Set User ID) biti ayarlanmışsa, program dosya **sahibinin** kimliğiyle çalışır. Örneğin `passwd` komutu `root`'a aittir ve SUID işaretlidir; çünkü parolanızı değiştirmek için `/etc/shadow` dosyasına yazması gerekir ve bu dosyaya yalnızca `root` yazabilir. Siz `passwd`'yi çalıştırdığınızda işlem geçici olarak `root` yetkisi kazanır.

Bu tasarımın kök nedeni pratiktir: bazı işlemler yüksek yetki gerektirir ama her kullanıcının yapabilmesi gerekir. SUID, bu ihtiyacı `sudo` gibi bir aracıya gerek kalmadan çözer. Sorun şudur: eğer SUID işaretli bir program, kullanıcıya keyfi komut çalıştırma, keyfi dosya okuma ya da yazma imkânı veriyorsa, o zaman kullanıcı bu yeteneği `root` bağlamında kullanabilir.

### GTFOBins Mantığı

GTFOBins, bu davranışı sistematikleştiren bir bilgi tabanıdır. Temel fikir: birçok standart Unix aracının, tasarım gereği, kabuk (shell) açma ya da dosyaya yazma gibi "yan yetenekleri" vardır. Bu araçlardan biri SUID ile işaretlenmişse, o yan yetenek `root` yetkisiyle tetiklenebilir.

Klasik örnek `find` komutudur. `find`, dosyaları ararken her eşleşme için bir komut çalıştırabilen bir seçeneğe sahiptir (`-exec`). Eğer `find` SUID işaretliyse, bir kabuk başlatan bir `-exec` ifadesiyle `root` kabuğu elde edersiniz. Aynı mantık `vim`, `less`, `awk`, `python`, `bash` gibi onlarca araç için geçerlidir. Örneğin `less` ya da `vim` gibi bir sayfalayıcı/düzenleyici, içinden kabuk komutu çalıştırma özelliği sunar; SUID ile bu kabuk `root` olur.

> Dürüstlük notu: her aracın kesin bayrak sözdizimini (örneğin `find`'in tam `-exec ... \;` biçimi ya da her sürümün desteklediği seçenekler) sürümden sürüme değişebildiği için, gerçek testte GTFOBins sitesindeki güncel karneleri (entries) referans almak, ezberden komut yazmaktan daha güvenlidir.

### Somut Keşif ve İstismar Mantığı

Saldırgan önce sistemdeki tüm SUID ikililerini listeler. Bunun mantığı, dosya sisteminde SUID biti (izin kümesinde özel bir bayrak) ayarlanmış dosyaları taramaktır. Elde edilen listeyi standart, zararsız SUID ikilileriyle (`passwd`, `sudo`, `mount` gibi beklenen olanlar) karşılaştırır. Listede beklenmedik bir araç varsa — özellikle GTFOBins'te "SUID" başlığı altında yer alan bir araç — bu güçlü bir yükseltme adayıdır.

İstismar mantığı her zaman aynıdır: SUID araç aracılığıyla, o aracın izin verdiği bir yan yetenekle (kabuk açma, dosya yazma, dosya okuma) `root` bağlamında bir işlem gerçekleştirmek. Kabuk açabiliyorsanız doğrudan `root` shell alırsınız; yalnızca dosya yazabiliyorsanız `/etc/passwd`'ye yeni bir ayrıcalıklı kullanıcı ekler ya da bir `root` cron dosyası yazarsınız; yalnızca okuyabiliyorsanız `/etc/shadow`'u okuyup parola hash'lerini kırmayı denersiniz.

### Savunma

SUID savunmasının özü, **SUID işaretli ikili sayısını en aza indirmek** ve her birini gerekçelendirmektir. Somut önlemler:

- Sistemdeki SUID ikililerini düzenli olarak envanterleyin ve bilinen bir temel (baseline) ile karşılaştırın; yeni bir SUID dosyası ortaya çıkması güçlü bir uyarı sinyalidir.
- Gerçekten SUID gerektirmeyen ikililerden bu biti kaldırın. Birçok dağıtım, geçmişte SUID olan araçları (örneğin bazı ağ araçları) artık `capabilities` ya da başka mekanizmalarla çözer.
- Kritik dosya sistemlerini `nosuid` seçeneğiyle bağlayın (mount); böylece o birim üzerindeki SUID bitleri yok sayılır. Bu, yazılabilir geçici dizinler (`/tmp`, `/dev/shm`) için özellikle önemlidir, çünkü saldırganın oraya kendi SUID ikilisini koymasını engeller.
- Dosya bütünlüğü izleme (file integrity monitoring) ile SUID bitindeki değişiklikleri gerçek zamanlı yakalayın.

## sudo Yapılandırma Hataları

### Çalışma Mantığı

`sudo`, belirli kullanıcıların belirli komutları başka bir kimlikle (varsayılan `root`) çalıştırmasına izin veren bir yetkilendirme aracıdır. Kuralları `/etc/sudoers` dosyasında tanımlanır. `sudo`'nun temel değeri, tam `root` erişimi vermeden, ince taneli (fine-grained) yetki devri sağlamasıdır — örneğin bir DevOps kullanıcısına yalnızca servisi yeniden başlatma izni vermek gibi.

Sorun, bu ince taneli iznin sıklıkla **düşünüldüğünden çok daha geniş** olmasından kaynaklanır. Kök neden yine güven sınırının yanlış çizilmesidir: yönetici "bu kullanıcı yalnızca X komutunu çalıştırabilir" diye düşünür, ama X komutu içinden başka komutlar çalıştırma, dosya yazma ya da kabuk açma imkânı sunuyorsa, kullanıcı fiilen `root` olur.

### İstismar Mantığı

Bir saldırgan ilk iş olarak kendisine tanınmış `sudo` izinlerini sorgular; bunun mantığı, mevcut kullanıcının hangi komutları hangi kimlikle çalıştırabileceğini `sudo`'nun kendisine listeletmektir. Çıktıda birkaç yaygın istismar deseni aranır:

- **GTFOBins uyumlu komutlar:** Eğer `sudo` ile `vim`, `less`, `awk`, `python`, `find` gibi bir araç çalıştırılabiliyorsa, o aracın kabuk açma yeteneğiyle doğrudan `root` shell alınır. Bu, SUID senaryosunun `sudo` karşılığıdır.
- **Wildcard ve argüman enjeksiyonu:** Bir kuralda joker karakter (wildcard) varsa, saldırgan beklenmedik argümanlar geçirerek komutun davranışını değiştirebilir.
- **`env_keep` ve `LD_PRELOAD`/`LD_LIBRARY_PATH` istismarı:** Eğer `sudoers` yapılandırması belirli ortam değişkenlerinin (environment variables) korunmasına izin veriyorsa, saldırgan bir paylaşımlı kütüphaneyi (shared library) önceden yükleterek (`LD_PRELOAD`) `root` bağlamında kendi kodunu çalıştırabilir. Bu yüzden modern `sudo`, ortam değişkenlerini varsayılan olarak temizler (`env_reset`).
- **`sudo` sürüm açıkları:** Zaman zaman `sudo`'nun kendisinde ciddi açıklar çıkmıştır (örneğin argüman/bellek işleme kaynaklı bir çeşit heap taşması sınıfı hatalar). Belirli bir CVE numarası ve etkilenen sürüm aralığını ezberden vermek yerine, hedefteki `sudo` sürümünü tespit edip bilinen açıklarla eşleştirmek doğru yöntemdir.

### Savunma

- `sudoers` kurallarında **asla joker karakterlere güvenmeyin**; komut yollarını tam ve mutlak (absolute path) belirtin.
- İçinden kabuk açabilen ya da keyfi dosya yazabilen araçlara `sudo` izni vermeyin. İzin vermeniz gerekiyorsa, o aracın "restricted" modu varsa onu kullanın.
- `env_reset` ve `secure_path` ayarlarını koruyun; bunları gevşetmek, tehlikeli ortam değişkeni istismarlarına kapı açar.
- `NOPASSWD` kullanımını mümkün olduğunca sınırlayın; parola istemi, bir saldırganın çalınmış oturumla sessizce yükselmesini zorlaştırır.
- `sudo`'yu güncel tutun. Yetki yükseltme açıklarının önemli bir bölümü, güncel olmayan `sudo` sürümlerinden kaynaklanır.

## Linux Capabilities

### Çalışma Mantığı

Geleneksel ikili yetki modeli (`root` her şeyi yapar) fazla kabadır. Bir programın yalnızca ağ portu açması gerekiyorsa, neden tam `root` yetkisi alsın? Linux `capabilities`, `root`'un bölünebilir yeteneklerini ayrı parçalara ayırarak bu sorunu çözer. Örneğin belli bir capability yalnızca ham ağ (raw socket) erişimi verir; başka biri dosya sahipliği kontrollerini atlamaya izin verir; bir diğeri başka bir kullanıcının kimliğine bürünmeye izin verir.

Bu, güvenlik açısından bir iyileştirmedir: tam `root` yerine, işleme yalnızca ihtiyaç duyduğu dilimi verirsiniz. Ancak yanlış atanan bir capability, tam `root` kadar tehlikeli olabilir. Kök neden yine aynıdır: bazı capability'ler o kadar güçlüdür ki, pratikte tam yetki yükseltmeye eşdeğerdir.

### İstismar Mantığı

Saldırgan, dosya sistemindeki ikililere atanmış capability'leri listeler. Kritik olan, hangi capability'nin pratikte tam `root`'a giden bir yol açtığını tanımaktır. Bazı capability sınıfları özellikle tehlikelidir:

- Bir programa keyfi dosyaların sahipliği/izin kontrollerini atlama yeteneği verilmişse, saldırgan hassas dosyaları (örneğin `/etc/shadow`) okuyabilir ya da değiştirebilir.
- Başka bir kullanıcının kimliğine bürünme (`setuid` benzeri) yeteneği verilmiş bir yorumlayıcı (örneğin bu yeteneğe sahip bir `python` ikilisi) varsa, saldırgan o yorumlayıcının içinden kendi kimliğini `root`'a (UID 0) çevirebilir. Bu, SUID `python` senaryosuna çok benzer ve doğrudan `root` shell'e götürür.

GTFOBins, SUID ve `sudo` karneleri gibi, "capabilities" karneleri de sunar; hangi aracın hangi capability ile nasıl istismar edildiğini gösterir.

### Savunma

- Capability atanmış ikilileri düzenli olarak envanterleyin; SUID envanteriyle aynı disiplinle ele alın.
- Bir işleme capability verirken en dar kapsamı seçin; asla "kolay olsun diye" geniş bir capability atamayın.
- Yorumlayıcılara (`python`, `perl`, `ruby` vb.) ve kabuk açabilen araçlara güçlü capability atamaktan kaçının; bunlar neredeyse her zaman tam `root`'a dönüşür.
- `nosuid` gibi, capability'leri de dosya sistemi seçenekleriyle sınırlayabileceğiniz durumları değerlendirin.

## Cron ve Zamanlanmış Görevler

### Çalışma Mantığı

`cron`, komutları zamanlanmış aralıklarla çalıştıran bir arka plan servisidir. Sistem cron görevleri genellikle `root` yetkisiyle çalışır — yedekleme, günlük döndürme (log rotation), temizlik betikleri gibi. İşte tehlike buradadır: eğer `root` olarak çalışan bir cron görevi, düşük yetkili bir kullanıcının kontrol edebildiği bir kaynağa dokunuyorsa, o kullanıcı `root` bağlamında kod çalıştırabilir.

### İstismar Mantığı

Birkaç klasik desen vardır:

- **Yazılabilir betik:** Cron `root` olarak bir betiği çalıştırıyor ama betik dosyası düşük yetkili kullanıcı tarafından yazılabilir durumdaysa, saldırgan betiğin içine kendi komutunu ekler ve bir sonraki çalışmada `root` olarak çalışır.
- **Yazılabilir dizin / dosya yerleştirme:** Betiğin kendisi yazılamaz ama bulunduğu dizin yazılabilirse, saldırgan dosyayı silip yerine kendi sürümünü koyabilir.
- **`PATH` istismarı:** Cron betiği bir komutu mutlak yol yerine çıplak adıyla çağırıyorsa (örneğin `tar` demek, `/bin/tar` dememek) ve `cron`'un `PATH`'inde saldırganın yazabildiği bir dizin önce geliyorsa, saldırgan aynı adda sahte bir çalıştırılabilir yerleştirerek onu `root` olarak çalıştırır.
- **Wildcard enjeksiyonu:** Bir cron betiği joker karakterle (örneğin bir dizindeki tüm dosyalar üzerinde) bir arşivleme/işleme komutu çalıştırıyorsa, saldırgan o dizine, komutun seçenek olarak yorumlayacağı adlarda dosyalar yerleştirerek argüman enjeksiyonu yapabilir. Bu, özellikle bazı arşivleme araçlarında "checkpoint" benzeri özelliklerle keyfi komut çalıştırmaya dönüşen ünlü bir tekniktir.

Saldırganın cron görevlerini keşfetme mantığı iki yönlüdür: bir yandan okunabilir cron yapılandırma dosyalarını inceler, öte yandan çalışan işlemleri izleyerek periyodik olarak beliren süreçleri tespit eder (yapılandırma okunamasa bile, bir işlem izleme yöntemiyle gizli cron işleri ortaya çıkarılabilir).

### Savunma

- `root` cron betiklerinin ve içerdikleri tüm dosyaların yalnızca `root` tarafından yazılabilir olmasını sağlayın; dizin izinlerini de kontrol edin.
- Cron betiklerinde her zaman **mutlak yol** kullanın ve betik başında `PATH`'i açıkça, güvenli biçimde tanımlayın.
- Joker karakterlerle çalışan komutlarda `--` gibi seçenek-sonu işaretçileri kullanın ya da dosya listesini güvenli biçimde oluşturun; kullanıcı denetimli dizinlerde kör wildcard işlemlerinden kaçının.
- Cron yapılandırma dosyalarında ve betik dizinlerinde bütünlük izleme uygulayın.

## Kernel Exploit'leri

### Çalışma Mantığı

Çekirdek (kernel), sistemdeki en yüksek güven bağlamıdır; donanımı yönetir, işlemler arası izolasyonu sağlar ve tüm yetki kontrollerini uygular. Bir kernel açığı, düşük yetkili bir kullanıcının çekirdek belleğinde bir hata (memory safety bug, race condition, tam sayı taşması vb.) tetiklemesine ve çekirdek bağlamında kod çalıştırmasına ya da veri yapılarını değiştirmesine olanak tanır. Çekirdek bağlamında kod çalıştıran biri, tanım gereği `root`'tan da güçlüdür.

Kök neden, çekirdeğin büyük, C ile yazılmış ve düşük yetkili kullanıcılarla geniş bir arayüzden (system calls) temas eden karmaşık bir yazılım olmasıdır. Bu genişlik, kaçınılmaz olarak istismar edilebilir hatalar barındırır. Meşhur bir örnek sınıfı, bir bellek eşlemesinde yazma işleminin bir yarış koşulu (race condition) yoluyla salt-okunur korumasını atlamasına dayanan tekniklerdir; bu tür açıklar, salt-okunur dosyalara `root` gibi yazmayı mümkün kılabilir.

> Dürüstlük notu: kernel açıkları çok sürüm-özeldir. Belirli bir CVE, tam çekirdek sürüm aralığı ve exploit'in çalıştığı kesin koşulları ezberden vermek risklidir. Doğru yöntem, hedefin çekirdek sürümünü ve dağıtımını tespit edip, o sürüme uygun, doğrulanmış bir exploit aramaktır.

### İstismar Mantığı ve Riski

Saldırgan hedefin çekirdek sürümünü ve dağıtım bilgisini toplar, ardından bu sürüme karşı bilinen yerel yetki yükseltme (LPE) açıklarını araştırır. Kernel exploit'leri güçlüdür çünkü diğer yolların hepsi kapalı olsa bile işe yarayabilir. Ancak ciddi bir dezavantajı vardır: **kararsızdırlar.** Yanlış sürüme karşı ya da yanlış koşullarda çalıştırılan bir kernel exploit, sistemi çökertebilir (kernel panic). Bu yüzden deneyimli test uzmanları kernel exploit'i genellikle **son çare** olarak, daha güvenli yollar (SUID, sudo, cron, capabilities) tükendiğinde kullanır.

### Savunma

- **Yama yönetimi (patch management)** en kritik savunmadır. Kernel açıklarının ezici çoğunluğu, güncel yamalarla kapatılmış açıklardır; sömürülen sistemler neredeyse her zaman güncellenmemiş sistemlerdir.
- Modern çekirdek sertleştirme (hardening) özelliklerini etkin tutun; bu mekanizmalar birçok exploit tekniğini işe yaramaz hale getirir ya da güvenilirliğini düşürür.
- Gereksiz çekirdek modüllerini ve nadir kullanılan system call gruplarını (`seccomp` benzeri filtrelerle) kısıtlayarak saldırı yüzeyini daraltın.
- Kritik sistemlerde canlı yama (live patching) çözümlerini değerlendirin, böylece yeniden başlatma olmadan da açıklar kapatılabilir.

## Kimlik Avı (Phishing) ve Kimlik Bilgisi Toplama

### Bağlam ve Çalışma Mantığı

Yetki yükseltme her zaman teknik bir açıktan geçmez; çoğu zaman en kolay yol, bir kimlik bilgisini (credential) doğrudan ele geçirmektir. Linux ortamında bu, klasik e-posta kimlik avından farklı ama akraba tekniklerle olur. Kök neden insan ve süreç zafiyetleridir: parolalar dosyalarda düz metin olarak durur, kullanıcılar aynı parolayı her yerde kullanır ve güvenilir görünen istemlere (prompt) parolalarını girerler.

### İstismar Desenleri

- **Sahte `sudo` istemi:** Saldırgan, düşük yetkili kullanıcının oturumunda çalışan bir betik ya da takma ad (alias) yerleştirir; bu, gerçek `sudo` gibi görünen bir parola istemi gösterir, kullanıcının girdiği parolayı yakalar, sonra gerçek komutu çalıştırarak şüphe uyandırmaz. Yakalanan parola çoğu zaman `sudo` ile `root`'a geçmeye yeter.
- **Dosyalarda gömülü kimlik bilgileri:** Uygulama yapılandırma dosyaları, betikler, ortam değişkeni dökümleri, geçmiş komut dosyaları (shell history) ve yedekler sıklıkla parolalar, API anahtarları ve `root` ya da veritabanı kimlik bilgileri içerir. Saldırgan sistemde bu kalıpları arar. Bu, teknik olarak "phishing" değil kimlik bilgisi toplama (credential harvesting) olsa da, aynı hedefe hizmet eder.
- **SSH anahtarları ve ajan (agent) istismarı:** Korumasız özel SSH anahtarları ya da yönlendirilmiş (forwarded) SSH ajanları, saldırganın başka kimliklere ya da başka makinelere sıçramasına olanak tanır.

### Savunma

- Yönetici işlemleri için ayrı, güçlü kimlik doğrulama kullanın; mümkünse çok faktörlü doğrulama (MFA) ekleyin.
- Parolaları ve anahtarları asla düz metin dosyalarında saklamayın; sır yönetimi (secrets management) araçları kullanın.
- Kullanıcıları, beklenmedik `sudo` parola istemlerine karşı eğitin; oturum bütünlüğünü ve kabuk yapılandırma dosyalarındaki (`.bashrc`, `.profile`) beklenmedik değişiklikleri izleyin.
- SSH ajan yönlendirmesini yalnızca gerekli olduğunda ve güvenilir sunuculara açın.

## Yaygın Hatalar

**Saldırgan/test tarafında:**
- Kernel exploit'e erken atlamak. Daha güvenli ve daha güvenilir yollar (SUID, sudo, cron, capabilities) denenmeden çökme riski yüksek exploit çalıştırmak amatörce ve tehlikelidir.
- Numaralandırmayı (enumeration) atlamak. Yetki yükseltmenin yüzde sekseni doğru numaralandırmadır; sistemi anlamadan komut denemek zaman kaybıdır.
- Bulunan kimlik bilgilerini denememek. En sık gözden kaçan zafiyet, bir dosyada duran parolanın başka bir hesapta işe yaramasıdır (parola tekrar kullanımı).

**Savunmacı tarafında:**
- SUID/capabilities envanterini hiç çıkarmamak. Neyin var olduğunu bilmeden neyi savunacağınızı bilemezsiniz.
- `sudoers` kurallarında joker karaktere ve göreli yollara güvenmek.
- Yama yönetimini ihmal etmek; "çalışıyorsa dokunma" yaklaşımı, kapatılmamış kernel ve `sudo` açıklarını canlı bırakır.
- Yazılabilir dizinleri `nosuid` olmadan bağlamak ve dosya bütünlüğü izlemesi kurmamak.

## En İyi Pratikler

1. **En az yetki ilkesini uygulayın.** Her kullanıcıya, servise ve işleme yalnızca ihtiyaç duyduğu yetkiyi verin. SUID biti, `sudo` kuralı ve capability, hepsi "gerçekten gerekli mi?" sorusundan geçmelidir.
2. **Envanter ve baseline tutun.** SUID ikilileri, capability atanmış dosyalar, `sudoers` kuralları ve cron görevleri için bilinen bir temel oluşturun ve sapmaları otomatik izleyin. Yeni bir SUID dosyası ya da yeni bir capability, her zaman incelenmelidir.
3. **Sertleştirme seçeneklerini kullanın.** `nosuid`, `noexec` ve `nodev` gibi mount seçenekleri, `env_reset`/`secure_path` gibi `sudo` ayarları ve çekirdek sertleştirme özellikleri, saldırı yüzeyini kalıcı biçimde daraltır.
4. **Yama yönetimini ciddiye alın.** Kernel ve `sudo` başta olmak üzere yetki yükseltmeyle ilişkili bileşenleri güncel tutmak, tek başına en yüksek getirili savunmadır.
5. **Gözlemlenebilirlik kurun.** Dosya bütünlüğü izleme, ayrıcalıklı komut denetimi (audit) ve anomali tespiti, bir yükseltme denemesini erkenden yakalamanızı sağlar. Savunma yalnızca engelleme değil, aynı zamanda görebilme meselesidir.
6. **Sırları düzgün yönetin.** Kimlik bilgilerini düz metin dosyalardan çıkarın, sır yönetimi araçlarına taşıyın ve parola tekrar kullanımını politika düzeyinde engelleyin.

Sonuç olarak Linux yetki yükseltme, tek bir sihirli açıktan çok, yanlış çizilmiş güven sınırlarının bir toplamıdır. Saldırgan bu sınırları arayıp bulur; savunmacı ise onları doğru yere çeker, görünür kılar ve güncel tutar. İki tarafın da başlangıç noktası aynıdır: sistemi gerçekten anlamak.
