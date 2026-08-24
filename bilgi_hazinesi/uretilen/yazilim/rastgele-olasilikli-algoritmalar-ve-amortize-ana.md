# Rastgele/Olasılıklı Algoritmalar ve Amortize Analiz

## Giriş ve Neden Önemli

Klasik algoritma analizi genellikle **worst-case** (en kötü durum) çalışma süresine odaklanır: "Bu algoritma, olası tüm girdiler içinde en kötüsünde ne kadar sürer?" Ancak pratikte iki güçlü fikir bu bakışı zenginleştirir:

1. **Rastgelelik (randomization):** Algoritmanın kendisi içine rastgele seçimler koyarak, kötü niyetli bir düşmanın (adversary) algoritmayı yavaşlatacak girdiyi *önceden* seçmesini imkânsız hale getirmek. Böylece garanti "girdiye" değil "beklenen değere" kayar.
2. **Amortize analiz (amortized analysis):** Tek tek pahalı görünen işlemlerin bir dizi (sequence) içinde ortalamasının aslında ucuz olduğunu göstermek. Tek bir işlem yavaş olabilir, ama işlem başına *ortalama* maliyet düşüktür.

Bu iki kavram; hash tablosu yeniden boyutlandırma (resizing), quicksort'un pratikteki hızı, akış (stream) üzerinde örnekleme ve **DoS-dirençli** (Denial-of-Service resistant) veri yapısı tasarımı gibi konuların temelinde yatar. Güvenlik açısından kritik olan nokta şudur: Deterministik bir veri yapısının worst-case davranışı, saldırgan tarafından *tetiklenebilir* bir zafiyettir. Rastgelelik, bu tetiklemeyi olasılıksal olarak engeller.

---

## 1. Rastgele Algoritma Sınıfları: Las Vegas ve Monte Carlo

Rastgele algoritmalar iki temel sınıfa ayrılır. Ayrım, "neyin rastgele olduğu" üzerinedir: sonuç mu, süre mi?

### Las Vegas algoritmaları

- **Tanım:** Sonuç **her zaman doğrudur**. Rastgele olan şey **çalışma süresidir**.
- **Örnek:** Randomized quicksort. Sonuç kesinlikle sıralı bir dizidir; ama pivot seçimlerinin şansına göre kimi çalıştırma hızlı, kimi yavaş olur. **Beklenen** süre O(n log n).
- **Garanti biçimi:** "Doğru cevabı garanti ederim, süreyi beklenen değerle söylerim."

### Monte Carlo algoritmaları

- **Tanım:** Çalışma süresi **sınırlıdır** (deterministik veya sıkı sınırlı), ama sonuç **belirli bir olasılıkla yanlış** olabilir.
- **Örnek:** Miller-Rabin asallık testi. Bir sayının asal olup olmadığını hızlıca söyler; "bileşik" (composite) dediğinde her zaman haklıdır, ama "muhtemelen asal" dediğinde küçük bir hata olasılığı vardır. Test tekrarlandıkça hata olasılığı üstel olarak (exponentially) düşer.
- **Alt türler:**
  - *One-sided error:* Hata sadece tek yönde olur (örn. sadece "yanlışlıkla asal der", asla "yanlışlıkla bileşik demez").
  - *Two-sided error:* Her iki yönde de hata olabilir.

### İkisi arasındaki ilişki

Bir Las Vegas algoritmasını, süreye bir üst sınır koyup "süre dolarsa rastgele bir cevap ver" diyerek Monte Carlo'ya çevirebilirsiniz. Ters yönde, bir Monte Carlo algoritmasının çıktısını *doğrulayabiliyorsanız* (verification cheap ise), yanlış çıktıda tekrar çalıştırarak Las Vegas'a çevirebilirsiniz. Bu dönüşüm, "cevabı üretmek zor, doğrulamak kolay" olan problemlerde çok kullanışlıdır.

**Sık yapılan hata:** İki sınıfı karıştırmak. "Beklenen O(n log n)" ile "yüksek olasılıkla doğru" tamamen farklı garantilerdir. Kriptografik veya güvenlik-kritik bir bağlamda Monte Carlo kullanıyorsanız, kabul edilebilir hata olasılığını (örn. 2⁻⁸⁰) açıkça belirlemeniz gerekir.

---

## 2. Randomized Quicksort

### Kök neden: Deterministik quicksort neden tehlikeli?

