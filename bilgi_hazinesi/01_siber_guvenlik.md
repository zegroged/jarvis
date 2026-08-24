# Siber Güvenlik — Uzman Bilgi Tabanı (Cilt 1)

Bu belge siber güvenliğin çekirdeğini, bir uzmanın kafasındaki bağlantılarla
anlatır. Amaç ezber değil, *neden böyle* sorusunu her yerde cevaplamak. Kırmızı
takım (saldırı) ve mavi takım (savunma) bakışları birlikte verilir; çünkü iyi
bir savunmacı saldırıyı, iyi bir saldırgan savunmayı bilmeden iş yapamaz.

---

## 1. Temel İlkeler ve Zihniyet

### 1.1. CIA üçlüsü
Güvenliğin üç temel hedefi:
- **Confidentiality (Gizlilik):** Bilgiye yalnızca yetkili kişiler erişir.
  Kırılması: veri sızıntısı, yetkisiz okuma. Koruma: şifreleme, erişim denetimi.
- **Integrity (Bütünlük):** Bilgi yetkisiz biçimde değiştirilemez. Kırılması:
  veri tahrifatı, man-in-the-middle. Koruma: hash, imza (signature), MAC.
- **Availability (Erişilebilirlik):** Sistem gerektiğinde çalışır. Kırılması:
  DoS/DDoS, fidye yazılımı. Koruma: yedeklilik, rate limiting, yedekleme.

Bu üçlü çoğu zaman çakışır: aşırı gizlilik erişilebilirliği düşürebilir. Güvenlik
her zaman bir *denge* ve *risk yönetimi* meselesidir, mutlak bir durum değil.

Ek iki kavram sık eklenir: **Authenticity** (kimliğin doğruluğu) ve
**Non-repudiation** (inkâr edilemezlik — bir eylemi yapanın onu yaptığını sonradan
reddedememesi; dijital imza bunu sağlar).

### 1.2. AAA
- **Authentication (Kimlik doğrulama):** "Sen kimsin?" — parola, token, biyometri.
- **Authorization (Yetkilendirme):** "Neye iznin var?" — roller, izinler, ACL.
- **Accounting/Auditing (Kayıt):** "Ne yaptın?" — loglar, iz kaydı.

Bu üçünün karıştırılması klasik hata kaynağıdır. Örneğin IDOR açığı özünde bir
*authorization* hatasıdır: kullanıcı kimliği doğru (authentication tamam) ama
başkasının kaynağına erişebiliyor (authorization eksik).

### 1.3. Savunma ilkeleri
- **Defense in depth (Derinlemesine savunma):** Tek bir kontrol yeterli değildir;
  katmanlar üst üste konur (ağ + host + uygulama + veri). Bir katman düşerse
  diğerleri tutar. WAF varsa da SQL sorgusu yine parametreli olmalı.
- **Least privilege (En az yetki):** Her özne (kullanıcı, servis, süreç) işini
  yapmak için gereken *asgari* yetkiye sahip olmalı. Bir web sunucusu root
  çalışmamalı; bir servis hesabı Domain Admin olmamalı.
- **Fail securely (Güvenli başarısızlık):** Bir kontrol hata verdiğinde varsayılan
  *reddetmek* olmalı, izin vermek değil. `if (yetki_kontrol() == HATA) izin_ver`
  şeklindeki mantık felakettir.
- **Zero trust (Sıfır güven):** "İç ağ güvenli" varsayımı terk edilir. Her istek,
  nereden gelirse gelsin, doğrulanır ve yetkilendirilir. "Never trust, always
  verify." Ağ konumu artık güven ölçütü değildir.
- **Attack surface minimization (Saldırı yüzeyini küçültmek):** Kapalı port,
  kaldırılmış özellik, devre dışı servis — saldırılamaz. En güvenli kod, hiç
  yazılmamış koddur.
- **Secure by default:** Ürün kutudan güvenli çıkmalı; kullanıcının güvenliği
  sonradan "açması" gerekmemeli.

### 1.4. Threat modeling (Tehdit modelleme)
Sistemi savunmadan önce *neye karşı* savunduğunu bilmelisin. Adımlar:
1. **Ne kuruyoruz?** — Mimariyi, veri akışlarını, güven sınırlarını (trust
   boundary) çiz. Data Flow Diagram (DFD) çıkar.
2. **Ne ters gidebilir?** — **STRIDE** çerçevesi:
   - **S**poofing (kimlik taklidi) → Authentication ile
   - **T**ampering (tahrifat) → Integrity ile
   - **R**epudiation (inkâr) → Non-repudiation/log ile
   - **I**nformation disclosure (bilgi sızıntısı) → Confidentiality ile
   - **D**enial of service → Availability ile
   - **E**levation of privilege (yetki yükseltme) → Authorization ile
3. **Ne yapacağız?** — Her tehdide karşı azaltma (mitigation).
4. **İyi iş çıkardık mı?** — Doğrula, tekrar et.

Risk kabaca: **Risk = Olasılık × Etki**. Sınırlı kaynağı en yüksek riskli
tehditlere ayır. DREAD gibi puanlama modelleri bunu sayısallaştırmaya çalışır.

### 1.5. Saldırı yaşam döngüsü — Cyber Kill Chain ve MITRE ATT&CK
Bir saldırıyı anlamanın iki haritası:
- **Lockheed Martin Kill Chain:** Reconnaissance → Weaponization → Delivery →
  Exploitation → Installation → Command & Control (C2) → Actions on Objectives.
- **MITRE ATT&CK:** Gerçek saldırgan davranışlarının taktik (neden) ve teknik
  (nasıl) matrisi. Taktikler: Initial Access, Execution, Persistence, Privilege
  Escalation, Defense Evasion, Credential Access, Discovery, Lateral Movement,
  Collection, Exfiltration, Impact. Mavi takım için ortak dil budur — bir
  tespit yazdığında hangi ATT&CK tekniğini kapsadığını söyleyebilmelisin.

---

## 2. Kriptografi

