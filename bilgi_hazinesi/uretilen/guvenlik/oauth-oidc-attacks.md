# OAuth 2.0 / OIDC Saldırıları: redirect_uri, state/CSRF, Token Sızdırma ve PKCE

## Giriş: OAuth ve OIDC Neden Bu Kadar Sık Kırılıyor?

OAuth 2.0 bir **authorization** (yetkilendirme) framework'üdür; kimlik doğrulama (authentication) protokolü değildir. OpenID Connect (OIDC) ise OAuth 2.0'ın üzerine oturan, kimlik doğrulama katmanını ekleyen bir profildir. Bu ayrım kritik çünkü sektördeki güvenlik açıklarının önemli bir kısmı, geliştiricilerin OAuth'u "login yapmak için" bir kimlik protokolü sanmasından doğar.

OAuth 2.0'ın kırılganlığının kök nedeni tek bir teknik hata değil, protokolün doğasıdır: OAuth, birden çok güvenlik alanı (browser, authorization server, client backend, resource server) arasında hassas bilgileri (authorization code, access token, kullanıcı kimliği) taşır. Bu bilgiler HTTP redirect'ler, URL parametreleri ve tarayıcı üzerinden akar. Her transfer noktası bir saldırı yüzeyidir. Framework esneklik için birçok "grant type" ve opsiyonel parametre tanımlar; bu esneklik, yanlış yapılandırıldığında zafiyete dönüşür.

Bu makale dört ana eksende ilerliyor: `redirect_uri` manipülasyonu, `state` parametresi ve CSRF, token sızdırma (leakage) senaryoları ve PKCE'nin bunları nasıl azalttığı. Her bölümde önce mekanizmayı, sonra istismar mantığını, sonra savunmayı ele alacağım.

## Temel Akış: Authorization Code Flow

Saldırıları anlamak için önce standart akışı netleştirelim. En yaygın ve önerilen akış **Authorization Code Flow**'dur:

