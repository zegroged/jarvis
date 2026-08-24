# Entra PRT Hırsızlığı ve Device Code Phishing — Tespiti

> Saha notu. Bu metin "PRT nedir" anlatmaz; sinyalleri nasıl bağladığını, tespitin sahada neden bozulduğunu ve triyaj yargısını anlatır. Alan/olay adları orijinal Sigma kurallarından alınmıştır; uydurma yoktur.

---

## 1. Özet: saldırı + naif tespit (kısa)

İki ayrı ama sık sık birleşen tehdit var.

**PRT (Primary Refresh Token) hırsızlığı:** Entra'ya join/registered bir Windows cihazında, `Microsoft.AAD.BrokerPlugin` ve LSASS/CloudAP katmanında tutulan PRT, saldırganın MFA'yı komple atlamasını sağlayan bir "altın anahtardır". PRT'yi ele geçiren saldırgan, kurbanın cihazının bütün SSO oturumlarını taklit edebilir; token yeniden verildikçe (refresh) MFA bir daha sorulmaz. Microsoft bunu tespit için **Identity Protection** tarafında `riskEventType: 'attemptedPrtAccess'` risk olayını üretir (logsource: azure / riskdetection). Naif tespit burada başlar ve biter: "attemptedPrtAccess gördün mü, alarm bas."

**Device Code phishing:** OAuth 2.0 device authorization grant, aslında TV/konsol gibi klavyesiz cihazlar içindir. Saldırgan `microsoft.com/devicelogin` üzerinde meşru bir device code başlatır, kurbana "shu kodu gir" diye sosyal mühendislikle kodu girdirtir; kurban kendi MFA'sıyla onaylar ve token doğrudan saldırganın oturumuna düşer. Sigma tarafında naif tespit: signinlogs içinde `properties.message: Device Code` (logsource: azure / signinlogs). EvilTokens gibi PhaaS kitleri de bu akışı endüstrileştirdi; proxy tarafında `c-uri` üzerinde `*.workers.dev` ve `*.up.railway.app` desenleri yakalanır (logsource category: proxy).

Bu dört Sigma kuralı ("attemptedPrtAccess", "Device Code", "Authentication Methods Policy Update", "User registered security info") sahada **tek başına** kullanıldığında ya kör kalır ya da analisti boğar. Değer, bunları bir zaman-çizgisi üzerinde bağlamakta.

---

## 2. Naif tespit neden yetmez

### 2.1 `attemptedPrtAccess` — düşük hacim ama geç ve dar

Kuralın kendi `falsepositives` notu dürüst: "low-volume, seen infrequently". Kulağa harika geliyor — az gürültü, yüksek değer. Sahadaki gerçek daha çirkin:

