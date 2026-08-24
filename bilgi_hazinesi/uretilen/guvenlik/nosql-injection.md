# NoSQL Injection: MongoDB Operatör Enjeksiyonu, JSON Body Saldırıları ve Savunma

## Tanım

NoSQL Injection, bir uygulamanın kullanıcıdan gelen veriyi yeterince doğrulamadan bir NoSQL veritabanı sorgusuna karıştırması sonucu ortaya çıkan bir enjeksiyon zafiyetidir. Klasik SQL Injection ile aynı köke sahiptir: **veri** ile **komut/sorgu yapısı** arasındaki sınırın erimesi. Saldırgan, veri olması beklenen bir alana sorgu mantığını değiştirecek unsurlar sokarak veritabanının davranışını yeniden şekillendirir. Ancak NoSQL dünyasında sorgular çoğu zaman düz metin (string) değil, yapısal nesnelerdir (JSON/BSON dokümanları, operatörlerle bezenmiş sözlükler). Bu yapısal doğa, saldırının şeklini SQL'den belirgin biçimde farklı kılar.

"NoSQL" tek bir teknoloji değildir; MongoDB (doküman tabanlı), Redis (anahtar-değer), Cassandra (geniş kolon), CouchDB, Elasticsearch gibi çok farklı veri modellerini kapsayan bir şemsiye terimdir. Enjeksiyonun somut biçimi kullanılan motora göre değişir. Bu makalede ağırlığı MongoDB'ye ve onun operatör tabanlı sorgu modeline vereceğiz, çünkü en yaygın karşılaşılan ve en öğretici örnek budur. Yine de anlatılan mantık, özellikle "yapısal veriyi güvenilmez girdiyle inşa etmek" fikri, diğer motorlara da taşınabilir.

## Kök Neden: Neden Böyle Oluyor?

NoSQL Injection'ın kökünü anlamak için önce MongoDB sorgusunun nasıl göründüğünü kavramak gerekir. MongoDB'de bir sorgu, aslında bir dokümandır. Örneğin bir kullanıcıyı adına göre bulmak istediğinizde sorgu şu biçimdedir:

```json
{ "username": "mert" }
```

Bu, "username alanı tam olarak mert'e eşit olan dokümanı getir" anlamına gelir. Buradaki `"mert"` bir **değer**dir. MongoDB, sorgu dokümanında özel anahtarlar (operatörler) tanır ve bunlar `$` işaretiyle başlar: `$ne` (eşit değil), `$gt` (büyüktür), `$in` (listede), `$regex` (düzenli ifade), `$where` (JavaScript ifadesi) gibi. Bir alanın değeri düz bir skaler yerine bir nesne olduğunda, MongoDB onu operatör ifadesi olarak yorumlar:

```json
{ "username": { "$ne": null } }
```

Bu sorgu artık "username'i null olmayan herhangi bir doküman" anlamına gelir; yani pratikte tüm kullanıcıları getirir.

İşte kök neden tam burada saklıdır. Web uygulamalarının çoğu, HTTP isteklerini gövdesindeki JSON'u doğrudan bir nesneye ayrıştırır ve bu nesneyi hiç düzeltmeden sorguya yerleştirir. Node.js/Express ekosisteminde bu pattern son derece yaygındır:

```javascript
// Tehlikeli: req.body doğrudan sorguya gidiyor
const user = await db.collection('users').findOne({
  username: req.body.username,
  password: req.body.password
});
```

Geliştirici burada `req.body.username`'in bir string olacağını **varsayar**. Ama HTTP istemcisi JSON gönderdiği için bu alanın string yerine bir nesne olmasını hiçbir şey engellemez. Saldırgan `username`'i `{"$ne": null}` olarak gönderdiğinde, geliştiricinin "eşitlik kontrolü" sandığı ifade sessizce bir "eşit değil" operatörüne dönüşür. Sorgunun **yapısı** kullanıcı tarafından ele geçirilmiştir; oysa geliştirici yalnızca bir **değer** beklemekteydi.

