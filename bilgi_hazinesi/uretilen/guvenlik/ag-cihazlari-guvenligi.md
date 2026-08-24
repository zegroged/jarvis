# Ağ Cihazları Güvenliği: Router/Switch Sertleştirme, VLAN Hopping, STP Manipülasyonu, HSRP/VRRP Saldırıları

## Neden Bu Konu Ayrı Bir Başlık?

Firewall ve segmentasyon konuları genellikle "trafik hangi kurala göre geçer/geçmez" sorusuna odaklanır — yani Layer 3/4 katmanındaki erişim kontrolüne. Ancak modern kurumsal ağların gerçek omurgası olan anahtarlama (switching) ve yönlendirme (routing) katmanının kendi protokolleri, kendi güven varsayımları ve kendi zafiyet sınıfları vardır. Bir saldırgan hiçbir firewall kuralını ihlal etmeden, salt Layer 2 protokollerinin (VLAN etiketleme, Spanning Tree Protocol, trunk müzakere protokolleri) tasarım gereği barındırdığı zımni güven ilişkilerini istismar ederek segmentasyonun *kendisini* dolanabilir. Bu, "duvar sağlam ama duvarın içindeki kapı menteşeleri güvenilmez malzemeden" durumuna benzer: erişim kontrol listeleri kusursuz olsa bile, o listelerin uygulandığı fiziksel/mantıksal zemin (switch'in VLAN işleme mantığı, STP'nin kök köprü seçim algoritması) manipüle edilebiliyorsa, üstteki güvenlik modeli anlamını yitirir.

Bu makalenin kapsadığı saldırı sınıfları üç ortak kök nedene dayanır:

1. **Zımni güven**: Layer 2 protokolleri (STP, DTP, CDP/LLDP, HSRP/VRRP) tasarlandıkları dönemde "ağdaki her cihaz iyi niyetlidir" varsayımıyla inşa edilmiştir; kimlik doğrulama ya hiç yoktur ya da opsiyoneldir.
2. **Varsayılan yapılandırmaların güvensizliği**: Fabrika ayarları çoğunlukla "her yerde çalışsın" hedefiyle optimize edilmiştir, "güvenli olsun" hedefiyle değil (örneğin tüm portların otomatik trunk müzakeresine açık gelmesi).
3. **Yönetim düzlemi ile veri düzleminin yetersiz izolasyonu**: Cihazın kendisini yönetmek için kullanılan arayüz (SSH, web arayüzü, SNMP) çoğu zaman aynı ağ üzerinden erişilebilir durumdadır ve bu da cihaz ele geçirildiğinde tüm ağın kontrolünün de düşmesi anlamına gelir.

Aşağıda her saldırı sınıfını kavramsal mekanizması, tespiti ve savunma önlemleriyle birlikte inceliyoruz.

---

## 1. Router/Switch Sertleştirme (Hardening) Temelleri

### Tanım

Sertleştirme, bir ağ cihazının varsayılan/gevşek yapılandırmasından, saldırı yüzeyini asgariye indiren bir yapılandırmaya geçiş sürecidir. Sunucu sertleştirmesinden farklı olarak burada odak işletim sistemi değil, protokol davranışları ve yönetim erişimidir.

### Kök Neden / Çalışma Mantığı

Ağ cihazları iki ayrı "düzlemde" çalışır:

- **Yönetim düzlemi (management plane)**: Cihazın kendisinin nasıl yapılandırılıp izlendiği (SSH, HTTP(S) arayüzü, SNMP, syslog).
- **Kontrol düzlemi (control plane)**: Yönlendirme/anahtarlama kararlarının alındığı protokoller (OSPF, BGP, STP, ARP).
- **Veri düzlemi (data plane)**: Asıl kullanıcı trafiğinin geçtiği yol.

Sertleştirme yapılmadığında bu üç düzlem arasında yeterli izolasyon olmaz: veri düzlemine erişimi olan biri, aynı arayüz üzerinden yönetim düzlemine de sızabilir (örneğin varsayılan VLAN 1 üzerinden hem kullanıcı trafiği hem de yönetim erişimi geçiyorsa).

### Yaygın Zafiyet Kalıpları ve Savunma

