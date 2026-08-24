# Risk Değerlendirmesi

## Tanım

Risk değerlendirmesi, bir sistemin, uygulamanın ya da kurumun karşı karşıya olduğu tehditleri sistematik biçimde belirleme, bu tehditlerin gerçekleşme olasılığını ve gerçekleştiğinde doğuracağı etkiyi ölçme ve elde edilen sonuçlara göre hangi zafiyetin önce ele alınacağına karar verme sürecidir. Siber güvenliğin çoğu alanı bir zafiyeti *bulmaya* ya da *kapatmaya* odaklanır; risk değerlendirmesi ise bir adım geri çekilip "elimizdeki onlarca, bazen binlerce bulgudan hangisi gerçekten canımızı yakar, hangisine önce koşmalıyız?" sorusunu cevaplar. Yani teknik bir tespit faaliyeti değil, bir *karar verme çerçevesidir*.

Bu ayrımı vurgulamak önemlidir çünkü sahada en sık yapılan yanlış, risk ile zafiyeti birbirine karıştırmaktır. Bir zafiyet (vulnerability) sistemdeki bir zayıflıktır. Tehdit (threat) bu zayıflığı kullanabilecek bir aktör ya da olaydır. Risk ise bu ikisinin bir araya gelmesiyle ortaya çıkan *beklenen kayıptır*. Klasik ve hâlâ en doğru tanım şudur:

> **Risk = Tehdit × Zafiyet × Etki**

Ya da uygulamada en çok kullanılan sadeleştirilmiş biçimiyle:

> **Risk = Olasılık × Etki**

## Kök neden: Neden olasılık ve etkiyi ayrı ayrı ölçeriz?

Risk değerlendirmesinin kalbinde şu gözlem yatar: bir olayın *ne kadar kötü* olduğu ile *ne kadar sık başına geleceği* birbirinden bağımsız iki boyuttur ve bunları tek bir sezgisel "tehlikeli/tehlikesiz" yargısında birleştirmek insanı sistematik olarak yanıltır.

Bir örnekle düşünelim. İnternete açık, kimlik doğrulaması olmayan bir yönetim panelinde çok düşük etkili bir bilgi sızıntısı (örneğin sunucu sürüm bilgisinin görünmesi) olsun. Etkisi düşüktür ama sömürülme olasılığı neredeyse kesindir; her tarayıcı botu bunu görecektir. Öte yandan, yalnızca fiziksel erişimi olan bir saldırganın, özel bir donanım ile yan kanal (side-channel) saldırısı yaparak şifreleme anahtarını çıkarabildiği bir zafiyet düşünün. Etkisi felakettir ama gerçekleşme olasılığı çoğu kurum için son derece düşüktür.

Eğer bu iki boyutu ayırmadan tek bir "tehlike hissi" ile karar verseydik, çarpıcı ama olasılığı düşük senaryoya (yan kanal saldırısı) gereğinden fazla, sıradan ama neredeyse kesin olan sızıntıya ise gereğinden az kaynak ayırırdık. İnsan zihni "dramatik" olanı "olası" olanla karıştırma eğilimindedir; buna availability bias denir. Risk formülünün olasılık ve etkiyi ayrı çarpanlar olarak zorunlu kılmasının kök nedeni tam olarak bu bilişsel yanlılığı disiplin altına almaktır.

Çarpım kullanmanın da bir mantığı vardır: toplama değil çarpma. Çünkü boyutlardan biri sıfıra yaklaşırsa risk de sıfıra yaklaşmalıdır. Etkisi hiç olmayan bir olay, ne kadar sık gerçekleşirse gerçekleşsin risk taşımaz; hiç gerçekleşemeyecek bir olayın etkisi ne kadar büyük olursa olsun beklenen kaybı sıfırdır. Toplama bu davranışı vermez, çarpma verir.

### Olasılık × Etki matrisinin çalışma mantığı

En yaygın pratik araç, olasılık ve etkiyi ayrı ayrı derecelendirip (tipik olarak 1-5 ya da Düşük/Orta/Yüksek/Kritik gibi) bir matris üzerinde kesiştirmektir. Matrisin her hücresi bir risk seviyesine (genellikle renk kodlu: yeşil/sarı/turuncu/kırmızı) karşılık gelir.

