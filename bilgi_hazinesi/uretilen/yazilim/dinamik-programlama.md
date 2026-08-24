# Dinamik Programlama

## Tanım

Dinamik programlama (dynamic programming, kısaca DP), bir problemi **birbiriyle örtüşen alt problemlere** ayırıp, her alt problemi yalnızca bir kez çözerek ve sonucunu saklayarak toplam işi dramatik biçimde azaltan bir algoritma tasarım tekniğidir. İsimdeki "programlama" kelimesi bilgisayar programlamayla değil, 1950'lerde Richard Bellman'ın kullandığı anlamıyla "tablo doldurarak planlama yapma" ile ilgilidir; yani bir karar tablosunu (schedule) optimize etme fikrinden gelir.

DP'yi tek cümlede özetlemek gerekirse: **tekrar tekrar hesaplayacağın şeyleri bir kez hesapla, sakla, tekrar sorulduğunda hafızadan oku.** Bu kadar basit görünen fikir, üstel (exponential) karmaşıklıktaki birçok problemi polinom zamana indirir. Ancak DP'yi bir "hile" gibi görmek yanıltıcıdır; tekniğin uygulanabilmesi için problemin iki temel yapısal özelliği taşıması gerekir: **optimal substructure** ve **overlapping subproblems**. Bu iki koşul sağlanmadan DP ne doğru sonuç verir ne de bir hız kazancı sunar. Makalenin omurgası bu iki koşulun neden bu kadar kritik olduğunu anlatmak üzerine kuruludur.

## Kök Neden: DP Neden Çalışır?

DP'nin işe yaramasının arkasında iki bağımsız yapısal koşul vardır. Bu ikisini ayrı ayrı anlamak, DP'yi ezberlemek ile gerçekten kavramak arasındaki farkı belirler.

### Optimal Substructure (Optimal Alt Yapı)

Bir problem, **optimal çözümü alt problemlerinin optimal çözümlerinden inşa edilebiliyorsa** optimal substructure özelliğine sahiptir. Yani "büyük problemin en iyi cevabı, küçük parçaların en iyi cevaplarını birleştirerek elde edilebilir" demektir.

Bunun neden önemli olduğunu bir karşı örnekle görmek en açıklayıcı yoldur. Bir grafta iki nokta arasındaki **en kısa yol** optimal substructure taşır: eğer A'dan C'ye giden en kısa yol B üzerinden geçiyorsa, o yolun A'dan B'ye olan parçası da A-B arasının en kısa yolu olmak zorundadır. Aksi halde daha kısa bir A-B parçasıyla toplam yolu kısaltabilirdik, bu da "en kısa" varsayımımızla çelişir. İşte bu "parçanın da optimal olması zorunluluğu", en kısa yol problemlerini DP ile (Bellman-Ford, Floyd-Warshall gibi) çözülebilir kılar.

Buna karşılık **en uzun basit yol** (longest simple path, aynı düğümü tekrar ziyaret etmeden) optimal substructure taşımaz. A'dan C'ye giden en uzun basit yolun A-B parçası, A-B arasındaki en uzun basit yol olmak zorunda değildir; hatta o parçayı en uzun yapmaya çalışırsanız, kalan yolda kullanmanız gereken bir düğümü tüketmiş olabilirsiniz ve sonuç geçersiz hale gelir. Alt problemlerin çözümleri birbirini kısıtladığı için parçaları bağımsız optimize edemezsiniz. Bu yüzden en uzun basit yol NP-hard'dır ve saf DP ile çözülemez. Bu karşıtlık, optimal substructure'ın neden bir "lüks" değil, DP'nin ön koşulu olduğunu net gösterir.

### Overlapping Subproblems (Örtüşen Alt Problemler)

İkinci koşul, aynı alt problemin **defalarca** ortaya çıkmasıdır. Eğer bir problemi alt problemlere böldüğünüzde her alt problem yalnızca bir kez görünüyorsa, saklamanın (memoization) size bir faydası olmaz; bu durumda klasik **divide and conquer** (böl ve yönet, örneğin merge sort) yeterlidir ve DP'ye gerek yoktur.

