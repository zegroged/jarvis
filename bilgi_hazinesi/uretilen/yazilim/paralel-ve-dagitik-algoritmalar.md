# Paralel ve Dağıtık Algoritmalar: Kilitsiz Veri Yapıları, Consensus (Paxos/Raft) ve MapReduce

## Giriş: Neden Ayrı Bir Algoritmik Alan?

Dağıtık sistemler ve tutarlılık modelleri çoğu yazılım tartışmasında "mimari" başlığı altında geçer. Ancak bu sistemlerin altında yatan **algoritmik çekirdek** ayrı bir disiplindir: birden çok iş parçacığının (thread) veya birden çok makinenin aynı veri üzerinde, birbirlerinin varlığından habersiz ama tutarlı biçimde çalışmasını sağlayan matematiksel garanti mekanizmaları.

Bu makale üç sütunu inceler:

1. **Lock-free / wait-free veri yapıları** — tek makine, çok çekirdek dünyası. `CAS` (Compare-And-Swap) tabanlı, kilit kullanmadan doğruluk garantisi.
2. **Consensus algoritmaları (Paxos, Raft)** — çok makine dünyası. Birbirine güvenmeyen ya da çökebilen düğümlerin tek bir değer üzerinde anlaşması.
3. **MapReduce modeli** — büyük veriyi paralel işleyen hesaplama soyutlaması.

Ortak tema şudur: **eşzamanlılık (concurrency) doğruluğu ücretsiz değildir.** Race condition, işlemlerin görünürlük sırası ve kısmi başarısızlık (partial failure), bu alanın ana düşmanlarıdır.

---

## Bölüm 1: Race Condition ve Bellek Modeli Temeli

### Tanım

**Race condition**, programın doğruluğunun iş parçacıklarının çalışma sırasına (thread scheduling) bağlı olduğu durumdur. Klasik örnek: iki thread aynı sayaç değişkenini `count++` ile artırır.

`count++` tek bir işlem gibi görünse de aslında üç adımdır:

```
1. read  R = count       (belleği oku)
2. add   R = R + 1        (artır)
3. write count = R        (belleğe yaz)
```

İki thread bu üç adımı iç içe (interleaved) çalıştırırsa:

```
Thread A: read R=5
Thread B: read R=5
Thread A: write count=6
Thread B: write count=6   -> iki artış oldu ama sonuç 6, olması gereken 7
```

Bu "kayıp güncelleme" (lost update) probleminin kökü, okuma-değiştir-yaz (read-modify-write) dizisinin **atomik olmamasıdır**.

### Kök Neden: Bellek Modeli ve Görünürlük

Modern işlemciler ve derleyiciler performans için işlemleri yeniden sıralar (reordering) ve değerleri çekirdek yerel önbelleklerinde (cache) tutar. Bir thread'in yazdığı değer, başka bir thread'e **anında görünmeyebilir**. Bu yüzden "memory model" (Java Memory Model, C++11 memory model gibi) kavramı vardır: hangi yazmaların hangi okumalara ne zaman görünür olacağını tanımlayan sözleşme.

İki temel kavram:

- **Atomiklik (atomicity):** İşlem ya tamamen olur ya hiç olmaz; yarısı görünmez.
- **Görünürlük (visibility):** Bir thread'in yaptığı değişikliğin diğer thread'ler tarafından ne zaman görülebileceği. `volatile`/`atomic` işaretleri ve bellek bariyerleri (memory barrier / fence) bunu düzenler.

Kilitler (lock/mutex) bu iki sorunu birlikte çözer: karşılıklı dışlama (mutual exclusion) sağlar ve serbest bırakılırken bellek bariyeri kurar. Ama kilidin bedeli vardır.

---

## Bölüm 2: Kilitsiz (Lock-Free) Veri Yapıları

### Kilitlerin Bedeli ve İlerleme Garantileri

Kilit kullanımı üç sorun getirir:

- **Contention (çekişme):** Çok thread aynı kilidi bekler; seri hale gelir.
- **Priority inversion:** Düşük öncelikli thread kilidi tutarken yüksek öncelikli thread bekler.
- **Deadlock / convoy:** Kilidi tutan thread uyutulur (preempted) veya çöker; herkes takılır.

