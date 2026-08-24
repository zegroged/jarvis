# AWS IAM Yetki Yükseltme — Tespiti

## 1. Özet: saldırı + naif tespit (KISA)

AWS'te yetki yükseltme (privilege escalation), saldırganın ele geçirdiği düşük yetkili bir kimlikten (IAM user, rol, ya da sızdırılmış bir access key) başlayıp, IAM API'lerini kötüye kullanarak `Administrator` seviyesine tırmanmasıdır. Klasik yol: sızan bir `AKIA...` anahtarıyla `iam.amazonaws.com`'a gidip kendine ya da bir kurbana yeni access key basmak (`CreateAccessKey`), inline policy yapıştırmak (`PutUserPolicy`), bir kullanıcıyı yönetici gruba eklemek (`AddUserToGroup`) veya `AttachUserPolicy` ile `AdministratorAccess` managed policy'sini bağlamaktır. Pacu'nun `iam__backdoor_users_keys` modülü tam olarak bunu otomatikleştirir: kurbanın adına ikinci bir anahtar üretir; kalıcılık + gizli erişim.

Naif tespit — sağdaki gerçek Sigma kuralı `AWS IAM Backdoor Users Keys` (id `0a5177f4-6ca9-44c2-aacf-d3f3d8b6e4d2`) — CloudTrail'de şunu arar:

```
selection_source:
    eventSource: iam.amazonaws.com
    eventName: CreateAccessKey
filter:
    userIdentity.arn|contains: responseElements.accessKey.userName
condition: selection_source and not filter
```

Yani "biri `CreateAccessKey` çağırdı **ve** anahtarı basan kişinin ARN'i, anahtarın basıldığı kullanıcı adını içermiyor" = başkası adına anahtar basılmış = backdoor şüphesi. Benzer şekilde `S3Browser` kuralları (`db014773-...`) `userAgent|contains: 'S3 Browser'` + `CreateUser`/`CreateAccessKey`/`PutUserPolicy` kombinasyonuyla belirli bir tehdit aktörü aracını yakalar.

Bu kurallar iyi başlangıç noktalarıdır. Ama tek başına hiçbiri "yetki yükseltme oldu" demeye yetmez. Aşağısı bunun neden böyle olduğunu ve sahada gerçekte ne yapıldığını anlatıyor.

## 2. Naif tespit neden yetmez (kör nokta, atlatma, false positive selleri)

**`CreateAccessKey` kuralının kör noktası — self-key senaryosu.** `filter` mantığı `userIdentity.arn|contains: responseElements.accessKey.userName` ile "kendi anahtarını basanı" eliyor. Ama iki temel problem var:

Birincisi, bu bir **string `contains`** karşılaştırması ve CloudTrail alanları arasında runtime'da yapılıyor; çoğu SIEM'de field-to-field `contains` doğrudan desteklenmez. Splunk'ta `| where like(...)` ya da eval gerekir, Sentinel KQL'de `where arn contains userName` yazılabilir ama Elastic'te iki alan arasında dinamik `contains` bir `runtime_field` veya `painless` script ister. Yani kuralı olduğu gibi taşırsanız, backend'in field-to-field karşılaştırmayı desteklememesi yüzünden filter sessizce **hiç çalışmaz** ve her `CreateAccessKey` alarm üretir. Bu, "kural açık ama filtre no-op" tipik SIEM tuzağıdır.

İkincisi, ARN string'i `arn:aws:iam::123456789012:user/DevOps/alice` gibi bir path içerebilir; `userName` sadece `alice`'tir. `contains` doğru eşleşir. Ama saldırgan kurbanı kendi adıyla aynı ismi taşıyan bir kullanıcı seçerse ya da rol üzerinden (`assumed-role/.../session`) çağrı yaparsa ARN'de `userName` hiç geçmez — meşru olsa bile alarm patlar. Federated / SSO ortamlarında herkes `assumed-role` ile gelir, kimsenin ARN'i hedef IAM user adını içermez → **her legit key rotasyonu false positive**.

