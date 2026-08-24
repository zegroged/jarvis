# Serverless / FaaS Güvenliği: Lambda ve Cloud Functions'a Özgü Saldırı Yüzeyi

## Giriş: Neden Bu Konu Ayrı Bir Kategori Hak Ediyor

Güvenlik eğitiminin büyük çoğunluğu iki modele oturur: klasik sunucu/VM (uzun ömürlü işletim sistemi, kalıcı disk, ağ arayüzü) ve konteyner (izole ama yine de "çalışan bir süreç" fikrine dayalı). Serverless / Function-as-a-Service (FaaS) — AWS Lambda, Google Cloud Functions, Azure Functions, Cloudflare Workers gibi platformlar — bu iki modelin varsayımlarını sistematik olarak kırar. Fonksiyonun kendisi kısa ömürlüdür, durumsuzdur (stateless olması beklenir), tetiklenmeden var olmaz ve genellikle saniyeler içinde ölür. Bu durum, "sunucuyu güçlendir (harden), ağı segmentle, log'u sunucudan topla" gibi klasik savunma reflekslerinin çoğunu ya işe yaramaz ya da yetersiz kılar.

Bu makalenin amacı, serverless mimarinin getirdiği KENDİNE ÖZGÜ (generic konteyner/VM güvenliğinden farklı) saldırı yüzeylerini kavramsal olarak anlamak ve bunlara karşı tespit/savunma zihniyeti kurmaktır. Dört ana eksen üzerinden ilerleyeceğiz: (1) aşırı geniş IAM execution role'leri, (2) event-injection (tetikleyici kaynaklar üzerinden), (3) soğuk başlatma (cold start) sırasında sır sızıntısı, (4) fonksiyonlar-arası yatay hareket.

---

## 1. Aşırı Geniş IAM Execution Role'leri

### Tanım ve Kök Neden

