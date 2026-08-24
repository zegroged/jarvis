# Ölçeklenebilirlik İlkeleri

## Tanım: Ölçeklenebilirlik Nedir, Ne Değildir?

Ölçeklenebilirlik (scalability), bir sistemin artan yüke (daha fazla kullanıcı, daha fazla istek, daha fazla veri) kaynak ekleyerek orantılı biçimde yanıt verebilme kabiliyetidir. Buradaki kritik sözcük "orantılı"dır: Kaynakları iki katına çıkardığınızda kapasiteniz de kabaca iki katına çıkıyorsa sistem iyi ölçekleniyor demektir. Eğer kaynağı iki katına çıkardığınızda kapasite yalnızca yüzde otuz artıyorsa, sisteminizde ölçeklenmeyi sınırlayan bir şey vardır.

Ölçeklenebilirliği performansla karıştırmamak gerekir. Performans, tek bir isteğin ne kadar hızlı yanıtlandığıyla (latency) ilgilenir. Ölçeklenebilirlik ise sistemin, performansını kabul edilebilir sınırlar içinde tutarak ne kadar çok işi aynı anda yapabildiğiyle (throughput) ilgilenir. Çok hızlı ama tek makinede tıkanan bir sistem yüksek performanslı olabilir fakat ölçeklenemez. Tersine, tek istek yavaş olsa da yüzlerce makineye dağılabilen bir sistem ölçeklenebilir olabilir. İyi mimari her ikisini de dengeler.

Ölçeklenebilirlik ayrıca "sonsuz kapasite" vaadi değildir. Her sistemin bir yerde tıkandığı bir nokta vardır. İyi bir mimarın işi, bu tıkanma noktasını yükün çok ötesine itmek ve tıkandığında sistemin çökmek yerine zarafetle (graceful degradation) yavaşlamasını sağlamaktır.

## Kök Neden: Neden Ölçeklenebilirlik Zor Bir Problem?

Ölçeklenebilirliğin doğası gereği zor olmasının temelinde iki fiziksel ve matematiksel gerçek yatar: paylaşılan durum (shared state) ve koordinasyon maliyeti.

Tek bir makinede çalışan bir program, tüm verisine aynı bellek üzerinden anında erişir. İki iş parçacığının aynı veriyi güncellemesi bir kilit (lock) ile hallolur. Ancak yükü birden çok makineye dağıttığınızda, o veriyi paylaşmak artık ağ üzerinden konuşmayı gerektirir. Ağ ise yavaştır, güvenilmezdir ve gecikmelidir. Bu yüzden dağıtık sistemlerde asıl düşman, işin kendisi değil, makineler arasındaki koordinasyondur.

Bu durumu matematiksel olarak açıklayan iki temel yasa vardır:

**Amdahl Yasası (Amdahl's Law):** Bir işin paralelleştirilemeyen (seri) bir kısmı varsa, ne kadar çok işlemci eklerseniz ekleyin toplam hızlanma bu seri kısımla sınırlıdır. Diyelim ki işinizin yüzde beşi seri (örneğin tek bir merkezi sıraya yazma). O zaman sonsuz sayıda makine ekleseniz bile en fazla yirmi kat hızlanma elde edersiniz. Bu, "neden makine ekledikçe kazanç azalıyor" sorusunun cevabıdır: Seri kalan kısım her zaman tavan koyar.

**Universal Scalability Law (USL):** Amdahl'ın bir adım ötesi. USL, makine sayısı arttıkça yalnızca seri kısmın değil, makineler arası tutarlılık koordinasyonunun (crosstalk / coherency) da maliyet yarattığını söyler. Öyle bir nokta gelir ki, yeni bir makine eklemek toplam kapasiteyi artırmak yerine düşürür, çünkü o makinenin diğerleriyle senkron kalma maliyeti getirdiği faydayı aşar. Gerçek dünyada "sunucu ekledik ama sistem yavaşladı" durumunun teorik açıklaması budur.

Bu yasaların pratik dersi nettir: Ölçeklenebilirliğin sırrı makine eklemek değil, koordinasyon ve paylaşılan durumu azaltmaktır. İyi mimarinin tamamı bu tek cümlenin etrafında döner.

## Dikey ve Yatay Ölçekleme

### Dikey Ölçekleme (Vertical Scaling / Scale Up)

Dikey ölçekleme, mevcut makineyi güçlendirmektir: Daha fazla CPU çekirdeği, daha fazla RAM, daha hızlı disk (NVMe), daha büyük bir sunucu. Zihinsel modeli basittir; tek bir güçlü bilgisayarınız vardır ve onu büyütürsünüz.

Dikey ölçeklemenin en büyük avantajı basitliğidir. Uygulama kodunuzda hiçbir şey değişmez. Paylaşılan durum, koordinasyon, ağ gecikmesi gibi dağıtık sistem sorunlarının hiçbiriyle uğraşmazsınız çünkü hâlâ tek makinedesiniz. Bir SQL veritabanının erken dönemlerinde en pratik çözüm çoğu zaman budur; "makineyi büyüt" der ve problemi bir süreliğine ertelersiniz.

Dezavantajları ise iki türlüdür. Birincisi fiziksel tavan: En büyük sunucu bile sonludur, sınırsız büyüyemezsiniz. İkincisi ekonomik: Donanım gücü lineer artarken maliyet üstel artar. İki kat güçlü bir makine iki kattan çok daha pahalıdır. Üstelik dikey ölçekleme tek arıza noktası (single point of failure) sorununu çözmez; o güçlü makine çökerse tüm sisteminiz çöker.

### Yatay Ölçekleme (Horizontal Scaling / Scale Out)

Yatay ölçekleme, tek bir güçlü makine yerine çok sayıda sıradan makineyi bir araya getirmektir. Yük, bir yük dengeleyici (load balancer) aracılığıyla bu makinelere dağıtılır. Zihinsel modeli bir sürüdür: Tek bir dev at yerine yüz tane midilli.

Yatay ölçeklemenin gücü, teorik olarak sınırsız oluşudur. Tavan yoktur; yük arttıkça makine eklersiniz. Ayrıca doğal olarak dayanıklıdır (fault tolerant): Bir makine çökerse yük dengeleyici onu devreden çıkarır, diğerleri işe devam eder. Bulut mimarisinin ve modern web ölçeğinin temeli budur.

Bedeli ise karmaşıklıktır. Artık paylaşılan durumla, ağ gecikmesiyle, tutarlılık problemleriyle, servis keşfiyle (service discovery) ve dağıtık hata ayıklamayla uğraşmak zorundasınız. Yukarıda bahsedilen Amdahl ve USL yasaları tam da burada devreye girer.

### Ne Zaman Hangisi?

Pratik kural şudur: Önce dikey ölçekle, gerektiğinde yatay ölçekle. Dikey ölçekleme size zaman kazandırır ve karmaşıklığı erteler; erken optimizasyon tuzağına düşmeden önce çoğu sistem için tek bir güçlü makine uzun süre yeter. Ancak sistemi baştan yatay ölçeklemeye *hazır* tasarlamak (yani stateless yapmak) ayrı bir konudur; buna hazır olmak bedavaya yakındır, sonradan geçmek pahalıdır. Doğru strateji genellikle "dikey çalış, ama yatay ölçeklenebilir tasarla"dır.

## Stateless Mimari: Yatay Ölçeklemenin Kalbi

### Tanım ve Çalışma Mantığı

Stateless (durumsuz) bir servis, iki ardışık isteği birbirinden bağımsız işleyen servistir. Sunucu, önceki istekten hiçbir şey "hatırlamaz"; bir isteği yanıtlamak için gereken tüm bilgi ya isteğin kendisinde gelir ya da paylaşılan harici bir depodan (veritabanı, cache, token) okunur.

Bunun neden yatay ölçeklemenin kalbi olduğunu anlamak kritik. Bir yük dengeleyici gelen istekleri makinelere dağıtırken, herhangi bir isteği herhangi bir makineye gönderebilmelidir. Eğer sunucu A kullanıcının oturum bilgisini kendi belleğinde tutuyorsa, o kullanıcının sonraki isteği sunucu B'ye giderse sunucu B onu tanımaz; kullanıcı aniden çıkış yapmış gibi olur. İşte bu yüzden bellekte durum tutan (stateful) sunucular yatay ölçeklenemez veya "yapışkan oturum" (sticky session) gibi kırılgan hilelere muhtaç kalır.

Stateless mimaride ise makineler birbirinin yerine geçebilir (interchangeable). İstediğiniz makineyi ekleyip çıkarabilir, çökeni atabilir, yenisini anında devreye alabilirsiniz. Bu, hem ölçeklenmenin hem de dayanıklılığın önkoşuludur.

### Durum Nereye Gider?

"Stateless" durumun yok olduğu anlamına gelmez; durum kaçınılmazdır. Anlamı, durumun *uygulama sunucusundan çıkarılıp* paylaşılan ve kasıtlı olarak yönetilen bir katmana taşınmasıdır:

- **Oturum durumu:** Sunucu belleği yerine harici bir cache'e (örneğin Redis) veya istemcide tutulan imzalı bir token'a (örneğin JWT) taşınır.
- **Kalıcı veri:** Zaten veritabanındadır, orada kalır.
- **Yüklenen dosyalar:** Sunucunun yerel diski yerine ortak bir nesne deposuna (object storage) taşınır. Yerel diske yazmak, stateless mimariyi bozan en sinsi hatalardan biridir.

Buradaki felsefe şudur: Durumu ortadan kaldıramazsınız, ama onu tek bir yerde toplayıp yönetebilirsiniz. Uygulama sunucularınız aptal ve değiştirilebilir; durum ise az sayıda, özenle ölçeklenen özel sistemde (veritabanı, cache) yaşar.

### Somut Örnek

Bir e-ticaret sitesi düşünün. Kullanıcı sepetine ürün ekliyor. Stateful yaklaşımda sepet, isteği karşılayan sunucunun belleğinde tutulur; kullanıcı bir sonraki sayfada farklı bir sunucuya düşerse sepeti boş görür. Stateless yaklaşımda sepet Redis'te bir kullanıcı anahtarı altında tutulur. Artık kullanıcının isteği hangi sunucuya giderse gitsin, o sunucu sepeti Redis'ten okur. Sonuç: Kara Cuma'da trafik on kat arttığında beş yerine elli sunucu çalıştırırsınız ve hiçbir şey bozulmaz.

## Darboğaz (Bottleneck): Sistemin En Zayıf Halkası

### Tanım ve Kök Neden

Bir zincir en zayıf halkası kadar güçlüdür. Bir sistemin toplam kapasitesi de en yavaş, en doygun bileşeni kadardır. İşte bu sınırlayıcı bileşene darboğaz (bottleneck) denir. Sistemin geri kalanını ne kadar güçlendirirseniz güçlendirin, darboğaz açılmadıkça toplam throughput artmaz.

Darboğazın var olmasının kök nedeni, sistemlerin heterojen olmasıdır. Bir istek; yük dengeleyiciden geçer, uygulama sunucusunda işlenir, veritabanına sorgu atar, belki bir cache'e uğrar, bir dış API'yi çağırır. Bu bileşenlerin her birinin kapasitesi farklıdır. En düşük kapasiteli olan, tüm hattın hızını belirler. Tıpkı bir üretim bandında en yavaş istasyonun tüm bandın hızını belirlemesi gibi (bu, Kısıtlar Teorisi / Theory of Constraints'in temel gözlemidir).

### Darboğazı Bulmanın Mantığı: Little Yasası ve Kuyruklar

Darboğazı anlamanın matematiksel çerçevesi kuyruk teorisidir. **Little Yasası (Little's Law)** der ki: Bir sistemdeki ortalama iş sayısı (L), varış hızı (λ) ile ortalama bekleme süresinin (W) çarpımına eşittir; yani L = λ × W. Bu basit denklem şunu söyler: Bir bileşene gelen istek hızı, o bileşenin işleme hızını aşmaya başladığında kuyruk sonsuza doğru büyür ve bekleme süresi patlar.

Pratik işareti şudur: Bir kaynağın kullanımı (utilization) yüzde yüze yaklaştıkça bekleme süresi lineer değil, üstel artar. Yüzde yetmiş kullanımda sistem rahatken, yüzde doksan beşte gecikme uçar. Bu yüzden deneyimli mimarlar bileşenleri asla yüzde yüz kullanıma kadar zorlamaz; darboğaz oluşmadan önce her zaman bir tampon bırakır.

### Darboğaz Nasıl Tespit Edilir?

Darboğaz avında altın kural: Tahmin etme, ölç. Mühendisler sezgiyle yanlış bileşeni suçlamaya eğilimlidir. Doğru yaklaşım metodolojiktir:

1. **Uçtan uca gözlemlenebilirlik (observability):** Bir isteğin katmanlar arasında geçirdiği süreyi dağıtık izleme (distributed tracing) ile parçalara ayırın. Hangi katman sürenin çoğunu yiyor?
2. **Kaynak doygunluğunu izleyin:** Her bileşen için CPU, bellek, disk G/Ç (I/O), ağ ve bağlantı havuzu (connection pool) doygunluğuna bakın. Yüzde yüze dayanan ilk kaynak güçlü şüphelidir.
3. **Yük testi (load testing):** Kademeli olarak yükü artırın ve throughput'un doğrusal artmayı bıraktığı, gecikmenin dikleştiği "diz" (knee) noktasını bulun. O noktada doyan kaynak, darboğazdır.

Kritik uyarı: Bir darboğazı açtığınızda, darboğaz kaybolmaz; sadece bir sonraki en zayıf bileşene *taşınır*. Veritabanını hızlandırırsınız, bu sefer uygulama sunucusunun CPU'su doyar. Bu yüzden ölçeklenebilirlik çalışması tek seferlik değil, sürekli ve yinelemeli (iteratif) bir süreçtir.

### Tipik Darboğaz: Veritabanı

Modern web mimarilerinde darboğaz neredeyse her zaman uygulama katmanından önce veritabanında ortaya çıkar. Sebep temeldir: Uygulama sunucuları stateless olduğundan kolayca çoğaltılabilir, ama veritabanı paylaşılan durumu tuttuğu için kolayca çoğaltılamaz. Bir veritabanına yeni bir yazma kopyası (write replica) eklemek, tutarlılık koordinasyonu gerektirdiğinden (USL'nin coherency maliyeti) çok daha zordur. Bu yüzden ölçeklenebilirlik savaşları çoğunlukla veri katmanında verilir: read replica'lar, önbellekleme, sharding (parçalama) ve CQRS gibi teknikler hep bu tek gerçeğe cevaptır.

## Kapasite Tahmini (Capacity Planning)

### Tanım ve Amaç

Kapasite tahmini, gelecekteki yükü öngörüp o yükü karşılamak için ne kadar kaynak gerektiğini önceden hesaplama disiplinidir. Amacı iki uçtan da kaçınmaktır: Az kaynak ayırırsanız sistem çöker ve müşteri kaybedersiniz; fazla kaynak ayırırsanız boşa para harcarsınız. Kapasite tahmini bu ikisi arasındaki dengeyi verilere dayanarak kurar.

### Çalışma Mantığı: Sayılara Dayanan Tahmin

İyi bir kapasite tahmini sezgiyle değil, birkaç temel büyüklükten geriye doğru hesapla yapılır. Çekirdek metrikler şunlardır:

- **Throughput hedefi:** Genellikle saniyedeki istek sayısı (RPS/QPS) olarak ifade edilir. "Zirvede saniyede kaç istek?" sorusudur.
- **Ortalama ve zirve yük ilişkisi:** Yük hiçbir zaman düz değildir. Günün tepe saati, ortalamanın çok üstünde olabilir. Kapasite ortalamaya değil, zirveye göre planlanır. Ayrıca "kalın kuyruk" olaylara (kampanya, viral an) karşı bir güvenlik payı (headroom) eklenir.
- **Tek birim kapasitesi:** Bir sunucunun, kabul edilebilir gecikmeyi bozmadan saniyede kaç isteği karşılayabildiği. Bu değer *ölçülerek* bulunur, tahmin edilerek değil.

Temel hesap kabaca şudur: Gereken birim sayısı, hedeflenen zirve throughput'un tek birim kapasitesine bölünmesiyle bulunur; üzerine arıza payı (bir makine çökerse diğerleri yükü kaldırabilmeli, buna N+1 ya da N+2 yedeklilik denir) ve büyüme payı eklenir. Örneğin bir sunucu güvenli biçimde 500 RPS kaldırıyorsa ve zirve hedefiniz 4000 RPS ise, sekiz sunucu işi görür; ama bir makinenin çökme ihtimali için dokuza, önümüzdeki çeyreğin büyümesi için ona çıkarırsınız.

### Zirve Yükü Anlamak: Ortalama Aldatıcıdır

Kapasite tahmininde en sık yapılan zihinsel hata, ortalamayla planlamaktır. Ortalama günlük yük düşük görünse bile, kullanıcı davranışı yoğunlaşmıştır: Sabah dokuzda herkes aynı anda giriş yapar, öğlen kampanya başlar, akşam trafik zirveye çıkar. Sistem, ortalamada değil zirvede çökeceği için kapasite daima p99 (yüzde doksan dokuzuncu yüzdelik) gecikme ve zirve throughput üzerinden planlanır. "Ortalama gecikmemiz iyi" cümlesi çoğu zaman en yavaş yüzde birlik kullanıcı deneyiminin felaket olduğunu gizler.

### Sürüklenen İki Yaklaşım: Statik ve Elastik

**Statik (öngörülü) kapasite:** Trafiği önceden tahmin edip kaynakları sabitlersiniz. Öngörülebilir yükler ve kendi donanımınızı işlettiğiniz (on-premise) durumlar için uygundur. Riski, tahmin yanılırsa ya boşa para ya çöküştür.

**Elastik (otomatik) kapasite:** Bulut ortamında, yük arttıkça otomatik olarak makine eklenir, azaldıkça geri alınır (autoscaling). Bu, ani ve öngörülemez zirveler için idealdir ve boşta duran kaynak maliyetini düşürür. Ancak "her şeyi otomatik ölçekleme çözer" yanılgısına düşmek tehlikelidir: Ölçek çıkışı anlıktır, ölçek girişi anlık değildir; yeni bir makinenin ayağa kalkması (soğuk başlangıç / cold start) dakikalar alabilir. Trafik dakikalar değil saniyeler içinde patlarsa, autoscaling yetişemeden sistem çöker. Bu yüzden elastik sistemlerde bile daima bir taban kapasite ve önceden ısıtılmış (pre-warmed) bir tampon bulundurulur.

## Yaygın Hatalar ve Tuzaklar

**Erken ölçekleme (premature scaling):** Henüz on kullanıcısı olan bir ürün için Kubernetes, mikroservisler ve global dağıtım kurmak. Bu, çözülmemiş bir problem için karmaşıklık bedeli ödemektir. Karmaşıklık ölçeklenmenin en büyük gizli maliyetidir; ölçekleme problemi kanıtlanana kadar en basit çalışan mimaride kalmak neredeyse her zaman doğrudur.

**Yerel diske ya da belleğe durum yazmak:** Stateless olduğunu sandığınız bir servisin sessizce yerel diske dosya yazması veya bellekte cache tutması. Tek makinede çalışırken sorun görünmez; ikinci makine eklendiği an tutarsızlık patlar. Bu, "test ortamında çalışıyordu, üretimde bozuldu" hikâyelerinin klasik nedenidir.

**Darboğazı ölçmeden tahmin etmek:** "Kesin veritabanıdır" deyip aylarca veritabanı optimize ederken gerçek darboğazın bir dış API çağrısı olduğunu fark etmemek. Ölçmeden yapılan optimizasyon, en iyi ihtimalle boşa emek, en kötü ihtimalle yeni darboğazlar yaratmaktır.

**Ölçeklenmeyi yalnızca "makine eklemek" sanmak:** USL'nin öğrettiği gibi, koordinasyon maliyetini düşürmeden makine eklemek bir noktadan sonra kapasiteyi *düşürür*. Gerçek iş, paylaşılan durumu ve senkronizasyon noktalarını azaltmaktır.

**Ortalamayla kapasite planlamak:** Yukarıda anlatıldığı gibi, sistem zirvede çöker. Ortalamaya göre yapılan plan, ilk gerçek yoğunlukta çöker.

**Tek arıza noktasını görmezden gelmek:** Onlarca stateless sunucu çalıştırıp hepsini tek bir veritabanına, tek bir cache'e ya da tek bir yük dengeleyiciye bağlamak. Uygulama katmanı ölçeklenmiş olsa da o tekil bileşen çökerse tüm sistem çöker. Dayanıklılık, zincirin her halkasında yedeklilik gerektirir.

## En İyi Pratikler

**Stateless tasarla, durumu dışarı taşı.** Uygulama sunucularını baştan durumsuz kabul et. Oturumu token'a veya paylaşılan cache'e, dosyaları nesne deposuna, kalıcı veriyi veritabanına koy. Bu tek karar, yatay ölçeklemenin kapısını açar ve maliyeti neredeyse sıfırdır eğer baştan yapılırsa.

**Önce ölç, sonra optimize et.** Her ölçeklenebilirlik çalışmasına gözlemlenebilirlikle başla: metrikler, dağıtık izleme, kaynak doygunluğu. Darboğazı veriyle bul, sezgiyle değil. Sonra en dar noktayı aç, ölç, tekrarla.

**Zirveye göre planla, güvenlik payı bırak.** Kapasiteyi ortalamaya değil zirveye, tek bir sayıya değil p99 gecikmeye göre boyutlandır. Kaynakları asla yüzde yüz kullanıma kadar zorlama; kuyruk teorisi gereği doyum noktasına yaklaştıkça gecikme patlar. Daima bir tampon (headroom) bulundur.

**Yedeklilik kur (N+1 / N+2).** Bir makinenin her an çökebileceğini varsay. Kapasiteyi, bir (ya da iki) birim düştüğünde kalanların yükü kaldıracağı şekilde boyutlandır. Tek arıza noktalarını sistematik olarak avla ve her katmanda çoğalt.

**Dikey çalış, yatay tasarla.** Erken aşamada dikey ölçekleme ile basitliği koru ve zaman kazan; ama mimariyi yatay ölçeklenebilir (stateless, paylaşılan durumu izole edilmiş) olacak şekilde kur ki büyüme geldiğinde geçiş ucuz olsun.

**Veri katmanını özel olarak düşün.** Ölçeklenebilirliğin gerçek savaşı veritabanındadır. Önbellekleme (caching), okuma kopyaları (read replicas), sharding ve okuma-yazma ayrımı (CQRS) gibi teknikleri, uygulama katmanını çoğaltmadan önce planla; çünkü asıl darboğaz büyük olasılıkla orada oluşacak.

**Zarafetle bozulmayı tasarla (graceful degradation).** Sistem tavana dayandığında ne olacağını önceden kararlaştır. Aşırı yük altında bazı isteklerin reddedilmesi (load shedding, backpressure), ikincil özelliklerin geçici kapatılması, tam çöküşten kat kat iyidir. İyi ölçeklenen sistem, sınırına dayandığında patlamaz; yavaşlar ama ayakta kalır.

**Otomatik ölçeklemeye körü körüne güvenme.** Autoscaling güçlüdür ama soğuk başlangıç gecikmesi vardır. Taban kapasiteyi koru, önceden ısıtılmış tampon bulundur ve ani zirveler için ölçekleme kurallarını gerçek yük desenlerine göre ayarla.

## Sonuç

Ölçeklenebilirlik, tek bir teknikle çözülen bir özellik değil, sistemin her katmanına işlenen bir tasarım disiplinidir. Kökeninde tek bir gerçek yatar: Kapasiteyi sınırlayan şey işin kendisi değil, paylaşılan durum ve koordinasyon maliyetidir. Dikey ve yatay ölçekleme bu maliyetle başa çıkmanın iki farklı stratejisi, stateless mimari yatay ölçeklemenin önkoşulu, darboğaz analizi sistemin gerçek sınırını bulmanın yöntemi, kapasite tahmini ise geleceğe hazırlanmanın disiplinidir. Hepsini birbirine bağlayan ilke şudur: Ölç, koordinasyonu azalt, zirveye göre planla ve sistemin sınırına dayandığında çökmek yerine zarafetle yavaşlamasını sağla.
