# AWS Bulut Güvenliği: IAM, S3, Metadata SSRF ve Yetki Yükseltme

AWS gibi bir bulut ortamında güvenlik, klasik sunucu güvenliğinden temel olarak farklı bir zihniyet gerektirir. Klasik dünyada tehdit çoğunlukla ağ katmanındaydı; güvenlik duvarı, port tarama ve işletim sistemi zafiyetleri hâkimdi. Bulutta ise saldırı yüzeyinin ağırlık merkezi **kimlik (identity)** ve **yetkilendirme (authorization)** katmanına kaymıştır. AWS'de bir saldırgan çoğunlukla bir exploit ile "içeri girmez"; genellikle sızdırılmış bir credential ile kapıdan yürüyerek girer ve ardından yanlış yapılandırılmış izinler sayesinde ortamda yayılır. Bu makale, bu yeni gerçekliğin dört kritik ekseni olan IAM, S3 açık bucket, metadata SSRF ve privilege escalation konularını derinlemesine, hem istismar hem savunma perspektifiyle ele alıyor.

## Paylaşımlı Sorumluluk Modeli: Neden Çoğu İhlal Müşteri Tarafında Olur

Her şeyden önce zihinsel çerçeveyi doğru kurmak gerekir. AWS'nin **Shared Responsibility Model** (Paylaşımlı Sorumluluk Modeli) dediği şey pratikte şudur: AWS "bulutun güvenliğinden" (fiziksel veri merkezi, hypervisor, altyapı donanımı) sorumludur; müşteri ise "buluttaki güvenlikten" (yapılandırma, IAM politikaları, veri şifreleme, ağ kuralları) sorumludur.

Bu ayrımın pratik sonucu şudur: Kamuya yansıyan büyük AWS ihlallerinin ezici çoğunluğu AWS'nin bir zafiyeti değil, **müşterinin yanlış yapılandırmasıdır (misconfiguration)**. Açık bırakılmış bir S3 bucket, aşırı geniş bir IAM politikası, internete açık bir metadata servisine erişebilen bir web uygulaması... Bunların hiçbiri AWS'nin hatası değildir. Dolayısıyla güvenlik mühendisi olarak sorunun neredeyse tamamı sizin kontrol alanınızdadır; bu hem kötü haber (kaçacak yer yok) hem iyi haberdir (kaderiniz sizin elinizde).

## IAM: Bulut Güvenliğinin Kalbi

### Tanım ve Temel Kavramlar

**IAM (Identity and Access Management)**, AWS'de "kim, neyi, hangi kaynak üzerinde yapabilir?" sorusunu yöneten sistemdir. Dört temel bileşeni vardır:

- **Principal**: Eylemi gerçekleştiren kimlik. Bir IAM user, bir role, bir AWS servisi veya federe bir kimlik olabilir.
- **Action**: Yapılmak istenen işlem, örneğin `s3:GetObject` veya `iam:PassRole`.
- **Resource**: Eylemin uygulandığı kaynak, ARN (Amazon Resource Name) formatında belirtilir.
- **Condition**: Erişimin hangi koşullarda geçerli olduğunu belirleyen ek kısıtlar (kaynak IP, MFA varlığı, kaynak hesap gibi).

Yetkilendirme kararı, bu bileşenlerin bir **policy** (JSON belgesi) içinde birleştirilmesiyle verilir.

### Kök Neden / Çalışma Mantığı: IAM Değerlendirme Mantığı Neden Bu Kadar Önemli

IAM'in güvenliğini anlamak için değerlendirme (evaluation) mantığını içselleştirmek gerekir. AWS bir isteği değerlendirirken şu prensiplerle çalışır:

1. **Varsayılan olarak her şey reddedilir (implicit deny)**. Açıkça izin verilmemiş hiçbir eylem yapılamaz.
2. Bir yerde açık bir **Allow** varsa eylem izinli hâle gelir.
3. Ancak herhangi bir yerde açık bir **Deny** varsa, o **her zaman kazanır**. Explicit deny, her allow'u ezer.

Bu üçlü hiyerarşi (explicit deny > explicit allow > implicit deny) savunmanın temel taşıdır. Çünkü kritik bir kaynağa erişimi kesin olarak engellemek istiyorsanız, geniş bir Allow politikasının yanına dar bir Deny koymak, o Allow'un yanlışlıkla açtığı kapıyı kapatır.

