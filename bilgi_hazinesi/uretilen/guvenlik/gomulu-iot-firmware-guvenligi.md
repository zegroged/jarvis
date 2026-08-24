# Gömülü/IoT Firmware Güvenliği

## Giriş ve Kapsam

IoT ve gömülü sistem güvenliği, klasik web veya Windows/Linux sunucu güvenliğinden köklü biçimde farklıdır: saldırgan çoğu zaman hedef cihaza fiziksel olarak erişebilir. Bu tek fark, tehdit modelini baştan sona değiştirir. Bir web uygulamasında saldırgan HTTP isteği gönderir; bir IoT cihazında saldırgan devre kartını sökebilir, çipin bacaklarına lehim yapabilir, flash belleği programlayıcıya takıp doğrudan okuyabilir. Bu nedenle IoT güvenliğinin temel disiplinleri şunlardır: **firmware extraction** (yazılımı cihazdan çıkarma), **donanım arayüzleri** (UART/JTAG/SWD) üzerinden erişim, **bootloader ve secure boot / chain-of-trust** mekanizmalarının çalışma mantığı ve bunların atlatılma yolları, ve bu ikisini birbirine bağlayan **firmware analiz araçları** (binwalk, firmadyne, QEMU tabanlı emülasyon).

Bu makalenin amacı bir "saldırı kılavuzu" değil, bir **mekanizma anlayışı** kazandırmaktır: bu katmanların neden bu şekilde tasarlandığını, hangi varsayımların kırıldığında güvenliğin çöktüğünü ve bir mühendisin/savunmacının bunlara karşı ne yapabileceğini anlamak. ICS/OT güvenliğinden (SCADA protokolleri, Modbus/DNP3 gibi endüstriyel protokoller) farklı olarak burada odak, cihazın kendisinin (router, kamera, akıllı ev cihazı, endüstriyel sensör, araç ECU'su vb.) donanım ve firmware katmanındaki güvenliğidir.

## Firmware Extraction (Yazılımı Çıkarma)

### Kök Neden / Kavramsal Temel

Bir gömülü cihazın "beyni" flash bellekte (NOR, NAND, eMMC, SPI flash) saklanan bir imajdır: bootloader, çekirdek (genellikle Linux), root dosya sistemi ve uygulama katmanı. Bu imajı elde etmek isteyen bir araştırmacı veya saldırgan için üç temel yol vardır:

1. **Yazılımsal (remote/logical) çıkarma**: Cihazın kendi güncelleme mekanizması, bir yönetim arayüzü veya debug servisi (telnet, özel bir protokol) üzerinden firmware imajını indirmek. Üreticinin web sitesinde yayınlanan güncelleme dosyalarını indirmek de bu kategoriye girer ve genellikle en kolay, en az riskli yoldur.
2. **Donanımsal doğrudan okuma (chip-off)**: Flash çipin fiziksel olarak sökülüp bir programlayıcıya (ör. bir SPI/NAND programlayıcı) takılarak ham veri okunması. Bu yöntem yazılımsal korumaları (kilitlenmiş bootloader, kapalı debug arayüzü) devreden çıkarır çünkü veri, çalışan sistemin kontrolü hiç devreye girmeden okunur.
3. **In-circuit (yerinde) okuma**: Çip sökülmeden, kartın üzerindeyken SPI/I2C hatlarına iğne veya klips ile bağlanıp flash'ın içeriğinin okunması. Chip-off kadar tahribatlı değildir ama elektriksel gürültü ve çakışan devre elemanları nedeniyle daha kırılgandır.

**Neden bu üç yol var?** Çünkü üreticiler farklı tehdit modelleri öngörür. Tüketici IoT cihazlarında (ucuz kameralar, router'lar) genellikle donanım koruması minimaldir çünkü maliyet baskısı vardır — chip-off veya in-circuit okuma çoğu zaman trivyaldir. Kurumsal/askeri sınıf cihazlarda ise epoksi kaplama, aktif tamper-detection, şifreli flash gibi önlemler bulunur çünkü tehdit modeli "saldırgan cihaza fiziksel erişebilir" varsayımını ciddiye alır.

### Nasıl Çalışır (Kavramsal)

Yazılımsal çıkarmada tipik akış: cihazın güncelleme dosyası (genellikle `.bin`, `.img` uzantılı) indirilir veya cihaz üzerinde bir zafiyet (ör. yetkisiz dosya okuma, komut enjeksiyonu) kullanılarak `/dev/mtd*` cihaz dosyaları `dd` benzeri bir araçla okunur ve dışarı çıkarılır. Donanımsal yolda ise flash çipin datasheet'i incelenir, pin-out çıkarılır, uygun voltaj ve protokol (SPI genelde 3.3V, NAND farklı komut setleri kullanır) ile bir programlayıcı bağlanır ve ham bayt dizisi bir dosyaya dökülür.

Elde edilen imaj çoğunlukla "tek parça" (monolitik) bir binary'dir; bootloader, kernel, dosya sistemi ve bazen kalibrasyon/konfigürasyon bölümleri art arda veya belirli offsetlerde birleştirilmiş haldedir. Bu yüzden çıkarmadan sonraki adım her zaman **ayrıştırma/analiz** olur (aşağıda binwalk bölümünde).

### Tespit

Cihaz tarafında fiziksel çıkarmayı "tespit etmek" çoğu zaman mümkün değildir çünkü işlem cihaz kapalıyken veya kontrol dışı gerçekleşir. Ancak dolaylı tespit imkânları vardır:
- **Tamper-evident/tamper-responsive donanım**: Kasa açılınca sıfırlanan anahtarlar (tamper switch), mesh sensörler; açılma girişimi loglanır veya anahtar materyali silinir (zeroization).
- **Kurumsal ortamda envanter ve fiziksel güvenlik telemetrisi**: Cihazın fiziksel olarak yerinden alındığına dair CCTV/erişim logları, saha operasyonlarında zincir-i emanet (chain of custody) kayıtları.
- **Sunucu tarafı anomali**: Çıkarılan firmware'den elde edilen kimlik bilgileriyle (gömülü API anahtarı, sertifika) daha sonra bulut servisine yapılan beklenmeyen kimlik doğrulama girişimleri izlenebilir — bu, saldırının "sonraki aşamasının" tespitidir, çıkarmanın kendisinin değil.

### Savunma

- **Gömülü sırları asla firmware'e düz metin gömmeme**: API anahtarları, özel TLS anahtarları, sabit kimlik bilgileri firmware imajında bulunmamalı; bunun yerine üretim sırasında cihaza özel, güvenli bir eleman (secure element/TPM benzeri) içinde üretilmeli.
- **Flash şifreleme**: Birçok modern SoC (system-on-chip), flash içeriğini çip içindeki bir anahtarla şifreleyip saklama (flash encryption) özelliği sunar; bu, chip-off ile ham veri alınsa bile anlamlı bilgiye erişimi zorlaştırır.
- **Debug/JTAG kilitleme üretimde**: Geliştirme sürecinde açık bırakılan debug portlarının seri üretim öncesi donanımsal veya e-fuse (bir kez yakılabilen bit) ile kalıcı olarak kapatılması.
- **Fiziksel tamper direnci**: Kasa tasarımı, epoksi kaplama, tamper-detect devreleri; maliyet-risk dengesine göre uygulanır.

### Yaygın Hatalar

- Firmware güncelleme dosyalarının imzasız/şifresiz olarak herkese açık bir web sitesinde barındırılması — bu, chip-off gerektirmeden tüm analiz zincirini herkese açar.
- "Gizli" (obscurity'e dayalı) debug portlarının üretim cihazlarında fiziksel olarak lehimli/erişilebilir bırakılması.
- Aynı sabit şifreleme anahtarının tüm cihaz serisinde kullanılması: tek bir cihazdan çıkarılan anahtar, tüm filoyu etkiler.

## UART, JTAG ve SWD: Donanım Debug Arayüzleri

### Kök Neden / Kavramsal Temel

Gömülü sistemlerde geliştirme ve üretim testi (fabrika test/burn-in) için donanım üreticileri işlemciye doğrudan erişim sağlayan arayüzler bırakır. Bunların var olma nedeni **meşrudur**: yazılım geliştirme sırasında hata ayıklama, üretim hattında flash programlama ve arıza teşhisi için bu arayüzler zorunludur. Güvenlik sorunu, bu arayüzlerin *üretime giden cihazlarda devre dışı bırakılmamasından* kaynaklanır.

- **UART (Universal Asynchronous Receiver/Transmitter)**: Basit, iki telli (TX/RX, artı toprak) seri haberleşme hattıdır. Çoğu gömülü Linux cihazında bootloader ve çekirdek çıktısı (konsol) buraya yönlendirilir. Bazı cihazlarda UART üzerinden doğrudan root shell'e (kabuk) erişim mümkündür çünkü seri konsol kimlik doğrulaması olmadan bırakılmıştır.
- **JTAG (Joint Test Action Group)**: Aslen devre kartı üretim testi (boundary scan) için tasarlanmış bir standarttır, ama zamanla işlemci hata ayıklama (debug) erişimi için de kullanılır hale gelmiştir. JTAG üzerinden CPU'nun register'larına, belleğine doğrudan erişilebilir, çalışma durdurulup (halt) adım adım (step) izlenebilir.
- **SWD (Serial Wire Debug)**: ARM mimarisine özgü, JTAG'a göre daha az pin kullanan (2 telli: SWDIO/SWCLK) bir debug protokolüdür; işlevsel olarak JTAG'ın ARM dünyasındaki eşdeğeridir.

**Neden bu kadar güçlü?** Çünkü bu arayüzler donanım test ve geliştirme için tasarlandı; "güvenlik sınırı" değil "mühendislik aracı" olarak düşünüldüler. CPU'nun tüm belleğine ve register durumuna erişim verirler — bu da, işletim sistemi düzeyinde hiçbir erişim kontrolünün (parola, yetkilendirme) bu katmanı koruyamayacağı anlamına gelir. JTAG/SWD, işletim sisteminin *altında* çalışır.

### Nasıl Çalışır (Kavramsal)

Bir araştırmacı devre kartı üzerinde etiketsiz pin sıralarını (header'lar veya lehim padleri) bulur, bir multimetre ve mantık analizörüyle (logic analyzer) hangi pinin toprak, hangisinin TX/RX veya TCK/TMS/TDI/TDO (JTAG sinyalleri) olduğunu belirler (bu sürece bazen "UART/JTAG pinout keşfi" denir). UART bulunduğunda bir USB-seri adaptör ile bağlanılır ve bootloader/kernel boot mesajları izlenir; bazı cihazlarda bootloader menüsüne müdahale edilerek boot argümanları değiştirilebilir (örneğin çekirdeğe `init=/bin/sh` parametresi geçirerek doğrudan root shell'e düşmek). JTAG/SWD bulunduğunda bir debug probe (ör. bir donanım arayüz cihazı) ile CPU'ya bağlanılır, OpenOCD gibi bir yazılım aracılığıyla çip tanınır (JTAG zincirindeki ID kodları okunarak), bellek dökümü alınabilir veya çalışan koda breakpoint konabilir.

### Tespit

Donanım seviyesinde "canlı" tespit çoğunlukla mümkün değildir (işletim sistemi bu erişimi göremez), ama dolaylı işaretler vardır:
- Cihaz üzerinde beklenmeyen sürelerde CPU durmuş/duraklamış gibi davranışlar (halt sırasında watchdog tetiklenmesi, servis kesintileri) izlenebilir.
- Kurumsal/kritik altyapıda fiziksel güvenlik kontrolleri (kasaya erişim logları, mühür bütünlüğü) asıl tespit katmanıdır.
- Bazı çipler debug erişimi denemesini bir güvenli günlük (secure log) veya e-fuse sayaç olarak kaydedebilir; bu üretici tasarımına bağlıdır.

### Savunma

- **Üretimde debug arayüzlerinin kalıcı kapatılması**: Çoğu modern SoC, JTAG/SWD erişimini bir e-fuse veya güvenli önyükleme bekçisi (secure boot ile bağlantılı bir "debug disable" biti) ile kalıcı olarak kapatma imkânı sunar. Bu, geri döndürülemez bir işlemdir ve üretim hattında test tamamlandıktan sonra uygulanmalıdır.
- **Kimlik doğrulamalı debug erişimi**: Bazı mimariler (ör. ARM'ın debug authentication mekanizmaları) JTAG/SWD erişimini bir kriptografik kimlik doğrulama adımının arkasına koyar — yalnızca yetkili bir anahtara sahip taraf debug oturumu açabilir.
- **Konsol kimlik doğrulaması**: UART üzerinden açılan seri konsolun, işletim sistemi seviyesinde parola/kimlik doğrulaması istemesi (login prompt) ve bootloader menüsünün bir parola veya zaman aşımı ile korunması.
- **Fiziksel gizleme/zorlaştırma değil, gerçek devre dışı bırakma**: Pinleri PCB'nin iç katmanına gömmek veya lehim maskesiyle kapatmak yalnızca *zorlaştırır*, gerçek güvenlik e-fuse/kriptografik kilittir.

### Yaygın Hatalar

- "Test pinlerini boyayla kapatırsak kimse bulamaz" varsayımı — mantık analizörü ve fiziksel inceleme ile bu kolayca aşılır; bu obscurity'dir, güvenlik değildir.
- Bootloader'ın (ör. U-Boot benzeri yükleyiciler) interaktif konsolunun parola veya zaman kısıtlaması olmadan üretim cihazında açık bırakılması.
- JTAG devre dışı bırakma bitinin yazılımsal bir bayrak olarak tutulup e-fuse gibi donanımsal/kalıcı olmaması — bu durumda bir glitching (voltaj/saat sinyali manipülasyonu) saldırısıyla bayrak atlatılabilir.

## Bootloader ve Secure Boot / Chain-of-Trust

### Kök Neden / Kavramsal Temel

Bir cihaz açıldığında ilk çalışan kod, genelde çipin içine gömülü değişmez bir **ROM bootloader**dır (Boot ROM). Bu, sırasıyla bir ikincil bootloader'ı (ör. U-Boot benzeri), o da işletim sistemi çekirdeğini yükler. Bu zincirin her halkası bir öncekine güvenir (trust). **Secure boot / chain-of-trust** kavramı, bu güvenin *kriptografik olarak doğrulanmasını* ifade eder: her aşama, bir sonraki aşamayı çalıştırmadan önce onun dijital imzasını (genellikle bir asimetrik imza algoritmasıyla) doğrular. Kök güven noktası (root of trust) genellikle çipin içine üretimde yakılan, değiştirilemez bir açık anahtar özeti (hash) veya doğrudan anahtardır.

**Neden bu mimari?** Çünkü tek bir noktada doğrulama yetmez — eğer yalnızca işletim sistemi kendini doğrularsa ama bootloader doğrulanmazsa, saldırgan bootloader'ı değiştirip işletim sistemi doğrulamasını tamamen atlayan bir yol kurabilir. Zincirin *her* halkasının doğrulanması gerekir; aksi halde en zayıf halka tüm zinciri kırar. Bu, "trust but verify"ın donanım karşılığıdır: her aşama bir sonrakine güvenmeden önce kanıtister.

### Nasıl Çalışır (Kavramsal)

1. Çip açılır, değişmez Boot ROM çalışır (bu kod maskeleme sırasında silikona işlenmiştir veya bir kere yazılabilir bellekte tutulur, dolayısıyla saldırgan tarafından değiştirilemez — bu zincirin *sabit* başlangıç noktasıdır).
2. Boot ROM, bir sonraki aşamanın (ikincil bootloader) imzasını, çipe gömülü kök açık anahtar veya anahtar özeti ile doğrular. İmza geçerliyse çalıştırır; geçersizse (tasarıma göre) boot durur veya kurtarma moduna geçer.
3. İkincil bootloader aynı mantıkla çekirdek imajının imzasını doğrular.
4. Çekirdek, dosya sistemini doğrulayabilir (ör. bir doğrulanmış/salt-okunur dosya sistemi mekanizması ile), böylece zincir uygulama katmanına kadar uzatılabilir.

Bu zincirin gücü, en zayıf halkasına eşittir. Bilinen atlatma yaklaşımları kavramsal olarak şu kategorilere ayrılır:

- **Uygulama hataları**: İmza doğrulama kodunda mantık hatası (ör. doğrulama sonucunun düzgün kontrol edilmemesi, bir "downgrade" — eski, imzalı ama zafiyetli bir sürümün kabul edilmesi).
- **Fault injection / glitching**: Çipin besleme voltajına veya saat sinyaline kısa süreli, hassas zamanlanmış bir bozulma (glitch) verilerek doğrulama adımının CPU tarafından "atlanması" sağlanır. Bu, yazılımı değil donanımın fiziksel davranışını hedefler; doğrulama kodu kendisi doğru olsa bile CPU'nun o anki komut akışı bozulabilir.
- **Side-channel (yan kanal) analiz**: Anahtar materyalinin işlenmesi sırasında güç tüketimi veya elektromanyetik emisyon gibi yan kanallardan sızan bilgi kullanılarak kriptografik anahtar veya doğrulama durumu çıkarılmaya çalışılır.
- **Anahtar/rollback zafiyetleri**: Kök anahtarın kendisinin sızması (üretim hatası, tedarik zinciri sorunu) veya eski/zafiyetli ama hâlâ geçerli imzalı bir firmware sürümüne "downgrade" edilmesine izin verilmesi.

### Tespit

Secure boot atlatma girişimlerinin çalışan sistemde "tespiti" doğası gereği zordur çünkü başarılı bir atlatma, tam olarak tespit mekanizmalarının da devre dışı kalmasını hedefler. Yine de:
- **Attestation (uzaktan doğrulama)**: Cihazın boot zincirinin durumunu (hangi aşamaların hangi ölçümlerle - hash - doğrulandığını) bir sunucuya kriptografik olarak kanıtlaması; sunucu beklenmeyen bir ölçüm görürse cihazı güvenilmez işaretler.
- **Boot sayaçları ve olay günlükleri**: Güvenli bir monoton sayaç (rollback saldırılarını önlemek için) ve boot aşaması hatalarının (ör. imza doğrulama başarısızlığı) güvenli bir alanda loglanması.
- **Anomali izleme filo genelinde**: Aynı model cihazlardan beklenmeyen firmware sürüm/hash raporlayan örneklerin filo yönetim sisteminde işaretlenmesi.

### Savunma

- **Zincirin her halkasını doğrulama, tek nokta bırakmama**: Boot ROM'dan uygulamaya kadar her aşama bir öncekince doğrulanmalı.
- **Rollback koruması**: Yalnızca güncel/onaylı sürüm numaralarının kabul edilmesi (monoton sürüm sayacı), eski zafiyetli ama geçerli imzalı sürümlerin reddedilmesi.
- **Fault injection'a karşı donanımsal sertleşme**: Voltaj/saat glitch algılayıcıları, kritik karşılaştırma işlemlerinin yedekli (redundant, çift kontrol) yapılması, sabit-zamanlı (constant-time) kriptografik karşılaştırma.
- **Anahtar yönetiminde en az ayrıcalık**: Kök imzalama anahtarının üretim ortamından tamamen izole (donanım güvenlik modülü, HSM) tutulması, cihaz başına türetilmiş anahtarlar kullanılması ki bir cihazın ele geçmesi filonun tamamını etkilemesin.
- **Güvenli, doğrulanabilir kurtarma modu**: Bootloader'ın bir kurtarma yolu sunması gerekiyorsa bile bu yolun da imza doğrulaması gerektirmesi; "her zaman açık, doğrulamasız" bir kurtarma modu tüm zinciri anlamsız kılar.

### Yaygın Hatalar

- Doğrulama fonksiyonunun dönüş değerinin yanlış yorumlanması (ör. hata kodu ile başarı kodunun karıştırılması) — küçük bir mantık hatası tüm zinciri geçersiz kılar.
- Secure boot'un yalnızca çekirdeğe kadar uygulanıp uygulama/kullanıcı alanı dosya sistemine uzatılmaması — saldırgan çekirdek altında değil üstünde değişiklik yapar.
- Geliştirme sürecinde kullanılan "test anahtarlarının" üretim imajlarında da kabul edilir durumda bırakılması.
- Fiziksel erişimi olan bir saldırganın glitching yapabileceğinin tehdit modeline hiç dahil edilmemesi ("yazılım güvenli, donanım güvenlik kapsamı dışı" yanılgısı).

## Firmware Analiz Araçları: binwalk ve firmadyne

### Kök Neden / Kavramsal Temel

Çıkarılan bir firmware imajı çoğunlukla belgelenmemiş, iç yapısı bilinmeyen bir ikili (binary) yığındır. Analistin ilk sorusu şudur: *bu blob'un içinde ne var, nereden başlıyor, nereden bitiyor?* Bu ihtiyaç, imza tabanlı (signature-based) tarama araçlarını doğurmuştur.

**binwalk**, bir firmware imajını tarayarak içindeki bilinen dosya sistemi imzalarını (ör. sıkıştırılmış dosya sistemi başlıkları, sıkıştırma formatı sihirli baytları, dosya sistemi süper blokları) tanır ve otomatik olarak çıkarmayı (extract) dener. Kavramsal olarak bir "dosya içinde dosya bulucu"dur — firmware imajları genellikle birden fazla bölümün (bootloader + sıkıştırılmış çekirdek + sıkıştırılmış kök dosya sistemi + belki bir kalibrasyon bölümü) art arda eklenmesiyle oluştuğundan, bu imzaları tanımak analiz sürecinin ilk ve en kritik adımıdır.

**firmadyne** ise bir adım öteye gider: çıkarılan bir Linux tabanlı firmware kök dosya sistemini alıp, gerçek donanım olmadan **QEMU** gibi bir emülatör içinde *çalıştırmayı* (emülasyon) otomatikleştiren bir araştırma çerçevesidir. Amaç, gerçek cihaza dokunmadan firmware'in çalışan bir web arayüzünü, ağ servislerini dinamik olarak test edebilmektir (ör. otomatik zafiyet tarama, web arayüzü fuzzing).

**Neden bu araçlar önemli?** Çünkü statik analiz (dosyaları açıp okumak) yalnızca sınırlı bilgi verir; bir servisin gerçekte nasıl davrandığını anlamak için çoğu zaman onu *çalıştırmak* gerekir. Ama gerçek donanımı her analiz için elde bulundurmak pratik değildir — emülasyon bu engeli aşar (kısmen; ağ donanımına özgü kernel modülleri veya mimariye özgü sistem çağrıları gibi emülasyonun tam taklit edemediği kısımlar da vardır).

### Nasıl Çalışır (Kavramsal)

binwalk, imajı baytların art arda dizilişinde bilinen "sihirli sayı" (magic number) ve yapısal imzaları arayarak tarar (bu yaklaşım dosya türü tanıma araçlarının genel mantığıyla aynıdır, sadece gömülü sistemlere özgü dosya sistemi ve sıkıştırma formatlarına odaklanır). Bulunan her imza için offset raporlanır; birçok kurulumda bulunan bölüm otomatik olarak ayrıştırılıp diske çıkarılır. Entropi analizi de genellikle beraberinde sunulur: yüksek entropili bölgeler (rastgele görünen veri) genellikle şifrelenmiş veya zaten sıkıştırılmış veriye işaret eder, bu da analistin "burada ekstra bir koruma katmanı olabilir" çıkarımı yapmasını sağlar.

firmadyne akışı kavramsal olarak şöyledir: çıkarılan kök dosya sisteminin mimarisi (ARM, MIPS vb.) tespit edilir; bu mimariye uygun bir QEMU kullanıcı-alanı veya sistem emülasyonu ortamı kurulur; cihazın normalde gerçek donanımdan beklediği bazı arayüzler (NVRAM benzeri konfigürasyon depolama, belirli donanım sürücüleri) sahte/taklit (mock) bileşenlerle değiştirilir çünkü emülatörde gerçek donanım yoktur; ağ arayüzleri sanal olarak bağlanır ve cihazın web sunucusu/servisleri "ayağa kalkacak" şekilde başlatılmaya çalışılır. Başarılı olursa artık bu servislere normal ağ araçlarıyla (tarayıcı, HTTP istemcisi, port tarayıcı) erişilip dinamik test yapılabilir.

### Tespit

Bu araçlar analiz tarafında kullanıldığından "tespit" kavramı burada ters yönde işler — yani üretici/savunmacı açısından soru şudur: *rakip veya araştırmacı bizim firmware'imizi binwalk/firmadyne ile kolayca analiz edebilir mi?* Bunun "tespiti" değil önlenmesi/zorlaştırılması hedeflenir (aşağıya bakınız). Kurumsal ortamda ise tersine mühendislik faaliyetinin dolaylı işaretleri şunlar olabilir: üretici forumlarında/GitHub'da ilgili cihaz modeline yönelik ani analiz paylaşımlarının artması, veya güncelleme sunucularına olağandışı toplu indirme paternleri.

### Savunma

- **İmza gizleme değil, gerçek şifreleme**: Dosya sistemi imzalarını değiştirerek binwalk'ı "kandırmaya" çalışmak (obfuscation) gerçek güvenlik sağlamaz, yalnızca analiz süresini biraz uzatır. Gerçek koruma, ilgili bölümlerin kriptografik olarak şifrelenmesi ve anahtarın chain-of-trust'a bağlı olmasıdır.
- **Emülasyona dayanıklı tasarım beklentisini yönetmek**: Bir savunmacı, kendi firmware'inin kolayca emüle edilip dinamik olarak fuzzing'e tabi tutulabileceğini varsaymalı ve bu nedenle ağ servislerini (özellikle web yönetim arayüzlerini) klasik web güvenliği pratikleriyle (girdi doğrulama, en az ayrıcalık, güvenli varsayılanlar) sağlamlaştırmalıdır — "kimse firmware'imi analiz edemez" varsayımı savunma stratejisi olamaz.
- **Kendi firmware'ini bu araçlarla düzenli test etme**: Üreticilerin kendi geliştirme sürecinde binwalk ile kendi imajlarını tarayıp beklenmeyen/istemeden gömülü kalmış hata ayıklama sembollerini, sabit kimlik bilgilerini veya özel anahtarları tespit etmesi iyi bir pratiktir (bir nevi "kendine karşı kırmızı takım" testi).
- **Güncelleme dosyalarını erişim kontrolü altına almak**: Herkese açık, kimlik doğrulamasız indirilebilen firmware imajları, analiz zincirinin ilk adımını bedavaya sunar; en azından üretici hesabı/cihaz seri numarası doğrulaması gibi bir eşik konması dağıtımı zorlaştırabilir (ama bu güvenliğin *değil* dağıtım kontrolünün bir parçasıdır; imajın kendisi hâlâ güçlü kriptografik korumaya sahip olmalı).

### Yaygın Hatalar

- Dosya sistemini "özel"/bilinmeyen bir sıkıştırma formatıyla paketleyip bunun güvenlik sağladığını düşünmek; bu yalnızca analistin biraz daha fazla tersine mühendislik yapmasını gerektirir, gerçek bir kriptografik engel değildir.
- Emülasyonda çalışmayan (gerçek donanıma bağımlı) bir güvenlik kontrolünün var olduğunu düşünüp bunun testi atlandığını fark etmemek — bazı üreticiler emülasyon zorluğunu yanlışlıkla "kimse test edemez" güvencesi sanır.
- Geliştirme/debug sembollerinin (log mesajları, fonksiyon isimleri, hata ayıklama arayüz kodları) üretim imajında bırakılması; bu, binwalk sonrası ikili analizini (strings, disassembly) ciddi ölçüde kolaylaştırır.

## Sonuç: Bütüncül Bakış

IoT/gömülü firmware güvenliğinin özü, **fiziksel erişimin tehdit modeline dahil edilmesi** gerektiğidir. Firmware extraction, UART/JTAG/SWD erişimi ve secure boot atlatma teknikleri birbirinden bağımsız değil, aynı zincirin halkalarıdır: firmware'i çıkaramayan bir saldırgan chain-of-trust'ı analiz edemez; donanım debug arayüzüne erişemeyen bir saldırgan glitching veya doğrudan bellek müdahalesi yapamaz. Savunmacı açısından da aynı bütünlük geçerlidir — yalnızca yazılımsal sertleştirme (secure boot) yeterli değildir, eğer JTAG açık bırakılmışsa veya flash şifrelenmemişse zincirin diğer halkaları savunmasız kalır. binwalk/firmadyne gibi araçlar bu resmin "analiz" tarafını temsil eder ve hem saldırgan hem savunmacı tarafından, sırasıyla zafiyet bulma ve kendi ürününü denetleme amacıyla kullanılabilir. Modern IoT pentestinin temel yetkinliği, tam olarak bu üç katmanı (fiziksel erişim, donanım debug, kriptografik zincir) birlikte değerlendirebilmektir.