- **Bu bir risk detection'dır, ham telemetri değil.** `attemptedPrtAccess`, Microsoft'un kendi buluttaki heuristikleri PRT erişim davranışını "riskli" saydığında üretilir. Yani tetiklenmesi için Microsoft'un modelinin senden önce şüphelenmesi gerekir. ROADtoken / Aadinternals ile yapılan "temiz" PRT çıkarımı, aynı cihaz/aynı IP bağlamında kaldığında bu risk olayını **hiç üretmeyebilir**. Kör nokta: cihazın üstünde local admin olan saldırgan, CloudAP'tan PRT'yi + session key'i alıp kendi makinesinde `x-ms-RefreshTokenCredential` header'ıyla kullandığında, davranış meşru cihaz imzasını taşıdığı için risk skoru düşük kalır.
- **Gecikme.** riskdetection olayları gerçek zamanlı değildir; dakikalar–saatler arası gecikmeyle gelir. Saldırgan PRT ile 60 dakikalık access token'ları çoktan üretmiş, mail kuralı kurmuş, OAuth uygulaması eklemiş olur. Alarm geldiğinde iş bitmiştir.
- **Lisans duvarı.** Identity Protection risk olaylarının tamamına (özellikle `riskEventType` ayrıntısına ve `riskDetections` API'sine) erişim P2 lisansı ister. P1'de bu sinyal ya yok ya güdüktür. Kuralı yazdın ama tenant'ın onu beslemiyorsa tespit kağıt üstünde kalır.

### 2.2 `Device Code` — meşru kullanımın gürültüsü ve mesaj-alanı kırılganlığı

`properties.message: Device Code` selection'ı **authentication method** olarak device code kullanılan her başarılı/başarısız sign-in'i yakalar. Sorun:

- **Meşru device code her yerde.** Azure CLI (`az login --use-device-code`), Azure PowerShell, Teams Rooms, IoT provisioning, headless CI/CD, bazı Linux/macOS kurulum akışları device code flow kullanır. DevOps ağırlıklı bir tenant'ta bu selection tek başına günde yüzlerce satır üretir. Sinyal/gürültü oranı, sıradan bir kurumda bile tek başına takip edilemez.
- **Alan adlandırması kaygan.** `properties.message` alanı, connector/şema sürümüne göre `AuthenticationProtocol == deviceCode` ya da `authenticationProtocol` olarak da görülür. Sentinel'de `SigninLogs` tablosunda bu bilgi `AuthenticationProtocol` sütununda; ham "Device Code" string'i her connector'da birebir bu değeri taşımayabilir. Kuralı motoruna birebir kopyalarsan alan eşleşmezse **sessizce hiç tetiklenmez** — en tehlikeli hata türü.
- **Başarısızlığı görmüyor.** Naif kural sadece "device code kullanıldı" der. Oysa phishing'in imzası, akışın **nereden** başladığıdır: device code'u başlatan client ile onu onaylayan kullanıcı bağlamının uyuşmaması.

### 2.3 `Authentication Methods Policy Update` ve `User registered security info` — kalıcılık, ama meşru IT gürültüsünün içinde

Bu iki kural saldırının **kalıcılık** fazını hedefler: saldırgan çaldığı oturumla yeni bir MFA yöntemi (kendi authenticator'ı, kendi telefonu) ekler ya da CBA (certificate-based auth) gibi passwordless bir arka kapı açar.

- `User registered security info` (`LoggedByService: 'Authentication Methods'`, `Category: 'UserManagement'`), her yeni çalışan onboarding'inde, her telefon değişikliğinde, her "MFA'mı sıfırlayın" help-desk çağrısında meşru olarak tetiklenir. Büyük bir kurumda günde binlerce satır. Tek başına aksiyon alınamaz.
- `Authentication Methods Policy Update` (`OperationName: 'Authentication Methods Policy Update'`, `TargetResources.modifiedProperties|contains: 'AuthenticationMethodsPolicy'`) daha nadirdir ama meşru IT projesi (ör. CBA'yı devreye alma, FIDO2 rollout) sırasında beklenen bir olaydır. CBA'yı ilk kez açan bir tenant admin ile, oturumu çalınmış bir Global Admin arasındaki farkı **bu kural tek başına ayırt edemez.** Kuralın referansı (SpecterOps "Passwordless Persistence") tam da bunu anlatır: CBA, saldırgan için parolasız, MFA'sız, kalıcı erişimdir.

Özet kör nokta: dört kuralın hiçbiri **tekil olayı** güvenle "ihlal" etiketleyemez. Her biri ya geç, ya dar, ya da meşru operasyonel gürültünün içinde boğulur. Değer korelasyonda.

---

## 3. Korelasyon zinciri (asıl değer)

Detection engineer'ın işi tek kuralı keskinleştirmek değil; **zayıf sinyalleri zaman ve bağlam ekseninde birleştirip** yüksek-güvenli bir desen üretmektir. Aşağıdaki iki zincir sahada gerçekten yüksek doğrulukla çalışır.

### 3.1 Zincir A — Device Code phishing → oturum ele geçirme → kalıcılık

Somut olay örgüsü (tek kurban, ~20 dakikalık pencere):

**A) Başlangıç — proxy sinyali:**
Kullanıcı bir phishing linkine tıklar. EvilTokens kuralı devreye girer: proxy loglarında `c-uri` bir Cloudflare Workers (`...-s-account.workers.dev`) veya `...up.railway.app` domainine gider. Tek başına `level: low` — çünkü bu domainler meşru de olabilir. Ama bu, zincirin **T0** damgasıdır.

**B) Kısa pencere içinde, farklı bağlamda — device code sign-in:**
T0'dan sonraki ~1–10 dakika içinde, **aynı kullanıcı** için signinlogs'ta `properties.message: Device Code` ile başarılı bir sign-in belirir. Kritik ayırt edici: bu sign-in'in **client uygulaması** ile kullanıcının cihaz envanterinin uyuşmaması. Tipik phishing imzası:
- `AppDisplayName` çoğu zaman **Microsoft Authentication Broker** ya da **Microsoft Office** (saldırganın hedef aldığı public client id'ler; ör. `29d9ed98-a469-...` Broker, `d3590ed6-...` Office).
- `IPAddress` kullanıcının normal coğrafyasından/ASN'inden farklı (VPS, hosting ASN'i).
- Onaylanan MFA, kullanıcının kendi MFA'sıdır — çünkü kodu **kurban** girmiştir. Yani MFA "başarılı" görünür; bu, olayı meşru sanmanın tuzağıdır.

Tek başına B zayıftır (meşru device code var). Ama **"proxy T0 + aynı kullanıcı + <10 dk + yabancı ASN + Broker/Office client"** birleşimi, tesadüf olasılığını yok denecek kadar düşürür.

**C) Kalıcılık — token sonrası davranış:**
Saldırgan token'ı aldıktan sonra dakikalar içinde:
- `User registered security info` (yeni authenticator ekler) — VEYA
- yüksek yetkili bir hesap ele geçirildiyse `Authentication Methods Policy Update` (CBA açar) — VEYA
- Exchange'de yeni bir inbox/transport kuralı, yeni bir OAuth uygulama consent'i.

