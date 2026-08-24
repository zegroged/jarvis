# WDigest Cleartext Credential Cache — Tespiti

## 1. Özet: saldırı + naif tespit

WDigest, Windows'un eski bir kimlik doğrulama sağlayıcısıdır (Digest Authentication, HTTP/SASL için). İşin can alıcı yanı şu: WDigest, çalışırken kullanıcının parolasının **açık metin (cleartext)** halini LSASS bellek alanında tutar. Windows 8.1 / Server 2012 R2 ile Microsoft, KB2871997 yamasında bu davranışı varsayılan olarak kapattı ve bir anahtar bıraktı:

```
HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest
    UseLogonCredential  (REG_DWORD)
```

Değer `0` ya da yoksa: WDigest açık metin parola tutmaz. Değer `1` ise: eski davranış geri gelir, LSASS yeniden açık metin parolaları önbelleğe alır. Saldırganın yaptığı tam olarak budur — buna genelde **"WDigest downgrade"** denir. Bir kez `UseLogonCredential=1` yazıldıktan ve kullanıcı **yeniden kimlik doğruladıktan** sonra, Mimikatz'ın `sekurlsa::wdigest` modülü ya da bir LSASS dump'ı NTLM hash yerine düz parolayı verir. MITRE ATT&CK karşılıkları: T1112 (Modify Registry), T1556 (Modify Authentication Process) ve nihai amaç olarak T1003.001 (LSASS Memory).

Klasik saldırı komutu şudur:

```
reg add HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest /v UseLogonCredential /t REG_DWORD /d 1 /f
```

**Naif tespit** de buradan doğar: "reg.exe süreci + komut satırında `WDigest` ve `UseLogonCredential` ve `/d 1` geçsin, alarm at." Elimizdeki `Reg Add Suspicious Paths` (id: b7e2a8d4-74bb-4b78-adc9-3f92af2d4829) kuralı tam bu ailedendir — `process_creation` logsource'unda `Image|endswith: '\reg.exe'` veya `OriginalFileName: 'reg.exe'` ile başlar, sonra `CommandLine|contains` içinde şüpheli registry yollarını arar. WMImplant çerçevesini yakalayan kural (id: 8028c2c3-e25a-46e3-827f-bbb5abf181d7) ise `ps_script` üzerinden `ScriptBlockText|contains: ' enable_wdigest '` ve `' disable_wdigest '` argümanlarını hedefler. İkisi de doğru sinyaller, ama tek başlarına bir tespit **stratejisi** değildir. Asıl mesele bundan sonrası.

## 2. Naif tespit neden yetmez

**Birinci kör nokta — `reg.exe`'ye kilitlenmek.** `UseLogonCredential=1` yazmanın onlarca yolu var, `reg.exe` bunlardan sadece biri. Aynı DWORD'ü şöyle de yazabilirsiniz:

- PowerShell: `Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest' -Name UseLogonCredential -Value 1`
- PowerShell .NET: `[Microsoft.Win32.Registry]::SetValue(...)`
- WMI StdRegProv: `Invoke-WmiMethod -Class StdRegProv -Name SetDWORDValue`
- Doğrudan API: `RegSetValueEx` çağrısı derlenmiş bir binary/C2 beacon içinde (in-memory)
- Uzak registry (`winreg` pipe) üzerinden başka bir makineden
- GPO / GPP ile toplu dağıtım
- WMImplant `enable_wdigest`, PowerSploit, Nishang gibi çerçevelerin fonksiyonları

`reg.exe`'ye bakan kural bunların yalnızca ilk (ve en kaba) yolunu görür. Süreç oluşturma (Sysmon EventID 1 / Security 4688) tarafında `reg.exe` hiç doğmadıysa, kural sessizdir.

