# Tutarlılık Modelleri (Consistency Models)

Dağıtık sistemlerde en zor problemlerden biri, aynı verinin birden fazla kopyası (replica) üzerinde çalışırken "doğru" davranışın ne olduğunu tanımlamaktır. Bir kullanıcı bir değeri yazdığında, başka bir kullanıcı ne zaman ve hangi değeri okumalıdır? İşte tutarlılık modeli, tam olarak bu sorunun cevabını veren bir sözleşmedir: sistem ile onu kullanan programcı arasında, "hangi okumaların hangi yazmaları görebileceğini" tanımlayan biçimsel bir garanti kümesi.

Bu makale, strong (güçlü), eventual (nihai) ve causal (nedensel) tutarlılık modellerini; bunları uygulamada mümkün kılan quorum mekanizmalarını; ve replikalar arası çakışmaların (conflict) nasıl çözüldüğünü kök nedenleriyle birlikte ele alır.

## Tutarlılık Neden Bir Problemdir

Kök neden tek bir cümlede özetlenebilir: **veriyi çoğaltıyoruz ama çoğaltma anında olmuyor.** Bir veriyi tek bir makinede tuttuğumuz sürece tutarlılık diye bir sorun yoktur; okuma ve yazma aynı bellek hücresine gider, doğal olarak sıralıdır. Ancak dayanıklılık (durability), yüksek erişilebilirlik (availability) ve coğrafi yakınlık (latency) için veriyi birden çok düğüme kopyalarız. Bu kopyalar arasında bir yazmanın yayılması ise ışık hızıyla, ağ gecikmeleriyle ve düğüm arızalarıyla sınırlıdır.

Sonuç: bir kopyaya yazılan değer, diğer kopyalara ulaşana kadar geçen sürede sistem **tutarsız** bir haldedir. Tutarlılık modelleri, bu tutarsızlık penceresini programcıya nasıl gösterdiğimizi (ya da gizlediğimizi) tanımlar.

### CAP ve PACELC: Kaçınılmaz Ödünleşim

Tutarlılık tartışmasının çerçevesini CAP teoremi çizer. Kabaca ifadesi şudur: bir ağ bölünmesi (network partition, yani düğümlerin birbiriyle haberleşememesi) yaşandığında, sistem ya **tutarlılığı** (Consistency) ya da **erişilebilirliği** (Availability) feda etmek zorundadır; ikisini aynı anda koruyamaz. Bölünme yokken bu zorlama ortadan kalkar.

CAP'in sık yapılan bir yanlış yorumu "üçünden ikisini seç" kalıbıdır; bu yanıltıcıdır çünkü Partition tolerance bir seçenek değil, dağıtık sistemde bir zorunluluktur. Ağ bölünecektir; siz sadece bölünme anında C mi yoksa A mı diyeceğinizi seçersiniz.

Daha rafine bir çerçeve olan PACELC şunu ekler: bölünme (Partition) olduğunda A ile C arasında seçim yaparsınız; **Else** (bölünme yokken bile) düşük **Latency** ile güçlü **Consistency** arasında bir ödünleşim vardır. Yani güçlü tutarlılık, arızasız durumda dahi bir gecikme bedeli getirir. Bu, "neden herkes güçlü tutarlılık kullanmıyor" sorusunun temel cevabıdır: bedeli her istekte ödenir.

## Strong Consistency (Güçlü Tutarlılık)

### Tanım

Güçlü tutarlılık, sistemi sanki tek bir kopyası varmış gibi davranmaya zorlar. En sık atıfta bulunulan iki biçimsel model vardır:

- **Linearizability (doğrusallaştırılabilirlik):** Her işlem, çağrıldığı an ile tamamlandığı an arasında bir noktada "anlık" olarak gerçekleşmiş gibi görünür ve bir yazma tamamlandıktan sonra başlayan her okuma, o yazmayı veya daha yenisini görmek zorundadır. Bu, gerçek zaman (real-time) sırasını korur.
- **Sequential consistency (sıralı tutarlılık):** Tüm işlemler, her sürecin kendi program sırasını koruyan tek bir küresel sıraya yerleştirilebilir; ancak bu sıra gerçek zaman ile uyumlu olmak zorunda değildir.

