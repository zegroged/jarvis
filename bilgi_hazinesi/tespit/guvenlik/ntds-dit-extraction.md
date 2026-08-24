# NTDS.dit Çıkarma — Tespiti

> Saha notu. Domain Controller üzerinde `NTDS.dit`'in çıkarılması, bir saldırganın ağdaki en yüksek değerli hamlesidir: içinde tüm domain kullanıcılarının NTLM hash'leri, Kerberos anahtarları ve (DPAPI ile) geçmiş parola geçmişi bulunur. Bu dosyayı ele geçiren saldırgan, `krbtgt` hash'ini alıp Golden Ticket üretebilir, offline olarak parola kırabilir ve domain'i kalıcı olarak sahiplenebilir. Bu yüzden tespiti "olur da yakalarız" değil, "kesinlikle görmemiz gereken" kategorisindedir. Aşağıda naif tespitin neden çöktüğünü, sinyalleri nasıl bağladığımızı ve SIEM'de gerçekte ne göründüğünü anlatıyorum.

---

## 1. Özet: saldırı + naif tespit (kısa)

`NTDS.dit`, Active Directory veritabanı dosyasıdır ve DC üzerinde `%SystemRoot%\NTDS\ntds.dit` yolunda, **ESE (Extensible Storage Engine)** motoru tarafından sürekli açık ve kilitli tutulur. Saldırgan bu dosyayı doğrudan `copy` ile alamaz çünkü LSASS/ESE onu kilitler. Dolayısıyla çıkarma teknikleri kilidi aşmaya odaklanır:

- **VSS / gölge kopya (Volume Shadow Copy):** `vssadmin create shadow`, `wmic shadowcopy`, `diskshadow` ile snapshot alıp dosyayı gölge birimden kopyalamak.
- **`ntdsutil` "IFM" (Install From Media):** `ntdsutil "ac i ntds" "ifm" "create full C:\temp"` — meşru DCPromo aracının snapshot + dosya export yeteneğini kötüye kullanmak.
- **`ntdsutil snapshot` / `esentutl`:** doğrudan ESE motoru üzerinden dosyayı okumak.
- **DCSync (MS-DRSR):** aslında dosyayı hiç dokunmadan replikasyon protokolüyle hash çekmek (`\GetNCChanges`). Bu, `T1003.006`; dosya çıkarmadan farklı ama aynı hedef.
- **Uzaktan araçlar:** `secretsdump.py`, `crackmapexec`, `Certipy` vb. ile SMB üzerinden.

**Naif tespit** çoğu ekipte şudur: "`vssadmin create shadow` gördüysem alarm ver" veya "`ntds.dit` string'i bir komut satırında geçtiyse alarm ver". Sağlanan Zeek kuralı (`2e69f167-...`, `smb_files` içinde `\ntds.dit` filename araması) de tam olarak bu naif katmandır. İşe yarar ama tek başına ne kör noktaları kapatır ne de FP selini durdurur.

---

## 2. Naif tespit neden yetmez

Tek string / tek komut avcılığının üç ayrı çöküş modu var: **kör nokta**, **atlatma** ve **FP seli**. Üçünü de ayrı ayrı görmek lazım çünkü çözümleri farklı.

**Kör nokta 1 — dosya adı hiç geçmeyebilir.** Zeek `smb_files` kuralı `\ntds.dit` filename'ini arıyor. Ama saldırgan IFM ile export ettiğinde dosya `C:\temp\Active Directory\ntds.dit` olur ve **yerelde** kalır; SMB üzerinden hiç transfer edilmezse Zeek bunu hiç görmez. Saldırgan dosyayı 7-Zip ile `db.dat` diye sıkıştırıp öyle taşırsa filename imzası tamamen ıskalar. Filename tabanlı tespit, saldırganın dosyayı yeniden adlandırmasıyla anında ölür — bu, imza tabanlı avın klasik kırılganlığıdır.

**Kör nokta 2 — DCSync dosyaya hiç dokunmaz.** En sinsi çıkarma yöntemi olan DCSync (`secretsdump.py -just-dc`), diskteki `ntds.dit`'e hiç temas etmez; DC'ye meşru bir replikasyon partner'ı gibi davranıp `DsGetNCChanges` çağırır. Dosya adı avcılığı, VSS avcılığı, `ntdsutil` avcılığı — hiçbiri tetiklenmez. Bunu görmek için tamamen farklı bir telemetriye (Security `4662` — Directory Service Access, replikasyon GUID'leri) bakmak gerekir.

