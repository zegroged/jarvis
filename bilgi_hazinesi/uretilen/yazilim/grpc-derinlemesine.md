# gRPC Derinlemesine: HTTP/2 Framing, Interceptor Zinciri, Deadline/Cancellation

## Neden Bu Konu Yüzeysel Geçilemez

Çoğu "API tasarımı" listesi gRPC'yi tek satırda "REST'e alternatif, Protobuf kullanır, hızlıdır" diye geçiştirir. Bu, bir mühendisin üretimde karşılaşacağı gerçek sorunların hiçbirine cevap vermez: Neden bir gRPC servisi CPU'yu %100'e sürüklüyor ama trafik normal görünüyor (HTTP/2 flow control kilitlenmesi)? Neden bir istemcinin "timeout" hatası aslında sunucuda işlemin hâlâ çalışmasına engel olmuyor (deadline propagation eksikliği)? Neden bir güvenlik denetçisi "reflection API'yi kapatın" diyor da kimse nedenini bilmiyor? Bu makale gRPC'yi bir **protokol yığını** olarak ele alıyor: HTTP/2 üzerindeki framing'den, uygulama katmanındaki interceptor zincirine, oradan da deadline ve güvenlik modeline kadar. Amaç ezber değil, mekanizmayı görüp doğru savunma kararını kendi başınıza verebilmek.

---

## 1. gRPC Neden HTTP/2 Üzerine Kuruludur

gRPC'nin REST/JSON'dan temel farkı taşıma katmanı seçimidir. HTTP/1.1 her istek için (keep-alive olsa bile) sıralı bir istek-cevap modeli sunar; aynı bağlantı üzerinde eşzamanlı çoklu akış (multiplexing) yoktur, bu da "head-of-line blocking" (HOL blocking) yaratır. HTTP/2 ise tek bir TCP bağlantısı üzerinde birden fazla bağımsız **stream**'i eşzamanlı taşıyabilir. gRPC bunu doğrudan miras alır: her RPC çağrısı bir HTTP/2 stream'idir.

### Framing Mekaniği (Kök Neden)

HTTP/2, verinin tamamını tek seferde göndermek yerine onu **frame**'lere böler. Her frame şu genel yapıya sahiptir: 9 bayt sabit başlık (length, type, flags, stream ID) + payload. Önemli frame tipleri:

- **HEADERS**: HTTP başlıklarını (ve gRPC'de `:path`, `content-type: application/grpc`, `grpc-timeout` gibi pseudo-header'ları) taşır. HPACK ile sıkıştırılır.
- **DATA**: Gerçek mesaj gövdesini taşır. gRPC burada kendi iç zarfını (length-prefixed message framing: 1 bayt compression flag + 4 bayt big-endian uzunluk + protobuf-encoded mesaj) kullanır. Yani **iki katmanlı framing** vardır: HTTP/2 frame'i, onun içinde gRPC'nin kendi mesaj zarfı.
- **RST_STREAM**: Bir stream'i tek taraflı sonlandırır (örneğin istemci `Cancel()` çağırdığında).
- **GOAWAY**: Tüm bağlantıyı düzgün kapatmak için kullanılır (sunucu yeniden başlarken).
- **WINDOW_UPDATE**: Flow control kredisi bildirir.
- **SETTINGS**: Bağlantı parametrelerini (max concurrent streams, başlangıç pencere boyutu vb.) müzakere eder.

**Neden bu detay önemli?** Çünkü gRPC'nin "streaming" iddiası aslında HTTP/2'nin stream çoğullaması üzerine kurulu bir soyutlamadır. Bir unary RPC bile arka planda bir HTTP/2 stream'i açar, HEADERS + DATA + trailing HEADERS (status için) gönderir ve stream'i kapatır. Bunu bilmeden "gRPC neden bazen bağlantı başına stream limiti aşınca hata veriyor" (`ENHANCE_YOUR_CALM` / too many concurrent streams) sorusunu teşhis edemezsiniz.

### Flow Control: Sık Görülen Performans Tuzağı

HTTP/2'de hem **bağlantı seviyesinde** hem **stream seviyesinde** flow control penceresi vardır (varsayılan genelde 64KB civarı, ayarlanabilir). Sunucu veya istemci `WINDOW_UPDATE` göndermezse, karşı taraf veri göndermeyi durdurur — bu bir deadlock değildir ama pratikte öyle hissettirir: RPC "asılı kalır", CPU boşta görünür, ağ trafiği sıfırlanır. Bu genelde şu senaryoda ortaya çıkar: sunucu tarafında büyük bir streaming response üretiliyor ama istemci mesajları okumuyor (örneğin başka bir senkron işlemle meşgul) — pencere dolar, akış durur. **Kök neden**: Akış kontrolü, uygulama kodunun mesajları tüketme hızına bağımlıdır; yavaş tüketici tüm stream'i durdurabilir.

