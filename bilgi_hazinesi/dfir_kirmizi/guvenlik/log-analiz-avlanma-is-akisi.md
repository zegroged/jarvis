# Log Analizi ve Avlanma İş Akışı — Bir DFIR Lead'in Saha Defteri

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Log analizi ve tehdit avı (threat hunting), olay müdahalesinin "belirsizlik" fazının motorudur. Bir uyarı düştü ya da bir kullanıcı "makinem tuhaf davranıyor" dedi. Elimizde tek bir IOC (indicator of compromise) var, belki hiç yok — sadece bir his. İşimiz bu tek noktadan başlayıp saldırganın tüm izini, giriş noktasından son eyleme kadar rekonstrükte etmek.

DFIR süreç modelinde (hazırlık → tespit → sınırlama → kök neden → toparlanma → dersler) log analizi asıl olarak **tespit ve kök neden** aşamalarında oturur, ama pratikte her aşamayı besler. Sınırlama kararını yanlış logdan alırsan yanlış makineyi izole eder, saldırganın gerçek dayanak noktasını (foothold) açıkta bırakırsın.

Burada kritik bir ayrım var ve acemiler bunu karıştırır:

- **Reaktif analiz (alert-driven):** Bir tetik var, onu doğrular ve genişletirsin. "Bu uyarı gerçek mi, ne kadar yayıldı?"
- **Proaktif avlanma (hypothesis-driven):** Uyarı yok. Bir hipotez kurarsın — "ortamda pass-the-hash yapılıyorsa Windows Event 4624 Type 3 + NTLM + admin hesabı + anormal kaynak IP paterni görürüm" — ve bunu test edecek sorguyu yazarsın.

İyi bir IR lead ikisini de akıcı yapar. Avlanmada Pyramid of Pain'i (David Bianco) aklından çıkarmazsın: hash ve IP avlamak kolay ama saldırgan bunları saniyede değiştirir. TTP (taktik-teknik-prosedür) seviyesinde avlarsan saldırganı gerçekten acıtırsın, çünkü davranışını değiştirmesi pahalıdır. Bu yüzden avın hedefi hep ATT&CK teknik davranışı olmalı, tek bir dosya adı değil.

## 2. Adım-adım İŞ AKIŞI ve KARAR — pro DFIR analisti ne yapar

Bir de sorgu disiplini var. İster Splunk SPL, ister Elastic KQL/EQL, ister Velociraptor VQL yazayım — kötü sorgu binlerce satır gürültü döker, iyi sorgu tek satırda saldırganı gösterir. İki prensibim: (1) **Geniş başla, hızla daralt** — önce zaman penceresi ve host ile kaba filtre, sonra alan bazlı sıkı filtre. (2) **Sayarak avlan** — nadirlik (rarity/stacking) avın en güçlü aletidir. "Tüm ortamda sadece 2 makinede çalışan imzasız binary" listesini çıkarmak, milyon satır logu okumaktan kat kat verimlidir. `stats count by ...` ile frekans dağılımı çıkarır, uzun kuyruğa (long tail) bakarım; kötü şey çoğu zaman az görülendir, çok görülen değil.

### Adım 0: Kapsam ve "kanıt öncelik sırası" (order of volatility) kararı

Sisteme dokunmadan önce iki soru sorarım: (1) Makine hâlâ açık mı ve saldırgan hâlâ aktif olabilir mi? (2) Hangi kanıt en hızlı buharlaşıyor?

RFC 3227'nin uçuculuk sırası pusulamdır: CPU register/cache → RAM (çalışan süreçler, ağ bağlantıları, şifre çözülmüş anahtarlar) → ağ durumu → disk → uzak loglar/arşiv. Yani makine açıksa **önce RAM alınır**, disk imajından önce. Çünkü fileless malware, in-memory C2 beacon, decrypt edilmiş credential'lar diski görmez; makineyi kapatırsan kanıtı kendi elinle yok edersin.

Karar kuralı: **"Pull the plug" mı, canlı triyaj mı?** Ransomware aktif şifreliyorsa ve her saniye dosya kaybediyorsak ağ izolasyonu (kablo çekme değil, switch port/EDR host-isolation) öncelikli. Sinsi bir APT ise ani izolasyon saldırganı ürkütür, kanıt silmeye ya da wiper tetiklemeye iter — burada sessizce genişletirim.

