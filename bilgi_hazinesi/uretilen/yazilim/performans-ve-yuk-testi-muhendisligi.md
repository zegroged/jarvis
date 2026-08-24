# Performans ve Yük Testi Mühendisliği

## Giriş: Neden Ayrı Bir Mühendislik Disiplini?

Fonksiyonel testler bir sistemin "doğru şeyi yapıp yapmadığını" sorar; performans testleri ise "bunu ne kadar hızlı, ne kadar çok kullanıcıyla ve ne kadar uzun süre yapabildiğini" sorar. Bu iki soru arasındaki fark, üretim ortamlarında çöken sistemlerin büyük kısmının kaynağıdır. Bir uygulama tüm birim testlerini geçebilir, kod incelemesinden temiz çıkabilir ve yine de kara cuma trafiğinde ilk on dakikada çökebilir.

Performans testi mühendisliği; **load testing** (yük testi), **stress testing** (stres testi), **soak/endurance testing** (dayanıklılık testi), **spike testing** (ani yük testi) ve **capacity planning** (kapasite planlama) gibi ayrı disiplinleri kapsayan, kendi araç setine, metodolojisine ve tuzaklarına sahip bir mühendislik pratiğidir. Genel test stratejileri bu alanı çoğu zaman "ayrıca performans da bakarız" düzeyinde geçiştirir; oysa doğru yapıldığında bu, sistematik ölçüm, hipotez kurma ve darboğaz avı gerektiren bilimsel bir süreçtir.

## Temel Kavramlar ve Metrikler

Herhangi bir performans testi konuşmasının önce ortak bir metrik diline oturması gerekir. Aksi halde "sistem yavaş" gibi ölçülemeyen ifadelerle kaybolunur.

### Latency (Gecikme) ve Response Time (Yanıt Süresi)

**Latency**, bir isteğin sisteme ulaşması ile ilk yanıt baytının dönmesi arasındaki süredir. **Response time** genellikle isteğin tamamının işlenip yanıtın tamamının döndüğü süreyi kapsar. Kritik nokta şudur: **ortalama (average/mean) yanıt süresi neredeyse her zaman yanıltıcıdır.** Ortalama, birkaç çok yavaş isteğin (kuyruk etkisi) altında binlerce hızlı isteğin gizlenmesine izin verir.

Bu yüzden performans mühendisleri **percentile** (yüzdelik dilim) düşünür:

- **p50 (medyan):** İsteklerin yarısı bu sürenin altında.
- **p95:** İsteklerin %95'i bu sürenin altında; %5'i daha yavaş.
- **p99, p99.9:** Kuyruğun ucundaki en kötü deneyimler.

p99 özellikle önemlidir çünkü yüksek trafikte bir kullanıcı tek bir sayfa için onlarca istek yapar; %1'lik yavaş isteklerin en az birine denk gelme olasılığı çok yükselir. Amazon ve Google gibi kuruluşların "tail latency" (kuyruk gecikmesi) üzerine bu kadar yoğunlaşmasının nedeni budur.

### Throughput (İş Hacmi)

**Throughput**, birim zamanda işlenen istek sayısıdır; genellikle **RPS** (requests per second) veya **TPS** (transactions per second) olarak ölçülür. Latency ve throughput birbirinden bağımsız değildir: Sistem doygunluğa yaklaştıkça, throughput'u artırma çabası latency'yi patlatır. Bu ilişkinin matematiksel temeli **Little's Law** ile ifade edilir:

> Ortalama eşzamanlı istek sayısı (L) = Varış hızı (λ, throughput) × Ortalama sistemde kalış süresi (W, latency)

Yani `L = λ × W`. Bu yasa neden önemli? Çünkü kapasite planlamanın çekirdeğidir: Eğer sistemde aynı anda taşıyabileceğiniz eşzamanlı istek sayısı sınırlıysa (örneğin bir bağlantı havuzu 100 bağlantıyla sınırlıysa), throughput ve latency birlikte hareket etmek zorundadır. Bir tanesini iyileştirmek diğerini bozabilir.

### Concurrency ve Utilization

