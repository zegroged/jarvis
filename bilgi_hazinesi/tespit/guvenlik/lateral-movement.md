# Lateral Movement (PsExec / WMI / SMB) — Tespiti

> İlke: "Hırsızı tanımadan mücevheri koruyamazsın." Önce saldırganın ağ içinde nasıl yanlamasına yayıldığını kavramsal olarak anlayacağız, sonra bu hareketin arkasında bıraktığı izleri ve bu izleri gerçek Sigma kurallarına demirleyerek nasıl tespit edeceğimizi işleyeceğiz. Amaç savunma ve tespittir; canlı bir saldırı reçetesi değildir.

Lateral movement (yanlamasına hareket), bir saldırganın ilk eriştiği makineden (initial foothold) başlayarak ağdaki diğer sistemlere sıçraması aşamasıdır. MITRE ATT&CK çerçevesinde bu davranışlar büyük ölçüde `attack.lateral-movement` taktiği altında, özellikle `T1021` (Remote Services), `T1021.003` (Distributed Component Object Model), `T1047` (Windows Management Instrumentation) ve zamanlanmış görev tabanlı hareketlerde `T1053.002` (Scheduled Task) tekniklerine karşılık gelir. Bu doküman PsExec, WMI ve SMB üzerinden gerçekleşen hareketi ele alır — ancak modern tespit yaklaşımının kalbinde, bu tekniklerin altında yatan ortak paydanın **uzaktan RPC (Remote Procedure Call) çağrıları** olduğunu göreceğiz. Verilen gerçek Sigma kuralları da tam olarak bu RPC katmanına odaklanır.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Windows'ta bir makinadan diğerine iş yaptırmanın "meşru" yolları vardır: sistem yöneticileri uzaktaki bir sunucuda servis başlatır, WMI ile envanter sorgular, uzak registry okur, zamanlanmış görev planlar, uzaktan yazıcı yönetir. Bütün bu meşru yönetim kanalları aynı zamanda saldırganın da iştahını kabartan kanallardır. Çünkü saldırgan, yeni bir zafiyet sömürmek yerine, sistemin **zaten var olan ve normal görünen** uzaktan yönetim yeteneklerini ele geçirdiği kimlik bilgileriyle (çalınmış parola hash'i, Kerberos bileti veya düz metin parola) kullanır. Buna "living off the land" denir — arazinin nimetleriyle geçinmek.

Kavramsal olarak saldırganın istismar ettiği şey şudur: Windows'un uzaktan yönetim mimarisi, kimliği doğrulanmış bir kullanıcının uzaktaki makinede **kod çalıştırmasına** izin verir. Saldırgan geçerli bir kimlik ele geçirdiğinde, bu yeteneği kötüye kullanarak hedef makinede kendi komutunu yürütür. Farklı araçlar bu yürütmeyi farklı RPC arayüzleri (interface) üzerinden yapar:

- **PsExec ve benzeri servis tabanlı araçlar:** SMB üzerinden hedefin `ADMIN$` paylaşımına bir çalıştırılabilir dosya kopyalar, ardından **Service Control Manager (SCM)** RPC arayüzünü (MS-SCMR) kullanarak uzaktan bir servis oluşturup başlatır. Servis, saldırganın taşıdığı ikili dosyayı SYSTEM yetkisiyle çalıştırır.
- **WMI / DCOM tabanlı hareket:** Saldırgan, DCOM (Distributed COM) altyapısı üzerinden uzaktaki WMI servisine bağlanır ve `Win32_Process.Create` gibi bir metotla hedef makinede süreç başlatır. Burada SMB paylaşımına dosya yazma adımı olmadan da yürütme mümkündür — bu yüzden daha "sessiz" kabul edilir.
- **Scheduled Task (ATSvc / ITaskSchedulerService):** Saldırgan uzaktan RPC ile hedef makinede zamanlanmış bir görev oluşturur ve tetikler; görev saldırganın komutunu çalıştırır. Bu, MS-TSCH protokolü üzerinden yürür.
- **Remote Registry (MS-RRP):** Uzak registry servisi üzerinden `Run` anahtarları, servis tanımları veya kod yürütmeye yol açabilecek değerler yazılabilir.
- **Remote Printing (MS-RPRN / MS-PAR):** Yazıcı spooler protokolünün kötüye kullanımı (örneğin PrintNightmare bağlamında) hem kimlik zorlaması hem de kod yürütme için bir kaldıraç olabilir.

