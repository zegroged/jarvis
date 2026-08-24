# Tehdit İstihbaratı (Cyber Threat Intelligence — CTI)

## Tanım

Tehdit istihbaratı (Cyber Threat Intelligence, kısaca CTI), ham veriyi işleyip, düşmanın kim olduğunu, ne yaptığını, nasıl yaptığını ve muhtemelen bundan sonra ne yapacağını anlatan **karar destekleyici bilgiye** dönüştürme disiplinidir. Buradaki kritik kelime "karar destekleyici"dir. Bir IP adresi listesi, tek başına istihbarat değildir; sadece veridir. O IP'nin hangi tehdit aktörüne ait olduğu, hangi kampanyada kullanıldığı, hangi hedeflere yöneldiği ve sizin ortamınız için ne anlama geldiği eklendiğinde istihbarat hâline gelir.

CTI'yi diğer güvenlik disiplinlerinden ayıran şey, **düşman odaklı (adversary-centric)** olmasıdır. Zafiyet yönetimi "benim sistemimde hangi delikler var?" diye sorar; CTI ise "hangi düşman, hangi motivasyonla, benim hangi deliğimi, hangi araçla sömürmeye eğilimlidir?" diye sorar. Bu bakış açısı farkı, savunmayı reaktif olmaktan çıkarıp öngörülü (proactive) hâle getirir.

CTI genelde üç seviyeye ayrılır ve bu ayrım kavramsal bir süslemeden ibaret değildir; farklı tüketiciler farklı seviyeye ihtiyaç duyar:

- **Stratejik istihbarat:** Üst yönetim ve risk sahipleri içindir. Jeopolitik eğilimler, sektörünüzü hedef alan aktör grupları, uzun vadeli tehdit manzarası. "Fidye yazılımı grupları artık sağlık sektörüne yöneliyor, veri şifreleme yerine veri sızdırma (double extortion) ağırlık kazandı" gibi.
- **Operasyonel istihbarat:** SOC yöneticileri, incident response (olay müdahale) liderleri içindir. Belirli bir kampanyanın kimi, ne zaman, nasıl hedeflediği. Aktörün TTP'leri.
- **Taktiksel istihbarat:** SOC analistleri, güvenlik cihazları içindir. IOC'ler, imzalar, tespit kuralları. En kısa ömürlü ama en hızlı tüketilen seviye.

Bu makalenin odağı, bu üç seviyeyi birbirine bağlayan çekirdek kavramlardır: IOC/TTP ayrımı, kaynak değerlendirme, Diamond Model ve operasyonel kullanım.

## Kök Neden ve Çalışma Mantığı: Neden CTI Var?

CTI'nin varlık nedeni basit bir asimetriden doğar: **savunan taraf her yeri korumak zorundadır, saldıran taraf ise tek bir zayıf noktayı bulmak zorundadır.** Bu asimetri savunanın aleyhinedir. CTI bu dengesizliği kısmen düzeltmeye çalışır çünkü saldırganlar aslında düşünülenden çok daha fazla **tekrar eder**.

Bir saldırgan grup bir araç seti, bir altyapı kurulumu ve bir çalışma tarzı (modus operandi) geliştirdiğinde bunu her hedefte sıfırdan yeniden icat etmez. Aynı phishing şablonunu, aynı komut-kontrol (C2) çatısını, aynı yanal hareket (lateral movement) tekniğini tekrar kullanır. İşte CTI'nin ekonomisi buradan gelir: **düşmanın tekrarını yakalayabilirsem, onu bir hedefte gördüğümde başka hedeflerde de tanıyabilirim.**

Ancak burada temel bir gerçek vardır ki tüm modern CTI düşüncesini şekillendirir: **Bir düşmanın bazı özelliklerini değiştirmesi kolay, bazılarını değiştirmesi zordur.** Bir IP adresini değiştirmek dakikalar sürer. Bir domain almak birkaç dolar ve birkaç dakikadır. Bir hash, dosyanın tek bir byte'ı değişince tamamen başkalaşır. Ama bir saldırganın *çalışma tarzını* — hangi araçları sevdiğini, hangi teknikleri hangi sırayla kullandığını, hangi zaman diliminde çalıştığını — değiştirmesi hem maliyetli hem de operasyonel olarak zordur. Bu içgörü, "Acı Piramidi" (Pyramid of Pain) olarak bilinen kavramın temelidir ve IOC ile TTP arasındaki ayrımı anlamanın anahtarıdır.

