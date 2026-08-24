# JWT Saldırıları — Derin Dalış: Doğrulama Mantığını Kırmanın Anatomisi

Bu metin, JWT saldırılarını bir özet gibi değil, kodun içine girerek ele alır. Amaç saldırının nasıl çalıştığını mekanizma düzeyinde anlamak, sahadaki gerçek CVE kayıtlarıyla bağlamak ve savunmayı tasarım kararı seviyesinde inşa etmektir. Özet makaledeki (`bilgi_hazinesi/uretilen/guvenlik/jwt-attacks.md`) kavramsal zemini burada varsayıyoruz: JWT'nin `header.payload.signature` yapısı, Base64URL'nin bir encoding olduğu (encryption değil), ve güvenliğin imzanın bütünlüğünden geldiği. Buradan itibaren doğrudan koda ve istismar mantığına dalıyoruz.

Tekrar edilmesi gereken tek bir çekirdek ilke var: **doğrulayan taraf, hangi doğrulamayı yapacağına saldırganın kontrol ettiği veriye bakarak karar verirse, doğrulama mantığının kontrolünü de saldırgana devretmiş olur.** Aşağıdaki her saldırı bu ilkenin bir varyasyonudur.

---

## 1. Çözümlü yürüyüş

Somut bir sistem kuralım. Bir Node.js/Express API'si düşünün: kullanıcılar giriş yapar, sunucu RS256 ile imzalı bir JWT verir, sonraki isteklerde bu token bir middleware'de doğrulanır. Yönetici uç noktaları `role: "admin"` claim'ine bakar. Bu, sahadaki en yaygın kurulumdur ve tam da bu kurulumun naif hâli **algorithm confusion** saldırısına açık kapı bırakır.

### 1.1 Zafiyetli / hatalı kod

Aşağıdaki middleware gerçekçi biçimde hatalıdır. Geliştirici "public key ile doğruluyorum, private key sunucuda güvende, o hâlde güvendeyim" diye düşünmüştür. `jsonwebtoken` kütüphanesini kullanıyor ama kritik bir parametreyi atlıyor.

```javascript
// auth-middleware.js  — HATALI SÜRÜM
const jwt = require('jsonwebtoken');
const fs = require('fs');

// Uygulama token'ları RS256 ile imzalıyor; public key herkese açık.
const PUBLIC_KEY = fs.readFileSync('./keys/public.pem', 'utf8');

function authenticate(req, res, next) {
  const authHeader = req.headers.authorization || '';
  const token = authHeader.replace(/^Bearer\s+/i, '');

  try {
    // KRİTİK HATA: 'algorithms' allowlist'i geçilmemiş.
    // Kütüphane, doğrulama algoritmasını token'ın HEADER'ından okuyacak.
    const payload = jwt.verify(token, PUBLIC_KEY);
    req.user = payload;
    next();
  } catch (err) {
    res.status(401).json({ error: 'invalid token' });
  }
}

function requireAdmin(req, res, next) {
  if (req.user && req.user.role === 'admin') return next();
  res.status(403).json({ error: 'forbidden' });
}

module.exports = { authenticate, requireAdmin };
```

Yüzeyde bu kod çalışır: meşru RS256 token'ları doğru şekilde doğrulanır, geçersiz imzalar reddedilir. Testler yeşil. Sorun, testlerin denemediği bir yolda.

### 1.2 Sorun nasıl ortaya çıkıyor (kavramsal)

`jwt.verify(token, PUBLIC_KEY)` çağrısında ikinci argüman "doğrulama anahtarı"dır ve burada bir PEM string'idir. Kütüphane, bu string'i **hangi algoritmaya göre yorumlayacağına token'ın header'ındaki `alg` alanına bakarak** karar verir — çünkü biz ona `algorithms` allowlist'i vermedik.

Şimdi asimetriyi görelim:

- Header `RS256` derse: kütüphane `PUBLIC_KEY`'i bir **RSA public key** olarak parse eder ve RSA imza doğrulaması yapar. Saldırgan bunu kıramaz; RSA imzası üretmek için private key gerekir ve o sunucuda.
- Header `HS256` derse: kütüphane `PUBLIC_KEY` string'ini bir **HMAC secret'ı** olarak yorumlar. HS256 için "anahtar", sadece rastgele baytlardan ibaret bir simetrik secret'tır. Kütüphane bakış açısıyla `PUBLIC_KEY` de sadece bir bayt dizisidir.

