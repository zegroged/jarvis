# Bulut Sign-in Anomalisi (Entra ID / Azure AD) — Tespiti

> Saha notu. 15 yıllık SOC pratiğinden. "Impossible travel alarmı geldi, ne yapayım?" sorusunun ötesi. Buradaki değer kuralların kendisi değil; kuralların gerçek ortamda nasıl ve neden çöktüğü, ve tek tek zayıf sinyalleri yüksek-güven tespite nasıl bağladığın.

---

## 1. Özet: saldırı + naif tespit

Bulut kimlik dünyasında (Entra ID, eski adıyla Azure AD) modern saldırının kalbi artık malware değil, **geçerli kimlik bilgisiyle oturum açmak**. MITRE tarafında bunun adı `T1078` (Valid Accounts) ve alt kırılımı `T1078.004` (Cloud Accounts). Saldırgan bir yerden bir credential ele geçirir — phishing, infostealer log'u, password spray, ya da en tehlikelisi bir **token/refresh token hırsızlığı** (AiTM proxy ile session cookie çalma) — ve senin tenant'ına meşru bir kullanıcı gibi girer. Endpoint'te çalışan bir şey yok, EDR'da bir process yok; sadece `signinlogs`'ta bir satır var.

Naif tespit herkesin bildiği yerden başlar. Microsoft'un kendi Identity Protection'ı iki hazır risk sinyali üretir ve SOC'lar bunları Sigma'ya sarar. Birincisi **Impossible Travel** (`riskEventType: 'impossibleTravel'`, logsource `azure/riskdetection`): kullanıcı 10 dakika arayla İstanbul'dan ve São Paulo'dan oturum açtıysa, ışık hızının altında bir uçak olmadığına göre biri credential'ı paylaşıyor demektir. İkincisi başarısız oturum eşiği: **Conditional Access tarafından bloklanan** giriş denemeleri (`ResultType: 53003`, `Resultdescription: Blocked by Conditional Access`, logsource `azure/signinlogs`) — bir baseline üstünde patlarsa spray/brute-force şüphesi.

Buna bir de **kontrol düzlemini** koruyan kurallar eklenir. Saldırgan içeri girdikten sonra kalıcılık için sık sık Conditional Access politikalarıyla oynar: politika **silme** (`properties.message: Delete conditional access policy`), **değiştirme** (`Update conditional access policy`), veya **yeni ekleme** (`Add conditional access policy`) — hepsi `azure/auditlogs` altında, ve hepsi "onaylı olmayan aktör bunu yaptıysa alarm" mantığıyla kurgulanır. Kâğıt üstünde temiz bir kapsam: girişi yakala, kontrol değişikliğini yakala. Gerçekte bu setin her biri tek başına ya kör ya da gürültü kaynağı. Asıl iş buradan sonra başlıyor.

---

## 2. Naif tespit neden yetmez

**Impossible Travel'ın kör noktaları operasyonel gerçeğin ta kendisi.** Microsoft'un bu sinyali named location'lar, GPS değil IP geolocation ile hesaplar — ve IP geolocation kurumsal ortamda sistematik olarak yanlıştır. Kullanıcı kurumsal VPN'e bağlanınca çıkış IP'si merkez ofisin olduğu şehir görünür; VPN'i kapatıp yerel kafeden bağlanınca gerçek şehir görünür. Motor bunu "iki farklı şehir, kısa süre" diye okur ve impossible travel basar. Aynı şey **mobil operatör CGNAT** ve **cloud proxy/ZTNA** (Zscaler, Netskope, Cloudflare WARP) için de geçerli: kullanıcının trafiği bazen Frankfurt PoP'undan, bazen Amsterdam PoP'undan çıkar, insan hiç yerinden kalkmamıştır. Sahada bu alarmın **false positive oranı rahatça %90+**'a çıkar ve ekip iki hafta içinde alarmı görmezden gelmeye başlar — klasik alert fatigue.

Daha sinsi olan tarafı: Impossible Travel **atlatması kolay** bir sinyaldir. Saldırgan kurbanla aynı ülkeden, hatta aynı şehirden bir residential proxy / VPS kullanırsa "seyahat" hiç imkânsız olmaz. AiTM ile session token çalan bir aktör, kurbanın coğrafyasına yakın bir çıkış noktası seçer ve bu risk sinyali hiç tetiklenmez. Yani Impossible Travel, **acemi saldırganı ve credential paylaşımını** yakalar; hedefli bir aktörü değil.

