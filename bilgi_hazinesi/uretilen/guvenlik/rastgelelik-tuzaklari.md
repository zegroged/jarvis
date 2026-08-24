# Kriptografide Rastgelelik Tuzakları

## Giriş: Kriptografinin Sessiz Temeli

Modern kriptografinin neredeyse tamamı, tahmin edilemez sayılar üretebilme yeteneğinin üzerine kuruludur. Bir şifreleme anahtarı, bir oturum belirteci (session token), bir başlatma vektörü (IV), bir nonce, bir tuz (salt) değeri, bir CSRF belirteci, bir parola sıfırlama bağlantısı; bunların hepsi ortak bir varsayıma dayanır: saldırganın bu değeri makul bir çabayla tahmin edememesi. Bu varsayım çöktüğü anda, üzerine inşa edilen tüm kriptografik yapı, matematiksel olarak ne kadar sağlam olursa olsun, anlamsız hâle gelir.

İşin acı tarafı şudur: rastgelelik hataları, kodda "çalışıyor" gibi görünür. Program çalışır, testler geçer, belirteçler üretilir, şifreleme tamamlanır. Hiçbir istisna (exception) fırlatılmaz, hiçbir uyarı çıkmaz. Zayıf rastgelelik, kendini işlevsel bir hata olarak değil, yalnızca güvenlik açığı olarak gösterir; ve bu açık çoğu zaman ancak birileri onu istismar ettiğinde fark edilir. Bu yüzden rastgelelik tuzakları, en tehlikeli ve en sık gözden kaçan kriptografik zafiyet sınıflarından biridir.

Bu makalede üç merkezî tuzağı derinlemesine ele alacağız: kriptografik olmayan rastgele sayı üreticilerinin (`rand()` ve benzerleri) yanlış kullanımı, tahmin edilebilir belirteç üretimi ve nonce/IV tekrarı. Her biri için önce mekanizmayı, sonra kök nedeni, ardından hem istismar hem de savunma mantığını inceleyeceğiz.

## Temel Kavram: PRNG, CSPRNG ve Entropi

Herhangi bir tartışmaya girmeden önce zemini netleştirelim.

Bir **PRNG** (Pseudo-Random Number Generator, sözde rastgele sayı üreticisi), bir başlangıç değerinden (seed) yola çıkarak deterministik bir algoritmayla rastgele *görünen* bir sayı dizisi üretir. Buradaki kritik kelime "deterministik"tir: aynı seed, her zaman aynı diziyi üretir. Bu üreticiler istatistiksel olarak düzgün dağılım sağlar, hızlıdır ve simülasyon, oyun, örnekleme gibi işler için mükemmeldir. Ama bir amaçları yoktur: *tahmin edilemez* olmak.

Bir **CSPRNG** (Cryptographically Secure PRNG, kriptografik olarak güvenli sözde rastgele sayı üreticisi) ise ek bir garanti sunar. Bir saldırgan ürettiğiniz çıktının bir bölümünü görse bile, ne gelecekteki ne de geçmişteki çıktıları hesaplanabilir bir maliyetle tahmin edemez. Buna sırasıyla "next-bit unpredictability" (sonraki bit tahmin edilemezliği) ve "backtracking resistance" (geriye gitme direnci) denir. CSPRNG, işletim sisteminin entropi havuzundan (donanım gürültüsü, kesme zamanlamaları, kullanıcı girdileri gibi öngörülemez kaynaklardan toplanan gerçek rastgelelik) beslenir.

**Entropi**, bir değerin içinde barındırdığı gerçek belirsizlik miktarıdır; bit cinsinden ölçülür. 128 bit entropi, saldırganın ortalama 2^127 deneme yapması gerektiği anlamına gelir ki bu bugünkü ve öngörülebilir gelecekteki hesaplama gücüyle erişilemez. Kriptografik anlamda "yeterince rastgele" olmak, aslında "yeterince entropiye sahip olmak" demektir.