Her serverless fonksiyon, çalışırken bir "execution role" (AWS'de IAM Role, GCP'de service account) ile ilişkilendirilir. Fonksiyon kodu çalıştığında, bu role'ün izinlerini miras alan geçici kimlik bilgileri (credentials) otomatik olarak ortama enjekte edilir — genellikle bir metadata servisi veya ortam değişkeni üzerinden. Fonksiyon kodu bu credential'ları kullanarak diğer bulut kaynaklarına (S3, DynamoDB, Secrets Manager, diğer Lambda'lar, RDS vb.) erişir.

Kök neden şudur: Geliştiriciler ve DevOps ekipleri, "bu fonksiyon çalışsın da" refleksiyle IAM policy yazarken en direnç en az olan yolu seçerler. `s3:GetObject` yerine `s3:*`, tek bir bucket ARN'i yerine `Resource: "*"` yazmak, hata ayıklamayı kolaylaştırır ama fonksiyonun GERÇEKTE ihtiyaç duyduğu izin kümesiyle SAHİP OLDUĞU izin kümesi arasında devasa bir fark (permission gap) yaratır. Bu fark, "least privilege" ilkesinin ihlalidir ve serverless'te özellikle tehlikelidir çünkü:

- Fonksiyon sayısı VM sayısından çok daha fazladır (bir uygulama onlarca-yüzlerce küçük fonksiyona bölünebilir), dolayısıyla IAM role sayısı da patlar — merkezi denetim zorlaşır.
- Her fonksiyon genellikle "tek görev" yapar ama role'ü tüm hesabın izinlerine yakın bir şey içerebilir; bu, klasik bir sunucudaki "root kullanıcı her şeyi yapabilir" senaryosunun mikro-servis versiyonudur.

### Çalışma Mantığı ve Saldırı Senaryosu

Saldırganın hedefi genelde fonksiyon kodunun kendisini ele geçirmek değil, KOD İÇİNDEKİ BİR ZAAFİYETİ (ör. bir dependency'deki remote code execution, bir template injection, bir deserialization açığı) kullanarak fonksiyonun ÇALIŞMA ORTAMINDA komut çalıştırma (arbitrary code execution) elde etmektir. Bu noktada saldırgan artık "fonksiyonun kodu" değil, "fonksiyonun execution role'ü" olarak hareket eder. Eğer role aşırı genişse, saldırgan:

- Metadata servisinden (AWS'de genelde ortam değişkenlerine yazılmış geçici anahtarlar, IMDS'e benzer ama Lambda'da farklı mekanizma) credential'ları çeker.
- Bu credential'ları kullanarak S3'teki tüm bucket'ları listeler, DynamoDB tablolarını dump eder, Secrets Manager'daki diğer servislerin sırlarını okur, hatta yeni IAM kullanıcıları/role'leri oluşturarak kalıcılık (persistence) sağlayabilir — eğer role'de `iam:*` gibi izinler varsa (privilege escalation zinciri).

Bunun klasik sunucu modelinden farkı: VM'de saldırgan genelde "önce local privilege escalation, sonra network pivoting" yapmak zorundadır. Serverless'te ise IAM role zaten "ağ sınırlarını aşan" bir yetki katmanıdır — role'ün kendisi saldırganın pivot aracıdır, ayrıca ağ keşfi yapmasına bile gerek kalmayabilir çünkü bulut API'leri her yerden erişilebilirdir.

### Tespit

- **IAM Access Analyzer / policy simülasyonu**: Fonksiyona atanmış policy ile CloudTrail/audit log'larda GERÇEKTE kullanılan API çağrıları arasındaki farkı (unused permissions) düzenli olarak analiz edin. Bu fark ne kadar büyükse, saldırı yüzeyi o kadar geniştir.
- **Anomali tabanlı izleme**: Bir fonksiyonun normalde sadece `dynamodb:GetItem` çağırdığı biliniyorsa, aniden `iam:CreateUser` veya `s3:ListBuckets` (hesap genelinde) çağırması güçlü bir IOC'dir (indicator of compromise). CloudTrail + bir SIEM/anomali motoru ile bu davranış sapmaları yakalanabilir.
- **Statik analiz**: IaC (Infrastructure as Code — Terraform, CloudFormation, SAM) dosyalarında wildcard (`*`) içeren `Resource` veya `Action` alanlarını CI/CD pipeline'ında otomatik tarayan araçlar (checkov, cfn-nag, tfsec benzeri) ile "deploy öncesi" yakalama.

### Savunma

- **Least privilege by function**: Her fonksiyona SADECE ihtiyaç duyduğu kaynak ARN'i ve eylem listesini tanımlayın. "Önce geniş yaz, sonra daralt" yerine "önce dar başla, hata verirse genişlet" yaklaşımı benimseyin.
- **Role ayrıştırma**: Fonksiyonları paylaşılan tek bir role yerine, her biri kendi dar role'üne sahip olacak şekilde tasarlayın (role explosion yönetilebilir hale getirilmeli — tag'leme ve otomasyonla).
- **Permission boundary / SCP (Service Control Policy)**: Hesap/organizasyon seviyesinde, tek bir fonksiyon role'ünün asla aşamayacağı üst sınırlar koyun (ör. hiçbir Lambda role'ü `iam:*` çağıramaz).
- **Geçici credential ömrünü kısaltma** ve kullanılmayan izinleri düzenli temizleme (permission hygiene) süreci kurumsallaştırın.

### Yaygın Hatalar

- "Zaten VPC içinde, network izole" diyerek IAM'i ihmal etmek — IAM, ağ izolasyonundan BAĞIMSIZ bir yetki katmanıdır, VPC içinde olmak IAM'i güvenli yapmaz.
- Managed policy'leri (ör. `AWSLambdaFullAccess` benzeri geniş kapsamlı hazır policy'ler) hızlı prototipten prodüksiyona taşımak ve orada unutmak.

---

## 2. Event-Injection: Tetikleyici Kaynaklar Üzerinden Saldırı

### Tanım ve Kök Neden

Serverless fonksiyonlar HTTP isteğiyle değil, genellikle bir "event" ile tetiklenir: bir S3 bucket'a dosya yüklenmesi, bir SQS/SNS mesajı, bir API Gateway isteği, bir zamanlayıcı (cron), bir veritabanı stream'i (DynamoDB Streams) vb. Bu event, fonksiyona bir JSON payload olarak gelir ve fonksiyon kodu bu payload'ı ayrıştırıp (parse) işler.

