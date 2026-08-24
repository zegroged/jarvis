# Coerced Authentication (PetitPotam / PrinterBug) — Tespiti

> Saha notu: Bu metin, "PetitPotam nedir, EFSRPC çağrısına bak" seviyesinin ötesine geçmek için yazıldı. Asıl mesele tek bir RPC çağrısını yakalamak değil; o çağrıyı **kimlik doğrulama zorlaması (coercion) → relay → ayrıcalık yükseltme** zincirinin bir halkası olarak görebilmek ve gerçek ortamda tespitin nerede sessizce çöktüğünü bilmek.

---

## 1. Özet: saldırı + naif tespit

Coerced authentication (zorlanmış kimlik doğrulama), bir saldırganın hedef bir Windows makinesini —çoğunlukla bir Domain Controller'ı veya herhangi bir domain üyesi sunucuyu— kendi kontrolündeki bir hosta doğru **kimlik doğrulaması yapmaya zorlamasıdır**. Saldırgan makinede oturum açmaz, exploit ile kod çalıştırmaz; sadece kurbanın kendi makine hesabıyla (`MACHINE$`) attacker'a NTLM/Kerberos ile bağlanmasını tetikler. Tetikleyici genellikle bir MS-RPC arayüzüdür: **PetitPotam** MS-EFSRPC (`EfsRpcOpenFileRaw`, `EfsRpcEncryptFileSrv` vb.) fonksiyonlarını, **PrinterBug (SpoolSample)** ise MS-RPRN'in `RpcRemoteFindFirstPrinterChangeNotificationEx` çağrısını kötüye kullanır. Aynı aileden PetitPotam varyantları MS-DFSNM, MS-FSRVP gibi başka arayüzleri de kullanır.

Tek başına coercion "sadece" bir NTLM authentication üretir. Asıl yıkıcı senaryo, bu authentication'ın **NTLM relay** ile bir başka servise aktarılmasıdır. Klasik örnek: DC'nin makine hesabını AD CS'nin web enrollment (HTTP) endpoint'ine relay edip (ESC8), o makine hesabı adına bir sertifika almak. Elinde DC'nin makine kimliğine ait sertifika olan saldırgan, artık Kerberos ile domain'e o kimlikle giriş yapar — pratikte domain admin'e giden yol. LDAP'a relay ile RBCD (Resource-Based Constrained Delegation) kurmak da eşit derecede ölümcüldür.

Naif tespit herkesin bildiği yer: PetitPotam için gerçek Sigma kuralı **`Potential PetitPotam Attack Via EFS RPC Calls`** (id `4096842a-8f9f-4d36-92b4-d0b2a62f9b2a`) — Zeek/RPC telemetrisinde MS-EFSRPC arayüz çağrılarını yakalar; kural açıklaması bile bunun "nadiren, belki de hiç" kullanılmaması gerektiğini söyler. PrinterBug için tipik refleks ise Security event **4624 (Logon Type 3, Anonymous/Machine)** veya bir hunting açısından spoolss trafiğine bakmaktır. Bu kurallar doğru ama yüzeyseldir; asıl değer buradan sonra başlar.

---

## 2. Naif tespit neden yetmez

**Birincisi, telemetri çoğu ortamda yok.** `Potential PetitPotam Attack Via EFS RPC Calls` kuralının logsource'u Windows event değil, **network / dce_rpc** (Zeek gibi bir sensör). Yani MS-EFSRPC fonksiyon adlarını ancak SMB/RPC named pipe trafiğini decode eden bir NDR/Zeek varsa görürsün. Saf Windows Security log dünyasında `EfsRpcOpenFileRaw` diye bir alan **yoktur**. Çoğu SOC, endpoint log'una güvenip "kural var" sanır ama sensör olmadığı için kural hiç ateşlenmez — sessiz kör nokta. Host tarafında karşılığı `\pipe\lsarpc`, `\pipe\efsrpc`, `\pipe\lsass`, `\pipe\samr` gibi named pipe erişimleridir ve bunlar varsayılan olarak loglanmaz.

