# Remote Registry Abuse — Tespiti

> Saha notu. Uzaktan registry erişimi (Remote Registry / MS-RRP) hem meşru yönetimin belkemiği hem de saldırganın en sessiz keşif ve yatay hareket kanallarından biridir. "winreg pipe'ını yakala, bitir" diye anlatılır; oysa bu konunun bütün değeri, meşru trafiğin devasa gürültüsü içinde saldırgan niyetini ayırmakta ve tek olayın neden yalan söylediğini bilmektedir. Aşağıda naif tespitten başlayıp gerçek ortamda neyin bozulduğuna, kıdemli bir analistin ekranda neye baktığına kadar iniyorum.

---

## 1. Özet: saldırı + naif tespit

Uzaktan registry erişimi, Windows'un `RemoteRegistry` servisi ve arkasındaki **MS-RRP** (Remote Registry Protocol, RPC arayüz UUID'si `338cd001-2244-31f1-aaaa-900038001003`) üzerinden çalışır. Uzaktaki bir istemci, hedef makinenin `IPC$` paylaşımı üzerinden `\winreg` adlı named pipe'a bağlanır, `OpenHKLM`/`OpenHKU` gibi çağrılarla bir kök anahtar handle'ı alır, ardından `RegQueryValue`, `RegEnumKey`, `RegEnumValue`, `RegSetValue`, `RegCreateKey`, `RegSaveKey` gibi opnum'larla değer okur/yazar/sıralar. Saldırganın bu kanaldan yaptığı üç ana iş vardır:

- **Keşif (discovery):** Uzaktan HKLM içindeki kurulu yazılım, servis konfigürasyonu, AV/EDR anahtarları, `HKLM\SYSTEM\CurrentControlSet\Services` altını, `winlogon`, RDP ayarları, hatta LSA sırlarının yaşadığı yolları okumak. Parola dökümü için `SAM`, `SECURITY`, `SYSTEM` hive'larını uzaktan `RegSaveKey` ile diske çıkarıp çekmek (klasik credential access varyantı).
- **Yatay hareket / kod çalıştırma (lateral movement):** Uzaktan `Run`/`RunOnce`, servis `ImagePath`, `Image File Execution Options` (IFEO), COM anahtarları, `AppInit_DLLs` gibi yolları **yazarak** hedefte kod tetiklemek. Bu, T1112 (Modify Registry) ile T1021 yatay hareketin kesiştiği yerdir.
- **Savunma zayıflatma (defense impairment):** Defender/EDR anahtarlarını uzaktan devre dışı bırakmak, `LocalAccountTokenFilterPolicy` yazıp UAC uzaktan kısıtlamasını kaldırmak, `RestrictAnonymous`/`RestrictRemoteSAM` değerlerini değiştirmek.

Naif tespit tarafında herkesin gösterdiği birkaç sabit nokta var. Verilen gerçek Sigma kuralları bu naif katmanı iyi temsil ediyor:

- **`68fcba0d-...` — Remote Registry Management Using Reg Utility:** Windows Security günlüğünde **EventID 5145** (a network share object was checked) satırlarında `RelativeTargetName|contains: '\winreg'` arar; yani `IPC$` üzerinden `\winreg` pipe'ına yapılan detaylı dosya paylaşım erişimini yakalar. `filter_main` ile bilinen yönetici iş istasyonlarının IP'lerini (`%Admins_Workstations%`) dışlar. Mantık basit: `\winreg` erişimi olan, ama yönetici iş istasyonundan **gelmeyen** her şey şüpheli.
- **`52d8b0c6-...` / `021310d9-...` — First Time Seen Remote Named Pipe:** İlki Windows Security **EventID 5145**, `ShareName: '\\*\IPC$'` ile, ikincisi Zeek `smb_files` üzerinden `path: '\\*\IPC$'` ile IPC$ üzerinde açılan named pipe'ları izler; `winreg`, `samr`, `lsarpc`, `svcctl`, `srvsvc` gibi bilinen pipe'ları filtreleyip **ilk kez görülen** pipe'a alarm üretir. Buradaki fikir winreg'i yakalamak değil, winreg dahil bilinen pipe'ların dışına çıkan anomaliyi görmek.
- **`d8ffe17e-...` — Remote Registry Recon** ve **`35c55673-...` — Remote Registry Lateral Movement:** İkisi de `rpc_firewall` ürününden (Zero Networks RPC Firewall), **EventID 3**, `EventLog: RPCFW`, `InterfaceUuid: 338cd001-2244-31f1-aaaa-900038001003` üzerinden gelir. Recon kuralı belirli okuma opnum'larını (`6,7,8,13,18,19,21`) filtreleyerek keşif desenini, Lateral Movement kuralı ise `OpNum: 6` (OpenHKLM sınıfı handle açma / yazma yolu) üzerinden kod çalıştırma potansiyelini işaretler.

