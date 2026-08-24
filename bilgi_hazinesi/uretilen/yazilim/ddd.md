# Domain-Driven Design: Bounded Context, Aggregate ve Taktiksel Tasarım

Domain-Driven Design (DDD), Eric Evans'ın 2003'te yayımladığı kitapla adını duyuran, karmaşık iş yazılımlarını **iş alanının (domain) kendi mantığına sadık kalarak** modellemeyi amaçlayan bir yaklaşımdır. DDD bir framework ya da kütüphane değildir; bir düşünme disiplini, bir dizi kavram ve pratik bütünüdür. Temel iddiası şudur: Yazılımın gerçek zorluğu genellikle teknolojide değil, **iş alanının doğasında var olan karmaşıklıktadır** (essential complexity). Bir sigorta poliçesinin, bir muhasebe defterinin ya da bir tedarik zincirinin kuralları özünde karmaşıktır; bu karmaşıklığı kod içinde dürüstçe temsil edemezsen, teknoloji ne kadar iyi olursa olsun sistem zamanla anlaşılmaz ve değiştirilemez hale gelir.

Bu makale DDD'nin dört merkezi kavramına odaklanır: **ubiquitous language** (her yerde geçerli ortak dil), **bounded context** (sınırlanmış bağlam), **aggregate** (bütünleşik nesne kümesi) ve genel olarak **taktiksel tasarım** kalıpları. Bunlar birbirinden bağımsız araçlar değil; her biri bir öncekinin üzerine oturur ve birlikte tutarlı bir mimari felsefe oluşturur.

## Neden DDD? Kök neden ve çalışma mantığı

DDD'yi anlamanın en iyi yolu, hangi problemi çözmek için doğduğuna bakmaktır. Klasik kurumsal yazılımlarda tipik bir çürüme senaryosu şöyle işler: Başta veritabanı tabloları tasarlanır, üzerine anemik (davranışsız, sadece getter/setter içeren) veri nesneleri konur ve iş kuralları hizmet (service) katmanına, controller'lara, hatta stored procedure'lara dağılır. Kısa vadede hızlı ilerlenir. Ama proje büyüdükçe aynı kavram (örneğin "müşteri" ya da "sipariş") her katmanda biraz farklı anlaşılır, kurallar tekrarlanır, tutarsızlaşır ve kimse artık sistemin bir davranışının **neden** öyle olduğunu tek bir yerden okuyamaz. Buna genellikle "big ball of mud" (büyük çamur topu) denir.

DDD'nin kök tezi şudur: **Bu çürümenin nedeni, yazılım modelinin iş alanının zihinsel modelinden kopmasıdır.** İş uzmanı "iade" derken belirli bir süreci kastediyor, geliştirici kodda `status = 3` yazıyor; aradaki çeviri her seferinde bilgi kaybına ve yanlış anlamaya yol açıyor. DDD bu kopmayı iki cephede kapatmaya çalışır:

1. **Dil cephesinde** ubiquitous language ile: kod, konuşma ve dokümanların aynı terimleri kullanmasını sağlar.
2. **Yapı cephesinde** bounded context ve taktiksel kalıplarla: iş kurallarının nesnelerin içine, doğru sınırlar içinde yerleşmesini sağlar.

Yani DDD aslında bir **iletişim ve sınır çizme disiplinidir**. Teknik kalıplar (aggregate, repository, value object) bu iletişimi kod düzeyinde somutlaştıran araçlardır.

## Ubiquitous Language: Ortak dilin gücü

### Tanım

Ubiquitous language, bir ekibin (geliştiriciler, iş uzmanları, analistler, testçiler) belirli bir bağlam içinde ortaklaşa ve tutarlı biçimde kullandığı, hem konuşmalarda hem de kodda birebir yaşayan dildir. "Ortak sözlük" demek yetersiz kalır; kritik olan bu dilin **koda kadar sızması**dır. Eğer iş uzmanı "poliçe fesih edildi" diyorsa, kodda `policy.cancel()` metodu bulunmalı; `policy.setStatus(5)` değil.

### Kök neden: Neden dil bu kadar önemli?

