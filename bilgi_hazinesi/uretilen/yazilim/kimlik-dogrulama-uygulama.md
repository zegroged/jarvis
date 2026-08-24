# Kimlik Doğrulama Uygulaması: Session, Token, Güvenli Cookie, MFA ve Güvenli Akış

## Giriş ve Kapsam

Kimlik doğrulama (authentication), bir isteğin arkasındaki varlığın (kullanıcı, servis veya cihaz) gerçekten iddia ettiği kişi olduğunu doğrulama sürecidir. Bunu yetkilendirmeden (authorization) ayırmak gerekir: authentication "sen kimsin?" sorusuna, authorization ise "senin buna hakkın var mı?" sorusuna cevap verir. Bu makale, modern bir web/mobil uygulamada oturum yönetiminin iki temel yaklaşımı olan **session tabanlı** ve **token tabanlı** doğrulamayı, bunların üzerinde durduğu **güvenli cookie** mekaniklerini, **çok faktörlü kimlik doğrulamayı (MFA)** ve baştan sona **güvenli bir doğrulama akışını** derinlemesine ele alır.

Temel mesele şudur: HTTP protokolü doğası gereği **stateless**'tir. Yani sunucu, iki ardışık isteğin aynı kullanıcıdan geldiğini kendiliğinden bilmez. Kullanıcı bir kez şifresini girdikten sonra, her istekte tekrar şifre sormadan onu tanımaya devam etmemiz gerekir. İşte session ve token, bu "hatırlama" problemine iki farklı mühendislik cevabıdır.

## Kök Sorun: Neden Oturum Yönetimine İhtiyaç Var?

Her HTTP isteğinin bağımsız olması, ölçeklenebilirlik açısından harika bir tasarım tercihidir; ama kullanıcı deneyimi açısından bir boşluk yaratır. Kullanıcı `/login` uç noktasına şifresini gönderip doğrulandıktan sonra, `/hesabim` sayfasına gittiğinde sunucu bu iki isteği ilişkilendirebilmelidir. Ham şifreyi her istekte tekrar tekrar taşımak felaket bir fikirdir: şifre ne kadar çok yerde dolaşırsa, sızma yüzeyi (attack surface) o kadar büyür ve tek bir sızıntıda kalıcı kimlik bilgisi ele geçirilir.

Çözüm, doğrulamadan sonra kısa ömürlü, iptal edilebilir bir **kimlik kanıtı** (proof of authentication) üretmektir. Bu kanıt her istekte taşınır ve şifrenin yerine geçer. Bu kanıtın nasıl saklandığı ve doğrulandığı, session ile token yaklaşımlarını birbirinden ayıran şeydir.

## Session Tabanlı Kimlik Doğrulama

### Tanım ve Çalışma Mantığı

Session tabanlı yaklaşımda, kullanıcı doğrulandıktan sonra sunucu tarafında bir **oturum kaydı** oluşturulur. Bu kayıt, sunucunun belleğinde, bir Redis örneğinde veya bir veritabanında tutulur ve genellikle şu bilgileri içerir: kullanıcı kimliği, oluşturulma zamanı, son etkinlik zamanı, IP/cihaz parmak izi gibi meta veriler. Sunucu bu kayda karşılık gelen, tahmin edilemez ve yüksek entropili bir **session ID** üretir (örneğin 128 bit veya daha fazla rastgele veri).

Bu session ID istemciye bir cookie olarak gönderilir. İstemci sonraki her istekte bu cookie'yi otomatik olarak taşır; sunucu ID'yi alır, oturum deposunda arar, kaydı bulursa kullanıcıyı tanır.

### Neden Böyle Çalışıyor?