**Savunma/tespit**: gRPC istemci/sunucu kütüphanelerinde flow control penceresi metriklerini (çoğu implementasyon `grpc.keepalive` ve akış istatistiklerini expose eder) izleyin. Uzun süredir "0 byte/s" olan ama kapanmamış stream'ler tipik bir semptomdur.

---

## 2. Streaming Türleri: Dördü de Aynı Mekanizmanın Farklı Kullanımı

gRPC dört RPC türü tanımlar; hepsi aynı HTTP/2 stream soyutlamasının farklı mesaj sayısı kombinasyonlarıdır:

1. **Unary**: 1 istek → 1 cevap. Tek stream, tek DATA frame seti her yönde.
2. **Server streaming**: 1 istek → N cevap. İstemci stream'i açar, tek istek gönderir, sunucu istediği kadar DATA frame'i art arda gönderip stream'i kapatır.
3. **Client streaming**: N istek → 1 cevap. İstemci birden fazla DATA frame'i gönderir, bitirince `half-close` yapar (kendi yönünü kapatır), sunucu tek cevap döner.
4. **Bidirectional streaming**: N istek ↔ N cevap, tam çift yönlü. Her iki taraf da bağımsız olarak kendi yönünü istediği zaman kapatabilir (`half-close` her iki yönde de ayrı ayrı olur).

**Kritik kavram — half-close**: HTTP/2 stream'i iki yarı-akıştan oluşur (istemciden sunucuya, sunucudan istemciye). Bir taraf kendi göndermesini bitirdiğini bildirebilir (END_STREAM flag'i) ama karşı taraftan veri almaya devam edebilir. Bidi streaming'in gücü tam olarak buradan gelir. Yaygın hata: geliştiriciler bidi stream'i "iki ayrı unary çağrı gibi" tasarlayıp senkronizasyon karmaşasına düşer — oysa doğru model, iki bağımsız mesaj kuyruğu olarak düşünmektir.

**En iyi pratik**: Server/client streaming'i sadece gerçekten sınırsız veya büyük hacimli veri aktarımında kullanın (örneğin log tail'i, dosya parçaları). Basit "birden fazla sonuç dönen" senaryolarda unary + sayfalama (pagination) çoğu zaman daha basit ve daha kolay hata yönetilebilir — streaming; bağlantı kopması, kısmi teslimat, backpressure gibi ek karmaşıklık maliyeti getirir.

---

## 3. Interceptor Zinciri: gRPC'nin Middleware Mimarisi

Interceptor'lar, HTTP middleware'lerinin gRPC karşılığıdır ama RPC'nin yaşam döngüsüne (çağrı öncesi/sonrası, streaming mesaj bazında) daha ince taneli erişim sağlarlar. İki eksen vardır: **istemci tarafı / sunucu tarafı** ve **unary / streaming**.

### Çalışma Mantığı

Sunucu tarafında bir unary interceptor şu imzaya benzer bir sarmalayıcıdır: `(context, request, handler) -> response`. Interceptor, `handler`'ı (gerçek servis metodunu veya bir sonraki interceptor'ı) çağırmadan önce ve sonra kod çalıştırabilir. Birden fazla interceptor zincirlendiğinde, bir **soğan (onion) modeli** oluşur: ilk interceptor en dışta, son interceptor gerçek handler'a en yakın katmandır. Çağrı dışarıdan içeriye, cevap içeriden dışarıya akar.

Streaming interceptor'lar daha karmaşıktır çünkü tek bir `request/response` yerine bir `ServerStream` nesnesini sarmalarlar — her `SendMsg`/`RecvMsg` çağrısını yakalayabilirler. Bu, mesaj bazında loglama, mesaj boyutu sınırlama veya mesaj bazında yetkilendirme gibi ihtiyaçlar için gereklidir.

### Tipik Kullanım Alanları (Neden Interceptor Kullanılır)

