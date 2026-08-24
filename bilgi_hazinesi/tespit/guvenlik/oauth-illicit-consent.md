# OAuth Illicit Consent Grant (Entra App Abuse) — Tespit

> Saha notu. Bu metin "OAuth nedir" anlatmıyor. Bir kiracıda (tenant) sahte/kötü niyetli bir uygulamanın kullanıcı rızasıyla nasıl kalıcı hale geldiğini, tespitin gerçekte hangi noktada koptuğunu ve tek sinyalle değil zincirle nasıl yakaladığımızı anlatıyor. Referans kurallar: `App Granted Microsoft Permissions` (c1d147ae), `App Granted Privileged Delegated Or App Permissions` (5aecf3d5), `Azure Service Principal Created` (0ddcff6d), `Application Using Device Code Authentication Flow` (248649b7), `Github High Risk Configuration Disabled` (8622c92d).

---

## 1. Özet: saldırı + naif tespit (kısa)

Illicit consent grant, klasik kimlik hırsızlığının yan yolu. Saldırgan kullanıcının parolasını veya MFA'sını kırmaya uğraşmaz; onun yerine kullanıcıya bir OAuth rıza (consent) ekranı gösterir. Kullanıcı "İzin Ver" dediği anda, saldırganın kontrolündeki bir uygulama (application / service principal) kullanıcının verilerine — `Mail.Read`, `Mail.Send`, `Files.ReadWrite.All`, `offline_access` — token'la erişir. Parola değişse de, MFA sıfırlansa da bu erişim ayakta kalır: çünkü verilen şey oturum değil, kalıcı `refresh_token`'dır. Bu yüzden persistence (kalıcılık) tekniğidir, initial access değil.

