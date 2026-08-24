# Golden SAML (AD FS Federasyon) — Tespit

> Detection engineer / SOC lead notu. Amaç "Golden SAML nedir" anlatmak değil; sinyalleri **birbirine bağlamak**, naif tespitin gerçekte **neden çöktüğünü** göstermek ve sahada işe yarayan **yargıyı** aktarmaktır.

---

## 1. Özet: saldırı + naif tespit (kısa)

Golden SAML, saldırganın AD FS token imzalama sertifikasının **özel anahtarını** ele geçirip, kimlik sağlayıcının (IdP) yerine geçerek istediği kullanıcı/claim için **geçerli SAML token'ları ürettiği** bir kimlik sahtekârlığıdır. Kerberos'taki Golden Ticket'in federasyon dünyasındaki karşılığıdır: krbtgt yerine **AD FS Token Signing sertifikası** çalınır. Anahtar bir kez ele geçince saldırgan Azure AD / Microsoft 365 / SAML güvenen (relying party) her uygulamaya, **hiçbir parola girmeden, MFA'ya takılmadan**, istediği kimlikle içeri girer. SolarWinds/UNC2452 kampanyasının imza tekniğiydi.

İki temel edinim yolu vardır ve tespit açısından ikisi taban tabana zıttır:
- **On-prem yol:** AD FS sunucusunun konfigürasyon DB'sinden (WID — Windows Internal Database) DKM anahtarını ve şifreli imza sertifikasını çekmek (ör. `ADFSDump`, Mimikatz). Bu diskte/sunucuda iz bırakır.
- **Bulut yolu (çok daha sinsi):** AD FS sunucusuna **hiç dokunmadan**, Azure AD Connect Health / Hybrid Health servisini kötüye kullanıp **sahte bir AD FS sunucu örneği** kaydederek imza loglarını buluta enjekte etmek (o365blog "hybridhealthagent"). Bu, on-prem log kaynağınızı tümüyle atlar.

Naif tespit refleksi genelde şudur: "SAML Token Issuer Anomaly kuralı (`riskEventType: tokenIssuerAnomaly`) zaten var, Entra ID Protection yakalar" veya "AD FS event log'unda EventID 1200/1202 imza olaylarını izlerim". İkisi de tek başına yeterli değildir ve neden yetmediği bu metnin asıl konusu.

---

## 2. Naif tespit neden yetmez

**a) `tokenIssuerAnomaly` bir sonuç sinyalidir, kaynak değil.** `SAML Token Issuer Anomaly` kuralı (`e3393cba-31f0-4207-831e-aef90ab17a8c`, logsource `product: azure / service: riskdetection`, `riskEventType: 'tokenIssuerAnomaly'`, T1606) çok değerlidir ama Microsoft tarafında **kapalı-kutu heuristik** ile üretilir. Ne zaman tetikleyeceğini siz kontrol etmezsiniz; token'daki claim'ler, imza zamanı, authnmethod alanı "olağandışı" göründüğünde çalışır. İyi hazırlanmış bir Golden SAML — gerçek kullanıcının normal claim setini, doğru `AuthnContextClassRef` değerini, makul `IssueInstant`'ı taklit ederse — bu anomaliyi **hiç tetiklemeyebilir**. Yani düşük FP'li ama düşük recall'lı bir sinyaldir. Kaçıranı hiç bilmezsiniz. Buna tek başına yaslanmak "yakaladıysa yakaladık" demektir.

**b) On-prem imza olayları kör noktadır.** Golden SAML token'ı AD FS sürecinin **dışında**, çalınan anahtarla offline üretilir. Dolayısıyla AD FS'in kendi EventID 1200/1202/307 imza olaylarında **hiçbir kayıt oluşmaz** — token'ı sizin AD FS'iniz imzalamadı, saldırgan imzaladı. "AD FS imza loglarını izliyorum" cümlesi bu saldırıya karşı yanlış güven verir. Görebileceğiniz tek şey, o token relying party'ye (Azure AD) sunulduğunda **bulut tarafındaki** oturum açma kaydıdır ve orada da imza geçerli göründüğü için normal görünür.

**c) Bulut yol on-prem telemetriyi tamamen atlar.** Hybrid Health üzerinden sahte sunucu kaydı (`Microsoft.ADHybridHealthService`) yapıldığında saldırgan AD FS diskine, WID'ine, registry'sine **hiç dokunmaz**. Sysmon named pipe kuralınız (`1ea13e8c`), registry SACL kuralınız (`ff151c33`), ADFSDump imzalarınız — hepsi **sessiz** kalır. Tek iz Azure Activity log'undadır ve o log çoğu kurumda ya toplanmaz ya da "gürültülü admin aktivitesi" diye kenara atılır.

