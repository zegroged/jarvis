# Trafik Analizi ve Derin Paket İnceleme (Wireshark/tcpdump ile Protokol Analizi, PCAP Forensics, Anomali Tespiti)

## Giriş ve Kapsam

Network forensics genel bir şemsiye terimdir: "ağ üzerinde ne oldu" sorusuna cevap arar. Ama bu şemsiyenin altında, günlük SOC (Security Operations Center) ve IR (Incident Response) çalışmasının asıl iş yükünü oluşturan, çok daha somut bir yetkinlik vardır: paket seviyesinde canlı veya kaydedilmiş (offline) trafiği okuyup yorumlama becerisi. Bir analist elinde bir PCAP dosyası veya canlı bir arayüz (interface) ile oturduğunda, gerçekte yaptığı şey; protokol katmanlarını ayrıştırmak (parse etmek), akışları (flow/stream) takip etmek, şifreli trafikte içerik göremediği için metadata'ya (zaman, boyut, sertifika, SNI) yönelmek ve "normal" ile "anormal" arasındaki sınırı çizmektir.

Bu makale, packet capture (paket yakalama) araçlarının (Wireshark, tcpdump, tshark) çalışma mantığını, protokol analizinin nasıl yapıldığını, PCAP forensics metodolojisini ve anomali tespiti yaklaşımlarını savunmacı bir bakış açısıyla ele alır. Amaç saldırı talimatı değil; bir mekanizmayı anlayıp ona karşı görüş (visibility) ve tespit (detection) kurmaktır.

## Neden Bu Konu Ayrı Bir Yetkinlik Alanı

Network forensics dendiğinde çoğu zaman "log topla, correlate et, SIEM'e at" akışı akla gelir. Ama loglar özetlenmiş, yorumlanmış veridir — bir firewall log'u size "bu bağlantı reddedildi" der, ama paketin TCP flag kombinasyonu, TTL değeri, TLS handshake'indeki JA3 parmak izi gibi ham detayları vermez. Paket seviyesi analiz, log seviyesinin altındaki gerçek zemin katmandır (ground truth). Şu üç durumda logların yetmediği, paket analizinin zorunlu hale geldiği anlar ortaya çıkar:

1. **Loglama yoksa veya yetersizse**: Saldırgan zaten log mekanizmasını devre dışı bırakmış veya cihaz o seviyede log üretmiyor olabilir. PCAP, cihazdan bağımsız, "kabloda ne varsa" onu kaydeder.
2. **Şüpheli ama sınıflandırılmamış davranış**: IDS/IPS bir imza (signature) eşleşmesi bulamadığında ama trafik "tuhaf" göründüğünde, tek çözüm ham paketi açıp elle incelemektir.
3. **Şifreli kanallarda niyet analizi**: İçeriği göremiyorsanız da zamanlama, boyut, sertifika zinciri, SNI (Server Name Indication) gibi metadata sinyalleri C2 (command and control) trafiğini ele verebilir.

Bu, network forensics'in "büyük resim" sorgularından (kim, ne zaman, hangi IP) ayrı; "bu spesifik akışta protokol düzeyinde ne oluyor" sorusuna cevap veren, uygulamalı ve araç-merkezli bir disiplindir.

## Kök Neden / Çalışma Mantığı: Paket Yakalama Nasıl İşler

### Katman Katman Yakalama

Bir paket yakalayıcı (packet capture engine), işletim sisteminin ağ yığınına (network stack) NIC (Network Interface Card) sürücüsü ile uygulama katmanı arasındaki bir noktada "musluk" (tap) takar. Linux'ta bu genellikle `libpcap` üzerinden `AF_PACKET` soket ailesi veya daha performanslı senaryolarda `PF_RING`, `eBPF`/`XDP` ile yapılır; Windows'ta ise `Npcap` (eski adıyla WinPcap) sürücüsü aynı işi görür. Mantık şudur: NIC üzerine gelen her ham çerçeveyi (frame), işletim sisteminin normal işleme zincirine (TCP/IP stack) girmeden önce (veya paralel olarak) bir kopyasını yakalayıcıya yönlendirmek.

