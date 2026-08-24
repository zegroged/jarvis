# BGP ve Yönlendirme Protokolü Güvenliği

## Giriş: Neden Yönlendirme Güvenliği Önemli?

İnternet, birbirinden bağımsız binlerce ağın (autonomous system, AS) oluşturduğu dev bir "ağlar ağıdır". Bu ağların birbirine hangi trafiği nasıl ileteceğini belirleyen mekanizma yönlendirme protokolleridir. Ne yazık ki bu protokollerin çoğu, güvenliğin bir öncelik olmadığı bir dönemde, karşılıklı güvene (implicit trust) dayanarak tasarlandı. Sonuç olarak yönlendirme katmanı, modern internetin en kırılgan ve en az korunan bölgelerinden biridir.

Bir web sunucusunu ne kadar sıkılaştırırsanız sıkılaştırın, o sunucuya giden trafik yolda başka bir ağa yönlendirilirse (hijack) veya sızdırılırsa, uygulama katmanındaki tüm önlemler etkisiz kalabilir. Bu yüzden yönlendirme güvenliği, ağ güvenliği uzmanlığının ihmal edilmemesi gereken bir parçasıdır.

Bu makalede iki ölçekte protokolü ele alacağız: internet omurgasını taşıyan **BGP** (Border Gateway Protocol, bir EGP/exterior gateway protocol) ve kurumsal ağların içindeki **OSPF** ve **EIGRP** gibi IGP'ler (interior gateway protocol). Her biri için çalışma mantığını, saldırı sınıflarını, tespit ve savunma yöntemlerini kavramsal düzeyde inceleyeceğiz.

---

## BGP Temelleri: Güvene Dayalı Bir Protokol

### BGP Ne Yapar?

BGP, autonomous system'ler arasında **erişilebilirlik bilgisi** (reachability) taşır. Her AS, sahibi olduğu IP adres bloklarını (prefix, örneğin `203.0.113.0/24`) komşularına duyurur. Komşular bu duyuruyu kendi komşularına aktarır ve böylece her prefix'in hangi AS'ler üzerinden erişilebilir olduğu tüm internete yayılır.

BGP bir **path-vector** protokolüdür. Her duyuru, o prefix'e ulaşmak için geçilecek AS'lerin listesini (AS_PATH) taşır. Bir router birden fazla yoldan aynı prefix'i öğrenirse, çeşitli kriterlere göre (yerel politika, AS_PATH uzunluğu, MED, vb.) en iyi yolu seçer.

### Kök Güvenlik Sorunu: Doğrulama Yokluğu

Klasik BGP'nin temel zaafı basittir: bir AS, aslında sahip olmadığı bir prefix'i duyurduğunda, komşuları bunun doğru olup olmadığını **kriptografik olarak doğrulayamaz**. Protokol, "AS64500 bana bu prefix'in kendisine ait olduğunu söylüyor" ifadesine varsayılan olarak inanır. Yönlendirme kararları, iddiaların doğruluğuna değil, komşuya duyulan güvene dayanır. İşte tüm BGP saldırılarının kökeni bu doğrulama boşluğudur.

---

## BGP Hijacking (Prefix Kaçırma)

### Tanım ve Çalışma Mantığı