Bunun daha derin sebebi, JSON ve dinamik tipli dillerin (JavaScript, Python, PHP) birleşmesinden doğan bir tip belirsizliğidir. String beklenen yerde nesne gelmesi çalışma zamanında hata üretmez; kod sessizce farklı davranır. SQL'de metin tabanlı sorgularda enjeksiyon için tırnak kaçırmak (`'`) gerekirken, MongoDB'de hiçbir tırnak kaçırmaya gerek yoktur; yalnızca gönderilen verinin **tipini** string'den nesneye çevirmek yeterlidir. Bu yüzden NoSQL Injection'a bazen "operatör enjeksiyonu" da denir.

## Somut Örnek 1: Kimlik Doğrulama Atlatma (Authentication Bypass)

En klasik ve en yıkıcı senaryo, giriş ekranının atlatılmasıdır. Yukarıdaki savunmasız `findOne` kodunu düşünelim. Normal bir giriş isteği şöyledir:

```http
POST /login HTTP/1.1
Content-Type: application/json

{ "username": "mert", "password": "GizliParola123" }
```

Saldırgan ise şunu gönderir:

```http
POST /login HTTP/1.1
Content-Type: application/json

{ "username": "admin", "password": { "$ne": null } }
```

Sunucudaki sorgu şuna dönüşür:

```json
{ "username": "admin", "password": { "$ne": null } }
```

Bu, "username'i admin olan ve password'ü null olmayan doküman" demektir. admin kullanıcısının bir parolası olduğu için (ki vardır) bu koşul sağlanır. Sorgu admin dokümanını döndürür, uygulama girişi başarılı sayar ve saldırgan parolayı hiç bilmeden admin oturumu açar. Parolanın karşılaştırması veritabanı katmanında yapıldığı ve saldırgan bu katmanın operatör sözdizimini ele geçirdiği için, gerçek parola tamamen devre dışı kalmıştır.

Eğer saldırgan hedef kullanıcı adını bile bilmiyorsa, her iki alanı da operatörle doldurabilir:

```json
{ "username": { "$ne": null }, "password": { "$ne": null } }
```

Bu sorgu koleksiyondaki **ilk** kullanıcıyı döndürür; çoğu sistemde bu ilk kayıt yönetici hesabıdır. Bu, güçlü parola politikalarını, hash'lemeyi ve tüm parola karmaşıklığı önlemlerini bir çırpıda anlamsız kılar; çünkü parola hiç karşılaştırılmamaktadır.

## Somut Örnek 2: Operatörlerle Veri Sızdırma ve Blind Injection

Saldırgan yalnızca giriş atlatmakla kalmaz; operatörleri veri çıkarmak için de kullanabilir. `$regex` operatörü bu konuda özellikle güçlüdür. Diyelim ki bir parola sıfırlama akışında sunucu, gönderilen token'ı doğrudan sorguya koyuyor. Saldırgan `$regex` ile token'ı karakter karakter tahmin edebilir:

```json
{ "resetToken": { "$regex": "^a" } }
```

Bu sorgu bir sonuç döndürürse token "a" ile başlıyor demektir; döndürmezse başka bir harf denenir. Yanıtın sadece "var/yok", "başarılı/başarısız" gibi ikili (boolean) bir sinyal vermesi yeterlidir. Bu tekniğe **blind NoSQL injection** denir ve mantığı SQL'deki blind injection ile aynıdır: doğrudan veri okuyamasak da, sorgunun doğru/yanlış cevabına bakarak veriyi bit bit yeniden inşa ederiz. Prefiks uzatılarak (`^ab`, `^abc` ...) token tamamen kurtarılabilir. Aynı teknik parola hash'lerini, gizli alanları veya diğer kullanıcıların kayıtlarını sızdırmak için uyarlanabilir.

`$where` operatörü ise daha da tehlikeli bir yüzeydir. MongoDB'nin bazı sürümlerinde ve yapılandırmalarında `$where`, sorgu içinde rastgele JavaScript çalıştırmaya izin verir:

```json
{ "$where": "this.password.length > 8" }
```

Saldırgan `$where` alanına girdi kontrol edebiliyorsa, hem karmaşık veri sızdırma koşulları yazabilir hem de sunucu tarafı JavaScript motorunu zorlayarak bir Denial of Service (örneğin sonsuz döngü veya ağır hesaplama) tetikleyebilir. Bu yüzden `$where` ve benzeri sunucu tarafı JavaScript özelliklerinin (`mapReduce`, `$accumulator` gibi) genellikle tamamen kapatılması önerilir.

## Somut Örnek 3: GET Parametreleri ve Dizi/Nesne Zorlaması

Enjeksiyon yalnızca JSON gövdesiyle sınırlı değildir. Birçok web framework'ü, URL sorgu string'lerini de zengin veri yapılarına ayrıştırır. Express'in varsayılan `qs` ayrıştırıcısı buna klasik örnektir. Şu istek:

```
GET /search?username[$ne]=null
```

`qs` tarafından şuna ayrıştırılır:

```javascript
{ username: { $ne: null } }
```

Yani geliştirici JSON body'yi hiç kullanmasa, sadece `req.query.username`'i sorguya koysa bile, saldırgan URL üzerinden operatör enjekte edebilir. Bu, "ben JSON almıyorum, güvendeyim" yanılgısının neden tehlikeli olduğunu gösterir. PHP'de de benzer bir durum vardır: `?username[$ne]=1` biçimindeki parametreler PHP tarafından diziye çevrilir ve MongoDB sürücüsüne nesne olarak ulaşır. Kök neden yine aynıdır: framework, düz string beklediğiniz bir yerde yapısal veri üretir ve siz bunu fark etmeden sorguya taşırsınız.

## Sömürü Mantığı: Saldırgan Nasıl Düşünür?

Bir saldırgan NoSQL Injection ararken önce hedefin arka planında bir NoSQL veritabanı olup olmadığını anlamaya çalışır. İpuçları: `Content-Type: application/json` kabul eden uçlar, JavaScript ağırlıklı yığınlar (MEAN/MERN stack), hata mesajlarında MongoDB/BSON izleri. Sonra tipik bir keşif akışı izler:

1. **Kırılganlık testi:** Bir alana `{"$ne": null}` veya URL'de `[$ne]=` sokarak yanıtın değişip değişmediğine bakar. Girişte "yanlış parola" yerine başarı dönüyorsa, ya da liste beklenenden fazla kayıt getiriyorsa, operatör yorumlanıyor demektir.
2. **Operatör keşfi:** `$gt`, `$in`, `$regex`, `$where` gibi operatörleri deneyerek hangilerinin ayrıştırıldığını haritalar. `$regex` çalışıyorsa blind veri çıkarma kapısı açılmıştır.
3. **Otomasyona geçiş:** Karakter karakter tahmin gibi yorucu işler script'lenir; regex prefiksleri programatik olarak uzatılarak gizli değerler kurtarılır. Zamana dayalı (time-based) varyantlarda ise `$where` içine ağır hesaplama konularak yanıt gecikmesi ölçülür ve boolean sinyal buradan elde edilir.

Bu mantığı bilmek savunmacı için kritiktir: saldırganın ihtiyaç duyduğu tek şey, girdisinin **tipini** değiştirebilmesi ve sorgu davranışında **gözlemlenebilir bir fark** yaratmasıdır. Savunmanın hedefi de tam olarak bu iki koşulu ortadan kaldırmaktır.

## Savunma: Katmanlı ve Kök-Neden Odaklı

Savunmada tek bir sihirli çözüm yoktur; birbirini tamamlayan katmanlar gerekir. En önemli ilke şudur: **girdinin tipini zorla, operatörlerin veri alanına sızmasını engelle.**

### 1. Girdi tipini doğrula ve zorla (en kritik katman)

Kök neden tip belirsizliği olduğu için en etkili savunma tipin kesinleştirilmesidir. Bir parolanın string olması gerekiyorsa, sorguya koymadan önce string olduğunu doğrulayın:

```javascript
if (typeof req.body.username !== 'string' ||
    typeof req.body.password !== 'string') {
  return res.status(400).json({ error: 'Geçersiz girdi' });
}
```

Bu basit kontrol, `{"$ne": null}` gibi nesne payload'larını daha sorgu kurulmadan reddeder çünkü onların tipi `object`'tir. Daha sağlam yol, bir şema doğrulama kütüphanesi (Joi, Zod, Ajv gibi) kullanarak her alan için beklenen tipi, uzunluğu ve biçimi merkezî olarak tanımlamaktır. Şema tabanlı doğrulama, tek tek `typeof` kontrollerinin unutulma riskini ortadan kaldırır ve girdiyi güvenilir hale getirir.

Girdiyi mutlaka string'e çevirmek de bir seçenektir (`String(req.body.username)`), ancak bu her zaman ideal değildir çünkü bazı meşru alanlar gerçekten dizi veya nesne olabilir. Bu yüzden "her şeyi string yap" yerine "her alanın beklenen tipini şemayla doğrula" yaklaşımı daha doğrudur.

### 2. Operatör anahtarlarını temizle (sanitization)

İkinci katman, `$` ile başlayan anahtarları ve nokta (`.`) içeren anahtarları girdiden ayıklamaktır; çünkü MongoDB operatörleri `$` ile başlar ve nokta iç içe alan erişimi için kullanılır. Bu iş için topluluk tarafından bakımı yapılan sanitize kütüphaneleri (örneğin Express için express-mongo-sanitize benzeri araçlar) mevcuttur; bunlar `req.body`, `req.query` ve `req.params` içindeki tehlikeli anahtarları temizler veya reddeder. Sürüm ve tam davranış farklılıkları olabileceğinden, kullanacağınız kütüphanenin belgesini doğrulayın; bazıları anahtarı siler, bazıları karakteri bir başkasıyla değiştirir.

Ancak sanitization'ı tek savunma yapmayın. Anahtar temizleme, tip doğrulamanın yerine geçmez; ikisi birlikte kullanıldığında güçlüdür. Ayrıca bazı sanitize kütüphanelerinin, iç içe geçmiş yapıları veya prototype pollution vektörlerini tam kapsamadığı durumlar olmuştur; bu yüzden derinlemesine savunma şarttır.

### 3. Sunucu tarafı JavaScript'i kapat

`$where`, `mapReduce` ve benzeri sunucu tarafı JavaScript yürütme özellikleri, uygulamanız bunlara gerçekten ihtiyaç duymuyorsa devre dışı bırakılmalıdır. MongoDB yapılandırmasında sunucu tarafı JavaScript'i kapatma seçeneği bulunur (genellikle güvenlik/JavaScript ile ilgili bir yapılandırma anahtarı). Bu, hem rastgele kod yürütme hem de DoS yüzeyini önemli ölçüde daraltır. Kesin yapılandırma anahtarının adı ve varsayılan davranışı MongoDB sürümüne göre değişebildiği için, kurulumunuzun sürümüne ait resmî belgeden teyit edin.

### 4. Parametreli/yapısal sorgu inşası ve en az yetki

Sorguyu string birleştirmeyle (özellikle `$where` içine metin ekleyerek) inşa etmekten kaçının; her zaman sürücünün yapısal API'sini kullanın ve değerleri açıkça değer olarak geçirin. Ek olarak, uygulamanın bağlandığı veritabanı kullanıcısına **en az yetki** (least privilege) verin: uygulama yalnızca okuma yapıyorsa yazma yetkisi olmasın, yalnızca belirli koleksiyonlara erişsin. Böylece bir enjeksiyon gerçekleşse bile hasarın kapsamı sınırlı kalır.

### 5. Blind çıkarmayı zorlaştır: yanıt farklarını azalt

`$regex` tabanlı blind saldırılar, yanıttaki boolean farktan beslenir. Kimlik doğrulama ve token doğrulama uçlarında, geçerli/geçersiz durumlar arasında ayırt edilebilir zamanlama ve mesaj farkları bırakmamaya çalışın; hata mesajlarını genelleştirin ve rate limiting uygulayın. Bu, enjeksiyonu tek başına engellemez ama otomatik çıkarma saldırılarını yavaşlatır ve pahalılaştırır.

## Yaygın Hatalar

**"Parolayı hash'liyorum, o yüzden güvendeyim" yanılgısı.** Authentication bypass senaryosunda parola hiç karşılaştırılmaz; `$ne` operatörü karşılaştırmayı baypas eder. Hash'leme çalınan veritabanını korur ama enjeksiyonu engellemez. İkisi farklı savunma katmanlarıdır.

**Sadece JSON body'yi düşünmek.** Geliştiriciler çoğu zaman `req.body`'yi temizler ama `req.query` ve `req.params`'ı unutur. Oysa `qs` ayrıştırıcısı URL parametrelerinden de nesne üretebilir. Sanitization ve doğrulama üç kaynağı da kapsamalıdır.

**Sadece SQL Injection düşünüp NoSQL'i unutmak.** Bir takım MongoDB kullandığı için SQL Injection'dan güvende olduğunu sanabilir. Enjeksiyon riski ortadan kalkmaz, yalnızca **biçim değiştirir**. Klasik WAF kuralları da çoğunlukla SQL sözdizimine odaklıdır ve `{"$ne": null}` gibi payload'ları kaçırabilir.

**Denylist (kara liste) ile yetinmek.** "`$ne` ve `$gt` kelimelerini engelleyeyim" gibi yaklaşımlar eksiktir; onlarca operatör vardır, kodlama ve büyük/küçük harf varyasyonları filtreyi atlatabilir. Doğru yaklaşım allowlist (izin listesi) mantığıdır: her alanın beklenen tipini/biçimini tanımlayıp geri kalan her şeyi reddetmek.

**İç içe geçmiş yapıları göz ardı etmek.** Payload derinlerde `{ "a": { "b": { "$ne": null } } }` biçiminde saklanabilir. Yüzeysel bir tip kontrolü bunu kaçırır; doğrulama özyinelemeli (recursive) veya şema tabanlı olmalıdır.

**Prototype pollution ile karıştırıp/ihmal etmek.** JavaScript'te `__proto__` gibi anahtarların kullanıcı girdisiyle nesnelere işlenmesi ayrı ama akraba bir sınıf zafiyettir. Sanitize kütüphanesi seçerken hem operatör anahtarlarını hem de prototype kirlenmesi vektörlerini ele alıp almadığını kontrol edin.

## En İyi Pratikler

Sağlam bir savunma duruşu şu ilkelerin birleşiminden doğar. Öncelikle **girdiye asla güvenme** ilkesini içselleştirin: HTTP'den gelen her şey (body, query, params, header) potansiyel olarak yapısal ve düşmancadır. İkinci olarak, doğrulamayı **allowlist mantığıyla ve mümkünse merkezî bir şema katmanıyla** yapın; her uçta tek tek if-kontrolü yazmak yerine Zod/Joi/Ajv gibi araçlarla girdiyi kapıda kesin biçime sokun. Üçüncü olarak, **tip zorlamasını** temel savunma sayın; string beklenen yer string olsun, operatör nesneleri veri alanına asla ulaşmasın.

Bunların üzerine derinlemesine savunma ekleyin: operatör anahtarlarını temizleyen bir middleware, sunucu tarafı JavaScript'in (`$where` vb.) kapatılması, veritabanı kullanıcısına en az yetki, ve hata mesajlarının genelleştirilmesiyle blind çıkarmanın zorlaştırılması. Kimlik doğrulama uçlarına rate limiting ve anomali tespiti koyun; regex tabanlı sızdırma denemeleri çok sayıda benzer istekle kendini belli eder.

Süreç tarafında, güvenlik testlerinizi otomatikleştirin: NoSQL enjeksiyon senaryolarını (operatör enjeksiyonu, blind regex çıkarma, query parametre zorlaması) düzenli olarak deneyen testler yazın veya bu yüzeyi tarayan araçları CI hattınıza dâhil edin. Bağımlılıklarınızı ve MongoDB sürücünüzü güncel tutun; sürücü ve framework'lerin varsayılan davranışları zamanla güvenli yönde değişir. Son olarak, kod incelemelerinde şu tek soruyu bir alışkanlık hâline getirin: "Bu değer sorguya girmeden önce tipi ve biçimi doğrulandı mı?" Çoğu NoSQL Injection, bu sorunun cevabının "hayır" olduğu yerlerde yaşar.

## Özet

NoSQL Injection, kökü SQL Injection ile aynı olan ama biçimi farklı bir zafiyet ailesidir: veri ile sorgu yapısı arasındaki sınırın erimesi. MongoDB özelinde bu, kullanıcı girdisinin string yerine operatör içeren bir nesneye dönüştürülmesiyle (`{"$ne": null}`, `{"$regex": ...}`) gerçekleşir ve kimlik doğrulama atlatmadan kör veri sızdırmaya kadar geniş bir etki yelpazesi doğurur. Kök neden, dinamik tipli dillerde ve JSON tabanlı API'lerde girdi tipinin belirsiz kalmasıdır. Savunmanın merkezinde bu belirsizliği ortadan kaldırmak vardır: allowlist tabanlı şema doğrulaması ve tip zorlaması. Bunun üzerine operatör temizleme, sunucu tarafı JavaScript'in kapatılması, en az yetki ve blind çıkarmayı zorlaştıran önlemler eklendiğinde, çok katmanlı ve dayanıklı bir savunma ortaya çıkar.
