# API Tasarım İlkeleri

## Giriş: API Neden Bir "Sözleşme"dir?

Bir API (Application Programming Interface), iki yazılım parçasının birbiriyle konuşmak için üzerinde anlaştığı bir **sözleşmedir** (contract). Bu tanımı vurgulamak önemli, çünkü API tasarımıyla ilgili neredeyse tüm ilkeler bu tek fikirden türer. Sıradan bir fonksiyon çağrısını istediğiniz gibi değiştirebilirsiniz; en kötü ihtimalle kendi kod tabanınızda birkaç yeri güncellersiniz. Ama bir API'yi yayınladığınız an, onu kullanan istemcilerin (client) kodunu görmüyor, kontrol etmiyor ve çoğu zaman kim olduklarını bile bilmiyorsunuz. Yani API'niz artık size değil, **onu tüketenlere** aittir.

Bu asimetri, API tasarımını normal kod yazmaktan temelde ayıran şeydir. Kötü tasarlanmış bir iç fonksiyonu bir öğleden sonra refactor edersiniz. Kötü tasarlanmış bir public API ise yıllarca sizinle taşınır, çünkü onu bozmak binlerce istemcinin uygulamasını kırar. İşte bu yüzden API tasarımı, "çalışan bir şey yapmak"tan çok "sonradan pişman olmayacağın kararlar vermek" disiplinidir.

Bu makale, sağlam bir API'nin dayandığı beş temel eksene odaklanıyor: **tutarlılık**, **versiyonlama**, **hata yönetimi**, **dokümantasyon** ve **geliştirici deneyimi (DX)**. Bunlar birbirinden bağımsız konular değil; hepsi aynı ana hedefe hizmet eder: API'yi tahmin edilebilir kılmak.

## Tutarlılık (Consistency)

### Tanım ve Kök Neden

Tutarlılık, API'nin her yerinde aynı fikrin aynı şekilde ifade edilmesidir. Bir kaynağı listeleme, bir alanı adlandırma, bir tarihi biçimlendirme, bir hatayı döndürme; bunların hepsi API boyunca aynı kalıpları izlemelidir.

Peki bu neden bu kadar önemli? Kök neden **insan zihninin nasıl çalıştığıyla** ilgilidir. Bir geliştirici API'nizin bir ucunu öğrendiğinde, zihninde bir zihinsel model (mental model) oluşturur: "Demek ki listeler `data` altında dönüyor, tarihler ISO 8601 formatında, isimler `snake_case`." Tutarlı bir API bu modeli her yeni endpoint'te doğrular ve geliştirici **tahmin ederek** ilerleyebilir. Dokümantasyona bakmadan bir sonraki endpoint'in nasıl davranacağını doğru tahmin edebiliyorsa, siz işinizi iyi yapmışsınız demektir. Tutarsızlık ise bu modeli her seferinde kırar; geliştirici artık hiçbir şeye güvenemez ve her ayrıntıyı tek tek kontrol etmek zorunda kalır. Bu, bilişsel yük (cognitive load) demektir ve bilişsel yük, DX'in en büyük düşmanıdır.

### Somut Örnekler

Tutarlılığın nerede kırıldığını görmek, onu anlamanın en iyi yoludur. Klasik bir tutarsızlık örneği:

```
GET /users          -> { "users": [...] }
GET /getProducts    -> { "productList": [...] }
GET /orders/all     -> { "data": [...] }
```

Burada üç ayrı liste endpoint'i, üç ayrı adlandırma stili, üç ayrı sarmalama (envelope) biçimi kullanıyor. Kaynak adlandırma bazen çoğul (`users`), bazen fiil içeriyor (`getProducts`), bazen fazladan yol parçası taşıyor (`all`). Cevap zarfı da her seferinde değişiyor. Geliştirici bunların hiçbirini tahmin edemez.

Tutarlı hali şöyle olurdu:

```
GET /users          -> { "data": [...], "meta": {...} }
GET /products       -> { "data": [...], "meta": {...} }
GET /orders         -> { "data": [...], "meta": {...} }
```

Tutarlılık sadece isimlendirmede değildir. Aynı disiplin şunları da kapsar:

- **HTTP metotlarının anlamı:** `GET` her zaman güvenli (safe) ve yan etkisiz olmalı; `POST` oluşturmalı, `PUT` bütünüyle değiştirmeli/idempotent olmalı, `PATCH` kısmi güncelleme yapmalı, `DELETE` silmeli. Bir yerde `GET` ile veri silen bir tasarım, sözleşmeyi ihlal eder.
- **Veri tipleri:** Tarihler her yerde aynı formatta (tercihen ISO 8601, UTC ve zaman dilimi belirtilmiş şekilde). Para birimleri her yerde aynı gösterimde (kayan nokta hatalarından kaçınmak için genellikle en küçük birim cinsinden tam sayı, örneğin kuruş).
- **Sayfalama (pagination):** Aynı parametre isimleri (`limit`/`offset` ya da cursor tabanlı) tüm liste endpoint'lerinde aynı şekilde çalışmalı.

### Doğru Kullanım, Tuzaklar ve En İyi Pratikler

En büyük tuzak, tutarlılığın **zamanla erozyona uğraması**dır. API'nin ilk sürümü tertemiz olur; sonra farklı ekipler farklı endpoint'ler ekler, herkes kendi tercihini uygular ve iki yıl sonra API bir yamalar bohçasına döner. Bunun çaresi, tutarlılığı bireysel disipline bırakmamaktır. Çözüm mekanizmaları şunlardır:

- **Yazılı bir API stil kılavuzu (style guide):** Adlandırma, çoğullaştırma, hata formatı, sayfalama gibi kararların tek bir yerde belgelenmesi.
- **Otomatik denetim (linting):** OpenAPI/JSON Schema tabanlı linter'lar, yeni endpoint'lerin kurallara uyup uymadığını CI aşamasında kontrol edebilir. İnsan iradesi yerine makine zorlaması, tutarlılığı ölçeklenebilir kılan tek yoldur.
- **Design review:** Yeni endpoint'ler koda geçmeden önce sözleşme düzeyinde gözden geçirilir.

## Versiyonlama (Versioning)

### Tanım ve Kök Neden

Versiyonlama, API sözleşmesini zaman içinde nasıl değiştireceğinizi yöneten stratejidir. Kök neden şudur: **hiçbir API ilk seferde mükemmel doğmaz** ve iş gereksinimleri değişir. Yeni alanlar eklemeniz, eski alanları kaldırmanız, veri modelini yeniden düzenlemeniz gerekir. Ama daha önce vurguladığımız gibi, istemcilerinizin kodu sizin kontrolünüzde değildir. İşte versiyonlama, "API'yi ilerletme ihtiyacı" ile "mevcut istemcileri kırmama yükümlülüğü" arasındaki gerilimi yönetmenin yoludur.

Buradaki merkezi kavram **kırıcı değişiklik (breaking change)** ile **geriye dönük uyumlu değişiklik (backward-compatible change)** ayrımıdır. Bu ayrımı doğru yapamayan bir ekip, ya API'yi hiç geliştiremez (korkudan) ya da sürekli istemcileri kırar.

Kırıcı olan değişiklikler tipik olarak şunlardır:
- Bir alanı veya endpoint'i kaldırmak.
- Bir alanın adını veya tipini değiştirmek.
- Zorunlu yeni bir istek parametresi eklemek.
- Bir hatanın anlamını veya kodunu değiştirmek.
- Cevabın yapısını (nesting) değiştirmek.

Kırıcı olmayan (aditif) değişiklikler ise:
- Cevaba **yeni ve opsiyonel** bir alan eklemek.
- Yeni bir endpoint eklemek.
- Opsiyonel yeni bir istek parametresi eklemek.

Bu ayrımın çalışma mantığı, iyi yazılmış istemcilerin **tolerant reader (hoşgörülü okuyucu)** ilkesine uymasına dayanır: bir istemci, tanımadığı alanları görmezden gelmelidir. Bu yüzden cevaba yeni alan eklemek çoğu istemciyi kırmaz. Ama bir alanı kaldırırsanız, ona bağımlı istemci mutlaka kırılır.

### Versiyonlama Stratejileri

Pratikte birkaç yaygın yaklaşım vardır ve her birinin bir bedeli vardır:

**URL yol tabanlı versiyonlama** (`/v1/users`, `/v2/users`): En açık ve en kolay anlaşılan yöntem. Bir geliştirici URL'ye bakarak hangi sürümü kullandığını hemen görür, tarayıcıda test etmek kolaydır. Eleştirisi, "aynı kaynağın (user) her sürümde farklı URL'e sahip olması REST'in kaynak felsefesine aykırı" olmasıdır ama pratikte en yaygın ve en pragmatik çözüm budur.