**Asıl kör nokta: `CreateAccessKey` privesc'in sadece bir yolu.** IAM privesc'in en az 20+ bilinen primitifi var (Rhino Security'nin haritası). Bu kural `AttachUserPolicy`, `PutUserPolicy`, `AddUserToGroup`, `CreatePolicyVersion` (`--set-as-default` ile), `UpdateAssumeRolePolicy`, `PassRole` + `CreateFunction`, `AttachRolePolicy`, `CreateLoginProfile` (konsol şifresi basma), `UpdateLoginProfile` hiçbirini görmez. Saldırgan `CreateAccessKey`'e hiç dokunmadan, sadece `AttachUserPolicy` ile `arn:aws:iam::aws:policy/AdministratorAccess`'i kendine bağlayarak admin olabilir. Bu kural kör.

**`S3 Browser` kuralları user-agent'a bağlı — trivial atlatma.** `userAgent|contains: 'S3 Browser'` demek, saldırgan kendi HTTP client'ının user-agent'ını değiştirdiği an (ki `boto3`/`aws-cli` default UA zaten "S3 Browser" değildir) kural devre dışı. Bu kurallar belirli bir aktörün (GUI-vil) belirli bir aracını yakalamak için yazılmış; imza-tabanlı ve kırılgan. Değeri düşük değil ama davranış değil, araç-parmak-izi tespiti.

**False positive selleri — gerçek kaynaklar:**
- **Terraform / CloudFormation / IaC:** Her `terraform apply` IAM user, policy, key üretebilir. `CreateAccessKey`, `PutUserPolicy`, `AttachUserPolicy` normal deploy trafiğidir. User-agent `aws-sdk-go` veya `Terraform`.
- **Anahtar rotasyon otomasyonu:** 90 günlük key rotasyonu yapan Lambda'lar başkası (servis hesabı) adına `CreateAccessKey` çağırır → backdoor kuralı yanar.
- **CI/CD pipeline'ları:** Jenkins/GitLab runner'ları servis kullanıcılarına dinamik key basar.
- **Onboarding otomasyonu:** Yeni çalışan geldiğinde HR entegrasyonu `CreateUser` + `CreateLoginProfile` + policy attach yapar.

Tek `eventName` gördüğünde bunları ayırt edemezsin. Sinyal-gürültü oranı berbat.

## 3. Korelasyon zinciri (asıl değer): tek sinyal zayıf; yüksek güven için çok aşamalı desen

Tek `CreateAccessKey` = gürültü. Değer, IAM privesc'in **davranışsal imzasını** — keşif → yetki değiştirme → kullanma zincirini — kısa pencerede birbirine bağlamakta.

### Somut zincir A: Sızan anahtar → keşif → self-privesc

Gerçek bir sızan-anahtar saldırısı neredeyse her zaman şöyle akar:

**Aşama 1 — Keşif (recon):** Saldırgan anahtarın ne yapabildiğini bilmez, önce sorar. CloudTrail'de patlama halinde `iam.amazonaws.com` okuma çağrıları:
```
eventName IN (GetCallerIdentity, ListUsers, ListRoles, ListAttachedUserPolicies,
              GetUserPolicy, ListUserPolicies, GetAccountAuthorizationDetails,
              SimulatePrincipalPolicy)
```
Özellikle `sts:GetCallerIdentity` + `iam:GetAccountAuthorizationDetails` (tüm IAM konfigürasyonunu tek çağrıda döker) kombinasyonu, insan operatörlerin ve Pacu'nun `enum` modüllerinin imzasıdır. Legit kullanıcı normalde `GetAccountAuthorizationDetails` çağırmaz.

**Aşama 2 — Yetki değiştirme (kısa pencerede, farklı bağlam):** Recon'dan **saniyeler-dakikalar** içinde bir yazma çağrısı:
```
eventName IN (AttachUserPolicy, PutUserPolicy, CreateAccessKey,
              AddUserToGroup, CreateLoginProfile, CreatePolicyVersion)
```
ve `requestParameters` içinde `AdministratorAccess` / `"Effect":"Allow"` / `"Action":"*"` / `"Resource":"*"`.

**Aşama 3 — Kullanma / kalıcılık:** Yeni yetkiyle yeni anahtarı ya da yeni yetkiyi kullanmak — genelde **farklı bir `sourceIPAddress`** ya da **yeni bir `accessKeyId`** ile.

**Yüksek güvenli kural (sözelleştirilmiş):**
> Aynı `userIdentity.arn` (ya da aynı `sourceIPAddress`) için: **5 dakikalık pencerede** ≥3 farklı IAM `List*`/`Get*` recon eventi **+** ardından `AttachUserPolicy`/`PutUserPolicy`/`CreateAccessKey`'den biri **+** requestParameters'ta admin göstergesi (`AdministratorAccess` veya `Action:*`) = **KRİTİK, gerçek privesc**.

Tek başına `AttachUserPolicy` orta seviyedir (Terraform de yapar). Ama "recon patlaması + hemen ardından admin policy attach + kullanıcının 90 gündür IAM'e hiç dokunmamış olması" üçlüsü, false positive'i neredeyse sıfırlar. Terraform recon yapmaz; doğrudan bilinen kaynağı deploy eder.

### Somut zincir B: `CreatePolicyVersion` sinsi yolu

`CreateAccessKey` ve `AttachUserPolicy` çoğu ekipte izlenir. Olgun saldırgan bunun yerine, zaten değiştirme yetkisi olduğu bir policy'de `CreatePolicyVersion --policy-document <admin> --set-as-default` çağırır. Görünürde "yeni bir policy version" — gürültü gibi. Ama:
> `CreatePolicyVersion` **+** aynı çağrının `requestParameters.setAsDefault=true` **+** yeni doküman `Action:*`/`Resource:*` içeriyor **+** 24 saat içinde aynı principal `iam:SimulatePrincipalPolicy` ile kendini test etmiş = gizli privesc.

Bu, tek-event kuralının asla yakalayamayacağı ama korelasyonun ortaya çıkardığı örüntü.

### Somut zincir C: Backdoor key → cross-account exfil

`AWS IAM Backdoor Users Keys` kuralı yandığında tek başına "birisi başkasına key bastı" der. Gerçek ihlal yargısı için bağla:
> `CreateAccessKey` (başkası adına, backdoor kuralı) **+** dakikalar içinde yeni basılan `accessKeyId`'nin **farklı bir `sourceIPAddress`/`userAgent`** ile ilk kez kullanılması **+** o kullanımın `s3:GetObject` / `sts:AssumeRole` (cross-account) içermesi = veri sızıntısı başlamış, sadece kalıcılık değil.

Buradaki "farklı bağlam" kritik: legit rotasyonda yeni key aynı CI runner IP'sinden kullanılır; backdoor'da anahtar üretilir, dışarıya taşınır, **bambaşka bir IP'den** hayata döner.

## 4. False positive gerçeği ve triage yargısı

Sahada bu kurallar açıldığında gelen alarmların ezici çoğunluğu meşrudur. Analistin FP kaynaklarını ve öncelik sırasını kafadan bilmesi lazım:

**FP kaynakları (sık → nadir):**
1. **IaC/Terraform state deploy** — `userAgent` `aws-sdk-go`/`Terraform`, `sourceIPAddress` CI/CD NAT gateway'i, `userIdentity` bir servis rolü (`assumed-role/terraform-exec/...`). En büyük gürültü.
2. **Key rotasyon otomasyonu** — servis Lambda'sı başkası adına `CreateAccessKey`; backdoor kuralını yakar. `userIdentity.arn` bilinen otomasyon rolü.
3. **Onboarding/IdP provisioning** — Okta/JumpCloud SCIM entegrasyonu `CreateUser`+policy.
4. **Konsoldan legit admin işi** — bir platform mühendisi gerçekten yeni kullanıcı açıyor; `userAgent` konsol imzası, `sessionContext.mfaAuthenticated=true`.
5. **S3 Browser gerçek kullanımı** — küçük ekiplerde biri gerçekten S3 Browser ile user/key üretmiş (Sigma kuralının kendi `falsepositives` notu).

**Analistin öncelik/triage sırası (yargı):**

1. **`userIdentity.type` ve `sessionContext.mfaAuthenticated`'e bak.** `IAMUser` + `mfaAuthenticated=false` + long-lived key = yüksek risk. `AssumedRole` + MFA + bilinen SSO = büyük ihtimal legit. İnsan mı makine mi ayrımı ilk filtre.
2. **`userAgent`'ı sınıflandır.** `aws-cli`, `Boto3`, `Terraform`, konsol, ya da **boş/garip/`python-requests`** mı? Garip veya generic HTTP client UA'sı → yukarı taşı. `Terraform` → büyük ihtimal aşağı.
3. **`sourceIPAddress`'i bağla.** Kurumsal CIDR / bilinen NAT / CI runner mı, yoksa **VPN çıkışı, Tor, yabancı ASN, bir cloud sağlayıcı IP'si** mi? Cloud IP'den (DigitalOcean/başka AWS hesabı) gelen IAM yazma çağrısı klasik saldırgan altyapısıdır.
4. **Principal'ın geçmişine bak (baseline).** Bu kullanıcı/rol daha önce IAM yazma yaptı mı? "90 gündür sadece `s3:GetObject` yapan bir servis hesabı birden `AttachUserPolicy` çağırdı" = kırmızı bayrak. `CloudTrail` geçmişi ya da UEBA baseline'ı burada altın değerinde.
5. **requestParameters içeriğini oku.** Bağlanan policy `AdministratorAccess` / `IAMFullAccess` / `Action:*` mı, yoksa dar kapsamlı bir uygulama policy'si mi? Admin/IAM-full = derhal eskale.
6. **Recon önceliği var mı?** Aynı principal son 10 dakikada `GetAccountAuthorizationDetails`/`SimulatePrincipalPolicy` çağırdıysa, tek bir `AttachUserPolicy` bile P1'e çıkar.

Yargı özeti: **tek event = ticket'ta bekletilir; event + (garip UA veya garip IP veya recon önceliği veya baseline sapması) = aktif inceleme; event + admin göstergesi + yeni key farklı IP'den kullanıldı = incident, key derhal iptal + principal dondur.**

## 5. Kaçınma → karşı-tespit (dokümanda yazmayan atlatma + ikinci derece tespit)

Sigma kuralları belirli event/UA imzalarına bağlı. Olgun saldırganın nasıl kaçtığını ve buna karşı ne yakaladığımızı bilmek gerçek işin özü.

**Atlatma 1 — Rol zinciri ile IAM'i by-pass.** Saldırgan `CreateAccessKey`/`AttachUserPolicy`'ye hiç dokunmaz. Bunun yerine ele geçirdiği principal'ın `sts:AssumeRole` ile daha yetkili bir role geçebildiğini bulur (`iam:PassRole` yanlış yapılandırması, ya da `AssumeRolePolicyDocument`'ı çok geniş bir rol). Hiçbir IAM yazma eventi yok; sadece `AssumeRole`. **Karşı-tespit:** `sts:AssumeRole` olaylarını hedef rolün **normalde-bu-principal-tarafından-alınmayan** bir rol olmasıyla korele et; `PassRole`'u `iam:CreateRole`/`lambda:CreateFunction`/`ec2:RunInstances` ile aynı pencerede bağla (PassRole privesc primitifi). Ayrıca `UpdateAssumeRolePolicy` — bir rolün güven politikasını kendi hesabına açacak şekilde değiştirme — düşük hacimli ama yüksek sinyalli bir eventtir, her zaman izle.

