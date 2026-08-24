# AMSI/ETW Tamper — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin önce saldırganın AMSI ve ETW gibi savunma altyapısını nasıl kör ettiğini kavramsal olarak anlatır, sonra bu körleştirmenin geride bıraktığı izleri ve bunları yakalayan tespit mantığını işler. Amaç savunma ve tespit mühendisliğidir; canlı bir saldırı reçetesi değildir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Windows'ta savunmanın gözü ve kulağı olan iki temel katman vardır ve saldırgan tam olarak bu ikisini hedef alır: **AMSI (Antimalware Scan Interface)** ve **ETW (Event Tracing for Windows)**. İkisi de "defense evasion" ailesinden, MITRE ATT&CK'te büyük ölçüde **T1562 (Impair Defenses)** altında sınıflandırılır. Yukarıda verilen Sigma kurallarının etiketlediği `attack.defense-impairment` tam olarak bu davranış sınıfını işaret eder.

### AMSI ne yapar, saldırgan neden onu hedef alır

AMSI, script motorlarının (PowerShell, VBScript, JScript, Office VBA, .NET runtime) çalışma zamanında ürettiği içeriği — yani bellekte deşifre edilmiş, tüm obfuscation katmanları soyulmuş **gerçek** kodu — kayıtlı bir antimalware sağlayıcısına "bunu tarar mısın?" diye sunmalarını sağlayan bir köprüdür. Klasik imza atlatma teknikleri (Base64, string birleştirme, XOR ile şifreleme) AMSI karşısında büyük ölçüde etkisizdir; çünkü kod, çalışabilmek için mutlaka deşifre olmak zorundadır ve tam o anda AMSI'ye net metin olarak düşer.

Saldırganın amacı bu köprüyü koparmaktır. Eğer AMSI devre dışıysa, deşifre edilmiş kötü amaçlı script hiçbir tarayıcıya uğramadan çalışır. Körleştirmenin kavramsal sınıfları şunlardır (adım adım reçete değil, davranış kategorisi olarak):

- **Bellek içi yama (in-memory patch):** Süreç kendi adres alanındaki `amsi.dll` içindeki tarama giriş noktasını (kavramsal olarak `AmsiScanBuffer` benzeri fonksiyon) değiştirerek her taramanın "temiz" sonucu döndürmesini sağlar. Disk dosyası değişmez, sadece o sürecin belleği bozulur. Bu yüzden en sinsi varyanttır.
- **Sağlayıcının hiç yüklenmemesi / bozuk yüklenmesi:** AMSI'nin başlatma aşamasında hata alması sağlanır, böylece motor "sağlayıcı yok" diye tarama yapmadan devam eder.
- **Registry üzerinden AMSI'nin veya sağlayıcının devre dışı bırakılması / silinmesi:** AMSI davranışını yöneten registry anahtarları veya AMSI provider CLSID kayıtları değiştirilir ya da silinir. Bu, kalıcı ve makine genelinde etkili bir müdahaledir.
- **AMSI provider'ın kötü amaçlı ile değiştirilmesi (persistence):** Saldırgan kendi CLSID'sini yeni bir AMSI provider olarak kaydeder; bu hem AMSI'yi manipüle etme hem de kalıcılık (persistence) fırsatı sunar.
- **"PowerShell without PowerShell":** `powershell.exe` çalıştırmak gürültülüdür ve izlenir. Bunun yerine saldırgan, `.NET` runtime'ını ve dolaylı olarak `amsi.dll`'i, PowerShell yürütücüsü olmayan bir LOLBIN (living-off-the-land binary) süreç içinden yükleyerek AMSI/script telemetrisini beklenmedik bir yerden tetikler.

### ETW ne yapar, saldırgan neden onu hedef alır

