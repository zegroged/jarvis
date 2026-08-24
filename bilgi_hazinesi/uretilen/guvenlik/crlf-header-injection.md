# CRLF ve HTTP Header Injection

## Tanım

CRLF injection, bir saldırganın kullanıcı kontrolündeki bir veriyi, satır sonu karakterleri olan **CR** (Carriage Return, `\r`, `0x0D`) ve **LF** (Line Feed, `\n`, `0x0A`) ile birlikte bir protokol akışına sızdırabilmesidir. Bu iki karakterin ardışık birleşimi olan `\r\n` (CRLF), metin tabanlı birçok internet protokolünde -en başta HTTP, ama aynı zamanda SMTP, IMAP, LDAP ve Redis gibi protokollerde- **satır sınırı** anlamına gelir. Yani bir satırın nerede bitip diğerinin nerede başladığını belirleyen ayraçtır.

**HTTP Header Injection**, CRLF injection'ın HTTP başlıklarına (header) uygulanmış özel halidir. Bir uygulama, kullanıcıdan gelen bir değeri temizlemeden bir HTTP yanıt (response) başlığına yazdığında, saldırgan araya `\r\n` sokarak kendi başlıklarını, hatta tamamen kendi yanıt gövdesini enjekte edebilir. Bu tekniğin en yıkıcı formu **HTTP Response Splitting**'tir: tek bir yanıtı iki ayrı yanıta "bölmek".

Bu makale üç eksende ilerliyor: response splitting'in nasıl çalıştığı ve neden mümkün olduğu, log injection'ın daha sinsi ama sık gözden kaçan boyutu, ve her ikisine karşı katmanlı savunma.

## Kök Neden: Neden Böyle Oluyor?

Sorunun temeli, HTTP/1.x'in **metin tabanlı ve satır yönelimli** bir protokol olmasında yatar. Bir HTTP yanıtı şuna benzer:

```
HTTP/1.1 200 OK\r\n
Content-Type: text/html\r\n
Set-Cookie: session=abc123\r\n
\r\n
<html>...gövde...</html>
```

Burada dikkat edilmesi gereken kritik nokta şudur: başlıkların her biri `\r\n` ile ayrılır ve **başlık bölümünün sona erdiğini, gövdenin başladığını gösteren şey boş bir satırdır** -yani art arda gelen iki CRLF (`\r\n\r\n`). Protokolde başlığın "adı" ile "değeri" arasında hiçbir uzunluk alanı, hiçbir tip güvenliği, hiçbir kaçış (escaping) mekanizması yoktur. Ayraç tamamen konumsaldır: `\r\n` gördüğün yerde bir satır biter.

İşte kök neden tam burası. Eğer bir uygulama şöyle bir kod yazarsa:

```
location = "/page?lang=" + kullanici_dili
response.setHeader("Location", location)
```

ve `kullanici_dili` değeri doğrudan URL parametresinden geliyorsa, saldırgan bu parametreye `\r\n` içeren bir değer koyduğunda, uygulama bunu masumca `Location` başlığına yazar. Ama HTTP istemcisi (tarayıcı) veya arada duran proxy, o `\r\n`'yi gördüğünde "Location başlığı burada bitti, yeni bir başlık başlıyor" diye yorumlar. Uygulama bir **değer** yazdığını sanır; protokol katmanı ise bir **yapı** okur. Bu anlam uçurumu, injection'ın özüdür.

Bu, aslında SQL injection veya command injection ile aynı ailedendir: **veri ve kontrol düzleminin karışması** (data/control plane confusion). Uygulama veriyi kod/yapı olarak yorumlanabilecek bir bağlama, o bağlamın özel karakterlerini kaçışlamadan koyar.

## Somut Örnek: Response Splitting Anatomisi

Diyelim ki bir uygulama, `redirect` parametresine göre bir yönlendirme başlığı üretiyor:

```
GET /git?redirect=/anasayfa HTTP/1.1
```

Normalde yanıt:

```
HTTP/1.1 302 Found\r\n
Location: /anasayfa\r\n
\r\n
```

Şimdi saldırgan `redirect` parametresine URL-encode edilmiş bir yük gönderir. `%0d` = CR, `%0a` = LF:

```
/anasayfa%0d%0aSet-Cookie:%20oturum=saldirgan%0d%0a%0d%0a<html>sahte%20sayfa</html>
```

Uygulama bunu decode edip Location değerine yazınca ortaya çıkan ham yanıt şu hale gelir:

```
HTTP/1.1 302 Found\r\n
Location: /anasayfa\r\n
Set-Cookie: oturum=saldirgan\r\n
\r\n
<html>sahte sayfa</html>\r\n
```

