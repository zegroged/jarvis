# Open Redirect (Açık Yönlendirme) Zafiyeti

## Tanım

Open Redirect, bir web uygulamasının kullanıcıyı başka bir adrese yönlendirirken, hedef adresi **saldırganın kontrol edebildiği bir girdiden** (URL parametresi, form alanı, header) almasından ve bu adresi yeterince doğrulamadan kullanmasından doğan bir zafiyettir. Türkçesiyle "açık yönlendirme": uygulama, sizi gitmek istediğiniz yere değil, saldırganın işaret ettiği yere götürür.

Klasik örnek şu biçimdeki bir bağlantıdır:

```
https://guvenilir-site.com/login?next=https://kotu-site.com/phish
```

Kullanıcı `guvenilir-site.com` alan adını görür, güvenir ve tıklar. Uygulama başarılı işlem sonrası `next` parametresindeki adrese yönlendirme yapar ve kurban aniden `kotu-site.com` üzerinde bulur kendini. Alan adı tanıdık olduğu için tıklama oranı yüksektir; asıl tehlike de buradadır.

Open Redirect tek başına çoğu zaman "düşük şiddetli" olarak etiketlenir çünkü doğrudan veri sızdırmaz. Ancak gerçekte bu zafiyet nadiren yalnız gezer: **phishing kampanyalarını meşrulaştıran**, **OAuth/OpenID Connect token'larını çalan** ve diğer zafiyetleri (SSRF, XSS, CSRF filtre atlatma) birbirine bağlayan bir "tutkal" görevi görür. Bu yüzden ciddiye alınması gereken bir sorundur.

## Kök Neden: Neden Böyle Oluyor?

Zafiyetin kökeninde tek ve basit bir hata yatar: **kontrol akışını belirleyen bir kararın, güvenilmeyen girdiye devredilmesi.**

Bir yönlendirme, HTTP düzeyinde genellikle `3xx` durum kodu ve bir `Location` header'ı ile gerçekleşir:

```
HTTP/1.1 302 Found
Location: https://kotu-site.com/phish
```

Ya da tarayıcı tarafında JavaScript ile:

```javascript
window.location = params.get("next");
```

Her iki durumda da tarayıcı, `Location`'daki veya `window.location`'a atanan adrese sorgusuz sualsiz gider. Tarayıcı için bu adres uygulamadan mı yoksa saldırgandan mı geldi ayrımı yoktur; o sadece emre uyar. Dolayısıyla güvenlik sınırı tamamen **uygulamanın hedef adresi kabul etmeden önce yaptığı doğrulamaya** dayanır. O doğrulama yoksa ya da zayıfsa, zafiyet doğar.

Peki neden geliştiriciler bu parametreyi kullanır? Çünkü meşru bir ihtiyaç vardır:

- **Login sonrası geri dönüş**: Kullanıcı korumalı bir sayfaya erişmek ister, login'e yönlendirilir, giriş yapınca istediği sayfaya geri dönmesi beklenir. Bunun için "nereye dönecek" bilgisi bir yerde tutulmalıdır ve en kolay yol URL parametresidir.
- **SSO / OAuth akışları**: `redirect_uri`, `RelayState`, `returnUrl` gibi parametreler protokolün kendisinin parçasıdır.
- **Tıklama takibi, çıkış sayfaları, kısa link servisleri**: `/exit?url=...` gibi ara yönlendiriciler.

İhtiyaç meşrudur; hata, bu ihtiyacı karşılarken **"kullanıcı ne yazarsa oraya giderim"** gevşekliğine düşmektir. Doğru yaklaşım, gidilebilecek yerleri önceden sınırlamaktır (allow-list), ki bu makalenin savunma bölümünün özüdür.

