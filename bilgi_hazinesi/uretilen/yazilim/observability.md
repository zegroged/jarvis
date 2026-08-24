# Gözlemlenebilirlik (Observability)

## Tanım

Gözlemlenebilirlik (observability), bir sistemin dışarıya yaydığı sinyallere bakarak iç durumunu ne kadar iyi anlayabildiğimizin ölçüsüdür. Terim aslında kontrol teorisinden gelir: bir sistem, çıktılarını gözlemleyerek iç state'inin çıkarsanabildiği ölçüde "gözlemlenebilir"dir. Yazılım dünyasında bu kavram şuna dönüşür: üretimde (production) beklenmedik bir davranış ortaya çıktığında, koda yeni instrumentation eklemeden, elimizdeki telemetri verisiyle "neden bu oldu?" sorusuna cevap verebiliyor muyuz?

Buradaki kritik ayrım, gözlemlenebilirliği geleneksel monitoring'den ayıran şeydir. Monitoring, önceden bildiğiniz sorulara cevap vermek üzere kurulur: "CPU kullanımı %90'ı geçti mi?", "hata oranı eşiği aştı mı?". Yani bilinen arıza modlarını (known failure modes) izlersiniz. Gözlemlenebilirlik ise bilinmeyen bilinmeyenler (unknown unknowns) içindir: daha önce hiç görmediğiniz, dashboard'unuza koymayı akıl edemediğiniz bir arıza türü ortaya çıktığında, ham veriyi keserek ve dilimleyerek (slice and dice) sorunun köküne inebilme yeteneği. Modern dağıtık sistemlerde (distributed systems), mikroservisler, otomatik ölçeklenen konteynerler ve dış bağımlılıklarla birlikte, arızaların büyük çoğunluğu artık "bunu hiç öngörmemiştim" kategorisine girdiği için gözlemlenebilirlik zorunlu hale gelmiştir.

Gözlemlenebilirlik pratikte üç temel telemetri türü — metrics, logs ve traces — üzerine kurulur. Bunlara sıklıkla "gözlemlenebilirliğin üç direği" (three pillars) denir. Ancak bu üç sinyali ayrı silolarda tutmak yerine, birbirine bağlanmış (correlated) tek bir bütün olarak düşünmek daha doğrudur; bu makalenin ilerleyen bölümlerinde bu bağlantının neden bu kadar önemli olduğunu göreceğiz.

## Kök neden: Neden üç ayrı sinyal türüne ihtiyaç duyarız?

Üç sinyal türünün var olmasının nedeni tesadüf değil; her biri farklı bir maliyet/bilgi dengesi (trade-off) üzerinde oturur. Bunu anlamak, hangi durumda hangi aracı kullanacağınızı ve neden hepsine birden ihtiyacınız olduğunu netleştirir.

Temel gerilim şudur: bir olay hakkında ne kadar çok ayrıntı saklarsanız, o kadar çok soruya cevap verebilirsiniz — ama depolama ve işleme maliyeti de o kadar artar. Üç sinyal türü bu spektrum üzerinde farklı noktalarda durur.

### Metrics: sayısal toplulaştırma (aggregation)

Metric, zaman içinde ölçülen bir sayıdır — istek sayısı, gecikme (latency), kuyruk uzunluğu, bellek kullanımı gibi. Metrikleri güçlü kılan şey toplulaştırılabilir (aggregatable) olmalarıdır. Milyonlarca isteği tek tek saklamak yerine, "son bir dakikada saniyede kaç istek geldi" bilgisini sabit boyutta bir sayaçta biriktirirsiniz. Bu yüzden metrikler ucuzdur ve maliyeti trafikle orantılı olarak patlamaz; 10 istek de gelse 10 milyon istek de gelse metriğin depolama maliyeti aynıdır.

Bu ucuzluğun bedeli ise ayrıntı kaybıdır. Bir metrik size "hata oranı yükseldi" diyebilir ama "hangi kullanıcının, hangi isteğinin, neden başarısız olduğunu" söyleyemez. Metriklerdeki bilgi, önceden seçtiğiniz boyutlar (dimensions / labels) üzerinden gruplanmıştır ve o boyutlar dışına çıkamazsınız.