Tipik akış: kimlik avı linki → `login.microsoftonline.com/common/oauth2/v2.0/authorize` üzerinde barındırılan gerçek Microsoft rıza ekranı (URL Microsoft'un kendisi, bu yüzden kurban rahatlar) → `scope=offline_access Mail.Read Mail.Send ...` → kullanıcı onaylar → Entra tarafında service principal oluşur, delegated permission grant yazılır → saldırgan Graph API ile mailbox'a girer.

Naif tespit genelde şu tek satır: "`Consent to application` operasyonu gördüysen alarm ver" ya da referans kuraldaki gibi `properties.message: Add delegated permission grant` gördüysen `high` alarm. Doğru sinyal, ama tek başına ya çok gürültülü ya da geç. Neden yetmediği asıl mesele.

---

## 2. Naif tespit neden yetmez

**Kör nokta 1 — "consent" olayı ile "grant" olayı aynı şey değil.** Entra AuditLogs'ta işi karıştıran nokta bu. Kullanıcı rıza verdiğinde `operationName` çoğu zaman `Consent to application`; ama izinlerin fiilen yazıldığı kayıt `Add delegated permission grant` (delegated) veya `Add app role assignment to service principal` (application permission). Referans kural `c1d147ae` tam da bu iki `properties.message` değerini yakalıyor. Sorun: tek bir consent olayı, arka planda birden fazla `Add delegated permission grant` satırı doğurabilir; ve tersine, admin consent akışında `Consent to application` hiç görünmeden doğrudan grant satırları düşebilir. Sadece `Consent to application`'a bakan bir kural, admin-consent yolundan geleni kaçırır.

**Kör nokta 2 — delegated ile application permission arasındaki risk farkı.** Naif kural ikisini de aynı seviyede alarm eder. Ama `Add app role assignment to service principal` (yani application permission — kullanıcı bağlamı olmadan, uygulamanın kendi kimliğiyle çalışan izin) çok daha tehlikelidir: `Mail.Read` delegated sadece rıza veren kullanıcının kutusunu okur, ama `Mail.Read` **application** izni bütün kiracının posta kutularını okur. Referans kural `5aecf3d5` bilinçli olarak yalnızca `Add app role assignment to service principal`'a odaklanır ve `attack.t1098.003` (Additional Cloud Roles) etiketler. İkisini ayırt etmeyen bir tespit, önceliklendirmeyi (triage) daha en baştan bozar.

**Atlatma 1 — düşük-riskli izinlerle radar altından geçmek.** `user_impersonation`, `User.Read`, `openid`, `profile`, `email` — bunlar günde yüzlerce kez rıza alır ve normaldir. Saldırgan tam da bu gürültünün içine `offline_access` + `Mail.Read` sıkıştırırsa, sadece "consent oldu" diyen kural bunu binlerce meşru rızanın arasında kaybeder. Kritik olan izin metnini (scope) parse edip riskli olanları ayırmaktır; ham operasyon adına bakan kural bunu yapmaz.

**Atlatma 2 — publisher-verified ve çok-kiracılı (multi-tenant) uygulama gölgesi.** Saldırgan uygulamayı "verified publisher" rozetiyle veya meşru görünen bir isimle ("Microsoft 365 Backup", "PDF Viewer", "Corp VPN") oluşturursa, kullanıcı ekrana güvenir. Naif tespit uygulama adına/publisher'a bakmaz, dolayısıyla sosyal mühendislik katmanını hiç görmez.

**False positive selleri.** Bir kuruluşta günde onlarca meşru SaaS entegrasyonu rıza alır: Slack, Zoom, Salesforce, DocuSign, yedekleme çözümleri, güvenlik tarayıcıları. `App Granted Microsoft Permissions` kuralını ham haliyle açarsanız SOC'a günde 50-200 alarm düşer ve iki gün içinde herkes onu susturur (alert fatigue). Kuralın kendi `falsepositives` alanı zaten dürüstçe "meşru ihtiyaç" diyor — yani kural tek başına karar veremez, bağlam ister.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek güven için üç şey aynı hikâyede buluşmalı: **kim onayladı, ne verildi, sonra ne yapıldı.** Illicit consent'in imzası, rızayı takip eden dakikalarda gelen "ilk defa görülen uygulamanın Graph'a saldırısıdır".

### Zincir A — klasik phishing-consent kalıcılığı

```
T+0    Sign-in: yeni/bilinmeyen client app, çoğu kez farklı ASN/ülke,
       properties.message ~ "Consent" akışı (signinlogs)
T+0..2 AuditLog: operationName = "Consent to application"
       + operationName = "Add service principal"   (0ddcff6d)
       + properties.message = "Add delegated permission grant"
         VE scope içinde: offline_access, Mail.Read, Mail.Send,
         Files.ReadWrite.All  (c1d147ae — riskli scope filtresi)
T+2..30 Graph aktivitesi: aynı appId ile MailItemsAccessed / Send
         (Exchange / MailboxAudit), ilk kez bu app'ten
```

Tek başına her satır zayıf: service principal oluşması normaldir (`0ddcff6d` zaten `medium` ve "admin yapmış olabilir" diyor). Delegated grant normaldir. Ama **"ilk kez görülen bir service principal, oluşturulduğu ilk 30 dakika içinde `offline_access` + `Mail.*` izniyle Graph üzerinden posta kutusuna eriyorsa"** — bu artık meşru SaaS onboarding'ine benzemez. Meşru entegrasyonda genelde IT tarafından bilinen bir isim, admin consent, ve saatler/günler süren kademeli kullanım vardır; saldırıda dakikalar içinde mailbox okuması başlar.

**Somut örnek:** Kullanıcı `ayse@corp` saat 14:03'te İstanbul'dan normal oturum açıyor. 14:05'te AuditLog'da `Add service principal` (app adı "Mail Backup Pro", appId ilk kez görülüyor) + iki satır `Add delegated permission grant` (`Mail.Read`, `offline_access`). 14:11'de Exchange MailboxAudit'te aynı appId `MailItemsAccessed` ile 400 mesaj okuyor, `ClientAppId` yeni SP'ye eşit. Üç ayrı log kaynağı (SigninLogs + AuditLogs + Exchange), tek appId etrafında, 8 dakikalık pencere = yüksek güven ihlal.

Dikkat: bu üç halkadan herhangi ikisi tek başına hâlâ zayıftır. Yalnızca `Add service principal` + `Add delegated permission grant` görürseniz (üçüncü halka, yani fiili mailbox erişimi olmadan), bu bir SaaS onboarding'i de olabilir — saldırgan token'ı almış ama henüz kullanmamış da olabilir. Bu durumda alarmı yükseltmeden "izlemeye al" durumuna koyup, aynı appId'den ilk Graph/mailbox erişiminde tetikleyecek bir takip kuralı (follow-on rule) bırakmak doğru yargıdır. Tersine, üçüncü halka (mailbox okuması) geldiyse artık "olası"yı geç: kalıcılık aktiftir, müdahale (SP disable + token revoke) başlamalıdır. Yani zincirin kaç halkasının tamamlandığı, doğrudan müdahale aciliyetini belirler.

### Zincir B — device code phishing + consent

Referans kural `248649b7` (Device Code flow) tek başına zayıf sinyaldir ama consent zinciriyle birleşince güçlenir. Saldırgan kurbana device code gönderir; kurban `microsoft.com/devicelogin`'e kodu girer; saldırgan token'ı alır; **sonra** aynı oturumdan kötü uygulamaya rıza verdirir. Desen:

```
signinlogs: properties.message = "Device Code"  (248649b7)
   + kullanıcı input-constrained cihazda DEĞİL (masaüstü/tarayıcı UA)
   ↓ kısa pencere (< 15 dk)
auditlogs: "Consent to application" + "Add delegated permission grant"
```

Device code akışı kurumunuzda IoT/kiosk dışında hiç kullanılmıyorsa, onu takip eden bir consent, tek başına device code alarmından çok daha anlamlıdır. Bağlamı bağlamak burada değer üretir: device code = "olağandışı kimlik doğrulama", consent = "olağandışı yetkilendirme"; ikisi arka arkaya = hedefli saldırı.

### Zincir C — admin consent + savunma zayıflatma (GitHub örneğiyle analoji)

En tehlikeli varyant: bir hesap ele geçirilir, saldırgan **admin consent** verir (tüm kiracı adına), böylece kullanıcı rızasına hiç gerek kalmaz. Burada `Add app role assignment to service principal` (`5aecf3d5`, application permission, tenant-geneli `Mail.Read`) düşer. Bunu güçlendiren ikinci-derece sinyal: saldırganın önce/sonra bir güvenlik ayarını gevşetmesi. Referans kural `8622c92d` GitHub tarafında "OAuth app access restrictions disabled" gibi bir yüksek-riskli konfigürasyon kapatmayı yakalar — Entra'daki muadili "kullanıcı rızasını kısıtlayan policy'nin (`Users can consent to apps` ayarı) kapatılması" ya da `Manage consent policy` değişikliğidir. Desen:

```
auditlogs: consent/authorization policy değişikliği (rıza kısıtı gevşetildi)
   ↓
auditlogs: "Add app role assignment to service principal"
           scope = tenant-wide Mail.Read / Directory.Read.All  (5aecf3d5)
   ↓
Graph: çok sayıda posta kutusuna erişim (tek app, çok kullanıcı)
```

"Önce çiti indir, sonra sürüyü içeri sok" imzası. Tek tek her olay bir yöneticinin meşru işi olabilir; ama **rıza kısıtı gevşetme + hemen ardından tenant-wide app permission + çok-kutu erişimi** üçlüsü meşru bir değişiklik penceresine benzemez.

---

## 4. False positive gerçeği ve triage yargısı

Bu tespitte alarmların ezici çoğunluğu meşrudur. Analistin işi "alarm mı" değil, **"bu meşru onboarding mi, yoksa saldırı mı"** ayrımı. Gerçek FP kaynakları:

- **SaaS onboarding dalgaları.** Yeni bir Slack/Zoom/Notion kurumsal yaygınlaştırması; tek gün içinde yüzlerce kullanıcı aynı appId'ye rıza verir. İmza: **aynı appId, çok kullanıcı, kademeli.** Saldırıda genelde az kullanıcı, tek appId, ani mailbox okuması.
- **Yedekleme ve arşiv çözümleri** (Veeam, Dropbox Backup, "Mail Backup" tarzı) — bunlar gerçekten `Mail.Read` + `offline_access` isterler. Bu yüzden scope'a bakan naif kural bunlarda patlar. Ayırt edici: publisher verified mı, appId kurumsal allowlist'te mi, admin mi consent verdi.
- **Güvenlik tarayıcıları / DLP / e-keşif** araçları geniş Graph izinleri ister (`Mail.Read`, `Directory.Read.All`). Beklenen davranıştır ama kötüye benzer.
- **Microsoft'un kendi first-party uygulamaları** — bunları appId allowlist ile en baştan elemek gerekir (örn. Office, Teams first-party appId'leri).

