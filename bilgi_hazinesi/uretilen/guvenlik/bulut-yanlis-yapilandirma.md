# Bulut Yanlış Yapılandırmaları

## Giriş ve Tanım

Bulut yanlış yapılandırması (cloud misconfiguration), bir bulut kaynağının, güvenlik açısından tehlikeli veya istenmeyen bir durumda çalışacak şekilde ayarlanmasıdır. Burada kritik nokta şudur: ortada sömürülen bir yazılım açığı (vulnerability) yoktur. Ne bir `buffer overflow` vardır, ne yamalanmamış bir CVE, ne de bir zero-day. Sistem tam olarak kendisine söylendiği gibi çalışır. Sorun, ona söylenen şeyin yanlış olmasıdır. Bir S3 bucket'ı herkese açık yapıldığında, AWS bir hata yapmaz; kullanıcının verdiği talimatı harfiyen uygular.

Bu ayrım, konuyu anlamanın anahtarıdır. Geleneksel güvenlik, "kötü kod"u avlar. Bulut güvenliğinin en büyük risk yüzeyi ise "kötü konfigürasyon"dur. Sektörde sıkça atıfta bulunulan bir öngörü, bulut güvenlik ihlallerinin büyük çoğunluğunun sağlayıcının değil, müşterinin hatasından kaynaklanacağı yönündedir. Bunun kurumsal adı **paylaşılan sorumluluk modeli** (shared responsibility model): Bulut sağlayıcısı "bulutun güvenliğinden" (donanım, hypervisor, fiziksel katman) sorumludur; müşteri ise "buluttaki güvenlikten" (veriler, erişim politikaları, ağ ayarları, şifreleme) sorumludur. Yanlış yapılandırma, neredeyse her zaman bu ikinci alanda, yani müşterinin kontrol ettiği katmanda ortaya çıkar.

Bu makalede dört ana odak alanını inceleyeceğiz: açık depolama (public storage), aşırı IAM izinleri (excessive permissions), dışa açık servisler (exposed services) ve bunları tespit eden tarama araçları.

## Kök Neden: Neden Bu Kadar Sık Oluyor?

Yanlış yapılandırmaların yaygınlığını anlamak için, "insanlar dikkatsiz" demenin ötesine geçmek gerekir. Yapısal nedenler vardır.

**Varsayılanların gücü ve varsayılanların evrimi.** Tarihsel olarak birçok bulut servisi, kolay kullanım uğruna görece açık varsayılanlarla geldi. Bir servis "çalışsın da nasıl çalışırsa çalışsın" beklentisi altında hızlıca ayağa kaldırıldığında, kısıtlayıcı olmayan ayar tercih edilir. Sağlayıcılar zamanla varsayılanları sıkılaştırdı (örneğin yeni oluşturulan depolama alanları artık genelde varsayılan olarak kapalıdır), ancak eski kaynaklar, kopyalanan eski `template`'ler ve internetteki eski dökümantasyon, tehlikeli kalıpları yaşatmaya devam ediyor.

**Hız ile güvenlik arasındaki gerilim.** Bulutun temel vaadi hızdır. Bir mühendis, dakikalar içinde bir veritabanı, bir sanal makine ve bir depolama kovası oluşturabilir. Bu hız, düşünme süresini kısaltır. "Şimdi açayım, sonra kısıtlarım" yaklaşımı, o "sonra"nın hiç gelmemesiyle sonuçlanır.

**Karmaşıklık ve dolaylılık.** Özellikle IAM (Identity and Access Management), insan zihninin doğrudan kavrayamayacağı bir karmaşıklığa ulaşabilir. Bir kullanıcının efektif izni; kimlik politikaları, kaynak politikaları, grup üyelikleri, rol devralmaları (`assume role`), izin sınırları (permission boundaries) ve organizasyon düzeyindeki politikaların (SCP gibi) kesişiminden doğar. Bir mühendis "bu kullanıcı ne yapabilir?" sorusuna bakarak dahi kolayca yanılabilir. İzinler toplamsaldır ve tek bir geniş `Allow`, on tane dar kuralı anlamsız kılabilir.

