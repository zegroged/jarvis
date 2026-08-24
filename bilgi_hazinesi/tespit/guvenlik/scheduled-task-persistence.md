# Scheduled Task Persistence — Tespiti

> Mavi takım notu: "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin önce saldırganın Windows Görev Zamanlayıcısı'nı (Task Scheduler) nasıl kötüye kullandığını kavramsal olarak anlatır, ardından bunun bıraktığı izleri ve bu izlerden nasıl **tespit** üretileceğini işler. Amaç savunma ve detection engineering'dir; canlı bir saldırı reçetesi değildir. MITRE ATT&CK karşılığı: **T1053.005 — Scheduled Task/Job: Scheduled Task**.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Windows'ta Task Scheduler, "şu koşul oluştuğunda şu programı çalıştır" mantığıyla işleyen, işletim sistemine gömülü meşru bir otomasyon altyapısıdır. Yedekleme, güncelleme kontrolü, disk temizliği gibi yüzlerce meşru görev bu mekanizmayla çalışır. Saldırgan için değerli olan tam da bu meşruiyettir: yeni bir görev eklemek, sistemde ayrı bir servis kurmaya veya yeni bir binary bırakmaya kıyasla çok daha "sıradan" görünür.

Saldırgan bu tekniği kavramsal olarak üç amaçla istismar eder:

- **Persistence (kalıcılık):** Kod çalıştırma yeteneğini yeniden başlatmalar sonrasında da korumak. Bir görev, `ONLOGON` (kullanıcı oturum açtığında), `ONSTART` (sistem açıldığında) veya belirli aralıklarla (`MINUTE`, `HOURLY`, `DAILY`) tetiklenecek şekilde tanımlanırsa, saldırganın implant'ı ilk erişimi kaybetse bile geri gelir.
- **Privilege escalation / execution context:** Görev `SYSTEM` bağlamında (`/RU SYSTEM`) veya başka bir kullanıcının kimliğiyle çalışacak şekilde tanımlanabilir. Bu, düşük yetkili bir süreçten daha yetkili bir bağlamda kod çalıştırma imkânı verir.
- **Savunmayı sabote etme (defense evasion / impact):** Saldırgan yalnızca görev *eklemez*; bazen mevcut ve **önemli** görevleri **siler veya devre dışı bırakır**. Özellikle Windows Defender, Windows Update, yedekleme ve telemetri ile ilgili yerleşik görevleri devre dışı bırakmak, savunma yeteneğini kör etmenin sessiz bir yoludur. Bu, sağladığımız Sigma kurallarının büyük bölümünün odaklandığı davranıştır.

Kavramsal olarak saldırganın elinde birkaç "kol" vardır: `schtasks.exe` komut satırı aracı, PowerShell'in `ScheduledTasks` modülü (`Register-ScheduledTask`), doğrudan Task Scheduler COM arayüzü ve en alttaki katman olan **registry ile dosya sistemi**. Çünkü her görev iki yerde birden yaşar: `C:\Windows\System32\Tasks\` altında bir XML tanım dosyası ve `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\` altındaki registry kayıtları (`Tasks`, `Tree` ve önemli olan `Index` değerleri). Gelişmiş saldırgan, `schtasks.exe`'yi hiç kullanmadan doğrudan bu registry ve dosya katmanına dokunarak "görünmez görev" yaratmaya veya bir görevi listelemelerden gizlemeye çalışabilir — sağladığımız `Index` değeri kaldırma kuralı tam da bu manevrayı hedefler.

Saldırganın burada oynadığı psikolojik oyun da önemlidir: Task Scheduler'daki bir görevin "normalliği", savunmacının dikkatini yormaya oynar. Bir SOC analisti günde onlarca meşru görev oluşturma olayı görür; saldırgan implantını bu gürültünün içine saklamayı umar. Bu yüzden kötü niyetli görevler sıklıkla meşru isimlere benzeyen adlarla (`GoogleUpdateTaskMachine`, `MicrosoftEdgeUpdate` gibi taklitlerle) veya `\Microsoft\Windows\` ağacının derinliklerine yerleştirilerek gizlenir. Tespit mühendisliğinin işi, bu "kalabalığa karışma" stratejisini bağlamsal sinyallerle (ebeveyn süreç, imza, oluşturulma zamanı, çalıştırdığı komut) bozmaktır.

