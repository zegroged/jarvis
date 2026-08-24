# CAP Teoremi ve Tutarlılık

## Giriş ve Tanım

CAP teoremi, dağıtık (distributed) veri sistemlerinin doğasında bulunan temel bir ödünleşimi (trade-off) tarif eder. Teorem, ilk olarak 2000 yılında Eric Brewer tarafından bir varsayım olarak ortaya atılmış, 2002'de Seth Gilbert ve Nancy Lynch tarafından biçimsel (formal) olarak kanıtlanmıştır. İfadesi kısaca şudur: Bir dağıtık veri deposu, aşağıdaki üç özelliğin en fazla **ikisini** aynı anda garanti edebilir:

- **Consistency (Tutarlılık, C):** Her okuma, ya en son yazılan veriyi döndürür ya da bir hata döndürür. Buradaki "tutarlılık" ACID'deki tutarlılıktan farklıdır; CAP bağlamında kastedilen aslında **linearizability** (doğrusallaştırılabilirlik) denen güçlü bir modeldir. Yani sistem, dışarıdan bakan bir gözlemciye sanki tek bir kopya varmış gibi görünür.
- **Availability (Erişilebilirlik, A):** Çökmemiş (non-failing) her node, her isteğe makul bir sürede — hata olmayan — bir yanıt verir. Yanıtın en güncel veri olması şart değildir; önemli olan sistemin yanıt vermeyi reddetmemesidir.
- **Partition Tolerance (Bölünme Toleransı, P):** Node'lar arasındaki ağ (network) rastgele sayıda mesajı düşürse (drop) veya geciktirse bile sistem çalışmaya devam eder.

Teoremin en çok yanlış anlaşılan yanı, "üçünden ikisini seç" şeklindeki popüler ama yanıltıcı özetidir. Gerçek hayatta P bir seçenek değil, bir **zorunluluktur**. Bu ayrımı anlamak, teoremin özünü kavramanın anahtarıdır.

## Kök Neden: Neden Böyle Olmak Zorunda?

CAP'in neden kaçınılmaz olduğunu anlamak için ağ bölünmesi (network partition) anını mikroskop altına almak gerekir. Bir bölünme, iki node grubunun birbiriyle iletişim kuramadığı durumdur; kablo koptu, switch bozuldu, bir veri merkezi (data center) diğerinden koptu veya sadece paketler kaybolmaya başladı.

Şimdi somut bir düşünce deneyi yapalım. Elimizde `N1` ve `N2` adında iki node var ve aralarında bir `x` değişkeninin kopyası (replica) tutuluyor. Başlangıçta ikisinde de `x = 0`. Aniden `N1` ile `N2` arasındaki ağ koptu. Bu sırada:

- Bir istemci (client) `N1`'e gelip `x = 1` yazmak istiyor.
- Aynı anda başka bir istemci `N2`'ye gelip `x`'in değerini okumak istiyor.

Sistem burada **çözülemez bir ikilemle** karşı karşıyadır:

1. Eğer `N1` yazmayı kabul eder ve `N2` de okumaya `0` yanıtı verirse — her ikisi de erişilebilir (available) davranmıştır ama sistem **tutarsız** hale gelmiştir. Okuyan istemci eski veriyi görmüştür. C feda edilmiştir, A korunmuştur.
2. Eğer sistem tutarlılığı korumak isterse, `N2`'nin okuma isteğine ya yanıt vermemesi ya da hata dönmesi gerekir — çünkü `N2`, `N1`'deki güncellemeden haberdar olamaz. Bu durumda **tutarlılık** korunur ama `N2` **erişilebilir** olmaktan çıkar. A feda edilmiştir, C korunmuştur.

İşte kök neden budur: **Bölünme sırasında, bir yazma bir tarafta gerçekleşmiş ancak diğer tarafa yayılamıyorsa, o diğer taraf ya eski veriyi verecek (tutarsızlık) ya da yanıt vermeyecektir (erişilemezlik).** Fizik ve bilgi teorisi gereği, mesajın ulaşamadığı bir node güncel gerçeği bilemez. Bilmediği bir şeyi ne tutarlı biçimde verebilir ne de o bilgiyi uydurabilir. Bu, kötü mühendisliğin değil, dağıtık sistemin doğasının dayattığı bir kısıttır.

