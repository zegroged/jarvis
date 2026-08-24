# Karmaşıklık Analizi (Big-O)

## Tanım: Karmaşıklık analizi neyi ölçer?

Karmaşıklık analizi, bir algoritmanın kaynak tüketiminin (çoğunlukla **çalışma süresi** ve **bellek**) girdi boyutu büyüdükçe *nasıl ölçeklendiğini* tanımlayan matematiksel bir çerçevedir. Buradaki en kritik kelime "ölçeklenme"dir. Big-O bize bir algoritmanın "kaç saniye süreceğini" veya "kaç megabyte kullanacağını" söylemez; girdi büyüdükçe bu maliyetin **hangi eğriyle arttığını** söyler.

Bunu ayırt etmek şart, çünkü mühendislikte en sık yapılan hatalardan biri Big-O'yu bir hız ölçüsü sanmaktır. Aslında Big-O bir *büyüme oranı* (growth rate) ölçüsüdür. Girdi boyutunu genelde `n` ile gösteririz. Bir algoritma `O(n)` ise, girdiyi iki katına çıkardığınızda iş yükü de yaklaşık iki katına çıkar. `O(n²)` ise girdiyi iki katına çıkardığınızda iş yükü dört katına çıkar. `O(log n)` ise girdiyi iki katına çıkardığınızda iş yükü sadece bir birim artar.

Formel olarak, `f(n) = O(g(n))` ifadesi şu anlama gelir: yeterince büyük `n` değerleri için (bir `n₀` eşiğinden sonra) ve bir `c` sabiti için, `f(n) <= c · g(n)` her zaman doğrudur. Bu tanımın iki gizli mesajı vardır ve ikisi de pratikte hayati önem taşır:

1. **"Yeterince büyük n için"**: Big-O küçük girdileri umursamaz. Küçük veri kümelerinde `O(n²)` bir algoritma, `O(n log n)` bir algoritmadan daha hızlı olabilir.
2. **"Bir c sabiti için"**: Sabit çarpanlar ve düşük dereceli terimler atılır. `5n + 100` de `O(n)`'dir, `0.001n` de `O(n)`'dir. Big-O bu sabitleri gizler; bu hem gücü hem de tehlikesidir.

Büyüme oranını sınıflandırmak için üç ayrı notasyon kullanılır ve bunları karıştırmak yaygın bir kavram hatasıdır:

- **O (Big-O)**: Üst sınır. "En kötü ihtimalle bu kadar." Bir tavan.
- **Ω (Big-Omega)**: Alt sınır. "En iyi ihtimalle en az bu kadar." Bir zemin.
- **Θ (Big-Theta)**: Sıkı sınır. Hem üst hem alt sınır aynı olduğunda, yani algoritma tam olarak bu oranda büyüdüğünde.

Günlük konuşmada herkes "O(n log n)" der ama çoğu zaman kastedilen Θ'dır (sıkı sınır). Teknik doğruluk açısından, bir algoritmanın *en kötü durumunun* Θ'sını söylemek Big-O'dan daha bilgilendiricidir; ama Big-O daha güvenli bir taahhüt olduğu için sektörde standarttır.

## Kök neden: Neden sabitleri atıyoruz ve neden büyüme oranı önemli?

Bu, konunun kalbidir ve genellikle atlanır. Neden `3n² + 500n + 10000` ifadesini alıp sadece `O(n²)` diye yazıyoruz? Attığımız o `500n` terimi ve `10000` sabiti küçük değil ki.

Cevap, **asimptotik davranış** kavramında yatar. `n` çok büyüdüğünde, en yüksek dereceli terim diğer her şeyi ezip geçer. Somut sayılarla görelim: `n = 1.000.000` için `n²` terimi `10¹²`'dir. `500n` terimi ise `5 × 10⁸`'dir. Yani ikinci terim, baskın terimin binde biri kadardır bile değil. `n` daha da büyüdükçe bu oran giderek küçülür. Dolayısıyla büyük ölçekte algoritmanın kaderini tek başına en yüksek dereceli terim belirler. Diğer terimleri taşımak, uzun vadeli davranışı anlamaya hiçbir şey katmaz, sadece analizi karmaşıklaştırır.

