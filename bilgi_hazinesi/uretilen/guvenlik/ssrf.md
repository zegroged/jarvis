# Server-Side Request Forgery (SSRF)

## Tanım

Server-Side Request Forgery (SSRF), bir saldırganın hedef sunucuyu, kendi seçtiği bir adrese istek (request) göndermeye zorladığı bir zafiyet sınıfıdır. İsmin de belirttiği gibi istek "sahteciliği" istemci tarafında değil, sunucu tarafında (server-side) gerçekleşir. Yani zararlı isteği atan taraf saldırganın tarayıcısı değil, saldırganın kandırdığı **kurban uygulama sunucusudur**.

Bu ayrım kritiktir. Uygulama sunucusu genellikle ağ topolojisi içinde ayrıcalıklı bir konumda durur: iç ağdaki (internal network) veritabanlarına, yönetim panellerine, servis keşif (service discovery) uç noktalarına ve bulut sağlayıcının metadata servislerine erişebilir. Dışarıdan bu kaynaklara ulaşılamaz; ama saldırgan, sunucuyu bir aracı (proxy) gibi kullanarak bu güven sınırını (trust boundary) aşar. SSRF'in tehlikesi tam olarak buradadır: zafiyet, sunucunun ağ üzerindeki güvenini silah olarak kullanır.

SSRF, OWASP'ın risk sıralamalarında kendine ayrı bir kategori açacak kadar önem kazanmıştır; çünkü modern mimarilerde (mikroservisler, bulut, container'lar) sunucunun yapabileceği "yan etkili" istek sayısı patlamıştır.

## Kök neden: neden SSRF oluşur?

SSRF'in kök nedeni tek bir cümleyle özetlenebilir: **uygulama, kullanıcının kontrol ettiği bir girdiyi (input) bir ağ isteğinin hedefi olarak kullanır ve bu hedefi yeterince doğrulamaz.**

Bunun neden bu kadar yaygın olduğunu anlamak için modern uygulamaların ne yaptığına bakmak gerekir. Bir uygulama sık sık şu işleri yapar:

- Kullanıcının verdiği bir URL'den önizleme (link preview) üretmek
- Uzak bir resmi indirip küçük resim (thumbnail) oluşturmak
- Webhook adresine bildirim (notification) göndermek
- Kullanıcının belirttiği bir kaynaktan veri içe aktarmak (import from URL)
- PDF üretmek için bir HTML sayfasını render eden servise URL geçirmek
- Bir dosya sağlama (fetch) işlemi için S3 benzeri bir adresi çözmek

Bütün bu senaryolarda ortak nokta şudur: kullanıcı bir adres söylüyor, sunucu o adrese gidiyor. Geliştirici genellikle şöyle düşünür: "Kullanıcı zaten bir resim URL'si girecek, ne olabilir ki?" İşte kök hata bu varsayımdır. Saldırgan resim URL'si yerine `http://169.254.169.254/...` gibi iç bir adres verdiğinde, sunucu itaatkâr bir şekilde oraya gider.

SSRF'in derinleşen nedeni, **ağ katmanındaki örtük güvendir**. Çoğu iç servis, "bu isteğe ağ içinden ulaşıldıysa güvenilirdir" varsayımıyla kimlik doğrulaması (authentication) yapmadan çalışır. Metadata servisleri, Redis, Elasticsearch, dahili admin API'leri sıklıkla bu şekildedir. Uygulama sunucusu ise bu iç ağın "güvenilir" bir üyesidir. Saldırgan SSRF ile bu güvenilir üyeyi ele geçirdiğinde, kimlik doğrulaması olmayan tüm iç servisler bir anda erişilebilir hâle gelir.

## Çalışma mantığı ve türleri

SSRF'i savunmadan önce, sonucun saldırgana nasıl döndüğüne göre iki temel türü ayırt etmek gerekir; çünkü savunma ve tespit stratejisi buna göre değişir.

### In-band (klasik) SSRF

Sunucunun hedeften aldığı yanıt (response), doğrudan ya da dolaylı olarak saldırgana geri döner. Örneğin link önizleme özelliği, iç bir adresin içeriğini önizleme kutusunda gösterir. Saldırgan iç servisin çıktısını doğrudan okuyabilir. Bu en kolay sömürülen (exploit) türdür.

### Blind (kör) SSRF

