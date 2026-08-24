# Dağıtık Sistemde Hata Ayıklama

## 1. Problem ve bağlam

Tek makinede çalışan bir programda hata ararken elinizde tam bir gerçek vardır: stack trace, tek bir saat, tutarlı bir bellek görüntüsü, adım adım ilerleyebileceğiniz bir debugger. Dağıtık bir sistemde bunların hiçbiri yoktur. On, yüz, bin makine birbirine ağ üzerinden mesaj atar; her birinin kendi saati, kendi belleği, kendi yerel doğrusu vardır. Bir istek yolunun ortasında kaybolur, bir servis diğerinin cevabını yanlış anlar, bir kuyruk sessizce dolar, ve sonuçta müşteri "bazen ödeme iki kere çekiliyor" der. "Bazen" kelimesi burada anahtardır: dağıtık hataların büyük çoğunluğu her zaman değil, belirli bir zamanlama, yük veya arıza kombinasyonunda ortaya çıkar.

Bu konu şunu çözer: **belirtinin göründüğü yer ile kök nedenin bulunduğu yer farklı makinelerde olduğunda, gerçeği nasıl yeniden inşa edersiniz.** Devreye girdiği anlar tipik olarak şunlardır: bir servis "yavaş" ama hangisi belli değil; hata oranı %0.3 gibi düşük ama sabit; sistem düşük yükte iyi, zirve yükte çöküyor; bir deploy sonrası "her şey aynı görünüyor ama latency arttı"; ya da en sinir bozucu olanı, aynı istek bazen çalışıp bazen çalışmıyor. Buradaki iş, tek bir "bug"ı bulmak değil, çoğu zaman sistemin **davranışını** anlamaktır. Bu ayrım, acemiyi profesyonelden ayıran ilk çizgidir.

## 2. Metodoloji ve karar ağacı (asıl değer)

Deneyimli biri dağıtık bir olaya girdiğinde önce **kod okumaz**. Bu çok önemli. Acemi hemen bir servisin kaynağına dalar, "burada bir mantık hatası olmalı" diye satır satır bakar. Profesyonel önce **sistemin o an ne yaptığını ölçer**, çünkü dağıtık hataların çoğu tek bir servisin mantığında değil, servisler *arasındaki* etkileşimde, zamanlamada, sırada ve arıza modlarında yaşar.

Zihnimdeki karar ağacı kabaca şöyle işler:

**Adım 0 — Belirtiyi somutlaştır.** "Yavaş" yeterli değil. Kaç milisaniye? p50 mi p99 mu bozuldu? Bütün istekler mi, belirli bir endpoint mi, belirli bir müşteri mi, belirli bir bölge mi? Ne zaman başladı? Bir profesyonelin ilk cümlesi neredeyse her zaman "bana tam zaman damgasını ve etkilenen isteklerin oranını ver" olur. Çünkü **"her zaman" bir bug'dır, "bazen" bir dağılımdır** ve ikisi bütünüyle farklı avlanır.

**Adım 1 — Değişen ne oldu?** Dağıtık sistemlerde kendiliğinden bozulan çok az şey vardır. Neredeyse her olayın arkasında bir değişiklik yatar: bir deploy, bir konfigürasyon, bir feature flag, bir trafik artışı, bir bağımlı servisin kendi deploy'u, bir sertifika süresinin dolması, bir disk dolması. İlk yaptığım şey **zaman çizelgesini olay zaman damgasıyla hizalamaktır**: bu dakikada ne deploy edildi, hangi flag açıldı, trafik grafiği ne gösteriyor. Vakaların belki yarısı burada, tek bir korelasyonla çözülür. Bu adımı atlamak, saatlerce kod okuyup sonunda "aslında dün gece bir config değişmiş" demektir.

**Adım 2 — Belirtiyi katmana yerleştir.** Sorun ağda mı, uygulamada mı, veri katmanında mı, altyapıda mı? Buradaki hızlı ayrımcı sorular: Hata oranı mı yoksa gecikme mi arttı? İkisi birden mi? Latency arttıysa **nerede** arttı — servisin kendi işleme süresinde mi (CPU/kilit), yoksa bir alt çağrıyı beklerken mi (downstream/ağ)? Bu ayrımı yapmanın tek dürüst yolu **span'lara bakmaktır** (aşağıda araçlar bölümünde). Bir isteğin toplam 800ms'sinin 780ms'si tek bir downstream çağrısını beklemekle geçiyorsa, sizin servisinizde arayacak bir şey yok — bir sonraki servise geçin. Bu "gecikmeyi takip et" yöntemi, dağıtık debugging'in belkemiğidir.

