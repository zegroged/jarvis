# Volume Shadow Copy Abuse — Tespiti

> Saha notu: Bu metin, "vssadmin delete shadows gördün mü, alarm bas" seviyesinin çok ötesinde yazılmıştır. Amaç, gerçek bir SOC'ta bu tekniğin neden yakalanmadığını, hangi sinyalin hangi sinyalle birleşince anlam kazandığını ve gece 03:00'te önünüzdeki 40 alarm arasından bu ihlali nasıl çekip çıkaracağınızı anlatmaktır.

---

## 1. Özet: Saldırı + Naif Tespit

Volume Shadow Copy (VSS), Windows'un dosya sistemi anlık görüntülerini (snapshot) tutan servisidir; yedekleme yazılımları, System Restore ve "Previous Versions" özelliği bunun üzerine oturur. Saldırgan için VSS iki ayrı sebeple değerlidir. Birincisi **impact / anti-recovery**: fidye yazılımı şifrelemeden hemen önce shadow copy'leri siler ki kurban dosyalarını geri yükleyemesin (MITRE ATT&CK **T1490 - Inhibit System Recovery**). İkincisi **credential access**: `ntds.dit` ve `SYSTEM` hive'ı çalışan bir domain controller'da kilitlidir; saldırgan bir shadow copy oluşturup snapshot'tan kilitsiz kopyayı çeker (T1003.003). Yani aynı teknik ailesi hem "yıkım" hem "kimlik hırsızlığı" için kullanılır ve bu ayrımı bilmek triage'ın kalbidir.

Naif tespit herkesin bildiği kalıptır: `process_creation` logunda `vssadmin.exe delete shadows` veya `wmic shadowcopy delete` komut satırını yakala. Sağlanan gerçek Sigma kurallarından **Esentutl Gather Credentials** (`7df1713a...`, `esentutl` + ` /p` komut satırı) bu ailenin credential-access tarafındaki naif imzasıdır — Conti'nin `ntds.dit`'i onarmak/erişmek için `esentutl /p` önermesine dayanır. Impact tarafında ise gerçek kurallar komut satırından kaçıp **DLL yükleme (image_load)** sinyaline geçmiştir: `vssapi.dll` (`37774c23...`), `vsstrace.dll` (`48bfd177...`) ve `vss_ps.dll` (`333cdbe8...`) DLL'lerinin "olağandışı" bir executable tarafından yüklenmesi.

Bu geçiş — komut satırından DLL yüklemeye — tesadüf değildir. VSS'i kötüye kullanmanın binlerce yolu vardır ve hepsi `vssadmin` çağırmaz. `ORCx41/DeleteShadowCopies` gibi araçlar `vssadmin` executable'ını hiç çalıştırmadan, doğrudan COM API üzerinden shadow copy'leri siler; işte bu yüzden Sigma cephesi savunmayı süreç adından **DLL yükleme davranışına** kaydırdı. Naif tespit hâlâ komut satırına bakıyorsa, saldırganın en olgun araçlarını daha baştan kaçırıyor demektir.

---

## 2. Naif Tespit Neden Yetmez

**Kör nokta 1 — süreç adı imzası ölüdür.** `CommandLine|contains: 'vssadmin'` kuralı yalnızca `vssadmin.exe`'yi doğrudan çağıran, gürültücü aktörleri yakalar. Oysa VSS API'si (`IVssBackupComponents` COM arayüzü) doğrudan çağrılabilir. `DeleteShadowCopies` gibi bir binary hiçbir zaman `vssadmin`, `wmic` veya `powershell` başlatmaz; sadece `vssapi.dll` / `vss_ps.dll`'i process'ine yükler ve API çağrısı yapar. Komut satırına bakan hiçbir kural bunu görmez. Impact kurallarının image_load'a geçmesinin tek sebebi budur.

