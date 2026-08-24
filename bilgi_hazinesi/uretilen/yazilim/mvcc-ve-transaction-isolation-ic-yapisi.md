# MVCC ve Transaction Isolation İç Yapısı

## Neden Bu Konu Ayrı Bir Başlığı Hak Ediyor?

"ACID/Transactions" ve "İlişkisel Model/SQL" gibi genel başlıklar, transaction'ların *ne* garanti ettiğini anlatır. Ama profesyonel seviyede asıl kritik soru şudur: **bu garantiler, aynı satıra aynı anda yüzlerce transaction erişirken, kilitlenmeden (lock etmeden) nasıl sağlanıyor?** Cevap neredeyse her modern ilişkisel veritabanında aynıdır: **MVCC (Multi-Version Concurrency Control)**. Bu makale MVCC'nin somut mekaniğine iner: tuple versiyonlama, snapshot isolation, vacuum/garbage collection, undo/redo log farkları (PostgreSQL vs InnoDB), phantom read, write skew ve Serializable Snapshot Isolation (SSI). Amaç, bir mühendisin "neden production'da bu tablo şişiyor", "neden bu transaction serialization error alıyor" gibi sorulara *mekanizmadan* cevap verebilmesi.

## MVCC Nedir, Kök Neden Ne?

### Problemin Kaynağı: Okuma-Yazma Çakışması

Klasik (kilit tabanlı, "2PL - Two-Phase Locking") bir eşzamanlılık kontrolünde, bir transaction bir satırı okurken o satır üzerinde paylaşımlı bir kilit (shared lock) alır; bu kilit varken başka bir transaction o satırı değiştiremez. Bu basit ve doğru çalışır ama ciddi bir performans problemi yaratır: **okuyucular yazarları, yazarlar okuyucuları bloklar.** Yoğun bir OLTP sisteminde (çok sayıda kısa okuma + yazma) bu, verimi düşüren bir kilit rekabeti (lock contention) yumağına dönüşür.

MVCC'nin kök fikri şudur: **eğer bir satırın birden fazla versiyonunu saklarsak, okuyucular hiçbir zaman yazarları beklemek zorunda kalmaz.** Bir transaction bir satırı okumaya başladığında, kendisine "bu satırın şu ana kadarki tutarlı görüntüsü" (snapshot) verilir; başka bir transaction aynı satırı değiştirse bile, okuyucu kendi snapshot'ındaki eski versiyonu görmeye devam eder. Yazan taraf yeni bir versiyon *ekler*, var olanı yerinde değiştirmez (in-place update yerine ek/append mantığı — PostgreSQL'de tam olarak böyle, InnoDB'de kısmen farklı, aşağıda göreceğiz).

Bu tek fikir üç şeyi aynı anda çözer:
1. Okuyucular yazarları bloklamaz, yazarlar okuyucuları bloklamaz (yalnızca yazar-yazar çakışması kilit/çakışma kontrolü gerektirir).
2. Her transaction'a **tutarlı bir an'ın fotoğrafı** (snapshot) verilerek "non-repeatable read" gibi sorunlar doğal olarak engellenir.
3. Geriye dönük okuma (point-in-time read) mümkün olur — bu da uzun süren raporlama sorgularının canlı yazma trafiğini kilitlememesini sağlar.

Bedelini de baştan söylemek gerekir: eski versiyonlar bir yerlerde birikir ve bir noktada temizlenmesi (garbage collection) gerekir. MVCC'nin en çok tartışılan operasyonel maliyeti tam olarak burasıdır.

## Tuple Versiyonlama: PostgreSQL Yaklaşımı

PostgreSQL'de her satır fiziksel olarak bir **tuple** (heap'teki fiziksel kayıt) olarak saklanır ve her tuple'ın başında görünmez sistem sütunları vardır: `xmin` ve `xmax`. Bunlar transaction ID'leridir (`xid`, monoton artan 32-bit sayaç — bu detay ileride "transaction ID wraparound" problemine yol açacak, ona döneceğiz).

