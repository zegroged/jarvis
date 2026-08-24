# Observability ile Hata Ayıklama: Trace, Log ve Metrik

## 1. Problem ve bağlam

Tek bir makinede çalışan monolitik bir uygulamada hata ayıklamak görece kolaydır: `gdb` veya bir IDE debugger'ı iliştir, breakpoint koy, çağrı yığınına bak. Ama üretimde işler böyle yürümez. İstek bir load balancer'dan giriyor, üç mikroservise dağılıyor, arada bir mesaj kuyruğu var, iki farklı veritabanı, bir de üçüncü parti ödeme sağlayıcısı. Kullanıcı "sepete ekle butonu bazen 8 saniye sürüyor" diyor. Bazen. Üretimde. Yeniden üretemiyorsun. Breakpoint koyacak tek bir yer yok, çünkü sorun tek bir yerde değil.

Observability tam olarak bunu çözer: **sistemin dışarıya yaydığı sinyallere (log, metrik, trace) bakarak, içeride ne olduğunu, üstelik daha önce hiç sormadığın soruları bile, sonradan sorabilmek.** Buradaki kilit ayrım "monitoring" ile arasındaki fark. Monitoring önceden bildiğin soruların cevabını gösterir (CPU %90'ı geçti mi?). Observability ise henüz aklına gelmemiş soruların cevabını verebilecek kadar zengin veri toplamandır ("dün gece 03:14'te, yalnızca Almanya'daki iOS kullanıcıları için, belirli bir ürün kategorisinde checkout'un neden yavaşladığı"). Bu ayrımı içselleştirmek, aracı seçmekten çok daha önemli.

Ne zaman devreye girer? Sorun "reprodüce edilemez", "aralıklı", "yalnızca üretimde", "yalnızca belirli kullanıcılarda" olduğunda. Yani debugger'ın işe yaramadığı her yerde. Bir de dağıtık sistemlerde, çünkü orada tek bir çağrı yığını yoktur; çağrı yığını ağ üzerine dağılmıştır ve onu ancak trace birleştirir.

## 2. Metodoloji ve karar ağacı (asıl değer)

Acemi bir alarm gördüğünde doğrudan log'lara dalar ve `grep` yapmaya başlar. Kıdemli mühendis üç sinyali bir **piramit** gibi kullanır ve yukarıdan aşağı iner. Sıralama önemli, çünkü her adım aramayı daraltır ve pahalı olanı (log) en sona bırakır.

**Adım 0 — Semptomu netleştir.** "Yavaş" yeterli değil. Kimin için yavaş? p50 mi p99 mu bozuldu? Eğer p50 iyi ama p99 kötüyse bu bir *kuyruk problemi* (kaynak doygunluğu, GC duraklaması, kilit çekişmesi, soğuk cache) işaretidir, sistematik bir hata değil. Eğer p50 de bozulduysa herkes etkileniyor demektir; muhtemelen bir bağımlılık komple yavaşladı. Bu tek ayrım bile araştırma yönünü ikiye böler. Ortalama gecikmeye (average latency) bakmak burada en klasik acemi tuzağıdır; ortalama, p99'daki felaketi gizler.

**Adım 1 — Metrikle "nerede" ve "ne zaman" sorusunu daralt.** Metrik ucuzdur, önceden toplanmıştır, geriye dönük bakarsın. Amacın kök neden bulmak değil, *problemin sınırlarını çizmek*. Hangi servis? Ne zaman başladı? Bir deploy'la mı örtüşüyor? Trafik artışıyla mı? Burada RED (Rate, Errors, Duration — istek gören servisler için) ve USE (Utilization, Saturation, Errors — kaynaklar için: CPU, disk, kuyruk, bağlantı havuzu) çerçeveleri pusuladır. Hata oranı mı arttı yoksa gecikme mi? İkisi birlikte mi? Deploy zaman damgasıyla grafikteki kırılma noktası çakışıyorsa araştırmanın %70'i bitmiştir — muhtemel şüpheli son değişikliktir.

**Adım 2 — Trace'le "hangi adım" sorusunu sor.** Metrik sana "checkout servisi yavaş" dedi. Ama checkout servisi 12 şeyi çağırıyor. Trace, tek bir yavaş isteğin uçtan uca dökümünü, her span'in (alt işlemin) ne kadar sürdüğünü gösterir. Burada aradığın şey **kritik yol (critical path)**: toplam süreyi belirleyen span zinciri. Çoğu zaman gözün bir tek şişkin span'e takılır — "envanter servisine yapılan çağrı 7.9 saniye". İşte kök neden orada. Trace'in en güçlü yanı, gecikmenin *kimin suçu* olduğunu ortaya çıkarmasıdır: kendi kodun mu, bir downstream bağımlılık mı, yoksa ikisinin arasındaki ağ/kuyruk bekleme süresi mi. Acemi "servisim yavaş" der; trace çoğu zaman "hayır, senin servisin başka birini beklerken boşta oturuyor" der.

**Adım 3 — Log'la "tam olarak neden" sorusunu sor.** Artık hangi servisin, hangi span'inde, hangi zaman aralığında sorun olduğunu biliyorsun. *Şimdi* log'a inersin — ama körlemesine `grep` değil, elinde trace_id ile. Yapısal log'ların (structured logging) trace_id taşıyorsa, o tek trace'e ait bütün log satırlarını saniyeler içinde çekersin. Exception mesajı, stack trace, o anki değişken değerleri orada. Log en pahalı, en gürültülü, en yüksek kardinaliteli sinyaldir; bu yüzden en sona bırakılır ve daima daraltılmış bir pencerede okunur.

Karar ağacının özü şu takas etrafında döner: **metrik ucuz ama düşük çözünürlüklü (bireysel isteği göremezsin), log pahalı ama yüksek çözünürlüklü, trace ikisi arasında köprü.** Yukarıdan başlayıp aşağı inmek, hem maliyeti hem de bilişsel yükü minimize eder. Aşağıdan başlamak — yani doğrudan terabaytlarca log içinde arama yapmak — aceminin gece 3'te saatlerini yediren yoldur.

Bir dallanma daha: **"Hata mı, yavaşlık mı?"** Hatalar için trace'te error=true span'lerine ve exception log'larına gidersin, iş nispeten nettir. Yavaşlık için ise doygunluğu (saturation) kovalarsın: bağlantı havuzu doldu mu, thread pool tükendi mi, GC duraklaması mı, disk IO mu, downstream mi yavaşladı. Yavaşlık her zaman "yavaş kod" değildir; çoğu zaman "sınırlı bir kaynak için bekleme"dir. Bu ayrımı yapamayan, kodu optimize etmeye çalışıp asıl darboğazı (havuz boyutu) atlar.

**Zaman korelasyonu — en güçlü tek soru.** Bir kıdemli mühendisin ilk refleksle sorduğu soru neredeyse her zaman aynıdır: "Ne değişti ve ne zaman?" Grafikteki kırılma noktasının tam zamanını al, sonra o pencereye ne denk geliyor diye bak: deploy mu, feature flag açılışı mı, konfigürasyon değişikliği mi, cron job mu, trafik zirvesi mi, bir downstream sağlayıcının olayı mı, sertifika süresi dolması mı, ay sonu batch işi mi? Olayların %80'i bir değişiklikle örtüşür. Bu yüzden deploy zaman damgalarını, feature flag geçmişini ve konfigürasyon değişikliklerini metrik grafiklerinin üstüne bindirebilmek (annotation / dağıtım işaretleri) paha biçilmez bir kolaylıktır. "Dün geceye kadar çalışıyordu" cümlesi bir ipucudur, laf değil: iki durum arasındaki *fark* neredeyse her zaman kök nedendir.

**"Bilinen-iyi" ile karşılaştır.** Tek bir grafiğe bakıp "bu yüksek mi?" diye sormak anlamsızdır; referansın olmadan yüksek/düşük diye bir şey yoktur. Pro her zaman bir temel çizgiyle (baseline) kıyaslar: geçen haftanın aynı saati, sağlıklı başka bir bölge, canary ile stable sürüm, ya da olaydan önceki gün. Aynı dashboard'da "şimdi vs bir hafta önce" katmanı, anomaliyi bir bakışta ortaya çıkarır. Mutlak sayılar yanıltır; sapma konuşur.

## 3. Gerçek senaryo üzerinden yürüyüş: aralıklı checkout yavaşlığı

Somut bir vaka üzerinden gidelim. E-ticaret. Alarm: checkout p99 gecikmesi 800 ms'den 9 saniyeye çıktı. p50 hâlâ 300 ms. Hata oranı normal. Yani herkes değil, isteklerin küçük bir kısmı felaket yavaş — klasik kuyruk problemi.

**Metrik adımı.** Grafiklere bakıyorum. p50 sabit, p99 tavan yapmış. Bu tek başına "sistematik bug değil, doygunluk" der. Deploy geçmişini üst üste bindiriyorum — son 6 saatte deploy yok. Demek ki kod değişmedi, koşullar değişti. Trafik grafiğine bakıyorum: istek hacmi %20 artmış. Küçük bir artış p99'u 10 kat bozuyorsa, bir yerde doğrusal olmayan bir davranış, tipik olarak bir kuyruk doygunluğu var. USE çerçevesi: DB bağlantı havuzu kullanımı grafiğine bakıyorum — havuz %100'e yapışmış ve "bağlantı bekleme süresi" metriği tavan yapmış. Şüphe kristalize oldu: bağlantı havuzu darboğazı.

**Trace adımı.** Yavaş isteklerden birinin trace'ini açıyorum (çoğu araç p99 üstü trace'leri örneklemenizi sağlar). Uçtan uca 9 saniye. Span dökümü şöyle:

```
checkout-request                          9.2 s
  auth-check                              12 ms
  load-cart                               8 ms
  reserve-inventory                       15 ms
  ├─ acquire-db-connection                8.4 s   ← DEVASA
  └─ execute-update                       22 ms
  charge-payment                          410 ms
  emit-order-event                        30 ms
```

`execute-update` yalnızca 22 ms sürüyor — yani sorgu hızlı. Ama `acquire-db-connection` 8.4 saniye! Kod yavaş değil; kod bir bağlantı *alabilmek için* kuyrukta bekliyor. Trace, "SQL'i optimize et" gibi yanlış bir yola sapmamı engelledi. Sorun sorguda değil, havuza erişimde.

**Log adımı.** Trace_id'yi alıp o servisin log'larını o pencerede çekiyorum. Şöyle satırlar var: `WARN HikariPool-1 - Connection is not available, request timed out after 8400ms` ve öncesinde `Pool stats: total=20, active=20, idle=0, waiting=37`. 20 bağlantılık havuz, 37 istek sırada bekliyor. Kök neden doğrulandı.

**Neden şimdi patladı?** Log'ları biraz geri sararak `reserve-inventory` içinde yeni bir yavaş sorgunun (envanter tablosunda eksik index yüzünden, ama nadir bir kategori için) bağlantıyı normalden 5 kat uzun tuttuğunu görüyorum. Trafik %20 artınca, uzun tutulan bağlantılar birikip havuzu tıkadı. Yani zincir şu: *nadiren yavaş bir sorgu → bağlantı uzun süre meşgul → trafik artınca havuz tükendi → bekleyen istekler p99'u patlattı.* Hiçbir kod deploy edilmemişti; sistem sadece bir eşiği aştı.