Sunucu isteği yapar ama yanıt saldırgana dönmez. Saldırgan yalnızca isteğin gerçekleştiğini dolaylı sinyallerle anlayabilir: yanıt süresindeki fark (timing), hata mesajları veya kendi kontrol ettiği bir sunucuya (out-of-band) gelen DNS/HTTP isteği. Kör SSRF daha az bilgi sızdırır gibi görünse de tehlikelidir; çünkü metadata çalmaya yetmese bile iç servislerde durum değiştiren (state-changing) POST istekleri tetiklemeye ya da port taraması yapmaya yarar. Kör SSRF tespitinde saldırganlar genellikle **out-of-band interaction** sunucuları (kendi kontrollerindeki bir domain'e gelen istekleri gözleyen altyapılar) kullanır.

## Somut senaryo: bulut metadata hırsızlığı

SSRF'in en yıkıcı ve en klasik sonucu, bulut sağlayıcının metadata servisinin (Instance Metadata Service, IMDS) çalınmasıdır. Bu senaryoyu adım adım anlamak, hem saldırıyı hem savunmayı kavramanın en iyi yoludur.

Bulut sağlayıcılar (AWS, GCP, Azure ve benzerleri), her sanal makinenin (instance) kendi hakkında bilgi ve geçici kimlik bilgilerini (credentials) alabilmesi için özel bir link-local IP adresinde çalışan bir HTTP servisi sunar. Bu adres geleneksel olarak `169.254.169.254`'tür. Bu link-local aralık (169.254.0.0/16) yönlendirilmez (non-routable); yani yalnızca instance'ın kendisinden erişilebilir. İşte tam da bu "yalnızca kendinden erişilir" varsayımı, SSRF ile kırılır.

Bir instance'a IAM rolü (role) atandığında, metadata servisi o role ait **geçici erişim anahtarlarını** (access key, secret key, session token) belirli bir yol üzerinden döndürür. Uygulama sunucusu, bir dış URL indireceğine inanarak `http://169.254.169.254/...` adresine yönlendirilirse, metadata servisinden dönen bu geçici bulut kimlik bilgileri saldırganın eline geçer.

Sonuç yıkıcıdır: saldırgan artık o instance'ın IAM rolünün yetkileriyle bulut hesabında işlem yapabilir. Rol geniş yetkiliyse (ki fazlasıyla yaygındır), bu S3 kovalarının okunması, yeni kaynakların oluşturulması, hatta yanal hareketle (lateral movement) hesabın büyük kısmının ele geçirilmesi anlamına gelir. Geçmişteki büyük bulut veri ihlallerinin bir kısmının çekirdeğinde tam olarak bu zincir yatar: SSRF ile metadata erişimi, oradan geçici kimlik bilgileri, oradan veri deposuna erişim.

Not: Farklı bulut sağlayıcıların metadata yolları, gerektirdiği HTTP header'ları ve koruma mekanizmaları birbirinden farklıdır. Buradaki `169.254.169.254` adresi AWS ve bazı sağlayıcılar için geçerli klasik değerdir; GCP ve Azure gibi sağlayıcılar özel bir header (örneğin `Metadata-Flavor` benzeri bir başlık) zorunluluğu getirerek basit SSRF'i kısmen zorlaştırır. Kesin yol ve başlık isimlerini üretim ortamında ilgili sağlayıcının güncel dokümantasyonundan doğrulamak gerekir; bu makale kavramı anlatır.

## IMDSv2: metadata servisini sertleştirmek

AWS'in metadata servisi için getirdiği ikinci sürüm (**IMDSv2**), SSRF üzerinden metadata hırsızlığını doğrudan hedef alan bir savunma tasarımıdır. Mantığını anlamak öğreticidir; çünkü zafiyetin kök nedenine yönelik akıllıca bir çözümdür.

Orijinal metadata servisi (IMDSv1) tek adımlıydı: sadece `GET` isteği at, kimlik bilgilerini al. Basit bir SSRF (tek bir GET yapabilen bir zafiyet bile) bunu sömürmeye yeterdi.

IMDSv2 bunu **oturum yönelimli (session-oriented)** hâle getirir. Kimlik bilgisi almadan önce istemcinin şunu yapması gerekir:

1. Önce özel bir **PUT** isteğiyle bir oturum token'ı (session token) talep etmek.
2. Bu token'ı sonraki her metadata isteğinde bir HTTP header içinde geri göndermek.

Bu iki adımlı yapı neden işe yarar? Çünkü SSRF zafiyetlerinin büyük çoğunluğu yalnızca basit `GET` istekleri yapabilir; saldırganın istediği metoda (`PUT`) izin vermez ve saldırgana isteğe keyfî header ekletmez. Yani IMDSv2, "metadata almak istiyorsan önce özel bir yazma isteği yapıp dönen token'ı header'a koymalısın" diyerek basit SSRF'in yeteneklerinin dışına çıkar.

Ek olarak IMDSv2, token yanıtına bir **TTL (yaşam süresi)** ve varsayılan olarak düşük bir **hop limit** koyar. Hop limiti, metadata yanıtının paketinin instance'ı terk etmesini (örneğin yanlış yapılandırılmış bir container ağ katmanından dışarı sızmasını) engellemeye yardım eder.

Kritik uyarı: IMDSv2'yi etkinleştirmek yeterli değildir; IMDSv1'i aynı zamanda **zorunlu olarak kapatmak** gerekir. Eğer instance hâlâ IMDSv1'i kabul ediyorsa, saldırgan basitçe eski yolu kullanır ve IMDSv2 hiçbir koruma sağlamaz. "IMDSv2'yi açtık" demek ile "IMDSv1'i kapatıp yalnızca IMDSv2'yi zorunlu kıldık" demek arasında dünya kadar fark vardır. Doğru yapılandırma, IMDS'i tümüyle "yalnızca v2 (required)" moduna almaktır.

## DNS rebinding: doğrulamayı atlatmanın sinsi yolu

SSRF savunmasının en yaygın ilk adımı, hedef URL'nin adresini kontrol etmektir: "Bu adres iç bir IP mi? Öyleyse reddet." Bu kontrol mantıklıdır ama saf uygulandığında **DNS rebinding** tekniğiyle atlatılabilir. Bu tekniğin çalışma mantığını anlamak, neden bu tür kontrollerin kırılgan olduğunu gösterir.

Problemin kaynağı, **kontrol zamanı ile kullanım zamanı arasındaki fark**tır (bir tür Time-of-Check to Time-of-Use, TOCTOU sorunu). Bir URL doğrulanırken sunucu şu iki işlemi ayrı ayrı yapar:

1. Alan adını (domain) bir IP'ye çözer (DNS resolution) ve bu IP'nin güvenli olup olmadığını kontrol eder.
2. Sonra asıl HTTP isteğini yapar, bu sırada alan adını **tekrar** çözer.

DNS rebinding saldırısı bu iki çözümleme arasına girer. Saldırgan, kendi kontrolündeki bir alan adı için DNS kaydını çok kısa bir TTL ile ayarlar. İlk çözümlemede alan adı zararsız bir dış IP'ye (örneğin saldırganın sunucusuna) çözülür ve doğrulama kontrolünü geçer. Ama TTL dolduğu için ikinci çözümlemede saldırgan aynı alan adını `169.254.169.254` gibi iç bir IP'ye "yeniden bağlar" (rebind). Sonuçta doğrulama zararsız IP'yi gördü, ama asıl istek iç IP'ye gitti. Kontrol geçerli görünürken kullanım zararlı oldu.

Bunun savunması, doğrulama ile istek arasında adres tutarlılığını garanti etmektir. En sağlam yaklaşım, alan adını **bir kez** çözmek, çözülen IP'yi doğrulamak ve **tam olarak o doğrulanmış IP'ye** bağlanmaktır (yani HTTP istemcisinin ayrı bir DNS çözümlemesi daha yapmasına izin vermemek). Buna sıklıkla "resolve-then-connect" ya da IP'yi pinleme (pinning) denir. Ayrıca çözülen tüm IP'lerin (bir alan adı birden çok IP'ye çözülebilir) her birinin güvenli olduğunu doğrulamak, sadece ilkine bakmamak gerekir.

## Sömürü mantığı: saldırgan nasıl düşünür?

SSRF'i savunacak kişinin, saldırganın araç setini bilmesi gerekir. Saldırgan tek bir "iç IP'yi engelle" kuralını görünce şu manevralara başvurur:

- **Alternatif IP gösterimleri**: `127.0.0.1` yerine ondalık (`2130706433`), sekizlik (octal), onaltılık (hex) ya da IPv6 eşleniği (`::1`, `[::ffff:127.0.0.1]`) gibi biçimler. Naif bir string kontrolü bunları kaçırır.
- **Yönlendirme (redirect) zinciri**: Saldırgan zararsız bir dış URL verir; o URL bir `3xx` redirect ile iç adrese yönlendirir. Uygulama redirect'i körü körüne takip ederse doğrulama boşa çıkar. Bu yüzden redirect'ler de doğrulanmalı veya kapatılmalıdır.
- **DNS rebinding**: Yukarıda anlatıldığı gibi, çözümleme zamanlamasını suistimal etmek.
- **Farklı şema (scheme) suistimali**: `http` beklenirken `file://`, `gopher://`, `dict://` gibi şemalarla yerel dosya okumak ya da ham TCP payload'ı enjekte etmek. Özellikle `gopher://`, ham byte gönderebildiği için kimlik doğrulaması olmayan Redis gibi servislere komut yazmakta kullanılır.
- **Link-local ve özel aralıkların tamamı**: Sadece `169.254.169.254` değil; `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `0.0.0.0` ve IPv6 karşılıkları hedef olabilir.

Saldırganın nihai amacı genellikle bir zincir kurmaktır: SSRF ile iç erişim → metadata veya iç servis → kimlik bilgisi veya komut çalıştırma → yanal hareket. Tek bir "önemsiz" link önizleme özelliği, bu zincirin ilk halkasıdır.

## Savunma: egress allow-list ve derinlemesine katmanlar

SSRF savunmasında en önemli zihinsel kayma şudur: **giriş (input) doğrulamasına güvenmeyi bırakıp çıkış (egress) kontrolüne geçmek.** Girdi doğrulaması (URL'yi denetlemek) gereklidir ama kırılgandır; yukarıdaki atlatma tekniklerinin hepsi girdi doğrulamasını hedef alır. Asıl dayanıklı savunma, sunucunun *nereye gidebileceğini* ağ seviyesinde sınırlamaktır.

### Egress allow-list (izin listesi) mantığı

Deny-list (engelleme listesi) yaklaşımı, "şu kötü adreslere gitme" der. Bu yaklaşım kaybetmeye mahkûmdur; çünkü saldırganın yaratıcılığını tahmin etmeye çalışır ve her zaman kaçırdığı bir gösterim, bir aralık, bir şema kalır. Allow-list (izin listesi) yaklaşımı ise tersini yapar: "**yalnızca şu bilinen adreslere gidebilirsin, geri kalan her şey yasak.**" Güvenli varsayılan (secure default) budur.

Pratikte bu, dışa istek yapan bileşenleri (link önizleme, webhook gönderimi, resim indirme) izole bir ağ segmentine ya da kısıtlı bir egress proxy'sinin arkasına koymak demektir. Bu proxy yalnızca önceden onaylanmış hedef alan adlarına/IP aralıklarına izin verir. Sunucunun ağ katmanı, `169.254.169.254` ve tüm iç aralıklara giden trafiği baştan bloklar. Böylece uygulama katmanındaki doğrulama atlatılsa bile, paket ağdan çıkamaz.

Egress allow-list'in gücü, saldırganın uygulama mantığındaki tüm hilelerini (rebinding, redirect, alternatif gösterim) **anlamsızlaştırmasıdır**; çünkü kontrol artık string kontrolü değil, gerçek paketin gerçek hedefidir.

### Katmanlı savunma (defense in depth)

Tek bir kontrole güvenmek yerine katmanları üst üste koymak gerekir:

1. **Şema kısıtı**: Yalnızca `http` ve `https`'e izin ver; `file`, `gopher`, `dict`, `ftp` gibi şemaları reddet.
2. **Resolve-then-connect**: Alan adını bir kez çöz, çözülen IP'yi (tüm IP'leri) iç aralıklara karşı doğrula, tam o IP'ye bağlan. Bu, DNS rebinding'i kırar.
3. **Redirect kontrolü**: Redirect'leri ya tamamen kapat ya da her redirect hedefini yeniden doğrula.
4. **Egress ağ kontrolü**: İç IP aralıklarına ve metadata adresine giden trafiği ağ/firewall seviyesinde blokla; mümkünse allow-list ile yalnızca gereken hedeflere izin ver.
5. **Metadata sertleştirme**: Bulutta IMDSv2'yi zorunlu kıl, IMDSv1'i kapat, hop limitini düşür.
6. **En az yetki (least privilege)**: Instance'a atanan IAM rolünü daraltarak, metadata çalınsa bile hasarı sınırla. Bu, SSRF'in bir metadata sızıntısına dönüşmesini engellemese de, sızan kimlik bilgilerinin ne yapabileceğini ciddi ölçüde kısar.

Bu katmanların her biri farklı bir atlatma tekniğini kapatır. Biri aşılsa bile diğerleri devrededir; SSRF savunmasının doğru zihniyeti budur.

## Yaygın hatalar

Sahada tekrar tekrar görülen, geliştiricilerin SSRF konusunda düştüğü tipik tuzaklar:

- **Deny-list'e güvenmek**: "127.0.0.1 ve 169.254.169.254'ü engelledik" demek. Alternatif IP gösterimleri, IPv6, DNS rebinding ve iç aralıkların tamamı düşünülmediği için bu neredeyse her zaman atlatılır.
- **Sadece string olarak URL kontrolü**: URL'yi düzgün ayrıştırmadan (parse) `startsWith`/regex ile kontrol etmek. `http://legit.com@169.254.169.254/` gibi userinfo hilesi ya da farklı kodlamalar bunu kandırır. Doğrulama, çözülmüş IP üzerinde yapılmalıdır, ham string üzerinde değil.
- **Redirect'leri körü körüne takip etmek**: İlk URL doğrulanır ama HTTP istemcisi 3xx redirect'i otomatik izler ve iç adrese gider.
- **DNS'i iki kez çözmek**: Doğrulama sırasında bir çözümleme, istek sırasında ayrı bir çözümleme yapmak; bu tam olarak DNS rebinding'in açtığı kapıdır.
- **IMDSv2'yi açıp IMDSv1'i açık bırakmak**: v2 etkin ama v1 hâlâ kabul ediliyorsa koruma yok denecek kadar azdır.
- **Aşırı geniş IAM rolleri**: Metadata çalınırsa hasarın büyüklüğü tamamen rolün yetkisiyle orantılıdır. Geniş rol, küçük bir SSRF'i hesap devralmaya çevirir.
- **Blind SSRF'i önemsememek**: "Yanıt geri dönmüyor, o zaman zararsız" varsayımı yanlıştır. Kör SSRF ile durum değiştiren istekler ve port taraması hâlâ mümkündür.
- **Yalnızca uygulama katmanında savunmak**: Ağ egress kontrolü olmadan, tek bir uygulama hatası tüm savunmayı çökertir.

## En iyi pratikler (özet)

- SSRF'i bir "girdi doğrulama" problemi değil, bir "**çıkış yetkilendirme**" problemi olarak düşünün. Sunucunun nereye gidebileceğini ağ seviyesinde sınırlayın.
- Deny-list yerine **egress allow-list** kullanın: yalnızca bilinen, gerekli hedeflere izin verin.
- Alan adını **bir kez çözün, çözülen IP'yi doğrulayın, o IP'ye bağlanın** (resolve-then-connect). Tüm çözülen IP'leri kontrol edin. Böylece DNS rebinding'i kapatın.
- Yalnızca `http`/`https` şemalarına izin verin; diğer tüm şemaları reddedin.
- Redirect'leri ya kapatın ya da her adımda yeniden doğrulayın.
- Bulutta **IMDSv2'yi zorunlu**, IMDSv1'i **kapalı** yapın; hop limitini düşürün.
- **En az yetki** ilkesiyle IAM rollerini daraltın; metadata sızsa bile hasarı sınırlayın.
- Dışa istek yapan bileşenleri (link preview, webhook, importer) izole bir ağ segmentine/proxy'nin arkasına alın.
- Kör SSRF için **out-of-band tespiti** ve loglama kurun; beklenmeyen iç isteklere alarm üretin.
- Kesin metadata yollarını, HTTP header adlarını ve bulut ayarlarını her zaman ilgili sağlayıcının güncel dokümantasyonundan doğrulayın; varsayımla ilerlemeyin.

SSRF, tek başına küçük görünen bir özelliğin (bir URL indirme) modern bulut mimarisindeki güven ilişkileriyle birleştiğinde nasıl hesap devralmaya kadar gidebileceğinin en net örneğidir. Doğru savunma, tek bir kontrolle değil; girdi doğrulama, DNS pinleme, egress allow-list, metadata sertleştirme ve en az yetkinin birlikte oluşturduğu katmanlı bir mimariyle kurulur.