**Varsayılan kimlik bilgileri ve zayıf kimlik doğrulama**
Birçok kurulumda cihazlar fabrika şifresiyle veya kolay tahmin edilebilir kimlik bilgileriyle üretime alınır. Savunma: ilk kurulumda zorunlu şifre değişimi, merkezi AAA (TACACS+/RADIUS) entegrasyonu, mümkünse çok faktörlü doğrulama ve rol tabanlı yetkilendirme (salt-okunur operatör ile tam yetkili yönetici ayrımı).

**Yönetim düzleminin düz metin protokollerle açık olması**
Telnet, HTTP (HTTPS değil), SNMP v1/v2c (community string düz metin ve genelde "public"/"private") hâlâ birçok cihazda etkin gelir. Bunlar ağ dinleme (sniffing) ile kimlik bilgilerinin doğrudan ele geçirilmesine yol açar. Savunma: yalnızca SSHv2, HTTPS ve SNMPv3 (kimlik doğrulama + şifreleme ile) kullanmak; kullanılmayan servisleri tamamen kapatmak.

**Yönetim erişiminin veri düzleminden ayrılmaması**
Yönetim arayüzü kullanıcı VLAN'larından erişilebilirse, ele geçirilen bir istemci doğrudan switch/router yönetim paneline ulaşabilir. Savunma: ayrı bir yönetim VLAN'ı / out-of-band yönetim ağı, yönetim erişimine yalnızca belirli kaynak IP'lerden izin veren ACL'ler (`access-class` benzeri mekanizmalar).

**Kullanılmayan servislerin ve portların açık kalması**
CDP/LLDP gibi keşif protokolleri, kullanılmayan fiziksel portlar, gereksiz yönetim servisleri (finger, echo, chargen gibi eski TCP/UDP küçük servisler) saldırı yüzeyini büyütür. Savunma: kullanılmayan fiziksel portları idari olarak kapatmak (`shutdown`) ve ayrı, kullanılmayan bir VLAN'a atamak; CDP/LLDP'yi yalnızca gerekli olan komşuluk bağlantılarında (örneğin IP telefonlarla) etkin bırakmak, kullanıcı-erişim portlarında kapatmak.

**Yapılandırma yedeklerinin ve loglamanın eksikliği**
Sertleştirme aynı zamanda operasyoneldir: değişiklik denetimi (configuration change auditing), merkezi log toplama (syslog'un merkezi bir SIEM'e akıtılması) ve düzenli yapılandırma yedekleri olmadan bir saldırı sonrası "ne değişti" sorusuna cevap vermek neredeyse imkânsızlaşır.

### Tespit

- Cihaz yönetim arayüzlerine yapılan başarısız/başarılı oturum açma denemelerinin merkezi izlenmesi (özellikle mesai dışı saatlerde veya beklenmeyen kaynak IP'lerden gelenler).
- Yapılandırma bütünlüğü izleme: cihaz konfigürasyonunun periyodik hash'lenip referans durumla karşılaştırılması (beklenmeyen `running-config` değişiklikleri alarm üretmeli).
- SNMP sorgu trafiğinin izlenmesi; community string ile brute-force denemelerinin tespiti.

---

## 2. VLAN Hopping

### Tanım

VLAN Hopping, bir saldırganın kendisine atanmış olmayan bir VLAN'daki trafiğe, o VLAN'a fiziksel/mantıksal olarak bağlı olmadan erişebilmesini sağlayan bir teknik sınıfıdır. VLAN'lar mantıksal segmentasyon sağlamak için tasarlanmıştır, ancak bu segmentasyon switch donanımının etiketleme (tagging) mantığına dayanır ve bu mantıktaki zayıflıklar istismar edilebilir.

### Kök Neden / Çalışma Mantığı

İki temel teknik vardır:

**a) Switch Spoofing (DTP İstismarı)**

Cisco gibi üreticilerin switch'lerinde Dynamic Trunking Protocol (DTP), komşu iki switch portunun otomatik olarak "trunk" moduna (yani birden fazla VLAN'ın etiketli olarak taşındığı bağlantı tipine) geçip geçmeyeceğini müzakere eder. Birçok switch portu varsayılan olarak "dynamic auto" veya "dynamic desirable" modunda gelir — yani "karşı taraf trunk istiyorsa ben de trunk olurum" davranışı sergiler.

