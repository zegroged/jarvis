# Pass-the-Hash (PtH) — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin bir saldırıyı önce **anlamak**, sonra **tespit etmek** üzerine kuruludur. Amaç mavi takım / detection engineering perspektifinden savunma ve tespit geliştirmektir; canlı bir saldırı reçetesi değil. Aşağıdaki tespit mantığı, tekniğe ait gerçek Sigma kurallarına (Mimikatz, WCE `wceaux.dll`, SYSTEM kullanıcı süreç oluşturma vb.) demirlenmiştir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Pass-the-Hash, Windows kimlik doğrulama mimarisinin temel bir tasarım gerçeğini istismar eder: **NTLM protokolünde parolanın kendisi değil, parolanın NT hash'i kimlik doğrulama sırrıdır.** Yani bir kullanıcının düz metin parolasını bilmek zorunda değilsiniz; NTLM challenge-response akışında istemci, sunucuya cevabı NT hash'ten türetir. Elinizde geçerli NT hash varsa, parolayı hiç kırmadan (crack etmeden) o kullanıcı olarak ağdaki kaynaklara kimlik doğrulaması yapabilirsiniz. Hash, fonksiyonel olarak parolanın kendisi kadar değerlidir — "parola eşdeğeri" (password equivalent) bir sırdır.

Kavramsal olarak saldırganın yaptığı üç aşamadan oluşur:

**Birincisi, hash'i ele geçirme.** Windows, oturum açmış kullanıcıların kimlik bilgilerini `LSASS` (Local Security Authority Subsystem Service, `lsass.exe`) sürecinin bellek alanında tutar. Bir saldırgan yerelde yönetici (veya `SeDebugPrivilege`) haklarına ulaştığında, LSASS bellek alanından NTLM hash'lerini okur. Mimikatz'ın `sekurlsa::logonpasswords` ve `lsadump::` modülleri tam olarak bunu yapar. Alternatif olarak hash'ler `SAM` veritabanından, Active Directory'nin `NTDS.dit` dosyasından (`lsadump::dcsync` ile DC üzerinden replikasyon taklidi yaparak) ya da kayıt defteri hive'larından elde edilebilir.

**İkincisi, hash'i yeniden kullanma (pass).** Saldırgan, ele geçirdiği hash'i kendi oturumuna "enjekte eder" ve bu kimlikle uzak bir sisteme NTLM üzerinden bağlanır. Mimikatz'ın `sekurlsa::pth` modülü, Windows Credential Editor (WCE) `-s` seçeneği veya Impacket araç ailesi (`psexec.py`, `wmiexec.py`, `smbexec.py` gibi) bu adımı gerçekleştirir. Bağlantı tipik olarak SMB (445), WMI, WinRM veya RPC üzerinden gerçekleşir.

**Üçüncüsü, yanal hareket (lateral movement).** Bir makinede geçerli olan hash, aynı parolayı paylaşan diğer makinelerde de geçerlidir. Özellikle her yerde aynı yerel yönetici parolasının kullanıldığı ortamlarda tek bir hash, tüm alan (domain) boyunca zincirleme erişim sağlar. Saldırgan makineden makineye atlar, ayrıcalık yükseltir ve nihayetinde Domain Admin veya `krbtgt` hash'ine ulaşmayı hedefler.

PtH'nin savunmacı açısından kritik özelliği şudur: **normal, geçerli kimlik doğrulama akışlarını taklit eder.** Ağ üzerinde "kötü niyetli bir paket" görünmez — protokol açısından her şey meşrudur. Bu yüzden tespit, tek bir imzaya değil; kimlik bilgisi erişimi (credential access), anormal oturum açma desenleri ve süreç davranışı korelasyonuna dayanır. Kavramsal olarak "hırsız, çalınmış ama geçerli bir anahtarla kapıdan giriyor" — bu yüzden kapıda değil, anahtarın nasıl kopyalandığı ve nerede kullanıldığı noktalarında yakalanır.

