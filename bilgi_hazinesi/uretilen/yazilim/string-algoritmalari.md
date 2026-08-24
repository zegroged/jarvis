# String Algoritmaları: KMP, Rabin-Karp, Trie ve Suffix Yapıları

## Giriş ve Bağlam

String algoritmaları, metin üzerinde arama, eşleştirme, indeksleme ve
sıkıştırma gibi işlemleri verimli yapan temel yapı taşlarıdır. İnsan gözü için
"bir metinde bir kelimeyi bulmak" basit görünür; fakat milyarlarca karakterlik
bir korpusta, saniyede binlerce sorguyla, sınırlı bellekle çalışırken bu
"basit" işlem hızla bir mühendislik problemine dönüşür. DNA dizileri, arama
motoru indeksleri, IDE'lerin otomatik tamamlama motorları, ağ trafiği denetimi
(deep packet inspection), veri tabanı `LIKE` sorguları, sürüm kontrol
sistemlerinin `diff` motorları; hepsi altta string algoritmalarına dayanır.

Bu makale dört ana kavramı derinlemesine işler: **KMP** (Knuth-Morris-Pratt)
tek desen aramada tekrarlı geri gitmeyi (backtracking) nasıl ortadan
kaldırır; **Rabin-Karp** hash tabanlı yaklaşımıyla çoklu desen ve kayan
pencere problemlerini nasıl çözer; **trie** ön ek (prefix) tabanlı sözlük
yapılarını nasıl mümkün kılar; ve **suffix yapıları** (suffix array, suffix
tree, suffix automaton) tek bir metin üzerinde sınırsız sorguyu nasıl önceden
işleyerek (preprocessing) hızlandırır.

Önce ortak düşmanı tanıyalım: naive (kaba kuvvet) desen arama.

## Kaba Kuvvet Arama ve Neden Yetersiz Kaldığı

Uzunluğu `n` olan bir metin `T` içinde uzunluğu `m` olan bir desen `P` arayalım.
En saf yaklaşım, metnin her `i` konumuna deseni hizalayıp karakter karakter
karşılaştırmaktır. Uyuşmazlık (mismatch) olunca `i`'yi bir artırıp baştan
başlarız.

Bu yaklaşımın en kötü durumu (worst case) `O(n * m)`'dir. Bunu neden yaşarız?
Çünkü bir uyuşmazlıkta, o ana kadar başarıyla eşleştirdiğimiz karakterlerin
verdiği bilgiyi **çöpe atarız**. `T = "AAAAAAAAAB"`, `P = "AAAAB"` örneğinde her
hizalamada 4 `A`'yı boşuna eşleştirir, `B`'de patlar, sonra deseni bir kaydırıp
aynı işi baştan yaparız. Zaten eşleştirdiğimiz `A`'ların desenin kendi
içindeki tekrarı hakkında bize bilgi verdiğini fark edemeyiz.

İşte KMP'nin çözdüğü kök problem tam olarak budur: **desenin kendi iç
yapısını önceden analiz ederek, bir uyuşmazlıkta metinde asla geri gitmemek.**

## KMP (Knuth-Morris-Pratt)

### Tanım

KMP, tek bir deseni `O(n + m)` zamanda garantili bulan bir algoritmadır. İki
aşaması vardır: desenin **failure function** (başarısızlık fonksiyonu, LPS
tablosu olarak da anılır) ön işlemesi ve ardından metin üzerinde tek geçişli
tarama.

### Kök Neden: Neden Metinde Geri Gitmeye Gerek Yok

Anahtar gözlem şudur: bir uyuşmazlık, `T` üzerinde `j` konumunda oldu ve o ana
kadar desenin ilk `k` karakteri eşleşmişti. Bu, `T`'nin bize gösterdiği son `k`
karakterin **tam olarak** desenin ilk `k` karakteri olduğu anlamına gelir.
Dolayısıyla bu `k` karakterlik parçayı zaten "biliyoruz" ‒ tekrar okumaya
gerek yok.