Kök neden: Bu müzakere sürecinde karşı ucun *gerçekten bir switch mi yoksa sıradan bir bilgisayar mı* olduğuna dair bir doğrulama yoktur. Bir saldırgan, normal bir kullanıcı portuna bağlanıp DTP çerçeveleri göndererek "ben bir switch'im, trunk olalım" diyebilir. Port bunu kabul ederse, saldırganın makinesi artık o switch üzerindeki *tüm* VLAN'ların etiketli trafiğini görebilir/gönderebilir hale gelir — tek bir VLAN'a hapsedilmiş olması gerekirken.

**b) Double Tagging (Çift Etiketleme)**

Bu teknik, "native VLAN" kavramının switch'ler arası trunk bağlantılarında etiketlenmeden taşınmasından yararlanır. Saldırgan, kendi bulunduğu VLAN'ın (genellikle native VLAN, çoğunlukla varsayılan olarak VLAN 1) üzerine iki katmanlı bir 802.1Q etiketi ekleyerek çerçeve gönderir: dıştaki etiket saldırganın kendi (native) VLAN'ını, içteki etiket ise hedef VLAN'ı taşır.

Kök neden mekanizması şudur: Çerçeve ilk switch'e ulaştığında, switch dış etiketin native VLAN'a ait olduğunu görür ve 802.1Q kuralı gereği native VLAN etiketini trunk üzerinden gönderirken *kaldırır* (çünkü native VLAN etiketsiz taşınır). Ancak içteki ikinci etiket bu işlemden sonra ortaya çıkar ve çerçeve artık "hedef VLAN'a ait, etiketli bir çerçeve" gibi görünerek ikinci switch'e ulaşır. İkinci switch bu etiketi okur ve çerçeveyi hedef VLAN'a yönlendirir — saldırganın hiçbir zaman o VLAN'a üye olmamasına rağmen. Bu saldırının kritik bir sınırlaması tek yönlü olmasıdır (genellikle yalnızca gönderim yönünde çalışır, dönüş trafiğini doğrudan göremez), bu yüzden pratikte daha çok "kör" (blind) enjeksiyon saldırıları için (örn. hedef VLAN'a sahte trafik göndermek) kullanılır.

### Tespit

- Trunk portlarında beklenmeyen DTP çerçevelerinin görülmesi (kullanıcı erişim portlarında hiç DTP trafiği olmaması gerekir).
- Aynı fiziksel portta beklenmedik şekilde birden fazla VLAN etiketi taşıyan çerçevelerin (double-tagged frame) switch loglarında veya paket yakalamalarında görülmesi.
- Bir kullanıcı erişim portunun trunk moduna geçtiğine dair switch port durumu değişikliği olayları (SNMP trap / syslog ile izlenebilir).
- Native VLAN'a ait beklenmeyen/anormal trafik hacmi.

### Savunma

- **DTP'yi kullanıcı erişim portlarında tamamen kapatmak**: Portları statik olarak `access` moduna sabitlemek ve DTP müzakeresini devre dışı bırakmak (`switchport nonegotiate` benzeri komutlar). Trunk gereken bağlantılarda da müzakereyi kapatıp iki ucu da manuel/statik trunk olarak yapılandırmak en güvenli yaklaşımdır.
- **Native VLAN'ı kullanılmayan, "çöp" bir VLAN'a atamak**: Native VLAN'ı gerçek kullanıcı/sunucu VLAN'larından tamamen ayrı, hiçbir cihaza atanmamış bir VLAN numarasına sabitlemek, double-tagging saldırısının temel önkoşulunu ortadan kaldırır.
- **Trunk portlarda native VLAN'ı da etiketlemek**: Bazı platformlar tüm VLAN'ları etiketli taşıma seçeneği sunar (native VLAN dahil); bu, dış/iç etiket ayrımına dayanan double-tagging mantığını kırar.
- **VLAN 1'i asla kullanmamak**: VLAN 1 çoğu üreticide varsayılan native/yönetim VLAN'ıdır ve saldırganların ilk hedefidir; kullanıcı ve yönetim trafiğini her zaman özel olarak tanımlanmış, VLAN 1 dışındaki VLAN'lara taşımak gerekir.
- **Kullanılmayan portları erişim moduna sabitleyip kapatmak**.