Standart quicksort'ta pivot'u sabit bir kuralla seçersiniz (örn. her zaman ilk eleman, veya son eleman). Bu deterministik seçim, bir zafiyet doğurur: Saldırgan, algoritmanın pivot seçim kuralını biliyorsa, her bölmede (partition) pivot'un en küçük veya en büyük eleman olmasını sağlayacak bir girdi **inşa edebilir**. Bu durumda her partition dizinin sadece bir elemanını ayırır, ağaç dengesizleşir ve süre **O(n²)** olur.

Bu, sadece teorik bir kaygı değildir: Dışarıdan gelen veriyi (kullanıcı girdisi, ağ paketleri) sıralayan bir serviste, saldırgan özenle hazırlanmış girdilerle CPU'yu tüketip **algorithmic complexity attack** (algoritmik karmaşıklık saldırısı) gerçekleştirebilir.

### Çalışma mantığı: Rastgele pivot

Randomized quicksort, pivot'u her adımda **düzgün rastgele (uniformly at random)** seçer. Artık girdi ne olursa olsun, pivot'un seçimi girdiden bağımsızdır. Saldırgan girdiyi kontrol etse bile pivot seçimini kontrol edemez.

**Beklenen çalışma süresi analizinin sezgisi:** İki elemanın karşılaştırılıp karşılaştırılmadığına bakılır. Sıralı sıradaki i'inci ve j'inci elemanların karşılaştırılma olasılığı 2/(j−i+1)'dir. Bu olasılıkların toplamı O(n log n) verir. Kilit nokta: Bu beklenti **girdiye bağlı değildir** — her girdi için beklenen süre aynıdır. Deterministik versiyonda "kötü girdi" vardı; randomize versiyonda "kötü rastgele seçim dizisi" vardır, ama bunun olasılığı astronomik olarak küçüktür.

### Doğru kullanım ve tuzaklar

