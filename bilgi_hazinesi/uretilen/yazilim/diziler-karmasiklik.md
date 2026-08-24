# Diziler, Listeler ve Karmaşıklık

Bilgisayar biliminin en temel veri yapısı dizidir (array). Neredeyse her üst düzey veri yapısının altında bir yerde bir dizi yatar: hash tabloları, yığınlar (stack), kuyruklar (queue), dinamik listeler, hatta çoğu dilin `string` tipi. Bu makale, dizilerin neden bu kadar merkezi olduğunu, dinamik dizilerin (dynamic array) nasıl çalıştığını, amortized (itfa edilmiş) analiz mantığını, cache dostu erişimin donanım seviyesindeki kök nedenini ve tüm bunların Big-O ile nasıl ifade edildiğini derinlemesine ele alır.

## Dizi Nedir ve Neden Böyle Tasarlanmıştır

Bir dizi, bellekte **bitişik (contiguous)** olarak yerleşmiş, aynı tipteki elemanlardan oluşan sabit boyutlu bir bloktur. "Bitişik" kelimesi burada süsleme değil, dizinin tüm gücünün kaynağıdır. Elemanlar art arda durduğu için, `i` indeksindeki elemanın adresi basit bir aritmetikle bulunur:

```
eleman_adresi = temel_adres + i * eleman_boyutu
```

Bu formül sabit sayıda işlemle sonuçlanır; dizinin uzunluğu ne olursa olsun değişmez. İşte bu yüzden diziye indeksle erişim **O(1)**, yani sabit zamanlıdır. Milyonuncu elemana erişmek de birinci elemana erişmek kadar hızlıdır. Bu özelliğe **random access** (rastgele erişim) denir ve dizinin en ayırt edici gücüdür.

### Kök neden: neden adres aritmetiği bu kadar önemli

Bir yapıda elemanları nerede bulacağını bilmek için ekstra bir arama yapmak zorunda kalıyorsanız, o yapı doğası gereği yavaştır. Bağlı liste (linked list) tam olarak bunu yapar: bir elemanı bulmak için baştan başlayıp işaretçileri (pointer) tek tek takip edersiniz. Dizide ise "bulmak" diye bir aşama yoktur; adres doğrudan hesaplanır. Bu, dizinin felsefesidir: **konumu hesapla, arama.**

Bunun bedeli, dizinin katı olmasıdır. Boyutu baştan belirlenir ve bellekte tek parça yer kaplaması gerektiği için, ortasına bir eleman eklemek istediğinizde arkadaki tüm elemanları kaydırmanız gerekir. Bu da **O(n)** maliyet demektir. Dizi, okuma için harika, yapısal değişiklik için pahalıdır. Bu asimetriyi kavramak, doğru veri yapısını seçmenin özüdür.

## Sabit Dizi ile Dinamik Dizi Ayrımı

Klasik dizi sabit boyutludur. C dilindeki `int arr[100]` gibi bir tanım, tam 100 elemanlık yer ayırır ve büyüyemez. Ancak gerçek programlarda kaç eleman geleceğini çoğu zaman önceden bilemeyiz. İşte burada **dinamik dizi** devreye girer.

Dinamik dizi, kullanıcıya sınırsız büyüyebilen bir liste izlenimi verir ama arka planda hâlâ sabit boyutlu bir bellek bloğu kullanır. Python'daki `list`, Java'daki `ArrayList`, C++'taki `std::vector`, Go'daki `slice`, C#'taki `List<T>` hepsi dinamik dizidir. Çalışma mantıkları şudur:

1. Belli bir kapasitede (capacity) bir bellek bloğu ayrılır. Kapasite, o an tutulan eleman sayısından (size) genellikle daha büyüktür.
2. Eleman eklendikçe `size` artar. `size < capacity` olduğu sürece ekleme yalnızca bir slota yazma işlemidir: **O(1)**.
3. `size == capacity` olduğunda blok dolmuştur. Bu noktada daha büyük yeni bir blok ayrılır, eski elemanlar oraya kopyalanır ve eski blok serbest bırakılır. Bu tek adım **O(n)**'dir çünkü tüm elemanlar taşınır.