Peki neden sabit çarpanları da atıyoruz? Çünkü sabit çarpanlar **donanıma, dile, derleyiciye ve implementasyona** bağlıdır; algoritmanın özsel yapısına değil. Aynı `O(n)` algoritmasını C ile yazarsanız sabitiniz küçük, saf Python ile yazarsanız 50 kat büyük olabilir. Big-O bu implementasyon detaylarından soyutlanarak "algoritmanın kendisi" hakkında konuşmamızı sağlar. Bir donanım iki kat hızlanabilir, ama bu `O(n²)` bir algoritmayı `O(n)` yapmaz; sadece sabiti değiştirir. Ölçek büyüdüğünde daha iyi bir büyüme oranı, her zaman daha hızlı donanımı yener.

İşte burada mühendislik sezgisi devreye girer: Büyüme oranı, ölçeklenebilirliğin kaderidir. Küçük bir startup'ın 1.000 kullanıcısı varken `O(n²)` bir sorgu fark edilmez. Ama kullanıcı sayısı 10 milyon olduğunda, aynı sorgu sistemi çökertir. Kod değişmemiştir; sadece `n` büyümüştür ve `O(n²)`'nin doğası kendini göstermiştir. Karmaşıklık analizini bilmek, bu çöküşü kod daha yazılırken öngörmek demektir.

### Büyüme sınıflarının hiyerarşisi

En hızlıdan en yavaşa doğru başlıca sınıflar ve sezgisel anlamları:

- **O(1) — Sabit**: Girdi ne olursa olsun aynı maliyet. Hash tablosundan okuma, dizinin belli bir indeksine erişme.
- **O(log n) — Logaritmik**: Her adımda problemi yarıya bölmek. Sıralı dizide binary search. `n` milyona çıksa bile ~20 adım.
- **O(n) — Doğrusal**: Her elemana bir kez dokunmak. Bir listeyi tarama.
- **O(n log n) — Doğrusal-logaritmik**: İyi sıralama algoritmalarının (merge sort, heapsort) sınırı. Karşılaştırmaya dayalı sıralamada teorik olarak aşılamaz.
- **O(n²) — Kareli**: İç içe iki döngü. Her elemanı her elemanla kıyaslamak.
- **O(2ⁿ) — Üstel**: Her elemanda ikiye dallanmak. Naif özyinelemeli çözümler, alt küme üretimi.
- **O(n!) — Faktöriyel**: Tüm permütasyonları denemek. Naif gezgin satıcı problemi.

Bu hiyerarşinin pratik dersi şudur: `O(2ⁿ)` ve `O(n!)` algoritmalar `n` yaklaşık 30-40'ı geçtiğinde evrenin ömründen uzun sürebilir. Bu yüzden onlara "işlenemez" (intractable) denir. `O(n²)` ile `O(n log n)` arasındaki fark ise genellikle bir web servisinin milyonlarca istekte ayakta kalmasıyla çökmesi arasındaki farktır.

## Zaman karmaşıklığı ve uzay karmaşıklığı: iki ayrı bütçe

Karmaşıklık analizi iki ayrı kaynağı ölçer ve bunlar sıklıkla birbirleriyle takas edilir.

**Zaman karmaşıklığı**, algoritmanın yürütmesi gereken temel işlem (basic operation) sayısının girdiyle nasıl büyüdüğüdür. Burada "işlem" derken karşılaştırma, atama, aritmetik gibi sabit sürede biten adımları kastederiz. Zaman analizinde işin çoğu döngüleri saymaktır: iç içe döngüler çarpılır, ardışık döngüler toplanır (ve toplamda baskın olan kalır).

**Uzay karmaşıklığı**, algoritmanın girdinin kendisi *dışında* ihtiyaç duyduğu ek belleğin (auxiliary space) girdiyle büyümesidir. Girdiyi tutmak için gereken bellek genelde sayılmaz, çünkü o zaten verilmiştir; önemli olan algoritmanın kendi başına ne kadar *ekstra* alan istediğidir. Örneğin bir diziyi yerinde (in-place) ters çeviren bir algoritma `O(1)` ek alan kullanır; ama sonucu yeni bir diziye kopyalayan bir algoritma `O(n)` ek alan kullanır.

