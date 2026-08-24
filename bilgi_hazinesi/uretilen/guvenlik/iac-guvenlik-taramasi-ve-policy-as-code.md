# IaC Güvenlik Taraması ve Policy-as-Code (Terraform/OPA/Kyverno/Checkov)

## Tanım: Bu Katman Ne İşe Yarar?

Infrastructure as Code (IaC), bulut kaynaklarının (VPC, S3 bucket, IAM rolü, Kubernetes cluster'ı) el ile konsoldan tıklanarak değil, Terraform, CloudFormation, Pulumi gibi araçlarla yazılan deklaratif kod dosyalarıyla tanımlanması pratiğidir. Bu pratik hıza ve tekrarlanabilirliğe muazzam katkı sağlar, ama aynı zamanda güvenlik hatasının da kod haline gelmesi ve `git push` ile milisaniyeler içinde onlarca ortama yayılması anlamına gelir.

Bu makalenin konusu, "IaC yazalım" seviyesinin ötesinde, üç ayrı ama birbirini tamamlayan savunma katmanını ele almaktır:

1. **Statik IaC taraması** (Checkov, tfsec benzeri araçlar): Terraform/CloudFormation kodu apply edilmeden ÖNCE, kod içindeki güvenlik yanlış yapılandırmalarını (misconfiguration) tespit etmek.
2. **Admission-time policy-as-code** (OPA/Gatekeeper, Kyverno): Kubernetes cluster'ına bir kaynak (Pod, Deployment, Service) girmeden hemen önce, canlı API sunucusu seviyesinde kuralları zorunlu kılmak (enforcement).
3. **Drift tespiti**: Terraform state dosyasının tanımladığı "olması gereken durum" ile bulutta fiilen var olan "gerçek durum" arasındaki sapmayı yakalamak — çünkü biri konsoldan elle bir güvenlik grubunu değiştirdiğinde, IaC artık yalan söylemeye başlar.

Bu üçü birlikte "preventive control" (önleyici kontrol) katmanını oluşturur: saldırgan bir kaynağı istismar etmeden önce, hatalı yapılandırmanın üretim ortamına hiç girmemesini sağlamak. Bu, "detective control" (SIEM, runtime tespit) katmanının bir öncekisi ve tamamlayıcısıdır — ikisi de gereklidir, biri diğerinin yerini tutmaz.

## Kök Neden: Neden Bu Katman Gerekli?

### Kök Neden 1 — Yanlış Yapılandırma, Bulut Güvenlik İhlallerinin Baskın Nedenidir

Bulut ortamlarındaki güvenlik olaylarının büyük çoğunluğu, bulut sağlayıcısının altyapısındaki bir açıktan değil, müşterinin kendi yapılandırma hatasından kaynaklanır (bu ayrım "shared responsibility model" ile tanımlanır — bulut sağlayıcısı "bulutun güvenliğinden", müşteri "bulut İÇİNDEKİ her şeyin güvenliğinden" sorumludur). Herkese açık bırakılmış S3 bucket'ları, `0.0.0.0/0`'a açık security group'lar, aşırı yetkili (over-privileged) IAM rolleri, şifrelenmemiş disk imajları — bunların hepsi kod seviyesinde bir satırlık hatadır ve manuel code review'da gözden kaçması çok kolaydır. Kod seviyesinde otomatik tarama olmadan, bu hatalar production'a "sessizce" ulaşır.

### Kök Neden 2 — Ölçek, İnsan Gözden Geçirmesini İmkansız Kılar

Bir organizasyon günde onlarca Terraform pull request'i merge ediyorsa, her PR'ı bir güvenlik mühendisinin elle okuyup "bu S3 bucket public mi, bu IAM policy'de wildcard var mı" diye kontrol etmesi ölçeklenemez. Statik analiz araçları bu kontrolü CI/CD pipeline'ına gömerek, insan darboğazını ortadan kaldırır ve tutarlılığı garanti eder (insan yorulur, unutur; makine unutmaz).

### Kök Neden 3 — Kubernetes'in Deklaratif API'si, "Kim Neyi Deploy Edebilir" Sorusunu Kod Seviyesinde Cevaplamayı Gerektirir

Kubernetes'te bir geliştirici `kubectl apply` dediğinde, bu istek doğrudan API sunucusuna gider ve API sunucusu bunu (RBAC yetkisi varsa) kabul eder. Eğer o Pod tanımı `privileged: true`, `hostNetwork: true` veya `runAsUser: 0` gibi tehlikeli alanlar içeriyorsa, RBAC bunu engellemez — RBAC sadece "bu kullanıcı Pod oluşturabilir mi" sorusuna cevap verir, "oluşturduğu Pod güvenli mi" sorusuna değil. Bu boşluğu dolduran katman **admission control**'dür: kaynak etcd'ye yazılmadan hemen önce araya giren, kaynağın İÇERİĞİNİ politika kurallarına göre denetleyen bir kapı.

### Kök Neden 4 — IaC ile Gerçek Dünya Arasında Senkronizasyon Garantisi Yoktur (Drift)

Terraform "declarative" çalışır: kod, hedef durumu tanımlar; Terraform bu durumu gerçekleştirmek için bir state dosyası tutar. Ancak biri AWS konsoluna girip elle bir security group kuralı eklerse veya bir acil müdahale sırasında `kubectl edit` ile canlı bir kaynağı değiştirirse, gerçek dünya durumu artık state dosyasındaki tanımdan sapmıştır. Bu sapmaya **drift** denir. Drift tehlikelidir çünkü: (a) IaC kodu artık "yalan söyler" — okuyan kişi kodun gerçeği yansıttığını sanır ama yansıtmaz; (b) bir sonraki `terraform apply` bu elle yapılan değişikliği geri alabilir (istenmeyen kesinti) ya da drift'i fark etmeden üstüne yeni değişiklik uygular; (c) saldırganlar tam olarak bu boşluğu kullanır — IaC'de görünmeyen, elle açılmış bir arka kapıyı.

## Katman 1: Statik IaC Taraması (Checkov, tfsec benzeri araçlar)

### Çalışma Mantığı

Bu araçlar Terraform HCL dosyalarını, CloudFormation şablonlarını veya Kubernetes manifest'lerini **parse edip bir soyut sözdizimi ağacına (AST benzeri bir iç temsile)** dönüştürür ve bunun üzerinde önceden tanımlı kural setleriyle (rule set) eşleştirme yapar. Kural örnekleri: "bir `aws_s3_bucket` kaynağının `server_side_encryption_configuration` bloğu yoksa uyar", "bir `aws_security_group_rule` kaynağında `cidr_blocks = ["0.0.0.0/0"]` ve port 22 (SSH) birlikte varsa kritik seviyede uyar", "bir IAM policy dokümanında `Action: "*"` ve `Resource: "*"` birlikte varsa uyar (aşırı yetkilendirme)".

Önemli nokta: bu araçlar kodu **çalıştırmaz** (uygulamaz), sadece statik olarak okur. Bu nedenle "kaynak apply edilmeden önce" güvenlik geri bildirimi verebilirler — yani CI/CD pipeline'ında `terraform plan` aşamasında ya da hatta `git commit` öncesi (pre-commit hook olarak) çalıştırılabilirler. Bu, "shift-left" (güvenliği geliştirme döngüsünün en soluna, mümkün olduğunca erkene taşıma) prensibinin somut uygulamasıdır: hatayı üretim ortamında değil, geliştiricinin ekranında, saniyeler içinde yakalamak.

Bazı araçlar sadece kodu değil, `terraform plan` çıktısının JSON formatını da analiz edebilir. Bunun avantajı: plan çıktısı, değişkenlerin (variables) ve modüllerin çözümlenmiş (resolved) halini gösterir — yani statik kod okumada gözden kaçabilecek "bu değişken production'da hangi değeri alacak" belirsizliği ortadan kalkar. Böylece "bu bucket'ın gerçekte hangi ortamda public olacağı" gibi sorulara daha kesin cevap verilebilir.

### Tespit

- **CI/CD pipeline entegrasyonu**: Tarama aracını `terraform plan` adımından hemen sonra, `terraform apply`'dan önce çalıştırıp, kritik/yüksek şiddetli bulgularda pipeline'ı başarısız (fail) yapmak — böylece güvenlik açığı olan kod merge edilemez.
- **Baseline ve suppression yönetimi**: Yeni başlayan bir organizasyonda binlerce mevcut bulgu çıkabilir; bunları "kabul edilmiş risk" (baseline) olarak işaretleyip sadece YENİ eklenen bulgulara odaklanmak, aracın "gürültü" nedeniyle göz ardı edilmesini önler.
- **Kural kapsamı takibi**: Hangi kuralların aktif, hangilerinin bilinçli olarak devre dışı bırakıldığını (ve NEDEN) periyodik olarak denetlemek — sessizce devre dışı bırakılmış kritik bir kural, taramanın kendisini anlamsız kılar.
- **SARIF/rapor formatlarını merkezi bir güvenlik panosunda toplamak**: Tek bir repo değil, organizasyon genelindeki tüm repoların tarama sonuçlarını tek bir yerde görebilmek, sistemik zayıf noktaları (örn. "tüm takımlar şifreleme bloğunu unutuyor") ortaya çıkarır.

### Savunma

- Taramayı **pull request** aşamasında zorunlu kılmak (pre-merge gate), sadece bilgilendirici (informational) bırakmamak — bulgu "kritik" ise merge engellenmelidir.
- **Golden module / güvenli varsayılan modüller** sağlamak: geliştiricilerin sıfırdan `aws_s3_bucket` yazması yerine, şifrelemesi, versioning'i, public-access-block'u zaten doğru ayarlanmış onaylı bir Terraform modülünü kullanmasını teşvik etmek. Bu, "her seferinde doğru yapılandırmayı hatırlamak" yükünü geliştiriciden alıp modül sahibine (platform ekibi) verir.
- **Politikanın kod olarak versiyonlanması**: kural setinin kendisi de bir repo'da, code review ile değişsin — böylece "kim, ne zaman, neden bir kuralı gevşetti" izlenebilir olsun.
- Taramayı sadece Terraform ile sınırlı tutmamak; container image'ları (Dockerfile), Kubernetes manifest'leri ve CI/CD pipeline tanımlarının kendisi (`.gitlab-ci.yml`, GitHub Actions workflow'ları) de benzer statik analizden geçirilmeli, çünkü pipeline tanımının kendisi de bir saldırı yüzeyidir (örn. secret'ların log'a basılması, üçüncü taraf action'lara aşırı yetki verilmesi).

### Yaygın Hatalar

- Aracı sadece "bilgi amaçlı" çalıştırıp hiçbir bulguyu pipeline'ı durdurmaya yetkilendirmemek — bu durumda araç sadece "vicdan rahatlatma" işlevi görür, gerçek bir kontrol değildir.
- Tüm kuralları aynı önem derecesinde ele almak; "kritik" (herkese açık veritabanı) ile "düşük" (etiketleme eksikliği) bulguyu aynı ciddiyetle işlemek, gerçek risklerin gürültüde kaybolmasına yol açar.
- Sadece `terraform plan`'ı taramak, ama gerçek bulut ortamındaki (zaten var olan) kaynakları hiç periyodik olarak yeniden taramamak — yeni kurallar eklendiğinde eski kaynaklar kör nokta olarak kalır.

## Katman 2: Admission-Time Policy-as-Code (OPA/Gatekeeper, Kyverno)

### Çalışma Mantığı

Kubernetes API sunucusu bir isteği (örneğin bir Pod oluşturma isteğini) işlerken belirli aşamalardan geçirir: kimlik doğrulama (authentication), yetkilendirme (authorization/RBAC), ve son olarak **admission control**. Admission control aşaması iki alt aşamadan oluşur: **mutating** (isteği değiştirebilen, örn. varsayılan değer ekleyen) ve **validating** (isteği sadece kabul/red edebilen) webhook'lar. Policy-as-code araçları (OPA/Gatekeeper ve Kyverno) tam olarak bu noktada, **ValidatingAdmissionWebhook** (ve gerektiğinde MutatingAdmissionWebhook) mekanizmasına bağlanarak çalışır.

Akış şöyledir: bir kullanıcı `kubectl apply -f pod.yaml` çalıştırır → istek API sunucusuna gider → authentication ve RBAC geçilir → API sunucusu, kaynağın JSON temsilini admission webhook olarak kayıtlı olan Gatekeeper/Kyverno servisine bir HTTP çağrısıyla gönderir → bu servis, kendi içinde tanımlı politika kurallarını bu JSON'a uygular → "izin ver" ya da "reddet" (ve neden reddettiğine dair bir mesaj) döner → API sunucusu buna göre kaynağı etcd'ye yazar ya da isteği kullanıcıya hata olarak geri döndürür.

**OPA (Open Policy Agent) / Gatekeeper**: OPA, Kubernetes'e özgü olmayan, genel amaçlı bir politika motorudur; kuralları **Rego** adlı bildirim temelli (declarative) bir dille yazılır. Gatekeeper, OPA'yı Kubernetes'e admission controller olarak entegre eden bileşendir ve politikaları `ConstraintTemplate` (kuralın Rego mantığı) ile `Constraint` (o kuralın hangi kaynaklara, hangi parametrelerle uygulanacağı) olmak üzere iki katmanlı bir CRD (Custom Resource Definition) yapısıyla ifade eder. Bu ayrım, bir kuralı bir kere yazıp farklı namespace'lerde farklı parametrelerle (örn. bir namespace'te izinli image registry listesi farklı) tekrar kullanmayı sağlar.

**Kyverno**: Kyverno'nun temel farkı, politikaları Rego gibi ayrı bir dil yerine, doğrudan Kubernetes'in kendi YAML sözdizimiyle (declarative, "Kubernetes-native" bir üslupla) ifade etmesidir. Bu, öğrenme eğrisini düşürür çünkü platform mühendisi zaten bildiği YAML'ı kullanır. Kyverno'nun ayrıca "mutate" (eksik alanları otomatik doldurma, örn. eksik `runAsNonRoot: true` ekleme), "validate" (reddetme) ve "generate" (bir kaynak oluşturulduğunda otomatik olarak ilişkili başka bir kaynak — örn. her yeni namespace'e otomatik bir NetworkPolicy — üretme) olmak üzere üç modu vardır.

### Neden Bu Katman Şart? (Kavramsal Gerekçe)

RBAC "kim yapabilir" sorusuna, admission policy "ne yapabilir" sorusuna cevap verir. Örnek: bir geliştiricinin `Deployment` oluşturma yetkisi (RBAC) olabilir, ama bu onun `privileged: true` bir container çalıştırabileceği, `hostPath` ile node dosya sistemine erişebileceği veya `latest` etiketli, doğrulanmamış bir image çekebileceği anlamına gelmemelidir. Bu tür kısıtlamalar RBAC'ın kapsamı dışındadır (RBAC kaynak TÜRÜ ve fiil — verb — üzerinde çalışır, kaynağın İÇERİĞİ üzerinde değil); admission control bu boşluğu doldurur.

### Tespit

- **Dry-run / audit modu**: Hem Gatekeeper hem Kyverno, kuralı henüz "enforce" (reddet) moduna almadan önce sadece ihlalleri loglayan "audit" veya "dry-run" modunda çalıştırılabilir. Bu, yeni bir kuralı üretime sokmadan önce "bu kural kaç mevcut kaynağı kırar" sorusuna cevap verir — kritik bir güvenlik adımı, çünkü aniden enforce edilen bir kural üretimde geniş çaplı kesintiye yol açabilir.
- **Politika ihlali metriklerini izlemek**: Gatekeeper/Kyverno'nun ürettiği ihlal olaylarını (audit sonuçları) merkezi loglama/metrik sistemine (örn. Prometheus) aktarıp, "hangi namespace, hangi ekip, en çok hangi kuralı ihlal ediyor" trendini görünür kılmak.
- **Webhook sağlığını izlemek**: Admission webhook servisinin kendisi çökerse veya yanıt vermezse ne olacağı kritik bir tasarım kararıdır (`failurePolicy: Fail` mi `Ignore` mi) — bu ayarın izlenmesi ve doğru tarafta hata vermesinin (varsayılan olarak güvenli, "fail closed") sağlanması gerekir.

### Savunma

- **Kademeli devreye alma**: Yeni bir politikayı önce audit modunda çalıştır, ihlalleri gözden geçir, mevcut iş yüklerini düzelt (veya istisna/exemption tanımla), sonra enforce moduna geç. Doğrudan enforce ile başlamak, üretimi durdurma riskini artırır.
- **Temel politika seti** (baseline): En azından şu sınıf kuralları enforce etmek yaygın kabul görür — ayrıcalıklı (`privileged`) container yasağı, `runAsRoot` yasağı (non-root zorunluluğu), host namespace'lerine (`hostNetwork`, `hostPID`, `hostIPC`) erişim yasağı, yalnızca onaylı/güvenilir image registry'lerinden çekim izni, kaynak limiti (CPU/memory) zorunluluğu, `NetworkPolicy` zorunluluğu (varsayılan deny).
- **Exemption/istisna mekanizmasının kendisinin denetlenebilir olması**: Bazı sistem bileşenlerinin (örn. CNI eklentileri) meşru olarak `privileged` çalışması gerekebilir; bu istisnalar genel kuraldan muaf tutulurken, kimin bu istisnayı tanımladığı ve neden gerektiği açıkça dokümante edilmeli — aksi halde istisna mekanizmasının kendisi bir bypass yolu haline gelir.
- **`failurePolicy: Fail` tercih etmek** (webhook'a ulaşılamazsa isteği REDDET), ama bunu yaparken webhook'un kendisinin yüksek erişilebilirlikli (HA) olmasını garanti etmek — aksi halde webhook'un kendisi bir tek hata noktası (single point of failure) olarak cluster'ı kilitleyebilir.

### Yaygın Hatalar

- Politikayı doğrudan enforce modunda, audit aşaması atlanarak devreye almak — bu genelde geniş çaplı, beklenmedik deployment reddiyle sonuçlanır ve ekiplerin policy-as-code'a güvenini kırar.
- Sadece Pod seviyesindeki güvenlik alanlarını (security context) kontrol edip, `NetworkPolicy` zorunluluğu gibi ağ seviyesindeki izolasyonu ihmal etmek — bir Pod "güvenli" security context'e sahip olsa bile, ağ seviyesinde her yere erişebiliyorsa yanal hareket (lateral movement) riski devam eder.
- Politika kod tabanını (Rego/Kyverno YAML) ayrı bir repo'da versiyonlamamak, code review'dan geçirmemek — politikanın kendisi de üretim kodudur ve gözden geçirilmeden değiştirilmemelidir.

## Katman 3: Drift Tespiti

### Çalışma Mantığı

Terraform, `terraform plan` komutunu çalıştırdığında önce mevcut state dosyasındaki kaynakların GERÇEK bulut durumunu bulut sağlayıcının API'sinden sorgulayarak "refresh" eder, sonra bu güncel durumu kod dosyalarında tanımlanan hedef durumla karşılaştırır. Eğer gerçek durum ile state dosyasındaki (bir önceki bilinen) durum arasında fark varsa ve bu fark kod tarafından açıklanmıyorsa (yani kimse kodu değiştirmediği halde bulutta bir şey değişmişse), bu drift'tir. Drift tespiti araçları temelde bu "refresh + diff" işlemini programatik ve periyodik (örn. saatlik/günlük) olarak, insan müdahalesi olmadan çalıştırıp sonucu raporlar veya uyarı üretir.

Drift'in kaynağı çoğunlukla üç kategoridir: (1) bir mühendisin acil bir durumda konsoldan elle müdahale etmesi ("hotfix" sonra unutulur ve koda yansıtılmaz), (2) bulut sağlayıcısının otomatik davranışları (örn. bazı alanların sağlayıcı tarafından arka planda güncellenmesi), (3) kötü niyetli bir aktörün — ele geçirdiği kimlik bilgileriyle — IaC pipeline'ını atlayıp doğrudan bulut konsolu/API'si üzerinden bir arka kapı (örn. yeni bir IAM kullanıcısı, gizli bir security group kuralı) açması. Üçüncü kategori özellikle kritiktir: bu, saldırganın "IaC'nin göremediği" bir değişiklik yapması demektir ve düzenli drift taraması olmadan haftalarca fark edilmeyebilir.

### Tespit

- **Periyodik otomatik `plan` çalıştırma** (sadece apply değil): CI/CD dışında, zamanlanmış bir job ile düzenli aralıklarla `terraform plan` çalıştırıp çıktıyı analiz etmek; çıktıda beklenmeyen bir "değişiklik" (diff) varsa bu bir drift sinyalidir.
- **Bulut sağlayıcısı native config denetim servisleri** (örn. sürekli kaynak yapılandırma değişikliklerini kaydeden servisler) ile CloudTrail/audit log korelasyonu: "bu kaynak ne zaman, kim tarafından, hangi API çağrısıyla değişti" sorusuna cevap aramak — Terraform state'i "ne değişti"yi söyler, audit log "kim ve nasıl değiştirdi"yi söyler; ikisi birlikte olay müdahalesi (incident response) için gereklidir.
- **State dosyasının kendisinin bütünlüğünü izlemek**: state dosyası hassas bilgi (bazen düz metin secret'lar dahil) içerebileceğinden, kim state'e erişti/değiştirdi izlenmeli; state dosyasının saklandığı backend (örn. uzak nesne depolama + kilitleme mekanizması) üzerindeki erişim loglarını denetlemek.
- Drift bulgularını sadece "bilgi" olarak değil, **önem derecesine göre sınıflandırarak** uyarı üretmek — bir etiket (tag) değişikliği ile bir security group'un `0.0.0.0/0`'a açılması aynı önemde değildir.

### Savunma

- **"Konsoldan elle değişiklik yasak" kültürünü ve teknik kontrolünü birlikte uygulamak**: sadece politika ile "elle değişiklik yapmayın" demek yetmez; mümkün olduğunca IAM/RBAC seviyesinde, üretim kaynaklarına doğrudan yazma yetkisini sadece IaC pipeline'ının kullandığı servis hesabına vermek, insan kullanıcılara sadece salt-okunur (read-only) veya acil durum için ayrı, loglanan/onaylı bir "break-glass" (acil durum) yolu tanımlamak.
- **Drift tespit edildiğinde otomatik "reconcile" etmemek, önce insan onayına sunmak**: bazı durumlarda drift kasıtlı ve meşru bir acil müdahaledir; otomatik olarak "koddaki hale geri döndür" davranışı, meşru bir acil düzeltmeyi geri alıp kesintiye yol açabilir. Bunun yerine drift bulgusu bir inceleme kuyruğuna düşmeli.
- **State dosyasını şifrelemek ve erişimini kısıtlamak**: state dosyası genellikle kaynakların bazı hassas özniteliklerini (bazen parola/anahtar gibi alanları) düz metin tutabilir; bu nedenle state backend'inin kendisi de bir güvenlik sınırı olarak ele alınmalı (şifreleme, erişim kontrolü, versiyonlama, kilitleme).
- **Drift'i düzenli bir ritimde (örn. günlük) otomatik taramak**, sadece "birisi fark ederse" reaktif yaklaşıma güvenmemek.

### Yaygın Hatalar

- Drift taramasını hiç kurmamak ve "IaC kodu = gerçeklik" varsayımıyla hareket etmek; bu varsayım zamanla yanlış hale gelir ve kimse ne zaman yanlış hale geldiğini bilmez.
- Drift bulunduğunda körü körüne `terraform apply` çalıştırıp elle yapılan (belki meşru ve gerekli) değişikliği sorgusuz geri almak.
- State dosyasını yerel diskte veya şifrelenmemiş, geniş erişimli bir depoda tutmak — bu, state'in kendisini bir saldırı hedefi haline getirir (state'i ele geçiren, altyapının tüm yapılandırma detaylarını ve bazen kimlik bilgilerini de ele geçirir).

## Üç Katmanın Birlikte Çalışması: Bütünsel Bakış

Bu üç mekanizma, IaC'nin yaşam döngüsünün farklı anlarına denk gelir ve biri diğerinin eksikliğini telafi edemez:

- **Statik IaC taraması**, kod henüz bulutta hiçbir şeye dönüşmeden ÖNCE, en ucuz ve en hızlı düzeltme noktasında çalışır (shift-left). Ama bu katman, Kubernetes cluster'ı İÇİNDE, deploy zamanında dinamik olarak oluşturulan (örn. bir CI job'unun runtime'da ürettiği) manifestleri göremez.
- **Admission-time policy-as-code**, tam olarak bu boşluğu doldurur: kaynağın kaynağı ne olursa olsun (Terraform, elle `kubectl apply`, bir CI pipeline), API sunucusuna ulaştığı an son bir denetim noktasından geçmesini garanti eder. Ama bu katman sadece Kubernetes API'sine giren kaynakları görür; VPC, IAM, S3 gibi bulut sağlayıcı seviyesindeki kaynakları kapsamaz (onun için ayrı bulut-native admission/policy mekanizmaları veya statik IaC taraması gerekir).
- **Drift tespiti**, ilk ikisinin de "atlandığı" senaryoyu — pipeline dışından, doğrudan yapılan değişiklikleri — yakalayan son güvenlik ağıdır.

Savunma mimarisi olgunluğu, bu üç katmanın HER BİRİNİN ayrı ayrı var olmasıyla değil, aralarında **tutarlı bir politika kaynağının** (aynı güvenlik kuralının hem statik tarama kural setinde hem admission policy'de hem de drift uyarı eşiğinde aynı mantıkla ifade edilmesi) paylaşılmasıyla ölçülür. Aksi halde üç ayrı araç, üç ayrı ekip tarafından yönetilen, birbirinden habersiz üç ayrı "gürültü kaynağına" dönüşür ve gerçek güvenlik kazanımı sağlamaz.