Saldırgan artık:
- Kendi `Set-Cookie` başlığını enjekte etti (**session fixation** saldırısına kapı açar -kurbanın oturumunu saldırganın belirlediği bir kimliğe sabitler).
- `\r\n\r\n` ile başlık bölümünü kapatıp **kendi gövdesini** enjekte etti.

Bu neden tehlikeli? Çünkü tek bir istekle kurbana, meşru domain üzerinden servis edilen sahte bir sayfa gösterilebilir. Bu, güçlü bir **XSS** vektörüne ve **web cache poisoning**'e dönüşebilir: eğer araya giren bir cache/proxy bu bölünmüş yanıtı yakalayıp iki ayrı yanıt olarak yorumlar ve ikinci "yanıtı" başka bir URL için önbelleğe alırsa, o cache'i kullanan tüm kullanıcılara saldırganın içeriği servis edilir. Bu, klasik **HTTP Request Smuggling**'in yakın akrabası olan **response splitting tabanlı cache poisoning**'dir.

## Sömürü Mantığı: Saldırgan Ne Kazanır?

CRLF injection tek başına bir amaç değil, bir **primitive**tir -üzerine başka saldırılar inşa edilen bir yapı taşı. Saldırganın elde edebileceği somut kazanımlar:

**Set-Cookie enjeksiyonu ile session fixation.** Saldırgan kurbanın tarayıcısına bilinen bir oturum çerezi yazdırır; kurban giriş yapınca saldırgan aynı çerezle oturuma sızar.

**Response splitting ile reflected XSS / defacement.** Başlık bölümünü kapatıp gövde enjekte ederek, hedef domain'in güvenlik bağlamında (same-origin) JavaScript çalıştırır. Bu, normalde CSP veya output encoding ile kapatılmış XSS yollarını atlatabilir çünkü zafiyet gövde üretiminden önce, protokol katmanında ortaya çıkar.

**Cache poisoning.** Yukarıda anlatıldığı gibi, araya giren cache'lerin yanlış yorumlamasından yararlanarak zehirli içeriği kalıcı hale getirir ve etkiyi tek kurbandan tüm kullanıcılara yayar.

**Güvenlik başlıklarının bastırılması veya taklidi.** Saldırgan `Content-Security-Policy`, `X-Frame-Options` gibi koruyucu başlıkların yerine kendi zayıf sürümlerini enjekte edebilir, ya da `Content-Length` ile oynayarak yanıt sınırlarını bulanıklaştırabilir.

**Open redirect ve phishing zinciri.** Location manipülasyonu, güvenilen domain üzerinden dış sitelere yönlendirme yapılmasını sağlar.

Sömürünün pratikteki tetikleyicisi neredeyse her zaman şudur: **kullanıcı girdisinin bir yanıt başlığına yansıtıldığı bir yer.** Aday noktalar -Location (redirect), Set-Cookie (dil/tema tercihi çerezi), özel `X-` başlıkları, `Content-Disposition` (dosya adı), ve `Refresh` başlıkları. Girdi kaynağı ise URL parametreleri, form alanları, hatta `Host` ya da `Referer` gibi diğer istek başlıkları olabilir.

## Log Injection: Sinsi ve Sık Gözden Kaçan Boyut

Response splitting görünür ve dramatiktir; **log injection** ise sessizdir ama savunma açısından en az onun kadar önemlidir. Buradaki fikir şudur: uygulamalar, gelen istekleri, kullanıcı adlarını, hata mesajlarını düz metin log dosyalarına yazar. Log dosyaları da -tıpkı HTTP gibi- **satır yönelimlidir**: her satır bir olaydır. Eğer log'a yazılan bir değer kullanıcı kontrolündeyse ve `\r\n` içeriyorsa, saldırgan **sahte log satırları** enjekte edebilir.

Bir örnek. Uygulama başarısız giriş denemelerini şöyle logluyor:

```
2026-07-05 14:00:01 UYARI Basarisiz giris: kullanici=<girdi>
```

Saldırgan kullanıcı adı olarak şunu gönderirse (satır sonları gerçek CRLF olarak):

```
admin
2026-07-05 14:00:02 BILGI Basarili giris: kullanici=admin ip=10.0.0.5
```

Log'a şu düşer:

```
2026-07-05 14:00:01 UYARI Basarisiz giris: kullanici=admin
2026-07-05 14:00:02 BILGI Basarili giris: kullanici=admin ip=10.0.0.5
```

Sonuç: log'a **hiç yaşanmamış başarılı bir giriş** kaydı düşer. Bunun etkileri katmanlıdır:

**Adli izlerin kirletilmesi (log forging).** Bir olay incelemesinde analistin gördüğü log artık güvenilmezdir; saldırgan izlerini gizleyebilir veya masum bir kullanıcıyı suçlu gibi gösterebilir.

