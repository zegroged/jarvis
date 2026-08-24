# Güvenli Çerez Özellikleri ve SameSite/Partitioned Cookie Mekanikleri

## Giriş ve Kapsam

Oturum yönetiminin kalbinde çerezler (cookies) bulunur. Bir kullanıcı kimliği doğrulandıktan sonra sunucu genellikle bir oturum tanımlayıcısını (session identifier) çereze koyar ve tarayıcı bu çerezi sonraki her istekte ilgili alan adına (domain) otomatik olarak geri gönderir. Bu "otomatik gönderim" davranışı çerezleri hem pratik hem de tehlikeli yapar: tarayıcı, isteğin kimin tarafından tetiklendiğini umursamadan çerezi ekler. İşte CSRF (Cross-Site Request Forgery), oturum sabitleme (session fixation), çerez çalma (session hijacking) ve üçüncü taraf izleme (third-party tracking) gibi saldırıların tümü bu davranışın etrafında döner.

Bu makale, çerez güvenlik özniteliklerini (attributes) mekanizma seviyesinde ele alır: `SameSite` (Lax/Strict/None), `Secure`, `HttpOnly`, `Domain`, `Path`, çerez ön ekleri (cookie prefixes: `__Host-`, `__Secure-`), CHIPS/`Partitioned` çerezler ve üçüncü taraf çerezlerin kaldırılması sonrası ortaya çıkan yeni saldırı-savunma dengeleri (bounce tracking, Storage Access API). Amaç, mekanizmayı anlamak ve sağlam savunma/tespit kurmaktır.

## Temel Kavram: "site" ve "origin" Farkı

Çerez semantiğini anlamanın önkoşulu iki kavramı ayırt etmektir:

- **Origin (köken):** `scheme` + `host` + `port` üçlüsü. `https://app.example.com` ile `https://api.example.com` farklı origin'lerdir.
- **Site:** eTLD+1 (etkin üst düzey alan adı + 1 etiket) düzeyinde tanımlanır. `app.example.com` ve `api.example.com` **aynı site**tir (`example.com`). Burada eTLD, Public Suffix List (PSL) üzerinden belirlenir; `co.uk`, `github.io` gibi çok parçalı son ekleri doğru işlemek için bu liste kullanılır.

`SameSite` özniteliği "site" kavramına dayanır; yani alt alan adları (subdomains) arası istekler çoğu durumda "same-site" (aynı site) sayılır. Bu ayrımı atlamak, güvenlik varsayımlarında ciddi hatalara yol açar.

Ek olarak modern tarayıcılarda "schemeful same-site" uygulanır: `http://example.com` ile `https://example.com` artık ayrı site sayılır. Yani plaintext'ten HTTPS'e geçiş cross-site muamelesi görebilir.

## SameSite: Lax, Strict, None

`SameSite`, çerezin **cross-site** (siteler arası) isteklerde gönderilip gönderilmeyeceğini belirler. Üç değeri vardır.

### SameSite=Strict

Çerez yalnızca istek, çerezin ait olduğu siteyle **aynı site**den kaynaklandığında gönderilir. Başka bir siteden gelen hiçbir istek — bir bağlantıya tıklama dahil — çerezi taşımaz.

- **Güçlü yanı:** CSRF'e karşı en katı koruma.
- **Kullanılabilirlik maliyeti:** Kullanıcı harici bir sitedeki bağlantıdan sitenize geldiğinde (örn. e-postadaki linke tıklayıp bankaya gitmek), ilk yüklemede oturum çerezi gönderilmez ve kullanıcı oturum açmamış gibi görünür. Bu yüzden salt `Strict` oturum çerezleri genellikle kötü bir ilk deneyim yaratır.

### SameSite=Lax

Çerez, aynı site isteklerinde ve **üst düzey gezinti (top-level navigation)** olan güvenli metot (`GET`) isteklerinde gönderilir. Yani kullanıcı bir bağlantıya tıklayıp adres çubuğundaki URL değişerek sitenize geldiğinde çerez taşınır; ama `POST` gibi durum değiştiren cross-site isteklerde, `<iframe>`, `<img>`, `fetch`/`XHR` gibi alt-kaynak (subresource) isteklerinde taşınmaz.

`Lax`, kullanılabilirlik ile CSRF savunması arasında dengeli bir noktadır ve modern tarayıcıların çoğunda `SameSite` belirtilmemiş çerezler için **varsayılan** davranıştır (default). Ancak "SameSite=Lax varsayılanı", `SameSite` özniteliğini açıkça yazmamayı mazur göstermez; varsayılana güvenmek yerine niyeti açıkça belirtmek daha sağlamdır.