Şimdi soru şu: deseni ne kadar kaydırabiliriz? Deseni öyle bir noktaya
kaydırmalıyız ki, desenin yeni başlangıcı, `T`'de zaten okuduğumuz son
karakterlerle çakışsın. Bunun mümkün olduğu tek durum, desenin bir **proper
prefix**'inin (kendisinden kısa bir ön ekinin) aynı zamanda bir **suffix**
(son ek) olmasıdır. İşte LPS tablosu her `i` için "ilk `i` karakterin en uzun
proper prefix'i olup aynı zamanda suffix'i olan parçanın uzunluğu"nu tutar.

Örnek: `P = "ABABAC"`. `"ABABA"` ön ekinin en uzun prefix-suffix çakışması
`"ABA"`dır (uzunluk 3). Yani `"ABABA"`ya kadar eşleşip `C` yerine başka bir
karakter görürsek, deseni sıfıra çekmek yerine 3 karaktere çekeriz; çünkü son
gördüğümüz `"ABA"` zaten desenin başındaki `"ABA"` ile aynıdır.

### Failure Function Nasıl Hesaplanır

LPS tablosu, desenin kendisini kendisine karşı KMP'lemesiyle `O(m)` zamanda
kurulur. Kavramsal akış: iki işaretçi tutulur; biri şu ana kadarki en uzun
prefix-suffix uzunluğunu (`len`), diğeri tabloyu doldurduğumuz konumu (`i`)
gösterir. `P[i] == P[len]` ise çakışma bir uzar. Uyuşmazlıkta `len`'i,
`len`'den bir önceki LPS değerine çekeriz ‒ ki bu, aynı algoritmanın kendi
üzerinde özyinelemeli uygulanışıdır.

```python
def lps_hesapla(desen):
    m = len(desen)
    lps = [0] * m
    uzunluk = 0        # o anki en uzun prefix-suffix
    i = 1
    while i < m:
        if desen[i] == desen[uzunluk]:
            uzunluk += 1
            lps[i] = uzunluk
            i += 1
        elif uzunluk != 0:
            uzunluk = lps[uzunluk - 1]   # geri gitmek yerine kısa devre
        else:
            lps[i] = 0
            i += 1
    return lps

def kmp_ara(metin, desen):
    lps = lps_hesapla(desen)
    sonuclar = []
    i = j = 0          # i: metin, j: desen
    while i < len(metin):
        if metin[i] == desen[j]:
            i += 1; j += 1
            if j == len(desen):
                sonuclar.append(i - j)   # eslesme bulundu
                j = lps[j - 1]           # sonrakini aramaya devam
        elif j != 0:
            j = lps[j - 1]               # metinde i GERI GITMEZ
        else:
            i += 1
    return sonuclar
```

Kritik satır `j = lps[j - 1]`'dir. `i` asla azalmaz; metin tek yönde ilerler.
Toplam iş `O(n)` tarama artı `O(m)` ön işleme = `O(n + m)`.

### Doğru Kullanım ve Tuzaklar

- KMP, **tek desen** ve karşılaştırma tabanlı senaryolar için idealdir;
  sözlük gibi çok sayıda desen için değil (onun için Aho-Corasick trie'si
  vardır).
- LPS'in "proper prefix" olması şarttır; desenin kendisi bir prefix-suffix
  olarak sayılırsa (yani `len == i`) sonsuz döngü ya da yanlış sonuç doğar.
- Pratikte, çoğu gerçek metinde naive arama beklenen ortalamada zaten hızlıdır;
  KMP'nin asıl değeri **worst-case garantisidir** ‒ örneğin saldırgan tarafından
  kontrol edilen girdilerde (ReDoS benzeri senaryolar) tahmin edilebilir
  performans gerektiğinde.

## Rabin-Karp

### Tanım

Rabin-Karp, desen ve metin pencerelerini birer sayıya (**hash**) dönüştürüp
önce hash'leri karşılaştıran bir algoritmadır. Fikir şu: iki string eşitse
hash'leri de eşittir; hash'ler farklıysa string'ler kesinlikle farklıdır.
Yani ucuz bir sayı karşılaştırmasıyla çoğu hizalamayı eleyebiliriz.

### Kök Neden: Rolling Hash ve Neden Sabit Zaman Günceller