DP'nin asıl gücü, alt problemler tekrar tekrar çakıştığında ortaya çıkar. Klasik Fibonacci örneği bunu mükemmel gösterir. `fib(5)` hesaplamak için `fib(4)` ve `fib(3)` gerekir; `fib(4)` için `fib(3)` ve `fib(2)` gerekir. `fib(3)` burada iki kere hesaplanıyor. Ağaç büyüdükçe bu tekrar üstel olarak patlar: naif özyinelemeli (recursive) Fibonacci O(2^n) çağrı yapar. Oysa farklı alt problem sayısı sadece n tanedir (fib(0)'dan fib(n)'e). Her birini bir kez hesaplayıp saklarsanız karmaşıklık O(n)'e düşer. **İşte tam bu "az sayıda farklı alt problem, çok sayıda tekrar" durumu DP'nin var oluş sebebidir.**

Bu iki koşulu birlikte düşünün: optimal substructure size çözümü *nasıl birleştireceğini* söyler, overlapping subproblems ise *saklamanın neden işe yarayacağını* söyler. İkisi bir arada olduğunda DP kaçınılmaz olarak doğru araçtır.

## İki Yaklaşım: Memoization ve Tabulation

DP'nin iki klasik uygulama biçimi vardır ve aralarındaki farkı anlamak pratikte çok işe yarar.

### Memoization (Top-Down / Yukarıdan Aşağıya)

Memoization, doğal özyinelemeli çözümü alıp üzerine bir **önbellek** (cache) eklemektir. Problemi büyükten küçüğe doğru düşünürsünüz: "fib(n) için fib(n-1) ve fib(n-2) lazım" dersiniz, özyineleme kendiliğinden küçük problemlere iner. Fark şudur: bir alt problem çözülmeden önce önbelleğe bakılır; oradaysa tekrar hesaplanmaz, doğrudan döndürülür.

```python
def fib(n, memo={}):
    if n < 2:
        return n
    if n in memo:          # daha once hesaplandi mi?
        return memo[n]
    memo[n] = fib(n - 1, memo) + fib(n - 2, memo)
    return memo[n]
```

Memoization'ın en büyük avantajı **doğallığıdır**: problemin matematiksel tanımını (recurrence) neredeyse birebir koda çevirirsiniz. Ayrıca yalnızca **gerçekten ihtiyaç duyulan** alt problemler hesaplanır; erişilmeyen durumlar hiç çözülmez. Bu, tablonun büyük ama fiilen ziyaret edilen kısmının küçük olduğu problemlerde ciddi kazanç sağlar.

Dezavantajı ise özyineleme derinliğidir. Çok derin problemlerde çağrı yığını (call stack) taşabilir (stack overflow) ve fonksiyon çağrısı ek yükü, sıkı döngülere göre biraz daha yavaştır.

> Yukarıdaki koddaki `memo={}` **mutable default argument** tuzağıdır: Python'da varsayılan sözlük bir kez oluşturulur ve çağrılar arasında paylaşılır. Öğretici olarak önbelleği otomatik paylaştırdığı için burada işe yarasa da, gerçek kodda bilinçsizce kullanılırsa şaşırtıcı hatalara yol açar. Doğrusu, önbelleği açıkça dışarıdan yönetmek ya da `functools.lru_cache` gibi bir dekoratör kullanmaktır.

### Tabulation (Bottom-Up / Aşağıdan Yukarıya)

Tabulation, işi ters yönden yapar: en küçük alt problemlerden başlar, bir tabloyu (dizi) sırayla doldurarak büyük probleme çıkar. Özyineleme yoktur; sadece döngü vardır.

```python
def fib(n):
    if n < 2:
        return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]
```

