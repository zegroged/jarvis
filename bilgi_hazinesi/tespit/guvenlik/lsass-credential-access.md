# LSASS Credential Access — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin önce saldırının LSASS
> üzerinde neyi istismar ettiğini kavramsal olarak anlatır, sonra bıraktığı
> izleri ve bu izlere dayanan **tespit mantığını** kurar. Amaç savunma ve
> detection engineering'dir; canlı, adım adım operasyonel saldırı reçetesi
> değildir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Windows'ta **LSASS** (Local Security Authority Subsystem Service,
`lsass.exe`) kimlik doğrulamanın kalbidir. Kullanıcı oturum açtığında,
Single Sign-On (SSO) deneyimini sağlamak için LSASS, kimlik bilgilerinin
çeşitli türevlerini kendi süreç belleğinde tutar: NTLM hash'leri,
Kerberos TGT/TGS bilet malzemesi, bazı yapılandırmalarda WDigest
üzerinden düz metin parolalar, DPAPI master key materyali ve cached
domain credentials. MITRE ATT&CK bu davranışı **T1003 — OS Credential
Dumping**, özellikle **T1003.001 — LSASS Memory** altında sınıflandırır.

Saldırganın kavramsal amacı basittir: makinede yeterli yetkiye
(genellikle local admin / `SeDebugPrivilege`) ulaştıktan sonra, LSASS'ın
bellek içeriğine erişip bu kimlik bilgisi türevlerini dışarı çekmek.
Elde edilen hash veya bilet, **lateral movement** (Pass-the-Hash,
Pass-the-Ticket) ve **privilege escalation** için doğrudan kullanılabilir.
Yani LSASS dump, tek bir makineyi ele geçirmekten tüm domain'i ele
geçirmeye giden köprüdür — bu yüzden kimlik erişim zincirinin en kritik
halkasıdır.

Saldırganın LSASS belleğine ulaşmak için başvurduğu **kavramsal yollar**
şunlardır (detection'ı anlamak için bunları tanımak gerekir):

- **Bellek dökümü (memory dump) alma:** LSASS sürecinin çalışan bellek
  görüntüsünü diske bir `.dmp` dosyası olarak yazmak. Bu, Task Manager'ın
  "Create dump file" özelliğinden, `procdump` gibi araçlardan, ya da
  `MiniDumpWriteDump` API'sini çağıran özel araçlardan yapılabilir. Döküm
  sonra çevrimdışı bir makinede parse edilir — bu, tespit açısından
  önemlidir çünkü asıl parse işlemi kurban makinede olmayabilir, ama
  **döküm oluşturma anı** iz bırakır.
- **Doğrudan süreç belleği okuma:** `OpenProcess` ile LSASS handle'ı
  alıp `ReadProcessMemory` ile belleği okumak. Klasik credential dumping
  araçları bunu yapar; genellikle dump/parse için `dbghelp.dll` veya
  `dbgcore.dll` gibi debugging kütüphanelerini yükler.
- **Debugging altyapısını kötüye kullanma:** Debug amaçlı tasarlanmış
  DLL'ler ve API'ler (comsvcs.dll'in MiniDump export'u gibi), meşru
  görünürken LSASS belleğini diske dökmek için istismar edilir.
- **Keşif (reconnaissance):** Saldırgan dump işleminden önce ya da sonra
  LSASS'ın PID'sini bulmak için `tasklist`/`findstr` gibi araçlarla süreç
  listesini tarar.

Önemli kavramsal nokta: LSASS **korumalı ve meşru** bir süreçtir. Onu
"okuyan" ya da ondan "döküm alan" çok az meşru senaryo vardır (AV/EDR,
bazı yedekleme ve teşhis araçları). Bu düşük meşru trafik, tespiti
mümkün kılan şeydir: LSASS'a normalde kimin dokunması gerektiği dar bir
kümedir, bu kümenin dışındaki her erişim şüphelidir.

---

## 2. Bıraktığı izler / artefaktlar

Detection engineering açısından LSASS credential access, telemetride
görece "gürültülü" bir tekniktir çünkü işletim sistemi çekirdeği ve
Sysmon bu etkileşimleri zengin biçimde loglar. Başlıca artefakt
kategorileri:

**a) Süreç erişim olayları (process access) — Sysmon Event ID 10**
LSASS belleğine erişmek için bir süreç `OpenProcess` çağırdığında,
Sysmon **Event ID 10 (ProcessAccess)** üretir. Bu olayın kritik
alanları:
- `TargetImage`: erişilen hedef süreç — burada `C:\Windows\System32\lsass.exe`.
- `SourceImage`: erişimi yapan süreç.
- `GrantedAccess`: talep edilen erişim maskesi. Bellek okumak/döküm almak
  için tipik olarak `0x1010`, `0x1410`, `0x1438`, `0x143a` gibi
  `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION` bitlerini içeren maskeler
  görülür.
