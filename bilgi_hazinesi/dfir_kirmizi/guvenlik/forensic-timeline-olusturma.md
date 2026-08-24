# Forensic Timeline Oluşturma (Olay Zaman Çizelgesi)

> Kıdemli DFIR / IR Lead notları. Bu metin bir aracın nasıl çalıştırılacağını anlatan bir kılavuz değil; bir olay sırasında **hangi artefaktı görünce nereye gittiğimi**, hangi sırayla düşündüğümü ve neye göre karar verdiğimi anlatan pratisyen defteridir.

---

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Forensic timeline (süper-timeline / birleşik zaman çizelgesi) oluşturmanın tek bir amacı vardır: **dağınık artefaktları tek bir zaman ekseninde yan yana dizip, saldırının hikâyesini dakikası dakikasına yeniden kurmak.** Bir olay müdahalesinde "ne oldu?" sorusunun cevabı asla tek bir logda durmaz. EDR bir process başlangıcı gösterir, güvenlik duvarı bir dış bağlantı gösterir, dosya sisteminde bir DLL değişir, registry'de bir Run anahtarı belirir. Bunlar tek başlarına gürültüdür. Ama doğru zaman çizelgesinde alt alta dizildiğinde saldırının **initial access → execution → persistence → lateral movement → collection → exfiltration** akışı ortaya çıkar.

IR sürecinde timeline, PICERL/NIST modelindeki **Identification** ve **Analysis** fazının kalbidir. Triage'da "bir şey oldu" dedik; timeline'da "tam olarak şu oldu, şu saatte başladı, şu makineye yayıldı, şu veri gitti" diyoruz. Timeline'ın çıktısı iki yere gider:
- **Containment/Eradication kararına**: Patient zero'yu ve persistence'ı doğru tespit etmezsen, sistemi temizler temizlemez saldırgan geri gelir.
- **Scope (kapsam) tayinine**: "Kaç makine etkilendi, ne zaman girdiler, ne kadar süre içerideydiler (dwell time)?" sorusunun tek dürüst cevabı buradadır.