Savunmacı açısından kritik nokta şudur: Task Scheduler'ın kötüye kullanımı neredeyse hiçbir zaman tamamen "sessiz" değildir. Her ekleme, silme, devre dışı bırakma veya kayıt manipülasyonu birden fazla telemetri kaynağında iz bırakır. Saldırganın bir kanalı kör etmesi mümkündür, ama dört kanalı birden köreltmesi hem zordur hem de o körleştirme girişiminin kendisi yeni bir alarm üretir. İşimiz bu izleri okumak ve birbirine bağlamaktır.

---

## 2. Bıraktığı izler / artefaktlar

Scheduled task manipülasyonu, aynı olayı farklı açılardan gören dört ayrı telemetri katmanında yankılanır. İyi bir tespit, bu katmanları birbirine bağlar.

### a) Süreç oluşturma (process creation) telemetrisi
En doğrudan iz, `schtasks.exe`'nin çalıştırılmasıdır. Bu, iki farklı log kaynağında görünür:
- **Sysmon Event ID 1** (Process Creation) — `Image`, `CommandLine`, `ParentImage`, `User` alanları.
- **Windows Security Event ID 4688** (A new process has been created) — `NewProcessName` ve `CommandLine` (denetim politikası açıksa).

Aranacak komut satırı desenleri:
- `schtasks.exe /create ...` — yeni görev.
- `schtasks.exe /delete /tn <GörevAdı> /f` — görev silme (`/f` onay atlatır).
- `schtasks.exe /change ... /disable` — görev devre dışı bırakma.
- `/ru SYSTEM`, `/ru "NT AUTHORITY\SYSTEM"` — yüksek yetkili bağlam.
- `/sc onlogon`, `/sc onstart`, `/sc minute /mo 1` — kalıcılık/tetikleyici işareti.

Parent süreç bağlamı burada altın değerindedir: `schtasks.exe`'nin ebeveyni `winword.exe`, `excel.exe`, `mshta.exe`, `wscript.exe`, `powershell.exe` gibi bir şeyse şüphe katsayısı fırlar; ebeveyni bir kurulum/güncelleme sürecinin bir parçasıysa daha olağandır.

### b) Task Scheduler operasyonel logu (asıl kaynak)
`Microsoft-Windows-TaskScheduler/Operational` kanalı, `schtasks.exe` hiç kullanılmasa bile (PowerShell veya COM ile yapılan işlemleri de) görevin yaşam döngüsünü kaydeder:
- **Event ID 106** — Yeni görev kaydedildi (Task registered).
- **Event ID 140** — Görev güncellendi (Task updated).
- **Event ID 141** — Görev silindi (Task deleted).
- **Event ID 142** — Görev devre dışı bırakıldı (Task disabled).
- **Event ID 200 / 201** — Görev eylemi çalıştırıldı / tamamlandı (hangi programın gerçekten koştuğunu gösterir).
- **Event ID 129** — Görev bir süreç başlattı.

Not: Bu kanal varsayılan olarak her ortamda tam açık olmayabilir; olgun bir SOC bunu toplar. Devre dışıysa, `schtasks.exe` süreç telemetrisi ve Security 4698/4699/4701 event'leri yedek görünürlük sağlar. Bu kanalın en büyük avantajı, olayı *sonuç* düzeyinde kaydetmesidir: görev ister `schtasks.exe` ile, ister PowerShell ile, ister doğrudan COM arayüzüyle silinsin, EID 141 yine de yazılır. Yani bu kanal, "araç değiştirerek kaçma" stratejisine karşı doğal bir bağışıklık sağlar; sağlanan `9e3cb244-...` kuralının değeri tam olarak bu araç-bağımsızlığındadır.

