# Sayı Teorisi ve Modüler Aritmetik Algoritmaları

## Giriş: Neden Bu Katman Önemli

RSA, Diffie-Hellman ve eliptik eğri kriptografisi (ECC) genellikle "büyük asal sayılar" ve "ayrık logaritma zorluğu" gibi üst seviye kavramlarla anlatılır. Ama bu protokolleri gerçekten anlamak, savunmak ve tespit edebilmek için bir seviye aşağı inmek gerekir: bu protokollerin çalıştığı **hesaplama makinesi**. Bu makine dört temel algoritmadan oluşur: hızlı modüler üs alma (fast modular exponentiation), genişletilmiş Öklid algoritması (extended Euclidean algorithm), Çin Kalan Teoremi (Chinese Remainder Theorem, CRT) ve olasılıksal asallık testleri (Miller-Rabin gibi).

Bu dört algoritma neden ayrı bir konu olarak ele alınmalı? Çünkü kriptografik protokollerin güvenlik açıkları çoğunlukla protokolün matematiksel tanımında değil, bu **alt katmanın implementasyonunda** ortaya çıkar. Bir mühendis RSA'nın "n = p*q" olduğunu bilebilir ama üs alma sırasında sabit olmayan zamanlı (non-constant-time) bir çarpma kullanırsa, timing side-channel ile özel anahtar sızabilir. Mod ters (modular inverse) hesaplaması yanlış yapılırsa CRT tabanlı imzalama bozuk çıktı üretebilir ve bu bazen anahtarın tamamen kurtarılmasına (Bellcore saldırısı ailesi) yol açabilir. Bu yazı, savunma ve tespit odaklı bir mühendis gözünden bu algoritmaların iç mekaniğini, doğru kullanım kalıplarını ve yaygın hataları ele alıyor.

## Modüler Aritmetiğin Temel Zemin

Modüler aritmetik, tam sayıları sabit bir `n` modülüne göre sınıflandırır: iki sayı `a` ve `b`, `a ≡ b (mod n)` ilişkisini sağlıyorsa aynı kalıntı sınıfındadır. Kriptografide `n` genellikle ya bir asal sayı `p` (Diffie-Hellman, ElGamal, eliptik eğri alan aritmetiği) ya da iki büyük asalın çarpımı `n = p*q` (RSA) olur. Bu seçim rastgele değildir: `n`'in yapısı, hangi cebirsel özelliklerin (tersinirlik, grup yapısı, CRT ayrıştırması) kullanılabilir olduğunu belirler.

