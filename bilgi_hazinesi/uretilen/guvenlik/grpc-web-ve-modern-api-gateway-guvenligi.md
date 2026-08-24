# gRPC-Web ve Modern API Gateway Güvenliği

## Giriş ve Kapsam

Modern uygulama mimarilerinde tarayıcı ile backend arasındaki iletişim artık yalnızca klasik REST/JSON ile sınırlı değil. **gRPC** (Google Remote Procedure Call), yüksek performanslı, sözleşme (contract) tabanlı bir RPC protokolü olarak servisler arası (service-to-service) iletişimde yaygınlaştı. Ancak gRPC doğrudan tarayıcıdan tüketilemez; bu boşluğu **gRPC-Web** doldurur. Bu makale, gRPC-Web'in tarayıcı tarafından tüketilmesinin güvenlik sonuçlarını, **API Gateway** ve **BFF (Backend-for-Frontend)** katmanındaki yetkilendirme tutarsızlıklarını ve **schema/introspection ifşası** risklerini savunma ve tespit merceğinden ele alır.

Amaç mekanizmayı anlamak ve savunma/tespit kurmaktır; canlı saldırı reçetesi değildir.

## gRPC-Web Nedir ve Neden Var?

### Tanım

gRPC, temelde **HTTP/2** üzerinde çalışan, mesajları **Protocol Buffers (protobuf)** ile ikili (binary) olarak serileştiren bir protokoldür. Tarayıcılar ise HTTP/2'nin gRPC'nin ihtiyaç duyduğu düşük seviye çerçeveleme (framing), trailer'lar ve akış (stream) kontrolü özelliklerine JavaScript'ten tam erişim vermez. Bu nedenle native gRPC tarayıcıdan doğrudan konuşulamaz.

**gRPC-Web**, bu uyumsuzluğu çözmek için tasarlanmış bir varyanttır. Tarayıcıdan çıkan istek, HTTP/1.1 veya HTTP/2 üzerinden taşınabilen, farklı çerçevelenmiş bir formata sahiptir. Arada bir **proxy** (tipik olarak Envoy, ya da bir dil-özel köprü) bu gRPC-Web trafiğini gerçek gRPC'ye çevirir ve backend servise iletir.

### Çalışma Mantığı (Kök Neden)

Akış şöyledir:

1. Tarayıcıdaki JavaScript istemcisi, `.proto` dosyasından üretilmiş kod ile mesajı protobuf olarak serileştirir.
2. Mesaj, gRPC-Web çerçevelemesiyle paketlenir. İki temel varyant vardır: ikili `application/grpc-web+proto` ve **base64 ile kodlanmış** `application/grpc-web-text+proto`. İkincisi, HTTP/1.1 ara katmanlarının ikili gövdeyi bozmamasını sağlamak için kullanılır.
3. Proxy (örneğin Envoy'un gRPC-Web filtresi) bu isteği alır, native gRPC'ye dönüştürür ve backend'e iletir.
4. Yanıt ters yönde çevrilir. gRPC'ye özgü **status kodu** ve **trailer**'lar (örneğin `grpc-status`, `grpc-message`) yanıt gövdesinin sonuna gömülür.

Güvenlik açısından kritik nokta şudur: **gövde ikili/base64 olsa da bu bir şifreleme değildir.** Herhangi biri istemci kodunu veya trafiği çözerek `.proto` şemasını yeniden inşa edebilir. "Binary olduğu için gizli" varsayımı temelden yanlıştır.

## Tehdit Modeli: gRPC-Web Nerede Ayrışır?

gRPC-Web, tarayıcıya açıldığı andan itibaren **güvenilmez istemci (untrusted client)** ilkesine tabidir; ancak birçok ekip onu hâlâ "iç servis" gibi ele alır. Ayrışma noktaları:

### 1. İstemci Tarafı Sözleşme Sızıntısı

Native gRPC'de `.proto` dosyaları genellikle sunucular arasında paylaşılır ve dışarıya çıkmaz. gRPC-Web'de ise istemci kodu **tarayıcıya gönderilen JavaScript bundle'ının içindedir.** Bu, tüm servis tanımlarının, metod adlarının, mesaj alanlarının ve alan numaralarının (field numbers) fiilen kamuya açık olması demektir. Saldırgan bundle'ı analiz ederek:

- Hangi RPC metodlarının var olduğunu,
- Mesaj yapılarını ve opsiyonel alanları,
- Bazen sadece "iç kullanım için" tasarlanmış ama aynı servise gömülü metodları

öğrenebilir.

### 2. "Gizli" Metod Yanılgısı

Bir servis içinde `GetPublicProfile` ile birlikte `AdminDeleteUser` gibi metodlar aynı gRPC servisinde tanımlıysa, UI bunları çağırmasa bile **endpoint erişilebilir durumdadır.** UI'nin butonu göstermemesi bir yetkilendirme kontrolü değildir. Bu, klasik "gizlilikle güvenlik" (security through obscurity) hatasının gRPC-Web versiyonudur.

### 3. Yetkilendirmenin Yanlış Katmanda Yaşaması

En yaygın ve tehlikeli hata: yetkilendirme mantığının API Gateway/BFF katmanında yapıldığı varsayılırken, backend gRPC servisinin **kimlik doğrulanmış ama yetkilendirilmemiş** her isteği kabul etmesi.

## API Gateway ve BFF Katmanının Rolü

### Tanımlar

- **API Gateway**: İstemci trafiğinin girdiği merkezî nokta. TLS sonlandırma, hız sınırlama (rate limiting), kimlik doğrulama (authentication), yönlendirme (routing) ve protokol çevirisi (örn. gRPC-Web → gRPC) gibi işleri üstlenir.
- **BFF (Backend-for-Frontend)**: Belirli bir istemciye (web, mobil) özel, ince bir backend katmanı. Birden çok downstream servisi tek bir istemci-dostu API'ye toplar; genellikle yetkilendirme ve veri şekillendirme burada yapılır.

Bu katmanlar merkezî oldukları için hem savunmanın hem de riskin yoğunlaştığı yerdir.

### Kök Neden: Yetkilendirme Tutarsızlığı (Confused Deputy)

Kritik anti-pattern şudur: Gateway/BFF, gelen kullanıcı token'ını doğrular, sonra downstream gRPC servisine kendi **servis kimliğiyle** (veya token'ı hiç iletmeden) çağrı yapar. Bu durumda:

- Backend servis, isteğin zaten yetkili bir gateway'den geldiğini varsayar ve **kaba yetkilendirme (coarse authz)** yapmaz.
- Gateway, ince taneli (fine-grained) kaynak seviyesi yetkilendirmeyi backend'e bıraktığını sanır.

Sonuç bir **confused deputy** problemidir: her iki katman da diğerinin kontrol yaptığını varsayar, gerçekte **hiçbir katman nesne seviyesinde (object-level) yetki kontrolü yapmaz.** Bu, gRPC dünyasındaki **BOLA (Broken Object Level Authorization)** açığının ta kendisidir: kullanıcı A, `GetInvoice(id=123)` yerine `id=124` göndererek başka kullanıcının faturasına erişir, çünkü backend "gateway zaten baktı" diye kimlik ile kaynak sahipliğini eşleştirmez.

### Örnek Senaryo

Bir e-ticaret uygulamasında:

- Web istemcisi `OrderService.GetOrder(order_id)` çağrısını gRPC-Web ile yapar.
- Envoy tabanlı gateway bunu native gRPC'ye çevirir ve JWT'yi doğrular (kullanıcı gerçekten giriş yapmış mı?).
- Backend `OrderService`, `order_id`'yi sorgular ama **bu order gerçekten bu kullanıcıya mı ait?** kontrolünü yapmaz; çünkü geliştirici bunu "gateway'in işi" sandı.

Saldırgan tarayıcıda kendi geçerli oturumuyla, `order_id`'yi değiştirerek başkalarının siparişlerini okur. Burada saldırı sofistike değildir; eksik olan tek şey **kimlik ile kaynağın backend'de eşleştirilmesidir.**

## Schema ve Introspection İfşası

### gRPC Server Reflection

Native gRPC'nin **Server Reflection** özelliği, istemcilerin çalışma zamanında servisin hangi metodları ve mesajları sunduğunu sorgulamasına izin verir. Geliştirme sırasında `grpcurl` gibi araçlarla test için çok kullanışlıdır. Ancak **üretimde (production) açık bırakılırsa**, sunucu kendi tüm API yüzeyini talep üzerine ifşa eder. Bu, saldırganın `.proto` dosyasına ihtiyaç duymadan tüm servis haritasını çıkarmasını sağlar.

