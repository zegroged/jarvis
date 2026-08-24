# Güvenli Kod Yazımı

Güvenli kod yazımı, bir yazılımın yalnızca "beklenen girdilerle doğru çalışması" değil, **kötü niyetli, bozuk veya beklenmedik girdiler karşısında da güvenliği ihlal etmeden davranması** disiplinidir. Klasik yazılım kalitesi "program ne yapmalı?" sorusuna odaklanır; güvenlik ise "saldırgan bu programa neyi *yaptırabilir*?" sorusuna odaklanır. Bu iki bakış açısı arasındaki fark, güvenli kodun neden ayrı bir zihniyet gerektirdiğini açıklar: Normal bir mühendis mutlu yolu (happy path) düşünür, güvenlik mühendisi ise düşmanın yolunu düşünür.

Bu makale dört temel taşa odaklanır: **girdi doğrulama** (input validation), **veri/kod ayrımı**, **en az yetki** (least privilege) ve **sır yönetimi** (secrets management). Bu dördü tesadüfen seçilmiş konular değildir; modern yazılımlardaki güvenlik açıklarının ezici çoğunluğu bu dört prensipten birinin ihlalinden doğar.

## Neden Güvenlik Ayrı Bir Zihniyettir

Bir programın "çalışması" ile "güvenli olması" bağımsız özelliklerdir. Bir fonksiyon tüm testlerini geçebilir, performansı mükemmel olabilir ve yine de sömürülebilir bir açık barındırabilir. Kök neden şudur: **Test edilen girdi kümesi sonludur, ama saldırganın deneyebileceği girdi kümesi neredeyse sonsuzdur.** Geliştirici on örnek girdi düşünürken, saldırgan milyonlarca kenar durumu (edge case), kodlama numarası ve protokol suistimali dener.

Güvenlik açıkları çoğu zaman tek bir hatadan değil, **güven varsayımlarının** yanlış yerde yapılmasından doğar. "Bu veri zaten temizlenmiştir", "bu istek yalnızca bizim frontend'imizden gelir", "bu kullanıcı zaten yetkili" gibi doğrulanmamış varsayımlar, güvenlik açıklarının doğduğu yerlerdir. Güvenli kod yazımının temel refleksi, her güven sınırında (trust boundary) durup "buraya gelen veri neden güvenilir olsun?" diye sormaktır.

## Girdi Doğrulama (Input Validation)

### Tanım ve Kök Neden

Girdi doğrulama, dışarıdan gelen her verinin işleme alınmadan önce beklenen biçim, tür, aralık ve uzunluğa uyup uymadığının denetlenmesidir. Buradaki kritik kelime "dışarıdan"dır. Güvenlik açısından **dışarısı** yalnızca son kullanıcı formu değildir: HTTP başlıkları, çerezler (cookies), URL parametreleri, dosya adları, yüklenen dosyaların içeriği, başka mikroservislerden gelen JSON, veritabanından okunan eski kayıtlar, ortam değişkenleri ve hatta zamanlanmış bir işten gelen veri — hepsi potansiyel olarak güvenilmezdir.

Kök neden şudur: Bilgisayar, verinin *anlamını* bilmez; yalnızca baytları işler. Bir alanın "e-posta adresi" olması gerektiği bilgisi sizin zihninizdedir, programın çalışma zamanında değil. Eğer bu beklentiyi açıkça koda dökmez ve zorlamazsanız, saldırgan o alana e-posta yerine bir SQL parçası, bir shell komutu ya da 2 GB'lık bir dize koyabilir ve program bunu memnuniyetle kabul eder.

### Allowlist ile Denylist

Girdi doğrulamada en önemli stratejik karar, **allowlist mi denylist mi** olduğudur. Denylist (kara liste) yaklaşımı "kötü olduğunu bildiğim şeyleri engelleyeyim" der: örneğin `<script>` dizesini, `../` dizisini veya tek tırnağı filtrelemeye çalışır. Bu yaklaşım neredeyse her zaman yenilgiye mahkûmdur, çünkü **saldırganın yaratıcılığını önceden tahmin edebileceğinizi varsayar.** Kötü olan her şeyi listelemek imkânsızdır; kodlama varyasyonları (`%3Cscript%3E`, unicode eşdeğerleri, büyük-küçük harf oyunları) denylist'i sürekli aşar.