- **Authentication/Authorization**: Gelen metadata'dan (HTTP/2 HEADERS frame'inde taşınan) token'ı çıkarıp doğrulamak. Bunu her servis metodunda tekrar tekrar yazmak yerine tek bir noktada merkezi hale getirir.
- **Logging/Tracing**: Her RPC'nin başlangıç/bitiş zamanını, trace context'ini (W3C traceparent gibi) metadata üzerinden taşımak.
- **Metrik toplama**: RPC süresi, hata kodu dağılımı.
- **Rate limiting**: İstemci/servis bazında.
- **Panik/recover**: Sunucu tarafında bir handler panik atarsa, interceptor bunu yakalayıp düzgün bir `INTERNAL` status'una çevirebilir — yoksa bağlantı çirkin şekilde kopar.
- **Deadline/context enforcement**: Aşağıda detaylandırılan deadline mekanizmasının uygulama tarafı genelde interceptor'da devreye girer (örneğin "eğer context zaten iptal olduysa handler'ı hiç çağırma").

### Yaygın Hata: Zincir Sırası ve Context Sızıntısı

İnterceptor zincirinde sıra önemlidir. Auth interceptor'ı logging interceptor'ından *sonra* koyarsanız, yetkisiz isteklerin detaylarını loglarsınız (bilgi ifşası riski olabilir) ama daha kötüsü, auth'dan önce çalışan bir interceptor yanlışlıkla hassas payload'ı işleyebilir. **En iyi pratik**: recover/panic-guard en dışta, sonra auth, sonra tracing/logging, en içte iş mantığına özel interceptor'lar.

İkinci yaygın hata: interceptor içinde context'i değiştirip yeni context'i `handler`'a geçirmeyi unutmak (`handler(newCtx, req)` yerine yanlışlıkla eski context'i geçirmek) — bu, context'e eklenen değerlerin (user ID, trace ID) alt katmanlara hiç ulaşmamasına yol açar; sessiz bir hata sınıfıdır, sadece testte fark edilir.

---

## 4. Deadline Propagation ve Cancellation: En Çok Yanlış Anlaşılan Konu

### Kavram: Timeout Değil, Deadline

gRPC'de istemci bir **timeout süresi** değil, sunucuya "şu mutlak zamana kadar" anlamına gelen bir **deadline** gönderir (`grpc-timeout` header'ı aslında relative bir süre olarak kodlanır ama sunucu bunu aldığı anda kendi mutlak deadline'ına çevirir — saat senkronizasyon farklarını relative gönderim minimize eder). Bu deadline, RPC'nin `Context`'ine (Go'da `context.Context`, Java'da `Context`, vb.) bağlanır.

### Kök Neden — Neden Propagation Şart

Gerçek sistemlerde bir istek genelde tek bir servise değil, bir **çağrı zincirine** gider: A → B → C → D. Eğer A, B'ye "500ms içinde cevap ver" der ve B bunu C'ye ve D'ye **iletmezse**, şu olur: A 500ms sonra vazgeçer ve istemciye hata döner, ama B, C, D zincirinde işlem **hâlâ çalışmaya devam eder** — CPU, veritabanı bağlantısı, kilit gibi kaynaklar boşuna tüketilir. Buna genelde "hayalet istek" (istemci artık cevabı beklemiyor ama sunucu hâlâ çalışıyor) denir. gRPC'nin doğru kullanımı, her ara servisin gelen deadline'ı **context aracılığıyla otomatik olarak** bir sonraki çağrıya taşımasıdır — çoğu gRPC istemci kütüphanesi, context'ten yeni bir stub çağrısı yapıldığında bunu otomatik yapar, ama bu "otomatik"lik sadece context doğru taşınırsa çalışır.

**Yaygın hata #1**: Bir handler içinde gelen `ctx`'i kullanmak yerine `context.Background()` (Go) veya benzeri "taze/boş" bir context ile alt servise çağrı yapmak. Bu, deadline zincirini kırar — üst servis vazgeçse bile alt servis sonsuza kadar (kendi varsayılan deadline'ı neyse o kadar, hatta hiç yoksa süresiz) çalışmaya devam eder. Bu, kod incelemesinde aranması gereken **somut ve tespit edilebilir** bir anti-pattern'dir: "bu RPC handler'ı, gelen context'i mi yoksa yeni bir context mi kullanıyor?"

**Yaygın hata #2**: Deadline'ı çok sıkı ayarlamak, retry mantığıyla birleştiğinde "deadline amplifikasyonu" yaratır — her retry, kalan süreyi daha da azaltır ve zincirin derinliklerindeki servisler pratikte hiç çalışma şansı bulamadan iptal edilmiş context alır.

### Cancellation Mekaniği

