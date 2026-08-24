# Dayanıklılık Kalıpları (Resilience Patterns)

Dağıtık sistemlerde başarısızlık bir istisna değil, kuraldır. Yeterince büyük bir sistemde her an bir düğüm çöker, bir ağ bağlantısı kopar, bir bağımlılık yavaşlar. Dayanıklılık kalıpları (resilience patterns), bir bileşenin başarısızlığının bütün sistemi çökertmesini engellemek; hataları izole etmek, sınırlamak ve zarif bir şekilde (gracefully) yönetmek için geliştirilmiş yerleşik mühendislik çözümleridir. Bu makale dört temel kalıba odaklanıyor: **timeout**, **retry + backoff + jitter**, **circuit breaker** ve **bulkhead**. Bunlar birbirinin alternatifi değil, birlikte katmanlı bir savunma oluşturan tamamlayıcı araçlardır.

## Sorunun Kök Nedeni: Neden Dayanıklılığa İhtiyaç Var?

Dayanıklılık kalıplarını anlamak için önce başarısızlığın dağıtık sistemlerde nasıl _yayıldığını_ (propagate) kavramak gerekir. Tek bir işlemde çalışan monolitik bir programda bir fonksiyon çağrısı ya döner ya hata fırlatır; arada gri bir bölge yoktur. Ağ üzerinden yapılan bir çağrıda ise durum tamamen farklıdır: çağrı başarılı olabilir, hata dönebilir veya **hiç dönmeyebilir**. İşte bu "hiç dönmeme" ihtimali, dağıtık sistemlerin en sinsi düşmanıdır.

Bir servisin (A) başka bir servise (B) senkron çağrı yaptığını düşünelim. B servisi yavaşladığında, A'daki her istek B'nin cevabını beklerken bir thread'i (veya connection'ı) meşgul eder. B'nin yanıt süresi 50 ms'den 5 saniyeye çıkarsa, A'ya gelen istek hacmi aynı kalsa bile A'daki bekleyen thread sayısı yüzlerce kat artar. Kısa süre içinde A'nın thread pool'u veya connection pool'u tükenir. Artık A yeni istekleri işleyemez hâle gelir; B ile hiç ilgisi olmayan istekler bile A'da beklemeye başlar. Böylece B'nin yavaşlığı A'yı da düşürür. A'yı çağıran C servisi de aynı mekanizmayla düşer. Bu zincirleme çöküşe **cascading failure** (basamaklı başarısızlık) denir ve bir tek yavaş bağımlılığın koca bir platformu dakikalar içinde diz çöktürdüğü senaryonun temelidir.

Buradaki kök neden şudur: **kaynaklar (thread, connection, memory) sonludur ve bekleme bu kaynakları tutar.** Dayanıklılık kalıplarının hepsi, aslında bu tek gerçeğe verilen farklı cevaplardır. Timeout, beklemeyi zamanla sınırlar. Bulkhead, tükenebilecek kaynakları bölümlere ayırır. Circuit breaker, işe yaramayacağı belli olan çağrıları hiç başlatmaz. Retry ise başarısızlığın _geçici_ olduğu durumlarda telafi sağlar ama yanlış kullanıldığında sorunu büyütür.

## Timeout: Sonsuz Beklemeyi Kesmek

### Tanım ve Çalışma Mantığı

Timeout, bir işlemin (ağ çağrısı, kilit alma, sorgu) tamamlanması için tanınan azami süredir. Bu süre dolduğunda işlem iptal edilir ve hata olarak ele alınır. Basit görünse de timeout, dayanıklılığın en temel ve en çok ihmal edilen taşıdır. Diğer üç kalıbın hepsi doğru çalışmak için timeout'a bağımlıdır: circuit breaker bir çağrının "başarısız" olduğunu ancak bir timeout sınırı sayesinde anlar; retry, sonsuza kadar beklemeyen bir çağrıyı yeniden dener.

Timeout'un varlık nedeni yukarıda anlatılan kaynak tükenmesidir. Bir çağrı için üst sınır koymamak, o çağrının bağlı olduğu bir thread'in _sonsuza kadar_ meşgul kalabilmesi demektir. Pratikte "sonsuz" olmasa bile, alttaki TCP katmanının veya işletim sisteminin varsayılan timeout'ları çoğu zaman dakikalar mertebesindedir; bu da uygulama düzeyinde felakete yol açacak kadar uzundur.

