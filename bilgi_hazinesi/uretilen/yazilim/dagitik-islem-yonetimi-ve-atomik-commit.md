# Dağıtık İşlem Yönetimi ve Atomik Commit (2PC/3PC, Saga Pattern, TCC)

## Giriş: Neden Bu Konu Ayrı Bir Başlık Hak Ediyor

Tekil bir veritabanında ACID garantisi görece kolay elde edilir: tek bir işlem yöneticisi (transaction manager), tek bir write-ahead log, tek bir kilit tablosu vardır. Bir işlem ya tamamen uygulanır ya da hiç uygulanmaz, çünkü her şey aynı sürecin, aynı diskin, aynı saatin kontrolü altındadır.

Mikroservis mimarisine geçtiğinizde bu rahatlık kaybolur. Bir "sipariş oluştur" iş akışı; Sipariş servisinde bir satır ekler, Envanter servisinde stok düşer, Ödeme servisinde para çeker, Kargo servisinde gönderi kaydı açar. Bu dört işlem dört ayrı veritabanında, dört ayrı süreçte, ağ üzerinden haberleşerek gerçekleşir. Sorulması gereken soru şudur: **Bu dört yerel işlemi, tek bir atomik "hep ya da hiç" birimi gibi nasıl davranmaya zorlarız — ağ gecikmesi, kısmi çökme ve mesaj kaybı ihtimaline rağmen?**

Bu, ACID'in "A"sının (Atomicity) tek makine sınırının dışına taşınmasıdır ve kendine özgü bir problem sınıfıdır: **dağıtık atomik commit problemi**. Bu makale bu problemi çözmek için geliştirilmiş üç ana yaklaşımı — Two-Phase Commit (2PC), Three-Phase Commit (3PC), Saga Pattern ve Try-Confirm-Cancel (TCC) — kök neden, çalışma mantığı, tuzaklar ve savunma pratikleri ekseninde ele alır.

## Kök Neden: Dağıtık Sistemlerde Atomiklik Neden Zor?

Tek makinede atomiklik "ya hep ya hiç" kararını tek bir irade verir. Dağıtık sistemde N farklı katılımcı (participant) vardır ve her biri kendi yerel kararını verebilir (commit edebilirim / edemem), ama nihai karar **hepsinin aynı yönde hemfikir olmasını** gerektirir. Bu, dağıtık sistemlerin temel zorluklarından biri olan **consensus (uzlaşı)** problemine indirgenir.

Sorunu zorlaştıran üç fiziksel gerçek vardır:

1. **Ağ güvenilir değildir**: Mesajlar gecikebilir, kaybolabilir, sıra dışı ulaşabilir. Bir katılımcının "commit" mesajını hiç almaması ile "aldı ama cevabı kayboldu" durumunu koordinatör ayırt edemez.
2. **Süreçler çökebilir**: Koordinatör (coordinator) kararını verip duyurmadan çökerse, katılımcılar kilitli (kararsız) durumda askıda kalır. Bu duruma **bloklanma (blocking)** denir ve 2PC'nin temel zaafıdır.
3. **Zaman senkron değildir**: "Ne kadar bekleyip sonra timeout ile iptal edeyim" kararı, dağıtık saatlerin senkron olmaması yüzünden güvenilir değildir — bir katılımcı timeout ile abort ederken koordinatör aslında commit kararı vermiş olabilir.

CAP teoremi bağlamında düşünürsek: dağıtık atomik commit, aslında **güçlü tutarlılığı ağ bölünmesi (partition) ihtimaline rağmen** istemektir. Bu yüzden 2PC gibi protokoller CP tarafına yaslanır (tutarlılık için müsaitliği feda eder), Saga gibi desenler ise AP tarafına yaklaşır (müsaitliği korumak için anlık tutarlılıktan feragat edip nihai tutarlılığa/eventual consistency razı olur). Bu makaledeki her yöntem, aslında bu CAP gerilimini farklı bir noktada çözmenin yoludur.

## Two-Phase Commit (2PC): Klasik Çözüm

### Çalışma Mantığı

2PC, adından anlaşılacağı gibi işlemi iki fazda yürütür ve bir **koordinatör (transaction manager)** ile birden çok **katılımcı (resource manager / participant)** içerir.