**d) MFA ve Conditional Access bypass edilir, dolayısıyla kimlik sinyalleri de yanıltıcıdır.** Token içinde `multipleauthn`/`mfa` claim'i saldırgan tarafından enjekte edildiği için oturum "MFA yapılmış" görünür. "MFA'sız giriş yakalarım" mantığı çalışmaz; tersine, **imkânsız MFA** (kullanıcı MFA prompt'u almadı ama token MFA claim'i taşıyor) asıl ipucudur ve bunu görmek AD FS log ile Entra sign-in log'unu **çapraz** okumayı gerektirir.

**e) False positive selleri gerçek engel.** Aşağıdaki tekil kuralların hepsi tek başına gürültülüdür:
- Named pipe / WID erişimi → yedekleme ajanları, AD FS'in kendi servis hesabı, konfigürasyon değişikliği.
- Registry SACL erişimi (`MonitoringAgent`) → Health ajanının kendi meşru okumaları.
- Hybrid Health servis üyesi oluşturma → gerçek AD FS sunucusu ekleme, DR tatbikatı, Connect kurulumu.

Bu yüzden mesele "bir kural yazmak" değil, **hangi olayların aynı olayın parçaları olduğunu** bilmek.

**f) Federasyon güveninin genişliği tespiti değersizleştiriyor sanrısı.** SOC'lerin bir kısmı "AD FS emekli oluyor, PTA/managed'a geçiyoruz, bu risk kapanıyor" der. Yanlış. Federasyon domain tenant'ta **hâlâ tanımlıysa**, token-signing güveni geçerli olduğu sürece Golden SAML çalışır; hatta kullanılmayan, kimsenin izlemediği eski bir federasyon domaini **en tehlikeli** olandır çünkü baseline'ınız yoktur. `Get-MgDomainFederationConfiguration` / `Get-MsolDomainFederationSettings` ile tenant'taki tüm federasyon ayarlarını periyodik envanterleyip, `IssuerUri` ve imza sertifikası thumbprint'i için bir **altın kopya** tutmak başlı başına bir tespit kontrolüdür: beklenmedik `IssuerUri` değişikliği veya yeni federasyon domaini, en temiz Golden SAML habercilerinden biridir.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek-güven için **çok-aşamalı, farklı log kaynağını birbirine dokuyan** desen gerekir. İki ayrı senaryo için iki ayrı zincir kuruyorum.

### Zincir A — On-prem anahtar hırsızlığı (klasik Golden SAML)

**A1. Config DB erişimi (Collection).** `ADFS Database Named Pipe Connection By Uncommon Tool` (`1ea13e8c-03ea-409b-877d-ce5c3d2c1cb3`, logsource `product: windows / category: pipe_created`, Sysmon **EventID 17/18**, T1005/attack.collection). WID'e giden named pipe'a (`\\.\pipe\microsoft##wid\tsql\query` benzeri) **AD FS servis process'i dışında** bir araçtan bağlantı. Tek başına: DBA aracı, yedekleme olabilir.

**A2. + kısa pencere içinde imza sertifikasına erişim işareti.** Aynı hostta, dakikalar içinde:
- `MonitoringAgent` registry anahtarına erişim: `Azure AD Health Monitoring Agent Registry Keys Access` (`ff151c33`, **EventID 4656/4663**, `ObjectType: 'Key'`, `ObjectName` = `\REGISTRY\MACHINE\SOFTWARE\Microsoft\Microsoft Online\Reporting\MonitoringAgent`, T1012). SACL yapılandırılmışsa.
- veya PowerShell/LSASS üzerinden DKM master key okuma, `lsass` erişimi (Sysmon EID 10) AD FS servis hesabı bağlamında.

**A3. + farklı bağlamda: aynı kimlikle beklenmedik yönetimsel hareket veya lateral.** İmza sertifikası çalan aktör aynı oturumda genelde ya DC'ye ya da Azure AD Connect sunucusuna dokunur.

**A4. Sonuç sinyali (saatler/günler sonra, farklı log kaynağı):** Entra sign-in / `tokenIssuerAnomaly` **veya** "MFA claim'i taşıyan ama karşılık gelen Azure MFA kaydı olmayan" federasyon girişi.

