# Veritabanı Replikasyon ve Sharding

Bir uygulama büyüdükçe tek bir veritabanı sunucusu er ya da geç yetersiz kalır. Bu yetersizlik iki farklı yüzden ortaya çıkar: ya sunucu gelen istek yükünü karşılayamaz (CPU, disk I/O, ağ doygunluğu), ya da verinin kendisi tek makineye sığmayacak kadar büyür. **Replikasyon** ve **sharding**, bu iki farklı probleme verilen iki farklı yapısal cevaptır. İkisi sık sık karıştırılır, hatta bazen birbirinin yerine kullanılır; oysa çözdükleri sorunlar temelde ayrıdır ve genellikle bir arada, birlikte kullanılırlar. Bu makale, replikasyonun ve sharding'in kök mantığını, read replica ile okuma ölçeğini, sharding anahtarının neden bir sistemin kaderini belirlediğini ve yazma (write) ölçeğinin neden en zor problem olduğunu derinlemesine ele alıyor.

## Temel Ayrım: Kopyalamak mı, Bölmek mi?

Replikasyon, **aynı verinin birden fazla kopyasını** farklı sunucularda tutmaktır. Diyelim ki bir `siparisler` tablonuz var; replikasyonda bu tablonun tamamı birincil (primary) sunucuda da bulunur, ikincil (replica) sunucuların her birinde de. Her kopya, teorik olarak aynı satırları içerir.

Sharding ise verinin **kendisini parçalara bölmek** ve her parçayı farklı bir sunucuda tutmaktır. `siparisler` tablonuzdaki 500 milyon satırı, örneğin müşteri kimliğine göre 10 parçaya ayırırsınız; her sunucu bu 500 milyonun yalnızca ~50 milyonunu barındırır. Hiçbir sunucuda tüm veri yoktur.

Bu ayrımı kavramak kritik, çünkü sundukları faydalar farklıdır. Replikasyon size **okuma ölçeği**, **yüksek erişilebilirlik (high availability)** ve **coğrafi yakınlık** kazandırır ama tek bir kopyanın taşıyabileceği yazma yükünü artırmaz — çünkü her yazma işleminin sonunda tüm kopyalara ulaşması gerekir. Sharding ise size hem **yazma ölçeği** hem **depolama ölçeği** kazandırır ama uygulama katmanına ciddi bir karmaşıklık yükler. Bir sonraki bölümlerde bu tavizlerin neden kaçınılmaz olduğunu göreceğiz.

## Read Replica: Okuma Ölçeğinin Mantığı

### Neden İşe Yarar?

Çoğu gerçek uygulamada okuma (read) trafiği, yazma (write) trafiğini büyük farkla geçer. Bir e-ticaret sitesinde bir ürün bir kez yazılır ama binlerce kez okunur; bir sosyal medya gönderisi bir kez oluşturulur ama milyonlarca kez görüntülenir. Okuma/yazma oranı 10:1, 100:1, hatta 1000:1 olabilir. İşte read replica'nın gücü buradan gelir: okuma yükünü birden çok sunucuya dağıtabilirsiniz.

Mantık şu: Birincil sunucu tüm yazma işlemlerini kabul eder. Yaptığı her değişikliği bir değişiklik akışı (MySQL'de binlog, PostgreSQL'de WAL — Write-Ahead Log) olarak üretir. Replica'lar bu akışı sürekli okur ve kendi kopyalarına aynen uygular. Böylece replica'lar birincil ile "aynı" veriyi tutmaya çalışır. Uygulamanız okuma sorgularını replica'lara, yazma sorgularını birincil sunucuya yönlendirdiğinde, birincil sunucu üzerindeki okuma baskısı büyük ölçüde hafifler ve okuma kapasitesini yeni replica ekleyerek neredeyse doğrusal biçimde artırabilirsiniz.

### Kök Neden: Replikasyon Neden Yazma Ölçeği Vermez?