ETW, Windows'un yüksek performanslı olay izleme altyapısıdır. EDR ve güvenlik ürünlerinin büyük kısmı davranışsal telemetriyi (özellikle `Microsoft-Windows-PowerShell` ve .NET runtime sağlayıcıları üzerinden script bloklarını, yüklenen assembly'leri) ETW üzerinden alır. Saldırgan ETW'yi kör ederse, EDR'ın "duyduğu" ses kesilir: script çalışır ama telemetri akmaz. Kavramsal olarak saldırgan, kendi sürecinde ETW olay sağlayıcısına giden çağrıları yamalayarak veya olay sağlayıcının handle'ını etkisizleştirerek "sessizleştirme" yapar. AMSI görmezse tarama olmaz; ETW duymazsa kayıt olmaz. İkisi birlikte kör edildiğinde saldırgan hem gözü hem kulağı kapatmış olur.

Önemli tespit içgörüsü şudur: **Körleştirmenin kendisi bir gürültüdür.** Saldırgan görünmez olmak için yaptığı hamlede, savunmayı devre dışı bırakma eylemini gerçekleştirmek zorundadır ve bu eylem — registry değişikliği, DLL yükleme deseni, komut satırı dizesi — kendi başına yüksek sinyalli bir artefakt üretir. Tespit mühendisliği tam olarak bu paradoksu sömürür. Savunmacının işi, saldırganın "sessize almak" için ürettiği tek seferlik, düşük hacimli ama çok belirgin sinyali yakalamaktır. Meşru bir üretim ortamında AMSI'yi kapatan, AMSI sağlayıcısını silen veya `amsi.dll`'i garip bir süreç içinden yükleten bir eylem neredeyse hiç görülmez; işte bu düşük taban gürültüsü (low base rate), bu davranışları mükemmel tespit adayı yapar.

Bir diğer önemli nokta: AMSI ve ETW tamper genellikle **birlikte** kullanılır. Saldırgan yalnızca AMSI'yi kapatırsa, ETW hâlâ script bloğunu (Event ID 4104) EDR'a iletebilir; yalnızca ETW'yi kapatırsa, AMSI hâlâ deşifre edilmiş kodu tarayıcıya sunabilir. Bu yüzden olgun bir saldırı ikisini ardışık olarak, çoğu zaman aynı süreç içinde hedefler. Savunmacı için bu bir fırsattır: iki ayrı körleştirme eyleminin kısa aralıkla aynı host'ta görülmesi, tek bir olaydan çok daha güçlü bir korelasyon sinyalidir.

---

## 2. Bıraktığı izler / artefaktlar

Saldırgan hangi yolu seçerse seçsin, belirli izler kalır. Bunları log kaynağına göre gruplayalım.

### 2.1 Registry artefaktları (en yüksek sinyalli)

AMSI'nin registry üzerinden manipülasyonu, Sysmon ile net biçimde yakalanır. İlgili Sysmon olayları:

- **Sysmon Event ID 13 — RegistryValue Set:** Bir registry değerinin yazılması/değiştirilmesi. AMSI davranışını kapatan değer ataması burada görünür.
- **Sysmon Event ID 12 — RegistryObject Added or Deleted:** Bir registry anahtarının/değerinin oluşturulması veya silinmesi. AMSI provider anahtarlarının silinmesi (registry_delete) tam olarak buraya düşer.

İlgili registry yolları ve desenleri (gerçek Sigma kurallarının hedeflediği alanlar):

- AMSI'yi devre dışı bırakan değer ataması — provider'ın yüklenmesini engelleyecek şekilde AMSI ile ilişkili anahtarlarda `DisableAntiSpyware` / `AmsiEnable` benzeri değerlerin `0`'a set edilmesi (kural: **AMSI Disabled via Registry Modification**, id `aa37cbb0-da36-42cb-a90f-fdf216fc7467`).
- AMSI provider CLSID kayıtlarının bulunduğu `...\Software\Microsoft\AMSI\Providers\{CLSID}` alanındaki anahtarların **silinmesi** (kural: **Removal Of AMSI Provider Registry Keys**, id `41d1058a-aea7-4952-9293-29eaaf516465`).
- Var olan bir AMSI provider'a ek olarak **yeni bir provider CLSID'sinin eklenmesi** — kalıcılık amaçlı (kural: **Potential Persistence Via New AMSI Providers - Registry**, id `33efc23c-6ea2-4503-8cfe-bdf82ce8f705`).
- Bu registry manipülasyonlarının **komut satırından** yapıldığı durumlar — yani `reg.exe`, `reg add`, `reg delete` ya da PowerShell `Set-ItemProperty`/`Remove-Item` çağrılarının komut satırında AMSI ile ilişkili registry yollarını içermesi (kural: **Windows AMSI Related Registry Tampering Via CommandLine**, id `7dbbcac2-57a0-45ac-b306-ff30a8bd2981`).

