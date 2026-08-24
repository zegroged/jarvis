# DevSecOps ve Güvenlik Pipeline Entegrasyonu: SAST/DAST/SCA/IaC Tarama Otomasyonu, Kalite Kapıları ve Triage Süreci

## Tanım

DevSecOps, "Development", "Security" ve "Operations" kelimelerinin birleşiminden oluşan, güvenliği yazılım teslim sürecinin (SDLC) ayrı ve sona bırakılmış bir aşaması olmaktan çıkarıp CI/CD pipeline'ının içine gömen bir mühendislik pratiğidir. Secure SDLC güvenliği *neyin ne zaman yapılması gerektiğini* tanımlayan bir süreç çerçevesidir (tehdit modelleme, güvenli tasarım incelemesi, güvenlik testi); CI/CD ise kodu otomatik olarak derleyip test edip dağıtan bir mekanizmadır. DevSecOps, bu ikisinin kesişimidir: Secure SDLC'nin gerektirdiği güvenlik kontrollerini, CI/CD pipeline'ının somut, otomatik, çalıştırılabilir adımlarına dönüştürme disiplinidir.

Bu, salt "pipeline'a bir güvenlik tarayıcısı ekle" demek değildir. Asıl mühendislik problemi şudur: bir tarayıcı çalıştırmak kolaydır; onun ürettiği yüzlerce/binlerce bulguyu **doğru eşikte pipeline'ı durduracak** (break-the-build) şekilde yapılandırmak, gürültüyü elemek, gerçek bulguları geliştiriciye zamanında ve anlaşılır biçimde ulaştırmak ve bunları bir **triage** (önceliklendirme ve karar) sürecinden geçirmek — işte DevSecOps mühendisliğinin asıl ağırlığı burada yatar. Bu makale dört tarama disiplinini (SAST, DAST, SCA, IaC taraması), bunların pipeline içindeki yerleşimini, kalite kapısı (quality gate) tasarımını ve sonuç triage sürecini bir savunma/tespit mühendisi gözüyle ele alır.

## Kök Neden: Güvenlik Neden Pipeline'a Gömülmeli?

### Denetim modelinin yapısal başarısızlığı

Klasik model, güvenliği ayrı bir ekibin (genellikle "AppSec" veya "InfoSec") yaptığı, geliştirme bittikten sonra devreye giren bir **kapı denetimi** (gate audit) olarak konumlandırır: kod yazılır, test edilir, dağıtıma hazırlanır, sonra güvenlik ekibi haftalarca sürecek bir penetrasyon testi veya manuel kod incelemesi yapar. Bu modelin kök nedensel çöküşü üç noktadan gelir:

Birincisi, **geri bildirim gecikmesi**. Bir güvenlik açığı, kodun yazıldığı andan haftalar/aylar sonra bulunduğunda, geliştirici o kodun bağlamını çoktan unutmuştur; düzeltme maliyeti disk üzerinde küçük bir diff olsa bile, zihinsel yeniden bağlamlama (re-contextualization) maliyeti yüksektir. Bu, CI/CD'nin "shift left" mantığıyla birebir aynı ekonomik argümandır: bir hatayı bulma maliyeti, bulunduğu ana ne kadar yakınsa o kadar düşüktür.

İkincisi, **ölçek uyumsuzluğu**. Modern teslimat hızında (günde onlarca dağıtım) haftalık/aylık manuel güvenlik denetimi darboğaz haline gelir. Ekip ya dağıtım hızını güvenlik denetimine göre yavaşlatır (iş hedefleriyle çelişir) ya da güvenliği atlar (risk birikir). Otomasyonun kök nedensel değeri, kontrolü *dağıtım hızını yavaşlatmadan* uygulayabilmesidir — çünkü makine saniyeler içinde tarar, insan ise günler harcar.