**İkincisi, sinyal tek başına düşük güvenli.** Bir NTLM makine-hesabı logon'u (4624 Type 3, `ANONYMOUS LOGON` ya da `HOST$`) ortamda saniyede onlarca üretilir. "DC bir yere authenticate oldu" cümlesi normal bir Active Directory ortamında gürültünün ta kendisidir. Coercion'ı bundan ayıran şey olayın kendisi değil, **hedefin attacker-kontrollü bir IP olması** ve zamanlamadır — bunu tek event'ten çıkaramazsın.

**Üçüncüsü, atlatma çok ucuz.** PetitPotam sadece EFSRPC değil; MS-DFSNM (`NetrDfsAddStdRoot`), MS-FSRVP, MS-RPRN gibi birden çok arayüzden aynı sonucu üretir. EFSRPC'ye özel kural yazdıysan, saldırgan `Coercer` aracıyla DFSNM'e geçer ve kuralının kör noktasından yürür. Ayrıca coercion tetikleyicisi authenticated bir kullanıcıyla `\pipe\efsrpc` üzerinden de gelebilir; MS'in yamaları (özellikle `PetitPotam`'ın `lsarpc` üzerinden anonymous varyantı için) sadece belirli pipe'ları kapattı, EFSRPC'nin kendisini değil.

**Dördüncüsü, false positive selleri.** Named pipe / RPC seviyesinde alarm kurarsan meşru EFS kullanımı, yedekleme ajanları, dosya sınıflandırma çözümleri ve özellikle **güvenlik tarayıcıları** (vuln scanner'lar coercion'ı zafiyet testi olarak tetikler) alarmı doldurur. "MS-EFSRPC gördüm" tek başına bir olay yönetim biletine değmez; onu bağlamla zenginleştirmeden triage kuyruğunu boğarsın.

Kısacası naif kural üç şeyden birini yapar: hiç ateşlenmez (sensör yok), ateşlenir ama gürültüdür (bağlam yok), ya da atlatılır (tek arayüze bakar). Değer, bunları çözen korelasyonda.

---

## 3. Korelasyon zinciri (asıl değer)

Coercion tek başına zayıf sinyaldir. Onu yüksek güvenli tespite çeviren şey, **kimin-nereye-ne kadar sürede** authenticate ettiğinin çok-aşamalı desenidir. İşte sahada işe yarayan somut zincirler:

### Zincir A — Coercion → Relay → AD CS (ESC8), klasik domain takeover