**İkinci kör nokta — bu kuralın yolu WDigest'i içermiyor.** Dikkat: `Reg Add Suspicious Paths` kuralının `selection_path` listesi `\AppDataLow\Software\Microsoft\` ve `\Policies\Microsoft\Windows\OOBE` ile başlıyor. Yani kural, adı "şüpheli registry yolları" olsa da **kutudan çıktığı haliyle WDigest anahtarını yakalamaz**. Bu tür genel amaçlı kuralları kendi ortamınıza uyarlamadan "WDigest'i kapsıyoruz" sanmak, sahadaki en yaygın yanılgılardan biridir. Bu yolu `SecurityProviders\WDigest` ve `UseLogonCredential` olarak listeye eklemeniz gerekir — aksi halde alarm hiç üretilmez ve kimse bunu fark etmez çünkü "kural var" diye kağıt üstünde kapsam görünür.

**Üçüncü kör nokta — registry değişikliği tek başına hırsızlık değildir.** Asıl yanlış anlama budur. `UseLogonCredential=1` yazmak, LSASS'ı **o an** açık metin parolalarla doldurmaz. WDigest, önbelleğini yalnızca **yeni bir interaktif kimlik doğrulama** olduğunda doldurur — kullanıcı kilit ekranından döndüğünde, RDP oturumu yeniden bağlandığında, `runas` çalıştırıldığında ya da makine yeniden başlatılıp biri oturum açtığında. Yani registry'deki tek sinyal, "hırsızlık gerçekleşti" demez; "hırsızlık için sahne hazırlandı" der. Bu ayrımı yapmayan bir tespit, ya çok erken (henüz kredensiyel yokken) alarm verir ya da asıl olayı — dump'ı — hiç bağlamaz.

**False positive seli.** Genel `reg add şüpheli yol` ve `PowerShell registry değişikliği` kuralları, olduğu gibi açıldığında SCCM, GPO baseline enforcement, güvenlik hardening scriptleri ve yapılandırma yönetimi araçlarının doğurduğu meşru registry yazımlarında sürekli tetiklenir. Özellikle acı verici olan nokta: birçok **hardening** aracı tam da bu anahtara `UseLogonCredential=0` yazar. Yani kırılganlığı **kapatan** meşru işlem ile açan saldırı, aynı anahtara dokunur; farkı yalnızca yazılan **değer** ve **bağlam** belirler. Değere bakmayan bir kural, güvenlik ekibinizin kendi hardening'ini saldırı sanıp gürültü üretir.

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıftır. Yüksek güven, WDigest downgrade'in doğası gereği **çok aşamalı** olmasından gelir: sahne hazırlığı → yeniden kimlik doğrulama → hasat. Bu üç fazı farklı bağlamlardan gelen sinyallerle bağlayınca, false positive'ler doğal olarak elenir çünkü meşru bir hardening aracı asla üç fazı da tamamlamaz.

**A — Sahne hazırlığı (registry flip):**
`UseLogonCredential` değeri `1` olarak yazılıyor. Bunu süreç değil, **registry değişikliği** olarak yakalayın:
- Sysmon EventID 13 (RegistryEvent - Value Set), `TargetObject` içinde `...\SecurityProviders\WDigest\UseLogonCredential`, `Details` = `DWORD (0x00000001)`.
- veya Security 4657 (A registry value was modified) — ama bu varsayılan loglanmaz (bkz. Bölüm 6).

Bu faz, `reg.exe`, PowerShell, WMI ya da derlenmiş bir beacon — hangisi olursa olsun tek noktada birleşir çünkü kernel geri çağrımı (Sysmon 13) yazan süreci umursamaz.

**B — Yeniden kimlik doğrulama (kısa pencere, farklı bağlam):**
Registry flip'ten sonra, önbelleği doldurmak için taze bir logon lazım. Saldırgan bunu genelde **tetikler**: sahte kilit ekranı gösterir, kullanıcıyı oturumu kilitleyip açmaya zorlar, ya da RDP/`tscon` ile yeniden bağlanır. İz:
- Security 4624 (An account was successfully logged on), `LogonType` 2 (interaktif), 7 (unlock) veya 10 (RemoteInteractive).
- Aynı hostta, A'dan sonraki kısa pencere içinde (örn. 30 dakika).