- `xmin`: bu tuple'ı **oluşturan** transaction'ın ID'si.
- `xmax`: bu tuple'ı **geçersiz kılan** (silen veya güncelleyen) transaction'ın ID'si. Henüz silinmemişse boştur/geçersizdir.

Bir `UPDATE` çalıştığında PostgreSQL var olan tuple'ı yerinde değiştirmez. Bunun yerine:
1. Eski tuple'ın `xmax`'ına güncelleyen transaction'ın ID'si yazılır (yani "bu versiyon şu transaction'dan itibaren geçersiz" denir).
2. Yeni içerikle **tamamen yeni bir tuple** heap'e eklenir, bu yeni tuple'ın `xmin`'i güncelleyen transaction'ın ID'sidir.
3. İndeksler de bu yeni tuple'ı işaret edecek şekilde güncellenir (bu yüzden PostgreSQL'de çok sütunlu index'i olan tablolarda `UPDATE` maliyeti index sayısıyla orantılı büyür — "HOT update" optimizasyonu bunun bir kısmını index'i değiştirmeden çözmeye çalışır, ama koşullara bağlıdır).

Bir transaction bir satırı okumaya çalıştığında, motor şu kuralı uygular (basitleştirilmiş): *"bu tuple'ın `xmin`'i benim snapshot'ıma göre zaten commit olmuş ve benden önce başlamış mı, VE `xmax`'ı ya boş ya da benim snapshot'ıma göre henüz commit olmamış mı?"* Eğer evet ise bu tuple benim için **görünür**dür. Bu kontrol her satır okumasında yapılır ve "visibility check" olarak anılır.

**Snapshot** dediğimiz şey aslında şu bilgiden ibarettir: "şu ana kadar commit olmuş transaction ID'lerin listesi (veya aralığı) + o an aktif/commit olmamış transaction ID'lerinin listesi". Bir transaction başladığı anda (ya da isolation seviyesine göre her sorguda) bu bilgiyi alır ve tüm görünürlük kontrollerini buna göre yapar.

### Vacuum: PostgreSQL'in Garbage Collection'ı

Eski tuple versiyonları (artık hiçbir aktif transaction'ın snapshot'ı tarafından görülemeyen, yani "dead tuple" olan versiyonlar) heap'te yer kaplamaya devam eder — PostgreSQL onları anında silmez, çünkü silme işlemi de bir yazma maliyetidir ve fiziksel silme senkron olmak zorunda değildir. Bunun yerine arka planda çalışan **`autovacuum`** süreci düzenli olarak heap'i tarar, hiçbir transaction'ın artık göremeyeceği (yani tüm aktif snapshot'ların "ötesinde kalmış") dead tuple'ları fiziksel olarak temizler ve o alanı yeniden kullanılabilir hale getirir.

Bunun kritik sonucu şudur: **eğer uzun süren bir transaction açık kalırsa (örneğin biri `BEGIN` yapıp saatlerce commit etmezse), vacuum o transaction'ın snapshot'ından daha yeni olan hiçbir dead tuple'ı temizleyemez** — çünkü teorik olarak o eski transaction hâlâ o eski versiyonu görebilmeli. Bu, production'da çok sık karşılaşılan bir performans krizinin kök nedenidir: "tablo şişiyor", "index bloat oluşuyor", "vacuum bir türlü rahatlamıyor" şikayetlerinin arkasında genellikle unutulmuş, commit edilmemiş uzun bir transaction ya da bir replication slot'unun tıkanması vardır.

**Transaction ID Wraparound:** `xid` 32-bit olduğu için sınırlıdır (~4 milyar). Çok yoğun yazma yapan ve düzenli vacuum edilmeyen bir veritabanında bu sayaç turlanabilir (wraparound), bu da eski verinin "gelecekten gelmiş" gibi görünüp yanlışlıkla kaybolmasına yol açabilecek ciddi bir tehlikedir. PostgreSQL bunu "freeze" mekanizmasıyla önler: yeterince eski tuple'lar özel bir "her zaman görünür" değerine dondurulur (`xmin` etkin olarak "FrozenXid" yapılır). Vacuum'un bir görevi de budur. Bu yüzden "vacuum'u kapatmak" veya uzun süre engellemek ciddi bir operasyonel risktir, sadece performans değil veri bütünlüğü riskidir.