1. **A olayı (tetikleyici):** Sensörde MS-EFSRPC / MS-RPRN çağrısı, kaynak = daha önce hiç RPC yapmamış bir IP (çoğu zaman bir workstation subnet'inden ya da VPN'den), hedef = bir **Domain Controller**. (`Potential PetitPotam Attack Via EFS RPC Calls` burada ateşler.)
2. **B olayı (birkaç saniye içinde, aynı kaynak IP'den başka yöne):** Aynı attacker IP → **AD CS sunucusunun HTTP/HTTPS enrollment endpoint'ine** (`/certsrv/`, `certfnsh.asp`) bir bağlantı. Bu, relay'in çıkış tarafıdır.
3. **C olayı (farklı host, farklı log kaynağı):** AD CS sunucusunda **Security 4886/4887** (Certificate Services received/approved a request) — **subject = DC'nin makine hesabı** (`DC01$`) ama talebi yapan network oturumu attacker IP'sinden geliyor. Makine hesabının kendi kendine web enrollment üzerinden client-auth sertifikası alması **anormaldir**; makineler normalde autoenrollment'ı DCOM/RPC üzerinden yapar, `/certsrv` HTTP üzerinden değil.
4. **D olayı (kapanış):** Kısa süre sonra o sertifikayla **Kerberos 4768 (TGT talebi)** — `DC01$` kimliğiyle, PKINIT (sertifika tabanlı) ön kimlik doğrulama. Makine hesabının PKINIT ile TGT alması ortamınızda parmakla sayılacak kadar nadirdir.

Bu dört olay tek başına şüpheli, birlikte **neredeyse kesin ihlal**. Korelasyon anahtarı: *aynı attacker IP kısa pencerede hem coercion'ın hedefi tarafından authenticate edilen taraf, hem de AD CS'ye bağlanan taraf* + *DC makine hesabının web enrollment ile sertifika alması*.

### Zincir B — Coercion → LDAP relay → RBCD

1. Coercion tetikleyicisi (A, yukarıdaki gibi), hedef bir sunucu makine hesabı.
2. Attacker IP → **DC'nin LDAP/LDAPS** portuna bağlanır (relay hedefi LDAP).
3. **Security 5136 (directory object modified)** — hedef makinenin `msDS-AllowedToActOnBehalfOfOtherIdentity` (RBCD) özniteliği değişir, değiştiren kimlik = relay edilen makine hesabı. Bu öznitelik değişimi son derece nadir ve yüksek değerli bir sinyaldir; RBCD kurulumunun imzasıdır.
4. Ardından `S4U2Self/S4U2Proxy` deseni (4769 Kerberos service ticket'ları, tuhaf delegation zinciri).

### Korelasyonu güçlendiren ortak sinyal — NTLM'in kendisi

Her iki zincirde de kritik doğrulayıcı **makine hesabının NTLM ile başka bir hosta authenticate etmesidir**. DC'ler ve sunucular normalde birbirlerine **Kerberos** ile konuşur. Bir DC makine hesabının (`DC01$`) NTLM (NTLMSSP) ile, hele hele **bir workstation'a veya beklenmedik bir IP'ye** logon üretmesi doğada nadirdir. `Security 4624 Type 3 + Authentication Package = NTLM + Source User = MACHINE$ + Source IP = non-server subnet` kombinasyonu, coercion+relay'in en temiz tek-event yaklaşımıdır — ama yine de zincirdeki diğer halkalarla teyit edilmeli.

Google tek sayfada sana "4624'e bak" der; ama "DC makine hesabının NTLM logon'unu, aynı IP'nin AD CS'ye bağlanmasıyla, aynı pencerede eşleştir ve makine hesabının PKINIT TGT'siyle kapat" desenini bir arada vermez. Zinciri kuran budur.

---

## 4. False positive gerçeği ve triage yargısı

Bu alarmları meşru üreten şeyler gerçek ortamda boldur; kıdemli analist bunları refleksle eler:

- **Güvenlik/vuln tarayıcıları (Qualys, Nessus, Tenable, Purple Team araçları):** Coercion'ı zafiyet testi olarak *bilerek* tetikler. Kaynak IP taranan bilinen scanner ise ve hedef geniş bir aralıksa, bu tarama penceresidir. **Ayırt edici:** scanner tek bir hosta değil, /24'e yayılır ve authentication *relay'e dönüşmez* (AD CS'ye ikinci-taraf bağlantı yok, makine hesabı sertifikası çıkmaz). Zincirin B/C halkaları yoksa gürültüdür.
- **EFS'nin meşru kullanımı:** Encrypting File System kullanan ortamlarda `EfsRpc*` çağrıları normaldir. Ama meşru EFS **client-server** ekseninde ve genelde dosya sunucusuna doğru olur; DC'yi hedef alan `EfsRpcOpenFileRaw` meşru senaryoda neredeyse hiç görülmez. **Hedefin DC olması** en güçlü ayraçlardan biridir.
- **Yedekleme / dosya sınıflandırma / DLP ajanları:** Named pipe ve RPC trafiği üretir. Bunlar bilinen servis hesaplarından, bilinen sunuculardan, düzenli ve zamanlı gelir. Baseline'da tanınırlar.
- **SCCM / dağıtım altyapısı:** Yoğun makine-hesabı authentication üretir ama bilinen SCCM sunucularından ve Kerberos ağırlıklıdır.
- **Cluster / SQL AlwaysOn / DFS-R:** Sunucular arası makine-hesabı authentication normaldir — ama sunucular arasında ve genelde Kerberos.

**Kıdemli analistin triage sırası — çoklu alarmda önce neye bakar:**

1. **Hedef kimliği:** Coercion hedefi bir **Domain Controller veya AD CS/ADFS/Exchange gibi tier-0 varlık mı?** Evetse öncelik tavan yapar; workstation ise büyük olasılıkla gürültü ya da lateral movement başka bir aşama.
2. **Authentication protokolü ve yön:** Makine hesabı **NTLM ile mi, beklenmedik bir IP'ye mi** authenticate etti? Kerberos ve sunucu-sunucu ise düş. NTLM + workstation-IP ise yüksel.
3. **İkinci-taraf bağlantısı (relay kanıtı):** Coercion'ı üreten IP, **kısa pencere içinde AD CS HTTP endpoint'ine, LDAP'a ya da bir SMB hedefine** bağlandı mı? Bu, "test mi gerçek relay mi" sorusunun cevabıdır. **Relay çıkışı yoksa** coercion tek başına genelde tarama/gürültüdür.
4. **Sonuç artefaktı:** Yeni makine-hesabı sertifikası (4886/4887), RBCD özniteliği değişimi (5136), PKINIT TGT (4768). Bu artefaktlardan biri varsa artık "şüphe" değil, **olay**.
5. **Kaynak IP itibarı ve varlık:** IP bilinen scanner mı, DHCP'den yeni mi, VPN'den mi? Kayıtlı bir varlık değilse ("bu IP kime ait?" cevabı yoksa) tehlike artar.

Pratik yargı: *Coercion alarmı tek başına P3'tür; relay çıkışıyla eşleşirse P1'e sıçrar.* Analistin en büyük hatası, ilk sinyali izole değerlendirip ya panikleyip her taramayı incident açmak ya da gürültü sanıp gerçek zinciri kaçırmaktır. Kural her ikisinde de "aynı pencerede ikinci-taraf var mı" sorusudur.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan naif kuralı bilir ve kural dokümanında yazmayan yollardan yürür. Her atlatmaya ikinci-derece bir tespit vardır:

**Atlatma 1 — Arayüz değiştirme.** EFSRPC'ye özel kuralın varsa, `Coercer` ile MS-DFSNM (`NetrDfsAddStdRoot`), MS-FSRVP (`IsPathShadowCopied`) veya MS-RPRN'e geçer. **Karşı-tespit:** Kuralı tek fonksiyon adına değil, **davranışa** bağla: "makine hesabının kısa pencerede beklenmedik bir IP'ye NTLM authentication'ı" tetikleyiciden bağımsızdır — hangi RPC arayüzü kullanılırsa kullanılsın relay çıkışı aynı NTLM izini bırakır. Yani ağırlığı A halkasından (RPC çağrısı) B/C/D halkalarına (relay ve sonuç) kaydır.

**Atlatma 2 — Kerberos coercion (relay-agnostik yeni cephe).** NTLM'i kapattıysan (SMB signing, EPA), saldırgan Kerberos coercion'a geçer. Gerçek Sigma kuralı **`Suspicious DNS Query Indicating Kerberos Coercion via DNS Object SPN Spoofing`** (id `e7a21b5f-d8c4-4ae5-b8d9-93c5d3f28e1c` ve network varyantı `5588576c-...`) tam bunu yakalar: `1UWhRCAAAAA..BAAAA` desenli DNS sorgusu, marshalled bir `CREDENTIAL_TARGET_INFORMATION` yapısının base64 imzasıdır — **CVE-2025-33073** ekseninde SPN spoofing ile authentication yönlendirme. **Karşı-tespit:** NTLM'e ek olarak bu DNS deseni için DNS Analytical log / network DNS sensörü kur; Kerberos cephesini NTLM cephesiyle aynı incident altında korelasyona sok.

**Atlatma 3 — Aracı binary'sini yeniden adlandırma / bellekte çalıştırma.** Saldırgan `PetitPotam.exe`'yi çalıştırmaz; Python (`Coercer`, `impacket`), C# implant veya BOF (Cobalt Strike beacon object file) ile in-memory tetikler. `HackTool Named File Stream Created` (id `19b041f6-...`, imphash tabanlı) veya `HackTool - Generic Process Access` (id `d0d2f720-...`, `\CoercedPotato.exe` gibi image adlarına bakar) gibi **isim/imphash tabanlı** kurallar bu durumda kördür. **Karşı-tespit:** İsimden vazgeç, **davranışa** dayan — attacker hostundan bakınca: `\pipe\efsrpc` / `\pipe\lsarpc` / `\pipe\spoolss`'a giden **çıkan** named-pipe bağlantıları, ardından **gelen** relay bağlantıları (443/389/445). Named pipe erişim telemetrisi (Sysmon Event ID 18 — PipeConnected, ya da 5145 detailed file share) isimden bağımsızdır.

**Atlatma 4 — Yavaşlatma / gürültüye karıştırma.** Coercion'ı bir vuln tarama penceresine denk getirir ya da tek atış yapıp saatlerce bekler, böylece "kısa pencere" korelasyonundan kaçar. **Karşı-tespit:** Korelasyon penceresini sonuç artefaktına bağla — relay çıkışı ile sertifika talebi (4886) arasındaki ilişki saatler sürebilir ama *makine hesabının web enrollment ile sertifika alması* kendi başına düşük-frekanslı, yüksek-değerli bir sinyaldir; zaman penceresi geniş olsa da nadir olduğu için ayakta durur.

**Atlatma 5 — Signing/EPA'yı by-pass eden reflection.** Synacktiv'in NTLM reflection çalışması (CVE-2025-33073 bağlamı), coercion'ı makinenin *kendi üzerine* relay ederek SMB signing gibi korumaları etkisiz kılabildiğini gösterdi. **Karşı-tespit:** Kaynak ve hedefin aynı host olduğu, ama authentication'ın anormal bir SPN/loopback deseni taşıdığı durumları ayrı bir hunt olarak izle; yukarıdaki DNS SPN-spoofing kuralı bu ailenin ağ tarafındaki ayak izidir.

Özetle kedi-fare şu eksende döner: saldırgan **tetikleyiciyi** (hangi RPC, hangi binary) sürekli değiştirebilir; ama **fiziksel sonuç** —bir makine hesabının beklenmedik yere authenticate etmesi ve ardından bir sertifika/RBCD/TGT artefaktı doğması— değişmez. Sağlam tespit ağırlığı değişebilen tetikleyiciden, değişemeyen sonuca kaydırır.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** `Potential PetitPotam Attack Via EFS RPC Calls` bir **network (dce_rpc) logsource** kuralıdır — Zeek alan adlarıyla (`operation`, `endpoint`, `named_pipe`) düşünür. Bunu bir Windows Security index'ine olduğu gibi map etmeye çalışmak boşa kürek; karşılığı yoktur. Windows tarafında en yakın host artefaktları: **5145** (detailed file share — `RelativeTargetName` = `efsrpc`, `lsarpc`, `samr`, `spoolss` named pipe'ları), **Sysmon Event 18** (pipe connected). `HackTool Named File Stream Created` kuralı ise `create_stream_hash` kategorisi ister — yani **Sysmon config'te Imphash logging açık** olmalı (`<HashAlgorithms>*</HashAlgorithms>` veya en azından IMPHASH). Bu açık değilse kural sessizdir. `HackTool - Generic Process Access` `process_access` (Sysmon Event 10) kategorisindedir; bu da varsayılan Sysmon config'lerde çoğu zaman gürültü kaygısıyla kısıtlanır.

