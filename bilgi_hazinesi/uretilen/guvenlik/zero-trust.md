# Zero Trust Mimarisi: "Asla Güvenme, Daima Doğrula"

## Tanım

Zero Trust (Sıfır Güven), ağ güvenliğine dair on yıllardır süregelen bir varsayımı reddeden bir mimari yaklaşımdır: "İç ağdaki her şey güvenilirdir" varsayımını. Klasik model bir kaleye benzer; dışarıda derin bir hendek (firewall, DMZ, VPN girişi) vardır, ama kapıdan içeri girildiğinde surların içi serbest dolaşım alanıdır. Zero Trust bu "sert kabuk, yumuşak iç" (hard shell, soft interior) modelini terk eder ve tek bir ilkeye indirger: **hiçbir istek, geldiği yer neresi olursa olsun, önceden doğrulanmadan güvenilir sayılamaz.**

Burada kritik nokta, Zero Trust'ın bir ürün değil bir **strateji** olmasıdır. Piyasada "Zero Trust çözümü" diye satılan tek bir kutu yoktur; bu, kimlik, cihaz, ağ, uygulama ve veri katmanlarını birbirine bağlayan bir tasarım felsefesidir. NIST'in bu konudaki temel yayını (NIST SP 800-207, Zero Trust Architecture) mimarinin fiili referans çerçevesidir ve terminolojinin büyük kısmı buradan gelir.

Modelin özünü üç temel ilke taşır:

1. **Never trust, always verify** — Konum (network location) bir güven kaynağı değildir. VPN üzerinden bağlanan bir kullanıcı da, veri merkezindeki bir sunucu da aynı sorgulamadan geçer.
2. **Assume breach** (İhlali varsay) — Saldırganın zaten içeride olduğunu kabul ederek tasarım yap. Bu varsayım, patlama yarıçapını (blast radius) küçültmeye ve yanal hareketi (lateral movement) engellemeye zorlar.
3. **Least privilege** (En az yetki) — Her kimliğe yalnızca işini yapması için gereken minimum erişim, gereken süre kadar verilir.

## Kök Neden: Neden Bu Modele İhtiyaç Doğdu?

Zero Trust'ı anlamak için önce çevresel güvenliğin (perimeter security) **neden çöktüğünü** anlamak gerekir. Bu bir moda değil, somut bir başarısızlığa verilen mühendislik cevabıdır.

**Çevre kayboldu.** Bulut (cloud), SaaS uygulamaları, uzaktan çalışma ve mobil cihazlar "iç ağ" kavramını anlamsızlaştırdı. Kurumsal verinin büyük kısmı artık kendi veri merkezinizde değil; başka firmaların sunucularında. Korunacak net bir "dış duvar" kalmadı. Duvarı olmayan bir kalede hendek kazmak beyhude bir çabadır.

**Yanal hareket, ihlalleri felakete çeviriyor.** Klasik modelin ölümcül kusuru şudur: Saldırgan tek bir zayıf noktadan (bir phishing e-postası, yamalanmamış bir uç nokta) içeri girdiğinde, iç ağ ona düz bir otoban sunar. Bir kullanıcının dizüstü bilgisayarını ele geçiren saldırgan, oradan dosya sunucusuna, oradan veritabanına, oradan Active Directory domain controller'a kadar adım adım ilerler. Buna **lateral movement** denir. Büyük veri ihlallerinin çoğunda asıl hasar, ilk girişten değil, bu engellenmeyen iç dolaşımdan kaynaklanır. Zero Trust'ın "assume breach" ilkesi tam da bunu hedefler: Saldırgan içeri girse bile, her sıçrayışta yeni bir kimlik doğrulama ve yetkilendirme duvarına toslasın.

**Güven, sömürülebilir bir varlıktır.** Güvenlikte temel bir doğru vardır: Örtük güven (implicit trust) her zaman bir saldırı yüzeyidir. "Bu IP aralığından geldiği için güvenilir" gibi bir kural, o IP aralığına sızmayı başaran herkese kapıyı açar. Zero Trust, örtük güveni sistematik olarak yok etmeye ve yerine **her erişimde yeniden değerlendirilen, açık (explicit) güven kararları** koymaya çalışır.

## Çalışma Mantığı: Karar Nasıl Veriliyor?

