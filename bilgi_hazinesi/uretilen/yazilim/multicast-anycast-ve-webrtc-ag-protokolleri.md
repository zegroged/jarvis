# Multicast/Anycast ve WebRTC Ağ Protokolleri (ICE/STUN/TURN)

## Giriş: Neden Bu Konu Önemli?

Modern web uygulamaları artık yalnızca istemci-sunucu (client-server) HTTP istekleriyle sınırlı değil. Görüntülü görüşme, sesli arama, ekran paylaşımı ve düşük gecikmeli oyun akışı gibi **gerçek zamanlı iletişim** (real-time communication, RTC) senaryoları tarayıcı içinde doğrudan çalışabiliyor. Bunu mümkün kılan teknoloji **WebRTC**'dir. Ancak WebRTC'nin temel zorluğu, iki tarayıcının internetteki **NAT** (Network Address Translation) ve güvenlik duvarları arkasında olmasına rağmen birbirini nasıl bulup **doğrudan** (peer-to-peer) bağlanacağıdır.

Bu makale iki birbiriyle ilişkili konuyu ele alır:

1. **Adresleme modelleri**: Unicast, Multicast, Anycast — trafiğin bir noktadan çoğa, çoktan bire nasıl dağıtıldığı.
2. **NAT geçiş protokolleri**: STUN, TURN ve bunları birleştiren ICE çerçevesi — WebRTC'nin bağlantı kurma mekanizması.

Ayrıca WebRTC'nin sıkça göz ardı edilen bir yan etkisini inceleyeceğiz: **WebRTC IP leak** (IP sızıntısı) — kullanıcının VPN arkasında olsa bile gerçek IP adresinin ifşa olabilmesi ve buna karşı savunma/tespit yöntemleri.

---

## Bölüm 1: Adresleme Modelleri — Unicast, Multicast, Anycast

### Tanım

IP ağlarında bir paketin hedefe nasıl ulaştırıldığını belirleyen üç temel iletişim modeli vardır. Bunlar "kaç alıcıya" ve "hangi alıcıya" sorularının cevabıdır.

- **Unicast (bire bir)**: Tek bir kaynaktan tek bir hedefe. İnternet trafiğinin ezici çoğunluğu budur. Bir web sayfası açtığınızda tarayıcınız ile sunucu arasındaki iletişim unicast'tir.
- **Multicast (bire çok)**: Tek bir kaynaktan, o trafiği almak isteyen **belirli bir grup** alıcıya. Kaynak paketi bir kez gönderir; ağ altyapısı (router'lar) paketi kopyalayıp gruptaki her üyeye dağıtır.
- **Anycast (bire en yakın olan)**: Aynı IP adresi coğrafi olarak dağıtılmış **birden fazla sunucuya** atanır. İstemcinin paketi, ağ topolojisi açısından **en yakın/en uygun** kopyaya yönlendirilir.

(Tarihsel bir dördüncü model olan **Broadcast** — bir ağdaki herkese gönderim — IPv4'e özgüdür ve IPv6'da yerini multicast almıştır.)

### Kök Neden / Çalışma Mantığı

**Multicast** neden var? Aynı içeriği (örneğin bir IPTV yayını veya borsa fiyat akışı) binlerce alıcıya unicast ile göndermek, kaynak sunucunun aynı veriyi binlerce kez kopyalayıp göndermesi demektir — bant genişliği israfı. Multicast'te kaynak veriyi **bir kez** gönderir; kopyalama işi ağın kenarına, dallanma noktalarındaki router'lara devredilir. IPv4'te multicast için **224.0.0.0 – 239.255.255.255** aralığı (D sınıfı) ayrılmıştır. Alıcılar **IGMP** (Internet Group Management Protocol) ile bir gruba katılırlar; router'lar arasındaki multicast yönlendirmesi ise **PIM** gibi protokollerle yapılır.

Önemli bir gerçek: **Multicast, genel internette (public internet) pratikte çalışmaz.** İnternet omurgasındaki (backbone) ISP'ler genellikle multicast trafiğini birbirine iletmez. Bu yüzden multicast esas olarak **kontrollü, tek yönetim alanındaki ağlarda** (kurumsal LAN, veri merkezi, ISP'nin kendi IPTV altyapısı) kullanılır. İnternet ölçeğinde "bire çok" dağıtım ihtiyacı, uygulama katmanında CDN'ler ve HTTP tabanlı adaptif akış (HLS, DASH) ile çözülür.