### Katmanlı Timeout'lar ve Zaman Bütçesi

Gerçek dünyada tek bir timeout yoktur; bir dizi katman vardır: connection timeout (bağlantı kurma süresi), read/socket timeout (yanıtın gelmesini bekleme), ve request timeout (isteğin baştan sona toplam süresi). Bunları ayırt etmek önemlidir çünkü farklı arızaları yakalarlar. Connection timeout, karşı tarafın hiç erişilebilir olmadığını hızlıca yakalar; socket timeout, bağlantı kurulduktan sonra takılan yanıtı yakalar.

Kritik ama sık atlanan kavram **timeout budget** (zaman bütçesi) veya **deadline propagation**'dır. Bir kullanıcı isteği A → B → C → D zincirinden geçiyorsa ve kullanıcıya en fazla 3 saniyede yanıt vermek istiyorsak, bu 3 saniye zincir boyunca paylaştırılmalıdır. A, B'yi çağırırken ne kadar süresinin kaldığını B'ye bildirmeli; B de kendine kalan süreyi C'ye aktarmalıdır. Aksi hâlde her katman bağımsız olarak "10 saniye" beklerse, kullanıcı çoktan vazgeçip gitmişken sistem hâlâ boşa çalışan bir isteğin peşinde kaynak harcar. gRPC gibi çerçeveler bu "deadline" kavramını yerel olarak destekler; HTTP tabanlı sistemlerde ise çoğu zaman elle taşınması gerekir.

### Yaygın Hatalar

- **Timeout hiç koymamak veya kütüphane varsayılanına güvenmek.** Birçok HTTP istemcisinin varsayılan timeout'u ya yoktur ya da çok uzundur. "Varsayılan yeterlidir" varsayımı, üretimdeki en yaygın kaynak tükenmesi nedenlerinden biridir.
- **İç içe timeout'ların tutarsızlığı.** Dıştaki timeout içtekinden kısaysa, içteki çağrı hiçbir zaman kendi timeout'una ulaşamadan dıştan kesilir; bu da retry mantığını ve hata sınıflandırmasını bozar. Genel kural: dış katmanın timeout'u, iç katmanların toplamından büyük olmalıdır — ama toplam kullanıcı bütçesini de aşmamalıdır.
- **Timeout'u iptal ile birleştirmemek.** Timeout dolduğunda istemci beklemeyi bırakır ama sunucu tarafındaki iş hâlâ çalışıyor olabilir. İdeal olan, timeout'un altta yatan işlemi de (context cancellation, connection close) gerçekten iptal etmesidir; yoksa sunucu, kimsenin beklemediği bir yanıtı üretmek için kaynak harcamaya devam eder.

## Retry + Backoff + Jitter: Geçici Hataları Telafi Etmek

### Tanım ve Kök Mantık

Retry (yeniden deneme), başarısız bir işlemi tekrar denemektir. Bunun altındaki temel varsayım şudur: bazı hatalar **geçici (transient)** olur — anlık bir ağ dalgalanması, kısa süreli bir aşırı yüklenme, bir load balancer'ın bir düğümü döngüden çıkarması. Bu tür hatalarda birkaç yüz milisaniye sonra yapılan yeni bir deneme büyük olasılıkla başarılı olur.

Ancak retry, dayanıklılık kalıpları arasında **iki ucu keskin bıçaktır**. Yanlış uygulandığında, çözmeye çalıştığı sorunu şiddetlendirir. Nedenini anlamak kritik: Bir servis aşırı yük altında hata dönmeye başladığında, tüm istemciler _hemen_ ve _birden fazla kez_ yeniden denerse, servise gelen yük olduğundan kat kat artar. Zaten boğulmakta olan servise, tam da toparlanmaya çalıştığı anda daha fazla istek yağar. Bu, "retry storm" olarak bilinen ve kendi kendini besleyen bir çöküş sarmalıdır. Bu yüzden retry asla çıplak (naked) kullanılmaz; **backoff** ve **jitter** ile birlikte kullanılır.

### Backoff: Denemeler Arasını Açmak

Backoff, ardışık denemeler arasındaki bekleme süresini kademeli olarak artırmaktır. En yaygın biçimi **exponential backoff** (üstel geri çekilme) olup, bekleme süresi her denemede katlanarak büyür: örneğin temel bekleme _base_ ise, n'inci denemeden önce beklenen süre yaklaşık `base * 2^n` olur (çoğu zaman bir üst sınıra, _cap_, tabi tutulur). Mantığı basittir: eğer sorun geçici bir sıkışmaysa, her denemede biraz daha beklemek, hedef servise toparlanması için zaman tanır ve gelen yükü zamana yayar.

