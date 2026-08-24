# Arama Motoru İç Yapısı: Ters İndeks, Relevance Scoring ve Sharding

## Giriş ve Kapsam

Modern arama motorları (Elasticsearch, OpenSearch, Apache Solr) ve bunların altında yatan **Apache Lucene** kütüphanesi, milyarlarca dokümanı milisaniyeler içinde arayabilmeyi mümkün kılar. Bu hızın sırrı, verinin nasıl saklandığında ve sorgunun nasıl skorlandığında gizlidir. Bu makale, bir arama motorunun iç mekanizmasını (ters indeks, analyzer boru hattı, relevance scoring, sharding) derinlemesine açıklar ve bu sistemlerin güvenlik yüzeyini (yetkisiz sorgu erişimi, query injection) savunma perspektifiyle ele alır.

Amaç, mekanizmayı **anlamak** ve sağlam savunma/tespit kurmaktır; canlı saldırı talimatı vermek değildir.

## Bölüm 1: Ters İndeks (Inverted Index) — Temel Yapı Taşı

### Tanım

**Ters indeks (inverted index)**, terimden dokümana giden bir eşlemedir. Sıradan bir veri yapısını düşünün: "Doküman 5'te hangi kelimeler var?" sorusunun cevabı ileri indekstir (forward index). Ters indeks bunun tersini yapar: "Hangi dokümanlarda 'kedi' kelimesi geçiyor?" sorusuna doğrudan cevap verir.

### Kök Neden / Neden Bu Yapı?

Bir metin araması yaparken temel problem şudur: milyonlarca dokümanı tek tek taramak (full scan) imkânsız derecede yavaştır. Bir kitabın sonundaki **dizin (index)** nasıl çalışıyorsa, ters indeks de öyle çalışır. Kitabın her sayfasını okumak yerine, dizinden "istatistik" kelimesine bakar ve "sayfa 42, 87, 190" bilgisini anında alırsınız.

Yapının temel bileşenleri:

- **Term dictionary (terim sözlüğü):** Tüm benzersiz terimlerin sıralı listesi. Lucene bunu sıkıştırılmış ve önekli (prefix-shared) biçimde saklar.
- **Postings list (gönderi listesi):** Her terim için, o terimi içeren dokümanların ID listesi. Ayrıca terim frekansı (term frequency), pozisyon bilgisi ve offset gibi ek veriler tutulur.

### Örnek

Üç dokümanımız olsun:

```
Doküman 1: "kırmızı elma tatlı"
Doküman 2: "yeşil elma ekşi"
Doküman 3: "kırmızı gül güzel"
```

Oluşan ters indeks (basitleştirilmiş):

```
kırmızı  -> [1, 3]
elma     -> [1, 2]
tatlı    -> [1]
yeşil    -> [2]
ekşi     -> [2]
gül      -> [3]
güzel    -> [3]
```

"kırmızı elma" araması yapıldığında motor iki postings listesini alır (`kırmızı -> [1,3]`, `elma -> [1,2]`) ve bir AND sorgusu için kesişimini (`[1]`) hesaplar. Bu kesişim işlemi, listeler doküman ID'sine göre sıralı olduğu için çok verimlidir (merge/skip algoritmaları ile).

### Segment ve Immutability (Değişmezlik)

Lucene'de kritik bir tasarım kararı: indeks **segment** adı verilen değişmez (immutable) parçalardan oluşur. Bir doküman eklendiğinde yeni bir segment yazılır; segmentler asla yerinde güncellenmez.

- **Neden değişmez?** Değişmezlik, kilitsiz (lock-free) okuma, agresif önbellekleme ve OS sayfa önbelleğinden (page cache) tam yararlanma sağlar. Bir segment bir kez yazıldıktan sonra herhangi bir okuyucu onu güvenle önbellekleyebilir.
- **Silme nasıl olur?** Bir doküman "silindiğinde" gerçekte silinmez; bir `.del` işaretleyicisiyle "tombstone" olarak işaretlenir. Sorgu sonuçlarından filtrelenir ama diskte kalır.
- **Merge (birleştirme):** Zamanla küçük segmentler birikir. Arka planda çalışan bir merge işlemi, küçük segmentleri büyük segmentlerde birleştirir ve bu sırada silinmiş dokümanları fiziksel olarak temizler.

Bu değişmezliğin pratik sonucu: **güncelleme = eski dokümanı silip yenisini yazmak** demektir. Sık güncellenen alanlarda bu, segment şişmesine ve merge yüküne yol açar; bu bir performans tuzağıdır.

## Bölüm 2: Analyzer Boru Hattı — Metnin Terime Dönüşmesi