Zero Trust mimarisinin kalbinde bir karar mekanizması vardır. NIST terminolojisiyle bunun iki ana bileşeni bulunur:

- **Policy Decision Point (PDP)** — Kararı veren beyin. "Bu kimlik, bu cihazdan, bu kaynağa, şu anda erişebilir mi?" sorusunu yanıtlar.
- **Policy Enforcement Point (PEP)** — Kararı uygulayan kapıcı. İsteği fiilen geçirir veya reddeder. Trafik daima PEP üzerinden akar.

Her erişim talebinde şu döngü işler: İstek PEP'e ulaşır, PEP karar için PDP'ye danışır, PDP eldeki tüm sinyalleri değerlendirir ve bir karar üretir. Kritik olan şudur: Bu karar **statik değil, dinamiktir**. Değerlendirmeye giren sinyaller çok boyutludur:

- Kimlik (kim?) ve o kimliğin doğrulama gücü (MFA yapıldı mı?)
- Cihaz durumu (device posture) — yamalı mı, disk şifreli mi, EDR çalışıyor mu, jailbreak/root var mı?
- Bağlam — coğrafi konum, saat, erişim geçmişindeki anormallikler
- Kaynağın hassasiyeti — maaş veritabanına erişim, kafeterya menüsüne erişimden daha sıkı sorgulanmalı

Bu yaklaşıma **risk-based** veya **adaptive** erişim denir. Örneğin normalde İstanbul'dan sabah 9'da giriş yapan bir kullanıcı, gece 3'te farklı bir ülkeden ve şifresi henüz güncellenmemiş bir cihazdan bağlanmaya çalışırsa, PDP erişimi reddedebilir veya ek doğrulama (step-up authentication) isteyebilir. Güven, bir kez kazanılıp süresiz tutulan bir rozet değil, her etkileşimde yeniden hesaplanan bir puandır.

## Temel Direk 1: Kimlik (Identity)

Zero Trust'ta yeni çevre (perimeter) artık ağ değil, **kimliktir**. "Identity is the new perimeter" sözü bir slogan değil, mimari bir gerçektir: Erişim kararları IP adresine değil, doğrulanmış kimliğe dayandığında, kimlik sisteminiz artık savunmanızın ön cephesidir.

Bu, kimlik altyapısını kritik hale getirir. Sağlam bir kimlik katmanı şunları içerir:

- **Güçlü authentication** — Parola tek başına yetersizdir; parolalar phishing ile çalınır, yeniden kullanılır (credential reuse), sızıntı listelerinde bulunur. MFA (Multi-Factor Authentication) bu yüzden Zero Trust'ın olmazsa olmazıdır. Ancak her MFA eşit değildir: SMS tabanlı OTP, SIM swapping ve gerçek zamanlı phishing proxy'lerine karşı zayıftır. **Phishing'e dirençli** yöntemler — FIDO2/WebAuthn tabanlı donanım anahtarları veya passkey'ler — kriptografik olarak ilgili siteye bağlı oldukları için (origin binding) sahte sitelere kimlik bilgisi sızmasını önler.
- **Merkezi kimlik yönetimi (IdP)** — Kimlikler tek bir kaynakta (identity provider) toplanır; SSO (Single Sign-On) ile uygulamalar bu merkeze federe olur. Dağınık, uygulamaya özel yerel hesaplar Zero Trust'ın düşmanıdır çünkü görünürlüğü ve kontrolü parçalar.
- **Least privilege ve JIT erişim** — Kimliğe kalıcı geniş yetkiler yerine, gerektiğinde ve gereken süre için (Just-In-Time) yükseltilen yetkiler verilir. Özellikle ayrıcalıklı hesaplar (privileged accounts) için bu kritiktir.
- **Makine kimlikleri de kimliktir** — Zero Trust yalnızca insanlarla ilgili değildir. Servisler, API'ler, konteynerler, otomasyon botları da kimlik taşır ve doğrulanmalıdır. Servisler arası iletişimde workload identity (örneğin mTLS ile karşılıklı kimlik doğrulama) bu ihtiyacı karşılar.

### İstismar mantığı ve savunma (Kimlik)