İlerleme garantileri (progress guarantees) hiyerarşisi:

| Garanti | Anlamı |
|---|---|
| **Blocking (kilitli)** | Kilidi tutan durursa, hiçbir thread ilerleyemeyebilir. |
| **Lock-free** | Sistem bütününde **en az bir** thread sonlu adımda ilerler. Bireysel thread açlığa (starvation) düşebilir. |
| **Wait-free** | **Her** thread, diğerlerinden bağımsız olarak sonlu adımda tamamlanır. En güçlü, en zor garanti. |

Lock-free, bir thread'in duraklamasının (veya çökmesinin) diğerlerini engellemediği anlamına gelir. Bu, gerçek zamanlı sistemlerde ve yüksek çekişmeli sunucularda değerlidir.

### CAS: Yapı Taşı

Lock-free algoritmaların çoğu tek bir donanım ilkeline dayanır: **Compare-And-Swap (CAS)**. Semantiği (atomik olarak):

```
CAS(adres, beklenen, yeni):
    if *adres == beklenen:
        *adres = yeni
        return true      # başarılı
    else:
        return false     # başka biri değiştirmiş
```

CAS, "değer hâlâ benim gördüğüm değerse, güncelle; değilse dokunma" der. Bu tek atomik işlem, kilitsiz güncellemenin temelidir. Tipik kullanım bir **retry loop** (yeniden deneme döngüsü) içindedir:

```
def atomik_arttir(sayac):
    while True:
        eski = sayac.oku()
        yeni = eski + 1
        if CAS(sayac, eski, yeni):
            return yeni
        # CAS başarısızsa: başka thread araya girdi, baştan dene
```

Buradaki fikir: CAS başarısız olursa değeri kimse kaybetmez; sadece yeniden okunup tekrar denenir. Kilit yoktur, dolayısıyla tutulan bir kilit de yoktur.

### Örnek: Lock-Free Yığın (Treiber Stack)

Klasik lock-free yığının `push` işlemi:

```
def push(yigin, deger):
    yeni = Node(deger)
    while True:
        tepe = yigin.head          # mevcut tepeyi oku
        yeni.next = tepe           # yeni düğümü ona bağla
        if CAS(yigin.head, tepe, yeni):   # tepe hâlâ aynıysa değiştir
            return
        # değilse: başka biri push/pop yaptı, tekrar dene
```

`pop` benzer şekilde tepeyi okur, `head`i `tepe.next`e taşımayı CAS ile dener.

### Yaygın Tuzak: ABA Problemi

Lock-free kodun en meşhur hatası **ABA problemidir.** CAS yalnızca "değer aynı mı?" diye bakar; "arada değişip geri mi döndü?" diye bakmaz.

Senaryo:
1. Thread 1, `head = A` okur. Duraklatılır.
2. Thread 2: A'yı pop eder (`head = B`), sonra B'yi pop eder, sonra A'yı geri push eder. Artık `head = A` yine, ama liste yapısı değişmiş; belki A'nın işaret ettiği düğüm serbest bırakılmış.
3. Thread 1 uyanır, `CAS(head, A, ...)` yapar. Değer A olduğu için **başarılı olur** — oysa aradaki dünya değişmiştir. Sonuç: bozuk liste, serbest bırakılmış belleğe erişim.

**Çözümler:**
- **Versiyon etiketi (tagged pointer / ABA counter):** İşaretçiyle birlikte bir sayaç tutulur; her değişiklikte artar. CAS `(pointer, counter)` çiftini karşılaştırır. Değer geri dönse bile sayaç farklı olur.
- **Hazard pointers / epoch-based reclamation:** Bir düğümün başka thread tarafından hâlâ okunuyor olabileceğini işaretleyip, güvenli olana kadar belleği geri kazanmama (memory reclamation) teknikleri. Lock-free'de bellek yönetimi, algoritmanın kendisinden daha zordur.

### Yaygın Hatalar (Lock-Free)

