# NoSQL Türleri: Document, Key-Value, Column-Family ve Graph

## Giriş ve Tanım

NoSQL terimi, ismine rağmen "SQL'e karşı" bir hareket değil, "Not Only SQL" (yalnızca SQL değil) anlamına gelen bir şemsiye kavramdır. Bu şemsiyenin altında, klasik ilişkisel veritabanlarının (RDBMS) katı tablo-satır-sütun modelinden ve tam ACID garantilerinden bilinçli olarak taviz veren, farklı veri modellerine sahip veritabanı aileleri yatar. Ortak noktaları, ilişkisel modelin dayattığı önceden tanımlı şema (schema-on-write) zorunluluğunu gevşetmeleri ve çoğunlukla yatay ölçeklenme (horizontal scaling / sharding) için tasarlanmış olmalarıdır.

NoSQL veritabanlarını genellikle dört ana aileye ayırırız: **document** (belge), **key-value** (anahtar-değer), **column-family** (geniş sütunlu / wide-column) ve **graph** (çizge/graf). Bu dört model rastgele seçilmiş kategoriler değildir; her biri belirli bir erişim örüntüsünü (access pattern) olabildiğince ucuza ve hızlı hale getirmek için doğmuştur. Bu makalenin ana tezi şudur: NoSQL türü seçimi bir moda tercihi değil, **verinizin şekli ile sorgularınızın şeklinin çakıştığı noktada verilen bir mühendislik kararıdır.**

Bu makalede önce her modelin ne olduğunu ve neden öyle çalıştığını (kök nedenini), sonra somut örneklerini, doğru kullanımını, tuzaklarını ve yaygın hataları inceleyeceğiz. Ardından hepsinin altındaki ortak tutarlılık felsefesi olan BASE'i ve son olarak "ne zaman hangisini kullanmalı" sorusunu ele alacağız.

## Neden NoSQL Ortaya Çıktı? Kök Neden

NoSQL'in ortaya çıkışını anlamak, türleri anlamanın ön koşuludur. İlişkisel veritabanları 1970'lerin normalize edilmiş, tutarlılığı her şeyin üstünde tutan dünyası için tasarlandı. Bu dünyada tek bir güçlü sunucu (vertical scaling) veriyi tutardı ve JOIN'ler ucuzdu çünkü her şey aynı makinedeydi.

2000'lerde web ölçeği (web-scale) bu varsayımları kırdı. Üç temel baskı ortaya çıktı:

1. **Hacim ve yatay ölçekleme baskısı:** Veri tek bir makineye sığmayınca, veriyi birden çok makineye bölmek (sharding) gerekti. Ancak ilişkisel modelin en güçlü aracı olan JOIN, veriyi farklı makinelere dağıttığınızda felakete dönüşür; çünkü artık ağ üzerinden makineler arası veri toplamanız gerekir. NoSQL modelleri, JOIN ihtiyacını en aza indirecek şekilde veriyi organize ederek bu sorunu kaynağında çözer.

2. **Şema esnekliği baskısı:** Hızlı gelişen ürünlerde veri yapısı sürekli değişir. Her alan eklemede `ALTER TABLE` çalıştırmak ve milyonlarca satırı kilitlemek pahalıdır. Şemasız (veya şema-esnek) modeller bu sürtünmeyi kaldırır.

3. **CAP teoremi gerçeği:** Eric Brewer'ın CAP teoremi, dağıtık bir sistemde Consistency (tutarlılık), Availability (erişilebilirlik) ve Partition tolerance (bölünme toleransı) üçlüsünden ağ bölünmesi (network partition) anında ancak ikisinin garanti edilebileceğini söyler. Ağ bölünmeleri dağıtık sistemlerde kaçınılmaz olduğundan, P pratikte zorunludur; bu da gerçek seçimin C ile A arasında olduğu anlamına gelir. Birçok NoSQL sistemi, "her zaman yanıt versin ama biraz eski veri dönebilsin" diyerek A'yı seçti. İşte BASE felsefesi buradan doğar.