Bu yüzden teoremin doğru okunuşu şudur: **Ağ bölünmesi (P) gerçekleştiğinde, C ile A arasında seçim yapmak zorundasın.** Bölünme yokken böyle bir zorunluluk yoktur; sistem hem tutarlı hem erişilebilir olabilir.

## P Bir Seçenek Değildir

"CA sistemi kurayım, bölünme toleransından vazgeçeyim" cümlesi teoride kulağa mantıklı gelir ama pratikte anlamsızdır. Çünkü ağ bölünmeleri sizin izniniz olmadan gerçekleşir. Ethernet kabloları kopar, router'lar yeniden başlar, garbage collection duraklamaları bir node'u saniyelerce sessizleştirir, bir veri merkezi elektriği kaybeder. Siz "bölünmeyi kabul etmiyorum" diyemezsiniz; bölünme size sorup gelmez.

Dolayısıyla birden fazla node üzerinde çalışan **her gerçek dağıtık sistem P'yi tolere etmek zorundadır**. Bu, seçimi ikili bir tercihe indirger:

- **CP sistemleri:** Bölünme anında tutarlılığı korur, erişilebilirlikten feragat eder.
- **AP sistemleri:** Bölünme anında erişilebilirliği korur, tutarlılıktan feragat eder.

"CA sistemi" dediğimiz şey ancak tek node'lu (single-node) bir veritabanıdır — ki orada zaten dağıtık bir bölünme kavramı yoktur. Tek makinede çalışan klasik bir PostgreSQL örneği CA'dır çünkü bölünecek bir ağ yoktur. Ağ araya girdiği anda oyun değişir.

## CP Sistemleri: Tutarlılığı Önceleyenler

CP bir sistem, tutarsız veri vermektense hiç veri vermemeyi tercih eder. Kök mantık şudur: Bazı iş alanlarında yanlış cevap, "cevap yok" cevabından çok daha maliyetlidir.

Klasik örnek bir **banka çekirdek defteri (core ledger)** veya bir **envanter/stok yönetimi** sistemidir. Bir hesabın bakiyesini iki farklı değerle göstermek, ya da elinizde 1 adet kalmış ürünü iki müşteriye birden satmak felakettir. Böyle bir sistem, bölünme sırasında azınlıkta (minority) kalan tarafın yazma — hatta bazen okuma — isteklerini reddeder.

Bunu sağlamak için CP sistemleri genellikle bir **consensus (uzlaşı) protokolü** kullanır: Raft veya Paxos gibi. Bu protokollerin çekirdek fikri **çoğunluk (quorum / majority) kuralıdır.** Toplam `N` node'dan oluşan bir kümede, bir yazmanın "kesinleşmiş" (committed) sayılması için en az `(N/2) + 1` node'un onaylaması gerekir. Bölünme olduğunda:

- Çoğunluğu barındıran taraf çalışmaya devam eder çünkü quorum'u sağlayabilir.
- Azınlıkta kalan taraf hiçbir yazmayı kesinleştiremez, çünkü çoğunluğa ulaşamaz. Bu taraf ya read-only moda geçer ya da tamamen yanıt vermeyi durdurur.

Bu tasarımın güzelliği şudur: İki tarafın ikisinin de aynı anda çoğunluğu iddia etmesi matematiksel olarak imkânsızdır (iki ayrık grubun her biri toplamın yarısından fazlasını içeremez). Böylece **split-brain** — yani sistemin iki farklı gerçeğe bölünmesi — engellenir. Bunun bedeli, azınlık tarafındaki kullanıcıların bölünme boyunca hizmet alamamasıdır.

Pratikte bu ailenin üyeleri arasında etcd, ZooKeeper, Consul ve consensus üzerine kurulu veritabanları (ör. güçlü tutarlılık modunda çalışan pek çok yeni nesil dağıtık SQL sistemi) sayılabilir. Kubernetes'in beyni olan etcd'nin neden CP olduğunu düşünün: Cluster'ın durumu (state) hakkında iki farklı gerçek olması, iki farklı "lider" seçilmesi anlamına gelir ki bu felakettir. Orada erişilebilirlik değil, doğruluk kritiktir.

## AP Sistemleri: Erişilebilirliği Önceleyenler

AP bir sistem, bölünme sırasında bile her isteğe yanıt verir; bunun karşılığında geçici olarak eski (stale) veri sunmayı göze alır. Kök mantık şudur: Bazı iş alanlarında "biraz eski cevap", "hiç cevap yok"tan çok daha iyidir ve tutarsızlık sonradan telafi edilebilir.