Burası çok kişinin gözden kaçırdığı nokta. Replica eklemek okuma ölçeğini artırır ama yazma ölçeğini **artırmaz**, çünkü her yazma işleminin eninde sonunda **her** kopyada tekrar uygulanması gerekir. 10 replica'nız varsa, birincilde yaptığınız bir INSERT işlemi 10 replica'da da tekrar çalışır. Yani yazma yükü azalmaz, hatta toplamda (tüm makineler dahil) çoğalır. Replica sayısını artırmak yazma kapasitesini büyütmez; tam tersine birincil sunucunun beslemesi gereken replica sayısı arttıkça replikasyon ağ yükü ve gecikmesi büyür. Yazma ölçeği için başka bir yapıya, yani sharding'e ihtiyaç duyulmasının kök nedeni budur.

### Replication Lag ve Read-Your-Own-Writes Problemi

Read replica'nın en sinsi tuzağı **replication lag**'dır (replikasyon gecikmesi). Replica'lar, birincilin değişiklik akışını asenkron olarak uygular. Bu, bir yazma işlemi birincilde tamamlandıktan sonra replica'ya ulaşmasının milisaniyeler, ağır yük altında saniyeler, hatta bazen dakikalar sürebileceği anlamına gelir.

Somut senaryo: Kullanıcı profilindeki adını değiştirir. Yazma birincile gider ve başarıyla tamamlanır. Uygulama hemen ardından profil sayfasını yeniden yükler, ama bu okumayı bir replica'ya yönlendirir. Replica henüz güncellemeyi almadıysa kullanıcı **eski adını** görür. Kullanıcının kendi yazdığını okuyamaması — literatürde **read-your-own-writes** ihlali — kafa karıştırıcı ve güven sarsıcıdır.

Bu problem, asenkron replikasyonun doğasından gelir ve tamamen kaçınmak mümkün değildir; yönetmek gerekir. Yaygın çözümler:

- **Kritik okumaları birincile yönlendirmek:** Bir yazmanın hemen ardından gelen okumayı (aynı kullanıcının kendi verisini) belirli bir süre birincilden okumak. Basit ve etkili ama birincil üzerindeki yükü bir miktar geri getirir.
- **Session/token bazlı tutarlılık:** Yazmadan sonra WAL/binlog pozisyonunu (LSN veya GTID) saklamak; okuma yaparken replica'nın o pozisyona ulaşıp ulaşmadığını kontrol edip yeterince güncel replica'yı seçmek.
- **Gecikme eşiği ile replica eleme:** Gecikmesi belli bir eşiği aşan replica'ları okuma havuzundan geçici olarak çıkarmak.

Buradaki temel gerçek şudur: read replica'lar **eventual consistency** (nihai tutarlılık) sunar. Okuduğunuz veri "bir süre önce doğruydu" garantisi verir, "şu an kesinlikle güncel" garantisi vermez. Uygulamanızın hangi okumaları için bunun kabul edilebilir olduğunu bilinçli olarak kararlaştırmanız gerekir. Ürün listesini biraz eski görmek sorun değildir; banka bakiyesini yazma sonrası eski görmek felakettir.

### Senkron mu Asenkron mu?

Replikasyon **asenkron**, **yarı-senkron (semi-synchronous)** veya **senkron** olabilir ve bu seçim doğrudan bir tutarlılık/performans/dayanıklılık tavizidir.

- **Asenkron:** Birincil, yazmayı yerelde işler ve replica'ya ulaşmasını beklemeden istemciye "tamam" der. En hızlısıdır ama birincil çökerse ve o son yazmalar henüz replica'ya gitmemişse **veri kaybı** olur.
- **Senkron:** Birincil, yazmanın (en az bir) replica tarafından onaylanmasını beklemeden istemciye başarı dönmez. Veri kaybı riski en aza iner ama her yazmaya ağ gidiş-dönüşü eklendiği için yazma gecikmesi artar; onaylayan replica yavaşlarsa birincil de yavaşlar.
- **Yarı-senkron:** İkisinin arasında bir uzlaşma; genelde en az bir replica'nın değişikliği **almış** olmasını bekler ama diske uygulamasını beklemez.