**Atlatma 2 — Yavaşlatma (low-and-slow).** 5 dakikalık korelasyon penceresini bilen saldırgan recon ile privesc arasına saatler/günler koyar. **Karşı-tespit:** Pencereyi olaya göre esnet — IAM yazma eventi tetikleyici olsun, geriye dönük **7 gün** içinde aynı principal'dan recon ara (retrospektif join). Ve baseline sapmasına yaslan: zaman aralığı önemsizleşir çünkü "bu principal IAM yazması yapması beklenmiyordu" sinyali zamandan bağımsızdır.

**Atlatma 3 — User-agent taklidi.** S3 Browser kuralından kaçmak için UA değiştirilir; hatta legit `aws-cli` UA'sı taklit edilir. **Karşı-tespit:** UA'ya güvenme; davranışa güven. Ama UA'nın **tutarlılığına** bak — aynı `accessKeyId` bir gün `aws-cli/2.x` bir gün `Boto3` bir gün `S3 Browser` gösteriyorsa, anahtarın paylaşıldığı/çalındığı sinyalidir (impossible UA-drift).

**Atlatma 4 — CloudTrail'i kör etme.** Gerçekten olgun saldırgan önce `cloudtrail:StopLogging`, `DeleteTrail`, `PutEventSelectors` (management event'leri kapatma), ya da `UpdateTrail` ile logu S3'te kendi kontrolündeki bucket'a yönlendirir. **Karşı-tespit:** Bunlar **çok düşük hacimli, çok yüksek sinyalli** eventlerdir — her biri tek başına P1 alarm olmalı. `StopLogging`/`DeleteTrail` neredeyse hiçbir zaman meşru değildir. Ayrıca CloudTrail'in kendi "log delivery durdu" GuardDuty bulgusu (`Stealth:IAMUser/CloudTrailLoggingDisabled`) ikinci hattır. Kritik: privesc tespitini **sadece** CloudTrail'e bağlama; log durursa körsün. `Config`, GuardDuty ve varsa organization-trail (üye hesabın kapatamayacağı) yedek görünürlük verir.

