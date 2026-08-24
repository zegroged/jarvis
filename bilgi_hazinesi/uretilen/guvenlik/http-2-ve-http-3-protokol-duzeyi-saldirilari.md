# HTTP/2 ve HTTP/3 (QUIC) Protokol Düzeyi Saldırıları

## Giriş: Neden Ayrı Bir Konu?

Request Smuggling literatürü büyük ölçüde HTTP/1.1'in metin tabanlı, sınır belirsizliğine dayalı doğasına odaklanır (Content-Length/Transfer-Encoding çatışması gibi). Ancak HTTP/2 ve HTTP/3, isteklerin sınırlarını belirlemek için tamamen farklı bir mekanizma kullanır: ikili (binary) çerçeveleme (framing) ve açık uzunluk alanları. Bu, klasik CL.TE tipi belirsizlikleri teorik olarak ortadan kaldırır. Fakat bu iki protokol, kendi mimarilerinden kaynaklanan **yepyeni** bir saldırı yüzeyi getirir:

- **Downgrade/mux karışıklığı**: Modern altyapıların çoğu HTTP/2'yi dışarıdan (istemciye) sunup arkada HTTP/1.1 ile konuşur (reverse proxy, CDN, load balancer). Bu **protokol dönüşümü sınırında** yeni smuggling türleri doğar (H2.CL, H2.TE).
- **Multiplexing**: HTTP/2 ve HTTP/3'ün temel özelliği olan "tek bağlantı üzerinden çoklu eşzamanlı stream" mimarisi, kaynak tüketimi saldırılarına (Rapid Reset) zemin hazırlar.
- **Başlık sıkıştırması (HPACK/QPACK)**: Başlıkları küçültmek için kullanılan durum bilgili (stateful) sıkıştırma algoritmaları, hem bellek tüketimi saldırılarına hem de yan kanal (side-channel) bilgi sızıntılarına açıktır.
- **QUIC/UDP temeli**: HTTP/3, TCP yerine QUIC (UDP üzerinde) kullanır; bu da bağlantı kurulumu, kimlik doğrulama ve amplifikasyon açısından bambaşka bir tehdit modeli getirir.

Bu makale bu dört eksende: kök neden, çalışma mantığı, tespit ve savunmayı ele alır.

---

## 1. HTTP/2 Temelleri: Neden Farklı Saldırı Yüzeyi Doğar

HTTP/1.1'de istekler düz metin olarak, satır sonlarıyla (CRLF) ayrılmış başlıklar ve `Content-Length` veya `Transfer-Encoding: chunked` ile belirlenen bir gövdeden oluşur. Bu format iki farklı bileşenin (örneğin ön uçtaki bir CDN ile arkadaki uygulama sunucusu) aynı baytları **farklı yorumlamasına** izin verir — smuggling'in kök nedeni budur.

HTTP/2 bunu, isteği **çerçevelere (frame)** bölerek çözer: her frame'in başında sabit uzunlukta bir başlık vardır (frame tipi, uzunluk, bayraklar, stream ID). Gövde bir `DATA` frame'i içinde taşınır ve frame'in uzunluk alanı baytları kesin olarak belirtir; belirsizlik yoktur. Başlıklar ayrı bir `HEADERS` frame'inde, HPACK ile sıkıştırılmış olarak gönderilir.

**Kök neden — asimetrik protokol desteği**: Sorun HTTP/2'nin kendisinde değil, HTTP/2'yi HTTP/1.1'e **çeviren** ara katmanlarda ortaya çıkar. Neredeyse hiçbir arka uç (origin) sunucu saf HTTP/2 konuşmaz; CDN/reverse proxy istemciyle HTTP/2 konuşur, sonra isteği HTTP/1.1'e "downgrade" ederek arka uca iletir. Bu çeviri sırasında, istemcinin gönderdiği ikili çerçeveler yeniden düz metne serileştirilir (serialize) — ve işte bu yeniden yazım adımında, klasik CL/TE belirsizlikleri **yapay olarak yeniden yaratılabilir**.

---

