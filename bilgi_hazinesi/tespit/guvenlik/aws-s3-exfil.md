# AWS S3 Veri Sızdırma — Tespiti

> Saha notu: Bu metin CloudTrail'de S3 exfiltration'ı gerçekten yakalamak için yazıldı. "S3 nedir" anlatmıyorum; sinyalleri nasıl bağladığımızı, tespitin sahada neden bozulduğunu ve triyajda neye öncelik verdiğimizi anlatıyorum. Alan/olay adları CloudTrail'in orijinal isimleriyle (`eventName`, `eventSource`, `requestParameters`, `userIdentity`) verilmiştir.

---

## 1. Özet: saldırı + naif tespit (kısa)

Tipik bir S3 exfiltration zinciri şudur: saldırgan geçerli bir kimlik ele geçirir (sızmış access key, üstlenilmiş rol, phishing'lenmiş konsol oturumu), hangi bucket'lar var diye bakar (`ListBuckets`), ilginç bucket'ın içini/politikasını okur (`GetBucketPolicy`, `GetBucketAcl`, `ListObjects`), sonra ya toplu indirir (binlerce `GetObject`) ya da daha sinsi olan yolu seçer: bucket'ı dışarı açar (`PutBucketPolicy` / `PutBucketAcl` ile public ya da farklı bir hesaba replikasyon), veriyi kendi kontrolündeki bir yere kopyalar. Fidye senaryosunda ek olarak versiyonlamayı kapatır (`PutBucketVersioning` → `Suspended`) ve objeleri/bucket'ı siler (`DeleteObject`, `DeleteBucket`).

Naif tespit dört kalıba indirgenir ve elimizdeki gerçek Sigma kuralları da tam bu naif katmandır:

- **`DeleteBucket`** başarılı → *AWS Bucket Deleted* (level: medium).
- **`PutBucketVersioning` + `requestParameters|contains: 'Suspended'`** → *AWS S3 Bucket Versioning Disable* (attack.t1490, impact).
- **`ListBuckets` + `userIdentity.type` AssumedRole değilse** → *Potential Bucket Enumeration on AWS* (attack.t1580).
- **`S3 Browser` userAgent'lı IAM işlemleri** → *S3Browser LoginProfile / templated policy* kuralları (araç-imzası tespiti).

Bu kuralların her biri gerçek ve yerinde. Ama tek başına hiçbiri size "veri sızdırıldı" demez. Söyledikleri şey: "bir S3 olayı oldu". Aradaki fark bu metnin konusu.

---

## 2. Naif tespit neden yetmez

### Kör nokta 1: Exfiltration'ın kendisi `DataEvent`, kural ise `ManagementEvent` diliyle yazılmış

Elimizdeki dört kuralın hepsi **management plane** olaylarına bakar: `DeleteBucket`, `PutBucketVersioning`, `ListBuckets`, `PutUserPolicy`. Ama asıl sızdırma fiili — objeyi indirmek — `GetObject`'tir ve `GetObject` bir **S3 data event**'idir. CloudTrail'de **veri olayları varsayılan olarak loglanmaz**. Hesabın CloudTrail trail'inde S3 data event kaydı açık değilse, saldırgan bucket'tan 40 GB müşteri verisini `GetObject` ile çeker ve *hiçbir* kural tetiklenmez — çünkü ortada log yoktur. *AWS Bucket Deleted* kuralı ancak saldırgan silerse tetiklenir; oysa iyi saldırgan silmez, kopyalar ve gider. En değerli sinyal, en pahalı ve en sık kapalı olan sinyaldir.

### Kör nokta 2: `ListBuckets` kuralının filter mantığı, gerçek saldırganı elemek üzerine kurulu

*Potential Bucket Enumeration* kuralı şunu diyor: `ListBuckets` var **ve** `userIdentity.type` **AssumedRole değil**. Yani AssumedRole ile yapılan enumerasyonu bilerek dışarıda bırakıyor (FP azaltmak için). Fakat bulut ihlallerinin çoğunda saldırgan tam olarak **AssumedRole** ile hareket eder: EC2 instance role'ünün credential'ını IMDS'ten çalar, ya da bir rolü `sts:AssumeRole` ile üstlenir. Kuralın FP'yi azaltmak için attığı tam da en tehlikeli aktörün kullandığı kimlik türüdür. Bu bir hata değil — kuralın niyeti "IAMUser ile insan/otomasyon taraması"nı yakalamak. Ama bunu bilmezseniz "enumerasyon tespitim var" yanılsamasına düşersiniz; asıl senaryoda kör olduğunuzu fark etmezsiniz.

### Kör nokta 3: `Suspended` string eşleşmesi bağlamdan bihaber

*Versioning Disable* kuralı `requestParameters|contains: 'Suspended'` ile eşleşiyor. Sorun: versiyonlamayı geçici kapatmak DevOps'ta rutin bir iştir — maliyet optimizasyonu, bir migrasyon öncesi, lifecycle testleri. Kural "kim, hangi kimlikle, bu bucket'ta bunu ilk kez mi yapıyor, arkasından silme geldi mi" diye sormaz. Tek başına orta seviye bir gürültü kaynağıdır. Değeri ancak **silme ile zincirlenince** ortaya çıkar (bkz. bölüm 3).

### Atlatma yüzeyi: string ve araç-imzasına bağlı kurallar kolayca kör edilir

`S3 Browser` kuralları `userAgent|contains: 'S3 Browser'` diyor. userAgent tamamen istemci kontrolündedir; saldırgan aynı API'yi `boto3`, `aws-cli` ya da custom bir SDK ile çağırırsa imza kaybolur, kural sessizdir. `<YOUR-BUCKET-NAME>` placeholder eşleşmesi de aynı şekilde — aracın default policy'sini elle düzelten bir saldırganda ölür. Bunlar "aptalı yakalayan" kurallardır; değerlidir ama üzerine tespit stratejisi kurulmaz.

### FP seli: management event'ler DevOps'un günlük nefesi

`PutBucketPolicy`, `PutBucketAcl`, `PutBucketVersioning`, hatta `DeleteBucket` — hepsi Terraform/CloudFormation/CDK pipeline'larında saniyede bir üretilir. Bir CI/CD hesabında `DeleteBucket` günde yüzlerce kez normaldir (ephemeral test bucket'ları). Tek olaya alarm kuran biri bu hesapta alarm körlüğüne (alert fatigue) gömülür ve gerçek silmeyi kaçırır.

