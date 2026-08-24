# Mesaj Kuyrukları ve Asenkron İşleme

## Tanım ve Kapsam

Mesaj kuyruğu (message queue), bir sistemin bir parçasının ürettiği veriyi (mesajı), başka bir parçasının onu tam o anda işlemeye hazır olmasını beklemeden gönderebilmesini sağlayan bir ara katmandır. Üretici (producer) mesajı bir aracıya (broker) bırakır, tüketici (consumer) hazır olduğunda oradan alır. Aradaki bu tampon, iki tarafın birbirinden zaman ve hız olarak bağımsız çalışmasına, yani **asenkron işleme**ye izin verir.

Bu yazının odağında iki temel araç var: **RabbitMQ** ve **Apache Kafka**. İkisi de "mesaj taşır" ama mimari felsefeleri temelden farklıdır. RabbitMQ klasik bir mesaj aracısıdır (message broker): mesajları kuyruklara yönlendirir, tüketici aldıktan sonra mesaj kuyruktan silinir. Kafka ise dağıtık bir **commit log**'tur: mesajlar bir log dosyasına sırayla eklenir (append-only), tüketici okusa da mesaj bir süre orada kalır. Bu ayrım, ilerideki her tartışmanın (teslim garantileri, backpressure, yeniden işleme) kök nedenini oluşturur.

Yanında ele alacağımız üç kavram, üretim ortamında bir kuyruk sisteminin kaderini belirler: **teslim garantileri** (mesaj kaç kez ulaşır), **dead letter queue / DLQ** (işlenemeyen mesaj nereye gider) ve **backpressure** (tüketici yetişemediğinde ne olur).

## Kök Neden: Asenkron İşlemeye Neden İhtiyaç Duyarız

Senkron bir çağrıda (örneğin bir HTTP isteği) çağıran taraf, cevap gelene kadar bekler ve iki servis **zaman içinde birbirine bağlıdır** (temporal coupling). Sipariş servisi, e-posta servisini doğrudan çağırırsa, e-posta servisi yavaşladığında sipariş servisi de yavaşlar; e-posta servisi çökerse sipariş alınamaz hale gelir. Yani bir bileşenin arızası, onu çağıran her yere yayılır.

Araya bir kuyruk koyduğumuzda bu bağ kırılır. Sipariş servisi "sipariş oluştu" mesajını kuyruğa bırakır ve kendi işine döner. E-posta servisi çökmüş olsa bile mesaj kuyrukta durur; servis ayağa kalkınca birikmiş mesajları işler. Bu üç somut fayda sağlar:

- **Dayanıklılık (resilience):** Alt sistem geçici olarak çökse bile iş kaybolmaz, kuyrukta bekler.
- **Yük dengeleme (load leveling):** Ani trafik zirvelerinde (spike) istekler kuyrukta birikir; tüketici kendi hızında, sabit bir tempoda tüketir. Sistem zirveye göre değil, ortalamaya göre boyutlandırılabilir.
- **Ölçeklenebilirlik:** Aynı kuyruğu birden çok tüketici (consumer) dinleyerek işi paralel bölüşebilir.

Bunun bedeli, kaybettiğiniz basitliktir. Asenkron sistemde artık anlık cevap yoktur, hata ayıklama zorlaşır, ve "mesaj gerçekten işlendi mi?" sorusu ciddi bir mühendislik problemine dönüşür. Bu yazının geri kalanı büyük ölçüde bu problemi ele alıyor.

## RabbitMQ: Akıllı Broker, Aptal Tüketici

RabbitMQ, AMQP (Advanced Message Queuing Protocol) protokolü etrafında şekillenmiş bir aracıdır. Zekâ broker'da toplanmıştır. Temel akış şöyledir:

Üretici mesajı bir **exchange**'e gönderir. Exchange, mesajı doğrudan bir kuyruğa değil, kendisine bağlanmış (binding) kurallara göre bir veya birden çok kuyruğa yönlendirir. Yönlendirme tipleri farklıdır: `direct` (routing key birebir eşleşmesi), `topic` (desen eşleşmesi, örneğin `siparis.*`), `fanout` (bağlı tüm kuyruklara kopyala), `headers` (mesaj başlıklarına göre). Bu yönlendirme esnekliği RabbitMQ'nun en güçlü yanıdır: karmaşık dağıtım topolojilerini broker seviyesinde kurabilirsiniz.

