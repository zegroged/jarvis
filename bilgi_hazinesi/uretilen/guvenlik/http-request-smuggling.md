# HTTP Request Smuggling (HTTP İstek Kaçakçılığı)

## Tanım

**HTTP Request Smuggling** (istek kaçakçılığı), bir HTTP isteğinin sınırlarının nerede bittiği konusunda zincir üzerindeki iki sunucunun farklı karar vermesinden doğan bir saldırı sınıfıdır. Modern web mimarilerinde bir istemci ile arka uç uygulama sunucusu (back-end) arasında genellikle bir **reverse proxy**, **load balancer** veya **CDN** gibi bir ön uç bileşen (front-end) bulunur. Bu iki bileşen aynı TCP bağlantısı üzerinden gelen bayt akışını okur; fakat isteğin nerede bitip yeni isteğin nerede başladığını belirlerken **farklı yorumlama kuralları** uygularsa, saldırgan araya "gizli" bir istek sıkıştırabilir. Ön uç bu baytları bir isteğin parçası sanarken, arka uç onları ayrı ve kendi başına bir istek olarak görür.

Bu uyumsuzluğun teknik adı **desync** (de-senkronizasyon) yani iki sunucunun istek akışı hakkındaki ortak anlayışının bozulmasıdır. Saldırının çekirdeği tek bir cümleyle özetlenebilir: **bir isteğin uzunluğunu iki farklı yöntemle ölçüp iki farklı cevaba varmak.**

## Kök Neden: HTTP Bir İsteğin Uzunluğunu Nasıl Belirler?

Saldırıyı anlamak için HTTP/1.1 protokolünün bir isteğin gövde (body) uzunluğunu nasıl belirlediğini bilmek gerekir. Protokolde iki temel mekanizma vardır:

1. **`Content-Length` (CL) başlığı:** Gövdenin kaç byte olduğunu doğrudan sayı olarak bildirir. Sunucu tam olarak o kadar byte okur ve isteği orada sonlandırır.
2. **`Transfer-Encoding: chunked` (TE) başlığı:** Gövde, her biri kendi uzunluğunu onaltılık (hex) olarak baştan bildiren "chunk"lar halinde gönderilir. Akış, uzunluğu `0` olan bir chunk ile (yani `0\r\n\r\n` dizisiyle) biter.

İşte problemin kökü tam burada başlar: **Bir istekte hem `Content-Length` hem de `Transfer-Encoding` başlığı aynı anda bulunursa ne olur?**

HTTP/1.1 standardı (RFC 7230 ve onun yerini alan RFC 9112) bu konuda nettir: **eğer `Transfer-Encoding: chunked` mevcutsa, `Content-Length` yok sayılmalıdır.** Standart ayrıca ikisinin birlikte gelmesini şüpheli/tehlikeli sayar ve proxy'lerin böyle istekleri reddetmesini önerir. Ancak asıl mesele şudur: standart bunu tavsiye eder, fakat sahadaki her yazılım bunu aynı şekilde ve aynı titizlikle uygulamaz. Bir sunucu CL'yi, diğeri TE'yi baz alırsa desync doğar.

Neden bu tutarsızlık var? Çünkü:

- HTTP/1.1 metin tabanlı, "insan okuyabilir" bir protokoldür ve bu esneklik, başlıkların ayrıştırılmasında (parsing) çok sayıda uç durum (edge case) yaratır: fazladan boşluklar, sekme karakterleri, büyük/küçük harf farkları, satır sonu (line ending) varyasyonları.
- Ön uç ve arka uç genellikle **farklı yazılımlar, farklı üreticiler, farklı sürümlerdir** (örneğin bir tarafta Nginx, diğer tarafta bir Java uygulama sunucusu). Her biri belirsizlikleri kendi geleneğiyle çözer.
- Performans için sunucular çoğunlukla **keep-alive** ve **bağlantı yeniden kullanımı** (connection reuse) yapar. Aynı TCP bağlantısı arka arkaya birçok istek taşır. Bu, kaçakçılığın işe yaramasının ön koşuludur: kaçırılan (smuggled) baytların bir sonraki isteğin başına eklenebilmesi için bağlantının açık kalması gerekir.