**Concurrency** (eşzamanlılık) aynı anda işlenen istek sayısıdır. **Utilization** (kaynak kullanımı) ise CPU, bellek, disk I/O, ağ bant genişliği gibi kaynakların doluluk oranıdır. Buradaki en kritik ve en çok ihmal edilen ilke **Universal Scalability Law** ve kuyruk teorisidir: Bir kaynak %70-80 kullanım seviyesini aştıkça, kuyruk uzunluğu doğrusal değil **üstel** olarak büyür. Bu yüzden "CPU %100 olana kadar sorun yok" düşüncesi tehlikelidir; sistem çoğu zaman %85 CPU'da kabul edilemez latency'ye ulaşır.

## Test Türleri: Her Biri Farklı Bir Soruyu Yanıtlar

### Load Testing (Yük Testi)

**Amaç:** Beklenen üretim yükü altında sistemin metriklerinin (latency, throughput, hata oranı) kabul edilebilir sınırlar içinde kaldığını doğrulamak.

Load testing bir "geçti/kaldı" sınavı gibidir. Beklenen zirve yükü belirlersiniz (örneğin 5.000 eşzamanlı kullanıcı, 2.000 RPS), yükü kademeli olarak (**ramp-up**) o seviyeye çıkarır, bir süre orada tutar (**steady state**) ve **SLO** (Service Level Objective) hedeflerinizi karşılayıp karşılamadığınıza bakarsınız. Örnek bir SLO: "p99 yanıt süresi 2.000 RPS altında 300 ms'nin altında kalmalı, hata oranı %0,1'i geçmemeli."

### Stress Testing (Stres Testi)

**Amaç:** Sistemi kırılma noktasına kadar zorlayarak **kapasite tavanını** ve **çökme davranışını** bulmak.

Stress testi kasıtlı olarak sistemi beklenen yükün ötesine iter. Buradaki asıl değer, kırılma anını değil, **kırılma biçimini** gözlemlemektir. İyi tasarlanmış bir sistem yük arttıkça zarifçe bozulur (**graceful degradation**): fazla istekleri reddeder, kuyruğa alır veya sınırlar. Kötü tasarlanmış bir sistem **cascading failure** (zincirleme çökme) yaşar; bir bileşenin çökmesi diğerlerini de aşağı çeker. Stres testi, sisteminizin hangi kategoride olduğunu üretim öncesi öğrenmenin tek yoludur.

Kritik gözlem: Sistem çöktükten sonra yükü geri çektiğinizde **kendini toparlayabiliyor mu?** Birçok sistem çökme sonrası "ölüm sarmalına" (death spiral) girer; retry fırtınaları, dolan kuyruklar ve tükenmiş bağlantı havuzları nedeniyle yük normale dönse bile ayağa kalkamaz.

### Soak / Endurance Testing (Dayanıklılık Testi)

**Amaç:** Orta düzey bir yükü **uzun süre** (saatler, hatta günler) uygulayarak zamanla ortaya çıkan sorunları yakalamak.

Bu, en çok ihmal edilen test türüdür çünkü sabır ister. Soak testi, kısa testlerde asla görünmeyen sınıf sorunları ortaya çıkarır:

- **Memory leak** (bellek sızıntısı): Her istekte serbest bırakılmayan küçük bellek parçaları saatler sonra sistemi OOM (Out of Memory) ile çökertir.
- **Connection leak:** Kapatılmayan veritabanı bağlantıları havuzu yavaşça tüketir.
- **Disk dolması:** Log rotasyonu olmayan bir sistemde diskin dolması.
- **Cache degradation:** Önbelleğin zamanla verimsizleşmesi veya sınırsız büyümesi.

Bir sistem 30 dakikalık load testini mükemmel geçip 8 saatlik soak testinde çökebilir. Bu tür kusurlar üretimde ancak birkaç gün sonra ortaya çıktığından, tespiti çok pahalıdır.

### Spike Testing (Ani Yük Testi)

**Amaç:** Yükün aniden ve keskin biçimde artmasına sistemin tepkisini ölçmek.

