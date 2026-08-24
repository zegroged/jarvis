# Bulut-Native Forensics ve Log Kaynakları

## Giriş: Neden Klasik Adli Analiz Bulutta İşe Yaramaz

Disk forensics, memory forensics ve network forensics disiplinlerinin ortak bir varsayımı vardır: incelenecek "şey" bir yerde durur. Bir sunucunun diski çıkarılıp write-blocker ile imaj alınabilir, RAM bir bellek dump'ı olarak dondurulabilir, ağdaki paketler bir SPAN port'undan yakalanabilir. Bu varsayımın temelinde **kalıcılık (persistence)** ve **fiziksel erişim** vardır.

Bulut ortamı bu iki varsayımı da kırar. KÖK NEDEN şu üçtür: bulut, sorumluluğu paylaşılan (shared responsibility) ve soyutlanmış (abstracted) bir modeldir. AWS/Azure/GCP müşteriye fiziksel diski, hipervizörü, ağ anahtarını vermez; bunun yerine servisler (managed services) ve bu servislerin ürettiği **log kayıtları** üzerinden görünürlük sağlar. Sonuç olarak adli analistin elinde artık "imaj alınacak bir disk" değil, "sorgulanacak dağıtılmış bir log ekosistemi" vardır. Bu, metodolojiyi kökten değiştirir:

- **Kalıcılık yok / ephemeral yaşam döngüsü**: Bir EC2 instance, bir Lambda execution environment veya bir container, saniyeler-dakikalar içinde oluşturulup yok edilebilir. Olay bittiğinde kanıt da bitebilir - eğer önceden toplanmadıysa.
- **Log kaynakları servis bazlı parçalanmış**: Kimlik doğrulama logları IAM'de, ağ akış kayıtları VPC'de, API çağrıları CloudTrail'de, tehdit tespiti GuardDuty'de, konteyner olayları EKS/ECS'de ayrı ayrı durur. Tek bir "olay günlüğü" yoktur; korelasyon analistin işidir.
- **Kontrol düzlemi (control plane) ile veri düzlemi (data plane) ayrımı**: "Kim neyi değiştirdi" (control plane - CloudTrail) ile "veri nereye gitti" (data plane - VPC Flow Logs, S3 access logs) farklı katmanlardadır ve genelde farklı retansiyon/varsayılan-açık/kapalı politikalarına sahiptir.
- **Multi-tenant soyutlama**: Fiziksel donanıma erişim yoktur; bu yüzden "diski imajla" gibi klasik adımlar bulutta "snapshot al" gibi API tabanlı eşdeğerlere dönüşür.

Bu makale, bulut-native forensics'i üç ana bulut sağlayıcısı (AWS, Azure, GCP) üzerinden, container/serverless özel durumlarıyla birlikte, savunma/tespit odaklı olarak ele alır.

## Bölüm 1: AWS - CloudTrail ve GuardDuty Derin Analiz

### CloudTrail: Kontrol Düzleminin Olay Günlüğü

**Tanım**: CloudTrail, AWS hesabınızda yapılan hemen her API çağrısını (konsol, CLI, SDK, başka bir AWS servisi tarafından yapılan çağrılar dahil) kaydeden servistir. Her kayıt; çağrıyı yapan kimlik (IAM user/role/kök kullanıcı), kaynak IP, zaman damgası, istenen aksiyon (örnek: `AssumeRole`, `PutObject`, `CreateUser`), yanıt (başarılı/başarısız, hata kodu) ve etkilenen kaynakları içerir.

**Çalışma mantığı**: CloudTrail iki temel event türü üretir:
- **Management events (kontrol düzlemi)**: Kaynak oluşturma/silme/değiştirme, IAM politika değişiklikleri, güvenlik grubu kuralları vb. Varsayılan olarak açık ve genelde ücretsizdir.
- **Data events (veri düzlemi)**: S3 nesne bazlı erişim (`GetObject`, `PutObject`), Lambda invoke'ları gibi yüksek hacimli olaylar. **Varsayılan olarak KAPALIDIR** çünkü hacim ve maliyet yüksektir - bu, adli analiz açısından kritik bir kördür.