## InnoDB Yaklaşımı: Undo Log Tabanlı MVCC

MySQL/InnoDB, kavramsal olarak aynı MVCC hedefine farklı bir fiziksel yolla ulaşır. PostgreSQL'in aksine InnoDB satırı genellikle **yerinde günceller** (in-place update, clustered index üzerinde), ama güncellemeden önceki eski hâli ayrı bir yapıya, **undo log**'a yazar.

Mekanik olarak:
- Her satırda gizli bir alan (roll pointer) vardır ve bu, o satırın *bir önceki versiyonunun* undo log'daki kaydına işaret eder.
- Bir transaction eski bir versiyonu görmesi gerektiğinde (kendi snapshot'ı öyle diyorsa), InnoDB roll pointer zincirini takip ederek undo log'dan geriye doğru eski versiyonları **yeniden inşa eder**. Buna "consistent read view" ile okuma denir.
- Undo log aynı zamanda `ROLLBACK` için de kullanılır: bir transaction geri alınırsa, undo log'daki kayıtlar tersine uygulanarak satır eski hâline döndürülür — isim buradan gelir.

Bu yaklaşımın PostgreSQL'e göre pratik sonuçları farklıdır:
- **Uzun okuma transaction'ları InnoDB'de farklı bir maliyet yaratır:** eğer bir satır o uzun transaction başladıktan sonra çok kez güncellenmişse, o transaction her okumada undo log zincirini uzun uzun takip etmek zorunda kalabilir — bu "uzun undo chain" performans sorunu olarak bilinir ve PostgreSQL'deki "vacuum yetişemiyor/bloat" sorununun InnoDB tarafındaki kuzenidir. Belirti farklı (yavaş sorgu vs. şişen tablo) ama kök neden aynıdır: **eski versiyonları tutmaya devam etmeye zorlayan uzun bir transaction.**
- InnoDB'nin temizliği (purge) arka planda çalışan **purge thread**'lerle yapılır: artık hiçbir aktif read view tarafından ihtiyaç duyulmayan undo log kayıtları silinir. Bu, PostgreSQL'deki autovacuum'a kavramsal karşılıktır.
- InnoDB'de tablo dosyası (heap) PostgreSQL'deki gibi "dead tuple çöplüğü" haline gelmez çünkü satır yerinde güncellenir; şişme daha çok **undo tablespace**'te ve ikincil indekslerdeki eski versiyon referanslarında yaşanır.

### WAL/Redo Log ile Undo Log'un Karıştırılmaması Gereken Farkı

Bu, sık yapılan bir kavram karışıklığıdır, o yüzden netleştirmekte fayda var:
- **Redo log (InnoDB) / WAL (PostgreSQL):** *Durability* ve *crash recovery* için vardır. "Bu değişikliği diske fiziksel olarak yazacağım" sözünü tutmak, çökme sonrası commit edilmiş değişiklikleri yeniden uygulamak (redo) için kullanılır. MVCC ile doğrudan ilgili değildir — bu, ACID'nin "D" (Durability) ve "A" (Atomicity) tarafını hizmet eder.
- **Undo log (InnoDB):** Hem `ROLLBACK` için hem de **MVCC görünürlüğü için eski versiyonları yeniden inşa etmek** için kullanılır. Yani InnoDB'de undo log iki işi birden görür: geri alma + eski sürüm okuma.
- **PostgreSQL'de ayrı bir "undo log" yoktur** — eski versiyonlar zaten heap'in kendisinde, farklı tuple'lar olarak durur; "geri alma" ise zaten hiç yazılmamış gibi ele alınır (commit edilmemiş tuple'lar görünmez sayılır, fiziksel olarak sonradan vacuum ile temizlenir).