Ortak nokta şudur: Hepsi, kaynak makineden hedef makineye giden **uzaktan RPC çağrılarıdır** ve her biri kendine özgü bir **interface UUID**'si ile tanımlanır. İşte savunmanın altın anahtarı budur: Aracın adı (PsExec mi, Impacket mi, yerli bir betik mi) değişse de, kablonun üzerinden geçen RPC arayüzü ve OpNum (operasyon numarası) değişmez. Saldırgan aracını değiştirse bile protokolü değiştiremez. Biz de tespiti araç ismine değil, protokol seviyesine demirlersek dayanıklı bir savunma kurmuş oluruz.

Bu bölümde bilinçli olarak adım adım komut dizisi vermiyoruz; amaç saldırganın **niyetini ve kavramsal mekaniğini** anlamak, ardından bu mekaniğin kaçınılmaz olarak bıraktığı izlere geçmektir.

---

## 2. Bıraktığı izler / artefaktlar

Yanlamasına hareket, "sessiz" olduğu iddia edilse bile Windows telemetrisinde zengin izler bırakır. Bu izleri katman katman inceleyelim.

### 2.1 Kimlik doğrulama ve oturum izleri (Security log)

Uzaktan bir makineye erişim, hedef makinede bir **oturum açma (logon)** olayı üretir:

- **Event ID 4624** (An account was successfully logged on) — özellikle **Logon Type 3** (Network) uzaktan ağ tabanlı erişimi, **Logon Type 2** (Interactive) yerel oturumu gösterir. PsExec/WMI hareketi tipik olarak Type 3 üretir.
- **Event ID 4625** — başarısız oturum açma; parola püskürtme (password spraying) veya yanlış kimlikle deneme sinyali.
- **Event ID 4672** (Special privileges assigned) — yeni oturuma yönetici düzeyi ayrıcalıkların atanması. Kısa aralıkla çok sayıda farklı hedefte aynı hesap için görülmesi kayda değerdir.
- **Event ID 4776 / 4768 / 4769** — NTLM doğrulama ve Kerberos TGT/TGS istekleri; kimlik bilgisi kullanım desenini gösterir.

Tek başına bir 4624 masumdur; ama tek bir kaynak hesabın kısa sürede **birçok farklı hedefte** Type 3 oturumu açması, klasik "one-to-many" yayılma desenidir.

### 2.2 PsExec / servis tabanlı hareketin izleri