Bu, "farklı bağlam" sinyalidir: A registry, B kimlik doğrulama — birbirinden bağımsız log kaynakları. Meşru bir GPO enforcement A'yı üretir ama arkasından bir hasat gelmez.

**C — Hasat (LSASS erişimi):**
Açık metin parola artık LSASS'ta. Saldırgan onu okur:
- Sysmon EventID 10 (ProcessAccess), `TargetImage` = `lsass.exe`, `GrantedAccess` = `0x1010` / `0x1410` / `0x1438` (okuma + VM read).
- veya `comsvcs.dll` MiniDump, `procdump.exe`, `rundll32.exe` ile LSASS dump (T1003.001).

**Somut ihlal deseni:**
> A: `host-FIN-07` üzerinde saat 03:14'te Sysmon 13 — `TargetObject` `...WDigest\UseLogonCredential`, `Details` `0x00000001`, yazan süreç `powershell.exe` (ParentImage `wsmprovhost.exe` — yani WinRM üzerinden uzaktan).
> **+ kısa pencere B (farklı bağlam):** 03:16'da aynı hostta Security 4624, `LogonType` 10, kaynak IP başka bir iç makine.
> **+ C:** 03:18'de Sysmon 10, `SourceImage` `rundll32.exe`, `TargetImage` `lsass.exe`, `GrantedAccess` `0x1410`.

Üç faz, dört dakikalık pencerede, `wsmprovhost.exe` gibi anormal bir ebeveynle → bu artık bir "olası registry değişikliği" değil, **yüksek güvenli kredensiyel hırsızlığı**dır. Tek başına A alarmının onlarca gürültüsü, bu zincir kurulunca tek bir kesin olaya iner.

Not: Zinciri A→C sırasıyla katı beklemeyin. Bazen saldırgan A'yı yazar, sonra `UseLogonCredential`'ı tekrar `0`'a çeker (iz temizleme). O zaman **aynı anahtara kısa pencerede 1 sonra 0** yazılması (flip-flop) tek başına güçlü bir sinyaldir — meşru yapılandırma araçları böyle salınım yapmaz.

**Neden korelasyon fazları "farklı bağlam" olmalı — tespit teorisi.** Korelasyonun gücü, fazların **bağımsız log kaynaklarından** ve **bağımsız saldırgan kararlarından** gelmesindedir. A (registry) bir yapılandırma eylemidir; B (logon) bir kimlik doğrulama eylemidir; C (LSASS okuma) bir bellek erişimidir. Bir false positive üretmek için üç bağımsız meşru sürecin aynı host'ta, aynı 30 dakikalık pencerede, aynı hesap bağlamında hizalanması gerekir — bu neredeyse hiç olmaz. Bir saldırı zincirinde ise bunlar zaten tek bir niyetin parçaları olduğu için doğal olarak hizalanır. İşte bu yüzden tek-sinyal fidelity'si %5 iken, üç-fazlı korelasyonun fidelity'si %95'e çıkar. Ayrıca fazlardan biri (özellikle B — forced relogon) saldırganın **kaçınamayacağı** bir adımdır: WDigest önbelleği taze logon olmadan dolmaz, dolayısıyla kredensiyeli almak isteyen saldırgan mutlaka bir yeniden kimlik doğrulama üretmek zorundadır. Kaçınamadığı adımı tespitin çıpası yapmak, olgun detection engineering'in özüdür.

**Alternatif çıpa — WDigest DLL yüklemesi.** Bir başka ikinci-derece sinyal: `UseLogonCredential=1` etkinleştiğinde ve yeni bir logon geldiğinde, `wdigest.dll` LSASS içinde kimlik doğrulama akışına aktif olarak katılır. Sysmon EventID 7 (Image loaded) ile `lsass.exe` içine anormal zamanlı DLL yüklemelerini izlemek her ortamda pratik olmasa da, sıkı izlenen kritik sunucularda (DC, PAW, Tier-0) A fazını destekleyen ek bir teyit katmanı sağlar.