Kriptografi güvenliğin matematiksel temelidir. **Altın kural: kendi kripton
protokolünü/algoritma implementasyonunu yazma.** İyi test edilmiş kütüphaneleri
(libsodium, Tink, platformun kripto API'si) doğru kullan. Hatalar algoritmada
değil, neredeyse her zaman *kullanımda* olur.

### 2.1. Simetrik şifreleme
Aynı anahtar hem şifreler hem çözer. Hızlıdır; büyük veri için kullanılır.
- **AES** standart bloktur (128-bit blok; 128/192/256-bit anahtar).
- **Mod (mode of operation) çok önemli:**
  - **ECB — asla kullanma.** Aynı düz metin bloğu aynı şifreli bloğu üretir;
    desenler sızar (ünlü "ECB penguen" görseli). 
  - **CBC:** IV (initialization vector) gerektirir, rastgele olmalı. Padding
    oracle saldırısına açık olabilir (yanlış kullanımda).
  - **CTR:** Blok şifreyi akış şifresine çevirir. Nonce **asla tekrar
    kullanılmamalı** — aynı (anahtar, nonce) iki kez = felaket (XOR ile düz
    metin kurtarılır).
  - **GCM (tercih edilen):** AEAD — hem şifreler hem doğrular (authenticated
    encryption). Bütünlüğü de sağlar. Nonce tekrarı yine yasak.
- **AEAD (Authenticated Encryption with Associated Data):** Modern doğru seçim.
  AES-GCM veya ChaCha20-Poly1305. Şifreleme + bütünlük tek işlemde. "Encrypt
  then MAC" prensibini içeride halleder.

### 2.2. Asimetrik (açık anahtarlı) şifreleme
İki anahtar: **public** (herkese açık) ve **private** (gizli). Biriyle
şifrelenen diğeriyle çözülür. Yavaştır; genelde bir simetrik anahtarı güvenle
taşımak (key exchange) ve imza için kullanılır.
- **RSA:** Büyük asal çarpanlara ayırmanın zorluğuna dayanır. Padding şart
  (OAEP şifreleme için, PSS imza için); ders kitabı "textbook RSA" güvensizdir.
- **ECC (Elliptic Curve):** Aynı güvenliği çok daha küçük anahtarla verir
  (256-bit ECC ≈ 3072-bit RSA). Curve25519 (anahtar değişimi), Ed25519 (imza)
  modern tercihlerdir.
- **Diffie-Hellman (DH/ECDH):** İki taraf, açık kanalda konuşarak ortak gizli
  anahtar üretir — dinleyen anahtarı çıkaramaz. **Forward secrecy**'nin temeli:
  her oturum için geçici (ephemeral, DHE/ECDHE) anahtar; sunucunun uzun ömürlü
  anahtarı sonradan çalınsa bile eski trafik çözülemez.

### 2.3. Hash fonksiyonları
Girdi → sabit boyutlu, geri döndürülemez özet. İyi bir hash: tek yönlü,
çarpışmaya dirençli (collision resistant), çığ etkisi (küçük değişiklik → çok
farklı çıktı).
- **Kullan:** SHA-256, SHA-3, BLAKE2/BLAKE3.
- **Kullanma:** MD5 ve SHA-1 — kırıldı, çarpışma üretilebiliyor. Yalnızca
  güvenlik dışı sağlama (checksum) için görülebilir ama yeni tasarımda hayır.
- **Kritik ayrım — parola hash'i ≠ genel hash.** Parolayı SHA-256 ile hash'lemek
  YANLIŞTIR (çok hızlı → brute force kolay). Parola için *kasıtlı yavaş*,
  tuzlanmış (salted), bellek-zoru (memory-hard) fonksiyonlar:
  **Argon2id (tercih)**, **scrypt**, **bcrypt**, en azından yüksek iterasyonlu
  PBKDF2. **Salt** her parola için benzersiz ve rastgele; rainbow table'ı
  öldürür. **Pepper** (uygulama genelinde gizli ek) opsiyonel ikinci katman.

### 2.4. MAC ve imza
- **MAC (Message Authentication Code) / HMAC:** Simetrik anahtarla bütünlük +
  kimlik. İki taraf da anahtarı bilir. Doğrulama **sabit zamanlı karşılaştırma**
  (constant-time compare) ile yapılmalı; normal `==` timing attack sızdırır.
- **Dijital imza:** Asimetrik. Private ile imzalanır, public ile doğrulanır.
  Bütünlük + kimlik + **inkâr edilemezlik** sağlar (MAC bunu sağlamaz, çünkü iki
  taraf da anahtarı bilir). Ed25519, RSA-PSS, ECDSA.

### 2.5. TLS ve PKI
- **TLS handshake (özet, TLS 1.3):** İstemci ve sunucu şifre paketinde anlaşır;
  ECDHE ile ephemeral ortak anahtar üretilir (forward secrecy); sunucu
  sertifikasıyla kimliğini kanıtlar; oturum simetrik anahtarla (AES-GCM/ChaCha)
  devam eder. TLS 1.3 eski/zayıf her şeyi (RSA key exchange, CBC, RC4) attı,
  handshake'i hızlandırdı.
- **PKI (Public Key Infrastructure):** Sertifika Otoriteleri (CA) zinciriyle
  "bu public key gerçekten bu alan adına mı ait?" sorusunu güven zinciriyle
  cevaplar. Kök CA → ara CA → sunucu sertifikası. Tarayıcı kök CA listesine
  güvenir. **Certificate pinning** ekstra katman (belirli sertifika/CA'ya
  sabitleme) ama yönetimi zor.
- **Yaygın TLS hataları:** sertifika doğrulamasını kapatmak (`verify=False`,
  `InsecureSkipVerify: true`) — MITM'e davet; eski protokol (SSLv3, TLS 1.0/1.1);
  zayıf şifre paketleri; süresi geçmiş/self-signed sertifikayı sessizce kabul.

### 2.6. Kriptografide klasik hatalar (sınavda çıkar)
- Nonce/IV tekrar kullanımı (özellikle CTR/GCM'de).
- Rastgelelik için güvensiz kaynak (`rand()`, `Math.random()`) — kriptografik
  CSPRNG kullan (`/dev/urandom`, `secrets`, `crypto.randomBytes`).
- "Encrypt" ile "encode" karıştırmak — Base64 şifreleme DEĞİLDİR, sadece kodlama.
- Kendi algoritmanı/XOR "şifreni" uydurmak.
- Bütünlük olmadan sadece şifrelemek (AEAD kullan).
- Anahtarı kaynak kodda/repo'da tutmak (secret management kullan).

---

## 3. Kimlik Doğrulama ve Yetkilendirme

### 3.1. Parolalar
- Sunucuda **asla düz metin veya geri çevrilebilir şifreli** saklanmaz. Argon2id
  ile salted hash saklanır (bkz. 2.3).
- Politika: uzunluk kısıttan önemlidir (uzun passphrase > karmaşık kısa). NIST
  artık zorunlu periyodik değişimi ve saçma karmaşıklık kurallarını önermiyor;
  bunun yerine sızmış parola listelerine karşı kontrol (breached password check)
  ve uzunluk öneriyor.
- **Rate limiting + hesap kilitleme** brute force'a karşı; ama kilitleme DoS'a
  yol açabilir (saldırgan başkasının hesabını kilitler) — dikkatli tasarla.
- **Credential stuffing:** Başka sitelerden sızmış parola-eposta çiftlerini
  denemek. Savunma: MFA, breached password kontrolü, anormallik tespiti.

### 3.2. MFA (Çok faktörlü kimlik doğrulama)
Faktör türleri: bildiğin (parola), sahip olduğun (telefon/token), olduğun
(biyometri). İki *farklı* tür = MFA.
- **TOTP** (Google Authenticator gibi): paylaşılan gizli + zaman → 6 haneli kod.
- **SMS OTP:** zayıf (SIM swap, SS7); yoktan iyi ama tercih edilmez.
- **FIDO2/WebAuthn (en güçlü):** Donanım anahtarı/passkey; phishing'e dayanıklı
  çünkü kriptografik olarak alan adına (origin) bağlıdır — sahte site imzayı
  alamaz.

### 3.3. Oturum yönetimi (session)
- Sunucu tarafı oturum: rastgele, tahmin edilemez session ID; cookie'de saklanır.
- **Cookie güvenlik bayrakları:** `HttpOnly` (JS erişemez → XSS ile çalınamaz),
  `Secure` (yalnız HTTPS), `SameSite` (Lax/Strict → CSRF azaltma).
- Girişte session ID yenile (**session fixation**'a karşı). Çıkışta sunucuda
  geçersiz kıl. Makul timeout (idle + absolute).

### 3.4. JWT (JSON Web Token)
Kendi kendini taşıyan token: `header.payload.signature`, Base64URL. Sunucu
durumu tutmadan doğrular (stateless).
- **Klasik açıklar:**
  - `alg: none` — imzayı yok saymak. Sunucu bunu kabul ederse token sahtelenir.
    **Sabit algoritma zorla**, `none`'ı reddet.
  - **HS256 ↔ RS256 karışıklığı:** Sunucu RS256 bekliyor ama HS256 kabul
    ediyorsa, saldırgan public key'i HMAC anahtarı gibi kullanıp token imzalar.
    Algoritmayı token'dan okuma, sabitle.
  - Zayıf HMAC secret → brute force.
- Payload **şifreli değil, sadece imzalı** — içine sır koyma; herkes okur.
- İptal (revocation) zordur (stateless olduğu için). Kısa ömür + refresh token,
  ya da kara liste. Duyarlı işlemler için kısa TTL.

### 3.5. OAuth 2.0 ve OIDC
- **OAuth 2.0:** *Yetkilendirme* çerçevesi (delegated authorization). "Bu
  uygulama, benim adıma şu kaynağa erişebilir." Kimlik doğrulama protokolü
  DEĞİLDİR — bunu karıştırmak yaygın hatadır.
- **OpenID Connect (OIDC):** OAuth üstüne kimlik katmanı (ID token ekler).
  "Google ile giriş yap" bunu kullanır.
- **Authorization Code + PKCE** akışı standarttır. PKCE (Proof Key for Code
  Exchange), code interception'a karşı korur (özellikle mobil/SPA).
- **Açıklar:** `redirect_uri` gevşek doğrulama → token çalma; `state`
  parametresi eksik → CSRF; token'ı URL fragment'ında sızdırma.

### 3.6. Erişim denetim modelleri
- **RBAC (Role-Based):** İzinler rollere, roller kullanıcılara. Yaygın, yönetimi
  kolay.
- **ABAC (Attribute-Based):** Kural motoru; özniteliklere göre (departman, saat,
  konum) dinamik karar. Esnek ama karmaşık.
- **Broken access control** OWASP #1'dir — çoğu ihlal karmaşık exploit değil,
  basitçe "yetki kontrolü unutulmuş" endpoint'lerdir. Her istekte, sunucu
  tarafında, nesne düzeyinde yetki kontrolü şart.

---

## 4. Web Uygulama Güvenliği (OWASP Top 10 Derinlemesine)

Web, saldırı yüzeyinin en geniş olduğu yerdir. Aşağıda her sınıf için *kök
neden*, *sömürü mantığı* ve *doğru savunma* verilir. Ortak kök neden çoğunlukla
aynıdır: **kullanıcı girdisine güvenmek** ve **veri ile kodu/komutu
karıştırmak.**

### 4.1. Injection — SQL Injection
- **Kök neden:** Kullanıcı girdisi, SQL sorgusuna string olarak yapıştırılır;
  veri, komut olarak yorumlanır.
- **Örnek zafiyet:** `"SELECT * FROM users WHERE name='" + ad + "'"`. Girdi
  `' OR '1'='1` → koşul her zaman doğru; `'; DROP TABLE users;--` → yıkım.
- **Türler:** In-band (hata/union tabanlı), **blind** (çıktı görünmez; boolean
  veya time-based `SLEEP()` ile bit bit çıkarım), out-of-band.
- **Tek doğru savunma: Parameterized queries / prepared statements.** Sorgu
  yapısı sabittir, girdi *veri* olarak bağlanır, asla kod olamaz. ORM'ler
  genelde bunu yapar ama ham sorgu (`raw`) yazınca yine dikkat.
- **Ek katmanlar:** en az yetkili DB kullanıcısı, girdi doğrulama (allow-list),
  WAF (yardımcı, tek başına yeterli değil). String kaçış (escaping) ile
  savunmaya *güvenme* — parametrelendirme esastır.
- **NoSQL injection** de vardır (ör. MongoDB'ye `{"$gt": ""}` enjekte etmek);
  aynı ilke: girdiyi operatör olarak yorumlatma.

### 4.2. Cross-Site Scripting (XSS)
- **Kök neden:** Kullanıcı girdisi, HTML/JS bağlamına kodlanmadan basılır;
  tarayıcı onu script olarak çalıştırır. Saldırgan **kurbanın tarayıcısında**
  JS çalıştırır → session çalma, keylogging, sahte formlar.
- **Türler:**
  - **Stored (kalıcı):** Girdi sunucuda saklanır (yorum, profil), her ziyaretçide
    çalışır. En tehlikelisi.
  - **Reflected (yansıyan):** Girdi anında yanıta yansır (arama sonucu, hata
    mesajı); kurbana özel link ile tetiklenir.
  - **DOM-based:** Zafiyet tamamen istemci JS'inde (`innerHTML`, `document.write`
    ile kullanıcı verisini basmak). Sunucu hiç görmeyebilir.
- **Savunma:**
  - **Bağlama duyarlı çıktı kodlaması (output encoding):** HTML gövdesi, HTML
    öznitelik, JS, URL, CSS bağlamları farklı kodlama ister. Framework'lerin
    otomatik kaçışına güven (React JSX, Django template) ama `dangerouslySetInnerHTML`,
    `|safe`, `v-html` ile bunu delme.
  - **Content Security Policy (CSP):** Inline script'i yasakla, kaynakları
    kısıtla — başarılı bir XSS'in etkisini sınırlar (savunma derinliği).
  - Zengin metin için **allow-list tabanlı sanitizasyon** (DOMPurify gibi).
  - `HttpOnly` cookie → XSS ile session çalınmasını zorlaştırır.

### 4.3. Cross-Site Request Forgery (CSRF)
- **Kök neden:** Tarayıcı, cookie'yi her isteğe otomatik ekler. Saldırgan
  sitesi, kurbanın oturumunu kullanarak *durum değiştiren* bir isteği kurban
  adına tetikler (görünmez form, resim).
- **Savunma:**
  - **Anti-CSRF token** (senkronizasyon token'ı): sunucu formda rastgele token
    verir, istekle geri bekler; saldırgan sitesi bu token'ı bilemez.
  - **SameSite cookie** (Lax varsayılan modern tarayıcılarda) çoğu CSRF'yi keser.
  - Duyarlı işlemlerde ek doğrulama.
- **Not:** JSON API'ler + token tabanlı auth (cookie yerine `Authorization`
  header) CSRF'e doğal dirençlidir çünkü tarayıcı header'ı otomatik eklemez.

### 4.4. Server-Side Request Forgery (SSRF)
- **Kök neden:** Sunucu, kullanıcının verdiği URL'ye istek yapar. Saldırgan bunu
  iç ağa/servislere yönlendirir.
- **Klasik hedef — bulut metadata:** `http://169.254.169.254/...` (AWS/GCP/Azure
  metadata endpoint) → geçici kimlik bilgileri (credentials) sızar. Bulutta SSRF
  çoğu zaman tam ihlale döner.
- **Savunma:** Çıkış (egress) allow-list; iç IP aralıklarını (RFC1918,
  link-local `169.254`, localhost) engelle; DNS rebinding'e dikkat (çözümlenen
  IP'yi kontrol et, sonra o IP'ye bağlan); mümkünse ham URL yerine dolaylı
  referans (ID) kullan; metadata endpoint'e IMDSv2 gibi korumalar.

### 4.5. Insecure Direct Object Reference (IDOR) / BOLA
- **Kök neden:** `/api/invoice/1234` — kullanıcı ID'yi 1235 yapınca başkasının
  faturasını görür. Nesne düzeyinde yetki kontrolü eksik (Broken Object Level
  Authorization). API'lerde **en yaygın** ciddi açık.
- **Savunma:** Her nesne erişiminde "bu kaynak bu kullanıcıya mı ait?" kontrolü,
  sunucu tarafında. Tahmin edilemez ID (UUID) yardımcıdır ama *yetki kontrolünün
  yerini tutmaz* (security through obscurity yeterli değil).

### 4.6. XML External Entity (XXE)
- **Kök neden:** XML parser dış varlık (external entity) çözümlemesine açık.
  `<!ENTITY xxe SYSTEM "file:///etc/passwd">` → dosya okuma, SSRF, DoS
  (billion laughs).
- **Savunma:** Parser'da DTD/external entity işlemeyi kapat (secure processing).
  Mümkünse XML yerine JSON.

### 4.7. Insecure Deserialization
- **Kök neden:** Güvenilmeyen veriyi nesneye çevirmek (Java `readObject`, Python
  `pickle`, PHP `unserialize`, .NET `BinaryFormatter`). Özel hazırlanmış payload
  "gadget chain" ile **uzaktan kod çalıştırma (RCE)**'ye döner.
- **Savunma:** Güvenilmeyen veriyi asla native deserialization ile açma.
  Veri-yalnızca formatlar (JSON) + katı şema. İmzalı/şifreli veri. `pickle`'ı
  ağdan gelen veriyle kullanma — bu kural neredeyse mutlaktır.

### 4.8. Server-Side Template Injection (SSTI)
- **Kök neden:** Kullanıcı girdisi template motoruna (Jinja2, Freemarker, Twig)
  ifade olarak geçer. `{{7*7}}` → 49 dönerse zafiyet var; oradan `{{
  config.__class__... }}` gibi zincirlerle RCE.
- **Savunma:** Kullanıcı girdisini template'e *ifade* olarak verme; sadece veri
  olarak (context değişkeni) geçir. Sandbox'lı motorlar tam güvence değildir.

### 4.9. Command Injection / Path Traversal
- **Command injection:** Kullanıcı girdisi shell komutuna girer. `ping ` + host,
  host = `; rm -rf /`. **Savunma:** Shell'i hiç çağırma; argümanları dizi olarak
  exec'e ver (`execve`, `subprocess.run([...], shell=False)`); allow-list.
- **Path traversal:** `../../etc/passwd` ile dizin dışına çıkma. **Savunma:**
  Kanonik yol (canonicalize) çöz, kök dizin içinde kaldığını doğrula; dosya adını
  allow-list/whitelist ile sınırla; kullanıcı girdisini yol olarak kullanmaktan
  kaçın.

### 4.10. Diğer önemli sınıflar
- **Security Misconfiguration:** Varsayılan parola, açık debug modu, gereksiz
  açık servis, ayrıntılı hata mesajı (stack trace sızıntısı), açık S3 bucket.
  En sık ihlal nedenlerinden. **Savunma:** sıkılaştırma (hardening), güvenli
  varsayılanlar, config yönetimi, en az yetki.
- **Vulnerable/Outdated Components:** Bilinen açığı olan kütüphaneler (Log4Shell
  gibi). **Savunma:** SCA (Software Composition Analysis), bağımlılık tarama
  (`pip-audit`, `npm audit`, Dependabot), yama yönetimi, SBOM.
- **Identification & Authentication Failures:** Zayıf parola, MFA yokluğu, kötü
  session yönetimi (bkz. bölüm 3).
- **Software & Data Integrity Failures:** İmzasız güncelleme, güvenilmeyen
  CI/CD, supply chain (bağımlılık zehirleme). **Savunma:** imza doğrulama,
  pinned dependencies, güvenli pipeline.
- **SSRF** (ayrı madde olarak Top 10'a girdi — bkz. 4.4).
- **Logging & Monitoring Failures:** Saldırıyı görememek. Etkili log + tespit
  olmadan ihlaller aylarca fark edilmez (bkz. bölüm 10).

### 4.11. Web güvenliği için ortak zihniyet
- **Tüm girdi güvenilmezdir** — form, header, cookie, URL, dosya adı, JSON,
  hepsi. "Client-side validation" sadece UX'tir; güvenlik değildir. Sunucu her
  şeyi yeniden doğrular.
- **Allow-list > deny-list.** Neyin *geçerli* olduğunu tanımlamak, neyin *kötü*
  olduğunu saymaktan güvenlidir; kötü listesi her zaman eksiktir.
- **Veri ile kodu ayır** — injection sınıfının tamamının panzehiri budur.
- **Derinlemesine savunma** — WAF, CSP, en az yetki tek tek yetmez; birlikte.

---

## 5. Ağ Güvenliği

### 5.1. Temel model
TCP/IP katmanları ve her katmanın saldırı yüzeyi:
- **Link (L2):** ARP spoofing/poisoning → MITM (aynı LAN'da). MAC flooding.
  Savunma: dynamic ARP inspection, port security, 802.1X.
- **Internet (L3):** IP spoofing, ICMP kötüye kullanımı, routing saldırıları.
- **Transport (L4):** TCP SYN flood (DoS), port tarama, oturum ele geçirme.
- **Application (L7):** DNS spoofing, HTTP saldırıları, TLS downgrade.

### 5.2. Tanıma / keşif (reconnaissance)
- **Pasif:** Hedefe dokunmadan bilgi (OSINT, WHOIS, sertifika şeffaflık logları,
  Shodan, sızmış veriler, Google dorking).
- **Aktif:** Doğrudan sorgulama. **Nmap** temel araç: host keşfi, port tarama
  (`-sS` SYN, `-sV` sürüm, `-O` OS tespiti, `-sC` script). Açık portlar =
  çalışan servisler = saldırı yüzeyi.

### 5.3. MITM ve trafik saldırıları
- **Man-in-the-Middle:** Araya girip trafiği okuma/değiştirme. ARP poisoning,
  rogue AP, DNS spoofing ile. **Savunma:** her yerde TLS, sertifika doğrulama,
  HSTS, pinning; güvenli DNS (DoH/DoT), DNSSEC.
- **DNS saldırıları:** cache poisoning, spoofing, subdomain takeover (sahipsiz
  CNAME'e servis bağlama), tünelleme (DNS exfiltration/C2).

### 5.4. Ağ savunma mimarisi
- **Firewall:** Katman 3/4 (paket filtre) veya katman 7 (uygulama/NGFW).
  Varsayılan reddet (default deny), yalnız gerekeni aç.
- **Segmentation / mikrosegmentasyon:** Ağı bölgelere ayır (DMZ, iç, yönetim).
  Bir bölge düşse yatay hareket zorlaşır. Zero trust'ın ağ ayağı.
- **IDS/IPS:** Snort/Suricata (imza + anomali). IDS tespit eder, IPS engeller.
- **VPN:** Uzak erişimi şifreli tünelle. Ama VPN "iç ağa tam güven" demek
  olmamalı (zero trust yaklaşımı VPN'in ötesine geçer — ZTNA).
- **NAC (Network Access Control):** Ağa katılan cihazı doğrula (802.1X).

### 5.5. Kablosuz
WPA2/WPA3. WPA2-PSK zayıf parolada handshake yakalanıp offline kırılabilir
(hashcat). WPA3 SAE ile bunu zorlaştırır. Kurumsal: WPA2/3-Enterprise + RADIUS.
Evil twin / rogue AP tehdidi.

---

## 6. İşletim Sistemi Güvenliği ve Yetki Yükseltme

Initial access'ten sonra saldırganın hedefi genelde **yetki yükseltmedir**
(privilege escalation): sıradan kullanıcıdan root/SYSTEM'e.

### 6.1. Linux privilege escalation
Aranan zayıflıklar:
- **SUID/SGID binary'ler:** root olarak çalışan, kötüye kullanılabilir ikili
  dosyalar (GTFOBins referansı — hangi binary shell/dosya okuma verir). `find /
  -perm -4000` ile bulunur.
- **sudo yanlış yapılandırması:** `sudo -l` ile hangi komutları parolasız/başkası
  olarak çalıştırabildiğine bak; birçok komut (`vim`, `find`, `less`, `awk`)
  shell'e kaçış verir.
- **Yazılabilir cron/servis dosyaları,** zayıf dosya izinleri, PATH hijacking.
- **Capabilities:** `getcap -r /` — `cap_setuid` gibi tehlikeli yetenekler.
- **Kernel exploit'leri** (Dirty COW, Dirty Pipe gibi) — yamasız çekirdek.
- **Kimlik bilgisi avı:** config dosyaları, geçmiş (`.bash_history`), SSH
  anahtarları, `.env`, bellek.
Otomasyon: LinPEAS, linux-smart-enumeration.

### 6.2. Windows privilege escalation
- **Servis yanlış yapılandırması:** unquoted service path, zayıf servis izinleri
  (binary değiştirilebilir), otomatik başlayan yazılabilir servis.
- **Token impersonation:** SeImpersonatePrivilege → "Potato" saldırıları
  (JuicyPotato/PrintSpoofer) ile SYSTEM.
- **AlwaysInstallElevated,** saklı kimlik bilgileri (Credential Manager, registry,
  Unattend.xml, GPP cpassword).
- **UAC bypass,** DLL hijacking, zayıf registry/dosya ACL'leri.
Otomasyon: WinPEAS, PowerUp, Seatbelt.

### 6.3. Konteyner / sanallaştırma kaçışı
- **Container escape:** privileged konteyner, mount edilmiş docker socket
  (`/var/run/docker.sock`), tehlikeli capability (`CAP_SYS_ADMIN`), host
  namespace paylaşımı. Konteyner ≠ güvenlik sınırı olarak varsayma.
- **Savunma:** en az yetkili konteyner (non-root, read-only fs, drop
  capabilities, seccomp/AppArmor), socket'i mount etme, güvenlik bağlamı
  (PodSecurity), imaj tarama.

### 6.4. OS sıkılaştırma (hardening)
En az yetki, gereksiz servisleri kapat, düzenli yama, uygulama allow-listing
(AppLocker/WDAC), disk şifreleme (BitLocker/LUKS), güvenli boot, host firewall,
merkezi log, EDR. CIS Benchmark'lar somut sıkılaştırma rehberidir.

---

## 7. Active Directory Saldırıları

Kurumsal ağların çoğu Windows AD üstünde çalışır; kurumsal pentest'in kalbi
budur. AD, Kerberos kimlik doğrulamasına dayanır.

### 7.1. Kerberos temeli
- İstemci → **AS-REQ** → KDC, **TGT** (Ticket Granting Ticket) verir (kullanıcının
  parola hash'iyle şifreli kısım içerir).
- İstemci TGT ile → **TGS-REQ** → belirli servis için **service ticket** alır.
- Service ticket, servis hesabının parola hash'iyle şifrelenir → buradan
  saldırılar doğar.

### 7.2. Başlıca saldırılar
- **Kerberoasting:** Herhangi bir alan kullanıcısı, SPN'i olan servis hesapları
  için service ticket ister; ticket servis hesabının hash'iyle şifreli →
  offline kırma (zayıf servis hesabı parolası = felaket). Çok yaygın, çünkü
  yalnızca geçerli bir alan hesabı yeter.
- **AS-REP Roasting:** "Kerberos preauth" kapalı hesaplar için AS-REP alınıp
  offline kırılır.
- **Pass-the-Hash (PtH):** NTLM hash'i ele geçince parolayı bilmeden kimlik
  doğrula. NTLM'in doğası gereği hash = parola.
- **Pass-the-Ticket:** Çalınan Kerberos ticket'ını yeniden kullan.
- **Overpass-the-Hash / Pass-the-Key.**
- **Golden Ticket:** `krbtgt` hesabının hash'i ele geçerse, saldırgan istediği
  kullanıcı için **kendi TGT'sini** üretir → alan üzerinde kalıcı, neredeyse
  sınırsız erişim. **Silver Ticket:** belirli bir servis için sahte ticket.
- **DCSync:** Yeterli yetkiyle (Replicating Directory Changes) bir Domain
  Controller'ı taklit edip parola hash'lerini (krbtgt dahil) çeker.
- **Delegation abuse:** Unconstrained/constrained/resource-based delegation
  yanlış yapılandırmaları yetki yükseltmeye açar.
- **ACL/nesne izni istismarı:** GenericAll, WriteDACL gibi aşırı izinler zincir
  oluşturur.

### 7.3. Keşif ve savunma
- **BloodHound:** AD nesneleri arasındaki ilişkileri graf olarak çıkarır;
  "buradan Domain Admin'e giden en kısa yol" sorusunu cevaplar. Saldırgan ve
  savunmacı ikisi de kullanır.
- **Savunma:** güçlü servis hesabı parolaları (veya gMSA), tiered admin modeli
  (Tier 0/1/2 ayrımı), LAPS (yerel admin parola rotasyonu), Protected Users
  grubu, delegation'ları denetle, `krbtgt` parolasını düzenli iki kez döndür,
  NTLM'i azalt, ayrıcalıklı hesapları izle, aşırı ACL'leri temizle.

---

## 8. Binary Exploitation (İkili Sömürü)

Bellek güvenli olmayan dillerde (C/C++) bellek bozulması açıklarının sömürüsü.
Düşük seviye ama CTF'lerin ve ciddi zafiyet araştırmasının kalbi.

### 8.1. Bellek yerleşimi
Bir sürecin belleği: **stack** (yerel değişkenler, dönüş adresleri, aşağı büyür),
**heap** (dinamik `malloc`, yukarı büyür), **data/bss** (global), **text** (kod).
Sömürünün çoğu bu yapının bozulmasından doğar.

### 8.2. Stack buffer overflow
- **Kök neden:** Sınır kontrolü olmayan kopya (`strcpy`, `gets`, `sprintf`)
  tampon sınırını aşar; bitişik bellek — özellikle **saved return address** —
  ezilir.
- **Klasik sömürü:** Dönüş adresini saldırganın koduna (shellcode) veya bir
  gadget'a yönlendir → kontrol akışını ele geçir.
- **Savunmalar ve atlatmaları:**
  - **Stack canary:** Dönüş adresinden önce rastgele değer; ezilirse program
    çöker. Atlatma: canary sızıntısı, brute force (fork'lu serverda).
  - **DEP/NX (non-executable stack):** Stack'te kod çalıştırılamaz → shellcode
    çalışmaz. Atlatma: **ROP**.
  - **ASLR:** Bellek adresleri rastgeleleşir → gadget adresi bilinmez. Atlatma:
    bilgi sızıntısı (info leak) ile bir adres öğrenip taban hesapla; kısmi
    overwrite; brute force (32-bit'te).
  - **PIE, RELRO, CFG/CFI:** ek sertleştirmeler.

### 8.3. Return-Oriented Programming (ROP)
NX kod enjeksiyonunu engelleyince, saldırgan *var olan* kod parçalarını
("gadget" — `pop rdi; ret` gibi, `ret` ile biten diziler) zincirleyerek istediği
işlemi yapar. Stack'e gadget adresleri ve argümanlar dizilir. ret2libc,
ret2syscall, tam ROP chain. `pwntools` ve ROPgadget bu işin araçlarıdır.

### 8.4. Heap sömürüsü
Allocator'ın (glibc malloc/ptmalloc) meta verisini bozarak. **Use-after-free**
(serbest bırakılmış belleği kullanmak), **double free**, **heap overflow**,
tcache/fastbin poisoning, unlink saldırıları. Modern glibc'de birçok koruma var;
sömürü giderek zorlaşır ama devam eder.

### 8.5. Format string
`printf(user_input)` (format string'i kullanıcı verir) → `%x` ile bellek
sızıntısı, `%n` ile bellek *yazma* → kontrol ele geçirme. Savunma basit:
`printf("%s", user_input)`.

### 8.6. Diğer bellek hataları
Integer overflow → yanlış boyut → küçük tampon; off-by-one; type confusion;
uninitialized memory. Modern savunma: bellek-güvenli dil (Rust), sanitizer'lar
(ASan/UBSan), fuzzing (AFL++, libFuzzer).

---

## 9. Tersine Mühendislik ve Malware Analizi

### 9.1. Statik analiz
Çalıştırmadan inceleme: `strings`, `file`, PE/ELF header analizi (imports,
sections, entropy — yüksek entropi = paketli/şifreli), disassembler/decompiler
(**Ghidra** — ücretsiz, güçlü; IDA Pro; Binary Ninja; radare2/Cutter). Kontrol
akışı ve fonksiyonları anla. Avantaj: kodu çalıştırmadan görürsün. Dezavantaj:
obfuscation/packing ile zorlaşır.

### 9.2. Dinamik analiz
İzole ortamda (sandbox/VM, ağı kontrollü) çalıştırıp gözlemleme: debugger (x64dbg,
gdb/pwndbg), API çağrı izleme (Procmon, API Monitor), ağ trafiği (Wireshark,
inetsim ile sahte internet), davranış (dosya/registry/process değişiklikleri).
Avantaj: gerçek davranış görünür. Risk: kaçış/yayılma — mutlaka izole et.

### 9.3. Malware kavramları
- **Türler:** virus, worm (kendi yayılır), trojan, RAT, ransomware, rootkit
  (gizlenme), bootkit, keylogger, cryptominer, wiper.
- **C2 (Command & Control):** Bulaşmış makinelerin operatörle konuştuğu kanal;
  HTTP(S), DNS, domain fronting, beaconing (Cobalt Strike, Sliver). Tespitte
  düzenli aralıklı çıkış trafiği (beacon) aranır.
- **Kaçınma:** packing, polymorphism, anti-debug/anti-VM, process injection
  (DLL injection, process hollowing, reflective loading), LotL (living off the
  land — meşru araçlar: PowerShell, WMI, certutil; LOLBAS referansı), fileless.
- **Persistence:** run key, scheduled task, service, WMI subscription, startup
  folder, DLL search order.
- **IOC vs IOA:** Indicator of Compromise (hash, IP, domain — kırılgan) vs
  Indicator of Attack (davranış — daha dayanıklı). Modern tespit davranışa kayar
  (bkz. Pyramid of Pain: hash'i değiştirmek kolay, TTP'yi değiştirmek pahalı).

---

## 10. Mavi Takım — Tespit, İzleme, Müdahale

Saldırıyı bilmek yarısı; onu *görmek* ve *durdurmak* diğer yarısı.

### 10.1. Loglama ve görünürlük
Görmediğini savunamazsın. Kaynaklar: OS logları (Windows Event Log — özellikle
Security; Sysmon zengin telemetri verir), auth logları, ağ (firewall, DNS,
NetFlow), uygulama, bulut (CloudTrail). **Merkezileştir** (log tek yerde
toplanmalı; saldırgan yerelde silebilir). Zaman senkronu (NTP) şart.

### 10.2. SIEM ve tespit mühendisliği
- **SIEM** (Splunk, Elastic, Sentinel): logları toplar, korele eder, uyarı
  üretir. **SOAR** yanıtı otomatikleştirir.
- **Detection engineering:** Log gürültüsünden anlamlı tespit yazma sanatı.
  - **Sigma:** SIEM-bağımsız tespit kuralı formatı.
  - **YARA:** dosya/bellek desen imzaları (malware avı).
  - **Suricata/Snort:** ağ imzaları.
- İyi tespit **MITRE ATT&CK tekniğine** eşlenir; kapsama (coverage) ATT&CK
  matrisinde ölçülür.
- **False positive dengesi:** çok gürültülü uyarı = alarm yorgunluğu = kaçırılan
  gerçek olay. Tespit kalitesi hacimden önemlidir.

### 10.3. EDR ve threat hunting
- **EDR/XDR:** Endpoint davranışını izler (process ağacı, injection,
  şüpheli komut satırı). İmza değil davranış temelli.
- **Threat hunting:** Uyarı beklemeden hipotezle proaktif arama ("bu ortamda
  kerberoasting olsaydı nasıl görünürdü?"). Varsayım: saldırgan zaten içeride.

### 10.4. Olay müdahalesi (Incident Response)
Standart döngü (NIST/SANS):
1. **Preparation** — plan, araç, yetki, iletişim önceden hazır.
2. **Identification** — olay mı? kapsam?
3. **Containment** — yayılmayı durdur (izole et; kısa ve uzun vadeli).
4. **Eradication** — kök nedeni ve saldırganı temizle.
5. **Recovery** — sistemleri güvenle geri getir, izle.
6. **Lessons Learned** — post-mortem; suçlama değil, iyileştirme.
Önemli: containment'tan önce **delil koru** (uçucu veriden kalıcıya sırayla
topla — order of volatility). Panikle her şeyi kapatmak delili yok edebilir.

### 10.5. Dijital adli bilişim (Forensics)
- **Order of volatility:** önce en uçucu (CPU/register, RAM, ağ bağlantıları,
  süreçler), sonra disk, sonra loglar/arşiv.
- **Memory forensics:** Volatility ile RAM imajından süreç, injection, ağ,
  kimlik bilgisi çıkarımı.
- **Disk forensics:** dosya sistemi zaman damgaları, silinmiş dosya kurtarma,
  Windows artefaktları (prefetch, shellbags, jump lists, MFT, registry hives,
  amcache, `$UsnJrnl`).
- **Chain of custody:** delilin bütünlüğü (hash) ve el değiştirme kaydı — adli
  değeri için kritik.
- **Timeline analysis:** olayı zaman çizgisine oturt (super timeline — Plaso).

### 10.6. Purple team
Kırmızı (saldırı) ve mavi (savunma) birlikte çalışır: kırmızı bir tekniği
çalıştırır, mavi tespit edebiliyor mu bakılır, boşluk bulunursa tespit yazılır.
Atomic Red Team, Caldera gibi araçlarla ATT&CK tekniklerini kontrollü tetikleme.
Amaç yakalamak değil, savunmayı ölçüp iyileştirmek.

---

## 11. Uygulamalı Pentest Metodolojisi

Yetkili sızma testinin genel akışı (ör. PTES / OSCP zihniyeti):
1. **Scoping & yetki:** Yazılı izin (rules of engagement) olmadan test yok —
   yetkisiz test suçtur. Kapsam, hedefler, kısıtlar netleşir.
2. **Reconnaissance:** pasif + aktif bilgi toplama (bölüm 5.2).
3. **Enumeration:** servisleri, sürümleri, kullanıcıları, paylaşımları derinlemesine
   sırala. "Enumeration is key" — OSCP mottosu; çoğu giriş burada bulunur.
4. **Exploitation:** bulunan zafiyetten ilk erişim (initial foothold).
5. **Post-exploitation:** privilege escalation, credential harvesting,
   persistence, lateral movement, pivoting.
6. **Exfiltration hedefi / etki gösterimi** (kapsam dahilinde, veriyi
   sızdırmadan kanıt).
7. **Raporlama:** En değerli çıktı. Bulgular, risk seviyesi (CVSS), teknik
   ayrıntı, iş etkisi, tekrar-üretim adımları, **somut düzeltme önerileri**.
   Kötü rapor iyi testi çöpe atar.

Etik çerçeve: yalnızca yazılı yetkiyle, kapsam içinde, zarar vermeden, gizlilikle.
Bu bilgi savunma ve yetkili test içindir.

---

## 12. Sık Kullanılan Araçlar (kategori bazlı harita)

- **Recon/OSINT:** nmap, masscan, Shodan, Amass, theHarvester, Recon-ng.
- **Web:** Burp Suite (proxy — web testinin merkezi), OWASP ZAP, ffuf/gobuster
  (içerik keşfi), sqlmap (SQLi otomasyonu — dikkatli/yetkili), nikto.
- **Exploitation:** Metasploit, searchsploit/exploit-db, pwntools (binary).
- **Credential/kırma:** hashcat, John the Ripper, hydra (online brute — dikkatli).
- **AD:** BloodHound, Impacket (secretsdump, psexec, GetUserSPNs), CrackMapExec/
  NetExec, Rubeus, mimikatz.
- **C2/post-ex:** Cobalt Strike (ticari), Sliver, Havoc, Metasploit.
- **RE/malware:** Ghidra, IDA, x64dbg, gdb+pwndbg, radare2, Wireshark, Volatility,
  YARA.
- **Mavi takım:** Sysmon, Splunk/Elastic/Sentinel, Suricata/Zeek, Velociraptor,
  Sigma, Atomic Red Team.
- **Bulut:** ScoutSuite, Prowler, Pacu (AWS), kube-hunter/kube-bench (k8s).

Araçlar değişir, *kavramlar* kalıcıdır. Bir aracı değil, altındaki tekniği öğren;
araç yarın başkası olur.

---

## Kapanış notu

Siber güvenlik, sonsuz bir kedi-fare oyunudur; "bitti" yoktur. İyi uzman iki şeyi
birleştirir: **derin teknik anlayış** (bu belgedeki kavramlar) ve **saldırgan
gibi düşünme alışkanlığı** ("bunu nasıl kırarım?"). Savunmayı da saldırıyı da
bilmek gerekir — ama her zaman *yetki dahilinde ve etik sınırda*. Bu belge o
temeli kurar; derinleşme her alan için ayrı bir cilt gerektirir.
