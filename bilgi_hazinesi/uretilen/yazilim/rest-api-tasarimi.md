# REST API Tasarımı: Kaynak Modelleme, Method Semantiği, Versiyonlama ve HATEOAS

## Giriş ve Tanım

REST (Representational State Transfer), Roy Fielding'in 2000 yılındaki doktora tezinde tanımladığı, dağıtık hipermedya sistemleri için bir mimari stildir. Dikkat edilmesi gereken ilk nokta şudur: REST bir protokol ya da standart değildir; bir dizi **mimari kısıt** (architectural constraint) bütünüdür. HTTP nasıl kullanılacağını dikte eden katı kurallar getirmez; bunun yerine, sistemin belirli özelliklere (ölçeklenebilirlik, gevşek bağlılık, önbelleklenebilirlik) sahip olması için uyulması gereken ilkeler önerir.

Bu ayrım kritiktir çünkü pratikte "REST API" olarak adlandırılan sistemlerin büyük çoğunluğu aslında Fielding'in tanımladığı anlamda tam REST değildir. Fielding'in kendisi de bu kavram kaymasından açıkça rahatsızlık duymuş ve HTTP üzerinden JSON döndüren her arayüzün REST olmadığını vurgulamıştır. Bu makale, hem yaygın pratiği hem de teorik doğruyu bir arada, "neden" sorusunu sürekli sorarak ele alacaktır.

REST'in dayandığı temel kısıtları hatırlamak, sonraki her kararın kökünü anlamak için gereklidir:

- **Client-Server**: Sunum katmanı ile veri katmanının ayrılması.
- **Stateless (durumsuzluk)**: Her istek, kendini anlamak için gereken tüm bağlamı taşır; sunucu istekler arasında client durumu (session) tutmaz.
- **Cacheable (önbelleklenebilirlik)**: Yanıtlar kendini önbelleklenebilir olarak işaretleyebilmelidir.
- **Uniform Interface (tekdüze arayüz)**: REST'i diğer stillerden ayıran çekirdek kısıt. Kaynakların tanımlanması, temsiller üzerinden manipülasyonu, self-descriptive mesajlar ve HATEOAS bu başlığın alt bileşenleridir.
- **Layered System (katmanlı sistem)**: Client, doğrudan sunucuya mı yoksa bir ara katmana (load balancer, proxy, cache) mı bağlandığını bilemez.
- **Code-on-Demand (isteğe bağlı, opsiyonel)**: Sunucu, client'a çalıştırılabilir kod gönderebilir.

Bu kısıtların neden konulduğunu anlamadan, tasarım kararları ezbere kurala dönüşür. Örneğin durumsuzluğun sebebi keyfi değildir: her isteğin bağımsız olması, isteklerin herhangi bir sunucu örneğine (instance) yönlendirilebilmesini sağlar, bu da yatay ölçeklemeyi (horizontal scaling) mümkün kılar. Session'ı sunucuda tutsaydınız, aynı kullanıcının isteklerini hep aynı sunucuya yönlendirmek (sticky session) zorunda kalır, elastik ölçeklemeyi kaybederdiniz.

## Kaynak Modelleme

### Kaynak Nedir ve Neden Merkezdedir

REST'te temel soyutlama **kaynaktır** (resource). Kaynak, adlandırılabilen ve bir URI ile referans verilebilen her türlü bilgidir: bir kullanıcı, bir sipariş, bir belge, hatta "bugünün hava durumu" gibi bir kavram bile kaynak olabilir. Kritik bir ayrım vardır: kaynak, o kaynağın herhangi bir andaki somut temsili (representation) değildir. Aynı `siparis/42` kaynağı, istemcinin talebine göre JSON, XML ya da HTML olarak temsil edilebilir. Kaynak soyut kavramdır; temsil onun aktarılan halidir.

Bu ayrım neden önemli? Çünkü REST'in tekdüze arayüz kısıtının kalbi budur. İstemci kaynağı doğrudan değiştirmez; kaynağın bir temsilini alır, üzerinde değişiklik yapar ve bu değiştirilmiş temsili sunucuya geri gönderir. Sunucu bu temsili yorumlayıp kendi iç durumunu günceller. İstemci, sunucunun veriyi nasıl sakladığını (veritabanı şeması, dosya sistemi) hiç bilmez ve bilmemelidir. Bu, gevşek bağlılığın (loose coupling) somut halidir.

