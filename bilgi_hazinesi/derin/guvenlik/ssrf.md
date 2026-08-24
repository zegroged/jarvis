# Server-Side Request Forgery (SSRF) — Derin Dalış

Bu metin, SSRF'i "tanım + önlem listesi" düzeyinde değil; kodun içinde, ağ paketinin gerçek hedefinde ve saldırganın zihnindeki adım adım kararlar düzeyinde inceler. Amaç eğitim ve savunmadır: mekanizmayı, tespiti ve dayanıklı savunma tasarımını kavramak. Canlı bir saldırı reçetesi değil, savunmacının sömürüyü anlamadan neden kaybettiğini gösteren bir çalışma metnidir.

---

## 1. Çözümlü yürüyüş: bir link-önizleme özelliğinin çöküşü

Somut bir örnek üzerinden gidelim; çünkü SSRF, soyut anlatıldığında "URL doğrula, bitsin" gibi görünen, ama her katmanda yeni bir kapı açan bir zafiyettir.

Senaryo: bir SaaS uygulaması, kullanıcı bir bağlantı yapıştırınca "link preview" (bağlantı önizleme) üretiyor. Sunucu, verilen URL'ye gidip başlık ve açıklama meta etiketlerini (`og:title`, `og:description`) çekiyor. Bu, LinkedIn'den Slack'e kadar her yerde olan, tamamen masum görünen bir özellik.

### 1.1. Zafiyetli kod (gerçek, çalışır)

Node.js/Express ile yazılmış tipik bir ilk sürüm:

```javascript
// preview.js — ZAFİYETLİ SÜRÜM
const express = require("express");
const axios = require("axios");
const cheerio = require("cheerio");

const app = express();
app.use(express.json());

app.post("/api/preview", async (req, res) => {
  const { url } = req.body;

  if (!url) {
    return res.status(400).json({ error: "url gerekli" });
  }

  try {
    // Kullanıcının verdiği URL'ye doğrudan gidiyoruz.
    const response = await axios.get(url, { timeout: 5000 });
    const $ = cheerio.load(response.data);

    const preview = {
      title: $('meta[property="og:title"]').attr("content") || $("title").text(),
      description: $('meta[property="og:description"]').attr("content") || "",
      // Hata durumunda içeriği de dönüyoruz — bu in-band sızıntıyı ağırlaştırır.
      raw: response.data.slice(0, 500),
    };

    res.json(preview);
  } catch (err) {
    // Hata mesajı da bilgi sızdırır: bağlantı reddedildi mi, timeout mu?
    res.status(502).json({ error: err.message, code: err.code });
  }
});

app.listen(3000);
```

Geliştiricinin kafasındaki varsayım tek cümledir: "Kullanıcı bir blog veya haber URL'si girecek." Bu varsayım, kodun her satırında örtük olarak vardır ve tam da bu varsayım zafiyetin kendisidir.

### 1.2. Sorun kavramsal olarak nasıl doğar?

Saldırgan `url` alanına bir haber sitesi değil, şunu gönderir:

```
http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

Sunucu itaatkârdır. `axios.get`, kullanıcının sunucusunun içinden, o link-local metadata adresine gider. Bu adres yalnızca instance'ın kendisinden erişilebilir olduğu için, dışarıdan hiç ulaşılamayan bir kaynağı saldırgan artık sunucuyu proxy olarak kullanarak okur. `raw` alanı sayesinde metadata yanıtı doğrudan JSON cevabında geri döner — bu **in-band SSRF**'tir.

Sorunun kökü ağ katmanındaki örtük güvendir: metadata servisi, "bana instance içinden geldiyse güvenilirdir" varsayar ve kimlik doğrulaması istemez. Uygulama sunucusu bu güvenilir çevrenin bir üyesidir. Saldırgan, SSRF ile bu güvenilir üyeyi kiralık bir kurye yapar.

Dikkat çeken üç ayrı hata var ve her biri bağımsız olarak ölümcül:

1. **Hedef hiç doğrulanmıyor** — `url` ne olursa olsun gidiliyor.
2. **Yanıt gövdesi geri dönüyor** (`raw`) — kör olması gereken bir sızıntı in-band'e dönüşüyor.
3. **Hata mesajı geri dönüyor** (`err.message`, `err.code`) — hedef doğrulama eklense bile, `ECONNREFUSED` ile `ETIMEDOUT` farkı iç port taraması için yeterli sinyal verir (blind SSRF oracle'ı).

### 1.3. Düzeltilmiş kod (resolve-then-connect + allow-list)

Naif düzeltme "URL'yi regex ile kontrol et" olurdu; ama bu, ilerideki bölümlerde göreceğimiz DNS rebinding, redirect ve alternatif IP gösterimleriyle atlatılır. Dayanıklı düzeltme, alan adını **bir kez** çözüp o IP'yi doğrulamak ve **tam olarak o doğrulanmış IP'ye** bağlanmaktır. Böylece "kontrol ettiğim adres" ile "bağlandığım adres" arasındaki TOCTOU boşluğu kapanır.

```javascript
// preview.js — DÜZELTİLMİŞ SÜRÜM
const express = require("express");
const axios = require("axios");
const cheerio = require("cheerio");
const dns = require("dns").promises;
const net = require("net");
const ipaddr = require("ipaddr.js");

const app = express();
app.use(express.json());

// Yasak (private/link-local/loopback/reserved) aralıklar.
function isDisallowedIp(ipStr) {
  let addr;
  try {
    addr = ipaddr.parse(ipStr);
  } catch {
    return true; // Ayrıştırılamayan adres = güvenilmez.
  }
  // IPv4-mapped IPv6 (::ffff:127.0.0.1) numarasını IPv4'e indir.
  if (addr.kind() === "ipv6" && addr.isIPv4MappedAddress()) {
    addr = addr.toIPv4Address();
  }
  const range = addr.range();
  // "unicast" dışındaki her şey (private, loopback, linkLocal,
  // uniqueLocal, reserved, carrierGradeNat...) reddedilir.
  return range !== "unicast";
}

async function safeFetch(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error("gecersiz URL");
  }

  // 1. Şema kısıtı: yalnızca http/https.
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("yalnizca http/https izinli");
  }

  // 2. Alan adını BİR KEZ çöz. Tüm dönen IP'leri kontrol et.
  const { address, family } = await dns.lookup(parsed.hostname, { verbatim: true });
  if (isDisallowedIp(address)) {
    throw new Error("hedef IP yasak aralikta");
  }

  // 3. Bağlanırken host header'ı orijinal olsun ama BAĞLANTI
  //    doğrulanmış IP'ye gitsin. axios/http'de bunu lookup'ı
  //    sabitleyerek yaparız: ikinci bir DNS çözümlemesine izin verme.
  const pinnedLookup = (hostname, opts, cb) => {
    // Host header ile eşleşmeyen bir yeniden-çözümlemeyi engelle:
    // her zaman ilk doğruladığımız adrese bağlan.
    cb(null, address, family);
  };

  const response = await axios.get(rawUrl, {
    timeout: 5000,
    maxRedirects: 0, // 4. Redirect'i takip ETME; her adım yeniden doğrulanmalı.
    lookup: pinnedLookup,
    // Yanıt boyutunu sınırla (zip-bomb / büyük iç sayfa koruması).
    maxContentLength: 512 * 1024,
    validateStatus: (s) => s >= 200 && s < 300,
  });

  return response.data;
}

app.post("/api/preview", async (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "url gerekli" });

  try {
    const html = await safeFetch(url);
    const $ = cheerio.load(html);
    // 5. İçeriği ve ham gövdeyi GERİ DÖNDÜRME — yalnızca beklenen alanlar.
    res.json({
      title: $('meta[property="og:title"]').attr("content") || $("title").text() || "",
      description: $('meta[property="og:description"]').attr("content") || "",
    });
  } catch (err) {
    // 6. Genel hata; iç sinyal (ECONNREFUSED/ETIMEDOUT farkı) sızdırma.
    res.status(400).json({ error: "onizleme uretilemedi" });
  }
});

