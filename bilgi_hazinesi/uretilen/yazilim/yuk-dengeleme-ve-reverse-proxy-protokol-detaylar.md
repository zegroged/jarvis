# Yük Dengeleme ve Reverse Proxy Protokol Detayları

Bu makale, yük dengeleme (load balancing) ve reverse proxy konusunu genel geliştirici bakış açısının bir adım altına inerek ele alır: paket ve bağlantı seviyesinde ne olup bittiği, L4 ile L7 arasındaki gerçek farkın nereden doğduğu, PROXY protocol'ün neden var olduğu ve HTTP bağlantı yeniden kullanımının (connection reuse) neden en tehlikeli sınıf zafiyetlerden biri olan request smuggling'in kök nedeni olduğu. Amaç mekanizmayı anlamak ve savunma/tespit kurabilmektir.

## Temel Kavramlar: Reverse Proxy ve Load Balancer

Bir **reverse proxy**, istemci (client) ile bir veya birden fazla arka uç sunucu (backend/upstream) arasında duran ve istemci adına isteği alıp arka uca ileten bir aracıdır. İstemci genellikle arka ucun varlığından habersizdir; onun için "sunucu" proxy'nin kendisidir.

Bir **load balancer** (yük dengeleyici), aynı işi yaparken gelen istekleri birden fazla arka uç arasında bir algoritmaya göre (round-robin, least-connections, hash-based vb.) dağıtan bir reverse proxy'nin özelleşmiş halidir. Pratikte HAProxy, NGINX, Envoy, AWS ALB/NLB gibi ürünler her iki rolü de üstlenir.

Kritik ayrım şudur: bu aracı **hangi OSI katmanında** karar veriyor? İşte L4 ve L7 farkı buradan doğar.

## L4 (Transport Katmanı) Yük Dengeleme

### Tanım ve çalışma mantığı

L4 load balancer, TCP/UDP seviyesinde çalışır. Kararlarını IP adresleri ve port numaraları üzerinden verir; **taşınan uygulama verisinin (HTTP başlıkları, gövde vb.) içeriğine bakmaz**. Yani bir L4 dengeleyici için akan şey sadece bir byte akışıdır (stream); onu HTTP olarak yorumlamaz.

L4'ün iki temel çalışma modeli vardır:

**1. NAT/proxy modu (connection terminating):** Load balancer istemciyle bir TCP bağlantısı, arka uçla ayrı bir TCP bağlantısı kurar ve byte'ları iki taraf arasında kopyalar. İstemcinin gördüğü kaynak, load balancer'ın IP'sidir. Arka ucun gördüğü kaynak da genellikle load balancer'ın IP'sidir. Bu yüzden gerçek istemci IP'si arka uçta kaybolur; PROXY protocol'ün doğuş nedeni tam da budur (aşağıda).

**2. DSR (Direct Server Return) / L4 yönlendirme:** Dengeleyici gelen paketin hedef MAC/IP'sini değiştirip arka uca yönlendirir, arka uç cevabı doğrudan istemciye döner. Cevap trafiği dengeleyiciden geçmez. Çok yüksek throughput sağlar ama kurulumu ve gözlemlenebilirliği zordur.

### Neden hızlıdır

L4 dengeleyici TLS'i çözmez (terminate etmez), HTTP'i parse etmez, tampon (buffer) yönetimi minimumdur. Bir bağlantı kurulduktan sonra çoğu iş çekirdek (kernel) seviyesinde, hatta bazı sistemlerde ağ kartına yakın katmanda yapılabilir. Bu yüzden L4 milyonlarca eşzamanlı bağlantı ve çok düşük gecikme (latency) ölçeklerinde tercih edilir.

### L4'ün yapamadıkları

L4 içeriğe bakmadığı için:

- URL path'e (`/api` vs `/static`) göre yönlendirme yapamaz.
- HTTP header'a (`Host`, `Cookie`) göre kural işletemez.
- TLS terminasyonu yoksa, sertifika yönetimi ve HTTP-seviyesi güvenlik (WAF) yapamaz.
- Aynı TCP bağlantısı içindeki farklı HTTP isteklerini ayrı ayrı ele alamaz; bağlantı bir bütündür.