---

## 3. STP Manipülasyonu (Spanning Tree Protocol Saldırıları)

### Tanım

Spanning Tree Protocol (STP), Layer 2 ağlarında döngüleri (loop) önlemek için tasarlanmış bir protokoldür: birden fazla switch arasında yedekli fiziksel bağlantılar olsa da, STP bu bağlantılardan birini "kök köprü" (root bridge) seçip diğer yolları mantıksal olarak bloklayarak tek bir aktif topoloji oluşturur.

### Kök Neden / Çalışma Mantığı

Kök köprü seçimi, switch'lerin birbirine gönderdiği BPDU (Bridge Protocol Data Unit) çerçevelerindeki "bridge priority" değerine ve bağlantı maliyetlerine dayanır — en düşük öncelik değerine (ve eşitlikte en düşük MAC adresine) sahip switch kök köprü olur. Bu seçim sürecinde **hiçbir kimlik doğrulama yoktur**: ağa bağlanan herhangi bir cihaz, kendi BPDU'sunda çok düşük bir öncelik değeri ilan ederek kök köprü seçilmeyi "iddia edebilir".

Kök köprü olmanın saldırgan açısından değeri şudur: STP topolojisinde tüm trafik akışı kök köprüye göre şekillenir. Kök köprü konumuna geçen bir saldırgan makinesi (tipik olarak iki farklı switch portuna bağlanan, düşük maliyetli bir Linux kutusu ile), normalde birbirine görece "yakın" olan iki switch arasındaki trafiğin kendi üzerinden geçmesini sağlayarak fiili bir **man-in-the-middle** konumuna geçebilir. Ayrıca sürekli topoloji değişikliği (TCN — Topology Change Notification) BPDU'ları göndererek switch'lerin MAC adres tablolarını sürekli boşaltmasına (flush) neden olup ağda performans düşüşüne/DoS'a yol açabilir.

İkinci bir saldırı biçimi ise **BPDU flooding/starvation**dır: switch'in BPDU işleme kapasitesini aşacak sayıda sahte BPDU göndererek kontrol düzlemini yorup kararsız topoloji durumlarına (sürekli yeniden hesaplama, port durumu salınımı) yol açmaktır.

### Tespit

- Kullanıcı erişim portlarında BPDU çerçevelerinin görülmesi (normal bir son kullanıcı cihazı asla BPDU göndermemelidir; bu tek başına güçlü bir anomali göstergesidir).
- Kök köprü kimliğinde beklenmeyen bir değişiklik (syslog/SNMP trap ile "root bridge changed" olayları).
- Anormal sıklıkta Topology Change Notification (TCN) olayları — kısa sürede tekrarlayan TCN'ler saldırı ya da fiziksel katman kararsızlığının işaretidir.
- Beklenmeyen bir portun aniden "designated"/"root" role geçmesi.

### Savunma

- **BPDU Guard**: Yalnızca son kullanıcı cihazlarının bağlı olması gereken erişim portlarında, bu portlardan BPDU alınması durumunda portu otomatik olarak devre dışı bırakan (err-disable) mekanizma. Bu, switch spoofing'e giden en yaygın ilk adımı doğrudan keser.
- **Root Guard**: Belirli portların kök köprü ilan eden (daha üstün/daha düşük öncelikli) BPDU'lar alması durumunda o portu bloke ederek, kök köprünün yalnızca önceden belirlenmiş, güvenilir switch(ler) arasında kalmasını garanti eden mekanizma.
- **PortFast'in yalnızca gerçek erişim portlarında kullanılması** ve mutlaka BPDU Guard ile birlikte etkinleştirilmesi (PortFast tek başına yalnızca port durumu geçişini hızlandırır, güvenlik sağlamaz — bu yüzden BPDU Guard'sız PortFast, saldırı yüzeyini daraltmaz, sadece saldırının daha hızlı işlemesine izin verir).
- **Kök köprü rolünün açıkça ve manuel olarak sabitlenmesi**: Kritik çekirdek switch'lere düşük bridge priority değeri elle atanarak kök köprü konumunun net biçimde belirlenmesi, "en düşük öncelik kazanır" belirsizliğinin saldırgan lehine kullanılmasını zorlaştırır.
- Mümkün olan yerlerde STP'ye alternatif/onu tamamlayan daha modern loop-önleme ve segmentasyon mimarilerinin (örn. Layer 3'e erken geçiş, yedeklilik gerektirmeyen tasarımlar) değerlendirilmesi.

