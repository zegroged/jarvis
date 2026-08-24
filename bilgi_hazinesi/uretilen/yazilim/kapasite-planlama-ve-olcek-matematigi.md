# Kapasite Planlama ve Ölçek Matematiği: Back-of-Envelope Estimation, Little's Law ve Kuyruk Teorisi

## Giriş: Neden Bu Konu Sistem Tasarımının Bel Kemiğidir

Bir sistemi "doğru" tasarlamak, soyut bir zarafet arayışı değildir; somut sayılarla sınırlanmış bir mühendislik problemidir. "Bu API kaç QPS (queries per second) kaldırır?", "500 milisaniyelik p99 gecikme hedefi için kaç worker gerekir?", "Bu veritabanı 2 yıl sonra diske sığar mı?" sorularının cevabı sezgiyle değil, hesapla verilir. Kapasite planlama, bir sistemin beklenen yükü, o yükün büyüme eğilimini ve mevcut/planlanan kaynakların bu yükü hangi gecikme ve hata oranıyla karşılayacağını **sayısal olarak** kestirme disiplinidir.

Bu konu genellikle sistem tasarım mülakatlarında "arka zarf hesabı" (back-of-envelope estimation) olarak karşımıza çıkar, ama gerçek hayattaki önemi çok daha büyüktür: kapasite planlaması yanlış yapıldığında ya para israf edilir (aşırı provizyon), ya da sistem üretimde çöker (yetersiz provizyon). Bu makale, bu tahminlerin ardındaki matematiksel iskeleti -- Little's Law ve kuyruk teorisi (queueing theory) -- ve bunların pratikte nasıl kullanıldığını, hangi tuzaklara düşüldüğünü ele alıyor.

## Back-of-Envelope Estimation: Kaba Ama Disiplinli Tahmin

### Tanım ve Amaç

Back-of-envelope estimation, kesin ölçüm verisi olmadan, makul varsayımlardan yola çıkarak bir büyüklüğü (trafik, depolama, bant genişliği, sunucu sayısı) 1-2 basamak doğrulukla tahmin etme tekniğidir. Amaç kesinlik değil, **doğru büyüklük mertebesini (order of magnitude)** yakalamaktır: sistemin 100 sunucu mu yoksa 100.000 sunucu mu gerektirdiğini ayırt edebilmek, 3 sunucu ile 5 sunucu arasındaki farkı bulmaktan daha önemlidir.

### Kök Neden / Çalışma Mantığı

Bu tekniğin işe yaramasının nedeni, gerçek dünya sistemlerinin çoğunun birkaç temel parametreden türetilebilir olmasıdır: kullanıcı sayısı, kullanıcı başına eylem sıklığı, eylem başına veri boyutu, okuma/yazma oranı, tepe/ortalama trafik oranı (peak-to-average ratio). Bu parametreleri zincirleme çarparak QPS, depolama ve bant genişliği gibi büyüklüklere ulaşılır.

Örnek zincir: 100 milyon günlük aktif kullanıcı (DAU) × kullanıcı başına günde 2 gönderi = günde 200 milyon yazma işlemi. Bunu 86.400 saniyeye bölersek ortalama ~2.300 QPS elde ederiz. Ama ortalama yanıltıcıdır -- trafik gün içinde düz dağılmaz, genelde tepe saatlerde ortalamanın 2-10 katına çıkar. Bu yüzden "tepe QPS = ortalama QPS × tepe katsayısı" hesabı yapılır ve kapasite tepe değere göre planlanır, ortalamaya göre değil. Bu tek adım, back-of-envelope hesaplamanın en sık atlanan ve en kritik parçasıdır: ortalamaya göre kapasite planlayan sistemler, tepe saatlerde kaçınılmaz olarak tıkanır.

### Doğru Kullanım ve En İyi Pratikler