Yazılım geliştirme aslında bir **model inşa etme** faaliyetidir ve model, kafalardaki soyut anlayışın somutlaştırılmış halidir. İnsanlar arasındaki her çeviri katmanı entropi ekler. İş uzmanı → analist → geliştirici → kod zinciri boyunca her adımda anlam biraz bozulur. Ubiquitous language, bu zinciri kısaltıp aradaki çeviricileri ortadan kaldırmayı hedefler: Herkes aynı kelimeleri kullanırsa, yanlış anlama fırsatı azalır ve kod, iş uzmanının bile (metot isimleri üzerinden) kabaca okuyabileceği bir belgeye dönüşür.

Bu dilin bir başka gizli faydası, **modeldeki kusurları erken açığa çıkarmasıdır.** Bir kavramı isimlendirmekte zorlanıyorsan, bu genellikle modelin o noktada yanlış ya da eksik olduğunun işaretidir. Örneğin ekip "şu şey" diye tarif ettiği bir nesneye türlü isim veriyorsa, muhtemelen orada birbirine karışmış iki farklı kavram vardır ve ayrıştırılması gerekir.

### Somut örnek

Bir e-ticaret sisteminde başlangıçta her şey "Order" (sipariş) etrafında modellenmiş olsun. İş uzmanlarıyla konuşuldukça şu ayrımlar ortaya çıkar: Müşterinin henüz onaylamadığı, sepetteki hali "Cart" (sepet); ödeme onayı beklenen hali "PendingOrder"; kargoya verilmiş hali "Shipment". Bunlar tek bir "Order" sınıfının farklı `status` değerleri gibi görünse de, iş dilinde farklı isimlere ve farklı kurallara sahip **farklı kavramlardır.** Ubiquitous language bu ayrımı zorlar; sonuçta kod da bu farklı yaşam evrelerini net biçimde temsil eder.

### Tuzaklar

En yaygın tuzak, ubiquitous language'i tek bir global sözlük sanmaktır. Gerçekte dil **bağlama bağlıdır**; bu da bizi doğrudan bounded context kavramına götürür.

## Bounded Context: Sınırlanmış bağlam

### Tanım

Bounded context, belirli bir modelin ve onun ubiquitous language'inin **geçerli olduğu açık sınırdır**. Bu sınırın içinde her terimin tek ve tutarlı bir anlamı vardır. Sınırın dışında ise aynı kelime bambaşka bir şey ifade edebilir. Bounded context, DDD'nin **stratejik tasarım** kısmının en önemli kavramıdır ve büyük sistemlerde belki de en değerli fikridir.

### Kök neden: Neden tek bir model tüm sistemi kapsayamaz?

Sezgisel beklenti, kurum genelinde tek, tutarlı, birleşik bir model kurmaktır — "tek bir Müşteri nesnesi, herkes onu kullansın". Bu beklenti pratikte çöker. Nedeni şudur: **Aynı kelime farklı departmanlarda gerçekten farklı anlamlara gelir ve bunları tek nesnede birleştirmeye çalışmak modeli şişirir ve tutarsızlaştırır.**

"Ürün" (Product) kavramını düşün. Satış bağlamında ürün, fiyatı, kampanyası, açıklaması ve görselleri olan bir şeydir. Depo/lojistik bağlamında ürün, ağırlığı, hacmi, raf konumu ve stok adedi olan bir şeydir. Muhasebe bağlamında ürün, vergi sınıfı ve maliyet kalemidir. Bu üç görünümü tek bir dev "Product" sınıfında birleştirirsen, onlarca alanı olan, her departmanın sadece küçük bir kısmını umursadığı, herkesin birbirinin değişikliğinden etkilendiği bir canavar elde edersin. Değişiklik yapmak korkutucu hale gelir çünkü bir alandaki değişiklik ilgisiz bir başka alanı bozabilir.