Klasik örnek bir **alışveriş sepeti (shopping cart)**, bir **sosyal medya beğeni sayacı** veya bir **DNS** sistemidir. Amazon'un meşhur Dynamo makalesi tam da bu felsefeyi somutlaştırır: Müşteri her zaman sepetine ürün ekleyebilmelidir. Bölünme yüzünden sepete eklenen bir ürünün diğer replica'ya birkaç saniye geç ulaşması, satışı kaybetmekten çok daha kabul edilebilirdir.

AP sistemleri genellikle **leaderless (lidersiz)** veya **multi-master** mimariyle çalışır ve her node bağımsız yazma kabul edebilir. Bunun kaçınılmaz sonucu, aynı verinin iki tarafta farklı biçimde değiştirilebilmesidir. Bu durumda ortaya **çakışma (conflict)** çıkar ve sistemin bunu çözecek bir stratejisi olması gerekir:

- **Last-Write-Wins (LWW):** En son zaman damgasına (timestamp) sahip yazma kazanır. Basittir ama sessizce veri kaybına (lost update) yol açabilir — özellikle saat senkronizasyonu (clock skew) sorunları varsa.
- **Version Vectors / Vector Clocks:** Hangi güncellemenin diğerinden gerçekten "sonra" geldiğini nedensellik (causality) bazında belirlemeye çalışır. Kararsız kalan gerçek çakışmaları uygulamaya devreder.
- **CRDT'ler (Conflict-free Replicated Data Types):** Matematiksel olarak birleştirildiğinde (merge) her zaman aynı sonucu veren veri yapıları. Örneğin bir sayaç veya küme (set), çakışsa bile deterministik biçimde birleştirilebilir. Bu, çakışma çözümünü uygulamadan alıp veri yapısının içine gömer.

Bu ailenin tipik üyeleri Cassandra, DynamoDB, Riak ve Couchbase gibi sistemlerdir. Ancak burada önemli bir nüans var: Bu sistemlerin çoğu aslında **ayarlanabilir tutarlılık (tunable consistency)** sunar; yani her sorgu bazında CP'ye mi AP'ye mi yaklaşacağınızı siz seçebilirsiniz. Bu noktaya birazdan geleceğiz.

## Eventual Consistency (Nihai Tutarlılık)

AP sistemlerinin sunduğu tutarlılık modeline **eventual consistency (nihai/eninde sonunda tutarlılık)** denir. Tanımı şudur: **Eğer sisteme yeni güncelleme yapılmazsa, sonunda tüm replica'lar aynı değere yakınsar (converge).** "Sonunda" kelimesi kritiktir; bu süre milisaniyeler de olabilir, bölünme uzun sürerse dakikalar da.

Buradaki en yaygın kavramsal hata, eventual consistency'yi "tutarsızlık" ile eş tutmaktır. Aslında bu bir **garanti** biçimidir; sadece zayıf bir garantidir. Sistem size şunu vaat eder: Değişiklikler kaybolmayacak, yayılacak ve nihayetinde herkes aynı gerçekte buluşacak. Vaat etmediği şey, bu buluşmanın **ne zaman** gerçekleşeceği ve bu arada okuduğunuz verinin güncel olduğudur.

Nihai tutarlılığın nasıl çalıştığını anlamak için altında yatan mekanizmalara bakmak gerekir:

- **Read Repair:** Bir okuma sırasında sistem birden çok replica'ya sorar; aralarında tutarsızlık görürse, en güncel değeri saptayıp geride kalan replica'yı sessizce günceller. Yani tamir okuma trafiğine "bindirilerek" yapılır.
- **Anti-Entropy / Merkle Trees:** Replica'lar arka planda periyodik olarak birbirlerinin veri özetlerini (hash tabanlı Merkle ağaçları) karşılaştırır. Farklılık bulunan alt ağaçlar hızlıca tespit edilip senkronize edilir. Merkle ağacının değeri, iki büyük veri kümesinin farkını tüm veriyi taramadan, sadece hash'leri kıyaslayarak bulabilmesidir.
- **Hinted Handoff:** Bir node geçici olarak erişilemez olduğunda, ona gitmesi gereken yazma başka bir node'da "ipucu (hint)" olarak tutulur; node geri döndüğünde bu birikmiş yazmalar ona teslim edilir.