- **Doğru:** Rastgeleliği gerçek bir kaynaktan (veya en azından girdiden bağımsız, tahmin edilemez bir PRNG'den) alın.
- **Tuzak — tahmin edilebilir RNG:** Eğer PRNG'nin tohumu (seed) sabit veya tahmin edilebilirse, saldırgan pivot dizisini yeniden üretebilir ve worst-case'i yine tetikler. Randomizasyonun güvenlik değeri, seed'in gizliliğine bağlıdır.
- **Tuzak — median-of-three yanılgısı:** "İlk, orta, son elemanın medyanını pivot al" tekniği *ortalama* girdilerde iyileştirme sağlar ama deterministiktir; özel hazırlanmış girdilerle hâlâ O(n²)'ye zorlanabilir. Gerçek rastgelelik veya introsort gibi hibrit yaklaşımlar gerekir.
- **Pratik savunma — introsort:** Birçok standart kütüphane (örn. C++ `std::sort` implementasyonlarının çoğu) recursion derinliğini izler; belirli bir derinliği (~2 log n) aşınca heapsort'a düşer. Böylece worst-case O(n log n)'e sabitlenir. Bu, "rastgeleliğe güvenmek yerine worst-case'i garantiye almak" yaklaşımıdır ve güvenlik açısından tercih edilebilir.

---

## 3. Reservoir Sampling

### Tanım ve problem

**Reservoir sampling**, boyutu önceden bilinmeyen veya belleğe sığmayan bir **akıştan (stream)**, tek geçişte (single pass) ve sabit bellekle, **k eleman** düzgün rastgele seçme problemini çözer. Klasik durum k=1'dir.

### Çalışma mantığı (Algorithm R, k=1)

1. İlk elemanı reservoir'a al.
2. i'inci eleman (i > 1) geldiğinde, 1/i olasılıkla reservoir'daki elemanı bununla değiştir.
3. Akış bitince reservoir'daki eleman, düzgün rastgele seçilmiş olur.

**Neden doğru çalışır?** n elemanlı akışta, herhangi bir j'inci elemanın hayatta kalma olasılığını hesaplayalım. j seçilir (1/j) ve sonraki her adımda değiştirilmez:
(1/j) × (1 − 1/(j+1)) × (1 − 1/(j+2)) × ... × (1 − 1/n)
Bu çarpım teleskopik olarak sadeleşir ve **1/n** verir. Yani her eleman eşit olasılıkla — akışın uzunluğunu asla bilmeden. Bu, matematiksel olarak zarif ve akışta pratik olarak vazgeçilmez bir sonuçtur.

### k > 1 durumu

İlk k elemanı doğrudan reservoir'a alın. i'inci eleman (i > k) için, k/i olasılıkla kabul edin; kabul edilirse reservoir'daki rastgele bir elemanla değiştirin. Daha büyük akışlar için **Algorithm L**, kaç eleman atlanacağını doğrudan hesaplayarak her elemanı tek tek işlemekten kaçınır ve önemli hız kazandırır.

### Doğru kullanım ve tuzaklar

- **Doğru kullanım:** Log akışlarından örnekleme, dağıtık sistemlerde sabit-bellekli örnekleme, A/B test trafiğinin bir kesitini yakalama.
- **Tuzak — bölünmüş akışları birleştirme:** İki ayrı reservoir'ı naif biçimde birleştirirseniz düzgünlük bozulur. Doğru birleştirme için her reservoir'ın gördüğü eleman sayısını (ağırlık) takip etmeniz gerekir.
- **Tuzak — ağırlıklı örnekleme:** Elemanların farklı ağırlıkları varsa temel Algorithm R yanlıştır; **weighted reservoir sampling** (örn. A-Res / Efraimidis-Spirakis yöntemi, her elemana rastgele bir anahtar atayıp en büyük k anahtarı tutma) gerekir.
- **Tuzak — RNG kalitesi:** Zayıf bir RNG, dağılımda gözle görülmez ama istatistiksel olarak tespit edilebilir sapmalar yaratır; örnekleme temelli kararlar (güvenlik izleme, fraud tespiti) için bu önemlidir.

---

## 4. Amortize Analiz

Amortize analiz, **bir işlem dizisinin toplam maliyetini** analiz edip işlem başına ortalamayı çıkarır. Kritik fark: Bu bir *olasılık* ortalaması değildir (rastgelelik yoktur), **worst-case dizinin** ortalamasıdır. Yani "şanslıysanız" değil, "her zaman" bu ortalamayı garanti eder.

Üç temel teknik vardır.

### 4.1 Aggregate (Toplam) Yöntemi

**Fikir:** n işlemin toplam worst-case maliyetini T(n) bulup, işlem başına T(n)/n dersin. Tüm işlemlere aynı amortize maliyeti atarsın.

**Örnek — binary sayaç (counter) artırma:** k-bitlik bir sayacı 0'dan başlayıp n kez artırın. Bir artırma en kötü durumda k bit çevirebilir (tüm 1'ler taşarken). Naif worst-case: O(k) işlem başına, toplam O(nk). Ama daha dikkatli bakın: 0. bit her artırmada çevrilir (n kez), 1. bit her iki artırmada bir (n/2 kez), 2. bit n/4 kez... Toplam bit çevirmesi n + n/2 + n/4 + ... < 2n. Yani **toplam O(n)**, işlem başına amortize **O(1)**.

### 4.2 Accounting (Muhasebe) Yöntemi

**Fikir:** Her işleme gerçek maliyetinden farklı bir "ücret" (charge) atarsın. Ucuz işlemler fazladan ücret öder, bu fazlalık "kredi" olarak veri yapısındaki nesnelerde biriktirilir. Pahalı işlemler bu birikmiş krediyi harcar. Kural: **Toplam biriken kredi asla negatif olmamalı** — aksi halde gelecekteki bir maliyeti "ödeyecek para" yok demektir ve amortize sınır geçersizdir.

**Örnek — dinamik dizi (dynamic array) ekleme:** Her `push` işlemine 3 birim ücret atayın: 1 birim elemanı yerleştirmek için, 2 birim gelecekteki kopyalama için kredi olarak. Dizi dolup ikiye katlanınca (doubling), taşınacak her eski elemanın taşınma maliyeti, o eleman eklenirken biriktirilmiş krediden ödenir. Kredi hiç negatife düşmez, dolayısıyla **push başına amortize O(1)**.

### 4.3 Potential (Potansiyel) Yöntemi

**Fikir:** Muhasebe yönteminin matematiksel olarak en güçlü ve genel biçimi. Veri yapısının durumuna bir **potansiyel fonksiyonu** Φ (phi) atarsın — sezgisel olarak "biriken toplam kredi" veya "gelecekteki pahalı işleri karşılayacak enerji". Bir işlemin **amortize maliyeti** şöyle tanımlanır:

    amortize maliyet = gerçek maliyet + (Φ_sonra − Φ_önce)