Özetle kök neden **protokolün bünyesindeki ayrıştırma belirsizliği** ile **heterojen zincir mimarisinin** birleşmesidir.

## İki Klasik Varyant: CL.TE ve TE.CL

Adlandırma mantığı basittir: birinci kısaltma **ön ucun** (front-end) hangi başlığı dikkate aldığını, ikinci kısaltma **arka ucun** (back-end) hangisini dikkate aldığını gösterir.

### CL.TE

Ön uç `Content-Length` başlığını temel alır, arka uç ise `Transfer-Encoding: chunked` başlığını temel alır.

Kavramsal bir örnek:

```
POST / HTTP/1.1
Host: hedef-site.com
Content-Length: 13
Transfer-Encoding: chunked

0

SMUGGLED
```

Burada ne oluyor?

- **Ön uç**, `Content-Length: 13` der ve gövdenin tamamının 13 byte olduğunu varsayar; `0\r\n\r\nSMUGGLED` bloğunun hepsini tek isteğin gövdesi sayıp arka uca iletir.
- **Arka uç**, `Transfer-Encoding: chunked` der ve gövdeyi chunk'lara göre okur. İlk chunk uzunluğu `0` olduğu için isteği hemen orada bitirir. Geriye kalan `SMUGGLED` baytlarını **bir sonraki isteğin başlangıcı** olarak yorumlar ve bağlantıda bekletir.

Sonuç: `SMUGGLED` dizisi, o bağlantıyı sonra kullanan **başka bir kullanıcının isteğinin önüne** yapışır. Saldırgan bu baytları `GET /admin ...` gibi tam bir istek satırıyla doldurursa, sonraki kurbanın isteği kısmen saldırganın kontrolündeki bir isteğe dönüşür.

### TE.CL

Bu, tam tersidir: ön uç `Transfer-Encoding: chunked`, arka uç `Content-Length` temel alır.

Kavramsal bir örnek:

```
POST / HTTP/1.1
Host: hedef-site.com
Content-Length: 3
Transfer-Encoding: chunked

8
SMUGGLED
0

```

Burada:

- **Ön uç** chunked okur: `8` uzunluğundaki chunk'ı (`SMUGGLED`) okur, ardından `0` chunk'ı görüp isteğin bittiğine karar verir ve tümünü arka uca iletir.
- **Arka uç** `Content-Length: 3` der ve gövdenin sadece ilk 3 byte'ını (`8\r\n` civarı) okur, geri kalanı bir sonraki isteğin başı sayar. Böylece `SMUGGLED` ve devamı arka uçta bekleyen "kaçak" istek olur.

Not: Gerçek exploit'lerde chunk uzunlukları ve `Content-Length` değerleri byte byte hesaplanır; `\r\n` (CRLF) karakterlerinin sayımı kritiktir. Bir byte hatası saldırıyı tamamen bozar. Yukarıdaki değerler mekanizmayı göstermek içindir, birebir çalışan payload değildir.

### TE.TE — Başlık Gizleme (Obfuscation)

Üçüncü bir sınıf da vardır: **her iki sunucu da `Transfer-Encoding`'i destekler**, ama başlığı öyle bir "bozarsınız" ki taraflardan biri onu geçerli sayar, diğeri saymaz. Örneğin başlık adında sekme, satır katlama (header folding), hafif yazım farkı ya da beklenmedik boşluk kullanmak:

```
Transfer-Encoding: chunked
Transfer-Encoding: x
```

veya

```
Transfer-Encoding:\tchunked
```

Sunuculardan biri bu "bozulmuş" TE başlığını kabul edip chunked'a geçerken diğeri onu tanımayıp CL'ye düşerse, sistem yeniden CL.TE veya TE.CL davranışına indirgenir. TE.TE'nin özü, birebir aynı iki başlıkla bile ayrıştırma toleransı farkını sömürebilmektir.

## HTTP/2 ve Downgrade Desync