**Varsayılan loglanmayanlar — asıl kör nokta.** Coercion tespitinin en kritik alanları default'ta kapalıdır:

- **5145 (Detailed File Share):** "Audit Detailed File Share" **Success** varsayılan olarak KAPALI. Bu açılmadan named pipe erişimlerini (`efsrpc`, `lsarpc`) Windows tarafında göremezsin. Açtığında ise hacim devasa olur — hedefli (DC/tier-0 sunucularda) açmak gerçekçi tuning'dir, her endpoint'te değil.
- **4886/4887 (AD CS Certificate Services):** CA rol logları **CA seviyesinde audit** açılmadan (`certutil -setreg CA\AuditFilter 127` + "Audit Certification Services" policy) gelmez. ESC8 tespitinin C halkası buna bağlıdır — çoğu ortamda kapalı olduğu için domain takeover'ın en net kanıtı hiç loglanmaz.
- **5136 (Directory Service Changes):** RBCD tespiti için şart; "Audit Directory Service Changes" default'ta kısıtlı ve `msDS-AllowedToActOnBehalfOfOtherIdentity` özelinde SACL gerekebilir.
- **NTLM auditing:** "Restrict NTLM: Audit" politikası açılmadan makine-hesabı NTLM logon'larının kaynağını netleştirmek zorlaşır; 4624 Type 3 gelir ama zenginlik eksik kalır.