- **Event ID 7045** (System log — A new service was installed) — uzaktan oluşturulan servis. PsExec varsayılanı olan `PSEXESVC` klasik bir işaret olsa da, saldırganlar servis adını rastgele değiştirir; bu yüzden isme değil, **kısa ömürlü / rastgele adlı / anormal ikili yolu olan servislere** bakılır.
- **Event ID 4697** (Security log — A service was installed by the system) — 7045'in Security log karşılığı, denetim politikası açıksa.
- **Event ID 4688** (Process creation) veya Sysmon **Event ID 1** — hedef makinede `services.exe` altında beklenmedik bir çocuk süreç (örneğin `cmd.exe`, `powershell.exe`, `rundll32.exe`).
- **SMB / ADMIN$ paylaşım erişimi:** Sysmon **Event ID 11** (FileCreate) hedefin `\Windows\` dizinine yazılan ikili; **Event ID 5140 / 5145** (Security — A network share object was accessed) `ADMIN$` veya `C$` paylaşımına erişim.
- Ağda: SMB üzerine (TCP 445) ardından servis kontrolüne dair RPC trafiği.

### 2.3 WMI / DCOM izleri

- Hedefte üst süreç olarak **`WmiPrvSE.exe`** altında doğan komut satırı süreçleri (4688 / Sysmon 1). `WmiPrvSE.exe` çocuğu olarak `cmd.exe` veya `powershell.exe` görülmesi güçlü bir sinyaldir.
- **Microsoft-Windows-WMI-Activity/Operational** logunda operasyon kayıtları.
- DCOM/RPC seviyesinde, aşağıdaki tespit bölümünde detaylandıracağımız belirli interface UUID'lerine yapılan uzak çağrılar.

### 2.4 Scheduled Task izleri

- **Event ID 4698** (A scheduled task was created), **4702** (updated), **4699** (deleted) — Security log.
- **Microsoft-Windows-TaskScheduler/Operational** logunda **Event ID 106 / 140 / 141 / 200 / 201** görev kayıt ve yürütme olayları.
- RPC seviyesinde: MS-TSCH protokolünün **ATSvc** (`1ff70682-0a51-30e8-076d-740be8cee98b`) ve **ITaskSchedulerService** (`86d35949-83c9-4044-b424-db363231fd0c`) arayüzlerine uzak çağrılar.

### 2.5 Remote Registry izleri

- **Event ID 4657** (A registry value was modified) — denetim açıksa.
- RPC seviyesinde MS-RRP arayüzü (`338cd001-2244-31f1-aaaa-900038001003`).

### 2.6 Komut satırı ve süreç desenleri

- `WmiPrvSE.exe` veya `services.exe` altında kodlanmış (`-enc`, `-EncodedCommand`) PowerShell komutları.
- `rundll32.exe`, `regsvr32.exe`, `mshta.exe` gibi ikililerin ağ oturumunun hemen ardından tetiklenmesi.
- Kısa zaman penceresinde: uzak oturum → dosya yazımı → servis/görev oluşturma → süreç yürütme zincirinin **aynı korelasyon anahtarı** (kaynak IP, hedef host, hesap) altında sıralanması.

Bu izlerin en değerlisi, tek tek olaylar değil, bunların **zaman ve kimlik ekseninde zincirlenmesidir**. Şimdi bu zinciri gerçek Sigma kurallarına demirleyelim.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Verilen beş Sigma kuralının hepsinin ortak bir tasarım felsefesi vardır ve bu felsefe tespit stratejimizin belkemiğidir. Hepsi şu `logsource`'u kullanır:

```
logsource:
    product: rpc_firewall
    category: application
```

Yani bu kurallar Windows'un standart Security/System loglarına değil, **RPC Firewall** adlı özel bir kontrole dayanır. RPC Firewall (Zero Networks tarafından geliştirilen açık kaynak araç), tüm süreçlere uygulanarak belirli RPC arayüzlerine yapılan çağrıları denetler (audit) ve gerektiğinde bloklar. Ürettiği log kaydında `EventLog: RPCFW` ve `EventID: 3` (bir RPC çağrısının denetlendiği/bloklandığı olay) alanları bulunur. Ayırt edici alan ise **`InterfaceUuid`**'dir — hangi RPC arayüzüne çağrı yapıldığını söyler. Bazı kurallar ek olarak **`OpNum`** (arayüz içindeki hangi operasyon) alanıyla daralır.

Bu yaklaşımın dehası şudur: Saldırgan PsExec yerine Impacket, Impacket yerine kendi yazdığı bir aracı kullanabilir; süreç adını, servis adını, dosya adını değiştirebilir. Ama uzaktan bir zamanlanmış görev oluşturmak istiyorsa **MS-TSCH arayüzünü** çağırmak, uzaktan WMI ile süreç başlatmak istiyorsa **DCOM/IRemUnknown arayüzlerini** çağırmak zorundadır. Interface UUID protokolün kimliğidir ve değiştirilemez. Bu yüzden UUID tabanlı tespit, araç tabanlı imza tespitinden çok daha dayanıklıdır.

### 3.1 Kurallardaki somut demir noktaları

Verilen kurallardan çıkardığımız gerçek alan ve değerler:

| Teknik | Sigma başlığı | InterfaceUuid | Ek alan |
|---|---|---|---|
| Scheduled Task (ATSvc) | Remote Schedule Task Lateral Movement via ATSvc | `1ff70682-0a51-30e8-076d-740be8cee98b` | EventID 3 |
| Scheduled Task (ITaskSchedulerService) | ...via ITaskSchedulerService | `86d35949-83c9-4044-b424-db363231fd0c` | EventID 3 |
| Remote Printing | Remote Printing Abuse for Lateral Movement | `12345678-1234-abcd-ef00-0123456789ab` ve `76f03f96-cdfd-44fc-...` | EventID 3 |
| DCOM / WMI | Remote DCOM/WMI Lateral Movement | `4d9f4ab8-7d1c-11cf-861e-0020af6e7c57`, `99fcfec4-5260-101b-bbcb-00aa0021347a`, `000001a0-0000-0000-c000-000000000046` | EventID 3 |
| Remote Registry | Remote Registry Lateral Movement | `338cd001-2244-31f1-aaaa-900038001003` | OpNum 6 (ve devamı) |

MITRE eşlemesi de kurallardan gelir: DCOM/WMI kuralı `attack.t1021.003` ve `attack.t1047` etiketli; Scheduled Task kuralları `attack.t1053` / `attack.t1053.002` etiketli; Remote Registry kuralı `attack.t1112` (Modify Registry) ve `attack.persistence` içerir.

### 3.2 Tespit mantığının Türkçe açıklaması

Bir Sigma kuralının `detection` bloğu şu iskeleti izler: bir `selection` tanımlanır (aranan alan-değer koşulları), sonra `condition` bu seçimin nasıl değerlendirileceğini söyler. Örneğin DCOM/WMI kuralında mantık şudur: "RPCFW logunda, EventID 3 olan ve InterfaceUuid alanı şu üç değerden **herhangi biri** olan bir kayıt görürsen alarm ver." Buradaki üç UUID sırasıyla DCOM'un `IRemoteSCMActivator` / `IRemUnknown` / `IObjectExporter` gibi çekirdek aktivasyon arayüzlerine karşılık gelir; bunlara uzaktan yapılan çağrı, uzak nesne oluşturma (dolayısıyla WMI ile uzak süreç yaratma) niyetinin protokol izidir.

Remote Registry kuralı bir adım daha inceltir: yalnızca UUID eşleşmesi değil, aynı zamanda **`OpNum: 6`** ve devamı koşulunu koyar. OpNum, arayüz içindeki spesifik fonksiyonu belirtir; MS-RRP'de belirli OpNum'lar değer yazma / anahtar oluşturma gibi **durum değiştiren** işlemlere karşılık gelir. Böylece salt registry okuma gürültüsünü eleyip, kod yürütmeye yol açabilecek yazma işlemlerine odaklanılır.

### 3.3 Sigma-benzeri basit tespit mantığı örnekleri

**Örnek 1 — Uzaktan zamanlanmış görev ile yanlamasına hareket (ATSvc):**

```yaml
title: Uzaktan Scheduled Task ile Lateral Movement (ATSvc)
status: experimental
logsource:
    product: rpc_firewall
    category: application
