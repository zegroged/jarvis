# Nmap ve Tarama Metodolojisi

Nmap (Network Mapper), bir ağdaki canlı sistemleri, açık portları, çalışan servisleri ve işletim sistemlerini keşfetmek için kullanılan, siber güvenliğin en temel araçlarından biridir. Bir sızma testinin (penetration test) ya da kırmızı takım (red team) operasyonunun neredeyse tamamı, karşımızdaki hedefi tanımadan başlamaz; işte Nmap bu "tanıma" (reconnaissance) aşamasının bel kemiğidir. Ancak Nmap'i gerçekten anlamak, komut satırına birkaç bayrak eklemekten çok daha fazlasını gerektirir. Aracın her davranışının altında TCP/IP protokol yığınının çalışma mantığı yatar. Bu makalede tarama metodolojisini adım adım, "neden böyle oluyor" sorusunu sürekli sorarak ele alacağız.

## Tarama Metodolojisinin Genel Mantığı

Bir hedefi taramadan önce şu soruyu sormak gerekir: elimizde ne var ve ne öğrenmek istiyoruz? İyi bir tarama metodolojisi katmanlı ilerler. Önce "hangi sistemler ayakta?" (host keşfi), sonra "bu sistemlerde hangi kapılar açık?" (port tarama), ardından "bu kapıların arkasında ne çalışıyor?" (servis ve sürüm tespiti), en sonunda da "bu sistem hangi işletim sistemi?" (OS tespiti) sorularını cevaplarız.

Bu sıralamanın rastgele olmadığını vurgulamak önemlidir. Her katman bir sonrakinin girdisini daraltır. Bütün bir /16 ağı (65 bin adres) için tam port taraması yapmak günler sürebilir; oysa önce host keşfi yapıp yalnızca canlı 200 sistemi hedeflersek, taramayı hem hızlandırır hem de gereksiz gürültü üretmemiş oluruz. Metodolojinin özü, her adımda arama uzayını akıllıca küçültmektir.

Bir diğer temel ilke ise **gizlilik ile hız arasındaki dengedir**. Ne kadar hızlı tararsanız, güvenlik cihazlarına (IDS/IPS, firewall) o kadar belli edersiniz kendinizi. Ne kadar sessiz olursanız, tarama o kadar uzar. Doğru metodoloji, hedefin ne olduğuna göre bu dengeyi bilinçli ayarlamaktır.

## Host Keşfi (Host Discovery)

### Tanım ve Çalışma Mantığı

Host keşfi, bir IP aralığındaki hangi adreslerin gerçekten canlı bir sisteme karşılık geldiğini belirleme işlemidir. Nmap dünyasında buna genellikle "ping tarama" da denir, ama bu isim yanıltıcıdır çünkü Nmap sadece ICMP echo request göndermez.

Neden sadece ICMP yeterli değildir? Çünkü modern ağlarda çoğu firewall ve host, ICMP echo (yani klasik `ping`) paketlerini engeller ya da yanıtlamaz. Eğer host keşfini yalnızca ICMP ile yaparsanız, aslında canlı olan onlarca sistemi "ölü" sanıp atlarsınız. Bu, tarama metodolojisindeki en yaygın ve en maliyetli hatalardan biridir.

Bu yüzden Nmap, varsayılan host keşfinde (yetkili/root kullanıcıyla) birden fazla teknik kullanır: ICMP echo request, ICMP timestamp request, belirli portlara TCP SYN paketi, belirli portlara TCP ACK paketi ve yerel ağda ARP istekleri. Mantık şudur: bir sistem ICMP'yi engelliyor olabilir ama açık bir web portuna (örneğin 443) gelen bir TCP paketine yanıt vermek zorunda kalır. Farklı prob türlerini bir arada kullanmak, "hayatta olduğunu" ele veren en az bir sinyal yakalama olasılığını artırır.

### ARP'ın Özel Rolü

