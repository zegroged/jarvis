# Stream Processing ve Olay Tabanlı Veri İşleme (Kafka Internals, Exactly-Once Semantics, Windowing)

## Giriş: Bu Konu Neden "Mesaj Kuyruğu" Konusundan Farklı

"Mesaj Kuyrukları" ve "Event-Driven Mimari" başlıkları genellikle uygulama seviyesindeki soruları cevaplar: hangi servis hangi olayı yayınlar, hangi servis dinler, coupling nasıl azaltılır. Bu makale ise bir kat aşağı iner: Kafka, Kinesis, Pulsar, Flink gibi sistemlerin **iç yapısı** nedir, bir mesaj disk üzerinde nasıl durur, bir consumer grubu nasıl koordine olur, "tam olarak bir kez işleme" (exactly-once semantics) dediğimizde gerçekte ne sağlanıyor, ve zaman pencereleri (windowing) geç gelen verilerle nasıl başa çıkıyor.

Bunu anlamak önemlidir çünkü dağıtık streaming sistemleri, yanlış anlaşıldığında **sessiz veri kaybına veya sessiz veri çoğaltmaya (duplication)** yol açar. Sistem hata vermez, log'da kırmızı bir satır olmaz ama finansal bir işlem iki kez işlenir ya da bir sensör okuması kaybolur. Savunma ve tespit açısından, bu tarz hataları yakalamak için mekanizmanın iç işleyişini bilmek şarttır.

## 1. Temel Model: Log-Tabanlı Mesajlaşma

### 1.1 Kuyruk mu, Log mu?

Klasik mesaj kuyruklarında (RabbitMQ, ActiveMQ gibi) mesaj tüketildiğinde kuyruktan silinir ya da "ack" edilene kadar görünmez kalır. Kafka'nın (ve benzer sistemlerin) temel farkı, mesajların **append-only bir log** yapısında saklanmasıdır. Bir mesaj tüketildikten sonra da log'da kalır; consumer, mesajı "sildiği" için değil, log üzerindeki **offset**'ini ilerlettiği için bir sonraki mesaja geçer.

Bu tasarımın kök nedeni şu gereksinimden gelir: birden fazla bağımsız tüketicinin (consumer) aynı veriyi farklı hızlarda, farklı zamanlarda ve hatta geçmişe dönerek (replay) okuyabilmesi gerekir. Kuyruk modeli "bir mesaj bir kez tüketilir" varsayımına dayanırken, log modeli "veri bir kayıttır, okuma işaretçi (pointer) ile yapılır" varsayımına dayanır. Bu, stream processing'in en temel zihniyet değişikliğidir: **veri bir olay akışıdır, tüketilip yok olan bir görev değildir.**

### 1.2 Topic, Partition, Offset

- **Topic**: Mantıksal bir kategori/kanal (örn. `siparis-olaylari`).
- **Partition**: Bir topic, paralellik ve ölçeklenebilirlik için birden fazla partition'a bölünür. Her partition, kendi içinde sıralı, değişmez (immutable) bir log'dur.
- **Offset**: Bir partition içindeki her mesajın sıra numarası. Offset sadece o partition içinde anlamlıdır; topic genelinde global bir sıra **yoktur**.

