# Donanım Yan Kanal Saldırıları: Spectre/Meltdown, Cache Timing, Rowhammer

## Giriş: Neden Bu Konu Kendi Başlığını Hak Ediyor

Yazılım güvenliği literatürünün çoğu, "doğru mantık yanlış yazılmıştır" varsayımıyla ilerler: buffer overflow, use-after-free, SQL injection — hepsi bir programın *belirtilen davranışından* sapmasıdır. Donanım yan kanal saldırıları (hardware side-channel attacks) farklı bir kategoridir: program mantıksal olarak %100 doğru çalışır, giriş/çıkış davranışı belgelendiği gibidir, ama CPU'nun performans için yaptığı optimizasyonlar (spekülatif çalıştırma, önbellekleme, DRAM yenileme döngüleri) gözlemlenebilir yan etkiler bırakır. Bu yan etkiler — bir işlemin ne kadar sürdüğü, hangi bellek adresinin önbellekte olduğu, hangi DRAM satırının kaç kez erişildiği — kendileri birer bilgi kanalı hâline gelir.

Bu sınıfın ayrı bir başlığı hak etmesinin nedeni şudur: mevcut güvenlik modelinizin (bellek izolasyonu, process sandboxing, kernel/user ayrımı, sanal makine izolasyonu) *tamamı*, "farklı güvenlik alanları birbirinin belleğine mantıksal olarak erişemez" varsayımına dayanır. Spectre/Meltdown bu varsayımı mikromimari seviyede delip geçer: mantıksal erişim kontrolü hâlâ çalışıyor olsa bile, spekülatif olarak okunan veri önbellek durumuna sızar ve oradan zamanlama farkıyla dışarı çıkarılabilir. Rowhammer ise erişim kontrolünü bile atlar — fiziksel DRAM hücrelerini elektriksel olarak bozarak, izin kontrolünün hiç devreye girmediği bir bit-flip üretir. Bu saldırılar "Bellek Yerlesimi" ve "Exploit Mitigations" başlıklarıyla kesişir ama onlardan farklıdır: onlar yazılımın bellek modelini konu alır, burada konu CPU'nun *fiziksel gerçekleştirimidir*. Savunma ekibi bu ayrımı bilmezse, "ASLR + DEP + stack canary yeterli" yanılgısına düşer — hâlbuki bu üç mekanizmanın hiçbiri mikromimari sızıntıya karşı koruma sağlamaz.

## Kavramsal Temel: Yan Kanal Nedir