Burada devreye kardinalite (cardinality) problemi girer ve bu, metrik sistemlerinin en yaygın tuzağıdır. Kardinalite, bir metriğin sahip olduğu benzersiz etiket kombinasyonlarının sayısıdır. `http_requests_total{method, status}` gibi bir metrik düşük kardinaliteye sahiptir çünkü method ve status'ün alabileceği değerler sınırlıdır. Ama etikete `user_id` veya `request_id` eklerseniz, her benzersiz kullanıcı için ayrı bir zaman serisi (time series) oluşur ve kardinalite patlar (cardinality explosion). Prometheus gibi sistemlerde her benzersiz etiket kombinasyonu bellekte ayrı bir seri olarak tutulduğundan, bu durum sistemin belleğini tüketip çökmesine yol açar. Kural olarak: sınırsız veya yüksek kardinaliteli değerleri asla metrik etiketi yapmayın.

### Logs: ayrık olayların kaydı

Log, belirli bir anda olan ayrık (discrete) bir olayın kaydıdır. Metriğin aksine log, bir olay hakkında zengin, yapılandırılmış bağlam taşıyabilir. Modern pratikte kritik olan nokta, düz metin loglar yerine yapılandırılmış loglama (structured logging) kullanmaktır — yani her log satırını JSON gibi makine tarafından işlenebilir bir formatta, anahtar/değer çiftleri olarak üretmek.

Bunun kök nedeni şudur: `"Kullanıcı 42 için ödeme başarısız oldu, tutar 199.90"` gibi bir metin satırını sonradan sorgulamak, regex ile ayrıştırmayı (parsing) gerektirir ve kırılgandır. Aynı bilgiyi `{"event": "payment_failed", "user_id": 42, "amount": 199.90, "reason": "insufficient_funds"}` şeklinde yapılandırırsanız, log toplama sistemi bu alanlar üzerinde doğrudan filtreleme, gruplama ve toplulaştırma yapabilir. Yapılandırılmış loglama, logları aranabilir bir veri kaynağına dönüştürür.

Logların bedeli hacimdir. Her olay için bir kayıt ürettiğiniz için, log hacmi trafikle doğrusal olarak büyür ve yüksek trafikli sistemlerde depolama ile taşıma (ingestion) maliyetinin en büyük kalemi genellikle loglardır. Bu yüzden örnekleme (sampling), log seviyesi (log level) yönetimi ve saklama süresi (retention) politikaları kritiktir.

### Traces: bir isteğin uçtan uca yolculuğu

Trace, tek bir isteğin sistem içindeki tüm yolculuğunu — hangi servislerden geçtiğini, her adımda ne kadar zaman harcadığını — uçtan uca kaydeden yapıdır. Bir trace, span adı verilen birbirine bağlı iş birimlerinden oluşur; her span bir işlem parçasını (örneğin bir HTTP çağrısı, bir veritabanı sorgusu) temsil eder ve başlangıç zamanı, süre ile üst span'e referans (parent-child ilişkisi) taşır. Bu ilişkiler birleştiğinde, isteğin bir ağaç yapısında nasıl dallandığını gösteren tam bir resim çıkar.

Traces'in var oluş nedeni doğrudan mikroservis mimarisinin doğasında yatar; bir sonraki bölümde bunu detaylandıracağız.

## Dağıtık izleme (distributed tracing): kök neden ve çalışma mantığı

### Problem: monolit'in ölümü tek noktalı görünürlüğü öldürdü

Tek parça (monolith) bir uygulamada bir isteğin neden yavaş olduğunu anlamak nispeten kolaydı: tek bir process içinde profiler çalıştırır, stack trace'e bakardınız. Ama bir istek 15 farklı mikroservisten geçtiğinde, her servis kendi makinesinde, kendi log dosyasına yazdığında, "bu istek neden 3 saniye sürdü?" sorusu felç edici hale gelir. Yavaşlık hangi serviste? Bir servis mi diğerini bekliyor? Bir veritabanı sorgusu mu tıkandı, yoksa bir dış API çağrısı mı zaman aşımına uğradı? Ayrı ayrı loglara bakarak bu bilgiyi elle birleştirmek pratikte imkânsızdır.

