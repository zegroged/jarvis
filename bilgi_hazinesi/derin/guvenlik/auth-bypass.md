# Kimlik Doğrulama Atlatma — Derin Dalış

Özet makale kimlik doğrulama atlatmayı (authentication bypass) dört yüzey üzerinden kavramsal olarak ele aldı: mantık hataları, response manipülasyonu, forced browsing ve 2FA bypass. Bu derin dalış aynı zemini tekrar etmez; onun yerine tek bir gerçekçi akışı **satır satır kodla** ele alır, gerçek CVE kayıtlarında bu hataların sahada nasıl göründüğünü gösterir, savunma tasarımlarını takaslarıyla karşılaştırır ve geliştiricilerin tekrar tekrar düştüğü hataların kataloğunu çıkarır.

Kimlik doğrulama atlatmanın kök karakteri şudur: saldırgan bir parolayı kırmaz, doğrulama sürecinin **mantığındaki** boşluğu kullanır. Bu yüzden bu sınıf zafiyetler kriptografik değil, **durum (state) ve güven sınırı (trust boundary)** sorunudur. Aşağıdaki her kod örneği bu iki ekseni somutlaştırmak için seçildi.

---

## 1. Çözümlü yürüyüş

Gerçekçi bir senaryo üzerinden gideceğiz: **parola sıfırlama akışı**. Bu akış, kimlik doğrulama atlatmanın neredeyse tüm klasik hatalarını tek bir yüzeyde toplar — token doğrulama, nesne sahipliği, oturum durumu ve rate limiting. Kod Python/Flask ile yazılmıştır çünkü mantık her dilde aynıdır; kusur çerçeveye değil tasarıma aittir.

### 1.a — Zafiyetli / hatalı kod

Aşağıdaki `reset_password` endpoint'i ilk bakışta makul görünür: bir token üretir, e-postayla gönderir, sonra token'ı doğrulayıp yeni parolayı yazar.

```python
import hashlib
import secrets
from flask import Flask, request, jsonify

app = Flask(__name__)

# Basitleştirilmiş "veritabanı"
users = {
    "alice@example.com": {"password_hash": "...", "id": 1},
    "bob@example.com":   {"password_hash": "...", "id": 2},
}
# Üretilen sıfırlama token'ları: token -> email
reset_tokens = {}


@app.route("/reset/request", methods=["POST"])
def reset_request():
    email = request.json.get("email")
    if email in users:
        # 6 haneli, tahmin edilebilir "token"
        token = str(secrets.randbelow(1000000)).zfill(6)
        reset_tokens[token] = email
        send_email(email, f"Sıfırlama kodunuz: {token}")
    # Kullanıcının var olup olmadığını sızdırmamak için hep aynı yanıt
    return jsonify({"message": "E-posta gönderildi"}), 200


@app.route("/reset/confirm", methods=["POST"])
def reset_confirm():
    token = request.json.get("token")
    email = request.json.get("email")          # <-- KUSUR 1
    new_password = request.json.get("new_password")

    if token in reset_tokens:                   # <-- KUSUR 2: token'ın email'e ait olup
        users[email]["password_hash"] = hash_pw(new_password)  #    olmadığı kontrol edilmiyor
        return jsonify({"message": "Parola değişti"}), 200

    return jsonify({"error": "Geçersiz token"}), 400
```

Bu kodda **dört** ayrı atlatma yüzeyi vardır ve hepsi birbirinden bağımsız olarak sömürülebilir:

- **Kusur 1 — Hedef kullanıcı istemciden geliyor.** `email` alanı token'dan türetilmiyor, istemcinin gönderdiği veriden okunuyor. Sunucu "bu token kime ait?" diye `reset_tokens[token]`'a bakmak yerine, istemcinin dilediği e-postayı kabul ediyor.

- **Kusur 2 — Nesne sahipliği doğrulanmıyor.** `if token in reset_tokens` yalnızca token'ın *var* olup olmadığını sorar, o token'ın *gönderilen email'e ait* olup olmadığını değil. Saldırgan kendi hesabı için geçerli bir token alır (`bob@example.com`), sonra `confirm` isteğine `email: "alice@example.com"` yazar. Token geçerlidir (bob'un token'ı), ama parola alice'in olarak sıfırlanır. Bu tam da özet makalede tanımlanan "kullanıcı karıştırma" mantık hatasıdır — burada kodla somutlaşmış hâli.

