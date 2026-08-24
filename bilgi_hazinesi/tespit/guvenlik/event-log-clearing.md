# Event Log Temizleme — Tespiti

> Saha notu: Bu metin, "1102 event'ine bak" seviyesinin altını kazır. Log temizlemenin neden nadiren *tek başına* görüldüğünü, gerçek ihlallerde hangi olay zincirinin ortasında durduğunu ve olgun ortamlarda tespitin tam olarak nerede sessizce çöktüğünü anlatır. MITRE karşılığı: **T1070.001 (Clear Windows Event Logs)**, üst teknik T1070 (Indicator Removal on Host). Anti-forensic ailesinin en gürültülü üyesidir — ve tam da bu yüzden sofistike saldırgan onu genelde *yapmaz*.

---

## 1. Özet: saldırı + naif tespit

Windows olay günlükleri (Security, System, Application, ve Operational kanalları) bir ihlalin en zengin adli izidir. Saldırgan, lateral hareket, kimlik hırsızlığı, persistans ve exfil bıraktıktan sonra bu izi yok etmek ister. En kaba yöntem tüm bir günlüğü topluca silmektir. Bunun için elde hazır meşru araçlar vardır: `wevtutil cl Security`, PowerShell'de `Clear-EventLog -LogName Security` veya `Wevtutil.exe`, WMI/CIM üzerinden `Get-WmiObject Win32_NTEventlogFile ... .ClearEventLog()`, ve doğrudan `EventLog` servisini durdurup EVTX dosyasını sıfırlama/silme.

Bunun güzel yanı şu: Windows'un kendisi bu eylemi loglar. Bir güvenlik günlüğü topluca temizlendiğinde, temizleme *öncesi* son kayıt olarak **Security kanalına EventID 1102** ("The audit log was cleared") yazılır — içinde temizlemeyi yapan `SubjectUserName`, `SubjectDomainName` ve `SubjectLogonId` alanları bulunur. Benzer şekilde **System kanalına EventID 104** ("The System log file was cleared") düşer ve `wevtutil` ile temizlenen *herhangi bir* klasik günlük için tetiklenir; içinde temizlenen kanalın adı (`Channel`) ve kullanıcı (`SubjectUserName`) yer alır.

Naif tespit bu kadar basittir: **Security 1102 VEYA System 104 gördüysen alarm üret.** Çoğu SOC'un ilk günkü tespit kuralı budur ve bir dedektörün olması gereken minimumdur. Sorun, bu kuralın çoğu gerçek olayda ya *geç kaldığı* ya *hiç ateşlenmediği* ya da tek başına ne olduğunu söyleyemediği için triyaj masasında ölü doğduğudur. Değer buradan sonra başlar.

---

## 2. Naif tespit neden yetmez

**Birincisi: 1102 kendini imha eden bir olaydır.** 1102 log temizlendiği anda, temizlenen günlüğün *içine* yazılır — yani temizleme işlemi bittikten hemen sonra o kanalın en eski (aslında tek kalan) kaydı odur. Eğer saldırgan aynı log kanalını birkaç saniye sonra tekrar temizlerse, önceki 1102 kaybolur ve elinizde yalnızca son 1102 kalır. Eğer log forwarding (WEF/WEC, ajan) gerçek zamanlı değilse ve batch/pull modelindeyse, ajanın bir sonraki toplama turundan *önce* ikinci temizlik gelirse o 1102'yi hiç görmezsiniz. Yani tespitiniz, koruması gereken şeyle aynı yerde yaşayan bir tanığa bağımlıdır. Adli mantıkta bu kabul edilemez.