Tüketici bir kuyruğa abone olur. Mesajı aldıktan sonra işini bitirince broker'a **acknowledgement (ack)** gönderir. Broker ack'i alınca mesajı kuyruktan siler. Ack gelmezse (tüketici çökerse veya zaman aşımına uğrarsa) broker mesajı başka bir tüketiciye yeniden dağıtır. İşte teslim garantisinin kalbi budur ve birazdan detaylandıracağız.

RabbitMQ'nun zihinsel modeli şudur: **mesaj tüketilince yok olur**. Kuyruk bir bekleme odasıdır, arşiv değildir. Bu yüzden RabbitMQ, "bir işi bir kez birine yaptırmam lazım" (task distribution) senaryolarında çok doğaldır: e-posta gönder, görsel işle, ödeme al.

## Kafka: Aptal Broker, Akıllı Tüketici

Kafka'nın felsefesi terstir. Broker mümkün olduğunca basit ve hızlıdır; zekâ tüketiciye kaydırılmıştır.

Kafka'da mesajlar **topic**'lere yazılır. Her topic, **partition** adı verilen parçalara bölünür. Bir partition, diske sırayla yazılan, değiştirilemez (immutable), append-only bir log dosyasıdır. Her mesajın partition içinde artan bir **offset** numarası vardır. Kafka'nın olağanüstü throughput'unun kök nedeni tam olarak budur: rastgele erişim yerine sıralı disk yazması yapar (sequential I/O), işletim sisteminin page cache'ini kullanır ve mesajları kopyalamadan ağ üzerinden iletebilir (zero-copy prensibi). Diskler sıralı yazmada, rastgele yazmaya göre kat kat hızlıdır; Kafka bu fiziksel gerçeği mimarisinin merkezine koyar.

Kritik fark: **tüketici mesajı okuduğunda mesaj silinmez.** Mesaj, ayarlanan saklama süresi (retention) boyunca (örneğin 7 gün) veya boyut sınırına kadar log'da kalır. Tüketici sadece kendi **offset**'ini, yani "log'da nereye kadar okudum" bilgisini ilerletir. Bu tek fark, Kafka'ya RabbitMQ'da olmayan üç yetenek kazandırır:

- **Yeniden okuma (replay):** Bir tüketici offset'ini geri alarak geçmiş mesajları baştan işleyebilir. Bir işleme bug'ı bulunduğunda, düzeltip son bir haftayı yeniden işlemek mümkündür.
- **Çoklu bağımsız tüketim:** Aynı topic'i birbirinden habersiz farklı **consumer group**'lar okuyabilir. Her grubun kendi offset'i vardır. Analitik ekibi, bildirim servisi ve arşivleme servisi aynı olay akışını, birbirini etkilemeden ayrı ayrı işler.
- **Sıra garantisi (partition içinde):** Bir partition içindeki mesajlar kesinlikle yazıldıkları sırayla okunur.

Consumer group içinde iş şöyle bölüşülür: her partition, grup içinde **yalnızca bir** tüketiciye atanır. Yani bir topic'te 10 partition varsa, o topic'i en fazla 10 tüketici paralel işleyebilir. Partition sayısı, Kafka'da paralellik tavanınızdır — bu, sonradan değiştirmesi zahmetli olduğu için baştan doğru düşünülmesi gereken bir tasarım kararıdır.

### Ne Zaman Hangisi

Kaba bir pusula: iş dağıtımı, karmaşık yönlendirme, düşük gecikme ve mesaj başına "bir kez yap" mantığı istiyorsanız RabbitMQ. Yüksek hacimli olay akışı (event streaming), replay ihtiyacı, birden çok bağımsız tüketici ve olay kaynağı (event sourcing) mimarisi istiyorsanız Kafka. Bunlar mutlak kurallar değil — RabbitMQ streams gibi, Kafka'nın da klasik kuyruk gibi kullanılabildiği örtüşme alanları var; ama felsefeleri bu yönde ayrışır.

## Teslim Garantileri: En Fazla, En Az, Tam Bir Kez