Dağıtık izleme tam olarak bu problemi çözmek için doğdu. Fikrin kökeni büyük ölçekli sistemlerin bu ihtiyacından çıkmıştır; Google'ın Dapper sistemi ve onu takip eden açık kaynak projeler (Zipkin, Jaeger) bu alanın temelini attı.

### Çalışma mantığı: context propagation

Dağıtık izlemenin kalbinde **bağlam yayılımı (context propagation)** yatar ve bu mekanizmayı anlamak, izlemenin nasıl çalıştığını anlamanın anahtarıdır.

İş şöyle yürür: Bir istek sisteme ilk girdiğinde, ona benzersiz bir **trace ID** atanır. Bu trace ID, isteğin dokunacağı tüm servisler boyunca taşınır. Her servis kendi işini yaparken bir **span** oluşturur; bu span, aldığı trace ID'yi ve kendisini çağıran span'in ID'sini (parent span ID) kaydeder. Servis bir başka servisi çağırdığında, trace ID ve mevcut span ID'yi çağrıya — tipik olarak HTTP header'ları içinde — enjekte eder. Alıcı servis bu header'ları okur, kendi span'ini bu bağlama bağlar ve zinciri devam ettirir.

Bu yayılımın standartlaşması gözlemlenebilirlik dünyasının en önemli gelişmelerinden biridir. W3C **Trace Context** standardı, `traceparent` adında bir HTTP header tanımlar; bu header trace ID, parent span ID ve örnekleme kararını (sampling flag) taşır. Standart sayesinde farklı dillerde, farklı kütüphanelerle yazılmış servisler aynı trace'e katkı yapabilir — çünkü hepsi aynı header formatını konuşur.

