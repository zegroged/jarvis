# Dosya Sistemi İç Yapısı ve Depolama Motorları

## Giriş ve Kapsam

Dosya sistemi (file system), ham blok depolama aygıtı üzerinde adlandırılabilir dosya ve dizin soyutlaması kuran bir yazılım katmanıdır. Yüzeyde "dosya aç, yaz, kapat" gibi görünen bu soyutlamanın altında; **çökme tutarlılığı (crash consistency)**, **veri bütünlüğü (integrity)**, **eşzamanlı erişim** ve **alan yönetimi** gibi zor problemler yatar. Bu makale, modern dosya sistemlerinin iç yapısını üç ana tasarım ekseninde inceler: **journaling** (kayıt tutarak kurtarma), **copy-on-write (COW)** (yerinde yazma yerine kopyalayarak yazma) ve **inode / B-tree tabanlı meta veri organizasyonu**. Ayrıca disk adli bilişimi (forensics) açısından bu yapıların nasıl yorumlanması gerektiğine ve yaygın yanılgılara değinir.

Amaç mekanizmayı anlamak, veri bütünlüğü ve kurtarma senaryolarını doğru kurgulamak ve adli analizde hatalı çıkarımlardan kaçınmaktır.

---

## Temel Katman: Blok Aygıtı ve On-Disk Yapı

Bir disk (HDD veya SSD), dosya sistemine sabit boyutlu **sektörler** (klasik 512 bayt, modern 4K "Advanced Format") veya soyut **bloklar** sunar. Dosya sistemi bu blokları mantıksal olarak gruplar ve üzerine kendi veri yapılarını serer. Tipik olarak diskte şu bölgeler bulunur:

- **Superblock**: Dosya sisteminin kimliği ve global durumu. Blok boyutu, toplam blok/inode sayısı, boş alan sayaçları, journal konumu, sürüm ve bayraklar burada tutulur. Superblock bozulursa dosya sistemi mount edilemez; bu yüzden çoğu FS superblock'un birden fazla yedeğini diske dağıtır.
- **Meta veri alanları**: inode tabloları, blok/inode ayırma bitmap'leri (allocation bitmaps), B-tree kökleri.
- **Veri bölgesi**: Gerçek dosya içeriğinin tutulduğu bloklar.

**Kök neden**: Diskin kendisi "dosya" kavramını bilmez; yalnızca "şu blok numarasına şu baytları yaz/oku" der. Dosya, dizin, izin, zaman damgası gibi her şey dosya sisteminin bu ham bloklar üzerine kurduğu bir yorumlamadır. Adli bilişimin gücü de buradan gelir: silinen bir dosyanın meta verisi ve içerik blokları, dosya sistemi onları "boş" işaretlese bile fiziksel olarak diskte durabilir.

---

## inode: Dosyanın Kimliği

### Tanım

**inode** (index node), bir dosyanın adı hariç tüm meta verisini tutan sabit boyutlu bir yapıdır. Klasik Unix/Linux dosya sistemlerinde (ext2/3/4, XFS) her dosya ve dizin bir inode ile temsil edilir. inode içinde şunlar bulunur:

- Dosya tipi (normal dosya, dizin, sembolik link, aygıt vb.) ve izin bitleri (mode)
- Sahip (UID) ve grup (GID)
- Boyut
- Zaman damgaları: **atime** (erişim), **mtime** (içerik değişimi), **ctime** (inode/meta değişimi); bazı FS'lerde **crtime/btime** (oluşturulma)
- **Link sayısı (link count)**: Kaç dizin girdisinin bu inode'a işaret ettiği
- Veri bloklarının konumunu gösteren **blok işaretçileri**

### Kritik Ayrım: Dosya Adı inode'da Değildir

Yaygın bir yanılgı, dosya adının inode içinde olduğunu sanmaktır. Aslında **ad, dizinde tutulur**. Bir dizin, özünde `(ad → inode numarası)` eşlemelerinden oluşan bir tablodur. Bu ayrımın önemli sonuçları vardır:

- **Hard link**: Aynı inode'a birden fazla addan işaret edilebilir. `ln a b` komutu yeni bir dosya kopyalamaz; sadece dizine yeni bir girdi ekler ve inode'un link sayısını artırır. Dosya ancak link sayısı sıfıra düşünce ve hiçbir process onu açık tutmuyorken gerçekten serbest bırakılır.
- **Silme (unlink)**: Bir dosyayı silmek çoğu zaman içeriği sıfırlamaz. Yalnızca dizin girdisi kaldırılır ve inode link sayısı azaltılır. Bu, adli kurtarmanın temel dayanağıdır.