Tabulation'ın avantajı **öngörülebilirliğidir**: özyineleme derinliği sorunu yoktur, fonksiyon çağrısı ek yükü yoktur, bellek erişim düzeni genellikle cache-friendly olur (bellekte sırayla ilerlediği için işlemcinin önbelleğini iyi kullanır). Ayrıca çoğu zaman **bellek optimizasyonu** yapmak burada daha kolaydır. Fibonacci'de görüldüğü gibi `dp[i]` yalnızca son iki değere bağlıdır; dolayısıyla tüm diziyi tutmak yerine iki değişken yeterlidir ve bellek O(n)'den O(1)'e iner.

```python
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```

Tabulation'ın dezavantajı, **doldurma sırasını doğru kurmanın** bazen zor olmasıdır. Bir hücreyi hesaplamadan önce bağımlı olduğu tüm hücrelerin dolu olması gerekir; bu bağımlılık sırasını (topolojik sıra) elle çözmek, özellikle çok boyutlu tablolarda kafa karıştırıcı olabilir. Memoization'da bu sırayı özyineleme sizin için otomatik halleder.

**Hangisini seçmeli?** İlk kez bir DP problemine yaklaşırken memoization genellikle daha kolaydır çünkü recurrence'ı doğrudan yazarsınız. Doğruluğu kanıtladıktan sonra, performans veya bellek kritikse tabulation'a çevirebilirsiniz. İkisi de aynı asimptotik karmaşıklığı verir; fark sabit çarpanlarda ve mühendislik pratiğindedir.

## Bir DP Çözümünü Kurmanın Yöntemi

Deneyimli birinin kafasındaki adımlar aslında bir reçete gibidir. Bir problemin DP ile çözülüp çözülemeyeceğini ve nasıl çözüleceğini şu sorularla test edin:

1. **Durumu (state) tanımla.** Alt problemi tek başına tarif eden en küçük bilgi kümesi nedir? Fibonacci'de bu tek bir `n`'dir. Knapsack'te "ilk i eşya ve kalan kapasite w" olmak üzere iki boyutludur. Durum tanımı yanlışsa geri kalan her şey çöker; DP'nin en zor ve en önemli adımı budur.
2. **Geçiş (recurrence / transition) yaz.** Bir durumun cevabı, daha küçük durumların cevaplarından nasıl elde edilir? Bu, optimal substructure'ın somut ifadesidir.
3. **Taban durumları (base cases) belirle.** Özyinelemenin durduğu, doğrudan bilinen en küçük durumlar nelerdir?
4. **Sırayı ve saklamayı kur.** Memoization ile otomatik, tabulation ile bağımlılık sırasını elle çöz.

Bu dört adım pratikte her DP probleminin iskeletidir. Zorlandığınızda genellikle 1. adımda, yani durumu doğru tanımlamakta zorlanıyorsunuzdur.

## Klasik Problemler

Aşağıdaki problemler yalnızca "bilinmesi gerekenler" listesi değildir; her biri DP'nin farklı bir yönünü öğretir.

### 0/1 Knapsack (Sırt Çantası)

Kapasitesi W olan bir çantanız ve her biri bir ağırlık ve değere sahip eşyalar var. Her eşyayı ya alırsınız ya almazsınız (0/1) ve toplam ağırlığı aşmadan değeri maksimize etmek istersiniz.

**Durum:** `dp[i][w]` = ilk `i` eşya arasından, kapasite `w` iken elde edilebilecek maksimum değer.

**Geçiş:** i'inci eşya için iki seçenek vardır. Ya almazsınız (`dp[i-1][w]`), ya alırsınız (eğer sığıyorsa: `dp[i-1][w - agirlik_i] + deger_i`). İkisinin maksimumunu alırsınız:

```
dp[i][w] = max(
    dp[i-1][w],                                  # i'yi alma
    dp[i-1][w - agirlik_i] + deger_i             # i'yi al (w >= agirlik_i ise)
)
```

