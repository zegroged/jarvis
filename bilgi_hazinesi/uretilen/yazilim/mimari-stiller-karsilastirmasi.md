# Mimari Stiller Karşılaştırması: Hexagonal, Onion, Clean Architecture, Katmanlı, Modular Monolit ve Serverless

## Giriş: Neden Bu Ayrım Önemli?

Yazılım camiasında "monolit mi mikroservis mi" tartışması o kadar çok yer kaplar ki, bunların *altında* yatan asıl mimari desenler gölgede kalır. Oysa monolit de olsan, mikroservis de olsan, her bir servisin veya modülün *içinde* bir iç mimari kurmak zorundasın. İşte Hexagonal Architecture, Clean Architecture, Onion Architecture, Modular Monolith ve Serverless/FaaS mimarisi tam olarak bu seviyeyi cevaplar: kod tabanının içinde bağımlılıkların nasıl aktığı, iş kuralının teknik detaylardan nasıl izole edildiği ve deployment biriminin nasıl tanımlandığı.

Bu makalenin amacı bu desenleri birbirine karıştırmadan, aralarındaki gerçek farkları ve ne zaman hangisini seçmeniz gerektiğini, kök nedenleriyle birlikte açıklamaktır.

## Ortak Kök Problem: Bağımlılıkların Yönü

Bütün bu mimari stillerin çözmeye çalıştığı tek bir temel problem var: **iş mantığınız, veritabanına, web çerçevesine (framework) ve dış servislere sıkı sıkıya bağlı hale geldiğinde, kodunuz test edilemez, değiştirilemez ve anlaşılamaz hale gelir.**

Klasik bir örnek: `OrderService` sınıfınız doğrudan `SqlConnection` açıyor, doğrudan `HttpClient` ile bir ödeme API'sine istek atıyor ve doğrudan ASP.NET'in `HttpContext`'ini kullanıyorsa, bu sınıfı test etmek için gerçek bir veritabanına ve gerçek bir ağ bağlantısına ihtiyacınız olur. Framework'ü değiştirmek isterseniz iş mantığınızın %80'ini yeniden yazmanız gerekir. Bu, **"bağımlılığın yanlış yöne akması"** (dependency pointing the wrong way) sorunudur: yüksek seviyeli politika (iş kuralı), düşük seviyeli detaylara (veritabanı, framework, ağ) bağımlı hale gelmiştir.

Robert C. Martin'in **Dependency Inversion Principle (DIP)**'i tam olarak bunu tersine çevirir: bağımlılık oku her zaman *detaydan soyutlamaya* doğru akmalı, iş mantığı hiçbir zaman somut bir altyapı sınıfını bilmemeli, sadece kendi tanımladığı bir arayüzü (interface/port) bilmeli. Hexagonal, Clean ve Onion mimarilerinin üçü de bu tek prensibin farklı sunumlarıdır. Aralarındaki fark; katman isimlendirmesi, çember sayısı ve vurgu noktasıdır — mekanizma aynıdır.

## Katmanlı Mimari (Layered / N-Tier Architecture)

### Tanım ve Çalışma Mantığı

En eski ve en yaygın bilinen desendir: Sunum (Presentation) → İş Mantığı (Business/Service) → Veri Erişimi (Data Access) → Veritabanı. Her katman yalnızca bir alt katmanı çağırır, üst katmanı asla bilmez.

### Kök Sorun: Tek Yönlü Ama Aşağıya Sızan Bağımlılık

Katmanlı mimarinin klasik hâlinde bağımlılık oku *aşağı* doğru akar: UI → Service → Repository → DB. Bu, ilk bakışta düzenli görünür ama kritik bir kusuru vardır: **iş mantığı katmanı (Service), veri erişim katmanına (Repository) somut olarak bağımlıdır.** Yani `OrderService`, `SqlOrderRepository`'yi doğrudan `new`ler veya somut sınıf olarak enjekte eder. Bu, DIP'i ihlal eder çünkü "yüksek seviye modül" (iş kuralı) "düşük seviye modülün" (SQL detayları) varlığına bağımlı kalır.