Kalıntı sınıfları kümesi `Z/nZ` toplama ve çarpma altında bir halka (ring) oluşturur. Bir elemanın çarpımsal tersi (`a^-1`) var olması için `gcd(a, n) = 1` şartı gerekir; yani `a` ile `n` aralarında asal olmalı. `n` asal olduğunda `0` dışındaki her eleman tersinirdir ve `Z/nZ` bir cisim (field) olur — bu, Diffie-Hellman ve eliptik eğri kriptografisinin güvendiği yapıdır. `n` bileşik olduğunda (RSA'daki gibi) sadece `n` ile aralarında asal olan elemanlar tersinirdir; bu elemanların sayısı Euler'in totient fonksiyonu `φ(n)` ile verilir ve RSA'nın gizli anahtarının matematiksel temelini oluşturur.

## Hızlı Modüler Üs Alma (Fast Modular Exponentiation)

### Tanım ve Kök Neden

RSA şifreleme/deşifreleme ve imzalama, `c = m^e mod n` biçiminde işlemler gerektirir. `e` tipik olarak 65537 gibi küçük olabilir ama özel anahtar işlemlerinde üs 2048 bit uzunluğunda olabilir. Naif yaklaşım — `m`'yi kendisiyle `e` kere çarpmak — `e` büyüklüğünde adım gerektirir; 2048 bitlik bir üs için bu pratikte imkansızdır (evrenin yaşından uzun sürer).

Kök neden çözümü **kare-al-ve-çarp (square-and-multiply)** yöntemidir: üssü ikili tabanda yazıp, her bitte bir kareleme ve (bit 1 ise) bir çarpma yaparak logaritmik sayıda adımla sonuca ulaşırız. `e`'nin ikili gösterimi `b_k b_{k-1} ... b_1 b_0` ise:

```
sonuc = 1
taban = m mod n
for i from 0 to k:
    if b_i == 1:
        sonuc = (sonuc * taban) mod n
    taban = (taban * taban) mod n
return sonuc
```

Bu algoritma `O(log e)` çarpma-mod işlemi yapar; 2048 bitlik bir üs için yaklaşık 2048-3072 modüler çarpma anlamına gelir — bu, modern donanımda milisaniyeler sürer. Her adımda ara sonuçların `mod n` ile küçültülmesi kritik: bu sayede sayılar hiçbir zaman `n^2`'den büyük büyümez ve çarpma maliyeti sabit kalır.

### Doğru Kullanım ve Tuzaklar

**Sabit zamanlı (constant-time) implementasyon zorunludur.** Yukarıdaki naif algoritmada `if b_i == 1` dallanması, bitin değerine göre farklı kod yolu (çarpma var/yok) çalıştırır. Bu, CPU'nun dallanma tahmini (branch prediction), cache erişim düzeni veya basit zamanlama farkı üzerinden **side-channel** sızıntısına yol açar: saldırgan, işlem süresini veya güç tüketimini ölçerek üssün (yani özel anahtarın) bitlerini tek tek çıkarabilir. Bu saldırı sınıfı akademik literatürde iyi belgelenmiştir (Kocher'in orijinal timing attack çalışması bu alanın başlangıcıdır).

Savunma yaklaşımı **Montgomery ladder** veya "her zaman kareleme ve çarpma yap, sonucu bite göre seç" (constant-time select) desenidir:

```
r0 = 1; r1 = taban
for i from k downto 0:
    if b_i == 0:
        r1 = r0 * r1 mod n; r0 = r0 * r0 mod n
    else:
        r0 = r0 * r1 mod n; r1 = r1 * r1 mod n
```

Burada her iki dalda da aynı sayıda ve aynı türde işlem yapılır; hangi dalın "gerçek" olduğu veri bağımlı dallanmaya değil, veri bağımlı seçime dayanır (ideal olarak donanım seviyesinde sabit zamanlı koşullu taşıma / `cmov` ile). Üretim kütüphaneleri (OpenSSL, BoringSSL gibi) bu nedenle kendi büyük sayı aritmetiğini dikkatle sabit zamanlı tutmaya çalışır; sıfırdan böyle bir algoritma yazmak eğitim amaçlı değilse tavsiye edilmez.

**Yaygın hatalar:**
- Değişken zamanlı büyük sayı kütüphaneleri kullanmak (ör. genel amaçlı bignum kütüphaneleri, kriptografik kullanım için tasarlanmamış).
- Ara sonuçları mod almadan büyütmek (performans ve bazen taşma hatası).
- Küçük `e` (ör. 3) ile birlikte padding olmadan şifreleme yapmak — bu, üs almanın kendisiyle ilgili değil ama aynı katmanda sık görülen bir hata (Coppersmith saldırıları ailesine kapı açar).

### Tespit Açısı

Bir sistemde zamanlama tabanlı yan kanal riskini değerlendirirken bakılacak yer: kriptografik kütüphanenin özel anahtar işlemlerinde veri bağımlı dallanma veya veri bağımlı bellek erişimi olup olmadığı (statik analiz araçları ve "constant-time" doğrulama araçları — ör. dinamik bilgi akışı izleyen test çerçeveleri — bu amaçla kullanılır). Ayrıca ağ üzerinden yapılan TLS handshake'lerinde anormal derecede tutarlı zamanlama farkları, olası bir timing attack denemesinin göstergesi olabilir; savunma tarafında sabit zamanlı implementasyon + rastgele gecikme eklemek (ikincisi tek başına yeterli değildir, sadece saldırıyı zorlaştırır) yaygın pratiktir.