İşin karmaşıklaşan yanı, izinlerin birden fazla katmandan gelebilmesidir: identity-based policy (kullanıcıya/role bağlı), resource-based policy (S3 bucket policy gibi kaynağa bağlı), permission boundary, SCP (Service Control Policy, organizasyon düzeyinde) ve session policy. Nihai izin, bu katmanların **kesişimidir**. Yani bir SCP bir eylemi reddediyorsa, kullanıcının identity policy'si onu açıkça izin verse bile eylem gerçekleşmez. Bu, büyük organizasyonlarda "koruyucu tavan" kurmanın temel mekanizmasıdır.

### En Tehlikeli Anti-Pattern: Wildcard İzinler

IAM'de en sık görülen ve en tehlikeli hata, tembellikten doğan wildcard kullanımıdır. Bir policy'de şuna benzer bir ifade görmek alarm zilidir:

```json
{
  "Effect": "Allow",
  "Action": "*",
  "Resource": "*"
}
```

Bu, o kimliğe hesap üzerinde neredeyse sınırsız yetki verir. Daha sinsi olanı `"Action": "s3:*"` gibi servis bazlı wildcard'lardır; masum görünürler ama bir S3 wildcard'ı, veri okuma yetkisinin yanında bucket policy'yi değiştirme (`s3:PutBucketPolicy`) yetkisini de içerir ki bu tek başına bir yetki yükseltme vektörüdür.

**Kök neden neden budur?** Çünkü geliştirici bir şeyi çalıştırmaya odaklanır; "hangi tam izinler gerekli?" diye düşünmek zaman alır, wildcard vermek anında çalışır. Least privilege (en az yetki) prensibi bir disiplin gerektirir ve bu disiplin, teslim baskısı altında ilk feda edilen şeydir.

### En İyi Pratikler (IAM)

- **En az yetki prensibi (least privilege)**: Her kimliğe yalnızca işini yapması için gereken minimum izni verin. İzinleri geniş verip sonra daraltmak yerine, dar verip ihtiyaç oldukça genişletin.
- **Uzun ömürlü access key'lerden kaçının**: Insan kullanıcılar için mümkünse IAM Identity Center / federasyon ile geçici credential kullanın. EC2 ve Lambda gibi iş yükleri için statik key gömmek yerine **IAM role** kullanın; role'ler geçici, otomatik rotasyona uğrayan credential sağlar.
- **MFA zorunlu kılın**: Özellikle ayrıcalıklı işlemler için `Condition` bloğunda `aws:MultiFactorAuthPresent` şartını kullanın.
- **Root hesabı kilitleyin**: Root credential'ı günlük kullanmayın, MFA ile koruyun, access key'i olmasın.
- **Analiz araçlarını kullanın**: IAM Access Analyzer, dışarıya açık veya beklenmedik erişim veren politikaları tespit eder. CloudTrail üzerinden gerçekte hangi izinlerin kullanıldığını görüp kullanılmayanları budayın.

## S3 Açık Bucket: En Klasik Veri Sızıntısı

### Tanım

Amazon S3, nesne depolama servisidir. Bir "bucket" içine dosyalar (object) konur. S3'ün ünlü olmasının sebebi, tarihsel olarak en çok veri sızıntısına yol açan servis olmasıdır: kredi kartı bilgileri, sağlık kayıtları, yedekler, kaynak kodları... hepsi yanlışlıkla dünyaya açılmış bucket'lardan sızmıştır.

### Kök Neden: Neden Bucket'lar Açılıyor

Bir S3 nesnesine erişimi birden fazla mekanizma kontrol eder ve bunların etkileşimi kafa karıştırıcıdır:

- **Block Public Access (BPA)** ayarları: Hem hesap hem bucket düzeyinde bulunan, herkese açık erişimi topluca engelleyen dört ayrı ayar.
- **Bucket policy**: Kaynağa bağlı JSON politikası.
- **ACL (Access Control List)**: Eski, nesne bazlı erişim mekanizması.
- **IAM policy**: Kimliğe bağlı izinler.

Bir bucket'ın "açık" hâle gelmesinin klasik yolu, bir bucket policy'de `"Principal": "*"` ile `s3:GetObject` verilmesi, yani "herkes okuyabilir" denmesidir:

```json
{
  "Effect": "Allow",
  "Principal": "*",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::sirket-yedekleri/*"
}
```