Üçüncüsü, **sorumluluk belirsizliği**. Güvenlik "başka bir ekibin işi" olduğunda, geliştirici kendi kodunun güvenlik sonuçlarından kopar; hataları düzeltmek yerine "güvenlik ekibi engelliyor" tepkisi doğar. DevSecOps'un kültürel tezi, güvenlik bulgusunun geliştiriciye *kendi pull request'inde*, kendi diliyle (hangi dosya, hangi satır, neden riskli) ulaşmasıdır — bu, sahiplenmeyi mümkün kılan tek teslimat şeklidir.

### "Pipeline'a gömme" ne anlama gelir, ne anlama gelmez

Güvenliği pipeline'a gömmek, güvenlik uzmanlarının işini otomasyonla *ikame etmek* değildir; onların bilgisini **ölçeklenebilir, tekrarlanabilir bir kural kümesine** kodlamaktır. Bir SAST kuralı, bir güvenlik mühendisinin "bu desen risklidir" bilgisini makinenin her commit'te kontrol edebileceği bir imzaya dönüştürür. Ancak makine yalnızca *bildiği desenleri* bulur; iş mantığı açıkları, kimlik doğrulama akışındaki tasarım hataları veya yeni nesil saldırı teknikleri gibi konularda insan incelemesinin (tehdit modelleme, manuel pentest, güvenlik mimarisi gözden geçirmesi) yerini tutmaz. Olgun bir DevSecOps kurulumu bunu şöyle dengeler: otomasyon *hacimli, tekrarlayan, bilinen* riskleri eler; insan uzmanlık *yüksek riskli, nadir, karmaşık* noktalara yönlendirilir. Bu ayrımı unutmak, "taramalar geçti, o yüzden güvenliyiz" yanlış güvenine (false sense of security) yol açar — bu, DevSecOps'un en yaygın olgunlaşmamışlık belirtisidir.

## Dört Tarama Disiplini: Mekanizma ve Pipeline'daki Yerleşim

Her tarama türü, farklı bir soruyu farklı bir bilgi kaynağından cevaplar. Bu farkı anlamak, hangisinin pipeline'ın hangi aşamasına konulacağını da belirler.

### SAST (Static Application Security Testing): Kaynağı okuyarak akıl yürütme

**Mekanizma:** SAST aracı kodu *çalıştırmadan* okur. Genellikle kodu bir soyut sözdizimi ağacına (AST) veya kontrol/veri akış grafiğine dönüştürür, sonra bilinen tehlikeli desenleri (ör. kullanıcı girdisinin doğrudan bir SQL sorgusuna veya komut çalıştırma fonksiyonuna ulaşması — "taint analysis" ile kaynaktan `source`'dan hedefe `sink`'e giden kirli veri yolunu izler) arar. Bazı araçlar yalnızca desen eşleştirme (regex benzeri kural) yapar, daha gelişmiş olanlar gerçek veri akışı analizi (taint tracking) uygular.

**Neden erken çalışır:** SAST çalışan bir uygulama veya ortam gerektirmez; yalnızca kaynak koda ihtiyaç duyar. Bu onu pipeline'ın en ucuz ve en erken çalıştırılabilir güvenlik kontrolü yapar — commit veya pull request anında, hatta IDE içinde (geliştirici yazarken) çalıştırılabilir.

