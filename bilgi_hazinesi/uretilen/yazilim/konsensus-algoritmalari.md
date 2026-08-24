# Konsensüs Algoritmaları: Raft, Paxos, Multi-Paxos ve EPaxos

## Giriş: "Dağıtık Sistemler" Neden Yetmez

"Dağıtık Sistemler" başlığı altında CAP teoremi, tutarlılık modelleri, replikasyon gibi konular genel çerçeveyi çizer ama somut soruyu cevaplamaz: **birden fazla makine, aynı değerin ne olduğu konusunda nasıl anlaşır, özellikle bir kısmı çökerken veya ağ bölünürken?** Bu soru "consensus problemi" olarak adlandırılır ve çözümü için Paxos ailesi ve Raft gibi somut protokoller vardır. Bir mühendis olarak bu protokollerin iç mekanizmasını (lider seçimi, log replikasyonu, quorum matematiği, üyelik değişikliği) bilmeden "dağıtık sistem tasarladım" demek, kilit mekanizmasını bilmeden "eş zamanlı kod yazdım" demeye benzer: yüzeyde çalışır, yük altında ve arızada çözülür.

Bu makale, savunma/tasarım gözüyle bu mekanizmaları derinlemesine ele alıyor: neden var olduklarını, nasıl çalıştıklarını, nerede yanlış kullanıldıklarını ve gerçek sistemlerde (etcd, ZooKeeper, CockroachDB, Kafka'nın KRaft'i vb.) nasıl karşımıza çıktıklarını.

## Consensus Problemi: Tam Olarak Ne Çözülür

Consensus (konsensüs/uzlaşı) problemi, N adet sürecin (node), bazıları çökse veya mesajlar gecikse bile, tek bir değerde anlaşmasını sağlar. Formal olarak bir consensus protokolü şu özellikleri sağlamalıdır:

- **Agreement (uzlaşı)**: Hiçbir iki doğru node farklı bir değer üzerinde karar kılmaz.
- **Validity (geçerlilik)**: Karar verilen değer, bir node tarafından önerilmiş olmalıdır (rastgele uydurulmuş olamaz).
- **Termination (sonlanma)**: Her doğru node eninde sonunda bir karara varır (liveness özelliği).
- **Integrity**: Bir node en fazla bir kez karar verir ve kararını değiştirmez.

Buradaki kritik zorluk FLP imkansızlık teoreminden gelir (Fischer, Lynch, Paterson, 1985): **tamamen asenkron bir sistemde, tek bir node bile arızalanabiliyorsa, hem safety (güvenlik) hem de liveness (canlılık) garantisi veren deterministik bir consensus algoritması YOKTUR.** Bu, "consensus imkansız" demek değildir; pratikte ağın çoğu zaman senkron davrandığı (mesajlar makul sürede ulaşır) varsayımıyla çalışılır. Raft ve Paxos, FLP'yi "asenkron dünyada safety'den asla ödün vermeyerek, ama liveness'i best-effort timeout/randomization ile sağlayarak" aşarlar. Bu, KÖK NEDEN'dir: neden lider seçiminde random timeout kullanılır, neden bir protokol "sonsuza kadar takılabilir" (teorik olarak) ama pratikte takılmaz -- çünkü tasarım bilinçli olarak safety'i garanti eder, liveness'i olasılıksal/pratik garanti eder.

## Neden Çoğunluk (Quorum) Mantığı Şart

Hem Paxos hem Raft'in kalbinde **quorum (çoğunluk)** vardır: N node'dan oluşan bir kümede karar almak için en az `floor(N/2)+1` node'un onayı gerekir.

**Neden çoğunluk?** İki farklı quorum'un (örneğin iki farklı oylama turunda toplanan iki grup) mutlaka kesişimi olmasını garanti eder. N=5 ise quorum=3'tür; iki farklı 3'lük grup 5 elemanlı bir kümede en az 1 ortak elemana sahip olmak ZORUNDADIR (pigeonhole ilkesi: 3+3=6 > 5). Bu kesişen node, "eski kararı" yeni oylamaya taşır ve çelişkili iki farklı değerin aynı zaman diliminde onaylanmasını imkansız kılar. Bu yüzden consensus algoritmalarının güvenliği, esasen bir **kesişim garantisi** üzerine kuruludur; sihirli bir şey değil, kombinatorik bir zorunluluktur.