Allowlist (beyaz liste, izin listesi) yaklaşımı ise tam tersini yapar: "yalnızca açıkça iyi olduğunu bildiğim şeye izin ver, gerisini reddet." Bir kullanıcı adının yalnızca harf, rakam ve alt çizgiden oluşabileceğini ve 3–32 karakter olabileceğini tanımlarsanız, düşünmediğiniz saldırılar dahil her şey otomatik olarak reddedilir. Allowlist'in gücü, **bilinmeyen bilinmeyenleri de kapsamasıdır**: Henüz keşfedilmemiş bir saldırı tekniği bile, tanımınıza uymadığı için engellenir.

### Somut Örnek ve Doğru Katman

Bir dosya indirme uç noktası düşünün: `GET /indir?dosya=rapor.pdf`. Naif bir uygulama dosya adını alıp doğrudan disk yoluna ekler. Saldırgan `dosya=../../../../etc/passwd` gönderdiğinde, bu bir **path traversal** açığıdır ve sunucudaki hassas dosyaları okuyabilir. Denylist yaklaşımıyla `../` dizisini silmeye çalışmak yetersizdir; `....//` gibi varyasyonlar veya URL kodlaması filtreyi aşabilir. Doğru çözüm allowlist'tir: Dosya adının yalnızca beklenen desene (örneğin `^[a-zA-Z0-9_-]+\.pdf$`) uyduğunu doğrulamak, ardından çözümlenmiş mutlak yolun izin verilen dizinin *içinde* kaldığını (canonical path karşılaştırması) ayrıca teyit etmektir.

Burada kritik bir tuzak vardır: **Doğrulamayı yanlış katmanda yapmak.** İstemci tarafı (client-side) doğrulama yalnızca kullanıcı deneyimi içindir; saldırgan tarayıcıyı atlayıp isteği doğrudan gönderebileceği için hiçbir güvenlik değeri taşımaz. Doğrulama daima verinin **güvenilir tarafa geçtiği sınırda**, yani sunucuda yapılmalıdır. Ayrıca doğrulama, verinin anlamının netleştiği yerde yapılmalıdır: Bir sayının aralığı iş mantığı katmanında, bir dizenin SQL'e gömülmeden önceki güvenliği ise veri erişim katmanında ele alınır.

### Yaygın Hatalar

- **Normalleştirmeden önce doğrulama.** Eğer önce doğrulayıp sonra Unicode normalleştirme (normalization) veya URL kod çözme yaparsanız, doğruladığınız dize ile sonunda kullanılan dize farklı olur. Daima **önce kanonik forma getir, sonra doğrula, sonra kullan** sırasını izleyin.
- **Uzunluk sınırının unutulması.** Aralık ve biçim doğrulanır ama boyut doğrulanmazsa, saldırgan aşırı büyük girdilerle bellek tüketimi veya hizmet reddi (denial of service) tetikleyebilir.
- **Doğrulama ile temizlemenin (sanitization) karıştırılması.** Doğrulama "kabul et ya da reddet" kararıdır; temizleme veriyi değiştirir. Sessizce veri değiştirmek (örneğin tehlikeli karakterleri silmek) çoğu zaman öngörülemeyen sonuçlar doğurur; genellikle reddetmek daha güvenlidir.

## Veri/Kod Ayrımı

### Tanım ve Kök Neden

Enjeksiyon (injection) açıklarının tamamının altında yatan tek bir kavramsal hata vardır: **verinin, onu işleyen sistem tarafından kod olarak yorumlanması.** SQL injection, komut enjeksiyonu (command injection), Cross-Site Scripting (XSS), LDAP injection ve daha niceleri aynı hastalığın farklı yüzleridir. Hepsinde ortak nokta: Geliştirici bir dize oluştururken kullanıcı verisini komut metnine *karıştırır* ve alt sistem (veritabanı, kabuk, tarayıcı) bu karışımı ayrıştırırken kullanıcının verisini komutun parçası sanır.