Bir istisna: **SNI (Server Name Indication) tabanlı yönlendirme.** TLS ClientHello içindeki SNI alanı şifrelenmeden gönderildiği için, L4 dengeleyici TLS'i çözmeden bile SNI'ye bakıp "bu bağlantı hangi backend'e gitmeli" kararı verebilir. Bu, teknik olarak L4 üzerinde uygulama-farkındalıklı bir yönlendirme örneğidir ve pass-through TLS mimarilerinde çok kullanılır.

## L7 (Uygulama Katmanı) Yük Dengeleme

### Tanım ve çalışma mantığı

L7 load balancer HTTP (veya gRPC, WebSocket vb.) seviyesinde çalışır. İstemciyle olan TLS'i **terminate eder**, gelen byte akışını **tam bir HTTP mesajı olarak parse eder**, header'ları ve gerekirse gövdeyi okur, karar verir ve arka uca **yeni bir HTTP isteği** olarak iletir.

Buradaki en önemli kavramsal nokta: L7 proxy, tek bir uçtan uca bağlantı değildir. **İki ayrı HTTP "konuşması" vardır**: istemci↔proxy ve proxy↔backend. Proxy, bir mesajı bir taraftan okuyup diğer tarafa yeniden yazar (re-serialize eder). İşte request smuggling zafiyetlerinin tamamı bu "iki taraf bir mesajın nerede bittiği konusunda anlaşamazsa ne olur" sorusundan doğar.

### L7'nin sağladıkları

- Path/host/header/cookie tabanlı yönlendirme.
- Header ekleme/çıkarma (`X-Forwarded-For`, `X-Request-ID`).
- TLS terminasyonu ve merkezî sertifika yönetimi.
- Retry, circuit breaking, rate limiting, WAF entegrasyonu.
- Bağlantı yeniden kullanımı (connection pooling) ile arka uca daha az sayıda TCP bağlantısı açma.

### Bedeli

Her isteği parse etmek, buffer'lamak, yeniden serileştirmek CPU ve bellek maliyeti getirir. L7 dengeleyici, L4'e göre bağlantı başına daha ağırdır. Bunun karşılığında görünürlük ve kontrol kazanılır.

### L4 mi L7 mi? Pratik karar

- Ham TCP/UDP, veritabanı bağlantıları, çok yüksek throughput, protokolden bağımsızlık gerekiyorsa: **L4**.
- İçerik tabanlı yönlendirme, TLS terminasyonu, HTTP-seviyesi güvenlik ve gözlem gerekiyorsa: **L7**.
- Gerçek dünyada sık görülen: dışta L4 (ör. AWS NLB) + içte L7 (ör. Envoy/NGINX) katmanlı mimarisi. Bu katmanlama gerçek istemci IP'sini ve HTTP semantiğini bozmadan taşıma sorununu ortaya çıkarır.

## PROXY Protocol: Gerçek İstemci Bilgisini Taşımak

### Kök neden

L4 proxy modunda, arka uç TCP bağlantısını load balancer'dan gelen bir bağlantı olarak görür. Arka ucun `getpeername()` çağrısı ona load balancer'ın IP'sini döner, gerçek istemcinin IP'sini değil. L7'de bu sorun `X-Forwarded-For` gibi bir HTTP header'ı eklenerek çözülür — ama L4 içeriğe dokunmadığı için HTTP header ekleyemez. TCP akışına HTTP header enjekte etmek zaten protokol katmanı ihlali olurdu.

Çözüm: **PROXY protocol** (HAProxy tarafından tanımlanmıştır). Fikir basittir: proxy, arka uca kurduğu TCP bağlantısının **en başına**, uygulama verisi başlamadan önce, tek seferlik küçük bir metadata bloğu yazar. Bu blok gerçek kaynak IP'yi, kaynak portu, hedef IP'yi ve portu taşır.

### İki versiyon

- **v1 (metin tabanlı):** İnsan tarafından okunabilir tek satır, örneğin `PROXY TCP4 <kaynak-ip> <hedef-ip> <kaynak-port> <hedef-port>\r\n` biçiminde. Debug için okunması kolaydır.
- **v2 (binary):** Sabit bir imza (signature) baytları ile başlayan, ayrıştırması makine için daha verimli ve belirsizliğe daha kapalı olan binary format. TLV (type-length-value) alanları ile ek metadata (ör. TLS bilgisi) taşıyabilir.

