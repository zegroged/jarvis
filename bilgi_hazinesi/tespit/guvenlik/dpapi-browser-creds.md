# DPAPI ve Tarayıcı Kimlik Bilgisi Hırsızlığı — TESPİTİ

> Saha notu. Bu metin "Event 4769'a bak" seviyesinin altında değil, üstünde konuşur. Amaç tek bir alarmı değil, bir hikâyeyi görmek. Zayıf sinyali yüksek güvenli tespite çevirmek, ve bunu yaparken hem sahte pozitif selini hem de akıllı saldırganın kaçış hamlelerini hesaba katmak.

---

## 1. Özet: saldırı + naif tespit

Modern kırmızı takım ve gerçek suç operasyonlarının en sık, en sessiz ve en kârlı adımlarından biri tarayıcı kimlik bilgisi hırsızlığıdır. Chromium tabanlı tarayıcılar (Chrome, Edge, Brave, Opera) kayıtlı şifreleri `Login Data` adında bir SQLite dosyasında tutar; çerezleri `Cookies` (yeni sürümlerde `Network\Cookies`) dosyasında saklar. Bu dosyalardaki `password_value` ve çerezlerin `encrypted_value` alanları düz metin değildir. Chromium bir AES-256-GCM anahtarı üretir, bu anahtarı `Local State` dosyasının `os_crypt.encrypted_key` alanına yazar, ve o anahtarı **DPAPI** (Data Protection API) ile kullanıcı bağlamında şifreler. Zincir şudur: DPAPI kullanıcı master key → `Local State` içindeki AES anahtarı → `Login Data`/`Cookies` içindeki asıl gizli değer. Saldırgan tüm zinciri çözmek için ya kurbanın oturumunda `CryptUnprotectData` çağırır (yerelde en kolay yol), ya da `masterkey` + kullanıcı parolası/hash'i ile çevrimdışı çözer (Mimikatz `dpapi::masterkey`, `impacket dpapi.py`, SharpDPAPI).