Bu matrisin gücü basitliğinde ve iletişim değerindedir; teknik olmayan yöneticiler bile kırmızı bir hücreyi anlar. Ancak kök nedenini bilmeden kullananların düştüğü tuzak şudur: matris *ordinal* (sıralı) bir ölçektir, *kardinal* (oransal) değil. "Yüksek olasılık" (4) ile "orta olasılık" (2) arasındaki gerçek olasılık farkı iki kat değildir; 4 puanlık bir olayın gerçek yıllık olasılığı belki %60, 2 puanlık bir olayınki %5 olabilir. Bu yüzden matris hücrelerini çarpıp elde edilen sayıları sanki gerçek para birimiymiş gibi işleme sokmak matematiksel olarak yanlıştır. Matris *kabaca önceliklendirme* için iyidir; *kesin bütçeleme* için değildir.

Nicel (kantitatif) tarafta ise bu sezgi paraya çevrilir. Klasik formüller:

- **SLE (Single Loss Expectancy)** = Varlık Değeri × Exposure Factor (tek bir olayda kaybedilen oran)
- **ARO (Annualized Rate of Occurrence)** = olayın yıllık beklenen tekrar sayısı
- **ALE (Annualized Loss Expectancy)** = SLE × ARO

ALE, "bu risk bize yılda ortalama kaç lira kaybettirir" sorusunu cevaplar ve bir güvenlik kontrolüne yılda ondan az harcıyorsak kontrolün ekonomik olarak mantıklı olduğunu söyler. Bu, olasılık × etki mantığının doğrudan finansal ifadesidir.

## CVSS: Zafiyet ciddiyetini standartlaştırmak

CVSS (Common Vulnerability Scoring System), tek tek yazılım zafiyetlerinin teknik ciddiyetini 0.0-10.0 arası bir puanla ifade eden, endüstri standardı açık bir çerçevedir. FIRST kuruluşu tarafından sürdürülür. Bir CVE yayımlandığında yanında gördüğünüz "9.8 Critical" gibi ifadeler CVSS puanlarıdır.

### CVSS neden var ve nasıl çalışır?

CVSS'in var oluş nedeni ortak bir dildir. Farklı satıcılar, farklı araştırmacılar zafiyetleri farklı kelimelerle tanımladığında karşılaştırma imkânsız hale gelir. CVSS, ciddiyeti standart bir vektör ve puana indirgeyerek "bizim A ürünündeki zafiyet, B ürünündeki zafiyetten daha mı ciddi?" sorusunu nesnel biçimde cevaplanabilir kılar.

CVSS puanı, birkaç grup metriğin birleşiminden hesaplanır. Bunları kavramsal olarak üç aileye ayırabiliriz:

**Base (Temel) metrikler** — zafiyetin zamandan ve ortamdan bağımsız, doğuştan gelen özelliklerini ölçer. Bu grup kendi içinde iki bölüme ayrılır:

- *Exploitability* (sömürülebilirlik) metrikleri: Saldırı vektörü (Attack Vector — ağ üzerinden mi, yerel mi, fiziksel mi erişim gerektiriyor?), saldırı karmaşıklığı (Attack Complexity), gereken yetki seviyesi (Privileges Required) ve kullanıcı etkileşimi gerekip gerekmediği (User Interaction). Bu metrikler kabaca "olasılık" tarafına karşılık gelir: uzaktan, karmaşıklık gerektirmeden, yetkisiz ve kullanıcı etkileşimsiz sömürülebilen bir zafiyet en kolay istismar edilebilendir.
- *Impact* (etki) metrikleri: Gizlilik (Confidentiality), bütünlük (Integrity) ve erişilebilirlik (Availability) üzerindeki etki — yani klasik CIA üçlüsü. Bu üçlü doğrudan "etki" tarafını temsil eder.

Dikkat ederseniz CVSS'in kendisi de risk formülünün olasılık × etki iskeletini yeniden üretir: sömürülebilirlik metrikleri olasılığı, CIA etkisi etkiyi modeller.

**Temporal (Zamansal) metrikler** — zamanla değişen özellikler: sömürü kodunun olgunluk seviyesi (bir PoC mı var, silah haline getirilmiş bir exploit mi dolaşıyor?), bir yamanın mevcut olup olmadığı, raporun güvenilirliği. Bir zafiyetin Base puanı sabit kalır ama silah haline getirilmiş exploit ortaya çıktığında zamansal metrikler gerçek riski yükseltir.