## IOC ve TTP: İki Farklı Soyutlama Seviyesi

### IOC (Indicator of Compromise — İhlal Göstergesi)

IOC, bir saldırının ardında bıraktığı **gözlemlenebilir, atomik iz**lerdir. Bunlar teknik olguları temsil eder:

- Zararlı dosyaların hash değerleri (MD5, SHA-256)
- Zararlı IP adresleri ve domain'ler
- C2 sunucularının URL'leri
- Belirli registry anahtarları, dosya yolları, mutex isimleri
- Anormal kullanıcı-ajan (user-agent) string'leri

IOC'nin gücü de zayıflığı da aynı şeyden gelir: **belirginlik.** Bir SHA-256 hash'i ya eşleşir ya eşleşmez; yorum gerektirmez. Bu, otomasyon için mükemmeldir — bir firewall'a on binlerce IOC yükleyip makine hızında bloklama yapabilirsiniz. Ama tam da bu kesinlik onu kırılgan yapar. Saldırgan dosyada tek bir byte değiştirdiğinde hash değişir ve IOC'niz ölür. Yeni bir sunucu kiraladığında IP IOC'niz ölür.

İşte bu yüzden IOC'ler **kısa ömürlüdür ve düşük değerlidir** — Acı Piramidi'nin tabanında yer alırlar. Bir saldırganın hash'ini veya IP'sini blokladığınızda ona verdiğiniz "acı" minimaldir; birkaç dakika içinde etrafından dolaşır. IOC'ler değersiz demiyoruz; hızlı, otomatikleştirilebilir ve geçmiş ihlalleri tespit etmede (retrospective hunting) çok değerlidirler. Ama tek başlarına bir savunma stratejisi olamazlar.

### TTP (Tactics, Techniques, and Procedures — Taktikler, Teknikler ve Prosedürler)

TTP, IOC'den bir soyutlama seviyesi yukarıdadır. Saldırganın **davranışını** tanımlar:

- **Tactic (Taktik):** Saldırganın *neden* bir şey yaptığı — amacı. Örneğin "Persistence" (kalıcılık sağlama), "Privilege Escalation" (yetki yükseltme), "Exfiltration" (veri sızdırma). Bu, en üst seviye hedeftir.
- **Technique (Teknik):** Bu amaca *nasıl* ulaşıldığı. Örneğin kalıcılık için "Scheduled Task" (zamanlanmış görev) oluşturmak veya bir "Registry Run Key" eklemek.
- **Procedure (Prosedür):** Bu tekniğin *tam olarak nasıl* uygulandığı — belirli bir aktörün spesifik uygulaması. Aynı tekniği iki grup farklı komut parametreleriyle, farklı sırayla uygulayabilir; işte bu spesifik parmak izi prosedürdür.

TTP'lerin değeri, **değiştirilmelerinin pahalı olmasından** gelir. Bir saldırgan grubun "PowerShell ile bellek içinde (fileless) kod çalıştırıp, ardından WMI üzerinden yanal hareket etme" alışkanlığı varsa, bunu değiştirmek yeni araçlar geliştirmeyi, ekibi yeniden eğitmeyi ve test etmeyi gerektirir. Bu yüzden TTP'yi tespit eden bir savunma çok daha dayanıklıdır: aynı grup IP'sini, domain'ini, hash'ini değiştirse bile, TTP tespitiniz onu yeni kampanyada da yakalar.

Bunun operasyonel karşılığı **MITRE ATT&CK** çerçevesidir. ATT&CK, gerçek dünyada gözlemlenmiş saldırgan davranışlarını taktik-teknik matrisi hâlinde kataloglar. Bir tespiti "IP 1.2.3.4'ü blokla" yerine "ATT&CK T-numaralı tekniği ortamımda tespit edebiliyor muyum?" olarak düşünmek, savunmayı IOC seviyesinden TTP seviyesine yükseltir. Not: ATT&CK teknik numaraları belirli bir kodlama şemasına sahiptir; spesifik bir numarayı emin olmadan yazmaktansa tekniğin adını ve mantığını referans almak daha güvenlidir.

