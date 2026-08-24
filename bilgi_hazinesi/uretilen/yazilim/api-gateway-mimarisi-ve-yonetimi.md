# API Gateway Mimarisi ve Yönetimi (Kong/Envoy/APISIX, Şema Doğrulama, Versiyonlama Stratejileri)

## Giriş: API Gateway Neden Ayrı Bir Konu?

Mikroservis mimarisine geçen her ekip, er ya da geç şu soruyla karşılaşır: "İstemci, onlarca farklı servise doğrudan mı bağlansın, yoksa tek bir kapıdan mı geçsin?" API gateway, bu sorunun cevabıdır ve REST/GraphQL/gRPC tasarımından veya rate limiting'den kavramsal olarak farklı bir katmandır. API tasarımı "servisin arayüzü ne olmalı" sorusuna, rate limiting ise "ne kadar trafiğe izin verilmeli" sorusuna cevap verirken; gateway mimarisi "istemci ile servisler arasındaki trafik nasıl yönlendirilir, dönüştürülür, birleştirilir ve yönetilir" sorusuna cevap verir. Bu, ayrı bir sorumluluk alanıdır ve kendine özgü kök nedenleri, tuzakları ve en iyi pratikleri vardır.

Bu makale beş temel alt konuyu derinlemesine işler: routing, request/response transformation, API composition ve backend-for-frontend (BFF) deseni, OpenAPI/şema-öncelikli (schema-first) tasarım ve doğrulama, ve son olarak API versiyonlama/deprecation stratejileri. Ayrıca Kong, Envoy ve Apache APISIX gibi somut gateway teknolojilerinin mimari yaklaşımlarını karşılaştırır.

## Kök Neden: Neden Bir Gateway Katmanına İhtiyaç Var?

Mikroservis sayısı arttıkça, istemci tarafında (mobil uygulama, SPA, üçüncü taraf entegratör) şu sorunlar birikir:

1. **Dağınık bağlantı bilgisi**: İstemci, her servisin adresini, kimlik doğrulama yöntemini ve protokolünü ayrı ayrı bilmek zorunda kalır. Bir servis taşındığında veya bölündüğünde tüm istemcilerin güncellenmesi gerekir.
2. **Çapraz kesen ilgiler (cross-cutting concerns) tekrarı**: Kimlik doğrulama, TLS sonlandırma, loglama, rate limiting, CORS gibi kaygılar her serviste ayrı ayrı implemente edilirse hem kod tekrarı hem de tutarsızlık riski oluşur.
3. **Protokol/veri modeli uyumsuzluğu**: Dahili servisler gRPC veya farklı iç şemalar kullanabilirken, dış istemciler REST/JSON veya GraphQL bekleyebilir.
4. **İstemciye özel veri ihtiyaçları**: Bir mobil uygulama ekranı, üç farklı servisten gelen veriyi tek bir yanıtta ister; oysa arka uçta bu veriler ayrı mikroservislerde yaşar.

Gateway, bu sorunları **tek bir merkezi kontrol noktasında** çözerek istemci-servis bağımlılığını gevşetir (decoupling). Bu, aynı zamanda yeni bir risk yaratır: gateway artık tek arıza noktası (single point of failure) ve potansiyel performans darboğazı haline gelir. Bu gerilim -merkezileştirmenin getirdiği fayda ile yarattığı risk arasındaki denge- gateway mimarisinin tüm tasarım kararlarının altında yatan temel çelişkidir.

## Routing: Trafiğin Yönlendirilme Mantığı

### Çalışma Mantığı

Routing, gelen bir isteğin (host, path, header, method, hatta gövde içeriği gibi kriterlere göre) hangi arka uç servise (upstream) iletileceğine karar verme sürecidir. Kavramsal olarak bir routing kuralı üç bileşenden oluşur:

- **Eşleştirici (matcher)**: `Host: api.example.com`, `Path: /siparisler/*`, `Header: X-Api-Version: 2` gibi koşullar.
- **Hedef (upstream/cluster)**: Eşleşen isteğin yönlendirileceği servis grubu ve yük dengeleme politikası.
- **Dönüşüm zinciri (filter chain)**: Yönlendirmeden önce/sonra uygulanacak ara katmanlar (kimlik doğrulama, rate limiting, transformation).