**Yüksek-güven kuralı:** `(proxy: workers.dev/railway.app c-uri)` **AND** kısa pencerede `(signinlogs: Device Code, aynı UserPrincipalName, yabancı IPAddress/ASN)` **AND** aynı oturum korelasyon id'si içinde `(auditlogs: User registered security info OR Authentication Methods Policy Update)` = **ihlal, P1.**

Bu üçlü, dördü de `level: low/medium` olan sinyalleri, tek başına hiçbirinin veremeyeceği bir kesinliğe taşır. Bağlayıcı anahtarlar: **UserPrincipalName / UserId** ve sign-in'in **CorrelationId**'si; auditlogs'ta aktörü sign-in'e bağlamak için `InitiatedBy` / `ActorUserId` alanı.

### 3.2 Zincir B — PRT hırsızlığı → cihaz-dışı yeniden kullanım

PRT çalındığında imza daha incedir çünkü token meşru cihaz kimliğini taşır. Zincir:

**A)** `riskdetection: riskEventType: 'attemptedPrtAccess'` — düşük hacimli, yüksek riskli tetik. Bunu **tetikleyici** olarak kullan, sonucun kendisi olarak değil.

**B)** Kısa pencere içinde, **aynı DeviceId** ile ilişkili sign-in'lerde bir çatallanma: aynı `DeviceId` / aynı PRT'den türeyen token, **iki farklı IP/ASN**'den, hatta iki farklı `UserAgent`'tan kullanılıyor (kurbanın gerçek cihazı + saldırganın makinesi). SigninLogs'ta `AuthenticationRequirement`/`DeviceDetail.deviceId` üzerinden aynı cihazın imkânsız-seyahat (impossible travel) deseni.

**C)** Peşi sıra: yeni MFA kaydı (`User registered security info`) veya CBA policy değişikliği (`Authentication Methods Policy Update`).

**Yüksek-güven kuralı:** `attemptedPrtAccess` **AND** aynı DeviceId için kısa pencerede iki ayrı ASN'den başarılı token kullanımı **AND** ardından auth-method değişikliği = **cihaz-dışı PRT yeniden kullanımı, P1.**