## 2. H2.CL ve H2.TE: HTTP/2'den HTTP/1.1'e Çeviride Smuggling

### Çalışma Mantığı

HTTP/2 isteğinde `content-length` bir başlık alanı olarak (HPACK ile kodlanmış) taşınabilir, fakat gerçek gövde uzunluğu protokol seviyesinde zaten DATA frame'lerinin toplam uzunluğuyla bellidir. Yani HTTP/2 çerçeveleme katmanı `content-length` başlığına **hiç ihtiyaç duymaz** — bu başlık sadece geriye dönük uyumluluk / uygulama katmanı için taşınan, çerçeveleme tarafından doğrulanmayan bir metaveridir.

Saldırgan bu ayrımı istismar eder:

- **H2.CL saldırısı**: İstemci, gerçek DATA frame uzunluğu ile **uyuşmayan** bir `content-length` başlığı gönderir (örneğin frame'ler 100 bayt taşırken başlıkta `content-length: 50` yazar). Ön uç bunu HTTP/2 seviyesinde kabul edip arka uca HTTP/1.1'e çevirirken `content-length: 50` başlığını kopyalar ve 100 baytlık gövdeyi olduğu gibi yazar. Arka uç sunucu `content-length: 50`'ye güvenip ilk 50 baytı bir isteğin gövdesi sayar, kalan 50 baytı ise **bir sonraki isteğin başlangıcı** olarak yorumlar. Bu, klasik CL.TE'nin ikizi ama tetikleyicisi farklı bir smuggling'dir.
- **H2.TE saldırısı**: HTTP/2 spesifikasyonu `transfer-encoding` başlığının HTTP/2 isteklerinde bulunmasını yasaklar (RFC'de açıkça belirtilir), çünkü chunked encoding kavramı HTTP/2'de anlamsızdır (frame'ler zaten kendi sınırını taşır). Fakat bazı ön uçlar bu başlığı sıkı biçimde reddetmez, sadece yok sayar ya da doğrudan arka uca iletir. Saldırgan `transfer-encoding: chunked` başlığını sızdırırsa ve arka uç HTTP/1.1 bunu **onurlandırırsa (honor)**, arka uç gövdeyi chunk sınırlarına göre parçalar — ön ucun DATA frame'inden anladığı sınırdan tamamen farklı bir noktada isteği keser. Sonuç yine istek kaçakçılığıdır.

### Neden Oluyor (Kök Neden Özeti)

Asıl problem **güven devri**: Ön uç, HTTP/2 seviyesinde geçerli bir isteği kabul ediyor, ama onu HTTP/1.1'e çevirirken uygulama-katmanı başlıklarını (content-length, transfer-encoding) **çerçeveleme gerçeğiyle çapraz doğrulamadan** kopyalıyor. Çerçeveleme (gerçek uzunluk) ile metaveri (beyan edilen uzunluk) arasında tutarlılık kontrolü yapılmaması kök nedendir.

### Tespit

- Ön uç günlüklerinde (access log) tek bir istemci bağlantısından beklenmedik sayıda arka uç isteği türemesi (bir isteğin ikiye bölünmesi izleri).
- WAF/ön uç loglarında `content-length` uyuşmazlığı uyarıları; ör. "declared length != frame length" tarzı iç metrikler (varsa).
- Anormal biçimde bir kullanıcının isteğine başka bir kullanıcının yanıtının karışması (response confusion) — özellikle paylaşımlı bağlantı havuzları (connection pooling / keep-alive reuse) olan mimarilerde.
- Pasif ağ analizinde (PCAP), istemciden gelen HTTP/2 DATA frame toplam boyutu ile aynı isteğin `content-length` başlığının farklı olması.

### Savunma

- **HTTP/2'den HTTP/1.1'e çeviri yapan her ürün için**: `transfer-encoding` başlığı HTTP/2 isteğinde asla kabul edilmemeli, görülürse istek reddedilmeli (RFC gereği zaten yasak).
- **content-length tutarlılık kontrolü**: Çeviri katmanı, beyan edilen `content-length` ile gerçek DATA frame toplamının **birebir eşleştiğini** doğrulamalı; uyuşmazlıkta isteği düşürmeli.
- Mümkünse arka uca da **HTTP/2 ile (end-to-end)** bağlanmak — böylece çeviri adımı tamamen ortadan kalkar (en sağlam çözüm).
- Ön uç ile arka uç arasında **bağlantı başına tek istek** (isteği yeniden kullanmama) politikası, smuggling'in etkisini (başka kullanıcının isteğine karışma) azaltır — performans maliyeti karşılığında.
- Güncel ters vekil (reverse proxy) ve CDN yazılımlarının bu sınıf saldırılara karşı yamalı sürümlerini kullanmak ve smuggling test araçlarıyla (ör. HTTP Request Smuggling tarayıcıları) düzenli otomatik test yapmak.

---

## 3. Stream Multiplexing ve Rapid Reset (CVE-2023-44487 sınıfı DoS)

### Kavram: Multiplexing Nedir, Neden Risklidir

HTTP/1.1'de her istek için ya yeni bir TCP bağlantısı açılır ya da bağlantı sırayla (head-of-line blocking ile) paylaşılır. HTTP/2 bunun yerine **tek TCP bağlantısı üzerinde onlarca/yüzlerce stream'i eşzamanlı çoklar (multiplex)**. Her stream bağımsız bir istek/yanıt çiftini temsil eder ve istemci, bir stream'i istediği an `RST_STREAM` frame'i göndererek **iptal edebilir**.

Bu iptal mekanizması meşru bir özelliktir (örneğin kullanıcı sayfadan ayrılınca gereksiz istekleri durdurmak için). Sorun şudur: **stream açmak ucuzdur, sunucu tarafında isteği işlemeye başlamak (routing, backend'e iletme, thread/worker tahsisi) pahalıdır.**

### Çalışma Mantığı (Rapid Reset)

Saldırgan tek bir TCP bağlantısı üzerinden:

1. Çok sayıda yeni stream açar (`HEADERS` frame'i ile istek başlatır),
2. Sunucu isteği işlemeye başlar başlamaz (backend'e yönlendirme, kaynak tahsisi vb.),
3. İstemci hemen `RST_STREAM` göndererek stream'i **iptal eder**,
4. Aynı bağlantı üzerinde HTTP/2'nin izin verdiği "eşzamanlı açık stream" limiti hemen boşaldığı için saldırgan **anında yeni stream açabilir** ve döngü çok yüksek hızda tekrarlanır.

Sonuç: Saldırgan, göreceli olarak az sayıda TCP bağlantısı ve düşük bant genişliğiyle, sunucu tarafında **çok yüksek sayıda "iste-başlat-iptal-et" döngüsü** tetikler. Sunucunun her döngüde harcadığı iş (backend bağlantısı açma, log yazma, kimlik doğrulama, kaynak tahsisi) saldırganın harcadığı işten çok daha pahalıdır — bu bir **asimetrik iş yükü (amplifikasyon) DoS'udur**, bant genişliği değil **hesaplama/kaynak** tüketimine dayanır.

Bu, 2023 sonlarında büyük ölçekte gözlemlenen ve endüstri genelinde (birden fazla büyük sağlayıcıyı etkileyen) bir HTTP/2 protokol seviyesi DoS sınıfı olarak duyurulmuştur; kesin CVE numarasını burada tek tek doğru hatırlayamayacağım detaylara girmeden, kavram olarak "Rapid Reset" adıyla anılan bu tekniğin temel mantığı yukarıdaki gibidir.

### Kök Neden

- HTTP/2 spesifikasyonu, "eşzamanlı açık stream sayısı" limitini (`SETTINGS_MAX_CONCURRENT_STREAMS`) sunucuya bildirir, ama bu limit **sadece o an açık olan stream'leri** sayar. İptal edilen stream anında sayaçtan düşer.
- Sunucu implementasyonlarının çoğu, "isteği işlemeye başlama maliyeti" ile "stream açma/kapama maliyeti"ni **aynı hız sınırlama (rate limiting) politikasına tabi tutmamıştır** — stream sayısı sınırlanmış olsa da, saniyedeki **oluşturma+iptal oranı** çoğu zaman sınırlanmamıştır.

### Tespit

- Tek bir bağlantı üzerinde anormal derecede yüksek `HEADERS` + `RST_STREAM` çifti oranı (saniyede yüzlerce/binlerce).
- Backend'e yönlendirilen ama hiç yanıt tamamlanmadan iptal edilen isteklerin oranında ani artış.
- Bağlantı sayısı görece düşükken CPU/worker tüketiminde ölçeksiz artış (klasik hacimsel DDoS imzasına uymayan bir DoS deseni — az trafik, çok kaynak tüketimi).
- HTTP/2 sunucu/proxy düzeyi metriklerinde (varsa) stream açma oranı, iptal oranı ve stream ömrü dağılımı izlenmeli.

### Savunma

- Bağlantı başına **stream oluşturma hızını** (yeni stream/saniye), sadece eşzamanlı açık stream sayısını değil, sınırlamak.
- Bir bağlantıda ardışık belirli sayıda hızlı iptal (RST) tespit edilirse bağlantıyı tamamen kapatmak (istemciyi "kötü davranışlı" sayıp cezalandırmak).
- İsteği backend'e iletmeden önceki adımların (auth, log, routing) maliyetini mümkün olduğunca **stream açılışından sonraya değil, gerçekten işlenmeye başladığı ana** ertelemek; erken iptal edilen stream'ler için pahalı işi hiç yapmamak.
- Sunucu/proxy yazılımını (web sunucusu, ters vekil, HTTP/2 kütüphanesi) bu sınıf saldırıya karşı yamalı sürümde tutmak — bu, endüstri çapında yama gerektiren bir konu olmuştur.
- Genel DDoS azaltma katmanları (oran sınırlama, davranışsal anomali tespiti) HTTP/2 stream düzeyinde de görünürlük sağlamalı; sadece IP/istek hacmine bakan klasik korumalar bu deseni kaçırabilir.

---

## 4. HPACK / QPACK: Başlık Sıkıştırma Saldırıları

### Kavram

HTTP/2, tekrar eden başlıkları (User-Agent, Cookie, çok sayıda özel başlık vb.) her istekte yeniden göndermemek için **HPACK** adlı durum bilgili bir sıkıştırma protokolü kullanır. HTTP/3 ise HPACK'in stream sıralaması gerektirme sorununu (head-of-line blocking, aşağıda değinilecek) çözmek için **QPACK**'i kullanır. Her iki mekanizma da bir **dinamik tablo (dynamic table)**: bağlantı boyunca daha önce görülen başlık adı/değer çiftlerini saklayan, indeks numarasıyla referans verilebilen bir önbellek tutar.

### Kök Neden ve Risk Sınıfları

**a) Bellek tüketimi / DoS**: Dinamik tablo bağlantı başına durum tutar. Saldırgan, çok sayıda benzersiz, büyük başlık değeri göndererek (veya çok sayıda paralel bağlantı/stream açarak) sunucunun HPACK/QPACK dinamik tablo belleğini şişirebilir. Buna ek olarak, "HPACK Bomb" tipi teknikler; küçük bir sıkıştırılmış girdinin, dinamik tablo referanslarının zincirlenmesiyle **çok büyük bir açılmış (decompressed) çıktıya** genişlemesini hedefler — klasik "zip bomb" mantığının başlık sıkıştırmasına uyarlanmış hâli. Sunucu her isteği açarken orantısız CPU/bellek harcar.

**b) Yan kanal (side-channel) sızıntısı — CRIME/BREACH ailesi mantığı**: HPACK/QPACK sıkıştırması, tekrar eden verinin daha kısa kodlanması ilkesine dayanır. Eğer saldırgan (örneğin kötücül bir JavaScript aracılığıyla tarayıcıda çalışan kod) sıkıştırılmış çıktının **boyutunu gözlemleyebiliyorsa** ve aynı bağlantıda gizli bir değer (ör. bir CSRF token veya session bilgisi içeren başlık/çerez) tekrar sıkıştırılan veriyle **birlikte** yer alıyorsa, saldırgan kendi kontrolündeki veriyi değiştirerek (deneme-yanılma) sıkıştırılmış çıktı boyutundaki değişimi gözlemler ve **byte byte gizli değeri tahmin edebilir**. Bu, TLS sıkıştırmasına karşı bilinen CRIME saldırısının kavramsal ailesindendir; HPACK/QPACK bağlamında teorik risk olarak değerlendirilir ve bu yüzden hassas verilerin sıkıştırılmış/tekrar kullanılan başlık alanlarıyla aynı bağlamda tutulmaması önerilir.

### Tespit

- Anormal derecede büyük HEADERS frame boyutları veya beklenmedik açılım (decompression) oranları (küçük giriş, dev çıkış) — sunucu tarafı HPACK/QPACK kütüphanesi bu tür oranları loglayabiliyorsa izlenmeli.
- Aynı bağlantıda alışılmadık sayıda benzersiz büyük başlık değeri (dinamik tabloyu şişirme girişimi).
- Yanıt boyutlarında, saldırganın kontrol ettiği girdiye bağlı olarak ölçülebilir, tekrarlayan küçük farklar (side-channel keşif taramasına işaret edebilir) — özellikle otomatik/çok sayıda tekrar eden istek deseni.

### Savunma

- Dinamik tablo boyutunu ve bağlantı başına toplam bellek kullanımını **sunucu tarafında sınırlamak** (protokol zaten `SETTINGS_HEADER_TABLE_SIZE` ile bir üst sınır pazarlığı sağlar; bu sınırı makul tutmak).
- Açılmış (decompressed) başlık boyutuna sunucu tarafında **sert bir üst sınır** koymak; sınır aşılırsa bağlantıyı sonlandırmak.
- Hassas, gizli değerleri (token, session id) taşıyan başlıkları, saldırganın kontrol ettiği değişken veriyle **aynı sıkıştırma bağlamında tekrar kullanılmayacak** şekilde tasarlamak; mümkünse bu tür token'ları sıkıştırılan alanlardan izole etmek veya sabit uzunlukta/rastgele dolgu ile boyut sinyalini gizlemek.
- Güncel, bilinen HPACK/QPACK bellek tüketimi zafiyetlerine karşı yamalı HTTP/2-3 kütüphaneleri kullanmak.

---

## 5. HTTP/3 ve QUIC'e Özgü Saldırı Yüzeyi

### Kavramsal Fark: Neden QUIC Yeni Bir Kategori

HTTP/3, taşıma katmanında TCP+TLS yerine **QUIC**'i (UDP üzerinde, şifrelemesi TLS 1.3 tabanlı entegre) kullanır. Bu, HTTP/2'nin "tek TCP bağlantısı üzerinde stream multiplexing" modelini korurken, **TCP'nin head-of-line blocking sorununu** taşıma katmanında da çözer: bir stream'deki paket kaybı artık diğer stream'leri bloklamaz (her stream kendi sıralama/kayıp kurtarma alanına sahiptir).

Bunun getirdiği yeni saldırı yüzeyleri:

**a) UDP tabanlı amplifikasyon / kaynak tükenmesi**: QUIC bağlantı kurulumu (handshake), TCP'nin aksine **el sıkışma öncesi (kısmen) durum tutar**. Saldırgan, sahte kaynak IP'si ile (IP spoofing) bir sunucuya bağlantı başlatma paketi gönderip sunucunun, gerçek sahibi olmayan bir kurbana büyük yanıt paketleri göndermesini sağlamaya çalışabilir — klasik UDP tabanlı amplifikasyon DDoS mantığının QUIC'e uyarlanmış hâli. QUIC tasarımı buna karşı önlemler içerir (ör. `Retry` mekanizması, adres doğrulama token'ı), fakat implementasyon hataları bu korumaları zayıflatabilir.

**b) Bağlantı durumu (connection state) tüketimi**: QUIC, TCP SYN'e benzer şekilde, tam el sıkışma tamamlanmadan sunucuda bir miktar durum ayırabilir. Çok sayıda sahte/yarım bağlantı başlatma isteği (paketleri) göndererek sunucu belleğini/CPU'sunu tüketmeye çalışmak (QUIC seviyesinde bir "SYN flood" analoğu) mümkündür.

**c) Bağlantı geçişi (connection migration) istismarı**: QUIC'in önemli bir özelliği, istemcinin IP adresi değişse bile (ör. Wi-Fi'den mobil veriye geçiş) bağlantı kimliğinin (Connection ID) korunmasıyla bağlantının **kesintisiz devam edebilmesidir**. Bu özellik, doğru doğrulanmazsa saldırgana, meşru bir bağlantı kimliğini ele geçirip **trafiği başka bir yola yönlendirme veya bağlantıyı ele geçirme (hijacking)** girişimi için bir yüzey sunabilir; bu yüzden yol doğrulama (path validation) adımlarının doğru uygulanması kritik önem taşır.