## Genişletilmiş Öklid Algoritması (Extended Euclidean Algorithm)

### Tanım ve Kök Neden

Klasik Öklid algoritması `gcd(a, b)`'yi bulur: `gcd(a, b) = gcd(b, a mod b)`, `b = 0` olana kadar tekrarlanır. **Genişletilmiş** versiyon aynı zamanda `a*x + b*y = gcd(a, b)` denklemini sağlayan `x, y` tam sayılarını da üretir (Bézout özdeşliği). Bu, mod ters hesaplamanın matematiksel temelidir: eğer `gcd(a, n) = 1` ise, `a*x + n*y = 1` denklemi `mod n` alındığında `a*x ≡ 1 (mod n)` verir — yani `x`, `a`'nın `mod n`'deki çarpımsal tersidir.

Neden bu algoritmaya ihtiyaç duyarız? RSA anahtar üretiminde özel üs `d`, `e*d ≡ 1 (mod φ(n))` denklemini sağlamalıdır; yani `d = e^-1 mod φ(n)`. Bu tersi hesaplamanın verimli yolu genişletilmiş Öklid'tir — `O(log min(a,b))` adımda sonuca ulaşır, oysa "deneme yanılma" ile ters aramak `φ(n)` büyüklüğünde arama anlamına gelir ve pratik değildir.

```
extended_gcd(a, b):
    if b == 0: return (a, 1, 0)
    (g, x1, y1) = extended_gcd(b, a mod b)
    x = y1
    y = x1 - (a // b) * y1
    return (g, x, y)
```

### Doğru Kullanım, Tuzaklar, En İyi Pratikler

**Mod ters için alternatif yol: Fermat'nın Küçük Teoremi.** `n` asal olduğunda, `a^-1 mod n = a^(n-2) mod n` şeklinde de hesaplanabilir (hızlı üs alma ile). Bu, genişletilmiş Öklid'e göre biraz daha yavaştır ama bazı ortamlarda (özellikle donanım hızlandırmalı üs alma birimi varsa) tercih edilebilir. Önemli sınırlama: bu yöntem sadece asal modülüs için geçerlidir; RSA'nın kendisinde (`mod n`, `n` bileşik) çalışmaz, ama `mod p` veya `mod q` gibi asal alt modüllerde (CRT bağlamında) işe yarar.

**Yaygın hata: gcd ≠ 1 durumunu kontrol etmemek.** Eğer `a` ile `n` aralarında asal değilse ters yoktur; genişletilmiş Öklid yine de bir `(g, x, y)` üçlüsü döndürür ama `g ≠ 1` ise `x` bir ters değildir. Üretim kodunda bu kontrolün atlanması sessiz ve tespit edilmesi zor hatalara yol açar — özellikle anahtar üretimi gibi nadiren tetiklenen ama kritik yollarda.

**Negatif kalıntı tuzağı.** Genişletilmiş Öklid'in ürettiği `x` negatif olabilir; sonucu `mod n` normalize ederken `((x % n) + n) % n` gibi bir düzeltme gerekir, çünkü birçok programlama dilinde `%` operatörü negatif sayılarla matematiksel modülüs yerine işaretli kalıntı döndürür (ör. C ve Java'da `-3 % 5 = -3`, matematiksel olarak beklenen `2`'dir). Bu, sinsi ve testlerde bazen fark edilmeyen bir hata kaynağıdır çünkü küçük pozitif girdilerle yazılan testler sorunu yakalamaz.

### Tespit Açısı

Anahtar üretim kodunu incelerken mod ters hesaplayan her yerde şu iki şeyin doğrulanmış olması aranır: (1) `gcd == 1` kontrolü, (2) sonucun normalize edilmiş (daima `[0, n)` aralığında) olması. Kod incelemesinde bu, birim testlerle de doğrulanabilir: negatif girdi veya `gcd != 1` durumu için özel test senaryosu olup olmadığı iyi bir gösterge.

