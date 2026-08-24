# Gözlemlenebilirlik Derinlik: Dağıtık İzleme (Distributed Tracing), OpenTelemetry, SLO/SLI/Hata Bütçesi

## Neden Bu Konu Önemli

"Observability" ve "loglama/telemetri" gibi genel başlıklar, bir mühendise "bir şeyler görüyorum" hissi verir ama gerçek soruyu cevaplamaz: **dağıtık bir sistemde bir istek 40 servisten geçerken, yavaşlık veya hata nerede başladı?** Log toplama tek başına bunu cevaplayamaz çünkü loglar servis-merkezlidir; her servis kendi dünyasından yazar, aralarındaki nedensellik ilişkisini kaybeder. Bu makale üç iç içe geçmiş derinliği ele alıyor:

1. **Dağıtık izleme (distributed tracing)** — bir isteğin sistem genelindeki yolculuğunu, sebep-sonuç zinciri olarak yeniden inşa etmek.
2. **OpenTelemetry (OTel)** — bunu vendor-lock-in olmadan, standart bir şekilde yapmanın endüstri protokolü.
3. **SLI/SLO/Hata Bütçesi (Error Budget)** — toplanan bu verinin "iyi mi kötü mü" sorusuna dönüştürülmesi ve alarm yorgunluğunun (alerting fatigue) sistematik olarak azaltılması.

Bunları ayrı ayrı bilmek yetmez; birbirine bağlı bir zincir olarak anlamak gerekir: trace context olmadan tracing çalışmaz, tracing olmadan SLI'lar kör olur, SLI olmadan SLO anlamsızdır, SLO olmadan alerting gürültüden ibarettir.

## Kök Neden: Neden Loglar ve Metrikler Yetmez

Bir monolitte hata ayıklamak basittir: stack trace tek bir process içinde, zaman sırasıyla dizilir. Mikroservis mimarisinde ise bir kullanıcı isteği şu şekilde ilerler:

```
Gateway -> Auth Servisi -> Sipariş Servisi -> Envanter Servisi -> Ödeme Servisi -> Mesaj Kuyruğu -> Bildirim Servisi
```

Her servisin kendi logu vardır. "Ödeme Servisi 250ms'de yanıt verdi" logunu görürsünüz ama bu 250ms'nin *kullanıcının gördüğü toplam gecikmenin* ne kadarını oluşturduğunu, hangi üst çağrının bu isteği tetiklediğini, paralel mi seri mi çalıştığını log satırlarından çıkaramazsınız. Bu, **korelasyon problemi**dir: dağınık kanıtları (loglar, metrikler) tek bir nedensellik grafiğine (causal graph) bağlayacak bir mekanizma yoktur.

Metrikler (örneğin CPU kullanımı, RPS, p99 gecikme) de agregattır — "sistem" seviyesinde neyin yanlış gittiğini söyler ama "hangi istek" veya "hangi çağrı zinciri" sorusuna cevap veremez. Loglar detaydır ama bağlamsız; metrikler bağlamsaldır ama detaysız. Dağıtık izleme, bu ikisinin arasındaki boşluğu dolduran üçüncü sinyal türüdür: **her bir isteğin, sistem genelindeki tam yürüyüşünü kaydeder.**

Bu üç sinyal türü (loglar, metrikler, izler) genellikle "gözlemlenebilirliğin üç sütunu" olarak anılır. Ama sütun metaforu biraz yanıltıcı: aslında birbirinden bağımsız üç direk değil, birbirine **bağlam üzerinden bağlı** üç görünümdür. İyi bir gözlemlenebilirlik sistemi, bir trace ID'den ilgili logları, ilgili metrik anormalliklerini çapraz sorgulayabilmelidir. Bu bağlamı taşıyan mekanizmanın adı **context propagation**'dır ve aşağıda detaylandırılıyor.

## Dağıtık İzlemenin Çalışma Mantığı

### Span ve Trace Kavramları