Bu tekniğin neden bu kadar kalıcı ve tehlikeli olduğunu anlamak için bir noktayı vurgulamak gerekir: PtH bir "yazılım açığı" (vulnerability) değil, protokolün **tasarım gereği** böyle çalışmasıdır. Bir yama ile kapatılamaz; ancak mimari önlemler (Credential Guard, LSASS koruması, ağ segmentasyonu, tekil yerel yönetici parolaları için LAPS) ve güçlü tespit ile yönetilebilir. MITRE ATT&CK çerçevesinde bu teknik **T1550.002 (Use Alternate Authentication Material: Pass the Hash)** olarak sınıflandırılır; öncülü olan kimlik bilgisi dökümü ise **T1003** (OS Credential Dumping) alt tekniklerine — `T1003.001` (LSASS Memory), `T1003.002` (SAM), `T1003.004` (LSA Secrets), `T1003.006` (DCSync) — karşılık gelir. Yukarıdaki Sigma kurallarının etiketlerinde (`tags`) tam olarak bu ATT&CK teknik ID'lerini görmeniz tesadüf değildir; kurallar credential-access ve lateral-movement taktiklerine demirlenmiştir.

---

## 2. Bıraktığı izler / artefaktlar

PtH zincirinin her aşaması farklı log kaynaklarında iz bırakır. Detection engineering açısından bu izleri üç kümede toplayabiliriz: **kimlik bilgisi hırsızlığı (credential dumping) izleri**, **hash yeniden kullanımı / oturum açma izleri** ve **araç/süreç artefaktları.**

### 2.1 Credential dumping izleri (LSASS ve türevleri)

- **LSASS bellek erişimi:** Sysmon **Event ID 10** (`ProcessAccess`), `TargetImage` alanı `lsass.exe` olan ve `GrantedAccess` değeri `0x1010`, `0x1410`, `0x1438`, `0x143a` gibi bellek okuma haklarını içeren erişimleri gösterir. Mimikatz, comsvcs.dll MiniDump, procdump gibi teknikler burada iz bırakır.
- **Object Access denetimi:** Güvenlik günlüğünde **Event ID 4656** (handle istendi) ve **Event ID 4663** (nesneye erişildi) olayları, hassas nesnelere erişimi kaydeder. WCE tabanlı PtH özelinde `wceaux.dll` isimli nesneye erişim tipik bir imzadır (aşağıdaki WCE kuralında bu tam olarak yakalanır).
- **DCSync / replikasyon:** Bir DC olmayan hesabın dizin replikasyonu talep etmesi (`DS-Replication-Get-Changes`) **Event ID 4662** ile görünür; `krbtgt` veya toplu hash çekiminin öncülüdür.
- **SAM / NTDS erişimi:** Kayıt defteri hive dump'ları, gölge kopya (VSS) oluşturma ve `ntds.dit` kopyalama işlemleri süreç oluşturma günlüklerinde iz bırakır.

### 2.2 Hash yeniden kullanımı / oturum açma izleri

- **Event ID 4624 (başarılı oturum açma):** PtH için en ayırt edici alan **`LogonType = 3`** (Network) ve **`AuthenticationPackageName = NTLM`** kombinasyonudur. Kerberos'un tercih edildiği modern bir alanda, ayrıcalıklı hesaplar için NTLM ağ oturumları anormaldir.
- **`LogonProcessName` = `NtLmSsp`** ve **`ImpersonationLevel`** değerleri PtH oturumlarında karakteristik desenler oluşturur. Klasik Mimikatz PtH oturumlarında `LogonType 9` (NewCredentials) ve `LogonProcessName = seclogo` da görülebilir.
- **Event ID 4625 (başarısız oturum açma):** Yanlış makinelerde denenen hash'ler, aynı kaynak IP'den çok sayıda `LogonType 3` başarısızlığı olarak birikir (yatay tarama deseni).
- **Event ID 4776 (NTLM kimlik doğrulama, DC üzerinde)** ve **4768/4769 (Kerberos)** dengesizliği: NTLM sayacında ani artış ile Kerberos'ta durgunluk, hash yeniden kullanımının makro göstergesidir.
- **Uzak yürütme izleri:** `psexec` benzeri araçlar hedef makinede geçici bir servis oluşturur — **Event ID 7045** (yeni servis kuruldu), rastgele adlı `.exe` ile. WMI tabanlı yürütme `wmiprvse.exe` altında `cmd.exe`/`powershell.exe` çocuk süreçleri bırakır.