Gerçek dünyada yük nadiren yumuşak bir eğriyle gelir. Bir ürünün televizyonda gösterilmesi, viral bir tweet veya bir bildirim gönderimi saniyeler içinde on kat trafik yaratabilir. Spike testi, sistemin bu ani sıçramada **auto-scaling** mekanizmalarının yeterince hızlı devreye girip girmediğini test eder. Çoğu auto-scaling dakikalar mertebesinde tepki verir; oysa spike saniyeler içinde gerçekleşir. Bu boşlukta sistemi ayakta tutan şey, ölçekleme değil, **load shedding** (yük atma) ve **rate limiting** gibi savunma mekanizmalarıdır.

### Diğer Türler

- **Capacity testing:** Belirli bir SLO'yu koruyarak taşıyabileceğiniz maksimum yükü bulmak.
- **Configuration testing:** Farklı yapılandırmaların (thread havuzu boyutu, JVM heap ayarları) performans etkisini karşılaştırmak.

## Kök Neden Analizi: Darboğaz (Bottleneck) Avı

Performans mühendisliğinin kalbi, bir sayı üretmek değil, **neden o sayı olduğunu** anlamaktır. Her sistemin bir **darboğazı** vardır; ölçekleme çabası, o an aktif olan darboğazı bulup gidermekten ibarettir. Darboğaz giderildiğinde başka bir darboğaz ortaya çıkar; bu, sonsuz bir kovalamaca değil, bilinçli bir mühendislik döngüsüdür.

Tipik darboğaz katmanları:

1. **CPU-bound:** İşlemci hesaplama ile doludur (şifreleme, serileştirme, sıkıştırma).
2. **Memory-bound:** GC (garbage collection) duraklamaları veya bellek bant genişliği sınırı.
3. **I/O-bound:** Disk veya ağ beklemesi; en yaygın darboğaz.
4. **Lock contention:** Thread'ler paylaşılan bir kilit için birbirini beklemekte.
5. **Database:** Neredeyse her ölçekli sistemin nihai darboğazı. Yavaş sorgular, eksik index'ler, bağlantı havuzu tükenmesi, tablo kilitleri.
6. **Downstream dependency:** Üçüncü taraf bir API veya mikroservisin yavaşlaması.

Darboğazı bulmanın yöntemi **USE metodudur** (Utilization, Saturation, Errors): Her kaynak için kullanım oranına, doygunluğa (kuyruk uzunluğu) ve hata sayısına bakılır. Yüksek doygunluk gösteren ilk kaynak, muhtemel darboğazdır. Buna karşılık **RED metodu** (Rate, Errors, Duration) servis düzeyinde gözlem için kullanılır.

## Doğru Kullanım ve Yaygın Tuzaklar

### Tuzak 1: Gerçekçi Olmayan İş Yükü Modeli

En sık ve en yıkıcı hata budur. Test, gerçek kullanıcı davranışını taklit etmiyorsa, ürettiği sayılar sahtedir. Yaygın alt tuzaklar:

- **Tek endpoint bombardımanı:** Tüm testin `/health` gibi tek ve hafif bir uç noktaya atılması. Gerçek trafik farklı ağırlıkta yüzlerce endpoint'e dağılır.
- **Cache-friendly veri:** Aynı kullanıcı ID'sini veya aynı ürünü tekrar tekrar istemek, önbelleği yapay olarak ısıtır ve gerçek üretimden çok daha iyi sonuç verir. Test verisi **yüksek kardinaliteli** ve gerçekçi dağılımda olmalıdır.
- **Think time eksikliği:** Gerçek kullanıcılar istekler arasında düşünür, okur, bekler. Bu **think time** modellenmezse, çok az sanal kullanıcı ile gerçekçi olmayan yoğunlukta yük üretilir.

### Tuzak 2: Coordinated Omission (Eşgüdümlü Atlama)

Bu, latency ölçümündeki en sinsi hatadır ve çoğu naif yük test aracı bundan muzdariptir. Sorun şudur: Araç bir istek gönderir, yanıtı bekler, **sonra** bir sonraki isteği gönderir. Sistem takıldığında (örneğin 5 saniyelik bir duraklama), araç o sırada göndermesi gereken yüzlerce isteği hiç göndermez; sadece bekler. Sonuç: En kötü latency dönemleri örnekleme dışı kalır ve ölçülen p99 gerçeğin çok altında görünür.