**Analistin öncelik sırası (triage yargısı), yukarıdan aşağı:**

1. **Application permission (`5aecf3d5`) > delegated (`c1d147ae`).** Tenant-geneli app izni her zaman önce bakılır; tek kutu yerine tüm kiracı risktedir.
2. **appId "ilk kez görüldü" mü?** Kuruluşta 90 gün geriye bakıp bu appId hiç görülmemişse öncelik yükselir. Bilinen/allowlist appId'ler otomatik düşürülür.
3. **Consent'i veren kim — kullanıcı mı admin mi?** Admin consent + tenant-wide scope, en yüksek.
4. **Post-grant davranış var mı?** Grant'tan sonra dakikalar içinde `MailItemsAccessed`/`Send`/`Files` erişimi geldiyse, artık "olası" değil "aktif" saldırıdır — SP'yi hemen devre dışı bırak.
5. **Coğrafya/ASN uyumsuzluğu.** Consent'i doğuran sign-in, kullanıcının normal ülkesi/cihazı mı, yoksa yeni ASN/anonimleştirici mi?
6. **Scope içeriği.** `offline_access` (kalıcılık niyeti) + yazma izinleri (`Mail.Send`, `Files.ReadWrite.All`) okuma-only'den daha yüksek.

Pratik kural: SOC'ta bu alarmları ham akış olarak değil, **appId etrafında toplulaştırılmış (aggregated) bir "yeni uygulama rıza olayı" kartı** olarak sunmak gerekir — analist tek appId için "kim verdi, ne verdi, sonra ne oldu"yu bir bakışta görsün. Yoksa 200 satırlık delegated grant listesi kimseyi bir yere götürmez.