## Çin Kalan Teoremi (Chinese Remainder Theorem, CRT)

### Tanım ve Kök Neden

CRT, aralarında asal modüllere göre verilen bir kalıntı sistemini tek bir birleşik çözüme dönüştürür: `x ≡ a1 (mod m1)`, `x ≡ a2 (mod m2)`, ... sistemi, `m1*m2*...` modülünde tek bir `x` çözümüne sahiptir (moduller ikişer ikişer aralarında asalsa). Kriptografide en önemli kullanım alanı RSA'nın **hızlandırılmış özel anahtar işlemi**dir: `n = p*q` olduğunda, `m^d mod n` işlemini doğrudan `n` (ör. 2048 bit) üzerinde yapmak yerine, işlemi `mod p` ve `mod q` (her biri ~1024 bit) üzerinde ayrı ayrı yapıp sonra CRT ile birleştirmek yaklaşık 4 kat hız kazandırır. Çünkü modüler üs almanın maliyeti bit uzunluğunun karesi (veya kübüyle) orantılıdır; iki yarı-boyutlu işlem tek bir tam-boyutlu işlemden çok daha ucuzdur.

CRT-RSA algoritması:
```
dp = d mod (p-1)
dq = d mod (q-1)
qinv = q^-1 mod p    (genişletilmiş Öklid ile)

m1 = c^dp mod p
m2 = c^dq mod q
h = qinv * (m1 - m2) mod p
m = m2 + h*q
```

### Kök Neden: Neden Hız/Güvenlik Ödünleşimi Var

CRT-RSA'nın performans kazancı bedelsiz değildir: implementasyon karmaşıklığı artar ve **fault attack (hata enjeksiyonu saldırısı)** yüzeyi açılır. Bu ailenin en bilinen örneği **Bellcore saldırısı**dır: eğer `m1` veya `m2` hesaplamalarından biri (donanım hatası, voltaj/clock glitch, kozmik ışın veya kasıtlı fiziksel müdahale ile) bozulursa, ortaya çıkan hatalı imza ile doğru imza karşılaştırılarak `p` veya `q` çarpanlarından biri cebirsel olarak geri çıkarılabilir (`gcd(hatalı_imza^e - mesaj, n)` hesaplaması çoğu zaman `p` veya `q`'yu doğrudan verir). Bu, "matematiksel olarak doğru ama fiziksel olarak kırılgan" bir algoritmanın klasik örneğidir.

### Doğru Kullanım ve En İyi Pratikler

**Savunma: imza doğrulama (verify-after-sign).** Özel anahtarla imza üretildikten sonra, aynı imza açık anahtarla anında doğrulanır; tutarsızlık varsa imza asla dışarı verilmez. Bu, ekstra bir üs alma maliyeti getirir ama hata enjeksiyonu saldırısını büyük ölçüde etkisizleştirir çünkü saldırganın ihtiyaç duyduğu "bozuk ama dışarı sızan imza" hiç üretilmez.

**Savunma: rastgeleleştirme (blinding).** RSA blinding, işlenen mesajı rastgele bir faktörle çarpıp işlemden sonra bu faktörü çıkararak hem timing hem bazı fault-attack türevlerini zorlaştırır. Üretim kütüphaneleri genellikle bunu varsayılan olarak uygular.

**Yaygın hata:** CRT parametrelerini (`dp, dq, qinv`) anahtar üretiminde önceden hesaplayıp saklamak performans için doğrudur, ama bu değerlerin de özel anahtar kadar hassas olduğunu unutmak. `dp` ve `dq` sızarsa, `p` ve `q` çarpanlarının kurtarılması genellikle mümkündür.

### Tespit Açısı

CRT-RSA kullanan bir sistemde imza-sonrası doğrulama adımının var olup olmadığı, fault-attack direncinin ilk göstergesidir. Donanım güvenlik modülü (HSM) veya akıllı kart gibi fiziksel saldırıya açık ortamlarda bu kontrolün atlanması ciddi bir bulgu olarak işaretlenmelidir.