Doğru araçlar, isteklerin **olması gereken zamanlarını** (schedule) sabitleyip, gecikmeyi bu ideal zamana göre ölçer. Bu kavramı popülerleştiren Gil Tene'nin `wrk2` ve `HdrHistogram` gibi araçları bu düzeltmeyi içerir. Bir yük testi aracını seçerken coordinated omission'ı ele alıp almadığını sormak, ciddiyetinin turnusol testidir.

### Tuzak 3: Yük Üreticisinin Kendisinin Darboğaz Olması

Sanal kullanıcıları üreten makine (**load generator**) de bir bilgisayardır ve kendi sınırları vardır. Eğer yük üreticinizin CPU'su, ağ bağlantısı veya efemeral port havuzu tükeniyorsa, ölçtüğünüz "yavaşlık" test edilen sistemin değil, test aracının yavaşlığıdır. Bu yüzden ciddi testlerde yük **birden fazla dağıtık üretici** ile oluşturulur ve üreticilerin kendi metrikleri de izlenir.

### Tuzak 4: Üretimden Farklı Ortamda Test

Yarı boyutlu bir staging ortamında yapılan testin sonuçları üretime **doğrusal ölçeklenmez.** Veritabanındaki veri hacmi, önbellek boyutları, ağ topolojisi, komşu servislerin varlığı sonuçları kökten değiştirir. İdeali, üretimle özdeş bir ortam ya da dikkatli tasarlanmış **production testing** (canlıda test) yaklaşımlarıdır: **shadow traffic** (gerçek trafiğin kopyasını test sistemine yönlendirme) veya **canary** dağıtımlar.

### Tuzak 5: Isınmayı (Warm-up) Göz Ardı Etmek

JIT derleme (JVM, .NET), önbellek doldurma, bağlantı havuzu kurulumu ve OS dosya önbelleği nedeniyle sistemler ilk saniyelerde yavaştır. Bu ısınma dönemi ölçüme dahil edilirse sonuçlar bozulur. Ölçüm, sistem **steady state**'e ulaştıktan sonra alınmalıdır.

## Kapasite Planlama

Kapasite planlama, performans testi verilerini **iş kararlarına** çeviren köprüdür. Temel soru şudur: "Önümüzdeki çeyrekte beklenen trafik büyümesini, SLO'larımı bozmadan, hangi kaynak miktarıyla karşılayabilirim?"

Süreç genellikle şöyle işler:

1. **Baseline ölçümü:** Tek bir birim (instance/pod) belirli bir SLO altında kaç RPS taşıyabilir? Buna **per-unit capacity** denir.
2. **Headroom belirleme:** Asla %100 kullanımda çalışılmaz. Genellikle **%50-70 hedef kullanım** bırakılır; bu pay, trafik dalgalanmaları, dağıtım anları ve bir instance'ın çökmesi durumuna karşı yastıktır (**N+1 redundancy**).
3. **Talep tahmini:** Geçmiş büyüme, mevsimsellik (kara cuma, dönem sonları) ve pazarlama kampanyaları hesaba katılır.
4. **Ölçekleme hesabı:** Gereken instance sayısı = (Tahmini zirve RPS) / (per-unit kapasite × hedef kullanım oranı).

Bu hesabın gizli tehlikesi, **doğrusal ölçeklenebilirlik varsayımıdır.** Universal Scalability Law bize bir sistemin sonsuza kadar doğrusal ölçeklenmediğini söyler: Paylaşılan kaynaklar (veritabanı, kilitler, koordinasyon maliyeti) yüzünden 10 instance genellikle 1 instance'ın 10 katı değil, belki 7-8 katı kapasite verir. Ölçek büyüdükçe bu **verim kaybı** artar; hatta bir noktadan sonra instance eklemek koordinasyon maliyeti yüzünden toplam kapasiteyi **düşürebilir**.

## Güvenlik Perspektifi: Yük Testi ile DoS'un İnce Çizgisi

