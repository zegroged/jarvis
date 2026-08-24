# Write-Ahead Logging (WAL), Crash Recovery ve Durability Mekanizmaları

## Giriş: Bu Konu Neden Var

Bir veritabanı "COMMIT" dediği anda, o veriyi kaybetmeyeceğine dair bir söz vermiş olur. Bu söze **durability** (ACID'in D'si) denir. Ama fiziksel gerçek acımasızdır: bellek (RAM) uçucudur (volatile), disk yazmaları yavaştır, işletim sistemi sayfa önbellekleri (page cache) verinin gerçekten diske indiğini garanti etmez, ve enerji her an kesilebilir. Write-Ahead Logging (WAL), bu acımasız fizik ile "veri kaybetmeme" vaadi arasındaki köprüdür.

Bu konu bir eğitim korpusunda mutlaka olmalı çünkü:

1. **Veritabanı internals'in temel taşı.** İndeksleme, sorgu optimizasyonu gibi konuları anlamak için bile önce "veri nasıl kalıcı hale gelir" sorusunu anlamak gerekir.
2. **Yanlış yapılandırma doğrudan veri kaybına yol açar.** `fsync` kapatmak, `synchronous_commit=off` gibi ayarların ne anlama geldiğini bilmeyen bir mühendis, performans uğruna sessizce durability'den vazgeçebilir.
3. **Forensics ve olay analizi ile doğrudan ilişkili.** Bir sistem çökmesinden (crash) sonra "veritabanında ne oldu, hangi işlemler kayboldu, hangi işlemler geri alındı" sorusunun cevabı WAL/redo-undo log analizinden geçer. Disk forensics yapan biri, WAL dosyalarının formatını ve recovery mantığını bilmeden yanlış sonuç çıkarabilir — örneğin "commit edilmiş" gibi görünen ama aslında rollback edilmiş bir işlemi gerçek sanabilir.

Bu makale, mekanizmayı bir savunmacı/mühendis gözüyle, saldırı talimatı değil **anlama ve doğru yapılandırma/tespit** amacıyla anlatır.

---

## 1. Temel Problem: Durability Neden Zor?

Bir veritabanı işlemi (transaction) commit edildiğinde şu garantiler istenir (ACID):