**Quorum matematiği ve fault tolerance**: N node ile `f = floor((N-1)/2)` node arızasına dayanabilirsiniz (crash-fault, Bizans değil). Yani:
- N=3 → f=1 (1 node kaybını tolere eder, quorum=2)
- N=5 → f=2 (2 node kaybını tolere eder, quorum=3)
- N=4 → f=1 (asimetrik: 4 node ile de sadece 1 kayıp tolere edilir, quorum=3; çift sayıda node kullanmak ek dayanıklılık sağlamadan sadece maliyet ekler)

**Yaygın tuzak**: "Daha fazla node = daha güvenli" varsayımı yanlış genellenir. N'i artırmak fault tolerance'i artırır ama **yazma gecikmesini de artırır** (çoğunluktan onay beklemek gerekir) ve N çift olduğunda israf vardır. Pratikte 3 veya 5 node çoğu sistemde (etcd, ZooKeeper) tercih edilir; 7 node yüksek-güvenlik senaryoları dışında nadirdir çünkü her yazma işlemi daha fazla node'un onayını beklemek zorunda kalır.

## Paxos: Temel Protokol

Paxos (Leslie Lamport, 1989/1998) consensus'un akademik temel taşıdır. Üç rol vardır: **Proposer** (değer önerir), **Acceptor** (oy verir), **Learner** (sonucu öğrenir). Tek bir "slot" (bir karar) için **iki fazlı** çalışır:

**Faz 1 (Prepare/Promise)**: Proposer, benzersiz ve artan bir "proposal number" (n) ile Acceptor'lara "Prepare(n)" gönderir. Bir Acceptor, daha önce gördüğü en yüksek numaradan büyükse kabul eder ve "Promise(n)" döner -- eğer daha önce bir değer kabul ettiyse onu da bildirir. Acceptor artık n'den küçük numaralı hiçbir teklifi kabul etmeyeceğine söz vermiştir.

**Faz 2 (Accept)**: Proposer, çoğunluktan Promise aldıysa, "Accept(n, v)" gönderir; burada v, eğer Promise yanıtlarında daha önceden kabul edilmiş bir değer varsa **o değer** (proposer kendi değerini değil, gördüğü en yüksek numaralı önceki değeri seçmek ZORUNDADIR), yoksa kendi önerdiği değerdir. Çoğunluk Accept'i kabul ederse değer karara bağlanmış olur.

**Neden bu iki faz gerekli**: Faz 1'in amacı, "gelecekte kimse benim onayımı görmeden farklı bir değer karara bağlayamaz" garantisini almak. Faz 2'nin proposer'in "görülen en yüksek numaralı değeri tekrar önermesi" kuralı ise, **iki farklı proposer'in aynı anda farklı değerlerle yarış yapıp birbirini engellemesi** (dueling proposers / livelock) durumunda bile safety'nin (agreement) asla bozulmamasını sağlar -- bozulan sadece liveness olur (ilerleme yavaşlar), güvenlik değil. Bu ayrım -- safety hiçbir zaman feda edilmez, liveness geçici olarak feda edilebilir -- tüm ailenin felsefesidir.

**Basic Paxos'un pratik sorunu**: Her karar (her log kaydı, her "slot") için bağımsız olarak iki fazı baştan çalıştırmak ağır bir maliyettir -- her yazma işlemi için en az iki round-trip (Prepare+Accept) gerekir. Bu yüzden gerçek sistemlerde "Basic Paxos" değil, **Multi-Paxos** kullanılır.

## Multi-Paxos: Optimizasyon Neden ve Nasıl