**Environmental (Çevresel) metrikler** — zafiyetin *sizin* ortamınızdaki önemini modeller. Aynı zafiyet, halka açık pazarlama sitenizde farklı, ödeme altyapınızda çok farklı bir gerçek risk taşır. Çevresel metrikler, etkilenen varlığın CIA gereksinimlerini ağırlıklandırmanıza izin verir.

### CVSS'i doğru okumak: Bir puan bir risk değildir

Buradaki en kritik ve en sık atlanan kavram şudur: **CVSS Base puanı bir ciddiyet ölçüsüdür, bir risk ölçüsü değildir.** Çoğu kurum sadece Base puana bakar, Temporal ve Environmental metrikleri hiç işlemez ve "9.8 gördüm, panik" ya da "5.3, boş ver" diye karar verir. Bu ciddi bir hatadır.

Somut düşünelim: 9.8 Base puanlı, uzaktan sömürülebilen bir zafiyet, tamamen izole edilmiş, internete kapalı, üzerinde değersiz test verisi olan bir laboratuvar sunucusundaysa gerçek riski düşüktür. Buna karşılık 6.5 Base puanlı bir zafiyet, doğrudan internete açık, müşteri kişisel verisi (PII) barındıran, silah haline getirilmiş exploit'i halihazırda dolaşan bir sistemdeyse gerçek risk kırmızıdır. Base puan başlangıç noktasıdır; ona varlık kritikliği, maruz kalma (exposure) ve tehdit istihbaratı eklenmeden karar verilmez.

Ayrıca kesinlikle bilmediğim tam sürüm numaralarını ya da spesifik CVE kimliklerini burada uydurmayacağım; önemli olan yöntemin kendisidir: bir CVSS vektörünü gördüğünüzde onu ayrıştırıp hangi metriğin sizin ortamınızda geçerli olduğunu sorgulamak.

## DREAD: Tehdit modellemede öznel bir derecelendirme

DREAD, tehditleri beş boyutta puanlayarak sıralamak için kullanılan bir kısaltmadır. Adı beş bileşeninin baş harflerinden gelir:

- **Damage** (Hasar): Sömürü başarılı olursa ne kadar zarar verir?
- **Reproducibility** (Tekrarlanabilirlik): Saldırıyı tekrar tekrar gerçekleştirmek ne kadar kolay ve güvenilirdir?
- **Exploitability** (Sömürülebilirlik): Saldırıyı başlatmak için ne kadar çaba, beceri ve araç gerekir?
- **Affected Users** (Etkilenen Kullanıcılar): Kaç kullanıcı ya da sistemin bileşeni etkilenir?
- **Discoverability** (Keşfedilebilirlik): Zafiyetin bir saldırgan tarafından bulunması ne kadar kolaydır?

Her boyut genellikle 1-10 (ya da düşük/orta/yüksek için 1/2/3) arası puanlanır, puanlar toplanır veya ortalaması alınır, ortaya çıkan sayı tehditleri sıralamakta kullanılır.

### DREAD'in çalışma mantığı ve zayıf noktası

DREAD, Microsoft kaynaklı bir yaklaşım olarak, özellikle uygulama geliştirme sürecinde tehdit modelleme (örneğin STRIDE ile tehditleri *belirledikten* sonra onları *önceliklendirmek* için) popülerleşti. Cazibesi basitliğinde ve geliştiricilerle konuşurken sezgisel olmasındadır. Bir mühendis "bu ne kadar hasar verir, ne kadar kolay bulunur?" sorularını doğal bulur.

Ancak DREAD'in kök zayıflığı öznelliğidir. Aynı tehdide iki farklı analistin verdiği puanlar ciddi ölçüde farklılaşabilir, çünkü "Discoverability için 7 mi 4 mü?" sorusunun nesnel bir cevabı yoktur. Bu yüzden birçok kurum, Microsoft'un kendisi de dahil, DREAD'i zamanla resmi süreçlerinden büyük ölçüde geri çekti ya da yalnızca kaba sıralama aracı olarak sınırladı. Tutarlılığı artırmak için mutlaka her puan seviyesinin ne anlama geldiğini önceden tanımlayan bir rubrik (örneğin "Discoverability 3 = zafiyet herkese açık dokümantasyondan görülebilir") oluşturmak gerekir; aksi halde sayılar tutarsız ve savunulamaz olur.