1. Kullanıcı client uygulamasında "X ile giriş yap" der.
2. Client, kullanıcıyı authorization server'a (AS) yönlendirir. Bu istekte `client_id`, `redirect_uri`, `response_type=code`, `scope` ve ideal olarak `state` ile PKCE parametreleri (`code_challenge`, `code_challenge_method`) bulunur.
3. Kullanıcı AS üzerinde kimliğini doğrular ve izni onaylar.
4. AS, kullanıcıyı `redirect_uri` adresine bir `code` (authorization code) ile geri yönlendirir.
5. Client backend, bu `code`'u kendi `client_secret`'ı (ve varsa PKCE `code_verifier`) ile birlikte AS'nin token endpoint'ine gönderir.
6. AS, `access_token` (ve OIDC'de `id_token`, opsiyonel `refresh_token`) döner.

Bu akışın güvenlik değeri şudur: hassas token'lar tarayıcıya hiç düşmez; sadece kısa ömürlü, tek kullanımlık `code` tarayıcıdan geçer. Token değişimi (token exchange) sunucudan sunucuya (back-channel) yapılır. Buna karşılık artık kullanımı önerilmeyen **Implicit Flow**'da access token doğrudan URL fragment'ında tarayıcıya dönerdi; bu yüzden büyük ölçüde terk edilmiştir.

## redirect_uri Saldırıları

### Mekanizma ve Kök Neden

`redirect_uri`, AS'nin authorization code'u (veya eski akışlarda token'ı) hangi adrese göndereceğini belirtir. Buradaki temel güven varsayımı şudur: AS, code'u yalnızca meşru client'a ait bir adrese göndermelidir. Eğer bir saldırgan AS'yi, code'u kendi kontrol ettiği bir adrese göndermeye ikna edebilirse, kurbanın hesabını ele geçirebilir.

Kök neden **redirect_uri doğrulamasının zayıf yapılması**dır. Spesifikasyon, kayıtlı (registered) redirect URI ile istekteki URI'nin **tam eşleşmesini** (exact match) önerir. Ancak birçok AS ve client, kolaylık için gevşek eşleştirme kullanır: prefix matching, subdomain wildcard, path'in serbest bırakılması gibi. Her gevşeklik bir açık kapıdır.

### Somut İstismar Senaryoları

**1. Açık redirect (open redirect) zinciri.** Client'ın kayıtlı redirect_uri'si `https://app.example.com/callback` olsun. Ancak `app.example.com` üzerinde `https://app.example.com/redirect?url=` gibi bir açık yönlendirme (open redirect) varsa, saldırgan meşru bir redirect_uri kullanarak code'u önce meşru domaine, oradan da açık yönlendirme ile kendi sitesine kaçırabilir. AS açısından her şey kurallara uygundur; zafiyet client tarafındaki open redirect'tedir.

**2. Gevşek path/subdomain eşleştirmesi.** AS yalnızca origin'i (`https://app.example.com`) doğruluyorsa, saldırgan `https://app.example.com/attacker-controlled` gibi kontrol edebildiği bir path'e code aldırabilir. Ya da wildcard subdomain (`*.example.com`) kayıtlıysa ve saldırgan bir alt domaini ele geçirebiliyorsa (örneğin unutulmuş bir subdomain, subdomain takeover), code oraya yönlenir.

**3. Parametre kirlenmesi ve encoding oyunları.** Saldırgan, `redirect_uri` içinde ek query parametreleri, farklı URL encoding'ler, `#` fragment enjeksiyonu, ya da `\` gibi tarayıcı ve sunucunun farklı yorumladığı karakterlerle doğrulamayı atlatmaya çalışır. Örneğin bazı parser'lar `https://app.example.com.attacker.com` ile `https://app.example.com` arasındaki farkı yanlış değerlendirebilir.

### Savunma

- **Tam eşleşme (exact string match) zorunlu tutun.** Kayıtlı redirect_uri'ler tam olarak, karakter karakter eşleşmeli. Wildcard ve prefix eşleştirmeden kaçının. OAuth 2.0 Security Best Current Practice dokümanları da bu yönde nettir.
- Redirect URI'leri **allowlist** (izin listesi) olarak tutun; dinamik ya da kullanıcıdan gelen redirect_uri'yi asla body'ye/isteğe olduğu gibi güvenmeyin.
- Client tarafındaki **open redirect** açıklarını kapatın; callback host'unuzda yönlendirme yapan endpoint'leri sıkılaştırın.
- Subdomain takeover riskini yönetin: kullanılmayan DNS kayıtlarını ve wildcard registration'ları temizleyin.

## state Parametresi ve CSRF

### Mekanizma ve Kök Neden

`state`, client'ın authorization isteğinde ürettiği ve callback'te geri beklediği, tahmin edilemez (unguessable) bir değerdir. Amacı iki katmanlıdır: birincisi CSRF koruması, ikincisi ise akış boyunca uygulamaya özel bağlam (context) taşımaktır.

CSRF (Cross-Site Request Forgery) burada şu şekilde ortaya çıkar: OAuth callback'i, sonuçta client'ın "bu code'u kullanıcının oturumuna bağla" dediği bir noktadır. Eğer client, gelen callback'in gerçekten **kendi başlattığı** akışa ait olup olmadığını doğrulamazsa, saldırgan kendi authorization code'unu kurbanın tarayıcısında tetikleyerek **kurbanın hesabına saldırganın hesabını bağlatabilir** (account injection / login CSRF).

Kök neden: OAuth callback state-changing (durum değiştiren) bir işlemdir ve HTTP redirect ile tetiklenir. Klasik CSRF korumasının OAuth'a uyarlanmış hali `state` parametresidir. `state` yoksa veya doğrulanmıyorsa, callback'i sahte olarak tetiklemek mümkün olur.

### Login CSRF Senaryosu

Saldırgan kendi hesabıyla OAuth akışını başlatır ama akışı yarıda bırakıp kendi authorization code'unu (veya callback URL'ini) yakalar. Sonra bu callback URL'ini kurbana tıklatır (ya da gizli bir iframe/otomatik istek ile tetikler). Kurbanın tarayıcısı callback'i çalıştırır; client eğer state doğrulaması yapmıyorsa, code'u değişip saldırganın kimliğine ait token'ı alır ve **kurbanın client oturumunu saldırganın kimliğine bağlar**. Artık kurban, saldırganın kontrolündeki bir kimlikle giriş yapmış olur; kurban örneğin ödeme bilgisi girerse bu saldırganın hesabına işler.

### state'in İkinci Rolü: Bağlam Taşıma ve Tehlikeleri

`state` çoğu zaman "kullanıcı akış sonrası hangi sayfaya dönsün" gibi bilgiyi de taşır. Burada iki hata sık yapılır:

1. **state'i redirect için doğrudan kullanmak.** Eğer `state` içindeki değer, callback sonrası yönlendirme adresi olarak kullanılıyorsa, bu yeni bir open redirect ve token sızdırma vektörü açar.
2. **state'i sadece tahmin edilemez yapmak ama session'a bağlamamak.** `state` rastgele olsa bile, client onu kullanıcının oturumuyla ilişkilendirip callback'te bu ilişkiyi doğrulamıyorsa CSRF koruması yarım kalır.

### Savunma

- Her authorization isteği için **kriptografik olarak güçlü, rastgele** bir `state` üretin.
- `state`'i mutlaka **kullanıcının server-side session'ına bağlayın** ve callback'te birebir karşılaştırın; eşleşmezse akışı reddedin. Tek kullanımlık (single-use) olsun.
- `state`'i **serbest yönlendirme verisi** olarak kullanmayın; yönlendirme hedeflerini de allowlist ile sınırlayın.
- OIDC kullanıyorsanız, replay ve token substitution'a karşı `nonce` parametresini de kullanın (aşağıda). `state` ve `nonce` farklı amaçlara hizmet eder; ikisi birbirinin yerine geçmez.

## Token Sızdırma (Token Leakage)

### Kök Neden

Token sızdırma, hassas kimlik bilgilerinin (authorization code, access token, id_token, refresh token) tasarlanmadıkları bir tarafın eline geçmesidir. Kök nedenler genelde şunlardır: token'ların URL'de taşınması, tarayıcı geçmişi/Referer başlığı üzerinden kaçışı, loglara yazılması, front-channel'da taşınması ve XSS ile client tarafından çalınması.

### Somut Sızma Vektörleri

**1. Referer başlığı ve tarayıcı geçmişi.** Token veya code URL'de (özellikle query string veya fragment'ta) taşınıyorsa, callback sayfasındaki herhangi bir dış kaynak (üçüncü parti script, resim, analytics) `Referer` başlığı üzerinden bu değeri dışarı taşıyabilir. Ayrıca URL tarayıcı geçmişinde ve proxy loglarında kalır. Bu, Implicit Flow'un terk edilmesinin ana nedenlerindendir: access token URL fragment'ında görünürdü.