Kritik nokta 3. adımdaki büyütme oranıdır. Blok dolduğunda kapasite **sabit bir katsayıyla çarpılır** (tipik olarak 2 kat, bazı gerçekleştirimlerde 1.5 kat). Kapasiteye sabit bir miktar (örneğin +1 veya +10) eklemek değil, **oransal** büyütmek. Bu ayrım her şeyi belirler ve amortized analizin kalbindedir.

## Amortized Analiz: Neden Ekleme "O(1)" Sayılır

Yeni başlayan bir mühendis şu itirazı yapar: "Ekleme bazen tüm diziyi kopyalıyorsa nasıl O(1) olabilir? Bazen O(n) oluyor!" Bu itiraz haklı görünür ama bir noktayı kaçırır: o pahalı kopyalama işlemi **çok seyrek** gerçekleşir. Amortized analiz, tek tek en kötü durumlara değil, **bir dizi işlemin toplam maliyetinin işlem sayısına bölümüne** bakar.

### Kök neden: neden oransal büyütme dengeyi kurtarır

Kapasiteyi her seferinde 2 katına çıkardığımızı düşünelim. Diziye sıfırdan başlayıp `n` eleman eklediğimizde kopyalama işlemleri şu kapasitelerde olur: 1, 2, 4, 8, 16, ... `n`'e kadar. Bu büyütmelerde toplam kopyalanan eleman sayısı:

```
1 + 2 + 4 + 8 + ... + n  ≈  2n
```

Bu bir geometrik seridir ve toplamı yaklaşık `2n`'e yakınsar; asla `n`'in katı bir çarpanla patlamaz. Yani `n` ekleme yaparken toplam kopyalama maliyeti `2n` civarındadır. Bunu `n` işleme böldüğümüzde işlem başına düşen maliyet sabit bir sayıya, yaklaşık 3'e (kendi yazma + itfa edilen kopyalama payı) iner. İşte bu yüzden ekleme işleminin **amortized O(1)** olduğunu söyleriz.

Eğer kapasiteyi sabit miktarla, mesela her seferinde +1 büyütseydik, her ekleme kopyalama tetiklerdi. `n` eleman için toplam kopyalama `1 + 2 + 3 + ... + n ≈ n²/2` olurdu. Bu da işlem başına O(n), toplamda O(n²) demektir; felaket bir performans. Oransal büyütmenin dahiyane yanı budur: **pahalı işlemleri üstel olarak seyrekleştirir, böylece maliyetleri ucuz işlemler arasına yayarak itfa eder.**

### Muhasebe yöntemiyle sezgi

Amortized analizi anlamanın güzel bir yolu "muhasebe (accounting) yöntemi"dir. Her ucuz eklemede aslında birkaç birim "fazladan ödeme" yaparız ve bu fazlalığı bir kenara biriktiririz. Kopyalama zamanı geldiğinde, biriktirdiğimiz bu krediyle kopyalama maliyetini karşılarız. Ortalama, her işlem sabit bir ücret ödemiş gibi çıkar. Amortized O(1), "her işlem hızlıdır" demek değildir; "uzun vadede işlem başına maliyet sabittir, tek tek bazı işlemler yavaş olsa da" demektir.

Bu ayrımın pratik bir sonucu vardır: **latency (gecikme) hassas sistemlerde** amortized O(1) yetmeyebilir. Bir oyun döngüsünde veya gerçek zamanlı bir sistemde, aniden diziyi kopyalayan o tek O(n) işlemi bir kare atlamasına (frame drop) yol açabilir. Bu durumlarda kapasiteyi baştan `reserve` ile ayırmak veya sabit gecikmeli veri yapıları tercih etmek gerekir.

## Cache Dostu Olmak: Donanımın Gizli Kuralı

Big-O analizi tüm bellek erişimlerini eşit maliyetli varsayar. Gerçek donanım böyle çalışmaz. Modern bir CPU, ana bellekten (RAM) bir veriyi okumak için yüzlerce çevrim (cycle) bekleyebilirken, cache'te (önbellek) duran bir veriye birkaç çevrimde ulaşır. Bu fark 100 kata varabilir. İşte bu yüzden aynı Big-O sınıfındaki iki algoritma pratikte 10 kat farklı hız verebilir; fark, **cache davranışındadır.**

### Kök neden: cache line ve spatial locality

CPU belleği tek tek byte'lar hâlinde değil, **cache line** denen bloklar hâlinde okur (yaygın olarak 64 byte). Bir elemanı istediğinizde donanım o elemanın etrafındaki komşu byte'ları da cache'e getirir; çünkü programların büyük olasılıkla yakındaki verilere de erişeceğini varsayar. Buna **spatial locality** (uzamsal yerellik) denir.