**CA-bloklu giriş eşiği (53003)** ise ters problemden muzdarip. Bu sayaç sürekli yüksek gürültü üretir çünkü meşru dünyada CA'yı en çok tetikleyen şeyler kötü niyetli değildir: eski bir Exchange ActiveSync client'ı legacy auth denemesi yapar ve bloklanır, kullanıcının telefonu compliant değildir ve her senkronda bloklanır, bir servis hesabı yanlış konfigüre olmuştur. Bu yüzden Sigma kuralının kendisi bile "define a baseline threshold" diyor — yani kural sana eşiği vermiyor, **tuning'i sana bırakıyor**. Eşiği yanlış koyarsan ya sürekli patlar ya da gerçek bir low-and-slow spray'i (saatte 2-3 deneme) hiç görmezsin. `ResultType: 53003` ayrıca sadece **CA tarafından** bloklananları yakalar; parola yanlış olduğu için başarısız olan girişler `50126`, MFA gerektiği için düşenler `50074`/`50076`, kullanıcı bulunamadı `50034` — bunlar 53003 filtresine hiç düşmez. Saldırgan geçerli parolayı bulduğu an artık 53003 üretmez; sadece MFA duvarına toslar (`50074`) ki bunu izlemiyorsan spray'in **başarılı olduğu anı** kaçırırsın.

**CA politika değişikliği kuralları** ise "non approved actor" kavramına yaslanıyor ama Entra'da bu kavramın **yerel bir alanı yok**. Kural `properties.message: Delete conditional access policy` diyor; ama "bunu yapan kişi onaylı mı?" sorusunun cevabını audit log tek başına vermiyor. Onaylı aktör listesini sen dışarıda tutmak, initiatedBy alanıyla eşleştirmek zorundasın. Bu yapılmazsa kural her legitimate CA değişikliğinde patlar — ve olgun bir tenant'ta CA politikaları sürekli değişir (yeni named location, yeni pilot grup, break-glass ayarı). Kısaca: dört kural da tek başına ya kör ya gürültü. Değer, bunları **birbirine bağlamakta**.

---

## 3. Korelasyon zinciri — asıl değer

Tek bir sign-in anomalisi zayıf sinyaldir. Gerçek ihlali, **zaman ekseninde birbirini takip eden çok-aşamalı bir desen** yakalar. Google sana tek tek kuralları verir; kimse sana bu diziyi vermez. Modern bir Entra hesap ele geçirmesinin (özellikle AiTM token hırsızlığının) **kanonik zinciri** şudur:

**Aşama A — Erişim.** `signinlogs`'ta başarılı bir interactive sign-in. Kritik nokta: bu giriş **MFA'yı "satisfied" gösterir ama yeni bir MFA challenge yoktur**. Token çalındığı için `authenticationDetails` içinde "previously satisfied" / "MFA requirement satisfied by claim in the token" görürsün. Yani MFA geçilmiş gibi görünür ama kullanıcı hiçbir şey onaylamamıştır. Yanında sıklıkla yeni bir ASN (hosting/VPS ASN'i, kullanıcının normal residential/kurumsal ASN'i değil) ve alışılmadık bir user agent vardır.

**Aşama B — Kalıcılık.** Girişten **dakikalar-saatler içinde** bir kimlik dayanıklılık işlemi: kullanıcı kendi hesabına **yeni bir MFA yöntemi kaydeder** (auditlogs: `Register security info` / authentication method eklenmesi), ya da bir **OAuth uygulamasına consent verir** (`Consent to application` / `Add app role assignment grant to user`) — attacker kendi app'ine kalıcı `offline_access` refresh token alır. Bazen doğrudan CA tarafına dokunur: `Update conditional access policy` ile MFA zorunluluğunu kendi IP aralığından muaf tutacak bir exclusion ekler, ya da riskli oturumları bloklayan politikayı `Delete conditional access policy` ile kaldırır.