### Blok İşaretçileri: Doğrudan ve Dolaylı

Klasik ext ailesinde inode, sınırlı sayıda **doğrudan işaretçi** (direct pointer) ve ardından **tek/çift/üçlü dolaylı işaretçiler** (indirect pointers) taşır. Küçük dosyalar doğrudan işaretçilerle adreslenir; büyük dosyalar için işaretçi bloklarından oluşan bir ağaç kurulur. Bu tasarımın zayıflığı, çok büyük dosyalarda çok sayıda dolaylı okuma gerektirmesi ve parçalanmaya (fragmentation) açık olmasıdır.

**extent tabanlı adresleme**: ext4, XFS ve modern FS'ler işaretçi listesi yerine **extent** kullanır. Bir extent, "şu mantıksal ofsetten başlayarak N ardışık fiziksel blok" diyen kompakt bir tanımdır. Ardışık büyük dosyalar için extent hem yer tasarrufu sağlar hem de meta veri okuma sayısını düşürür.

---

## B-tree Tabanlı Dosya Sistemleri

Klasik bitmap ve sabit inode tablosu yaklaşımı, milyarlarca dosya, çok büyük dizinler ve anlık görüntü (snapshot) gibi ihtiyaçlarda ölçeklenmekte zorlanır. Modern yüksek performanslı dosya sistemleri (XFS, Btrfs, ZFS'in ağaç yapıları, APFS) meta veriyi **B-tree** veya B-tree varyantları (B+tree) ile organize eder.

**Kök neden**: B-tree, sıralı anahtarlar üzerinde logaritmik zamanda arama, ekleme ve silme sağlar; diskte dengeli kalır ve geniş dallanma faktörüyle ağaç yüksekliğini düşük tutarak disk erişim sayısını azaltır. Bu, çok büyük dizinlerde (`ls` bir milyon dosyalı klasörde) ve serbest alan yönetiminde belirleyici avantajdır.

Btrfs bunu uç noktaya taşır: **her şey ağaçtır**. inode'lar, dizin girdileri, extent referansları, checksum'lar ayrı B-tree'lerde anahtar-değer kayıtları olarak durur. Bu birleşik yapı, snapshot ve COW ile doğal biçimde uyumludur.

---

## Journaling: Çökme Tutarlılığı Problemi

### Sorun

Bir dosya oluşturmak tek atomik işlem değildir; birden çok bloğun güncellenmesini gerektirir: inode ayırma bitmap'i, yeni inode, dizin girdisi, blok bitmap'i, veri blokları. Diyelim ki sistem bu güncellemelerin ortasında elektrik kesintisiyle çöktü. Sonuç, **tutarsız bir dosya sistemidir**: dizin bir inode'a işaret ediyor ama inode "boş" işaretli, ya da bloklar hem dosyaya hem boş listeye ait görünüyor.

Journaling olmayan dosya sistemlerinde bu durumu **fsck** (file system check) düzeltir. fsck, tüm meta veriyi tarayarak tutarsızlıkları arar: iki dosyaya birden ait bloklar, sıfır link'li ama ayrılmış inode'lar, yanlış boş alan sayaçları. Sorun şu ki fsck taraması, disk büyüdükçe **saatler** sürebilir ve bu süre boyunca sistem hizmet dışıdır.

### Çözüm: Write-Ahead Journal

**Journaling**, değişiklikleri asıl konumlarına uygulamadan önce özel bir **journal** (günlük) alanına yazmaktır. Fikir, veritabanlarındaki **write-ahead logging (WAL)** ile aynıdır:

1. Yapılacak meta veri değişiklikleri bir **transaction** olarak journal'a yazılır.
2. Journal kaydı diske kalıcı olduğunda bir **commit** işareti eklenir.
3. Ancak bundan sonra değişiklikler asıl konumlarına uygulanır (checkpoint).

Çökme durumunda kurtarma basittir: journal okunur. **Commit edilmiş** ama henüz asıl konumlarına yazılmamış transaction'lar tekrar uygulanır (**redo**); commit edilmemiş kısmi transaction'lar yok sayılır. Böylece dosya sistemi ya değişikliğin tamamını görür ya da hiçbirini; asla yarım kalmış tutarsız bir ara duruma düşmez. Bu **atomiklik** garantisidir.

### Journaling Modları ve Kritik Bir Yanılgı

Journaling'in **neyi** koruduğu çok yanlış anlaşılır. ext3/ext4'te tipik olarak üç mod vardır:

- **Journal (data=journal)**: Hem meta veri hem veri journal'a yazılır. En güvenli, en yavaş; her şey iki kez yazılır.
- **Ordered (data=ordered, tipik varsayılan)**: Yalnızca meta veri journal'lanır, ama veri blokları meta veri commit'inden **önce** diske yazılmaya zorlanır. Böylece bir inode asla henüz yazılmamış çöp bloklara işaret etmez.
- **Writeback (data=writeback)**: Yalnızca meta veri journal'lanır, veri sıralama garantisi yoktur. Meta veri tutarlıdır ama çökme sonrası bir dosya doğru boyutta görünüp içinde eski çöp veri barındırabilir.

**Yaygın hata**: "Journaling verimi kurtarır" sanmak. Çoğu yaygın modda journaling yalnızca **meta verinin tutarlılığını** garanti eder, dosya içeriğinin en son halini değil. Journaling, fsck süresini kısaltmak için vardır; kullanıcı verisinin kaybolmayacağı anlamına gelmez. Uygulamalar hâlâ kritik anlarda `fsync()` çağırıp verinin gerçekten kalıcı olduğundan emin olmalıdır.

---

## Copy-on-Write (COW): Farklı Bir Felsefe

### Tanım

**Copy-on-write** dosya sistemleri (ZFS, Btrfs, APFS) journaling'e alternatif bir tutarlılık modeli kullanır. Temel kural: **var olan bir bloğun üzerine asla yazma**. Bir bloğu değiştirmek gerektiğinde içeriği **yeni bir boş bloğa** yazılır, eski blok değiştirilmeden yerinde kalır. Sonra bu değişikliği yansıtacak şekilde üstteki işaretçiler de yeni bloklara kopyalanarak güncellenir; bu, değişikliğin ağacın kökünde tek bir işaretçi (superblock/uberblock) atomik güncellemesiyle "yayınlanmasına" kadar yukarı doğru zincirleme ilerler.

### Kök Neden: Atomik Ağaç Güncellemesi

COW'da dosya sistemi kökten yapraklara bir ağaçtır. Bir değişiklik yapıldığında, kökten değişen yaprağa kadar olan tüm yol yeniden yazılır (**path copy**). Yeni ağaç tamamen diske yazıldıktan sonra, kök işaretçisi **tek bir atomik yazma** ile eski kökten yeni köke çevrilir. Bu an gelene kadar disk hâlâ eski, tutarlı ağacı gösterir.

**Sonuç**: Çökme her ne zaman olursa olsun disk her zaman geçerli bir durumdadır; ya eski tutarlı ağaç ya yeni tutarlı ağaç görülür. Bu yüzden ZFS ve Btrfs **journal gerektirmez** (ZFS'te ZIL adında ayrı bir amaçlı log vardır ama bu bir meta veri journal'ı değil, senkron yazma gecikmesini düşürmek içindir). fsck kavramı da klasik anlamda ortadan kalkar.

### COW'un Doğal Hediyeleri: Snapshot ve Checksum

COW modeli iki güçlü özelliği neredeyse bedava getirir:

- **Snapshot (anlık görüntü)**: Eski bloklar zaten yerinde durduğundan, bir anın durumunu dondurmak için o andaki kök işaretçisini saklamak yeterlidir. Snapshot alması anlıktır ve başlangıçta ek yer tutmaz; sadece sonradan değişen bloklar için yeni yer kullanılır (yer paylaşımı). Bu, yedekleme ve "önceki sürüme dönme" için idealdir.
- **Uçtan uca checksum**: ZFS ve Btrfs her blok için sağlama toplamı (checksum) tutar ve bunu **işaretçinin bulunduğu üst düğümde** saklar. Okuma sırasında checksum doğrulanır; uyuşmazsa (**silent data corruption / bit rot**) hata tespit edilir ve ayna/RAID varsa doğru kopyadan kurtarılır. Klasik dosya sistemleri bu tür sessiz bozulmayı fark etmez bile.

### COW'un Bedelleri ve Tuzakları

- **Fragmentation**: Yerinde güncelleme olmadığından, özellikle rastgele yazma yoğun ve dolu diskte veri hızla parçalanır. Sık güncellenen büyük dosyalar (veritabanı dosyaları, VM imajları) COW ile ciddi performans düşüşü yaşayabilir. Btrfs'te bu tür dosyalar için COW'u kapatan bir öznitelik (nodatacow) vardır; ancak bu checksum'ı da devre dışı bırakır.
- **Boş alan raporlaması**: Snapshot'lar eski blokları canlı tuttuğundan, `df` bir dosyayı sildiğinizde beklediğiniz alanı geri vermez. Alan ancak o bloğa referans veren tüm snapshot'lar silinince serbest kalır. Bu, operasyonda çok kafa karıştırır.
- **Write amplification**: Küçük bir değişiklik ağacın köküne kadar bir işaretçi zincirini yeniden yazdırır. Yoğun küçük yazmalarda toplam yazma miktarı artar.

---

## Journaling vs COW: Karşılaştırma

| Boyut | Journaling (ext4, XFS) | COW (ZFS, Btrfs, APFS) |
|---|---|---|
| Tutarlılık yöntemi | Değişikliği önce log'a yaz, sonra uygula | Yeni bloklara yaz, kökü atomik çevir |
| fsck | Gerekebilir; journal replay hızlandırır | Klasik fsck yok; scrub ile doğrulama |
| Snapshot | Doğal değil (LVM gibi alt katman gerekir) | Neredeyse bedava |
| Checksum | Genelde yalnızca meta veri (bazıları hiç) | Uçtan uca veri + meta veri |
| Yazma amplifikasyonu | Journal nedeniyle meta veri iki kez | Path-copy nedeniyle artabilir |
| Parçalanma | Yerinde güncelleme, daha az | COW nedeniyle daha fazla |

Doğru seçim iş yüküne bağlıdır: Yoğun rastgele yazma ve öngörülebilir gecikme isteyen sistemler XFS/ext4'ü, veri bütünlüğü ve snapshot önceliği olan depolama/yedekleme sistemleri ZFS/Btrfs'i tercih eder.

---

## Dayanıklılık Katmanı: Barriers, fsync ve Yazma Önbelleği

Tüm bu tutarlılık şemaları tek bir varsayıma dayanır: **journal commit'i veya kök güncellemesi gerçekten diske kalıcı olduğunda önce yazılması gerekenler zaten kalıcı olmuştur.** Ama diskler ve denetleyiciler yazmaları **önbellekte** tutup yeniden sıralayabilir.

Bu yüzden dosya sistemi, denetleyiciye "bu noktadan önceki her şey kalıcı olmadan sonrakilere geçme" diyen **write barrier** / **cache flush (FUA/FLUSH)** komutları gönderir. Eğer disk üzerindeki uçucu yazma önbelleği (volatile write cache) yanlış yapılandırma ya da yalan söyleyen ucuz donanım nedeniyle flush'ı gerçekten uygulamazsa, journaling veya COW'un tüm garantileri **çöker**. Adli ve operasyonel açıdan kritik bir gerçek: "journaling'im var" demek, güç kaybı testinden geçmiş sağlam bir depolama yığını olmadan garanti değildir.

Benzer şekilde `fsync()`, bir uygulamanın "yazdığım verinin şu an fiziksel olarak kalıcı olduğundan emin ol" demesidir. Veritabanları ve diğer dayanıklılık gerektiren yazılımlar doğruluk için `fsync()`'e güvenir; onu atlamak veya yanlış varsaymak veri kaybının en yaygın kök nedenlerindendir.

---

## Adli Bilişim Açısından Doğru Yorumlama

Disk adli bilişimi (disk forensics), bu iç yapıların bilinmesiyle güçlenir; bilinmemesiyle **yanlış çıkarımlara** yol açar. Kavramsal olarak dikkat edilmesi gerekenler:

### Silme, Yok Etme Değildir

Yukarıda belirtildiği gibi, `unlink` genelde yalnızca dizin girdisini kaldırır ve inode'u serbest işaretler. Veri blokları, üzerlerine yeni bir dosya yazılana kadar diskte kalabilir. **File carving** teknikleri, dosya sistemi meta verisi olmadan, ham diskte bilinen dosya imzalarını (magic bytes / header-footer) arayarak içerik kurtarır. Ancak burada dikkatli olmak gerekir: extent tabanlı ve parçalanmış dosyalarda ardışıklık varsayımı bozulur; carving eksik veya karışık veri döndürebilir.

### Zaman Damgalarını Aşırı Yorumlama Tuzağı

atime/mtime/ctime yorumlaması adli analizde çok hataya açıktır:

- **atime** genellikle performans için `relatime` veya `noatime` ile devre dışı/kısıtlıdır; "kullanıcı bu dosyaya şu an baktı" çıkarımı çoğu modern sistemde geçersizdir.
- **ctime**, dosya oluşturulma değil, inode meta verisinin son değişimidir; yanlışlıkla "oluşturulma zamanı" sanılır.
- Zaman damgaları kullanıcı alanından değiştirilebilir (**timestomping**). Bu yüzden ciddi analizde on-disk zaman damgalarını journal veya `$LogFile` gibi bağımsız kaynaklarla çapraz doğrulamak gerekir.

### Journal ve COW Adli Delil Olarak

- Journaling FS'lerin **journal alanı**, yakın geçmişteki meta veri işlemlerinin izini taşıyabilir; silinen dosyaların meta verisi burada bir süre görünebilir.
- COW FS'lerde **eski bloklar** ve snapshot'lar, değiştirilmiş ya da silinmiş verinin önceki hallerini barındırabilir. Bir snapshot'ın varlığı, "üzerine yazıldı sanılan" verinin hâlâ erişilebilir olması demektir.
- **NTFS** tarafında, adli açıdan zengin yapılar vardır: `$MFT` (Master File Table, inode'un muadili kayıtlar), `$LogFile` (journaling), `$UsnJrnl` (değişiklik günlüğü), ve **Alternate Data Streams (ADS)** gibi kolay gözden kaçan içerik saklama noktaları.

### SSD, TRIM ve Kurtarmanın Sınırı

Kritik bir modern gerçek: **SSD'lerde TRIM/discard**, dosya silindiğinde denetleyiciye "bu bloklar artık gereksiz" der ve arka planda **garbage collection** o blokları fiziksel olarak sıfırlayabilir. Bu durumda mantıksal kurtarma mümkün olsa bile fiziksel içerik geri gelmez. HDD'de geçerli olan "silinen veri diskte kalır" varsayımı, TRIM aktif SSD'lerde çoğu zaman **geçersizdir**. Adli görüntü alırken (imaging) bu farkı bilmemek yanlış beklentiye yol açar. Ayrıca SSD'lerdeki wear-leveling ve over-provisioning nedeniyle mantıksal blok adresinin gösterdiği fiziksel hücre zamanla değişir; bu da düşük seviye kurtarmayı karmaşıklaştırır.

---

## Yaygın Hatalar ve Doğru Uygulamalar

- **"Journaling veri kaybını önler" yanılgısı**: Çoğu modda yalnızca meta veri tutarlılığı korunur. Uygulama seviyesinde dayanıklılık için `fsync()` şarttır.
- **fsync'i atlamak / önbelleğe güvenmek**: Performans için `fsync` atlanırsa, güç kaybında "yazıldı sanılan" veri kaybolur. Bu, veritabanı ve mesaj kuyruğu tasarımında klasik bir bug kaynağıdır.
- **Yalan söyleyen donanım / bozuk barrier**: Ucuz denetleyiciler veya sanallaştırma katmanları flush'ı görmezden gelirse tüm tutarlılık garantileri kağıt üzerinde kalır. Güç kaybı testi yapılmalıdır.
- **COW'da disk doldurma tuzağı**: COW FS neredeyse dolu diskte dramatik yavaşlar ve silme bile yeni blok gerektirdiği için çıkmaza girebilir; belli bir doluluk eşiğinin altında tutulmalıdır.
- **Snapshot'ları unutmak**: Silinen dosyanın alanı geri gelmiyorsa, sorumlusu genelde birikmiş snapshot'lardır. Snapshot yaşam döngüsü yönetilmelidir.
- **Adli analizde zaman damgası aşırı-yorumu**: atime/ctime anlamını yanlış varsaymak ve timestomping olasılığını yok saymak hatalı sonuç kronolojisi üretir.
- **SSD kurtarmada HDD sezgisiyle davranmak**: TRIM aktifken silinen veriyi geri getirme beklentisi çoğu zaman gerçekçi değildir.

---

## Özet

Dosya sistemleri, ham blokları güvenilir ve adlandırılabilir depolamaya dönüştürmek için iki temel tutarlılık felsefesinden birini benimser: **journaling** (değişikliği önce log'a yazıp atomiklik sağlamak) ya da **copy-on-write** (yerinde yazmadan kaçınıp kökü atomik çevirmek). inode ve B-tree yapıları meta veriyi organize eder; extent ve checksum modern verimlilik ve bütünlük sağlar. Bu mekanizmaların hepsi, altta yatan donanımın flush garantilerine güvenir; bu güven kırıldığında tüm şema çöker. Adli açıdan ise silmenin yok etme olmadığını, zaman damgalarının aldatıcı olabileceğini ve SSD/TRIM'in kurtarma sınırlarını değiştirdiğini bilmek, doğru ve savunulabilir çıkarımların önkoşuludur. Derinlik burada güvenliğin ve veri güvenilirliğinin temelidir.