Bu üç baskı, farklı erişim örüntüleri için farklı optimizasyonlar gerektirdi ve dört aile bu ihtiyaçlardan filizlendi.

## Key-Value (Anahtar-Değer) Depolar

### Tanım

En basit NoSQL modelidir. Veri, bir anahtarın (key) bir değere (value) eşlendiği devasa bir hash tablosu gibi düşünülebilir. Değer, veritabanı açısından çoğunlukla opak (opaque) bir blob'dur; yani sistem değerin içine bakmaz, onun sadece bir baytlar dizisi olduğunu varsayar. Örnekleri: Redis, Amazon DynamoDB (temel modelinde), Riak, Memcached, etcd.

### Kök Neden / Çalışma Mantığı

Neden bu kadar hızlıdır? Çünkü anahtar-değer deposu, çözebileceği sorgu evrenini kasıtlı olarak daraltmıştır. Yapabileceğiniz temel işlemler `GET(key)`, `PUT(key, value)` ve `DELETE(key)`'tir. "Değeri X olan tüm kayıtları bul" diyemezsiniz. Bu sınırlama bir zafiyet değil, tasarımın özüdür: Anahtar üzerinden bir hash fonksiyonu, verinin hangi shard'da ve bellekte nerede olduğunu O(1) karmaşıklıkla belirler. JOIN yoktur, karmaşık sorgu planlayıcı (query planner) yoktur, ikincil indeks yükü yoktur. Bu yüzden anahtar-değer depoları, doğru kullanıldığında mikrosaniye seviyesinde gecikmeye (latency) ulaşabilir.

Redis gibi bellek-içi (in-memory) örnekler bu hızı bir adım öteye taşır: Veri diskte değil RAM'de tutulur, kalıcılık ise arka planda snapshot veya append-only log ile sağlanır.

### Somut Örnekler

- **Oturum yönetimi (session store):** Web uygulamasında `session:abc123` anahtarına karşılık kullanıcının oturum verisini saklamak. Milyonlarca eşzamanlı oturumu ölçeklenebilir şekilde tutmanın klasik yoludur.
- **Önbellek (cache):** Pahalı bir SQL sorgusunun sonucunu `query_hash → result` olarak saklayıp tekrar hesaplamamak.
- **Rate limiting ve sayaçlar:** Redis'in atomik `INCR` komutuyla "bu IP son dakikada kaç istek attı" bilgisini tutmak.
- **Feature flag ve konfigürasyon dağıtımı.**

### Doğru Kullanım ve Tuzaklar

Anahtar-değer deposu, erişim örüntünüz **her zaman anahtar üzerinden** olduğunda mükemmeldir. Kritik tuzak: Değerin içeriğine göre sorgulama ihtiyacı doğduğunda model çöker. Örneğin "e-posta adresi ile kullanıcı bul" gerekiyorsa ve anahtarınız kullanıcı ID'si ise, ya ikinci bir eşleme (`email → user_id`) kurmanız ya da yanlış aracı seçmiş olmanız gerekir.

Redis özelinde ek bir güç vardır: Redis aslında saf anahtar-değer değil, "veri yapıları sunucusudur" (list, set, sorted set, hash, stream). Bu, kuyruk, liderlik tablosu (leaderboard), pub/sub gibi örüntüleri tek araçta çözmenizi sağlar. Ancak bu güç, Redis'i birincil kalıcı veritabanı sanma hatasına da yol açabilir; bellek pahalıdır ve tüm veri setinizin RAM'e sığması gerekir.

## Document (Belge) Veritabanları

### Tanım

Değeri opak bırakan anahtar-değer modelinin, "değerin içine bakabilen ve içine göre sorgulayabilen" versiyonudur. Veri, kendi kendini tanımlayan (self-describing) belgeler halinde saklanır; bu belgeler tipik olarak JSON, BSON veya XML formatındadır. Her belge, iç içe geçmiş (nested) yapılar, diziler ve alanlar içerebilir. Örnekleri: MongoDB, Couchbase, Amazon DocumentDB, CouchDB.

