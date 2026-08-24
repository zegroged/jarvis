# Web Cache Deception (Web Önbellek Aldatması)

## Tanım

**Web Cache Deception (WCD)**, bir saldırganın önbellek (cache) katmanını kandırarak, aslında kullanıcıya özel ve hassas olan dinamik bir yanıtı *statik bir kaynakmış gibi* önbelleğe yazdırdığı bir zafiyet sınıfıdır. Önbelleğe yazılan bu yanıt daha sonra başka kişiler (veya saldırganın kendisi) tarafından geri okunabildiğinde, kurbanın oturum bilgileri, profil verileri, API anahtarları, CSRF token'ları veya diğer gizli içerikleri ifşa olur.

Tekniğin çekirdeği tek bir yanlış anlaşılmaya dayanır: **önbellek katmanı ile origin (kaynak) sunucu, bir isteğin "önbelleklenebilir olup olmadığına" farklı kurallarla karar verir.** Saldırgan bu iki karar mekanizması arasındaki uyumsuzluğu (parser discrepancy) sömürür.

### WCD, Web Cache Poisoning'den nasıl ayrılır?

Bu iki tekniği ayırmak kritik önem taşır, çünkü modern CDN/edge-cache mimarilerinde sıkça birbirine karıştırılırlar:

| Boyut | Web Cache Poisoning | Web Cache Deception |
|-------|---------------------|---------------------|
| **Amaç** | Önbelleğe *zararlı içerik* enjekte etmek | Önbellekten *hassas veri sızdırmak* |
| **Kurban** | Önbelleklenmiş sayfayı sonradan çeken *herkes* | Genellikle yanıtı önbelleklenen *tek bir kullanıcı* |
| **Zehirlenen anahtar** | Saldırganın kontrol ettiği unkeyed girdi (header vb.) | Kurbanın kendi kimlikli yanıtı, saldırganca okunabilir URL'de |
| **Yön** | Saldırgan → önbellek → mağdur (içerik iter) | Mağdur → önbellek → saldırgan (içerik çeker) |
| **Tetikleyici** | Cache key'e girmeyen bir girdinin yanıtı etkilemesi | Cache key ile origin routing arasındaki path/uzantı uyuşmazlığı |

Kısaca: **Poisoning "içeri kötü şey koyar", Deception "dışarı gizli şey çıkarır".** İkisi de cache-key ve origin arasındaki bir mantık farkını sömürür, ama saldırının yönü ve hedefi tamamen zıttır.

## Kök Neden ve Çalışma Mantığı

WCD'nin var olabilmesi için genellikle üç koşulun aynı anda sağlanması gerekir.

### 1. Path-based cache kuralları (uzantıya göre önbellekleme)

Birçok CDN ve reverse proxy, performans için "statik varlıkları" agresif şekilde önbellekler. Bu kural çoğu zaman **URL yolunun uzantısına (extension)** bakılarak uygulanır: `.css`, `.js`, `.jpg`, `.png`, `.ico`, `.woff` gibi uzantılarla biten yollar "statik" kabul edilip, yanıttaki `Cache-Control` başlıkları bazen *ezilerek* önbelleğe alınır.

Sorun şu: Önbellek bu kararı verirken **yanıtın içeriğine değil, yalnızca URL'nin yüzeysel görünümüne** bakar. Origin sunucu ise aynı URL'yi bambaşka yorumlayabilir.

### 2. Origin'in path'i "esnek" yorumlaması (path confusion)

Asıl zafiyeti doğuran şey, uygulama sunucusunun (origin) bir URL yolunu, önbelleğin varsaydığından farklı bölmesidir. Klasik senaryo şudur:

Kurban normalde şu sayfaya erişir:
```
https://hedef.com/hesap/ayarlar
```
Bu, kullanıcının oturum çerezleriyle kimlikli, gizli bir sayfadır (isim, e-posta, telefon, belki API anahtarı içerir).

Saldırgan kurbanı şu URL'ye yönlendirir:
```
https://hedef.com/hesap/ayarlar/kotu.css
```

Burada iki farklı yorum çatışır:

- **Origin sunucu** birçok framework'te (özellikle yol sonundaki fazladan segmenti yok sayan veya `PATH_INFO` mantığıyla çalışan uygulamalarda) bu isteği hâlâ `/hesap/ayarlar` handler'ına yönlendirir. `kotu.css` kısmı ya yok sayılır ya path parametresi olarak ele alınır. Sonuçta origin, **hassas ayarlar sayfasının tam içeriğini** üretir ve kurbanın çerezleriyle doldurur.
- **Önbellek katmanı** ise URL'nin `.css` ile bittiğini görür, "bu statik bir stylesheet" diye düşünür ve `Cache-Control: private` gibi uyarıları göz ardı ederek yanıtı `/hesap/ayarlar/kotu.css` anahtarıyla **önbelleğe yazar.**

Artık saldırgan, kendi tarayıcısından (kimliksiz, çerezsiz) aynı `https://hedef.com/hesap/ayarlar/kotu.css` adresini çeker ve önbellekteki, kurbana ait hassas yanıtı okur.

### 3. Cache key'in ayırt edici gizli bilgiyi içermemesi

Önbellek genellikle yanıtları URL yoluna göre anahtarlar; çereze göre değil. Yani kimlikli yanıt, çereze bağlı olmayan bir URL anahtarı altında saklanır. Bu yüzden saklanan içerik "herkese açık bir dosya" gibi geri servis edilir. Eğer önbellek her yanıtı `Set-Cookie` veya `Authorization`'a göre ayrı anahtarlasaydı bu saldırı çalışmazdı; ama statik varlıklarda bunu yapmak performans açısından anlamsız olduğu için çoğu yapılandırma bunu yapmaz.

### Neden "deception" (aldatma)?

Çünkü kimse gerçek anlamda bir açık bırakmamıştır: Origin doğru sayfayı üretmiştir, önbellek de "statik dosyaları önbellekle" kuralını dürüstçe uygulamıştır. Zafiyet, **iki bağımsız bileşenin aynı URL'yi farklı yorumlaması** sonucu ortaya çıkan bir *sistem seviyesi* hatasıdır. Saldırgan, önbelleği "bu gizli sayfa aslında bir CSS dosyası" diye *aldatmıştır.*

## Path Confusion Varyantları

WCD sadece "sonuna `.css` ekle" ile sınırlı değildir. Origin ile önbelleğin URL ayrıştırmasındaki farklar çeşitli biçimlerde sömürülebilir. Başlıca desenler:

- **Yol ekleme (path parameter / extra path):**
  `/profil` yerine `/profil/x.css`. Origin fazladan segmenti yutar, önbellek uzantıyı görür.
- **Encoded karakterler ve delimiter farkları:**
  Bazı yığınlarda `%2F` (kodlanmış `/`), `%00`, `;`, `#`, `?` gibi karakterler önbellek ile origin tarafından farklı sınırlayıcılar olarak ele alınır. Örneğin `/hesap%2Fx.css` önbellekte tek path, origin'de iki segment gibi çözülebilir.
- **Noktalı-virgül parametreleri (matrix params):**
  `/hesap;x.css` bazı Java tabanlı sunucularda `;` sonrasını path parametresi sayar; origin `/hesap`'ı servis eder, önbellek `.css` görür.
- **Normalizasyon farkları:**
  `/hesap/..%2fx.css` gibi yollarda önbellek ve origin path normalizasyonunu farklı sırada/kuralda yaparsa uyumsuzluk doğar.

Bu varyantların ortak paydası aynıdır: **iki ayrıştırıcının (parser) tek bir URL üzerinde anlaşamaması.** Bu genel olguya literatürde bazen "parser discrepancy" veya "path confusion" denir ve WCD dışında request smuggling gibi başka sınıflarda da rol oynar.

## Somut Örnek (Kavramsal Akış)

Bir e-ticaret sitesinde `/account` sayfası, giriş yapmış kullanıcının adını, adresini ve son sipariş numaralarını gösteriyor olsun. Site bir CDN arkasında ve CDN "her `.jpg` uzantılı istek statiktir, 1 saat önbellekle" kuralına sahip.

1. Saldırgan kurbana (ör. e-posta/mesajla) şu bağlantıyı gönderir:
   `https://magaza.com/account/avatar.jpg`
2. Kurban giriş yapmış durumdayken bu linke tıklar. Tarayıcı kurbanın oturum çerezini gönderir.
3. Origin sunucu, framework'ün yol yorumlaması nedeniyle bunu hâlâ `/account` olarak ele alır ve **kurbanın kişisel hesap sayfasını** HTML olarak döndürür. `Cache-Control: no-store` başlığı gönderse bile CDN kuralı bunu uzantıya bakıp ezebilir.
4. CDN, `.jpg` gördüğü için yanıtı `/account/avatar.jpg` anahtarıyla önbelleğe yazar.
5. Saldırgan kendi tarayıcısından (oturumsuz) aynı URL'yi açar. CDN önbellekten kurbanın hesap sayfasını servis eder. Saldırgan kurbanın kişisel verilerini görür.