Yerel ağ segmentinde (aynı broadcast domain) Nmap, IP tabanlı prob'lar yerine ARP isteklerini tercih eder ve bunu bilinçli yapar. Neden? Çünkü aynı LAN üzerinde bir IP'ye paket göndermeden önce zaten ARP çözümlemesi yapmak zorunludur. Bir host, IP seviyesinde firewall ile ICMP ve TCP'yi engellese bile, ARP isteğine yanıt vermemesi ağ kartının çalışmaması anlamına gelir. Yani ARP, yerel ağda neredeyse atlatılamaz bir keşif yöntemidir. Bu, host keşfini yerel ağda hem çok hızlı hem de çok güvenilir kılar.

### Somut Senaryo

Diyelim ki bir kurum içi sızma testi yapıyorsunuz ve size `10.0.5.0/24` aralığı verildi. Önce sadece host keşfi (port taraması yapmadan) çalıştırırsınız; Nmap'te bunu "ping scan / list of live hosts" modu sağlar. Çıktı olarak, örneğin 254 adresten 37'sinin canlı olduğunu öğrenirsiniz. Artık sonraki bütün taramalarınızı bu 37 adrese odaklarsınız. 254 yerine 37 sistemi taramak, süreyi kabaca yedide bire indirir.

### İstismar ve Savunma Perspektifi

Saldırgan açısından host keşfi, saldırı yüzeyini (attack surface) haritalamanın ilk adımıdır. Ancak bu aşama savunma tarafında da fark edilebilir: art arda gelen ARP istekleri veya çok sayıda adrese gönderilen SYN paketleri, bir IDS için klasik "ağ tarama" imzasıdır.

Savunma tarafında birkaç yaklaşım vardır. Birincisi, ICMP'yi tümden kapatmak yerine mantıklı sınırlamak (rate limiting) tercih edilmelidir; ICMP'yi tamamen kapatmak bazı meşru ağ işlevlerini bozabilir ve zaten saldırganı ARP/TCP tekniklerinden koruyamaz. İkincisi ve daha etkilisi, yerel ağda ARP izleme ve segment içi trafik denetimidir; kısa sürede çok sayıda ARP isteği yayan bir kaynak alarm üretmelidir. Üçüncüsü, ağ segmentasyonudur: saldırganın eriştiği segmentten diğer kritik segmentlere geçişi kısıtlarsanız, host keşfinin görebildiği alanı daraltmış olursunuz.

## Port Tarama ve SYN Taraması

### TCP El Sıkışmasını Hatırlamak

Port taramasının kalbini anlamak için TCP el sıkışmasını (three-way handshake) net bilmek gerekir. Normal bir TCP bağlantısı şöyle kurulur: istemci `SYN` gönderir, sunucu port açıksa `SYN-ACK` ile yanıtlar, istemci `ACK` göndererek bağlantıyı tamamlar. Eğer port kapalıysa sunucu `RST` (reset) döner. Eğer önünde bir firewall paketi sessizce düşürüyorsa (drop), hiçbir yanıt gelmez.

Bu üç durum — SYN-ACK, RST, yanıt yok — port taramasının bütün temelini oluşturur. Nmap bu yanıtlara bakarak portun durumunu `open`, `closed` veya `filtered` olarak sınıflandırır.

### SYN Taraması Neden "Yarı Açık"?

En yaygın ve genellikle varsayılan tarama türü SYN taramasıdır (çoğu zaman `-sS` bayrağıyla anılır). Bu taramanın çalışma mantığı zekicedir: Nmap `SYN` gönderir, `SYN-ACK` gelirse portun açık olduğunu anlar, ama bağlantıyı tamamlamak yerine hemen `RST` göndererek el sıkışmasını **yarıda keser**. İşte bu yüzden "half-open scan" (yarı açık tarama) denir.

Peki neden bağlantı tamamlanmaz? İki sebep var. Birincisi hız: her portta üçüncü paketi göndermeyip bağlantıyı hiç kurmamak, kaynak kullanımını ve süreyi azaltır. İkincisi ve tarihsel olarak daha önemlisi gizlilik: bağlantı tam kurulmadığı için, uygulama katmanındaki log mekanizmaları çoğu zaman bu bağlantıyı "kabul edilmiş bağlantı" olarak kaydetmez. Yani sunucudaki uygulama logunda iz bırakmama olasılığı daha yüksektir. Bunun "tam gizlilik" anlamına gelmediğini vurgulamak gerekir; modern IDS/IPS sistemleri yarı açık taramaları kolaylıkla tespit eder. Ama uygulama seviyesi loglama açısından geçmişte gerçek bir avantajdı ve bu isim oradan gelir.