**Anycast** neden var? Aynı hizmeti dünya çapında birçok noktadan sunmak istediğinizde, kullanıcıyı otomatik olarak en yakın noktaya yönlendirmenin en zarif yolu anycast'tir. Aynı IP prefix'i (örneğin bir /24 bloğu) birden fazla veri merkezinden **BGP** (Border Gateway Protocol) ile duyurulur. Her istemcinin trafiği, BGP'nin "en kısa AS yolu" mantığıyla ona en yakın kopyaya akar. Bu, sihirli bir yük dengeleme ve yakınlık optimizasyonu sağlar.

### Örnek

- **DNS kök sunucuları**: 13 mantıksal kök sunucu adresi vardır, ancak her biri anycast sayesinde dünya genelinde yüzlerce fiziksel örneğe (instance) karşılık gelir. `8.8.8.8` (Google Public DNS) ve `1.1.1.1` (Cloudflare) de anycast'tir — İstanbul'dan sorduğunuzda muhtemelen Türkiye'ye yakın bir sunucuya, Tokyo'dan sorulduğunda Japonya'ya yakın bir sunucuya ulaşır. IP aynıdır; ulaşılan makine farklıdır.
- **CDN ve DDoS azaltma**: Cloudflare, Fastly gibi CDN'ler anycast kullanır. Bir DDoS saldırısında trafik tek bir noktaya değil, dünyadaki tüm PoP'lara (Point of Presence) dağılır; böylece saldırı **coğrafi olarak seyrelir** ve tek bir veri merkezini boğamaz.

### Doğru Kullanım ve Tuzaklar

- **Anycast, TCP için dikkat gerektirir.** Çoğu anycast dağıtımı TCP ile iyi çalışır çünkü BGP yolları oturum süresince genellikle kararlıdır. Ancak bir BGP rota değişikliği (route flap) olursa, kurulmuş bir TCP oturumu ortasında **farklı bir sunucuya** yönlenebilir; bu durumda o sunucu oturumu tanımadığı için bağlantı kopar. Bu yüzden anycast en çok **kısa, durumsuz (stateless)** işlemlerde — özellikle UDP tabanlı DNS'te — parlar.
- **"Coğrafi en yakın" ile "topolojik en yakın" karıştırılır.** Anycast BGP'ye göre yönlendirir; BGP metriği fiziksel mesafe değil AS yollarıdır. Bazen fiziksel olarak yakın ama BGP açısından uzak bir kopyaya gidebilirsiniz. Bu normaldir.
- **Multicast'i internette çalışır sanmak.** Yeni başlayanların en yaygın hatası budur. LAN'da mükemmel çalışan multicast uygulaması internete çıkınca sessizce çalışmaz.

---

## Bölüm 2: WebRTC ve NAT Geçişi Problemi

### Tanım

**WebRTC** (Web Real-Time Communication), tarayıcılar ve mobil uygulamalar arasında eklenti (plugin) olmadan doğrudan ses, video ve rastgele veri (data channel) alışverişi sağlayan bir teknoloji setidir. Medya akışı için genellikle **SRTP** (güvenli RTP), veri kanalı için **SCTP over DTLS** kullanılır; taşıma katmanında büyük ölçüde **UDP** tercih edilir çünkü gerçek zamanlı medyada düşük gecikme, güvenilir teslimattan daha önemlidir.