Modern gateway'lerde (Envoy, Kong, APISIX) bu mantık genellikle bir **veri düzlemi (data plane)** ve bir **kontrol düzlemi (control plane)** olarak ikiye ayrılır:

- Veri düzlemi, gerçek trafiği işleyen, düşük gecikmeli, yüksek performanslı proxy'dir (Envoy'un kendisi, Kong'un Nginx/OpenResty tabanlı çekirdeği, APISIX'in Nginx+LuaJIT çekirdeği).
- Kontrol düzlemi, routing kurallarını, servis keşfini (service discovery) ve yapılandırmayı veri düzlemine dağıtan yönetim katmanıdır (örn. Istio'nun `istiod`'u Envoy'u kontrol eder; Kong'un kendi admin API'si veya Kong Konnect; APISIX'in etcd tabanlı yapılandırma deposu).

Bu ayrım önemlidir çünkü **dinamik yeniden yapılandırma** ihtiyacını çözer: yeni bir servis devreye girdiğinde veya bir servisin adresi değiştiğinde, veri düzlemini yeniden başlatmadan (zero-downtime reload) kuralların güncellenmesi gerekir. Envoy'un xDS API'si (Discovery Service protokolleri: LDS, RDS, CDS, EDS) bu dinamik güncellemenin referans mimarisidir ve Istio gibi service mesh'lerin temelini oluşturur.

### Yaygın Hatalar ve Tuzaklar

- **Statik konfigürasyona aşırı bağımlılık**: Routing kurallarını dosya tabanlı statik konfigürasyonla yönetmek, sık değişen mikroservis ortamlarında operasyonel yük yaratır; her değişiklik için redeploy gerekir. Kontrol düzlemi + servis keşfi entegrasyonu (Consul, Kubernetes Endpoints, etcd) bu sorunu çözer.
- **Path matching önceliği karmaşası**: Örneğin `/kullanicilar/{id}` ve `/kullanicilar/aktif` gibi iki route tanımlandığında, eşleştirme sırası (en spesifik önce mi, tanım sırasına göre mi) yanlış anlaşılırsa istekler beklenmeyen servise gider. Bu, üretimde teşhisi zor "sessiz yanlış yönlendirme" hatalarına yol açar.
- **Sağlık kontrolü (health check) eksikliği**: Routing kararı, hedef instance'ın gerçekten sağlıklı olup olmadığını göz ardı ederse, gateway trafiği ölü veya yavaşlayan bir instance'a göndermeye devam eder (bu, dairesel kesici -circuit breaker- ve aktif/pasif health check mekanizmalarının neden gateway'in ayrılmaz parçası olduğunu açıklar).

### En İyi Pratikler

- Routing kurallarını servis keşfi ile entegre edin; statik IP/port listelerinden kaçının.
- Canary/mavi-yeşil (blue-green) dağıtım için weight-based routing (trafiğin yüzdesel dağıtımı) desteğini kullanın.
- Routing katmanını gözlemlenebilir (observable) yapın: her route için latency, hata oranı, istek hacmi metriklerini dışa aktarın.

## Request/Response Transformation

### Tanım ve Kök Neden

Transformation, gateway'in isteği arka uç servise iletmeden önce veya yanıtı istemciye döndürmeden önce içeriğini değiştirmesidir: header ekleme/çıkarma, path yeniden yazma (rewrite), gövde formatı dönüştürme (örn. XML'den JSON'a), kimlik bilgisi enjeksiyonu (JWT'den iç kullanıcı ID'sini çıkarıp header olarak ekleme) gibi.

Bu ihtiyacın kök nedeni, **istemci sözleşmesi ile servis sözleşmesinin birbirinden bağımsız evrimleşmesi gerekliliğidir**. Bir servis iç API'sini değiştirdiğinde (örneğin bir alanın adını `user_id`'den `userId`'ye çevirdiğinde), dışa dönük sözleşmeyi kırmadan bunu gateway seviyesinde absorbe edebilmek, servis ekiplerine bağımsız evrim özgürlüğü tanır. Bu, Postel'in Yasası'nın ("gönderdiğinde tutucu ol, aldığında esnek ol") kurumsal ölçekte pratik uygulamasıdır.

### Nasıl Çalışır

Kong'da bu, plugin mimarisi ile yapılır (`request-transformer`, `response-transformer` gibi eklentiler Lua/OpenResty faz kancalarına -`access`, `header_filter`, `body_filter`- takılır). Envoy'da benzer işlev HTTP filter zinciri ile sağlanır (`lua` filter, `header_mutation` filter, ya da WASM tabanlı özel filtreler). APISIX de benzer şekilde plugin tabanlıdır ve etcd üzerinden dinamik olarak güncellenebilir.

Kavramsal olarak transformation iki fazda gerçekleşir:
- **İstek fazı (pre-proxy)**: İstemciden gelen isteği, arka uca göndermeden önce değiştirir.
- **Yanıt fazı (post-proxy)**: Arka uçtan gelen yanıtı, istemciye göndermeden önce değiştirir.

### Tuzaklar

- **Performans maliyetini görmezden gelmek**: Her transformation adımı, özellikle gövde (body) üzerinde çalışan dönüşümler (JSON parse/serialize), gecikmeye ekler. Yüksek hacimli trafikte bu maliyet kümülatif olarak önemli hale gelir. Body transformation'ı mümkün olduğunca minimize etmek, sadece header/path seviyesinde kalmak tercih edilir.
- **İş mantığının gateway'e sızması**: Transformation katmanı, zamanla "hafif iş mantığı" barındırmaya başlar (örn. koşullu alan hesaplama, iş kuralına dayalı yönlendirme). Bu, gateway'i "gizli bir mikroservis"e dönüştürür ve test edilebilirliği, izlenebilirliği ciddi şekilde bozar. Gateway'in sorumluluğu **altyapısal** olmalı, **iş mantığı** olmamalıdır -bu ayrım net tutulmalı.
- **Sessiz veri kaybı**: Yanlış yapılandırılmış bir response transformer, istemcinin ihtiyaç duyduğu bir alanı yanlışlıkla filtreleyebilir; bu hata genellikle entegrasyon testlerinde değil, üretimde belirli bir istemci sürümüyle ortaya çıkar.

### En İyi Pratikler

- Transformation kurallarını versiyon kontrollü, gözden geçirilebilir konfigürasyon olarak yönetin (GitOps yaklaşımı).
- Transformation'ları küçük, tek sorumluluklu adımlara bölün; test edilebilir olsun.
- Kritik path'lerde (yüksek hacimli endpoint'ler) transformation'ı minimumda tutup, karmaşık dönüşümleri servis tarafına bırakmayı değerlendirin.