Kök neden, **birleştirme (concatenation) ile veriyi ve kodu tek bir metin dizesinde eritmektir.** Bir kez birleştirdikten sonra, ayrıştırıcı için hangi baytın "geliştiricinin niyeti", hangisinin "kullanıcının verisi" olduğunu ayırt etmenin bir yolu kalmaz. Çözüm bu yüzden kaçış karakterleri (escaping) eklemek değil, **veriyi ve kodu hiç birleştirmemektir.**

### Somut Örnek: SQL Injection

Klasik örnek: `"SELECT * FROM kullanicilar WHERE ad = '" + kullaniciAdi + "'"`. Saldırgan kullanıcı adı olarak `' OR '1'='1` girerse, sorgu tüm satırları döndürür; `'; DROP TABLE kullanicilar; --` girerse tabloyu silebilir. Neden? Çünkü tek tırnak, dize verisinin bittiğini ve yeni bir SQL ifadesinin başladığını bildiren bir **kontrol karakteridir**. Kullanıcının verisi, veri sınırını "kırıp" komut alanına taştığında enjeksiyon gerçekleşir.

Doğru çözüm **parametreli sorgulardır** (parameterized queries / prepared statements): `SELECT * FROM kullanicilar WHERE ad = ?` yazılır ve `kullaniciAdi` ayrı bir parametre olarak iletilir. Bu neden işe yarar? Çünkü sorgunun yapısı (kod) veritabanına önceden, parametrelerden *bağımsız* olarak gönderilir. Veritabanı `?` konumundaki değeri her zaman saf veri olarak muamele eder; içindeki tek tırnak veya `DROP TABLE` metni asla ayrıştırılmaz, yalnızca aranacak bir dize olarak ele alınır. Veri ile kod protokol düzeyinde ayrılmıştır, string düzeyinde değil. Bu, string escaping'den kategorik olarak üstündür çünkü escaping'i unutmak veya yanlış yapmak mümkünken, parametreli bir sorguda enjeksiyon yapısal olarak imkânsızdır.

### Diğer Enjeksiyon Türleri ve Aynı Çözüm Deseni

Aynı desen her yerde tekrarlanır. Komut enjeksiyonunda, kullanıcı girdisini bir kabuk (shell) komut dizesine gömmek yerine, programı doğrudan bir argüman dizisiyle (`exec(["ffmpeg", "-i", kullaniciDosyasi])`) çağırırsınız — böylece kabuk hiç devreye girmez ve `;`, `|`, `$()` gibi kabuk metakarakterleri anlamlarını yitirir. XSS'te, kullanıcı verisini HTML'e string olarak eklemek yerine, çıktının gömüldüğü bağlama uygun **context-aware output encoding** uygularsınız veya şablon motorunun otomatik kaçışına güvenirsiniz.

Buradaki genel prensip şudur: **Kaçış (escaping) daima çıktının gideceği hedefe göre yapılmalıdır, girdinin geldiği yere göre değil.** Aynı veri HTML gövdesine, HTML özniteliğine, JavaScript bağlamına ve URL'ye farklı biçimlerde kodlanır. Bir bağlam için doğru kaçış, başka bir bağlamda tamamen yetersizdir. Bu yüzden "girişte bir kez temizleyip her yerde güvenle kullanırım" düşüncesi tehlikeli bir yanılgıdır.

### Yaygın Hatalar

- **Kendi kaçış fonksiyonunu yazmak.** Tek tırnağı iki tırnakla değiştiren ev yapımı çözümler, karakter kodlaması kenar durumlarında ve çok baytlı (multibyte) karakter saldırılarında başarısız olur. Daima platformun parametreleştirme mekanizmasını kullanın.
- **ORM veya sorgu oluşturucuya körü körüne güvenmek.** Modern ORM'ler çoğu durumda parametreleştirir, ama ham SQL parçası eklemeye izin veren yöntemler (raw fragments) hâlâ enjeksiyona açıktır.
- **Yalnızca girdi doğrulamaya güvenip veri/kod ayrımını atlamak.** İkisi tamamlayıcıdır, alternatif değildir. Bir isim alanı meşru olarak tek tırnak içerebilir (`O'Brien`); doğrulama bunu reddetmemelidir, dolayısıyla enjeksiyona karşı gerçek savunma parametreleştirmedir.