### Adım 1: Hızlı triyaj toplama — KAPE ile

Tam disk imajı (dd/E01) saatler sürer. Ben önce **KAPE (Kroll Artifact Parser and Extractor)** ile hedefli triyaj alırım. `!SANS_Triage` hedef seti ile 10-15 dakikada işin özünü toplarım:

- `$MFT`, `$UsnJrnl:$J` (dosya oluşturma/silme zaman çizelgesi)
- Windows Event Logs (`Security`, `System`, `Application`, `Sysmon/Operational`, `PowerShell/Operational`, `TerminalServices-*`, `WMI-Activity`, `TaskScheduler`)
- Registry hive'ları (`SYSTEM`, `SOFTWARE`, `SAM`, `SECURITY`, `NTUSER.DAT`, `UsrClass.dat`)
- Amcache.hve, SRUM (`SRUDB.dat`), Prefetch, ShimCache
- Tarayıcı geçmişi, `$Recycle.Bin`, jump lists, LNK dosyaları

Uzaktaki bir filoda (100+ makine) tek tek KAPE koşmam — orada **Velociraptor** devreye girer. VQL ile tüm filoya aynı anda "kimde bu registry Run key var?", "kimde bu şüpheli scheduled task var?" diye sorar, sonuçları merkezde toplarım. Velociraptor'ın hunt yeteneği proaktif avlanmanın filo ölçeğindeki karşılığıdır.

### Adım 2: Süper zaman çizelgesi (super timeline) inşası

Bu işin kalbidir. Farklı artefaktları tek bir zaman ekseninde birleştirmeden saldırganın hikâyesini kuramazsın. Araç zinciri:

- **Plaso / log2timeline** → `psort` ile tüm artefaktlardan birleşik timeline (`.plaso` → CSV/Elastic).
- Ya da hedefli gidersem **Eric Zimmerman araçları**: `MFTECmd` ($MFT), `AmcacheParser`, `AppCompatCacheParser` (ShimCache), `PECmd` (Prefetch), `SBECmd` (ShellBags), `LECmd` (LNK), `RECmd` (registry), `EvtxECmd` (event log → normalize edilmiş CSV).
- Görselleştirme ve ekip çalışması için **Timesketch**: timeline'ı yükler, "star" ile önemli olayları işaretler, saga anlatısını ekip arkadaşlarıyla ortak yürütürüm.

Karar mantığı — **pivot noktası bulma:** Elimdeki tek IOC'yi (diyelim şüpheli `svchost.exe` C:\Users\Public altında) timeline'a düşürürüm ve o zaman damgasının ±5 dakikasına bakarım. Bu "olay etrafındaki pencere" tekniği altındır. O pencerede ne var? Hangi process onu doğurdu (parent-child)? Öncesinde bir `winword.exe → cmd.exe → powershell` zinciri mi var (makro ile ilk erişim)? Sonrasında bir 4624 logon başka makineye mi gitti (lateral movement)?

### Adım 3: ATT&CK zincirini geriye ve ileriye örme

Saldırgan prosedürlerini bilmek, hangi logda ne aradığımı belirler. Yukarıdaki atomic teknikleri "avcının gözüyle" çeviriyorum:

**Discovery izleri (T1007 System Service Discovery, T1012 Query Registry):** Saldırgan yeni girdiği makinede etrafı yoklar. Sysmon Event ID 1 (process create) içinde `sc query`, `tasklist /svc`, `net start`, `reg query`, `systeminfo`, `whoami /all` gibi komutların **kısa aralıkla art arda** çalışması klasik keşif imzasıdır. Tek başına `whoami` masumdur; 90 saniye içinde 8 keşif komutu bir insan admin değil, bir playbook'tur. Karar: burayı gördüysem "ilk erişim bundan önce" der, timeline'da geriye giderim.

