# SAM Registry Hive Dump — Tespiti

> Saha notu: Bu metin "`reg save hklm\sam` gördün mü alarm bas" seviyesinin çok ötesindedir. Amaç, bu tekniğin gerçek bir SOC'ta neden sıklıkla kaçtığını, hangi zayıf sinyalin hangi başka sinyalle birleşince "yüksek güven" hâline geldiğini ve gece nöbetinde önünüzdeki alarm yığınından bu ihlali nasıl çekip alacağınızı anlatmaktır. SAM dump, LSASS dump'ın gölgesinde kalır ama çok daha sinsidir: LSASS'e dokunmadan, disk üzerindeki bir dosyayı okuyarak yerel yönetici NTLM hash'lerini alır ve EDR'ın "credential access" sezgilerinin çoğunu tetiklemez.

---

## 1. Özet: Saldırı + Naif Tespit

Windows, yerel hesapların parola doğrulayıcılarını (NTLM hash) **SAM** hive'ında tutar; ama SAM tek başına işe yaramaz — hash'ler `SYSTEM` hive'ındaki **bootkey/SysKey** ile şifrelenmiştir. Domain hesaplarının önbelleğe alınmış doğrulayıcıları (MSCache/DCC2) ise `SECURITY` hive'ındadır. Dolayısıyla gerçek bir SAM dump neredeyse her zaman **üç hive'ın da** (SAM + SYSTEM, çoğu zaman + SECURITY) beraber alınmasıdır. Saldırgan bu üçlüyü diske yazar, çevrimdışı bir makineye taşır ve `secretsdump.py`, `samdump2`, `mimikatz lsadump::sam` ile hash'leri çözer. MITRE ATT&CK karşılığı **T1003.002 — OS Credential Dumping: Security Account Manager**.

Bu neden değerli? Kurumların çoğunda yerel yönetici parolası **imaj üzerinden** ortak dağıtılmıştır (LAPS yoksa). Tek bir iş istasyonundan çıkan yerel admin NTLM hash'i, Pass-the-Hash ile yüzlerce makineye lateral hareket demektir. Yani SAM dump, tek bir uçtan tüm filoya yayılan bir domino taşıdır.

Naif tespit herkesin bildiği kalıptır ve sağlanan gerçek Sigma kuralları da bunun izini taşır:

- **Lazarus Group Activity** (`24c4d154`) kuralındaki `selection_generic`, komut satırında birebir `'reg.exe save hklm\sam %temp%\~reg_sam.save'` string'ini arar — yani en klasik `reg save` kalıbı.
- **PowerShell SAM Copy** (`1af57a4b`), gölge kopya (shadow copy) yolundan SAM okumayı hedefler: `CommandLine|contains|all` ile hem `'\HarddiskVolumeShadowCopy'` hem `'System32\config\sam'`, artı bir kopyalama fiili (`'Copy-Item'`, `'cp $_.'`, `'copy $_.'`, `'.File]::Copy('`). Bu, HiveNightmare/SeriousSAM (CVE-2021-36934) sonrası ACL'lerin bozuk olduğu shadow copy'lerden SAM sızdırma davranışını yakalar.
- **Suspicious SYSTEM User Process Creation** (`2617e7ed`), SAM'e özel değil ama SYSTEM bağlamında (`IntegrityLevel: 'System'` veya `'S-1-16-16384'`, `User|contains: 'AUTHORI'/'AUTORI'`) çalışan şüpheli araç/parametreleri yakalayan geniş bir ağdır; SAM dump sıklıkla SYSTEM olarak yapıldığı için bu kural dolaylı bir tetikleyicidir.
- **Webshell Hacking Activity Patterns** (`4ebc877f`), `w3wp.exe`/`php-cgi.exe`/`nginx.exe`/`httpd.exe` gibi web sunucusu süreçlerinin credential dumping türü çocukları doğurmasını yakalar — SAM dump'ın web shell üzerinden geldiği senaryonun ebeveyn-çocuk imzası.

İşte naif katman bu: string eşleşmesi. Ve tam da bu yüzden yetmez.

---

## 2. Naif Tespit Neden Yetmez

