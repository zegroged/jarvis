# Yazılım Mühendisliği — Uzman Bilgi Tabanı (Cilt 1)

Bu belge yazılım mühendisliğinin çekirdeğini, kavramları birbirine bağlayarak
anlatır. Hedef: "nasıl" kadar "neden"i de vermek. Güvenlik cildiyle (01) kardeş;
çünkü güvenli yazılım, iyi yazılımın bir alt kümesidir — bu yüzden yer yer
güvenlik köprüleri kurulur.

---

## 1. Programlama Paradigmaları

Bir paradigma, problemi kodda ifade etme *biçimidir*. İyi mühendis birini
seçmez, birden fazlasını yerine göre kullanır.

- **Imperative / Procedural:** "Nasıl" — adım adım komut ve durum değişimi
  (C, klasik Python). Donanıma yakın, kontrol net.
- **Object-Oriented (OOP):** Veri + davranış nesnelerde kapsüllenir. Dört ilke:
  - **Encapsulation:** iç durumu gizle, arayüzle eriş.
  - **Abstraction:** karmaşıklığı sadeleştirilmiş arayüz ardında sakla.
  - **Inheritance:** ortak davranışı türet (dikkatli kullan — kompozisyon
    çoğu zaman kalıtımdan iyidir; "composition over inheritance").
  - **Polymorphism:** aynı arayüz, farklı davranış.