Sonuçta trace verileri merkezi bir sisteme (backend'e) gönderilir; orada aynı trace ID'ye sahip tüm span'ler toplanır, parent-child ilişkilerine göre birleştirilir ve isteğin uçtan uca zaman çizelgesi (genellikle şelale/waterfall görünümü olarak) yeniden inşa edilir. Artık hangi span'in en uzun sürdüğünü, nerede beklendiğini, nerede paralellik olduğunu tek bakışta görebilirsiniz.

### Somut örnek

Diyelim ki bir e-ticaret sitesinde "sipariş ver" isteği geliyor:

1. `api-gateway` isteği alır, trace ID `abc123` üretir, bir span açar.
2. `order-service`'i çağırır; `traceparent` header'ında `abc123`'ü ve kendi span ID'sini gönderir.
3. `order-service` sırayla `inventory-service` (stok kontrolü), `payment-service` (ödeme) ve `notification-service` (bildirim) çağırır. Her biri `abc123` altında kendi span'ini oluşturur.
4. `payment-service` bir dış banka API'sini çağırıyor ve bu 2.8 saniye sürüyor.

Backend'de trace'e baktığınızda şelale görünümünde `payment-service`'in dış çağrısının toplam sürenin neredeyse tamamını kapladığını anında görürsünüz. Loglara tek tek bakarak asla bu kadar hızlı ulaşamazdınız. İşte dağıtık izlemenin sunduğu değer budur: gecikmenin nerede biriktiğini kanıtlarıyla göstermek.

### Örnekleme (sampling): kaçınılmaz bir uzlaşma

Her isteği tam olarak izlemek çoğu yüksek trafikli sistemde hem çok pahalı hem gereksizdir. Bu yüzden örnekleme yapılır. İki temel yaklaşım vardır ve aralarındaki fark önemlidir:

- **Head-based sampling (baştan örnekleme):** Karar, trace daha başlarken (ilk span'de) verilir; örneğin isteklerin %1'ini izle. Basit ve öngörülebilirdir ama sorunu şudur: hata veren veya çok yavaş olan istekler tam da izlemek istediğiniz isteklerdir, ancak baştan karar verdiğiniz için onları kaçırma ihtimaliniz yüksektir.
- **Tail-based sampling (kuyruktan örnekleme):** Karar, trace tamamlandıktan sonra verilir. Böylece "hata içeren veya belirli bir süreyi aşan tüm trace'leri sakla, gerisinden az örnek al" gibi akıllı politikalar kurabilirsiniz. Dezavantajı, karar verilene kadar tüm span'leri geçici olarak tamponlamak (buffering) gerektiğidir; bu da daha fazla altyapı kaynağı ve karmaşıklık demektir.

Doğru seçim trafiğinize ve bütçenize bağlıdır, ama genel eğilim, sorunlu trace'leri kaçırmamak için tail-based sampling'e doğrudur.

## Üç sinyali birbirine bağlamak: gerçek güç korelasyonda

Metrics, logs ve traces'i ayrı ayrı toplamak faydalıdır ama asıl sıçramayı bunları birbirine bağladığınızda yaparsınız. Bunun neden bu kadar önemli olduğunu tipik bir arıza akışıyla görelim.

Bir uyarı (alert) tetiklenir: checkout servisinin p99 gecikmesi (latency) eşiği aştı — bu bir **metrik** sinyalidir; size bir problem *olduğunu* söyler ama *nedenini* söylemez. Metrik dashboard'unda o zaman aralığındaki yavaş isteklere ait örnek **trace'lere** atlarsınız (exemplar denilen mekanizma tam da metrikten trace'e bu köprüyü kurar). Trace'i açtığınızda gecikmenin `payment-service`'te biriktiğini görürsünüz. O span'e bağlı **loglara** geçersiniz ve `{"error": "connection pool exhausted"}` mesajını bulursunuz. Böylece metrik → trace → log zinciriyle dakikalar içinde kök nedene inersiniz.

Bu köprülerin çalışması için sinyallerin ortak kimliklerle işaretlenmesi (korelasyon) gerekir. En yaygın pratik, her log satırına ilgili `trace_id` ve `span_id`'yi eklemektir. Böylece bir trace'ten "bu span sırasında hangi loglar üretildi?" diye tek tıkla geçebilirsiniz. Bu korelasyon olmadan üç sinyal üç ayrı ada olarak kalır ve her arızada üçünü elle eşleştirmek için zaman kaybedersiniz.

## OpenTelemetry: standartlaşmanın neden önemli olduğu

Geçmişte her gözlemlenebilirlik satıcısının kendi ajanı, kendi SDK'sı ve kendi veri formatı vardı. Bu, satıcı kilitlenmesine (vendor lock-in) yol açardı: bir satıcıdan diğerine geçmek, tüm kodunuzdaki instrumentation'ı yeniden yazmak demekti.

**OpenTelemetry (OTel)**, bu problemi çözmek için ortaya çıkan, telemetri üretimi için satıcıdan bağımsız bir standart ve araç setidir. Metrics, logs ve traces için ortak bir veri modeli, ortak API/SDK'lar ve **OTLP** (OpenTelemetry Protocol) adında ortak bir kablo protokolü tanımlar. Ayrıca **OpenTelemetry Collector** adında, telemetriyi toplayıp, işleyip (örneğin örnekleme, filtreleme, zenginleştirme) istediğiniz backend'e yönlendiren bir ara katman bileşeni sunar.

Bunun getirdiği kök fayda şudur: instrumentation'ı bir kez OTel ile yaparsınız, sonra Collector'daki tek bir yapılandırma değişikliğiyle verinizi hangi backend'e göndereceğinize karar verirsiniz. Uygulama koduna dokunmadan satıcı değiştirebilirsiniz. Bu esneklik, OTel'i modern gözlemlenebilirlik yığınının fiili standardı haline getirmiştir.

## SLO, SLI ve SLA: gözlemlenebilirliği iş kararına bağlamak

Toplanan tüm bu telemetri, "sistemim yeterince iyi mi?" sorusuna disiplinli bir cevap üretmediği sürece havada kalır. İşte bu noktada **hizmet seviyesi (service level)** kavramları devreye girer ve gözlemlenebilirliği mühendislik kararlarına bağlar.

Üç terimi net ayırmak gerekir çünkü sıklıkla karıştırılırlar:

- **SLI (Service Level Indicator):** Servis kalitesinin ölçülen, sayısal bir göstergesidir. Örnek: "başarılı isteklerin toplam isteklere oranı" (availability), veya "isteklerin ne kadarının 300 ms altında tamamlandığı" (latency). SLI, doğrudan telemetriden — genellikle metriklerden — hesaplanır.
- **SLO (Service Level Objective):** SLI için koyduğunuz hedeftir. Örnek: "30 günlük pencerede istek başarı oranı %99.9 olmalı". SLO, mühendislik ekibinin kendisine koyduğu iç hedeftir.
- **SLA (Service Level Agreement):** Müşteriyle yapılan, ihlali durumunda finansal veya sözleşmesel sonuçları olan resmi taahhüttür. SLA genellikle SLO'dan daha gevşek tutulur ki iç hedefi kaçırmak hemen sözleşme ihlaline dönüşmesin.

### Error budget: SLO'nun asıl gücü

SLO'yu gerçekten güçlü kılan kavram **hata bütçesidir (error budget)**. Mantığı şudur: %100 güvenilirlik ne mümkündür ne de arzu edilir — ona ulaşmaya çalışmak inovasyonu felç eder ve maliyeti astronomik olur. Eğer SLO'nuz %99.9 ise, bu örtük olarak "%0.1'lik bir başarısızlığa izin veriyorum" demektir. İşte bu %0.1, harcayabileceğiniz hata bütçenizdir.

Bu bütçe, mühendislik kararlarına somut bir çerçeve verir. Bütçeniz henüz tükenmediyse, hızlı hareket edebilir, yeni özellikler yayınlayabilir, risk alabilirsiniz. Bütçenizi tükettiyseniz, bu güçlü bir sinyaldir: yeni özellik geliştirmeyi durdurup güvenilirliğe (reliability) odaklanmanız gerekir. Böylece "ne kadar risk alalım?" tartışması öznel bir çekişme olmaktan çıkıp veriye dayalı, otomatik bir karara dönüşür. Site Reliability Engineering (SRE) pratiğinin merkezinde bu fikir yatar.

### Burn rate: hata bütçesini akıllıca alarma bağlamak

Hata bütçesini ne zaman "yaktığınızı" ölçen kavrama **burn rate (yanma oranı)** denir. Burn rate 1 ise, bütçenizi tam olarak SLO penceresinin sonunda bitirecek hızda harcıyorsunuz demektir. Burn rate 10 ise, bütçeyi on kat hızlı tüketiyorsunuz — bu ciddi bir acil durumdur.

Bu neden önemli? Çünkü naif eşik uyarıları ya çok gürültülüdür ya da çok geç kalır. Geleneksel "hata oranı %1'i geçti" uyarısı, kısa süreli bir dalgalanmada gereksiz yere çalar (alert fatigue / uyarı yorgunluğu yaratır) ya da yavaş ama sürekli bir bozulmayı kaçırır. Bunun yerine **çok pencereli, çok oranlı burn rate uyarıları (multi-window multi-burn-rate alerts)** kullanılır: hem kısa hem uzun bir zaman penceresini aynı anda kontrol edersiniz. Hızlı yanmayı yakalamak için kısa pencerede yüksek burn rate ararsınız (hızlı ama hassas tepki); yavaş sızıntıyı yakalamak için uzun pencerede düşük burn rate ararsınız. İki pencerenin de aynı anda ihlal olması, sadece o zaman sayfa (page) atmanız, hem gürültüyü azaltır hem de önemli olayları kaçırmamanızı sağlar.

## Yaygın hatalar ve tuzaklar

Alanda tekrar tekrar görülen, maliyetli hataları toplu halde ele alalım; bunların çoğu yukarıda anlatılan kök nedenleri göz ardı etmekten doğar.

**Metriklerde kardinalite patlaması.** Daha önce vurgulandı ama en sık yaşanan üretim kazalarından biri olduğu için tekrar edilmeyi hak ediyor: `user_id`, `request_id`, `email`, `session_id` gibi sınırsız kardinaliteye sahip alanları metrik etiketi yapmak. Bu, metrik backend'inizi (özellikle Prometheus tipi sistemleri) bellek tükenmesiyle çökertir. Bu tür yüksek kardinaliteli bilgiler loglara veya trace'lere aittir, metriklere değil.

**Yapılandırılmamış, tutarsız loglama.** Serbest metin loglar, olay anında "işe yarar gibi" görünür ama üretimde arıza ararken felaket olur. Farklı servisler farklı formatlarda, farklı zaman damgası (timestamp) biçimlerinde, tutarsız alan adlarıyla yazınca korelasyon imkânsızlaşır. Baştan yapılandırılmış (structured) ve tüm servisler arasında tutarlı bir şema ile loglamak şarttır.

**Trace context'i kaybetmek.** Dağıtık izleme, `traceparent` header'ının her servis sınırında doğru şekilde iletilmesine bağlıdır. Asenkron kuyruklar (message queue), thread havuzları, background job'lar veya elle yazılmış HTTP istemcileri bağlamı düşürebilir. Bir yerde bağlam koptuğunda trace ikiye bölünür ve "yetim" (orphan) span'ler oluşur; izlemenin en çok işe yarayacağı asenkron akışlarda tam da bu kopmalar yaşanır. Kuyruk mesajlarına trace context'i elle enjekte etmek gerekir.

**Hassas veriyi telemetriye sızdırmak.** Loglara veya span'lere şifre, kredi kartı numarası, kişisel veri (PII) yazmak yaygın ve tehlikeli bir hatadır. Telemetri sistemleri genellikle uygulama veritabanından daha geniş bir kitleye açıktır ve daha uzun saklanır. Üretim öncesi bir redaksiyon/maskeleme (scrubbing) katmanı — tercihen Collector seviyesinde — kurmak gerekir.

**Uyarı yorgunluğu (alert fatigue).** Her metriğe eşik uyarısı koymak, ekibi gerçek acil durumlara karşı duyarsızlaştıran bir gürültü seli yaratır. İnsanın gecenin bir yarısı uyandırılmasını hak eden uyarı, kullanıcıyı etkileyen, hemen müdahale gerektiren durumlardır. Uyarıları sistem iç metriklerine (CPU %80 oldu gibi) değil, kullanıcıyı etkileyen belirtilere (symptom-based alerting) — yani SLO ihlallerine — bağlamak bu gürültüyü kökten azaltır.

**Sadece ortalamaya (average) bakmak.** Gecikme metriklerinde ortalama yanıltıcıdır çünkü birkaç aşırı yavaş isteği (ki bunlar en çok acı çeken kullanıcılardır) kalabalığın içinde gizler. Bunun yerine yüzdelik dilimlere (percentile) — p50, p95, p99 — bakmak gerekir. p99 gecikme, "en kötü %1 kullanıcının deneyimi" demektir ve gerçek kullanıcı acısını ortalamadan çok daha dürüst yansıtır. Ayrıca yüzdeliklerin farklı makinelerden geldikten sonra matematiksel olarak toplanamayacağını (ortalamaların ortalaması gibi p99'ların p99'u alınamaz) bilmek, doğru toplulaştırma için histogram tabanlı yaklaşımları gerektirir.

**"Üç direği" birbirinden kopuk kurmak.** Metrics, logs ve traces'i üç ayrı araçta, hiç korelasyon olmadan toplamak, teknik olarak "gözlemlenebilirliğimiz var" dedirtir ama pratikte her arızada üç ekranı elle eşleştirmekle zaman kaybettirir. Değerin büyük kısmı, önceki bölümde anlattığımız gibi, sinyaller arası köprülerdedir (`trace_id` loglarda, exemplar'lar metriklerde).

## En iyi pratikler

**Instrumentation'ı OpenTelemetry ile standartlaştırın.** Satıcı bağımsız kalmak, tek bir veri modeli konuşmak ve gelecekte esneklik için OTel'i temel alın. Otomatik instrumentation (auto-instrumentation) kütüphaneleri, popüler framework'ler için sıfır kod değişikliğiyle temel trace ve metrikleri sağlar; buradan başlayıp kritik iş mantığına elle span ekleyerek zenginleştirin.

**SLO'ları kullanıcı deneyiminden türetin, sistem içi metriklerden değil.** "CPU %70" bir SLO değildir; kullanıcı bunu umursamaz. "İsteklerin %99.9'u başarılı ve 300 ms altında" bir SLO'dur. SLI'ları seçerken hep "bu, kullanıcının gerçekten hissettiği bir şey mi?" diye sorun. İyi bir SLI genellikle "iyi olay / geçerli olay" oranı biçimindedir.

**Hata bütçesini bir karar aracı olarak kullanın.** SLO'yu sadece bir dashboard sayısı olarak değil, geliştirme hızını yöneten bir kaldıraç olarak kullanın. Bütçe sağlıklıyken hızlanın, tükendiğinde güvenilirliğe yatırım yapın. Bu politikayı ekipçe önceden yazılı olarak anlaşmak, kriz anındaki tartışmaları önler.

**Uyarıları belirtiye (symptom) bağlayın ve burn rate kullanın.** İnsanı uyandıran uyarılar kullanıcı etkisiyle ilişkili olmalı. Çok pencereli burn rate uyarıları, hem hızlı felaketleri hem yavaş sızıntıları düşük gürültüyle yakalar. Nedene (cause) dayalı uyarıları — "disk doluyor" gibi — ise sayfa atmayan, iş saatlerinde bakılan tiketlere yönlendirin.

**Kardinaliteyi bilinçli yönetin.** Yüksek kardinaliteli boyutları trace ve loglara koyun; metrikleri düşük, sınırlı kardinaliteli etiketlerle sade tutun. Yeni bir metrik etiketi eklemeden önce "bu değer kaç farklı olabilir?" diye sorun; cevap sınırsızsa etikete koymayın.

**Loglamayı baştan yapılandırın ve tutarlı bir şema uygulayın.** JSON tabanlı, tüm servislerde ortak alan adlarına sahip (örneğin her yerde `trace_id`, `service.name`, `severity`) bir loglama standardı belirleyin. Her log'a mümkün olduğunca `trace_id` iliştirerek loglar ile trace'ler arası köprüyü otomatik kurun.

**Örnekleme stratejisini bilinçli seçin.** Yüksek trafikte her trace'i saklamak gereksiz ve pahalıdır; ama hataları ve yavaş istekleri kaçırmamak da kritiktir. Mümkünse tail-based sampling ile "ilginç" (hatalı veya yavaş) trace'leri her zaman saklayın, geri kalanından temsili bir örnek alın.

**Saklama (retention) ve maliyeti proaktif yönetin.** Telemetri maliyeti — özellikle log ingestion — sessizce büyür ve bir gün faturada patlar. Ham veriyi kısa süre, toplulaştırılmış/özetlenmiş veriyi uzun süre saklayın. Collector seviyesinde gereksiz gürültülü logları filtreleyin, düşük değerli verileri düşürün.

**Gözlemlenebilirliği sonradan değil baştan tasarlayın.** En iyi zaman, sistemi kurarken instrumentation'ı içine örmektir. Üretimde bir arıza olduğunda "keşke şunu loglasaydım" demek, gözlemlenebilirliğin var olma nedeninin — yeni kod yazmadan bilinmeyen soruları cevaplayabilmenin — tam olarak başarısız olduğu andır. Yeni bir servis yazarken trace, metrik ve yapılandırılmış logları en baştan, bir birinci sınıf gereksinim (first-class requirement) olarak ele alın.

## Özet

Gözlemlenebilirlik, bir sistemin dışarı yaydığı sinyallerden iç durumunu — özellikle daha önce öngörülmemiş arızaları — anlayabilme yeteneğidir ve modern dağıtık sistemlerde bir lüks değil zorunluluktur. Üç temel sinyal — metrics (ucuz, toplulaştırılmış, düşük ayrıntı), logs (zengin bağlam, yüksek hacim), traces (isteğin uçtan uca yolculuğu) — farklı maliyet/bilgi dengelerinde durur ve asıl güçleri birbirine bağlandıklarında (korelasyon) ortaya çıkar. Dağıtık izleme, mikroservislerde kaybolan tek noktalı görünürlüğü, bağlam yayılımı (context propagation) yoluyla geri kazandırır. OpenTelemetry bu telemetriyi satıcıdan bağımsız üretmenin fiili standardı haline gelmiştir. Nihayetinde SLO ve hata bütçesi disiplini, tüm bu veriyi "ne kadar risk alalım, nereye yatırım yapalım" gibi somut mühendislik kararlarına bağlayarak gözlemlenebilirliği teknik bir merak olmaktan çıkarıp iş değerine dönüştürür.