**Faz 1 — Oylama (Voting / Prepare Phase):**
Koordinatör tüm katılımcılara "PREPARE" mesajı gönderir. Her katılımcı kendi yerel işlemini yapar, değişiklikleri kalıcı depoya (genelde kendi WAL/redo log'una) yazar, gerekli kilitleri tutar ve "Evet, commit edebilirim" (VOTE-COMMIT) ya da "Hayır, edemem" (VOTE-ABORT) cevabı döner. Bu noktada katılımcı **commit etmemiştir**, sadece "commit etmeye hazırım ve bu sözden dönmeyeceğim" taahhüdünü vermiştir.

**Faz 2 — Karar (Commit/Abort Phase):**
Koordinatör tüm oyları toplar. Herkes VOTE-COMMIT dediyse, tüm katılımcılara "COMMIT" komutu gönderir; herhangi biri VOTE-ABORT dediyse veya zaman aşımına uğradıysa, herkese "ABORT" gönderir. Katılımcılar bu komutu alınca kararı uygular ve kilitlerini serbest bırakır.

Kritik nokta: bir katılımcı VOTE-COMMIT dediği andan itibaren koordinatörün kararını bekleyen bir **belirsizlik penceresi (uncertainty window)**'ne girer. Bu pencerede kendi başına karar veremez — commit de edemez abort da, çünkü koordinatörün diğer katılımcılara ne söylediğini bilmez.

### Neden Bloklanma (Blocking) Sorunu Var?

İşte 2PC'nin en bilinen zaafı: Faz 1 bittikten sonra, tüm katılımcılar VOTE-COMMIT demiş ama koordinatör Faz 2'deki kararı göndermeden **çökerse**, katılımcılar sonsuza dek (ya da koordinatör ayağa kalkana kadar) kilitli bekler. Katılımcılar birbirleriyle konuşup "biz aramızda karar verelim" diyemezler, çünkü hiçbiri koordinatörün gerçek kararını (belki kararı verdi ama duyuramadı) bilemez — birbirlerine sorsalar bile hepsi aynı "bilmiyorum" durumunda olabilir. Bu, dağıtık sistemlerdeki **FLP imkânsızlık sonucu**yla da örtüşen bir gerçektir: asenkron bir sistemde, bir tek sürecin çökmesi ihtimaline karşı bile, sonlu zamanda garanti edilen uzlaşı (consensus) imkânsızdır.

Bu yüzden 2PC "CP" tercihidir: koordinatör kaybolduğunda sistem müsait olmaz (kilitli kalır), ama tutarlılık asla bozulmaz (kimse yanlışlıkla commit/abort etmez).

### 2PC'nin Doğru Kullanım Alanları

- Katılımcı sayısı azken ve hepsi aynı güven sınırı (aynı organizasyon, aynı veri merkezi) içindeyken.
- XA standardı (X/Open Distributed Transaction Processing) üzerinden ilişkisel veritabanları arası işlemlerde (örn. Java'da JTA/XA driver'lar).
- Kısa süreli işlemlerde — kilitlerin tutulma süresi kısa olmalı, çünkü kilit tutma süresi doğrudan sistem throughput'unu düşürür.

### Yaygın Hatalar ve Tuzaklar

- **Kilitleri uzun tutmak**: 2PC'de her katılımcı, Faz 1'den Faz 2'ye kadar satır/tablo kilitlerini tutar. Katılımcı sayısı arttıkça veya ağ gecikmesi büyüdükçe bu süre uzar, sistem throughput'u çöker. 2PC'yi mikroservislerde "genel çözüm" gibi kullanmak, aslında sistemin en yavaş bileşenine göre tüm sistemi kilitlemek demektir.
- **Coordinator'ı tek hata noktası (single point of failure) yapmak**: Koordinatör recovery log'unu (kimin ne cevap verdiğini) kalıcı diske yazmazsa, çöküp geri geldiğinde hangi işlemlerin hangi aşamada olduğunu bilemez ve katılımcılar sonsuza dek asılı kalır.
- **Heuristic decision (sezgisel karar) riskini görmezden gelmek**: Bazı XA implementasyonları, çok uzun süre koordinatör cevap vermezse katılımcının kendi başına "heuristic commit/abort" kararı vermesine izin verir. Bu, tutarlılığı garantisiz hale getirir ve production'da "heuristic exception" olarak karşınıza çıkar — sessizce veri tutarsızlığına yol açabilir.
- **Ağ bölünmesini (network partition) hesaba katmamak**: 2PC senkron ağ varsayar; gerçek ağlarda bölünme olduğunda koordinatör bir katılımcıya ulaşamıyorsa bunun "katılımcı öldü" mü yoksa "sadece ağ koptu" mu olduğunu ayırt edemez, bu yüzden en güvenli seçenek olan "bekle" davranışına düşer.

## Three-Phase Commit (3PC): Bloklanmayı Azaltma Girişimi

### Çalışma Mantığı

3PC, 2PC'nin bloklanma sorununu **ara bir faz ekleyerek** hafifletmeye çalışır: CanCommit → PreCommit → DoCommit.

1. **CanCommit**: Koordinatör katılımcılara "commit edebilir misin?" diye sorar (henüz kaynak kilitlemeden, sadece bir ön kontrol).
2. **PreCommit**: Herkes evet derse, koordinatör "PreCommit" gönderir. Katılımcılar bu noktada commit'e hazırlanır ve **eğer koordinatör kaybolursa bile, diğer katılımcılardan yeterli çoğunluğun PreCommit aldığını öğrenirlerse commit yönünde ilerleyebilirler** — çünkü PreCommit almış olmak, hiçbir katılımcının abort oyu vermediğinin kanıtıdır.
3. **DoCommit**: Koordinatör son onayı verir, herkes commit eder.

Buradaki kilit fikir: 3PC, katılımcılara **timeout sonrası koordinatörsüz karar verebilme** yeteneği kazandırır, çünkü PreCommit aşamasına ulaşmış olmak zaten "tüm katılımcılar hemfikirdi" bilgisini taşır. Bu da bloklanma süresini teorik olarak azaltır.

### Neden Pratikte Az Kullanılır?

- **Senkron ağ varsayımı hâlâ gerekli**: 3PC'nin bloklanmayı önleme garantisi, "mesaj gecikmesi sınırlıdır" (bounded network delay) varsayımına dayanır. Gerçek ağlarda (özellikle internet üzerinden coğrafi olarak dağıtık sistemlerde) bu varsayım güvenilir değildir; gecikme sınırı aşılırsa 3PC de bloklanabilir hatta **network partition sırasında tutarsız karar (split-brain benzeri durum: bir grup commit ederken başka bir grup abort eder)** riski taşıyabilir.
- **Ekstra round-trip maliyeti**: Üç fazlı olması, gecikmeyi ve mesaj sayısını artırır — zaten pahalı olan 2PC'yi daha da pahalı yapar.
- **Endüstride nadiren üretim kullanımı var**: Akademik olarak önemli bir kavramdır (özellikle "neden 2PC bloklanır, bunu nasıl azaltabiliriz" sorusuna cevap olarak), ama pratikte çoğu şirket 2PC'nin darboğazlarını 3PC ile değil, mimariyi değiştirerek (Saga, event-driven, tek-servis-tek-veri sahiplik ilkesi) çözer.

3PC'yi öğrenmenin asıl değeri, **"neden dağıtık uzlaşı zor" sorusuna ek bir açıdan bakmayı öğretmesidir**: senkron zaman varsayımlarının garantilere ne kadar sızdığını göstermesi bakımından eğitici bir ara basamaktır.

## Saga Pattern: Uzun Ömürlü İşlemler İçin Nihai Tutarlılık

### Kök Neden: Neden 2PC Yerine Saga?

Mikroservis mimarisinin temel ilkelerinden biri her servisin **kendi veritabanına sahip olması ve başka bir servisin veritabanına doğrudan erişmemesidir** (database-per-service). Bu, 2PC'nin gerektirdiği "ortak transaction koordinatörü altında tüm kaynakları kilitleme" modeliyle doğası gereği gerilim içindedir: kilitleri uzun süre (belki dakikalar, kullanıcı onayı bekleyen adımlarda saatler) tutmak, yüksek trafikli sistemlerde kabul edilemez.

Saga Pattern'in cevabı radikaldir: **atomikliği tek bir anlık kilitli işlemle değil, bir dizi bağımsız yerel işlem + her biri için önceden tanımlanmış bir telafi (compensating) işlemiyle** sağlamaktır. Yani "hep ya da hiç"i **anlık** değil, **zaman içinde ilerleyen** bir garanti haline getirir: ya tüm adımlar sırayla başarılı olur, ya da bir adım başarısız olduğunda önceki adımlar geriye doğru telafi edilir (compensate).

### Çalışma Mantığı

Her Saga, bir dizi yerel işlemden (T1, T2, ..., Tn) oluşur. Her Ti için bir telafi işlemi Ci tanımlanır (Ci, Ti'nin etkisini iş mantığı düzeyinde tersine çevirir — veritabanı ROLLBACK'i değil, **iş anlamı taşıyan tersine çevirme**dir: "parayı çek" yerine "parayı iade et", "stok düş" yerine "stok geri ekle").

Akış: T1 başarılı → T2 başarılı → T3 başarısız olursa, sistem C2 ve C1'i sırayla çalıştırarak sistemi mantıksal olarak T1 öncesi duruma getirir.

İki koordinasyon stili vardır:

**Koreografi (Choreography)**: Merkezi bir yönetici yoktur. Her servis kendi işlemini yapar ve bir olay (event) yayınlar; sıradaki servis bu olayı dinleyip kendi işlemini tetikler. Örneğin Sipariş servisi "SiparişOluşturuldu" olayı yayınlar, Envanter servisi bunu dinleyip stok düşürür ve "StokDüşürüldü" ya da "StokYetersiz" yayınlar.
- Avantaj: Gevşek bağlılık (loose coupling), yeni katılımcı eklemek kolay.
- Dezavantaj: İş akışının genel resmini görmek zorlaşır ("hangi olay kimi tetikliyor" haritası dağılır), döngüsel bağımlılık riski, uçtan uca test etmek zorlaşır.

**Orkestrasyon (Orchestration)**: Merkezi bir "saga orchestrator" servisi, hangi adımın sırayla çağrılacağını ve hata durumunda hangi telafilerin tetikleneceğini açıkça yönetir (genelde bir durum makinesi/state machine olarak).
- Avantaj: İş akışı tek bir yerde görünür, izlenebilirlik ve hata yönetimi daha kolay.
- Dezavantaj: Orkestratör, iş mantığının önemli bir kısmını üstlendiği için potansiyel bir "God object" / merkezi bağımlılık haline gelebilir; orkestratörün kendisi yüksek kullanılabilirliğe sahip olmalıdır (fakat 2PC koordinatöründen farklı olarak, kilit tutmadığı için bloklanma riski çok daha düşüktür).

### Neden "Nihai Tutarlılık" ve Neden Bu Kabul Edilebilir?

Saga sırasında sistem, T1 ile T3 arasında **geçici olarak tutarsız bir ara durumdadır** (örneğin sipariş "oluşturuldu" ama ödeme henüz alınmadı). Bu ara durumun dışarıya (başka okuyuculara) görünür olması, ACID'in Isolation garantisinin klasik anlamda kaybolduğu anlamına gelir. Bunu kabul edilebilir kılan şey, iş süreçlerinin zaten çoğu zaman doğası gereği aşamalı olmasıdır (bir e-ticaret siparişi de gerçek dünyada anlık değil, aşama aşama ilerler) — Saga bu gerçekliği yazılım modeline taşır.

### Tuzaklar ve En İyi Pratikler

- **Telafi işlemlerinin idempotent olmaması**: Ağ tekrar denemeleri (retry) yüzünden bir telafi işlemi birden fazla çağrılabilir. Eğer "parayı iade et" işlemi idempotent değilse, aynı iadeyi iki kez yapabilirsiniz. Her adım ve her telafi, bir **idempotency key** ile korunmalıdır.
- **Telafi edilemez işlemler (non-compensatable actions)**: "E-posta gönder" veya "SMS gönder" gibi bazı yan etkiler geri alınamaz. Saga tasarımında bu tür adımları mümkünse akışın **en sonuna** koymak temel bir pratiktir (geri dönüşü olmayan işlem, ancak diğer her şey kesinleşince yapılmalı).
- **Semantic lock eksikliği / "kirli okuma" riski**: Saga sırasında ara durumdaki veriyi başka bir süreç okuyup üzerine iş kurabilir (örn. henüz ödemesi tamamlanmamış siparişi "tamamlanmış" sayıp kargoya vermek). Buna karşı **semantic lock** (durumu açıkça "PENDING" gibi işaretleyip diğer süreçlerin bunu görmezden gelmesini sağlamak) veya **commutative updates** gibi teknikler kullanılır.
- **Saga'nın kendisinin durumunu kaybetmesi**: Orkestratör çökerse, saga'nın hangi adımda olduğu bilgisi kalıcı olarak (event log, veritabanı) saklanmalı; aksi halde recovery sonrası aynı adım tekrar mı çalıştırılacak yoksa devam mı edilecek belirsizleşir. Event sourcing bu yüzden Saga ile sıkça birlikte anılır.
- **Gözlemlenebilirlik (observability) eksikliği**: Dağıtık, çok adımlı bir işlemde hangi saga'nın hangi adımda takıldığını görmek için distributed tracing (correlation ID / saga ID'nin tüm loglarda taşınması) şarttır; aksi halde production'da "hangi sipariş neden yarım kaldı" sorusuna cevap vermek çok zorlaşır.