- **"volatile ile çözerim" yanılgısı:** `volatile`/`atomic` görünürlük sağlar ama read-modify-write'ı atomik yapmaz. Sayaç için `atomic` okuma+yazma yetmez; atomik `fetch_add` veya CAS gerekir.
- **Retry loop'un canlılık sorunu:** Aşırı çekişmede thread'ler sürekli birbirinin CAS'ini bozup boşa döner (livelock benzeri). Lock-free "hızlı" demek değildir; düşük çekişmede kilitten yavaş bile olabilir.
- **Bellek geri kazanımını unutmak:** GC'li dillerde (Java, C#, Go) çöp toplayıcı ABA'nın bir kısmını maskeler; C/C++'ta bunu elle yönetmek gerekir ve buraya birçok bug girer.
- **Yanlış ölçüm:** Lock-free'yi doğru yazmak zordur; ölçmeden "daha hızlı olur" varsaymak yaygın hatadır. Çoğu iş yükünde iyi tasarlanmış bir mutex veya sharding daha basit ve yeterlidir.

---

## Bölüm 3: Dağıtık Consensus — Paxos ve Raft

Tek makineden çok makineye geçince yeni bir düşman çıkar: **kısmi başarısızlık (partial failure).** Bir düğüm çöker, ağ paketi kaybolur veya gecikir, mesajlar farklı sıralarda ulaşır. Yine de sistemin **tek bir gerçek** üzerinde anlaşması gerekir. Bu problem **consensus** olarak adlandırılır.

### Consensus Problemi ve FLP Sonucu

Consensus'un istenen özellikleri:
- **Agreement:** Hiçbir iki doğru düğüm farklı değer kararlaştırmaz.
- **Validity:** Kararlaştırılan değer, önerilmiş değerlerden biridir.
- **Termination:** Doğru düğümler eninde sonunda bir karara varır.

**FLP teoremi (Fischer-Lynch-Paterson)** şunu kanıtlar: Tam asenkron bir sistemde, tek bir düğüm bile çökebiliyorsa, **her zaman sonlanan** (termination garantili) deterministik bir consensus algoritması **imkânsızdır**. Pratik algoritmalar bu duvarı, "zamanlama varsayımları" (timeout, kısmi senkronluk) ekleyerek aşar: güvenlik (safety) her zaman korunur, canlılık (liveness) ise ağ yeterince stabil olduğunda sağlanır.

Bu ayrım kritiktir: **Paxos ve Raft asla yanlış cevap vermez (safety), ama ağ sürekli bozuksa ilerlemeyi durdurabilir (liveness).**

### Quorum Mantığı

Her iki algoritmanın da kalbi **çoğunluk (majority quorum)** fikridir. `N` düğümden oluşan bir kümede, herhangi iki çoğunluk kümesi **en az bir düğümde kesişir**. Bu kesişim, eski ve yeni kararların birbirinden habersiz oluşmasını engeller. `2f + 1` düğümle en fazla `f` çökmeye dayanılır (örneğin 5 düğüm, 2 çökmeye dayanır).

### Paxos

Paxos, ilk kanıtlanmış consensus algoritmasıdır. Rolleri:
- **Proposer:** Bir değer önerir.
- **Acceptor:** Önerileri oylar/kabul eder.
- **Learner:** Kararlaştırılan değeri öğrenir.

**Basitleştirilmiş iki fazlı akış (single-decree Paxos):**

**Faz 1 — Prepare (hazırlık):**
1. Proposer benzersiz, artan bir teklif numarası `n` seçer, tüm acceptor'lara `Prepare(n)` gönderir.
2. Bir acceptor `n`, daha önce gördüğü en büyük numaradan büyükse: söz verir ("bundan küçük hiçbir teklifi kabul etmeyeceğim") ve daha önce kabul ettiği bir değer varsa onu geri döner (`Promise`).

**Faz 2 — Accept (kabul):**
3. Proposer çoğunluktan Promise alırsa, `Accept(n, v)` gönderir. Kritik kural: eğer Promise'lerde daha önce kabul edilmiş bir değer geldiyse, proposer **kendi değerini değil o değeri** kullanmak zorundadır. Bu, bir değer bir kez seçilirse sonsuza dek korunmasını sağlar.
4. Acceptor'lar `n`den büyük bir söz vermediyse kabul eder. Çoğunluk kabul ederse değer **kararlaştırılmıştır (chosen)**.