**Splunk vs Sentinel vs Elastic farkı.**
- **Splunk:** Korelasyonu genelde `transaction` ya da zaman-pencereli `stats`/`join` ile kurarsın; attacker IP'yi ortak anahtar yapıp coercion event'i ile AD CS bağlantısını `| stats ... by src_ip` üzerinden eşleştirmek performanslıdır. Zeek verisi varsa Corelight/Zeek TA ile dce_rpc alanları hazır gelir — PetitPotam network kuralının doğal evi burasıdır.
- **Sentinel:** KQL'de multi-stage için `join kind=inner` ya da `materialize` + zaman-pencereli korelasyon; `SecurityEvent` (4624/4768/4886) ile `DeviceNetworkEvents` (Defender for Endpoint) arasında join. Sentinel'in Fusion/ML korelasyonu bu tür çok-aşamalı deseni bazen kendiliğinden birleştirir ama tuning ister. AD CS event'leri için sunucuya MMA/AMA agent şart.
- **Elastic:** EQL **sequence** sorgusu bu iş için biçilmiş kaftandır — `sequence by source.ip with maxspan=5m [coercion] [ad_cs_connection]` gibi. Ama Elastic'te Windows event field normalizasyonu (ECS) tuzaklıdır: `winlog.event_data.*` altındaki ham alanlar ile ECS `user.name`/`source.ip` arasındaki eşleme pipeline'a bağlıdır; `SubjectUserName` vs `TargetUserName` karıştırılırsa makine hesabı filtresi yanlış çalışır.