**Atlatma 5 — Konsol üzerinden `CreateLoginProfile`.** Anahtar yerine kurbana/kendine konsol şifresi basmak (`CreateLoginProfile`/`UpdateLoginProfile`) key-tabanlı kuralları atlar. **Karşı-tespit:** Bu eventleri `CreateAccessKey` ile aynı önem sınıfına koy; `UpdateLoginProfile` başkası adına = backdoor mantığının şifre versiyonu, aynı `arn|contains userName` filtresini uygula.

**Atlatma 6 — "Meşru" managed policy'nin arkasına saklanma.** `AttachUserPolicy` kuralları çoğunlukla `AdministratorAccess` string'ini arar. Saldırgan bunun yerine `IAMFullAccess`, `PowerUserAccess`, ya da daha sinsi bir şekilde `AWSLambda_FullAccess` + `iam:PassRole` gibi **dolaylı admin'e giden** managed policy'leri bağlar. `PowerUserAccess` "admin değil" diye elenirse, saldırgan zaten neredeyse her şeyi yapabilir. **Karşı-tespit:** Admin-eşdeğeri policy ARN'lerinin bir allowlist'ini (`IAMFullAccess`, `PowerUserAccess`, `AWSOrganizationsFullAccess`, `Billing`, herhangi bir `*FullAccess` içeren) tut ve string eşleşmesini tek `AdministratorAccess`'e daraltma. Ayrıca `policyDocument` içindeki inline policy'lerde `iam:*`, `sts:AssumeRole`, `iam:PassRole`, `iam:CreatePolicyVersion` action'larını regex ile ara — managed policy adı değil, **granted action** üzerinden yargıla.

