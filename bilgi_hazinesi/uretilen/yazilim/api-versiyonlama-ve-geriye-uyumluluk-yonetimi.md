# API Versiyonlama ve Geriye Uyumluluk Yönetimi

## Giriş ve Neden Önemli

Bir API (Application Programming Interface) yayına alındığı andan itibaren, sizin kontrolünüz dışındaki istemciler (client) ona bağımlı hale gelir. Mobil uygulamalar, üçüncü taraf entegrasyonlar, partner sistemleri ve dahili servisler bu API'nin davranışına güvenerek çalışır. İşte bu noktada temel gerilim ortaya çıkar: bir yandan API'yi geliştirmek, yeni özellikler eklemek ve hataları düzeltmek istersiniz; diğer yandan mevcut istemcileri bozmadan bunu yapmanız gerekir.

**API versiyonlama**, bu gerilimi yönetmenin disiplinidir. Amaç, API'nin evrimini (evolution) kontrol altında tutarken, mevcut tüketicilerin (consumer) çalışmaya devam etmesini sağlamaktır. Yanlış yönetildiğinde, tek bir dikkatsiz değişiklik binlerce üretim istemcisini aynı anda çökertebilir; doğru yönetildiğinde ise bir API yıllarca geriye uyumlu (backward compatible) kalarak güven inşa eder.

Bu makale versiyonlama stratejilerini, geriye uyumluluğun teknik anlamını, breaking change (kırıcı değişiklik) yönetimini, deprecation (kullanımdan kaldırma) politikalarını ve sözleşme testlerini (contract testing) uzman seviyesinde ele alır.

## Temel Kavram: Breaking Change ve Non-Breaking Change

Her şeyin merkezinde tek bir soru vardır: "Bu değişiklik mevcut bir istemciyi bozar mı?"

### Kırıcı Olmayan Değişiklikler (Non-Breaking / Backward-Compatible)

Bir istemcinin, kodunu değiştirmeden çalışmaya devam edebildiği değişikliklerdir. Genel kural olarak **eklemeci (additive)** değişiklikler kırıcı değildir:

- Response'a (yanıt) **yeni bir opsiyonel alan** eklemek.
- API'ye **yeni bir endpoint** eklemek.
- Bir isteğe **yeni bir opsiyonel parametre** eklemek (varsayılan değeri, eski davranışı koruyacak şekilde).
- Bir enum'a **yeni bir değer** eklemek — ancak bu dikkatli bir konudur (aşağıda tuzaklara bakınız).

Bunların kırıcı olmamasının kök nedeni **tolerant reader (hoşgörülü okuyucu) ilkesi**dir: iyi yazılmış bir istemci, tanımadığı alanları görmezden gelir; beklediği alanlar hâlâ orada olduğu sürece çalışır.

### Kırıcı Değişiklikler (Breaking Changes)

İstemcinin davranışını bozan, kod veya yapılandırma değişikliği gerektiren değişikliklerdir:

- Bir alanı veya endpoint'i **kaldırmak** ya da **yeniden adlandırmak**.
- Bir alanın **veri tipini değiştirmek** (örneğin `id` alanını integer'dan string'e çevirmek).
- Bir alanı **opsiyoneldan zorunluya** çevirmek (istekte yeni bir zorunlu parametre eklemek de buna dahildir).
- **Response yapısını yeniden düzenlemek** (bir alanı iç içe bir nesnenin altına taşımak).
- **Hata davranışını değiştirmek** — daha önce `200` dönen bir durumda artık `400` dönmek, ya da hata kodlarının anlamını değiştirmek.
- **Validation (doğrulama) kurallarını sıkılaştırmak** — daha önce kabul edilen bir girdiyi reddetmeye başlamak.
- **Varsayılan değerlerin veya sıralamanın (ordering) anlamını değiştirmek** istemci buna güveniyorsa.

