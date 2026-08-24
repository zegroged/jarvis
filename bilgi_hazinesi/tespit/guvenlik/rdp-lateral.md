# RDP Lateral Movement — Tespit (Saha Notları)

> Bu metin, RDP'yi bir *yanal hareket* aracı olarak kullanan saldırganı yakalamak üzerine. "RDP nedir" anlatmıyorum; sinyalleri nasıl birbirine bağlayacağını, tespitin sahada gerçekte neden çöktüğünü ve triyajda neyi önce açacağını anlatıyorum. Referans olarak elimizde dört gerçek Sigma kuralı var (aşağıda `id`'leriyle birlikte anıyorum), onların `logsource`/`field`/`EventID` adlarını değiştirmeden kullanıyorum.

---

## 1. Özet: saldırı + naif tespit (KISA)

Yanal hareketin klasik profili şu: Saldırgan bir uç noktada (genelde bir kullanıcı iş istasyonu, "patient zero") tutunmuş durumda. Oradan Domain'in içine yayılmak için en sevdiği yol RDP (TCP 3389, `mstsc.exe` istemci tarafında). Neden RDP? Çünkü meşru. Admin de RDP kullanıyor, yardım masası da RDP kullanıyor, sen de RDP kullanıyorsun. Trafik şifreli, protokol imzalı, EDR'ın "kötü" diye bağırdığı bir binary yok ortada. Saldırgan çalınmış bir kimlik bilgisiyle (pass-the-hash sonrası bilet, ya da düz parola) hedef sunucuya `mstsc` ya da bir C2 üzerinden proxy'lenmiş RDP ile bağlanıyor; **`Type 10` (RemoteInteractive) logon** düşüyor, oturum açılıyor, iş bitiyor.

**Naif tespit** genelde şu üçünden biri:

1. **Ağ tarafı:** "3389 portuna giden trafik" — firewall/NetFlow'da 3389 gördüm, alarm.
2. **Güvenlik logu tarafı:** **Security EventID 4624** + `LogonType=10` — "biri RDP ile giriş yaptı".
3. **Konfigürasyon tarafı:** RDP'yi *açan* registry değişiklikleri. Burada elimizdeki iki gerçek kural devreye giriyor:
   - `id: 88bf1ccf-789d-4864-9eaf-547990ffe90a` → **"Default RDP Port Changed to Non Standard Port"** (`registry_set`, alt kural `id: 509e84b9-a71a-40e0-834f-05470369bd1e`),
   - `id: a9bcd1ab-6556-4fc3-b9c9-724b335485e4` → **"Allow RDP Remote Assistance Feature"** (`registry_set`, alt kural `id: 37b437cf-3fc5-4c8e-9c94-1d7c9aff842b`).

Bunların hepsi *doğru* sinyaller. Ama tek başlarına alarm olarak kullanıldıklarında ya kör kalıyorlar ya da SOC'u boğuyorlar. Neden — Bölüm 2.

---

## 2. Naif tespit neden yetmez

### 2.1 "3389 gördüm" ölü doğmuş bir alarm

3389'u ağda izlemek iki nedenle çöker. Birincisi, kurumsal ortamda RDP *zaten* her yerde: yönetim VLAN'ı, jump host'lar, yardım masası araçları, hatta bazı yazılımların kendi remote-support modülleri. Günde binlerce meşru 3389 akışı olan bir ortamda tek başına port sinyali bir triyaj kaynağı değil, bir gürültü jeneratörüdür.

İkincisi — ve saha insanının gözden kaçırdığı kritik nokta — saldırgan **standart portu kullanmak zorunda değil**. İşte tam burada `509e84b9-...` kuralı ("Default RDP Port Changed to Non Standard Port") kavramsal olarak anlam kazanıyor: RDP dinleme portu `HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp\PortNumber` değeriyle değiştirilebilir. Saldırgan bunu 3389'dan mesela 443'e ya da 4444'e çekerse, senin "3389'u izle" kuralın anında körleşir. Yani port-tabanlı naif tespit, saldırganın tek bir `reg add` ile devre dışı bırakabileceği bir savunmadır. Bu yüzden değerli olan port trafiğini görmek değil, **portun değiştirilmesi olayını** görmektir (ki o da bir registry sinyali, ağ sinyali değil).

### 2.2 "4624 Type 10 gördüm" — bağlamsız tek satır