---

## 5. Kaçınma → karşı-tespit

Belgelerde yazmayan, sahada görülen atlatmalar ve bunların ikinci-derece tespiti:

**Atlatma 1 — grant'ı böl, düşük scope'la başla, sonra genişlet.** Saldırgan ilk rızada sadece `User.Read` alır (masum), günler sonra aynı SP'ye `Add delegated permission grant` ile `Mail.Read` ekletir. İlk consent'e bakan tespit bunu kaçırır çünkü "yeni uygulama" penceresi çoktan kapanmıştır.
> **Karşı-tespit:** Consent olayına değil, **var olan bir SP'ye sonradan yüksek-riskli izin eklenmesine** ayrı bir kural koy. `properties.message = "Add delegated permission grant"` VE hedef SP'nin oluşturulma tarihi > 24 saat önce VE scope riskli = "izin genişletme" alarmı. Kuralın ana selection'ı grant'tır (referans `c1d147ae`), ama SP yaşını korelasyonla ekle.

**Atlatma 2 — meşru bir uygulamanın client secret'ını çalıp onu kullanmak.** Yeni SP hiç oluşmaz, yeni grant hiç düşmez; saldırgan zaten allowlist'te olan bir uygulamanın kimliğiyle Graph çağrısı yapar. Consent/grant tabanlı tespitin tümü kör kalır.
> **Karşı-tespit:** `Update application – Certificates and secrets management` / `Add service principal credentials` audit olayı. Var olan bir uygulamaya **yeni credential eklenmesi** kalıcılığın sessiz yoludur (T1098.001). Ayrıca sign-in tarafında aynı appId'nin aniden yeni IP/ASN'den token alması. Yani "grant" değil "credential + davranış sapması" izle.