SYN taramasının bir kısıtı, ham paket (raw packet) oluşturabilmek için genellikle yetkili (root/administrator) ayrıcalık gerektirmesidir. Yetki yoksa Nmap, işletim sisteminin normal `connect()` çağrısını kullanan tam bağlantı taramasına (TCP connect scan) düşer; bu da el sıkışmasını tamamladığı için hem daha yavaş hem de uygulama loglarında daha görünürdür.

### open, closed, filtered Ayrımının İncelikleri

Buradaki en kritik kavramsal nokta `filtered` durumudur. Nmap bir porta SYN gönderip **hiç yanıt alamazsa**, bunun iki nedeni olabilir: ya paket bir firewall tarafından sessizce düşürülüyordur (drop), ya da paket ağda kayboldu. Nmap bu belirsizlik yüzünden portu `filtered` olarak işaretler ve genellikle prob'u birkaç kez tekrarlar. Bu, taramanın neden filtreli ağlarda çok yavaşladığını açıklar: her yanıtsız port için Nmap yeniden deneme (retransmission) ve zaman aşımı (timeout) beklemek zorundadır.

`closed` durumu ise aslında bilgi verir: RST dönen bir port, o hostun canlı olduğunu ama o portta hizmet çalışmadığını kesinleştirir. Yani "kapalı port" bile keşif için değerli bir sinyaldir.

### Diğer Bayrak Kombinasyonları ve Mantıkları

TCP bayraklarını manipüle eden FIN, NULL ve Xmas gibi taramalar da vardır. Bunların mantığı RFC'deki bir davranışa dayanır: kapalı bir porta, SYN bayrağı olmayan (örneğin sadece FIN bayraklı) bir paket geldiğinde standart uyumlu bir yığının RST dönmesi, açık bir portun ise bu paketi sessizce yok sayması beklenir. Böylece "yanıt yok = açık ya da filtreli", "RST = kapalı" çıkarımı yapılır. Bu taramaların amacı bazı basit firewall kurallarını atlatmaktır çünkü bu kurallar çoğunlukla SYN paketlerine odaklanır. Ancak bu tekniklerin güvenilirliği işletim sistemine bağlıdır: bazı sistemler (özellikle bazı Windows yığınları) RFC'yi bu noktada farklı yorumlar ve her kapalı porta RST döndürebilir, bu da FIN/NULL/Xmas taramalarını o hedeflerde işe yaramaz kılar. Bu yüzden bu teknikleri kör güvenmeden, sonuçları doğrulayarak kullanmak gerekir.

UDP taraması ise ayrı bir dünyadır. UDP bağlantısız olduğu için el sıkışması yoktur. Nmap bir UDP portuna paket gönderir; yanıt gelmezse portun açık ya da filtreli olduğunu varsayar, "ICMP port unreachable" hatası gelirse kapalı olduğunu anlar. UDP taramasının çok yavaş olmasının nedeni tam da budur: açık portlar genellikle sessiz kalır ve Nmap uzun zaman aşımları beklemek zorundadır. Üstelik ICMP hata mesajları da genellikle hız sınırlamasına (rate limiting) tabidir.

## Servis ve Sürüm Tespiti (Version Detection)

### Neden Sadece Port Numarası Yetmez?

Bir portun açık olduğunu bilmek, orada ne çalıştığını bilmek değildir. 80 numaralı portun açık olması "muhtemelen web servisi" der ama hangi web sunucusu, hangi sürüm, belki de standart port üzerinden çalışan bambaşka bir hizmet olabilir. Saldırgan için asıl değerli bilgi sürümdür, çünkü zafiyetler (vulnerabilities) belirli yazılım sürümlerine bağlıdır.

### Çalışma Mantığı

Sürüm tespiti (genellikle `-sV` bayrağı) şöyle çalışır: Nmap açık porta bağlanır ve önce servisin kendiliğinden gönderdiği banner'ı dinler. Birçok servis (SSH, SMTP, FTP gibi) bağlanır bağlanmaz kendini tanıtan bir metin gönderir. Eğer banner yeterli değilse, Nmap bir prob veritabanı kullanarak porta çeşitli sorgular gönderir ve gelen yanıtların imzasını (signature) bilinen desenlerle karşılaştırır. Örneğin bir HTTP servisine `GET` isteği gönderip yanıt başlıklarına bakar, TLS servisine el sıkışması başlatıp sertifika bilgisini okur.