**İstismar tarafı:** Saldırganlar Zero Trust'ta kimliği hedefler çünkü kimlik yeni çevredir. Başlıca yöntemler: parola püskürtme (password spraying) ile zayıf parolaları bulmak; **MFA fatigue / MFA bombing** — kurbana peş peşe onay bildirimi göndererek, bıkkınlıkla birinin "onayla"ya basmasını ummak; **token/session hijacking** — MFA'yı atlamak için doğrulama sonrası oluşan oturum token'ını (session cookie) çalmak. Bu son yöntem önemlidir: Token çalındığında saldırgan zaten doğrulanmış bir oturumu devralır ve MFA'yı tekrar geçmesine gerek kalmaz. AiTM (Adversary-in-the-Middle) phishing kitleri tam olarak bunu, kullanıcı ile gerçek site arasına girip oturum token'ını yakalayarak yapar.

**Savunma tarafı:** MFA fatigue'e karşı **number matching** (kullanıcının ekrandaki sayıyı uygulamaya girmesi) basit onay yerine geçer ve körlemesine onaylamayı engeller. Token hırsızlığına karşı token binding ve kısa oturum ömrü etkilidir; ayrıca sürekli değerlendirme (continuous access evaluation) sayesinde, oturum ortası bir risk sinyali (örneğin IP'nin aniden değişmesi) oturumu iptal edebilir. Phishing'e dirençli FIDO2/passkey kullanımı, AiTM saldırılarının çoğunu kökten etkisiz kılar çünkü kimlik bilgisi sahte origin'e asla gönderilmez.

## Temel Direk 2: Mikrosegmentasyon (Microsegmentation)

Mikrosegmentasyon, ağı büyük güven bölgeleri yerine çok sayıda küçük, izole bölmeye ayırmaktır. Amaç tektir: **yanal hareketi öldürmek.** Bir batıştaki gemide su geçirmez bölmeler nasıl bir deliğin tüm gemiyi batırmasını önlerse, mikrosegmentasyon da bir ele geçirilmiş sunucunun tüm ağa yayılmasını önler.

Klasik segmentasyon (VLAN'lar, kaba firewall zone'ları) genellikle üç-beş büyük bölgeyle sınırlıdır ve bir bölge içindeki her şey birbiriyle serbestçe konuşabilir. Mikrosegmentasyon bunu **iş yükü (workload) düzeyine** kadar indirir. İdeal hedef, ağın "varsayılan olarak reddet" (default-deny) çalışmasıdır: İki iş yükü arasında açıkça izin verilmiş bir kural yoksa, o trafik akmaz. Web sunucusunun yalnızca uygulama sunucusunun belirli portuyla konuşabildiği, uygulama sunucusunun yalnızca veritabanının o portuyla konuşabildiği, ama web sunucusunun veritabanına doğrudan hiç erişemediği bir tasarım düşünün. Saldırgan web sunucusunu ele geçirse bile, oradan gidebileceği yer neredeyse yoktur.

### Çalışma mantığı ve neden zor

Mikrosegmentasyonun gücü kimlik-tabanlı politikalardan gelir. Modern yaklaşımlar segmenti IP adresine değil, iş yükünün **kimliğine ve etiketine** (label/tag) bağlar. "PCI kapsamındaki ödeme servisleri" gibi bir etiket grubu, IP'ler değişse bile politikanın tutarlı kalmasını sağlar. Uygulama genellikle iş yüklerine yerleştirilen ajanlar veya ağ dokusundaki (fabric) uygulama noktaları üzerinden host tabanlı firewall kurallarıyla yapılır.

Zorluğu ise şudur: Mikrosegmentasyon başarısız olduğu yer, çoğunlukla **görünürlük eksikliğidir**. Neyin neyle konuştuğunu bilmeden segment çizemezsiniz. Bu yüzden doğru sıra önce trafik akışlarını haritalamak (flow mapping/discovery), sonra politika yazmaktır. Aksi halde ya meşru trafiği kırarsınız ya da güvenli görünen ama aslında delik dolu kurallar yazarsınız.

### İstismar mantığı ve savunma (Mikrosegmentasyon)