### 2.2 Process creation / komut satırı artefaktları

- **Sysmon Event ID 1 — Process Creation** (veya Windows Security **Event ID 4688**, `CommandLine` denetimi açıksa). AMSI ile ilişkili registry yollarını içeren `reg.exe`/PowerShell komut satırları burada görünür. `CommandLine` alanında AMSI provider yolu + `delete`/`add`/`Remove-Item` kombinasyonu güçlü bir işaretçidir.
- PowerShell komut satırında bilinen AMSI atlatma dizeleri — örneğin `System.Management.Automation.AmsiUtils`, `amsiInitFailed`, `[Ref].Assembly.GetType(...)` benzeri reflection kalıpları. Bunlar özellikle **Script Block Logging** ile kesişince değerlidir.

### 2.3 Image load (DLL yükleme) artefaktları

- **Sysmon Event ID 7 — Image Loaded.** "PowerShell without PowerShell" saldırısı, `amsi.dll`'in bir LOLBIN süreç tarafından yüklenmesiyle iz bırakır. Gerçek kural **Amsi.DLL Loaded Via LOLBIN Process** (id `6ec86d9e-912e-4726-91a2-209359b999b9`) tam olarak bunu yakalar: `ImageLoaded` alanı `\amsi.dll` ile bitiyor **ve** yükleyen `Image` beklenmeyen bir süreç (`\ExtExport.exe`, `\odbcconf.exe`, `\rundll32.exe`). Normalde `amsi.dll`'i `powershell.exe`, `wscript.exe` gibi script motorları yükler; bu ikili yükleyicilerden gelmesi anomali sinyalidir.

### 2.4 PowerShell / .NET telemetri artefaktları

- **Microsoft-Windows-PowerShell/Operational — Event ID 4104 (Script Block Logging):** Deşifre edilmiş script bloğunu kaydeder. AMSI atlatma reflection kodu buraya net metin olarak düşebilir. Not: ETW başarıyla körleştirildiyse 4104 **kesilir** — yani beklenen bir sürecin script block loglarının aniden susması da bir artefakttır (kanıtın yokluğu ile tespit).
- **Event ID 4103 (Module/Pipeline logging)** ve `AMSI operation failed` / `AmsiUtils` referansları.

### 2.5 Ağ ve dolaylı izler

AMSI/ETW tamper doğrudan bir ağ artefaktı üretmez; ancak körleştirme genellikle bir sonraki aşamanın (indirici, C2, in-memory payload) hemen öncesinde gelir. Bu yüzden bir AMSI tamper olayının hemen ardından gelen `powershell.exe` outbound bağlantısı veya beklenmeyen süreç enjeksiyonu, korelasyon için değerli bağlamdır. Zaman ekseninde düşünmek kritik: tamper olayı, saldırı zincirinin ortasında bir "dönüm noktası" işaretidir. Öncesinde genellikle bir teslim (delivery) aşaması — phishing eki, indirilen script — bulunur; sonrasında ise gerçek kötü amaçlı yük çalışır. Tek başına AMSI tamper olayını yakalamak değerlidir, ama onu bir zincirin parçası olarak — öncesi ve sonrasıyla — kurgulamak, hem tespit güvenini hem de olay müdahale (incident response) sırasındaki kök-neden analizini güçlendirir.

### 2.6 Artefaktların dayanıklılık sıralaması