İkinci bir kök neden de **filtre yazmanın URL ayrıştırmadan zor olmasıdır.** Geliştiriciler "http ile başlıyorsa engelle", "kendi domainimi içeriyorsa izin ver" gibi naif kontroller yazar. URL grammar'ı ise şaşırtıcı derecede esnektir ve bu naif kontrollerin neredeyse tamamı atlatılabilir. Bu noktaya "yaygın hatalar" bölümünde ayrıntısıyla döneceğiz.

## Somut Örnekler

### Örnek 1: Login geri dönüş parametresi

Uygulama kodu (kavramsal):

```python
@app.route("/login")
def login():
    next_url = request.args.get("next", "/")
    if user_authenticated():
        return redirect(next_url)   # doğrulama yok — zafiyet burada
    return render_login_page()
```

Saldırgan şu bağlantıyı hazırlar ve e-posta ile gönderir:

```
https://banka.com/login?next=https://banka-com.kotu-site.net/oturum-dogrula
```

Kurban `banka.com` gördüğü için güvenir, giriş yapar. Uygulama girişi doğrular ve `next`'e yönlendirir. Kurban artık `banka-com.kotu-site.net` üzerindedir — görsel olarak bankanın birebir kopyası olan bir sayfada. Az önce girdiği parolayı yeniden girmesi istenir ve saldırgana teslim edilir.

Buradaki incelik: **phishing'in ilk adımı meşru sitede başladı.** Kullanıcı gerçekten `banka.com`'a giriş yaptı; bu güven duygusunu ikinci sahte sayfaya taşıdı.

### Örnek 2: OAuth token sızdırma (en tehlikeli senaryo)

OAuth 2.0 / OpenID Connect akışında `redirect_uri`, kimlik sağlayıcının (identity provider) kullanıcıyı ve — kritik olan — **authorization code veya access token'ı** geri göndereceği adrestir. Eğer authorization server, kayıtlı `redirect_uri`'leri gevşek eşleştirirse ya da istemci uygulamasının kendi içinde bir open redirect varsa, token doğrudan saldırgana akabilir.

Örneğin implicit flow'da token URL fragment'inde (`#access_token=...`) döner. Zincirleme senaryo şöyle işler:

```
1. Meşru istemcinin kayıtlı redirect_uri'si: https://app.com/callback
2. app.com/callback içinde bir open redirect var: 
   https://app.com/callback?next=<istenilen adres>
3. Saldırgan authorization isteğini bu callback'e yönlendirir; 
   token app.com'a gelir ama callback onu ?next hedefine taşır.
4. Token, saldırganın domain'ine sızar.
```

`redirect_uri` doğrulaması **tam eşleşme** yerine "başlangıç eşleşmesi" (`startsWith`) ile yapılıyorsa iş daha da kolaydır. Saldırgan `https://app.com.kotu-site.net` gibi bir adresle `startsWith("https://app.com")` kontrolünü geçirebilir. Bu yüzden OAuth spesifikasyonu `redirect_uri` için **tam string eşleşmesi** önerir; bu, allow-list mantığının protokol düzeyindeki karşılığıdır.

### Örnek 3: Header tabanlı ve JavaScript tabanlı yönlendirme

Sunucu tarafında `Location` header'ına doğrudan girdi yazmak (`Location: <kullanıcı girdisi>`) hem open redirect hem de — girdi yeni satır karakterleri içeriyorsa — HTTP response splitting riski taşır. İstemci tarafında ise:

```javascript
const dest = new URLSearchParams(location.search).get("returnTo");
location.href = dest;   // doğrulama yok
```

Burada ek bir tehlike var: eğer `dest` değeri `javascript:` şemasıyla başlıyorsa (`javascript:alert(document.cookie)`), bu artık yalnızca yönlendirme değil, doğrudan **DOM tabanlı XSS**'e dönüşür. Bu yüzden istemci tarafı yönlendirmelerinde şema kontrolü (yalnız `http`/`https`) ayrıca zorunludur.

## Sömürü Mantığı: Saldırgan Nasıl Düşünür?

Saldırganın amacı, **güvenilir alan adının itibarını ödünç alıp** kullanıcıyı ya da sırrı (token, cookie, parola) kendi kontrolüne çekmektir. Saldırı mantığı katmanlıdır:

**1. Güven aktarımı (phishing).** İnsanlar ve güvenlik ürünleri (e-posta filtreleri, URL reputation servisleri) bağlantının alan adına bakar. `https://tanidik-marka.com/...` ile başlayan bir link "temiz" görünür ve filtreleri geçer. Open redirect sayesinde saldırgan, kendi kötü sayfasını tanıdık markanın "arkasına" saklar. Kullanıcı da, otomatik güvenlik taraması da ilk domaine güvenir.

**2. Sır sızdırma (token/cookie).** Buradaki mekanizma daha derindir. Tarayıcı bir adrese yönlendiğinde, o sayfaya giden isteğe **`Referer` header'ı** eklenir ve önceki sayfanın URL'sini taşır. Eğer hassas bilgi (reset token, session id, OAuth code) URL'de bulunuyorsa ve sayfa saldırgan kontrolündeki bir domaine yönlendiriyorsa, bu bilgi `Referer` üzerinden saldırgana akabilir. OAuth'ta ise sır doğrudan `redirect_uri`'nin kendisine, query ya da fragment olarak yazılır — yukarıdaki Örnek 2. Bu, open redirect'i "düşük şiddet"ten "kritik" seviyeye taşıyan asıl senaryodur.

**3. Zincirleme (chaining).** Open redirect tek başına zayıf olsa bile başka zafiyetlerle birleşince güçlenir: SSRF filtrelerini atlatmak için (savunma sadece izinli bir domaine izin veriyorsa, o domaindeki open redirect ile başka yere sıçramak), CSP'yi ya da güvenli-domain beyaz listelerini dolaşmak için, ya da güvenlik ekiplerinin "sadece kendi domainimize giden linkler güvenli" varsayımını çürütmek için kullanılır.

Saldırganın atlatma tekniklerinin çoğu, savunmanın **string eşleştirme** yaparken URL'nin gerçek yapısını yanlış anlamasına dayanır. Bunları savunmayla yan yana ele alalım.

## Savunma: Allow-List Merkezli Yaklaşım

Temel ilke şudur: **Yönlendirme hedefini asla ham girdiden türetme; her zaman güvendiğin bir kümeye eşle.** Savunmayı katmanlar halinde inşa edin.

### 1. En sağlam yöntem: doğrudan URL almamak (indirection)

En güvenli tasarım, kullanıcıdan URL kabul etmemektir. Bunun yerine hedefi bir **token/anahtar** ile temsil edin:

```
/redirect?to=dashboard    →  sunucuda {"dashboard": "/app/dashboard"} eşlemesine bakılır
```

Saldırgan `to` değerine ne yazarsa yazsın, eşleme tablosunda olmayan bir anahtar reddedilir. Kullanıcı hiçbir zaman ham bir URL'yi kontrol edemez. Bu, allow-list'in en katı ve en güvenli biçimidir; mümkün olan her yerde tercih edilmelidir.

### 2. Relative path'e zorlamak

Login geri dönüş gibi senaryolarda hedef neredeyse her zaman **kendi sitenizin içindedir.** O halde harici adrese hiç izin vermeyin: girdinin **yalnızca path** olmasını dayatın, mutlak URL'yi (scheme veya host içereni) reddedin.

Kritik incelik: girdinin tek bir `/` ile başlaması yetmez. `//kotu-site.com` biçimindeki **protocol-relative URL**, tarayıcı için `https://kotu-site.com` demektir ve harici bir adrestir. Benzer şekilde `/\kotu-site.com`, `/%2F%2Fkotu-site.com`, veya backslash varyantları da atlatma amaçlıdır. Doğru kontrol: girdi tek `/` ile başlamalı, ama `//` veya `/\` ile başlamamalı; ayrıca decode edilip yeniden kontrol edilmeli.

```python
from urllib.parse import urlparse, unquote