Buradaki temel ayrım şudur: PRNG istatistiksel rastgelelik sağlar, CSPRNG ise kriptografik tahmin edilemezlik sağlar. İkisi farklı problemleri çözer ve birini diğerinin yerine kullanmak, tuzağın ta kendisidir.

## Birinci Tuzak: CSPRNG Yerine rand() Kullanımı

### Mekanizma ve Kök Neden

Neredeyse her programlama dili, kolay erişilebilen genel amaçlı bir rastgele sayı fonksiyonu sunar: C'de `rand()`, Python'da `random` modülü, Java'da `java.util.Random`, JavaScript'te `Math.random()`, PHP'de eski `mt_rand()`/`rand()`. Bu fonksiyonlar hızlı, taşınabilir ve dokümantasyonun ilk sayfasında karşınıza çıkar. Tam da bu erişilebilirlik, onları tehlikeli yapar: geliştirici "rastgele bir sayı lazım" diye düşünür, en görünür aracı alır ve güvenlik açığını farkında olmadan koda gömer.

Kök neden, bu üreticilerin *tasarım gereği* öngörülebilir olmasıdır. Klasik `rand()` implementasyonlarının çoğu, doğrusal eşlenik üreteç (LCG, Linear Congruential Generator) gibi basit yinelemeli formüllere dayanır: bir sonraki değer, bir öncekinden birkaç çarpma ve toplama işlemiyle üretilir. Python'un `random` modülü ise Mersenne Twister algoritmasını kullanır; istatistiksel olarak çok kaliteli, ama kriptografik olarak kırılabilir bir üreteçtir.

Sorun iki katmanlıdır:

**İç durumun geri çıkarılabilmesi.** Mersenne Twister için, art arda üretilmiş yeterli sayıda çıktıyı gözlemleyen bir saldırgan, üreticinin iç durumunu (state) tamamen yeniden kurabilir ve o noktadan sonraki tüm çıktıları birebir tahmin edebilir. LCG için ise genellikle bir avuç çıktı bile iç durumu çözmeye yeter. Bu teorik bir tehdit değildir; bunu yapan hazır araçlar mevcuttur.

**Seed'in zayıflığı.** Çoğu kod, üreticiyi geçerli zamanla (`time()` gibi) tohumlar. Zaman, saldırganın büyük ölçüde bildiği bir değerdir. Belirtecin oluşturulma anını saniye hassasiyetinde tahmin edebilen bir saldırgan, olası seed'lerin sayısını dakikalar içinde deneyecek kadar küçük bir kümeye indirir. Seed uzayı 32 bit ise, bu zaten baştan kaybedilmiş bir savaştır: 2^32 olasılık, modern donanımda saniyeler-dakikalar meselesidir.

### Somut Örnek ve İstismar Mantığı

Şöyle bir sözde-kod düşünelim:

```
srand(time(NULL));
token = "";
for (i = 0; i < 16; i++)
    token += hex(rand() % 16);
```

Bu kod, kullanıcı oturum belirteci üretiyor olsun. Saldırganın istismar akışı şu şekilde ilerler: Önce kendisi için bir hesap açar ve kendi belirtecini alır. Belirtecin üretildiği anın Unix zamanını, sunucunun yanıt başlıklarındaki `Date` alanından saniye hassasiyetinde bilir. Şimdi bu zamanın etrafındaki birkaç saniyelik pencereyi tek tek seed olarak deneyerek aynı `rand()` dizisini yeniden üretir, kendi belirtecinin çıktısıyla eşleşen seed'i bulur. O seed'i bulduğu an, üreticinin iç durumunu ele geçirmiş olur. Artık *diğer* kullanıcılara üretilen belirteçleri, üretim anlarını tahmin ederek yeniden hesaplayabilir. Oturum ele geçirme (session hijacking) buradan doğar.