Geliştirici genellikle "statik bir web sitesini herkes görsün" gibi meşru bir amaçla bunu yapar; ama aynı bucket'ta hassas veriler de varsa felaket kaçınılmazdır. Diğer klasik hata, geçmişte `AuthenticatedUsers` ACL grubunun ne anlama geldiğinin yanlış anlaşılmasıydı: bu grup "benim hesabımdaki kullanıcılar" değil, **herhangi bir AWS hesabına sahip herkes** demekti. Yani bir AWS hesabı olan her saldırgan erişebilirdi.

### İstismar Mantığı

Saldırgan tarafında S3 keşfi şöyle işler: Bucket isimleri global olarak benzersizdir ve tahmin edilebilir kalıplar taşır (`sirketadi-backup`, `sirketadi-logs`, `sirketadi-prod`). Saldırganlar kelime listeleriyle bucket isimlerini brute-force ederek varlığını ve okunabilirliğini test eder. Açık bir bucket'ta listeleme (`ListBucket`) açıksa, saldırgan tüm nesne isimlerini çekip ardından tek tek indirir. Daha kötüsü, yazma izni (`PutObject`) açık bir bucket, statik sitelere zararlı içerik enjekte etmek veya veri değiştirmek için kullanılabilir.

### Savunma (S3)

- **Block Public Access'i hesap düzeyinde açın**: Bu tek ayar, altındaki tüm bucket'lar için "herkese açık" yapılandırmaları geçersiz kılan bir güvenlik ağıdır. Gerçekten public olması gereken bir CDN kaynağınız yoksa, bunu istisnasız açık tutun.
- **ACL'leri devre dışı bırakın**: Modern S3'te "bucket owner enforced" ayarıyla ACL'ler kapatılıp tüm erişim yalnızca policy'lerle yönetilebilir; bu, karmaşıklığı azaltarak hata yüzeyini daraltır.
- **Varsayılan şifreleme**: Tüm bucket'larda at-rest şifrelemeyi (SSE-S3 veya KMS anahtarlı SSE-KMS) zorunlu kılın. KMS kullanmak, veriye erişimi ayrıca anahtar iznine bağladığı için ek bir savunma katmanı ekler.
- **Public erişim yerine imzalı erişim**: Bir dosyayı geçici olarak paylaşmak istiyorsanız, bucket'ı açmak yerine süresi dolan **presigned URL** kullanın.
- **İzleme**: S3'e yönelik erişimleri CloudTrail data event'leri ve GuardDuty ile izleyin; olağandışı toplu indirme veya bilinmeyen kaynaktan erişim alarm üretmelidir.

## Metadata SSRF: EC2'nun Aşil Topuğu

### Tanım ve Çalışma Mantığı

Her EC2 instance'ı, içeriden erişilebilen özel bir adreste (link-local adres `169.254.169.254`) bir **Instance Metadata Service (IMDS)** barındırır. Bu servis, instance hakkında bilgi (instance ID, region, ağ bilgisi) ve kritik olarak, instance'a atanmış IAM role'ün **geçici güvenlik credential'larını** (access key, secret key, session token) sunar.

Bu tasarım aslında güvenlik için icat edilmişti: EC2 üzerindeki uygulama, statik AWS key gömmek zorunda kalmasın diye, credential'ı IMDS'den dinamik olarak alsın. Uygulama credential'ı diskte tutmaz, IMDS otomatik rotasyon yapar. Güzel bir fikir; ama bir yan etkisi var.

### Kök Neden: SSRF ile IMDS Neden Ölümcül Bir İkili

**SSRF (Server-Side Request Forgery)**, bir saldırganın uygulamayı kandırıp onun adına istemediği bir hedefe HTTP isteği yaptırdığı bir zafiyet sınıfıdır. Klasik örnek: uygulamanın "şu URL'deki resmi çek" özelliği. Saldırgan URL yerine `http://169.254.169.254/...` verir. Uygulama, kendi ağından bu isteği yapar ve IMDS'in döndürdüğü credential'ları saldırgana geri yansıtır.

İşte kritik nokta: IMDS'in eski (IMDSv1) sürümü **kimlik doğrulaması yapmaz**. Basit bir GET isteği credential'ları döndürür. Yani SSRF ile ulaşabilen herkes, o instance'ın IAM role'ünün tüm yetkilerini eline geçirir. Bu, tek bir web uygulaması zafiyetinin, doğrudan bulut credential hırsızlığına dönüştüğü noktadır. Sızdırılan credential'lar geçicidir ama saldırganın ortamda ilerlemesi için fazlasıyla yeterli süre yaşarlar.