Buradaki en önemli mühendislik kavramı **zaman-uzay takasıdır** (time-space tradeoff). Çoğu zaman daha fazla bellek harcayarak zamandan tasarruf edebiliriz, ya da tersi. Klasik örnek: bir fonksiyonun daha önce hesapladığı sonuçları bir tabloda saklamak (memoization). Bu, `O(2ⁿ)` özyinelemeli bir Fibonacci hesabını `O(n)` zamana indirir, ama karşılığında `O(n)` bellek harcar. Zaman kazanılmış, bellek verilmiştir.

Bu takas gerçek sistemlerde her yerdedir. Bir veritabanı index'i tam olarak budur: sorguları hızlandırmak (zaman) için ekstra disk alanı (uzay) harcarsınız. Cache'leme de aynı mantıktır. İyi bir mühendis, hangi kaynağın kıt olduğunu bilerek bu takası bilinçli yapar. Bellek boldu ama gecikme kritikse belleği harcarsınız; gömülü bir sistemde RAM 64 KB ise zamanı harcarsınız.

## Somut örnek: aynı problemi iki farklı büyüme oranıyla çözmek

Diyelim ki bir listede bir sayının olup olmadığını arıyoruz. İki yaklaşım karşılaştıralım.

**Yaklaşım 1 — Doğrusal arama, O(n):**

```python
def var_mi(liste, hedef):
    for eleman in liste:      # n kez döner
        if eleman == hedef:
            return True
    return False
```

Bu kod en kötü durumda (hedef listede yoksa ya da sondaysa) `n` elemanın hepsine bakar. Zaman `O(n)`, ek uzay `O(1)`.

**Yaklaşım 2 — Önce set'e koy, sonra ara, O(1) sorgu:**

```python
def hazirla(liste):
    return set(liste)          # O(n) bir kerelik kurulum

def var_mi(kume, hedef):
    return hedef in kume       # ortalama O(1)
```