**İkincisi: Topluca temizlik gürültülüdür, olgun saldırgan onu tercih etmez.** Deneyimli aktör tüm Security günlüğünü silmez — çünkü 1102 anlık ve yüksek-güven bir alarmdır; her SOC bunu izler. Bunun yerine **seçici silme** yapar: kendi logon oturumunu, belirli EventID'leri (4624/4625/4672/4688) veya belirli zaman aralığını hedef alır. Bunun için EVTX dosyasını doğrudan manipüle eden araçlar (ör. EVTX kayıt yapısını düzenleyen kamu araçları) veya EventLog servisinin process'ine bellek üzerinden müdahale eden teknikler kullanılır. Seçici silme **ne 1102 ne 104 üretir** — çünkü Windows'un "log temizlendi" mantığı yalnızca API üzerinden yapılan topyekûn clear çağrısına bağlanmıştır. Sizin naif kuralınız bu senaryoda tamamen kördür.

**Üçüncüsü: EventLog servisini durdurmak clear değildir.** Saldırgan `net stop eventlog` veya servis manipülasyonu ile günlüklemeyi *duraklatırsa*, o pencerede yapılan hiçbir eylem loglanmaz ve ne 1102 ne 104 üretilir. Sonrasında servisi tekrar başlatır. Elinizde tek iz, System kanalındaki servis durma/başlama olayları (**EventID 7034/7035/7036**, kaynak Service Control Manager) ve olsa olsa bir **zaman boşluğu** olur. Naif "1102 gör" kuralı burada da sessizdir.

**Dördüncüsü: 1102 tek başına *bağlam* taşımaz.** Diyelim 1102 ateşlendi. `SubjectUserName` alanında ne var? Çoğu ortamda cevap `SYSTEM` veya bir hizmet hesabıdır — çünkü temizlik meşru bir süreç (imaj yeniden kurulumu, GPO, bir bakım scripti) tarafından yapılmış olabilir. 1102'nin kendisi size "bu kötü müydü" sorusunu *cevaplamaz*; sadece "log temizlendi" der. Tek sinyalli bir alarm olarak 1102, olgun ortamlarda haftada birçok kez ateşlenir ve analist onu görmezden gelmeyi öğrenir. Alarm yorgunluğu (alert fatigue) tam da böyle başlar: teknik olarak doğru ama bağlamsız bir dedektör, pratikte kapatılan bir dedektördür.

**Beşincisi: kapsam sorunu.** 1102 sadece **Security** kanalı içindir. Saldırgan PowerShell Operational (`Microsoft-Windows-PowerShell/Operational`), Sysmon Operational, TerminalServices, veya Windows Defender Operational gibi kanalları temizlerse Security 1102 çıkmaz — bunlar System 104 üretir (klasik günlükler) ama bazı Operational kanallar için davranış tutarsızdır. Yalnızca 1102'ye bakan bir SOC, kendi izleme kanallarının (ör. Sysmon) silinmesini kaçırır.

---

## 3. Korelasyon zinciri (asıl değer)

Log temizleme **tek başına zayıf ve geç bir sinyaldir**. Onu yüksek-güven bir ihlal tespitine çeviren şey, *zaman ve fail ekseninde onu çevreleyen olaylardır*. Kıdemli detection engineer log temizlemeyi bir "olay" olarak değil, bir **saldırı zincirinin kapanış hareketi** olarak modeller. İşte pratikte kurulan bağlar:

**Zincir A — "Temizlikten önce ne oldu?" (retrospektif pivot):**
1102/104 ateşlendiğinde, ilk refleks alarmı kapatmak değil, **aynı host + aynı `SubjectLogonId` için temizlikten önceki 60 dakikayı** açmaktır. Aranan desen:
`4624 (Type 3 veya 10 logon, olağandışı kaynak IP)` → `4672 (special privileges assigned — SeDebugPrivilege, SeBackupPrivilege)` → `4688 / Sysmon EventID 1 (process creation: cmd, powershell, rundll32, wmic)` → **`1102` / `104`**.
Yani "ayrıcalıklı bir oturum açıldı, hassas privilege'lar alındı, birkaç komut çalıştı ve *hemen ardından* log temizlendi" deseni, tek başına 1102'den kat kat daha güçlüdür. Buradaki altın kural: temizlik, saldırının *son* adımıdır; değerli iz temizlikten önceki dakikalardadır ve o iz genellikle **başka bir kanalda** (Sysmon, PowerShell Operational) hâlâ durur çünkü saldırgan sadece Security'yi temizlemiştir.