## 4. False positive gerçeği ve triage yargısı

Sahada bu kuralın altını dolduran meşru gürültü kaynakları ve analistin öncelik sırası:

**Değer temelli ilk eleme (en kritik yargı).** WDigest anahtarına yazılan `Details` değeri her şeyi belirler:
- `UseLogonCredential = 0` yazılması → neredeyse her zaman **hardening / baseline enforcement**. SCCM Configuration Baseline, GPO, Intune, CIS/DISA STIG remediation scriptleri bunu sürekli yapar. Bu, güvenliği **artıran** eylemdir; alarm listenizin en dibine koyun ya da tamamen suppress edin.
- `UseLogonCredential = 1` yazılması → varsayılan güvenli davranışı **geri alan** eylem. Meşru sebebi çok nadirdir (bazı çok eski Digest-tabanlı uygulama uyumluluğu). Öncelik listenizin en tepesi.

Değere bakmadan "WDigest anahtarına dokunuldu" alarmı, kendi hardening ekibinizi kovalamakla geçen bir vardiya demektir.

**Bağlam temelli eleme.** `1` yazımı bile her zaman kötü niyet değildir:
- **Yazan hesap ve ebeveyn:** SYSTEM olarak, `TrustedInstaller` veya SCCM ajanı (`ccmexec.exe`) altında mı, yoksa interaktif bir kullanıcı → `powershell.exe` → `cmd.exe` zinciriyle mi? İkincisi çok daha şüpheli.
- **Zamanlama ve makine:** Bir workstation'da mesai dışı, WinRM (`wsmprovhost.exe`) ebeveyniyle → kırmızı. Bir lab/test makinesinde, bilinen bir yönetici oturumunda → muhtemelen bir mühendisin denemesi.
- **Scanner/audit araçları:** Nessus, Qualys, BloodHound gibi araçlar bu anahtarı **okur** (registry query), yazmaz. Sysmon 13 yalnızca **Value Set** üretir; okuma üretmez. Yani bir vulnerability scanner bu kuralı tetiklememelidir — tetikliyorsa, kuralınız yanlışlıkla süreç komut satırındaki `WDigest` string'ini yakalıyordur (scanner'ın kendi kontrol açıklamasında geçen metin), gerçek yazımı değil. Bunu ayırt etmek triage'ın parçasıdır.

**Analistin öncelik sırası (pratikte):**
1. `Details = 0x00000001` **ve** aynı host+pencerede LSASS erişimi (Sysmon 10) veya dump → **P1, hemen izole et.**
2. `Details = 0x00000001`, anormal ebeveyn (WinRM/Office/script host), ama henüz LSASS erişimi yok → **P2, hostu incele, forced-relogon aranıyor.**
3. `Details = 0x00000001`, bilinen yönetici/test bağlamı → **P3, doğrula (kullanıcıya sor).**
4. `Details = 0x00000000` (hardening) → **suppress / bilgilendirici.**

**Somut FP kaynakları ve nasıl ayrışırlar:**
- **SCCM / Configuration Baseline:** Düzenli aralıklarla (compliance evaluation cycle) `UseLogonCredential=0` yazar. İz: `Image` = `CcmExec.exe` veya `WmiPrvSE.exe`, `Details=0`, saatte/günde bir düzenli ritim. Ayırt edici: değer `0`, süreç ve zamanlama öngörülebilir. → suppress.
- **GPO / Group Policy Client:** `gpsvc` üzerinden baseline `0` yazımı, genelde makine başlangıcında veya 90 dakikalık GPO refresh'te. İz: ana süreç `svchost.exe` (gpsvc), `Details=0`. → suppress, ama `svchost` altından `1` gelirse (GPO ile downgrade dağıtımı — nadir ama mümkün) → incele, çünkü bu bir saldırgan-kontrollü GPO'ya (T1484) işaret edebilir.
- **Yedekleme / imaj araçları:** Registry snapshot'ları **okur**, yazmaz — Sysmon 13 üretmez. Eğer bir yedekleme aracı adına alarm görüyorsanız, muhtemelen süreç komut satırındaki string eşleşmesidir, gerçek Value Set değil. → kural mantığını registry olayına taşıyın.
- **Vulnerability scanner (Nessus/Qualys):** Anahtarı okur ve raporlar; yazmaz. Alarm görüyorsanız neredeyse kesinlikle bir `process_creation` kuralı, scanner'ın kontrol açıklamasındaki `UseLogonCredential` metnini yakalıyordur. → bu kuralı registry Value Set'e daraltın.
- **Yönetici / mühendis denemesi:** Bir kişinin `1` yazıp test edip geri alması. İz: interaktif oturum, bilinen yönetici hesabı, mesai içi, hostta başka kötü niyet yok. → doğrula (kullanıcıya sor), false positive olarak kapat ama olayı belgele.