Dağıtık bir sistemde "mesaj tüketiciye ulaştı" ile "tüketici mesajı başarıyla işledi ve bunu broker'a bildirdi" arasında bir zaman aralığı vardır. Bu aralıkta ağ kopabilir, tüketici çökebilir, broker yeniden başlayabilir. Teslim garantilerinin tamamı, **tam bu belirsizlik penceresini** nasıl ele aldığınızla ilgilidir.

### At-most-once (en fazla bir kez)

Mesaj ya bir kez teslim edilir ya da hiç. Kayıp mümkün, tekrar imkânsız. Bu genellikle şöyle olur: tüketici mesajı alır almaz, daha işlemeden önce ack gönderir (veya offset'ini ilerletir), sonra işlemeye başlar. İşleme sırasında çökerse mesaj gitmiştir, kimse yeniden denemez. Hızlıdır, en az iş yapar, ama veri kaybını tolere edebildiğiniz durumlar içindir (örneğin örnekleme yapılan metrikler, önemsiz log'lar).

### At-least-once (en az bir kez)

Mesaj kaybolmaz ama **birden çok kez** teslim edilebilir. Doğru sıra şudur: tüketici mesajı alır, **önce işler**, işlem başarıyla bittikten sonra ack gönderir. Eğer işlemeyi bitirip ack'i göndermeden çökerse, broker ack alamadığı için mesajı yeniden dağıtır ve mesaj ikinci kez işlenir.

Bu, üretimdeki sistemlerin büyük çoğunluğunun tercihidir çünkü veri kaybetmemek, çift işlemekten daha önemlidir. Ama bir bedeli vardır: **tekrarları kendiniz yönetmek zorundasınız**. Bunun standart çözümü **idempotency**'dir (aynı işlemi birden çok kez uygulamanın, bir kez uygulamakla aynı sonucu vermesi). Örneğin ödeme çekerken mesaja bir `transaction_id` koyar, tüketici tarafında "bu id'yi daha önce işledim mi?" diye kontrol edersiniz. İşlediyseniz atlarsınız. İdempotency olmadan at-least-once, çift tahsilat gibi felaketlere yol açar.

### Exactly-once (tam bir kez)

Her mesajın etkisinin sisteme tam olarak bir kez yansıması. Kulağa ideal gelir ama dağıtık sistemlerde **saf haliyle imkânsıza yakındır** ve bu konuda çok yanlış anlama vardır. Sorun şu: mesajı işlemek ve "işledim" bilgisini kaydetmek iki ayrı adımdır ve ikisi arasında sistem çökebilir. Gerçek dünyada "exactly-once" dediğimiz şey neredeyse her zaman **at-least-once teslim + idempotent işleme** kombinasyonudur; yani teslim birden çok kez olsa da nihai etki bir kezmiş gibi görünür.