Buradaki kritik nokta şudur: **anlamlı bilginin tamamı sunucudadır, istemcide yalnızca anlamsız bir referans (opaque token) vardır.** Session ID'nin kendisi hiçbir şey ifade etmez; sadece sunucudaki bir kayda işaret eden bir anahtardır. Bu tasarımın en büyük gücü **anlık iptal edilebilirliktir**: bir oturumu sonlandırmak istediğinizde, sunucudaki kaydı silmeniz yeterlidir. Bir sonraki istek geldiğinde ID artık bir kayda karşılık gelmez ve kullanıcı reddedilir. Kullanıcı "tüm cihazlardan çıkış yap" dediğinde ya da bir güvenlik ihlali sonrası tüm oturumları anında geçersiz kılmak istediğinizde, bu yetenek paha biçilmezdir.

### Tuzaklar ve Maliyet

Bunun bedeli **durum tutma (statefulness)** yükümlülüğüdür. Her istekte oturum deposuna bir okuma yapılır; bu, yatay ölçeklemede (birden çok sunucu örneği) oturum deposunun paylaşılmasını ve yüksek erişilebilir olmasını gerektirir. Genelde bunun için Redis gibi merkezi, hızlı bir depo kullanılır. Oturum deposu çökerse, herkes çıkış yapmış olur. Yine de birçok üretim sistemi için bu maliyet, sağladığı kontrol karşısında kabul edilebilir ve hatta tercih edilir.

## Token Tabanlı Kimlik Doğrulama (JWT)

### Tanım ve Çalışma Mantığı

Token tabanlı yaklaşımda -pratikte en yaygın biçimi **JWT (JSON Web Token)**- kullanıcı doğrulandıktan sonra sunucu, kullanıcı bilgilerini (claims) içeren, kendi kendini taşıyan (self-contained) ve **imzalı** bir token üretir. JWT üç parçadan oluşur ve nokta ile ayrılır: `header.payload.signature`.

- **Header**: token tipini ve kullanılan imza algoritmasını belirtir (örneğin HMAC-SHA256 ya da RSA/ECDSA tabanlı asimetrik imza).
- **Payload**: claim'leri içerir - kullanıcı ID'si, roller, son kullanma zamanı (`exp`), veren (`iss`) gibi standart ve özel alanlar. **Bu kısım şifreli değildir, yalnızca base64url ile kodlanmıştır.** Yani herkes okuyabilir; içine hassas veri koymak ciddi bir hatadır.
- **Signature**: header ve payload'ın, sunucunun gizli anahtarıyla imzalanmış halidir. Bu imza, token'ın içeriğinin değiştirilmediğini garanti eder.

### Neden Böyle Çalışıyor?

JWT'nin temel fikri **doğrulamanın sunucuda durum tutmadan yapılabilmesidir.** Sunucu bir token aldığında, veritabanına gitmeden, sadece imzayı kendi gizli anahtarıyla yeniden hesaplayıp token'daki imzayla karşılaştırarak token'ın gerçek ve değiştirilmemiş olduğunu anlar. İmza tutuyorsa, payload'daki bilgilere güvenebilir. Bu, **stateless** bir mimaridir: herhangi bir sunucu örneği, oturum deposuna erişmeye ihtiyaç duymadan token'ı doğrulayabilir. Mikroservis mimarilerinde ve dağıtık sistemlerde bu özellik çok değerlidir, çünkü servisler arasında paylaşılan bir oturum deposu darboğazını ortadan kaldırır.

Asimetrik imza (örneğin RSA veya ECDSA) kullanıldığında bu daha da güçlenir: token'ı üreten **auth servisi** özel anahtarla imzalar, doğrulayan diğer servisler yalnızca **açık anahtara** sahiptir. Böylece token üretemeyen ama doğrulayabilen servisler kurabilirsiniz; gizli anahtar tek bir yerde kalır.

### En Büyük Tuzak: İptal Problemi

Stateless olmanın doğrudan sonucu şudur: **bir JWT'yi süresi dolmadan iptal etmek doğası gereği zordur.** Token kendi kendini doğruladığı için, onu geçersiz kılacak bir "kayıt silme" işlemi yoktur. Kullanıcı çıkış yapsa bile, token teknik olarak `exp` süresine kadar geçerli kalır. Çalınmış bir token'ı erkenden geçersiz kılmak isterseniz, aslında stateless avantajından vazgeçip bir **deny-list (kara liste)** tutmanız gerekir ki bu da sizi tekrar durum tutmaya geri götürür.