**d) 0-RTT tekrar oynatma (replay) riski**: TLS 1.3 tabanlı QUIC, önceden bilinen bir sunucuyla hızlı yeniden bağlanma için 0-RTT veri gönderimine izin verir — istemci, tam el sıkışma tamamlanmadan ilk veriyi (isteği) gönderebilir. Bu performans kazanımı, 0-RTT'de taşınan verinin **tekrar oynatma saldırılarına (replay attack)** karşı doğası gereği daha kırılgan olması riskiyle gelir: bir saldırgan yakaladığı 0-RTT paketini tekrar göndererek, sunucu tarafında idempotent olmayan bir işlemi (ör. bir ödeme isteğini) tekrar tetikleyebilir. Bu, HTTP/3'e özgü değil TLS 1.3 0-RTT'nin genel bir bilinen sınırlamasıdır, ama HTTP/3 ile yaygınlaştığı için burada anılması gerekir.

**e) Ortadaki kutuların (middlebox) UDP/QUIC görünürlüğü**: Kurumsal güvenlik duvarları, IDS/IPS ve DPI (derin paket inceleme) araçlarının büyük bölümü TCP+TLS akışlarını analiz etmeye göre inşa edilmiştir. QUIC trafiğinin gövdesi neredeyse tamamen şifreli olduğundan (başlıklarının çoğu da şifrelenmiştir), geleneksel ağ görünürlüğü araçları QUIC/HTTP-3 trafiğini **etkili biçimde inceleyemez**. Bu bir "saldırı" değil ama önemli bir **görünürlük/savunma boşluğu**dur: kötü amaçlı trafik QUIC arkasına gizlenerek DPI tabanlı tespitten kaçabilir.