Bu mimari fark şu pratik sonucu doğurur: **InnoDB'de `ROLLBACK` ucuzdur çünkü zaten değişiklik commit edilmemiş sayılır ve undo bilgisi hâlâ oradadır; PostgreSQL'de de rollback ucuzdur ama farklı sebeple — commit edilmemiş tuple hiçbir zaman "gerçek" sayılmaz, sadece daha sonra vacuum tarafından süpürülür.**

## Isolation Seviyeleri ve Somut Anomaliler

SQL standardı dört isolation seviyesi tanımlar: **Read Uncommitted, Read Committed, Repeatable Read, Serializable**. Bunları soyut olarak ezberlemek yerine, hangi anomaliyi hangi mekanizmanın önlediğini anlamak gerekir.

### Dirty Read
Commit edilmemiş bir değişikliği başka bir transaction'ın görmesi. MVCC'li sistemlerde (PostgreSQL, InnoDB varsayılan modları) bu zaten mimari olarak imkânsızdır çünkü görünürlük kontrolü zaten "commit olmuş mu" diye bakar — Read Uncommitted seviyesi bu sistemlerde çoğunlukla adı var, kendisi yok (PostgreSQL'de Read Uncommitted istense bile Read Committed gibi davranır).

### Non-Repeatable Read
Aynı transaction içinde aynı satırı iki kez okuduğunuzda farklı sonuç almak — çünkü aralarda başka bir transaction o satırı değiştirip commit etti. **Read Committed** seviyesi bunu *önlemez* (her sorgu kendi anlık snapshot'ını alır); **Repeatable Read** seviyesi transaction'ın *tamamı* için tek bir snapshot sabitleyerek bunu önler.

### Phantom Read
Bir transaction bir `WHERE` koşuluna uyan satırları iki kez sorguladığında, aralarda başka bir transaction o koşula uyan **yeni bir satır ekleyip commit ettiği için** ikinci sorguda "hayalet" (phantom) bir satır belirmesi. Bu, non-repeatable read'den farklıdır: var olan bir satırın değişmesi değil, *yeni bir satırın kümeye girmesi* söz konusudur.

Burada motorlar arasında önemli bir fark vardır:
- **PostgreSQL'de Repeatable Read** (ki PostgreSQL'in snapshot mekaniği bunu doğal olarak sağlar) phantom read'i de otomatik olarak engeller, çünkü transaction'ın tuttuğu tek snapshot yeni eklenen satırları hiç görmez. Bu yüzden PostgreSQL'de standardın tanımladığı "Repeatable Read" ile "Serializable" arasındaki fark, standardın öngördüğünden daha incedir.
- **InnoDB'de Repeatable Read** varsayılan izolasyon seviyesidir ve *büyük ölçüde* phantom read'i önler, ama tam garanti için **gap lock** ve **next-key lock** adı verilen ek kilitleme mekanizmalarına da başvurur (saf MVCC yetmez, çünkü `INSERT` gibi bir işlemde henüz var olmayan bir aralığı "kilitlemek" MVCC'nin doğal işi değildir — bu yüzden InnoDB burada MVCC'yi kilitlemeyle *tamamlar*). Bu, "InnoDB MVCC kullanıyor, o zaman hiç kilit yok" gibi yaygın bir yanlış anlamayı düzeltir: InnoDB pratikte **hibrit** bir modeldir, MVCC + seçici kilitleme.

### Write Skew ve Serileştirme Anomalisi

Snapshot Isolation (PostgreSQL'in Repeatable Read'i, Oracle'ın "Serializable" dediği ama aslında SI olan modu) çoğu anomaliyi çözer ama **write skew** adı verilen ince bir anomaliye karşı savunmasızdır. Klasik örnek: bir hastanede nöbetçi doktor kuralı "en az bir doktor nöbette kalmalı" olsun. İki doktor da aynı anda "şu an iki doktor nöbette, ben çıkabilirim" diye kontrol edip ikisi de aynı snapshot'ı görür, ikisi de kendi çıkışını commit eder — sonuç: hiç doktor kalmaz. Her transaction kendi yazdığı satırla ilgili bir çakışma görmez (ikisi de *farklı* satırları güncelliyordur), ama birlikte ele alındıklarında iş kuralını ihlal ederler. Bu, klasik kilitli sistemlerde `SELECT ... FOR UPDATE` gibi açık kilitlerle önlenebilecek bir durumdur, ama saf Snapshot Isolation bunu kendiliğinden yakalamaz çünkü her transaction'ın gördüğü veri kendi başına tutarlıdır — çakışma sadece *ikisinin birleşiminde* ortaya çıkar.

### Serializable Snapshot Isolation (SSI)

PostgreSQL'in gerçek `SERIALIZABLE` seviyesi (2011'den beri, PostgreSQL 9.1+), Snapshot Isolation'ın üzerine **SSI (Serializable Snapshot Isolation)** algoritmasını ekleyerek write skew dahil tüm serileştirme anomalilerini yakalar. Kök fikir şudur: motor, transaction'lar arasındaki **okuma-yazma bağımlılıklarını** (rw-antidependency: bir transaction'ın okuduğu veriyi başka bir transaction'ın değiştirmesi) izler. Eğer bu bağımlılık grafiğinde belirli bir tehlikeli örüntü (iki ardışık rw-antidependency, "pivot" transaction) oluşursa, motor bunu "bu execution sırası serial bir sıraya eşdeğer olmayabilir" diye tespit eder ve transaction'lardan birini **serialization failure** hatasıyla iptal eder (genellikle `ERROR: could not serialize access due to read/write dependencies among transactions`).

Bunun mühendislik açısından pratik sonucu şudur: **`SERIALIZABLE` seviyesini kullanan bir uygulama, bu hatayı bekleyip transaction'ı yeniden denemeye (retry) hazır olmak zorundadır.** Bu bir hata değil, tasarımın parçasıdır — SSI, kilitlemeden serileştirme sağlamanın bedelini "bazen bir transaction'ı iptal edip yeniden denet" şeklinde öder. Bu, iyimser eşzamanlılık kontrolünün (optimistic concurrency control) genel felsefesiyle uyumludur: çakışma nadirse önceden kilitlemek yerine sonradan tespit edip iptal etmek daha verimlidir.

## Doğru Kullanım, Tuzaklar, En İyi Pratikler

**Uzun transaction'ları asla açık bırakmayın.** Hem PostgreSQL'de vacuum'un ilerlemesini engeller hem InnoDB'de undo log'un şişmesine yol açar. Bir bağlantı havuzunda (connection pool) "idle in transaction" durumunda unutulmuş bir bağlantı, production'da sessizce birikip günler sonra fark edilen bir performans krizine dönüşebilir. `idle_in_transaction_session_timeout` (PostgreSQL) gibi güvenlik ağları bu yüzden önemlidir.

**İzolasyon seviyesini iş mantığına göre seçin, varsayılanı sorgulamadan kabul etmeyin.** Read Committed çoğu CRUD işlemi için yeterlidir ve en ucuzudur. Ancak "oku-kontrol et-yaz" (read-modify-write, örneğin bakiye kontrolü) örüntüsü içeren iş mantığında Read Committed **race condition'a açıktır** çünkü kontrol ile yazma arasında başka bir transaction araya girip veriyi değiştirebilir (bu, non-repeatable read'in doğrudan sonucu bir bug sınıfıdır). Böyle durumlarda ya `SELECT ... FOR UPDATE` ile açık kilitleme, ya Repeatable Read/Snapshot Isolation, ya da Serializable + retry mantığı gerekir.