Bir **trace**, bir isteğin uçtan uca yolculuğunu temsil eden bir ağaçtır (aslında bir DAG'a yakındır ama pratikte çoğunlukla ağaç yapısındadır). Bu ağacın her düğümüne **span** denir. Bir span şunları taşır:

- **trace_id**: Tüm isteğin kimliği (isteğin başından sonuna kadar sabit kalır).
- **span_id**: Bu spesifik işlemin kimliği.
- **parent_span_id**: Bu işlemi kimin tetiklediği (ağaç yapısını kurar).
- **başlangıç zamanı ve süre**: Ne zaman başladı, ne kadar sürdü.
- **attributes/tags**: Anahtar-değer meta veri (http.method, db.statement, user.id gibi).
- **events**: Span içinde belirli anlarda olan şeyler (örneğin bir exception fırlatıldı).
- **status**: Başarılı mı, hata mı.

Bir trace'i bir "çağrı ağacı + zaman çizelgesi" olarak düşünün. Gateway'in span'ı, Auth Servisi'nin span'ının ebeveynidir (parent); Auth Servisi'nin span'ı da Sipariş Servisi çağrısının ebeveynidir. Bu hiyerarşi, bir gecikmenin nereden kaynaklandığını görsel olarak (flame graph / waterfall diagram) gösterir: eğer Ödeme Servisi'nin span'ı 3 saniye sürüyorsa ve toplam istek 3.2 saniye sürüyorsa, darboğaz nettir.

### Context Propagation: İşin Gerçek Zorluğu

Tracing'in teorik kısmı kolaydır; zor olan kısım, **trace_id ve parent_span_id'nin süreç sınırları arasında nasıl taşınacağı**dır. Bir servis HTTP ile başka bir servisi çağırdığında, bu bağlamı bir şekilde iletmesi gerekir; aksi halde her servis kendi izole trace'ini başlatır ve bunlar hiç birleşmez (bu, "kırık trace" — broken trace — problemi olarak bilinir).

Bunun standart çözümü **W3C Trace Context** başlığıdır (`traceparent` HTTP header). Format kabaca şöyledir:

```
traceparent: 00-<trace-id>-<parent-span-id>-<trace-flags>
```

Bir servis, gelen isteğin `traceparent` başlığını okur, kendi span'ını bu trace'in altına ekler, sonraki çağrıda güncellenmiş `traceparent`'ı yeni isteğe enjekte eder. Bu zincir kırılmadan devam ettiği sürece trace bütün olarak kalır.

Kırılma noktaları genellikle şunlardır:
- **Asenkron mesaj kuyrukları** (Kafka, RabbitMQ): HTTP başlığı yoktur; context'in mesaj metadata'sına (header) manuel olarak enjekte edilip tüketici tarafında çıkarılması (extract) gerekir. Bu adım unutulursa, kuyruk sonrası her şey yeni, bağlamsız bir trace olarak başlar.
- **Batch işler / cron görevleri**: Genellikle hiçbir çağıran context'i yoktur, bu yüzden kasıtlı olarak yeni bir trace başlatılır — bu doğru davranıştır, ama ekip bunu "eksiklik" sanıp gereksiz yere debug etmeye çalışabilir.
- **Eski (legacy) sistemler veya üçüncü taraf servisler**: Trace context'i anlamaz/geçirmez, zincir orada kopar. Çözüm genellikle "sınır span'ı" oluşturup, o sınırın ötesini ayrı bir trace olarak kabul etmektir.
- **Farklı vendor'ların uyumsuz format kullanması**: Bir sistem B3 header (Zipkin mirası), diğeri W3C Trace Context kullanıyorsa, ortak bir noktada çeviri (translation) katmanı gerekir. OpenTelemetry SDK'ları genellikle her ikisini de destekler ama yapılandırma gerektirir.

### Sampling: Hepsini Tutmak İmkânsız

Yüksek trafikli bir sistemde her isteğin tam trace'ini saklamak hem depolama hem performans açısından sürdürülemez. Bu yüzden **sampling** (örnekleme) stratejileri kullanılır:

- **Head-based sampling**: Karar, isteğin en başında (genellikle rastgele bir oranla, örn. %1) verilir. Basittir ama "ilginç" olayları (hatalar, yavaş istekler) kaçırma riski yüksektir — çünkü karar verildiğinde henüz isteğin hata vereceği bilinmez.
- **Tail-based sampling**: Karar, isteğin tamamı bittikten sonra verilir (örneğin "hata içeriyorsa" veya "p99'un üzerindeyse tut"). Daha akıllıdır ama tüm span'ların geçici olarak bir yerde (collector) tutulup karar sonrası atılmasını gerektirdiği için daha fazla kaynak ister ve mimari karmaşıklık ekler.
- **Adaptive/priority sampling**: Trafik hacmine göre oranı dinamik ayarlama, veya belirli kullanıcı/endpoint'leri her zaman örnekleme gibi hibrit yaklaşımlar.

Sampling kararı **kök neden analizinin doğrudan kalitesini belirler**: yanlış sampling stratejisi ile, tam da araştırmak istediğiniz nadir-ama-kritik hata trace'i hiç kaydedilmemiş olabilir. Bu, tracing sistemlerinin en sinsi tuzaklarından biridir — "izleme kurduk" demek "izliyoruz" demek değildir, "doğru anları örnekliyoruz" demektir.

## OpenTelemetry: Standardizasyonun Rolü

### Neden OpenTelemetry Var

OTel öncesinde her APM (Application Performance Monitoring) sağlayıcısının (Datadog, New Relic, vs.) kendi SDK'sı, kendi enstrümantasyon kütüphaneleri, kendi veri formatı vardı. Bir uygulamayı Datadog için enstrümante ettiyseniz, New Relic'e geçmek kod tabanınızda büyük bir yeniden yazım demekti — **vendor lock-in**. OpenTelemetry (CNCF projesi, OpenTracing ve OpenCensus'un birleşmesiyle doğdu), şu ayrımı standartlaştırır:

- **API/SDK katmanı**: Uygulamanızda "bu bir span, şu attribute'ları var" demenin vendor-tarafsız yolu.
- **Protokol (OTLP — OpenTelemetry Protocol)**: Verinin tel üzerinde nasıl taşınacağı.
- **Collector**: Veriyi toplayan, işleyen (batch, filtre, sampling), ve istediğiniz backend'e (Jaeger, Prometheus, Datadog, kendi depolamanız) yönlendiren ayrı bir bileşen.

Bu ayrımın kilit faydası: **enstrümantasyon kodu, backend seçiminden bağımsızdır.** Uygulama kodu OTel SDK'sına yazar; hangi görselleştirme/depolama aracının kullanılacağı, sadece Collector yapılandırmasında değişir — kod değişmez.

### Üç Sinyal, Tek API

OTel, logs, metrics, traces için **ortak bir veri modeli ve ortak bir SDK ailesi** sunar. Bu önemlidir çünkü artık üç sinyal, aynı "resource" (hangi servis, hangi versiyon, hangi ortam) ve aynı trace context ile etiketlenebilir — yani bir log satırından doğrudan ilgili trace_id'ye, oradan ilgili span'lara atlanabilir. Bu, "correlated observability" dediğimiz şeyin teknik temelidir.

### Auto-Instrumentation ve Manuel Enstrümantasyon Arasındaki Denge

OTel çoğu popüler framework için (HTTP sunucuları, veritabanı istemcileri, mesaj kuyrukları) **otomatik enstrümantasyon** ajanları sunar — kod değiştirmeden, çalışma zamanında (bytecode injection, monkey-patching gibi tekniklerle) span'lar otomatik oluşturulur. Bu hızlı başlangıç sağlar ama:

- Otomatik span'lar genellikle **iş mantığı** hakkında bilgi vermez (örneğin "bu hangi kullanıcı segmenti için işleniyor" gibi domain-özel attribute'lar).
- Aşırı-enstrümantasyon (her fonksiyon çağrısını span yapmak) trace'i okunamaz hale getirir ve overhead'i artırır.

En iyi pratik, otomatik enstrümantasyonu temel (HTTP, DB çağrıları) için kullanıp, **kritik iş mantığı sınırlarına** (örneğin "ödeme doğrulama", "envanter rezervasyonu") manuel, anlamlı span'lar eklemektir. Amaç "her şeyi izlemek" değil, **karar noktalarını ve hata olası bölgelerini** izlemektir.

### Yaygın Hatalar

- **Cardinality patlaması**: Attribute olarak yüksek kardinaliteli değerler (kullanıcı ID'si, tam URL query string, timestamp) metrik etiketi olarak kullanmak, backend'in (özellikle Prometheus tarzı time-series DB'lerin) patlamasına yol açar. Trace attribute'u olarak yüksek kardinalite sorun değildir (her span zaten benzersizdir) ama metrik etiketi olarak felakettir. Bu ayrımı karıştırmak sık görülen bir hatadır.
- **Collector'ı tek nokta hata (single point of failure) yapmak**: Collector düşerse, tüm telemetri kaybolabilir. Buffering, retry, ve gerekirse yerel disk'e yedekleme stratejisi olmadan production'a çıkmak risklidir.
- **Sampling oranını "varsayılan" bırakmak**: Çoğu SDK'nın varsayılanı (örneğin %100 head sampling test ortamında, çok düşük oran production'da yapılandırılmadan) ya maliyeti patlatır ya da kritik olayları kaçırır.
- **Context propagation'ı asenkron sınırlarda unutmak**: Yukarıda değinildi — mesaj kuyruklarında context enjekte/çıkarma adımı atlanırsa trace'ler parçalanır ve "neden trace'im yarım" sorusu haftalarca çözülemez.

## SLI, SLO ve Hata Bütçesi: Veriyi Karara Dönüştürmek

### Tanımlar ve Aralarındaki İlişki

- **SLI (Service Level Indicator)**: Ölçülen şey. Örnek: "başarılı isteklerin oranı", "p99 gecikme", "kuyruk işleme gecikmesi". SLI, doğrudan tracing ve metrik verisinden türetilir — örneğin span status'lerinden hata oranı, span süresinden gecikme dağılımı hesaplanır.
- **SLO (Service Level Objective)**: SLI için hedef eşik. Örnek: "30 günlük pencerede isteklerin %99.9'u 200ms altında yanıtlanmalı." SLO, içsel bir hedeftir (SLA'dan farklı olarak sözleşmesel/cezai yaptırımı yoktur, ama genellikle SLA'nın temelini oluşturur).
- **Hata Bütçesi (Error Budget)**: SLO'nun matematiksel tersi. SLO %99.9 ise, hata bütçesi %0.1'dir — yani 30 günde toplam ~43 dakikalık "izin verilen" kesinti/hata payı vardır.

Bu üçünün zinciri şudur: **Tracing/metrikler → SLI hesaplanır → SLI, SLO'ya karşı değerlendirilir → SLO ihlali riski, hata bütçesi tüketimi olarak izlenir → bütçe tüketim hızı, alarm ve karar mekanizmasını tetikler.**

### Kök Neden: Neden "Her Şeyi Alarma Bağlamak" Yanlış

Alerting fatigue (alarm yorgunluğu), bir ekip her küçük anormalliğe alarm kurduğunda oluşur: CPU %80'i geçti, disk %70 doldu, tek bir istek 500 hatası verdi. Bu alarmların çoğu **eyleme dönüşmez** (actionable değildir) — kimse gece 3'te CPU %81 için uyanmak istemez, çünkü genellikle kendiliğinden düzelir veya önemsizdir. Sonuç: ekip alarmları görmezden gelmeye başlar (normalization of deviance), ve gerçek bir kesinti olduğunda da alarm gürültüye karışır.

SLO/hata bütçesi yaklaşımının **kök nedeni çözme mantığı** şudur: alarmı ham metrik eşiğine değil, **kullanıcı deneyimini etkileyen bütçe tüketim hızına** bağlamak. Örneğin "CPU yüksek" değil, "hata bütçesinin %10'u son 1 saatte tüketildi, bu hızla devam edersek 6 saat içinde SLO'yu ihlal ederiz" — bu, hem **eyleme dönüşür** hem de **öncelik sinyali taşır** (yavaş tüketim = araştır; hızlı tüketim = şimdi müdahale et).

### Multi-Window, Multi-Burn-Rate Alerting

Basit bir "hata oranı eşiği geçti" alarmı iki şekilde başarısız olur:
- **Çok hassas kısa pencere**: 1 dakikalık hata oranı spike'ı, geçici bir network blip'inden kaynaklanabilir; gerçek sorun değildir ama alarm patlar.
- **Çok yavaş uzun pencere**: 30 günlük pencerede hata oranına bakarsanız, SLO ihlali gerçekleşene kadar fark etmeyebilirsiniz — reaktif değil, çok geç kalmış olursunuz.

Google SRE pratiğinden gelen çözüm, **çoklu pencere / çoklu yanma hızı (multi-window, multi-burn-rate)** alerting'dir: aynı anda hem kısa (örn. 5 dakika + 1 saat) hem uzun (örn. 6 saat + 3 gün) pencerelerde bütçe tüketim hızını izlemek, ve alarmı sadece **her iki pencerede de** anormal yanma hızı tutarlı olduğunda tetiklemek. Mantık: kısa pencere "şu an kötü mü" sorusuna, uzun pencere "bu geçici mi yoksa gerçek bir trend mi" sorusuna cevap verir. İkisi birden doğrulanınca gürültü büyük ölçüde elenir.

Bunun kök nedeni: tek bir eşik/pencere, "gürültü" ile "sinyal"i ayırt edecek yeterli bilgiye sahip değildir; sadece iki farklı zaman ölçeğinin **kesişimi**, gerçek bir trendi geçici bir dalgalanmadan güvenilir şekilde ayırabilir.

### En İyi Pratikler

- **SLI'yı kullanıcı deneyimine göre seçin, sisteme göre değil.** "Veritabanı bağlantı havuzu doluluğu" bir SLI değildir (bu bir iç metriktir); "kullanıcı isteklerinin başarı oranı" bir SLI'dır. İç metrikler, SLI'nın *nedenini* teşhis etmek için tracing/dashboard'da kullanılır ama SLO'nun kendisi olmamalıdır.
- **Az sayıda, anlamlı SLO tanımlayın.** Her endpoint için ayrı SLO tanımlamak, yönetilemez karmaşıklık yaratır. Kullanıcı yolculuğundaki kritik işlemlere (checkout, login, arama) odaklanın.
- **Hata bütçesini bir yönetim aracı olarak kullanın.** Bütçe tükenmişse, yeni özellik geliştirmeyi durdurup güvenilirliğe odaklanma kararı (feature freeze) SLO'nun doğal sonucu olmalıdır — bu, mühendislik ile ürün arasındaki "ne zaman hız keselim" tartışmasını veriye dayalı hale getirir.
- **SLO'yu tracing verisiyle besleyin, sadece agregat metriklerle değil.** Trace verisi, "hangi bağımlılık SLO ihlaline katkıda bulunuyor" sorusuna agregat metriklerden çok daha hızlı cevap verir çünkü nedensellik zincirini taşır.
- **Alarmları "sayfaya çağrılacak" (paging) ve "bilgi amaçlı" (ticket/dashboard) olarak ayırın.** Sadece kullanıcı etkisi olan, eyleme dönüşebilir ve aciliyeti olan durumlar insanı gece uyandırmalı; geri kalanı dashboard'da veya düşük öncelikli ticket olarak kalmalı.

### Yaygın Hatalar

- **SLA ile SLO'yu karıştırmak**: SLA cezai/sözleşmeseldir ve genellikle SLO'dan daha gevşek tutulur (marj bırakmak için); SLO'yu doğrudan SLA olarak dışarı vermek, iç esnekliği yok eder.
- **%100 hedefleme**: %100 kullanılabilirlik hedefi hem imkânsızdır hem de yanlış teşviktir — hiç risk almama (yeni deploy yapmama) teşvik eder. Hata bütçesinin *varlığının amacı*, kabul edilebilir bir risk payı üzerinden hız ile güvenilirlik arasında bilinçli denge kurmaktır.
- **Bütçe tüketimini sadece "toplam" olarak izleyip yanma hızını izlememek**: "Ayın 20 gününde bütçenin %5'i tükendi" bilgisi tek başına yeterli değildir; "son 1 saatte bütçenin %30'u tükendi" çok daha acil bir sinyaldir. Yanma hızı olmadan hata bütçesi, geriye dönük bir rapor kartına indirgenir, önleyici bir araç olmaktan çıkar.
- **SLI hesaplamasını yanlış katmanda yapmak**: Örneğin load balancer seviyesinde ölçülen "başarı oranı", uygulama seviyesinde sessizce yutulan hataları (örneğin retry ile maskelenen ama kullanıcı deneyimini kötüleştiren gecikmeler) kaçırabilir. SLI'nın, mümkün olduğunca kullanıcıya en yakın noktadan (client-side RUM, veya en azından edge/gateway) ölçülmesi gerekir.

## Tespit ve Savunma Perspektifi: Bir Sistemin "Sağlıklı Gözlemlenebilir" Olduğunu Nasıl Doğrularsınız

Bir savunmacı/mühendis gözüyle, gözlemlenebilirlik altyapısının kendisinin de doğrulanması gerekir:

1. **Trace bütünlüğü testi**: Bilinçli olarak sisteme uçtan uca bir test isteği gönderip (synthetic transaction), trace'in gerçekten tüm servisler boyunca kırılmadan, tek bir trace_id altında toplandığını doğrulayın. Kırık bir zincir varsa, tam da bir gerçek olayda ihtiyaç duyacağınız anda kör kalırsınız.
2. **Sampling'in kritik olayları kaçırmadığını doğrulayın**: Bilerek bir hata senaryosu (örneğin 500 hatası) tetikleyip, bu olayın trace backend'inde göründüğünü kontrol edin. Sadece "trace var" demek yetmez, "doğru anlarda trace var" demek gerekir.
3. **Alarm-eyleme dönüşüm oranını periyodik gözden geçirin**: Son N alarmın kaçının gerçek bir insan eylemine yol açtığını, kaçının "gürültü/kendiliğinden düzeldi" olarak kapandığını ölçün. Düşük eyleme-dönüşüm oranı, alerting fatigue'in somut bir göstergesidir ve alarm kurallarının (eşik, pencere, burn-rate mantığı) yeniden tasarlanması gerektiğine işaret eder.
4. **Hata bütçesi tüketim geçmişini bir post-mortem girdisi yapın**: Her SLO ihlalinde, hangi trace'lerin/span'ların kök nedeni gösterdiğini geriye dönük inceleyin; bu, sadece "neyin kırıldığını" değil "gözlemlenebilirlik sisteminin bunu ne kadar hızlı gösterebildiğini" de test eder — yani gözlemlenebilirlik altyapısının kendisinin MTTD (mean time to detect) üzerindeki etkisini ölçün.

Sonuç olarak, gözlemlenebilirlik derinliği; ham veri toplamaktan (log/metrik biriktirmek) **nedensellik taşıyan, standartlaştırılmış, ve karar-odaklı bir sinyal zincirine** geçiştir. Dağıtık izleme "ne oldu"yu bağlamla anlatır, OpenTelemetry bunu vendor-tarafsız ve tutarlı şekilde yapmanın iskeletini sağlar, SLI/SLO/hata bütçesi ise bu bağlamı "harekete geçmeli miyiz, ne zaman, ne kadar aciliyetle" sorusuna çeviren karar katmanıdır. Bu üçü birlikte kurulmadığında, ekipler ya kör kalır (yetersiz izleme) ya da sürekli gürültüde boğulur (aşırı, önceliksiz alarm) — ikisi de aynı kök nedenden, **bağlamsız veri toplamaktan**, kaynaklanır.