**Kör nokta 3 — `esentutl` ve alternatif motorlar.** `esentutl /y /vss ntds.dit /d out.dit` gibi az bilinen yollar, `vssadmin`'i hiç çağırmadan VSS API'sini programatik kullanır. `vssadmin.exe` process'i hiç doğmaz, sadece `esentutl.exe` doğar — ki bu meşru bir DB bakım aracıdır ve çoğu allowlist'te "temiz" işaretlidir.

**Atlatma — LOLBIN çeşitliliği.** Sağlanan `diskshadow` kuralı (`9f546b25-...`) tam da bu noktaya işaret ediyor: `diskshadow.exe` script mode (`diskshadow /s script.txt`) ile VSS oluşturur ve `vssadmin`'i hiç kullanmaz. Saldırgan `vssadmin`'i izliyorsanız `diskshadow`'a, onu da izliyorsanız `wmic shadowcopy call create`'e, onu da izliyorsanız PowerShell `Win32_ShadowCopy` WMI çağrısına kayar. Tek bir process adına kilitlenen her kural, bir sonraki LOLBIN'e karşı kördür. Bu bir "whack-a-mole" problemi ve tek-sinyal yaklaşımıyla asla kazanılmaz.

**FP seli — meşru operasyon aynı komutları çalıştırır.** İşin can sıkıcı gerçeği: `vssadmin create shadow`, `ntdsutil ifm`, VSS snapshot — bunların hepsi **meşru yedekleme ve DR operasyonlarının** günlük ekmeğidir. Bir DC'de:
- Windows Server Backup / VSS-aware yedekleme her gece snapshot alır.
- Veeam, CommVault, NetBackup ajanları VSS'i saatlerce çağırır.
- SCCM/Intune, SCOM ajanları WMI sorguları atar.
- DC'yi klonlarken veya yeni bir DC promote ederken `ntdsutil ifm` **meşru** kullanılır.

Naif "`vssadmin create shadow` = alarm" kuralı, 500 sunuculu bir ortamda günde yüzlerce tetikleme üretir ve iki hafta içinde analistler bu alarmı "auto-close" kuralına yazar. **En tehlikeli sonuç budur:** kural teknik olarak "çalışır" ama pratikte kapatılmıştır, yani gerçek saldırıyı da kaçırır. Tespit mühendisliğinde bir kuralın FP oranı, onun keşif oranı kadar önemlidir — çünkü göz ardı edilen bir alarm, hiç olmayan bir alarmdan kötüdür (yanlış güven verir).

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek güven, **birbirinden bağımsız telemetri kaynaklarından gelen sinyalleri kısa bir zaman penceresinde bağlamaktan** doğar. Aşağıda gerçek bir VSS tabanlı NTDS çıkarmanın imza zincirini kuruyorum. Kilit fikir: tek tek her adım meşru olabilir, ama **birbirini takip eden bu spesifik sıralama** meşru operasyonda neredeyse hiç görülmez.

**Zincir A — VSS tabanlı çıkarma (klasik):**

```
[T+0s]   Sysmon EventID 1 (process_creation):
         ParentImage: C:\Windows\System32\cmd.exe  (veya wsmprovhost.exe, powershell.exe)
         Image: C:\Windows\System32\vssadmin.exe
         CommandLine: vssadmin create shadow /for=C:
         -> User: bir DA/EA hesabı, INTERAKTIF olmayan bir oturumdan

[T+3s]   Sysmon EventID 1:
         Image: C:\Windows\System32\cmd.exe
         CommandLine: copy \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1\Windows\NTDS\ntds.dit C:\temp\
         -> "GLOBALROOT" + "ntds.dit" aynı komutta = çok güçlü sinyal

[T+4s]   Sysmon EventID 1:
         CommandLine: reg save HKLM\SYSTEM C:\temp\sys.hiv
         -> ntds.dit'i çözmek için SYSTEM hive (boot key) şart; bu ikinci imza

[T+30s]  Sysmon EventID 11 (FileCreate):
         TargetFilename: C:\temp\ntds.dit  (ve sys.hiv)

[T+90s]  Zeek smb_files VEYA Sysmon EventID 3:
         ntds.dit veya sıkıştırılmış arşivin dışa transferi
```

