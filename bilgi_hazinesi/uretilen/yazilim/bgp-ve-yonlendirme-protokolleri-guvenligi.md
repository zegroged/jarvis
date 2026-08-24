# BGP ve Yönlendirme Protokolleri Güvenliği

## Giriş: Neden Bu Konu Kritik

İnternet, tek bir merkezi otoritenin yönettiği bir ağ değildir; onbinlerce bağımsız işletim sistemi (Autonomous System, AS) arasında dinamik olarak kurulan güven ilişkilerinin toplamıdır. Bu ilişkileri kuran protokol **BGP (Border Gateway Protocol)**'dur. BGP, "şu IP bloğuna giden trafiği bana yönlendirin, ben oraya ulaştırırım" diyen bir duyuru (announcement) mekanizmasıdır ve tasarımı gereği **güvene dayalıdır (trust-based)**, kimlik doğrulaması değildir. Bir AS, teknik olarak sahibi olmadığı bir IP prefix'ini duyurabilir ve komşu router'lar bunu sorgulamadan kabul edebilir.

Bu zafiyet soyut bir teorik risk değildir: gerçek dünyada devlet destekli aktörlerin trafik dinleme (mass surveillance) operasyonlarından kripto para borsalarına yönelik saldırılara, büyük içerik sağlayıcıların (CDN, DNS kök sunucuları) saatlerce erişilemez hale gelmesine kadar defalarca kullanılmıştır. Bir saldırgan BGP hijack yaparak trafiği kendi üzerinden geçirip TLS trafiğini downgrade edebilir, sahte sertifika alabilir (Certificate Authority'lerin domain doğrulaması genellikle IP'ye dayanır) veya basitçe hizmeti kesintiye uğratabilir (blackhole). Kurumsal ağ güvenliği konuşulurken genellikle firewall, VPN, uç nokta güvenliği ele alınır; ama şirketin internete çıkışını taşıyan yönlendirme katmanı çoğu zaman kör noktadır. Bu makale, BGP'nin çalışma mantığını, saldırı sınıflarını, RPKI/ROV ile savunmayı ve iç ağ yönlendirme protokollerinin (OSPF, EIGRP) güvenlik yönlerini bir savunma mühendisi bakış açısıyla ele alır.

## BGP'nin Çalışma Mantığı: Kök Neden Neden Bu Kadar Kırılgan

### AS'ler ve Prefix Duyuruları

İnternet, her biri bir kuruma (ISP, üniversite, büyük şirket) ait, benzersiz bir **AS numarası (ASN)** ile tanımlanan binlerce özerk ağdan oluşur. Her AS, sahip olduğu IP prefix'lerini (örn. 203.0.113.0/24) komşularına "bu blok bende, buraya giden trafiği bana yollayın" diyerek duyurur. Bu duyuru komşudan komşuya yayılır (path vector), her AS kendi ASN'sini duyuru yoluna (AS_PATH) ekler. Sonunda bir router, aynı prefix için birden fazla yol öğrenebilir ve en kısa/en tercih edilen AS_PATH'i seçer.

Buradaki kök neden şudur: **BGP, bir AS'in duyurduğu prefix'in gerçek sahibi olup olmadığını doğrulayan yerleşik bir mekanizmaya sahip değildir.** Protokol 1980'lerin sonunda, internetin küçük ve güvenilir bir araştırma topluluğu olduğu varsayımıyla tasarlanmıştır. "Kaynağa güven" (trust but don't verify) modeli ölçek büyüdükçe bir güvenlik açığına dönüşmüştür — tıpkı DNS'in başlangıçta bütünlük doğrulaması içermemesi gibi (bkz. DNSSEC'in sonradan eklenmesi).

### BGP Hijack: Mekanizma