Her pencere için hash'i baştan hesaplasak `O(m)` sürer, hiçbir kazancımız olmaz.
Rabin-Karp'ın kalbi **rolling hash**'tir (kayan hash): pencere bir karakter
sağa kaydığında, çıkan karakterin katkısını çıkarıp giren karakterin katkısını
ekleyerek yeni hash'i `O(1)`'de üretiriz.

Bunu polinom hash ile kurarız. Metni bir sayı tabanı (`b`, tipik olarak 256
veya bir asal) ve büyük bir asal modül (`q`) ile şöyle kodlarız:

```
hash(T[i..i+m-1]) = (T[i]*b^(m-1) + T[i+1]*b^(m-2) + ... + T[i+m-1]) mod q
```

Pencere kayınca:

```
yeni = ( (eski - T[i]*b^(m-1)) * b + T[i+m] ) mod q
```

`b^(m-1) mod q` bir kez önceden hesaplanır. Böylece güncelleme sabit zamanlıdır.

### Neden Modül Asal ve Neden Doğrulama Şart

Modül `q`'nun büyük bir asal olması, hash dağılımını iyileştirir ve
**collision** (çakışma) olasılığını azaltır. Ama çakışma sıfırlanmaz: iki farklı
string aynı hash'e düşebilir. Bu yüzden hash eşleştiğinde **mutlaka** karakter
karakter doğrulama yapılır. Doğrulamayı atlayan bir Rabin-Karp uygulaması
sessizce yanlış pozitif üretir ‒ bu en yaygın hatalardan biridir.

```python
def rabin_karp(metin, desen, b=256, q=1_000_000_007):
    n, m = len(metin), len(desen)
    if m > n: return []
    yuksek = pow(b, m - 1, q)
    hd = ht = 0
    for k in range(m):                       # ilk pencere ve desen hash'i
        hd = (hd * b + ord(desen[k])) % q
        ht = (ht * b + ord(metin[k])) % q
    sonuclar = []
    for i in range(n - m + 1):
        if hd == ht and metin[i:i+m] == desen:   # DOGRULAMA sart
            sonuclar.append(i)
        if i < n - m:
            ht = ((ht - ord(metin[i]) * yuksek) * b + ord(metin[i+m])) % q
            ht %= q                            # negatif olmasin diye
    return sonuclar
```

### Ortalama ve Kötü Durum

Ortalama karmaşıklık `O(n + m)`'dir: iyi bir hash ile çakışma nadir olur ve
doğrulamalar seyrek tetiklenir. Ancak kötü durumda ‒ kötü seçilmiş modül veya
saldırgan tarafından tasarlanmış girdi ile her pencere çakışırsa ‒ her
hizalamada doğrulama tetiklenir ve `O(n * m)`'e döner. Güvenlik açısından önemli
sistemlerde, modül ve tabanı çalışma anında rastgele seçmek (randomized hashing)
saldırganın çakışma üretmesini zorlaştırır.

### Rabin-Karp'ın Asıl Parladığı Yer: Çoklu Desen

Rabin-Karp tek desende KMP'ye üstünlük sağlamaz; asıl gücü **çoklu desen**
aramadadır. `k` tane aynı uzunlukta deseni bir hash kümesine (set) koyarsak,
metin üzerinde tek geçişte hepsini `O(n + k)` beklenen zamanda ararız ‒ her
pencerede tek bir hash hesaplayıp set'te sorgularız. Ayrıca 2 boyutlu desen
arama (görüntü/matris eşleştirme) ve **Rabin fingerprinting** ile içerik tabanlı
parçalama (content-defined chunking; rsync, dedup sistemleri) bu tekniğe dayanır.

## Trie (Prefix Tree)

### Tanım

Trie, string kümesini karakter karakter dallanan bir ağaç olarak saklayan
veri yapısıdır. Kökten bir düğüme giden yol bir prefix'i temsil eder; ortak
ön ekleri paylaşan kelimeler aynı dalları paylaşır. "car", "card", "care"
kelimeleri `c-a-r` yolunu ortak kullanır, sonra ayrışır.

### Kök Neden: Neden Hash Tablosu Yetmiyor

