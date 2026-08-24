# Token Impersonation (Potato Ailesi) — Tespiti

> Saha notu. Bu metin "Potato nedir" anlatmaz; Potato ailesini SIEM'de gerçekten nasıl yakalarsın, naif kuralın neden ilk hafta çöktüğünü ve analistin masasında hangi sinyali önce açtığını anlatır. 15 yıllık SOC refleksiyle yazıldı.

---

## 1. Özet: saldırı + naif tespit (kısa)

Potato ailesi (JuicyPotato, RoguePotato, RottenPotato, PrintSpoofer, EfsPotato, CoercedPotato, DiagTrackEoP, GodPotato, SharpEfsPotato...) tek bir amaca hizmet eder: elinde `SeImpersonatePrivilege` veya `SeAssignPrimaryTokenPrivilege` olan bir hesap (tipik olarak `IIS APPPOOL`, `MSSQLSERVER`, `NT AUTHORITY\NETWORK SERVICE`, `LOCAL SERVICE`) bir Windows yetki-yükseltme (privilege escalation) tekniğiyle `NT AUTHORITY\SYSTEM` token'ını taklit eder (impersonation). Web shell'den veya bir servis hesabından SYSTEM'e sıçramanın en yaygın yoludur.

Mekanizmanın kalbi hep aynıdır: saldırgan bir **named pipe** (adlandırılmış boru) veya RPC/COM yolu üzerinden ayrıcalıklı bir Windows servisini kendisine kimlik doğrulamaya (authenticate) **zorlar** (coercion), gelen SYSTEM token'ını yakalar, `ImpersonateNamedPipeClient` ile taklit eder ve o token'la yeni bir süreç (process) başlatır.

**Naif tespit** genelde şu üçünden biridir:
- Antivirüs imza uyarısı: `HKTL`, `HTOOL`, `ATK/` gibi başlıklarla `HackTool` yakalamak (`Antivirus - Hacktool Signature`).
- Sabit named pipe adı avlamak (`\\.\pipe\RoguePotato`, `EfsPotato` deseni, CoercedPotato pipe deseni, DiagTrackEoP default pipe).
- `whoami /priv` veya `SeImpersonate` string'i geçen komut satırını yakalamak.

Bunların hepsi doğru sinyaldir; ama tek başına hiçbiri "olay" değildir. Değer, bunları **bağlamak** ve tespitin **nerede bozulduğunu** bilmektir.

Neden bu aile bu kadar önemli: kurumsal iç ağda ilk erişim (initial access) çoğu zaman düşük ayrıcalıklı bir servis hesabıyla başlar — bir SQL enjeksiyonundan `xp_cmdshell`, bir deserialization açığından `w3wp.exe`, bir Tomcat/JBoss RCE'sinden servis bağlamı. Bu hesapların hemen hepsi tarihsel bir Windows tasarım tercihi yüzünden `SeImpersonatePrivilege` taşır. Yani saldırganın elindeki "yarım erişim", Potato ile tek adımda tam SYSTEM'e döner. Bir yatay hareket (lateral movement) veya credential dump aşamasından **önce** gelen bu sıçrama, saldırı zincirinin en dar boğazıdır — ve bu yüzden savunmacı için en değerli tespit noktalarından biridir. Burayı kaçırırsan, saldırgan artık host üzerinde SYSTEM'dir ve sonraki her adımı (LSASS dump, servis kurulumu, kalıcılık) meşru bir yönetici gibi görünür.

---

## 2. Naif tespit neden yetmez