**Aşama C — Aksiyon/yayılma.** Farklı bir bağlamda etki: Exchange Online'da **yeni bir inbox rule** (gelen finans/güvenlik uyarılarını otomatik "Deleted Items"a taşıyan bir kural — BEC'in imzası), mailbox'a delegate ekleme, ya da SharePoint/OneDrive'da toplu indirme. Bu genellikle **farklı bir workload'ın loglarında** (`OfficeActivity` / Exchange audit) görünür, sign-in log'unda değil.

Yüksek-güven tespiti bu üç aşamayı **aynı kullanıcı üstünde, dar bir zaman penceresinde** birleştirdiğinde doğar. Somut örnek:

> **Yeni ASN'den başarılı sign-in (MFA "previously satisfied", token'dan)** + **60 dakika içinde aynı UPN için `Register security info` (yeni MFA yöntemi)** + **kısa süre sonra Exchange'de "Delete all incoming mail" mantığıyla yeni inbox rule** = neredeyse kesin BEC/ATO.

Bu üçlünün her biri tek başına orta/düşük değerdir. Impossible travel hiç tetiklenmeyebilir (attacker yakın coğrafyadan geldi). Ama **"MFA method register" olayı, o kullanıcının o oturumda yeni/nadir bir ASN'den geldiği** gerçeğiyle çakıştığında hikâye değişir: meşru kullanıcı MFA yöntemini genellikle bilinen cihazından, bilinen ağından kaydeder. İkinci somut zincir, kontrol düzlemi için:

> **`Add conditional access policy` veya `Update conditional access policy`** olayı + **initiatedBy, senin "CA'ya dokunabilir" allow-list'inde OLMAYAN bir kullanıcı** + **aynı aktörün son 24 saatte risky sign-in / yeni ASN geçmişi** = privilege escalation / kalıcılık girişimi (`T1556`, `T1548`).

Burada kilit bağ, statik "non approved actor" kuralını **davranışsal bağlamla** zenginleştirmek: CA'yı meşru admin de değiştirir, ama meşru admin bunu PIM ile yükseltilmiş bir oturumdan, bilinen ağdan, iş saatinde yapar. Saldırgan aynı işlemi ele geçirilmiş bir hesaptan, garip bir ASN'den, ve genellikle **PIM aktivasyonu olmadan** yapar. Yani `Update conditional access policy` olayını, aynı actor'ün o penceredeki **PIM activation kaydının yokluğu** ve **sign-in risk'i** ile korele edersen, gürültülü kural yüksek-güven kurala dönüşür.

Bir üçüncü, çok değerli ama az kurulan bağ: **spray → başarı geçişi**. Password spray başladığında yüzlerce `50126` (yanlış parola) görürsün, çoğu tek denemeyle. Kritik an, aynı kaynak IP/ASN'den bir hesabın aniden `50126`'dan `50074`'e (parola doğru, MFA gerekiyor) veya doğrudan `success`'e geçtiği andır. "Aynı ASN, çok sayıda hesap, çoğunlukla başarısız, **içlerinden biri başarılı**" deseni — bu, tek bir başarılı girişten çok daha güçlü bir sinyaldir çünkü spray'in **hedefini bulduğu** anı işaretler.

---

## 4. False positive gerçeği ve triage yargısı

Bu alarmları gerçek ortamda meşru üreten şeylerin listesini ezbere bilmezsen, kıdemli olamazsın. Somut FP kaynakları:

- **VPN / ZTNA çıkış noktası kayması:** Impossible travel ve "yeni ASN" alarmlarının bir numaralı meşru kaynağı. Zscaler/Netskope/Cloudflare PoP değişimi, kurumsal VPN'in datacenter IP'si. Bunları tanımak için elinde kurumun **VPN/proxy ASN ve IP aralıkları** olmalı; bu bir allow-list olarak korelasyona girmeli.
- **Servis hesapları ve otomasyon:** Bir yedekleme yazılımı (Veeam, Commvault), SCCM/Intune bağlantıları, bir vuln scanner (Tenable, Qualys) veya CI/CD pipeline, Graph API üstünden çok sayıda kimlik doğrulama üretir. Bunlar 53003/50126 sayaçlarını doldurur ve "olağandışı hacim" alarmlarını tetikler. Servis hesabı bir insan gibi davranmaz — non-interactive sign-in'lerde, sabit ASN'den, düzenli aralıkla gelir.
- **Legacy protokol istemcileri:** Eski bir ActiveSync/IMAP client'ı sürekli legacy auth denemesi yapar, CA bunu blocklar, 53003 patlar. Gerçek spray değil, sadece emekli olmamış bir Outlook.
- **Roaming yöneticiler / seyahat:** C-level bir yönetici gerçekten sabah İstanbul'da, öğleden sonra Londra'da olur. Impossible travel değil ama "yeni ülke" alarmı basar.
- **MFA yöntem kaydı olayları:** Yeni telefon alan çalışan, yeni bir authenticator kaydeder. Bu meşru `Register security info` olayının, ele geçirmedeki olaydan farkı **bağlam**: bilinen cihaz/ağ, yeni ASN yok, öncesinde başarısız giriş seli yok.