def guvenli_yerel_path(gelen):
    aday = unquote(gelen or "")
    p = urlparse(aday)
    # host ya da scheme varsa harici demektir — reddet
    if p.scheme or p.netloc:
        return "/"
    # tek / ile baslamali, // veya /\ olmamali
    if not aday.startswith("/") or aday.startswith("//") or aday.startswith("/\\"):
        return "/"
    return aday
```

### 3. Harici domain gerekiyorsa: kesin allow-list

Bazı durumlarda (SSO ortakları, iş ortağı siteleri) harici yönlendirme gerçekten gerekir. O zaman izin verilen hedefleri **tam host bazında** beyaz listeye alın ve karşılaştırmayı doğru katmanda yapın:

```python
IZINLI_HOSTLAR = {"partner.com", "app.partner.com"}

def guvenli_harici(gelen):
    p = urlparse(gelen)
    if p.scheme not in ("https",):          # yalnız https
        return None
    host = (p.hostname or "").lower()        # ayristirilmis host — string arama DEGIL
    if host in IZINLI_HOSTLAR:               # tam esitlik
        return gelen
    return None
```

Buradaki üç kural savunmanın kalbidir:

- **Ayrıştırılmış host üzerinde çalış**, ham string üzerinde `contains`/`startsWith` yapma. `urlparse(...).hostname` gerçek host'u verir; saldırganın `@`, `#`, `\`, kullanıcı-bilgisi hilelerini tarayıcıyla aynı biçimde çözer.
- **Tam eşitlik** kullan (`==` veya küme üyeliği), `startsWith`/`endsWith` değil. `endsWith(".partner.com")` gibi bir kontrol bile `evil-partner.com` ya da `partner.com.kotu.net` gibi varyasyonlarla dikkatlice test edilmeli; en güvenlisi host'lar kümesine tam üyeliktir.
- **Şemayı beyaz listele**: yalnız `https` (ve gerekiyorsa `http`). `javascript:`, `data:`, `file:` gibi şemaları kesinlikle reddet — bunlar XSS ve yerel kaynak erişimine kapı açar.

### 4. OAuth'a özel savunma

OAuth/OIDC için authorization server tarafında `redirect_uri` **tam string eşleşmesiyle** doğrulanmalı; wildcard veya prefix eşleşmesinden kaçınılmalı. `state` parametresi CSRF'e karşı zorunludur ve kontrol edilmelidir. Hassas token'ı URL fragment'inde döndüren implicit flow yerine, mümkünse **Authorization Code + PKCE** akışı tercih edilmelidir; bu, sızan bir code'un tek başına işe yaramamasını sağlar.

### 5. Kullanıcıyı uyaran ara sayfa (interstitial)

Harici bir adrese yönlendirmek zorundaysanız ve allow-list mümkün değilse, en azından bir **ara uyarı sayfası** gösterin: "guvenilir-site.com'dan ayrılıyorsunuz, gideceğiniz adres: kotu-site.com. Devam et?" Bu, sessiz otomatik yönlendirmenin sağladığı gizliliği bozar; kullanıcı kötü adresi görür. Bu bir savunma katmanıdır, tek başına yeterli değildir ama phishing'in görünmezliğini ortadan kaldırır.

## Yaygın Hatalar

Bu hataların her biri, savunmanın URL'nin gerçek yapısını yanlış anlamasından doğar:

- **`startsWith` / `contains` ile kontrol.** "URL benim domainimle başlıyorsa güvenli" mantığı `https://benim-site.com.kotu.net` ile atlatılır. "URL içinde benim domainim geçiyorsa güvenli" ise `https://kotu.net/?x=benim-site.com` ile atlatılır. Host'u ayrıştırmadan yapılan hiçbir string kontrolüne güvenilmez.

- **Sadece `http://` / `https://` engelleyip protocol-relative'i unutmak.** `//kotu-site.com` scheme içermez ama tarayıcı onu harici mutlak URL olarak yorumlar. Backslash varyantları (`\/\/`, `/\`) da tarayıcıların URL normalizasyonu nedeniyle atlatma sağlar.