**Düzeltme.** İki katmanlı. Kısa vade: havuz boyutunu ve bağlantı zaman aşımını gözden geçir, yavaş sorguya `statement_timeout` koy ki bir bağlantıyı sonsuza kadar rehin almasın. Kalıcı çözüm: envanter tablosundaki eksik index'i ekle, böylece o sorgu 5 kat değil normal sürede biter. Doğrulama: index eklendikten sonra aynı trafik altında `acquire-db-connection` span'i milisaniyelere döndü, `waiting` sayacı sıfırlandı. Kritik nokta: düzeltmeyi de aynı sinyallerle *doğruladım*. "Deploy ettim, herhalde düzelmiştir" demedim; metrikte havuz bekleme süresinin düştüğünü gözlerimle gördüm.

Bu vakanın dersi: üç sinyal birlikte çalıştı. Metrik "ne zaman ve hangi kaynak" dedi, trace "hangi adım" dedi, log "tam olarak neden" dedi. Herhangi birini atlasaydım ya yanlış yolu kovalar (sorguyu optimize etmek) ya da saatlerce log içinde boğulurdum.

## 4. Acemi vs pro: tuzaklar

**Ortalamaya bakmak.** En yaygın hata. Ortalama gecikme yalan söyler. 100 isteğin 99'u 100 ms, biri 10 saniye sürerse ortalama ~200 ms çıkar ve her şey yolunda görünür — ama bir kullanıcı 10 saniye bekledi. Pro her zaman persentillere (p50, p95, p99, p99.9) bakar. Dağıtık sistemde asıl acıyı p99 ve kuyruğun kuyruğu (tail latency) verir.