### İstismar Zinciri (Somut Örnek)

Tipik bir saldırı zinciri şöyle akar: (1) Web uygulamasında bir SSRF bulunur. (2) Saldırgan bu SSRF ile IMDS'ten instance'a bağlı role adını sorgular. (3) Ardından o role'ün credential'larını çeker. (4) Bu credential'ları kendi makinesinde kullanarak AWS API'lerine erişir. (5) İlk keşif olarak kim olduğunu ve ne yetkisi olduğunu anlamaya çalışır (`sts:GetCallerIdentity` çağrısı gibi). (6) Role'ün izinlerine göre S3'ten veri çeker, başka kaynaklara erişir veya yetki yükseltmeye geçer.

### Savunma (Metadata SSRF)

- **IMDSv2'yi zorunlu kılın**: IMDSv2, istekten önce bir token alınmasını gerektiren bir "session-oriented" akış getirir. Token almak için özel bir başlık ve PUT isteği gerekir; ayrıca IMDSv2 yanıtları düşük bir TTL kısıtına tabidir. Bunun SSRF'e karşı savunması şudur: Çoğu SSRF zafiyeti yalnızca basit GET isteği yaptırabilir, gerekli PUT + özel başlık kombinasyonunu üretemez. IMDSv1'i tamamen kapatıp yalnızca IMDSv2'ye izin verirseniz (instance metadata options'ta "required"), pek çok SSRF vektörünü etkisiz hâle getirmiş olursunuz.
- **Hop limit'i düşürün**: IMDSv2'nin yanıt paketlerine uyguladığı hop sınırını 1 tutmak, metadata yanıtının container ağ katmanlarından dışarı sızmasını zorlaştırır; bu özellikle konteynerli ortamlar için önemlidir.
- **Uygulama katmanında SSRF savunması**: Kök sorun SSRF olduğu için orada da savunun. Kullanıcının verdiği URL'lerde link-local ve özel IP aralıklarını (`169.254.0.0/16`, `10.0.0.0/8`, `127.0.0.0/8` vb.) engelleyin. Sadece izinli hedeflerin allowlist'ini kullanın, deny yerine allow mantığı tercih edin.
- **Role izinlerini daraltın**: IMDS sızsa bile hasarın sınırlı kalması için, instance role'üne yalnızca gereken minimum izinleri verin. Least privilege burada da hasar kontrolü sağlar.
- **Ağ segmentasyonu**: IMDS erişimini gerçekten ihtiyaç duyan süreçlerle sınırlamak için host düzeyinde firewall kuralları uygulanabilir.

## Privilege Escalation: İçeride Yayılmanın Sanatı

### Tanım

**Privilege escalation (yetki yükseltme)**, saldırganın eline geçirdiği düşük yetkili bir kimlikten yola çıkarak, IAM izinlerini kötüye kullanarak daha yüksek yetkili bir kimliğe ulaşmasıdır. Buluttaki privilege escalation, işletim sistemindeki gibi bir kernel exploit değildir; tamamen **yanlış yapılandırılmış IAM izinlerinin mantıksal zinciridir**.

### Kök Neden: Belirli İzinler Neden "Yetki Yükseltme Primitifi"dir

Bazı IAM izinleri, tek başına masum görünse de, bir kimliğin kendi yetkisini genişletmesine imkân tanır. Bunlar iyi bilinen "escalation primitive"leridir. Mantığı anlamak için birkaç kategoriyi inceleyelim:

**1. iam:PassRole + servis oluşturma yetkisi.** `iam:PassRole`, bir kimliğin bir role'ü bir AWS servisine "geçirmesine" izin verir. Tek başına zararsızdır. Ama `iam:PassRole` ile birlikte bir EC2 instance başlatma veya Lambda fonksiyonu oluşturma izni varsa, saldırgan yüksek yetkili bir role'ü kendi başlattığı bir instance'a/fonksiyona atar ve o kaynağın içinden o role'ün credential'larını kullanır. Yani "başkasının yetkisini bir kaynağa giydir, sonra o kaynağın içine gir" mantığıdır. `PassRole`, buluttaki en kritik ve en çok gözden kaçan izindir.

**2. IAM policy manipülasyonu.** `iam:PutUserPolicy`, `iam:AttachUserPolicy`, `iam:CreatePolicyVersion` gibi izinler, saldırganın kendisine ya da kontrol ettiği bir kimliğe yeni izinler eklemesine olanak tanır. Örneğin `iam:AttachUserPolicy` yetkisi olan bir kullanıcı, kendine `AdministratorAccess` policy'sini bağlayarak anında admin olur. Bu, "izin verme yetkisinin kendisinin bir yetki yükseltme olduğu" klasik örnektir.

**3. Var olan credential'ları ele geçirme.** `iam:CreateAccessKey` başka bir kullanıcı için access key üretebiliyorsa, saldırgan admin bir kullanıcı için yeni bir key oluşturup onun kimliğine bürünür. Benzer şekilde `iam:UpdateLoginProfile` ile başka bir kullanıcının konsol şifresini değiştirmek de bir ele geçirme yoludur.

**4. sts:AssumeRole ve zayıf trust policy.** Bir role'ün "trust policy"si kimin onu üstlenebileceğini belirler. Trust policy aşırı geniş yazılmışsa (örneğin tüm hesaba veya beklenmedik bir principal'a güveniyorsa), düşük yetkili bir kimlik yüksek yetkili role'ü üstlenebilir.