Arka uç sunucu (veya içteki L7 proxy) bu başlığı okuyup ayrıştıracak şekilde **açıkça yapılandırılmış olmalıdır**. Aksi halde bu baytları ilk HTTP isteğinin parçası sanar ve istek bozulur.

### Kritik güvenlik tuzağı: PROXY header spoofing

PROXY protocol başlığı, veriyi gönderen taraftan gelen ve arka ucun **koşulsuz güvendiği** bir kaynak-IP iddiasıdır. Eğer arka uç sunucu, herhangi bir istemciden gelen bağlantıda PROXY başlığını kabul edecek şekilde yapılandırılırsa, saldırgan doğrudan arka uca bağlanıp sahte bir PROXY başlığı göndererek **istediği IP'den geliyormuş gibi** görünebilir. Bu, IP tabanlı erişim kontrollerini (allowlist), rate limiting'i ve loglamayı tamamen atlatır.

Savunma:

- Arka uç, PROXY başlığını **yalnızca güvenilen proxy'lerin IP'lerinden** kabul etmelidir (kaynak IP allowlist).
- Arka uç ağ katmanında yalıtılmalı; internete doğrudan açık olmamalı, sadece load balancer erişebilmeli.
- PROXY protocol'ü "kabul et" ayarı ile "her kaynaktan kabul et" ayarı karıştırılmamalı; birçok ürün bu ayrımı ayrı seçenek olarak sunar.

### Yaygın hatalar

- **Tek taraf açık, diğer taraf kapalı:** Proxy PROXY başlığı gönderiyor ama arka uç beklemiyor → her istek bozuk. Ya da tersi: arka uç bekliyor ama proxy göndermiyor → arka uç ilk baytları başlık sanıp bağlantıyı düşürür.
- **TLS ile katman karışıklığı:** PROXY başlığı, TLS handshake'ten **önce** mi sonra mı geliyor? Ürün ve mod'a göre değişir; yanlış sıra bağlantı sıfırlanmasına yol açar.
- **Health check'lerin başlıksız gelmesi:** Load balancer'ın sağlık kontrolleri PROXY başlığı göndermeyebilir; arka uç başlığı zorunlu tutarsa health check'ler başarısız olur.

## HTTP Keep-Alive ve Connection Reuse: Verim ve Tehlike

### Keep-alive nedir, neden var

HTTP/1.0'da her istek için yeni bir TCP bağlantısı kuruluyordu. TCP handshake ve (varsa) TLS handshake pahalı olduğundan, bu ciddi bir gecikme kaynağıydı. HTTP/1.1 varsayılan olarak **persistent connection (keep-alive)** getirdi: aynı TCP bağlantısı üzerinden **peş peşe birden fazla istek/cevap** gönderilebilir. `Connection: keep-alive` ve `Connection: close` header'ları bu davranışı kontrol eder.

Bu, performans için kritiktir. Ama bir reverse proxy zincirinde iki ayrı keep-alive politikası vardır:

1. **İstemci ↔ proxy** bağlantısının reuse'u.
2. **Proxy ↔ backend** bağlantısının reuse'u.

Bu ikisi bağımsızdır. Proxy, arka uca açtığı bağlantıları bir **connection pool**'da tutup **farklı istemcilerin isteklerini aynı arka uç bağlantısında** taşıyabilir. Verim için harika; güvenlik için tehlikeli sınıra buradan girilir.

### Bir HTTP isteği tam olarak nerede biter?

Persistent bağlantıda kritik soru şudur: bir mesajın gövdesi nerede bitiyor ki bir sonraki mesaj nerede başlıyor bilinsin? HTTP/1.1'de bunu belirleyen iki mekanizma var:

- **`Content-Length`:** Gövdenin tam byte sayısını verir.
- **`Transfer-Encoding: chunked`:** Gövde, her biri kendi uzunluğunu belirten "chunk"lar halinde gelir; sıfır uzunluklu chunk sonu işaretler.