Doğru seçim, kaybetmeye tahammül edebileceğiniz veri miktarına (RPO — Recovery Point Objective) ve tolere edebileceğiniz yazma gecikmesine bağlıdır. Finansal işlemlerde senkron veya yarı-senkron tercih edilirken, analitik/log verilerinde asenkron makuldür.

### Failover ve Yüksek Erişilebilirlik

Read replica'nın ikinci büyük faydası okuma ölçeğinden bağımsızdır: **yüksek erişilebilirlik**. Birincil sunucu çökerse, bir replica terfi ettirilip (promote) yeni birincil yapılabilir. Bu **failover** sürecidir. Ancak burada iki büyük tehlike vardır:

- **Split-brain:** Eski birincil aslında ölmemiş, sadece ağ bölünmesi (network partition) nedeniyle erişilemez hale gelmişse ve bu sırada bir replica birincile terfi ettirilirse, ortada **iki birincil** oluşur. İkisi de yazma kabul eder ve veriler çatallanır. Bunu önlemek için genellikle bir **fencing** mekanizması (eski birincili zorla devre dışı bırakma, STONITH) veya bir dış koordinatör (consensus tabanlı, ör. Raft) tarafından yönetilen çoğunluk (quorum) kararı gerekir.
- **Veri kaybı:** Asenkron replikasyonda terfi eden replica, çöken birincilin son yazmalarını almamış olabilir; bu yazmalar failover'da kaybolur.

## Sharding: Verinin Kendisini Bölmek

### Neden Gerekli?