Buradaki yargı: **`vssadmin create shadow` + kısa pencerede (≤60sn) `GLOBALROOT`/`ntds.dit` erişimi + `reg save ...SYSTEM`** üçlüsü, tek başına `vssadmin`'in binlerce meşru tetiklemesinden anlamlı biçimde ayrışır. Yedekleme yazılımı snapshot alır ama **ardından `reg save HKLM\SYSTEM` çalıştırmaz** ve **`ntds.dit`'i `C:\temp`'e elle kopyalamaz** — o dosyayı kendi VSS-aware API'siyle stream eder, komut satırında `ntds.dit` string'i asla görünmez. İşte iki dünyayı ayıran şey: meşru yedek dosya adına dokunmaz; saldırgan dosya adına dokunmak zorundadır.

**Zincir B — DCSync (dosyasız):**

```
[T+0s]   Security EventID 4662 (Operation on object):
         AccessMask: 0x100  (Control Access)
         Properties: {1131f6aa-9c07-11d1-f79f-00c04fc2dcd2}  (DS-Replication-Get-Changes)
                     {1131f6ad-9c07-11d1-f79f-00c04fc2dcd2}  (DS-Replication-Get-Changes-All)
                     {89e95b76-444d-4c62-991a-0facbeda640c}  (GetChangesInFilteredSet)
         SubjectUserName: bir workstation'dan gelen normal kullanıcı (!)

[eşzamanlı] Security EventID 4624 Type 3 + akabinde replikasyon,
            KAYNAK IP bir DC DEĞİL -> en güçlü sinyal
```

DCSync'in altın imzası: **`4662` içinde replikasyon GUID'lerinin (`DS-Replication-Get-Changes-All`) bir DC olmayan bir kaynaktan çağrılması.** Meşru replikasyon sadece DC'ler arasında olur. Bir kullanıcı workstation'ından veya `krbtgt` dışı bir hesaptan gelen `GetNCChanges`, neredeyse kesin olarak `secretsdump`/`mimikatz lsadump::dcsync`'tir. Bu zinciri kurmak için DC'lerin IP listesini bir lookup tablosu olarak SIEM'de tutmak ve `4662`'yi bu listeye karşı zenginleştirmek gerekir — saf log yeterli değildir, **bağlam zenginleştirmesi** şarttır.

**Zincir C — `ntdsutil` IFM:**

```
[T+0s]   Sysmon EventID 1:
         Image: ...\ntdsutil.exe
         CommandLine: ntdsutil "ac i ntds" "ifm" "create full C:\pentest" q q
         ParentImage: powershell.exe / cmd.exe  (meşruda genelde interaktif admin)

[T+5s]   Sysmon EventID 1:
         Image: ...\esentutl.exe  (ntdsutil child'ı; IFM snapshot'ı işler)

[T+10s]  Sysmon EventID 11:
         TargetFilename: C:\pentest\Active Directory\ntds.dit
         TargetFilename: C:\pentest\registry\SYSTEM
         -> IFM her zaman "Active Directory\" ve "registry\" alt klasörlerini üretir; bu yol yapısı imzadır
```

IFM'in ayırt edici imzası, ürettiği **klasör yapısıdır**: `<hedef>\Active Directory\ntds.dit` + `<hedef>\registry\SYSTEM` + `\registry\SECURITY`. Bu spesifik yapı, IFM dışında pek bir şeyle üretilmez ve FileCreate (`EventID 11`) telemetrisinde son derece güvenilir bir bağlantı noktasıdır.

**Zincirin özü:** hiçbir tekil olay "ihlal" demez. Ama "**A (snapshot oluşturma) + kısa pencerede B (SYSTEM hive dışa alma — tamamen farklı bir bağlam, registry) + C (`ntds.dit`/`GLOBALROOT` dosya erişimi)**" birleşimi, meşru operasyonların üretmediği bir imzadır. Detection engineering'de değer, tek kuralın hassasiyetinde değil, **farklı bağlamlardan gelen zayıf sinyalleri zaman ekseninde birbirine dikmekte** yatar.

---

## 4. False positive gerçeği ve triage yargısı

Sahada bu kuralları açtığınızda karşınıza çıkacak gürültü kaynakları, önem sırasına göre:

1. **Yedekleme yazılımı (en yaygın).** Veeam, Windows Server Backup, CommVault her gece DC'de VSS snapshot alır. **Ayırt etme:** yedekleme, `reg save HKLM\SYSTEM` **çalıştırmaz** ve `ntds.dit`'i komut satırında adıyla kopyalamaz. Snapshot'ı kendi servis hesabı (örn. `svc_veeam`) altında, öngörülebilir bir zaman penceresinde (gece 01:00-03:00) yapar. **Triage yargısı:** snapshot'ı tetikleyen parent process yedekleme ajanı mı? Kullanıcı bir servis hesabı mı? Takip eden `reg save`/`ntds.dit copy` var mı? Yoksa — kapat.