Bir başka teknik itiraz: DREAD bileşenlerini *toplamak*, olasılık ve etki boyutlarını matematiksel olarak birbirine karıştırır. Damage bir etki metriğiyken; Reproducibility, Exploitability, Discoverability olasılık/kolaylık metrikleridir. Bunları düz toplamak, yüksek hasarlı ama zor sömürülen bir tehdidi, düşük hasarlı ama çok kolay sömürülen bir tehditle aynı toplam puana getirebilir; oysa bunların risk profilleri çok farklıdır. Daha olgun bir yaklaşım, hasar (etki) eksenini kolaylık (olasılık) ekseninden ayrı tutup çarpmaktır — yani DREAD'i risk = olasılık × etki mantığına geri bağlamaktır.

## Sömürü/istismar mantığı ile savunmanın birlikte düşünülmesi

Risk değerlendirmesi doğası gereği hem saldırganın hem de savunmacının bakış açısını aynı anda tutmayı gerektirir. Puan verirken saldırgan gibi düşünmek zorundasınız; önlem alırken savunmacı gibi.

### Saldırgan tarafı: Puanlar saldırı yüzeyini nasıl ele verir

Bir saldırgan, savunmacının hazırladığı risk envanterinin *tersini* düşünür. Savunmacı için "yüksek olasılık × yüksek etki" en acil kapatılacak hücreyken, saldırgan için aynı hücre en yüksek getirili hedeftir. Saldırgan da aslında zihinsel olarak bir risk hesabı yapar: bir hedefin sömürülme *maliyeti* (gereken beceri, zaman, tespit edilme riski) ile *ödülü* (elde edilecek erişim, veri, kalıcılık). CVSS'in Exploitability metriklerinin ya da DREAD'in Exploitability/Discoverability bileşenlerinin yüksek çıktığı yerler, saldırganın "ucuz ve güvenilir" bulduğu yerlerdir.

Bu yüzden bir risk değerlendirmesi tablosu düşmanın eline geçerse, ona bir yol haritası verir. Değerlendirme çıktıları hassas belgelerdir ve öyle korunmalıdır. Aynı zamanda savunmacı, saldırganın önceliklendirmesini taklit ederek kendi önceliklendirmesini keskinleştirebilir: "Ben saldırgan olsam nereye vururdum?" sorusu, kâğıt üzerindeki CVSS puanının maruz kalma ile birleşince nasıl değiştiğini görmeyi sağlar.

### Savunma tarafı: Riski düşürmenin dört yolu

Risk değerlendirmesinin çıktısı bir eylem kararıdır. Her risk için dört klasik seçenek vardır ve doğru seçim risk seviyesine göre değişir:

1. **Azaltma (Mitigate)**: Bir kontrol ekleyerek olasılığı ya da etkiyi düşürmek. En yaygın yol. Örneğin uzaktan sömürülebilirliği bir WAF ya da ağ segmentasyonu ile azaltmak (olasılığı düşürür), ya da veriyi şifreleyerek sızma durumundaki etkiyi düşürmek.
2. **Transfer (Transfer)**: Riski bir başkasına devretmek — siber sigorta ya da hizmeti bir sağlayıcıya taşımak. Etki finansal olarak paylaşılır ama sorumluluk tam olarak devredilmez.
3. **Kabul (Accept)**: Risk yeterince düşükse ya da azaltma maliyeti beklenen kayıptan büyükse, riski bilinçli ve belgelenmiş biçimde kabul etmek. ALE hesabı burada devreye girer: yılda 1.000 lira beklenen kayba karşı 50.000 liralık bir kontrol ekonomik değildir.
4. **Kaçınma (Avoid)**: Riskli özelliği ya da faaliyeti tamamen terk etmek. Bazen en güvenli servis, hiç açılmayan servistir.

Savunma tasarlarken kritik ilke *derinlemesine savunmadır* (defense in depth): tek bir kontrole güvenmek yerine, olasılığı düşüren kontroller (erişim denetimi, yama yönetimi) ile etkiyi düşüren kontrolleri (segmentasyon, şifreleme, yedekleme) katmanlamak. Çünkü risk formülünde olasılık *ya da* etkiyi düşürmek riski düşürür; ikisini birden düşürmek çarpım etkisiyle riski çok daha aşağı çeker.

## Önceliklendirme: Sınırlı kaynağı en yüksek riske yöneltmek

Risk değerlendirmesinin nihai amacı önceliklendirmedir. Hiçbir kurumun her bulguyu aynı anda kapatacak kaynağı yoktur; mesele hangi sırayla koşacağınızdır.