detection:
    selection:
        EventLog: RPCFW
        EventID: 3
        InterfaceUuid: '1ff70682-0a51-30e8-076d-740be8cee98b'
    condition: selection
level: high
tags:
    - attack.lateral-movement
    - attack.execution
    - attack.t1053.002
```

Mantık: RPC Firewall, ATSvc arayüzüne (`1ff70682-...`) yapılan uzak bir çağrıyı EventID 3 ile kaydettiğinde alarm üretilir. Bu arayüze uzaktan çağrı, normal iş istasyonu-sunucu trafiğinde nadirdir; çünkü zamanlanmış görevler genellikle yerel olarak veya GPO ile yönetilir, ham RPC ile uzaktan değil.

**Örnek 2 — DCOM/WMI çekirdek aktivasyon arayüzlerine uzak çağrı:**

```yaml
title: Uzaktan DCOM/WMI Aktivasyonu (Lateral Movement)
status: experimental
logsource:
    product: rpc_firewall
    category: application
detection:
    selection:
        EventLog: RPCFW
        EventID: 3
        InterfaceUuid:
            - '4d9f4ab8-7d1c-11cf-861e-0020af6e7c57'
            - '99fcfec4-5260-101b-bbcb-00aa0021347a'
            - '000001a0-0000-0000-c000-000000000046'
    condition: selection
level: high
tags:
    - attack.lateral-movement
    - attack.t1021.003
    - attack.t1047