### 2.3 Araç ve süreç artefaktları

- **Mimikatz komut satırı desenleri:** `sekurlsa::pth`, `sekurlsa::logonpasswords`, `lsadump::`, `kerberos::ptt`, `kerberos::golden` gibi modül çağrıları; ayrıca `mimidrv.sys`, `mimilib.dll`, `gentilkiwi.com`, `eo.oe.kiwi` gibi imza dizeleri (aşağıdaki Mimikatz kuralları bunları hedefler).
- **WCE artefaktları:** `wceaux.dll` dosyasının diske düşmesi ve bu DLL'e erişim (WCE'nin uzak komut yürütme mekanizması).
- **SYSTEM olarak beklenmedik süreçler:** PtH sonrası saldırgan sıklıkla `NT AUTHORITY\SYSTEM` bağlamında `IntegrityLevel = System` ile araçlar çalıştırır; bu, meşru olmayan araçlar (`calc.exe`, `mshta.exe`, `cscript.exe` vb.) SYSTEM olarak koştuğunda anormaldir.
- **Ağ izleri:** SMB (445), RPC (135 + yüksek portlar), WMI (DCOM) ve WinRM (5985/5986) üzerinden makineler arası, özellikle iş istasyonundan iş istasyonuna (east-west) beklenmedik yönetimsel bağlantılar.

### 2.4 Artefaktların savunmacı açısından okunması

Bu izlerin tek tek varlığı çoğu zaman yeterli kanıt değildir; kıymetli olan **zamansal ve mantıksal dizilimleridir.** Örneğin tek başına bir Event ID 4624 `LogonType 3` + NTLM oturumu gürültüdür; ancak aynı hesabın önce bir makinede LSASS erişimi (Sysmon 10), hemen ardından beş ayrı sunucuda NTLM ağ oturumları ve o sunucularda servis kurulumu (7045) bırakması, PtH yanal hareketinin klasik "yayılma imzası"dır. Detection engineering'in görevi bu izleri tekil alarmlar olarak değil, bir **saldırı grafiği** (attack graph) olarak modellemektir: kaynak host, hedef host, kullanıcı bağlamı, kimlik doğrulama paketi ve zaman penceresi birer düğüm/kenar olarak ele alınır. Bir SIEM'de bu, `4624`/`4625` olaylarını `TargetUserName`, `IpAddress` ve `WorkstationName` üzerinden gruplayıp "tek hesap → çok hedef, kısa pencere" desenini aramak anlamına gelir.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki tespit yaklaşımı, tekniğe ait dört gerçek Sigma kuralının mantığını temel alır. Her birinde **hangi `logsource`**, **hangi `field`/koşul** ve **hangi eşik** ile alarm üretildiğini Türkçe açıklıyorum.

### 3.1 Mimikatz anahtar kelime tespiti (Eventlog imza avı)