Multi-Paxos'un iç görüsü şudur: eğer bir proposer ardışık birden fazla slot için "stabil lider" olacaksa, Faz 1'i (Prepare/Promise) **her slot için değil, bir kez** yapabilir -- "ben N numarasından sonraki TÜM slotlar için lider olmak istiyorum" diyerek. Lider seçildikten sonra sonraki her karar için sadece Faz 2 (Accept) yeterli olur; bu da tek round-trip'e iner.

Bu, Raft'in temelidir aslında: **Raft, Multi-Paxos'un "anlaşılır ve uygulamaya yönelik" bir formalizasyonudur** diyebiliriz (Raft'in yazarları da makalede bunu açıkça söyler -- "understandability" tasarım hedefiydi). Multi-Paxos'ta lider seçimi ayrı, gevşek tanımlanmış bir mekanizmadır (protokol dışı bırakılır çoğu zaman); Raft ise lider seçimini protokolün **birinci sınıf, kesin tanımlı** bir parçası yapar.

**Yaygın tuzak**: İnsanlar "Paxos" derken genelde Multi-Paxos'u kastediyor ama akademik makalelerde "Paxos" Basic Paxos'u anlatır. Bu terminoloji karışıklığı, tasarım tartışmalarında yanlış anlamalara yol açar -- "Paxos kullanıyoruz" demek pratikte hiçbir şey söylemez; hangi varyant, hangi optimizasyonlarla önemlidir.

## Raft: Anlaşılırlık Odaklı Tasarım

Raft (Ongaro & Ousterhout, 2014), Paxos ile aynı garantileri sağlar ama problemi açıkça üç alt-probleme böler: **Leader Election**, **Log Replication**, **Safety** (+ genellikle dördüncü olarak Membership Changes eklenir).

### Leader Election

Her node üç durumdan birinde olur: **Follower**, **Candidate**, **Leader**. Sistem "term" (dönem) adı verilen monoton artan bir sayaçla bölümlenir; her term'de en fazla bir lider olabilir (veya hiç olmayabilir).

Mekanizma: Her follower rastgele bir **election timeout** (örneğin 150-300ms aralığında rastgele) bekler. Bu sürede lider'den heartbeat (AppendEntries, boş da olabilir) gelmezse, follower kendini Candidate yapar, term'i bir artırır, kendine oy verir ve diğerlerinden RequestVote ister. Çoğunluk oy alırsa lider olur.

**Neden randomize timeout -- KÖK NEDEN**: Eğer tüm node'lar aynı timeout'u kullansaydı, hepsi aynı anda Candidate olur, oylar bölünür (split vote), kimse çoğunluk alamaz, tekrar timeout, tekrar eş zamanlı deneme... Bu "livelock" senaryosudur. Randomizasyon, bir node'un diğerlerinden **önce** timeout'a uğramasını ve böylece "ilk oyu toplama avantajını" yakalamasını sağlar, split vote olasılığını pratikte ihmal edilebilir seviyeye indirir. Bu, dağıtık sistemlerde "simetriyi rastgelelikle kırma" prensibinin klasik bir örneğidir (aynı prensip exponential backoff, CSMA/CD gibi alanlarda da görülür).

**Oy verme kuralı (Election Restriction)**: Bir follower, sadece adayın log'u **en az kendi log'u kadar güncelse** oy verir (son log entry'nin term'i daha büyükse, veya term eşitse index daha büyük/eşitse). Bu kural, **committed bir entry'nin asla kaybolmamasını** garanti eder -- yeni lider, otomatik olarak tüm committed entry'leri içeren bir node olmak ZORUNDADIR, ayrıca bir "log recovery" fazına gerek kalmaz. Bu, Raft'in Paxos'a göre "anlaşılırlık" avantajının somut örneğidir: Multi-Paxos'ta lider değişiminde log'ları senkronize etmek için ekstra mekanizma gerekebilirken, Raft bunu seçim kuralıyla önceden çözer.

### Log Replication

Lider, client'tan gelen her komutu kendi log'una ekler, sonra tüm follower'lara paralel AppendEntries RPC'si gönderir. Çoğunluk bu entry'yi kendi log'una yazdığında (disk'e persist ettiğinde), lider entry'yi **committed** ilan eder ve state machine'e uygular; sonuç client'a dönülür.

**consistency check mekanizması**: Her AppendEntries, bir önceki entry'nin (prevLogIndex, prevLogTerm) bilgisini taşır. Follower, kendi log'unda o index/term uyuşmuyorsa reddeder. Lider, reddedilirse nextIndex'i geri saydırıp tekrar dener -- bu, follower'in log'unu liderinkiyle **tutarlı hale getirene kadar** geriye doğru arama yapan basit ama sağlam bir mekanizmadır.

**"Leader Completeness" kuralı**: Bir entry commit edildiyse, o entry'den sonraki tüm lider'lerin log'unda o entry mutlaka bulunur. Bu, quorum kesişimi + election restriction kombinasyonunun doğal sonucudur; ayrıca özel bir "recovery protokolü" gerektirmez.

**Önemli ince nokta -- neden lider sadece kendi term'indeki entry'leri sayarak commit eder**: Raft'ta bir lider, ÖNCEKİ bir term'e ait bir entry'yi, sadece o entry'nin çoğunlukta bulunmasına dayanarak commit edemez (doğrudan commit sayamaz); sadece **kendi mevcut term'inde** yazdığı bir entry çoğunluğa ulaştığında commit sayılır -- bu commit, transitif olarak önceki tüm entry'leri de commit eder. Bu kural olmadan, çok ince bir zamanlama senaryosunda (lider değişimi ile çakışan commit), daha sonra farklı bir lider o "commit edilmiş gibi görünen" entry'nin üzerine yazabilir ve committed bir değerin kaybolmasına yol açabilirdi. Bu detay, Raft makalesinin en subtle kısmıdır ve implementasyon hatalarının en sık kaynağı orada birikir.

### Üyelik Değişikliği (Membership Change / Joint Consensus)

Bir kümeye node eklemek/çıkarmak, quorum tanımını değiştirir. **Neden bu tehlikeli**: eğer tüm node'lar aynı anda eski konfigürasyondan yeniye geçmezse, bir süre boyunca **iki farklı çoğunluk** (eski config'in quorum'u ve yeni config'in quorum'u) aynı anda, birbirinden habersiz karar alabilir -- bu "split brain"in tam da consensus katmanındaki karşılığıdır.

Raft'in orijinal çözümü **joint consensus**: Geçiş, `C_old,new` adı verilen ara bir konfigürasyona geçerek yapılır; bu ara durumda **hem eski hem yeni konfigürasyonun ayrı ayrı çoğunluğu** gerekir (yani karar alabilmek için eski quorum VE yeni quorum'un ikisinden de onay lazım). Böylece geçiş süresince herhangi bir anda seçilen lider, iki konfigürasyondan birinde değil, **her ikisinde birden** çoğunluğa sahip olmak zorundadır -- bu da iki ayrık çoğunluk grubunun aynı anda farklı kararlar almasını matematiksel olarak imkansız kılar. C_old,new commit edildikten sonra C_new'e geçilir.

**Pratikte yaygın sadeleştirme -- tek node değişikliği (single-server changes)**: Joint consensus implementasyonu karmaşık olduğu için, çoğu gerçek sistem (etcd dahil) "her seferinde sadece bir node ekle/çıkar" kuralına dayanır. Matematiksel gerekçe: eski ve yeni konfigürasyonların quorum'ları arasında **tek node değişikliğinde her zaman kesişim garantisi** vardır (N ile N+1 veya N-1 arasında quorum'lar mutlaka örtüşür), bu yüzden ara joint-state'e hiç girmeden güvenli geçiş yapılabilir. Bu, "teoride doğru olan en genel çözüm" (joint consensus) ile "pratikte yeterli olan sadeleştirilmiş çözüm" (tek node) arasındaki klasik mühendislik değiş-tokuşudur.