**Log'a trace_id koymamak.** Yapısal olmayan, bağlamsız log en pahalı ve en işe yaramaz şeydir. `logger.info("işlem başladı")` — hangi işlem? Hangi kullanıcı? Hangi istek? Pro her log satırına trace_id, user_id, request_id gibi *yüksek kardinaliteli* alanları yapısal olarak (JSON) ekler. Böylece log, trace ile korelasyona girer. Acemi düz metin log yazar ve sonra `grep`le onu ayrıştırmaya çalışır.

**Her şeyi log'lamak (veya hiç log'lamamak).** İki uç da yanlış. Her isteğe debug log basmak hem maliyeti patlatır hem de sinyali gürültüde boğar; asıl olay geldiğinde milyonlarca satırın içinde kaybolur. Öte yandan yetersiz log da körlük yaratır. Pro dengeyi bilir: hata yollarını ve durum geçişlerini bol log'lar, mutlu yolu (happy path) örnekler veya sadece metrikle takip eder.

**%100 trace örneklemesi (sampling) yapmak.** Acemi "her isteği trace'leyeyim, sonra lazım olur" der. Üretim hacminde bu hem devasa maliyet hem de performans yüküdür. Pro *tail-based sampling* kullanır: tüm trace'leri geçici tutar ama yalnızca *ilginç* olanları (hatalı, yavaş, nadir) kalıcı saklar. Böylece p99 trace'i her zaman elindedir ama depolama maliyeti makul kalır. Ama dikkat: baş-tabanlı örneklemede (head-based) yavaş isteği baştan yakalayamayabilirsin — bu ince ayar kritiktir.

**Kardinalite bombası.** Bu, deneyimli olmayanın metrik sisteminin faturasını (ve bazen kendisini) patlatan tuzaktır. Bir metriğe user_id veya request_id gibi milyonlarca farklı değer alabilen bir etiket (label/tag) eklemek, zaman serisi sayısını patlatır. `http_requests_total{user_id="..."}` milyonlarca ayrı seri yaratır ve Prometheus'u dize düşürür. Kural: **yüksek kardinaliteli veri log'a/trace'e gider, metriğe asla.** Metrik etiketleri sınırlı, sayılabilir kümeler olmalı (endpoint, status_code, region). Bu ayrımı bilmemek, hem para hem gözlemlenebilirlik kaybettirir.

**Saat senkronizasyonuna güvenmek.** Dağıtık trace'lerde farklı makinelerin saatleri birkaç milisaniye kayabilir. Acemi span sürelerini mutlak zaman damgalarına göre yorumlamaya çalışıp "negatif süre" gibi imkânsız şeyler görür. Pro göreli süreleri ve span üst-alt ilişkisini esas alır, saat kaymasını hesaba katar.

**"Deploy ettim, düzeldi herhalde."** Doğrulamasız düzeltme. Bir düzeltmeyi ürettiğin sinyalle doğrulamadıysan, işi bitirmemişsindir. Belki semptom trafik düştüğü için geçici kayboldu, kök neden duruyor. Pro düzeltmeden önce ve sonra aynı grafiği yan yana koyar.

