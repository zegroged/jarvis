# Yan Kanal Saldırıları (Side-Channel Attacks): Timing, Power Analysis, Cache-Timing ve Spectre/Meltdown

## Giriş: Neden Bu Konu Kritik

Kriptografi eğitiminin büyük bölümü "matematiksel güvenlik" üzerine kuruludur: AES'in brute-force ile kırılamayacağını, RSA'nın çarpanlara ayırma zorluğuna dayandığını, ECDSA'nın ayrık logaritma probleminin zorluğundan güç aldığını öğreniriz. Bu analiz **doğrudur ama eksiktir**. Çünkü bir algoritma soyut bir matematik nesnesi olarak güvenli olsa bile, o algoritmayı çalıştıran gerçek bir CPU, gerçek bir elektrik devresi, gerçek bir bellek hiyerarşisi vardır — ve bu fiziksel/mikromimari gerçeklik, algoritmanın "ideal" davranışından sapmalar üretir. İşte side-channel attack (yan kanal saldırısı), tam da bu sapmayı hedef alır: **algoritmanın girdisi/çıktısı değil, algoritmayı çalıştırırken ortaya çıkan yan etkiler** (süre, güç tüketimi, elektromanyetik emisyon, ses, önbellek durumu, spekülatif yürütme izleri) bilgi sızdırır.

Bu konunun bir eğitim korpusunda mutlaka yer alması gerekir çünkü pratikte kriptografik sistemlerin kırılma nedenlerinin önemli bir kısmı algoritmanın matematiksel zayıflığından değil, implementasyon hatalarından kaynaklanır. RSA, AES, ECDSA matematiksel olarak sağlamdır; ama "sabit zamanlı olmayan" bir karşılaştırma fonksiyonu, "veriye bağımlı dallanma" içeren bir if-else bloğu, ya da modern bir CPU'nun performans için yaptığı spekülatif yürütme optimizasyonu, o sağlam matematiği anlamsız hale getirebilir. Savunmacı/mühendis perspektifinden bu konuyu anlamak demek, "algoritma doğru seçildi, güvenliyiz" yanılgısından çıkıp "implementasyon ve donanım da tehdit yüzeyinin parçası" bakış açısına geçmek demektir.

## Kök Neden: Neden Yan Kanallar Var?

Yan kanalların var olmasının temel nedeni şudur: **modern donanım ve yazılım, performans için veriye bağımlı optimizasyonlar yapar.** Bu optimizasyonların her biri, "hangi veri işleniyor" sorusuna dair bir ipucu sızdırır.

Somut nedenler:

1. **Veriye bağımlı dallanma (data-dependent branching):** `if (key_bit == 1) { A() } else { B() }` gibi bir kod, key_bit'in değerine göre farklı komutlar çalıştırır. Farklı komutlar farklı süre alır, farklı güç tüketir, farklı önbellek satırlarına erişir.
2. **Veriye bağımlı bellek erişimi:** Bir tablo look-up işlemi (`sbox[key_byte]` gibi), erişilen indekse göre farklı bellek adreslerine dokunur. Bu adresler CPU önbelleğinde (cache) iz bırakır — hangi satırın önbellekte olduğu, dolaylı olarak indeksi (yani anahtar baytını) sızdırabilir.
3. **Mikromimari optimizasyonlar:** Modern CPU'lar sırayla değil, spekülatif ve out-of-order çalışır; dallanma tahmini (branch prediction) yapar; önbellek hiyerarşisi kullanır. Bunların hepsi "gerçekte hangi yol izlendi" bilgisini fiziksel iz olarak bırakır.
4. **Fiziksel gerçeklik:** Bir transistörün anahtarlanması elektrik akımı çeker; işlemci farklı komutlar için farklı miktarda güç harcar; bu güç tüketimi elektromanyetik dalga olarak da yayılır ve dışarıdan ölçülebilir.