Ters indekse girmeden önce ham metin bir **analyzer (çözümleyici)** boru hattından geçer. Bu adım, arama kalitesini belirleyen en kritik ve en çok hataya açık aşamadır.

### Boru Hattının Aşamaları

1. **Character filter (karakter filtresi):** Ham karakter akışını dönüştürür. Örnek: HTML etiketlerini temizleme (`<b>elma</b>` -> `elma`), belirli karakterleri değiştirme.

2. **Tokenizer (belirteçleyici):** Metni token'lara böler. En yaygın olanı standart tokenizer'dır ve genellikle Unicode metin bölme kurallarına göre çalışır. `"kırmızı elma."` -> `["kırmızı", "elma"]`.

3. **Token filter (belirteç filtresi):** Token'ları dönüştürür. Sıralı bir zincir hâlinde uygulanır:
   - **Lowercase:** `"Elma"` -> `"elma"`
   - **Stop words (durak kelimeler):** "ve", "ile", "bir" gibi çok sık geçen ve ayırt edici olmayan kelimeleri atma.
   - **Stemming (kök bulma):** Kelimeyi köküne indirme. İngilizcede `"running"` -> `"run"`. Türkçe için bu çok daha zordur (aşağıda).
   - **Synonym (eş anlamlı):** `"bilgisayar"` ve `"komputer"` gibi eş anlamlıları eşleme.
   - **ASCII folding:** `"café"` -> `"cafe"` (aksan kaldırma).

### Kök Neden: Neden Analyzer Zorunlu?

Arama motorunun altın kuralı: **indeksleme zamanında ve sorgu zamanında aynı (veya uyumlu) analyzer kullanılmalıdır.** Eğer bir dokümanı "Elma" olarak lowercase filtresiyle indekslediyseniz, indekste "elma" saklanır. Kullanıcı "Elma" aradığında, sorgu da aynı filtreden geçmezse "Elma" terimi indekste bulunamaz — çünkü orada "elma" yazar. Sonuç: hiç eşleşme dönmez.

### Türkçe'ye Özgü Tuzaklar

Türkçe, arama motorları için notorik derecede zordur:

- **Noktasız/noktalı i problemi:** `"İSTANBUL"` kelimesinin lowercase karşılığı, doğru dil kuralıyla `"istanbul"` (noktasız değil, noktalı i ile başlar) olmalıdır. Yanlış locale ayarı `"i̇stanbul"` gibi bozuk sonuçlar üretir. Bir lowercase filtresinin dil-duyarlı (Turkish lowercase) olması gerekir.
- **Sondan eklemeli yapı:** `"evlerimizden"` kelimesi `"ev"` kökünü içerir. Basit stemming çalışmaz; morfolojik çözümleme gerektiren dil-özel bir stemmer gerekir. Yanlış stemming, alakasız sonuçlar getirir veya doğru sonuçları kaçırır.
- **Aksan/özel karakter katlama:** Kullanıcı "gunes" yazsa da "güneş" dokümanını bulabilmeli mi? Bu bir tasarım kararıdır; ASCII folding ile çözülür ama dikkatli yapılmazsa "sac" ve "saç" gibi farklı anlamlı kelimeleri karıştırır.

## Bölüm 3: Relevance Scoring — TF-IDF ve BM25

Arama sadece "eşleşen dokümanları bulmak" değildir; onları **alaka düzeyine (relevance)** göre sıralamaktır. Bunun için istatistiksel skorlama modelleri kullanılır.

### TF-IDF: Klasik Model

**TF-IDF**, iki sezginin çarpımıdır:

- **Term Frequency (TF):** Bir terim bir dokümanda ne kadar sık geçiyorsa, o doküman o terimle o kadar alakalıdır. "elma" kelimesi bir dokümanda 10 kez geçiyorsa, 1 kez geçenden muhtemelen daha alakalıdır.

- **Inverse Document Frequency (IDF):** Bir terim ne kadar az dokümanda geçiyorsa, o kadar ayırt edicidir ve değerlidir. "ve" kelimesi her dokümanda geçtiği için neredeyse hiç bilgi taşımaz (düşük IDF). "kuantum" nadir geçtiği için çok ayırt edicidir (yüksek IDF).

Sezgi: **Bir dokümanı iyi tanımlayan terim, o dokümanda sık ama tüm koleksiyonda nadir geçen terimdir.**

### BM25: Modern Standart

Lucene, Elasticsearch ve OpenSearch varsayılan olarak **BM25** (Best Matching 25) kullanır. BM25, TF-IDF'in iki temel zayıflığını düzeltir:

1. **TF doygunluğu (saturation):** Ham TF-IDF'te terim frekansı arttıkça skor doğrusal artar. BM25'te ise skor bir doyum noktasına yaklaşır. Sezgi: bir kelimenin 100 kez geçmesi, 10 kez geçmesinden anlamlı derecede daha alakalı yapmaz. Bu davranışı `k1` parametresi kontrol eder.

2. **Doküman uzunluğu normalizasyonu:** Uzun bir doküman doğal olarak her terimi daha çok içerir. Bu, uzun dokümanları haksız yere avantajlı kılar. BM25, doküman uzunluğunu ortalama doküman uzunluğuna göre normalize eder; bu davranışı `b` parametresi kontrol eder.

BM25'in kavramsal formülü şu bileşenleri birleştirir: her sorgu terimi için IDF ağırlığı çarpı, doygunluğa uğramış ve uzunlukla normalize edilmiş bir TF terimi. Tam formülü ezberlemek yerine, **hangi girdinin skoru nasıl etkilediğini** anlamak önemlidir:

- Nadir terim -> yüksek IDF -> skora büyük katkı.
- Terim dokümanda sık geçiyor -> yüksek TF -> katkı artar ama doyar.
- Doküman ortalamadan uzun -> normalizasyon skoru azaltır.

### Skorlamanın Sharding ile İnce Etkileşimi

Kritik bir ayrıntı: IDF hesabı **doküman frekansına** dayanır; yani "kaç dokümanda geçiyor". Dağıtık bir indekste dokümanlar birden çok **shard**'a dağılmıştır. Varsayılan davranışta her shard kendi lokal istatistiklerini kullanarak skor hesaplar. Küçük indekslerde veya dengesiz shard dağılımında bu, aynı sorgunun farklı çalıştırmalarda hafif farklı sıralamalar üretmesine yol açabilir. Bu, "neden test ortamımda skorlar tutarsız?" sorusunun sık görülen kök nedenidir. Global istatistik toplayan (DFS query-then-fetch benzeri) bir arama tipi bu tutarsızlığı azaltır ama ek round-trip maliyeti getirir.

## Bölüm 4: Sharding ve Dağıtık Mimari

### Tanım

Bir indeks tek bir makineye sığmayabilir veya tek makine tüm yükü kaldıramaz. **Sharding**, indeksi **shard** adı verilen bağımsız parçalara bölmektir. Her shard, aslında tam işlevsel bir Lucene indeksidir (kendi ters indeksi, segmentleri olan).

- **Primary shard:** Verinin ana kopyası. Yazma işlemleri önce buraya gider.
- **Replica shard:** Primary'nin kopyası. Hem yüksek erişilebilirlik (bir düğüm çökerse) hem de okuma kapasitesi (paralel sorgu) sağlar.

### Çalışma Mantığı

Bir doküman indekslendiğinde hangi shard'a gideceği genellikle şöyle belirlenir: `shard = hash(routing_değeri) mod primary_shard_sayısı`. Varsayılan routing değeri doküman ID'sidir.

Bunun önemli bir sonucu vardır: **primary shard sayısı indeks oluşturulurken sabitlenir ve sonradan kolayca değiştirilemez.** Çünkü shard sayısı değişirse modulo sonucu değişir ve tüm dokümanların yeniden konumlandırılması gerekir. Bu yüzden shard sayısı planlaması önceden yapılmalıdır.

### Sorgu Yaşam Döngüsü (Scatter-Gather)

Dağıtık bir arama iki fazda çalışır:

1. **Query phase (scatter):** Koordinatör düğüm, sorguyu ilgili tüm shard'lara dağıtır. Her shard kendi lokalinde en iyi N sonucu bulur ve sadece doküman ID'lerini + skorları döner.
2. **Fetch phase (gather):** Koordinatör tüm shard'lardan gelen sonuçları birleştirir, globalde en iyi N'i seçer ve sadece bu dokümanların tam içeriğini ilgili shard'lardan çeker.

Bu iki fazlı tasarım, ağ üzerinden gereksiz veri taşımayı önler.

### Yaygın Sharding Hataları

- **Over-sharding (aşırı parçalama):** Her shard kendi Lucene indeksi olduğu için hafıza ve dosya tanıtıcısı (file handle) maliyeti taşır. Binlerce küçük shard, cluster'ı yavaşlatır. Genel prensip: shard sayısını veri hacmine göre makul tutmak.
- **Dev shard'lar:** Aşırı büyük shard'lar merge ve recovery işlemlerini yavaşlatır.
- **Dengesiz routing:** Özel routing kullanılıyorsa ve bir routing değeri çok popülerse, o shard aşırı yüklenir (hot shard problemi).