**Somut kural cümlesi:** *host X'te (AD FS sunucusu) `pipe_created` uncommon-tool WID bağlantısı (A1) **+ 30 dk pencere** `4663 ObjectName ...MonitoringAgent` (A2) + aynı `SubjectUserName` DA-olmayan bir hesap = **P1 olası imza-anahtarı hırsızlığı**.* Bu üçlü, ayrı ayrı her biri gürültülü olan sinyalleri, birlikte görülünce FP oranını neredeyse sıfıra indirir; çünkü meşru yedekleme A1'i yapar ama A2'yi **aynı process/aynı kullanıcı bağlamında** yapmaz.

### Zincir B — Bulut yol (Hybrid Health sahte sunucu) — **atlatmanın atlatması**

Saldırgan on-prem'e hiç dokunmaz. Buradaki değer, tek sinyalin çok güçlü ama nadir ve bu yüzden gözden kaçan bir dizide olması:

**B1. Sahte AD FS sunucu örneği oluşturma/güncelleme.** `Azure Active Directory Hybrid Health AD FS New Server` (`288a39fc-4914-4831-9ada-270e9dc12cb4`, logsource `product: azure / service: activitylogs`, T1578/attack.defense-impairment):
```
CategoryValue: 'Administrative'
ResourceProviderValue: 'Microsoft.ADHybridHealthService'
ResourceId|contains: 'AdFederationService'
OperationNameValue: 'Microsoft.ADHybridHealthService/services/servicemembers/action' (servicemembers/...)
```

**B2. + kısa pencere sonra aynı servisin silinmesi (iz temizleme).** `Azure Active Directory Hybrid Health AD FS Service Delete` (`48739819-8230-4ee3-a8ea-e0289d1fb0ff`, T1578.003):
```
OperationNameValue: 'Microsoft.ADHybridHealthService/services/delete'
```
Aktör sahte sunucuyu spoof loglarını enjekte etmek için kurar, işi bitince siler.

**B3. Bağlam: bu işlemi yapan kimlik gerçek AD FS admini mi?** B1/B2'yi tetikleyen `Caller` / initiating user, tenant'ta **daha önce hiç ADHybridHealthService yazmamış** bir servis principal veya kullanıcı ise güven fırlar.

**Somut kural cümlesi:** *`servicemembers/action` (B1) **+ 24 saat içinde** aynı `AdFederationService` ResourceId için `services/delete` (B2) + `Caller` son 90 günde bu ResourceProvider'a hiç yazmamış = **P1 sahte federasyon telemetri enjeksiyonu**.* Oluştur-kullan-sil deseni meşru operasyonda neredeyse hiç görülmez; gerçek sunucu ekleme kalıcıdır.

### Zincir C — Baseline sapması (imza altyapısının kendisini izle)
En sessiz ama en yüksek-değerli zincir, olay-tabanlı değil **durum-tabanlıdır**:

**C1.** Tenant federasyon config snapshot'ı (günlük): `IssuerUri`, `SigningCertificate` thumbprint, `PassiveLogOnUri`, federated domain listesi.

**C2.** Herhangi bir alanın **planlı change olmadan** değişmesi. Özellikle yeni bir `IssuerUri` veya ikinci bir imza sertifikasının eklenmesi — saldırgan kendi sertifikasını **ek** güven olarak koyarsa mevcut token'lar bozulmadan kendi token'ı da geçerli olur; bu, sertifika hırsızlığından bile sinsi bir varyanttır.

**C3.** + eşzamanlı yüksek-ayrıcalıklı rol ataması veya yeni servis principal kimlik bilgisi (`Add servicePrincipal credentials` — Azure AD Audit). Federasyon oynanışı çoğu zaman bir kimlik-kalıcılığı adımıyla birlikte gelir.

**Kural cümlesi:** *federasyon `IssuerUri`/thumbprint altın-kopyadan sapma (C2) + 24 saat içinde `Update application – Certificates and secrets` veya yeni SP credential (C3) + değişiklik CAB kaydıyla eşleşmiyor = **P1 federasyon güven manipülasyonu**.* Bu zincir AD FS event'ine hiç bakmaz; tenant konfigürasyonunun kendisini kaynak-of-truth yapar ve hem on-prem hem bulut yolunu tek noktada yakalar.