`Math.random()` özelinde durum daha da vahimdir çünkü çıktı tarayıcı tarafında, yani saldırganın tam kontrolündeki bir ortamda üretilir. Araştırmacılar, art arda gözlemlenen `Math.random()` çıktılarından motorun iç durumunu geri çıkarıp sonraki değerleri tahmin etmenin pratik yollarını göstermiştir. Kısacası: istemci tarafında `Math.random()` ile üretilen hiçbir belirteç güvenli sayılamaz.

### Savunma Mantığı

Savunma kavramsal olarak basit ama disiplinli olmayı gerektirir: **güvenlik gerektiren her rastgele değer için işletim sisteminin CSPRNG'sini kullanın.** Doğru araçlar dilden dile şöyle konumlanır:

- Linux/Unix'te temel kaynak `/dev/urandom` veya `getrandom` sistem çağrısıdır.
- Python'da `secrets` modülü (`secrets.token_bytes`, `secrets.token_hex`, `secrets.token_urlsafe`) ve düşük seviyede `os.urandom`.
- Java'da `java.security.SecureRandom`.
- JavaScript'te tarayıcıda `crypto.getRandomValues`, Node.js'te `crypto.randomBytes`.
- C/C++'ta doğrudan `getrandom`/`/dev/urandom` veya kütüphanenin sağladığı kriptografik üreteç.

Ayrım şu prensipte özetlenir: eğer üretilen değerin tahmin edilebilmesi bir güvenlik sonucu doğuruyorsa, mutlaka CSPRNG kullanın. Bir oyunun zar atışında `rand()` gayet uygundur; bir parola sıfırlama belirtecinde felakettir. Karar kriteri hızın değil, tahmin edilebilirliğin sonucudur.

Ek bir savunma katmanı olarak, kod inceleme (code review) ve statik analiz süreçlerinde `Math.random`, `java.util.Random`, çıplak `rand()` gibi çağrıların güvenlik bağlamlarında kullanımını otomatik olarak işaretlemek çok değerlidir. İnsanlar bu hatayı tekrar tekrar yapar; araçla yakalamak, iyi niyete güvenmekten daha etkilidir.

## İkinci Tuzak: Tahmin Edilebilir Belirteçler (Token)

### Mekanizma ve Kök Neden

Zayıf bir üreticiyi düzeltseniz bile, belirteç üretiminin kendisinde başka tuzaklar gizlidir. Tahmin edilebilir belirteç sorunu, sadece "hangi üreticiyi kullandım" değil, "belirteci neyden türettim ve içinde ne kadar gerçek entropi var" sorusuyla ilgilidir.

En yaygın kök nedenler şunlardır:

**Anlamlı verilerden türetme.** Belirteci; kullanıcı kimliği, e-posta, kayıt zamanı, artan bir sayaç ya da bunların bir kombinasyonundan üretmek. Örneğin `token = md5(user_id + timestamp)` gibi bir yaklaşım son derece yaygındır ve son derece zayıftır. Buradaki yanılgı, `md5` veya `sha256` gibi bir hash fonksiyonunun çıktıyı "rastgele gösterdiği" için güvenli sandığımızdır. Oysa hash geri döndürülemez olabilir ama **girdi tahmin edilebilirse çıktı da tahmin edilebilirdir.** Saldırgan girdiyi (kullanıcı kimliği zaten belli, zaman damgası tahmin edilebilir) deneyerek aynı hash'i yeniden üretir. Hash burada hiçbir entropi *eklemez*; sadece var olan entropiyi karıştırır.

**Yetersiz uzunluk / entropi.** Belirteç doğru üreticiden gelse bile, çok kısaysa kaba kuvvetle (brute force) taranabilir. 32 bitlik bir belirteç modern koşullarda güvenli değildir. Pratik kural, güvenlik açısından kritik belirteçlerin en az 128 bit entropi taşımasıdır.

