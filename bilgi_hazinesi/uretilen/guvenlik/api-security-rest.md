# REST API Güvenliği ve Mass Assignment

## Giriş ve Kapsam

Modern uygulamaların çoğu artık monolitik yapılardan çıkıp, birbirleriyle REST API üzerinden konuşan servislere dönüştü. Bu mimari değişim, saldırı yüzeyini de köklü biçimde değiştirdi. Klasik web güvenliğinde tarayıcı ile sunucu arasındaki HTML sayfaları korunurken, API güvenliğinde asıl korunması gereken şey doğrudan iş mantığına (business logic) ve veri modeline açılan uç noktalardır. API'ler tasarımı gereği makine tarafından tüketilmek üzere yapılmıştır; bu da bir saldırganın istekleri otomatikleştirmesini, milyonlarca varyasyonu denemesini ve tarayıcı katmanının sağladığı hiçbir "görsel engele" takılmadan doğrudan endpoint ile konuşmasını kolaylaştırır.

Bu makale, OWASP API Security Top 10 çerçevesini merkeze alarak dört kritik konuyu derinlemesine ele alır: **aşırı veri ifşası (excessive data exposure)**, **rate limiting eksikliği**, **mass assignment** ve bunların altında yatan yetkilendirme ve tasarım kök nedenleri. Amacımız kuru bir kontrol listesi vermek değil; her bir zafiyetin *neden* ortaya çıktığını, saldırganın onu *nasıl* sömürdüğünü ve savunmanın *hangi katmanda* kurulması gerektiğini akıl yürüterek göstermektir.

## OWASP API Security Top 10: Neden Ayrı Bir Liste Var?

OWASP, geleneksel Web Application Top 10 listesinin yanında ayrı bir API Security Top 10 yayınlar. Bunun sebebi, API'lerdeki risklerin ağırlık merkezinin farklı olmasıdır. Web uygulamalarında XSS, CSRF gibi tarayıcı temelli saldırılar öne çıkarken, API dünyasında sorunların büyük çoğunluğu **yetkilendirme (authorization)** ekseninde toplanır.

Listenin en tepesinde tarihsel olarak **BOLA (Broken Object Level Authorization)** yer alır. Bunun hemen ardından **Broken Authentication**, **Broken Object Property Level Authorization** (ki mass assignment ve aşırı veri ifşası bu başlığın altında birleşmiştir), **Unrestricted Resource Consumption** (rate limit ve kaynak tüketimi) ve **Broken Function Level Authorization** gelir. Dikkat edilirse listenin belkemiği tek bir soruya indirgenebilir: *"Bu isteği yapan kişi, tam olarak bu nesneye, bu alana, bu fonksiyona erişme hakkına sahip mi?"*

Buradaki kök neden şudur: API geliştiricileri, uç noktayı yazarken çoğu zaman "kimlik doğrulanmış kullanıcı" ile "yetkili kullanıcı" kavramlarını karıştırır. Kullanıcının geçerli bir token taşıması, o kullanıcının istediği her nesneye erişebileceği anlamına gelmez. Ancak framework'ler kimlik doğrulamayı (authentication) kolayca hazır verirken, nesne düzeyinde yetkilendirmeyi (authorization) geliştiricinin *her endpoint'te elle* yazmasını bekler. İşte bu boşluk, listenin neredeyse tamamının kaynağıdır.

## Aşırı Veri İfşası (Excessive Data Exposure)

### Tanım

Aşırı veri ifşası, API'nin bir kaynağı döndürürken ihtiyaç duyulandan fazla alan (field) göndermesi durumudur. Sunucu, veritabanı nesnesini olduğu gibi serialize edip istemciye yollar; hangi alanların gösterileceği kararını istemci arayüzüne (client) bırakır. Kullanıcı arayüzü bu fazla alanları ekranda göstermese bile, ham API yanıtında bu veriler kelimenin tam anlamıyla açıkta durur.

### Kök Neden: Sorumluluğun Yanlış Katmana Kayması

