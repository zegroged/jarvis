# Yan Kanal Saldırıları: Mikromimari Zafiyetler (Spectre/Meltdown, Cache Timing, Rowhammer)

## Giriş ve Kapsam

Klasik güvenlik açıkları yazılım mantığındaki hatalardan doğar: bir tampon taşması (buffer overflow), yanlış bir yetki denetimi, hatalı bir girdi doğrulaması. **Yan kanal saldırıları (side-channel attacks)** ise tamamen farklı bir katmanda çalışır. Burada saldırgan, programın *ne yaptığına* değil, o işi yaparken sisteme *sızdırdığı fiziksel veya davranışsal ize* bakar. Bir hesaplama ne kadar sürdü, işlemci ne kadar güç çekti, hangi bellek bölgesi önbelleğe (cache) girdi, elektromanyetik yayılım nasıl değişti; bunların hepsi, matematiksel olarak "gizli" olması gereken veriye dair sızıntı taşıyabilir.

Bu makale özellikle **mikromimari (microarchitectural) yan kanallar** üzerine odaklanır. Bunlar, modern CPU'ların performans için kullandığı optimizasyonların (spekülatif yürütme, önbellekleme, DRAM yoğunluğu) yan ürünü olarak ortaya çıkan zafiyetlerdir. Amacımız mekanizmayı *anlamak* ve buna karşı *tespit ile savunma* kurmaktır; bu operasyonel bir saldırı el kitabı değildir.

## Temel Kavram: Yan Kanal Nedir?

### Tanım

Bir **yan kanal**, bir sistemin asıl işlevsel çıktısı dışında, çalışması sırasında dolaylı olarak dışarı verdiği ölçülebilir bir sinyaldir. Kriptografi bağlamında, bir algoritma matematiksel olarak kusursuz olabilir, ama uygulaması (implementation) gizli anahtara bağlı gözlemlenebilir bir davranış sergiliyorsa, saldırgan bu davranışı ölçerek anahtarı geri kurabilir.

Klasik yan kanal türleri:

- **Zamanlama (timing):** İşlemin süresi gizli veriye bağlıysa. Örneğin bir dizgi karşılaştırması, ilk farklı byte'ta erken dönerse, saldırgan byte byte parola tahmin edebilir.
- **Güç analizi (power analysis):** İşlemcinin çektiği anlık güç, yürütülen komutlara ve işlenen bitlere göre değişir. Akıllı kartlar (smart card) klasik hedeftir.
- **Elektromanyetik (EM) yayılım:** Devrelerin yaydığı EM sinyaller uzaktan yakalanabilir.
- **Akustik / termal:** Daha egzotik, ama gerçek örnekleri vardır.

### Kök Neden

Yan kanalların temel nedeni **soyutlama sızıntısıdır (abstraction leakage)**. Programcı, kodu ideal, sabit-maliyetli bir soyut makine üzerinde çalışıyormuş gibi düşünür. Gerçek donanım ise performans için veriye bağlı kısayollar alır: önbellek isabet ederse hızlı, ıskalarsa yavaş; dal tahmini tutarsa hızlı, tutmazsa yavaş. Bu veriye-bağlı davranış farkları, dışarıdan gözlemlenebildiğinde yan kanala dönüşür.

## Cache Timing (Önbellek Zamanlaması) Saldırıları

### Neden Önbellek Bir Kanaldır?

Modern CPU'larda ana bellek (DRAM) erişimi yüzlerce döngü sürerken, L1 önbellekten erişim birkaç döngüdür. Bu devasa hız farkı, saldırgana ölçülebilir bir "termometre" verir: bir bellek satırına (cache line) erişim *hızlıysa* o veri önbellektedir (yani biri yakın zamanda ona dokunmuştur); *yavaşsa* önbellekte değildir.

Önbellek paylaşımlı bir kaynaktır. Aynı fiziksel çekirdeği veya paylaşımlı son-seviye önbelleği (LLC, Last Level Cache) kullanan iki süreç, birbirinin bıraktığı izleri görebilir. Kurban bir işlem, gizli veriye bağlı olarak farklı bellek adreslerine erişiyorsa, saldırgan hangi cache line'ların "sıcak" olduğunu ölçerek bu gizli erişim örüntüsünü çıkarabilir.

### Tipik Örüntüler

Literatürde adı geçen başlıca teknikler kavramsal olarak şöyledir:

- **Flush+Reload:** Saldırgan, kurbanla paylaşılan bir bellek bölgesini (örneğin ortak bir kütüphane) önbellekten atar (flush), kurbanın çalışmasını bekler, sonra tekrar erişerek süreyi ölçer. Hızlıysa kurban o bölgeye erişmiştir. Bu, en yüksek çözünürlüklü tekniklerden biridir ve paylaşımlı bellek gerektirir.
- **Prime+Probe:** Paylaşımlı bellek gerektirmez. Saldırgan önbelleğin belirli kümelerini (cache set) kendi verisiyle doldurur (prime), kurbanı bekler, sonra kendi verisine tekrar erişerek hangi satırlarının atıldığını (evict edildiğini) ölçer. Atılan satırlar, kurbanın o kümeyi kullandığını gösterir.
- **Evict+Time, Cache Collision** gibi başka varyantlar da vardır.

Bu tekniklerin klasik hedefi, tablo-tabanlı (table-based) kriptografik uygulamalardır; örneğin AES'in erken yazılım uygulamalarında, S-box tablosuna erişim indeksleri gizli anahtara bağlıydı ve cache erişim örüntüsü anahtar bitlerini sızdırıyordu.

### Kök Neden Vurgusu

Cache timing'in kökü, **paylaşımlı, veriye-bağlı-durumlu bir kaynağın (önbellek) süreçler arasında izole olmamasıdır**. Önbellek, tasarım gereği performans için paylaşılır; güvenlik için değil.

## Spekülatif Yürütme ve Spectre / Meltdown

### Arka Plan: Spekülatif ve Sıra-Dışı Yürütme

Modern yüksek performanslı CPU'lar, komutları program sırasına göre teker teker beklemez. Bir dal (branch) komutunun sonucu henüz belli değilken, **dal tahmincisi (branch predictor)** hangi yolun izleneceğini tahmin eder ve o yolu **spekülatif olarak (speculatively)** yürütmeye başlar. Tahmin doğruysa, iş çoktan bitmiştir ve performans kazanılır. Tahmin yanlışsa, spekülatif sonuçlar **mimari durumdan (architectural state)** geri alınır; yani register'lar ve bellek, sanki o komutlar hiç çalışmamış gibi görünür.

Kritik nokta şudur: Bu geri alma **mimari** düzeyde yapılır, ama **mikromimari** düzeyde iz bırakır. Spekülatif yürütme sırasında bir bellek adresine erişildiyse, o veri önbelleğe alınmıştır ve geri alma bu önbellek durumunu temizlemez. İşte Spectre ve Meltdown bu boşluğu kullanır.

### Meltdown: İzolasyon İhlali

**Meltdown**, kabaca şu prensibe dayanır: Bazı işlemcilerde, yetkisiz bir erişim (örneğin kullanıcı modundaki bir kodun çekirdek belleğine erişmesi) bir istisna (exception/fault) doğursa bile, o istisna *emekliye ayrılmadan* (retire olmadan) önce, spekülatif olarak devam eden komutlar yasak veriyi geçici olarak okuyup, onu bir yan kanala (tipik olarak cache) kodlayabilir. İstisna sonradan işlenip erişim iptal edilse de, veri zaten önbellek durumuna sızdırılmıştır. Saldırgan sonra Flush+Reload gibi bir teknikle bu değeri geri okur.

Meltdown'ın ciddiyeti, kullanıcı-çekirdek izolasyonunu delmesiydi; ilkesel olarak tüm çekirdek belleğinin (ve dolayısıyla fiziksel belleğin büyük kısmının) okunmasına imkân verebiliyordu. Başlıca yazılım savunması **KPTI / KAISER (Kernel Page-Table Isolation)** oldu: çekirdek sayfa tablolarını kullanıcı adres uzayından ayırarak, kullanıcı modunda çekirdek eşlemelerinin büyük kısmını görünmez kılmak. Bunun bir performans maliyeti vardır çünkü sistem çağrılarında adres uzayı geçişleri (TLB flush) artar.

### Spectre: Kurbana Kendi Verisini Sızdırtmak

**Spectre**, Meltdown'dan daha temel ve daha zor giderilir bir sınıftır. Meltdown izolasyon sınırını doğrudan delerken, Spectre kurban sürecin *kendi* koduna, spekülatif olarak "yapmaması gereken" bir işi yaptırır ve sonucu yan kanala sızdırır.

İki klasik varyant kavramsal olarak şöyledir:

- **Variant 1 — Bounds Check Bypass:** Bir kodda `if (x < dizi_boyutu) { y = dizi[x]; ... }` gibi bir sınır denetimi düşünün. Dal tahmincisi, sınır denetiminin "geçeceğini" tahmin edecek şekilde eğitilirse, saldırgan `x` değerini sınır dışına taşıdığında CPU spekülatif olarak `dizi[x]`'i (sınır dışı, gizli bir bellek) okur ve onu ikinci bir spekülatif erişimin adres örüntüsüne kodlar. Denetim sonradan başarısız olup spekülasyon geri alınsa da, cache izi kalır.
- **Variant 2 — Branch Target Injection:** Saldırgan, dolaylı dal tahmincisini (indirect branch predictor) zehirleyerek, kurbanın dolaylı bir çağrısının spekülatif olarak saldırganın seçtiği bir "gadget"a yönelmesini sağlar. Bu gadget, gizli veriyi yine yan kanala kodlar.

### Kök Neden Vurgusu

Spectre'ın kökü çok derindir: **Spekülatif yürütme, mimari düzeyde güvenlik sınırlarını sayan, ama mikromimari düzeyde bu sınırları saymayan bir mekanizmadır.** Yani CPU, "bu erişim aslında yapılmamalıydı" bilgisini geç fark eder ve bu ara pencerede sızıntı zaten olmuştur. Bu yüzden Spectre tek bir yazılım yamasıyla tam kapanmaz; kısmen donanım tasarımı, kısmen derleyici, kısmen işletim sistemi düzeyinde katmanlı azaltmalar (mitigation) gerektirir.

### Spectre/Meltdown Savunma Katmanları

- **Donanım/mikrokod:** Üreticiler mikrokod güncellemeleriyle spekülasyon davranışını sınırlayan kontroller ve yeni dal tahmincisi bariyerleri ekledi. Yeni nesil çekirdekler bazı varyantlara karşı donanımda dirençlidir.
- **Derleyici azaltmaları:** Örneğin **retpoline**, dolaylı dalları, tahmincinin zehirlenmesini engelleyen bir dönüş-tabanlı yapıya çevirir (Variant 2'ye karşı). **Spekülasyon bariyerleri** (örneğin `lfence` benzeri serialize edici komutlar) hassas sınır denetimlerinden sonra spekülasyonu durdurmak için kullanılır (Variant 1'e karşı).
- **İşletim sistemi:** KPTI (Meltdown), süreç izolasyonu, aynı çekirdekte güvensiz iş yüklerini birlikte çalıştırmaktan kaçınma.
- **Tarayıcı düzeyi:** Web tarayıcıları, JavaScript'ten Spectre'ı zorlaştırmak için zamanlayıcı çözünürlüğünü düşürdü (`performance.now` hassasiyetini azalttı), `SharedArrayBuffer`'ı geçici olarak kısıtladı ve **site izolasyonu (site isolation)** ile farklı kökenleri (origin) ayrı süreçlere yerleştirdi.

Not: Spectre/Meltdown'ın çok sayıda türevi (Foreshadow/L1TF, MDS/ZombieLoad, RIDL, Fallout gibi) zamanla ortaya çıktı. Bunların hepsi "spekülatif/geçici (transient) yürütme, mikromimari tampon veya durum üzerinden veri sızdırır" çekirdek fikrinin farklı yüzeylerini kullanır. Kesin varyant isimlerini ve etkilenen tam işlemci modellerini burada tek tek listelemek yerine mekanizmayı vurguluyorum; belirli bir sistemin etkilenip etkilenmediği üreticinin resmî güvenlik bildirimlerinden doğrulanmalıdır.

## Rowhammer: DRAM Bit-Flip Saldırısı

### Tanım

**Rowhammer**, yan kanal ailesinden biraz farklı bir sınıftır; burada saldırgan yalnızca *okuma* yapmaz, DRAM'in fiziksel bir zayıflığını kullanarak *dokunmadığı* bellek bitlerini **değiştirir (bit-flip)**. Bu, gizlilik değil doğrudan bütünlük (integrity) ihlalidir.

### Kök Neden / Çalışma Mantığı

DRAM hücreleri, bir kapasitörde tutulan yük ile bit değeri saklar. Bellek yoğunluğu arttıkça hücreler birbirine çok yaklaştı. Bir DRAM satırına (row) çok hızlı ve tekrar tekrar erişildiğinde, elektriksel girişim komşu satırlardaki hücrelerin yükünü sızdırır. Yeterince "çekiçlenirse" (hammer), komşu satırdaki bir bit, yenileme (refresh) periyodundan önce değerini değiştirebilir; yani `1` iken `0`, ya da tersi olur.