```

Mantık: Bu üç UUID'den herhangi birine uzak RPC çağrısı, DCOM üzerinden uzak nesne aktivasyonuna işaret eder; bu da WMI ile uzak süreç yaratmanın altyapısıdır. `condition: selection` ile listedeki herhangi bir eşleşme alarmı tetikler (Sigma'da liste değerleri OR mantığıyla değerlendirilir).

### 3.4 RPC Firewall telemetrisi yoksa: yerli log alternatifi

RPC Firewall her ortamda kurulu olmayabilir. Bu durumda aynı davranışı yerli Windows/Sysmon loglarıyla **yaklaşık** olarak yakalayabiliriz (kesinlik biraz düşer, korelasyon gerekir):

- **Scheduled Task hareketi:** Security log **4698** (görev oluşturma) + oluşturan oturumun **Logon Type 3** (4624) olması → uzaktan görev oluşturma.
- **WMI hareketi:** Sysmon **Event ID 1** ile üst süreci `WmiPrvSE.exe` olan `cmd.exe`/`powershell.exe`.
- **PsExec/servis hareketi:** System **7045** (yeni servis) + hedefe kısa süre önce **4624 Type 3** + `ADMIN$` erişimi (5140/5145).

Bu yerli sinyaller RPC Firewall kadar keskin değildir ama korelasyonla güçlü bir ikincil hat oluşturur.

---

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırgan tespiti nasıl atlatmaya çalışır

**Araç ve isim değiştirme:** Saldırganın ilk refleksi imza kaçırmaktır — PsExec yerine Impacket'in `smbexec`/`wmiexec`/`atexec` modüllerini, servis adı olarak rastgele diziler, dosya adı olarak meşru görünen isimler kullanır. Ancak burada RPC-UUID tabanlı tespitin gücü ortaya çıkar: araç ve isim değişse de çağrılan **interface UUID ve OpNum sabittir**. Saldırgan `atexec` kullansa da ATSvc UUID'sini (`1ff70682-...`) çağırmaktan kaçamaz. Bu yüzden UUID tabanlı kurallar bu kaçınmaya karşı dirençlidir.

**"Living off the land" ve meşru araçlarla karışma:** Saldırgan, sysadmin'lerin de kullandığı WMI/scheduled task kanallarını kullanarak gürültünün içinde saklanmaya çalışır. Karşı önlem, **kaynak-hedef ve hesap bağlamını** değerlendirmektir: Bir sunucudan iş istasyonlarına doğru WMI süreç yaratma, veya bir kullanıcı iş istasyonundan onlarca hedefe kısa sürede giden RPC çağrıları anomalidir. Tespit mantığına "kaynak, yönetim altyapısı IP havuzunun dışında mı?" filtresi eklemek false positive'i düşürüp gerçek hareketi öne çıkarır.

**Protokol çeşitlendirme:** Bir kanal izleniyorsa saldırgan diğerine geçer — ATSvc bloklanmışsa ITaskSchedulerService'e, o da izleniyorsa DCOM'a. Bu yüzden verilen kural setinin **hepsini birlikte** devreye almak önemlidir; tek bir arayüzü izlemek, saldırganı yan kanala yönlendirmekten öteye geçmez. Beş kural bir arada, uzaktan yürütmenin başlıca RPC yollarını kapatır.

**Zamana yayma (low and slow):** Korelasyon eşiklerinin altında kalmak için saldırgan hareketleri günlere yayabilir. Karşı önlem, eşik tabanlı kuralların yanında **davranışsal temel çizgi (baseline)** tutmak: "Bu hesap daha önce hiç uzaktan görev oluşturmamıştı" gibi ilk-görülme (first-seen) mantığı, tek bir olayı bile anlamlı kılar.

**Denetim/RPC Firewall'ı devre dışı bırakma:** Saldırgan yeterli yetki alırsa RPC Firewall'ı veya denetim politikalarını kapatmayı deneyebilir. Bu nedenle telemetri kaynaklarının kendisinin bütünlüğü izlenmeli (servis durdurma 7045/7040 olayları, denetim politikası değişikliği 4719) ve loglar merkezî SIEM'e gerçek zamanlı akıtılmalı ki yerel silme etkisiz kalsın.

### 4.2 Savunmacının karşı hamleleri

- **Kural setini bütün olarak uygula:** Verilen beş kuralı (ATSvc, ITaskSchedulerService, Remote Printing, DCOM/WMI, Remote Registry) birlikte devreye alarak yanal yürütmenin ana RPC yollarını kapsa.
- **Segmentasyon ve RPC Firewall'ı `action:block` moduna alma:** Kural tanımlarındaki `audit:true action:block` ifadesi, sadece görmekle kalmayıp bloklama seçeneğini de sunar. Meşru yönetim trafiği belirli kaynaklardan geldiği için, yönetim istasyonları dışından gelen bu arayüz çağrılarını bloklamak hem tespit hem önleme sağlar.
- **Korelasyon kuralları:** Tekil RPCFW olaylarını, aynı korelasyon anahtarı altındaki 4624 Type 3 + 7045/4698 + süreç yaratma zinciriyle birleştirerek yüksek güvenli alarm üret.
- **Kimlik hijyeni:** Tiered administration (katmanlı yönetim) ile ayrıcalıklı hesapların iş istasyonlarında oturum açmasını engelle; bu, hash/bilet çalma sonrası yayılmayı kaynağında zorlaştırır.

### 4.3 Tipik false positive kaynakları ve nasıl ayıklanır

RPC arayüzleri meşru amaçlarla da kullanılır; bu yüzden kör alarm gürültü üretir. Başlıca yanlış pozitif kaynakları:

- **Yönetim ve envanter araçları:** SCCM/MECM, Tanium, PDQ Deploy, Ansible/WinRM tabanlı otomasyon uzaktan WMI ve scheduled task kullanır. Bunlar sürekli DCOM/WMI ve ATSvc çağrıları üretir. **Ayıklama:** Bu araçların çalıştığı yönetim sunucularının kaynak IP/host'larını bir allowlist'e alıp kuraldan `filter` ile düş; kalan çağrılar beklenmedik kaynaklardan gelir.
- **Yazılım dağıtımı ve yama pencereleri:** Bakım pencerelerinde toplu servis kurulumu (7045) ve görev oluşturma artar. **Ayıklama:** Zaman bağlamı ekle; onaylı değişiklik pencerelerini korelasyonda hesaba kat.
- **Yedekleme ve izleme ajanları:** Bazı yedekleme/monitoring çözümleri uzak registry ve WMI'ye erişir. **Ayıklama:** Bilinen ajan hesaplarını ve süreçlerini tanımlayıp temel çizgiye dahil et.
- **Baskı/print sunucuları:** Remote Printing kuralı (`MS-RPRN/MS-PAR`), meşru yazıcı sunucusu trafiğinde tetiklenebilir. **Ayıklama:** Print server rolündeki sunucuları kaynak/hedef olarak muaf tut; asıl ilgi, print rolü olmayan makinelere veya makinelerden gelen spooler RPC çağrılarıdır.
- **Domain Controller ve altyapı gürültüsü:** DC'ler doğaları gereği yoğun RPC üretir. **Ayıklama:** DC'ler için ayrı, daha dar baseline kullan; iş istasyonu-iş istasyonu (peer-to-peer) hareketine düşük tolerans, sunucu-sunucu meşru trafiğe daha yüksek tolerans uygula.

Ayıklamanın altın kuralı: **allowlist'i kaynağa göre kur, kuralı olduğu gibi bırak.** Yani UUID tabanlı geniş yakalamayı koru, ardından bilinen meşru kaynakları `filter` ile ele. Böylece saldırganın yeni/beklenmedik bir kaynaktan yaptığı aynı çağrı elenmeden alarm üretir — çünkü saldırgan meşru yönetim sunucusunun kimliğini ve konumunu taklit etmek zorunda kalır, bu da onun için ek bir engel ve ek bir iz demektir.

---

### Özet

Yanlamasına hareketin tespitinde kritik içgörü, aracın adına değil **protokolün kimliğine** demirlenmektir. PsExec, WMI ve SMB tabanlı hareketlerin hepsi, arka planda sabit **RPC interface UUID**'lerine yapılan uzak çağrılardır. Verilen gerçek Sigma kuralları bu felsefeyi somutlaştırır: `product: rpc_firewall`, `EventID: 3` ve belirli `InterfaceUuid` / `OpNum` değerleriyle — ATSvc, ITaskSchedulerService, DCOM/WMI, Remote Registry ve Remote Printing yollarını kapsayarak. Bu kuralları bütün olarak devreye alıp, kaynak-hedef-hesap bağlamıyla korelasyon kurmak ve meşru yönetim kaynaklarını allowlist ile ayıklamak, hem dayanıklı hem düşük gürültülü bir tespit hattı verir. Hırsızın hangi kılığa girerse girsin geçmek zorunda olduğu kapıyı — RPC arayüzünü — izleyerek mücevheri koruruz.