**Zincir B — "Fail hesabı meşru mu?" (kimlik korelasyonu):**
`SubjectUserName` bir **interaktif kullanıcı** (bir çalışan hesabı) ve temizlik **iş saatleri dışında** ise, güven ciddi yükselir. Meşru temizlik neredeyse her zaman `SYSTEM`, bir bakım hizmet hesabı, veya bilinen bir yönetim sunucusundan gelir. Bir muhasebe kullanıcısının hesabıyla saat 03:14'te Security log temizlenmesi, tek başına 1102'nin taşıyamayacağı bir hikâye anlatır. Bunu **UEBA/temel çizgi (baseline)** ile birleştirin: "bu hesap daha önce hiç log temizlemedi + bu host'ta daha önce hiç temizlik olmadı" = anomali skoru tavan.

**Zincir C — "Yatay yayılma imzası" (çok-hostlu korelasyon):**
Gerçek bir ihlalde temizlik **tek host'ta kalmaz**. Ransomware operatörü veya APT, birden fazla makinede iz siler. Bu yüzden en güçlü tespitlerden biri: **kısa bir pencere içinde (ör. 30 dk) N'den fazla farklı host'ta 1102/104**. Somut desen: `Host-A'da 1102 (14:02)` + `Host-B'de 1102 (14:05, aynı SubjectUserName)` + `Host-C'de 104 (14:09)`. Tek host'ta 1102 gürültü olabilir; **aynı fail hesabıyla üç host'ta beş dakikada temizlik** neredeyse kesin bir ihlaldir. Domain controller'da veya birden fazla DC'de eşzamanlı temizlik ise kırmızı alarmdır.

**Zincir D — "Anti-forensic küme" (teknik ailesi korelasyonu):**
Log temizleme nadiren yalnız gelir. Onu diğer T1070 alt-tekniklerle aynı zaman penceresinde arayın:
- **Volume Shadow Copy silme**: `vssadmin delete shadows`, `wmic shadowcopy delete` (T1490).
- **USN journal / dosya zaman damgası manipülasyonu** (timestomp, T1070.006).
- **PowerShell / bash history temizleme** (T1070.003).
- **`fsutil usn deletejournal`**.
Aynı host'ta 20 dakika içinde `1102` + `vssadmin delete shadows` görürseniz, bu bir "bakım" değil, bir **kapanış sekansıdır** — büyük olasılıkla ransomware şifrelemesinden hemen önce. Bu iki sinyalin birleşimi, ikisinin toplamından değil çarpımından değerlidir.

**Zincir E — "Temizlik değil, susturma" (negatif alan / gap tespiti):**
En zor ama en değerli sinyal: **log akışının aniden durması**. Bir host normalde dakikada X olay üretirken birden sıfıra düşerse (ve host hâlâ ağdaysa, ping'e cevap veriyorsa), bu ya EventLog servisinin durdurulduğunu ya da forwarding'in kesildiğini gösterir. Bu "olmayan olayın" tespiti, temizleme API'sini hiç çağırmayan saldırganı yakalayan tek yoldur. SIEM tarafında buna genelde "log source stopped reporting" / "heartbeat kaybı" kuralı denir ve ihmal edilir — çünkü olayların *yokluğunu* aramak, varlıklarını aramaktan zihinsel olarak daha zordur.

Bu zincirlerin ortak dersi: **1102'yi bir tetikleyici değil, bir pivot noktası olarak kullanın.** Alarm ateşlendiği anda otomatik bir sorgu, o host+hesap için temizlik-öncesi pencereyi ve diğer hostlardaki eşzamanlı temizlikleri getirmeli. İşte Google'ın tek sayfada vermediği şey budur.

---

## 4. False positive gerçeği ve triyaj yargısı

Olgun bir kurumsal ortamda 1102/104 **her gün** ateşlenir ve büyük çoğunluğu iyi huyludur. Deneyimli analistin işi, gürültüyü elemek için hızlı ve tutarlı bir yargı ağacı uygulamaktır. Gerçek dünyada bu alarmı meşru üreten başlıca kaynaklar:

- **İmaj yeniden kurulumu / provisioning**: SCCM/MECM, MDT, Autopilot ve benzeri araçlar bir makineyi kurarken veya "sysprep" sürecinde günlükleri temizler. Fail hesabı `SYSTEM`, host bir "yeni kurulan makine", zaman bir bakım penceresi. Bu, en yaygın FP kaynağıdır.
- **Yedekleme yazılımı**: Bazı ajanlar (özellikle eski sürümler) Security log'u yedekleyip "arşivle ve temizle" (backup-and-clear) modunda çalışır. Bu, düzenli aralıklarla, hizmet hesabıyla, aynı hostlarda tekrar eden bir desen üretir.
- **Vuln scanner / yönetim araçları**: Kimlik doğrulamalı taramalar, ajan dağıtımları, GPO-tabanlı bakım scriptleri.
- **Admin scriptleri**: Bir sistem yöneticisinin "disk doluyor, logları temizleyeyim" refleksiyle çalıştırdığı `wevtutil cl` döngüsü. Bunlar interaktif hesapla gelir ve en çok kafa karıştıran FP'lerdir çünkü kötü niyetliye *benzer*.
- **Test/laboratuvar makineleri**: Sık yeniden kurulan, sürekli temizlenen ortamlar.

Kıdemli analistin gerçek/gürültü ayrımı için sorduğu sırayla sorular (triyaj yargı ağacı):

1. **`SubjectUserName` nedir?** `SYSTEM` veya bilinen bir hizmet hesabı mı, yoksa bir interaktif çalışan hesabı mı? İnteraktif hesap = güven yukarı.
2. **Host kim?** Yönetim sunucusu / bilinen provisioning hedefi / lab mı, yoksa bir DC, bir dosya sunucusu, bir yönetici iş istasyonu mu? Kritik varlıkta temizlik = güven yukarı.
3. **Zaman?** Planlı bakım penceresi mi, yoksa 03:00 mi? Bilinen bir değişiklik kaydı (change ticket) var mı? Yoksa güven yukarı.
4. **Tek mi, çoklu mu?** Bu host bu saatte tek başına mı temizledi, yoksa aynı hesapla başka hostlarda da mı temizlik var? Çoklu = güven tavan.
5. **Temizlikten önceki 30 dakikada ne var?** Ayrıcalıklı logon, olağandışı process, lateral hareket izi (Zincir A) var mı? Varsa artık FP tartışması bitmiştir.

Çoklu alarm geldiğinde deneyimli analist **önce en kritik varlığa ve en anormal fail hesabına** bakar — DC'de veya yönetici hesabıyla gelen temizliği, lab makinesindeki SYSTEM temizliğinden önce çeker. İkinci refleks: **temizliğin *kapsamını*** kontrol etmek — sadece Security mi temizlendi, yoksa Sysmon/PowerShell Operational da mı? Bir saldırgan tam olarak *sizin izlediğiniz* kanalları hedeflerken, bir bakım scripti gelişigüzel Security'yi temizler. Hedef seçimi niyeti ele verir.

FP'leri azaltmanın kalıcı yolu **allowlist değil, bağlam zenginleştirmedir**: bilinen provisioning hostlarını ve bakım hizmet hesaplarını bir referans listesinde tutup alarmı bastırmak yerine *skorunu düşürmek* — çünkü kompromize olmuş bir bakım hesabı en tehlikeli senaryodur ve tam allowlist onu görünmez yapar.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan naif "1102 gör" kuralını bilir ve onu atlatmak için kural dokümanında *yazmayan* yollara başvurur. Her kaçınma için ikinci-derece bir tespit vardır:

**Kaçınma 1 — Servisi durdur, iz bırakma, sonra çalış.**
`net stop eventlog` veya EventLog servisini bir alt-process olarak sonlandırma. Bu pencerede yapılan hiçbir şey loglanmaz; clear API çağrılmadığı için 1102/104 yok.
**Karşı-tespit:** EventLog servisi normalde durmaz. System kanalında **EventID 7035/7036 (servis durum değişimi)** ve **7034 (beklenmedik sonlanma)**, kaynak "Service Control Manager" — özellikle `eventlog` servisi için. Ayrıca Sysmon **EventID 5 (process terminated)** ve servis process'inin (svchost, `EventLog` grubu) sonlanması. En güçlüsü: **log heartbeat kaybı** — SIEM tarafında bu host'un olay akışının ani durması. Servis durdurma, temizlemeden *daha* şüphelidir çünkü meşru sebebi neredeyse yoktur.

**Kaçınma 2 — Seçici silme (EVTX manipülasyonu).**
Tüm log yerine yalnızca kendi izlerini (belirli EventID/oturum) silmek. Clear API kullanılmaz, dosya doğrudan düzenlenir. 1102/104 üretilmez.
**Karşı-tespit:** Bunu *önlemenin* en sağlam yolu logları host'tan **çıkarmaktır** — WEF/WEC veya ajanla gerçek zamanlı forwarding. Merkeze ulaşmış olay artık host üzerinde silinemez; saldırgan yerel EVTX'i düzenlese de merkez kopyası durur. Host üzerinde ise: EVTX dosyalarına (`C:\Windows\System32\winevt\Logs\*.evtx`) doğrudan **yazma/handle açma** erişimini Sysmon **EventID 11 (FileCreate)** / **EventID 2 (file creation time changed — timestomp)** ile ve dosya bütünlüğü izlemesiyle yakalamak. Ayrıca EVTX içindeki **kayıt numarası sürekliliği**: adli araç EVTX'teki RecordID'lerde atlama/boşluk arar — seçici silme kayıt zincirinde kopukluk bırakır.

**Kaçınma 3 — İzleme kanalını hedefle (Sysmon/PowerShell Operational sil).**
Security'yi bırakıp tam da sizin dedektörünüzü besleyen kanalları temizlemek. Sysmon config'i devre dışı bırakma, Sysmon servisini durdurma.
**Karşı-tespit:** Sysmon'un kendi kendini izlemesi: **Sysmon EventID 4 (Sysmon service state changed)** ve **255 (Sysmon error)**. Sysmon config değişimini, servis durmasını ve driver kaldırılmasını (`fltmc unload`) izleyin. Yine kurtarıcı, forwarding'dir: Sysmon olayları anında merkeze gitmeli ki yerel silme etkisiz kalsın. Bir de "meta-tespit": *dedektörün susması* bir sinyaldir — bir host normalde Sysmon EventID 1 üretirken birden kesilirse, Sysmon devre dışı bırakılmış demektir.

**Kaçınma 4 — LOLBIN ile dolaylı temizlik.**
`wevtutil` yerine WMI (`Win32_NTEventlogFile.ClearEventLog()`), PowerShell `Clear-EventLog`, `Get-EventLog -Newest ... | Remove-*`, veya `.NET` sınıfları (`System.Diagnostics.EventLog`) üzerinden temizlik. Amaç, komut satırı imzasından (`wevtutil cl`) kaçmak.
**Karşı-tespit:** Komut satırı string'ine değil **davranışa** bakın. Sonuç yine 1102/104'tür (API aynı) — ama *tetikleyici process* değişir. Sysmon EventID 1 ile `powershell.exe`/`wmic.exe`/`wmiprvse.exe`'nin log temizleme ile *ilişkilendirilmesi*: 1102 ile aynı `SubjectLogonId`'ye sahip son process yaratma olayı. Ayrıca PowerShell **ScriptBlock logging (EventID 4104)** — `Clear-EventLog`, `Remove-EventLog`, `.ClearEventLog()` string'lerini yakalar (kod obfuscate edilmemişse).

**Kaçınma 5 — "Gürültüde boğ".**
Meşru bir bakım penceresinde, allowlist'lenmiş bir hesapla temizlik yapmak — savunmacının kendi FP-bastırma kuralına sığınmak.
**Karşı-tespit:** Tam allowlist yerine skor düşürme (§4). Ayrıca bakım penceresi *dışında* aynı allowlist hesabının kullanılması, ya da o hesabın normalde temizlemediği bir hosttan temizlik yapması = anomali. Allowlist'i statik bir "geç" değil, "bu hesabın normal davranışı" temel çizgisiyle birlikte değerlendirin.

Buradaki genel prensip: **log temizleme tespitini host üzerindeki loglara dayandırdığınız sürece, saldırganla aynı zeminde oynarsınız ve o zemini o kontrol eder.** Tek kalıcı üstünlük, olayı host'tan *önce* dışarı taşımaktır (real-time forwarding) — böylece savaş, saldırganın silebildiği kopya üzerinde değil, sizin merkezî ve değişmez kopyanız üzerinde geçer.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** Ham EVTX'te temizleyen kullanıcı **`SubjectUserName`** ve oturum **`SubjectLogonId`** alanlarındadır (1102 için `UserData/LogFileCleared`, XML şemasında). Ama normalize edilmiş SIEM şemalarında bu alan adı değişir: Splunk CIM'de `user`, Sentinel/ASIM'de `ActorUsername` veya `TargetUserName`, Elastic ECS'te `winlog.event_data.SubjectUserName` ya da `user.name`. En yaygın hata: analist `TargetUserName` ararken 1102'de böyle bir alan **yoktur** — temizlemeyi yapan `Subject*` alanlarındadır. Yanlış alana bakan bir sorgu sessizce boş döner ve dedektör "çalışıyor gibi görünür" ama hiçbir şey yakalamaz. Bir de: 104 ve 1102'nin alan yapıları *birbirinden farklıdır* (104 System kanalında, farklı şema); ikisini tek sorguda birleştirirken alan adları eşleşmez.

**Varsayılan loglanmayan şeyler.** Kritik gerçek: **EventID 4688 (process creation) varsayılan olarak KAPALIDIR** ve açık olsa bile komut satırı argümanları ("Include command line in process creation events") ayrı bir GPO ayarı gerektirir. Bu açılmadan, "`wevtutil cl` çalıştı mı" sorusunu ham Windows loguyla cevaplayamazsınız — sadece sonucu (1102) görürsünüz, tetikleyiciyi değil. Bu yüzden ciddi ortamlar **Sysmon**'a dayanır: Sysmon EventID 1 hem komut satırını hem parent process'i hem hash'i verir. Ancak Sysmon ayrı kurulum ve iyi bir config (ör. topluluk bazlı sıkı config) ister; varsayılan Windows'ta yoktur. Özet audit policy gereksinimi: **Audit Object Access / Audit System Events** (1102/104 için Security ve System kanalları zaten üretir, ama forwarding şart), **Process Creation auditing + command line** (4688), ve tercihen **PowerShell ScriptBlock Logging (4104)** ve **Module Logging**. Bunlar açık değilse tespitiniz kâğıt üstündedir.

**Forwarding olmadan hepsi anlamsız.** §5'te tekrar tekrar söylenen şeyin SIEM karşılığı: 1102/104/4104/Sysmon olayları **host'tan gerçek zamanlı** merkeze akmıyorsa, saldırgan sizin göreceğiniz kopyayı silebilir. WEF/WEC ya da bir EDR/ajan ile push-based, düşük-gecikmeli toplama olmazsa olmazdır. Pull/batch toplama (ör. 15 dakikada bir) saldırgana temizlik penceresini hediye eder.

**Splunk vs Sentinel vs Elastic farkları.**
- **Splunk**: Windows TA (`Splunk_TA_windows`) 1102'yi `WinEventLog:Security`, 104'ü `WinEventLog:System` altında toplar; `EventCode=1102`. CIM'e `Change` / `Endpoint` datamodel'ine map edilir ama log-clear için hazır bir CIM alanı zayıftır — çoğu ekip ham `EventCode` üzerinden yazar. Universal Forwarder gerçek zamanlı çalışır (iyi). Tuzak: `index=wineventlog` içinde 104 ve 1102 farklı sourcetype/kanal olduğundan `EventCode IN (1102,104)` sorgusu iki kanalı da kapsamalı.
- **Sentinel**: `SecurityEvent` tablosunda `EventID == 1102`, ama modern dağıtımlarda **AMA (Azure Monitor Agent)** ve **DCR (Data Collection Rule)** ile hangi EventID'lerin toplandığı *açıkça seçilmelidir*. Varsayılan DCR "Common" profili 1102'yi içerir ama "Minimal" içermez — yani Sentinel'de 104/1102 tablonuza *hiç ulaşmıyor* olabilir ve bunu ancak DCR'ı denetleyince fark edersiniz. ASIM normalizasyonu (`imProcessCreate`, `ActorUsername`) alan adlarını yine değiştirir.
- **Elastic**: Winlogbeat/Elastic Agent ECS'e map eder; `event.code: "1102"`, `winlog.channel: "Security"`. Prebuilt detection rule'lar (`Windows Event Logs Cleared`) hazır gelir. Tuzak: ECS'te hem `winlog.event_data.SubjectUserName` (ham) hem `user.name` (normalize) bulunur ve ikisi her zaman aynı dolmaz; korelasyon için hangisine güveneceğinizi test edin.

**Tuning gerçeği.** Tek başına 1102 kuralı, ilk hafta içinde provisioning/backup FP'leriyle boğulur ve ya kapatılır ya görmezden gelinir. Sürdürülebilir tespit, §3'teki korelasyonu SIEM'de gerçekten yazmaktır: 1102'yi tetikleyici alıp, aynı host+`SubjectLogonId` için temizlik-öncesi pencereyi (`join`/`transaction`/`sequence` ile) ve çoklu-host desenini otomatik zenginleştiren bir kural. Elastic'te `sequence by host.id`, Splunk'ta `transaction` veya `stats` ile zaman-pencereli korelasyon, Sentinel'de `SecurityEvent`'i `DeviceProcessEvents` (Defender) ile `join` — pratikte tespiti kuran budur. Ve son tuning kuralı: **allowlist'i bastırma değil skorlama olarak** uygulayın, yoksa kompromize bakım hesabı sizin kendi istisnanızın arkasına saklanır.

---

### Kapanış yargısı
Event log temizleme, savunmacı için paradoksaldır: en gürültülü anti-forensic eylemdir (1102 anında bağırır), ama olgun saldırgan tam da bu yüzden onu ya hiç yapmaz (servisi durdurur / seçici siler) ya da kapanışta gürültüsü önemsiz hâle geldiğinde yapar. Bu yüzden değer, "1102 gördüm" demekte değil; onu bir **pivot** olarak kullanıp temizlik-öncesi dakikaları, çoklu-host desenini ve anti-forensic kümesini bağlamakta; olayı host'tan gerçek zamanlı çıkarıp saldırganın silemeyeceği bir kopya üzerinde savaşmakta; ve *log'un yokluğunu* (heartbeat kaybını) en az varlığı kadar ciddiye almaktadır. Naif kural minimumdur — tespit, ondan sonra başlar.