Kritik nokta: Saldırgan yalnızca *kendi* eriştiği satırlara vurur, ama bit-flip *başka bir bellek satırında*, potansiyel olarak başka bir sürecin veya çekirdeğin verisinde gerçekleşir. Bu yüzden bir bellek izolasyonu ihlalidir.

### Sömürü Senaryoları (Kavramsal)

Bit-flip rastgele görünse de, saldırgan bellek düzenini (memory massaging / "spraying") manipüle ederek, kritik bir yapıyı çevrilebilir bir bitin komşuluğuna yerleştirebilir. Klasik kavramsal hedefler:

- **Sayfa tablosu girdileri (page table entries):** Bir işaretçi bitinin çevrilmesi, saldırganın kendi sayfasını başka bir fiziksel çerçeveye eşlemesini sağlayarak ayrıcalık yükseltmeye (privilege escalation) yol açabilir.
- **Yetki/karar bitleri:** Bir "root mu?" bayrağı ya da bir imza doğrulama sonucu gibi hassas bir bitin çevrilmesi.

**Rowhammer.js** gibi çalışmalar, saldırının teoride tarayıcıdan JavaScript ile bile tetiklenebileceğini gösterdi. **ECC belleğin (Error-Correcting Code)** tek-bit hataları düzelttiği için savunma sağladığı düşünülürdü, ancak çok-bit flip'lerle ECC'nin de aşılabileceğini gösteren çalışmalar (ECCploit türü) çıktı; yani ECC yardımcıdır ama mutlak koruma değildir.

### Savunma

- **TRR (Target Row Refresh)** ve benzeri donanım azaltmaları: Sık erişilen satırların komşularını erken yenileyerek yükün boşalmasını önlemeye çalışır. Ancak bazı gelişmiş çok-yönlü çekiçleme (many-sided hammering) teknikleri bunu da atlatabilmiştir; bu bir kedi-fare yarışıdır.
- **DDR nesil iyileştirmeleri:** Yeni bellek standartları daha güçlü satır yenileme yönetimi getirir, ama yoğunluk arttıkça baskı da artar.
- **ECC bellek:** Tek-bit hataları düzeltir, çok-bitte tespit sağlayabilir; savunmayı derinleştirir ama tek başına yeterli sayılmamalı.
- **Fiziksel/bellek düzeni önlemleri:** Hassas yapıları saldırgan-kontrollü bellekten fiziksel olarak izole etmeye çalışan çekirdek teknikleri.
- **Yenileme aralığını sıkılaştırmak:** Daha sık DRAM refresh, çevrilme penceresini kısaltır ama güç ve performans maliyeti getirir.

## Tespit ve İzleme

Yan kanal saldırılarının tespiti zordur çünkü saldırgan çoğunlukla "yasal" işlemler (bellek okuma, zamanlama ölçme) yapar; imza-tabanlı klasik tespit çalışmaz. Yaklaşımlar davranışsaldır:

- **Donanım performans sayaçları (HPC / hardware performance counters):** Cache-miss oranı, LLC erişimleri ve dal-tahmini hatalarında olağandışı yükseklik, Flush+Reload veya Prime+Probe gibi tekniklerin karakteristik imzasını taşıyabilir. Bir sürecin anormal derecede yüksek cache-flush veya cache-miss aktivitesi göstermesi bir sinyal olabilir. Uyarı: Bu ölçümler gürültülüdür ve yanlış-pozitif (false positive) üretmeye eğilimlidir; iyi kalibre edilmeli.
- **Rowhammer için:** Aşırı yüksek, dar bir bellek bölgesine yönelik erişim yoğunluğu ve ECC hata sayaçlarında ani artış izlenebilir. ECC düzeltilebilir-hata (correctable error) loglarındaki ani yükseliş erken uyarıdır.
- **Yama/sürüm doğrulaması:** Sistemin ilgili mikrokod, çekirdek ve derleyici azaltmalarını taşıyıp taşımadığını doğrulamak, tespitten önce gelen en pratik "sağlık kontrolü"dür. Birçok işletim sistemi, aktif spekülatif-yürütme azaltmalarının durumunu raporlayan bir arayüz sunar; bu durum düzenli denetlenmelidir.
- **İzolasyon telemetrisi:** Bulut ortamlarında, komşu-kiracı (co-tenant) riskini azaltmak için hangi iş yüklerinin fiziksel çekirdek paylaştığının izlenmesi.