Cancellation, deadline'ın "biri bitmeden önce elle tetiklenen" halidir: istemci `Cancel()` çağırdığında, istemci tarafı bir **RST_STREAM** frame'i gönderir (HTTP/2 seviyesinde). Sunucu tarafında bu, context'in `Done()` kanalının (veya eşdeğerinin) tetiklenmesi olarak yüzeye çıkar. **Doğru davranış**: uzun süren handler'lar (özellikle döngü içinde iş yapanlar) periyodik olarak context'in iptal edilip edilmediğini kontrol etmeli ve iptal edildiyse işi erken sonlandırmalıdır. Bunu yapmamak, cancellation'ı sadece "istemci artık cevabı almayacak" anlamına indirger ama sunucu kaynak tüketimini durdurmaz — kaynak tükenmesi (resource exhaustion) saldırılarına karşı savunmasızlık yaratır: bir saldırgan çok sayıda pahalı RPC başlatıp hemen iptal ederse, sunucu iptali fark etmeden işlemeye devam ediyorsa, az sayıda istekle sunucuyu boğabilir.

**Tespit/savunma**: Sunucu tarafı metriklerinde "iptal edilmiş ama tamamlanan" (cancelled-but-completed) RPC oranını izleyin; yüksekse context iptalini dinlemeyen handler'lar var demektir. Kod seviyesinde, uzun işlemlerde context kontrolünü bir kod inceleme kuralı haline getirin.

---

## 5. gRPC'ye Özgü Güvenlik Modeli

### mTLS'in Neredeyse Zorunlu Olmasının Nedeni

REST/JSON API'lerde tek yönlü TLS + token tabanlı auth yaygın kabul edilebilir bir modeldir çünkü istemci genelde bir tarayıcı veya kullanıcı uygulamasıdır. gRPC'nin en yaygın kullanım alanı ise **servisler arası (service-to-service)** iletişimdir — mikroservis mimarilerinde her servis hem istemci hem sunucu rolü oynar. Bu ortamda "hangi servis benimle konuşuyor" sorusunun cevabı token'dan daha güçlü bir kimlik doğrulamasına ihtiyaç duyar: **mutual TLS (mTLS)**, hem sunucunun hem istemcinin sertifika sunduğu, her iki tarafın da kriptografik olarak doğrulandığı bir model sağlar. Servis mesh'leri (Istio, Linkerd gibi) gRPC ile bu kadar sık birlikte anılır çünkü mTLS'i otomatik olarak enjekte edip sertifika rotasyonunu yönetirler — elle mTLS yönetimi operasyonel bir kâbustur (sertifika süresi dolumu, rotasyon, dağıtım).

**Kök neden özeti**: gRPC'nin tipik dağıtım topolojisi (dahili ağ, çok sayıda servis, yüksek çağrı hacmi, her çağrının potansiyel olarak hassas iç veriye erişimi) tek başına ağ sınırı güvenliğine (perimeter security) güvenmeyi riskli kılar — "sıfır güven" (zero trust) yaklaşımı burada mTLS ile pratik hale gelir: her bağlantı, ağ konumundan bağımsız olarak kimlik doğrulanır.

**Yaygın hata**: mTLS'i sadece dış sınırda (ingress) uygulayıp dahili servisler arası trafiği düz TCP/TLS-olmadan bırakmak — "zaten dahili ağdayız, güvenli" varsayımı, bir saldırganın ağın herhangi bir noktasına (ele geçirilmiş bir pod, yanlış yapılandırılmış bir güvenlik grubu) sızması durumunda tüm dahili trafiği düz metin gibi dinlemesine izin verir (lateral movement sonrası kolay hedef).

### Reflection API: Kullanışlı Ama İfşa Riski Taşıyan Özellik

gRPC Server Reflection, bir istemcinin `.proto` dosyalarına önceden erişimi olmadan, çalışma zamanında sunucuya "hangi servisleri, hangi metodları, hangi mesaj şemalarını sunuyorsun" diye sorabilmesini sağlar. `grpcurl` gibi araçlar bunu, tıpkı bir REST API'de Swagger/OpenAPI şemasını keşfetmek gibi kullanır — geliştirme ve hata ayıklamada son derece kullanışlıdır.

**Kök neden — neden risk**: Reflection açıkken, sunucu tüm servis yüzeyini (metod isimleri, alan isimleri, hatta bazen iç veri modelini ima eden alan adlandırmaları — `internal_debug_dump`, `admin_override_flag` gibi) parola veya özel bir yetki gerekmeden ifşa eder. Bu, saldırgana **API keşif** aşamasını neredeyse ücretsiz verir: normalde "kara kutu" olan bir servisin tüm metod imzalarını çıkarıp saldırı yüzeyini haritalayabilir. Bu tek başına bir açık değildir ama "savunma derinliği" (defense in depth) ilkesini zayıflatır — saldırgana gereksiz bilgi verir.