Eventual consistency spektrumunun içinde daha güçlü ara modeller de vardır ve bunları bilmek önemlidir:

- **Read-your-writes consistency:** Kendi yazdığınızı en azından kendiniz her zaman görürsünüz. (Bir yorum yazıp sayfayı yeniledeğinizde yorumunuzun kaybolmaması gibi.)
- **Monotonic reads:** Bir kez yeni bir değer gördüyseniz, sonraki okumalarda daha eskisine geri "kaymazsınız."
- **Causal consistency:** Nedensel olarak bağlı olaylar herkese aynı sırada görünür. Bir soruya verilen cevabın, sorudan önce görünmemesini garanti eder. Bu, eventual consistency'nin sunabileceği en güçlü pratik modellerden biridir ve bölünme toleransıyla uyumlu kalabilir.

## Quorum Ayarı: Tutarlılığı İnce Ayarlamak

Dynamo tarzı sistemlerin en güçlü yanı, tutarlılığı sabit bir tasarım kararı olmaktan çıkarıp **sorgu bazında ayarlanabilir** hale getirmesidir. Bunun matematiği zarif biçimde basittir. Üç parametre tanımlanır:

- **N:** Her verinin kaç replica'da tutulacağı (replication factor).
- **W:** Bir yazmanın başarılı sayılması için kaç replica'nın onaylaması gerektiği (write quorum).
- **R:** Bir okumanın kaç replica'ya danışacağı (read quorum).

Kritik kural şudur: **Eğer `W + R > N` ise, okuma ve yazma quorum'ları en az bir node'da mutlaka çakışır (overlap).** Bu çakışan node en güncel yazmayı içerdiği için, okuma her zaman en güncel değeri "görebilecek" en az bir kaynağa dokunmuş olur. Bu koşula **güçlü tutarlılık** denir ve nihai tutarlı bir sistemi bile linearizability'ye yaklaştırır.

Somut örnek: `N=3`, `W=2`, `R=2` seçerseniz, `W+R = 4 > 3`'tür; her okuma en az bir güncel replica'ya değer. Buna karşılık `N=3`, `W=1`, `R=1` seçerseniz (`W+R = 2 < 3`), yazma tek bir node'a düşer düşmez başarılı sayılır ve okuma başka bir node'a gidebilir — bu son derece hızlı ve erişilebilir ama nihai tutarlıdır; eski veri okuma ihtimali vardır.