- `CallTrace`: erişimin çağrı yığını. Bu alanda **`dbgcore.dll`** veya
  **`dbghelp.dll`** gibi debugging DLL'lerinin görünmesi güçlü bir
  sinyaldir, çünkü bu kütüphaneler `MiniDumpWriteDump`'ı barındırır ve
  meşru bir uygulamanın LSASS'ı bu şekilde okuması nadirdir.

**b) Dosya oluşturma olayları (file creation) — Sysmon Event ID 11**
LSASS belleği diske döküldüğünde bir dump dosyası yazılır. Sysmon
**Event ID 11 (FileCreate)** bu artefaktı yakalar. İlgili alanlar:
- `Image`: dosyayı oluşturan süreç (örn. `taskmgr.exe`).
- `TargetFilename`: yazılan dosya yolu — örneğin Task Manager LSASS
  dökümünü `%TEMP%\lsass.DMP` benzeri bir yola yazar.
`lsass` adını içeren veya `.dmp` uzantılı, LSASS ile ilişkili dosyaların
oluşumu doğrudan artefakttır.

**c) Süreç oluşturma olayları (process creation) — Sysmon Event ID 1 /
Windows Security 4688**
Keşif ve dump araçlarının çalıştırılması komut satırı desenleri bırakır:
- `findstr` / `tasklist` ile LSASS PID keşfi: `tasklist` çıktısında
  `lsass` string'ini arayan komut satırları.
- Dump araçlarının komut satırında `lsass` hedefinin, `-ma` (full dump)
  gibi bayrakların veya `MiniDump` çağrılarının görünmesi.
İlgili alanlar: `CommandLine`, `Image`, `ParentImage`.

**d) Antivirus / EDR imza uyarıları**
AV motorları credential dumper ve stealer'ları imza ile yakalar. Bir AV
olayının `Signature` alanında `PWS`, `DCSync`, `Creddump`, `DumpCreds`,
`Certify`, `Mimikatz` benzeri imza adlarının görünmesi, credential access
girişiminin (bloke edilmiş olsa bile) kanıtıdır. Bu, `logsource:
category: antivirus` altında değerlendirilir.

**e) Ağ üzerinden hassas dosya transferi — Zeek SMB**
Dump alındıktan sonra saldırgan çıktıyı ağ paylaşımı üzerinden dışarı
taşıyabilir. Zeek'in `smb_files` servisi, paylaşım üzerinden okunan/
yazılan dosya adlarını loglar. `\lsass`, `\windows\minidump\`,
`\mimidrv`, `\sam`, `\ntds.dit`, `\security`, `\hiberfil` gibi kimlik
verisi içeren iyi bilinen dosya adları, `name` alanında görüldüğünde
credential exfiltration artefaktıdır.

**f) Registry izi (bağlamsal)**
WDigest ile düz metin parola yakalamayı etkinleştirmek için saldırgan
`HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest`
altında `UseLogonCredential=1` ayarlayabilir. Bu, LSASS dump'ının
değerini artıran bir hazırlık artefaktıdır.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki tespit mantığı, verilen **gerçek Sigma kurallarına** demirlidir;
log kaynağı, event ID ve field adları bu kurallardan alınmıştır.

### 3.1 Task Manager ile LSASS bellek dökümü (file_event)
**Demir:** `LSASS Process Memory Dump Creation Via Taskmgr.EXE`
(rule id `69ca12af-119d-44ed-b50f-a47af0ebc364`), provider
`Microsoft-Windows-Sysmon`, kategori **file_event**.

Mantık: Sysmon **Event ID 11 (FileCreate)** üzerinde, dosyayı oluşturan
süreç `taskmgr.exe` iken oluşturulan dosyanın adı LSASS dökümüne işaret
ediyorsa alarm ver. Task Manager'ın "Create dump file" özelliği meşru bir
teşhis aracıdır, ama **LSASS** hedefli döküm neredeyse her zaman kimlik
hırsızlığı niyetlidir.

```
logsource:
  category: file_event
  product: windows