## API Composition ve Backend-for-Frontend (BFF) Deseni

### Kök Neden

Mikroservis mimarisinde bir iş kullanım senaryosu (örn. "sipariş detay ekranı") genellikle birden fazla servisten veri toplamayı gerektirir: sipariş servisi, kullanıcı servisi, ürün servisi, kargo servisi. İstemci bu dört isteği ayrı ayrı yaparsa: (a) mobil ağda round-trip gecikmesi katlanır, (b) istemci kodu, arka uç mimarisinin dahili detaylarını (kaç servis olduğunu, hangi sırayla çağrılacağını) bilmek zorunda kalır -bu da sıkı bağlaşım (tight coupling) yaratır.

**API composition**, bu birden fazla arka uç çağrısını gateway (veya ona bağlı bir composition katmanı) seviyesinde birleştirip istemciye tek bir yanıt döndürme desenidir.

**Backend-for-Frontend (BFF)**, composition fikrinin bir adım ileri götürülmüş halidir: her istemci tipi (web, iOS, Android, üçüncü taraf entegratör) için **ayrı bir gateway/agregasyon katmanı** tanımlanır. Web BFF, mobil BFF'den farklı veri şekli, farklı sayfalama, farklı alan kümesi sunabilir -çünkü her istemcinin ihtiyacı farklıdır.

### Neden Bu Ayrım Gerekli?

Tek bir "genel amaçlı" gateway'in tüm istemci tiplerine hizmet vermeye çalışması, zamanla o gateway'in kodunu her istemcinin özel isteklerini karşılayan koşullu mantıkla (if mobile, if web...) doldurur. Bu, **paylaşılan bir bileşenin çoklu paydaş taleplerinin kesişiminde sıkışması** klasik problemidir. BFF deseni, her istemci ekibine kendi agregasyon katmanı üzerinde bağımsız değişiklik yapma özgürlüğü vererek bu sıkışmayı çözer -bedeli, birden fazla BFF'nin bakımını üstlenmektir (operasyonel yük artışı).