### Jitter: Sürüyü Dağıtmak

Sadece exponential backoff yeterli değildir. Diyelim ki bir servis bir anda düştü ve binlerce istemci aynı anda hata aldı. Hepsi aynı backoff formülünü kullanıyorsa, hepsi de _tam olarak aynı anda_ yeniden dener. İlk denemeleri aynı anda, ikinci denemeleri (aynı 2 saniye backoff'tan sonra) yine aynı anda gerçekleşir. Böylece yük, dağılmış olması gerekirken senkronize dalgalar hâlinde gelir; bu olguya **thundering herd** (gürleyen sürü) denir.

Çözüm **jitter**: backoff süresine rastgelelik eklemek. Amaç, istemcilerin yeniden deneme anlarını zamana yaymak, senkronizasyonu kırmaktır. Yaygın bir ve etkili yaklaşım "full jitter"dır: hesaplanan backoff üst sınırı `[0, base * 2^n]` aralığında olacak şekilde, bekleme süresi bu aralıktan _rastgele_ seçilir. Böylece iki farklı istemcinin aynı anda denemesi olasılığı düşer ve hedef servise gelen yük düzleşir. Sezgiye aykırı görünse de, çoğu durumda düzgün jitter eklemek, karmaşık backoff formüllerinden daha çok fark yaratır.

### Idempotency: Retry'ın Gizli Önkoşulu

Retry'ı güvenli kılan en önemli koşul **idempotency**'dir. Bir işlem idempotent ise, bir kez veya birden çok kez uygulanması aynı sonucu verir. Sorun şu ki, bir istek başarısız gibi görünebilir ama aslında sunucuda işlenmiş olabilir — örneğin sunucu isteği aldı, işledi, ama yanıtı istemciye ulaşmadan ağ koptu. İstemci timeout görür ve yeniden dener. İşlem idempotent değilse (örneğin "hesaptan 100 TL çek"), bu yeniden deneme parayı iki kez çeker.

Bu yüzden retry uygulanacak işlemler ya doğaları gereği idempotent olmalı (GET, PUT), ya da bir **idempotency key** ile idempotent hâle getirilmelidir: istemci her mantıksal işleme benzersiz bir anahtar atar, sunucu bu anahtarı daha önce gördüyse işlemi tekrar yapmaz, önceki sonucu döner. Ödeme, sipariş oluşturma gibi kritik işlemlerde bu mekanizma retry'ın olmazsa olmazıdır.

### Neyi Yeniden Denememek Gerekir

Her hata retry'a uygun değildir. Retry yalnızca geçici hatalarda anlamlıdır. Kalıcı hataları (permanent errors) yeniden denemek boşa kaynak harcar ve hatta zararlıdır:

- **İstemci hataları (4xx sınıfı):** Geçersiz istek, yetkisiz erişim, bulunamayan kaynak — bunları yeniden denemek anlamsızdır; istek bir sonraki denemede de aynı şekilde reddedilir.
- **İş kuralı hataları:** Yetersiz bakiye, doğrulama hatası gibi durumlar retry ile düzelmez.
- **429 (Too Many Requests) durumu özeldir:** Bu, retry edilebilir bir durumdur ama sunucu genellikle bir `Retry-After` başlığıyla ne kadar beklenmesi gerektiğini söyler; bu değere saygı gösterilmelidir.

Ayrıca **toplam deneme sayısı sınırlanmalı** ve **retry bütçesi (retry budget)** kullanılmalıdır. Retry budget, "en fazla toplam trafiğin %X'i retry olabilir" gibi bir sınır koyarak, sistem genelinde retry storm'un önünü keser.

## Circuit Breaker: İşe Yaramayacak Çağrıyı Hiç Başlatmamak

### Tanım ve Analoji

Circuit breaker (devre kesici), adını elektrik sigortalarından alır. Bir devrede aşırı akım olduğunda sigorta atar ve devreyi keser; böylece kablolar yanmaz. Yazılımda circuit breaker, bir bağımlılığın sürekli başarısız olduğunu tespit ettiğinde ona giden çağrıları bir süreliğine _tamamen durdurur_. Yani "bu servis şu an bozuk, denemeye bile gerek yok, hızlıca hata dön" der.

Bunun retry'dan farkı ve onu tamamlayıcı yönü şudur: retry, tekil bir isteğin başarısızlığına yanıttır ("belki bu sefer olur"). Circuit breaker ise bir bağımlılığın _sistemik_ durumuna yanıttır ("bu servis genel olarak çökmüş, herkesin ısrarla denemesini durdurayım"). Yavaş bir servise ısrarla istek göndermek — hatta bunları retry ile çoğaltmak — kaynak tükenmesinin ta kendisidir. Circuit breaker tam da bu ısrarı keser.

### Üç Durum: Kapalı, Açık, Yarı Açık

Circuit breaker bir durum makinesidir (state machine) ve üç temel durumu vardır. İsimlerdeki "kapalı/açık" elektrik devresi mantığıyladır; sezgiye biraz ters gelebilir:

- **Closed (Kapalı):** Normal durum. Devre kapalıdır, yani çağrılar akar. Breaker bu sırada başarısızlıkları sayar. Başarısızlık oranı belli bir eşiği aşarsa (örneğin son N istekte %50'den fazla hata) breaker "açık" duruma geçer.
- **Open (Açık):** Devre açıktır, akım geçmez. Bağımlılığa hiçbir çağrı yapılmaz; her istek anında ve hızlıca hata döner (fail fast). Bu, hem çağıran servisi bekleme kaynağı harcamaktan korur hem de çöken servise nefes alma alanı bırakır. Bu durum belli bir süre (reset timeout) korunur.
- **Half-Open (Yarı Açık):** Reset süresi dolunca breaker, bağımlılığın toparlanıp toparlanmadığını anlamak için _sınırlı sayıda deneme_ isteği geçirir. Bu deneme istekleri başarılı olursa breaker "closed"a döner ve normal akış geri gelir. Başarısız olurlarsa breaker tekrar "open"a döner ve reset süresi yeniden başlar. Yarı açık durum, körlemesine devreyi tam açmak yerine, kontrollü bir yoklama (probe) yapılmasını sağlar; bu sayede servis daha toparlanmadan üstüne tüm yükün birden binmesi (yani yeni bir thundering herd) engellenir.

### Neden İşe Yarar: Fail Fast

Circuit breaker'ın asıl değeri **fail fast** ilkesindedir. Bir bağımlılık çöktüğünde, en kötü davranış her isteğin timeout süresince beklemesidir. 30 saniyelik timeout ile çöken bir servise giden her istek 30 saniye thread tutar. Circuit breaker açıkken ise istek mikrosaniyeler içinde hata döner. Bu, çağıran servisin kaynaklarını korumakla kalmaz; kullanıcıya da 30 saniye bekletip hata vermek yerine anında bir yanıt (belki bir fallback, belki nazik bir hata mesajı) verme imkânı tanır.

### Tuzaklar ve İnce Ayarlar

- **Eşiklerin yanlış ayarı.** Çok hassas bir breaker (birkaç hatada açılan), geçici dalgalanmalarda gereksiz yere devreyi keser ve sağlıklı trafiği reddeder. Çok toleranslı bir breaker ise çöken servise uzun süre istek göndermeye devam eder ve amacını yerine getirmez. Eşikler mutlak sayı yerine oran + minimum hacim üzerinden tanımlanmalıdır; örneğin "en az 20 istek olduğunda ve hata oranı %50'yi geçtiğinde aç". Az sayıda örnekle karar vermek yanıltıcıdır.
- **Fallback gerektirir.** Breaker açıldığında istek hızlıca başarısız olur — peki sonra ne olacak? İyi bir tasarımda bunun bir cevabı vardır: önbellekten eski veri dönmek, varsayılan bir değer sağlamak, özelliği geçici kapatmak (graceful degradation) veya en azından anlamlı bir hata döndürmek. Fallback olmadan circuit breaker, sadece hatayı hızlandırır.
- **Granülerlik.** Breaker genellikle bağımlılık başına (hatta endpoint başına) ayrı tutulmalıdır. Tek bir global breaker, ilgisiz bir bağımlılığın sorunu yüzünden sağlıklı bir bağımlılığa giden trafiği de kesebilir.
- **Yarı açık durumda eşzamanlılık kontrolü.** Half-open durumda çok sayıda deneme isteğinin aynı anda geçmesine izin verilirse, henüz toparlanmakta olan servis tekrar boğulur. Bu yüzden deneme sayısı sıkıca sınırlanmalıdır.

## Bulkhead: Kaynakları Bölmelere Ayırmak

### Tanım ve Denizcilik Analojisi

Bulkhead (bölme perdesi), adını gemilerin gövdesindeki su geçirmez bölmelerden alır. Bir gemi, gövdesi birden çok yalıtılmış bölmeye ayrıldığı için, bir bölme su alsa bile diğerleri kuru kalır ve gemi batmaz. Yazılımda bulkhead, kaynakları (thread pool, connection pool, semaphore) ayrı havuzlara bölerek, bir bileşenin kaynak tükenmesinin diğerlerini etkilemesini engeller.

### Çözdüğü Kök Problem

Makalenin başındaki cascading failure senaryosunu hatırlayalım: B servisi yavaşladığında, A'nın _tüm_ thread pool'u B'yi bekleyen isteklerle dolar ve A, B ile ilgisi olmayan istekleri bile işleyemez hâle gelir. Sorunun kökü, tüm bağımlılıkların _aynı_ paylaşılan kaynak havuzunu kullanmasıdır.

Bulkhead bu paylaşımı keser. Her bağımlılığa (veya her istek türüne) ayrı bir kaynak havuzu tahsis edilir. B'yi çağırmak için ayrılan havuz 10 thread ise, B tamamen çöküp bu 10 thread'in hepsi tıkansa bile, C ve D için ayrılmış havuzlar dokunulmadan kalır. A, B'ye giden isteklerde başarısız olur ama diğer işlevlerini sürdürür. Böylece bir bağımlılığın arızası, o bağımlılığın "bölmesi" içinde hapsedilir; gemi su alır ama batmaz.

### Uygulama Biçimleri

Bulkhead iki temel biçimde uygulanır:

- **Thread pool izolasyonu:** Her bağımlılık için ayrı bir thread pool ayrılır ve çağrılar o havuzda çalışır. Bu güçlü bir izolasyon sağlar (yavaş çağrı çağıran thread'i doğrudan bloke etmez) ama her çağrının bir thread'e geçişinin (context switch) bir maliyeti vardır.
- **Semaphore (sayaç) izolasyonu:** Ayrı thread havuzu yerine, her bağımlılık için eşzamanlı istek sayısına bir üst sınır konur. Daha hafiftir ama çağrılar hâlâ çağıran thread'de çalıştığından, thread pool izolasyonu kadar güçlü bir yalıtım sağlamaz.

Daha büyük ölçekte bulkhead, ayrı servis örnekleri, ayrı veritabanı connection pool'ları veya farklı müşteri segmentlerine ayrılmış kapasite havuzları biçiminde de görülür. Örneğin, ücretsiz kullanıcıların trafiğiyle ücretli kullanıcıların trafiğini ayrı havuzlara koymak, ücretsiz taraftaki bir yük patlamasının ücretli müşterileri etkilemesini engeller.

### Tuzaklar

- **Aşırı bölümleme kaynağı israf eder.** Her havuz sabit bir kaynak ayırdığından, çok fazla ince bölme, toplam kaynağın verimsiz kullanımına yol açar; bir havuz boşta beklerken başka bir havuz tıkanabilir. Bölme büyüklükleri gerçek trafik ölçülerine göre ayarlanmalıdır.
- **Havuz boyutlandırması zordur.** Çok küçük havuz, sağlıklı zamanlarda bile gereksiz reddedilmelere (rejection) neden olur; çok büyük havuz izolasyon değerini azaltır. Bu, gözlem ve yük testine dayanan sürekli bir ayardır.

## Kalıpları Birlikte Kullanmak: Katmanlı Savunma

Bu dört kalıp ayrı ayrı değil, birlikte anlam kazanır. Tek bir dışa bağımlı çağrıyı sararken hepsi belirli bir sırayla devreye girer ve şu senaryoyu düşünün:

1. **Bulkhead** en dışta durur: çağrı, o bağımlılığa ayrılmış sınırlı havuzdan bir yer ister. Havuz doluysa çağrı hemen reddedilir — böylece bu bağımlılık, diğerlerinin kaynağını asla ele geçiremez.
2. **Circuit breaker** devreye girer: bağımlılık zaten "open" durumundaysa çağrı hiç yapılmadan fail fast ile döner. Böylece çöken bir servise boşuna gidilmez.
3. **Timeout** çağrıyı zamanla sınırlar: çağrı yapıldıysa, belirlenen süre içinde dönmezse iptal edilir ve başarısız sayılır. Bu, circuit breaker'ın "başarısızlık" saymasını da besler.
4. **Retry** en içte, timeout ve hata sonrası devreye girer: hata geçici görünüyorsa, backoff + jitter ile sınırlı sayıda yeniden dener. Ama retry'lar da circuit breaker ve bulkhead sınırlarına tabidir.

Bu sıralamadaki uyum kritiktir. Örneğin retry ile circuit breaker arasında ince bir ilişki vardır: retry başarısızlıkları, breaker'ın hata sayacını beslemelidir ki, kalıcı olarak çöken bir bağımlılıkta breaker açılıp retry'ları da durdursun. Aksi hâlde retry ve breaker birbirine karşı çalışır. Benzer şekilde, retry'ın toplam süresi timeout bütçesini aşmamalıdır; yoksa kullanıcı, sistem hâlâ yeniden denerken çoktan pes etmiş olur.

## Gözlemlenebilirlik ve Test: Sessiz Dayanıklılık Tehlikelidir

Bu kalıpların en tehlikeli yanı, doğru çalışırken _sessiz_ olmalarıdır. Bir circuit breaker açıldığında, bir bulkhead istekleri reddettiğinde veya retry'lar devreye girdiğinde, sistem "çalışıyor" gibi görünebilir ama altta ciddi bir sorun vardır. Bu yüzden her kalıp **metriklerle donatılmalıdır**: breaker durum geçişleri, reddedilen bulkhead istekleri, retry sayıları ve oranları, timeout sıklığı sürekli izlenmeli ve alarma bağlanmalıdır. "Breaker sık sık açılıyor" bilgisi, altta yatan bir bağımlılık sorununun en erken habercisidir.

Ayrıca bu mekanizmalar **test edilmelidir**. Dayanıklılık kodu, tanımı gereği yalnızca nadir arıza durumlarında çalışır; bu yüzden normal testlerde hiç tetiklenmez ve sessizce bozulmuş olabilir. Bağımlılıkların bilinçli olarak yavaşlatıldığı, hataya zorlandığı **chaos engineering** ve fault injection pratikleri, bu kodun gerçekten çalıştığını doğrulamanın tek güvenilir yoludur. Üretimde ilk kez test edilen bir circuit breaker, çoğu zaman yanlış yapılandırılmış bir circuit breaker'dır.

## En İyi Pratiklerin Özeti

- **Her ağ çağrısına timeout koy.** Kütüphane varsayılanına asla güvenme; makul, ölçülmüş değerler belirle ve deadline propagation ile zaman bütçesini zincir boyunca taşı.
- **Retry'ı asla çıplak kullanma.** Daima exponential backoff + jitter ile birlikte; sadece geçici hataları, sadece idempotent işlemlerde, sınırlı deneme sayısı ve retry budget ile yeniden dene.
- **Circuit breaker'ı bağımlılık başına, oran + minimum hacim eşikleriyle ve mutlaka bir fallback ile kur.** Half-open durumda deneme sayısını sıkıca sınırla.
- **Bulkhead ile paylaşılan kaynak havuzlarını böl.** Kritik ve kritik olmayan trafiği, farklı bağımlılıkları ayrı havuzlara koy; boyutları gerçek trafik verisiyle ayarla.
- **Kalıpları katmanlı ve tutarlı kullan.** Retry–breaker–timeout etkileşimlerinin birbirini beslediğinden emin ol; toplam süreler kullanıcı bütçesini aşmasın.
- **Her şeyi ölç ve arızayı bilerek üret.** Metrik ve alarm olmadan dayanıklılık bir yanılsamadır; chaos testleri olmadan doğrulanmamıştır.

Sonuç olarak dayanıklılık, tek bir sihirli kalıpla değil; sonlu kaynakların nasıl tükendiğini anlayıp, beklemeyi sınırlayan (timeout), telafi eden (retry), sistemik arızayı durduran (circuit breaker) ve arızayı izole eden (bulkhead) araçları bilinçli biçimde katmanlayarak elde edilir. Bu kalıplar başarısızlığı ortadan kaldırmaz — çünkü bu imkânsızdır — ama başarısızlığın _sınırlı_ ve _yönetilebilir_ kalmasını sağlar.