### Kök Neden / Çalışma Mantığı

Document modelinin temel felsefesi **"birlikte okunan, birlikte saklansın"** (data locality) ilkesidir. İlişkisel dünyada bir blog yazısını, yazarını, etiketlerini ve yorumlarını dört ayrı tabloya normalize eder, okurken JOIN ile birleştirirsiniz. Document dünyasında ise tüm bu ilgili veriyi tek bir belgeye gömebilirsiniz (embedding). Böylece tek bir okuma işlemi, uygulamanın ihtiyaç duyduğu her şeyi getirir. JOIN'e gerek kalmaz; işte bu, yatay ölçeklemeyi mümkün kılan kilit tasarım kararıdır çünkü tek belge tek shard'da durur ve makineler arası koordinasyon gerekmez.

Ayrıca şema esnekliği (schema-on-read) burada devrededir. Aynı koleksiyondaki iki belge farklı alanlara sahip olabilir. Veritabanı yazma anında şemayı dayatmaz; anlamı, okuyan uygulama koduna bırakır. Bu, hızlı iterasyon için özgürleştiricidir ama sonraki bölümde göreceğimiz gibi bir sorumluluk devridir.

Document veritabanları, anahtar-değerin aksine değer içindeki alanlar üzerinde ikincil indeks (secondary index) kurabilir, böylece "yaşı 30'dan büyük kullanıcıları bul" gibi zengin sorgular yapılabilir.

### Somut Örnek

Bir e-ticaret ürününü ele alalım. İlişkisel modelde `products`, `product_variants`, `product_images`, `product_attributes` tabloları olurdu. Document modelinde:

```json
{
  "_id": "urun_842",
  "ad": "Kablosuz Kulaklik",
  "fiyat": 1299.90,
  "kategori": ["elektronik", "ses"],
  "varyantlar": [
    { "renk": "siyah", "stok": 45 },
    { "renk": "beyaz", "stok": 12 }
  ],
  "ozellikler": { "bluetooth": "5.3", "pil_saat": 30 }
}
```

Tek okumada ürünün her şeyi elimizde. Ürün sayfasını render etmek için tek sorgu yeter.

### Doğru Kullanım ve Tuzaklar