**Atlatma 7 — Yeni oluşturulan bir kaynağa yükseltme.** Saldırgan mevcut kullanıcıya dokunmak yerine `CreateUser` + `CreateAccessKey` + `AttachUserPolicy` ile tamamen yeni, temiz bir backdoor identity oluşturur; sonra asıl ele geçirdiği anahtarı hiç kullanmaz. Baseline-sapması tespitleri "yeni kullanıcının geçmişi yok" diye kör kalabilir. **Karşı-tespit:** `CreateUser` eventinin kendisini takip et — özellikle bunu yapan principal'ın **normalde kullanıcı oluşturmadığı** durumda. `CreateUser` → dakikalar içinde aynı yeni `userName` için `AttachUserPolicy`/`CreateAccessKey`/`CreateLoginProfile` zinciri (Pacu'nun `iam__backdoor_users_keys` + create akışının tam imzası) tek başına yüksek güvenli bir örüntüdür; yeni kullanıcının "temiz" olması sinyali zayıflatmaz, tam tersine bu üçlünün saniyeler içinde art arda gelmesi otomasyon/saldırı imzasıdır.

## 6. SIEM/saha gerçeği (field mapping, varsayılan loglanmayan, Splunk/Sentinel/Elastic farkı, tuning)

**Field mapping — CloudTrail'in gerçek şeması.** Ham CloudTrail JSON'ında alanlar şunlardır ve normalizasyon her SIEM'de bozulabilir:
- `eventSource` = `iam.amazonaws.com` / `sts.amazonaws.com`
- `eventName` = `CreateAccessKey`, `PutUserPolicy` vb.
- `userIdentity.arn`, `userIdentity.type` (`IAMUser`/`AssumedRole`/`Root`), `userIdentity.accessKeyId`, `userIdentity.sessionContext.attributes.mfaAuthenticated`
- `requestParameters.userName`, `requestParameters.policyArn`, `requestParameters.policyDocument`
- `responseElements.accessKey.accessKeyId`, `responseElements.accessKey.userName`
- `sourceIPAddress`, `userAgent`, `errorCode` (yetki reddi = `AccessDenied`/`Client.UnauthorizedOperation`)