Bu kuralların hepsi doğru ve gereklidir. Sorun, tek başına hiçbirinin "kötü niyetli uzaktan registry erişimi oldu" demeye yetmemesidir. Naif tespit ya bir **imza** (winreg pipe adı) ya bir **protokol olayı** (MS-RRP opnum) arar; oysa registry abuse, meşru yönetimle bit bit aynı görünen bir **davranıştır**.

---

## 2. Naif tespit neden yetmez

**Birinci kör nokta: MS-RRP kanalı meşru altyapının bel kemiğidir.** SCCM/ConfigMgr envanteri, GPO uygulaması, vulnerability scanner'lar (Nessus/Qualys/Tenable authenticated scan tam da uzaktan HKLM okur), yedekleme ajanları, SCOM/monitoring, hatta `psexec`/servis yönetimi araçları — hepsi doğal olarak `\winreg` pipe'ı açar ve HKLM altını uzaktan tarar. Kurumsal bir ortamda EventID 5145 `\winreg` erişimi günde on binlerce satır üretir. Gerçek saldırgan bu denizde bir damladır. `68fcba0d` kuralının `%Admins_Workstations%` filtresi bu yüzden kritik ama aynı zamanda kuralın en kırılgan yeri: envanter/scanner sunucuları yönetici iş istasyonu listesinde değildir, dolayısıyla ya sürekli alarm üretirler ya da onları da whitelist'e ekleyip kör noktayı büyütürsünüz.

**İkinci kör nokta: en ayırt edici alan çoğu ortamda hiç loglanmaz.** Bir uzaktan registry erişimini "keşif" mi "yazma/kod çalıştırma" mı olduğunu ayıran şey **opnum**'dur — okuma mı (`RegQueryValue`) yoksa yazma mı (`RegSetValue`/`RegCreateKey`/`RegSaveKey`). Ama bu ayrımı sadece **RPC Firewall** (`RPCFW` EventID 3) verir. Standart Windows denetiminde opnum yoktur. EventID 5145 size sadece "biri `\winreg` pipe'ına erişti" der; ne okudu, ne yazdı, hangi anahtara dokundu — hiçbiri yok. Yani `d8ffe17e` ve `35c55673` kurallarının dayandığı opnum granülaritesi, RPC Firewall kurmadıysanız (ki çoğu ortamda kurulu değildir) **elinizde yoktur**. Bu, tespit tasarımının en sık gözden kaçan gerçeğidir: kuralın demirlediği alan, sizin log kaynağınızda mevcut olmayabilir.

**Üçüncü kör nokta: RegSaveKey ile hive çıkarma, "registry değişikliği" gibi görünmez.** Saldırgan SAM/SECURITY/SYSTEM hive'larını uzaktan `RegSaveKey` ile hedefin diskine (veya bir ağ yoluna) kaydettiğinde, bu bir **okuma-ağırlıklı** işlemdir; registry'ye yazmaz, bir dosya üretir. `Sysmon EventID 13` (registry value set) tetiklenmez, çünkü değer yazılmıyor. Sadece pipe açılışı (5145 `\winreg`) ve ardından ortaya çıkan bir dosya (`Sysmon EventID 11 file_create`, örn. `\Windows\Temp\sam.save`) görünür — ve bu ikisi çoğu SIEM'de aynı korelasyon penceresinde birbirine bağlı değildir.

**Dördüncü kör nokta: EDR uzaktan registry'yi çoğu zaman "göremez".** Endpoint EDR'ları lokal `RegSetValue` API çağrılarını kancalar. Ama uzaktan gelen MS-RRP isteği, hedefte `svchost.exe` (RemoteRegistry servisi, `-k localService` altında) tarafından işlenir. EDR telemetrisinde değişikliği yapan process olarak **`svchost.exe`** görünür — kaynak makine, kaynak kullanıcı, uzaktan olduğu bilgisi çoğu üründe zayıf doldurulur veya hiç doldurulmaz. Yani lokal registry monitoring, uzaktan yazmayı yanlış attribute eder; "svchost bir Run anahtarı yazdı" satırı, ne kadar kritik olursa olsun, kaynağı olmadan triage edilemez.