### Tespit (HTTP/3 / QUIC için)

- Kaynak IP başına anormal sayıda yarım kalan (el sıkışma tamamlanmamış) QUIC bağlantı girişimi.
- Sunucudan istemciye giden yanıt/istek paket boyutu oranının (amplifikasyon faktörü) izlenmesi; oran çok yüksekse potansiyel amplifikasyon kaynağı sayılabilir.
- Sık ve anlamsız görünen bağlantı geçişi (connection migration) olayları, özellikle aynı Connection ID'nin coğrafi olarak tutarsız kaynak IP'lerden kullanılmaya çalışılması.
- 0-RTT ile gelen isteklerin sunucu tarafında ayrıca işaretlenip idempotent olmayan işlemler için 0-RTT verisinin reddedilip edilmediğinin denetimi.
- Ağ güvenlik ekipleri için: UDP/443 (QUIC) trafiğinin toplam hacminin ve TLS/TCP trafiğine oranının izlenmesi — beklenmedik artışlar araştırılmalı.

### Savunma

- Sunucu tarafı QUIC implementasyonunun adres doğrulama (address validation / Retry mekanizması) özelliğini etkinleştirmek; el sıkışma tamamlanmadan büyük yanıt göndermemek (amplifikasyonu sınırlamak için yanıt/istek boyut oranına protokol seviyesinde sınır konmuştur, bunun doğru uygulandığından emin olmak).
- Bağlantı geçişinde yeni yolun (path) meşruluğunu doğrulamadan (path validation) tam güvenmemek.
- 0-RTT'yi sadece **idempotent** (tekrar çalıştırılması güvenli) işlemler için kabul etmek; durum değiştiren (state-changing) işlemleri 0-RTT üzerinden asla işlememek — bu, uygulama seviyesinde açıkça kodlanması gereken bir kontroldür.
- Kurumsal ağlarda, QUIC'in DPI görünürlüğünü kısıtlaması nedeniyle, gerekliyse (politika gereği) QUIC/UDP-443'ü kenar noktalarda engelleyip istemcilerin HTTP/2 (TCP) üzerine düşmesini (fallback) sağlamak — bu bir trade-off'tur (performans kaybı karşılığında görünürlük kazanımı) ve her ortam için doğru cevap değildir.
- Sunucu ve CDN sağlayıcılarının QUIC implementasyonlarını güncel tutmak; bu görece genç bir protokol olduğundan olgunlaşmamış kod tabanlarında implementasyon hataları daha sık görülebilir.

