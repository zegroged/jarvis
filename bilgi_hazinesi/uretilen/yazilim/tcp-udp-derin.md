# TCP ve UDP Derinlemesine

Bu makale, internet üzerindeki neredeyse tüm veri iletişiminin dayandığı iki taşıma katmanı (transport layer) protokolünü — TCP ve UDP — mühendislik derinliğinde ele alır. Amaç ezber bir tanım listesi vermek değil; **neden** böyle tasarlandıklarını, **nasıl** çalıştıklarını ve gerçek sistemlerde hangi tuzaklara düşüldüğünü akıl yürüterek anlatmaktır. El sıkışma (handshake), akış (flow) ve tıkanıklık (congestion) kontrolü, UDP'nin doğru kullanım alanları ve modern QUIC protokolü ana eksenlerdir.

## Taşıma Katmanının Var Oluş Sebebi

Ağın altında IP (Internet Protocol) katmanı vardır ve IP'nin verdiği tek söz şudur: "Elimden geleni yaparım." IP paketleri kaybolabilir, sırası bozulabilir, çoğaltılabilir (duplicate) veya bozulabilir. IP, bir makineden diğerine (host-to-host) paket taşır ama bir makinedeki hangi uygulamaya gideceğini bilmez.

İşte taşıma katmanı tam da bu iki boşluğu doldurmak için vardır. Birincisi **çoğullama (multiplexing)**: port numaraları sayesinde aynı IP adresine gelen trafiği doğru uygulamaya (web sunucusu, veritabanı, DNS çözümleyicisi) yönlendirir. İkincisi ise **güvenilirlik seviyesi seçimi**. TCP güvenilir, sıralı bir bayt akışı (byte stream) sunar; UDP ise IP'nin üstüne neredeyse hiçbir şey eklemez, sadece port çoğullaması ve isteğe bağlı bir bütünlük kontrolü (checksum) getirir.

Bu ikilik tesadüf değildir. Bazı uygulamalar için "hiç kaybetme, sırasını koru" en önemli özelliktir; bazıları içinse "en güncel veriyi en hızlı ilet, gecikeni çöpe at" daha değerlidir. Tek bir protokol bu iki zıt ihtiyacı iyi karşılayamaz, bu yüzden iki farklı protokol vardır.

## TCP'nin Temel Modeli: Güvenilir Bayt Akışı

TCP'yi anlamanın anahtarı, onun bir **bağlantı yönelimli (connection-oriented)** ve **bayt akışı** soyutlaması sunduğunu kavramaktır. Uygulama TCP'ye bir yığın bayt yazar; TCP bunların karşı tarafa aynı sırayla, eksiksiz ve tekrarsız ulaşmasını garanti eder. Uygulama "mesaj" görmez, sürekli bir bayt dizisi görür. Bu yüzden TCP'de mesaj sınırları yoktur — gönderdiğiniz iki `write` çağrısı karşı tarafta tek `read` ile gelebilir. Bu, ilerideki "yaygın hatalar" bölümünün temelidir.

Bu garantileri sağlamak için TCP her baytı bir **sıra numarası (sequence number)** ile numaralar. Karşı taraf aldığı baytları **onay (acknowledgment, ACK)** numarası ile teyit eder: "Şu bayta kadar her şeyi aldım, sıradaki beklediğim şu." Kaybolan veri, ACK gelmeyince yeniden gönderilir (retransmission). Bütün TCP mekaniğinin altında bu sıra numarası / ACK muhasebesi yatar.

### Üçlü El Sıkışma (Three-Way Handshake)

TCP bağlantısı veri akmadan önce kurulmalıdır. Bunun sebebi yalnızca "merhaba demek" değil, **her iki tarafın başlangıç sıra numaralarını (Initial Sequence Number, ISN) birbirine bildirmesi ve birbirinin kendisini duyduğunu doğrulamasıdır.** İletişim çift yönlü olduğu için her yönün kendi sıra numarası uzayı vardır ve her iki taraf da kendi ISN'ini karşıya söyleyip onun onayını almalıdır.

Akış üç adımda ilerler:

1. **SYN**: İstemci, `SYN` bayrağı set edilmiş bir segment gönderir ve kendi başlangıç sıra numarasını (diyelim `x`) bildirir.
2. **SYN-ACK**: Sunucu hem istemcinin SYN'ini onaylar (`x+1` bekliyorum der) hem de kendi başlangıç sıra numarasını (`y`) bildirir.
3. **ACK**: İstemci sunucunun sıra numarasını onaylar (`y+1` bekliyorum der).

Neden iki değil de üç adım? Çünkü iki adım tek yönün doğrulanmasını sağlar. Üçüncü adım, sunucunun sıra numarasının da istemci tarafından alındığını teyit eder. Ayrıca başlangıç sıra numaralarının rastgele (randomized) seçilmesi önemlidir: tahmin edilebilir ISN'ler, saldırganın bağlantıya sahte segment enjekte etmesine (sequence prediction / spoofing) kapı açar. Modern yığınlar ISN'i güçlü bir biçimde rastgeleleştirir.

El sıkışma sırasında taraflar ayrıca **seçenekleri (options)** pazarlaşır: Maksimum Segment Boyutu (MSS), pencere ölçekleme (window scaling), seçici onay yeteneği (SACK), zaman damgaları (timestamps) gibi. Bu pazarlaşma, sonraki bölümlerdeki performans mekanizmalarının çalışabilmesi için gereklidir.