## Try-Confirm-Cancel (TCC): Uygulama Seviyesinde İki Fazlı Model

### Çalışma Mantığı

TCC, 2PC'nin fikrini (iki fazlı, kilite dayalı koordinasyon) korurken, kilitleme mekanizmasını **veritabanı seviyesinden uygulama/iş mantığı seviyesine** taşır. Her katılımcı üç operasyon sağlar:

1. **Try**: Kaynağı gerçekten değiştirmeden, **rezerve eder** (örn. "stoktan 3 adet düş" yerine "3 adedi rezerve/blocked olarak işaretle, gerçek stoktan düşme"). Bu adım her servisin kendi yerel işlemidir ve hemen commit edilir — uzun süreli dağıtık kilit yoktur.
2. **Confirm**: Tüm katılımcıların Try'ı başarılıysa, rezervasyonu kalıcı hale getirir (örn. rezerve edilen stok gerçekten düşülür).
3. **Cancel**: Herhangi bir Try başarısız olursa, tüm katılımcılarda rezervasyon geri alınır (rezerve edilen stok serbest bırakılır).

### 2PC ile Farkı ve Neden Önemli

2PC'de Faz 1 (Prepare), veritabanı seviyesinde **fiziksel bir kilit** tutar ve bu kilit dış dünyaya kapalıdır (generic, iş mantığından bağımsız). TCC'de Try adımı **iş mantığı seviyesinde bir rezervasyon** yapar; bu, kaynağı tamamen kilitlemek yerine "bu kadarını ayır, geri kalanını başkaları kullanabilir" esnekliğini sağlayabilir (örn. stok miktarı bazlı rezervasyon, tüm tabloyu kilitlemez). Bu yüzden TCC, Saga'ya göre **daha güçlü izolasyon** (rezervasyon sayesinde "kirli okuma" riski azalır) sağlarken, 2PC'ye göre **çok daha kısa süreli ve daha hafif kilitleme** sunar.