**Yaygın hata**: Üyelik değişikliğini "sadece bir config dosyası güncellemesi" gibi görüp, bunu normal bir log entry dışında, özel senkronizasyon olmadan yapmaya çalışmak. Bu, geçici süre boyunca çift lider / çift quorum riski doğurur ve production'da veri tutarsızlığına yol açabilir.

## EPaxos: Leader'sız Consensus

Multi-Paxos ve Raft'in ortak zayıflığı: **tek lider darboğazı**. Tüm yazmalar lider üzerinden geçmek zorundadır; lider coğrafi olarak uzaksa (multi-datacenter) veya yük fazlaysa, bu gecikme ve throughput tavanı yaratır.

EPaxos (Egalitarian Paxos, Moraru/Andersen/Kaminsky, 2013), **her node'un herhangi bir komut için proposer olabildiği**, sabit bir lider'e ihtiyaç duymayan bir varyanttır. Temel fikir: iki komut, eğer üzerinde çalıştıkları veri kümesi (key/kayıt) **çakışmıyorsa**, sırayla değil paralel/bağımsız olarak commit edilebilir; sadece çakışan komutlar arasında bir sıra (dependency graph) belirlenmesi gerekir.

**Nasıl çalışır (yüksek seviye)**: Bir node, komutu aldığında doğrudan diğer node'lara "Pre-Accept" gönderir; her node kendi gördüğü, bu komutla çakışan diğer komutların bağımlılıklarını ekler ve yanıt verir. Eğer tüm yanıtlar aynı bağımlılık kümesinde uzlaşıyorsa (fast path), tek round-trip'te commit edilir. Uzlaşmıyorsa (bazı node'lar farklı çakışan komutlar görmüş), bir "Accept" fazı (Paxos'un Faz 2'sine benzer) devreye girer -- bu **slow path**tir.

**Neden önemli**: Coğrafi olarak dağıtık, çok-datacenter'lı sistemlerde (örneğin farklı bölgelerden gelen bağımsız yazmalar) EPaxos, hiçbir tek node'un darboğaz olmaması sayesinde önemli ölçüde daha düşük gecikme sunabilir -- her istek en yakın quorum'a gidebilir, hep aynı uzak lider'e gitmek zorunda değildir.

**Tuzak ve maliyet**: EPaxos'un karmaşıklığı çok daha yüksektir -- dependency graph'in doğru inşa edilmesi, çakışma tespiti (conflict detection) mantığının uygulamaya (application semantics) özel olması gerekir (hangi komutlar "çakışır" bilgisi, generic bir consensus katmanının değil, üzerindeki sistemin bilmesi gereken bir şeydir). Ayrıca graph tabanlı execution sırası çıkarma (SCC/topological sort benzeri işlemler) ek CPU maliyeti getirir. Bu yüzden EPaxos, akademik ilgiye rağmen Raft/Multi-Paxos kadar yaygın production benimsemesi görmedi; özellikle "her zaman aynı lider yeterlidir, gecikme önemli değil" senaryolarında ekstra karmaşıklığa değer bulunmuyor. Pratikte ilham aldığı fikirler (leaderless, conflict-based ordering) başka sistemlerde (örneğin bazı blockchain/ledger consensus tasarımlarında) yeniden ortaya çıkar.

## Fast Paxos (Kısa Not)

Fast Paxos (Lamport, 2005), belirli koşullar altında (çakışma olmadığında) proposer'in doğrudan Faz 2'ye atlayarak tek round-trip'te karar almasını sağlar -- ama bunun bedeli, çakışma olduğunda daha büyük bir quorum gerektirmesidir (basit çoğunluk yerine, çoğu zaman en az `3N/4`'e yakın bir "fast quorum"). EPaxos, kavramsal olarak Fast Paxos'un fikrini (çakışmayan işlemler için hızlı yol) genelleştirip lider'i tamamen kaldıran bir sonraki adım olarak görülebilir.