Pratikte bunun sonucu şudur: veritabanı teknolojisini değiştirmek, iş mantığı katmanını da etkiler; iş mantığını veritabanı olmadan test etmek zorlaşır (mock'lamak gerekir ama arayüz sözleşmesi net değildir, genelde somut sınıflar mock'lanır).

### Doğru Kullanım ve En İyi Pratikler

- Katmanlı mimari, **basit CRUD ağırlıklı, karmaşık iş kuralı içermeyen** uygulamalarda son derece uygundur. Her yere Hexagonal kurmak gereksiz karmaşıklıktır (over-engineering).
- "Katı katmanlı" (strict layering) kuralına uyun: bir katman sadece hemen altındaki katmanı çağırabilsin, katlar atlanmasın (UI'ın doğrudan Repository'yi çağırması gibi).
- Repository katmanı için en azından bir arayüz (`IOrderRepository`) tanımlayıp Service katmanının somut sınıfa değil arayüze bağımlı olmasını sağlarsanız, katmanlı mimari ile Onion/Hexagonal arasındaki farkı büyük ölçüde kapatmış olursunuz.

### Yaygın Hatalar

- **"Anemic domain model" + "fat service" kombinasyonu**: Domain nesneleri sadece veri taşıyıcısı (getter/setter) haline gelir, tüm mantık Service katmanına yığılır. Bu, nesne yönelimli tasarımın faydasını sıfırlar.
- **Katman atlama**: Performans bahanesiyle Controller'ın doğrudan Repository'yi çağırması, zamanla mimariyi "spagetti"ye çevirir.
- **Service katmanının framework'e bağımlı hale gelmesi**: `HttpContext.Current` gibi web framework detaylarının iş mantığına sızması.

## Hexagonal Architecture (Ports & Adapters)

### Tanım

Alistair Cockburn tarafından 2005 civarında tanımlanmıştır. Merkezde uygulamanın çekirdeği (application core / domain) bulunur; bu çekirdek dış dünyayla yalnızca **port** adı verilen arayüzler üzerinden konuşur. Portların gerçek dünyaya bağlanan somut uygulamalarına **adapter** denir. "Hexagonal" (altıgen) ismi mimari bir zorunluluk değil, sadece "birden fazla kenarı olabilir" fikrini görselleştirmek için seçilmiştir — altıgenin altı kenarının özel bir anlamı yoktur.

### Kök Neden / Çalışma Mantığı

Hexagonal'ın temel içgörüsü şudur: **"dışarıdan içeri" ve "içeriden dışarı" olan iki farklı bağımlılık türü vardır ve ikisi de aynı mekanizmayla (port arayüzü) tersine çevrilebilir.**

