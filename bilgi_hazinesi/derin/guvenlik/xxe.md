# XML External Entity (XXE) — Derin Dalış

Bu metin XXE'yi bir "kategori adı" olmaktan çıkarıp, ayrıştırıcının belleğinde tam olarak ne olduğunu, hangi satırın neden patladığını ve savunmanın neden çoğu zaman yanlış yerden kurulduğunu gösteren uygulamalı bir incelemedir. Özet makale mekanizmayı ve savunma ilkelerini kavramsal olarak veriyordu; burada asıl işi yapıyoruz: gerçek kod yazıyoruz, kırıyoruz, düzeltiyoruz; gerçek CVE'lerle sahaya demirliyoruz; savunma seçeneklerinin takaslarını tartışıyoruz ve geliştiricilerin defalarca düştüğü tuzakları tek tek çıkarıyoruz.

---

## 1. Çözümlü yürüyüş

Somut bir senaryo seçelim: bir kurumsal uygulamanın kullanıcı profillerini XML formatında içe aktaran (import) bir uç noktası. Frontend bir XML dosyası yüklüyor, backend bunu ayrıştırıp veritabanına yazıyor. Bu, sahada gördüğünüz en klasik XXE giriş noktalarından biridir; çünkü "dosya import" özelliği neredeyse her zaman güvenilmeyen girdiyi tam ayrıştırma ile karşılar.

### 1.1 Zafiyetli kod (Java / JAXP)

Aşağıdaki Spring tarzı bir servlet uç noktası düşünün. Kod işlevsel olarak tamamen doğrudur, kod incelemesinden (code review) sorunsuz geçer, testleri yeşildir:

```java
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.NodeList;
import java.io.InputStream;

public class ProfilImportServisi {

    public String kullaniciAdiCek(InputStream xmlGirdi) throws Exception {
        // KLASIK ZAFIYETLI YAPILANDIRMA
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        // Hiçbir güvenlik özelliği ayarlanmadı — varsayılanlar aktif.

        DocumentBuilder builder = factory.newDocumentBuilder();
        Document doc = builder.parse(xmlGirdi);

        NodeList isimler = doc.getElementsByTagName("isim");
        StringBuilder sonuc = new StringBuilder();
        for (int i = 0; i < isimler.getLength(); i++) {
            // Ayrıştırılan içerik doğrudan yanıta yansıyor.
            sonuc.append(isimler.item(i).getTextContent());
        }
        return sonuc.toString();
    }
}
```

Beklenen normal girdi:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kullanicilar>
  <kullanici><isim>Mehmet</isim></kullanici>
  <kullanici><isim>Ayşe</isim></kullanici>
</kullanicilar>
```

Bu girdiyle servis "MehmetAyşe" döndürür. Sorun yok gibi görünüyor.

### 1.2 Sorun nasıl ortaya çıkıyor (kavramsal)

Kritik satır şudur: `DocumentBuilderFactory.newInstance()`. Bu fabrika, JAXP referans implementasyonunda **DTD işlemeyi ve dış varlık (external entity) çözümlemesini varsayılan olarak açık** getirir. Yani `builder.parse()` çağrısı, gelen XML'in içinde bir `<!DOCTYPE>` bloğu ve `<!ENTITY ... SYSTEM ...>` tanımı varsa, bu tanımı sadece okumakla kalmaz — ayrıştırma sırasında **çözer**: işaret edilen URI'yi açar, içeriğini okur ve varlık referansının geçtiği yere gömer.

Saldırgan normal `<isim>Mehmet</isim>` yerine şunu gönderir:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE kullanicilar [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<kullanicilar>
  <kullanici><isim>&xxe;</isim></kullanici>
</kullanicilar>
```

Ayrıştırıcının içinde olan biten adım adım şudur:

1. `<!DOCTYPE>` görülür, DTD işleme başlar (varsayılan açık).
2. `<!ENTITY xxe SYSTEM "file:///etc/passwd">` tanımı belleğe alınır: "xxe adlı varlığın içeriği bu dosyadır."
3. Gövdede `&xxe;` referansına gelindiğinde ayrıştırıcı dosyayı açar, `/etc/passwd` içeriğini okur, `&xxe;` yerine yerleştirir.
4. `getTextContent()` artık `Mehmet` yerine `/etc/passwd` içeriğinin tamamını döndürür.
5. Servis bunu yanıta yansıtır. Saldırgan sunucudaki parola dosyasının içeriğini görür.

Burada **iki hata birleşmiştir**: (a) ayrıştırıcı güvenilmeyen girdi için sertleştirilmemiştir, (b) ayrıştırma çıktısı kontrolsüzce geri yansıtılmaktadır. İkisi bir araya gelince "in-band file disclosure" olur. Yansıma olmasa bile — birazdan göreceğimiz gibi — kör (blind) XXE ile veri yine sızabilir; yani asıl kök neden (a)'dır.

Dikkat çekici nokta: kodun hiçbir yerinde "dosya oku" diyen bir satır yok. Dosya okuma yeteneğini geliştirici değil, **ayrıştırıcının varsayılanı** getiriyor. XXE'yi bu kadar sinsi yapan da budur.

### 1.3 Düzeltilmiş kod (Java / JAXP)

Doğru savunma, ayrıştırma yapmadan önce fabrikayı sertleştirmektir. En sağlam hamle DTD'yi tümüyle yasaklamaktır; çünkü DTD hiç işlenmezse dış varlık da, parametre varlığı da, entity expansion (billion laughs) da imkânsızlaşır — üç saldırı sınıfı tek satırla kapanır:

```java
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.NodeList;
import java.io.InputStream;

public class ProfilImportServisi {

    public String kullaniciAdiCek(InputStream xmlGirdi) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

        // 1) EN GÜÇLÜ HAMLE: DOCTYPE/DTD'yi tamamen yasakla.
        // DTD işlenmezse dış varlık, parametre varlık ve billion laughs birden kapanır.
        factory.setFeature(
            "http://apache.org/xml/features/disallow-doctype-decl", true);

        // 2) Kuşak-kuşak savunma: DTD bir şekilde işlenirse diye
        //    dış genel ve dış parametre varlıklarını da kapat.
        factory.setFeature(
            "http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature(
            "http://xml.org/sax/features/external-parameter-entities", false);

        // 3) Dış DTD (external subset) yüklemesini kapat.
        factory.setFeature(
            "http://apache.org/xml/features/nonvalidating/load-external-dtd", false);

        // 4) XInclude ve entity referans genişletmesini kapat.
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);

        // 5) JAXP güvenli işleme bayrağı.
        factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);

        DocumentBuilder builder = factory.newDocumentBuilder();
        Document doc = builder.parse(xmlGirdi);

        NodeList isimler = doc.getElementsByTagName("isim");
        StringBuilder sonuc = new StringBuilder();
        for (int i = 0; i < isimler.getLength(); i++) {
            sonuc.append(isimler.item(i).getTextContent());
        }
        return sonuc.toString();
    }
}
```

Artık aynı saldırı payload'u gönderildiğinde `disallow-doctype-decl=true` olduğu için ayrıştırıcı `<!DOCTYPE>` gördüğü anda bir `SAXParseException` fırlatır ("DOCTYPE is disallowed"). Dosya hiç açılmaz. Normal (DOCTYPE'suz) girdiler ise sorunsuz işlenmeye devam eder.

Neden tek `disallow-doctype-decl` yeterken 2–5 arası bayrakları da koyuyoruz? Çünkü bazı meşru uygulamalar DTD'yi tümden kapatamaz (aşağıda takasları tartışacağız). O durumda katmanlı bayraklar devreye girer. `disallow-doctype-decl=true` koyabiliyorsanız tek başına yeterlidir; diğerleri "kemer + askı" güvencesidir ve zarar vermez.