Kök neden: Klasik web uygulamalarında geliştiriciler "kullanıcı girdisine güvenme" refleksini büyük ölçüde HTTP request body/header/query string için geliştirmiştir. Ama serverless'te event kaynağı ÇOK ÇEŞİTLİDİR ve her kaynağın kendi payload şeması, kendi güven seviyesi vardır. Geliştirici genelde "bu event zaten benim S3 bucket'ımdan geliyor, güvenli" varsayımıyla event içeriğini yeterince doğrulamadan işler — halbuki event içeriğinin BİR KISMI (ör. dosya adı, S3 object key, SQS mesaj body'si, API Gateway header'ları) NİHAİ OLARAK dış kullanıcı tarafından kontrol edilebilir bir veridir.

### Çalışma Mantığı

Örnek zincir: Bir kullanıcı halka açık bir web formundan dosya yükler → bu dosya bir S3 bucket'a düşer → S3 event notification bir Lambda'yı tetikler → Lambda, event payload'ındaki `object key` (dosya adı) alanını hiçbir sanitizasyon yapmadan bir shell komutuna, bir SQL sorgusuna, bir dosya sistemi yoluna (path traversal — `../../` içeren dosya adı) veya bir başka servise ileten bir mesaj gövdesine gömer.

Bunun "injection" olarak adlandırılmasının nedeni klasiktir (SQL injection, command injection ile aynı KÖK mantık): güvenilmeyen veri ile kontrol/komut arasındaki sınır bulanıklaşır. Ama serverless'e ÖZGÜ olan kısım, bu güvenilmeyen verinin GİRİŞ NOKTASININ çok çeşitlenmiş olmasıdır — artık sadece "HTTP endpoint'i doğrula" yetmez; S3 key'leri, SQS mesaj attribute'ları, SNS mesaj body'si, DynamoDB stream kayıtları, hatta bulut sağlayıcının kendi event formatındaki metadata alanları (ör. `Records[].eventSource`, `requestContext` gibi alanlar) da potansiyel giriş noktalarıdır. Ayrıca fonksiyonlar genelde BİRDEN FAZLA event kaynağına aynı anda bağlı olabilir ve kod, "bu event hangi kaynaktan geldi" ayrımını her zaman güvenli yapmayabilir (event source spoofing / confused deputy riski: fonksiyon, event'in gerçekten beklenen kaynaktan geldiğini varsayar ama bu event şeklen taklit edilebilir veya event'in bazı alanları çağıran taraf tarafından serbestçe doldurulabilir).

Özel bir alt tür: **API Gateway → Lambda proxy entegrasyonu**nda tüm HTTP isteği (header, query string, body) tek bir JSON event objesine paketlenir. Geliştirici, "input validation API Gateway seviyesinde yapılıyor" varsayarsa ama gerçekte sadece şema doğrulama yüzeysel yapılmışsa, Lambda kodu içinde header enjeksiyonu, deserialization saldırıları (özellikle body'nin otomatik JSON/base64 çözümlenmesi güvenilmeyen içerikle birleşince) mümkün olur.

### Tespit

- **Event kaynağı bazlı loglama**: Her fonksiyon çağrısında `event.Records[].eventSource` (veya eşdeğeri) ile fonksiyonun DEPLOYMENT ZAMANINDA tanımlı beklenen tetikleyici kaynaklarını karşılaştırın; beklenmeyen bir event source'tan gelen çağrı anomali sayılmalı.
- **Payload şema doğrulama izleme**: Fonksiyon girişinde şema doğrulaması (JSON Schema, ör. bir input validation middleware) başarısız olan isteklerin oranını metrikleştirin; ani artış, aktif bir fuzzing/injection denemesini işaret edebilir.
- **Anormal karakter/uzunluk desenleri**: S3 object key'lerinde `../`, null byte, aşırı uzun stringler; SQS mesajlarında beklenmeyen JSON derinliği veya boyutu — bunlar WAF benzeri bir ön filtre veya fonksiyon içi loglama ile yakalanabilir.

### Savunma

- **Her event kaynağını "güvenilmeyen kullanıcı girdisi" olarak ele alın** — S3 key'i, SQS body'si, DynamoDB stream kaydı fark etmeksizin, HTTP body'sini doğruladığınız titizlikle doğrulayın (allowlist tabanlı, tip kontrolü, uzunluk sınırı, path traversal koruması).
- **Event source doğrulama**: Mümkünse fonksiyonun sadece BEKLENEN kaynak ARN'inden gelen event'leri kabul etmesini sağlayın (ör. resource-based policy ile "sadece bu S3 bucket bu Lambda'yı tetikleyebilir" kısıtlaması; SNS/SQS için mesaj imzası doğrulama).
- **Deserialization'ı en aza indirin**: Otomatik/örtük deserialization (ör. güvenilmeyen body'yi doğrudan nesneye çeviren kütüphaneler) yerine açık, minimal şema ile parse edin.
- **Prensip olarak fonksiyonu tek amaçlı tutun**: Bir fonksiyonun kabul ettiği event tiplerini ve kaynak sayısını minimumda tutmak, doğrulama yükünü ve hata yüzeyini azaltır.