### Zincirlerin ortak dersi
Golden SAML'da **tek bir "smoking gun" event yoktur**. Değer, *edinim (A1/A2 veya B1) → kullanım (sahte token) → sonuç (tokenIssuerAnomaly / imkânsız MFA)* üçlüsünü **farklı log kaynakları arasında** aynı entity (host, hesap, ResourceId, kullanıcı) etrafında birleştirmekte. SIEM'de bunu entity-based korelasyon veya risk skoru toplama (her sinyal +N puan, eşik aşınca alarm) ile modellersiniz.

---

## 4. False positive gerçeği ve triage yargısı

Her sinyalin meşru ikizi vardır. Analist önceliklendirmesi:

| Sinyal | Klasik FP kaynağı | Ayırt edici soru |
|---|---|---|
| WID named pipe (A1) | AD FS servis hesabı kendi DB'sine erişir; SQL yedekleme ajanı; SCCM envanteri | Bağlanan process **AD FS process'i mi**? İmza-atılmış, beklenen binary mi, yoksa `powershell.exe`/`rundll32`/bilinmeyen araç mı? |
| Registry `MonitoringAgent` erişimi (A2) | Health ajanının kendi meşru okumaları (`Microsoft.Identity.Health.Adfs.*`) | Erişen process Health ajanı mı, yoksa keşif yapan bir shell mi? EID 4656'da `ProcessName` alanına bak. |
| Hybrid Health `servicemembers/action` (B1) | Yeni gerçek AD FS sunucusu ekleme; Connect Health kurulumu; DR node | Bunu yapan **kimlik** rutinde bu işi yapan mı? Sunucu **kalıcı** mı yoksa saatler içinde silindi mi (B2)? |
| Hybrid Health `services/delete` (B2) | Servis dışı bırakma, tenant temizliği, migrasyon | Silinen servis **yakın zamanda oluşturuldu mu**? Oluştur-sil aralığı ne kadar? |
| `tokenIssuerAnomaly` | Yasal IdP config değişikliği, sertifika rollover, yeni federasyon partneri | Aynı kullanıcının komşu oturumları normal mi? Sertifika rollover **planlı bir değişiklik penceresinde** mi? |

**Analistin öncelik sırası (triage yargısı):**

1. **Önce bağlamı sabitle: değişiklik penceresi var mı?** AD FS token-signing sertifikası rutin olarak (varsayılan 1 yıl, AutoCertificateRollover ile) yenilenir. Rollover döneminde `tokenIssuerAnomaly` ve config erişimleri **beklenir**. Change management/CAB kaydıyla eşleşiyorsa gürültüyü düşür.
2. **Kimliği doğrula, olayı değil.** "Ne oldu"dan çok "**kim** yaptı ve o kişi bunu **rutinde** yapar mı" sorusu FP'yi eler. Yeni/atipik bir servis principal'in `Microsoft.ADHybridHealthService`'e yazması, meşru bir admin'in aynısını yapmasından **çok** daha yüksek önceliklidir.
3. **Kalıcılık testi.** Meşru altyapı **kalır**. Golden SAML altyapısı (sahte sunucu) **kullanılıp silinir**. Oluştur→sil kısa aralığı, tek başına en yüksek-değerli FP-ayıklayıcıdır.
4. **Çapraz kaynak teyidi olmadan P1 verme.** Tek sinyal → en fazla P3/izleme. İki farklı log kaynağı aynı entity'de → P2. Edinim + kullanım/sonuç zinciri → P1, IR devreye.
5. **Blast radius'u hemen çıkar.** Golden SAML doğrulanırsa mesele tek hesap değil; **imza sertifikası** tüm relying party'ler için geçerli token üretebilir. Triage'ın çıktısı "bu kullanıcıyı disable et" değil, "**token-signing sertifikasını rotate et (iki kez)**, tüm federasyon oturumlarını revoke et" olmalı.

---

## 5. Kaçınma → karşı-tespit

Dokümante kuralların yazmadığı, sahada gördüğüm atlatma manevraları ve bunlara ikinci-derece cevaplar:

**Kaçınma 1 — On-prem'i tümüyle terk et (bulut yol).** Saldırgan zaten Global Admin / uygun rolü ele geçirdiyse AD FS sunucusuna hiç girmez; Hybrid Health API'siyle sahte imza logu enjekte eder. On-prem Sysmon/SACL kurallarınız (`1ea13e8c`, `ff151c33`) tümüyle boş çıkar.
> **Karşı-tespit:** Azure Activity log'unu `Microsoft.ADHybridHealthService` ResourceProvider'ı için **mutlaka** toplayın. `288a39fc` ve `48739819` kuralları tam da bu kör noktayı kapatmak için var. On-prem odaklı SOC'lerin çoğunda bu log **hiç toplanmaz** — en kritik açık burada.