**Kural:** *Mimikatz Use* (id `06d71506-7beb-4f22-8888-e2e5e2ca7fd8`).
**`logsource`:** `product: windows` (genel Windows Eventlog'ları).
**Mantık:** Bu kural bir davranış değil, **imza** tespitidir. Herhangi bir Windows olay günlüğünde Mimikatz'a özgü sabit dizeler geçtiğinde alarm verir: `sekurlsa::pth`, `lsadump::`, `kerberos::ptt`, `kerberos::golden`, `kerberos::tgt`, `dpapi::masterkey`, `\mimilib.dll`, `mimidrv.sys`, `gentilkiwi.com`, `eo.oe.kiwi`, `Kiwi Legit Printer`. `keywords` bloğundaki bu dizelerden **herhangi biri** (OR mantığı) eşleşirse tetiklenir. PtH açısından kritik olan `sekurlsa::pth` ve `kerberos::ptt` (pass-the-ticket) dizeleridir. Eşik: tek eşleşme yeterli — bu dizeler meşru sistemlerde neredeyse hiç görülmez.

Bu kural neden değerli? PtH zincirinin "hash'i ele geçir" ve "hash'i geç" adımlarının en yaygın aracı Mimikatz olduğundan, aracın modül adları güçlü bir sinyaldir. Zayıflığı ise açık: dize tabanlı olduğu için yeniden derlenmiş/adı değiştirilmiş sürümlerde atlatılabilir (bkz. Bölüm 4).

### 3.2 Mimikatz komut satırı tespiti (process_creation)

**Kural:** *HackTool - Mimikatz Execution* (id `a642964e-bead-4bed-8910-1bb4d63e3b4d`).
**`logsource`:** `category: process_creation`, `product: windows` (yani Sysmon Event ID 1 veya Güvenlik 4688).
**Mantık:** İki seçim bloğu OR ile birleşir:
- `selection_tools_name`: `CommandLine|contains` alanında `mimikatz` veya `DumpCreds` geçmesi.
- `selection_function_names`: modül/fonksiyon adlarının komut satırında görünmesi (`::aadcookie`, `::detours`, `::memssp`, `::mflt` vb.). Bu ikinci blok, `mimikatz.exe` yeniden adlandırılsa bile **fonksiyon adlarının** komut satırında kalmasından yararlanır.

PtH avı için bu kuralı, `sekurlsa::pth` ve `sekurlsa::logonpasswords` argümanlarını içerecek şekilde genişletmek doğaldır. Eşik: tek satır eşleşmesi. Bu kural 3.1'den daha operasyoneldir çünkü tam **çalıştırma anını** ve süreç ağacını (ParentImage) yakalar.

### 3.3 WCE Pass-the-Hash tespiti (`wceaux.dll` erişimi)

**Kural:** *WCE wceaux.dll Access* (id `1de68c67-af5c-4097-9c85-fe5578e09e67`), `level: critical`.
**`logsource`:** `product: windows`, `service: security` (Güvenlik günlüğü, Object Access denetimi açık olmalı).
**Mantık:**
```
selection:
  EventID: [4656, 4663]
  ObjectName|endswith: '\wceaux.dll'
condition: selection
```
Yani `4656` (nesne handle'ı istendi) veya `4663` (nesneye erişim gerçekleşti) olaylarında, erişilen nesnenin adı `\wceaux.dll` ile bitiyorsa alarm. WCE aracı, kaynak host üzerinde uzaktan komut yürütme için bu yardımcı DLL'i kullanır; dolayısıyla bu DLL'e herhangi bir erişim doğrudan WCE tabanlı PtH göstergesidir. Eşik: tek erişim — `wceaux.dll` meşru bir Windows bileşeni değildir, bu yüzden `level: critical` olarak işaretlenmiştir.

### 3.4 SYSTEM olarak şüpheli süreç oluşturma

**Kural:** *Suspicious SYSTEM User Process Creation* (id `2617e7ed-adb7-40ba-b0f3-8f9945fe6c09`).
**`logsource`:** `category: process_creation`, `product: windows`.
**Mantık:** İki koşul AND ile birleşir:
- `selection`: `IntegrityLevel` = `System` (veya SID `S-1-16-16384`) **ve** `User|contains` `AUTHORI`/`AUTORI` (dil bağımsız olarak `NT AUTHORITY\SYSTEM`'i yakalamak için).
- `selection_special`: bu SYSTEM bağlamında normalde SYSTEM olarak koşmaması gereken imajlar (`\calc.exe`, `\cscript.exe`, `\mshta.exe`, `\wscript.exe`, `\hh.exe`, `\ping.exe` vb.) veya belirli komut satırı desenleri.

PtH ile ilgisi: saldırgan hash'i geçip uzak makinede SYSTEM bağlamında araç çalıştırdığında, "SYSTEM olarak `mshta.exe`" gibi anomaliler ortaya çıkar. Bu davranışsal kural, imza tabanlı 3.1/3.2'yi tamamlar — araç yeniden adlandırılsa bile "yanlış kullanıcı, yanlış süreç" korelasyonu tutar.

### 3.5 Basit Sigma-benzeri tespit mantığı örnekleri

**Örnek A — PtH karakteristik NTLM ağ oturumu (davranışsal):**
```yaml
title: Suspicious NTLM Network Logon (Possible Pass-the-Hash)
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4624
    LogonType: 3
    AuthenticationPackageName: 'NTLM'
  filter_machine:
    TargetUserName|endswith: '$'   # makine hesaplarını ele
  condition: selection and not filter_machine
falsepositives:
  - NTLM'e bağımlı eski uygulamalar, tarayıcılar, NAS erişimi
level: medium
```
Mantık: Kerberos'un olması gereken bir alanda, ayrıcalıklı bir kullanıcı hesabının `LogonType 3` + `NTLM` ile ağ oturumu açması PtH şüphesi doğurur. Makine hesapları (`$` ile biten) elenerek gürültü azaltılır. Bu kural tek başına delil değil, **korelasyon tetikleyicisidir**.

**Örnek B — LSASS'tan hash çekme (kaynak adım):**
```yaml
title: LSASS Memory Access with Dump Rights
logsource:
  product: windows
  category: process_access   # Sysmon Event ID 10
detection:
  selection:
    TargetImage|endswith: '\lsass.exe'
    GrantedAccess:
      - '0x1010'
      - '0x1410'
      - '0x1438'
      - '0x143a'
  filter_known:
    SourceImage|endswith:
      - '\MsMpEng.exe'      # Defender
      - '\wininit.exe'
  condition: selection and not filter_known
level: high
```
Mantık: `lsass.exe`'ye bellek okuma haklarıyla erişen, bilinen meşru koruma/sistem süreçleri dışındaki her süreç kritik sinyaldir. PtH'nin "hash'i ele geçir" adımını kaynağında yakalar.

**Korelasyon:** En güçlü tespit, bu sinyalleri **zincir olarak** birleştirmektir: (1) Bölüm 3.2/Örnek B ile bir makinede credential dumping → (2) kısa süre sonra Örnek A ile aynı hesabın başka makinelerde NTLM ağ oturumları → (3) hedef makinelerde 3.4 ile SYSTEM anomalisi veya Event ID 7045 servis kurulumu. Bu üçlü zaman-pencereli korelasyon, tekil kuralların false positive'ini bastırırken PtH yanal hareketini yüksek güvenle ortaya koyar.

---

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırgan tespiti nasıl atlatmaya çalışır

**İmza kaçırma:** Mimikatz dize tabanlı kurallarını (3.1, 3.2) atlatmanın en yaygın yolu aracı yeniden derlemek, dize/fonksiyon adlarını değiştirmek (obfuscation), ya da `Invoke-Mimikatz` gibi bellek-içi (fileless) PowerShell yansımalı yükleyicilerle diske hiç `mimikatz.exe` düşürmemektir. `DumpCreds`, `gentilkiwi.com` gibi sabitler kaldırıldığında `keywords` eşleşmesi kırılır.

**Karşı önlem:** İmzaya değil davranışa demirlenen kurallara ağırlık verin — Bölüm 3.4 (SYSTEM anomalisi) ve Örnek B (LSASS `GrantedAccess`). LSASS bellek erişimi, aracın adından bağımsız olarak gerçekleşmek zorundadır; bu yüzden Sysmon Event ID 10 tabanlı tespit yeniden adlandırmaya dayanıklıdır. Ayrıca LSASS'ı **PPL (Protected Process Light)** ve **Credential Guard** ile koruyarak dumping'i baştan zorlaştırın; bu, saldırganı gürültülü sürücü yükleme (`mimidrv.sys`) gibi tespit edilebilir yollara iter.

**Protokol seçimi:** Saldırgan PtH yerine Pass-the-Ticket'e (`kerberos::ptt`) veya overpass-the-hash'e geçerek NTLM sinyalinden (Örnek A) kaçabilir. Bu durumda NTLM oturumu görünmez, ama Kerberos tarafında anormal bilet talepleri belirir.

**Karşı önlem:** Sadece NTLM'e değil, Kerberos anomalilerine de bakın (`4768`/`4769` desenleri, şifreleme türü düşürme). Ağ genelinde NTLM/Kerberos oranını izleyin; NTLM'de ani artış yanal hareket habercisidir.

**Meşru araçlarla karışma (LOLBins):** Saldırgan PtH yürütmesini `wmic`, `sc.exe`, WinRM gibi yerleşik yönetim araçlarına kaydırarak "yönetim gürültüsü" içinde saklanmaya çalışır.

**Karşı önlem:** Yönetimsel bağlantıları **kaynak-hedef bazında beyaz listeleyin** (jump host'lar). İş istasyonundan iş istasyonuna east-west yönetim trafiği neredeyse her zaman anormaldir.

### 4.2 Tipik false positive kaynakları ve ayıklama

- **`wceaux.dll` kuralı (3.3):** Bilinen tek false positive kaynağı "unknown" olarak işaretlenmiştir — pratikte bu DLL meşru yazılımda bulunmaz, dolayısıyla kritik seviye korunmalıdır. Herhangi bir eşleşme neredeyse kesin gerçek pozitiftir.
- **NTLM ağ oturumu kuralı (Örnek A):** En gürültülü kural budur. Eski uygulamalar, NTLM'e bağımlı NAS/dosya paylaşımları, tarayıcı entegre kimlik doğrulaması ve bazı vuln tarayıcıları meşru NTLM `LogonType 3` üretir. **Ayıklama:** makine hesaplarını (`$`) eleyin; bilinen servis hesaplarını ve NTLM'e mecbur eski sistemleri istisna listesine alın; kuralı yalnızca **ayrıcalıklı hesaplar** ve **çok sayıda hedef makine** ile daralması durumunda yükseltin (tekil oturum yerine "1 hesap → N makine" eşiği).
- **LSASS erişim kuralı (Örnek B):** EDR/antivirüs (Defender `MsMpEng.exe`), yedekleme ajanları ve bazı izleme araçları meşru olarak LSASS'a erişir. **Ayıklama:** `SourceImage` beyaz listesi ve `GrantedAccess` maskesini yalnızca gerçek bellek-okuma bayraklarını içerecek şekilde daraltın; imzalı, bilinen yollardan gelen süreçleri filtreleyin.
- **SYSTEM süreç kuralı (3.4):** Yazılım kurulumları, WSUS/SCCM ajanları ve bazı zamanlanmış görevler SYSTEM olarak beklenmedik ikili dosyalar çalıştırabilir. **Ayıklama:** `selection_special` imaj listesini kurum ortamına göre kalibre edin; bilinen dağıtım araçlarının `ParentImage`'ını istisna edin.
- **Mimikatz komut satırı (3.2):** Güvenlik ekiplerinin kendi sızma testleri, mor takım tatbikatları ve eğitim ortamları gerçek pozitif üretir ama "operasyonel tehdit" değildir. **Ayıklama:** test aralıklarını ve yetkili test makinelerini bir bağlamla (allowlist + zaman penceresi) işaretleyin, ama asla kalıcı olarak susturmayın.

### 4.3 Savunmacının olgunluk yol haritası

En dayanıklı tespit tekil kurala değil, **kaynak → yeniden kullanım → hedef** korelasyonuna dayanır. Öncelik sırası: (1) Credential Guard ve LSASS PPL ile hash'in çalınmasını baştan zorlaştır (önleme); (2) LSASS erişimi ve DCSync (`4662`) ile "hırsızlık anını" davranışsal olarak yakala; (3) NTLM/Kerberos oturum anomalileri ile "hash'in nerede geçtiğini" izle; (4) SYSTEM anomalileri ve servis kurulumu (`7045`) ile "hedefteki eylemi" doğrula. İmza kuralları (Mimikatz, WCE) bu davranışsal katmanın üzerinde hızlı ve yüksek-güvenli birer tetikleyici olarak durur — atlatılabilir olsalar da, atlatma çabası kendisi başka gürültülü izler bırakır. Mavi takımın işi, saldırganı hiç iz bırakmadan hareket edemeyeceği bir koridora sıkıştırmaktır.