Knapsack, optimal substructure'ın "al ya da alma" biçiminde nasıl bir karar ağacına dönüştüğünü ve her düğümde alt problemlerin nasıl çakıştığını gösterir. Karmaşıklık O(n·W)'dir. Buradaki ince nokta şudur: bu karmaşıklık W'ye bağlıdır ve W girdide bir sayı olarak verildiği için aslında **pseudo-polynomial**'dır. W çok büyük olduğunda (örneğin çok basamaklı bir sayı) bu çözüm pratikte yavaşlar; knapsack'in NP-hard sınıfında olmasının nedeni de budur. Bu, "DP her şeyi hızlandırır" yanılgısını kıran önemli bir derstir.

### Longest Common Subsequence (LCS - En Uzun Ortak Alt Dizi)

İki dizinin (örneğin iki metin) sırasını koruyan, ama bitişik olması gerekmeyen en uzun ortak alt dizisini bulur. `diff` araçlarının, sürüm kontrol sistemlerindeki değişiklik gösteriminin ve biyoinformatikte DNA dizi karşılaştırmasının temelidir.

**Durum:** `dp[i][j]` = birinci dizinin ilk `i` karakteri ile ikinci dizinin ilk `j` karakteri arasındaki LCS uzunluğu.

**Geçiş:** Son karakterlere bakılır. Eşleşiyorlarsa ortak diziyi bir uzatırsınız (`dp[i-1][j-1] + 1`). Eşleşmiyorlarsa, ya birinci dizinin son karakterini ya da ikincininkini atarsınız ve iki durumdan iyisini alırsınız (`max(dp[i-1][j], dp[i][j-1])`). LCS, iki boyutlu durum tablosunun ve "son elemana bakarak karar verme" mantığının klasik örneğidir. Karmaşıklık O(m·n)'dir.

### Edit Distance (Levenshtein Mesafesi)

Bir kelimeyi başka bir kelimeye çevirmek için gereken minimum ekleme, silme ve değiştirme sayısıdır. Yazım denetleyicilerinin "bunu mu demek istediniz?" önerilerinin, otomatik düzeltmenin ve bulanık arama (fuzzy search) motorlarının kalbinde bu vardır. LCS ile aynı iskelete sahiptir ama geçişte üç operasyonun (ekle, sil, değiştir) minimumu alınır. Neden çalıştığını kavramak için LCS ile karşılaştırmak öğreticidir: aynı "iki dizi, iki boyutlu tablo" yapısı, farklı bir amaç fonksiyonuyla yeniden kullanılır.

### Coin Change (Para Üstü)

Verilen kupürlerle belli bir tutarı en az kaç parayla oluşturabileceğinizi (ya da kaç farklı yolla oluşturabileceğinizi) sorar. Bu problem, DP ile **açgözlü (greedy)** algoritma arasındaki farkı anlamak için altın değerindedir. Bazı para sistemlerinde (örneğin bilinen çoğu resmi para birimi) "her seferinde en büyük kupürü al" açgözlü stratejisi doğru sonuç verir. Ama keyfi kupür kümelerinde açgözlü çöker: örneğin kupürler {1, 3, 4} ve hedef 6 ise, açgözlü "4+1+1 = 3 para" der, oysa optimal cevap "3+3 = 2 para"dır. DP burada tüm olasılıkları örtük olarak deneyerek doğru minimumu garanti eder. **Ders:** optimal substructure her problemde vardır sanmak yanlıştır; ama var olduğunda greedy'nin gözden kaçırdığı çözümleri DP yakalar.

### Matrix Chain Multiplication (Matris Zinciri Çarpımı)

Birden fazla matrisi çarparken (çarpma birleşmelidir ama sonuç aynıdır) parantezleri nasıl yerleştirirseniz toplam skaler çarpma sayısını en aza indirdiğinizi sorar. Bu problem, durumun "bir aralık" (interval) olduğu **interval DP** ailesinin klasik örneğidir: `dp[i][j]`, i'den j'ye kadarki matrisleri çarpmanın minimum maliyetidir ve geçiş, aralığı ikiye bölen tüm noktaları deneyerek yapılır. Karmaşıklık O(n^3)'tür ve DP'nin "en iyi bölme noktasını bul" tipindeki problemleri nasıl ele aldığını gösterir.