**"MVCC var, o zaman kilit yok" varsayımına düşmeyin.** Gördüğümüz gibi InnoDB gap lock/next-key lock kullanır; PostgreSQL da `FOR UPDATE`, `FOR SHARE` gibi açık satır kilitleri ve tablo seviyesinde çeşitli kilit modları sunar. MVCC yazar-yazar çakışmasını ortadan kaldırmaz, sadece okuyucu-yazar çakışmasını ortadan kaldırır. İki transaction aynı satırı aynı anda güncellemeye çalışırsa, biri diğerini bekler (ya da deadlock/serialization failure oluşur).

**Bloat ve wraparound izlemeyi operasyonel bir rutin haline getirin.** PostgreSQL'de `pg_stat_user_tables` üzerinden dead tuple oranını, `age(datfrozenxid)` üzerinden wraparound mesafesini izlemek; InnoDB'de `information_schema.INNODB_TRX` ve uzun süredir açık transaction'ları izlemek, MVCC tabanlı sistemlerde temel bir sağlık göstergesidir — CPU/RAM metrikleri kadar önemlidir ama çoğu zaman ihmal edilir.

**Serializable'ı "ücretsiz güvenlik" sanmayın.** Doğru araçtır ama retry mantığı, olası ekstra abort'lar ve SSI'ın kendi defter tutma (predicate lock benzeri izleme) yükü vardır. Yüksek çakışma oranı olan iş yüklerinde Serializable'ın abort oranı yükselebilir; bu durumda uygulama katmanında iyi bir retry-with-backoff stratejisi şarttır, yoksa kullanıcı tarafında görünen hatalar artar.