**Sıralı veya öngörülebilir yapı.** Artan kimlikler, tahmin edilebilir örüntüler ya da belirteçler arasında görünür ilişki bırakmak. Bir kullanıcı `...a3f0` alıyor, diğeri `...a3f1` alıyorsa, orada rastgelelik yok demektir.

### Somut Örnek ve İstismar Mantığı

Parola sıfırlama akışını ele alalım; bu, tahmin edilebilir belirtecin klasik istismar alanıdır. Bir uygulama, "şifremi unuttum" isteğinde kullanıcıya `https://site/reset?token=XYZ` biçiminde bir bağlantı gönderiyor olsun. Bu belirteç `sha1(email + gununTarihi)` gibi bir formülle üretiliyorsa, saldırganın kurbanın e-postasını bilmesi (çoğu zaman zaten bilinir) ve tarihi bilmesi (bugündür) yeterlidir. Saldırgan kendi tarafında aynı belirteci hesaplar, sıfırlama bağlantısını kendisi ziyaret eder ve kurbanın parolasını değiştirir. Hesap tamamen ele geçirilmiştir; üstelik kurbana hiçbir e-posta ulaşmadan.

Bir başka klasik örnek, "insecure direct object" mantığıyla birleşen tahmin edilebilir belirteçlerdir: davetiye bağlantıları, dosya paylaşım linkleri, fatura numaraları sıralı üretiliyorsa, saldırgan basitçe sayacı artırarak başkalarına ait kaynakları toplu hâlde çeker (enumeration). Burada üretici "yeterince rastgele" olmadığı için değil, belirteç *sıralı olduğu için* zafiyet doğar.

### Savunma Mantığı

Doğru belirteç üretiminin üç ilkesi vardır:

**Entropiyi veriden değil, CSPRNG'den alın.** Belirteç, anlamlı hiçbir girdiye bağlı olmamalı; doğrudan kriptografik üreticinin ürettiği ham rastgele baytlardan oluşmalıdır. `secrets.token_urlsafe` benzeri fonksiyonlar tam olarak bunu yapar: yeterli sayıda rastgele bayt üretip URL-güvenli biçimde kodlar.

**Yeterli uzunluk verin.** Güvenlik açısından kritik belirteçler için en az 128 bit, tercihen 256 bit entropi hedeflenmelidir. Baytların çıktı kodlaması (hex, base64url) entropiyi artırmaz; entropiyi belirleyen ham bayt sayısıdır. 16 rastgele bayt = 128 bit; bu, hex olarak 32 karakter, base64url olarak yaklaşık 22 karakter eder.

**Belirtece bağlam ve ömür ekleyin.** Rastgelelik gerekli ama tek başına yeterli değildir. Sıfırlama belirteçleri kısa ömürlü olmalı (tek kullanımlık ve dakikalar içinde geçersizleşen), sunucu tarafında saklanan bir karşılıkla eşleştirilmeli ve karşılaştırma sabit zamanlı (constant-time) yapılmalıdır. Sabit zamanlı karşılaştırma, zamanlama saldırılarıyla (timing attack) belirtecin bayt bayt çözülmesini engeller: karşılaştırmayı ilk uyuşmayan baytta kesen naif bir eşitlik kontrolü, doğru tahmin edilen her ön ekte mikroskobik zamanlama farkı sızdırır.

Özetle doğru zihniyet şudur: **belirteç bir "sır"dır, bir "kimlik" değil.** İçinde anlam taşımamalı; sadece tahmin edilemez olmalıdır.

## Üçüncü Tuzak: Nonce ve IV Tekrarı

### Mekanizma ve Kök Neden

Bu tuzak, rastgeleliği doğru üreten deneyimli geliştiricileri bile yakalar, çünkü sorun üreticide değil, kullanım kuralındadır. Birçok kriptografik yapı, girdiler arasında **benzersizlik** ya da **tazelik** garantisi gerektirir. Bu garantiyi sağlayan değere bağlama göre nonce (number used once, bir kez kullanılan sayı) ya da IV (initialization vector, başlatma vektörü) denir.