### Yaygın Hatalar

- "Event, benim kendi bulut kaynağımdan (S3/SQS) geliyor, dolayısıyla temiz" varsayımı — event'in KAYNAĞI güvenilir olsa da event'in İÇERİĞİ nihayetinde dış kullanıcı etkisi taşıyabilir.
- Tek bir Lambda'yı birden fazla farklı tetikleyiciye (hem API Gateway hem S3 hem SQS) bağlayıp, her kaynağın kendine özgü payload şemasını ayrı ayrı doğrulamamak.

---

## 3. Soğuk Başlatma (Cold Start) Sırasında Sır Sızıntısı

### Tanım ve Kök Neden

Serverless platformlar maliyet ve ölçeklenebilirlik için fonksiyon ortamlarını (execution environment / container) isteğe bağlı oluşturur ve bir süre kullanılmazsa yok eder. Bir isteğe cevap vermek için sıfırdan yeni bir ortam ayağa kaldırılması "cold start" olarak adlandırılır; bu sırada çalışma zamanı (runtime) başlatılır, bağımlılıklar yüklenir, ve KRİTİK OLARAK, fonksiyonun ihtiyaç duyduğu sırlar (API anahtarları, veritabanı parolaları, imzalama anahtarları) bir şekilde ortama getirilir — ortam değişkenleri, bir Secrets Manager/Parameter Store çağrısı, veya bir init dosyası üzerinden.

Kök neden çok katmanlı:
1. **Ortam değişkenleri düz metin gibi davranır**: Birçok platformda ortam değişkenleri "şifreli" görünse de, ÇALIŞMA ZAMANINDA fonksiyon koduna düz metin olarak sunulur; bu değişkenler platform loglarına, hata ayıklama (debug) çıktısına, hatta yanlışlıkla loglama ifadelerine (`console.log(process.env)` gibi) karışabilir.
2. **Cold start sırasında init kodu, HANDLER KODUNDAN DAHA AZ İZLENİR**: Geliştiriciler genelde güvenlik/loglama refleksini "istek işleme" mantığına odaklarlar; ama sır yükleme genelde handler ÇAĞRILMADAN ÖNCE, modül seviyesinde (import/init aşaması) çalışır ve bu aşamadaki hatalar/loglar genelde daha az denetlenir.
3. **Ortam yeniden kullanımı (warm start)**: Bir cold start sonrası ortam bir süre "sıcak" kalır ve sonraki isteklerde YENİDEN KULLANILIR. Bu, ortamda kalan bellek durumunun (ör. önceki isteğin işlediği hassas veri, bir önceki kullanıcının oturum bilgisi) SONRAKİ, FARKLI BİR KULLANICIYA AİT isteğe SIZMASI riskini doğurur — çünkü fonksiyon "stateless" tasarlanmış OLMASI GEREKİRKEN, altındaki çalışma zamanı aslında durumu (global değişkenler, bellek, geçici dosya sistemi `/tmp`) isteğe bağlı bir sınır olmaksızın paylaşır.

### Çalışma Mantığı ve Saldırı Senaryosu

İki ayrı ama ilişkili senaryo var:

**(a) Sır sızıntısı loglama/hata yoluyla**: Fonksiyon init sırasında bir bağımlılık hatası verirse (ör. yanlış yapılandırılmış bir SDK), stack trace veya hata mesajı ortam değişkenlerini/sırları İÇEREBİLİR ve bu, platformun merkezi log servisine (CloudWatch Logs benzeri) düz metin olarak yazılır. Log servisine erişimi olan (veya log export/aggregation zincirinde sızıntı olan) herhangi biri bu sırları okuyabilir. Bu, "sırrı çalmak için fonksiyonu ele geçirmeye bile gerek yok, sadece log altyapısına erişimin olması yeterli" demektir — klasik VM'de bu kadar merkezi ve otomatik log toplama genelde yoktur.

**(b) Ortam paylaşımı yoluyla sızıntı (cross-invocation leakage)**: Bir saldırgan, aynı fonksiyonun SICAK (warm) bir örneğine denk gelirse ve fonksiyon kodu önceki çağrının bıraktığı global bir değişkende (ör. bir önbellek, bir bağlantı havuzu, `/tmp` dizinine yazılmış geçici dosya) hassas veri bırakmışsa, bu veriye erişebilir. Bu özellikle "performans optimizasyonu" adına global scope'ta önbellekleme yapan (ör. veritabanı bağlantısını veya bir kullanıcı token'ını modül seviyesinde saklayan) kod desenlerinde risklidir.

Bunun neden serverless'e ÖZGÜ olduğunu vurgulamak gerekir: Klasik bir sunucuda süreç ömrü uzundur ve "bu süreç kimin isteğini işliyor" ayrımı genelde açık bir oturum/thread modeliyle yönetilir. Serverless'te ise "hangi isteğin hangi ortamda, hangi önceki durumla çalıştığı" geliştiriciye ÖRTÜKTÜR — platform bunu soyutlar ve geliştirici genelde ortamın ne zaman yeniden kullanıldığını, ne zaman sıfırdan oluşturulduğunu bilmez/kontrol edemez.

### Tespit

- **Log içeriği taraması**: Merkezi log akışını (CloudWatch/Stackdriver vb.) düzenli olarak bilinen sır desenleri (API key formatları, `AKIA...` gibi önekler, yüksek entropili stringler) için tarayan otomatik bir DLP (data loss prevention) katmanı kurun.
- **Init/handler ayrımını izleyin**: Hata oranı ve hata TÜRÜ metriklerini "cold start init hataları" ile "handler çalışma zamanı hataları" olarak AYRI izleyin; init hatalarındaki artış, sır yükleme mekanizmasında bir sorunu işaret edebilir.
- **Bellek/dosya sistemi kalıntısı testleri**: Güvenlik testlerinde, aynı warm ortamı ardışık farklı "kullanıcı" bağlamlarıyla çağırıp önceki çağrının verisinin sızıp sızmadığını (global değişken, `/tmp` dosyası) kontrol eden testler ekleyin.

### Savunma

- **Sırları ortam değişkeninde tutmayın; her çağrıda bir sır yönetim servisinden (Secrets Manager/Parameter Store/KMS ile şifreli) OKUYUN** ve mümkünse kısa ömürlü, dar kapsamlı token'lar kullanın.
- **Global scope'ta hassas veri biriktirmeyin**: Kullanıcıya özgü veriyi (token, oturum, kişisel veri) her zaman handler fonksiyonu içinde, isteğe özgü kapsamda tutun; modül seviyesinde sadece "kullanıcıdan bağımsız" kaynakları (statik yapılandırma, bağlantı havuzu NESNESİ — içeriği değil) önbellekleyin.
- **`/tmp` dizinini her çağrı sonunda temizleyin veya hassas veri yazmaktan kaçının**; zorunluysa işlem sonunda açıkça silin.
- **Log'lama disiplini**: Hata yakalama (try/catch) bloklarında ham hata objesini/ortam değişkenlerini asla doğrudan loglamayın; sadece sanitize edilmiş, sır içermeyen mesajları loglayın.
- **En az ayrıcalıklı, kısa ömürlü kimlik bilgileri**: Mümkün olduğunda uzun ömürlü statik anahtarlar yerine platformun sağladığı otomatik rotasyonlu geçici credential mekanizmasını kullanın.

### Yaygın Hatalar

- "Ortam değişkenleri şifreli, güvenli" diyerek sırrı doğrudan env var'da tutmak ve loglama disiplinini ihmal etmek.
- Performans kaygısıyla veritabanı bağlantısını/token'ı global scope'ta "önbelleğe almak" ama bunun İÇİNE isteğe özgü hassas veriyi de karıştırmak.