- **Kusur 3 — Token entropisi düşük.** `secrets.randbelow(1000000)` yalnızca 10^6 olasılık üretir. `confirm` endpoint'inde rate limiting yoktur; saldırgan bir milyon değeri makul sürede deneyebilir. Token kriptografik olarak güçlü üretilse bile (secrets modülü CSPRNG'dir), **çıktının aralığı** onu zayıflatır.

- **Kusur 4 — Token tek kullanımlık ve kısa ömürlü değil.** Başarılı sıfırlamadan sonra `reset_tokens`'tan silinmiyor; süre sınırı yok. Sızmış bir token süresizce yeniden kullanılabilir.

### 1.b — Sorun kavramsal olarak nasıl ortaya çıkıyor?

Buradaki asıl hata teknik bir yazım hatası değil; **güven sınırının yanlış yere çizilmesidir.** Geliştirici zihninde akış şöyle işliyor: "Kullanıcı e-postasındaki linke tıklar, link doğru token ve doğru e-postayı taşır, ben ikisini de alırım." Bu, mutlu yolun (happy path) doğru tanımı. Ancak saldırgan e-postadaki linke tıklamaz; `confirm` isteğini elle kurar ve iki parametreyi **birbirinden bağımsız** kontrol edebilir. Geliştirici token ile e-posta arasında örtük bir bağ olduğunu varsaydı; saldırgan bu bağın sunucuda **doğrulanmadığını** fark etti.

Kök soru her zaman aynı: "Bu güvenlik kararı hangi veriye dayanıyor ve o veri kimin kontrolünde?" Burada karar (kimin parolasının değişeceği) istemcinin kontrolündeki `email` alanına dayanıyor. Doğru tasarımda hedef kullanıcı **yalnızca token'dan** türetilmeli, çünkü token sunucunun ürettiği ve tek doğru kaynak (source of truth) olan nesnedir.

### 1.c — Düzeltilmiş / doğru kod

```python
import secrets
import time

# token -> {email, expires_at, used}
reset_tokens = {}
TOKEN_TTL = 900  # 15 dakika


@app.route("/reset/request", methods=["POST"])
def reset_request():
    email = request.json.get("email")
    if email in users:
        # Yüksek entropili token: 256-bit, tahmin edilemez
        token = secrets.token_urlsafe(32)
        reset_tokens[token] = {
            "email": email,
            "expires_at": time.time() + TOKEN_TTL,
            "used": False,
        }
        send_email(email, f"Sıfırlama linkiniz: https://app/reset?token={token}")
    return jsonify({"message": "E-posta gönderildi"}), 200


@app.route("/reset/confirm", methods=["POST"])
@rate_limit(max_attempts=5, per="ip_and_token")   # brute-force sınırı
def reset_confirm():
    token = request.json.get("token")
    new_password = request.json.get("new_password")
    # DİKKAT: 'email' artık istemciden ALINMIYOR

    record = reset_tokens.get(token)
    if record is None:
        return jsonify({"error": "Geçersiz token"}), 400
    if record["used"]:
        return jsonify({"error": "Token zaten kullanıldı"}), 400
    if time.time() > record["expires_at"]:
        return jsonify({"error": "Token süresi doldu"}), 400

    # Hedef kullanıcı SADECE token'dan türetiliyor — güven sınırı sunucuda
    email = record["email"]

    if not password_policy_ok(new_password):
        return jsonify({"error": "Parola politikası"}), 400

    users[email]["password_hash"] = hash_pw(new_password)
    record["used"] = True            # tek kullanımlık: anında geçersizleşir
    invalidate_all_sessions(email)   # sıfırlama sonrası açık oturumları düşür
    return jsonify({"message": "Parola değişti"}), 200
```

Değişikliklerin her biri bir kusurun karşılığıdır:

- Hedef kullanıcı istemciden değil `record["email"]`'den, yani token'dan türetiliyor → **kullanıcı karıştırma imkânsız.**
- `token_urlsafe(32)` ≈ 256-bit entropi → brute-force pratikte olanaksız.
- `rate_limit` dekoratörü token/IP başına deneme sınırlıyor → düşük entropi ihtimaline karşı ikinci savunma hattı (defense in depth).
- `used` bayrağı ve `expires_at` → token tek kullanımlık ve kısa ömürlü.
- `invalidate_all_sessions` → saldırgan zaten bir oturum açtıysa parola sıfırlama onu da düşürür (hesap ele geçirme sonrası kalıcılığı kırar).