## Asallık Testleri: Miller-Rabin

### Tanım ve Kök Neden

RSA anahtar üretimi, yüzlerce basamaklı rastgele bir sayının asal olup olmadığını belirlemeyi gerektirir. Kesin (deterministic) asallık testleri (ör. AKS algoritması) teorik olarak polinom zamanlıdır ama pratikte kriptografik boyutlarda çok yavaştır. Bunun yerine **olasılıksal** testler kullanılır: **Miller-Rabin**, en yaygın ve en iyi anlaşılan yöntemdir.

Kök mantık Fermat'nın Küçük Teoremi'nin bir genellemesine dayanır: `n` asal ise, `n-1 = 2^s * d` (d tek) yazıldığında, rastgele bir `a` tabanı için ya `a^d ≡ 1 (mod n)` ya da bir `r` (0 ≤ r < s) için `a^(2^r * d) ≡ -1 (mod n)` sağlanmalıdır. Bu koşulu sağlamayan bir `a` bulunursa, `n` **kesin olarak bileşiktir** (composite witness). Koşulu sağlayan bir `a`, `n`'in asal olduğuna dair güçlü bir kanıt sunar ama kesinlik vermez — çünkü bazı bileşik sayılar (**güçlü yalancı asallar / strong pseudoprime**) belirli tabanlar için de bu testi geçebilir.

### Neden Olasılıksaldır ve Nasıl Güvenilir Hale Getirilir

Her rastgele taban seçimiyle, eğer `n` gerçekten bileşikse, testin yanlışlıkla "asal" demesi olasılığı en fazla `1/4`'tür (matematiksel ispatı Miller-Rabin'in temel teoremidir). Bu nedenle test **bağımsız rastgele tabanlarla tekrarlanır**: `k` bağımsız tur sonunda hatalı pozitif olasılığı `4^-k`'ye düşer. Kriptografik anahtar üretiminde tipik olarak yüksek sayıda tur (ör. NIST FIPS 186 gibi standartlar belirli güvenlik seviyeleri için gereken tur sayısını tanımlar) kullanılarak hata olasılığı pratikte ihmal edilebilir seviyeye (ör. `2^-128` mertebesinde) çekilir. Bu sayı kaynağının kalitesi kritiktir: zayıf/öngörülebilir rastgelelik kullanan bir Miller-Rabin implementasyonu, testin istatistiksel garantisini tamamen geçersiz kılabilir.

**Önemli nüans — kötü niyetli seçilmiş sayılar:** Miller-Rabin'in `1/4` sınırı *rastgele seçilmiş* `n` için geçerlidir. Bir saldırgan önceden belirli tabanlara karşı Miller-Rabin'i geçecek bileşik sayılar inşa edebilir (bu sayılar literatürde bilinir). Bu yüzden güvenlik kritik bağlamlarda tabanların **testi çalıştıran taraf tarafından rastgele** seçilmesi, saldırganın önceden bilebileceği sabit bir taban listesi kullanılmaması önemlidir.

### Doğru Kullanım, En İyi Pratikler, Yaygın Hatalar

**En iyi pratik:** Önce küçük asallara (2, 3, 5, 7, ...) bölünebilirlik ile hızlı eleme yapmak (adayların büyük çoğunluğu bu ucuz filtrede elenir), sonra Miller-Rabin uygulamak. Bazı kütüphaneler ek olarak Lucas testiyle birleştirerek (Baillie-PSW yaklaşımı) daha güçlü garanti sağlar.

**Yaygın hata:** Tur sayısını (`k`) çok düşük tutmak (ör. eğitim amaçlı örneklerde sık görülen `k=1` veya `k=5`), üretim kriptografisinde yetersiz güvenlik payı bırakır. Anahtar üretimi tek seferlik bir işlem olduğundan (kullanıcı deneyiminde saniyeler fark etmez) tur sayısını cömert tutmanın maliyeti düşüktür — bu nedenle standartlar burada tutucu davranmayı önerir.