DPAPI'nin kendisi iki katmanlıdır. Kullanıcının master key'leri `%APPDATA%\Microsoft\Protect\<SID>\` altında durur; bunlar da ya kullanıcı parolasının türevinden ya da domain ortamında **DPAPI domain backup key** (`BackupKey`) ile korunur. Domain backup key, DC üzerinde `LSA` gizli anlaşması ile saklanır ve Domain Admin seviyesinde `lsadump::backupkeys` ile çekilebilir. Bu yüzden DPAPI hırsızlığı hem tek makine (yerel) hem de tüm domain (backup key ile herkesin master key'ini çözme) ölçeğinde bir tehdittir; bu ikisini karıştırmamak triyajın temelidir.

Naif tespit herkesin bildiği yerdedir: (a) AV imzası — `PWS`, `Creddump`, `DumpCreds`, `Mimikatz` gibi imzalar (bkz. *Antivirus - Password Dumper Signature*, id `78cc2dd2-...`); (b) Mimikatz anahtar kelimeleri eventlog içinde — `dpapi::masterkey`, `lsadump::`, `sekurlsa::` gibi dizeler (bkz. *Mimikatz Use*, id `06d71506-...`); (c) bilinen hacktool ikili adları — `\secretsdump`, `\dpapi_windows.exe`, `\Certify.exe` process_creation/process_access üzerinden (bkz. *HackTool - Impacket Tools Execution* ve *HackTool - Generic Process Access*). Bu kurallar gerçek ve değerlidir; envanterde mutlaka olmalı. Ama bir SOC lead olarak sana söyleyeceğim şey şu: bu kuralların hepsi **saldırganın aptal olduğunu ve araç adını değiştirmediğini** varsayar. Asıl iş bu varsayım çöktüğünde başlar.

---

## 2. Naif tespit neden yetmez

Yukarıdaki dört kuralın her birinin kör noktasını tek tek açalım, çünkü değer tam olarak burada başlar.

**AV imza kuralı (`78cc2dd2`) sadece "yakalandığında" konuşur.** `Signature|startswith: 'PWS'` mantığı, AV'nin dosyayı zaten bir ailenin bilinen örneği olarak tanıması durumunda tetiklenir. Ama tarayıcı creds çalan modern yükler ya tamamen özel (bespoke) ya da `.NET` reflection / `PowerShell` in-memory çalışan, diske hiç düşmeyen kod parçalarıdır. `CryptUnprotectData` çağrısı meşru bir Windows API'sidir; onu çağıran bir `rundll32` ya da özel bir C# binary'si AV için "şüpheli" değildir. Ayrıca bu kural `logsource: antivirus` — yani AV telemetrisi SIEM'e akmıyorsa (birçok ortamda EDR ayrı, AV konsolu ayrı yaşar ve normalize edilmez) kural hiç ateşlenmez. Kuralın açıklamasındaki asıl uyarı da göz ardı edilir: "AV blokladı diye kapatma, nasıl geldiğine bak." Pratikte L1 analistler AV "blocked/quarantined" gördüğünde ticket'ı kapatır — oysa aynı host'ta iki gün önce bir initial access olabilir.

**Mimikatz keyword kuralı (`06d71506`) string tabanlıdır; string değişir.** `dpapi::masterkey`, `lsadump::` gibi dizeler ancak (a) komut satırına yazıldıysa, (b) bir script bloğu loglandıysa (PowerShell ScriptBlock Logging açıksa), ya da (c) bir hata/handle mesajında geçtiyse görünür. Saldırgan Mimikatz'ı kaynaktan derleyip fonksiyon adlarını değiştirdiğinde, ya da `Invoke-Mimikatz` yerine SharpDPAPI / donut-shellcode / BOF (Beacon Object File) kullandığında bu string'lerin hiçbiri ortaya çıkmaz. DPAPI çözümü zaten Mimikatz gerektirmez — saf `.NET` `ProtectedData.Unprotect` ya da doğrudan `dpapi.dll` P/Invoke ile yapılabilir. Yani bu kural "Mimikatz'ı adıyla çağıran" saldırganı yakalar, tekniği değil.

**Impacket kuralı (`4627c6ae`) dosya adına bakar.** `Image|contains: '\secretsdump'` — saldırgan `secretsdump.exe`'yi `svchost_update.exe` olarak yeniden adlandırdığında kör olur. Kuralın kendi açıklaması bunu itiraf eder: "isimlere veya isimlerin bir kısmına dayanır — false positive'e yol açabilir." Impacket zaten sıklıkla `.py` olarak Linux saldırgan kutusundan çalıştırılır ve hedefte hiç ikili bırakmaz; SMB üzerinden uzaktan `secretsdump` çektiğinde hedef host'ta `Image` adı hiç oluşmaz — sadece ağ ve `4624/4672` logon izleri kalır.

**Generic Process Access kuralı (`d0d2f720`) `SourceImage` adına bağımlıdır.** LSASS'a `process_access` (Sysmon Event ID 10) isteği yapan kaynağın adı `\dpapi_windows.exe`, `\Certify.exe` gibi bilinen listedeyse yakalar. Ama LSASS erişimi DPAPI backup key veya masterkey çözümü için tek yol değil ve saldırgan `GrantedAccess` maskesini düşürerek (ör. `0x1000` yerine minimal erişim) ya da meşru bir process'e inject ederek `SourceImage`'ı `svchost.exe`/`taskmgr.exe` yapabilir. Ayrıca tarayıcı creds hırsızlığının çoğu **LSASS'a hiç dokunmaz** — kullanıcı oturumunda `CryptUnprotectData` çağırmak yeterlidir, LSASS handle'ı gerekmez.

Özet: bu kurallar "isim" ve "imza" katmanında çalışır. Saldırgan bu iki katmanı ücretsiz atlatır. Bunun üzerine bir de FP seli gelir — kuralların çoğu `test`/`experimental` statüsünde ve gerçek ortamda ScriptBlock loglarında `lsadump` geçen bir güvenlik eğitimi dokümanı, bir pentest raporu PDF'i açan çalışan, ya da EDR'ın kendi imza güncellemesi bile bunları tetikleyebilir. Yalnız kural = yalnız gürültü.

---

## 3. Korelasyon zinciri (asıl değer)

Tek başına "biri `Login Data` dosyasına erişti" düşük değerli bir sinyaldir — çünkü tarayıcının kendisi, senkronizasyon servisleri, yedek yazılımı ve antivirüs sürekli bu dosyalara dokunur. Değer, bunu **çok aşamalı bir desene** oturtmakta. Sahada güvenilir bulduğum korelasyon zincirlerini somutlaştırıyorum.

**Zincir A — "Yabancı process, kilitli dosya, ağ çıkışı" (yerel hırsızlık):**
1. **A olayı:** `chrome.exe`/`msedge.exe` **dışında** bir process (`powershell.exe`, `rundll32.exe`, özel bir binary, hatta `python.exe`) `...\User Data\Default\Login Data`, `...\Local State`, ya da `...\Network\Cookies` yolunu **okumak için açar**. Sysmon Event ID 11 (FileCreate değil, burada asıl değer **11 + handle**; pratikte Sysmon 11 kopyalama anını, EDR ise `FileOpen`/`ReadFile`'ı yakalar). Kritik ipucu: Chrome bu dosyaları çalışırken kilitler, bu yüzden saldırganların çoğu önce **dosyayı kopyalar** (`copy`, `esentutl /y`, `WMI`, VSS shadow) — yani `Login Data` → `%TEMP%\ld.tmp` gibi bir kopya olayı.
2. **Kısa süre içinde B:** aynı process ya da çocuğu `Local State` içindeki base64 anahtarı okur **ve** `CryptUnprotectData` / DPAPI API çağrısı yapar. Bunu doğrudan görmek zor (API-level telemetri gerekir); pratik proxy: `dpapi.dll`/`crypt32.dll` yüklemesi olağandışı bir process tarafından (image_load), ya da EDR'ın `Sensitive API` telemetrisi.
3. **Farklı bağlamda C:** aynı host'tan kısa süre sonra bir **ağ çıkışı** — Telegram/Discord API (`api.telegram.org`, `discord.com/api/webhooks`), bir pastebin, bir C2 beacon, ya da alışılmadık bir hedefe HTTPS POST. Stealer'ların imza deseni budur: çal → arşivle (bazen `.zip`/`.7z` `%TEMP%'de) → dışarı gönder.