### Kör nokta 1: Sabit pipe adı = derlenmiş binary'ye bağımlılık
`HackTool - EfsPotato Named Pipe Creation` (`637f689e-...`), `HackTool - CoercedPotato Named Pipe Creation` (`4d0083b3-...`) ve `HackTool - DiagTrackEoP Default Named Pipe` (`1f7025a6-...`) kurallarının hepsi tek bir varsayıma yaslanır: saldırgan aracı **default pipe adıyla** kullanacak. Gerçekte bu araçların çoğu kaynak koddan derlenir ve pipe adı tek satırlık bir `#define`'dır. DiagTrackEoP kuralının referansı bile doğrudan koddaki `main.cpp#L22` satırını gösteriyor — yani pipe adı sabit bir string ve saldırganın onu değiştirmesi 10 saniyelik iş. RoguePotato'nun `RoguePotato` pipe'ı, GodPotato'nun rastgele isim üreten yeni sürümleri... Sabit-string tespiti, "aracı hiç değiştirmeden çalıştıran" saldırganı yakalar. Kırmızı takım (red team) ve gerçek saldırganın çoğu bunu değiştirir.

### Kör nokta 2: `logsource` gereksinimi çoğu kurumda karşılanmıyor
Pipe kurallarının hepsi `logsource: category: pipe_created` istiyor ve `definition` alanında açıkça yazıyor: **Sysmon Event ID 17 (Pipe Created) ve 18 (Pipe Connected) loglanmalı.** Standart Windows denetimi (audit) named pipe olaylarını **üretmez**. SwiftOnSecurity sysmon-config'in bazı sürümlerinde pipe kuralları yorumlanmış (comment) veya dar tutulmuştur. Yani kural SIEM'de "aktif" görünür ama besleyen log akmıyordur — sessiz kör nokta. Kuralın kendi `definition`'ı bunu itiraf ediyor: "it is worth verifying". Doğrulamayan SOC, olmayan bir korumaya güvenir.

### Kör nokta 3: AV imzası "engelledim" der, kök nedeni gizler
`Antivirus - Hacktool Signature` kuralının `description`'ı tam da bunu vurguluyor: *"This event must not be ignored just because the AV has blocked the malware."* Saha gerçeği: analist AV'nin "Blocked/Quarantined" dediğini görür, ticket'ı kapatır. Ama Potato zaten **ikinci aşama** araçtır — o binary diske düştüyse ilk erişim (web shell, RCE) çoktan olmuştur. AV `HKTL_Potato` engellese bile saldırgan `SeImpersonate` yetkisiyle oradadır ve LOLBAS ile aynı sonucu üretebilir. AV uyarısı bir **başlangıç**, kapanış değil.

### Atlatma yüzeyi
`SeImpersonate` string'i komut satırında görünmez — araç onu API çağrısıyla kontrol eder. Named pipe adı değiştirilir. Binary yeniden derlenir, imphash değişir (`HackTool Named File Stream Created` kuralı imphash'e yaslanır — yeniden derleme onu kaçırır). PrintSpoofer gibi bazıları named pipe yerine `\pipe\spoolss` üzerinden gider ki bu **meşru** bir pipe'tır.

### False positive selleri
`Antivirus - Hacktool Signature` kuralı `Adfind`, `BloodH`, `SecurityTool` gibi çok geniş imza öbeklerini yakalar. Pentest dönemleri, güvenlik ekibinin kendi araç deposu, EDR'ın kendi test imzaları bu kuralı gürültüye boğar. Filtresiz açılırsa analist alarm yorgunluğuna (alert fatigue) girer.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıftır. Yüksek güven, **farklı kaynaklardan gelen sinyalleri kısa bir zaman penceresinde** birleştirmekle gelir. Potato'nun imzası, süreç ağacında (process tree) ve token'da bıraktığı **anomalidir**: bir servis hesabı aniden SYSTEM gibi davranmaya başlar ve alışılmadık bir çocuk süreç doğurur.

### Somut zincir: Web shell'den SYSTEM'e

**A — Anormal ebeveyn (parent) süreç:** `w3wp.exe` (IIS worker) veya `sqlservr.exe` bir komut yorumlayıcısı doğurur.
```
w3wp.exe  →  cmd.exe / powershell.exe
```
Tek başına: orta değer. IIS'in cmd doğurması bazı uygulamalarda normaldir (kötü ama var). `Sysmon Event ID 1 (Process Creation)`, `ParentImage` = `w3wp.exe`, `Image` = `cmd.exe`.