## Bölüm 5: Güvenlik — Savunma ve Tespit Perspektifi

Arama motorları büyük miktarda hassas veriyi (loglar, kişisel veri, iş belgeleri) barındırdığı için değerli bir hedeftir. Aşağıdaki bölüm, riskleri **anlamak ve savunmak** içindir.

### 5.1 Yetkisiz Erişim — En Yaygın Kök Neden

Elasticsearch/OpenSearch ile ilgili en yaygın güvenlik olayı sofistike bir exploit değil, **kimlik doğrulaması olmadan internete açık bir küme**dir. Geçmişte pek çok veri ihlali, HTTP REST API'si (tipik olarak 9200 portu) herkese açık olan ve kimlik doğrulaması etkin olmayan kümelerden kaynaklanmıştır.

**Kök neden:** Eski sürümlerde güvenlik özellikleri varsayılan kapalıydı veya ayrı/ücretli bir eklentiydi. Bir yönetici kümeyi hızlıca ayağa kaldırıp `0.0.0.0`'a bind ettiğinde, kimlik doğrulaması olmadan tüm indeks dünyaya açık hâle gelirdi.

**Savunma katmanları:**

- **Kimlik doğrulama ve yetkilendirmeyi (authentication/authorization) mutlaka etkinleştirin.** Modern sürümlerde güvenlik özellikleri varsayılan olarak açıktır; bunu devre dışı bırakmayın.
- **Ağ segmentasyonu:** Arama kümesi asla doğrudan internete açık olmamalı. REST portlarını (9200) ve düğümler arası iletişim portunu (9300) güvenlik duvarıyla kısıtlayın; sadece uygulama katmanı erişebilsin.
- **TLS/şifreleme:** Hem istemci-düğüm hem düğüm-düğüm trafiğini TLS ile şifreleyin. Şifresiz düğümler arası trafik, sniffing'e ve düğüm taklit etme (rogue node) saldırılarına açıktır.
- **En az yetki (least privilege) ve RBAC:** Her uygulama/kullanıcı sadece ihtiyaç duyduğu indekslere, ideal olarak belge/alan seviyesinde (document/field level security) erişmeli. Bir uygulama sadece kendi indeksini okuyabilmeli.
- **API key ve kimlik bilgisi yönetimi:** Uzun ömürlü admin kimlik bilgileri yerine kapsamı sınırlı, süreli API anahtarları kullanın.

### 5.2 Query Injection

**Tanım:** Kullanıcı girdisinin, doğrudan ve temizlenmeden bir arama sorgusuna gömülmesiyle oluşan sınıf. Web'deki SQL injection'ın arama motoru karşılığıdır.

İki ana varyant:

**1. Query string / Lucene syntax injection:** Bazı uygulamalar kullanıcının girdiğini doğrudan bir `query_string` sorgusuna koyar. Bu sorgu tipi Lucene'in tam sorgu sözdizimini destekler (alan adları, boolean operatörler, wildcard, regexp, aralık sorguları). Kötü niyetli kullanıcı bu sözdizimini kullanarak:
   - Sorguyu, kendisine gösterilmemesi gereken alanlara yönlendirebilir (örneğin `password:*` gibi bir alanın varlığını yoklamak).
   - Ağır **wildcard/regexp** sorgularıyla (`*a*`, karmaşık regex) sistemi CPU/bellek açısından tüketip **DoS** oluşturabilir.
   - Boolean mantığını değiştirerek erişim filtrelerini atlatmaya çalışabilir.

**2. Yapısal (JSON DSL) manipülasyon:** Uygulama, kullanıcı girdisini string birleştirmeyle bir JSON sorgu gövdesine gömüyorsa, kullanıcı JSON yapısını bozarak filtre koşullarını (örneğin "sadece kendi kayıtlarını gör" filtresini) etkisiz kılabilir. Bu, yetkilendirme atlatmaya (broken access control) yol açar.

**Savunma:**