**Kaçınma 2 — Named pipe yerine offline DB/registry kopyası.** ADFSDump yerine, WID veritabanı dosyasını (`AdfsConfigurationV*.mdf`) VSS snapshot'tan veya offline kopyayla çekmek. `pipe_created` (EID 17/18) hiç tetiklenmez.
> **Karşı-tespit:** DKM master key'e giden yol AD içindeki `CN=ADFS,...` container'ındaki `thumbnailPhoto`/DKM özniteliğidir. **AD nesnesi okuma denetimi** (bu container'a SACL) + VSS/shadow copy oluşturma olayları (EID 7036/8222, `vssadmin`/`wmic shadowcopy`) korelasyonu. Named pipe kör kaldığında ikincil kaynak budur.

**Kaçınma 3 — Sysmon config'de pipe loglama kapalı.** `1ea13e8c` kuralının kendi notu bunu açıkça söyler: Named Pipe olayları (EID 17/18) **Sysmon config'de ayrıca açılmalı**. SwiftOnSecurity config'i içerir ama birçok kurum pipe event'lerini gürültü diye kapatır. Saldırgan bunu bilir; loglanmayan yerden geçer.
> **Karşı-tespit:** AD FS sunucularında Sysmon pipe loglamasının **fiilen açık** olduğunu doğrulayın (config denetimi bir tespit görevidir). Kapalıysa kuralınız yeşil görünür ama kördür — bu "sessiz başarısızlık" en tehlikeli durum.

**Kaçınma 4 — Claim'leri mükemmel taklit et.** Token'a doğru `AuthnContextClassRef`, gerçekçi `IssueInstant`, kullanıcının normal grup claim'leri konursa `tokenIssuerAnomaly` tetiklenmez.
> **Karşı-tespit:** İkinci-derece sinyal — **imkânsız yol / imkânsız MFA**. Federasyon girişinde MFA claim'i var ama Azure MFA servisinde karşılık gelen challenge kaydı yok; ya da giriş IP'si AD FS'in beklenen çıkış IP'sinden değil. Token'ın içeriği kusursuz olsa da **çevresel bağlam** (nereden, hangi altyapıdan geldi) sahteciliği ele verir.

**Kaçınma 5 — Sertifikayı çal ama günlerce bekle.** Edinim ve kullanım arasına uzun boşluk koyarak korelasyon penceresini aşmak.
> **Karşı-tespit:** Kısa (30 dk / 24 saat) korelasyon pencerelerine ek olarak, edinim sinyalini **entity risk skoruna kalıcı** olarak yazın (host/hesap 30-90 gün "yüksek riskli" etiketli kalsın). Böylece kullanım geç gelse bile o entity'deki federasyon anomalisi anında P1'e yükselir.

---

## 6. SIEM / saha gerçeği

**Field mapping — ham event vs. normalize alan.** Yukarıdaki Sigma alanları **ham** Azure Activity / Windows Security şemasıdır; SIEM'de karşılıkları değişir:

- **Sentinel (`AzureActivity` tablosu):** `CategoryValue` → `CategoryValue` veya bazı sürümlerde `Category`; `ResourceProviderValue` → `ResourceProviderValue`; `OperationNameValue` → `OperationNameValue`; `ResourceId` alanı olduğu gibi. Eski `AzureActivity` şemasında `OperationName` (görünen ad) ile `OperationNameValue` (kaynak-yolu, ör. `Microsoft.ADHybridHealthService/services/delete`) **farklıdır** — Sigma `OperationNameValue`'yu, yani makine-okunur yolu kullanır; yanlış alanı sorgularsanız kural sessizce hiç eşleşmez.
- **Splunk:** Azure logları genelde Add-on ile `source=azure:*` altında JSON; `properties.*` altına iner. `ResourceProviderValue` çoğu zaman `resourceProviderValue` veya `properties.resourceProvider` olur; field extraction'ı **kendiniz doğrulamadan** kural taşımayın.
- **Elastic (ECS):** Azure Activity için `azure.activitylogs.*`; `OperationNameValue` → `azure.activitylogs.operation_name`. Windows tarafında EID 4656/4663 → `winlog.event_id`, `ObjectName` → `winlog.event_data.ObjectName`, `ObjectType` → `winlog.event_data.ObjectType`. Sysmon EID 17/18 → `winlog.event_data.PipeName`, process → `winlog.event_data.Image`.

**Varsayılan loglanmayanlar (en sık ölümcül boşluklar):**
1. **Windows Security 4656/4663 obje erişimi** yalnızca ilgili nesnede **SACL** kuruluysa üretilir. `ff151c33` kuralı bunu açıkça şart koşar: `MonitoringAgent` registry anahtarına SACL/ACE (bkz. OTRF `Set-AuditRule`) eklemelisiniz. SACL yoksa kural sonsuza dek 0 sonuç döner — "kuralım var" yanılgısı.
2. **Sysmon EID 17/18 (named pipe)** birçok config'de kapalı (Kaçınma 3). Açık olduğunu teyit et.
3. **Azure Activity — `Administrative` kategorisi** genelde toplanır ama `Microsoft.ADHybridHealthService` işlemleri "gürültülü health verisi" diye filtrelenmiş olabilir; toplama kapsamını doğrula.
4. **AD FS "Audit" olayları** (1200/1202) Windows'ta varsayılan **kapalıdır**; `Set-AdfsProperties -AuditLevel Verbose` + Local Security Policy'de AD FS audit'i açmak gerekir. Ama hatırla (§2b): bunlar açık olsa bile Golden SAML token'ı **buraya düşmez**; asıl faydaları meşru imza taban çizgisini kurup bulut anomalisini bağlamlandırmak.

**Splunk / Sentinel / Elastic farkı — pratik:**
- **Sentinel** bulut-yerlisi olduğu için `288a39fc`/`48739819` (Azure Activity) neredeyse sürtünmesiz çalışır; asıl eksik on-prem Sysmon/Security tarafının MMA/AMA ile toplanması.
- **Splunk** en esnek ama en çok manuel field-extraction/CIM normalizasyonu ister; Azure Add-on'un JSON derinliğinde alan adları sürüm sürüm değişir — kuralı **kendi ortamınızın örnek event'iyle** doğrulamadan güvenmeyin.
- **Elastic** ECS ile tutarlı ama Azure/Windows modüllerinin doğru kurulumu ve `event.code`/`winlog.event_id` eşlemesi şart; pipe ve registry event'leri için Sysmon+Winlogbeat zinciri sağlam olmalı.

**Tuning önerileri (sahada işe yarayan):**
- Named pipe ve registry kurallarını **allowlist ile** çalıştırın: bilinen AD FS servis hesabı, imzalı Health ajan binary'leri, onaylı yedekleme process'leri hariç tut → geriye anlamlı sapmalar kalır.
- Hybrid Health kurallarını **düşük hacimli-yüksek değerli** kabul edip **hiç bastırmayın**; bunlar günde bir kez bile ateşlemez, ateşlerse bakılır. `Caller` bazlı "ilk-kez-görülen principal" zenginleştirmesi ekleyin.
- Korelasyonu tek kural yerine **entity risk toplama** ile kurun: A1=+30, A2=+40, tokenIssuerAnomaly=+50; 24 saat içinde aynı host/hesapta toplam ≥70 → P1. Bu, her sinyalin tek başına gürültülü olduğu ama birlikte kesin olduğu bu saldırı için doğru mimari.
- **Sertifika rollover takvimini** SIEM'e besleyin (lookup). Planlı rollover penceresinde `tokenIssuerAnomaly` ve config erişimlerinin önceliğini otomatik düşürün; pencere dışıysa yükseltin. FP'nin en büyük kaynağı budur ve takvim eşlemesi olmadan analist her yıl aynı meşru olaya boğulur.

**Kapanış yargısı:** Golden SAML'ı "bir kuralla" yakalamaya çalışan SOC kaybeder. Kazanan yaklaşım: (1) bulut yolunu (`Microsoft.ADHybridHealthService`) mutlaka logla — çünkü on-prem odağı buranın kör noktası; (2) her tekil sinyalin SACL/Sysmon config'inin **fiilen açık** olduğunu denetle — sessiz başarısızlık en büyük risk; (3) edinim→kullanım→sonuç zincirini entity bazında bağla; (4) kalıcılık ve kimlik-rutinliği testleriyle FP ele. Doğrulandığında cevap tek hesap değil, **token-signing sertifikasını iki kez rotate + tüm federasyon oturumlarını iptal**tir.