2. **DC promote / demote ve klonlama.** Yeni bir DC kurarken veya sanal DC klonlarken `ntdsutil ifm` **meşru** kullanılır. **Ayırt etme:** bu, planlı bir değişiklik penceresinde, bilinen bir admin tarafından, interaktif bir oturumdan (`4624` Type 2/10) yapılır. **Triage yargısı:** change ticket var mı? `ntdsutil`'in parent'ı interaktif bir `cmd.exe`/`mmc` mi yoksa `wsmprovhost.exe` (uzak WinRM) / `powershell -enc` mi? Uzaktan, encode edilmiş, ticket'sız = yükselt.

3. **SCCM / SCOM / vulnerability scanner (Nessus, Qualys).** Bunlar DC'ye WMI sorguları ve bazen VSS ile ilgili enumerasyon yapar. Genelde `4662` gürültüsü ve process access üretirler ama gerçek replikasyon GUID'lerini çağırmazlar. **Ayırt etme:** scanner'ın kaynak IP'si bilinen tarama sunucusudur; `DS-Replication-Get-Changes-All` erişimi yoktur.

4. **Adminlerin manuel VSS'i.** Bir sysadmin bazen sorun giderirken elle `vssadmin list shadows` çalıştırır (`list`, `create` değil — dikkat). `create` çok daha nadirdir.

**Analistin öncelik sırası (triage playbook):**

- **P1 (anında yükselt):** DCSync imzası — DC olmayan kaynaktan `DS-Replication-Get-Changes-All`. Bu neredeyse hiç meşru değildir; change window'a bakmadan IR başlat.
- **P1:** `vssadmin/diskshadow create shadow` + ≤60sn içinde `reg save HKLM\SYSTEM` + `ntds.dit`/`GLOBALROOT` erişimi. Tam zincir = ihlal varsayımıyla hareket et.
- **P2 (24 saat içinde doğrula):** `ntdsutil ifm` uzaktan/encode edilmiş parent'tan, ticket yok. Change yönetimini kontrol et; yoksa yükselt.
- **P3 (bağlamla kapat):** tekil `vssadmin create shadow`, yedekleme servis hesabından, gece penceresinde, takip eden hive/dosya erişimi yok.

Kilit yargı: **tekil sinyalleri asla P1 yapma.** Tekil `vssadmin`'i P1 yaparsan iki hafta içinde ekip kuralı susturur. Bunun yerine tekil sinyali "zenginleştirme tetikleyicisi" yap — o olay gelince ilgili host'ta ±5 dakikalık pencerede `reg save`, `ntds.dit`, `GLOBALROOT`, replikasyon aktivitesi ara. Zincir tamamlanırsa P1'e yükselt. Bu, "alarm yorgunluğu" ile "kaçırılan ihlal" arasındaki dengeyi kuran şeydir.

---

## 5. Kaçınma → karşı-tespit

İyi bir saldırgan, yukarıdaki imzaların hiçbirini bilerek bırakmaz. Dokümanlarda yazmayan atlatmalar ve onlara karşı ikinci-derece tespit:

**Atlatma 1 — `esentutl` ile sessiz VSS.** `esentutl.exe /y /vss C:\Windows\NTDS\ntds.dit /d C:\temp\out.dit` komutu, VSS API'sini programatik çağırır; `vssadmin.exe`, `diskshadow.exe`, `wmic` process'lerinin **hiçbiri doğmaz**. `esentutl` meşru bir DB aracı olduğu için çoğu allowlist onu görmezden gelir.
**Karşı-tespit:** `esentutl.exe` komut satırında `/vss` **ve** `ntds.dit` (veya `.dit` uzantısı) birlikte geçiyorsa alarm. `esentutl`'un meşru kullanımı (`/mh`, `/p`, `/r` — header dump, repair, recovery) `/vss` bayrağını nadiren kullanır ve `ntds.dit`'e canlı sistemde `/vss` ile dokunmak neredeyse her zaman kötü niyetlidir. Ayrıca `esentutl`'un `ParentImage`'i bir DC'de `services.exe`/`ntdsutil.exe` dışı bir şeyse (örn. `powershell.exe`) şüphe artar.

