# Gerçek Zamanlı İletişim Derinliği: WebRTC, Server-Sent Events, Push Notification Mimarisi (APNs/FCM)

## Giriş: WebSocket Yeterli Değil

Çoğu "gerçek zamanlı sistemler" anlatısı WebSocket'te durur ve orada biter. Bu ciddi bir eksikliktir, çünkü üretim sistemlerinin büyük bir kısmı WebSocket'i hiç kullanmaz veya sadece bir parça olarak kullanır. Üç farklı problem sınıfı var ve her biri farklı bir çözüm gerektiriyor:

1. **Medya/veri akışının iki cihaz arasında doğrudan, düşük gecikmeli aktığı** senaryolar (görüntülü arama, ekran paylaşımı, P2P dosya transferi) — bunun çözümü **WebRTC**'dir.
2. **Sunucudan istemciye tek yönlü, sürekli güncelleme akışı** gereken senaryolar (canlı skor, log takibi, bildirim akışı) — bunun çözümü genellikle **Server-Sent Events (SSE)**'dir, WebSocket değil.
3. **Uygulama arka planda veya kapalıyken cihaza mesaj ulaştırmak** — bu tamamen farklı bir problem sınıfıdır ve **APNs/FCM push bildirim mimarisi** ile çözülür; burada TCP soketi bile yoktur, işletim sistemi araya girer.

Bu üçünü karıştırmak mimari hatalara yol açar: WebRTC gerektiren bir görüntülü arama özelliğini WebSocket üzerinden medya aktararak inşa etmeye çalışmak (sunucu maliyeti patlar, gecikme artar) ya da arka plandaki bir mobil uygulamaya "canlı bağlantı" ile bildirim ulaştırmaya çalışmak (işletim sistemi soketi zaten öldürmüştür) gibi. Bu makale her üçünün çalışma mantığını, kök nedenini ve savunma/tespit açısından önemini derinlemesine ele alıyor.

---

## Bölüm 1: WebRTC — Tarayıcılar Arası Doğrudan Bağlantı

### Neden WebRTC Var?

İki tarayıcının birbirine doğrudan medya (ses/video) veya veri göndermesi istendiğinde, en saf çözüm "istemci A'dan istemci B'ye doğrudan TCP/UDP bağlantısı" gibi görünür. Ama bu, günümüz internetinin gerçek topolojisiyle çelişir: neredeyse her cihaz bir **NAT (Network Address Translation)** arkasındadır ve çoğu zaman bir **güvenlik duvarı** da vardır. A'nın B'ye "içeri gel" diyebilmesi için B'nin herkese açık, yönlendirilebilir bir IP:port'u olması gerekir — ki NAT arkasındaki bir ev/ofis cihazının böyle bir adresi yoktur.

WebRTC bu problemi üç bileşenle çözer: **ICE (Interactive Connectivity Establishment)**, **STUN (Session Traversal Utilities for NAT)**, **TURN (Traversal Using Relays around NAT)**. Bunları anlamak WebRTC'yi anlamaktır; gerisi API detayıdır.

### STUN: "Benim Dışarıdan Görünen Adresim Ne?"

STUN'un tek işi budur: istemci bir STUN sunucusuna bir paket gönderir, STUN sunucusu "senden gelen bu paketi şu genel IP:port'tan gördüm" diye cevap verir. İstemci böylece kendi NAT'ının dışarıya hangi IP:port ile çevirdiğini öğrenir (buna **server-reflexive address** denir). Bu bilgiyi karşı tarafa (sinyalleşme kanalıyla) iletir.