Modern bir uyarı: **HTTP/2**. HTTP/2'de mesaj uzunluğu belirsizliği prensipte çözülmüştür, çünkü uzunluk bilgisi başlık metninde değil, ikili (binary) frame'lerin yapısında taşınır ve `Content-Length` ile `Transfer-Encoding` başlıklarının kullanımı katı kurallara bağlanmıştır. Ancak birçok mimaride ön uç istemciyle HTTP/2 konuşur, sonra isteği arka uca **HTTP/1.1'e çevirerek (downgrade)** iletir. Bu çeviri sırasında ön uç, HTTP/2 mesajındaki başlıkları HTTP/1.1 metnine yeniden yazar. Eğer bu yeniden yazım titiz değilse (örneğin bir başlık değerinin içine CRLF gömülmesine izin verirse), HTTP/1.1'e inen istekte yeniden smuggling doğar. Buna **H2.CL / H2.TE** veya genel olarak **HTTP/2 downgrade desync** denir. Yani HTTP/2 tek başına sorunu bitirmez; **çeviri katmanı yeni bir saldırı yüzeyidir.**

## Etki: Neden Bu Kadar Tehlikeli?

Request smuggling'in etkisi, birçok yüksek etkili sonuca "taşıyıcı" olabildiği için oldukça geniştir. Öne çıkanlar:

- **Güvenlik kontrollerini atlatma (front-end bypass):** Çoğu mimaride yetkilendirme, IP filtreleme veya WAF gibi kontroller ön uçta uygulanır. Kaçırılan istek arka uca doğrudan ulaştığından, ön uçtaki `/admin` engeli gibi kontroller devre dışı kalabilir. Ön uç isteği hiç "görmediği" için erişim kararını da veremez.
- **Başka kullanıcıların isteklerini ele geçirme / zehirleme (request hijacking):** Kaçak baytlar, aynı bağlantıyı kullanan bir sonraki kurbanın isteğinin önüne eklenir. Saldırgan kurbanın isteğini kendi kontrolündeki bir yola yönlendirip kurbanın oturum bilgilerini (çerezleri, `Authorization` başlığını) kendi kontrol ettiği bir yere yansıtabilir.
- **Web Cache Poisoning (önbellek zehirleme):** Kaçak istek, bir cache'in yanlış içeriği yanlış anahtarla saklamasına yol açarak zararlı bir cevabın birçok kullanıcıya servis edilmesini sağlayabilir. Bu, tek bir isteğin geniş kitleyi etkilemesi demektir.
- **Depolanmış/yansıyan XSS'i tetikleme ve kontrolleri atlama:** Normalde erişilemeyen veya filtrelenen davranışlar smuggling ile tetiklenebilir.
- **Kimlik bilgisi ve oturum sızıntısı:** Kurbanların istekleri saldırganın kontrolündeki bir endpoint'e "yankılanabildiği" için oturum token'ları çalınabilir.

Kritik nokta şudur: request smuggling nadiren "tek başına" son hedeftir; genellikle **bir zincirin ilk halkasıdır** ve arkasından çok daha ciddi bir istismar gelir. Etkiyi bu kadar büyüten şey, saldırının **diğer kullanıcıları** etkileyebilmesi ve **güven sınırlarını** (trust boundary) delmesidir.

## Sömürü Mantığı: Bir Saldırgan Nasıl Düşünür?

Bu bölüm savunmayı anlamak için istismar mantığını açıklar; amaç, savunmacının saldırganla aynı zihinsel modeli kurmasıdır.

1. **Tespit (differential timing / davranış farkı):** Saldırgan önce zincirin desync'e açık olup olmadığını anlar. Klasik yöntem, kasıtlı olarak "eksik" bir chunked istek göndermektir. Eğer arka uç, gelmeyen kalan baytları beklerken takılıp cevabı geciktirirse (timeout), bu bir CL.TE/TE.CL göstergesidir. **Zamanlama farkı** (timing differential), yıkıcı olmayan ilk sinyaldir çünkü başka kullanıcıyı bozmadan test yapmayı sağlar.
2. **Onaylama:** Saldırgan zararsız iki istek gönderir; ikincisinin cevabı beklenenden farklı gelirse (örneğin kaçak önekten dolayı `404` yerine tuhaf bir hata), desync doğrulanmış olur.
3. **Silahlandırma:** Kaçak öneki gerçek bir saldırıya dönüştürür: yetki atlama için `GET /admin`, önbellek zehirleme için özenle seçilmiş bir yol, veya kurbanın isteğini yakalamak için gövdesi bir sonraki isteği "yutacak" şekilde ayarlanmış bir istek.