## İstihbarat Kaynakları ve Kaynak Değerlendirme

İstihbaratın değeri, kaynağının kalitesi kadardır. Kötü kaynaktan gelen istihbarat, hiç istihbarat olmamasından daha tehlikelidir çünkü yanlış bir güven hissi verir ve kaynakları yanlış yönlendirir.

Kaynaklar tipik olarak şöyle sınıflanır:

- **OSINT (Open Source Intelligence):** Açık kaynaklar — bloglar, güvenlik firmalarının raporları, sosyal medya, açık IOC beslemeleri (feed), sertifika şeffaflık (certificate transparency) logları. Ucuz ve bol, ama gürültülü ve doğrulanması gerekir.
- **Ticari beslemeler (Commercial feeds):** Ücretli, işlenmiş, bağlamlandırılmış istihbarat. Genelde daha güvenilir ve düşük yanlış-pozitif oranlıdır, ama pahalıdır ve sağlayıcıya bağımlılık yaratır.
- **Paylaşım toplulukları:** Sektörel ISAC/ISAO yapıları, güven temelli paylaşım grupları. Sektörünüze özgü, taze istihbarat için değerlidir.
- **Dâhili telemetri (en değerlisi):** Kendi ortamınızdan çıkan veri. Kendi SOC'nizin gördüğü saldırılar, kendi honeypot'larınız, kendi incident response bulgularınız. Bu, **sizin ortamınıza tam uygun** olduğu için en yüksek sinyal/gürültü oranına sahiptir.

### Kaynağı Değerlendirmenin Kök Mantığı

Ham bir IOC beslemesini körü körüne firewall'a yüklemek klasik bir hatadır. Neden? Çünkü kaynak değerlendirmesi yapılmamıştır. İstihbarat topluluğu, kaynağı değerlendirmek için iki eksenli bir yaklaşım kullanır (askeri istihbarattan miras kalan bir mantık):

1. **Kaynağın güvenilirliği:** Bu sağlayıcı geçmişte ne kadar doğruydu? Kanıtlanmış bir geçmişi var mı, yoksa deneme aşamasında mı?
2. **Bilginin doğruluğu:** Bu spesifik bilgi başka kaynaklarca teyit ediliyor mu (corroboration)? Mantıklı mı? Tek kaynağa mı dayanıyor?

Bu iki eksen bağımsızdır. Genelde güvenilir bir kaynak, tek seferlik doğrulanmamış bir bilgi verebilir; ya da yeni bir kaynak, birden çok yerden teyit edilen bir bilgi verebilir. Kritik nokta: **Bir bilgiyi tek kaynağa dayanarak aksiyona dökmeyin; mümkünse en az iki bağımsız kaynaktan teyit (corroboration) arayın.**

Ayrıca **tazelik (recency)** ve **güven paylaşım işareti (TLP — Traffic Light Protocol)** de kritiktir. TLP, bir istihbaratın kiminle paylaşılabileceğini renk koduyla belirtir (kırmızıdan yeşile doğru artan paylaşım serbestisi). Bir istihbaratı yanlış kişiyle paylaşmak, kaynağın güvenini yakar ve gelecekteki paylaşımları keser — CTI'de itibar, para kadar değerlidir.

## Diamond Model: Saldırıyı Yapılandırılmış Anlamak

İstihbarat analistlerinin en çok kullandığı analitik çerçevelerden biri **Diamond Model** (Elmas Modeli)'dir. Neden gereklidir? Çünkü bir saldırı olayına baktığınızda kolayca "ağaçların içinde kaybolabilirsiniz" — yüzlerce log satırı, onlarca IOC. Diamond Model, her saldırgan olayını (event) **dört köşesi olan bir yapıya** oturtarak analize disiplin getirir:

1. **Adversary (Düşman):** Saldırıyı yürüten aktör. Kimliği başta bilinmese bile bir köşe olarak yer tutar.
2. **Capability (Yetenek):** Kullanılan araç ve teknikler — zararlı yazılım, exploit, TTP'ler.
3. **Infrastructure (Altyapı):** Saldırının fiziksel/mantıksal altyapısı — C2 sunucuları, domain'ler, IP'ler, e-posta hesapları.
4. **Victim (Kurban):** Hedef — kişi, kurum, varlık, ya da hedeflenen zafiyet.

