# Dağıtık Sistemlerde Hata Modelleri ve Byzantine Fault Tolerance

## Giriş: Neden Hata Modeli Konuşmalıyız?

Dağıtık bir sistem tasarlarken en temel soru şudur: "Bir bileşen bozulursa **nasıl** bozulur?" Bu sorunun cevabı bir keyfi ayrıntı değildir; sistemin dayanabileceği hata türünü, gereken replika sayısını ve kullanılabilecek konsensüs algoritmasını doğrudan belirler. Çoğu mühendis "sunucu çöktü" ile "sunucu yalan söylüyor" arasındaki farkı ciddiye almaz. Oysa bu iki durum tamamen farklı matematiksel garantiler gerektirir.

Bir **hata modeli** (fault model), sistemdeki bir düğümün (node) veya sürecin (process) hangi biçimde arızalanabileceğini tanımlayan formal bir varsayımdır. Bir algoritmanın doğruluk ispatı daima belirli bir hata modeli altında geçerlidir. Yanlış hata modeli varsayarsanız, ispatlanmış bir algoritma bile gerçek dünyada güvenliğini kaybeder. Bu makale hata modellerini en zayıftan en güçlüye doğru inceler ve en zorlu model olan **Byzantine** hataya karşı geliştirilmiş konsensüs mekanizmalarını (özellikle PBFT'yi) derinlemesine açıklar.

## Hata Modelleri Hiyerarşisi

Hata modelleri bir kapsama hiyerarşisi oluşturur: en genel model, altındaki tüm daha kısıtlı hataları da kapsar. Byzantine model en tepededir çünkü bir düğümün yapabileceği **her türlü** yanlış davranışı içerir.

### Fail-Stop (Dur-ve-Kes)

**Tanım:** Düğüm arızalandığında tamamen çalışmayı durdurur ve — kritik nokta — bu durdurmayı **diğer düğümler güvenilir biçimde tespit edebilir**. Yani sistemde bir "başarısızlık dedektörü" (failure detector) vardır ve bu dedektör hata yaptığında yanılmaz: bir düğümü öldü diye işaretlediyse, o düğüm gerçekten ölmüştür.

**Çalışma mantığı:** Bu, teorik olarak en kolay çalışılan modeldir çünkü belirsizlik yoktur. "Cevap gelmedi" ile "düğüm öldü" aynı anlama gelir. Gerçek ağlarda mükemmel bir fail-stop dedektörü kurmak çok zordur çünkü ağ gecikmesi ile gerçek çöküşü ayırt etmek mümkün değildir. Bu yüzden fail-stop daha çok teorik bir referans noktasıdır.

### Fail-Silent / Crash-Stop (Çökme)

**Tanım:** Düğüm çöktüğünde durur ve bir daha mesaj göndermez, ancak diğer düğümler bunu **kesin olarak** bilemez. Çöken bir düğüm ile sadece yavaş/erişilemez olan bir düğüm dışarıdan aynı görünür. Bu, pratikte en yaygın kabul edilen modeldir ve **crash fault** olarak da anılır.

**Çalışma mantığı ve önemi:** Raft ve (klasik) Paxos gibi konsensüs algoritmaları bu modelde çalışır. Buradaki temel zorluk, gerçek çöküş ile ağ gecikmesinin ayırt edilemezliğidir. FLP imkânsızlık teoremi (Fischer, Lynch, Paterson) tam da bu noktaya değinir: **tamamen asenkron** bir sistemde, tek bir düğüm bile çökebiliyorsa, deterministik bir algoritma konsensüse ulaşmayı **garanti edemez**. Pratik sistemler bunu zaman aşımları (timeout) ve kısmi senkron (partially synchronous) varsayımlarla aşar — yani sistem "sonunda" yeterince hızlı davranır.

### Fail-Noisy ve Omission (İhmal) Hataları

**Omission hatası**, düğümün bazı mesajları göndermeyi veya almayı "unutması"dır — ama tamamen çökmemiştir. Örneğin ağ arabelleği (buffer) taşması nedeniyle bazı paketler düşer. Bu, crash ile Byzantine arasında bir ara modeldir: düğüm kötü niyetli değildir ama tutarsız davranır.

### Byzantine (Keyfi) Hatalar

**Tanım:** Düğüm **herhangi bir** şekilde davranabilir: yanlış değer gönderebilir, farklı düğümlere farklı (çelişkili) değerler gönderebilir, protokolü kasten ihlal edebilir, mesajları geciktirebilir, uydurabilir veya tamamen sessiz kalabilir. Bu davranış rastgele bir bozulmadan (bit flip, bozuk disk) kaynaklanabileceği gibi, kasıtlı bir saldırgan (compromised node) tarafından da yönlendirilebilir.

**İsmin kökeni:** Terim, Lamport, Shostak ve Pease'in 1982 tarihli "The Byzantine Generals Problem" makalesinden gelir. Alegoride, birkaç Bizans generali bir şehri kuşatmıştır ve yalnızca ulaklarla haberleşerek ortak bir karara (saldır/geri çekil) varmalıdır. Sorun şudur: generallerden bazıları **haindir** ve farklı generallere kasten çelişkili mesajlar göndererek sadık olanları uyumsuz kararlara sürüklemeye çalışır. Soru: Sadık generaller, hainlerin varlığına rağmen nasıl ortak bir plana ulaşabilir?

Bu modelin önemi, gerçek dünyadaki iki senaryodan gelir: (1) **açık/güvensiz ortamlar** — blockchain gibi, katılımcıların birbirine güvenmediği sistemler; (2) **kritik/yüksek güvenilirlik sistemleri** — uçak aviyonik sistemleri, uzay araçları, nükleer kontrol gibi donanım arızasının keyfi çıktılar üretebileceği ortamlar.

## Byzantine Konsensüsün Temel Sınırı: Neden 3f + 1?

Byzantine hataya dayanan sistemlerin en kritik matematiksel sonucu şudur: **En fazla `f` adet Byzantine düğüme tolerans göstermek için toplam en az `n ≥ 3f + 1` düğüm gerekir.** Yani bir hain generale dayanmak için en az 4 general, ikiye dayanmak için 7 general gerekir. Bu, crash-tolerant sistemlerdeki `n ≥ 2f + 1` (basit çoğunluk) sınırından **belirgin biçimde daha katıdır**.

### Neden 2f + 1 Yetmez? — Sezgisel İspat

Sezgiyi adım adım kuralım. Byzantine bir sistemde bir düğümün, bir bilgiyi doğru kabul etmesi için yeterli sayıda "tanık"tan onay alması gerekir. İki temel gerçekle karşı karşıyayız:

1. **Byzantine düğümler cevap vermeyebilir.** Sağlıklı düğüm, `f` düğümden asla cevap gelmeyebileceğini varsaymak zorundadır (belki hepsi ölmüştür). Dolayısıyla ilerlemek için en fazla `n − f` cevap beklemelidir; daha fazlasını beklemek sistemi kalıcı olarak kilitler.

2. **Cevap veren düğümler yalan söyleyebilir.** Topladığı `n − f` cevabın içinde `f` tanesi Byzantine (yalancı) olabilir. Yani her toplama işleminde en kötü durumda `f` yalancı sese maruz kalır.

Şimdi kilit gereksinim: iki farklı "quorum" (yeter sayı kümesi) — örneğin bir yazma işlemini onaylayan küme ile onu okuyan küme — daima **en az bir dürüst düğümde** kesişmelidir ki tutarlılık korunsun. İki quorum her biri `n − f` büyüklüğündeyse, kesişimleri en az `2(n − f) − n = n − 2f` düğüm içerir. Bu kesişimin içinde en fazla `f` Byzantine düğüm olabileceğinden, en az bir **dürüst** düğümün ortak olması için:

```
n − 2f > f   ⟹   n > 3f   ⟹   n ≥ 3f + 1
```

İşte 3f + 1'in kaynağı budur. Kesişim garantisi (`n − 2f ≥ f + 1`) sağlanmazsa, bir saldırgan iki farklı gruba iki farklı gerçeği kabul ettirebilir; bu da **çatallanmaya** (fork / split-brain) yol açar. Blockchain bağlamında bu "çift harcama"nın (double-spend) protokol düzeyindeki karşılığıdır.

## PBFT: Practical Byzantine Fault Tolerance

Uzun süre Byzantine konsensüs teorik olarak mümkün ama pratik olarak çok pahalı sayıldı. **1999'da Castro ve Liskov'un yayımladığı PBFT (Practical Byzantine Fault Tolerance)** bunu değiştirdi: senkron olmayan (asenkron) ağlarda, gerçekçi performansla çalışabilen ilk pratik Byzantine-tolerant algoritmayı sundu. Modern BFT protokollerinin çoğu (Tendermint, HotStuff vb.) PBFT'nin fikirlerini geliştirir.

### Çalışma Modeli ve Roller

PBFT bir **state machine replication** (durum makinesi çoğaltma) protokolüdür: tüm dürüst replikalar aynı komut dizisini aynı sırayla uygular, dolayısıyla aynı duruma ulaşır. Sistemde bir **primary** (lider) ve geri kalan **backup** (yedek) replikalar vardır. Liderin görev dönemine **view** (görünüm) denir. Lider kötü davranırsa veya yanıt vermezse **view change** (görünüm değişimi) ile değiştirilir.

PBFT `n = 3f + 1` replika ile `f` Byzantine hataya dayanır. Kritik varsayımlar: mesajlar imzalanır (dijital imza veya MAC ile kimlik doğrulanır) ve ağ **kısmi senkron**dur — yani ilerleme (liveness) garantisi ağın sonunda düzelmesine bağlıdır, ancak **güvenlik (safety) asenkron koşulda bile korunur**. Bu ayrım hayatidir: PBFT ağ tamamen kaotikken **yanlış bir sonucu asla onaylamaz**; sadece ilerlemeyi geciktirir.

### Üç Fazlı Protokol

Normal çalışma (view change olmadan) üç mesaj fazından oluşur. İstemci bir istek gönderir, lider ona bir sıra numarası atar ve şu üç faz işler:

1. **Pre-prepare:** Lider, isteğe bir sıra numarası (sequence number) atayıp tüm yedeklere yayınlar. Bu faz sıralamayı **önerir**. Yedekler liderin geçerli bir sıra numarası önerdiğini ve daha önce aynı numaraya farklı bir istek atamadığını doğrular.

2. **Prepare:** Her yedek, gördüğü öneriyi diğer tüm replikalara yayınlar ("ben bu sıra numarasında bu isteği gördüm"). Bir replika `2f` adet eşleşen prepare mesajı (kendi dahil `2f + 1`) topladığında **prepared** durumuna geçer. Bu faz, **dürüst replikaların aynı sırada anlaştığını** garanti eder — yani lider farklı yedeklere farklı sıralamalar gönderemez, çünkü çelişki prepare fazında ortaya çıkar.

3. **Commit:** Prepared olan her replika bir commit mesajı yayınlar. `2f + 1` eşleşen commit toplandığında istek **committed** olur ve replika komutu uygular, ardından istemciye yanıt gönderir. Bu faz, kararın **view değişimlerine rağmen kalıcı olduğunu** (yani yeni lider gelse bile bu kararın unutulmayacağını) garanti eder.

İstemci, `f + 1` farklı replikadan aynı yanıtı aldığında sonucu kabul eder. Neden `f + 1`? Çünkü `f + 1` yanıtın içinde en az biri kesinlikle dürüsttür.

**İki fazın rol ayrımı, PBFT'yi anlamanın anahtarıdır:** Prepare fazı **aynı view içinde** sıralama üzerinde anlaşma sağlar (tek liderden çelişkili sıralamayı engeller). Commit fazı ise bu anlaşmanın **view'lar arası** hayatta kalmasını sağlar (view change sonrası kararın korunması). Tek fazla Byzantine güvenlik elde edilemez; iki tur oylama bu iki farklı garantiyi ayrı ayrı kurar.

### View Change: Lider Kötü Davranırsa

Lider Byzantine ise (örneğin hiç pre-prepare göndermiyor veya çelişkili sıralar dağıtıyorsa), yedekler zaman aşımıyla bunu fark eder ve bir **view-change** mesajı yayınlayarak yeni lidere (genelde `view + 1 mod n`) geçmek ister. Yeni lider `2f + 1` view-change mesajı topladığında yeni view'ı başlatır. Kritik incelik: yeni lider, önceki view'da **prepared/committed olmuş kararları korumak** zorundadır; view-change mesajları bu kararların kanıtını taşır, böylece onaylanmış hiçbir işlem kaybolmaz. Bu, güvenliğin lider değişse bile korunmasını sağlayan mekanizmadır.

### PBFT'nin Maliyeti ve Ölçeklenme Sınırı

PBFT'nin en büyük dezavantajı **mesaj karmaşıklığıdır**. Prepare ve commit fazları "herkes herkese" (all-to-all) yayın gerektirdiğinden, normal çalışma her istek için **O(n²)** mesaj üretir. Bu, PBFT'yi onlarca düğüme kadar pratik, ama binlerce düğüme ölçeklendirmede zorlayıcı kılar. HotStuff gibi sonraki protokoller mesaj karmaşıklığını lider-merkezli iletişim ve imza toplama (threshold signature) ile **O(n)**'e indirmeyi hedefler; bu, Facebook'un Libra/Diem tasarımının da temelidir.

## BFT ile Nakamoto Konsensüsü (Blockchain) İlişkisi

Bitcoin'in **Proof-of-Work** (Nakamoto konsensüsü) da bir Byzantine hataya dayanma biçimidir, ama PBFT'den temelde farklıdır:

- **PBFT:** Kesin (deterministic) **finality** sağlar — bir işlem commit olduğunda kesinlikle geri alınamaz. Katılımcı kümesi bilinir (permissioned). `f < n/3` sınırına tabidir.
- **Nakamoto/PoW:** **Olasılıksal (probabilistic) finality** sağlar — bir blok gömüldükçe geri alınma olasılığı üstel olarak düşer ama teorik olarak asla tam sıfır olmaz. Katılım açıktır (permissionless). Güvenlik, dürüst düğümlerin **hesaplama gücünün** çoğunluğuna (%51) dayanır, düğüm sayısına değil.

Bu ayrım "hangisi daha iyi" değil, farklı hata modeli ve ortam varsayımlarının farklı çözümleridir. Sybil saldırısına (bir saldırganın binlerce sahte kimlik yaratması) açık ortamda PoW/PoS gerekir; kimliklerin bilindiği kurumsal ortamda PBFT daha verimlidir.

## Doğru Kullanım ve Yaygın Tuzaklar

### Doğru Kullanım İlkeleri

- **Hata modelini bilinçli seçin.** Sisteminiz güvenilir bir veri merkezinde, tek bir kurumun kontrolündeyse ve düğümler yalnızca çökebiliyorsa, Raft/Paxos gibi crash-tolerant bir çözüm yeterlidir. BFT'nin O(n²) maliyetini gereksiz yere ödemeyin.
- **BFT'yi gerçekten güvensiz veya kritik ortamlar için saklayın.** Katılımcıların birbirine güvenmediği (blockchain) veya keyfi donanım arızasının felaketle sonuçlanacağı (aviyonik) durumlarda BFT gereklidir.
- **`3f + 1` bütçesini net planlayın.** İki düğüm hatasına dayanmak istiyorsanız 7 replika kurmanız gerekir. Kaynak planlamasını buna göre yapın.
- **Safety ve liveness'ı ayırt edin.** İyi tasarlanmış bir BFT protokolü, ağ bölünmesinde (partition) ilerlemeyi durdurur ama **yanlış sonuç üretmez**. Yani şüpheye düştüğünde durur; sessizce bozulmaz.

### Yaygın Hatalar ve Tuzaklar

- **"Byzantine olması olası değil" varsayımı.** Byzantine hata her zaman kötü niyetli saldırgan demek değildir. Bozuk bir RAM, hatalı bir firmware, bir bit flip veya yarı çalışan bir disk de bir düğümün **keyfi yanlış** çıktı üretmesine yol açar. Crash-tolerant sistemler bu tür sessiz bozulmalara (silent corruption) karşı **kör**dür.
- **Kimlik doğrulamayı atlamak.** BFT protokolleri mesaj imzalarına (authentication) dayanır. İmza/MAC olmadan bir saldırgan mesajları taklit edebilir (spoofing) ve `3f + 1` garantisi çöker. İmzalama BFT'nin isteğe bağlı bir eklentisi değil, temel varsayımıdır.
- **Zaman aşımı ayarını hafife almak.** View-change'i tetikleyen timeout çok kısaysa, sağlıklı bir lider yavaş ağda haksız yere değiştirilir ve sistem sürekli view change'de kilitlenir (liveness kaybı). Çok uzunsa, gerçekten kötü bir lider uzun süre zarar verir. Adaptif (üstel artan) timeout yaygın çözümdür.
- **Determinizm ihlali.** State machine replication'ın çalışması için tüm replikaların aynı girdiye aynı çıktıyı vermesi gerekir. Kodda rastgele sayı, sistem saati veya iş parçacığı zamanlamasına (thread scheduling) bağımlılık varsa, dürüst replikalar bile farklı durumlara sapar ve protokol bunu Byzantine hata sanır. BFT üzerinde çalışan uygulama mantığı **tam deterministik** olmalıdır.
- **`f`'i çalışma zamanında aşmak.** Tüm garantiler `en fazla f düğüm bozuk` varsayımına dayanır. Aynı anda `f + 1` düğüm ele geçirilirse (örneğin hepsi aynı zafiyeti taşıyan aynı imajı çalıştırıyorsa — korelasyonlu hata), protokolün safety garantisi tümüyle çöker. Bu yüzden replikaların **çeşitlendirilmesi** (farklı işletim sistemi, farklı implementasyon) ideal ama pahalı bir savunmadır.
- **Byzantine ile crash-tolerant düğüm sayısını karıştırmak.** `2f + 1`, crash toleransı içindir; Byzantine için **kesinlikle `3f + 1`** gerekir. Bu ikisini karıştırmak, kâğıt üzerinde güvenli görünüp gerçekte saldırıya açık bir sistem üretir.

## Özet

Dağıtık sistemlerin sağlamlığı, hangi hata modeline göre tasarlandıklarıyla belirlenir. Fail-stop, crash (fail-silent), omission ve Byzantine, giderek genişleyen bir hiyerarşi oluşturur; Byzantine model bir düğümün yapabileceği her türlü keyfi/kötü niyetli davranışı kapsar. Byzantine hataya dayanmanın matematiksel bedeli `n ≥ 3f + 1`'dir ve bu, quorum kesişiminde en az bir dürüst düğüm bulunması zorunluluğundan doğar. PBFT, üç fazlı (pre-prepare / prepare / commit) yapısı ve view-change mekanizmasıyla bu problemi pratik hale getiren dönüm noktasıdır; prepare fazı view içi sıralamayı, commit fazı ise view'lar arası kalıcılığı garanti eder. Blockchain'in Nakamoto konsensüsü aynı problemi olasılıksal ve açık-katılımlı bir zeminde çözer. Doğru mühendislik, hata modelini bilinçle seçmek, `3f + 1` bütçesini planlamak, kimlik doğrulama ve determinizmi ihmal etmemek ve her şeyden önce `f` sınırının çalışma zamanında aşılmadığından emin olmaktır.