Bedeli: Her katılımcı servisin Try/Confirm/Cancel'ı **kendi başına, doğru semantikle** implemente etmesi gerekir — bu, Saga'daki "telafi işlemi yaz" yüküne benzer ama üç ayrı operasyonun (özellikle Try'ın rezervasyon mantığının) doğru tasarlanması ek mühendislik yükü getirir. TCC, tipik olarak finansal/ödeme sistemlerinde (örn. bir bakiyeyi "hold" etmek — kredi kartı ön otorizasyonu tam olarak bu mantıkla çalışır) tercih edilir.

### Yaygın Hatalar

- **Confirm/Cancel'ın idempotent olmaması**: Saga'daki gibi, ağ tekrarları yüzünden Confirm veya Cancel birden fazla tetiklenebilir; idempotency zorunludur.
- **Try aşamasının çok uzun tutulması**: Rezervasyon süresi uzarsa, kaynak "askıda" kalır (örn. kredi kartı ön otorizasyonunun süresi dolabilir); bir zaman aşımı ve otomatik Cancel mekanizması olmalı.
- **Coordinator'ın (TCC'yi tetikleyen servisin) kendisinin tek hata noktası olması**: TCC'de de bir koordinatör genelde Try'ları başlatıp sonucu toplar; bu koordinatörün durumu kalıcı olarak saklanmalı, yoksa "hangi katılımcılar Try'ı tamamladı, Confirm mi Cancel mi göndermeliyim" bilgisi kaybolabilir.