**Savunma ilkesi**: Server Reflection üretimde varsayılan olarak kapalı olmalı; gerekliyse yalnızca iç ağda ve kimlik doğrulamalı olmalıdır.

### GraphQL Introspection ile Paralellik

Aynı sorun GraphQL dünyasında **introspection** sorgularıyla yaşanır: `__schema` ve `__type` alanları tüm tip sistemini döndürür. gRPC-Web ile GraphQL genellikle aynı gateway'in arkasında birlikte bulunur, bu yüzden ekipler ikisini de aynı sertlikte (hardening) ele almalıdır. Üretimde introspection'ı kapatmak tek başına yeterli bir güvenlik önlemi **değildir** (şema yine bundle'dan çıkarılabilir), ama gereksiz keşif yüzeyini daraltan derinlemesine savunmanın (defense in depth) parçasıdır.

### İkili Format Yanılgısı Tekrar

gRPC-Web trafiği base64/binary olduğu için "okunamaz" sanılır. Gerçekte proxy araçları ve tarayıcı eklentileri bu çerçevelemeyi çözebilir. Şema gizliliği asla bir güvenlik sınırı sayılmamalıdır.

## Tespit (Detection)

Tespit, gateway'in merkezî konumunun avantaja çevrildiği yerdir. Trafik burada normalize edilir, dolayısıyla loglanabilir.

### Loglanması Gerekenler

- **RPC metod adı** (tam yol, örn. `/order.OrderService/GetOrder`): Hangi metodların çağrıldığı görünür olmalı.
- **`grpc-status` kodu**: Özellikle `PermissionDenied` (7) ve `Unauthenticated` (16) durumları. Bunların ani artışı bir yetkilendirme sondalaması (probing) işareti olabilir.
- **Kimlik (subject)**: Token'dan çıkarılan kullanıcı/servis kimliği log'a bağlanmalı ki hangi kimliğin hangi kaynağa eriştiği izlenebilsin.

### Anormallik Sinyalleri

- Tek bir kimliğin **kısa sürede çok sayıda farklı nesne ID'sine** erişmeye çalışması (BOLA/IDOR taraması işareti). Ardışık veya rastgele ID denemeleri güçlü bir sinyaldir.
- UI akışında **hiç kullanılmayan bir RPC metoduna** doğrudan çağrı gelmesi. Örneğin normal bir kullanıcı oturumunda hiç tetiklenmeyen `AdminXxx` metoduna trafik.
- Beklenmedik `Content-Type` veya çerçeveleme: gRPC-Web dışı ham gRPC denemeleri gateway'e ulaşıyorsa, protokol katmanı atlanmaya çalışılıyor olabilir.
- **Server Reflection** endpoint'ine üretimde gelen sorgular; normalde hiç olmamalı.

### Korelasyon

Gateway logları, backend servis loglarıyla korele edilmelidir. Gateway "yetki verdim" derken backend'de nesne sahipliği reddi görülüyorsa, mimaride yetkilendirme sorumluluğunun net olmadığı ortaya çıkar. Tutarsız log görünümü başlı başına bir tasarım kokusudur (design smell).

## Savunma (Defense)

### 1. Sıfır Güven: Her Katman Kendi Kontrolünü Yapar

En temel ilke: **backend gRPC servisi, isteğin gateway'den gelmiş olmasına güvenmemelidir.** Kullanıcı kimliği (token veya doğrulanmış bir kimlik başlığı) backend'e kadar taşınmalı ve backend, nesne seviyesi yetkilendirmeyi (bu kaynak bu kullanıcıya mı ait?) kendisi yapmalıdır. Gateway'deki kimlik doğrulama, backend'deki yetkilendirmenin yerini tutmaz.

### 2. Kimlik Aktarımı (Identity Propagation)

Token'ı olduğu gibi iletmek yerine, yaygın ve daha güvenli bir desen **token exchange** veya kısa ömürlü, dar kapsamlı (narrowly-scoped) iç token üretmektir. Amaç: backend'in isteği yapan gerçek son kullanıcının kimliğini güvenilir biçimde bilmesi. mTLS ile servis kimliği + kullanıcı kimliğinin ayrı taşınması olgun bir yaklaşımdır.

### 3. Metod Seviyesi Allowlist

Gateway'de, istemci tipine göre **hangi RPC metodlarına izin verildiği** açıkça beyan edilmelidir (allowlist, denylist değil). Web istemcisinin çağırabileceği metodlar sınırlı bir listeyse, `AdminDeleteUser` gibi metodlar gateway seviyesinde daha backend'e ulaşmadan reddedilir. Bu, sözleşme sızıntısının etkisini azaltır.

### 4. Şema Ayrıştırma

Herkese açık web istemcisinin ihtiyaç duyduğu metodlar, iç/admin metodlarından **ayrı gRPC servislerine** bölünmelidir. Böylece web bundle'ından yalnızca genel servisin sözleşmesi sızar; admin yüzeyi ayrı bir ağ sınırında kalır.

### 5. Reflection ve Introspection Sertleştirme

- gRPC Server Reflection üretimde kapalı.
- GraphQL introspection üretimde kapalı (yalnızca derinlemesine savunma amaçlı, tek başına yeterli değil).
- Bu ayarların CI/CD'de doğrulanması; yanlışlıkla açık kalmasını önlemek için otomatik test.

### 6. Girdi ve Kaynak Doğrulama

Protobuf tip güvenliği sağlar ama iş kuralı doğrulamasını yapmaz. Alan uzunlukları, enum değerleri, sayfa boyutu (pagination limit) gibi sınırlar açıkça doğrulanmalıdır. Aksi halde büyük sayfa istekleri veya derin nesne talepleri **kaynak tüketimi (DoS)** ve toplu veri sızıntısı riski doğurur.

### 7. Hız Sınırlama ve Kota

BOLA taraması genellikle çok sayıda hızlı istek gerektirir. Kimlik başına, metod başına hız sınırlama ve anormal erişim genişliğine karşı kota, taramayı hem yavaşlatır hem tespit edilebilir kılar.

## Yaygın Hatalar (Anti-Patterns)

- **"Binary olduğu için güvenli" varsayımı.** gRPC-Web gövdesi kodlanmıştır, şifreli değildir; şema gizli değildir.
- **UI'nin göstermediği endpoint'i korumasız bırakmak.** Buton yoksa metod yok sanmak. Endpoint her zaman erişilebilirdir.
- **Yetkilendirmeyi tek katmana bırakmak.** Gateway "auth yaptım" derken backend "gateway yaptı" der; sonuç: kimse nesne yetkisini kontrol etmez (confused deputy).
- **Token'ı doğrulamadan sadece varlığını kontrol etmek.** Backend'in gelen bir başlığı doğrulamadan "kullanıcı X" diye kabul etmesi, başlık enjeksiyonuna açık kapıdır. İç kimlik başlıkları backend'e dışarıdan gelmeyecek şekilde ağ düzeyinde temizlenmelidir (header stripping).
- **Server Reflection'ı üretimde açık unutmak.** Geliştirme kolaylığı, kalıcı keşif yüzeyine dönüşür.
- **gRPC status kodlarını loglamamak.** `PermissionDenied` artışları görülmezse yetkilendirme sondalaması sessizce ilerler.
- **GraphQL ve gRPC-Web'i farklı sertlikte ele almak.** Aynı gateway'in arkasındalarsa introspection/reflection politikaları tutarlı olmalı.
- **Alan seviyesi hassas veriyi mesaj tipinde tutmak ama gateway'de filtrelediğini sanmak.** Backend hassas alanı döndürüyorsa, gateway filtrelemesine güvenmek kırılgandır; hassas alan hiç dönmemeli veya ayrı yetki kontrolüne tabi olmalı.

## Özet

gRPC-Web, gRPC'nin performans ve sözleşme avantajlarını tarayıcıya taşır; ama bunu yaparken istemciyi **güvenilmez** kılar ve servis sözleşmesini fiilen kamuya açar. API Gateway ve BFF katmanları bu trafiğin merkezî geçiş noktasıdır: doğru kurulduklarında normalize edilmiş loglama, metod allowlist'i ve kimlik aktarımı ile güçlü bir savunma hattı olurlar; yanlış kurulduklarında ise "diğer katman kontrol ediyor" varsayımıyla **confused deputy** ve **BOLA** açıklarının doğduğu yer olurlar.

Ana ilke sabittir: **her katman kendi yetkilendirmesini yapar, ikili format bir güvenlik sınırı değildir, ve keşif yüzeyi (reflection/introspection/schema) üretimde bilinçli olarak daraltılır.** Tespit tarafında gateway'in merkezî konumu, metod ve status seviyesinde görünürlük sağlayarak yetkilendirme sondalamalarını yakalanabilir kılar.