**Kör nokta 1 — `reg save` string imzası kırılgan ve dar.** `24c4d154` kuralı `'reg.exe save hklm\sam %temp%\~reg_sam.save'` gibi **tam bir string** arıyor; bu bir threat-intel imzası, generic bir davranış kuralı değil. Saldırgan çıktı yolunu `%temp%\~reg_sam.save`'den `C:\Users\Public\a.dat`'a çevirdiği an bu kural ölür. Dahası `reg`'in kendisi kolayca gizlenir: `reg save "hklm\sam" out.hiv`, `reg.exe save HKLM\SAM out`, büyük/küçük harf karışımı (`ReG SaVe`), `/y` ile sessiz üzerine yazma, hatta `reg` yerine `reg.exe`'nin kopyalanıp yeniden adlandırılmış hâli. `hklm\sam` alt string'i arayan generic bir kural yazsanız bile — ki daha sağlamdır — saldırgan `HKLM\SAM` yerine kısayol `HKLM\Sam` ya da tırnak/boşluk hileleriyle oynayabilir. String'e bakan her kural, komut satırı obfuscation'ına karşı doğuştan zayıftır.

**Kör nokta 2 — `reg.exe` hiç çalışmayabilir.** SAM dump'ın en olgun yolları `reg.exe` binary'sini hiç başlatmaz. Impacket `secretsdump.py` uzaktan **RemoteRegistry** servisini SMB/`\PIPE\winreg` (MS-RRP protokolü) üzerinden ayağa kaldırır, hive'ları uzaktan okur; hedef makinede `reg.exe` process_creation logu **oluşmaz**. Benzer şekilde `nanodump`, doğrudan `NtSaveKey`/`RegSaveKey` API'lerini kod içinden çağıran araçlar veya bir C2 beacon'ının in-memory modülü, hiçbir zaman komut satırında `save hklm\sam` göstermez. Komut satırına bakan kuralların tamamı bu sınıfı görmez.

**Kör nokta 3 — HiveNightmare tamamen farklı bir imza.** SeriousSAM'de (CVE-2021-36934) mesele "process çalıştırmak" değil, **ayrıcalıksız bir kullanıcının** `C:\Windows\System32\config\SAM` dosyasını `\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1\Windows\System32\config\SAM` yolundan okuyabilmesidir — çünkü shadow copy'lerdeki ACL yanlış yapılandırılmıştı. `1af57a4b` bunu PowerShell `Copy-Item` özelinde yakalar, ama saldırgan aynı okumayı derlenmiş bir exe ile, `python`'la ya da doğrudan `CreateFile` API'siyle yaparsa `Copy-Item`/`cp $_.` string'i hiç görünmez. Kural PowerShell kopyalamaya kilitli; teknik ise API'ye kayabilir.

**Kör nokta 4 — false positive selleri.** `hklm\sam` ve `\config\SAM` gerçek dünyada masum olarak da görülür. Yedekleme yazılımları, sistem imajı alan araçlar (DISM, `wbadmin`), forensic/DFIR takımlarının kendi toplama scriptleri (KAPE, Velociraptor `reg save` yapar!), SCCM/MDT görev sıraları, hatta bazı yazılım envanter ajanları registry hive'larına dokunur. `SYSTEM` bağlamında (`2617e7ed`) çalışan process sayısı bir sunucuda binlercedir — Windows'un neredeyse tüm servisleri SYSTEM'dir. `IntegrityLevel: System` + `User: AUTHORITY` tek başına neredeyse hiçbir şey söylemez; o kural ancak `selection_special`'daki şüpheli imaj/parametre listesiyle daraldığında anlam kazanır. Ham hâliyle açarsanız kural günde yüzlerce olay üretir ve iki hafta içinde susturulur.

Özet: `reg save` imzası dar ve gizlemeye açık, API tabanlı dump görünmez, HiveNightmare farklı bir yol, SYSTEM bağlamı ise gürültü denizi. Hiçbiri tek başına yüksek güven değildir. Değer, bunları **birbirine bağlamakta** ve "hangi hive'lar birlikte, hangi sırayla, kim tarafından" sorusunu sormakta.

---

## 3. Korelasyon Zinciri (asıl değer)

Tek bir `reg save hklm\sam` çağrısı zayıf sinyaldir. Onu yüksek güvene çeviren şey, **SAM dump'ın asla tek başına yapılmaması** gerçeğidir. Hash çözmek için SAM tek başına işe yaramaz — SysKey `SYSTEM` hive'ındadır. Bu, saldırganın fiziği gereği bize üçlü bir imza bırakması demektir. Üç ayrı senaryo için üç zincir kuruyorum.

