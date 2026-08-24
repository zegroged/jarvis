# String Eşleştirme ve Sıkıştırma Algoritmaları

## Giriş: Neden Bu Konu Önemli?

"String algoritmaları" başlığı genellikle çok yüzeysel geçilir; oysa metin üzerinde çalışan algoritmalar hem performansın hem de güvenliğin kalbindedir. Bir web sunucusundaki her HTTP isteği, bir antivirüs motorundaki her imza taraması, bir log toplayıcının her satır eşleştirmesi ve bir dosya sisteminin her sıkıştırma işlemi bu algoritmalara dayanır.

Bu makale beş temel algoritmayı derinlemesine ele alır:

- **KMP (Knuth-Morris-Pratt)** ve **Rabin-Karp**: tek desenli arama.
- **Aho-Corasick**: çok desenli arama (IDS, antivirüs imza motorlarının temeli).
- **Levenshtein / Damerau-Levenshtein**: bulanık eşleştirme (log analizi, phishing domain tespiti).
- **Huffman ve LZ77/78**: sıkıştırma (ve zip bombası gibi DoS vektörlerinin kök nedeni).

Amacımız mekanizmayı **anlamak** ve güvenlik boyutunda **tespit/savunma** kurabilmektir; operasyonel saldırı talimatı değil, kavramsal derinlik.

---

## 1. Tek Desenli Arama: Naif Yöntemin Problemi

### Tanım

Bir `text` (uzunluk *n*) içinde bir `pattern` (uzunluk *m*) aramak istiyoruz. Naif (brute-force) yaklaşım her pozisyonda deseni baştan karşılaştırır.

### Kök Neden: Neden Naif Yöntem Yavaştır?

Naif algoritma bir uyumsuzluk (mismatch) bulduğunda metinde yalnızca **bir karakter** ilerler ve deseni **baştan** tekrar karşılaştırmaya başlar. Bu, daha önce başarıyla eşleştirdiği karakterleri "unutur". En kötü durumda `text = "aaaaaa...a"`, `pattern = "aaaa...ab"` gibi bir örnekte her pozisyonda deseni sonuna kadar karşılaştırıp son karakterde başarısız olur; karmaşıklık **O(n·m)** olur.

KMP ve Rabin-Karp bu israfı iki farklı fikirle çözer: KMP desenin iç yapısını önceden çıkarır; Rabin-Karp hash kullanır.

---

## 2. KMP (Knuth-Morris-Pratt)

### Çalışma Mantığı

KMP'nin temel içgörüsü şudur: bir uyumsuzluk olduğunda, o ana kadar eşleşen kısım (desenin bir **prefix**'i) zaten bilinir. Bu prefix'in kendi içindeki en uzun "hem prefix hem suffix" (proper prefix = proper suffix) bilgisini kullanarak deseni geriye değil ileriye kaydırabiliriz. Metin işaretçisi (*i*) **hiç geri gitmez**.

Bu bilgi **failure function** (veya *prefix function*, `pi` dizisi) olarak önceden hesaplanır. `pi[k]`, desenin ilk `k+1` karakterinin oluşturduğu alt string için en uzun proper prefix-suffix uzunluğudur.

### Örnek

`pattern = "ABABAC"` için prefix function:

```
index:   0  1  2  3  4  5
char:    A  B  A  B  A  C
pi:      0  0  1  2  3  0
```

`pi[4] = 3` çünkü `"ABABA"` için `"ABA"` hem baştan hem sondan gelir. Metinde beşinci karakterde (`C` beklenirken başka bir şey gelirse) deseni tamamen başa almak yerine `pi` değerine bakıp deseni 3 karakterlik eşleşmiş konuma kaydırırız.

### Karmaşıklık

- Prefix function hesabı: **O(m)**.
- Arama: **O(n)**.
- Toplam: **O(n + m)**, ek bellek **O(m)**.

### Doğru Kullanım ve Tuzaklar

- KMP, **tek** bir sabit desen için deterministik en kötü durum garantisi ister (gerçek zamanlı sistemler, hash saldırısına dayanıklı olmak) durumunda güçlüdür.
- **Tuzak**: Pratikte, kısa desenler ve tipik metinlerde `memchr` tabanlı veya Boyer-Moore-Horspool gibi algoritmalar KMP'den hızlı olabilir çünkü modern CPU ve önbellek davranışı sabit faktörleri değiştirir. KMP'nin asıl değeri **garantili doğrusal** olmasıdır, ortalama hız rekoru değil.
- **Yaygın hata**: prefix function'ı yanlış (0-indeksleme/1-indeksleme karışıklığı) yazmak; sınır (`k`) güncellemesinde döngüyü unutmak sonsuz döngüye veya yanlış eşleşmeye yol açar.