Bu yaklaşımın gücü, portun standart olmayan bir yerde çalışmasına aldırmamasıdır. 8080'de çalışan bir web sunucusu da, 2222'de çalışan bir SSH de doğru şekilde tanınır çünkü Nmap port numarasına değil, gerçek trafik davranışına bakar.

### İstismar ve Savunma

Saldırgan açısından `-sV` çıktısı bir zafiyet araştırmasının başlangıç noktasıdır. "Apache 2.x.y" ya da "OpenSSH x.y" gibi bir çıktı elde edildiğinde, saldırgan o sürüme ait bilinen zafiyetleri araştırır. Sürüm, saldırıyı hedeflenmiş (targeted) hale getirir.

Savunma tarafında en temel önlem **banner gizleme/azaltma**dır. Birçok yazılımın sürüm bilgisini banner'dan kaldırma ya da genel bir değerle değiştirme seçeneği vardır. Ancak burada dürüst olmak gerekir: banner gizleme gerçek bir güvenlik değil, "security through obscurity"dir. Nmap'in davranışsal prob'ları çoğu zaman banner olmadan da servisi tahmin edebilir; ayrıca sürümü gizlemek zafiyeti ortadan kaldırmaz, sadece keşfini biraz zorlaştırır. Asıl savunma yamanın uygulanmasıdır (patch management). Banner gizleme, otomatik/gürültülü tarayıcıları yavaşlatan ikincil bir katman olarak düşünülmelidir; birincil savunma değil.

Bir diğer savunma, web application firewall (WAF) ve ters proxy (reverse proxy) kullanımıdır. Arka uçtaki gerçek sunucu sürümünü dışarıya yansıtmayan bir proxy, sürüm tespitini yanıltabilir.

## İşletim Sistemi Tespiti (OS Detection)

### Çalışma Mantığı: TCP/IP Parmak İzi

OS tespiti (genellikle `-O` bayrağı) belki de Nmap'in en zarif tekniklerinden biridir ve mantığı şudur: her işletim sistemi TCP/IP yığınını RFC'lere biraz farklı yorumlayarak uygular. RFC'ler her ayrıntıyı zorunlu kılmaz; birçok noktada uygulamaya serbestlik bırakır. İşte bu serbest bırakılan alanlardaki tercihler, işletim sistemleri arasında farklılık gösterir ve bir tür **parmak izi (fingerprint)** oluşturur.

Nmap, hedefe bir dizi özel hazırlanmış paket gönderir ve yanıtlardaki ince ayrıntıları inceler: başlangıç TTL (Time To Live) değeri, TCP pencere boyutu (window size), TCP seçeneklerinin (options) sırası ve değerleri, başlangıç sıra numarası (ISN) üretim deseni, belirli hatalı/olağandışı paketlere verilen tepkiler gibi. Bu ölçümlerin bileşimi, Nmap'in imza veritabanındaki bilinen sistem parmak izleriyle karşılaştırılır ve en yakın eşleşme raporlanır.

### Neden Kesin Değil?

OS tespiti bir tahmindir, kesinlik değil. Nmap genellikle bir "doğruluk yüzdesi" ve birden fazla aday sunar. Bunun sebebi çeşitli faktörlerdir. Aradaki firewall'lar, NAT cihazları ve yük dengeleyiciler (load balancer) paketleri değiştirebilir; sanal makineler ve konteynerler ana sistemin yığın davranışını maskeleyebilir; ayrıca güvenilir bir parmak izi için Nmap'in en az bir açık ve bir kapalı porta ihtiyacı vardır — ikisi de yoksa tahmin zayıflar. Bu yüzden OS tespiti sonuçlarını hep bir güven aralığıyla okumak gerekir.

### İstismar ve Savunma

Saldırgan için işletim sistemini bilmek, saldırıyı doğru hedefe yöneltmeyi sağlar; bir zafiyet Windows'a özgüyse ve hedef Linux'sa vakit harcamaya değmez. OS tespiti bu yüzden exploit seçimini daraltır.

