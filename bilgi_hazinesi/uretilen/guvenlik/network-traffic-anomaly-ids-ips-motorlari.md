# Network Traffic Anomaly / IDS-IPS Motorları: Snort/Suricata Kural Yazımı ve NetFlow/sFlow Analizi

## Giriş: Bu Konu Neden Ayrı Bir Beceridir

SIEM kurulumu, Sigma kuralları ve genel "detection engineering" pratikleri çoğunlukla **log tabanlı** çalışır: endpoint ajanı bir olay üretir, log toplayıcı onu taşır, SIEM bir korelasyon kuralıyla eşler. Bu model güçlüdür ama tek bir katmana bağımlıdır — eğer endpoint ajanı susturulmuşsa, log iletimi kesilmişse ya da saldırgan henüz bir uç noktaya (endpoint) dokunmamışsa, log tabanlı görünürlük kördür.

Ağ katmanı (network layer) bu körlüğe karşı **bağımsız bir ikinci tanık** sağlar. Paketler ve akış kayıtları (flow records), uç noktadaki ajanın durumundan etkilenmeden, kablo üzerinde (on the wire) veya switch/router üzerinde pasif olarak toplanabilir. Bu yüzden IDS/IPS (Intrusion Detection/Prevention System) motorları ve NetFlow/sFlow analizi, SIEM/Sigma dünyasının üstüne inşa edilen değil, onunla **paralel ve tamamlayıcı** bir savunma katmanıdır. Bir kurumsal ağ güvenliği mimarisinin merkezinde bu ikisi olmadan gerçek bir "derinlemesine savunma" (defense in depth) iddiası eksik kalır.

Bu makale iki ayrı ama birbirini besleyen beceriyi ele alır:
1. **İmza/anomali tabanlı IDS/IPS motorları** (Snort, Suricata) — paket içeriğine bakan, "ne" iletildiğini tespit eden katman.
2. **NetFlow/sFlow analizi** — paket içeriğine bakmayan ama "kim kiminle, ne kadar, ne zaman konuştu" sorusuna cevap veren hacimsel (volumetric) görünürlük katmanı.

---

## Kısım 1: İmza ve Anomali Tabanlı IDS/IPS Motorları

### 1.1 Tanım ve Temel Ayrım: IDS mi, IPS mi?

**IDS (Intrusion Detection System)**, ağ trafiğini pasif olarak izleyip şüpheli/kötü niyetli örüntüleri tespit eden ve alarm üreten bir sistemdir — trafiği durdurmaz, sadece görür ve bildirir. Genellikle bir **SPAN/mirror port** veya **network TAP** üzerinden trafiğin bir kopyasını alır (out-of-band).

**IPS (Intrusion Prevention System)**, aynı tespit mantığını kullanır ama trafiğin **akış yolunun üzerine (inline)** yerleştirilir; bir tespit eşleştiğinde paketi düşürebilir (drop), bağlantıyı sıfırlayabilir (reset) veya IP'yi kara listeye alabilir. Bu, tespiti **engellemeye** dönüştürür ama beraberinde kritik bir mühendislik riski getirir: **yanlış pozitif (false positive) durumunda IPS meşru trafiği keser** — yani IPS'in kendisi bir kullanılabilirlik (availability) riskidir. Bu yüzden IPS kuralları IDS kurallarından çok daha muhafazakâr (conservative) yazılmalı ve yeni kurallar önce "alert-only/IDS modunda" devreye alınıp bir süre gözlemlendikten sonra "block/drop moduna" terfi ettirilmelidir. Bu ayrım — tespit güveni ile engelleme kararı arasındaki mesafe — IDS/IPS mühendisliğinin kök felsefesidir.

### 1.2 Kök Neden / Çalışma Mantığı: Neden Bu Motorlara İhtiyaç Var?