Kritik nokta: bu değerlerin bazı bağlamlarda gizli olması gerekmez, ama **asla tekrar etmemesi** gerekir. Ve "asla tekrar etmemek", tasarlanması sanıldığından çok daha zor bir özelliktir.

Kök neden, farklı algoritmaların nonce tekrarına karşı çok farklı hassasiyetler göstermesidir:

**Akış şifreleri ve sayaç (CTR) benzeri modlar.** AES-CTR, ChaCha20 gibi yapılar, nonce'tan bir anahtar akışı (keystream) üretir ve düz metni bu akışla XOR'lar. Aynı anahtar ve aynı nonce ile iki farklı mesaj şifrelenirse, aynı anahtar akışı üretilir. İki şifreli metni birbiriyle XOR'layan saldırgan, anahtarı hiç bilmeden iki düz metnin XOR'unu elde eder. Bu, "many-time pad" olarak bilinen klasik felakettir ve bilinen düz metin parçaları ya da dil istatistikleriyle mesajlar okunabilir hâle gelir.

**GCM gibi kimlik doğrulamalı modlar.** AES-GCM'de nonce tekrarı çok daha yıkıcıdır. Nonce'un aynı anahtarla tekrar kullanılması yalnızca gizliliği bozmakla kalmaz; GCM'in kimlik doğrulama katmanının dayandığı gizli değeri (kimlik doğrulama anahtarını) açığa çıkarma yolunu açar. Bu, saldırganın kendi sahte mesajları için geçerli kimlik doğrulama etiketleri (authentication tag) üretebilmesine, yani mesaj bütünlüğünü (integrity) tamamen aşmasına imkân verir. GCM için nonce tekrarı, "gizlilik zayıfladı" değil, "bütünlük çöktü" seviyesinde bir olaydır.

**CBC modunda IV.** CBC için IV'nin gizli olması gerekmez ama öngörülemez olması gerekir. Öngörülebilir IV kullanımı, seçilmiş düz metin saldırıları (chosen-plaintext attack) için kapı aralar; tarihsel olarak TLS'teki bir dizi zafiyetin kökeni tam da buydu.

### Nonce Tekrarı Neden Bu Kadar Sık Oluşur?

Nonce tekrarının pratik sebepleri öğreticidir, çünkü hepsi "makul görünen" mühendislik kararlarıdır:

**Sabit veya sıfır nonce.** Geliştirici basitlik için nonce'u sabit bir değere ya da tamamen sıfıra ayarlar. Kod çalışır, testler geçer, ama her mesaj aynı nonce'u kullanır.

**Sayaç durumunun kaybı.** Nonce bir sayaçla üretiliyorsa ve sistem yeniden başlar, bir yedekten (backup/snapshot) geri yüklenir ya da aynı anahtar birden fazla makineye kopyalanırsa, sayaç sıfırdan başlayarak daha önce kullanılmış nonce'ları yeniden üretir. Sanallaştırma ve konteyner ortamlarında bir sanal makine görüntüsünün (VM snapshot) geri yüklenmesi bu problemin klasik tetikleyicisidir.

**Rastgele nonce ve doğum günü problemi (birthday problem).** Nonce rastgele seçiliyorsa, tekrar olasılığı üretilen mesaj sayısının karesiyle orantılı olarak büyür. GCM'in 96 bitlik nonce'u için, aynı anahtarla çok büyük sayıda mesaj şifrelendiğinde tekrar (collision) ihtimali ihmal edilemez hâle gelir. Bu, sonsuza kadar aynı anahtarla rastgele nonce üretmenin neden güvenli olmadığını açıklar.

### İstismar ve Savunma Mantığı