**En iyi pratik**: Reflection'ı sadece geliştirme/staging ortamlarında açık tutun; üretimde (özellikle dış dünyaya açık uç noktalarda) kapatın veya en azından ayrı bir yetkilendirme katmanının arkasına koyun. Dahili mesh içinde bile, "gerekli olduğu kadar erişim" (least privilege) ilkesiyle sınırlı tutulması tercih edilir.

### Protobuf Deserialization Riskleri

Protobuf, JSON'a göre daha katı bir şema tanımına sahip olduğu için deserialization saldırıları (örneğin Java'nın nesne serileştirmesinde görülen gadget chain istismarları) klasik anlamda daha az yaygındır — Protobuf, keyfi kod çalıştırmaya izin veren generic nesne grafiği deserialize etmez, alanları şemaya göre ayrıştırır. Ancak risk sıfır değildir:

- **Kaynak tüketimi (resource exhaustion)**: Şema izin veriyorsa, çok derin iç içe mesajlar (deeply nested messages) veya çok büyük `repeated` alanlar, ayrıştırıcıyı aşırı CPU/bellek harcamaya zorlayabilir — bir tür algoritmik karmaşıklık saldırısı. Bu yüzden mesaj boyutu sınırları (`max receive message size`) ve makul iç içe geçme derinliği sınırları önemlidir; birçok gRPC implementasyonu varsayılan bir mesaj boyutu sınırı koyar, bunu sınırsız yapmak bir anti-pattern'dir.
- **Bilinmeyen alanlar (unknown fields)**: Protobuf'un ileri/geri uyumluluk tasarımı gereği, tanımadığı alanları sessizce saklar/yok sayar. Bu davranış kendi başına tehlikeli değildir ama şema evrimini dikkatsiz yönetirseniz (örneğin bir alanı "kaldırdım" sanıp aslında hâlâ eski istemcilerden geliyor olması), güvenlik açısından hassas bir alanın beklenmedik şekilde yeniden yorumlanmasına (field number yeniden kullanımı) yol açabilir — bu yüzden **field number'ları asla yeniden kullanmayın**, bu Protobuf şema tasarımının temel bir kuralıdır.
- **Şema güveni**: Protobuf'un kendisi mesajın *içeriğinin* iş mantığı açısından geçerli olduğunu doğrulamaz — sadece tip/şekil uyumunu sağlar. Yani "geçerli bir protobuf mesajı" almak, "güvenli/beklenen bir girdi" almakla eş değildir; uygulama seviyesinde girdi doğrulaması (input validation) hâlâ gereklidir, tıpkı JSON'da olduğu gibi.

**Savunma özet**: Mesaj boyutu ve derinlik sınırlarını açıkça yapılandırın, reflection'ı üretimde kısıtlayın, field number yeniden kullanımından kaçının, ve protobuf şemasının geçerliliğini iş mantığı doğrulamasının yerine koymayın.

---

## 6. Toparlama: Uçtan Uca Zihin Modeli

gRPC'yi anlamanın en sağlam yolu, katmanları tek tek düşünmektir:

1. **Taşıma katmanı (HTTP/2)**: Multiplexing, framing (HEADERS/DATA/RST_STREAM/GOAWAY/WINDOW_UPDATE), flow control — performans sorunlarının çoğu burada gizlidir.
2. **RPC semantiği (streaming türleri)**: unary/server/client/bidi, hepsi aynı stream soyutlamasının farklı mesaj örüntüleridir; half-close kavramı bidi'nin gücünü açıklar.
3. **Uygulama katmanı (interceptor)**: Middleware zinciri, doğru sırayla (recover → auth → tracing → iş mantığı) kurulmalı; context'in doğru aktarılması kritik.
4. **Yaşam döngüsü kontrolü (deadline/cancellation)**: Context propagation zinciri kırılmamalı; sunucu tarafı iptal sinyalini aktif dinlemeli — aksi halde hem kaynak israfı hem DoS yüzeyi oluşur.
5. **Güvenlik**: mTLS servis kimliğini ağ konumundan bağımsız doğrular; reflection kullanışlı ama ifşa riski taşır; protobuf deserialization JSON'a göre daha güvenli ama girdi doğrulamasının yerini tutmaz.

Bu beş katmanı ayrı ayrı ama birbirine bağlı düşünebilen bir mühendis, hem "neden yavaş" hem "neden güvensiz" sorularına ezbersiz, mekanizmadan giden cevaplar verebilir.