- **Driving/Primary port**: Dış dünyanın uygulamayı *tetiklediği* taraf (örn. bir REST controller'ın çağırdığı `PlaceOrderUseCase` arayüzü). Adapter burada "dışarıdan gelen" taraftır (HTTP controller, CLI, mesaj tüketicisi).
- **Driven/Secondary port**: Uygulamanın dışarıyı *tetiklediği* taraf (örn. `OrderRepository` arayüzü). Adapter burada "uygulamanın çağırdığı" taraftır (Postgres implementasyonu, e-posta gönderme servisi).

Kritik nokta: her iki yönde de **arayüz çekirdek tarafında tanımlanır**, implementasyon dışarıda kalır. Böylece testte gerçek bir HTTP sunucusu veya gerçek bir veritabanı olmadan, portların yerine sahte (fake/in-memory) adapter'lar takarak çekirdeği tamamen izole test edebilirsiniz.

### Doğru Kullanım, Tuzaklar, En İyi Pratikler

- **Ne zaman kullanılır**: İş kuralı karmaşık, birden fazla giriş kanalı var (REST + mesaj kuyruğu + CLI), ve/veya altyapı teknolojisinin gelecekte değişmesi bekleniyor (örn. şu an MySQL, ileride DynamoDB'ye geçiş planı var).
- **Tuzak — "port patlaması"**: Her metod için ayrı bir port arayüzü tanımlamak, gereksiz soyutlama katmanları yaratır. Portlar iş yeteneğine (use case) göre gruplanmalı, teknik metoda göre değil.
- **Tuzak — sızan soyutlama**: Port arayüzü, belirli bir veritabanının sorgu diline (örn. SQL'e özgü filtreleme sözdizimi) göre tasarlanırsa, "adapter değiştirilebilir" vaadi kağıt üzerinde kalır. Port, *iş ihtiyacını* ifade etmeli (`findActiveOrdersForCustomer`), *teknik detayı* değil (`executeQuery(sql: string)`).
- **En iyi pratik**: Port arayüzlerini domain'in kendi terimleriyle (ubiquitous language) adlandırın, altyapı terimleriyle değil.

### Yaygın Hatalar

- Adapter içine iş kuralı sızdırmak (örn. bir REST controller'ın kendi içinde indirim hesaplaması yapması).
- Port sayısını gereğinden fazla artırıp mimariyi anlaşılmaz hale getirmek ("mimari için mimari" tuzağı — YAGNI ihlali).

## Onion Architecture

### Tanım

Jeffrey Palermo tarafından tanımlanmıştır. İç içe geçmiş halkalar (soğan katmanları) şeklinde görselleştirilir: en merkezde **Domain Model** (entity'ler, value object'ler), onun etrafında **Domain Services**, onun etrafında **Application Services**, en dışta **Infrastructure ve UI**.

### Kök Neden / Çalışma Mantığı

Onion'ın Hexagonal'dan farkı, teknik anlamda çok küçüktür — ikisi de DIP'e dayanır — ama **vurgu noktası farklıdır**: Onion, "merkeze doğru giden bağımlılık kuralını" (her katman sadece kendinden içteki katmana bağımlı olabilir, asla dışarıdakine) çok daha katı ve açık şekilde ifade eder. Kural basit: **oku her zaman içe doğru çiz, asla dışa değil.**

Pratikte bu şu anlama gelir: Domain katmanı hiçbir şeyi (ne ORM'i ne HTTP'yi ne de Application katmanını) bilmez; sadece saf iş kurallarını içerir. Application Services katmanı Domain'i bilir ama Infrastructure'ı bilmez (arayüz üzerinden konuşur). Infrastructure en dışta olur ve *her şeyi* bilebilir çünkü o "detaydır", değiştirilebilir olan taraftır.

### Doğru Kullanım, Tuzaklar

- Onion, özellikle **zengin domain modeli** (rich domain model, DDD ile uyumlu) olan sistemlerde nettir çünkü "Domain Model en merkezde ve hiçbir dış bağımlılığı yok" kuralını somut bir görsel/organizasyonel yapıya oturtur.
- **Tuzak**: Katman sayısını dogmatik şekilde arttırmak. Onion'ın 4 halkası bir zorunluluk değil, bir referans noktasıdır; küçük projede 3 halka yeterli olabilir.
- **En iyi pratik**: Domain katmanına *hiçbir* NuGet/npm paketi (ORM, JSON serializer, framework) referansı eklenmemesi kuralını statik analiz veya derleme zamanı bağımlılık kontrolüyle (dependency-cruiser, ArchUnit, NetArchTest gibi araçlarla) otomatik denetlemek. Bu kuralı sadece "disiplinle" tutmaya çalışmak, zamanla ihlal edilir.

## Clean Architecture

### Tanım

Robert C. Martin ("Uncle Bob") tarafından, Hexagonal ve Onion'ın fikirlerini birleştirip isimlendiren, dört halkalı (Entities → Use Cases → Interface Adapters → Frameworks & Drivers) bir modeldir.

### Kök Neden / Çalışma Mantığı

Clean Architecture'ın kendine has katkısı **"The Dependency Rule"**'un açık formülasyonu ve **Use Case** kavramının merkeze alınmasıdır:

- **Entities**: Kurumsal çapta, en genel iş kuralları (herhangi bir uygulamadan bağımsız olarak var olan gerçekler — örn. "bir siparişin toplamı, kalemlerin toplamına eşittir").
- **Use Cases (Interactors)**: Bu uygulamaya özgü iş akışları (örn. "SiparişOluştur", "SiparişİptalEt"). Entity'leri kullanarak uygulamaya özel iş kuralını uygular.
- **Interface Adapters**: Controller'lar, Presenter'lar, Gateway'ler — veriyi Use Case'in istediği formattan dış dünyanın (web, DB) istediği formata çevirir.
- **Frameworks & Drivers**: En dışta, Web framework'ü, DB, UI.

Kritik ayrım noktası, Hexagonal'ın "port/adapter" ikilisine kıyasla Clean Architecture'ın **Use Case seviyesini ayrı bir birinci sınıf katman olarak isimlendirmesidir.** Bu, "domain mantığı" ile "bu uygulamaya özgü iş akışı mantığı"nı ayırt etmenizi zorunlu kılar — DDD terminolojisiyle söylersek, Entity saf domain kuralını taşırken, Use Case bir **application service**'in yaptığı orkestrasyonu taşır.

Ayrıca Clean Architecture, veri sınırları arası geçişte **DTO benzeri veri yapıları (Input/Output boundary)** kullanılmasını öngörür: Use Case, Entity nesnesini doğrudan dışarı sızdırmaz, kendi tanımladığı çıktı modelini döndürür. Bu, iç domain modelinin dış dünyaya (örn. bir REST API response şemasına) sıkı bağlanmasını önler — aksi halde domain modelinizdeki her değişiklik, API sözleşmenizi kırar.

### Doğru Kullanım, Tuzaklar, En İyi Pratikler

- **Ne zaman kullanılır**: Uzun ömürlü, iş kuralı karmaşık, birden fazla teslimat mekanizması (web + mobil API + batch job) olması beklenen sistemlerde.
- **Tuzak — "Anemic Use Case"**: Use Case sınıfının sadece Repository çağrısını yönlendiren ince bir kabuk olması, gerçek katma değer yaratmaması. Bu durumda Use Case katmanı gereksiz bir dolaylama (indirection) haline gelir.
- **Tuzak — DTO patlaması**: Her Use Case için ayrı Input/Output modeli tanımlamak, çok sayıda neredeyse birbirinin aynı sınıf üretebilir; bu, bakım yükünü artırır. Pragmatik ekipler, düşük riskli alanlarda bu kuralı gevşetir.
- **En iyi pratik**: "Screaming Architecture" ilkesini uygulayın — klasör yapınıza baktığınızda framework'ü değil, *uygulamanın ne yaptığını* görebilmelisiniz (`use_cases/place_order`, `use_cases/cancel_order` gibi, `controllers/`, `models/` gibi değil).

### Yaygın Hatalar

- Controller'ların Entity'yi doğrudan JSON'a serialize etmesi (Interface Adapter katlanmasının atlanması).
- Use Case'lerin birbirini doğrudan çağırması (bu, gizli bir bağımlılık zinciri yaratır; orkestrasyon için ayrı bir "orchestrator" veya event tabanlı yaklaşım tercih edilmelidir).

## Hexagonal vs Onion vs Clean: Pratik Fark Var mı?

Dürüst olmak gerekirse: **üçü de aynı DIP prensibinin farklı sunumlarıdır ve modern literatürde genellikle "aynı ailenin" üyeleri sayılır.** Aralarındaki pratik fark şudur:

| Boyut | Hexagonal | Onion | Clean |
|---|---|---|---|
| Vurgu | Port/Adapter simetrisi (driving/driven ayrımı) | İç içe katman disiplini, domain'in saflığı | Use Case'in birinci sınıf vatandaş olması, sınır (boundary) veri modelleri |
| En güçlü olduğu senaryo | Çok kanallı giriş/çıkış (REST+queue+CLI) | DDD ağırlıklı, zengin domain modeli | Karmaşık uygulama iş akışları, uzun ömürlü sistemler |
| Terminoloji riski | "Altıgen" kelimesi yanlış anlaşılıp altı adet port zorunluymuş gibi algılanabilir | Katman sayısı dogmatik hale getirilebilir | Katman sayısı fazla gelip küçük projede over-engineering yaratabilir |

Gerçek mühendislik kararında bu üçü arasında seçim yapmak, isim tartışmasından çok, **ekibin DIP'i doğru uygulayıp uygulamadığını** denetlemekle ilgilidir. Hangi isim kullanılırsa kullanılsın, test edilebilirlik ve framework bağımsızlığı elde edilemiyorsa mimari amacına ulaşmamış demektir.

## Modular Monolith (Modüler Monolit)

### Tanım

Tek bir deployment birimi (tek process, tek dağıtım artefaktı) içinde, kod tabanının **net modül sınırlarıyla** bölündüğü, modüller arası iletişimin yalnızca tanımlı arayüzler (ve genellikle in-process event'ler) üzerinden yapıldığı yaklaşımdır.

### Kök Neden / Çalışma Mantığı

Modular Monolith, mikroservislere geçişin "her modülü network sınırıyla ayırma" maliyetini (dağıtık sistem karmaşıklığı, ağ gecikmesi, dağıtık transaction problemi, operasyonel yük) ödemeden, **modülerliğin asıl faydasını** (bağımsız geliştirilebilir, anlaşılır, test edilebilir sınırlar) elde etmeyi hedefler.

Kök neden şudur: birçok ekip mikroservise, "kodumuz spagetti oldu, modüller birbirine karıştı" sorununu çözmek için geçer. Ama bu sorunun kökü *deployment birimi* değil, **modül sınırlarının disiplinsiz olmasıdır.** Mikroservise geçmek bu disiplini zorla dayatır (ağ sınırı, kod paylaşımını fiziksel olarak imkânsız kılar) ama bunun bedeli çok yüksektir. Modular Monolith, aynı disiplini *derleme zamanı ve kod inceleme disiplini* ile, network maliyeti ödemeden sağlamaya çalışır.

Pratik mekanizma: her modül kendi klasöründe yaşar, kendi (mantıksal) veritabanı şemasına/tablo grubuna sahiptir, dışarıya sadece açık bir genel arayüz (public API) sunar; diğer modüller bu modülün iç sınıflarına veya tablolarına doğrudan erişemez. Bu genellikle derleme zamanı erişim kontrolü (internal/package-private modifier'lar) veya statik analiz araçlarıyla (ArchUnit, dependency-cruiser, Moduliths gibi) zorunlu kılınır.

### Doğru Kullanım, Tuzaklar, En İyi Pratikler

- **Ne zaman kullanılır**: Ekip henüz "hangi sınırların gerçek servis sınırı olması gerektiğini" net bilmiyorsa (yani domain sınırları hâlâ netleşiyorsa) Modular Monolith, mikroservise göre çok daha ucuz bir "sınırları deneme" ortamı sunar. Sınır yanlış çizildiyse, kod içinde klasör taşımak, ayrı bir servisi yeniden yazmaktan çok daha ucuzdur.
- **En iyi pratik**: Modüller arası senkron çağrı yerine mümkün olduğunca in-process event/domain event kullanmak, ileride bu event'leri gerçek bir mesaj kuyruğuna taşımayı kolaylaştırır (mikroservise geçiş "kolay yol" haline gelir).
- **Tuzak — "gizli monolit"**: Modül sınırları sadece klasör düzeyinde var olur ama kod hâlâ birbirinin private sınıflarına, hatta birbirinin veritabanı tablolarına doğrudan SQL join ile erişir. Bu, "modular" adı taşıyan ama aslında disiplinsiz bir klasik monolittir — en yaygın başarısızlık nedenidir.
- **Tuzak — paylaşılan veritabanı şeması**: Modüller ayrı görünse de tek şemada birbirinin tablosuna FK ile bağlıysa, gerçek bağımsızlık yoktur; bir modülün şema değişikliği diğerini kırar.

### Yaygın Hatalar

- Modül sınırlarını statik analiz ile denetlemeden sadece "iyi niyet" ile tutmaya çalışmak (zamanla erozyona uğrar).
- "Shared kernel" (ortak modül) klasörünü çöp kutusu haline getirip her modülün ona bağımlı hale gelmesi — bu, gizli bir "herkes herkese bağımlı" grafiği yaratır.

## Serverless / FaaS Mimarisi

### Tanım

Function-as-a-Service (AWS Lambda, Azure Functions, Google Cloud Functions gibi) modelinde, geliştirici sunucu yönetimi yapmaz; kodu, tetikleyici bir olaya (HTTP isteği, kuyruk mesajı, zamanlanmış iş) bağlı, kısa ömürlü, durumsuz (stateless) fonksiyonlar halinde yazar. Platform, ölçeklendirmeyi, provisioning'i ve altyapı yönetimini üstlenir.

### Kök Neden / Çalışma Mantığı

Serverless'in temel varsayımı **"her fonksiyon çağrısı bağımsız ve durumsuzdur"** ilkesidir. Bu, iki temel mimari sonucu doğurur:

1. **Cold start problemi**: Fonksiyon bir süre çağrılmadıysa, platform onun çalışma ortamını (process/container) kapatır. Yeni bir çağrı geldiğinde bu ortam sıfırdan ayağa kaldırılmalıdır (cold start), bu da gecikme yaratır. Kök neden, platformun kaynak verimliliği için boşta duran ortamları geri almasıdır — bu, serverless'in "kullandığın kadar öde" faydasının doğal bedelidir.
2. **Durum paylaşımı için dış bağımlılık zorunluluğu**: Fonksiyonlar arası veya çağrılar arası durum paylaşımı in-memory yapılamaz (her çağrı potansiyel olarak farklı bir ortamda çalışabilir); bu yüzden durum her zaman harici bir depoya (DB, cache, kuyruk) taşınmalıdır. Bu, mimariyi doğal olarak **event-driven** ve **her fonksiyonun tek bir sorumluluğu olduğu** (single-purpose function) bir yapıya iter.

### Doğru Kullanım, Tuzaklar, En İyi Pratikler

- **Ne zaman kullanılır**: Trafiği düzensiz/patlamalı (bursty) olan iş yükleri, olay güdümlü entegrasyonlar (dosya yüklenince işleme, kuyruk mesajı geldiğinde tetiklenme), düşük-orta trafikli API'ler. Sürekli yüksek ve öngörülebilir trafik olan sistemlerde maliyet avantajı genelde kaybolur — konteyner/sunucu bazlı modelle karşılaştırıldığında sürekli çalışan yükte serverless daha pahalıya gelebilir.
- **Tuzak — "dağıtık monolit" (distributed monolith) fonksiyon versiyonu**: Fonksiyonlar birbirini senkron olarak zincirleme çağırırsa (Fonksiyon A → Fonksiyon B → Fonksiyon C, hepsi senkron HTTP ile), mikroservislerdeki aynı hastalık (yüksek bağlaşıklık, kademeli hata yayılımı, izlenebilirlik kaybı) FaaS dünyasında da ortaya çıkar. Kök neden aynıdır: deployment birimini bölmek otomatik olarak gevşek bağlaşıklık (loose coupling) getirmez; bağlaşıklık iletişim şekline bağlıdır (senkron çağrı zinciri vs. asenkron event).
- **Tuzak — vendor lock-in**: Fonksiyon kodunun platforma özgü SDK'lara ve event formatlarına doğrudan bağımlı yazılması, iş mantığını platforma kilitler. Burada da yine Hexagonal'daki port/adapter mantığı uygulanabilir: iş mantığı platform event formatını değil, kendi tanımladığı bir arayüzü bilmeli; platforma özgü adaptasyon ince bir "handler" katmanında kalmalı.
- **En iyi pratik**: Fonksiyon içindeki iş mantığını, fonksiyonun tetikleyicisinden (trigger) ayırın. `handler(event) { const input = parseX(event); return core.doWork(input); }` şeklinde ince bir adapter katmanı, `core.doWork` fonksiyonunu tetikleyiciden (HTTP mi, kuyruk mu) bağımsız ve test edilebilir tutar.
- **Gözlemlenebilirlik (observability) zorunluluğu**: Kısa ömürlü, dağıtık, çok sayıda fonksiyon olduğunda geleneksel log/debug yöntemleri yetersiz kalır; dağıtık izleme (distributed tracing, correlation ID) serverless'te opsiyonel değil, temel gerekliliktir.

### Yaygın Hatalar

- Fonksiyonlar arası paylaşılan mutable state varsayımı (örn. global değişkende cache tutup her çağrıda var olacağını varsaymak) — cold start sonrası bu state kaybolur, tutarsız davranışa yol açar.
- Aşırı ince fonksiyon bölünmesi ("nanoservice" tuzağı): her satırlık işlem için ayrı fonksiyon açmak, çağrılar arası gecikmeyi ve operasyonel karmaşıklığı gereksiz artırır.

## Seçim Kriterleri: Hangi Durumda Hangisi?

Mimari seçimi bir moda meselesi değil, somut mühendislik kısıtlarına göre yapılmalıdır:

- **İş kuralı basit, CRUD ağırlıklı, küçük ekip**: Klasik Katmanlı Mimari yeterlidir; Hexagonal/Clean kurmak gereksiz soyutlama maliyetidir.
- **İş kuralı karmaşık, birden fazla giriş kanalı, uzun ömürlü sistem, teknoloji değişimi bekleniyor**: Hexagonal/Onion/Clean ailesinden biri — hangisinin seçileceği çoğunlukla ekip alışkanlığı ve terminoloji tercihidir, mekanizma aynıdır.
- **Domain sınırları henüz netleşmemiş ama gelecekte servislere bölünme ihtimali var**: Modular Monolith, hem bugünün operasyonel basitliğini korur hem de yarının bölünmesini ucuzlatır.
- **Trafik düzensiz/patlamalı, olay güdümlü, küçük bağımsız işlemler**: Serverless/FaaS; ama fonksiyonlar arası senkron zincirleme çağrıdan kaçınılmalı.

Bu beş/altı yaklaşım birbirini dışlamaz — üstelik genellikle iç içe kullanılır: bir Modular Monolith'in her modülü kendi içinde Hexagonal desenle yazılabilir; bir serverless fonksiyonunun handler'ı ince bir adapter, çekirdek mantığı ise Clean Architecture'daki bir Use Case olabilir. Kritik olan isim değil, **bağımlılık okunun doğru yöne aktığını ve iş mantığının teknik detaydan izole kaldığını** her seviyede tutarlı şekilde sağlamaktır.

## Sonuç

Bu mimari stillerin hepsi, aynı kök sorunu — iş mantığının altyapı detaylarına sıkı bağlanması — farklı görsel modellerle çözer. Hexagonal port/adapter simetrisini, Onion iç içe katman disiplinini, Clean Architecture use case'in birinci sınıf statüsünü vurgular; Modular Monolith bu disiplini deployment birimi seviyesinde, Serverless ise fonksiyon ve tetikleyici seviyesinde uygular. Bir mühendis olarak doğru soru "hangi diyagramı çizeceğim" değil, "bağımlılık oku burada hangi yöne akıyor, ve bu yön iş mantığımı teknik detaydan koruyor mu" sorusudur. Bu soruyu her katmanda, her modülde ve her fonksiyonda tutarlı şekilde sorabilen bir ekip, isim ne olursa olsun sağlam bir mimari kurar.