### 1.4 Aynı hata Python'da (kısa karşı-örnek)

Aynı yürüyüşün Python `lxml` versiyonu, savunmanın neden dile göre farklı ama ilkenin aynı olduğunu gösterir:

```python
# ZAFIYETLI: lxml varsayılanları dış varlığı çözer ve ağ erişimine izin verir
from lxml import etree

def kullanici_adi_cek(xml_bytes: bytes) -> str:
    root = etree.fromstring(xml_bytes)   # sertleştirilmemiş
    return "".join(e.text or "" for e in root.iter("isim"))
```

```python
# DÜZELTİLMİŞ: DTD yükleme kapalı, varlık çözümleme kapalı, ağ kapalı
from lxml import etree

def kullanici_adi_cek(xml_bytes: bytes) -> str:
    parser = etree.XMLParser(
        resolve_entities=False,   # &xxe; çözülmez
        no_network=True,          # SYSTEM "http://..." engellenir
        load_dtd=False,           # dış DTD yüklenmez
        dtd_validation=False,
        huge_tree=False,          # aşırı genişleme koruması
    )
    root = etree.fromstring(xml_bytes, parser=parser)
    return "".join(e.text or "" for e in root.iter("isim"))
```

Daha da güvenlisi, projeye `defusedxml` ekleyip standart ayrıştırıcıları onun sertleştirilmiş sarmalayıcılarıyla değiştirmektir; `defusedxml` DTD, dış varlık ve entity bombalarını varsayılan olarak reddeder. İlke her iki dilde de aynıdır: **güvenilmeyen XML için DTD/dış-varlık/ağ erişimini kapat.**

---

## 2. Gerçek dünya (CVE ile)

XXE'nin "yeni ve egzotik" bir şey olmadığını, tersine yirmi yılı aşkın süredir aynı kök nedenden tekrar tekrar patladığını görmek için verilen gerçek kayıtlara bakalım.

### CVE-2008-0628 — "Bayrağı kapattım sandım" hatasının ders kitabı örneği

Bu kayıt, XXE savunmasının en ince tuzağını tam kalbinden vurur. Kayıt der ki: Sun Java Runtime Environment (JDK/JRE 6 Update 3 ve öncesi) içindeki XML ayrıştırma kodu, **"external general entities" özelliği `false` olarak ayarlanmış olsa bile dış varlık referanslarını işliyordu.** Sonuç: uzaktaki saldırganlar XXE saldırısı yaparak servis dışı bırakma (DoS) tetikleyebiliyor veya kısıtlı kaynaklara erişebiliyordu.

Buradaki ders paha biçilmezdir ve doğrudan Bölüm 1.3'teki tasarım tercihimizi haklı çıkarır: **tek bir bayrağa güvenmek kırılgandır.** Geliştirici doğru bayrağı ayarlamış olsa bile, ayrıştırıcının o sürümündeki bir hata yüzünden savunma sessizce devre dışı kalabiliyordu. İşte bu yüzden modern öneri "önce mümkünse DTD'yi tümden yasakla, sonra genel + parametre varlıklarını + dış DTD yüklemesini ayrı ayrı kapat, üstüne SECURE_PROCESSING ekle" şeklinde katmanlıdır. CVE-2008-0628, "bir bayrak yeterli" varsayımının platform seviyesinde bile çökebildiğinin somut kanıtıdır. Ayrıca bu, yalnızca uygulama kodunun değil, alttaki runtime'ın da güncel tutulması gerektiğini gösterir; savunma bir kez yazılıp unutulacak bir şey değildir.

### CVE-2009-1699 — Tarayıcıda `file:///etc/passwd`, ders kitabı payload'u sahada

Bu kayıt, Bölüm 1.2'de yazdığımız kavramsal payload'un gerçek dünyada birebir görülmüş halidir. Apple Safari'nin (4.0 öncesi; iPhone OS 1.0–2.2.1) WebKit içindeki XSL stylesheet implementasyonu dış varlıkları düzgün işlemiyordu ve kayıt açıkça şunu söylüyor: saldırgan **`file:///etc/passwd` URL'sini bir varlık tanımına gömerek** hazırlanmış bir DTD üzerinden keyfi dosya okuyabiliyordu — "XXE attack" olarak nitelenmiş.