Dizi bu prensiple mükemmel uyum içindedir. Elemanlar bellekte bitişik durduğu için, diziyi baştan sona dolaştığınızda her cache line getirişi birden çok elemanı önceden yükler. İşlemcinin **prefetcher** birimi bu düzenli, sıralı erişim desenini tanır ve bir sonraki cache line'ı siz istemeden getirir. Sonuç: dizi üzerinde döngü kurmak donanımın en sevdiği erişim desenidir.

Bağlı liste ise tam tersidir. Her düğüm (node) bellekte rastgele bir yerde durabilir; işaretçiyi takip etmek "cache miss" (önbellek ıskası) yağmuruna yol açar. Her adımda CPU beklemek zorunda kalır. Bu yüzden modern donanımda, ortadan sık ekleme/silme yapmadığınız sürece, dizi tabanlı yapılar bağlı listeyi neredeyse her senaryoda ezer; teorik Big-O'ları benzer görünse bile.

### Somut örnek: satır-öncelikli vs sütun-öncelikli gezinme

İki boyutlu bir matrisi tek boyutlu bir dizide row-major (satır-öncelikli) düzende sakladığınızı düşünün; yani bir satırın elemanları bellekte art arda durur. Bu matrisi satır satır gezerseniz erişim bellekte sıralı olur ve cache dostudur. Ama aynı matrisi sütun sütun gezerseniz, her adımda bir satır uzunluğu kadar bellekte sıçrarsınız. Büyük matrislerde bu, aynı sayıda işlem yapmanıza rağmen program hızını kat kat düşürür. Big-O aynı O(n²) kalır, ama duvar saati (wall-clock) süresi bambaşkadır. Bu, "aynı karmaşıklık, farklı gerçek performans" olgusunun en öğretici örneğidir.

## Big-O: Karmaşıklığın Ortak Dili

Big-O gösterimi, bir algoritmanın kaynak kullanımının **girdi boyutu büyüdükçe nasıl ölçeklendiğini** ifade eder. Sabit çarpanları ve düşük dereceli terimleri kasıtlı olarak eler; çünkü amaç mikro-optimizasyon değil, **ölçekleme davranışını** yakalamaktır. `3n + 50` de `1000000n` de O(n)'dir, çünkü ikisi de girdi iki katına çıktığında yaklaşık iki katına çıkar.

Bu soyutlama hem güçlü hem tuzaklıdır. Güçlüdür çünkü donanımdan, dilden ve derleyiciden bağımsız bir karşılaştırma dili verir. Tuzaklıdır çünkü sabit çarpanları görmezden gelir; oysa yukarıda gördüğümüz gibi cache etkileri o sabit çarpanlarda saklıdır. Bu yüzden Big-O gerekli ama yeterli değildir; "hangi sınıf" sorusunu Big-O ile, "aynı sınıfta hangisi hızlı" sorusunu ölçümle cevaplarsınız.

### Dizi ve dinamik dizi için karmaşıklık tablosu

| İşlem | Dizi / Dinamik Dizi | Bağlı Liste |
|---|---|---|
| İndeksle erişim (`a[i]`) | O(1) | O(n) |
| Sona ekleme | Amortized O(1) | O(1) (kuyruğu tutuyorsa) |
| Başa/ortaya ekleme | O(n) | O(1) (düğüm elimizdeyse) |
| Ortadan silme | O(n) | O(1) (düğüm elimizdeyse) |
| Değere göre arama | O(n) | O(n) |
| Bellek yerleşimi (locality) | Mükemmel | Zayıf |

Bu tablonun asıl dersi tek tek satırlar değil, **desenidir**: dizi erişim ve sona ekleme için üstündür, yapısal değişiklik için zayıftır; bağlı liste tam tersi teorik güç vaat eder ama cache cezası yüzünden pratikte çoğu zaman bu vaadi tutamaz. "Ortaya ekleme O(1)" avantajı ancak eklenecek düğümü zaten elinizde tutuyorsanız geçerlidir; onu bulmak için O(n) arama yaptıysanız avantaj buharlaşır.

### Amortize edilmiş, en kötü ve ortalama durum farkı