BGP hijacking, bir AS'in sahibi olmadığı bir IP prefix'ini (veya bir başkasının prefix'inin daha spesifik bir alt bloğunu) duyurarak o adreslere giden trafiği kendine çekmesidir. İki temel biçimi vardır:

**Origin hijack:** Saldırgan AS, kurbanın prefix'ini sanki kendi prefix'iymiş gibi (kendisini origin AS göstererek) duyurur. Trafiği çeken duyuru internet üzerinde yayılır ve bazı ağlar meşru yol yerine saldırganın yolunu tercih etmeye başlar.

**Daha spesifik (more-specific) hijack:** İnternet yönlendirmesinde en uzun önek eşleşmesi (longest prefix match) kuralı geçerlidir. Kurban `/16` duyururken saldırgan aynı bloğun içinden bir `/24` duyurursa, `/24` daha spesifik olduğu için trafik hemen hemen tüm internette saldırgana yönelir. Bu, hijack'in en etkili biçimidir çünkü meşru daha geniş duyuruyu "ezer".

### Neden Olur? Yayılma Dinamiği

Bir hatalı ya da kötü niyetli duyurunun ne kadar yayılacağı, o AS'in komşularının uyguladığı **filtrelemeye** bağlıdır. Eğer üst-akım sağlayıcılar (upstream) müşterilerinden gelen duyuruları katı biçimde filtrelemiyorsa, sahte duyuru internete yayılır. Tarihsel olarak hem kaza kaynaklı (yanlış yapılandırma, "fat-finger") hem de kasıtlı olaylar yaşanmıştır; örneğin bir servis sağlayıcının yanlışlıkla büyük bir platformun prefix'lerini duyurup küresel erişilebilirliği bozması gibi olaylar iyi bilinen kamu örnekleridir.

### Amaçlar

Hijacking farklı amaçlarla kullanılabilir: trafiği **dinleme/araya girme** (interception, trafik saldırgan üzerinden geçip meşru hedefe geri döndürülürse man-in-the-middle mümkün olur), hizmet **kesintisi** (denial of service, trafik kara deliğe gider), spam veya kötü amaçlı altyapı için kullan-at IP alanı elde etme, ve kimlik doğrulama gerektiren sistemlere yönelik daha karmaşık saldırıların (örneğin sertifika doğrulama süreçlerini istismar) bir parçası olma.

### Örnek Senaryo

`198.51.100.0/24` bloğu meşru olarak AS64510'a aittir ve internete `/24` olarak duyurulur. Saldırgan AS64666 aynı bloğu `/24` origin hijack olarak duyurur ve AS_PATH'i kısa görünür. Bazı ağlar için AS64666'nın yolu daha iyi görünür (daha kısa AS_PATH ya da yerel tercih) ve trafik oraya akmaya başlar. Saldırgan trafiği yutabilir veya kaydedip meşru hedefe geri iletebilir. Eğer saldırgan `/25` gibi daha spesifik bir blok duyurabilseydi, longest prefix match nedeniyle etki çok daha geniş olurdu.

---

## Route Leak (Yol Sızıntısı)

### Tanım

Route leak, hijacking'den farklı bir sorundur. Burada prefix sahipliği sahte değildir; sorun, duyurunun **yönlendirme politikasına aykırı bir yönde yayılmasıdır**. Yani doğru prefix, olmaması gereken bir komşuya aktarılır.

### Kök Neden: Valley-Free Kuralının İhlali

İnternet ilişkilerinde genel bir prensip vardır (Gao-Rexford modeli olarak da anılır): Bir AS, bir **peer**'den veya **provider**'dan öğrendiği yolları başka bir provider'a ya da peer'e **aktarmamalıdır**. Yani "müşteriden gelen yollar herkese, provider/peer'den gelen yollar yalnızca müşterilere" ilkesi uygulanır. Bu ilkeye "valley-free" denir.

Route leak, tipik olarak çok-bağlantılı (multi-homed) bir müşteri AS'in, bir üst-akım sağlayıcıdan öğrendiği geniş internet yollarını yanlışlıkla başka bir üst-akım sağlayıcıya aktarmasıyla oluşur. Bu durumda o küçük AS aniden büyük trafik akışları için transit yolu gibi görünür. Trafik onun üzerinden geçmeye çalışır; kapasitesi yetmez, gecikmeler ve kesintiler yaşanır.

### Etki ve Örnek

Küçük bir kurumsal AS'in yanlış yapılandırma nedeniyle "internetin bir kısmına giden en iyi yol benim üzerimden" mesajını vermesi, dünya çapında büyük ölçekli erişim sorunlarına yol açan bilinen olaylara neden olmuştur. Route leak çoğunlukla kaza sonucu olur ama etkisi büyük çaplı hizmet kesintisidir. Hijacking'de "sahte sahiplik" varken, leak'te "yanlış yönde meşru yol yayılımı" vardır.

---

## Savunma Katmanı 1: Filtreleme ve Politika Hijyeni

Yönlendirme güvenliğinde en temel, en yaygın ve en etkili önlemler kriptografiden önce **filtrelemedir**.

**Prefix filtering:** Her komşudan yalnızca duyurmasına izin verilen prefix'leri kabul edin. Özellikle müşteri oturumlarında, o müşterinin sahip olduğu bloklara ait açık bir izin listesi (whitelist) uygulanmalıdır. IRR (Internet Routing Registry) kayıtlarından türetilen prefix listeleri bu amaçla kullanılır.

**AS_PATH filtering:** Komşudan gelen AS_PATH'lerin makul olup olmadığını kontrol edin. Bir müşteriden, içinde büyük transit sağlayıcıların AS numaralarını taşıyan bir yol gelmesi anormaldir ve leak işaretidir.

**Max-prefix limit:** Bir komşudan kabul edilecek prefix sayısına üst sınır koyun. Beklenmedik bir sıçrama (örneğin bir müşterinin aniden yüz binlerce yol duyurması) leak'in erken göstergesidir ve oturum otomatik kapatılabilir.

**Bogon ve özel adres filtreleme:** RFC1918 özel adresleri, ayrılmamış/rezerve bloklar ve varsayılan rota gibi asla internette görünmemesi gereken duyuruları reddedin.

**MANRS (Mutually Agreed Norms for Routing Security):** Operatörlerin gönüllü olarak uyguladığı, filtreleme, anti-spoofing, koordinasyon ve doğrulama gibi temel iyi uygulamaları tanımlayan bir çerçevedir. Bu normların benimsenmesi ekosistem genelinde saldırı yüzeyini azaltır.

---

## Savunma Katmanı 2: RPKI ve Origin Doğrulaması

### RPKI Nedir?

**RPKI (Resource Public Key Infrastructure)**, hangi AS'in hangi prefix'i duyurmaya **yetkili** olduğunu kriptografik olarak doğrulanabilir hale getiren bir sistemdir. Adres bloklarını tahsis eden otoriteler (RIR'ler, örneğin RIPE, ARIN), kaynak sahiplerine sertifikalar verir.

### ROA ve Origin Validation

Prefix sahibi bir **ROA (Route Origin Authorization)** yayınlar. ROA temelde şunu söyler: "Bu prefix'i (ve belirtilen maksimum uzunluğa kadar olan alt bloklarını) yalnızca şu AS numarası origin olarak duyurabilir." ROA'lar kriptografik olarak imzalıdır.

Router'lar, RPKI validator yazılımı aracılığıyla doğrulanmış ROA verisini alır ve gelen her BGP duyurusunu **ROV (Route Origin Validation)** ile üç durumdan birine sınıflandırır:

- **Valid:** Duyurunun origin AS'i ve prefix uzunluğu ilgili ROA ile uyumlu.
- **Invalid:** Bir ROA var ama origin AS ya da prefix uzunluğu ona aykırı. Bu, origin hijack'in güçlü göstergesidir.
- **NotFound / Unknown:** Bu prefix için bir ROA yayınlanmamış; doğrulama yapılamıyor.

Yaygın politika, **Invalid** duyuruları reddetmek (drop), **Valid** ve **NotFound** olanları kabul etmektir. Bu, ROA yayınlamış blokların origin hijack'ini önemli ölçüde zorlaştırır.

### RPKI'nin Sınırları (Dürüst Değerlendirme)

RPKI güçlüdür ama sihirli değildir:

- RPKI/ROV yalnızca **origin AS'i** doğrular; AS_PATH'in tamamının gerçekliğini doğrulamaz. Saldırgan meşru origin AS'i AS_PATH'in sonuna ekleyerek ("prepend" ederek) ROV'u atlatabilir. Bu, path'in gerçekten geçerli olduğu anlamına gelmez.
- ROA yayınlamayan bloklar (NotFound) korumasız kalır; kapsama tam değildir.
- Route leak'e karşı doğrudan koruma sağlamaz; leak'te origin doğrudur.
- Validator altyapısının doğru ve güncel çalışması operasyonel bir sorumluluktur.

### AS_PATH Doğrulaması: BGPsec ve ASPA

AS_PATH'in bütünlüğünü doğrulamak için **BGPsec** tasarlanmıştır; her AS geçişini kriptografik olarak imzalayarak path'i doğrular. Ancak hesaplama maliyeti ve yaygınlaşma zorlukları nedeniyle pratik benimsenmesi sınırlı kalmıştır. Daha hafif ve leak/path anomalilerini yakalamaya yönelik bir yaklaşım olarak **ASPA (Autonomous System Provider Authorization)** üzerinde çalışılmaktadır; bir AS'in hangi sağlayıcıları olduğunu kaydederek valley-free ihlallerinin tespitini mümkün kılmayı amaçlar. Bu alan gelişmeye devam etmektedir.

---

## Tespit: Yönlendirme Anomalilerini İzleme

Savunma yalnızca önleme değil, aynı zamanda tespittir. Kendi prefix'lerinizin internette nasıl göründüğünü sürekli izlemelisiniz:

- **Genel BGP izleme platformları ve looking glass'lar:** İnternetin farklı noktalarındaki BGP tablolarına bakarak sizin prefix'lerinizin beklenmedik bir origin AS ile veya beklenmedik daha spesifik bir blokla duyurulup duyurulmadığını görebilirsiniz.
- **Prefix ve origin izleme/alarm servisleri:** Sahip olduğunuz bloklar için, farklı bir AS tarafından duyurulma ya da yeni bir more-specific duyuru ortaya çıkması durumunda uyarı üreten servisler ve açık kaynak araçlar mevcuttur. Bu, hijack'i dakikalar içinde fark etmenizi sağlar.
- **Kendi BGP tablonuzda anomali izleme:** Ani AS_PATH değişimleri, max-prefix eşiğine yaklaşma, beklenmedik yönlerden gelen yollar ve MED/community anomalileri leak veya hijack işaretleri olabilir.
- **RPKI durum izleme:** Kendi ROA'larınızın "valid" olarak yayıldığını ve validator'larınızın güncel kaldığını doğrulayın.

Tespit edildiğinde müdahale: Kendi meşru duyurunuzu daha spesifik hale getirerek (örneğin `/24`'ü `/24`'ler halinde parçalamak) hijack'i zayıflatmak, üst-akım sağlayıcılar ve NOC'larla koordinasyon, ve ilgili operatör topluluklarıyla iletişim tipik adımlardır.

---

## IGP Güvenliği: OSPF ve EIGRP Saldırıları

Şimdiye kadar internet ölçeğindeki BGP'yi ele aldık. Kurumsal ağın **içinde** ise IGP'ler çalışır ve bunların kendi güvenlik sorunları vardır. IGP'ler genellikle güvenilir sayılan bir yerel alanda çalıştığı için tarihsel olarak kimlik doğrulaması ihmal edilmiştir; oysa iç ağa erişebilen bir saldırgan için bunlar cazip hedeflerdir.

### OSPF (Open Shortest Path First)

OSPF bir **link-state** protokolüdür. Her router, ağ topolojisini tanımlayan LSA'lar (Link-State Advertisement) üretir; tüm router'lar bu LSA'ları paylaşarak ortak bir topoloji veritabanı (LSDB) oluşturur ve en kısa yolu (SPF/Dijkstra) hesaplar.

**Saldırı mantığı:** İç ağa erişebilen bir saldırgan, sahte LSA enjekte ederek topoloji görüşünü bozabilir. Kendini sahte bir router olarak komşuluk (adjacency) kurmaya çalışabilir, yolları kendine çekerek trafiği araya girme veya kara delik amacıyla yönlendirebilir, ya da hatalı LSA'larla SPF hesaplamalarını sürekli tetikleyip yönlendirme kararsızlığı (instability) ve kaynak tüketimi yaratabilir. OSPF'in kendi iç tutarlılık ve LSA "fight-back" mekanizmaları bazı manipülasyonları zorlaştırsa da bu mekanizmaları istismar eden ince teknikler tartışılmıştır.

**Savunma:**
- **Kriptografik kimlik doğrulama:** OSPFv2 için mesajların bütünlüğünü koruyan (basit şifre yerine kriptografik hash tabanlı, örneğin HMAC türevi) doğrulama kullanın. OSPFv3 IPv6'da IPsec ile korunabilir. Kimliği doğrulanmamış komşuluk kurulmamalıdır.
- **Passive interface:** Router olmayan (son kullanıcı) segmentlerde OSPF konuşmasını pasif hale getirin; bu arayüzlerden komşuluk kurulmasını engelleyin.
- **Alan tasarımı ve summarization:** Area'lara bölme ve özetleme, hem hata alanını hem manipülasyon yüzeyini sınırlar.

### EIGRP (Enhanced Interior Gateway Routing Protocol)

EIGRP, Cisco kökenli (sonradan bilgisi yayımlanmış) gelişmiş bir distance-vector protokolüdür; DUAL algoritmasıyla ilmeksiz (loop-free) yollar hesaplar. Komşular arasında hello ve güncelleme mesajları alışverişi yapılır.

**Saldırı mantığı:** İç ağa erişimi olan saldırgan sahte EIGRP komşuluğu kurmaya, sahte güncellemelerle yolları etkilemeye (metrikleri manipüle ederek trafiği çekmeye) veya sürekli güncelleme/hello akışıyla kararsızlık ve kaynak tüketimi oluşturmaya çalışabilir. OSPF'teki mantıksal kardeşi budur; protokol farklı, tehdit modeli benzerdir.

**Savunma:**
- **Kimlik doğrulama:** EIGRP komşuluğu için kriptografik kimlik doğrulama (hash tabanlı) etkinleştirin; kimliği doğrulanmamış komşu kabul etmeyin.
- **Passive interface:** Kullanıcı segmentlerinde EIGRP'yi pasif yapın.
- **Router erişim kontrolü:** Yönetim düzlemi sıkılaştırması, control-plane policing ve segment izolasyonu.

### Tüm IGP'ler İçin Ortak Savunma İlkeleri

- **Kimlik doğrulama varsayılan olmalı:** İç ağda "güvenilir" varsayımı tehlikelidir. Tüm yönlendirme komşulukları kriptografik olarak doğrulanmalıdır.
- **En küçük konuşma alanı:** Router protokolü yalnızca router'ların olduğu bağlantılarda konuşmalı; her yerde passive interface uygulanmalı.
- **Control plane koruması:** Yönlendirme işlemcisine yönelik flood/DoS'a karşı control-plane policing ve rate-limit.
- **Segmentasyon ve izleme:** Yönlendirme değişikliklerini loglayın; beklenmedik komşuluk kurulumları ve topoloji değişiklikleri için alarm üretin. Ani bir yeni komşuluk çoğunlukla ya yanlış yapılandırma ya da saldırıdır.

---

## Yaygın Hatalar ve Yanılgılar

- **"RPKI her şeyi çözer" yanılgısı:** RPKI/ROV yalnızca origin doğrular, path'i ve leak'i değil. Filtreleme, RPKI'nin yerini almaz; birlikte katmanlı savunma oluştururlar.
- **Filtrelemeyi ihmal etmek:** Origin hijack ve leak olaylarının çoğu, komşularda basit prefix ve AS_PATH filtresi olsaydı engellenirdi. Kriptografiye atlamadan önce filtreleme hijyenini sağlamak gerekir.
- **max-prefix limitini koymamak:** Bu tek satırlık önlem, birçok leak'in küresel yayılmasını erken kesebilir.
- **IGP kimlik doğrulamasını "iç ağ zaten güvenli" diye atlamak:** İç ağa giren saldırgan için doğrulamasız OSPF/EIGRP açık davetiyedir.
- **more-specific gücünü unutmak:** `/24` duyuran bir saldırgan, `/16` duyuran meşru sahibi longest prefix match nedeniyle ezer. Kendi kritik bloklarınızı yeterince spesifik duyurmak ve ROA maksimum uzunluğunu doğru ayarlamak önemlidir.
- **ROA maxLength'i çok gevşek bırakmak:** ROA'da gereğinden geniş bir maksimum uzunluk izni vermek, saldırganın "valid" görünen daha spesifik bloklar duyurmasına kapı aralayabilir. maxLength gerçek ihtiyaca göre sıkı tutulmalıdır.
- **İzleme yapmamak:** Hijack'in en kısa fark edilme süresi, dışarıdan izleme kurmuş olmanıza bağlıdır. Önleme kadar tespit de kritiktir.

---

## Özet

Yönlendirme protokolleri internetin ve kurumsal WAN'ların temel güven omurgasıdır ama tasarım gereği doğrulamadan yoksundur. BGP tarafında iki büyük tehdit sınıfı vardır: sahte sahiplikle trafiği çeken **prefix hijacking** ve meşru yolun yanlış yönde yayıldığı **route leak**. Savunma katmanlıdır: önce sağlam **filtreleme** (prefix, AS_PATH, max-prefix, bogon) ve MANRS gibi normlar; ardından origin'i kriptografik doğrulayan **RPKI/ROV**; ve sürekli **izleme/alarm**. RPKI güçlüdür ama path ve leak'i çözmez; bu boşluklar için BGPsec/ASPA gibi gelişen yaklaşımlar vardır.

Kurumsal ağ içinde **OSPF** ve **EIGRP** gibi IGP'ler, iç ağa erişen bir saldırgan tarafından sahte LSA/komşuluk enjeksiyonu, metrik manipülasyonu ve kararsızlık yaratma amacıyla istismar edilebilir. Bunlara karşı temel savunma her yerde **kriptografik kimlik doğrulama**, kullanıcı segmentlerinde **passive interface**, control-plane koruması ve değişiklik izlemedir. Tüm bu katmanların ortak dersi tektir: yönlendirmede "güven" varsayılan olarak verilmemeli, mümkün olduğunca **doğrulanmalıdır**.
