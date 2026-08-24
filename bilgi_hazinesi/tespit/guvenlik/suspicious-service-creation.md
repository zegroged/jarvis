# Şüpheli Servis Oluşturma (Event ID 7045) — Tespiti

## 1. Özet: saldırı + naif tespit

Windows servisleri, saldırganların en sevdiği kalıcılık (persistence) ve yetki yükseltme (privilege escalation) mekanizmalarından biridir çünkü servisler `SYSTEM` bağlamında, kullanıcı oturumundan bağımsız, sistem her açıldığında otomatik çalışır. Bir saldırgan hedefte `SeCreateServicePrivilege` veya yerel yönetici hakkı elde ettiğinde, `sc.exe create`, `New-Service`, `PsExec` (ki kendi servisini `PSEXESVC` adıyla kurar), veya doğrudan `CreateServiceW` / registry `HKLM\SYSTEM\CurrentControlSet\Services\` altına yazarak kendi kodunu bir servis olarak tanımlar. `binPath` bir EXE olabilir, bir `cmd /c`, bir `powershell -enc`, hatta bir servis DLL'i (`svchost.exe -k` grubuna sokulmuş) olabilir. MITRE tarafında bu, T1543.003 (Windows Service) ve Linux muadili T1543.002 (Systemd Service) altında toplanır.

Servis Kontrol Yöneticisi (SCM, yani `services.exe`) yeni bir servis kaydettiğinde, `System` event log kanalına **Event ID 7045** ("A service was installed in the system") üretir. Bu olay bize `ServiceName`, `ImagePath`, `ServiceType`, `StartType` ve `AccountName` (`ServiceAccount`) alanlarını verir. Naif tespit tam da buraya kurulur: "7045 gördün mü, alarm ver" veya biraz daha zekisi — `ImagePath` içinde `powershell`, `cmd`, `\Temp\`, `-enc`, `.bat`, `%COMSPEC%` gibi şüpheli ifadeler ara. Sigma dünyasında bunun karşılığı, verilen kurallardaki gibi `process_creation` üzerinden `sc.exe` (`Image|endswith: '\sc.exe'` + `CommandLine|contains|all: create, binPath`) ve PowerShell (`New-Service` + `-BinaryPathName`) yakalamaktır.

Bu, herkesin bildiği kısımdır ve Google'da ilk sayfada bulunur. SOC'a yeni başlayan biri "7045 = servis kuruldu, şüpheli servis = tehdit" der ve kuralı yazar. Gerçek ortamda bu kuralın ömrü, ortama bağlı olarak yarım günden birkaç saate kadardır — sonra ya kapatılır ya da kimse bakmadığı bir kuyruğa (queue) düşer. Değer, bu kuralın **neden** çöktüğünü bilmekte başlar.

## 2. Naif tespit neden yetmez

Birinci ve en büyük sorun: **7045 varsayılan olarak gürültülüdür ve büyük çoğunluğu meşrudur.** Kurumsal bir Windows filosunda her yazılım kurulumu, her güncelleme, her sürücü paketi, her ajan dağıtımı bir veya birden fazla servis yaratır. SCCM/MECM (`ccmsetup`, `CcmExec`), yedekleme ajanları (Veeam, CommVault, Rubrik), EDR/AV ajanları (kendisi!), Chrome/Edge güncelleyicileri (`GoogleUpdate`, `edgeupdate`), .NET runtime kurulumları, VPN istemcileri, yazıcı sürücüleri — hepsi 7045 üretir. Ortalama bir 5.000 uçlu ortamda günde binlerce meşru 7045 görürsün. "Şüpheli servis kuruldu" alarmı, sinyal/gürültü oranı 1:1000'in altında olan bir alarmdır ve bu oranla hiçbir SOC ayakta kalamaz.

İkincisi: **7045'in kendisi bir kör noktaya sahiptir — hangi süreç servisi kurdu bilgisi yoktur.** 7045 olayı `services.exe` tarafından üretilir ve size sadece *ne* kurulduğunu söyler, *kim/ne* kurdu değil. Yani `ImagePath` şüpheli görünmese bile arkasındaki ana süreç (parent process) `winword.exe` veya `w3wp.exe` (IIS worker) olabilir — asıl tehlike sinyali budur ama 7045 tek başına onu vermez. Ana süreci görmek için 7045'i, servisi kuran süreç oluşturma olayına (Sysmon EID 1 veya Security 4688 üzerinden `sc.exe`/`services.exe` soyağacı) korele etmen gerekir. Naif kural bunu yapmaz.

Üçüncüsü: **atlatması kolaydır.** `ImagePath` içinde string arayan bir kuralı düşünün. Saldırgan `powershell` yerine `pwsh`, `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`, veya kısa isim (8.3) `POWER~1.EXE` kullanır; `cmd` yerine `%COMSPEC%` kullanır; string'i kırmak için tırnak ve boşluk enjekte eder (`p^owershell`); veya en temizi, `binPath`'i tamamen meşru bir yola koyup DLL side-loading ile kötü kodu çağırır. `ImagePath` string listen ne kadar uzun olursa olsun, imza-tabanlı (signature-based) mantık her zaman bir adım geridedir.

Dördüncüsü: **7045 bir kanaldan gelir ama saldırgan başka kanaldan girer.** Servis registry'e doğrudan `reg add HKLM\SYSTEM\CurrentControlSet\Services\...` ile veya `CreateService` API'siyle SCM'i atlayarak yazılırsa, bazı senaryolarda 7045 üretilir (SCM yine devrededir), ama servis registry'si dışarıdan (örneğin çevrimdışı disk, veya `reg load` ile başka bir hive) manipüle edilirse 7045 hiç doğmaz. Ayrıca 7045'in "Security" değil "System" log kanalında olduğunu unutma — birçok ekip yalnızca Security kanalını topladığı için 7045'i **hiç görmez**. Bu, sahada gördüğüm en yaygın kör noktalardan biridir.

Beşincisi ve en incesi: **`sc.exe` ve `New-Service` yalnızca servisi *tanımlar*, çalıştırmayı garanti etmez.** Sigma `sc.exe create` kuralı `create` fiilini yakalar ama saldırgan `sc.exe create` ile tanımlayıp `sc.exe config` ile `binPath`'i sonradan değiştirebilir — ki bu, çok daha sinsi bir tekniktir: meşru bir servis oluştur, sonra ImagePath'ini değiştir (T1543.003'ün "modify existing service" varyantı). `create` arayan kural bu `config binPath=` değişikliğini kaçırır.

## 3. Korelasyon zinciri (asıl değer)

Servis oluşturma **tek başına zayıf bir sinyaldir** — çünkü meşru trafik onu boğar. Onu yüksek güvenli bir tespite dönüştüren şey, olayı **önce ve sonrasındaki bağlamla** zincirlemektir. Kıdemli bir detection engineer 7045'e tek başına asla alarm koymaz; onu bir düğüm (node) olarak kullanıp etrafına graf örer.

**Klasik lateral movement zinciri (PsExec / RemCom deseni):**
1. Host-A'da bir kimlik doğrulama: `Security 4624 Type 3` (network logon), kaynak Host-B, ardından `4672` (special privileges — admin logon).
2. Aynı anda Host-A'da bir isimli boru (named pipe): Sysmon EID 17/18, pipe adı `\PSEXESVC` veya rastgeleleştirilmiş bir isim.
3. Saniyeler içinde Host-A'da **7045**: `ServiceName=PSEXESVC` (veya rastgele), `ImagePath` `C:\Windows\PSEXESVC.exe` veya `\ADMIN$` üzerinden bırakılmış bir binary.
4. Ardından servis çalışır, `services.exe` çocuk süreci olarak `cmd.exe`/`powershell.exe` (Sysmon EID 1, ParentImage `services.exe`).

Bu dördünün **aynı host'ta ~10 saniye içinde** peş peşe gelmesi, tek başına 7045'ten kat kat güçlü bir sinyaldir. Kritik ayırt edici nokta 4. adımdaki soyağacıdır: **meşru servisler `services.exe`'nin çocuğu olarak `cmd`/`powershell` doğurmaz.** SCCM bile bunu paketleyip kendi ajanı üzerinden yapar; `services.exe → powershell.exe -enc <base64>` neredeyse her zaman kötücüldür.

**Yetki yükseltme zinciri (yerel):**
1. Standart kullanıcı bağlamında bir süreç (`4688`/Sysmon 1), örneğin bir Office makrosu veya bir exploit.
2. Kısa süre içinde **7045**, `ServiceAccount=LocalSystem`, `ImagePath` kullanıcının yazabildiği bir yolda (`C:\Users\...\AppData\`, `C:\ProgramData\`, `\Temp\`).
3. Servis `SYSTEM` olarak başlar → aynı kullanıcının makinesinde birden aniden `SYSTEM` bağlamlı süreçler doğar.

Burada zinciri kuran mantık şudur: **"Kullanıcı-yazılabilir bir yoldan `SYSTEM` olarak çalışan yeni bir servis"** = neredeyse kesin yetki yükseltme. `ImagePath` `C:\Program Files\` veya `C:\Windows\System32\` altında ve imzalıysa gürültü; `AppData`/`Temp`/`ProgramData` altında ve imzasızsa av.

**Kalıcılık + savunma devre dışı bırakma zinciri (ransomware öncesi):**
Gerçek ihlallerde en değerli korelasyon şudur: **7045 (yeni servis) + kısa süre içinde `7036`/`7040` ile bir güvenlik servisinin durdurulması + `driver_load` ile şüpheli/savunmasız sürücü yüklenmesi.** Vulnerable Driver Load kuralı (verilen `loldrivers.io` hash listesi) tam burada devreye girer: BYOVD (Bring Your Own Vulnerable Driver) saldırılarında saldırgan önce savunmasız bir sürücüyü **servis olarak** kurar (7045, `ServiceType=kernel driver`), sonra o sürücü üzerinden EDR'ı kernel seviyesinde öldürür. Yani 7045'in `ServiceType` alanı `0x1` (kernel driver) ise ve ImagePath `.sys` gösteriyorsa, bu artık "yazılım kuruldu" değil — bu, driver_load olayıyla birebir eşleştirilmesi gereken çok daha yüksek riskli bir sinyaldir. `7045 (kernel driver) + driver_load (loldrivers hash match) + hemen ardından EDR servisinin ölmesi` = BYOVD ihlali, tartışmasız.

**Cross-host desen (yayılma):**
Tek host'ta 7045 gürültü olabilir. Ama **kısa bir pencere içinde 5-10 farklı host'ta aynı `ServiceName` veya aynı `ImagePath` hash'iyle 7045** görürsen — bu bir dağıtım (deployment) desenidir. Sorun şu: bu hem SCCM yazılım dağıtımı (meşru) hem de ransomware yayılımı (kötücül) olabilir. Ayırt edici: SCCM dağıtımı `CcmExec.exe` soyağacından gelir ve servis adı ürün adıdır; kötücül dağıtım genelde `PSEXESVC`/rastgele isimden, WMI (`WmiPrvSE.exe` parent) veya WinRM üzerinden gelir. Yani cross-host 7045 korelasyonunu **her zaman dağıtım mekanizmasının kimliğiyle** birlikte değerlendirmen gerekir.

## 4. False positive gerçeği ve triyaj yargısı

Sahada bu alarmı meşru üreten şeylerin listesi uzundur ve bunları ezbere bilmezsen kuyruğun altında ezilirsin:

- **SCCM/MECM yazılım dağıtımı:** Kurumun binlerce makinesine paket bastığında dalga dalga 7045 üretir. Parent `CcmExec.exe`/`ccmsetup.exe`. Bu en büyük tek gürültü kaynağıdır.
- **Yedekleme yazılımı:** Veeam, CommVault, Backup Exec kurulum/güncelleme sırasında servis kurar; bazıları geçici (transient) servisler bile açıp kapatır.
- **Vulnerability scanner'lar:** Nessus, Qualys, Rapid7 — kimlik doğrulamalı (authenticated/credentialed) tarama yaparken hedefe geçici bir servis kurup tarama yapıp kaldırırlar. Bu, PsExec deseniyle **birebir aynı** görünür: uzaktan admin logon + servis kurulumu + çalıştırma + kaldırma. Sahada gördüğüm en yaygın "sahte PsExec alarmı" kaynağı budur. Scanner'ın kaynak IP'lerini bilmiyorsan haftada 50 sahte alarm açarsın.
- **EDR/AV ajanları:** Kendi güncellemelerinde servis kurar; ironik biçimde kendi sensörün gürültü üretir.
- **Admin script'leri:** Bir sistem yöneticisi `sc create` ile bir bakım görevi kurar, ya da PsExec'i **meşru** olarak troubleshooting için kullanır. Bu gerçek bir kullanımdır ve kör bir kural onu suçlar.
- **Dropbox** (verilen Sigma kuralındaki `filter_optional_dropbox`) gibi masaüstü uygulamaları da `sc.exe` çağırır — kural yazarları bunu bilerek dışladı.

Kıdemli analistin gerçek/gürültü ayrımını yaparken izlediği sıra:

**Önce soyağacı (parent process).** İlk baktığım şey 7045'in kendisi değil, onu üreten süreç zinciridir. `services.exe`'yi kim tetikledi? `CcmExec` → gürültü. `WmiPrvSE`/`wsmprovhost` (WinRM) uzaktan → dikkat. `winword`/`excel`/`w3wp`/`explorer` uzaktan bir servis kuruyorsa → yüksek şüphe.

**Sonra ImagePath'in üç özelliği:** (1) Yolu — sistem dizini mi, kullanıcı-yazılabilir dizin mi? (2) İmza — imzalı mı, imzalıysa imzalayan kim (Microsoft/tanınan yayıncı vs. imzasız/kendinden imzalı)? (3) İçeriği — doğrudan bir EXE mi, yoksa `cmd`/`powershell`/`rundll32` üzerinden dolaylı çalıştırma mı? İmzasız + kullanıcı yolu + dolaylı çalıştırma üçlüsü aynı anda geliyorsa triyaj biter, incelemeye geçer.

**Sonra prevalans (yaygınlık).** Bu `ImagePath` hash'i ortamda ilk kez mi görülüyor, yoksa 3.000 makinede mi var? Yeni + tek host = ilginç. Yaygın = büyük ihtimalle meşru bir ürün. Prevalans sorgusu (frequency analysis) bu alarmı triyaj etmenin en güçlü tek aracıdır.

**Sonra zaman/bağlam.** Bu 7045 bir bakım penceresinde mi, patch salı gecesinde mi geldi? SCCM dağıtım takvimiyle örtüşüyor mu? Yoksa gece 03:00'te, hiçbir change record olmadan mı? Değişiklik yönetimi (change management) kayıtlarıyla çakıştırmak, meşru admin işini kötücülden ayırmanın en hızlı yoludur.

Çoklu alarm patladığında **önce en dar/en yüksek güvenli sinyale** bakarım: BYOVD/loldrivers hash eşleşmesi varsa ona; yoksa `services.exe → powershell -enc` soyağacına; yoksa cross-host aynı-servis desenine. Ham 7045 sayımına en son bakarım çünkü o, en gürültülü katmandır.

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan, servis-tabanlı tespiti bildiği için kural dokümanında yazmayan yollara başvurur. Her birine ikinci-derece bir karşı-tespit vardır:

**Kaçınma 1: `sc create` yerine `sc config` ile mevcut servisi ele geçirme.** Saldırgan yeni servis kurmaz, atıl/kullanılmayan meşru bir servisin `ImagePath`'ini değiştirir (`sc config <hizmet> binPath= ...`). 7045 doğmaz çünkü yeni servis yok. **Karşı-tespit:** registry üzerinde `HKLM\SYSTEM\CurrentControlSet\Services\*\ImagePath` değerinin **değişimini** izle (Sysmon EID 13 registry value set). Yeni servis değil, *var olan servisin ImagePath modifikasyonu* daha sinsi ve daha az izlenen bir sinyaldir. Servis binary'lerinin bir "altın liste"sini tutup değişenleri işaretlemek en sağlam yaklaşımdır.

**Kaçınma 2: `New-Service`/`sc.exe` yerine doğrudan `CreateServiceW` API'si.** Komut satırı imzası yok, `sc.exe` çalışmıyor. **Karşı-tespit:** komut satırına değil, sonuca odaklan — 7045 yine üretilir (SCM devrede), ayrıca registry `Services` anahtarı altında yeni bir alt-anahtar oluşur (Sysmon EID 12 registry key create). Yani `New-Service`/`sc.exe` süreç kuralları atlatılsa bile 7045 + registry key create katmanı ayakta kalır. Bu yüzden **tek bir kanala güvenme** — süreç, olay-log ve registry üç bağımsız katmandır; saldırgan üçünü birden aynı anda susturamaz.

**Kaçınma 3: Kısa-ömürlü (transient) servis.** Servisi kur, çalıştır, hemen sil — alarm gelene kadar iz kalmaz. **Karşı-tespit:** 7045 (install) ile 7034/7035/7036 (servis durum değişimi) ve servis silme'yi aynı kısa pencerede korele et. Bir servisin **dakikalar içinde kurulup silinmesi** başlı başına anomalidir; meşru servisler kalıcıdır. "Kur-çalıştır-sil" imzası, PsExec ve pek çok C2 çerçevesinin doğal davranışıdır.

**Kaçınma 4: Yaşayan-toprak (LOLBin) `binPath`.** `binPath`'e tamamen meşru, imzalı bir Microsoft binary koy (`rundll32`, `regsvr32`, `msiexec`, `mshta`) ve kötü yükü argümanla geçir. İmza kontrolü geçer. **Karşı-tespit:** `ServiceType` genelde `own process` iken `ImagePath`'in bir servis olmayan (servis kontrol handler'ı içermeyen) LOLBin'i işaret etmesi mantıksızdır. `services.exe → rundll32.exe`/`regsvr32.exe` soyağacı neredeyse her zaman kötücüldür çünkü bu binary'ler meşru servis binary'leri değildir — SCM'in beklediği `ServiceMain` giriş noktasına sahip değiller, dolayısıyla genelde `1053` (servis zamanında yanıt vermedi) hatası bile üretirler ki bu ek bir sinyaldir.

**Kaçınma 5: Servis DLL'i (`svchost -k`).** Kendi kötü DLL'ini bir `svchost` servis grubuna kaydettirir (`ServiceDll` registry değeri altında). ImagePath meşru `svchost.exe` görünür. **Karşı-tespit:** ImagePath'e değil, `HKLM\...\Services\<svc>\Parameters\ServiceDll` değerine bak. Yeni bir `ServiceDll` yolu, özellikle imzasız/kullanıcı-yazılabilir bir DLL gösteriyorsa, klasik svchost hijack'idir. Ayrıca `svchost.exe`'nin standart-dışı bir `-k` grubuyla veya bilinmeyen bir servisle başlaması anomalidir.

**Kaçınma 6: Log kanalını susturma.** Gelişmiş saldırgan `System` event log'unu manipüle eder veya `EventLog` servisini geçici durdurur. **Karşı-tespit:** log toplama boşluklarını (gap detection) izle — bir host'tan beklenen 7045/System heartbeat'i aniden kesilirse bu, olayın yokluğunun kendisi bir sinyaldir. `1102`/`104` (log temizleme) ve EventLog servisi durdurma olaylarını ayrıca izle.

Buradaki temel felsefe: **her tekil kaçınma bir katmanı atlatır ama nadiren tümünü.** Sağlam tespit mimarisi, aynı davranışı süreç oluşturma + olay log + registry + soyağacı olmak üzere birbirinden bağımsız çoklu telemetriyle örter. Saldırgan birini kör edebilir; hepsini aynı anda ve sessizce köreltmek çok daha zordur ve bu köreltme çabasının kendisi bir sinyal üretir.

## 6. SIEM / saha gerçeği

**Kanal ve toplama tuzağı.** En kritik saha gerçeği: **7045, `System` event kanalındadır, `Security` değil.** Sadece Security log'u toplayan sayısız ortam gördüm — bunlar 7045'i hiç görmez ve "biz servis oluşturmayı izliyoruz" sanır. WEF/WEC (Windows Event Forwarding) aboneliklerinde veya EDR log toplama profilinde `System` kanalının açıkça toplandığından emin ol. Aksi halde bu kuralların hepsi kağıt üstünde çalışır, sahada hiç tetiklenmez.

**Sysmon vs Security 4688 tuzağı.** `sc.exe`/`New-Service` süreç kurallarının çalışması için süreç oluşturma loglaması şart. İki kaynak var: Security `4688` (varsayılan **kapalı**; ayrıca komut satırı loglaması ayrı bir GPO — "Include command line in process creation events" — açık değilse `CommandLine` alanı **boş** gelir ve `binPath` filtresi çöker) veya Sysmon EID 1 (varsayılan olarak komut satırını içerir, tercih edilen). Eğer sadece 4688 topluyorsan ve komut satırı GPO'su kapalıysa, `sc.exe create ... binPath=` kuralın hiçbir zaman eşleşmez çünkü göreceği tek şey `sc.exe`'nin çalıştığıdır. Bu, sahada en sık gördüğüm sessiz kural ölümüdür.

**Field mapping tuzakları.** 7045'in ham alan adları platformlar arası değişir ve bu, taşınabilir kural yazmayı zorlaştırır:
- Ham Windows XML'de alan `ServiceName`, `ImagePath`, `ServiceType`, `StartType`, `AccountName`'dir.
- **Splunk** (Add-on for Windows / `WinEventLog:System`) genelde `Service_Name`, `Service_File_Name`, `Service_Type`, `Service_Start_Type` diye map'ler — alt çizgili ve farklı. `ImagePath` = `Service_File_Name` olur; bunu bilmeyen analist boş sonuç alır.
- **Microsoft Sentinel**, `Event` tablosunda 7045'i `EventData` içinde XML olarak tutar; alanları `extractjson`/`parse_xml` ile çıkarman gerekir. Defender for Endpoint tarafında ise servis kurulumu `DeviceEvents` içinde `ActionType == "ServiceInstalled"` olarak gelir ve alan adları yine farklıdır (`AdditionalFields` içinde JSON). Yani Sentinel'de aynı tespiti hem `Event` (7045) hem `DeviceEvents` (ServiceInstalled) üzerinden yazabilirsin ve ikisi farklı şema ister.
- **Elastic** (Winlogbeat/Elastic Agent) ECS'e normalize eder: `winlog.event_data.ImagePath`, `winlog.event_data.ServiceName`. ECS tarafında `event.action: "service-installed"` gibi normalize alanlar da olur. Ham `winlog.event_data.*` ile normalize `event.*` arasında hangisine yazdığına dikkat et; ECS güncellemeleriyle map değişebilir.

Sigma bu farkı `logsource` + field taksonomisiyle soyutlamaya çalışır ama backend'in (pySigma pipeline) doğru field mapping'i uyguladığından emin olmalısın; yanlış pipeline ile Sigma'yı Splunk'a çevirdiğinde `ImagePath` diye ararsın, veri `Service_File_Name`'de durur, kural sessizce hiç eşleşmez.

**ServiceType'ı kaybetme.** Çoğu ekip 7045'i alırken `ServiceType` alanını normalize ederken düşürür. Oysa BYOVD tespiti için kritik olan tam da budur: `kernel mode driver` (`0x1`) vs `user mode service`. Bu alanı pipeline'da koru; `.sys` kernel servisi ile `.exe` kullanıcı servisini ayırmak, sürücü-tabanlı saldırıları yakalamanın anahtarıdır.

**Tuning gerçeği.** Bu kuralları üretime almanın tek yolu allowlist (izin listesi) tabanlı tuning'dir, string kara-listesi değil:
1. Önce **ImagePath prevalansına** göre baştan bir taban çizgisi (baseline) çıkar — ortamda >N host'ta görülen her ImagePath hash'ini "bilinen iyi" olarak işaretle. Yeni/nadir olanlar kuyruğa girer.
2. **Parent process allowlist:** `CcmExec.exe`, `ccmsetup.exe`, yedekleme ajanları, EDR ajanları, bilinen kurulum yolları. Sigma'daki `filter_optional_dropbox` mantığını kendi ortamının araçlarıyla çoğalt.
3. **Scanner IP'lerini dışla:** Nessus/Qualys/Rapid7 tarama kaynak host'larından gelen uzaktan servis kurulumlarını ayrı bir düşük-öncelikli akışa yönlendir; onları tümden bastırma (çünkü tarayıcının kendisi ele geçirilebilir) ama ana yüksek-güven akışından çıkar.
4. **Yüksek-güven akışını dar tut:** `services.exe → powershell/cmd/rundll32/regsvr32` soyağacı, veya kullanıcı-yazılabilir yoldan `SYSTEM` servisi, veya loldrivers hash eşleşmesi — bunlar prevalans/allowlist'e bakmadan doğrudan alarm üretebilecek kadar spesifiktir.

Özetle: 7045'i tek başına bir alarm olarak değil, bir **zenginleştirme (enrichment) kaynağı** olarak kullan. Ham 7045'i düşük-öncelikli bir bağlam akışına gönder; alarmı, onu soyağacı + prevalans + registry + driver_load ile zincirlediğin korelasyon kurallarından üret. Naif kural "servis kuruldu" der; kıdemli tespit mühendisi "kullanıcı-yazılabilir yoldan, imzasız, `services.exe`'nin doğrudan `powershell -enc` doğurduğu, ortamda ilk kez görülen ve 20 saniye önce network logon'la gelen bir servis kuruldu" der — ve aradaki fark, çalışan bir SOC ile boğulan bir SOC arasındaki farktır.