## Yaygın Hatalar

- Bir transaction'ın *başında* aldığı snapshot ile sorgu sonuçlarının hâlâ "canlı" veri olduğunu sanmak — Repeatable Read/Snapshot Isolation altında transaction boyunca gördüğünüz veri, transaction'ın başladığı andaki dondurulmuş görüntüdür; başkalarının yaptığı commit'ler sizin için görünmez kalır.
- "Neden bu `DELETE` sonrası tablo boyutu küçülmedi" şaşkınlığı — PostgreSQL'de fiziksel alan `VACUUM FULL` (tabloyu kilitleyen, ağır bir işlem) olmadan işletim sistemine iade edilmez; normal `VACUUM` alanı yeniden kullanılabilir yapar ama dosyayı küçültmez.
- Write skew'i "MVCC bozuk" sanmak — aslında bu, Snapshot Isolation'ın *tanımı gereği* kapsamadığı, bilinen ve belgelenmiş bir sınırdır; çözüm ya Serializable'a geçmek ya da açık kilitleme eklemektir.
- İzolasyon seviyesini yükseltmenin "her zaman daha güvenli, dolayısıyla her zaman tercih edilir" olduğunu düşünmek — daha yüksek izolasyon, daha fazla abort/retry ve genelde daha fazla defter tutma maliyeti demektir; doğru seviye iş mantığının gerçekte hangi anomaliye karşı savunmasız olduğuna göre seçilir, körü körüne en yükseğe çıkmak performans israfıdır.

## Özet

MVCC, "okuyucuları yazarlarla kilitlemeden tutarlı bir görüntü sunma" probleminin cevabıdır ve bunu her yazma işleminde yeni bir versiyon üreterek yapar. PostgreSQL bunu heap üzerinde çoklu tuple + `xmin`/`xmax` + vacuum ile, InnoDB ise yerinde güncelleme + undo log zinciri + purge thread ile çözer; ikisi de aynı hedefe farklı fiziksel yollardan ulaşır ve ikisinin de kendine özgü "eski versiyon birikmesi" operasyonel riski vardır. İzolasyon seviyeleri bu temel üzerine kurulur: Read Committed her sorguda yeni snapshot alır, Repeatable Read/Snapshot Isolation transaction boyunca tek snapshot kullanır (ve böylece non-repeatable read ile çoğu phantom'u önler), ama write skew gibi ince anomalilere karşı savunmasız kalır — bunun çözümü PostgreSQL'de SSI ile gerçek Serializable'dır, InnoDB'de ise MVCC'nin gap lock gibi kilitleme mekanizmalarıyla tamamlanmasıdır. Bir mühendis için pratik sonuç nettir: doğru izolasyon seviyesini bilinçli seçmek, uzun transaction'ları asla açık bırakmamak ve bloat/wraparound gibi MVCC'ye özgü sağlık göstergelerini izlemek, "veritabanı yavaşladı" tarzı gizemli production sorunlarının çoğunu baştan önler.