Yani ĉᵢ = cᵢ + ΔΦ. Φ ≥ 0 ve Φ_başlangıç = 0 seçilirse, n işlemin amortize maliyetlerinin toplamı, gerçek maliyetlerin toplamı için bir **üst sınırdır** (çünkü ara Φ terimleri teleskopik olarak sadeleşir ve geriye +Φ_son ≥ 0 kalır).

**Örnek — dinamik dizi:** Φ = 2 × (eleman sayısı) − (kapasite) tanımlayın. Taşma olmayan bir push'ta eleman sayısı 1 artar, Φ 2 artar; gerçek maliyet 1, amortize = 1 + 2 = 3 = O(1). Doubling anında gerçek maliyet O(n) olur ama Φ o anda büyük ölçüde düşer (kapasite iki katına çıkar), bu düşüş gerçek maliyeti tam olarak "yutar" ve amortize yine O(1) kalır.

**Neden potansiyel yöntemi tercih edilir?** Muhasebe yöntemi "krediyi hangi nesneye koyayım" diye sezgisel karar gerektirir; potansiyel yöntemi bunu tek bir fonksiyona indirger ve karmaşık veri yapılarında (splay tree, Fibonacci heap, union-find) kanıtları düzenli hale getirir.

### Amortize analizde yaygın hatalar

- **Amortize ≠ ortalama-durum (average-case):** Amortize, worst-case bir dizide her işlemin *paylaşılmış* maliyetidir; girdi dağılımı hakkında hiçbir varsayım yapmaz. Average-case ise girdi dağılımına dayanır. Bunları karıştırmak yaygın bir kavram hatasıdır.
- **Amortize ≠ tekil worst-case:** Amortize O(1), *tek* bir işlemin O(1) olduğunu **garanti etmez**. Dinamik dizide doubling anındaki tek push O(n)'dir. Gerçek-zamanlı (real-time) sistemlerde bu "latency spike" kabul edilemez olabilir; o zaman amortize değil, işlem başına worst-case sınır veren yapılar (örn. incremental resizing) gerekir.
- **Potansiyelin negatife düşmesi:** Φ < 0'a izin verirseniz kanıt çöker. Φ'nin daima ≥ Φ_başlangıç kalması şarttır.

---

## 5. Hash Tablosu Yeniden Boyutlandırma ve DoS-Dirençli Tasarım

Bu bölüm, önceki iki kavramın (amortize + rastgelelik) güvenlikte nasıl birleştiğini gösterir.

### Amortize tarafı: Rehashing

Bir hash tablosu dolunca (load factor eşiği aşılınca), daha büyük bir tabloya **rehash** edilir: tüm elemanlar yeniden hash'lenip taşınır. Tek bir insert bu yüzden O(n) olabilir. Ancak doubling stratejisiyle (kapasiteyi iki katına çıkarmak), tıpkı dinamik dizide olduğu gibi, **insert başına amortize O(1)** elde edilir. Aynı potansiyel/muhasebe analizi geçerlidir.

**Tuzak — büyütme faktörü:** Kapasiteyi sabit bir *miktar* (örn. +100) artırırsanız amortize O(1) **bozulur**, insert başına O(n)'e döner. Amortize O(1) için **çarpımsal** büyüme (×2, ×1.5) şarttır. Bu, "neden dizi/hash tabloları hep ikiye katlanır" sorusunun cevabıdır.

### Rastgelelik tarafı: Hash-flooding saldırısı ve savunma

**Kök neden — deterministik hash:** Hash tablosunun ortalama O(1) lookup garantisi, elemanların bucket'lara düzgün dağılması varsayımına dayanır. Eğer hash fonksiyonu **sabit ve herkesçe bilinen** bir fonksiyonsa (klasik `hashCode` gibi), saldırgan aynı bucket'a düşen (aynı hash değerini veren) **çok sayıda anahtar (collision) üretebilir**. O bucket bir bağlı listeye/uzun zincire dönüşür ve her lookup O(n) olur. Sonuç: **hash-flooding / hash-collision DoS** — az sayıda özenle seçilmiş girdiyle sunucunun CPU'sunu diz çöktürmek. Bu, 2000'lerin başından beri bilinen ve web framework'lerini (POST parametrelerini hash tablosuna koyanları) hedeflemiş gerçek bir saldırı sınıfıdır.