### Kök Neden / Çalışma Mantığı: NAT Neden Sorun?

Evdeki ya da ofisteki cihazınız **özel (private) bir IP adresine** sahiptir (örneğin `192.168.1.42`). Bu adres internette yönlendirilemez. Router'ınız **NAT** yaparak, giden bağlantılarda özel IP:port'unuzu kendi **genel (public) IP** adresi ve bir port ile eşler. Sorun şudur:

- İki tarayıcı da NAT arkasındadır ve **kendi genel IP:port** ikilisini bilmez.
- NAT, dışarıdan **kendiliğinden gelen** (unsolicited) paketleri varsayılan olarak reddeder — içeriden önce bir bağlantı başlatılmadıysa paket düşer.

Yani iki peer'ın doğrudan bağlanabilmesi için önce şu bilinmelidir: "Karşı taraf beni internette hangi IP:port üzerinden görüyor?" ve "NAT'ımda bu bağlantı için bir delik (hole) açık mı?" İşte **STUN, TURN ve ICE** bu problemi çözer.

---

## Bölüm 3: STUN — Kendi Genel Adresini Öğrenmek

### Tanım

**STUN** (Session Traversal Utilities for NAT), bir istemcinin NAT arkasındayken **kendi genel IP adresini ve portunu** öğrenmesini sağlayan basit bir istek-yanıt protokolüdür.

### Çalışma Mantığı