### Neden yalnızca CVSS'e göre sıralamak yetmez

Yaygın ve tehlikeli bir uygulama, bütün zafiyetleri CVSS Base puanına göre yukarıdan aşağı sıralayıp "önce tüm 9'ları, sonra 8'leri kapatalım" demektir. Bu neden yanlıştır? Çünkü daha önce vurgulandığı gibi Base puan gerçek riski değil, teknik ciddiyeti ölçer. Yüksek Base puanlı ama internete kapalı, kimsenin sömürmeye çalışmadığı bir zafiyet, düşük Base puanlı ama aktif olarak sömürülen ve internete açık bir zafiyetin önüne geçirilirse, ekip yanlış işi yapar.

Olgun önceliklendirme en az üç girdiyi birleştirir:

- **Teknik ciddiyet** (CVSS Base): Zafiyet ne kadar güçlü?
- **Tehdit bağlamı** (Temporal / tehdit istihbaratı): Bu zafiyet *gerçek dünyada aktif olarak sömürülüyor mu?* Bir zafiyetin vahşi doğada istismar edildiğine dair kanıt, önceliği dramatik biçimde yükseltir. (Kamu otoritelerinin yayımladığı "bilinen sömürülen zafiyetler" listeleri tam da bu bağlamı verir; bilmediğim spesifik liste adlarını uydurmuyorum ama kavram budur: exploit'in aktif olup olmadığı önceliği belirler.)
- **İş bağlamı** (Environmental / varlık kritikliği ve maruz kalma): Etkilenen sistem sizin için ne kadar değerli ve ne kadar erişilebilir?

Bu üçünün birleşimi, çıplak CVSS sıralamasından çok daha isabetli bir eylem listesi verir. Modern risk temelli zafiyet yönetimi (risk-based vulnerability management) yaklaşımının özü tam olarak budur.

### İstismar olasılığını ölçen tamamlayıcı ölçütler

CVSS'in bir zafiyetin gerçekte sömürülme *olasılığını* iyi tahmin etmediği kabul edilen bir gerçektir; CVSS ciddiyeti ölçer, olasılığı değil. Bu boşluğu doldurmak için, bir zafiyetin yakın gelecekte sömürülme olasılığını istatistiksel olarak tahmin etmeyi amaçlayan tamamlayıcı skorlama sistemleri geliştirilmiştir (istismar tahminine odaklanan olasılık skorları). Bunları CVSS ile birlikte kullanmanın mantığı doğrudan risk = olasılık × etki formülüne dayanır: CVSS etki/ciddiyet tarafını, istismar olasılığı skoru olasılık tarafını besler. İkisini çarpıp önceliklendirdiğinizde, "yüksek puanlı ama kimsenin sömürmeyeceği" zafiyetlerle vaktinizi harcamaz, "orta puanlı ama yarın sömürülecek" olanları öne alırsınız.

## Yaygın hatalar

**Riski zafiyetle karıştırmak.** En temel hata. Zafiyet sayısını raporlamak ("3.000 açığımız var") bir risk ifadesi değildir; bunların kaçının gerçekten sömürülebilir ve kritik varlıklara dokunduğu söylenmeden hiçbir anlam taşımaz.

**Ordinal puanları kardinal gibi işlemek.** 1-5 matris puanlarını ya da CVSS'in 0-10 skalasını gerçek para ya da gerçek olasılık gibi çarpıp toplamak. "9 puan, 3 puanın üç katı risklidir" ifadesi matematiksel olarak yanlıştır; bu ölçekler sıralıdır, oransal değildir.

**Yalnızca Base CVSS'e bakıp bağlamı yok saymak.** Temporal ve Environmental metrikleri, tehdit istihbaratını ve varlık kritikliğini işlemeden karar vermek, ekibi sürekli yanlış önceliğe yönlendirir.

**DREAD puanlarını rubrik olmadan vermek.** Her analistin kafasına göre puan verdiği, tanımsız bir DREAD tablosu tutarsız ve savunulamazdır; sonuçları kimseyi ikna etmez.

**Olasılığı sabit varsaymak.** Risk statik değildir. Yeni bir exploit çıktığında, sistem internete açıldığında ya da bir tehdit aktörü sektörünüzü hedef aldığında olasılık değişir. Bir kez yapılıp rafa kaldırılan risk değerlendirmesi hızla eskir.

**Etkiyi yalnızca teknik açıdan düşünmek.** Etki sadece "sunucu çöktü" değildir; itibar kaybı, yasal/regülasyon cezaları (kişisel veri ihlallerinde olduğu gibi), iş sürekliliği kaybı ve müşteri güveni de etkinin parçalarıdır. Teknik ekiplerin en sık gözden kaçırdığı boyut budur.

**Kuyruk (tail) risklerini görmezden gelmek.** Olasılığı çok düşük ama etkisi felaket boyutunda olan olaylar (örneğin tüm yedeklerin şifrelendiği bir ransomware) beklenen değer hesabında küçük görünebilir ama kurumu batırabilir. Sadece ortalamaya (ALE) bakmak bu kuyruk risklerini gizler.

## En iyi pratikler

**Nitel ve nicel yaklaşımları birlikte kullanın.** Nitel matris (Düşük/Orta/Yüksek) hızlı tarama, iletişim ve ilk elemede mükemmeldir. Kritik ya da tartışmalı riskler için nicel analize (SLE, ARO, ALE) geçip kararı parayla destekleyin. Her şeyi nicelleştirmeye çalışmak zaman kaybıdır; hiçbir şeyi nicelleştirmemek ise büyük kararları sezgiye bırakır.

**Puanlama için yazılı rubrik oluşturun.** İster CVSS Environmental metriklerini, ister DREAD'i, ister kendi matrisinizi kullanın, her seviyenin ("olasılık 4 = yılda birden fazla beklenen") ne anlama geldiğini önceden yazın. Bu, farklı analistler arasında tutarlılık ve zaman içinde karşılaştırılabilirlik sağlar.

**Tehdit istihbaratını önceliklendirmeye entegre edin.** Bir zafiyetin vahşi doğada aktif sömürülüp sömürülmediği, tek başına Base puandan daha güçlü bir öncelik sinyalidir. Aktif sömürülen zafiyetler, puanı ne olursa olsun listenin başına çıkmalıdır.

**Varlık envanteri ve kritiklik sınıflandırması tutun.** Environmental değerlendirme, hangi varlığın kritik olduğunu bilmeden yapılamaz. Neyin nerede olduğunu, hangi verinin nerede aktığını bilmeyen kurum, riski doğru ağırlıklandıramaz. Risk değerlendirmesinin ön koşulu iyi bir varlık yönetimidir.

**Riski canlı bir kayıt olarak yönetin.** Bir risk kaydı (risk register) oluşturun; her risk için sahip, seviye, seçilen tepki (azalt/transfer/kabul/kaçın), son değerlendirme tarihi ve tekrar gözden geçirme tarihi bulunsun. Kabul edilen riskler açıkça ve yetkili onayıyla belgelenmelidir; "biri bir yerde kabul etmişti" savunulabilir değildir.

**Kalan riski (residual risk) hesaba katın.** Bir kontrol uyguladıktan sonra risk sıfırlanmaz, azalır. Geriye kalan riski ölçün ve bunun kabul edilebilir eşiğin altında olup olmadığını değerlendirin. "Yamayı yaptık, güvendeyiz" düşüncesi genellikle kalan riski görmezden gelir.

**Karar vericiyle onun dilinde konuşun.** Yönetime CVSS vektörü değil, "bu risk gerçekleşirse şu kadar TL ve şu kadar itibar kaybı beklenir, azaltmak şu kadara mal olur" ifadesi ulaşır. Risk değerlendirmesinin nihai değeri, teknik gerçeği iş kararına çevirebilmesindedir. Aksi halde en doğru analiz bile rafta kalır.

## Kapanış

Risk değerlendirmesi, siber güvenliği bir "her açığı kapatma" yarışından, "sınırlı kaynağı en yüksek beklenen kayba yönlendirme" disiplinine dönüştüren şeydir. Olasılık × etki temel iskelettir; CVSS bu iskeletin zafiyet ciddiyetini standartlaştırır; DREAD tehdit modellemede kaba bir sıralama sunar ama öznelliği nedeniyle rubrik ve dikkat gerektirir; önceliklendirme ise bütün bunları tehdit istihbaratı ve iş bağlamıyla birleştirerek nihai eylem listesini üretir. Sağlam bir risk değerlendirmesi, hem saldırgan gibi düşünmeyi hem savunmacı gibi karar vermeyi, hem sayıları hem de sayıların ardındaki iş gerçeğini aynı anda tutmayı gerektirir.