Savunma tarafında "OS fingerprint spoofing" denen teknikler vardır: sistemin TCP/IP yığın davranışını değiştirerek Nmap'i yanıltmaya çalışmak. Bazı işletim sistemleri ve güvenlik cihazları TTL, pencere boyutu gibi değerleri normalize edebilir. Ancak burada da gerçekçi olmak lazım: parmak izini gizlemek saldırganı yavaşlatır ama durdurmaz ve kararlı bir saldırgan işletim sistemini başka ipuçlarından (banner'lar, servis davranışları, hata mesajları) yine çıkarabilir. Daha sağlam savunma, tespit edilse bile sömürülemeyecek kadar sıkılaştırılmış (hardened) ve güncel bir sistemdir.

## Nmap Scripting Engine (NSE)

### Tanım ve Mimarî

NSE, Nmap'i basit bir port tarayıcıdan çok yönlü bir güvenlik denetim aracına dönüştüren, Lua diliyle yazılmış betiklerden oluşan bir motordur. Fikir şudur: tarama sırasında keşfedilen açık portlar ve servisler üzerinde, otomatik olarak ek kontroller çalıştırmak. Böylece "port açık" bilgisinden "bu portta şu zafiyet var" ya da "bu servis şu bilgiyi sızdırıyor" sonucuna tek adımda geçilebilir.

Betikler kategorilere ayrılmıştır ve bu kategoriler metodolojinin farklı aşamalarına denk gelir. Kabaca: keşif amaçlı (discovery), güvenli bilgi toplama (safe), zafiyet kontrolü (vuln), kimlik doğrulama ve kaba kuvvet (auth, brute), hatta gerçekten saldırgan/tehlikeli (intrusive, exploit) kategoriler bulunur. Bu kategorizasyon çok önemlidir çünkü bir betiğin ne kadar "gürültülü" ve ne kadar "riskli" olduğunu belirler.

### Çalışma Mantığı ve Somut Örnek

NSE betikleri, tarama bilgileriyle beslenir. Örneğin bir betik yalnızca 443 portu açıksa çalışacak şekilde tetiklenebilir; Nmap açık portu görünce ilgili TLS/SSL betiklerini otomatik devreye sokar. Somut bir örnek: bir SSL betiği, sunucunun desteklediği şifreleme paketlerini (cipher suites) listeleyip zayıf olanları işaretleyebilir; bir HTTP betiği, yaygın dizinleri ya da başlık yanlış yapılandırmalarını arayabilir; bir SMB betiği, paylaşımları ve protokol sürümünü sorgulayabilir.

Burada kritik uyarı şudur: **NSE'nin bazı kategorileri gerçekten müdahalecidir**. `brute` kategorisi kaba kuvvet denemesi yapar ve hesapları kilitleyebilir; `intrusive` ve `exploit` betikleri hedefte hizmet kesintisine (denial of service) ya da beklenmeyen değişikliklere yol açabilir. Yetkisiz bir sistemde bu betikleri çalıştırmak hem etik hem yasal olarak ciddi sorundur. Bir betiği çalıştırmadan önce ne yaptığını anlamak, profesyonel sorumluluğun parçasıdır.

### İstismar ve Savunma

Saldırgan için NSE, keşif ile zafiyet doğrulaması arasındaki köprüdür; elle yapılacak birçok kontrolü otomatikleştirir. Savunma tarafında NSE trafiği çoğu zaman ayırt edici desenler taşır — belirli prob dizileri, karakteristik istekler — ve iyi ayarlanmış bir IDS bunları yakalayabilir. Ayrıca `brute` gibi kategorilere karşı en doğrudan savunma hesap kilitleme politikaları, oran sınırlama ve anormal kimlik doğrulama denemelerinin izlenmesidir.

## Zamanlama ve Performans (Timing)

### Neden Zamanlama Bu Kadar Önemli?

Zamanlama, tarama metodolojisinin en yanlış anlaşılan ama en belirleyici parçasıdır. Bir taramanın ne kadar hızlı, ne kadar sessiz ve ne kadar doğru olacağını doğrudan zamanlama parametreleri belirler. Yanlış zamanlama, ya taramanın günlerce sürmesine, ya güvenlik cihazlarınca hemen fark edilmesine, ya da yanlış (eksik ya da hatalı) sonuçlar üretmesine yol açar.