**Cardinality/gürültü yüzünden alarm körlüğü.** Çok fazla alarm kuran ekip, alarmlara duyarsızlaşır. Gece 3'te 40 sayfa gelirse hiçbirine bakılmaz. Pro alarmı *semptoma* kurar (kullanıcı etkileniyor mu — SLO ihlali) değil *nedene* (CPU %80'i geçti — belki de normaldir). "CPU yüksek" alarm değildir; "istekler yavaşlıyor ve kullanıcı etkileniyor" alarmdır.

**Trace'i olmayan async sınırları.** Mesaj kuyruğu, background job, thread havuzu geçişlerinde trace bağlamı (context) kopar. Acemi kuyruğa mesaj atar ve trace orada biter; tüketici tarafı ayrı, bağlantısız bir trace olur. Pro trace bağlamını mesaj başlığına (header) enjekte eder ve tüketicide devam ettirir. Aksi halde uçtan uca resmin tam ortasında kör nokta oluşur.

**Log'da hassas veri sızdırmak.** Acemi hata ayıklarken "her şeyi bas, sonra bakarım" der ve request body'yi olduğu gibi log'lar. İçinde parola, kredi kartı, kişisel veri (PII), oturum token'ı olabilir. Bir kez log deposuna yazıldığında bu veri aylarca orada durur, erişimi geniştir ve bir sızıntıda felakete döner. Pro daha en baştan log'a giren alanları maskeler/redakte eder, hassas alanları enstrümantasyonda karalar. Gözlemlenebilirlik uğruna gizlilik/uyumluluk (GDPR/KVKK) ihlali etmek en pahalı "hata ayıklama" olur.

**Semptomu sinyalle değil hisle kovalamak.** Acemi "sanırım şu servistir" der ve o servisin koduna dalar, oysa hiçbir sinyal oraya işaret etmemiştir. Bu, doğrulama yanlılığıyla saatler yakar. Pro her hipotezi bir sinyalle sınar: "Şuysa, şu grafikte şunu görmeliyim." Görmüyorsa hipotez ölür, yenisine geçilir. Hata ayıklama bir tahmin yarışı değil, kanıta dayalı eleme sürecidir.

**Yalnızca ortalama örnekleme oranına güvenip nadir olayı kaçırmak.** Head-based sampling'de %1 örneklerken, saniyede bir olan kritik ama nadir bir hatayı hiç yakalayamayabilirsin — trace'i baştan atılmıştır. Pro hata ve yüksek gecikme için ayrı, %100'e yakın örnekleme kuralı tanımlar; sıradan başarılı isteği seyrek örnekler. Örneklemeyi "tek oran" sanmak, tam da ihtiyaç duyduğun anda elinin boş kalmasına yol açar.

## 5. Araçlar ve saha notları

**Standart olarak OpenTelemetry (OTel).** Bugün pratikte tartışmasız başlangıç noktası. Neden? Çünkü satıcı bağımsızdır (vendor-neutral). Enstrümantasyonu OTel ile yaparsın, veriyi istediğin backend'e (Jaeger, Tempo, Datadog, Honeycomb, ne olursa) yollarsın. Kod değişmeden backend değiştirebilmek büyük bir kaldıraçtır. Otomatik enstrümantasyon kütüphaneleri (HTTP client, DB driver, web framework) çoğu span'i sen elle yazmadan üretir — önce bunu aç, çıplak elle span yazmaya ancak iş mantığındaki özel adımlar için gir. OTel Collector'ı da ortada bir tampon/işlemci olarak kullan; örnekleme, filtreleme, yeniden etiketleme orada merkezi yapılır, uygulama koduna dağılmaz.

**Metrik için:** Prometheus (toplama/sorgulama) + Grafana (görselleştirme) fiili standart. Prometheus çekme (pull) modeliyle çalışır ve RED/USE panolarını burada kurarsın. Kardinaliteyi burada dizginlemek hayati; her yeni etiketten önce "bunun kaç farklı değeri olabilir?" diye sor.