---

## 4. Fonksiyonlar Arası Yatay Hareket (Lateral Movement)

### Tanım ve Kök Neden

Klasik yatay hareket modeli ağ tabanlıdır: saldırgan bir makineyi ele geçirir, ağdaki diğer makinelere (SMB, SSH, RDP) sıçrar. Serverless mimaride "ağ" kavramı büyük ölçüde ORTADAN KALKAR veya arka plana çekilir — fonksiyonlar birbirine doğrudan ağ bağlantısı kurarak değil, ÇOĞUNLUKLA PAYLAŞILAN BULUT KAYNAKLARI ve OLAY ZİNCİRLERİ (event chains) üzerinden etkileşir: bir fonksiyonun çıktısı bir SQS kuyruğuna yazılır, bu kuyruk başka bir fonksiyonu tetikler; bir fonksiyon bir S3 bucket'a yazar, bu başka bir fonksiyonu tetikler; fonksiyonlar ortak bir DynamoDB tablosunu, ortak bir Secrets Manager sırrını, ortak bir VPC'yi paylaşır.

Kök neden: Mikro-fonksiyon mimarisi, uygulamayı onlarca-yüzlerce küçük parçaya böler ve bu parçalar arasındaki GÜVEN SINIRLARI genelde AÇIKÇA TASARLANMAZ — "zaten hepsi bizim uygulamamızın parçası" varsayımıyla fonksiyonlar birbirinin ürettiği veriye, birbirinin yazdığı kaynaklara geniş erişim izniyle bağlanır. Bu, klasik mikroservis mimarisindeki "service mesh + mTLS + ağ segmentasyonu" disiplininin serverless dünyasında IAM POLICY'LERİ VE KAYNAK BAZLI İZİNLERE dönüşmesi demektir — ama bu dönüşüm genelde eksik yapılır çünkü "sunucu yok, ağ yok" hissi geliştiricide "izole, güvenli" yanılsaması yaratır.

### Çalışma Mantığı ve Saldırı Senaryosu

Saldırgan bir fonksiyonda (ör. dosya işleme fonksiyonu) bir zaafiyet (kod enjeksiyonu, kötü niyetli bağımlılık, aşırı geniş IAM role — yukarıdaki bölüm 1 ile birleşerek) üzerinden ilk ele geçirmeyi (initial foothold) sağladıktan sonra, bu fonksiyonun execution role'ünün erişebildiği PAYLAŞILAN KAYNAKLAR üzerinden ZİNCİRLEME İLERLER:

- Fonksiyon A'nın çıktığı bir SQS kuyruğuna kötü niyetli/manipüle edilmiş bir mesaj enjekte ederek, bu kuyruğu dinleyen Fonksiyon B'yi (farklı, belki daha yüksek yetkili bir role ile çalışan) tetikler — bu, event-injection (bölüm 2) ile lateral movement'ın kesiştiği noktadır.
- Fonksiyon A'nın erişebildiği paylaşılan bir S3 bucket'a, Fonksiyon C'nin okuyup İŞLEYECEĞİ (ve güvenmesi beklenen) bir dosya yerleştirerek Fonksiyon C'yi dolaylı olarak etkiler (confused deputy: C, A'dan gelen veriye kendi yetkisiyle güvenerek işlem yapar).
- Paylaşılan bir VPC içinde çalışan fonksiyonlar arasında, eğer güvenlik grupları (security groups) gevşek yapılandırılmışsa, DOĞRUDAN ağ erişimi de mümkün olabilir — bu durumda klasik ağ tabanlı lateral movement serverless bağlamında yeniden ortaya çıkar (VPC-bağlı Lambda'lar arası).
- Ortak bir Secrets Manager sırrına veya ortak bir yapılandırma deposuna erişimi olan fonksiyonlar arasında, bir fonksiyonun ele geçirilmesi diğer fonksiyonların KULLANDIĞI (ama kendi kodunda barındırmadığı) kimlik bilgilerinin de çalınmasına yol açabilir.

Bunun klasik modelden temel farkı: Saldırganın "ilerlemesi" ağ paketleriyle değil, BULUT API ÇAĞRILARI ve OLAY TETİKLEMELERİYLE olur; dolayısıyla ağ tabanlı IDS/IPS (intrusion detection/prevention) araçları bu hareketi genelde GÖREMEZ — çünkü trafik "normal" bulut API trafiğine benzer. Tespit için bulut kontrol düzlemi (control plane) log'larına (CloudTrail benzeri) bakmak gerekir, ağ log'larına değil.

### Tespit

- **Kaynak grafiği analizi (resource graph / attack path mapping)**: Hangi fonksiyonun hangi kaynaklara yazma/okuma izni olduğunu ve bu kaynakların hangi BAŞKA fonksiyonları tetiklediğini haritalayan bir graf çıkarın; bu graf üzerinde "düşük yetkili bir fonksiyondan yüksek yetkili bir fonksiyona ulaşan zincir var mı" sorusunu düzenli sorun (bu, bulut güvenlik duruş yönetimi — CSPM/CIEM araçlarının yaptığı temel analizdir).
- **Çapraz-fonksiyon çağrı anomalisi**: Normalde birbirini tetiklemeyen iki fonksiyon arasında ani bir event akışı (ör. beklenmedik bir SQS mesajı, beklenmedik bir S3 yazma) tespit edilirse alarm üretin.
- **CloudTrail/audit log korelasyonu**: Tek bir kimlik (bir fonksiyonun execution role'ü) kısa sürede ÇOK FARKLI kaynak türlerine (S3, SQS, DynamoDB, IAM) erişim denemesi yapıyorsa, bu tipik keşif/pivot davranışıdır.

### Savunma

- **Fonksiyonlar arası güven sınırlarını açıkça tasarlayın**: Her paylaşılan kaynağa (kuyruk, bucket, tablo) hangi fonksiyonların yazabileceğini/okuyabileceğini EN DAR ŞEKİLDE tanımlayın; "aynı uygulamanın parçası" argümanı bir güven gerekçesi DEĞİLDİR.
- **Mesaj/veri doğrulamasını her sınırda tekrarlayın**: Fonksiyon B, Fonksiyon A'dan gelen veriye "zaten iç sistemden geldi" diye güvenmemeli; her fonksiyon, girdisini kaynağından bağımsız olarak doğrulamalı (defense in depth, confused deputy'ye karşı).
- **Segmentasyon**: Farklı güven seviyesindeki fonksiyonları (ör. halka açık girdi işleyen ile hassas veri işleyen) ayrı hesaplara/projelere veya en azından ayrı IAM sınırlarına (permission boundary) koyun; "her şey tek hesapta" tasarımından kaçının.
- **VPC kullanan fonksiyonlarda güvenlik gruplarını da klasik ağ segmentasyonu disipliniyle yönetin** — serverless olmak ağ kontrollerini gereksiz kılmaz, sadece birincil kontrol katmanı olmaktan çıkarır.

### Yaygın Hatalar

- Tüm fonksiyonları "kolaylık olsun" diye tek bir geniş IAM role'e veya tek bir VPC/güvenlik grubuna bağlamak.
- Fonksiyonlar arası veri akışını (kim kime mesaj/dosya gönderiyor) hiç haritalamamak, dolayısıyla bir ihlalin "ne kadar yayılabileceğini" önceden bilmemek.

---

## Sonuç: Savunma Zihniyetinde Değişmesi Gereken Şey

Serverless güvenliğinin özü şudur: Güven sınırı artık "makine/ağ" değil, "kimlik/izin ve olay" düzlemine taşınmıştır. Bu nedenle klasik güvenlik reflekslerinin (sunucu sertleştirme, ağ segmentasyonu, port tarama savunması) çoğu YETERSİZ kalır ve yerini şu dört disipline bırakmalıdır: (1) IAM'i kod kadar ciddiye almak ve sürekli daraltmak, (2) her event kaynağını güvenilmeyen girdi olarak muamele etmek, (3) sır yönetimini çalışma zamanı ömrüne (cold/warm start) göre yeniden düşünmek, (4) fonksiyonlar arası veri/olay akışını bir güven grafiği olarak haritalayıp en dar izinle bağlamak. Bu dört ekseni birlikte ele almayan bir serverless güvenlik programı, mimarinin getirdiği asıl riski büyük ölçüde gözden kaçırır.