detection:
  selection:
    Image|endswith: '\taskmgr.exe'
    TargetFilename|contains: 'lsass'
    TargetFilename|endswith: '.dmp'   # örn. lsass.DMP
  condition: selection
level: high
```

### 3.2 Debugging DLL'leri ile LSASS'a şüpheli erişim (process_access)
**Demir:** `Suspicious Process Access to LSASS with Dbgcore/Dbghelp DLLs`
(rule id `9f5c1d59-33be-4e60-bcab-85d2f566effd`), provider
`Microsoft-Windows-Sysmon`, kategori **process_access**.

Mantık: Sysmon **Event ID 10 (ProcessAccess)** üzerinde, `TargetImage`
`lsass.exe` iken erişimin `CallTrace` alanı **`dbgcore.dll`** veya
**`dbghelp.dll`** içeriyorsa alarm ver. Bu DLL'ler `MiniDumpWriteDump`'ı
barındırır; LSASS'a bunları içeren bir çağrı yığınıyla erişim, bir bellek
dökümü girişiminin güçlü göstergesidir. İstersen `GrantedAccess`
maskesini de (`PROCESS_VM_READ` biti içeren değerler) daraltıcı koşul
olarak ekleyebilirsin.

```
logsource:
  category: process_access
  product: windows
detection:
  selection:
    TargetImage|endswith: '\lsass.exe'
    CallTrace|contains:
      - 'dbgcore.dll'
      - 'dbghelp.dll'
  condition: selection
level: high
```

### 3.3 Findstr ile LSASS keşfi (process_creation)
**Demir:** `LSASS Process Reconnaissance Via Findstr.EXE`
(rule id `fe63010f-8823-4864-a96b-a7b4a0f7b929`), provider
`Microsoft-Windows-Sysmon`, kategori **process_creation**.

Mantık: Süreç oluşturma olayında (**Sysmon Event ID 1** / Windows
Security **4688**), `findstr` süreç listesini `lsass` string'i için
tarıyorsa alarm ver. Bu, dump öncesi PID keşfinin tipik bir işaretidir;
tek başına düşük gürültülü, ama diğer LSASS sinyalleriyle korele
edildiğinde değerlidir. `CommandLine` alanında hem `lsass` hem de süreç
listeleme bağlamı aranır (örn. `tasklist ... | findstr ... lsass`).

```
logsource:
  category: process_creation
  product: windows
detection:
  selection:
    Image|endswith: '\findstr.exe'
    CommandLine|contains: 'lsass'
  condition: selection
level: medium
```

### 3.4 AV imzası — password dumper (antivirus)
**Demir:** `Antivirus - Password Dumper Signature`
(rule id `78cc2dd2-7d20-4d32-93ff-057084c38b93`), kategori **antivirus**,
etiketler `attack.credential-access`, `attack.t1003`, `attack.t1003.001`,
`attack.t1003.002`, `attack.t1558`.

Mantık: AV olayının `Signature` alanı `PWS` ile başlıyorsa ya da
`Certify`, `DCSync`, `Creddump`, `DumpCreds` gibi bilinen credential
dumper imza adlarını içeriyorsa yüksek öncelikli alarm ver. Kritik
operasyonel not: **AV malware'i bloke etmiş olsa bile bu olay
yoksayılmamalıdır** — dosyanın makineye ilk nasıl geldiği araştırılmalı
ve gerekiyorsa etkilenen parolalar sıfırlanmalıdır.

```
logsource:
  category: antivirus
detection:
  selection:
    - Signature|startswith: 'PWS'
    - Signature|contains:
        - 'Certify'
        - 'DCSync'
        - 'Creddump'
        - 'DumpCreds'
  condition: selection
