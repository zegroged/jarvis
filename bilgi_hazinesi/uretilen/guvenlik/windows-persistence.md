# Windows Kalıcılık Teknikleri (Persistence)

## Tanım ve Bağlam

Kalıcılık (persistence), bir saldırganın sisteme ilk erişimi elde ettikten sonra, sistem yeniden başlatılsa, kullanıcı oturumu kapansa veya çalışan process (süreç) sonlandırılsa bile erişimini koruyabilmesini sağlayan tekniklerin bütünüdür. MITRE ATT&CK çerçevesinde bu, "Persistence" adı verilen tam bir taktik kategorisidir ve modern bir saldırı zincirinin (kill chain) neredeyse zorunlu bir halkasıdır.

Kalıcılığın neden bu kadar merkezi olduğunu anlamak için saldırganın maliyet-fayda hesabına bakmak gerekir. İlk erişim (initial access) genellikle bir saldırının en pahalı ve en gürültülü aşamasıdır: bir phishing kampanyası, bir zero-day exploit, çalınmış bir kimlik bilgisi. Saldırgan bu kadar emek harcayıp içeri girdikten sonra, tek bir yeniden başlatmayla veya bir EDR (Endpoint Detection and Response) tespitiyle bu erişimi kaybetmek istemez. Kalıcılık, ilk erişimin değerini "amorti eden" mekanizmadır. Bu yüzden savunma tarafında da kalıcılık, tespit için altın bir fırsattır: saldırgan diskte veya konfigürasyonda kalıcı bir iz bırakmak zorundadır ve bu iz, doğru bakılan yerlerde yakalanabilir. Kalıcılık, saldırganın "kör noktası"dır — dinamik ve geçici olmak zorunda olan diğer aşamaların aksine, tanım gereği bir yere yazılmış ve orada duran bir şeydir.

Bu makale Windows üzerindeki en yaygın ve en çok istismar edilen dört kalıcılık ailesini derinlemesine ele alır: **Registry Run Key'leri**, **Scheduled Task'lar (zamanlanmış görevler)**, **Windows Service'ler (hizmetler)** ve **WMI olay abonelikleri (event subscription)**. Her biri için çalışma mantığını, kök nedenini, istismar biçimini ve savunma/tespit yaklaşımını birlikte inceleyeceğiz. Sonda ise ortak tespit felsefesini, yaygın hataları ve en iyi pratikleri toparlayacağız.

Önemli bir çerçeve: kalıcılık teknikleri neredeyse her zaman meşru bir işletim sistemi özelliğinin kötüye kullanılmasıdır. Windows'un otomatik başlatma mekanizmaları, zamanlayıcıları ve olay altyapısı meşru yazılımlar için tasarlanmıştır. Saldırgan yeni bir açık icat etmez; var olan ve güvenilir sayılan bir mekanizmaya kendi kodunu iliştirir. Bu, hem tespiti zorlaştıran hem de "living off the land" (LOL — sistemin kendi araçlarıyla ve ikilileriyle yaşama) felsefesinin özünü oluşturan noktadır. Tespitin zorluğu da buradan gelir: kötü niyetli kalıcılığı meşru kalıcılıktan ayıran şey mekanizmanın kendisi değil, mekanizmanın *neyi çalıştırdığı* ve *nasıl oluşturulduğudur*.

---

## Registry Run Key'leri

### Çalışma Mantığı ve Kök Neden

Windows başlatıldığında veya bir kullanıcı oturum açtığında, işletim sistemi belirli Registry anahtarlarını okuyarak orada listelenen komut satırlarını otomatik olarak çalıştırır. Bu davranış bir açık değil, tasarlanmış bir özelliktir: kullanıcıların her açılışta güncelleyici, senkronizasyon aracı veya tepsi (tray) uygulaması gibi programlarının otomatik başlamasını beklemesi normaldir.

En bilinen anahtarlar şunlardır:

- `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- `HKLM\Software\Microsoft\Windows\CurrentVersion\Run`
- Aynı yolların `RunOnce` varyantları (tek seferlik çalıştırma; değer çalıştırıldıktan sonra normalde silinir)

Buradaki temel ayrım önemlidir: `HKCU` (HKEY_CURRENT_USER) altındaki anahtarlar yalnızca o kullanıcı oturum açtığında tetiklenir ve **yönetici (administrator) yetkisi gerektirmez** — kullanıcı kendi profilinin Registry hive'ına yazabilir. `HKLM` (HKEY_LOCAL_MACHINE) altındakiler ise tüm kullanıcılar için sistem genelinde tetiklenir ama yazmak için yükseltilmiş yetki (elevation) ister. Saldırgan açısından bu, yetki seviyesine göre bir menü sunar: sıradan bir kullanıcı yetkisiyle bile `HKCU\...\Run` kullanılabilir; bu, en düşük eşikli kalıcılık yöntemlerinden biridir ve tam da bu yüzden çok yaygındır.

Kök neden şudur: Windows bu anahtarların içeriğini çalıştırırken herhangi bir imza doğrulaması, yol beyaz-listesi (allowlisting) veya bütünlük kontrolü uygulamaz. Anahtardaki değer bir komut satırıdır ve olduğu gibi işletilir. Mekanizma "ne çalıştırdığına" değil "kaydedilmiş olmasına" bakar. Bu güven varsayımı, meşru yazılımlar için kolaylık, saldırgan için ise açık kapıdır.

Run Key ailesinin daha az bilinen ama daha sinsi akrabaları da vardır. Örneğin `Winlogon` altındaki `Userinit` ve `Shell` değerleri oturum açma akışının çok erken bir noktasında çalıştırılır; buradaki değere virgülle ikinci bir program eklemek klasik bir tekniktir. Benzer şekilde `Image File Execution Options` (IFEO) altında bir programa `Debugger` değeri tanımlamak, o program her çalıştığında saldırganın belirttiği ikilinin onun yerine (veya debugger olarak) başlatılmasına yol açar. Bunların hepsi aynı kök nedeni paylaşır: Windows'un bir Registry değerini sorgusuz sualsiz bir yürütme talimatı olarak kabul etmesi.

### Somut Örnek ve İstismar Mantığı

Bir saldırgan, düşük yetkili bir shell elde ettikten sonra kendi payload'ını (yükünü) diske yazar ve şuna benzer bir kayıt oluşturur:

```
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "OneDriveUpdate" /t REG_SZ /d "C:\Users\Public\svc.exe" /f
```

Burada iki istismar detayı dikkat çeker. Birincisi, değer adının (`OneDriveUpdate`) meşru bir yazılıma benzetilmesi — bu, bir yönetici Registry'ye baktığında gözden kaçırmayı hedefler; sosyal mühendislik burada makinenin operatörüne değil, olay yerini inceleyen analiste yöneliktir. İkincisi, payload'ın `C:\Users\Public` gibi kullanıcı yazabilir bir dizine konması — çünkü `Program Files` gibi korumalı yollar yönetici yetkisi ister.

İleri düzey saldırganlar diske EXE yazmaktan tamamen kaçınmak ister; çünkü dosya, antivirüs ve EDR için en kolay yakalanan iz türüdür. Bu yüzden Run Key değerine doğrudan bir yorumlayıcı komutu yazarlar: örneğin `powershell -w hidden -enc <base64>` veya `rundll32`, `mshta`, `regsvr32` gibi imzalı ve güvenilir Windows ikililerini (LOLBins — living-off-the-land binaries) kötü amaçlı bir betiği veya uzak bir kaynağı yüklemek için kullanırlar. Böylece diskte kalıcı olan tek şey Registry değeridir; asıl kod bellekte veya uzakta durur. Bu, "fileless persistence" mantığının Run Key üzerindeki tipik uygulamasıdır.

### Savunma ve Tespit

Run Key savunmasının temeli, bu anahtarların sürekli izlenmesidir. Sysinternals'in **Autoruns** aracı, tüm otomatik başlatma noktalarını (Run Key'ler dahil onlarca farklı ASEP — Auto-Start Extensibility Point) tek yerde toplar ve dijital imza durumunu gösterir. İmzasız veya bilinmeyen bir yayıncıya ait bir Run değeri, ilk elemede öne çıkarılması gereken şeydir. Autoruns'un komut satırı sürümü (`autorunsc`) düzenli olarak çalıştırılıp çıktısı bir temel (baseline) ile karşılaştırılabilir.

Gerçek zamanlı tespit için Registry yazma olaylarının loglanması gerekir. **Sysmon** Event ID 12/13/14 (Registry nesne oluşturma/silme, değer ayarlama, yeniden adlandırma) Run Key yollarına yapılan yazmaları yakalar. Doğru kurulmuş bir Sysmon konfigürasyonuyla, `\CurrentVersion\Run` alt ağacına yapılan her değer değişikliği bir alarm üretebilir. Kritik nokta: bu tür bir yazma meşru bir kurulum sırasında da olur, dolayısıyla ham olay değil, **hangi process'in yazdığı** (parent process) belirleyicidir. `powershell.exe` veya `cmd.exe`'nin `winword.exe` veya `outlook.exe` gibi bir üst süreçten türeyip Run Key'e yazması, güçlü bir kötü niyet sinyalidir.

Savunma derinliği açısından, uygulama kontrolü (WDAC — Windows Defender Application Control veya AppLocker) burada dolaylı ama etkili bir katmandır: Run Key kötü niyetli bir ikiliyi çalıştırmaya kalksa bile, imzasız/beyaz-listede olmayan ikilinin çalışması engellenirse kalıcılık işlevsiz kalır. Kalıcılık tespitini yalnızca "kaydı bulmaya" indirgemek yerine, "kaydın çalıştıracağı şeyi engelleme" katmanını da eklemek doğru mimaridir.

---

## Scheduled Task'lar (Zamanlanmış Görevler)

### Çalışma Mantığı ve Kök Neden

Windows Task Scheduler, bir eylemi belirli bir zamanda veya belirli bir tetikleyici (trigger) gerçekleştiğinde çalıştıran genel amaçlı bir zamanlayıcıdır. Tetikleyici çeşitliliği, bu mekanizmayı kalıcılık için son derece esnek ve güçlü kılar: bir görev sistem başlangıcında (at startup), kullanıcı oturum açtığında (at logon), belirli aralıklarla, boşta kalınca (on idle), bir olay günlüğüne (event log) belirli bir kayıt düştüğünde veya bir ağ olayında tetiklenebilir.

Kök neden ve saldırgan çekiciliği şuradan gelir: zamanlanmış görevler **SYSTEM** bağlamında çalışacak şekilde yapılandırılabilir — yani makinedeki en yüksek yerel yetki. Ayrıca görevin çalışması, saldırganın oturumundan veya varlığından tamamen bağımsızdır; saldırgan çıkış yapsa bile görev planlanan zamanda çalışır. Bu iki özellik (yüksek yetki + bağımsız tetiklenme), zamanlanmış görevi hem kalıcılık hem de yetki yükseltme (privilege escalation) için ideal kılar.

Zamanlanmış görevlerin dahili yapısı savunma açısından kritiktir. Her görevin iki temsili vardır: `C:\Windows\System32\Tasks` altındaki bir XML dosyası ve Registry'de `HKLM\...\Schedule\TaskCache` altındaki kayıtlar (özellikle `Tree` ve `Tasks` alt anahtarları). Bu ikilik önemli bir istismar yüzeyi doğurur: bazı gizlenme (evasion) teknikleri, görevi normal API üzerinden değil doğrudan bu Registry ve dosya yapılarını manipüle ederek oluşturur veya bir görevi standart araçlardan (örneğin `schtasks /query` veya Task Scheduler MMC arayüzü) "görünmez" kılmaya çalışır — örneğin `TaskCache\Tree` altındaki `SD` (Security Descriptor) değerini silerek görevi listeleme araçlarından gizleme gibi teknikler bilinmektedir.

### Somut Örnek ve İstismar Mantığı

Klasik ve gürültülü bir oluşturma şöyledir:

```
schtasks /create /tn "UpdateHealthCheck" /tr "C:\Users\Public\svc.exe" /sc onlogon /ru SYSTEM
```

Burada `/sc onlogon` tetikleyiciyi oturum açmaya bağlar, `/ru SYSTEM` ise görevi SYSTEM olarak çalıştırır (bu, oluşturma anında yönetici yetkisi gerektirir). Görev adının yine meşru bir bakım işine benzetildiğine dikkat edin.

İstismar mantığının inceliği, tetikleyici seçiminde saklıdır. Bir saldırgan görevi her açılışta çalıştırmak yerine, örneğin belirli bir Windows olay günlüğü kaydına bağlarsa, tespit için "sistem başlangıcında çalışan görevleri" tarayan basit avlar bu görevi kaçırır. Aynı şekilde, görevi çok seyrek (örneğin haftada bir) veya kullanıcı belirli bir süre boşta kaldığında tetiklemek, davranışsal analizde öne çıkmayı azaltır. Bir başka yaygın örüntü, meşru bir Microsoft görevini (örneğin bir güncelleme veya telemetri görevini) kopyalayıp yalnızca `Actions` bölümündeki komutu değiştirmek; böylece görev meta verisi tümüyle meşru görünürken çalıştırdığı şey kötü niyetlidir.

Yakın geçmişte, `schtasks` aracının kendisinde ve Task Scheduler'ın iç yapılarında, bir görevi ayrıcalıkları kötüye kullanarak SYSTEM'e yükseltmeye veya görevi gizlemeye izin veren çeşitli zafiyetler raporlanmıştır. Kesin CVE numaralarını burada uydurmak yerine kavramı vurgulayalım: zamanlayıcının XML/Registry ikili temsili ile güvenlik denetimleri arasındaki uyumsuzluklar, tekrar eden bir zafiyet sınıfı olmuştur. Bu tür ayrıntılar için resmi güvenlik bültenlerine (MSRC) başvurulmalıdır.

### Savunma ve Tespit

Zamanlanmış görev tespitinin en güvenilir kaynağı Windows'un kendi olay günlükleridir. `Microsoft-Windows-TaskScheduler/Operational` günlüğü, görev oluşturma, silme, kayıt (registration) ve çalıştırma olaylarını ayrı Event ID'lerle kaydeder. Özellikle görev *kaydı* (registration) olayı, "yeni bir kalıcılık oluşturuldu" sinyalinin doğrudan kanıtıdır. Ayrıca Güvenlik günlüğündeki Event ID 4698 (bir zamanlanmış görev oluşturuldu), denetim (audit) açıksa güçlü bir tespit noktasıdır. Bu günlükler her ortamda varsayılan olarak aktif toplanmaz; olgun bir SOC (Security Operations Center) bunları merkezi log toplama (SIEM) kapsamına almalıdır.

İkinci güçlü sinyal, **Sysmon Event ID 1** (process oluşturma) üzerinden gelir: `taskeng.exe` veya `svchost.exe` (Schedule hizmeti bağlamı) altında beklenmedik bir çocuk süreç — özellikle bir betik yorumlayıcısı veya bilinmeyen bir ikili — güçlü bir işaret verir. Yine parent-child ilişkisi belirleyicidir: normal bir sistemde SYSTEM olarak çalışan bir zamanlanmış görevin `powershell.exe -enc ...` başlatması olağan değildir.

Baseline karşılaştırması burada da vazgeçilmezdir. `C:\Windows\System32\Tasks` klasöründeki XML dosyalarının ve `TaskCache` Registry ağacının düzenli olarak envanterlenip bilinen-iyi bir temel ile karşılaştırılması, "listeleme araçlarından gizlenmiş" görevleri bile ortaya çıkarabilir — çünkü dosya sisteminde ve Registry'de bırakılan artefaktlar, kullanıcı arayüzünde görünmese de fiziksel olarak oradadır. Bu, "aracın gösterdiğine değil, diskin içerdiğine bak" ilkesinin somut uygulamasıdır.

---

## Windows Service'ler (Hizmetler)

### Çalışma Mantığı ve Kök Neden

Windows Service'ler, kullanıcı arayüzü olmadan arka planda çalışan, sistem açılışında (kullanıcı oturum açmadan önce) otomatik başlatılabilen ve genellikle SYSTEM yetkisiyle koşan uzun ömürlü process'lerdir. Service Control Manager (SCM), bu hizmetlerin yaşam döngüsünü yönetir ve her hizmetin konfigürasyonunu Registry'de `HKLM\SYSTEM\CurrentControlSet\Services\<HizmetAdı>` altında tutar. Buradaki kritik değerler `ImagePath` (çalıştırılacak ikilinin yolu), `Start` (başlatma tipi; otomatik/manuel/devre dışı) ve `ServiceDll` (bir `svchost` hizmetiyse yüklenecek DLL) değerleridir.

Saldırgan için hizmetlerin çekiciliği zamanlanmış görevlerinkiyle örtüşür: varsayılan olarak SYSTEM bağlamı ve açılışta otomatik başlama. Ancak hizmetler daha "kalıcı" ve daha derin bir varlık hissi verir; bir hizmet, işletim sisteminin altyapısının bir parçası gibi görünür. Bu, hem meşruiyet kamuflajı sağlar hem de bazı temizlik/tespit araçlarının hizmetleri Run Key'lere göre daha az agresif taramasından faydalanır.

Kök neden burada tek bir güven varsayımı değil, birden fazla zayıf noktanın birleşimidir. Hizmetler yalnızca "yeni bir kötü hizmet oluşturma" ile değil, **var olan meşru hizmetleri ele geçirme** yoluyla da istismar edilir. Başlıca istismar yüzeyleri şunlardır:

- **Zayıf hizmet izinleri:** Bir hizmetin konfigürasyonunu (özellikle `ImagePath`'i) düşük yetkili bir kullanıcı değiştirebiliyorsa, o kullanıcı hizmeti kendi ikilisine yönlendirip bir sonraki başlatmada SYSTEM'e yükselir. Bu, klasik bir yerel yetki yükseltme + kalıcılık kombinasyonudur.
- **Zayıf ikili dosya izinleri (weak binary permissions):** Hizmetin çalıştırdığı EXE dosyası, düşük yetkili kullanıcının yazabildiği bir konumdaysa, saldırgan dosyayı doğrudan kendi payload'ıyla değiştirir. Hizmet bir sonraki açılışta saldırganın kodunu SYSTEM olarak çalıştırır.
- **Tırnaksız hizmet yolu (unquoted service path):** `ImagePath` boşluk içeren ve tırnak içine alınmamış bir yolsa (örneğin `C:\Program Files\Some App\svc.exe`), Windows yolu çözerken önce `C:\Program.exe`, sonra `C:\Program Files\Some.exe` gibi ara adayları dener. Saldırgan bu ara konumlardan yazabildiği birine kötü niyetli bir EXE koyarsa, meşru hizmet yerine onunki çalışır. Bu, hem yaygın hem de sıklıkla göz ardı edilen bir yanlış yapılandırmadır.

### Somut Örnek ve İstismar Mantığı

Yeni bir hizmetin doğrudan oluşturulması şöyle görünebilir:

```
sc create WinDefendSvc binPath= "C:\Users\Public\svc.exe" start= auto
```

(`sc` sözdiziminde `binPath=` ile değeri arasındaki boşluğun bilinçli olduğuna dikkat edin; aracın kendine özgü ayrıştırma kuralıdır.) Hizmet adının Windows Defender'a benzetilmesi yine kamuflaj amaçlıdır.

Ancak daha sofistike ve sık görülen yol, var olan bir hizmeti hedef almaktır. Saldırgan `accesschk` (Sysinternals) gibi araçlarla hizmet izinlerini ve ikili dosya izinlerini tarar; `SERVICE_CHANGE_CONFIG` veya ikili üzerinde yazma hakkı bulduğu bir hizmeti seçer. Bu yaklaşım "yeni hizmet oluşturma" gürültüsünü tamamen ortadan kaldırır — çünkü hizmet zaten vardır, zaten meşrudur ve envanterlerde zaten kayıtlıdır; saldırgan sadece onun çalıştırdığı şeyi değiştirir. Ayrıca bir hizmet DLL'ini (`ServiceDll`) hedeflemek, EXE değiştirmekten daha sinsidir, çünkü `svchost.exe` altında birçok hizmet aynı meşru ana process'i paylaşır.

### Savunma ve Tespit

Hizmet tabanlı kalıcılığın en doğrudan tespit noktası, Güvenlik günlüğündeki Event ID 4697 (bir hizmet sisteme kuruldu) ve Sistem günlüğündeki Event ID 7045 (yeni bir hizmet yüklendi) olaylarıdır. Yeni bir hizmet kurulumu, kurumsal bir ortamda nadir bir olaydır ve bu yüzden yüksek sinyal/gürültü oranına sahip harika bir avdır. Bu olayı, hizmeti kuran hesabın ve üst process'in bağlamıyla zenginleştirmek (örneğin bir betikten kurulan hizmet) neredeyse kesin bir alarm üretir.

Yanlış yapılandırma temelli istismarlara karşı savunma ise tespitten çok **önleme** ile ilgilidir: hizmet ve ikili izinlerinin düzenli denetimi, tırnaksız yolların (unquoted paths) taranıp düzeltilmesi, hizmet ikililerinin yalnızca korumalı dizinlerde tutulması ve hizmet konfigürasyonlarını değiştirme yetkisinin (`SERVICE_CHANGE_CONFIG`) minimum ayrıcalık ilkesine (least privilege) göre kısıtlanması. Bu tür denetimleri PowerShell veya özel araçlarla periyodik olarak otomatikleştirmek, "saldırgan bulmadan önce yanlış yapılandırmayı bul" yaklaşımının temelidir.

Sürekli izleme tarafında, `HKLM\SYSTEM\CurrentControlSet\Services` altındaki `ImagePath` ve `ServiceDll` değerlerine yapılan değişiklikler Sysmon Registry olaylarıyla yakalanmalıdır. Var olan bir hizmetin `ImagePath`'inin değişmesi, "yeni hizmet oluşturma" kadar gürültülü değildir ama en az onun kadar tehlikelidir — bu yüzden özellikle izlenmesi gereken bir örüntüdür.

---

## WMI Olay Abonelikleri (Event Subscription)

### Çalışma Mantığı ve Kök Neden

Windows Management Instrumentation (WMI), Windows'un yönetim ve otomasyon altyapısıdır. WMI'nin en güçlü — ve saldırgan açısından en tehlikeli — özelliği, kalıcı olay aboneliği (permanent event subscription) mekanizmasıdır. Bu mekanizma üç bileşenden oluşur:

1. **Event Filter (`__EventFilter`):** Hangi olayın izleneceğini tanımlayan bir WQL (WMI Query Language) sorgusu. Örneğin "sistem 200 saniye çalıştığında" veya "belirli bir process başladığında" veya "belirli bir saatte" gibi bir koşul.
2. **Event Consumer (`__EventConsumer`):** Filtre tetiklendiğinde yapılacak eylem. En tehlikeli türler `CommandLineEventConsumer` (bir komut satırı çalıştırır) ve `ActiveScriptEventConsumer` (bir VBScript/JScript çalıştırır) tipleridir.
3. **Binding (`__FilterToConsumerBinding`):** Filtreyi tüketiciye bağlayan ve mekanizmayı canlı hale getiren nesne.

Bu üçlü, `root\subscription` WMI ad alanında (namespace) kalıcı olarak saklanır. Kök neden ve saldırgan çekiciliği buradaki üç özellikte yatar. Birincisi, bu abonelikler **WMI deposunda** (`CIM repository`, tipik olarak `%SystemRoot%\System32\wbem\Repository` altında) tutulur — geleneksel bir dosya veya Registry Run Key gibi görünmez; dosya tabanlı taramalar ve pek çok kalıcılık avı bu depoyu incelemez. İkincisi, tetiklendiğinde eylem `WmiPrvSE.exe` (WMI Provider Host) bağlamında, genellikle SYSTEM yetkisiyle çalışır — yani hem yüksek ayrıcalık hem de meşru bir üst process kamuflajı. Üçüncüsü, WQL sorgusu son derece esnek olduğundan tetikleyici neredeyse her koşula bağlanabilir; bu, WMI kalıcılığını hem sağlam hem de öngörülemez kılar.

Bu tekniğin gerçek dünyadaki önemi büyüktür: WMI olay aboneliği, gelişmiş kalıcı tehdit (APT) gruplarının ve önemli fidye yazılımı operasyonlarının kullandığı, "fileless" ve "stealthy" olarak sınıflandırılan üst düzey bir kalıcılık yöntemidir. Uzun süre "gizli köşe" olarak kalması, savunma araçlarının onu geç kapsamasından kaynaklandı.

### Somut Örnek ve İstismar Mantığı

Kavramsal olarak saldırgan, PowerShell'in WMI cmdlet'leri veya `wmic` ile şuna benzer bir yapı kurar: bir `__EventFilter`, "sistem açıldıktan yaklaşık 60-300 saniye sonra" gibi bir koşula bağlanır (bu, açılışta doğrudan tetiklenen görevlerden farklı olarak boot sürecinin gürültüsünden sonra sessizce çalışmayı sağlar); bir `CommandLineEventConsumer`, saldırganın payload'ını (örneğin gizli bir PowerShell komutu) çalıştıracak şekilde tanımlanır; ve bir `__FilterToConsumerBinding` bu ikisini birbirine bağlar.

İstismar mantığının inceliği çok katmanlıdır. Tetikleyici olarak sabit bir saat yerine "sistem uptime'ı" veya "belirli bir kullanıcının oturum açması" gibi bir koşul seçilirse, davranış öngörülemez hale gelir ve zamanlanmış görevlerdeki gibi net bir çalıştırma günlüğü bırakmaz. Payload'ın `ActiveScriptEventConsumer` ile inline (satır içi) bir betik olarak saklanması, diske hiç dosya yazmadan tam bir kod yürütme sağlar — bu, WMI'yi "fileless persistence"in en saf örneklerinden biri yapar. Ayrıca abonelik nesneleri WMI deposunda ikili (binary) biçimde saklandığından, düz metin arama yapan araçlarla bulunması zordur.

### Savunma ve Tespit

WMI kalıcılığının en iyi tespiti, Windows'un yerleşik WMI-Activity operasyonel günlüğüdür. Bu günlük, kalıcı olay aboneliği bileşenlerinin (filter, consumer, binding) oluşturulmasını kaydeden olaylar üretir — bir abonelik oluşturulduğunda ilgili Event ID'ler, "yeni WMI kalıcılığı" için doğrudan kanıt sunar. Bu telemetriyi SIEM'e almak, WMI kalıcılığını "görünmez" olmaktan çıkarmanın en etkili yoludur.

İkinci ve son derece güçlü kaynak **Sysmon**'dur: Sysmon, WMI olay filtresi, tüketicisi ve binding'inin oluşturulmasını özel Event ID'lerle (19, 20 ve 21) doğrudan raporlar. Bu üç olay, WMI kalıcılık avı için altın standarttır; bir ortamda `WmiPrvSE.exe`'nin bir `CommandLineEventConsumer` üzerinden `powershell.exe` başlatması ile birleştiğinde neredeyse kesin bir tehdit göstergesidir.

Proaktif avlanma (threat hunting) için `root\subscription` ad alanının doğrudan sorgulanması gerekir. PowerShell ile:

```
Get-WmiObject -Namespace root\subscription -Class __EventFilter
Get-WmiObject -Namespace root\subscription -Class __EventConsumer
Get-WmiObject -Namespace root\subscription -Class __FilterToConsumerBinding
```

Bu üç sorgunun çıktısı, temiz bir sistemde çoğunlukla boştur veya yalnızca birkaç bilinen Microsoft/güvenlik yazılımı girdisi içerir. Bilinmeyen, özellikle `ActiveScriptEventConsumer` veya `CommandLineEventConsumer` tipinde ve şüpheli bir komut içeren herhangi bir abonelik, derhal incelenmelidir. Bu tür bir çıktının bilinen-iyi bir baseline ile karşılaştırılması, WMI avının en pratik biçimidir.

---

## Ortak Tespit Felsefesi

Dört tekniği yan yana koyduğumuzda ortak bir tespit mantığı belirginleşir; bu mantığı içselleştirmek, tek tek Event ID ezberlemekten çok daha değerlidir.

Birincisi, **kalıcılık daima bir yere yazılır**. Run Key Registry'ye, zamanlanmış görev XML + Registry'ye, hizmet Registry'ye, WMI ise CIM deposuna. Saldırgan ne kadar "fileless" olursa olsun, konfigürasyon düzeyinde kalıcı bir artefakt bırakmak zorundadır. Bu, savunmacının değişmez kaldıracıdır: kalıcı nesneler oluşturulma anında (event) ve varlık olarak (baseline karşılaştırması) izlenebilir.

İkincisi, **parent-child process ilişkisi hemen her teknikte belirleyicidir**. Kötü niyetli kalıcılığı meşrudan ayıran en güçlü tek sinyal, "olması gerekmeyen bir üst süreç, olması gerekmeyen bir alt süreci başlatıyor" örüntüsüdür: `svchost` veya `WmiPrvSE`'nin bir betik yorumlayıcısı doğurması, bir Office uygulamasının Registry Run Key'e yazması gibi. Sysmon'un process oluşturma (Event ID 1) telemetrisi, tüm bu tekniklerin çalıştırma aşamasını ortak bir noktada yakalar.

Üçüncüsü, **baseline (temel) her şeydir**. Kalıcılık avının en büyük düşmanı, "neyin normal olduğunu bilmemek"tir. Bilinen-iyi bir sistemin Run Key'leri, zamanlanmış görevleri, hizmetleri ve WMI abonelikleri envanterlenip düzenli olarak farkı (diff) alınırsa, saldırganın eklediği tek bir kalıcılık noktası bu farkta parlar. Autoruns'un çıktısını periyodik saklamak, bu felsefenin en basit ve en güçlü uygulamasıdır.

Dördüncüsü, **imzalı LOLBin kullanımı tek başına suçsuzluk kanıtı değildir**. `rundll32`, `mshta`, `regsvr32`, `powershell` imzalı ve meşru araçlardır; ama bir kalıcılık noktasından çağrılmaları ve şüpheli argümanlar (kodlanmış komut, uzak URL, alışılmadık DLL) taşımaları güçlü göstergedir. Tespiti "imzasız EXE" aramaya indirgemek, modern saldırganların çoğunu kaçırır.

---

## Yaygın Hatalar

**Savunma tarafında:**

- **Yalnızca EXE ve dosya taramaya güvenmek.** Fileless kalıcılık (Run Key'de kodlanmış komut, inline WMI betiği) diskte yürütülebilir bir dosya bırakmaz. Yalnızca antivirüs imza taramasına dayanan bir savunma bu teknikleri tümüyle kaçırır.
- **WMI olay aboneliklerini hiç incelememek.** En çok gözden kaçan kalıcılık köşesi budur. Pek çok kurum Run Key ve hizmetleri izler ama `root\subscription` ad alanına hiç bakmaz.
- **Baseline tutmamak.** Bir sistemde 40 hizmet ve 60 zamanlanmış görev varken, "hangisi normal?" sorusuna cevabı olmayan bir analist, saldırganın eklediğini fark edemez.
- **Sysmon ve gelişmiş günlükleri toplamayı ihmal etmek.** Windows'un varsayılan denetim politikası bu tekniklerin çoğunu net kaydetmez; Event ID 4697/4698/7045 ve WMI-Activity günlükleri sıklıkla toplanmaz. Telemetri yoksa tespit de yoktur.
- **Kalıcılığı tek noktada temizlenmiş sanmak.** Olgun saldırganlar birden çok kalıcılık mekanizmasını (örneğin hem bir zamanlanmış görev hem bir WMI aboneliği) yedek olarak kurar. Biri bulunup silinince diğeri hayatta kalır. Bir kalıcılık noktası bulmak, avın bittiği değil derinleşmesi gerektiği anlamına gelir.

**Saldırgan mantığını yanlış modellemek (savunmacı için tuzak):**

- Kalıcılığın hep "açılışta" tetiklendiğini varsaymak. Olay tabanlı, uptime tabanlı veya seyrek tetikleyiciler bu varsayımı boşa çıkarır.
- Yüksek yetki gerektiğini varsaymak. `HKCU\...\Run` ve kullanıcı bağlamlı zamanlanmış görevler yönetici yetkisi olmadan kurulabilir.

---

## En İyi Pratikler

Savunma tarafında etkili bir kalıcılık programı katmanlı ve süreç-odaklıdır:

1. **Telemetriyi önce kur.** Sysmon'u iyi bir konfigürasyonla (process oluşturma, Registry yazma, WMI olayları dahil) yaygınlaştır; TaskScheduler/Operational, WMI-Activity, Security (4697/4698) ve System (7045) günlüklerini merkezi SIEM'e akıt. Tespit, ancak toplanan veri kadar iyidir.

2. **Baseline oluştur ve düzenli farkını al.** Autoruns/autorunsc çıktısını, hizmet listesini, zamanlanmış görev envanterini ve `root\subscription` içeriğini bilinen-iyi bir referans olarak sakla; periyodik olarak yeni durumla karşılaştır. Kalıcılık avının bel kemiği budur.

3. **Minimum ayrıcalık ilkesini (least privilege) uygula.** Kullanıcıların Registry HKLM alanlarına, hizmet konfigürasyonlarına ve korumalı dizinlere yazma hakkını kısıtla. Tırnaksız hizmet yollarını ve zayıf ikili/hizmet izinlerini periyodik denetle ve düzelt — bu, hem yetki yükseltmeyi hem de var olan mekanizmalar üzerinden kalıcılığı keser.

4. **Uygulama kontrolü ekle.** WDAC veya AppLocker ile yalnızca imzalı/beyaz-listede olan kodun çalışmasına izin ver. Bu, bir kalıcılık noktası kaydedilse bile çalıştıracağı payload'ı engelleyerek zinciri kırar.

5. **Parent-child davranışına dayalı tespit kuralları yaz.** "Office uygulaması → Run Key yazma", "svchost/WmiPrvSE → betik yorumlayıcısı", "SYSTEM zamanlanmış görev → kodlanmış PowerShell" gibi anomali örüntülerini alarm haline getir. Statik göstergeden çok davranışa odaklan.

6. **Kalıcılık avını yinelemeli yap.** Bir mekanizma bulunduğunda, diğer üç aileyi de (ve mümkünse tüm ASEP'leri) tara; saldırganların yedekli kalıcılık kurduğunu varsay. Temizlik, tek bir kaydı silmek değil, tüm ayak izini haritalamaktır.

Sonuç olarak Windows kalıcılığı, "sihirli tek bir açık" değil, işletim sisteminin meşru otomasyon mekanizmalarının sistematik kötüye kullanımıdır. Her teknik aynı temel gerilimi paylaşır: Windows'un kullanıcıya ve yazılıma sağladığı esneklik ile saldırgana açtığı kapı aynı kapıdır. Bu yüzden savunmanın özü, mekanizmayı kapatmak (ki çoğu zaman mümkün değildir) değil, mekanizmanın *nasıl* ve *ne için* kullanıldığını görünür kılmak, temellemek ve anomaliyi yakalamaktır.