### Kör nokta 4: `errorCode` filtresi, "denendi ama izin verilmedi" sinyalini de eler

*Bucket Deleted* kuralı yalnızca **başarılı** silmeye bakar (`errorCode: 'Success'` veya null). Bu bilinçli bir seçim ama tespit açısından bir kayıp: bir saldırgan yetersiz izinle `DeleteBucket`, `PutBucketPolicy` ya da `GetObject` denediğinde CloudTrail `errorCode: AccessDenied` yazar. Bu **başarısız denemeler seli**, çoğu zaman gerçek ihlalin en erken ve en temiz habercisidir — çünkü meşru otomasyon `AccessDenied` üretmez, o izinlere zaten sahiptir. Başarıya odaklı kural bu erken uyarıyı görmez. Ayrı bir "aynı kimlikten kısa pencerede çok sayıda `AccessDenied`" tespiti, keşif/hak-yükseltme aşamasını başarıdan önce yakalar.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyalin zayıf, çok-aşamalı desenin güçlü olduğu yer burası. Amaç: yüksek-güven bir "exfil oldu" yargısını, düşük-güven sinyalleri **zaman penceresi + kimlik sürekliliği + bağlam değişimi** ile örerek üretmek.

### Zincir A — Klasik "keşif → açığa çıkarma → çekme" (en yaygın)