Bu problemi hafifletmenin standart yolu **kısa ömürlü access token + uzun ömürlü refresh token** desenidir:

- **Access token**: çok kısa ömürlüdür (örneğin birkaç dakika ile bir saat arası). Her API isteğinde taşınır. Çalınsa bile penceresi dardır.
- **Refresh token**: daha uzun ömürlüdür, yalnızca yeni access token almak için kullanılır ve genellikle sunucu tarafında saklanıp iptal edilebilir. Refresh token'ı bir güvenli cookie'de tutmak yaygın ve iyi bir pratiktir.

Bu desende iptal problemi refresh token seviyesine indirgenir: refresh token'ı sunucudan silerseniz, mevcut access token en fazla birkaç dakika daha yaşar, sonra kullanıcı yenileyemez ve dışarı düşer.

## Session mi, Token mı? Kök Karşılaştırma

Bu bir "hangisi daha iyi" sorusu değil, bir **denge (trade-off)** sorusudur. Karar, iptal kontrolü ile ölçeklenme kolaylığı arasındaki gerilimden doğar:

- **Anlık iptal ve tam kontrol** öncelikliyse (bankacılık, sağlık, yönetim panelleri) session tabanlı yaklaşım daha doğrudan bir cevaptır.
- **Yatay ölçekleme, mikroservisler, mobil istemciler ve üçüncü taraf API tüketimi** öncelikliyse token tabanlı yaklaşım daha uygundur.

Çok yaygın ve pragmatik bir hata, JWT'yi "moda olduğu için" klasik, tek sunuculu bir web uygulamasında session'ın yerine koymaktır. Böyle bir bağlamda JWT çoğu zaman ekstra karmaşıklık ve daha zayıf iptal davranışı dışında bir şey getirmez. Buna karşılık, "sadece cookie eski teknoloji" diyerek session'ı reddetmek de yanlıştır. Doğru mühendislik, mimarinin gerçek ihtiyacına göre seçim yapmaktır. Not: session ID'lerini de cookie ile taşırsınız; yani "cookie vs token" değil, gerçek eksen "sunucuda durum tutma vs tutmama"dır.

## Güvenli Cookie: Kimlik Kanıtını Doğru Taşımak

Session ID de olsa refresh token da olsa, tarayıcı ortamında bu kanıtı taşımanın en güvenli yolu genellikle cookie'dir. Ama cookie'nin güvenliği tamamen doğru **niteliklerle (attributes)** işaretlenmesine bağlıdır. Bu nitelikler kağıt üzerinde küçük görünür ama gerçek dünyadaki saldırıların büyük kısmını kapatır.

### HttpOnly

`HttpOnly` işaretli bir cookie'ye **JavaScript erişemez** (`document.cookie` üzerinden okunamaz). Bunun kök nedeni **XSS (Cross-Site Scripting)** saldırılarına karşı savunmadır. Eğer bir saldırgan sayfaya kötü niyetli JavaScript enjekte edebilirse ve oturum kanıtınız JavaScript'ten okunabilir bir yerde duruyorsa (örneğin `localStorage`), token doğrudan çalınır. `HttpOnly` cookie, kanıtı JavaScript'in erişim alanının dışına çıkarır. **Bu, JWT'yi `localStorage`'da tutmanın neden riskli olduğunun da cevabıdır:** `localStorage` XSS'e tamamen açıktır. Token'ı HttpOnly cookie'de tutmak bu vektörü büyük ölçüde kapatır.

### Secure