Bu zafiyetin kök nedeni, filtreleme sorumluluğunun sunucudan istemciye kaymasıdır. Geliştirici, `return user;` gibi bir kod yazdığında, ORM veya serializer o kullanıcı nesnesinin *tüm* sütunlarını JSON'a çevirir. Bu; `passwordHash`, `resetToken`, `isAdmin`, `internalRiskScore`, `ssn`, `dateOfBirth` gibi arayüzde asla gösterilmeyen ama nesnede duran alanları da kapsar.

Neden bu kadar yaygın? Çünkü "nesneyi olduğu gibi döndürmek" en az kod yazılan, en hızlı geliştirilen yoldur. Bir DTO (Data Transfer Object) katmanı kurmak, her endpoint için hangi alanların dışarı çıkacağını açıkça tanımlamak ek emek ister. Zaman baskısı altında geliştirici "istemci zaten sadece adını gösteriyor" diyerek tüm nesneyi yollar. Sorun şu ki istemci güvenilir bir sınır değildir; saldırgan tarayıcının geliştirici konsolundaki Network sekmesinden ham yanıtı okuyabilir.

### Somut Örnek

Bir sosyal uygulamada profil endpoint'i düşünelim:

```
GET /api/v1/users/8842
```

Arayüz yalnızca ad, avatar ve biyografiyi gösterir. Ancak ham yanıt şöyle döner:

```json
{
  "id": 8842,
  "name": "Ayse Yilmaz",
  "avatar": "https://cdn.example/av/8842.jpg",
  "bio": "Yazilim gelistirici",
  "email": "ayse@example.com",
  "phone": "+90 5xx xxx xx xx",
  "passwordHash": "$2b$12$...",
  "isAdmin": false,
  "internalNotes": "VIP musteri, iade politikasi esnek",
  "lastLoginIp": "85.10.x.x"
}
```

Burada arayüz `email`, `phone`, `passwordHash`, `internalNotes` ve `lastLoginIp` alanlarını hiç göstermez, ama hepsi yanıtta mevcuttur. Saldırgan sadece uç noktayı çağırarak binlerce kullanıcının e-postasını ve telefonunu toplayabilir (harvesting).

### İstismar Mantığı

Saldırganın yaklaşımı sistematiktir. Önce bir endpoint'in ham yanıtını inceler, arayüzde görünmeyen "bonus" alanları not eder. `passwordHash` gibi bir alan varsa offline crackleme hedefi olur. `isAdmin` gibi bir boolean, sonraki adımda mass assignment denemesi için ipucudur. Ardından `id` parametresini otomatik döngüye alıp (BOLA ile birleştirerek) tüm kullanıcı tabanını çeker. Aşırı veri ifşası tek başına da tehlikelidir, ancak asıl gücü diğer zafiyetlerle birleştiğinde ortaya çıkar.

### Savunma

Temel prensip **açık beyaz liste (allowlist)** ile çıkış şeması tanımlamaktır. Nesneyi asla ham haliyle serialize etmeyin. Bunun yerine:

- Her yanıt için ayrı bir **response DTO / view model** tanımlayın ve yalnızca izin verilen alanları oraya kopyalayın. "Ne göstermeyeceğimi kara listeye alayım" değil, "ne göstereceğimi açıkça belirteyim" mantığı esastır; çünkü kara liste yaklaşımında yeni eklenen her sütun sessizce ifşa olur.
- Serializer katmanında (ör. çeşitli framework'lerdeki serializer/schema mekanizmaları) hangi alanların çıkacağını sabitleyin.
- Aynı nesnenin farklı roller için farklı görünümleri olduğunu kabul edin: bir kullanıcı kendi profilinde e-postasını görmeli, ama başkasının profilinde görmemelidir. Yetkiye göre alan seviyesinde filtreleme yapın.
- API yanıtlarını düzenli olarak denetleyin; gerçek trafik üzerinde hangi hassas alanların gittiğini tespit eden veri sınıflandırma araçları bu konuda yardımcı olur.

## Mass Assignment (Toplu Atama)

### Tanım

Mass assignment, bir API'nin istemciden gelen JSON gövdesini (request body) doğrudan bir nesneye veya veritabanı modeline otomatik olarak bağlamasıyla (binding) ortaya çıkan zafiyettir. Geliştirici yalnızca birkaç alanın güncellenmesini beklerken, saldırgan gövdeye beklenmeyen alanlar ekleyerek normalde değiştiremeyeceği özellikleri değiştirir. OWASP sınıflandırmasında bu, aşırı veri ifşası ile aynı çatı altında — nesne özelliği düzeyinde bozuk yetkilendirme (Broken Object Property Level Authorization) — yer alır. İkisi aynı madalyonun iki yüzüdür: biri *okuma* tarafında fazla veri sızdırır, diğeri *yazma* tarafında fazla veri kabul eder.

### Kök Neden: Kolaylık Uğruna Güven

Modern framework'ler geliştirici verimliliği için "gelen tüm alanları modele otomatik doldur" özelliği sunar. `user.update(request.body)` veya benzeri bir kalıp, gelen sözlüğü nesnenin özelliklerine tek satırda eşler. Bu son derece pratiktir ama örtük bir varsayım taşır: *istemcinin gönderdiği her alan meşrudur.*

Kök neden tam olarak burasıdır. İstemci güvenilir değildir. Geliştirici formda yalnızca `name` ve `bio` alanları olduğunu bildiği için gövdenin de sadece bunları içereceğini varsayar. Oysa saldırgan gövdeye elle `"isAdmin": true` veya `"role": "admin"` ya da `"balance": 999999` ekleyebilir. Framework bu alanı da körü körüne modele bağlarsa, saldırgan iş mantığının hiç öngörmediği bir yetki yükseltmesi (privilege escalation) gerçekleştirir.

### Somut Örnek

Bir kullanıcı profil güncelleme endpoint'i düşünelim. Beklenen istek:

```
PATCH /api/v1/users/me
Content-Type: application/json

{ "name": "Mehmet", "bio": "Muzisyen" }
```

Sunucu tarafında zafiyetli kod kavramsal olarak şöyledir:

```
kullanici = Kullanici.bul(mevcut_kullanici.id)
kullanici.tum_alanlari_guncelle(istek.govde)   # tehlikeli: koru koru baglama
kullanici.kaydet()
```

Saldırgan aynı endpoint'e şu gövdeyi gönderir:

```json
{
  "name": "Mehmet",
  "bio": "Muzisyen",
  "isAdmin": true,
  "accountBalance": 1000000,
  "emailVerified": true,
  "subscriptionTier": "enterprise"
}
```

`tum_alanlari_guncelle` gelen sözlüğü olduğu gibi işlerse, saldırgan kendisini yönetici yapmış, bakiyesini şişirmiş, e-posta doğrulamasını atlamış ve ücretli bir katmana bedava geçmiş olur. Bu alanların isimlerini nereden bildi? Çoğu zaman *aşırı veri ifşasından*: GET yanıtında `isAdmin` alanını görmüştü. İki zafiyetin birleşimi tam da bu yüzden ölümcüldür.

### İstismar Mantığı

Saldırganın adımları nettir. Önce keşif: nesnenin şemasını çıkarmak için GET yanıtlarını, API dokümantasyonunu (Swagger/OpenAPI) veya hata mesajlarını inceler. Hangi alanların hassas olduğunu (rol, bakiye, sahiplik, durum bayrakları) belirler. Sonra deneme: bu alanları update/create isteklerinin gövdesine ekleyip yanıtı ve sistem davranışını gözlemler. Alan sessizce güncellendiyse zafiyet doğrulanmıştır. Genellikle iç içe (nested) nesneler de denenir; `"user": {"role": "admin"}` gibi derin yapılar bazı naif binder'ları atlatabilir.

### Savunma

Savunmanın kalbi, girişte de çıkışta olduğu gibi **açık allowlist** kullanmaktır:

- **Input DTO / binding modeli** tanımlayın. Endpoint yalnızca `name` ve `bio` kabul ediyorsa, binding hedefi yalnızca bu iki alanı olan bir sınıf/şema olsun. Gövdedeki fazla alanlar ya yok sayılsın ya da açıkça reddedilsin.
- Framework'lerin sağladığı **"strong parameters" / allowlist / `[Bind]` benzeri** mekanizmaları kullanın. Ama bunları kara liste (blacklist) olarak değil beyaz liste olarak kurun; kara liste her yeni hassas alan eklendiğinde yeniden açık verir.
- Yetki gerektiren alanları (rol, bakiye, sahiplik) **hiçbir zaman** kullanıcı girdisiyle güncellenebilir yapmayın. Bu alanlar yalnızca ayrı, yetkilendirilmiş yönetim akışlarından değişmelidir.
- Domain modelinizi (veritabanı entity'si) doğrudan API sınırına açmayın. API katmanı ile veri katmanı arasına bir dönüşüm (mapping) koymak, mass assignment'ı yapısal olarak imkânsız hale getirir.
- Şema doğrulaması yapın: JSON Schema veya eşdeğeriyle "bilinmeyen alanlara izin verme" (`additionalProperties: false` mantığı) kuralını uygulayın.

## Rate Limiting ve Sınırsız Kaynak Tüketimi

### Tanım

Rate limiting, bir istemcinin belirli bir zaman diliminde yapabileceği istek sayısını sınırlama mekanizmasıdır. OWASP bunu daha geniş bir başlık olan **Unrestricted Resource Consumption** (Sınırsız Kaynak Tüketimi) altında ele alır; çünkü sorun yalnızca istek sayısı değil, aynı zamanda CPU, bellek, ağ bant genişliği, veritabanı bağlantısı ve üçüncü taraf servis maliyeti gibi *her türlü* kaynağın kontrolsüz tüketimidir.

### Kök Neden: "İyi Niyetli İstemci" Varsayımı

Rate limit eksikliğinin kök nedeni, API'nin istemcilerin makul davranacağını varsaymasıdır. Bir arayüz normalde saniyede bir login denemesi yaparken, otomatikleştirilmiş bir saldırgan saniyede binlerce deneme yapar. Sunucu her isteği eşit ciddiyetle işlerse, hem meşru olmayan trafiğe kaynak ayırır hem de bazı endpoint'lerin doğasında var olan asimetriyi göz ardı eder: bir istek çok ucuz (birkaç bayt gövde) ama sunucuya çok pahalı (ağır rapor üretimi, dosya işleme, e-posta gönderimi) olabilir. Bu asimetri, saldırganın az maliyetle büyük yük oluşturmasına imkân verir.

### Somut Örnekler ve İstismar Mantığı

**Credential stuffing ve brute force:** Rate limit olmayan bir login endpoint'i, saldırganın sızmış parola listelerini otomatik denemesine izin verir. Milyonlarca `email:parola` çiftini sırayla dener; sınır olmadığından hiçbir engelle karşılaşmaz.

**OTP / doğrulama kodu tahmini:** 4-6 haneli bir SMS kodu, saniyede binlerce deneme yapılabiliyorsa kaba kuvvetle kırılabilir. Buradaki savunma sadece rate limit değil, aynı zamanda kod başına deneme sayısını sınırlamak ve kısa geçerlilik süresidir.

**Ağır sorgu suistimali:** `?limit=1000000` gibi sayfalama parametreleriyle veya derin arama filtreleriyle veritabanını dize dize çalıştırıp servisi çökertmek. Saldırgan tek bir istekle devasa yük üretir.

**Maliyet tükenmesi (denial of wallet):** Bulut ortamında her istek para demektir. E-posta/SMS gönderen, dış API çağıran veya otomatik ölçeklenen bir endpoint'i sınırsız çağırmak, hizmet reddi yerine astronomik faturaya yol açar. Bu, bulut çağının kendine özgü bir saldırı biçimidir.

### Savunma

Rate limiting tek katmanlı değil, **çok boyutlu** kurulmalıdır:

- Sınırı yalnızca IP'ye göre değil; kullanıcı kimliğine, API anahtarına ve endpoint hassasiyetine göre uygulayın. IP tabanlı sınır, NAT arkasındaki meşru kullanıcıları cezalandırırken botnet'lerdeki dağıtık IP'leri durduramaz.
- Hassas endpoint'lere (login, parola sıfırlama, OTP doğrulama) çok daha sıkı sınırlar koyun. Bunlarda ek olarak artan gecikme (exponential backoff), hesap kilitleme ve CAPTCHA gibi katmanlar ekleyin.
- Kaynak asimetrisini yönetin: pahalı operasyonlara ayrı ve daha katı kotalar, sayfalama parametrelerine üst sınırlar (`limit` en fazla 100 gibi), istek gövdesi ve dosya boyutu limitleri koyun.
- Sınır aşıldığında `429 Too Many Requests` döndürün ve `Retry-After` başlığı ile istemciyi bilgilendirin. Meşru istemcilerin doğru davranabilmesi için sınırları şeffaf iletin.
- Sınırlamayı mümkünse API gateway / reverse proxy katmanında merkezî olarak uygulayın; her servisin ayrı ayrı doğru yapmasına güvenmek kırılgandır. Dağıtık sistemlerde sayaçları paylaşımlı bir depoda (ör. merkezî bir in-memory store) tutmak, birden çok sunucu kopyasında tutarlı sınır sağlar.
- Zaman penceresi algoritmasını bilinçli seçin: sabit pencere (fixed window) pencere sınırında ani patlamalara (burst) izin verirken, kayan pencere (sliding window) ve token bucket daha pürüzsüz ve adil sınırlama sağlar.

## Bu Zafiyetleri Birbirine Bağlayan Ortak Kök Neden

Dört konuyu tek tek incelediğimizde ortak bir örüntü belirir: **istemciye duyulan yersiz güven ve açık sınırların eksikliği.** Aşırı veri ifşasında sunucu "ne göndereceğime istemci karar versin" der; mass assignment'ta "ne yazacağıma istemci karar versin" der; rate limit eksikliğinde "ne kadar isteyeceğine istemci karar versin" der. Üçünde de sorumluluk, kontrol edilemeyen tarafa devredilmiştir.

Doğru zihniyet şudur: **API sınırı bir güven sınırıdır.** Bu sınırdan içeri giren her şey (gövde alanları, sorgu parametreleri, istek sıklığı) düşman kabul edilerek açık kurallarla süzülmelidir. Çıkan her şey (yanıt alanları) açık beyaz liste ile sınırlanmalıdır. "Varsayılan reddet, izin verileni açıkça beyan et" ilkesi, bu üç zafiyeti birden yapısal olarak kapatır.

## Yaygın Hatalar

- **Kimlik doğrulama ile yetkilendirmeyi karıştırmak.** Geçerli token, "bu nesneye erişebilir" demek değildir. Her endpoint nesne ve alan düzeyinde yetki kontrolü yapmalıdır.
- **İstemci arayüzünü güvenlik sınırı sanmak.** "Arayüz o alanı göstermiyor" veya "arayüz o alanı göndermiyor" cümleleri güvenlik argümanı değildir. Saldırgan arayüzü hiç kullanmaz, doğrudan endpoint ile konuşur.
- **Domain modelini API sınırına açmak.** ORM entity'sini hem girişte hem çıkışta doğrudan kullanmak, mass assignment ve aşırı veri ifşasını aynı anda davet eder. DTO katmanı olmazsa olmazdır.
- **Kara liste (blacklist) ile filtrelemek.** "Şu hassas alanları hariç tut" yaklaşımı, koda yeni bir hassas alan eklendiğinde sessizce açık verir. Her zaman beyaz liste kullanın.
- **Rate limit'i yalnızca IP'ye bağlamak.** Dağıtık saldırılar bunu kolayca atlatır; meşru NAT kullanıcıları ise haksız yere engellenir.
- **Hata mesajlarında fazla bilgi sızdırmak.** Ayrıntılı stack trace, alan adları ve iç yapı bilgisi, saldırgana mass assignment ve enumeration için harita çizer.
- **Versiyonlanmış eski endpoint'leri unutmak.** `/api/v1` güvenli hale getirilirken hâlâ ayakta olan zafiyetli `/api/v0` tüm çabayı boşa çıkarır. Kullanılmayan endpoint'ler kapatılmalıdır.
- **Kod üretme/otomatik bağlama araçlarına körü körüne güvenmek.** Bir framework'ün "otomatik model doldurma" kolaylığı, açık allowlist tanımlanmadığında tam da mass assignment kapısıdır.

## En İyi Pratikler

**Tasarımda güven sınırlarını netleştirin.** API'nizi çizerken hangi verinin hangi role gittiğini, hangi alanların yazılabilir olduğunu ve her endpoint'in hangi kaynağı ne kadar tükettiğini önceden belirleyin. Güvenlik sonradan yamanan değil, tasarımda kurulan bir özelliktir.

**Giriş ve çıkışta açık şema kullanın.** Her endpoint için input DTO ve output DTO tanımlayın. OpenAPI/JSON Schema ile hem beklenen alanları hem "bilinmeyen alan reddi" kuralını sözleşmeye bağlayın. Şema doğrulamasını isteğin en dış katmanında, iş mantığına ulaşmadan önce çalıştırın.

**Yetkilendirmeyi merkezîleştirin ve her katmanda uygulayın.** Nesne düzeyi (BOLA), fonksiyon düzeyi ve alan düzeyi yetki kontrollerini tek bir yerde, tutarlı bir politikayla yönetin. "Bu kullanıcı bu nesnenin sahibi mi?" kontrolünü her veri erişiminde tekrarlayın.

**Rate limiting'i katmanlı kurun.** Gateway seviyesinde global sınır, endpoint seviyesinde hassasiyete göre sınır, hesap seviyesinde suistimal tespiti bir arada çalışsın. Pahalı operasyonlara ayrı kotalar, sayfalama ve gövde boyutuna üst sınırlar koyun.

**En az veri ilkesini benimseyin.** İstemciye yalnızca o an gereken alanları gönderin; yalnızca gereken alanları kabul edin. Hassas alanları (parola özeti, iç notlar, rol, bakiye) API yanıtlarından tamamen çıkarın veya yalnızca yetkili görünümlerde açın.

**Sürekli test edin.** OpenAPI şemanızdan otomatik güvenlik testleri üretin; fuzzing ile beklenmeyen alanları ve parametreleri deneyin. Trafik üzerinde hassas veri sızıntısını ve anormal istek hacimlerini izleyen tespit araçları kurun. Güvenlik, bir kere geçilen bir denetim değil, sürekli işleyen bir süreçtir.

**Loglama ve izleme kurun.** Yetki reddi olaylarını, rate limit ihlallerini ve beklenmeyen alan içeren istekleri kaydedin. Bu sinyaller hem canlı saldırı tespiti hem de zafiyet keşfi için değerlidir. Ancak logların kendisine hassas veri (parola, token) yazmamaya dikkat edin.

## Sonuç

REST API güvenliğinin özü, tek bir cümlede toplanır: **API sınırından geçen her şeyi düşman, izin verileni ise açıkça beyan edilmiş kabul et.** Aşırı veri ifşası, mass assignment ve rate limit eksikliği yüzeyde farklı görünse de aynı hatanın üç yansımasıdır — kontrolün, güvenilemeyecek olan istemciye devredilmesi. OWASP API Security Top 10'un neredeyse tamamı bu yetkilendirme ve sınır disiplinine indirgenebilir. DTO temelli açık şemalar, katmanlı ve boyutlu rate limiting, her seviyede tekrarlanan yetki kontrolleri ve "varsayılan reddet" ilkesi bir arada uygulandığında, bu zafiyetler tek tek yamanan hatalar olmaktan çıkıp mimarinin doğal bir özelliği olarak kapanır.
