# Güvenlik Araçlarını Devre Dışı Bırakma — Tespiti

> Saha notu. 15 yıllık SOC/detection engineering birikiminden. Bu metin "AMSI nedir, hangi event'e bak" anlatmıyor; sinyalleri nasıl bağlayıp yüksek-güven tespite çevirdiğini, tespitin gerçek dünyada neden bozulduğunu ve kıdemli analistin yargısını anlatıyor. Demir aldığım gerçek kurallar: *Windows AMSI Related Registry Tampering Via CommandLine* (7dbbcac2-57a0-45ac-b306-ff30a8bd2981), *Windows EventLog Autologger Session Disabled* (d7b81144-b866-48a4-9bcc-275dc69d870e), *Important Scheduled Task Deleted/Disabled* (7595ba94-cf3b-4471-aa03-4f6baa9e5fad ve 9e3cb244-bdb8-4632-8c90-6079c8f4f16d), ve *Cisco Dot1x Disabled* (ef0ff092-a24a-4fbc-beea-06c08d53e085).

---

## 1. Özet: saldırı + naif tespit

MITRE bunu **T1562 — Impair Defenses** altında toplar ama sahada "güvenlik aracını devre dışı bırakma" tek bir şey değil, bir *aile*. Saldırgan bir uçta AMSI'yi kör eder (script tabanlı payload'lar taranmadan geçsin diye), diğer uçta ETW/EventLog autologger session'larını kapatır (telemetri hiç doğmasın diye), ortada Defender'ın scheduled task'larını siler, ağ tarafında bir switch'te `dot1x` kimlik doğrulamasını söker. Ortak nokta: **hepsi tespitin gözünü çıkarmayı hedefler**, ama her biri farklı bir katmanda, farklı bir log kaynağında iz bırakır. İşin püf noktası da bu — çünkü saldırgan gözü çıkarınca, o çıkarma eyleminin *kendisi* en değerli sinyal haline gelir.

Naif tespit yaklaşımı basit ve yaygın: her tekniğin bilinen "imzasını" bir Sigma kuralına koyar, alarm çıkınca kırmızı yanar. AMSI için `HKCU\Software\Microsoft\Windows Script\Settings\AmsiEnable` registry değerinin `reg add` ile 0 yapılmasını yakalarsın (kural 7dbbcac2 tam da CommandLine üzerinden bunu arar). Autologger için `HKLM\SYSTEM\CurrentControlSet\Control\WMI\Autologger\EventLog-*` altındaki `Start` değerinin sıfırlanmasını izlersin (kural d7b81144). Scheduled task için `schtasks /delete` veya `/change /disable` komutunu (9e3cb244) ya da Security log'da 4699/4701 event'lerini (7595ba94) beklersin. Cisco'da CLI'da `no dot1x` görürsün.

Bu yaklaşım *demolarda* mükemmel çalışır. Atomic Red Team testini koşarsın, alarm yanar, ekran görüntüsünü rapora koyarsın. Sorun şu: gerçek bir saldırgan senin kuralının aradığı tam string'i kullanmaz, gerçek bir kurumsal ortam da o "kötü" görünen komutları günde yüzlerce kez *meşru* sebeplerle üretir. Naif tespit demoyu geçer, prod'da ya sağır kalır ya da false positive selinde boğulur. Bu metnin geri kalanı tam olarak bu iki başarısızlık modunu ve onları nasıl aşacağını anlatıyor.

---

## 2. Naif tespit neden yetmez

**Kör nokta 1: Sinyal ile telemetrinin doğduğu yer aynı olmayabilir.** En sinsi durum EventLog autologger'da. Kural d7b81144 `HKLM\...\Autologger\EventLog-*\Start = 0` değişikliğini *process creation / command line* üzerinden yakalar. Ama düşün: saldırgan bu registry değerini `reg.exe` ile değil, doğrudan bir process içinden `RegSetValueEx` API'siyle değiştirirse command line'da hiçbir iz kalmaz. Daha kötüsü — autologger değişikliği ancak **bir sonraki reboot'ta** devreye girer. Yani saldırgan `Start=0` yazar, session hâlâ çalışıyordur, sen "hâlâ log alıyorum, sorun yok" dersin, makine haftalar sonra planlı bakımda restart olur ve o günden itibaren o log kaynağı sessizce ölür. Registry yazımını kaçırdıysan, telemetrinin kaybını fark edecek ikinci bir mekanizman yoktur. Bu yüzden autologger tampering'i yakalamak "reboot sonrası log hacminde düşüş" ile korele edilmeli — buna 6. bölümde döneceğim.