Savunmacı açısından artefaktları "atlatılabilirlik" derecesine göre sıralamak faydalıdır. En dayanıklı (atlatılması en zor) olandan başlayarak: (1) registry_delete / registry_set olayları — normalize edilmiş `TargetObject` yolu obfuscation'a dirençlidir; (2) image_load olayları — `amsi.dll` yükleme deseni bellek yamasında da görünür çünkü DLL yine de yüklenir; (3) process_creation / command-line olayları — obfuscation'a en açık katman; (4) script içerik logları (4104) — ETW körleştirilirse tamamen kaybolabilir. Bu sıralama, hangi kurallara stratejik olarak ağırlık verileceğini belirler.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki mantıklar tamamen yukarıda verilen gerçek Sigma kurallarına dayanır. Uydurma kural, CVE veya field yoktur; log kaynağı, field ve koşullar bu kurallardan alınmıştır.

### 3.1 Registry set — AMSI'nin devre dışı bırakılması

Kural referansı: **AMSI Disabled via Registry Modification** (`aa37cbb0-...`), pozitif test provider'ı **Microsoft-Windows-Sysmon**.

- **logsource:** `category: registry_set` (Sysmon Event ID 13)
- **Mantık:** `TargetObject` alanı AMSI ile ilişkili anahtarı işaret ediyor **ve** `Details` alanı devre dışı bırakan değeri (örn. `DWORD (0x00000000)`) gösteriyorsa alarm üret.
- **Eşik:** Tek olay yeterlidir (match_count: 1). Bu düşük hacimli, yüksek sinyalli bir olaydır; production'da nadiren meşru olarak gerçekleşir.

Basit Sigma-benzeri örnek:

```yaml
title: AMSI Registry Üzerinden Devre Dışı (örnek mantık)
logsource:
    category: registry_set
    product: windows
detection:
    selection:
        TargetObject|contains: '\AMSI\'
        Details: 'DWORD (0x00000000)'
    selection_amsi_enable:
        TargetObject|endswith: '\AmsiEnable'
        Details: 'DWORD (0x00000000)'
    condition: selection or selection_amsi_enable
level: high
```

### 3.2 Registry delete — AMSI provider anahtarının silinmesi

Kural referansı: **Removal Of AMSI Provider Registry Keys** (`41d1058a-...`), provider **Microsoft-Windows-Sysmon**.

- **logsource:** `category: registry_delete` (Sysmon Event ID 12, `EventType: DeleteValue`/`DeleteKey`)
- **Mantık:** `TargetObject` alanı `...\AMSI\Providers\{CLSID}` desenine uyan bir anahtarın silinmesini gösteriyorsa alarm üret. Bir AMSI sağlayıcısının **silinmesi** meşru yönetimsel işlerde neredeyse hiç görülmez; bu güçlü bir kötü niyet işaretidir.
- **Eşik:** Tek olay yeterli.

### 3.3 Registry set — yeni AMSI provider ile persistence

Kural referansı: **Potential Persistence Via New AMSI Providers - Registry** (`33efc23c-...`).

- **logsource:** `category: registry_set`
- **Mantık:** `...\AMSI\Providers\` altında **yeni** bir CLSID kaydı oluşuyorsa ve bu CLSID işaret ettiği InprocServer32 DLL'i şüpheli bir konumdaysa (kullanıcı profili, `%TEMP%`, `AppData`) alarm üret. Burada tespit hem manipülasyon hem persistence açısından çift değerlidir.

### 3.4 Command line — AMSI registry tampering

Kural referansı: **Windows AMSI Related Registry Tampering Via CommandLine** (`7dbbcac2-...`), provider **Microsoft-Windows-Sysmon** (Event ID 1).

- **logsource:** `category: process_creation`
- **Mantık:** `CommandLine` alanı hem AMSI ile ilişkili registry yolunu (`\AMSI\` veya provider CLSID'si) hem de bir manipülasyon fiilini (`reg delete`, `reg add`, `Remove-ItemProperty`, `Set-ItemProperty`) içeriyorsa alarm üret.

Basit Sigma-benzeri örnek:

```yaml
title: AMSI Registry Tampering — Komut Satırı (örnek mantık)
logsource:
    category: process_creation
    product: windows