Dikkat edilmesi gereken incelik: bu düzeltmelerin hiçbiri kriptografi değildir. Hepsi **durum yönetimi ve güven sınırı** düzeltmesidir. Zafiyetli kodda `secrets` modülü zaten kullanılıyordu; sorun kriptonun zayıflığı değil, kararın yanlış veriye bağlanmasıydı.

---

## 2. Gerçek dünya (CVE ile)

Yukarıdaki soyut hatalar sahada tam olarak nasıl görünür? Verilen gerçek CVE kayıtlarından üçü, bu derin dalışın üç ayrı temasını demirliyor.

### Eksik/yarım yama teması — CVE-2002-0870

Bu kayıt, kimlik doğrulama atlatmada en sinsi kalıbı gösterir: **bir bypass'ı yamalamak, aynı bypass'ın bir varyantını açık bırakabilir.** CVE-2002-0870, Cisco Content Service Switch 11000 serisindeki daha eski bir kimlik doğrulama atlatma zafiyetinin (CVE-2001-0622) yamasının **eksik** olduğunu kaydeder. Uzak saldırgan, web yönetim arayüzünde adım adım gezinmek yerine yönetim URL'sini **doğrudan isteyerek** ek ayrıcalık elde edebiliyordu. Bu, özet makaledeki forced browsing'in ta kendisidir: arayüzde gösterilmeyen ama sunucuda korumasız duran bir yönetim endpoint'ine doğrudan istek.

Buradaki ders çift katmanlıdır. Birincisi, kök neden klasik forced browsing / eksik fonksiyon-seviyesi erişim kontrolüdür — 1.a'daki Kusur 2 ve özet makaledeki "URL bilinmiyorsa güvenli" yanılgısıyla aynı ailedendir. İkincisi ve daha öğreticisi: ilk yama, saldırının yalnızca *bilinen bir yolunu* kapattı, kök nedeni (doğrudan URL erişiminde eksik yetki kontrolü) değil. İki CVE numarasının aynı zafiyete atanması (2001-0622 → 2002-0870), "belirli girdiyi engelleme" (blacklist) yaklaşımının neden "kararı doğru yerde verme" (default-deny) yaklaşımına yenildiğinin canlı kanıtıdır.

### Zincirleme ve "kimlik doğrulaması gerektiren" yanılgısı — CVE-2006-1087

CVE-2006-1087, PHP-Stats 0.1.9.1'de `admin.php` içindeki `modify_config` işleminde bir static code injection kaydeder: `option_new[compatibility_mode]` parametresi filtrelenmeden `config.php`'ye yazılıyordu. İlk okumada bu bir kod enjeksiyonu gibi görünür ve kaydın kendisi bunu "remote authenticated administrators" (uzaktan kimliği doğrulanmış yöneticiler) tarafından sömürülebilir diye tanımlar. Ama kaydın NOT kısmı asıl dersi verir: bu zafiyet, **kimliği doğrulanmamış** saldırganlar tarafından, `option[admin_pass]` **authentication bypass** zafiyetiyle **zincirlenerek** sömürülebilir.

Bu, kimlik doğrulama atlatmanın neden tek başına değil bir **etki çarpanı** olarak değerlendirilmesi gerektiğini gösterir. "Bu endpoint sadece admin'e açık, o yüzden güvenli" varsayımı, admin kapısının kendisi atlanabildiğinde çöker. Savunma tarafında çıkarım: bir enjeksiyon kusurunu "yalnızca yetkili kullanıcı erişebilir" diye düşük öncelikli saymak tehlikelidir; kimlik doğrulama katmanı bir bypass ile düşerse, "yetkili-only" kusur bir anda "kimlik doğrulamasız uzaktan kod yürütme"ye terfi eder. Derinlemesine savunma tam da bunun için vardır: her katman diğerinin çökeceğini varsayarak tasarlanır.

### Aygıt/gömülü sistemlerde parse (ayrıştırma) hatası — CVE-2007-5383

CVE-2007-5383, Thomson/Alcatel SpeedTouch 7G router'da (BT Home Hub'da kullanılan) çarpıcı bir örnek verir: intranetteki saldırgan, `cgi/b` yoluna giden `PATH_INFO`'nun sonuna bir `/` (slash) karakteri ekleyerek kimlik doğrulamayı atlayıp yönetici erişimi elde ediyordu — kayıtta "double-slash auth bypass" olarak adlandırılıyor. Ayrıca kayıt, intranet dışındaki saldırganların bunu ayrı bir CSRF zafiyetiyle (bkz. CVE-2007-5384) birleştirebileceğini not eder.

