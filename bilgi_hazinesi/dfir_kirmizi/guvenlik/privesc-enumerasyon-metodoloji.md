# Privilege Escalation Enumerasyon Metodolojisi (Linux + Windows)

> Çerçeve: Bu metin yetkili bir güvenlik testi (pentest / red team engagement) bağlamında yazılmıştır. Amaç, saldırganın bir sistemde yetki yükseltmeden önce **nasıl düşündüğünü**, hangi sırayla enumere ettiğini ve kararı **neye göre** verdiğini anlamaktır — çünkü bunu anlamayan bir savunmacı doğru yerlere sensör koyamaz. Metin metodoloji ve yargı odaklıdır; canlı ya da izinsiz bir hedefe yönelik adım adım saldırı reçetesi değildir.

---

## 1. Bu aşama neyi hedefler, engagement'taki yeri

Yetki yükseltme (privilege escalation, kısaca privesc) enumerasyonu, bir makinede **sınırlı bir kullanıcı bağlamında** (düşük yetkili servis hesabı, sıradan domain kullanıcısı, web uygulaması altında çalışan `www-data` gibi) tutunduktan sonra, o bağlamı **daha yetkili bir bağlama** (root, SYSTEM, yerel Administrator, sonrasında domain seviyesinde ayrıcalık) taşımanın yolunu **haritalamak** anlamına gelir.

Engagement zincirindeki yeri kritik: Initial Access (ilk erişim) genellikle sizi zayıf bir bağlama koyar. Bir web servisinin çalıştığı kullanıcının ne SSH anahtarları vardır, ne de LSASS'a erişimi. Gerçek değer — kalıcılık (persistence), yanal hareket (lateral movement), kimlik bilgisi toplama (credential access) — neredeyse her zaman yükseltilmiş bir bağlam gerektirir. Bu yüzden privesc, bir engagement'ın "kilidi açan" aşamasıdır.

Enumerasyonun kendisi **exploit değildir**. Enumerasyon, "burada ne var, bu bağlamda neyi görebiliyorum, neyi değiştirebiliyorum, sistem bana kimliğini nasıl gösteriyor" sorularının cevabıdır. Olgun bir operatör için enumerasyon süresi, sömürü (exploitation) süresinin defalarca katıdır. Acemi, bir POC arar; profesyonel, **sistemin kendi konfigürasyonunun yarattığı yolları** arar — çünkü en güvenilir privesc genellikle bir CVE değil, bir yanlış yapılandırmadır (misconfiguration): fazla izin verilmiş bir dosya, korumasız bir servis, unutulmuş bir kimlik bilgisi.

---

## 2. Metodoloji ve karar ağacı (asıl değer)

### 2.1 Temel zihinsel çerçeve: üç eksen

Bir profesyonel makineye bakarken üç eksende düşünür. Her privesc bulgusu bu üçünden birine düşer:

1. **Kim olduğum (identity):** Hangi kullanıcı, hangi gruplar, hangi token/yetkiler, hangi ayrıcalıklar. Kimliğin sınırlarını bilmeden neyin "yükseltme" sayılacağını bilemezsiniz.
2. **Neyi çalıştırabildiğim/değiştirebildiğim (execution & write primitives):** Root/SYSTEM olarak çalışan ama benim yazabildiğim bir şey var mı? Bir dosya, bir servis binary'si, bir zamanlanmış görev, bir konfigürasyon.
3. **Neyi biliyor olabileceğim (secrets & trust):** Diskte, bellekte, geçmiş komutlarda, konfigürasyonlarda duran kimlik bilgileri. En hızlı yükseltme çoğu zaman "yeni bir zafiyet" değil, "başka birinin parolasını bulmak"tır.

Karar ağacının kökü şudur: **Önce ucuz ve gürültüsüz olanı topla, sonra pahalı ve gürültülü olana geç.** Enumerasyon bir maliyet-fayda hesabıdır; her komut hem zaman hem tespit riski taşır.

### 2.2 Faz 0 — Bağlamı sabitle (her iki OS)

İlk yapılan şey her zaman **"ben kimim ve neredeyim"** sorusudur. Bu, sömürü değil yönelimdir:

- Kullanıcı adı, üyesi olduğu gruplar, etkin ayrıcalıklar.
- Host adı, OS sürümü ve yama seviyesi, mimari (32/64-bit).
- Bu makine bir domain'e mi bağlı, yoksa yalıtılmış mı? (Bu tek soru, tüm stratejiyi ikiye böler: yerel privesc mi, yoksa domain saldırı yüzeyi mi?)
- Ağ konumu: hangi arayüzler, hangi iç ağlar görünür.

Bu fazın çıktısı bir "harita"dır. Deneyimli operatör buradan sonra rastgele komut atmaz; haritaya bakıp **hangi eksende zayıflık aramaya değeceğine** karar verir.

### 2.3 Linux karar ağacı

Linux'ta profesyonelin zihinsel sıralaması genelde şudur:

**(a) Kimlik ve grup üyelikleri.**
İlk bakılan `id` çıktısıdır. Neden? Çünkü bazı grup üyelikleri neredeyse "gizli root"tur: `docker`, `lxd`, `disk`, `sudo/wheel`, bazı dağıtımlarda `adm`. Bir kullanıcı `docker` grubundaysa, konteyner motoru üzerinden host dosya sistemine root olarak erişebilir — bu bir CVE değil, tasarım gereği verilmiş bir güçtür. Karar: "Grup üyeliklerimden biri bilinen bir yükseltme vektörü mü?" Evet ise, diğer her şeyden önce oraya bakılır çünkü en güvenilir yoldur.

**(b) `sudo` hakları.**
`sudo -l` çıktısı bir profesyonel için altın madenidir. Sorular: Parolasız (`NOPASSWD`) çalıştırabildiğim bir şey var mı? Çalıştırabildiğim binary "kırılabilir" mi — yani bir kabuk (shell) doğurabilen, dosya yazabilen ya da başka bir programı çağırabilen bir yeteneği var mı? Burada devreye GTFOBins mantığı girer: standart bir Unix aracının (editör, arşivleyici, dil yorumlayıcısı, sayfalama aracı) beklenmedik bir "shell escape" yeteneği. Karar kuralı: "Root olarak çağırabildiğim herhangi bir program, dolaylı olarak bana keyfi kod yürütme veriyor mu?"

**(c) SUID/SGID binary'leri ve capabilities.**
Sahibi root olan ve SUID biti set edilmiş, sahibinin yetkisiyle çalışan binary'ler taranır. Aynı GTFOBins yargısı geçerlidir. Modern sistemlerde `capabilities` (örneğin `cap_setuid`) de aynı rolü oynayabilir ve SUID taramasının gözden kaçırdığı bir yüzeydir — olgun operatör ikisini birden bakar.

**(d) Yazılabilir ama ayrıcalıklı bağlamda okunan/çalıştırılan şeyler.**
Bu, karar ağacının en verimli ama en çok atlanan dalıdır. Sorular:
- Root'un cron ile çalıştırdığı bir betik var mı, ve o betik ya da içerdiği bir dosya benim yazabildiğim bir yerde mi?
- `PATH` içinde yazabildiğim bir dizin, root'un çalıştırdığı bir betiğin önünde mi geliyor? (Görece yol / PATH hijacking mantığı.)
- Bir systemd servis dosyası, bir `.timer`, ya da onların çağırdığı bir binary benim değiştirebildiğim mi?
- Dünya-yazılabilir (`world-writable`) dosyalar ve dizinler, özellikle `/etc` altında.

Karar kuralı burada nettir: **"Ayrıcalıklı bir süreç, benim kontrol edebildiğim bir girdiyi güveniyor mu?"** Cevap evetse, bir yükseltme primitifiniz vardır.

**(e) Sırlar ve kimlik bilgileri.**
Konfigürasyon dosyaları (özellikle web app, veritabanı, yedekleme scriptleri), `.bash_history` ve diğer geçmiş dosyaları, çevre değişkenleri, SSH anahtarları, hafızada duran kimlik bilgileri. Karar: "Başka bir kullanıcının parolasını bulup yatay/dikey geçiş yapmak, bir exploit yazmaktan daha ucuz ve sessiz mi?" Çoğu zaman evettir.

