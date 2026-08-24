# Şüpheli PowerShell (Encoded / Obfuscated) — Tespiti

> İlke: "Hırsızı tanımadan mücevheri koruyamazsın." Önce saldırganın PowerShell'i neden ve nasıl silah olarak kullandığını anlarız; sonra bu davranışın loglarda bıraktığı izleri gerçek tespit kurallarına demirleyerek yakalarız. Bu metnin amacı savunma ve tespittir; canlı bir saldırı reçetesi değildir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

PowerShell, saldırgan için neredeyse ideal bir araçtır ve buna literatürde "Living off the Land Binary" (LOLBin) denir. Sisteme yeni bir zararlı `.exe` bırakmaya gerek yoktur; Windows'un içinde zaten güvenilir, imzalı, her yerde bulunan bir yorumlayıcı vardır. Saldırgan neyi istismar eder?

**1. Meşru bir aracın güvenilirliğini istismar eder.** `powershell.exe` Microsoft tarafından imzalıdır ve çoğu allow-list / uygulama beyaz listesi tarafından serbest bırakılır. AppLocker veya WDAC gibi kontrolleri aşmanın en kolay yolu, izin verilen bir aracı kötüye kullanmaktır.

**2. Diskten bağımsız (fileless) çalışma yeteneğini istismar eder.** PowerShell, kodu diske hiç yazmadan doğrudan bellekte çalıştırabilir. Bunun kavramsal kalbi `Invoke-Expression` (kısaca `IEX`) cmdlet'idir: bir string'i alır ve onu PowerShell komutu olarak yürütür. Saldırgan zararlı kodu bir string olarak indirir (`(New-Object Net.WebClient).DownloadString(...)`) ve doğrudan `IEX`'e verir. Böylece disk üzerinde taranacak bir dosya kalmaz — antivirüs imza taramasının kör noktasıdır.

**3. İnsan gözünü ve basit imza tabanlı savunmayı istismar eder (obfuscation).** Analist veya basit bir regex, `Invoke-Mimikatz` gibi bir string arar. Saldırgan bunu gizlemek için birkaç kavramsal katman kullanır:

- **Base64 / EncodedCommand:** `powershell.exe -EncodedCommand <base64>` (veya `-Enc`, `-e`) parametresi, UTF-16LE kodlanmış ve Base64'e çevrilmiş bir komut alır. Amaç tırnak/kaçış sorunlarını çözmektir ama saldırgan bunu asıl niyeti gizlemek için kullanır. Base64 bloğu insan gözüne anlamsız görünür.
- **String manipülasyonu:** `-join`, `[char[]]`, `+` ile birleştirme, `-replace`, `[Convert]::FromBase64String`, backtick (`` ` ``) karakter araya sokma, format operatörü (`-f`) ile parça parça yeniden kurma.
- **Ortam ve yürütme bayrakları:** Saldırgan tipik olarak pencereyi gizler ve profili/etkileşimi kapatır: `-NoProfile` (`-NoP`), `-NonInteractive` (`-NonI`), `-WindowStyle Hidden` (`-W Hidden`), `-ExecutionPolicy Bypass` (`-ep bypass`). Bunlar tek başına bir tespit sinyali kümesidir çünkü meşru bir kullanıcı nadiren hepsini aynı anda kullanır.

**4. Yürütme politikasının bir güvenlik sınırı olmamasını istismar eder.** `-ExecutionPolicy Bypass` ile ExecutionPolicy tamamen atlanır; Microsoft'un kendisi bunun bir güvenlik özelliği olmadığını söyler, yalnızca kaza eseri script çalıştırmayı önler.

**5. Komuta-kontrol (C2) ve indirme davranışını gizler.** Zararlı payload'ı çekmek için PowerShell'in ağ cmdlet'leri (`DownloadString`, `DownloadFile`, `Invoke-WebRequest`, `Invoke-RestMethod`) kullanılır. İlginç bir kaçınma varyantı, payload'ı DNS TXT kayıtlarının içine gizleyip yanıtı `IEX` ile çalıştırmaktır (Nishang'ın `DNS_TXT_Pwnage` örneği). Böylece trafik "normal" DNS gibi görünür.

Kavramsal olarak akış şudur: **güvenilir yorumlayıcıyı çağır → niyeti gizle (encode/obfuscate) → payload'ı diske değmeden bellekte çalıştır → mümkünse ağ trafiğini de meşru göster.** Saldırganın kazandığı şey görünmezliktir; savunmacının işi bu görünmezliği kıran davranışsal ve telemetri izlerini yakalamaktır.

**6. Saldırgan neden bu kadar sık PowerShell'e döner?** Çünkü ATT&CK çerçevesinde tek bir teknik birçok taktiği aynı anda karşılar. `T1059.001` (Command and Scripting Interpreter: PowerShell) yürütme (execution) taktiğidir; ama aynı process içinde saldırgan `T1027` (Obfuscated Files or Information) ile gizlenme, `T1564.003` (Hidden Window) ile savunmadan kaçınma, `T1105` (Ingress Tool Transfer) ile indirme, `T1071.004` (DNS C2) ile komuta-kontrol yeteneklerini birleştirir. Yani tek bir `powershell.exe` çağrısı, öldürme zincirinin (kill chain) birçok halkasını tek satırda taşır. Savunmacının şansı da tam burada: bu kadar çok yeteneğin tek yere sıkışması, tek bir komut satırında olağandışı derecede yoğun bir sinyal kümesi bırakır. Meşru bir yönetici komutu bu kadar yeteneği aynı anda barındırmaz.

---

## 2. Bıraktığı izler / artefaktlar

"Fileless" olması, "izsiz" olduğu anlamına gelmez. Diskte bir dosya olmayabilir ama işlem oluşturma, PowerShell'in kendi loglaması ve ağ katmanı bol miktarda telemetri üretir.

### Süreç oluşturma (process creation) izleri
En değerli kaynak, `powershell.exe` başlatıldığında oluşan süreç oluşturma olayıdır:

- **Windows Security Log — Event ID 4688** ("A new process has been created"). Bu olayın `CommandLine` alanı (Command line auditing / `ProcessCommandLine` denetimi açıksa) tam komut satırını içerir. Not: Bu alanın dolması için "Include command line in process creation events" GPO ayarı gereklidir.
- **Sysmon — Event ID 1** ("Process Create"). `CommandLine`, `ParentImage`, `ParentCommandLine`, `Image`, `User`, `IntegrityLevel`, `Hashes` alanlarını verir. Detection engineering için altın standart budur.

Komut satırı desenleri — aranacak somut string'ler: `-EncodedCommand`, `-Enc`, `-e`, `-NoProfile`/`-NoP`, `-NonInteractive`/`-NonI`, `-WindowStyle Hidden`/`-W Hidden`, `-ExecutionPolicy Bypass`, `-Sta`, `-Command`, uzun Base64 blokları, `FromBase64String`, `IEX`, `Invoke-Expression`, `DownloadString`, `DownloadFile`, `Net.WebClient`.

### Ebeveyn-çocuk (parent-child) ilişkisi izleri
Süreç ağacı çok kritik bir artefakttır. `powershell.exe`'nin ebeveyni beklenmedik bir uygulama ise (örneğin `winword.exe`, `excel.exe`, `outlook.exe`, `mshta.exe`, `wscript.exe`, `cscript.exe`), bu bir makro/phishing zincirinin güçlü işaretidir. Sysmon Event ID 1'in `ParentImage` alanı bunu verir. Ayrıca `cmd.exe`'nin `start /b` veya `start /min` ile bir script'i arka planda/gizli başlatması (Sigma "Cmd Launched with Hidden Start Flags") aynı zincirin bir başka halkasıdır.

### PowerShell'in kendi loglama izleri
- **Script Block Logging — Event ID 4104** (Microsoft-Windows-PowerShell/Operational). Bu, obfuscation'a karşı en güçlü kaynaktır: PowerShell, `-EncodedCommand` ile verilen Base64'ü **çözdükten sonra**, gerçekte çalıştırdığı script bloğunu düz metin olarak loglar. Yani saldırganın gizlemeye çalıştığı asıl kod burada açığa çıkar. Ayrıca PowerShell, çok kademeli/şüpheli obfuscation gördüğünde otomatik olarak Warning seviyesinde 4104 üretir.
- **Module Logging — Event ID 4103** (pipeline yürütme detayları).
- **PowerShell engine start — Event ID 400/403/600** (klasik Windows PowerShell logu); özellikle `HostApplication` alanı komut satırını içerebilir ve `powershell -enc ...` gibi konsol-dışı barındırıcıları ele verir.

### Ağ izleri
- **DownloadString / DownloadFile** kullanıldığında, `New-Object Net.WebClient` varsayılan olarak **boş User-Agent** ile HTTP isteği yapar. Proxy loglarında `c-useragent` alanının boş olması (Sigma "HTTP Request With Empty User Agent") bunun izidir.
- **DNS TXT** tabanlı C2'de, DNS log kaynağında `record_type = TXT` ve `answer` içinde `IEX`, `Invoke-Expression`, `cmd.exe` gibi execution string'lerinin geçmesi (Sigma "DNS TXT Answer with Possible Execution Strings") çok belirgin bir artefakttır.

### Diğer artefaktlar
- Kalıcılık kuruluyorsa: Registry Run anahtarları, Scheduled Task (`schtasks`), WMI event subscription. Sysmon Event ID 12/13/14 (registry) ve 11 (file create) bunları yakalar.
- `AmsiScanBuffer` / AMSI baypası denemeleri; AMSI, script içeriğini yürütme anında AV'ye sunar, bu yüzden saldırganlar AMSI'yi devre dışı bırakmaya çalışır — bu da 4104 loglarında görünür.

### İzlerin neden kalıcı olduğunu anlamak
Saldırganın en büyük yanılgısı, "fileless" olmanın "telemetriden muaf" olmakla aynı şey olduğunu sanmasıdır. Diskte tarayacak bir dosya olmaması, disk-tabanlı antivirüsü atlatır; ama üç katman saldırganın kontrolü dışındadır:

1. **İşletim sistemi çekirdeği süreç oluşturmayı loglar.** `powershell.exe` başladığı an, komut satırı argümanlarıyla birlikte 4688 / Sysmon 1 üretilir. Saldırgan bu argümanları kullanmak zorundadır — çünkü payload'ı bir şekilde process'e geçirmesi gerekir.
2. **PowerShell motorunun kendisi loglar.** Script Block Logging, saldırganın kod yürütme kararını verdiği andan sonra devreye girer; yani gizleme katmanları soyulduktan *sonra*. Saldırgan kodu çalıştırmak istiyorsa, motor onu görmek zorundadır, dolayısıyla loglayabilir.
3. **Ağ katmanı loglar.** Payload dışarıdan çekiliyorsa, proxy ve DNS sunucusu bu isteği görür; içeriye doğru trafik saldırganın gizleyemeyeceği fiziksel bir gerçekliktir.

Bu üç katmanın hepsini aynı anda kör etmek pratikte çok zordur; savunmacının stratejisi bu yüzden **derinlemesine savunma** ve kaynak korelasyonudur.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki mantık tamamen size verilen gerçek Sigma kurallarının `logsource`, field ve koşullarına dayanır. Uydurma field/event kullanmadan, bu kuralların mantığını Türkçe açıklıyorum.

### 3.1 Komut satırı parametre kombinasyonu (process_creation)
"HackTool - Covenant PowerShell Launcher" ve "HackTool - Empire PowerShell Launch Parameters" kuralları aynı temel fikri kullanır: **tek bir bayrak değil, bayrak kümesinin bir arada bulunması** alarm üretir. Meşru kullanıcı `-NoProfile` kullanabilir, `-WindowStyle Hidden` kullanabilir; ama `-Sta -NoProfile -WindowStyle Hidden` üçlüsü + `-EncodedCommand` aynı komut satırında görülünce false positive olasılığı çöker.

- `logsource`: `category: process_creation`, `product: windows`
- Covenant kuralının mantığı (`selection_1`): `CommandLine` **hepsini** içeriyor mu → `-Sta`, `-Nop`, `-Window`, `Hidden`; **ve** `CommandLine` şunlardan birini içeriyor → `-Command` veya `-EncodedCommand`.
- Empire kuralının mantığı: `CommandLine` şu spesifik dizilimi içeriyor → `' -NoP -sta -NonI -W Hidden -Enc '`. Yani parametrelerin bu sıralı ve kısaltılmış hali, insan elinden çıkmış normal bir komuta benzemez; bir framework imzasıdır.

**Sigma-benzeri örnek 1 — Encoded + gizli pencere + profilsiz kombinasyon:**

```yaml
title: Suspicious PowerShell Encoded Command with Stealth Flags
logsource:
    category: process_creation
    product: windows
detection:
    selection_img:
        Image|endswith: '\powershell.exe'
    selection_enc:
        CommandLine|contains:
            - '-EncodedCommand'
            - '-Enc '
            - ' -e '
    selection_stealth:
        CommandLine|contains|all:
            - 'Hidden'
            - '-NoP'
    condition: selection_img and selection_enc and selection_stealth
level: high
```

Bu, verilen Covenant/Empire kurallarının mantığının sadeleştirilmiş bir uyarlamasıdır: aynı `CommandLine|contains|all` yaklaşımıyla "encoded + gizli + profilsiz" üçlüsünü arar.

### 3.2 Boş User-Agent ile indirme (proxy)
"HTTP Request With Empty User Agent" kuralı, `(New-Object Net.WebClient).DownloadString` çağrısının ürettiği boş User-Agent'ı hedefler.

- `logsource`: `category: proxy`
- Koşul: `c-useragent` alanı boş string (`''`).
- Mantık: Modern tarayıcılar ve çoğu meşru uygulama daima bir User-Agent gönderir. Boş UA, script/otomasyon kaynaklı bir isteğin işaretidir. Tek başına `level: medium`'dur çünkü bazı meşru araçlar da boş UA gönderebilir; bu yüzden başka sinyallerle (aynı host'ta process_creation alarmı) korelasyon önerilir.

### 3.3 DNS TXT içinde execution string (dns)
"DNS TXT Answer with Possible Execution Strings" kuralı DNS tabanlı C2/indirme davranışını yakalar.

- `logsource`: `category: dns`
- Koşul: `record_type = 'TXT'` **ve** `answer` içeriyor → `IEX` veya `Invoke-Expression` veya `cmd.exe`.
- Mantık: Meşru bir TXT kaydı SPF/DKIM/domain doğrulama metni taşır; içinde `IEX` veya `Invoke-Expression` geçmesi neredeyse kesinlikle kötücüldür. `level: high`.

**Sigma-benzeri örnek 2 — indirme + yürütme string'inin birlikteliği (script block log):**

```yaml
title: PowerShell Download Cradle in Script Block
logsource:
    product: windows
    service: powershell   # Event ID 4104 - Script Block Logging
detection:
    selection:
        ScriptBlockText|contains|all:
            - 'Net.WebClient'
            - 'DownloadString'
        keywords:
            ScriptBlockText|contains:
                - 'IEX'
                - 'Invoke-Expression'
    condition: selection and keywords
level: high
```

Buradaki kritik nokta: **Event ID 4104 obfuscation'ı çözer.** `-EncodedCommand cwB2ACAAbwAgA...` gibi Base64 komut satırında görünse bile, 4104 çözülmüş `ScriptBlockText`'i loglar; bu yüzden `IEX + DownloadString` deseni Base64 katmanının altından açığa çıkar. Covenant kuralının `-EncodedCommand cwB2ACAAbwAgA` gibi bilinen Base64 prefix'lerini `CommandLine`'da araması da tamamlayıcı bir yaklaşımdır — çünkü bazı framework payload'ları her zaman aynı UTF-16LE başlangıcıyla kodlanır.

### Katmanlı tespit özeti
Sağlam bir tespit tek kurala değil, bu kaynakların korelasyonuna dayanır:
1. **process_creation (4688 / Sysmon 1):** parametre kombinasyonu + şüpheli ebeveyn.
2. **PowerShell Operational (4104):** çözülmüş script içeriğinde `IEX`, `DownloadString`, AMSI baypas string'leri.
3. **proxy:** boş User-Agent.
4. **dns:** TXT içinde execution string.
Aynı host ve zaman penceresinde iki veya daha fazlasının çakışması, high-fidelity bir alarmdır.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırgan tespiti nasıl atlatmaya çalışır

**a) Base64 yerine katmanlı obfuscation.** Saldırgan `-EncodedCommand` kullanmaz, çünkü bu string'in kendisi bir imzadır. Bunun yerine string'i çalışma anında kurar: `-join`, `-f` format operatörü, `[char]` dizileri, `-replace`, backtick araya sokma, değişken parçalama. Böylece komut satırında `IEX` bile görünmez.
- **Karşı-tespit:** Burada **Script Block Logging (4104)** belirleyicidir. Komut satırı ne kadar gizlense de, PowerShell kodu yürütmek için sonunda çözülmüş bloğu değerlendirir ve loglar. Ayrıca PowerShell, aşırı obfuscation'ı sezip otomatik Warning 4104 üretir. Savunmacı 4104'ü mutlaka açmalı ve `-EncodedCommand` yokluğunda bile 4104 içeriğine tespit yazmalıdır.

**b) Kısaltma ve boşluk varyasyonu.** `-EncodedCommand` yerine `-Enc`, `-e`, `-ec`; `-WindowStyle Hidden` yerine `-W Hidden`, `-w h`; büyük/küçük harf karışımı (`-eNcOdEd`). PowerShell parametreleri büyük/harf duyarsız ve önek eşleştirmeli olduğundan onlarca varyant vardır.
- **Karşı-tespit:** Sigma'da `contains|all` ve büyük/küçük harf duyarsız eşleştirme kullan; parametrenin en kısa benzersiz önekini (`-e`, `-enc`) ve tam halini ayrı ayrı listele. Empire kuralının yaptığı gibi tipik *dizilimleri* de yakala (` -NoP -sta -NonI -W Hidden -Enc `).

**c) LOLBin ile powershell.exe'yi hiç çağırmama.** `System.Management.Automation.dll`'i başka bir process içine yükleyip (unmanaged PowerShell) `powershell.exe` sürecini hiç oluşturmamak. Böylece `Image=powershell.exe` filtresi boşa düşer.
- **Karşı-tespit:** `Image` yerine davranışa bak: PowerShell Operational logu process adından bağımsız üretilir; ayrıca `.NET` assembly yüklemeleri (Sysmon Event ID 7 - Image Load, `clr.dll`/`System.Management.Automation` beklenmedik process'te) ve AMSI telemetrisi devreye girer.

**d) C2 trafiğini meşru gösterme.** Boş User-Agent yerine gerçek bir tarayıcı UA'sı set etmek (`$wc.Headers['User-Agent']='Mozilla/5.0...'`), HTTPS kullanmak, meşru CDN'lere payload koymak.
- **Karşı-tespit:** UA-tabanlı kural tek başına yetmez; bu yüzden onu `level: medium` tutup process/script sinyalleriyle korele et. TLS metadata (JA3), nadir hedef domain'ler ve süreç-ağ eşlemesi (hangi process bağlantı açtı) ile zenginleştir.

**e) DNS TXT payload'ını da encode etme.** TXT yanıtına düz `IEX` koymak yerine payload'ı Base64/parçalı gönderip client tarafında birleştirmek.
- **Karşı-tespit:** DNS log kuralına ek olarak anomali tespiti: alışılmadık uzunlukta/sıklıkta TXT sorguları, tek domain'e yüksek hacim, yüksek entropili TXT yanıtları (DNS tunneling göstergesi).

### Tipik false positive kaynakları ve ayıklama

- **Meşru yönetim/otomasyon:** SCCM, Intune, Ansible, Chocolatey, yazılım dağıtım araçları rutin olarak `-NoProfile -ExecutionPolicy Bypass -EncodedCommand` kullanır. Bu, encoded PowerShell'de en büyük FP kaynağıdır.
  - *Ayıklama:* Bilinen otomasyon hesaplarını, ebeveyn süreçleri (`ccmexec.exe`, `AgentExecutor.exe`) ve imzalı script kaynaklarını allow-list'e al. Çözülmüş 4104 içeriğini incele: meşum indirme/AMSI baypas string'i yoksa gürültüdür.
- **Boş User-Agent:** Bazı meşru sağlık/monitoring probe'ları, eski uygulamalar boş UA gönderebilir.
  - *Ayıklama:* Kaynak host + hedef domain kombinasyonuna bak; iç network monitoring IP'lerini hariç tut. Tek başına ticket açma, korelasyon bekle.
- **DNS TXT:** Domain doğrulama, e-posta güvenliği (SPF/DKIM/DMARC) TXT kayıtları normaldir; ama bunlarda `IEX`/`Invoke-Expression` geçmez — verilen kural zaten yalnızca execution string'lerine bakarak bu FP'yi büyük ölçüde eler.
- **Geliştirici/DevOps iş istasyonları:** Yazılımcılar sık sık gizli pencere + bypass ile script çalıştırır.
  - *Ayıklama:* Bu grupları ayrı bir risk kademesine koy, eşiği yükselt; ama `DownloadString + IEX` gibi cradle desenlerinde istisna tanıma.

### Kaçınmanın sınırları — savunmacının kalıcı avantajı
Saldırganın her kaçınma hamlesi bir bedel getirir. Komut satırını tamamen temizlerse, 4104'te açığa çıkar. 4104'ü kapatmak için AMSI/logging baypası denerse, bu baypas girişimi kendi başına yüksek-güvenilirlikli bir 4104/Defender alarmı üretir (`System.Management.Automation.AmsiUtils`, `amsiInitFailed` gibi string'ler). `powershell.exe`'yi hiç çağırmazsa (unmanaged PowerShell) bu kez `clr.dll` ve `System.Management.Automation.dll`'in beklenmedik bir process'e yüklenmesi Sysmon Event ID 7 ile görünür hale gelir. Yani saldırgan bir kapıyı kapatınca başka bir kapı açılır. Detection engineering'in özü, bu kapıların tümünü aynı anda izlemek ve saldırganı "hepsini birden gizleyemeyeceği" bir köşeye sıkıştırmaktır. Tek bir imzaya bağlı kalan savunmacı kaybeder; davranış kümelerini ve çapraz-kaynak korelasyonunu kullanan savunmacı kazanır.

### Savunmacı için pratik öncelik sırası
1. **Script Block Logging (4104) ve Module Logging (4103) aç** — obfuscation'a karşı en yüksek getirili tek adım.
2. **Command line auditing (4688) veya Sysmon Event ID 1 dağıt** — parametre kombinasyonu tespiti için zorunlu.
3. **Kombinasyon-tabanlı kurallar yaz** (tek bayrağa değil, Covenant/Empire mantığındaki kümelere alarm ver).
4. **Kaynakları korele et** (process + script + proxy + dns) ve otomasyon baseline'ı çıkararak FP'yi kes.
5. **PowerShell Constrained Language Mode + AppLocker/WDAC** ile saldırganın hareket alanını daralt; böylece tespit edilmeyen varyantlar bile başarısız olur.

Özet: Encoded/obfuscated PowerShell, güveni ve görünmezliği silah edinir. Fakat "diske değmeden çalışma" telemetriden kaçamaz — süreç oluşturma, PowerShell'in kendi script-block logları, proxy ve DNS katmanları saldırıyı ele verir. Tespit sanatı, tek bir string'i değil, davranış kümelerini yakalamak ve bu kaynakları korele ederek meşru otomasyon gürültüsünden gerçek tehdidi ayıklamaktır.