- **Functional (FP):** Saf fonksiyonlar (aynı girdi → aynı çıktı, yan etki yok),
  immutability, birinci sınıf fonksiyonlar, map/filter/reduce. Yan etkiyi
  kısıtlamak eşzamanlılığı ve test edilebilirliği kolaylaştırır (Haskell, Clojure;
  ama Python/JS/Rust'ta da FP kalıpları).
- **Declarative:** "Ne" istediğini söyle, "nasıl"ı motora bırak (SQL, HTML,
  Prolog, React'in bildirimsel UI'ı).

Modern diller çok paradigmalıdır. Ustalık: probleme uygun aracı seçmek —
durum-ağırlıklı domain'de OOP, veri dönüşümünde FP, sorguda declarative.

---

## 2. Veri Yapıları ve Algoritmalar

Bir programın performansı çoğu zaman *doğru veri yapısı seçimine* bağlıdır.
Karmaşıklık **Big-O** ile ifade edilir: girdi büyürken maliyetin nasıl büyüdüğü
(en kötü durum, sabitler atılır).

### 2.1. Karmaşıklık sezgisi
- O(1) sabit, O(log n) logaritmik (ikili arama), O(n) doğrusal, O(n log n) iyi
  sıralama, O(n²) iç içe döngü, O(2ⁿ)/O(n!) kombinatoryal (küçük n dışında
  pratik değil). "Ölçeklenecek mi?" sorusunun cevabı burada.
- **Amortized** analiz: tekil işlem bazen pahalı ama ortalama ucuz (dinamik
  dizinin yeniden boyutlanması → amortized O(1) ekleme).
- Zaman kadar **space complexity** de önemli (bellek/hız takası klasiktir).

### 2.2. Temel veri yapıları (ne zaman hangisi)
- **Array / dynamic array:** bitişik bellek, O(1) indeksli erişim, sonuna
  amortized O(1) ekleme, ortaya ekleme O(n). Cache-dostu.
- **Linked list:** O(1) ekle/çıkar (düğüm elde varsa) ama O(n) erişim, cache
  düşmanı. Pratikte sanıldığından az kullanılır.
- **Hash table (dict/map):** ortalama O(1) ekle/ara/sil; kötü hash veya çok
  çakışmada O(n)'e düşer. Sırasızdır (ya da ekleme sırası). En çok kullanılan
  yapı. Güvenlik notu: hash collision DoS (kullanıcı kontrollü anahtarlar) —
  randomized hashing ile azaltılır.
- **Set:** üyelik testi O(1); tekilleştirme.
- **Stack (LIFO) / Queue (FIFO):** çağrı yığını, BFS/DFS, iş kuyrukları.
- **Tree:** hiyerarşi. **BST** dengeliyse (AVL, Red-Black) ara/ekle/sil
  O(log n). **B-tree/B+tree** disk/DB indeksinin temeli (geniş dallı, az disk
  erişimi). **Heap** (öncelik kuyruğu) O(log n) ekle/çıkar, min/max O(1).
  **Trie** önek araması (autocomplete).
- **Graph:** düğüm + kenar. Komşuluk listesi (seyrek) veya matrisi (yoğun).
  Sosyal ağ, harita, bağımlılık, AD (BloodHound bir graf problemi!).

### 2.3. Temel algoritmalar
- **Sıralama:** quicksort (ortalama O(n log n), yerinde), mergesort (kararlı,
  O(n log n), O(n) yer), heapsort. Pratikte diller hibrit kullanır (Timsort —
  Python/Java; introsort — C++).
- **Arama:** ikili arama (sıralı veride O(log n)) — çok güçlü, sık unutulur.
- **Graf gezme:** BFS (en kısa yol, ağırlıksız; katman katman), DFS (derinlik;
  döngü tespiti, topolojik sıralama). Dijkstra (ağırlıklı en kısa yol), A*
  (sezgisel). Union-Find (bağlı bileşen).
- **Dinamik programlama (DP):** üst üste binen alt problemleri hafızalayarak
  üstel maliyeti polinoma indir (knapsack, en uzun ortak alt dizi, edit
  distance). Anahtar: optimal substructure + overlapping subproblems.
- **Greedy:** her adımda yerel en iyi (bazen global optimum — MST, Huffman;
  bazen değil — kanıt gerekir).
- **Two pointers / sliding window, recursion & backtracking, divide & conquer,
  bit manipulation** — problem çözme aletleri.

Pratik ilke: önce doğru çalışan basit çözüm, sonra ölç, sonra darboğazı optimize
et. "Premature optimization is the root of all evil" — ama Big-O seçimi
prematüre değildir; o tasarımın parçasıdır.

---

## 3. Bellek, İşaretçiler ve Sistem Programlama

Yüksek seviye dilde çalışsan bile altındaki modeli bilmek hata ayıklamada ve
güvenlikte belirleyicidir.

- **Stack vs heap:** Stack — otomatik, hızlı, fonksiyon yaşam süresi, sınırlı
  boyut (stack overflow — derin/sonsuz recursion). Heap — manuel/GC'li, esnek,
  yavaş, fragmentasyon riski.
- **Pointer / reference:** bir bellek adresi. Aritmetiği güçlü ama tehlikeli.
- **Bellek yönetimi modelleri:**
  - **Manuel (C/C++):** `malloc/free`, `new/delete`. Hata sınıfları: memory
    leak, use-after-free, double free, dangling pointer, buffer overflow
    (bunlar güvenlik açığıdır — bkz. 01 bölüm 8).
  - **Garbage collection (Java, C#, Go, Python):** otomatik geri kazanım.
    Kolaylık ama duraklama (GC pause) ve öngörülemezlik. Referans sayımı
    (Python) + döngü toplayıcı; izleyici (mark-sweep, generational).
  - **Ownership (Rust):** derleme zamanında, GC'siz bellek güvenliği. Her
    değerin tek sahibi; borrow checker aliasing+mutation kurallarını zorlar →
    veri yarışı ve use-after-free *derlenmez*. Devrimsel fikir: güvenlik runtime
    maliyeti olmadan.
- **Değer vs referans semantiği,** kopyalama (shallow/deep), byte düzeni
  (endianness), hizalama (alignment), sanal bellek/sayfalama temelleri.

---

## 4. Eşzamanlılık ve Paralellik

- **Concurrency ≠ parallelism.** Concurrency: birden çok işi *yönetme* (tek
  çekirdekte bile — zaman paylaşımı). Parallelism: aynı anda *yürütme* (çok
  çekirdek). Concurrency yapı, parallelism yürütmedir.
- **Modeller:**
  - **Thread + shared memory:** güçlü ama tehlikeli. **Race condition** (paylaşılan
    duruma senkronsuz erişim), **deadlock** (karşılıklı kilit bekleme),
    livelock, starvation. Kilit (mutex), semaphore, condition variable ile
    korunur. Kural: paylaşılan değişebilir durumu minimize et.
  - **Async / event loop (Node.js, Python asyncio):** tek thread, I/O beklerken
    başka işe geç. I/O-bound iş için mükemmel; CPU-bound işi *bloke eder*.
  - **Message passing (Go goroutine+channel, Erlang/aktör):** "belleği
    paylaşarak iletişme; ileterek belleği paylaş." Paylaşılan durumu azaltır →
    daha az yarış.
  - **Data parallelism:** aynı işi veri parçalarına dağıt (SIMD, GPU, MapReduce).
- **GIL (Python):** CPython'da aynı anda tek thread bytecode çalıştırır → thread'ler
  CPU-bound'da paralel değil. CPU işi için multiprocessing veya native uzantı.
  (Python 3.13+ deneysel no-GIL geliyor.)
- **Atomicity, memory ordering, false sharing, lock-free/wait-free** yapılar ileri
  konular. Pratik ilke: yüksek seviye soyutlama (thread pool, executor,
  channel, async) kullan; ham kilitle uğraşmaktan kaçın; paylaşımı azalt.

Güvenlik köprüsü: **TOCTOU** (time-of-check to time-of-use) bir race condition
zafiyetidir — kontrol ile kullanım arasında durum değişir (dosya izni kontrolü
sonrası symlink değişimi gibi).

---

## 5. İşletim Sistemi Kavramları

- **Process vs thread:** process — kendi bellek alanı, izole. Thread — process
  içinde, belleği paylaşır, hafif. İzolasyon vs paylaşım takası.
- **Scheduling:** OS, süreçleri çekirdeklere paylaştırır (preemptive; öncelik,
  time slice). Context switch maliyetlidir.
- **Sanal bellek:** her sürece izole adres alanı; sayfalama (paging), MMU, page
  fault, swap. İzolasyon + soyutlama.
- **System call:** user mode ↔ kernel mode geçişi; süreç, çekirdekten hizmet
  ister (dosya, ağ, süreç). Güvenlik sınırı buradadır.
- **IPC:** pipe, socket, shared memory, message queue, signal.
- **Dosya sistemi:** inode, izinler (Unix rwx / owner-group-other, setuid),
  journaling, sembolik link.
- **I/O:** blocking vs non-blocking, buffering, `select/poll/epoll/kqueue`
  (yüksek eşzamanlı I/O'nun temeli — async server'lar buna dayanır).

Bunları bilmek performans (neden yavaş?), hata ayıklama (neden takıldı?) ve
güvenlik (ayrıcalık sınırları) için gereklidir.

---

## 6. Ağlar (Yazılımcı Gözüyle)

01/bölüm 5 güvenlik açısından ele aldı; burada geliştirici açısı:
- **Katman modeli (TCP/IP):** Link → Internet (IP) → Transport (TCP/UDP) →
  Application (HTTP/DNS/TLS). Soyutlama: her katman altındakine güvenir.
- **TCP vs UDP:** TCP — bağlantılı, güvenilir, sıralı, akış kontrolü (web, çoğu
  şey). UDP — bağlantısız, hızlı, güvencesiz (DNS, oyun, video, QUIC tabanı).
- **HTTP:** istek/yanıt, stateless. Method (GET güvenli/idempotent, POST/PUT/
  DELETE), status kodları (2xx başarı, 3xx yönlendirme, 4xx istemci, 5xx sunucu),
  header'lar, cookie. HTTP/1.1 → HTTP/2 (multiplexing) → HTTP/3 (QUIC/UDP).
- **REST:** kaynak-merkezli, stateless, HTTP metodlarını semantik kullan. **vs
  GraphQL** (tek endpoint, istemci istediği alanı sorgular — over/under-fetch
  çözer ama kendi karmaşıklığı), **gRPC** (binary, HTTP/2, servis-servis, hızlı).
- **DNS:** isim → IP çözümleme, hiyerarşik, cache'li. **TLS:** bkz. 01/2.5.
- **WebSocket:** çift yönlü kalıcı bağlantı (gerçek zamanlı).

---

## 7. Veritabanları

### 7.1. İlişkisel (SQL)
- **Model:** tablolar, satır/sütun, ilişkiler (foreign key), şema. SQL ile sorgu.
- **ACID (transaction garantileri):** **Atomicity** (hep ya da hiç),
  **Consistency** (kısıtlar korunur), **Isolation** (eşzamanlı işlemler
  birbirini bozmaz), **Durability** (commit kalıcıdır). Finans gibi tutarlılık
  kritik yerde vazgeçilmez.
- **İndeksleme:** B-tree indeks, sorguyu O(n) taramadan O(log n) aramaya indirir.
  Doğru indeks = performans; yanlış/eksik indeks en yaygın yavaşlık nedeni.
  Composite index sıra önemi, covering index, indexin yazma maliyeti.
- **Normalizasyon:** veri tekrarını azalt (1NF-3NF), tutarsızlığı önle. **Denormalizasyon:**
  okuma hızı için kasıtlı tekrar (takas).
- **Isolation levels:** read uncommitted → read committed → repeatable read →
  serializable. Yüksek izolasyon = tutarlılık ama az eşzamanlılık. Anomali:
  dirty read, non-repeatable read, phantom read.
- **Query planı:** `EXPLAIN` ile sorgunun nasıl çalıştığını gör (full scan mı,
  index mi, join tipi). Optimizasyonun başlangıcı.
- **Güvenlik:** parametreli sorgu (SQLi — 01/4.1), en az yetkili DB kullanıcı,
  hassas veriyi şifrele, yedekle.

### 7.2. NoSQL
İhtiyaca göre farklı modeller:
- **Document (MongoDB):** JSON-benzeri belgeler, esnek şema.
- **Key-value (Redis, DynamoDB):** en basit, en hızlı; cache, session.
- **Column-family (Cassandra):** yazma-yoğun, yatay ölçek.
- **Graph (Neo4j):** ilişki-yoğun sorgular.
NoSQL genelde ölçek/esneklik için ACID'den ödün verir (**BASE:** Basically
Available, Soft state, Eventual consistency).

### 7.3. CAP teoremi
Dağıtık veri deposunda ağ bölünmesi (Partition) anında **Consistency** ve
**Availability** arasında seçim yapmak zorundasın (ikisini birden değil). CP
(tutarlılık öncelikli — reddet) vs AP (erişilebilirlik öncelikli — eski veri
dönebilir). Pratikte "eventual consistency" yaygın bir orta yol. PACELC bunu
genişletir (bölünme yokken bile latency/consistency takası).

---

## 8. Sistem Tasarımı (Ölçeklenebilir Mimari)

Küçük uygulamadan milyon kullanıcıya giden yol. Anahtar: darboğazı bul, o
katmanı ölçekle.

- **Scale up (dikey) vs scale out (yatay):** daha güçlü makine vs daha çok
  makine. Yatay ölçek daha dayanıklı ve genelde daha ucuz-esnek ama dağıtık
  sistem karmaşıklığı getirir.
- **Load balancer:** istekleri sunuculara dağıt (round-robin, least-conn);
  tek nokta hatasını önlemek için kendisi de yedekli. Stateless sunucular yatay
  ölçeği kolaylaştırır (durumu dışarı al — session store).
- **Caching:** en etkili performans kaldıracı. Katmanlar: client, CDN (statik
  içerik, kullanıcıya yakın), reverse proxy, uygulama (Redis/Memcached), DB.
  Zorluk: **cache invalidation** ("bilgisayar biliminde iki zor şey: cache
  invalidation ve isimlendirme"). Stratejiler: TTL, write-through, write-back,
  cache-aside. Stale veri takası.
- **Database ölçekleme:** **read replica** (okuma dağıt), **sharding** (veriyi
  parçala — anahtar seçimi kritik), **partitioning**. Yazma ölçeği en zorudur.
- **Asenkron / message queue (Kafka, RabbitMQ, SQS):** bileşenleri gevşek
  bağla, yük dalgalanmasını tampon, arka plan işleri. Producer/consumer,
  at-least-once/exactly-once teslim, dead-letter queue.
- **Mimari stiller:**
  - **Monolith:** tek dağıtım birimi. Başlangıçta basit, hızlı; büyüyünce
    hantal. Çoğu proje burada başlamalı ("monolith first").
  - **Microservices:** bağımsız dağıtılan küçük servisler. Ölçek ve ekip
    bağımsızlığı; ama dağıtık sistem vergisi (ağ, gözlemlenebilirlik, veri
    tutarlılığı, dağıtık transaction). Erken benimsemek yaygın hatadır.
  - **Event-driven, serverless (FaaS), CQRS, event sourcing** ileri kalıplar.
- **Güvenilirlik:** redundancy, failover, health check, circuit breaker (arızalı
  bağımlılığı devre dışı bırak), retry + exponential backoff + jitter,
  idempotency, graceful degradation, rate limiting.
- **Gözlemlenebilirlik (observability):** üç sütun — **metrics** (Prometheus),
  **logs** (yapılandırılmış), **traces** (dağıtık izleme). "Göremediğini
  yönetemezsin."
- **CDN, DNS, API gateway** kenar bileşenleri.
- **Tasarım süreci:** gereksinim (fonksiyonel + non-fonksiyonel: ölçek, latency,
  tutarlılık) → kapasite tahmini → API tasarımı → veri modeli → yüksek seviye
  mimari → derinleştir → darboğaz/tradeoff tartış. Her karar bir takastır;
  "en iyi" değil "bu bağlama uygun" mimari vardır.

---

## 9. Yazılım Mühendisliği Pratikleri

Kod yazmak işin yarısı; sürdürülebilir, doğru, ekipçe geliştirilebilir kod
diğer yarısı.

### 9.1. Sürüm kontrolü (Git)
- Anlık görüntü tabanlı; commit = değişiklik birimi. Branch ucuz → feature
  branch akışı. `merge` vs `rebase` (rebase temiz tarih ama paylaşılan dalı
  yeniden yazma). Pull request + code review.
- İyi commit: küçük, atomik, açıklayıcı mesaj (ne + neden). Sırlar repo'ya
  girmemeli (bir kez girdiyse tarihten temizle + sızan sırrı döndür — 01 ile
  köprü).

### 9.2. Test
- **Test piramidi:** çok **unit** (hızlı, izole, bir birim), daha az
  **integration** (bileşenler birlikte), az **end-to-end** (tüm sistem, yavaş,
  kırılgan). Tersi (buzdağı) yavaş ve kırılgan olur.
- **TDD:** önce test, sonra kod (kırmızı-yeşil-refactor). Her yerde şart değil
  ama tasarımı ve güveni iyileştirir.
- Kaliteler: deterministik (flaky test zehirdir), bağımsız, hızlı, anlamlı
  kapsama (coverage sayısı değil, kritik yolları test etmek önemli).
- **Fuzzing** (rastgele/otomatik girdi) hem bug hem güvenlik açığı bulur (01 köprü).

### 9.3. Temiz kod ve tasarım
- **SOLID (OOP):** Single responsibility, Open/closed, Liskov substitution,
  Interface segregation, Dependency inversion. Amaç: değişime dayanıklı,
  gevşek bağlı kod.
- **DRY** (tekrarı önle) ama aşırıya kaçma (yanlış soyutlama tekrardan kötü —
  "premature abstraction"). **KISS**, **YAGNI** (gerekmeden yapma).
- **Coupling düşük, cohesion yüksek.** Modüller az bağlı, içleri tutarlı.
- **Design patterns:** ortak problemlere adlandırılmış çözümler — Factory,
  Strategy, Observer, Adapter, Decorator, Singleton (dikkatli), Repository,
  Dependency Injection. Patterns araçtır, amaç değil; zorlama uygulama karmaşıklık
  katar.
- **İsimlendirme** en zor ve en önemli iş; kod okunmak içindir ("kod yazıldığından
  çok daha fazla okunur").
- **Teknik borç:** bilinçli/bilinçsiz kısayolların birikmiş maliyeti; yönet,
  görmezden gelme.

### 9.4. CI/CD ve DevOps
- **CI (Continuous Integration):** her push'ta otomatik derle + test + lint +
  güvenlik tara (SAST/SCA — 01 köprü). Hataları erken yakala.
- **CD (Continuous Delivery/Deployment):** otomatik, güvenli, tekrarlanabilir
  dağıtım. Blue-green, canary, rollback.
- **IaC (Terraform, Ansible):** altyapıyı kod olarak — tekrarlanabilir, gözden
  geçirilebilir.
- **Konteynerleştirme (Docker) + orkestrasyon (Kubernetes):** taşınabilir,
  izole, ölçeklenebilir dağıtım. Güvenlik: en az yetkili imaj, tarama (01/6.3).
- **12-Factor App** ilkeleri (config'i ortamdan al, stateless süreç, log'u
  stream olarak vb.) bulut-doğal uygulama için rehber.

### 9.5. Güvenli geliştirme yaşam döngüsü
Güvenlik sonradan eklenmez, baştan tasarlanır (**shift left**): tehdit modelleme
(01/1.4) → güvenli tasarım → güvenli kodlama → SAST/DAST/SCA → gözden geçirme →
düzenli yama. "Security is everyone's job."

---

## 10. Diller — Güçlü/Zayıf Yönler ve Güvenlik Notları

Dil bir araçtır; işe göre seçilir. Kısa profiller:

- **Python:** Okunaklı, hızlı geliştirme, devasa ekosistem (veri, ML, betik,
  web). Yavaş (yorumlanan, GIL), CPU-yoğunda zayıf. Güvenlik: `pickle`/`eval`/
  `exec` tehlikeli, `subprocess(shell=True)` command injection, bağımlılık
  riski. Jarvis'in dili — pratikte tutkal ve ML için ideal.
- **C:** Donanıma en yakın, hızlı, her yerde. Bellek elle yönetilir → tüm bellek
  güvenlik açıkları burada doğar (01/8). Sistem/gömülü/çekirdek. Güç ve tehlike
  bir arada.
- **C++:** C + OOP + soyutlama + şablonlar; yüksek performans (oyun, motor,
  yüksek frekans). Karmaşık; C'nin bellek riskleri + kendi tuzakları. Modern
  C++ (RAII, smart pointer) riski azaltır.
- **Rust:** Bellek güvenliği *GC'siz*, derleme zamanında (ownership/borrow —
  bkz. 3). C/C++ performansı + güvenlik. Öğrenme eğrisi dik. Sistem programlama,
  güvenlik-kritik, WebAssembly. "Fearless concurrency" — veri yarışı derlenmez.
- **Go:** Basitlik, hızlı derleme, yerleşik eşzamanlılık (goroutine/channel),
  iyi standart kütüphane. Bulut/ağ servisleri, CLI, DevOps araçları (Docker,
  k8s Go ile). GC var; kasıtlı sade (generics geç geldi).
- **JavaScript/TypeScript:** Web'in dili (tarayıcı tekeli) + Node ile sunucu.
  TypeScript tip güvenliği ekler (büyük kod tabanında neredeyse şart). Tuzaklar:
  zayıf tipleme, async karmaşıklığı, npm supply chain riski (01 köprü),
  prototype pollution.
- **C#/.NET:** Güçlü, olgun, kurumsal; Windows kökenli ama artık çapraz platform.
  Web (ASP.NET), masaüstü, oyun (Unity). GC'li, güvenli-varsayılan; `BinaryFormatter`
  deserialization tuzağı (01/4.7).
- **Java:** Kurumsal omurga, JVM taşınabilirliği, olgun ekosistem. Ayrıntılı ama
  öngörülebilir. Deserialization gadget'ları klasik açık kaynağı (01/4.7).

Seçim ekseni: performans mı geliştirme hızı mı; bellek kontrolü mü güvenliği mi;
ekosistem/ekip bilgisi. "En iyi dil" yoktur, iş için en uygun dil vardır.

---

## 11. Güvenli Kod Yazımı (Yazılım ↔ Güvenlik Köprüsü)

Bu bölüm iki cildi birleştirir. Güvenli kodun evrensel kuralları:

1. **Tüm girdiyi doğrula** — allow-list ile, sunucu tarafında (01/4.11).
2. **Veri ile kodu/komutu/sorguyu ayır** — parametreli sorgu, exec dizi
   argümanı, output encoding (injection'ların panzehiri).
3. **En az yetki** — kod, süreç, DB kullanıcısı, token; hepsi asgari yetkiyle.
4. **Güvenli varsayılan / fail secure** — hata durumunda reddet.
5. **Sırları koddan ayır** — secret manager/ortam değişkeni; repo'ya sır koyma.
6. **Kanıtlanmış kripto kütüphanesi kullan, kendi kriptonu yazma** (01/2).
7. **Bağımlılıkları güncel + taranmış tut** — SCA, pinning (01/4.10).
8. **Hata mesajında bilgi sızdırma** — kullanıcıya genel mesaj, ayrıntı log'a.
9. **Duyarlı işlemi logla ama sırrı loglama** (parola/token/PII log'a düşmesin).
10. **Bellek-güvenli dil tercih et** (mümkünse); C/C++'ta sanitizer + dikkat.
11. **Race condition/TOCTOU'ya dikkat** (4. bölüm), atomik işlemler kullan.
12. **Güvenliği baştan tasarla** (shift left), sonradan yama değil.

İyi mühendis için güvenlik ayrı bir konu değil, kalitenin bir boyutudur:
sağlam, doğru, öngörülebilir kod büyük ölçüde zaten güvenli koddur.

---

## Kapanış notu

Yazılım mühendisliği, karmaşıklığı yönetme sanatıdır. Araçlar (dil, framework,
platform) hızla değişir; ama bu belgedeki temeller — veri yapıları, karmaşıklık,
eşzamanlılık, sistem tasarımı takasları, temiz kod ilkeleri — kalıcıdır. Bir
sonraki teknolojiyi öğrenmek, bu temellere sahipsen sadece "yeni sözdizimi"
öğrenmektir. Derinlik her başlık için ayrı bir cilt ister; bu belge haritayı
verir, yürümek çalışmayla olur.