İstismar tarafı yukarıda anlatıldı: XOR ile düz metin sızıntısı (CTR/akış), kimlik doğrulama anahtarının açığa çıkması (GCM), seçilmiş düz metin (öngörülebilir CBC IV). Savunma tarafında birkaç sağlam ilke vardır:

**Anahtar–nonce çiftini asla tekrarlamayın.** Kural budur ve pazarlıksızdır. Bunu sağlamanın en güvenilir yollarından biri, nonce'u güvenilir, kalıcı ve monoton artan bir sayaçtan üretmektir; ama bu sayaç durumunun geri yüklemelere ve çoklu yazarlara (multiple writers) karşı gerçekten güvenli tutulması şartıyla. Sayaç durumunu güvenle yönetemiyorsanız, bu yaklaşım rastgele nonce'tan daha tehlikeli olabilir.

**Anahtar başına mesaj sayısını sınırlayın ve anahtarları döndürün (key rotation).** Rastgele nonce kullanıyorsanız, doğum günü sınırına yaklaşmadan çok önce anahtarı yenileyin. Anahtar rotasyonu, tek bir anahtar altında biriken nonce sayısını düşük tutarak tekrar riskini yönetilebilir kılar.

**Nonce yanlış kullanımına dayanıklı (nonce-misuse resistant) modları tercih edin.** AES-GCM-SIV gibi tasarımlar, nonce yanlışlıkla tekrar etse bile felaketi sınırlamak üzere tasarlanmıştır: tekrarlanan nonce yalnızca "aynı düz metin aynı şifreli metni üretti" bilgisini sızdırır, kimlik doğrulama anahtarını açığa çıkarmaz. Nonce yönetiminden emin olamadığınız sistemlerde bu modlar önemli bir emniyet ağıdır.

**Doğrulanmış, üst düzey kütüphaneler kullanın.** Bu belki de en pratik tavsiyedir. `libsodium` gibi kütüphaneler ya da "authenticated encryption" için tek çağrılık, nonce yönetimini içeride halleden API'ler, geliştiriciyi tehlikeli düşük seviye kararlardan uzak tutar. Kendi başınıza AES-GCM'i çıplak primitiflerle kurmaya çalışmak, tam da nonce tuzağına düşmenin en olası yoludur.

## Yaygın Hatalar: Bir Kontrol Listesi

Aşağıdaki hatalar, gerçek dünyada tekrar tekrar karşımıza çıkar:

- Güvenlik bağlamında `rand()`, `Math.random()`, `java.util.Random` veya benzeri kriptografik olmayan üreticileri kullanmak.
- Üreticiyi `time()` gibi tahmin edilebilir bir değerle tohumlamak (seeding).
- Bir hash fonksiyonunun (md5, sha256) çıktısını "rastgele göründüğü" için güvenli sanmak; tahmin edilebilir girdinin tahmin edilebilir çıktı verdiğini unutmak.
- Belirteçleri kullanıcı kimliği, e-posta, zaman damgası gibi anlamlı verilerden türetmek.
- Yetersiz belirteç uzunluğu; 128 bitin altına düşmek.
- Belirteç karşılaştırmasını sabit zamanlı yapmamak ve zamanlama saldırısına açık bırakmak.
- Aynı anahtarla nonce/IV tekrar etmek; özellikle sabit veya sıfır nonce kullanmak.
- Sayaç tabanlı nonce durumunun yeniden başlatma, yedekten dönme veya VM snapshot ile sıfırlanabileceğini hesaba katmamak.
- Rastgele nonce ile sınırsız sayıda mesaj şifreleyerek doğum günü çakışmasını görmezden gelmek.
- CBC için öngörülebilir IV kullanmak.
- Kendi kriptografik primitiflerinizi düşük seviyede birleştirerek "roll your own crypto" yapmak.
- Konteyner ve bulut ortamlarında entropi havuzunun başlangıçta yetersiz dolduğu (boot-time entropy starvation) durumu göz ardı etmek; bu, erken üretilen anahtarların zayıf olmasına yol açabilir.