Bu kaydın öğrettiği kök neden, 1.b'deki güven sınırı sorununun bir varyantıdır ama farklı bir mekanizmayla: **yol ayrıştırma (path parsing) ile yetkilendirme mantığının uyumsuzluğu.** Erişim kontrolü katmanı bir URL'yi bir biçimde normalize ederken (örneğin "bu yol korumalı mı?"), asıl istek işleyici aynı yolu **başka bir biçimde** çözümler. Sona eklenen bir `/` iki katmanın yolu farklı görmesine yol açar: yetki katmanı "bu korumalı bir yol değil" der, işleyici ise korumalı kaynağı servis eder. Bu, "parser differential" (ayrıştırıcı farkı) sınıfının klasik örneğidir ve gömülü cihazlarda, ters vekil (reverse proxy) + uygulama sunucusu ikililerinde bugün de tekrarlanır. CVE-2007-5383 ile CVE-2007-5384'ün birlikte anılması, ayrıca 1.a'daki temayı pekiştirir: tek başına "yalnızca intranet" görünen bir bypass, bir CSRF ile zincirlenince internete açılır.

Bu üç kayıt birlikte okunduğunda ortaya çıkan tablo: kimlik doğrulama atlatma nadiren tek ve izole bir hatadır. Ya eksik bir yama (2002-0870), ya bir zincirin halkası (2006-1087), ya da iki katman arasındaki bir yorum farkıdır (2007-5383) — ve neredeyse her zaman başka bir zafiyetle birleşince tam etkisine ulaşır.

---

## 3. Karşılaştırma / karar

Kimlik doğrulama atlatmaya karşı savunma tasarımında birkaç temel eksende seçim yaparsınız. Her seçimin bir takası vardır; "her zaman en iyisi" olan yoktur, bağlama bağlıdır.

### 3.a — Erişim kontrolü: default-deny (allowlist) vs. default-allow (blacklist)

**Default-deny (varsayılan reddet):** Hiçbir endpoint açıkça izin verilmedikçe erişilemez. Yeni bir route eklendiğinde, geliştirici bilinçli olarak yetki kuralı tanımlamak zorundadır; unutursa endpoint erişilemez kalır (fail-closed).

**Default-allow (varsayılan izin):** Endpoint'ler açıktır; korunması gerekenler tek tek "engelle" listesine eklenir.

Takas: default-deny geliştiriciyi yorar (her endpoint için açık kural), ama unutma hatasını **güvenli tarafa** düşürür. CVE-2002-0870'in gösterdiği "yamayı unuttuk" senaryosu tam olarak default-allow zihniyetinin ürünüdür. Karar kuralı: **kimlik doğrulama söz konusu olduğunda daima default-deny.** Default-allow yalnızca gerçekten herkese açık (public) içerik sunan, hiçbir yetki sınırı olmayan sistemlerde savunulabilir.

### 3.b — Yetki kontrolünün yeri: merkezi middleware vs. endpoint-başına kontrol

**Merkezi (middleware/filter):** Yetki kararı tek bir katmanda, tüm isteklerin geçtiği bir kapıda verilir.

**Dağıtık (her handler kendi kontrolünü yapar):** Her endpoint kendi yetki mantığını içerir.

Takas: merkezi katman tutarlılık ve "unutma"ya karşı yapısal koruma sağlar; ama fazla merkezileşme, endpoint'e özgü ince yetki kurallarını (örneğin "kullanıcı yalnızca kendi kaydını görebilir") ifade etmekte zorlanır — bu tür kurallar kaynak-seviyesi (object-level) bilgi gerektirir. Pratikte doğru cevap **iki katmanlı**dır: kaba yetki (bu kullanıcı bu endpoint sınıfına erişebilir mi?) merkezi middleware'de; ince yetki (bu kullanıcı *bu* nesneye erişebilir mi?) handler'da nesne sahipliği kontrolüyle. CVE-2007-5383'ün parser-differential dersi burada kritik: merkezi katman ile handler **aynı yol normalizasyonunu** kullanmalı, yoksa iki katman aynı isteği farklı görür.

### 3.c — Kaynak varlığını gizleme: 403 vs. 404

Var olan ama yetkisiz bir kaynağa `403 Forbidden` dönmek kaynağın *var olduğunu* sızdırır; `404 Not Found` dönmek varlığı gizler.