- **Kullanıcıya `query_string` gibi ham sözdizimi sunmayın.** Bunun yerine `match`, `term` gibi yapılandırılmış, girdiyi veri olarak ele alan sorgu tiplerini kullanın. Ham arama söz dizimi gerekiyorsa `simple_query_string` gibi hataya dayanıklı ve daha kısıtlı bir tip tercih edin.
- **Sorguyu string birleştirmeyle kurmayın.** Sorgu gövdesini programatik olarak (nesne/parametre olarak) oluşturun; kullanıcı girdisi her zaman bir değer alanına yerleştirilsin, yapının parçası olmasın. Bu, SQL'deki parametreli sorgunun (parameterized query) karşılığıdır.
- **Yetkilendirme filtresini backend'de zorlayın.** "Kullanıcı sadece kendi verisini görsün" kuralı, kullanıcı girdisiyle aynı düzeyde birleştirilmemeli; sunucu tarafında, kullanıcının değiştiremeyeceği bir `filter` bağlamında uygulanmalı. İdeal olan, veri seviyesinde document-level security kullanmaktır.
- **Maliyetli operasyonları kısıtlayın:** Öndeki wildcard (`*abc`), açık uçlu regexp, derin sayfalama ve script sorgularını sınırlayın veya kapatın. Bunlar hem DoS vektörü hem de bilgi sızdırma riskidir.
- **Girdi doğrulama ve limitler:** Sorgu uzunluğu, wildcard sayısı, boolean cümle sayısı (`indices.query.bool.max_clause_count` benzeri limitler) gibi sınırlar koyun.

### 5.3 Script Injection ve Diğer Yüzeyler

Arama motorları, skorlama ve alan hesaplaması için betik dilleri (örneğin Painless) çalıştırabilir. Kullanıcı girdisi bir betiğe gömülürse, kod çalıştırma riski doğar. Tarihsel olarak, daha eski ve daha az kısıtlı betik motorlarında ciddi uzaktan kod çalıştırma (RCE) zafiyetleri görülmüştür; bu yüzden modern motorlar betikleri kum havuzuna (sandbox) alır.

**Savunma:** Kullanıcı girdisini asla betik gövdesine gömmeyin; betiklere parametre olarak geçirin. Dinamik/satır içi (inline) betikleri mümkünse kapatın veya sadece güvenilir, önceden saklanmış (stored) betiklere izin verin.

### 5.4 Tespit (Detection)

Savunmanın yanında görünürlük kritiktir:

- **Denetim loglama (audit logging):** Kimlik doğrulama başarısızlıkları, yetki reddi olayları ve hassas indekslere erişim denemelerini loglayın ve merkezî bir yere (SIEM) gönderin.
- **Anomali tespiti:** Alışılmadık derecede ağır sorgular (çok sayıda wildcard, dev regexp), tek bir istemciden gelen yüksek hacimli tarama benzeri istekler ve normalde erişilmeyen indekslere erişim, tespit sinyalleridir.
- **Alan/indeks keşfi (enumeration) tespiti:** `_cat`, `_mapping`, `_all` gibi meta-veri uç noktalarına yetkisiz erişim denemeleri, keşif aşamasının göstergesidir.
- **Konfigürasyon izleme:** Kimlik doğrulamanın kapatılması, portların dışa açılması gibi tehlikeli konfigürasyon değişikliklerini izleyin ve alarm kurun.

## Bölüm 6: Sık Yapılan Hataların Özeti

- **Analyzer uyumsuzluğu:** İndeksleme ve sorgu zamanında farklı analyzer kullanmak, "eşleşmesi gereken hiçbir şey eşleşmiyor" sorununun bir numaralı nedenidir.
- **Türkçe locale ihmali:** Dil-duyarlı olmayan lowercase/stemming ile bozuk arama sonuçları.
- **`query_string`'i kullanıcıya açmak:** En büyük injection ve DoS yüzeyi.
- **Güvenliği devre dışı bırakmak:** "Sonra açarız" diyerek kimlik doğrulamasız küme kurmak.
- **Shard sayısını sonradan değiştirmeye çalışmak:** Baştan planlanması gereken bir karar.
- **Skor tutarsızlığını hata sanmak:** Küçük indekslerde shard-lokal IDF istatistikleri doğal sonuçtur.
- **Değişmezliği görmezden gelmek:** Çok sık güncelleme yapılan modelde segment/merge yükünü hesaba katmamak.

## Sonuç

Bir arama motoru, özünde üç fikrin zarif birleşimidir: veriyi terimden dokümana ters çeviren **ters indeks**, alakayı istatistikle sıralayan **BM25 gibi skorlama modelleri** ve ölçeği mümkün kılan **sharding**. Bu üç mekanizmayı anlamak, hem yüksek performanslı arama tasarlamanın hem de sistemi güvenli kılmanın önkoşuludur. Güvenlik tarafında ise ders nettir: felaketlerin çoğu egzotik zafiyetlerden değil, temel hijyen eksikliğinden (açık kümeler, ham sorgu sözdizimini kullanıcıya sunmak, yetkilendirmeyi girdiyle karıştırmak) doğar. Güçlü savunma; ağ izolasyonu, kimlik doğrulama, en az yetki, yapılandırılmış sorgu inşası ve sürekli denetim loglamasının katmanlı birleşimidir.