---

## 4. HSRP/VRRP Saldırıları (First-Hop Redundancy Protocol Saldırıları)

### Tanım

HSRP (Hot Standby Router Protocol, Cisco) ve VRRP (Virtual Router Redundancy Protocol, açık standart) gibi First-Hop Redundancy Protocol (FHRP) çözümleri, bir alt ağdaki uç cihazlara tek, sanal bir varsayılan ağ geçidi (default gateway) IP'si sunarken, bu görevi gerçekte birden fazla fiziksel router'ın devralabildiği bir yedeklilik mekanizması kurar. Aktif router çöktüğünde yedek router, kesintisiz biçimde sanal IP/MAC'i devralır.

### Kök Neden / Çalışma Mantığı

Aktif router seçimi, katılımcı router'ların birbirine gönderdiği "hello" mesajlarındaki öncelik (priority) değerine dayanır — en yüksek öncelik kazanır. Kritik zayıflık: bu protokollerin **kimlik doğrulaması varsayılan olarak ya kapalıdır ya da düz metin bir parola ile son derece zayıftır**. Ağa erişimi olan bir saldırgan:

1. Ağdaki gerçek FHRP trafiğini dinleyerek mevcut aktif router'ın önceliğini öğrenir.
2. Kendi sahte bir HSRP/VRRP mesajını, gözlemlenen değerden daha yüksek bir öncelikle yayınlar.
3. Diğer router'lar (protokol tasarımı gereği) "daha yüksek öncelikli biri var" diyerek saldırgana aktif rolü (ve dolayısıyla sanal gateway IP/MAC adresini) bırakır.

Bunun sonucu: ağdaki tüm uç istemcilerin varsayılan ağ geçidine giden trafiği artık **fiziksel olarak saldırganın makinesinden geçer**. Bu, VLAN içi bir man-in-the-middle konumundan çok daha güçlüdür çünkü bu sefer saldırgan yalnızca aynı VLAN içi trafiği değil, o VLAN'dan *dışarı çıkan tüm trafiği* (internet erişimi, diğer VLAN'lara giden yönlendirilmiş trafik) görebilir/manipüle edebilir hale gelir. Saldırgan isterse trafiği pasifçe dinleyip gerçek router'a iletir (şeffaf MITM), isterse trafiği tamamen keserek DoS oluşturur.

### Tespit

- FHRP kimlik doğrulama başarısızlıklarının (yapılandırılmışsa) loglanması.
- Aktif router (HSRP "Active" / VRRP "Master") rolünün beklenmeyen sıklıkta veya beklenmeyen bir cihaza geçmesi — router değişim olayları izlenmeli.
- Ağda beklenen router MAC/IP eşleşmesinin dışında, sanal gateway MAC adresini kullanan yeni/tanınmayan bir fiziksel cihazın (farklı switch portu/farklı gerçek MAC ile) görünmesi.
- Pasif ağ izleme ile aynı öncelik sınıfında beklenmeyen kaynaklardan gelen HSRP/VRRP hello paketlerinin tespiti.

### Savunma