**Lateral movement (T1021.001 RDP, T1021.002 SMB/Admin Shares):**
- RDP için: Security log 4624 **Logon Type 10** (RemoteInteractive) + `TerminalServices-RemoteConnectionManager/Operational` EID 1149 (bağlantı) + `LocalSessionManager` EID 21/25 (oturum açılış/reconnect). Kaynak IP'ye bakarım — iç ağdan bir iş istasyonundan sunucuya RDP, çoğu ortamda anormaldir.
- SMB/Admin share için: 4624 **Logon Type 3** (Network) + 5140/5145 (share erişimi, `ADMIN$`, `C$`, `IPC$`) + 4672 (özel yetkiler atandı = admin logon). PsExec kullanıldıysa 7045 (yeni servis kuruldu, rastgele isimli servis + `%SYSTEMROOT%` altına atılmış binary) ve Sysmon EID 13 (registry) izleri gelir.

**Pass-the-hash / kimlik hırsızlığı ayrımı:** 4624 Type 3'te `Authentication Package = NTLM` ve `Logon Process = NtLmSsp`, üstelik hesap normalde Kerberos kullanan bir domain hesabıysa — PtH şüphem yükselir. Kerberos anomalileri için 4768/4769 (TGT/TGS) ve encryption type düşüşü (RC4'e downgrade = Kerberoasting/overpass-the-hash sinyali) bakarım.