Bunun kök nedeni, ağın **katmanlı (layered)** bir mimari olmasıdır — OSI modeli veya pratikte TCP/IP modeli. Her katman kendinden bir üst katmanın verisini "encapsulate" eder (Ethernet çerçevesi içinde IP paketi, IP paketi içinde TCP segmenti, TCP içinde HTTP/TLS verisi gibi). Bir analiz aracı bu paketi aldığında, sırayla her katmanın header'ını "dissect" eder (ayrıştırır): önce Ethernet (MAC adresleri, EtherType), sonra IP (kaynak/hedef IP, TTL, fragmentasyon bilgisi), sonra TCP/UDP (port, sequence number, flag'ler), en sonda uygulama katmanı protokolü (HTTP, DNS, TLS vs.). Wireshark'ın "dissector" mimarisi tam olarak bu prensibe dayanır: her protokol için ayrı bir ayrıştırıcı modül vardır ve bir üst katmanın çıktısı bir sonrakinin girdisi olur.

### Promiscuous Mode ve Görünürlük Sınırı

Normalde bir NIC, sadece kendi MAC adresine (veya broadcast/multicast) yönelik çerçeveleri işleme alır, gerisini donanım seviyesinde eler. "Promiscuous mode" (veya kablosuzda "monitor mode"), NIC'e gelen **her** çerçeveyi işlemciye geçirmesini söyler. Bunun neden önemli olduğunu anlamak, görünürlüğün sınırlarını anlamak demektir: bir switch'e bağlı bir portta promiscuous mode açsanız bile, switch zaten yalnızca size yönelik trafiği o porta iletir (hub'ların aksine). Bu nedenle tam görünürlük için ya bir **SPAN/mirror port** (switch üzerinde bir portun trafiğini başka bir porta kopyalayan yapılandırma) ya da bir **network TAP** (fiziksel olarak hatta giren, trafiği pasif kopyalayan donanım) gerekir. Bu, "neden trafiğimi göremiyorum" sorusunun kök nedenidir ve bir çok gerçek dünya PCAP toplama başarısızlığının sebebi budur.

### BPF: Filtreleme Neden Kaynak Katmanında Yapılır

`tcpdump` ve Wireshark'ın capture filter'ları **BPF (Berkeley Packet Filter)** üzerine kuruludur. BPF, çekirdek (kernel) içinde çalışan, minimal ve güvenli bir sanal makinedir; kullanıcı "host 10.0.0.5 and port 443" gibi bir filtre yazdığında, bu ifade BPF bytecode'una derlenir ve çekirdeğe yüklenir. Kök neden/verimlilik mantığı şudur: eğer filtreleme yalnızca kullanıcı alanında (userspace) yapılsaydı, her paket önce çekirdekten kullanıcı alanına kopyalanır, sonra elenirdi — yüksek trafik hacminde bu ciddi bir performans kaybı ve paket kaybı (drop) riski yaratır. BPF, eleme işlemini paket henüz çekirdekteyken yaptığı için gereksiz kopyalamayı önler. Bu yüzden "capture filter" (BPF, yakalamadan önce uygulanır, performans kritik) ile "display filter" (Wireshark'ın kendi ifade dili, zaten yakalanmış veri üzerinde çalışır, esnek ama yakalama sonrası) arasındaki ayrım kavramsal olarak çok önemlidir: display filter'lar donanım/performans avantajı sağlamaz, sadece zaten diskte/bellekte olan veriyi görüntüleme amaçlı süzer.

## Nasıl Çalışır: Akış Takibi (Stream Reassembly)

TCP; veriyi segmentlere böler, bu segmentler ağda farklı yollardan, farklı sırayla, hatta tekrar tekrar (retransmission) gelebilir. Bir analiz aracının "TCP akışını takip et" (Follow TCP Stream) özelliği aslında şunu yapar: sequence number ve acknowledgment number alanlarına bakarak segmentleri doğru sıraya dizer, tekrarlananları (retransmission) eler, ve orijinal byte akışını yeniden inşa eder (reassembly). Bunun kök nedeni, uygulama katmanı verisinin (bir HTTP isteği, bir dosya transferi) tek bir pakette değil, çoğu zaman onlarca segmentte parçalanmış olarak taşınmasıdır — insan analistin okuyabileceği anlamlı bir bütünü ancak bu yeniden birleştirme sonrasında görebilirsiniz.