Bu, çok kritik bir noktadır: Kafka **sadece partition içi sırayı garanti eder**, topic genelinde değil. Eğer uygulamanız "olaylar A, B, C sırasıyla gelmeli" varsayımına dayanıyorsa ve bu olaylar farklı partition'lara dağıtılmışsa, sıra garantisi kaybolur. Bu yüzden aynı entity'ye (örn. aynı kullanıcı ID'si) ait olaylar genellikle bir **partition key** (mesaj anahtarı) ile hash'lenerek hep aynı partition'a yönlendirilir. Partition key seçimi yanlış yapılırsa (örn. düşük kardinaliteli bir key, ya da hiç key kullanılmaması) hem sıra garantisi bozulur hem de partition'lar arası yük dengesizliği (hot partition) oluşur.

### 1.3 Replikasyon ve Lider Seçimi

Her partition, dayanıklılık için birden fazla broker'a replike edilir (replication factor). Bir partition'ın bir **lider (leader)** replikası vardır; tüm yazma/okuma istekleri lidere gider, diğerleri (follower) lideri takip eder (ISR - In-Sync Replicas kümesi). Lider düşünce, ISR içindeki bir follower yeni lider seçilir.

Kök neden mantığı: dağıtık sistemlerde tek nokta hatası (single point of failure) kabul edilemez, ama çoklu yazıcılı (multi-master) sistemler tutarlılık çakışmalarına yol açar. Lider-takipçi modeli bu ikisi arasında pratik bir denge kurar — yazma tek bir yerden yapılır (basit tutarlılık), ama veri çoklu kopyada durur (dayanıklılık). `acks` ayarı (kaç replikanın yazmayı onaylaması gerektiği: 0, 1, veya "all"/ISR) burada doğrudan **dayanıklılık ile gecikme (latency) arasındaki ödünleşimi** kontrol eder. `acks=all` olmadan "veri kaybolmaz" iddia etmek yanlıştır.

## 2. Consumer Group ve Rebalancing

### 2.1 Consumer Group Nedir

Bir consumer group, aynı topic'i birlikte tüketen consumer'lardan oluşur; her partition, grup içinde **en fazla bir** consumer'a atanır (bu, paralel işleme + tekilliği aynı anda sağlar). Grup, bir **group coordinator** broker'ı tarafından yönetilir.

### 2.2 Rebalancing: Neden Var, Neden Tehlikeli

Bir consumer gruba katıldığında, ayrıldığında veya çöktüğünde (crash, ya da heartbeat süresi aşıldığında), coordinator partition-consumer atamasını yeniden hesaplar — buna **rebalancing** denir. Kök neden: sistem elastik olmalı, consumer sayısı değiştiğinde yük otomatik dağılmalı.

Ama rebalancing'in maliyeti vardır: "stop-the-world" tarzı eski protokollerde (eager rebalancing), rebalance başladığında **tüm consumer'lar partition atamalarını bırakır**, yeniden dağıtım olur, herkes yeniden başlar. Bu sırada tüketim durur (rebalancing storm / "stop the world" etkisi). Yeni nesil **cooperative/incremental rebalancing** protokolleri, sadece değişen partition'ları elden ele geçirir, diğerleri kesintisiz devam eder. Bunu bilmek önemlidir çünkü üretimde sıklıkla görülen "consumer lag birden yükseldi, sonra kendiliğinden düştü" paterni çoğu zaman gereksiz/sık rebalance'lardan kaynaklanır (örn. `session.timeout.ms` çok düşük, ya da bir consumer'ın mesaj işleme süresi `max.poll.interval.ms`'i aşıp coordinator tarafından ölü sayılması).

**Tespit açısından önemli sinyal**: Rebalancing sırasında kısa süreli duplicate işlemler oluşabilir, çünkü bir partition eski consumer'dan yeni consumer'a geçerken, eski consumer'ın commit etmediği offset'ler yeniden işlenir. Bu, exactly-once tartışmasının tam da kalbidir (aşağıda).

### 2.3 Static Membership

Consumer'lar sık sık yeniden başlatılıyorsa (deployment, autoscaling) her yeniden başlama bir rebalance tetikler. **Static membership** (sabit bir `group.instance.id` atamak), kısa süreli kopmalarda consumer'ın "ayrıldı" sayılmamasını, atamasının korunmasını sağlar — böylece gereksiz rebalance'lar önlenir. Bu, operasyonel bir en iyi pratiktir ama çoğu takım tarafından bilinmez ve varsayılan yapılandırmada kapalı kalır.

## 3. At-Least-Once, At-Most-Once, Exactly-Once: Gerçekte Ne Anlama Gelir

Bu ayrım, mülakatlarda ve mimari tartışmalarda en çok yanlış anlaşılan konudur. Önce temel tanımları netleştirelim:

- **At-most-once**: Mesaj hiç işlenmeyebilir ama asla birden fazla işlenmez. (Önce oku/commit et, sonra işle — hata olursa kaybolur.)
- **At-least-once**: Mesaj en az bir kez işlenir ama tekrar işlenebilir. (Önce işle, sonra commit et — commit'ten önce crash olursa aynı mesaj tekrar gelir.)
- **Exactly-once**: Mesaj net etkisi açısından tam olarak bir kez işlenmiş gibi davranır.

### 3.1 Kök Neden: Neden "Gerçek" Exactly-Once Dağıtık Sistemlerde Zordur

Dağıtık bir sistemde üç ayrı adım vardır: (1) mesajı oku, (2) iş mantığını uygula/yan etki üret (DB yazma, başka bir sisteme çağrı), (3) okumanın offset'ini commit et. Bu üç adım **atomik değildir** — aralarında crash olabilir. Eğer (2) başarıyla tamamlanıp (3) başarısız olursa, sistem yeniden başlatıldığında aynı mesaj tekrar (2)'yi tetikler: **duplicate**. Eğer (3) yapılıp (2) hiçbir zaman görünür olmazsa (örn. yan etki bir kuyruğa yazılmadı ama offset ilerledi): **kayıp**.

Bu yüzden "exactly-once delivery" (dağıtım) kavramının genel dağıtık sistemlerde **imkansıza yakın** olduğu söylenir (iki general problemi / consensus zorluğu ile aynı köktendir). Kafka ve benzeri sistemlerin sunduğu şey aslında **exactly-once semantics (EOS)** — yani mesajın fiziksel olarak bir kez teslim edilmesi değil, **net etkinin** bir kez uygulanmış gibi görünmesidir. Bu, iki farklı teknikle sağlanır:

### 3.2 Idempotent Producer

Producer, her mesaja bir sıra numarası (sequence number) ve producer ID (PID) ekler. Broker, aynı PID + sequence number'ı tekrar görürse mesajı **yok sayar** (dedup). Bu, "producer retry ederse aynı mesaj iki kez yazılmasın" problemini çözer — ağ hatası yüzünden ack gelmeyip producer'ın aynı mesajı tekrar göndermesi durumunda broker tarafında tekilleştirme yapılır.

### 3.3 Transactional / Atomic Writes (Read-Process-Write Döngüsü)

Bir stream processing uygulaması genellikle "bir topic'ten oku, işle, başka bir topic'e yaz + offset'i commit et" döngüsünü çalıştırır. Kafka'nın **transaction** mekanizması, bu **yazma + offset commit**'ini tek bir atomik işlem gibi paketler: ya hepsi görünür olur ya da hiçbiri (bir transaction coordinator ve iki-aşamalı commit benzeri bir protokol kullanılarak). Tüketici tarafında `isolation.level=read_committed` ayarı ile, henüz commit edilmemiş (ya da abort edilmiş) transaction'lara ait mesajlar okunmaz.

Bunun kök mantığı şöyle özetlenebilir: exactly-once, tek bir mesajın sihirli şekilde bir kez teslim edilmesiyle değil, **"oku-işle-yaz" üçgeninin tek bir atomik birim haline getirilmesiyle** sağlanır. Eğer işlem yarıda keserse (crash), sistem yeniden başladığında transaction abort edilmiş sayılır, hiçbir yan etki "yarım" görünmez, ve mesaj baştan işlenir (ama önceki yarım yazı görünmez olduğu için net etki bir kez uygulanmış gibi olur).

### 3.4 Sınırlar: Exactly-Once Nerede Biter

EOS garantisi **sistem sınırları içinde** geçerlidir. Eğer iş mantığınız Kafka dışına bir yan etki üretiyorsa (örn. bir e-posta gönderme, harici bir REST API çağrısı, dosya sistemine yazma), Kafka'nın transaction mekanizması o yan etkiyi kapsamaz. Bu durumda **idempotent tüketici mantığı uygulamanın sorumluluğundadır**: harici sisteme yazarken bir "idempotency key" kullanmak (örn. mesajın kendi offset'i + partition'ı bir unique key olarak DB'ye yazılır, aynı key tekrar gelirse işlem atlanır).

**Yaygın hata**: "Kafka exactly-once destekliyor, o zaman consumer'ımızda hiçbir dedup mantığına gerek yok" varsayımı. Bu sadece Kafka-to-Kafka (topic-to-topic) işlem hatlarında doğrudur; dışarıya çıkan her yan etki için ayrıca düşünülmesi gerekir.

## 4. Windowing: Zamanla Yarışan Hesaplama

### 4.1 Neden Pencereleme Gerekli

Stream sınırsız (unbounded) bir veri kaynağıdır. "Son 5 dakikadaki işlem sayısı" gibi bir agregasyon hesaplamak için, sonsuz akışı sonlu parçalara (window) bölmek gerekir. Ama burada iki farklı zaman kavramı çakışır:

- **Event time**: Olayın gerçekte gerçekleştiği an (cihaz üzerinde üretildiği zaman damgası).
- **Processing time**: Olayın işleme sistemine ulaştığı/işlendiği an.

Bu ikisi genellikle **aynı değildir** — ağ gecikmesi, cihaz saat sapması, offline buffer'lama gibi nedenlerle bir olay üretildikten dakikalar hatta saatler sonra sisteme ulaşabilir. Event-time tabanlı pencereleme "doğru" sonucu verir ama geç gelen veriyle başa çıkma karmaşıklığını beraberinde getirir; processing-time pencereleme basittir ama ağ/gecikme koşullarına göre **farklı, tutarsız sonuçlar** üretebilir (aynı veri seti farklı koşullarda çalıştırılınca farklı agregasyon sonucu verir).

### 4.2 Pencere Türleri

- **Tumbling window**: Sabit boyutta, çakışmayan pencereler (0-5dk, 5-10dk, ...). Her olay tam olarak bir pencereye düşer.
- **Sliding/hopping window**: Sabit boyutta ama belirli bir adımla kayan pencereler (5dk pencere, 1dk kaydırma). Bir olay birden fazla pencereye düşebilir.
- **Session window**: Sabit boyut yok; bir olay dizisi arasındaki boşluk (gap) belirli bir eşiği aşarsa yeni pencere başlar. Kullanıcı oturumu, cihaz aktivite patlaması gibi düzensiz aralıklara sahip veriler için kullanılır.

### 4.3 Watermark: Geç Gelen Veriye Karşı Savunma Mekanizması

Event-time pencereleme kullanıldığında temel soru şudur: **"5-10dk penceresini ne zaman kapatıp sonucu yayınlayabilirim? Ya hâlâ 6. dakikaya ait geç gelen bir olay yoldaysa?"** Bu sorunun cevabı sonsuza kadar bekleyemez — bir noktada pencereyi kapatıp sonucu üretmek gerekir.

**Watermark**, sistemin "bu zaman damgasından önce olan tüm olayları gördüğümü varsayıyorum" şeklindeki bir **heuristik/tahmindir**. Watermark bir event-time eşiği geçtiğinde, o eşiğin altındaki pencereler "tamamlandı" sayılır ve sonuç yayınlanır. Watermark'ın kök mantığı: dağıtık sistemde "artık hiçbir geç veri gelmeyecek" diye kesin bir garanti olamaz (ağ her zaman beklenmedik gecikme üretebilir), o yüzden sistem pratik bir bekleme süresi (örn. "en fazla 2 dakika gecikmeye tolerans") tanımlar ve bunun ötesindeki gecikmiş veriyi ya atar ya da özel bir "late data" yolunda işler.

**Tuzak**: Watermark çok sıkı (dar tolerans) ayarlanırsa, gerçekte geçerli olan ama biraz geç gelen veri sessizce dışlanır — sonuç "yanlış değil ama eksik" olur, ve bu hata genellikle fark edilmez çünkü sistem crash olmaz, sadece sayaçlar biraz düşük çıkar. Watermark çok gevşek ayarlanırsa, pencereler uzun süre açık kalır, bellek/state büyür, ve sonuç gecikmeli yayınlanır (düşük gecikme gereksinimleriyle çelişir). Bu, doğruluk ile gecikme arasındaki klasik bir ödünleşimdir ve iş gereksinimine (SLA'ya) göre kalibre edilmelidir, tek bir "doğru değer" yoktur.

### 4.4 Geç Gelen Veri İçin Stratejiler

- **Allowed lateness**: Pencere "resmen" kapandıktan sonra bile bir süre daha geç gelen veriyi kabul edip sonucu **güncelleyerek** yeniden yayınlamak (retraction/update semantics).
- **Side output / dead-letter yolu**: Tolerans dışında kalan veriyi ayrı bir akışa yönlendirip ayrıca analiz etmek (kaybetmemek, ama ana sonucu bloklamamak).
- **Idempotent/upsert sink**: Aşağı akış sistemine (DB, dashboard) yazarken "upsert" semantiği kullanmak, böylece bir pencerenin sonucu birden fazla kez (güncellenerek) yazılsa da son değer doğru kalır.

## 5. Kafka Internals: Fiziksel Depolama ve Performans

### 5.1 Segment Dosyaları ve Sequential I/O

Her partition, diskte tek bir dev dosya değil, **segment** adı verilen küçük dosyalara bölünür (belirli boyut ya da zaman eşiğine ulaşınca yeni segment açılır). Bu, hem eski verinin silinmesini (retention policy — tüm dosyayı silmek, tek tek kayıt silmekten çok daha ucuz) hem de index yönetimini kolaylaştırır.

Kafka'nın yüksek verimliliği (throughput) büyük ölçüde **sequential disk I/O**'ya dayanır — rastgele erişim yerine, hem yazma hem okuma diskte ardışık olarak yapılır, bu da dönen diskte bile (SSD'de zaten hızlı olan) yüksek performans sağlar. Ayrıca **zero-copy** tekniği (işletim sisteminin `sendfile` benzeri sistem çağrılarını kullanarak veriyi kullanıcı alanına kopyalamadan doğrudan disk'ten socket'e aktarması) network gönderiminde CPU/bellek kopyalama maliyetini azaltır.

### 5.2 Page Cache Güvenme Stratejisi

Kafka, kendi özel bellek önbelleğini tutmak yerine işletim sisteminin **page cache**'ine güvenir — yazılan veri önce page cache'e gider, arka planda diske flush edilir; okuma istekleri de sıklıkla page cache'ten karşılanır (disk I/O'ya hiç gitmeden). Bu tasarım kararı, JVM heap yönetiminin (GC duraklamaları) büyük önbellekler için verimsiz olmasından kaçınmak ve işletim sisteminin çok daha optimize edilmiş cache mekanizmasından yararlanmak için bilinçli olarak alınmıştır.

### 5.3 Consumer Lag: En Önemli Operasyonel Metrik

**Consumer lag**, bir partition'daki en son yazılan offset ile consumer'ın commit ettiği offset arasındaki farktır. Bu, streaming sistemlerinde **tek bir en kritik sağlık metriğidir** — lag sürekli artıyorsa, tüketim üretimden yavaş demektir ve sistem gerideyecek/birikecek demektir.

Tespit açısından önemli: lag'in tek başına yüksek olması her zaman "kötü" değildir (batch-tipi bir tüketici kasıtlı olarak birikimi bekliyor olabilir), ama **lag'in sürekli, monotonik olarak artan trendi** her zaman bir uyarı işaretidir — ya consumer yetersiz ölçekte, ya bir consumer takılmış/crash olmuş (rebalance beklemede), ya da downstream bir bağımlılık (DB, API) yavaşlamış ve consumer onu bekliyordur (backpressure).

## 6. Yaygın Hatalar ve Savunma Pratikleri

1. **Partition key seçmemek / rastgele key kullanmak**: Sıra garantisi beklenen yerlerde sırasız veri işlenir. Savunma: entity-bazlı (örn. user_id, order_id) sabit bir partition key kullanmak ve bunu belgelemek.

2. **"At-least-once yeter" deyip consumer tarafında idempotency düşünmemek**: Retry/rebalance sırasında doğal olarak duplicate oluşur; downstream sistem (DB, ödeme API'si) bunu tolere edecek şekilde (unique constraint, idempotency key) tasarlanmalıdır. "Exactly-once" bir sihir değil, uçtan uca dikkatli tasarımın sonucudur.

3. **`max.poll.interval.ms`'i aşan uzun işlem süreleri**: Consumer, mesajı işliyor gibi görünse de coordinator tarafından "ölü" sayılıp rebalance tetiklenir; bu da yarıdan kesilen işlem + duplicate + gereksiz rebalance fırtınasına yol açar. Savunma: uzun süren işlemleri ayrı bir thread/queue'ya devretmek, ya da poll aralığını işin gerçek süresine göre ayarlamak.

4. **Watermark/lateness ayarını iş gereksinimine göre kalibre etmemek**: Varsayılan değerlerle gidip "neden sayaçlarımız gerçek veriden düşük" sorusuna düşmek. Savunma: geç gelen veri oranını gözlemleyip (late-arrival histogram) tolerans değerini veriye dayalı seçmek, ve dışlanan veriyi bir side-output'a yönlendirip izlemek (sessizce atmamak).

5. **Consumer lag'i izlememek**: Streaming hattının "hayatta" olması, veri işliyor olması anlamına gelmez — birikiyor da olabilir. Savunma: lag'i, işleme gecikmesini (end-to-end latency) ve hata oranını (deserialization hataları, dead-letter queue boyutu) izleyen dashboard/alarm kurmak.

6. **Schema evrimini görmezden gelmek**: Producer bir alanın tipini değiştirir ya da alan ekler/çıkarırsa, eski consumer'lar deserialize hatası verebilir ya da sessizce yanlış veri okuyabilir. Savunma: schema registry kullanmak, geriye/ileriye uyumluluk (backward/forward compatibility) kurallarını zorunlu kılmak.

## Sonuç

Stream processing sistemlerinin gücü, "sınırsız veriyi sürekli ve ölçekli işleme" vaadinden gelir, ama bu vaat beraberinde dağıtık sistemlerin klasik zorluklarını taşır: kısmi hatalar, ağ gecikmeleri, zaman belirsizliği. Kafka'nın partition/offset modeli paralellik sağlar ama sıra garantisini partition sınırına hapseder; consumer group rebalancing esneklik sağlar ama geçici duraklama ve duplicate riski taşır; exactly-once semantics gerçek bir "sihirli tek teslim" değil, idempotent producer + transactional yazma + dikkatli tüketici tasarımı bileşimidir; windowing ise event-time ile processing-time arasındaki kaçınılmaz gerilimi watermark mekanizmasıyla yönetilebilir kılar. Bu iç mekanizmaları anlamayan bir mühendis, sistemi "çalışıyor" sanıp aslında sessizce veri kaybeden ya da çift işleyen bir hat kurabilir — bu yüzden savunma, önce mekanizmayı doğru modellemekle başlar.