**Atlatma 2 — WMI ile process-adsız snapshot.** `wmic shadowcopy call create Volume='C:\'` veya PowerShell `([WMICLASS]"root\cimv2:Win32_ShadowCopy").Create("C:\","ClientAccessible")`. Bu, `vssadmin` process'i olmadan snapshot üretir.
**Karşı-tespit:** Windows `System` log **EventID 7036/7040** (Volume Shadow Copy service durum değişimi) ve daha iyisi, VSS operatör logu **`Microsoft-Windows-Volsnap`** ve **`Microsoft-Windows-Backup`** kanalları. Snapshot oluşumu process'ten bağımsız olarak burada iz bırakır. Ayrıca WMI provider'ın kendisi Sysmon `EventID 1`'de `WmiPrvSE.exe` child'ı olarak yakalanabilir — snapshot'ı tetikleyen `WmiPrvSE.exe` + DC + takip eden dosya erişimi = zincir.

**Atlatma 3 — `ntds.dit`'i asla çıkarmadan DCSync.** Bölüm 3'te işlendi; dosya tabanlı her tespit için ölümcül. Tek karşı-tespit `4662` + replikasyon GUID + DC olmayan kaynaktır. Buna ek olarak **`4742` (computer account changed)** ve anormal replikasyon metadata'sı (repadmin ile korele) ikinci-derece sinyal verir.

**Atlatma 4 — dosya adını değiştirme + parçalama.** Saldırgan `ntds.dit`'i `C:\temp\update.bin` olarak export edip, WinRAR ile parçalayıp DNS/HTTPS üzerinden sızdırır. Filename tabanlı Zeek kuralı tamamen kör.
**Karşı-tespit:** filename yerine **davranışa** bak. Bir DC'de kısa sürede `C:\temp` veya `C:\Windows\Temp` altında **~10-50 MB+ tek bir yeni dosya** oluşması (ntds.dit tipik boyutu) + ardından bir arşivleme aracının (`7z.exe`, `rar.exe`, PowerShell `Compress-Archive`) o yolu okuması + giden bir ağ akışı. Boyut + zamanlama + arşivleme, dosya adından bağımsız bir imzadır. Ayrıca DC'de `C:\temp`'e yazma **normalde olmaz** — DC'nin dosya sistemi çok statiktir; herhangi bir kullanıcı yazması bile başlı başına anomalidir.

**İkinci-derece prensip:** saldırgan process adını, dosya adını ve komut satırını değiştirebilir — ama snapshot'ın **VSS altyapısında bıraktığı izi** (Volsnap logu), replikasyonun **protokol seviyesindeki imzasını** (`4662` GUID), ve `ntds.dit`'i çözmek için **mutlaka gereken SYSTEM boot key erişimini** kolayca gizleyemez. Tespiti bu "kaçınılmaz" noktalara demirlemek, imza tabanlı ava göre çok daha dayanıklıdır. Saldırganın atlatamayacağı fiziği hedefle, atlatabileceği string'i değil.

---

## 6. SIEM/saha gerçeği

**Field mapping ve varsayılan loglanmayanlar — en kritik bölüm.** Yukarıdaki zincirlerin çoğu, **varsayılan Windows loglaması ile GÖRÜNMEZ.** Bunu bilmeden kural yazmak, boş bir index'e sorgu atmaktır.

- **Sysmon `EventID 1` (process_creation), `EventID 11` (FileCreate), `EventID 3` (network):** bunların hiçbiri stok Windows'ta yoktur. Sysmon yüklü ve doğru config'li (SwiftOnSecurity/Olaf tabanlı) olmalı. `ntdsutil`, `esentutl`, `vssadmin`, `diskshadow` process ve command-line görünürlüğü tamamen buna bağlı. Sysmon yoksa Security `4688` (process creation) devreye girmeli — ama `4688` varsayılan **kapalıdır** ve command-line loglaması ayrı bir GPO (`Include command line in process creation events`) gerektirir. Bu GPO açık değilse `4688` gelse bile `CommandLine` alanı boştur ve `vssadmin create shadow` ile `vssadmin list shadows`'u ayırt edemezsiniz — tüm tespit çöker.

- **Security `4662`:** DCSync tespitinin bel kemiği ama **varsayılan olarak replikasyon GUID'lerini üretmez.** DC'nin **SACL**'ı, Directory Service nesnesi üzerinde audit için yapılandırılmalı ("Audit Directory Service Access" — Advanced Audit Policy). Bu yapılmadan `4662` ya hiç gelmez ya da `Properties` alanı boş gelir. Sahada gördüğüm en yaygın hata: DCSync kuralı yazılmış ama SACL yapılandırılmadığı için index'te hiç `4662`+GUID olayı yok — kural sonsuza dek sessiz. **Bu bölümdeki her kuraldan önce audit policy'yi doğrula.**

