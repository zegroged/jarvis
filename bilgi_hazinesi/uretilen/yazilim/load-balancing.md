# Load Balancing (Yük Dengeleme)

## Tanım

Load balancing, gelen ağ trafiğini veya iş yükünü birden fazla sunucu (backend, upstream) arasında dağıtan bir tekniktir. Amacı; tek bir sunucunun aşırı yüklenmesini önlemek, sistemin toplam işlem kapasitesini (throughput) artırmak, gecikmeyi (latency) düşürmek ve bir sunucu çökse bile hizmetin ayakta kalmasını (high availability) sağlamaktır. Bu işi yapan bileşene **load balancer** denir ve mimaride istemci ile sunucu havuzu arasında oturur.

Load balancer'ı basitçe bir "akıllı trafik polisi" gibi düşünebilirsiniz: gelen her isteğe bakar, o an hangi sunucunun uygun olduğuna karar verir ve isteği oraya yönlendirir. Ancak bu basit görünen kararın arkasında; hangi katmanda çalıştığı (L4 mü L7 mi), hangi algoritmayı kullandığı, sunucuların sağlığını nasıl takip ettiği ve bir kullanıcının hep aynı sunucuya gidip gitmemesi gerektiği gibi kritik tasarım tercihleri vardır. Bu makale bu tercihleri ve altlarındaki "neden"leri açıklar.

## Kök Neden: Load Balancing'e Neden İhtiyaç Duyarız?

Load balancing bir lüks değil, ölçeklenmenin (scaling) doğal bir sonucudur. Tek sunucunun iki temel sınırı vardır:

1. **Dikey ölçeklenmenin bir tavanı vardır.** Bir sunucuya daha fazla CPU, RAM eklemek (vertical scaling) belli bir noktaya kadar işe yarar; ama donanımın fiziksel sınırı, maliyetin katlanarak artması ve tek bir makinenin hâlâ **tek arıza noktası** (single point of failure) olması bu yolu tıkar.

2. **Tek sunucu, tek arıza noktasıdır.** O makine çökerse, kernel panic yaşarsa veya bakım için kapatılırsa tüm hizmet durur.

Çözüm yatay ölçeklenmedir (horizontal scaling): aynı işi yapan çok sayıda ucuz sunucu koymak. Fakat bu, "kullanıcı isteği bu sunuculardan hangisine gitsin?" sorusunu doğurur. İşte load balancer bu sorunun cevabıdır. Yani load balancer, yatay ölçeklenmeyi mümkün kılan tutkaldır. Onun sayesinde istemciler tek bir sanal adres (VIP - Virtual IP) veya tek bir DNS ismi görür; arkadaki onlarca sunucunun varlığından habersizdir. Sunucu ekleyip çıkarmak (elastic scaling), bakıma alıp geri koymak, istemciyi hiç etkilemeden yapılabilir hâle gelir.

## L4 ve L7 Yük Dengeleme: Katman Farkı Neden Önemli?

Load balancer'lar OSI modelinde hangi katmanda karar verdiklerine göre ikiye ayrılır. Bu ayrım akademik bir detay değildir; performans, esneklik ve maliyet arasındaki temel dengeyi (trade-off) belirler.

### L4 (Transport Layer) Yük Dengeleme

L4 load balancer, TCP/UDP seviyesinde çalışır. Karar verirken yalnızca IP adreslerine ve port numaralarına bakar. Paketin **içine bakmaz**; HTTP header'ını, URL'i, cookie'yi görmez, göremez de.

**Nasıl çalışır?** İki temel yöntem vardır:

- **NAT (Network Address Translation) tabanlı:** Load balancer, gelen paketin hedef IP'sini seçtiği backend'in IP'siyle değiştirir. Bir bağlantı için ilk paket geldiğinde bir backend seçer ve bu eşleştirmeyi bir **connection table**'da tutar; aynı bağlantının sonraki paketleri hep aynı backend'e gider. Dönüş trafiği de load balancer üzerinden geçer.
- **DSR (Direct Server Return):** Load balancer isteği backend'e yönlendirir ama backend'in cevabı load balancer'a uğramadan doğrudan istemciye gider. Bu, load balancer'ın dönüş trafiği yükünü ortadan kaldırır ve çok yüksek throughput sağlar; özellikle cevap boyutunun istek boyutundan çok büyük olduğu (video, dosya indirme) senaryolarda değerlidir.