Sigma kuralının `userIdentity.arn` ve `responseElements.accessKey.userName` dot-notation'ı, Splunk'ta `userIdentity.arn` (spath ile), Sentinel `AWSCloudTrail` tablosunda `UserIdentityArn` ve `ResponseElements` (JSON string, `parse_json` gerekir), Elastic ECS'te `aws.cloudtrail.user_identity.arn` ve `aws.cloudtrail.response_elements` olur. **Kuralı olduğu gibi kopyalamak = kırık kural**; field adları her platformda farklı.

**Varsayılan loglanmayan — en kritik saha gerçeği.** CloudTrail default trail **sadece management event'leri** loglar; **data event'ler (S3 object-level `GetObject`, Lambda invoke) default KAPALIDIR** ve ayrıca açılmalı + ekstra ücretlidir. Yani "backdoor key farklı IP'den `s3:GetObject` yaptı" korelasyonunu (Zincir C) kurmak istiyorsan S3 data event logging'i açık olmalı — çoğu ortamda değildir. Ayrıca `GetCallerIdentity` gibi bazı `sts` read event'leri geç eklendi/eksik olabilir; recon tespiti (Zincir A) `GetAccountAuthorizationDetails` gibi **management-read** eventlere yaslanmalı, ki bunlar loglanır. IAM read event'lerinin bir kısmı yüksek hacimli olduğu için bazı ekipler bunları filtreler — o zaman recon körlüğü oluşur.

**Global servis gerçeği:** IAM ve STS (long-term) **global** servistir; olayları tarihsel olarak yalnızca `us-east-1`'de üretilir. Multi-region trail'iniz yoksa ya da `us-east-1`'i toplamıyorsanız IAM privesc'i **hiç görmezsiniz**. Sahada en sık kaçırılan konfigürasyon hatası budur.

**Splunk / Sentinel / Elastic farkı — field-to-field karşılaştırma:**
- **Splunk:** Backdoor kuralının `arn contains userName` mantığı için: `... | eval is_backdoor=if(like('userIdentity.arn', "%".'responseElements.accessKey.userName'."%"), 0, 1) | where is_backdoor=1`. `tstats`/data model ile hızlandırılabilir ama field-to-field `like` accelerated aramada zordur.
- **Sentinel (KQL):** `AWSCloudTrail | where EventName == "CreateAccessKey" | extend targetUser = tostring(parse_json(ResponseElements).accessKey.userName) | where UserIdentityArn !contains targetUser`. `ResponseElements` string olduğu için `parse_json` şart; unutulursa kural boş döner.
- **Elastic:** İki alan arasında dinamik `contains` sorgu zamanında yapılamaz; ya ingest pipeline'da bir `backdoor_flag` boolean'ı hesaplanmalı (Painless processor) ya da runtime field tanımlanmalı. EQL sequence ile korelasyon zinciri (Zincir A) çok temiz yazılır: `sequence by aws.cloudtrail.user_identity.arn with maxspan=5m [any where event.action in ("GetAccountAuthorizationDetails","ListRoles")] [any where event.action in ("AttachUserPolicy","CreateAccessKey")]`.

Yani basit tek-event kural her üçünde de çalışır ama **backdoor filter mantığı** ve **çok aşamalı korelasyon** platforma göre tamamen farklı yazılır; taşınabilir değildir.