**B — Kısa pencerede (≤ 30 sn), farklı bağlam: named pipe / token olayı.** Aynı süreç ağacının altında:
- `Sysmon Event ID 17` ile bir pipe oluşur (`PipeName` şüpheli veya `\pipe\spoolss`'a olağandışı bağlantı), **veya**
- `Windows Security Event ID 4624` **Logon Type 9 (NewCredentials)** ya da token manipülasyonu, **veya**
- `Event ID 4672 (Special privileges assigned to new logon)` içinde `SeImpersonatePrivilege` / `SeAssignPrimaryTokenPrivilege`.

Tek başına B: gürültülü. Ama A'nın 30 saniye içinde, aynı `ProcessGuid` soyunda gelmesi bağlamı değiştirir.

**C — Token ihlalinin çıktısı: SYSTEM'e sıçrayan çocuk süreç.** Az önce servis hesabı olan ağaç, birden **`NT AUTHORITY\SYSTEM`** bütünlük/kullanıcı bağlamıyla yeni bir süreç doğurur:
```
w3wp.exe (IIS APPPOOL\DefaultAppPool)
  └─ potato.exe / cmd.exe
       └─ cmd.exe   (User = NT AUTHORITY\SYSTEM)   ← integrity yükseldi
```
`Sysmon Event ID 1`, `User` alanı ebeveynde servis hesabı, çocukta `SYSTEM`. Bu **integrity/user sıçraması** Potato'nun en güvenilir imzasıdır — pipe adına da imphash'e de bağımlı değildir.

**Kural:** `A (w3wp→cmd) + kısa pencere B (SeImpersonate/4672 veya pipe 17) + C (aynı soyda SYSTEM'e user değişimi) = ihlal.` Üçü bir arada = yüksek güven, gerçek pozitif. Bir de üstüne `Antivirus - Hacktool Signature` HKTL uyarısı düşerse → kritik, olay yönetimine.

Bu zinciri Sentinel/Elastic'te kurarken çıpa (anchor) alanın **`ProcessGuid` / süreç soyu** olması şart; yoksa host üzerindeki alakasız olayları yanlışlıkla birleştirirsin.

### İkinci somut zincir: SQL Server → EfsPotato → servis kurulumu
Gerçek bir olayda gördüğün desen şudur:
```
sqlservr.exe (NT SERVICE\MSSQLSERVER)
  └─ cmd.exe   (xp_cmdshell)
       └─ EfsPotato.exe   → \pipe\lsarpc / \pipe\efsrpc coercion
            └─ cmd.exe  (User = NT AUTHORITY\SYSTEM)
                 └─ sc.exe create ... / net user ... / powershell -enc ...
```
- **A:** `Sysmon EID 1`, `ParentImage=sqlservr.exe`, `Image=cmd.exe`. Tek başına düşük değer (DBA scriptleri de üretir), ama `xp_cmdshell` çoğu prod ortamda kapalı olmalı — açıksa zaten anomali.
- **B:** `Sysmon EID 18` (Pipe Connected), `PipeName` içinde `efsrpc`/`lsarpc`'ye servis hesabından beklenmedik bağlantı. `EfsPotato` kuralı (`637f689e`) tam da bu deseni hedefler ama sabit pipe adına bağlıysa kaçırabilir; pipe **hedefine** (efsrpc) bakmak daha dayanıklıdır.
- **C:** `EID 1`, aynı soyda `User` alanı `SYSTEM`'e döner. Hemen ardından **`Windows Security EID 4697` / `System EID 7045`** (yeni servis kurulumu) veya `EID 4720` (kullanıcı oluşturma) gelirse zincir tamamlanır.

Bu zincirde çıpa yine süreç soyu; ama dikkat: `xp_cmdshell` bazen ara `cmd.exe` katmanını atlar ve `sqlservr.exe` doğrudan aracı çağırır. Korelasyonu iki-seviye ebeveyn derinliğine göre değil, `ProcessGuid` zincirine göre kur ki bu varyasyonu kaçırma.

### Zaman penceresi ayarı
`maxspan` seçimi kritik: Potato'nun coercion → impersonation → yeni süreç adımları saniyeler içinde olur. Pencereyi **30 saniye** tutmak dengeli; 5 dakikaya çıkarırsan alakasız olayları toplarsın (FP artar), 5 saniyeye indirirsen yavaş disk/yüklü host'ta gerçek pozitifi kaçırırsın. `w3wp→cmd` (A) ile SYSTEM sıçraması (C) arasındaki gecikme, saldırganın aracı indirip çalıştırma süresine bağlı olduğundan A→C penceresini biraz daha geniş (60 sn), B→C penceresini dar (10 sn) tutmak sahada iyi çalışır.

---

## 4. False positive gerçeği ve triage yargısı

Potato tespitinin FP kaynakları bellidir; analistin işi bunları hızlı elemektir.

- **SCCM / yönetim ajanları:** `SeImpersonate` yetkisiyle çalışan servis hesapları meşru olarak token taklit eder. SCCM, ConfigMgr client, yedekleme ajanları (Veeam, Commvault), antivirüs/EDR servisleri sürekli SYSTEM bağlamında iş yapar.
- **Zafiyet tarayıcıları (scanner):** Nessus/Qualys kimlik-doğrulamalı taramada named pipe ve token olayları üretir.
- **Meşru uygulama havuzları (app pool):** Bazı hatalı yapılandırılmış web uygulamaları normalde de `cmd.exe` doğurur; bu FP değil ama Potato da değildir — bağlamla ayrılır.
- **Kırmızı takım / pentest pencereleri:** Bilinen tarih aralıklarını ve kaynak IP'leri baştan istisna listesine (allowlist) al.

### Analistin öncelik sırası (triage yargısı)
1. **User sıçraması gerçek mi?** Ebeveyn servis hesabı, çocuk SYSTEM mi? Değilse çoğu FP burada elenir.
2. **Ebeveyn bağlamı ne?** `w3wp.exe`, `sqlservr.exe`, `php-cgi.exe` gibi internete bakan bir servis mi? İnternet-yüzeyli servisin altındaki Potato imzası en yüksek önceliktir.
3. **Bu host'ta bu davranış taban çizgisinde (baseline) var mı?** SCCM sunucusunda token taklidi normaldir; bir e-ticaret web sunucusunda değildir. Host rolü, kararı yönlendirir.
4. **Zaman:** Bakım penceresi/patch günü mü? SCCM aktivitesi salkım (cluster) hâlinde gelir; tek bir web sunucusunda izole olay gelmez.
5. **Eşlik eden sinyal:** Aynı host'ta yeni servis kurulumu (`Event ID 7045`), olağandışı dış bağlantı, web shell dosya yazımı var mı? Varsa öncelik en üste çıkar.

Yargı özeti: **İzole, internet-yüzeyli servis hesabından gelen "servis → cmd → SYSTEM" salkımı = P1.** Bakım penceresinde SCCM sunucusundan gelen aynı desen = büyük ihtimalle gürültü, host rolüyle bastır.

---

## 5. Kaçınma → karşı-tespit

Belgelerde geçmeyen atlatmalar ve onların ikinci-derece (second-order) tespiti:

**Atlatma 1 — Pipe adını değiştir.** Saldırgan `EfsPotato`/`RoguePotato` pipe'ını rastgele isimle derler. `637f689e`, `4d0083b3`, `1f7025a6` kuralları kör olur.
**Karşı-tespit:** Pipe **adı** yerine pipe **oluşturan süreç bağlamını** ve **sonucu** (C aşaması) izle. Bir servis hesabının named pipe oluşturup hemen ardından SYSTEM süreç doğurması, pipe adından bağımsızdır. Ayrıca `\pipe\lsarpc`, `\pipe\efsrpc`, `\pipe\spoolss` gibi **meşru RPC pipe'larına** servis hesabından beklenmedik bağlantılar (`Event ID 18`) EFS/RPC coercion'un izidir.

**Atlatma 2 — Yeniden derleme, imphash değişir.** `HackTool Named File Stream Created` (`19b041f6-...`) imphash'e yaslanıyor; kaynaktan derleme onu bozar.
**Karşı-tespit:** Named file stream'in kendisi (`create_stream_hash`, ADS — Alternate Data Stream kullanımı) zaten anomali. Hash'ten bağımsız olarak, servis hesabının ADS'e yazması + SeImpersonate + SYSTEM sıçraması davranışsal çıpadır.

**Atlatma 3 — LOLBAS ile aynı sonuç.** PrintSpoofer meşru `spoolss` pipe'ını kullanır; RPC/COM üzerinden coercion araç binary'si diske düşmeden yapılabilir.
**Karşı-tespit:** Yine C aşaması. Diske binary düşmese de **token/integrity sıçraması** `Event ID 4624 Logon Type 9` veya süreç user değişimi olarak görünür. `Event ID 4672`'de servis hesabına `SeImpersonatePrivilege` atanması + hemen sonra SYSTEM eylemi.

**Atlatma 4 — Süreç enjeksiyonu (T1055) ile ağacı gizle.** CoercedPotato/DiagTrackEoP `attack.t1055` etiketli; token'ı alıp mevcut bir SYSTEM sürecine enjekte ederse yeni "çocuk süreç" görünmeyebilir.
**Karşı-tespit:** `Event ID 8 (CreateRemoteThread)`, `Event ID 10 (ProcessAccess)` — servis hesabından SYSTEM sürecine `PROCESS_ALL_ACCESS`/handle açılışı. Enjeksiyon süreç ağacını kırar ama handle/thread olayı bırakır.

**Atlatma 5 — AV'yi engelle/atlat.** İmza engellemesini kabul edip aracı obfuscate eder.
**Karşı-tespit:** `Antivirus - Hacktool Signature` bloklasa bile onu **kök neden avının başlangıcı** say; aynı host'ta A+B+C zincirini geriye doğru ara.

**Atlatma 6 — Meşru ebeveynin altına gizlen (parent PID spoofing).** Gelişmiş saldırgan `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS` ile yeni SYSTEM sürecini `services.exe` gibi meşru bir ebeveynin altında gösterebilir; böylece A aşaması (`w3wp→cmd`) süreç ağacında görünmez olur.
**Karşı-tespit:** Ebeveyn-çocuk ilişkisi sahtelense de `Sysmon EID 1`'deki `ParentProcessId` ile gerçek yaratıcı arasındaki tutarsızlık, ve daha güvenilir olarak token'ın kaynağı (`EID 4672`/`4624 LogonType 9`) hâlâ orijinal servis hesabına işaret eder. Ayrıca spoof edilen ebeveynin `services.exe` olması ama komut satırının `services.exe`'nin normal davranışına uymaması ikinci sinyaldir. Bu yüzden C aşamasını **yalnızca ebeveyn adına** değil, token soyuna da bağla.

Kısaca karşı-tespit felsefesi: **Atlatılabilir olan pipe adı, imphash, string'dir. Atlatılamayan, tekniğin fiziği olan token/integrity sıçraması ve anormal ebeveyn-çocuk bağlamıdır.** Tespiti ikinciye çıpala.

### MITRE eşlemesi (avı yönlendirmek için)
Kuralların etiketlerinden hareketle: birincil taktik `attack.privilege-escalation`; teknik olarak coercion + token taklidi `attack.t1055` (Process Injection — CoercedPotato, DiagTrackEoP etiketi), token/impersonation davranışı **T1134 (Access Token Manipulation)** ve alt tekniği **T1134.001 (Token Impersonation/Theft)** ile hizalanır. AV imzası kuralı `attack.execution`/`attack.t1204` taşır; ADS kuralı `attack.t1564.004` (NTFS File Attributes ile gizlenme). Avlama planını T1134.001 etrafında kur, T1055 ve T1543 (yeni servis — zincirin C sonrası adımı) ile genişlet.

---

## 6. SIEM / saha gerçeği

### Alan (field) eşlemesi — kaynağı karıştırma
- **Named pipe:** yalnızca **Sysmon** üretir. `Event ID 17` = Pipe Created (`PipeName`, `Image`), `Event ID 18` = Pipe Connected. Sigma `logsource: category: pipe_created` bunlara eşlenir. Windows Security log'unda pipe olayı **yoktur**.
- **Ayrıcalık:** `Windows Security Event ID 4672` (Special privileges — `PrivilegeList` içinde `SeImpersonatePrivilege`, `SeAssignPrimaryTokenPrivilege`). `Event ID 4624` (`LogonType`, özellikle 9 = NewCredentials).
- **Süreç:** Sysmon `Event ID 1` (`ParentImage`, `Image`, `User`, `IntegrityLevel`, `ProcessGuid`, `CommandLine`) — en zengin çıpa burada. Windows `Event ID 4688` de kullanılabilir ama `IntegrityLevel` yoktur ve komut satırı denetimi ayrıca açılmalıdır (`Include command line in process creation events` GPO).
- **AV:** Sigma `logsource: category: antivirus`, `Signature` alanı. Defender'da bu `Microsoft-Windows-Windows Defender/Operational` `Event ID 1116/1117`, threat adı `Signature`'a eşlenir. `HackTool - Hacktool Signature` kuralı `Signature|startswith: 'HKTL','HTOOL','ATK/'...` bekler; kendi AV'nin isimlendirmesini bu alana map ettiğinden emin ol.
- **ADS:** Sysmon `Event ID 15` (`create_stream_hash`), imphash logging config'de açık olmalı.

### Varsayılan loglanmayanlar (en sık tökezleme)
- **Named pipe (17/18) varsayılan KAPALI.** Sysmon yoksa veya config'de pipe bölümü daraltılmışsa `EfsPotato`/`CoercedPotato`/`DiagTrackEoP` kuralları besinsiz kalır. Deploy'dan sonra "bu kuralın son 30 günde hiç log görüp görmediğini" mutlaka doğrula (health check).
- **`4688` komut satırı** varsayılan gelmez; GPO ile açılmalı.
- **`4672`** çok gürültülü diye bazı kurumlar filtreler — o zaman SeImpersonate görünürlüğün gider.
- Sysmon `IntegrityLevel` ve `User` alanları config'e bağlıdır; minimal config'de boş gelebilir, C aşaması çıpan çöker.

### Splunk / Sentinel / Elastic farkı
- **Splunk:** Süreç soyu korelasyonu `transaction` veya `stats ... by ProcessGuid` ile kurulur; A+B+C için tercihen bir data model (`Endpoint.Processes`) üstünde. Pipe olayları Sysmon TA (`Splunk_TA_microsoft_sysmon`) ile normalize edilir — `EventCode=17/18`. Zaman penceresi korelasyonunu `transaction maxspan=30s` ile bağla.
- **Microsoft Sentinel:** Sysmon `Event`/`SecurityEvent` tablolarında; kurumsalda Defender for Endpoint varsa `DeviceProcessEvents`, `DeviceEvents` (ActionType `NamedPipeEvent`) çok daha temiz. Korelasyonu KQL `join`/`union` + `InitiatingProcessId` soyuyla kur. Sentinel'de pipe adı gelmese bile `DeviceProcessEvents`'te ebeveyn-çocuk + `AccountName`/`ProcessIntegrityLevel` ile C aşaması güçlü.
- **Elastic:** Sysmon → `winlogbeat`, `event.code: "17"`. EQL'in **sequence** özelliği bu iş için biçilmiş kaftandır: `sequence by process.entity_id with maxspan=30s [process where parent...] [process where user.name=="SYSTEM"]`. Süreç soyu korelasyonunda EQL sequence, Splunk transaction'dan daha doğrudur.

### Tuning reçetesi (deploy sırası)
1. Önce **C aşamasını** (servis hesabı → SYSTEM sıçraması) düşük gürültülü tek kural olarak aç; host rolüne göre baseline çıkar.
2. SCCM/yedek/EDR servis hesaplarını ve pentest pencerelerini `ParentImage`+`AccountName` bazlı istisnala.
3. Pipe kurallarını (`637f689e`, `4d0083b3`, `1f7025a6`) **düşük öncelikli sinyal** olarak tut; tek başına ticket üretmesin, korelasyona besleme yapsın.
4. `Antivirus - Hacktool Signature`'ı ayrı orta öncelikte tut; HKTL uyarısı geldiğinde otomatik olarak aynı host'ta A+B+C geriye-arama (retro-hunt) tetikle.
5. Ayda bir **log sağlık kontrolü**: her Sigma kuralının son 30 günde besleyen olay görüp görmediğini doğrula — sessiz kör noktayı bu yakalar.

### Örnek avlama sorgusu iskeleti (Elastic EQL — C aşaması çıpalı)
```
sequence by process.entity_id with maxspan=60s
  [ process where process.parent.name in ("w3wp.exe","sqlservr.exe","php-cgi.exe","httpd.exe")
      and process.name in ("cmd.exe","powershell.exe","potato.exe") ]
  [ process where user.name : "*SYSTEM" and process.parent.name != "services.exe" ]
```
Bu iskelet pipe adı içermez — bilerek. Pipe kurallarını ayrı, düşük öncelikli sinyal olarak besleyip bu davranışsal çıpayı yükseltirsin. Sentinel KQL karşılığında `DeviceProcessEvents`'i `InitiatingProcessFileName` (ebeveyn) + `AccountName == "system"` ile `join`'leyip `Timestamp` farkını `< 60s` süzersin.

### Kapasite ve saklama notu
Sysmon `EID 17/18` yüksek hacimlidir; her tarayıcı, her RPC çağrısı pipe olayı üretir. Ham hâlde SIEM'e akıtmak indeksleme maliyetini patlatır. Saha çözümü: pipe olaylarını **kaynakta filtrele** (Sysmon config'de bilinen gürültülü pipe'ları — `\pipe\lsass`, `\pipe\srvsvc` rutin — hariç tut ama `efsrpc`/`spoolss`/`lsarpc`'yi tut), ya da EDR telemetrisi varsa (Defender for Endpoint `DeviceEvents` ActionType `NamedPipeEvent`) onu tercih et; EDR bu olayları zaten normalize ve deduplike eder. Saklama süresini en az 90 gün tut: Potato genelde daha büyük bir ihlalin erken adımıdır ve retro-hunt yaparken A+B+C'yi geriye doğru izlemen gerekir.

**Saha özeti:** Potato tespitinde asıl kuralı pipe adına değil, **süreç soyundaki token/integrity sıçramasına** kur; pipe adı, imphash ve AV imzasını çıpalayıcı değil, güven artırıcı yan sinyal olarak kullan. Loglama tarafında named pipe (Sysmon 17/18) ve komut satırı denetiminin gerçekten aktığını **doğrula** — bu iki sessiz kör nokta, çoğu SOC'un Potato'yu kaçırma nedenidir. Tekniğin fiziği değişmez: düşük ayrıcalıklı bir servis hesabı, saniyeler içinde SYSTEM gibi davranmaya başlar. O sıçramayı gördüğün an, pipe'ın adı ne olursa olsun, elinde bir olay var demektir.