İşte tuzak: public key **tanım gereği herkese açıktır** (JWKS endpoint'inden, sertifikadan, ya da GitHub'daki bir config dosyasından alınabilir). Saldırgan bu public key'in tam bayt temsilini (genellikle PEM metninin satır sonlarıyla birlikte birebir hâli) alır, kendi payload'ını `role: "admin"` yapar, header'ı `HS256`'ya çevirir ve token'ı **public key'i HMAC secret olarak kullanarak** imzalar. Sunucu doğrularken elindeki aynı PUBLIC_KEY ile HMAC hesaplar, sonuç birebir tutar, token geçerli sayılır.

Saldırgan hiçbir zaman private key'i bilmedi. Gizli olması gereken imzalama sırrına hiç ihtiyaç duymadı; çünkü doğrulama tarafı, **açık** bir anahtarı **simetrik** bir bağlamda kullanmaya kandırıldı.

Saldırganın forge ettiği token'ı üretmesi kavramsal olarak şuna denk gelir (bu, saldırının mekanizmasını göstermek içindir, savunma tarafında bu davranışı test etmek de yararlıdır):

```javascript
// forge-demo.js — saldırının NEDEN işe yaradığını gösteren kavramsal kod
const jwt = require('jsonwebtoken');
const fs = require('fs');

// Saldırgan public key'i zaten elde etmiştir (JWKS, sertifika, repo...).
const attackerCopyOfPublicKey = fs.readFileSync('./public.pem', 'utf8');

const forged = jwt.sign(
  { sub: '1234', role: 'admin' },
  attackerCopyOfPublicKey,        // public key'i secret gibi kullanıyor
  { algorithm: 'HS256' }          // asimetrik anahtarı simetrik algoritmaya sokuyor
);
// forged token, HATALI middleware tarafından geçerli kabul edilir.
```

Önemli nüans: saldırının başarısı, doğrulama tarafının public key'i **tam olarak nasıl yüklediğine** (satır sonları, trailing newline, PEM header/footer dahil mi) bağlıdır. Bu yüzden pratikte saldırgan public key'in birkaç farklı temsilini dener. Bu detay savunmayı daha da güçlendirir: sorun anahtarın formatında değil, anahtar tipinin algoritmaya bağlanmamış olmasındadır.

### 1.3 Düzeltilmiş / doğru kod

Düzeltme iki katmanlıdır. Birincisi ve en önemlisi: **kabul edilen algoritmaları allowlist ile sunucuda sabitlemek.** İkincisi (savunmayı derinleştiren): anahtarı, kütüphanenin HMAC secret olarak yorumlayamayacağı **tipli bir key nesnesi** olarak vermek.

```javascript
// auth-middleware.js  — DOĞRU SÜRÜM
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const fs = require('fs');

// Public key'i ham string olarak değil, tipli bir KeyObject olarak yükle.
// Böylece bu nesne bir RSA public key'dir; HMAC secret'ı OLARAK ASLA kullanılamaz.
const PUBLIC_KEY = crypto.createPublicKey(
  fs.readFileSync('./keys/public.pem', 'utf8')
);

function authenticate(req, res, next) {
  const authHeader = req.headers.authorization || '';
  const token = authHeader.replace(/^Bearer\s+/i, '');

  try {
    const payload = jwt.verify(token, PUBLIC_KEY, {
      algorithms: ['RS256'],     // <-- allowlist: yalnızca RS256. 'none' ve 'HS*' reddedilir.
      issuer: 'https://auth.example.com',
      audience: 'api.example.com',
      clockTolerance: 30,        // exp/nbf için makul saat kayması toleransı (saniye)
    });
    req.user = payload;
    next();
  } catch (err) {
    // TokenExpiredError, JsonWebTokenError ('invalid algorithm' dahil) burada yakalanır.
    res.status(401).json({ error: 'invalid token' });
  }
}

function requireAdmin(req, res, next) {
  if (req.user && req.user.role === 'admin') return next();
  res.status(403).json({ error: 'forbidden' });
}

module.exports = { authenticate, requireAdmin };
```

Neden bu iki katman birden?

