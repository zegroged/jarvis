# Backpressure ve Akış Kontrolü (Flow Control / Backpressure Yönetimi)

## Tanım

**Backpressure** (geri basınç), bir sistemde veri üreten tarafın (producer), veriyi tüketen taraftan (consumer) daha hızlı ürettiği durumda ortaya çıkan yük dengesizliğini yönetme mekanizmasıdır. Kavram fiziksel bir metafordan gelir: bir boruya girebileceğinden fazla su bastığınızda, borunun içinde biriken basınç geriye doğru yayılır ve pompayı yavaşlatmaya zorlar. Yazılımda da amaç aynıdır: tüketici yetişemediğinde, bu "yetişememe" sinyalinin üretici tarafa **geriye doğru** iletilmesi ve üreticinin hızını kısmasıdır.

**Flow control** (akış kontrolü) daha geniş bir şemsiye terimdir ve backpressure'ı da içerir. Akış kontrolü, iki uç arasındaki veri akış hızını düzenleyen tüm tekniklerin toplamıdır; TCP'nin `receive window` mekanizması, HTTP/2'nin `WINDOW_UPDATE` çerçeveleri, reactive streams'in `request(n)` çağrıları bunların hepsi akış kontrolü örnekleridir.

Bu konu, `Rate Limiting` ile karıştırılır ama farklıdır. Rate limiting genellikle **dışarıya bakan**, önceden belirlenmiş bir eşiğe göre isteği reddeden bir politikadır (örneğin "saniyede 100 istek"). Backpressure ise **içeriye bakan**, sistemin anlık gerçek kapasitesine göre dinamik olarak akışı ayarlayan bir mekanizmadır. Rate limiting kapıdaki bekçidir; backpressure ise binanın içindeki basınç sensörüdür.

## Kök Neden: Neden Backpressure'a İhtiyaç Var?

Her tüketicinin sonlu bir işleme kapasitesi vardır: sınırlı CPU, sınırlı bellek, sınırlı disk veya ağ bant genişliği. Üretici bu kapasiteyi aştığında iki temel şey olabilir:

1. **Sınırsız kuyruklama (unbounded buffering):** Sistem gelen fazla veriyi bir kuyrukta biriktirmeye çalışır. Bu kuyruk RAM'de büyüdükçe önce garbage collector baskısı, sonra `OutOfMemoryError` ve nihayetinde sürecin çökmesiyle sonuçlanır. Bu, en tehlikeli senaryodur çünkü çöküş ani ve topyekûndur.

2. **Veri kaybı (drop):** Sistem kapasitesi aşınca gelen veriyi sessizce atar. Bazı durumlarda (metrik, log, canlı video) kabul edilebilir; bazı durumlarda (finansal işlem, sipariş) felakettir.

Backpressure, bu ikisi arasında üçüncü bir yol sunar: **üreticiyi yavaşlatmak.** Sistemin kendisini koruması için basıncı kaynağa geri iletmesidir. Bu, kapasite planlamasının kalbindedir çünkü sistem "elimden geleni yapıyorum, sen yavaşla" diyebildiğinde, ani yük artışlarında (spike) çökmek yerine zarif biçimde (gracefully) yavaşlar.

### Little's Law ile Bağlantı

Kuyruk teorisinin temel yasası olan **Little's Law** şunu söyler: `L = λ × W`. Burada `L` sistemdeki ortalama iş sayısı, `λ` varış hızı, `W` ise bir işin sistemde geçirdiği ortalama süredir. Eğer varış hızı `λ`, işleme hızını (servis hızı) sürekli aşarsa, `L` sonsuza gider yani kuyruk sınırsız büyür ve bekleme süresi (`W`) patlar. Backpressure'ın matematiksel gerekçesi budur: varış hızını servis hızına yaklaştırarak `L`'yi sınırlı tutmak.

## Çalışma Mantığı: Backpressure Nasıl Uygulanır?

Backpressure'ı gerçekleştiren birkaç temel strateji vardır. Gerçek sistemlerde bunlar sıklıkla birlikte kullanılır.

### 1. Pull-based (Çekme temelli) Modeller

Push modelinde üretici, tüketici hazır olsun olmasın veri iter. Pull modelinde ise tüketici, işleyebileceği kadarını **talep eder**. Reactive Streams spesifikasyonu bunun kanonik örneğidir.

