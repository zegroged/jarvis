# QUIC Protokol İç Yapısı

## Neden Önemli

QUIC (RFC 9000, IETF tarafından standartlaştırılmıştır), HTTP/3'ün (RFC 9114) taşıma katmanı temelidir ve bugün internet trafiğinin ciddi bir yüzdesi -özellikle büyük CDN'ler, Google, Facebook/Meta ve Cloudflare arkasındaki trafik- QUIC üzerinden akmaktadır. TCP+TLS ikilisinin onlarca yıllık tasarım kısıtlarını (head-of-line blocking, bağlantı kurulum gecikmesi, ortadaki kutuların (middlebox) protokolü dondurması) çözmek için sıfırdan tasarlanmış bir taşıma protokolüdür. Bir yazılım/güvenlik mühendisi için QUIC'i anlamak artık isteğe bağlı bir "ileri seviye ağ bilgisi" değil; modern web performansı, CDN mimarisi, mobil bağlantı dayanıklılığı ve yeni nesil DoS/replay saldırı yüzeylerini anlamanın ön koşuludur. Bu makale QUIC'in iç mekanizmalarını, tasarım kararlarının "neden"ini ve savunma/tespit perspektifinden bilinmesi gerekenleri ele alır.

## QUIC Nedir, TCP'den Farkı Ne

QUIC, UDP üzerinde çalışan, kendi içinde güvenilirlik (reliability), akış kontrolü, sıra kontrolü ve şifreleme (TLS 1.3 entegre) sağlayan bir taşıma protokolüdür. "UDP üzerinde TCP inşa etmek" gibi görünse de aslında çok daha fazlasıdır: TCP + TLS + HTTP/2'nin stream multiplexing katmanının yeniden tasarlanmış, birleşik bir versiyonudur.

Kök neden sorusu şudur: TCP neden yetersiz kaldı?

1. **Middlebox ossification (donmuşluk)**: TCP, yıllar içinde NAT cihazları, güvenlik duvarları ve trafik optimize edici kutular (middlebox) tarafından o kadar sıkı varsayımlarla işlendi ki, TCP'nin kendisinde yeni bir alan/bayrak eklemek bile pratikte imkansız hale geldi. Birçok ağ cihazı, TCP başlığındaki alışılmadık bir bit kombinasyonunu görünce paketi düşürüyor. QUIC bu sorunu, taşıma katmanı meta verisinin neredeyse tamamını **şifreleyerek** çözer: middlebox'lar sadece UDP başlığını görür, QUIC'in kendi iç durumunu (connection ID hariç) göremez. Bu, protokolün gelecekte esnekçe evrilebilmesini (yeni uzantılar, yeni congestion control algoritmaları) sağlar.
2. **Head-of-line (HOL) blocking**: TCP tek bir bayt akışıdır (single byte-stream abstraction). HTTP/2 bu akış üzerine çoklu mantıksal stream'i multiplexler, ama TCP seviyesinde bir paket kaybolduğunda, TCP kayıp paketi yeniden iletene kadar **o TCP bağlantısındaki tüm stream'ler** bloke olur -bir stream'in verisi kaybolmuş olsa bile diğer stream'lerin zaten gelmiş verisi uygulamaya teslim edilemez. Buna "TCP-level HOL blocking" denir. QUIC bunu, stream'leri taşıma katmanının kendisinde birinci sınıf yapılar (first-class citizens) haline getirerek çözer: her stream bağımsız sıra numarasına ve kayıp kurtarmasına sahiptir, bir stream'in kaybı diğerlerini bloklamaz.
3. **Bağlantı kurulum gecikmesi (handshake latency)**: Klasik TCP + TLS 1.2/1.3 modeli, veri gönderebilmek için önce TCP 3 yönlü el sıkışması (1 RTT), sonra TLS el sıkışması (1-2 RTT) gerektirir. QUIC, taşıma ve şifreleme el sıkışmasını **birleştirerek** (transport handshake ile TLS handshake'i tek bir round-trip'e sıkıştırarak) bunu 1 RTT'ye, tekrar bağlantılarda ise 0-RTT'ye indirir.
4. **Connection migration (bağlantı göçü)**: TCP bir bağlantıyı 4'lü (source IP, source port, dest IP, dest port) ile tanımlar. Mobil bir cihaz Wi-Fi'den hücresel ağa geçtiğinde IP değişir, TCP bağlantısı kopar, uygulama yeniden bağlanmak zorunda kalır. QUIC bağlantıları IP/port yerine kendi ürettiği **Connection ID (CID)** ile tanımlar, böylece IP değişse bile bağlantı devam edebilir.