**Atlatma 3 — consent'i az kullanıcıya, yavaş dağıt.** Toplulaştırma mantığını bilen saldırgan, tek appId'yi 50 kullanıcıya bir günde değil, 5 kullanıcıya bir haftada rıza verdirir; "çok kullanıcı = meşru onboarding" varsayımını tersine kullanır ama eşiğin altında kalır.
> **Karşı-tespit:** Eşik tabanlı toplulaştırmaya güvenme; **appId novelty (yenilik) + scope riski**ni davranışsal outlier ile birleştir. Az kullanıcı + yeni appId + `offline_access` hâlâ yüksek önceliktir. Kullanıcı sayısı düşükse alarm *artmalı*, azalmamalı.

**Atlatma 4 — device code'u kısa ömürlü tutup logları yormak.** `248649b7` device code sinyalini üretir ama saldırgan flow'u dakikalar içinde tamamlayıp token'ı alır; SigninLogs'ta "başarısız" veya "iptal" gibi görünmesini umar.
> **Karşı-tespit:** Device code sign-in'i, onu izleyen consent/grant ile **her zaman** korele et; device code'un tek başına başarı/başarısızlık durumuna takılma, ardından gelen yetkilendirmeye bak.

---

## 6. SIEM / saha gerçeği

**Field mapping (kaynağa göre).** Referans kurallar `logsource: product: azure` altında iki servis kullanıyor: `auditlogs` ve `signinlogs`. Ham Entra Graph şemasında alanlar `properties.*` altındadır; ama her SIEM bunları farklı düzleştirir:

| Kavram | Sigma (ham Azure) | Microsoft Sentinel | Splunk (Azure add-on) | Elastic |
|---|---|---|---|---|
| Operasyon adı | `operationName` | `OperationName` | `operationName` / `Operation` | `azure.auditlogs.operation_name` |
| Mesaj/kategori | `properties.message` | `ResultDescription` / `TargetResources` | `properties.message` | `azure.auditlogs.properties.*` |
| Tablo (audit) | — | `AuditLogs` | `mscs:azure:audit` sourcetype | `logs-azure.auditlogs-*` |
| Tablo (signin) | — | `SigninLogs` | `mscs:azure:signin` | `logs-azure.signinlogs-*` |

Önemli tuzak: referans kurallar `properties.message`'e string eşleşme yapar (`"Add delegated permission grant"`), ama Sentinel'de bu değer çoğu zaman `properties.message` alanında değil, `TargetResources` veya olayın `ActivityDisplayName` alanındadır. Sigma kuralını Sentinel'e KQL'e çevirirken `AuditLogs | where OperationName in ("Add delegated permission grant","Add app role assignment to service principal")` demek genelde daha doğrudur — çünkü Sentinel `OperationName`'i `properties.message` ile aynı içerikle doldurur. Yani kuralı olduğu gibi taşırsanız Sentinel'de hiç eşleşmeyebilir; field'ı doğru kolona bağlamak şart.

**Varsayılan loglanmayan / gözden kaçan.** İki büyük boşluk:

1. **Post-grant Graph erişimi varsayılan Entra AuditLogs'ta yoktur.** `MailItemsAccessed`, `Send` gibi mailbox aktivitesi **Exchange Online / Unified Audit Log** (SecurityComplianceCenter) tarafındadır ve **mailbox auditing açık olmalıdır**. Zincirin en değerli üçüncü halkası (grant'tan sonra ne yapıldı) çoğu kiracıda ya kapalıdır ya da SIEM'e alınmamıştır. Bunu açmadan Bölüm 3'teki zinciri kuramazsınız.
2. **Consent olayının scope detayı.** "Hangi izin verildi" bilgisi bazı kiracılarda `AuditLogs`'un `TargetResources.modifiedProperties` altında derinde gömülüdür; SIEM ingest bu iç içe JSON'u düzleştirmezse scope'a göre filtreleme (offline_access, Mail.Read ayıklama) yapılamaz — kural yalnızca "grant oldu"ya düşer, "riskli grant"ı ayıramaz. Ingest tarafında bu alanın parse edildiğini doğrulayın. Pratikte scope, `modifiedProperties` içinde `DelegatedPermissionGrant.Scope` / `AppRole.Value` gibi eski-yeni değer çiftleri olarak gelir; delegated izinler boşlukla ayrılmış tek bir string'dir (`"offline_access Mail.Read Mail.Send"`), application izinler ise ayrı `AppRoleAssignment` satırlarıdır. Bu farkı ingest'te normalize etmezseniz, delegated tarafta scope'u `split(" ")` ile açmanız, application tarafta ise her satırı tek tek değerlendirmeniz gerekir — aynı kural iki farklı parse mantığı ister.

