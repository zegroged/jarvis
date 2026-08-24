# JWT Saldırıları: alg:none, HS/RS Karışıklığı, Zayıf Secret ve Savunma

## Giriş ve Tanım

JWT (JSON Web Token), taraflar arasında bilgiyi güvenli biçimde taşımak için kullanılan, açık standart (RFC 7519) bir token biçimidir. Modern web uygulamalarında oturum yönetimi, API kimlik doğrulaması (authentication) ve yetkilendirme (authorization) için son derece yaygın olarak kullanılır. Temel çekiciliği stateless olmasıdır: sunucu, oturum bilgisini kendi tarafında bir veritabanında tutmak yerine, imzalı bir token'ın içine gömer ve istemciye verir. İstemci her istekte bu token'ı geri gönderir, sunucu da imzayı doğrulayarak token'a güvenip güvenmeyeceğine karar verir.

Bir JWT üç parçadan oluşur ve bu parçalar nokta (`.`) ile ayrılır:

```
header.payload.signature
```

Her parça Base64URL ile kodlanmıştır. Önemli bir nokta şudur: **Base64URL bir şifreleme (encryption) değildir, yalnızca bir kodlamadır (encoding).** Yani header ve payload'ı herkes çözebilir ve okuyabilir. Token'ın güvenliği içeriğin gizliliğinden değil, **imzanın (signature) bütünlüğünden** gelir. İmza, token'ın üretildikten sonra değiştirilmediğini garanti eder.

Tipik bir header şöyle görünür:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

Buradaki `alg` alanı, imzanın hangi algoritma ile üretildiğini belirtir. İşte JWT saldırılarının büyük çoğunluğu tam olarak bu `alg` alanının etrafında döner. Çünkü doğrulayan taraf, token'a ne kadar körü körüne güvendiğine bağlı olarak burada ciddi hatalar yapabilir.

Bu makalede dört kritik konuya odaklanıyoruz: `alg:none` saldırısı, HS/RS algoritma karışıklığı (algorithm confusion), zayıf secret'a karşı brute-force ve tüm bunlara karşı savunma. Her birinde hem **istismar mantığını** hem de **savunmayı** ele alacağız, çünkü savunmayı gerçekten anlamak için saldırının neden işe yaradığını kavramanız gerekir.

## Simetrik ve Asimetrik İmzalama: Zemin Bilgisi

Saldırıları anlamadan önce iki imzalama ailesini net biçimde ayırmak şart, çünkü karışıklık saldırıları tam da bu ayrımın istismarına dayanır.

**HMAC tabanlı algoritmalar (HS256, HS384, HS512):** Bunlar simetriktir. İmzayı üretmek ve doğrulamak için **aynı** gizli anahtar (secret) kullanılır. Sunucu bir secret bilir; token'ı hem bu secret ile imzalar hem de gelen token'ı yine aynı secret ile doğrular. Buradaki secret bir paroladır ve gizli kalmak zorundadır.

**RSA/ECDSA tabanlı algoritmalar (RS256, ES256 vb.):** Bunlar asimetriktir. Bir anahtar çifti vardır: **private key** (gizli anahtar) ile imzalanır, **public key** (açık anahtar) ile doğrulanır. Private key sunucuda gizli tutulur; public key ise adı üstünde açıktır, dağıtılabilir, hatta çoğu zaman bir `.well-known/jwks.json` endpoint'inden herkese sunulur. Doğrulama tarafının yalnızca public key'e ihtiyacı vardır.

Bu ayrımın kritik sonucu şudur: RS256'da public key'in herkes tarafından bilinmesi tasarım gereğidir ve normalde bir sorun değildir, çünkü public key ile yalnızca doğrulama yapılabilir, imza üretilemez. Ta ki uygulama, algoritma seçimini yanlış yönetip bu public key'i bir HMAC secret'ı gibi kullanana kadar. Buna birazdan geleceğiz.

## alg:none Saldırısı

### Çalışma Mantığı ve Kök Neden

JWT standardı, `alg` alanı için `none` adında özel bir değere izin verir. `none`, "bu token imzasızdır, imza doğrulaması yapılmayacak" anlamına gelir. Standart bunu, imzanın başka bir katmanda (örneğin zaten güvenli bir taşıma kanalında) sağlandığı senaryolar için düşünmüştür. Ancak bu, kimlik doğrulaması yapan bir sistem için felaket bir olasılıktır.