**Kör nokta 2: Aynı etkinin yüzlerce sözdizimi var.** AMSI'yi kör etmenin `AmsiEnable=0` dışında en az bir düzine yolu var ve kural 7dbbcac2 bunların sadece registry/CommandLine kolunu görür. `amsi.dll`'yi hiç yüklememek, `AmsiScanBuffer`'ı memory'de patch'lemek, `AMSI_RESULT_CLEAN` döndüren sahte bir provider'ı `HKLM\SOFTWARE\Microsoft\AMSI\Providers` altına register etmek, ya da PowerShell process'inin içinde reflection ile `amsiInitFailed` field'ını true yapmak — hiçbiri `reg add ... AmsiEnable 0` string'i üretmez. Naif kural sadece en gürültülü, en amatör varyantı görür; hedefli aktör onu kullanmaz.

**Kör nokta 3: False positive selleri.** Scheduled task silme/disable en acımasız örnek. `schtasks /delete` her yerde koşar: yazılım güncellemeleri eski task'ları temizler, SCCM/Intune deployment'ları task'ları yeniden yazar, GPO'lar task oluşturup siler, hatta Windows'un kendi bakım rutinleri task'ları disable eder. Kural 7595ba94 ve 9e3cb244 "**Important** Scheduled Task" der — yani anahtar kelime `Important`. Kuralın değeri, herhangi bir task'ı değil, *savunmaya kritik* task path'lerini (örn. `\Microsoft\Windows\Windows Defender\`, `\Microsoft\Windows\SystemRestore\`, `\Microsoft\Windows\BitLocker\`) hedeflemesinde. Ama kurumlar bu allow/deny listesini kendi ortamlarına göre tune etmezse, kural ya çok geniş (her task silme alarm) ya çok dar (saldırganın hedeflediği task listede yok) olur. Ham haliyle deploy edilen bu kural, birkaç gün içinde ya kapatılır ya "acknowledge" tuşuna refleks basılan bir gürültüye dönüşür.

**Kör nokta 4: Bağlam yokluğu tek başına yargı ürettirmez.** `no dot1x` bir Cisco switch'te görüldü diyelim (ef0ff092). Bu bir saldırı mı? Belki bir ağ mühendisi bir konferans odası portunda misafir cihaz sorununu çözmek için 802.1X'i geçici kapattı. Belki de saldırgan fiziksel erişim sağlayıp rogue cihazını sokmak için NAC'i deviriyor. Komutun kendisi ikisinde de bire bir aynı. Tek başına event, "kim, nereden, hangi zaman diliminde, hangi değişiklikle birlikte" bağlamı olmadan yargı üretmez.

Naif tespitin özeti: her kural **tek bir zayıf sinyali** yakalar. Zayıf sinyal ya sessizdir (kaçırılır) ya gürültülüdür (boğar). Değer, bu zayıf sinyalleri **birbirine bağlamakta**.

---

## 3. Korelasyon zinciri — asıl değer

Buradan itibaren Google tek sayfada vermez. Tek başına "AMSI disable" alarmı bir kıdemli analistte kalp atışını hızlandırmaz; günde onlarca gelir. Onu **yüksek-güven ihlale** çeviren şey, kısa bir pencere içinde farklı katmanlarda dizilen çok-aşamalı desendir.

**Desen A — "Kör et, sonra çalıştır" zinciri (host içi, 5-10 dk pencere):**

1. **T-0:** Bir kullanıcı host'unda `powershell.exe` veya `wscript.exe` altından `AmsiEnable=0` registry yazımı (kural 7dbbcac2). Tek başına: düşük güven.
2. **T+2 dk:** Aynı host, aynı process ağacında, encoded (`-enc`) veya `-nop -w hidden` bayraklı ikinci bir PowerShell process'i. Tek başına: orta güven (birçok admin script'i de böyle koşar).
3. **T+4 dk:** Aynı host üzerinde `HKLM\...\Autologger\EventLog-Security\Start=0` ya da `wevtutil sl Security /e:false` (kural d7b81144 komşusu). 
4. **T+6 dk:** Defender'ın scheduled task'ının silinmesi — `\Microsoft\Windows\Windows Defender\Windows Defender Scheduled Scan` (kural 9e3cb244).

Tek tek bunların hiçbiri kesin değil. Ama **AMSI kör etme → ETW/EventLog kör etme → Defender task silme** üçlüsü *aynı host'ta, aynı kullanıcı bağlamında, 10 dakikalık pencerede* dizildiğinde bu artık %95+ gerçek ihlaldir. Çünkü meşru hiçbir iş akışı bu üçünü ardarda yapmaz: SCCM AMSI'ye dokunmaz, yedek yazılımı ETW autologger'ı kapatmaz. Bu bir "defense evasion demeti" ve demet halinde gelmesi tesadüf değildir. SIEM'de bunu `stats`/`transaction` ile host+user bazında pencereleyip, her aşamaya risk puanı verip (AMSI=30, ETW=40, task-delete=30) toplam ≥70'te yükselt — tek tek alarmları bastır, demeti yükselt.

**Desen B — "Ağ katmanı + host katmanı köprüsü" (çok-host, saatlik pencere):**

Bu, tek bir host'a bakan analiz araçlarının kaçırdığı desendir ve asıl kıymet burada. 

1. Bir kenar/erişim switch'inde `no dot1x` veya AAA authentication devre dışı (kural ef0ff092). Bu, o porta artık *kimliksiz* bir cihaz bağlanabileceği anlamına gelir.
2. **Kısa pencere içinde** (dakikalar-saatler), o switch'in beslediği subnet'te DHCP loglarında **daha önce hiç görülmemiş bir MAC adresi** / yeni bir cihaz.
3. O yeni cihazdan iç ağa **doğu-batı tarama** (aynı /24 içinde çok sayıda SYN, SMB/445, WinRM/5985 denemeleri).

`dot1x disabled` tek başına "ağ ekibi bir şey yapıyor" der. Ama `dot1x disabled` **+** *aynı port/VLAN'da yeni bir MAC* **+** *o MAC'ten lateral tarama* = birisi fiziksel/NAC bypass ile ağa rogue cihaz soktu. Bu köprüyü kuran korelasyon, network telemetrisi (Cisco AAA/syslog) ile host/DHCP telemetrisini *birleştirmeyi* gerektirir — ki çoğu SOC bu iki dünyayı ayrı dashboard'larda tutar ve köprüyü asla kurmaz.

**Desen C — "Sessizleşme" negatif korelasyonu:** En zor ama en değerli. Autologger disable + reboot sonucu bir log kaynağı ölürse, pozitif bir alarm gelmez — *bir şey gelmemeye başlar*. Bunu yakalamak için her kritik host için "beklenen EDR/Sysmon EID 1 hacmi" baseline'ı tutulur; belirli bir host **normalde saatte X event üretirken aniden sıfıra düşerse**, bu "log kaynağı öldü" alarmı, geriye dönük olarak o host'taki son autologger/servis değişikliğiyle ilişkilendirilir. Pozitif sinyalin yokluğunu sinyale çevirmek — kıdemli detection engineering'in imzasıdır.

Bağı özetle: **T1562 teknikleri tek başına gürültüdür; demet, sıralama ve katmanlar arası köprü onları kanıta çevirir.**

---

## 4. False positive gerçeği ve triage yargısı

Kıdemli analistin gerçek işi alarm okumak değil, **gürültüyü meşru gürültüden ayırmaktır**. İşte her sinyalin gerçek FP kaynakları ve triage refleksleri:

**Scheduled task silme/disable (7595ba94, 9e3cb244) — en gürültülü.**
- **Meşru üreticiler:** SCCM/ConfigMgr client (task'ları sürekli yeniden yazar), Intune, yazılım güncelleyicileri (Chrome, Adobe, Java eski task'ları temizler), yedekleme ajanları (Veeam, Commvault kendi task'larını yönetir), vuln scanner'lar (Qualys/Nessus agent'ları), GPO uygulaması.
- **Ayrım yargısı:** Silinen task'ın *path'i* her şeyi belirler. `\GoogleUpdateTaskMachine*` silinmesi = gürültü. `\Microsoft\Windows\Windows Defender\*` veya `\Microsoft\Windows\SystemRestore\SR` silinmesi = kırmızı. **Parent process'e bak:** `TrustedInstaller.exe`, `ccmexec.exe`, `msiexec.exe` altından gelen task silme büyük olasılıkla meşru; `cmd.exe`/`powershell.exe` altından, özellikle `-enc` ile başlamış bir ağaçtan gelen = şüpheli. **Kullanıcıya bak:** SYSTEM/SCCM service account = normal; interaktif bir kullanıcının task'ı Defender path'inde silmesi = anormal.

**AMSI registry tampering (7dbbcac2).**
- **Meşru üreticiler:** Şaşırtıcı derecede az. Bazı eski uygulama installer'ları AMSI ile çakışma yaşayıp geçici kapatabilir; bazı geliştirici/pentest lab makineleri. Kurumsal bir son-kullanıcı endpoint'inde `AmsiEnable=0` neredeyse **hiçbir zaman meşru değildir**.
- **Ayrım yargısı:** Bu düşük-FP'li, yüksek-sadakatli bir sinyaldir — geldiğinde ciddiye al. FP çıkıyorsa muhtemelen bir developer/security team makinesindir; bu makineleri ayrı bir "known tooling" grubuna koy, kuralı orada bastır ama **son-kullanıcı VLAN'ında asla bastırma**.

**Autologger disable (d7b81144).**
- **Meşru üreticiler:** Performans tuning yapan sistem yöneticileri (nadir), bazı imaj hazırlama (sysprep) süreçleri, log toplama ajanı kurulumları kendi provider'larını register/deregister edebilir.
- **Ayrım yargısı:** Hangi autologger? `EventLog-Security`, `EventLog-System`, `Microsoft-Windows-Threat-Intelligence` veya EDR'nin kendi ETW session'ı hedefleniyorsa = kırmızı. Bir performans counter session'ı = muhtemelen gürültü. Değişikliği yapan process ve reboot ile ilişkisi kritik.

**Cisco dot1x disabled (ef0ff092).**
- **Meşru üreticiler:** Ağ ekibinin troubleshooting'i, yeni cihaz onboarding, konferans odası/misafir portları, IP telefon/yazıcı istisnaları.
- **Ayrım yargısı:** *Change management* ile eşleştir. Onaylı bir change ticket'ı varsa gürültü; mesai dışı, ticket'sız, ve ardından yeni MAC geliyorsa kırmızı. **Kim yaptı** (yetkili ağ mühendisi mi, yoksa paylaşımlı bir enable hesabı mı) ve **nereden** (jump host mu, beklenmedik bir kaynak mı) belirleyici.

**Çoklu alarmda öncelik sırası.** Aynı anda beş alarm patladığında kıdemli analistin sırası şudur: (1) **Düşük-FP + yüksek-etki olanı önce** — AMSI tampering ve EDR-ETW disable, çünkü bunlar hem nadiren meşrudur hem de "birazdan kör olacağım" anlamına gelir, saati işliyordur. (2) **Demet oluşturanı** — tek host'ta üç farklı T1562 sinyali varsa, o host'u izole etmeyi tek bir Defender task silmesinin önüne al. (3) **Sessizleşme sinyalini** — bir kritik sunucu log göndermeyi kesmişse, bu "gelmeyen 100 alarm" demektir, öne al. (4) En sona gürültülü-ama-tekil scheduled task silmelerini bırak. Yargının özü: *etkiyi ve geri-döndürülemezliği* önceliklendir, alarm sayısını değil.

---

## 5. Kaçınma → karşı-tespit

Saldırgan kural dokümantasyonunu senden iyi okur. İşte kuralların *yazmadığı* atlatma yolları ve her birine ikinci-derece tespit:

**AMSI için `AmsiEnable` yerine memory patch.** Kural 7dbbcac2 registry/CommandLine'a bakar; saldırgan bunun yerine PowerShell process'inde `amsi.dll`'nin `AmsiScanBuffer` fonksiyonunun ilk byte'larını `VirtualProtect` + memory write ile değiştirir. Registry'ye hiç dokunmaz.
- **Karşı-tespit:** EDR'nin memory/API telemetrisi — `amsi.dll` bölgesine `RWX` ile yapılan runtime yazma, veya klasik "amsiInitFailed" reflection pattern'i script block logging'de (PowerShell EID 4104) görünür. Ayrıca `amsi.dll`'yi *hiç yüklemeyen* ama yine de script koşturan PowerShell process'i anomalidir: modül yükleme telemetrisinde amsi.dll yokluğu bir sinyal.

**Autologger yerine servisi durdurma / provider deregister.** `Start=0` yazmak yerine saldırgan doğrudan `EventLog` servisini durdurur, ya da `logman stop` ile trace session'ı canlı olarak öldürür, ya da `RegSetValueEx` API'siyle registry'ye command line bırakmadan yazar (kör nokta 1).
- **Karşı-tespit:** Servis durdurma → Security EID 7035/7036 (servis kontrol yöneticisi) + kritik servisler için "beklenen çalışıyor" health check. `logman`/`wevtutil sl /e:false` komut satırı ayrı yakalanmalı. En sağlamı **negatif korelasyon**: EventLog session'ının ürettiği event akışının kesilmesini, o host için baseline ile karşılaştırıp bağımsız alarm çıkar. Saldırgan komutu gizleyebilir ama *log akışının durmasını* gizleyemez.

**Schtasks yerine COM / Task Scheduler API.** Kural 9e3cb244 `schtasks.exe` komut satırına, 7595ba94 Security EID 4699/4701'e bakar. Saldırgan `schtasks.exe` yerine `ITaskService` COM arayüzünü (PowerShell `Register-ScheduledTask`/`Unregister-ScheduledTask` ya da doğrudan COM) kullanırsa `schtasks.exe` process'i hiç doğmaz.
- **Karşı-tespit:** Kritik olan **Security EID 4699 (task deleted) / 4701 (task disabled)**'e güvenmek, çünkü bu event *hangi API kullanılırsa kullanılsın* Task Scheduler tarafından üretilir — command-line kuralı atlatılabilir ama SCM/Security audit event'i atlatmak çok daha zordur. Yani command-line kuralı ile event-log kuralını **birlikte** deploy et; biri kaçarsa diğeri yakalar. Ek olarak `Microsoft-Windows-TaskScheduler/Operational` log'unda EID 141 (task deleted) ikinci bir kaynaktır.

**Cisco'da `no dot1x` yerine daha sinsi devre dışı bırakma.** Global `no dot1x system-auth-control` yerine saldırgan tek bir interface'de `authentication open` yapar ya da MAB (MAC Authentication Bypass) fallback'i sömürür — 802.1X hâlâ "açık" görünür ama pratikte bypass edilir.
- **Karşı-tespit:** Sadece `no dot1x` string'ine değil, `authentication open`, `authentication port-control force-authorized`, interface bazında `dot1x` kaldırılmasına bak. Cisco config değişikliklerini periyodik **config diff** ile izle (NCM/RANCID) — CLI event'ini kaçırsan bile config baseline'dan sapma yakalanır. Ve yine köprü: dot1x zayıflatma + o portta beklenmedik MAC.

**Genel meta-kaçınma: "yavaş ve dağınık".** Zeki saldırgan üç T1562 eylemini 10 dakikaya sığdırmaz — birini Pazartesi, birini Çarşamba, farklı hesaplarla yapar ki Desen A'daki pencere korelasyonu tetiklenmesin.
- **Karşı-tespit:** Korelasyon penceresini host+kullanıcı yerine **varlık (asset) bazlı ve daha uzun (24-72 saat)** tut; risk puanını zaman içinde biriktir (decaying score). Ayrıca "aynı host'ta farklı günlerde farklı savunma-zayıflatma tekniği" desenini bağımsız bir meta-kural yap. Amaç, saldırganı hız yapmaya değil, *sabırlı olmaya bile* zorlanınca yakalamak.

---

## 6. SIEM / saha gerçeği

**Varsayılan loglanmayan şeyler — en büyük tuzak.** Yukarıdaki kuralların çoğu, kutu-varsayılan bir Windows'ta **hiç tetiklenmez**, çünkü gereken telemetri kapalıdır:

- **Registry değişikliği telemetrisi** (AMSI 7dbbcac2, Autologger d7b81144): Security log'da registry auditing varsayılan **kapalıdır**. Bu kuralların çalışması için pratikte **Sysmon** gerekir — `Microsoft-Windows-Sysmon/Operational`, **Event ID 13** (RegistryValueSet). Sysmon config'inde bu registry path'leri (`\AmsiEnable`, `\Autologger\`) açıkça include edilmiş olmalı; SwiftOnSecurity/Olaf tarzı bir config bunları kapsar ama daraltılmış bir kurumsal config kapsamayabilir. Sysmon yoksa bu kuralların yakaladığı tek şey command-line'dır (EID 1) ki o da API-tabanlı atlatmaya açıktır (5. bölüm).
- **Scheduled task Security event'leri** (7595ba94): EID 4699/4701 için **"Audit Other Object Access Events"** alt kategorisi advanced audit policy'de açık olmalı — varsayılan **kapalı**. Açık değilse 4699 hiç düşmez, kural sağırdır. Birçok kurum bunu bilmez ve "kuralı deploy ettim ama hiç alarm gelmiyor" der; sebep kural değil, audit policy.
- **Command-line capture** (schtasks 9e3cb244): Process creation'da command line'ın loglanması için ya Sysmon ya da **"Include command line in process creation events"** GPO ayarı + Audit Process Creation (EID 4688) açık olmalı. Kapalıysa `schtasks /delete` görünür ama argümanlar görünmez, kural eşleşemez.
- **Cisco AAA/dot1x** (ef0ff092): Switch'in `logging` ve AAA accounting'i SIEM'e syslog basıyor olmalı; çoğu ortamda ağ cihaz logları "gürültü" diye ya hiç toplanmaz ya da düşük seviyede tutulur. `logging level` yetersizse config komutları hiç gelmez.

**Field mapping tuzakları.** Sigma soyut alan adları kullanır (`CommandLine`, `TargetObject`, `Image`); bunlar her SIEM'de farklı isme map olur ve yanlış map = sessiz sağırlık:
- **Splunk:** Sysmon TA ile `TargetObject`, `CommandLine`, `Image` genelde doğrudan gelir ama `process` vs `Image`, `CommandLine` vs `process` çakışmaları olur; CIM normalizasyonu (`Processes` datamodel) alan adlarını değiştirir. Registry için `Registry` datamodel'inde `registry_path`/`registry_value_name` kullanılır — Sigma'nın `TargetObject`'i doğrudan gelmez, çevirmen gerekir.
- **Sentinel:** `SecurityEvent` (klasik 4688/4699) vs `DeviceProcessEvents`/`DeviceRegistryEvents` (MDE) iki ayrı dünyadır. MDE tarafında alan `RegistryValueName`, `ProcessCommandLine`'dır; Sysmon-Sigma kuralını birebir çalıştıramazsın, MDE şemasına çevirmen şart. Ayrıca Sysmon EID 13 → Sentinel'e ancak AMA/DCR ile toplanırsa gelir.
- **Elastic:** ECS ile `process.command_line`, `registry.path`, `registry.data.strings`. Sigma→ECS çevirisinde en sık hata registry value'nun `registry.path`'e mi yoksa `registry.value`'ya mı map olduğunu karıştırmaktır; `Autologger\...\Start` yolunun tam eşleşmesi ECS'de `registry.path` + `registry.data.strings: "0"` ister.

**Tuning yargısı.** Bu aileyi prod'a alırken sıralama şu olmalı: (1) **Önce telemetri doğrula** — audit policy ve Sysmon config gerçekten bu event'leri üretiyor mu, bir Atomic testle *canlı* teyit et. "Kural var" ≠ "veri var". (2) **Bilinen-iyi'yi ortama göre çıkar** — SCCM/TrustedInstaller/msiexec parent'larını, developer VLAN'larını allow-list'e al ama bunu *dar ve gerekçeli* tut, geniş `powershell.exe` bastırması yapma. (3) **Tek kuralı yükseltme, demeti yükselt** — tek tek T1562 kurallarını "informational/low" tut, korelasyon meta-kuralını "high" yap; analistin gelen kutusunu tek sinyaller değil demetler doldursun. (4) **Sessizleşmeyi izle** — her kritik host için telemetri health/heartbeat monitörü kur; bir log kaynağının susması, gelen bir alarmdan daha tehlikelidir çünkü onu hiç kimse "acknowledge" etmez, sadece yokluğuyla var olur.

Saha özeti: Güvenlik aracı devre dışı bırakma tespitinde asıl beceri imza yazmak değil — doğru telemetrinin *var olduğundan* emin olmak, zayıf sinyalleri katmanlar arası köprülerle demetlemek, meşru gürültüyü path/parent/kullanıcı üçlüsüyle elemek, ve saldırgan telemetriyi öldürdüğünde *sessizliğin kendisini* bir alarma çevirmektir.