### c) Windows Security denetim event'leri
Denetim politikası ("Audit Other Object Access Events") açıksa:
- **Event ID 4698** — A scheduled task was created.
- **Event ID 4699** — A scheduled task was deleted.
- **Event ID 4700** — A scheduled task was enabled.
- **Event ID 4701** — A scheduled task was disabled.
- **Event ID 4702** — A scheduled task was updated.

Bu event'lerin güzelliği, görev XML tanımını (`TaskContent`) çoğu zaman içermeleridir; yani gizlenen görevin ne yapmaya çalıştığını doğrudan okuyabilirsiniz.

### d) Dosya sistemi ve registry artefaktları
- **Dosya:** `C:\Windows\System32\Tasks\<GörevAdı>` — her görevin XML tanımı. Sysmon Event ID 11 (FileCreate) bu yola yazılan yeni dosyaları yakalar. Klasör adının kendisi (örn. tırnaklı/gizli isimler) bile bir sinyal olabilir.
- **Registry:** `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\` altında:
  - `Tasks\{GUID}` — görevin ikili tanımı.
  - `Tree\<GörevAdı>` — görevin ağaçta görünmesini sağlayan yapı; buradaki **`Index`** değeri kritik.
  - Sysmon Event ID 12/13/14 (Registry object added/set/deleted) bu değişiklikleri kaydeder.

Sağladığımız Sigma kuralı `526cc8bc-...` tam olarak şu artefakta odaklanır: saldırgan `Tree\<Görev>\Index` değerini **silerse**, görev Task Scheduler kullanıcı arayüzünden ve bazı listelemelerden gizlenir ama tetiklenmeye devam eder. Bu, "görevi ortadan kaldırmadan görünmez kılma" hilesidir ve normal bir yönetimsel işlemde neredeyse hiç görülmez.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki tespit mantığı, göreve verilen gerçek Sigma kurallarından türetilmiştir. Bu kurallar iki büyük davranış ailesini kapsar: (1) önemli/yerleşik bir zamanlanmış görevin **silinmesi veya devre dışı bırakılması**, (2) bir görevin **registry `Index` değeri kaldırılarak gizlenmesi**. Dikkat çekici olan: sağlanan kural setinin ağırlığı "görev ekleme"de değil, **savunma sabotajında** (silme/disable) ve **gizlemede**dir. Bu, olgun bir tespit stratejisinin sadece "yeni persistence" değil, "savunmanın körleştirilmesi"ni de izlemesi gerektiğini gösterir.

### Kuralların dayandığı gerçek log kaynakları ve alanlar

Verilen kural metadatasındaki test kanıtları (regression test'lerin `provider: Microsoft-Windows-Sysmon` olması ve dosya yollarındaki `process_creation`, `taskscheduler`, `registry_delete`, `builtin/security` kategorileri) tespit mantığının şu kaynaklara demirlendiğini gösterir:

- **process_creation** kategorisi → `schtasks.exe` komut satırı (Sysmon EID 1 / Security 4688). Kurallar: `dbc1f800-...` (Delete Important Scheduled Task), `9ac94dc8-...` (Disable Important Scheduled Task).
- **taskscheduler** kategorisi → `Microsoft-Windows-TaskScheduler/Operational` (EID 141 silme / 142 disable). Kural: `9e3cb244-...` (Important Scheduled Task Deleted or Disabled).
- **builtin/security** kategorisi → Windows Security kanalı (4699 delete / 4701 disable). Kural: `7595ba94-...` (Important Scheduled Task Deleted/Disabled).
- **registry_delete** kategorisi → registry değeri silme (Sysmon EID 12). Kural: `526cc8bc-...` (Removal Of Index Value to Hide Schedule Task).

Bu dört kaynağın hepsi aynı davranış ailesini farklı görünürlük katmanlarından yakalar; bu yüzden bunlar **tek başına değil, birlikte** güçlüdür.

### Ortak tespit fikri: "önemli görev" listesi

`7595ba94-...`, `9e3cb244-...`, `dbc1f800-...` ve `9ac94dc8-...` kurallarının hepsinde ortak çekirdek şudur: silinen/devre dışı bırakılan görevin adı, **savunma açısından önemli, yerleşik Windows görevlerinden** biriyse alarm üret. Yani sadece "bir görev silindi" değil, "kritik bir görev silindi" tetikleyicidir. Bu görevler tipik olarak `\Microsoft\Windows\...` ağacındaki güvenlik/güncelleme/telemetri görevleridir (örn. Windows Defender, WindowsUpdate, BITS ile ilgili yerleşik görevler). Buradaki dedektif zekâsı: meşru yöneticiler bu görevleri neredeyse hiç silmez veya kapatmaz; saldırgan ise savunmayı köreltmek için tam olarak bunları hedef alır.

### Örnek tespit mantığı 1 — process_creation üzerinden (silme/disable)

`schtasks.exe` ile önemli bir görevin silinmesini/kapatılmasını yakalayan basitleştirilmiş Sigma-benzeri mantık (kurallar `dbc1f800-...` ve `9ac94dc8-...`'nin özü):

```yaml
title: Onemli Scheduled Task Silme/Devre Disi Birakma (schtasks)
logsource:
    category: process_creation
    product: windows