**Altyapının kodla yönetilmesi ve kopyala-yapıştır.** `Terraform`, `CloudFormation` gibi Infrastructure as Code (IaC) araçları güçlüdür ama aynı zamanda hatayı ölçeklendirir. Bir modülde `0.0.0.0/0` (yani "internetin tamamı") yazan biri, o modülü on farklı ortama dağıttığında hatasını on katına çıkarır. Yanlış yapılandırma artık tek bir tıklama değil, versiyon kontrolüne commit edilmiş, tekrarlanabilir bir kusurdur.

**Görünürlük eksikliği.** Klasik bir veri merkezinde envanteri saymak mümkündü. Bulutta kaynaklar dakikalar içinde doğar ve ölür; farklı ekipler farklı hesaplarda kaynak açar. "Neyimiz var ve nasıl yapılandırılmış?" sorusuna cevap vermek, otomatik araçlar olmadan imkânsız hale gelir. Görmediğinizi koruyamazsınız.

## Odak 1: Açık Depolama (Public Storage)

### Çalışma Mantığı

En klasik ve en zararlı yanlış yapılandırma, nesne depolama (object storage) servislerinin -AWS S3, Google Cloud Storage, Azure Blob Storage- yanlışlıkla herkese açık bırakılmasıdır. Bu servisler HTTP(S) üzerinden erişilebilir. Eğer erişim politikası "anonim herkese okuma izni ver" diyorsa, o veriye ulaşmak için hiçbir kimlik doğrulaması gerekmez; sadece doğru URL yeterlidir.

Erişimi belirleyen genellikle iki mekanizma vardır ve karışıklığın kaynağı çoğu zaman bu ikisidir:

- **ACL (Access Control List):** Nesne veya kova düzeyinde, "kim ne yapabilir" listesi. Tehlikeli olan, `AllUsers` (herkes) veya `AuthenticatedUsers` gibi geniş gruplara verilen izinlerdir. Dikkat: `AuthenticatedUsers`, "benim hesabımdaki kimliği doğrulanmış kullanıcılar" anlamına gelmez; o bulut sağlayıcısında hesabı olan **herkes** demektir. Bu, sık yapılan ve yıkıcı bir yanlış anlamadır.
- **Bucket Policy / IAM Policy:** JSON tabanlı, daha ince ayarlı erişim kuralları. Burada `"Principal": "*"` ifadesi, "isteği yapan herkes" anlamına gelir ve bir koşulla (condition) sınırlandırılmamışsa kovayı anonim erişime açar.

### Somut Örnek

Bir ekip, bir web uygulamasının kullanıcı profil fotoğraflarını bir kovada tutuyor. Fotoğrafların tarayıcıdan görüntülenebilmesi için "public read" yaptılar. Sorun şu ki, aynı kovaya zamanla veritabanı yedekleri, log dosyaları ve bir `.env` dosyası da atıldı. Artık o `.env` dosyası -içindeki veritabanı şifreleri ve API anahtarlarıyla birlikte- kimlik doğrulaması olmadan indirilebilir durumda. Kovanın adı tahmin edilebilir (örneğin `sirketadi-backups`) olduğunda, saldırganın bu veriyi bulması dakikalar sürer.

### İstismar Mantığı

Saldırganın bakış açısından açık depolama bir hazine avıdır ve mantığı basittir:

1. **Keşif (enumeration):** Kova isimleri global bir isim uzayında yaşar ve genellikle tahmin edilebilir kalıplar taşır: `sirket-prod`, `sirket-backup`, `sirket-dev`. Saldırganlar, hedef kurumun adını çeşitli ön ek/son eklerle birleştiren kelime listeleri (wordlist) kullanarak var olan kovaları tarar.
2. **İzin testi:** Bulunan her kova için anonim `list` (içeriği listeleme) ve `get` (indirme) denemesi yapılır. Listeleme açıksa saldırgan tüm dosya adlarını görür.
3. **Veri sızdırma (exfiltration):** İlgili görünen dosyalar toplu indirilir. Kovada yazma izni de varsa, iş daha da kötüleşir: saldırgan kova içeriğini değiştirebilir (örneğin bir JavaScript dosyasına zararlı kod enjekte ederek watering hole saldırısı), silebilir veya fidye için şifreleyebilir.

