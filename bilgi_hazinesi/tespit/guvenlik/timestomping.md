# Timestomping — Tespiti

## 1. Özet: saldırı + naif tespit

Timestomping, saldırganın bir dosyanın zaman damgalarını (MACE: Modified, Accessed, Changed, Birth/Created) manipüle ederek geriye dönük analizi bozma tekniğidir. MITRE ATT&CK'te `T1070.006` olarak geçer, "Indicator Removal" ailesinin altındadır. Amaç basittir: attacker koyduğu bir web shell'i, backdoor'u ya da persistence aracını, bulunduğu klasördeki meşru dosyalarla aynı yaşta göstererek DFIR analistinin timeline'ında "gürültüye" gömmek. Bir `C:\Windows\System32` içine bırakılan implantın oluşturma tarihi 2009 (OS kurulum tarihi) gösterildiğinde, "son 30 günde oluşan dosyalar" sorgusu onu kaçırır. Klasik metasploit `timestomp` komutu, PowerShell'de `(Get-Item x).CreationTime = ...` ataması, ya da `[IO.File]::SetCreationTime()` çağrısı bu işi yapar. Linux tarafında `touch -r` ile referans dosyadan zaman kopyalama aynı mantıktır.

Naif tespit iki yerden gelir. Birincisi, PowerShell Script Block Logging (Event ID 4104) açıksa, `ScriptBlockText` içinde `.CreationTime =`, `.LastWriteTime =`, `.LastAccessTime =`, `[IO.File]::SetCreationTime`, `[IO.File]::SetLastAccessTime`, `[IO.File]::SetLastWriteTime` gibi string'leri aramak. Bu, Sigma'daki `Powershell Timestomp` (id `c6438007-e081-42ce-9483-b067fbef33c3`) kuralının tam olarak yaptığı şey. İkincisi, dosya oluşturma tarihinin anormal derecede eskiye — örneğin 2020 öncesine — çekilmiş olmasını yakalamak (`File Creation Date Changed to Another Year`, id `558eebe5-f2ba-4104-b339-36f7902bcc1a`). Bir dosyanın Birth time'ı 2009 ama NTFS'teki $MFT kaydı diyor ki bu dosya geçen hafta oluştu — burada bariz bir çelişki var.

Bu iki yaklaşım da doğru, ikisi de korpusun bilgisi. Ama ikisi de sahada tek başına neredeyse işe yaramaz. Asıl mühendislik, bunun *neden* yetmediğini ve onu neyle sağlamlaştırdığını bilmekte.

## 2. Naif tespit neden yetmez