Üç kavram sık karıştırılır. **En kötü durum (worst case)** tek bir işlemin olabilecek en kötü maliyetidir; dinamik diziye eklemede bu O(n)'dir (kopyalama anı). **Amortized** bir işlem dizisinin ortalamasıdır; eklemede O(1)'dir. **Ortalama durum (average case)** ise girdinin olasılık dağılımına dayanan istatistiksel bir beklentidir; genellikle hash tabloları gibi yapılarda konuşulur. Bir mülakatta "dinamik diziye ekleme O(1) mi?" sorusuna doğru cevap: "**Amortized O(1)**, ama tek işlem worst-case O(n)." Bu ince ayrımı vermek, konuyu gerçekten anladığınızı gösterir.

## Doğru Kullanım ve Yaygın Tuzaklar

### Ortadan silme ve indeks kayması

Bir dizinin ortasından eleman silmek arkadaki her şeyi bir sola kaydırır: O(n). Sık ortadan silme yapan bir kodda bu, gizli bir O(n²) yaratır. Sıra önemli değilse **"swap-and-pop"** hilesi işe yarar: silinecek elemanı dizinin son elemanıyla yer değiştirir, sonra sonu atarsınız. Böylece silme O(1) olur ama sıralama bozulur. Sıra korunması gerekiyorsa ya kaydırmaya katlanır ya da farklı bir yapı seçersiniz.

Bir başka klasik hata, **bir diziyi döngüyle gezerken içinden eleman silmektir.** İleri giden indeks, silme sonrası kayan elemanları atlar veya sınır dışına taşar. Doğru yöntem ya sondan başa doğru gezmek, ya silinecekleri işaretleyip tek geçişte yeni bir diziye süzmek, ya da dilin güvenli silme iterator'ünü kullanmaktır.

### Yineleme sırasında büyümeye dikkat

Bazı dillerde, bir koleksiyonu gezerken ona eleman eklemek "concurrent modification" hatasına yol açar veya daha sinsi biçimde, büyütme sırasındaki yeniden ayırma (reallocation) yüzünden elinizdeki işaretçi/iterator **geçersizleşir (invalidation)**. C++'ta `std::vector`'e ekleme yaptığınızda kapasite aşılırsa, daha önce aldığınız tüm işaretçi ve iterator'ler geçersiz olur; bu, fark edilmesi zor bir "dangling pointer" kaynağıdır. Kural: büyüyebilecek bir dizinin iç belleğine tuttuğunuz ham işaretçilere, ekleme sonrasında güvenmeyin.

### Kapasiteyi önceden ayırmak

Kaç eleman ekleyeceğinizi yaklaşık biliyorsanız, kapasiteyi baştan `reserve`/`ensureCapacity` ile ayırın. Bu, döngü boyunca tekrar tekrar büyüme ve kopyalama maliyetini ortadan kaldırır; amortized O(1)'i gerçek, kesintisiz O(1)'e yaklaştırır ve latency ani sıçramalarını önler. Milyonlarca eleman ekleyen bir döngüde bu tek satır, ölçülebilir bir hızlanma sağlar.

### Bellek israfı ve küçülme

Dinamik dizi büyürken kapasiteyi ikiye katlar; bu, en kötü durumda tuttuğu belleğin yaklaşık yarısının boş olabileceği anlamına gelir. Çoğu senaryoda bu makul bir bedeldir. Ama çok sayıda dizi tutan bellek-kısıtlı sistemlerde, elemanları sildikten sonra fazla kapasiteyi geri vermek isteyebilirsiniz (`shrink_to_fit` benzeri işlemler). Dikkat: küçültme de bir kopyalama gerektirir, yani ucuz değildir; büyüyüp küçülen bir yük altında sürekli küçültmek "thrashing"e yol açar.

## Yaygın Hatalar ve Kavram Yanılgıları

**"Bağlı liste her zaman daha hızlı ekler."** Teorik olarak ortaya O(1) ekler ama pratikte o noktayı bulmak için gezinmesi ve her düğümün cache miss üretmesi bu avantajı çoğu zaman siler. Modern donanımda, aksini ölçmediyseniz, varsayılan tercihiniz dizi tabanlı yapı olmalıdır.

**"Amortized O(1), her ekleme hızlı demektir."** Değildir. Ortalama hızlıdır; ama arada bir gelen kopyalama işlemi tek başına O(n)'dir. Gerçek zamanlı sistemlerde bu tek sıçrama önemlidir.