## Doğru Kullanım ve Tuzaklar

### Durum Uzayının Patlaması

DP'nin karmaşıklığı doğrudan **farklı durum sayısı × her geçişin maliyeti** ile belirlenir. Durumu tanımlarken gereğinden fazla boyut eklerseniz, tablonuz üstel olarak büyür ve DP'nin sağladığı avantaj yok olur. Örneğin knapsack'te durumu sadece kapasiteyle tanımlamak yeterken, gereksiz yere "hangi eşyaların alındığı kümesi"ni de duruma koyarsanız durum sayısı 2^n'e fırlar. **İyi bir DP çözümü, doğru cevabı vermek için gereken en küçük durum tanımını bulur.** Bu bir sanattır ve pratikle gelişir.

### Bellek Optimizasyonu ve Yol Geri Kurma (Path Reconstruction) Gerilimi

Birçok DP'de `dp[i]` yalnızca son birkaç satıra bağlıdır, dolayısıyla eski satırları atarak bellekten büyük tasarruf yapabilirsiniz (Fibonacci'deki O(n)→O(1) gibi). Ancak dikkat: yalnızca **optimal değeri** değil, o değere ulaştıran **gerçek çözümü** (hangi eşyalar alındı, hangi karakterler eşleşti) de istiyorsanız, geriye dönüp yolu kurmak için tabloyu tutmanız gerekebilir. Değer için bellek küçültme ile çözümü geri kurabilme arasında bir denge (trade-off) vardır; bunu baştan planlamazsanız, optimize edilmiş kodunuzda "cevabı biliyorum ama nasıl elde edildiğini söyleyemiyorum" durumuna düşersiniz.

### Kayan Nokta ve Taşma

Değerler büyükse (örneğin sayma problemlerinde yol sayısı) sonuç integer taşmasına (overflow) uğrayabilir; birçok yarışma problemi bu yüzden sonucu bir modülo ile ister. Kayan nokta değerlerle DP yaparken de eşitlik karşılaştırmaları güvenilmezdir. Bu detaylar, doğru algoritma yanlış tip seçimiyle sessizce bozulabildiği için önemlidir.

## Yaygın Hatalar

**Optimal substructure olmadan DP uygulamaya çalışmak.** En sık ve en sinsi hatadır. Problem "en iyi bir şeyi bul" dediği için insanlar refleks olarak DP kurar; ama alt problemler birbirini kısıtlıyorsa (en uzun basit yol örneğindeki gibi) sonuç yanlış olur. DP kurmadan önce "parçaların optimalliği bütünün optimalliğini garanti ediyor mu?" sorusunu dürüstçe cevaplayın.

**Durumu eksik tanımlamak.** Eğer iki farklı gerçek durum aynı `dp` hücresine düşüyorsa ama farklı cevaplar gerektiriyorsa, tablonuz yanlış değerlerle "kirlenmiştir" (state aliasing). Cevap bazen doğru bazen yanlış çıkar ve hata bulunması çok zordur. Kural: durum, o alt problemin cevabını **tek başına** belirleyecek her şeyi içermelidir.

**Yanlış doldurma sırası (tabulation'da).** Bir hücreyi, bağımlı olduğu hücreler henüz dolmadan hesaplamak. Bu genellikle döngü sınırlarında ya da yönünde bir hatadır; sonuç sessizce yanlış çıkar, çünkü kod çöker değil, sadece boş/eski değerleri okur.

**Base case'leri unutmak veya yanlış kurmak.** Özyinelemenin durma koşulu eksikse sonsuz döngü ya da yanlış sonuç olur. Base case, çoğu zaman "boş girdi" durumudur ve gözden kaçması kolaydır (örneğin LCS'de dizilerden biri boşken cevabın 0 olması).

