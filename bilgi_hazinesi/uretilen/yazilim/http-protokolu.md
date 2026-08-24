# HTTP/1.1, HTTP/2 ve HTTP/3: Derinlemesine Referans

HTTP (HyperText Transfer Protocol), World Wide Web'in taşıyıcı protokolüdür. İstemci (genellikle bir tarayıcı) ile sunucu arasında istek/yanıt (request/response) döngüsüyle çalışan, metin tabanlı kökenli, durumsuz (stateless) bir uygulama katmanı protokolüdür. Ama "HTTP" tek bir şey değildir; bugün üç ana sürüm aynı anda internette dolaşımda: HTTP/1.1, HTTP/2 ve HTTP/3. Bu üç sürüm **anlambilim (semantics)** açısından büyük ölçüde aynıdır (aynı method'lar, aynı durum kodları, aynı header mantığı) ama **taşıma (transport) ve kablo üzerindeki temsil (wire format)** açısından köklü biçimde farklıdır. Bu makale, ortak anlambilimden başlayıp her sürümün neden ortaya çıktığını, hangi darboğazı çözdüğünü ve hangi yeni tuzakları getirdiğini kök nedenleriyle açıklar.

Önemli bir kavramsal ayrım: modern spesifikasyonlarda (RFC 9110 ve devamı) HTTP **anlambilimi** taşıma protokolünden ayrıştırılmıştır. Yani "method nedir, durum kodu nedir, header nedir" sorularının cevabı sürümden bağımsızdır; sürümler yalnızca bu anlambilimi tel üzerinde nasıl kodladığını değiştirir. Bunu en baştan anlamak, üç sürümü kafada doğru yerleştirmenin anahtarıdır.

## Ortak Anlambilim: Method, Durum Kodu ve Header

### HTTP Method'ları: niyetin ifadesi

Bir HTTP isteği, sunucudan ne istediğinizi bir **method** (fiil) ile belirtir. En yaygınları:

- `GET`: Bir kaynağı getir. Yan etkisi olmamalıdır (idempotent ve safe).
- `POST`: Sunucuya veri gönder, genellikle yeni bir kaynak oluştur veya bir işlem tetikle. Idempotent değildir.
- `PUT`: Bir kaynağı verilen temsile göre tümüyle oluştur/değiştir. Idempotent'tir.
- `PATCH`: Bir kaynağı kısmen güncelle.
- `DELETE`: Kaynağı sil. Idempotent'tir.
- `HEAD`: `GET` gibi ama yalnızca header'ları döndür, gövde (body) yok.
- `OPTIONS`: Sunucunun desteklediği yetenekleri sorgula (CORS preflight'ının temeli).

Burada iki kavram kritik ve sık karıştırılır: **safe** ve **idempotent**. Safe bir method sunucu durumunu değiştirmez (`GET`, `HEAD`). Idempotent bir method ise aynı isteği bir kez de gönderseniz on kez de gönderseniz sunucudaki sonuç durumu aynıdır (`PUT`, `DELETE`, `GET`). `POST` idempotent değildir: iki kez gönderirseniz iki kayıt oluşabilir. Bu ayrımın **kök nedeni** ağ güvenilirliğidir: bir istek zaman aşımına uğradığında istemci "gitti mi, gitmedi mi?" bilemez. Idempotent method'lar güvenle yeniden denenebilir (retry); `POST` gibi non-idempotent bir isteği körlemesine retry etmek çift işlem (double charge, çift sipariş) yaratır. Bu yüzden ödeme gibi kritik `POST` uç noktalarında **idempotency key** deseni kullanılır: istemci benzersiz bir anahtar gönderir, sunucu aynı anahtarı ikinci kez görürse işlemi tekrarlamaz.

### Durum Kodları (Status Codes): yanıtın özeti

Sunucu her yanıta üç haneli bir durum koduyla başlar. Sınıflar mantıklı bir hiyerarşi taşır:

- **1xx (Bilgi)**: Ara durum. `100 Continue`, `101 Switching Protocols`.
- **2xx (Başarı)**: `200 OK`, `201 Created`, `204 No Content`.
- **3xx (Yönlendirme)**: `301 Moved Permanently` (kalıcı), `302 Found` / `307 Temporary Redirect` (geçici), `304 Not Modified` (önbellek geçerli).
- **4xx (İstemci hatası)**: `400 Bad Request`, `401 Unauthorized` (kimlik doğrulama gerekli), `403 Forbidden` (yetki yok), `404 Not Found`, `409 Conflict`, `429 Too Many Requests`.
- **5xx (Sunucu hatası)**: `500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`.

Sık yapılan bir hata `401` ile `403`'ü karıştırmaktır. `401` "kim olduğunu bilmiyorum, kimlik doğrula" der; doğru credential ile tekrar denemek anlamlıdır. `403` "kim olduğunu biliyorum ama bu kaynağa erişemezsin" der; aynı credential ile tekrar denemek anlamsızdır. Bir başka önemli ayrım `301` ile `302` arasındadır: `301` kalıcıdır ve tarayıcılar/ara katmanlar bunu agresif biçimde önbelleğe alır. Yanlışlıkla `301` verirseniz, sonradan geri almak zordur çünkü istemciler eski adrese bir daha uğramadan yeni adrese gider. Emin değilseniz `302`/`307` tercih edin.

### Header'lar: mesajın meta verisi

Header'lar `Ad: Değer` biçiminde anahtar-değer çiftleridir ve mesajın gövdesinden ayrı olarak içeriği, önbelleklemeyi, kimliği ve içerik pazarlığını (content negotiation) yönetir. Kritik başlıklar:

- `Content-Type`: Gövdenin MIME türü (`application/json`, `text/html`).
- `Content-Length` / `Transfer-Encoding: chunked`: Gövdenin ne kadar sürdüğünü belirleme yolları.
- `Host`: HTTP/1.1'de zorunlu; tek IP üzerinde birden çok site (virtual hosting) barındırmayı mümkün kılar.
- `Cache-Control`, `ETag`, `Last-Modified`: Önbellekleme ve koşullu istekler.
- `Authorization`, `Cookie`, `Set-Cookie`: Kimlik ve oturum.
- `Accept`, `Accept-Encoding`, `Accept-Language`: İçerik pazarlığı.

Header'ların durumsuz protokoldeki rolü hayatidir: HTTP kendi başına oturum tutmaz, bu yüzden her istek kendi kendine yeterli olmalıdır. Kimlik `Authorization` veya `Cookie` header'ıyla her istekte yeniden taşınır. Bu, header'ları hem çok tekrarlı (her istekte neredeyse aynı `Cookie`, `User-Agent`, `Accept` gider) hem de performans açısından pahalı yapar; ileride göreceğimiz gibi HTTP/2 ve HTTP/3'ün header sıkıştırması tam da bu tekrarı hedefler.

## HTTP/1.1: metin tabanlı temel ve baş darboğazı

### Nasıl çalışır

HTTP/1.1 (1997) insan tarafından okunabilen, satır bazlı, ASCII metin protokolüdür. Bir istek şöyle görünür:

```
GET /index.html HTTP/1.1
Host: example.com
Accept: text/html

```

Sunucu benzer bir metin bloğuyla yanıt verir. Bir TCP bağlantısı üzerinden, `Connection: keep-alive` sayesinde ardışık birden çok istek yapılabilir (persistent connection). Bu, HTTP/1.0'a göre büyük bir kazanımdı: her istek için yeni TCP handshake açmak zorunda kalmazsınız.

### Kök darboğaz: head-of-line blocking

HTTP/1.1'in temel sınırı şudur: **tek bir TCP bağlantısında istekler bir kuyruk gibi sıralı işlenir.** Bir isteğin yanıtı gelmeden, o bağlantıda arkasındaki istekler bekler. Buna **head-of-line (HOL) blocking** denir. Protokol "pipelining" (yanıtı beklemeden art arda istek gönderme) tanımlasa da, yanıtların gönderilen sırayla dönmesi zorunluluğu ve ara katman uyumsuzlukları yüzünden pipelining pratikte hemen hemen hiç kullanılmadı.

Bu darboğazın **kök nedeni**, HTTP/1.1'in tek bağlantıda tek seferde tek istek/yanıt taşıyabilmesidir; birden çok isteği ayırt edecek bir kimliklendirme (stream ID) yoktur. Tarayıcıların buna çözümü kaba kuvvetti: aynı sunucuya (origin) **paralel birden çok TCP bağlantısı** açmak, tipik olarak 6 kadar. Bu, HOL blocking'i kısmen gizler ama başka sorunlar doğurur: her bağlantının kendi TCP slow-start'ı vardır (yani başta yavaştır), her biri ayrı TLS handshake gerektirir, sunucu ve ara katmanlarda bağlantı sayısı katlanır. Bu darboğaz yüzünden geliştiriciler yıllarca **domain sharding** (varlıkları çok sayıda alt alan adına dağıtıp bağlantı limitini aşmak), **CSS sprite** (çok sayıda küçük resmi tek dosyada birleştirmek) ve dosya birleştirme (concatenation) gibi hileler geliştirdi. Bu hilelerin varlığı, protokolün gerçek bir çoklama (multiplexing) mekanizmasından yoksun olduğunun işaretiydi.

## HTTP/2: ikili çerçeveleme ve multiplexing

### Nasıl çalışır: binary framing layer

HTTP/2 (2015, RFC 7540; anlambilim tarafı sonradan RFC 9113'e taşındı), aynı HTTP anlambilimini korur ama tel üzerindeki temsili tümden değiştirir. Metin yerine **ikili (binary) çerçeveler (frame)** kullanır. Tek bir TCP bağlantısı, birden çok mantıksal **stream**'e bölünür; her stream'in bir kimliği (stream ID) vardır. İstek ve yanıtlar `HEADERS` ve `DATA` gibi çerçevelere parçalanır, her çerçeve hangi stream'e ait olduğunu taşır ve bağlantı üzerinde bu çerçeveler iç içe (interleaved) gönderilir.

Bunun sonucu **multiplexing**'tir: tek bir TCP bağlantısı üzerinden onlarca istek gerçekten eşzamanlı akar; birinin yanıtını beklemek diğerlerini engellemez (uygulama katmanında). Böylece HTTP/1.1'in çoklu bağlantı ihtiyacı ortadan kalkar. Domain sharding, sprite ve concatenation gibi hileler artık **anti-pattern** hâline gelir; hatta zararlı olabilirler, çünkü sharding tek bağlantının multiplexing avantajını böler.

### HPACK: header sıkıştırması

HTTP/2, header tekrarına doğrudan saldırır. **HPACK** adlı sıkıştırma algoritması, hem statik bir tablo (sık kullanılan header adları için) hem de dinamik bir tablo (bağlantı boyunca daha önce görülen header'lar için) tutar. İkinci istekte değişmeyen `Cookie`, `User-Agent` gibi başlıklar tam metin olarak değil, tabloya bir indeks referansı olarak gönderilir. Bu, özellikle çok sayıda küçük isteğin olduğu sayfalarda ciddi bant genişliği tasarrufu sağlar. HPACK, sıkıştırmayı kullanan ama sıkıştırma oranı üzerinden bilgi sızdıran saldırılara (CRIME sınıfı) karşı bilinçli olarak dizayn edilmiştir; bu yüzden genel amaçlı gzip yerine header'a özel bir şema seçilmiştir.

### Ek yetenekler ve stream priority

HTTP/2 ayrıca **server push** (istemci istemeden sunucunun kaynak göndermesi) ve **stream priority** (hangi stream'in önce servis edileceğine dair ipuçları) getirdi. Ancak server push pratikte beklenen faydayı vermedi: sunucu genellikle istemcinin önbelleğinde neyin olduğunu bilemez, bu yüzden zaten var olan kaynağı gönderip bant genişliği israf eder. Bu yüzden büyük tarayıcılar zamanla server push desteğini kaldırma yoluna gitti; onun yerine `103 Early Hints` ve `<link rel=preload>` gibi daha güvenli erken-yükleme yöntemleri öne çıktı. Bu, "spesifikasyonda olması iyi olması demek değildir" konusunda öğretici bir örnektir.

### HTTP/2'nin çözemediği şey: TCP seviyesinde HOL blocking

HTTP/2 uygulama katmanındaki HOL blocking'i çözdü ama **taşıma katmanındakini çözemedi**, ve bu onun temel sınırıdır. Kök neden şudur: HTTP/2'nin tüm stream'leri **tek bir TCP bağlantısı** üzerinde akar. TCP ise kendisine teslim edilen byte akışını **sıralı ve kayıpsız** garanti eder. Eğer ağda tek bir TCP paketi kaybolursa, TCP o paket yeniden iletilene kadar **kendisinden sonraki tüm byte'ları** uygulamaya teslim etmeyi durdurur. Oysa kaybolan paket belki yalnızca bir stream'e aitti; ama TCP stream kavramını bilmediği için, kaybolan paketin arkasındaki tüm stream'lerin verisi de bekler. Yani multiplexing sayesinde mantıksal olarak bağımsız olan stream'ler, TCP'nin tek sıralı kuyruğu yüzünden fiziksel olarak birbirine kilitlenir. Bu, özellikle paket kaybının yüksek olduğu mobil ve zayıf ağlarda HTTP/2'yi hatta bazen çoklu bağlantılı HTTP/1.1'den daha kötü duruma düşürebilir. Bu sorunu çözmek için taşıma katmanının kendisini değiştirmek gerekiyordu; işte HTTP/3'ün doğuş nedeni budur.

## HTTP/3 ve QUIC: taşıma katmanını yeniden kurmak

### QUIC nedir ve neden UDP üzerinde?

HTTP/3 (2022, RFC 9114), HTTP anlambilimini yine korur ama TCP'yi tamamen terk eder. Bunun yerine **QUIC** (RFC 9000) adlı yeni bir taşıma protokolü üzerinde çalışır. QUIC ise **UDP** üzerine kurulmuştur. İlk bakışta bu tuhaf gelir: UDP güvenilir değildir, sıra garantisi vermez, akış kontrolü yoktur. Peki neden?

Kök neden **konuşlandırılabilirlik (deployability)**'tir. TCP, işletim sistemi çekirdeğinde (kernel) uygulanır ve internetteki milyonlarca router, firewall ve NAT cihazı (topluca **middlebox** denir) TCP'yi derinden tanır, ona müdahale eder ve tanımadığı yeni TCP seçeneklerini çoğu zaman düşürür (ossification / kemikleşme problemi). Yani TCP'ye yeni bir özellik eklemek pratikte imkansızdır çünkü ara katmanlar buna izin vermez. UDP ise middlebox'lar tarafından basit bir "zarf" olarak görülür. QUIC, güvenilirliği, sıralamayı, akış kontrolünü ve şifrelemeyi UDP'nin **içine**, uygulama uzayında (user space) yeniden inşa eder. Böylece protokol evrimi çekirdek güncellemelerine ve middlebox uyumuna bağımlı olmaktan kurtulur; tarayıcı ve sunucu yazılımı güncellenince yeni QUIC sürümü hemen yayılabilir.

### QUIC'in çözdüğü asıl sorun: stream başına bağımsız teslimat

QUIC'in en önemli özelliği, **stream kavramını taşıma katmanının içine gömmesidir.** Her QUIC stream'i kendi sıralamasını bağımsız olarak yönetir. Bir stream'e ait bir paket kaybolduğunda, QUIC yalnızca **o stream'i** bekletir; diğer stream'lerin verisi kesintisiz uygulamaya teslim olmaya devam eder. Böylece HTTP/2'nin çözemediği **taşıma katmanı HOL blocking'i** kökten ortadan kalkar. HTTP/3'ün multiplexing'i işte bu yüzden "gerçek" multiplexing'tir: hem uygulama hem taşıma katmanında stream'ler birbirinden bağımsızdır.

Header sıkıştırması tarafında HTTP/3, HPACK yerine **QPACK** kullanır. Nedeni yine multiplexing'tir: HPACK'in dinamik tablosu, header'ların **sıralı** işlenmesini varsayar; ama QUIC'te stream'ler sırasız gelebildiği için bu varsayım kırılır. QPACK, dinamik tablo güncellemeleriyle header bloklarını çözerken oluşabilecek bağımlılıkları ayrı bir kodlama akışıyla yöneterek bu sırasızlığa dayanacak biçimde tasarlanmıştır.

### Birleşik handshake ve zorunlu şifreleme

QUIC'in bir başka temel kazanımı **handshake gecikmesini** azaltmasıdır. Klasik HTTPS'te önce TCP handshake (bir gidiş-dönüş, RTT) tamamlanır, sonra TLS handshake (ek RTT'ler) yapılır. QUIC, taşıma ve şifreleme el sıkışmasını **birleştirir**; TLS 1.3 doğrudan QUIC'in içine gömülüdür. Böylece yeni bir bağlantı tipik olarak tek RTT'de kurulabilir. Ayrıca daha önce görüşülmüş bir sunucuya bağlanırken **0-RTT** desteğiyle ilk veri handshake'le birlikte gönderilebilir. 0-RTT güçlü bir hızlanmadır ama bir tuzağı vardır: 0-RTT verisi bir saldırgan tarafından yeniden gönderilebilir (**replay attack**), bu yüzden 0-RTT yalnızca idempotent ve replay'e dayanıklı isteklerde (örneğin `GET`) kullanılmalıdır; ödeme gibi yan etkili işlemler 0-RTT'ye konmamalıdır.

QUIC'te şifreleme **isteğe bağlı değildir**; TLS 1.3 zorunludur. Bu, hem güvenlik hem de kemikleşmeye karşı direnç sağlar: paketlerin çoğu şifreli olduğu için middlebox'lar içeriğe bakıp müdahale edemez, dolayısıyla protokolün ileride evrilmesinin önü açık kalır.

### Connection migration

QUIC'in TCP'ye karşı somut bir kullanıcı-deneyimi üstünlüğü **connection migration**'dır. TCP bağlantısı, dört bileşenle (kaynak IP, kaynak port, hedef IP, hedef port) tanımlanır; telefonunuz Wi-Fi'dan mobil veriye geçtiğinde IP'niz değişir ve TCP bağlantısı kopar, her şey baştan kurulur. QUIC ise her bağlantıya IP'den bağımsız bir **connection ID** verir. Ağ değişse ve IP adresiniz değişse bile, connection ID aynı kaldığı için bağlantı kesintisiz devam edebilir. Bu, hareketli cihazlarda video ve indirmelerin kopmadan sürmesini sağlar.

## Sürümlerin karşılaştırması ve doğru kullanım

Üç sürümü tek bir çerçevede toplarsak: anlambilim (method, durum kodu, header) hepsinde ortaktır; fark taşıma ve kodlamadadır.

- **HTTP/1.1**: Metin, tek bağlantıda tek istek/yanıt, uygulama katmanı HOL blocking, çoklu bağlantı ve sharding hileleriyle telafi.
- **HTTP/2**: İkili çerçeveleme, tek TCP bağlantısında multiplexing, HPACK, ama TCP seviyesinde HOL blocking sürüyor.
- **HTTP/3**: QUIC (UDP üzerinde), stream başına bağımsız teslimat sayesinde HOL blocking yok, QPACK, birleşik handshake, connection migration, zorunlu TLS 1.3.

### Yaygın hatalar ve tuzaklar

**HTTP/2 gelince HTTP/1.1 optimizasyonlarını sürdürmek.** Domain sharding, sprite ve dosya concatenation, HTTP/1.1'in bağlantı limitine karşı çareydi. HTTP/2 ve HTTP/3'te bunlar multiplexing'i sabote eder ve önbellek verimliliğini düşürür. Sürüm yükseltilince bu hileler kaldırılmalıdır. Bu, "eski çözümün yeni ortamda soruna dönüşmesi" için ders niteliğinde bir örnektir.

**HTTP/3 için firewall/UDP'yi unutmak.** Birçok kurumsal ağ UDP trafiğini (özellikle 443 portu üzerinde QUIC'i) engeller veya kısıtlar. HTTP/3, `Alt-Svc` header'ı ile ilan edilir ve istemci önce HTTP/2 üzerinden bağlanıp sonra HTTP/3'e "yükseltmeyi" dener. Bu yüzden HTTP/3 dağıtırken TCP tabanlı bir fallback (HTTP/2) her zaman çalışır durumda bırakılmalıdır; aksi halde UDP'nin engellendiği ağlardaki kullanıcılar siteye hiç erişemez.

**Idempotency ve retry'ı yanlış yönetmek.** Ağ katmanı değişse de bu kural değişmez: non-idempotent `POST` isteklerini otomatik retry etmek çift işlem doğurur. QUIC'in 0-RTT'si bu riski büyütür çünkü 0-RTT verisi replay edilebilir; 0-RTT yalnızca güvenli method'lara açılmalıdır.

**Durum kodlarını gevşek kullanmak.** Hata durumunda `200 OK` dönüp gövdeye "error" yazmak (SOAP-vari bazı API'lerde görülür) önbellekleri, ara katmanları ve izleme araçlarını yanıltır. Anlambilimi doğru taşıyan kod (`4xx`/`5xx`) kullanılmalı; `301` yalnızca gerçekten kalıcı taşımalarda verilmelidir çünkü geri alınması çok zordur.

**Büyük ve tekrarlı header'lara güvenmek.** HPACK/QPACK header'ları sıkıştırsa da, çok büyük Cookie'ler ve gereksiz özel header'lar hâlâ maliyetlidir ve bazı sunucuların header boyutu limitlerine (örneğin `431 Request Header Fields Too Large`) takılabilir. Header'ı hafif tutmak her sürümde iyi pratiktir.

### En iyi pratikler

- **Tüm modern trafiği TLS üzerinden sunun.** HTTP/2 ve HTTP/3 pratikte zaten şifreli çalışır; TLS 1.3 handshake gecikmesini de azaltır.
- **HTTP/3'ü HTTP/2 fallback'i ile birlikte dağıtın.** `Alt-Svc` ile ilan edin, UDP engelli ağları düşünün.
- **Sürüm yükseltirken 1.1 hilelerini temizleyin.** Multiplexing'in avantajını bölmeyin.
- **Method anlambilimine sadık kalın.** Safe/idempotent ayrımına uyun, veri değiştiren işlemleri `GET`'e koymayın (önbellekler ve prefetch bunları yan etkisiz sanır).
- **Önbellekleme header'larını bilinçli kullanın.** `Cache-Control`, `ETag` ile koşullu istekler bant genişliğini ve gecikmeyi her sürümde iyileştirir; taşıma katmanı ne kadar hızlansa da göndermediğiniz byte en hızlısıdır.
- **Kritik `POST` uç noktalarında idempotency key uygulayın.** Böylece retry ve 0-RTT senaryolarında çift işlemden korunursunuz.

## Sonuç

HTTP'nin üç sürümünün hikayesi aslında tek bir problemin, **head-of-line blocking**'in, katman katman aşağı inerek çözülmesinin hikayesidir. HTTP/1.1 istekleri tek bağlantıda kuyruğa soktu ve uygulama katmanında kilitlendi. HTTP/2 ikili çerçeveleme ve stream'lerle uygulama katmanını çözdü ama sorunu TCP'nin tek sıralı kuyruğuna itti. HTTP/3, TCP'yi bırakıp QUIC ile stream'i taşıma katmanının içine gömerek darboğazı kökünden kaldırdı ve üstüne birleşik handshake ile connection migration gibi kazanımlar ekledi. Bu arada method, durum kodu ve header anlambilimi hiç değişmeden kaldı; çünkü asıl mesele "ne söylediğimiz" değil, "onu tel üzerinde ne kadar verimli taşıdığımız"dı. Bir mühendis olarak doğru sezgi şudur: sürüm seçimi bir taşıma kararıdır, anlambilim kararı değil; ve her yeni sürüm bir önceki sürümün en zekice hilesini gereksiz, hatta zararlı hâle getirir.