Aynı mantık IP fragmentasyonunda da geçerlidir: MTU (Maximum Transmission Unit) sınırını aşan bir IP paketi parçalara bölünür, hedefte (veya bazı senaryolarda ara noktalarda) yeniden birleştirilir. Fragmentasyon, tarihsel olarak IDS/firewall atlatma (evasion) tekniklerinin de temeli olmuştur (örneğin fragment'ları kasıtlı olarak çakıştırarak — overlapping fragments — farklı işletim sistemlerinin bunları farklı önceliklendirmesinden faydalanmak). Bu, "neden bir IDS bazen saldırıyı kaçırır" sorusunun köklerinden biridir: eğer IDS'in fragment reassembly mantığı, hedef sistemin (ör. Windows vs. Linux) reassembly mantığıyla birebir örtüşmüyorsa, IDS'in "gördüğü" veri ile hedefin "işlediği" veri farklılaşabilir.

## Protokol Analizi: Katman Katman Ne Aranır

### DNS

DNS, çoğu saldırı zincirinde erken bir sinyal kaynağıdır çünkü neredeyse her şey (C2 domain çözümleme, exfiltration, phishing altyapısı) DNS ile başlar. Analiz açısından bakılacak noktalar: sorgu sıklığı ve entropisi (yüksek entropili, rastgele görünen subdomain'ler DGA — Domain Generation Algorithm — şüphesi doğurur), TXT/NULL kayıt tipi kullanımı (DNS tünelleme için sıkça istismar edilir, çünkü bu kayıt tipleri keyfi veri taşımaya izin verir), NXDOMAIN oranının anormal yüksekliği (DGA tabanlı malware genellikle üretilen domain'lerin çoğunda başarısız olur, gerçek C2 sunucusuna denk gelene kadar), ve sorgu hacmi/boyutunun normal kullanıcı davranışına göre sapması.

### HTTP/HTTPS ve TLS Metadata

Düz metin HTTP'de analist doğrudan header'ları, User-Agent'ı, istek/yanıt gövdesini görebilir — anomali (ör. beklenmeyen bir User-Agent string'i, bilinen kötü amaçlı bir URI deseni) doğrudan tespit edilebilir. TLS ile şifrelenmiş trafikte ise içerik görünmez, ama **el sıkışma (handshake) metadata'sı** hâlâ açık taşınır: SNI (istemcinin hangi hostname'e bağlanmak istediği), sunucu sertifikası (Subject, Issuer, geçerlilik süresi, self-signed olup olmadığı), ve TLS versiyon/cipher suite tercihleri. Buradan doğan **JA3/JA3S** gibi fingerprinting teknikleri, istemcinin (veya sunucunun) TLS ClientHello/ServerHello içindeki alan sırasını ve değerlerini hash'leyerek bir "parmak izi" üretir — kök mantık şudur: farklı TLS kütüphaneleri (OpenSSL, BoringSSL, farklı diller/framework'ler) handshake'i biraz farklı kurar, bu da malware ailelerinin veya belirli araçların (ör. belirli bir C2 framework'ünün) trafiğini, içeriği çözmeden dahi ayırt etmeyi mümkün kılar.

Şifreli trafikte davranışsal analiz de mümkündür: paket boyutu dağılımı, zamanlama aralıkları (inter-arrival time), oturum süresi ve periyodiklik. Düzenli aralıklarla (ör. her 60 saniyede bir) sabit boyutlu, düşük hacimli bağlantılar kuran bir host, klasik bir C2 "beacon" (yoklama sinyali) davranışı gösteriyor olabilir — bu, "içeriği okuyamasam da davranışı görebilirim" prensibinin somut uygulamasıdır.

### ICMP ve Diğer Az Görülen Protokoller

ICMP normalde tanılama (ping, traceroute) amaçlıdır, ama payload alanına keyfi veri gömülerek tünel/exfiltration kanalı olarak kötüye kullanılabilir. Kök neden: birçok ağ politikası ICMP'yi "zararsız" kabul edip filtrelemez veya derinlemesine incelemez, bu da onu düşük gürültülü bir kaçış yolu haline getirir. Analist açısından anormal büyüklükte ICMP payload'ları, beklenmeyen ICMP tip/kod kombinasyonları veya yüksek hacimli ICMP trafiği bir bayrak (red flag) olmalıdır.

## PCAP Forensics Metodolojisi

Bir olay müdahalesi (incident response) sürecinde PCAP ile çalışırken izlenen mantıksal akış şu şekilde özetlenebilir:

1. **Kapsam belirleme (scoping)**: Hangi zaman aralığı, hangi host(lar), hangi segment. Büyük PCAP dosyalarını (bazen terabayt mertebesinde) elle taramak pratik değildir; bu yüzden önce zaman/IP/port bazlı ön filtreleme yapılır (`tshark` ile komut satırından toplu filtreleme, veya `tcpdump -r dosya -w yeni_dosya <filtre>` ile alt küme çıkarma).
2. **İstatistiksel özet çıkarma**: Wireshark'ın "Statistics" menüsü (Protocol Hierarchy, Conversations, Endpoints, IO Graph) veya `tshark -q -z conv,ip` gibi komutlar ile "kim kiminle, ne kadar, ne zaman konuştu" sorusuna hızlı cevap aranır. Bu adım, tek tek paket okumadan önce "nereye bakmalıyım" sorusunu daraltır.
3. **Anomali odaklarını belirleme**: Yukarıdaki özetten çıkan aykırı noktalar (beklenmeyen bir dış IP'ye yüksek hacimli trafik, garip bir port, alışılmadık bir protokol dağılımı) üzerine odaklanılır.
4. **Derinlemesine dissect**: İlgilenilen akış(lar) `Follow Stream` ile yeniden birleştirilir, uygulama katmanı içeriği (mümkünse) incelenir, gerekiyorsa objeler (dosyalar, sertifikalar) `File > Export Objects` benzeri mekanizmalarla çıkarılır.
5. **Zaman çizelgesi (timeline) inşası**: Bulgular, diğer kanıt kaynaklarıyla (host log'ları, EDR telemetrisi, proxy log'ları) zaman damgası üzerinden korelasyona sokulur — paket analizi tek başına nadiren yeterlidir, diğer kanıtlarla birleşince anlam kazanır.

### Delil Bütünlüğü (Chain of Custody) Notu

Bir PCAP, adli süreçte kanıt olarak kullanılacaksa, dosyanın hash değeri (ör. SHA-256) alınıp kayıt altına alınmalı, kimin ne zaman eriştiği belgelenmelidir. Kök neden: PCAP dosyaları kolayca düzenlenebilir/kırpılabilir; bütünlük kanıtı olmadan mahkemede veya resmi bir soruşturmada değeri tartışmalı hale gelir.

## Anomali Tespiti: Neye Göre "Anormal"

Anomali tespitinin temel zorluğu, "normal"in ağdan ağa, hatta gün içinde saatten saate değişmesidir. Bu yüzden etkili tespit, statik imzalardan çok **baseline (temel çizgi) sapmasına** dayanır:

- **Hacim bazlı anomaliler**: Bir host'un normalde ürettiği trafik hacminin kat kat üzerine çıkması (exfiltration şüphesi) veya normalde hiç konuşmadığı bir ülke/AS numarasına ani bağlantı.
- **Zamanlama anomalileri**: Mesai dışı saatlerde artan aktivite, düzenli periyodik "beacon" desenleri (C2 yoklaması).
- **Protokol/port uyumsuzluğu**: 443 portunda TLS olmayan düz metin trafiği (veya tam tersi — port 80'de şifreli veri), bilinen bir uygulama protokolünün beklenen davranış kalıbından sapması.
- **Asimetri**: Normal bir istemci-sunucu ilişkisinde istek küçük, yanıt büyük olur (web tarama gibi); bunun tersi bir örüntü (küçük düzenli istekler, büyük giden veri) exfiltration'ı düşündürür.
- **Sertifika/SNI tutarsızlıkları**: Kendinden imzalı (self-signed) sertifikalar, SNI alanı ile sertifika Subject/SAN alanının uyuşmaması, çok yeni oluşturulmuş (kısa ömürlü) sertifikalar.

Bu sinyallerin hiçbiri tek başına kesin kanıt değildir — anomali tespiti olasılıksaldır, bu yüzden gerçek dünyada bu sinyaller birleştirilip (correlation) bir güven skoru oluşturulur, ardından insan analist nihai değerlendirmeyi yapar.

## Tespit ve Savunma Stratejisi

Savunma tarafında öncelik, önce **görünürlük (visibility)** sonra **analiz kapasitesi** kurmaktır:

1. **Görünürlük altyapısı**: Kritik segmentlere TAP/SPAN yerleştirmek, tam paket yakalama (full packet capture) ile en azından metadata (NetFlow/IPFIX) toplamak arasında bir denge kurmak. Tam PCAP depolama maliyetlidir; bu yüzden çoğu kurum kısa pencereli tam capture (ör. son 24-72 saat) + uzun süreli akış/metadata kaydı (NetFlow) kombinasyonu kullanır.
2. **Baseline oluşturma**: Her ağın kendi normal davranış profilini çıkarmak — hangi host'lar hangi hostlarla, ne sıklıkla, hangi protokollerle konuşur. Baseline olmadan anomali tanımı anlamsızlaşır.
3. **TLS metadata odaklı tespit**: İçeriği deşifre etmek (SSL/TLS inspection — bir ara sunucu/proxy ile trafiği açıp tekrar şifreleme) her ortamda mümkün veya arzu edilir değildir (gizlilik, performans, sertifika pinning sorunları). Bu yüzden JA3/JA3S, SNI analizi, sertifika zinciri incelemesi gibi "içeriği açmadan" yapılan analiz teknikleri savunma cephaneliğinde öncelikli olmalıdır.
4. **IDS/IPS imzaları ile davranışsal tespiti birlikte kullanmak**: İmza tabanlı tespit bilinen tehditleri yakalar ama sıfırıncı gün (zero-day) veya özel araçlara karşı kördür; davranışsal/istatistiksel anomali tespiti bu boşluğu bir ölçüde kapatır.
5. **Merkezi zaman senkronizasyonu (NTP)**: Farklı kaynaklardan (PCAP, log, EDR) gelen zaman damgalarının tutarlı korelasyonu için tüm cihazların saat senkronizasyonu şarttır — bu sık gözden kaçan ama IR sürecini baştan sona etkileyen bir temel gereksinimdir.
6. **Depolama ve erişim politikası**: PCAP'ler hassas veri (kişisel bilgiler, kimlik bilgileri düz metin protokollerde görünebilir) içerebileceğinden, erişim kontrolü ve saklama süresi politikaları (ör. KVKK/GDPR uyumu) tasarım aşamasında düşünülmelidir.

## Yaygın Hatalar

- **Yanlış yakalama noktası seçmek**: Switch'te mirror port yapılandırmadan veya yanlış VLAN'ı dinleyerek "trafik görünmüyor" sonucuna varmak; kök sorun genelde topoloji/yapılandırma hatasıdır, araç hatası değil.
- **Display filter ile capture filter'ı karıştırmak**: Büyük hacimli, filtresiz canlı yakalamada tüm trafiği önce diske yazıp sonra display filter ile süzmeye çalışmak; bu hem performans hem depolama sorunu yaratır. Mümkünse capture filter (BPF) ile en baştan daraltmak gerekir.
- **Fragmentasyon/reassembly ayarlarını görmezden gelmek**: Wireshark'ta reassembly kapalıyken bir TCP akışını "eksik" veya "bozuk" sanmak; aslında segmentler ayrı ayrı görüntüleniyordur.
- **Şifreli trafikte içerik beklemek**: TLS trafiğinde payload'u "kırmaya" çalışmak yerine (mümkün olmayan senaryolarda) metadata analizine yönelmemek, zaman kaybına yol açar.
- **Tek bir anomali sinyaline aşırı güvenmek**: Örneğin yalnızca yüksek hacim gördüğünde hemen "exfiltration" sonucuna varmak; büyük bir yedekleme işi veya CDN senkronizasyonu da benzer imza üretebilir. Bağlam (context) olmadan sinyal yanlış pozitif üretir.
- **Zaman dilimi (timezone) tutarsızlığı**: PCAP zaman damgaları genelde capture makinesinin yerel saatinde veya UTC'de olabilir; farklı kaynaklardan gelen kanıtları birleştirirken saat dilimini kontrol etmemek, yanlış bir olay sıralaması (timeline) çıkarılmasına yol açar.
- **Baseline'ı güncel tutmamak**: Ağ topolojisi ve uygulama davranışı zamanla değişir (yeni SaaS entegrasyonları, yeni CDN'ler); eski bir baseline'a göre çalışan bir anomali tespiti hem çok fazla yanlış pozitif hem de yeni normalleşmiş kötü niyetli trafiği kaçırma riski taşır.

## Sonuç

Paket seviyesinde trafik analizi, network forensics'in soyut "ne oldu" sorusunu somut, doğrulanabilir bir zemine (ham bayt akışına) indirger. Bu yetkinlik; katmanlı ağ mimarisinin nasıl ayrıştırıldığını (dissection), akışların nasıl yeniden inşa edildiğini (reassembly), şifreli trafikte içerik yerine metadata'nın nasıl okunacağını ve "normal"i tanımlamadan "anormal"in anlamsız olduğunu kavramayı gerektirir. Savunmacı için asıl kazanım araç kullanmayı ezberlemek değil, altındaki nedensellik zincirini (neden bu paket böyle görünür, neden bu tespit yöntemi işe yarar veya yaramaz) içselleştirmektir — çünkü araçlar değişir, protokoller evrilir, ama katmanlı encapsulation ve istatistiksel sapma tespiti mantığı temel kalır.