## En Az Yetki (Least Privilege)

### Tanım ve Kök Neden

En az yetki ilkesi, her bileşenin (kullanıcı, süreç, servis, API anahtarı) yalnızca görevini yerine getirmek için gereken **asgari izinlere** sahip olması gerektiğini söyler. Kök neden basittir ama derindir: **Bir bileşen ne kadar çok yetkiye sahipse, o bileşen ele geçirildiğinde saldırganın eline geçen güç o kadar büyüktür.** Güvenlik açıkları kaçınılmazdır; en az yetki, kaçınılmaz olan ihlalin *yıkım yarıçapını* (blast radius) küçültme stratejisidir.

Bu ilkenin en güçlü tarafı, **savunmanın diğer katmanları başarısız olduğunda bile değer üretmesidir.** Girdi doğrulamanız aşıldı, bir enjeksiyon açığınız var diyelim. Eğer uygulamanın veritabanı kullanıcısı yalnızca birkaç tabloya `SELECT` yetkisine sahipse, saldırgan `DROP TABLE` çalıştıramaz veya başka veritabanlarını okuyamaz. En az yetki, tek bir hatanın toplam felakete dönüşmesini engelleyen bir kayıp önleyicidir (containment).

### Somut Örnek

Tipik bir hata, uygulamanın veritabanına `admin` veya `root` düzeyinde bir hesapla bağlanmasıdır — sırf "her ihtimale karşı" ya da kurulumu kolaylaştırmak için. Bu, enjeksiyon riski gibi görünmeyen bir mimari kararın, bir açık ortaya çıktığında felaketi katbekat büyütmesi demektir. Doğrusu, uygulamanın yalnızca ihtiyaç duyduğu tablolara ihtiyaç duyduğu işlemler (bazıları sadece okuma, bazıları okuma-yazma) için yetkilendirilmiş, ayrı ve dar kapsamlı bir veritabanı hesabı kullanmasıdır.

Aynı prensip her yerde geçerlidir: Bir konteyner (container) `root` yerine ayrıcalıksız bir kullanıcıyla çalışmalı; bir bulut servis rolü (IAM role) tüm S3 kovalarına değil yalnızca kullandığı tek kovaya erişebilmeli; bir API anahtarı okuma-yazma-silme yerine yalnızca gereken kapsama (scope) sahip olmalı; bir mikroservis ağ düzeyinde yalnızca konuşması gereken servislerle iletişim kurabilmelidir. Her genişletilmiş yetki, ileride birinin sömüreceği potansiyel bir yoldur.

### Zamansal ve Kapsamsal Daraltma

En az yetkinin iki boyutu vardır. **Kapsam** boyutu "neye erişebilir?" sorusudur (yukarıda anlatıldı). **Zaman** boyutu ise "ne kadar süre erişebilir?" sorusudur. Kalıcı, süresi dolmayan geniş yetkiler yerine, kısa ömürlü ve gerektiğinde verilen (just-in-time) erişim çok daha güvenlidir. Örneğin, statik ve asla değişmeyen bulut kimlik bilgileri yerine, otomatik olarak kısa aralıklarla yenilenen geçici kimlik bilgileri (temporary credentials) kullanmak, sızan bir bilginin işe yarama penceresini dramatik biçimde daraltır.

### Yaygın Hatalar

- **Geliştirme kolaylığı için geniş yetki verip düzeltmeyi unutmak.** "Şimdilik hepsine izin verelim, sonra daraltırız" kararı neredeyse hiçbir zaman geri alınmaz ve prodüksiyona sızar.
- **Kullanılmayan izinlerin birikmesi (privilege creep).** Zamanla eklenen ama artık gerekmeyen izinler temizlenmezse, hesaplar giderek daha tehlikeli birer hedefe dönüşür. Periyodik izin denetimi (access review) şarttır.
- **Yetki sınırlarını yalnızca uygulama katmanında zorlamak.** Uygulama kodu "bu kullanıcı bunu yapamaz" dese bile, alttaki veritabanı veya dosya sistemi izinleri de bunu bağımsız olarak zorlamalıdır. Derinlemesine savunma (defense in depth) tek bir katmana güvenmemek demektir.