Buradaki yönetici yargısı şudur: **değer + yazan bağlam + ardından LSASS erişiminin var/yok olması** üçlüsü, hemen her meşru senaryoyu saldırıdan ayırır. Tek bir eksende (sadece süreç adı, ya da sadece anahtar yolu) filtreleyen her yaklaşım ya çok gürültü ya çok kaçak üretir.

## 5. Kaçınma → karşı-tespit

Dokümanların anlatmadığı, olgun saldırganın yaptığı atlatmalar ve bunlara karşı ikinci-derece tespit:

**Kaçınma 1 — `reg.exe`'yi hiç kullanmamak.** `Set-ItemProperty`, WMI `StdRegProv.SetDWORDValue`, ya da beacon içinden doğrudan `RegSetValueEx` API çağrısı. Süreç oluşturma tabanlı `Reg Add Suspicious Paths` kuralı bunların hiçbirini görmez.
→ **Karşı-tespit:** Süreç değil, **registry olayına** dayanan Sysmon EventID 13 kuralı. Sysmon config'inizde `RegistryEvent` için `SecurityProviders\WDigest` yolunu **include** ettiğinizden emin olun — varsayılan Sysmon config'lerin birçoğu tüm registry'yi loglamaz, seçici include listesi kullanır. WDigest anahtarı o listede yoksa Sysmon 13 hiç üretilmez ve API-tabanlı yazımı da kaçırırsınız.

**Kaçınma 2 — Script Block Logging'i atlamak.** WMImplant'ın `enable_wdigest` fonksiyonunu yakalayan kural `ps_script` logsource'una, yani EventID 4104 ScriptBlockText'e dayanır. Saldırgan aynı işi **derlenmiş** bir .NET/C++ araçla ya da `-EncodedCommand` + AMSI bypass ile yaparsa, ScriptBlockText hiç oluşmaz.
→ **Karşı-tespit:** Sonucu izleyin, aracı değil. Hangi araç kullanılırsa kullanılsın, **registry değeri değişmek zorunda** — Sysmon 13 son ortak noktadır. Ayrıca AMSI/ETW tampering'i (T1562) ayrı bir sinyal olarak korele edin; script block logging'in aniden sustuğu bir host zaten şüphelidir.

**Kaçınma 3 — Flip-then-restore (iz temizleme).** Değeri `1` yap, kilit ekranını tetikle, LSASS'ı dump'la, sonra `0`'a geri çek. Anlık bir snapshot alan bir denetim, sonradan `0` görür ve "temiz" sanır.
→ **Karşı-tespit:** Snapshot değil, **olay akışı**. Sysmon 13 her iki yazımı da (1 ve 0) ayrı olay olarak kaydeder. `UseLogonCredential` üzerinde kısa pencerede **1 → 0 salınımı** kalıcı bir izdir; değeri sonradan silseniz bile olay logunda durur. Bu flip-flop desenini ayrı bir kural yapın.