### SameSite=None

Çerez tüm cross-site isteklerde gönderilir; yani "eski" (öznitelik yokken geçerli olan) davranışa döner. Bu, üçüncü taraf bağlamları (embed edilmiş widget'lar, SSO iframe'leri, ödeme sağlayıcıları) için gereklidir. Modern tarayıcılar `SameSite=None` çerezlerini yalnızca `Secure` (yani HTTPS) ile kabul eder. `Secure` olmadan `SameSite=None` yazılırsa çerez reddedilir — bu yaygın bir üretim hatasıdır.

### "Lax + POST" ve iki dakikalık nüans

Bazı tarayıcı sürümlerinde, yeni set edilmiş (`SameSite` belirtilmemiş) çerezler için kısa bir zaman penceresinde cross-site top-level `POST`'lara istisnai olarak izin verilmiştir. Bu, bazı OAuth/POST tabanlı akışları bozmamak için getirilmiş geçici bir uyumluluk davranışıdır. Kesin süre ve varlığı tarayıcı sürümüne göre değişebildiği için, güvenlik tasarımınızı bu istisnaya dayandırmayın; niyetinizi açık `SameSite` değerleriyle ifade edin.

## Diğer Kritik Öznitelikler

### Secure

Çerez yalnızca HTTPS bağlantılarıyla gönderilir. Oturum çerezleri için zorunlu kabul edilmelidir; aksi halde `http://` üzerinden ağı dinleyen bir saldırgan çerezi düz metin olarak yakalayabilir. `Secure` olmadan `SameSite` tek başına yeterli koruma değildir.

### HttpOnly

Çereze JavaScript'ten (`document.cookie`) erişimi engeller. Bu, bir XSS (Cross-Site Scripting) açığı olsa bile saldırganın oturum tanımlayıcısını doğrudan `document.cookie` ile okuyup dışarı sızdırmasını zorlaştırır. Not: `HttpOnly`, XSS'i çözmez — saldırgan tarayıcıda kod çalıştırabildiği için istekleri kurbanın oturumuyla yine tetikleyebilir. Ama çerezin sunucuya taşınmasını engelleyerek "token'ı kopyalayıp başka yerde kullanma" senaryosunu kırar.

### Domain ve Path

- `Domain` verilmezse çerez yalnızca onu set eden host'a (host-only) bağlanır; bu daha dar ve daha güvenlidir.
- `Domain=example.com` verilirse çerez tüm alt alan adlarına yayılır. Bu, "cookie tossing" ve alt alan adı ele geçirme (subdomain takeover) durumunda saldırı yüzeyini genişletir. Zayıf/güvenilmeyen bir alt alan adı, üst site için geçerli görünen çerezler set edebilir.
- `Path`, güvenlik sınırı DEĞİLDİR. Aynı origin içindeki bir sayfa, farklı path'teki çereze DOM/istek manipülasyonuyla erişebilir. `Path`'e izolasyon amacıyla güvenmeyin.

## Çerez Ön Ekleri: `__Host-` ve `__Secure-`

Çerezlerin bir tasarım zayıflığı vardır: bir `Set-Cookie` başlığındaki öznitelikler (özellikle `Domain` ve `Secure`) tarayıcıdan sunucuya geri gönderilen çerezde **görünmez**. Sunucu yalnızca `isim=değer` alır; çerezin gerçekten `Secure` mi yoksa hangi `Domain` ile mi set edildiğini istekten anlayamaz. Bu belirsizlik, bir saldırganın (örn. güvensiz bir alt alan adından veya `http://` üzerinden) aynı isimde sahte bir çerez "enjekte" etmesine (cookie injection / tossing) zemin hazırlar.

Ön ekler bu boşluğu, çerez ismine kural gömerek kapatır. Tarayıcı, isim belli bir ön ekle başlıyorsa çerezin katı koşulları sağlamasını zorunlu kılar; sağlamıyorsa reddeder:

- **`__Secure-` ön eki:** Çerez `Secure` bayrağıyla ve güvenli (HTTPS) bir bağlamdan set edilmiş olmalıdır. Aksi halde tarayıcı çerezi kabul etmez.
- **`__Host-` ön eki:** Daha katıdır. Çerez `Secure` olmalı, güvenli bağlamdan set edilmeli, `Domain` özniteliği **olmamalı** (yani host-only, alt alan adlarına yayılmaz) ve `Path=/` olmalıdır. Bu, çerezi tek bir origin'e sabitler ve alt alan adları arası "cookie tossing"e karşı en güçlü pratik korumadır.