---

## 3. Rabin-Karp

### Çalışma Mantığı

Rabin-Karp, deseni ve metnin her `m`-uzunluğundaki penceresini bir **hash** değerine indirger. İki string eşitse hash'leri eşittir; hash'ler farklıysa string'ler kesinlikle farklıdır. Yalnızca hash'ler eşleştiğinde (potansiyel eşleşme) karakter karakter doğrulama yapılır.

Anahtar numara **rolling hash** (yuvarlanan hash): pencereyi bir karakter sağa kaydırırken hash'i sıfırdan hesaplamak yerine, çıkan karakteri düşüp giren karakteri O(1) sürede ekleriz. Tipik olarak polinom hash kullanılır:

```
hash = (c0·b^(m-1) + c1·b^(m-2) + ... + c(m-1)) mod q
```

Burada `b` taban, `q` büyük bir asal moduldür.

### Karmaşıklık

- Ortalama/beklenen: **O(n + m)**.
- En kötü durum: **O(n·m)** — tüm pencereler aynı hash'e düşerse (hash collision) her birinde tam doğrulama gerekir.

### Güvenlik Boyutu: Hash-Flooding

Rabin-Karp'ın en kötü durumu teorik değildir. Modül `q` ve taban `b` **sabit ve tahmin edilebilirse**, bir saldırgan bilerek çok sayıda collision üreten girdi hazırlayarak algoritmayı O(n·m)'ye zorlayabilir; bu bir **algorithmic complexity attack** (DoS) türüdür. Aynı sınıf saldırı hash tablolarında da görülür (HashDoS). **Savunma**: çalışma zamanında rastgele seçilen (randomized/seeded) taban ve modül kullanmak; kriptografik olmayan ama seed'li hash fonksiyonları (ör. SipHash ailesi hash tabloları için) bu saldırı yüzeyini kapatır.

### Doğru Kullanım

- Rabin-Karp özellikle **çoklu desen** aramada (aynı uzunlukta birçok deseni tek hash setinde tutmak) ve iki boyutlu örüntü (görüntü/matris) aramada zariftir.
- **Tuzak**: modulo taşması. Hash hesabında ara çarpımlar 64-bit'i taşabilir; dikkatli modüler aritmetik gerekir.

---

## 4. Aho-Corasick: Çok Desenli Arama

### Neden Ayrı Bir Algoritma?

Bir IDS/antivirüs motorunun binlerce, hatta yüz binlerce imzayı **tek geçişte** araması gerekir. Her imza için ayrı ayrı KMP çalıştırmak O(n·k) olur (k = desen sayısı). Aho-Corasick tüm desenleri **tek bir otomat**ta birleştirir ve metni **bir kez** tarayarak tüm eşleşmeleri bulur.

### Çalışma Mantığı

Aho-Corasick üç yapıdan oluşur:

1. **Trie (goto function)**: Tüm desenler ortak prefix'leri paylaşan bir ağaçta saklanır. Metnin bir karakterini okurken ağaçta ilerleriz.
2. **Failure links**: KMP'nin prefix function'ının çok desenli genellemesi. Bir düğümde eşleşme kesildiğinde, o ana kadar okunan suffix'in başka bir desenin prefix'i olup olmadığını gösteren en uzun düğüme "atlarız" — böylece hiçbir karakteri tekrar okumadan devam ederiz.
3. **Output links**: Bir düğüme geldiğimizde orada biten (ve failure link zinciri üzerinden biten) tüm desenleri raporlar. Bir konumda birden fazla desen aynı anda bitebilir (`"he"`, `"she"`, `"his"`, `"hers"` klasik örneği).

### Karmaşıklık

- Otomat inşası: **O(toplam desen uzunluğu)** (alfabe faktörüyle).
- Arama: **O(n + z)**, burada *z* toplam eşleşme sayısıdır.
- Kritik özellik: arama süresi desen **sayısından bağımsızdır**. 10 imza da 100.000 imza da metni aynı doğrusal hızda tarar (bellek dışında).