### İsimlendirme: Neden İsimler, Fiiller Değil

Kaynak modellemenin en temel kuralı: URI'lar **isim** (noun) içermeli, **fiil** (verb) içermemelidir. Bunun kök nedeni, fiillerin zaten HTTP method'ları tarafından karşılanmasıdır. Aşağıdaki karşılaştırma bunu netleştirir:

```
Yanlış (fiil URI'da):
  GET  /getUser?id=42
  POST /createUser
  POST /deleteUser?id=42
  POST /updateUserEmail?id=42

Doğru (isim + method semantiği):
  GET    /users/42
  POST   /users
  DELETE /users/42
  PATCH  /users/42
```

Fiilleri URI'ya koyduğunuzda, sonsuz sayıda endpoint üretme yolunu açarsınız (`getUser`, `getUserWithOrders`, `getActiveUser`...) ve tekdüzeliği kaybedersiniz. HTTP method'larıyla tanımlanan sınırlı ve iyi anlaşılmış eylem kümesi (GET, POST, PUT, PATCH, DELETE), her kaynağa aynı şekilde uygulanabildiğinde, arayüz öngörülebilir ve öğrenilebilir hale gelir. Bir geliştirici `GET /users/42`'nin ne yaptığını bildiğinde, `GET /orders/17`'nin de ne yapacağını tahmin edebilir.

### Koleksiyonlar ve Hiyerarşi

Kaynaklar genellikle iki biçimde gelir: **koleksiyon** (collection) ve **tekil öğe** (item). `/users` bir koleksiyondur; `/users/42` o koleksiyonun bir üyesidir. Bu ayrım method semantiğini doğrudan etkiler:

- `POST /users` → koleksiyona yeni bir üye ekler (yeni bir ID sunucu tarafından üretilir).
- `GET /users` → koleksiyonu listeler.
- `GET /users/42` → tek bir üyeyi getirir.

İlişkiler için iç içe (nested) yollar kullanılabilir: `/users/42/orders`, "42 numaralı kullanıcının siparişleri" anlamına gelir. Ancak burada yaygın bir tuzak vardır: **aşırı iç içe geçme** (over-nesting). `/users/42/orders/17/items/3/product/reviews/9` gibi bir yol bakım kabusudur. Pratik kural, iç içe geçmeyi bir, en fazla iki seviyede tutmak, derin ilişkiler için kaynağın kendi kök yolundan erişim sağlamaktır. `/orders/17` doğrudan erişilebiliyorsa, `/users/42/orders/17`'ye gerek yoktur; `17` numaralı sipariş zaten tekildir.

İç içe geçmenin ne zaman anlamlı olduğuna karar verirken sorulacak soru şudur: "Alt kaynak, üst kaynak olmadan var olabilir mi ve tekil olarak mı erişilir?" Bir siparişin satır kalemleri (`line items`) genellikle o sipariş bağlamında anlamlıdır, dolayısıyla `/orders/17/items` mantıklıdır. Ama ürün, birçok siparişte geçtiği için bağımsız bir kök kaynaktır: `/products/88`.

### Filtreleme, Sıralama ve Sayfalama

Bir koleksiyonu daraltmak için query parametreleri kullanılır, yeni endpoint'ler değil:

```
GET /users?status=active&role=admin&sort=-created_at&page=2&page_size=50
```

Buradaki mantık şudur: `status=active`, koleksiyonun bir alt kümesini seçer ama yeni bir kaynak türü yaratmaz. Aktif kullanıcılar ayrı bir kaynak değil, `users` koleksiyonunun filtrelenmiş bir görünümüdür. `sort=-created_at` ifadesindeki eksi işareti azalan sıralama için yaygın bir konvansiyondur (standart değil, konvansiyon).

Sayfalama iki temel yaklaşımla yapılır ve aralarındaki fark önemlidir:

- **Offset/limit tabanlı** (`page` ve `page_size` ya da `offset` ve `limit`): Uygulaması basittir ama büyük veri kümelerinde derin sayfalarda performans düşer, ayrıca veri araya eklenirse/silinirse kayan sonuç (page drift) sorunu yaşanır. Aynı öğe iki farklı sayfada görünebilir ya da tamamen atlanabilir.
- **Cursor (keyset) tabanlı**: Bir sıralama anahtarına (örneğin timestamp + id) dayanarak "şu noktadan sonrasını getir" mantığıyla çalışır. Kayan sonuç sorununa dayanıklıdır ve büyük veri kümelerinde tutarlı performans verir. Bedeli, rastgele sayfaya atlamanın (jump to page 50) mümkün olmamasıdır.