Bir yan kanal (side channel), bir sistemin *amaçlanan* çıktısı dışında, fiziksel gerçekleştirimin kaçınılmaz yan ürünü olarak sızdırdığı bilgi kanalıdır. Klasik örnekler: bir akıllı kartın şifreleme sırasında çektiği akımın gücü (power analysis), bir donanımın elektromanyetik yayılımı (EM analysis), bir işlemin ne kadar sürdüğü (timing analysis). CPU dünyasında en pratik ve uzaktan sömürülebilir olan yan kanal **zamanlamadır**: önbellekte olan bir veriye erişim nanosaniyeler sürer, önbellekte olmayana (DRAM'e gitmesi gerekeni) yüzlerce nanosaniye sürer. Bu fark, saldırganın "gizli bir bit sıfır mı bir mi" sorusunu, "bu erişim hızlı mı yavaş mı" sorusuna indirgemesini sağlar — ve zaman ölçmek, izin sistemi tarafından engellenemeyen bir işlemdir.

## Cache Timing Saldırıları: Temel Mekanizma

### Kök Neden

CPU önbelleği (L1/L2/L3), sınırlı miktarda hızlı SRAM'i tüm proseslerin paylaştığı bir kaynaktır. Paylaşım, yalıtım (isolation) ile çelişir: iki farklı güvenlik alanı (örneğin şifreleme yapan bir proses ile saldırgan proses) aynı fiziksel önbellek donanımını kullanıyorsa, birinin önbellek üzerindeki etkisi diğeri tarafından *dolaylı olarak* gözlemlenebilir. Önbellek, adres uzayına göre izole edilmiş bir kaynak değildir — fiziksel adrese ve önbellek setine (cache set) göre paylaşılan bir kaynaktır.

### Nasıl Çalışır: Flush+Reload ve Prime+Probe

**Flush+Reload**: Saldırgan ve kurban aynı fiziksel belleği (örneğin paylaşılan bir kütüphane sayfası — shared library) kullanıyorsa, saldırgan şu döngüyü kurar:
1. Hedef bellek satırını önbellekten temizle (`clflush` benzeri bir talimatla).
2. Kurbanın çalışmasını bekle (kurban, gizli veriye bağlı olarak bu satıra erişir veya erişmez).
3. Aynı satıra kendisi erişip süresini ölç. Hızlıysa kurban o satıra dokunmuştur (önbellekte kalmış); yavaşsa dokunmamıştır.

Bu teknik, örneğin bir AES şifreleme uygulamasının "T-table" arama tablosuna hangi indeksle eriştiğini —ki bu indeks genellikle anahtarın bir fonksiyonudur— dışarıdan çıkarmayı mümkün kılar.

**Prime+Probe**: Paylaşılan bellek gerektirmez, bu yüzden daha genel ve daha tehlikelidir. Saldırgan önce önbelleğin bir setini kendi verisiyle doldurur (prime). Kurban çalışır. Saldırgan aynı seti tekrar okuyup hangi girdilerinin (kendi verisinin) hâlâ önbellekte olduğunu ölçer (probe). Kurbanın hangi setlere dokunduğunu, kendi verisinin o setlerden atılmış olmasından (eviction) çıkarır. Bu, saldırgan ile kurbanın aynı belleği paylaşmasını gerektirmediği için bulut/sanal makine ortamlarında komşu kiracılar (co-tenant) arasında bile uygulanabilir — VM izolasyonunu mikromimari seviyede delen klasik bir senaryodur.

### Neden Önemli

Cache timing, kriptografik anahtar çıkarma (AES, RSA, ECDSA implementasyonlarına karşı), KASLR (kernel address space layout randomization) atlatma ve Spectre gibi spekülatif çalıştırma saldırılarının **çıkış kanalı** olarak kullanılır. Yani cache timing kendi başına bir saldırı sınıfıdır, ama aynı zamanda Spectre/Meltdown'un "gizli veriyi dışarı taşıma" mekanizmasının temelidir — bu ikisini birbirinden ayrı ama iç içe geçmiş olarak anlamak gerekir.

## Spekülatif Çalıştırma: Meltdown ve Spectre

### Kök Neden — Neden Modern CPU'lar Spekülatif Çalışır

Modern CPU'lar tek komutu bitirip sıradakine geçmez; performans için **out-of-order execution** ve **speculative execution** kullanır. Bir dallanma (branch) talimatına (if/else) geldiğinde, CPU sonucu henüz bilmeden (koşul hesaplanmadan) en olası dalı *tahmin ederek* çalıştırmaya başlar (branch prediction). Tahmin doğruysa büyük hız kazancı olur; yanlışsa, CPU spekülatif olarak yaptığı işlemleri "geri alır" (mimari durumu — register, bellek — eski haline döner). Buradaki kritik hata varsayımı şudur: "geri alma" mimari durumu tam olarak eski haline getirir, ama **mikromimari durumu** (önbellek içeriği) geri almaz. Spekülatif olarak okunan bir bellek adresi, yanlış tahmin sonucu iptal edilse bile önbellekte iz bırakmış olur. İşte tüm sınıfın kök nedeni budur: mimari geri alma (architectural rollback) ile mikromimari geri alma (microarchitectural rollback) arasındaki asimetri.

### Meltdown: Ayrıcalık Kontrolünün Sıralaması

Meltdown'da sorun şudur: CPU, bir bellek okuma talimatını spekülatif olarak *önce çalıştırır*, ayrıcalık kontrolünü (bu adrese erişim izniniz var mı) *sonra* yapar. Kullanıcı modunda çalışan bir kod, kernel belleğine ait bir adresi okumaya çalıştığında:
1. CPU spekülatif olarak o adresteki veriyi okur (henüz izin kontrolü tamamlanmamıştır).
2. Okunan gizli baytı kullanarak, kendi adres uzayında bir diziyi indeksler (`array[gizli_bayt * 4096]`), bu da o dizinin belirli bir sayfasını önbelleğe yükler.
3. İzin kontrolü tamamlanır, istisna (exception) fırlatılır, spekülatif sonuç mimari olarak iptal edilir — register'a gizli bayt hiçbir zaman "yazılmış" görünmez.
4. Ama önbellekte iz kalmıştır. Saldırgan, diziyi Flush+Reload ile tarayarak hangi sayfanın önbellekte olduğunu bulur — bu da gizli baytın değerini verir.

Bu adım adım bayt-bayt tüm kernel belleğini (ya da başka bir sürecin belleğini) okumayı mümkün kılar. Meltdown esasen bir "sıralama hatasıdır": kontrol/veri erişimi sırası ters.

### Spectre: Dal Tahmininin Kötüye Kullanımı

Spectre ailesi daha temel ve daha zor kapatılabilir bir sorunu hedefler: CPU'yu *yanlış* bir dalı çalıştırmaya ikna etmek. Klasik örnek (Spectre v1 — bounds check bypass):

```
if (x < array1_length) {
    y = array2[array1[x] * 4096];
}
```

Saldırgan önce CPU'nun dal tahmincisini (branch predictor) `x < array1_length` koşulunun genelde doğru olduğuna "eğitir" (defalarca geçerli x değerleriyle çağırarak). Sonra sınır dışı bir `x` değeri verir. CPU, tahminine güvenerek sınır kontrolü sonucu gelmeden `array1[x]`'i spekülatif olarak okur — bu, saldırganın seçtiği adres uzayının herhangi bir yerinden (sınır kontrolü henüz doğrulanmadığı için) bir bayt okumak demektir. Bu bayt `array2` içindeki bir indeksleme için kullanılır, önbellekte iz bırakır, sınır kontrolü nihayet başarısız olduğunda spekülasyon iptal edilir ama iz kalır. Saldırgan Flush+Reload ile `array2`'yi tarar.

Spectre v2 (branch target injection) benzer mantığı dolaylı dallanmalara (indirect branch/jump — sanal fonksiyon çağrıları, switch-case tabloları) uygular: saldırgan, dal hedef tahmincisini (Branch Target Buffer) kendi seçtiği bir adrese işaret edecek şekilde zehirler, kurban kod dolaylı bir sıçrama yaptığında CPU spekülatif olarak saldırganın seçtiği "gadget" koduna sıçrar.

### Meltdown ile Spectre Arasındaki Fark — Neden İkisi Ayrı

Meltdown, ayrıcalık kontrolü ile veri erişiminin *sırasını* istismar eder ve esasen belirli CPU mimarilerine (özellikle erken Intel çekirdekleri) özgü bir tasarım hatasıdır; mikrokod/donanım güncellemeleriyle veya KPTI (Kernel Page Table Isolation) gibi yazılım geçici çözümleriyle kapatılabilmiştir. Spectre ise dal tahmininin *kendisinin* doğasında olan bir sorundur — tahmin yapmak performansın özüdür, tahmin yapmayı tamamen kaldırmak CPU'yu anlamsız derecede yavaşlatır. Bu yüzden Spectre varyantları (v1, v2, ve sonraki türevler — SSB/Spectre v4, MDS ailesi gibi ilişkili sızıntılar) yıllar içinde tekrar tekrar ortaya çıkmıştır: her düzeltme belirli bir gadget desenini kapatır, ama "spekülasyon + ölçülebilir yan etki" temel deseni CPU mimarisinin ta kendisidir.

## Rowhammer: Yazılım Değil, Fizik Sorunu

### Kök Neden

DRAM, veriyi kapasitörlerde elektrik yükü olarak saklar; her hücre periyodik olarak "yenilenir" (refresh) çünkü yük zamanla sızar. DRAM yoğunluğu arttıkça (daha küçük hücreler, daha az fiziksel ayrım), komşu satırlara yapılan çok sık ve tekrarlı erişim (aktivasyon), elektriksel parazit (crosstalk / voltage coupling) yoluyla komşu satırdaki hücrelerin yükünü bozabilir — bit yenileme süresinden önce sızacak kadar. Sonuç: hiçbir mantıksal erişim izni ihlal edilmeden, saf donanım fiziği yoluyla, saldırganın *hiç erişme yetkisi olmayan* bir bellek adresindeki bit değeri değişir (0→1 veya 1→0).

### Nasıl Çalışır

Saldırgan kendi erişebildiği (izinli) iki DRAM satırını ("saldırgan satırlar" — aggressor rows) art arda, önbelleği atlayarak (`clflush` + tekrar erişim döngüsü, ya da önbellek atlatma teknikleri) yüksek frekansta okur/yazar. Bu iki satır arasındaki "kurban satır" (victim row), her iki komşusundan gelen elektriksel etkiyle bit bozulmasına uğrayabilir. Saldırının inceliği burada: saldırgan kurban satırın *içeriğini* değil sadece *hangi fiziksel satır olduğunu* kontrol eder — bu yüzden Rowhammer genelde belirli bir bilgiyi okumak için değil, **ayrıcalık yükseltme** için kullanılır: örneğin bir sayfa tablosu girdisindeki (page table entry) bir biti çevirerek kendi sayfasını kernel belleğine işaret eder hâle getirmek, ya da bir genel anahtarın (public key) bir bitini bozarak zayıflatmak.

### Neden Önemli — Yazılım Savunmasının Sınırı

Rowhospitality açıkça gösterir ki bazı saldırılar *yazılım katmanının erişemeyeceği* bir seviyede yaşar. İşletim sistemi mükemmel bellek izolasyonu uygulasa bile, DRAM fiziksel olarak komşu hücrelere sızıntı yapıyorsa, izin kontrolü hiç devreye girmeden bit değişir. Bu nedenle Rowhammer savunması büyük ölçüde donanım seviyesindedir: **TRR (Target Row Refresh)**, DRAM'in şüpheli sıklıkta erişilen satırları tespit edip komşularını erken yenilemesi; **ECC (Error-Correcting Code) bellek**, tek bit hatalarını düzeltip çift bit hatalarını tespit etmesi (ama ECC'nin de sınırları vardır — çoklu bit flip senaryoları ECC'yi de aşabilir); DDR4/DDR5'te yenileme aralıklarının sıkılaştırılması.

## Tespit ve Savunma: Katman Katman

### Donanım/Mikrokod Seviyesi
- **Spekülatif yürütme baraları**: `LFENCE` gibi talimatlar, CPU'ya belirli bir noktadan önceki talimatların spekülatif çalıştırılmasını durdurmasını söyler. Derleyiciler (compiler), potansiyel Spectre gadget'larının (özellikle sınır kontrolünden hemen sonraki dizi erişimleri) etrafına otomatik olarak bu bariyerleri ekleyebilir.
- **IBRS/IBPB/STIBP** (Indirect Branch Restricted Speculation ve ilişkili mikrokod kontrolleri): dolaylı dal tahmininin güvenlik sınırları arasında (kullanıcı/kernel, VM/host) sızmasını sınırlayan CPU mikrokod özellikleri.
- **KPTI (Kernel Page Table Isolation)**: Meltdown'a karşı, kullanıcı modu çalışırken kernel sayfa tablolarının büyük kısmının haritalanmamış olmasını sağlar — spekülatif okunacak bir kernel adresi yoksa sızdırılacak bir şey de yoktur. Bedeli: her sistem çağrısında (syscall) sayfa tablosu değişimi, ölçülebilir performans kaybı.
- **TRR / gelişmiş DRAM yenileme**: Rowhammer'a karşı donanım seviyesi savunma.

### İşletim Sistemi / Hipervizör Seviyesi
- Süreçler arası ve VM'ler arası **önbellek bölümlemesi (cache partitioning)** veya Intel CAT (Cache Allocation Technology) gibi mekanizmalarla paylaşılan önbelleğin izole edilmesi — Prime+Probe'un temel önkoşulunu (paylaşılan kaynak) zayıflatır.
- Yüksek çözünürlüklü zamanlayıcılara (`rdtsc` benzeri talimatlar) tarayıcı/sandbox içinden erişimin kısıtlanması veya çözünürlüğünün düşürülmesi (timing side channel'ın "ölçüm aracını" körelt) — tarayıcı üreticilerinin Spectre sonrası JavaScript zamanlayıcı hassasiyetini kasıtlı olarak düşürmesi bu yaklaşımın örneğidir.
- Sayfa tablosu izolasyonu (KPTI) ve süreçler arası bellek paylaşımının (özellikle salt-okunur paylaşılan kütüphaneler dışında) en aza indirilmesi.

### Derleyici / Yazılım Seviyesi
- **Speculative load hardening**: derleyicinin, güvenlik sınırı geçen kontrol akışlarına (özellikle sınır kontrollerine) spekülasyonu kesen talimatlar (`LFENCE` ya da adres maskeleme) eklemesi.
- Kriptografik kod için **sabit zamanlı (constant-time) implementasyon**: gizli veriye bağlı dallanma veya gizli veriye bağlı bellek erişim deseni olmayan algoritma yazımı — cache timing saldırılarının ön koşulunu (veriye bağlı erişim deseni) ortadan kaldırır. Bu, "yaygın hata" bölümünde detaylandırılacak en kritik savunmacı disiplindir.

### Tespit
Bu saldırı sınıfının tespiti klasik imza tabanlı (signature-based) yöntemlerle zordur çünkü saldırı, tamamen meşru CPU talimatlarının (bellek okuma, dallanma, zamanlayıcı okuma) olağan kullanımından oluşur — kötü niyetli bir "imza" yoktur. Pratik tespit yaklaşımları:
- **Performans sayaçları (Hardware Performance Counters / PMU)** izleme: anormal derecede yüksek önbellek kaçırma oranı (cache miss rate), anormal dal yanlış tahmin oranı (branch misprediction rate) veya olağandışı yüksek bellek aktivasyon frekansı (Rowhammer belirtisi), bir saldırının yürütüldüğüne dair istatistiksel sinyal olabilir.
- Rowhammer'a özgü olarak: belleğe anormal derecede yüksek frekansta erişim yapan (özellikle `clflush` ile önbelleği bypass eden) süreçlerin izlenmesi.
- Genel prensip: bu saldırılar *davranışsal anomali* olarak görünür, *kod imzası* olarak değil — savunma ekibinin zihniyeti antivirüsten çok anomali tespiti (anomaly detection) yönünde olmalıdır.

## Yaygın Hatalar ve Tuzaklar

**Hata 1 — "Mikrokod yaması aldık, iş bitti" yanılgısı.** Spectre ailesi tek bir CVE değil, sürekli genişleyen bir *desen ailesidir*. Her yama belirli bir gadget sınıfını kapatır; yeni mikromimari optimizasyon her tanıtıldığında (yeni önbellek seviyesi, yeni tahmin mekanizması) potansiyel olarak yeni bir varyant doğar. Savunma "bir kez yama, sonsuza dek güvenli" değil, sürekli izlenmesi gereken bir kategori olarak ele alınmalıdır.

**Hata 2 — Performans/güvenlik dengesini görmezden gelmek.** KPTI, IBRS gibi geçici çözümlerin gerçek ve bazen büyük performans maliyeti vardır (özellikle sistem çağrısı yoğun iş yüklerinde). Kör bir şekilde "tüm mitigasyonları aç" yaklaşımı, üretim sistemlerinde kabul edilemez yavaşlamaya yol açabilir. Doğru yaklaşım, tehdit modeline göre önceliklendirmedir: paylaşımlı/çok kiracılı (multi-tenant) ortamlarda (bulut, tarayıcı) mitigasyonlar kritik; tek kullanıcılı, izole, güvenilir kod çalıştıran sistemlerde bazı mitigasyonlar gereksiz maliyet olabilir.

**Hata 3 — Kriptografik kodun "doğru sonucu üretiyor" diye güvenli sanılması.** Fonksiyonel doğruluk (correctness) ile yan-kanal güvenliği (side-channel security) ayrı eksenlerdir. Anahtara bağlı dallanma yapan veya anahtara bağlı indeksle bellek erişen bir AES/RSA implementasyonu, test vektörlerini mükemmel geçer ama cache timing ile anahtarı sızdırabilir. Savunmacı disiplin: kriptografik kod için sabit-zamanlı, veri-bağımsız-erişim (data-independent memory access) prensipleri zorunlu tutulmalı, statik analiz araçlarıyla doğrulanmalıdır.

**Hata 4 — Rowhammer'ı "sadece donanım sorunu, yazılımı ilgilendirmez" diye göz ardı etmek.** ECC bellek veya TRR olmayan sistemlerde (özellikle bazı mobil cihazlar, eski/ucuz DRAM), yazılım seviyesinde de azaltıcı önlemler mümkündür: bellek ayırıcının (allocator) güvenlik-kritik verileri (sayfa tabloları gibi) rastgele/tahmin edilemez konumlara yerleştirmesi, ya da "güvenli satırlar" (guard rows) bırakarak saldırgan-kurban satır bitişikliğini kırması. "Bu donanımın işi" demek, mevcut donanımda zaten çalışan sistemlerin savunmasız kalmasına neden olur.

**Hata 5 — Sanal makine/konteyner izolasyonunu mutlak sanmak.** Bulut ortamlarında "farklı müşteriler farklı VM'lerde, birbirlerini göremezler" varsayımı, mikromimari seviyede yanlıştır: aynı fiziksel CPU çekirdeğini veya aynı LLC (Last Level Cache) dilimini paylaşan VM'ler arasında Prime+Probe teorik olarak uygulanabilir. Yüksek güvenlik gerektiren iş yükleri için "aynı fiziksel çekirdek/soket paylaşımını engelleyen" (dedicated host, CPU pinning) yapılandırmalar değerlendirilmelidir.

## Sonuç: Savunmacı Zihniyeti

Bu saldırı sınıfını anlamanın pratik değeri şudur: mantıksal erişim kontrolü ("bu kullanıcı bu belleği okuyamaz") ile fiziksel/mikromimari gerçeklik ("bu CPU'nun önbelleği ve DRAM'i bu erişim kontrolünden habersiz paylaşılan bir kaynaktır") arasındaki uçurumu görmek. Savunma tek bir yamayla kapanmaz; katmanlı bir yaklaşım gerekir: donanım/mikrokod güncellemeleri, işletim sistemi/hipervizör izolasyonu, derleyici destekli sabit-zamanlı kod, ve sürekli performans-sayacı tabanlı anomali izleme. Bir mühendisin çıkarması gereken temel ders: "doğru çalışan kod" ile "güvenli kod" farklı şeylerdir, ve bu fark en çarpıcı biçimde donanımın performans için yaptığı optimizasyonların sızdırdığı yan kanallarda ortaya çıkar.