Nmap, zamanlamayı bir dizi "timing template" (zamanlama şablonu) ile soyutlar; genellikle `-T0`'dan `-T5`'e kadar numaralandırılır. Düşük numaralar çok yavaş ve sessiz, yüksek numaralar çok hızlı ve gürültülüdür. `-T0` (paranoid) IDS atlatma amacıyla paketleri arasında dakikalarca bekleyebilir; `-T5` (insane) mümkün olan en agresif hızı hedefler ama paket kaybına ve yanlış sonuçlara açıktır. Orta değerler günlük işlerin çoğunda dengelidir.

### Şablonların Altındaki Parametreler

Bu şablonlar aslında daha alt seviye parametrelerin hazır setleridir. Bunları anlamak, neden bir taramanın yavaş ya da yanlış olduğunu teşhis etmeyi sağlar. Temel parametreler şunlardır:

- **Paralellik (parallelism):** Aynı anda kaç prob'un uçuşta olduğu. Yüksek paralellik hızı artırır ama ağı ve hedefi zorlar.
- **Yeniden deneme sayısı (retries):** Yanıtsız bir prob'un kaç kez tekrar gönderileceği. Yüksek değer doğruluğu artırır ama filtreli ağlarda taramayı çok yavaşlatır.
- **Zaman aşımı süreleri (timeouts):** Bir yanıtı ne kadar bekleyeceği. Kısa timeout hızlıdır ama yavaş yanıt veren hostları "filtreli" sanma riski taşır.
- **Prob'lar arası gecikme (scan delay):** Paketler arasına konan bekleme. Oran sınırlamalı hedeflerde ve IDS atlatmada kritiktir.

### Doğruluk ile Hız Gerilimi

Buradaki kök neden şudur: ağlar mükemmel değildir. Paketler kaybolabilir, gecikebilir, hedef oran sınırlama uygulayabilir. Çok agresif bir zamanlama, gerçekte açık olan bir portu yanıt zamanında gelmediği için "kapalı" ya da "filtreli" sanabilir. Yani hız uğruna doğruluğu feda edersiniz. Tersine, çok muhafazakâr bir zamanlama doğrudur ama pratik olmayacak kadar uzun sürer. Profesyonel bir tarayıcı, hedefin özelliklerine (yerel LAN mı, yüksek gecikmeli internet mi, oran sınırlamalı mı) göre bu dengeyi bilinçli ayarlar; kör bir `-T5` alışkanlığı çoğu zaman sessiz veri kaybına yol açar.

### İstismar ve Savunma

Saldırgan açısından düşük zamanlama şablonları, IDS/IPS'in "kısa sürede çok bağlantı" tabanlı tarama tespit eşiklerinin altında kalmayı amaçlar. Paketler yeterince seyrek gönderilirse, tespit sistemi bunları bir tarama olarak ilişkilendiremeyebilir.

Savunma tarafı için bu, tespit mantığının sadece "hız eşiğine" dayanmaması gerektiğini gösterir. Yavaş ve dağıtık taramaları yakalamak için daha uzun zaman pencerelerinde korelasyon yapan, farklı portlara/hostlara yayılan erişim desenlerini birleştiren tespit yaklaşımları gerekir. Ayrıca oran sınırlama (rate limiting) savunma tarafında da bir araçtır: hedef sistemler ve ağ cihazları prob'lara yavaş yanıt vererek saldırganın taramasını hem yavaşlatır hem de gürültüsünü artırıp fark edilmesini kolaylaştırır.

## Yaygın Hatalar

Sahada tekrar tekrar görülen hatalar, çoğunlukla metodolojinin altındaki mantığı atlamaktan kaynaklanır.

**Host keşfini atlamak veya yanlış yapmak.** ICMP engellenen ağlarda sadece ping'e güvenip canlı sistemleri kaçırmak en klasik hatadır. Bazen tam tersi de olur: host keşfini tümden atlayıp devasa aralıklarda tam port taraması başlatarak günler kaybedilir.