Kritik nokta: Saldırganın kurbanın çerezini *çalması* gerekmez; yalnızca kurbanın *bir kez o linke tıklaması* yeterlidir. Sızan yanıt CSRF token veya API anahtarı içeriyorsa, hesap ele geçirmeye (account takeover) kadar tırmanabilir.

## Tespit

### Kara kutu / test perspektifi

- **Uzantı ekleme denemesi:** Kimlikli, dinamik bir sayfaya (`/profil`, `/settings`, `/api/me` vb.) sahte statik uzantı ekleyin (`/profil/test.css`). Yanıt hâlâ hassas kişisel içerik döndürüyor mu? Döndürüyorsa ilk alarm.
- **Önbellek göstergelerini okuyun:** Yanıt başlıklarında `X-Cache: HIT/MISS`, `CF-Cache-Status`, `Age`, `X-Served-By`, `Cache-Control` gibi alanlara bakın. İkinci istekte `HIT` veya artan `Age` görmek, yanıtın önbelleklendiğini gösterir.
- **İki tarayıcı / iki oturum testi:** Kimlikli oturumda `/profil/test.css` çekin; ardından **tamamen ayrı, çerezsiz** bir istemciyle aynı URL'yi çekin. İkinci istekte birinci kullanıcının kişisel verisi geliyorsa zafiyet doğrulanmıştır. (Bu testi yalnızca yetkiniz olan, izinli sistemlerde yapın.)
- **Varyant taraması:** Sadece `.css` değil; `.js`, `.jpg`, `.ico`, `.txt` gibi uzantıları ve `;`, `%2F`, `%00`, yol sonu `/` kombinasyonlarını deneyin. Bir uzantı çalışmasa da diğeri çalışabilir.

### Sunucu / operasyon perspektifi (savunmacı tespit)

- **Önbellek loglarında anomali:** Normalde asla önbelleklenmemesi gereken yollar (ör. `/account`, `/dashboard`) altında statik uzantılı isabetler görülüyorsa (`/account/*.css` gibi) bu bir WCD sondajının işareti olabilir.
- **Set-Cookie + cache HIT birlikteliği:** Bir yanıt hem `Set-Cookie` içeriyor hem de önbelleğe yazılıyorsa bu ciddi bir yapılandırma kokusudur; alarm kuralı yazılmalıdır.
- **WAF/log korelasyonu:** Aynı hassas base-path'e sürekli farklı sahte uzantılarla gelen istek serileri, otomatik WCD taramasına işaret eder.

## Savunma

WCD tek bir kontrolle değil, **katmanlı** savunmayla kapatılır. En sağlam çözümler önbellek ile origin arasındaki *yorum farkını ortadan kaldıranlar*dır.

### 1. Önbelleği içeriğe göre karar verecek şekilde yapılandırın (en önemli ilke)

Önbellek kararı **yalnızca URL uzantısına göre değil, origin'in gönderdiği `Cache-Control`/`Content-Type` başlıklarına saygı göstererek** verilmelidir.

- Origin `Cache-Control: no-store` veya `private` diyorsa, önbellek bunu **uzantıya bakarak ezmemelidir.** Birçok WCD olayının kökeninde "statik uzantıları koşulsuz önbellekle" kuralının bu başlıkları görmezden gelmesi yatar.
- Statik varlıkları önbelleklerken, yanıtın gerçekten beklenen `Content-Type`'a sahip olduğunu doğrulamak güçlü bir savunmadır: URL `.css` ile bitiyor ama origin `text/html` döndürüyorsa, bu bir statik dosya değildir; önbelleklenmemelidir.

### 2. Origin'de path yorumunu katılaştırın (strict routing)

- Uygulama, tanımlı route'lara **birebir** eşleşmeyen yolları önbellekleme öncesinde reddetmeli veya `404` döndürmelidir. `/account/anything.css` gibi fazladan segment içeren yollar sessizce `/account`'a düşmemelidir.
- Framework'ün `PATH_INFO`, trailing-path yutma, matrix parametreleri (`;`) gibi "esnek" davranışlarını kapatın veya kısıtlayın.
- URL'yi hem origin hem edge tarafında **aynı** normalizasyon kurallarıyla (encoding, `.`/`..` çözümü, delimiter'lar) işleyin. Amaç: iki parser'ın asla farklı sonuç üretmemesi.