Bu kayıt iki önemli noktayı sahaya demirler. Birincisi, XXE yalnızca sunucu tarafı bir SOAP/REST servisi meselesi değildir; **XML işleyen her bileşen** — burada bir web tarayıcısının XSLT motoru — hedeftir. XSLT dönüşümleri de altta bir XML ayrıştırıcısı kullandığı için aynı dış-varlık tuzağını taşır. İkincisi, en meşhur payload olan `file:///etc/passwd` bir efsane değil, gerçek bir istismar vektörüdür; bir dosyanın varlığını/içeriğini doğrulamak saldırganın ilk hamlesidir. Savunma açısından çıkarım: XSLT/`Transformer` kullanan kod yollarını da (yalnızca DOM/SAX'ı değil) sertleştirmek gerekir — Java'da `TransformerFactory` üzerinde `ACCESS_EXTERNAL_DTD` ve `ACCESS_EXTERNAL_STYLESHEET`'i boş dizgeye çekmek gibi.

### CVE-2005-1306 — "Sadece dosya var mı" bilgisi bile zafiyettir

Adobe Reader/Acrobat 7.0–7.0.1'deki bu kayıt, XML script içeren JavaScript aracılığıyla saldırganın **dosyaların varlığını tespit edebilmesini** sağlıyordu; kayıt bunu doğrudan "XML External Entity vulnerability" diye adlandırıyor. Buradaki incelik şudur: saldırgan dosyanın *içeriğini* göremese bile, sadece "bu dosya var mı, yok mu" (varlık/yokluk, ya da hata mesajının farklılaşması) bilgisi bile bir sızıntıdır. Bu, **kör (blind) XXE'nin** en zayıf ama yine de tehlikeli formudur — bir yan kanal (side channel). Ayrıştırma sonucu hiç yansımasa bile, dosya bulununca ile bulunamayınca oluşan davranış farkı (zamanlama, hata metni, başarı/başarısızlık) saldırgana bilgi taşır. Bu yüzden "yanıt geri dönmüyor, güvendeyim" yanılgısı yanlıştır; CVE-2005-1306 tam olarak bu yanılgının çürütülmesidir.

### Yan not: "XXE" her yerde aynı XXE değildir

Verilen listede CVE-2005-3194, CVE-2005-3262, CVE-2005-3284, CVE-2005-3317 gibi kayıtlar da "XXE" kısaltmasını içerir — ancak dikkatli okununca bunlar **XXE dosya formatı** (UUE'nin bir akrabası olan, sıkıştırma/kodlama arşiv formatı) ile ilgilidir; ALZip, WinRAR, AhnLab V3, ZipGenius gibi araçlardaki buffer overflow / format string zafiyetleridir, XML External Entity ile ilgisi yoktur. Bunu özellikle belirtiyorum çünkü aynı üç harfin iki tamamen farklı anlamı vardır ve bir güvenlik uzmanının bunları karıştırmaması gerekir. Bu metnin konusu olan XML External Entity için sahaya demirlediğimiz gerçek kayıtlar CVE-2008-0628, CVE-2009-1699, CVE-2005-1306 ve tarihsel köken olarak CVE-2002-1252'dir.

### CVE-2002-1252 — Kökeni: SOAP/HTTP POST ile dosya okuma

En eski kayıt olan CVE-2002-1252, PeopleSoft ürünlerinde kullanılan PeopleTools Application Messaging Gateway'de, bir HTTP POST isteğindeki belirli XXE alanları aracılığıyla `SimpleFileHandler` üzerinden **keyfi dosya okumaya** izin veriyordu. Bu kayıt, XXE'nin daha 2002'de kurumsal mesajlaşma/entegrasyon katmanlarında (yani bugün "SOAP/XML API" dediğimiz şeyin atası) görüldüğünü gösterir. Örüntü tanıdık: güvenilmeyen bir HTTP POST gövdesi, XML olarak ayrıştırılıyor, ayrıştırıcı dış varlığı çözüyor, dosya içeriği dışarı sızıyor. Yirmi yılda saldırı yüzeyi (SVG, DOCX, SAML, cloud metadata) genişledi ama kök neden hiç değişmedi: **güvenilmeyen XML + varsayılan açık DTD/dış-varlık işleme.**

---

## 3. Karşılaştırma / karar

Savunmada birden fazla yol vardır ve hepsi her senaryoya uymaz. İşte seçenekler ve takasları.

### Seçenek A — DTD'yi tümden yasakla (`disallow-doctype-decl` / eşdeğeri)

**Ne zaman:** Uygulamanız güvenilmeyen XML alıyorsa ve DTD'ye meşru bir ihtiyacınız yoksa (vakaların ezici çoğunluğu). Bu, altın standarttır.

**Neden:** DTD hiç işlenmediği için dış varlık, parametre varlık ve entity expansion (billion laughs) saldırılarının **tamamı** tek hamlede imkânsızlaşır. Kör XXE de, in-band file disclosure da, DoS da kapanır. Savunma yüzeyi minimuma iner; yanlış yapılandırma ihtimali azalır.

**Takas:** DTD'ye gerçekten ihtiyaç duyan (dahili varlık tanımları, doctype tabanlı doğrulama isteyen) eski entegrasyonlar kırılır. Ama pratikte "güvenilmeyen kullanıcıdan gelen XML'in DTD'ye ihtiyacı olması" çok nadirdir; genelde bu bir kokudur (smell), gereksinim değil.

### Seçenek B — DTD açık, ama dış varlıkları kapat (üçlü bayrak)

**Ne zaman:** DTD'yi tümden yasaklayamıyorsanız (örneğin dahili varlıklara meşru ihtiyaç var, ama dış kaynak erişimi istemiyorsunuz).

**Neden:** Dış genel varlık + dış parametre varlık + dış DTD yüklemesinin üçünü birden kapatarak dosya okuma ve SSRF'i engellersiniz.

**Takas:** Bu, A'dan daha kırılgandır. Üç bayraktan birini unutmak kapıyı açık bırakır (özellikle parametre varlıklarını unutmak blind XXE'ye kapı açar). Ayrıca CVE-2008-0628'in gösterdiği gibi, bir bayrak platform hatası yüzünden sessizce çalışmayabilir. Billion laughs için ayrıca entity genişleme limiti gerekir; A'da bu bedava gelirdi. Yani B daha fazla bakım yükü, daha fazla hata payı demektir.

### Seçenek C — Sertleştirilmiş kütüphane kullan (`defusedxml` vb.)

**Ne zaman:** Python gibi, güvenli sarmalayıcıların hazır olduğu ekosistemlerde; ekibin bayrak ezberlemesini istemiyorsanız.

**Neden:** Güvenli varsayılanlar kod düzeyinde garanti altına alınır; geliştiricinin her çağrı noktasında doğru bayrağı hatırlaması gerekmez. İnsan hatası riskini büyük ölçüde eler.

**Takas:** Bir bağımlılık daha eklenir ve güncel tutulması gerekir. Ayrıca ekip "kütüphane halleder" diye rahatlayıp diğer XML giriş noktalarını (SVG, Office, üçüncü parti kütüphaneler) gözden kaçırabilir. Kapsam disiplini gerektirir.

### Seçenek D — Girdi filtreleme (`<!DOCTYPE` karalisteleme)

**Ne zaman:** Asla birincil savunma olarak değil. Yalnızca ikincil, defense-in-depth katmanı olarak.

**Neden (neden yetmez):** Karaliste XXE'de neredeyse her zaman atlatılır — UTF-16/UTF-7 kodlama hileleri, boşluk/yorum varyasyonları, farklı byte order mark'lar filtreyi delip geçer. Karaliste "güvenlik hissi" verir ama gerçek güvenlik vermez; asıl işi parser hardening yapmalıdır.

**Takas:** Yanlış güven duygusu en tehlikeli takastır. Filtreyi birincil savunma sanan ekip, ayrıştırıcıyı hiç sertleştirmez ve ilk kodlama hilesinde düşer.

### Seçenek E — Formatı değiştir (XML yerine JSON)

**Ne zaman:** Yeni tasarımda ve XML'e gerçek bir bağımlılık yoksa.

**Neden:** JSON'da entity ve dış varlık kavramı yoktur; bu saldırı sınıfı yapısal olarak elenir.

**Takas:** Mevcut SOAP/SAML/Office/SVG ekosistemleri XML'i zorunlu kılar; her yerde değiştiremezsiniz. Ayrıca JSON'un da kendi ayrıştırıcı riskleri (derin iç içe geçme DoS'u vb.) vardır. "XML kötü, JSON iyi" değil; "gereksiz yere XML kullanma" doğru okumadır.

### Karar özeti

Pratik karar ağacı basittir: **Güvenilmeyen XML mi işliyorsun? → Evet → DTD'ye meşru ihtiyacın var mı? → Hayır (çoğu durum) → Seçenek A.** Evetse → Seçenek B + entity limitleri, ve tercihen C ile destekle. D'yi yalnızca üstüne serp, asla tek başına güvenme. E'yi yeni tasarımlarda düşün. XSLT/`Transformer` kullanıyorsan bunların dış-kaynak erişimini de ayrıca kapatmayı unutma (CVE-2009-1699 dersi).

---

## 4. Hata-modu kataloğu

Sahada geliştiricilerin ve savunmacıların XXE'de tekrar tekrar yaptığı tipik hatalar:

1. **Tek bayrağa güvenmek.** Yalnızca `external-general-entities=false` koyup "hallettim" sanmak. CVE-2008-0628'in kanıtladığı gibi tek bayrak platform hatasıyla bile devre dışı kalabilir; ayrıca parametre varlıklarını açık bırakır. Katmanlı sertleştirme şarttır.

2. **Parametre varlıklarını unutmak.** Genel varlıkları (`&x;`) kapatıp parametre varlıklarını (`%x;`) açık bırakmak. Blind/OOB XXE tam olarak parametre varlıkları üzerinden dış DTD ile veri sızdırır; bu boşluk en sık istismar edilen yerdir.

3. **Karaliste ile `<!DOCTYPE` filtrelemek.** Payload'da string aramak. UTF-16/UTF-7 kodlaması, BOM oyunları, boşluk ve yorum varyasyonlarıyla atlatılır. Filtre birincil savunma sanılırsa ayrıştırıcı hiç sertleştirilmez ve ilk hilede düşülür.

4. **Bir uç noktayı düzeltip diğerlerini unutmak.** Aynı kod tabanında XML çoğu zaman birden çok yerde ayrıştırılır: SOAP servisi, dosya import, konfigürasyon okuma, üçüncü parti kütüphane içi. Birini sertleştirip diğerini unutmak tüm çabayı boşa çıkarır; XXE en zayıf halkadan girer.

5. **Gizli XML'i gözden kaçırmak.** SVG resimleri, DOCX/XLSX (ZIP içindeki XML), SAML mesajları, RSS/Atom beslemeleri hep XML'dir. "Ben XML almıyorum, sadece resim yüklemesi var" demek yanıltıcıdır; bir SVG avatar yükleme özelliği pekâlâ XXE giriş noktasıdır.

6. **XSLT/Transformer yolunu unutmak.** DOM/SAX'ı sertleştirip `TransformerFactory` / XSLT dönüşümlerini es geçmek. CVE-2009-1699'un gösterdiği gibi XSLT motoru da alttan XML ayrıştırır ve `file:///` ile dosya okuyabilir. `ACCESS_EXTERNAL_DTD` ve `ACCESS_EXTERNAL_STYLESHEET` boş dizgeye çekilmelidir.

7. **"Yanıt yansımıyor, güvendeyim" yanılgısı.** In-band yansıma olmadığında rahatlamak. Blind XXE OOB kanalıyla (dış DTD + parametre varlık) veriyi saldırganın sunucusuna sızdırır; CVE-2005-1306'daki gibi sadece "dosya var mı" bilgisi bile bir yan kanal sızıntısıdır.

8. **SSRF boyutunu görmezden gelmek.** `SYSTEM "file://..."` savunulur ama `SYSTEM "http://169.254.169.254/..."` düşünülmez. XXE, güvenlik duvarının içinden çıkan bir SSRF köprüsüdür; bulut metadata servisinden IAM kimlik bilgisi çalınabilir. Yalnızca dosya değil, tüm dış kaynak erişimi kapatılmalıdır.

9. **Billion laughs'ı boyut limitiyle çözmeye çalışmak.** Girdi birkaç yüz byte'tır; tehlike ham boyutta değil, genişleme oranındadır. Boyut sınırı entity bombasını durdurmaz; entity genişleme sayısı/derinliği limiti veya (en iyisi) DTD'yi tümden kapatmak gerekir.

10. **Eski runtime/kütüphaneyle yaşamak.** Uygulama kodunu sertleştirip alttaki JRE/libxml/parser'ı güncellememek. Güvenli varsayılanlar sürümle gelir; CVE-2008-0628 bizzat runtime seviyesinde bir hataydı. "Bir kez yapılandır, unut" değil; güncellemede tekrar doğrula.

11. **İmza doğrulamadan önce ayrıştırmak (SAML).** SAML akışında XML imzası kontrol edilmeden önce belge ayrıştırılırsa, imza hiç devreye girmeden XXE tetiklenir. Bu pre-auth (kimlik doğrulaması gerektirmeyen) bir saldırı yüzeyi olduğu için özellikle kritiktir.

12. **Güvenli sarmalayıcıya güvenip kapsamı daraltmak.** `defusedxml` gibi bir kütüphane eklenince "artık tüm XXE bitti" sanmak. Kütüphane yalnızca onunla ayrıştırılan yolları korur; ekipteki başka bir kişinin doğrudan `lxml`/`etree` çağırdığı unutulan bir yol açık kalır. Kapsam envanteri disiplinini gevşetmek yaygın bir tuzaktır.

---

## Kapanış

XXE, adı "gelişmiş" çağrışım yapsa da kökeni tek ve basittir: XML standardının güçlü bir özelliği olan dış varlık çözümlemesinin, güvenilmeyen girdi için varsayılan olarak açık gelmesi. Bölüm 1'de bunun kodda nasıl sessizce yaşadığını (hiçbir "dosya oku" satırı olmadan dosya okuyan bir ayrıştırıcı) ve düzeltmenin ayrıştırma öncesi birkaç bayrağa indiğini gördük. Bölüm 2'de CVE-2002-1252'den CVE-2009-1699'a kadar yirmi yıllık bir örüntünün hep aynı kök nedeni tekrarladığını, CVE-2008-0628'in ise "tek bayrak yeter" varsayımını platform seviyesinde çürüttüğünü gördük. Bölüm 3'te savunma seçeneklerinin takaslarını tarttık; altın kural, mümkünse DTD'yi tümden kapatmaktır. Bölüm 4'te ise bu ilkeyi boşa çıkaran on iki tipik hatayı çıkardık.

Sahada akılda tutulacak tek cümle şudur: **Güvenilmeyen XML işleyen her ayrıştırıcıda, ayrıştırmadan önce DTD ve dış varlık işlemesini kapat — ve bunu her giriş noktasında, her dilde, her güncellemede tekrar doğrula.** Saldırının mekanizmasını anlayan, savunmayı doğru yerden kurar.