Kritik nokta şudur: **breaking change'i belirleyen, kodun kendisi değil, istemcilerin gerçekte neye bağımlı olduğudur.** Teknik olarak "eklemeci" görünen bir değişiklik bile, istemciler beklenmeyen bir varsayıma dayanıyorsa (örneğin JSON'daki alan sırasına ya da tam bir alan kümesine) kırıcı olabilir. Bu yüzden ne olacağını tahmin etmek yerine sözleşme testleriyle (contract testing) doğrulamak gerekir.

## Semantic Versioning (SemVer) ve API'ye Uyarlanması

**Semantic Versioning (SemVer)**, `MAJOR.MINOR.PATCH` (örn. `2.4.1`) formatındaki bir sürüm numaralandırma standardıdır. Anlamı nettir:

- **MAJOR**: Geriye uyumsuz (backward-incompatible), yani kırıcı bir değişiklik yapıldığında artar.
- **MINOR**: Geriye uyumlu şekilde yeni işlevsellik eklendiğinde artar.
- **PATCH**: Geriye uyumlu hata düzeltmeleri yapıldığında artar.

SemVer'in kütüphaneler (library) için tasarlandığını unutmamak gerekir; HTTP API'lere uyarlanırken bazı incelikler vardır. Kütüphanelerde her MAJOR sürümü tüketici derleme zamanında (compile time) fark eder. HTTP API'lerde ise istemci çalışma zamanında (runtime) bağlanır ve genellikle yalnızca MAJOR sürümü URL'de veya header'da görünür. Bu nedenle pratikte:

- **MAJOR sürüm** dışa açık sözleşmeye yansıtılır (örn. `/v1/`, `/v2/`). Kırıcı değişiklik yeni bir MAJOR sürüm gerektirir.
- **MINOR ve PATCH** genellikle istemci için şeffaftır; mevcut sürüm eklemeci biçimde evrilir. Birçok büyük API sağlayıcısı MINOR/PATCH'i URL'de göstermez, sadece dokümantasyon ve değişiklik günlüğünde (changelog) izler.

**Doğru zihinsel model:** Bir MAJOR sürüm, aynı anda desteklenmesi gereken bir "sözleşme kuşağı"dır (contract generation). `/v1` ve `/v2` bir süre paralel yaşar; `/v1` içinde eklemeci evrim devam edebilir.

## Versiyonlama Stratejileri

API sürümünün nerede ve nasıl belirtileceği konusunda birkaç yaklaşım vardır. Her birinin kök mantığı ve tuzakları farklıdır.

### 1. URI Path Versioning (URL Yolunda Versiyonlama)

```
GET /v1/users/42
GET /v2/users/42
```

**Avantajları:** En görünür ve en basit yaklaşımdır. Tarayıcıdan test edilebilir, cache'lenmesi (önbellekleme) kolaydır, dokümantasyonda nettir. Yönlendirme (routing) altyapısı sürüme göre kolayca ayrıştırılabilir.

**Tuzakları:** Saf REST/HATEOAS savunucuları, aynı kaynağın (resource) iki farklı URI'sinin olmasını "kaynak kimliği tekildir" ilkesine aykırı bulur. Ayrıca istemciler URL'leri elle kodladığı için sürüm geçişleri manuel olur. Buna rağmen, pragmatik nedenlerle **sektörde en yaygın kullanılan yöntem budur**.

### 2. Header / Media Type Versioning (Content Negotiation)

Sürüm, özel bir header ya da `Accept` başlığındaki media type üzerinden belirtilir:

```
GET /users/42
Accept: application/vnd.sirket.v2+json
```

**Avantajları:** URL temiz kalır, aynı kaynağın tek bir kanonik adresi olur. HTTP'nin içerik müzakeresi (content negotiation) mekanizmasıyla teorik olarak en "doğru" REST yaklaşımıdır.