Spesifikasyon der ki: ikisi birden varsa, `Transfer-Encoding` `Content-Length`'i geçersiz kılar. Sorun şu: **zincirdeki iki ayrı sunucu (front-end proxy ve back-end) bu kuralı aynı yorumlamazsa** ne olur?

## Request Smuggling: Connection Reuse Mismatch'in Kök Nedeni

### Kök neden (kavramsal)

HTTP Request Smuggling, **aynı arka uç bağlantısında** ard arda taşınan istekler arasında, ön uç (front-end) proxy ile arka uç (back-end) sunucunun **bir isteğin nerede bittiği konusunda anlaşamamasından** doğar. Ön uç isteği bir yerde bitiriyor sanar, arka uç başka bir yerde. Aradaki fark, arka uç tarafından **bir sonraki isteğin başı** olarak yorumlanır. Saldırgan bu "artık" (leftover) baytları önceden yerleştirirse, o baytlar **pool'daki bir sonraki kurbanın isteğinin önüne yapışır**.

Bu yüzden request smuggling'in kök nedeni tek cümleyle: **connection reuse + mesaj sınırı belirsizliği (ambiguity)**. Bağlantı yeniden kullanılmasaydı ("her istek yeni bağlantı"), artık baytların bir sonraki kurbana bulaşması mümkün olmazdı — bu da bazı azaltma stratejilerinin neden reuse'u kapatmak olduğunu açıklar.

### Klasik belirsizlik biçimleri (kavramsal)

- **CL.TE:** Ön uç `Content-Length`'e göre, arka uç `Transfer-Encoding: chunked`'a göre ayrıştırır. Uzunluk hesapları farklı bittiğinden artık bayt oluşur.
- **TE.CL:** Tersi. Ön uç chunked'a, arka uç Content-Length'e bakar.
- **TE.TE:** İki taraf da chunked destekler ama biri, örneğin bozuk/gizlenmiş (obfuscated) bir `Transfer-Encoding` header'ını farklı ele alır; biri onu geçerli sayar, diğeri yok sayar.

Ortak payda hep aynıdır: **iki uygulama, aynı byte dizisini farklı mesaj sınırlarına böler.**

### HTTP/2 ve downgrade