### Uygulama Yaklaşımları

1. **Gateway seviyesinde composition**: Kong/APISIX gibi gateway'lerde özel plugin yazarak birden fazla upstream'e paralel istek atıp yanıtları birleştirme. Basit senaryolar için uygundur ama karmaşık iş mantığı gerektiren composition'lar gateway'i şişirir.
2. **GraphQL federasyonu**: GraphQL'in doğal composition yeteneği (bir sorgu, birden fazla alt-grafiği tek yanıtta birleştirir) BFF ihtiyacının önemli bir kısmını organik olarak karşılar. Bu, GraphQL'in mikroservis dünyasında popülerleşmesinin başlıca nedenlerinden biridir.
3. **Ayrı BFF servisi**: Gateway'in arkasında, her istemci tipine özel ince bir orkestrasyon servisi (Node.js/Go gibi hafif bir katman) çalıştırma. İş mantığı barındırma riski gateway'den ayrıldığı için daha temiz bir sorumluluk ayrımı sağlar; çoğu olgun mimaride tercih edilen yol budur.

### Tuzaklar

- **Composition katmanında senkron zincir çağrılar**: A servisini çağır, sonucunu kullanarak B'yi çağır, onun sonucuyla C'yi çağır -bu zincir, gecikmenin toplamsal (additive) değil çarpımsal risk taşımasına yol açar (bir servis yavaşlarsa tüm zincir yavaşlar). Mümkün olduğunca bağımsız çağrıları paralelleştirmek (fan-out/fan-in) gerekir.
- **Kısmi başarısızlık yönetimi eksikliği**: Dört servisten biri hata verdiğinde, composition katmanı "hepsi ya da hiçbiri" mi davranacak yoksa kısmi yanıt mı dönecek karar net olmalı. Bu karar verilmezse istemci tarafında tutarsız/belirsiz davranışlar ortaya çıkar.
- **BFF'lerin kendi aralarında kod tekrarına düşmesi**: Her BFF ayrı bakım gerektirdiğinden, ortak mantık (kimlik doğrulama, hata formatı) tekrar tekrar yazılabilir. Paylaşılan kütüphaneler/şablonlar ile bu tekrar azaltılmalı.

## OpenAPI / Şema-Öncelikli (Schema-First) Tasarım ve Doğrulama

### Kavram

Şema-öncelikli tasarım, bir API'nin implementasyonundan **önce** sözleşmesinin (OpenAPI/Swagger belgesi, gRPC için `.proto` dosyası, GraphQL için SDL) tanımlanmasıdır. Bu belge, hem insan hem makine tarafından okunabilir; istemci SDK'ları, sunucu iskeletleri (stub), dokümantasyon ve doğrulama kuralları bu tek kaynaktan (single source of truth) üretilir.

### Kök Neden: Neden Şema Doğrulama Gateway'e Taşınır?

Sözleşme ihlali (contract violation) -istemcinin beklenmeyen bir alan göndermesi, servisin dokümante edilenden farklı bir yanıt döndürmesi- geleneksel olarak her serviste ayrı ayrı doğrulama koduyla (genellikle eksik veya tutarsız şekilde) ele alınır. Şema doğrulamasını **gateway seviyesine** taşımanın mantığı şudur:

1. **Savunma derinliği (defense in depth)**: Gateway, kötü biçimlendirilmiş veya şemaya uymayan istekleri servise ulaşmadan reddeder. Bu, hem servisin kendi doğrulama yükünü azaltır hem de şema ihlali kaynaklı hataların (örn. beklenmedik tip nedeniyle oluşan çökme) arka uca sızmasını engeller.
2. **Tutarlılık**: Tüm servisler için doğrulama mantığı tek bir yerde, tek bir motor ile (örn. JSON Schema validator) uygulanır; her ekip kendi doğrulama kodunu yazıp güncel tutmak zorunda kalmaz.
3. **Erken hata tespiti**: İstemci geliştiricisi, sözleşmeye uymayan bir istek gönderdiğinde hatayı hemen (gateway'den 400 yanıtıyla) görür, servisin iç loglarını kazmak zorunda kalmaz.

### Nasıl Çalışır

Kong'da `openapi-enforcer` gibi pluginler veya doğrudan OpenAPI belgesinden route/plugin konfigürasyonu üreten araçlar (deck, Kong Ingress Controller'ın OpenAPI CRD desteği) kullanılabilir. APISIX benzer şekilde `openapi-validator` tarzı pluginlerle şema doğrulamasını destekler. Envoy'da bu genellikle bir WASM filtresi veya harici bir doğrulama servisi (external authorization/ext_authz filtresi ile) olarak uygulanır çünkü Envoy'un çekirdeği şema doğrulamayı native olarak hedeflemez -bu tasarım tercihi, Envoy'un "genel amaçlı proxy" felsefesini yansıtır.