**Kör nokta 2 — DLL yükleme sinyali tek başına gürültü denizidir.** Peki image_load'a geçince iş bitti mi? Hayır — tam tersine yeni bir sorun doğar. `vssapi.dll`'i günün her saati **meşru** onlarca proses yükler: `explorer.exe` (Previous Versions sekmesi), her türlü yedekleme ajanı, Windows Installer (`msiexec`), SystemSettings, WinRE ajanları. Kuralın `filter_main_windows` bloğuna bakın: `explorer.exe`, `System32\`, `SysWOW64\`, `WinSxS\`, `$WinREAgent\Scratch\`, `Package Cache\{...}` gibi kocaman bir beyaz liste var. Bu beyaz liste, kuralın gürültüde boğulmaması için mecburi. Ama işte tuzak: **saldırgan payload'unu `C:\Windows\System32\` altına veya installer görünümlü bir yola koyarsa, kural onu kendi eliyle filtreler.** Beyaz liste güvenlik açığına dönüşür.

**Kör nokta 3 — kolay atlatma, LOLBIN çeşitliliği.** Shadow copy silmenin/oluşturmanın kanonik olmayan yolları: `wmic shadowcopy delete`, `PowerShell` üzerinden `Get-WmiObject Win32_ShadowCopy | Remove-WmiObject`, `Win32_ShadowCopy` WMI sınıfı, `diskshadow.exe` script modu (`diskshadow /s script.txt`), `wbadmin delete catalog`, hatta `bcdedit /set recoveryenabled no` (silme değil ama recovery engelleme — aynı T1490). `vssadmin` stringi arayan kural bunların yarısını kaçırır. `diskshadow` özellikle sinsidir çünkü meşru bir yedekleme aracıdır ve script dosyasından okur — komut satırında `delete shadows` görünmez, `diskshadow /s C:\temp\x.txt` görünür.

**Kör nokta 4 — false positive selleri operatörü kör eder.** Diyelim doğru şeyi yaptınız, image_load kuralını açtınız. SCCM/Configuration Manager ajanları, Veeam, Acronis, Veritas NetBackup, Windows Server Backup, hatta bir vuln scanner'ın authenticated tarama modülü düzenli olarak VSS DLL'lerini yükler. Bir kurumsal ortamda bu kural günde yüzlerce olay üretebilir. Analist iki hafta sonra bu kuralı ya susturur (mute) ya da otomatik kapatır — ve gerçek fidye günü alarm o susturulmuş kuyruğa düşer. **Tespit mühendisliğinde bir kuralı öldürmenin en yaygın yolu onu fazla hassas bırakmaktır.**

Özetle: komut satırı imzası kapsam olarak dar, DLL yükleme imzası ise tek başına gürültücü. Hiçbiri tek başına "yüksek güven" değildir. Değer, bunları **bağlamakta**.

---

## 3. Korelasyon Zinciri (asıl değer)

Tek bir VSS sinyali zayıftır. Onu yüksek güvene çeviren şey, **zaman penceresi içinde farklı bağlamlardan gelen sinyalleri örmektir**. İki farklı senaryo için iki ayrı zincir kuruyorum, çünkü VSS abuse'un impact ve credential-access yüzleri tamamen farklı korelasyonlar ister.

### Zincir A — Fidye yazılımı, anti-recovery (T1490)

Fidye operatörü nadiren tek başına shadow copy siler; bu, şifreleme koreografisinin bir adımıdır. Gerçek yüksek-güven deseni:

**A1 — Toplu servis/recovery müdahalesi (kısa pencere):** 60-120 saniyelik bir pencerede aynı host'ta arka arkaya: `vssadmin delete shadows /all /quiet` **VEYA** olağandışı bir executable'dan `vssapi.dll` yüklemesi (`37774c23`), ardından `bcdedit /set {default} recoveryenabled no`, `wbadmin delete catalog -quiet`, ve `wevtutil cl` (log temizleme). Bunların **tek tek** her biri zayıf; **arka arkaya aynı süreç ağacında** olması neredeyse patognomoniktir.

**A2 — Anormal ebeveyn/kaynak:** VSS silme komutunu doğuran süreç kimdir? Meşru yedekleme yazılımı VSS'i kendi servis kimliği altında çağırır. Fidyede ebeveyn genellikle `cmd.exe` → `wscript.exe`, `powershell.exe`, Office ürünü, veya bir `%TEMP%`/`AppData` yolundaki imzasız binary'dir. Burada sağlanan **"Rare Remote Thread Creation By Uncommon Source Image"** (`02d1d718`) kuralı devreye girer: `cscript.exe`, `esentutl.exe`, `expand.exe` gibi LOLBIN'lerin **remote thread** oluşturması (T1055 process injection). Fidye/Cobalt Strike zincirinde bu, "enjekte edilmiş süreç şimdi VSS'i siliyor" demektir. `create_remote_thread` + kısa pencerede VSS DLL yüklemesi = enjeksiyon sonrası impact.

**A3 — Hızlı seri dosya değişimi:** Aynı pencerede yüksek hacimli dosya yeniden adlandırma / uzantı değişimi (`.locked`, `.crypt` vb.) veya olağandışı entropi artışı. VSS silme **öncesinde** gelir; şifreleme **sonrasında**. Bu sırayı görürseniz — VSS sil, sonra kitle dosya rename — bu bir tatbikat değildir.

**Yüksek güven kararı:** `A1 (VSS + recovery müdahale demeti) + A2 (anormal/enjekte ebeveyn) + A3 (kısa pencerede kitle dosya değişimi) = doğrulanmış fidye`. Herhangi biri tek başına ticket; üçü birden **çağrı-uyandır (page)** olayıdır.

### Zincir B — DC'den kimlik hırsızlığı (T1003.003)

Bu tamamen farklı bir hikâye ve genelde **domain controller**'da geçer.

**B1 — Shadow copy OLUŞTURMA (silme değil!):** `vssadmin create shadow /for=C:` veya `diskshadow` ile snapshot yaratılır. Dikkat: impact senaryosu **siler**, credential senaryosu **oluşturur**. Bir DC'de shadow copy *oluşturulması* zaten kendi başına şüphelidir — çünkü DC'de kimse manuel snapshot almaz, yedekleme ajanı alır. Yedekleme ajanı olmayan bir prosesten `create shadow` = kırmızı bayrak.

**B2 — Snapshot yolundan NTDS kopyalama:** Snapshot oluşunca `\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopyN\Windows\NTDS\ntds.dit` ve `...\System32\config\SYSTEM` kopyalanır. Sağlanan **Esentutl Gather Credentials** kuralı (`esentutl` + ` /p`) tam burada devreye girer: Conti, kopyalanan (ve muhtemelen "dirty" durumdaki) `ntds.dit`'i `esentutl /p` ile onarır. Yani `create shadow` → dosya kopya → `esentutl /p ntds.dit` = üç adımlı NTDS hırsızlığı.

**B3 — DC bağlamı + kısa süre sonra anormal kimlik doğrulama:** Kopyalama başarılıysa saldırgan offline `secretsdump` çalıştırır ve saatler/günler içinde daha önce hiç görülmemiş hesaplarla **DCSync (Event 4662)** veya golden ticket belirtileri (anormal TGT süreleri, `krbtgt` kullanımı) baş gösterir. VSS→NTDS zincirini o gün göremediyseniz bile, sonraki DCSync'i geriye doğru bu olaya bağlayabilirsiniz.

**Yüksek güven kararı:** `B1 (DC'de non-backup create shadow) + B2 (GLOBALROOT'tan ntds.dit erişimi VEYA esentutl /p) = kesin credential theft girişimi`. DC üzerinde olması güveni tek başına yükseltir; DC dışı bir sunucuda `create shadow` çok daha meşru olabilir.

**Google tek sayfada bunu vermez** çünkü her makale ya sadece `vssadmin delete`'i (impact) ya da sadece `esentutl`'ü (credential) anlatır. İkisinin **farklı zincirler** olduğunu, birinin *silme* diğerinin *oluşturma* ile başladığını, ve her birinin farklı ikinci-derece sinyalle (kitle dosya değişimi vs. DCSync) doğrulandığını bir arada gösteren şey saha tecrübesidir.

---

## 4. False Positive Gerçeği ve Triage Yargısı

Bu alarm ailesinin meşru üreticileri, gerçek bir kurumda şunlardır — ve her birinin bir "parmak izi" vardır:

- **Yedekleme yazılımı (Veeam, Acronis, Veritas, Commvault, Windows Server Backup):** VSS DLL'lerini yükler ve `create shadow` yapar. **Parmak izi:** Süreç kendi kurulum dizininden çalışır (`C:\Program Files\Veeam\...`), imzalıdır, düzenli/zamanlanmış saatlerde tetiklenir (gece yedekleme penceresi), ve **create** yapar, toplu **delete /all** yapmaz. Meşru retention politikası eski snapshot'ları teker teker siler ama `bcdedit`/`wevtutil` demeti eşlik etmez.
- **SCCM / Configuration Manager & MDT:** Yazılım dağıtımı ve OS imajlama sırasında VSS'e dokunur. **Parmak izi:** `ccmexec.exe` süreç ağacı, bilinen SCCM sunucusundan tetiklenme, bakım penceresi.
- **Vuln scanner authenticated tarama (Nessus, Qualys, Rapid7):** Bazı denetim modülleri VSS'e dokunabilir. **Parmak izi:** Kaynak IP taramanın bilinen scanner host'u, geniş bir host filosuna aynı anda aynı deseni basar — tekil değil, filo-geneli.
- **Admin scriptleri / System Restore:** `explorer.exe`'nin Previous Versions sekmesi `vssapi.dll` yükler; bir sysadmin manuel `vssadmin list shadows` çalıştırır. **Parmak izi:** `list` (okuma) zararsızdır, `delete /all /quiet` değil. İnteraktif oturum, gündüz saati, konsol.

**Kıdemli analistin gerçek/gürültü ayrım kuralları:**

1. **Fiil ayrımı `list` << `create` << `delete /all /quiet`.** `list` neredeyse hiç önemli değil. `create` bağlama göre (DC'de kritik, dosya sunucusunda normal). `delete shadows /all /quiet` **meşru retention'da neredeyse hiç kullanılmaz** — yedekleme yazılımı belirli snapshot ID'sini siler, hepsini `/quiet` ile toptan uçurmaz. `/all /quiet` kombinasyonu tek başına kaliteyi ciddi yükseltir.

2. **"Yalnızlık" testi:** Sinyal tek mi, demet mi? Yedekleme ajanı VSS'e dokunur ama `bcdedit recoveryenabled no` + `wbadmin delete catalog` + `wevtutil cl` yapmaz. **Demet = kötü niyet.**

3. **Kimlik/yol testi:** Süreç imzalı mı, kendi Program Files dizininden mi çalışıyor, yoksa `%TEMP%`/`AppData`/`\Users\Public`'ten mi? İmzasız/geçici-yol + VSS = üst sıra.

4. **Zamanlama testi:** Yedekleme penceresi (gece 02:00) mi, yoksa Salı öğlen 14:37 rastgele mi? Beklenen pencerede beklenen ajandan gelen olay gürültüdür.

**Çoklu alarmda öncelik sırası (aynı anda 3 host'ta patladı diyelim):**

- **P1 (hemen page):** Domain Controller üzerinde `create shadow` + `ntds.dit`/GLOBALROOT erişimi veya `esentutl /p`. Kimlik hazinesi tehdidi, dakikalar önemli.
- **P1 (hemen page):** Herhangi bir host'ta VSS `delete /all /quiet` + recovery-müdahale demeti + kitle dosya değişimi. Aktif fidye şifrelemesi, saniyeler önemli — hostu izole et.
- **P2 (öncelikli ticket):** İmzasız/geçici-yol prosesten VSS DLL yüklemesi, demet yok ama bağlam kötü. Araştır.
- **P3/kapat:** Bilinen yedekleme ajanından, bakım penceresinde, `create`/`list`, imzalı, kendi dizininden. Baseline'a ekle, sustur — ama **allowlist'i süreç adı+yol+imza üçlüsüyle** dar tut, sadece "vssapi.dll yüklendi" diye değil.

---

## 5. Kaçınma → Karşı-Tespit

Saldırgan, kural dokümanında yazmayan yollarla atlatmaya çalışır. Her birine ikinci-derece tespit:

**Kaçınma 1 — `vssadmin`'i hiç çağırmamak, doğrudan COM API.** `DeleteShadowCopies` tarzı araçlar `IVssBackupComponents::DeleteSnapshots`'ı doğrudan çağırır.
**Karşı-tespit:** Zaten sağlanan image_load kuralları (`vssapi.dll`, `vss_ps.dll`, `vsstrace.dll`) tam bunun için var. Ama beyaz liste tuzağına düşmeyin: kuralın `filter_main` bloğu `System32\`'yi komple filtreliyor. **Tuning:** İmza kontrolü ekleyin — `System32\` altında olsa bile *imzasız* veya Microsoft-imzalı-olmayan bir binary VSS DLL yüklüyorsa filtreyi delin. Sadece yol bazlı beyaz liste yetersizdir.

**Kaçınma 2 — LOLBIN üzerinden dolaylı çağrı.** `wmic shadowcopy delete`, `Get-WmiObject Win32_ShadowCopy | Remove-WmiObject`, `diskshadow /s script.txt`, `wbadmin`.
**Karşı-tespit:** `vssadmin` string'ine değil, **WMI `Win32_ShadowCopy` sınıfına yapılan Delete işlemine** bakın (WMI-Activity operational log, Event 5857/5858 veya Sysmon değil ama WMI provider). `diskshadow` için: `diskshadow.exe` süreç başlatma + `-s`/`/s` parametresi (script modu) + ebeveynin backup ajanı olmaması. `diskshadow`'un script dosyasını da (`FileCreate` + sonra `diskshadow /s` aynı yolu okuma) yakalayabilirsiniz.

**Kaçınma 3 — Renaming / kopyalama (masquerading).** Saldırgan `vssadmin.exe`'yi `svchost.exe` veya `backup.exe` olarak kopyalar; ya da payload'unu `C:\Windows\System32\` içine atarak image_load beyaz listesini sömürür.
**Karşı-tespit:** İç imza (`OriginalFileName` / `Description` PE alanı) ile dış dosya adını karşılaştırın. Sysmon Event ID 1 `OriginalFileName`'i verir. `OriginalFileName == VSSADMIN.EXE` ama `Image` adı farklıysa → masquerade. Yol bazlı değil, **PE-metadata bazlı** eşleme kaçınmayı kapatır.

**Kaçınma 4 — Yavaşlatma / "living off the land" gürültüye karışma.** Saldırgan VSS silmeyi meşru yedekleme penceresine denk getirir, tek komut çalıştırıp bekler, demet oluşturmaz.
**Karşı-tespit:** Burada tek olayı yakalayamazsınız — **baseline sapması** gerekir. "Bu host'ta VSS delete'i normalde yalnız `Veeam.Backup.Manager.exe` yapar" davranışsal baseline'ı kurulmuşsa, aynı işi yapan **farklı bir ebeveyn** anomalidir. UEBA/baseline olmadan bu kaçınma başarılıdır; dürüst olmak gerekirse en zor yakalanan senaryo budur.

**Kaçınma 5 — Log temizleme ile örtbas.** `wevtutil cl`, olay loglarını temizleyerek zinciri kırar.
**Karşı-tespit:** Log temizlemenin kendisi güçlü bir sinyaldir: **Security Event 1102 (audit log cleared)** ve **System Event 104 (log file cleared)**. VSS delete penceresine yakın bir 1102/104, tek başına ikisinden daha güçlüdür. Ayrıca logları merkezî SIEM'e **gerçek zamanlı** akıtın — saldırgan yereldeki logu temizlese de forwarder olayı çoktan göndermiştir. Yerel log silme, merkezî kopya karşısında etkisizdir; bu yüzden forwarding gecikmesi (batch vs. real-time) kritik.

---

## 6. SIEM / Saha Gerçeği

**Varsayılan loglanmayan şeyler — önce bunu düzeltmeden kural yazmak boşunadır:**

- **`image_load` (Sysmon Event ID 7) varsayılan olarak KAPALIDIR ve açık haldeyse aşırı gürültülüdür.** Sağlanan üç DLL kuralının (`vssapi.dll`, `vsstrace.dll`, `vss_ps.dll`) çalışması **mutlaka Sysmon Event ID 7'nin açık olmasını** gerektirir. Ama ID 7'yi geniş açmak günde milyonlarca olaydır; SwiftOnSecurity/Olaf config'lerinde ImageLoad genelde daraltılır. **Pratik çözüm:** ImageLoad'ı yalnız bu spesifik VSS DLL'leri için filtreleyen dar bir Sysmon include kuralı yazın — tüm DLL yüklemelerini değil. Config satırı örneği mantığı: `<ImageLoad onmatch="include"><ImageLoaded condition="end with">vssapi.dll</ImageLoaded>...`. Bu yapılmazsa kural "test" statüsünde kalır ve sahada hiç veri görmez.

- **`create_remote_thread` (Sysmon Event ID 8)** — "Rare Remote Thread" kuralı (`02d1d718`) bunu ister. Bu da default Windows'ta yoktur; yalnız Sysmon verir. ID 8 nispeten düşük hacimlidir, açık tutulabilir.

- **Process creation komut satırı loglama.** `vssadmin` komut satırı kuralları için ya **Security Event 4688 + "Include command line in process creation events" GPO'su açık** olmalı, ya da **Sysmon Event ID 1**. Default'ta 4688 komut satırını **loglamaz** — sadece süreç adını verir. `vssadmin.exe` çalıştığını görürsünüz ama `delete shadows /all /quiet` argümanını göremezsiniz, ki tüm ayrım orada. GPO: `Administrative Templates > System > Audit Process Creation > Include command line`.

- **`ntds.dit` erişimi.** GLOBALROOT yolundan dosya erişimini görmek için **object access auditing (Event 4663)** gerekir ve NTDS klasörüne SACL konmalıdır — neredeyse hiçbir yerde default açık değildir. Pratikte Sysmon Event ID 11 (FileCreate) + `esentutl` komut satırı daha güvenilir sinyaldir.

**Field mapping tuzakları (platform farkları):**

- **Splunk (Sysmon TA):** DLL kuralındaki `ImageLoaded` alanı Splunk'ta genelde `ImageLoaded` olarak gelir ama bazı TA sürümlerinde `image_loaded` veya CIM'e map edilince `file_path` olur. `Image` (yükleyen süreç) ile `ImageLoaded` (yüklenen DLL) karıştırılırsa kural ters çalışır — bu klasik bir hata. Sigma'daki `Image` = yükleyen proses, `ImageLoaded` = kurban DLL.
- **Microsoft Sentinel:** Sysmon verisi genelde `Event` tablosunda ham XML olarak veya `DeviceImageLoadEvents`'te (Defender for Endpoint) gelir. MDE'de alan adları tamamen farklıdır: `ImageLoaded` yerine `FolderPath` + `FileName`, `Image` yerine `InitiatingProcessFolderPath`. Sigma kuralını doğrudan yapıştırmak çalışmaz; MDE şemasına çevirmek gerekir. Ayrıca MDE ImageLoad telemetrisini agresif filtreler — bazı VSS DLL yüklemeleri EDR tarafından hiç raporlanmayabilir.
- **Elastic:** ECS'te `Image` → `process.executable`, `ImageLoaded` → `dll.path` (veya eski sürümde `file.path`), `CommandLine` → `process.command_line`. ECS'e migrate edilmiş bir ortamda ham Sysmon alan adıyla yazılmış Sigma hiç eşleşmez; `sigma` CLI ile ECS backend'ine derlemek şart.

**Tuning ve operasyonel gerçek:**

1. **Beyaz listeyi imzayla güçlendir.** Sağlanan `filter_main_windows` bloğu saf yol tabanlı (`System32\`, `WinSxS\`...). Sahada bunu **imza durumuyla** birleştirin: "System32 altında AMA Microsoft imzalı" filtreleme çok daha güvenli. Aksi halde saldırgan payload'unu System32'ye atıp kuralı bypass eder.
2. **Kurumsal yedekleme ajanlarını isim+yol+imza üçlüsüyle allowlist'e al**, salt DLL adıyla değil. `Veeam.Backup.Manager.exe` @ `C:\Program Files\Veeam\` @ imzalı → filtrele. Bu üçlü yoksa geçir.
3. **Kuralları korelasyon katmanında birleştir.** Tekil DLL/komut kuralları `level: medium`'da bırakılmalı (ticket), ama SIEM'de bir **correlation search** kurun: "aynı host, 120 saniye pencere, VSS-delete + (bcdedit VEYA wbadmin VEYA wevtutil) → level: high, page." Sigma'nın yeni `correlation` özelliği (temporal/event_count) tam bunun için; tek tek kuralları yükseltmek yerine bileşimi yükseltin.
4. **DC'yi ayrı bir kural kümesiyle izle.** DC'de `create shadow` neredeyse her zaman şüpheli; üye sunucuda değil. `logsource` veya host grubu bazlı ayrım yapıp DC'lerde eşiği düşürün.
5. **`esentutl /p` kuralını genişlet.** Sağlanan Conti kuralı yalnız `esentutl` + ` /p` bakıyor; buna `ntds`, `.dit` veya GLOBALROOT string kontrolü eklerseniz false positive (meşru DB onarımı) düşer. Ama dikkat: saldırgan dosyayı önce başka isme kopyalayıp onarabilir, o yüzden salt dosya adına güvenmeyin — ebeveyn/bağlam da bakın.

**Son yargı:** Volume Shadow Copy abuse tespiti, tek bir "sihirli kural" işi değildir. Sağlanan gerçek Sigma kuralları (`vssadmin`/`esentutl` komut satırı + üç VSS DLL image_load + remote thread) birer **ham sinyaldir**. Bunları yüksek güvene çeviren şey (a) impact ile credential-access zincirlerini ayırmak, (b) VSS sinyalini recovery-müdahale demeti / kitle dosya değişimi / DCSync ile zaman penceresinde örmek, (c) beyaz listeyi yol yerine imzayla sağlamlaştırmak, ve (d) doğru telemetriyi (Sysmon ID 1/7/8, command-line auditing, DC ayrımı) baştan açmaktır. Bunlar olmadan kural "test" statüsünde defter süsü olarak kalır; sahada fidye günü sessiz kalır.