- `algorithms: ['RS256']` tek başına algorithm confusion'ı ve `alg:none`'ı kapatır: `HS256` header'lı bir token daha imza kontrolüne varmadan "invalid algorithm" ile reddedilir. Bu, **zorunlu** ve **tek başına yeterli** birincil savunmadır.
- `crypto.createPublicKey(...)` ile anahtarı bir `KeyObject` yapmak **derinlemesine savunma**dır. Diyelim biri gelecekte allowlist'i yanlışlıkla gevşetti; kütüphane yine de bir RSA `KeyObject`'i HMAC secret'ı olarak kullanmayı reddeder, çünkü tip düzeyinde uyumsuzdur. İki bağımsız hata olmadan zafiyet doğmaz.

Aynı prensibin HMAC (HS256) senaryosundaki doğru hâli de şudur — buradaki kritik nokta secret'ın entropisidir:

```javascript
// HS256 kullanmak zorundaysanız: güçlü secret + allowlist
const jwt = require('jsonwebtoken');

// 32 bayt (256 bit) kriptografik rastgelelik, ortam değişkeninden okunur.
// Klavyeden uydurulmuş 'supersecret123' DEĞİL.
const SECRET = Buffer.from(process.env.JWT_SECRET_BASE64, 'base64');
if (SECRET.length < 32) throw new Error('JWT secret too short');

function verifyHs(token) {
  return jwt.verify(token, SECRET, {
    algorithms: ['HS256'],   // yine allowlist; 'none' ve 'RS*' reddedilir
    issuer: 'https://auth.example.com',
    audience: 'api.example.com',
  });
}
```

Bu iki dosya, bölüm 4'teki hata kataloğunun büyük çoğunluğunu tek başına kapatır. Geri kalan hatalar (claim doğrulama, `kid`/`jku`, revocation) ayrı disiplinlerdir ve aşağıda ele alınıyor.

---

## 2. Gerçek dünya (CVE ile)

Yukarıdaki hatalar teorik değil; JWT ekosisteminin ilk yıllarında neredeyse her büyük kütüphane bu sınıf zafiyetlerden en az birini yaşadı. Somut kayıtlara bakalım.

### 2.1 Algorithm confusion — CVE-2015-9235 ve CVE-2016-10555

**CVE-2015-9235**, tam olarak bölüm 1'de anlattığımız algorithm confusion'ın kanonik örneğidir. Açıklama nettir: `jsonwebtoken` Node modülünün 4.2.2 öncesi sürümlerinde, token asimetrik bir anahtarla (RS/ES ailesi) imzalanmış olsa bile, saldırgan bunun yerine **simetrik bir algoritma (HS* ailesi)** ile imzalanmış bir token gönderebiliyordu ve doğrulama bunu geçiriyordu. CWE-20 (Improper Input Validation) olarak sınıflandırılmış. Bizim "HATALI SÜRÜM" middleware'imiz, güncel bir kütüphaneyle bile `algorithms` allowlist'ini atladığında aynı davranışı yeniden üretir — yani zafiyet sadece kütüphanenin değil, çağıranın da sorumluluğudur.

**CVE-2016-10555**, aynı sınıfı `jwt-simple` (0.3.0 ve öncesi) kütüphanesinde gösterir ve kök nedeni tek cümlede özetler: `jwt.decode()` içinde "algorithm" zorunlu kılınmadığından, kötü niyetli kullanıcı hangi algoritmanın sunucuya gönderileceğini **kendisi seçebiliyordu**. Kayıttaki ifade, algorithm confusion'ın mantığını tam olarak anlatıyor: "Sunucu RSA beklerken RSA'nın public key'iyle HMAC-SHA gönderilirse, sunucu public key'i bir HMAC private key sanır ve saldırgan istediği veriyi forge edebilir." Bu, bölüm 1.2'de kavramsal olarak anlattığımız tuzağın CVE numaralı, sahada belgelenmiş hâlidir. Yine CWE-20.

Bu ikisinin birlikte verdiği ders: **algoritma seçimini çağırana bırakan her API tehlikelidir.** Modern `jsonwebtoken` bugün `algorithms` verilmediğinde uyarır/kısıtlar; ama savunmacı asla kütüphanenin varsayılanına güvenmemeli, allowlist'i açıkça geçmelidir.

### 2.2 İmza doğrulamayı komple bypass — CVE-2015-2951 ve CVE-2015-2964

Bir sonraki sınıf daha da temeldir: imza doğrulamasının **crafted token'larla tamamen atlatılması.**

