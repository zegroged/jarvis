# Dağıtık Veritabanı Konsensüs ve Replikasyon Protokolleri (Raft/Paxos, Quorum, Split-Brain)

## Giriş: Neden Bu Konu Ayrı ve Merkezi

"Replikasyon/Sharding" ve "CAP Teoremi" başlıkları dağıtık sistemlerin *ne* yaptığını ve *hangi ödünleşimlerle* karşılaştığını anlatır. Ama bunların altında, "birden fazla makine bir olgu (fact) üzerinde nasıl anlaşır" sorusuna somut, matematiksel olarak kanıtlanmış cevaplar veren bir katman vardır: konsensüs algoritmaları. Bir dağıtık veritabanı mühendisi için CAP teoremini bilmek yeterli değildir; "leader nasıl seçilir", "bir yazma ne zaman güvenle onaylanır", "ağ bölünmesinde (network partition) sistem nasıl davranır", "iki düğüm kendini lider sanırsa ne olur" sorularının cevabı olmadan üretim sistemi tasarlanamaz, incelenemez, hata ayıklanamaz. Bu makale, mekanizmanın kendisine iner: Paxos ve Raft'ın çalışma mantığı, quorum aritmetiği, split-brain senaryoları ve CRDT'lerin konsensüsü nasıl by-pass ettiği.

## Konsensüs Problemi: Tam Olarak Ne Çözülüyor

Konsensüs problemi resmi olarak şöyle tanımlanır: N düğümden oluşan bir küme, her biri bir değer önerse (propose) bile, sonunda **tek bir değer** üzerinde anlaşmalıdır (agreement), önerilen değerlerden biri seçilmelidir (validity) ve karar veren her düğüm aynı değeri görmelidir (termination — arıza olmadığı sürece karar nihayetinde verilmelidir).

Neden zor? Çünkü dağıtık ortamda üç temel belirsizlik var:
- **Mesaj gecikmesi/kaybı**: Bir mesajın hiç gelmemesi mi, yoksa gecikmesi mi olduğunu ayırt edemezsiniz.
- **Düğüm çökmesi vs. yavaşlık**: Bir düğümden yanıt gelmiyorsa, o düğüm ölmüş mü yoksa sadece GC duraklaması mı yaşıyor, ayırt edilemez (bu, ünlü FLP imkânsızlık teoreminin özüdür: asenkron bir sistemde, tek bir düğüm arızası bile olsa, deterministik bir konsensüs algoritmasının sonlanacağı garanti edilemez).
- **Ağ bölünmesi (partition)**: Küme ikiye ayrılabilir; her iki taraf da kendi başına "çoğunluk" sanabilir.

Pratikte kullanılan Paxos ve Raft gibi algoritmalar FLP'yi "aşmaz", pratik varsayımlar ekleyerek (zaman aşımları, kısmi senkronizmi kabul etme) *çoğu zaman* sonlanan ama teorik olarak sonsuz gecikebilen çözümler sunar. Bunu bilmek önemli: "bu algoritma her zaman X ms'de karar verir" diye bir garanti yoktur; garanti edilen şey **güvenliktir (safety)** — asla yanlış/çelişkili bir karara varılmaz — **canlılık (liveness)** ise best-effort'tur.

## Paxos: Temel Mantık

Paxos, Leslie Lamport tarafından tanımlanan, kanıtlanmış doğru ilk pratik konsensüs protokolüdür. Temel (Basic Paxos) hâli tek bir değer üzerinde anlaşmayı hedefler ve üç rol tanımlar: **Proposer** (değer öneren), **Acceptor** (öneriyi kabul/red eden çoğunluk üyesi), **Learner** (sonucu öğrenen).

Çalışma mantığı iki fazlıdır:

**Faz 1 (Prepare/Promise)**: Proposer, tekil artan bir numara (n) ile "prepare(n)" isteği gönderir. Her acceptor, eğer daha önce n'den büyük bir numara görmemişse, "promise" yanıtı verir ve daha önce kabul ettiği en yüksek numaralı öneriyi (varsa) bildirir. Acceptor, bu promise'dan sonra n'den küçük numaralı hiçbir öneriyi kabul etmeyeceğine söz verir.

