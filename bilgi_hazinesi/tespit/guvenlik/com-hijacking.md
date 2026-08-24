# COM Hijacking — Tespiti

> Saha notu. 15+ yıl detection engineering / SOC lead perspektifi. Bu metin "Event 4657'ye bak, tamamdır" seviyesinin çok ötesinde; asıl amaç sinyalleri **bağlamak**, tespitin gerçek ortamda **neden çöktüğünü** anlatmak ve **yargı** vermek.

---

## 1. Özet: saldırı + naif tespit (herkesin bildiği kısım)

COM (Component Object Model), Windows'un yıllardır sırtında taşıdığı devasa nesne-çağırma altyapısı. Bir uygulama `CLSID` (Class ID) üzerinden bir COM nesnesi istediğinde, Windows registry'de o sınıfın nasıl hayata geçeceğini arar: `InprocServer32` (bir DLL yükle), `LocalServer32` (bir EXE çalıştır) ya da `TreatAs` (aslında şu diğer CLSID'yi kullan) anahtarları. Kritik nokta şu: Windows nesneyi ararken **önce `HKEY_CURRENT_USER` (HKCU) altına bakar, sonra `HKEY_LOCAL_MACHINE` (HKLM) altına**. Yani kullanıcı düzeyinde (yönetici hakkı gerektirmeyen) bir registry yazımı, makine düzeyindeki meşru kaydı **gölgeleyebilir**. COM Hijacking'in bel kemiği budur: `HKCU\Software\Classes\CLSID\{...}\InprocServer32` altına saldırganın DLL'ini yazarsın, o CLSID her çağrıldığında senin kodun kullanıcı bağlamında yüklenir. Kalıcılık (persistence), savunma kaçırma (defense evasion) ve — DCOM ile birleştiğinde — yanal hareket (lateral movement) hepsi tek teknikte toplanır. MITRE'de karşılığı **T1546.015** (Event Triggered Execution: Component Object Model Hijacking) ve yanal hareket tarafında **T1021.003** (DCOM).

Saldırının cazibesi "sık çağrılan bir CLSID"yi ele geçirmekte. Explorer başlatıldığında, bir zamanlanmış görev tetiklendiğinde, Office açıldığında otomatik yüklenen CLSID'ler vardır. Bunlardan birini hijack edersen, kullanıcı sadece normal işini yaparken senin implant'ın tekrar tekrar canlanır — hiçbir Run key, hiçbir Startup klasörü, hiçbir Service yok. Klasik APT29/Cozy Bear oyun kitabında bu yüzden yer aldı.

Naif tespit herkesin ilk aklına geleni yapar: Sysmon **Event ID 13** (RegistryValue Set) ile `HKCU\...\Classes\CLSID\...\InprocServer32` yazımlarını yakala; ya da güvenlik logunda **Event 4657** (registry value modified) izle; ya da yukarıdaki gerçek Sigma kurallarında olduğu gibi `TreatAs` subkey'ine yazımı (`9b0f8a61-91b2-464f-aceb-0527e0a45020` — *Potential COM Object Hijacking Via TreatAs Subkey*) veya `.*\shell\open\command` anahtarlarının silinmesini (`96f697b0` — *Removal of Potential COM Hijacking Registry Keys*, `attack.t1112`) alarma bağla. Doğru başlangıç noktaları — ama tek başlarına sahada ya kör kalır ya da seni false positive selinde boğar. Değer buradan sonra başlıyor.

---

## 2. Naif tespit neden yetmez (değer burada başlar)

**Birinci sorun: kapsam yanlışı.** "InprocServer32 yazımını izle" kulağa net gelir ama HKCU altındaki `Software\Classes\CLSID` ağacı meşru trafikle dolu. Her kullanıcı profili kurulumu, her .NET uygulaması per-user COM kaydı, her tarayıcı eklentisi, her Office add-in buraya yazar. Ham "InprocServer32 SetValue" kuralı bir kurumsal ortamda günde binlerce olay üretir. Analist ilk hafta kapatır (mute eder), ikinci hafta kuralı devre dışı bırakır. Tespitin "çalışıyor" görünüp aslında ölmesinin klasik yolu budur.

**İkinci sorun: registry sinyalinin görünmezliği.** Sysmon Event 13/12 (registry) **varsayılan Sysmon yapılandırmasında COM anahtarlarını kapsamaz** — SwiftOnSecurity/Olaf config'lerinde bile CLSID ağacı seçici include edilir, tüm `Software\Classes` değil. Güvenlik logu tarafında Event 4657 ise **"Audit Registry" alt kategorisi + ilgili registry anahtarına SACL** olmadan hiç doğmaz. Yani birçok kurumda bu olaylar **hiç loglanmıyor**; kural SIEM'de "hiç tetiklenmedi, demek ki temiziz" diye yanlış güven veriyor. Sıfır alarm = sıfır görünürlük, sıfır tehdit değil.

**Üçüncü sorun: teknik tek anahtardan ibaret değil.** Naif kural sadece `InprocServer32` DLL hijack'ine odaklanır. Ama saldırgan `TreatAs` ile CLSID'yi başka bir CLSID'ye yönlendirebilir (dosyaya hiç DLL yazmadan!), `LocalServer32` ile bir EXE'ye işaret edebilir, ya da CLSID hijack'i yerine **shell komut hijack'i** (`shell\open\command`) yapabilir. Yukarıdaki `TreatAs` Sigma kuralının ayrı yazılmış olması tam da bu yüzden — tek anahtara bakan kural diğer varyantı görmez.

**Dördüncü sorun: yeni nesil DCOM/COM yanal hareket.** 2025 tarihli BitlockMove (`baaupdate.exe`, `BDEUILauncher` CLSID `ab93b6f1-...`) ve SpeechRuntimeMove (`SpeechRuntime.exe`) kuralları gösteriyor ki COM hijacking artık sadece "registry'ye DLL yaz + bekle" değil; **INTERACTIVE USER olarak yapılandırılmış COM sınıflarını uzaktan tetikleyip kurbanın oturum bağlamında proses doğurmak** için kullanılıyor. Bu senaryoda registry yazımı hiç olmayabilir — sinyal proses ağacında (`ParentImage: \baaupdate.exe` → `\cmd.exe`) ya da DLL yükleme yolunda (public-writable dizinden DLL load) beliriyor. Sadece registry izleyen bir program bunu tamamen kaçırır.

Özetle: naif kural ya loglanmayan bir şeyi izler (görmez), ya gürültülü bir şeyi izler (boğulur), ya da tekniğin tek dilimine bakar (atlanır). Gerçek tespit bunların hepsini aynı anda çözmek zorunda.

---

## 3. Korelasyon zinciri (asıl değer — Google tek sayfada VERMEZ)

COM hijacking tek başına **zayıf sinyaldir**. `InprocServer32` yazımı görmek "belki kötü, belki bir uygulama kurulumu" demek. Onu **yüksek güvenli** tespite çeviren şey, tek olayı değil çok-aşamalı deseni yakalamaktır. Sahada gerçekten işe yarayan korelasyon zincirleri şunlar:

**Zincir A — Kalıcılık kurulumu (klasik hijack):**
```
[A] Registry Set: HKCU\Software\Classes\CLSID\{CLSID}\InprocServer32
    → değer, kullanıcının yazabildiği bir yola işaret ediyor
       (\AppData\, \ProgramData\, \Users\Public\, \Temp\)
        ↓ (dakikalar–saatler içinde)
[B] Aynı CLSID başka bir prosesçe çözümlenip o DLL Image-Load ediliyor
    (Sysmon Event 7: ImageLoaded = az önce yazılan yol,
     yükleyen proses explorer.exe / bir Office ürünü / taskhostw.exe)
        ↓
[C] O prosesten anormal çocuk: rundll32/regsvr32/network beacon
```
Buradaki altın kural: **A olayındaki dosya yolu ile B olayındaki `ImageLoaded` yolunun birebir eşleşmesi**. Kurulum (meşru) senaryosunda DLL genelde `Program Files` altına yazılır ve imzalıdır; hijack'te kullanıcı-yazabilir dizine yazılır ve imzasız/yeni-oluşturulmuş bir dosyadır. "Kullanıcı-yazabilir yola işaret eden InprocServer32 + kısa süre içinde aynı yolun ImageLoad edilmesi + yükleyen prosesin imzalı bir sistem/Office prosesi olması" — bu üçlü, tek başına registry alarmından kat kat yüksek güven verir.

**Zincir B — DCOM ile yanal hareket (BitlockMove deseni):**
```
[A] Host-1'de: anormal DCOM/RPC aktivitesi Host-2'ye
    (Event 4624 Logon Type 3, ardından RPC/DCOM çağrısı;
     network tarafında 135/tcp + yüksek portlar)
        ↓
[B] Host-2'de: baaupdate.exe (veya SpeechRuntime.exe) başlıyor
    — bu binary'nin normalde bir parent'ı yoktur, çocuğu hiç olmaz
        ↓
[C] baaupdate.exe → cmd.exe / mshta.exe / cscript.exe / bitsadmin.exe
    (gerçek Sigma 9f38c1db bunu yakalar)
    VEYA baaupdate.exe public-writable dizinden DLL load ediyor
    (gerçek Sigma 6e8fe0a8)
```
Kritik bağ: **farklı host + tetikleyici uzaktan geldi + normalde yaprak-proses olan bir binary birden ebeveyn oldu**. Tek bir host'ta "baaupdate.exe cmd doğurdu" görmek şüphelidir; ama bunu "az önce bu host'a Host-1'den DCOM bağlantısı geldi" ile birleştirince yanal hareket neredeyse kesinleşir. SOC'da bu iki sinyali ayrı ekipler (network vs endpoint) izlerse zincir hiç kurulamaz — korelasyonun asıl değeri sinyalleri **coğrafi ve zamansal** olarak birleştirmekte.

**Zincir C — Silme ile iz temizleme (`96f697b0` deseni):**
Bir tehdit aktörü işini bitirdikten sonra `.*\shell\open\command` veya CLSID anahtarlarını **siler** (Event 4657 / Sysmon Event 12 DeleteValue). Tek başına "registry key silindi" gürültüdür. Ama **"aynı anahtar N gün önce anormal bir prosesçe yazıldı → şimdi siliniyor"** deseni tespit-değeri yüksektir: kurulum + temizlik aynı anahtar üzerinde = bilinçli operasyon. Bu yüzden registry write ve delete olaylarını **anahtar-yolu bazında birbirine bağlamak** (state tutmak) tek olaya bakmaktan çok daha güçlüdür.

**Zincir D — CLSID seçim mantığından tespit (aktörün zayıf noktası):**
Aktör "canlanma garantisi" için sık-yüklenen bir CLSID seçmek zorunda. Bu bir zayıflık: ortamda **hangi CLSID'lerin normalde HKLM'de tanımlı olup HKCU'da tanımlı OLMADIĞINI** biliyorsan, birden HKCU tarafında beliren "zaten HKLM'de var olan bir CLSID" güçlü sinyaldir. Çünkü meşru uygulama kendi yeni CLSID'sini kaydeder; **var olan bir makine-düzeyi CLSID'yi kullanıcı düzeyinde gölgelemek** neredeyse hep kötü niyetlidir.
```
[A] HKCU\Software\Classes\CLSID\{X}\InprocServer32 yazıldı
[B] Aynı {X} HKLM\Software\Classes\CLSID\{X} altında ZATEN kayıtlı
        → "gölgeleme" (shadowing) tespiti: HKCU kaydı HKLM'i override ediyor
```
Bu deseni yakalamak için envanterinde HKLM CLSID tablosunu tutman (ya da tetiklenme anında karşılaştırman) gerekir — Google'da hazır kural yoktur, ortam bilgisiyle üretilir.

Bu zincirlerin ortak dersi: COM hijacking'i tek satırlık bir kuralla değil, **kurulum → tetiklenme → sonuç** (ya da **uzak tetik → anormal proses → payload**) üçlemesini zamansal pencerede birleştiren bir korelasyon mantığıyla yakalarsın. SIEM'de bu ya bir `stats`/`transaction` (Splunk), ya EQL sequence (Elastic), ya da bir korelasyon kuralı (Sentinel Analytics) demektir. Ve unutma: zincirin **her halkası tek başına düşük değerli** ama birleştikçe güven üstel olarak artar — bu yüzden ham olayları kapatmak yerine düşük öncelikli kuyrukta **korelasyon için canlı** tutarsın.

---

## 4. False positive gerçeği ve triage yargısı

Bu alarmı gerçek ortamda meşru üreten şeyleri bilmeden hiçbir COM hijacking tespiti üretime dayanamaz. En sık gerçek FP kaynakları:

- **Yazılım kurulum/güncellemeleri:** MSI kurucular, `.NET` runtime kayıtları, Office/Adobe/Chrome güncellemeleri sürekli `HKCU\...\Classes\CLSID\...\InprocServer32` yazar. Özellikle **ClickOnce** ve per-user MSI kurulumları bunu binlerce kez yapar.
- **SCCM / Intune / dağıtım araçları:** Uygulama dağıtımı sırasında COM kayıtları normaldir. `ccmexec.exe`, `TiWorker.exe` (Windows Modules Installer), `msiexec.exe` bağlamındaki yazımlar neredeyse hep meşru.
- **Yedekleme/EDR/vuln scanner ajanları:** Kendi COM bileşenlerini kaydeder; ayrıca **vuln scanner'lar** (kimlik doğrulamalı tarama) registry'yi tarar ve bazı ortamlarda geçici anahtarlar oluşturur.
- **Roaming profiller / VDI:** Golden image + profil katmanlama (FSLogix, App Layering) her oturum açılışında CLSID ağacını "yeniden yazıyor" gibi görünür. VDI ortamında ham registry kuralı tam bir kabus.
- **Geliştirici makineleri:** Visual Studio, `regsvr32` ile COM test kaydı, PowerShell ISE — geliştiriciler sürekli COM kaydeder/siler.

Kıdemli analist gerçek/gürültü ayrımını **tek alana bakarak değil, bağlamı okuyarak** yapar. Triage'da bakılacak sıra:

1. **Yükleyen/yazan proses kim?** `msiexec.exe`, `TiWorker.exe`, imzalı bir installer → çok muhtemel meşru. `powershell.exe`, `rundll32.exe`, `wscript.exe`, imzasız bir binary, ya da `explorer.exe`'nin çocuğu bir LOLBin → şüphe yükselir.
2. **Yazılan değer nereyi gösteriyor?** `Program Files\...` altında imzalı DLL → gürültü. `\AppData\Local\Temp\`, `\Users\Public\`, `\ProgramData\` altında **yeni oluşturulmuş, imzasız** bir dosya → gerçek şüphe. Yolun imza durumu (Authenticode) tek başına en ayırt edici alandır.
3. **Hangi CLSID?** Bilinen bir uygulamanın CLSID'si mi, yoksa **sık otomatik-yüklenen bir "abuse-prone" CLSID** mi (Explorer/shell tarafından çağrılanlar)? Aktör her zaman "canlanma garantisi" olan CLSID'leri seçer.
4. **Zamansal/coğrafi bağlam:** Bu makinede aynı saat içinde başka bir şüpheli olay var mı? Kullanıcı normalde bu saatte aktif mi? Aynı CLSID başka host'larda da mı yazıldı (kampanya)?

**Çok alarmlı durumda önce neye bakılır?** Önceliklendirme kuralım: (a) **imza + yol** — imzasız + kullanıcı-yazabilir yol en üste çıkar; (b) **prosessel bağlam** — LOLBin/script motoru yazımları öne; (c) **korelasyon derecesi** — Bölüm 3'teki zincirin ikinci halkası (ImageLoad ya da anormal çocuk proses) da gerçekleşmiş mi? Zincirin ikinci halkası doğrulanmış bir alarm, tek registry olayından **her zaman** önce incelenir. Yalın "registry yazıldı" olayları, yalnızca başka bir sinyalle eşleşince yükselen düşük öncelikli kuyruğa gider.

Sahadan pratik bir yargı: bir COM hijacking alarmı **hiçbir zaman tek başına "kesin ihlal" değildir**. Ya "kurulum gürültüsü" ya da "bir zincirin ilk halkası"dır. Analistin işi hangisi olduğunu 60 saniyede kestirmek — ve bunun için önceden **baseline** (bu ortamda hangi CLSID'ler normalde kim tarafından yazılır) çıkarmış olmak şart. Baseline yoksa triage yoktur, sadece tahmin vardır.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Kural dokümanlarının **yazmadığı** kaçınma yolları ve her birine ikinci-derece tespit:

**Kaçınma 1: `InprocServer32` yerine `TreatAs` kullan.** Saldırgan diske hiç DLL yazmaz; sadece hedef CLSID'yi kendi kontrolündeki başka bir (zaten kayıtlı) CLSID'ye `TreatAs` ile yönlendirir. Diskte yeni dosya arayan EDR bunu kaçırır.
→ **Karşı-tespit:** `TreatAs` subkey yazımını ayrı izle (gerçek Sigma `9b0f8a61`). Ama asıl değer: **`TreatAs` hedefinin nereye çözüldüğünü** takip et — yönlendirilen CLSID kullanıcı-yazabilir bir DLL'e mi çıkıyor? İki-adımlı yönlendirmeyi çözmeden `TreatAs` tek başına anlamsız görünebilir.

**Kaçınma 2: Yolu yasal görünen bir dizine yaz.** `AppData\Local\Microsoft\` gibi "Microsoft" içeren ama kullanıcı-yazabilir yollara DLL koy. Analist "Microsoft" görüp geçebilir.
→ **Karşı-tespit:** Yol string'ine değil, **Authenticode imza durumuna + dosyanın oluşturulma zamanına** bak. "Microsoft" klasörü altında ama **imzasız ve son 10 dakikada oluşmuş** bir DLL, yolundan bağımsız kırmızı bayrak. Yol-tabanlı allowlist yerine imza-tabanlı mantık kur.

**Kaçınma 3: Meşru bir DLL'i sideload et (imzalı ama savunmasız).** Aktör kendi imzasız DLL'ini yazmak yerine, imzalı-ama-hijack'lenebilir bir ikili + yanına kötü bir dependency DLL bırakır (search-order hijack ile birleşik).
→ **Karşı-tespit:** ImageLoad olaylarında **imzalı proses + imzasız DLL aynı anormal dizinden** desenini yakala. Ayrıca beklenmedik parent-child (Bölüm 3, BitlockMove örneği) her zaman ikinci-derece sinyaldir.

**Kaçınma 4: Registry'yi hiç kullanma — DCOM'u doğrudan tetikle.** BitlockMove/SpeechRuntimeMove sınıfı: INTERACTIVE USER COM sınıfını uzaktan tetikle, kurbanın oturumunda proses doğur. Registry kuralı hiç tetiklenmez.
→ **Karşı-tespit:** **Proses-soyağacı tespiti** devreye girer: `baaupdate.exe` / `SpeechRuntime.exe` gibi normalde yaprak olan binary'lerin **herhangi bir çocuk doğurması** (gerçek Sigma `9f38c1db`, `78f10490`). Bunu network-yan DCOM (135/tcp + Logon Type 3) ile korele et. Registry kör olsa bile proses+network zinciri yakalar.

**Kaçınma 5: İz temizle — kurduğun anahtarı sil.** İş bitince `InprocServer32` / `shell\open\command` sil (Event 4657 delete).
→ **Karşı-tespit:** Delete olaylarını izlemek (gerçek Sigma `96f697b0`) + **aynı anahtarın önceki write olayıyla eşleştirme**. "Yakın zamanda anormal yazılmış anahtarın silinmesi" tek başına silmeden çok daha güçlü sinyal. Ayrıca **loglar merkeze anlık gönderiliyorsa** (forward), aktör diskteki registry'yi silse de SIEM'deki write kaydı kalır — bu yüzden gerçek-zamanlı log iletimi karşı-tespitin bel kemiği.

**Kaçınma 6: Sysmon/audit config'in kör noktasına yaz.** Aktör hangi CLSID ağacının izlenmediğini bilir (örn. `WOW6432Node` altındaki 32-bit CLSID görünümü, ya da config'in include etmediği bir alt ağaç).
→ **Karşı-tespit:** Config kapsamını **hem 64-bit hem `WOW6432Node`** görünümünü içerecek şekilde genişlet; ve registry kör noktasını proses/ImageLoad katmanıyla telafi et. Tek katmana güvenme — savunma derinliği tam olarak bunun için.

Kedi-fare özeti: her registry-tabanlı kaçınmanın karşısına bir **davranışsal/prosessel** ikinci katman koyarsın; her diske-yazma kaçınmasının karşısına **imza+zaman** yargısı koyarsın. Aktör bir katmanı kör edebilir ama üçünü birden aynı anda kör etmek zordur. Tespitin dayanıklılığı katman sayısından gelir, tek "mükemmel kuraldan" değil.

---

## 6. SIEM / saha gerçeği

**Alan eşleme (field mapping) tuzakları:**
- Sysmon **Event 13** = `RegistryValue Set`, **Event 12** = `Object Create/Delete` (anahtar oluşturma/silme), **Event 14** = `Rename`. COM hijacking'de asıl sinyal genelde 13 (InprocServer32 değeri) + 12 (delete/iz temizleme). Bu ikisini karıştırırsan silme senaryosunu kaçırırsın.
- Sysmon registry olaylarında yol **kısaltılmış hive önekleriyle** gelir: `HKLM` yerine `\REGISTRY\MACHINE\`, `HKCU` yerine `\REGISTRY\USER\<SID>\`. Kuralında düz `HKCU\Software\Classes` ararsan **hiç eşleşmez**. Bu klasik "kural doğru görünüyor ama hiç tetiklenmiyor" tuzağı. Ya normalize et ya `\REGISTRY\USER\...\Classes\CLSID\` desenini kullan.
- Güvenlik logu **Event 4657** için `ObjectName` alanı yolu tutar, ama bu olay **yalnızca ilgili anahtara SACL + "Audit Registry" alt kategorisi Success/Failure** açıksa doğar. Varsayılan denetim politikasında **kapalıdır**. `auditpol /get /subcategory:"Registry"` ile doğrula; `Object Access → Audit Registry` açık değilse Event 4657 hiç gelmez ve registry-tabanlı tüm kuralların ölüdür.

**Varsayılan loglanmayan şeyler (şart olan config):**
- **Sysmon:** COM CLSID ağacını registry include listesine eklemelisin. Çoğu popüler config `Software\Classes\CLSID` yazımlarını **seçici** kapsar; INTERACTIVE USER / DCOM yanal hareket için ayrıca **ImageLoad (Event 7)** ve **ProcessCreate (Event 1) with ParentImage** logging şart. ImageLoad olayları hacimlidir; kurumlar performans için kapatır — ama BitlockMove sınıfı tespit için ImageLoad olmadan körsün.
- **Proses oluşturma:** `4688` (güvenlik logu) ya da Sysmon Event 1. `4688` için **"Include command line" (ProcessCreationIncludeCmdLine_Enabled)** GPO'su açık olmalı, yoksa komut satırı gelmez ve `baaupdate.exe → cmd.exe /c ...` tespiti anlamsızlaşır.
- **DCOM/yanal hareket:** Network tarafı için `4624` (Logon Type 3), RPC/DCOM için 135/tcp + dinamik yüksek portlar. Bunlar ayrı log kaynağı; endpoint ekibiyle network ekibinin logları aynı SIEM'de birleşmiyorsa Zincir B hiç kurulamaz.

**Platform farkları (tuning gerçeği):**
- **Splunk:** Registry olaylarını `Registry` data model'e / CIM'e map et; korelasyonu `transaction`/`stats by` ile kur. Zincir A için: `InprocServer32` write ile ImageLoad'ı **dosya yolu** üzerinden `stats values(EventCode) by TargetImagePath` ile birleştir. Dikkat: Sysmon `Details` alanı serbest metin; DLL yolunu regex ile çıkarman gerekir, alan olarak hazır gelmez.
- **Microsoft Sentinel:** Sysmon'u `Event`/`SecurityEvent` tablosunda ya da AMA ile `DeviceRegistryEvents` (Defender XDR) tablosunda ararsın. **En büyük tuzak:** Sentinel'de aynı veriyi iki kaynak (Sysmon + Defender) farklı şemayla getirebilir; `RegistryKey`/`RegistryValueData` alan adları Defender XDR ile Sysmon arasında farklı. KQL'de `DeviceRegistryEvents | where RegistryKey has "InprocServer32"` yazarsan Sysmon-only ortamda hiç sonuç almazsın. Korelasyon için `join`/`materialize` + `bin(TimeGenerated, 10m)` zaman penceresi.
- **Elastic:** EQL **sequence** COM zincirleri için en doğal araç: `sequence by host.id with maxspan=10m [registry where registry.path : "*InprocServer32*"] [library where dll.path : registry.data.strings]` mantığı. Elastic'te `registry.data.strings` normalize edilmiş gelir, Splunk'a göre burada avantajın var. Ama ECS alan adlarına (`registry.path`, `dll.path`, `process.parent.name`) sadık kal; ham Sysmon alan adlarını (`TargetObject`) EQL'de kullanamazsın.

**Tuning gerçeği:** Üretime çıkmadan önce mutlaka **2-4 haftalık baseline** topla; ortamındaki meşru `InprocServer32` yazan prosesleri (`msiexec`, `TiWorker`, `ccmexec`, imzalı installer'lar) allowlist'e al — ama **allowlist'i proses+imza üzerinden yap, yol üzerinden yapma** (Kaçınma 2'yi hatırla). VDI/roaming profil ortamında registry kuralını ya oturum-açılış penceresinde bastır ya da tamamen davranışsal katmana (ImageLoad + proses ağacı) kaydır. Ve en önemli saha kuralı: **sıfır alarm üreten bir COM hijacking kuralı "temiz ortam" değil, "kör config" demektir** — önce test EVTX'iyle (yukarıdaki regression `9b0f8a61-...evtx` gibi) kuralın gerçekten ateşlediğini doğrula, sonra üretime güven. Bir kuralın canlı olduğunu bilmenin tek yolu onu kontrollü olarak tetikleyip SIEM'de gördüğünü teyit etmektir; "hiç alarm gelmedi" asla teyit değildir.