**İstismar tarafı:** Saldırganın hedefi, konulan bölmeleri delip yatay ilerlemektir. Yollar: aynı segment içinde bırakılmış aşırı geniş kurallar ("any-any" istisnaları); segmentasyonun kimlik yerine sadece IP'ye dayanması durumunda IP taklidi veya ele geçirilmiş bir "güvenilir" host üzerinden atlama; yönetim düzlemine (management plane) — segmentasyon kontrolcüsünün kendisine — ulaşıp politikaları gevşetmek. Ayrıca doğu-batı (east-west) trafiği izlenmiyorsa, saldırgan segmentler arası izinli yollarda gürültüsüzce dolaşabilir.

**Savunma tarafı:** Default-deny temel savunmadır — açıkça izin verilmemiş her şey yasak. Kuralları IP yerine kimlik/etiket temelli yazmak IP taklidini anlamsızlaştırır. Doğu-batı trafiğini de (yalnız kuzey-güney değil) izlemek ve loglamak, atlama girişimlerini görünür kılar. Yönetim düzlemini ayrı, sıkı korunan bir segmentte tutmak ve ona erişimi ayrıcalıklı erişim yönetimiyle sınırlamak, "kontrolcüyü ele geçirip her şeyi aç" senaryosunu kapatır. En yüksek değerli varlıkları (Tier 0: domain controller'lar, kimlik sistemi, yedekler) en sıkı mikrosegmentle çevrelemek, patlama yarıçapını en kritik yerde küçültür.

## Temel Direk 3: ZTNA (Zero Trust Network Access)

ZTNA, Zero Trust ilkelerinin uzaktan erişime uygulanmış somut halidir ve büyük ölçüde **klasik VPN'in yerini almak** üzere doğmuştur. Farkı anlamak, ZTNA'nın neden var olduğunu anlamaktır.

**VPN'in temel kusuru:** Geleneksel VPN, kullanıcıyı *ağa* bağlar. Kimlik doğrulaması başarılı olduğunda, kullanıcının cihazı iç ağın bir parçası olur ve — ek kontrol yoksa — o ağdaki pek çok şeye erişebilecek konuma gelir. Yani VPN, "içeri girdin, artık iç ağdasın" mantığıyla çalışır; bu tam da Zero Trust'ın reddettiği örtük güvendir. Ele geçirilmiş bir VPN kimliği veya cihazı, saldırgana geniş bir iç ağ yüzeyi açar.

**ZTNA'nın yaklaşımı:** ZTNA kullanıcıyı ağa değil, **tek tek uygulamalara** bağlar. Prensip şudur: Kimlik ve cihaz doğrulanana kadar hiçbir şey görünmez, doğrulandıktan sonra bile yalnızca yetkili olunan spesifik uygulamaya erişim açılır — ağın geri kalanı görünmez ve erişilmez kalır. Bu "uygulama-merkezli, en az yetkili erişim" modelidir.

ZTNA'nın güçlü bir mekanizması **default-deny + gizlenmiş yüzey** yaklaşımıdır. Uygulamalar doğrudan internete açık portlar üzerinden dinlemez; bunun yerine erişim bir aracı (broker) üzerinden yönlendirilir. Yaygın bir desende iç uygulama sunucusu dışarıya doğru bir bağlantı başlatır (outbound connection to broker), yani dışarıdan gelen dinleyen bir port yoktur. Bu, **açık bir dinleme portu olmadığı için taranamayan/keşfedilemeyen bir yüzey** oluşturur — kimliği doğrulanmamış bir saldırgan uygulamanın var olduğunu bile göremez. Bu yaklaşım "dark cloud" veya kaynağı gizleme mantığıyla anılır.

### Çalışma mantığı

Tipik akış: Kullanıcı erişim istediğinde önce broker/trust controller kimliği (IdP üzerinden) ve cihaz durumunu doğrular. Politika kararı olumluysa, broker kullanıcı ile hedef uygulama arasında yalnızca o uygulamaya özel, kimlik-doğrulanmış bir tünel/proxy bağlantısı kurar. Kullanıcı ağı "görmez"; yalnızca izinli uygulamaya giden bir yol görür. Karar sürekli yeniden değerlendirilebilir: Cihaz durumu bozulursa (örneğin EDR devre dışı kalırsa) erişim oturum ortasında kesilebilir.

### İstismar mantığı ve savunma (ZTNA)

**İstismar tarafı:** ZTNA saldırı yüzeyini daraltır ama sıfırlamaz. Saldırgan artık ağı tarayamadığından, hedefini **kimlik ve broker** olarak değiştirir: Kimlik bilgisi phishing'i ile geçerli bir kullanıcı gibi görünmek, veya broker/portal'ın kendisindeki bir açığı sömürmek. Ayrıca cihaz durumu kontrolü zayıfsa, saldırgan meşru kullanıcının uyumlu (compliant) cihazından oturumu çalıp (session hijacking) doğrulanmış tünelin üzerine binebilir. ZTNA, kullanıcının yetkili olduğu uygulama içindeki bir güvenlik açığını (örneğin uygulamanın kendi yetkilendirme kusurunu) çözmez — sadece o uygulamaya kimin ulaşabileceğini kontrol eder.

**Savunma tarafı:** Kimlik cephesini phishing'e dirençli MFA ile sertleştirmek (yukarıdaki kimlik direği ile aynı savunma) ZTNA'nın en zayıf halkasını güçlendirir. Broker/erişim altyapısını öncelikli olarak yamalamak kritiktir çünkü o artık merkezî bir kapıdır — kapıyı ele geçiren her yere ulaşır. Güçlü ve sürekli cihaz durumu kontrolü, ele geçirilmiş uyumsuz cihazların içeri girmesini engeller. Uygulama içi güvenliği ihmal etmemek gerekir: ZTNA bir kapıcıdır, uygulamanın kendi giriş kapısı (authorization, input validation) hâlâ ayrıca güvenli olmalıdır. Erişim sonrası davranışı da izlemek — doğrulanmış bir oturumun beklenmedik davranması — hijack edilmiş oturumları yakalar.

## Yaygın Hatalar

**Zero Trust'ı bir ürün sanmak.** En sık ve en pahalı hata. "Zero Trust firewall'u aldık, tamam" düşüncesi yanlıştır. Zero Trust, kimlik, cihaz, ağ, uygulama ve veriyi kapsayan bir mimaridir; tek bir kutu onu sağlamaz. Bir bileşeni (örneğin ZTNA) alıp geri kalan katmanları eski örtük güvenle bırakmak, sahte bir güvenlik hissi yaratır.

**MFA'yı kurup "kimlik tamam" demek.** MFA gereklidir ama tüm MFA'lar eşit değildir. Zayıf (SMS OTP, basit push-onay) MFA, phishing ve MFA fatigue karşısında kırılır. Ayrıca MFA'yı yalnızca giriş anında yapıp, sonrasında oturumu süresiz güvenilir saymak, token hırsızlığına kapı açar.

**Politikaları statik yazmak.** Zero Trust'ın gücü dinamik, risk-tabanlı karardan gelir. "Bir kez izin ver, hep izinli kalsın" mantığı, adaptif değerlendirmeyi öldürür ve modeli klasik erişim listesine (ACL) düşürür.

**Mikrosegmentasyonu görünürlük olmadan yapmaya çalışmak.** Trafik akışlarını bilmeden segment çizmek ya üretimi kırar ya da delik dolu kurallar üretir. Ayrıca yalnızca kuzey-güney (dışarı-içeri) trafiğe odaklanıp doğu-batı (içerideki iş yükleri arası) trafiği izlemesiz bırakmak, yanal hareketi görünmez kılar.

**Makine kimliklerini ve legacy sistemleri unutmak.** Servis hesapları, API'ler, otomasyon botları ve MFA destekleyemeyen eski sistemler çoğu zaman Zero Trust kapsamının dışında bırakılır — ve saldırganın tam da aradığı zayıf halka olurlar. Kapsam dışı her istisna, örtük güvenin geri sızdığı bir çatlaktır.

**Yönetim düzlemini ihmal etmek.** Politika kontrolcüsü, broker, kimlik sistemi — bunlar merkezî güç noktalarıdır. Zero Trust'ı uygulayan altyapının kendisi ele geçirilirse, tüm model çöker. Kontrol düzlemi (control plane) en sıkı korunan katman olmalıdır.

**Kullanıcı deneyimini yok saymak.** Aşırı sürtünme (her adımda tekrar doğrulama, sürekli engellenme) kullanıcıları gölge BT'ye (shadow IT) ve kuralları atlatma yollarına iter. İyi Zero Trust, sürtünmeyi riskle orantılar: düşük riskli erişim sorunsuz, yüksek riskli erişim daha sıkı.

## En İyi Pratikler

**Kademeli ve varlık-öncelikli başlayın.** Zero Trust bir gecede kurulmaz; olgunluk yolculuğudur. Önce en kritik varlıklarınızı (crown jewels) belirleyin — kimlik sistemi, en hassas veriler, Tier 0 altyapı — ve koruma çabasını oradan başlatın. "Herşeyi aynı anda" yaklaşımı çoğu projeyi boğar.

**Kimlikle başlayın, çünkü yeni çevre odur.** Güçlü, tercihen phishing'e dirençli MFA'yı yaygınlaştırmak, SSO ile kimlikleri merkezîleştirmek ve least privilege'ı uygulamak genellikle en yüksek getirili ilk adımdır. Kimlik sağlam değilse üstüne kurulan her katman kumdan olur.

**Cihaz durumunu karara dahil edin.** Kimlik "kim" sorusunu yanıtlar; cihaz durumu "hangi güvenilirlikteki araçtan" sorusunu yanıtlar. Yamalı, şifreli, EDR korumalı bir cihaz ile ele geçirilmiş bir cihaz aynı erişimi almamalıdır.

**Default-deny'i esas alın.** İster ağ segmentasyonunda ister uygulama erişiminde olsun, temel duruş "açıkça izin verilmeyen yasaktır" olmalıdır. İzin listeleri (allowlist), yasak listelerinden (denylist) daima daha güvenlidir çünkü öngörülmeyen her şeyi varsayılan olarak kapatır.

**Sürekli doğrulayın, tek seferlik değil.** Güveni oturum boyunca sürekli yeniden değerlendirin. Risk sinyali değiştiğinde (konum, cihaz durumu, davranış anomalisi) erişimi oturum ortasında yeniden sorgulayın veya iptal edin. Bu, statik "bir kez giriş" modelinden Zero Trust'ı ayıran temel farktır.

**Görünürlük ve loglamayı temel altyapı sayın.** Karar veremediğiniz şeyi göremezsiniz; göremediğiniz şeyi savunamazsınız. Kimlik olaylarını, erişim kararlarını, doğu-batı trafiğini merkezî olarak toplayın ve analiz edin. Bu hem politika iyileştirmenin hem de ihlal tespitinin yakıtıdır.

**Assume breach ile tasarlayın ve test edin.** Saldırganın zaten içeride olduğunu varsayarak patlama yarıçapını her katmanda küçültün. Bu varsayımı düzenli olarak sınayın — kırmızı takım (red team) tatbikatları ve saldırı simülasyonları, teoride kusursuz görünen politikaların pratikteki deliklerini ortaya çıkarır.

**Least privilege'ı zamanla da sınırlayın.** Yalnızca "ne kadar" değil, "ne kadar süre" de önemlidir. Kalıcı ayrıcalıklar yerine JIT (Just-In-Time) ve gerektiğinde yükseltme (elevation) modeli, ele geçirilmiş bir hesabın kullanabileceği pencereyi daraltır.

**İnsan ve süreç boyutunu unutmayın.** Zero Trust bir teknoloji projesinden fazlasıdır. Yönetişim, sahiplik, istisna yönetimi ve kullanıcı eğitimi olmadan en iyi araçlar bile zamanla erozyona uğrar. İstisnaları izlenebilir, süreli ve gözden geçirilir tutun; kalıcı istisna, örtük güvenin yeniden doğduğu yerdir.

## Kapanış

Zero Trust'ın özü tek bir zihinsel dönüşümdür: Güveni bir konuma değil, her etkileşimde yeniden kanıtlanan bir karara bağlamak. Kimlik yeni çevredir, mikrosegmentasyon patlama yarıçapını sınırlar, ZTNA örtük güvenli VPN'i uygulama-merkezli en az yetkiye çevirir — ve "assume breach" tüm bunları birbirine bağlayan varsayımdır. Doğru uygulandığında Zero Trust, ilk ihlali imkânsız kılmaz (hiçbir mimari bunu vaat edemez); yaptığı şey, o ihlalin bir felakete dönüşmesini engellemektir. Asıl kazanç budur.
