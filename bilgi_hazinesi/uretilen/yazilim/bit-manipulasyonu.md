# Bit Manipülasyonu: Maskeleme, Bit Hileleri, Bitset ve Performans

## Giriş ve Tanım

Bit manipülasyonu, bir sayının ikili (binary) gösteriminde tek tek bitleri okumak, ayarlamak, temizlemek ve çevirmek için yapılan işlemlerin tümüdür. Modern bir işlemci, veriyi 8, 16, 32 veya 64 bitlik kelimeler (word) halinde tutar; bu bitlerin her biri fiziksel olarak bir bellek hücresindeki mantıksal 0 veya 1 durumudur. Bit manipülasyonu, bu en küçük bilgi birimine doğrudan erişerek, daha yüksek seviyeli soyutlamaların (örneğin bir boolean dizisi ya da bir set) getirdiği bellek ve hız maliyetinden kaçınmayı amaçlar.

Bu tekniği önemli kılan tek şey mikro-optimizasyon değildir. İşletim sistemi çekirdekleri, network protokolleri, dosya sistemleri, sıkıştırma algoritmaları, kriptografi, grafik motorları ve gömülü (embedded) sistemler, doğaları gereği bit seviyesinde konuşur. Bir TCP başlığındaki flag'ler, bir dosya izin maskesi (`rwxr-xr-x`), bir renk kanalının paketlenmesi ya da bir donanım register'ının kontrol bitleri hep bit manipülasyonuyla ele alınır. Dolayısıyla bu, "gösterişli bir numara" değil, sistem programcılığının temel dilidir.

## Kök Neden: Neden Bitlerle Uğraşırız?

Sorulması gereken ilk soru şu: elimizde `bool` tipi, dizi, `set` gibi rahat yapılar varken neden bitlere iniyoruz? Cevap üç eksende toplanır.

Birincisi **bellek yoğunluğu**. Çoğu dilde tek bir `bool` değeri, aslında bir bit bilgi taşımasına rağmen 1 byte (8 bit) yer kaplar; çünkü işlemci byte'tan daha küçük adreslenebilir birimle verimli çalışamaz. 64 boolean bayrağı ayrı ayrı tutarsanız 64 byte harcarsınız; oysa bunları tek bir 64 bitlik tamsayının bitlerine yerleştirirseniz 8 byte yeter. Sekiz kat kazanç. Milyonlarca nesne için bu, cache'e sığıp sığmama farkı demektir.