app.listen(3000);
```

Bu sürüm neden dayanıklı? Çünkü savunma artık string kontrolünde değil: (a) alan adı bir kez çözülüyor, (b) çözülen gerçek IP private/link-local/reserved aralıklarına karşı doğrulanıyor, (c) `pinnedLookup` ile HTTP istemcisinin ikinci bir DNS çözümlemesi yapması engelleniyor — DNS rebinding penceresi kapanıyor, (d) redirect takibi kapalı, (e) yanıt gövdesi ve hata detayı sızdırılmıyor.

Kritik incelik: `maxRedirects: 0` şart. Aksi hâlde saldırgan `http://zararsiz.com/` verir, o URL 302 ile `http://169.254.169.254/...`'e yönlendirir ve `pinnedLookup` yalnızca ilk hostname'i sabitlediği için redirect hedefi yeniden çözülüp iç adrese gidebilir. Redirect'i uygulama içinde döngüyle takip etmek istiyorsak, her adımın hedefini `safeFetch`'ten geçirmemiz gerekir.

İkinci incelik: bu bile tek başına yeterli "savunma" sayılmamalı. Kod katmanı atlatılabilir; asıl kale, bir sonraki bölümlerde göreceğimiz **ağ egress kontrolüdür**. Uygulama kodu ilk savunma hattı, egress ise son ve en sağlam hattır.

---

## 2. Gerçek dünya: CVE kayıtlarında SSRF nasıl görünür?

SSRF, akademik bir tehdit değil; küçük eklentiden büyük CMS'e kadar sahada onlarca yıldır tekrarlanan bir desendir. Verilen gerçek kayıtlardan üçü, zafiyetin farklı "evrelerini" güzelce gösteriyor.

### CVE-2013-0235 — WordPress XMLRPC pingback ile iç ağ tarama

Bu, SSRF'in "ders kitabı" örneklerinden biridir. **CVE-2013-0235**, WordPress 3.5.1 öncesindeki XMLRPC API'sini ilgilendirir: uzak saldırganlar, bir pingback için özenle hazırlanmış (crafted) bir **kaynak URL** belirterek WordPress sunucusunu iç ağdaki (intranet) sunuculara HTTP isteği yaptırabiliyor ve bu yolla **port taraması** gerçekleştirebiliyordu. Kayıt bunu açıkça bir "Server-Side Request Forgery (SSRF)" sorunu olarak tanımlar.