### Savunma

Savunmanın kalbi **derinlemesine savunma** (defense in depth) ve **hesap düzeyinde toplu kilit** yaklaşımıdır.

- **Public Access Block:** AWS'de "Block Public Access" gibi bir mekanizma, hesap veya kova düzeyinde, tek tek ayarların ne dediğine bakılmaksızın tüm anonim erişimi topluca reddeder. Bunu hesap genelinde açmak, tek bir yanlış ACL'nin veri sızdırmasını imkânsızlaştırır. Bu tür bir "master switch" en güçlü tek savunmadır.
- **Varsayılan olarak kapalı, gerekçeyle açık:** Hiçbir kova, açıkça belgelenmiş ve onaylanmış bir iş gerekçesi olmadan public olmamalıdır. Herkese açık içeriğin (örneğin bir CDN kaynağı) verisi, hassas veriden fiziksel olarak ayrı bir kovada tutulmalıdır. Yani "public kovaya asla gizli veri koyma" ilkesi ayrıştırmayla zorlanmalıdır.
- **Şifreleme:** Nesneler durağan halde (at rest) şifrelenmeli. Bu, depolama katmanı ele geçse dahi bir savunma katmanı sağlar, ancak anonim `get` erişimine karşı tek başına yeterli değildir; çünkü servis veriyi okurken zaten çözer.
- **Erişim günlükleri:** Kovaya kimin eriştiğini kaydeden loglar, bir sızıntının fark edilmesi ve olay müdahalesi (incident response) için hayati önemdedir.

## Odak 2: Aşırı IAM İzinleri (Excessive Permissions)

### Çalışma Mantığı

IAM, bulutta kimin neyi yapabileceğini belirleyen sistemdir. Aşırı izin (over-permissioning), bir kimliğe -bir kullanıcıya, bir servise, bir role- işini yapması için gerekenden fazlasının verilmesidir. Bu, en yaygın ve en tehlikeli yanlış yapılandırma sınıfıdır; çünkü doğrudan bir açık kapı yaratmasa bile, başka herhangi bir açığın etkisini felakete dönüştürür.

Temel ilke **en az ayrıcalık** (principle of least privilege) ilkesidir: Bir kimlik, sadece ve sadece görevini yerine getirmek için ihtiyaç duyduğu izinlere sahip olmalıdır. Pratikte ise sıkça görülen, `Action: "*"` ve `Resource: "*"` içeren, yani "her şeyi, her kaynak üzerinde yapabilirsin" diyen politikalardır. Bu genellikle tembellikten değil, gerçek ihtiyacın ne olduğunu bulmanın zor olmasından kaynaklanır. Doğru izin setini belirlemek zahmetlidir; `*` yazmak beş saniye sürer ve "çalışır".

### Neden Bu Kadar Kritik: Privilege Escalation ve Lateral Movement

Aşırı iznin asıl tehlikesi, saldırganın ilk erişim noktasında değil, sonrasında ortaya çıkar. Saldırgan tek bir düşük yetkili kimliği ele geçirdiğinde -örneğin bir kod deposunda unutulmuş bir erişim anahtarı (access key) bulduğunda- işi o kimliğin izinleriyle sınırlıdır. Eğer o kimlik dar yetkiliyse, hasar sınırlı kalır. Ama eğer o kimlik gereğinden geniş yetkiliyse, saldırgan **yatay hareket** (lateral movement) ve **yetki yükseltme** (privilege escalation) yapabilir.

IAM'de yetki yükseltmenin klasik yolları, aslında meşru IAM izinlerinin kötüye kullanımıdır:

- **Yeni politika ekleme yetkisi:** Bir kimlik kendi kendine politika ekleyebiliyorsa (`iam:AttachUserPolicy` benzeri bir izin), kendisine yönetici (`AdministratorAccess`) politikasını ekleyerek anında tam yetki kazanır.
- **Rol devralma zincirleri:** Bir kimlik, kendisinden daha yetkili bir rolü devralabiliyorsa (`sts:AssumeRole`), o rolün yetkilerine bürünür. Yanlış yapılandırılmış güven politikaları (trust policy) bu zincirleri istenmeden açar.
- **Servis kimlikleri üzerinden dolaşma:** Bir sanal makineye yüksek yetkili bir rol atanmışsa ve saldırgan o makineyi ele geçirmişse, makinenin metadata servisi üzerinden o rolün geçici kimlik bilgilerini çekebilir. Bu, bulutta çok sık görülen bir saldırı zinciridir.

Buradaki mantık şudur: Bulutta neredeyse hiçbir ihlal tek adımda gerçekleşmez. Küçük bir dayanak noktası (foothold), aşırı izinler sayesinde tüm ortamın ele geçirilmesine dönüşür. Bu yüzden least privilege, "iyi bir uygulama" değil, ihlalin yarıçapını (blast radius) belirleyen kritik faktördür.

### Savunma