**Beşinci kör nokta: "ilk kez görülen pipe" mantığının doğal zayıflığı.** `52d8b0c6`/`021310d9` kurallarının fikri güzel — winreg dahil bilinen pipe'ları filtreleyip yeni olana bakmak. Ama `winreg` zaten **bilinen** listesinde olduğu için, saldırgan standart winreg pipe'ını kullandığında bu kural **hiç ötmez**. Bu kural winreg abuse'u değil, alışılmadık/özel pipe'ları yakalar; registry senaryosunda ancak baseline'a yeni giren bir makine-pipe çiftinde işe yarar. Yani isim bazlı "first seen" mantığı, saldırgan meşru pipe adını kullandığı anda kör olur.

Değer buradan başlıyor: uzaktan registry abuse'u tespit etmek için tek olayı değil, olaylar arasındaki **ilişkiyi** — kim, nereden, hangi anahtara, hemen ardından ne yaptı zincirini — kurmak gerekir.

---

## 3. Korelasyon zinciri (asıl değer)

Tek bir `\winreg` erişimi (5145) veya tek bir RPCFW opnum olayı zayıf sinyaldir. Onu yüksek güvene çeviren şey, saldırının **zorunlu olarak** ürettiği çok aşamalı ve çok bağlamlı desendir. Deseni üç eksende bağlayın: **kimlik/kaynak** (kim, hangi IP), **hedef anahtar** (ne okundu/yazıldı), **zaman penceresi** (ardışıklık ve hız).

**Somut zincir — SAM hive uzaktan çıkarma (credential access):**

1. **A (kanal açılışı):** Hedef `SRV05` üzerinde **EventID 5145**, `ShareName: \\*\IPC$`, `RelativeTargetName` içinde `\winreg`, kaynak IP bir kullanıcı iş istasyonu (`10.20.4.66`) — yönetici subnet'i değil. `68fcba0d` kuralı burada `filter_main` dışında kaldığı için tetiklenir.
2. **B (yazma/kaydetme — farklı bağlam):** **Kısa pencere içinde** (saniyeler), aynı oturumda RPC Firewall varsa `RPCFW` EventID 3, InterfaceUuid `338cd001-...`, `OpNum: 6` (handle açma → yazma yolu) görünür; RPC Firewall yoksa dolaylı iz olarak hedefte **Sysmon EventID 11**, `sam.save`/`security.save`/`system.save` benzeri bir dosya oluşumu.
3. **C (dışa taşıma):** Aynı kaynak IP, kısa süre sonra **EventID 5145** ile bu kez `C$` veya `ADMIN$` paylaşımından `.save` dosyasını okur, ya da `Sysmon EventID 3` (network) ile aynı kutu dışarı SMB/HTTP bağlantısı kurar.

Tek başına adım 1 günde on binlerce kez olur. Ama **"yönetici-olmayan kaynaktan `\winreg`" + kısa pencerede "SAM/SYSTEM hive dosyası oluşumu" + "aynı kaynağın hive dosyasını geri okuması"** üçlüsü, meşru envanter taramasının asla üretmediği bir imzadır. Envanter scanner'ı HKLM okur ama hive **kaydetmez** ve `.save` dosyası geri **çekmez**.

**Somut zincir — uzaktan persistence yazma + tetik (lateral movement):**