- **2'nin kuvvetleriyle ve yuvarlak sayılarla çalış**: 1 KB ≈ 10^3 bayt, 1 MB ≈ 10^6, 1 GB ≈ 10^9 gibi kabaca yuvarlamalar hesabı hızlandırır ve hatayı gizlemez çünkü zaten mertebe hedefleniyor.
- **Varsayımları açıkça yaz**: Her rakamın yanına "varsayım: %20 yazma, %80 okuma" gibi notlar düşülmeli. Bu, hem gözden geçirmeyi kolaylaştırır hem de varsayım yanlış çıktığında hangi adımın revize edileceğini gösterir.
- **Zinciri modüler kur**: Depolama, bant genişliği, QPS, bellek ihtiyacı ayrı ayrı zincirler olarak hesaplanmalı; birini değiştirmek diğerlerini otomatik etkilemeli.
- **Sağlama (sanity check) yap**: Sonuç gerçekçi bir referansla karşılaştırılmalı. "500.000 sunucu mu gerekiyor?" gibi bir sonuç çıkarsa, muhtemelen bir çarpanda hata vardır.

### Yaygın Hatalar ve Tuzaklar

- **Ortalama ile tepe değeri karıştırmak**: Kapasite ortalamaya göre planlanırsa, tepe saatlerde sistem çöker. Bu, en yaygın ve en pahalı hatadır.
- **Büyüme faktörünü unutmak**: Kapasite planlaması an be an değil, gelecek 6-24 ay içindir. Yıllık büyüme oranı (örn. %50 kullanıcı artışı) hesaba katılmazsa, sistem birkaç ay içinde yetersiz kalır.
- **Aşırı hassasiyet illüzyonu**: "1.247.583 QPS gerekiyor" gibi sahte kesinlikte sonuçlar üretmek; gerçekte bu hesabın hata payı kolayca ±%50 olabilir, dolayısıyla "~1.2M QPS" demek daha dürüsttür.
- **Bağımlı kaynakları unutmak**: Sadece uygulama sunucusu değil; veritabanı bağlantı havuzu, önbellek (cache) kapasitesi, ağ bant genişliği, disk IOPS gibi her katmanın kendi darboğazı olabileceği unutulur. Sistemin kapasitesi, en zayıf halkası kadardır.

## Little's Law: Kuyruk Teorisinin Temel Denklemi

### Tanım

Little's Law, kuyruk teorisinin en temel ve en genel sonucudur:

**L = λ × W**

Burada:
- **L**: Sistemdeki ortalama iş/istek sayısı (örneğin aynı anda işlenmekte olan istek sayısı, concurrency).
- **λ (lambda)**: Sisteme birim zamanda giren iş oranı (varış hızı / arrival rate, örneğin QPS).
- **W**: Bir işin sistemde geçirdiği ortalama süre (bekleme + işlenme süresi, yani gecikme/latency).

Bu formülün olağanüstü gücü, sistemin iç işleyişi hakkında **hiçbir varsayım gerektirmemesidir**. Kuyruk disiplini (FIFO, LIFO, öncelikli), servis süresi dağılımı, varış sürecinin dağılımı ne olursa olsun -- sistem kararlı durumdaysa (uzun vadede kuyruk sınırsız büyümüyorsa) bu ilişki her zaman doğrudur. Bu yüzden matematiksel bir teorem düzeyinde güvenilirdir, bir sezgisel kural değildir.

### Kök Neden / Çalışma Mantığı

Sezgisel olarak neden doğru olduğunu şöyle anlayabiliriz: Eğer saniyede 100 istek geliyorsa (λ=100/s) ve her istek sistemde ortalama 2 saniye kalıyorsa (W=2s), o zaman herhangi bir anda sistemde ortalama 200 istek "birikmiş" durumda olmalıdır (L=200), çünkü son 2 saniyede gelen tüm istekler henüz sistemden çıkmamıştır. Bu, bir "banyo küveti" (bathtub) analojisiyle de düşünülebilir: küvete birim zamanda giren su miktarı ile suyun küvette kalma süresinin çarpımı, küvetteki su hacmini verir.