## Sır Yönetimi (Secrets Management)

### Tanım ve Kök Neden

Sırlar; parolalar, API anahtarları, veritabanı bağlantı dizeleri, şifreleme anahtarları, private key'ler ve token'lar gibi, ifşa edildiğinde güvenliği doğrudan çökerten hassas verilerdir. Sır yönetiminin kök zorluğu şudur: **Sırların bir yerde bulunması gerekir ki uygulama onları kullanabilsin, ama bulundukları her yer bir sızıntı riskidir.** İyi sır yönetimi, sırların yaşam döngüsü boyunca (oluşturma, saklama, dağıtma, kullanma, döndürme, iptal etme) maruz kaldığı yüzey alanını en aza indirmektir.

### Neden Kaynak Kodu Sırlar İçin En Kötü Yerdir

En yaygın ve en yıkıcı hata, sırları doğrudan kaynak koduna gömmektir (hardcoding). Bunun neden bu kadar tehlikeli olduğunu anlamak önemlidir. Kaynak kodu **kopyalanmak üzere tasarlanmıştır**: Her geliştiricinin makinesine klonlanır, yedeklenir, CI/CD sistemlerine, log'lara ve genellikle üçüncü taraf araçlara akar. Daha da kötüsü, versiyon kontrolü (git gibi) **geçmişi kalıcı kılar**: Bir sırrı bir commit'te ekleyip sonraki commit'te silseniz bile, sır tüm geçmiş boyunca erişilebilir kalır. "Sildim" hissi sahte bir güven verir; sır hâlâ oradadır.

Bu nedenle temel kural mutlaktır: **Bir sır bir kez versiyon kontrolüne girdiyse, o sır ifşa olmuş kabul edilmelidir ve derhal döndürülmelidir (rotation).** Geçmişi temizlemek genellikle mümkün olsa da, sırrın o pencerede kopyalanmadığını asla garanti edemezsiniz. Tek güvenli varsayım, sırrın yandığı ve yenisinin üretilmesi gerektiğidir.

### Doğru Yaklaşımlar

Sırları koddan tamamen ayrı tutmak temel prensiptir. Pratikte bu, sırların **çalışma zamanında** koda enjekte edilmesi anlamına gelir; kaynakta değil. Bunun birkaç düzeyi vardır:

- **Ortam değişkenleri ve yapılandırma dosyaları** (kod deposunun dışında, `.gitignore`'a eklenmiş): Basit projeler için bir başlangıçtır ama zayıf noktaları vardır — süreç ortamı log'lara veya hata raporlarına sızabilir.
- **Adanmış sır kasaları (secret managers / vaults):** Sırların şifreli olarak saklandığı, erişimin denetlendiği ve kaydedildiği (audit log), ve sırların merkezî olarak döndürülebildiği sistemler. Uygulama, sırrı bir dosyadan değil, kimliğini kanıtlayarak bu servisten çalışma zamanında talep eder. Bu yaklaşımın büyük avantajı, sırrın hiçbir zaman kalıcı bir dosyada bulunmaması ve döndürmenin (rotation) tek merkezden yapılabilmesidir.

### Döndürme, Denetim ve Sızıntı Tespiti

Sır yönetimi tek seferlik bir kurulum değil, süregelen bir süreçtir. Üç bileşen kritiktir. **Döndürme (rotation):** Sırlar düzenli aralıklarla ve özellikle bir sızıntı şüphesinde derhal değiştirilmelidir; kısa ömürlü sırlar, uzun ömürlülerden çok daha güvenlidir. **Denetim (auditing):** Bir sırra kim, ne zaman eriştiği kaydedilmelidir, böylece anormal erişim tespit edilebilir. **Sızıntı tespiti:** Kod deposuna sır girişini yakalamak için otomatik tarayıcılar (commit öncesi hook'lar ve CI kontrolleri olarak) kullanmak, sorunu depoya karışmadan önce durdurmanın en etkili yoludur.

### Yaygın Hatalar

- **Sırları log'lara yazmak.** Hata ayıklarken bağlantı dizesini veya token'ı log'lamak, sırrı düz metin olarak log altyapısının her yerine yaymaktır. Log'lar genellikle güvenlik sırlarından çok daha az korunur.
- **Örnek/varsayılan sırları prodüksiyona taşımak.** `admin/admin` veya örnek yapılandırmalardaki test anahtarları değiştirilmeden canlıya çıkarsa, bu tahmin edilebilir bir açık kapıdır.
- **Sırları istemci tarafına gömmek.** Bir API anahtarını mobil uygulamanın veya JavaScript paketinin içine koymak, onu herkese açık etmektir; istemci kodu daima tersine mühendisliğe (reverse engineering) açıktır.
- **"Şifreleme" ile "kodlama"yı karıştırmak.** Base64 bir kodlamadır, koruma değildir; base64'lenmiş bir sır düz metin kadar açıktır.

## Prensipleri Birlikte Düşünmek: Derinlemesine Savunma

Bu dört prensibin ayrı ayrı ele alınması pedagojik bir kolaylıktır; gerçekte bunlar **katmanlı bir savunma** oluşturur ve en büyük değerlerini birlikte gösterirler. Bir örnekle görelim: Bir saldırgan bir enjeksiyon açığı bulmak istiyor.

- **Girdi doğrulama** ilk katmandır: Beklenmedik biçimli girdiyi en baştan reddederek birçok saldırıyı hiç başlamadan durdurur.
- **Veri/kod ayrımı** (parametreleştirme) ikinci katmandır: Doğrulamayı aşan meşru görünümlü girdi bile komut olarak yorumlanamaz.
- **En az yetki** üçüncü katmandır: İlk iki katman bir şekilde başarısız olsa bile, ele geçirilen bağlantının yetkisi dar olduğu için hasar sınırlı kalır.
- **Sır yönetimi** dördüncü katmandır: Saldırgan bir şekilde sunucuya eriştiğinde bile, sırlar koda gömülü olmadığı için tüm sistemin anahtarlarını ele geçiremez.

Buradaki temel felsefe **derinlemesine savunmadır** (defense in depth): Hiçbir tek kontrolün mükemmel olmadığını kabul edip, bir katman delindiğinde diğerlerinin devreye girdiği üst üste bağımsız savunmalar kurmak. Güvenlik, tek bir "sihirli çözüm" değil, her biri diğerinin başarısızlığını telafi eden katmanların bileşimidir.

## En İyi Pratiklerin Özeti

- **Tüm dış girdileri güvenilmez say** ve güven sınırında, sunucu tarafında, allowlist temelli doğrula. Önce kanonik forma getir, sonra doğrula, sonra kullan.
- **Veriyi asla koda birleştirme.** SQL için parametreli sorgular, komutlar için argüman dizileri, çıktı için bağlama duyarlı kodlama kullan. Enjeksiyonu bir filtre sorunu değil, bir mimari sorun olarak çöz.
- **Her bileşene asgari yetkiyi ver**, hem kapsam hem zaman boyutunda. Yetki birikimini düzenli denetimle temizle. Yetki sınırlarını birden fazla katmanda bağımsız olarak zorla.
- **Sırları koddan ve versiyon kontrolünden tamamen ayır.** Çalışma zamanında enjekte et, adanmış bir kasada sakla, düzenli döndür, erişimi denetle ve sızıntıyı otomatik tara. Bir sır depoya girdiyse onu ifşa olmuş kabul et ve döndür.
- **Güvenli varsayılanları benimse.** Sistem başarısız olduğunda güvenli tarafa düşmeli (fail secure); yetki, erişim ve maruziyet varsayılan olarak kapalı olmalı, gerektikçe açılmalıdır.
- **Derinlemesine savun.** Tek bir kontrole güvenme; her savunmayı, öncekinin çökeceği varsayımıyla tasarla.

Güvenli kod yazımının özü tek cümlede toplanabilir: **Girdiye güvenme, veriyi koddan ayır, yetkiyi kıs, sırrı sakla — ve her katmanın bir gün delineceğini varsayarak bir sonrakini hazırla.** Bu refleksler bir kez zihniyet hâline geldiğinde, güvenlik ayrı bir "ekstra iş" olmaktan çıkar ve iyi mühendisliğin doğal bir parçası olur.