- **FHRP kimlik doğrulamasını etkinleştirmek**: HSRP/VRRP'nin sunduğu kimlik doğrulama mekanizmalarını (mümkünse düz metin değil, hash tabanlı/MD5 türü seçenekleri) mutlaka açmak; bu, sahte hello mesajlarının kabul edilmesini önler.
- **FHRP trafiğinin sadece güvenilir router'lar arasındaki bağlantılarda görülmesini sağlamak**: Kullanıcı erişim VLAN'larında/portlarında HSRP/VRRP çok adresine (multicast/anycast hedef) yönelik trafiği filtreleyen ACL'ler tanımlamak, uç kullanıcı segmentinden sahte FHRP paketi enjekte edilmesini engeller.
- **Öncelik değerlerinin ve "preempt" davranışının bilinçli yapılandırılması**: Hangi router'ın hangi koşulda aktif rolü geri alacağının net tanımlanması, beklenmeyen rol değişikliklerinin daha kolay fark edilmesini sağlar.
- **Ağ izleme ile temel çizgi (baseline) oluşturma**: Sanal gateway MAC'inin normalde hangi fiziksel router'lar arasında geçiş yaptığının bilinmesi, anomalinin (üçüncü, bilinmeyen bir kaynağın bu role soyunması) hızla fark edilmesini sağlar.

---

## 5. Router/Switch İşletim Sistemi Zafiyetleri

### Tanım

Bu kategori, yukarıdaki protokol seviyesi saldırılardan farklı olarak, cihazların çalıştırdığı gömülü işletim sisteminin (Cisco IOS/IOS-XE, Juniper Junos ve benzerleri) kendisindeki yazılım zafiyetlerini kapsar: bellek bozulması zafiyetleri, kimlik doğrulama atlatmaları, yetersiz girdi doğrulaması gibi klasik yazılım güvenlik açığı sınıflarının ağ cihazı bağlamındaki karşılıkları.

### Kök Neden / Çalışma Mantığı

Ağ cihazı işletim sistemleri de sonuçta yazılımdır ve genel yazılım zafiyet sınıflarına tabidir: bellek yönetimi hataları, ayrıştırıcı (parser) zafiyetleri (özellikle SNMP, web yönetim arayüzü, belirli paket başlıklarını işleyen kod yollarında), yetkilendirme mantığı hataları. Bu cihazların özel olarak riskli olmasının nedeni şudur:

- **Yama uygulama döngüsü genellikle çok yavaştır**: Sunuculardan farklı olarak router/switch güncellemeleri genelde planlı bakım pencereleri gerektirir (kesinti riski), bu da bilinen zafiyetlerin üretim ortamında aylarca/yıllarca açık kalmasına yol açar.
- **Tek bir cihaz, çok geniş bir "blast radius" (etki alanı) taşır**: Bir çekirdek switch veya sınır router'ın ele geçirilmesi, arkasındaki tüm segmentlerin güvenliğini aynı anda tehlikeye atar — bu, tek bir sunucunun ele geçirilmesinden çok daha yıkıcı bir kapsam genişlemesidir (özellikle cihaz hem kontrol hem veri düzlemini aynı anda etkiliyorsa).
- **Yönetim arayüzlerinin internete açık bırakılması**: Bazı kurulumlarda cihazların web tabanlı yönetim arayüzü veya SSH servisi yanlışlıkla veya "geçici olarak" internetten erişilebilir bırakılır; bu, uzaktan istismar edilebilir zafiyetlerin doğrudan internetten tetiklenmesini mümkün kılar.
- **Tedarik zinciri ve gömülü kimlik bilgileri**: Bazı geçmiş olaylarda, üretici tarafından gömülmüş (hardcoded) yönetim kimlik bilgileri veya arka kapı benzeri erişim mekanizmaları ortaya çıkmıştır; bunlar cihaz üreticisinin yazılım geliştirme sürecindeki denetim eksikliklerinden kaynaklanır.

Somut CVE numaraları ve kesin sürüm bilgileri zaman içinde hızla değiştiği ve üreticiye/modele göre çeşitlendiği için burada belirli bir numara/sürüm iddia etmiyorum — güncel ve doğru bilgi için üreticinin güvenlik danışma (security advisory) yayınları takip edilmelidir. Önemli olan kavram şudur: **ağ cihazı işletim sistemleri "kur ve unut" değil, sunucular gibi düzenli yama ve envanter yönetimi gerektiren varlıklardır.**

### Tespit