Sonsuz kaydırma (infinite scroll) yapan ve tutarlılık isteyen sistemlerde cursor tabanlı sayfalama tercih edilir; sayfa numaralarıyla gezinen klasik yönetim panellerinde offset yeterli olabilir. Karar veri hacmine ve erişim desenine bağlıdır.

## Method Semantiği

### Güvenli ve İdempotent Kavramları

HTTP method'larını doğru kullanmanın temeli iki özelliktir: **safe** (güvenli) ve **idempotent** (etkisiz eleman özelliği). Bu iki kavramı karıştırmak, yaygın hataların kaynağıdır.

**Safe**, method'un sunucu durumunu değiştirmemesi anlamına gelir. GET, HEAD ve OPTIONS güvenlidir. Bir GET isteği hiçbir yan etki üretmemelidir. Bunun pratik sonucu büyüktür: proxy'ler, arama motoru botları ve tarayıcı önyükleyicileri (prefetcher) güvenli methodları serbestçe, defalarca çağırabilir. Eğer `GET /users/42/delete` gibi bir tasarım yapıp GET ile silme işlemi yaptırırsanız, bir web crawler sitenizde gezinirken tüm kayıtlarınızı silebilir. Bu teorik değil, gerçekte yaşanmış bir felakettir.

**Idempotent**, aynı isteğin bir kez ya da defalarca gönderilmesinin sunucu durumu üzerindeki etkisinin aynı olması demektir. Dikkat: yanıtın aynı olması gerekmez, sunucudaki *son durumun* aynı olması gerekir. GET, PUT, DELETE ve HEAD idempotenttir. Neden önemli? Ağ güvenilmezdir. Bir istek gönderdiniz, yanıt gelmeden bağlantı koptu. İstek sunucuya ulaştı mı, ulaşmadı mı bilmiyorsunuz. Method idempotent ise, çekinmeden yeniden gönderebilirsiniz; iki kez işlense bile sonuç değişmez. Idempotent değilse (klasik örnek POST ile ödeme), yeniden gönderim tehlikelidir çünkü müşteriden iki kez para çekebilirsiniz.

### Method'ların Doğru Kullanımı