Bir **route hijack**, bir AS'in sahibi olmadığı bir prefix'i (veya o prefix'in bir alt bloğunu) duyurmasıdır. İki temel varyant vardır:

1. **Tam prefix hijack**: Saldırgan AS, kurbanla birebir aynı prefix'i (örn. 203.0.113.0/24) duyurur. Bu durumda hangi duyurunun kazanacağı topolojiye, AS_PATH uzunluğuna ve BGP'nin yol seçim algoritmasına bağlıdır — saldırganın duyurusu bazı bölgelerde kazanabilir, bazılarında kazanamaz.

2. **Alt prefix (more-specific) hijack**: Saldırgan, kurbanın duyurduğu /24'ün içinden daha spesifik bir blok (örn. /25) duyurur. BGP'de **en uzun prefix eşleşmesi (longest prefix match)** kuralı gereği, daha spesifik rota HER ZAMAN kazanır — AS_PATH uzunluğundan bağımsız olarak. Bu, hijack'in en güçlü ve en tehlikeli biçimidir çünkü neredeyse deterministik biçimde tüm interneti etkiler.

Neden bu kadar etkili çalışır: Router'lar "en iyi yol" kararını verirken prefix sahipliğini değil, yalnızca yol niteliklerini (uzunluk, local preference, MED gibi metrikler) değerlendirir. Sahiplik doğrulaması olmadığı için, protokol açısından meşru bir duyuru ile kötü niyetli bir duyuru **ayırt edilemez** — ikisi de sözdizimsel olarak geçerlidir.

### Route Leak: Farklı Bir Hata Sınıfı

**Route leak**, kasıtlı bir saldırı olmak zorunda değildir; çoğunlukla yanlış yapılandırmadan kaynaklanır. Bir AS, bir yukarı akış sağlayıcıdan (upstream/transit) öğrendiği rotaları, ticari anlaşmaya aykırı biçimde başka bir yukarı akış sağlayıcıya veya emsale (peer) yeniden duyurduğunda oluşur. Sonuç: o AS aniden büyük miktarda internet trafiğinin (örneğin bir ülkenin tüm trafiğinin) transit noktası haline gelir çünkü diğer AS'ler "daha kısa/daha iyi" görünen bu sahte yolu tercih eder. Route leak'ler genellikle kötü niyetli değildir ama etkisi hijack ile aynıdır: trafik yanlış yere akar, gecikme artar, bazen tamamen kesinti (blackhole) oluşur.

Kök neden: BGP'de **ticari ilişki politikaları (Gao-Rexford kuralları: müşteri, emsal, sağlayıcı ayrımı)** protokolün kendisinde değil, her operatörün router yapılandırmasındaki filtrelerde (route-map, prefix-list) tutulur. Bu filtreler insan tarafından elle yazıldığı veya eksik bırakıldığı için bir yapılandırma hatası anında küresel etkiye yol açabilir.

## RPKI ve ROV: Kriptografik Savunma

### RPKI Nedir, Neyi Çözer

**RPKI (Resource Public Key Infrastructure)**, IP prefix sahipliğini kriptografik olarak doğrulanabilir hale getiren bir sistemdir. Mantığı şudur: bir prefix sahibi, bölgesel internet kayıt kuruluşu (RIR — ARIN, RIPE, APNIC vb.) aracılığıyla imzalı bir kayıt yayınlar: **ROA (Route Origin Authorization)**. ROA, "şu prefix, şu AS numarası tarafından, en fazla şu uzunlukta (max length) duyurulabilir" der ve bu bildirimi sahibinin özel anahtarıyla kriptografik olarak imzalar.

Bu, DNS'teki DNSSEC'e kavramsal olarak benzer: merkezi bir güven kökünden (RIR) başlayan bir imza zinciri, "bu kaynak gerçekten bu tarafa ait" iddiasını doğrulanabilir kılar.

### ROV: Doğrulamanın Uygulanması

ROA'ların var olması tek başına yeterli değildir — router'ların bunları **kullanması** gerekir. Bu adım **ROV (Route Origin Validation)** olarak adlandırılır. Bir router, gelen her BGP duyurusunu yerel bir RPKI önbelleği (relying party yazılımı üzerinden RIR verilerinden türetilmiş) ile karşılaştırır ve duyuruyu üç durumdan birine sınıflandırır:

- **Valid**: Duyurulan prefix ve origin AS, bir ROA ile eşleşiyor.
- **Invalid**: Prefix bir ROA kapsamında ama duyurulan AS veya prefix uzunluğu ROA ile uyuşmuyor (yani muhtemelen bir hijack).
- **NotFound (Unknown)**: Bu prefix için hiç ROA yayınlanmamış — doğrulama yapılamıyor.

Savunma pratiğinde en iyi yaklaşım, **Invalid** olarak işaretlenen duyuruları BGP karar sürecinde en düşük önceliğe koymak veya doğrudan reddetmektir (drop). Bu, önemli bir kavramsal noktadır: ROV'un amacı her duyuruyu "doğru" kanıtlamak değil, **kanıtlanabilir biçimde sahte olanları elemektir**. NotFound durumundaki prefix'ler (henüz ROA'sı olmayanlar) hâlâ kabul edilir — bu yüzden RPKI'nin etkinliği, sahiplerin ROA yayınlama oranına (RPKI adoption) doğrudan bağlıdır. Küresel ROA kapsamı yıllar içinde önemli ölçüde arttı ama hâlâ evrensel değil; bu nedenle ROV tek başına mutlak bir çözüm değil, **riski önemli ölçüde azaltan** bir katmandır.

### ROV'un Sınırları — Dürüstçe

ROV, origin'i (hangi AS'in prefix'i duyurduğunu) doğrular ama **AS_PATH'in tamamının meşruluğunu doğrulamaz**. Yani bir saldırgan, meşru origin AS'i kullanıp yolu manipüle ederek (path manipulation, örn. AS_PATH prepending sahteciliği veya yol içi bir noktada trafiği yönlendirme) hâlâ saldırı düzenleyebilir. Bunu çözmeye yönelik daha kapsamlı öneriler (BGPsec gibi tüm yolu kriptografik olarak imzalayan yaklaşımlar) vardır, ancak işlem yükü ve dağıtım karmaşıklığı nedeniyle geniş operasyonel benimseme düzeyleri sınırlı kalmıştır — bu alandaki güncel durumu iddia etmek yerine, kavramsal olarak "origin doğrulama yeterli değildir, tam yol doğrulaması ayrı ve daha zor bir problemdir" demek daha doğrudur.

## Tespit: Bir Hijack veya Leak Nasıl Anlaşılır

Savunma mühendisliği açısından tespit iki katmanda düşünülmelidir:

### 1. Kendi Prefix'lerinizin Dış Dünyada Nasıl Görüldüğünü İzlemek

Kuruluşunuz kendi IP bloklarını duyuruyor olsa bile, internetin başka bir yerinde biri sizin prefix'inizi (veya bir alt bloğunu) duyurabilir. Bunu kendi router'ınızdan göremezsiniz çünkü sorun *sizin* ağınızda değil, internetin *başka bir yerinde* oluşur. Bu nedenle dışa dönük izleme şarttır:

- **Halka açık BGP gözlem noktaları** (route collector projeleri, örn. RIPE RIS, RouteViews benzeri girişimler) üzerinden kendi prefix'lerinizin küresel görünürlüğünü periyodik olarak sorgulamak.
- Ticari veya açık kaynak **BGP monitoring** servisleri kullanarak, prefix'iniz için beklenmedik bir origin AS numarası göründüğünde otomatik uyarı almak.
- **Anomali imzaları**: aniden görülen daha spesifik bir alt prefix (sizin /24'ünüzün içinden bir /25), beklenmedik coğrafyalardan gelen origin AS'ler, AS_PATH'te normalde görülmeyen ülkelerin/operatörlerin belirmesi.

### 2. Kendi Ağınızın Ne Duyurduğunu ve Ne Kabul Ettiğini Doğrulamak

- **Giden filtreleme (egress/outbound filtering)**: Kendi AS'inizin yalnızca sahip olduğunuz prefix'leri duyurduğundan emin olun (prefix-list, IRR — Internet Routing Registry kayıtlarıyla eşleşme).
- **Gelen filtreleme (ingress/inbound filtering)**: Müşterilerinizden/emsallerinizden gelen duyuruları, onların sahip olduğu prefix'lerle sınırlayın; "bogon" (ayrılmış/özel/tahsis edilmemiş) adres bloklarını reddedin.
- **Max-prefix limitleri**: Bir komşudan beklenenden çok daha fazla prefix duyurusu geldiğinde BGP oturumunu otomatik düşürmek (route leak'e karşı bir güvenlik supabı).
- **RPKI ROV loglarını izlemek**: Router'ınız Invalid işaretli duyuruları reddettiğinde bu olayları loglayıp bir SIEM'e beslemek; ani bir Invalid duyuru artışı hedefli bir saldırı girişiminin erken sinyali olabilir.

Kök mantık: BGP'de tespit büyük ölçüde **dışa dönük gözlemcilik** gerektirir çünkü tehdit modeli "içerideki bir cihazın ele geçirilmesi" değil, "internetin başka bir yerindeki bir AS'in yalan söylemesi"dir. Bu, geleneksel uç nokta/ağ güvenliği zihniyetinden (kendi telemetrinize bakmak) temel bir sapmadır.

## En İyi Pratikler ve Yaygın Hatalar

### En İyi Pratikler

- **RPKI ROA yayınlamak**: Sahip olduğunuz her prefix için doğru max-length ile ROA oluşturmak, sizi başkalarının ROV'undan faydalanır hale getirir (yani sizi hijack'ten korur).
- **ROV'u uçtan uca etkinleştirmek**: Yalnızca ROA yayınlamak yetmez; kendi router'larınızda gelen duyuruları da doğrulamalısınız (böylece siz de başkalarının hijack girişimlerine karşı korunursunuz).
- **IRR kayıtlarını güncel tutmak**: Prefix-filtre otomasyonu büyük ölçüde IRR (Internet Routing Registry) kayıtlarına dayanır; eski/yanlış kayıtlar ya meşru trafiğinizi engeller ya da filtrelemeyi anlamsızlaştırır.
- **Max-prefix ve prefix-length filtreleri**: Bir komşudan makul olmayan sayıda veya olmayan uzunlukta (örn. /32'lerin toplu duyurulması) prefix geldiğinde oturumu otomatik kapatmak.
- **Çoklu izleme kaynağı kullanmak**: Tek bir gözlem noktasına güvenmeyin; BGP küresel bir sistemdir ve bir hijack yalnızca belirli coğrafi bölgelerde görünür olabilir.
- **İç yönlendirme protokollerinde kimlik doğrulama**: OSPF ve EIGRP gibi iç ağ (intra-domain) protokollerinde komşuluk (adjacency/neighbor) kurulumunda MD5 veya daha güçlü kimlik doğrulama mekanizmalarını etkinleştirmek.

### Yaygın Hatalar

- **"BGP dışarıdaki bir problem, bizi ilgilendirmez" varsayımı**: Şirketler genellikle kendi ISP'lerinin bu işi hallettiğini varsayar; oysa çok-evli (multihomed) veya kendi ASN'i olan her kuruluş kendi filtreleme sorumluluğunu taşır.
- **Yalnızca ROA yayınlayıp ROV'u etkinleştirmemek**: Bu, kilidi takıp anahtarı kullanmamak gibidir — kendi prefix'lerinizi korursunuz ama siz hâlâ başkalarının sahte duyurularını kabul edersiniz.
- **Max-length'i gereğinden geniş ROA tanımlamak**: Örneğin /24 sahibiyken max-length'i /32 olarak ayarlamak, saldırganın herhangi bir alt bloğu "Valid" görünümünde duyurmasına izin verir — bu, RPKI'yi anlamsızlaştıran çok yaygın bir yapılandırma hatasıdır.
- **İç protokollerde kimlik doğrulamayı atlamak**: "Zaten iç ağdayız, güvenli" varsayımı; oysa bir saldırgan iç ağa bir şekilde erişim sağladığında (yanlış yapılandırılmış bir switch portu, ele geçirilmiş bir cihaz üzerinden) kimlik doğrulaması olmayan bir IGP komşuluğu kurup sahte rotalar enjekte edebilir.
- **Route leak'i yalnızca kötü niyetli senaryo sanmak**: Çoğu gerçek olay kötü niyet değil, yapılandırma hatasıdır; bu yüzden teknik önlemler (filtreleme, max-prefix) insan hatasına karşı da savunma olarak tasarlanmalıdır.

## İç Ağ Yönlendirme Protokolleri: OSPF ve EIGRP Güvenliği

BGP internet ölçeğinde (AS'ler arası, inter-domain) çalışırken, kurum içi ağlarda (intra-domain) **OSPF** ve **EIGRP** gibi İç Ağ Geçidi Protokolleri (IGP) kullanılır. Bu protokollerin tehdit modeli farklıdır: saldırgan zaten bir şekilde iç ağa (fiziksel erişim, ele geçirilmiş bir host, yanlış segmentlenmiş bir VLAN üzerinden) erişim sağlamıştır ve amaç sahte yönlendirme bilgisi enjekte etmektir.

### Kök Neden: Komşuluk Kurulumunda Doğrulama Eksikliği

OSPF ve EIGRP, komşu router'larla "adjacency" (komşuluk) kurarken varsayılan olarak kimlik doğrulaması yapmayabilir. Bir saldırgan, ağa fiziksel/mantıksal erişim sağladığında sahte bir router gibi davranıp gerçek router'larla komşuluk kurabilir ve şunları yapabilir:

- **Sahte rota enjeksiyonu**: Kendini belirli bir alt ağa (subnet) veya varsayılan geçide (default route) giden en iyi yol gibi göstermek, böylece trafiği kendi üzerinden geçirip dinlemek (man-in-the-middle) veya çöpe atmak (blackhole).
- **Yönlendirme tablosu şişirme / kaynak tüketimi (DoS)**: Aşırı sayıda sahte rota duyurarak router'ların CPU/bellek kaynaklarını tüketmek, yönlendirme tablosu yeniden hesaplamalarını (SPF recalculation OSPF'de) tetikleyerek ağ genelinde kararsızlık yaratmak.
- **Route flapping tetikleme**: Sürekli rota ekleyip kaldırarak IGP'nin sürekli yeniden yakınsama (reconverge) yapmasına, bunun da ağ genelinde gecikme ve kesintiye yol açmasına neden olmak.

### Savunma: Kimlik Doğrulama ve Segmentasyon

- **OSPF'de komşuluk kimlik doğrulaması**: MD5 tabanlı (veya daha güçlü, protokolün desteklediği ölçüde) kimlik doğrulamasını her arayüzde etkinleştirmek, sahte bir cihazın meşru komşuluk kuramamasını sağlar.
- **EIGRP'de kimlik doğrulama**: Benzer şekilde, komşuluk kurulumunda paylaşılan anahtar tabanlı doğrulama kullanmak.
- **Pasif arayüzler (passive-interface)**: Yönlendirme komşuluğunun gerekmediği uç (edge/access) arayüzlerde IGP duyurularını tamamen kapatmak — bir saldırganın erişim katmanından komşuluk kurma girişimini baştan engeller.
- **Ağ segmentasyonu**: Yönetim ve yönlendirme trafiğini kullanıcı/veri trafiğinden VLAN ve ACL ile ayırmak, saldırganın IGP konuşan bir segmente erişmesini zorlaştırır.
- **Rota özetleme ve filtreleme (route summarization/filtering)**: Alan sınırlarında (OSPF area border, EIGRP redistribution noktaları) hangi rotaların dışarı sızacağını sınırlamak, bir bölgedeki sorunun tüm ağa yayılmasını önler.

Kavramsal olarak BGP ile IGP güvenliği arasındaki fark şudur: BGP'de tehdit "internetteki herhangi bir yabancı AS"tir ve savunma **kriptografik sahiplik doğrulamasına (RPKI)** dayanır; IGP'de tehdit "iç ağa sızmış bir aktör"dür ve savunma **komşuluk kimlik doğrulaması + segmentasyon + en az ayrıcalık** ilkesine dayanır. İkisi de aynı kök soruna işaret eder: yönlendirme protokolleri tarihsel olarak "kim konuşuyorsa doğru söylüyordur" varsayımıyla tasarlanmıştır ve modern güvenlik pratiği bu varsayımı kriptografik ve yapısal kontrollerle telafi etmeye çalışır.

## Sonuç

BGP ve iç ağ yönlendirme protokolleri, güvenlik mimarisinde sıklıkla göz ardı edilen ama internetin ve kurumsal ağların temel taşını oluşturan bir katmandır. BGP'nin kök zafiyeti, prefix sahipliğinin protokol seviyesinde doğrulanmamasıdır; bu da route hijack (kasıtlı, kimlik hırsızlığı gibi) ve route leak (çoğunlukla kazara, yapılandırma hatası) sınıflarına yol açar. RPKI/ROV bu soruna kriptografik bir cevap sunar — ROA'lar prefix-AS eşleşmesini imzalar, ROV router'ların bu imzaları doğrulayıp geçersiz duyuruları reddetmesini sağlar — ama bu çözüm yalnızca origin'i doğrular, tam yolu değil, ve etkinliği küresel benimseme oranına bağlıdır. Savunma mühendisinin görevi hem kendi prefix'lerini ROA ile korumak hem de kendi router'larında ROV'u etkinleştirmek hem de dışa dönük izleme ile "prefix'im başka biri tarafından duyuruluyor mu" sorusunu sürekli sormaktır. İç ağ tarafında ise OSPF/EIGRP gibi protokollerde komşuluk kimlik doğrulaması ve segmentasyon, "ağa giren biri otomatik olarak güvenilir yönlendirici" varsayımını kırmanın anahtarıdır. Sonuç olarak yönlendirme güvenliği, ne bir firewall kuralıyla ne de bir VPN tüneliyle kapatılabilecek, ayrı ve kendine özgü bir tehdit yüzeyidir; ciddiye alınması gereken bir mühendislik disiplinidir.