Buradaki incelik: `attemptedPrtAccess` gecikmeli gelir. Bu yüzden korelasyonu **geriye dönük** kur — risk olayı düştüğünde, o kullanıcının/cihazın önceki 60–120 dakikasını otomatik zenginleştir (retro-hunt). SOAR playbook'unda "risk geldi → geçmişi tara" adımı olmadan bu zincir kapanmaz.

---

## 4. False positive gerçeği ve triyaj yargısı

Her sinyalin kendi meşru ikizi var. Analistin işi, "alarm var mı" değil, **hangi sırayla bakılacağı**dır.

**`Device Code` false positive kaynakları (en sık → en nadir):**
1. **Azure CLI / PowerShell / DevOps.** `az login --use-device-code`, CI runner'lar, terraform pipeline'ları. İmza: `AppDisplayName = Microsoft Azure CLI` (`04b07795-...`), kaynak IP = kurumsal veri merkezi/bilinen CI ASN'i, kullanıcı = servis/DevOps hesabı. **Triyaj yargısı:** client id `04b07795` + bilinen CI subnet ise otomatik kapat.
2. **Teams Rooms / IoT / headless provisioning.** İmza: cihaz hesabı, tekrar eden düzenli desen, sabit IP.
3. **Meşru kullanıcı, meşru ihtiyaç** (yeni bir CLI aracı deniyor). Nadir ama olur.

**Analistin öncelik sırası — Device Code alarmı geldiğinde:**
1. Client id public/hassas mı? (Broker `29d9ed98`, Office `d3590ed6`, Teams `1fec8e78`) — evetse **öne al**. Azure CLI `04b07795` ise geriye at.
2. IPAddress'in ASN'i hosting/VPS mı, yoksa kurumsal/CI mı?
3. Bu kullanıcı için son 30 günde device code görülmüş mü? İlk kez ise şüphe artar.
4. Kısa pencerede proxy `workers.dev/railway.app` sinyali VAR MI? Varsa — triyaj biter, eskalasyon.

**`User registered security info` false positive:** onboarding dalgaları, help-desk MFA sıfırlama, telefon değişimi. **Triyaj yargısı:** Bu olayı **asla tek başına kovalamaz.** Yalnızca "şüpheli sign-in'in ardından <30 dk içinde geldiyse" öne çıkar. Bağlam: kayıt yapan IP, az önceki sign-in IP'siyle aynı mı? Yeni yöntem, kullanıcının bilinen telefon/authenticator'ından farklı mı?

**`Authentication Methods Policy Update` false positive:** meşru CBA/FIDO2 rollout, güvenlik ekibinin planlı politika değişikliği. **Triyaj yargısı:** Bunu **change management** kaydıyla kesiştir. Planlı bir CBA projesi varsa ve değişikliği yapan bilinen bir kimlik mühendisiyse — beklenen. Değişikliği yapan `InitiatedBy` bir iş kullanıcısı ya da yeni ele geçirilmiş bir admin ise — **kritik.** Bu, tüm listede false-positive oranı en düşük, tekil önceliği en yüksek olan olaydır; çünkü CBA açmak "normal kullanıcı işi" değildir.