**2. Loglara yazma.** Reverse proxy, load balancer veya uygulama logları tam URL'i loglarsa, code ve token'lar düz metin olarak diskte kalır. Log toplama sistemleri geniş erişimli olduğu için bu ciddi bir maruz kalma yüzeyidir.

**3. Authorization code interception.** Özellikle native/mobil uygulamalarda ve SPA'larda, custom URI scheme (`myapp://callback`) ile başka bir kötü niyetli uygulama aynı scheme'i kaydederek code'u yakalayabilir. Bu senaryo PKCE'nin doğduğu temel problemdir (aşağıda ayrıntılı).

**4. XSS ile token çalma.** Access token veya refresh token tarayıcıda erişilebilir bir yerde (örneğin `localStorage`) tutuluyorsa, sayfadaki herhangi bir XSS bunları okuyup dışarı gönderebilir. Bu, SPA mimarilerinde token saklamanın en temel gerilimidir.

**5. Mix-up saldırıları.** Client birden çok authorization server'ı destekliyorsa, saldırgan client'ı yanıltarak code'u bir AS'ye ait sanıp başka bir AS'nin token endpoint'ine göndermesini sağlayabilir; ya da hangi AS'den döndüğünü karıştırarak code'u kaçırabilir. Bu, `iss` (issuer) doğrulaması ve akış başına AS'nin sabitlenmesiyle engellenir.

### Savunma

- **Authorization Code Flow + PKCE** kullanın; token'ları front-channel'da taşımayın. Implicit Flow'dan kaçının.
- Token'ları ve code'ları **URL query string'te taşımaktan kaçının**; mümkün olduğunca back-channel'da tutun.
- Callback sayfalarında **Referrer-Policy** başlığını sıkılaştırın (örneğin `no-referrer`) ve callback'i işleyip URL'i temizleyin.
- **Logging'de token/code redaction** uygulayın; proxy ve uygulama loglarında hassas parametreleri maskeleyin.
- SPA'larda refresh token'ı tarayıcıda `localStorage`'da tutmaktan kaçının; mümkünse **BFF (Backend-for-Frontend)** deseniyle token'ları server-side'da tutun ve tarayıcıya sadece `HttpOnly`, `Secure`, `SameSite` cookie tabanlı bir oturum verin.
- **Token binding / sender-constrained token** yaklaşımlarını (örneğin mutual TLS ile veya DPoP gibi proof-of-possession mekanizmalarıyla) değerlendirin; böylece çalınan bir token başka bir istemcide kullanılamaz.
- **Kısa ömürlü access token** ve dönüşümlü (rotating) refresh token kullanın; refresh token rotation ile bir refresh token yeniden kullanıldığında tüm zinciri geçersiz kılın (reuse detection).

## PKCE (Proof Key for Code Exchange)

### Ne Problemi Çözer, Neden Var?