**Tuzakları:** Görünürlük düşüktür — bir URL'ye bakarak hangi sürümün kullanıldığını anlayamazsınız. Tarayıcıda basit bir GET ile test etmek zorlaşır. Cache anahtarlarının `Vary` header'ını doğru işlemesi gerekir; yanlış yapılandırılırsa yanlış sürüm cache'lenir.

### 3. Query Parameter Versioning

```
GET /users/42?version=2
```

Basittir ama header ve path yaklaşımlarının dezavantajlarını karıştırır; cache davranışı ve zorunlu/opsiyonel olma durumu belirsizleşir. Genellikle önerilmez, ancak hızlı prototipler için görülür.

### Pratik Öneri

Çoğu ekip için **URI path versioning (MAJOR düzeyde) + eklemeci evrim (MINOR/PATCH)** en dengeli seçimdir: görünür, test edilebilir, açıklaması kolay. Header versioning, sofistike istemci tabanına ve içerik müzakeresini doğru yönetebilecek altyapıya sahip olgun API programları için uygundur. Önemli olan tek bir yaklaşımı seçip tutarlı uygulamaktır.

## Deprecation (Kullanımdan Kaldırma) Politikası

Bir sürümü ya da alanı hemen silemezsiniz; istemcilerin göç etmesi (migration) için zaman tanımanız gerekir. **Deprecation policy**, bir özelliğin "artık önerilmiyor ama hâlâ çalışıyor" durumundan "tamamen kaldırıldı" durumuna nasıl geçeceğini tanımlayan sözleşmedir.

Sağlıklı bir deprecation yaşam döngüsü şu aşamaları içerir:

1. **Duyuru (Announce):** Değişiklik changelog, dokümantasyon ve mümkünse doğrudan istemci iletişimiyle ilan edilir. Kaldırma tarihi (sunset date) net verilir.
2. **Sinyal verme (Signal):** API çalışma zamanında da uyarı verir. Bunun için standartlaşmış mekanizmalar vardır:
   - **`Deprecation` HTTP response header'ı**, endpoint'in kullanımdan kaldırıldığını makine-okunabilir biçimde bildirir.
   - **`Sunset` HTTP header'ı** (RFC 8594), kaynağın erişilemez hâle geleceği tarihi belirtir.
   - `Link` header'ı ile göç dokümantasyonuna işaret edilebilir.
3. **Bekleme süresi (Grace period):** İstemcilere göç için makul bir süre tanınır. Bu süre API'nin kritikliğine ve istemci tabanının çevikliğine bağlıdır; dahili servislerde haftalar, geniş dış partner ağlarında aylar hatta bir yıldan uzun olabilir. Önemli olan **önceden ilan edilmiş, öngörülebilir bir sürenin olmasıdır**.
4. **Kaldırma (Sunset / Retire):** Süre dolduğunda sürüm veya özellik kaldırılır.

**Kök mantık:** Deprecation, teknik bir olaydan çok bir **iletişim ve güven** meselesidir. İstemciler, habersiz çökmelerle değil, öngörülebilir ve iyi belgelenmiş geçişlerle karşılaştıklarında API'ye güvenirler. Bir deprecation politikasının en önemli özelliği tutarlı ve önceden bilinir olmasıdır.

### Yaygın Deprecation Hataları

- **Sessiz kaldırma:** Bir alanı changelog'a yazmadan, header uyarısı vermeden kaldırmak. Bu, üretim ortamında ani arızalara yol açar.
- **Sonsuz deprecation:** "Deprecated" işaretlenip yıllarca kaldırılmayan özellikler, ekibi eski kodu taşımaya zorlar ve teknik borcu büyütür.
- **Kullanım verisi olmadan karar vermek:** Bir endpoint'in gerçekten kullanılıp kullanılmadığını bilmeden kaldırmak. **Sürüm ve endpoint bazında kullanım telemetrisi (usage telemetry)** toplamak, güvenli kaldırmanın önkoşuludur.