Bir saldırganın en çok uğraştığı şey **byte hassasiyetidir**: `Content-Length` ve chunk boyutları CRLF'ler dahil tam tutmalıdır, aksi halde bağlantı ya kapanır ya da beklenen davranış oluşmaz.

## Savunma: Katman Katman Nasıl Durdurulur?

Savunma tek bir sihirli ayara değil, birbirini pekiştiren birkaç ilkeye dayanır. Temel mantık: **isteğin uzunluğu konusunda zincirdeki her bileşenin aynı, kesin karara varmasını garanti etmek.**

### 1. Uçtan Uca HTTP/2 Kullanın

En güçlü yapısal savunma, isteğin ön uçtan arka uca **HTTP/2 olarak** taşınmasıdır; downgrade yapılmamalıdır. HTTP/2'nin uzunluk bilgisi belirsizlik bırakmadığından, klasik CL/TE muğlaklığı ortadan kalkar. Downgrade zorunluysa, çeviri katmanının başlık değerlerini titizce doğrulaması (özellikle CRLF enjeksiyonuna karşı) şarttır.

### 2. Belirsiz İstekleri Reddedin (Normalize Etme, Ret)

Ön uç, aşağıdaki durumlarda isteği **kabul edip düzeltmek yerine reddetmelidir** (`400`-benzeri hata):

- Hem `Content-Length` hem `Transfer-Encoding` içeren istekler.
- Birden fazla `Content-Length` başlığı, ya da tutarsız/çelişkili başlıklar.
- Standart dışı biçimlenmiş `Transfer-Encoding` (fazladan boşluk, sekme, beklenmedik değer, duplike başlık).

Neden "normalize et" değil de "reddet"? Çünkü normalize etmek, ön uç ile arka ucun **aynı normalizasyonu yaptığını varsaymayı** gerektirir; bu varsayım her zaman doğru değildir ve yeni desync'lere kapı açar. Belirsiz olanı reddetmek, tüm sınıfı kökten kapatan en güvenli tavırdır.

### 3. Ön Uç ile Arka Ucu Tutarlı Kılın

İdeal olarak ön uç ve arka uç **aynı HTTP ayrıştırma davranışına** sahip olmalıdır. Pratikte bu, aynı üreticiyi/kütüphaneyi kullanmak ya da her ikisinin de standarda katı (strict) modda çalıştığını doğrulamak anlamına gelir. Ayrıştırma toleransı ne kadar düşükse, sömürülecek belirsizlik o kadar azdır.

### 4. Bağlantı Yeniden Kullanımını Kısıtlama Seçeneği

Arka uçla yapılan bağlantının yeniden kullanılmaması (her istemci isteği için ayrı arka uç bağlantısı, ya da şüpheli durumda bağlantının kapatılması) saldırının "kaçak baytların sonraki kurbana yapışması" adımını zorlaştırır. Bu performans maliyeti yaratır, bu yüzden birincil değil, tamamlayıcı bir savunmadır; asıl çözüm belirsizliği baştan bitirmektir.

### 5. Anormal İstekte Bağlantıyı Kapatın

Bir sunucu, ayrıştıramadığı ya da şüpheli bulduğu bir istekle karşılaştığında bağlantıyı **tamamen kapatmalı**, üzerinde işlemeye devam etmemelidir. Böylece bağlantıda bekleyen "artık" baytlar sonraki isteğe bulaşamaz.

## Yaygın Hatalar