**Adım 3 — Belirti yönüne göre dallan.** Somut karar mantığım:

- **"p99 kötü ama p50 iyi"** görürsem: bu bir kaynak doygunluğu veya kuyruk problemidir, mantık hatası değil. Bir yerde bir havuz (thread pool, connection pool, dosya tanıtıcısı) tükeniyor, istekler kuyruğa giriyor. Kilitlenme (lock contention), garbage collection duraklamaları, ya da downstream'de yavaşlayan bir alt küme node. Buraya profiler ve havuz metrikleriyle giderim.

- **"hata oranı sabit ve düşük, ~%0.x"** görürsem: bu neredeyse her zaman ya belirli bir node'un/pod'un bozuk olması (yükün 1/N'i o node'a gidiyor), ya retry/timeout etkileşimi, ya da belirli bir veri şeklinin (belirli müşteri, belirli karakter, belirli boyut) tetiklediği bir kenar durumudur. İlk bakışım: hatalar tek bir host'ta mı toplanıyor? `group by host` yaptığımda dağılım düzse veri kaynaklı, tek host'ta yoğunsa altyapı kaynaklı düşünürüm.

- **"yük artınca çöküyor"** görürsem: retry fırtınası, thundering herd, ya da bir yerde geri basınç (backpressure) eksikliği ararım. Klasik senaryo: bir downstream yavaşlar → istemci timeout'a düşer → retry atar → downstream'in yükü artar → daha da yavaşlar → **retry'lar orijinal trafikten fazla olur** → çöküş. Buna metastable failure denir; sistem düşük yüke geri dönse bile kendi retry'ları yüzünden toparlanamaz.

- **"aynı istek bazen çalışıyor bazen çalışmıyor"** görürsem: bu bir yarış durumu (race), bir tutarlılık/replikasyon gecikmesi, ya da bir önbellek tutarsızlığıdır. En sık gerçek suçlu: **read-after-write tutarlılığı yok**. Yazma primary'ye gitti, okuma bir replica'ya düştü, replica henüz güncellenmemiş.

**Adım 4 — Hipotezi ucuz doğrula.** Profesyonel, "sanırım şu" dediğinde onu kanıtlamanın en ucuz yolunu arar. Bir log satırı ekleyip beklemek yerine, mevcut trace'te o span'ı bulmak; ya da tek bir isteğin correlation ID'siyle tüm servislerdeki izini toplamak. Buradaki takas nettir: **canlıda deneme yapmak pahalı ve riskli; gözlem ucuz.** Önce elde olan telemetriden azami bilgiyi sık, sonra gerekiyorsa hedefli log/trace eklerim.

Bu ağacın altında yatan tek felsefe şudur: **dağıtık sistemde asla varsayma, ölç.** "Ağ güvenilirdir", "saatler senkron", "downstream ya çalışır ya çalışmaz (ama yavaşlamaz)", "mesajlar sırayla gelir", "mesaj bir kez işlenir" — bunların hepsi *fallacies of distributed computing* olarak bilinen yanlış varsayımlardır ve her biri gerçek bir üretim olayının kök nedenidir.

## 3. Gerçek senaryo üzerinden yürüyüş

Somut, tekrar eden bir üretim olayı anlatayım; bunu bir e-ticaret ödeme akışı üzerinden vereyim çünkü klasiktir ve çoğu kişi başına gelmiştir.

**Belirti:** Müşteri destek "bazı kullanıcılar iki kere ücretlendiriliyor" diyor. Muhasebe bir günde ~40 çift çekim buldu; günde ~200.000 ödeme var. Yani oran ~%0.02. Klasik "bazen" problemi.

**Mimari:** `Checkout` servisi, `Payment` servisine senkron HTTP çağrısı yapıyor. `Payment` de dışarıdaki ödeme sağlayıcısına gidiyor, sonucu bir Postgres tablosuna yazıyor.

**Yürüyüş:**

Adım 0-1: Zaman çizelgesine baktım. Çift çekimler rastgele saatlerde değil, hafif de olsa **yüksek gecikme dönemlerinde** yoğunlaşıyordu. Ödeme sağlayıcısının p99 latency'si zirve saatlerde 2 saniyeden 6 saniyeye çıkıyordu.