detection:
    selection_path:
        CommandLine|contains: '\AMSI\'
    selection_verb:
        CommandLine|contains:
            - 'reg delete'
            - 'reg add'
            - 'Remove-Item'
            - 'Set-ItemProperty'
    condition: selection_path and selection_verb
level: high
```

### 3.5 Image load — LOLBIN tarafından amsi.dll yükleme

Kural referansı: **Amsi.DLL Loaded Via LOLBIN Process** (`6ec86d9e-...`), `status: test`, `level: medium`.

- **logsource:** `category: image_load` (Sysmon Event ID 7)
- **Mantık (kuralın birebir çekirdeği):** `ImageLoaded|endswith: '\amsi.dll'` **ve** yükleyen `Image|endswith` şu ikili listeden biri: `\ExtExport.exe`, `\odbcconf.exe`, `\rundll32.exe`. Kuralın yorumunda `regsvr32.exe` kasıtla dışarıda bırakılmıştır çünkü meşru olarak `amsi.dll` çağırır (false positive kaynağı). Bu ayrıntı, kural yazımında bağlam bilgisinin önemini gösterir.
- **Eşik:** `medium`. Tek olay alarm üretir ama triage gerektirir; çünkü LOLBIN yükleme desenleri kurumsal ortamda ara sıra meşru olabilir.

### Katmanlı tespit stratejisi

Bu kuralları birlikte düşünmek gerekir. En sağlam yaklaşım, farklı log kaynaklarını (registry_set, registry_delete, process_creation, image_load) tek bir "AMSI/ETW tamper" korelasyon senaryosunda birleştirmektir: aynı host'ta kısa bir zaman penceresinde hem AMSI registry değişikliği hem de beklenmedik `amsi.dll` yüklemesi görülürse, güven skoru tek başına her bir olaydan çok daha yükselir.

---

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırgan tespiti nasıl atlatmaya çalışır

- **Registry yerine yalnızca bellek içi yama:** En etkili kaçınma, hiç registry'ye dokunmadan sürecin kendi belleğindeki `amsi.dll` giriş noktasını yamalamaktır. Bu, bölüm 3'teki registry ve command-line kurallarını (`aa37cbb0`, `41d1058a`, `7dbbcac2`, `33efc23c`) tamamen atlar; çünkü ne registry_set/delete ne de `reg`/`Set-ItemProperty` komut satırı üretir.
  - **Savunmacı karşılığı:** Bu senaryo için registry telemetrisi kördür; bunun yerine **image_load** ve **script içerik** telemetrisine yaslanmak gerekir. `amsi.dll` yüklendikten hemen sonra bilinen atlatma reflection dizelerinin (`AmsiUtils`, `amsiInitFailed`, `[Ref].Assembly.GetType`) Script Block Logging (4104) veya AMSI'nin kendi buffer içeriğinde görülmesi, in-memory patch'i dolaylı yakalar. Ayrıca EDR'ın memory-integrity / `amsi.dll` code section bütünlüğü izlemesi bu boşluğu kapatır.

- **Komut satırı obfuscation'ı:** `reg delete` yerine karakter kaçırma, ortam değişkeni birleştirme veya alternatif encoding ile `CommandLine|contains` eşleşmelerinden kaçmak. `7dbbcac2` gibi command-line kuralları bu tür kaçırmaya karşı hassastır.
  - **Savunmacı karşılığı:** Command-line kurallarını registry olay kurallarıyla (registry_set/delete) yedeklemek. Registry olayı `TargetObject` alanını gerçek, normalize edilmiş yol olarak kaydeder; komut satırı ne kadar obfuscate edilse de sonuçta oluşan registry değişikliği aynı `\AMSI\Providers\` yoluna düşer ve `aa37cbb0`/`41d1058a` yakalar. Bu, "iki farklı telemetri katmanının aynı davranışı yakalaması" ilkesinin neden değerli olduğunu gösterir.

- **LOLBIN listesinin dışına çıkma:** `6ec86d9e` kuralı sabit bir ikili listesi (`ExtExport.exe`, `odbcconf.exe`, `rundll32.exe`) kullanır. Saldırgan `amsi.dll`'i listede olmayan başka bir imzalı süreç içine yükleyerek kaçabilir. Kuralın kendi içindeki `# TODO: Add more interesting processes` yorumu bu sınırlamayı açıkça kabul eder.
  - **Savunmacı karşılığı:** Allowlist (izin listesi) mantığına geçmek: "`amsi.dll` yükleyen süreç, bilinen meşru script motorları / güvenlik ürünleri kümesinin **dışındaysa** alarm ver." Bu, denylist'in aksine yeni LOLBIN'leri otomatik kapsar. Baseline'ı (hangi süreçler normalde `amsi.dll` yükler) çıkararak anomali eşiği kurmak en dayanıklı yöntemdir.