- Cihaz üzerinde beklenmeyen/yetkisiz yapılandırma değişiklikleri (konfigürasyon bütünlük izleme ile).
- Cihazın normalden farklı davranması: beklenmedik yeniden başlatmalar (kilitlenme/çökme, olası exploit denemesinin belirtisi olabilir), CPU/bellek kullanımında ani sıçramalar.
- Yönetim arayüzüne yönelik anormal tarama/istismar denemesi imzaları (IDS/IPS imzaları üretici danışmalarına göre güncel tutulmalı).
- Cihaz üzerinde beklenmeyen yeni kullanıcı hesapları, SNMP community string değişiklikleri veya yeni erişim kuralları.
- Ağ varlık envanterinin (hangi cihaz, hangi donanım/yazılım sürümü) güncel ve merkezi tutulması — bu, hangi cihazların bilinen bir zafiyetten etkilendiğini hızlıca belirlemenin ön koşuludur.

### Savunma

- **Düzenli ve zamanında yama yönetimi**: Üretici güvenlik danışmalarının takip edilmesi, kritik zafiyetler için hızlandırılmış bakım pencereleri süreci tanımlanması.
- **Yönetim arayüzlerinin asla doğrudan internete açık bırakılmaması**: Yönetim erişimi VPN/jump host/bastion üzerinden, sıkı ACL'lerle sınırlanmalı.
- **Gereksiz servislerin kapatılması** (bkz. Bölüm 1) — saldırı yüzeyi küçüldükçe, işletim sistemi zafiyetlerinin istismar edilebilir yolu da azalır.
- **Donanım/yazılım envanterinin merkezi tutulması** ve düzenli zafiyet taraması (mümkünse üretici destekli araçlarla) yapılması.
- **Defence-in-depth**: Tek bir cihazın ele geçirilmesinin tüm ağı çökertmemesi için segmentasyon, en az ayrıcalık ilkesiyle yapılandırılmış yönetim erişimi ve kritik cihazlar için yedekli/çeşitlendirilmiş (farklı model/üretici) mimari tercih edilmesi.

---

## Yaygın Hatalar (Tüm Kategoriler İçin Özet)

- **"Segmentasyon var, o zaman güvenliyiz" varsayımı**: VLAN'ların salt mantıksal ayrım sağladığını, ancak alttaki switch/protokol mantığı sertleştirilmediği sürece bu ayrımın atlatılabilir olduğunu göz ardı etmek.
- **Varsayılan yapılandırmaların üretime taşınması**: DTP'nin auto/desirable modda bırakılması, VLAN 1'in native/yönetim VLAN'ı olarak kullanılmaya devam etmesi, FHRP kimlik doğrulamasının hiç açılmaması.
- **PortFast'in BPDU Guard olmadan kullanılması**: Hız kazandırırken güvenlik açığı bırakmak.
- **Yönetim ve veri düzlemlerinin aynı VLAN/ağ üzerinde karışması**.
- **Ağ cihazlarının yama döngüsünün sunuculardan ayrı, daha gevşek bir sürece tabi tutulması** — "kesinti riski" gerekçesiyle kritik güvenlik yamalarının aylarca ertelenmesi.
- **İzleme ve loglamanın yalnızca sunucu/uygulama katmanına odaklanıp Layer 2/kontrol düzlemi olaylarının (BPDU değişiklikleri, FHRP rol değişimleri, DTP müzakereleri) izlenmemesi** — bu, yukarıda tarif edilen saldırıların çoğunun günlerce/haftalarca fark edilmeden sürebilmesinin başlıca nedenidir.

## Sonuç

Router/switch güvenliği, firewall ve segmentasyon politikalarının *üzerine* inşa edildiği temeldir; bu temel sertleştirilmemişse üstteki tüm kontroller kâğıt üzerinde kalır. VLAN hopping, STP manipülasyonu ve FHRP saldırılarının ortak paydası, Layer 2/kontrol düzlemi protokollerinin tasarım gereği taşıdığı zımni güvenin istismar edilmesidir — bunlara karşı savunma çoğunlukla karmaşık teknoloji değil, **disiplinli, açık ve varsayılanları sorgulayan yapılandırma** (BPDU Guard, Root Guard, statik trunk/access modları, FHRP kimlik doğrulama, yönetim düzlemi izolasyonu) ve bu kontrol düzlemi olaylarının aktif biçimde izlenmesidir.