Saldırının kök nedeni şudur: **Doğrulama kütüphanesi, token'ın kendi header'ında yazan `alg` değerine güvenerek hangi doğrulamayı yapacağına karar verirse, saldırgan bu alanı kontrol ettiği için doğrulama mantığını da kontrol eder.** Token'ı gönderen saldırgandır; header'ı da o yazar. Eğer sunucu "header'da `none` yazıyor, o halde imzayı hiç kontrol etmiyorum" derse, saldırgan istediği payload'ı hazırlar, imza kısmını boş bırakır ve token geçerli sayılır.

Buradaki temel tasarım hatası, güvenlik kararının **saldırganın kontrol ettiği veriye** dayandırılmasıdır. Güvenlikte altın kural: doğrulama politikasını asla doğrulanacak nesnenin içine yazdırmayın.

### Somut Örnek

Diyelim ki normal bir token payload'ı şöyle:

```json
{ "sub": "1234", "role": "user" }
```

Saldırgan bu payload'ı `role` alanı `admin` olacak şekilde değiştirir:

```json
{ "sub": "1234", "role": "admin" }
```

Header'ı da şu hâle getirir:

```json
{ "alg": "none", "typ": "JWT" }
```

Ardından token'ı `base64url(header).base64url(payload).` biçiminde oluşturur. Dikkat edin: son noktadan sonra hiçbir şey yoktur, imza kısmı boştur. Bazı kütüphaneler `none` değerinin büyük/küçük harf varyasyonlarını (`None`, `NONE`, `nOnE`) farklı ele aldığından, filtreleri atlatmak için bu varyasyonlar da denenir. Eğer sunucu bu token'ı kabul ederse, saldırgan artık admin olarak oturum açmıştır.

### Savunma

Savunma kavramsal olarak basittir ama disiplin gerektirir:

- **Kabul edilen algoritmaları sunucu tarafında sabitleyin (allowlist).** Doğrulama çağrısına "yalnızca `HS256` kabul et" ya da "yalnızca `RS256` kabul et" biçiminde açık bir liste geçirin. Kütüphanenin token'ın header'ından algoritma çıkarmasına asla izin vermeyin.
- **`none` algoritmasını üretim ortamında kesinlikle devre dışı bırakın.** Kimlik doğrulaması yapan hiçbir akışta imzasız token'a yer yoktur.
- Modern kütüphaneler bu saldırıya karşı büyük ölçüde sertleşmiş olsa da, eski sürümler ve yanlış yapılandırmalar hâlâ risklidir. Kullandığınız kütüphanenin güncel olduğundan ve doğrulama çağrısında beklenen algoritmayı zorunlu kıldığınızdan emin olun.

## HS/RS Algoritma Karışıklığı (Algorithm Confusion)

### Çalışma Mantığı ve Kök Neden

Bu, JWT dünyasının en zarif ve en tehlikeli saldırılarından biridir; adı "algorithm confusion" veya "key confusion" olarak da geçer. Kök nedeni, simetrik (HMAC) ve asimetrik (RSA) algoritmaların doğrulama mantığındaki asimetriyi istismar etmektir.

Senaryoyu düşünün: Uygulama token'larını RS256 ile imzalıyor. Yani private key ile imzalanıyor, public key ile doğrulanıyor. Public key herkese açık; bunu elde etmek zor değil.

Şimdi doğrulama kodunun tipik ama kusurlu bir hâline bakalım. Birçok kütüphanede doğrulama fonksiyonu şu iki argümanı alır: doğrulanacak token ve bir "anahtar". Kusurlu kod, bu anahtar olarak her zaman public key'i verir ve algoritmayı token'ın header'ından okumasına izin verir. İşte kritik nokta:

- Header `RS256` derse, kütüphane public key'i **RSA public key** olarak yorumlar ve RSA doğrulaması yapar. Saldırgan bunu istismar edemez, çünkü imza üretmek için private key gerekir.
- Ama saldırgan header'ı `HS256` yaparsa, kütüphane aynı public key'i bu sefer bir **HMAC secret'ı** olarak yorumlar. Çünkü HS256, verilen anahtar baytlarını simetrik secret olarak kullanır.

İşte tuzak burada kapanır. Public key saldırgan tarafından **zaten bilinen** bir değerdir. Saldırgan, token'ı `HS256` olarak işaretler, payload'ı istediği gibi düzenler ve token'ı **public key'i HMAC secret olarak kullanarak** imzalar. Sunucu token'ı doğrularken elindeki public key ile HMAC hesabı yapar, sonuç tutar ve token'ı geçerli sayar.