Kök neden burada netleşiyor: NAT çevirisi genelde deterministiktir (aynı iç adres+port her zaman aynı dış adres+port'a çevrilir — "cone NAT" durumunda), dolayısıyla A bu dış adresi öğrenip B'ye söylerse, B doğrudan o adrese paket gönderebilir ve NAT bunu doğru şekilde içeri yönlendirir. STUN çok hafiftir: sadece bir "yansıtma" hizmetidir, trafiğin kendisini taşımaz. Bu yüzden STUN sunucusu işletmek ucuzdur.

**Sınırlılık**: Bazı NAT türleri (özellikle **symmetric NAT**, kurumsal ağlarda ve bazı mobil operatörlerde yaygın) her farklı hedef için farklı bir dış port kullanır. Bu durumda STUN ile öğrenilen adres sadece STUN sunucusuna karşı geçerlidir, B'ye karşı geçerli olmayabilir. Bu noktada STUN tek başına yeterli kalmaz.

### TURN: "STUN İşe Yaramazsa Rölede Buluşalım"

TURN, symmetric NAT veya kısıtlayıcı güvenlik duvarı (UDP'yi tamamen bloke eden kurumsal ağlar gibi) durumunda devreye girer. TURN sunucusu bir **röle (relay)** olarak çalışır: her iki taraf da TURN sunucusuna bağlanır, TURN sunucusu trafiği ikisi arasında aktarır. Artık gerçek anlamda P2P değildir — tüm medya trafiği üçüncü bir sunucudan geçer.

Bunun bedelleri açıktır:
- **Bant genişliği maliyeti**: TURN sunucusu tüm medya akışını taşır, bu da P2P'nin "sunucu maliyetsiz" vaadini ortadan kaldırır. Büyük ölçekli WebRTC sistemlerinde (Zoom, Meet benzeri) TURN kullanım oranı genelde %15-30 arası olur (ağ koşullarına göre değişir) ve maliyetin büyük kısmı buradan gelir.
- **Ekstra gecikme**: Röle bir hop daha eklediği için gecikme artar.

**Kök neden özeti**: ICE, STUN ile en ucuz yolu (doğrudan P2P) dener, başarısız olursa TURN ile en pahalı ama garantili yolu (röle) kullanır. Bu "aday toplama ve öncelik sıralama" mantığına **ICE** denir.

### ICE: Adayları Toplama ve En İyisini Seçme

ICE, bir istemcinin kendi bağlanabilirlik "adaylarını" (candidates) toplama sürecidir:
1. **Host candidate**: Cihazın kendi yerel IP'si (örn. 192.168.x.x).
2. **Server-reflexive candidate**: STUN ile öğrenilen dış IP:port.
3. **Relay candidate**: TURN sunucusu üzerinden alınan adres.

İki taraf da bu adayları sinyalleşme kanalıyla (aşağıda) değişir, sonra **ICE connectivity checks** yaparak (her aday çiftini deneyerek) hangi çiftin gerçekten çalıştığını bulur. Çalışan en düşük maliyetli (genelde host > server-reflexive > relay önceliğiyle) çift seçilir. Bu süreç "ICE gathering" ve "ICE negotiation" olarak ikiye ayrılır ve WebRTC bağlantı kurulumunun büyük kısmı budur.

### Sinyalleşme (Signaling) — WebRTC'nin Kasıtlı Boşluğu

Önemli bir kavramsal nokta: **WebRTC standardı sinyalleşme protokolünü tanımlamaz.** SDP (Session Description Protocol — medya yetenekleri, kodekler, ağ adaylarının tanımı) mesajlarının A'dan B'ye nasıl taşınacağı uygulamaya bırakılmıştır. Pratikte bu WebSocket, SSE, hatta düz HTTP polling ile yapılır.

Bu tasarım kararının nedeni: sinyalleşme aslında "oturum kurulumu" problemi, medya taşıma problemi değildir; var olan bir uygulama sunucusu (chat sunucusu gibi) zaten bir kanal üzerinden mesajlaşabiliyorsa, o kanalı SDP taşımak için de kullanabilir. Yaygın akış:

```
A (tarayıcı) --SDP Offer--> Sinyalleşme Sunucusu --SDP Offer--> B (tarayıcı)
B --SDP Answer--> Sinyalleşme Sunucusu --SDP Answer--> A
A <--ICE candidates (karşılıklı, sinyalleşme üzerinden)--> B
[ICE negotiation tamamlanır, doğrudan/TURN bağlantı kurulur]
[Medya artık sinyalleşme sunucusundan GEÇMEZ — P2P veya TURN üzerinden akar]
```

Buradaki en kritik güvenlik/mimari çıkarım şudur: **sinyalleşme sunucusu medya içeriğini görmez** (P2P durumunda). Bu hem gizlilik avantajı hem de bir tuzaktır — geliştiriciler bazen sinyalleşme sunucusunun "her şeyi gördüğünü" varsayarak loglama/moderasyon tasarlar, ama gerçek medya trafiği oradan hiç geçmez.

### Şifreleme: DTLS-SRTP — Opsiyonel Değil, Zorunlu

WebRTC'de medya trafiği **her zaman şifrelenir**; bu, standart tarafından zorunlu kılınmıştır (WebRTC'nin diğer eski medya protokollerinden temel farkı budur). Mekanizma:
- **DTLS (Datagram TLS)**: UDP üzerinde TLS benzeri bir handshake yaparak simetrik anahtar değişimini gerçekleştirir.
- **SRTP (Secure Real-time Transport Protocol)**: DTLS ile türetilen anahtarları kullanarak asıl ses/video paketlerini şifreler.
- Veri kanalları (DataChannel) için ise SCTP, DTLS üzerinde taşınır.

**Kök neden**: RTP (şifresiz gerçek zamanlı taşıma protokolü) tasarım olarak açık metindir; VoIP'in erken günlerinde bu ciddi dinleme (eavesdropping) riskiydi. WebRTC, tarayıcı tabanlı olduğu ve güvenilmeyen ağlar (halka açık Wi-Fi vb.) üzerinden çalışacağı için şifrelemeyi opsiyonel bırakmadı, zorunlu yaptı. Bu da demektir ki bir WebRTC bağlantısını "düz metin" olarak dinlemek, TLS'i kırmadan mümkün değildir — saldırgan ya uç noktalardan birini (tarayıcı/cihaz) ele geçirmeli ya da MITM ile DTLS handshake'ine müdahale etmelidir (ki sertifika doğrulaması + sinyalleşme kanalının bütünlüğü buna karşı korur).

### Savunma ve Tespit Açısından WebRTC

**IP sızıntısı (IP leak) riski**: ICE candidate toplama süreci, VPN kullanan bir kullanıcının bile gerçek yerel/genel IP adresinin JavaScript üzerinden ifşa olmasına yol açabilir (ünlü "WebRTC IP leak" sorunu). Bunun kök nedeni: `RTCPeerConnection` API'si, candidate'ları toplarken tarayıcının ağ arayüzü bilgisine erişir; VPN her zaman bu düzeyde araya giremeyebilir. Savunma: tarayıcı ayarlarında ICE candidate politikasını kısıtlamak (`relay` moduna zorlamak) veya VPN yazılımının WebRTC'yi özel olarak ele alması.

**TURN sunucusu istismarı**: TURN sunucuları kimlik doğrulama olmadan açık bırakılırsa, üçüncü taraflar bunları ücretsiz bir trafik rölesi (açık proxy) olarak kötüye kullanabilir — bu hem maliyet hem de kötüye kullanım (anonimleştirme aracı olarak) riski taşır. Savunma: TURN için zaman sınırlı, kısa ömürlü kimlik bilgileri (genellikle HMAC tabanlı geçici kullanıcı adı/parola, `coturn` gibi sunucularda yaygın desen) kullanmak, sabit/paylaşılan parola kullanmamak.

**Sinyalleşme kanalının güvenliği**: SDP mesajları IP adresleri ve ağ topolojisi bilgisi taşıdığından, sinyalleşme kanalı (WebSocket/SSE) mutlaka TLS ile korunmalı ve karşı tarafın kimliği (oturum/JWT ile) doğrulanmalıdır — aksi halde bir saldırgan sahte SDP answer enjekte ederek görüşmeyi kendi TURN/relay'ine yönlendirebilir (ortadaki adam senaryosu, "SDP injection" olarak da anılır).

**Bant genişliği/DoS gözetimi**: Bir istemcinin anormal sayıda PeerConnection açması veya TURN üzerinden aşırı veri aktarması, kaynak tüketim saldırısı (TURN relay'i doldurmak) belirtisi olabilir; sunucu tarafında oturum başına bant genişliği ve süre limiti koymak standart bir korumadır.

---

## Bölüm 2: Server-Sent Events (SSE) — Hafif Tek Yönlü Akış

### Neden SSE, Neden WebSocket Değil?

Sunucudan istemciye tek yönlü, sürekli güncelleme gönderilecekse (canlı skor, log akışı, AI yanıtlarının token-token akıtılması, bildirim listesi) WebSocket kullanmak fazla mühendisliktir. WebSocket çift yönlü, ayrı bir protokoldür (HTTP Upgrade ile başlar, sonra kendi çerçeveleme formatına geçer); ama bu senaryoda istemciden sunucuya sürekli mesaj gönderme ihtiyacı yoktur (istekler zaten normal HTTP ile yapılabilir).

SSE, **düz HTTP üzerinde**, `text/event-stream` içerik tipiyle çalışan basit bir protokoldür. Sunucu bağlantıyı açık tutar ve `data: ...\n\n` formatında mesajlar akıtır. Bu tasarımın kök nedeni: mevcut HTTP altyapısını (proxy'ler, yük dengeleyiciler, CDN'ler, kimlik doğrulama katmanları) hiç değiştirmeden yeniden kullanmaktır. WebSocket bazı eski proxy'lerde/güvenlik duvarlarında sorun çıkarabilirken, SSE "sadece uzun süren bir HTTP yanıtı" olduğu için bu altyapıyla doğal olarak uyumludur.

### Otomatik Yeniden Bağlanma ve `Last-Event-ID`

SSE'nin az bilinen ama kritik bir özelliği: tarayıcının yerleşik `EventSource` API'si bağlantı koptuğunda **otomatik olarak yeniden bağlanır** ve son alınan olayın kimliğini (`Last-Event-ID` header'ı ile) sunucuya geri gönderir. Bu, uygulamanın "kaldığı yerden devam et" mantığını sunucu tarafında olay kimlikleriyle (event ID) implemente etmesine imkân tanır — istemci tarafında ekstra kod yazmaya gerek kalmaz. Bu, WebSocket'e göre SSE'nin gözden kaçan bir avantajıdır; WebSocket'te yeniden bağlanma ve durum senkronizasyonu tamamen uygulamanın sorumluluğundadır.

### Kök Sınırlılık: Bağlantı Sayısı ve HTTP/1.1 Domain Limiti

HTTP/1.1'de tarayıcılar aynı domaine eşzamanlı olarak genelde 6 bağlantıya izin verir. Bir sayfada birden fazla sekme açıksa ve her biri aynı domain'e SSE bağlantısı açıyorsa, bu limit hızla dolar ve diğer HTTP istekleri (normal API çağrıları) kilitlenebilir. **HTTP/2 bu sorunu büyük ölçüde çözer** çünkü tek bir TCP bağlantısı üzerinde çoklama (multiplexing) yapar — SSE akışı diğer istekleri bloke etmez. Bu yüzden üretimde SSE kullanan sistemlerin HTTP/2 (veya HTTP/3) üzerinden servis edilmesi neredeyse zorunludur; aksi halde tarayıcı limiti kaynaklı gizli bir kesinti (istemci fark etmeden diğer isteklerin askıda kalması) yaşanır.

### Yaygın Hatalar ve En İyi Pratikler

- **Proxy/buffer tuzağı**: Nginx gibi ters proxy'ler varsayılan olarak yanıtları arabelleğe alabilir (buffering), bu da SSE olaylarının gerçek zamanlı değil, birikip toplu halde istemciye ulaşmasına yol açar. Kök neden: proxy, yanıtın "bittiğini" beklemeye çalışır ama SSE yanıtı hiç bitmez (uzun süre açık kalır). Çözüm: proxy tarafında bu rota için buffering'i devre dışı bırakmak (`X-Accel-Buffering: no` gibi başlıklarla veya proxy konfigürasyonuyla).
- **Yük dengeleyici zaman aşımı (timeout)**: Çoğu yük dengeleyici, uzun süre veri akmayan (idle) bağlantıları kapatır. SSE bağlantısı veri göndermiyorsa (örneğin olay yoksa) bu süre dolabilir. Çözüm: periyodik "keep-alive" yorumu satırları (`: heartbeat\n\n` gibi boş yorum mesajları) göndermek — bu, SSE'nin protokol düzeyinde desteklediği bir mekanizmadır.
- **Ölçeklenebilirlik**: Her açık SSE bağlantısı sunucu tarafında bir bağlantı/thread/coroutine tüketir. Binlerce eşzamanlı istemci için event-loop tabanlı (asenkron I/O) sunucu mimarisi (thread-per-connection değil) gerekir; aksi halde bağlantı sayısı arttıkça sunucu kaynakları tükenir.
- **Kimlik doğrulama**: `EventSource` API'si özel HTTP header ekleyemez (yalnızca `withCredentials` ile çerezleri taşıyabilir), bu yüzden token tabanlı kimlik doğrulama genelde URL query parametresi olarak taşınır — bu da token'ın loglara (proxy/erişim logları) sızma riskini artırır. Savunma: kısa ömürlü, tek kullanımlık (one-time) token'lar üretmek, uzun ömürlü kalıcı token'ları URL'de asla taşımamak.

### SSE'nin Güvenlik/Tespit Açısı

SSE düz HTTP olduğu için TLS zorunluluğu ve CORS kuralları normal HTTP isteği gibi işler — bu bir avantajdır (mevcut güvenlik altyapısı doğrudan uygulanır). Ama loglama açısından dikkat: uzun süre açık kalan bir SSE bağlantısı, standart erişim loglarında "tek bir istek" gibi görünür ve o istek üzerinden saatlerce veri aktığı fark edilmeyebilir; anomali tespiti için bağlantı süresi ve toplam aktarılan bayt miktarı gibi metrikler ayrıca izlenmelidir.

---

## Bölüm 3: Push Notification Mimarisi (APNs/FCM) — Bağlantısız Gerçek Zamanlılık

### Kök Problem: Uygulama Çalışmıyorken Nasıl Mesaj Ulaştırılır?

WebSocket ve SSE'nin ortak bir varsayımı vardır: **istemci tarafında açık bir bağlantı/soket vardır.** Mobil işletim sistemlerinde bu varsayım geçersizdir — pil tasarrufu için işletim sistemi, arka plandaki uygulamaların ağ soketlerini agresif şekilde kapatır/askıya alır. Bir uygulama arka plandayken kendi WebSocket'ini canlı tutamaz.

Bu yüzden push bildirimleri **uygulamanın soketi üzerinden değil, işletim sisteminin kendi her zaman açık bağlantısı üzerinden** gelir. iOS'ta bu APNs (Apple Push Notification service), Android'de FCM (Firebase Cloud Messaging) aracılığıyla olur. Kök tasarım fikri: cihazın işletim sistemi, tüm uygulamalar adına **tek bir** kalıcı bağlantıyı bulut sağlayıcısına (Apple/Google sunucuları) açık tutar; uygulamalar kendi soketlerini yönetmek zorunda kalmaz.

### Akış: Sunucu → APNs/FCM → Cihaz → Uygulama

```
[Uygulama Sunucusu] --push isteği (device token + payload)--> [APNs / FCM]
[APNs / FCM] --(OS'un kalıcı bağlantısı üzerinden)--> [Cihaz İşletim Sistemi]
[Cihaz İşletim Sistemi] --uyandırma/teslim--> [Hedef Uygulama]
```

Üç aktör var: **uygulama sunucusu** (sizin backend'iniz), **push sağlayıcısı** (Apple/Google altyapısı), **cihaz**. Uygulama sunucusunun cihaza asla doğrudan bağlantısı yoktur — her zaman push sağlayıcısı üzerinden dolaylı iletim olur. Bu, mimarinin en kritik noktasıdır: **push sağlayıcısına güven zorunludur**, çünkü mesaj içeriği onun altyapısından geçer.

### Device Token: Kimlik mi, Sır mı?

Bir uygulama ilk açıldığında işletim sistemine kayıt olur ve bir **device token** (APNs) veya **registration token** (FCM) alır. Bu token, "bu APNs/FCM sunucusu, bu cihazdaki bu uygulamayı benzersiz şekilde temsil eder" anlamına gelir. Uygulama sunucusu bu token'ı saklar ve push göndermek istediğinde token'ı hedef olarak kullanır.

**Kritik nokta**: Token kalıcı bir kimlik değildir — uygulama yeniden yüklenirse, işletim sistemi güncellenirse veya sağlayıcı rotasyon yaparsa değişebilir. Bu yüzden uygulamalar token yenileme olaylarını (`didRegisterForRemoteNotificationsWithDeviceToken` / FCM'nin `onNewToken` callback'i) dinleyip backend'e güncel token'ı bildirmek zorundadır. Bunu yapmayan sistemler "sessizce" bildirim göndermeyi bırakır — token eskimiştir ama hata da net değildir (genelde "unregistered"/geçersiz token hatası döner, uygulama bunu işleyip veritabanından silmelidir).

**Güvenlik açısı**: Token tek başına bir "yetki" değildir — token'ı ele geçiren biri, sizin uygulama sunucunuzun kimlik bilgileri (APNs sertifikası/anahtarı veya FCM server key) olmadan push gönderemez. Ama token, cihazı hedef almak için yeterlidir; bu yüzden token'lar backend veritabanında gereksiz yere sızdırılmamalı, loglara yazılmamalıdır (bir saldırgan token'ı ele geçirip *sizin* kimlik bilgilerinizi de ele geçirirse, o kullanıcıya istenmeyen/aldatıcı bildirim gönderebilir — sosyal mühendislik/phishing vektörü).

### Kimlik Doğrulama: Sunucudan Push Sağlayıcısına

Uygulama sunucusunun APNs/FCM'e "ben gerçekten bu uygulamanın sahibiyim" demesi gerekir:
- **APNs**: Token tabanlı kimlik doğrulama (JWT benzeri, ES256 imzalı, `.p8` anahtar dosyasıyla üretilen bir kimlik doğrulama token'ı) veya eski usul TLS sertifikası tabanlı yöntem. Token tabanlı yöntem tercih edilir çünkü sertifikalar süre dolduğunda manuel yenileme gerektirirken, imzalanan JWT token daha esnektir ve tek bir anahtarla birden fazla uygulama/servis kimlik doğrulaması yapılabilir.
- **FCM**: Google servis hesabı kimlik bilgileri (service account JSON) ile OAuth2 tabanlı erişim token'ı alınır, istekler bu token ile imzalanır.

**Kök neden — neden bu kadar katı?**: Push kanalı, kullanıcının kişisel cihazına doğrudan içerik enjekte eden bir kanaldır. Kimlik doğrulama zayıf olsaydı, herhangi biri rastgele cihazlara (device token'ı bilirse) sahte bildirim gönderebilirdi — phishing, itibar zedeleme, hatta bazı bildirim türlerinin arka planda kod tetiklemesi (silent push / background fetch tetikleme) nedeniyle kaynak tüketimi saldırısına dönüşebilirdi.

### Silent Push / Background Push: Görünmez Ama Güçlü

Hem APNs hem FCM, kullanıcıya görünür bir bildirim göstermeden uygulamayı arka planda uyandırıp veri senkronize etmesini sağlayan bir mekanizma sunar (APNs'te `content-available: 1` ile "silent notification", FCM'de "data message"). Bu, gerçek zamanlı senkronizasyon (örneğin yeni mesaj geldiğinde uygulamanın arka planda önbelleği güncellemesi) için güçlü bir araçtır.

**Tuzak ve tespit açısı**: Bu mekanizma kötüye kullanılabilir — bir saldırgan (ya da agresif bir uygulama geliştiricisi) sık silent push göndererek cihazı sürekli uyandırıp pil/veri tüketimini artırabilir. İşletim sistemleri bu yüzden silent push'lara saatlik/günlük kota sınırlaması uygular ve kotayı aşan uygulamaların bildirimlerini sessizce düşürebilir. Savunma tarafında: uygulamanın silent push sıklığını izlemek, gereksiz senkronizasyonu azaltmak; kullanıcı tarafında ise anormal pil tüketiminin bir "aşırı arka plan uyandırma" belirtisi olabileceğini bilmek.

### Yaygın Hatalar

- **Token'ı asla yenilememek**: Uygulamalar token rotasyonunu dinlemezse, zamanla bildirim ulaşmayan kullanıcı oranı sessizce artar; bu genelde "bildirimler bozuk" şikayetleriyle fark edilir, kod incelemesiyle değil.
- **Payload boyutu sınırları**: Hem APNs hem FCM, bildirim payload boyutuna sıkı sınır koyar (birkaç KB mertebesinde). Büyük veri göndermeye çalışmak sessiz başarısızlıkla sonuçlanabilir; büyük veri gerekiyorsa bildirim sadece bir "tetikleyici" olmalı, asıl veri uygulama kendi API'sinden çekmelidir.
- **Sertifika/anahtar süre dolumunu izlememek**: APNs sertifikası veya kimlik doğrulama anahtarı süresi dolduğunda tüm push akışı aniden durur; bu genelde production'da "neden bildirimler gitmiyor" paniğiyle keşfedilir. Sertifika/anahtar geçerlilik süresi izlemesi (monitoring/alerting) standart bir operasyonel pratik olmalı.
- **Tek noktadan gönderim varsayımı**: FCM/APNs %100 teslimat garantisi vermez (best-effort'tur); kritik iş mantığı push bildirimin ulaştığı varsayımı üzerine kurulmamalı, uygulama açıldığında ayrıca bir "reconciliation" (durumu senkronize etme) adımı olmalıdır.

---

## Üçünü Bir Arada Düşünmek: Mimari Karar Ağacı

Pratikte bir sistem tasarlarken şu soru sırası işe yarar:

1. **İki uç nokta arasında doğrudan medya/veri akışı mı gerekiyor (ses, video, P2P dosya)?** → WebRTC. STUN/TURN altyapısını (kendi TURN sunucunuzu işletmek ya da yönetilen bir servis kullanmak) ve sinyalleşme kanalını planlayın.
2. **Sadece sunucudan istemciye tek yönlü, sürekli akış mı gerekiyor ve istemci uygulama açık/ön planda mı çalışacak?** → SSE. HTTP/2 arkasında, buffering kapalı, heartbeat'li.
3. **Çift yönlü, düşük gecikmeli, oturum boyunca sürekli mesajlaşma mı gerekiyor (chat, oyun, canlı işbirliği)?** → WebSocket (bu makalenin kapsamı dışında ama üçlemenin tamamlayıcısı).
4. **Uygulama arka planda/kapalıyken cihaza ulaşmak mı gerekiyor?** → Push bildirim (APNs/FCM), çünkü hiçbir soket tabanlı çözüm bu durumda çalışmaz — işletim sistemi araya girmek zorundadır.

Bu dört mekanizma birbirinin yerine geçmez, birbirini tamamlar. Olgun bir gerçek zamanlı sistem (örneğin bir görüntülü sohbet uygulaması) genelde hepsini aynı anda kullanır: sinyalleşme için WebSocket/SSE, medya için WebRTC, kullanıcı uygulamayı kapattığında "gelen arama" bildirimi için APNs/FCM (özellikle iOS'ta VoIP push — `PushKit` — arka planda gelen görüntülü aramayı uyandırmak için ayrı bir push kategorisidir ve normal bildirim push'undan farklı önceliğe sahiptir).

## Sonuç

"Gerçek zamanlı" tek bir teknoloji değil, farklı kısıtlar altında çalışan bir mekanizma ailesidir. WebRTC, NAT arkasındaki iki cihazın doğrudan konuşabilmesi için ICE/STUN/TURN üçlüsünü ve zorunlu DTLS-SRTP şifrelemesini kullanır; kök zorluğu ağ topolojisidir (NAT, güvenlik duvarları). SSE, HTTP'nin üzerine kurulu hafif bir tek yönlü akış protokolüdür; kök zorluğu altyapı uyumluluğudur (proxy buffering, yük dengeleyici timeout'ları). Push bildirimleri ise bambaşka bir kategoridir — soket tabanlı hiçbir çözümün çalışmadığı, işletim sisteminin aracılık ettiği, kimlik doğrulaması ve token yönetimi etrafında dönen bir güven zinciridir. Bu üçünü doğru yerde doğru şekilde kullanmak — ve her birinin kendine özgü tuzaklarını (IP sızıntısı, TURN istismarı, proxy buffering, token rotasyonu, silent push kötüye kullanımı) bilmek — gerçek zamanlı sistemleri hem doğru hem güvenli inşa etmenin temelidir.