Kıdemli analistin triage yargısı **sırayla** işler. Çoklu alarm patladığında önce şuna bakarım: **"Bu oturum başarılı mı, ve başarılıysa kimlik-dayanıklılık işlemi izledi mi?"** Çünkü sinyallerin ağırlığı eşit değil. Başarısız giriş selleri gürültüdür; asıl kıymet **başarılı girişi takip eden ikinci-aşama olaydır** (MFA register, OAuth consent, inbox rule, CA değişikliği). Triage önceliğim:

1. **Sign-in başarılı mı?** ResultType success değilse ve ikinci aşama yoksa, çoğu zaman spray gürültüsü — eşiğe göre izle, koşma.
2. **MFA gerçekten yapıldı mı, yoksa token'dan mı "satisfied"?** `authenticationDetails`'a bakarım. "Previously satisfied" + yeni ASN, bende alarm zilidir — token replay şüphesi.
3. **Aynı kullanıcı/actor için pencerede ikinci-aşama var mı?** Auditlogs'ta MFA method register, OAuth grant, CA change; Exchange'de inbox rule. Varsa incident'a yükseltirim.
4. **Actor bilinen otomasyon/VPN aralığında mı?** Allow-list eşleşmesi FP'ye çeker.
5. **PIM/known-admin bağlamı:** CA değişikliği ise, initiatedBy PIM ile mi yükseldi, iş saatinde mi, bilinen ağdan mı?

En büyük hata, **her sign-in alarmına eşit ağırlık vermek**. Verdiğin an ekip boğulur. Doğru yaklaşım: tek başına gelen bir sign-in anomalisini **düşük öncelikli, korelasyon için "besleyici" sinyal** olarak tut; onu ancak ikinci-aşama bir olayla eşleştiğinde yükselt.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Deneyimli saldırgan bu kuralların **dokümanda yazmayan** zayıflıklarını hedefler. Her kaçınmaya ikinci-derece bir tespit lazım.

**Kaçınma 1 — Coğrafi yakınlık.** Attacker impossible travel'ı hiç tetiklememek için kurbanla aynı ülkeden, hatta aynı şehirden residential proxy kullanır. → **Karşı-tespit:** Coğrafyaya değil, **ASN ve cihaz tutarlılığına** bak. Kullanıcının baseline ASN profili (son 30-90 gün) çıkar; residential proxy/VPS ASN'i coğrafya aynı olsa bile "kullanıcı için yeni ASN"dir. Ayrıca cihaz uyumu: normalde compliant/Entra-joined cihazdan gelen kullanıcı, aniden unmanaged bir cihazdan/tarayıcıdan geliyorsa bu geolocation'dan bağımsız bir anomalidir.

**Kaçınma 2 — Token replay ile MFA'yı atlama.** AiTM ile session cookie çalındığında yeni MFA challenge hiç doğmaz; sign-in "MFA satisfied" görünür. Impossible travel de risky sign-in de düşük skorlanabilir. → **Karşı-tespit:** `authenticationDetails` içinde MFA'nın **"claim in the token" / "previously satisfied"** olarak işaretlendiği, ama oturumun **yeni bir cihaz/ASN/user-agent** taşıdığı durumları yakala. Meşru "remember MFA" ile hırsızlanmış token'ın farkı: meşru olan bilinen cihazdan gelir. Ek olarak **token issuance/refresh anomalileri** ve mümkünse token binding / CAE (Continuous Access Evaluation) sinyalleri.