İkincisi **paralel işlem**. Bir işlemci `AND`, `OR`, `XOR` gibi bit operasyonlarını tek bir kelimenin 64 biti üzerinde aynı anda, tek çevrimde uygular. Yani bir bitset üzerinde 64 boolean'ı birden `AND`'lemek istiyorsanız, bunu bir tek makine komutuyla yaparsınız. Bu, veri düzeyinde paralellik (SIMD'in ilkel bir biçimi) sağlar ve `for` döngüsüyle tek tek gezmekten kat kat hızlıdır.

Üçüncüsü **donanım ve protokol uyumu**. Dış dünya bit konuşur. Bir donanım register'ının 3. biti bir motoru açıyorsa, siz o biti set etmek zorundasınız; başka soyutlama yoktur. Bir ikili dosya formatı alanları bit alanları (bit fields) halinde paketliyorsa, okumak için maskelemek gerekir.

Neden çalıştığının derin nedeni ise ikili sayı sisteminin kendisidir: her bit, 2'nin bir kuvvetini temsil eder. Bu yüzden 2'nin kuvvetleriyle ilgili her işlem (bölme, çarpma, mod alma, hizalama) kaydırma ve maskeleme ile "bedavaya" gelir. Örneğin `n & (n-1)` ifadesinin en düşük set biti temizlemesi bir tesadüf değil; ikili aritmetikte 1 çıkarmanın, en sağdaki 1'i 0 yapıp ondan sonraki tüm 0'ları 1'e çevirmesinin doğrudan sonucudur.

## Temel Operatörler ve Anlamları

Bit manipülasyonunun alfabesi altı operatörden oluşur. Her birinin "neden öyle davrandığını" bilmek, hile ezberlemekten çok daha kalıcıdır.

- **AND (`&`)**: İki bit de 1 ise sonuç 1. Bit *okumak* ve *temizlemek* için kullanılır, çünkü bir biti 0 ile AND'lerseniz her zaman 0, 1 ile AND'lerseniz kendisi kalır. Yani AND bir "filtre"dir.
- **OR (`|`)**: Bitlerden en az biri 1 ise 1. Bit *set etmek* (açmak) için kullanılır; 1 ile OR her zaman 1, 0 ile OR değeri korur.
- **XOR (`^`)**: Bitler farklıysa 1. Bit *çevirmek* (toggle) için kullanılır, çünkü 1 ile XOR biti tersine çevirir, 0 ile XOR korur. Ayrıca XOR'un kendisiyle sıfırlaması (`a ^ a == 0`) ve tersinir olması, birçok hilenin (takas, checksum, tek eleman bulma) temelidir.
- **NOT (`~`)**: Tüm bitleri tersine çevirir. İkiye tümleyen (two's complement) sistemde `~x == -x - 1` eşitliği buradan gelir.
- **Sol kaydırma (`<<`)**: Bitleri sola öteler, sağdan 0 doldurur. `x << k` matematiksel olarak `x * 2^k`'dir (taşma olmadığı sürece).
- **Sağ kaydırma (`>>`)**: Bitleri sağa öteler. Burada kritik bir ayrım var: **mantıksal (logical)** kaydırma soldan 0 doldururken, **aritmetik (arithmetic)** kaydırma işaret bitini korur. İşaretli tiplerde negatif sayıların bölünmesinin doğru çıkması için aritmetik kaydırma gerekir.

## Maskeleme: İşin Kalbi

Maskeleme, ilgilendiğiniz bitleri seçip gerisini görmezden gelmenin yöntemidir. Bir maske, hangi bitlerle ilgilendiğinizi 1'lerle işaretleyen bir bit desenidir. Dört temel işlem şöyle kurulur (burada `pos`, 0'dan başlayan bit konumudur):

```c
// Belirli bir biti SET etme (açma)
x |=  (1u << pos);

// Belirli bir biti TEMİZLEME (kapatma)
x &= ~(1u << pos);

// Belirli bir biti ÇEVİRME (toggle)
x ^=  (1u << pos);

// Belirli bir biti OKUMA (0 mı 1 mi?)
int bit = (x >> pos) & 1u;
```

Buradaki mantığı adım adım kavramak şart. `1u << pos` ifadesi, yalnızca `pos` konumunda 1 olan, gerisi 0 olan bir maske üretir. Bu maskeyi OR'larsak sadece o bit açılır, ötekilere dokunulmaz. Temizlemek için maskeyi tersine çeviririz (`~`): artık `pos` hariç her yer 1'dir; bununla AND'lersek `pos` biti 0'a zorlanır, diğerleri korunur. Toggle için XOR kullanılır çünkü XOR maskedeki 1'lerin denk geldiği bitleri çevirir. Okumak için ilgilendiğimiz biti en sağa kaydırıp `& 1` ile izole ederiz.

Çok bitlik alanlar için maske bir bit aralığını kapsar. Örneğin 32 bitlik bir kelimenin 8-15. bitlerini (bir byte'lık alanı) çekmek isterseniz:

```c
uint32_t alan = (x >> 8) & 0xFF;   // 8 bit sağa kaydır, alt 8 biti al
```

`0xFF` maskesi tam olarak 8 tane 1 bit demektir; yukarıdaki gürültüyü keser. Bir alanı *yazmak* ise iki adımlıdır: önce eski değeri temizle (clear), sonra yeniyi yerleştir (set):

```c
x = (x & ~(0xFFu << 8)) | ((yeni & 0xFF) << 8);
```

Bu "clear-then-set" kalıbı, gömülü sistemlerde donanım register'larına yazarken en sık yapılan iş ve en sık yapılan hataların da kaynağıdır. Temizlemeyi atlarsanız eski bitler yeniyle OR'lanır ve çöp değer oluşur.

## Klasik Bit Hileleri ve Neden Çalıştıkları

Bit hileleri, ezberlenecek büyülü formüller değildir; her biri ikili aritmetiğin bir sonucudur. Birkaç önemlisini nedenleriyle inceleyelim.

**En düşük set biti temizleme: `x & (x - 1)`.** Bir sayıdan 1 çıkarınca, en sağdaki 1 biti 0 olur ve ondan sağdaki tüm 0'lar 1'e döner. Örneğin `x = 10110000`, `x-1 = 10101111`. Bunları AND'lediğinizde ortak olmayan alt kısım silinir ve yalnızca `10100000` kalır; yani en düşük set bit gitti. Bu hile, bir sayıdaki set bitleri saymak için (Brian Kernighan yöntemi) döngüde kullanılır ve döngü, set bit sayısı kadar döner, 32 kez değil.

**En düşük set biti izole etme: `x & (-x)`.** İkiye tümleyende `-x == ~x + 1`'dir. Bu, en düşük set bitin altındaki her şeyi çevirip taşımayı sağlar; sonuçta yalnızca en düşük set bit hayatta kalır. Fenwick ağacı (binary indexed tree) gibi yapılar bu ifadeye dayanır.

**İkinin kuvveti mi? `x != 0 && (x & (x - 1)) == 0`.** İkinin kuvvetlerinin ikili gösteriminde tek bir 1 vardır. En düşük set biti temizlediğinizde 0 kalıyorsa, demek ki tek set bit vardı.

**XOR ile takas.** `a ^= b; b ^= a; a ^= b;` iki değişkeni geçici değişken olmadan takas eder. XOR'un tersinirliğinden çalışır. Ancak modern derleyicilerde geçici değişkenli takas genellikle daha hızlıdır ve `a` ile `b` aynı bellek adresini gösteriyorsa bu hile değeri sıfırlar. Yani zekice ama pratikte tuzaklı; öğretici değeri gerçek değerinden yüksektir.

**Tek başına kalan sayıyı bulma.** Bir dizide her eleman iki kez, biri bir kez geçiyorsa, hepsini XOR'larsanız çiftler birbirini götürür (`a ^ a == 0`), geriye tek eleman kalır. Bu, ekstra bellek kullanmadan çalışan zarif bir çözümdür.

**Popcount (set bit sayma).** Bir kelimede kaç bit 1 olduğunu saymak. Elle döngüyle yapılabilir ama modern işlemciler bunun için özel bir komuta sahiptir. C/C++'ta derleyici intrinsic'leri (örneğin GCC/Clang'de `__builtin_popcount`) bu donanım komutuna derlenir ve döngüden onlarca kat hızlıdır. Kendi popcount döngünüzü yazmak yerine, dilin/derleyicinin sağladığı yerleşik fonksiyonu tercih etmek neredeyse her zaman doğrudur.

## Bitset: Yoğun Boolean Kümesi

Bitset, çok sayıda boolean değeri paketleyerek tutan bir veri yapısıdır. N elemanlı bir küme için N bit ayrılır; her bit bir elemanın "var/yok" ya da "açık/kapalı" durumunu tutar. C++'ta derleme zamanında boyutu bilinen kümeler için `std::bitset<N>`, çalışma zamanında değişen boyut için `std::vector<bool>` (ki bu aslında özel olarak bit-paketlenmiş bir uzmanlaşmadır) vardır. Java'da `java.util.BitSet`, Python'da yerleşik bir tip olmasa da tamsayıların sınırsız hassasiyeti sayesinde tamsayıyı bitset gibi kullanmak mümkündür.

Bitset'in gücü, küme operasyonlarını kelime kelime yürütebilmesinden gelir. İki bitset'in kesişimi (`AND`), birleşimi (`OR`), farkı (`AND NOT`) ve simetrik farkı (`XOR`), altta yatan tamsayı dizisinin karşılıklı kelimeleri üzerinde tek tek uygulanır. 64 bitlik bir platformda 640 elemanlı iki kümenin kesişimini almak yalnızca 10 kelime işlemi gerektirir; elemanları teker teker karşılaştırmaya kıyasla 64 kat az iş.

Bir bitset'in içinde belirli bir eleman için doğru kelimeyi ve bit konumunu bulmak şöyle yapılır (64 bitlik kelimelerle):

```c
size_t kelime = i / 64;   // veya i >> 6
size_t bit    = i % 64;   // veya i & 63
kume[kelime] |= (1ull << bit);
```

Burada `i / 64` yerine `i >> 6`, `i % 64` yerine `i & 63` yazmak aynı sonucu verir çünkü 64 ikinin kuvvetidir; bu, kaydırma/maskelemenin bölme/mod'dan daha ucuz olmasından yararlanan tipik bir örnektir. Yine de modern derleyiciler sabit ikinin kuvveti bölmelerini kendiliğinden bu forma çevirdiği için, okunabilirlik uğruna `/ 64` yazmak da savunulabilir.

Bitset'in gerçek dünyadaki en görünür kullanımı, veritabanı ve arama motorlarındaki **bitmap index**'lerdir. Milyonlarca kaydın belirli bir özelliğe sahip olup olmadığı bir bitmap'te tutulur; sorgular "bu koşulu ve şu koşulu sağlayanlar" biçiminde bitmap'lerin AND'lenmesiyle inanılmaz hızlı çözülür. Seyrek (sparse) veriler için sıkıştırılmış bitmap yapıları (örneğin Roaring Bitmap ailesi) hem belleği hem hızı korur.

## Doğru Kullanım ve Sık Düşülen Tuzaklar

Bit manipülasyonu güçlüdür ama dilin tanımsız/uygulamaya bağlı davranışlarına (undefined/implementation-defined behavior) çok yakın çalışır. En yaygın tuzaklar şunlardır.

**İşaretli tamsayılarla kaydırma.** İşaretli bir tamsayıda işaret bitine ya da ötesine kaydırma, birçok dilde tanımsız davranıştır. Örneğin C/C++'ta `1 << 31` işaretli 32 bit `int` üzerinde taşma sayılır ve derleyici bunu istismar edebilir. Doğrusu, maske sabitlerini işaretsiz yazmaktır: `1u << 31` ya da 64 bit için `1ull << 63`. Genel kural: bit manipülasyonu yapıyorsanız işaretsiz (unsigned) tipler kullanın; işaret biti işleri çabucak karıştırır.

**Kaydırma miktarının tip genişliğine eşit ya da fazla olması.** Bir 32 bitlik değeri 32 ya da daha fazla kaydırmak birçok dilde tanımsızdır; işlemciye göre 0 verebilir, hiç kaydırmayabilir ya da beklenmedik sonuç doğurabilir. Kaydırma miktarı her zaman `0 <= k < genişlik` aralığında olmalıdır. Değişken kaydırmalarda bunu açıkça kontrol edin.

**Operatör önceliği.** Bit operatörlerinin önceliği, karşılaştırma operatörlerinden düşüktür. Bu yüzden `if (x & MASK == 0)` beklediğiniz gibi çalışmaz; önce `MASK == 0` değerlendirilir. Doğrusu `if ((x & MASK) == 0)`'dır. Bu, C ailesinde en sinsi ve en sık rastlanan bit hatasıdır; parantez alışkanlığı hayat kurtarır.

**`1` yerine geniş tipte literal kullanmayı unutmak.** `1 << pos` ifadesinde `1`, `int` tipindedir. `pos` 40 ise ve hedefiniz 64 bitlik bir değerse, kaydırma önce 32 bitlik `int` üzerinde yapılır ve sonuç çöp olur. Doğrusu literali baştan geniş yazmaktır: `1ull << pos`.

**İşaretli sağ kaydırmanın taşınabilirlik sorunu.** Negatif işaretli sayıların sağa kaydırılmasında işaret bitinin korunup korunmayacağı bazı dillerde uygulamaya bağlıdır. Pratikte yaygın platformlar aritmetik kaydırma yapar ama buna bel bağlayan taşınabilir kod yazmak risklidir.

**Endianness karışıklığı.** Bir kelimenin bitlerini manipüle etmek endianness'tan (byte sıralaması) etkilenmez; bitlerin anlamı tanım gereği sabittir. Ancak çok baytlı veriyi belleğe/diske/network'e yazıp okurken byte sırası önem kazanır. "Bit sıralaması" ile "byte sıralaması"nı karıştırmak, özellikle protokol ayrıştırmada zor bulunan hatalara yol açar.

## Performans: Ne Zaman Kazanç, Ne Zaman Kayıp?

Bit manipülasyonunun performans avantajı gerçektir ama her yerde değil. En büyük kazanç, verinin cache'e sığmasından gelir. Modern işlemcilerde bellek erişimi, aritmetikten kat kat yavaştır; L1 cache erişimi birkaç çevrimken ana belleğe gitmek yüzlerce çevrim tutar. Bir bitset, aynı bilgiyi 8 kat daha az yerde tuttuğu için 8 kat fazla veri cache'e sığar; bu, tek tek bit operasyonlarının teorik hızından çok daha büyük bir kazanç sağlar. Yani asıl kahraman genellikle "hızlı komut" değil, "az bellek + iyi cache lokalitesi"dir.

Öte yandan tuzaklar da vardır. Birincisi, **erken optimizasyon**. Sıcak yol (hot path) olmayan bir yerde kodu bit hileleriyle şifreleyip okunmaz hale getirmek, kazanılan nanosaniyelere değmez. Derleyiciler zaten `x % 2`, `x / 8` gibi ifadeleri bit operasyonlarına kendileri çevirir; onların işini elle yapmaya çalışmak çoğu zaman gereksizdir.

İkincisi, **dallanma (branch) maliyeti**. Bit hilelerinin bir güzelliği, dalsız (branchless) kod yazabilmeleridir. Örneğin iki sayının maksimumunu koşul kullanmadan bit işlemleriyle hesaplamak, dal tahmininin (branch prediction) başarısız olduğu sıcak döngülerde işe yarayabilir. Ama modern işlemcilerin dal tahmini çok iyidir; tahmin edilebilir dallar neredeyse bedavadır. Dalsız kod yalnızca dalın gerçekten öngörülemez olduğu durumlarda kazandırır ve bunu ancak profil ölçümü söyler, sezgi değil.

Üçüncüsü, **taşınabilirlik ve derleyici bağımlılığı**. `__builtin_popcount` gibi intrinsic'ler harikadır ama derleyiciye özgüdür ve hedef işlemcide karşılığı olan komut yoksa yavaş bir yazılım karşılığına düşebilir. Popcount, leading/trailing zero sayma gibi işlemler için dilin standart kütüphanesinin taşınabilir karşılıkları (varsa) tercih edilmelidir.

Genel performans ilkesi nettir: önce ölç, sonra optimize et. Bit manipülasyonunu bir performans aracı olarak kullanacaksanız, bunu ancak bir profiler'ın işaret ettiği sıcak noktalarda, ölçülebilir kazanç gösterdiği yerde yapın. Aksi halde bit hileleri, faydadan çok bakım maliyeti getirir.

## Yaygın Hatalar Özeti

- Maskeyi parantezlemeyi unutmak: `x & M == 0` yerine `(x & M) == 0`.
- İşaretli tiple kaydırma yapıp taşma/tanımsız davranışa girmek; işaretsiz kullanmamak.
- `1 << pos`'te literalin genişliğini yükseltmemek (`1ull << pos` gerekirken `1 << pos`).
- Tip genişliğine eşit ya da fazla kaydırmak.
- Çok bitlik alan yazarken önce temizlemeyi (clear) atlayıp eski bitlerle OR yapmak.
- Bit sıralaması ile byte sıralamasını (endianness) karıştırmak.
- Okunabilirliği hiçe sayıp sıcak olmayan kodu şifrelemek; erken optimizasyon.
- Kendi popcount/kaydırma döngüsünü yazıp derleyici intrinsic'ini görmezden gelmek.

## En İyi Pratikler

Bit manipülasyonunu sağlam kullanmanın yolu, zekayı azaltıp niyeti artırmaktan geçer. Öncelikle **isimlendirin**: çıplak `0x1F` yerine `#define IZIN_MASKESI 0x1Fu` gibi anlamlı sabitler kullanın; hangi bitin ne olduğunu belgeleyen bir enum ya da sabit seti, kodu maskelerin arkasındaki gizemden kurtarır. İkincisi, **kapsülleyin**: bit set/clear/test işlemlerini küçük, satır içi (inline) yardımcı fonksiyonlar ya da makrolar arkasına alın; böylece parantez ve tip hatalarını tek yerde çözer, çağrı yerlerini temiz tutarsınız.

Üçüncüsü, **işaretsiz ve genişliği belirli tipler** kullanın: `uint32_t`, `uint64_t` gibi sabit genişlikli tipler, platformlar arası davranışı öngörülebilir kılar. Dördüncüsü, **dilin araçlarına güvenin**: popcount, sondaki/baştaki sıfır sayma gibi işlemler için yerleşik fonksiyonları ve intrinsic'leri tercih edin; kendi elle-optimize döngünüz neredeyse her zaman daha yavaş ve daha hatalıdır. Beşincisi, **test edin**: bit sınırlarında (0. bit, en yüksek bit, sıfır değeri, tamamı 1 değeri) özel test durumları yazın; bit hataları çoğunlukla kenar durumlarında ortaya çıkar.

Son olarak, **niyeti performansa tercih edin**: bir soyutlama (bitset sınıfı, bit alanı yapısı) yeterince hızlıysa, elle bit hilesine gerek yoktur. Bit manipülasyonu, gerçekten gerektiğinde başvurulacak keskin bir alet olmalı; her problemin varsayılan çözümü değil. Doğru yerde kullanıldığında bellek ve hızda dramatik kazanç sağlar; yanlış yerde ise okunmaz, taşınamaz ve hataya açık kod üretir. Ustalık, ikisi arasındaki farkı ölçüyle ayırt etmektir.