Kafka'nın "exactly-once semantics" (EOS) desteği vardır ama bu, sınırlı bir kapsamda çalışır: idempotent producer ve transaction'lar sayesinde, Kafka'dan okuyup işleyip **yine Kafka'ya yazan** (read-process-write) akışlarda uçtan uca tam-bir-kez sağlanabilir. Ancak tüketicinizin yan etkisi Kafka dışına çıkıyorsa (harici bir veritabanına yazmak, bir e-posta göndermek, bir ödeme API'si çağırmak), o harici sistem Kafka transaction'ına dahil olmadığı için garanti kırılır. Buradaki dürüst mühendislik tavrı: exactly-once'a sihirli bir ayar olarak güvenmeyin; kritik yan etkilerinizi **idempotent** tasarlayın.

## Dead Letter Queue (DLQ): İşlenemeyen Mesajın Sığınağı

At-least-once dünyasında kaçınılmaz bir soru doğar: **bir mesaj sürekli işlenemiyorsa ne olur?** Diyelim ki mesajın içeriği bozuk (malformed), veya işleyen kod o mesaj tipinde bir bug'a takılıyor. Tüketici mesajı alır, patlar, ack gönderemez, broker yeniden dağıtır, tüketici tekrar patlar... Bu bir **sonsuz döngü**dür (poison message / zehirli mesaj problemi). Tek bir bozuk mesaj, kuyruğun tamamını tıkayıp tüketiciyi kilitleyebilir.

Çözüm **dead letter queue**'dur: belirli bir sayıda yeniden deneme başarısız olduktan sonra, mesaj ana kuyruktan alınıp ayrı bir "ölü mektup" kuyruğuna taşınır. Böylece:

1. Zehirli mesaj ana akıştan çıkar, sağlıklı mesajlar işlenmeye devam eder.
2. Bozuk mesaj kaybolmaz; DLQ'da durur, sonra incelenir, düzeltilir veya elle yeniden işlenir (reprocess).

RabbitMQ'da bu, kuyruğa bir `x-dead-letter-exchange` argümanı tanımlayarak yapılır; mesaj reddedildiğinde (nack) veya TTL'i dolduğunda veya kuyruk taşınca o exchange'e yönlendirilir. Kafka'da yerleşik bir DLQ kavramı yoktur; bu deseni siz kurar veya Kafka Connect ile framework'lerin (örneğin Spring Kafka) sağladığı DLQ topic mekanizmasını kullanırsınız — başarısız mesaj ayrı bir topic'e yazılır.

DLQ ile ilgili kritik ve sık atlanan nokta: **DLQ'yu izlemezseniz işe yaramaz.** DLQ, sessizce dolan bir çöp kutusu olmamalı. DLQ'ya mesaj düşmesi bir alarm tetiklemeli; oraya düşen her mesaj, ele alınması gereken bir olaydır. İzlenmeyen bir DLQ, "hatalarımızı bir yere süpürdük ama kimse bakmıyor" durumudur ve genellikle sessiz veri kaybının kaynağıdır. Ayrıca mesajı DLQ'ya taşırken, **neden** başarısız olduğu bilgisini (exception, deneme sayısı, orijinal kuyruk) mesaj başlıklarına eklemek, sonraki teşhisi çok kolaylaştırır.

## Backpressure: Tüketici Yetişemezse Ne Olur

Backpressure (geri basınç), üretici(ler)in mesaj üretme hızının, tüketici(ler)in işleme hızını sürekli aşması durumunda ortaya çıkan problemi ve onun çözümünü anlatır. Kök soru fizikseldir: her tampon sonludur. Üretim tüketimden hızlıysa, bir yerde bir şey **birikir** ve o şeyin bir sınırı vardır.

### Neden Tehlikelidir

Diyelim bir servis içinde sınırsız (unbounded) bir bellek kuyruğu var ve üretim sürekli tüketimi geçiyor. Kuyruk büyür, büyür, sonunda süreç belleği tükenir ve servis **OutOfMemory** ile çöker. Çöktüğü anda bellekteki tüm birikmiş iş de kaybolur. Yani backpressure'ı yönetmemek, en kötü anda (sistem zaten zorlanırken) topyekûn çökmeye davetiyedir. Bu yüzden **sınırsız kuyruk bir bug'dır**; her tampon sınırlı (bounded) olmalıdır.

### RabbitMQ ve Backpressure

RabbitMQ'nun temel silahı **prefetch** ayarıdır (`basic.qos` ile `prefetch_count`). Bu, "bir tüketiciye, ack beklemeden aynı anda en fazla kaç mesaj gönderebilirim" sınırıdır. Prefetch'i düşük tutmak (örneğin 1 veya birkaç), yavaş bir tüketiciye broker'ın yüzlerce mesaj yığmasını engeller; mesajlar broker'da, güvenli ve dayanıklı biçimde bekler. Prefetch sınırsız veya çok yüksek olursa, broker mesajları hızlıca tüketiciye "iter" (push modeli) ve yavaş tüketicinin belleği dolar.

İkinci mekanizma, broker'ın kendi kaynak sınırlarıdır: RabbitMQ bellek veya disk için belirlenmiş yüksek eşiklere (watermark) ulaşınca üreticileri yavaşlatabilir, hatta yayınları bloke edebilir (flow control). Böylece basınç ta üreticiye kadar geri iletilir — backpressure kelimesinin tam anlamı budur: basıncın zincirin başına doğru geri yansıması. Ayrıca kuyruklara **maksimum uzunluk** (`x-max-length`) koyabilir, dolduğunda yeni mesajların ya reddedilmesini ya da en eskisinin DLQ'ya düşmesini seçebilirsiniz.

### Kafka ve Backpressure

Kafka'da mimari fark, backpressure'ı doğal olarak daha yumuşak kılar. Tüketici mesajı **kendi hızında çeker** (pull modeli); broker tüketiciye mesaj itmez. Tüketici yavaşsa sadece offset'i yavaş ilerler; birikmiş iş broker'ın belleğinde değil, zaten diske yazılı log'da durur. Bu birikime **consumer lag** denir: "log'un sonu ile tüketicinin okuduğu offset arasındaki fark". Consumer lag, bir Kafka sisteminin **en önemli sağlık metriğidir**. Lag sürekli büyüyorsa, tüketicileriniz üretimi karşılayamıyor demektir ve partition sayısını (dolayısıyla paralel tüketici sayısını) veya tüketici verimini artırmanız gerekir.

Kafka'da tehlike, retention penceresinde gizlidir: log 7 gün saklanıyorsa ve tüketiciniz 7 günden fazla geride kalırsa, **henüz okumadığınız mesajlar silinir** ve veri kaybı yaşarsınız. Yani Kafka backpressure altında çökmez ama sessizce veri düşürebilir; bu yüzden lag'i retention'a göre izlemek şarttır.

### Genel Backpressure Stratejileri

Tüketici uzun süre yetişemiyorsa seçenekleriniz şunlardır ve hepsi bir ödünleşimdir:

- **Ölçekle (scale out):** Daha çok tüketici ekle. Kafka'da partition tavanına, RabbitMQ'da genellikle kuyruk düzenine bağlıdır.
- **Yavaşlat (throttle):** Üreticiyi yavaşlat. Veri kaybı yok ama gecikme (latency) artar.
- **Düşür (load shedding / drop):** Aşırı yükte bazı mesajları bilinçli olarak at. Veri kaybı var ama sistem ayakta kalır. Yalnızca kaybı tolere edebilen veriler için.
- **Örnekle:** Her mesajı değil, belirli bir oranını işle.

Doğru seçim, verinin değerine bağlıdır: bir ödeme mesajını asla düşüremezsiniz (ölçekle veya yavaşlat), ama saniyede bir milyon telemetri noktasının bir kısmını düşürmek makul olabilir.

## Yaygın Hatalar

**Sınırsız kuyruk kurmak.** Uygulama içi bellek kuyruklarında sık yapılır. Yük artınca OutOfMemory ile çöker. Her tampon bounded olmalı ve dolduğunda ne yapılacağı (blokla, reddet, düşür) açıkça kararlaştırılmalı.

**İdempotency olmadan at-least-once kullanmak.** Sistem "genelde" doğru çalışır, sonra bir yeniden dağıtım gününde çift e-posta, çift tahsilat, çift stok düşümü olarak patlar. At-least-once seçtiyseniz idempotency zorunludur, opsiyonel değil.

**Exactly-once'a mutlak güvenmek.** Özellikle yan etkisi harici sisteme çıkan işlemlerde, "broker exactly-once diyor, ben rahatım" tehlikeli bir yanılgıdır. Kritik yan etkileri idempotent tasarlamak, tek gerçek güvencedir.

**DLQ'yu izlememek.** Mesajlar sessizce DLQ'ya düşer, kimse bakmaz, haftalar sonra "şu bildirimler neden hiç gitmemiş?" diye fark edilir. DLQ mutlaka alarmlı olmalı.

**Yeniden denemede geri çekilme (backoff) olmaması.** Başarısız mesajı hemen, aralıksız yeniden denemek, geçici bir arızada (örneğin bağımlı bir servis kısa süre yavaşladı) sistemi retry fırtınasına sokar ve arızayı derinleştirir. Denemeler arasında artan bekleme (exponential backoff) ve rastgelelik (jitter) uygulanmalı, deneme sayısı sınırlı olmalı, sınır aşılınca DLQ'ya gidilmeli.

**Kafka'da partition sayısını hafife almak.** Az partition, ileride paralellik tavanına çarpar ve partition sayısını sonradan artırmak, anahtar-bazlı sıralamayı (key-based ordering) bozabilir. Kapasiteyi baştan öngörmek gerekir.

**Sıra garantisini olduğundan geniş sanmak.** Kafka sırayı yalnızca **partition içinde** garanti eder, topic genelinde değil. Belirli bir varlığın (örneğin bir kullanıcının) olaylarının sıralı işlenmesini istiyorsanız, o varlığın kimliğini partition key olarak kullanıp tüm olaylarını aynı partition'a düşürmelisiniz.

**Büyük payload'ları kuyruktan geçirmek.** Mesajın içine devasa dosyalar (video, büyük görsel) koymak broker'ı yorar. Doğrusu **claim-check deseni**dir: büyük veriyi bir nesne deposuna (object storage) koyup, mesaja sadece ona işaret eden bir referans/URL konur.

## En İyi Pratikler

**Tüketicileri idempotent tasarlayın.** Bu tek karar, teslim garantileriyle ilgili sorunların çoğunu kaynağında çözer. Her mesaja benzersiz bir kimlik verin ve tüketicide "bu kimliği işledim mi" kontrolü yapın.

**Her tamponu sınırlayın ve dolunca ne olacağını tanımlayın.** Sınırsız birikim yok. Reddet, blokla, DLQ'ya at veya düşür — ama bilinçli seç.

**Backoff + jitter ile sonlu yeniden deneme, ardından DLQ.** Yeniden deneme mantığı, geçici hataları toparlarken kalıcı hataları sonsuza dek denememeli; belirli bir eşikten sonra mesaj DLQ'ya gitmeli.

**Consumer lag'i (Kafka) ve kuyruk derinliğini (RabbitMQ) izleyin ve alarmlayın.** Bunlar sistemin en erken uyarı sinyalleridir. Lag/derinlik sürekli artıyorsa kapasite yetersizdir; küçük bir birikme normal, sürekli büyüyen bir birikme kırmızı alarmdır.

**DLQ'yu birinci sınıf bir izleme hedefi yapın.** Oraya düşen her mesaj bir olay olarak ele alınmalı; düzenli olarak boşaltılıp incelenmeli.

**Mesajları şema ile yönetin ve geriye/ileriye uyumluluğu koruyun.** Uzun ömürlü akışlarda (özellikle Kafka'da replay yaparken) eski ve yeni tüketiciler aynı mesaj tipini okuyabilmeli. Schema Registry gibi araçlarla şemayı merkezîleştirmek, uyumsuz değişiklikleri (breaking change) deploy öncesi yakalamayı sağlar.

**Doğru aracı işe göre seçin.** Her şeyi tek bir kuyruk teknolojisine zorlamayın. İş dağıtımı ve karmaşık yönlendirme için RabbitMQ, yüksek hacimli olay akışı ve replay için Kafka. İkisini aynı mimaride farklı yerlerde kullanmak tamamen normaldir.

**Zehirli mesajları erken izole edin.** Bir mesaj işlenmiyorsa hızlıca DLQ'ya alın; onun yüzünden tüm kuyruğun tıkanmasına izin vermeyin. Bir tüketicinin sağlığı, tek bir bozuk mesaja rehin olmamalı.

## Kapanış

Mesaj kuyrukları, sistemleri gevşek bağlı (loosely coupled), dayanıklı ve ölçeklenebilir yapmanın temel aracıdır; ama getirdiği güç, senkron çağrının basitliğini bir belirsizlikle takas eder: "mesaj gerçekten, tam bir kez işlendi mi?" RabbitMQ ile Kafka'nın mimari felsefeleri (tüketilince silinen kuyruk vs. saklanan log) bu belirsizliğin nasıl ele alınacağını belirler. Teslim garantileri size seçenek sunar ama bedava öğle yemeği yoktur; pratikte at-least-once + idempotency, sağlam sistemlerin belkemiğidir. DLQ, kaçınılmaz başarısızlıkları sistemi kilitlemeden yakalar. Backpressure ise fiziğin dayattığı gerçeği kabul etmektir: hiçbir tampon sonsuz değildir, ve o basıncı izleyip yönetmezseniz, sistem en kötü anda çöker. Bu üç kavramı ciddiye alan bir tasarım, üretimde ayakta kalan bir tasarımdır.