Bu dört köşe, kenarlarla birbirine bağlıdır ve modelin asıl gücü de buradadır: **bir köşeyi bildiğinizde, kenarlar üzerinden diğerlerini keşfetmeye (pivot) çalışırsınız.**

### Pivoting: Diamond Model'in Operasyonel Kalbi

Diamond Model'i güçlü yapan tek şey diyagramı değil, "pivot" edebilme yeteneğidir. Bir örnek üzerinden düşünelim:

Diyelim ki bir zararlı dosya (Capability) yakaladınız. Bu dosyayı analiz ederek gömülü bir C2 domain'i (Infrastructure) buldunuz. O domain'in WHOIS ve pasif DNS geçmişine bakarak (Infrastructure ekseninde pivot) aynı e-postayla kaydedilmiş beş domain daha buldunuz. Bu beş domain'in geçmiş çözümlemelerine bakarak (pivot) daha önce hiç görmediğiniz üç zararlı örneği (yeni Capability) keşfettiniz. Bu örneklerin hedeflediği kurumlara bakarak (Victim ekseni) saldırganın belirli bir sektöre odaklandığını gördünüz. Ve tüm bu altyapı örtüşmesi, olayı bilinen bir tehdit grubuyla (Adversary) ilişkilendirmenizi sağladı.

Tek bir dosyadan başlayıp, kenarlar üzerinden pivot ederek bütün bir kampanyayı ortaya çıkardınız. **İşte istihbarat üretimi budur:** izole olayları birbirine bağlayıp örüntü (pattern) çıkarmak. Diamond Model bu düşünme sürecine yapı verir, böylece analistler sezgiye değil sistematik bir yönteme dayanır.

Diamond Model ayrıca **Kill Chain** (Cyber Kill Chain) ile birlikte kullanıldığında güçlenir. Kill Chain saldırının *zaman içinde* nasıl ilerlediğini (keşif, silahlandırma, teslimat, sömürü, kurulum, C2, hedefe yönelik eylemler) fazlar hâlinde tanımlar. Diamond Model her fazdaki olayı yapılandırır; ikisi birleşince hem "ne oldu" hem "hangi sırayla oldu" resmi çıkar.

## Sömürü/İstismar Mantığı ile Savunma: İki Taraflı Bakış

CTI, doğası gereği hem saldırgan hem savunan tarafın zihnini modellemeyi gerektirir. Bu ayrımı bir örnek üzerinden somutlaştıralım.

### Saldırganın İstismar Mantığı (Neden CTI'yi Saldırgan da Kullanır?)

CTI tek yönlü değildir. Olgun saldırgan grupları da istihbarat toplar ve bunu savunmanızı aşmak için kullanır:

- **Savunma kaçınma (defense evasion):** Saldırgan, hedefin hangi EDR/AV ürününü kullandığını keşfeder (bu bir istihbarat faaliyetidir) ve o ürünün tespit ettiği bilinen TTP'lerden kaçınacak şekilde araçlarını uyarlar.
- **IOC eskitme:** Saldırgan, altyapısının "yanmış" (bilinen IOC listelerine düşmüş) olduğunu tespit ederse — kendi domain'lerini tehdit istihbarat platformlarında arayarak bunu yapabilir — hemen yeni altyapıya geçer. Yani sizin IOC beslemenizin varlığı, saldırganın davranışını değiştirir.
- **Besleme zehirleme (feed poisoning):** Gelişmiş saldırganlar, açık istihbarat beslemelerine kasıtlı yanlış IOC enjekte etmeye çalışabilir; amaç savunanın meşru altyapıyı bloklamasına yol açıp yanlış-pozitif gürültüsü yaratmak ve analistleri yormaktır.

Bu istismar mantığını **bilmek**, savunmanın ön koşuludur. Saldırganın sizin istihbaratınızı okuduğunu varsaymak gerekir.

### Savunma Tarafı

Aynı örüntüleri savunma için kullanmanın yolu:

- **TTP-öncelikli tespit:** IOC'leri bloklamayı bırakmayın ama üstüne davranışsal tespit kurun. "Bu hash'i blokla" yerine "hangi süreç, hangi ebeveyn süreçten spawn edildi ve ne yaptı?" sorusuna yanıt veren tespitler yazın. Böylece saldırgan IOC'sini değiştirdiğinde bile TTP tespitiniz ayakta kalır.
- **İstihbaratı avlamaya (threat hunting) dönüştürme:** Gelen istihbaratı sadece bloklama listesine değil, geriye dönük ava dönüştürün. "Bu yeni TTP'yi öğrendik; son 90 günün loglarında bu davranış var mıydı?" sorusu, henüz alarm üretmemiş bir ihlali ortaya çıkarabilir.
- **Kendi altyapınızı izleme:** Kendi domain'lerinizi ve markanızı istihbarat platformlarında izleyerek, saldırganın sizi hedeflemek için kayıt ettiği benzer (typosquatting) domain'leri erkenden yakalayabilirsiniz.

## Operasyonel Kullanım: İstihbaratı Aksiyona Dökmek

İstihbarat, tüketilmediği sürece maliyet kalemidir. Operasyonelleştirmenin temel prensibi: **her istihbarat parçası bir tüketiciye ve bir eyleme bağlanmalıdır.** Bunun için ihtiyaçtan başlanır.

Bu döngü genelde **istihbarat çevrimi (intelligence cycle)** olarak adlandırılır ve mantıksal olarak şu adımlardan oluşur: yönlendirme/ihtiyaç belirleme (hangi soruları cevaplamam gerekiyor?), toplama, işleme, analiz, yayma (dissemination) ve geri bildirim. Kritik olan, döngünün **ihtiyaçla başlamasıdır** — "hangi IOC'leri toplayabilirim?" değil, "karar vericilerin hangi sorusunu cevaplamam gerekiyor?" Bu, PIR (Priority Intelligence Requirements — Öncelikli İstihbarat İhtiyaçları) olarak formüle edilir.

Operasyonel entegrasyonun somut biçimleri:

- **TIP (Threat Intelligence Platform):** İstihbaratı toplayan, normalize eden, tekilleştiren ve dağıtan merkezî platform. Farklı beslemeleri ortak bir formata (örneğin STIX gibi yapılandırılmış bir standart) çevirip birbirine bağlar.
- **Otomatik dağıtım:** Yüksek güvenli IOC'ler otomatik olarak firewall/EDR'a; düşük güvenli olanlar önce analist onayından geçecek şekilde. Her IOC'nin bir **güven skoru** ve **son kullanma tarihi** olmalıdır.
- **SIEM/SOAR entegrasyonu:** Gelen bir alarm, otomatik olarak istihbaratla zenginleştirilir (enrichment). "Bu IP alarm üretti" yerine analist, "bu IP şu aktöre ait, şu kampanyada görüldü, güven skoru yüksek" bağlamıyla karşılaşır. Bu, triyaj süresini dramatik biçimde kısaltır.
- **Atıf (attribution) dikkati:** Bir saldırıyı belirli bir gruba atfetmek çekicidir ama tehlikelidir. Atıf, teknik bulguların ötesinde jeopolitik/istihbari bağlam gerektirir ve yanlış atıf ciddi sonuçlar doğurur. Operasyonel savunma için genelde atıf **gerekli değildir** — TTP'yi tespit edip durdurmak için grubun adını bilmeniz şart değildir. Atıfı, gerçekten gerektiğinde ve yüksek kanıt eşiğiyle yapın.

## Yaygın Hatalar