**Yaygın hata:** Asallık testinden geçen `p` ve `q`'yu ek yapısal kontroller olmadan kabul etmek. Güvenli RSA anahtar üretimi ayrıca `p` ve `q`'nun birbirine çok yakın olmamasını (Fermat çarpanlarına ayırma saldırısına karşı), `p-1` ve `q-1`'in yeterince büyük asal çarpanlara sahip olmasını (bazı eski çarpanlara ayırma yöntemlerine karşı) gözetir. Bu kontroller "asallık testi" kapsamının biraz dışına taşan ama aynı anahtar üretim boru hattının parçası olan ek sağlamlaştırmalardır.

### Tespit Açısı

Bir anahtar üretim kütüphanesini değerlendirirken bakılacak noktalar: (1) rastgelelik kaynağının kriptografik olarak güvenli olup olmadığı (işletim sisteminin CSPRNG'i mi, yoksa zayıf bir sözde rastgele üreteç mi), (2) Miller-Rabin tur sayısının hedef güvenlik seviyesine uygun olup olmadığı, (3) tabanların testi çalıştıran taraf tarafından taze rastgelelikle seçilip seçilmediği. Üretilen anahtarlarda anormal derecede küçük asal farkı (`|p - q|`) veya tekrarlayan asal kullanımı (birden fazla anahtarın ortak bir asal çarpanı paylaşması — büyük ölçekli anahtar taramalarında gerçek dünyada bulunmuş bir zafiyet sınıfıdır) izlenebilecek pratik göstergelerdir.

## Bu Dört Algoritmanın Birlikte Çalışması: RSA Anahtar Yaşam Döngüsü Üzerinden Özet

1. **Anahtar üretimi:** Miller-Rabin ile rastgele büyük asal adayları test edilerek `p` ve `q` bulunur; `n = p*q`, `φ(n) = (p-1)(q-1)` hesaplanır.
2. **Özel üs türetimi:** Genişletilmiş Öklid ile `d = e^-1 mod φ(n)` bulunur; CRT parametreleri (`dp, dq, qinv`) önceden hesaplanır.
3. **İmzalama/deşifreleme:** CRT-RSA ile işlem `mod p` ve `mod q` üzerinde hızlı modüler üs alma (sabit zamanlı) kullanılarak yapılır, sonuçlar CRT ile birleştirilir.
4. **Doğrulama:** Üretilen imza, açık anahtarla anında doğrulanarak fault-attack riski azaltılır.

Her aşamada bir zayıflık, bir sonraki aşamanın güvenlik varsayımını geçersiz kılabilir: zayıf rastgelelik → tahmin edilebilir asallar; sabit olmayan zamanlı üs alma → timing ile anahtar sızıntısı; doğrulamasız CRT → fault attack ile çarpanlara ayırma. Bu nedenle "RSA güvenlidir" ifadesi aslında "RSA'nın matematiksel problemi zordur VE bu dört alt algoritma doğru implemente edilmiştir" ifadesinin kısaltmasıdır. Bir güvenlik değerlendirmesinde protokol seviyesinde doğru görünen bir sistem, bu alt katmanda basit bir implementasyon hatası yüzünden tamamen kırılabilir — bu yazının ana çıkarımı budur.

## Sonuç

Hızlı modüler üs alma, genişletilmiş Öklid algoritması, Çin Kalan Teoremi ve Miller-Rabin asallık testi, modern açık anahtarlı kriptografinin görünmeyen ama her şeyi taşıyan iskeletidir. Bu algoritmaların her biri kendi başına zarif ve verimlidir, ama her biri aynı zamanda kendine özgü bir yan-kanal veya hata sınıfı taşır: üs almada zamanlama, Öklid'de normalize etmeme hatası, CRT'de fault injection, asallık testinde zayıf rastgelelik. Savunmacı bir mühendis için buradaki pratik ders, "kütüphaneyi güven ama implementasyon detaylarını denetle" ilkesidir — özellikle sabit zamanlı garantiler, doğrulama adımları ve rastgelelik kaynağı gibi noktalarda.