Aradaki fark inceliklidir ama önemlidir: linearizability, "dışarıdan bakan bir gözlemcinin duvar saatiyle" tutarlılığı garantiler; sequential consistency ise sadece mantıksal bir sıra sözü verir. Pratikte "güçlü tutarlılık" dendiğinde çoğunlukla linearizability kastedilir.

### Kök Neden: Neden Bu Kadar Pahalı

Linearizability'yi sağlamak için sistemin, bir yazma "tamamlandı" demeden önce o yazmanın, sonraki okumaların onu kaçırmayacağı bir noktaya ulaştığından emin olması gerekir. Bu genelde şu anlama gelir: yazma, yeterli sayıda kopyaya işlenmeli ve okumalar da güncel kopyayı görecek şekilde koordine edilmelidir. Bu koordinasyon **senkron** iletişim ve çoğu zaman bir **consensus** (uzlaşma) protokolü gerektirir.

İşte pahalı olmasının kök nedeni: her güçlü tutarlı işlem, ağ üzerinden birden fazla düğümle round-trip yapmayı bekler. Bir düğüm yavaşsa veya erişilemezse, işlem ya bekler ya da başarısız olur. Bu yüzden CAP'te bölünme anında güçlü tutarlılık, erişilebilirliği feda eder.

### Consensus Protokolleri

Güçlü tutarlılığın altındaki motor genellikle bir consensus algoritmasıdır. En bilinenleri **Paxos** ve onun daha anlaşılır tasarlanmış varisi **Raft**'tır. Bunların çözdüğü temel problem şudur: birden çok düğüm, bazıları arızalanabilirken, tek bir değer (ya da işlem sırası) üzerinde nasıl anlaşır?

Raft bunu bir **lider** (leader) seçerek yapar; tüm yazmalar liderden geçer, lider bunları bir loga yazar ve **çoğunluğa** (majority) çoğaltır. Bir log girdisi çoğunluk tarafından onaylandığında "committed" (kesinleşmiş) sayılır ve geri alınamaz. Lider arızalanırsa, en güncel loga sahip düğümlerden biri yeni lider seçilir. Buradaki kritik nokta çoğunluk kavramıdır ve bu bizi doğrudan quorum'a götürür.

## Quorum: Çoğunluk Matematiği

### Tanım ve Çalışma Mantığı

Quorum, bir işlemin geçerli sayılması için gereken minimum düğüm sayısıdır. Klasik quorum tabanlı çoğaltmada üç parametre vardır:

- **N:** Toplam replika sayısı.
- **W:** Bir yazmanın başarılı sayılması için onaylaması gereken replika sayısı (write quorum).
- **R:** Bir okumanın başarılı sayılması için cevap vermesi gereken replika sayısı (read quorum).

Sistemin güçlü tutarlılığa yaklaşmasının **kök nedeni** basit bir küme kesişimi (set intersection) argümanıdır:

> **W + R > N** olduğunda, her okuma quorum'u ile her yazma quorum'u en az bir ortak düğümde kesişir.

Neden bu işe yarar? Çünkü bir yazma en az W düğüme ulaştıysa ve bir okuma en az R düğümden cevap topluyorsa, W + R > N koşulu bu iki kümenin boş olmayan bir kesişiminin olmasını **garanti eder** (güvercin yuvası / pigeonhole prensibi). Yani okuyan düğümlerden en az biri, en son yazılmış değeri mutlaka içerir. Okuyan taraf, dönen sürümler arasından en güncelini (genelde bir sürüm numarası veya timestamp ile) seçtiğinde, eski bir değer okuma riski ortadan kalkar.

### Somut Örnek

N = 3, W = 2, R = 2 alalım. Bu, dağıtık veritabanlarında çok yaygın bir yapılandırmadır.