**Kör noktaları:** SAST, çalışma zamanı bağlamını (runtime context) bilmez. Bir fonksiyonun pratikte hiç kullanıcı girdisiyle çağrılmadığını, veya bir güvenlik açığının bir önceki katmanda (ör. bir doğrulama middleware'i) zaten engellendiğini göremeyebilir — bu **yanlış pozitif** üretir. Ayrıca konfigürasyon hatalarını, çalışma zamanı ortam sorunlarını veya birden fazla servisin etkileşiminden doğan açıkları (mikroservis mimarisinde servisler arası yetki sızıntısı gibi) yakalayamaz, çünkü tek bir kod tabanının statik görünümüyle sınırlıdır.

### DAST (Dynamic Application Security Testing): Çalışan sistemi dışarıdan sınama

**Mekanizma:** DAST aracı, kaynak koda erişimi olmadan (kara kutu / black-box), çalışan bir uygulamaya gerçek bir saldırganın yapacağı gibi HTTP istekleri gönderir: form alanlarına özel karakterler enjekte eder, hata mesajlarını analiz eder, yetkisiz uç noktalara erişmeyi dener. Uygulamanın *gerçek davranışını* gözlemler; kodun ne dediğini değil, sistemin ne yaptığını test eder.

**Neden geç çalışır:** DAST'ın çalışması için dağıtılmış, ayakta bir uygulama gerekir. Bu yüzden pipeline'da SAST'tan sonra, genellikle bir test/staging ortamına dağıtım sonrasında devreye girer. Daha yavaştır (gerçek ağ istekleri, sayfa render'ları içerir) ve pipeline'ı önemli ölçüde uzatabileceği için genellikle her commit'te değil, günlük/gece taramaları veya release öncesi kapı olarak çalıştırılır.

**Kör noktaları:** DAST, uygulamanın *gördüğü* dış yüzeyle sınırlıdır; kimlik doğrulama gerektiren derin iş akışlarına ulaşmakta zorlanabilir, kaynak kod düzeyinde "neden" açıklaması veremez (yalnızca "bu istek beklenmedik şekilde 200 döndü" der, kodun hangi satırının sorumlu olduğunu bilmez). SAST ile DAST'ın birbirini tamamlaması budur: SAST "kodda potansiyel olarak tehlikeli bir desen var" der, DAST "bu tehlikeli desen gerçekten dışarıdan istismar edilebilir mi" sorusunu — çalışan sistem üzerinde — sınar. Bir kuruluş yalnızca birini seçmek zorunda kalırsa, ikisinin farklı yalan/doğru profilleri olduğu unutulmamalıdır: SAST çok sayıda potansiyel bulguyu erken yakalar ama gürültülüdür; DAST daha az ama gerçek-dünya doğrulamalı bulgu üretir, geç ve pahalıdır.

### SCA (Software Composition Analysis): Tedarik zinciri riski

**Mekanizma:** SCA aracı, projenin bağımlılık ağacını (doğrudan ve geçişli/transitive bağımlılıklar dahil) çıkarır ve her bileşeni bilinen açık veritabanlarıyla (kamuya açık güvenlik açığı kayıtları) eşleştirir. Bu tamamen farklı bir bilgi kaynağı kullanır: SAST ve DAST *sizin yazdığınız* kodu inceler, SCA ise *başkalarının yazdığı, sizin kullandığınız* kodu inceler.

**Neden kritik:** Modern bir uygulamanın kod hacminin büyük kısmı üçüncü parti kütüphanelerden gelir. Bir bağımlılıkta açık bulunduğunda, o açığı kullanan *her* uygulama otomatik olarak savunmasız hale gelir — bu, tek bir zafiyetin binlerce projeye yayılmasına yol açan tedarik zinciri (supply chain) riskinin temelidir. SCA'nın kök nedensel değeri, bu riski insan hafızasına değil otomatik envanter takibine bağlamasıdır: hiçbir mühendis yüzlerce geçişli bağımlılığın sürümünü ve açık durumunu manuel takip edemez.