1. **A:** `SRV05` üzerinde 5145 `\winreg`, kaynak alışılmadık bir makine.
2. **B (yazma):** Kısa pencerede hedefte **Sysmon EventID 13** (registry value set), yol `HKLM\...\CurrentVersion\Run\` veya bir servis `ImagePath`'i ya da `Image File Execution Options\<exe>\Debugger`. Değişikliği yapan process **`svchost.exe`** (RemoteRegistry) — lokal bir kullanıcı process'i değil. İşte ayırt edici: normalde bir Run anahtarını yazan şey installer/kullanıcı process'idir; `svchost` (localService) altından Run/IFEO yazımı uzaktan-tetikli olduğunu gösterir.
3. **C (icra):** Yazılan yola bağlı olarak dakikalar/reboot sonrası hedefte yeni process (**Sysmon EventID 1**), parent zinciri `winlogon`/`services.exe`/beklenmedik bir yol; ya da anlık icra için aynı kaynağın hemen ardından `svcctl` (servis oluşturma, EventID 7045 System log) veya `\atsvc` (görev) pipe'ına geçmesi.

Buradaki yargı: **B'deki `svchost` kaynaklı hassas anahtar yazımı, A'daki uzaktan pipe açılışıyla aynı zaman/kimlik penceresinde eşleşiyorsa**, tek bir Sysmon 13'ün asla veremeyeceği güveni elde edersiniz. Korelasyon anahtarı: hedef host + `svchost` yazımı + son N saniyede aynı host'ta yönetici-olmayan kaynaktan `\winreg` 5145.

**Zincirin gücü şudur:** saldırgan tek adımı gizleyebilir (isim değiştirir, opnum'u karıştırır, hive'ı bellekte tutar), ama **kanal → hassas anahtar → ardışık icra** zincirinin tamamını aynı anda gizleyemez. Değer, tek imzayı değil, bu zorunlu ardışıklığı avlamaktır.

---

## 4. False positive gerçeği ve triage yargısı

Uzaktan registry, meşru dünyada **sürekli** çalışır. Bir SOC lead'i olarak alarm geldiğinde önceliklendirme sıramı şudur:

**Öncelik sırası (analist zihni):**

1. **Kaynak kim?** İlk baktığım alan kaynak IP/hesap. Bilinen scanner (Nessus/Qualys/Tenable service account), SCCM site sunucusu, yedekleme ajanı IP'si mi? Bunlar bilinen bir CMDB/asset listesinden doğrulanır. Kaynak bilinen envanter altyapısıysa ve hedef seti geniş+düzenliyse (her gece aynı saat, aynı port deseni) → büyük olasılıkla FP, ama körü körüne kapatma: scanner **hesabının** ele geçirilip aynı kanaldan farklı bir şey yapması en sinsi senaryodur.
2. **Hedef anahtar ne?** Envanter, `Uninstall`, `CurrentVersion`, servis konfig okur — bunlar rutin. Ama `SAM`, `SECURITY`, `SYSTEM` hive'ına dokunma, `Run`/IFEO/`AppInit_DLLs`/`LSA` yazımı, Defender anahtarı değişikliği → asla rutin değil, anında yükselt. RPC Firewall varsa opnum ayrımı (okuma opnum'ları `7,8,13,18,19,21` vs yazma) burada altın değerinde.
3. **Yön: okuma mı yazma mı?** Meşru envaretin %99'u okumadır. `RegSetValue`/`RegCreateKey`/`RegSaveKey` (yazma/kaydetme) FP oranını dramatik düşürür. Okuma alarmlarını volume nedeniyle düşük öncelik, yazma alarmlarını yüksek öncelik yaparım.
4. **Ardışıklık var mı?** `\winreg` sonrası aynı kaynaktan `svcctl`/`\atsvc` pipe'ına geçiş, veya hive dosyası oluşumu, veya yeni servis (7045). Zincir varsa scanner mazereti çöker.

**Klasik FP kaynakları ve mazeretleri:**

- **Vulnerability scanner (authenticated):** Uzaktan HKLM okur, çok host, düzenli takvim. Ayırt edici: **sadece okuma**, hive kaydetmez, persistence yazmaz. Scanner hesabından **yazma** görürseniz alarm.
- **SCCM/ConfigMgr:** Envanter + bazen registry policy yazımı yapar — bu gerçek yazma üretir, en zorlu FP. Mazereti: SCCM'in yazdığı yollar bilinir (`SOFTWARE\Microsoft\SMS`, policy anahtarları), kaynağı site sunucusudur, `Run`/`SAM`/IFEO'ya dokunmaz.
- **Yedekleme/monitoring ajanları:** `SYSTEM` hive'ı okuyabilir (VSS/bootkonfig için). Ayırt edici: yerleşik hesap, sabit kaynak.
- **Yönetici manuel `reg.exe \\host`:** Gerçek yönetici troubleshooting. `68fcba0d` kuralının `%Admins_Workstations%` filtresi tam bunun için. Yönetici jump host dışından gelen manuel reg → soru işareti.

Triage'ın altın kuralı: **kaynak + hedef anahtar + yön** üçlüsünü aynı satırda göremiyorsanız, alarmın önceliğini doğru veremezsiniz. Onun için mühendislikte bu üç alanı korelasyonla tek görünüme getirmek, kuralın kendisinden daha değerlidir.

---

## 5. Kaçınma → karşı-tespit

Saldırgan, yukarıdaki naif kuralların hepsini bildiğini varsayarak hareket eder. Dokümante edilmeyen atlatmalar ve onların ikinci-derece karşı-tespitleri:

**Atlatma 1 — RemoteRegistry servisini kendisi başlatıp bitince durdurmak.** Birçok ortamda `RemoteRegistry` servisi `Manual` (disabled değil) modundadır. Saldırgan `svcctl` üzerinden servisi uzaktan `START` eder, işini yapar, `STOP` eder. Naif "winreg pipe" kuralı işi yakalasa da olay dar bir pencerededir.
- **Karşı-tespit:** `RemoteRegistry` servisinin durum değişikliği. System log **EventID 7036** (service entered running/stopped state) veya **7040** (start type changed). Bir makinede `RemoteRegistry`'nin başlayıp **dakikalar içinde** tekrar durması, üstelik iş saatleri dışında → güçlü sinyal. Bu servisin baseline'da hiç başlamadığı host'larda tek bir 7036 "running" bile dikkat çeker.

**Atlatma 2 — winreg yerine dolaylı registry API'leri.** Saldırgan `winreg` pipe'ına hiç dokunmadan aynı sonucu WMI (`StdRegProv` sınıfı, `root\default` namespace) üzerinden alabilir; WMI DCOM/`IWbemServices` üzerinden gider, `\winreg` pipe'ı **açılmaz**. `68fcba0d` ve first-seen-pipe kuralları tamamen kör kalır.
- **Karşı-tespit:** WMI tarafı ayrı bir telemetri gerektirir — **Microsoft-Windows-WMI-Activity/Operational** logu (EventID 5857/5858/5860/5861), `StdRegProv` metod çağrıları, uzaktan `wmiprvse.exe` kaynaklı registry erişimi. Registry tespitini "sadece winreg pipe" üzerine kurmak, WMI kanalını komple açık bırakır. Kıdemli tasarımda registry abuse tespiti hem MS-RRP hem WMI-Activity kanadını kapsamalıdır.

**Atlatma 3 — opnum karıştırma / okuma kılıfında yazma.** RPC Firewall opnum bazlı kural (`d8ffe17e` okuma opnum'larını filtreler) belirli opnum setlerine bel bağlar. Saldırgan handle açıp (`OpNum 6`) sonra farklı bir opnum ile değer set ederse, sadece okuma opnum'larına bakan recon kuralının filtresi arasından sızabilir; sadece `OpNum 6`'ya bakan lateral movement kuralı ise handle açan her meşru okumada da öter (FP riski).
- **Karşı-tespit:** Opnum'a değil, **handle açma → ardından yazma opnum'u** ardışıklığına bakmak; RPC Firewall olaylarını tek tek değil dizi olarak (aynı bağlantıda open→set) korele etmek. Ayrıca RPC Firewall'ı **audit:true action:block** modunda çalıştırıp (kuralların `definition` alanında tam da bu yazıyor: `"audit:true action:block uuid:338cd001-..."`) hassas opnum'ları bloklamak — tespitten öte önlem.

**Atlatma 4 — LocalAccountTokenFilterPolicy ile UAC uzaktan kısıtını kaldırmak.** Saldırgan uzaktan `HKLM\SOFTWARE\...\System\LocalAccountTokenFilterPolicy = 1` yazarak yerel admin hesaplarının uzaktan tam token'la gelmesini açar; sonrasında her şey "meşru admin" gibi görünür.
- **Karşı-tespit:** Bu **spesifik değerin** yazımına özel Sysmon 13 kuralı — düşük hacimli, çok yüksek sinyalli bir "canary". Bu değer meşru ortamda neredeyse hiç değişmez; tek bir yazım incelemeye değer.

**Atlatma 5 — kaynağı görüş alanı dışına çıkarmak.** Saldırgan uzaktan registry'yi kendi Linux kutusundan `impacket` (`reg.py`, `secretsdump.py`) ile sürer. Kaynak makinede Windows telemetrisi yoktur. Ama **hedef** Windows'tur — 5145, 7036, Sysmon 13/11 hedefte üretilir. Kör nokta yalnızca saldırgan-taraflıdır; savunma tespiti hedefe demirlenmelidir, kaynağa değil.

---

## 6. SIEM / saha gerçeği

**Field mapping ve varsayılan loglanmayanlar — en önemli kısım:**

- **EventID 5145** (Detailed File Share) **varsayılan olarak KAPALIDIR.** `52d8b0c6` ve `68fcba0d` kurallarının `definition` alanı bunu açıkça yazıyor: *"Audit Detailed File Share" advanced audit policy Success/Failure olarak yapılandırılmalı*. Bu politika açık değilse, `\winreg` tabanlı tüm tespitleriniz **hiç veri görmez**. Üstelik 5145 açıldığında hacim devasadır (her IPC$/dosya erişimi bir satır) — birçok kurum performans/depolama nedeniyle onu kapalı tutar. Kural yazmadan önce sorulacak ilk soru: 5145 topluyor muyuz?
- **RPC Firewall (`RPCFW` EventID 3)** üçüncü parti bir üründür (Zero Networks). `d8ffe17e` ve `35c55673` kuralları bunun kurulu ve **tüm process'lere** uygulanmış olmasını şart koşar (`definition`'da yazıyor). Kurulu değilse opnum granülaritesi elinizde **yoktur** — bu iki kuralı kütüphaneye eklemek onları çalışır kılmaz. Saha gerçeği: çoğu ortamda RPC Firewall yoktur, dolayısıyla opnum bazlı ayrım bir hayaldir ve tespit 5145 + Sysmon 13 kombinasyonuna düşer.
- **`RelativeTargetName` vs `ShareName`:** 5145'te `ShareName` `\\*\IPC$` iken, gerçek pipe adı `RelativeTargetName` alanındadır (`winreg`, `svcctl`, `atsvc`...). `68fcba0d` doğru alanı (`RelativeTargetName|contains: '\winreg'`) kullanıyor. `IpAddress` alanı 5145'te genelde dolar (relay'in aksine burada güvenilir) — kaynak korelasyonunun temelidir.
- **Sysmon 13** uzaktan yazmayı yakalar ama `Image` alanı **`svchost.exe`** gösterir; gerçek kaynağı (uzak makine) Sysmon vermez. Uzaklığı ancak aynı host'taki 5145 `\winreg` ile korele ederek kurarsınız.

**Platform farkları:**

- **Splunk:** 5145 hacmi nedeniyle genelde `WinEventLog:Security` içinde ama pahalı; birçok kurum 5145'i indeks dışında tutar. Korelasyon için `transaction` veya `stats ... by dest,src` ile `\winreg` erişimi + kısa pencerede Sysmon 13'ü birleştirmek gerekir. RPCFW verisi custom sourcetype olur.
- **Microsoft Sentinel:** 5145 `SecurityEvent` tablosunda; ama MDE ortamlarında ham 5145 yerine `DeviceEvents`/`DeviceRegistryEvents` tercih edilir. `DeviceRegistryEvents` uzaktan yazımı `InitiatingProcessFileName = svchost.exe` ile gösterir — yine kaynak korelasyonu ayrı `DeviceNetworkEvents` join'i ister. Sentinel'de zincir KQL'de `join kind=inner ... on DeviceName` + `where TimeGenerated between` pencere mantığıyla kurulur.
- **Elastic:** Sysmon registry (EventID 13) `registry.path`, `registry.value` alanlarına normalize edilir (ECS). 5145 `winlog.event_data.RelativeTargetName` altında kalır — ECS'ye tam oturmaz, custom alan gerekir. EQL `sequence by host.name with maxspan=30s` yapısı, "5145 winreg → Sysmon 13 hassas anahtar" zincirini yazmak için en doğal araçtır; SIEM'ler içinde sequence korelasyonu Elastic'te en temizdir.

**Tuning yargısı:** Uzaktan registry tespitini üç katmanlı kurun. (1) **Geniş ama düşük öncelikli** taban: `\winreg` 5145, yönetici-olmayan kaynaktan (`68fcba0d` mantığı) — hacimli, sadece korelasyon besleyicisi, tek başına alarm değil. (2) **Dar ve yüksek sinyalli** canary'ler: `LocalAccountTokenFilterPolicy`, `RestrictRemoteSAM`, Defender/LSA/IFEO anahtarlarına `svchost` kaynaklı yazım — az sayıda, doğrudan alarm. (3) **Korelasyon**: taban + canary/hive-dosyası/servis-değişikliği aynı host ve zaman penceresinde. Alarmı katman 3'e taşıyın; katman 1'i asla tek başına analiste göndermeyin, yoksa scanner gürültüsünde boğulur ve ekip kuralı susturur — susturulan kural, olmayan kuraldır.

Son yargı: uzaktan registry abuse, "winreg yakala" kuralıyla değil, **kanalın (MS-RRP/5145) meşru gürültüsünü kabul edip, üstüne hedef-anahtar hassasiyeti ve ardışık-icra korelasyonu bindirerek** tespit edilir. Tek imza yalan söyler; zincir söylemez.