Modern varyantlarda risk, HTTP/2'nin arka uca **HTTP/1.1'e downgrade** edilerek iletilmesinde ortaya çıkar. HTTP/2 mesaj uzunluğunu netçe (frame'lerle) belirtir; ama proxy bunu HTTP/1.1'e çevirirken `Content-Length`/`Transfer-Encoding` üretir ve bu çeviri sırasında yeniden belirsizlik doğabilir (bazen "H2.CL", "H2.TE" olarak anılır). Kök neden yine aynı: **protokoller arası çeviride mesaj sınırının yeniden yorumlanması.**

### Neden bu kadar tehlikeli

Request smuggling ile saldırgan:

- Ön uçtaki güvenlik kontrollerini (WAF, auth, path kısıtları) atlatabilir — çünkü arka uç, ön ucun hiç görmediği "gizli" bir istek görür.
- Başka bir kullanıcının isteğine kendi payload'ını enjekte edip cevabı zehirleyebilir (response queue poisoning), oturum çalabilir, önbelleği zehirleyebilir (cache poisoning).

## Savunma ve Tespit

Bu bölüm operasyonel saldırı değil, savunma odaklıdır.

### Mimari ve yapılandırma savunmaları

- **Belirsizliği reddet:** Ön ve arka uç, hem `Content-Length` hem `Transfer-Encoding` içeren, ya da çoğaltılmış/bozuk header taşıyan istekleri **normalize etme, doğrudan reddet** (`400`). Belirsiz istek geçerli bir istek değildir.
- **Aynı HTTP stack'ini tercih et:** Ön ve arka uç aynı ürün/aynı ayrıştırma davranışına sahipse, "iki taraf farklı yorumlar" durumu büyük ölçüde ortadan kalkar. Karışık zincirler (ör. bir üründen diğerine) en riskli olanlardır.
- **HTTP/2'yi uçtan uca taşı:** Mümkünse arka uca kadar HTTP/2 kullan; HTTP/1.1'e downgrade etme. Downgrade zorunluysa çevirinin sıkı doğrulama yapan bir implementasyonla yapıldığından emin ol.
- **Header normalizasyonu:** Ön uçta gelen istekleri kanonik bir biçime getirip arka uca öyle ilet; whitespace, satır sonu (CRLF) ve header çoğaltma anomalilerini temizle veya reddet.

### Connection reuse ile ilgili sertleştirme

- Arka uca giden bağlantı yeniden kullanımını kavramsal olarak anla: reuse performans getirir ama smuggling'in yayılma kanalıdır. Yüksek riskli/karışık zincirlerde arka uç bağlantı reuse'unu kısıtlamak (ör. hassas yollarda) bir azaltma seçeneğidir — bedeli performanstır.
- **Timeout uyumu:** İstemci↔proxy ve proxy↔backend keep-alive/idle timeout değerlerinin uyumsuzluğu, "bir taraf bağlantıyı kapattı sandı, diğeri hâlâ açık" durumlarına ve yarış (race) kaynaklı hatalara yol açar. Bu doğrudan smuggling değildir ama bağlantı-durumu uyumsuzluğunun bir başka yüzüdür; timeout'ları katmanlar arası tutarlı ayarlamak gerekir.

### Tespit (detection)

- **Anomali imzaları:** Aynı anda `Content-Length` ve `Transfer-Encoding` taşıyan, satır içinde beklenmedik CRLF veya ikili header barındıran, olağandışı chunked yapıları olan istekleri logla ve alarma bağla.
- **Cevap eşleşmesi izleme:** Bir kullanıcının aldığı cevabın kendi isteğiyle tutarsız olduğu durumlar (yanlış içerik, başka kullanıcının verisi) response queue poisoning belirtisidir. İstek-cevap eşleşmesini `X-Request-ID` gibi bir korelasyon kimliğiyle izlemek bunu görünür kılar.
- **Zamanlama anomalileri:** Bazı smuggling denemeleri, arka ucun "eksik" bir isteği tamamlamak için beklemesinden kaynaklı gecikme desenleri üretir. Beklenmedik latency artışları tetikleyici olabilir.
- **PROXY protocol tarafı:** Beklenmeyen kaynaklardan gelen PROXY başlıklarını, ya da başlıkta iddia edilen IP ile gerçek TCP kaynak IP'si arasındaki tutarsızlıkları (mümkünse) logla.

### Yaygın hatalar özeti

- İstemci IP'sini `X-Forwarded-For`'a **körlemesine güvenmek**: bu header istemci tarafından uydurulabilir; yalnızca güvenilen proxy'nin eklediği en dıştaki değer güvenilirdir.
- PROXY protocol'ü arka uçta **her kaynaktan** kabul etmek → IP spoofing.
- Ön ve arka ucu **farklı HTTP ayrıştırıcılarla** eşleştirip normalize etmemek → smuggling zemini.
- Belirsiz istekleri reddetmek yerine **"tolere edip düzeltmeye" çalışmak**: tolerans, iki tarafın farklı düzeltmesi demektir; bu tam da zafiyeti doğurur.
- Katmanlar arası timeout ve keep-alive ayarlarını **birbirinden habersiz** yapılandırmak.

## Özet

L4 ile L7 arasındaki fark, dengeleyicinin **hangi katmanda ve ne kadar derinden** karar verdiğidir: L4 byte akışını taşır ve hızlıdır; L7 HTTP'i anlar ve kontrol sağlar ama her mesajı yeniden yazar. Bu yeniden yazma ve **bağlantı yeniden kullanımı**, hem PROXY protocol gibi çözümlerin (gerçek IP'yi taşıma) hem de request smuggling gibi zafiyetlerin (mesaj sınırı belirsizliği) kaynağıdır. Sağlam bir mimari; katmanlar arası protokol yorumunu tutarlı tutmak, belirsiz istekleri reddetmek, güven sınırlarını (PROXY başlığını yalnızca güvenilen kaynaktan kabul etmek gibi) açıkça çizmek ve bağlantı-durumu uyumsuzluklarını gözlemleyebilmek üzerine kuruludur.