1. İstemci `x = 5` yazar. Yazma, 3 replikadan en az 2'sine (diyelim A ve B) işlenene kadar başarılı sayılmaz.
2. Bu sırada C düğümü hâlâ eski değeri (`x = 3`) tutuyor olabilir; henüz güncelleme ona ulaşmamıştır.
3. Başka bir istemci okuma yapar ve R = 2 gereği 2 düğümden cevap ister. Hangi 2 düğüme sorarsa sorsun (A-B, A-C ya da B-C), en az biri yeni değeri (`x = 5`) içerecektir; çünkü yazma A ve B'de vardı ve herhangi bir ikili en az birini kapsar.
4. Okuyucu, dönen `{5 (sürüm 7), 3 (sürüm 6)}` gibi cevaplardan en yüksek sürümü seçer: `5`.

Eğer W = 1 seçseydik (W + R = 3, N'ye eşit, büyük değil), yazma sadece A'ya gider, okuma B-C'den cevap alırsa ikisi de eski değeri döndürür ve tutarsızlık yaşanırdı.

### Quorum'un Sınırları ve Tuzakları

Quorum'un W + R > N kuralı yaygın olarak "güçlü tutarlılık" diye anlatılır; bu **eksik ve kısmen yanıltıcı** bir ifadedir. Gerçekte klasik quorum, tek başına linearizability garanti etmez. Bilinen tuzaklar:

- **Eşzamanlı okuma-yazma yarışı:** Bir yazma tam yayılırken gelen okumalar, bazı düğümlerde yeni bazılarında eski değeri görebilir. Kesişim garantisi "en yeni değeri gören en az bir düğüm var" der, ama sonraki bir okumanın da aynı yeni değeri göreceğini garanti etmez (monotonluk kırılabilir).
- **Kısmi yazma başarısızlığı:** Yazma W'ye ulaşamadan (ör. sadece 1 düğüme yazıldıktan sonra istemci çöktü), sistem yarım kalmış bir durumda kalabilir. Bazı sonraki quorum'lar bu yarım değeri görüp "kazandırabilir".
- **Sloppy quorum:** Erişilebilirliği artırmak için bazı sistemler, hedef N düğüm erişilemezse yazmayı geçici olarak başka düğümlere kabul eder (hinted handoff ile geri taşımak üzere). Bu, erişilebilirliği yükseltir ama kesişim garantisini zayıflatır: artık okuma ve yazma quorum'ları farklı düğüm kümelerinde olabilir.

Bu yüzden gerçek güçlü tutarlılık için quorum'un üzerine ek mekanizmalar (leader tabanlı sıralama, read-repair, versiyon vektörleri) gerekir. Quorum bir yapı taşıdır, tek başına çözüm değildir.

## Eventual Consistency (Nihai Tutarlılık)

### Tanım

Nihai tutarlılık en zayıf pratik garantidir ve şunu söyler: **yeni yazma gelmezse, yeterince zaman geçtiğinde tüm replikalar aynı değere yakınsayacaktır.** Ne zaman yakınsayacağına dair bir süre garantisi yoktur; sadece "sonunda" olacağı söylenir.

Bu model ilk bakışta zayıf görünse de, internet ölçeğindeki birçok sistemin (DNS, büyük NoSQL depoları, CDN'ler, dağıtık cache'ler) temelidir. Sebebi PACELC'te gizlidir: nihai tutarlılık, her istekte senkron koordinasyon gerektirmediği için çok düşük gecikme ve çok yüksek erişilebilirlik sunar. Bir düğüm bölünme sırasında bile yazma kabul edebilir; senkronizasyon sonraya bırakılır.

### Kök Neden: Asenkron Yayılım

Nihai tutarlılığın çalışma mantığı basittir: yazma yerel olarak kabul edilir ve istemciye hemen "tamam" denir; değerin diğer replikalara yayılması **arka planda, asenkron** yapılır (gossip protokolü, anti-entropy taramaları, replikasyon logu gibi mekanizmalarla). Koordinasyonu kritik yoldan (critical path) çıkarmak, bu modelin hem gücünün hem de zayıflığının kaynağıdır.

### Nihai Tutarlılığın Alt Türleri

"Eventual" tek kelime altında pratikte çok farklı garanti seviyeleri gizlenir. İyi tasarlanmış sistemler, ham eventual yerine şu **oturum garantilerini** (session guarantees) sunar:

- **Read-your-writes:** Kendi yazdığınız değeri sonraki okumanızda mutlaka görürsünüz. (Profil fotoğrafınızı değiştirip sayfayı yenilediğinizde eski fotoğrafı görmemeniz için gerekir.)
- **Monotonic reads:** Bir değeri gördükten sonra, daha eski bir değere geri "dönmezsiniz". Okumalar zamanda geriye gitmez.
- **Monotonic writes:** Aynı sürecin yazmaları, tüm replikalarda o sürecin yazdığı sırayla uygulanır.

Bu garantiler eventual'ın en can sıkıcı anomalilerini ortadan kaldırır ve genelde istemci tarafında sürüm takibi veya "sticky session" ile sağlanır. Ham eventual consistency bunların hiçbirini garanti etmez; o yüzden bir sistemin sadece "eventually consistent" olduğunu duyduğunuzda, hangi oturum garantilerini verdiğini de sormalısınız.

## Causal Consistency (Nedensel Tutarlılık)

### Tanım

Nedensel tutarlılık, eventual ile strong arasında çok değerli bir orta noktadır. Temel sözü şudur: **nedensel olarak birbirine bağlı işlemler, tüm düğümlerde aynı sırada görülür; birbirinden bağımsız (concurrent) işlemlerin sırası ise düğümden düğüme değişebilir.**

"Nedensellik" (causality) burada teknik bir anlam taşır ve **happens-before** ilişkisiyle tanımlanır (Lamport'un tanımladığı ilişki):

- Aynı süreçte A, B'den önce gerçekleştiyse, A → B (A, B'den önce olur).
- A bir mesaj gönderme, B o mesajı alma ise, A → B.
- Geçişkendir: A → B ve B → C ise A → C.

Eğer ne A → B ne de B → A ise, bu iki işlem **eşzamanlıdır** (concurrent) ve nedensel tutarlılık onların sırası hakkında bir şey söylemez.

### Kök Neden: Neden Sadece Nedensellik

En sezgisel örnek bir yorum dizisidir. Kullanıcı bir soru gönderir (A), başka biri o soruyu görüp cevap yazar (B). Burada A → B'dir, çünkü B, A'yı gördükten sonra yazılmıştır. Nedensel tutarlılık, hiçbir gözlemcinin **cevabı sorudan önce görmemesini** garanti eder. Aksi olsaydı, bağlamsız bir cevap ekrana düşerdi.

Ama iki farklı kişinin aynı anda yazdığı iki bağımsız yorumun kim önce görünecek diye kesin bir sıraya sokulmasına gerek yoktur; onlar zaten birbirini görmemiştir. İşte nedensel tutarlılığın zarafeti budur: **sadece gerçekten önemli olan sıralamaları zorlar, gereksiz koordinasyonu bırakır.** Bu sayede tam sıralama (total order) maliyetinden kaçınarak yüksek erişilebilirlik ve düşük gecikme korunabilir; teorik olarak nedensel tutarlılık, ağ bölünmesi altında bile erişilebilir kalabilen en güçlü modeldir.

### Nasıl Uygulanır: Version Vektörleri

Nedenselliği takip etmenin yaygın yolu **version vector** (sürüm vektörü) veya vector clock kullanmaktır. Her düğüm, kendi ve diğer düğümlerin gördüğü son sürümleri bir vektörde tutar. Bir yazma yayıldığında bu vektör de taşınır. Bir düğüm, bir güncellemeyi uygulamadan önce onun tüm nedensel öncüllerini (causal dependencies) görmüş olmasını bekler; görmemişse güncellemeyi tampona (buffer) alır. Böylece "cevap, sorudan önce uygulanmaz" garantisi sağlanır.

Version vektörlerinin bir yan faydası, iki güncellemenin nedensel mi yoksa eşzamanlı mı olduğunu **kesin** ayırt edebilmeleridir. İki vektörden biri diğerini "domine ediyorsa" (her bileşeni büyük ya da eşitse), nedensel bir sıra vardır; hiçbiri diğerini dominoe etmiyorsa işlemler eşzamanlıdır ve bu bir çakışmadır.

## Çakışma Çözümü (Conflict Resolution)

### Çakışma Ne Zaman ve Neden Oluşur

Çakışma, iki işlemin **eşzamanlı** (birbirini görmeden) aynı veriyi farklı şekilde değiştirmesiyle oluşur. Bu, güçlü tutarlılık dışındaki modellerin doğal sonucudur: koordinasyonu kritik yoldan çıkardığınızda, iki istemcinin aynı anahtarı aynı anda güncellemesine izin vermiş olursunuz. Sistem sonradan bu iki değerin uzlaştırılması (reconciliation) sorunuyla karşılaşır.

Çakışma çözümünde birkaç temel strateji vardır ve her birinin bedeli farklıdır.

### Strateji 1: Last-Write-Wins (LWW)

En basit strateji: her yazmaya bir timestamp ekle, çakışmada en büyük timestamp'i kazanan ilan et. Uygulaması kolaydır ve deterministiktir (tüm düğümler aynı kararı verir).

Ancak en tehlikeli tuzaklardan birini barındırır: **sessiz veri kaybı** (silent data loss). LWW, kaybeden yazmayı geri döndürülemez biçimde atar. İki kullanıcı aynı anda aynı belgeyi güncellediyse, birinin çalışması izsizce kaybolur. Dahası, timestamp'ler düğümlerin duvar saatlerine dayanıyorsa ve saatler senkron değilse (clock skew), "en son yazma" aslında zaman olarak daha önce yapılmış bir yazma olabilir. Bu yüzden LWW, ancak veri kaybının kabul edilebilir olduğu durumlarda (ör. cache, en son bilinen konum, telemetri) güvenlidir.

### Strateji 2: Uygulamaya Çakışmayı Bildirmek (Sürüm Vektörleriyle)

Daha güvenli bir yaklaşım, çakışmayı **çözmeye çalışmadan** korumaktır. Sistem, eşzamanlı yazmaları version vector ile tespit eder ve her ikisini birden (siblings / eş kardeşler olarak) saklar. Bir sonraki okumada her iki versiyonu da istemciye döndürür ve "bunları sen birleştir" der.

Klasik örnek bir alışveriş sepetidir. Kullanıcı iki farklı cihazdan sepete ayrı ürünler eklerse, iki eşzamanlı versiyon oluşur. Bir eş kardeşi seçip diğerini atmak, bir ürünün sepetten kaybolması demektir. Doğru çözüm iki sepetin **birleşimini** (union) almaktır. Ama bu birleştirme mantığını sistem bilemez; sepet için birleşim doğrudur, ama bir banka bakiyesi için birleşim saçmadır. O yüzden karar uygulamaya bırakılır. Bedeli: uygulama karmaşıklığı artar.

### Strateji 3: CRDT'ler (Conflict-free Replicated Data Types)

En zarif yaklaşım, veri yapısını çakışmaların **matematiksel olarak imkânsız** olacağı şekilde tasarlamaktır. CRDT'ler, birleştirme (merge) işlemi şu üç özelliği sağlayan veri tipleridir: değişmeli (commutative), birleşmeli (associative) ve etkisiz-tekrarlı (idempotent). Bu özellikler sayesinde güncellemeler hangi sırayla, kaç kez uygulanırsa uygulansın, tüm replikalar aynı nihai duruma yakınsar.

Örnekler: her düğümün kendi sayacını ayrı tuttuğu ve toplamı okuma anında hesapladığı bir **artış sayacı** (grow-only counter); ekleme ve silmeyi ayrı kümelerde tutarak "silme kazanır" ya da "ekleme kazanır" kuralı uygulayan **kümeler**; ve işbirlikli metin editörlerinin altında yatan sıralı diziler. CRDT'lerin gücü, çakışma çözümünü uygulama katmanından alıp veri tipinin matematiğine gömmeleridir; bedeli ise metadata büyümesi (silinen öğelerin izlerini "tombstone" olarak tutmak gibi) ve her problem için uygun bir CRDT tasarlamanın zorluğudur.

### Strateji 4: Operational Transformation (OT)

İşbirlikli düzenleme (Google Docs benzeri) alanında geleneksel yaklaşım OT'dir. Fikir şudur: eşzamanlı işlemler geldiğinde, bir işlemi diğerinin etkisini hesaba katacak şekilde **dönüştür** (transform). Örneğin iki kullanıcı aynı anda farklı konumlara harf eklerse, ikinci işlemin ekleme indeksi, birincinin eklediği karakter sayısı kadar kaydırılır. OT güçlüdür ama doğru uygulaması notoriously (kötü şöhretle) zordur; kenar durumları çoktur. Bu zorluk, birçok yeni sistemi CRDT'lere yöneltmiştir.

## Doğru Model Nasıl Seçilir

Tutarlılık modeli seçimi bir "mühendislik değil, iş kararı" olarak da görülebilir çünkü doğrudan kullanıcı deneyimini ve maliyeti belirler. Karar verirken sorulması gereken sorular:

- **Yanlış/eski veri okumanın bedeli nedir?** Bir banka bakiyesi, envanterdeki son ürün, veya bir kimlik doğrulama tokenı için eski veri kabul edilemez; strong consistency gerekir. Bir sosyal medya beğeni sayısı için birkaç saniye eski olması önemsizdir; eventual yeter.
- **Yazma-yazma çakışması olası mı, olursa ne kadar zarar verir?** Nadir ve zararsızsa LWW; olası ve önemliyse CRDT ya da uygulama tarafı birleştirme.
- **Bölünme anında ne olsun?** Sistem durmalı mı (CP) yoksa çalışmaya devam edip sonra uzlaşmalı mı (AP)?
- **Gecikme bütçeniz nedir?** Coğrafi olarak dağıtık ve düşük gecikme kritikse, her istekte cross-region consensus yapmak sürdürülemez olabilir.

Kritik bir gözlem: **bir sistemin her yerinde aynı modeli kullanmak zorunda değilsiniz.** Modern mimariler genelde melez (hybrid) çalışır. Aynı uygulamada ödeme akışı güçlü tutarlı, kullanıcı profili nedensel tutarlı, öneri/analitik verileri ise nihai tutarlı olabilir. Doğru mühendislik, her veri parçası için "yanlış cevabın bedelini" ayrı ayrı değerlendirmektir.

## Yaygın Hatalar

- **"Güçlü tutarlılık her zaman daha iyidir" varsayımı.** Değildir. Gereksiz güçlü tutarlılık, PACELC'in "Else-Latency" tarafında sürekli bir gecikme ve erişilebilirlik bedeli ödetir. İhtiyaç olmayan yere consensus koymak, sistemi yavaşlatır ve bölünmelere karşı kırılganlaştırır.
- **Quorum'u linearizability sanmak.** W + R > N tek başına gerçek güçlü tutarlılık sağlamaz; eşzamanlı okuma-yazma ve sloppy quorum senaryolarında anomali kalır. Quorum bir yapı taşıdır, garanti değildir.
- **LWW'yi düşünmeden kullanmak.** Timestamp tabanlı LWW, senkron olmayan saatlerle sessizce veri kaybettirir. En sinsi hatalardan biridir çünkü hiçbir hata mesajı üretmez; veri sadece kaybolur.
- **Saat senkronizasyonuna körü körüne güvenmek.** Fiziksel saatler kayar (clock skew). Nedensellik gerektiğinde fiziksel timestamp yerine mantıksal saat (logical clock / version vector) kullanılmalıdır; nedensellik fiziksel zamanla değil, happens-before ile tanımlanır.
- **Oturum garantilerini atlamak.** Sadece "eventual" bir depo üzerine kullanıcı deneyimi kurup read-your-writes garantisini unutmak, "az önce yazdığım şey neden yok?" tarzı hataların baş sebebidir.
- **Çakışmaların olmayacağını varsaymak.** AP bir sistemde eşzamanlı yazma mümkünse, çakışma **olacaktır**. Bir çözüm stratejisi baştan tasarlanmamışsa, sistem çakışmayı ya sessizce ezer ya da tanımsız davranır.

## En İyi Pratikler

- **Her veri alanı için tutarlılık ihtiyacını açıkça yazın.** "Bu veri kaç saniye eski olabilir?" ve "iki kişi aynı anda yazarsa ne olmalı?" sorularının cevaplarını dokümante edin. Bu kararı örtük bırakmak, sonradan üretimde sürprizle karşılaşmak demektir.
- **Güçlü tutarlılığı sadece gerçekten gerektiği yerde kullanın** (para, envanter, benzersizlik kısıtları, kilitler) ve orada bir consensus tabanlı, lider koordineli mekanizmaya yaslanın.
- **Nedensel tutarlılığı, kullanıcıların sıralamayı fark edeceği yerlerde** (mesajlaşma, yorumlar, aktivite akışları) tercih edin; strong'un maliyetini ödemeden anlamlı sıralama alırsınız.
- **Çakışma çözüm stratejisini veri semantiğine göre seçin:** kaybı tolere edilebilen sayaç benzeri veriler için CRDT; kaybı tolere edilemeyen ve birleştirme mantığı domain'e özgü olan veriler için sibling'leri uygulamaya döndürme.
- **Nedensellik takibi için mantıksal saat kullanın**, fiziksel timestamp değil. Version vector'lar eşzamanlılığı kesin ayırt eder; duvar saati bunu yapamaz.
- **Anti-entropy ve read-repair mekanizmalarını ihmal etmeyin.** Nihai tutarlı sistemlerde replikaların gerçekten yakınsaması, arka plandaki bu onarım süreçlerine bağlıdır; bunlar zayıfsa "eventual" pratikte "asla" olabilir.
- **Test edin: bölünmeyi ve gecikmeyi kasıtlı üretin.** Ağ bölünmesi, gecikme ve düğüm arızası enjekte eden testler (chaos/fault injection tarzı) olmadan, tutarlılık garantilerinizin gerçek olup olmadığını asla bilemezsiniz. Tutarlılık hataları, tam da bu nadir koşullarda ortaya çıkar.

## Özet

Tutarlılık modelleri, dağıtık verinin kaçınılmaz gecikmeli çoğaltılmasıyla ortaya çıkan tutarsızlığı programcıya nasıl gösterdiğimizi tanımlayan sözleşmelerdir. **Strong** tutarlılık tek-kopya yanılsaması verir ama consensus ve senkron koordinasyon bedeliyle gelir; **eventual** tutarlılık koordinasyonu kritik yoldan çıkararak yüksek erişilebilirlik ve düşük gecikme sunar ama anomalileri programcıya bırakır; **causal** tutarlılık ise sadece happens-before ilişkisini koruyarak ikisinin arasında zarif bir denge kurar. Quorum'un W + R > N kuralı bir kesişim garantisiyle güçlü tutarlılığa yaklaşmayı sağlar ama tek başına yeterli değildir. Çakışmalar, koordinasyondan vazgeçmenin kaçınılmaz bedelidir; LWW'nin sessiz kaybından, CRDT'lerin matematiksel zarafetine kadar uzanan çözüm yelpazesi, her zaman verinin semantiğine göre seçilmelidir. Nihayetinde doğru cevap tek bir model değil, her veri parçası için "yanlış cevabın bedelini" ayrı ayrı ölçen bilinçli bir mühendislik kararıdır.