## Bağlantı Kurulumu: 1-RTT ve 0-RTT

### 1-RTT El Sıkışması

QUIC'in normal (ilk kez bağlanan) el sıkışması şöyle işler: İstemci, TLS ClientHello'yu QUIC transport parametreleriyle (idle timeout, max stream sayısı, initial max data gibi) birlikte tek bir UDP paketinde (Initial paket) sunucuya gönderir. Sunucu, ServerHello + sertifika + Finished mesajlarını (Handshake paketleri) döner. İstemci bunları doğrular ve kendi Finished'ini gönderir; bu noktada uygulama verisi (1-RTT anahtarlarıyla şifreli) akmaya başlayabilir. Kritik nokta: TCP'nin ayrı 3 yönlü el sıkışması + TLS'in ayrı el sıkışması yerine, ikisi **tek bir paket alışverişi zincirinde** iç içe geçirilmiştir (coalesced). Bu, RTT sayısını klasik modelin yarısına indirir.

QUIC, aynı zamanda çoklu şifreleme seviyesini (encryption level) eşzamanlı yönetir: Initial (düşük güvenlik, sadece obfuscation amaçlı sabit anahtarla şifreli), Handshake, 0-RTT (varsa) ve 1-RTT. Her seviyenin kendi paket numarası uzayı (packet number space) vardır -bu, farklı seviyelerdeki paketlerin kayıp/yeniden iletim mantığının birbirine karışmamasını sağlar.

### 0-RTT: Kazanç ve Risk