### Zincir A — Klasik yerel dump (`reg save` üçlemesi)

**A1 — Hive üçlemesi, kısa pencere:** 30-90 saniyelik bir pencerede aynı host'ta, çoğu zaman aynı süreç ağacında arka arkaya:
`reg save hklm\sam ...` **+** `reg save hklm\system ...` **+** (sıklıkla) `reg save hklm\security ...`.
Bunların **tek tek** her biri gürültü olabilir — bir yedekleme ajanı tek bir hive'a dokunabilir. Ama **SAM ile SYSTEM'in aynı dakikada, aynı ebeveynden** kaydedilmesi neredeyse patognomoniktir; çünkü meşru hiçbir iş akışı "önce SAM sonra hemen SYSTEM"i bu sırayla, bu ikilikte istemez. Korelasyon anahtarı: `host + parent_process_guid`, pencere 120 sn, koşul "farklı iki hive adı".

**A2 — Anormal ebeveyn/bağlam:** Bu `reg save` demetini kim doğurdu? Meşru bağlamda ebeveyn bir yedekleme servisi ya da yönetici bir bakım scriptidir. İhlalde ebeveyn genellikle `cmd.exe` → daha yukarıda `powershell.exe`, `wscript.exe`, bir Office ürünü, `w3wp.exe`/`php-cgi.exe` (web shell — bkz. `4ebc877f`), ya da `%TEMP%`/`AppData`/`C:\Users\Public` altındaki imzasız bir binary'dir. Süreç ağacında "explorer → cmd → reg" el ile çalışan bir yöneticiyi düşündürür; "w3wp → cmd → reg" ise bir web shell'dir ve bağlam tek başına kararı değiştirir.

**A3 — Çıktının taşınması (exfil/staging):** `reg save` çıktısı bir dosyadır; saldırgan onu çevrimdışı çözmek için taşımak zorundadır. Kısa süre sonra aynı yoldaki `.hiv`/`.save`/`.dat` dosyasının bir arşive (`.zip`, `.7z`, `.cab`) konması, SMB ile başka host'a kopyalanması (`copy \\host\c$`), ya da bir C2 kanalından yüklenmesi. `reg save` + kısa pencerede `SAM`/`SYSTEM` byte imzalı dosyanın ağa çıkması = doğrulanmış hırsızlık.

**Yüksek güven kararı:** `A1 (SAM+SYSTEM aynı pencerede) + A2 (anormal ebeveyn) = kesin dump girişimi`. `+ A3 (çıktı staging/exfil)` eklenirse bu artık girişim değil, **tamamlanmış hırsızlıktır** ve etkilenen tüm yerel hesapların parolası yakılmalıdır. A1 tek başına yüksek öncelikli ticket; A1+A2 çağrı-uyandır (page).

### Zincir B — Uzaktan dump (secretsdump / RemoteRegistry)

Bu zincir host'ta `reg.exe` üretmez; bu yüzden farklı sinyaller ister.

**B1 — RemoteRegistry servisinin canlanması:** `secretsdump.py`, hedefte durmuş olan **RemoteRegistry** servisini başlatır. Bu, hedef host'ta bir servis durum değişimi bırakır (System log `7036`/`7040`, ya da EDR service-change telemetrisi). Hiçbir yerde çalışmayan RemoteRegistry servisinin aniden başlaması + kısa süre sonra durması, çok güçlü bir zayıf sinyaldir.

