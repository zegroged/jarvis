# WAF/RASP Atlatma Teknikleri ve Payload Obfuscation

## Giriş ve Kapsam

Web Application Firewall (WAF) ve Runtime Application Self-Protection (RASP), uygulama katmanı saldırılarına karşı savunmanın son hatlarından ikisidir. WAF, HTTP trafiğini uygulamaya ulaşmadan önce inceleyen bir ağ/proxy seviyesi kontroldür; RASP ise uygulamanın kendi çalışma zamanı (runtime) içine gömülür ve fonksiyon çağrılarını, sorgu yapıcılarını, dosya sistemi erişimlerini gözlemleyerek karar verir. İkisi de "imza tabanlı" veya "davranış tabanlı" tespit mantığına dayanır ve bu mantığın doğası gereği atlatılabilir. Bu makalenin amacı, atlatma tekniklerinin ARKASINDAKI mantığı anlamak, böylece hem red-team/bug-bounty çalışmasında "neden bu payload işliyor" sorusuna cevap verebilmek hem de savunma tarafında doğru mimariyi kurabilmektir. Burada bir "canlı hedefe saldırı kılavuzu" değil, mekanizma analizi ve tespit/savunma rehberi sunulmaktadır.

Konunun neden ayrı bir modül olarak ele alınması gerektiği açık: SQL injection, XSS, command injection gibi konular "payload'ın ne yaptığını" anlatır; WAF atlatma ise "payload doğru olsa bile filtreden nasıl geçer" sorusunu ele alır. Bir pentest'te en yaygın senaryo, uygulamanın zaten savunmasız olması değil, savunmasız uygulamanın önüne konan WAF'in yanlış yapılandırılmış veya imza tabanlı olup normalize etme hatası yapmasıdır.

## Kök Neden: WAF/RASP Neden Atlatılabilir?

### Temel Sebep 1 - Parsing Differential (Ayrıştırma Farklılığı)

WAF'in HTTP isteğini/gövdesini yorumlama biçimi ile arkadaki uygulama sunucusunun (nginx, Apache, Tomcat, uygulama kodu, veritabanı parser'ı) yorumlama biçimi TIPATIP AYNI OLMAK ZORUNDA DEĞİLDİR. İki farklı parser, aynı bayt dizisini farklı şekilde "anlarsa", aralarında bir yorum farkı (interpretation gap) oluşur. Saldırgan, WAF'in "zararsız" olarak okuduğu ama arka uçtaki sistemin "zararlı" olarak çalıştırdığı bir girdi tasarlar. Bu, tüm WAF atlatma tekniklerinin en temel kök nedenidir: normalization asimetrisi.