Doğrulamanın kapsamı: istek path/query parametreleri, header'lar, gövde şeması (JSON Schema/OpenAPI şema tanımına göre tip, zorunlu alan, enum, format kontrolü), ve isteğe bağlı olarak yanıt şeması (özellikle test/staging ortamlarında, servisin kendi sözleşmesini ihlal etmediğini doğrulamak için).

### Yaygın Hatalar

- **Şemanın kod ile senkron kalmaması (schema drift)**: OpenAPI belgesi elle yazılıp koddan bağımsız güncellenirse, zamanla gerçek davranışla belge birbirinden sapar. Bu, "şema-öncelikli" iddiasını boşa çıkarır. Kod-öncelikli (code-first, anotasyonlardan şema üretimi) veya sıkı CI kontrolleri (şemanın gerçek davranışla test edilmesi -contract testing, örn. Pact) ile bu risk azaltılmalı.
- **Aşırı gevşek şemalar**: Her alanı `optional` ve tipi `any`/`object` bırakmak, doğrulamayı anlamsız kılar; bu genellikle geliştiricilerin "şema hatası yüzünden entegrasyon kırılmasın" korkusuyla yaptığı bir kısayoldur ama gerçek koruma sağlamaz.
- **Gateway'de doğrulama var diye serviste doğrulamayı tamamen kaldırmak**: Savunma derinliği ilkesine aykırıdır; gateway atlanabilir (iç ağdan doğrudan servise erişim, yanlış yapılandırma, gateway güvenlik açığı) senaryolarında servis savunmasız kalır. Gateway doğrulaması bir **ilk hat**tır, tek hat değildir.

### En İyi Pratikler

- OpenAPI belgesini kod tabanının bir parçası olarak, CI/CD içinde otomatik doğrulanan (linting: örn. Spectral gibi araçlarla) bir yapı olarak tutun.
- Gateway'deki şema doğrulamasını, servis içi doğrulamanın **yerine değil, tamamlayıcısı** olarak konumlandırın.
- Yanıt şeması doğrulamasını üretimde performans nedeniyle kapatıp, CI/staging'de açık tutmak yaygın ve makul bir dengedir.

## API Versiyonlama ve Deprecation Stratejileri

### Kök Neden

Bir API'nin sözleşmesi zamanla değişmek zorundadır (yeni iş gereksinimleri, hatalı tasarım kararlarının düzeltilmesi, güvenlik iyileştirmeleri). Ancak API'nin tüketicileri (istemciler) genellikle gateway/servis sahibinin kontrolü dışındadır -mobil uygulamalar app store onay sürecinde bekler, üçüncü taraf entegratörler kendi hızlarında güncellenir. Bu asimetri -**sağlayıcı istediği an değişebilir ama tüketici istediği an güncellenemez**- versiyonlama stratejisinin temel gerekçesidir.

### Versiyonlama Yaklaşımları