Kısacası: **hesaplama fiziksel bir süreçtir ve fiziksel süreçler gözlemlenebilir yan etkiler üretir.** Algoritmanın matematiği bu yan etkileri hesaba katmadığı sürece, saldırgan bu yan etkileri "yan kanal" olarak kullanıp gizli veriyi (anahtar, parola, plaintext) çıkarsayabilir.

Bu, güvenlik mühendisliğinde çok genel bir prensibin özel bir örneğidir: **soyutlama sızıntısı (abstraction leakage)**. Bir sistemi tasarlarken hangi katmanda çalıştığımızı düşünürüz (matematik katmanı), ama saldırgan alttaki katmanda (fiziksel/mikromimari katman) çalışır ve üst katmanın varsaymadığı bilgiye erişir.

## Timing Attacks (Zamanlama Saldırıları)

### Çalışma Mantığı

En temel yan kanal türü budur: bir işlemin ne kadar sürdüğünü ölçerek, işlenen verinin kendisi hakkında bilgi çıkarmak. Mantık şu: eğer bir fonksiyonun çalışma süresi işlediği gizli veriye (anahtar, parola) bağlıysa, saldırgan bu süreyi tekrar tekrar ölçüp istatistiksel analiz yaparak gizli veriyi bit bit veya bayt bayt çıkarabilir.

Klasik örnek: **naif string karşılaştırması**. Bir parola veya HMAC doğrulama kodu şöyle yazılmışsa:

```
for i in range(len(input)):
    if input[i] != secret[i]:
        return False
return True
```

Bu fonksiyon, ilk yanlış baytta erken çıkış (early return) yapar. Yani `secret`'ın ilk baytı doğru tahmin edilmişse fonksiyon bir adım daha ileri gider ve dolayısıyla biraz daha uzun sürer. Saldırgan, her olası bayt değeri için binlerce kez ölçüm yapıp ortalama süreyi karşılaştırarak, doğru baytı (en uzun süren tahmin) bulabilir. Bu işlemi bayt bayt tekrarlayarak tüm gizli değeri —teorik olarak O(n × 256) civarı denemeyle— çözebilir; brute force'un O(256^n) karmaşıklığına göre devasa bir hızlanmadır.