**B2 — Ağ bağlamı:** Aynı pencerede kaynak IP'den hedefe **SMB (445)** üzerinden bir oturum, `\PIPE\winreg` named pipe'ına erişim (MS-RRP), ve genellikle önce `ADMIN$`/`IPC$` paylaşımına bağlanma. Windows Security 5145 (network share object access, `winreg` pipe'ı için) ya da Zeek/Suricata SMB günlüğü bunu görür. Anahtar korelasyon: **tek bir kaynak host'un kısa sürede RemoteRegistry + winreg pipe erişimi**.

**B3 — Yanal yayılım deseni:** secretsdump nadiren tek hedefe koşulur; genellikle bir dizi host'a arka arkaya. Aynı kaynak hesabın 5-10 dakikada 3+ farklı host'ta aynı RemoteRegistry/winreg desenini üretmesi, kararı "tek makine bakımı"ndan "kimlik toplama kampanyası"na taşır.

**Yüksek güven kararı:** `B1 (RemoteRegistry canlanma) + B2 (aynı kaynaktan winreg pipe/SMB) = uzaktan SAM dump`. `+ B3 (çoklu host)` = aktif lateral kimlik hasadı, hemen kaynak hesabı devre dışı bırak.

### Zincir C — HiveNightmare / SeriousSAM (privilege escalation + SAM)

**C1 — Ayrıcalıksız bağlamdan shadow copy'ye SAM okuma:** `1af57a4b` kuralının kalbi budur — `\HarddiskVolumeShadowCopy` + `System32\config\sam` + kopyalama fiili. Kritik ayrım: bu okuma **medium integrity / normal kullanıcı** bağlamında oluyorsa, bu bir privilege escalation girişimidir (kullanıcı SYSTEM olmadan SAM'e ulaşıyor). SYSTEM bağlamındaki `reg save` "zaten admin'im" der; HiveNightmare "henüz admin değilim ama olacağım" der.

**C2 — Shadow copy varlığı ön koşulu:** SeriousSAM ancak sistemde en az bir VSS shadow copy varsa çalışır. Ortamınızda System Restore/VSS aktifse, `create shadow` görmeden doğrudan mevcut snapshot'tan okuma yapılabilir. Bu yüzden C1'i, o host'ta shadow copy'lerin varlığıyla ve yakın zamanda yama (KB) durumuyla birlikte değerlendirin.

**C3 — Sonuç: yeni yerel admin / PtH:** Başarılı HiveNightmare'i çözen saldırgan yerel admin hash'ini alır; kısa süre sonra aynı host'ta ayrıcalık yükselmesi belirtileri (SYSTEM olarak yeni process, yeni yerel hesap — bkz. account-manipulation) ya da o hash'le başka host'a PtH görünür.

**Bunu Google tek sayfada vermez** çünkü makaleler ya sadece `reg save`'i, ya sadece secretsdump'ı, ya sadece HiveNightmare'i anlatır. Üçünün **farklı zincirler** olduğunu — birinin SYSTEM bağlamında disk yazması, ikincisinin ağ üzerinden pipe, üçüncüsünün ayrıcalıksız shadow-copy okuması olduğunu — ve her birinin farklı ikinci-derece sinyalle doğrulandığını bir arada görmek saha tecrübesidir. Ortak payda ise fizik yasası: **hash çözmek için SYSTEM hive'ı da lazım.** Hangi zincir olursa olsun, SAM'in yanında SYSTEM'i arayın.

---

## 4. False Positive Gerçeği ve Triage Yargısı

SAM dump kuralları, açıldığında en çok "bu meşru muydu?" sorusuyla boğar. İşte gerçek FP kaynakları ve analistin öncelik sırası.

**Meşru `reg save hklm\...` üreticileri:**
- **DFIR/forensic toplama:** KAPE, Velociraptor, CyLR, hatta manuel IR — bunlar bilinçli olarak SAM/SYSTEM/SECURITY'yi kaydeder. Kendi mavi takımınız gece yarısı bir triage koştuğunda kendi kuralınızı tetikler. (İronik ama çok yaygın.)
- **Yedekleme & imajlama:** Windows Server Backup, bazı sistem klonlama araçları, MDT/SCCM görev sıraları hive'lara dokunur.
- **Yönetici bakım scriptleri:** Registry yedeği alan eski usul admin batch'leri.

**Meşru shadow-copy + SAM erişimi:**
- Yedekleme ajanları VSS snapshot'ından tüm diski okur; yol içinde `config\SAM` de vardır. Ama bunlar `1af57a4b`'nin aradığı `Copy-Item`/`cp $_.` kalıbını değil, kendi API'lerini kullanır — bu yüzden PowerShell-özel kural aslında oldukça temizdir. FP'yi asıl üreten, IR ekibinin PowerShell one-liner'larıdır.