İstemci daha önce aynı sunucuya bağlanmışsa ve sunucu bir **session resumption ticket** (TLS 1.3'ün PSK/session ticket mekanizması) vermişse, istemci ilk pakette doğrudan uygulama verisini (0-RTT verisi) gönderebilir -hiç RTT beklemeden. Bu, sayfa yükleme süresini önemli ölçüde kısaltır, özellikle yüksek gecikmeli (mobil, uydu) bağlantılarda.

**Kök neden / neden riskli**: 0-RTT verisi, önceki oturumdan türetilmiş bir PSK (pre-shared key) ile şifrelenir ve bu anahtar sunucu tarafında **forward secrecy sağlamaz** (taze bir Diffie-Hellman anahtar değişimi henüz gerçekleşmemiştir). Daha kritik olarak, 0-RTT verisi **replay saldırısına karşı doğal olarak korumasızdır**: bir saldırgan, ağı dinleyerek yakaladığı ilk 0-RTT paketini tekrar tekrar sunucuya gönderebilir ve sunucu (eğer önlem almazsa) bu isteği her seferinde işler. TLS 1.3 spesifikasyonu bunu açıkça belirtir: 0-RTT verisi **idempotent olmayan** işlemler için (örneğin bir ödeme işlemi, bir "bakiyeden düş" komutu) kullanılmamalıdır.

**Savunma/tespit açısından çıkarımlar**:
- Sunucu tarafı uygulamalar, 0-RTT üzerinden gelen isteklerde yan etkisi olan (state-changing) işlemleri **reddetmeli veya idempotency key** zorunlu kılmalıdır.
- Sunucular genellikle 0-RTT anti-replay için bir **de-duplication cache** (görülen ticket/nonce'ları saklayan, sınırlı ömürlü bir yapı) tutar; bu önbelleğin boyutu ve pencere genişliği, saldırı yüzeyinin bir parçasıdır (çok küçük pencere = meşru retransmisyonları reddeder, çok büyük = bellek tüketimi saldırısına açık).
- Loglama ve izleme sistemlerinde, "0-RTT ile kabul edilen istek" ile "1-RTT ile kabul edilen istek" ayrımının yapılabilmesi önemlidir -bir güvenlik olayı incelemesinde, hangi isteklerin daha zayıf tekrar oynatma garantisiyle geldiğini bilmek olay müdahalesini kolaylaştırır.

## Stream Multiplexing ve HOL Blocking Çözümü

QUIC bağlantısı, birden fazla bağımsız **stream**'den oluşur. Her stream tek yönlü veya çift yönlü olabilir; stream ID'nin son iki biti yönü ve başlatıcıyı (istemci mi sunucu mu) kodlar. Her stream kendi akış kontrolüne (flow control), kendi sıra numarasına ve kendi kayıp kurtarma durumuna sahiptir.

**Neden bu HOL blocking'i çözer**: TCP'de tek bir sıra numarası uzayı ve tek bir yeniden iletim mekanizması olduğu için, kaybolan bir segment tüm sonraki verinin teslimini durdurur (uygulama katmanına). QUIC'te ise kayıp, sadece o stream'i etkiler; paket kaybı bir stream'in verisini geciktirirken, aynı UDP paketinde taşınmamış diğer stream'lerin verisi (farklı paketlerde gelmişse) hemen teslim edilebilir. Bu, HTTP/2'nin TCP üzerinde yaşadığı "bir kayıp tüm sayfa yüklemesini durdurur" sorununu doğrudan hedefler.

Önemli bir ayrıntı: HOL blocking **tamamen** ortadan kalkmaz, sadece stream sınırına indirgenir. Eğer bir paket, birden fazla stream'in verisini taşıyorsa (frame coalescing), o paketin kaybı yine de birden fazla stream'i etkileyebilir. Ayrıca uygulama katmanında (örneğin HTTP/3 header compression -QPACK- bağlamında), stream'ler arası bağımlılıklar hâlâ dolaylı bir HOL etkisi yaratabilir; QPACK bu nedenle HTTP/2'nin HPACK'inden farklı, stream sırasına daha az bağımlı bir tasarıma sahiptir.

**En iyi pratik / tuzak**: Uygulama geliştiricileri, kritik olmayan kaynakları (örneğin analytics, reklam) ayrı stream'lere koyarak kritik render-blocking kaynakların (CSS, ana HTML) onlardan etkilenmemesini sağlayabilir. Yaygın hata: tüm veriyi tek bir stream üzerinden göndermek -bu, QUIC'in multiplexing avantajını tamamen yok sayar ve pratikte TCP'ninkine benzer bir HOL blocking'e geri döner.

## Connection Migration ve Connection ID Mekanizması

Bir QUIC bağlantısı, IP/port 4'lüsü yerine **Connection ID (CID)** ile tanımlanır. Bağlantı kurulumunda taraflar birbirine bir dizi CID sunar (`NEW_CONNECTION_ID` frame'i ile); istemcinin ağı değişip yeni bir IP/port aldığı anda, aynı CID'yi kullanarak pakete devam edebilir, sunucu bu CID'yi görünce bunun aynı bağlantı olduğunu anlar.

**Kök neden**: Mobil cihazlarda ağ geçişleri (Wi-Fi ↔ hücresel) çok sık olur ve TCP bu geçişte bağlantıyı koparır çünkü kimlik doğrulaması tamamen 4'lü IP/port eşleşmesine dayanır. QUIC, kimliği taşıma katmanının kendi ürettiği rastgele bir tanımlayıcıya taşıyarak bu kırılganlığı ortadan kaldırır.

**Güvenlik açısından kritik nokta -path validation**: Bir bağlantı yeni bir yoldan (yeni IP kaynağından) paket almaya başladığında, QUIC bunu kör güvenle kabul etmez. Sunucu, yeni yolun gerçekten istemci tarafından kontrol edildiğini doğrulamak için bir **PATH_CHALLENGE** frame'i gönderir ve karşı taraftan aynı rastgele değeri içeren bir **PATH_RESPONSE** bekler. Bu doğrulanana kadar sunucu, o yeni yoldan gönderdiği veri miktarını sınırlar (amplifikasyon sınırı, genelde alınan verinin küçük bir katsayı katı kadarıyla sınırlıdır).

**Neden bu sınır var -amplifikasyon/DoS ile bağlantısı**: Path validation olmasaydı, bir saldırgan kurbanın IP adresini sahtekârlıkla (spoofing) kullanarak sunucuya "ben bu bağlantının yeni yoluyum" diyebilir ve sunucu kurbana büyük miktarda veri gönderirdi -bu klasik bir **yansıma/amplifikasyon DoS saldırısı** (reflection/amplification attack) olurdu, çünkü saldırgan küçük bir paketle sunucuyu kurbana büyük bir yanıt göndermeye kandırmış olur. Aynı mantık, ilk bağlantı kurulumunun (Initial paket) kendisi için de geçerlidir: RFC 9000, sunucunun istemci adresini doğrulamadan (adres doğrulama/anti-amplifikasyon token'ı olmadan) gönderebileceği veri miktarını, istemciden alınan verinin sabit bir katsayısıyla (spesifikasyonda tanımlı bir sınır) sınırlar. Bu, QUIC'i DNS amplifikasyonuna benzer saldırılarda "reflector" olarak kullanılmaktan korur.

**Tespit/savunma açısından**: Ağ savunma ekipleri, tek bir sunucu IP'sinden çok sayıda farklı kurban IP'sine giden orantısız büyük UDP/QUIC yanıtlarını izlemelidir; bu, bir amplifikasyon saldırısının reflector'ı olarak istismar edilen bir sunucunun belirtisi olabilir. Sunucu tarafı yapılandırmalarda anti-amplifikasyon limitinin ve retry (adres doğrulama) mekanizmasının etkin olduğundan emin olunmalıdır.

## 0-RTT Replay ve Diğer QUIC'e Özgü Saldırı Yüzeyleri

QUIC'in tasarımı klasik TCP tabanlı saldırıların çoğunu (SYN flood gibi) değiştirir ama yeni saldırı yüzeyleri de getirir:

1. **0-RTT replay**: Yukarıda ele alındı -idempotent olmayan işlemler risk altındadır.
2. **Amplifikasyon/DoS (reflection)**: Yukarıda ele alındı -RFC seviyesinde sınırlanmıştır ama yanlış yapılandırılmış ya da eski uygulamalarda risk sürebilir.
3. **CID tabanlı bağlantı çalma / off-path saldırılar**: Eğer bir saldırgan bir bağlantının CID'sini öğrenirse (örneğin ağ gözlemi ile, ya da CID'ler öngörülebilir/zayıf üretilmişse), teorik olarak bağlantıyı manipüle etmeye çalışabilir. Bu nedenle uygulamalar CID'leri kriptografik olarak güçlü rastgelelikle üretmelidir; zayıf/öngörülebilir CID üretimi, bir güvenlik açığı sınıfıdır.
4. **Sunucu tarafı kaynak tükenmesi (state exhaustion)**: QUIC bağlantı kurulumu, TCP'ye göre sunucu tarafında daha fazla kriptografik işlem (TLS 1.3 el sıkışması, imza doğrulama) gerektirebilir; bir saldırgan çok sayıda sahte Initial paket göndererek sunucunun CPU/bellek kaynaklarını tüketmeye çalışabilir (bir tür "handshake flood"). Retry mekanizması (stateless retry token) bu saldırıyı azaltır: sunucu, tam el sıkışma durumunu tutmadan önce istemciye bir token gönderir ve istemcinin bu token'ı geri getirmesini ister -bu, sunucunun IP sahtekarlığı yapan saldırganlar için pahalı durum tutmasını engeller.
5. **UDP tabanlı ağ cihazı davranışları**: Bazı ağ cihazları/NAT'lar UDP akışlarını TCP'den daha agresif zaman aşımına uğratır; bu bir "saldırı" değil ama QUIC bağlantılarının beklenmedik şekilde kesilmesine yol açabilen bir operasyonel körlük/dayanıklılık sorunudur. QUIC'in **PING frame** ve idle timeout mekanizmaları bu NAT rebinding sorununu kısmen telafi eder.
6. **Sürüm ve uzantı müzakeresi manipülasyonu (version negotiation)**: Bir saldırgan, sahte bir "version negotiation" paketi enjekte ederek istemciyi daha zayıf/eski bir protokol sürümüne düşürmeye çalışabilir (bir tür downgrade saldırısı). QUIC bunu, el sıkışma sonrasında transport parametrelerinin ve sürüm bilgisinin TLS ile korunan bir alanda tekrar doğrulanmasıyla (transcript'e dahil edilerek) engellemeye çalışır -saldırgan tarafından enjekte edilen sahte bir negotiation, el sıkışma tamamlandığında algılanabilir hale gelir.

Not: Yukarıdaki maddelerin bir kısmı (özellikle 3 ve 6) genel tasarım prensiplerine dayanır; kesin CVE numaraları veya belirli uygulama (implementasyon) hataları burada iddia edilmemektedir -bu tür spesifik zafiyetler, kullanılan QUIC kütüphanesine (quiche, ngtcp2, msquic, quic-go vb.) göre değişir ve güncel güvenlik danışma belgelerinden takip edilmelidir.

## Doğru Kullanım, Tuzaklar ve En İyi Pratikler

**Doğru kullanım**:
- 0-RTT'yi yalnızca idempotent, yan etkisiz istekler için etkinleştirin (örneğin GET ile statik kaynak getirme); state-changing işlemleri (ödeme, hesap değişikliği) 0-RTT üzerinden kabul etmeyin ya da uygulama seviyesinde ek idempotency kontrolü koyun.
- Sunucu tarafında anti-amplifikasyon ve retry (adres doğrulama) mekanizmalarının varsayılan olarak açık olduğundan emin olun; bunları "performans için" kapatmak DoS riskini artırır.
- Connection ID'leri kriptografik olarak güvenli rastgele üreteçle oluşturun, tahmin edilebilir sayaç kullanmayın.
- congestion control (tıkanıklık kontrolü) algoritmasını (örneğin CUBIC, BBR) ağ koşullarına göre seçin/izleyin; QUIC congestion control'ü kernel'den kullanıcı alanına taşıdığı için uygulama/kütüphane seçimi artık performansı doğrudan etkiler.

**Yaygın hatalar**:
- QUIC'i "sadece UDP üzerinde TCP" sanıp güvenlik modelini TCP+TLS ile birebir aynı varsaymak -özellikle 0-RTT'nin farklı garantilere sahip olduğunu gözden kaçırmak.
- Sunucu tarafı kaynak sınırlarını (bağlantı başına bellek, açık stream sayısı, toplam eşzamanlı bağlantı) yapılandırmamak; QUIC'in bağlantı başına daha fazla durum (state) tutması, kontrolsüz bırakıldığında bellek tükenmesi saldırılarına daha açık hale getirebilir.
- Ağ izleme/IDS sistemlerinin hâlâ TCP varsayımlarıyla (port bazlı, açık metin başlık alanlarına bakarak) çalıştığını düşünmek -QUIC trafiğinin büyük kısmı şifreli olduğu için, geleneksel derin paket incelemesi (DPI) çoğu alanı göremez; tespit stratejileri trafik analizi, JA3/JA4 benzeri parmak izi çıkarma (mümkün olan sınırlı açık alanlar üzerinden) veya uç nokta (endpoint) loglarına kaymalıdır.
- Yük dengeleyici (load balancer) ve CDN katmanlarında CID tabanlı yönlendirmenin doğru yapılandırılmadığı senaryolarda, connection migration'ın beklenmedik şekilde bozulması veya oturumların yanlış backend'e düşmesi.

## Tespit ve Savunma Perspektifi Özet

Bir savunma mühendisi/tespit mühendisi olarak QUIC ile çalışırken şu soruları sormak gerekir:

- Sunucumuz 0-RTT'yi kabul ediyor mu, kabul ediyorsa hangi istek türleri için? Replay senaryosunda ne olur?
- Anti-amplifikasyon ve retry mekanizmaları etkin mi; sunucumuz spoof edilmiş bir IP için reflector olarak kullanılabilir mi?
- Bağlantı başına kaynak tüketimi (bellek, stream sayısı, açık bağlantı sayısı) sınırlanmış mı; bir handshake flood senaryosunda sunucu ne kadar dayanır?
- Ağ görünürlüğü (visibility) araçlarımız QUIC/UDP 443 trafiğini nasıl sınıflandırıyor; şifreli olduğu için içerik bazlı değil, davranışsal/metadata bazlı (bağlantı süresi, veri hacmi, zamanlama) tespit stratejilerine mi geçmemiz gerekiyor?
- Connection ID rotasyonu (gizlilik amacıyla CID'lerin periyodik değiştirilmesi, bağlantı izlenebilirliğini/linkability'yi azaltmak için) doğru uygulanıyor mu?

Bu sorular, QUIC'in getirdiği performans kazancının, yeni bir tehdit modeliyle birlikte geldiğini gösterir: middlebox görünürlüğünün azalması hem saldırganın hem savunmacının elini değiştirir -saldırganın payload'ını gizlemesi kolaylaşırken, savunmacının klasik DPI tabanlı tespiti de zayıflar. Bu nedenle QUIC çağında savunma, giderek daha çok uç nokta telemetrisine, davranışsal analize ve protokol seviyesinde doğru yapılandırılmış sınırlara (rate limiting, kaynak kotaları, adres doğrulama) dayanmak zorundadır.

## Sonuç

QUIC, TCP+TLS'in yapısal kısıtlarını (middlebox ossification, HOL blocking, el sıkışma gecikmesi, IP'ye bağımlı kimlik) kökten çözmek için tasarlanmış, taşıma ve şifrelemeyi birleştiren modern bir protokoldür. Bu birleşim, önemli performans kazançları (1-RTT, opsiyonel 0-RTT, gerçek stream multiplexing, connection migration) getirirken, kendine özgü bir güvenlik yüzeyi de (0-RTT replay, amplifikasyon riski, bağlantı durumu tükenmesi, azalan ağ görünürlüğü) doğurur. Bu yüzeyi anlamak, hem protokolü doğru yapılandırmak hem de üzerine kurulu sistemleri (HTTP/3, CDN'ler, mobil uygulamalar) güvenli ve dayanıklı işletmek için zorunludur.