**Memoization'da önbelleği anahtarlarken durumun tüm boyutlarını kullanmamak.** Çok boyutlu bir durumu tek boyutla anahtarlarsanız (örneğin sadece `i` ile, ama gerçek durum `(i, w)` ise) farklı durumlar birbirinin cevabını okur. Bu, sessiz ve tespiti güç bir hata sınıfıdır.

**DP'yi gerekmeyen yerde kullanmak.** Alt problemler örtüşmüyorsa DP, divide and conquer'a göre ek karmaşıklık getirir ama hız kazandırmaz. Her "alt problemlere bölme" DP değildir.

## En İyi Pratikler

**Önce recurrence'ı kâğıtta doğrula.** Kod yazmadan önce durum, geçiş ve base case'leri açıkça yazın. DP hatalarının büyük çoğunluğu koddan değil, yanlış recurrence'tan kaynaklanır. Doğru matematik, yanlış koddan çok daha kolay düzeltilir.

**Küçük girdilerle naif çözümle karşılaştırın.** DP çözümünüzü, tüm olasılıkları deneyen yavaş ama açıkça doğru bir "brute force" ile küçük girdilerde karşılaştırın (buna yarışma dünyasında *stress testing* denir). Uyuşmazlık varsa hatanızı küçük, ayıklanabilir bir örnekte yakalarsınız. Bu tek alışkanlık, sessiz DP hatalarının çoğunu erken yakalar.

**Önce top-down ile doğru çözümü elde edin, sonra gerekirse bottom-up'a çevirin.** Memoization'ı recurrence'tan yazmak daha az hata riskiyle çalışan bir çözüm verir. Performans darboğazı ölçümle kanıtlandığında tabulation'a ve bellek optimizasyonuna geçin. Erken optimizasyon burada da tuzaktır.

**Durumu olabildiğince küçük tutun.** Duruma bir boyut eklemenin karmaşıklığı çarpan olarak artırdığını unutmayın. "Bu bilgi gerçekten alt problemin cevabını belirlemek için gerekli mi, yoksa geçişte türetebilir miyim?" diye sorun.

**Hazır araçları küçümsemeyin.** Python'da `functools.lru_cache` / `cache` dekoratörü, doğru yazılmış bir özyinelemeli fonksiyonu tek satırda memoize eder. Elle önbellek yönetiminin getirdiği anahtarlama hatalarından kaçınmak için, uygun olduğunda dilin sunduğu araçları kullanın.

**Karmaşıklığı baştan hesaplayın.** DP çözümünüzün "durum sayısı × geçiş maliyeti" çarpımını yazın ve girdinin en büyük boyutunda bu sayının kabul edilebilir olup olmadığını kontrol edin. Özellikle knapsack gibi pseudo-polynomial problemlerde, W büyükse çözümünüz teoride doğru ama pratikte kullanılamaz olabilir. Bu farkındalık, doğru algoritmayı yanlış problemde harcamaktan sizi korur.

## Kapanış

Dinamik programlama, bir "kalıp koleksiyonu" değil, iki basit yapısal gözleme dayanan bir düşünme biçimidir: optimal substructure (bütünün en iyisi, parçaların en iyisinden kurulur) ve overlapping subproblems (aynı işi tekrar tekrar yapıyoruz). Bu iki koşulu bir problemde tanıyabildiğinizde, geri kalan mekanik iştir: durumu tanımla, geçişi yaz, sakla. Ustalık, bu iki koşulu doğru teşhis etmekte ve durumu mümkün olan en küçük biçimde tanımlamakta yatar. DP'yi gerçekten anlamak, "hangi problemde işe yaramaz?" sorusuna cevap verebilmekle başlar; çünkü bir tekniğin sınırlarını bilmek, onu güvenle kullanmanın ön koşuludur.