**Splunk / Sentinel / Elastic farkı, pratikte:**

- **Sentinel** en doğal ortam: `AuditLogs` ve `SigninLogs` connector'ları yerleşik. Ama consent scope'unu ayıklamak için `mv-expand TargetResources` + `modifiedProperties` açmak gerekir; ham kural bunu yapmaz, korelasyon kuralını (analytics rule) elle yazmak gerekir. Referans `0ddcff6d`, `5aecf3d5`, `c1d147ae` doğrudan `AuditLogs`'a maplenir.
- **Splunk**: Azure AD/Entra verisi genelde `Splunk Add-on for Microsoft Cloud Services` ile gelir; sourcetype ve alan adları add-on sürümüne göre değişir. `properties.message` alanı bazı sürümlerde `properties.message`, bazılarında düzleştirilip `message` olur — kuralı taşımadan önce bir `| stats count by sourcetype` ile hangi alanda geldiğini doğrula. Post-grant için Exchange verisini ayrı bir input olarak almanız gerekir; tek panelde birleştirmek için `appId`/`AppId` alanını normalize edin (Sign-in'de `AppId`, Audit'te target resource id, Exchange'de `ClientAppId` — üçünü ortak bir alana map edin, yoksa korelasyon join'i tutmaz).
- **Elastic**: `azure.auditlogs` ve `azure.signinlogs` datasetleri Filebeat/Azure module ile gelir; alanlar ECS'e map edilir ama `properties`'in iç içe kısmı `azure.auditlogs.properties.*` altında kalır. EQL sequence ile zincir kurmak güçlüdür: `sequence by azure.*.properties.app_id with maxspan=30m [service principal add] [delegated grant] [mailbox access]` — ama app_id'nin üç datasette de aynı alana normalize edildiğinden emin ol.

**Tuning — gürültüyü öldürmeden hassasiyeti korumak:**

1. **First-party ve bilinen appId allowlist.** Microsoft first-party appId'lerini ve kurumsal onaylı SaaS appId'lerini en baştan ele. Bu tek adım alarmların çoğunu keser.
2. **Scope tabanlı katmanlama.** Sadece `openid/profile/email/User.Read` içeren grant'ları düşür veya `low`; `offline_access` + yazma izni içerenleri `high`. Referans `c1d147ae` `high` seviyesini hak eder ama ancak scope filtresiyle; ham haliyle çok gürültülü.
3. **App vs delegated ayrımı.** `5aecf3d5` (app role assignment) her zaman ayrı ve daha yüksek öncelikli kuyruğa.
4. **Toplulaştırma penceresi.** appId başına 24 saatlik pencerede kullanıcı sayısı, ilk-görülme, scope, consent tipi (admin/user) tek karta toplansın. Analist appId'yi değerlendirsin, tek tek grant satırını değil.
5. **Zincir zorunluluğu.** Yüksek-güven kuyruğuna yalnızca "yeni appId + riskli scope + kısa pencerede Graph/mailbox erişimi" tam zincirini koy; tek sinyalleri "avlama/hunting" kuyruğunda tut, ana alarm yapma.

**Kapanış yargısı:** Bu tekniği yakalayan şey tek bir sihirli kural değil. `Consent to application` / `Add delegated permission grant` / `Add app role assignment to service principal` sinyalleri hammadde; değer, bunları **appId etrafında, kısa zaman penceresinde, kimin-ne-verdiği + sonra-ne-yapıldığı** ekseninde birleştirmekte. Post-grant mailbox denetimini açmadan ve scope'u parse etmeden bu tespit yarım kalır; onları hallettikten sonra bile SOC'un işi alarm saymak değil, "meşru onboarding mi saldırı mı" yargısını hızlı vermektir. Kalıcılık verildiği için de tespit tek başına yetmez — yakaladığında refleks, SP'yi devre dışı bırakmak ve verilen refresh token'ları iptal etmektir; yoksa parola/MFA sıfırlamak erişimi kapatmaz.
