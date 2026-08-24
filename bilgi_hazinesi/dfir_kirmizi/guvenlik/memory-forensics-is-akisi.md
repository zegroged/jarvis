# Bellek Forensics İş Akışı — Pratisyen Notları

> Bu metin, saha deneyiminden damıtılmış bir iş akışıdır. Amacı komut ezberletmek değil, "hangi artefaktı görünce hangi sonuca gittiğim" karar mantığını aktarmaktır. Araçlar değişir; yargı kalır.

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Bellek forensics (RAM analizi), bir sistemin **o anki canlı halini** yakalayıp incelemektir. Diskte olmayan, sadece bellekte yaşayan gerçekleri ortaya çıkarır: şifresi çözülmüş (decrypted) payload'lar, bellekte çalışan ama diske hiç düşmemiş fileless malware, açık ağ bağlantıları, çözülmüş kimlik bilgileri (LSASS içindeki cleartext veya NTLM hash'ler), injection edilmiş kod, ve saldırganın komut geçmişi.

IR yaşam döngüsündeki yeri nettir: **Identification (tespit)** ile **Containment (kapsama)** arasındaki köprüdür. Bir EDR alarmı ya da SIEM korelasyonu size "bu makinede bir şey var" der; bellek analizi size "ne olduğunu, ne kadar ilerlediğini ve saldırganın elinde ne olduğunu" söyler. Diğer bir deyişle, triyajda hız, derinlik analizinde ise kesinlik sağlar.

Pro'nun buradaki temel kabulü şudur: **Order of volatility (uçuculuk sırası).** RAM, en uçucu delildir. Makineyi kapatırsanız kaybolur; hatta bekletirseniz bile süreçler ölür, bağlantılar kapanır, bellek sayfaları geri kazanılır (page reuse). Bu yüzden bellek forensics, olay müdahalesinde çoğu zaman **ilk toplanan** delildir — diskten bile önce. "Önce imajı al, sonra düşün" değil; "önce RAM'i dondur, sonra diski al, sonra düşün."

Bir uyarı, en baştan: bellek analizi güçlüdür ama tek başına delil zinciri kurmaz. RAM size "o an" fotoğrafını verir; **zaman çizelgesini (timeline)** disk artefaktlarıyla (MFT, event log, prefetch, ShimCache/Amcache) birleştirmeden vaka bütünlenmez. Bellek, hipotez üretir; disk, onu tarih ve süreklilikle doğrular.

## 2. Adım-adım iş akışı ve karar (asıl değer)

### Adım 0 — Toplamadan önce: karar verme

İlk soru teknik değil, taktikseldir: **Makineyi canlı mı bırakacağım, yoksa hemen izole mi edeceğim?**

- Aktif, yayılan bir saldırgan (lateral movement, ransomware pre-encryption) varsa: ağdan izole et ama **gücü kesme.** Ağ kablosunu çekmek veya EDR'ın network containment'ını kullanmak süreçleri öldürmez, RAM'i korur.
- Ransomware şifreleme başladıysa dahi karar nüanslıdır: bazı ailelerde şifreleme anahtarı hâlâ bellektedir. Aceleyle kapatmak, kurtarılabilir anahtarı yok eder. Önce RAM.

**Anti-forensics riski yüksekse** (saldırgan aktif olarak log siliyorsa, timestomp yapıyorsa) toplama penceresi daralır — hız önceliklidir.

### Adım 1 — Bellek imajını al (acquisition)

Amacımız: **bütünlüğü bozmadan, atomik bir görüntü.** Windows için pratikte kullanılan araçlar:

- **WinPv.exe (Magnet)** / **DumpIt (Comae/Magnet RAM Capture)** / **WinPmem** — hepsi ham (raw) veya AFF4 formatında dökme yapar.
- **Belkasoft Live RAM Capturer** — özellikle korumalı (anti-dumping) süreçlere karşı kernel modunda çalıştığı için tercih edilir.
- **KAPE**, canlı sistemden hem hafif triyaj artefaktlarını hem de (modülle) RAM'i tek geçişte toplayabilir — saha triyajının belkemiği.

Toplama sırasında iki kritik nokta:
1. İmajı **hedef diske değil**, harici/ağ mount'a yaz. Kendi diskine yazmak page reuse'u tetikler, delili kirletir.
2. Toplar toplamaz **hash al** (SHA-256). Bu, chain of custody'nin başlangıcıdır. `imaj.raw` + `imaj.raw.sha256` her zaman birlikte yaşar.

Ham imajın yanında **page file (pagefile.sys)** ve mümkünse **hiberfil.sys**'i de topla. Modern analizde swap'e itilmiş sayfalar RAM analizinin kör noktasıdır; pagefile onları geri getirir.