**(f) Çekirdek/servis exploit'i — en son çare.**
Kernel exploit'i (örneğin bilinen yerel yükseltme sınıfları) genellikle **listenin sonundadır**, başında değil. Neden? Çünkü kernel exploit'leri makineyi çökertebilir (engagement'ta kabul edilemez bir yan etki), sürüme aşırı bağımlıdır, ve gürültülüdür. Profesyonel, misconfiguration yollarını tükettikten sonra buraya bakar. "Sürümü gördüm, hemen kernel exploit'i" refleksi acemiliğin en net işaretidir.

### 2.4 Windows karar ağacı

Windows'ta eksenler aynıdır ama primitifler farklıdır:

**(a) Kimlik, token ve ayrıcalıklar.**
`whoami /priv` ve `whoami /groups` çıktısı Linux'taki `id + sudo -l` karşılığıdır. Kritik olan **token ayrıcalıklarıdır**. Belirli ayrıcalıklar (impersonation sınıfı olanlar başta olmak üzere) tek başına SYSTEM'e giden kapıdır; bir servis hesabı bunlara sahipse yol neredeyse deterministiktir. Karar kuralı: "Bağlamımın taşıdığı bir ayrıcalık, tek başına bir yükseltme sınıfını açıyor mu?"

**(b) Servisler.**
Windows privesc'in kalbi servislerdir. Sorulan sorular katmanlıdır:
- **Zayıf servis izinleri:** Bir servisin konfigürasyonunu (özellikle çalıştırdığı binary yolunu) benim yeniden yapılandırma yetkim var mı? Varsa, servis SYSTEM olarak yeniden başladığında benim seçtiğim şeyi çalıştırır.
- **Zayıf binary/klasör izinleri:** Servisin işaret ettiği binary'yi ya da onun bulunduğu klasörü ben değiştirebiliyor muyum?
- **Tırnaksız servis yolu (unquoted service path):** Yol boşluk içeriyor ve tırnaksızsa, Windows yolu parçalayarak ararken benim yazabildiğim bir ara dizinde durabilir. Klasik ve hâlâ bulunan bir misconfiguration.
- **DLL arama sırası (DLL hijacking):** Ayrıcalıklı bir süreç, benim yazabildiğim bir yerden yüklenen bir DLL'e mi güveniyor?

Bunların hepsi tek bir yargıya indirgenir: **"SYSTEM olarak çalışan bir şey, benim yazabildiğim bir kaynağa güveniyor mu?"** — Linux'taki (d) dalıyla birebir aynı mantık, farklı kılıfta.

**(c) Zamanlanmış görevler.**
Task Scheduler ve deprecated `at` mekanizması (ATT&CK T1053) aynı soruyu doğurur: yükseltilmiş bir bağlamda çalışan bir görevin çağırdığı betik/binary benim değiştirebildiğim mi? `at`'in tarihsel notu ilginçtir: Windows'ta çalışması için Task Scheduler servisinin çalışıyor olması ve kullanıcının yerel Administrators grubunda olması gerekir — yani `at` bir *yükseltme* aracı değil, zaten yetkili bir bağlamda *kalıcılık/yürütme* aracıdır. Bunu karıştırmak yaygın bir kavram hatasıdır.

**(d) AlwaysInstallElevated, kayıt defteri ve otomatik çalışanlar (autoruns).**
`AlwaysInstallElevated` politikası hem makine hem kullanıcı kovanında set edilmişse, sıradan kullanıcı SYSTEM bağlamında paket kurabilir — saf bir misconfiguration yükseltmesi. Registry içinde saklanmış otomatik oturum açma kimlik bilgileri, servis parametreleri ve autorun girdileri de bu dala girer.

**(e) Sırlar ve kimlik bilgileri.**
Windows'ta bu dal özellikle zengindir: yanıtlar dosyaları (unattend/sysprep), Group Policy Preferences kalıntıları, kayıtlı kimlik bilgileri, uygulama konfigürasyonları, bellekte duran materyaller. Domain bağlamında, sıradan bir kullanıcının bile okuyabildiği dizin nesneleri (kullanıcı/grup ilişkileri, hizmet ilkeleri, delegasyon ayarları) yatay ve dikey hareket için bir hazinedir. Varsayılan hesaplar (ATT&CK T1078.001) — Guest, yerleşik Administrator, cihaz/uygulama fabrika hesapları — hâlâ değiştirilmemişse en ucuz yoldur.

**(f) UAC bypass ve sosyal katman.**
Zaten Administrators grubunda olan ama bütünlük seviyesi düşük bir bağlamdaysanız, sorun "yatay UAC sınırı"dır. Ayrı olarak, GUI kimlik bilgisi yakalama (ATT&CK T1056.002) — sahte ama meşru görünen bir kimlik doğrulama penceresiyle kullanıcıdan parola istemek — teknik bir zafiyet değil, insan katmanını kullanan bir yoldur. Bir savunmacı açısından önemli olan: privesc her zaman bir binary hatası değildir; bazen sadece ikna edici bir dialog kutusudur.

### 2.5 Karar ağacının birleştirici ilkesi

Her iki OS'ta da profesyonel aynı üç soruyu döngüsel sorar ve **maliyeti artan sırayla** ilerler:

1. Bana zaten verilmiş bir güç var mı? (gruplar, ayrıcalıklar, sudo) — en ucuz.
2. Ayrıcalıklı bir süreç benim kontrol ettiğim bir girdiye güveniyor mu? (yazılabilir binary/betik/servis/görev/DLL/PATH) — orta maliyet, en güvenilir.
3. Diskte/bellekte bir sır var mı? — değişken maliyet, çoğu zaman en sessiz.
4. Son çare: sürüme bağımlı exploit. — en pahalı, en gürültülü, en kırılgan.

"Şu bulguyu görünce şu yöne giderim" örnekleri:
- `id` çıktısında `docker`/`lxd` → diğer her şeyi bırak, oraya bak.
- `sudo -l`'de bir yorumlayıcı ya da editör NOPASSWD → GTFOBins yargısı, bitti sayılır.
- `whoami /priv`'de bir impersonation ayrıcalığı → servis/token yoluna odaklan.
- Tırnaksız servis yolu + yazılabilir ara klasör → yüksek güvenilirlikli, patlamayan bir yol.
- Konfigürasyonda düz metin DB parolası → önce onu dene, exploit yazma.

---

## 3. Acemi vs pro: hatalar, gözden kaçanlar, verimsizlikler

**"Sürüm gördüm, exploit çalıştırdım" refleksi.** Acemi, kernel/OS sürümünü görür görmez bir searchsploit sorgusuna koşar. Pro, bunu son çare olarak saklar çünkü misconfiguration yolları hem daha güvenilir hem daha sessizdir ve makineyi çökertmez. Bir engagement'ta hedefi çökertmek çoğu zaman sözleşme ihlalidir.

**Otomatik araca kör güvenmek.** Acemi, bir enumerasyon aracını (WinPEAS/LinPEAS türü) çalıştırıp kırmızı vurguları arar ve gerisini görmez. Pro, aracı bir "ikinci göz" olarak kullanır ama ham çıktıyı da okur — çünkü araçlar bağlama özgü zincirleri (iki zayıf iznin birleşiminden doğan yolu) çoğu zaman kaçırır. Ayrıca bu araçlar çok gürültülüdür; bir SOC'un dikkatini anında çeker.

**Yazma yetkisini "önemsiz" saymak.** Acemi, yazabildiği ama "ilginç görünmeyen" bir dosyayı atlar. Pro sorar: "Bunu kim, hangi yetkiyle okuyor/çalıştırıyor?" Dünya-yazılabilir bir betik tek başına bir şey değildir; onu root'un cron'u çalıştırıyorsa her şeydir. Gözden kaçan hep bu bağlantıdır.

**Sırları küçümsemek.** Acemi, `.bash_history`, config dosyaları, hafıza gibi "sıkıcı" yerlere bakmaz, bir zafiyet ister. Gerçek engagement'ların çoğu, birinin bir yere düz metin bıraktığı bir parolayla ilerler. En yüksek yatırım getirisi olan yer burasıdır.

**Bütünlük/token semantiğini yanlış anlamak.** Windows'ta "Administrators grubundayım ama SYSTEM değilim ve işlem düşük bütünlükte" durumunu acemi karıştırır. Pro, yatay UAC sınırı ile gerçek dikey yükseltmeyi ayırır; hangisiyle uğraştığını bilmek doğru tekniği seçtirir.

**Not tutmamak.** Acemi bulguları aklında tutar, aynı komutu üç kez çalıştırır (gürültü + zaman kaybı). Pro her bulguyu, her hesabı, her yazılabilir yolu kaydeder — hem raporlama için hem de zinciri sonradan görebilmek için. Enumerasyon bir kez yapılıp saklanır; tekrar tekrar sorgulamak hem verimsiz hem tespit edilebilirdir.

**Temizlik ve geri döndürülebilirlik.** Acemi, denediği yollarda kalıntı bırakır (yazdığı dosya, değiştirdiği servis, oluşturduğu görev). Pro, engagement kurallarına uygun olarak yaptığı her değişikliği kaydeder ve geri alır; bir sistemi test sonrası zayıf bırakmak sözleşmenin ihlalidir.

---

## 4. Savunma köprüsü (mavi takım)

Bu aşamanın savunmacı için anlamı büyüktür, çünkü **enumerasyon iz bırakır** ve bu izler doğru yerlere sensör konursa erken yakalanabilir. Saldırganın "sessiz" sandığı adımların çoğu, doğru telemetriyle gürültülüdür.

**Ne iz bırakır:**
- **Keşif komutlarının yığılması.** Kısa bir zaman penceresinde `whoami`, grup/ayrıcalık sorgulama, servis listeleme, sudo hak sorgulama gibi komutların bir kullanıcıdan ardı ardına gelmesi, tek başlarına masum olsalar da **desen olarak** anormaldir. Sıradan bir kullanıcı gün içinde `whoami /priv` çalıştırmaz.
- **Otomatik enumerasyon araçları.** Bu araçlar yüzlerce dosya sistemi ve registry sorgusunu saniyeler içinde yapar; bu erişim hacmi ve hızı bir davranış imzasıdır.
- **Hassas dosyalara erişim.** SUID taraması, gölge parola dosyalarına ya da kimlik bilgisi barındıran konfigürasyonlara okuma erişimi, GPP/unattend dosyalarına dokunma — bunlar dosya erişim denetimiyle görülebilir.
- **Servis/görev/registry değişiklikleri.** Bir servisin binary yolunun değişmesi, yeni bir zamanlanmış görev (T1053) oluşturulması, `AlwaysInstallElevated` benzeri politika anahtarlarının okunması/yazılması — bunlar yüksek değerli, düşük gürültülü tespit noktalarıdır.

**Nasıl tespit edilir (mantık):**
- **Süreç oluşturma denetimini komut satırı kaydıyla açmak.** Windows'ta detaylı süreç oluşturma logu + komut satırı yakalama, Linux'ta auditd/eBPF tabanlı yürütme telemetrisi olmadan bu aşama büyük ölçüde görünmezdir. Görünürlük birinci önceliktir.
- **Tek olayları değil desenleri avlamak.** Tekil `whoami` alarm üretmez; kısa pencerede kümelenmiş keşif komutları üretmelidir. Tespit mühendisliği burada "tek imza" değil "davranış zinciri" düşünmelidir.
- **Yüksek-sadakat kancalar.** Servis binPath değişikliği, yeni SUID dosya oluşumu, `at`/schtasks ile görev kaydı, LSASS'a erişim gibi olaylar nadiren meşrudur; bunlar yanlış-pozitifi düşük, değeri yüksek kurallardır.
- **Aldatma (deception).** Bilinçli olarak konulmuş sahte kimlik bilgileri (honeytoken/canary), enumerasyon yapan bir saldırganı yakalamanın en verimli yollarından biridir: meşru kullanıcı asla o parolayı denemez.

**Sertleştirme (kök neden):** Tespitten önce gelen şey, saldırı yüzeyini daraltmaktır — en az ayrıcalık ilkesi, servis hesaplarına gereksiz ayrıcalık vermemek, tırnaksız servis yolu/zayıf ACL gibi misconfiguration'ları düzenli taramak, varsayılan hesap parolalarını (T1078.001) değiştirmek, `AlwaysInstallElevated`'ı kapatmak. Bir yükseltme yolu hiç var olmazsa, tespit edilecek olay da olmaz.

---

## 5. Araçlar ve gerçek dünya notları

**Enumerasyon otomatlayıcıları (LinPEAS / WinPEAS / linux-smart-enumeration / benzerleri):** Geniş yüzeyi hızla tarayıp öne çıkanları renklendirirler. Değeri: hız ve kapsam. Tuzağı: gürültü ve "kırmızı = zafiyet" yanılgısı. Pratik tüyo: bir engagement'ta bunları körlemesine çalıştırmak SOC alarmı demektir; olgun operatör ya çıktıyı offline analiz için toplar ya da manuel, seçici sorgularla gider.

**GTFOBins ve LOLBAS:** Sırasıyla Unix ve Windows dünyasında "meşru binary'lerin beklenmedik yetenekleri" referanslarıdır. Bunlar araç değil, **yargı kütüphaneleridir**: "Bu binary'yi ayrıcalıklı bağlamda çağırabiliyorum; onu nasıl kabuğa/dosya yazmaya çevirebilirim?" sorusunun kataloğu. Bir profesyonelin bunları ezberden bilmesi değil, mantığını bilmesi beklenir.

**Domain görünürlük araçları (BloodHound türü graf analizciler):** Windows domain bağlamında, sıradan bir kullanıcının bile okuyabildiği ilişkileri bir grafa çevirip "en kısa yükseltme yolunu" görselleştirirler. Değeri, insan gözünün kaçıracağı dolaylı yolları (A, B'yi kontrol eder, B, C'ye ulaşır...) ortaya çıkarmasıdır. Bir savunmacı için de aynı araç, kendi ortamındaki tehlikeli yolları görmenin en iyi yoludur — kırmızı ve mavinin aynı haritayı kullandığı nadir yerlerden biri.

**Manuel yerleşik araçlar:** Çoğu zaman en sessiz enumerasyon, harici araç indirmeden, sistemin kendi yerleşik komutlarıyla yapılandır. Yerleşik araçlar disk üzerinde yeni bir dosya bırakmaz ve "beklenen binary" oldukları için daha az dikkat çekerler. Pratik gerçek: harici bir enumeratör indirmek, çoğu zaman enumerasyonun kendisinden daha çok iz bırakır.

**Gerçek dünya notları:**
- **Zaman dağılımı:** Saha gerçekliği, sürenin ezici çoğunluğunun enumerasyon ve doğrulamada, çok küçük bir kısmının fiili sömürüde geçtiğidir. "Exploit'i bul" değil, "yolu anla" işidir.
- **En güvenilir yol nadiren en havalı olandır.** Bir kernel 0-day değil, unutulmuş bir yedekleme scriptinin içindeki parola ya da yanlış ACL'li bir servis çoğu engagement'ı çözer.
- **Bağlam her şeyi değiştirir.** Aynı bulgu (dünya-yazılabilir bir dosya) bir sistemde değersiz, diğerinde kritiktir; farkı yaratan, o kaynağa **kimin, hangi yetkiyle dokunduğudur**. Metodolojinin tamamı bu tek soruyu farklı kılıflarda sormaktan ibarettir.
- **Kurallar ve kapsam (scope):** Yetkili bir testte enumerasyon bile kapsam dahilinde olmalıdır; bazı sistemlere dokunmak, bazı araçları çalıştırmak sözleşmeyle yasak olabilir. Profesyonelliğin bir parçası, "yapabilirim" ile "yapmama izin var" arasındaki farkı bilmektir.

---

### Kapanış

Privesc enumerasyonu bir komut listesi değil, bir **yargı disiplinidir**. Üç eksen (kim olduğum, neyi değiştirebildiğim, neyi bilebileceğim) ve tek birleştirici soru — *"ayrıcalıklı bir şey, benim kontrol edebildiğim bir girdiye mi güveniyor?"* — hem Linux'u hem Windows'u, hem saldırıyı hem savunmayı kapsar. Acemiyi profesyonelden ayıran şey bildiği exploit sayısı değil, **hangi yolu, hangi sırayla, hangi maliyetle deneyeceğine dair verdiği karardır**. Ve tam olarak bu karar ağacını anlayan bir savunmacı, doğru dört beş sensörle saldırganın en güvendiği sessiz adımları gürültülü hale getirebilir.