Adım 2-3: `Checkout`'un `Payment`'a olan çağrısındaki timeout **3 saniye** idi ve başarısızlıkta **1 retry** yapıyordu. İşte hipotez: Sağlayıcı yavaşladığında, `Payment` sağlayıcıya isteği gönderiyor, sağlayıcı parayı çekiyor ama cevabı 5. saniyede dönüyor. Ama `Checkout` 3. saniyede timeout'a düşmüş ve **retry** atmış. İkinci deneme yeni bir ödeme başlatıyor — ikinci çekim.

Bu, hatalı kodun özüdür. `Payment` servisinin işleme mantığı kabaca şöyleydi:

```
fonksiyon odemeYap(istek):
    sonuc = saglayici.ucretlendir(istek.tutar, istek.kart)   # dış çağrı, yavaş olabilir
    veritabani.kaydet(istek.siparisId, sonuc)
    dön sonuc
```

`Checkout` tarafı:

```
cevap = http.post("payment/odemeYap", govde, timeout=3sn)
eğer cevap zaman_asimi_veya_hata:
    cevap = http.post("payment/odemeYap", govde, timeout=3sn)   # retry — TEHLİKE
```

Buradaki kök neden **idempotency (aynılık) garantisinin olmayışıdır**. Ağda hiçbir zaman "cevap gelmedi" ile "işlem olmadı"yı ayırt edemezsiniz. Timeout, isteğin başarısız olduğunu *kanıtlamaz*; sadece cevabın zamanında dönmediğini söyler. İşlem karşı tarafta pekâlâ başarılı olmuş olabilir. Retry atmak, "iki genç generalin ordusu" (Two Generals) probleminin ta kendisidir: mesajın ulaşıp ulaşmadığından asla emin olamazsınız.

**Düzeltme** iki katmanlıdır ve ikisi de gereklidir:

Birincisi, istemci **idempotency anahtarı** üretir ve retry'da *aynı* anahtarı gönderir:

```
idemKey = uuid()                      # istek başına BİR kez üret, retry'da AYNI kalır
govde.idempotencyKey = idemKey
cevap = http.post("payment/odemeYap", govde, timeout=3sn)
eğer cevap zaman_asimi_veya_hata:
    cevap = http.post("payment/odemeYap", govde, timeout=3sn)  # aynı idemKey
```

İkincisi, sunucu bu anahtarı **çekimden önce**, benzersiz kısıtlı bir tabloya yazarak ilk gören olur:

```
fonksiyon odemeYap(istek):
    # Anahtarı önce rezerve et. UNIQUE kısıt sayesinde ikinci istek burada patlar.
    eklendi = veritabani.ekleEğerYoksa(istek.idempotencyKey, durum="BASLADI")
    eğer değil eklendi:
        mevcut = veritabani.getir(istek.idempotencyKey)
        eğer mevcut.durum == "TAMAM":
            dön mevcut.sonuc          # daha önce başarılı olmuş, aynı cevabı ver
        değilse:
            dön "işleniyor, tekrar dene"   # ya da mevcut sonucu bekle
    sonuc = saglayici.ucretlendir(istek.tutar, istek.kart)
    veritabani.güncelle(istek.idempotencyKey, durum="TAMAM", sonuc=sonuc)
    dön sonuc
```

Kritik nokta: idempotency anahtarını **dış çağrıdan önce** yazmak. Eğer çekimden sonra yazsaydınız, tam da çekim ile yazma arasındaki pencerede gelen retry yine çift çekim yapardı. Ayrıca ödeme sağlayıcısının kendisi idempotency anahtarı destekliyorsa (çoğu ciddi sağlayıcı destekler), o anahtarı sağlayıcıya da geçirmek üçüncü ve en sağlam savunma hattıdır — böylece iki `Payment` node'u aynı anda denese bile sağlayıcı bir kez çeker.

Bu senaryonun öğrettiği genel ders: **retry ve timeout, çözüm gibi görünüp üretimde patlayan en yaygın çiftlerdir.** Retry'ı idempotency olmadan eklemek, bir hatayı bir veri bozulmasına çevirir.

## 4. Acemi vs profesyonel

**Timeout'u "yok" kabul etmek.** Acemi timeout'u "işlem olmadı" sanır. Profesyonel bilir ki timeout sadece "cevabı zamanında görmedim" demektir; işlem olmuş da olabilir. Para, e-posta, sipariş oluşturma gibi yan etkili işlemlerde bu ayrım milyon liralık farktır.