**Faz 2 (Accept)**: Proposer, çoğunluktan promise aldıysa, "accept(n, v)" gönderir — burada v, eğer acceptor'lardan biri önceden kabul edilmiş bir değer bildirdiyse **o değerdir** (proposer kendi değerini dayatamaz, en yüksek numaralı önceki kabulü devam ettirmek zorundadır — bu kural protokolün güvenliğinin temelidir). Acceptor'lar, hâlâ daha yüksek bir numara görmedilerse kabul eder. Çoğunluk kabul ederse değer "seçilmiş" (chosen) sayılır.

**Kök neden — neden bu iki faz gerekli**: Tek fazlı bir "en yüksek numara kazanır" yaklaşımı, iki proposer'ın eşzamanlı olarak farklı çoğunluklara farklı değerler yazdırmasına (split decision) izin verirdi. Faz 1'in "önceki kabulü öğren ve devam ettir" kuralı, bir değer bir kez çoğunluk tarafından kabul edildiyse, ondan sonraki her proposer'ın **aynı değeri** önermeye zorlanmasını sağlar — böylece iki farklı değerin aynı anda "seçilmiş" olması imkânsız hale gelir. Bu, Paxos'un safety kanıtının kalbidir.

**Multi-Paxos**: Basic Paxos her karar için iki round-trip gerektirir, bu pahalıdır. Pratikte bir düğüm "stabil lider" (distinguished proposer) olarak seçilir; lider sabitken Faz 1 atlanabilir (aynı numara aralığı önceden rezerve edilmiş sayılır) ve sadece Faz 2 çalıştırılır — bu da Raft'ın temelde yaptığı şeye çok benzer. Gerçek dünyada "Paxos" denince genelde Multi-Paxos kastedilir (Google Chubby, Spanner'ın parçaları vb.).

**Paxos'un pratikteki zorluğu**: Orijinal makale son derece soyut ve anlaşılması zordur (Lamport'un kendisi bunu "Paxos Made Simple" ile düzeltmeye çalışmıştır). Üyelik değişikliği (yeni düğüm ekleme/çıkarma — reconfiguration), log kompaksiyonu gibi pratik detaylar makalede net değildir; her üretim implementasyonu (Chubby, ZooKeeper'ın ZAB'ı, vb.) bunları kendi yorumuyla doldurmak zorunda kalmıştır. Bu belirsizlik, Raft'ın doğuş nedenidir.

## Raft: Anlaşılabilirlik Odaklı Tasarım

Raft (Diego Ongaro ve John Ousterhout, 2014), Paxos ile **eşdeğer güvenlik garantileri** sunar ama açıkça "anlaşılabilirlik" (understandability) hedefiyle tasarlanmıştır. Bunu üç alt probleme ayrıştırarak yapar: **leader election**, **log replication**, **safety**.

### Leader Election

Raft'ta her düğüm üç durumdan birindedir: **Follower**, **Candidate**, **Leader**. Zaman, **term** adı verilen artan tamsayılarla bölümlenir; her term'de en fazla bir lider olabilir (veya hiç olmayabilir).

Mekanizma: Follower'lar liderden periyodik "heartbeat" (boş AppendEntries RPC) bekler. Rastgele bir **election timeout** (tipik olarak 150-300ms aralığında rastgele) süresi içinde heartbeat gelmezse, follower kendini candidate ilan eder, term'i bir artırır, kendine oy verir ve diğer düğümlere RequestVote gönderir. Çoğunluk oy alırsa lider olur.

**Neden rastgele timeout**: Tüm follower'lar aynı anda timeout olursa hepsi aynı anda candidate olur, oylar bölünür (split vote), kimse çoğunluk alamaz, yeni bir seçim turu gerekir — bu tekrarlayabilir. Rastgele gecikme, genellikle bir düğümün diğerlerinden önce candidate olmasını sağlayarak split vote olasılığını pratikte düşürür. Bu, Raft'ın "anlaşılabilir ama kanıtlanabilir" yaklaşımının tipik bir örneğidir: zarif değil ama basit ve işliyor.