**Neden hızlıdır?** Çünkü çok az iş yapar. Paketin uygulama içeriğini parse etmez, TLS'i çözmez, sadece başlık bilgisine bakıp yönlendirir. Bu yüzden çok düşük gecikmeyle, milyonlarca bağlantıyı işleyebilir. Modern L4 dengeleyiciler (örneğin XDP/eBPF tabanlı çözümler veya donanım) çok yüksek paket işleme hızlarına ulaşır.

**Sınırı nedir?** İçeriği görmediği için içeriğe göre karar veremez. `/api` isteklerini bir gruba, `/images` isteklerini başka bir gruba gönderemez; çünkü URL'in ne olduğunu bilmez.

### L7 (Application Layer) Yük Dengeleme

L7 load balancer, uygulama katmanında (genellikle HTTP/HTTPS, gRPC) çalışır. İsteğin tamamını okur: URL yolunu (path), HTTP metodunu, header'ları, cookie'leri, hatta gerekirse body'yi görür.

**Nasıl çalışır?** L7 dengeleyici tipik olarak bir **full proxy** gibi davranır. İstemciyle kendi arasında bir TCP bağlantısı kurar (ve genelde TLS'i burada sonlandırır — TLS termination), isteği tamamen alır, anlar, sonra backend'e **kendisi yeni bir bağlantı** açarak isteği iletir. Yani istemci load balancer'la, load balancer da backend'le ayrı ayrı konuşur. Bu, iki bağlantının özelliklerinin (örneğin istemci HTTP/2, backend HTTP/1.1) farklı olmasına bile izin verir.

**Neyi mümkün kılar?** İçeriği gördüğü için çok daha zeki kararlar verebilir:

- **Content-based routing:** `/api/*` isteklerini API sunucularına, `/static/*` isteklerini statik içerik sunucularına yönlendirmek.
- **Header/cookie tabanlı yönlendirme:** A/B testleri, canary deployment (trafiğin %5'ini yeni sürüme yönlendirme), belli kullanıcıları belli backend'lere gönderme.
- **TLS termination:** Şifre çözmeyi merkezileştirip backend'leri bu yükten kurtarma.
- **İstek/cevap manipülasyonu:** Header ekleme/silme, compression, response caching, rate limiting, Web Application Firewall (WAF) entegrasyonu.

**Bedeli nedir?** Tüm bu iş CPU ve gecikme maliyeti getirir. Her isteğin parse edilmesi, TLS'in çözülmesi, tampon (buffer) yönetimi ek yük yaratır. Bu yüzden L7, L4'e göre daha ağırdır — ama sağladığı esneklik çoğu web uygulaması için bu bedeli fazlasıyla değer kılar.

**Pratik gerçek:** Modern mimarilerde ikisi birlikte kullanılır. Örneğin trafiğin ilk girişinde çok hızlı bir L4 katmanı (kaba dağıtım ve DDoS emme), onun arkasında akıllı yönlendirme yapan bir L7 katmanı bulunur. Bu iki katmanlı yaklaşım hem ölçek hem esneklik verir.

## Yük Dengeleme Algoritmaları

Load balancer'ın kalbindeki soru şudur: "Bir sonraki isteği hangi backend'e vereyim?" Bu kararı veren mantığa algoritma denir. Yanlış algoritma seçimi, sunucular boşta dururken bazılarının boğulmasına yol açabilir. Algoritmalar iki büyük aileye ayrılır: **statik** (sunucunun anlık durumuna bakmayan) ve **dinamik** (bakan).

### Round Robin

En basit statik algoritma. İstekleri sırayla sunuculara dağıtır: 1, 2, 3, 1, 2, 3... Basit ve öngörülebilirdir.

**Neden çalışır?** Sunucuların kapasitesi benzer ve istekler benzer maliyette ise, yük doğal olarak eşitlenir. **Ne zaman yetersiz kalır?** İstekler farklı maliyetteyse (biri 2 ms sürerken diğeri 5 saniye süren bir raporsa) round robin bunu göremez; bir sunucuya art arda ağır istekler denk gelebilir ve o sunucu ezilirken diğerleri boşta kalabilir.

### Weighted Round Robin

Sunucuların farklı kapasitede olduğu durumu çözer. Her sunucuya bir ağırlık (weight) verilir; güçlü sunucu daha fazla istek alır. Örneğin ağırlıkları 3 ve 1 olan iki sunucudan birincisi üç kat daha fazla trafik çeker. Heterojen (farklı donanımlı) havuzlarda mantıklıdır.

### Least Connections (En Az Bağlantı)

İlk dinamik algoritma. İsteği, o an **en az aktif bağlantısı olan** sunucuya gönderir.

**Kök mantık:** Aktif bağlantı sayısı, bir sunucunun ne kadar meşgul olduğunun kaba ama iyi bir göstergesidir. Uzun süren bağlantıların olduğu (örneğin WebSocket, uzun HTTP istekleri) ve isteklerin maliyetinin değişken olduğu sistemlerde round robin'den çok daha iyidir; çünkü yavaş sunucuda bağlantılar birikir, algoritma da otomatik olarak oraya daha az yeni istek gönderir. Bunun ağırlıklı versiyonu (**Weighted Least Connections**) de vardır.

### Least Response Time / Least Load

Least connections'ın bir adım ötesi. Sadece bağlantı sayısına değil, sunucunun ölçülen cevap süresine (response time) veya başka bir yük metriğine de bakar. En hızlı cevap veren, en az yüklü sunucuyu tercih eder. Daha akıllıdır ama sunucu sağlık/performans verisini sürekli toplamayı gerektirir.

### Hash Tabanlı (IP Hash / Consistent Hashing)

Bu aile, "aynı girdi hep aynı sunucuya gitsin" ihtiyacı için vardır. Bir anahtar (genellikle istemci IP'si, bazen URL veya bir header) üzerinden bir hash hesaplanır ve bu hash bir sunucuya eşlenir. Aynı istemci hep aynı sunucuya düşer.

**Neden değerli?** İki sebeple: (1) session affinity'yi (aşağıda anlatılacak) sunucu tarafında ekstra bir şey tutmadan sağlar; (2) cache verimliliği. Örneğin bir CDN veya cache katmanında, aynı URL'in hep aynı sunucuya gitmesi o sunucunun cache'inin sıcak (hit oranı yüksek) kalmasını sağlar.

**Kritik problem ve çözümü — Consistent Hashing:** Basit `hash(IP) mod N` yönteminde bir sorun vardır. Sunucu sayısı N değişirse (bir sunucu eklenir ya da çıkarılırsa), mod işleminin sonucu neredeyse tüm anahtarlar için değişir; yani **neredeyse tüm istemciler yeni sunuculara yeniden dağılır**. Cache açısından bu bir felakettir: tüm cache'ler bir anda geçersiz olur (cache stampede). **Consistent hashing** bu sorunu çözer: sunucuları ve anahtarları sanal bir çember (hash ring) üzerine yerleştirir. Bir sunucu eklenir/çıkarılırsa yalnızca çemberde ona komşu olan küçük bir anahtar dilimi yeniden dağılır, geri kalan her şey yerinde kalır. Bu yüzden dağıtık cache, sharding ve büyük ölçekli sistemlerde tercih edilen yöntem consistent hashing'dir.

### Power of Two Choices (P2C)

Zarif ve pratik bir dinamik algoritma. Tüm sunuculara bakıp en iyisini seçmek (least connections'ın küresel versiyonu) büyük havuzlarda pahalıdır ve dağıtık dengeleyicilerde koordinasyon gerektirir. P2C bunun yerine **rastgele iki sunucu seçer ve bu ikisinden az yüklü olanı** kullanır. Matematiksel olarak şaşırtıcı bir sonuç verir: sadece iki rastgele seçim, tamamen rastgele dağıtıma göre en yüklü sunucudaki yığılmayı üssel olarak (exponential'dan logaritmik'e) azaltır. Düşük maliyetli ama neredeyse "en iyi seçim" kadar iyi sonuç verdiği için modern dengeleyicilerde çok sevilir.

## Health Check (Sağlık Kontrolü): Ölü Sunucuya Trafik Göndermemek

Load balancing'in en kritik ama en çok ihmal edilen parçası budur. En akıllı algoritma bile, isteği çökmüş bir sunucuya gönderirse hiçbir işe yaramaz. Load balancer'ın hangi backend'lerin sağlıklı (canlı ve hizmet verebilir) olduğunu **sürekli** bilmesi gerekir. İşte bunu health check sağlar.

### Active (Aktif) Health Check

Load balancer, belirli aralıklarla backend'lere kendisi bir yoklama (probe) gönderir ve cevabı denetler. Üç seviyede yapılabilir:

- **L3 (ping):** Sunucu ağ üzerinde erişilebilir mi? En kaba kontrol.
- **L4 (TCP connect):** Belirtilen porta TCP bağlantısı açılabiliyor mu? Servis en azından dinliyor mu?
- **L7 (uygulama seviyesi):** En değerlisi. Örneğin `/health` veya `/healthz` gibi bir endpoint'e HTTP isteği atılır ve **200 OK** dönüp dönmediğine, hatta cevap gövdesinin beklenen içeriği taşıyıp taşımadığına bakılır.

**Neden L7 health check kritiktir?** Çünkü bir sunucu TCP portunu açık tutuyor (yani L4 sağlıklı görünüyor) ama arkadaki veritabanı bağlantısı kopmuş, uygulaması exception fırlatıyor olabilir. L4 kontrolü bu "yaşayan ölü" (zombie) sunucuyu sağlıklı sanır ve trafik göndermeye devam eder. İyi tasarlanmış bir `/health` endpoint'i, kritik bağımlılıkları (veritabanı, cache, disk) kontrol ederek gerçek sağlığı yansıtır.

### Passive (Pasif) Health Check

Ayrı bir probe göndermek yerine, **gerçek kullanıcı trafiğinin sonuçlarını gözlemler**. Bir backend art arda hata dönüyorsa (5xx), timeout veriyorsa veya bağlantı reddediyorsa, load balancer onu otomatik olarak havuzdan çıkarır (bu mekanizmaya bazı sistemlerde **outlier detection** denir). Avantajı: ekstra probe yükü yaratmaz ve gerçek trafikteki sorunları yakalar. Dezavantajı: sorunu ancak birkaç gerçek kullanıcı isteği başarısız olduktan **sonra** fark eder.

En sağlam yaklaşım ikisini birleştirmektir: pasif kontrol sunucuyu hızla devre dışı bırakır, aktif kontrol ise iyileşip iyileşmediğini test edip geri alır.

### İyi Health Check Tasarımının İncelikleri

- **Eşik (threshold) kullanın.** Tek bir başarısız kontrolde sunucuyu atmak "flapping"e (sunucunun sürekli girip çıkması) yol açar. Genellikle "art arda 3 başarısızlıkta çıkar, art arda 2 başarıda geri al" gibi eşikler kullanılır.
- **Aralık (interval) ve timeout dengesi.** Çok sık kontrol backend'e gereksiz yük bindirir; çok seyrek kontrol arızayı geç fark eder. Timeout ise gerçekçi olmalı — yavaş cevabı arıza sanmamalı.
- **Graceful shutdown / connection draining.** Bir sunucu bakıma alınacaksa, health check'i başarısız yapıp yeni trafik almasını durdurun; ama **mevcut aktif bağlantıların bitmesini bekleyin** (draining). Bağlantıları anında kesmek, o an işlem yapan kullanıcıların hata almasına yol açar.

## Sticky Session (Session Affinity): Aynı Kullanıcıyı Aynı Sunucuda Tutmak

Sticky session (ya da session affinity), belli bir istemcinin isteklerinin **hep aynı backend sunucuya** yönlendirilmesini sağlayan mekanizmadır. Adı "yapışkan" oturumdur çünkü kullanıcı bir sunucuya "yapışır".

### Kök Neden: Neden Buna İhtiyaç Doğar?

İhtiyaç, **stateful** (durum tutan) uygulamalardan doğar. Diyelim ki bir web uygulaması kullanıcının oturum bilgisini (login durumu, alışveriş sepeti) sunucunun kendi RAM'inde tutuyor. Kullanıcı ilk istekte 1 numaralı sunucuya düştü ve orada bir session oluştu. İkinci isteği round robin yüzünden 2 numaralı sunucuya giderse, o sunucu kullanıcıyı tanımaz — kullanıcı aniden logout olmuş görünür veya sepeti boşalır. Sticky session bunu engeller: kullanıcı hep 1 numaralı sunucuya gider, session'ı orada bütünlüğünü korur.

### Nasıl Uygulanır?

- **Cookie tabanlı (L7):** Load balancer, ilk cevaba özel bir cookie enjekte eder (örneğin backend'i işaret eden bir tanımlayıcı). Sonraki isteklerde bu cookie'ye bakarak kullanıcıyı aynı sunucuya yönlendirir. En yaygın ve en güvenilir yöntemdir; NAT arkasındaki farklı kullanıcıları da doğru ayırt eder.
- **IP hash tabanlı (L4):** İstemci IP'sinin hash'i sunucuyu belirler. Cookie gerektirmez ama sorunludur: kurumsal NAT veya mobil operatör arkasındaki binlerce kullanıcı tek IP'den geldiği için hepsi aynı sunucuya yığılabilir; ayrıca kullanıcının IP'si değişirse affinity kopar.

### Sticky Session'ın Gizli Tehlikeleri

Sticky session pratik bir çözüm gibi görünür ama önemli sakıncaları vardır ve bir "kod kokusu" (anti-pattern) işareti olabilir:

1. **Yük dengesizliği.** Trafik artık serbestçe dağıtılamaz; bir sunucuya bağlı kullanıcılar orada kalmak zorundadır. Uzun oturumlar bazı sunucuları aşırı yükleyip diğerlerini boş bırakabilir.
2. **Zayıf failover.** Kullanıcının yapıştığı sunucu çökerse, o session'daki tüm veri (RAM'de tutulduğu için) kaybolur; kullanıcı yeni sunucuda sıfırdan başlar. Yani sticky session, yüksek erişilebilirliği kısmen baltalar.
3. **Ölçeklenme sürtünmesi.** Yeni sunucu ekleyince mevcut yapışık kullanıcılar dağılmaz; yeni sunucu sadece yeni kullanıcıları alır, yük hemen eşitlenmez.

### Doğru Yaklaşım: Stateless Mimari

Bu yüzden modern en iyi pratik, sticky session'a **muhtaç olmamaktır**. Session durumunu sunucunun RAM'inden çıkarıp paylaşılan bir dış katmana taşımak — örneğin Redis/Memcached gibi bir dağıtık cache veya bir veritabanına koymak, ya da durumu istemcideki imzalı/şifreli bir token'da (örneğin JWT tabanlı) tutmak. Böylece **her sunucu her isteği işleyebilir** hâle gelir (stateless). Bu durumda load balancer isteği herhangi bir sunucuya özgürce dağıtabilir; failover sorunsuz olur, ölçeklenme temiz çalışır. Sticky session'ı ancak bu dönüşümü yapamadığınız eski (legacy) sistemler için bir köprü çözüm olarak görün.

## Yaygın Hatalar

- **Health check'i L4'te bırakmak.** Sadece TCP porta bakıp uygulama sağlığını kontrol etmemek, zombie sunuculara trafik göndermeye devam etmenin en yaygın nedenidir.
- **Round robin'i her yere uygulamak.** İstek maliyetleri değişkense veya uzun bağlantılar varsa, körü körüne round robin dengesizlik yaratır; least connections daha uygundur.
- **Sticky session'ı stateless mimari yerine kullanmak.** Uygulamayı stateless yapmaktan kaçınıp her şeyi affinity'ye yaslamak, ileride failover ve ölçeklenme sorunlarını garantiler.
- **`hash mod N` ile cache dağıtmak.** Consistent hashing yerine basit mod kullanmak, her sunucu değişiminde tüm cache'in çökmesine yol açar.
- **Connection draining'i unutmak.** Deploy sırasında sunucuları aniden kapatmak, o an işlenen istekleri hataya düşürür ve kullanıcı deneyimini bozar.
- **Load balancer'ı tek nokta yapmak.** Load balancer'ın kendisi de yedeklenmezse (active-passive veya active-active ikili, VRRP/floating IP, anycast) o kendisi bir single point of failure olur. Trafiği dağıtan bileşenin kendisi çökerse tüm sistem çöker.
- **Timeout ve retry ayarlarını körlemesine yapmak.** Çok agresif retry, zaten zorlanan bir backend'e "retry storm" bindirip çöküşü hızlandırabilir.

## En İyi Pratikler

- **Doğru katmanı seçin, gerekiyorsa ikisini birlikte kullanın.** Ham hız ve basit yönlendirme için L4; içeriğe göre yönlendirme, TLS termination ve akıllı kararlar için L7. Büyük sistemlerde önce L4 sonra L7 katmanlaması yaygındır.
- **Algoritmayı iş yükünüze göre seçin.** Homojen ve kısa istekler için round robin; değişken maliyet ve uzun bağlantılar için least connections; cache/sharding için consistent hashing; büyük havuzlarda ucuz ama etkili denge için power of two choices.
- **Anlamlı, uygulama seviyesinde health check yazın.** `/health` endpoint'i kritik bağımlılıkları gerçekten kontrol etsin; eşik değerleriyle flapping'i önleyin; aktif ve pasif kontrolü birlikte kullanın.
- **Uygulamalarınızı stateless yapmaya çalışın.** Session'ı paylaşılan bir cache'e veya token'a taşıyıp sticky session bağımlılığını ortadan kaldırın. Bu, ölçeklenme ve dayanıklılığın (resilience) temelidir.
- **Load balancer'ın kendisini yedekleyin.** Yüksek erişilebilirlik için ikili (redundant) load balancer kurgusu ve otomatik failover (floating IP, anycast, sağlık takipli DNS) kullanın.
- **Deploy'larda draining uygulayın.** Sunucuyu havuzdan zarif biçimde çıkarın, aktif bağlantıların bitmesini bekleyin, sonra durdurun.
- **Gözlemleyin (observability).** Sunucu başına istek dağılımı, hata oranları, gecikme yüzdelikleri (p50/p95/p99), aktif bağlantı sayıları ve health check durumları sürekli izlenmeli. Dengesizliği ancak ölçerek görebilirsiniz.

## Kapanış

Load balancing özünde tek bir soruyu iyi cevaplama sanatıdır: "Bu isteği hangi sağlıklı sunucuya, sistemi en dengeli tutacak şekilde göndermeliyim?" Bu sorunun cevabı; hangi katmanda çalıştığınıza (L4/L7), seçtiğiniz algoritmaya, sunucu sağlığını ne kadar dürüst ölçtüğünüze (health check) ve uygulamanızın durumu nerede tuttuğuna (sticky session'a mahkûm mu, stateless mi) bağlıdır. Bu dört ekseni doğru kurgulayan bir sistem; hem yüksek trafik altında dengeli kalır, hem sunucular çökse bile ayakta durur, hem de yeni sunucu eklendiğinde sorunsuzca büyür. Kötü kurgulayan sistem ise trafiği "dağıtır" ama dengelemez — ve genellikle en kötü anda, en yüksek yükte çöker.