**Retry'ı her yere serpmek.** Acemi "hata mı aldın, tekrar dene" mantığını her katmana ekler. Sonuç: A→B→C zincirinde her katman 3 retry yaparsa, en alttaki servis **27 kat** yük görür. Buna retry amplification denir. Profesyonel retry'ı yalnızca **bir** katmanda, üstel geri çekilme (exponential backoff) ve **jitter** (rastgele sapma) ile, ve yalnızca *idempotent* ve *geçici* (5xx, timeout) hatalarda yapar. 4xx'e retry atmak anlamsızdır, sadece yükü artırır.

**Backoff'a jitter koymamak.** Acemi "1s, 2s, 4s bekle" der. Ama 1000 istemci aynı anda başarısız olursa hepsi tam olarak aynı anda tekrar dener — senkronize dalgalar, thundering herd. Profesyonel bekleme süresine rastgelelik ekler ki dalga yayılsın.

**Log'lara güvenip trace'i ihmal etmek.** Acemi her serviste ayrı ayrı log'a bakar, sonra bunları elle birleştirmeye çalışır. Bir isteğin 8 servisteki izini elle kovalamak saatler yer. Profesyonel her isteğe en kenarda bir **correlation/trace ID** iliştirir, tüm servisler bunu log'a ve bir sonraki çağrıya taşır; böylece tek bir kimlikle tüm yolculuğu görür. Bu ID yoksa, ilk yapılacak iş onu eklemektir — çünkü onsuz her soruşturma iki kat uzar.

**Saatlerin senkron olduğunu varsaymak.** Acemi iki farklı makinenin log zaman damgasını doğrudan karşılaştırıp "A, B'den önce oldu" der. Makine saatleri saniyeler kayabilir; NTP bile mükemmel değildir. Nedensel sıra için duvar saati değil, **mantıksal saat** (Lamport, vektör saat) ya da tek bir merkezi izleme sistemi gerekir. "Wall clock ile sıralama" pek çok yanlış teşhisin kaynağıdır.

**Ortalamaya bakmak.** Acemi "ortalama latency 120ms, iyiyiz" der. Ama ortalama, sizi öldüren kuyruğu gizler. Kullanıcıların %1'i 5 saniye bekliyorsa ortalama bunu yutar. Profesyonel **her zaman yüzdelik dilimlere** (p50/p90/p99/p99.9) bakar. Üretimde sizi arayan müşteri p99'daki müşteridir. Dahası, bir kullanıcı bir sayfada 10 alt-istek yapıyorsa, o kullanıcının en az bir p99 isteğine denk gelme olasılığı çok yüksektir — buna "tail latency amplification" denir.

**"Bende çalışıyor" yanılgısı.** Acemi hatayı yerelde tek makinede tekrar üretmeye çalışır, olmayınca "reprodüksiyon yok" der. Dağıtık hataların çoğu tek makinede *asla* tekrar üretilemez, çünkü hata tam da eşzamanlılıktan, ağ gecikmesinden, yükten doğar. Profesyonel reprodüksiyonu üretim benzeri koşulda arar: yük altında, gecikme enjekte ederek, birden çok node ile.

**Idempotent olmayanı at-least-once kuyruğa koymak.** Acemi bir mesaj kuyruğu (Kafka, SQS vb.) kullanır ve "mesaj bir kez işlenir" sanır. Çoğu kuyruk **en az bir kez** (at-least-once) teslim eder — yani aynı mesaj tekrar gelebilir, özellikle tüketici çökerse. Consumer idempotent değilse, çift işleme kaçınılmazdır. Bu, 3. bölümdeki para hatasının kuyruk versiyonudur ve en az onun kadar sık görülür.

**Kısmi başarısızlığı görmezden gelmek.** Tek makinede işlem ya tümüyle olur ya olmaz. Dağıtıkta, üç servisten ikisi başardı biri başaramadı diye bir durum vardır — sistem tutarsız bir ara halde kalır. Acemi mutlu yolu kodlar. Profesyonel "peki bu adımdan sonra, bir sonrakinden önce çökerse ne olur?" sorusunu her adım için sorar, ve telafi (saga, outbox pattern) ya da idempotent yeniden deneme ile kapatır.

## 5. Araçlar ve saha notları