En sinsi tuzak **modelleme kararı: gömmek (embed) mi, referans vermek (reference) mi?** Kural şudur: Birlikte ve sık okunuyorsa, alt-veri sınırlıysa ve bağımsız olarak sorgulanmıyorsa göm. Ancak veri sınırsız büyüyorsa (örneğin bir gönderiye milyonlarca yorum), gömmek felakettir çünkü belgeler şişer, belge boyutu limitine dayanır (MongoDB'de belge başına 16 MB sınırı vardır) ve her küçük güncelleme koca belgeyi yeniden yazar.

İkinci büyük tuzak: Document veritabanlarını ilişkisel veritabanı gibi kullanmaya çalışmak. Eğer sürekli belgeler arası "manuel JOIN" yapıyor, uygulama kodunda ilişkileri elle birleştiriyorsanız, muhtemelen yanlış aracı seçtiniz. Aşırı normalize edilmiş bir document modeli, her iki dünyanın en kötüsünü verir.

Üçüncüsü, şemasızlığı "şema tasarımı yok" sanmak. Şema kaybolmaz; sadece veritabanından uygulama koduna taşınır. Disiplin olmazsa üç yıl sonra aynı koleksiyonda alan adının beş farklı yazımıyla (`fiyat`, `price`, `Fiyat`...) karşılaşırsınız.

## Column-Family (Geniş Sütunlu / Wide-Column) Veritabanları

### Tanım

Bu model isminden dolayı en çok yanlış anlaşılandır. "Column-family" sistemleri, adının çağrıştırdığı sütun-yönelimli (columnar) analitik depolardan farklıdır. Veri, satır anahtarı (row key) altında, dinamik sayıda sütunun gruplandığı sütun ailelerinde (column families) saklanır. Her satır, farklı sayıda ve isimde sütuna sahip olabilir; yani bu, "satır başına milyonlarca sütun tutabilen, seyrek (sparse) çok boyutlu bir eşleme" olarak düşünülmelidir. Örnekleri: Apache Cassandra, Apache HBase, Google Bigtable, ScyllaDB.

### Kök Neden / Çalışma Mantığı

Bu model, Google'ın Bigtable ve Amazon'un Dynamo makalelerinin mirasıdır ve tek bir amaca hizmet eder: **devasa yazma hacmini (write throughput) ve lineer yatay ölçeklemeyi** desteklemek. Cassandra gibi sistemler, master'sız (masterless / peer-to-peer) mimarileri sayesinde tek bir darboğaz noktası olmadan yüzlerce düğüme yayılabilir.

Buradaki en kritik ve genelde anlaşılmayan nokta: **Cassandra'da veri modeli sorgulara göre tasarlanır, ilişkilere göre değil.** İlişkisel dünyada önce veriyi normalize eder, sonra istediğiniz her sorguyu atarsınız. Cassandra'da tam tersi geçerlidir: Önce hangi sorguları atacağınızı bilmeniz, sonra tabloyu (aslında sorgu başına ayrı bir tabloyu) o sorguya göre kurmanız gerekir. Bunun kök nedeni, verinin partition key ile fiziksel olarak dağıtılması ve clustering key ile disk üzerinde sıralı yazılmasıdır. Sorgunuz partition key'e uymuyorsa, veri fiziksel olarak orada bulunmadığından ya çok pahalı olur ya da tümüyle imkânsızdır. Aynı veriyi farklı sorgular için birden çok kez, farklı şekillerde yazmak (denormalization) burada norm ve doğru pratiktir; disk ucuz, ağ üzerinden dağınık okuma pahalıdır.

Yazma hızının sırrı LSM-tree (Log-Structured Merge tree) yapısıdır: Yazmalar önce belleğe ve bir commit log'a eklenir (sıralı, çok hızlı), sonra arka planda diske düzenlenir. Bu, rastgele disk yazmasından kaçınarak yüksek write throughput sağlar.

### Somut Örnek

Zaman-serisi (time-series) verisi bu modelin ana yurdudur: Milyonlarca sensörden saniyede gelen ölçümler. Partition key olarak `sensor_id`, clustering key olarak `zaman` seçilir. Böylece "42 numaralı sensörün son 1 saatteki tüm ölçümleri" sorgusu, tek partition içinde diskte zaten sıralı duran veriyi tek seferde okur; son derece verimlidir. IoT telemetrisi, mesaj geçmişleri, olay günlükleri (event logging) tipik kullanımlardır.

### Doğru Kullanım ve Tuzaklar

En yıkıcı hata **sıcak partition (hot partition)** yaratmaktır. Partition key kötü seçilirse (örneğin tüm veriyi tek bir güne veya tek bir kullanıcıya yığan bir key), tüm yük tek bir düğüme biner ve lineer ölçekleme vaadi çöker. Verinin partitionlara dengeli dağılması (yüksek kardinalite) hayatidir.

İkinci tuzak: Cassandra'yı esnek bir ilişkisel veritabanı sanmak ve `ALLOW FILTERING` ile partition key'siz sorgular atmaya çalışmak. Bu, tüm kümede tarama (full scan) tetikler ve üretimde felakettir. Ayrıca büyük tombstone (silinen veri işaretleri) birikimi, silme-yoğun iş yüklerinde okuma performansını sessizce öldürür.

## Graph (Çizge) Veritabanları

### Tanım

Bu ailenin diğer üçünden felsefi olarak ayrıldığı nokta şudur: Diğerleri ilişkileri (relationships) en aza indirerek ölçeklenmeye çalışırken, graph veritabanları **ilişkinin kendisini birinci sınıf vatandaş** yapar. Veri, düğümler (nodes/vertices), bu düğümleri bağlayan kenarlar (edges) ve her ikisinin de taşıyabildiği özellikler (properties) olarak modellenir. En yaygın model "property graph"tir. Örnekleri: Neo4j, Amazon Neptune, ArangoDB, JanusGraph.

### Kök Neden / Çalışma Mantığı

Graph veritabanının varlık nedeni, ilişkisel dünyada "çok seviyeli JOIN'lerin" katlanarak pahalılaşması sorunudur. "Ali'nin arkadaşlarının arkadaşlarının beğendiği ürünler" gibi bir sorgu, ilişkisel modelde her derinlik seviyesinde bir JOIN daha, yani sorgu maliyetinde patlama demektir.

Graph veritabanlarının sırrı **"index-free adjacency"** (indekssiz komşuluk) ilkesidir. Her düğüm, komşularına doğrudan fiziksel işaretçiler (pointer) tutar. Yani bir düğümden komşusuna geçmek için bir indeks araması yapmanıza gerek yoktur; işaretçiyi takip edersiniz. Sonuç olarak, bir ilişkiyi (edge) geçme maliyeti, grafın toplam büyüklüğünden bağımsız olarak sabittir. İlişkisel JOIN, veri büyüdükçe yavaşlar; graph traversal ise yalnızca dokunduğunuz alt-grafın büyüklüğüne bağlıdır. Derin ilişki sorgularında aradaki fark, saniyelerle milisaniyeler arasındaki farktır.

Sorgular tipik olarak bildirimsel bir graph dili ile yazılır (Neo4j'de Cypher, standartlaşan yeni dil GQL). Örneğin bir yol bulma (path finding) ya da örüntü eşleştirme (pattern matching), bu dillerde doğal biçimde ifade edilir.

### Somut Örnekler

- **Sosyal ağlar:** Arkadaşlık, takip, "kaç adım uzaktasınız" (degrees of separation) sorguları.
- **Öneri motorları (recommendation):** "Bunu alan şunu da aldı" tarzı ilişki-yoğun çıkarımlar.
- **Dolandırıcılık tespiti (fraud detection):** Görünüşte bağımsız hesaplar arasındaki gizli halka örüntülerini yakalamak; graph'ın en güçlü olduğu alanlardan biridir.
- **Bilgi çizgeleri (knowledge graphs), ağ ve altyapı topolojisi, erişim yetki modelleri.**

### Doğru Kullanım ve Tuzaklar

Graph veritabanı, sorgularınızın özü **ilişkiler üzerinde gezinmekse** parlar. Tuzak: Onu genel amaçlı bir veritabanı sanmak. Basit "tüm ürünleri listele, fiyata göre sırala" gibi ilişki içermeyen toplu sorgular graph veritabanının güçlü yanı değildir; document veya ilişkisel model bunu daha iyi yapar.

İkinci tuzak yatay ölçeklemedir. Bir grafı birden çok makineye bölmek (graph partitioning) doğası gereği zordur; çünkü bir kenarın iki ucu farklı makinelere düşerse, ölçeklemeyi mümkün kılan "index-free adjacency" avantajı ağ atlaması yüzünden kaybolur. Bu yüzden graph veritabanları genelde en zor yatay ölçeklenen ailedir ve çoğu senaryoda dikey ölçekleme ya da dikkatli partition stratejileri tercih edilir.

## BASE: NoSQL'in Tutarlılık Felsefesi

Dört modeli anlattıktan sonra, çoğunun (özellikle dağıtık olanların) altında yatan ortak tutarlılık felsefesine gelelim. İlişkisel dünyanın garantisi **ACID**'dir: Atomicity, Consistency, Isolation, Durability. ACID, "işlem ya tamamen olur ya hiç olmaz, ve bittiğinde herkes aynı, doğru veriyi görür" der. Bu güçlü garanti, tek makinede kolaydır ama dağıtık sistemde pahalıya mal olur çünkü makineler arası koordinasyon (örneğin two-phase commit) gecikme ve erişilebilirlik kaybı yaratır.

BASE, ACID'e bilinçli bir alternatif olarak, biraz da esprili bir karşıtlık kurmak için (kimya metaforu: asit/baz) türetilmiştir. Açılımı:

- **Basically Available (Temelde Erişilebilir):** Sistem her zaman bir yanıt vermeye çalışır. Bir düğüm çökse veya ağ bölünse bile, sistem tümüyle durmaz; belki eksik veya biraz eski veriyle ama yanıt döner. Bu, CAP teoremindeki A (availability) tercihinin somutlaşmasıdır.

- **Soft state (Yumuşak Durum):** Sistemin durumu, dış bir girdi olmasa bile zamanla değişebilir. Bunun nedeni, verinin arka planda düğümler arasında yayılıyor (replication) olmasıdır. Yani "şu an" sistemin durumu her düğümde birebir aynı olmayabilir; kopyalar birbirine yetişmeye çalışırken durum "yumuşaktır".

- **Eventually consistent (Sonunda Tutarlı):** Yeni yazma işlemleri dursa, sistem sonunda tüm kopyaların aynı değere yakınsadığı tutarlı bir duruma ulaşır. "Sonunda" kelimesi kilittir: Tutarlılık garanti edilir ama **anında değil**. Bir kullanıcı verisini güncelledikten hemen sonra başka bir düğümden okuyan ikinci kullanıcı, kısa bir süre eski değeri görebilir.

### Neden BASE? Kök Neden

BASE bir "gevşeklik" ya da "kalitesizlik" değildir; CAP teoreminin dayattığı takasa verilen rasyonel bir yanıttır. Ağ bölünmesi kaçınılmazsa ve siz sisteminizin her koşulda yanıt vermesini (erişilebilirlik) istiyorsanız, geçici tutarsızlığı kabul etmek zorundasınız. Bir sosyal medya beğeni sayısının 3 saniye boyunca 1.000 yerine 999 görünmesi kabul edilebilir bir bedeldir; buna karşılık sistemin asla düşmemesi çok değerlidir.

Ancak burada kritik bir olgunluk noktası vardır: **BASE her yere uygun değildir.** Bir bankada bakiyeyi eventual consistency ile yönetmek felakettir; birinin parayı iki kez çekmesine yol açabilir. Nitekim modern NoSQL sistemleri bu ayrımı fark etmiş, ayarlanabilir tutarlılık (tunable consistency) sunmaya başlamıştır. Cassandra'da her sorgu için "kaç düğüm onaylarsa yazma/okuma başarılı sayılsın" (consistency level: ONE, QUORUM, ALL) seçilebilir; QUORUM seviyesinde okuma ve yazma quorumları örtüştüğünde güçlü tutarlılığa yakın davranış elde edilir. DynamoDB de "eventually consistent read" ile "strongly consistent read" arasında seçim sunar. Yani BASE, açılıp kapanabilen bir kadran haline gelmiştir; "hep BASE" ya da "hep ACID" değil, iş yükünün her parçası için ayrı bir denge.

Ek olarak, "NoSQL = ACID yok" eşitlemesi artık yanlıştır. MongoDB çok-belgeli ACID transaction'ları destekler, birçok NoSQL sistemi belge/satır düzeyinde atomik işlemler sunar. BASE bir zorunluluk değil, bir tasarım seçeneğidir.

## Ne Zaman Hangisini Kullanmalı?

Şimdi tüm parçaları bir karar çerçevesinde birleştirelim. Doğru soru "hangi NoSQL daha iyi" değil, **"benim erişim örüntüm hangi modelin doğal gücüyle örtüşüyor"** sorusudur.

**Key-Value seçin, eğer:** Erişiminiz neredeyse her zaman tek bir bilinen anahtar üzerindense; çok düşük gecikme ve çok yüksek okuma/yazma hacmi gerekiyorsa; veri yapısı basitse. Önbellek, oturum deposu, rate limiting, feature flag için birinci tercih. Değerin içeriğine göre sorgu ihtiyacınız varsa bu modeli seçmeyin.

**Document seçin, eğer:** Veriniz doğal olarak iç içe, kendine yeten belgeler halindeyse; şema hızla evrilyorsa; bir ekranı/nesneyi tek okumada getirmek istiyorsanız. İçerik yönetimi, ürün katalogları, kullanıcı profilleri, mobil/web uygulama backend'leri için idealdir. Verileriniz yoğun biçimde çok-yönlü ilişkiliyse ve sürekli JOIN'e benzer birleştirme yapıyorsanız, ilişkisel veya graph'i düşünün.

**Column-Family seçin, eğer:** Yazma hacminiz devasa ve büyümeye devam edecekse; lineer yatay ölçekleme ve yüksek erişilebilirlik kritikse; sorgu örüntüleriniz önceden bilinip partition key etrafında tasarlanabiliyorsa. Zaman-serisi, IoT telemetrisi, olay günlükleri, mesajlaşma geçmişleri için güçlüdür. Ad-hoc, önceden kestirilemeyen, esnek sorgular istiyorsanız bu model sizi cezalandırır.

**Graph seçin, eğer:** Sorularınızın kalbi varlıklar arası çok seviyeli ilişkilerde geziniyorsa; "kaç adım uzakta", "gizli bağlantılar", "en kısa yol", "örüntü eşleştirme" gibi ihtiyaçlar merkezdeyse. Sosyal ağlar, öneri sistemleri, dolandırıcılık tespiti, bilgi çizgeleri için eşsizdir. İlişkiler basit ve sığsa, güçlü graph özelliklerine para/karmaşıklık harcamanıza gerek yoktur.

### Genel Uyarı: Polyglot Persistence ve İlişkiseli Küçümsememek

Modern mimarilerde tek bir doğru cevap dayatmak yerine **polyglot persistence** (çok-dilli kalıcılık) yaklaşımı yaygınlaşmıştır: Aynı sistemde her iş parçası için en uygun deponun kullanılması. Bir e-ticaret sistemi ürün kataloğu için document, sepet ve oturum için key-value, öneri için graph, sipariş kayıtları için ise pekâlâ ilişkisel bir veritabanı kullanabilir.

Buradaki en önemli uzman tavsiyesi şudur: **NoSQL'e varsayılan olarak koşmayın.** Modern PostgreSQL gibi ilişkisel veritabanları JSONB ile document benzeri esneklik, dizilerle ve uzantılarla graph ve zaman-serisi yetenekleri sunar; üstelik tam ACID ve olgun ekosistemle. Çoğu uygulama için, "web ölçeği" ihtiyacı gerçekleşmeden NoSQL'e geçmek, kazanmayacağınız bir ölçeklenme için ödemeyeceğiniz sorgu esnekliğinden ve güçlü tutarlılıktan vazgeçmek olur. NoSQL, somut bir ölçek, erişim örüntüsü veya veri şekli baskısına verilen bilinçli bir yanıt olduğunda değerlidir; bir moda olarak değil.

## Özet

NoSQL, ilişkisel modelin dağıtık ölçekteki sınırlarına verilen dört farklı yanıttır. Key-value opak değerlerle en yalın ve en hızlı anahtar erişimini; document belgelere gömülü veriyle veri yerelliğini ve şema esnekliğini; column-family sorguya göre denormalize edilmiş yapılarla devasa yazma hacmini ve lineer ölçeklemeyi; graph ise index-free adjacency ile ilişki-yoğun sorguları çözer. Bu modellerin çoğu, CAP teoreminin dayattığı takas gereği BASE (temelde erişilebilir, yumuşak durum, sonunda tutarlı) felsefesini benimser; ancak modern sistemlerde tutarlılık artık açılıp kapanabilen ayarlanabilir bir kadrandır. Doğru seçim daima verinin şekli ile sorgunun şeklinin çakıştığı noktada verilir; ve çoğu zaman en olgun cevap, tek bir modele saplanmak yerine her işe uygun aracı seçen polyglot persistence yaklaşımıdır.