**Kaçınma 3 — Low-and-slow spray.** Saatte 2-3 deneme, günlere yayılmış, tek eşiği asla aşmaz. → **Karşı-tespit:** Anlık eşik yerine **kaynak-bazlı toplama**: aynı ASN/IP'nin geniş pencerede (24-72 saat) **kaç farklı hesaba** dokunduğuna bak. Bir IP'nin 200 farklı UPN'e birer kez denemesi, tek hesaba 200 kez denemekten daha tehlikelidir (spray imzası). Hacim değil, **hesap yayılımı (fan-out)** metriği.

**Kaçınma 4 — Kontrol düzlemini sessizce köreltme.** Attacker CA'yı silmek yerine (`Delete` gürültü yapar) **inceden değiştirir**: politikayı silmez, sadece kendi IP aralığını exclude eder ya da politikanın atandığı grubu daraltır. → **Karşı-tespit:** `Update conditional access policy` olayında **modifiedProperties old vs new** karşılaştırmasını mutlaka aç. Kuralın kendisi bunu söylüyor: "Review Modified Properties and compare old vs new value." Exclusion listesine kullanıcı/IP **eklenmesi**, grant control'ün MFA'dan "grant"e düşürülmesi, ya da enabled→report-only'e çekilmesi — bunlar silmeden çok daha sinsi. Aynı şeyi **named location** eklemeleri için de izle: attacker kendi IP'sini "trusted location" yaparsa MFA'yı meşru yoldan atlar.

**Kaçınma 5 — Kalıcılığı OAuth'a taşıma.** Interactive sign-in izi bırakmamak için, ilk girişten sonra bir **illicit consent grant** ile kendi multi-tenant app'ine `offline_access` alır; sonrasında refresh token'la gelir, interactive sign-in log'unda görünmez. → **Karşı-tespit:** `Consent to application` / `Add OAuth2PermissionGrant` / `Add app role assignment` olaylarını izle; özellikle **admin consent gerektirmeyen ama yüksek yetki isteyen** (Mail.ReadWrite, Mail.Send, offline_access) grant'ler. Non-interactive sign-in loglarını da topla — çoğu ekip sadece interactive'i izler, service principal ve non-interactive sign-in'ler kör noktadır.

**Kaçınma 6 — Zamanlama ile korelasyonu kırma.** Attacker A/B/C aşamalarını **dar pencerede yapmaz**; girişten sonra günlerce bekler, sonra kalıcılık kurar. Senin 60 dakikalık korelasyon penceren kaçırır. → **Karşı-tespit:** Kritik ikinci-aşama olayları (MFA register, CA change, OAuth consent) **her zaman**, korelasyon penceresi olsun olmasın, düşük eşikli bağımsız alarm olarak tut; sonra geriye dönük 7-30 günlük pencerede o kullanıcının **risky sign-in geçmişiyle** enrich et. Yani korelasyonu sadece ileri değil, **geriye** de çalıştır.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları, platforma göre.** Aynı Entra olayı üç SIEM'de üç farklı şema ile gelir ve Sigma kuralının `logsource`'u seni yanıltabilir:

- **Sentinel:** Sign-in'ler `SigninLogs` (interactive) ve `AADNonInteractiveUserSignInLogs` (non-interactive) tablolarında **ayrı** durur. Sigma `azure/signinlogs` dediğinde çoğu backend sadece `SigninLogs`'a çevirir — **non-interactive tablo dışarıda kalır** ve token-replay/service-principal aktivitesinin çoğu oradadır. Bu tek başına en sık atlanan kör nokta. Denetim olayları `AuditLogs`, risk sinyalleri `AADUserRiskEvents`/`AADRiskyUsers` tablolarında. Alan adları da farklı: `ResultType` string olarak gelir, `properties.message` Sentinel'de doğrudan yok — audit olayı `OperationName` (örn. "Update conditional access policy") ve `TargetResources`/`InitiatedBy` alanlarıyla temsil edilir. Sigma'daki `properties.message: Delete conditional access policy` mapping'i, Sentinel'de `OperationName == "Delete conditional access policy"`'e dönmezse kural sessizce hiçbir şey eşleştirmez.
- **Splunk:** Genelde **Microsoft Graph Security / Azure AD add-on** ile gelir; alanlar `properties.*` altında nested JSON olarak oturur ve `spath`/otomatik KV extraction'a bağlıdır. `properties.message` alanı add-on'un sürümüne göre `message`, `operationName`, ya da hiç çıkmayabilir. Impossible travel gibi risk olayları riskDetection API'sinden gelir; add-on bunu çekmiyorsa o veri Splunk'ta hiç yoktur. Field extraction'ı doğrulamadan Sigma çevirisine güvenme.
- **Elastic:** ECS normalizasyonu araya girer. `ResultType` → `event.outcome` + `azure.signinlogs.properties.status.error_code` gibi yerlere dağılır; `initiatedBy` → `azure.auditlogs.properties.initiated_by.*`. Sigma'nın ham alan adları ECS'te birebir yoktur; ECS taxonomy'e map etmeden kural boş döner.

