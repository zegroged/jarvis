# Gerçek Dağıtık Sistem Mimarisi Vaka Çalışmaları: Spanner, Dynamo, Cassandra, Kafka, HDFS/GFS

## Neden Bu Konu Önemlidir

CAP teoremi, replikasyon ve sharding gibi genel kavramları bilmek, bir binanın "yerçekimi vardır" ve "malzeme dayanımı önemlidir" gibi fizik ilkelerini bilmesine benzer: doğrudur ama bir bina inşa etmenizi sağlamaz. Gerçek mühendislik değeri, bu ilkelerin somut, üretimde çalışan sistemlerde HANGİ SOMUT TASARIM KARARLARINA dönüştüğünü görmekte saklıdır. Bu makale, endüstrinin en çok referans verdiği beş mimariyi (Dynamo, Spanner, Cassandra, Kafka, GFS/HDFS) mekanizma seviyesinde inceler: her birinin hangi problemi çözmek için var olduğunu, iç yapısını nasıl kurduğunu, hangi tasarım ödününü (trade-off) neden verdiğini ve bu ödünün sistemi üreten mühendislere hangi tuzakları bıraktı. Amaç ezber değil, "bu sistem neden böyle davranıyor" sorusuna kendi başınıza cevap üretebilecek bir zihinsel model kurmaktır.

Bu vaka çalışmalarını anlamak, sadece akademik merak değil, doğrudan pratik bir yetkinliktir: bugün yazdığınız herhangi bir dağıtık servis (bir mikroservis kümesi, bir cache katmanı, bir event pipeline), bu beş sistemin çözdüğü problemlerin küçük ölçekli bir versiyonuyla mutlaka karşılaşır. Vector clock'u anlamayan biri "neden aynı anahtarın iki farklı değeri var" sorusuna cevap veremez; ISR mantığını anlamayan biri Kafka'da veri kaybı yaşandığında nedenini teşhis edemez.

---

## 1. Amazon Dynamo: Müşteri Deneyimini Her Şeyin Üstüne Koyan Mimari

### Tanım ve Bağlam

Dynamo, Amazon'un 2007 tarihli makalesinde tanımladığı, alışveriş sepeti gibi yüksek kullanılabilirlik gerektiren iç hizmetler için geliştirilmiş bir key-value deposudur (not: Amazon'un bugünkü DynamoDB'si bu makaledeki fikirlerden ilham alır ama mimarisi zamanla değişti; burada anlatılan orijinal Dynamo tasarımıdır). Temel öncülü radikaldi: "müşteri sepetine ürün ekleyememesi, tutarsız bir sepet görmesinden daha kötüdür." Bu iş kararı, CAP teoreminde AP (Availability + Partition tolerance) tarafını seçmeyi zorunlu kıldı ve bütün mimari bu seçimin etrafında inşa edildi.

### Kök Neden / Çalışma Mantığı

**Consistent hashing ile veri dağıtımı:** Dynamo, verileri sunucular arasında dağıtmak için bir hash halkası (ring) kullanır. Her sunucu halka üzerinde bir veya daha fazla noktaya (virtual node) atanır; bir anahtar hash'lendiğinde, halka üzerinde saat yönünde ilerleyerek karşılaştığı ilk N sunucuya (N=replikasyon faktörü) yazılır. Bunun klasik `hash(key) % sunucu_sayisi` yöntemine üstünlüğü şudur: bir sunucu eklendiğinde veya çıkarıldığında, SADECE halka üzerindeki komşu aralıklar etkilenir; tüm veri kümesinin yeniden dağıtılması gerekmez. Virtual node kullanımı ise fiziksel sunucular arasındaki yük dengesizliğini (bazı sunuculara hash halkasında daha büyük bir aralık düşme ihtimalini) azaltır; her fiziksel makine halka üzerinde onlarca-yüzlerce sanal noktaya sahip olur, böylece istatistiksel olarak yük eşitlenir.