**Header tabanlı versiyonlama** (örneğin bir `Accept` header'ında sürüm belirtmek): URL'yi temiz tutar ve teorik olarak daha "doğru"dur, ama görünmez olduğu için test etmesi ve hata ayıklaması zordur. Geliştirici hangi sürümü çağırdığını yanlışlıkla kaçırabilir.

**Sürüm yok, sadece geriye uyumlu evrim:** Bazı büyük sağlayıcılar API'yi hiç versiyonlamaz; sadece aditif değişiklikler yapar ve asla kırıcı değişikliğe gitmezler. Bu, en yüksek disiplini gerektiren ama istemciler için en rahat olan yaklaşımdır. Tarih tabanlı sürümler (istek başına belirtilen bir tarih ile "o günkü davranışı dondurmak") de bunun bir çeşididir.

### Semantik Versiyonlama ve Deprecation

Kütüphane API'lerinde (REST değil, kod kütüphanesi) **semantic versioning** (SemVer, `MAJOR.MINOR.PATCH`) standarttır: MAJOR kırıcı değişiklik, MINOR geriye uyumlu yeni özellik, PATCH geriye uyumlu hata düzeltmesi anlamına gelir. Bu şema, istemcilere bir sürümü güncellemenin ne kadar riskli olduğunu tek bakışta anlatır.

Versiyonlamanın en çok ihmal edilen ama en kritik parçası **deprecation (kullanımdan kaldırma) süreci**dir. Bir sürümü kapatmak tek bir anda yapılmaz; şu adımlar izlenir:

1. Yeni sürümü yayınla, eski sürümü çalışır tut.
2. Eski sürümü **deprecated** olarak işaretle (dokümantasyonda ve mümkünse cevap header'larında uyarı ver).
3. İstemcilere geçiş için makul ve önceden duyurulmuş bir süre tanı (aylar, hatta yıllar).
4. Kullanım metriklerini izle; kimlerin hâlâ eski sürümü çağırdığını bil ve onlara ulaş.
5. Ancak trafik yeterince düştüğünde kapat.

En yaygın hata, "artık bu alanı kullanmıyoruz" deyip bir alanı sessizce kaldırmaktır. Bu, en az bir istemciyi mutlaka kırar. İkinci yaygın hata, **v2'yi çıkarıp v1'i asla kapatmamak** ve sonunda beş sürümü aynı anda sürdürmek zorunda kalmaktır. Versiyonlama disiplini, hem başlatma hem de sonlandırma tarafında planlı olmayı gerektirir.

## Hata Yönetimi (Error Handling)

### Tanım ve Kök Neden

Hata yönetimi, bir şey ters gittiğinde API'nizin istemciye ne söylediğidir. Çoğu API tasarımcısı zamanının %90'ını "mutlu yol"a (happy path) harcar ve hataları sonradan düşünür. Bu bir hatadır, çünkü **istemcinin en çok yardıma ihtiyaç duyduğu an, bir şeyin ters gittiği andır.** Mutlu yolda geliştiricinin size ihtiyacı yoktur; ama 400 aldığında ve nedenini anlayamadığında, kötü hata tasarımınız onu saatlerce oyalar.

Kök neden, **hataların da makineler tarafından okunması gerektiği** gerçeğidir. Bir hata mesajı hem bir insanın (geliştirici) hem de bir programın (istemci kodu) anlayabileceği şekilde tasarlanmalıdır. İnsan mesajı okur; program ise koda göre dallanır (örneğin "kredi kartı reddedildi" hatasında kullanıcıya farklı bir ekran gösterir).

### HTTP Durum Kodları ve Yapılandırılmış Gövde

HTTP'de hataların ilk katmanı **durum kodudur (status code)**. Bunları doğru kullanmak sözleşmenin temelidir:

- **2xx** — Başarı.
- **4xx** — İstemci hatası. Sorun isteği yapanda; aynı isteği aynen tekrarlamak yine başarısız olur. `400` (kötü istek), `401` (kimlik doğrulanmamış), `403` (yetki yok), `404` (bulunamadı), `409` (çakışma), `422` (doğrulama hatası), `429` (çok fazla istek) gibi.
- **5xx** — Sunucu hatası. Sorun sizde; istemci genelde daha sonra tekrar deneyebilir.

Kritik ve sık yapılan bir ayrım hatası: `401` **kimliğinin kim olduğunu kanıtlayamadın** (authentication) demektir; `403` ise **kim olduğunu biliyorum ama bunu yapmaya iznin yok** (authorization) demektir. Bunları karıştırmak istemcinin yanlış davranmasına yol açar.

Durum kodu tek başına yetmez; **yapılandırılmış (structured) bir hata gövdesi** de gerekir. İyi bir hata gövdesi şunları içerir: makine tarafından okunabilir sabit bir hata kodu, insan tarafından okunabilir bir mesaj ve hangi alanın neden başarısız olduğunu belirten ayrıntılar. Örnek bir doğrulama hatası:

```json
{
  "error": {
    "code": "validation_error",
    "message": "İstek doğrulanamadı.",
    "details": [
      { "field": "email", "issue": "geçersiz e-posta formatı" },
      { "field": "age", "issue": "0'dan büyük olmalı" }
    ]
  }
}
```

Buradaki tasarım kararları önemlidir. `code` alanı **sabittir ve asla çevrilmez**; istemci koduna göre dallanır. `message` insan içindir ve değişebilir. `details` ise formların birden çok alanının aynı anda başarısız olabildiği durumlarda kritiktir; istemci tek seferde tüm hataları kullanıcıya gösterebilir. Endüstride bu tür yapılandırılmış hata gövdeleri için ortak bir formatı benimsemek (örneğin HTTP API'ler için "problem details" tarzı bir yapı) tekerleği yeniden icat etmekten kurtarır.

### Tuzaklar ve En İyi Pratikler

En yaygın ve en tehlikeli hata **her şeye `200 OK` dönüp gövdede `{"success": false}` yazmaktır.** Bu, HTTP'nin tüm hata altyapısını (izleme araçları, retry mantığı, cache davranışı, load balancer sağlık kontrolleri) çöpe atar. Durum kodu, ara katmanların (proxy, gateway) anlayabildiği tek ortak dildir; onu doğru kullanın.

İkinci büyük tuzak **güvenlik açısından fazla bilgi sızdırmaktır.** Bir 500 hatasında ham stack trace'i, veritabanı sorgusunu veya iç dosya yollarını istemciye dönmek, saldırganlara sisteminizin haritasını verir. Ayrıntılı iç bilgiyi sunucu loglarına yazın; istemciye genel bir mesaj ve hatayı loglarda bulmayı sağlayacak bir **correlation ID / request ID** dönün. Bu ID, geliştiricinin size "şu isteğim patladı" diyebilmesi ve sizin de o isteği loglarda anında bulabilmeniz için altın değerindedir.

Diğer önemli pratikler:
- **Tutarlı hata formatı:** Tüm API boyunca hataların aynı yapıda dönmesi (tutarlılık ilkesiyle birleşir).
- **`429` ile birlikte yeniden deneme rehberi:** Hız sınırına (rate limit) takılan istemciye ne zaman tekrar deneyebileceğini söyleyen bir bilgi (örneğin `Retry-After` header'ı) vermek.
- **Idempotency:** Ödeme gibi kritik `POST` işlemlerinde, istemcinin bir **idempotency key** göndermesine izin vermek. Ağ koptuğunda istemci aynı isteği güvenle tekrarlayabilir ve siz işlemi iki kez uygulamazsınız. Bu, "hata yönetimi"nin en olgun halidir: hatayı sadece bildirmez, ondan güvenli kurtulmayı da mümkün kılarsınız.

## Dokümantasyon (Documentation)

### Tanım ve Kök Neden

Dokümantasyon, API sözleşmesinin insan tarafından okunabilir halidir. Şu keskin gerçeği kabul etmek gerekir: **dokümante edilmemiş bir özellik, pratikte var olmayan bir özelliktir.** Bir geliştirici keşfedemediği bir endpoint'i kullanamaz. Bu yüzden dokümantasyon, API'nin "ekstra"sı değil, arayüzün kendisinin bir parçasıdır.

Kök neden, geliştiricilerin API'nizi **okuyarak değil, deneyerek** öğrenmesidir. Kimse baştan sona bir referans okumaz; herkes çözmeye çalıştığı somut probleme en yakın örneği arar, kopyalar, çalıştırır ve oradan ilerler. İyi dokümantasyon bu davranışı destekleyecek şekilde tasarlanır.

### İyi Dokümantasyonun Katmanları

Etkili dokümantasyon tek bir şey değildir; farklı ihtiyaçlara hitap eden katmanlardan oluşur:

- **Başlangıç kılavuzu (getting started / quickstart):** Yeni bir geliştiricinin ilk başarılı çağrıyı yapmasına kadar geçen yolu, ideal olarak beş dakikanın altında, elinden tutarak geçiren bölüm. Bu, "ilk değere ulaşma süresi"ni (time to first call) belirler ve bir API'yi benimseyip benimsememe kararının çoğu burada verilir.
- **Kavramsal rehberler (guides):** "Kimlik doğrulama nasıl çalışır", "sayfalama nasıl yapılır", "webhook'ları nasıl kurarsın" gibi, birden çok endpoint'i bir arada anlatan konu bazlı anlatımlar.
- **Referans (reference):** Her endpoint'in, her parametrenin, her alanın eksiksiz ve kesin tanımı. Bunun büyük ölçüde makine tarafından üretilmesi idealdir.
- **Örnekler (examples):** Gerçek, kopyalanıp çalıştırılabilir istek/cevap çiftleri. Her endpoint için en az bir tam örnek.

### Sözleşme Odaklı Yaklaşım ve Tuzaklar

Modern dokümantasyonun temel taşı, **makine tarafından okunabilir bir API tanımıdır** (HTTP API'ler için OpenAPI/Swagger, gRPC için Protobuf tanımları, GraphQL için şema). Bu tanım tek bir gerçek kaynağı (single source of truth) olarak hizmet eder ve ondan hem interaktif dokümantasyon, hem istemci kütüphaneleri (SDK), hem de test/doğrulama araçları otomatik üretilebilir.

Buradan en kritik tuzak çıkar: **dokümantasyonun koddan ayrı yaşaması ve zamanla senkronizasyonu kaybetmesi.** Elle yazılmış, koddan bağımsız bir dokümantasyon kaçınılmaz olarak eskir. Bir endpoint değişir, dokümantasyon güncellenmez ve **yanlış dokümantasyon, hiç olmamasından daha kötüdür** çünkü geliştiriciyi aktif olarak yanlış yönlendirir ve güveni yok eder. Çözüm, dokümantasyonu mümkün olduğunca koddan/şemadan üretmek ve testlerle doğrulanır hale getirmektir. Örneklerin gerçekten çalıştığını CI'da test etmek, "belgelerdeki örnek artık çalışmıyor" utancını ortadan kaldırır.

Bir başka değerli araç, **interaktif dokümantasyon**dur: geliştiricinin tarayıcıdan doğrudan gerçek bir istek gönderip cevabı görebildiği bir arayüz (bir "deneyin/try it" alanı). Bu, okumayı denemeye çevirir ve öğrenme eğrisini dramatik biçimde düşürür.

## Geliştirici Deneyimi (Developer Experience — DX)

### Tanım: Diğer Her Şeyin Toplamı

DX, bir geliştiricinin API'nizle çalışırken hissettiği toplam deneyimdir. Yukarıda konuştuğumuz her şey (tutarlılık, versiyonlama, hata yönetimi, dokümantasyon) aslında DX'in bileşenleridir. DX'i ayrı bir başlık yapmamın nedeni, onu belirleyen ama diğer başlıklara girmeyen ek ilkeleri toplamak ve hepsinin arkasındaki felsefeyi netleştirmektir.

O felsefe şudur: **API'niz bir üründür ve kullanıcısı geliştiricidir.** Bu bakış açısı her şeyi değiştirir. Bir ürün yöneticisi kullanıcının işini nasıl kolaylaştıracağını düşünür; siz de geliştiricinin işini nasıl kolaylaştıracağınızı düşünmelisiniz. İyi DX'in ticari sonucu somuttur: benimsenme (adoption) artar, destek talepleri azalır, geliştiriciler sizi başkalarına önerir.

### DX'i İyi Yapan İlkeler

**Az sürprizle çalışmak (principle of least astonishment):** API, deneyimli bir geliştiricinin **tahmin edeceği** gibi davranmalıdır. Sektörün ortak kalıplarını (REST konvansiyonları, standart header'lar, alışılmış hata formatları) benimsemek, geliştiricinin daha önce öğrendiği her şeyi API'nizde yeniden kullanmasını sağlar. Yaratıcı olmanız gereken yer iş mantığınızdır, HTTP metodu seçiminiz değil.

**Basit şeyler basit, karmaşık şeyler mümkün olmalı:** En yaygın kullanım senaryosu minimum çabayla yapılabilmeli; ileri senaryolar da (isteğe bağlı parametrelerle) desteklenmeli ama basit yolu karmaşıklaştırmamalıdır. Yeni bir geliştiriciyi ilk çağrıda on zorunlu parametreyle boğmak, benimsenmeyi öldürür.

**Anlamlı varsayılanlar (sensible defaults):** İyi seçilmiş varsayılan değerler, geliştiricinin vermek zorunda olduğu karar sayısını azaltır. Bir liste endpoint'i varsayılan bir sayfa boyutuyla gelmelidir; geliştirici her seferinde `limit` belirtmek zorunda kalmamalıdır.

**İyi SDK'lar ve dil desteği:** Ham HTTP çağrıları çoğu geliştirici için tercih değildir. Resmî, iyi bakımı yapılan istemci kütüphaneleri (SDK) API'yi o dilin doğal deyimlerine çevirir, kimlik doğrulama/retry/sayfalama gibi tekrar eden işleri halleder ve DX'i katbekat artırır. Bu SDK'ları da API tanımından üretmek hem tutarlılığı hem de bakım kolaylığını sağlar.

**Hızlı ve güvenli deneme ortamı:** Bir **sandbox/test ortamı** ve **test anahtarları**, geliştiricinin gerçek veriyi veya gerçek parayı riske atmadan denemesini sağlar. Denemenin ucuz ve risksiz olması, öğrenmeyi hızlandırır.

### DX Tuzakları ve En İyi Pratikler

DX'i sabote eden yaygın hatalar genellikle "kolay çıkış yolları"dır:

- **Sızdıran soyutlama (leaky abstraction):** İç veritabanı şemanızı, tablo isimlerinizi veya iç servis sınırlarınızı olduğu gibi API'ye yansıtmak. İstemci sizin iç kararlarınıza bağımlı hale gelir ve siz refactor yapamaz olursunuz. API, iç yapınızı değil, istemcinin ihtiyacı olan **kavramları** modellemelidir.
- **Tutarsız kimlik doğrulama:** Bir endpoint bir yöntemi, diğeri başkasını isteyince geliştirici her seferinde durup düşünmek zorunda kalır.
- **Sessiz kırılmalar ve sürpriz limitler:** Belgelenmemiş bir hız sınırına ansızın çarpmak veya cevabın yapısının haber verilmeden değişmesi, güveni en hızlı yok eden şeylerdir.
- **Geri bildirim döngüsünün yavaşlığı:** Değişikliklerin sonucunu görmek uzun sürüyorsa (yavaş sandbox, zor kurulum), geliştirici pes eder. İyi DX, kısa geri bildirim döngüleri demektir.

En iyi pratik ise DX'i tahmine değil **ölçüme** dayandırmaktır: geliştiricilerin en çok hangi hataları aldığını, en çok nerede takıldığını, "ilk başarılı çağrıya" ne kadar sürede ulaştıklarını izleyin. Bu metrikler, API'nizin gerçek zayıf noktalarını gösterir ve tahminle değil veriyle iyileştirme yapmanızı sağlar.

## Sonuç: Beş İlke, Tek Hedef

Bu beş eksene tek tek baktık ama asıl fikir hepsinin ortak paydasında yatıyor: **tahmin edilebilirlik.** Tutarlılık, geliştiricinin bir sonraki adımı tahmin edebilmesidir. Versiyonlama, değişimin ne zaman ve nasıl geleceğinin tahmin edilebilir olmasıdır. İyi hata yönetimi, bir şey ters gittiğinde ne olacağının tahmin edilebilir olmasıdır. Dokümantasyon, bu tahminleri açıkça yazıya dökmektir. DX ise bu tahmin edilebilirliğin geliştiricide yarattığı güven ve akıcılık hissidir.

API tasarımının özünde teknik bir mesele değil, bir **empati** meselesi vardır: kodunu görmediğiniz, adını bilmediğiniz, sizinle konuşamayan bir geliştiricinin yerine kendinizi koymak. En iyi API'lerin ortak özelliği görkemli özellikler değil, **sıkıcı derecede tutarlı ve tahmin edilebilir** olmalarıdır. Bu sıkıcılık, bir kusur değil; en zor kazanılan erdemdir. Çünkü bir sözleşme yazıyorsunuz ve iyi sözleşmeler sürprizsizdir.