**Varsayılan port setine körü körüne güvenmek.** Nmap varsayılan olarak en yaygın portları tarar, tüm 65535 portu değil. Kritik bir servis olağandışı bir portta çalışıyorsa, "tam" sandığınız tarama onu hiç görmez. Kapsam ve hedefe göre port aralığını bilinçli seçmek gerekir.

**`-T5`'i her yerde kullanmak.** Hız güzeldir ama yüksek gecikmeli ya da oran sınırlamalı ağlarda agresif zamanlama sessizce yanlış sonuç üretir. En tehlikeli hata türü, yanlış olduğunu fark edemediğiniz hatadır.

**UDP taramasını tümden ihmal etmek.** UDP yavaş diye atlanır, oysa DNS, SNMP, birçok VPN ve önemli servisler UDP üzerindedir. Sadece TCP taraması, saldırı yüzeyinin bir kısmını kör bırakır.

**`filtered` sonucunu "yok" sanmak.** Filtreli port, "orada bir şey var ama firewall koruyor" demektir; bilgi değil, aksine önemli bir ipucudur. Bunu yok saymak yanlış bir güvenlik hissi yaratır.

**Kapsam ve izin sınırlarını çiğnemek.** Özellikle NSE'nin müdahaleci betikleri ve kaba kuvvet kategorileri, yetki verilmemiş sistemlerde çalıştırıldığında hem hizmet kesintisine hem hukuki sonuçlara yol açar. Yazılı kapsam (scope) ve izin olmadan tarama yapmak profesyonel bir hatadır.

## En İyi Pratikler

**Katmanlı ilerleyin.** Önce host keşfi, sonra hedef daraltarak port taraması, sonra sürüm ve OS tespiti, en sonunda uygun NSE betikleri. Her adım bir sonrakini besler ve gürültüyü azaltır.

**Hedefe göre zamanlama seçin.** Yerel LAN'da agresif olabilirsiniz; yüksek gecikmeli veya izlenen bir ortamda muhafazakâr ve sabırlı olun. Zamanlamayı bilinçli bir karar olarak ele alın, alışkanlıkla değil.

**Sonuçları doğrulayın, tek taramaya güvenmeyin.** Özellikle OS tespiti ve filtreli portlar için, farklı teknikleri (SYN, ACK, farklı prob'lar) çapraz kontrol edin. Kritik bir bulguyu, mümkünse elle veya farklı bir araçla teyit edin.

**Çıktıyı yapılandırılmış biçimde saklayın.** Taramaları makine-okunur formatlarda kaydetmek, sonradan işleme, karşılaştırma ve raporlama için değerlidir. İki farklı zamandaki taramaları karşılaştırarak ağdaki değişimi görebilirsiniz.

**Gürültü ve iz bırakmanın bilincinde olun.** Meşru bir sızma testinde bile, gereksiz agresif taramalar hedef sistemlere zarar verebilir ya da savunma ekibini yanlış yönlendirebilir. Yaptığınız her prob'un bir maliyeti olduğunu unutmayın.

**Betikleri çalıştırmadan önce anlayın.** Bir NSE betiğinin ne yaptığını, hangi kategoride olduğunu ve hedefte ne gibi bir etki bırakacağını bilmeden çalıştırmayın. "Safe" olmayan her şey, aksi kanıtlanana kadar riskli varsayılmalıdır.

**Yetki ve kapsam disiplinini koruyun.** Her zaman yazılı izin ve tanımlı kapsam içinde kalın. Metodolojinin en önemli parçası teknik değil, etik ve yasal çerçevedir.

## Sonuç

Nmap'i güçlü kılan şey, komutlarının çokluğu değil, altında yatan protokol mantığıdır. SYN taramasının neden yarı açık olduğunu, host keşfinin neden çok yöntemli çalıştığını, OS tespitinin neden bir tahmin olduğunu ve zamanlamanın doğruluğu nasıl etkilediğini anladığınızda, Nmap artık bir bayrak listesi değil, ağı okuyan bir mercek haline gelir. İyi bir güvenlik uzmanı, her taramada "ne öğrenmek istiyorum, bu prob neden bu sonucu verdi ve bunun savunma tarafındaki karşılığı ne?" sorularını sorar. Metodoloji, işte bu soruları disiplinli bir sıraya koymaktan ibarettir.