İstemci, internette bulunan bir **STUN sunucusuna** bir bağlama isteği (Binding Request) gönderir. STUN sunucusu paketi aldığında, paketin **kaynak IP:port** bilgisine (yani NAT'ın dışarıya gösterdiği eşlemeye) bakar ve bunu yanıtta istemciye geri söyler: "Ben seni `85.x.x.x:54321` olarak görüyorum."

Bu bilgiye WebRTC terminolojisinde **server reflexive address** (sunucu yansımalı adres, `srflx`) denir. İstemci artık bu adresi karşı tarafa "beni buradan dene" diye önerebilir.

STUN son derece hafiftir: sunucu sadece bir ayna gibi davranır, medya trafiğini taşımaz. Bu yüzden çok ucuzdur ve WebRTC dağıtımlarının büyük kısmı **kamuya açık STUN sunucularıyla** (örneğin Google'ın çalıştırdığı genel STUN uçları) idare edebilir.

### Sınırı

STUN her NAT türünde işe yaramaz. Özellikle **Symmetric NAT** denen türde, NAT her farklı hedef için farklı bir dış port eşlemesi kullanır. Bu durumda STUN sunucusuyla konuşurken görülen port, peer ile konuşurken kullanılacak porttan farklı olur; delik açma (hole punching) başarısız olur. İşte bu noktada TURN devreye girer.

---

## Bölüm 4: TURN — Aktarma (Relay) Sunucusu

### Tanım

**TURN** (Traversal Using Relays around NAT), doğrudan peer-to-peer bağlantının kurulamadığı durumlarda medya trafiğini **kendi üzerinden aktaran** (relay) bir sunucudur. TURN aslında STUN'un bir uzantısıdır.

### Çalışma Mantığı

Doğrudan bağlantı imkânsızsa (iki taraf da katı Symmetric NAT arkasındaysa veya kurumsal güvenlik duvarı UDP'yi engelliyorsa), her iki peer da TURN sunucusuna bağlanır ve trafiği **onun aracılığıyla** geçirir. Peer A → TURN → Peer B. Bu adrese **relay address** (`relay`) denir.

TURN çalışması için istemcinin sunucuda kimlik doğrulaması yapması gerekir (aksi halde herkes sizin bant genişliğinizi bedava kullanabilir). Genellikle **kısa ömürlü kimlik bilgileri** (time-limited credentials) üretilir.

### Tuzaklar / Maliyet

- **TURN pahalıdır.** STUN sadece adres söyler; TURN ise **tüm medya trafiğini** kendi bant genişliği üzerinden taşır. Görüntülü bir görüşme onlarca Mbps tutabilir. Bu yüzden TURN son çare olarak, "başka türlü bağlanamıyorsak" diye kullanılır.
- **Kamuya açık ücretsiz TURN sunucusu neredeyse yoktur** — çünkü maliyeti taşıyabilecek kimse bunu bedava sunmaz. Üretim WebRTC uygulamaları kendi TURN sunucularını (örneğin `coturn` yazılımıyla) çalıştırır veya bir servis satın alır.
- **Güvenlik duvarı dostu port seçimi.** Katı kurumsal ağlarda yalnızca 443/TCP (HTTPS) açık olabilir. Bu yüzden TURN'ün **TLS üzerinden 443 portunda (TURNS)** çalışacak şekilde yapılandırılması, en kısıtlı ağlarda bile bağlantı kurma şansını artırır.

---

## Bölüm 5: ICE — Hepsini Birleştiren Çerçeve

### Tanım

**ICE** (Interactive Connectivity Establishment), STUN ve TURN'ü kullanarak iki peer arasında **çalışan en iyi yolu bulan** koordinasyon çerçevesidir. ICE tek bir protokol değil, bir **strateji**dir: "Elimizdeki tüm olası adresleri toplayalım, hepsini deneyelim, çalışan en iyisini seçelim."

### Çalışma Mantığı: Aday (Candidate) Toplama ve Sınama

ICE üç tür **aday (candidate)** adres toplar:

1. **Host candidate**: Cihazın kendi yerel arayüz adresleri (örneğin `192.168.1.42`, Wi-Fi ve Ethernet ayrı ayrı, ve varsa IPv6 adresleri). Aynı LAN'daki iki cihaz için en hızlı yol budur.
2. **Server reflexive (`srflx`)**: STUN ile öğrenilen genel NAT adresi.
3. **Relay (`relay`)**: TURN sunucusundan alınan aktarma adresi — en son çare.

İki peer bu adaylarını **sinyalleşme (signaling)** kanalı üzerinden birbirine gönderir. (Dikkat: **sinyalleşmeyi WebRTC standardı belirlemez** — genellikle geliştirici kendi WebSocket sunucusuyla SDP tekliflerini/adayları taşır.) Ardından ICE, adayları **çiftler halinde** eşleştirir ve her çift için **bağlanabilirlik kontrolü** (connectivity check) yapar — bunlar STUN Binding istekleridir. Bu, aynı zamanda NAT'ta **hole punching** (delik açma) etkisi yaratır: iki taraf da eşzamanlı paket gönderince NAT'lar her iki yönde de deliği açık tutar.

Çalışan çiftler arasından, önceden atanmış **öncelik (priority)** değerlerine göre en iyisi seçilir. Genel kural: **host > srflx > relay**. Yani mümkünse doğrudan, olmuyorsa STUN ile, o da olmuyorsa TURN ile. Buna **ICE nomination** denir.

### ICE Türleri ve Gelişmeler

- **Trickle ICE**: Klasik ICE'de tüm adaylar toplanana kadar beklenirdi; bu yavaştı. Trickle ICE'de adaylar **bulundukça** karşı tarafa akıtılır (trickle = damla damla), böylece bağlantı çok daha hızlı kurulur. Modern tarayıcılar bunu kullanır.

### Doğru Kullanım ve Tuzaklar

- **STUN'suz WebRTC olmaz, TURN'süz olur (ama riskli).** STUN neredeyse her senaryoda gereklidir; TURN'ü atlamak bütçe tasarrufu sağlar ama katı ağlardaki kullanıcılar bağlanamaz. Üretim kalitesi için TURN şarttır.
- **Sinyalleşmeyi ICE ile karıştırmak.** Sık yapılan bir kavram hatası: "WebRTC sunucusuz çalışır" denir ama bu yanlıştır. Medya doğrudan akabilir, fakat iki tarafın birbirini **bulması** için mutlaka bir sinyalleşme kanalı (sunucu) gerekir; ayrıca çoğu zaman STUN/TURN sunucusu da gerekir.
- **IPv6 adaylarını unutmak.** İyi bir ICE dağıtımı hem IPv4 hem IPv6 adaylarını toplar; bu bağlanabilirliği artırır.

---

## Bölüm 6: WebRTC IP Leak (IP Sızıntısı) — Gizlilik Riski

### Tanım

**WebRTC IP leak**, bir web sayfasının, kullanıcının rızası olmadan JavaScript aracılığıyla kullanıcının **yerel ve/veya gerçek genel IP adresini** öğrenebilmesidir. Bu, WebRTC'nin bir hatası değil, **tasarımının doğal sonucudur**: ICE'nin işini yapabilmesi için aday adresleri toplaması ve bunları JavaScript'e görünür kılması gerekir.

### Kök Neden / Çalışma Mantığı

WebRTC bağlantısı kuran JavaScript, `RTCPeerConnection` nesnesi oluşturup bir STUN sunucusu tanımladığında, tarayıcı ICE aday toplama sürecini başlatır. Bu süreçte:

- **Host candidate** olarak cihazın **yerel ağ IP'si** (örneğin `192.168.x.x`) ortaya çıkar.
- **srflx candidate** olarak STUN ile öğrenilen **gerçek genel IP** ortaya çıkar.

Bu adaylar `onicecandidate` olayı ile JavaScript'e teslim edilir. Kötü niyetli bir sayfa, gerçek bir görüşme kurmak zorunda bile olmadan, sadece aday toplama sürecini tetikleyerek bu IP'leri okuyabilir.

**Neden VPN'i deler?** Kullanıcı bir VPN kullanıyor olsa bile, işletim sistemi seviyesinde WebRTC bazı yapılandırmalarda VPN dışındaki fiziksel arayüzden de aday toplayabilir. Sonuç: sayfa, VPN'in gizlediği **gerçek IP'yi** srflx aday olarak görebilir. Bu, VPN ile anonim kaldığını sanan kullanıcı için ciddi bir ifşa riskidir. (Modern tarayıcılar ve iyi yapılandırılmış VPN'ler bunu büyük ölçüde azalttı, ama risk yapılandırmaya bağlıdır.)

### Ek Bir Gizlilik Katmanı: mDNS ile Yerel IP Gizleme

Tarayıcılar bu riski azaltmak için bir savunma geliştirmiştir: **host candidate'lardaki yerel IP'yi, rastgele bir `.local` mDNS adına** (örneğin `a1b2c3d4-....local`) çevirmek. Böylece web sayfası artık `192.168.1.42` gibi gerçek yerel IP'yi göremez; sadece anlamsız bir mDNS ismi görür. Bu, WebRTC'nin çalışmasını bozmaz (aynı LAN'daki peer'lar bu ismi çözebilir) ama parmak izi (fingerprinting) için kullanılan yerel IP sızıntısını engeller. Bu davranış modern tarayıcılarda varsayılandır.

### Tespit (Detection)

Savunma perspektifinden, bir ortamda WebRTC IP sızıntısı olup olmadığını nasıl tespit edersiniz?

- **Kendi ortamınızı test etme**: Kontrol ettiğiniz bir test sayfasında `RTCPeerConnection` ile aday toplayıp, ortaya çıkan srflx adresinin beklenen (VPN) IP mi yoksa gerçek IP mi olduğunu gözlemleyin. IP sızıntısı test siteleri tam olarak bunu yapar.
- **Ağ/log tarafında**: Kurumsal bir ağda, beklenmedik STUN trafiği (klasik olarak **UDP 3478** portu, TURNS için **5349**) çıkışını izlemek, hangi uygulamaların WebRTC aday topladığını gösterir. Bu bir IDS/güvenlik izleme sinyali olabilir.
- **Tarayıcı yapılandırma denetimi**: Kurumsal cihazlarda tarayıcı politikalarının WebRTC IP işleme modunu nasıl ayarladığını denetlemek.

### Savunma (Defense)

- **Tarayıcı ayarı / eklenti**: Birçok tarayıcı, WebRTC'nin yalnızca varsayılan (public) arayüzü kullanmasını veya IP ifşasını kısıtlamasını sağlayan bir gizlilik ayarına ya da kurumsal politikaya sahiptir. VPN kullanıcıları için "WebRTC IP handling policy"yi kısıtlayıcı moda almak önemlidir.
- **VPN seçimi**: WebRTC sızıntısını kendi istemcisinde engelleyen (arayüz bağlaması yapan) VPN'ler tercih edilmeli.
- **WebRTC'yi tamamen kapatma**: Gerçek zamanlı iletişime ihtiyaç duymayan yüksek gizlilik gerektiren senaryolarda WebRTC tarayıcı düzeyinde devre dışı bırakılabilir — ama bu görüntülü görüşme sitelerini bozar, bir denge kararıdır.
- **mDNS varsayılanını koruma**: Yukarıda anlatılan `.local` mDNS gizlemesini devre dışı bırakan yapılandırmalardan kaçının.

### Yaygın Yanlış Anlamalar

- **"WebRTC bir güvenlik açığıdır."** Hayır — WebRTC'nin medya trafiği DTLS/SRTP ile **zorunlu olarak şifrelenir**; şifresiz WebRTC medyası yoktur. "Sızıntı" olan şey medya içeriği değil, **IP metadata**sıdır ve bu ICE'nin çalışması için gereklidir. Sorun protokolde değil, bunun gizlilik açısından farkında olmayan kullanıcıdadır.
- **"VPN kullanıyorum, güvendeyim."** VPN yapılandırması WebRTC'yi kapsamıyorsa gerçek IP yine sızabilir. Anonimlik iddiası, WebRTC testi yapılmadan güvenilir değildir.
- **"STUN sunucusuna güvenmem gerekmez."** STUN sunucusu sizin genel IP:port ikilinizi görür; medyayı görmez ama meta veriyi görür. TURN sunucusu ise (relay modunda) tüm trafiği taşıdığından ona daha fazla güven gerekir — bu yüzden kendi TURN sunucunuzu çalıştırmak gizlilik açısından anlamlıdır.

---

## Özet ve Kavramsal Harita

- **Unicast/Multicast/Anycast** trafiğin dağıtım modelidir. Multicast kontrollü ağlarda "bire çok", anycast internet ölçeğinde "en yakına yönlendirme" (CDN, DNS) sağlar; genel internette multicast pratik değildir.
- **WebRTC**, NAT arkasındaki iki tarafın doğrudan gerçek zamanlı medya alışverişini hedefler; asıl zorluk **NAT geçişi**dir.
- **STUN** ucuz bir aynadır: kendi genel adresini öğretir (`srflx`).
- **TURN** pahalı bir aktarıcıdır: doğrudan bağlantı imkânsızsa medyayı taşır (`relay`).
- **ICE** tüm adayları (host/srflx/relay) toplayıp deneyen ve en iyisini seçen çerçevedir; **host > srflx > relay** önceliğiyle çalışır.
- **WebRTC IP leak**, ICE'nin aday adresleri JavaScript'e açmasının doğal sonucudur; **mDNS gizleme**, kısıtlayıcı **IP handling policy** ve **WebRTC'yi kapsayan VPN** ile savunulur; **STUN trafiği izleme** ile tespit edilir.

Bu mimariyi anlamak, hem sağlam gerçek zamanlı uygulamalar kurmak hem de kullanıcı gizliliğini koruyan savunmalar tasarlamak için gereklidir.