**Script Block tabanlı kural sadece PowerShell'i görür.** Timestomping PowerShell'e özgü bir şey değil, bir Windows API davranışı. `SetFileTime()` Win32 API'sini çağıran her şey — C# ile derlenmiş bir implant, Go ile yazılmış bir dropper, Cobalt Strike'ın `timestomp` beacon komutu, Nim/Rust bir loader — hiçbir PowerShell script bloğu üretmeden dosyanın zamanını değiştirir. Sigma `c6438007` kuralı bu vakaların hiçbirini görmez. Yani kural, en amatör saldırganı (ekrandan kopyaladığı PowerShell one-liner'ı) yakalar; gerçek operatörü yakalamaz. Detection engineering'de buna "yakaladığın şey tehdit modelinin en alt kuşağı" deriz — kötü değil ama üstüne güven inşa edilemez.

Dahası, Script Block Logging pek çok ortamda ya kapalıdır ya da sadece "suspicious" bloklar için ScriptBlockLogging aktiftir (Warning-level otomatik loglama). `.LastWriteTime =` gibi masum görünen bir ifade otomatik "suspicious" sınıfına girmeyebilir, yani full logging kapalıysa 4104 hiç düşmez. Kuralın `definition` alanı boşuna "Requirements: Script Block Logging must be enabled" demiyor — bu bir uyarı değil, itiraf: kural varsayılan bir Windows'ta sessizdir.

**"2020 öncesi tarih" kuralı false positive selinde boğulur.** Bu kural gerçek ortamda alarmı en çok üreten kurallardan biridir çünkü meşru dünyada dosya oluşturma/değiştirme tarihini eskiye çeken *çok* şey var. Bir ZIP/TAR arşivini açtığınızda içerdeki dosyalar arşivdeki orijinal timestamp'i taşır — bir kütüphaneyi 2016'da paketlenmiş bir tarball'dan extract ettiyseniz, o dosyalar 2016 tarihiyle diske düşer. `robocopy /COPYALL`, `xcopy`, yedekten geri yükleme, Git checkout, MSI installer'ların taşıdığı dosyalar, container image katmanlarından çıkan dosyalar... hepsi geçmiş tarihli timestamp üretir. Kuralın kendi açıklaması da bunu kabul ediyor: "many processes legitimately change the creation time of a file; it does not necessarily indicate malicious activity" ve "first baseline normal behavior... then tune". Yani kural üreticisi bile "bunu ham haliyle koyarsan SOC'u boğar" diyor. Tune edilmemiş halde bir haftada binlerce olay üretir ve analist onu mute eder — mute edilen kural, olmayan kuraldır.

**Kör nokta: hangi timestamp'i izliyorsun?** NTFS'te her dosyanın iki ayrı yerde zamanı vardır: `$STANDARD_INFORMATION` ($SI) attribute'u ve `$FILE_NAME` ($FN) attribute'u. Windows API'leri, Explorer, `dir`, çoğu EDR ve neredeyse tüm timestomp araçları *sadece* $SI'yı değiştirir. Çünkü $FN attribute'unu değiştirmek user-mode'dan normal API ile mümkün değildir — kernel, $FN'i dosya rename/move sırasında günceller. İşte asıl tespit fırsatı buradadır ve naif kuralların ikisi de buna bakmaz.

## 3. Korelasyon zinciri (asıl değer)

Timestomping tek başına zayıf, gürültülü bir sinyaldir. Onu yüksek güvenli tespite çevirmenin yolu, onu *bir olay değil bir düğüm* olarak görüp öncesine ve sonrasına bağlamaktır. Sahada işe yarayan zincirler:

**Zincir 1 — $SI vs $FN tutarsızlığı + yürütme.** Gerçek altın sinyal: MFT üzerinde `$SI.CreationTime < $FN.CreationTime` (özellikle $SI yıllarca geriye çekilmiş ama $FN dünkü tarihte). Bunu tek başına bulmak bile güçlüdür ama tam güven şu birleşimden gelir:
- (A) MFT taramasında bir dosyada $SI Birth time = 2009, $FN Birth time = bu hafta — yani $SI manipüle edilmiş.
- (B) Aynı dosya, oluşturulmasından sonraki kısa pencerede yürütülmüş (Sysmon Event ID 1 process create, ya da 4688) — özellikle `C:\Windows\`, `C:\ProgramData\`, `AppData\Local\Temp` gibi yerlerde.
- (C) Dosya imzasız ya da bilinmeyen bir publisher, ve parent process anormal (`w3wp.exe` bir `.aspx` doğuruyor, `services.exe` beklenmedik bir binary başlatıyor).

A+B+C bir araya geldiğinde false positive olasılığı çöker. Yedek yazılımı $SI'yı eskiye çekebilir ama o dosyayı hemen yürütmez ve imzasız değildir.

**Zincir 2 — Sub-second precision anomalisi + FileCreate.** Meşru Windows dosyalarının $SI timestamp'lerinde nanosecond hassasiyetli, "gürültülü" alt-saniye bileşenleri vardır (ör. `.4517823`). Kaba timestomp araçları timestamp'i saniyeye ya da tam sıfıra yuvarlar (`.0000000`). Sysmon Event ID 2 (`FileCreateTime` — "A process changed a file creation time") bu olayı doğrudan loglar ve hem eski hem yeni zamanı verir. Korelasyon: **Sysmon EID 2 (creation time değişti) + yeni timestamp'in alt-saniyesi tam sıfır + değiştiren process `powershell.exe`/`cmd.exe`/imzasız binary + hedef dosya bir executable/script.** Sysmon EID 2, timestomping için en doğrudan telemetridir ama çoğu Sysmon config'inde gürültü diye ya kapalıdır ya filtrelidir — bu 6. bölümün konusu.

**Zincir 3 — Drop → stomp → persist, kısa zaman penceresinde.** Gerçek bir ihlalde timestomping izole olmaz; bir öldürme zincirinin ortasındadır. Yüksek güvenli desen, üç ayrı telemetri kaynağının kısa pencerede (dakikalar) hizalanmasıdır:
- `w3wp.exe` ya da bir Office process'i yeni bir dosya yazıyor (Sysmon EID 11, FileCreate) — örn. yeni bir `.aspx` web shell.
- Saniyeler/dakikalar içinde aynı dosyada FileCreateTime değişimi (Sysmon EID 2) — attacker onu komşu meşru dosyalarla yaşıtlıyor.
- Ardından persistence ya da execution: yeni bir Run key (Sysmon EID 13), yeni service (System 7045), scheduled task, ya da o dosyanın yürütülmesi.

Bu üçlü — "yaz, yaşını sakla, kalıcılaştır" — tek bir hikaye anlatır ve hiçbir yedek/deployment aracı bu tam sırayı üretmez. SIEM'de bunu bir sequence/correlation kuralı olarak (aynı `TargetFilename` üzerinden join, `< 10 dakika` pencere) yazmak, tek başına 4104 aramaktan kat kat üstündür.

**Zincir 4 — Timeline çelişkisi ($MFT vs USN Journal vs $LogFile).** Attacker $SI'yı geri çekse bile başka artefaktları unutur. NTFS USN Change Journal (`$Extend\$UsnJrnl`) dosya oluşturma/yazma olaylarını *gerçek* zamanla, kendi sıralı USN numarasıyla kaydeder — ve bunu timestomp etmek pratik değildir. Korelasyon: MFT'de dosya 2009 diyor ama USN Journal'da o dosyanın `FILE_CREATE` kaydı geçen haftaya, yüksek bir USN numarasına düşüyor. İki kaynak çelişiyorsa, çelişkinin kendisi tespittir. Aynı şekilde Prefetch, `$LogFile`, SRUM, Amcache/Shimcache (ilk görülme zamanı) — bunların hepsi $SI'dan bağımsız "gerçek" zaman verir. Kıdemli DFIR mantığı: **tek bir timestamp'e asla güvenme; en az iki bağımsız zaman kaynağını çapraz doğrula.**

## 4. False positive gerçeği ve triage yargısı

Timestomping alarmları — özellikle Sysmon EID 2 ve "eski tarih" kuralı — meşru dünyada bolca üretilir. Kıdemli analistin işi, gerçek/gürültü ayrımını hızlı yapmaktır. Sahada bu alarmı meşru üreten başlıca kaynaklar:

- **Yedekleme/geri yükleme yazılımları** (Veeam, Commvault, Windows Backup): restore edilen dosyalar orijinal timestamp'lerini taşır, bu da FileCreateTime değişimi olarak görünür. Genelde process imzalı ve bilinen bir yol.
- **Deployment/config yönetimi** (SCCM/MECM, Intune, Ansible, Chocolatey): paket dağıtırken dosya zamanlarını kaynaktan kopyalar. `ccmexec.exe`, `TiWorker.exe` gibi imzalı parent'lar.
- **Arşiv çıkarma** (7-Zip, WinRAR, `Expand-Archive`, tar): içerideki orijinal tarihleri korur.
- **Geliştirici araçları**: `git checkout`/`clone` (dosya mtime'ı commit'e göre değil ama build araçları oynatır), MSBuild, `robocopy /COPYALL`, Docker/container katman çıkarma.
- **Yasal yazılım kurulumları**: MSI installer'lar CAB içindeki orijinal build tarihlerini korur — bu yüzden `Program Files` altındaki EXE'ler kurulum gününden eski görünür (tamamen normal).

Kıdemli triage yargısı şu sıraya oturur:

**1. İmza ve reputasyon önce.** Değiştiren process imzalı ve bilinen bir yönetim aracıysa (SCCM, Veeam, MsMpEng) ve hedef dosya da imzalıysa — bu neredeyse kesin gürültü. İmzasız bir process, imzasız bir hedef dosyanın zamanını oynatıyorsa — kırmızı bayrak.

**2. Yer ve dosya türü.** `C:\Users\...\Downloads` altında bir belgenin zamanının değişmesi ile `C:\Windows\System32` ya da bir IIS web root'unda bir `.aspx`/`.exe`/`.dll`'in zamanının değişmesi aynı şey değildir. Executable + hassas dizin = önceliklendir. Kullanıcı doküman dizininde ofis dosyası = büyük ihtimalle senkronizasyon/arşiv.

**3. Hedeflenen zaman değeri.** Yeni timestamp komşu dosyalarla *tam* eşleşiyorsa (aynı saniye, aynı klasördeki 5 dosyayla birebir) bu meşru kopyalamadan çok kasıtlı kamuflaj kokar. Alt-saniye sıfırlanmışsa şüphe artar.

**4. Çoklu alarmda önce zincire bak, tek olaya değil.** Eğer aynı host'ta kısa pencerede FileCreate (yeni dosya) → FileCreateTime (zaman değişti) → yeni persistence görüyorsan, timestomp alarmı artık bağımsız bir olay değil, doğrulanmış bir hikayenin parçası — en yüksek önceliğe çıkar. Kıdemli analist ilk baktığı şey "bu alarm yalnız mı geldi yoksa bir dizinin ortasında mı?" sorusudur. Yalnız gelen timestomp alarmı %95 gürültü; bir öldürme zincirine gömülü olan %95 gerçek.

Pratik bir baseline hilesi: ortamındaki FileCreateTime değiştiren process'lerin listesini bir hafta topla, imzalı yönetim araçlarını (SCCM, Veeam, antivirüs, Intune) bir allowlist'e koy, kalanı incele. Kalan liste genelde küçüktür ve orada gerçek anomaliler yaşar.

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Olgun bir saldırgan yukarıdaki tespitleri bilir ve etrafından dolaşmaya çalışır. Kural dokümanlarında yazmayan kaçınma yolları ve her birine ikinci derece tespit:

**Kaçınma 1: PowerShell yerine derlenmiş araç.** Attacker `SetFileTime()` API'sini doğrudan çağıran bir C#/Go/Rust binary kullanır — 4104 hiç düşmez.
→ *Karşı-tespit:* Script Block Logging'e güvenmeyi bırak; Sysmon EID 2 (FileCreateTime) API seviyesindedir, hangi process çağırırsa çağırsın loglanır. Ayrıca MFT'de $SI/$FN çelişkisi araç ne olursa olsun kalır. Tespiti PowerShell string'inden dosya sistemi artefaktına taşı.

**Kaçınma 2: $FN'i de senkronlamak (double timestomping).** Sofistike attacker $SI/$FN çelişkisini bildiği için $FN'i de eşitlemeye çalışır. Bunu yapmanın kirli bir yolu vardır: dosyayı, hedef $SI zamanına sahip başka bir dosyanın olduğu bir yere *taşımak/rename etmek* — çünkü $FN move sırasında güncellenir ve o an $SI'dan kopyalanabilir. Bazı araçlar (SetMace gibi) doğrudan kernel/raw disk üzerinden $FN'e yazmayı dener.
→ *Karşı-tespit:* Artık MFT tek başına yetmez, USN Journal'a geç. USN Change Journal her rename/create'i kendi sıralı numarasıyla ve gerçek zamanla tutar; $FN'i kandırsan bile USN kaydındaki `FILE_CREATE`/`RENAME` olayı gerçek zamanda kalır. Ayrıca $MFT giriş numarası (record number) sıralıdır — dosya "2009'da" oluştu diyorsa ama MFT record numarası son eklenen dosyalarla aynı bölgedeyse, sıralama çelişir. SetMace tarzı raw disk yazımları ise $LogFile'da anomali bırakır.

**Kaçınma 3: Alt-saniye hassasiyetini taklit etmek.** Attacker `.0000000` yuvarlaması ile yakalandığını öğrenir ve gerçekçi görünen nanosecond'lar üretir.
→ *Karşı-tespit:* Alt-saniye tek başına zaten zayıf bir sinyaldi; bunu bir tuning ipucu olarak kullan, ana kanıt olarak değil. Ağırlığı $SI/$FN çelişkisine ve çapraz-artefakt zaman doğrulamasına (USN, Prefetch, Amcache) ver. Bu artefaktları hep birden tutarlı biçimde kandırmak pratikte çok zordur — biri her zaman sızar.

**Kaçınma 4: Sysmon'u kör etmek.** Attacker EID 2'nin izlediğini bilir; Sysmon'u durdurmayı, config'ini değiştirmeyi ya da event log'u temizlemeyi dener.
→ *Karşı-tespit:* Sysmon servis durması/config değişikliği kendi başına yüksek güvenli bir alarmdır (Sysmon EID 4/16, ya da service state değişimi). Windows Security event log temizleme Event ID 1102, System log temizleme 104 — bunlar timestomping'den çok daha gürültüsüz ve nadir olaylardır. Attacker anti-forensic yaparken bıraktığı meta-iz, orijinal izden daha yakalanabilirdir. Telemetriyi host'ta bırakma; log forwarding ile SIEM'e anında akıt ki lokal temizlik geç kalsın.

**Kaçınma 5: $SI'yı hiç dokunmadan sadece komşuya benzemek.** Attacker dosyayı zaten eski görünen bir dizine (ör. `System32`) koyar ve $SI'yı OS kurulum tarihine çeker — böylece "2020 öncesi" kuralına takılmaz çünkü tarih makul (2009 OS kurulumu, o makine için normal).
→ *Karşı-tespit:* "Sabit eşikli eski tarih" mantığından çık, "bu dosyanın $SI'sı komşularıyla uyuşuyor ama USN/Amcache diyor ki dün geldi" çelişkisine bak. Yani mutlak tarih anomalisi değil, *bağıl* artefakt çelişkisi. İyi tespit eşiğe değil tutarsızlığa dayanır.

**Kaçınma 6: Diske hiç düşürmemek (fileless).** En olgun operatör timestomping problemini tümüyle atlar: implantı diske yazmaz, bellekte tutar (reflective DLL injection, `.NET Assembly.Load`, process hollowing). Diskte dosya yoksa timestamp de yoktur, yani timestomping tespitin tamamı devre dışı kalır.
→ *Karşı-tespit:* Bu artık bir timestomping tespiti değil, bir kapsam sınırıdır ve bunu bilmek kıdemli olmanın parçasıdır. Timestomping tespitin sana "diske dosya yazan ama izini gizleyen" saldırganı verir; fileless saldırganı vermez ve vermesini beklemek yanlıştır. Onu farklı katman (memory scanning, EDR behavioral, AMSI, `Sysmon EID 8` CreateRemoteThread, `EID 10` ProcessAccess) yakalar. Tespit mühendisinin en tehlikeli hatası, bir kontrolün kapsamını olduğundan geniş sanmaktır — "timestomping kuralım var, dosya gizleme bende çözüldü" demek, fileless ve $FN-double-stomp vakalarını görmezden gelmektir.

Buradaki genel ders: her timestamp tabanlı kaçınma, saldırganın *dokunmadığı* bir başka zaman kaynağı bırakır. Kedi-fare oyunu tek artefaktta kaybedilir, çoklu artefakt korelasyonunda kazanılır. Ve her tespitin bir kapsam duvarı vardır — o duvarın nerede olduğunu bilmek, kuralı yazmak kadar değerlidir.

## 6. SIEM / saha gerçeği

**Varsayılan loglanmayan şeyler — en büyük tuzak.** Timestomping tespitinin can damarı olan telemetri, kutudan çıktığı gibi bir Windows'ta *yoktur*:
- **Sysmon EID 2 (FileCreateTime)** en doğrudan sinyaldir ama pek çok Sysmon config'i (SwiftOnSecurity dahil) onu gürültü diye ya kapatır ya da dar filtreler. Tespit istiyorsan config'inde `FileCreateTime` bloğunun açık ve executable/script uzantıları ile hassas dizinleri kapsıyor olması şart. Bunu doğrulamadan "kuralım var" deme.
- **PowerShell Script Block Logging (4104)** GPO ile açık olmalı (`Administrative Templates > Windows PowerShell > Turn on PowerShell Script Block Logging`). Kapalıysa Sigma `c6438007` sessizdir.
- **Process creation with command line (4688)** için ayrıca "Include command line in process creation events" audit policy'si gerekir; yoksa command line boş gelir ve korelasyon çöker.
- **MFT/$SI vs $FN ve USN Journal** neredeyse hiçbir SIEM'de canlı stream olarak *yoktur*. Bunlar DFIR triage sırasında (KAPE, MFTECmd, Velociraptor, EDR raw file collection) toplanır. Yani $SI/$FN çelişkisi tespiti bir SIEM detection değil, bir hunt/triage prosedürüdür — bunu karıştırma. Velociraptor gibi araçlarla MFT'yi periyodik toplayıp $SI<$FN anomalisini flag'lemek olgun bir yaklaşımdır.

**Field mapping tuzakları.** Sigma kuralı `ScriptBlockText` alanına bakar ama bu alan SIEM'e göre farklı normalize edilir:
- **Splunk** (Windows TA ile): `ScriptBlockText` genelde aynı isimle gelir ama 4104 event'lerinin `EventCode=4104` ve doğru sourcetype (`WinEventLog:Microsoft-Windows-PowerShell/Operational`) ile ingest edildiğini doğrula. Uzun script blokları birden çok event'e bölünür (`MessageNumber`/`MessageTotal`) — tek event'te arama yaparsan parçalı saldırıyı kaçırırsın.
- **Microsoft Sentinel**: PowerShell operational log'u `Event` tablosuna ya da AMA ile özel tabloya düşer; alan `EventData` içinde XML olarak gömülü gelebilir, `ScriptBlockText` düz kolon değil — parse etmen gerekir. Sysmon EID 2 ise `Event`/`SysmonEvent` içinde `RuleName`, `PreviousCreationUtcTime` ve `CreationUtcTime` alanlarıyla gelir; asıl güç `PreviousCreationUtcTime != CreationUtcTime` farkındadır.
- **Elastic**: ECS normalizasyonu ile Sysmon EID 2 `file.created` ve `event.code: "2"` altına maplenir; `winlog.event_data.PreviousCreationUtcTime` ham alandır. PowerShell 4104 `powershell.file.script_block_text` altına gider — Sigma'nın `ScriptBlockText` alanı bire bir aynı isimde değildir, backend çevirisi (sigmac/pySigma Elastic backend) bunu halleder ama elle yazıyorsan doğru ECS alanını kullan.

**Sysmon EID 2'nin gizli değeri: PreviousCreationUtcTime.** Bu alan çoğu tespit yazarının kaçırdığı hazinedir. EID 2 sadece "zaman değişti" demez, *eski değeri de* verir. Yüksek güvenli kural: `CreationUtcTime` (yeni) `PreviousCreationUtcTime`'dan (eski) *daha eski* ise — yani zaman geriye çekilmişse. Meşru dosya işlemleri zamanı genelde ileri taşır ya da korur; kasıtlı geriye çekme timestomping'in imzasıdır. Bu tek koşul, ham EID 2 gürültüsünü ciddi biçimde süzer.

**Tuning gerçeği.** Ham EID 2 kuralı devreye alınca ilk hafta yüzlerce-binlerce olay gelir. Sürdürülebilir hale getirmek için: (1) değiştiren process imzalı yönetim araçlarını (SCCM, Veeam, antivirüs, Intune, `TiWorker.exe`) allowlist'le, (2) hedefi executable/script/hassas dizinle sınırla, (3) "zaman geriye çekildi" koşulunu ekle, (4) mümkünse imzasız-process ve düşük-reputasyon koşulunu bağla. Bu dört filtreyle olay hacmi genelde günde tek haneli, incelenebilir bir sayıya iner. Tune edilmemiş kural mute edilir, mute edilen kural savunma değil tiyatrodur.

**Zaman dilimi (timezone) tuzağı.** Timestomping analizinin sessiz katilidir. NTFS $SI/$FN zamanları UTC tutulur ama Explorer, `dir` ve pek çok araç lokal saatte gösterir. USN Journal UTC, Prefetch lokal, event log'lar SIEM'e göre çevrilir. Çapraz-artefakt korelasyonu yaparken iki kaynağı farklı timezone'da karşılaştırırsan yapay bir çelişki üretir ya da gerçek bir çelişkiyi maskelersin — 3 saatlik bir fark, "geriye çekilmiş" gibi görünür ama aslında sadece UTC vs UTC+3 kaymasıdır. Kural: her zaman UTC'ye normalize et ve hangi artefaktın hangi timezone'da olduğunu bil. Sysmon UTC verir (`CreationUtcTime` — adında zaten UTC var), bunu lokal timeline ile karşılaştırırken çevir.

**Kapanış yargısı.** Timestomping tespitinde en sık yapılan hata, onu tek bir kuralla ("PowerShell string ara" ya da "eski tarih ara") çözülmüş saymaktır. Gerçekte bu, katmanlı bir problemdir: canlı telemetri (Sysmon EID 2 + PreviousCreationUtcTime farkı) SIEM'de gürültüyü baseline ile süzerek erken uyarı verir; asıl kanıt ise triage'da çoklu artefaktın (MFT $SI/$FN, USN Journal, Amcache, Prefetch) çapraz doğrulamasından çıkar. Saldırgan tek artefaktı kandırabilir, hepsini birden asla. Kıdemli detection engineer'ın işi, tek kuralı değil bu çapraz doğrulama refleksini kurmaktır.