`Secure` işaretli cookie yalnızca HTTPS bağlantısı üzerinden gönderilir. Kök neden **man-in-the-middle** ve pasif dinleme saldırılarıdır: cookie düz metin HTTP üzerinden giderse, ağı dinleyen biri onu okuyabilir. `Secure`, cookie'nin asla şifresiz kanaldan gitmemesini garanti eder. Üretimde istisnasız zorunludur.

### SameSite

`SameSite` niteliği, cookie'nin **siteler arası (cross-site) isteklerde** gönderilip gönderilmeyeceğini kontrol eder ve **CSRF (Cross-Site Request Forgery)** saldırılarına karşı ana savunma hattıdır. CSRF'in mantığı şudur: siz bir siteye giriş yapmışken, kötü niyetli başka bir site tarayıcınızı sizin adınıza o siteye istek atmaya kandırır; tarayıcı cookie'leri otomatik eklediği için istek "sizden gelmiş gibi" görünür.

- `SameSite=Strict`: cookie yalnızca aynı siteden gelen isteklerde gönderilir. En güvenli ama en katı; başka bir siteden gelen bir linkle geldiğinizde ilk istekte oturum taşınmayabilir.
- `SameSite=Lax`: makul bir denge. Üst düzey gezinme (bir linke tıklama gibi) GET isteklerinde cookie gönderilir, ama siteler arası POST gibi "durum değiştiren" isteklerde gönderilmez. Modern tarayıcılarda çoğunlukla varsayılan davranış budur.
- `SameSite=None`: cookie tüm siteler arası isteklerde gönderilir; bu değer verildiğinde `Secure` de zorunludur. Gerçekten cross-site senaryo (örneğin ayrı domain'lerdeki frontend/backend) gerekmedikçe kaçınılmalıdır.

### Ek Nitelikler ve Bütünsel Bakış

`Domain` ve `Path` cookie'nin kapsamını daraltır; gereksiz geniş kapsam, cookie'nin gereğinden fazla yerde açığa çıkmasına yol açar. `Max-Age`/`Expires` ömrü belirler; oturum kanıtları makul kısa tutulmalıdır. Cookie ön ekleri (örneğin `__Host-` ön eki) tarayıcının cookie'yi yalnızca belirli katı koşullarda kabul etmesini zorlar ve ek bir sertlik katmanı sağlar.

Kritik ders: bu nitelikler **birlikte** çalışır. `HttpOnly` XSS'i, `SameSite` CSRF'i, `Secure` ise ağ dinlemeyi hedefler. Biri eksikse, o vektör açık kalır. Doğru bir üretim cookie'si tipik olarak şuna benzer: HttpOnly, Secure, SameSite=Lax (veya gereğine göre Strict), dar kapsamlı ve makul ömürlü.

## Çok Faktörlü Kimlik Doğrulama (MFA)

### Tanım ve Kök Mantık

Şifre tek başına zayıf bir faktördür: yeniden kullanılır, phishing ile çalınır, veri sızıntılarında toplu halde ele geçirilir. MFA'nın kök fikri, kimlik kanıtını **farklı kategorilerden** en az iki bağımsız faktöre dayandırmaktır:

1. **Bildiğiniz bir şey** (knowledge): şifre, PIN.
2. **Sahip olduğunuz bir şey** (possession): telefon, donanım anahtarı, authenticator uygulaması.
3. **Olduğunuz bir şey** (inherence): parmak izi, yüz gibi biyometrik veriler.

Güvenliğin arttığı yer, faktörlerin **farklı kategorilerden** olmasıdır. İki şifre sormak MFA değildir; çünkü ikisi de aynı zafiyete (bilgi çalınması) sahiptir. Bir saldırganın hem şifrenizi bilmesi hem de fiziksel telefonunuza sahip olması çok daha düşük olasılıktır. Yani MFA, tek bir faktörün ele geçirilmesini **yeterli olmaktan çıkarır**.

### MFA Yöntemleri ve Güvenlik Sıralaması

- **SMS/e-posta OTP**: kullanıcıya tek kullanımlık bir kod gönderilir. Yaygın ve kolaydır ama en zayıf ikinci faktördür. **SIM swapping** (saldırganın operatörü kandırıp numarayı kendi SIM'ine taşıması) ve SMS'in şifresiz doğası nedeniyle risklidir. Hiç MFA olmamasından iyidir, ama hassas sistemlerde tercih edilmemelidir.

- **TOTP (Time-based One-Time Password)**: Google Authenticator, Authy gibi uygulamalarla çalışır. Sunucu ve uygulama, kurulum sırasında paylaşılan bir gizli anahtardan (shared secret) ve mevcut zamandan yola çıkarak periyodik olarak (tipik olarak 30 saniyede bir) aynı kodu üretir. Ağ üzerinden kod gitmediği için SMS'ten çok daha güvenlidir. Zayıflığı, kullanıcının kodu bir phishing sitesine girmesiyle gerçek zamanlı olarak yakalanabilmesidir.

- **Push tabanlı onay**: kullanıcının telefonuna "giriş yapmayı onaylıyor musunuz?" bildirimi gider. Kolaydır ama **MFA fatigue / prompt bombing** saldırısına açıktır: saldırgan sürekli onay isteği gönderip yorulan kullanıcının yanlışlıkla onaylamasını umar. Numara eşleştirme (number matching) gibi tekniklerle sertleştirilebilir.

- **FIDO2/WebAuthn (donanım güvenlik anahtarları, passkey'ler)**: en güçlü kategoridir. Kök gücü şudur: kimlik doğrulama, açık anahtar kriptografisine dayanır ve **doğrulama, sitenin gerçek origin'ine kriptografik olarak bağlanır (origin binding).** Bu yüzden phishing'e karşı doğası gereği dirençlidir: kullanıcı sahte bir siteye yönlendirilse bile, kimlik doğrulayıcı yanlış origin için imza üretmez. Gizli anahtar cihazdan hiç çıkmaz. Passkey'ler bu teknolojiyi kullanıcı dostu hale getirir ve giderek şifresiz (passwordless) geleceğin temeli olur.

### MFA Tuzakları

En sık hatalar: MFA'yı yalnızca girişe koyup **hassas işlemleri** (şifre değiştirme, para transferi) korumasız bırakmak; **kurtarma akışlarını (account recovery)** MFA'sız tasarlayarak arka kapı açmak - çünkü zayıf bir "şifremi unuttum" akışı tüm MFA'yı anlamsız kılar; ve **yedek kodları** güvensiz saklamak. MFA'nın gücü, en zayıf halkası kadardır.

## Baştan Sona Güvenli Doğrulama Akışı

Şimdi tüm bu parçaları uçtan uca bir akışta birleştirelim ve her adımın **neden** öyle olduğunu görelim.

### 1. Kayıt ve Şifre Saklama

Kullanıcı kaydolduğunda şifre **asla düz metin olarak veya geri döndürülebilir şifreleme ile saklanmaz.** Şifre, özel olarak yavaş ve tuzlu (salted) bir **password hashing** algoritmasıyla saklanır. Bunun için genel amaçlı hızlı hash fonksiyonları (örneğin ham SHA-256) **yanlış seçimdir**, çünkü çok hızlı olmaları saldırganın saniyede milyarlarca deneme yapmasına izin verir. Doğrusu, kasıtlı olarak yavaş ve bellek-yoğun (memory-hard) algoritmalardır: bcrypt, scrypt ve modern öneri olan **Argon2** bu ailedendir.

Buradaki iki kavram kritiktir:
- **Salt**: her şifreye eklenen benzersiz rastgele değer. Aynı şifreye sahip iki kullanıcının hash'inin farklı olmasını sağlar ve önceden hesaplanmış tablolarla (rainbow table) saldırıyı imkansız kılar.
- **Work factor / cost**: algoritmanın ne kadar yavaş olacağını ayarlar. Donanım güçlendikçe bu parametre artırılarak brute-force maliyeti yüksek tutulur.

### 2. Giriş (Login)

Kullanıcı e-posta ve şifresini gönderir. Sunucu şifreyi aynı algoritmayla hash'leyip saklanan hash ile karşılaştırır. Burada ince ama önemli bir nokta: **kullanıcı adı yanlış** ile **şifre yanlış** durumlarını ayırt eden mesajlar vermeyin; her ikisinde de aynı genel hatayı ("e-posta veya şifre hatalı") döndürün. Aksi halde saldırgana hangi hesapların var olduğunu (**user enumeration**) sızdırırsınız. Ayrıca karşılaştırmanın **timing attack**'lara karşı sabit zamanlı olması, ve giriş uç noktasının **rate limiting** ile korunması gerekir - yoksa brute-force ve credential stuffing (başka sızıntılardan gelen şifre listelerini deneme) saldırıları serbest kalır.

### 3. MFA Adımı

Şifre doğrulandıysa, MFA etkinse ikinci faktör istenir. Kritik nokta: kullanıcı MFA'yı geçene kadar **tam yetkili oturum verilmemelidir.** Genellikle geçici, sınırlı yetkili bir ara durum (pending MFA state) tutulur; yalnızca ikinci faktör de doğrulandıktan sonra gerçek oturum kanıtı üretilir.

### 4. Oturum Kanıtının Üretilmesi ve Teslimi

Tüm faktörler doğrulandıktan sonra oturum kanıtı üretilir (session ID veya access/refresh token çifti) ve yukarıda anlatılan güvenli cookie nitelikleriyle (HttpOnly, Secure, SameSite) istemciye teslim edilir. Bu anda **session fixation** saldırısına karşı önlem alınır: giriş öncesi zaten bir oturum kimliği varsa, giriş anında **yeni bir oturum kimliği üretilip eskisi geçersiz kılınmalıdır.** Aksi halde saldırgan, kurbanı önceden bildiği bir session ID ile giriş yapmaya kandırıp o oturumu ele geçirebilir.

### 5. Yetkili İstekler ve Yenileme

İstemci sonraki isteklerde kanıtı taşır. Token yaklaşımında access token süresi dolduğunda, refresh token ile sessizce yenilenir. İyi bir pratik **refresh token rotation**'dır: her yenilemede yeni bir refresh token verilip eskisi geçersiz kılınır. Eğer eski (kullanılmış) bir refresh token tekrar kullanılmaya çalışılırsa, bu neredeyse kesin bir çalınma işaretidir; sistem o zinciri tamamen iptal eder (**reuse detection**). Bu, çalınmış refresh token'ların tespitini mümkün kılan güçlü bir mekanizmadır.

### 6. Çıkış (Logout) ve İptal

Session yaklaşımında logout, sunucudaki kaydı silmektir - anında ve kesin. Token yaklaşımında logout, refresh token'ı iptal edip cookie'yi temizlemektir; access token en fazla kısa ömrü kadar daha yaşar. "Tüm cihazlardan çıkış" gibi özellikler, session'da doğal, token'da ise ancak sunucu tarafı refresh token/deny-list yönetimiyle mümkündür.

## Yaygın Hatalar (Toplu Bir Bakış)

Aşağıdaki hatalar sahada tekrar tekrar görülür ve her biri yukarıdaki bir "neden"in ihlalidir:

- **JWT'yi `localStorage`'da tutmak**: XSS'e tamamen açık bırakır. Tarayıcıda HttpOnly cookie tercih edin.
- **JWT payload'ına hassas veri koymak**: payload şifreli değildir, sadece kodlanmıştır; herkes okur.
- **`alg: none` veya zayıf algoritma kabulü**: bazı kütüphaneler token'ın belirttiği algoritmaya körü körüne güvenirse, saldırgan imzasız token dayatabilir. Sunucu kabul edeceği algoritmayı **kendisi sabitlemelidir**, token'ın dediğine güvenmemelidir.
- **Şifreyi hızlı hash ile saklamak** (ham MD5/SHA): brute-force'a açık. Argon2/bcrypt/scrypt kullanın.
- **Cookie niteliklerini eksik bırakmak**: HttpOnly, Secure, SameSite üçlüsünden birini atlamak ilgili saldırı vektörünü açar.
- **Rate limiting ve hesap kilitleme olmaması**: brute-force ve credential stuffing'i davet eder.
- **User enumeration**: giriş, kayıt ve "şifremi unuttum" akışlarında farklı mesaj/zamanlama sızıntısı.
- **Zayıf hesap kurtarma akışı**: MFA'yı ve tüm güvenliği baypas eden arka kapı.
- **Session fixation'ı önlememek**: giriş sonrası oturum kimliğini yenilememek.
- **MFA'yı yalnızca girişte uygulamak**: hassas işlemleri korumasız bırakmak.
- **Gizli anahtarları koda gömmek**: imza/şifreleme anahtarları koda veya sürüm kontrolüne konulursa, tüm güven modeli çöker. Anahtarlar bir secret yönetim sisteminde tutulmalı ve döndürülebilmelidir.

## En İyi Pratikler (Özet ve Gerekçeleri)

- **İhtiyaca göre seç**: Anlık iptal ve merkezi kontrol istiyorsan session; dağıtık, stateless ölçek istiyorsan kısa ömürlü access + iptal edilebilir refresh token deseni. Kararı mimari ihtiyaç belirlesin, moda değil.
- **Tarayıcıda kanıtı HttpOnly + Secure + SameSite cookie'de taşı**: üç ayrı saldırı sınıfını (XSS, MITM, CSRF) aynı anda daraltır.
- **Şifreleri Argon2/bcrypt/scrypt ile, salt ve ayarlanabilir cost ile sakla**: donanım güçlendikçe cost'u yükselt.
- **MFA'yı sun ve mümkünse phishing'e dirençli yöntemlere (FIDO2/WebAuthn/passkey) yönlendir**; SMS OTP'yi ancak son çare olarak kullan.
- **Access token'ı kısa, refresh token'ı iptal edilebilir tut; refresh token rotation + reuse detection uygula**: çalınmayı hem sınırla hem tespit et.
- **Giriş uç noktalarını rate limiting ile koru**, hesap kilitleme ve şüpheli davranış izleme ekle.
- **Kayıt, giriş ve kurtarma akışlarında tek tip yanıt ve zamanlama** ile user enumeration'ı önle.
- **Giriş anında oturum kimliğini yenile** (session fixation savunması).
- **Hassas işlemler için yeniden doğrulama (step-up authentication)** iste; her şeyi tek bir giriş anına bağlama.
- **Gizli anahtarları secret yönetiminde tut, döndürülebilir yap**; asimetrik imza ile üretim/doğrulama sorumluluklarını ayır.
- **Her yerde HTTPS**, güvenli varsayılanlar ve derinlemesine savunma (defense in depth): tek bir kontrolün başarısız olacağını varsay ve katmanla.

## Sonuç

Kimlik doğrulama, tek bir kütüphane çağrısıyla "hallolan" bir özellik değil, birbirini destekleyen kararlar zinciridir. Session ile token arasındaki seçim aslında **durum tutma ile stateless ölçek** arasındaki bir denge; güvenli cookie nitelikleri farklı saldırı sınıflarını kapatan tamamlayıcı katmanlar; MFA ise tek bir faktörün ele geçirilmesini yetersiz kılan bir kategori çeşitlendirmesidir. Güvenli akışın özü, her adımda "bu adım hangi saldırıyı, neden engelliyor?" sorusunu net biçimde cevaplayabilmektir. Sağlam bir sistem, tek bir kontrolün başarısız olacağını baştan kabul eder ve savunmayı katmanlar; çünkü gerçek dünyada güvenlik, en güçlü halkanız kadar değil, en zayıf halkanız kadardır.