### Adım 2 — Profil / semboller ve ilk oryantasyon

**Volatility 3** ile çalışıyorsak (pratikte artık varsayılan bu), Vol2'deki manuel profil seçimi derdi büyük ölçüde bitti; Vol3 sembol tabloları (ISF) üzerinden otomatik çözer. Yine de ilk yapılan iş, imajın sağlamlığını ve OS build'ini doğrulamaktır:

```
vol.py -f imaj.raw windows.info
```

Burada baktığım: KDBG/DTB bulundu mu, build numarası mantıklı mı, imaj tamamen mı yakalanmış (kesik imaj sıkça olur, özellikle canlı toplamada). `windows.info` çöküyorsa imaj bozuktur — analize devam etmeden tekrar toplama kararı veririm.

### Adım 3 — Süreç ağacı: "normal neye benzer?" hattı

İlk asıl analiz adımı **süreç listesi ve ağacıdır.** Çünkü Windows'ta neyin normal olduğunu bilmek, anomaliyi bir bakışta yakalatır.

```
vol.py -f imaj.raw windows.pstree
vol.py -f imaj.raw windows.pslist
vol.py -f imaj.raw windows.psscan
```

`pslist` (aktif liste) ile `psscan`'i (bellek taraması, pool tag üzerinden) **kıyaslarım.** Aradaki fark bana **gizlenmiş / sonlanmış süreçleri** verir. psscan'de görünüp pslist'te olmayan bir süreç = ya unlinking ile gizlenmiş (DKOM), ya yeni ölmüş. İkisi de ilgi çekicidir.

Süreç ağacında aradığım klasik kırmızı bayraklar — **parent-child ilişkisi mantıksızsa alarm:**