## Karşılaştırma ve Doğru Seçim Yapmak

| Kriter | 2PC | 3PC | Saga | TCC |
|---|---|---|---|---|
| Tutarlılık modeli | Güçlü (senkron) | Güçlü (varsayımlı senkron ağ) | Nihai (eventual) | Neredeyse güçlü (rezervasyon ile) |
| Kilit süresi | Uzun (tüm katılımcılar boyunca) | Uzun | Yok (her adım kendi içinde commit) | Kısa (sadece rezervasyon) |
| Bloklanma riski | Yüksek | Azaltılmış ama var | Yok (asenkron ilerler) | Düşük |
| Uygulama karmaşıklığı | Düşük (altyapı/driver hallediyor - XA) | Orta | Yüksek (her adım için telafi yazılmalı) | Yüksek (her katılımcı 3 operasyon yazmalı) |
| Tipik kullanım | Tek organizasyon, az katılımcı, kısa işlem | Akademik/nadiren üretim | Mikroservisler, uzun iş akışları | Finansal rezervasyon, ödeme |

Karar verirken sorulacak temel sorular:

1. **Katılımcılar aynı güven/altyapı sınırında mı?** Evetse ve işlem kısa süreliyse, 2PC (XA) makul bir seçenek olabilir.
2. **İşlem uzun sürebilir mi, insan onayı içeriyor mu?** Saga tercih edin — kilit tutmak imkansızdır.
3. **Ara durumun görünür olması iş açısından kritik bir sorun mu?** (örn. finansal bakiyenin geçici olarak yanlış görünmesi kabul edilemezse) TCC'nin rezervasyon modeli değerlendirilmeli.
4. **Telafi mantığı gerçekten tanımlanabiliyor mu?** Bazı işlemler (dış dünyaya e-posta/SMS gönderme, üçüncü taraf API'ye geri dönüşü olmayan çağrı) telafi edilemez; bu tür adımları akışın sonuna koymak veya Outbox Pattern gibi tekniklerle güvenceye almak gerekir.

## Tespit ve Gözlemlenebilirlik: Sorunları Nasıl Yakalarız?

Savunma/tespit perspektifinden, dağıtık işlem yönetiminde izlenmesi gereken sinyaller şunlardır:

- **Asılı kalan (in-doubt) işlemler**: 2PC/XA kullanan sistemlerde, koordinatör loglarında "PREPARE gönderildi ama commit/abort kararı verilmedi" kayıtları izlenmelidir; bu, potansiyel bloklanmanın erken göstergesidir.
- **Saga adım süresi anomalileri**: Bir saga adımının normalden çok uzun sürmesi (veya hiç tamamlanmaması), aşağı akış servisinin hatalı olduğuna işaret eder; her adım için timeout ve alerting tanımlanmalı.
- **Telafi/Cancel oranındaki artış**: Telafi işlemlerinin oranında ani artış, alt sistemlerden birinde (örn. envanter, ödeme sağlayıcısı) sistemik bir sorun olduğunun erken belirtisidir.
- **Idempotency ihlali izleri**: Aynı idempotency key ile birden fazla farklı sonuç üretilmesi (örn. bir iade işleminin iki kez kayda geçmesi), retry mantığının hatalı kurgulandığının kanıtıdır ve mutlaka loglanıp izlenmelidir.
- **Correlation/saga ID'nin uçtan uca taşınması**: Distributed tracing altyapısında (örn. bir trace ID) her adımın aynı kimlikle loglanması, "bu iş akışı nerede takıldı" sorusuna dakikalar içinde cevap verebilmenin önkoşuludur.

## Sonuç

Dağıtık atomik commit problemi, tek makinedeki ACID garantisinin ağ üzerinden koordine edilmesi gerektiğinde ortaya çıkan temel bir zorluktur ve kökeninde dağıtık uzlaşının (consensus) fiziksel kısıtları (güvenilmez ağ, süreç çökmeleri, senkron olmayan zaman) yatar. 2PC bu problemi güçlü tutarlılıkla ama bloklanma riskiyle çözer; 3PC bloklanmayı azaltmaya çalışır ama senkron ağ varsayımına bağımlı kalır ve pratikte az kullanılır. Saga Pattern, kilitlemeyi tamamen terk edip nihai tutarlılık ve telafi işlemleriyle uzun ömürlü iş akışlarını mümkün kılar; TCC ise rezervasyon tabanlı bir ara model sunarak Saga'nın esnekliği ile 2PC'nin güçlü izolasyonu arasında bir denge kurar. Doğru seçim; işlem süresi, katılımcıların güven sınırı, telafi edilebilirlik ve iş açısından ara durumun görünürlüğünün ne kadar kritik olduğuna bağlıdır — ve her seçim, aslında CAP teoreminin tutarlılık-müsaitlik geriliminin mikroservis mimarisindeki somut yansımasıdır.