- **En az ayrıcalık ile başla:** Yeni bir kimliğe sıfır izinle başlayıp, ihtiyaç ortaya çıktıkça dar izinler ekle. Tersini yapmak -geniş verip sonra daraltmak- pratikte asla tamamlanmaz.
- **Kullanılmayan izinleri buda:** Sağlayıcılar, bir kimliğin son X günde hangi izinleri fiilen kullandığını gösteren araçlar sunar (örneğin AWS'de "Access Analyzer" ve son erişim bilgileri). Hiç kullanılmayan izinler kaldırılmalıdır. İzinler statik değil, sürekli budanan bir bahçe gibi ele alınmalıdır.
- **Permission boundaries ve SCP:** İzin sınırları ve organizasyon düzeyindeki servis kontrol politikaları (Service Control Policies), bir kimliğin alabileceği maksimum yetkiye bir tavan koyar. Bir mühendis yanlışlıkla kendine admin verse bile, üstteki SCP buna izin vermez. Bu, "insan hata yapacak" varsayımıyla tasarlanmış bir güvenlik ağıdır.
- **İnsan yerine rol:** Uzun ömürlü erişim anahtarları yerine, kısa ömürlü, otomatik dönen kimlik bilgileri (geçici token'lar, rol devralma) tercih edilmelidir. Sızdırılan bir anahtar aylarca geçerliyse felakettir; on beş dakika geçerliyse çoğu zaman zararsızdır.
- **Root/en yetkili hesabın izolasyonu:** En yetkili hesap günlük işlerde asla kullanılmamalı, üzerinde çok faktörlü kimlik doğrulama (MFA) zorunlu olmalı ve neredeyse hiç dokunulmamalıdır.

## Odak 3: Dışa Açık Servisler (Exposed Services)

### Çalışma Mantığı

Bu kategori, bir servisin ağ düzeyinde olması gerekenden geniş bir kitleye açılmasıdır. Klasik örnek, bir yönetim portunun veya veritabanının doğrudan internete açılmasıdır. Bulutta ağ erişimini kontrol eden temel araçlar güvenlik grupları (security groups), ağ ACL'leri ve firewall kurallarıdır. Bu kurallarda kaynak adresi olarak `0.0.0.0/0` yazmak, "dünyadaki her IP adresinden gelen bağlantıyı kabul et" demektir.

En tehlikeli örnekler:

- **Yönetim portları:** SSH (22), RDP (3389) gibi portların internete açılması. Bunlar açık olduğu anda, dünya çapındaki otomatik botlar saniyeler içinde bulur ve kimlik bilgisi deneme (brute force / credential stuffing) saldırılarına başlar.
- **Veritabanları:** Genellikle kimlik doğrulaması zayıf ya da hiç olmayan veritabanı ve önbellek servislerinin (yaygın NoSQL veritabanları, önbellek katmanları, arama motorları) internete açılması. Geçmişte "internete açık, şifresiz veritabanı" milyonlarca kaydın sızmasına yol açan bir kalıp olmuştur.
- **Yönetim panelleri ve API'ler:** Kubernetes API sunucusu, konteyner orkestrasyon panelleri, CI/CD arayüzleri gibi, kimliği doğrulanmamış erişim verildiğinde tüm kümenin kontrolünü teslim eden servisler.

### Somut Örnek ve Metadata Riski

Bir geliştirici, sorun gidermek için bir veritabanının güvenlik grubunu geçici olarak `0.0.0.0/0` yaptı ve geri almayı unuttu. O andan itibaren veritabanı tüm internete açıktır. Buna ek olarak, bulutta özellikle tehlikeli bir kalıp SSRF (Server-Side Request Forgery) ile metadata servisinin birleşimidir: Uygulama katmanındaki bir SSRF açığı, saldırganın sunucuyu kendi metadata endpoint'ine istek yapmaya zorlamasına ve buradan sunucunun rol kimlik bilgilerini çalmasına imkân verebilir. Bu yüzden metadata servisinin daha korumalı sürümünü (örneğin oturum tabanlı, tek atlamalık erişim gerektiren yapılandırma) zorunlu kılmak önemli bir sertleştirme adımıdır.

### İstismar Mantığı

Dışa açık servislere yönelik saldırı, büyük ölçüde otomatiktir ve internet ölçeğinde çalışır:

1. **İnternet çapı tarama:** Saldırganlar tüm IPv4 uzayını sürekli tarayan araçlar ve `Shodan`, `Censys` gibi hazır arama motorları kullanır. Bu motorlar internete açık her servisi, banner'ıyla ve versiyonuyla birlikte indeksler. "Şu versiyondaki şu veritabanı, kimlik doğrulaması kapalı" gibi bir sorgu, saldırgana hazır hedef listesi verir.
2. **Otomatik istismar:** Zayıf/varsayılan kimlik bilgileri denenir, bilinen açıklar için exploit çalıştırılır. Burada saldırgan sizi tanımaz; sadece açık bir kapı görür ve girer. Hedeflenmek için önemli olmanıza gerek yoktur, açık olmanız yeterlidir.

### Savunma

- **Varsayılan reddet (default deny):** Ağ kuralları "her şey kapalı, sadece gerekli olan açık" mantığıyla kurulmalıdır. Kaynak olarak `0.0.0.0/0`, yalnızca gerçekten herkese açık olması gereken servisler (örneğin bir public web sunucusunun 443 portu) için ve bilinçli bir kararla kullanılmalıdır.
- **Yönetim erişimini tünelle:** SSH/RDP asla doğrudan internete açılmamalıdır. Bunun yerine bir bastion host, sağlayıcının oturum yöneticisi (session manager) veya sıfır güven (zero trust) ağ erişimi kullanılmalıdır. İdeal olan, yönetim portunun internetten hiç görünmemesidir.
- **Ağ segmentasyonu:** Veritabanları, uygulama sunucularının bulunduğu ağdan ayrı, internete çıkışı olmayan özel alt ağlarda (private subnet) tutulmalıdır. Bir katman ele geçse bile bir sonrakine geçiş ağ düzeyinde engellenir.
- **Sürekli doğrulama:** "Şu an internete açık olan ne var?" sorusu, insan hafızasına değil sürekli çalışan bir tarama sürecine bırakılmalıdır. Geçici açılan bir kural, saatler içinde tespit edilip alarma dönüşmelidir.

## Odak 4: Tespit ve Tarama Araçları

Bu kadar geniş ve dinamik bir yüzeyi manuel denetlemek imkânsızdır. Bu yüzden yanlış yapılandırma yönetimi büyük ölçüde araç ve otomasyon meselesidir. Araçları amaçlarına göre gruplamak, hangisinin ne zaman kullanıldığını anlamayı kolaylaştırır.

### Dışarıdan Bakan Keşif Araçları (Attacker's View)

Saldırganların da savunmacıların da kullandığı, "dışarıdan ne görünüyor?" sorusuna cevap veren araçlardır:

- **Shodan / Censys:** İnternete açık servislerin arama motorları. Kendi IP aralıklarınızı bu motorlarda aratarak, dışarıya istemeden ne sızdırdığınızı görebilirsiniz. Savunmacı için bu, saldırganla aynı gözle bakma imkânıdır.
- **Depolama kovası tarayıcıları:** Kova isimlerini tahmin ederek açık depolama arayan açık kaynak araçlar mevcuttur. Bunlar hem saldırgan tarafından hedef bulmak hem de savunmacı tarafından "kendi kovalarımız dışarıdan erişilebilir mi?" testi için kullanılır.

### CSPM: Bulut Güvenlik Duruş Yönetimi

Bu konunun kalbindeki araç kategorisi **CSPM** (Cloud Security Posture Management) olarak bilinir. Bir CSPM aracı, bulut hesabınıza okuma yetkisiyle bağlanır, tüm kaynakların yapılandırmasını sürekli okur ve bunları bir kurallar/kıyaslama seti (benchmark) ile karşılaştırır. "Bu kova public mi?", "Bu güvenlik grubu 22'yi dünyaya açık mı?", "Bu rolde admin izni var mı?" gibi yüzlerce kontrolü otomatik ve sürekli çalıştırır.

Bu alanda hem açık kaynak hem ticari çözümler vardır. Açık kaynak dünyasında çok kullanılan denetim araçları (örneğin AWS için `Prowler`, çok bulutlu ortamlar için `ScoutSuite` ve `CloudSploit` gibi projeler) bir hesabı tarayıp bulguları raporlar. Ölçüt olarak genellikle **CIS Benchmarks** (Center for Internet Security) gibi sektörce kabul görmüş sertleştirme kılavuzları kullanılır; bu kılavuzlar, her büyük bulut için "güvenli varsayılan" ne demek olduğunu maddeler halinde tanımlar.

CSPM'in değeri, tek seferlik bir denetim değil **sürekli** olmasıdır. Bulut sürekli değiştiği için, dünkü temiz rapor bugün geçerli olmayabilir. İyi bir CSPM, yeni bir kaynak yanlış yapılandırıldığı anda alarm üretir.

### Kaydırma-Sola: IaC Tarama (Shift Left)

En etkili yaklaşım, yanlış yapılandırmayı canlı ortama ulaşmadan, kod aşamasında yakalamaktır. Buna **shift left** (kontrolü geliştirme sürecinin başına kaydırma) denir. `Terraform`, `CloudFormation` gibi IaC dosyalarını, dağıtımdan önce statik olarak tarayan araçlar vardır (bu kategoride yaygın kullanılan açık kaynak araçlar bulunur; örneğin `Checkov`, `tfsec`/`Trivy`, `terrascan` gibi projeler). Bunlar CI/CD hattına yerleştirilir ve bir mühendis `0.0.0.0/0` içeren bir güvenlik grubu yazdığında, kod daha `merge` edilmeden uyarı verir veya dağıtımı durdurur.

Bunun mantığı ekonomiktir: Bir yanlış yapılandırmayı kod aşamasında düzeltmek dakikalar; canlıda tespit edip düzeltmek saatler; ihlalden sonra temizlemek ise haftalar ve itibar kaybı demektir. Hatayı ne kadar erken yakalarsan o kadar ucuzdur.

### CIEM: İzin Analizi

IAM'in karmaşıklığı için özelleşmiş bir kategori **CIEM** (Cloud Infrastructure Entitlement Management) olarak bilinir. Bu araçlar, "bu kimlik teoride ne yapabilir ve pratikte ne kullanıyor?" sorusuna odaklanır; kullanılmayan izinleri, tehlikeli yetki yükseltme yollarını ve aşırı geniş rolleri görselleştirir. Least privilege'ı elle uygulamanın imkânsızlığına verilen otomatik cevaptır.

## Yaygın Hatalar

Aşağıdaki hatalar, sahada tekrar tekrar görülen kalıplardır ve çoğu, iyi niyetli mühendislerin baskı altında verdiği kısa yollardan doğar:

- **"Geçici" değişikliklerin kalıcılaşması.** Sorun gidermek için açılan bir port, verilen bir izin ya da public yapılan bir kova, iş bitince geri alınmaz. Geçici olan hiçbir şey gerçekten geçici değildir; bu yüzden geçici değişiklikler otomatik süre sonu (TTL) ile ya da bir ticket'a bağlanarak yönetilmelidir.
- **`AuthenticatedUsers`'ı yanlış anlamak.** "Kimliği doğrulanmış kullanıcılar"ın kendi kurumunuzla sınırlı olduğunu sanmak. Gerçekte bu, o bulutta hesabı olan herkestir.
- **`*` ile izin yazmak.** Hem `Action` hem `Resource` alanında yıldız kullanmak; "sonra daraltırım" diyerek admin yetkisi vermek. O daraltma günü asla gelmez.
- **Sırların kaynağa gömülmesi.** API anahtarlarını, veritabanı şifrelerini kod deposuna, konteyner imajına ya da yapılandırma dosyasına gömmek. Sırlar bir secrets manager'da tutulmalı ve kod depoları sır tarayıcılarıyla denetlenmelidir.
- **Loglamanın ve denetim izinin (audit trail) kapalı olması.** Bulut aktivitelerini kaydeden servis (örneğin AWS CloudTrail) açık değilse, bir ihlal olduğunda ne olduğunu anlamanın hiçbir yolu kalmaz. Görünürlük olmadan güvenlik yoktur.
- **Şifrelemeyi tek savunma sanmak.** "Veri şifreli, o zaman güvende" düşüncesi yanıltıcıdır; anonim `get` erişimi olan bir kovada şifreleme, veriyi okuyan servis onu zaten çözdüğü için saldırganı durdurmaz. Şifreleme bir katmandır, tek başına yeterli değildir.
- **Her hesap için ayrı ayrı düşünmek.** Organizasyon düzeyinde politika (SCP, merkezi loglama, merkezi CSPM) kurmak yerine her hesabı tek tek yönetmeye çalışmak. Ölçeklenince bu yaklaşım çöker.

## En İyi Pratikler

Sonuç olarak, bulut yanlış yapılandırmalarına karşı sağlam bir duruş, birbirini tamamlayan birkaç ilkeye dayanır:

1. **Varsayılanı reddet, gerekçeyle aç.** Hem ağ hem erişim hem depolama katmanında, güvenli varsayılan "kapalı" olmalı; her açılma bilinçli, belgelenmiş bir karar olmalıdır.
2. **En az ayrıcalığı zorunlu kıl.** İzinleri sürekli budanan bir şey olarak ele al. Kullanılmayanı kaldır, kimseye ihtiyacından fazlasını verme, uzun ömürlü anahtarlar yerine kısa ömürlü kimlikler kullan.
3. **Blast radius'u küçült.** Ağ segmentasyonu, ayrı hesaplar, permission boundary ve SCP ile, tek bir hatanın ya da ihlalin yayılabileceği alanı en baştan sınırla. Bir şey ele geçtiğinde ne kadarına ulaşabileceği tasarımla belirlenir.
4. **Kontrolü sola kaydır.** Yanlış yapılandırmayı canlıya çıkmadan, kod aşamasında yakala. IaC tarayıcılarını CI/CD hattına zorunlu adım olarak koy.
5. **Sürekli izle.** Tek seferlik denetim değil, CSPM ve CIEM ile sürekli izleme. Bulut sürekli değişir; savunma da sürekli olmalıdır.
6. **Kendini saldırganın gözünden gör.** Kendi IP ve kova alanını `Shodan`/`Censys` ve kova tarayıcılarıyla düzenli tara. Dışarıdan ne göründüğünü bilmek, savunmanın en dürüst aynasıdır.
7. **Her şeyi kaydet, MFA'yı her yerde zorla.** Denetim izini (audit trail) her zaman açık tut, en yetkili hesapları izole et ve çok faktörlü kimlik doğrulamayı istisnasız uygula.

Bulut güvenliğinin özünde şu vardır: Tehdit çoğu zaman gizli bir yazılım açığı değil, açıkça yapılmış yanlış bir tercihtir. Bu yüzden çözüm de büyük ölçüde disiplin, otomasyon ve doğru varsayılanlar meselesidir. Sistemler tam olarak söylendikleri gibi çalışır; iş, onlara doğru şeyi söylemektir.