**GET** — Kaynağın temsilini getirir. Safe ve idempotent. Request body içermemelidir (bazı sunucular gövdeli GET'i reddeder). Filtreleme ve sayfalama query parametreleriyle yapılır.

**POST** — En esnek ve en sık yanlış anlaşılan method. Ne safe ne idempotent. Temel kullanımı bir koleksiyona yeni kaynak eklemektir: `POST /orders`. Sunucu yeni ID'yi üretir ve genellikle `201 Created` durum kodu ile birlikte yeni kaynağın konumunu `Location` header'ında döner. POST aynı zamanda RESTful kalıba tam oturmayan işlemler için de kullanılır (örneğin bir hesaplama tetikleme); bu, saf REST'ten sapma olsa da pragmatik gerçekliktir.

**PUT** — Kaynağın *tamamını* değiştirir ya da belirtilen URI'da yoksa oluşturur. İdempotenttir çünkü aynı temsili on kez göndermek, sonuçta kaynağı hep aynı hale getirir. Kritik nokta: PUT bir *tam değiştirmedir* (full replacement). Gönderdiğiniz gövdede olmayan alanlar, sunucuda silinmeli ya da varsayılana dönmelidir. PUT'u kısmi güncelleme için kullanmak yaygın bir hatadır.

**PATCH** — Kaynağın *kısmi* güncellemesi. Sadece değişen alanları gönderirsiniz. PATCH garantili olarak idempotent değildir; bu method'un semantiği gönderilen patch belgesinin biçimine bağlıdır. Örneğin JSON Patch ile "şu diziye bir eleman ekle" işlemi idempotent değildir. Bu yüzden PATCH ile idempotency gerektiğinde ek önlem (aşağıda anlatılan idempotency key) alınır. Kısmi güncellemenin iki yaygın gösterimi vardır: JSON Merge Patch (basit, ama null ile "sil" arasında belirsizlik taşır) ve JSON Patch (daha ifade gücü yüksek, operasyon tabanlı).

**DELETE** — Kaynağı siler. İdempotenttir: bir kaynağı silmek, sonra tekrar silmeye çalışmak, sunucu durumunu değiştirmez (kaynak zaten yok). İlk çağrı `200` ya da `204`, ikinci çağrı `404` dönebilir; durum kodları farklı olsa da idempotency sunucu durumuyla ilgilidir, yanıt koduyla değil.

### Durum Kodlarının Anlamı

Durum kodları sözleşmenin (contract) bir parçasıdır; süs değildir. Doğru kod, istemcinin doğru davranmasını sağlar. Sınıfların anlamı:

- **2xx** — Başarı. `200 OK`, `201 Created` (yeni kaynak, `Location` header ile), `202 Accepted` (işlem kuyruğa alındı, henüz tamamlanmadı — asenkron işlemler için), `204 No Content` (başarılı ama gövde yok).
- **3xx** — Yönlendirme. `304 Not Modified` (önbellek geçerli, aşağıda ETag ile ilişkili).
- **4xx** — İstemci hatası. `400 Bad Request` (bozuk istek), `401 Unauthorized` (kimlik doğrulama eksik — aslında "unauthenticated" demek, isimlendirme tarihsel bir talihsizlik), `403 Forbidden` (kimlik var ama yetki yok), `404 Not Found`, `409 Conflict` (durum çakışması, örneğin optimistic concurrency ihlali), `422 Unprocessable Entity` (biçim doğru ama semantik olarak geçersiz), `429 Too Many Requests` (rate limit).
- **5xx** — Sunucu hatası. `500 Internal Server Error`, `503 Service Unavailable`.

En kritik ayrım `401` ile `403` arasındadır: `401`, "kim olduğunu bilmiyorum, kimliğini kanıtla" der; `403`, "kim olduğunu biliyorum ama bunu yapmana izin yok" der. Bunları karıştırmak, istemci tarafında yanlış hata akışlarına (örneğin gereksiz yere tekrar login'e yönlendirme) yol açar.

`4xx` ile `5xx` ayrımı da önemlidir çünkü otomatik yeniden deneme (retry) mantığını belirler: `5xx` ve `429` genellikle yeniden denenebilir (geçici sorun); `400` ya da `422` yeniden denenmemelidir çünkü istek zaten hatalıdır, tekrar göndermek aynı hatayı verir.

## Versiyonlama

### Neden Versiyonlamaya İhtiyaç Var

Bir API yayınlandığı an, onu tüketen istemciler üzerinde bir sözleşme oluşur. Bu istemcilerin çoğu sizin kontrolünüzde değildir: mobil uygulamalar kullanıcıların cihazında aylarca güncellenmeden kalır, üçüncü taraf entegrasyonlar sizin ne zaman değişiklik yapacağınızı bilmez. Bu nedenle **geriye dönük uyumluluğu bozan** (breaking change) her değişiklik, mevcut istemcileri kırar. Versiyonlama, bu kaçınılmaz evrimi yönetmenin yoludur.

Önce ayrım yapmak gerekir. Bozan olmayan (non-breaking) değişiklikler versiyon gerektirmez ve serbestçe eklenebilir: yeni bir opsiyonel alan eklemek, yeni bir endpoint eklemek, yeni bir opsiyonel query parametresi eklemek. Bozan değişiklikler ise versiyon gerektirir: bir alanı kaldırmak ya da yeniden adlandırmak, bir alanın tipini değiştirmek, zorunlu bir parametre eklemek, bir yanıtın yapısını değiştirmek, bir endpoint'i kaldırmak. Bu ilkenin adı **tolerant reader / robust behavior** ilkesidir: istemciler bilmedikleri alanları görmezden gelecek şekilde yazılırsa, sunucu güvenle ekleme yapabilir.

### Versiyonlama Stratejileri ve Getirileri

**URI path versiyonlama** — En yaygın ve en görünür yöntem: `/v1/users`, `/v2/users`. Avantajı çok açıktır; bir bağlantıya bakan herkes hangi versiyonu kullandığını görür, tarayıcıda test etmek kolaydır, cache anahtarı doğal olarak versiyonu içerir. Dezavantajı, saf REST purist bakış açısına aykırı olmasıdır: aynı kavramsal kaynak (`kullanıcı 42`) iki farklı URI'ya (`/v1/users/42` ve `/v2/users/42`) sahip olur, oysa REST'te bir kaynağın tek bir kanonik tanımlayıcısı olmalıdır. Bu teorik itiraza rağmen, pratikliği nedeniyle en sık tercih edilen yöntemdir.

**Header tabanlı / content negotiation versiyonlama** — Versiyon, `Accept` header'ı içinde media type ile taşınır (örneğin özel bir media type ile sürüm belirtme). Teorik olarak daha "temizdir" çünkü URI aynı kalır, versiyon temsilin bir özelliği olarak ele alınır. Dezavantajı, keşfedilebilirliğin (discoverability) düşük olması ve tarayıcıdan basit test yapmanın zorlaşmasıdır; header ayarlamak gerekir.

**Query parametresi versiyonlama** — `/users?version=2`. Basit ama cache davranışını karmaşıklaştırabilir ve genellikle daha az tercih edilir.

Hangisini seçerseniz seçin, asıl mesele tutarlılıktır. Sık yapılan bir hata, versiyonu her endpoint'e ayrı ayrı, tutarsız biçimde uygulamaktır. Bir diğer önemli karar, versiyonlamayı **her küçük değişiklikte değil, yalnızca bozan değişikliklerde** artırmaktır. Sürüm numaralarını gereksiz yere şişirmek, hem sizi hem de istemcilerinizi yorar.

### Versiyon Yaşam Döngüsü

Versiyonlamanın gözden kaçan boyutu, **kullanımdan kaldırma** (deprecation) sürecidir. Yeni versiyon çıkarmak kolaydır; eski versiyondan kurtulmak zordur. İyi bir uygulama şunları içerir: eski versiyonun ne zaman destekten çıkacağını önceden duyurmak, yanıtlarda uyarı sinyalleri (bir deprecation header ya da yanıt gövdesinde uyarı) göndermek, kullanıcılara geçiş için makul bir süre tanımak ve eski versiyonun gerçek kullanım metriklerini izleyerek gerçekten kimsenin kullanmadığından emin olduktan sonra kapatmak. Sonsuza kadar her versiyonu desteklemek, bakım maliyetini kartopu gibi büyütür; bu yüzden net bir yaşam döngüsü politikası, versiyonlama stratejisinin ayrılmaz bir parçasıdır.

## HATEOAS

### Kavram ve Kök Neden

HATEOAS (Hypermedia As The Engine Of Application State), tekdüze arayüz kısıtının en çok ihmal edilen ama Fielding'e göre REST'i REST yapan bileşenidir. Fielding açıkça, hipermedya kontrolleri içermeyen bir API'nin REST olarak adlandırılamayacağını yazmıştır. Kavramın özü şudur: istemci, uygulamanın durumları arasında geçişi, sunucunun yanıtlarda gönderdiği **bağlantılar** (links) aracılığıyla yapmalıdır; endpoint yollarını önceden bilerek (hardcode ederek) değil.

Somut bir örnekle açalım. Bir sipariş kaynağı düşünün:

```json
{
  "id": 17,
  "durum": "beklemede",
  "toplam": 250.00,
  "_links": {
    "self":   { "href": "/orders/17" },
    "iptal":  { "href": "/orders/17/cancel", "method": "POST" },
    "odeme":  { "href": "/orders/17/payment", "method": "POST" }
  }
}
```

Burada istemci, siparişin iptal edilebileceğini ya da ödenebileceğini, kendi içine gömdüğü bir kuraldan değil, sunucunun sunduğu bağlantılardan öğrenir. Sipariş `"kargolandı"` durumuna geçtiğinde, sunucu artık `iptal` bağlantısını göndermez. İstemcinin "iptal butonunu göster/gizle" mantığını yeniden yazmasına gerek kalmaz; sunucu, mevcut duruma göre hangi eylemlerin mümkün olduğunu bildiren tek otorite olur.

### HATEOAS'ın Vaat Ettiği Fayda ve Gerçeklik

HATEOAS'ın vaadi güçlüdür: istemci ile sunucu arasındaki bağlılığı azaltır. İstemci URI yapılarını değil, bağlantı ilişkilerini (link relations, örneğin `next`, `self`, `cancel`) bilir. Sunucu URI'larını yeniden düzenlese bile, istemci hâlâ `next` bağlantısını takip edeceği için çalışmaya devam eder. Bu, teorik olarak sunucunun bağımsız evrimini mümkün kılar.

Ancak dürüst olmak gerekir: HATEOAS pratikte en az uygulanan REST bileşenidir ve bunun sebepleri vardır. Çoğu istemci, bağlantıları takip edecek kadar genel (generic) yazılmaz; geliştiriciler `_links.iptal.href`'i takip etmek yerine URI'yı yine de kendi kodlarına gömme eğilimindedir, bu da HATEOAS'ın sağladığı gevşek bağlılığı boşa çıkarır. Faydası, gerçekten hipermedya-güdümlü genel istemcilerin (örneğin bir API tarayıcısı, ya da sunucunun sık evrildiği uzun ömürlü entegrasyonlar) olduğu durumlarda ortaya çıkar. Basit, tek bir ekip tarafından kontrol edilen dahili API'larda HATEOAS'ın maliyeti faydasını aşabilir.

Bunu söylemek önemlidir çünkü kör bir "her API HATEOAS içermeli" tavsiyesi, ekiplerin hiç kullanılmayacak bağlantı yapıları üretip enerji harcamasına yol açar. Doğru yaklaşım, HATEOAS'ı bir amaç değil bir araç olarak görmek: istemci-sunucu bağımsız evrimine gerçekten ihtiyacınız varsa değerlidir; yoksa daha basit tutmak makul bir mühendislik kararıdır. Hipermedya biçimlerini standartlaştırmak için HAL, JSON:API ve Siren gibi formatlar geliştirilmiştir; bunlardan birini seçmek, kendi ad-hoc bağlantı yapınızı icat etmekten daha sürdürülebilirdir.

## Yaygın Hatalar

Deneyimle görülen, tekrar eden hatalar şunlardır:

**Fiil tabanlı URI kullanmak** — `/createOrder`, `/getOrderById` gibi. Bu, method semantiğini yok sayar ve endpoint sayısını patlatır. Çözüm, isimleri kaynak, fiilleri HTTP method'u olarak ele almaktır.

**Yanlış durum kodu döndürmek** — En sinsi hata, her şeyi `200 OK` ile dönüp hatayı yanıt gövdesinde `{"error": true}` gibi bir alanla belirtmektir. Bu, HTTP'nin sözleşme katmanını görmezden gelir; ara katmanlar (proxy, monitoring) isteğin başarılı sandığı için hataları fark etmez, otomatik retry mantığı bozulur.

**GET ile durum değiştirmek** — Yukarıda anlatılan crawler felaketinin kaynağı. GET her zaman safe kalmalıdır.

**PUT ile kısmi güncelleme yapmak** — PUT tam değiştirme olduğundan, gönderilmeyen alanlar kaybolur. Kısmi güncelleme için PATCH kullanılmalıdır.

**Durumsuzluğu ihlal etmek** — Sunucuda istek zincirine bağlı geçici durum tutmak (örneğin çok adımlı bir işlemin ara adımlarını sunucu belleğinde saklamak). Bu, yatay ölçeklemeyi kırar. Gereken durum ya istemcide tutulmalı ya da paylaşılan bir kalıcı katmana (veritabanı, dağıtık cache) yazılmalıdır.

**Idempotency'yi gözardı etmek** — Özellikle ödeme gibi POST işlemlerinde. Ağ kesildiğinde istemci yeniden dener ve çifte işlem oluşur. Çözüm, istemcinin ürettiği bir **idempotency key**'i (genellikle bir header'da) sunucuya göndermesi; sunucunun aynı anahtarla gelen ikinci isteği yeni işlem yapmadan ilk sonucu döndürmesidir.

**Aşırı iç içe geçmiş URI'lar** — Derin hiyerarşiler bakımı zorlaştırır ve URI'ları kırılgan yapar.

**Hata yanıtlarını tutarsız biçimlendirmek** — Her endpoint farklı bir hata gövdesi döndürdüğünde, istemci genel bir hata işleyici yazamaz. Tutarlı, makine tarafından okunabilir bir hata biçimi (örneğin bir tür kodu, insan-okunur mesaj ve isteğe bağlı ayrıntı alanları içeren standart bir yapı) benimsemek gerekir. Problem Details for HTTP APIs (RFC 7807) gibi bir standart, bunu tekerleği yeniden icat etmeden sağlar.

## En İyi Pratikler

**Tutarlılık her şeyden önce gelir.** İsimlendirme (tekil mi çoğul mu, snake_case mi camelCase mi), sayfalama parametreleri, hata biçimi, versiyonlama şeması, tarih formatı (ISO 8601 ve UTC kullanmak güçlü bir varsayılandır) tüm API boyunca aynı olmalıdır. Tutarlı bir API, keşfedilebilir ve öğrenilebilir bir API'dir. Öngörülebilirlik, iyi API tasarımının en değerli özelliğidir.

**Önbelleklemeyi ciddiye alın.** GET yanıtlarına uygun `Cache-Control` ve `ETag` header'ları eklemek, hem performansı hem de eşzamanlılık denetimini iyileştirir. ETag ile birlikte koşullu istekler (`If-None-Match` ile önbellek doğrulama, `If-Match` ile optimistic concurrency) kullanmak, hem gereksiz veri transferini önler hem de "kayıp güncelleme" (lost update) problemini çözer: iki istemci aynı kaynağı aynı anda güncellemeye kalktığında, eski ETag ile gelen istek `412 Precondition Failed` alır.

**Hataları makine ve insan için birlikte tasarlayın.** İyi bir hata yanıtı, hem programın dallanabileceği kararlı bir kod hem de geliştiricinin log'da okuyacağı açıklayıcı bir mesaj içerir. Hassas bilgi (stack trace, iç sistem detayları) asla istemciye sızmamalıdır.

**Güvenliği tasarımın parçası yapın.** Kimlik doğrulama (authentication) ile yetkilendirme (authorization) ayrı kavramlardır ve `401` / `403` ayrımıyla doğru yansıtılmalıdır. Rate limiting uygulayın ve `429` ile birlikte istemciye ne zaman tekrar deneyebileceğini söyleyen bir `Retry-After` sinyali verin. TLS zorunlu olmalıdır; hassas veri düz metin üzerinden asla taşınmamalıdır.

**Dokümantasyonu makine-okunur bir sözleşmeyle destekleyin.** OpenAPI (eski adıyla Swagger) gibi bir spesifikasyon, hem insan dokümantasyonu hem de istemci/sunucu kod üretimi, test ve doğrulama için tek kaynak (single source of truth) sağlar. Sözleşme-öncelikli (contract-first) tasarım, ekiplerin API üzerinde uzlaşmasını implementasyondan önce sağlar.

**Asenkron işlemleri dürüstçe modelleyin.** Uzun süren bir işlem senkron bir yanıtla tamamlanamayacaksa, `202 Accepted` dönüp istemciye işlemin durumunu sorgulayabileceği bir durum kaynağı (status resource) bağlantısı verin. İstemciyi dakikalarca bekletmek yerine, işlemi bir kaynağa dönüştürüp durumunu takip edilebilir kılmak REST'in ruhuna uygundur.

**Pragmatik olun, purist değil.** Bu makale boyunca teorik doğruyla pratik gerçeklik arasındaki gerilime dikkat çektik. Gerçek dünyadaki neredeyse hiçbir API tam REST değildir ve bu her zaman bir kusur değildir. Richardson Maturity Model, bir API'nin ne kadar RESTful olduğunu seviyeler halinde tanımlar (kaynak kullanımı, HTTP method'ları, HATEOAS). Amaç en yüksek seviyeye ulaşmak değil, sisteminizin ihtiyaçlarına uygun seviyede bilinçli bir karar vermektir. İyi mühendislik, kuralları ezbere uygulamak değil, her kuralın *neden* var olduğunu anlayıp bağlama göre doğru dengeyi kurmaktır.

## Sonuç

REST API tasarımı, yüzeyde basit görünen ama derinlemesine bakıldığında birbirine bağlı ilkelerden oluşan bir disiplindir. Kaynak modelleme, sistemin sözlüğünü kurar; method semantiği, o sözlüğe uygulanan eylemleri tekdüze ve öngörülebilir kılar; versiyonlama, kaçınılmaz evrimi istemcileri kırmadan yönetir; HATEOAS ise -uygulandığında- istemci ile sunucunun bağımsız gelişimini mümkün kılar. Bu bileşenlerin hepsinin altında yatan ortak amaç aynıdır: gevşek bağlı, ölçeklenebilir, öngörülebilir ve zaman içinde bakımı sürdürülebilir sistemler kurmak. Her tasarım kararında "bu kısıt neden var ve benim bağlamımda ne kazandırıyor?" sorusunu sormak, sizi ezberci bir uygulayıcıdan bilinçli bir tasarımcıya dönüştürür.