- **"WAF var, güvendeyiz" yanılgısı:** Request smuggling'in birincil hedefi zaten çoğu zaman ön uçtaki WAF/filtreyi atlamaktır. Kaçak istek arka uca WAF'ı görmeden ulaşabildiği için, WAF tek başına bu sınıfı kapatmaz.
- **Belirsiz isteği reddetmek yerine "düzeltmeye" çalışmak:** Ön ucu başlıkları normalize edecek şekilde yapılandırmak, arka ucun aynı normalizasyonu yapmaması halinde yeni bir uyumsuzluk yaratabilir. Ret, düzeltmeden daha güvenlidir.
- **HTTP/2'yi "sihirli çözüm" sanmak:** HTTP/2 istemci tarafında konuşulsa bile arka uca HTTP/1.1'e downgrade ediliyorsa risk devam eder. Asıl kritik nokta uçtan uca davranıştır.
- **Sadece CL.TE'yi test edip TE.CL ve TE.TE'yi atlamak:** Bir zincir bir varyanta kapalı olup diğerine açık olabilir. Test kapsamı tüm varyantları içermelidir.
- **Byte/CRLF sayımını gözden kaçırmak:** Hem test hem savunma doğrulaması yapılırken satır sonlarının (CRLF) doğru sayılmaması yanlış negatif sonuçlara yol açar; "açık değil" sanılan bir sistem aslında açıktır.
- **Sadece uygulama katmanına odaklanıp ara katmanları (CDN, LB, proxy) unutmak:** Desync genellikle uygulamanın kendisinde değil, önündeki ara bileşenlerin farklı yorumlarında doğar. Tüm zincirin envanteri çıkarılmalıdır.

## En İyi Pratikler

- **Uçtan uca modern protokol:** Mümkünse tüm zincirde HTTP/2 (ya da daha yeni) kullanın ve gereksiz HTTP/1.1 downgrade'lerinden kaçının. Downgrade zorunluysa çeviri katmanını başlık enjeksiyonuna karşı katılıkla yapılandırın.
- **Belirsizliği reddet, düzeltme:** Çelişkili veya standart dışı uzunluk başlıklarını taşıyan istekleri ön uçta reddedin; sessizce normalize etmeyin.
- **Zincir bütünlüğü:** Ön uç ve arka ucun HTTP ayrıştırma davranışlarını hizalayın; ideal olarak katı (strict) modda çalışan, davranışı bilinen bileşenler seçin.
- **Şüpheli durumda bağlantıyı kapat:** Ayrıştırılamayan istekte bağlantıyı yeniden kullanmayın; kapatın.
- **Tüm zinciri envanterle:** CDN, load balancer, reverse proxy ve uygulama sunucusu dahil her katmanın hangi HTTP sürümünü konuştuğunu ve uzunluğu nasıl yorumladığını belgeleyin. Görünmeyen katman en riskli katmandır.
- **Düzenli test:** Yalnızca yetkili ortamlarda ve izinle, timing tabanlı tespit dahil tüm varyantları (CL.TE, TE.CL, TE.TE, HTTP/2 downgrade) kapsayan güvenlik testleri yürütün. Yıkıcı olmayan tespit tekniklerini tercih edin ki başka kullanıcıları etkilemeyin.
- **Bileşenleri güncel tutun:** Proxy ve sunucu yazılımlarındaki ayrıştırma sertleştirmeleri sürümlerle gelir; güncelleme, bilinen desync vektörlerini kapatmanın en pratik yollarından biridir.
- **İzleme ve loglama:** Anormal uzunluk başlıkları, beklenmeyen bağlantı davranışları ve tuhaf cevap eşleşmeleri için loglama kurun; smuggling denemeleri genelde log'da tutarsız istek/yanıt eşleşmeleri olarak iz bırakır.

## Sonuç

HTTP Request Smuggling, egzotik bir "hafıza hatası" değil; **protokolün metinsel esnekliği ile heterojen zincir mimarisinin** kesişiminde doğan bir yorumlama uyumsuzluğudur. Kök neden her zaman aynıdır: bir isteğin nerede bittiği konusunda iki sunucunun anlaşamaması. Bu yüzden savunmanın da özü sabittir — zincirdeki her bileşenin isteğin uzunluğu hakkında **tek ve kesin** karara varmasını sağlamak, belirsiz olanı düzeltmeye çalışmadan reddetmek ve mümkün olan yerde belirsizliği yapısal olarak (uçtan uca modern protokolle) ortadan kaldırmak. Etkisi kimlik atlamadan önbellek zehirlemeye kadar uzandığı için, request smuggling'i "bir bug" değil, arkasından ciddi zincirler gelebilen bir **güven sınırı ihlali** olarak ele almak gerekir.