**CVE-2015-2951**: F21 JWT kütüphanesinin (2.0 öncesi) `JWT.php` dosyasında, uzaktaki saldırganların özel hazırlanmış token'larla imza doğrulamasını **bypass** etmesine izin veren bir zafiyet. **CVE-2015-2964**: NAMSHI/JOSE 5.0.0 ve öncesinde, JWT header'ındaki crafted token'larla imza doğrulamasının bypass'ı. Her iki kayıt da aynı dönemin (2015) `alg:none` ve algoritma-esnekliği dalgasına aittir; PHP ekosisteminin JWT kütüphaneleri de Node ile aynı hataları bağımsız olarak yaptı.

Bu kayıtların bize öğrettiği: `alg:none` ve türevleri **dile özgü değildir** — Node, PHP, Go, hepsi aynı tasarım tuzağına düştü. Savunma prensibi de dilden bağımsızdır: doğrulama politikasını header'dan değil, sunucu konfigürasyonundan al.

### 2.3 Timing side-channel — CVE-2015-10004 ve CVE-2016-7037

Daha ince bir sınıf: imza karşılaştırmasının **zamanlama** üzerinden sızdırılması.

**CVE-2015-10004** (Go, `github.com/robbert229/jwt`): token doğrulama metodları, HMAC karşılaştırması sırasında bir **timing side-channel**'a açıktı. Düşük gecikmeli bir bağlantı üzerinden yeterince çok istekle, saldırgan beklenen HMAC'i baytı baytına daraltarak çıkarabiliyordu. CWE-208 (Information Exposure Through Timing Discrepancy).

**CVE-2016-7037** (PHP, Malcolm Fell `jwt` 1.0.3 öncesi): `Encryption/Symmetric.php` içindeki `verify` fonksiyonu hash karşılaştırmasında **timing-safe olmayan** bir fonksiyon kullanıyordu; bu, saldırganların timing attack ile imzaları taklit etmesine izin veriyordu.

Kök neden ortak: imza karşılaştırması `a == b` gibi **erken çıkışlı** (short-circuit) bir string karşılaştırmasıyla yapılırsa, ilk farklı baytta döner ve geçen süre eşleşen prefix uzunluğunu sızdırır. Doğru yaklaşım **sabit zamanlı (constant-time)** karşılaştırmadır. Kendi imza karşılaştırmanızı yazmak zorunda kalırsanız (genelde kalmamalısınız — kütüphaneye bırakın):

```javascript
const crypto = require('crypto');

// YANLIŞ: erken çıkış -> timing sızıntısı (CVE-2015-10004 / CVE-2016-7037 sınıfı)
function badCompare(a, b) {
  return a === b;
}

// DOĞRU: sabit zamanlı karşılaştırma
function safeCompare(a, b) {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  // Uzunluk farkını da sızdırmamak için önce uzunluğu eşitle/kontrol et
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}
```

### 2.4 Eksik doğrulama mantığı — CVE-2016-8218 ve CVE-2016-10525

**CVE-2016-8218** (Cloud Foundry routing-release 0.142.0 öncesi): JWT kütüphanelerindeki **eksik doğrulama mantığı** (incomplete validation logic), yetkisiz saldırganların routing API'sine başka kullanıcıları taklit ederek erişmesine izin veriyordu — kayıtta "Unauthenticated JWT signing algorithm in routing" olarak adlandırılmış. Yani yine algoritma tarafında bir doğrulama boşluğu, kimlik taklidine (impersonation) dönüşüyor.

**CVE-2016-10525** (`hapi-auth-jwt2` 5.1.1): hapi'de `try` authentication modunu desteklemeye çalışırken ortaya çıkan bir hata, kişilerin **authentication'ı komple bypass** etmesine yol açıyordu (Improper Authentication). Bu kayıt farklı bir dersi vurgular: zafiyet çekirdek imza mantığında değil, **"opsiyonel authentication" (try mode) gibi bir kolaylık özelliğinin** kenar durumunda doğmuştu. "Auth zorunlu değil ama varsa doğrula" gibi ikili modlar, savunmacının kör noktasıdır.

**Bu altı grubun ortak dersi:** JWT zafiyetleri neredeyse hiçbir zaman kriptografinin kendisinde değildir. Kırılan şey her zaman **doğrulama etrafındaki mantıktır** — algoritma seçimi, karşılaştırmanın zamanlaması, opsiyonel-auth kenar durumu, ya da eksik claim kontrolü.