PKCE, özellikle `client_secret`'ı güvenli saklayamayan **public client'lar** (mobil uygulamalar, SPA'lar, masaüstü uygulamaları) için tasarlandı. Public client'ın sırrı yoktur ya da sırrı ele geçirilebilir; dolayısıyla token endpoint'te "sen gerçekten o client mısın" doğrulaması zayıftır. Ayrıca native uygulamalarda authorization code, custom URI scheme üzerinden başka bir uygulama tarafından yakalanabilir (code interception). PKCE, çalınan bir authorization code'un saldırgan tarafından token'a çevrilmesini engeller.

### Çalışma Mantığı

PKCE, akışa dinamik olarak üretilen bir sır ekler:

1. Client, akış başlamadan önce rastgele bir **`code_verifier`** üretir (yüksek entropili bir string).
2. Bundan bir **`code_challenge`** türetir. Önerilen yöntem `S256`'dır: `code_challenge = BASE64URL(SHA256(code_verifier))`. `plain` yöntemi de vardır (challenge = verifier) ama güvenli değildir ve kaçınılmalıdır.
3. Authorization isteğinde `code_challenge` ve `code_challenge_method=S256` gönderilir. AS bunu code ile ilişkilendirip saklar.
4. Token değişiminde client, orijinal `code_verifier`'ı gönderir. AS, `SHA256(code_verifier)`'ı hesaplayıp sakladığı `code_challenge` ile karşılaştırır. Eşleşmezse token vermez.

Buradaki dahiyane nokta şu: `code_challenge` front-channel'da (authorization isteğinde) gider ve bir saldırgan onu görebilir. Ama `code_verifier` back-channel'da (token isteğinde) gider. SHA-256 tek yönlü bir hash olduğu için, challenge'ı gören saldırgan verifier'ı geri hesaplayamaz. Dolayısıyla saldırgan code'u çalsa bile, doğru `code_verifier`'ı bilmediği için code'u token'a çeviremez. PKCE böylece code interception ve code injection saldırılarını etkisiz kılar.

### PKCE'nin state ve nonce ile İlişkisi (Sık Karıştırılan Nokta)

Bu üç parametrenin işlevlerini karıştırmamak önemlidir:

- **state**: CSRF/akış bütünlüğü; callback'in client'ın kendi başlattığı akışa ait olduğunu doğrular.
- **PKCE (code_verifier/challenge)**: Code'un, onu başlatan client tarafından kullanıldığını kanıtlar; code interception/injection'a karşı korur.
- **nonce (OIDC)**: `id_token` içine gömülür; id_token'ın replay edilmesini ve token substitution'ı engeller. Client, ürettiği nonce'ı id_token içindeki `nonce` claim'i ile karşılaştırır.

Modern rehberler artık **PKCE'yi tüm client tipleri için** (public ve confidential) önermektedir; sadece mobil/SPA için değil. Çünkü PKCE, code injection'a karşı `state`'in tek başına vermediği ek bir garanti sağlar.

### Savunma ve Doğru Kullanım

- Daima **`S256`** kullanın; `plain` methodu asla kabul etmeyin. AS tarafında `plain`'i tümüyle reddetmek iyi bir sertleştirmedir.
- `code_verifier`'ı **yeterli entropi** ile üretin (kriptografik rastgele kaynak; spesifikasyon minimum uzunluk sınırları koyar).
- AS tarafında PKCE'yi **zorunlu** kılın (public client'lar için özellikle). Bir client PKCE ile başladıysa, token değişiminde verifier eksikse reddedin (PKCE downgrade'i engelleyin).
- PKCE'yi `state` ve OIDC'de `nonce` ile birlikte kullanın; birbirlerinin yerine geçmezler.

## OIDC'ye Özgü Ek Riskler: id_token Doğrulama

OIDC'de client bir `id_token` (JWT) alır ve bunu kullanıcının kimliği olarak yorumlar. Buradaki en kritik hata **id_token doğrulamasının eksik yapılması**dır. Kök neden: JWT self-contained (kendi içinde taşınan) bir yapıdır; imzası doğrulanmazsa içeriği tamamen sahte olabilir.

Doğrulanması gereken temel claim'ler ve nedenleri:

- **İmza (signature).** Token'ın gerçekten beklenen AS tarafından imzalandığını doğrulayın; imzayı AS'nin yayınladığı public key (JWKS) ile kontrol edin. **`alg: none`** kabul etmeyin; bu klasik JWT saldırısı imzayı tamamen atlatır. Ayrıca beklenen algoritmayı sabitleyin ki saldırgan asimetrik doğrulamayı simetrik bir yönteme (key confusion) düşürmesin.
- **`iss` (issuer).** Beklenen authorization server ile eşleşmeli; mix-up saldırılarına karşı korur.
- **`aud` (audience).** Token'ın gerçekten sizin `client_id`'niz için düzenlendiğini doğrular; başka bir client için düzenlenmiş token'ın kabulünü (token substitution) engeller.
- **`exp` / `iat`.** Süresi geçmiş token'ları reddedin; replay penceresini daraltın.
- **`nonce`.** Akışta ürettiğiniz değerle eşleşmeli; id_token replay'ini engeller.

Ek bir tuzak: access token'ı kimlik doğrulama için kullanmak. Access token'lar bir kaynağa erişim için düzenlenir; kime ait oldukları client açısından her zaman doğrulanabilir değildir. Kullanıcı kimliği için **id_token**'ı (uygun doğrulamayla) ya da UserInfo endpoint'ini kullanın.

## Yaygın Hatalar (Anti-Patterns)

- **redirect_uri'de wildcard/prefix eşleştirme.** En sık ve en tehlikeli hatalardan biri; exact match kullanın.
- **state'i hiç kullanmamak veya session'a bağlamadan sadece "var mı" diye bakmak.** CSRF korumasını fiilen devre dışı bırakır.
- **Implicit Flow kullanmaya devam etmek.** Token'ı URL'de taşır; artık önerilmez.
- **PKCE'yi `plain` ile veya hiç kullanmamak.** Public client'larda code interception'a açık kapı bırakır.
- **id_token imzasını doğrulamamak, `aud`/`iss`/`nonce` kontrol etmemek.** Sahte kimlikle giriş mümkün olur.
- **Access token'ı localStorage'da tutmak ve XSS'e karşı savunmasız SPA.** Token hırsızlığını kolaylaştırır.
- **Refresh token rotation ve reuse detection olmadan uzun ömürlü refresh token.** Çalınan bir refresh token uzun süre sömürülebilir.
- **Token/code'ları loglara maskesiz yazmak.** Geniş erişimli loglarda kalıcı sızıntı.
- **scope'u aşırı geniş vermek.** İhlal anında etki alanını büyütür; least privilege uygulayın.
- **Tek AS'ye sabitlenmemek ve `iss` doğrulamamak.** Mix-up saldırılarına açık.

## En İyi Pratikler (Özet Kontrol Listesi)

1. **Authorization Code Flow + PKCE (S256)** kullanın; tüm client tipleri için PKCE'yi zorunlu kılın.
2. **redirect_uri için exact match** ve allowlist uygulayın; wildcard'dan kaçının.
3. Her akışta **güçlü, rastgele, session'a bağlı, tek kullanımlık `state`** kullanın.
4. OIDC'de **`nonce`** kullanın ve **id_token'ı tam doğrulayın** (imza, `iss`, `aud`, `exp`, `nonce`; `alg:none` reddi).
5. Token'ları **front-channel'da taşımayın**; SPA'larda mümkünse **BFF** deseniyle token'ları server-side tutun.
6. **Kısa ömürlü access token**, **rotating refresh token** ve **reuse detection** kullanın.
7. **Referrer-Policy**'yi sıkılaştırın, callback URL'ini temizleyin, **loglarda redaction** yapın.
8. **Least privilege scope** ilkesine uyun; gereksiz izin istemeyin.
9. Mümkünse **sender-constrained token** (mTLS / DPoP gibi proof-of-possession) ile token hırsızlığının etkisini azaltın.
10. Client'taki **open redirect** açıklarını kapatın ve **subdomain takeover** riskini yönetin.
11. **iss doğrulaması** ile mix-up saldırılarına karşı korunun; akış başına AS'yi sabitleyin.

## Kapanış

OAuth 2.0 ve OIDC'nin güvenliği tek bir parametreye değil, birlikte çalışan bir savunma katmanına dayanır. `redirect_uri`'nin katı doğrulaması code'un doğru yere gitmesini, `state` callback'in bütünlüğünü, PKCE code'un doğru client tarafından kullanıldığını, `nonce` ve id_token doğrulaması kimliğin sahte olmadığını, token saklama ve taşıma disiplini de sızıntıyı engeller. Bu parçalardan biri eksik olduğunda genellikle hesap ele geçirme (account takeover) seviyesinde bir zafiyet ortaya çıkar. Doğru mimari, en güncel Security Best Current Practice rehberlerini takip etmek ve "OAuth bir yetkilendirme framework'üdür, kimlik doğrulama için OIDC'yi doğru uygulayın" ilkesini içselleştirmektir.