- **Atomicity**: İşlem ya tamamen uygulanır ya da hiç uygulanmaz.
- **Consistency**: İşlem veritabanını bir geçerli durumdan başka bir geçerli duruma taşır.
- **Isolation**: Eş zamanlı işlemler birbirini görmez (concurrency control konusu, WAL'dan ayrı).
- **Durability**: Commit edilen veri, sistem çökse de kaybolmaz.

Sorun şudur: performans için veritabanı motorları veriyi bellekte tutulan sayfalarda (buffer pool / page cache) değiştirir. Her değişiklikte bütün veri sayfasını diske yazmak aşırı yavaştır (rastgele I/O, büyük sayfalar). Eğer sadece bellekte değişiklik yapılıp commit başarılı sayılırsa ve sonra elektrik kesilirse, o değişiklik yok olur — durability ihlali.

Naif çözüm "her commit'te tüm kirli (dirty) sayfaları diske yaz" olurdu, ama bu:
- Rastgele I/O olduğu için çok yavaştır.
- Bir sayfada birden fazla satırın değişikliği olabilir; her commit'te o sayfayı tekrar tekrar yazmak israftır.
- Sayfa yazılırken sistem çökerse, sayfa **yarım yazılmış (torn write)** halde kalabilir — bu da ayrı bir bozulma riski.

WAL'in çözdüğü problem tam olarak budur.

---

## 2. WAL'in Kök Mantığı: Önce Log, Sonra Veri

WAL kuralının özü tek cümleyle şöyle özetlenebilir:

> **Bir veri sayfasındaki değişiklik diske yazılmadan önce, o değişikliği açıklayan log kaydı diske (kalıcı depoya) yazılmış ve fsync edilmiş olmalıdır.**

Yani sıra şudur:
1. İşlem bir değişiklik yapar (örneğin bir satır güncellenir).
2. Bu değişiklik önce **log buffer**'a yazılır: "hangi sayfa, hangi offset, eski değer (undo/before-image), yeni değer (redo/after-image)".
3. Commit anında, log buffer'daki ilgili log kayıtları **fsync** ile kalıcı depoya yazılır (log flush). Commit, ancak bu fsync başarılı olduktan sonra istemciye "başarılı" diye dönülür.
4. Asıl veri sayfası (data page) bellekte "kirli" kalır; diske yazılması (checkpoint/background writer tarafından) daha sonra, tembel bir şekilde yapılabilir.

Bu tasarımın güzelliği: log dosyası **append-only (sadece sona ekleme)** olduğu için yazma sekanseldir (sequential I/O), bu da diskte (özellikle HDD'de, SSD'de de) veri sayfalarına rastgele yazmaktan çok daha hızlıdır. Böylece commit gecikmesi tek bir küçük sekansiyel yazmaya indirgenir; asıl büyük ve rastgele veri sayfası yazmaları arka planda, performans açısından uygun zamanda yapılır.

### Neden "önce log" sıralaması kritik?

Eğer tersi olsaydı — önce veri sayfası diske yazılsa, sonra log yazılsa — ve sistem tam bu arada çökse: diskte log'da olmayan ama veri sayfasında olan bir değişiklik kalırdı. Recovery sırasında bu değişikliğin commit edilip edilmediğini bilmenin hiçbir yolu olmaz, çünkü değişikliği açıklayan tek kayıt (log) yok. WAL kuralı bu belirsizliği ortadan kaldırır: log her zaman veriden "önde" olduğu için, recovery işlemi her zaman log'u referans alarak veri sayfalarının durumunu yeniden inşa edebilir.

---

## 3. Redo ve Undo Logları: İki Farklı Amaç

Log kayıtları genelde iki işlevi birden taşır (fiziksel/mantıksal log türüne göre değişir):

- **Redo (yeniden yap) bilgisi**: "Bu değişiklik commit edildiyse ve veri sayfasına henüz yazılmadıysa, bunu tekrar uygula." Crash sonrası, commit edilmiş ama sayfaya henüz yansımamış değişiklikleri geri getirmek için kullanılır.
- **Undo (geri al) bilgisi**: "Bu işlem commit edilmediyse (rollback edildi ya da crash anında hala açıktı), bu değişikliği geri al." Yarım kalmış işlemleri temizlemek için kullanılır.

Bu ayrım önemlidir çünkü bir crash anında diskteki durum üç türlü işlem barındırabilir:
1. Commit edilmiş ve sayfaya da yazılmış işlemler — dokunmaya gerek yok.
2. Commit edilmiş ama sayfaya henüz yazılmamış işlemler — **redo** gerekir (log'daki after-image tekrar uygulanır).
3. Commit edilmemiş (açık kalmış) işlemler — **undo** gerekir (log'daki before-image ile geri alınır).

Bu üç durumu ayırt edebilmek için log kayıtlarının transaction ID, commit/abort kayıtları ve sayfa-log sıralama bilgisi (LSN — Log Sequence Number) taşıması gerekir.

---

## 4. ARIES Algoritması: Sanayi Standardı Yaklaşım

Çoğu modern ilişkisel veritabanı motorunun (ya da onun türevlerinin) recovery mantığı, IBM'in 1990'larda yayınladığı **ARIES** (Algorithm for Recovery and Isolation Exploiting Semantics) algoritmasından esinlenir. Tam detayları motor motor değişir, ama temel fikir üç fazlıdır:

### Faz 1: Analysis (Analiz)
Log, son checkpoint'ten (veya log'un başından) itibaren okunur. Amaç: crash anında hangi işlemlerin açık (commit edilmemiş) olduğunu ve hangi sayfaların "kirli" (bellekte değişip diske yazılmamış) olabileceğini tespit etmek. Bu bilgi **Transaction Table** ve **Dirty Page Table** olarak yeniden inşa edilir.

### Faz 2: Redo (Yeniden Yapma)
Log, dirty page table'daki en eski gerekli noktadan itibaren **ileri yönde** tekrar oynatılır. Burada önemli bir nokta: ARIES *repeating history* prensibini kullanır — yani commit edilmiş olsun olmasın, log'daki her değişiklik ilk önce uygulanır (redo), sistem crash öncesindeki tam durumuna getirilir. Ayrım işlemi bir sonraki fazda yapılır.

### Faz 3: Undo (Geri Alma)
Redo tamamlandıktan sonra, analysis fazında tespit edilen "açık kalmış" (commit edilmemiş) işlemler **geriye yönde** log okunarak geri alınır (undo). Bu sırada undo işleminin kendisi de loglanır (compensation log records / CLR), böylece undo yarıda kesilse bile tekrar crash olursa nereden devam edileceği bilinir.

**Neden bu sıra (önce tüm redo, sonra undo)?** Çünkü bazı sayfalar birden fazla işlemin etkisini taşıyabilir ve doğru son durumu elde etmek için önce "gerçekte ne olmuştu" bilgisini tam olarak yeniden kurmak (redo ile), sonra "hangi kısmını geri almam gerekiyor" (undo ile) ayırmak gerekir. Önce undo yapıp sonra redo yapmaya çalışmak, sayfalar arası bağımlılıklar yüzünden tutarsızlığa yol açabilir.

---

## 5. Checkpointing: Log'u Sonsuza Kadar Büyütmemek

Log dosyası sürekli büyür; eğer hiçbir zaman "eski log kayıtlarına artık ihtiyacımız yok" denilmezse hem disk dolar hem de recovery süresi (crash sonrası tüm log'u baştan okumak) aşırı uzar.

**Checkpoint**, periyodik olarak şu işlemi yapan bir mekanizmadır: o ana kadar bellekte biriken kirli sayfaların bir kısmını/tamamını diske yazar (flush) ve "bu noktadan önce commit olup diske de yazılmış her şeyin log'a ihtiyacı yok" bilgisini kaydeder. Böylece recovery, log'un başından değil, en son checkpoint'ten başlayabilir.

İki genel yaklaşım vardır:
- **Sharp / consistent checkpoint**: Checkpoint sırasında tüm yazma işlemleri durdurulur, tüm kirli sayfalar diske yazılır, sonra checkpoint tamamlanmış sayılır. Basit ama uygulamayı checkpoint sırasında durdurur (throughput düşüşü).
- **Fuzzy checkpoint**: Checkpoint, sistem çalışmaya devam ederken başlar; "checkpoint başladığında hangi işlemler açıktı, hangi sayfalar kirliydi" bilgisini kaydeder, gerçek diske yazma işlemi arka planda kademeli devam eder. Çoğu modern sistem bunu kullanır çünkü kesinti yaratmaz.

Checkpoint sıklığı bir denge meselesidir: çok sık checkpoint I/O yükünü artırır, çok seyrek checkpoint ise crash sonrası recovery süresini (RTO — Recovery Time Objective) uzatır.

---

## 6. fsync ve Durability'nin Gerçek Anlamı

Burası en çok yanlış anlaşılan ve en çok gerçek dünya veri kaybına yol açan kısımdır.

`write()` sistem çağrısı verinin **işletim sistemi sayfa önbelleğine (OS page cache)** yazıldığını garanti eder — diske değil. Eğer elektrik kesilirse ve veri hala sadece page cache'teyse, o veri kaybolur. `fsync()` (veya eşdeğeri: `fdatasync`, `F_FULLFSYNC`, vs.) çağrısı, işletim sistemine "bu veriyi gerçekten kalıcı depoya (fiziksel diske) yaz ve ben dönene kadar bitir" der.

Ama bu bile katmanlı bir zincirdir; her katmanda "yalancı güvenlik" riski vardır:

1. **Uygulama → OS page cache**: `write()` yeterli değildir, `fsync()` gerekir.
2. **OS → disk kontrolcüsü**: Diskin kendi yazma önbelleği (disk write cache) olabilir. Eğer bu önbellek "yazma tamamlandı" der ama veri hala volatile disk cache'indeyse ve disk write cache flush edilmiyorsa, `fsync()` bile yanıltıcı olabilir.
3. **Disk write cache → kalıcı ortam**: Bazı disklerde write cache'i bypass eden veya flush eden bir mekanizma (`FUA` — Force Unit Access, ya da disk write cache'i kapatmak) gerekebilir; sanallaştırma/bulut ortamlarında bu katmanlar (hypervisor, network storage) daha da karmaşıklaşır.

**Mühendislik dersi**: "commit başarılı dendi" ile "veri gerçekten kalıcı depoda" arasında, doğru yapılandırılmamış bir sistemde önemli bir fark olabilir. Bu yüzden veritabanları genelde şu tür ayarlar sunar:

- PostgreSQL'de `fsync = off` veya `synchronous_commit = off` gibi ayarlar performans uğruna durability'den ödün verir. Bunlar test/geliştirme ortamında mantıklıdır ama production'da bilmeden açık bırakılırsa, "commit onaylandı" dediği halde crash sonrası o işlem kaybolabilir.
- `full_page_writes` (PostgreSQL) gibi ayarlar, torn page (yarım yazılmış sayfa) sorununu çözmek için ilk değişiklikte sayfanın tamamını log'a yazar; bunu kapatmak checkpoint sonrası ilk yazımda crash olursa sayfa bütünlüğünü riske atar.

---

## 7. Torn Writes ve Sayfa Bütünlüğü

Diskler genelde sektör boyutunda (512 bayt / 4KB) atomic yazma garantisi verir, ama veritabanı sayfaları genelde daha büyüktür (örneğin 8KB, 16KB). Eğer bir sayfa yazılırken tam ortasında elektrik kesilirse, sayfanın bir kısmı eski veri bir kısmı yeni veri ile karışık (torn) kalabilir. Bu, checksum hatalarına veya sessiz veri bozulmasına yol açar.

Savunma yaklaşımları:
- **Full page image logging**: Checkpoint sonrası bir sayfaya ilk kez dokunulduğunda, sayfanın tam önceki halini log'a yazmak (PostgreSQL'in `full_page_writes`'i budur). Torn write olursa, recovery bu tam imajdan sayfayı yeniden kurar.
- **Double-write buffer** (MySQL/InnoDB yaklaşımı): Sayfa asıl konumuna yazılmadan önce, önce ayrı bir "double write" alanına yazılır. Crash olursa, asıl sayfa bozuksa double-write alanından onarılır.
- **Checksum'lu sayfalar**: Her sayfaya bir checksum eklenerek, okuma sırasında bozulma tespit edilebilir (ama tek başına onarım sağlamaz, sadece tespit).

---

## 8. Group Commit: Performans ve Durability'yi Bir Arada Tutmak

Her commit için ayrı bir `fsync()` çağrısı yapmak pahalıdır (disk I/O gecikmesi, özellikle dönen diskte milisaniyeler mertebesinde). **Group commit (toplu commit)** tekniğinde, kısa bir zaman penceresinde biriken birden fazla işlemin log kayıtları **tek bir fsync** ile birlikte diske yazılır. Bu, throughput'u ciddi şekilde artırır çünkü fsync sayısı azalır, ama her işlem hafif bir gecikme (diğerlerini beklemek) yaşar. Bu, durability'den ödün vermeden performans kazanmanın klasik bir yoludur — çünkü her işlem hala kendi fsync'i tamamlanmadan "commit başarılı" dönmez.

---

## 9. Replikasyon ile İlişki: Yerel Durability Yetmeyebilir

WAL sadece tek makinede crash recovery sağlar; diskin kendisi bozulursa (fiziksel arıza) WAL da onunla beraber gider. Bu yüzden çoğu production sistemde WAL, **replikasyon**'un da temelidir: WAL kayıtları başka bir makineye (replica) gönderilir ve orada da uygulanır (streaming replication). Böylece durability, "tek diskin fsync'i" seviyesinden "birden fazla bağımsız makinenin onayladığı yazma" seviyesine çıkarılabilir (örneğin PostgreSQL'de `synchronous_commit = remote_apply` gibi ayarlar).

Bu, dağıtık sistemlerdeki genel "durability tanımı tek makineyle sınırlı değildir" prensibinin somut bir uygulamasıdır.

---

## 10. Yaygın Hatalar ve Tuzaklar

1. **Durability ayarlarını anlamadan değiştirmek**: `fsync=off` gibi bir ayarı "performans arttı" diye production'a almak, sessiz bir risk kabul etmektir. Bu tür ayarlar sadece; verinin tekrar üretilebilir olduğu (örneğin bir ETL scratch tablosu) veya kayıp kabul edilebilir senaryolarda mantıklıdır.
2. **Disk write cache'i göz ardı etmek**: Özellikle eski/ucuz donanımlarda veya yanlış yapılandırılmış sanal disklerde, işletim sistemi "fsync tamam" dese bile fiziksel diskin kendi önbelleği veriyi henüz kalıcı hale getirmemiş olabilir. Kurumsal ortamlarda "write cache enabled ama battery-backed değil" konfigürasyonu klasik bir risktir.
3. **Checkpoint sıklığını yanlış ayarlamak**: Çok seyrek checkpoint, crash sonrası recovery süresini (ve dolayısıyla downtime'ı) ciddi şekilde uzatır. Çok sık checkpoint ise gereksiz I/O yüküne ve performans düşüşüne yol açar.
4. **Log dosyalarını disk doluyor diye silmek**: WAL/log dosyaları, henüz checkpoint'e dahil edilmemiş veya henüz replikaya gönderilmemiş kritik bilgi taşıyor olabilir. Bunları elle silmek, hem crash recovery'yi hem de replikasyonu bozabilir — birçok "disk doldu, log dosyalarını sildim, veritabanı açılmadı" olayının kök nedeni budur.
5. **Forensics sırasında WAL'i yanlış yorumlamak**: Bir olay analizinde, log'da görünen bir işlemin **commit edilmiş** mi yoksa **rollback edilmiş** mi olduğunu ayırt etmeden "bu veri değişikliği gerçekleşti" sonucuna varmak yanlış olabilir. ARIES tarzı bir sistemde undo/CLR kayıtları da log'da yer alır; doğru analiz, commit/abort kayıtlarını ve transaction table'i dikkate almalıdır. Ham log'u "sıralı değişiklik listesi" gibi okuyup analiz etmek yanlış sonuç doğurur.
6. **Yedekleme (backup) ile WAL ilişkisini kopartmak**: Point-in-time recovery (PITR) yapan sistemlerde (örneğin PostgreSQL), fiziksel bir taban yedeği (base backup) tek başına yeterli değildir; o yedek alındıktan sonraki WAL kayıtlarının da saklanması/arşivlenmesi gerekir. Sadece taban yedeğini alıp WAL arşivlemeyi atlamak, "sadece o ana kadar geri dönebilirim" şeklinde gizli bir kısıtlama yaratır.

---

## 11. Tespit ve Savunma Önerileri (Mühendis/Savunmacı Perspektifi)

- **Yapılandırmayı denetleyin**: Kullandığınız veritabanının durability ile ilgili ayarlarını (`fsync`, `synchronous_commit`, `full_page_writes`, benzerleri) açıkça dokümante edin ve production/staging/dev için farklı profiller tanımlayın. "Varsayılan ayar neydi, kim değiştirdi" sorusuna her zaman cevap verilebilmeli.
- **Donanım katmanını doğrulayın**: Disklerin/SAN/bulut disklerinin write cache davranışını (battery-backed mi, fsync'i gerçekten disk'e mi indiriyor mu) test edin. Bu genelde "power-fail testing" ile (kontrollü ortamda enerji kesme testleri) doğrulanır.
- **Checkpoint ve log metriklerini izleyin**: Checkpoint sıklığı, log büyüme hızı, ve crash sonrası recovery süresi izlenmesi gereken operasyonel metriklerdir. Beklenmedik log büyümesi, arşivlemenin veya replikasyonun tıkandığına işaret edebilir.
- **Forensics/inceleme öncesi log formatını öğrenin**: Kullandığınız motorun (PostgreSQL WAL, MySQL InnoDB redo/undo log, SQLite WAL modu, vb.) log kayıt formatını, LSN yapısını ve commit/abort işaretleyicilerini anlamadan olay sonrası analiz yapmayın; yanlış yorumlama, gerçek olmayan bir "veri kaybı" veya "yetkisiz değişiklik" sonucuna varılmasına yol açabilir.
- **Replikasyon ile tek nokta bağımlılığını azaltın**: Kritik sistemlerde durability'yi tek diskin fsync'ine bırakmayın; senkron replikasyon (en az bir uzak kopyanın onayı) ile fiziksel diskin kendisi de bir hata noktası olmaktan çıkarılabilir.

---

## Özet

WAL, "önce niyeti kalıcı olarak kaydet, sonra gerçek veriyi rahatına yaz" ilkesine dayanan bir mekanizmadır. Bu ilke sayesinde performans (sekansiyel log yazma) ile durability (crash sonrası hiçbir commit edilmiş işlemin kaybolmaması) aynı anda sağlanabilir. ARIES gibi algoritmalar, crash sonrası hangi işlemlerin tekrar uygulanacağını (redo) ve hangilerinin geri alınacağını (undo) sistematik bir şekilde belirler; checkpointing bu sürecin süresini makul tutar; fsync ve ilgili donanım garantileri ise bütün bu yapının gerçekten "diske indiği" varsayımını doğrulayan kritik, sık unutulan halkadır. Bu mekanizmayı anlamayan bir mühendis hem yanlış performans/durability dengesi kurar hem de bir olay sonrası log verisini yanlış yorumlayarak hatalı sonuçlara varabilir.