detection:
    selection_img:
        Image|endswith: '\schtasks.exe'
    selection_action:
        CommandLine|contains:
            - ' /delete'
            - ' /change'
    selection_disable_or_del:
        CommandLine|contains:
            - '/disable'
            - '/delete'
    selection_important_task:
        CommandLine|contains:
            # savunma/guncelleme/telemetri iceren yerlesik gorevler
            - '\Microsoft\Windows\Windows Defender\'
            - '\Microsoft\Windows\WindowsUpdate\'
            - '\Microsoft\Windows\SystemRestore\'
            - '\Microsoft\Windows\BitLocker\'
    condition: selection_img and selection_action and selection_disable_or_del and selection_important_task
level: high
```

Buradaki mantık katmanlıdır: (1) süreç gerçekten `schtasks.exe` mi, (2) eylem silme/değiştirme mi, (3) sonuç disable/delete mi, (4) hedef *önemli* bir görev mi. Dördü birden gerçekleşince eşik aşılır. "Önemli görev" listesi ortama göre genişletilmesi gereken bir allowlist/denylist mantığıdır; kuralların değeri bu listenin kalitesindedir.

### Örnek tespit mantığı 2 — registry `Index` değeri silme ile gizleme

`526cc8bc-...` kuralının özü: `TaskCache\Tree` altındaki bir görevin `Index` değerinin silinmesi. Basitleştirilmiş mantık:

```yaml
title: Scheduled Task Gizleme - Index Degeri Kaldirma (Registry)
logsource:
    category: registry_delete
    product: windows
detection:
    selection:
        TargetObject|contains: '\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree\'
        TargetObject|endswith: '\Index'
        EventType: DeleteValue
    condition: selection
level: high
```

Bu davranış son derece spesifiktir: `Tree\...\Index` değerinin silinmesi normal görev yönetiminde gerçekleşmez. Windows bir görevi meşru şekilde sildiğinde tüm alt anahtarı kaldırır; tek başına `Index` değerini silip görevi ağaçta *bırakmak*, görevi gizleme niyetinin neredeyse kesin göstergesidir. Task Scheduler kullanıcı arayüzü ve `schtasks /query` gibi listeleme yolları görev bütünlüğünü doğrularken bu `Index` değerine güvenir; değer eksik olduğunda görev listeden düşer ama zamanlayıcı motoru onu tetiklemeye devam eder. Yani saldırgan tek bir registry değeriyle "listede yokum ama çalışıyorum" durumunu elde eder. Bu yüzden bu kural yüksek güvenle (düşük false positive) çalışır ve genellikle tek başına aksiyon almaya değer.

### Örnek tespit mantığı 3 — TaskScheduler operasyonel kanalı (araç-bağımsız)

`schtasks.exe`'ye hiç bakmadan, silme/disable sonucunu doğrudan operasyonel kanaldan yakalayan mantık (`9e3cb244-...` ve `7595ba94-...`'nin ortak özü):

```yaml
title: Onemli Yerlesik Gorevin Silinmesi/Devre Disi Birakilmasi (araci onemsemez)
logsource:
    product: windows
    service: taskscheduler