### İstismar Mantığı

Saldırgan, eline bir credential geçirdikten sonra ilk iş olarak **enumeration (izin keşfi)** yapar: hangi izinlere sahibim? Bunun için IAM'i sorgular, kendi kullanıcısına/role'üne bağlı politikaları listeler. Ardından bu izin setini bilinen escalation primitive'leriyle eşleştirir. Bu süreç otomatize edilmiştir; saldırganlar bir kimliğin izinlerini alıp içinde yükseltme yolu olup olmadığını tarayan araçlar kullanır (bu tür araçların en bilineni Rhino Security Labs'ın çalışmalarından türeyen açık kaynak projelerdir). Bir yol bulununca zincir işletilir ve saldırgan admin'e ulaşır.

Kritik nokta şudur: Bu saldırılar **hiçbir zafiyet sömürmez**. Her adım, AWS'nin tasarlandığı gibi çalışan, tamamen "meşru" API çağrılarıdır. Bu yüzden geleneksel zafiyet taramaları bunları yakalamaz; ancak IAM izin ilişkilerini analiz eden araçlar yakalar.

### Savunma (Privilege Escalation)

- **iam:PassRole'ü kısıtlayın**: `PassRole` iznini asla `Resource: "*"` ile vermeyin. Hangi role'lerin geçirilebileceğini ARN ile sınırlayın ve `Condition` içinde `iam:PassedToService` şartıyla yalnızca ilgili servise geçirilmesine izin verin. Bu, "herhangi bir role'ü herhangi bir yere giydirme" kabiliyetini keser.
- **IAM yazma izinlerini ayrıcalıklı sayın**: `iam:*Policy`, `iam:CreateAccessKey`, `iam:UpdateLoginProfile`, `iam:CreateUser` gibi kimlik yönetimi izinlerini yalnızca gerçekten kimlik yöneten dar bir yönetici grubuna verin. Bir uygulama role'ünün bu izinlere sahip olmasının neredeyse hiçbir meşru gerekçesi yoktur.
- **Permission boundary ve SCP kullanın**: Bir kimlik yetki yükseltse bile, üzerine yerleştirilmiş bir permission boundary veya organizasyon düzeyi SCP, ulaşabileceği tavanı sınırlar. Örneğin bir SCP ile "hiçbir kimlik IAM policy'lerini değiştiremez, ancak merkezi yönetim role'ü hariç" kuralı koyulabilir. Bu, en az yetkinin üzerine konan ikinci bir güvenlik ağıdır.
- **Trust policy'leri sıkı yazın**: Role trust policy'lerinde principal'ı mümkün olduğunca dar tutun; `aws:PrincipalOrgID`, `sts:ExternalId` gibi koşullarla üçüncü taraf role üstlenmelerini sıkılaştırın. Özellikle üçüncü taraf entegrasyonlarında "confused deputy" problemine karşı `ExternalId` kullanımı standart olmalıdır.
- **Sürekli analiz**: IAM ilişkilerini graf olarak modelleyip yükseltme yollarını arayan araçları (örneğin açık kaynak IAM analiz araçları) düzenli çalıştırın. Access Analyzer'ın "unused access" bulgularıyla ölü izinleri temizleyin.

## Katmanların Birleşimi: Gerçek Bir Saldırı Nasıl Zincirlenir