**A + B + C on dakika içinde, aynı host, Chrome dışı bir process = yüksek güvenli hırsızlık.** Tek başına A gürültü; üçü bir arada neredeyse hep gerçek.

**Zincir B — "Domain ölçekli DPAPI" (backup key hırsızlığı):**
1. Bir host'ta `4672` (Special privileges — SeDebugPrivilege / SeBackupPrivilege) + ardından DC'ye `4624 Type 3` yüksek yetkili logon.
2. DC üzerinde `LSA`/`backupkeys` erişimi: pratikte `4662` (Directory Service Access) ile `BCKUPKEY_*` GUID objelerine `DS-Replication` benzeri erişim, ya da `secretsdump`/`SharpDPAPI backupkey` ağ deseni.
3. Ardından **birden çok kullanıcının** `%APPDATA%\...\Protect\<SID>\` master key dosyalarının toplu okunması / bir dosya paylaşımından çekilmesi.
Bu zincir "tek kullanıcının Chrome'u" değil, "tüm domain kullanıcılarının DPAPI sırları" demektir — severity tavan. `4662` + backup key GUID'i tek başına çok nadir meşru olur; onu master key toplu erişimiyle birleştirmek altın vuruştur.

**Zincir C — "Uzaktan, dosyasız" (Impacket yolu):** Hedef host'ta hiç `Image` yok. Bunun yerine: kaynak host'tan `4624 Type 3` + `5145` (network share `IPC$`/`ADMIN$` detailed file share) + `Login Data`/`ntds`/`SAM` benzeri hedef erişimi + kaynakta `\secretsdump`/`\dpapi_windows.exe`. Burada tespit hedefte değil, **kaynak host'ta ve ağ katmanında**. Naif kural sadece kaynak host'ta ateşlenir; hedefte sessizdir. İkisini `LogonId`/`IpAddress`/`TargetUserName` üzerinden birleştirmek zinciri tamamlar.

Korelasyonun altın kuralı: **process kimliği + dosya hassasiyeti + zamansal yakınlık + çıkış davranışı.** Dördünden en az üçü hizalandığında güven yükselir. Tek sinyal asla ticket açtırmaz; üçlü hiza her zaman açtırır.

---

## 4. False positive gerçeği ve triyaj yargısı

Bu alarm ailesinin FP'leri boldur ve onları tanımayan analist ya boğulur ya da gerçek olayı gürültü sanıp kapatır. Gerçek ortamda bu alarmları **meşru** üreten şeyler:

- **Yedekleme/senkron yazılımı:** Chrome/Edge kendi senkronizasyonu, kurumsal profil yedekleyiciler, `OneDrive Known Folder Move`, Veeam/CrowdStrike/Cohesity gibi ürünlerin agent'ları `User Data` klasörüne meşru erişir. Bunlar `Login Data`'yı da kapsayabilir.
- **EDR/AV'nin kendisi:** Birçok EDR periyodik olarak tarayıcı dosyalarını, `Local State`'i, hatta LSASS'ı **meşru** olarak okur (memory scan, credential theft koruması). CrowdStrike/Defender'ın kendi `MsMpEng.exe`/`CSFalconService.exe` LSASS erişimi klasik FP'dir.
- **Vulnerability scanner ve uyum ajanları:** Tenable/Qualys agent'ları, DLP çözümleri dosya sistemini tarar; `lsadump`/`dpapi` string'leri imza veritabanlarında geçtiği için ScriptBlock/komut satırı kurallarını tetikler.
- **SCCM/Intune ve admin scriptleri:** Yönetim scriptleri toplu profil işlemleri, migrasyon araçları (kullanıcı profili taşırken tarayıcı verisini kopyalar), `USMT` (User State Migration Tool) meşru olarak `Login Data`/`Cookies` kopyalar. Bu, gerçek stealer davranışına dosya-katmanında birebir benzer.
- **Mavi/kırmızı takım eğitimi, pentest artefaktları:** Bir çalışanın açtığı Mimikatz cheat sheet PDF'i, bir güvenlik blog sayfası, `atomic-red-team` test çalıştırması — hepsi `lsadump::`, `sekurlsa` keyword'lerini "içerik" olarak üretir.

**Kıdemli analist gerçek/gürültü ayrımını nasıl yapar?** Sırayla şu yargı adımları:

1. **İlk soru "kim" değil, "kim, hangi imzayla, hangi ata soyuyla":** Process'in **parent chain**'ine bak. `msedge.exe` → `Login Data` = normal. `winword.exe` → `powershell.exe` → `Login Data` = neredeyse hep kötü (makro→stealer). `CSFalconService.exe` → LSASS = FP. Ata soyu tek başına vakaların yarısını çözer.
2. **İmzalı mı, bilinen kurulum yolundan mı?** Meşru yedek/EDR ajanları imzalı ve `Program Files` altındadır. `%TEMP%`, `%APPDATA%\Local\Temp`, `\Users\Public`, `\ProgramData` altından çalışan imzasız bir process aynı dosyaya dokunuyorsa alarm ağırlaşır.
3. **Yalnız mı, zincirin parçası mı?** Bölüm 3'teki A+B+C. Tek dosya erişimi + hiçbir çıkış yok + bilinen ajan = büyük olasılıkla FP. Dosya erişimi + kısa süre sonra Telegram/webhook çıkışı = gerçek.
4. **Çoklu alarmda önce neye bakılır?** **Çıkış (exfil) ve kimlik yükselmesi (privilege) sinyaline.** Sıralama: (a) DC/backup key erişimi (Zincir B) — varsa her şeyi bırak, bu domain-wide; (b) dışarı veri çıkışı olan host — veri çoktan gitmiş olabilir, containment aciliyeti; (c) LSASS/masterkey toplu erişim; (d) en sona, tek başına dosya-okuma alarmları. Yani "en gürültülü kural en çok ateşleyen" değil, "en geri dönülmez sonucu olan" önce.

Pratik bir kural: FP'yi susturmak için **process imzası + yol + parent** üçlüsüyle allowlist yap, asla sadece "process adı"yla. `esentutl.exe` meşru bir Windows aracı ama `esentutl /y Login Data` neredeyse hep kötü niyetli kopyalamadır — aracı değil, argümanı ve hedefi allowlist/blocklist et.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Şimdi kural dokümanlarında yazmayan kısım. Yetkin bir saldırgan naif kuralları nasıl atlatır ve her atlatmanın ikinci-derece tespiti nedir?

**Kaçış 1 — Araç adını değiştirme / kaynaktan derleme.** `secretsdump.exe` → `svc_host.exe`, Mimikatz string'lerini yeniden adlandırma. `Image|contains` ve keyword kurallarını komple bypass eder.
→ *Karşı-tespit:* İsimden davranışa geç. **Dosya yolu + davranış** kuralları: "Chrome dışı herhangi bir process `\User Data\...\Login Data` açtı" (ada bakmaz). LSASS için isim değil `GrantedAccess` mask + `CallTrace`'te `dbghelp.dll`/`MiniDumpWriteDump` sinyali. Davranışsal kural araç adına bağımlı olmadığı için yeniden adlandırma işe yaramaz.

**Kaçış 2 — LSASS'a hiç dokunmama, kullanıcı bağlamında yaşama.** Saldırgan zaten kurbanın oturumundaysa `CryptUnprotectData`'yı doğrudan çağırır; master key gerekmez, LSASS gerekmez. `d0d2f720` ve LSASS-erişim kuralları sessiz.
→ *Karşı-tespit:* Bu senaryoda tek sağlam iz **dosya erişim deseni + exfil**. `Login Data`/`Cookies`/`Local State` üçüne kısa pencerede dokunan Chrome-dışı process. Ayrıca `crypt32.dll`/`dpapi.dll`'i olağandışı process'e image_load. En güvenilir yakalama noktası çıkış (Bölüm 6'daki ağ tuning'i).

**Kaçış 3 — Meşru araca sığınma (LOLBin) ve dosya kopyalama.** `esentutl /y`, `copy`, `robocopy`, `WMI`, `VSS`/`vssadmin create shadow` ile kilitli dosyayı kopyalayıp çevrimdışı çözme. Hiçbir "hacktool" adı geçmez.
→ *Karşı-tespit:* **Argüman-hedef** kuralları. `esentutl.exe` komut satırında `Login Data`/`Cookies`/`ntds.dit` hedefi; `vssadmin`/`wmic shadowcopy` çağrısı ardından `Protect\<SID>` ya da tarayıcı klasörüne erişim; `\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy` yol deseni. Bunlar meşru araçlarla yapılsa bile hedef+argüman kombinasyonu nadirdir.

**Kaçış 4 — Domain backup key ile "temiz" çözüm.** Domain Admin ele geçirilince `lsadump::backupkeys` ile backup key alınır; artık **hiçbir kullanıcının parolası gerekmeden** tüm master key'ler çözülür ve bu **çevrimdışı**, kurban makinelerinden uzakta yapılır. Endpoint kuralları hiç ateşlenmez.
→ *Karşı-tespit:* Tespit noktası endpoint değil, **DC ve AD katmanı**. `4662` üzerinde `BCKUPKEY_P Secret`/`BCKUPKEY_PREFERRED` GUID erişimi (bu GUID'ler sabittir, izlenebilir), DC'ye olağandışı `SeBackupPrivilege` kullanımı, DPAPI backup key objelerine erişim. Bu, "önleyemediğin ama görebildiğin" klasik bir yerdir — backup key'e meşru erişim son derece nadir olduğu için düşük-FP, yüksek-değer bir kural.

**Kaçış 5 — Çıkışı gizleme.** Exfil'i meşru bulut servisine (OneDrive, GitHub, Google Drive, Telegram) sığdırma; DNS tünelleme; küçük parçalara bölme.
→ *Karşı-tespit:* Host içi zinciri (dosya erişimi) çıkış olmadan da yakalayacak şekilde tut — çıkışa bağımlı kalma. Ama çıkış tarafında: yeni process'in **ilk kez** bir bulut/mesajlaşma API'sine gitmesi + kısa süre önce tarayıcı dosyası okuması korelasyonu. Beacon için JA3/JA4 ve düzenli aralık (beaconing) analizi.

Genel ilke: her isim/imza tabanlı kaçış, bir davranış/hedef/zaman tabanlı ikinci-derece kuralla karşılanır. Saldırgan aracı değiştirebilir ama **DPAPI zincirinin fiziği**ni değiştiremez — `Local State` okunmalı, gizli değer çözülmeli, veri çıkmalı. Tespiti bu değişmez fiziğe demirle, araç adına değil.

---

## 6. SIEM / saha gerçeği

Kural yazmak kolay; kuralın gerçekten ateşlenmesi için doğru logun akıyor olması lazım. Sahada tökezleten yerler:

**Varsayılan loglanmayanlar — audit policy ve Sysmon config şart:**
- **Sysmon olmadan dosya-erişim görünmez.** `Login Data`/`Local State` erişimini yakalamak için Sysmon Event ID 11 (FileCreate — kopyalama anı) ve Event ID 10 (ProcessAccess — LSASS) gerekir; hiçbiri Windows'ta varsayılan değildir. Sysmon config'inde bu yolların ve LSASS'ın **dahil edilmiş** olması şart. Birçok ortamda Sysmon var ama config `Login Data`'yı hiç kapsamıyor — kural teknik olarak doğru, telemetri yok, sonuç: sessiz kör nokta.
- **PowerShell ScriptBlock Logging (Event ID 4104) ve Module Logging** kapalıysa `lsadump::`/`dpapi::` keyword kuralı (`06d71506`) çoğu durumda hiç veri görmez. Bu GPO ile açılmalı. Ayrıca AMSI bypass edilirse ScriptBlock da güvenilmez olur.
- **`4662` (Directory Service Access)** DC'de varsayılan olarak tüm objeler için loglanmaz; backup key GUID'lerini görmek için SACL'lerin ilgili AD objelerine konması ya da `Directory Service Access` alt kategorisinin `Success` açılması gerekir. Aksi halde Zincir B'nin en kritik adımı görünmez.
- **LSASS process_access** için EDR ya da Sysmon 10 gerekir; ham Windows Security log'da doğrudan yoktur.

**Field mapping tuzakları (Sigma → gerçek şema):** Sigma kuralları soyut alan adları kullanır; her SIEM'de karşılığı farklıdır ve burada sessiz hatalar olur:
- `Image` / `SourceImage` / `TargetImage`: Sysmon'da bu adlarla gelir; ama **Sentinel**'de `DeviceProcessEvents`/`DeviceImageLoadEvents` içinde `FolderPath`/`InitiatingProcessFolderPath`; **CrowdStrike**'ta `ImageFileName`; **Elastic ECS**'te `process.executable` / `process.parent.executable`. `Image|endswith: '\arubanetsvc.exe'` gibi bir `endswith` mantığı ECS'de `process.name` ile eşleşmeli, aksi halde tam yol vs. isim farkından kural boşa düşer.
- `ImageLoaded` (image_load kuralları, ör. `90ae0469`): Sysmon Event ID 7; Defender/Sentinel'de `DeviceImageLoadEvents`; birçok EDR image_load telemetrisini **varsayılan toplamaz** (gürültülü olduğu için) — DLL sideloading/`crypt32.dll` load kuralların çoğu ortamda ölü doğar.
- `CommandLine`: alan var ama **komut satırı kaydı** (`Include command line in process creation events` GPO / `4688` command line) açık değilse boş gelir. Argüman-tabanlı kuralların (`esentutl /y ...`) tamamı buna bağlı.
- `category: antivirus` (`78cc2dd2`): en oynak kaynak. AV konsolu (Defender, Symantec, TrendMicro) SIEM'e farklı şemalarda akar; `Signature` alanı Defender'da `ThreatName`, başka üründe `Malware Name`. Normalize edilmemişse `Signature|startswith: 'PWS'` hiçbir şey eşleştirmez.

**Splunk vs. Sentinel vs. Elastic farkı:**
- **Splunk:** Sigma → SPL çevirisinde `logsource.category` senin `sourcetype`/`index` yapına bağlı. `process_access` çoğu Splunk ortamında `XmlWinEventLog:Microsoft-Windows-Sysmon/Operational EventCode=10`. Korelasyon zincirlerini `transaction` ya da `stats ... by host` ile zaman penceresinde birleştirmek doğal; ama pahalı, `tstats` ve data model (özellikle CIM `Endpoint`) ile ölçeklemek gerekir.
- **Sentinel (KQL):** `DeviceProcessEvents`, `DeviceFileEvents`, `DeviceImageLoadEvents`, `SecurityEvent` tablolarına dağılmış. Zincir korelasyonu `join`/`union` + `bin(TimeGenerated, 10m)` ile yapılır; ama MDE ham dosya-okuma olaylarını `DeviceFileEvents`'te sınırlı raporlar (her `ReadFile`'ı vermez), bu yüzden "Login Data okundu" doğrudan yerine "kopyalandı/oluşturuldu" üzerinden yakalanır.
- **Elastic:** ECS alan adları en tutarlısı ama Sysmon → ECS pipeline (Winlogbeat/Elastic Agent) doğru maplenmemişse `process.parent.*` alanları boş kalır; parent-chain korelasyonu (Bölüm 4'ün belkemiği) bozulur. EQL `sequence by host.id with maxspan=10m` zincir tespiti için en zarif araçtır.

**Tuning gerçeği:** Bu kural ailesini prod'a koymadan önce mutlaka bir **baseline** çıkar: senin ortamında `Login Data`/`Local State`'e meşru dokunan process'lerin (EDR, yedek ajanı, senkron, SCCM) tam listesini imza+yol+parent ile çıkar ve bunları zincir kurallarının A adımından **hariç tut** — ama exfil (C adımı) tetiklendiğinde hariç tutmayı **geçersiz kıl** (allowlist'i sadece "yalnız dosya erişimi"ne uygula, "erişim + çıkış"a asla). LSASS erişim kuralında EDR'ının kendi servis adını (`CSFalconService.exe`, `MsMpEng.exe`, `SenseIR.exe`) hariç tut yoksa her 5 dakikada bir FP alırsın. Ve unutma: `test`/`experimental` statüsündeki kuralları (yukarıdaki dördünün üçü öyle) doğrudan blocking/high-severity moduna alma — önce gözlem modunda 2-4 hafta baseline topla, FP profilini gör, sonra severity ver. Sahada kuralları yakan şey teknik değil, tuning disiplinsizliğidir.