- **IOC'yi istihbarat sanmak:** En yaygın hata. Bağlamsız IOC listeleri istihbarat değil ham veridir. "10.000 IOC'lik beslemem var" övünülecek bir şey değildir; kaçının doğrulandığı, kaçının hâlâ taze olduğu ve kaçının sizin ortamınızla alakalı olduğu önemlidir.
- **Son kullanma tarihi olmayan IOC'ler:** IOC'ler eskir. Bir zamanlar zararlı olan bir IP, altı ay sonra meşru bir bulut sunucusuna atanmış olabilir. Son kullanma / yeniden değerlendirme mekanizması olmayan bir bloklama listesi, zamanla yanlış-pozitif üretip meşru trafiği keser.
- **İhtiyaçtan değil, veriden başlamak:** "Elimde bu istihbarat var, ne yapabilirim?" diye başlamak, tükettiği kaynağa değmeyen raporlar üretir. Önce PIR belirlenir, sonra toplama yapılır.
- **Kaynak çeşitliliğini teyit sanmak:** Beş farklı besleme aynı orijinal kaynağı tekrarlıyorsa, bu beş bağımsız teyit değildir; tek bir kaynağın beş kopyasıdır. Gerçek teyit, bağımsız gözlemlerden gelir.
- **Atıfa takılıp savunmayı unutmak:** "Bu hangi APT grubu?" sorusu ilginçtir ama saldırı devam ederken enerjiyi yanlış yere harcar. Önce durdur, sonra merak et.
- **İstihbaratı SOC'a "atıp" geri bildirim almamak:** Yayılan istihbaratın işe yarayıp yaramadığı ölçülmezse döngü kapanmaz ve istihbarat programı zamanla alakasızlaşır.
- **Saldırganın da CTI okuduğunu unutmak:** Kendi IOC'lerinizi ve yöntemlerinizi fazla açık paylaşmak, saldırgana savunmanızı gösterir.

## En İyi Pratikler

- **Acı Piramidi'nde yukarı tırmanın:** Hash/IP tespitleriyle yetinmeyin; araç, ağ/host artifact'ları ve nihayet TTP seviyesinde tespit kabiliyeti geliştirin. TTP'yi yakaladığınızda saldırgana gerçek maliyet yüklersiniz.
- **Dâhili telemetriyi baş tacı yapın:** En değerli istihbarat, kendi ortamınızdan çıkandır. Kendi incident response bulgularınızı yapılandırıp tekrar kullanılabilir istihbarata dönüştürün.
- **Her IOC'ye metadata iliştirin:** Kaynak, güven skoru, ilk görülme, son görülme, son kullanma, ilgili kampanya/TTP. Metadata olmayan IOC yönetilemez.
- **PIR ile hizalanın:** İstihbarat programını, kurumun gerçek risklerini yansıtan öncelikli sorulara bağlayın. Sektörünüzü, varlıklarınızı ve tehdit manzaranızı yansıtsın.
- **Diamond Model ve Kill Chain'i birlikte kullanın:** Olayları yapılandırmak (Diamond) ve zaman ekseninde konumlandırmak (Kill Chain) için ikisini bir arada işletin; pivot fırsatlarını sistematik arayın.
- **İstihbaratı ölçün:** Kaç ihlali erken yakaladı, triyaj süresini ne kadar kısalttı, kaç yanlış-pozitif üretti? Ölçülmeyen istihbarat programı savunulamaz.
- **Paylaşımı iki yönlü yapın:** İstihbarat topluluğu karşılıklıdır. Sadece almak değil, TLP kurallarına uyarak vermek de, uzun vadede aldığınız istihbaratın kalitesini yükseltir.
- **Otomasyon ile insan yargısını dengeleyin:** Yüksek güvenli, atomik IOC'leri otomasyona bırakın; bağlam ve atıf gerektiren analizleri insana bırakın. Otomasyon hızı, insan derinliği sağlar.

## Özet

Tehdit istihbaratı, ham veriyi düşman odaklı karar destekleyici bilgiye çevirme disiplinidir. Çekirdeği, **IOC (kırılgan, atomik, kısa ömürlü göstergeler) ile TTP (dayanıklı, davranışsal örüntüler) arasındaki ayrımı** anlamaktan geçer — savunmayı IOC bloklamadan TTP tespitine yükseltmek, saldırgana gerçek maliyet yükler. Kaynaklar titizlikle değerlendirilmeli, tek kaynağa güvenilmemeli ve her istihbarat bir tazelik ve güven skoruyla yönetilmelidir. Diamond Model, olayları dört köşeli bir yapıya oturtup pivot ederek izole olaylardan bütün kampanyaları ortaya çıkarmayı sağlar. Ve nihayetinde istihbarat, ihtiyaçtan (PIR) başlayıp aksiyona ve geri bildirime bağlanan bir çevrim olarak operasyonelleştirilmediği sürece sadece bir maliyet kalemidir. Unutulmaması gereken temel gerçek: saldırgan da istihbarat toplar; savunma, düşmanın sizin istihbaratınızı okuduğu varsayımıyla tasarlanmalıdır.