Takas: `404` numaralandırma (enumeration) saldırılarını zorlaştırır ama hata ayıklamayı ve meşru kullanıcı deneyimini bozabilir; `403` dürüsttür ama bilgi sızdırır. Karar kuralı: bu **ikincil** bir önlemdir. Asıl koruma erişim kontrolüdür; `404`'e "güvenlik" olarak güvenmek, forced browsing'in beslendiği "obscurity" yanılgısına geri dönmektir. Yüksek hassasiyetli kaynaklarda (örneğin başka kullanıcıların nesne ID'leri) `404` tercih edilir; genel yönetim panellerinde fark çoğunlukla önemsizdir çünkü asıl savunma zaten erişimi engellemektir.

### 3.d — Rate limiting boyutu: IP-başına vs. hesap/kimlik-başına

**IP-başına:** Tek IP'den gelen istek sayısı sınırlanır.

**Hesap/token-başına:** Belirli bir hesaba veya token'a yönelik deneme sayısı sınırlanır.

Takas: IP-başına sınır dağıtık kaba kuvveti (botnet, IP rotasyonu) durduramaz — saldırgan her denemeyi farklı IP'den yapar. Hesap-başına sınır bu boşluğu kapatır ama bu sefer meşru kullanıcıyı kilitleme (account lockout) yoluyla bir DoS yüzeyi açar. 1.a'daki 6-haneli token örneği tam olarak hesap-başına sınırın eksikliğinden ölümcüldü. Karar kuralı: **ikisini birlikte** kullan; hesap-başına sınıra ek olarak, kilitleme yerine kademeli gecikme (exponential backoff) veya CAPTCHA ile DoS riskini azalt.

### 3.e — Oturum durumu modeli: tek-durum vs. çok-durum

**Tek-durum:** "Giriş yapıldı" tek bir boolean'dır.

**Çok-durum:** "Parola doğrulandı, 2FA bekleniyor" ile "tam doğrulandı" ayrı durumlardır.

Takas neredeyse yok — çok-durum modeli biraz daha karmaşıktır ama 2FA adım-atlama saldırısını (özet makaledeki en kritik 2FA bypass) yapısal olarak imkânsızlaştırır. Karar kuralı: 2FA/MFA olan her sistemde **çok-durumlu oturum zorunlu.** Yarım oturumla hiçbir korumalı endpoint'e erişilememeli.

---

## 4. Hata-modu kataloğu

Aşağıdaki hatalar, kimlik doğrulama atlatma zafiyetlerinin arkasındaki en sık tekrarlanan geliştirici/savunmacı yanlışlarıdır. Her biri yukarıdaki koda, CVE'lere veya karar eksenlerine bağlanır.

1. **Hedef kullanıcıyı istemciden almak.** Parola sıfırlama, hesap işlemleri veya yetki kararlarında etkilenecek kullanıcıyı istekteki bir parametreden (örneğin `email`, `user_id`) okumak; token'dan veya oturumdan türetmek yerine. 1.a'daki Kusur 1 — kullanıcı karıştırmanın kökü.

2. **Nesne sahipliğini doğrulamamak.** Bir token, kayıt veya kaynak üzerinde işlem yaparken "bu talep edene mi ait?" sorusunu atlamak. `if token in tokens` yeterli değildir; `tokens[token].owner == current_user` gerekir. Hem mantık hatasının hem IDOR'un ortak kökü.

3. **Güvenlik kararını istemci yanıtına bağlamak.** Sunucunun `{"authenticated": false}` gibi bir bayrak döndürüp kararı istemciye bırakması. Saldırgan proxy'de bayrağı çevirir. Response manipülasyonunun tamamı ve 2FA bypass'ın büyük kısmı bu tek hatadan doğar.

4. **"URL gizliyse güvenli" (security through obscurity) sanmak.** Yönetim panelini menüden kaldırıp korumasız bırakmak. CVE-2002-0870'in forced browsing yüzeyi tam olarak budur; kaynak sunucuda korunmalı, gizlenmemeli.

5. **Bypass'ı kök neden yerine belirti düzeyinde yamamak.** Bilinen tek bir saldırı yolunu (belirli bir girdi, belirli bir URL) engelleyip kök nedeni (eksik yetki kontrolü) bırakmak. CVE-2001-0622 → CVE-2002-0870 zinciri bu hatanın canlı örneğidir; blacklist daima bir varyant bırakır.

6. **Oturum durumlarını ayırt etmemek.** "Parola doğrulandı ama 2FA bekliyor" ile "tam doğrulandı"yı aynı saymak. Korumalı endpoint yarım oturumla erişilebilir olunca 2FA adım-atlama ortaya çıkar.

7. **Rate limiting'i yalnızca IP başına uygulamak.** Hesap/token-başına sınır olmadan, IP rotasyonuyla kaba kuvvet aşılır. 1.a'daki düşük entropili token bu eksiklikle ölümcül hâle geldi.

8. **Token/OTP entropisini düşük tutmak veya tek-kullanımlık yapmamak.** 6-haneli, süresi dolmayan, kullanıldıktan sonra geçersizleşmeyen token'lar. Sızmış veya tahmin edilmiş bir değer defalarca kullanılabilir. 1.a'daki Kusur 3 ve 4.

9. **Yol/parse normalizasyonunda katmanlar arası tutarsızlık.** Yetki katmanı ile istek işleyicinin aynı URL'yi farklı çözümlemesi (trailing slash, `%2e`, çift slash, null byte). CVE-2007-5383'ün "double-slash" bypass'ı ve CVE-2005-4147'nin trailing-null-byte (`%00`) atlatması bu ailedendir — parser differential yetkilendirmeyi delip geçer.

10. **"Yalnızca yetkili erişebilir" diye ikincil kusurları küçümsemek.** Bir enjeksiyon veya tehlikeli işlemi "sadece admin çağırabilir" diye düşük öncelikli saymak. Kimlik doğrulama bir bypass ile düşerse, o kusur kimlik doğrulamasız uzaktan sömürüye terfi eder. CVE-2006-1087'nin zincirleme notu tam bu tuzağı gösterir.

11. **Kurtarma ve alternatif giriş yollarını ana akıştan zayıf bırakmak.** Güçlü 2FA ama zayıf "cihazımı kaybettim" akışı; ya da 2FA gerektirmeyen bir sosyal/SSO yan kapısı. Saldırgan güçlü kapıyı değil, en zayıf halkayı seçer. Zincir en zayıf halkası kadar güçlüdür.

12. **Hassas işlemlerde yeniden doğrulama (step-up) istememek.** 2FA'yı kapatma, parola/e-posta değiştirme, güvenli cihaz ekleme gibi işlemleri mevcut güçlü bir doğrulama olmadan çalıştırmak. Bir kez ele geçirilmiş yarım oturum, kalıcı ele geçirmeye dönüşür.

13. **Parola sıfırlama sonrası açık oturumları düşürmemek.** Saldırgan zaten bir oturum açtıysa, kurbanın parolayı değiştirmesi onu atmaz. 1.c'deki `invalidate_all_sessions` bu boşluğu kapatır; eksikliği, hesap kurtarmayı yanıltıcı biçimde etkisiz kılar.

14. **Fiziksel/yerel erişim varsayımlarını gözden kaçırmak.** Bazı bypass'lar ağdan değil fiziksel yakınlıktan gelir: CVE-2008-0706 (HP Compaq dizüstü BIOS'unda power-on parolasının atlatılması) ve CVE-2006-7163 (DreameeSoft Password Master'ın master parola ayarlı olsa bile veritabanını şifresiz saklaması) bunu gösterir. "Kimlik doğrulama var" demek, altındaki verinin veya donanımın da korunduğu anlamına gelmez.

---

## Kapanış

Kimlik doğrulama atlatmanın bu derin dalışta tekrar tekrar ortaya çıkan iki kök ekseni vardı: **güven sınırının nerede çizildiği** (karar hangi veriye dayanıyor, o veri kimin kontrolünde?) ve **durumun nasıl yönetildiği** (oturum yarım mı tam mı, token kullanıldı mı, adımlar zorunlu mu?). 1.a'daki dört kusur, üç CVE'nin sahadaki görünümü ve karar eksenlerinin tümü bu iki eksene indirgenir.

Pratik özü tek cümlede: **kararı sunucuda, doğru veriye (token/oturum) dayanarak ver; durumu net ayır; varsayılan olarak reddet.** Bunu yapan bir sistemde bu yazıdaki tekniklerin çoğu yapısal olarak — tek tek yama gerektirmeden — etkisiz kalır. CVE-2002-0870'in öğrettiği gibi, belirtiyi yamamak yeni varyantlar doğurur; kök nedeni (yanlış güven sınırı, kötü durum yönetimi) düzeltmek ise sınıfı bir bütün olarak kapatır.