```
[T+0]    userIdentity.arn = R1  →  ListBuckets                (keşif)
[T+2dk]  userIdentity.arn = R1  →  GetBucketPolicy /          (hedef seçimi)
                                    GetBucketAcl (aynı bucket)
[T+5dk]  userIdentity.arn = R1  →  PutBucketPolicy            (dışarı açma)
                                    (Principal: "*" veya farklı AccountId)
[T+6dk]  sourceIPAddress değişti / yeni AccountId →  GetObject seli
```

Buradaki değer, hiçbir adımın tek başına alarm olmaması ama **aynı `userIdentity` (aynı accessKeyId/sessionContext), 10 dakikalık pencerede, keşiften mutasyona geçiş** olmasıdır. Kilit ayırt edici: `PutBucketPolicy`'nin `requestParameters` içindeki policy dokümanında `"Principal": "*"` ya da **kendi hesabınıza ait olmayan bir AccountId** görülmesi. Kendi Org'unuzun account listesini bir lookup olarak tutup "policy'de yabancı principal" koşulu koyarsanız FP neredeyse sıfırlanır.

### Zincir B — Fidye/yıkım deseni (mevcut kuralları birleştirir)

Elimizdeki iki kuralı — *Versioning Disable* ve *Bucket Deleted* — tek başına orta seviyeyken, sıralı görünce kritiğe çıkarırız:

```
[T+0]   PutBucketVersioning  →  Suspended     (kurtarmayı devre dışı bırak)
[T+X<1s..dakikalar]  aynı bucket, aynı kimlik  →  DeleteObject (çok sayıda) 
                                              veya DeleteBucket
```

Invictus-ir'ın belgelediği bulut fidye kalıbı tam budur: silmeden önce versiyonlamayı kapatırlar, çünkü versiyonlama açıkken silme "geri alınabilir"dir. **"Versiyonlama Suspended → aynı bucket'ta 5 dakika içinde silme"** korelasyonu, iki medium kuralı tek bir yüksek-güven "aktif yıkım devam ediyor" sinyaline dönüştürür. Bu zincirde zaman penceresi ne kadar dar (saniyeler-dakikalar) o kadar güvenli, çünkü meşru admin bu ikisini nadiren peş peşe yapar.

### Zincir C — Kimlik anomalisi + hacim (en güvenilir exfil sinyali)

Eğer S3 data event loglaması **açıksa** (ki değerli hedeflerde açık olmalı), en güçlü tespit davranışsaldır, imza-temelli değil:

```
baz çizgi:  R1 rolü normalde günde ~50 GetObject, 1-2 bucket, iş saatlerinde
sapma:      R1 aniden  →  yeni sourceIPAddress (yeni ASN/ülke)
            + tek pencerede 5.000+ GetObject
            + daha önce hiç dokunmadığı bucket'lar
            + iş saatleri dışında
```

Tek başına "çok GetObject" FP üretir (yedek işi, analytics job). Tek başına "yeni IP" FP üretir (VPN, yeni bastion). Ama **yeni-kimlik-bağlamı + hacim-patlaması + yeni-bucket-kümesi** üçlüsü aynı `userIdentity.sessionContext` altında birleşince, meşru açıklaması neredeyse kalmayan bir desen olur. Burada `userIdentity.sessionContext.sessionIssuer` ile rolü, `sourceIPAddress` + `userAgent` ile bağlamı sabitleyip baz çizgiden sapmayı ölçersiniz.

### Zincircin özü

"A + kısa pencere B (farklı bağlam) + C = ihlal" ilkesini somutlarsak:

> **A:** `ListBuckets`/`GetBucketAcl` (keşif, düşük değer)
> **+ B (≤10 dk, aynı sessionContext):** `PutBucketPolicy` yabancı principal ile (bağlam değişti: okumadan yazmaya, içeriden dışarıya)
> **+ C:** yeni `sourceIPAddress`/AccountId'den `GetObject` hacmi
> **= yüksek güvenli veri sızdırma yargısı.**

Hiçbir tekil kural bunu vermez; korelasyon motoru (Splunk `transaction`/`stats by`, Sentinel `Sequence`/`bin`, Elastic EQL `sequence by`) verir.