**`attemptedPrtAccess` false positive:** bazı EDR/AV ürünlerinin ve meşru araçların (ör. Microsoft'un kendi Defender bileşenleri, bazı yedekleme/yönetim ajanları) LSASS/CloudAP ile etkileşimi risk olayını tetikleyebilir. SCCM/Intune ajanlarının cihaz sağlık taraması da nadiren gürültü üretir. **Triyaj yargısı:** kural notunun dediği gibi hacim düşük; geldiğinde **her zaman** incele, ama önce "bu cihazda bilinen bir güvenlik/yönetim ajanı bu davranışı üretiyor mu" diye whitelist'e bak. Düğüm noktası: erişimin ardından **cihaz-dışı** token kullanımı var mı? Yoksa büyük ihtimalle ajan gürültüsü; varsa ihlal.

Genel yargı ilkesi: **Tek olay = zenginleştir. Kısa pencerede iki bağımsız olay = eskale et. Zincir kapandı = izole et (cihaz + kullanıcı token revoke).**

---

## 5. Kaçınma → karşı-tespit

Saldırgan bu kuralları bildiği için, dokümanlarda yazmayan atlatmaları uygular. İkinci-derece tespitler:

**Kaçınma 1 — Azure CLI client id ile gizlenme.** Saldırgan device code akışını bilerek `04b07795` (Azure CLI) client id'siyle başlatır, çünkü analistlerin bu id'yi otomatik kapattığını bilir. **Karşı-tespit:** client id whitelist'ini **kaynak bağlamıyla birlikte** değerlendir. Azure CLI meşru olarak kurumsal/CI ASN'lerinden gelir; hosting ASN'inden gelen bir "Azure CLI device code" başlı başına anomalidir. Yani beyaz liste "client id" değil, "client id × ASN sınıfı" olmalı.

**Kaçınma 2 — Proxy'siz phishing.** EvilTokens kuralı `workers.dev/railway.app` domainlerine bağlıdır. Saldırgan kendi altyapısını (custom domain, ya da doğrudan `microsoft.com/devicelogin`'e kurbanı SMS/Teams ile yönlendirme) kullanırsa **proxy sinyali hiç oluşmaz.** Bu ciddi bir kör noktadır. **Karşı-tespit:** proxy-bağımsız kal. Zincir A'yı proxy T0 olmadan da çalıştırabilecek şekilde kur: "device code sign-in + yabancı ASN + hassas public client + <30 dk içinde auth-method değişikliği" tek başına yeterli güven verir. Ek olarak, `microsoft.com/devicelogin` ve `login.microsoftonline.com/common/oauth2/deviceauth` URL'lerine **kısa süre içinde çoklu farklı kullanıcıdan** erişim, bir kampanya sinyalidir (proxy domaini değişse de hedef Microsoft URL'i sabittir).

**Kaçınma 3 — MFA yöntemi eklemeden yaşama.** Saldırgan kalıcılık için MFA eklemek yerine sadece uzun-ömürlü refresh token ve OAuth app consent kullanır; böylece `User registered security info` ve `Authentication Methods Policy Update` hiç tetiklenmez. **Karşı-tespit:** kalıcılık faz kuralını genişlet — `Consent to application` / `Add app role assignment grant to user` (auditlogs) ve yeni **inbox rule / transport rule** oluşturma olaylarını da zincirin C halkasına ekle. Auth-method değişikliği kalıcılığın **tek** biçimi değil.

**Kaçınma 4 — attemptedPrtAccess'i hiç tetiklememe.** Cihaz-üstü, aynı IP, aynı kullanıcı bağlamında PRT'yi çıkarıp orada kullanmak (ör. token'ı yerelde kötüye kullanan bir implant) risk olayını üretmeyebilir. **Karşı-tespit:** bulut telemetrisi bu durumda kördür; tespiti **endpoint tarafına** taşı. LSASS'a `Microsoft.AAD.BrokerPlugin` bağlamı dışından erişim, `dsregcmd /status` çağrıları, ROADtoken/Aadinternals imzaları EDR'de aranmalı. Yani PRT hırsızlığının tam kapsamı sadece Entra logu ile kapatılamaz — bu, sınırın dürüst kabulüdür.

**Kaçınma 5 — "impossible travel"i öldürmek.** Saldırgan, kurbanın coğrafyasına yakın bir residential proxy / aynı ülke VPS kullanarak ASN ve geo anomalisini bastırır. **Karşı-tespit:** ASN sınıfını (hosting vs residential vs corporate) ham geo'dan daha çok önemse; ve cihaz parmak izini (UserAgent, `DeviceDetail.browser`, TLS/JA3 varsa) sinyale kat. İki farklı UserAgent'ın aynı PRT/oturumu paylaşması, geo aynı olsa bile güçlü bir sinyaldir.

---

## 6. SIEM/saha gerçeği

### 6.1 Alan eşleme (kuralın yazdığı ≠ tablonda göreceğin)

Sigma kuralları **Sigma taksonomisiyle** yazılır; SIEM'inde alan adları farklıdır. En sık takılınan noktalar:

| Sigma alanı (kuraldaki) | Microsoft Sentinel (KQL) | Elastic (ECS) |
|---|---|---|
| `properties.message` (Device Code) | `SigninLogs.AuthenticationProtocol` / `AuthenticationDetails` | `azure.signinlogs.properties.authentication_protocol` |
| `riskEventType: attemptedPrtAccess` | `AADUserRiskEvents.RiskEventType` / `AADRiskyUsers` | `azure.identity_protection.*` |
| `OperationName` (auditlogs) | `AuditLogs.OperationName` | `azure.auditlogs.operation_name` |
| `TargetResources.modifiedProperties` | `AuditLogs.TargetResources` (dinamik, `mv-expand` gerekir) | `azure.auditlogs.properties.target_resources` |
| `LoggedByService` | `AuditLogs.LoggedByService` | `azure.auditlogs.properties.logged_by_service` |
| `c-uri` (proxy) | `_CL` özel tablo / `CommonSecurityLog.RequestURL` | `url.original` / `url.full` |

**Kritik uyarı:** `properties.message: Device Code` selection'ı Sentinel'de birebir çalışmaz. `SigninLogs` tablosunda "Device Code" bir mesaj string'i değil, `AuthenticationProtocol == "deviceCode"` alan değeridir. Kuralı çevirmeden import edersen **hiç tetiklenmez ve bunu fark etmezsin** — çünkü hata değil, sessiz sıfır sonuç alırsın. Her zaman bir bilinen-pozitif test et (`az login --use-device-code` çalıştır, satırın düştüğünü doğrula).

### 6.2 Varsayılan loglanmayan / gizli boşluklar

- **riskdetection telemetrisi lisans-bağımlı.** `attemptedPrtAccess` gibi ayrıntılı `riskEventType`'lar Entra ID P2 ister. P1'de `AADUserRiskEvents` ya boş ya sınırlıdır. Kuralın var ama besleyen akış yoksa tespit yok.
- **AuditLogs `modifiedProperties` içeriği kısılabilir.** `TargetResources.modifiedProperties` dizisi bazen `oldValue/newValue` maskeler ya da diagnostic setting'de bu alt-alan tam akıtılmaz. `AuthenticationMethodsPolicy` string'i tam gelmeyebilir; `contains` eşleşmesi kaçar.
- **Device code'un *başlatılması* ayrı loglanmaz.** SigninLogs sana device code'un **onaylandığı** anı verir; kodu kimin, nereden **başlattığını** ayrı bir olayla vermez. Bu yüzden "kod nereden üretildi" sorusuna Entra logu tek başına cevap veremez; proxy/network katmanı olmadan başlangıç bağlamı eksik kalır.
- **Proxy logu olmayan kurum.** EvilTokens kuralı `logsource category: proxy` ister. SSL inspection yapmayan ya da roaming/uzaktan çalışan (proxy'den geçmeyen) kullanıcılarda `c-uri` hiç görünmez. Uzaktan çalışma ağırlıklı ortamda bu kural pratikte devre dışıdır — DNS logu ya da EDR network telemetrisiyle telafi et.

### 6.3 Splunk / Sentinel / Elastic farkı

- **Sentinel** Entra için en doğal yer: `SigninLogs`, `AuditLogs`, `AADUserRiskEvents` tabloları connector ile hazır gelir; korelasyonu `join`/`union` + `datetime_diff` ile kurarsın. Zincir A'yı tek KQL'de `SigninLogs` ile `AuditLogs`'u `UserPrincipalName` ve zaman penceresi üzerinden `join` ederek yazabilirsin. Dezavantaj: risk olayları gecikmeli geldiği için near-real-time korelasyonda zaman penceresini (`bin`) geniş tutmak gerekir, bu da maliyet/gürültü dengesi ister.
- **Splunk** Entra verisini genelde Graph API / Azure Monitor add-on ile çeker; alan adları `properties.*` nested JSON olarak gelir, `spath` ile açman gerekir. Korelasyonu `transaction` ya da `stats ... by UserPrincipalName` + zaman penceresiyle kurarsın. Nested `TargetResources` dizisini `mvexpand` gerektirir. Avantaj: proxy/DNS/EDR loglarıyla Entra'yı aynı indekste birleştirmek (cross-source zincir A/B) Splunk'ta esnektir.
- **Elastic** ECS normalizasyonu güçlü ama Entra alan eşlemesi (`azure.signinlogs.*`) integration sürümüne bağlı; sürüm atladığında alan yolu değişebilir. EQL sequence ile "device code sign-in →(30dk)→ auth method register" zincirini `sequence by user.id with maxspan=30m` şeklinde doğrudan yazabilmen en büyük avantajdır — çok-aşamalı deseni ifade etmek Elastic EQL'de en temizidir.

### 6.4 Tuning — pratik reçete

1. **Bilinen-pozitif ile doğrula.** Her kuralı deploy etmeden önce meşru yolla tetikle (device code için `az login --use-device-code`, auth-method için test kullanıcısına yöntem ekle). Satır düşmüyorsa alan eşlemesi bozuktur.
2. **Beyaz listeyi bileşik yap.** Device code için "client id × ASN sınıfı"; asla salt client id ile kapatma.
3. **Tekil kuralları alarm değil, zenginleştirme yap.** `Device Code`, `User registered security info`, `attemptedPrtAccess` tek başına → düşük öncelik / risk skoru artışı. **Zincir kapandığında** → gerçek alarm. SIEM'de bunu risk-based alerting (Splunk RBA / Sentinel Fusion benzeri) ile kur: her zayıf sinyal aynı `UserPrincipalName`'e puan ekler, eşik aşılınca tek yüksek-güven insident doğar.
4. **Retro-hunt otomasyonu.** `attemptedPrtAccess` gecikmeli geldiği için, düştüğünde ilgili kullanıcının/cihazın önceki 2 saatini otomatik çek. Playbook'a "risk geldi → geçmişi zenginleştir" adımını koy.
5. **Yanıtı token seviyesinde ver.** Zincir kapandığında tek başına parola sıfırlama YETMEZ — çalınan refresh token/PRT hâlâ geçerlidir. `Revoke-MgUserSignInSession` (veya portal "Revoke sessions") + cihaz disable + yeni eklenen MFA yöntemini kaldırma birlikte yapılmalı. Aksi halde saldırgan mevcut token ile içeride kalır.

---

## Kapanış yargısı

Bu dört Sigma kuralı sağlamdır ama **hammaddedir.** `attemptedPrtAccess` geç ve lisans-bağımlı; `Device Code` meşru DevOps gürültüsünde boğulur; auth-method kuralları IT operasyonuyla iç içe. Değer, hiçbirini tek başına alarm saymamakta; **UserPrincipalName ve zaman penceresi** ekseninde — proxy başlangıcı, yabancı ASN'li device code sign-in ve ardından gelen auth-method/consent değişikliğini — tek bir yüksek-güvenli zincire dizmekte. Saldırgan client id ve proxy domainiyle oynayarak tekil kuralları atlatır; proxy-bağımsız kalan, kalıcılığı sadece MFA'ya bağlamayan ve PRT'nin cihaz-üstü kaçış senaryosunu endpoint telemetrisiyle telafi eden korelasyon ayakta kalır. Ve her şeyden önce: kuralı motoruna koymadan önce bilinen-pozitifle tetiklediğini gör — çünkü bu ekosistemde en sık kaybedilen tespit, hiç yazılmayan değil, **alan eşlemesi sessizce bozulduğu için hiç tetiklenmeyen** tespittir.