Bu dört konuyu ayrı ayrı anlattık ama gerçek olaylarda bunlar bir zincir oluşturur ve zincirin gücü buradadır. Tipik bir uçtan uca senaryo şöyledir: İnternete açık bir web uygulamasında bir **SSRF** bulunur. SSRF ile **IMDS**'ten instance'ın IAM role credential'ları çekilir. Bu role'ün, tasarımdaki tembellik nedeniyle `s3:*` ve `iam:PassRole` gibi geniş izinleri vardır. Saldırgan önce erişebildiği **S3 bucket'larından** veri sızdırır. Ardından `iam:PassRole` + Lambda oluşturma iznini kullanarak bir **privilege escalation** gerçekleştirir ve admin'e ulaşır. Artık tüm hesap onundur.

Bu zincirin öğrettiği en önemli ders, **savunmanın da katmanlı olması gerektiğidir (defense in depth)**. Zincirin her halkasında bir engel koyabilseydiniz saldırı kırılırdı: uygulamada SSRF savunması, IMDSv2 zorunluluğu, role'de least privilege, S3'te Block Public Access, IAM'de PassRole kısıtı ve SCP tavanı. Herhangi biri tek başına saldırıyı durdurabilirdi; hepsi birlikte olduğunda saldırganın işi neredeyse imkânsızlaşır.

## Yaygın Hatalar (Özet)

- **Wildcard izinler**: `Action: "*"` veya servis bazlı `s3:*`, `iam:*` gibi geniş izinler vermek. En sık ve en tehlikeli hata.
- **Statik access key gömmek**: Kod içine, environment değişkenine veya konfigürasyon dosyasına uzun ömürlü key koymak. Bunlar sızar, git geçmişinde kalır, rotasyona uğramaz. Iş yükleri için role kullanılmalı.
- **IMDSv1'i açık bırakmak**: Varsayılanı kabul edip IMDSv2'yi zorunlu kılmamak, her SSRF'i credential hırsızlığına açık bırakır.
- **Block Public Access'i kapatmak**: "Bir dosyayı paylaşacağım" diye BPA'yı kapatıp unutmak. Presigned URL kullanılmalı.
- **iam:PassRole'ü sınırsız vermek**: `Resource: "*"` ile PassRole, sessiz bir admin kapısıdır.
- **Loglamayı ihmal etmek**: CloudTrail'i tüm region'larda açmamak, GuardDuty kullanmamak. Görmediğiniz saldırıya müdahale edemezsiniz.
- **Root hesabı günlük kullanmak**: Root ile iş yapmak ve MFA'sız bırakmak.

## En İyi Pratikler (Bütünsel Bakış)

Sağlam bir AWS güvenlik duruşu birkaç ilkeye dayanır. Birincisi **least privilege**: her kimlik minimum yetkiyle çalışmalı, izinler geniş verilip daraltılmak yerine dar verilip gerektikçe genişletilmeli. İkincisi **kimlik merkezli düşünmek**: statik credential yerine geçici, role tabanlı credential; her yerde MFA; federasyon. Üçüncüsü **defense in depth**: BPA, IMDSv2, SCP, permission boundary gibi birbirinden bağımsız güvenlik ağlarını üst üste koymak, böylece tek bir hatanın felakete dönüşmemesi. Dördüncüsü **görünürlük**: CloudTrail, GuardDuty, Config ve Access Analyzer ile hem gerçek zamanlı tehdidi hem de yapılandırma sapmalarını sürekli izlemek. Beşincisi **otomasyon ve tekrarlanabilirlik**: altyapıyı Infrastructure as Code ile tanımlayıp güvenlik yapılandırmalarını kod incelemesinden geçirmek, elle yapılan hataları en aza indirir.

Son ve belki en önemli ilke şudur: Bulut güvenliği bir varış noktası değil, sürekli bir süreçtir. IAM izinleri zamanla birikir ("permission creep"), yeni servisler yeni saldırı yüzeyleri açar, ekipler değişir. Bu yüzden düzenli erişim gözden geçirmeleri, ölü izinlerin budanması ve saldırgan gözüyle yapılan periyodik değerlendirmeler (kırmızı takım çalışmaları) bir lüks değil, zorunluluktur. AWS size dünyanın en güçlü altyapı güvenliğini sunar; ama o altyapının üzerine ne inşa ettiğiniz tamamen sizin sorumluluğunuzdadır.