## Yaygın Tasarım Hataları ve Savunma Önerileri

**1. "Kendi consensus'unu yazmaya çalışmak"**: Bu alanın en tehlikeli tuzağı budur. Consensus algoritmaları, kağıt üzerinde basit görünür ama köşeleri (edge case'ler -- özellikle lider değişimi sırasındaki yarış durumları, network partition + rejoin senaryoları) son derece inceliklidir. Savunma: **kanıtlanmış, formal olarak doğrulanmış (TLA+ ile modellenmiş) implementasyonlar** (etcd/raft, Hashicorp Raft, ZooKeeper/ZAB) kullanın; özel bir sebep yoksa yeniden yazmayın.

**2. Quorum'u yanlış hesaplamak (split-brain riski)**: Özellikle "N/2" yerine "N/2+1" hesaplarken tam sayı bölme hatası (integer division) veya çift sayıda node ile yanlış güven. Savunma: fault tolerance hesaplarını test edin; production'da tek sayıda node (3, 5, 7) tercih edin.

**3. Membership değişikliğini "normal" bir operasyon gibi ele almak**: Yukarıda açıkladığımız gibi, config değişikliği sırasında özel dikkat gerekir. Savunma: kullandığınız kütüphanenin (etcd raft, vb.) resmi "add/remove member" API'sini kullanın, elle config dosyası değiştirmeyin.

**4. Consensus'u "her okuma için de gerekli" sanmak**: Çoğu sistemde okuma işlemleri, tutarlılık gereksinimine göre optimize edilebilir (lider'den lease-based read, ya da read index mekanizması, ya da stale read kabul edilebilirse follower'dan okuma). Her okumayı consensus round-trip'i ile yapmak gereksiz gecikme ve throughput kaybı yaratır. Savunma: hangi okumaların "linearizable" olması gerektiğini, hangilerinin "eventually consistent" yeterli olduğunu net ayırın.

**5. Network partition testi yapmamak**: Consensus protokolünün doğruluğu tam olarak partition/gecikme senaryolarında sınanır. Savunma: chaos engineering / Jepsen tarzı testler (network gecikmesi, partition, node crash simülasyonu) uygulamayı doğrulama sürecine dahil edin -- gerçek dünyada birçok "consensus kullanıyoruz" iddiası, Jepsen testlerinde tutarlılık ihlali bulunduğunda çökmüştür (birçok NoSQL veritabanının geçmişinde bu tür bulgular vardır; spesifik vaka detaylarını burada iddia etmiyorum, ama bu testlerin sektörde yaygın ve etkili olduğu bilinen bir gerçektir).

**6. "Consensus" ile "replikasyon" kavramlarını karıştırmak**: Basit primary-replica async replikasyon, consensus DEĞİLDİR -- lider çöktüğünde veri kaybı riski taşır (son yazılan, henüz replike olmamış veriler kaybolabilir). Consensus, bu riski quorum-tabanlı commit ile ortadan kaldırır (commit, sadece çoğunluğa ulaştığında ilan edilir). Savunma: "verimizi replike ediyoruz" ile "verimiz consensus ile korunuyor" arasındaki farkı mimari kararlarda açıkça belirtin -- bu iki yaklaşımın dayanıklılık garantileri tamamen farklıdır.

## Kapanış: Hangi Mercekten Bakmalı

Bu konuyu "Dağıtık Sistemler" başlığından ayırıp özel olarak ele almanın nedeni net: CAP teoremi ve tutarlılık modelleri size **ne** istediğinizi söylemenize yardım eder (strong consistency mi, eventual mi), ama consensus algoritmaları size **bunu nasıl, hangi somut mesajlaşma protokolü ile, hangi arızalara dayanıklı şekilde** gerçekleştireceğinizi anlatır. Bir sistem tasarımcısı olarak "Raft kullanıyoruz" demek yeterli değildir; leader election'in nasıl timeout aldığını, hangi entry'nin ne zaman commit sayıldığını, membership değişikliğinde ne olduğunu bilmiyorsanız, o sistemin arızalara gerçekten dayanıklı olup olmadığını değerlendiremezsiniz. Bu makalede aktarılan mekanizma bilgisi tam da bu değerlendirmeyi yapabilmeniz içindir -- saldırı talimatı değil, doğru soruları sorabilme ve production incident'larını doğru teşhis edebilme yeteneğidir.