Tek makineye sığmayan veri ya da tek birincilin kaldıramayacağı yazma yükü olduğunda replikasyon çare olmaz — çünkü gördüğümüz gibi her yazma her kopyada tekrarlanır. Çözüm, veriyi bölmek ve yazma yükünü birden çok bağımsız birincile dağıtmaktır. İşte sharding budur: veri **shard** denen parçalara bölünür, her shard kendi sunucusunda (çoğunlukla kendi replica'larıyla) yaşar. Böylece hem depolama hem yazma yükü, shard sayısıyla ölçeklenir.

Kritik nokta: Sharding'de her shard **bağımsız bir birincile** sahip olduğu için, sistemin toplam yazma kapasitesi shard sayısıyla artar. 10 shard varsa, teorik olarak 10 kat yazma kapasitesi elde edersiniz. Yazma ölçeğinin tek gerçek çözümü budur.

### Sharding Anahtarı: En Kritik Karar

Sharding'in kaderini belirleyen tek karar, **sharding anahtarının (shard key / partition key)** seçimidir. Sharding anahtarı, bir satırın hangi shard'a gideceğini belirleyen sütun(lar)dır. Bu seçim, sistemi kurduktan sonra değiştirmesi son derece zor — çoğu zaman tüm veriyi yeniden dağıtmayı (resharding) gerektiren — bir karardır. Bu yüzden en baştan doğru düşünmek şarttır.

İyi bir sharding anahtarının taşıması gereken üç özellik vardır ve bunlar çoğu zaman gerilim içindedir:

1. **Yüksek kardinalite ve düzgün dağılım:** Anahtar, veriyi shard'lar arasında dengeli dağıtmalı. Örneğin `ulke` sütununu anahtar yaparsanız ve trafiğinizin %70'i tek ülkeden geliyorsa, bir shard aşırı yüklenirken diğerleri boş kalır. Bu **hot shard** problemidir.
2. **Sorgu yerelliği (query locality):** Uygulamanızın çoğu sorgusu, tek bir shard'dan cevaplanabilmeli. Anahtar kötü seçilirse, sık yapılan sorgular **tüm shard'lara** dağılmak zorunda kalır (scatter-gather); bu, sharding'in performans avantajını yok eder.
3. **Değişmezlik:** İdeal olarak, bir satırın shard anahtarı zamanla değişmemeli. Değişirse, satırı bir shard'dan diğerine taşımanız gerekir ki bu pahalı ve karmaşıktır.

Somut örnek: Çok kiracılı (multi-tenant) bir SaaS uygulamasında `kiraci_id` (tenant_id) genellikle mükemmel bir sharding anahtarıdır. Çünkü hemen her sorgu tek bir kiracının verisiyle ilgilenir (sorgu yerelliği yüksektir), kiracılar veriyi doğal olarak böler ve bir kaydın kiracısı değişmez. Buna karşılık, `siparis_tarihi` gibi bir zaman sütununu anahtar yapmak felakettir: en yeni shard tüm yeni yazmaları çeker (hot shard), eski shard'lar atıl kalır.

### Aralık, Hash ve Dizin Tabanlı Sharding

Bir satırı shard'a eşlemenin üç ana yöntemi vardır ve her birinin kendine has bir gerilimi var:

- **Aralık tabanlı (range) sharding:** Anahtar değer aralıklarına göre bölünür (ör. A–H bir shard'da, I–P diğerinde). **Aralık sorgularını** verimli kılar ama düzgün dağıtmak zordur ve kolayca hot shard oluşturur (yeni kayıtlar hep son aralığa düşerse). Ardışık artan bir anahtarla (auto-increment ID, timestamp) birleşince en son shard bir "sıcak nokta" haline gelir.
- **Hash tabanlı sharding:** Anahtar bir hash fonksiyonundan geçirilir ve sonuç shard'a eşlenir. Dağılımı çok düzgün yapar, hot shard riskini büyük ölçüde düşürür. Bedeli: aralık sorguları artık tüm shard'lara dağılmak zorundadır, çünkü ardışık değerler farklı shard'lara serpilmiştir.
- **Dizin/arama (lookup/directory) tabanlı sharding:** Ayrı bir eşleme tablosu hangi anahtarın hangi shard'da olduğunu tutar. En esnek yöntemdir (shard'ları istediğiniz gibi yeniden dengeleyebilirsiniz) ama bu dizin bir tekil arıza noktası (single point of failure) ve her sorguya bir ek adım ekler.

### Naif Hash'in Tuzağı ve Consistent Hashing

Sık yapılan bir hata, `shard = hash(anahtar) % N` (N = shard sayısı) formülünü kullanmaktır. Bu, N sabitken çalışır. Ancak shard eklediğinizde veya çıkardığınızda N değişir ve **hemen hemen tüm anahtarların** shard eşlemesi değişir — yani neredeyse tüm veriyi yeniden taşımanız gerekir. Bu, üretim ortamında son derece maliyetli, hatta yıkıcıdır.

**Consistent hashing** (ve pratikte sık kullanılan **sanal düğüm / virtual node** varyantı) bu problemi çözmek için tasarlanmıştır. Anahtarları ve shard'ları aynı dairesel hash uzayına yerleştirir; bir shard eklendiğinde yalnızca **komşu bölgedeki** anahtarların yeri değişir, geri kalan her şey yerinde kalır. Böylece resharding maliyeti tüm veri yerine yalnızca küçük bir orana iner. Ölçeklenmesi gereken sistemlerde consistent hashing, naif modulo yaklaşımına neredeyse her zaman tercih edilir.

## Sharding'in Bedelleri: Neyi Kaybediyorsunuz?

Sharding güçlüdür ama tek makinelik bir veritabanının verdiği bazı garantileri elinizden alır. Bu bedelleri baştan bilmek, sonradan acı çekmemenin tek yoludur.

### Shard'lar Arası JOIN ve Toplama (Aggregation) Kaybı

Tek veritabanında iki tabloyu bir JOIN ile birleştirmek doğaldır. Ama ilgili satırlar farklı shard'larda yaşıyorsa, veritabanı bunu tek başına yapamaz. Ya sorguyu uygulama katmanında birden çok shard'a gönderip sonuçları elle birleştirirsiniz (scatter-gather, yavaş ve karmaşık), ya da veri modelinizi ilgili verinin **aynı shard'da** kalacağı biçimde tasarlarsınız. İşte bu yüzden sharding anahtarını, sık birlikte sorgulanan verileri aynı shard'a düşürecek şekilde seçmek (**colocation / birlikte yerleştirme**) hayati önemdedir. Örneğin bir kullanıcının kendisi ve tüm siparişleri aynı `kullanici_id` shard'ında tutulursa, "kullanıcı ve siparişleri" sorgusu tek shard'dan cevaplanır.

Aynı şekilde, `COUNT`, `SUM`, `ORDER BY ... LIMIT` gibi tüm veri kümesi üzerinde çalışan toplama sorguları da artık her shard'da ayrı çalışıp sonra birleştirilmelidir. Global bir "en yeni 10 kayıt" sorgusu, her shard'dan en yeni 10'ar kaydı çekip uygulama katmanında yeniden sıralamayı gerektirir.

### Dağıtık İşlemler (Distributed Transactions) ve Atomiklik Kaybı

Tek veritabanında bir işlem (transaction) birden çok tabloyu atomik olarak değiştirebilir: ya hepsi olur ya hiçbiri (ACID). Ama iki değişiklik iki farklı shard'daysa, tek bir yerel işlem bunu garanti edemez. Klasik örnek: A shard'ındaki hesaptan para düşüp B shard'ındaki hesaba eklemek.

Bunun için ya **two-phase commit (2PC)** gibi dağıtık işlem protokolleri kullanılır — ki bunlar yavaştır, koordinatör bir arıza noktasıdır ve kilitlenmeye açıktır — ya da mimari **saga** desenine kaydırılır: işlemi bir dizi yerel işlem ve telafi (compensation) adımından oluşan bir akışa bölüp nihai tutarlılığı kabul edersiniz. Pratikte olgun ekiplerin çoğu, shard'lar arası atomik işlem ihtiyacını **veri modelini yeniden düşünerek ortadan kaldırmayı** tercih eder; çünkü dağıtık işlemlerle yaşamak zordur.

### Benzersiz Kimlik (Unique ID) Üretimi

Tek veritabanında `AUTO_INCREMENT` veya `SEQUENCE` benzersiz kimlikleri kolayca üretir. Ama her shard bağımsız olduğundan, iki farklı shard aynı auto-increment değerini üretip çakışma yaratabilir. Çözümler: UUID kullanmak (yer kaplar ve indeks yerelliği kötüdür), her shard'a farklı bir aralık/ofset atamak, ya da Snowflake benzeri (zaman + makine kimliği + sıra numarasını birleştiren) dağıtık kimlik üreticileri kullanmak.

## Replikasyon ve Sharding Birlikte

Gerçek üretim sistemlerinde bu ikisi neredeyse her zaman **birlikte** kullanılır. Tipik desen şudur: veri N shard'a bölünür (yazma ölçeği ve depolama için) ve her shard'ın kendi read replica'ları vardır (o shard için okuma ölçeği ve yüksek erişilebilirlik için). Böylece:

- Sharding, **yazma ve depolama** ölçeğini verir.
- Her shard içindeki replikasyon, o shard'ın **okuma** ölçeğini ve **failover** dayanıklılığını verir.

Bu katmanlı yapı, ikisinin farklı problemleri çözdüğü gerçeğini somutlaştırır: sharding "veri sığmıyor / yazma yetişmiyor" sorununu, replikasyon "okuma yetişmiyor / sunucu çökerse ne olacak" sorununu çözer.

## Yaygın Hatalar

- **Erken sharding:** Sharding, karmaşıklığı ciddi biçimde artırır (dağıtık işlemler, cross-shard JOIN kaybı, resharding zorluğu). Henüz tek makinenin sınırlarına dayanmadan sharding yapmak, kazanmadığınız bir ölçek için büyük bir bakım borcu ödemektir. Önce dikey ölçekleme (daha güçlü makine), okuma için read replica ve önbellekleme (caching) tüketilmeli; sharding son çare olmalıdır.
- **Kötü sharding anahtarı:** En pahalı hata. Hot shard'a yol açan (ör. zaman veya artan ID tabanlı) ya da sorgu yerelliğini bozan bir anahtar seçmek, sonradan resharding gerektirir ki bu, çalışan bir sistemde en zorlu operasyonlardan biridir.
- **Replication lag'i yok saymak:** Read replica'yı senkronmuş gibi kullanmak, read-your-own-writes hatalarına ve tutarsız kullanıcı deneyimine yol açar. Hangi okumanın bayat (stale) veri tolere edebileceğini açıkça kararlaştırmamak.
- **Failover'ı test etmemek:** Failover mekanizması, gerçek bir arızada ilk kez çalıştığında beklenmedik biçimde kırılır. Split-brain koruması, fencing ve otomatik terfi süreçleri düzenli olarak (kaos mühendisliği tarzı) provasız bırakılmamalıdır.
- **Naif modulo hashing:** `hash % N` kullanıp sonra shard eklemek zorunda kalmak, neredeyse tüm veriyi taşımayı gerektirir. Consistent hashing baştan düşünülmelidir.

## En İyi Pratikler

- **Önce daha basit çözümleri tüketin.** Dikey ölçekleme, read replica ve agresif önbellekleme, çoğu uygulamanın ölçek ihtiyacını sharding'e hiç gerek kalmadan karşılar. Sharding'e ancak yazma veya depolama tek makineyi gerçekten aştığında geçin.
- **Sharding anahtarını en baştan, sorgu desenlerinize göre seçin.** En sık ve en kritik sorgularınızın tek shard'dan cevaplanabileceği, sık birlikte sorgulanan verilerin aynı shard'a düşeceği bir anahtar seçin. Kardinalitesi yüksek, dağılımı düzgün ve zamanla değişmeyen bir sütun ideal.
- **Okuma tutarlılığı ihtiyaçlarını sınıflandırın.** Her okuma için "bu, bayat veriyi tolere eder mi?" sorusunu yanıtlayın. Tolere edenler replica'ya, edemeyenler (özellikle read-your-own-writes gerektirenler) birincile veya güncelliği doğrulanmış replica'ya gitsin.
- **Failover'ı otomatikleştirin ve düzenli test edin.** Consensus/quorum tabanlı bir koordinatör, fencing ve split-brain koruması kullanın; failover'ı üretimde ilk kez arıza anında denemeyin.
- **Resharding'i baştan planlayın.** Consistent hashing veya dizin tabanlı eşleme kullanarak, gelecekte shard ekleme/çıkarmayı katlanılabilir kılın. Bir gün mutlaka yeniden dengelemek zorunda kalacağınızı varsayın.
- **RPO ve gecikme hedeflerinize göre replikasyon modunu seçin.** Veri kaybına tahammülü düşük iş yükleri için senkron/yarı-senkron; gecikmeye duyarlı ve bir miktar veri kaybını tolere edebilen iş yükleri için asenkron.

## Özet

Replikasyon ve sharding farklı iki soruna verilen iki ayrı cevaptır. Replikasyon veriyi kopyalar; okuma ölçeği ve yüksek erişilebilirlik sağlar ama yazma ölçeği vermez — çünkü her yazma her kopyada tekrar uygulanır. Read replica'lar okuma yükünü dağıtır ama nihai tutarlılık ve replication lag ile birlikte gelir; read-your-own-writes gibi tuzaklar bilinçli yönetilmelidir. Sharding ise veriyi böler; yazma ve depolama ölçeğini gerçekten veren tek yapıdır, ama JOIN, atomik işlem ve benzersiz kimlik gibi tek makinelik garantileri elinizden alır. Sistemin kaderini belirleyen tek karar sharding anahtarının seçimidir; yanlış seçim hot shard ve maliyetli resharding demektir. Üretimde ikisi katmanlı olarak birlikte kullanılır: shard'lar yazmayı ölçekler, her shard'ın replica'ları okumayı ölçekler ve dayanıklılığı sağlar. Altın kural değişmez: sharding'i, daha basit çözümler gerçekten tükendiğinde ve son çare olarak uygulayın.