level: high
```

### 3.5 Ağ paylaşımı üzerinden kimlik verisi transferi (Zeek SMB)
**Demir:** `Transferring Files with Credential Data via Network Shares - Zeek`
(rule id `2e69f167-47b5-4ae7-a390-47764529eff5`), product **zeek**,
service **smb_files**.

Mantık: Zeek SMB dosya olaylarında, `name` alanı kimlik verisiyle
ilişkili iyi bilinen dosya adlarından birini içeriyorsa alarm ver:
`\lsass`, `\windows\minidump\`, `\mimidrv`, `\sam`, `\ntds.dit`,
`\security`, `\hiberfil`, `\sqldmpr`. Bu, dump çıktısının ya da doğrudan
hassas sistem dosyalarının ağ üzerinden taşınmasını (exfiltration ya da
lateral collection) yakalar.

```
logsource:
  product: zeek
  service: smb_files
detection:
  selection:
    name:
      - '\lsass'
      - '\windows\minidump\'
      - '\mimidrv'
      - '\sam'
      - '\ntds.dit'
      - '\security'
      - '\hiberfil'
  condition: selection
level: medium
```

### 3.6 Korelasyon önerisi
Bu sinyaller tek tek de değerli ama **korelasyon** tespiti güçlendirir.
Örnek yüksek güvenli senaryo: kısa bir zaman penceresinde (örn. 5 dk)
aynı host üzerinde (3.3) findstr LSASS keşfi + (3.2) dbgcore/dbghelp ile
LSASS process access + (3.1) `lsass*.dmp` dosya oluşumu görülürse, bu
neredeyse kesin bir credential dumping zinciridir ve en yüksek önceliğe
yükseltilmelidir. Tek başına düşük seviyeli (medium) keşif olayları,
bir döküm/erişim olayıyla eşleştiğinde birlikte incelenmelidir.

---

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırgan tespiti nasıl atlatmaya çalışır

- **CallTrace gizleme / DLL kaçınması:** 3.2'deki tespit `dbgcore.dll` /
  `dbghelp.dll`'in çağrı yığınında görünmesine dayanır. Saldırgan bu
  kütüphaneleri hiç yüklemeden, kendi `MiniDumpWriteDump` implementasyonu
  ya da doğrudan syscall'larla dump alarak `CallTrace` imzasını
  kırmayı hedefleyebilir. **Karşı-tedbir:** yalnızca `CallTrace`'e
  güvenme; `TargetImage=lsass.exe` üzerindeki *tüm* şüpheli
  `GrantedAccess` maskelerini (PROCESS_VM_READ içeren) taban çizgisi
  dışı source süreçler için izle. LSASS'a dokunması beklenen süreçlerin
  bir allowlist'ini kur; bu listenin dışındaki her ProcessAccess
  olayını incele.
- **Farklı dump aracı / LOLBIN kullanımı:** 3.1 özellikle `taskmgr.exe`
  hedefler. Saldırgan Task Manager yerine başka bir LOLBIN veya özel araç
  kullanabilir. **Karşı-tedbir:** dosya oluşturma tespitini `Image`'dan
  bağımsız olarak `TargetFilename|contains: 'lsass'` + `.dmp` üzerine de
  kur; kaynak sürecin ne olduğuna bakmadan LSASS'a ait bir döküm dosyası
  oluşumunu yakala.
- **Dosya adını / uzantısını değiştirme:** Çıktıyı `lsass.dmp` yerine
  jenerik bir ada (`update.bin`, `log.tmp`) yazmak, ad tabanlı 3.1 ve 3.5
  tespitlerini atlatabilir. **Karşı-tedbir:** ad tabanlı tespiti tek
  savunma katmanı yapma; asıl güvenilir sinyal, LSASS'a **process
  access** anıdır (3.2) — dosya adı ne olursa olsun belleğe erişim
  gerçekleşmek zorundadır. Ayrıca çıktı dosyasının içerik imzası
  (minidump magic header `MDMP`) EDR ile taranabilir.
- **Keşifsiz çalışma:** Saldırgan LSASS PID'sini findstr yerine doğrudan
  API ile bulup 3.3'ü tetiklemeyebilir. Bu yüzden keşif tespiti
  yardımcıdır, birincil değildir.
- **Ağ yerine yerel exfiltration:** 3.5 SMB'ye dayanır; saldırgan dökümü
  HTTPS ya da bulut depolama üzerinden çıkarırsa SMB tespiti atlanır.
  **Karşı-tedbir:** exfiltration'ı tek katmana bağlama; asıl önleme dump
  oluşumu anında olmalı.

### 4.2 Savunmacının katmanlı yaklaşımı

- **LSASS koruması:** RunAsPPL (Protected Process Light) ile LSASS'ı
  korumalı süreç olarak çalıştır; Credential Guard'ı etkinleştir. Bu,
  birçok kullanıcı-modu dump tekniğini kaynağında engeller ve tespit
  yükünü azaltır.
- **Attack Surface Reduction:** LSASS'tan credential çalmayı engelleyen
  ASR kuralını etkinleştir.
- **Allowlist temelli tespit:** LSASS'a meşru erişen süreçlerin dar
  listesini (AV/EDR, belirli teşhis araçları) çıkar; her ProcessAccess
  olayını bu taban çizgisine göre değerlendir. Sapmalar birincil
  sinyaldir.
- **Zincir korelasyonu:** Tekil düşük seviyeli olaylar yerine 3.6'daki
  gibi zincirleri yükselt.

### 4.3 Tipik false positive kaynakları ve ayıklama

- **Meşru AV/EDR ve teşhis araçları:** Güvenlik ürünlerinin kendisi
  LSASS'a erişir. Bunları `SourceImage`/imzalı yayıncıya göre allowlist'e
  al; ama kör allowlist yapma — saldırganlar güvenilir isimleri taklit
  edebilir, imzayı (signer) de doğrula.
- **Meşru çökme dökümü:** LSASS gerçekten çökerse Windows Error Reporting
  (WER) meşru bir döküm yazabilir. WER süreç bağlamını (`werfault.exe`) ve
  standart WER yollarını dikkate alarak ayıkla; ama LSASS'ı kasten
  çökertip WER dökümünü toplamanın da bir teknik olduğunu unutma —
  şüpheli süreç erişimiyle birlikte gelen dökümleri incele.
- **Yedekleme / yönetim araçları:** Bazı yedekleme ve sistem yönetim
  araçları hassas dosyalara (`\sam`, `\security`, `\ntds.dit`) meşru
  erişir; özellikle Domain Controller'larda `ntds.dit` erişimi normal
  olabilir. 3.5 için: erişimi yapan hesabın/hostun beklenen bir yönetim
  bağlamı olup olmadığını, kaynağın DC'nin kendisi mi yoksa rastgele bir
  iş istasyonu mu olduğunu değerlendir. Sigma kuralının belirttiği gibi,
  meşru yönetici işi false positive kaynağıdır.
- **findstr gürültüsü (3.3):** `findstr lsass` yasal betiklerde/sağlık
  kontrollerinde görülebilir; bu yüzden medium seviyededir ve tek başına
  aksiyona götürmemeli, korelasyonda kullanılmalı.
- **AV imza uyarısı (3.4):** Bloke edilmiş bir tespit "temizlendi" diye
  kapatılmamalı. Kural açıkça uyarır: olay yoksayılmamalı; malware'in
  makineye giriş yolu araştırılmalı ve gerekiyorsa parolalar
  sıfırlanmalıdır — bloke, kök nedeni çözmez.

**Özet:** LSASS credential access tespitinin bel kemiği, LSASS'a **process
access** anını (Sysmon Event ID 10, `TargetImage=lsass.exe`) ve LSASS
**döküm dosyası** oluşumunu (Event ID 11) izlemektir; bunlara AV imza,
Zeek SMB ve keşif sinyalleri eklenerek katmanlı, korelasyonlu bir tespit
kurulur. En sağlam yaklaşım, ad/araç tabanlı tekil imzalara güvenmek
yerine "LSASS'a normalde kimin dokunması gerektiği" taban çizgisini
kurup sapmaları avlamaktır.