Oturum ve CSRF token çerezleri için pratik öneri: mümkünse `__Host-` ön ekini kullanın. İsmin kendisi bir güvenlik sözleşmesi haline gelir ve isim tabanlı çerez enjeksiyonunu büyük ölçüde etkisizleştirir.

## CHIPS ve `Partitioned` Çerezler

### Sorun: üçüncü taraf çerez izleme

Klasik modelde, farklı sitelere embed edilmiş aynı üçüncü taraf (örn. `tracker.example`) tüm bu sitelerde **aynı** çerez deposunu paylaşırdı. Böylece `A.com` ve `B.com`'da gömülü olan `tracker.example`, kullanıcıyı siteler arası ilişkilendirip (cross-site) profil çıkarabiliyordu. Bu, üçüncü taraf çerez izlemesinin (third-party tracking) temeliydi.

### Çözüm: partition (bölümleme)

CHIPS (Cookies Having Independent Partitioned State) yaklaşımı, `Partitioned` özniteliğiyle set edilen üçüncü taraf çerezleri **üst düzey siteye göre ayrı bir bölüme (partition)** yerleştirir. Yani `tracker.example`'ın `A.com` içindeki çerezi ile `B.com` içindeki çerezi ayrı kutularda tutulur; biri diğerini göremez. Böylece meşru üçüncü taraf işlevsellik (örn. bir chat widget'ının veya embed'in kendi durumunu hatırlaması) korunurken siteler arası ilişkilendirme kırılır.

Pratik detaylar:

- `Partitioned` çerezler `Secure` gerektirir ve genellikle `SameSite=None` ile birlikte anlamlıdır (çünkü üçüncü taraf bağlamda kullanılırlar).
- Partition anahtarı üst düzey siteyi içerir; çerez o üst siteyle ilişkili bağlamlara hapsedilir.
- Meşru embed senaryolarını (ödeme, destek widget'ları) üçüncü taraf çerez kaldırma dalgasında ayakta tutmak için tasarlanmıştır.

Not: CHIPS/`Partitioned`, "gizlilik dostu izole durum" için bir mekanizmadır; genel amaçlı bir izleme kanalı değildir ve siteler arası paylaşımı bilinçli olarak engeller.

## Üçüncü Taraf Çerezlerin Kaldırılması Sonrası Yeni Denge

Tarayıcılar üçüncü taraf çerezleri kısıtladıkça (partition'lama veya tümüyle engelleme), izleme ve bazı meşru akışlar yeni yollara kayar. Güvenlik/gizlilik açısından iki yön önemlidir.

### Bounce Tracking (sıçratma izleme)

Üçüncü taraf çerezleri okuyamayan bir izleyici, kullanıcıyı bir **ara yönlendirme (redirect)** üzerinden kendi alan adından geçirebilir. Kullanıcı `A.com` → `tracker.example` (anlık, birinci-taraf bağlamda çerez okur/yazar) → `B.com` şeklinde "sıçratılır". Bu geçici birinci-taraf ziyaret, izleyicinin kendi çerezini okuyup kullanıcıyı yeniden tanımasına imkan verir. Böylece üçüncü taraf çerez engeli, yönlendirme zinciriyle atlatılmaya çalışılır.

Savunma tarafında tarayıcılar "bounce tracking mitigation" mekanizmaları getirmiştir: yalnızca sıçratma amaçlı ziyaret edildiği tespit edilen (kullanıcı etkileşimi olmayan) alan adlarının depolamasını/çerezlerini periyodik temizleme gibi. Kesin eşikler ve algoritma tarayıcıya ve sürüme göre değişir; buradaki fikir, "etkileşimsiz ara durak" alanlarının kalıcı tanımlayıcı biriktirmesini engellemektir.

### Storage Access API ve ilişkili mekanizmalar

Üçüncü taraf bağlamların (iframe) meşru olarak birinci-taraf çerezlerine erişmesi gerekebilir (örn. gömülü bir SSO veya yorum sistemi). **Storage Access API** (`document.requestStorageAccess()`), gömülü bir dokümanın, kullanıcı etkileşimi bağlamında, üst siteyle ilişkili çerez erişimi istemesine olanak tanır. Tarayıcı bu isteği kullanıcı jesti, önceki etkileşim geçmişi ve politika temelinde değerlendirir.

İlgili bir kavram da "related website sets" / ilişkili site kümeleridir: aynı kuruluşa ait ama farklı eTLD+1'e sahip alan adlarının (örn. bir markanın `.com` ve `.co.uk` mülkleri) sınırlı ölçüde ilişkili sayılabilmesi için bir çerçeve. Bu, kaba üçüncü taraf çerez kullanımını, denetlenebilir ve sınırlı bir izinle değiştirmeyi amaçlar. Ayrıntılar ve isimlendirme tarayıcı ekosisteminde evrilmektedir.

## Tespit (Detection)

Güvenli çerez hijyenini bir güvenlik ekibi olarak nasıl doğrular ve izlersiniz:

- **Set-Cookie denetimi:** Uygulamanın ürettiği tüm `Set-Cookie` başlıklarını toplayın (proxy log'ları, DAST tarayıcı, tarayıcı geliştirici araçları). Oturum ve auth çerezlerinde şu bayrakların varlığını doğrulayın: `Secure`, `HttpOnly`, açık `SameSite` değeri ve mümkünse `__Host-` ön eki.
- **Eksik bayrak taraması:** Otomatik güvenlik tarayıcıları "cookie without Secure/HttpOnly/SameSite" bulgularını verir. Bunları auth çerezleri için yüksek öncelikli sayın; kritik olmayan tercih çerezleri için bağlama göre değerlendirin.
- **SameSite=None + Secure tutarlılığı:** `SameSite=None` içeren ama `Secure` içermeyen başlıkları arayın; bunlar sessizce reddedilir ve kırık işlevselliğe yol açar. Log'larda "beklenen çerez gelmedi" örüntüsü bir ipucudur.
- **Domain kapsamı:** Geniş `Domain=.example.com` set eden çerezleri listeleyin. Her birinin gerçekten alt alan adları arası paylaşıma ihtiyacı var mı sorusunu sorun; gereksizse host-only'ye çekin.
- **Alt alan adı envanteri:** Terk edilmiş veya üçüncü tarafa yönlenen (dangling) DNS kayıtlarını izleyin. Subdomain takeover, geniş `Domain` çerezleriyle birleşince çerez enjeksiyonu ve oturum saldırılarına kapı açar.
- **CSRF token doğrulama testi:** Durum değiştiren endpoint'lere cross-site kaynaklı istek simülasyonuyla, SameSite ve CSRF token'ın gerçekten koruma sağladığını test edin. Yalnızca öznitelik varlığına değil, sunucu tarafı token doğrulamasının çalıştığına da bakın.
- **Anomali izleme:** Aynı oturum tanımlayıcısının kısa sürede farklı IP/ağ/kullanıcı-ajanından (User-Agent) gelmesi olası oturum çalınması işaretidir. Oturum çerezini cihaz/istemci bağlamına gevşekçe bağlamak (binding) ve sapmada yeniden kimlik doğrulama tetiklemek etkili bir tespittir.

## Savunma (Defense)

Katmanlı ve tutarlı bir çerez politikası:

1. **Varsayılan güvenli set:** Tüm oturum/auth çerezleri `Secure` + `HttpOnly` + açık `SameSite` (mümkünse `Lax`, gerçekten cross-site gerekmiyorsa `Strict`) ile set edilmeli. Üçüncü taraf bağlam zorunluysa `SameSite=None; Secure` kullanın ve bu çerezin neden gerektiğini belgeleyin.
2. **`__Host-` ön ekini benimseyin:** Oturum ve CSRF token çerezlerinde `__Host-` ön ekiyle çerezi tek origin'e ve `Path=/`'e sabitleyin. Bu, isim tabanlı çerez enjeksiyonuna karşı ucuz ve güçlü bir savunmadır.
3. **SameSite'ı tek savunma sanmayın:** `SameSite`, CSRF'e karşı derin savunmanın bir katmanıdır, tek katmanı değil. Durum değiştiren istekler için ayrıca sunucu tarafı **CSRF token** (senkronize token veya double-submit) ve/veya kaynak doğrulama (`Origin`/`Sec-Fetch-Site` başlıklarının denetimi) uygulayın. Eski tarayıcılar `SameSite`'ı hiç desteklemeyebilir.
4. **`Origin` / `Sec-Fetch-*` başlık kontrolü:** Modern tarayıcılar `Sec-Fetch-Site`, `Sec-Fetch-Mode` gibi Fetch Metadata başlıklarını gönderir. Durum değiştiren endpoint'lerde `Sec-Fetch-Site: same-origin`/`same-site` beklemek, CSRF'e karşı güçlü ve düşük maliyetli bir sunucu tarafı kontroldür.
5. **Dar kapsam ilkesi:** Çerezleri gerektiğinden geniş `Domain` ile yaymayın. Host-only tercih edin. Alt alan adı hijyenini (takeover önleme) çerez güvenliğinin parçası sayın.
6. **Oturum yaşam döngüsü:** Kimlik doğrulama sonrası oturum tanımlayıcısını **yenileyin** (session fixation'a karşı). Yeterli entropiye sahip, tahmin edilemez tanımlayıcılar üretin. Makul idle/absolute timeout uygulayın ve çıkışta sunucu tarafında oturumu geçersiz kılın (yalnızca çerezi silmek yetmez).
7. **Üçüncü taraf durum için `Partitioned`:** Meşru embed işlevselliğinin siteler arası izlemeye dönüşmemesi için `Partitioned` (CHIPS) çerezleri değerlendirin; durumu üst siteye izole edin.
8. **Storage Access API'yi doğru bağlamda kullanın:** Gömülü meşru akışlarda üçüncü taraf çerez erişimini varsaymak yerine, `requestStorageAccess()` ile kullanıcı jesti bağlamında açıkça isteyin ve reddedilme durumunu zarifçe ele alın.
9. **HTTPS'i her yerde zorunlu kılın:** HSTS ile birlikte, çerezlerin düz metin kanala düşmesini engelleyin. `Secure` bayrağının anlamı ancak plaintext HTTP tamamen kapalıysa tamdır.

## Yaygın Hatalar

- **`SameSite=None` yazıp `Secure` unutmak:** Çerez sessizce reddedilir; "neden oturumum düşüyor" hatalarının klasik kaynağı.
- **Varsayılan Lax'a körü körüne güvenmek:** Tarayıcı ve sürümlere göre davranış farkları ve "Lax+POST" istisnası nedeniyle, açık `SameSite` yazmamak riskli. Niyeti daima açıkça belirtin.
- **`SameSite`'ı CSRF'in tek çözümü sanmak:** Aynı-site alt alan adlarından gelen istekler same-site sayılır; güvensiz bir alt alan adı ele geçirilirse `SameSite` koruması delinebilir. Token tabanlı savunmayı bırakmayın.
- **`Path`'i güvenlik sınırı sanmak:** Aynı origin içindeki farklı path'ler birbirini izole etmez. İzolasyon için origin ve `__Host-` kullanın, `Path` değil.
- **Geniş `Domain` çerezi + zayıf alt alan adı:** `Domain=.example.com` ile yayılan oturum çerezi, tek bir savunmasız alt alan adının tüm siteyi riske atmasına yol açabilir.
- **`HttpOnly`'yi XSS panzehiri sanmak:** `HttpOnly` token okumasını zorlaştırır ama XSS varsa saldırgan zaten kurbanın oturumunda istek yapabilir. XSS'i kaynağında (çıktı kodlama, CSP) çözün.
- **Çıkışta yalnızca çerezi silmek:** Sunucu tarafı oturumu geçersiz kılmazsanız, saldırganın elindeki kopya token hâlâ geçerli olabilir. Logout mutlaka sunucu tarafında oturumu sonlandırmalı.
- **`Partitioned`'ı izleme kanalı sanmak veya tümüyle görmezden gelmek:** CHIPS bilinçli olarak siteler arası paylaşımı keser; üçüncü taraf embed'iniz çapraz-site durum bekliyorsa kırılır. Mimarinizi buna göre gözden geçirin.

## Özet

Güvenli çerez tasarımı tek bir bayrağa değil, tutarlı bir öznitelik setine dayanır: `Secure` + `HttpOnly` + açık `SameSite`, tercihen `__Host-` ön ekiyle sabitlenmiş, dar `Domain` kapsamlı çerezler. `SameSite` (Lax/Strict/None) CSRF savunmasının önemli ama tek olmayan katmanıdır; sunucu tarafı token ve Fetch Metadata kontrolleriyle desteklenmelidir. Üçüncü taraf çerezlerin kaldırılması, izlemeyi CHIPS/`Partitioned` gibi izole modellere ve bounce tracking gibi atlatma tekniklerine kaydırırken, Storage Access API meşru gömülü erişimi denetlenebilir hale getirir. Sağlam savunma; doğru öznitelikleri set etmek, `Set-Cookie` başlıklarını sürekli denetlemek, oturum yaşam döngüsünü sağlam yönetmek ve çerez güvenliğini alt alan adı ve HTTPS hijyeniyle bir bütün olarak ele almaktan geçer.