Little's Law'ın kapasite planlamadaki asıl gücü, üç değişkenden ikisini bilirsen üçüncüyü türetebilmesidir:

- **Concurrency'den kapasiteye**: Bir sunucunun aynı anda kaç isteği işleyebildiğini (thread pool boyutu, connection pool boyutu gibi bir L sınırı) biliyorsan ve hedef gecikmeyi (W) biliyorsan, o sunucunun taşıyabileceği maksimum QPS'i (λ) hesaplayabilirsin: λ = L / W.
- **Thread/worker sayısı belirleme**: Hedef λ (beklenen QPS) ve tipik W (servis süresi) biliniyorsa, gereken eşzamanlı worker sayısı L = λ × W ile bulunur. Bu, thread pool ya da connection pool boyutlandırmasının doğrudan matematiksel temelidir.
- **Gecikme artışının erken sinyali**: Sabit bir donanımda L (concurrency, örneğin aktif bağlantı sayısı) aniden artıyorsa ama λ sabitse, W'nin (gecikmenin) arttığı anlamına gelir -- bu, sistemde bir performans bozulmasının erken göstergesidir ve genellikle darboğazın (bottleneck) oluştuğunu haber verir.

### Doğru Kullanım, Tuzaklar, En İyi Pratikler

- **Birimler tutarlı olmalı**: λ istek/saniye ise, W saniye cinsinden olmalı; birim uyuşmazlığı en sık yapılan hesap hatasıdır.
- **Kararlı durum (steady state) varsayımı unutulmamalı**: Little's Law, sistem uzun vadeli dengede (kuyruk sürekli büyümüyor) olduğunda geçerlidir. Ani, geçici trafik patlamalarında (burst) anlık L, λ×W'den sapabilir; formül ortalama/uzun-vadeli davranışı tanımlar, anlık spike'ları değil.
- **"L" neyi kapsıyor dikkatli tanımlanmalı**: L sadece aktif işlenen istekleri mi, yoksa kuyrukta bekleyenleri de mi içeriyor? Bu ayrım karışırsa (örneğin sadece thread pool'daki aktif işleri sayıp kuyrukta bekleyenleri unutmak), kapasite hesabı yanlış çıkar.
- **Pratik kullanım**: Web sunucusu thread pool boyutlandırmasında klasik formül: gerekli thread sayısı ≈ hedef QPS × ortalama istek süresi (saniye). Örneğin 1000 QPS hedefi ve 50ms ortalama yanıt süresi için: 1000 × 0.05 = 50 thread. Bundan az thread ayrılırsa, istekler kuyrukta bekler ve W (dolayısıyla algılanan gecikme) katlanarak artar.

## Kuyruk Teorisi (Queueing Theory): M/M/1 ve Ötesi

### Tanım

Kuyruk teorisi, isteklerin rastgele zamanlarda geldiği ve sınırlı kaynaklarla (sunucu, işlemci, bağlantı) hizmet verildiği sistemlerin davranışını modelleyen matematik dalıdır. Kendall notasyonu ile sınıflandırılır: **A/S/c** biçiminde, A varış sürecinin dağılımı, S servis süresinin dağılımı, c ise sunucu (server) sayısıdır. En temel ve kapasite planlamada en sık kullanılan model **M/M/1**'dir: varışlar Poisson sürecine göre (M = Markovian/memoryless), servis süreleri üstel dağılıma göre (M) rastgele, ve tek bir sunucu (1) var.

### Kök Neden / Çalışma Mantığı: Neden Kuyruklar Doğrusal Değil Patlayarak Büyür

M/M/1 kuyruğunda temel parametre **utilization (kullanım oranı) ρ (rho) = λ / μ**'dür; burada λ varış hızı, μ ise sunucunun servis hızıdır (birim zamanda işleyebildiği iş sayısı). Sistemin kararlı kalması için ρ < 1 olmalıdır (sunucu, gelen işi geldiğinden daha hızlı işleyebilmeli).

M/M/1 modelinin en önemli ve en çok göz ardı edilen sonucu şudur -- ortalama sistemde geçirilen süre:

**W = 1 / (μ − λ) = (1/μ) / (1 − ρ)**

Bu formülün şekli kritiktir: ρ (kullanım oranı) 1'e yaklaştıkça, (1−ρ) sıfıra yaklaşır ve W **sonsuza doğru patlar**. Bu, doğrusal değil **hiperbolik** bir ilişkidir. Somut sayılarla: ρ=%50'de bekleme süresi taban seviyenin 2 katıyken, ρ=%90'da 10 katı, ρ=%95'te 20 katı, ρ=%99'da 100 katıdır. Yani sunucuyu %70'ten %90 kullanıma çıkarmak masum bir optimizasyon gibi görünür ama gecikmeyi katlayarak artırır.

Bunun kök nedeni sezgiseldir: Rastgele (stokastik) varışlarda, kısa süreliğine varış hızının ortalamanın üzerine çıktığı anlar kaçınılmaz olarak olur (varyans / burstiness). Sunucu zaten yüksek kullanımdaysa (ρ yüksek), bu kısa patlamaları absorbe edecek "boşluk" (slack) kalmamıştır, dolayısıyla kuyruk hızla birikir ve boşalması uzun sürer. Düşük ρ'de ise sistemde bolca boş kapasite olduğundan patlamalar hemen emilir.

Bu, kapasite planlamanın en temel ve en yanlış anlaşılan ilkesidir: **yüksek kaynak kullanımı = verimlilik değil, gecikme riski demektir**. Bir sistemi CPU'yu %95 dolu tutacak şekilde tasarlamak "verimli" görünür ama gerçekte gecikmeye aşırı duyarlı, kırılgan bir sistem yaratır.

### M/M/c ve Çoklu Sunucu Modelleri

Gerçek sistemler genellikle tek sunucu değil, sunucu havuzlarıdır (M/M/c, c sunucu sayısı). Buradaki önemli kavrayış: **birden fazla küçük kuyruk yerine tek bir paylaşılan kuyruk (ortak havuz) her zaman daha iyi ortalama bekleme süresi verir**, aynı toplam kapasitede. Bu, çağrı merkezlerinde "her müşteri temsilcisinin kendi kuyruğu" yerine "tek ortak kuyruk + boşta kalan ilk temsilci alır" modelinin neden tercih edildiğinin matematiksel temelidir; yazılımda ise bu, load balancer arkasında paylaşılan bir istek kuyruğunun, her worker'a sabit ayrılmış kuyruklardan neden daha verimli olduğunu açıklar.

### Doğru Kullanım, Tuzaklar, En İyi Pratikler

- **Güvenli utilization hedefi belirle**: Pratikte çoğu sistem ρ'yi %70-80 aralığında tutmayı hedefler; bu, hem kaynak israfını önler hem de gecikme patlamasından güvenli mesafe bırakır. %90 üzeri hedefler, "normal" görünen trafik varyansında bile ciddi gecikme sıçramalarına yol açar.
- **Servis süresi dağılımının şekli önemlidir**: M/M/1 varsayımı (üstel dağılım) her zaman gerçekçi değildir; gerçek servis süreleri genelde daha değişken (yüksek varyans, "heavy-tailed") olabilir, bu da kuyrukların M/M/1'in öngördüğünden bile daha kötü davranmasına yol açar (Pollaczek-Khinchine formülü gibi M/G/1 modelleri bu değişkenliği hesaba katar).
- **Kuyruklanma her katmanda birikir**: Bir mikroservis zincirinde her aşama kendi kuyruğuna sahiptir; her aşamadaki küçük gecikme birikimleri, uçtan uca gecikmede (tail latency) katlanarak büyür. Bu yüzden p50 değil p99/p999 gecikmelere odaklanmak gerekir.
- **Kuyruk teorisi kapasite planlamasında "ne zaman ek sunucu eklemeli" sorusuna nicel cevap verir**: Hedef W (gecikme SLA'sı) ve beklenen λ biliniyorsa, gereken μ (ve dolayısıyla sunucu/kaynak sayısı) formülden geriye doğru hesaplanabilir.

### Yaygın Hatalar

- **Ortalama utilization'a bakıp "kapasitemiz yeterli" demek**: Ortalama ρ=%60 olsa bile, trafiğin dağılımı düzensizse (bursty), kısa süreli tepe noktalarında ρ 1'e yaklaşabilir ve kullanıcılar gecikme yaşar. Ortalamalar, kuyruk davranışının doğrusal olmayan doğasını gizler.
- **Kuyruk teorisini yalnızca CPU'ya uygulayıp diğer kaynakları (disk I/O, ağ, veritabanı bağlantı havuzu, kilitler/locks) göz ardı etmek**: Her kaynak kendi M/M/c sistemidir ve en dar boğaz olan (bottleneck resource) genel sistem gecikmesini belirler.
- **"Auto-scaling her şeyi çözer" yanılgısı**: Otomatik ölçeklendirme (autoscaling) tepkisi gecikmeli çalışır (yeni sunucu ayağa kaldırma, ısınma süresi); ani ve keskin trafik patlamalarında, ρ zaten 1'e dayanmışken autoscaling devreye girene kadar geçen sürede kullanıcılar zaten gecikme/hata yaşamış olur. Bu yüzden kapasite planlaması, sadece reaktif ölçeklendirmeye değil, öngörülü (proaktif) tamponlamaya (buffer/headroom) dayanmalıdır.

## Bu Kavramların Birlikte Kullanımı: Uçtan Uca Bir Akıl Yürütme Örneği

Kapasite planlamasının gerçek gücü, bu üç aracın birlikte kullanılmasında ortaya çıkar:

1. **Back-of-envelope** ile beklenen tepe QPS'i (λ) tahmin edilir (kullanıcı sayısı, davranış, büyüme, tepe katsayısı üzerinden).
2. **Little's Law** ile bu λ'yı karşılamak için gereken concurrency (L) ve dolayısıyla worker/thread/connection sayısı hesaplanır, hedef gecikme (W) sabitlenerek.
3. **Kuyruk teorisi (M/M/c)** ile, seçilen sunucu sayısının verdiği ρ (kullanım oranı) hesaplanır ve bu ρ'nin güvenli aralıkta (örn. <%80) kalıp kalmadığı, dolayısıyla gecikme SLA'sının tutup tutmayacağı doğrulanır.

Bu üçü sırasıyla uygulanmadan yapılan kapasite kararları genellikle iki uçtan birine düşer: gereğinden fazla provizyon (maliyet israfı) ya da gereğinden az provizyon (üretimde gecikme patlaması ve kesinti). Doğru yaklaşım, her zaman "beklenen ortalama yük" değil, "tepe yük altında kabul edilebilir gecikmeyi koruyacak minimum kapasite + güvenlik payı" sorusuna nicel bir cevap aramaktır.

## Sonuç

Kapasite planlama, tahmin sanatı ile matematiksel titizliğin kesişimindedir. Back-of-envelope estimation doğru büyüklük mertebesini bulmayı öğretir; Little's Law, bir sistemin üç temel değişkeni (eşzamanlılık, varış hızı, gecikme) arasındaki değişmez ilişkiyi verir; kuyruk teorisi ise neden yüksek kaynak kullanımının doğrusal değil patlayarak artan bir gecikme riski taşıdığını açıklar. Bu üçünü birlikte kullanabilen bir mühendis, "kaç sunucuya ihtiyacımız var" sorusuna sezgiyle değil, savunulabilir sayılarla cevap verebilir -- ve bu, hem sistem tasarım mülakatlarının hem de gerçek üretim sistemlerinin güvenilirliğinin temelidir.