### 3. Hassas yanıtları asla önbelleklenemez yapın

- Kimlikli/kişisel tüm endpoint'ler net şekilde `Cache-Control: no-store` (ve gerektiğinde `private`, `Vary: Cookie`) göndermeli.
- Kritik veri içeren yanıtlarda `Vary: Cookie` veya benzeri anahtarlama, önbelleğin farklı kullanıcı yanıtlarını karıştırmasını engeller — fakat bunu *tek başına* yeterli görmeyin; asıl savunma no-store + strict routing'dir.

### 4. Statik içeriği mimari olarak ayırın

- Gerçek statik varlıkları ayrı bir path prefix'i veya ayrı bir hostname/subdomain altında sunun (ör. `static.hedef.com`). Önbelleği yalnızca bu ayrılmış alanda agresif çalışacak şekilde sınırlayın. Böylece uygulama path'leri hiçbir zaman "statik" kuralının kapsamına girmez.

### 5. Derinlemesine savunma

- Önbelleklenmiş yanıtlar için makul TTL'ler belirleyin; sonsuza dek yaşayan önbellek girdileri, sızıntı penceresini uzatır.
- CDN'inizin WCD'ye karşı özel koruma/normalizasyon seçenekleri varsa etkinleştirin.
- Güvenlik testlerinize (DAST/pentest) düzenli WCD senaryosu ekleyin; yeni route eklendiğinde regresyon riski vardır.

## Yaygın Hatalar ve Yanlış Anlamalar

- **"WCD ile Cache Poisoning aynı şeydir" sanmak.** En sık hata budur. Poisoning içerik *enjekte eder ve kitleyi vurur*; Deception hassas veri *sızdırır ve kurbanı okur*. Savunmaları da kısmen farklıdır.
- **Yalnızca `Vary: Cookie` eklemeyi yeterli sanmak.** Bu, farklı kullanıcı yanıtlarının karışmasını azaltabilir ama zayıf/atlanabilir yapılandırmalarda ve bazı önbellek anahtarlama senaryolarında tek başına güvenli değildir. Asıl çözüm hassas yanıtı `no-store` yapmak ve routing'i katılaştırmaktır.
- **Sorunu sadece uygulama katmanında aramak.** WCD, tek bir bileşenin bug'ı değil; **önbellek ile origin arasındaki etkileşim** hatasıdır. İki tarafı ayrı ayrı "doğru" görünse de birlikte açık üretebilirler. Denetimi mutlaka uçtan uca yapın.
- **Sadece `.css`/`.js`'i test edip geçmek.** Farklı uzantılar, encoded karakterler ve delimiter'lar bağımsız olarak çalışabilir. Bir uzantı güvenliyken diğeri açık olabilir.
- **`Cache-Control: no-store` gönderdiğine güvenip önbelleği denetlememek.** Eğer CDN kuralı uzantıya bakıp bu başlığı eziyorsa, origin doğru başlığı gönderse bile yanıt yine önbelleklenebilir. Origin başlıklarına *önbelleğin gerçekten saygı gösterdiğini* doğrulayın.
- **Statik varlıklar için `Content-Type` doğrulaması yapmamak.** URL `.jpg` diye önbelleklenen bir `text/html` yanıtı neredeyse her zaman bir WCD göstergesidir; bu tutarsızlığı yakalamak ucuz ve etkili bir kontroldür.

## Özet

Web Cache Deception, önbelleğin bir URL'yi "statik dosya" sanıp origin'in ürettiği **kimlikli, hassas** yanıtı herkese açık bir anahtar altında saklamasıyla oluşan bir sızıntı zafiyetidir. Kökeni, önbellek ile origin sunucunun aynı yolu farklı yorumlamasıdır (path confusion / parser discrepancy). Web Cache Poisoning'in tersine, saldırının yönü *kurbandan saldırgana* doğrudur ve amaç veri sızdırmaktır. En güçlü savunma, önbelleğin kararını uzantı yerine origin'in `Cache-Control`/`Content-Type` başlıklarına ve içeriğine dayandırması, origin'de path yorumunu katılaştırması, hassas yanıtları `no-store` yapması ve statik içeriği mimari olarak ayrı tutmasıdır.