detection:
    selection_event:
        EventID:
            - 141   # Task deleted
            - 142   # Task disabled
    selection_important:
        TaskName|startswith: '\Microsoft\Windows\'
        TaskName|contains:
            - 'Windows Defender'
            - 'WindowsUpdate'
            - 'BitLocker'
            - 'SystemRestore'
    condition: selection_event and selection_important
level: high
```

Bu kuralın gücü, saldırganın hangi aracı seçtiğine kör olmasıdır. `schtasks.exe`, `powershell.exe`, `wmic` veya doğrudan COM — hepsi aynı EID 141/142 izini bırakır. Örnek 1 (process_creation) ile Örnek 3'ü (taskscheduler) birlikte devreye almak, tek bir kanalın atlatılmasına karşı derinlemesine savunma sağlar.

### Tespit mantığını katmanlama

Olgun yaklaşım şudur: aynı silme/disable olayını birden fazla kanaldan (process_creation + TaskScheduler Operational 141/142 + Security 4699/4701) korele et. Saldırgan bir kanaldan (örn. `schtasks.exe` yerine PowerShell `Unregister-ScheduledTask` veya doğrudan COM) kaçsa bile TaskScheduler/Security kanalları olayı yakalar. Tek kaynağa bağlı tespit kırılgandır; korelasyon dayanıklıdır.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırganın tespiti atlatma yolları ve savunmacının karşı hamlesi

**a) `schtasks.exe`'den kaçınmak.** Örnek tespit 1 tamamen `Image|endswith: '\schtasks.exe'` üzerine kuruludur. Saldırgan `schtasks.exe`'yi hiç kullanmayıp PowerShell `ScheduledTasks` modülünü (`Unregister-ScheduledTask`, `Disable-ScheduledTask`) veya doğrudan Task Scheduler COM arayüzünü kullanırsa bu process_creation kuralı sessiz kalır.
*Karşı-tespit:* Süreç telemetrisine bağımlı kalmayın. `Microsoft-Windows-TaskScheduler/Operational` (EID 141/142) ve Security (4699/4701) event'leri, aracın kimliğinden bağımsız olarak *sonucu* — görevin silinmesini/kapatılmasını — kaydeder. `9e3cb244-...` ve `7595ba94-...` kurallarının değeri tam da budur: aracı değil, olayı izlerler.

**b) İkili yeniden adlandırma / LOLBin gölgeleme.** Saldırgan `schtasks.exe`'yi kopyalayıp farklı bir isimle çalıştırabilir; `Image` eşleşmesi kaçar.
*Karşı-tespit:* `Image` yerine `OriginalFileName` alanına (PE metadatasından gelir, yeniden adlandırma ile değişmez) demirleyin. Sysmon EID 1 bu alanı sağlar: `OriginalFileName: 'schtasks.exe'`.

**c) Görev adını maskeleme.** "Önemli görev" tespiti bir isim listesine dayanır. Saldırgan hedef görevi tam yol yerine kısaltarak, farklı büyük/küçük harfle veya ara boşluklarla yazabilir.
*Karşı-tespit:* Eşleşmeyi büyük/küçük harf duyarsız yapın, hem tam yol hem kısa ad varyantlarını listeye ekleyin ve mümkünse görevin *sonucunu* (Defender görevinin devre dışı kalması gibi) ikinci bir sinyalle (örn. Defender servis durumu telemetrisi) doğrulayın.

**d) Registry/dosya katmanına doğrudan yazma.** En gelişmiş kaçınma, hiçbir yönetim aracını kullanmadan doğrudan `TaskCache` registry'sine ve `System32\Tasks\` klasörüne yazarak görev oluşturmak veya `Index` değerini silerek gizlemektir.
*Karşı-tespit:* Sysmon registry (EID 12/13) ve FileCreate (EID 11) izlemesini `TaskCache\Tree` ve `System32\Tasks\` yolları için açık tutun. `526cc8bc-...` kuralı bu katmanı kapatır; `Index` silme davranışı o kadar anormaldir ki gelişmiş gizlemeyi paradoksal olarak *daha* görünür kılar.

**e) Log'u susturma.** Saldırgan TaskScheduler/Operational kanalını devre dışı bırakmayı veya log'ları temizlemeyi deneyebilir.
*Karşı-tespit:* Event log servisine dokunma (EID 1102 log temizleme, `wevtutil cl`) ve kanal devre dışı bırakma girişimlerini ayrı bir tespitle izleyin; kritik ana makinelerde log'ları gerçek zamanlı olarak merkezi bir SIEM'e forward edin ki yerel silme etkisiz kalsın.

### Tipik false positive kaynakları ve ayıklama

Scheduled task tespitlerinde en büyük operasyonel maliyet false positive'lerdir. Başlıca kaynaklar:

- **Yazılım kurulum/kaldırma ve güncelleme:** Kurulumcular (installer) ve güncelleyiciler rutin olarak kendi görevlerini oluşturur, günceller ve *kaldırır*. Bir uygulamanın kaldırılması, kendi zamanlanmış görevini meşru şekilde siler.
  *Ayıklama:* Ebeveyn sürecin bilinen bir installer (`msiexec.exe`, imzalı güncelleyici) olup olmadığına ve silinen görevin uygulamanın *kendi* görevi mi yoksa *yerleşik bir Windows savunma görevi* mi olduğuna bakın. Kurallar zaten "önemli/yerleşik görev" filtresiyle bu gürültünün çoğunu keser.

- **Meşru sistem yönetimi (SCCM, Intune, GPO, yapılandırma araçları):** Kurumsal yönetim araçları merkezi olarak görev ekler/kaldırır. Bu yüzden `schtasks.exe`'nin ebeveyni bir yönetim ajansı olduğunda hacim yüksektir.
  *Ayıklama:* Bilinen yönetim sunucularını/servis hesaplarını ve imzalı yönetim binary'lerini allowlist'e alın; ama allowlist'i *kaynak host + hesap* düzeyinde tutun, sadece "schtasks meşrudur" gibi geniş bir istisna yapmayın.

- **Sysadmin ad-hoc işlemleri:** Bir yöneticinin bozuk bir görevi elle silmesi veya devre dışı bırakması meşru olabilir.
  *Ayıklama:* İnteraktif oturum (logon type), kaynak host'un bir yönetici iş istasyonu olması ve olayın bir değişiklik/bakım penceresiyle örtüşmesi gibi bağlamsal sinyallerle triage edin.

- **Registry `Index` silme (kural `526cc8bc-...`) için:** Bu davranışın meşru muadili neredeyse yoktur; dolayısıyla bu kuralın false positive oranı çok düşüktür. Nadir istisna, bozuk görev deposunu onaran kurtarma/repair araçlarıdır. Şüphe halinde ilgili görevin `Tree` ve `Tasks` anahtarlarının tutarlılığını inceleyin.

### Kapanış: tespit felsefesi

Bu kural ailesinin öğrettiği ana ders, "yeni persistence eklendi" alarmının tek başına yetmediğidir. Gerçek saldırgan davranışının imzası çoğu zaman **savunmayı köreltme** (önemli görevlerin silinmesi/devre dışı bırakılması) ve **gizlenme** (`Index` değeri kaldırma) etrafında toplanır. Sağlanan Sigma kurallarının ağırlık merkezinin tam da burada olması tesadüf değildir. İyi bir mavi takım, hem "eklenen görevi" (process_creation + EID 106/4698) hem de "kaybolan/susturulan savunmayı" (EID 141/142, 4699/4701, registry `Index` silme) aynı anda ve birbirine korele ederek izler. Tek kanala bağlı tespit atlatılır; katmanlı ve sonuç-odaklı tespit dayanıklıdır.