**Sloppy quorum ve hinted handoff:** Klasik quorum (R+W>N kuralı: okuma ve yazma çoğuluk kümeleri kesişmeli) katı bir kural uygulasaydı, bir replika düğümü geçici olarak erişilemez olduğunda yazma işlemi başarısız olurdu. Dynamo bunun yerine "sloppy quorum" kullanır: eğer halka üzerindeki doğal N sunucudan biri erişilemezse, yazma işlemi halka üzerinde bir sonraki sağlıklı sunucuya yönlendirilir; bu sunucu veriyi geçici olarak tutar ve orijinal sahibi normal sağlığına döndüğünde veriyi ona "hinted handoff" ile devreder (verinin yanında "bu aslında X sunucusuna ait" notu taşınır). Bu tasarım, kullanılabilirliği sert tutarlılık pahasına maksimize eder: yazma her zaman başarılı olur (neredeyse), ama okuma sırasında aynı anahtarın farklı replikalarda farklı versiyonları görülmesi mümkün hale gelir.

**Vector clock ile çatışma tespiti:** Sloppy quorum'un doğurduğu sonuç, aynı anahtara eş zamanlı/çakışan yazmaların farklı sunucularda farklı sonuçlar üretebilmesidir. Dynamo bunu basit bir timestamp ile çözmez (timestamp'ler saat senkronizasyon sorunlarından dolayı güvenilmezdir ve "hangi yazma diğerinden önce oldu" sorusuna nedensellik açısından yanlış cevap verebilir). Bunun yerine her değer, hangi sunucunun kaç kez o değeri güncellediğini tutan bir vector clock (örnek: `[(Sx,1),(Sy,2)]`) ile etiketlenir. İki versiyon karşılaştırıldığında üç durum olur: (1) biri diğerinin "atası" ise (tüm sayaçlar küçük eşit), eski versiyon güvenle atılır; (2) vector clock'lar birbirini kapsamıyorsa ("concurrent"/eş zamanlı), bu GERÇEK bir çatışmadır ve sistem karar veremez; (3) eşitlik. Concurrent durumda Dynamo çözümü uygulama katmanına bırakır: okuma isteminde tüm çakışan versiyonlar dönülür ("sibling"lar) ve istemci (örnek: sepet birleştirme mantığı) bunları uzlaştırır. Bu, "merkezi otorite yerine anlamlı birleştirme mantığı olan istemciye güven" felsefesinin somut kodudur.

**Merkle ağacı ile anti-entropy:** Replikalar zamanla birbirinden sapabilir (bir düğüm offline'ken yazma kaçırması gibi). Dynamo, iki replikanın veri kümesini karşılaştırmak için tüm veriyi tek tek karşılaştırmak yerine Merkle ağacı (hash ağacı) kullanır: her yaprak bir anahtar aralığının hash'i, üst düğümler alt düğümlerin hash'lerinin hash'idir. İki ağacın kök hash'i farklıysa, ağaç aşağı inilerek SADECE farklı olan dallar bulunur — bu, O(log n) karşılaştırma ile O(n) veri transferinden kaçınmayı sağlar.

### Doğru Kullanım, Tuzaklar ve En İyi Pratikler

- **Tuzak — "sibling patlaması":** Uygulama katmanı çakışan versiyonları düzgün birleştirmezse (last-write-wins gibi naif bir çözümle sessizce veri kaybederse veya hiç birleştirmezse), sibling sayısı zamanla artar ve okuma performansı ile depolama maliyeti patlar. Doğru pratik: iş mantığına özgü, semantik olarak doğru bir "reconciliation" (uzlaştırma) fonksiyonu yazmak (sepet örneğindeki gibi "union" mantığı).
- **En iyi pratik — N/R/W ayarlarını bilinçli seçmek:** N=3, R=2, W=2 gibi tipik ayarlar "quorum" sağlar (R+W>N) ama bu SERT tutarlılık garanti etmez, sadece "genellikle" en güncel veriyi okuma olasılığını artırır; ağ bölünmesi sırasında hala eski veri okunabilir.
- **Yaygın hata:** Vector clock boyutunun sınırsız büyüyeceğini varsaymak. Pratikte sistemler vector clock'u belli bir uzunlukta kırpar (pruning), bu da nadiren yanlış nedensellik çıkarımına yol açabilir — bu bilinen, kabul edilmiş bir mühendislik ödünüdür.

---

## 2. Google Spanner: Global Ölçekte Güçlü Tutarlılığı Mümkün Kılan Mimari

### Tanım ve Bağlam

Spanner, Google'ın dünya çapında dağıtılmış veri merkezlerinde çalışan, hem ACID işlemleri hem de SQL semantiği sunan, aynı zamanda dış gözlemciye göre harici tutarlılık (external consistency — linearizability'nin dağıtık/global versiyonu) garanti eden bir veritabanıdır. Buradaki asıl bilmece şudur: Dynamo'nun aksine Spanner CP tarafını seçer VE bunu kabul edilemez derecede yavaş olmadan yapar. Bunu mümkün kılan şey, çoğu dağıtık veritabanının sahip olmadığı özel bir donanım/API katmanıdır: **TrueTime**.