**Neden önemli - KÖK NEDEN**: Bir saldırgan bir S3 bucket'ındaki hassas veriyi dışarı sızdırdığında, eğer data event loglama açık değilse, "kim hangi dosyayı indirdi" sorusuna CloudTrail'den asla cevap alamazsınız - sadece bucket policy değişikliği gibi management event'leri görürsünüz. Bu, saldırı sonrası en sık karşılaşılan "kanıt boşluğu"dur.

**Tespit ve analiz metodolojisi**:
1. **Olay zinciri kurma (event chaining)**: Bir sızıntı genelde tek bir API çağrısı değil, bir zincirdir: `GetCallerIdentity` (keşif) -> `AssumeRole` (yetki yükseltme/yanal hareket) -> `CreateAccessKey` (kalıcılık) -> `PutBucketPolicy` (veri dışarı açma) -> data event `GetObject` (sızıntı). CloudTrail'i tek olay olarak değil, `sourceIPAddress`, `userIdentity.arn` ve zaman penceresi ile korelasyonlu bir zincir olarak okumak gerekir.
2. **`userIdentity` alanının derin okunması**: CloudTrail kaydındaki `userIdentity.type` alanı (`IAMUser`, `AssumedRole`, `FederatedUser`, `Root`) saldırının hangi kimlik katmanında olduğunu gösterir. Özellikle `AssumedRole` durumunda `sessionContext.sessionIssuer` alanı, hangi rolün/politikanın gerçekte kullanıldığını gösterir - bu, geçici kimlik bilgileriyle (temporary credentials) yapılan saldırılarda izleme zincirinin anahtarıdır.
3. **Anomali işaretleri**: Aynı erişim anahtarıyla coğrafi olarak imkansız mesafede ardışık çağrılar (impossible travel), normalde kullanılmayan bölgelerde (region) ani aktivite, `console.aws.amazon.com` dışı bir `userAgent` ile yapılan hassas çağrılar (özellikle otomatize saldırı araçlarının varsayılan user-agent string'leri).
4. **Log manipülasyonuna karşı dikkat**: Saldırgan yeterli yetkiye sahipse `StopLogging`, `DeleteTrail` veya trail'i hedef almayan bir S3 bucket'ına yönlendirme gibi aksiyonlarla kendi izini silmeye çalışabilir. Bu yüzden CloudTrail'in kendisi de bir hedeftir; bu olaylar en yüksek önceliğiyle alarm üretmelidir.

**SAVUNMA**:
- CloudTrail'i **organizasyon genelinde (organization trail)** ve **tüm bölgelerde (all-region)** etkinleştirin; tek bölgeli trail, saldırganın kullanılmayan bir bölgede işlem yapmasıyla kolayca atlatılır.
- Logları **ayrı, kilitli bir hesapta (log archive account)**, mümkünse **S3 Object Lock (WORM)** ile saklayın - böylece log-hesabını ele geçirmiş bir saldırgan bile geçmiş kayıtları silemez.
- **Data event loglamayı** en azından hassas bucket'lar ve Lambda fonksiyonları için açın.
- CloudTrail'in kendisine yönelik değişiklikleri (`StopLogging`, `DeleteTrail`, `UpdateTrail`) EventBridge + SNS/Lambda ile gerçek zamanlı alarma bağlayın.
- **CloudTrail Lake** veya merkezi bir SIEM'e (Sentinel, Splunk, vb.) aktarım yaparak retansiyonu genişletin - varsayılan konsol görüntüleme sadece 90 günlük olay geçmişi sunar.

### GuardDuty: Yönetilen Tehdit Tespiti

**Tanım**: GuardDuty, CloudTrail loglarını, VPC Flow Logs'u ve DNS sorgu loglarını sürekli analiz ederek bilinen kötü amaçlı IP/domain listeleri, davranışsal anomali modelleri ve makine öğrenmesi ile tehdit bulguları (finding) üreten yönetilen bir servistir.

**Çalışma mantığı**: GuardDuty ham log erişimi gerektirmez - AWS altyapısında arka planda çalışır ve sadece **bulgu (finding)** üretir. Bulgular; `Recon:` (keşif), `UnauthorizedAccess:`, `CredentialAccess:`, `Persistence:`, `Exfiltration:` gibi MITRE ATT&CK benzeri kategorilere ayrılır. Örneğin `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration` bulgusu, bir EC2 instance'ının metadata servisinden (IMDS) alınan geçici kimlik bilgilerinin, o instance dışından kullanıldığını işaret eder - klasik bir SSRF-to-credential-theft senaryosunun somut göstergesidir.

**Neden önemli**: GuardDuty, analistin CloudTrail'i satır satır okuması gerekmeden "nereye bakmalı" sorusuna hazır bir başlangıç noktası sunar; ancak **bulgu = kesin ihlal değildir**, doğrulama (triage) hala gerekir.

**Tespit metodolojisi - bulgu doğrulama**:
1. Bulgunun işaret ettiği kimlik/kaynak (`resource.instanceDetails` veya `resource.accessKeyDetails`) üzerinden CloudTrail'de o kimliğe ait tüm aktiviteyi zaman penceresiyle sınırlayarak çekin.
2. Bulgu zamanından **önce** ve **sonra** ne olduğunu inceleyin - saldırının başlangıç noktası genelde bulgu zamanından önceki keşif adımlarındadır.
3. VPC Flow Logs ile çapraz doğrulama yapın: GuardDuty'nin işaret ettiği IP ile gerçek network trafiği eşleşiyor mu.

**SAVUNMA**:
- GuardDuty'yi tüm hesaplarda ve tüm bölgelerde açın, bulguları merkezi bir güvenlik hesabına (delegated administrator) toplayın.
- S3 Protection, EKS Protection, Malware Protection, Lambda Protection gibi ek modülleri ihtiyaca göre açın - varsayılan kurulum sadece temel VPC/CloudTrail/DNS analizini kapsar.
- Yüksek/kritik önemli bulgular için otomatik yanıt (örnek: Lambda ile IAM anahtarını otomatik devre dışı bırakma) kurun, ancak otomatik aksiyonların yanlış-pozitif riskini de değerlendirin.

### VPC Flow Logs ile Korelasyon

VPC Flow Logs, network arayüzü seviyesinde kaynak/hedef IP, port, protokol, byte sayısı ve kabul/red bilgisini kaydeder - paket içeriğini değil, akış metaverisini (metadata) tutar. Bu, CloudTrail'in "kim ne yaptı" sorusunu, "veri nereye ve ne kadar gitti" sorusuyla tamamlar. Örneğin CloudTrail'de görülen bir `GetObject` çağrısının ardından, aynı zaman diliminde beklenmedik bir dış IP'ye büyük hacimli giden (egress) trafik varsa, bu veri sızıntısının somut network kanıtıdır. **KÖK NEDEN olarak**: CloudTrail servis API'sini görür ama fiili veri hacmini görmez; Flow Logs ise veri hacmini görür ama hangi kullanıcının sorumlu olduğunu görmez - ikisi birlikte kullanılmadan tam resim çıkmaz.

## Bölüm 2: Azure - Sentinel ve Defender

### Azure Activity Log ve Sentinel

**Tanım**: Azure Activity Log, AWS CloudTrail'in eşdeğeridir - abonelik (subscription) seviyesinde kaynak oluşturma/silme/değiştirme gibi kontrol düzlemi olaylarını kaydeder. **Microsoft Sentinel** ise bu logları (ve Azure AD/Entra ID sign-in logları, Defender bulguları, özel kaynaklar dahil) toplayan, korelasyon kuralları (analytics rules) çalıştıran ve olay (incident) oluşturan bulut-native SIEM/SOAR katmanıdır.

**Çalışma mantığı**: Sentinel, verileri **Log Analytics workspace** üzerinde KQL (Kusto Query Language) ile sorgular. Bulut-native forensics açısından önemi, farklı kaynaklardan (Activity Log, Entra ID sign-in log, Defender for Cloud bulguları, ağ NSG flow logları) gelen veriyi **tek bir sorgu katmanında korelasyonlamayı** mümkün kılmasıdır - AWS tarafında bunu genelde ayrı servisleri manuel birleştirerek ya da harici bir SIEM'e aktararak yapmak gerekir.

**Tespit metodolojisi**:
- **Entra ID (eski adıyla Azure AD) sign-in logları** ile Activity Log'un korelasyonu: Bir yönetici hesabının sign-in logunda "riskli oturum açma" (impossible travel, anonim IP, bilinmeyen cihaz) işareti varsa, aynı kimliğe ait Activity Log'daki kaynak değişikliklerini (özellikle RBAC rol atamaları, `Microsoft.Authorization/roleAssignments/write`) zaman penceresiyle inceleyin.
- **Conditional Access ve MFA olayları**: Bir saldırganın MFA'yı atlatmaya çalıştığı durumlar (örnek: token replay, adversary-in-the-middle phishing) sign-in loglarında `authenticationRequirement` ve `conditionalAccessStatus` alanlarında iz bırakır.
- **Sentinel'de UEBA (User and Entity Behavior Analytics)**: Kullanıcıların normal davranış profilinden sapmaları (örnek: hiç erişmediği bir kaynak grubuna erişim) otomatik skorlanır; bu, "bilinen kötü"yü değil "anormal"i yakalamaya çalışan davranışsal bir katmandır.

**Microsoft Defender ailesi** (Defender for Cloud, Defender for Endpoint, Defender for Identity, Defender for Office 365), farklı katmanlardaki (bulut kaynağı, endpoint, on-prem AD/Entra ID, e-posta) tehdit tespitini Sentinel'e besler. Örneğin Defender for Identity, on-prem Active Directory'deki Kerberoasting veya DCSync gibi saldırıları tespit edip Sentinel'e bir olay olarak yansıtabilir - bu, hibrit ortamlarda (on-prem + bulut) adli analizin tek bir konsolda birleşmesini sağlar.

**SAVUNMA**:
- Log Analytics workspace retansiyonunu (varsayılan genelde kısa) ihtiyaca göre uzatın ve kritik tabloları (`SigninLogs`, `AuditLogs`, `AzureActivity`) mutlaka Sentinel'e bağlı tutun.
- Diagnostic Settings ile her kaynağın (Key Vault, Storage Account, SQL) kendi loglarını merkezi workspace'e akıtmasını sağlayın - Azure'da bu, kaynak bazında ayrı ayrı yapılandırılması gereken bir adımdır ve sıkça atlanır.
- Sentinel analytics rule'larını MITRE ATT&CK tekniklerine eşleştirilmiş şablonlarla başlatıp organizasyona özel finetune edin.

## Bölüm 3: GCP - Cloud Audit Logs

**Tanım**: GCP'de eşdeğer yapı **Cloud Audit Logs**'tur ve üç alt türü vardır: **Admin Activity** (kaynak oluşturma/değiştirme - her zaman açık, kapatılamaz), **Data Access** (veri okuma/yazma - varsayılan çoğunlukla KAPALI, açık metin/hassas veri içerdiği için), **System Event** (Google'ın sistem tarafından tetiklenen otomatik işlemler).

**KÖK NEDEN - AWS ile paralellik**: GCP'nin Data Access loglarını varsayılan kapalı tutması, tıpkı AWS'nin S3 data event'lerini kapalı tutması gibi aynı maliyet/hacim dengesinden kaynaklanır. Bu üçü bulutta da ortak desen: **"kim ne yaptı" (kontrol düzlemi) genelde varsayılan açık, "hangi veriye dokunuldu" (veri düzlemi) genelde varsayılan kapalı**. Adli hazırlık (forensic readiness) yapan bir savunmacı bu deseni bilmeli ve kritik veri kaynakları için data access loglamayı bilinçli olarak açmalıdır.

**Tespit metodolojisi**:
- Cloud Audit Logs, **Cloud Logging** üzerinden merkezi sorgulanır; log-based metric'ler ve alert policy'ler ile IAM politika değişiklikleri (`SetIamPolicy`), servis hesabı anahtar oluşturma (`CreateServiceAccountKey`) gibi yüksek riskli olaylar gerçek zamanlı izlenebilir.
- **VPC Service Controls** ihlal logları, bir servis hesabının veya kullanıcının tanımlı güvenlik perimetresi dışına veri taşıma girişimini gösterir - bu, GCP'ye özgü, AWS/Azure'da birebir karşılığı olmayan güçlü bir data-exfiltration tespit katmanıdır.
- **Servis hesabı (service account) anahtar suistimali**, GCP'de en yaygın kalıcılık ve yanal hareket vektörüdür; çünkü bir servis hesabı anahtarı indirilebilir JSON dosyasıdır ve sızarsa uzun süreli, IP/cihaz kısıtlaması olmadan kullanılabilir. Audit loglarda anahtar oluşturma/indirme olaylarının izlenmesi kritiktir.

**SAVUNMA**:
- Data Access loglarını en azından hassas BigQuery veri setleri ve Cloud Storage bucket'ları için açın.
- Audit logları ayrı bir "log sink" projesine, mümkünse BigQuery'ye export edip uzun dönem/değiştirilemez saklayın.
- Servis hesabı anahtarlarını mümkün olduğunca ortadan kaldırıp Workload Identity Federation gibi anahtarsız mekanizmalara geçin - bu hem saldırı yüzeyini azaltır hem de forensics'i basitleştirir (kanıt artık "sızan bir dosya" değil, izlenebilir bir kimlik federasyonu olayıdır).

## Bölüm 4: Container ve Serverless Adli Analiz - Ephemeral Ortamda Kanıt Toplama

### Neden Farklı Bir Metodoloji Gerekir

**KÖK NEDEN**: Klasik adli analiz "olay anı (an) - inceleme anı" arasında sistemin hayatta kalacağını varsayar. Container'larda (özellikle orkestrasyon altında - Kubernetes/ECS) ve serverless fonksiyonlarda (Lambda/Cloud Functions/Azure Functions) bu varsayım geçersizdir:

- Bir container, sağlık kontrolü (health check) başarısız olduğunda veya otomatik ölçeklendirme (autoscaling) tetiklendiğinde saniyeler içinde sonlandırılıp yeniden oluşturulabilir - **suç mahalli kendini yok eder**.
- Bir Lambda execution environment, çağrı bittikten sonra "sıcak" (warm) tutulabilir ama garantisi yoktur; sonraki çağrıya farklı, tertemiz bir environment atanabilir.
- Container image katmanları değişmez (immutable) olabilir ama **çalışma zamanı durumu (runtime state)** - bellekteki process'ler, geçici dosya sistemi değişiklikleri, aktif ağ bağlantıları - konteyner durduğu an kaybolur.

### Nasıl Çalışır - Kanıt Toplama Yaklaşımları

1. **Canlı yakalama öncelikli (live capture first)**: Klasik "önce imajla, sonra analiz et" sırası burada tersine döner - önce **çalışırken** mümkün olduğunca fazla veri toplamak gerekir, çünkü "sonra"sı olmayabilir. Bu; container'ın `exec` ile process listesi, ağ bağlantıları, açık dosya tanımlayıcıları (file descriptors) gibi bilgilerin **olay anında** çıkarılması anlamına gelir.
2. **Container imaj/katman analizi (post-mortem, ama sınırlı)**: Container image'in kendisi (registry'de saklanan katmanlar) statik olarak incelenebilir - bu, "hangi kod çalışıyordu" sorusuna cevap verir ama "runtime'da ne oldu" sorusuna vermez. İkisi farklı soruları cevaplar; birini diğeriyle karıştırmamak gerekir.
3. **Kubernetes özelinde**: `kubectl` audit logları (API server'a yapılan her istek - pod oluşturma, exec, port-forward), pod'un kendisinden daha uzun yaşar ve genelde en güvenilir kanıt kaynağıdır. Bir saldırganın `kubectl exec` ile bir pod'a girip komut çalıştırması, pod loglarında görünmeyebilir ama **audit log'da mutlaka görünür** (eğer audit logging aktifse).
4. **Sidecar / eBPF tabanlı sürekli izleme**: Runtime'da ne olduğunu, olay bittikten sonra değil, **olurken** dışarı akıtan (Falco gibi eBPF tabanlı araçların çalışma mantığı budur) bir mekanizma olmadan, ephemeral container'larda runtime forensics pratik olarak imkansıza yakındır. Bu, savunma tarafında en kritik mimari karardır: **kanıt toplamayı olaydan SONRAYA değil, olaydan ÖNCEYE (sürekli log akışı) taşımak**.
5. **Serverless (Lambda vb.) için**: Kod ve çalışma zamanı tamamen soyutlandığı için tek güvenilir kanıt kaynağı, platformun kendi loglarıdır - CloudWatch Logs (her invocation'ın stdout/stderr'i), X-Ray (dağıtık izleme/tracing, çağrı zincirini görselleştirir), ve CloudTrail (Lambda'nın hangi IAM rolü ile hangi AWS API'lerini çağırdığı). Fonksiyonun **içinde** ne olduğunu (bellek durumu, yerel değişkenler) sonradan çıkarmak genelde mümkün değildir; sadece fonksiyonun log'a yazdığı ne varsa odur.

### TESPİT ve SAVUNMA - Önceden Hazırlık (Forensic Readiness)

Bulut-native ortamda forensic readiness, "olay olunca ne yaparız" sorusundan çok, **"olay olmadan önce ne kaydediyoruz"** sorusuna dönüşür:

- **Kubernetes audit logging'i mutlaka açık tutun** ve merkezi bir log deposuna (SIEM) akıtın; API server'ın kendisi log kaynağıdır, pod'lar değil.
- **Container çalışma zamanı güvenlik araçları** (Falco, veya bulut sağlayıcının kendi runtime threat detection'ı - GuardDuty EKS Protection, Defender for Containers) ile anomali davranışını (beklenmeyen process başlatma, ayrıcalık yükseltme, konteyner içi shell açma) gerçek zamanlı yakalayın - bu araçlar aslında "olay anındaki kanıt"ı, olay bitmeden önce dışarı taşıyan mekanizmalardır.
- **Immutable/read-only container image politikası** ile, bir saldırganın container içine kalıcı değişiklik yapmasını zorlaştırın; bu hem saldırı yüzeyini azaltır hem de "ne değişti" sorusunu basitleştirir (değişmemesi gerekeni değişmiş görmek daha kolay bir anomalidir).
- **Snapshot alma stratejisi**: Şüpheli bir EC2/VM instance'ı hemen sonlandırmak yerine, önce **EBS/disk snapshot'ı alın**, ağ izolasyonu için güvenlik grubunu değiştirin (instance'ı kapatmadan izole edin), sonra inceleyin. Bu, klasik "kapatma diski çıkar" yaklaşımının bulut-native karşılığıdır: fiziksel disk yerine API ile tetiklenen bir snapshot işlemi.
- **Lambda/serverless için log retansiyonunu bilinçli ayarlayın**: CloudWatch Logs varsayılan olarak **sınırsız saklar ve bu maliyetlidir ama kapatılırsa kanıt da kaybolur** - retansiyon süresini güvenlik/uyumluluk gereksinimine göre bilinçli belirleyin, varsayılana güvenmeyin.

## Yaygın Hatalar

1. **"Log servisi açık, demek ki her şey kaydediliyor" yanılgısı**: CloudTrail/Activity Log/Cloud Audit Logs açık olsa bile, data-plane olayları (S3 object erişimi, BigQuery veri okuma) çoğu zaman ayrı ve varsayılan kapalı bir ayardır. Kurulumu doğrulamadan "loglarız zaten" varsayımı, olay sonrası en büyük kanıt boşluğunun sebebidir.
2. **Log'ları kaynağın kendisiyle aynı hesap/projede tutmak**: Saldırgan o hesabı/projeyi ele geçirirse logları da silebilir. Log'lar ayrı, kısıtlı erişimli, mümkünse değiştirilemez (WORM/Object Lock) bir depoda tutulmalı.
3. **Retansiyon süresini varsayılana bırakmak**: Çoğu servisin konsol/varsayılan log görünümü 30-90 gün gibi kısa bir pencereye sahiptir; bir sızıntı aylar sonra fark edildiğinde kanıt çok önce silinmiş olabilir.
4. **Container/serverless'i "geleneksel sunucu gibi" incelemeye çalışmak**: Ephemeral bir ortamda "diski imajla" refleksi zaman kaybıdır - ortam çalışırken kanıt toplanmalı veya önceden sürekli akan bir izleme katmanı (audit log, eBPF sidecar) kurulmuş olmalıdır.
5. **Tek bulut kaynağını tek başına okumak**: CloudTrail'i CloudTrail olarak, VPC Flow Logs'u Flow Logs olarak ayrı ayrı okumak, saldırı zincirinin sadece bir parçasını gösterir. Kontrol düzlemi + veri düzlemi + ağ katmanı birlikte korelasyonlanmadan tam resim çıkmaz.
6. **IAM/kimlik zincirini takip etmemek**: Geçici kimlik bilgileri (assumed role, federated identity, service account impersonation) ile yapılan işlemlerde, "görünen" kimlik ile "gerçek" kaynak kimliği farklı olabilir; `sessionContext`/`sessionIssuer` gibi alanlar atlanırsa saldırının gerçek başlangıç noktası kaybolur.
7. **Otomatik yanıt mekanizmalarını kör kör kurmak**: GuardDuty/Sentinel bulgusuna dayanarak otomatik olarak kaynak silme/hesap kilitleme gibi aksiyonlar, yanlış-pozitif durumunda iş sürekliliğini bozabilir ve hatta saldırganın "gürültü yaratıp" savunmayı kendi aleyhine yanlış hedefe yönlendirmesine (alarm fatigue / gaming) zemin hazırlayabilir; doğrulama adımı olmadan tam otomasyon riskli olabilir.

## Sonuç

Bulut-native forensics'in özeti şu cümleyle kurulabilir: **kanıt artık "toplanan" değil, "önceden akıtılan" bir şeydir.** Klasik disk/memory/network forensics "olay sonrası git ve incele" mantığıyla çalışırken, bulut ortamı - özellikle container ve serverless gibi ephemeral katmanlarda - kanıtın var olması için olay **gerçekleşmeden önce** bir log/izleme altyapısının kurulmuş olmasını gerektirir. AWS CloudTrail+GuardDuty+VPC Flow Logs, Azure Activity Log+Sentinel+Defender, GCP Cloud Audit Logs+VPC Service Controls - hepsi aynı ilkeye hizmet eder: kontrol düzlemini, veri düzlemini ve ağ katmanını ayrı ayrı değil, korelasyonlu ve merkezi, değiştirilemez bir şekilde önce kaydet, sonra sorgula. Bir savunma/mühendislik ekibinin en değerli yatırımı, saldırı sonrası "keşke şu log'u tutsaydık" pişmanlığını önceden ortadan kaldıran bir log mimarisi kurmaktır.