Buradaki mekanizma, 1. bölümdeki link-preview senaryosunun bire bir kardeşidir: pingback özelliği, "başka bir sitenin bana link verdiğini doğrulamak için o siteye gideyim" der. Saldırgan bu "git" davranışını iç adreslere yönlendirir. Yanıtın tamamı geri dönmese bile (blind'e yakın), **zamanlama ve hata farkları** bir port-tarama oracle'ı oluşturur: açık port ile kapalı port, kabaca farklı sürelerde/farklı hatalarla cevaplanır. Savunma açısından dersi nettir: "sunucunun başkasının URL'sine gitmesi" gereken her özellik, potansiyel bir SSRF ilkelidir (primitive).

### CVE-2012-10018 — Mapplic WordPress eklentisinde SSRF → XSS zinciri

**CVE-2012-10018**, Mapplic ve Mapplic Lite WordPress eklentilerini (sırasıyla 6.1 ve 1.0 dâhil ve öncesi sürümler) etkileyen, **CWE-918 (Server-Side Request Forgery)** olarak sınıflandırılmış, CVSS v3.1 puanı **8.3 (HIGH)** olan bir kayıttır. İlginç yanı: SSRF burada tek başına "veri çalma" için değil, bir **SVG dosyası isteyerek nihayetinde XSS** gerçekleştirmek için zincirleniyor. Yani sunucu, saldırganın istediği bir kaynağı çekiyor; çekilen içerik SVG olduğunda içindeki script bağlamı tetiklenerek zafiyet bir cross-site scripting sonucuna dönüşüyor.

Bu kayıt önemli bir dersi somutlaştırır: **SSRF sonucu her zaman "metadata çalmak" değildir.** Bazen sunucunun getirdiği içeriğin *türü* (content-type) ve *nereye render edildiği* asıl silahtır. 1. bölümdeki düzeltmede yanıt gövdesini geri döndürmemenin ve içerik türünü daraltmanın neden önemli olduğu tam olarak budur — sunucunun getirdiği yabancı içeriği güvenli bir bağlamda değerlendirdiğinizden emin olmak, SSRF-zincir yüzeyini küçültür.

### CVE-2007-6758 — feed-proxy: "proxy" ismi zaten uyarıdır

En eski kayıt olan **CVE-2007-6758**, extjs 5.0.0'daki `feed-proxy.php`'de bir SSRF zafiyetini tanımlar. Dosyanın adı bile hikâyeyi anlatır: **feed-proxy**. Yani uygulama, kullanıcı adına bir feed'i "proxy'leyen", yani başka bir adresten çekip getiren bir bileşen. Bu tür "proxy", "fetch", "loader", "import", "gateway", "preview" adlı bileşenler, mimarideki SSRF için doğal mıknatıslardır; çünkü tanımları gereği kullanıcının işaret ettiği bir hedefe giderler. Bir kod tabanında SSRF avlarken bu isimler ilk bakılacak yerlerdir.

Ayrıca verilen kayıtlardan CVE-2010-1105, CVE-2010-1106, CVE-2010-1113, CVE-2010-1114 ve CVE-2010-1115'in birincil CWE'leri SSRF değil (XSS, remote/local file inclusion, directory traversal); bunlar aynı zafiyet ailelerinin (dosya/URL parametresini kötüye kullanma) komşularıdır ve genelde SSRF ile aynı "kullanıcı bir kaynak adresi kontrol ediyor" kök nedenini paylaşırlar. Bu komşuluk tesadüf değil: bir parametre "nereden okuyacağımı" belirliyorsa; o parametre LFI/RFI/traversal ya da SSRF'e — hedefin yerel dosya mı yoksa ağ adresi mi olduğuna göre — dönüşebilir.

---

## 3. Karşılaştırma / karar: hangi savunmayı ne zaman?

SSRF savunmasında birden çok yaklaşım var ve hepsi aynı değil. Doğru mimari, bunları takaslarıyla bilerek katmanlamaktır.

### 3.1. Deny-list vs. Allow-list (girdi katmanı)

| Ölçüt | Deny-list ("kötü adresleri engelle") | Allow-list ("yalnızca iyi adreslere izin ver") |
|---|---|---|
| Güvenlik varsayılanı | Güvensiz (unutulan her şey açık) | Güvenli (tanımsız her şey kapalı) |
| Atlatma yüzeyi | Çok geniş (alt IP gösterimleri, IPv6, rebinding, redirect) | Dar |
| Bakım | Sürekli "yeni kötü adres" ekleme yarışı | Hedef değişince güncelleme |
| Uygulanabilirlik | Hedef kümesi öngörülemezse tek seçenek gibi görünür | Hedef kümesi bilinebiliyorsa ideal |

Karar: hedef kümesi bilinebiliyorsa (webhook yalnızca belirli sağlayıcılara gider, importer yalnızca belirli domainlerden çeker) **her zaman allow-list**. Deny-list yalnızca hedefin gerçekten açık uçlu olduğu (örneğin "kullanıcı herhangi bir blog'u önizleyebilsin") durumlarda, o zaman da tek başına değil, resolve-then-connect + egress kontrolü ile birlikte kullanılmalı.

### 3.2. Uygulama katmanı doğrulama vs. Ağ egress kontrolü

- **Uygulama katmanı (kodda IP doğrulama, şema kısıtı, rebinding koruması):** avantajı, zengin bağlam (hangi kullanıcı, hangi özellik) ve anlamlı hata mesajları verebilmesi. Dezavantajı: kırılgan; tek bir kod yolu (yeni eklenen bir "export" endpoint'i) doğrulamayı atlarsa savunma çöker.
- **Ağ egress kontrolü (firewall/egress proxy ile iç aralıklara çıkışı bloklamak):** avantajı, uygulama mantığındaki tüm hileleri (rebinding, redirect, alternatif gösterim) **anlamsızlaştırması** — kontrol artık gerçek paketin gerçek hedefinde. Dezavantajı: bağlamdan yoksun (kim/neden bilmez), yapılandırması altyapı ekibinin işi, ve "meşru dış istek" ile "kötü dış istek" ayrımını yapamaz (sadece *nereye* ayrımını yapar).

Karar: bunlar rakip değil, **tamamlayıcı**dır. Uygulama katmanı ilk hat ve kullanıcıya anlamlı davranış; egress katmanı ise "kod hata yaparsa yakalayan ağ". Ciddi bir sistemde ikisi de bulunmalı. Tek birini seçmek zorunda kalırsanız (asla kalmayın), egress daha az atlatılır.

### 3.3. IMDSv1 vs. IMDSv2 (bulut metadata sertleştirme)

- **IMDSv1:** tek `GET` ile kimlik bilgisi verir. Basit bir SSRF (tek GET yapabilen zafiyet) bile sömürür.
- **IMDSv2:** önce `PUT` ile session token alıp onu sonraki isteklerde header'da göndermeyi zorunlu kılar. Çoğu SSRF yalnızca basit GET yapabildiği ve keyfî header/metod ekleyemediği için bu, SSRF'in yeteneklerinin dışına çıkar. Ek olarak token TTL'i ve düşük hop-limit getirir.

Karar: bulutta her zaman IMDSv2'yi **zorunlu (required)** moda al ve IMDSv1'i **kapat**. "v2'yi açtık" ile "v1'i kapatıp yalnızca v2'yi zorunlu kıldık" arasında dünya kadar fark var: v1 açık kaldıkça saldırgan eski yolu kullanır ve v2 hiçbir koruma sağlamaz.

### 3.4. Merkezî egress proxy vs. dağıtık kod içi doğrulama

- **Merkezî egress proxy (tüm dış istekler tek bir sertleştirilmiş proxy'den geçer):** tek yerde doğrulama, tek yerde loglama, tek yerde allow-list. Ölçeklenebilir ve denetlenebilir. Dezavantajı: proxy tek arıza/atlatma noktası olur ve doğru kurulması gerekir.
- **Dağıtık kod içi doğrulama (her servis kendi `safeFetch`'ini çağırır):** başlangıçta kolay ama zamanla tutarsızlaşır — bir servis günceller, diğeri unutur. "Bir kez doğru yaz, her yerde kullan" için ortak bir kütüphane ve zorunlu code-review gerekir.

Karar: büyük/çok servisli mimaride merkezî egress proxy + ortak istemci kütüphanesi kazanır; küçük tek uygulamada iyi test edilmiş bir `safeFetch` yeterli olabilir.

---

## 4. Hata-modu kataloğu: geliştiricilerin ve savunmacıların tipik hataları

1. **Deny-list'e güvenmek.** "127.0.0.1 ve 169.254.169.254'ü engelledik" demek; alternatif IP gösterimleri, IPv6, `0.0.0.0`, iç aralıkların tamamı ve DNS rebinding düşünülmediği için neredeyse her zaman atlatılır.

2. **URL'yi ham string olarak kontrol etmek.** `startsWith("http://legit.com")` gibi kontroller `http://legit.com@169.254.169.254/` userinfo hilesiyle veya kodlama farklarıyla kandırılır. Doğrulama çözülmüş IP üzerinde yapılmalı, ham string üzerinde değil.

3. **DNS'i iki kez çözmek.** Doğrulama sırasında bir çözümleme, asıl istek sırasında ayrı bir çözümleme yapmak; bu tam olarak DNS rebinding'in (TOCTOU) açtığı kapıdır. Çözüm: bir kez çöz, o IP'ye pinle.

4. **Redirect'leri körü körüne takip etmek.** İlk URL doğrulanır ama HTTP istemcisi 3xx yönlendirmesini otomatik izleyip iç adrese gider. `maxRedirects: 0` ya da her adımı yeniden doğrulama şart.

5. **Yalnızca IPv4 düşünmek.** `::1`, `::ffff:127.0.0.1` (IPv4-mapped) ve IPv6 unique-local aralıkları atlanırsa savunma yarım kalır. IPv4-mapped adresleri IPv4'e indirip yeniden kontrol etmek gerekir.

6. **Şemayı kısıtlamamak.** `http`/`https` beklenirken `file://`, `gopher://`, `dict://`, `ftp://` gibi şemalara izin vermek; `gopher://` ham byte gönderebildiği için kimlik doğrulaması olmayan Redis'e komut yazmaya kadar gider. Allow-list ile yalnızca `http`/`https`.

7. **Yanıt gövdesini/hata detayını geri döndürmek.** 1. bölümdeki `raw` alanı ve `err.message`/`err.code` gibi ayrıntılar, kör olması gereken bir SSRF'i in-band sızıntıya çevirir ve iç port taraması için oracle sağlar. Yanıtı beklenen alanlara daralt, hatayı genelleştir.

8. **Blind SSRF'i "zararsız" saymak.** "Yanıt dönmüyor, o hâlde risk yok" varsayımı yanlıştır. CVE-2013-0235'te olduğu gibi kör SSRF ile port taraması ve durum değiştiren (state-changing) POST istekleri hâlâ mümkündür; out-of-band sinyallerle bilgi de sızdırılabilir.

9. **IMDSv2'yi açıp IMDSv1'i açık bırakmak.** v2 etkin ama v1 hâlâ kabul ediliyorsa saldırgan eski yolu kullanır; koruma yok denecek kadar azdır. v1 mutlaka kapatılmalı.

10. **Aşırı geniş IAM rolleri.** Metadata çalınırsa hasar tamamen rolün yetkisiyle orantılıdır. Geniş rol, önemsiz görünen bir link-preview SSRF'ini tam hesap devralmaya çevirir. En az yetki, sızıntının "patlama yarıçapını" küçültür.

11. **SSRF'i yalnızca uygulama katmanında savunmak.** Ağ egress kontrolü olmadan tek bir kod yolu hatası (yeni eklenen bir endpoint) tüm savunmayı çökertir. Kod ilk hat, egress son hat olmalı.

12. **İçerik türünü ve render bağlamını göz ardı etmek.** CVE-2012-10018'in gösterdiği gibi, sunucunun getirdiği içerik SVG/HTML olduğunda SSRF bir XSS'e zincirlenebilir. Getirilen yabancı içeriğin content-type'ını daraltmamak ve onu güvenli olmayan bir bağlamda değerlendirmek, SSRF yüzeyini büyütür.

13. **"Proxy/fetch/import/preview" adlı bileşenleri tehdit modellemesine almamak.** CVE-2007-6758'deki `feed-proxy.php` gibi, adı bile "başkasının URL'sine gidiyorum" diyen bileşenler doğal SSRF mıknatıslarıdır; kod tabanında bunlar özel dikkat ve zorunlu `safeFetch` gerektirir.

14. **Test/staging ortamında egress kısıtını gevşetip üretime taşımak.** Geliştirici kolaylığı için açılan bir egress kuralının üretime sızması, tüm ağ savunmasını sessizce etkisiz kılabilir; ortam parite (parity) denetimi şarttır.

---

## Kapanış

SSRF, tek başına küçük görünen bir özelliğin (bir URL indirmek) modern bulut ve mikroservis mimarisindeki örtük güven ilişkileriyle birleşince nasıl port taramasına, metadata hırsızlığına, XSS zincirine ve nihayetinde hesap devralmaya kadar gidebildiğinin en net örneğidir. Kayıtlar bunu on yıllar boyunca tekrarlar: 2007'de `feed-proxy.php`, 2013'te WordPress pingback, günümüze yakın Mapplic eklentisi. Değişen teknoloji, sabit kalan kök neden: **kullanıcı bir hedef adresi kontrol ediyor ve sunucu onu yeterince doğrulamadan o hedefe gidiyor.** Doğru savunma tek bir kontrolle değil; resolve-then-connect ile DNS pinleme, şema/redirect kısıtı, yanıt/hata sızıntısını kesme, ağ seviyesinde egress allow-list, bulutta IMDSv2 zorunluluğu ve en az yetkili IAM rollerinin birlikte oluşturduğu katmanlı bir mimariyle kurulur.