- **`@` ve kullanıcı-bilgisi hilesini gözden kaçırmak.** `https://benim-site.com@kotu-site.com/` adresinde gerçek host `kotu-site.com`'dur; `benim-site.com` yalnızca userinfo kısmıdır. Naif göz (ve naif regex) `benim-site.com` görür, tarayıcı `kotu-site.com`'a gider.

- **Tek kez decode edip bırakmak.** `%2F%2Fkotu-site.com` decode edilince `//kotu-site.com` olur. Bir katman decode eden ama sonra yeniden kontrol etmeyen filtreler atlatılır. Ayrıca çift encode (`%252F`) da hesaba katılmalıdır.

- **Şema doğrulamasını atlamak.** İstemci tarafı yönlendirmelerinde `javascript:`, `data:` şemalarını engellememek, open redirect'i doğrudan XSS'e yükseltir.

- **OAuth'ta gevşek `redirect_uri` eşleşmesi.** Prefix veya wildcard eşleşme, token sızmasının en yaygın gerçek dünya sebebidir.

- **"Zaten düşük şiddetli" diye ertelemek.** Zincirleme potansiyeli (phishing meşrulaştırma, token sızdırma) göz ardı edilerek düzeltme geciktirilir.

## En İyi Pratikler

- **Varsayılan olarak URL kabul etme.** Yönlendirme hedefini anahtar/token ile temsil et (indirection); ham URL en son çare olsun.
- **İç yönlendirmelerde yalnız relative path'e izin ver.** `//`, `/\`, scheme ve host içeren her girdiyi reddet; decode edip yeniden doğrula.
- **Harici hedefler için tam host allow-list uygula.** Ayrıştırılmış `hostname` üzerinde tam eşitlikle karşılaştır; `startsWith`/`contains`'e asla güvenme.
- **Şemayı beyaz listele.** Yalnız `https` (gerekiyorsa `http`); `javascript`, `data`, `file` şemalarını engelle.
- **OAuth'ta `redirect_uri`'yi tam string eşleşmesiyle doğrula**, `state` kontrolü yap, Authorization Code + PKCE tercih et.
- **Hassas veriyi URL'de taşıma.** Reset token, session id gibi sırları query string'e koyma; koyman gerekiyorsa `Referrer-Policy: no-referrer` gibi başlıklarla sızıntı yüzeyini daralt.
- **Girdiyi ayrıştır, string'le uğraşma.** Doğrulamayı olgun bir URL kütüphanesinin çıkardığı bileşenler üzerinde yap; kendi regex'ini yazma dürtüsüne diren.
- **Ara uyarı sayfası** kullan (allow-list mümkün değilse) ve **loglama/izleme** ekle: beklenmedik harici yönlendirme denemelerini kaydet, bunlar aktif saldırının erken işaretidir.
- **Test et.** `//evil.com`, `/\evil.com`, `https://site.com@evil.com`, `%2f%2fevil.com`, `javascript:...` gibi klasik payload'ları düzenli olarak regresyon testlerine koy.

## Özet

Open Redirect, kontrol akışını güvenilmeyen girdiye devretme hatasıdır. Kök nedeni basit olsa da sonuçları — güvenilir markanın arkasına saklanan phishing ve OAuth token sızdırma — ciddidir. Tek gerçek çözüm, hedefi ham girdiden türetmeyi bırakıp **önceden tanımlı bir allow-list'e** eşlemektir: mümkünse indirection ile, iç bağlantılarda relative-path zorlamasıyla, harici bağlantılarda ayrıştırılmış host üzerinde tam eşitlik kontrolüyle. String eşleştirmeye ve naif filtrelere dayanan her savunma er ya da geç atlatılır; URL'yi gerçekten ayrıştıran ve kapalı bir izin kümesine dayanan savunma ise sağlam kalır.