Paxos doğrudur ama anlaşılması ve doğru implemente edilmesi zordur; ayrıca temel Paxos tek bir değer içindir. Ardışık kararlar için **Multi-Paxos** gerekir (bir lider seçip Faz 1'i tekrar tekrar atlayarak).

### Raft

Raft, Paxos ile **eşdeğer güvenlik** sunar ama açıkça **anlaşılabilirlik** hedefiyle tasarlanmıştır. Problemi üç alt parçaya böler:

**1. Lider seçimi (Leader Election):**
- Düğümler üç durumdadır: **Follower, Candidate, Leader.**
- Zaman **term** denen artan dönemlere bölünür. Her term'de en fazla bir lider olur.
- Bir follower, liderden belirli süre (election timeout, rastgeleleştirilmiş) mesaj almazsa **candidate** olur, term'i artırır, kendine oy verir ve diğerlerinden oy ister (`RequestVote`).
- Çoğunluk oyu alan candidate lider olur. Rastgele timeout'lar, iki candidate'in sürekli çakışmasını (split vote) engeller.

**2. Log çoğaltma (Log Replication):**
- Tüm istemci istekleri lidere gider. Lider, komutu kendi log'una ekler ve `AppendEntries` ile follower'lara gönderir.
- Bir log girişi **çoğunlukta** kopyalandığında **committed** sayılır; lider onu durum makinesine (state machine) uygular ve istemciye cevap verir.
- Lider, her follower'ın log'unu kendi log'una uyacak şekilde zorlar; tutarsız girişler üzerine yazılır.

**3. Güvenlik kısıtı (Safety):**
- Raft'ın en önemli kuralı: bir candidate, **ancak kendi log'u en az oy veren kadar güncelse** oy alabilir. Bu, committed olmuş bir girişin asla kaybolmamasını garanti eder (Leader Completeness).

Raft'ın gücü, tek liderli (strong leader) tasarımıyla akış diyagramının zihinsel olarak izlenebilir olmasıdır. etcd, Consul ve birçok modern dağıtık veri deposu Raft kullanır.

### Paxos vs Raft — Doğru Kullanım

- **Ortak nokta:** İkisi de çoğunluk quorum'una dayanır, `f` çökmeye `2f+1` düğümle dayanır, safety'yi asla feda etmez.
- **Fark:** Raft güçlü lider ve sıralı log varsayar (anlaşılırlık ve implementasyon kolaylığı). Paxos daha esnektir ama pratikte Multi-Paxos'a evrildiğinde o da lider kullanır.
- Her ikisi de **Byzantine hatalara karşı korumasızdır** — kötü niyetli/rastgele yanlış cevap veren düğümü varsaymazlar; sadece çökme/gecikme (crash-fail) modeli. Byzantine ortam için PBFT gibi farklı aile gerekir.

### Yaygın Hatalar (Consensus)

- **"Consensus latency'yi düşürür" yanılgısı:** Aksine; her yazma en az bir tur ağ gidiş-dönüşü (round trip) + disk kalıcılığı gerektirir. Consensus **tutarlılık için** kullanılır, hız için değil.
- **Split-brain:** Quorum kuralına uyulmazsa (örneğin çift sayıda düğüm veya yanlış konfigürasyon) iki ayrı lider oluşabilir. Bu, verinin çatallanmasıdır ve consensus'un tam önlemek istediği felakettir. Çözüm her zaman tek çoğunluk kuralına sadık kalmaktır.
- **Küme boyutunu yanlış seçmek:** Çift sayı (örneğin 4) düğüm, çökme toleransını artırmaz ama quorum'u zorlaştırır. Genelde 3 veya 5 tek sayı seçilir.
- **Timeout'ları yanlış ayarlamak:** Çok kısa election timeout, gereksiz lider seçimlerine (leader churn) yol açar; çok uzun, iyileşmeyi geciktirir.
- **Consensus'u her yere serpmek:** Her işlem consensus'tan geçmek zorunda değildir. Yalnızca gerçekten koordinasyon gereken durumlar (lider seçimi, konfigürasyon, kritik metadata) için kullanmak, ölçeklenebilirlik açısından doğrudur.

---

## Bölüm 4: MapReduce Hesaplama Modeli

### Tanım ve Motivasyon

**MapReduce**, çok büyük veriyi bir makine kümesinde paralel işlemek için bir **programlama modeli ve çalışma zamanı soyutlamasıdır.** Ana fikir: geliştirici sadece iki saf (pure) fonksiyon yazar; kümedeki paralelleştirme, veri dağıtımı, hata toleransı ve düğümler arası taşımayı çalışma zamanı (framework) halleder.

İki fonksiyon:

- **Map:** `(k1, v1) -> list(k2, v2)`. Her girdi parçasını bağımsız işler, ara anahtar-değer çiftleri üretir.
- **Reduce:** `(k2, list(v2)) -> list(v3)`. Aynı ara anahtara sahip tüm değerleri toplar, birleştirir.

Arada framework'ün yaptığı görünmez ama kritik adım **Shuffle & Sort**tur: aynı `k2` anahtarına sahip tüm değerleri aynı reducer'a taşır.

### Örnek: Kelime Sayımı (Word Count)

```
map(dokuman_adi, metin):
    for kelime in metin.split():
        emit(kelime, 1)

# Shuffle: aynı kelimenin tüm 1'leri aynı reducer'a gider

reduce(kelime, sayilar):
    emit(kelime, sum(sayilar))
```

Terabaytlarca metin, yüzlerce makinede paralel `map` edilir; her makine kendi parçasını işler. Sonra "the" kelimesinin tüm sayıları bir reducer'da toplanır. Geliştirici hiçbir thread, kilit veya ağ kodu yazmaz.

### Çalışma Mantığı ve Hata Toleransı

MapReduce'un asıl dehası **hata toleransındadır**. Yüzlerce ucuz makinede bir görevin çökmesi kuraldır, istisna değil.

- Girdi, parçalara (input split) bölünür; her map görevi bir parçayı işler.
- Bir map/reduce görevi (task) başarısız olursa, master onu **başka bir makinede yeniden çalıştırır.** Bu mümkündür çünkü map/reduce fonksiyonları **deterministik ve yan etkisizdir**; aynı girdi hep aynı çıktıyı verir.
- **Ara çıktı diske yazılır**; bir reducer çökerse, gerekli map çıktıları hâlâ okunabilir.
- **Straggler (yavaş görev) problemi:** Bir makine yavaşlarsa tüm iş beklemez; master aynı görevi paralel olarak başka makinede de başlatır (**speculative execution / backup task**), ilk biteni kullanır.

### Doğru Kullanım ve Sınırlar

MapReduce **için uygun** işler:
- Tek geçişli, embarrassingly parallel toplu işleme (batch): log analizi, indeks kurma, ETL, toplu istatistik.
- Veri map aşamasında bağımsızca parçalanabiliyorsa.

MapReduce **için uygun olmayan** işler:
- **İteratif algoritmalar** (makine öğrenmesi, graf algoritmaları): her iterasyon ara sonucu diske yazıp okur; çok yavaştır. Spark gibi bellek-içi (in-memory) motorlar tam bu boşluğu doldurmak için doğdu.
- **Düşük gecikmeli / gerçek zamanlı** sorgular: MapReduce toplu (batch) doğası gereği saniyeler-dakikalar mertebesindedir, milisaniye değil.
- **Çok küçük veri:** Kurulum/koordinasyon maliyeti (job overhead) faydadan büyük olur.

### Yaygın Hatalar (MapReduce)

- **Data skew (veri çarpıklığı):** Bir anahtar (örneğin "the", veya bir "hot" müşteri) aşırı fazla değere sahipse, o reducer diğerleri bitmişken hâlâ çalışır. İş bir tek reducer'a kilitlenir. Çözüm: combiner kullanmak, anahtarı bölmek (salting), ya da özel partitioner.
- **Combiner'ı reducer sanmak:** Combiner (map tarafında yerel ön-toplama) yalnızca **birleştirilebilir/değişmeli (associative & commutative)** işlemler için doğrudur. Ortalama gibi işlemlerde combiner'ı reducer ile aynı yazmak yanlış sonuç verir.
- **Map/Reduce içinde yan etki (side effect):** Global değişkene yazmak, dış servise doğrudan yazmak — görev yeniden çalıştırıldığında (retry) çift işlem yapılır. Fonksiyonların idempotent ve saf olması şarttır.
- **Aşırı reducer sayısı sanmak = daha hızlı:** Çok fazla reducer, çok fazla küçük çıktı dosyası ve shuffle yükü demektir. Reducer sayısı veri ve küme boyutuna göre ayarlanmalıdır.

---

## Bölüm 5: Üç Alanı Bağlayan Ortak İlkeler

Bu üç konu yüzeyde farklı görünse de aynı derin ilkeleri paylaşır:

- **Atomiklik ve görünürlük her ölçekte vardır.** Tek makinede CAS ile, kümede quorum ile sağlanır. İkisi de "bir işlemin ya tam görünür ya hiç görünmemesi" fikridir.
- **İlerleme garantileri bir spektrumdur.** Lock-free/wait-free (tek makine) ile safety/liveness ayrımı (consensus) aynı düşünce ailesidir: kötü durumda ne garanti edilir, ne edilmez?
- **Kısmi başarısızlığı varsaymak zorunludur.** Lock-free'de bir thread'in duraklaması, consensus'ta bir düğümün çökmesi, MapReduce'ta bir görevin ölmesi — hepsi "bir bileşen durursa sistem doğru kalmalı" ilkesinin farklı yüzleridir.
- **Determinizm ve idempotentlik altın kuraldır.** MapReduce görevlerinin yan etkisiz olması, consensus log'unun aynı sırayla uygulanınca aynı state'i vermesi, lock-free retry'ın güvenle tekrarlanabilmesi — hepsi "yeniden çalıştırılabilirlik" üzerine kuruludur.

### Tespit ve Savunma Perspektifi

Bu mekanizmaları anlamanın pratik değeri, **hataları teşhis edebilmektir:**

- **Race condition tespiti:** ThreadSanitizer (TSan), Helgrind gibi dinamik analiz araçları, veri yarışlarını çalışma zamanında yakalar. Bir bug'ın "bazen" olması ve yükte artması race condition'ın klasik imzasıdır.
- **Consensus sağlığı:** Sürekli lider değişimi (leader election churn), artan commit gecikmesi, quorum kaybı uyarıları izlenmelidir. Split-brain'i erken yakalamak için düğüm sayısı ve ağ bölünmesi (partition) senaryoları test edilmelidir (örneğin Jepsen tarzı hata enjeksiyonu).
- **Dağıtık iş sağlığı:** MapReduce/Spark işlerinde straggler ve skew, tamamlanma sürelerinin görev bazında dağılımına bakılarak tespit edilir; tek bir görevin diğerlerinin 10 katı sürmesi skew işaretidir.

## Sonuç

Paralel ve dağıtık algoritmalar, "aynı anda birden fazla şey olurken doğruluğu korumak" problemine verilen matematiksel cevaplardır. **CAS ve lock-free yapılar** tek makinede kilitsiz güvenlik sunar (ama ABA ve bellek yönetimi tuzaklarıyla). **Paxos ve Raft** çok makinede, çökmelere rağmen tek gerçek üzerinde anlaşmayı garanti eder (safety'yi asla feda etmeden, liveness'i ağ stabilitesine bağlayarak). **MapReduce** büyük ölçekli paralel işlemeyi, geliştiriciden karmaşıklığı gizleyen iki saf fonksiyona indirger. Üçünün de altında yatan disiplin aynıdır: kısmi başarısızlığı varsaymak, atomiklik ve görünürlüğü açıkça yönetmek, ve determinizmi bir güvenlik ağı olarak kullanmak.