---

## 3. Karşılaştırma / karar

Savunmacının en önemli tasarım kararları burada. Her birinin takasını netleştirelim.

### 3.1 Simetrik (HS256) mı, asimetrik (RS256/ES256) mı?

| Boyut | HS256 (simetrik) | RS256 / ES256 (asimetrik) |
|---|---|---|
| Anahtar dağıtımı | Aynı secret'ı imzalayan **ve** doğrulayan herkes bilmek zorunda | Doğrulayanlara yalnızca **public** key dağıtılır |
| Sır yayılım riski | Doğrulayıcı sayısı arttıkça secret'ı bilen taraf sayısı artar → sızma yüzeyi büyür | İmzalama sırrı tek yerde kalır |
| Performans | Çok hızlı (HMAC ucuzdur) | İmzalama/doğrulama daha pahalı (ES256 imzası RS256'dan hızlı, doğrulaması yavaş) |
| Token boyutu | Küçük imza | RS256 imzası büyük (2048-bit key ile ~256 bayt); ES256 daha kompakt |
| Ana risk | Zayıf secret → offline brute-force | Yanlış kullanımda algorithm confusion (bölüm 1) |

**Karar kuralı:** Token'ı üreten ve doğrulayan **aynı** güvenilir taraf ise (tek monolit, kendi secret'ını kendi kontrol eder) ve secret güçlü tutulabiliyorsa HS256 pratik ve hızlıdır. Ama token birden çok servis, üçüncü taraf ya da istemci tarafından doğrulanacaksa **asimetrik zorunludur**: aksi hâlde herkesin aynı simetrik secret'ı bilmesi gerekir ve tek bir sızıntı tüm sistemi çökertir. Mikroservis ve federated kimlik senaryolarında RS256/ES256 varsayılan olmalıdır.

### 3.2 `verify` mi, `decode` mi?

Bu bir takas değil, bir tuzaktır — ama karar noktası olarak görünür. `decode` yalnızca Base64URL'yi çözer, **imzayı kontrol etmez.** Meşru tek kullanımı: imzayı zaten doğruladıktan sonra, ya da güvenmediğiniz bir token'dan sadece `kid` gibi bir alanı okumak (ve o değere göre anahtar seçmek). Güvenlik kararı vereceğiniz her yerde **her zaman `verify`**, ve `verify`'a mutlaka `algorithms` allowlist'i.

### 3.3 Algoritmayı nerede sabitlemek — kod mu, config mi?

Allowlist'i koda gömmek (`algorithms: ['RS256']`) en katı ve en güvenli seçenektir; deploy dışında değiştirilemez. Config'ten okumak esneklik verir ama config'i saldırgan ya da yanlış bir operatör gevşetebilir. **Karar:** algoritma ailesini koda sabitleyin; yalnızca anahtar rotasyonu gibi gerçekten değişebilir parametreleri config'e taşıyın. "Header ne derse ona göre algoritma seç" seçeneği bir seçenek değil, doğrudan zafiyettir.

### 3.4 Token iptali: stateless saflık mı, revocation mı?

JWT'nin cazibesi stateless olmasıdır, ama saf stateless bir token **iptal edilemez** — süresi dolana kadar geçerlidir. Takas:

- **Saf stateless + kısa `exp`:** Basit, ölçeklenebilir; ama çalınan token, `exp` dolana dek (örn. 5-15 dk) kullanılabilir kalır. Kritik olmayan sistemler için kabul edilebilir.
- **Kısa access token + refresh token + sunucu tarafı deny-list:** Refresh anını sunucu kontrol eder; şüpheli oturum anında kesilebilir. Karmaşıklık ve bir miktar state maliyeti getirir ama güvenlik penceresini daraltır.

**Karar kuralı:** access token'ı olabildiğince kısa ömürlü tutun, gerçek oturum uzunluğunu refresh token ile yönetin, ve yüksek riskli sistemlerde bir revocation/deny-list stratejisi ekleyin. "Uzun ömürlü access token" neredeyse her zaman yanlış cevaptır.

---

## 4. Hata-modu kataloğu

Aşağıdakiler, gelistiricilerin ve savunmacıların bu konuda tekrar tekrar yaptığı somut hatalar. Her biri en az bir CVE ya da bölüm 1-3'teki bir mekanizmayla bağlıdır.