**Tuzaklar:** Geçişli bağımlılıklar (bir bağımlılığın bağımlılığı) genellikle görünmezdir; SCA aracı tam bağımlılık grafiğini (SBOM — Software Bill of Materials'a benzer bir envanter) çıkaramazsa kör nokta oluşur. Ayrıca "bilinen açık var" ile "bu açık benim kullanım şeklimde istismar edilebilir" farklı şeylerdir — bir kütüphanenin savunmasız fonksiyonu hiç çağrılmıyorsa risk teorik kalabilir, ama bunu otomatik olarak ayırt etmek zordur (buna "reachability analysis" denir ve gelişmiş SCA araçlarının bir kısmı bunu kısmen dener). Sürüm sabitleme (pinning) olmadan derlenen projelerde, bir bağımlılığın hangi tam sürümünün kullanıldığı build'den build'e değişebilir — bu, "dün geçti, bugün kaldı" tarzı tutarsız SCA sonuçlarının kök nedenidir.

### IaC Taraması (Infrastructure as Code Scanning): Altyapı tanımını denetleme

**Mekanizma:** Altyapı artık genellikle kod olarak tanımlanır (bulut kaynak tanım dosyaları, konteyner orkestrasyon manifestoları, altyapı şablonları). IaC tarayıcısı bu tanım dosyalarını, dağıtımdan *önce*, bilinen güvensiz konfigürasyon desenleri için statik olarak inceler: herkese açık bırakılmış depolama kovaları, aşırı geniş ağ erişim kuralları, şifrelenmemiş veri depoları, aşırı yetkili servis hesapları gibi.

**Neden ayrı bir disiplin:** SAST uygulama kodundaki mantık hatalarını bulur; IaC taraması *ortamın kendisinin* nasıl yapılandırıldığını denetler. Bir uygulama kusursuz yazılmış olabilir ama üzerinde çalıştığı altyapı yanlış yapılandırılmışsa (ör. veritabanı internete açık) sonuç aynı derecede vahim olabilir. Bulut ortamlarında yanlış konfigürasyon, en yaygın ihlal nedenlerinden biridir çünkü saldırı yüzeyi kod mantığından değil, bir tık yanlışlıkla açılan bir ayardan doğar.

**Kök neden mantığı:** IaC taraması da "shift left" ilkesinin bir uzantısıdır — yanlış yapılandırılmış bir kaynağı *dağıtılmadan önce*, tanım dosyası aşamasında yakalamak, o kaynak zaten canlıya çıktıktan ve olası bir sızıntıdan sonra düzeltmekten kıyaslanamayacak kadar ucuzdur. Ayrıca IaC taraması "configuration drift" (zamanla elle yapılan değişikliklerin kod ile ortam arasında sapma yaratması) sorununu da dolaylı olarak azaltır: eğer altyapı yalnızca kod üzerinden, taramadan geçerek değişiyorsa, elle yapılan denetim dışı değişikliklerin alanı daralır.

## Pipeline Yerleşimi: Sıralama Neden Önemli

Dört tarama türü pipeline'a rastgele değil, **maliyet ve geri bildirim hızına göre sıralı** yerleştirilir — tıpkı test piramidinde ucuz birim testlerinin pahalı E2E testlerinden önce gelmesi gibi:

1. **IaC taraması ve SAST**, kod push/pull-request anında, saniyeler-dakikalar içinde çalışır. Çalışan bir ortam gerektirmezler, en erken ve en ucuz kontrollerdir.
2. **SCA**, bağımlılıklar kurulur kurulmaz çalışabilir; genellikle build aşamasıyla birlikte veya hemen sonrasında yer alır.
3. **DAST**, yalnızca bir ortama dağıtım *sonrasında* mümkündür; bu yüzden pipeline'ın ilerisinde, genellikle test/staging ortamına dağıtımdan sonra veya ayrı, zamanlanmış (nightly/periodic) bir iş akışında çalışır.

Bu sıralamanın kök nedensel mantığı "fail fast"tir: ucuz ve hızlı kontrol bir sorunu daha derindeki pahalı kontrolden önce yakalarsa, geliştirici dakikalar içinde geri bildirim alır ve pahalı DAST/entegrasyon aşamasının kaynakları boşa harcanmaz.

## Kalite Kapıları ve Break-the-Build Eşikleri

Bir tarayıcıyı pipeline'a eklemek kolaydır; zor olan, onun sonucunu **ne zaman pipeline'ı durduracağına** (break-the-build) karar vermektir. Bu kararın kök nedensel gerekçesi, tarama sonuçlarının doğası gereği **ikili değil, dereceli** olmasıdır.

### Neden "her bulguda durdur" işe yaramaz

Bir tarayıcı, olgunlaşmamış bir kurulumda genellikle yüzlerce, hatta binlerce bulgu üretir; bunların büyük kısmı düşük önemde, teorik veya yanlış pozitiftir. Her bulguda pipeline'ı durdurmak iki felakete yol açar: birincisi geliştirme tamamen durur (hiçbir dağıtım geçemez); ikincisi ekip bu duruma tepki olarak taramayı devre dışı bırakır veya bulguları gözü kapalı "reddet/yoksay" (suppress) ile geçiştirir — ki bu, kontrolün varlığını anlamsızlaştırır. Bu, CI/CD dünyasındaki "flaky test'i görmezden gelme alışkanlığı" ile birebir aynı bozulma örüntüsüdür: aşırı gürültülü bir kontrol, zamanla saygısını kaybeder.

### Kademeli eşik tasarımı

Olgun bir kurulum, bulguyu **önem derecesi (severity)** ve **istismar edilebilirlik** eksenlerinde sınıflandırır ve eşiği buna göre ayarlar:

- **Kritik/Yüksek önem + doğrulanmış istismar edilebilirlik:** pipeline'ı durdurur (hard gate / break-the-build). Örnek: bir SCA bulgusu, üretimde kullanılan ve doğrudan erişilebilir bir fonksiyonda bilinen, aktif istismar edilen bir açık bildiriyorsa.
- **Orta önem:** genellikle pipeline'ı durdurmaz ama görünür bir uyarı üretir, bir takip bileti (ticket) açar ve bir SLA'ya (ör. "30 gün içinde düzelt") bağlanır.
- **Düşük önem / bilgilendirici:** raporlanır, dashboard'da izlenir, engellemez.

Bu kademelendirme aynı zamanda **zaman içinde sıkılaştırılabilir** olmalıdır: yeni bir tarayıcı ilk eklendiğinde mevcut kod tabanında birikmiş çok sayıda eski bulgu (backlog) bulunur; bunları anında "hard gate" yapmak pipeline'ı kilitler. Bunun yerine yaygın strateji, eşiği yalnızca **yeni eklenen kod** için sıkı tutmak ("yeni açık eklenemez") ve mevcut backlog'u ayrı, zamana yayılmış bir iyileştirme planına bağlamaktır. Bu, "yeni giren pisliği durdur, eski pisliği aşamalı temizle" mantığıdır — sıfırdan mükemmellik beklemek gerçekçi değildir ve gerçekçi olmayan bir eşik, ekibin eşiği tamamen görmezden gelmesine yol açar.

### Baseline ve bastırma (suppression) yönetimi tuzağı

Bulgunun "kabul edilebilir risk" olarak işaretlenip (suppress/ignore/false-positive olarak kapatılıp) bir daha hiç sorgulanmamak üzere bir baseline dosyasına gömülmesi, en yaygın pratik hatadır. Zamanla bu baseline dosyası, incelemesi kimsenin yapmadığı devasa bir "yoksayılanlar mezarlığına" dönüşür; içinde gerçekten geçerli olmayan bastırmalarla birlikte, koşullar değiştiği için artık geçerli olmayan (ör. "bu fonksiyon hiç çağrılmıyordu" denilen ama sonradan çağrılmaya başlanan) bastırmalar da birikir. En iyi pratik, her bastırmanın bir **gerekçe, sorumlu kişi ve son geçerlilik tarihi** taşımasıdır; süresi dolan bastırmalar otomatik olarak yeniden değerlendirmeye düşmelidir.

## Sonuç Triage Süreci

Tarama bittikten sonraki adım — bulguları kimin, hangi sırayla, hangi kriterle değerlendireceği — DevSecOps'un en az otomatikleştirilebilir ama en kritik parçasıdır.

### Neden triage bir süreç gerektirir, tek seferlik bir karar değil

Bir bulgu tek başına yeterli bağlam taşımaz. "SQL injection'a açık bir desen bulundu" bilgisi, o kodun gerçekten kullanıcı girdisi alıp almadığını, o uç noktanın kimlik doğrulama arkasında olup olmadığını, verinin hassasiyetini bilmeden risk açısından anlamlı değildir. Bu yüzden triage, bulguyu **iş bağlamına** oturtan bir insan (veya insan+araç iş birliği) sürecidir. Tipik bir triage akışı şu soruları sırayla cevaplar:

1. **Bu bulgu gerçek mi, yoksa yanlış pozitif mi?** (Taint analizinin izlediği veri yolu pratikte hiç tetiklenmiyor olabilir.)
2. **Gerçekse, istismar edilebilir mi?** (Açığın varlığı ile pratik istismar edilebilirlik farklı şeylerdir; bir açık teorik olarak var ama örneğin ağ erişimi zaten kısıtlıysa pratik risk düşüktür.)
3. **İstismar edilebilirse, etkisi ne olur?** (Veri sızıntısı mı, hizmet kesintisi mi, yetki yükseltme mi — etki, önceliklendirmeyi belirler.)
4. **Ne zaman düzeltilmeli?** (Kritik + istismar edilebilir + yüksek etki: hemen. Diğerleri: SLA'ya bağlı sıra.)

### Triage'i ölçeklendirme: neden salt manuel süreç çöker

Büyüyen bir kod tabanında günde yüzlerce yeni bulgu üretilebilir; bunların tamamını insan gözden geçirirse triage kendisi darboğaz haline gelir — tıpkı otomasyonsuz güvenlik denetiminin başta çözmeye çalıştığımız sorunu yeniden üretmesi gibi. Olgun kurulumlar bunu şöyle azaltır:

- **Deduplikasyon:** Aynı kök nedenden doğan yüzlerce bulguyu (ör. aynı güvensiz fonksiyonun 50 farklı çağrı noktası) tek bir "desen" olarak gruplayıp tek seferde değerlendirmek.
- **Bağlam zenginleştirme (auto-triage yardımcıları):** Bulgunun canlı ortamda gerçekten erişilebilir olup olmadığını otomatik kontrol eden ek analizler (reachability, çalışma zamanı doğrulaması) düşük öncelikli gürültüyü otomatik elemeye yardımcı olur.
- **Sahiplik yönlendirme:** Bulguyu, o kod parçasının sahibi olan takıma/kişiye otomatik yönlendirmek (ör. kod sahiplik haritasından); merkezi bir güvenlik ekibinin her bulguyu manuel dağıtması yerine.
- **Geri bildirim döngüsü:** Bir bulgu tekrar tekrar yanlış pozitif olarak işaretleniyorsa, bu bilginin tarayıcı kuralına geri beslenmesi (kural ayarı, bastırma listesi güncellemesi) — aksi halde aynı gürültü sonsuza dek tekrar üretilir.

### Kim karar verir: sorumluluk modeli

Sağlıklı bir DevSecOps kültüründe, triage kararının nihai sorumlusu genellikle **kodun sahibi olan geliştirme ekibidir**, güvenlik ekibi değil. Güvenlik ekibinin rolü, doğru araçları kurmak, eşikleri kalibre etmek, karmaşık/yüksek riskli vakalarda danışmanlık yapmak ve sistemik örüntüleri (tekrarlayan hata sınıfları) tespit etmektir — ama her tekil bulguyu kapatma kararını vermek değil. Bu ayrım net değilse, güvenlik ekibi yine darboğaz haline gelir ve DevSecOps'un "ölçeklenebilirlik" vaadi boşa çıkar.

## Yaygın Hatalar ve En İyi Pratikler

**Hata: Taramayı yalnızca "ekle ve unut" olarak kurmak.** Bir tarayıcıyı pipeline'a eklemek, kural setinin ve eşiklerin sürekli kalibre edilmesi gereken canlı bir süreç olduğunu unutturmamalıdır. Kalibre edilmemiş bir tarayıcı ya çok gürültülü olur (görmezden gelinir) ya da çok gevşek olur (gerçek riskleri kaçırır).

**Hata: Tüm tarama türlerinin aynı eşiği paylaşması.** SAST'ın yüksek yanlış pozitif oranı ile DAST'ın nispeten daha güvenilir (çalışan sistemde doğrulanmış) bulguları aynı "kritikse durdur" kuralına tabi tutulursa, ya SAST aşırı katı ya da DAST aşırı gevşek kalır. Her araç türü kendi güvenilirlik profiline göre ayrı eşiklenmelidir.

**Hata: Yalnızca dağıtım anında tarama, geliştirme sırasında değil.** Bulguyu geliştirici IDE'de veya commit anında görmesi ile üç gün sonra bir pipeline raporunda görmesi arasında büyük bağlamsal fark vardır. Mümkün olduğunca erken (shift left) geri bildirim, düzeltme maliyetini düşürür.

**En iyi pratik: SBOM benzeri envanter disiplini.** Hangi bağımlılığın, hangi sürümün, hangi üründe kullanıldığının güncel bir envanterini tutmak, yeni bir açık duyurulduğunda ("şu kütüphanenin şu sürümünde açık var") etkilenen sistemleri dakikalar içinde tespit etmeyi mümkün kılar; envanter yoksa bu, günler süren manuel bir arama haline gelir.

**En iyi pratik: Güvenlik bulgusunu geliştiricinin diline çevirmek.** Ham tarayıcı çıktısı (uzun bir CVE tanımlayıcı, soyut bir kural adı) genellikle eyleme geçirilemezdir. Bulguyu "bu dosyanın şu satırında, şu değişikliği yap" seviyesine indirgemek, düzeltme oranını belirgin şekilde artırır.

**En iyi pratik: Metrikleri düzeltme hızına göre izlemek, bulgu sayısına göre değil.** "Kaç bulgu var" yerine "ortalama bulgu kapatma süresi (mean time to remediate)" ve "kritik bulguların SLA içinde kapanma oranı" gibi metrikler, sürecin gerçekten işleyip işlemediğini gösterir. Ham bulgu sayısı yanıltıcıdır çünkü tarayıcı hassasiyeti (sensitivity) ayarlandıkça kolayca değişir.

## Özet

DevSecOps, güvenliği bir denetim aşamasından çıkarıp pipeline'ın yapısal bir parçası haline getirir; bunun kök nedensel gerekçesi, hatayı erken yakalamanın (shift left) ve otomasyonun ölçek sorununu çözmesinin ekonomik üstünlüğüdür. SAST, DAST, SCA ve IaC taraması farklı bilgi kaynaklarını (statik kod, çalışan sistem, üçüncü parti bağımlılık, altyapı tanımı) sorguladığı için birbirinin yerine değil, tamamlayıcısı olarak kullanılmalıdır ve pipeline'a maliyet/hız sırasına göre yerleştirilmelidir. Ancak bir tarayıcı kurmak işin kolay kısmıdır; asıl mühendislik zorluğu, kademeli break-the-build eşikleri tasarlamak ve bulguları gerçek iş bağlamına oturtan, ölçeklenebilir bir triage sürecini kurumsallaştırmaktır. Bu ikisi olmadan DevSecOps, ya geliştirmeyi durduran bir bürokrasiye ya da kimsenin dikkate almadığı, kendini aldatan bir "yeşil tik" tiyatrosuna dönüşür.