Burada `set` bir hash tablosudur ve içindeki eleman aramayı ortalama `O(1)` zamanda yapar. Ama karşılığında `O(n)` ek bellek harcadık (set'i tutmak için) ve `O(n)` bir kurulum maliyeti ödedik.

Ders şudur: eğer bu listede **bir kez** arama yapacaksak, set kurmak anlamsızdır; doğrusal arama zaten `O(n)` ve set kurulumu da `O(n)`, üstelik bellek harcamıyoruz. Ama aynı liste üzerinde **binlerce kez** arama yapacaksak, bir kerelik `O(n)` kurulum maliyetini ödeyip her sorguyu `O(1)`'e indirmek muazzam bir kazançtır. Analiz, kullanım desenini bilmeden yapılamaz — Big-O'yu bağlamdan kopararak uygulamak en yaygın hatalardan biridir.

## En kötü, ortalama ve en iyi durum: hangisini konuşuyoruz?

Bir algoritmanın karmaşıklığı çoğu zaman tek bir sayı değildir; girdinin *içeriğine* göre değişir. Bu yüzden üç senaryoyu ayırırız.

**En iyi durum (best case)**, işlerin en lehimize gittiği girdidir. Örneğin doğrusal aramada hedef ilk elemansa, `O(1)`'de biter. En iyi durum genellikle yanıltıcıdır ve mühendislikte nadiren güvenilir; çünkü şansımıza bel bağlayamayız.

**En kötü durum (worst case)**, işlerin en aleyhimize gittiği girdidir. Bu, Big-O ile en sık verilen taahhüttür, çünkü bir **garanti** sunar: "Ne olursa olsun, bundan daha kötü olmayacak." Gerçek zamanlı sistemlerde, güvenlik açısından kritik yazılımlarda ve SLA taahhütlerinde daima en kötü durumu düşünürüz. Bir uçağın kontrol yazılımı "ortalamada hızlı" olamaz; her zaman zamanında bitmelidir.

**Ortalama durum (average case)**, tüm olası girdiler üzerinden beklenen maliyettir. Bu, pratikte en çok deneyimlenen performansı yansıtır ama tanımlaması zordur, çünkü "girdilerin dağılımı" hakkında varsayım yapmayı gerektirir. Gerçek dünyada girdiler rastgele değildir; bu yüzden teorik ortalama durum ile pratik davranış ayrışabilir.

Bu ayrımın en öğretici örneği **quicksort**'tur. Quicksort'un ortalama durumu `O(n log n)` ile mükemmeldir ve pratikte çoğu sıralama algoritmasından hızlıdır. Ama en kötü durumu `O(n²)`'dir — bu, pivot seçimi her seferinde en kötü elemanı seçtiğinde (örneğin zaten sıralı bir dizide sabit pivot kullanılırsa) olur. Naif implementasyonlarda bu, kötü niyetli bir saldırganın özel olarak hazırlanmış girdilerle sistemi `O(n²)`'ye zorlaması anlamına gelir (algorithmic complexity attack denen bir saldırı türü). Bu yüzden gerçek dünya quicksort'ları pivotu rastgele seçer ya da introsort gibi hibrit yaklaşımlarla en kötü durumu `O(n log n)`'e sabitler.

Bir başka klasik örnek **hash tablosu**dur. Ortalama durumda ekleme/arama `O(1)`'dir ve bu yüzden hash tabloları her yerde kullanılır. Ama en kötü durumda — tüm anahtarlar aynı bucket'a düşerse (hash collision) — `O(n)`'e kadar bozulabilir. İyi bir hash fonksiyonu ve yeniden boyutlandırma stratejisi bu en kötü durumu pratikte neredeyse imkânsız kılar, ama teorik olarak vardır ve bilinmesi gerekir.

## Amortized (itfa edilmiş) analiz: pahalı işlemin maliyetini yaymak

Amortized analiz, karmaşıklık teorisinin en zarif ve en yanlış anlaşılan kavramlarından biridir. Sorduğu soru şudur: "Tek bir işlem bazen çok pahalı olabilir, ama bir dizi işlemin *ortalama* maliyeti nedir?"

Bunu ortalama durumla karıştırmamak kritik. **Ortalama durum**, girdilerin olasılıksal dağılımı üzerinden bir ortalamadır ve şans içerir. **Amortized analiz** ise olasılık içermez; bir işlem *dizisi* üzerinde en kötü durumda bile toplam maliyeti garanti eder ve bunu işlem sayısına böler. Yani amortized `O(1)`, "ortalamada hızlı olabilir" demek değil, "herhangi bir uzun işlem dizisinde işlem başına maliyet garantili olarak sabittir" demektir.

En temiz örnek **dinamik dizi** (Python'da `list`, Java'da `ArrayList`, C++'ta `vector`) sonuna eleman ekleme işlemidir. Dizi dolduğunda daha büyük bir bellek bloğu ayrılır ve tüm elemanlar oraya kopyalanır — bu tek işlem `O(n)`'dir. Öyleyse `append` `O(n)` mi? Hayır. Çünkü dizi genellikle **iki katına** çıkarılır. Kopyalama pahalı olsa da nadiren olur: `n` elemanı eklemek için toplam kopyalama sayısı `n + n/2 + n/4 + ... ≈ 2n`'dir. Yani `n` eklemenin toplam maliyeti `O(n)`, işlem başına `O(1)`'dir. Buna **amortized O(1)** denir.

Neden iki katına çıkarmak işe yarar da, örneğin her seferinde bir eleman daha büyütmek (fixed increment) çalışmaz? Çünkü sabit artışta her ekleme neredeyse tam kopyalama gerektirir ve toplam maliyet `O(n²)` olur. Geometrik büyüme (iki katı, ya da 1.5 katı), pahalı yeniden boyutlandırmaları o kadar seyrekleştirir ki maliyetleri araya yayıldığında sabit kalır. Bu, amortized analizin kök sezgisidir: nadir ama pahalı olaylar, sık ve ucuz olaylara "yayıldığında" ortalama sabit kalabilir.

Amortized analiz için üç klasik yöntem vardır:

- **Toplam (aggregate) yöntemi**: `n` işlemin toplam maliyetini hesapla, `n`'e böl. Yukarıdaki gibi.
- **Muhasebe (accounting) yöntemi**: Ucuz işlemlere "fazladan ücret" yükle, bu krediyi biriktir, pahalı işlemde harca. Sanki her `append` işlemi ileride yapılacak kopyalama için önceden ödeme yapar gibi.
- **Potansiyel (potential) yöntemi**: Veri yapısının bir "potansiyel enerji" fonksiyonunu tanımla; işlemler bu potansiyeli yükseltir ya da düşürür, gerçek maliyet artı potansiyel değişimi amortized maliyeti verir.

Kritik uyarı: Amortized `O(1)`, her *tekil* işlemin hızlı olduğunu garanti etmez. Gerçek zamanlı bir sistemde, o nadir `O(n)` yeniden boyutlandırma tam da kritik anda gelirse bir gecikme tıkanması (latency spike) yaratabilir. Bu yüzden düşük gecikme gereksinimleri olan sistemler bazen amortized-hızlı ama worst-case-yavaş yapılardan kaçınıp, her işlemi garantili hızlı olan yapıları (örneğin önceden ayrılmış sabit boyutlu tamponlar) tercih eder. "Amortized ortalaması iyi" ile "her seferinde iyi" farklı şeylerdir ve bu ayrım production'da önem taşır.

## Doğru kullanım ve tuzaklar

**Sabitler küçük ölçekte kraldır.** Big-O sabitleri gizler, ama sabitler yok olmaz. `n` küçükken `O(n²)` bir insertion sort, `O(n log n)` bir merge sort'tan daha hızlı olabilir çünkü sabiti ve genel giderleri (overhead) çok düşüktür. Bu yüzden gerçek dünya sıralama kütüphaneleri (örneğin timsort) küçük alt dizilerde insertion sort'a düşer. Asimptotik üstünlük ancak `n` yeterince büyükse gerçekleşir; eşik değerini bilmek mühendisliktir.

**Bellek hiyerarşisi görünmezdir ama gerçektir.** Big-O modeli, her bellek erişiminin eşit maliyetli olduğunu varsayar. Gerçekte CPU cache'ine sığan bir erişim, RAM'e gitmekten yüzlerce kat hızlıdır. Bu yüzden teoride aynı `O(n)` olan iki algoritma pratikte 10 kat farklı hızda çalışabilir: biri bellekte ardışık (cache-friendly) erişirken diğeri rastgele sıçrar. Bir bağlı liste (linked list) ile bir dizi (array) taramak ikisi de `O(n)`'dir, ama dizi cache dostluğu sayesinde çok daha hızlıdır. Big-O bunu görmez.

**Girdi boyutunun ne olduğunu net tanımlayın.** `n` neyi ölçüyor? Eleman sayısı mı, bit sayısı mı, string uzunluğu mu? Örneğin bir sayının asal olup olmadığını test eden naif bir algoritma "sayıya kadar döndüğü için" `O(n)` gibi görünür; ama girdi boyutu sayının *basamak sayısıdır* (yani `log n` bit), dolayısıyla algoritma aslında girdi boyutuna göre üsteldir. Bu, kriptografinin dayandığı ince ayrımdır.

## Yaygın hatalar

**Big-O'yu hız sanmak.** En temel hata. `O(n log n)` "hızlı" değildir; sadece `O(n²)`'den *daha iyi ölçeklenir*. Küçük veride tersine bile dönebilir.

**Sabit çarpanları küçümsemek.** "İkisi de O(n), fark etmez" cümlesi çoğu performans felaketinin başlangıcıdır. `2n` ile `100n` arasında pratikte 50 kat fark vardır ve bu gerçektir.

**Gizli maliyetleri görmezden gelmek.** Bir döngü içinde string birleştirme (`s += x`) masumca `O(1)` gibi görünür, ama çoğu dilde string değişmez (immutable) olduğu için her birleştirme yeni bir string kopyalar; döngü toplamda `O(n²)` olur. Aynı şekilde, bir döngü içinde `liste.contains(x)` çağrısı `O(n)`'dir ve döngüyle çarpılıp `O(n²)` yaratır. Bu tür tuzaklar dilin standart kütüphanesinin karmaşıklığını bilmeyi gerektirir.

**Ortalama durum ile amortized'ı karıştırmak.** Biri olasılıksal, diğeri deterministik bir garantidir. Bir hash tablosu ortalama `O(1)`'dir (girdi dağılımına bağlı); dinamik dizi append amortized `O(1)`'dir (dağılımdan bağımsız garanti). Terimleri gevşek kullanmak yanlış güven yaratır.

**En kötü durumu yok saymak.** "Pratikte hep hızlı" diyerek en kötü durumu görmezden gelmek, algorithmic complexity attack'lara ve nadir ama yıkıcı gecikme tıkanmalarına kapı açar. Düşman girdilerle karşılaşabilecek her sistemde en kötü durum bir güvenlik meselesidir.

**Uzayı unutmak.** Herkes zamana bakar, ama bir algoritma `O(n)` zamanda çalışıp `O(n)` bellek harcayarak büyük veride belleği tüketip çökebilir. Özyinelemenin çağrı yığını (call stack) da bir uzay maliyetidir; derin özyineleme `O(n)` yığın alanı kullanır ve stack overflow ile patlar.

## En iyi pratikler

**Önce doğru büyüme sınıfını seçin, sonra sabitleri optimize edin.** `O(n²)`'den `O(n log n)`'e geçmek, `O(n²)` kodu iki kat hızlandırmaktan çok daha değerlidir — yeterince büyük veride. Algoritmik iyileştirme her zaman mikro-optimizasyondan önce gelir.

**Ama önce ölçün, sonra optimize edin.** Big-O bir kılavuzdur, kanıt değil. Gerçek darboğazı bulmak için profiling yapın. En kötü Big-O'ya sahip kod parçası, `n` küçükse ya da nadiren çağrılıyorsa hiç önemli olmayabilir. "Erken optimizasyon" tuzağına düşmeden, gerçek verinin gerçek büyüklüğüne göre karar verin.

**Kullanım desenini analiz edin.** Bir veri yapısı seçerken tek bir işlemin değil, işlem *karışımının* karmaşıklığına bakın. Çok okuma az yazma mı, tersi mi? Hangi işlem sıcak yolda (hot path)? Bir yapı bir işlemde `O(1)`, diğerinde `O(n)` olabilir; sizin için önemli olanı optimize eden yapıyı seçin.

**Standart kütüphanenizin karmaşıklıklarını bilin.** Kullandığınız dilin sözlük, liste, küme işlemlerinin Big-O'sunu ezbere bilmek, farkında olmadan `O(n²)` yazmaktan korur. Dokümantasyon çoğu zaman bu garantileri açıkça belirtir.

**En kötü durumu bir tasarım kararı olarak ele alın.** Sistem düşman girdilerle karşılaşabiliyor ya da katı gecikme garantileri gerektiriyorsa, ortalama durumu değil en kötü durumu hedefleyen yapılar seçin; amortized-hızlı ama worst-case-yavaş yapıların gecikme tıkanması riskini bilinçli değerlendirin.

**Zaman-uzay takasını bilinçli yapın.** Hangi kaynağın kıt olduğunu belirleyin ve boldan harcayıp kıttan tasarruf edin. Cache, index, memoization — hepsi aynı takasın farklı yüzleridir. Bilinçsiz yapıldığında bellek şişmesine, bilinçli yapıldığında büyük hızlanmaya yol açar.

Karmaşıklık analizi, kodun bugünkü hızını değil, yarın on kat, yüz kat büyüdüğünde ayakta kalıp kalmayacağını öngörme sanatıdır. Bir mühendisi tecrübeli kılan, bu ölçeklenme eğrisini kod daha yazılırken zihninde görebilmesidir.