1. **`algorithms` allowlist'ini geçmemek.** `jwt.verify(token, key)` çağrısında algoritma listesini atlamak, kütüphanenin `alg`'i header'dan okumasına yol açar; algorithm confusion (CVE-2015-9235, CVE-2016-10555) ve `alg:none` buradan doğar.

2. **`alg:none`'ı üretimde açık bırakmak.** İmzasız token kabul eden bir doğrulama yolu, saldırganın imza kısmını boş bırakarak istediği payload'ı geçirmesine izin verir; `None`/`NONE` gibi harf varyasyonları filtre atlatmakta kullanılır.

3. **Public key'i ham string olarak generic `key` argümanına vermek.** Anahtar bir `KeyObject`/tipli nesne değilse, kütüphane onu HS256 secret'ı olarak yorumlayabilir ve algorithm confusion kapısı açılır.

4. **`verify` yerine `decode` çağırmak.** İmza hiç kontrol edilmez; saldırgan payload'ı serbestçe değiştirir. Sinsi çünkü kod "çalışıyor" görünür.

5. **İmza karşılaştırmasını erken-çıkışlı (`==`) yapmak.** Sabit zamanlı olmayan karşılaştırma timing side-channel yaratır (CVE-2015-10004, CVE-2016-7037); `crypto.timingSafeEqual` ya da kütüphanenin kendi güvenli karşılaştırması kullanılmalıdır.

6. **Kısa/tahmin edilebilir/varsayılan HMAC secret'ı kullanmak.** `secret`, `password`, tutorial'dan kopyalanmış değerler offline brute-force ile saniyeler içinde kırılır; secret en az 256 bit kriptografik rastgelelik olmalı.

7. **Secret'ı repoya, image'a, örnek dosyaya gömmek.** Sızma testlerinin en sık bulgusu; anahtar sızınca tüm HS256 sistemi biter. Ortam değişkeni ya da secret yöneticisi + rotasyon şart.

8. **`exp` / `nbf` doğrulamamak.** İmza doğru olsa bile süresi dolmuş ya da henüz geçerli olmayan token'lar kabul edilir; çalınan token sonsuza dek yaşar. Ayrıca makul bir `clockTolerance` belirlenmeli.

9. **`aud` / `iss` doğrulamamak.** Bir servis için üretilmiş token, başka bir serviste ya da başka bir issuer'dan kabul edilir; token yanlış bağlamda geçerli olur (token confusion / audience karışıklığı).

10. **`kid`, `jku`, `x5u` header alanlarına körü körüne güvenmek.** `kid`'i dosya yoluna/DB sorgusuna koymak path traversal veya injection doğurur; `jku`/`x5u`'daki URL'ye güvenmek saldırganın kendi anahtarını doğrulatmasına izin verir. Bu alanlar güvensiz veri olarak ele alınmalı, `jku`/`x5u` katı allowlist'e bağlanmalı.

11. **"Opsiyonel authentication" (try/optional mode) kenar durumunu ihmal etmek.** Auth'un opsiyonel olduğu yollar, doğrulama boşluğunu tüm authentication'ın bypass'ına çevirebilir (CVE-2016-10525 sınıfı).

12. **Eski/güncellenmemiş kütüphane kullanmak ve payload'a hassas veri koymak.** Bilinen `alg:none`/confusion sertleştirmeleri güncellemelerle gelir; ayrıca payload okunabilir olduğundan parola, tam kart numarası gibi gizli veriler oraya konmamalıdır.

---

## Kapanış

Altı CVE grubu, dört ayrı dil ve onlarca kütüphane; hepsinin ortak paydası tek bir cümlede toplanır: **JWT'de kırılan şey kriptografi değil, doğrulamanın etrafındaki karar mantığıdır.** Algoritmayı sunucuda allowlist ile sabitleyin, anahtar tipini algoritmaya tip düzeyinde kilitleyin, imzayı sabit zamanlı doğrulayın, tüm claim'leri (`exp`, `nbf`, `iss`, `aud`) kontrol edin, secret'ı güçlü tutun ve `kid`/`jku`/`x5u` gibi header kaynaklı yönlendirmeleri güvensiz kabul edin. Bu disiplin uygulandığında, bölüm 2'deki her CVE'nin kök nedeni kapanır. JWT tehlikeli bir araç değildir; ona nasıl güvendiğiniz tehlikeli olabilir.