**Meşru RemoteRegistry:**
- Bazı envanter/uyumluluk tarayıcıları (SCCM client, vuln scanner'ın authenticated modülü) uzaktan registry okur. Ama bunlar genellikle SAM/SYSTEM hive'larını **kaydetmez**, belirli anahtarları sorgular. secretsdump'ı ayıran, hive'ın **tamamının** okunması ve RemoteRegistry'nin **başlatılıp durdurulmasıdır.**

**Analistin triage öncelik sırası (gece 03:00 yargısı):**

1. **Önce hive çokluğuna bak.** Tek başına `reg save hklm\system` mi, yoksa SAM+SYSTEM birlikte mi? Tek SYSTEM büyük ihtimalle gürültü; SAM+SYSTEM ikilisi çok daha kötü. **En hızlı ayrıştırıcı budur.**
2. **Ebeveyn zincirini çek.** `explorer → cmd` (interaktif yönetici, muhtemelen meşru ya da bilinen IR) mi, yoksa `w3wp/powershell/wscript → cmd` (otomatik/istismar) mı? Ebeveyn `services.exe` altındaki bilinen bir yedekleme servisi mi?
3. **Aktörü tanı.** Çalıştıran hesap bir hizmet hesabı mı, bilinen bir admin mi, yoksa standart bir kullanıcı mı? Standart kullanıcının SAM'e dokunması çok daha ciddidir (privesc kokusu).
4. **Değişiklik penceresine bak.** Onaylı bir bakım/IR penceresi var mı? Kurumsal change ticket ya da IR run defteri bununla örtüşüyor mu?
5. **Çıktının kaderini izle.** Kaydedilen dosya nereye gitti — silindi mi, arşivlendi mi, ağa mı çıktı? Exfil belirtisi triage'ı "araştır"dan "olay"a taşır.
6. **Host değerini tart.** Bir DC ya da PAW (privileged access workstation) üzerindeyse eşik düşer; sıradan bir kiosk'ta biraz nefes alanı vardır.

Pratik kural: **SAM+SYSTEM aynı pencerede + non-backup ebeveyn** görürseniz, meşru bir açıklama kanıtlanana kadar bunu ihlal varsayın. Tersi değil. Yerel hash sızıntısının maliyeti (tüm filoda PtH) o kadar yüksektir ki yanlış-pozitif tarafında hata yapmak ucuzdur.

---

## 5. Kaçınma → Karşı-Tespit

Saldırganların dokümante kuralları atlatmak için yaptıkları ve bizim ikinci-derece karşı hamlelerimiz.

**Kaçınma 1 — `reg.exe`'yi hiç kullanmamak (API dump).** `nanodump`, özel loader'lar veya bir beacon `RegSaveKeyEx`/`NtSaveKey` API'lerini doğrudan çağırır. Komut satırı temizdir.
→ **Karşı-tespit:** API tabanlı hive kaydı bile diske dosya yazar. Dosya oluşturma telemetrisinde (Sysmon Event ID 11) `config\SAM` içeriğine sahip bir dosyanın **beklenmedik bir yola** (`%TEMP%`, `Public`, `AppData`) yazılmasını izleyin. Daha da iyisi: hive dosyalarının ilk byte'ları `regf` sihirli imzasını taşır — bir DLP/dosya-tipi tespiti, uzantısı ne olursa olsun `regf` başlıklı dosyanın ağa çıkmasını yakalayabilir. Ayrıca `SeBackupPrivilege`/`SeRestorePrivilege`'ın olağandışı bir process tarafından etkinleştirilmesi (Event 4673/4674) hive okumanın habercisidir.

**Kaçınma 2 — Komut satırı obfuscation.** `reg save`'i çevre değişkenleri, `^` kaçışları, tırnak parçalama (`re"g" sa"ve"`), ya da Base64-encoded PowerShell içine gömme ile gizlemek.
→ **Karşı-tespit:** String eşleşmesinden **davranışsal ankraja** geçin: "kısa pencerede iki farklı hive adının kaydedilmesi" imzası, komut satırı nasıl gizlenirse gizlensin çıktı yollarında `sam`/`system` alt-string'ini ya da hedef anahtar adını bırakır. PowerShell için ScriptBlock logging (Event 4104) obfuscation'ı çözülmüş hâlde loglar — komut satırı gizli olsa bile 4104 gerçek metni gösterir.

**Kaçınma 3 — Çıktıyı gizli isimlendirme.** `%temp%\~reg_sam.save` yerine `C:\Windows\Temp\update.log` gibi masum bir ad; `24c4d154`'ün tam-string imzasını kör eder.
→ **Karşı-tespit:** Kuralı çıktı adından bağımsızlaştırın. `reg save hklm\sam` **fiilinin varlığı** (hedef `hklm\sam`) önemlidir, hedef dosya adı değil. Generic kural: `Image|endswith: '\reg.exe'` + `CommandLine|contains|all: ['save', 'hklm\sam']`. Bu, çıktı adı ne olursa olsun tutar; asıl obfuscation yüzeyi `hklm\sam` string'idir ve onu da 4104/ScriptBlock ile çift kontrol edin.

**Kaçınma 4 — `reg`'i yeniden adlandırma / kopyalama.** `reg.exe`'yi `svc.exe` olarak kopyalayıp çalıştırmak; `Image|endswith: '\reg.exe'` kuralını kör eder.
→ **Karşı-tespit:** `OriginalFileName` alanına bakın. Sysmon ve Windows process_creation, PE başlığındaki `OriginalFileName`'i loglar; kopyalanmış `svc.exe`'nin `OriginalFileName`'i hâlâ `reg.exe`'dir. `OriginalFileName: 'reg.exe'` AND `Image` ≠ `...\reg.exe` = güçlü kaçınma sinyali (masquerading, T1036).

**Kaçınma 5 — Uzaktan, ajanı olmayan yol.** secretsdump'ı hedefte hiç binary bırakmadan, tamamen ağ üzerinden koşmak.
→ **Karşı-tespit:** Host telemetrisi zayıfsa **ağa** düşün. RemoteRegistry servis-durum değişimi + `\PIPE\winreg` erişimi + `ADMIN$` bağlantısı, kaynak host'a geri izlenebilir. Bir DC'de bu, DCSync değildir ama aynı derecede ciddi bir yanal kimlik toplamadır — ağ IDS/NDR ve Windows 5145 buranın gözüdür.

Ana fikir: dokümante Sigma kuralları **string** katmanında yaşar; olgun saldırgan **API/ağ** katmanına iner. Karşı-tespit, savunmayı komut satırından **dosya oluşturma + ayrıcalık etkinleştirme + servis değişimi + ağ pipe** katmanlarına yaymaktır. Tek bir katmana yaslanan tespit, tek bir kaçınmayla düşer.

---

## 6. SIEM / Saha Gerçeği

**Alan eşlemesi (field mapping) — kuralları gerçek loglara oturtmak.** Sağlanan Sigma kuralları `logsource: category: process_creation` ve `CommandLine`, `Image`, `ParentImage`, `IntegrityLevel`, `User`, `OriginalFileName` alanlarını kullanır. Bunlar soyut Sigma alanlarıdır; sahada nereye düştüklerini bilmezseniz kural yazamazsınız:

- **Sysmon Event ID 1** (process create): `CommandLine`, `Image`, `ParentImage`, `IntegrityLevel`, `User`, `OriginalFileName`, `ParentProcessGuid` doğrudan gelir. `2617e7ed`'in aradığı `IntegrityLevel: 'System'` ve `User|contains: 'AUTHORI'` Sysmon'da birebir vardır. **Bu kural ailesi Sysmon'la yaşar.**
- **Windows Security Event ID 4688** (varsayılan): `New Process Name` (=Image), `Creator Process Name` (=ParentImage) var; ama **`CommandLine` VARSAYILAN OLARAK YOKTUR.** "Include command line in process creation events" GPO ayarını (Audit Process Creation + `ProcessCreationIncludeCmdLine_Enabled`) açmadıysanız, `reg save hklm\sam`'in komut satırını hiç görmezsiniz — kural sessizce boştur. Ayrıca 4688'de `IntegrityLevel` ve `OriginalFileName` **yoktur**. Yani `1af57a4b` ve `24c4d154` gibi CommandLine'a dayalı kuralları 4688 ile besleyemezsiniz; Sysmon şart.

**Varsayılan loglanmayanlar — sessiz kör noktalar:**
- **PowerShell ScriptBlock (4104)** varsayılan kapalı; açmadıysanız `1af57a4b`'nin PowerShell kopyalamasını obfuscation altında kaçırırsınız.
- **RemoteRegistry / winreg pipe erişimi (5145)** için "Detailed File Share" denetimi varsayılan kapalıdır; secretsdump'ın ağ ayağını görmek istiyorsanız açmalısınız.
- **Ayrıcalık etkinleştirme (4673/4674, SeBackupPrivilege)** çok gürültülüdür ve genelde toplanmaz; ama API-tabanlı hive dump'ın nadir güvenilir sinyalidir.
- **Sysmon FileCreate (Event 11)** ajan yapılandırmanızda `config\SAM` yollarını kapsamıyorsa hive yazımını göremezsiniz.

**Platform farkları:**
- **Splunk:** `reg save` üçlemesi korelasyonu `transaction`/`streamstats` ile pencere içinde yapılır. Tipik yaklaşım: `Sysmon EventCode=1 (Image=reg.exe CommandLine="*save*hklm\\*")` üzerinde `streamstats` ile `parent_process_guid` başına farklı hive sayısını sayıp `where distinct_hives>=2`. Ham CIM eşlemesinde `CommandLine` → `Processes.process`, `ParentImage` → `Processes.parent_process`. Backslash kaçışı (`hklm\\sam`) Splunk regex'inde klasik tökezleme noktasıdır.
- **Microsoft Sentinel / Defender:** `DeviceProcessEvents` tablosu; `ProcessCommandLine`, `FileName`, `InitiatingProcessFileName`, `ProcessIntegrityLevel`. KQL'de pencere korelasyonu için `summarize make_set(ProcessCommandLine) by DeviceId, InitiatingProcessId, bin(TimeGenerated, 2m)` sonra SAM ve SYSTEM'in ikisinin de sette olduğunu kontrol. Defender'ın kendi "Sensitive credential memory read" ve SAM-erişim analitikleri LSASS'e odaklıdır; SAM hive dump için kendi kuralınızı yazmanız gerekir — hazır gelmez.
- **Elastic:** ECS eşlemesi `process.command_line`, `process.parent.name`, `process.pe.original_file_name`, `user.name`. EQL sequence bu iş için idealdir: `sequence by process.parent.entity_id with maxspan=2m [process where ... "hklm\\sam"] [process where ... "hklm\\system"]` — EQL'in `sequence by ... maxspan` yapısı A1 zincirini neredeyse birebir ifade eder ve platformlar içinde en temiz korelasyon dilidir.

**Tuning yargısı — kuralı yaşatmak:**
1. `reg save` kuralını **çıktı adından bağımsız** (generic `save`+`hklm\sam`), ama **hive çokluğu** ile daraltarak yazın; tek-hive'ı düşük şiddet (bilgi), SAM+SYSTEM ikilisini yüksek şiddet yapın. Bu tek hamle FP'yi 10 kat düşürür.
2. **Bilinen IR/yedekleme araçlarını host+araç bazında allowlist'leyin**, global değil. KAPE'yi tüm ortamda beyaza almak, saldırganın KAPE'yi taklit etmesine kapı açar; yalnızca IR jump-box'larından geleni beyaza alın.
3. `2617e7ed`'i (SYSTEM user) **tek başına SAM tespiti sanmayın**; o geniş bir ağdır, ancak `selection_special` imaj listesiyle daraldığında ve SAM sinyaliyle korele edildiğinde değerlidir.
4. **Web shell ebeveyni** (`4ebc877f` — `w3wp`/`php-cgi` → `cmd`/`reg`) SAM dump'la kesişirse eşiği tavana çekin; internete bakan bir sunucudan gelen SAM dump neredeyse kesin ihlaldir.
5. Uzaktan yol için host telemetrisine güvenmeyin; **RemoteRegistry servis-durum + 5145 winreg** kuyruğunu ayrı besleyin ve kaynak host'a göre gruplayın.

Son söz: SAM dump, LSASS dump kadar "havalı" değildir ama daha tehlikelidir; çünkü daha sessizdir, EDR'ın credential-memory sezgilerini tetiklemez ve ürettiği yerel admin hash'i doğrudan filo-çapında PtH demektir. Onu yakalamanın anahtarı tek bir string değil, **fiziği**: hash çözmek için SAM ve SYSTEM birlikte lazım — o ikiliyi, kısa pencerede, anormal bir ebeveynin altında ararsanız, saldırganın nasıl gizlerse gizlesin bırakmak zorunda olduğu izi yakalarsınız.