1. **URI versiyonlama** (`/v1/siparisler`, `/v2/siparisler`): En açık ve önbelleklemeye (caching) en dostu yöntemdir; ama her yeni versiyon aslında yeni bir kaynak/route seti anlamına gelir, bu da gateway routing tablosunun büyümesine yol açar.
2. **Header tabanlı versiyonlama** (`Accept: application/vnd.example.v2+json` veya özel `X-Api-Version` header'ı): URI'yi temiz tutar ama önbellekleme ve hata ayıklama (curl ile hızlı test etme) daha zahmetlidir; istemcilerin header'ı doğru göndermeyi unutması yaygın bir operasyonel sorundur.
3. **Query parametre versiyonlama** (`?version=2`): Basittir ama REST semantiğiyle daha az uyumludur, önbellek anahtarlama karmaşıklaşabilir.

Hiçbir yöntem evrensel olarak "doğru" değildir; seçim, önbellekleme ihtiyacı, istemci çeşitliliği ve operasyonel tercihlere bağlıdır. Önemli olan, **seçilen stratejinin tutarlı uygulanması ve gateway seviyesinde merkezi olarak yönetilmesidir** -versiyon yönlendirme mantığının her serviste ayrı ayrı tekrarlanması, versiyonlar arası tutarsızlığa yol açar.

### Deprecation: Kaldırmanın Yönetimi

Yeni versiyon çıkarmak, eski versiyonu **ne zaman ve nasıl** kaldıracağınızı planlamadan yapılırsa, sonsuza kadar büyüyen bir versiyon yığınına dönüşür. Sağlıklı bir deprecation süreci şu unsurları içerir:

- **Deprecation sinyali**: Yanıt header'larında (`Deprecation: true`, `Sunset: <tarih>` -RFC 8594 tarzı yaklaşımlar) istemcilere önceden haber verme. Bu, gateway seviyesinde merkezi olarak enjekte edilebilecek bir header transformation'dır -yukarıda anlatılan transformation mekanizmasıyla doğrudan ilişkilidir.
- **Kullanım telemetrisi**: Hangi istemcilerin hâlâ eski versiyonu kullandığını gateway loglarından/metriklerinden izlemek. Bu veri olmadan "kimseyi kırmadan kaldırabilir miyiz" sorusuna cevap veremezsiniz.
- **Kademeli kısıtlama**: Sertçe kapatmak yerine, eski versiyona rate limit uygulamak, sonra belirli bir tarihte 410 Gone döndürmek gibi aşamalı bir geçiş.
- **Sözleşme genişletme kuralı (backward-compatible evolution)**: Mümkün olduğunca yeni versiyon açmak yerine, sözleşmeyi geriye dönük uyumlu şekilde genişletmek (yeni alan ekleme -zorunlu olmayan-, yeni endpoint ekleme) tercih edilmeli; versiyon sıçraması sadece kırıcı (breaking) değişikliklerde gerekli olmalı. "Kırıcı değişiklik" tanımını netleştirmek (alan kaldırma, tip değiştirme, zorunlu alan ekleme, anlamsal davranış değişikliği) ekip içi bir sözleşme olmalı.

### Yaygın Hatalar

- Versiyonlama stratejisini API büyüdükten sonra düşünmek -baştan bir strateji benimsemeyip her ekibin kendi yöntemini seçmesi, gateway'de tutarsız bir routing/header karmaşasına yol açar.
- Deprecation duyurusu yapmadan veya yetersiz süre tanıyarak eski versiyonu aniden kapatmak -bu, entegrasyon güvenini (trust) kalıcı olarak zedeler.
- Sonsuza kadar çoklu versiyonu canlı tutmak -her versiyon, gateway ve servis tarafında ayrı test/bakım yükü taşır; bu yük genellikle hafife alınır ve zamanla teknik borç birikimine dönüşür.

## Kong, Envoy ve APISIX: Mimari Karşılaştırma

Bu üç teknoloji sıkça birlikte anılsa da farklı mimari felsefelere sahiptir:

- **Kong**: Nginx/OpenResty (LuaJIT) üzerine kurulu, plugin mimarisiyle genişletilen, API yönetimi odaklı bir gateway. Güçlü yanı zengin plugin ekosistemi ve declarative (bildirimsel) konfigürasyon (Kong'un DB-less modu). Kong Gateway hem tek başına API gateway hem de Kubernetes Ingress Controller olarak kullanılabilir.
- **Envoy**: Başlangıçta Lyft tarafından geliştirilen, C++ ile yazılmış, yüksek performanslı genel amaçlı bir proxy/sidecar. API gateway'den daha geniş bir kapsamı hedefler -service mesh veri düzleminin (Istio, Consul Connect) temel bileşenidir. xDS API'si üzerinden dinamik konfigürasyon, gözlemlenebilirlik (native olarak zengin metrik/tracing desteği) ve genişletilebilirlik (native filtreler + WASM) güçlü yanlarıdır. Ancak API yönetimi (geliştirici portalı, API anahtarı yönetimi gibi üst seviye özellikler) native olarak sağlanmaz; bunun için genellikle üzerine bir kontrol katmanı (Istio, veya Envoy tabanlı ticari ürünler) eklenir.
- **Apache APISIX**: Nginx+LuaJIT tabanlı, etcd'yi konfigürasyon deposu olarak kullanan, plugin mimarisiyle genişletilen bir gateway. Kong'a kavramsal olarak yakındır ama etcd tabanlı dağıtık konfigürasyon senkronizasyonu ve daha hafif/hızlı plugin geliştirme deneyimi öne çıkan farklardandır.

Seçim kriteri genellikle şu eksende şekillenir: eğer amaç **service mesh** (servisler arası iç trafik yönetimi, mTLS, ince taneli gözlemlenebilirlik) ise Envoy tabanlı çözümler (Istio) doğal seçimdir. Eğer amaç **kenar (edge) API yönetimi** (dış istemcilere API anahtarı, geliştirici portalı, kota yönetimi sunmak) ise Kong veya APISIX gibi API-yönetimi-öncelikli gateway'ler daha uygundur. Büyük mimarilerde ikisi birlikte de kullanılır: Envoy/Istio iç mesh'i yönetirken, Kong/APISIX dış kenar noktasında durur.

## Tespit ve Savunma Perspektifi: Gateway'i Güvenlik Kontrol Noktası Olarak Görmek

Savunma açısından gateway, saldırı yüzeyinin merkezi bir gözlem ve müdahale noktasıdır:

- **Anomali tespiti**: Routing/transformation katmanından geçen tüm trafiğin merkezi loglanması, anormal path deseni taramaları (path traversal denemeleri, bilinmeyen route'lara yoğun istek) veya şema ihlali oranındaki ani artışları (olası fuzzing/saldırı denemesi sinyali) tespit etmeyi kolaylaştırır.
- **Şema doğrulamasının güvenlik faydası**: Sıkı şema doğrulama, birçok enjeksiyon sınıfı saldırının (beklenmeyen tip/format ile servise ulaşmaya çalışma) ilk savunma hattıdır -ama tek başına yeterli değildir, servis tarafı girdi doğrulaması hâlâ gereklidir.
- **Versiyon/deprecation güvenlik boyutu**: Kullanılmayan eski API versiyonları, genellikle güvenlik yamalarının uygulanmadığı, unutulmuş saldırı yüzeyleridir ("gölge API" -shadow API- riski). Aktif envanter ve zamanlı deprecation, bu riski azaltan operasyonel bir güvenlik pratiğidir.
- **Gateway'in kendisinin sertleştirilmesi**: Gateway tek arıza/saldırı noktası olduğundan, admin API'sinin (Kong Admin API, APISIX Admin API) ağ seviyesinde izole edilmesi, kimlik doğrulamasının zorunlu kılınması kritik önemdedir -yanlış yapılandırılmış (kimlik doğrulamasız) bir admin API, tüm gateway'in ele geçirilmesi anlamına gelebilir.

## Sonuç

API gateway mimarisi, mikroservis dünyasında istemci-servis ilişkisini yöneten kritik bir soyutlama katmanıdır. Routing, isteklerin doğru yere gitmesini sağlarken dinamik servis keşfiyle beslenmelidir; transformation, sözleşmeler arası esnekliği sağlarken iş mantığı sızıntısına karşı disiplinli tutulmalıdır; composition ve BFF deseni, istemciye özel ihtiyaçları karşılarken merkezi bir gateway'in şişmesini önler; şema-öncelikli tasarım ve doğrulama, sözleşme bütünlüğünü savunma derinliği ilkesiyle korur; versiyonlama ve deprecation ise API'nin zaman içindeki evrimini, tüketicilerin güvenini kaybetmeden yönetmenin disiplinidir. Kong, Envoy ve APISIX gibi araçlar bu kavramları farklı mimari felsefelerle somutlaştırır, ama altta yatan tasarım gerilimleri -merkezileştirme faydası ve riski, esneklik ile sorumluluk sınırı, sağlayıcı özgürlüğü ile tüketici istikrarı- her araçta aynı kalır.