**"Big-O daha düşük olan her zaman daha hızlıdır."** Küçük `n`'ler için sabit çarpanlar baskındır. O(n log n) bir algoritma, küçük girdilerde O(n²) bir algoritmadan yavaş olabilir; bu yüzden birçok pratik sıralama gerçekleştirimi küçük parçalar için insertion sort'a geçer. Big-O asimptotik, yani "sonsuza giderken" bir ifadedir.

**"İndekslemeye eşdeğer olduğu için `list` ve dizi aynı şeydir."** Python `list` bir dinamik dizidir ama Python'un `LinkedList` benzeri deque'i, C'nin ham dizisi, bir dilin immutable tuple'ı hepsi farklı maliyet profillerine sahiptir. İsimlere değil, altındaki bellek modeline bakın.

**Sınır kontrolünü unutmak.** Ham dizilerde (C gibi) sınır dışına yazmak **buffer overflow**'a, bellek bozulmasına ve güvenlik açıklarına yol açar. Yönetimli dillerde bu genellikle bir istisna fırlatır ama yine de mantık hatasıdır. Off-by-one hataları (döngüde `<=` yerine `<` veya tersi) bu ailenin en yaygın üyesidir.

## En İyi Pratikler

**Varsayılanınız dinamik dizi olsun.** Erişim ve sona ekleme baskınsa, cache dostu ve basit olan dinamik dizi çoğu iş yükü için en iyi seçimdir. Diğer yapılara ancak ölçülebilir bir gerekçeyle geçin.

**Erişim desenini veri yapısından önce düşünün.** "Çoğunlukla ne yapacağım?" sorusuna cevap verin: rastgele erişim mi, sona ekleme mi, başa/ortaya ekleme mi, sık silme mi, hep sıralı gezme mi? Baskın işlem, yapıyı seçer. Ortaya sık ekleme gerçekten gerekiyorsa deque, dengeli ağaç veya bağlı yapı düşünün; ama önce bunun gerçekten sık olduğunu doğrulayın.

**Boyutu tahmin edebiliyorsanız kapasite ayırın.** `reserve` tek satırlık ama en etkili optimizasyonlardan biridir; yeniden ayırmaları ve latency sıçramalarını yok eder.

**Bitişik bellekten faydalanın.** Veriyi sıralı işleyecekseniz, onu bellekte sıralı tutun. "Struct of Arrays" (SoA) düzeni, ilgili alanları ayrı dizilerde tutarak yalnızca ihtiyaç duyulan alanların cache'e girmesini sağlar; performans-kritik döngülerde "Array of Structs" (AoS) düzenine göre belirgin hızlanma verebilir.

**Big-O ile başlayın, ölçümle bitirin.** Big-O yanlış sınıftaki bir çözümü baştan eler; ama aynı sınıftaki adaylar arasında karar için gerçek donanımda profil çıkarın. Sabit çarpanlar, cache davranışı ve bellek düzeni ancak ölçümde görünür.

**Doğru kelimeleri kullanın.** Ekleme için "amortized O(1)", tek işlem için "worst-case O(n)" deyin. Bu kesinlik hem düşünceyi netleştirir hem de birlikte çalıştığınız insanlarla aynı dili konuşmanızı sağlar.

## Özet

Dizi, "konumu ara" yerine "konumu hesapla" ilkesi üzerine kuruludur; bu yüzden erişimi O(1)'dir ve bitişik bellek düzeni sayesinde donanımın cache mekanizmasıyla mükemmel uyum içindedir. Dinamik dizi, bu gücü koruyarak büyüme yeteneği ekler; oransal (2 kat) büyütme sayesinde ekleme amortized O(1) olur, çünkü pahalı kopyalamalar üstel olarak seyrekleşip maliyetleri ucuz işlemlere yayılır. Big-O bize ölçekleme sınıfını verir ama sabit çarpanları eler; gerçek performans farkı çoğu zaman o eleme yüzünden görünmez kalan cache davranışında saklıdır. Bu yüzden ustalık, üç katmanı birden görmekte yatar: doğru asimptotik sınıfı Big-O ile seçmek, doğru maliyet ifadesini (amortized/worst-case) ayırt etmek ve son kararı gerçek donanımdaki ölçümle vermek.