Bir kelime kümesinde "bu kelime var mı?" sorusuna hash tablosu da `O(uzunluk)`
cevap verir. O halde trie neden var? Çünkü trie'nin çözdüğü asıl problem **prefix
sorgularıdır**: "şu ön ekle başlayan tüm kelimeler hangileri?" (otomatik
tamamlama), "şu ön ek herhangi bir kelimenin başı mı?" Hash tablosu bunu yapamaz,
çünkü anahtarları parçalamadan bütün olarak saklar. Trie ise ön ek bilgisini
yapısının içine gömer.

Ek olarak trie, ortak ön ekleri paylaştığı için bellek açısından çakışan
kelime kümelerinde tasarruf sağlayabilir ve sıralı gezinme (lexicographic
traversal) doğal olarak sıralı çıktı verir.

### Yapı ve Karmaşıklık

Her düğüm, alfabedeki her karakter için bir çocuk göstericisi ve "burada bir
kelime bitiyor mu?" bayrağı tutar. Ekleme, arama ve prefix sorgusu, alfabe
boyutundan bağımsız olarak **kelime uzunluğuyla orantılıdır** ‒ `n` kelime
sayısından bağımsız. Bu, çok büyük sözlüklerde kritik bir avantajdır.

```python
class TrieDugum:
    __slots__ = ("cocuklar", "kelime_sonu")
    def __init__(self):
        self.cocuklar = {}
        self.kelime_sonu = False

class Trie:
    def __init__(self):
        self.kok = TrieDugum()
    def ekle(self, kelime):
        d = self.kok
        for k in kelime:
            d = d.cocuklar.setdefault(k, TrieDugum())
        d.kelime_sonu = True
    def ara(self, kelime):
        d = self._yolu_izle(kelime)
        return d is not None and d.kelime_sonu
    def prefix_var_mi(self, onek):
        return self._yolu_izle(onek) is not None
    def _yolu_izle(self, s):
        d = self.kok
        for k in s:
            if k not in d.cocuklar: return None
            d = d.cocuklar[k]
        return d
```

### Tuzaklar ve Bellek

Trie'nin en büyük tuzağı **bellek maliyetidir**. Sabit dizili düğümler (örneğin
her düğümde 256 elemanlı dizi) çok sayıda boş göstericiyle belleği israf eder,
özellikle seyrek (sparse) alfabelerde. Çözümler:

- **Hash map tabanlı çocuklar** (yukarıdaki gibi): bellek dostudur ama gösterici
  takibi sebebiyle cache dostu değildir.
- **Radix tree / Patricia trie**: tek çocuklu zincirleri tek bir kenarda
  sıkıştırır. "test" için `t-e-s-t` yerine tek bir "test" kenarı. Bu, uzun ortak
  ön ekli kümelerde düğüm sayısını dramatik azaltır.
- **DAWG (Directed Acyclic Word Graph)**: ortak son ekleri de birleştirir,
  minimum otomat elde eder.

### Aho-Corasick: Trie + KMP

Çoklu desen aramanın altın standardı **Aho-Corasick**'tir. Tüm desenleri bir
trie'ye koyar, sonra KMP'nin failure function fikrini ağaca genelleştirerek
"failure link"ler ekler. Böylece metin üzerinde tek geçişte, tüm desenleri
`O(n + toplam_desen_uzunlugu + eslesme_sayisi)` zamanda bulur. Antivirüs imza
tarama, spam filtreleri ve içerik denetimi motorlarının çekirdeğidir.

## Suffix Yapıları

Şimdiye kadarki yapılar deseni ön işledi. Suffix yapıları tersini yapar:
**metni** ön işler. Metin sabit ve üzerine çok sayıda farklı sorgu gelecekse,
tüm son ekleri (suffix) bir kez indeksleyip her sorguyu çok hızlı cevaplarız.
"Bir metnin herhangi bir alt dizesi (substring), bir suffix'in prefix'idir"
gözlemi bu yapıların temelidir ‒ tüm substring'leri aramak, tüm suffix'lerin
prefix'lerini aramaya indirgenir.

### Suffix Array