**Karar kuralı — "gördüm → giderim" örnekleri:**
- 4688/Sysmon-1'de `parent=powershell.exe, child=rundll32.exe` + ağ bağlantısı görürsem → C2 ya da credential dump (comsvcs.dll MiniDump ile LSASS) şüphesiyle Sysmon EID 10'a (process access, `Target=lsass.exe`, `GrantedAccess=0x1410/0x1010`) bakarım.
- Amcache/Prefetch'te bir binary'nin **ilk çalıştırma zamanı** ile olayın başlangıcı örtüşüyorsa → o binary "patient zero" adayı.
- ShimCache/Amcache'te var ama diskte dosya yok → çalıştırılıp silinmiş; anti-forensics ya da normal cleanup. UsnJrnl'de silme kaydını ararım.
- PowerShell `4104` (script block) içinde `-enc`, `FromBase64String`, `IEX (New-Object Net.WebClient).DownloadString`, `-WindowStyle Hidden -NonInteractive` → obfuscated indir-çalıştır. Base64'ü çözer, gerçek payload'ı okurum.
- `4104`/`4103` hiç yoksa ama PowerShell çalıştıysa → saldırgan `powershell -version 2` ile downgrade yapmış olabilir (script block logging'i baypas için). System log'da PowerShell v2 engine yüklenmesi kendisi bir avlanma imzasıdır.

**Log kaynağının güvenilirlik hiyerarşisi.** Aynı olayı birden çok kaynak gösterir ve hepsi eşit güvenilir değildir. Sysmon (doğru yapılandırılmışsa) ham Security 4688'den daha zengindir (hash, parent command-line, image load). Ama saldırgan EDR/Sysmon'u fark edip durdurmuş olabilir; o yüzden bir kaynağın "sustuğu" ana da bakarım — Sysmon servisinin durduğu an (System 7036/7040), saldırganın en aktif olduğu andır çoğu zaman. Çapraz doğrulama şart: registry son yazma zamanı, MFT, event log ve Amcache aynı hikâyeyi anlatmalı; anlatmıyorsa ya timestomp var ya da yanlış okuyorum.

### Adım 4: Bellek analizi — Volatility

Disk yalan söyleyebilir, bellek nadiren söyler. RAM imajı aldıysam **Volatility 3** ile:
- `windows.pslist` / `windows.psscan` (gizli/unlinked process — DKOM ile saklananları psscan yakalar, pslist kaçırır)
- `windows.pstree` (parent-child anomalisi — `services.exe` altında olmayan bir `svchost`)
- `windows.malfind` (RWX, image-backed olmayan enjekte kod bölgeleri)
- `windows.netscan` (aktif/kapanmış C2 bağlantıları)
- `windows.cmdline`, `windows.dlllist`, `windows.handles`
- `windows.svcscan`, `windows.registry.*`

Karar: `malfind` bir process'te enjekte PE bulursa, o bölgeyi dump edip **YARA** ile tararım. Bilinen bir aile mi (Cobalt Strike beacon config, Metasploit stager) yoksa custom mu? YARA kuralı hem bellek hem diskte tekrar avlamak için pivot verir — kanıtı IOC'den davranış/imza seviyesine yükseltirim.

### Adım 5: Doğrulama ve genişletme (scoping)

Tek makinede kök nedeni bulduktan sonra iş bitmez. "Bu davranış başka nerede?" sorusu sınırlamanın (containment) doğruluğunu belirler. YARA kuralımı, bulduğum registry Run key'i, C2 IP'sini, saldırganın kullandığı hesap adını alıp Velociraptor hunt ya da SIEM sorgusu ile tüm filoda ararım. Bir makine izole edip rahatlarsan ve saldırganın 6 makinede daha beacon'ı varsa, yarın geri gelir.

### Adım 6: Persistans avı — geri döneceği kapıları bulmak

Saldırganı temizlemeden önce nereye tutunduğunu bilmem gerekir, yoksa reboot sonrası geri gelir. Kalıcılık (persistence) için sabit bir kontrol listesi yürütürüm ve her birinin log/artefakt karşılığını bilirim:

- **Run/RunOnce anahtarları** (`HKLM\...\CurrentVersion\Run`, `NTUSER.DAT` altındaki kullanıcı hive'ı) → RECmd ile parse, Sysmon EID 13 ile ne zaman yazıldığını görürüm.
- **Scheduled Task** (T1053.005) → `TaskScheduler/Operational` EID 106 (kayıt) / 200 (çalıştı) + `C:\Windows\System32\Tasks\` altındaki XML dosyaları. Rastgele isimli, `%APPDATA%` ya da `Public` altından çalışan bir görev alarm zilidir.
- **Servis** (T1543.003) → System log 7045 (yeni servis) + 7009/7034 (çökme/beklenmedik durma). Binary yolu tırnaksız ve boşluklu mu (unquoted service path)? İsim rastgele mi?
- **WMI event subscription** (T1546.003) → `WMI-Activity/Operational` EID 5861; `__EventFilter` + `__EventConsumer` + `__FilterToConsumerBinding` üçlüsü. En sinsi kalıcılıktır çünkü diskte klasik iz bırakmaz, `OBJECTS.DATA` içinde saklanır.
- **Startup klasörü, logon script, BITS job, DLL search-order hijack, IFEO Debugger** — her biri ayrı bir kapı.

Karar: Bunların hepsini taramadan "temizlendi" raporu yazmam. Autoruns benzeri bir tarama + Amcache/timeline korelasyonu ile saldırganın kurulum zaman damgasının çevresine bakarım — genelde persistans, ilk erişimden dakikalar sonra kurulur ve timeline'da kümelenir.

### Adım 7: Exfiltration ve etki değerlendirmesi

Yasal ve iş açısından en kritik soru çoğu zaman "veri çıktı mı?"dır. SRUM (`SRUDB.dat`) uygulama bazında ağ byte sayacı tutar — bir process gigabyte ölçeğinde upload yaptıysa SRUM'da görünür (`SrumECmd` ile parse). Proxy/firewall loglarında büyük outbound transferler, tanıdık olmayan bulut depolama (mega, anonfiles) hedefleri, DNS tünelleme paterni (anormal uzunlukta ve sıklıkta TXT sorguları) ararım. `$UsnJrnl`'de saldırganın topladığı dosyaları bir arşive (`.7z`, `.rar` — T1560) sıkıştırdığı staging izleri sıklıkla exfil öncesi görünür.

## 3. Kritik dikkat noktaları — delil bütünlüğü ve anti-forensics

**Delil bütünlüğü ve chain of custody:** Her aldığım imajın (RAM, disk, triyaj paketi) topladığım anda SHA-256 hash'ini alır, kayıt altına alırım. Analizi **her zaman kopya üzerinde** yaparım; orijinal write-blocker arkasında ya da salt-okunur mount'ta durur. Kim, ne zaman, neyi, hangi araçla topladı — bu zincir kopmuşsa bulgu mahkemede (ve çoğu zaman iç soruşturmada) çöptür. Windows'ta bir E01 imajını doğrudan Autopsy'ye verir, orijinale asla yazmam.

**Order of volatility'i pratikte çiğnememek:** Acemi refleks "makineyi hemen kapatıp diski al" olur. Bu, RAM'deki tüm fileless kanıtı öldürür. Kural: canlı sistemde **önce uçucu olanı** (RAM, `netstat`, çalışan process listesi, açık handle'lar) topla, sonra diske geç. Ama canlı toplama da sistemi değiştirir (Locard değiş-tokuş prensibi) — hangi aracı çalıştırdığını, ne kadar iz bıraktığını belgele.

**Zaman senkronizasyonu ve UTC:** Farklı loglar farklı saat diliminde ya da saati kaymış olabilir. Timeline'ı **her zaman UTC'ye normalize** ederim. Bir olayı yanlış TZ yüzünden 3 saat kaydırırsan tüm nedensellik zinciri çöker. EvtxECmd ve Plaso UTC çıkarır; ham log okurken kaynağın TZ'sini doğrularım.

**Anti-forensics'e karşı:**
- **Log temizleme:** Security log'da 1102 (audit log cleared) ya da System'de 104 saldırganın en sevdiği kapanış hamlesidir. 1102 gördüğüm an bu bir kaza değil, niyettir — o zaman damgasından önceki her şey şüpheli, USN journal ve VSS (Volume Shadow Copy) ile silinmiş logları kurtarmaya çalışırım.
- **Timestomping (T1070.006):** Saldırgan `$STANDARD_INFORMATION` zaman damgasını değiştirir ama `$FILE_NAME` damgasını değiştirmek daha zordur. MFT'de SI ve FN zamanları tutarsızsa (özellikle SI, FN'den önceyse ya da saniye altı hassasiyet `.0000000` ile bitiyorsa) timestomp şüphesi. `MFTECmd` bunu yan yana verir.
- **Volume Shadow Copy:** Saldırgan sildi diye pes etme; VSS'te dosyanın eski hali, silinmiş loglar, hatta ransomware öncesi temiz kopyalar durabilir.
- **Silinen dosya:** Amcache/ShimCache "çalıştı" der ama disk boş — carving ve UsnJrnl analizi ile kurtarma denerim.

## 4. Gerçek dünya senaryosu — iş akışını yürütmek

**Tetik:** Cuma 02:14'te EDR, bir dosya sunucusunda (`FS01`) `rundll32.exe`'nin dış bir IP'ye bağlanmasına dair düşük güvenli bir uyarı üretti. SOC "muhtemelen false positive" diye geçmiş. Pazartesi masama geldi.

**Adım 1 — Triyaj:** FS01 hâlâ açık. Önce Velociraptor ile RAM imajı + KAPE `!SANS_Triage` topluyorum, hash'liyorum. Makineyi izole etmiyorum çünkü sinsi bir davranış paterni var, saldırganı ürkütmek istemiyorum.

**Adım 2 — Pivot:** EvtxECmd + Plaso ile timeline. `rundll32.exe`'nin bağlantı zamanı 02:14. Sysmon EID 1'de parent'ına bakıyorum: parent `powershell.exe`, onun parent'ı `wmiprvse.exe`. WMI ile uzaktan tetiklenmiş → bu bir lateral movement izi, FS01 muhtemelen ikinci kurban.

**Adım 3 — Geriye örme:** 02:14 penceresinden geriye. Security log 4624 **Type 3, NTLM**, kaynak `WKS-042` (bir muhasebe iş istasyonu), hesap `svc_backup` (bir servis hesabı). Bir muhasebe PC'sinden dosya sunucusuna, gece 2'de, servis hesabıyla NTLM logon — üç ayrı anomali. Öncesinde 5140 ile `ADMIN$` erişimi. Bu, pass-the-hash + WMI exec imzası.

**Adım 4 — WKS-042'ye geç:** Aynı triyajı WKS-042'de alıyorum. Burada Sysmon EID 10: `lsass.exe`'ye `GrantedAccess=0x1410` ile erişim; parent `comsvcs.dll` MiniDump çağrısı → LSASS credential dump (T1003.001). Amcache'te 3 gün önce çalışmış bir `update.exe` (C:\Users\Public), diskte artık yok. UsnJrnl silme kaydı var. VSS'ten kurtarıyorum, YARA ile tarıyorum → Cobalt Strike beacon.

**Adım 5 — İlk erişime kadar:** WKS-042 timeline'ında `update.exe`'nin ilk çalışması, bir `outlook.exe → *.iso mount → update.exe` zincirine bağlanıyor. ISO ekli phishing → HTML smuggling. Patient zero ve giriş vektörü bulundu.

**Adım 6 — Filo taraması:** Cobalt Strike C2 IP'si, beacon YARA kuralı, `svc_backup` hesabının anormal kullanımı — üçünü Velociraptor hunt ile tüm filoda arıyorum. WKS-042 ve FS01 dışında iki sunucuda daha beacon çıkıyor. **Şimdi** dört makineyi eşzamanlı izole ediyorum, `svc_backup` ve etkilenen kullanıcıların parolalarını + KRBTGT'yi (çift kez) resetliyoruz.

**Varılan sonuç:** Phishing (ISO/HTML smuggling) → LSASS dump → PtH → WMI/SMB ile lateral movement → 4 makinede Cobalt Strike. Tek "false positive" uyarı, doğru pivotlandığında tüm kampanyayı açtı. SOC'un gözden kaçırdığı şey uyarının kendisi değil, **etrafındaki bağlamdı**.

## 5. Yaygın tuzaklar ve pro yargısı

**Tuzak 1 — Tek IOC'de takılıp kalmak.** Acemi kötü hash'i bulur, siler, "temizlendi" der. Pro, o hash'i sadece bir pivot noktası olarak görür; asıl soru "bu makineye nasıl geldi ve başka nereye gitti?"dir. Hash saldırganın en kolay değiştireceği şeydir (Pyramid of Pain'in tabanı).

**Tuzak 2 — Timeline'ı UTC'ye normalize etmemek.** Karışık zaman dilimleri nedenselliği ters çevirir; "sonuç, nedenden önce olmuş" gibi görünen saçmalıklar hep TZ hatasıdır.

**Tuzak 3 — Uçucu kanıtı önce diski alacağım diye öldürmek.** Fileless saldırılarda tüm hikâye RAM'dedir. Makineyi düşünmeden kapatan analist kendi davasını yakar.

**Tuzak 4 — Bir logun yokluğunu kanıt yokluğu sanmak.** 1102 (log temizlendi) ya da loglama hiç açık değildiyse, "iz yok, temiz" demek en tehlikeli hatadır. Yokluğun kendisi bir bulgudur. "Absence of evidence is not evidence of absence." Sysmon yoksa 4688 command-line auditing açık mı, PowerShell script block logging (4104) var mı diye bakarım; hiçbiri yoksa bu ortamın görünürlük açığını raporun kök bulgusu yaparım.

**Tuzak 5 — Parent-child bağlamını atlamak.** `powershell.exe` tek başına bir şey söylemez. Ama parent'ı `winword.exe` ya da `wmiprvse.exe` ise bambaşka bir hikâyedir. Süreç ağacını (process tree) kurmadan process adına bakmak, cümleyi görmeden tek kelimeyi okumaktır.

**Tuzak 6 — Normal'i bilmeden anomali avlamak.** "Baseline" olmadan avlanamazsın. Ortamda `PsExec` zaten IT tarafından meşru kullanılıyorsa her PsExec'i kovalamak seni boğar. Pro, önce ortamın normalini öğrenir; anomali normalden sapmadır, mutlak bir listeden değil.

**Tuzak 7 — Bulgusuz sonuç, sonuçsuz bulgu.** Acemi ya ham log dökümü verir (yorum yok) ya da kanıtsız "hacklenmişsiniz" der. Değer, her iddiayı bir artefakta bağlamakta: "FS01'e 02:14'te WKS-042'den `svc_backup` ile NTLM logon oldu (Security 4624, Type 3), aynı hesap normalde interaktif oturum açmaz — bu lateral movement'tir." İddia + artefakt + neden anormal olduğu. Üçü bir arada değilse rapor eksiktir.

**Son söz — yargı, aracın değil analistin işidir.** KAPE, Volatility, Plaso hepsi harika; ama hangi pencereye bakacağını, hangi anomalinin gerçek hangisinin gürültü olduğunu, saldırganı ne zaman ürküteceğini araç söylemez. İyi bir avcı, saldırgan gibi düşünür: "Ben bu makineye girsem sıradaki hamlem ne olurdu?" — ve o hamlenin logda bırakacağı izi önceden arar. İş akışı iskelettir; kas, ATT&CK bilgisi ve saha sezgisidir.