Aynı mantık RSA gibi asimetrik algoritmalarda da geçerlidir: modüler üs alma (modular exponentiation) işleminde kullanılan "square-and-multiply" algoritması, özel anahtarın her bitine göre farklı sayıda çarpma işlemi yapabilir; bu da toplam süreyi bit desenine bağımlı kılar. Paul Kocher'in 1996'daki çığır açan çalışması tam olarak bunu göstermiştir: ağ üzerinden bile (network jitter'a rağmen) yeterli örnekleme ile RSA özel anahtarının timing saldırısıyla çıkarılabileceğini kanıtlamıştır.

### Tespit

- **Kod incelemesi (statik analiz):** Gizli veriye bağımlı `if/else`, döngü erken çıkışı, veriye bağımlı döngü sayısı olan fonksiyonları ara. Özellikle kriptografik karşılaştırma, imza doğrulama, MAC doğrulama, parola kontrolü fonksiyonları risk altındadır.
- **Dinamik/istatistiksel analiz:** Aynı fonksiyonu farklı girdilerle binlerce kez çalıştırıp süre dağılımını ölç; girdiye göre istatistiksel olarak anlamlı süre farkı varsa (t-test, Welch's t-test — akademik literatürde "TVLA": Test Vector Leakage Assessment yaygın bir metodolojidir) bu bir zafiyet işaretidir.
- **Araç destekli tespit:** dg/dudect gibi zamanlama sızıntısı tespit araçları veya derleyici/statik analiz araçları (ör. ctgrind, Valgrind tabanlı sabit-zaman doğrulayıcılar) kullanılabilir.

### Savunma

- **Sabit zamanlı (constant-time) implementasyon:** Karşılaştırma, seçim ve dallanma işlemlerini gizli veriden bağımsız sabit sürede çalışacak şekilde yaz. Örneğin karşılaştırmada erken çıkış yapmadan tüm baytları XOR'layıp OR'layarak tek seferde sonucu üret (`constant_time_compare`).
- **Kriptografik kütüphanelere güven, kendi kripton yazma:** Olgun kütüphaneler (libsodium, BoringSSL, OpenSSL'in modern sürümleri) bu tür sabit-zaman garantilerini üretim kalitesinde sağlar; "roll your own crypto" yapmak neredeyse her zaman yan kanal riski taşır.
- **Blinding (kör etme):** RSA gibi algoritmalarda, işlem öncesi veriye rastgele bir maskeleme (blinding factor) uygulayıp işlem sonrası kaldırma — bu, saldırganın gördüğü süre ile gerçek özel anahtar arasındaki korelasyonu kırar.
- **Donanım/dil seviyesinde sabit zamanlı primitifler:** Modern CPU'larda AES-NI gibi donanım hızlandırmalı talimatlar, yazılım tablo look-up'larına göre yan kanal sızıntısını büyük ölçüde azaltır çünkü veriye bağımlı bellek erişimi ortadan kalkar.

## Power Analysis / DPA (Differential Power Analysis)

### Çalışma Mantığı

Power analysis, bir cihazın (özellikle akıllı kartlar, IoT cihazları, donanım güvenlik modülleri — HSM, gömülü sistemler) çalışırken çektiği elektrik akımını ölçerek iç durumunu çıkarsamayı hedefler. Kök neden: CMOS transistörlerde bit 0'dan 1'e (veya tam tersi) geçtiğinde anlık akım tüketimi olur; bu nedenle işlenen verinin Hamming ağırlığı (bitteki 1 sayısı) veya Hamming mesafesi (ardışık işlenen değerler arası fark), toplam güç tüketimi ile korelasyonludur.

İki ana teknik vardır:

- **SPA (Simple Power Analysis):** Tek bir güç izini (trace) doğrudan gözle veya basit analizle inceleyerek yapısal bilgi çıkarma. Örneğin RSA'nın square-and-multiply algoritmasında "square" ve "multiply" işlemlerinin güç profili farklıysa, iz üzerinde bu ikisinin sırası doğrudan özel anahtarın bit desenini verir.
- **DPA (Differential Power Analysis):** Paul Kocher, Joshua Jaffe ve Benjamin Jun tarafından 1990'ların sonunda tanıtılan istatistiksel teknik. Saldırgan, aynı işlemin binlerce/on binlerce güç izini toplar, anahtarın olası bir baytı (veya alt kümesi) için bir "hipotez" kurar (ör. AES S-box çıktısının Hamming ağırlığı), bu hipoteze göre izleri iki gruba ayırır ve gruplar arası ortalama fark hesaplar. Doğru anahtar hipotezinde bu fark istatistiksel olarak belirgin bir "sivri uç" (spike) üretirken yanlış hipotezlerde gürültüye karışır. Bu yöntem, tek bir izde görünmeyen çok zayıf sinyalleri istatistiksel ortalamayla ortaya çıkarır — dolayısıyla donanım gürültüsüne karşı bile etkilidir.
- **CPA (Correlation Power Analysis):** DPA'nın gelişmiş bir varyantı; ikili gruplama yerine Pearson korelasyon katsayısı kullanarak hipotez ile ölçülen güç arasındaki ilişkiyi doğrudan nicel olarak değerlendirir, genellikle daha az iz ile daha güçlü sonuç verir.

Aynı prensip **elektromanyetik analiz (EMA/EM-SCA)** için de geçerlidir: cihazın ürettiği EM emisyonları, özellikle yerel prob ile belirli bir çip bölgesine odaklanarak ölçülür ve benzer istatistiksel yöntemlerle analiz edilir. EM analiz genellikle güç analizine göre daha "hedefe özel" (spatial olarak lokalize) bilgi verir çünkü çipin farklı bölgelerinden farklı sinyal alınabilir.

### Tespit

Power/EM analysis tespiti, çoğunlukla **kurumsal/laboratuvar bağlamında ürün güvenlik değerlendirmesi (evaluation)** sürecinde yapılır, canlı ağ trafiğinde tespit edilecek bir şey değildir:

- Donanım güvenlik sertifikasyon süreçleri (ör. Common Criteria, FIPS 140-3 gibi çerçevelerde yan kanal dayanıklılık testleri) cihazı osiloskop ve EM prob ile test eder.
- Kurum içi güvenlik ekipleri, kritik gömülü/IoT/ödeme cihazlarını üretime çıkmadan önce TVLA benzeri metodolojilerle test eder: cihaz sabit girdilerle mi yoksa rastgele girdilerle mi istatistiksel olarak ayırt edilebilir güç profili üretiyor, ölçer.
- Üretim ortamında fiziksel olarak "kim cihaza prob bağladı" tespiti, fiziksel güvenlik kontrolleri (tamper-evident muhafaza, tamper detection sensörleri, anormal fiziksel erişim logları) ile ele alınır — bu klasik "endpoint detection" mantığından çok fiziksel güvenlik ve tedarik zinciri güvenliği alanına girer.

### Savunma

- **Maskeleme (masking):** Ara değerleri rastgele bir maske ile XOR'layıp gerçek değeri gizlemek; hesaplama maskelenmiş veri üzerinde yapılır, en sonda maske kaldırılır. Bu, Hamming ağırlığı ile gerçek veri arasındaki korelasyonu istatistiksel olarak kırar.
- **Gizleme (hiding):** Güç tüketimini veriden bağımsız hale getirmeye çalışmak — sabit güç tüketen mantık devreleri (dual-rail logic), rastgele gecikmeler (random delays/jitter), işlem sırasını karıştırma (shuffling/randomized execution order), dummy (sahte) işlemler ekleme.
- **Donanımsal karşı önlemler:** Güç hattı filtreleme, dahili kapasitörler ile ani akım dalgalanmalarını yumuşatma, yonga üzerinde sensör ile fiziksel müdahale (probing/tamper) tespiti.
- **Anahtar rotasyonu ve oturum sınırlama:** Bir anahtarla yapılan işlem sayısını sınırlamak, saldırganın DPA için gereken çok sayıda izi toplamasını zorlaştırır (istatistiksel gücün örnek sayısına bağlı olduğunu unutmayın).
- **Sertifikasyon süreçlerine güven:** Kritik donanım (akıllı kart, HSM, ödeme terminali) seçerken, yan kanal dayanıklılığı test edilmiş, ilgili sertifikalara sahip ürünleri tercih etmek — bunu kendi başına doğrulamaya çalışmak yerine üçüncü taraf değerlendirmesine dayanmak, çoğu kurum için gerçekçi yaklaşımdır.

## Cache-Timing Attacks

### Çalışma Mantığı

Cache-timing, timing attack'in mikromimari düzeyde özel ve son derece güçlü bir alt türüdür. Kök neden: CPU önbelleği (L1/L2/L3) sınırlı boyuttadır ve bellek erişimleri önbellekte "hit" (önbellekte var, hızlı) veya "miss" (önbellekte yok, RAM'den getirilmeli, yavaş) olabilir. Bu hit/miss farkı onlarca-yüzlerce CPU çevrimi (cycle) mertebesinde ölçülebilir bir süre farkı yaratır. Eğer bir kriptografik algoritma, gizli veriye bağlı olarak *hangi bellek adresine* eriştiğini belirliyorsa (örneğin AES'in yazılım S-box look-up tablosu, anahtar baytına göre farklı tablo indekslerine erişir), saldırgan bu erişim örüntüsünü önbellek zamanlaması üzerinden çıkarsayabilir.

En bilinen teknikler:

- **Evict+Time:** Saldırgan belirli bir önbellek setini "tahliye eder" (kendi verisiyle doldurur), kurbanın işlemini bir kez çalıştırır, sonra toplam süreyi ölçer. Eğer kurban o set ile ilgili bir adrese erişmişse süre daha uzun olur (çünkü tekrar getirmesi gerekir).
- **Prime+Probe:** Saldırgan önce önbelleği kendi verisiyle "doldurur" (prime), kurbanın çalışmasına izin verir, sonra kendi verisine tekrar erişip (probe) hangi setlerin "evict" edildiğini (yani kurban tarafından kullanıldığını) süre ölçerek anlar. Bu teknik, saldırganın kurbanla aynı bellek bölgesini paylaşmasına gerek duymaz — sadece önbellek setlerini paylaşmaları yeterlidir; bu da onu **paylaşımlı bulut ortamlarında (multi-tenant cloud), aynı fiziksel makinede farklı VM'ler arasında** dahi uygulanabilir kılar.
- **Flush+Reload:** Eğer saldırgan ile kurban aynı fiziksel bellek sayfasını paylaşıyorsa (ör. paylaşılan kütüphane, deduplicated bellek), saldırgan bir bellek adresini `clflush` benzeri bir talimatla önbellekten atar, kurbanın çalışmasını bekler, sonra o adrese tekrar erişip süreyi ölçer — hızlıysa kurban o adrese erişmiştir. Bu, en yüksek çözünürlüklü ve en yaygın kullanılan cache-timing tekniklerinden biridir; AES T-table implementasyonlarına, RSA/ECDSA'ya karşı akademik olarak defalarca gösterilmiştir.

Kök neden özetle: **paylaşılan mikromimari kaynaklar (önbellek), izolasyon varsayımını kırar.** İşletim sistemi/hipervizör seviyesinde "process A ve process B birbirinden izole" dense bile, ikisi aynı fiziksel önbelleği paylaşıyorsa, önbellek durumu üzerinden bilgi sızabilir — bu, sanallaştırma ve konteynerlerin güvenlik sınırı iddialarını fiziksel donanım seviyesinde zayıflatan temel bir gerçektir.

### Tespit

- **Statik kod analizi:** Gizli veriye bağımlı dizi indeksleme (`table[secret_byte]`) veya veriye bağımlı bellek erişim deseni olan kriptografik kod parçalarını tara.
- **Mikromimari izleme:** Performans sayaçları (perf counters — cache miss oranı, LLC (last-level cache) miss/hit istatistikleri) anormal örüntü gösteriyorsa, bu bir cache-timing saldırı girişiminin (özellikle Prime+Probe gibi yüksek frekanslı önbellek erişim döngülerinin) işareti olabilir. Kurumsal ortamlarda bulut sağlayıcıları ve güvenlik araştırmacıları bu tür anomali tespiti için özel sayaç izleme araçları kullanır.
- **Yan kanal test çerçeveleri:** dudect gibi araçlar, yazılımın veri bağımlı zamanlama sızdırıp sızdırmadığını istatistiksel olarak test etmek için kullanılabilir; bu, cache-timing kaynaklı sızıntıları da (dolaylı olarak toplam süre üzerinden) yakalayabilir.

### Savunma

- **Sabit zamanlı / veri-bağımsız erişim deseni:** Kriptografik implementasyonlarda tablo look-up yerine bit-slicing veya donanım hızlandırmalı talimatlar (AES-NI gibi) kullanmak — bu talimatlar S-box'ı bellek erişimi olmadan devre içinde hesaplar, dolayısıyla önbellek tabanlı sızıntıyı ortadan kaldırır.
- **Önbellek bölümleme / izolasyon:** Bulut/sanallaştırma ortamlarında cache partitioning (Intel CAT — Cache Allocation Technology gibi mekanizmalar) kritik iş yüklerini diğer kiracılardan önbellek düzeyinde izole edebilir.
- **Sayfa paylaşımını sınırlama:** Güvenlik açısından hassas süreçler için "page deduplication" (KSM benzeri mekanizmalar) devre dışı bırakmak, Flush+Reload gibi tekniklerin ön koşulunu (paylaşılan fiziksel sayfa) ortadan kaldırır.
- **Rastgele gecikme/gürültü ekleme:** Zamanlama ölçümünü zorlaştırmak için yürütmeye kontrollü gürültü eklemek — bu tam çözüm değildir (istatistiksel ortalamayla hâlâ aşılabilir) ama saldırı maliyetini artırır.
- **Kritik iş yüklerini fiziksel olarak izole etme:** Çok yüksek hassasiyetli anahtar işlemleri (ör. HSM içinde) paylaşımlı genel amaçlı donanımdan ayrı, özel donanımda çalıştırmak.

## Spectre / Meltdown ve Spekülatif Yürütmenin Kriptoya Etkisi

### Kavramsal Arka Plan

2018'de kamuoyuna duyurulan Spectre ve Meltdown, cache-timing mantığını bir üst seviyeye taşıyan, CPU'ların **spekülatif yürütme (speculative execution)** ve **out-of-order execution** optimizasyonlarından kaynaklanan mikromimari zafiyet sınıflarıdır. Kök neden şudur: modern CPU'lar performans için, bir dallanmanın (branch) sonucunu henüz kesin olarak bilmeden, "muhtemelen doğru olacağını tahmin ettiği" yolu önceden yürütmeye başlar (speculative execution). Eğer tahmin yanlış çıkarsa, mimari durum (register, bellek yazımı gibi kullanıcıya görünür etkiler) geri alınır (**mimari olarak** hiç olmamış gibi davranılır) — ama bu spekülatif yürütme sırasında **mikromimari yan etkiler** (özellikle önbellek durumu) geri alınmaz. Yani CPU "gerçekte olmaması gereken" bir işlemi kısa süreliğine çalıştırmış, sonucu iptal etmiş, ama o işlemin önbellekte bıraktığı iz kalıcı olarak durmuştur.

Bu, saldırgana şu deseni açar: CPU'yu, normalde erişim izni olmayan bir belleğe (Meltdown'da çekirdek belleği; Spectre'de aynı süreç içinde ama erişilmemesi gereken bir veri, örneğin sınır kontrolü atlatılarak) spekülatif olarak eriştirmek, bu erişilen değere bağlı olarak bir önbellek satırına dokundurmak (`array2[secret_value * 512]` gibi bir "gadget" kodu), sonra spekülasyon iptal edildikten sonra bile o önbellek izini Flush+Reload tekniğiyle okuyarak spekülasyon sırasında "görülen" gizli veriyi bit bit/bayt bayt çıkarmak.

- **Meltdown**, temel olarak bir CPU'nun yetki kontrolünü (sıra dışı yürütme sırasında) yeterince erken uygulamamasından kaynaklanır ve kullanıcı seviyesi bir sürecin çekirdek belleğini (ve dolayısıyla teorik olarak diğer süreçlerin belleğini) okumasına izin verebilir.
- **Spectre**, dallanma tahmininin (branch prediction) kötüye kullanılmasına dayanır; saldırgan CPU'nun dal tahmin birimini eğiterek (training), kurban kodun normalde erişmeyeceği bir belleğe spekülatif olarak eriştirmesini sağlar. Spectre, Meltdown'dan farklı olarak tek bir donanım hatası değil, dallanma tahmini yapan hemen hemen tüm modern CPU mimarilerini etkileyen daha genel bir zafiyet sınıfıdır ve düzeltmesi (mitigasyonu) daha zordur.

### Kriptografiye Etkisi

Bu zafiyetler doğrudan "kripto algoritması kırıldı" anlamına gelmez; ama pratik etkisi kriptografiyi ciddi şekilde tehdit eder çünkü:

1. **Anahtar materyali bellekte açık halde bulunur.** Şifreleme/imzalama işlemleri sırasında özel anahtarlar RAM'de (bazen belirli sürelerle) düz metin olarak tutulur. Spectre/Meltdown türü saldırılar, bu belleği izin dışı okuma imkânı sunduğu için, kripto işlemi matematiksel olarak sağlam olsa dahi anahtarın kendisi bellekten sızdırılabilir.
2. **Sanallaştırma/konteyner izolasyonunu zayıflatır.** Bulutta çalışan bir kripto servisinin (ör. bir HSM emülasyonu, bir TLS terminasyon sunucusu) yanında çalışan kötü niyetli bir kiracı VM, teorik olarak Spectre varyantlarıyla komşu VM'in bellek alanına ait izleri okumaya çalışabilir — "aynı fiziksel makinede izolasyon garanti edilir" varsayımını sarsar.
3. **Kripto kütüphaneleri de "gadget" içerebilir.** Sabit-zamanlı yazılmış bir kripto fonksiyonu bile, derleyici optimizasyonları veya CPU'nun spekülatif yürütmesi nedeniyle, "mimari olarak hiç çalışmaması gereken" bir dallanma yolunu spekülatif olarak yürütüp önbellekte iz bırakabilir — bu, "sabit zamanlı kod yazdım, güvendeyim" varsayımını da kısmen sarsan önemli bir noktadır.

### Tespit

- **Mikroarşitektürel izleme:** Performans sayaçları üzerinden anormal spekülatif yürütme/branch misprediction oranlarını izlemek (araştırma seviyesinde; üretim ortamında pratik ve gürültüsüz tespit hâlâ zordur).
- **Zafiyet tarama araçları:** CPU/işletim sistemi üreticilerinin yayınladığı tespit script'leri (ör. belirli mikrokod ve çekirdek yaması seviyesini kontrol eden araçlar) sistemin savunmasız olup olmadığını (yama durumu üzerinden) kontrol eder — bu, aktif saldırıyı değil, **açıklığın var olup olmadığını** tespit eder.
- **Yama/mikrokod versiyon takibi:** Varlık yönetimi ve zafiyet yönetimi (vulnerability management) süreçlerinde CPU mikrokodu, işletim sistemi çekirdeği ve derleyici sürümlerinin bu sınıf zafiyetlere karşı güncel olup olmadığını sürekli izlemek.

### Savunma

- **Mikrokod ve işletim sistemi yamaları:** CPU üreticilerinin yayınladığı mikrokod güncellemeleri (dallanma tahmin birimini süreçler arası izole eden mekanizmalar gibi) ve işletim sisteminin çekirdek sayfa tablosu izolasyonu (KPTI/KAISER benzeri yaklaşımlar, Meltdown'a karşı kullanıcı/çekirdek adres alanlarını daha katı ayırır) uygulamak.
- **Derleyici tabanlı mitigasyonlar:** Spekülatif yürütmeyi durduran talimatlar (ör. bariyer/fence talimatları) derleyici tarafından riskli dallanma noktalarına otomatik eklenebilir; kritik kod yollarında manuel olarak da eklenebilir.
- **Kritik anahtar materyalini izole etme:** Mümkün olduğunda özel anahtar işlemlerini ayrı fiziksel donanımda (HSM) veya güvenilir yürütme ortamlarında (TEE — Trusted Execution Environment, örn. donanım destekli enclave teknolojileri) yapmak; bu tür ortamlar tasarım olarak bazı yan kanal sınıflarına karşı ek izolasyon sağlamayı hedefler (mükemmel değildir, kendi yan kanal geçmişleri de vardır, ama genel amaçlı CPU'ya göre saldırı yüzeyini daraltır).
- **Bulutta kiracı izolasyonu sıkılaştırma:** Çok kiracılı ortamlarda aynı fiziksel çekirdek/önbelleği paylaşan VM'lerin güven sınırlarını netleştirmek; yüksek hassasiyetli iş yükleri için "dedicated host" / fiziksel izolasyon seçeneklerini tercih etmek.
- **Performans-güvenlik dengesini bilinçli yönetmek:** Bu mitigasyonların çoğu performans maliyeti getirir (spekülasyonu kısıtlamak CPU'yu yavaşlatır). Güvenlik mühendisliğinin gerçekçi tarafı: bu maliyeti hangi iş yükünde göze alacağınıza risk değerlendirmesiyle karar vermektir — her sistemde maksimum mitigasyon her zaman doğru cevap olmayabilir, ama karar bilinçli ve dokümante edilmiş olmalıdır.

## Yaygın Hatalar

Yan kanal savunması söz konusu olduğunda mühendislerin ve kurumların düştüğü tipik hatalar:

1. **"Algoritma matematiksel olarak güvenli, o zaman güvenliyiz" yanılgısı.** En yaygın ve en tehlikeli hata budur. AES-256 veya RSA-4096 seçmiş olmak, implementasyonun yan kanal sızdırmadığı anlamına gelmez. Algoritma seçimi ile implementasyon güvenliği farklı katmanlardır.
2. **Kendi kripto/karşılaştırma kodunu yazmak.** "Basit bir string karşılaştırması" yazarken erken çıkışlı döngü kullanmak, HMAC doğrulamada `==` operatörüne güvenmek gibi küçük görünen kararlar, gerçek dünyada tekrar tekrar sömürülen timing zafiyetleri üretmiştir.
3. **Sadece ağ gecikmesi (network jitter) yüzünden timing saldırısının pratikte imkânsız olduğunu düşünmek.** İstatistiksel yöntemlerle (çok sayıda örnekleme, ortalama alma) network jitter'ın üzerine çıkmak mümkündür; "network zaten gürültülü" argümanı tek başına yeterli bir savunma değildir.
4. **Yan kanal testini geliştirme sürecine hiç dahil etmemek.** Fonksiyonel test (doğru input → doğru output) yapılır ama "bu fonksiyonun çalışma süresi girdiden bağımsız mı" sorusu hiç sorulmaz. TVLA benzeri değerlendirmeler genellikle sadece donanım güvenlik ürünlerinde zorunlu tutulur, genel yazılımda ihmal edilir.
5. **Mitigasyonları "hepsi ya da hiçbiri" şeklinde ele almak.** Spectre/Meltdown yamalarını performans kaygısıyla tamamen devre dışı bırakmak ya da tam tersi her sistemde maksimum mitigasyonu zorunlu kılmak — ikisi de risk temelli olmayan, kaba yaklaşımlardır.
6. **Donanım güvenini sorgulamamak.** "CPU üretici garantisi var, güvenlidir" varsayımı ile üçüncü parti/tedarik zinciri kaynaklı donanım risklerini (ör. sahte/değiştirilmiş donanım, düşük kaliteli gömülü cihazlarda hiç yan kanal testi yapılmamış olması) göz ardı etmek.
7. **Yan kanalı sadece "kripto" bağlamında düşünmek.** Aslında yan kanal sızıntısı parola karşılaştırma, oturum token doğrulama, hatta yapay zeka çıkarım sunucularının (inference timing üzerinden model/veri sızıntısı) gibi kriptografi dışı alanlarda da geçerlidir; savunmacı bakış açısı bunu dar bir "sadece şifreleme kütüphanesi" sorunu olarak görmemelidir.

## Sonuç

Yan kanal saldırıları, güvenlik mühendisliğine şu temel dersi verir: **güvenlik, soyut modelin değil, gerçek implementasyonun özelliğidir.** Bir algoritmanın "kırılamaz" olması, onu çalıştıran donanım ve yazılımın da kırılamaz olduğu anlamına gelmez. Savunmacı bir mühendis için pratik çıkarım şudur: kriptografik kod yazarken veya seçerken, sadece "hangi algoritma" sorusunu değil, "bu implementasyon sabit zamanlı mı, veriye bağımlı dallanma/bellek erişimi var mı, bu donanım hangi mikromimari zafiyetlere maruz ve yamalı mı" sorularını da sormak gerekir. Olgun kriptografik kütüphanelere güvenmek, düzenli yama yönetimi yapmak, kritik anahtar operasyonlarını izole donanımda tutmak ve yan kanal testini güvenlik test sürecinin standart bir parçası haline getirmek, bu tehdit sınıfına karşı gerçekçi ve sürdürülebilir savunma hattını oluşturur.