**Dağıtık izleme (distributed tracing).** Tek en değerli araç. OpenTelemetry standardı ile Jaeger, Tempo, Zipkin ya da ticari APM'ler (Datadog, Honeycomb, New Relic) bir isteğin tüm servislerdeki span'larını tek bir zaman çizelgesinde gösterir. Bir isteğin nerede zaman harcadığını *tahmin etmeden* görürsünüz. Saha notu: **context propagation** doğru kurulmazsa trace'ler kopar; her servisin gelen trace başlığını okuyup giden çağrıya taşıdığından emin olun. Asenkron sınırlarda (kuyruk, thread havuzu) bağlam en sık burada kaybolur.

**Yapılandırılmış log + korelasyon.** Log'ları düz metin değil, JSON gibi yapılandırılmış yazın ve her satıra trace_id, span_id, kullanıcı/istek kimliği koyun. Böylece merkezi bir sistemde (Elasticsearch/OpenSearch, Loki, Splunk) tek bir ID ile tüm servisleri filtreleyebilirsiniz. Honeycomb tarzı **yüksek kardinalite** desteği burada altın değerindedir: "hangi müşteri ID'sinde hata var" gibi soruları önceden metrik tanımlamadan sorabilmek, "bazen" hatalarını avlamanın en hızlı yoludur.

**Metrikler ve RED/USE.** Servis başına **RED** (Rate, Errors, Duration) ve kaynak başına **USE** (Utilization, Saturation, Errors) panoları temel gözlem setidir. Prometheus + Grafana yaygın kombinasyondur. Metrikler "ne zaman ve nerede" sorusunu ucuza cevaplar; trace "neden" sorusunu cevaplar. İkisi birlikte kullanılır: metrik alarmı verir, trace kök nedeni bulur.

**Profiler.** Latency bir servisin *kendi içinde* (downstream beklemede değil) ise, CPU/allocation profiler devreye girer. Continuous profiling (Pyroscope, Parca, ya da dilin kendi araçları) üretimde sürekli örnek alır; "hangi fonksiyon CPU yiyor", "GC neden duraklıyor" sorularını cevaplar. Saha notu: kilit çekişmesi (lock contention) CPU profilinde görünmez; bunun için blocking/off-CPU profiline ya da thread dump'a bakın. p99'u bozan şey çoğu zaman CPU değil, bir kilidi ya da bir bağlantıyı beklemektir.

**Kaos ve hata enjeksiyonu.** Dağıtık hataları güvenilir üretmek için hatayı *kasten* enjekte edersiniz: gecikme ekleme, paket düşürme, node öldürme (toxiproxy, service mesh fault injection, Chaos Monkey türevleri). "Downstream 5 saniye yavaşlarsa ne olur" sorusunu tahmin etmek yerine test edersiniz. Bir retry/timeout hatasını doğrulamanın en dürüst yolu budur — üretimde beklemek yerine staging'de gecikme enjekte edip davranışı gözlemlemek.

**tcpdump / paket seviyesi.** Nadiren ama kurtarıcı olarak: "istek gerçekten gitti mi, cevap geldi mi" gibi en alt seviye soruda uygulama log'u yalan söyleyebilir ama tel üzerindeki paket söylemez. TLS ile içerik görünmese de bağlantının kurulup kurulmadığı, RST gelip gelmediği, retransmit olup olmadığı görünür. "Bağlantı yarıda kapanıyor" tarzı hayalet hataların çoğu burada çözülür.

**Service mesh gözlemi.** Istio/Linkerd gibi bir mesh varsa, uygulamaya hiç dokunmadan servisler arası latency, hata, retry sayılarını verir; ayrıca timeout/retry/circuit-breaker politikalarını merkezi yönetmenizi sağlar. Retry amplification'ı mesh seviyesinde sınırlamak, her servise ayrı ayrı kod yazmaktan sağlamdır.

**Pratik saha tüyoları:**