**Tuning gerçeği.** İlk gün her `EfsRpc*` çağrısına alarm kurarsan analistleri boğarsın. Gerçekçi olgunlaşma sırası: (1) **hedefi tier-0'a daralt** — sadece DC/AD CS/ADFS'e giden coercion; (2) **makine-hesabı NTLM logon'unu beklenmedik yöne** high-fidelity tekil kural yap; (3) asıl yatırımı **relay çıkışı + sonuç artefaktı** korelasyonuna koy (4886 makine-hesabı sertifikası, 5136 RBCD, 4768 PKINIT) — bunlar düşük frekanslı olduğu için tuning derdi az, değeri yüksek. Scanner IP'lerini ve bilinen yedek/EFS servis hesaplarını allowlist'e alarak alt katmandaki gürültüyü bastır. Unutma: bu tespitte kazanan taraf en çok kural yazan değil, **doğru dört event'i aynı olayın altında birleştirebilen** taraftır.

---

**Kapanış yargısı:** PetitPotam/PrinterBug tespitinde tek bir "sihirli kural" yoktur ve olmamalıdır. Değerli olan mimari şudur — tetikleyici katmanı (RPC/DNS, atlatılabilir, düşük güven) + kimlik katmanı (makine-hesabı NTLM/Kerberos anomali, orta güven) + sonuç katmanı (sertifika/RBCD/PKINIT artefaktı, yüksek güven). Naif kural sadece birinci katmandır. Kıdemli iş, üç katmanı aynı attacker-IP ve zaman ekseninde dikip, telemetrinin default kapalı parçalarını (5145, 4886, 5136, NTLM audit) tier-0 varlıklarda bilinçli olarak açmaktır.