## Contract Testing ve Pact

Geriye uyumluluğu "umut ederek" değil, otomatik olarak **doğrulamak** gerekir. İşte bu noktada **contract testing (sözleşme testleri)** devreye girer.

### Sorun

Klasik entegrasyon testleri, sağlayıcı ve tüketici servislerini birlikte ayağa kaldırıp gerçek çağrılar yapmayı gerektirir. Mikroservis (microservice) mimarilerinde bu, yavaş, kırılgan ve pahalıdır; onlarca servisin aynı anda ayakta olmasını ister. Ayrıca "sağlayıcının yeni sürümü tüketiciyi bozar mı?" sorusunu erken değil, ancak entegrasyonda geç yakalar.

### Contract Testing Yaklaşımı

Contract testing, tüketici ile sağlayıcı arasındaki etkileşimi bir **sözleşme (contract)** olarak kaydeder: "Tüketici şu isteği gönderdiğinde, sağlayıcının şu yapıda bir yanıt döndürmesini bekliyorum." Bu sözleşme, iki tarafı **ayrı ayrı ve bağımsız** test etmeye izin verir.

**Pact**, bu alandaki en bilinen araçlardan biridir ve **consumer-driven contract testing (tüketici güdümlü sözleşme testi)** yaklaşımını uygular:

1. **Tüketici tarafı:** Tüketicinin testleri, sağlayıcının yerine geçen bir mock (taklit) sunucuya karşı çalışır. Bu testler çalışırken, tüketicinin gerçekten yaptığı istekleri ve beklediği yanıtları içeren bir **pact dosyası** (sözleşme) üretilir.

2. **Sözleşme paylaşımı:** Bu pact dosyası bir merkezi depoya (örneğin **Pact Broker**) yüklenir.

3. **Sağlayıcı tarafı doğrulaması:** Sağlayıcı, bu pact dosyasındaki her etkileşimi kendi gerçek kodu üzerinde tekrar oynatır (replay) ve gerçekten sözleşmeye uygun yanıt verip vermediğini doğrular.

**Kök mantık ve gücü:** Sözleşmeyi **tüketici belirler** — çünkü asıl önemli olan, tüketicinin API'nin hangi kısmına gerçekten bağımlı olduğudur. Sağlayıcı, hiçbir tüketicinin bağımlı olmadığı bir alanı özgürce değiştirebilir; ama bir tüketicinin bağımlı olduğu bir davranışı değiştirdiğinde, sağlayıcı doğrulaması **CI (Continuous Integration) aşamasında** kırılır. Böylece breaking change üretime çıkmadan, hatta sağlayıcı deploy edilmeden yakalanır.

Pact Broker'ın **can-i-deploy** özelliği bunu operasyonel hale getirir: "Sağlayıcının bu yeni sürümünü, üretimdeki tüm tüketicilerle uyumlu mu? Deploy edebilir miyim?" sorusuna otomatik yanıt verir.

### Contract Testing'in Sınırları

- Contract testing **fonksiyonel testin yerini tutmaz**; sadece arayüz sözleşmesinin korunduğunu doğrular. İş mantığının doğruluğunu ayrıca test etmelisiniz.
- Sözleşme, yalnızca tüketicinin gerçekten kullandığı alanları kapsar; kullanılmayan alanlardaki değişiklikler yakalanmaz (ki bu genelde istenen davranıştır).
- Şema temelli alternatifler de vardır: **OpenAPI/JSON Schema** spesifikasyonlarını referans alıp sürümler arası şema farkını (diff) otomatik denetleyen araçlar, breaking change'leri statik olarak yakalayabilir. Bu, contract testing'i tamamlayan bir katmandır.

## Uçtan Uca Doğru Kullanım: Bir Evrim Senaryosu

Diyelim ki `/v1/users` endpoint'i şu yanıtı dönüyor:

```json
{ "id": 42, "name": "Ayse Yilmaz" }
```

Yeni gereksinim: `name` alanını `firstName` ve `lastName` olarak ayırmak. Bu **kırıcı bir değişikliktir** çünkü `name`'i kaldırmak istemcileri bozar.

**Doğru yaklaşım (parallel change / expand-contract deseni):**

1. **Expand (Genişlet):** `/v1`'e `firstName` ve `lastName` alanlarını **eklemeci** biçimde ekleyin. `name` alanını da geriye uyumluluk için doldurmaya devam edin. Artık yanıt hem eski hem yeni tüketicileri memnun eder:
   ```json
   { "id": 42, "name": "Ayse Yilmaz", "firstName": "Ayse", "lastName": "Yilmaz" }
   ```
2. **Migrate (Göç):** İstemcileri yeni alanları kullanmaya teşvik edin, dokümantasyonu güncelleyin, `name`'i deprecated olarak işaretleyin (`Deprecation` header'ı ve changelog).
3. **Contract (Daralt):** Ancak yeni bir MAJOR sürümde — `/v2` — `name` alanını tamamen kaldırın. `/v1` yaşadığı sürece `name` orada kalır.

Bu **expand-contract (genişlet-daralt)** deseni, geriye uyumlu evrimin temel taşıdır: önce eklersin, herkes göç eder, sonra (yeni sürümde) kaldırırsın.

## Yaygın Hatalar ve Tuzaklar (Özet)

- **Enum'a değer eklemeyi masum sanmak:** Response enum'una yeni bir değer eklemek, katı bir istemcinin (bilinmeyen değeri reddeden) bozulmasına yol açabilir. İstemcileri en baştan "bilinmeyen enum değerlerini tolere edecek" biçimde tasarlamak ve bunu dokümante etmek gerekir.
- **Validation'ı sessizce sıkılaştırmak:** Daha önce kabul edilen bir girdiyi reddetmeye başlamak, teknik olarak "sadece bir doğrulama" gibi görünse de kırıcı bir değişikliktir.
- **Sürümü ölçmeden kaldırmak:** Kullanım telemetrisi olmadan bir sürümü kapatmak, sessiz ama kritik tüketicileri çökertir.
- **Çok fazla MAJOR sürüm:** Her küçük istek için yeni MAJOR sürüm açmak, bakım yükünü katlar. Mümkün olduğunca eklemeci evrimle aynı sürümde kalın; MAJOR sürümü gerçekten kaçınılmaz olduğunda kullanın.
- **Sürüm başına sonsuz destek:** Eski MAJOR sürümleri hiç kapatmamak, güvenlik yamaları ve bakım maliyetini sürekli artırır. Net bir sunset politikası ve makul sayıda desteklenen sürüm (genellikle mevcut + bir önceki) sağlıklıdır.
- **Sözleşmeyi belgelememek:** Versiyonlama stratejisini, deprecation politikasını ve desteklenen sürüm penceresini yazılı bir sözleşme olarak yayımlamamak. Tüketiciler ne bekleyeceklerini bilmelidir.

## Sonuç

API versiyonlama, tek bir teknik hile değil, bir **evrim disiplinidir**. Özü üç ilkeye dayanır: (1) breaking change ile non-breaking change'i doğru ayırt etmek ve mümkün olduğunca eklemeci ilerlemek; (2) kırıcı değişiklik kaçınılmaz olduğunda SemVer/MAJOR mantığıyla paralel sürümler ve öngörülebilir bir deprecation politikasıyla yönetmek; (3) geriye uyumluluğu umut ederek değil, contract testing (örneğin Pact) ve şema denetimi ile **otomatik doğrulayarak** garanti altına almak. Bu üç ilke bir araya geldiğinde, bir API yıllar boyunca hem gelişebilir hem de üzerine güvenle iş kurulabilecek kadar kararlı kalabilir.