En pratik ve bellek dostu yapıdır. Metnin tüm son eklerinin, alfabetik sıraya
göre başlangıç indekslerini tutan bir tam sayı dizisidir. `"banana"` için son
ekler sıralanınca dizi indeksleri elde edilir.

Neden işe yarar? Son ekler sıralı olduğu için, bir deseni **binary search** ile
`O(m log n)` zamanda ararız: desen, sıralı son eklerin oluşturduğu bir aralığa
(range) düşer ve o aralığın uzunluğu, desenin metinde kaç kez geçtiğini verir.

- **İnşa maliyeti**: Naif inşa (tüm son ekleri sırala) `O(n^2 log n)`'e kadar
  çıkabilir çünkü karşılaştırmalar uzun olabilir. Modern algoritmalarla `O(n)`
  veya `O(n log n)` inşa mümkündür (örneğin ikiye katlama / prefix-doubling
  yaklaşımı `O(n log n)` verir; doğrusal inşa algoritmaları da mevcuttur).
- **LCP dizisi (Longest Common Prefix)**: Suffix array'i, komşu son eklerin
  ortak ön ek uzunluklarını tutan LCP dizisiyle zenginleştirmek, arama ve
  "en uzun tekrar eden alt dize" gibi sorguları hızlandırır. Kasai'nin
  algoritması LCP'yi `O(n)` üretir.

Suffix array, düşük bellek kullanımı ve cache dostu erişimi sebebiyle
biyoinformatik ve arama motoru altyapılarında suffix tree'ye tercih edilir.

### Suffix Tree

Bir metnin tüm son eklerini içeren, kenarları sıkıştırılmış (Patricia) bir
trie'dir. Kavramsal olarak en güçlü suffix yapısıdır: birçok sorguyu doğrusal
veya sorgu uzunluğuyla orantılı sürede cevaplar (örneğin desen arama `O(m)`,
en uzun tekrar eden alt dize, en uzun ortak alt dize).

Kök gücü: her substring bir kök-düğüm yolunun ön eki olduğundan, ağaçta tek bir
iniş sorguyu çözer. Ukkonen'in algoritması suffix tree'yi `O(n)` zamanda
online (karakter karakter) inşa eder ‒ ancak uygulaması sabit faktörü yüksek ve
karmaşıktır. Suffix tree'nin pratikteki en büyük dezavantajı **bellek
maliyetidir**: düğüm başına birçok gösterici sebebiyle metin boyutunun katları
kadar RAM tüketebilir. Bu yüzden pratikte çoğu sistem suffix array + LCP
kombinasyonunu tercih eder; bu kombinasyon suffix tree'nin sağladığı sorguların
çoğunu daha az bellekle taklit edebilir.

### Suffix Automaton

Bir metnin tüm alt dizelerini tanıyan **minimum deterministik sonlu otomat**tır.
Boyutu metin uzunluğunda doğrusaldır (`O(n)` durum ve geçiş) ve online, doğrusal
zamanda inşa edilir. Güçlü olduğu sorgular: bir substring'in metinde olup
olmadığı `O(m)`, farklı alt dizelerin sayısı, en uzun ortak alt dize. Suffix
tree'ye kıyasla daha kompakt ve inşası bazı kişilerce daha anlaşılır bulunur;
substring'lerin **eşdeğerlik sınıflarını** (endpos setleri) birleştirmesi onu
zarif kılar.

### Suffix Yapıları Ne Zaman Kullanılır

Suffix yapılarının önişleme maliyeti yüksektir. Bu maliyet, aynı metin üzerinde
**çok sayıda sorgu** yapılacaksa amorti edilir. Metin sık değişiyorsa (dinamik),
her değişimde yeniden inşa pahalıdır; böyle durumlarda çevrimiçi (online)
algoritmalar veya farklı yapılar (örneğin FM-index gibi sıkıştırılmış indeksler)
düşünülmelidir. Tek seferlik bir arama için suffix yapısı kurmak, KMP veya
Rabin-Karp'a göre büyük bir israftır.

## Doğru Yaklaşımı Seçmek

- **Tek desen, tek arama, worst-case garanti gerekli**: KMP. Ön işleme küçük,
  tarama tek geçişli, geri dönüş yok.