**Trace için:** Jaeger veya Grafana Tempo açık kaynak tarafında yaygın; ticari tarafta Datadog APM, Honeycomb (yüksek kardinalite sorgularında özellikle güçlü). Trace görüntüleyicide her zaman kritik yolu ara, span'leri süreye göre sırala.

**Log için:** Yapısal (JSON) log üret, bir toplayıcıya (Loki, Elasticsearch/OpenSearch, ya da ticari bir çözüm) gönder. Loki'nin güzel yanı log'ları metriklerle aynı etiket modelinde tutması, korelasyonu kolaylaştırması. Log seviyesini (log level) çalışırken değiştirebilmek — üretimde geçici olarak DEBUG'a çıkıp sorunu yakalayıp geri düşmek — çok değerli bir yetenektir; altyapını buna göre kur.

**Korelasyon her şeydir.** Araç seçiminden çok daha önemli olan, üç sinyalin birbirine bağlanabilmesi. Grafana'da bir metrik anomalisinden tek tıkla ilgili trace'e, oradan trace_id ile ilgili log'lara geçebiliyorsan, gözlemlenebilirliğin gerçekten çalışıyor demektir. Bu "exemplar" (metrikteki bir noktadan bir örnek trace'e bağ) mekanizması, dağınık üç aracı tek bir araştırma akışına dönüştürür.

**Klasik debugger ölmedi.** Observability üretim içindir, ama sorunu lokalde yeniden üretebiliyorsan hâlâ en hızlı yol adım adım debugger'dır. İkisini karşı karşıya koyma; farklı ortamların araçlarıdır. Lokal geliştirmede breakpoint, üretimde trace/log/metrik.

**Profiler'ı unutma.** Trace "hangi servis/span yavaş" der ama tek bir fonksiyonun içinde CPU'yu neyin yediğini söylemez. Orada continuous profiling (sürekli profilleme — örn. pprof tarzı, alev grafiği/flame graph çıktısıyla) devreye girer. "Bu servis CPU'ya boğuluyor ama neden" sorusunun cevabı profiler'dadır. Trace makro, profiler mikro seviyedir; ikisi tamamlayıcıdır.

**SLO ve error budget zihniyeti.** Olgun ekip her metriğe alarm kurmaz; kullanıcıya söz verdiği bir SLO (örn. "isteklerin %99.9'u 500 ms altında") tanımlar ve alarmı bunun *tükenme hızına* (burn rate) kurar. Bu, gürültüyü keser ve mühendis enerjisini gerçekten kullanıcıyı etkileyen şeye odaklar. "Neye alarm kurmalı" sorusunun profesyonel cevabı: nedene değil, kullanıcı etkisine.

**Kartopu (cascading failure) okuması.** Dağıtık sistemde bir servis yavaşlayınca, onu çağıranlar bağlantı/thread biriktirir, onlar da yavaşlar, geriye doğru dalga yayılır. Metrikte bunu "aynı anda birçok servisin p99'unun bozulması" olarak görürsün. Acemi her birini ayrı sorun sanıp panikler. Pro trace'te en derindeki, *ilk* yavaşlayan span'i arar — kaynak orasıdır, gerisi domino. Retry fırtınaları (her katmanın yeniden denemesi yükü katlar) bu tabloyu ağırlaştırır; timeout ve retry politikalarını buna göre, exponential backoff ve jitter ile kur.

**Son saha notu — enstrümantasyonu sonradan eklenen bir iş sanma.** En değerli span ve log'lar, kodu yazarken iş mantığını en iyi bildiğin anda konur. "Önce çalıştıralım, gözlemlenebilirliği sonra ekleriz" diyen ekip, tam da gece 3'te lazım olan span'in orada olmadığını fark eder. Gözlemlenebilirlik, test gibi, kodun birinci sınıf bir parçasıdır. Bir olay (incident) sonrası her zaman şu soruyu sor: "Bunu daha hızlı teşhis edebilmek için hangi sinyal eksikti?" ve o sinyali ekle. Sistemin gözlemlenebilirliği, yaşadığın olaylardan öğrenerek olgunlaşır.