Performans testinin savunma tarafı açısından önemli bir kavramsal örtüşme vardır: Bir yük testi ile bir **Denial of Service** (DoS) saldırısı, mekanik olarak benzer şeyler yapar; ikisi de sistemi çok sayıda istekle doldurur. Fark **niyet ve kontroldedir**: Yük testi, kendi sisteminizde, kontrollü, izinli ve gözlemlenen bir egzersizdir.

Bu benzerlik savunma açısından öğreticidir. Stres testi sırasında sisteminizin çökme biçimini incelemek, aslında bir saldırganın sizi nasıl devireceğini önceden öğrenmektir. Bu yüzden **savunma mekanizmalarınızı** yük testiyle doğrulamalısınız:

- **Rate limiting:** İstek başına/kullanıcı başına/IP başına hız sınırlarının gerçekten devreye girip girmediği.
- **Load shedding:** Sistem doygunlaştığında düşük öncelikli istekleri reddedip kritik olanları koruyabilme.
- **Circuit breaker:** Yavaşlayan bir alt bağımlılığa yapılan çağrıların kesilip zincirleme çökmenin önlenmesi.
- **Backpressure:** Kuyrukların sınırsız büyümesini engelleyip yukarı doğru "yavaşla" sinyali gönderme.
- **Timeout ve retry politikaları:** Retry fırtınalarının (**retry storm**) sistemi kendi kendine devirmesini önlemek için `exponential backoff` ve `jitter` kullanımı.

Tespit tarafında, üretim trafiğinizin normal performans profilini (baseline) yük testleriyle bilmek, bir anomali algılama sistemine temel oluşturur. Ani p99 sıçraması, throughput düşerken artan hata oranı gibi imzalar, hem gerçek bir saldırının hem de kapasite tükenmesinin erken işaretleridir.

**Önemli etik ve yasal not:** Yük/stres testi yalnızca sahibi olduğunuz veya açık yazılı izniniz olan sistemlerde yapılır. Üçüncü tarafların (bulut sağlayıcılar dahil) çoğu, yük testi için önceden bildirim/onay gerektirir; izinsiz yüksek yük üretmek yasal olarak bir saldırıdan ayırt edilemeyebilir.

## Yaygın Hatalar Özeti

- **Sadece ortalamaya bakmak:** Percentile'ler olmadan latency'nin gerçeğini göremezsiniz.
- **Coordinated omission'ı görmezden gelmek:** p99'unuzun yalan söylemesine izin vermek.
- **Gerçekçi olmayan iş yükü:** Tek endpoint, sıcak önbellek, think time yokluğu.
- **Yük üreticisini izlememek:** Kendi test aracınızı darboğaz yapıp sisteme fatura kesmek.
- **Isınma dönemini ölçüme katmak:** Steady state'e ulaşmadan sonuç almak.
- **Soak testini atlamak:** Bellek/bağlantı sızıntılarını üretimde keşfetmek.
- **Doğrusal ölçekleme varsaymak:** Kapasite planında koordinasyon maliyetini yok saymak.
- **Çökme sonrası toparlanmayı test etmemek:** Sistemin ölüm sarmalına girip giremediğini bilmemek.
- **Tek çalıştırmaya güvenmek:** Sonuçların istatistiksel gürültü içerdiğini unutup tek testin sonucunu kesin doğru saymak; tekrarlı ölçüm ve tutarlılık kontrolü şarttır.

## Sonuç

Performans ve yük testi mühendisliği, bir sisteme "hızlı mı?" diye soran naif bir bakıştan çok daha derindir. Doğru metrik dilini (percentile, throughput, utilization) konuşmayı, doğru test türünü doğru soruya eşlemeyi (load/stress/soak/spike), coordinated omission gibi ölçüm tuzaklarından kaçınmayı, darboğazı sistematik biçimde avlamayı ve tüm bunları kapasite planlama ile iş kararlarına bağlamayı gerektirir. En değerli çıktısı bir sayı değil, **sisteminizin baskı altında nasıl davrandığına dair mühendislik güvenidir**: Ne zaman, nasıl ve niçin bozulacağını üretim öncesi bilmek. Bu bilgi, hem gerçek trafik zirvelerinde hem de kötü niyetli yük karşısında bir sistemin ayakta kalıp kalmayacağını belirler.