---

## 4. False positive gerçeği ve triyaj yargısı

Sahada bu tespitleri kör eden meşru aktörler bellidir. Analistin kafasındaki öncelik sırası şöyle olmalı:

**Önce "bu kimlik bir makine mi insan mı?" diye sor.** `userIdentity.arn` bir servis rolü, CI/CD rolü ya da `arn:aws:iam::...:role/terraform-*` ise, management event'ler (Put/Delete Bucket*) neredeyse kesin altyapı otomasyonudur. Bunları kimlik bazında **allowlist**'e alın — kural gövdesinden değil, tuning katmanından. En yaygın gerçek FP kaynakları:

- **IaC pipeline'ları (Terraform/CloudFormation/CDK):** `DeleteBucket`, `PutBucketPolicy`, `PutBucketVersioning` üretirler. Ayırt edici: `userAgent` genelde `aws-sdk-go`/`cloudformation.amazonaws.com` gibidir ve `sourceIPAddress` kurumsal CI ASN'idir, tek bir role ARN'inden gelir.
- **Yedekleme/replikasyon işleri:** `GetObject` hacmini patlatır. Ayırt edici: sabit bir servis rolü, sabit IP, öngörülebilir zamanlama (cron), *hep aynı* bucket kümesi. Exfil'in aksine "yeni bucket'a dokunma" yoktur.
- **Güvenlik tarayıcıları (Prowler, ScoutSuite, Nessus cloud, CSPM ajanları):** `ListBuckets`, `GetBucketPolicy`, `GetBucketAcl` selini üretir — tam da keşif kalıbına benzer. Ayırt edici: bilinen tarayıcı rolü/userAgent, *okuma-only* (asla `PutBucketPolicy` yabancı principal yok), düzenli tarama penceresi.
- **Analytics/veri gölü işleri (Athena, EMR, Glue):** meşru büyük `GetObject` hacmi. Ayırt edici: servis principal (`athena.amazonaws.com` vb.) ya da bilinen analytics rolü.

**Triyaj yargı sırası (bir alarm düştüğünde 60 saniyede sorulacaklar):**

1. **Kimlik:** `userIdentity.arn` insan mı, servis mi? Servis+bilinen ise → düşük öncelik, allowlist adayı.
2. **Bağlam sapması:** `sourceIPAddress` bu kimlik için yeni mi? ASN/ülke beklenen mi? Yeni ise öncelik yükselir.
3. **Yön:** `PutBucketPolicy`/`PutBucketAcl` içinde **yabancı principal ya da `"*"`** var mı? Varsa bu artık FP değil, olay müdahalesidir.
4. **Zincir var mı:** Aynı sessionContext'te keşif→mutasyon ya da versioning-suspend→delete sıralaması var mı? Varsa medium'u kritiğe yükselt.
5. **Hacim ve yenilik:** `GetObject` sayısı baz çizginin kaç katı, daha önce dokunulmamış bucket'lar mı?

Kural: **management-plane tek olayı** (tek `DeleteBucket`, tek `Suspended`) düşük-orta öncelikte kalır; **zincir ya da yabancı-principal** görülür görülmez öncelik fırlar. Analistin en pahalı hatası, IaC gürültüsünde boğulup 500'üncü `DeleteBucket`'ı da otomatik kapatırken içine karışmış tek gerçek silmeyi kaçırmaktır. Bunu engelleyen şey kimlik-bazlı allowlist + zincir korelasyonudur; eşik büyütmek değil.

---

## 5. Kaçınma → karşı-tespit

Dökümante kuralların yazmadığı, sahada gördüğüm atlatmalar ve bunların ikinci-derece tespiti:

### Atlatma 1: Data event'i hiç loglatmama / trail'i kör etme
Saldırgan `GetObject`'in loglanmadığını bilir. Daha da ileri gidip `PutBucketPolicy` yerine trail'in kendisine dokunur: `StopLogging`, `UpdateTrail` (S3 data selector'ı kaldırma), ya da trail'in yazdığı bucket'a `PutBucketPolicy` ile erişimi bozar.
**Karşı-tespit:** `eventSource: cloudtrail.amazonaws.com` üzerinde `StopLogging`, `DeleteTrail`, `UpdateTrail`, `PutEventSelectors` olaylarını izleyin. Bir exfil'den hemen önce gelen "logging kapatma" olayı, exfil'in kendisi loglanmasa bile **kanıtın yok edilme girişimini** yakalar. Bu, "loglanan şeyin kaybolması"nı meta-sinyal olarak kullanmaktır.

### Atlatma 2: Public açma yerine sessiz replikasyon
`PutBucketPolicy` ile public yapmak gürültülüdür (GuardDuty `Policy:S3/BucketAnonymousAccessGranted` üretir). Sinsi yol: `PutBucketReplication` ile bucket'ı saldırganın başka bir hesaptaki bucket'ına replike etmek. Veri arka planda AWS altyapısı üzerinden akar, tek bir `GetObject` seli görünmez.
**Karşı-tespit:** `eventName: PutBucketReplication` her zaman incelenmeli — nadir bir management olayıdır ve hedef `requestParameters` içindeki destination bucket ARN'i **kendi Org'unuzun account listesinde değilse** neredeyse kesin kötücüldür. Aynı mantık `PutBucketPolicy`'nin cross-account grant'ine, presigned-URL üretimine ve `CreateAccessPoint` ile yeni erişim noktası açmaya da uygulanır.

### Atlatma 3: `sts:AssumeRole` ile kimlik türünü kuralın kör noktasına taşımak
Bölüm 2'de dediğim gibi *ListBuckets* kuralı AssumedRole'ü elemekte. Saldırgan bir rol üstlenir ve enumerasyonu o kimlikle yapar — kural sessiz.
**Karşı-tespit:** `AssumeRole` olayını exfil zincirinin ilk halkası olarak modelleyin: `sts:AssumeRole` (özellikle olağandışı rol, olağandışı `sourceIPAddress`) → kısa pencerede aynı `sessionContext` ile `ListBuckets`/`GetObject`. Kuralın körlüğünü, kimlik geçişinin kendisini izleyerek kapatırsınız.

### Atlatma 4: Hacmi tabanın altında tutmak (low-and-slow)
Hacim tespitini bilen saldırgan günde 200 obje, haftalara yayarak çeker; baz çizgi eşiğinin altında kalır.
**Karşı-tespit:** Hacim yerine **kapsam yeniliği**ne bakın: kimlik bazında "ilk kez dokunulan bucket/prefix sayısı" ve "kümülatif benzersiz obje" trendi. Yavaş exfil hacimde görünmese de "bu rol daha önce hiç görmediği 30 farklı bucket'ı gezdi" davranışında görünür.

### Atlatma 5: userAgent/araç imzasını taklit etme
`S3 Browser` kurallarını bilen saldırgan userAgent'ı `aws-cli/2.x` gibi meşru bir değere set eder ya da tam tersi normal bir userAgent taklit eder.
**Karşı-tespit:** userAgent'ı hiçbir zaman tek başına güven ekseni yapmayın; kimlik + davranış zincirini birincil, userAgent'ı yalnızca zenginleştirme (enrichment) olarak kullanın.

---

## 6. SIEM/saha gerçeği

### Alan eşlemesi (field mapping) — bilinmesi gereken tuzaklar

CloudTrail JSON'ında kritik alanların gerçek yolları ve SIEM'e girerken bozulan yerleri:

- `eventName`, `eventSource` — sabit, güvenilir. Sigma bunların üzerine kurulu.
- `errorCode` — *Bucket Deleted* kuralı `errorCode: 'Success'` **veya** `errorCode: null` diyor. Tuzak: başarılı olaylarda CloudTrail çoğu zaman `errorCode` alanını **hiç yazmaz** (null), bazı durumlarda `Success` yazar. SIEM'iniz null'ı "alan yok" olarak indeksliyorsa `errorCode: null` koşulu beklediğiniz gibi çalışmayabilir — bu yüzden kural iki koşulu `1 of selection_status_*` ile OR'lamış. Kendi tuning'inizde bunu doğrulayın; aksi halde başarılı silmeleri kaçırırsınız.
- `userIdentity.type` / `userIdentity.arn` / `userIdentity.sessionContext.sessionIssuer.arn` — korelasyonun bel kemiği. Splunk'ta genelde `userIdentity.arn` düz gelir; Sentinel'de `AWSCloudTrail` tablosunda `UserIdentityArn`, `UserIdentityType`, `SessionIssuerArn` olarak ayrı sütunlara açılır. Elastic ECS'te `aws.cloudtrail.user_identity.arn` ve `user.name`/`user.id`'ye map'lenir. Aynı mantığı üç platformda yazarken alan adları tamamen değişir — kuralı taşırken en çok kırılan yer burasıdır.
- `requestParameters` — serbest-form JSON. `PutBucketVersioning`'de versiyon durumu `requestParameters.VersioningConfiguration.Status` altındadır ama CloudTrail bunu iç içe obje olarak yazar; `requestParameters|contains: 'Suspended'` string araması bu yüzden kullanılmış (yapılandırılmış path yerine). Splunk'ta `spath`, Sentinel'de `parse_json`, Elastic'te `requestParameters` çoğu zaman flatten edilmemiş halde `*` string alanı olarak durur. `contains` yaklaşımı taşınabilir ama false-positive'e açık (başka bir alanda "Suspended" geçerse).
- `sourceIPAddress` — servis-üzeri çağrılarda IP yerine `athena.amazonaws.com` gibi **servis adı** yazar. "Yeni IP" tespitinizde bunu hesaba katın, yoksa her Athena sorgusu "yeni IP"ymiş gibi görünür.

### Varsayılan loglanmayan: en büyük saha gerçeği

Tekrar, çünkü her şeyi belirler: **S3 object-level (data) event'ler varsayılan olarak CloudTrail'e yazılmaz.** `GetObject`, `PutObject`, `DeleteObject`'i görmek için trail'de **S3 için data event selector** açık olmalı (advanced event selectors ile bucket/prefix bazında). Bu maliyet üretir, o yüzden çoğu hesapta kapalıdır. Sonuç: bu metindeki en güçlü tespitler (Zincir C, hacim, low-and-slow) **ancak data event loglaması açıksa** çalışır. Açık değilse GuardDuty'nin S3 Protection'ı (VPC/DNS/CloudTrail temelli, `Exfiltration:S3/ObjectRead.Unusual`, `Discovery:S3/*` bulguları) fallback'iniz olur; ama o da örneklem-temelli ve gecikmelidir. **İlk yapılacak iş:** kritik/veri-hassas bucket'lar için S3 data event loglamasını açmak — tespit mühendisliğinden önce gelen bir önkoşuldur.

### Splunk / Sentinel / Elastic farkı

- **Splunk:** CloudTrail'i genelde `sourcetype=aws:cloudtrail`. Korelasyon için `stats`/`transaction ... by userIdentity.arn` ve `bin _time span=10m` doğal araçlar. Zincir B'yi `stats earliest(eventName) latest(eventName) by bucketName, userIdentity.arn` ile "Suspended önce, Delete sonra" olarak kurabilirsiniz. Data-model (CIM) map'lemesi yaparsanız `Change` datamodel'ine oturur.
- **Sentinel (KQL):** `AWSCloudTrail` tablosu. Çok-aşamalı deseni `AWSCloudTrail | where EventName in (...) | ... | evaluate` ya da iki sorguyu `join kind=inner` / `Sequence`-benzeri `partition by SessionIssuerArn` ile örersiniz. Analytics rule'da `bin(TimeGenerated, 10m)` pencere. Entity mapping'i (Account, IP, AWSResource) UEBA'ya bağlamak için önemli.
- **Elastic (EQL/ESQL):** Gerçek çok-aşamalı korelasyonun en temiz yeri EQL `sequence by aws.cloudtrail.user_identity.arn with maxspan=10m`. Zincir A'yı neredeyse birebir EQL sequence olarak yazabilirsiniz: `[any where event.action=="ListBuckets"] [any where event.action=="PutBucketPolicy"] [any where event.action=="GetObject"]`. ECS alan adları farklı olduğu için Sigma'yı `sigma convert` ile Elastic backend'ine çevirirken `logsource: product=aws, service=cloudtrail` map'ini doğrulayın.

### Tuning felsefesi

1. **Kimlik-bazlı allowlist, gövde değil.** IaC/backup/scanner rollerini kuralın `filter`'ına değil, ayrı bir lookup/watchlist'e koyun; kural mantığı temiz kalsın, istisna listesi versiyonlansın.
2. **Tek-olay kuralları → sinyal; zincir kuralları → alarm.** *Bucket Deleted*, *Versioning Disable*, *ListBuckets enum* kurallarını "kritik alarm" değil, korelasyon motoruna giren **atomik gözlem** olarak çalıştırın. Alarmı zincir üretsin.
3. **Yabancı principal koşulunu her yerde uygulayın.** `PutBucketPolicy`/`PutBucketAcl`/`PutBucketReplication`/`CreateAccessPoint` olaylarında `requestParameters` içindeki principal/destination'ı Org account listesiyle karşılaştıran bir enrichment yazın. Bu tek kural, public-açma ve cross-account exfil'in çoğunu yüksek güvenle yakalar ve FP'si düşüktür.
4. **Log-tamperi meta-sinyal olarak.** `StopLogging`/`UpdateTrail`/`PutEventSelectors` her zaman incelensin; exfil loglanmasa da kör-etme girişimi loglanır.
5. **Baz çizgi kimlik başına, global değil.** "5000 GetObject" bir analytics rolü için normal, bir IAM kullanıcısı için felakettir. Eşikleri `userIdentity.arn` başına öğrenin.

### Pratik bir tuning örneği: gürültülü hesabı sessizleştirmek

Diyelim bir platform hesabında *Bucket Deleted* günde 300 kez tetikleniyor ve analist hepsini kapatıyor. Doğru müdahale sırası şudur: önce `stats count by userIdentity.arn, userAgent` ile silmelerin dağılımını çıkar. Neredeyse tamamı iki-üç `terraform-*` rolünden ve `aws-sdk-go` userAgent'ından geliyorsa, o rolleri bir `iac_service_roles` watchlist'ine al ve **alarm koşulunu "silme VE kimlik watchlist'te değil" haline getir** — kuralı silme, sadece bilinen otomasyonu düş. Kalan avuç dolusu olay şimdi incelenebilir hacimde. İkinci adım: bu kalanların üzerine "aynı bucket'ta 5 dk içinde önce `PutBucketVersioning`→Suspended geldi mi?" korelasyonunu koy; geldiyse severity'i kritiğe yükselt. Böylece 300 gürültülü olaydan, incelenebilir bir avuç ve içinden yükseltilmiş bir-iki gerçek adaya inersin. Anahtar: **eşik büyütmedin, bağlam ekledin** — hacmi azaltmanın doğru yolu budur.

### Kapanış yargısı

Elimizdeki Sigma kuralları doğru ve gerekli, ama hepsi **sonuç** ya da **hazırlık** olaylarına bakan tekil imzalardır. S3 exfiltration'ı gerçekten yakalayan şey, bu tekil olayları (a) **data event loglaması açıkken** `GetObject` davranışıyla, (b) **kimlik sürekliliği** (`sessionContext`) ekseninde, (c) **dar zaman pencerelerinde** ve (d) **yabancı-principal/log-tamper** bağlam koşullarıyla örmektir. Tek kural size "bir şey oldu" der; zincir size "veri gitti" der — ve SOC olarak maaşımızı ikincisini doğru söylediğimiz için alırız.