- `svchost.exe`'nin parent'ı `services.exe` **değilse** → sahte svchost, injection.
- `explorer.exe` altından doğrudan `powershell.exe`, `cmd.exe`, `mshta.exe`, `wscript.exe` → kullanıcı tetiklemeli execution, muhtemelen phishing.
- `winword.exe` / `excel.exe` / `outlook.exe` → child `cmd`/`powershell`/`certutil` → makro veya exploit sonrası execution. **Bu paterni görürsem vaka "phishing → office → living-off-the-land" hipotezine gider.**
- `lsass.exe`'ın anormal bir parent'ı olması ya da **birden fazla lsass** → credential dumping veya masquerading.
- Yazımı bozuk isimler: `scvhost.exe`, `lssass.exe`, `csrsss.exe` → tipik masquerading.
- System32'de olması gereken bir binary'nin `\Users\...\AppData\Temp\` ya da `\ProgramData\`'dan çalışması → neredeyse her zaman kötücül.

`windows.pstree`'de PID/PPID, başlangıç zamanı ve komut satırını birlikte okurum. Zaman damgası kümeleri (aynı saniyede doğan bir küme süreç) genelde bir script/loader'ın imzasıdır.

### Adım 4 — Komut satırı ve ortam

```
vol.py -f imaj.raw windows.cmdline
```

Süreç adı masumdur, **argümanlar konuşur.** Burada aradıklarım:

- Base64 / gzip encoded PowerShell: `-enc`, `-EncodedCommand`, `FromBase64String`, `IEX`, `-nop -w hidden`.
- `rundll32` ile çağrılan garip export'lar, `regsvr32 /s /u /i:http...` (Squiblydoo), `mshta http...`.
- `certutil -urlcache -f http...` (indirici olarak kötüye kullanım), `bitsadmin /transfer`.
- LOLBAS ikilileri genelde argümanlarıyla ele verir. Encoded PowerShell bulursam onu **decode edip** payload'ı çıkarır, IOC'leri (URL, IP, dosya yolu) toplarım.

### Adım 5 — Ağ: dışarıya kim konuşuyor?

```
vol.py -f imaj.raw windows.netscan
```

Aradığım: dinleyen anormal portlar, **giden (ESTABLISHED)** bağlantılar ve onları sahiplenen süreç. Bir `powershell.exe` ya da `notepad.exe`'ın kurumsal olmayan bir dış IP'ye 443/4444/8080'den bağlantısı = C2 şüphesi. Süreci ağ bağlantısıyla eşleştirmek, "bu makine dışarı ne sızdırıyor" sorusunun en hızlı yanıtıdır. Bulduğum IP/portları hemen **containment listesine** (firewall block, EDR isolate) ve threat intel sorgusuna gönderirim.

### Adım 6 — Injection ve gizli kod: bellek analizinin kalbi

Diskte olmayanı burada yakalarız.

```
vol.py -f imaj.raw windows.malfind
```

`malfind`, RWX (okuma-yazma-çalıştırma) izinli, backing file'ı olmayan bellek bölgelerini bulur — process hollowing, reflective DLL injection, shellcode'un klasik izi. Çıktının başında `MZ` header (4D 5A) görmek ya da bölge başında düz shellcode (örn. `push`/`call` desenleri, `\xfc\xe8` gibi metasploit stub'ları) görmek beni doğrudan "aktif enjekte kod" sonucuna götürür.

Tamamlayıcı komutlar:

```
vol.py -f imaj.raw windows.ldrmodules   # yüklü ama üç listeden birinde eksik DLL = gizleme
vol.py -f imaj.raw windows.dlllist
vol.py -f imaj.raw windows.handles      # anormal handle'lar, named pipe'lar
vol.py -f imaj.raw windows.vadinfo
```

`ldrmodules`'de bir DLL üç PEB listesinden (Load/Init/Mem order) birinde yoksa, unlinking yapılmıştır — kasıtlı gizleme. Şüpheli bölgeyi `windows.vaddump` / `windows.dumpfiles` ile diske çıkarır, **YARA** ile tararım.

### Adım 7 — Kalıcılık (persistence) ve otomatik başlatma

Bellekte kayıt defterinin (registry) canlı hali yaşar:

```
vol.py -f imaj.raw windows.registry.hivelist
vol.py -f imaj.raw windows.registry.printkey --key "Software\Microsoft\Windows\CurrentVersion\Run"
```

Run/RunOnce, Services, Winlogon Shell/Userinit, IFEO (Image File Execution Options) hijack, ve scheduled task izleri. Persistence bulmak, olayın **kalıcı mı yoksa tek seferlik mi** olduğunu — dolayısıyla remediation'ın kapsamını — belirler.

### Adım 8 — Kimlik bilgileri ve lateral movement izi

`lsass` süreç dump'ı (`windows.dumpfiles` ile lsass'ı çıkarıp **Mimikatz/pypykatz** offline analizi) çözülmüş credential'ları verebilir. Saldırganın hangi hesapları ele geçirmiş olabileceğini görmek, **blast radius'u** (etki alanını) belirlemek için kritiktir. Bellekte cleartext parola ya da tazelenmiş TGT bulmak, "hangi hesapların şifresini acil sıfırlamalıyım" kararını doğrudan besler.

### Adım 9 — YARA ile hedefli tarama

```
vol.py -f imaj.raw windows.vadyarascan --yara-file kurallar.yar
```

Bilinen aile imzaları, C2 stringleri, packer desenleri için tüm süreç belleğini tararım. `malfind` "şüpheli bir şey var" derken, YARA "bu Cobalt Strike beacon'ı" diyebilir.

### Adım 10 — Korelasyon ve zaman çizelgesi

Bellek bulgularını tek başına bırakmam. **Timesketch** üzerinde, RAM'den çıkan süreç başlangıç zamanlarını, disk artefaktlarıyla birleştiririm:

- **KAPE** ile toplanan triyaj paketi → **Eric Zimmerman araçları** ile parse: `MFTECmd` (MFT/UsnJrnl), `PECmd` (Prefetch), `AppCompatCacheParser` + `AmcacheParser` (execution kanıtı), `EvtxECmd` (event log'lar), `RECmd` (registry), `SBECmd` (shellbags).
- Bu CSV'leri Timesketch'e yükleyip **süper zaman çizelgesi (super timeline)** kurarım (Plaso/log2timeline de aynı işi yapar).

Karar mantığı: RAM'de gördüğüm C2 bağlantısı **saat X'te** aktifse, aynı dakikada Prefetch'te malware'in çalıştığını, Amcache'te ilk yüklenme zamanını, event log'da 4688 (process creation) ve 4624 (logon) kayıtlarını arar; birbirini teyit eden bu izler **initial access → execution → C2** zincirini tarihiyle kurar. **Autopsy** ise disk imajı üzerinde deleted file recovery, web history ve dosya seviyesinde derin inceleme için ikinci hattır.

Not: **Velociraptor** ise bu iş akışının filo (fleet) ölçekli halidir. Tek makinede öğrendiğim IOC'leri (dosya hash'i, mutex, C2 IP, servis adı) Velociraptor VQL hunt'ıyla **tüm ortamda** aratırım — "başka hangi makinelerde aynı iz var?" sorusunun ölçeklenebilir cevabı budur. Velociraptor ayrıca uzaktan canlı RAM analizi (yerleşik Volatility benzeri yetenekler) da sunar.

## 3. Kritik dikkat noktaları

**Order of volatility (uçuculuk sırası).** Kural sırası: CPU register/cache → RAM → ağ durumu/çalışan süreçler → disk → uzak loglar → arşiv. Pratik sonuç: RAM'i **her şeyden önce** dondur. Makinede "acaba" diye komut çalıştırmak bile bellek durumunu değiştirir; her müdahale ayak izi bırakır. Bu yüzden toplama aracını ideal olarak minimum ayak iziyle, harici mount'tan çalıştırırım.

**Delil bütünlüğü (integrity).** İmajı aldığın **anda** hash'le; her transferden sonra tekrar doğrula. Hash zinciri kırılırsa delil mahkemede (ve iç soruşturmada) çürür. İmaj üzerinde **asla** orijinali işleme; her zaman kopya üzerinde çalış, orijinali salt-okunur sakla.

**Chain of custody (delil zinciri).** Kim, ne zaman, neyi, nereden, hangi araçla topladı — hepsi belgelenir. Toplama aracının adı ve versiyonu, tarih-saat (ve zaman dilimi/UTC), toplayan kişi, saklama ortamı. Bu, delilin değil sürecin savunmasıdır. Bir tarih belirsizliği bile tüm timeline'ı sorgulatır — **her zaman UTC'de çalış** ve makinenin saat sapmasını (clock skew) not et.

**Anti-forensics'e karşı.** Saldırgan da bunları bilir:
- **Timestomp** (`$STANDARD_INFORMATION` zamanlarını geriye alma) → ben `$FILE_NAME` (MFT'deki ikinci zaman kümesi) ile SI zamanlarını kıyaslarım; uyuşmazlık manipülasyon işaretidir. Ayrıca UsnJrnl ve prefetch, sahte SI zamanına aldırmadan gerçek execution zamanını verir.
- **Log temizleme** → Event log silinmişse (Event ID 1102), USN Journal, SRUM, ShimCache/Amcache silinen execution'ları hatırlar; RAM'deki kalıntı yapılar da öyle.
- **Bellekte gizleme (DKOM/unlinking)** → `pslist` vs `psscan`, `ldrmodules` tam da bunun içindir.
- **Anti-dumping korumalı süreçler** → kernel-mod dumper (Belkasoft, WinPmem) gerekir.
- **Şifreli disk (BitLocker)** ama açık oturum → RAM'de **volume master key** bulunabilir; bu yüzden yine önce RAM.

## 4. Gerçek dünya senaryosu

**Alarm:** SIEM, bir muhasebe kullanıcısının iş istasyonundan (WKS-FIN-07) saat 14:12'de bilinmeyen bir dış IP'ye tekrarlayan 443 çıkışını korele ediyor. EDR ise `winword.exe`'ın bir alt süreç doğurduğuna dair düşük öncelikli bir uyarı vermiş.

**Karar 1 — İzole et, kapatma.** Aktif C2 şüphesi var. EDR network containment'ı uygularım (RAM korunur), sonra KAPE + WinPmem ile RAM + triyaj paketini harici diske toplarım. SHA-256 alınır, custody formu doldurulur, UTC not edilir.

**Analiz:**

- `windows.pstree`: `winword.exe (PID 4820)` → `cmd.exe (5104)` → `powershell.exe (5160)`. **Klasik phishing→office→execution zinciri.** PowerShell başlangıcı 14:09.
- `windows.cmdline`: PowerShell argümanı `-nop -w hidden -enc SQBFAFgA...`. Decode ettiğimde: bir `.dat` dosyasını `%ProgramData%`'ya indirip `rundll32` ile çağıran bir downloader. → **İkinci aşama payload** hipotezi.
- `windows.netscan`: PID 5160'a bağlı, 185.x.x.x:443 **ESTABLISHED** — SIEM'in gördüğü IP ile aynı. → C2 doğrulandı, süreç kimliği belli.
- `windows.malfind`: `rundll32.exe (5320)` içinde RWX bölge, başında `MZ` header. → **Injection / hollowing.**
- `windows.vadyarascan`: aynı bölge Cobalt Strike beacon YARA kuralına takılıyor. → **Aile tanımlandı.**
- `windows.registry.printkey` (Run anahtarı): `%ProgramData%\svhost.dat` işaret eden bir RunOnce değeri. → **Persistence var; olay kalıcı.**
- `lsass` dump → pypykatz: muhasebe kullanıcısının NTLM hash'i ve bir **domain admin** oturumunun tazelenmiş bilgisi. → **Blast radius büyük; lateral movement riski.**

**Korelasyon (Timesketch):** Prefetch (`PECmd`) `powershell.exe` execution'ını 14:09'da; Amcache `svhost.dat`'ın ilk kaydını 14:10'da; Event log 4688 zinciri office→cmd→powershell'i; Outlook'un o sabah 14:06'da bir ek açtığını (MFT + shellbag) gösteriyor. → **Initial access: 14:06 phishing eki.**

**Varılan sonuç:** Phishing eki (14:06) → makro/exploit ile PowerShell downloader (14:09) → Cobalt Strike beacon rundll32'ye enjekte (14:11) → C2 (14:12) → credential dumping (domain admin ele geçirilmiş). Persistence RunOnce'ta.

**Aksiyon:** (1) C2 IP'sini tüm ortamda **Velociraptor VQL hunt** ile ara — WKS-FIN-07 dışında 2 makine daha aynı beacon'ı barındırıyor. (2) Ele geçen domain admin ve kullanıcı parolalarını **acil sıfırla**, KRBTGT dahil değerlendir. (3) `svhost.dat` hash'i ve mutex'i IOC olarak yay. (4) Etkilenen üç makineyi izole et, yeniden görüntüle. Bellek analizi burada saatler yerine dakikalar içinde **kim, ne, ne kadar** sorusunu yanıtladı.

## 5. Yaygın tuzaklar ve pro yargısı

**Tuzak 1 — Canlı makinede körlemesine komut çalıştırmak.** Acemi, "bakayım ne var" diye şüpheli makinede `netstat`, `tasklist`, hatta antivirüs taraması çalıştırır. Her komut RAM'i değiştirir, page reuse'u hızlandırır, hatta tripwire tetikleyip saldırganı uyarır. Pro önce dondurur, sonra bakar.

**Tuzak 2 — Gücü kesmek / "temiz olsun diye" reboot.** En pahalı hata. RAM'i, açık C2'yi, çözülmüş credential'ı, ransomware anahtarını yok eder. "Kapatıp açalım" IR'de neredeyse her zaman yanlıştır.

**Tuzak 3 — İmajı hedef diske yazmak.** Delili topladığın diske yazmak, incelediğin veriyi ezer. Her zaman harici/ağ hedefi.

**Tuzak 4 — Sadece `pslist`'e güvenmek.** Aktif liste manipüle edilebilir. `psscan` ile kıyaslamayan analist gizlenmiş süreci kaçırır. Tek kaynağa güvenme; **çapraz doğrula.**

**Tuzak 5 — Süreç adına bakıp isme kanmak.** `svchost.exe` görünce "normal" demek. Pro parent'a, yola, komut satırına ve imza durumuna bakar. İsim ucuzdur; bağlam pahalı.

**Tuzak 6 — Zaman damgalarına sorgusuz güvenmek.** SI zamanları timestomp'lanmış olabilir. Pro `$FILE_NAME` ile kıyaslar, UsnJrnl/prefetch ile teyit eder. Ayrıca **UTC vs yerel saat** karmaşası birçok timeline'ı bozar — clock skew'i ölç ve not et.

**Tuzak 7 — Pagefile'ı ihmal etmek.** Sadece RAM alıp swap'e itilmiş sayfaları görmemek, tabloyu yarım bırakır. Kritik payload tam da swap'te olabilir.

**Tuzak 8 — Bellek bulgusunu tek başına delil saymak.** RAM "o an"dır. Persistence, initial access ve süreklilik disk artefaktlarıyla kurulur. Korelasyon yapmayan analist "ne olduğunu" bilir ama "nasıl girdiğini ve tekrar edip etmeyeceğini" bilemez — yani remediation eksik kalır.

**Tuzak 9 — Kesik/bozuk imajla devam etmek.** `windows.info` çökerken ısrar etmek saatleri boşa harcatır. Önce imaj sağlığını doğrula.

**Tuzak 10 — IOC'yi tek makineye hapsetmek.** Bir makinede bulduğun beacon büyük ihtimalle yalnız değildir. Filo çapında (Velociraptor/EDR) aramayan analist, kapsamayı yarım yapar ve saldırgan başka makineden geri döner.

**Pro yargısının özü:** Bellek forensics bir "araç yarışı" değil, bir **hipotez-doğrulama** disiplinidir. Süreç ağacı hipotez kurar, ağ ve injection onu güçlendirir, disk timeline'ı tarihiyle mühürler, filo hunt'ı kapsamı belirler. Hız (uçuculuk yüzünden) ve titizlik (delil bütünlüğü yüzünden) aynı anda gerekir — ikisini dengeleyebilen analist iyi analisttir.