### Güvenlik: İmza Motorlarının Temeli

Aho-Corasick, geleneksel imza tabanlı IDS (örneğin Snort'un çok-desenli ön filtresi) ve birçok antivirüs tarayıcısının çekirdeğidir. İmza sayısı arttıkça tarama hızının sabit kalması, gerçek zamanlı ağ trafiği taramasını mümkün kılan şeydir.

**Savunma tasarımı açısından önemli noktalar**:

- **Bellek şişmesi**: Failure link'li tam otomat (özellikle her düğümde tüm alfabe için geçiş saklanan "goto tablosu" varyantı) büyük imza setlerinde ciddi RAM tüketir. Double-array trie gibi sıkıştırılmış temsiller bunu azaltır.
- **Evasion (kaçınma)**: İmza tabanlı tespit yalnızca **bilinen** baytları yakalar. Saldırganlar payload'u kodlayarak/parçalayarak (encoding, fragmentation, polymorphism) imzadan kaçabilir. Bu yüzden imza motorunun önünde **normalizasyon** (protokol decode, unicode normalizasyonu, defragmentation) katmanı olmazsa Aho-Corasick doğru çalışsa bile tespit başarısız olur. Ders: algoritma güçlü, ama tespit gücü girdiyi ne kadar normalize ettiğinize bağlı.

### Yaygın Hata

Failure link'leri BFS (genişlik öncelikli) sırayla hesaplamamak. Failure link'ler kök seviyesinden başlayarak katman katman kurulmalıdır; bir düğümün failure link'i, ebeveyninin failure link'i üzerinden bulunur. DFS ile veya sıralama olmadan kurmaya çalışmak yanlış otomat üretir.

---

## 5. Levenshtein ve Damerau-Levenshtein: Bulanık Eşleştirme

### Tanım

**Levenshtein distance** (edit distance), bir string'i diğerine dönüştürmek için gereken minimum tekil-karakter düzenleme sayısıdır. İzin verilen işlemler:

- **Insertion** (ekleme)
- **Deletion** (silme)
- **Substitution** (değiştirme)

**Damerau-Levenshtein** bunlara **transposition** (komşu iki karakterin yer değiştirmesi) ekler. Bu, klavye/yazım hatalarını çok daha iyi modellediği için gerçek dünya "typo" tespitinde daha isabetlidir.

### Çalışma Mantığı: Dinamik Programlama

`dp[i][j]`, `a`'nın ilk *i* karakteri ile `b`'nin ilk *j* karakteri arasındaki edit distance'tır. Yineleme (recurrence):

```
dp[i][j] = min(
    dp[i-1][j]   + 1,                 // deletion
    dp[i][j-1]   + 1,                 // insertion
    dp[i-1][j-1] + (a[i]==b[j] ? 0:1) // substitution/eşleşme
)
```

Damerau için ayrıca `a[i]==b[j-1] && a[i-1]==b[j]` durumunda `dp[i-2][j-2] + 1` (transposition) seçeneği eklenir.

### Karmaşıklık

- Zaman **O(m·n)**, bellek **O(m·n)** — ancak yalnızca mesafe değeri isteniyorsa iki satır tutularak bellek **O(min(m,n))**'e düşürülür.
- Yalnızca "mesafe ≤ k mı?" sorusu için **banded** (Ukkonen) optimizasyonu O(k·min(m,n))'e indirir; büyük sözlüklerde bu kritiktir.

### Güvenlik Uygulaması: Phishing Domain Tespiti

Levenshtein/Damerau, **typosquatting** ve **lookalike domain** tespitinin çekirdeğidir. `paypa1.com` (l→1), `gooogle.com` (fazladan o), `micros0ft.com` gibi domainler meşru markaya küçük edit distance ile yakındır. Bir savunma pipeline'ı yeni kaydedilen domainleri korunan marka listesine karşı edit distance ile ölçer ve eşik altındakileri şüpheli işaretler.

**Önemli incelikler / tuzaklar**:

- **Homoglyph saldırıları** ham Levenshtein'ı atlatır: Kiril "а" (U+0430) Latin "a"ya bayt düzeyinde eşit değildir, ama görsel olarak aynıdır; edit distance 1 verir ama saf ASCII karşılaştırması hiç yakalamaz. Bu yüzden domain tespitinde önce **Unicode/punycode normalizasyonu** ve homoglyph haritalama, sonra distance ölçümü gerekir.
- **Ölçek problemi**: Milyonlarca domaini teker teker Levenshtein ile karşılaştırmak pahalıdır. Pratikte **BK-tree** (Burkhard-Keller tree) veya **n-gram/LSH** ön filtreleme ile aday kümesi daraltılır, sonra tam distance hesaplanır.
- **Log analizi**: Levenshtein, log satırlarını şablonlara (template) kümelemek, gürültülü/mutasyonlu string'leri gruplamak için de kullanılır; ama uzun satırlarda O(m·n) maliyeti nedeniyle çoğu log pipeline'ı token bazlı veya hash bazlı yaklaşımlarla birleştirir.

### Yaygın Hata

Levenshtein distance'ı bir **benzerlik yüzdesi** gibi mutlak yorumlamak. Mesafe 2, kısa string'de büyük fark, uzun string'de küçük farktır. Doğru kullanım genellikle **normalize edilmiş** oran (`distance / max(len)`) veya uzunluğa bağlı eşiktir.

---

## 6. Sıkıştırma: Huffman ve LZ77/78

Sıkıştırma yüzeyde bir eşleştirme konusu gibi görünmese de aynı ailenin parçasıdır: tekrar eden **örüntüleri** bulup daha kısa temsille değiştirir. Ayrıca güvenlik açısından kritik bir DoS yüzeyidir.

### 6.1 Huffman Coding — Entropi Kodlaması

**Tanım**: Huffman, karakterlere **değişken uzunlukta** kod atayan bir kayıpsız (lossless) sıkıştırmadır. Sık geçen sembollere kısa kod, nadir geçenlere uzun kod verir.

**Çalışma mantığı**: Sembol frekansları sayılır. En düşük frekanslı iki düğüm tekrar tekrar birleştirilerek bir ikili ağaç (Huffman tree) inşa edilir; bu greedy strateji **prefix-free** (hiçbir kod başka bir kodun prefix'i değil) ve **optimal** (verilen sembol-başına kod için minimum ortalama uzunluk) bir kodlama üretir. Prefix-free olması, kod akışının ayraç olmadan tek biçimde çözülebilmesini sağlar.

**Karmaşıklık**: Ağaç inşası bir öncelik kuyruğu (min-heap) ile **O(σ log σ)** (σ = alfabe boyutu).

**Tuzak**: Huffman yalnızca sembol frekans dağılımından yararlanır; **dizilim/tekrar** yapısını (örneğin `"abcabcabc"`) göremez. Bu yüzden pratikte tek başına değil, LZ ailesiyle birlikte kullanılır (ör. DEFLATE = LZ77 + Huffman).

### 6.2 LZ77 — Sözlük/Pencere Tabanlı Sıkıştırma

**Tanım**: LZ77, tekrar eden alt string'leri, daha önce görülmüş bir konuma **geri referans** (back-reference) ile değiştirir. Çıktı `(distance, length, next_char)` üçlüleri akışıdır: "buradan `distance` bayt geride başlayan `length` baytlık diziyi kopyala".

**Çalışma mantığı**: Kayan bir **sliding window** (geçmiş = search buffer, gelecek = look-ahead buffer) içinde en uzun eşleşme aranır. `"aaaaaaaa"` gibi bir dizi tek bir kısa referansla kodlanabilir çünkü referans kendi kopyaladığı baytların üzerine "yuvarlanabilir".

**LZ78/LZW farkı**: LZ78 ailesi açık bir **sözlük** kurar; her yeni giren dizi sözlüğe eklenip bir indeks ile temsil edilir (GIF ve eski `compress` aracının kullandığı LZW bu ailedendir). LZ77 pencere-referans, LZ78 sözlük-indeks temellidir; ikisi de aynı "tekrarı yeniden kullan" fikrinin farklı somutlaşmalarıdır.

**Nerede**: DEFLATE (zip, gzip, PNG), zlib, ve LZ77 türevleri (LZ4, Snappy, Zstandard'ın match bulma katmanı) modern altyapının her yerindedir.

### 6.3 Güvenlik: Zip Bombası ve Decompression DoS

Sıkıştırmanın kök özelliği — **küçük girdi, büyük çıktı** — aynı zamanda bir saldırı vektörüdür.

**Kavram**: Bir **zip bombası** (decompression bomb), çok küçük bir sıkıştırılmış dosyanın açıldığında orantısız (megabaytlar → gigabaytlar/terabaytlar) veri üretmesidir. Klasik örnek yüksek oranda tekrar eden veridir (LZ77 tekrarı mükemmel sıkıştırır) ve **iç içe / rekürsif** (nested) arşivlerdir; bazı tasarımlar aynı sıkıştırılmış bloğu birçok kez paylaşarak (overlapping entries) devasa mantıksal boyut üretir. Amaç, kurbanın açma işleminde **disk, RAM veya CPU'yu tüketerek** hizmet dışı bırakmaktır (DoS).

**Neden çalışır**: Naif bir açıcı (decompressor) çıktıyı **sınırsız** yazmaya çalışır; sıkıştırma oranını önceden bilmez ve akışı sonuna kadar açar.

**Savunma / tespit — kavramsal**:

- **Çıktı sınırı (hard limit)**: Açma sırasında üretilen bayt sayısını sürekli say; makul bir tavanı aşınca işlemi iptal et. Tüm çıktıyı belleğe/diske yazmadan **akış (streaming)** olarak sınırla.
- **Sıkıştırma oranı eşiği**: `açılan_boyut / sıkıştırılmış_boyut` oranı anormal yüksekse (ör. binlerce kat) şüphelen. Meşru dosyalarda oran belli aralıklarda kalır.
- **Entry sayısı ve derinlik sınırı**: Arşiv içindeki dosya sayısını ve **iç içe** arşiv açma derinliğini sınırla (rekürsif açmayı engelle veya bir derinlik sayacı tut).
- **Kaynak izolasyonu**: Açma işlemini bellek/CPU/zaman kotalı bir sandbox veya ayrı işlemde çalıştır; kota aşımında öldür.
- **Bildirilen boyutlara güvenmeme**: Arşiv başlığındaki "uncompressed size" alanı saldırgan kontrolündedir; savunma buna değil **gerçekte açılan** bayta bakmalıdır.

**Yaygın hata**: "Dosya sadece 42 KB, güvenlidir" varsaymak. Boyut sıkıştırılmış hâlin boyutudur; tehlike açıldığındaki boyuttadır. Bir diğer hata, sınırı yalnızca en dış katmana koyup iç içe arşivleri kontrolsüz açmaktır.

---

## 7. Karşılaştırma ve Doğru Aracı Seçme

| Algoritma | Problem | Zaman | Ne zaman |
|---|---|---|---|
| KMP | Tek desen, garantili doğrusal | O(n+m) | Gerçek zamanlı, en kötü durum garantisi gerekli |
| Rabin-Karp | Tek/çoklu desen, hash | O(n+m) ort. | Çoklu eşit-uzunluk desen, 2B arama |
| Aho-Corasick | Çok sayıda desen | O(n+z) | IDS/AV imza motoru, binlerce imza |
| Levenshtein/Damerau | Bulanık/yaklaşık eşleşme | O(m·n) | Typo, phishing domain, log kümeleme |
| Huffman | Entropi sıkıştırma | O(σ log σ) | Frekans dengesizliği; LZ ile birlikte |
| LZ77/78 | Tekrar sıkıştırma | ~O(n) | Genel amaçlı kayıpsız sıkıştırma |

### Birleştirilmiş İçgörü

- **Prefix function fikri** hem KMP'de (tek desen) hem Aho-Corasick'te (çok desen, failure link) aynı köktendir: "eşleşen kısmı boşa harcama."
- **Hash fikri** hem Rabin-Karp'ta hem hash tablolarında aynı algoritmik-karmaşıklık saldırısına açıktır; savunma her ikisinde de **randomizasyon**dur.
- **Tekrar örüntüsü** hem LZ sıkıştırmasının gücü hem zip bombasının silahıdır; savunma **çıktı tarafını sınırlamak**tır.

### Kapanış: Güvenlik Dersi

Bu algoritmaların hiçbiri tek başına "güvenli" veya "güvensiz" değildir. Aho-Corasick doğru çalışsa bile normalizasyon eksikse tespit kaçırır; Levenshtein doğru olsa bile homoglyph normalizasyonu yoksa phishing atlar; LZ77 doğru açsa bile çıktı sınırı yoksa DoS olur. Savunma her zaman **algoritmanın çevresindeki girdi işleme ve kaynak sınırlaması** katmanında kurulur — algoritmanın kendisinde değil.