### Kök Neden / Çalışma Mantığı

**TrueTime — belirsizliği gizlemek yerine ölçmek:** Standart bir sunucu saati `now()` çağrıldığında tek bir sayı döner ve bu sayının gerçek zamana ne kadar yakın olduğu bilinmez (saat kayması/clock skew). TrueTime bunun yerine bir ARALIK döner: `TT.now() = [earliest, latest]`, yani "gerçek zaman kesinlikle bu iki değer arasındadır." Bu aralık, Google veri merkezlerine yerleştirilmiş GPS alıcıları ve atomik saatler aracılığıyla küçük tutulur (tipik olarak birkaç milisaniyeden küçük belirsizlik epsilon'u). Önemli olan felsefe değişikliği şudur: belirsizliği yok saymak yerine AÇIKÇA MODELLEMEK ve bu modele göre bekleyerek doğruluğu garanti etmek.

**Commit-wait ile external consistency:** Spanner bir işlemi commit ederken, işlemin zaman damgasını TrueTime aralığından alır ve commit'i tamamlamadan önce `TT.now().earliest`'in bu zaman damgasını geçmesini BEKLER (commit-wait). Bu bekleme sayesinde, T1 işlemi commit olduğunda gerçek dünya saatinin kesinlikle T1'in zaman damgasını geçtiği garanti edilir. Sonuç: eğer T1, T2 başlamadan önce (gerçek zamanda) commit olduysa, T2 kesinlikle T1'in etkisini görür — sistem global olarak, sanki tek bir makinaymış gibi, zaman sıralamasına sadık kalır. Bu, "iki veri merkezi arasında ışık hızı gecikmesi varken bile global sıra tutarlılığı" probleminin çözümüdür.

**Paxos ile replikasyon, 2PC ile cross-shard işlemler:** Spanner veriyi "tablet" adı verilen parçalara böler; her tablet grubu bir Paxos grubu olarak çoklu veri merkezinde replike edilir (genellikle 3-5 replika, çoğunluk oyu ile lider seçimi ve commit onayı). Tek bir Paxos grubu içindeki işlemler doğal olarak sıralıdır. Ama bir işlem birden fazla Paxos grubunu (farklı shard'ları) kapsıyorsa, Spanner bunların arasında iki-fazlı commit (2PC) çalıştırır; her grubun Paxos lideri 2PC'de bir katılımcı gibi davranır. Yani Spanner aslında "Paxos grupları üzerine kurulu 2PC" şeklinde katmanlanmış bir mimaridir — 2PC'nin klasik zayıflığı (koordinatör çöker ise katılımcıların kilitli kalması) Paxos'un kendisi çöker-dayanıklı olduğu için büyük ölçüde yumuşatılır.

### Doğru Kullanım, Tuzaklar ve En İyi Pratikler

- **Tuzak — TrueTime'i taklit etmeye çalışmak:** Özel donanım (atomik saat/GPS) olmadan yazılımla aynı garantiyi vermeye çalışmak (yalnızca NTP'ye güvenerek), epsilon değerini küçük tutamadığından commit-wait süresini pratik olmayacak kadar uzatır veya yanlış garanti verir. Bu, "Spanner'in sırrı Paxos değil, TrueTime'in donanım desteğidir" şeklinde özetlenebilir.
- **En iyi pratik — yazma gecikmesini kabul etmek:** Spanner güçlü tutarlılık için commit-wait'i (epsilon kadar, tipik olarak birkaç ms) bilinçli olarak ödeyen bir sistemdir; bu sistemi taklit eden mimariler tasarlarken "güçlü tutarlılık ücretsiz değildir, gecikme olarak fatura edilir" ilkesini unutmamak gerekir.
- **Yaygın hata:** Spanner'in "CAP teoremini kırdığını" düşünmek. Kırmıyor: ağ bölünmesi sırasında azınlıkta kalan Paxos replika grubu YAZMA/OKUMA yapamaz hale gelir (kullanılabilirlik feda edilir) — Spanner CP'dir, sadece C'yi çok yüksek doğrulukla ve makul gecikmeyle sunar.

---

## 3. Apache Cassandra: Dynamo Fikirlerinin Büyük Ölçekte Operasyonelleştirilmesi

### Tanım ve Bağlam

Cassandra, Facebook'ta başlayıp Apache'ye açılan, Dynamo'nun dağıtım/kullanılabilirlik modelini Google Bigtable'in veri modeliyle (sütun ailesi/wide-column) birleştiren bir veritabanıdır. "Dynamo + Bigtable" formülü literatürde sıklıkla tekrarlanır çünkü doğrudur: consistent hashing, gossip tabanlı üyelik, tunable consistency Dynamo'dan; SSTable/LSM-tree tabanlı depolama motoru Bigtable'dan gelir.

### Kök Neden / Çalışma Mantığı

**Gossip protokolü ile merkeziyetsiz üyelik yönetimi:** Cassandra kümesinde merkezi bir koordinatör/master yoktur. Her düğüm, saniyede bir kez rastgele seçilen birkaç başka düğümle "gossip" yapar: kendi bildiği küme durumunu (hangi düğümler yaşıyor, hangi versiyon bilgisine sahipler) paylaşır. Bu bilgi versiyonlanır (heartbeat state + application state, generation ve version sayaçlarıyla) böylece düğümler hangi bilginin daha yeni olduğunu anlayabilir. Zamanla (logaritmik yayılma hızıyla) tüm küme aynı görüşe (eventually consistent membership) yakınsar. Bunun önemi: tek bir koordinatör olmadığı için tek-nokta-hata (SPOF) yoktur, ama bunun bedeli "küme durumu hakkında herkesin aynı anda aynı bilgiye sahip olması" garantisinin olmamasıdır — yeni eklenen bir düğüm, kümenin geri kalanınca "görülmesi" için bir süre gerekir.

**Phi Accrual Failure Detector:** Cassandra bir düğümün "ölü" mü "canlı" mı olduğuna basit bir zaman aşımı (timeout) ile değil, İSTATİSTİKSEL bir şüpheli-derecesi (suspicion level, phi) hesaplayarak karar verir. Geçmişte alınan heartbeat'lerin varış zamanlarının dağılımına bakarak, "şu anda heartbeat almamak ne kadar anormal" sorusuna sürekli bir ölçek (0-1 sabit eşik yerine) ile cevap verir. Bu, ağdaki geçici gecikme dalgalanmalarına (jitter) karşı sabit-eşikli detektörlerden daha az yanlış-pozitif üretir.

**LSM-tree tabanlı yazma yolu:** Cassandra yazmaları önce bellekte bir yapıda (memtable) tutar ve durabilite için commit log'a (write-ahead log) ekler; memtable belli boyuta ulaşınca diske değişmez bir SSTable (Sorted String Table) olarak flush edilir. Bu tasarım yazmaları sıralı disk I/O'ya çevirir (rastgele yazma yerine ekleme/append), bu da dönen disklerde bile yüksek yazma verimi sağlar. Bedel: okuma sırasında bir anahtarın değeri birden fazla SSTable'a dağılmış olabilir, bu yüzden okuma potansiyel olarak birden fazla dosyaya bakmak zorunda kalır — bunu hafifletmek için Bloom filter (bir SSTable'in anahtarı kesinlikle içermediğini ucuza söyleyebilen olasılıksal veri yapısı) ve periyodik compaction (küçük SSTable'ları birleştirip eski/silinmiş verileri temizleme) kullanılır.

**Tunable consistency:** Cassandra, her okuma/yazma isteminde ayrı ayrı consistency level seçilmesine izin verir (ONE, QUORUM, ALL gibi). Bu, Dynamo'nun R/W parametrelerinin doğrudan operasyonel API'ye taşınmış halidir: uygulama geliştiricisi her sorguda hız-tutarlılık dengesini kendisi seçer.

### Doğru Kullanım, Tuzaklar ve En İyi Pratikler

- **Yaygın hata — "tombstone" birikimi:** Cassandra'da silme işlemi veriyi anında yok etmez, bir "tombstone" (mezar taşı) işareti yazar; gerçek temizlik compaction sırasında olur. Çok sık silme/güncelleme yapan iş yüklerinde (örnek: bir kuyruk gibi kullanmak) tombstone'lar birikip okuma performansını ciddi şekilde düşürebilir — bu Cassandra'nın en bilinen operasyonel tuzaklarından biridir; "Cassandra'yı kuyruk olarak kullanma" şeklinde özetlenen anti-pattern budur.
- **En iyi pratik — veri modelini sorguya göre tasarlamak:** Cassandra ilişkisel JOIN desteklemez; veri modeli "hangi sorgular çalışacak" sorusuna göre, gerekirse veri çoklanarak (denormalization) tasarlanmalıdır. İlişkisel alışkanlıklarla (önce normalize et, sonra sorgula) modelleme yapmak performans felaketidir.
- **Tuzak — yanlış consistency level seçimi:** QUORUM yazma + QUORUM okuma matematiksel olarak "güçlü tutarlılığı" garantiler gibi görünse de, hinted handoff ve read-repair gecikmeleri gibi operasyonel gerçeklikler nedeniyle pratikte hala kısa süreli tutarsızlıklar gözlemlenebilir; ONE/ONE kullanımı ekstra hız sağlar ama eski veri okuma riskini açıkça kabul eder.

---

## 4. Apache Kafka: Log-Merkezli Dağıtık Mesajlaşmanın İç Mimarisi

### Tanım ve Bağlam

Kafka, temelde basit ama derin bir soyutlama etrafında kurulmuştur: her şey bir "dağıtık, sıralı, değişmez (immutable) log"dur. Bir mesaj kuyruğu gibi değil, sonu olmayan bir append-only defter gibi davranır; tüketiciler bu defterden istedikleri hızda ve istedikleri konumdan (offset) okur. Bu basit soyutlama, hem yüksek verimlilik hem de yeniden-oynatma (replay) yeteneği sağlar.

### Kök Neden / Çalışma Mantığı

**Partition — paralellik biriminin temeli:** Bir Kafka topic'i partition'lara bölünür; her partition kendi başına sıralanmış, sadece-ekleme yapılan bir log dosyasıdır. Paralellik doğal olarak partition sayısıyla sınırlıdır: bir consumer group içindeki her partition'a en fazla bir tüketici atanabilir. Bu tasarım kararı, "global sıra" yerine "partition içinde sıra" garantisi verir — bir topic genelinde toplam sıralamayı garanti etmek isterseniz tek partition kullanmak zorundasınız (ama bu paralelliği sıfırlar). Bu, Kafka kullanan mühendislerin en çok kaçırdığı noktadır: partition anahtarı (key) seçimi, hem sıralama garantisini hem de yük dağılımını belirler.

**Sequential disk I/O ve zero-copy — hızın kaynağı:** Kafka'nın şaşırtıcı verimliliğinin sırrı karmaşık bir bellek-içi motor değil, tam tersi: işletim sistemine güvenmektir. Yazmalar diske sıralı olarak eklenir (rastgele erişimden kaçınarak dönen disklerde bile yüksek verim sağlar) ve işletim sisteminin sayfa önbelleğine (page cache) güvenilir — Kafka kendi bellek-içi önbellek katmanı yeniden icat etmez. Tüketim tarafında ise `sendfile` sistem çağrısı (zero-copy) kullanılarak veri, disk önbelleği -> kullanıcı alanı -> soket önbelleği şeklinde çift kopyalanmadan doğrudan disk önbelleği -> ağ soketine aktarılır. Bu iki karar birlikte, Kafka'nın neden "diske yazan ama hala son derece hızlı olan" bir sistem olduğunu açıklar.

**Replikasyon: lider, izleyici ve ISR (In-Sync Replicas):** Her partition'in bir lideri ve sıfır veya daha fazla izleyicisi (follower) vardır; tüm okuma/yazma lider üzerinden yapılır (izleyiciler sadece lideri kopyalar). ISR, lider ile "yeterince güncel" olan izleyicilerin kümesidir — bir izleyici lider ile senkron kalmakta çok geriye düşüyorsa (yapılandırılabilir bir eşikten fazla gecikiyorsa), ISR'dan çıkarılır. Bir yazma, sadece `acks=all` ayarlandığında VE ISR'daki TÜM replikalar onayladığında "commit edilmiş" sayılır. Bu, dayanıklılık (durability) garantisinin ISR boyutuna doğrudan bağlı olduğu anlamına gelir: eğer ISR küçük (örnek: sadece lider) kalırsa, lider çöktüğünde veri kaybı riski artar — bu, `min.insync.replicas` ayarının var olma nedenidir (ISR belli bir boyutun altına düşerse yazma reddedilir, kullanılabilirlik feda edilip dayanıklılık korunur).

**acks parametresi ile dayanıklılık-gecikme dengesi:** Kafka üreticileri (producer) için `acks=0` (onay bekleme, en hızlı en riskli), `acks=1` (sadece lider onaylasın yeterli, lider çöker ve henüz replike olmamışsa veri kaybedilebilir), `acks=all` (ISR'daki hepsi onaylasın, en dayanıklı en yavaş) seçenekleri sunar. Bu, Dynamo'nun R/W parametrelerinin mesajlaşma dünyasındaki karşılığıdır — aynı dağıtık sistemler teorisi (kaç kopyanın onaylaması yeterli) farklı bir kelime hazinesiyle tekrar karşımıza çıkar.

**Consumer group ve offset yönetimi:** Tüketiciler kendi okuma konumlarını (offset) Kafka'nın kendisinde özel bir topic'te (`__consumer_offsets`) saklar. Bu, "en az bir kez" (at-least-once) ya da doğru yapılandırmayla (idempotent producer + transactional semantics) "tam bir kez" (exactly-once) işleme garantisi kurmayı mümkün kılar — ama varsayılan davranış at-least-once'dır ve tüketici tarafının idempotent olması gerekir.

### Doğru Kullanım, Tuzaklar ve En İyi Pratikler

- **Yaygın hata — yanlış partition key seçimi:** Sabit veya düşük kardinaliteli bir anahtar (örnek: her zaman sabit bir değer) kullanmak tüm trafiği tek bir partition'a yığar ("hot partition"), paralelliği yok eder. Doğru pratik: yüksek kardinaliteli, iş mantığına uygun bir anahtar seçmek (örnek: kullanıcı ID) — ama bu da o anahtarla ilgili tüm olayların sırasını garanti eder, farklı anahtarlar arası sıra garanti etmez.
- **Tuzak — `acks=1` ile "dayanıklı" sandığı bir sistem kurmak:** Lider çöktüğü anda henüz replike olmamış en son mesajlar kaybolabilir; bu ürün gereksinimi finansal/kritik veri içeriyorsa `acks=all` + yeterli `min.insync.replicas` şarttır.
- **En iyi pratik — retention ile "replay" gücünü kullanmak:** Kafka'nın log'u tüketildikten sonra silinmez (retention süresi/boyutu doluncaya kadar tutulur); bu, aynı veriyi birden fazla farklı tüketici sisteminin (analytics, arama indexleme, cache güncelleme) BAĞIMSIZ hızlarda okuyabilmesini sağlar — klasik kuyruklarda (mesaj tüketilince silinir) bu mümkün değildir.

---

## 5. GFS/HDFS: Büyük Dosyaların Dağıtık Depolanmasının Temel Mimarisi

### Tanım ve Bağlam

Google File System (GFS, 2003 makalesi) ve onun açık kaynak türevi HDFS (Hadoop Distributed File System), çok büyük dosyaları (gigabayt-terabayt) binlerce ucuz sunucuya dağıtarak depolamak ve bunlar üzerinde yüksek verimli, sıralı (streaming) okuma/yazma yapmak için tasarlanmıştır. Kritik varsayım: donanım arızası İSTİSNA değil, NORMdur — binlerce disk/sunucudan oluşan bir kümede her gün bir şeyin bozulması beklenen bir durumdur, sistem bunun ETRAFINDA tasarlanmalıdır.

### Kök Neden / Çalışma Mantığı

**Master/NameNode - Chunkserver/DataNode ayrımı:** Mimari, metadata (dosya adı -> hangi blokların hangi sunucularda olduğu bilgisi) ile gerçek veriyi açıkça ayırır. Tek bir Master (GFS) / NameNode (HDFS) tüm metadata'yı bellekte tutar ve tüm istemcilerin ilk temas noktasıdır; gerçek veri blokları yüzlerce/binlerce Chunkserver (GFS) / DataNode (HDFS) üzerinde saklanır. İstemci önce Master'a "bu dosyanın blokları nerede" diye sorar, sonra veriyi DOĞRUDAN ilgili chunkserver'dan okur/yazar — Master veri transferine hiç karışmaz. Bu ayrım, Master'in darboğaz olmasını engeller (metadata trafiği veri trafiğinden kat kat küçüktür) ama aynı zamanda Master'i potansiyel tek-nokta-hata haline getirir; bu yüzden hem GFS hem HDFS'in modern versiyonlarında Master/NameNode için yüksek kullanılabilirlik (secondary/standby NameNode, checkpoint mekanizmaları) eklenmiştir.

**Büyük blok boyutu (64MB-128MB):** Geleneksel dosya sistemleri kilobyte mertebesinde blok kullanırken, GFS/HDFS bilinçli olarak çok büyük bloklar seçer. Nedeni doğrudan iş yüküne bağlıdır: sistem küçük rastgele okumalar için değil, büyük dosyaların BAŞTAN SONA sıralı taranması (batch analytics, MapReduce iş yükleri) için optimize edilmiştir. Büyük blok boyutu, metadata miktarını (Master'in bellekte tutması gereken blok-konum eşlemesi sayısını) drastik azaltır ve bir istemcinin aynı sunucuyla sürekli yeniden bağlantı kurması yerine uzun süreli, verimli sıralı transfer yapmasını sağlar. Bedel: küçük dosyalarla veya rastgele-erişim iş yükleriyle (örnek: bir OLTP veritabanı gibi kullanmaya çalışmak) bu mimari son derece verimsizdir.

**Replikasyon (tipik 3 kopya) ve rack-aware yerleşim:** Her blok varsayılan olarak 3 kopya halinde saklanır; yerleşim rastgele değildir — tipik strateji bir kopyayı yerel rack'te, diğerini farklı bir rack'te tutmaktır. Böylece hem (a) tek bir sunucu arızasına karşı hızlı kurtarma (yerel rack'teki kopyadan) hem de (b) TÜM BİR RACK'İN elektrik/ağ arızasına karşı dayanıklılık (farklı racktaki kopya sayesinde) sağlanır. Bu, "replika sayısı" kadar "replikaların FİZİKSEL olarak nereye konulduğu" sorusunun da kritik bir tasarım kararı olduğunu gösterir — aynı rack'e 3 kopya koymak, o rack'in güç kaynağı çöktüğünde tüm kopyaları aynı anda kaybetmek demektir.

**Tek yazıcı, çoklu okuyucu ve "append" merkezli yazma modeli:** GFS'in orijinal tasarımı, dosyanın ortasında rastgele güncelleme yerine sonuna EKLEME (record append) yapmayı birinci sınıf işlem olarak destekler — bu, çoklu istemcinin aynı dosyaya eş zamanlı, atomik olarak (en az bir kez garanti ile) log tarzı veri eklemesini optimize eder (örnek: dağıtık loglama, MapReduce ara çıktıları). Rastgele yazma desteklenir ama optimize edilmemiştir ve eş zamanlı rastgele yazmalarda tutarlılık garantisi zayıftır.

**Heartbeat ve re-replikasyon ile kendini onarma:** DataNode/Chunkserver'lar düzenli aralıklarla Master/NameNode'a "yaşıyorum" sinyali (heartbeat) gönderir. Bir sunucudan sinyal kesilirse, Master o sunucudaki tüm blokların replika sayısının eksildiğini varsayar ve otomatik olarak diğerlerinde bu blokların yeni kopyalarını oluşturur (re-replication) — sistem insan müdahalesi olmadan kendi dayanıklılık hedefine geri döner. Bu, "arıza normaldir" varsayımının doğrudan kodlanmış hali: sistem sürekli, arka planda kendini "3 kopya" invariant'ına geri getirmeye çalışır.

### Doğru Kullanım, Tuzaklar ve En İyi Pratikler

- **Yaygın hata — "küçük dosya problemi":** HDFS'e milyonlarca küçük dosya (KB mertebesinde) yazmak, NameNode'un bellekteki metadata tablosunu şişirir (her dosya/blok bellekte bir kayıt tutar) ve NameNode'u darboğaz/arıza noktası haline getirir. Doğru pratik: küçük dosyaları birleştirip (örnek: SequenceFile, Parquet gibi konteyner formatları) az sayıda büyük dosya olarak saklamak.
- **Tuzak — HDFS'i genel amaçlı/düşük gecikmeli depolama gibi kullanmak:** Yüksek verim (throughput) için tasarlanmış bir sistemdir, düşük gecikme (low latency) için değil; rastgele okuma/yazma ağırlıklı bir iş yükü (örnek: bir web uygulaması arka ucu) için doğru araç değildir.
- **En iyi pratik — rack topolojisini doğru bildirmek:** Rack-aware yerleşimin faydalı olması için küme yöneticisinin fiziksel rack topolojisini sisteme doğru tanımlamış olması şarttır; yanlış/eksik topoloji bilgisi, "farklı rackte" sanılan kopyaların aslında aynı güç/ağ hattına bağlı olmasına (dolayısıyla korelasyonlu arızaya karşı savunmasız kalmasına) yol açar.

---

## Ortak İplikler: Beş Mimariden Çıkan Genel Dersler

Bu beş sistemi yan yana koyduğumuzda, tekrar eden birkaç derin desen ortaya çıkar:

1. **Her sistem CAP üçgeninde bilinçli, iş-güdümlü bir nokta seçer.** Dynamo ve Cassandra müşteri deneyimi/kullanılabilirlik için AP'yi seçer; Spanner finansal/global tutarlılık için CP'yi seçer (özel donanımla gecikme maliyetini düşürerek). Hiçbir sistem "hepsini birden" almaz; soru her zaman "hangi hata modunda neyi feda ediyoruz" sorusudur.

2. **Metadata ile veri ayrımı tekrar eden bir ölçekleme deseni.** GFS/HDFS'in Master-Chunkserver ayrımı, Kafka'nın controller-broker ayrımı (ve Cassandra/Dynamo'nun gossip ile bu ayrımı tamamen ortadan kaldırma tercihi) aynı sorunun (küçük-ama-kritik kontrol bilgisini büyük veri hacminden ayırarak darboğazı önlemek) farklı çözümleridir.

3. **Failure detection her zaman olasılıksaldır, hiçbir zaman kesin değildir.** Bir düğümün "ölü" mü "yavaş mı" olduğunu ağ üzerinden kesin olarak ayırt etmek imkansızdır (bu, dağıtık sistemlerin temel bir teorik sınırıdır). Cassandra'nın phi accrual detector'u, Kafka'nın ISR eşik mekanizması, GFS'in heartbeat zaman aşımı hepsi bu belirsizliği YÖNETMEYE çalışan farklı istatistiksel/sezgisel yaklaşımlardır; hiçbiri "kesin doğru" değildir, hepsi yanlış-pozitif/yanlış-negatif dengesini ayarlar.

4. **Replikasyon miktarı kadar replikasyon YERLEŞİMİ önemlidir.** GFS'in rack-aware yerleşimi, Cassandra'nın "NetworkTopologyStrategy" ile veri merkezi/rack farkındalığı, hepsi aynı gerçeği vurgular: 3 kopyanız olması, bu 3 kopyanın BAĞIMSIZ arıza alanlarında olmadığı sürece sizi korelasyonlu arızadan korumaz.

Bu mimarileri inceleyen bir mühendis için en değerli alışkanlık, "bu sistem hangi iş yükünü birinci sınıf vatandaş olarak optimize etmiş, hangi durumu ikinci plana atmış" sorusunu her zaman sormaktır — çünkü hiçbir dağıtık sistem tasarımı bütün eksenlerde aynı anda en iyi olamaz; her biri, kendi yaratıldığı bağlamın somut kısıtlarının bir yansımasıdır.