Özetle saldırgan, gizli olması gereken imzalama anahtarını hiç bilmeden geçerli imza üretmiştir; çünkü doğrulama tarafı asimetrik bir anahtarı simetrik bir bağlamda kullanmaya kandırılmıştır. Kök neden yine aynıdır: **algoritma seçiminin saldırgana bırakılması** ve anahtar tipinin algoritmaya göre katı biçimde bağlanmaması.

### Somut Örnek (Kavramsal Akış)

1. Saldırgan uygulamanın public key'ini elde eder. Bu genellikle bir JWKS endpoint'inden (`/.well-known/jwks.json`) doğrudan alınır. Eğer public key açıkça sunulmuyorsa, bazı durumlarda ele geçirilen birkaç geçerli RS256 token'ının imzalarından matematiksel olarak türetilmesi bile mümkündür; yani "public key gizli, öyleyse güvendeyiz" varsayımı yanlıştır.
2. Saldırgan header'ı `{"alg":"HS256"}` yapar ve payload'ı istediği gibi (örneğin `role: admin`) değiştirir.
3. Public key'in **tam bayt temsilini** (çoğu zaman PEM formatındaki metnin birebir hâli) HMAC anahtarı olarak alır ve token'ı HS256 ile imzalar. Burada en sık yapılan hata, PEM'in hangi baytlarının secret olarak kullanılacağının yanlış tahmin edilmesidir; saldırının başarısı doğrulama tarafının public key'i tam olarak nasıl yüklediğine bağlıdır ve bu yüzden farklı temsiller (satır sonları dahil/hariç) denenir.
4. Sunucu, public key'i HMAC secret'ı sanarak doğrular ve token geçerli çıkar.

### Savunma

- **Algoritmayı allowlist ile sabitleyin ve anahtar tipiyle eşleştirin.** RS256 kullanıyorsanız doğrulama yalnızca RS256'yı kabul etmelidir. `HS256` header'lı bir token, RS256 bekleyen bir uç noktaya geldiğinde derhal reddedilmelidir.
- **Public key nesnesini asla ham baytlar olarak generic bir "key" argümanına geçirmeyin.** Kütüphaneye "bu bir RSA public key'idir" bilgisini tip düzeyinde verin; böylece kütüphane onu bir HMAC secret olarak asla kullanamaz. Doğru kütüphane API'si, anahtar tipiyle uyumsuz bir algoritma istendiğinde hata fırlatır.
- **Simetrik ve asimetrik anahtarları hiçbir kod yolunda karıştırmayın.** Doğrulama fonksiyonuna geçen anahtarın türü, beklenen algoritma ailesiyle mimari olarak kilitlenmiş olmalıdır.
- Mümkünse imza doğrulaması için tek bir algoritma ailesine bağlı, bunu esnek bırakmayan bir soyutlama kullanın. "Header ne derse ona göre anahtar seç" mantığı bu saldırının ta kendisidir.

## Zayıf Secret (HMAC Brute-Force)

### Çalışma Mantığı ve Kök Neden

Bu saldırı yalnızca HMAC tabanlı algoritmaları (HS256 vb.) hedefler ve son derece pratiktir. Kök neden basittir: HS256'da token'ın güvenliği tamamen secret'ın gizliliğine ve **entropisine** dayanır. Eğer secret zayıfsa, tahmin edilebilir bir kelimeyse ya da kısa bir dizeyse, saldırgan onu offline olarak kırabilir.

Neden offline? Çünkü saldırgan geçerli bir token'ı ele geçirdiğinde (bu token'ı normal bir kullanıcı olarak kendisi de alabilir), elinde `header.payload` ve bunlara karşılık gelen geçerli `signature` vardır. HMAC deterministiktir: aynı girdi ve aynı secret her zaman aynı imzayı üretir. Saldırgan bir secret adayı seçer, `header.payload`'ı bu adayla HMAC'ler ve ürettiği imzayı token'daki gerçek imzayla karşılaştırır. Tutarsa secret bulunmuştur. Bu işlem tamamen saldırganın kendi makinesinde, sunucuya hiç dokunmadan, saniyede milyonlarca deneme hızında yapılabilir. Rate limiting, hesap kilitleme gibi savunmalar burada işe yaramaz, çünkü sunucu sürecin içinde değildir.

Bir secret bulunduğunda oyun biter: saldırgan artık istediği payload'ı üretip geçerli biçimde imzalayabilir, yani istediği kullanıcı ve rolü taklit edebilir.

### Somut Örnek