**Tuning reçetesi (sahada işe yarayan):**
1. **Allowlist'i principal + UA + kaynak IP üçlüsüyle kur**, tek boyutla değil. `userIdentity.arn IN (terraform-exec, key-rotator-lambda)` AND `sourceIPAddress IN (CI CIDR)` AND `userAgent matches (Terraform|aws-sdk-go)` = bastır. Sadece ARN'ye göre bastırırsan, o rol ele geçirilince kör kalırsın.
2. **`errorCode` olan çağrıları ayrı ele al.** `AccessDenied` dönen bir `AttachUserPolicy` = başarısız privesc denemesi = aslında **daha yüksek sinyal** (biri yetkisi olmadığı halde denedi). Çoğu ekip bunları eler; tam tersi, `errorCode=AccessDenied` + IAM yazma çağrısı brute-force privesc göstergesidir.
3. **GuardDuty'yi ikinci hat yap.** `PrivilegeEscalation:IAMUser/AnomalousBehavior`, `Recon:IAMUser/*`, `Persistence:IAMUser/AnomalousBehavior` bulgularını kendi korelasyon kuralınla birleştir; GuardDuty ML baseline sağlar, sen deterministik zinciri sağlarsın.
4. **Root kullanımı ayrı P1.** `userIdentity.type=Root` ile herhangi bir IAM eventi neredeyse hiçbir zaman meşru değildir (break-glass hariç); ayrı, bastırılamaz bir kural.
5. **Yeni access key'in ilk kullanımını izle (Zincir C tuning).** Yeni `responseElements.accessKey.accessKeyId`'yi bir lookup'a yaz, sonraki N saat içinde o key'in `sourceIPAddress`'i backdoor'u basan IP'den farklıysa alarm yükselt.
6. **Recon eventlerini `readOnly=true` ile ucuz filtrele.** CloudTrail her event'i `readOnly` boolean'ıyla işaretler. Recon aşaması (`List*`/`Get*`/`Simulate*`) tamamı `readOnly=true`, yetki değiştirme (`Attach*`/`Put*`/`Create*`) tamamı `readOnly=false`'tır. Korelasyon kuralını "≥N readOnly IAM eventi + ardından bir readOnly=false IAM eventi" olarak genelleştirirsen, tek tek eventName listesi bakımından kaçınırsın ve yeni eklenen IAM API'lerini otomatik kapsarsın.
7. **`sessionContext.sessionIssuer`'ı korele et.** `AssumedRole` çağrılarında asıl kaynak rolü `userIdentity.sessionContext.sessionIssuer.arn`'dedir. Bir SSO/federe kimliğin arkasındaki gerçek insanı (`sessionIssuer` + `sourceIPAddress` + zaman) izlemeden, saldırgan aynı rolü paylaşan onlarca kullanıcının gürültüsünde saklanır. Baseline'ı `sessionIssuer` + hedef eylem çiftine kur.

**Erken uyarı sinyalleri (privesc'ten önce gelenler).** Sahada olgun bir tespit programı yetki yükseltmeyi **başladıktan sonra** değil, hazırlık aşamasında yakalamayı hedefler. En değerli erken sinyaller: (a) sızan-anahtar tespiti — bir `accessKeyId`'nin aniden yeni bir ASN/coğrafyadan kullanılması (`GeoIP` + `impossible travel`); (b) `iam:GetAccountAuthorizationDetails` veya `iam:SimulatePrincipalPolicy`'nin insan olmayan bir principal tarafından çağrılması — bu iki API neredeyse yalnızca ya güvenlik denetimi araçlarının ya da saldırgan enum'ının işidir, ikisini de allowlist'le; (c) `ListAccessKeys` + `GetLoginProfile` gibi "kimin nesi var" keşif çağrılarının artışı. Bunlar yüksek hacimli değildir, düşük gürültüyle erken uyarı verir.

**Kapanış yargısı.** Verilen Sigma kuralları doğru başlangıçtır ama üç şeyi hatırla: (1) `CreateAccessKey`/S3 Browser imzaları privesc'in dar bir diliminidir — `AttachUserPolicy`, `PutUserPolicy`, `CreatePolicyVersion --set-as-default`, `UpdateAssumeRolePolicy`, `CreateLoginProfile`, `AssumeRole`/`PassRole` zincirini de kapsamadan yetki yükseltmeyi göremezsin; (2) tek event her zaman gürültüdür, değer recon + değiştirme + kullanma zincirini kısa/esnek pencerede ve baseline sapmasıyla bağlamakta; (3) CloudTrail'in kendisi kör edilebilir ve global-servis/region/data-event konfigürasyonu yanlışsa hiçbir kuralın çalışmaz — tespit mimarisini log kaynağının bütünlüğü üzerine kur, sonra kuralları yaz.