**Savunma — randomized/keyed hashing:**
- **Tanım:** Süreç başlangıcında gizli, rastgele bir **anahtar (seed)** üretilir ve hash fonksiyonu bu anahtarla parametrelenir (keyed hash). Saldırgan anahtarı bilmediği için, hangi girdilerin çakışacağını **önceden hesaplayamaz**.
- **SipHash:** Bu amaçla tasarlanmış, hızlı ve anahtarla parametreli bir **PRF** (pseudo-random function). Python (hash randomization, `PYTHONHASHSEED`), Rust (`HashMap`'in varsayılan hasher'ı), Ruby, Perl gibi diller hash-flooding'e karşı bunu benimsemiştir. Amaç kriptografik hash gücü değil, **girdiden bağımsız, tahmin edilemez dağılım** garantisidir — tam da randomized quicksort'taki mantığın aynısı.
- **Neden işe yarar:** Rastgelelik, worst-case'i "belirli bir girdinin özelliği" olmaktan çıkarır. Saldırgan artık deterministik olarak kötü girdi *inşa edemez*; en fazla şansa güvenir, o da olasılıksal olarak imkânsıza yakındır.

### Tespit ve savunma pratikleri

- **Tespit sinyalleri:** Beklenmedik CPU sıçramaları, tek bir bucket/zincirin anormal uzaması, hash tablosu lookup'larında latency dağılımının kuyruğunun (tail) şişmesi. Metriklerde bucket dağılımının çarpıklığını (skew) izlemek erken uyarı verir.
- **Savunma katmanları:**
  1. **Keyed/randomized hashing** (yukarıda) — birincil savunma.
  2. **Bucket içinde ağaç yapısı:** Bir bucket çok uzarsa (örn. Java HashMap'te belirli eşik sonrası) bağlı liste yerine dengeli ağaca geçmek, worst-case'i O(n) yerine O(log n)'e indirir. Bu, rastgeleliğe ek bir güvenlik ağıdır.
  3. **Girdi sınırlama:** Tek istekte kabul edilen parametre/anahtar sayısını sınırlamak, saldırı yüzeyini küçültür.
- **Tuzak — yanlış güven:** Randomized hashing kriptografik bütünlük *sağlamaz*; sadece collision-DoS'u zorlaştırır. Ayrıca seed süreç içinde sızarsa (örn. hata mesajlarıyla, timing side-channel ile) koruma zayıflar. Güvenlik, seed'in gizli kalmasına dayanır.

---

## 6. Kavramların Birleşimi: Ortak Tema

Bu makaledeki tüm konuları tek bir cümlede birleştiren fikir şudur: **Deterministik bir algoritmanın worst-case davranışı, saldırgan için bir kaldıraçtır; rastgelelik bu kaldıracı kırar, amortize analiz ise nadir pahalı işlemlerin toplam maliyetini dürüstçe hesaplar.**

- **Randomized quicksort** ve **randomized hashing**, aynı savunmanın iki yüzüdür: pivot/bucket seçimini girdiden bağımsız kılmak.
- **Reservoir sampling**, rastgeleliğin doğruluk (uniformity) *garantisi* için kullanıldığı bir örnektir — saldırı savunması değil, matematiksel bir kesinlik aracı.
- **Amortize analiz**, hem dinamik dizide hem hash rehashing'de "ara sıra pahalı ama ortalamada ucuz" davranışı *garantiye* bağlar; bu garanti olasılıksal değil, deterministik ve worst-case'tir.

### Tasarımcı için pratik özet

- Dış girdiyle beslenen veri yapılarında **her zaman** deterministik worst-case'in tetiklenebilir olduğunu varsayın; keyed/randomized yaklaşım veya worst-case-sıkı yapı (introsort, dengeli ağaç bucket) seçin.
- Rastgeleliğin güvenlik değeri **seed gizliliğine** bağlıdır; tahmin edilebilir RNG koruma sağlamaz.
- Amortize O(1) latency spike gizler; gerçek-zamanlı sistemlerde işlem-başına worst-case sınır isteyip istemediğinizi netleştirin.
- Monte Carlo mu Las Vegas mı kullandığınızı bilin ve kabul edilebilir hata olasılığını açıkça belgeleyin.