## En İyi Pratikler

Tüm bu analizin damıtılmış hâli birkaç sağlam prensipte toplanır.

**Varsayılan olarak CSPRNG kullanın.** Tahmin edilebilirliğin bir güvenlik sonucu doğurabileceği her yerde, işletim sisteminin kriptografik üreticisine dayanan yüksek seviye API'leri seçin: Python'da `secrets`, Java'da `SecureRandom`, tarayıcıda `crypto.getRandomValues`, Node'da `crypto.randomBytes`. Hangi üreticinin güvenli olduğundan emin değilseniz, dilin dokümantasyonunda "cryptographically secure" ifadesini açıkça arayın.

**Entropiyi anlamdan ayırın.** Bir sır, tahmin edilemezliğini içindeki anlamdan değil, içindeki gerçek rastgelelikten almalıdır. Belirteçlere iş verisi gömmeyin; ham rastgele bayt üretip gerekiyorsa bağlamı ayrı, sunucu tarafında saklanan bir eşlemeyle ilişkilendirin.

**Yeterli uzunlukta olun ve fazlasını verin.** 128 bit alt sınırdır; ekstra baytların maliyeti ihmal edilebilirken güvenlik payı değerlidir. Entropiyi belirleyenin ham bayt sayısı olduğunu, kodlamanın (hex/base64) entropi eklemediğini unutmayın.

**Nonce/IV benzersizliğini bir tasarım gereksinimi olarak ele alın.** "Muhtemelen tekrar etmez" yeterli değildir. Anahtar–nonce çiftinin tekrarını mimari düzeyde imkânsız kılın; emin olamıyorsanız nonce-misuse dirençli modları ve anahtar rotasyonunu benimseyin.

**Kendi kriptonuzu yazmayın.** Doğrulanmış, bakımı yapılan, topluluk incelemesinden geçmiş kütüphaneleri (`libsodium` ve benzerleri) kullanın. Bu kütüphaneler tam olarak bu makaledeki tuzakları yıllarca yaşayarak öğrenmiş ve güvenli varsayılanlar içine gömmüştür.

**Zayıf rastgeleliği araçla yakalayın.** Kod inceleme, statik analiz ve linter kurallarıyla tehlikeli üreticilerin ve tahmin edilebilir belirteç desenlerinin kullanımını otomatik olarak işaretleyin. İnsan dikkati güvenilmez; otomasyon tekrarlanabilir.

**Entropi kaynağının sağlığını düşünün.** Özellikle konteyner, sanal makine ve gömülü sistemlerde, sistemin açılış anında yeterli entropiye sahip olduğundan emin olun; erken üretilen kriptografik malzemenin zayıf olma riskini göz önünde bulundurun.

## Sonuç

Kriptografide rastgelelik, gözle görülmeyen ama her şeyi taşıyan bir temeldir. Bu makaledeki üç tuzağın ortak dersi şudur: rastgelelik hataları sessizdir. Kod çalışır, hiçbir alarm çalmaz ve zafiyet ancak birileri onu istismar ettiğinde görünür olur. Bu yüzden rastgelelikte "işe yarıyor gibi görünmek" hiçbir şey ifade etmez; önemli olan, tahmin edilemezliğin matematiksel olarak garanti altına alınmasıdır.

Üç ilkeyi aklınızda tutun: güvenlik gerektiren her yerde CSPRNG kullanın, belirteçlerin entropisini anlamdan değil rastgelelikten alın, ve anahtar–nonce çiftini asla tekrarlamayın. Bu üç kural, pratikte karşılaşacağınız rastgelelik tuzaklarının büyük çoğunluğunu ortadan kaldırır. Geri kalanı için de altın kural değişmez: kendi kriptonuzu yazmak yerine, bu dersleri sizin için çoktan öğrenmiş kütüphanelere güvenin.