Kritik nokta: timeline aynı zamanda **hipotez test aracıdır**. Sen "phishing ile girdiler" dersin; timeline bunu ya doğrular (Outlook → ekli dosya → wscript.exe zinciri) ya da çürütür (aslında dışarıya açık RDP'den brute-force). Duyguyla değil, artefaktın söylediğiyle ilerlersin.

---

## 2. Adım-adım İŞ AKIŞI ve KARAR (asıl değer)

### 2.0 Önce delili topla, sonra düşün — sıralama önemli

Timeline kurmaya oturmadan önce **hangi veriye sahip olduğun** akışı belirler. Canlı bir makinede miyim, yoksa elimde bir disk imajı mı var, yoksa sadece merkezî loglar mı? Order of volatility'e (bkz. Bölüm 3) göre önce uçucu olanı, sonra kalıcı olanı toplarım.

Pratikte sahaya gittiğimde ilk hamle **KAPE (Kroll Artifact Parser and Extractor)** ile hedefli triage collection'dır. Tüm diski imajlamak saatler alır; ben olay başında dakikalar istiyorum. KAPE'nin `!SANS_Triage` veya `KapeTriage` target'ı ile bir makineden şu kritik artefakt setini 3-10 dakikada çekerim:
- `$MFT`, `$LogFile`, `$UsnJrnl:$J` (dosya sistemi omurgası)
- Event log'lar (`Security`, `System`, `Application`, `Sysmon/Operational`, `PowerShell/Operational`, `TerminalServices`, `WMI-Activity`)
- Registry hive'ları (`SYSTEM`, `SOFTWARE`, `SAM`, `SECURITY`, `NTUSER.DAT`, `UsrClass.dat`, `Amcache.hve`)
- Prefetch, SRUM, WMI repository, scheduled task XML'leri, browser history

Uzaktaki onlarca/yüzlerce makine için aynı işi **Velociraptor** ile yaparım. Velociraptor'un `Windows.KapeFiles.Targets` artifact'ı ile filo genelinde aynı triage'ı paralel toplarım; ayrıca hunt modunda "şu IOC'yi tüm makinelerde ara" derim. Bu, scope tayininde tek makine düşüncesinden filo düşüncesine geçtiğim andır.

**Karar kuralı:** Eğer RAM hâlâ canlıysa ve şüpheli aktif çalışıyorsa, disk imajından ÖNCE bellek dökümü alırım (WinPMEM / Velociraptor'un memory acquisition'ı / FTK Imager). Çünkü reboot'ta uçucu delil — decrypted payload, injected code, açık network soketleri, cleartext parolalar — sonsuza dek gider.

### 2.1 Süper-timeline'ın omurgası: dosya sistemi

Timeline'ın iskeleti **NTFS `$MFT`**'dir. Neden? Çünkü her dosyanın 4 zaman damgası vardır — **MACB**: Modified, Accessed, Changed ($MFT değişimi), Born (Created). Bunları **MFTECmd** (Eric Zimmerman) ile parse ederim:

```
MFTECmd.exe -f "$MFT" --csv out --csvf mft.csv
```

Ama tek başına $MFT yetmez, çünkü zaman damgaları **timestomp** edilebilir (bkz. anti-forensics). O yüzden `$MFT`'yi **`$UsnJrnl:$J`** ile çaprazlarım. USN Journal dosya seviyesindeki her değişimi (create, rename, delete, data extend) sırayla kaydeder ve timestomp'lamak çok daha zordur. **Karar mantığı:** Bir DLL'in $STANDARD_INFORMATION zamanı 2019 gösteriyor ama USN Journal onu bu sabah 03:14'te "FileCreate" olarak yazmışsa — o dosya timestomp'lanmıştır ve şüpheli #1'dir.

Eric Zimmerman'ın `$STANDARD_INFORMATION` ile `$FILE_NAME` attribute'larını karşılaştırma numarası da burada devreye girer: klasik timestomp araçları $SI'yi değiştirir ama $FN'yi çoğu zaman değiştirmez. $SI < $FN veya $SI'de saniye/alt-saniye alanı sıfırlanmışsa (`.000000` ile biten manipüle zamanlar) alarm zilim çalar.

### 2.2 "Ne çalıştırıldı?" — execution artefaktları

Initial access noktasını bulmak için "bu makinede ne çalıştı ve ilk defa ne zaman çalıştı?" sorusuna gitmeliyim. Gittiğim artefaktlar ve **her birinin ne söylediği**:

- **Prefetch** (`C:\Windows\Prefetch\*.pf`) → **PECmd** ile parse. Bir executable'ın çalıştığını, kaç kez ve son 8 çalışma zamanını söyler. `svchost.exe` C:\Users\Public'ten çalışmışsa bu tek başına olaydır.
- **Amcache.hve** → **AmcacheParser**. Çalışmış/varlığı bilinen binary'lerin SHA1'ini ve ilk görülme zamanını verir. Silinmiş malware'in hash'ini buradan kurtarıp VirusTotal/tehdit istihbaratıyla eşlerim.
- **ShimCache (AppCompatCache, SYSTEM hive)** → **AppCompatCacheParser**. Dikkat: ShimCache zaman damgası **çalıştırma değil, dosyanın $SI Modified zamanıdır** ve girdiler yalnızca reboot'ta yazılır. Acemi burada tuzağa düşer (bkz. Bölüm 5).
- **SRUM (System Resource Usage Monitor)** → **SrumECmd**. Hangi process ne kadar ağ baytı göndermiş/almış, saatlik olarak. **Exfiltration'ı tespit etmenin en sevdiğim yolu**: normalde 2 MB gönderen bir process bir gece 8 GB göndermişse, veri sızıntısını burada yakalarım.
- **Sysmon Event ID 1 (Process Create)** ve **Security 4688** → varsa altın madeni. Tam komut satırı, parent-child ilişkisi, hash, kullanıcı bağlamı. `winword.exe → cmd.exe → powershell.exe -enc <base64>` zincirini burada okurum.

**Karar mantığı örneği:** Prefetch'te `powershell.exe`, Amcache'te aynı dakikada bir `update.exe` (SHA1 tehdit istihbaratında biliniyor), Sysmon'da parent'ı `winword.exe` → sonuç: **makro içeren Office belgesiyle initial access + PowerShell downloader**. Üç ayrı artefakt, tek hikâye.

### 2.3 "Nasıl kalıcı oldular?" — persistence

Eradication'ı doğru yapabilmek için tüm persistence mekanizmalarını çıkarmam şart. Bakılacak yerler (ve araç):
- Registry Run/RunOnce, Winlogon, Image File Execution Options → **Registry Explorer / RECmd** ile bookmark'lı taramalar.
- **Scheduled Tasks** (`C:\Windows\System32\Tasks\` XML'leri + `TaskScheduler/Operational` Event ID 106/140/200).
- **Services** (SYSTEM hive `Services` anahtarı + Event ID 7045 "yeni servis kuruldu").
- **WMI Event Subscription** persistence (fileless!) → WMI repository'yi parse ederim; `__EventFilter`, `CommandLineEventConsumer`, `__FilterToConsumerBinding` üçlüsü varsa klasik WMI persistence'tır.
- Startup klasörleri, DLL search-order hijack, COM hijack.

**Karar mantığı:** Event 7045 ile 03:14'te kurulan bir servis + aynı dakika USN Journal'da o servisin binary'sinin oluşturulması + ShimCache'de aynı yol → persistence noktası kesinleşti, eradication listesine girdi.

### 2.4 "Nasıl yayıldılar?" — lateral movement ve auth

Scope'u belirleyen faz budur. Kaynak ve hedef makinelerdeki auth artefaktlarını timeline'a koyarım:
- **Security Event 4624 (logon)** — özellikle **Type 3 (network)** ve **Type 10 (RDP)**. Kaynak IP + hesap.
- **4648** (explicit credential kullanımı — pass-the-hash / runas göstergesi).
- **4672** (özel yetkilerle logon — admin hareketi).
- Hedef makinede **RDP**: `TerminalServices-LocalSessionManager/Operational` Event 21/25.
- **PsExec izi**: hedefte Event 7045 ile `PSEXESVC` servisi + `ADMIN$` erişimi.
- **WMI/WinRM lateral**: `WMI-Activity/Operational` ve WinRM logları.

**Karar mantığı:** Patient zero'da 03:20'de `4648` (explicit cred) → hedef sunucuda 03:21'de `4624 Type 3` aynı hesapla + 7045 PSEXESVC → **PsExec + çalınmış kimlik bilgisiyle lateral movement**. Timeline'da iki makinenin logu yan yana gelince ok gibi görünür.

### 2.5 Bellek analizi — disk yalan söylediğinde

Fileless malware, process injection ve in-memory payload disk timeline'ında ya hiç görünmez ya da zayıf görünür. Burada **Volatility 3** devreye girer:
- `windows.pslist` / `windows.psscan` — gizlenmiş/unlinked process'ler (`psscan` pslist'in göremediğini bulur).
- `windows.malfind` — injected/executable private memory bölgeleri (RWX, MZ header).
- `windows.netscan` — o an açık olan C2 bağlantıları.
- `windows.cmdline`, `windows.dlllist`, `windows.svcscan`.

Bellekten çıkardığım process başlangıç zamanlarını ve network bağlantılarını da timeline'a eklerim. **Karar mantığı:** Diskte hiçbir yürütülebilir iz yok ama `malfind` `explorer.exe` içinde RWX shellcode + `netscan` bilinen C2 IP'sine bağlantı gösteriyorsa → process hollowing / injection ile fileless C2. Diskte olmayan hikâyeyi bellek anlatır.

### 2.6 Her şeyi birleştir — süper-timeline ve pivot

Tüm bu artefaktları tek eksende toplamak için iki yaklaşım kullanırım:

1. **Plaso / log2timeline** → `psort` ile birleşik CSV/DB. Her artefakt tipini normalize edip tek zaman çizelgesine döker. Güçlü ama gürültülüdür; ham log2timeline çıktısı milyonlarca satırdır.
2. **Timesketch** → Plaso çıktısını yüklerim, olayları etiketlerim (star/tag), yorum eklerim, ekip olarak aynı sketch üzerinde çalışırız. "Analiz penceresi" ile ilgilendiğim 30 dakikaya zoom yaparım.

**Kritik pratik:** Ham süper-timeline'da boğulmamak için **pivot point** ile başlarım. Elimde bir "bilinen kötü zaman" olur (EDR alert'i, ilk şüpheli process, ilk C2 bağlantısı). O zamanı merkeze alıp **± birkaç dakikalık pencereye** odaklanırım. Saldırgan hareketleri saniyeler-dakikalar içinde kümelenir; timeline'da bu "olay çevresindeki artefakt yoğunlaşması" gözle görülür. Oradan zincirin başına doğru geriye (initial access) ve sonuna doğru ileriye (exfil) yürürüm.

**YARA'nın yeri:** Timeline sırasında bir hash veya davranış şüpheliyse, YARA kurallarıyla hem disk hem bellek üzerinde tarar, aynı IOC'nin başka makinelerdeki varlığını Velociraptor hunt'ıyla filo geneline yayarım. Böylece "bu makine" düşüncesinden "kaç makine" cevabına geçerim.

### 2.7 Zaman dilimi ve normalizasyon — sessiz katil

Her artefaktı **UTC'ye normalize etmeden** timeline kurmak en sık yapılan ölümcül hatadır. $MFT UTC, event log çoğu zaman UTC (ama görüntüleyici lokal saat gösterir), bazı uygulama logları lokal, browser history bazen Unix epoch. Bunları karıştırırsan iki gerçek olayın arasına yapay 3 saatlik boşluk koyar, nedensellik zincirini kırarsın. **Kural: Her şey UTC, kaynak zaman dilimini not et, sonra tek eksende birleştir.** Plaso bunu doğru yapar ama girdi zaman dilimini (`-z`) doğru vermek senin sorumluluğundur.

---

## 3. Kritik dikkat noktaları

### Order of Volatility (uçuculuk sırası)
Delil, uçuculuk sırasına göre toplanır — en çabuk kaybolan önce. Pratik sıralamam:
1. CPU register/cache (pratikte erişilmez, geç)
2. **RAM** (process, injected code, network state, decrypted data, parolalar)
3. Network state / açık bağlantılar (`netstat`, ARP)
4. Çalışan process listesi ve açık handle'lar
5. Disk (kalıcı artefaktlar)
6. Uzak loglar, yedekler, fiziksel konfigürasyon

**Neden önemli:** Şüpheli makinede paniğe kapılıp önce diski imajlamak, sonra reboot etmek → belleği yani en değerli fileless delili öldürmektir. Canlı ve aktif tehdit varsa **önce RAM**.

### Delil bütünlüğü (integrity)
- Her imaj/dosya alındığı anda **hash'lenir** (SHA-256; MD5 sadece eski uyumluluk için, tek başına yeterli değil). Alma anında ve her transferde hash doğrulanır.
- **Write blocker** kullan (fiziksel disk için donanım write blocker; imaj için read-only mount). Delili yazmadan oku.
- **Orijinali asla üzerinde çalışma.** Çalışma kopyası (working copy) üzerinde analiz yaparsın; orijinal imaj mühürlü kalır.

### Chain of Custody (delil zinciri)
Her delil parçası için: kim topladı, ne zaman (UTC), nereden, hangi araçla, kime devretti, nerede saklanıyor — **kesintisiz** kayıt. Mahkemeye/soruşturmaya gidecek bir olayda zincirdeki tek boşluk tüm delili çürütür. İç olay bile olsa bu disiplini bozmam; çünkü olayın hukuki boyuta döneceğini baştan asla bilemezsin.

### Anti-forensics'e karşı
Saldırgan izini siler; sen bunu bilerek çalışırsın:
- **Timestomp** → $SI'yi $FN ile ve $MFT'yi USN Journal ile çaprazla.
- **Log temizleme** → Security Event **1102** ("audit log cleared") ve System **104** ("log cleared") başlı başına IOC'dir. Ayrıca event log'daki **record number süreksizliği** (atlanan sıra numaraları) manipülasyon işaretidir. Merkezî SIEM/forwarder varsa lokal silme işe yaramaz — bu yüzden log forwarding hayati.
- **Dosya silme** → $MFT'de silinmiş kayıtlar, USN Journal'da `FileDelete` girdileri, VSS (Volume Shadow Copy) ve Amcache silinmiş binary'nin hash'ini hâlâ tutar.
- **Şüphe kuralı:** Bir yerde delilin "fazla temiz" olması, o temizliğin kendisi bir delildir.

---

## 4. Gerçek dünya senaryosu

**Vaka:** Bir üretim firmasının SOC'undan gece 04:00'te alarm: bir dosya sunucusundan bilinmeyen bir yurt dışı IP'ye anormal büyük veri transferi. IR lead olarak çağrıldım.

**Toplama.** Aktif transfer sürüyor. Önce kural gereği dosya sunucusundan **WinPMEM ile RAM dökümü**, ardından Velociraptor ile hem dosya sunucusundan hem de son 24 saatte o sunucuya bağlanan iş istasyonlarından **KapeFiles.Targets** triage collection. Her imaj SHA-256 ile hash'lendi, chain of custody formu açıldı.

**Pivot point.** SRUM (SrumECmd) dosya sunucusunda 03:40-04:10 arası `rclone.exe` adında bir process'in ~14 GB **gönderdiğini** gösterdi. İşte pivot zamanım: 03:40 civarı. rclone meşru bir araç ama bu sunucuda hiç kurulu değildi → **dual-use exfil aracı**.

**Geriye yürüme (initial access'e doğru).**
- Prefetch (PECmd): `rclone.exe` ilk çalışma 03:38. Parent zinciri Sysmon Event 1'de: `rclone.exe`'yi bir scheduled task tetiklemiş.
- Scheduled Tasks XML + Event 106: 03:31'de `SystemUpdateTask` adlı görev oluşturulmuş. Persistence bulundu.
- Bu göreve dokunan kullanıcı: Security 4624 **Type 3**, 03:29, kaynak IP bir iş istasyonu (WS-042), hesap `svc_backup`.
- WS-042'ye gidiyorum. Orada 03:15'te 4648 (explicit cred `svc_backup`) + PSEXESVC servisi (7045). Yani lateral movement PsExec + çalınmış servis hesabı.
- WS-042'de daha geriye: 02:58'de Sysmon zinciri `outlook.exe → winword.exe → cmd.exe → powershell.exe -enc …`. Amcache o dakikada bir `invoice.doc` ve indirilen `svc.exe` hash'i — tehdit istihbaratında bilinen bir loader.
- $MFT vs USN çaprazı: `svc.exe`'nin $SI zamanı 2020 (**timestomp**), USN Journal'da FileCreate 02:58. Yalan yakalandı.

**İleriye yürüme (exfil'i doğrulama).** Bellek analizi (Volatility 3 `netscan`) dosya sunucusunda rclone'un o yurt dışı IP'sine açık bağlantısını doğruladı; `malfind` ek injection göstermedi (fileless değil, basit binary). SRUM'daki 14 GB ile netscan tutarlı.

**Sonuç (varılan yargı).** Zaman çizelgesi:
- 02:58 — WS-042'de makrolu `invoice.doc` ile initial access, `svc.exe` loader (timestomp'lu).
- 03:15 — `svc_backup` kimlik bilgisi çalındı, PsExec ile dosya sunucusuna lateral movement.
- 03:31 — `SystemUpdateTask` ile persistence.
- 03:38-04:10 — `rclone` ile ~14 GB veri exfiltration.

**Aksiyon:** Patient zero WS-042 ve dosya sunucusu izole edildi, `svc_backup` hesabı devre dışı + parola/anahtar rotasyonu, scheduled task ve rclone eradike edildi, C2 IP'si tüm filoda Velociraptor hunt'ıyla arandı (başka etkilenen yok — dwell time yalnızca ~72 dakika, erken yakalandı). SRUM sayesinde sızan verinin **hangi paylaşım** olduğu da tespit edilip bildirim yükümlülüğü değerlendirildi.

Dikkat: hiçbir adımda tek artefakta güvenmedim. rclone'u SRUM gösterdi ama exfil'i netscan doğruladı; timestomp'u USN çürüttü; lateral'i iki makinenin logu birlikte kanıtladı. **Timeline'ın gücü tek delilde değil, çapraz doğrulamada.**

---

## 5. Yaygın tuzaklar ve pro yargısı

**1. Zaman dilimini normalize etmemek.** Acemi $MFT (UTC) ile lokal saatli logu aynı çizelgeye koyar, 3 saatlik hayalet boşluk yaratır, nedenselliği ters kurar. Pro her şeyi UTC'ye çevirir ve kaynağı not eder.

**2. Zaman damgalarına körü körüne inanmak.** $SI zamanı timestomp'lanabilir. Pro her kritik zamanı ikinci bir kaynakla (USN Journal, event log, Amcache) çaprazlar. Tek artefakt = hipotez, çapraz doğrulanmış artefakt = bulgu.

**3. ShimCache'i "çalıştırma zamanı" sanmak.** AppCompatCache zaman damgası dosyanın **$SI Modified** zamanıdır, çalıştırma değil; girdiler reboot'ta yazılır ve sıralamaları çalıştırma sırasını göstermez. Bunu "program şu saatte çalıştı" diye rapora yazmak klasik acemi hatasıdır. "Program bu makinede biliniyordu/mevcuttu" demek doğrudur.

**4. Belleği önce almadan reboot/kapatma.** Panikle makineyi kapatıp fileless malware'i, açık C2'yi, cleartext parolayı öldürmek. Order of volatility ihlali. Aktif tehditte **önce RAM**.

**5. Süper-timeline'da boğulmak.** Ham log2timeline çıktısını baştan sona okumaya çalışmak — milyonlarca satır, günler kaybı. Pro pivot point'ten başlar, dar pencereye zoom yapar, zinciri iki yöne yürür.

**6. Sadece bir artefakt sınıfına yaslanmak.** "EDR her şeyi görür" diyip dosya sistemine, registry'ye, belleğe bakmamak. EDR devre dışı bırakılmış veya olaydan sonra kurulmuş olabilir; saldırgan EDR'ın kör noktasında çalışır. Pro çok kaynaklı çalışır.

**7. Log temizliğinin kendisini görmezden gelmek.** Event 1102/104'ü "log yok, veri kaybı" diye geçmek. Halbuki temizliğin varlığı ve **zamanı** başlı başına saldırganın hangi izini gizlemek istediğini söyler — negatif delil de delildir.

**8. Delil bütünlüğünü ciddiye almamak.** "İç olay, mahkemeye gitmez" diye hash almamak, write blocker kullanmamak, orijinal üzerinde çalışmak. Olayın nereye evrileceğini baştan bilemezsin; disiplini her zaman uygularsın. Bir kez kirlenen delil geri gelmez.

**9. Anlatıya âşık olmak (confirmation bias).** İlk hipotezine (örn. "phishing") kilitlenip onu doğrulayan artefaktları toplayıp çürütenleri görmezden gelmek. Pro yargısı: timeline'ı hipotezi **çürütmek** için de kullanır. Artefakt ne diyorsa o; senaryo veriye uyar, veri senaryoya değil.

**10. Scope'u tek makinede bırakmak.** Patient zero'yu bulup "tamam" demek. Lateral movement varsa saldırgan başka yerdedir. Pro her IOC'yi (hash, IP, hesap, task adı) filo geneline hunt eder ve dwell time ile yayılımı ölçmeden containment'ı "bitti" saymaz.

---

### Kapanış yargısı
İyi bir forensic timeline, araç bilgisiyle değil **çapraz doğrulama disipliniyle** kurulur. Araçlar (KAPE, Velociraptor, Plaso, Timesketch, Volatility, Eric Zimmerman seti, YARA) sana ham zaman damgalarını verir; değeri yaratan, o damgaları birbirine karşı okuyup yalanı ayıklaman, pivot'tan başlayıp hikâyeyi iki yöne kurman ve her bulguyu ikinci bir kaynağa dayaman. Timeline bir rapor değil, test edilmiş bir **iddia**dır: "Şu saatte şu oldu" derken arkasında her zaman en az iki bağımsız artefakt durmalı.