**Varsayılan loglanmayanlar — en pahalı ders.** Birçok kritik veri **lisans ya da konfigürasyon** olmadan hiç akmaz:

- **Impossible travel ve risk sinyalleri** Identity Protection'a, o da pratikte **Entra ID P2** lisansına bağlıdır. P1/free tenant'ta `riskdetection` verisi ya çok kısıtlı ya yoktur — Sigma kuralı geçerli ama besleyecek log yok. Bunu incident sırasında keşfetmek acıdır.
- **Non-interactive sign-in'ler ve service principal sign-in'leri** Diagnostic Settings'te **ayrı kutucuklardır**. `SignInLogs`'u export ediyor ama `NonInteractiveUserSignInLogs`, `ServicePrincipalSignInLogs`, `ManagedIdentitySignInLogs`'u işaretlememişsen, token replay ve app-based kalıcılığın büyük kısmı log'a hiç düşmez.
- **Mailbox audit** (inbox rule, delegate ekleme) Entra tarafında değil, **Unified Audit Log / Exchange**'de. Korelasyon zincirinin C aşaması bambaşka bir pipeline'dan gelir; ikisini aynı incident'ta birleştirmek için ortak anahtar (UPN + zaman) ile join kurman gerekir.
- **CA "report-only" modu:** Bir politika report-only'e çekilirse artık **blocklamaz** ama audit log yine "policy applied" benzeri kayıt üretebilir — analisti "koruma var" sanısına düşürür. Enabled→report-only geçişini bir kaçınma göstergesi olarak izle.

**Tuning gerçeği.** Hiçbir sign-in kuralı **allow-list olmadan** üretime çıkmaz. Minimum tutman gerekenler: kurumsal **VPN/proxy ASN ve IP aralıkları**, **servis hesabı UPN'leri ve onların beklenen kaynak ASN'leri**, **CA'ya dokunmaya yetkili admin listesi** (initiatedBy eşleştirmesi için), ve kullanıcı başına **baseline ASN/ülke profili**. Bu enrichment tabloları olmadan kurallar ya susar ya bağırır; ikisi de işe yaramaz.

Son olarak zaman senkronu ve tenant gecikmesi: Entra sign-in logları Log Analytics'e **2-15 dakika** (bazen daha fazla) gecikmeyle gelir ve audit logları farklı gecikmeyle. İki farklı tablodan olay korele ederken bu gecikmeyi hesaba katmazsan, gerçekte 5 dakika arayla olan A ve B olaylarını "aynı anda değil" diye ıskalarsın. Korelasyon penceresini ingest gecikmesine göre biraz geniş tut ve mümkünse olayları **kaynak zaman damgasına** (`TimeGenerated` değil, olayın kendi `createdDateTime`'ına) göre hizala.

---

*Özet yargı: Bu alandaki tespit, tek kuralları çalıştırmak değil; zayıf sign-in sinyallerini kimlik-dayanıklılık olaylarıyla (MFA register, OAuth consent, CA değişikliği) ve farklı workload'lardaki aksiyonlarla (inbox rule) zaman ekseninde bağlamaktır. Coğrafyaya değil ASN/cihaz tutarlılığına güven; başarısız giriş seline değil başarılı girişi takip eden ikinci-aşamaya odaklan; ve hiçbir kuralı allow-list ile zenginleştirmeden üretime alma.*