Bounded context der ki: **Bırakın her bağlamın kendi "Product" modeli olsun.** Bunlar farklı sınıflardır, aynı gerçek dünya nesnesinin farklı görünümleridir ve genellikle sadece bir kimlik (ürün ID'si) ile birbirine bağlanırlar. Böylece her bağlam kendi içinde sade, tutarlı ve bağımsız olarak evrilebilir kalır.

### Context Map: Bağlamlar arası ilişkiler

Bounded context'ler birbirinden tamamen kopuk değildir; aralarında veri ve olay akışı olur. Bu ilişkileri açıkça haritalamaya **context map** denir. DDD, bağlamlar arası ilişki türleri için isimlendirmeler sunar. Sık kullanılanlardan bazıları:

- **Shared Kernel** (paylaşılan çekirdek): İki ekip küçük bir ortak modeli birlikte sahiplenir. Sıkı koordinasyon gerektirir; dikkatli kullanılmalıdır.
- **Customer/Supplier** (müşteri/tedarikçi): Aşağı akıştaki (downstream) bağlam yukarı akıştaki (upstream) bağlamdan besleniyordur ve ihtiyaçlarını ona iletebilir.
- **Conformist** (uyumcu): Aşağı akış, yukarı akışın modelini olduğu gibi kabul etmek zorundadır, pazarlık gücü yoktur.
- **Anticorruption Layer** (ACL, yozlaşmaya karşı katman): Bir bağlam, dış bir sistemin (özellikle eski/legacy ya da kötü modellenmiş bir sistemin) modelinin kendi içine sızıp modelini bozmasını engellemek için bir çeviri katmanı koyar. Bu, DDD'nin en pratik ve en çok işe yarayan kalıplarından biridir: Dış dünyanın kaosunu sınırında karşılar ve kendi temiz modeline çevirir.

### Bounded context ile mikroservisler ilişkisi

Bounded context, mikroservis mimarisinin doğal sınır çizme aracı olarak yaygın biçimde kullanılır. Bir mikroservisin sınırlarını **bounded context sınırlarına** göre çizmek, güçlü bir sezgidir; çünkü bounded context zaten "burada dil ve model değişiyor" diyen doğal fay hattıdır. Ancak dikkat: bounded context ile mikroservis birebir aynı şey değildir. Bir bounded context tek bir monolit içinde bir modül olarak da yaşayabilir. Mikroservise geçiş bir dağıtım (deployment) kararıdır; bounded context ise bir modelleme kararıdır. Sağlıklı yol genellikle önce iyi bounded context'ler tanımlamak, servis bölmeyi sonra yapmaktır.

## Taktiksel Tasarım: Yapı taşları

Stratejik tasarım (bounded context, context map) sistemin büyük parçalarını çizerken, **taktiksel tasarım** her bir bounded context'in içini modellemek için kullanılan somut kalıpları sunar. Başlıcaları: entity, value object, aggregate, repository, domain service, domain event ve factory.

### Entity ve Value Object

**Entity** (varlık), kimliği (identity) olan ve zaman içinde durumu değişse de aynı nesne olarak kalan şeydir. Bir müşteri, adı değişse de aynı müşteridir; onu bir kimlik (ID) tanımlar. İki entity, tüm alanları eşit olsa bile farklı kimliklere sahipse farklıdır.

**Value object** (değer nesnesi) ise kimliği olmayan, sadece değerleriyle tanımlanan şeydir. Bir para tutarı (100 TL), bir tarih aralığı, bir adres, bir renk — bunlar value object'tir. İki value object, tüm alanları eşitse aynıdır. Value object'ler ideal olarak **değiştirilemezdir (immutable)**: 100 TL'yi 150 TL yapmazsın, yeni bir 150 TL nesnesi oluşturursun.

Bu ayrımın kök nedeni önemlidir: Value object'ler modele **anlam ve güvenlik** katar. `BigDecimal amount` yerine `Money amount` kullandığında, para birimi kontrolü, yuvarlama kuralları ve geçersiz negatif değerlerin engellenmesi gibi kuralları tek bir yere hapsedebilirsin. Anemik modellerin en büyük dertlerinden biri, iş kavramlarını ilkel tiplerle (string, int, decimal) temsil etmektir — buna **primitive obsession** (ilkel tip saplantısı) denir. Value object bunun panzehiridir.

### Aggregate: Tutarlılık sınırının kalbi

#### Tanım

Aggregate, birlikte bir bütün olarak ele alınması gereken, tutarlılık kurallarını (invariant) birlikte koruyan entity ve value object kümesidir. Her aggregate'in bir **aggregate root** (kök) adı verilen tek bir giriş kapısı entity'si vardır. Dış dünya aggregate'in içindeki nesnelere doğrudan değil, **yalnızca kök üzerinden** erişebilir ve değişiklik yapabilir.

#### Kök neden: Aggregate neden var?

Bu, DDD'nin en yanlış anlaşılan ama en güçlü kavramıdır. Aggregate'in var oluş nedeni **tutarlılık (invariant) korumaktır.** Bir invariant, her zaman doğru kalması gereken bir iş kuralıdır. Örnek: "Bir siparişin toplam tutarı, kalemlerinin toplamına eşit olmalıdır" ya da "Bir siparişte en az bir kalem bulunmalıdır."

Eğer sipariş ve sipariş kalemlerine dış kodun herhangi bir yerden serbestçe eriştiğini düşünürsen, bu kuralı korumak imkânsız hale gelir; birileri kalem ekler ama toplamı güncellemeyi unutur, tutarlılık bozulur. Aggregate der ki: **Order aggregate'ini bir kutu gibi düşün. İçine el uzatamazsın. `order.addLine(...)` çağırırsın, kök hem kalemi ekler hem toplamı günceller hem de kuralları kontrol eder.** Böylece geçersiz durum oluşması yapısal olarak engellenir.

Aggregate ayrıca **transaction sınırıdır.** Genel kural: bir transaction'da yalnızca bir aggregate örneği değiştirilmelidir. Bunun nedeni hem tutarlılık hem ölçeklenebilirliktir. Bir aggregate, tek bir transaction içinde atomik olarak tutarlı tutulur (strong consistency). Farklı aggregate'ler arasında ise genellikle **eventual consistency** (nihai tutarlılık) kabul edilir, yani değişiklik domain event'ler aracılığıyla bir süre sonra yansır.

#### Somut örnek

Bir `Order` (sipariş) aggregate'i düşünelim:

- Aggregate root: `Order`
- İçindeki nesneler: `OrderLine` (kalem) listesi (bunlar entity ya da value object olabilir), `ShippingAddress` (value object), `Money total` (value object).

İnvariantlar: toplam tutar kalemlerin toplamına eşit; sipariş onaylandıktan sonra kalem eklenemez; kalem adedi sıfırdan büyük olmalı.

Dışarıdan yapılan tek doğru erişim şudur:

```
order.addLine(productId, quantity, unitPrice);
order.confirm();
```

Yanlış olan şudur: `order.getLines().add(new OrderLine(...))` — bu, kökü atlayıp içeri doğrudan müdahale eder ve toplamın güncellenmemesine yol açar. Bu yüzden iyi tasarlanmış aggregate'lerde iç koleksiyonlar dışarıya değiştirilemez (unmodifiable) olarak verilir.

#### Aggregate boyutu: En kritik tasarım kararı

Aggregate tasarımının en zor ve en önemli kısmı **boyut**tur. Yaygın hata, aggregate'leri fazla büyük tutmaktır. Yeni başlayanlar sıklıkla "müşteri ve tüm siparişleri" ya da "kategori ve altındaki tüm ürünler" gibi doğal görünen ama devasa aggregate'ler kurar. Bunun bedeli ağırdır: Böyle bir aggregate'i yüklemek büyük veri getirir, aynı anda birçok kullanıcı onu değiştirmek isteyince kilitlenme (contention) ve optimistic locking çakışmaları artar, performans çöker.

Modern DDD pratiğinin rehber ilkeleri şunlardır:

- **Aggregate'leri mümkün olduğunca küçük tut.** Sadece gerçekten aynı transaction'da birlikte tutarlı kalması **zorunlu** olan şeyleri bir aggregate'e koy.
- **Aggregate'ler arası referansları doğrudan nesne referansıyla değil, kimlikle (ID) tut.** `Order` içinde `Customer customer` yerine `CustomerId customerId` tutmak daha doğrudur. Böylece aggregate'ler birbirine yapışmaz, ayrı yüklenip ayrı ölçeklenebilir.
- **Bir invariant iki aggregate'i kapsıyorsa,** ya modelin sınırlarını yeniden düşün ya da o tutarlılığı eventual consistency ve domain event ile sağla.

### Repository

Repository, aggregate'leri kalıcı depodan (veritabanı) alıp veren, ama bunu bir koleksiyon soyutlamasıyla yapan kalıptır. `orderRepository.findById(id)` ve `orderRepository.save(order)` gibi. Kritik nokta: **Repository'ler aggregate root başına tanımlanır**, her tablo için değil. `OrderLineRepository` diye bir şey olmamalıdır; kalemlere `Order` üzerinden erişilir. Repository, domain modelini kalıcılık teknolojisinin ayrıntılarından yalıtır; domain kodu SQL, ORM ya da NoSQL bilmez.

### Domain Service ve Domain Event

Her davranış bir entity ya da value object'e doğal olarak yerleşmez. Birden fazla aggregate'i ilgilendiren, bir iş kuralı olan ama tek bir nesneye ait olmayan işlemler **domain service** içine konur. Örneğin "para transferi" iki hesabı ilgilendirir ve tek başına ne bir hesaba ne diğerine ait olur. Dikkat: domain service, iş kurallarını içerir; uygulama akışını yöneten application service'ten farklıdır.

**Domain event** (alan olayı), iş alanında olan, önem taşıyan bir şeyin geçmiş zaman kipiyle ifadesidir: `OrderConfirmed`, `PaymentReceived`, `PolicyCancelled`. Domain event'ler DDD'nin modern kullanımında merkezî hale gelmiştir çünkü bounded context'ler arası ve aggregate'ler arası **gevşek bağlı (loosely coupled)** iletişimi mümkün kılar. Bir aggregate değiştiğinde bir event yayar; başka bağlamlar bu event'e tepki vererek kendi tutarlılıklarını nihai olarak sağlar. Bu, eventual consistency'nin pratik uygulama biçimidir ve event-driven mimarilerin temelidir.

## Yaygın hatalar

**1. DDD'yi her yerde uygulamaya çalışmak.** DDD'nin bedeli vardır: daha fazla düşünme, daha fazla soyutlama, iş uzmanlarıyla yoğun çalışma. Bu yatırım yalnızca **karmaşıklığın gerçekten iş alanında olduğu** yerlerde geri döner. Basit bir CRUD uygulaması (form doldur, kaydet, listele) için DDD kurmak fazladan yüktür. DDD'yi çekirdek alt alana (core domain) — yani işi rakiplerden ayıran, en değerli ve en karmaşık kısma — sakla; generik ve destekleyici alt alanlarda daha hafif yaklaşımlar kullan.

**2. Anemik domain model.** DDD'yi kâğıt üzerinde uygulayıp entity'leri hâlâ davranışsız veri torbaları olarak bırakmak, en yaygın ve en sinsi hatadır. İş kuralları hâlâ service katmanına kaçmışsa, ne aldığın "domain" isimleri ne de repository'ler seni kurtarır; sadece anemik modeli DDD kostümüyle giydirmiş olursun.

**3. Aggregate'leri çok büyük tasarlamak.** Yukarıda ayrıntısıyla anlatıldı. Belki de taktiksel düzeyde en pahalı hata budur; performans ve eşzamanlılık sorunlarının başlıca kaynağıdır.

**4. Aggregate'ler arası doğrudan nesne referansı tutmak.** Bu, aggregate sınırlarını fiilen ortadan kaldırır, lazy loading zincirleri ve devasa nesne grafikleri doğurur.

**5. Tek bir kurumsal (canonical) model dayatmak.** Bounded context'i reddedip "herkes aynı Customer'ı kullansın" demek, DDD'nin en değerli fikrini çöpe atmaktır ve büyük ölçekte kaçınılmaz olarak çamur topuna götürür.

**6. Ubiquitous language'i sadece dokümanda bırakmak.** Sözlük yazıp kodda `status = 3` kullanmaya devam etmek, dilin tüm faydasını yok eder. Dil kodda yaşamıyorsa, ubiquitous değildir.

**7. Teknik katmanları bounded context sanmak.** "Frontend context", "database context" gibi bölmeler bounded context değildir. Bounded context **iş alanına** göre bölünür (satış, envanter, faturalama), teknik katmanlara göre değil.

## En iyi pratikler

**İş uzmanlarıyla gerçekten konuş.** DDD'nin kalbi teknik değil, sosyaldir. Ubiquitous language ve doğru bounded context'ler ancak iş uzmanlarıyla yoğun, sürekli diyalogla ortaya çıkar. **Event Storming** gibi atölye teknikleri, bir iş sürecini domain event'ler üzerinden birlikte keşfetmek ve bounded context sınırlarını doğal biçimde bulmak için çok etkilidir; ekibi ve iş uzmanlarını aynı odada (ya da sanal panoda) buluşturur.

**Önce sınırları, sonra iç yapıyı tasarla.** Stratejik tasarım (bounded context, context map) taktiksel kalıplardan önce gelmelidir. Yanlış sınırlar üzerine kurulmuş mükemmel aggregate'ler işe yaramaz. Sınırları bulmanın iyi bir ipucu: dilin nerede değiştiğine, aynı kelimenin nerede farklı anlam kazandığına bak. Dilin kırıldığı yer, muhtemelen bir bounded context sınırıdır.

**Aggregate'leri küçük tut ve ID ile bağla.** Bu tek ilke bile taktiksel düzeyde birçok soruna karşı sigortadır. "Bu iki şey gerçekten aynı anda, aynı transaction'da tutarlı kalmak zorunda mı?" sorusunu her seferinde dürüstçe sor. Cevap "hayır"sa, ayrı aggregate'ler yap.

**Value object'leri cömertçe kullan.** İş alanındaki her anlamlı kavramı (para, tarih aralığı, e-posta, kimlik numarası, koordinat) kendi value object'iyle temsil et. Bu, primitive obsession'ı önler, kuralları merkezileştirir ve modeli hem güvenli hem okunur kılar.

**Domain'i altyapıdan yalıt.** Domain katmanı; framework, veritabanı, HTTP ve mesajlaşma ayrıntılarından habersiz kalmalıdır. Hexagonal architecture (ports and adapters) ya da benzeri katmanlı yaklaşımlar DDD ile çok iyi eşleşir: domain merkezde saf kalır, teknoloji kenarlarda adapter olarak durur. Böylece iş kuralları test edilebilir, uzun ömürlü ve teknoloji değişimlerine dayanıklı olur.

**DDD'yi bir yolculuk olarak gör, tek seferlik bir tasarım olarak değil.** Model, iş alanı hakkındaki anlayış derinleştikçe evrilir. İlk bounded context sınırları ya da aggregate boyutları yanlış çıkabilir; bu normaldir. Önemli olan, dilin ve modelin sürekli rafine edilmesidir. Evans'ın deyimiyle bu bir "refactoring toward deeper insight" (daha derin kavrayışa doğru yeniden düzenleme) sürecidir.

## Kapanış

Domain-Driven Design'ın özü tek bir cümlede toplanabilir: **Karmaşık bir iş alanını, o alanın kendi diline ve mantığına sadık kalarak, doğru sınırlar içinde modelle.** Ubiquitous language bu sadakati dil düzeyinde, bounded context sınır düzeyinde, aggregate ise tutarlılık düzeyinde sağlar. Taktiksel kalıplar (entity, value object, repository, domain service, domain event) bu fikirleri koda döken araçlardır.

DDD sihirli bir çözüm değildir ve her projeye uymaz; bedeli, yalnızca gerçek iş karmaşıklığı karşısında geri döner. Ama doğru yerde uygulandığında, yıllar boyunca değiştirilebilir, anlaşılır ve iş gerçeğiyle uyumlu kalan sistemler üretmenin en olgun yollarından biridir. En büyük değeri de belki şudur: seni, kod yazmadan önce iş alanını gerçekten anlamaya zorlar.