**Oy verme kısıtı (election safety'nin temeli)**: Bir düğüm, kendi log'u adayınkinden **en az güncel** değilse oy vermez (log karşılaştırması: son entry'nin term'i ve index'i kıyaslanır). Bu kural, log'u eksik olan bir düğümün lider seçilmesini engeller — çünkü lider seçildikten sonra kendi log'unu diğerlerine dayatır; eksik loglu bir lider committed veri kaybına yol açardı.

### Log Replication

Lider, client'tan gelen her komutu kendi log'una ekler, sonra tüm follower'lara paralel AppendEntries RPC'siyle gönderir. **Çoğunluk** (majority quorum) bu entry'yi log'una yazdığını onayladığında, lider entry'yi **committed** olarak işaretler ve state machine'e uygular, sonra client'a yanıt döner.

**Log Matching Property**: İki farklı log'da aynı index ve aynı term'e sahip bir entry varsa, o index'e kadar olan tüm önceki entry'ler de aynıdır. Bu özellik, AppendEntries'in "consistency check" mekanizmasıyla (her istek önceki entry'nin index+term'ini taşır, follower eşleşmezse reddeder) korunur ve lider follower'ların log'unu geriye doğru tarayarak (nextIndex azaltarak) tutarlı hale getirir.

**Kök neden — neden çoğunluk yeterli**: Committed bir entry'nin sonraki liderlerde de korunacağının garantisi şuna dayanır: bir entry çoğunlukta yazıldıysa, sonraki her lider seçimi de bir çoğunluğun oyunu gerektirir; iki çoğunluk kümesi N düğümlü bir sistemde **kesişmek zorundadır** (quorum kesişim ilkesi — aşağıda detaylandırılıyor). Yani yeni lider adayı olacak düğüm, committed entry'yi içeren düğümlerden en az biriyle kesişecek, dolayısıyla oy verme kısıtı sayesinde o entry'yi görmeyen biri lider olamayacaktır.

### Safety — Leader Completeness

Raft'ın can alıcı iddiası: bir entry belirli bir term'de committed olduysa, o entry sonraki tüm term'lerin liderlerinin log'unda bulunacaktır. Bu, yukarıdaki oy kısıtı + quorum kesişimin doğal sonucudur ve Raft makalesinde formel olarak (TLA+ ile de) kanıtlanmıştır.

**Önemli tuzak — "current term'den committed sayma" kuralı**: Raft'ta bir lider, **önceki** term'lerden kalma bir entry'yi salt çoğunluk kopyaladı diye commit edemez; entry'yi commit sayabilmesi için o entry'nin **kendi mevcut term'inde** bir entry ile birlikte çoğunlukta bulunması gerekir. Bu ince kural olmasa, nadir bir yeniden-lider-seçimi senaryosunda daha önce "çoğunlukta" gibi görünen ama aslında commit edilmemiş bir entry'nin üzerine yeni lider farklı bir entry yazıp onu committed hale getirebilir — bu bir güvenlik ihlali (committed verinin değişmesi) olurdu. Bu, Raft makalesinin en çok atlanan ama en kritik detaylarından biridir; implementasyon yaparken (veya bir implementasyonu incelerken) bu kuralın var olup olmadığı doğrudan doğruluk kanıtını etkiler.

## Quorum Aritmetiği: Okuma/Yazma Çoğunluğu

Konsensüsün pratikteki temel aracı **quorum**'dur: N düğümlü bir kümede, W (write quorum) ve R (read quorum) seçilirse, **W + R > N** koşulu sağlandığında her yazma kümesi ile her okuma kümesi en az bir düğümde kesişir — yani her okuma, en güncel yazmayı görmeyi garanti eder (strong consistency, "quorum consistency" olarak da anılır — Dynamo tarzı sistemlerde N/W/R parametreleri olarak açıkça ayarlanabilir).

Tipik seçimler:
- **W = N, R = 1**: Yazma pahalı (herkes onaylamalı), okuma ucuz ve her zaman güncel — ama tek düğüm arızasında yazma bloklanır.
- **W = 1, R = N**: Yazma hızlı, okuma pahalı — yazma dayanıklılığı düşük.
- **W = R = ⌈(N+1)/2⌉** (majority-majority, Raft/Paxos'un kullandığı): Dengeli, tek düğüm arızasına dayanıklı (N=3'te 1 arıza, N=5'te 2 arıza tolere edilir).

**Kök neden — neden çoğunluk (majority) özel**: Çoğunluk quorum'un en önemli özelliği, **herhangi iki çoğunluk kümesinin kesişmesidir** — bu matematiksel bir zorunluluktur (N düğümden iki alt küme her biri >N/2 ise, ikisinin boyut toplamı N'i aşar, dolayısıyla kesişmeleri gerekir — güvercin yuvası ilkesi). Bu kesişim garantisi olmadan (örneğin W=R=N/3 seçilseydi) iki farklı çoğunluk grubu birbirinden habersiz, çelişen kararlar alabilirdi — split-brain'in matematiksel kökeni tam olarak budur.

**Tuzak — quorum yeterli ama tek başına konsensüs değildir**: Sade quorum okuma/yazma (örn. klasik Dynamo modeli), **hangi değerin "kazanacağına"** dair bir sıralama/versiyon mekanizması olmadan çelişkileri çözemez (concurrent yazmalar, "last write wins" ya da vector clock gerektirir). Raft/Paxos quorum'u **sıralı log ve tekil lider** ile birleştirerek total order sağlar; salt N/W/R parametreleştirmesi bunu otomatik vermez. Bu, "quorum kullanıyoruz, o yüzden konsensüsümüz var" yanılgısının kaynağıdır — quorum gerekli ama tek başına yeterli değildir.

## Split-Brain: Kök Neden ve Senaryolar

Split-brain, bir kümenin ağ bölünmesi (partition) sonucu **birden fazla düğümün/grubun eşzamanlı olarak kendini yetkili (lider/primary) sanması** durumudur. Sonuç: her iki taraf da bağımsız yazma kabul eder, veriler çatallanır (diverge), birleştirilemeyen çelişkiler oluşur.

### Senaryo 1: Naif Lider-Takip Sistemlerinde (Konsensüs Olmadan)

Basit primary-replica sistemlerde (örn. eski nesil manuel failover'lı MySQL, ilkel Redis Sentinel kurulumları), bir "izleyici" (watchdog) süreç primary'ye ulaşamadığında yeni bir primary terfi ettirir. Eğer eski primary aslında **ölmemiş**, sadece ağdan izole olmuşsa (network partition), o eski primary hâlâ kendini primary sanarak yazma kabul etmeye devam eder. Şimdi iki primary var — klasik split-brain.

**Kök neden**: Bu sistemlerde "kim primary" kararı **tek taraflı gözlem** ile (bir izleyicinin "ulaşamıyorum" demesi) alınır, quorum tabanlı bir mutabakat değildir. Quorum olmadan, "X'e ulaşamıyorum" ile "X ölü" arasındaki fark asla kesin olarak ayırt edilemez (bu FLP'nin pratik yansımasıdır).

### Senaryo 2: Konsensüs Kümesinde Bile Yanlış Yapılandırma

Raft/Paxos gibi konsensüs tabanlı sistemler split-brain'i **quorum kesişimi** ile matematiksel olarak imkânsız hale getirir — **eğer** doğru yapılandırılmışsa. Ama şu hatalar hâlâ split-brain benzeri sorunlara yol açabilir:
- **Çift kümeleme (split cluster misconfiguration)**: Aynı veri kümesi için iki ayrı bağımsız Raft grubu yanlışlıkla ayağa kaldırılırsa (örn. yapılandırma hatasıyla iki farklı "cluster ID"), her biri kendi içinde tutarlıdır ama ikisi birbirinden habersiz farklı liderlere sahiptir — bu artık konsensüs hatası değil, operasyonel hatadır.
- **Even N (çift sayı düğüm)**: N=4 gibi çift sayılı kümelerde, bir 2-2 bölünme olursa **hiçbir taraf** çoğunluk sağlayamaz (bu split-brain değil, kilitlenmedir — güvenlik korunur ama liveness kaybedilir). Bu yüzden pratikte tek sayılı düğüm sayıları (3, 5, 7) tercih edilir: aynı dayanıklılığı daha az düğümle sağlar (N=4 ile N=5 aynı 1-2 arıza toleransını vermez; N=5, N=4'e göre ekstra düğüm pahasına ekstra tolerans katar).
- **Stale lider "lease" varsayımı**: Bazı sistemler performans için liderin "lease süresi boyunca ben hâlâ liderim" varsayımıyla quorum'a danışmadan okuma yapmasına izin verir (leader lease / lease-based reads). Eğer saat senkronizasyonu (clock drift) veya GC duraklaması lease süresini aşarsa, eski lider hâlâ "lease'im geçerli" sanırken yeni lider zaten seçilmiş olabilir — bu **stale read** riskidir, tam split-brain değildir ama aynı kök nedenden (zaman varsayımlarının ağ gerçekliğiyle uyuşmaması) gelir.

### Tespit ve Savunma

- **Fencing (fencing tokens)**: Her lider terfi olduğunda artan bir token/epoch numarası alır; alt sistemler (örn. paylaşılan depolama), eski token ile gelen isteği reddeder. Bu, "eski liderin fiziksel olarak yazmaya devam etmesini" engellemez ama **etkilerini** engeller — Martin Kleppmann'ın dağıtık kilitler üzerine yazılarında vurguladığı temel savunma budur.
- **STONITH (Shoot The Other Node In The Head)**: Geleneksel HA kümelerinde, şüpheli düğümü aktif olarak öldürme (güç kesme, ağdan izole etme) yoluyla split-brain'i fiziksel olarak imkânsızlaştırma.
- **Quorum tabanlı üyelik değişikliği**: Küme yeniden yapılandırması (üye ekleme/çıkarma) da quorum kurallarına tabi olmalı (Raft'ın joint consensus / single-server membership change mekanizmaları); aksi halde yapılandırma değişikliği sırasında geçici olarak iki farklı çoğunluk tanımı aktif olabilir — bu klasik bir "reconfiguration split-brain" kaynağıdır.
- **Gözlemlenebilirlik**: Term/epoch numarasının izlenmesi (metrik olarak), aynı anda birden fazla "lider" metriği görülüyorsa alarm — bu operasyonel split-brain tespitinin en pratik yoludur.

## CRDT: Konsensüsü Bypass Etme Stratejisi

CRDT (Conflict-free Replicated Data Type), farklı bir felsefeyle yaklaşır: **konsensüse hiç ihtiyaç duymadan** birden fazla düğümün bağımsız, eşzamanlı güncellemeler yapmasına izin verip, sonradan bu güncellemeleri **matematiksel olarak deterministik ve çakışmasız** biçimde birleştirmeyi (merge) garanti eder.

**Kök neden — nasıl çalışır**: CRDT'ler, birleştirme işleminin **komütatif, ilişkisel (associative) ve idempotent** olduğu veri yapıları/işlemler seçerek çalışır. Örnekler:
- **G-Counter (grow-only counter)**: Her düğüm kendi sayacını tutar, toplam değer tüm düğüm sayaçlarının toplamıdır; birleştirme = eleman-bazlı maksimum alma.
- **LWW-Register (last-write-wins)**: Her yazmaya bir zaman damgası eklenir, çakışmada en yüksek zaman damgası kazanır (basit ama zaman damgası çarpışması/clock skew riski taşır).
- **OR-Set (observed-remove set)**: Ekleme ve silmeyi, her elemente eşsiz bir etiket (tag) atayarak çakışmasız hale getirir (silme, yalnızca "görülmüş" etiketleri siler; yeni eklenen aynı elemanın farklı etiketi hayatta kalır).

**Ödünleşim**: CRDT'ler **AP** tarafında (CAP açısından) konumlanır — ağ bölünmesinde bile her düğüm yerel olarak yazmaya devam edebilir, birleştirme sonradan (eventually) gerçekleşir. Konsensüs/quorum tabanlı sistemler (Raft/Paxos) ise genellikle **CP** tarafındadır — tutarlılık için müsaitliği (bölünme sırasında yazma reddi) feda eder. CRDT, "hangi düğüm doğru" sorusunu hiç sormaz; onun yerine "hangi birleştirme fonksiyonu her zaman aynı sonuca yakınsar" sorusunu çözer. Bu, split-brain'i **önlemez** ama split-brain'in **zararsız hale gelmesini** sağlar — çünkü çakışan iki dal, birleştiğinde tanımlı ve tutarlı bir sonuca ulaşır (strong eventual consistency).

**Tuzak**: CRDT'ler her veri modeline uygulanamaz. Bankacılık bakiyesi gibi "negatife düşmemeli" türünden invariant'lar (kısıtlar) CRDT'lerle doğal olarak ifade edilemez, çünkü birleştirme fonksiyonunun komütatifliği genellikle böyle global kısıtları ihlal edebilir. CRDT, "her düğüm bağımsız karar verebilir ve birleşme her zaman anlamlıdır" varsayımının geçerli olduğu veri modellerinde (sayaçlar, set'ler, collaborative metin editörleri gibi) güçlüdür; genel amaçlı transactional tutarlılık gerektiren sistemlerde konsensüsün yerini tutmaz.

## Yaygın Hatalar ve En İyi Pratikler (Özet)

- **Hata**: "Quorum kullanıyoruz" demek ile "konsensüsümüz var" demek aynı şey sanılması — quorum, sıralı log/tekil lider olmadan tek başına total order garantisi vermez.
- **Hata**: Çift sayılı düğüm sayısı (4, 6) seçmek — ekstra maliyet, ekstra tolerans getirmez; tek sayı (3, 5, 7) tercih edilmeli.
- **Hata**: Lease/cache tabanlı "hızlı okuma" optimizasyonlarını saat senkronizasyonu garantisi olmadan kullanmak — clock drift veya GC duraklaması stale read'e yol açar.
- **En iyi pratik**: Üyelik değişikliğini (membership reconfiguration) de konsensüs protokolünün kendisi üzerinden, quorum kurallarına tabi şekilde yapmak; manuel/dıştan müdahaleyle üye eklemek/çıkarmak split-brain riski taşır.
- **En iyi pratik**: Fencing token'ları, sadece "kim lider" sorusunu değil, **alt sistemlere yazma erişimini** de bu token'a bağlı kılmak — liderlik değişince eski liderin fiziksel olarak susturulmasını beklemek yerine, etkilerini engellemek.
- **En iyi pratik**: Hangi tutarlılık modelinin (strong/CP ile Raft-Paxos, ya da eventual/AP ile CRDT) veri modeline uygun olduğuna, iş kısıtlarına (invariant'lara) bakarak karar vermek — "hepsi için tek çözüm" yoktur.

## Sonuç

Konsensüs algoritmaları, dağıtık veritabanlarının "birden fazla makine tek bir gerçek üzerinde nasıl anlaşır" sorusuna verdiği somut, kanıtlanabilir cevaptır. Paxos'un iki fazlı prepare/accept yapısı ve Raft'ın leader election + log replication ayrıştırması, aynı temel ilkeye (quorum kesişimi) dayanır ama anlaşılabilirlik ve pratik implementasyon kolaylığı açısından farklılaşır. Split-brain, bu quorum kesişim garantisinin (yanlış yapılandırma, çift sayılı düğüm, lease varsayımları yoluyla) bozulduğu her durumda ortaya çıkar; fencing ve doğru quorum tasarımı bunun karşı önlemidir. CRDT'ler ise farklı bir felsefeyle, konsensüsü tamamen atlayıp matematiksel birleştirme garantileriyle çakışmasızlık sağlar — ama her veri modeline uygulanamaz. Bir dağıtık sistem mühendisi için bu kavramları derinlemesine anlamak, "hangi veritabanı hangi tutarlılık garantisini nasıl sağlıyor" sorusunu yüzeysel pazarlama iddialarının ötesinde, mekanizma seviyesinde okuyabilmek demektir.