`LogonType=10` görmek RDP oturumunu görmek demektir, doğru. Ama sorun şu: Type 10 logon'ların **ezici çoğunluğu meşru**. Admin sabah jump host'a bağlanıyor → Type 10. Yardım masası kullanıcıya destek veriyor → Type 10. Sen kendi sunucuna bağlanıyorsun → Type 10. Bir alarmın "true positive oranı" %0.1 civarındaysa, o alarm bir alarm değil, bir arşivdir.

Dahası, `4624` tek başına *kaynağı* net vermez. `IpAddress` alanı vardır ama iç ağda NAT/jump host arkasında anlamsızlaşır; `WorkstationName` boş ya da sahte olabilir. Yani "kim, nereden, hangi kimlikle" sorusunun üçünü birden tek `4624` satırından güvenle çıkaramazsın.

### 2.3 Registry kuralları: doğru ama "geç" ve "tekil"

`88bf1ccf-...` (port değişikliği) ve `a9bcd1ab-...` (Remote Assistance açma) kuralları `registry_set` `logsource`'una dayanıyor — yani **Sysmon EventID 13** (RegistryValue Set) gerektiriyorlar (kuralların `regression_tests_info` bloğunda `provider: Microsoft-Windows-Sysmon` yazması tesadüf değil). İki problem:

- **Sysmon şart.** Sysmon deploy edilmemiş bir sunucuda bu iki kural sıfır sinyal üretir. Yani bu kurallar *default* Windows loglamasında yoktur; onları görmek için önceden bir telemetri yatırımı yapmış olman gerekir. Çoğu kurumda "kritik sunuculara Sysmon" dendiği için, saldırganın uğradığı ikinci-kademe sunucularda tam da bu kör nokta oluşur.
- **Tekil sinyal geç kalır.** RDP portunu değiştirmek ya da Remote Assistance'ı açmak, saldırının *kalıcılık/hazırlık* fazıdır; yanal hareketin *kendisi* değildir. Bunları tek başına alarm yaparsan, ya saldırgan bunları hiç yapmadan (default RDP zaten açıksa) geçer ve sen hiçbir şey görmezsin, ya da bir sysadmin meşru bir sebeple portu değiştirir ve sen boşuna koşarsın.

### 2.4 Canary'nin sınırı

Elimizdeki dördüncü kural `id: 598290cf-5932-45cd-9123-be1e05ab4f2e` — **OpenCanary "RDP New Connection Attempt"** (`logsource: category: application, product: opencanary`, `detection: selection: logtype: 14001`). Bu *çok* değerli bir sinyaldir çünkü canary'ye giden RDP'nin neredeyse hiçbir meşru sebebi yoktur (`falsepositives: Unlikely`, `level: high` — haklı olarak). Ama sınırı da açık: canary sadece **kendisine dokunulursa** öter. Saldırgan senin canary IP'ine hiç uğramadan gerçek sunucuya giderse, bu kural sessiz kalır. Yani canary bir *tarama/keşif* dedektörüdür, hedefli yanal hareketin garantili yakalayıcısı değil.