**Log tabanlı savunmaların kandırılması.** SIEM sistemleri, IDS kuralları ve alarm mekanizmaları log satırlarını ayrıştırır. Enjekte edilen sahte satırlar yanlış alarmlar üretebilir veya gerçek saldırıyı gürültüyle boğabilir.

**İkincil injection.** Eğer log'lar sonradan bir web arayüzünde (örneğin bir admin log görüntüleyicisinde) HTML olarak render ediliyorsa, log'a enjekte edilen `<script>` etiketi **stored XSS**'e dönüşür. Aynı şekilde log'lar bir ELK/Splunk pipeline'ında işleniyorsa, format karakterleri o ayrıştırıcıyı da bozabilir.

Log injection'ın kök nedeni response splitting ile birebir aynıdır: satır yönelimli bir metin formatına, satır ayracını kaçışlamadan kullanıcı verisi yazmak.

## Savunma: Katmanlı Yaklaşım

Tek bir savunma yeterli değildir; derinlemesine savunma (defense in depth) gerekir. Katmanları önem sırasıyla ele alalım.

### 1. Modern protokol yapıları ve framework'lere güven (en güçlü savunma)

En sağlam savunma, sorunu ortadan kaldıran mimaridir. **HTTP/2 ve HTTP/3 binary (ikili) protokollerdir**; başlıklar metin satırları olarak değil, uzunluğu belli çerçeveler (frame) halinde taşınır. Bu, satır ayracı belirsizliğini kökten kaldırır -bir başlık değerinin içindeki `\r\n` artık "yeni başlık" anlamına gelmez, sadece iki bayttır. Bu yüzden HTTP/2+ üzerinde klasik response splitting büyük ölçüde uygulanamaz hale gelir (ancak downgrade veya HTTP/1.1'e çeviren gateway'ler varsa risk geri gelebilir).

Aynı şekilde, **modern web framework'leri ve HTTP kütüphaneleri, başlık değerlerine yazılan CR/LF karakterlerini artık reddeder.** Örneğin çağdaş Java, Python, Node.js ve .NET HTTP API'leri, bir başlık değerine kontrol karakteri koymaya çalıştığınızda hata fırlatır. Dolayısıyla en iyi savunma çoğu zaman **başlıkları elle string birleştirerek üretmemek**, bunun yerine framework'ün sağladığı güvenli `setHeader`/`addHeader` API'lerini kullanmaktır. (Not: burada belirli sürüm numaraları veriyorsam bunlar örnek amaçlıdır; kendi yığınınızın güncel dokümantasyonundan doğrulayın -bu davranış zamanla katılaştırılmıştır.)

### 2. Girdi doğrulama ve CR/LF temizliği (input validation)

Uygulama kodunda, kullanıcıdan gelip bir başlığa ya da log'a gidebilecek her değeri savunun. Buradaki prensip **allowlist (izin listesi)** olmalıdır: değerin sadece beklenen karakterleri içerdiğini doğrulayın (örneğin dil kodu için sadece `[a-z]{2}`), gerisini reddedin. Bu, `\r`, `\n` dahil tüm sürprizleri kapatır.

Allowlist mümkün değilse, en azından **CR ve LF karakterlerini (ve genel olarak `0x00`-`0x1F` aralığındaki tüm kontrol karakterlerini) tespit edip reddedin veya kaldırın.** Kritik incelik: sadece `\r\n` çiftini aramak yetmez; tek başına `\r` veya tek başına `\n` de bazı ayrıştırıcılar tarafından satır sonu sayılabilir. Bu yüzden her ikisini de bağımsız olarak filtreleyin.

Bir tuzağa dikkat: **filtreleme decode'dan sonra yapılmalıdır.** Saldırgan `%0d%0a` veya çift-encode edilmiş (`%250d`) formlar kullanabilir. Eğer sadece ham `\r\n` ararsanız ama uygulama sonradan decode ediyorsa, bypass edilirsiniz. Doğrulamayı, değerin gerçekten başlığa/log'a yazılacağı son forma en yakın noktada yapın.

### 3. Log'a özgü savunmalar

Log injection için ek olarak:

- **Yapısal (structured) loglama kullanın.** Düz metin satırları yerine JSON gibi bir formatla loglarsanız, kullanıcı verisi bir alanın **değeri** olur ve o değer JSON-encode edilir -içindeki `\n` otomatik olarak `\\n` kaçışına dönüşür ve satır yapısını bozamaz. Bu, log injection'a karşı en temiz mimari çözümdür.
- Loglama kütüphanesinin **kontrol karakterlerini kaçışlayan** bir yapılandırmasını kullanın (birçok modern loglama framework'ünde CR/LF sınırlama davranışı sonradan varsayılan hale gelmiştir; kendi sürümünüzde açık olduğunu doğrulayın).
- Log'ları **görüntüleyen arayüzde de** output encoding uygulayın; log'a hangi kirlilik girmiş olursa olsun, HTML bağlamında güvenli render edin. Bu, log kaynaklı stored XSS'i kapatır.

### 4. Çıktı kodlaması ve bağlama uygun kaçış

Response splitting'e karşı, başlık değerlerini bir başlık bağlamına yazarken -eğer framework yapmıyorsa- CR/LF'yi kodlayın veya kaldırın. Ancak vurgulamak gerekir: **bağlama uygun kodlama tek başına yeterli bir strateji değildir**, çünkü hangi kodlamanın doğru olduğu ayrıştırıcıya bağlıdır. Bu yüzden filtreleme + güvenli API + modern protokol birlikte kullanılmalıdır.

## Yaygın Hatalar

**"Sadece `\r\n` çiftini filtrelemek yeterli" yanılgısı.** Tek başına `\r` veya `\n` de tehlikelidir. Ayrıca `\r\n` çiftini silen ama `\n\r` veya çift-kodlanmış varyantları kaçıran filtreler bypass edilir.

**Decode sırasını yanlış kurmak.** Filtreyi decode'dan önce çalıştırmak klasik hatadır; saldırgan encode ederek geçer, uygulama sonradan decode eder ve zafiyet açılır.

**Denylist'e (yasak liste) güvenmek.** "Şu kötü karakterleri sil" yaklaşımı kırılgandır. Allowlist -"sadece şu iyi karakterlere izin ver"- her zaman daha sağlamdır.

**Başlıkları elle string birleştirerek üretmek.** `"Location: " + deger` gibi manuel başlık inşası, framework'ün güvenlik kontrollerini atlar. Güvenli API'leri kullanın.

**Log'ları güvenli veri sanmak.** Geliştiriciler log'ları "sadece bizim gördüğümüz iç veri" olarak görür ve temizlemez. Oysa log'lar hem adli değere sahiptir hem de sıklıkla web arayüzlerinde/SIEM'de ikincil olarak ayrıştırılır.

**Reverse proxy / CDN katmanını unutmak.** Uygulama HTTP/2 konuşuyor olsa bile, arada HTTP/1.1'e çeviren bir katman varsa response splitting/smuggling riski geri gelir. Zincirin tamamını değerlendirin.

**Host ve Referer başlıklarını "güvenli girdi" saymak.** Bunlar da kullanıcı kontrolündedir. Bir değeri başka bir istek başlığından alıp yanıt başlığına yazmak da injection'a açıktır.

## En İyi Pratikler (Özet)

- **Framework'ün güvenli başlık API'lerini kullanın**; başlıkları asla ham string birleştirmeyle üretmeyin.
- **Mümkünse HTTP/2+** kullanın ve zincirdeki tüm gateway/proxy'lerin de güvenli davrandığını doğrulayın.
- Kullanıcıdan başlığa/log'a giden her değeri **allowlist** ile doğrulayın; olmuyorsa tüm kontrol karakterlerini (`0x00`-`0x1F`, en başta CR ve LF) reddedin.
- Filtrelemeyi **decode sonrası**, değerin nihai formunda yapın; çift-kodlamayı hesaba katın.
- **Yapısal (JSON) loglama** benimseyin; kullanıcı verisini kaçışlanan bir alan değeri olarak yazın.
- Log görüntüleyici arayüzlerde **output encoding** uygulayın.
- Redirect'lerde `Location` değerini **allowlist'lenmiş iç yollarla** sınırlayın; open redirect'i de birlikte kapatın.
- Güvenlik başlıklarını (CSP, X-Frame-Options) **sunucu tarafında sabit** olarak ayarlayın ki enjeksiyonla bastırılamasınlar.
- CI/CD içinde **DAST/SAST** ile CRLF injection senaryolarını düzenli tarayın; regresyon testlerine `%0d%0a` yüklerini ekleyin.

## Kapanış

CRLF ve HTTP header injection, özünde tek bir mimari zaafın iki yüzüdür: **satır yönelimli metin protokollerinde, kullanıcı verisini yapı ayracından ayıramamak.** Response splitting bu zaafın gürültülü, log injection ise sessiz sonucudur. Modern binary protokoller ve katılaştırılmış framework'ler bu sınıfın büyük kısmını mimari olarak kapatmıştır -ama elle başlık üreten kod, eski protokol katmanları, decode sırası hataları ve "log'lar güvenlidir" varsayımı bu zafiyeti hâlâ canlı tutar. Sağlam savunma; güvenli API'ler, allowlist doğrulama, yapısal loglama ve zincirin tamamını (proxy/CDN dahil) kapsayan bir bakışın birleşimidir.