**Reactive Streams** (Java'da `Flow` API, Project Reactor, RxJava, Akka Streams) dört arayüz tanımlar: `Publisher`, `Subscriber`, `Subscription`, `Processor`. Kritik mekanizma `Subscription.request(n)` çağrısıdır: tüketici, yayıncıya "bana en fazla `n` eleman gönder" der. Yayıncı bu talebi aşamaz. Tüketici bir batch'i işleyip bittiğinde tekrar `request(n)` çağırır. Böylece talep, tüketicinin gerçek işleme hızına bağlanır ve backpressure otomatik olarak akış boyunca (upstream) yukarı doğru yayılır.

```java
// Kavramsal örnek: reactive streams'te talep temelli tüketim
subscription.request(10); // "Bana en fazla 10 eleman ver"

public void onNext(Item item) {
    process(item);
    // İşleme kapasitem oldukça yeni talep açıyorum
    subscription.request(1);
}
```

Burada dikkat: `request(Long.MAX_VALUE)` çağrısı pratikte backpressure'ı kapatır çünkü "sınırsız gönder" demektir. Bu, farkında olmadan yapılan yaygın bir hatadır.

### 2. Bounded Queues (Sınırlı kuyruklar)

Üretici ve tüketici arasına **sabit kapasiteli** bir kuyruk koyulur. Kuyruk dolduğunda, kuyruğa yazma işlemi ya **bloke olur** (üreticiyi bekletir, dolayısıyla yavaşlatır) ya da bir doluluk politikası devreye girer. Java'daki `ArrayBlockingQueue`, Go'daki buffered channel (`make(chan T, N)`), bu prensibi somutlaştırır.

Go'da buffered channel'a yazma, kanal doluysa gönderen goroutine'i bloke eder; bu, dilin doğal backpressure mekanizmasıdır:

```go
ch := make(chan Task, 100) // 100 kapasiteli sınırlı kuyruk
ch <- task // kanal doluysa burada bloke olur, üretici yavaşlar
```

Sınırlı kuyruğun anahtarı sonlu kapasitedir. `LinkedBlockingQueue`'yu kapasite belirtmeden oluşturmak (varsayılan `Integer.MAX_VALUE`) pratikte sınırsız kuyruk yaratır ve backpressure korumasını iptal eder; bu, üretim ortamında en sık görülen bellek sızıntısı kaynaklarından biridir.

### 3. Credit-based (Kredi temelli) Akış Kontrolü

Ağ protokollerinde yaygındır. Alıcı, göndericiye ne kadar veri kabul edebileceğini bir "kredi" veya "pencere" (window) olarak bildirir. Gönderici bu krediyi tükettikçe durur; alıcı işledikçe yeni kredi yayınlar.

- **TCP flow control:** Alıcı, `receive window` (rwnd) alanı ile "tamponumda şu kadar boş yer var" bilgisini her ACK'te gönderir. Gönderici bu pencereyi aşamaz. Pencere sıfırlandığında (`zero window`) gönderici durur ve periyodik olarak pencereyi yoklar.
- **HTTP/2 ve gRPC:** Bağlantı ve stream seviyesinde `WINDOW_UPDATE` çerçeveleriyle akış kontrolü yapar. Her stream'in kendi kredi bütçesi vardır, böylece tek bir yavaş tüketici tüm bağlantıyı tıkamaz (head-of-line blocking sorununu hafifletir).

Kredi temelli modelin gücü, akış kontrolünü **uçtan uca** (end-to-end) taşıyabilmesidir.

## Backpressure Sinyali Kaynağa Ulaşamadığında: Load Shedding

Backpressure her zaman kaynağa kadar yayılamaz. Örneğin kaynak, kontrol edemediğiniz binlerce internet istemcisidir; onları "yavaşlat" diye zorlayamazsınız. Böyle durumlarda sistemin kendini koruması için **load shedding** (yük atma) devreye girer: sistem, kapasitesini aşan işleri **bilinçli olarak reddeder** ki mevcut işleri sağlıklı tamamlayabilsin.

Load shedding, backpressure'ın "geri yayamıyorsam, keserim" versiyonudur. Temel stratejiler:

- **Fail-fast reddi:** Kuyruk veya thread havuzu doluysa isteği hemen `503 Service Unavailable` ile reddet. Bekletmektense reddetmek daha iyidir çünkü uzun bekleyen istekler zaten timeout'a düşecek ve o boşa harcanan işlem kapasitesi kaybolacaktır.
- **Öncelikli atma (priority-based shedding):** Yük altında düşük öncelikli trafiği (örneğin analitik, öneri) at, kritik trafiği (ödeme, giriş) koru.
- **Adaptive load shedding:** Sistem, gecikme (latency) veya kuyruk derinliği gibi sinyallere bakarak reddetme oranını dinamik ayarlar. Google'ın anlattığı yaklaşımlarda sunucular, artan gecikmeyi aşırı yüklenmenin işareti olarak kullanır.

### Buffer Doluluk Politikaları (Overflow Strategies)

Kuyruk dolduğunda ne yapılacağı, sistemin karakterini belirler. Yaygın politikalar:

| Politika | Davranış | Ne zaman uygun |
|---|---|---|
| **Block** | Üreticiyi bekletir | Üretici kontrol edilebiliyorsa (gerçek backpressure) |
| **Drop newest / drop tail** | En yeni geleni atar | Eski veriler daha değerliyse |
| **Drop oldest / drop head** | En eskiyi atar, yeniye yer açar | Güncel veri değerliyse (canlı metrik, telemetri) |
| **Error / fail** | Hata fırlatır | Veri kaybı asla kabul edilemezse |
| **Latest** | Sadece son değeri tutar | Anlık durum yeter (sensör, fiyat tickeri) |

Doğru politika seçimi tamamen iş gereksinimine bağlıdır ve "varsayılan" bir doğru cevap yoktur. Reactive kütüphanelerde `onBackpressureBuffer`, `onBackpressureDrop`, `onBackpressureLatest` gibi operatörler bu politikaları sağlar.

## Kapasite Planlaması ile İlişkisi

Backpressure ve kapasite planlaması iç içedir. Backpressure mekanizması size iki hayati sinyal verir:

1. **Doygunluk erken uyarısı:** Kuyruk derinliğinin sürekli artması, sistemin kapasite sınırına yaklaştığının erken göstergesidir. Bu, çöküşten önce ölçek büyütmek (scale up/out) için pencere açar.
2. **Gerçek kapasitenin ölçülmesi:** Backpressure sinyalinin ne sıklıkta tetiklendiği, sistemin gerçek işleme kapasitesini ampirik olarak ortaya koyar; teorik değil, gözlemlenen kapasiteyi.

Kapasite planlamasında hedef, tepe yükte (peak) bile kuyruğun tamamen dolmadan çalışabilmesidir. Backpressure ise bu planın **güvenlik ağıdır**: plan yanılsa bile sistem çökmez, yavaşlar.

## Tespit ve İzleme (Detection)

Backpressure sorunlarını görmek için doğru metrikleri toplamak şarttır. İzlenmesi gereken temel sinyaller:

- **Kuyruk derinliği (queue depth) ve doluluk oranı:** Sürekli yükseliyorsa üretici tüketiciyi geçiyordur. En doğrudan sinyaldir.
- **Latency dağılımı (özellikle p99, p99.9):** Kuyrukta bekleme arttıkça kuyruk gecikmesi (queueing delay) toplam gecikmeyi domine etmeye başlar. Ortalama gecikme aldatıcıdır; yüzdelik dilimlere (percentile) bakın.
- **Reddedilen / atılan istek sayısı (drop count, 503 oranı):** Load shedding'in ne kadar devreye girdiğini gösterir.
- **Thread havuzu doygunluğu ve rejected task sayısı:** `ThreadPoolExecutor`'da `RejectedExecutionException` sayısı doygunluğun net işaretidir.
- **Bellek kullanımı ve GC baskısı:** Sınırsız kuyruk kaynaklı sorunlar önce artan heap kullanımı ve GC duraklamaları olarak görünür.
- **Consumer lag (tüketici gecikmesi):** Kafka gibi log tabanlı sistemlerde tüketicinin en son offset'ten ne kadar geride olduğu; artan lag, tüketicinin yetişemediğini gösterir.

Sağlam bir tespit yaklaşımı, bu metriklere eşik temelli uyarılar (alert) bağlamaktır: örneğin "p99 latency 500 ms'yi 5 dakika aştı" veya "kuyruk doluluğu %80'i geçti".

## Doğru Kullanım ve Tuzaklar

### Doğru Kullanım İlkeleri

- **Sınırları her yerde tanımla:** Her kuyruk, her tampon, her thread havuzu **sonlu** kapasiteye sahip olmalı. "Sınırsız" varsayılanlar (unbounded queue, sınırsız buffer) gizli birer zaman bombasıdır.
- **Timeout'ları backpressure ile birleştir:** İstekler sonsuza kadar kuyrukta beklememeli. Deadline propagation (istek başladığında bir son tarih belirleyip her katmanda taşımak) sayesinde, zaten geç kalmış işler işlenmeden atılır ve boşa iş yapılmaz.
- **Backpressure'ı uçtan uca düşün:** Bir katmanda backpressure uygulayıp bir sonrakinde sınırsız kuyruk kullanmak, sadece sorunu bir sonraki katmana taşır. En zayıf halka sistemin gerçek koruma seviyesini belirler.
- **Yavaşlamayı zarif kıl:** Load shedding'de kullanıcıya net hata (`503` + `Retry-After` başlığı) döndürmek, istemcinin akıllı bir geri çekilmeyle (backoff) yeniden denemesini sağlar.

### Yaygın Hatalar ve Tuzaklar

**1. Sınırsız kuyruğu backpressure sanmak.** Fazla veriyi bir kuyruğa yığmak backpressure değildir; sadece çöküşü erteler ve büyütür. Kuyruk sonunda dolar, bu sefer daha çok veriyle ve daha ani çöker.

**2. Retry fırtınası (retry storm) yaratmak.** Sistem yük altında istekleri reddedince, istemciler hemen yeniden dener. Bu, tam da sistem zorlanırken yükü katlar ve bir **metastable failure** (kendini besleyen çöküş) doğurur. Çözüm: exponential backoff + jitter (rastgele gecikme) ve devre kesici (circuit breaker) kalıplarıdır.

**3. Bufferbloat.** Çok büyük tamponlar, backpressure sinyalinin gecikmesine yol açar. Tampon dolana kadar üretici hızını hiç düşürmez; dolduğunda ise gecikme zaten kabul edilemez seviyeye çıkmıştır. Büyük tampon her zaman iyi değildir; gecikmeyi gizler ama çözmez.

**4. Head-of-line blocking'i ihmal etmek.** Tek bir paylaşılan kuyrukta, yavaş bir tüketici veya büyük bir iş, arkasındaki tüm işleri bekletir. Stream başına ayrı akış kontrolü (HTTP/2'nin yaptığı gibi) veya öncelik kuyrukları bu sorunu hafifletir.