- **Volsnap / Backup operatör logları:** `Microsoft-Windows-Volsnap/Operational` ve `Microsoft-Windows-Backup` kanalları çoğu SIEM'e **hiç toplanmaz** çünkü WEF/agent config'inde bu kanallar yoktur. WMI tabanlı snapshot'ı yakalamak istiyorsanız bu kanalları toplama listesine eklemek gerekir.

**Splunk / Sentinel / Elastic farkı:**

- **Splunk:** Sysmon verisi tipik olarak `WinEventLog:Microsoft-Windows-Sysmon/Operational` sourcetype'ında. Command-line araması: `EventCode=1 (Image="*vssadmin.exe" OR Image="*diskshadow.exe") CommandLine="*create*shadow*"`. Zincir korelasyonu için `transaction` veya daha iyisi `stats` + `streamstats` ile host bazında zaman penceresi. DCSync için `EventCode=4662 Properties="*1131f6ad*"` (GetChangesAll GUID substring) + `| lookup dc_ip_list src_ip` ile zenginleştirme. Splunk'ta GUID'ler bazen `{}` içinde, bazen çıplak gelir — `Properties="*1131f6aa*"` gibi wildcard substring en güvenlisi.

- **Sentinel (KQL):** Sysmon verisi `SecurityEvent` değil genelde `Event` (Sysmon channel) tablosunda; MDE varsa `DeviceProcessEvents` (bu en zengini — `ProcessCommandLine`, `InitiatingProcessFileName` hazır parse'lı). DCSync için `SecurityEvent | where EventID == 4662 | where Properties has "1131f6ad-9c07-11d1-f79f-00c04fc2dcd2"`. Zincir için `join kind=inner ... on Computer` + `where TimeGenerated between (...)` veya en temizi `DeviceProcessEvents` üzerinde `partition by DeviceId` ile ardışık process arama. MDE'nin `IdentityDirectoryEvents` tablosu ayrıca native DCSync tespiti sunar — mümkünse ona da bak.

- **Elastic (ECS):** Sysmon Winlogbeat/Elastic Agent ile ECS'e map'lenir: `process.name`, `process.command_line`, `process.parent.name`, `file.path`. Sorgu: `event.code:"1" and process.name:("vssadmin.exe" or "diskshadow.exe") and process.command_line:*shadow*`. Elastic'in avantajı **EQL sequence** desteği — zinciri native ifade edebilirsin:
  ```
  sequence by host.name with maxspan=60s
    [process where process.name == "vssadmin.exe" and process.command_line : "*create*shadow*"]
    [process where process.command_line : "*reg*save*HKLM*SYSTEM*"]
  ```
  Bu, korelasyon zincirini tek sorguda ifade etmenin en temiz yoludur; Splunk/Sentinel'de aynı şeyi `streamstats`/`join` ile elle kurman gerekir.

**Tuning gerçeği ve kapanış yargısı.** Bir kuralı prod'a alırken sıralama şu olmalı: (1) önce **görünürlüğü doğrula** — Sysmon config'de ilgili process'ler ve FileCreate izleniyor mu, `4662` SACL açık mı, command-line loglaması aktif mi? Bunlar yoksa kural yazmak zaman kaybı. (2) Sonra **baseline çıkar** — 2-4 hafta boyunca `vssadmin/diskshadow/ntdsutil` tetiklemelerinin hangi hesaplardan, hangi parent'lardan, hangi zaman pencerelerinden geldiğini topla; yedekleme servis hesaplarını ve bilinen değişiklik pencerelerini allowlist'e al. (3) Ancak **ondan sonra** korelasyon kuralını P1 yap. Bu sırayı atlayıp doğrudan tekil `vssadmin` alarmını açan ekip, iki hafta içinde ya kuralı susturur ya da analistlerini yakar — her ikisi de gerçek NTDS çıkarmasını kaçırmaya götürür. Detection engineering'in acı gerçeği budur: kötü tune edilmiş bir kural, hiç olmayan bir kuraldan daha tehlikelidir, çünkü sahte bir güvenlik hissi verir. NTDS.dit gibi "kaybedersen domain'i kaybettin" bir varlıkta bu lüksü kaldıramayız — zinciri kur, bağlamı zenginleştir, fiziği hedefle.