**Kaçınma 4 — Sysmon/EDR'yi kör etmek.** Registry yazımından önce Sysmon servisini durdur ya da config'ini boşalt, doğrudan syscall ile EDR user-mode hook'larını atla.
→ **Karşı-tespit:** İkinci-derece — Sysmon servis sağlığı ve config bütünlüğü. Sysmon EventID 4 (Sysmon service state changed) ve 16 (Sysmon config changed) izleyin; ayrıca telemetri **sessizliğini** bir sinyal olarak modelleyin (bir host'un beklenen registry/process olay hacmi aniden sıfıra düşerse). "Log yokluğu" da bir logdur.

**Kaçınma 5 — Uzak registry / lateral.** `winreg` named pipe üzerinden başka makineden yazma. Kurban hostta yazan bir "süreç" görünmez.
→ **Karşı-tespit:** Kurban hostta Sysmon 13 yine de üretilir (yazım orada gerçekleşir). Buna ek olarak kaynak hostta `RemoteRegistry` servisine erişim ve `4624 LogonType 3` (network) korelasyonu, kaynağı işaret eder.

**Kaçınma 6 — Değeri REG_DWORD dışı yazmak / tip oyunu.** Bazı akıllı saldırganlar, kurala takılmamak için değeri beklenen tipten farklı yazmayı dener (örn. bir string olarak `"1"`, ya da `0x1` yerine daha büyük bir non-zero DWORD). WDigest kodu değeri "non-zero mu?" diye kontrol ettiği için `2`, `0xFF` gibi herhangi bir sıfır-olmayan değer de downgrade'i tetikler.
→ **Karşı-tespit:** Kuralınızı `Details = 0x00000001` gibi **tam eşleşmeye** değil, "`UseLogonCredential` yazıldı **ve** değer sıfır değil" mantığına kurun. Splunk'ta `Details!="DWORD (0x00000000)"`, MDE'de `RegistryValueData != "0"` yaklaşımı, `1`'e sabitlenmiş bir kuraldan çok daha dayanıklıdır. Yalnızca `= 1` arayan kurallar, `= 2` yazan bir saldırganı sessizce kaçırır — bu, sahada gördüğüm en ince ama en pahalı kural hatalarından biridir.

**Kaçınma 7 — Meşru araç gölgesine saklanma.** Saldırgan, yazımı bir SCCM/GPO enforcement penceresine denk getirir ya da yazan süreci `svchost.exe`/`ccmexec.exe` gibi görünecek şekilde isimlendirir (ya da o süreçlere enjekte eder). Amacı, whitelist'inizin arkasına saklanmaktır.
→ **Karşı-tespit:** Süreç adını değil, **değeri ve ana sonucu** çıpa yapın. Bir SCCM ajanı `UseLogonCredential=0` (hardening) yazar; `=1` yazan bir "SCCM ajanı" başlı başına anomalidir. Yani whitelist'i yalnızca `Details=0` yazımlarına daraltmak (Bölüm 4), bu gölgelenmeyi de kapatır. Ayrıca `ccmexec.exe`'nin beklenmedik bir ebeveynden (`cmd.exe`, `powershell.exe`) doğması ya da imza/yol tutarsızlığı, taklidi ele verir.

## 6. SIEM / saha gerçeği

**Alan eşleme (field mapping) ve varsayılan loglanmayan.** En sık düşülen tuzak: Security 4657 (A registry value was modified) **varsayılan olarak loglanmaz.** Bunu almak için hem Advanced Audit Policy'de "Object Access → Audit Registry" başarısını açmanız, hem de WDigest anahtarına özel bir **SACL** koymanız gerekir. Çoğu kurumda ikisi de yoktur. Dolayısıyla pratikte WDigest downgrade tespitinin **birincil telemetrisi Sysmon EventID 13**'tür, 4657 değil. Kurulumunuz Sysmon'a dayanmıyorsa, önce bu SACL'i deploy edin — yoksa registry flip'i hiç görmezsiniz.

Sysmon 13 alanları: `TargetObject` (tam registry yolu), `Details` (`DWORD (0x00000001)` biçiminde), `Image` (yazan süreç), `EventType` = `SetValue`. Yol eşlemesinde `CurrentControlSet`'in registry'de sabit olduğunu unutmayın — ama bazı loglar `ControlSet001` şeklinde normalize edebilir; kuralınızda `\SecurityProviders\WDigest\UseLogonCredential` son ekiyle `contains`/`endswith` kullanmak, `ControlSet001`/`CurrentControlSet` farkına dayanıklı olur.

**Splunk (Sysmon, TA-microsoft-sysmon):**
```
index=sysmon EventCode=13 
  TargetObject="*\\SecurityProviders\\WDigest\\UseLogonCredential" 
  Details="DWORD (0x00000001)"
| stats count by host, Image, ParentImage, _time
```
Sonra `4624` ve `EventCode=10 TargetImage=*lsass.exe` ile `transaction host maxspan=30m` veya `stats`+`streamstats` ile korele edin.

**Microsoft Sentinel / Defender (MDE):** Sentinel'de iki ayrı tablo var, karıştırılır:
- `SecurityEvent` (4657 — SACL gerektirir, çoğunlukla boştur).
- `Event` (Sysmon, AMA/Log Analytics agent üzerinden — `EventID == 13`).
- MDE avantajı: `DeviceRegistryEvents` tablosu ham Sysmon'a göre normalize edilmiştir:
```
DeviceRegistryEvents
| where RegistryValueName == "UseLogonCredential"
| where RegistryKey has "WDigest"
| where RegistryValueData == "1"
```
`RegistryValueData` MDE'de ondalık string (`"1"`) olarak gelir; Sysmon'daki `DWORD (0x00000001)` biçiminden farklıdır — bu ayrımı bilmeden yazılan Sentinel sorgusu sessizce boş döner.

**Elastic (Winlogbeat / Elastic Agent):** Alanlar ECS'e map edilir: `event.code: "13"`, `registry.path`, `registry.value: "UseLogonCredential"`, `registry.data.strings`. Elastic'te `registry.data.strings` bir dizidir; `"0x1"` veya `"1"` normalize biçimine göre değişir — kendi ortamınızdan bir örnek olayı açıp gerçek değeri teyit edin, dokümana güvenmeyin.

**Platformlar arası tuning yargısı:**
- Değere göre filtreleyin (`= 1`), yoksa hardening (`= 0`) gürültüsünde boğulursunuz.
- Bilinen yapılandırma ajanlarını (`ccmexec.exe`, `TrustedInstaller.exe`, Intune) `Image`/`ParentImage` bazında whitelist'e alın — ama yalnızca `Details = 0` yazımları için; `1` yazımını hiçbir ajan için otomatik affetmeyin.
- Tek başına A alarmını "informational" tutup, A+B veya A+C korelasyonunu "high" severity'ye yükseltin. Bu, analiz yükünü onlarca gürültüden birkaç gerçek olaya indirir.
- `Reg Add Suspicious Paths` kuralını kullanıyorsanız, `selection_path` listesine `\SecurityProviders\WDigest` ve `UseLogonCredential` yollarını **elle ekleyin** — çünkü kutudan çıktığı hali WDigest'i kapsamaz (Bölüm 2). Ancak bunu eklerken bunun yalnızca `reg.exe` yolunu yakaladığını, PowerShell/WMI/API yollarını Sysmon 13'e bıraktığınızı unutmayın; iki katman birlikte çalışmalı.

**Son yargı:** WDigest downgrade tespitinde başarı, "reg add komutunu yakalamak" değil; **doğru telemetriyi (Sysmon 13, doğru include listesiyle) toplamak**, **değeri okumak** (1 vs 0), ve **registry → forced relogon → LSASS erişimi** zincirini kurmaktır. Bu üçünü yapan bir SOC, tek satırlık komut imzasına güvenen bir SOC'un aylarca göremeyeceği sessiz downgrade'leri dört dakikalık pencerede yakalar.