Bir SIEM'in görebildiği "olay", genellikle bir uygulamanın veya işletim sisteminin *kendi kaydettiği* bir şeydir. Ama saldırganın ağ üzerinden gönderdiği ham paket — örneğin bir exploit'in shellcode'unu taşıyan TCP segmenti, ya da bir C2 (command and control) protokolünün karakteristik bayt dizisi — hiçbir uygulama logunda görünmeyebilir. Kök neden şudur: **ağ, uygulamadan önce gelir**. Paket önce kabloda vardır, sonra uygulamaya ulaşır (ya da hiç ulaşmaz, çünkü exploit henüz başarısızdır). IDS/IPS bu ilk temas noktasında durur ve şunu sorar: *"Bu baytlar, bilinen kötü bir örüntüyle mi eşleşiyor (imza tabanlı), yoksa bu protokol için beklenenden sapan bir davranış mı sergiliyor (anomali tabanlı)?"*

İki tespit felsefesi birbirini tamamlar:

- **İmza tabanlı (signature-based) tespit**: Bilinen bir saldırı örüntüsünün bayt dizisi, regex'i veya protokol alanı imzası önceden tanımlanır (ör. belirli bir exploit'in payload'ındaki sabit bir dize, ya da bilinen bir web shell'in User-Agent'ı). Güçlü yanı: düşük yanlış pozitif, yüksek kesinlik. Zayıf yanı: **sadece bilineni** yakalar; imza veritabanında olmayan (0-day, obfuscate edilmiş, varyant) saldırıları kaçırır (false negative).
- **Anomali tabanlı (anomaly-based) tespit**: "Normal" trafiğin istatistiksel bir taban çizgisi (baseline) çıkarılır; bu çizgiden sapan davranış (ör. anormal paket boyutu dağılımı, beklenmeyen protokol kombinasyonu, olağandışı bağlantı sıklığı) şüpheli sayılır. Güçlü yanı: bilinmeyen/yeni saldırıları da yakalayabilir. Zayıf yanı: "normal" tanımı ortama göre değişir, taban çizgisi kötü çıkarılırsa yanlış pozitif patlaması olur, ve saldırgan yavaş/kademeli hareket ederek taban çizgiyi kaydırabilir (baseline poisoning).