İşte AP/CP ayrımının aslında ikili bir anahtar değil, bir **kadran (dial)** olduğu nokta budur. Aynı Cassandra cluster'ında bir sorguyu `QUORUM` tutarlılıkla (CP'ye yakın), başka bir sorguyu `ONE` tutarlılıkla (AP'ye yakın) çalıştırabilirsiniz. Mühendislik, doğru veri için doğru kadran ayarını seçmektir.

## CAP'in Eksikliği ve PACELC

CAP teoreminin ciddi bir kör noktası vardır: Sadece **bölünme anındaki** davranışı tarif eder. Peki ağ tıkır tıkır çalışırken, hiçbir bölünme yokken sistem nasıl davranır? CAP bu konuda tamamen sessizdir. Oysa gerçek sistemlerin ömrünün büyük çoğunluğu bölünmesiz geçer ve asıl kritik ödünleşim çoğu zaman orada yaşanır.

Bu boşluğu **PACELC** teoremi doldurur. Daniel Abadi tarafından 2012 civarında formüle edilen bu genişletme şöyle okunur:

> **if Partition (P), then Availability (A) vs Consistency (C); Else (E), Latency (L) vs Consistency (C).**

Türkçesi: **Bölünme varsa (P), A ile C arasında seçim yaparsın (klasik CAP); bölünme yoksa (E — Else), bu sefer gecikme (Latency) ile tutarlılık (Consistency) arasında seçim yaparsın.**

Bu ikinci yarı, PACELC'in asıl katkısıdır ve neden derin olduğunu anlamak için kök nedene inelim. Güçlü tutarlılık istiyorsanız, bir yazmanın birden çok replica'ya (hatta çoğunluğa) ulaşıp onaylanmasını **beklemek** zorundasınız. Bu bekleme, coğrafi olarak dağıtık bir sistemde ışık hızının dayattığı gerçek bir gecikmedir; iki kıta arasındaki bir round-trip on-larca milisaniye sürer. Yani bölünme olmasa bile, tutarlılık her zaman gecikme olarak bir bedel öder.

Buna karşılık, yazmayı tek bir yakın node'a yazıp hemen "tamam" derseniz gecikme çok düşük olur ama replica'lara yayılma asenkron (asynchronous) gerçekleştiği için geçici tutarsızlık doğar. İşte bölünmesiz durumdaki asıl gerilim budur: **düşük gecikme mi, güçlü tutarlılık mı?**

PACELC ile sistemleri dört sınıfta sınıflandırabiliriz:

- **PC/EC:** Bölünmede tutarlılık, bölünme yokken de tutarlılık seçer — her koşulda tutarlılığı gecikmeye tercih eder. Consensus tabanlı güçlü tutarlı sistemler bu sınıftadır.
- **PA/EL:** Bölünmede erişilebilirlik, bölünme yokken de düşük gecikme seçer — her koşulda tutarlılığı feda eder. Dynamo tarzı yüksek-erişilebilir sistemlerin varsayılan davranışı buna yakındır.
- **PC/EL:** Bölünmede tutarlılık ama normalde düşük gecikme. İlginç bir orta yoldur; bölünmede sıkı davranıp normalde hızlı çalışır.
- **PA/EC:** Bölünmede erişilebilirlik ama normalde tutarlılık. Daha az görülen ama olası bir kombinasyon.

PACELC'in değeri, "bu veritabanı CP mi AP mi?" gibi kaba bir sorudan, "bölünmede ne yapar, normalde ne yapar?" gibi iki boyutlu ve gerçeğe çok daha yakın bir soruya geçmemizi sağlamasıdır. Modern bir sistemi değerlendirirken sorulması gereken doğru soru budur.

## Somut Karar Senaryoları

Teoriyi mühendislik kararına dönüştürelim. Aynı üründe farklı bileşenler farklı tercihler gerektirir — ve olgun sistemler bunu bilinçli olarak yapar.

**Senaryo 1 — Ödeme ve bakiye:** Bir kullanıcının cüzdan bakiyesi mutlak doğruluk ister. Burada CP / güçlü tutarlılık şarttır. Bölünme sırasında "bakiyeyi gösteremiyorum, birazdan tekrar dene" demek, yanlış bakiye gösterip çift harcamaya (double-spend) izin vermekten kat kat iyidir.

**Senaryo 2 — Ürün beğeni sayısı:** Bir gönderinin beğeni sayacının 1.204 yerine geçici olarak 1.203 görünmesi kimseyi incitmez. Burada AP / eventual consistency doğru seçimdir; her zaman hızlı yanıt ver, sayıyı arka planda yakınsat.

**Senaryo 3 — Kullanıcı oturumu (session) ve profili:** Kullanıcının kendi profil değişikliğini anında görmesi gerekir (read-your-writes), ama başkalarının onu birkaç saniye geç görmesi sorun değildir. Burada nihai tutarlılığın güçlü bir ara modeli yeterlidir.

Bu senaryoların ortak dersi şudur: **CAP/PACELC bir sistem düzeyi etiketi değil, veri ve işlem düzeyi bir karardır.** Tek bir uygulama içinde farklı verileri farklı noktalarda konumlandırmak, olgun mimarinin işaretidir.

## Yaygın Hatalar ve Yanlış Anlamalar

**"Üçünden ikisini seç" saplantısı:** En yaygın hata. P zorunlu olduğundan gerçek seçim yalnızca C ile A arasındadır ve bu seçim yalnızca bölünme sırasında geçerlidir. "CA veritabanı" pazarlama söylemidir; dağıtık dünyada karşılığı yoktur.

**CAP'teki C ile ACID'deki C'yi karıştırmak:** CAP'in C'si linearizability'dir (kopyalar arası güncellik). ACID'in C'si ise bütünlük kısıtlarının (integrity constraints) korunmasıdır. Aynı harf, çok farklı kavramlar.

**Eventual consistency'yi "veri kaybolabilir" sanmak:** Nihai tutarlılık, güncellemelerin **yakınsayacağını** garanti eder. Veri kaybı ancak çakışma çözümü (ör. naif Last-Write-Wins) yanlış tasarlanırsa olur; bu modelin doğasında değildir.

**Bölünmeyi nadir/imkânsız varsaymak:** "Bizim ağımız güvenilir, bölünme olmaz" varsayımı, dağıtık sistemlerdeki en pahalı yanılgıdır. Bölünme sadece kablo kopması değildir; uzun GC duraklaması, aşırı yük altında zaman aşımı (timeout), yavaş bir node — hepsi pratikte bölünme gibi davranır. Sistem bölünmeyi bir **beklenen olay** olarak ele almalıdır.

**CAP'i statik bir sistem etiketi sanmak:** Tunable consistency nedeniyle aynı sistem, farklı sorgularda CP veya AP gibi davranabilir. Sistemi tek bir kutuya koymak, sunduğu esnekliği görmezden gelmektir.

**"Güçlü tutarlılık her zaman daha iyi" yanılgısı:** Güçlü tutarlılık gecikme ve erişilebilirlik maliyetiyle gelir (PACELC'in E tarafı). Beğeni sayacına linearizability koymak, gereksiz gecikme ve kırılganlık satın almaktır.

## En İyi Pratikler

**İş gereksiniminden başla, teknolojiden değil.** Her veri parçası için sor: "Bu verinin bir an eski görünmesi ne kadar zarar verir? Yanıt vermemesi ne kadar zarar verir?" Bu iki sorunun cevabı sizi C veya A tarafına doğru itecektir. Teknoloji seçimi bu cevaptan sonra gelir.

**Tutarlılığı sistem düzeyinde değil, veri/işlem düzeyinde tasarla.** Modern tunable sistemler bunu mümkün kılar. Para hareketini güçlü tutarlılıkla, aktivite akışını nihai tutarlılıkla ele al.

**PACELC merceğiyle bak.** Bir sistemi seçerken yalnızca "bölünmede ne yapar" değil, "normal çalışmada gecikme mi tutarlılık mı önceler" sorusunu da sor. Sistemlerin ömrünün çoğu bölünmesiz geçtiği için E tarafı çoğu zaman daha çok hissedilir.

**Quorum matematiğini bilinçli ayarla.** `W + R > N` kuralını bir kadran gibi kullan. Kritik okumalarda quorum'u yükselt, tolere edilebilir okumalarda düşürerek gecikmeyi ve erişilebilirliği kazan.

**Çakışma çözümünü baştan tasarla.** AP tarafına geçiyorsan, çakışmaların **kaçınılmaz** olduğunu kabul et ve stratejini önceden belirle: mümkünse CRDT'ler, aksi halde version vector'ler; naif Last-Write-Wins'e ancak veri kaybını gerçekten göze alabildiğinde başvur.

**Bölünmeyi kaos mühendisliğiyle test et.** Bölünme davranışını üretimde ilk kez keşfetmek istemezsin. Ağ bölünmelerini, yavaş node'ları ve node kayıplarını kasıtlı olarak enjekte ederek sistemin gerçekte CP mi AP mi davrandığını doğrula — çünkü belgelerin vaadi ile gerçek davranış çoğu zaman ayrışır.

**En azından read-your-writes ve monotonic reads hedefle.** Tam linearizability pahalıysa bile, bu ara garantiler kullanıcı deneyimindeki en sinir bozucu tutarsızlıkları (kendi yazdığını görememek, verinin geriye kayması) ortadan kaldırır ve çoğu uygulama için "yeterince tutarlı" hissini verir.

## Özet

CAP teoremi, dağıtık sistemlerde ağ bölünmesi kaçınılmaz olduğu için, bölünme anında tutarlılık (CP) ile erişilebilirlik (AP) arasında seçim yapmak zorunda olduğumuzu söyler; "CA" gerçek dağıtık dünyada karşılığı olmayan bir kavramdır. Eventual consistency, AP sistemlerinin verdiği "eninde sonunda tüm kopyalar yakınsar" garantisidir ve read repair, anti-entropy, hinted handoff gibi mekanizmalarla hayata geçer. PACELC ise CAP'in kör noktasını kapatarak bölünme yokken bile gecikme (L) ile tutarlılık (C) arasında sürekli bir ödünleşim olduğunu gösterir. Uzman yaklaşımı, bu ödünleşimleri sistem düzeyinde tek bir etikete indirgemek yerine, her veri ve her işlem için iş gereksinimine göre bilinçli olarak ayarlamaktır.