Zayıf secret'lar gerçek dünyada şaşırtıcı derecede yaygındır: `secret`, `password`, `123456`, uygulamanın adı, bir tutorial'dan kopyalanmış varsayılan değer ya da geliştiricinin aklına gelen kısa bir kelime. Saldırgan tipik olarak şu adımları izler:

1. Herhangi bir yolla geçerli bir HS256 token'ı elde eder.
2. Bu token'ı yaygın bir kırma aracına (örneğin sözlük tabanlı ve kural tabanlı saldırılar yapabilen parola kırma araçlarına, ya da JWT'ye özel yardımcı araçlara) verir.
3. Büyük bir kelime listesi (wordlist) üzerinden dener. Zayıf bir secret çoğu zaman saniyeler içinde düşer.

Buradaki dürüst not: eğer secret gerçekten yüksek entropili ve yeterince uzun rastgele bir değerse (örneğin en az 256 bit rastgelelik), brute-force pratikte imkânsız hâle gelir. Saldırı zayıflığı istismar eder, matematiği değil.

### Savunma

- **Uzun ve yüksek entropili secret kullanın.** HS256 için en az imza algoritmasının çıktı boyutu kadar (256 bit) rastgelelik hedefleyin. Secret'ı bir kriptografik rastgele üretici ile üretin; klavyeden uydurmayın.
- **Secret'ı asla kaynak koda, repoya, örnek dosyalara veya container image'ına gömmeyin.** Bir secret yönetim sistemi ya da en azından ortam değişkeni (environment variable) kullanın ve rotasyonunu planlayın.
- **Mümkünse mimari olarak asimetrik imzalamaya (RS256/ES256) geçin.** Bu durumda doğrulama tarafları yalnızca public key'i bilir; imzalama anahtarı tek bir güvenli yerde kalır. Doğrulayan sistemlerin sayısı arttıkça, herkesin aynı simetrik secret'ı bilmek zorunda olması başlı başına bir risktir; asimetrik yaklaşım bu dağıtım riskini ortadan kaldırır.
- **Varsayılan/örnek secret'ları üretime taşımadığınızı denetleyin.** Bu, sızma testlerinde en sık bulunan hatalardan biridir.

## Diğer Kritik Doğrulama Hataları

alg saldırıları en meşhurları olsa da, gerçek dünyadaki JWT zafiyetlerinin çoğu "imzayı hiç ya da yanlış doğrulama" ekseninde toplanır. Bunları da bilmek savunmanızı bütünler:

- **İmzayı hiç doğrulamamak.** Bazı kütüphanelerde token'ı yalnızca çözüp (decode) içindeki veriyi okumak ile tam doğrulama (verify) yapmak ayrı fonksiyonlardır. Geliştirici yanlışlıkla yalnızca decode eden fonksiyonu çağırırsa, imza hiç kontrol edilmez ve saldırgan payload'ı serbestçe değiştirebilir. Bu, `alg:none` kadar tehlikeli ama daha sinsi bir hatadır.
- **`kid` (Key ID) enjeksiyonu.** Header'daki `kid` alanı, doğru anahtarı seçmek için kullanılır. Eğer uygulama bu alanı doğrudan bir dosya yoluna, veritabanı sorgusuna ya da komuta güvensizce koyarsa, path traversal, SQL injection veya komut enjeksiyonu gibi ikincil zafiyetler doğar. Örneğin `kid` ile saldırgan sunucuyu tahmin edilebilir bir dosyayı (ya da kendisinin yüklediği içeriği) anahtar olarak kullanmaya zorlayabilir.
- **`jku`/`x5u` ile anahtar kaynağını dışarı taşıma.** Bazı header alanları, doğrulama anahtarının nereden çekileceğini gösteren bir URL içerir. Uygulama bu URL'ye körü körüne güvenirse, saldırgan kendi kontrolündeki bir sunucuyu göstererek kendi anahtarıyla imzaladığı token'ı doğrulatabilir. Bu URL'lerin mutlaka katı bir allowlist ile sınırlanması gerekir.
- **Standart claim'leri doğrulamamak.** `exp` (son kullanma), `nbf` (bu tarihten önce geçersiz), `iss` (issuer) ve `aud` (audience) alanlarının kontrol edilmemesi ayrı bir risktir. `exp` doğrulanmazsa süresi dolmuş token'lar sonsuza dek geçerli kalır. `aud` doğrulanmazsa, bir servis için üretilmiş token başka bir serviste kabul edilebilir (token'ın yanlış yerde geçerli olması sorunu).

## Yaygın Hatalar

Buraya kadarki her bölüm bir hatayı zaten içeriyordu; şimdi bunları bir savunmacının kontrol listesi gibi toplayalım:

- **Algoritmayı token'ın header'ından okumak.** Tüm alg saldırılarının ortak kök nedeni budur. Politikayı saldırganın verisine bırakmayın.
- **`verify` yerine yanlışlıkla `decode` çağırmak.** İmza hiç kontrol edilmez.
- **Public key'i ham baytlar olarak generic anahtar argümanına vermek.** HS/RS karışıklığının kapısını açar.
- **Kısa, tahmin edilebilir veya varsayılan HMAC secret'ı kullanmak.** Offline brute-force ile kırılır.
- **`exp`, `aud`, `iss` gibi claim'leri doğrulamamak.** İmza doğru olsa bile token yanlış bağlamda ya da süresi dolmuş hâlde kabul edilir.
- **Hassas veriyi payload'a koymak.** JWT payload'ı okunabilir; parola, tam kredi kartı numarası gibi verileri buraya koymak gizliliği ihlal eder.
- **Uzun ömürlü token ve iptal (revocation) mekanizması olmaması.** Stateless JWT'nin doğası gereği, üretilmiş bir token'ı geri çağırmak zordur. Uzun `exp` süreleri, çalınan bir token'ın uzun süre kullanılabilir kalması demektir.
- **Eski/güncellenmemiş kütüphane kullanmak.** `alg:none` gibi bilinen zafiyetlere karşı sertleştirmeler kütüphane güncellemeleriyle gelir.

## En İyi Pratikler

Sağlam bir JWT doğrulama stratejisi için özet reçete:

1. **Algoritmayı sunucuda sabitleyin.** Doğrulama çağrısına açık bir allowlist geçirin (`{ algorithms: ['RS256'] }` gibi). Header'a asla güvenmeyin. `none`'ı üretimde tamamen kapatın.
2. **Anahtar tipini algoritmaya kilitleyin.** Asimetrik doğrulamada anahtarı, kütüphanenin HMAC secret'ı olarak yorumlayamayacağı bir tipli nesne olarak verin. Simetrik ve asimetrik yolları kod düzeyinde karıştırmayın.
3. **Mümkünse asimetrik imzalama seçin (RS256/ES256).** İmzalama sırrını tek bir güvenli yerde tutar, doğrulayanlara yalnızca public key dağıtır ve simetrik secret paylaşımı riskini ortadan kaldırır.
4. **HMAC kullanacaksanız secret'ı güçlü tutun.** En az 256 bit rastgelelik, kriptografik üreticiyle üretilmiş, kod dışında saklanmış ve rotasyonu planlanmış.
5. **Tüm standart claim'leri doğrulayın.** `exp`, `nbf`, `iss`, `aud` kontrol edilmeli; ayrıca zaman kayması (clock skew) için makul bir tolerans belirlenmeli.
6. **`kid`, `jku`, `x5u` gibi header kaynaklı yönlendirmeleri güvensiz veri olarak ele alın.** `kid`'i sorgu/dosya yoluna sokmayın; harici anahtar URL'lerini katı allowlist ile sınırlayın.
7. **Token ömrünü kısa tutun ve yenileme (refresh token) mekanizması kurun.** Kısa ömürlü access token + güvenli refresh akışı, çalınan token'ın etki penceresini daraltır. Kritik sistemlerde bir revocation/deny-list stratejisi ekleyin.
8. **Hassas veriyi payload'a koymayın.** Payload gizli değildir; yalnızca gizli olması gerekmeyen kimlik ve yetki bilgilerini taşıyın.
9. **Kütüphaneleri güncel tutun ve doğrulama kodunu düzenli denetleyin.** Güvenlik, bir kez yazılıp unutulan değil, sürdürülen bir şeydir.

## Sonuç

JWT saldırılarının neredeyse tamamı tek bir ilkeye indirgenebilir: **doğrulayan taraf, güvenlik kararını saldırganın kontrol ettiği veriye dayandırdığında zafiyet doğar.** `alg:none`, algoritma seçiminin header'a bırakılmasıdır. HS/RS karışıklığı, anahtar tipinin algoritmaya sıkıca bağlanmamasıdır. Zayıf secret, gizliliğin entropisiz bir değere emanet edilmesidir. Üçü de aynı disiplinle çözülür: algoritmayı ve anahtar tipini sunucuda katı biçimde belirle, secret'ı güçlü tut, imzayı gerçekten doğrula ve tüm claim'leri kontrol et. JWT güçlü bir araçtır; tehlike token'ın kendisinde değil, ona nasıl güvendiğinizdedir.