- **Correlation ID'yi ilk gün ekleyin.** Bir olay patladığında eklemeye çalışmak geç kalmaktır. En kenardaki giriş noktasında (API gateway/load balancer) üretin, her yere taşıyın.
- **Circuit breaker koyun.** Bir downstream sürekli başarısızsa, ona istek atmayı bir süre durdurun (devreyi açın). Bu, yavaşlayan bir servisin tüm sistemi kilit havuzu tükenmesiyle yere sermesini önler — bomba tahliyesi gibi.
- **Timeout'ları uçtan uca bütçeleyin.** İç içe çağrılarda dıştaki timeout, iç toplamdan büyük olmalı; yoksa iç çağrı hâlâ çalışırken dış timeout'a düşer ve boşa iş yapılır. "Deadline propagation" — kalan süreyi aşağı taşımak — bunu düzeltir.
- **Retry'ı yalnızca idempotent + geçici hatada, backoff+jitter ile, tek katmanda yapın.**
- **Kuyruk tüketicilerini idempotent yazın.** At-least-once teslimatı veri gerçeği kabul edin; işlenmiş mesaj kimliklerini saklayın ya da işlemi doğal olarak idempotent kurun (upsert gibi).
- **Alarmı belirtiye değil, kullanıcı etkisine bağlayın.** "CPU %90" bir alarm değildir; "checkout hata oranı %1'i geçti" alarmdır. SLO tabanlı alarm gürültüyü keser.
- **Post-mortem'i suçsuz (blameless) yapın.** İnsan hatasını değil, sistemin o hatayı mümkün kılan tasarımını arayın; yoksa aynı sınıf hata farklı isimle geri gelir.

**Örnek bir gerçek soruşturma diyaloğu (zihinsel akış).** Bir olayda kafamın içinde şu sırayla ilerlerim, ve bu sırayı bilinçli tutmak acemiyi profesyonele en çok yaklaştıran alışkanlıktır. "Belirti ne, sayıyla?" → "p99 checkout latency 300ms'den 4s'ye çıkmış, hata oranı normal." → "Ne zaman başladı? 14:32." → "14:32'de ne oldu? Deploy yok, ama trafik grafiği normal. Bir dakika — bir bağımlı servis, `Inventory`, 14:30'da deploy almış." → "Trace aç: checkout span'ının 3.8 saniyesi `Inventory.check` çağrısında geçiyor." → "`Inventory`'nin kendi trace'i: 3.7 saniye bir veritabanı sorgusunda." → "O sorgu yeni deploy'da değişmiş mi? Evet, bir `WHERE` koşulundan indeks kullanan bir kolon çıkarılmış, sorgu full table scan'e düşmüş." Toplam süre: on beş dakika, ve tek satır uygulama kodu okumadan. Çünkü gecikmeyi katman katman takip etmek, kör kod okumaktan her zaman hızlıdır. Buradaki ders: **span, kök nedene doğru bir ok gibi gösterir; siz sadece oku takip edin.**

Bu örnek aynı zamanda şunu gösterir: dağıtık bir olayın kök nedeni sıklıkla "dağıtık" bile değildir — tek bir servisteki bir indeks kaybı, bir kilit, bir bellek sızıntısıdır. Ama *belirti* başka bir serviste, başka bir ekipte, başka bir dashboard'da göründüğü için dağıtık bir problem gibi hissedilir. Profesyonelin işi, belirtinin göründüğü yerden kök nedenin yaşadığı yere köprüyü hızlı kurmaktır; gözlemlenebilirlik tam da bu köprüdür.

**Bir uyarı — "değişen ne oldu" her zaman sizin değişikliğiniz değildir.** Kendi deploy'unuz temiz olabilir, ama bir bağımlı servis, bir bulut sağlayıcının bölgesel yavaşlaması, bir DNS değişikliği, bir sertifika yenilenmesi, ya da paylaşılan bir veritabanındaki başka bir ekibin ağır sorgusu sizin sisteminizi bozabilir. "Biz bir şey değiştirmedik" cümlesi doğru olabilir ama olayı çözmez; soru "sistemin gördüğü dünyada ne değişti" olmalıdır, sadece "biz ne değiştirdik" değil. Bu ayrım, ekipler arası "top bende değil" tartışmasında saatler kazandırır.

Son bir çerçeve: dağıtık debugging'de gerçek düşman bilgi eksikliğidir. Tek makinede gerçek elinizin altındadır; dağıtıkta gerçeği **inşa etmek** zorundasınız — trace, log, metrik ve kimliklerle. Sisteminize gözlemlenebilirliği ne kadar erken ve ne kadar tutarlı gömerseniz, "bazen ödeme iki kere çekiliyor" cümlesi karşınıza çıktığında o kadar az korkarsınız. Çünkü profesyonelliğin özü hatayı hiç yapmamak değil — hata olduğunda onu birkaç dakikada, tahmin etmeden görebilecek altyapıyı önceden kurmuş olmaktır.