Modern motorlar (Snort 3, Suricata) ikisini birleştirir: imza kuralları + protokol anomali tespiti (protocol anomaly detection, ör. bir HTTP başlığının RFC'ye aykırı biçimlendirilmesi) + bazı ML/istatistik eklentileri.

### 1.3 Mimari: Nasıl Çalışır (Kavramsal)

Bir IDS/IPS motorunun işlem hattı (pipeline) kavramsal olarak şu aşamalardan geçer:

1. **Paket yakalama (packet capture)**: libpcap/AF_PACKET/DPDK gibi bir mekanizma ile ham paketler kernel'den kullanıcı alanına (userspace) veya doğrudan motor sürecine aktarılır.
2. **Ön işleme / decode**: Ethernet → IP → TCP/UDP → uygulama katmanı olarak paket ayrıştırılır (decode edilir).
3. **Akış yeniden birleştirme (stream reassembly / TCP reassembly)**: TCP parçalanmış (fragmented) veya sıra dışı (out-of-order) gelen segmentleri, hedef makinenin göreceği gibi yeniden birleştirir. Bu adım **kritiktir** çünkü saldırganlar kasıtlı olarak paketleri parçalayarak (fragmentation, segmentation) imza eşleşmesinden kaçmaya çalışır (evasion) — motor eğer hedef host'un TCP/IP yığınının davranışını doğru taklit etmezse (ör. hangi çakışan segmenti önce/sonra kabul ettiği), saldırgan bu farktan yararlanarak IDS'e görünmez, hedefe görünür bir payload gönderebilir. Bu, Ptacek & Newsham'ın 1998'de formelleştirdiği klasik IDS evasion sorunudur ve hâlâ geçerlidir.
4. **Protokol ayrıştırma (protocol parsing / app-layer decoders)**: HTTP, TLS, DNS, SMB gibi protokoller ayrıştırılıp normalize edilir (ör. URL encode/decode, HTTP chunked transfer birleştirme).
5. **Tespit motoru (detection engine)**: Kurallar (imza) ve/veya anomali modelleri normalize edilmiş veriye uygulanır.
6. **Aksiyon**: Alert üret (IDS), veya drop/reject/reset (IPS).

### 1.4 Suricata ve Snort Kural Yazımı: Mantık ve Sözdizimi Kavramı

Snort ve Suricata (Suricata, Snort kural formatına büyük ölçüde uyumludur ve onu genişletir) kuralları kavramsal olarak iki bölümden oluşur:

**Başlık (header)**: `aksiyon protokol kaynak_ip kaynak_port yön hedef_ip hedef_port`
Örnek kavramsal yapı: `alert tcp $EXTERNAL_NET any -> $HOME_NET 445 (...)` — burada "dış ağdan iç ağın 445 (SMB) portuna giden TCP trafiğinde alarm üret" denmektedir.

**Seçenekler (options)**: Parantez içinde, eşleşme koşullarını ve meta veriyi tanımlar. Kavramsal olarak en önemli seçenek kategorileri:
- **`content`**: Paket içinde aranacak sabit bayt dizisi/dize (ör. bilinen bir exploit payload'ı imzası). `nocase` ile büyük/küçük harf duyarsızlığı eklenebilir.
- **Konumlandırma değiştiricileri (`offset`, `depth`, `distance`, `within`)**: `content` eşleşmesinin paket içinde *nerede* aranacağını sınırlar — bu hem performans (her paketi baştan sona taramak yerine belirli bölgeye bakmak) hem de **yanlış pozitifi azaltmak** için kritiktir; aynı bayt dizisi paketin başka bir yerinde masumca geçebilir.
- **`pcre`**: Regex tabanlı, daha esnek ama daha maliyetli (CPU) eşleşme; sabit content ile ön filtreleme yapılıp pcre'nin sadece adayları incelemesi tercih edilir (performans nedeniyle).
- **Protokol-özel anahtarlar (Suricata'da özellikle zengin)**: `http.uri`, `http.header`, `tls.sni`, `dns.query` gibi normalize edilmiş alan eşleştiriciler — bu, ham `content` aramasından daha güvenilirdir çünkü encoding/obfuscation varyasyonlarını motor zaten normalize etmiştir.
- **`flow`**: Bağlantının yönü ve durumu (ör. `established`, `to_server`) — tek yönlü/stateless eşleşmeyi engeller, gürültüyü azaltır.
- **`flowbits`**: Çok adımlı bir saldırı örüntüsünü (ör. önce X isteği, sonra Y yanıtı) birden fazla kural arasında **durum (state)** taşıyarak ilişkilendirmeye yarar — tek paketlik değil, bir *diyalog* örüntüsü tespiti sağlar.
- **`threshold` / `detection_filter`**: Aynı eşleşmenin belirli bir zaman aralığında kaç kez tekrarlandığında alarm üretileceğini kontrol eder — brute-force gibi tekrar temelli saldırılarda tek paket değil *sıklık* önemlidir; bu olmadan her deneme ayrı alarm üretip SOC'u (Security Operations Center) alarm yorgunluğuna (alert fatigue) sürükler.
- **`metadata`, `classtype`, `sid`, `rev`**: Kuralın kimliği, sınıflandırması ve versiyonu — SOC triyajı (triage) ve kural yönetimi için zorunludur.

**Neden bu yapı böyle?** Çünkü ham bir "bu bayt dizisini gördüğünde alarm ver" kuralı hem çok fazla yanlış pozitif üretir (aynı bayt dizisi meşru trafikte de geçebilir) hem de kolayca atlatılır (encoding değişince eşleşme kaybolur). Kural yazarının işi, imzayı **mümkün olduğunca spesifik** (yanlış pozitifi azaltmak için: doğru protokol, doğru yön, doğru konum, doğru bağlam) ama **mümkün olduğunca genel** (varyantları da yakalamak için: tam dize yerine karakteristik bir alt-dizi, ya da davranışsal bir örüntü) tutmak arasında bir denge kurmaktır. Bu denge kurulamazsa iki uç sonuç ortaya çıkar: ya SOC alarm gürültüsünde boğulur ya da kural hiçbir gerçek saldırıyı yakalamaz.

### 1.5 Tespit: Operasyonel Olarak Ne Yapılır

- **Kural kaynakları**: Topluluk kural setleri (Emerging Threats/ET Open, Snort community rules) temel bir başlangıç sağlar; ancak kör bir şekilde hepsini aktif etmek gürültü doğurur. Ortama özgü ayarlama (tuning) zorunludur.
- **Ağ değişkenlerinin doğru tanımlanması**: `$HOME_NET`, `$EXTERNAL_NET` gibi değişkenlerin gerçek ağ topolojisini yansıtması, kuralın doğru yönde çalışması için temel şarttır — yanlış tanımlanmış `$HOME_NET`, hem yanlış pozitif hem de kritik yanlış negatiflere yol açar.
- **App-layer (uygulama katmanı) loglama**: Suricata'nın EVE JSON çıktısı (`eve.json`) sadece alarm değil, HTTP/TLS/DNS/SSH gibi protokol meta verisini de zenginleştirilmiş biçimde üretir — bu çıktı SIEM'e beslenerek imza-tabanlı alarmlarla ilişkilendirilebilir (correlation) ve imza olmasa bile "bu bağlantı garip bir TLS SNI'sine gitti" gibi bağlamsal tespit yapılabilir.
- **Performans izleme**: IDS/IPS motoru paket kaybederse (packet drop, genelde CPU/bant genişliği yetersizliğinden) o kayıp trafik hiç görülmez — bu sessiz bir kör nokta oluşturur. Motorun kendi istatistiklerini (drop oranı, ring buffer doluluk) izlemek, "kural çalışıyor ama trafiği hiç görmüyor" durumunu ayırt etmek için şarttır.
- **Kural test döngüsü**: Yeni kural önce IDS/alert-only modda devreye alınır, bir süre (genelde günler-haftalar) gerçek trafikte gözlemlenir, yanlış pozitif oranı kabul edilebilir seviyeye indirildikten sonra IPS/block moduna terfi ettirilir.

### 1.6 Savunma: Nasıl Güçlendirilir

- **Katmanlama**: IDS/IPS tek başına yeterli değildir; TLS içindeki trafiği göremez (aksi halde TLS inspection/decryption altyapısı gerekir, ki bu ayrı bir mimari ve gizlilik/performans maliyeti taşır). Bu yüzden IDS/IPS, endpoint tespiti ve SIEM korelasyonu ile birlikte katmanlanmalıdır.
- **Segmentasyon ile birlikte konumlandırma**: Motoru sadece ağ sınırına (perimeter) değil, kritik segmentlerin (ör. yönetim ağı, OT/ICS ağı, veri merkezi içi doğu-batı trafiği) arasına da yerleştirmek, "sınırı geçen saldırgan artık serbest" varsayımını kırar.
- **IPS'i kademeli devreye alma**: Yukarıda anlatılan alert-only → block geçişini disiplinli uygulamak, üretim kesintisi riskini azaltır.
- **Kural hijyeni**: Kullanılmayan/güncel olmayan kuralları periyodik gözden geçirmek, imza veritabanını güncel tutmak (yeni CVE'ler için kural gecikmesi bir pencere/gap oluşturur).
- **Evasion'a dayanıklılık**: Motorun TCP reassembly ve fragment yeniden birleştirme davranışını, korunan ağdaki gerçek host/işletim sistemi davranışıyla mümkün olduğunca örtüştürecek şekilde yapılandırmak (target-based reassembly) — bu, Ptacek&Newsham tipi atlatmaları azaltır.

### 1.7 Yaygın Hatalar

- Topluluk kural setini hiç ayarlamadan (tuning yapmadan) doğrudan IPS/block modunda devreye almak — kaçınılmaz olarak meşru trafiği keser.
- `$HOME_NET`/`$EXTERNAL_NET` değişkenlerini varsayılan/yanlış bırakmak.
- Aşırı geniş `content` eşleşmeleri (konum kısıtlaması olmadan) yazıp performans ve yanlış pozitif sorunlarına yol açmak.
- TLS ile şifrelenmiş trafiğe "içerik" bazlı imza yazmaya çalışmak — şifreli payload içinde `content` araması anlamsızdır; bunun yerine TLS meta verisi (SNI, sertifika, JA3/JA3S benzeri parmak izi kavramları) kullanılmalıdır.
- Motorun paket düşürdüğünü (drop) fark etmemek ve "kural sessiz kaldı = saldırı yok" yanılgısına düşmek.
- Threshold/detection_filter kullanmadan tekrarlayan olaylarda (tarama, brute-force) binlerce ayrı alarm üretip SOC'u yormak.

---

## Kısım 2: NetFlow/sFlow ile Hacimsel Trafik Görünürlüğü

### 2.1 Tanım ve IDS/IPS'ten Farkı

**NetFlow** (Cisco kaynaklı, IPFIX olarak standartlaştırılmış) ve **sFlow** (örnekleme tabanlı, sample-based), paketlerin **içeriğine değil**, **meta verisine** bakan görünürlük teknolojileridir. Bir "akış" (flow) kaydı tipik olarak şunları içerir: kaynak/hedef IP, kaynak/hedef port, protokol, başlangıç/bitiş zamanı, bayt/paket sayısı, TCP bayrakları (flags), giriş/çıkış arayüzü.

Kök fark şudur: IDS/IPS "bu paketin *içinde ne yazıyor*" sorusuna cevap verirken, NetFlow/sFlow "bu iki uç noktanın *ne kadar ve nasıl bir örüntüde* konuştuğu" sorusuna cevap verir. Bu, **ölçeklenebilirlik** açısından hayati bir ayrımdır: bir çekirdek (core) router veya büyük bir omurga (backbone) bağlantısında her paketin tam içeriğini derin paket incelemesi (deep packet inspection, DPI) ile analiz etmek hesaplama açısından pahalıdır ve şifreli trafikte zaten mümkün değildir; ama akış meta verisini toplamak çok daha hafiftir ve şifreleme bu görünürlüğü etkilemez (çünkü IP başlıkları ve port bilgisi şifrelenmez).

**NetFlow/IPFIX**, genelde router/switch üzerinde **her akış için** (ya da örnekleme oranıyla) bir kayıt üretir ve bir toplayıcıya (collector) export eder. **sFlow**, paket düzeyinde rastgele örnekleme (ör. her N paketten birini yakala) artı arayüz sayaçlarını periyodik olarak export eder — bu, çok yüksek hızlı (high-speed) omurga bağlantılarında NetFlow'un tam-akış muhasebesinden daha düşük maliyetlidir, ama istatistiksel bir tahmin olduğu için küçük/kısa akışları kaçırma ihtimali taşır.

### 2.2 Kök Neden / Çalışma Mantığı: Neden Bu Görünürlüğe İhtiyaç Var?

Şifreli trafiğin (TLS 1.3, VPN tünelleri) yaygınlaşması, imza tabanlı DPI'ın etkinliğini azalttı: paketin içeriğine bakarak "bu bir C2 payload'ı" demek artık çoğu zaman mümkün değil. Ama saldırganın **davranışı** — hangi host'un, ne zaman, kaç host'a, ne hacimde veri gönderdiği — şifrelemeden etkilenmez. Bu, savunmanın "içeriğe bakamıyorsam davranışa bakarım" mantığına kaymasının kök nedenidir. NetFlow/sFlow tam da bu davranışsal görünürlüğü sağlar:

- **Veri sızdırma (data exfiltration)**: Normalde küçük istekler gönderen bir sunucudan aniden büyük hacimde giden (outbound) trafik — içerik şifreli olsa bile *hacim* anomali sinyalidir.
- **C2 sinyalizasyonu (beaconing)**: Bir host'un düzenli aralıklarla (ör. her 60 saniyede) aynı dış IP'ye kısa bağlantılar açması — periyodiklik (periodicity) davranışsal bir imzadır, paket içeriği bilinmese de tespit edilebilir.
- **Yanal hareket (lateral movement)**: İç ağda normalde birbirleriyle konuşmayan iki host'un aniden SMB/RDP gibi portlarda konuşmaya başlaması — "kim kiminle konuşuyor" grafiği (network communication graph) bu tür sapmaları ortaya çıkarır.
- **Port/host taraması (scanning)**: Bir kaynağın çok sayıda hedefe/porta kısa süre içinde bağlantı denemesi — akış kayıtlarındaki "tek kaynak - çok hedef" örüntüsü klasik bir tarama imzasıdır.
- **DDoS/hacimsel anomali**: Bir arayüze gelen trafik hacminin/paket sayısının taban çizgiden aşırı sapması.

### 2.3 Nasıl Çalışır (Kavramsal Mimari)

1. **Dışa aktarıcı (exporter)**: Router/switch/güvenlik duvarı, geçen trafiği akışlara gruplar (5-tuple: kaynak IP, hedef IP, kaynak port, hedef port, protokol — bazı sürümlerde ek alanlarla) ve bu akış özetlerini periyodik olarak bir toplayıcıya gönderir.
2. **Toplayıcı (collector)**: Akış kayıtlarını alır, depolar, indeksler.
3. **Analiz katmanı**: Toplanan akışlar üzerinde taban çizgisi (baseline) çıkarılır — "bu segment normalde şu kadar trafik üretir, şu host'larla konuşur" gibi. Sapmalar, iş kuralları (business logic) veya istatistiksel eşiklerle (threshold, standart sapma tabanlı) işaretlenir.
4. **Korelasyon**: Flow verisi, DNS logları, IDS alarmları ve SIEM olaylarıyla ilişkilendirilerek zenginleştirilir (enrichment) — tek başına bir flow kaydı genelde yeterli bağlam taşımaz, ama diğer kaynaklarla birleşince güçlü bir tespit sinyaline dönüşür.

### 2.4 Tespit: Operasyonel Olarak Ne Aranır

- **Taban çizgisi sapması**: Saatlik/günlük normal trafik hacminin dışına çıkan ani artışlar (özellikle giden trafikte).
- **Periyodiklik analizi**: Aynı iç host - dış IP çifti arasında düzenli zaman aralıklı, benzer boyutlu bağlantılar (klasik beacon örüntüsü).
- **"Tek kaynak - çok hedef" ve "tek hedef - çok kaynak" örüntüleri**: Sırasıyla tarama ve olası DDoS/kimlik doğrulama saldırısı (credential stuffing) göstergesi.
- **Beklenmeyen protokol/port kombinasyonları**: Ör. iç ağda normalde kullanılmayan bir portta ani trafik artışı, ya da standart olmayan bir portta tünellenen (tunneled) trafik.
- **Asimetrik akışlar**: Çok fazla giden veri, çok az gelen yanıt (ya da tersi) — normal istemci-sunucu davranışından sapma, sızdırma veya tarama göstergesi olabilir.
- **Yeni/nadir görülen dış IP'lerle iç host konuşması**: Özellikle kritik segmentlerden (ör. veritabanı sunucuları) daha önce hiç konuşulmamış dış adreslere giden bağlantılar.

### 2.5 Savunma: Nasıl Güçlendirilir

- **Kapsamlı export noktaları**: Sadece sınır router'da değil, iç omurga ve kritik segment sınırlarında da flow export etkinleştirmek — yanal hareket sadece sınırda değil, iç ağda görünür.
- **Yeterli saklama süresi (retention)**: Bir olay genelde günler/haftalar sonra fark edilir; flow verisinin makul bir süre saklanması, geriye dönük araştırma (retrospective investigation) için gereklidir.
- **Taban çizgisinin periyodik güncellenmesi**: Ağ topolojisi ve iş yükleri değiştikçe (yeni servisler, mevsimsel trafik) taban çizgi de güncellenmeli; aksi halde ya eski taban çizgi anlamsızlaşır ya da saldırgan yavaş bir kayma ile yeni "normali" saldırgan lehine kaydırabilir (bu son nokta bir yaygın hata olarak da aşağıda tekrar geçer).
- **Flow + DPI + log üçlüsünün birleştirilmesi**: Flow "kim kiminle ne kadar konuştu" der, IDS/IPS (mümkünse) "ne konuştu" der, endpoint/uygulama logu "ne yaptı" der — üçü birlikte tam resim oluşturur.
- **sFlow kullanılan ortamlarda örnekleme oranının bilinçli seçilmesi**: Çok düşük örnekleme oranı (ör. 1/10000) kısa/küçük akışları ve düşük hacimli ama kritik sinyalleri (ör. tek bir C2 handshake'i) kaçırabilir; oran, bağlantının hızı ile analitik hassasiyet ihtiyacı arasında bilinçli dengelenmelidir.

### 2.6 Yaygın Hatalar

- Flow verisini toplamak ama hiç taban çizgisi çıkarmadan/analiz etmeden sadece "arşivlemek" — veri var ama tespit yok.
- Sadece sınır (perimeter) noktasında export etkinleştirip iç ağ (doğu-batı, east-west) trafiğini hiç görmemek — yanal hareket bu kör noktada kaybolur.
- sFlow'un istatistiksel örnekleme olduğunu unutup, örneklenen veriyi NetFlow'un tam-akış muhasebesi gibi kesin sayı olarak yorumlamak.
- Taban çizgiyi bir kez çıkarıp bir daha güncellememek — ağ değiştikçe taban çizgi anlamsızlaşır ya da saldırgan kademeli sapmalarla (slow drift) tespiti atlatır.
- Flow verisini izole analiz edip DNS/proxy/IDS loglarıyla hiç ilişkilendirmemek — tek başına bir IP/port çifti çoğu zaman yeterli bağlam taşımaz, yanlış yorum riski yüksektir.
- Şifreli trafikte "içerik göremiyoruz, o zaman flow da işe yaramaz" yanılgısına düşmek — davranışsal sinyal (hacim, periyodiklik, iletişim grafiği) şifrelemeden bağımsız çalışır ve bu tam da flow analizinin var oluş nedenidir.

---

## Sonuç: İki Katmanın Birlikte Değeri

İmza/anomali tabanlı IDS/IPS, "neyin" iletildiğine dair yüksek çözünürlüklü ama pahalı ve şifrelemeye karşı kör bir görüş sağlar. NetFlow/sFlow, "kimin kiminle nasıl bir örüntüde konuştuğuna" dair düşük çözünürlüklü ama ucuz, ölçeklenebilir ve şifrelemeden etkilenmeyen bir görüş sağlar. Bir saldırganın hem imza üretebileceği ham paket içeriğinden kaçınması (encoding, TLS, fragmentation) hem de davranışsal örüntüsünü (hacim, zamanlama, iletişim grafiği) tamamen gizlemesi çok daha zordur — çünkü davranış, protokolün kendisinden bağımsız olarak fiziksel/istatistiksel bir iz bırakır. Bu yüzden olgun bir ağ güvenliği mimarisi bu iki katmanı SIEM/Sigma tabanlı log korelasyonunun *yerine* değil, *yanına* koyar; üçü birlikte, tek bir katmanın kör noktalarını diğer ikisinin kapatmasını sağlayan bir savunma derinliği oluşturur.