**Özet:** Her sinyal tek başına ya kör (Sysmon yok, canary'ye uğranmadı), ya geç (registry hazırlık fazı), ya da gürültü (3389, Type 10). Değer, bunları **zincirlemekte**.

---

## 3. Korelasyon zinciri (asıl değer)

Yanal hareketi yüksek güvenle yakalamanın yolu, "RDP oldu mu" sorusundan "RDP **anomali** deseninde mi oldu" sorusuna geçmektir. Tek sinyal zayıf; farklı bağlamlardan gelen 2-3 sinyali kısa bir zaman penceresinde birleştirdiğinde false positive katlanarak düşer.

### 3.1 Çekirdek desen: "İş istasyonu → Sunucu, ters yön" + yeni kaynak

Meşru RDP'nin topolojisi öngörülebilir: admin makinelerinden / jump host'lardan → sunuculara. Yanal hareket bu topolojiyi *bozar*. En güçlü tek gözlem: **bir kullanıcı iş istasyonunun, başka bir uç noktaya RDP *başlatması***. Normalde workstation-to-workstation ya da workstation-to-server RDP (jump host dışından) neredeyse yoktur.

**Zincir örneği (somut):**

- **A —** Kaynak makinede **`mstsc.exe` süreç başlatma** (Sysmon EventID 1 / Security 4688). Tek başına: zayıf, herkes mstsc açar.
- **+ kısa pencere (≤ 2 dk) B —** Aynı kaynaktan hedefe giden **çıkış RDP bağlantısı** (Sysmon EventID 3, `DestinationPort: 3389` *veya* — port değiştirilmişse — non-standart port + `Image: mstsc.exe`). Farklı bağlam: süreç değil, ağ.
- **+ C —** Hedefte **`4624 LogonType=10`**, `TargetUserName` = ayrıcalıklı bir hesap, `IpAddress` = A'nın makinesinin bir *kullanıcı iş istasyonu* olması. Farklı bağlam: kimlik/logon.

A + B + C = "bir kullanıcı iş istasyonu, ayrıcalıklı bir hesapla, bir sunucuya interaktif RDP açtı, iki dakika içinde." Bu üçlü aynı anda meşru olmak için çok fazla anomali barındırır. Bu, tek `4624`'ün %0.1 TP oranını yüzde onlara çıkarır.

### 3.2 Kimlik bağlamını ekle: 4624'ü 4768/4769 ile evlendir

Saldırgan RDP'ye çalınmış kimlikle giriyorsa, logon'dan hemen önce Kerberos izleri kalır. Zinciri güçlendiren dördüncü halka:

- **+ D —** Hedef logon'dan (`4624 Type 10`) hemen önce, kaynak makine adına **`4768` (TGT talebi)** veya **`4769` (hizmet bileti talebi)** — özellikle bilet, kullanıcının *normalde hiç oturum açmadığı* bir makine için isteniyorsa. Pass-the-ticket / overpass-the-hash sonrası RDP'de bu desen çok tipiktir: bilet birden fazla makine için art arda istenir (recon), sonra hedefe Type 10.

"Aynı hesap, 60 saniye içinde 5 farklı hedef için `4769` + ardından birine `4624 Type 10`" = neredeyse deterministik yanal hareket sinyali.

### 3.3 "Hazırlık" sinyalini zincire ekle (registry kuralları burada değer kazanır)

Bölüm 2'de "tekil oldukları için geç" dediğim registry kuralları, zincirin *bağlamı* olarak altın değerinde:

- Eğer bir hedefte `509e84b9-...` (**PortNumber değişikliği**) veya `37b437cf-...` (**Remote Assistance açma** — `HKLM\...\Terminal Server\fAllowToGetHelp` = 1) sinyali düştüyse **ve** aynı host'a **ilk kez** bir Type 10 logon geldiyse, bu artık "sysadmin bakım yapıyor" değil, "saldırgan kalıcı RDP arka kapısı kuruyor" hipotezine döner. Registry değişikliğini *yalıtık* değil, *logon deseniyle korele* okuduğunda FP çöker.

### 3.4 Canary'yi keşif sinyali olarak kullan

`598290cf-...` (OpenCanary `logtype: 14001`) zincirin **erken uyarı** halkası. Saldırgan yanal hareket öncesi ağ tarar; canary RDP'ye dokunması "birileri RDP hedefi arıyor" der. Bunu şu sırayla oku: **Canary RDP tetiklendi → sonraki 30 dk içinde aynı kaynak IP'den gerçek bir sunucuya `4624 Type 10`**. Canary tek başına "birisi taradı", ama canary + ardından gerçek hedefe başarılı Type 10 = "taradı **ve** girdi". Bu, PetitPotam kuralının (`id: 4096842a-...`) açıklamasındaki mantığın aynısı: *"View surrounding logs (within a few minutes before and after) from the Source IP"* — kaynak IP'yi sabitle, çevresindeki `rdp`, `ntlm`, `kerberos`, `smb_mapping` olaylarını topla. Yanal hareket triyajının özü budur: **kaynak IP'yi eksen al, zaman penceresinde farklı log tiplerini üst üste bindir.**

### 3.5 Zincirin özeti

> Tek başına: `4624 Type 10` = gürültü. 
> Zincir: `mstsc` süreci (EDR) **+** çıkış 3389/non-standart (Sysmon EID 3) **+** hedefte Type 10 ayrıcalıklı hesap (Security 4624) **+** öncesinde çoklu `4769` (Kerberos) **+** hedefte `PortNumber`/`fAllowToGetHelp` değişikliği (Sysmon EID 13) = **yüksek güven ihlal.**

Hiçbir tekil kural bunu vermez; korelasyon verir.

---

## 4. False positive gerçeği ve triyaj yargısı

Sahada seni öldüren TP değil, FP selidir. RDP tespitinde büyük FP kaynakları ve triyaj yaklaşımı:

**Başlıca FP üreticileri:**

- **SCCM / yönetim ajanları:** Yazılım dağıtımı, envanter, uzak yardım modülleri düzenli olarak sunuculara/uç noktalara bağlanır. Bazı SCCM Remote Control çözümleri RDP benzeri oturum açar. Bunlar `4624`'ü belirli *servis hesaplarıyla* ve *belirli kaynak sunuculardan* üretir — bu ikiliyi baseline'la.
- **Yedekleme sistemleri / izleme:** Veeam, monitoring ajanları, bazı yedek ajanları interaktif olmayan ama "uzak" görünen oturumlar açar. Genelde Type 10 değil Type 3'tür, ama karışık ürünlerde Type 10 da görülür.
- **Zafiyet/varlık tarayıcıları (Nessus, Qualys):** 3389'a *bağlanmayı dener*, bu da canary'yi (`598290cf-...`) ve ağ sinyallerini tetikler. Ama bunlar **kimlik doğrulamaz** — canary'de connection attempt olur, ama arkasından başarılı `4624` **gelmez**. Ayırt edici nokta: tarayıcı = attempt var, logon yok; saldırgan = attempt + başarılı Type 10.
- **Jump host / bastion trafiği:** Bir bastion'dan onlarca sunucuya Type 10 tamamen normaldir. Bastion IP'lerini bir *allowlist eksen* olarak tanımla — ama dikkat: saldırgan bastion'u ele geçirdiyse bu allowlist seni kör eder, o yüzden bastion'dan çıkan RDP'yi *hesap davranışıyla* izle (yeni hesap, olağandışı saatte).
- **VDI / yardım masası:** Kullanıcıya destek veren yardım masası ekibi `fAllowToGetHelp` ve Remote Assistance'ı meşru olarak açar — `37b437cf-...` kuralı için doğal FP. Yardım masası araç sunucusunu ve servis hesabını baseline'a al.

**Analistin öncelik (triyaj) sırası — en yüksekten en düşüğe:**

1. **Canary RDP (`598290cf-...`) + ardından gerçek hedefe başarılı Type 10.** `falsepositives: Unlikely`. Sıfır tolerans, hemen aç. Bu neredeyse hiçbir zaman yanlış değildir.
2. **Ayrıcalıklı hesapla, bir *kullanıcı iş istasyonundan* sunucuya Type 10** (jump host değil). Topoloji ihlali. Yüksek öncelik.
3. **Çoklu `4769` recon deseni + Type 10.** Pass-the-ticket şüphesi. Yüksek.
4. **Hedefte `PortNumber`/`fAllowToGetHelp` değişikliği + yeni Type 10.** Kalıcılık şüphesi. Orta-yüksek — ama önce "değişikliği yapan hesap yardım masası/sysadmin mi" diye bak.
5. **Yalıtık Type 10, bilinen bastion'dan, bilinen hesapla.** Muhtemel FP. Otomatik kapat ya da toplu incele.

**Triyajın altın sorusu:** "Bu logon'un *kaynağı* normalde bu hesabı, bu hedefe, bu saatte gönderir mi?" Üç boyut (kaynak, hesap, hedef) birden anormalse — koş. Biri bile normalse — çoğunlukla FP.

---

## 5. Kaçınma → karşı-tespit

Deneyimli saldırgan yukarıdaki zincirin her halkasını kırmayı bilir. Dokümanların yazmadığı gerçek atlatmalar ve onların ikinci-derece karşı-tespiti:

### 5.1 Port değiştirme ile ağ körlüğü → registry sinyali kalır

Saldırgan `PortNumber`'ı değiştirip 3389 tabanlı ağ kurallarını kör eder. Ama bunu yaparken tam da `509e84b9-...` kuralının aradığı `registry_set` olayını üretir (Sysmon EID 13). **Karşı-tespit:** Port sinyaline değil, *port değişikliği* olayına güven. Ayrıca `mstsc.exe`'nin hedef portu ne olursa olsun `Image: mstsc.exe` + `DestinationPort != 3389` kombinasyonu başlı başına şüphelidir — çünkü meşru mstsc neredeyse hep 3389'a gider.

### 5.2 RDP tünelleme / proxy (SSH, ngrok, SOCKS) → uç nokta süreç ağacı

Saldırgan RDP'yi doğrudan açmak yerine bir tünelden (SSH port forward, ngrok, chisel, ya da C2'nin SOCKS proxy'si) geçirir; ağ tarafında "RDP" hiç görünmez, `127.0.0.1:3389`'a `localhost` bağlantısı olur. **Karşı-tespit:** İki katman. (a) **Loopback RDP anomalisi:** hedefte `4624 Type 10` var ama `IpAddress = 127.0.0.1`/`::1` → bu neredeyse her zaman tünelin işaretidir; meşru interaktif RDP loopback'ten gelmez. (b) **Tünel binary'sinin kendisi:** `ssh.exe -L`, `ngrok`, `chisel`, olağandışı `plink.exe` süreçleri — süreç yaratma (EID 1/4688) ve komut satırıyla yakalanır. Linux ayağında bu, `f7158a64-...` kuralının (`auditd`, "Suspicious C2 Activities") izlediği `ssh`, `socat`, `nc`, `rdesktop` çağrılarıyla örtüşür — auditd `-w /usr/bin/ssh -p x -k susp_activity` ile tünel kurucuyu görebilir.

### 5.3 Restricted Admin / pass-the-hash ile RDP → Kerberos deseni

`mstsc /restrictedadmin` modu RDP'ye parola göndermeden hash ile bağlanmayı mümkün kılar (network logon gibi davranır). Bu, bazı istemci-tarafı parola sinyallerini atlatır. **Karşı-tespit:** Restricted Admin logon'ları farklı bir imza bırakır (`4624` içinde ek alanlar, `4648` explicit credential kalıpları). Ayrıca overpass-the-hash için üretilen bilet `4769` deseniyle görünür kalır — Kerberos halkası (Bölüm 3.2) burada kritik.

### 5.4 "Loglama kapalı" hedef → merkezi korelasyon

Saldırgan Sysmon'u durdurabilir (`sc stop`, driver unload) ya da Sysmon deploy edilmemiş bir sunucuya kaçar; registry kuralları (`88bf1ccf-...`, `a9bcd1ab-...`) körelir. **Karşı-tespit:** (a) **Sysmon'un kendisinin susması** bir sinyaldir — Sysmon EID 255 / servis durması / `System` log'da servis stop. (b) Sysmon olmasa bile **Security `4624 Type 10`** varsayılan olarak (uygun politikayla) düşer; ağ kenarındaki NetFlow ve hedefteki Kerberos logonları merkezi loglamaya gider. Yani tek bir host'un telemetrisini kaybetsen bile, korelasyonu *başka* log kaynaklarından yeniden kur.

### 5.5 Yavaşlatma (low & slow) → pencereyi genişlet, davranış baselineı

Saldırgan zincirin halkalarını saatlere/günlere yayarak "kısa pencere" korelasyonundan kaçar. **Karşı-tespit:** Zaman-penceresi korelasyonuna ek olarak **davranışsal baseline**: "bu hesap ilk kez bu hedefe Type 10 yaptı" (first-seen) sinyali pencereden bağımsızdır. First-seen (kullanıcı×hedef) + first-seen (kullanıcı×kaynak makine) düşük hacimli ama yüksek değerli sinyallerdir.

---

## 6. SIEM / saha gerçeği

### 6.1 Field mapping ve varsayılan loglanmayanlar

- **`4624 LogonType=10`** Security kanalında **Logon/Logoff** denetimi *başarı* için açık olmalı. Çoğu Windows'ta başarı logon denetimi açıktır ama yüksek hacimli sunucularda bazen kısılır — **kontrol et**, yoksa RDP logon'un hiç görünmez.
- **Registry kuralları (`88bf1ccf-...`, `a9bcd1ab-...`) Sysmon EID 13 gerektirir.** Windows'un yerel loglaması registry `set` olaylarını *varsayılan üretmez* (yerel Registry denetimi ancak SACL ile ve pratikte devasa gürültüyle gelir). Yani Sysmon config'inde `HKLM\...\Terminal Server\...` ve `WinStations\RDP-Tcp\PortNumber` yolları izleniyor olmalı. İzlenmiyorsa kural body'si doğru olsa da sinyal sıfırdır.
- **Süreç oluşturma (`mstsc.exe`, tünel binary'leri):** Security **4688** için "Audit Process Creation" + tercihen komut satırı loglaması (`Include command line in process creation events` GPO) açık olmalı; yoksa Sysmon EID 1 gerekir. Default kurumda komut satırı çoğu zaman **kapalıdır** — bu, tünel tespitinde en büyük kör noktadır.
- **Ağ bağlantısı (`Sysmon EID 3`):** Yüksek hacimli olduğu için birçok kurum EID 3'ü kısar/filtreler. RDP portu (3389 + bilinen non-standart portlar) mutlaka include listesinde olmalı.

### 6.2 Splunk / Sentinel / Elastic farkı

- **Splunk:** Zincir korelasyonu için `tstats` + `transaction`/`stats by src` en pratik. Type 10 logon'ları `EventCode=4624 Logon_Type=10`; Sysmon `sourcetype=XmlWinEventLog:Microsoft-Windows-Sysmon/Operational`. Korelasyonu `| stats ... by src_ip` ile kaynak IP eksenli kur (PetitPotam kuralının mantığı). Risk-based alerting (RBA) burada ideal: her zayıf sinyale düşük risk skoru ver, eşik aşımında alarm üret — böylece tekil FP'ler tek başına ötmez, ama üst üste binince ateşler.
- **Microsoft Sentinel:** KQL ile `SecurityEvent | where EventID == 4624 and LogonType == 10`. Sysmon'u getirmişsen `Event`/`SysmonEvent`. Sentinel'in **UEBA** ve **Fusion** modülleri "anormal RDP" ve "impossible travel benzeri" korelasyonu hazır sunar; ayrıca `4769` recon'u UEBA anomali olarak işaretleyebilir. Zinciri `join`/`union` + `bin(TimeGenerated, 5m)` ile pencerele.
- **Elastic:** ECS alan adları önemli — `event.code: "4624"`, `winlog.event_data.LogonType: "10"`, kaynak `source.ip`. Elastic'in **EQL sequence** özelliği bu iş için biçilmiş kaftan: `sequence by source.ip with maxspan=5m [process where mstsc] [authentication where logon_type==10]` gibi. Sysmon ağ olayları `event.category: network`.

### 6.3 Tuning — pratik reçete

1. **Bastion/jump host IP'lerini ve yönetim servis hesaplarını** ayrı bir referans listesine al; bunlardan gelen Type 10'u düşük skorla (ama *asla* tamamen suppress etme — ele geçirilmiş bastion senaryosu).
2. **SCCM/Veeam/monitoring servis hesaplarını** hesap-bazlı istisna yap, IP-bazlı değil (IP değişir, hesap davranışı sabit kalır).
3. **First-seen mantığını** ekle: kullanıcı×hedef ve kullanıcı×kaynak ikilileri için ilk görülme takibi — düşük hacim, yüksek değer.
4. **Non-standart RDP portunu** ağ kuralına da yansıt: sadece 3389 değil, `mstsc.exe` + herhangi bir dış port kombinasyonunu izle.
5. **Canary alarmını (`598290cf-...`) hiç tune etme** — `level: high`, `falsepositives: Unlikely`. Onu olduğu gibi bırak, RBA'da en yüksek skoru ver.
6. **Sysmon'un canlılığını** izle (heartbeat/EID 255) — telemetri kaybı da bir alarm olsun.

### 6.4 Kapanış yargısı

RDP yanal hareketi tespitinde başarı, "daha çok kural" değil, **daha çok bağlam**tır. Elimizdeki gerçek kurallar (`88bf1ccf`, `a9bcd1ab`, `598290cf`) tek tek doğrudur ama her biri savunma zincirinin *bir* halkasıdır. Değeri üreten şey, kaynak IP'yi eksen alıp — canary attempt'ini, süreç ağacını, Type 10 logon'unu, Kerberos recon'unu ve registry hazırlık izlerini kısa bir pencerede üst üste bindirmektir. Saldırgan bu halkalardan birini kırdığında (portu değiştir, tünelle, hash'le gir, logu sustur), her seferinde *başka bir kaynakta* ikinci-derece bir iz bırakır — işi o izi görecek şekilde kurmuş olmaktır. Naif dedektör "RDP oldu mu" sorar; olgun dedektör "bu RDP, bu hesabın, bu kaynaktan, bu hedefe, bu saatte yaptığı *beklenen* şey mi" sorar. Fark, %0.1 TP oranıyla gecelerini harcamakla, sabah gerçek ihlali masasında bulmak arasındaki farktır.