---

## 6. Yaygın Hatalar (Savunma Tarafında)

1. **"HTTP/2 ikili, o yüzden smuggling imkansız" varsayımı**: Yanlıştır — asıl risk HTTP/2-den-HTTP/1.1'e çeviri sınırındadır, protokolün kendisinde değil.
2. **Stream/bağlantı limitlerini sadece "eşzamanlı açık sayı" olarak düşünmek**: Rapid Reset, oluşturma+iptal **hızını** sınırlamadığı sürece eşzamanlı sayı limitinin işe yaramadığını gösterir.
3. **HPACK/QPACK dinamik tablosuna sınırsız güvenmek**: Varsayılan kütüphane ayarlarının üretim ortamı için yeterince sıkı olduğunu varsaymak; boyut sınırlarını gözden geçirmemek.
4. **QUIC'i "TCP gibi davranır" varsayarak eski DDoS/IDS kurallarını aynen taşımak**: UDP tabanlı olması, bağlantı geçişi ve şifreli başlıklar nedeniyle TCP'ye özgü tespit mantığı QUIC'te doğrudan işlemez.
5. **0-RTT'yi performans için açıp replay riskini uygulama katmanında ele almamak**: Bu sorumluluk protokol tarafından değil, uygulama geliştiricisi tarafından yönetilmelidir.
6. **Arka uca hâlâ HTTP/1.1 ile bağlanan altyapıyı "geçici çözüm" diye süresiz sürdürmek**: En kalıcı çözüm uçtan uca HTTP/2 (ya da HTTP/3) olsa da, çoğu kurum eski arka uçlar nedeniyle çeviri katmanını yıllarca korur — bu katmanın güvenlik testine tabi tutulmadan üretimde kalması asıl risktir.

---

## Sonuç

HTTP/2 ve HTTP/3, HTTP/1.1'in belirsizlik kaynaklı sorunlarını (smuggling'in klasik kökeni) çözmek için tasarlanmış olsa da, kendi mimari yenilikleri (çerçeveleme/çeviri sınırı, multiplexing, durum bilgili başlık sıkıştırma, UDP tabanlı taşıma) yeni ve farklı bir tehdit yüzeyi doğurur. Savunma stratejisi üç eksende özetlenebilir: (1) protokol çevirisi yapan her bileşende tutarlılık doğrulaması yapmak, (2) kaynak tüketimini sadece statik limitlerle değil **davranışsal oran ve desen** analiziyle sınırlamak, (3) yeni protokolün (özellikle QUIC'in) getirdiği görünürlük ve durum yönetimi farklarını mevcut güvenlik araçlarına ve mimarisine bilinçli biçimde entegre etmek. Bu alanın hâlâ hızla geliştiğini ve sunucu/kütüphane implementasyonlarının olgunlaştıkça yeni zafiyet sınıflarının ortaya çıkabileceğini akılda tutmak gerekir.