**5. Async kod backpressure'ı otomatik çözer sanmak.** Asenkron veya "reactive" olmak, tek başına backpressure sağlamaz. `CompletableFuture` veya callback tabanlı bir kodda, talep sınırı yoksa üretici yine tüketiciyi ezer. Reactive framework kullanmak, `request(n)` semantiğini doğru uygulamadıkça koruma vermez.

**6. Metrikleri ortalamayla izlemek.** Ortalama gecikme, kuyruk sorunlarını gizler. Sistem çoğu zaman hızlıdır ama tepe yüklerde p99 patlar; kullanıcı deneyimini o kuyruk anları belirler. Her zaman yüzdelik dilimlere bakın.

**7. Load shedding'i hiç test etmemek.** Yük atma mantığı, en çok ihtiyaç duyulduğu anda (gerçek olay sırasında) ilk kez çalışıyorsa, muhtemelen beklenmedik biçimde başarısız olur. Yük testi ve chaos engineering ile bu yollar önceden doğrulanmalıdır.

## Özet

Backpressure, üreticinin tüketiciyi ezmesini önleyen, basıncı kaynağa geri ileten bir öz-koruma mekanizmasıdır. Temelinde Little's Law yatar: varış hızı servis hızını aşarsa kuyruklar ve gecikmeler sınırsız büyür. Uygulaması pull-based talep (reactive streams `request(n)`), sınırlı kuyruklar ve kredi temelli pencereler (TCP rwnd, HTTP/2 `WINDOW_UPDATE`) üzerinden gerçekleşir. Sinyal kaynağa ulaşamadığında load shedding devreye girerek sistemi ayakta tutar. Kapasite planlamasının hem erken uyarı sistemi hem güvenlik ağıdır. Doğru uygulamanın anahtarı: her yerde sonlu sınırlar, uçtan uca düşünme, timeout entegrasyonu ve yüzdelik dilim temelli izlemedir. En büyük tuzak, sınırsız kuyruğu koruma sanmak ve retry fırtınalarını hesaba katmamaktır.