Bir mühendislik notu: Bu el sıkışma en az bir tam gidiş-dönüş süresi (Round-Trip Time, RTT) boyunca gecikme yaratır. Veri ancak üçüncü adımdan sonra (bazı iyileştirmelerle üçüncü ACK'e binmiş olarak) akmaya başlar. Bu bir RTT'lik kurulum maliyeti, TLS el sıkışmasıyla birleşince gecikmeye duyarlı uygulamalarda ciddi bir gider olur — QUIC'in doğuş sebeplerinden biri tam olarak budur.

### SYN Flood: El Sıkışmanın Kör Noktası

Üçlü el sıkışma güzel bir tasarımdır ama bir zayıflığı vardır. Sunucu ilk SYN'i alınca, yarı açık (half-open) bir bağlantı için kaynak ayırır ve SYN-ACK gönderip son ACK'i bekler. Bir saldırgan sahte kaynak adresleriyle binlerce SYN gönderip hiç ACK dönmezse, sunucunun yarı açık bağlantı kuyruğu dolar ve meşru bağlantılar reddedilmeye başlar. Buna **SYN flood** denir.

Klasik çözüm **SYN cookie** yaklaşımıdır: sunucu, yarı açık bağlantı için durum tutmak yerine, bağlantı durumunu ISN içine kriptografik olarak kodlar. Son ACK geldiğinde bu bilgi ACK numarasından geri çözülür. Böylece kuyruk tutmadan bağlantı doğrulanabilir. Bu, "durumu istemcinin geri getirmesini sağla" fikrinin zarif bir örneğidir; aynı fikir QUIC'in retry token mekanizmasında da yaşar.

### Bağlantı Kapatma ve TIME_WAIT

Kapatma da simetriktir: her yön bağımsız kapatılır. Bir taraf `FIN` gönderir, karşı taraf onu ACK'ler; sonra karşı taraf da kendi `FIN`'ini gönderir ve o da onaylanır. İki yön ayrı ayrı kapandığı için buna dört adımlı kapanış da denir (pratikte bazı adımlar birleşebilir).

Kapatan taraf `TIME_WAIT` durumunda bir süre (tipik olarak maksimum segment ömrünün iki katı, 2×MSL) bekler. Bunun **kök nedeni** iki tanedir: (1) son ACK kaybolursa karşı tarafın tekrar gönderdiği FIN'i yanıtlayabilmek, (2) bu bağlantıya ait gecikmiş eski segmentlerin, aynı port çiftiyle açılacak yeni bir bağlantıya karışmasını önlemek. `TIME_WAIT`, yoğun kısa bağlantı açan sunucularda port tükenmesine yol açabilir; bu yüzden bağlantı havuzlama (connection pooling) ve `keep-alive` bu kadar önemlidir.

## Akış Kontrolü (Flow Control): Alıcıyı Korumak

Akış kontrolü tek bir soruyu çözer: **Hızlı bir gönderici, yavaş bir alıcıyı ezmemeli.** Alıcının uygulaması veriyi yeterince hızlı okuyamıyorsa, alıcının tampon belleği (buffer) taşar ve veri düşer.

TCP bunu **kayan pencere (sliding window)** ile çözer. Alıcı her ACK'te bir **duyurulan pencere (advertised window / receive window, rwnd)** değeri bildirir: "Şu an tamponumda bu kadar boş yerim var, bundan fazlasını gönderme." Gönderici, onaylanmamış (in-flight) veri miktarını bu pencereyle sınırlar. Alıcı tamponu dolarsa pencereyi sıfır ilan eder ve gönderici durur; alan açılınca pencere güncellemesiyle akış yeniden başlar.

Burada iki klasik tuzak vardır. Birincisi **silly window syndrome**: alıcı çok küçük parçalar halinde yer açarsa, gönderici de minik segmentler gönderir ve başlık (header) yükü verimliliği öldürür. Çözüm, alıcının kayda değer bir yer açılana kadar küçük pencere güncellemeleri yapmaması ve göndericinin küçük segmentleri biriktirmesidir (bkz. Nagle algoritması). İkincisi, orijinal 16 bitlik pencere alanının yüksek bant genişliği × gecikme çarpımına (bandwidth-delay product) sahip yollar için çok küçük kalmasıdır; **pencere ölçekleme (window scaling)** seçeneği bu yüzden el sıkışmada pazarlaşılır.

Kritik ayrım şudur: akış kontrolü **alıcının** kapasitesini korur. Ama veri kaybının çoğu alıcıdan değil, ağın ortasındaki tıkanıklıktan kaynaklanır. Onu ayrı bir mekanizma çözer.

## Tıkanıklık Kontrolü (Congestion Control): Ağı Korumak

1980'lerin sonunda internet, "tıkanıklık çöküşü (congestion collapse)" denen bir olguyla karşılaştı: ağ doldukça paketler düşüyor, düşen paketler yeniden gönderiliyor, bu da ağı daha da dolduruyordu — bir kısır döngü. Çözüm, göndericilerin ağın doluluk durumuna göre kendini frenlemesiydi. Bu, TCP'nin en zarif ve en çok üzerinde çalışılan kısmıdır.

Temel fikir: TCP, ağın ne kadar veri taşıyabileceğini doğrudan bilemez, bu yüzden **deneyerek tahmin eder.** Gönderici, `rwnd`'ye ek olarak bir de **tıkanıklık penceresi (congestion window, cwnd)** tutar ve gerçek gönderim sınırı bu ikisinin küçüğüdür: `min(cwnd, rwnd)`. `cwnd`, ağdan gelen sinyallere göre büyür ve küçülür.

### Klasik Döngü: Slow Start ve Congestion Avoidance

**Slow start** ismi yanıltıcıdır; aslında hızlı büyür. Bağlantı küçük bir `cwnd` ile başlar ve her RTT'de pencereyi katlar (üstel büyüme). Amaç, ağın kapasitesini hızla yoklamaktır. Belirli bir eşiğe (`ssthresh`) ulaşınca **congestion avoidance** aşamasına geçilir: artık her RTT'de pencere yalnızca yaklaşık bir segment kadar artar (doğrusal büyüme). Böylece kapasiteye yaklaşırken ihtiyatlı davranılır.

Peki ağın dolduğunu TCP nereden anlar? Klasik yaklaşımda **paket kaybı bir tıkanıklık sinyalidir.** İki tür kayıp tepkisi vardır:

- **Zaman aşımı (timeout)**: ACK hiç gelmezse ciddi bir sorun var demektir; `cwnd` en aza indirilir ve slow start'a dönülür. Bu sert bir geri çekilmedir.
- **Üç yinelenen ACK (three duplicate ACKs)**: alıcı bir paketi kaçırdığında, sonraki paketleri alsa da hep aynı "beklediğim baytı" tekrarlar. Üç yinelenen ACK, "bir paket düştü ama akış devam ediyor" anlamına gelir. Gönderici o paketi hemen yeniden gönderir (**fast retransmit**) ve pencereyi ikiye böler ama sıfırlamaz (**fast recovery**). Bu daha yumuşak bir tepkidir.

Bu "yavaş büyü, kayıpta yarıya in" döngüsü klasik **AIMD** (Additive Increase, Multiplicative Decrease) davranışıdır ve testere dişi (sawtooth) grafiğini üretir. AIMD'nin matematiksel güzelliği, birden çok akışın aynı darboğazı **adil (fair)** biçimde paylaşmaya yakınsamasıdır: fazla alan geri çekildikçe, az alan büyür.

### Kayıp Tabanlı Kontrolün Zayıflığı ve Yeni Nesil

Kayba dayalı kontrolün bir kör noktası vardır: **büyük tamponlarla dolmuş ağlarda (bufferbloat)**, kayıp çok geç gelir. Paketler düşmeden önce ara yönlendiricilerin (router) kuyruklarında uzun süre bekler, gecikme fırlar ama TCP bunu "her şey yolunda" sanıp göndermeye devam eder. Sonuç: yüksek verim ama korkunç gecikme.

Bu yüzden modern tıkanıklık kontrolü sinyal olarak kaybın ötesine geçti:

- **Gecikme tabanlı yaklaşımlar** RTT'nin artmasını erken bir tıkanıklık işareti sayar (kuyruklar dolmaya başlayınca RTT artar).
- **ECN (Explicit Congestion Notification)**, yönlendiricilerin paketi düşürmek yerine "tıkanıklık başlıyor" diye işaretlemesine izin verir; TCP kayıp yaşamadan yavaşlar.
- Google'ın geliştirdiği **BBR** gibi model tabanlı yaklaşımlar, yolun bant genişliğini ve minimum RTT'sini aktif olarak ölçüp gönderim hızını buna göre ayarlar; kaybı ana sinyal olarak kullanmaz. Bu, bufferbloat'lu ve kayıplı yollarda klasik yaklaşımlardan belirgin biçimde iyi sonuç verebilir.

Buradaki mühendislik dersi önemlidir: tıkanıklık kontrolü tek bir "doğru" algoritma değildir; ağ koşullarına ve iş yüküne göre farklı ödünleşimler yapan bir algoritma ailesidir. İşletim sistemi hangi algoritmayı kullandığınıza göre performansınız dramatik değişebilir.

## UDP: Kasıtlı Sadelik

UDP'yi doğru anlamak için onu "eksik TCP" değil, "farklı bir felsefe" olarak görmek gerekir. UDP, IP'nin üstüne yalnızca dört şey ekler: kaynak portu, hedef portu, uzunluk ve bir checksum. El sıkışma yok, bağlantı durumu yok, ACK yok, yeniden gönderim yok, sıralama yok, akış/tıkanıklık kontrolü yok.

Bu eksiklikler kusur değil, **özellik**tir. UDP şöyle der: "Ben sana en ham datagram servisini veririm; güvenilirliği, sıralamayı, hızı senin ihtiyacına göre sen kur." Bu neden değerlidir?

**Birincisi, gecikme.** Bazı verilerin değeri zamanla hızla düşer. Bir sesli görüşmede 200 ms önce kaybolan bir ses paketini yeniden göndermek anlamsızdır — o an çoktan geçmiştir, yeniden gelen paket sadece gecikmeyi artırır. Bu tür uygulamalar için TCP'nin "her baytı garanti et, sırayı koru" ısrarı bir zarardır. **Head-of-line blocking** denen olgu tam da budur: TCP'de bir paket kaybolduğunda, ondan sonraki paketler alınmış olsa bile uygulamaya teslim edilmez, çünkü sıra bozulmamalıdır. Gerçek zamanlı medyada bu tolere edilemez.

**İkincisi, esneklik ve kontrol.** UDP üstüne kendi güvenilirlik mantığınızı kurabilirsiniz — sadece kritik mesajları yeniden gönderebilir, kendi sıralama şemanızı, kendi tıkanıklık kontrolünüzü uygulayabilirsiniz. Modern oyun ağ kodları ve QUIC tam olarak bunu yapar.

**Üçüncüsü, çok-alıcılı iletişim.** UDP, çoklu gönderim (multicast) ve yayın (broadcast) destekler; TCP'nin bağlantı modeli buna uygun değildir.

### UDP Nerede Doğru Seçimdir?

- **Gerçek zamanlı medya**: VoIP, video konferans, canlı yayın. Güncellik güvenilirlikten önemlidir.
- **Çevrimiçi oyunlar**: oyuncu konumu gibi durum güncellemeleri; eski bir konum güncellemesini yeniden göndermenin anlamı yoktur, en yenisi zaten geliyordur.
- **DNS**: tek istek/tek yanıt, küçük ve hızlı. TCP el sıkışma maliyeti burada orantısız olurdu (büyük yanıtlar veya bölge transferi için TCP'ye düşülür).
- **Telemetri ve loglama**: bazı ölçümlerin ara sıra kaybı kabul edilebilir; hız ve düşük yük daha önemlidir.
- **Yeni taşıma protokollerinin temeli**: QUIC, UDP üstünde çalışır.

### UDP Tuzakları

UDP'nin sadeliği, sorumluluğu uygulamaya yıkar ve buradan kaynaklanan hatalar yaygındır:

- **Güvenilirlik gerekiyorsa onu siz kurmalısınız.** "UDP hızlı, o zaman TCP yerine UDP kullanayım" diyip güvenilirlik gerektiren bir protokolü çıplak UDP üstüne kurmak, sonunda TCP'nin kötü bir kopyasını yeniden icat etmenize yol açar. Güvenilirlik gerçekten gerekiyorsa ya TCP kullanın ya da QUIC gibi işi hakkıyla yapmış bir katman seçin.
- **Tıkanıklık kontrolü yoktur.** Çıplak UDP ile agresif gönderim yaparsanız hem ağı boğar hem de kendinize zarar verirsiniz; TCP akışlarına karşı adaletsiz davranırsınız. Yüksek hacimli UDP kullanan her uygulama kendi tıkanıklık kontrolünü uygulamak zorundadır.
- **Datagram boyutu ve parçalanma (fragmentation).** Bir UDP datagramı yol boyunca izin verilen en küçük MTU'yu (Maximum Transmission Unit) aşarsa IP seviyesinde parçalanır; parçalardan biri düşerse tüm datagram kaybolur. Ayrıca birçok orta kutu (middlebox) IP parçalarını düşürür. Bu yüzden pratik UDP protokolleri datagramlarını güvenli bir boyut altında tutar ve yol MTU'sunu (Path MTU) keşfetmeye çalışır.
- **NAT ve durum zaman aşımı.** UDP bağlantısız olduğu için NAT cihazları eşlemeleri (mapping) kısa süre sonra düşürebilir. Uzun ömürlü UDP akışları düzenli "keep-alive" paketleri göndermezse sessiz kalınca kopar.
- **Checksum'ı atlamak.** IPv4'te UDP checksum'ı teknik olarak isteğe bağlıdır ama kapatmak, bozuk verinin fark edilmeden uygulamaya ulaşmasına yol açar. Kapatmayın.

## QUIC: UDP Üstünde Modern Bir Taşıma

QUIC, TCP'nin onlarca yıllık birikmiş kısıtlarını aşmak için tasarlanmış, UDP üzerinde çalışan modern bir taşıma protokolüdür ve HTTP/3'ün temelidir. Neden UDP üstünde? Çünkü TCP çekirdek işletim sistemine gömülüdür ve yavaş evrilir; ayrıca ağdaki orta kutular yalnızca TCP ve UDP'yi iyi geçirir, yeni bir IP protokol numarasını çoğu yerde geçiremezsiniz. UDP üstünde çalışarak QUIC, hem her yerde geçebilir hem de mantığını kullanıcı alanında (user space) tutup hızla güncellenebilir.

QUIC'in çözdüğü asıl problemleri anlamak, onu değerli kılar:

### 1. El Sıkışma Gecikmesini Birleştirmek

Klasik HTTPS'te önce TCP el sıkışması (bir RTT), sonra TLS el sıkışması (ek RTT'ler) yapılır. QUIC, taşıma ve kriptografik el sıkışmayı **birleştirir**; TLS 1.3'ü doğrudan içine gömer. Böylece güvenli bir bağlantı klasik yığından belirgin biçimde az gidiş-dönüşte kurulur. Dahası, daha önce konuşulmuş bir sunucuya **0-RTT** ile, ilk pakette veri göndererek bağlanmak mümkündür (bunun bir yeniden oynatma / replay riski taşıdığını ve yalnızca idempotent isteklerde güvenli olduğunu belirtmek gerekir).

### 2. Head-of-Line Blocking'i Gerçekten Çözmek

HTTP/2, tek bir TCP bağlantısı üstünde birçok mantıksal akışı (stream) çoğullardı. Ama altta TCP olduğu için, o tek bağlantıda **bir paket kaybolduğunda tüm akışlar dururdu** — TCP baytların sırasını global olarak korumak zorundadır. Bu, taşıma seviyesindeki head-of-line blocking'dir.

QUIC bunu kökten çözer: akışları taşıma protokolünün **kendisi** bilir. Her akışın kendi sıralaması vardır; bir akıştaki paket kaybı yalnızca o akışı bekletir, diğerleri akmaya devam eder. Bu, çoklu istek indiren bir web sayfası için gerçek bir kazançtır. Kayıp koşullarında QUIC'in HTTP/2 üzerindeki avantajının çoğu buradan gelir.

### 3. Bağlantı Göçü (Connection Migration)

TCP bağlantısı dört değerle tanımlanır: kaynak IP, kaynak port, hedef IP, hedef port. Telefonunuz Wi-Fi'dan mobil veriye geçince IP adresiniz değişir ve TCP bağlantısı ölür. QUIC ise bağlantıyı IP/port çiftine değil, kriptografik bir **bağlantı kimliğine (Connection ID)** bağlar. Ağınız değişse bile bağlantı yaşamaya devam edebilir. Mobil çağında bu büyük bir kullanıcı deneyimi kazancıdır.

### QUIC'in Getirdiği Ödünleşimler

QUIC bedava değildir. Tüm işi (şifreleme, paket işleme) kullanıcı alanında yaptığı için ve TCP kadar yıllarca donanım/çekirdek düzeyinde optimize edilmediği için, çok yüksek hacimlerde **CPU maliyeti** TCP'den fazla olabilir. Paketlerin çoğunun şifreli olması ağ operatörlerinin görünürlüğünü azaltır (bu bir gizlilik kazancı ama teşhis zorluğu). Ayrıca bazı ağlar UDP trafiğini kısıtlar ya da bloke eder; bu yüzden istemciler genellikle QUIC başarısız olursa TCP'ye geri düşen (fallback) bir mantık taşır.

Yine de dikkat çeken şey şudur: QUIC, aslında TCP'nin öğrettiği her dersi (sıra numaraları, ACK, tıkanıklık kontrolü, akış kontrolü) alıp UDP üstünde, modern ihtiyaçlara göre yeniden kurar. Yani UDP'nin "güvenilirliği sen kur" felsefesinin en olgun meyvesidir. TCP ile UDP arasındaki eski ikilem, QUIC ile "her ikisinin de iyi yanlarını UDP üstünde birleştir" biçiminde aşılmaya çalışılmıştır.

## Uygulama Katmanında Yaygın Hatalar ve En İyi Pratikler

Protokol iç mekaniğini bilmek, gündelik hataların çoğunu açıklar. En sık görülenler:

**TCP'yi mesaj yönelimli sanmak.** En yaygın acemi hatası budur. TCP bir bayt akışıdır; `send` çağrılarınızla `recv` çağrıları birebir eşleşmez. Bir mesajı tam okuduğunuzu varsaymak (kısmi okuma / partial read hatası) veya iki mesajın birleşmesi (message framing eksikliği) bozuk protokollere yol açar. Çözüm: uzunluk ön eki (length-prefixing) veya bir ayraç (delimiter) ile mesaj sınırlarını **siz** tanımlayın.

**Nagle algoritması ile gecikme sürprizi.** Nagle, küçük TCP segmentlerini biriktirip verimi artırmak için tasarlanmıştır ama gecikmeye duyarlı, küçük istek/yanıt trafiğinde (özellikle gecikmeli ACK ile birleşince) beklenmedik takılmalara yol açabilir. İnteraktif protokollerde Nagle'ı kapatmak (TCP_NODELAY benzeri seçenek) sık gerekir — ama körlemesine değil, ölçerek.

**Kaybı gecikme yerine hız sanmak.** "İnternetim yavaş" şikayetlerinin çoğu bant genişliği değil, tıkanıklık ve bufferbloat kaynaklı gecikmedir. Doğru teşhis için verimi (throughput) ve gecikmeyi (latency) ayrı ölçmek gerekir.

**UDP ile güvenilirliği yarım yamalak yeniden icat etmek.** Yukarıda değinildi: gerçekten güvenilirlik gerekiyorsa hazır ve olgun bir çözüm (TCP veya QUIC) seçin.

**Zaman aşımı ve yeniden gönderim ayarlarını sabit kodlamak.** RTT ağa göre çok değişir; iyi protokoller RTT'yi ölçüp uyarlar (adaptive timeout). Sabit bir zaman aşımı ya çok erken tetiklenir (gereksiz yeniden gönderim) ya çok geç (kötü tepki süresi).

Genel en iyi pratikler şöyle özetlenebilir:

- **Doğru aracı seç.** Sıralı, güvenilir, hacimli veri → TCP. Gecikmeye duyarlı, kayba toleranslı → UDP. Modern, çoklu akışlı, güvenli web trafiği ve mobilite → QUIC/HTTP/3.
- **Bağlantı kurma maliyetini hafife alma.** El sıkışma + TLS bir RTT'ler toplamıdır. Bağlantı havuzlama, `keep-alive` ve mümkünse oturum sürdürme (session resumption) kullan.
- **Tampon boyutlarını ve pencere ölçeklemeyi bilinçli ayarla.** Yüksek bant genişliği × gecikme çarpımına sahip yollarda pencere ölçekleme olmadan tam hıza ulaşamazsın.
- **Ölçmeden ayar (tuning) yapma.** TCP_NODELAY, tampon boyutları, tıkanıklık algoritması seçimi — hepsi iş yüküne bağlıdır. Varsayımla değil, gerçek ağda ölçerek karar ver.
- **Güvenlik açısından el sıkışmayı ve durum yönetimini ciddiye al.** SYN flood'a karşı korumaları (SYN cookie), rastgele ISN'i ve UDP tarafında amplifikasyon saldırılarına karşı önlemleri (yanıtı istek boyutuyla sınırlama, adres doğrulama) uygula.

## Kapanış

TCP ve UDP, aynı ihtiyacın iki zıt ucudur: biri güvenilirlik ve sırayı, diğeri gecikme ve esnekliği önceler. TCP'nin el sıkışması, akış kontrolü ve tıkanıklık kontrolü, "güvenilir bir bayt akışını, adil paylaşılan bir ağ üzerinde nasıl taşırım" sorusunun onlarca yıllık cevabıdır. UDP ise bu cevabı dayatmayı reddederek, güvenilirliği uygulamanın ihtiyacına göre kurmaya alan açar. QUIC, bu iki dünyayı UDP üstünde birleştirerek TCP'nin çekirdeğe gömülü kalmasından doğan sorunları aşar ve modern web'in taşıma katmanı haline gelir.

Bu mekanizmaların hepsinin ortak dersi aynıdır: ağda hiçbir garanti bedava değildir; her garanti bir gecikme, karmaşıklık veya kaynak maliyetiyle gelir. İyi bir sistem mühendisi, hangi garantiye gerçekten ihtiyacı olduğunu bilir ve gerisini ölçerek karar verir.