Somut örnek: WAF bir HTTP body'sini `Content-Length` header'ına göre okurken, arka uçtaki sunucu `Transfer-Encoding: chunked`'a göre okuyabilir (HTTP request smuggling ile ilişkili bir mantık). Ya da WAF bir parametreyi URL-decode ederken bir kez decode eder, arka uygulama iki kez decode eder (double encoding) — WAF `%2527` gördüğünde bunu `%27` sanarak zararsız bulur, ama uygulama iki kez decode edip gerçek `'` (tek tırnak) karakterine ulaşır.

### Temel Sebep 2 - İmza Tabanlı Tespitin Doğası

Klasik WAF kuralları (örneğin ModSecurity CRS gibi açık kaynak kural setleri) regex veya string-match tabanlıdır: `UNION.*SELECT`, `<script`, `../` gibi kalıpları arar. Bu yaklaşımın matematiksel sınırı nettir — regex, sonsuz sayıda sözdizimsel varyasyonu kapsayamaz. SQL, HTML, JavaScript gibi diller yorumlayıcı seviyesinde ÇOK ESNEKTİR (yorum satırları, whitespace alternatifleri, fonksiyonel eşdeğerlik, encoding katmanları), bu yüzden "aynı anlamı taşıyan ama farklı görünen" sonsuz sayıda string üretilebilir. Bir imza "bir" varyasyonu yakalar; obfuscation bu varyasyon uzayında gezinerek imzanın dışına çıkar.

### Temel Sebep 3 - Bağlam Kaybı (Context Loss)

WAF, HTTP isteğini görür ama arka uçtaki kodun HANGİ BAĞLAMDA (context) bu veriyi kullanacağını bilmez: SQL sorgusuna mı gidecek, HTML'e mi yazılacak, bir shell komutuna mı enjekte edilecek, yoksa bir dosya yoluna mı eklenecek? Aynı girdi bağlama göre farklı şekilde "tehlikeli" hale gelir. WAF bu bağlam bilgisine sahip olmadığı için genellikle en geniş/en gevşek kuralı uygulamak zorunda kalır (yanlış pozitifleri azaltmak için), bu da tespit hassasiyetini düşürür. RASP bu sorunu kısmen çözer çünkü runtime içinde çalışır ve gerçek "sink" fonksiyonunu (örneğin `exec()`, prepared statement olmayan bir SQL çağrısı) görebilir — ama RASP'in de kendi zayıflıkları vardır (aşağıda).

## Encoding Katmanları ve Karakter Seviyesi Obfuscation

Bu, en yaygın ve kavramsal olarak en önemli kategoridir. Mantık şöyle işler: HTTP, tarayıcılar ve sunucular ÇOKLU encoding şemasını destekler (URL encoding, double URL encoding, Unicode/UTF-8 overlong encoding, HTML entity encoding, hex/octal kaçışlar, base64 katmanları belirli bağlamlarda). WAF bu encoding katmanlarından HANGİSİNİ, KAÇ KEZ decode edeceğini seçmek zorundadır; seçim yanlışsa saldırgan bu farktan yararlanır.

**Neden çalışır**: WAF genellikle performans nedeniyle sınırlı sayıda decode döngüsü yapar (örneğin bir kez URL-decode). Ama arka uçtaki web sunucusu veya uygulama çerçevesi (framework) kendi iç mantığında birden fazla decode aşaması uygulayabilir — örneğin bir path normalization işlemi sırasında veya bir template engine'in kendi decode adımı sırasında. Bu durumda `%25` (encoded `%`) gibi bir katmanla saklanan zararlı karakter, WAF'in görmediği bir noktada açılır.

Case manipulation da benzer bir mantığa dayanır: bazı diller/parserlar case-insensitive'dir (SQL anahtar kelimeleri, HTML tag isimleri), WAF kuralı ise case-sensitive regex yazılmış olabilir (örneğin sadece küçük harf `select` arayan bir kural, `SeLeCt` yazılınca kaçar). Bu, geliştiricinin/kural yazarının regex'i normalize etmeden yazması kaynaklı klasik bir hatadır.

Whitespace/separator manipulation ise SQL ve benzeri dillerin boşluk yerine başka ayırıcıları (yorum satırları `/**/`, tab, newline, parantez) kabul etmesinden kaynaklanır. `UNION SELECT` yerine `UNION/**/SELECT` veya `UNION%0aSELECT` gibi varyasyonlar, "boşluk arayan" bir regex'i atlatırken parser'a göre geçerli sözdizimi kalır.

**Tespit**: Tek katmanlı decode + regex yerine, "normalize-then-match" mimarisi (canonical form'a getirip eşle) ve BİRDEN FAZLA decode döngüsü uygulanıp her aşamada tekrar kontrol edilmesi (recursive/iterative normalization) gerekir. Loglarda aynı istekte çoklu encoding katmanı görülmesi (`%25XX`, çift encode edilmiş path segmentleri) başlıbaşına bir anomali sinyalidir ve alarm üretmelidir — normal istemciler nadiren kendi kendine çift encode üretir.

**Savunma**: WAF/proxy seviyesinde tüm decode işlemlerinin ARKA UÇTAKI UYGULAMAYLA AYNI SEMANTİĞE sahip olması sağlanmalı (aynı kütüphane/versiyon, aynı decode derinliği). Daha güçlü olan yaklaşım ise WAF'a güvenmek yerine, uygulama seviyesinde parametrize sorgular (prepared statements), context-aware output encoding (HTML/JS/URL bağlamına göre doğru encoder), ve allowlist tabanlı girdi doğrulama kullanmaktır — bunlar encoding oyunlarından BAĞIMSIZ çalışır çünkü sentaks ağacında (parse tree) çalışırlar, string eşleşmesinde değil.

## HTTP Parameter Pollution (HPP)

**Tanım**: Aynı parametre adının bir HTTP isteğinde birden fazla kez gönderilmesidir (`?id=1&id=2` gibi) ya da farklı gövde/parça kombinasyonlarında (query string + body, JSON + form-encoded karışımı) aynı mantıksal alanın çoklu temsilidir.

**Kök neden**: HTTP spesifikasyonu, tekrarlanan parametrelerin nasıl ele alınacağını KESİN OLARAK TANIMLAMAZ. Bu "boşluk", her dil/framework/sunucunun kendi tercihini yapmasına yol açmıştır: PHP son değeri alır, ASP.NET tüm değerleri virgülle birleştirir, bazı Java framework'leri ilk değeri alır. WAF, HTTP katmanında tek bir "doğru" yorumu seçmek zorundadır (genellikle ilk veya son değer), ama arka uygulama farklı davranırsa, WAF'in incelediği değer ile uygulamanın GERÇEKTEN İŞLEDİĞİ değer FARKLI olur. Saldırgan zararsız görünen değeri WAF'in baktığı konuma, zararlı değeri uygulamanın okuyacağı konuma yerleştirir.

**Nasıl çalışır (kavramsal)**: Diyelim WAF ilk `id` parametresini kontrol ediyor ve arkadaki uygulama sonuncusunu kullanıyor. `?id=1&id=' OR '1'='1` şeklinde bir istek, WAF'in gözünde masum (`id=1`) görünür ama uygulama katmanında zararlı değer işlenir. Bu, WAF ile uygulamanın aynı "kaynak" veriyi farklı şekilde seçmesinden (selection differential) kaynaklanır — parsing differential'in bir alt türüdür.

**Tespit**: Aynı parametre adının tekrar etmesi zaten anomali sayılmalıdır; loglama ve WAF kuralları tekrarlanan parametre isimlerini FLAGLEMELİ, çoklu değer varsa tümünü incelemelidir (sadece ilkini ya da sonuncusunu değil).

**Savunma**: Uygulama katmanında, framework'un parametre çokluğu davranışı AÇIKÇA BİLİNMELİ ve WAF konfigürasyonu buna GÖRE hizalanmalı. En sağlam savunma, girdi doğrulamasının WAF'ta değil UYGULAMA KODUNDA, tüm parametre değerleri toplanıp değerlendirilerek yapılmasıdır; ayrıca API gateway/proxy seviyesinde tekrarlanan parametrelerin reddedilmesi (strict parsing) makul bir varsayılan olabilir.

## Protokol Seviyesi Kaçışlar (Protocol-Level Evasion)

Bu kategori, HTTP'nin kendisinin katmanlar arası (WAF - ters proxy - uygulama sunucusu) tutarsız yorumlanmasından yararlanır; geniş anlamda "HTTP request smuggling / desync" ailesiyle akrabadır.

**Kök neden**: Modern web mimarileri ÇOKLU HTTP işlemcisinden oluşur (CDN, WAF, load balancer, reverse proxy, uygulama sunucusu). Her biri isteği kendi kod tabanında ayrı ayrı parse eder. `Content-Length` ve `Transfer-Encoding` header'ları aynı anda bulunursa (veya belirsiz/hatalı biçimde yazılırsa), hangi katmanın hangisini "geçerli" saydığı FARKLILAŞABİLİR. Bir katman gövdenin nerede bittiğine bir şekilde karar verirken, diğeri farklı karar verir; bu da bir isteğin iç içe iki istek gibi yorumlanmasına (smuggling) veya WAF'in görünmeyen kısmını arka ucun işlemesine yol açar.

Benzer şekilde, HTTP/2'den HTTP/1.1'e downgrade yapan gateway'lerde, HTTP/2'nin binary framing yapısı ile HTTP/1.1'in text tabanlı yapısı arasındaki dönüşüm de tutarsızlık kaynağı olabilir (örneğin gizli/pseudo-header enjeksiyonu, newline karakterlerinin farklı katmanlarda farklı yorumlanması — CRLF injection ailesiyle ilişkilidir).

**Tespit**: Ağ katmanında anormal header kombinasyonları (hem `Content-Length` hem `Transfer-Encoding` varlığı, geçersiz `Transfer-Encoding` değerleri, obfuscated chunk boyutları) loglanmalı ve reddedilmeli. Ters proxy/WAF ile arka uç arasında "istek/yanıt sayısı tutarsızlığı" (bir istek gönderilip birden fazla yanıt alınması gibi) izlenmelidir.

**Savunma**: En etkili savunma, TÜM katmanların AYNI HTTP kütüphanesini/parser davranışını kullanması ya da en azından RFC'ye sıkı uyan, belirsiz istekleri OTOMATİK REDDEDEN (fail-closed) sunucu yazılımları seçmektir. HTTP/1.1'i tamamen devre dışı bırakıp her yerde HTTP/2 (end-to-end) kullanmak, bu smuggling sınıfının bir kısmını ortadan kaldırır. Düzenli olarak katmanlar arası tutarlılık testleri (differential testing) yapılması önerilir.

## RASP'a Özgü Atlatma Mantığı

RASP, WAF'tan farklı olarak "ağ seviyesinde string" değil, "runtime'da gerçek fonksiyon çağrısı ve veri akışı" görür; bu yüzden encoding oyunlarına karşı genel olarak daha dayanıklıdır (çünkü değerlendirmeyi decode edilmiş, gerçek kullanılan değer üzerinde yapar). Ancak RASP'in kendi zayıf noktaları vardır:

**Instrumentation kapsam dışı kalma**: RASP genellikle bilinen "tehlikeli sink" fonksiyonlarını (SQL execute, shell exec, dosya açma vb.) hook'lar. Eğer saldırgan, enstrümante olmayan bir kütüphane/yol üzerinden (örneğin native/JNI çağrısı, dinamik kod yükleme, reflection, az bilinen bir serialization/deserialization yolu) aynı etkiye ulaşırsa, RASP bu yolu görmez. Bu, "kapsam dışı kalma" (instrumentation gap) olarak düşünülebilir — WAF'taki parsing differential'in runtime karşılığıdır.

**Performans/timeout baskısı**: RASP, uygulamanın kendi thread'i içinde çalıştığı için ağır analiz yapamaz (performans etkisi kritik SLA'ları bozar); bu da bazı derin analiz türlerinin (örneğin tüm veri akışını izleyen taint tracking) sınırlı/örneklemeli uygulanmasına yol açabilir; saldırgan bu sınırların dışında kalan yolları arayabilir.

**Bağlam/tenant karıştırma**: Mikroservis mimarilerinde RASP her servis için ayrı ayrı devreye alınmış olabilir; bir servis korunurken zincirdeki diğer servis (iç API, arka plan iş kuyruğu, mesaj kuyruğu tüketicisi) korumasız kalabilir. Saldırgan, korunan servisin ARKASINDAKI korunmayan servise doğrudan veya dolaylı şekilde ulaşmaya çalışır (SSRF, mesaj kuyruğu enjeksiyonu gibi yollarla).

**Tespit/Savunma**: RASP tek başına yeterli değildir; "defense in depth" ilkesiyle WAF + RASP + uygulama seviyesi güvenli kodlama (parametrize sorgular, en az yetki ilkesi, girdi doğrulama) katmanları birlikte kullanılmalıdır. RASP kapsamının (hangi fonksiyonlar/kütüphaneler instrumente edildiği) DÜZENLİ OLARAK gözden geçirilmesi ve yeni bağımlılıklar eklendiğinde kapsamın güncellenmesi önemlidir. Mikroservis ortamında her servis SINIRLARINDA (trust boundary) kendi girdi doğrulamasını yapmalı, "üst katman zaten kontrol etti" varsayımına güvenilmemelidir (zero-trust prensibi).

## Yaygın Hatalar (Savunma Tarafında)

**Tek katman güvenine dayanma**: WAF'i "yeterli" görüp uygulama kodunu güvenli yazmayı ihmal etmek en yaygın ve en tehlikeli hatadır. WAF bir yardımcı kontroldür (compensating control), birincil savunma DEĞİLDİR. Prepared statement kullanılmayan bir SQL sorgusu, WAF ne kadar iyi olursa olsun bir gün bir obfuscation varyasyonuyla aşılabilir.

**Blocklist yaklaşımı**: "Bilinen kötü kalıpları" listeleyip engellemek (blocklist/denylist), yeni varyasyonlara karşı yapısal olarak zayıftır; sonsuz varyasyon uzayı karşısında sonlu bir liste her zaman eksik kalır. Allowlist (izin verilenler listesi, örneğin "sadece rakam", "sadece bilinen enum değerleri") yapısal olarak çok daha güçlü bir savunmadır çünkü beklenmeyen HER ŞEYİ reddeder.

**WAF kural setini "kopyala-yapıştır" kurup özelleştirmemek**: Genel amaçlı açık kaynak kural setleri (örneğin CRS tarzı) geniş uyumluluk için gevşek ayarlanmıştır; uygulamaya özel sıkı kurallar (örneğin belirli bir parametrenin sadece UUID formatında olabileceğini bilen bir kural) çok daha az atlatılabilir ama kurulum efor gerektirir. Kör kopyalama, hem yanlış pozitif hem yanlış negatif oranı yüksek bir sistem üretir.

**Loglama/gözlemlenebilirlik eksikliği**: WAF/RASP'in "engelledim" demesi yetmez; NEDEN engellendiği, hangi imzaya takıldığı, hangi normalize edilmiş form üzerinden karar verildiği loglanmalıdır. Bu loglar olmadan "false negative" (kaçırılan saldırı) tespiti neredeyse imkansızdır çünkü sadece başarılı bloklar görüntülenir, başarısız bloklar (atlatılanlar) sessiz kalır.

**Tek nokta arızası olarak WAF/RASP'i konumlandırmak**: WAF/RASP devre dışı kalırsa (yanlışlıkla kapatılma, fail-open konfigürasyon, DoS ile bypass) uygulamanın ÇIPLAK kalması, mimari bir tasarım hatasıdır. Fail-closed (hata durumunda trafiği reddet) tercih edilmeli ve WAF'in kendisi de izlenen/alarm üreten bir bileşen olarak ele alınmalıdır.

## Sonuç

WAF/RASP atlatma teknikleri, tek tek "sihirli payload'lar" değil, altta yatan iki sistemin (WAF'in gördüğü ile arka ucun işlediği) arasındaki YORUM FARKINDAN doğan yapısal bir zayıflıktır. Encoding katmanları, HPP, protokol seviyesi kaçışlar ve RASP kapsam boşlukları hepsi aynı kökü paylaşır: çoklu bileşenli bir sistemde her bileşenin aynı veriyi FARKLI SEMANTİKLE yorumlaması. Bu nedenle savunmanın gerçek çözümü, WAF/RASP'i "sihirli kalkan" olarak değil, katmanlı savunmanın BİR PARÇASI olarak konumlandırmak; asıl güvenliği uygulama kodunda (parametrize sorgular, context-aware encoding, allowlist doğrulama, en az yetki) kurmak; ve tüm katmanlar arasında parsing/normalizasyon tutarlılığını SIKI ŞEKİLDE test etmektir (differential testing, fuzzing, düzenli red-team değerlendirmesi). Gözlemlenebilirlik (detaylı loglama, alarm, anomali tespiti) olmadan hiçbir WAF/RASP kurulumunun gerçek etkinliği ölçülemez; "engelliyoruz" varsayımı, aktif olarak doğrulanmadıkça bir varsayımdan ibarettir.