- **ETW sessizleştirme ile telemetriyi kesme:** Saldırgan ETW'yi kör ederse Script Block Logging (4104) durur, dolayısıyla içerik tabanlı tespitler kaybolur.
  - **Savunmacı karşılığı:** **Telemetrinin yokluğunu bir sinyal olarak izlemek.** Aktif bir kullanıcı oturumunda `powershell.exe` çalışıyorken beklenen PowerShell operational olaylarının aniden kesilmesi, ETW tampering göstergesidir. Ayrıca EDR'ın çekirdek/sürücü seviyesi telemetrisi (kullanıcı modu ETW yamasından etkilenmez) bu boşluğu kapatır.

### 4.2 Tipik false positive kaynakları ve ayıklama

- **`regsvr32.exe`'nin meşru `amsi.dll` çağrısı:** `6ec86d9e` kuralı bunu bilerek listeden çıkarmıştır. Kendi kurallarınızı yazarken bu istisnayı korumak, gereksiz alarm selini engeller.
- **Güvenlik ürünlerinin ve yönetim araçlarının AMSI provider kaydı yazması/güncellemesi:** Bir antivirüs kurulumu veya güncellemesi meşru olarak `\AMSI\Providers\` altına yazabilir. Ayıklama yöntemi: yükleyen sürecin imza durumu (signed publisher), yolun `Program Files` altında olması ve olay zamanının bilinen bir yazılım kurulum/güncelleme penceresine denk gelmesi.
- **Kurumsal yapılandırma/GPO araçları:** Merkezi yönetim bazen AMSI ile ilişkili registry değerlerine dokunabilir. Ayıklama: değişikliği yapan hesabın bir servis/yönetim hesabı olması ve `reg.exe`/`Set-ItemProperty` çağrısının bilinen bir yönetim otomasyonu bağlamından (SCCM, Intune, GPO client) gelmesi.
- **Geliştirici ve güvenlik araştırma makineleri:** AMSI atlatma dizeleri (`AmsiUtils` vb.) güvenlik araştırmacılarının, pentester'ların ve eğitim ortamlarının makinelerinde meşru olarak görülebilir. Ayıklama: bu makineleri ayrı bir varlık grubuna (asset group) koyup eşiği ona göre ayarlamak; production sunucularında ise **sıfır tolerans** uygulamak.

### 4.3 Tuning ve olgunluk önerileri

En sağlam tespit duruşu tek bir kurala değil, **savunma derinliğine** dayanır: registry (registry_set + registry_delete), process_creation (command line), image_load ve script içerik (4104) katmanlarını birbirini yedekleyecek şekilde birlikte devreye almak. Saldırgan bir katmanı atlatsa bile diğerinde iz bırakır. False positive'i azaltmak için host'u role göre gruplayın (sunucu, iş istasyonu, geliştirici/güvenlik makinesi) ve her grup için farklı eşik ve şiddet uygulayın. Son olarak, körleştirmenin ardından gelen davranışı (in-memory payload, C2, credential access) korelasyon zincirine ekleyin: AMSI/ETW tamper nadiren tek başına gelir; bir saldırı zincirinin ortasındaki "ışıkları söndürme" adımıdır ve öncesi ile sonrası birlikte değerlendirildiğinde tespit güveni en yükseğe çıkar.