## Savunma Tasarımı: Özet İlkeler

1. **Sabit-zamanlı (constant-time) programlama:** Kriptografik kodda, gizli veriye bağlı dal alma ve gizli veriye bağlı bellek indeksleme yapılmamalıdır. Çalışma süresi ve erişim örüntüsü gizli veriden bağımsız olmalıdır. Bu, cache ve timing yan kanallarının büyük kısmını kaynağında keser.
2. **Kaynak izolasyonu:** Güvenlik sınırının iki tarafındaki iş yükleri, mümkünse aynı fiziksel çekirdeği (SMT/Hyper-Threading dâhil) paylaşmamalıdır. Yüksek güvenlik gereken ortamlarda SMT'nin kapatılması bir seçenektir.
3. **Katmanlı azaltma:** Spectre gibi mikromimari zafiyetlerde tek bir yamaya güvenilmez; mikrokod + çekirdek + derleyici + uygulama azaltmaları birlikte uygulanır.
4. **Güncel donanım ve firmware:** Mikrokod ve BIOS/UEFI güncellemeleri güvenlik yamasıdır, sadece performans değil.
5. **Derinlemesine savunma (defense in depth):** ECC bellek, site izolasyonu, düşük çözünürlüklü zamanlayıcılar gibi önlemlerin hiçbiri tek başına yeterli değildir; birlikte anlam kazanır.

## Yaygın Hatalar ve Yanlış Anlamalar

- **"Yazılımım güvenli, çünkü matematik doğru."** Yan kanallar matematiği değil *uygulamayı* hedefler. Doğru algoritma, sabit-zamanlı olmayan bir uygulamada bile anahtar sızdırabilir.
- **"Spectre için yamayı yükledim, bitti."** Spectre bir varyant ailesidir ve tek bir yama tüm yüzeyleri kapatmaz. Ayrıca bazı azaltmalar performans için varsayılan olarak kapalı olabilir; etkin olduklarını doğrulamak gerekir.
- **"Rowhammer'a karşı ECC yeter."** ECC savunmayı derinleştirir ama çok-bit flip'lerle aşılabildiği gösterilmiştir. Mutlak koruma değildir.
- **"Yan kanal saldırısı için fiziksel erişim şart."** Cache timing ve hatta Rowhammer'ın uzaktan/yerel-yazılım ile (bazı durumlarda tarayıcı içinden) tetiklenebildiği gösterilmiştir. Fiziksel erişim şart değildir.
- **"Azaltmaları kapatırsam yalnızca performans kazanırım."** Spekülatif-yürütme azaltmalarını kapatmak ölçülebilir güvenlik yüzeyi açar; bu bilinçli bir risk kararı olmalı, sessiz bir varsayılan değil.
- **"Zamanlayıcı hassasiyetini düşürmek saldırıyı tamamen engeller."** Zorlaştırır ama saldırganlar zamanlama gürültüsünü istatistiksel olarak azaltan (amplifikasyon, çok-tekrarlı ölçüm) teknikler geliştirmiştir. Yavaşlatma bir engel katmanıdır, kapı değil.
- **HPC-tabanlı tespite körü körüne güvenmek:** Performans sayaçları gürültülüdür; iyi kalibre edilmemiş bir eşik hem kaçırma (false negative) hem gereksiz alarm üretir.

## Sonuç

Mikromimari yan kanallar, güvenliğin en alt katmanında, performans için verilmiş donanım kararlarının içinde saklıdır. Spectre/Meltdown, "spekülatif yürütmenin mikromimari izleri geri alınmaz" gerçeğini; cache timing, "paylaşımlı önbellek veriye-bağlı zamanlama sızdırır" gerçeğini; Rowhammer ise "yoğun DRAM'de bir satıra vurmak komşu satırın bitini bozabilir" gerçeğini istismar eder. Ortak ders şudur: Bir soyutlama (izole süreç, gizli anahtar, ayrık bellek) yalnızca *mantıksal* olarak varsa ama *fiziksel/mikromimari* olarak sızıntı bırakıyorsa, o soyutlama tam güvenli değildir. Savunma; sabit-zamanlı kod, kaynak izolasyonu, katmanlı azaltma ve güncel firmware'in bir arada uygulanmasıyla, tek bir sihirli yama aramadan, derinlemesine kurulmalıdır.