- **Çoklu desen, aynı uzunlukta, olasılıksal hız**: Rabin-Karp hash set;
  **çoklu desen, farklı uzunluk, deterministik**: Aho-Corasick (trie + failure
  link).
- **Prefix sorguları, otomatik tamamlama, sözlük**: trie; bellek darsa radix
  tree / DAWG.
- **Sabit metin, çok sayıda substring sorgusu**: suffix array + LCP (pratik,
  bellek dostu) ya da suffix automaton; en zengin sorgu kümesi gerekiyorsa
  suffix tree ‒ belleği göze alabiliyorsanız.
- **Ortalama pratik metin, esneklik**: çoğu dilin standart kütüphanesindeki
  arama (genelde Boyer-Moore veya hibrit varyantları), gerçek dünya metinlerinde
  KMP'den bile hızlı olabilir çünkü **atlamalarla** (skip) çalışır; deseni
  sondan başa karşılaştırıp eşleşmeyen karakteri görünce büyük sıçramalar yapar.

## Yaygın Hatalar

- **Rabin-Karp'ta hash eşleşmesini doğrulamamak**: sessiz yanlış pozitif üretir.
  Hash bir filtredir, kanıt değildir.
- **Modüler aritmetikte negatif değer**: rolling hash güncellemesinde çıkarma
  sonrası mod almayı unutmak, dile bağlı olarak negatif hash ve yanlış
  karşılaştırma doğurur. Her adımda `((x % q) + q) % q` disiplini gerekir.
- **KMP LPS'inde proper prefix şartını ihlal etmek**: `len`'in `i`'ye eşit
  olmasına izin vermek yanlış kaydırma üretir.
- **Trie'yi sabit büyük dizili düğümlerle kurmak**: seyrek alfabede belleği
  patlatır; Unicode gibi geniş alfabelerde felakettir.
- **Suffix yapısını dinamik metinde kullanmak**: her güncellemede yeniden inşa,
  yapının tüm kazancını yer.
- **Karmaşıklıkta alfabe boyutunu unutmak**: birçok analizde alfabe boyutu `σ`
  sabit varsayılır; büyük alfabelerde (Unicode) çocuk arama maliyeti bunu
  bozabilir.

## En İyi Pratikler

- Önce **profil çıkarın**: gerçek girdinizde naive/kütüphane araması yeterliyse
  karmaşık bir yapı kurmayın. Karmaşıklık kanıtlanmış bir darboğaz için eklenir.
- **Worst-case'i düşünün, özellikle girdi güvenilmezse**: saldırgan kontrolündeki
  metinlerde hash tabanlı ve regex tabanlı çözümlerde randomizasyon ve zaman
  sınırı uygulayın.
- **Bellek/hız dengesini bilinçli seçin**: suffix tree'nin zarafeti çoğu zaman
  suffix array + LCP'nin pratikliğine yenilir; ölçün.
- **Doğrulamayı asla atlamayın**: olasılıksal yapılarda (Rabin-Karp, bloom
  filtresi vb.) hash'i her zaman kesin karşılaştırma ile teyit edin.
- **Standart kütüphaneye güvenin**: dilinizin string arama, `re` motoru veya
  suffix array kütüphaneleri genelde iyi optimize edilmiştir; kendi versiyonunuzu
  yazmadan önce oradaki garantileri okuyun.

## Kapanış

String algoritmalarının ortak dersi tek cümlede toplanır: **daha önce
yaptığınız işi tekrar yapmayın.** KMP bunu desenin iç yapısını hatırlayarak,
Rabin-Karp kayan bir hash ile pencere hesabını yeniden kullanarak, trie ortak
ön ekleri paylaşarak, suffix yapıları ise metni bir kez ön işleyip tüm sorgulara
hizmet ederek yapar. Doğru yapıyı seçmek; girdinin boyutuna, sorgu sayısına,
metnin değişkenliğine, bellek bütçesine ve girdinin güvenilirliğine bağlı bir
mühendislik kararıdır. Bu boyutları netleştirmeden algoritma seçmek, çözümün
kendisini bir soruna dönüştürür.
