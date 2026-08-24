# Firmware / Gömülü Sistem Tersine Mühendisliği (UEFI/BIOS, Router/IoT Firmware Analizi)

## Giriş ve Kapsam

Gömülü sistemler (router, IoT kamerası, endüstriyel kontrolcü, akıllı ev cihazı) ve modern bilgisayarların önyükleme katmanı (UEFI/BIOS) günümüz saldırı yüzeyinin en az incelenen ama en kritik parçalarından biridir. Bu sistemler genellikle işletim sisteminden *önce* çalışır, kullanıcıdan bağımsız güncellenir ve çoğu zaman hiçbir uç nokta güvenlik ürünü tarafından görülmez. Bir firmware'i tersine mühendislik yapabilmek; tedarik zinciri güvenliğini denetlemek, arka kapı (backdoor) tespit etmek, zafiyet araştırması yapmak ve olay müdahalesinde "cihaz ele geçirildi mi" sorusuna cevap verebilmek için temel bir yetkinliktir. Bu makale, mekanizmayı savunma ve tespit odaklı bir bakış açısıyla açıklar; canlı bir hedefe saldırı talimatı içermez.

## Kavramsal Temel: Firmware Nedir, Neden Farklı Analiz Gerektirir

Firmware, donanımla doğrudan konuşan, genellikle flash bellek (NOR/NAND) üzerinde saklanan düşük seviyeli yazılımdır. Masaüstü uygulama analizinden üç temel farkı vardır:

1. **Mimari çeşitliliği**: x86 dışında ARM (32/64 bit), MIPS (big/little endian), bazen RISC-V hedeflenir. Her mimarinin calling convention'ı, komut seti ve derleyici optimizasyon davranışı farklıdır; tek bir disassembler zihniyeti yetmez.
2. **Dosya sistemi ve paketleme katmanı**: Firmware genelde bir "imaj"dır — bootloader + kernel + kök dosya sistemi (SquashFS, JFFS2, UBIFS, cramfs) tek bir binary'de art arda veya header'larla ayrılmış şekilde paketlenmiştir. Analiz öncesi bu katmanların *çıkarılması* (extraction) gerekir.
3. **Çalışma zamanı erişiminin kısıtlılığı**: Masaüstünde debugger bağlamak kolaydır; gömülü cihazda dinamik analiz için donanım arayüzlerine (UART, JTAG, SPI) fiziksel erişim veya emülasyon (QEMU) gerekir.

## Kök Neden / Çalışma Mantığı: Firmware Neden Bu Kadar Az Denetlenir

Firmware'in güvenlik açısından ihmal edilmesinin yapısal nedenleri vardır ve bunları anlamak, savunma stratejisinin nereye odaklanması gerektiğini gösterir:

- **Görünürlük eksikliği**: EDR/AV çözümleri işletim sistemi katmanında çalışır; UEFI veya router firmware'i bu görüş alanının tamamen dışındadır. Bir implant SPI flash'a yerleşirse, disk formatlansa bile hayatta kalabilir.
- **Güncelleme zinciri güveni**: Üretici imzalama anahtarını ele geçiren veya update sunucusunu tehlikeye atan bir saldırgan, imzalı-görünen ama arka kapılı bir firmware dağıtabilir (tedarik zinciri saldırısı). Cihaz tarafında imza doğrulama zayıfsa (veya hiç yoksa) bu tamamen sessiz kalır.
- **Kaynak kısıtları nedeniyle sadeleştirilmiş güvenlik**: IoT/router firmware'leri genelde bellek koruma mekanizmalarından (ASLR, stack canary, NX) yoksun veya zayıf uygulanmış derlenir; çünkü CPU/RAM bütçesi kısıtlıdır ve üreticinin önceliği maliyet ve hız-to-market'tır.
- **Ekonomik zafiyet yaşam döngüsü**: Router/IoT üreticileri çoğu zaman ürünü 2-3 yıl sonra "end of life" ilan eder; bu süre sonunda bilinen CVE'ler için yama çıkmaz, cihaz internette çalışmaya devam eder. Saldırgan açısından bu, kalıcı ve bol hedef anlamına gelir (bkz. büyük IoT botnet'leri).

Bu nedenlerin ortak paydası: **firmware, güven zincirinin en altında ama denetim zincirinin en dışındadır.** Savunma stratejisi bu asimetriyi kapatmaya çalışır.

## Firmware Çıkarma (Extraction) — Nasıl Çalışır

### Kavramsal Akış

Bir firmware imajı elde edildiğinde (üretici web sitesinden indirilen güncelleme dosyası, cihazdan SPI flash dökümü, ya da güncelleme trafiğinden yakalanmış paket), ilk adım bunun *ne içerdiğini* anlamaktır. İmaj genelde şu bileşenlerin birleşimidir:

- Bootloader (ör. U-Boot) — donanımı başlatır, kernel'i belleğe yükler.
- Sıkıştırılmış kernel imajı (ör. uImage, zImage).
- Kök dosya sistemi (SquashFS, JFFS2, UBIFS, cramfs, initramfs/cpio).
- Üretici tarafından eklenen header/imza/checksum blokları.

**Binwalk mantığı**: Binwalk gibi araçlar, dosya içinde bilinen "magic byte" imzalarını (dosya formatı başlangıç işaretleri) tarayarak olası dosya sistemi veya sıkıştırma başlangıçlarını işaretler. Bu bir imza tabanlı sinyatür eşleştirmedir — dosyayı "anlamaz", sadece bilinen kalıpları arar. Bulduğu ofsetlerden itibaren ilgili sıkıştırma algoritmasını (gzip, LZMA, LZO) veya dosya sistemi ayrıştırıcısını devreye sokarak içeriği diske açar. Entropi analizi modülü ek olarak yüksek entropili bölgeleri (şifrelenmiş veya sıkıştırılmış veri) görsel olarak işaretler; düşük entropili düz metin/kod bölgelerinden ayırt etmeye yarar.

**Dosya sistemi katmanı (SquashFS/JFFS2)**:
- *SquashFS*: Salt-okunur, sıkıştırılmış bir dosya sistemidir; router/IoT firmware'lerinde en yaygın kök dosya sistemi formatıdır çünkü flash alanından tasarruf sağlar. İçinde binary'ler (BusyBox tabanlı shell araçları, web arayüzü CGI/binary'leri), konfigürasyon dosyaları ve bazen düz metin parola/anahtar bulunabilir.
- *JFFS2/UBIFS*: Flash belleğe özel, aşınma dengeleme (wear leveling) ve günlük tabanlı (log-structured) yazma destekleyen dosya sistemleridir; yazılabilir bölümlerde (kullanıcı ayarları, kalıcı veri) kullanılır.

Çıkarma sonrası elde edilen kök dosya sisteminde `/etc/passwd`, init script'leri (`/etc/init.d`, `/etc/rc.d`), web arayüzü CGI binary'leri ve varsa güncelleme doğrulama mantığı incelenir — bunlar arka kapı, sabit kodlanmış (hardcoded) kimlik bilgisi ve zafiyetli servis tespitinde ilk bakılacak yerlerdir.

### Tespit ve Savunma — Extraction Aşaması

- **Üretici tarafı**: Firmware imajını imzalayın ve cihazda secure boot ile imza doğrulaması zorunlu kılın; imza doğrulanmadan flash yazımına izin vermeyin.
- **Kurumsal tarafta**: Yeni firmware sürümlerini üretime almadan önce izole bir ortamda extraction + statik analiz yapıp bilinen zafiyetli kütüphane sürümlerini (ör. eski OpenSSL, BusyBox) tarayan bir süreç (SBOM benzeri firmware envanteri) kurun.
- **Tespit sinyali**: Cihazdan periyodik SPI flash hash karşılaştırması (üreticinin yayınladığı resmi hash ile) sapma tespiti sağlar; bu, "golden image" karşılaştırma yaklaşımıdır.

## Bootloader ve UEFI/BIOS Tersine Mühendisliği

### Kavramsal Model: Önyükleme Güven Zinciri

Modern x86 sistemlerde önyükleme sırası kabaca: CPU mikrokodu → UEFI firmware (SPI flash üzerinde, PEI/DXE/BDS aşamaları) → önyükleme yükleyici (bootloader) → işletim sistemi kernel'i. Secure Boot bu zincirde her aşamanın bir sonrakini kriptografik imza ile doğrulamasını öngörür (chain of trust). Zincirin en başındaki UEFI firmware'i kendisi tehlikeye girerse (ör. flash'a doğrudan yazma, SPI koruma bitlerinin (BIOS_CNTL, WPD gibi) yanlış yapılandırılması), bu zincirin *kökü* bozulur ve üzerine kurulu tüm doğrulamalar anlamsızlaşır — işletim sistemi ne kadar sağlam olursa olsun.

Gömülü router/IoT dünyasında benzer mantık U-Boot gibi bootloader'lar için geçerlidir: U-Boot ortam değişkenleri (`bootargs`, `bootcmd`) ve doğrulama adımları (varsa) cihazın "kime güveneceğini" belirler.

### Neden Önemli — Kalıcılık Açısı

UEFI/bootloader seviyesindeki bir implant şu özellikleri taşır:
- İşletim sistemi yeniden kurulsa, disk formatlansa dahi hayatta kalır (implant flash'ta, diskte değil).
- Çoğu uç nokta güvenlik aracının erişim/görüş alanının dışındadır (ring -2/-1 seviyesinde çalışır diyebiliriz, işletim sisteminden önce).
- Tespiti çok özel araçlar (firmware bütünlük tarayıcıları) gerektirir.

Bu nedenle UEFI implantları, gelişmiş ve hedefli tehdit aktörlerinin (APT) kalıcılık cephaneliğinde yüksek değerli bir araç olarak kabul edilir.

### Nasıl İncelenir (Kavramsal)

UEFI modülleri PE/COFF formatında derlenir (Windows PE dosyalarına benzer yapı) ama farklı bir çalışma ortamı (EFI runtime/boot services) ve farklı API tablosu (`EFI_SYSTEM_TABLE`, `EFI_BOOT_SERVICES`) kullanır. Bir UEFI modülünü tersine mühendislik yaparken:
- Modülün hangi protokolleri (`LocateProtocol`, `InstallProtocolInterface` çağrıları üzerinden) kullandığına bakılır — bu, modülün hangi donanım/servisle etkileşime girdiğini gösterir.
- SMM (System Management Mode) modülleri özellikle kritiktir: SMM, işletim sisteminden tamamen izole, en yüksek ayrıcalıklı çalışma modudur; buradaki bir zafiyet "Ring -2" seviyesinde kalıcı erişim anlamına gelebilir.
- Statik analiz araçları PE/COFF yapısını tanıdığı için UEFI modüllerini genel amaçlı disassembler'larla açmak mümkündür, ancak EFI'ye özgü yardımcı eklentiler (GUID veritabanları, protokol isim çözümleme) analiz doğruluğunu ciddi artırır.

### Tespit ve Savunma

- **Secure Boot + ölçümlü önyükleme (measured boot)**: TPM (Trusted Platform Module) ile her önyükleme aşamasının hash'ini ölçüp PCR (Platform Configuration Register) değerlerinde tutmak, sonradan uzaktan doğrulama (remote attestation) ile "önyükleme zincirinin beklenen durumda olup olmadığını" kanıtlamayı sağlar.
- **SPI flash yazma koruması**: Donanım seviyesinde flash tanımlayıcı bölgelerinin (descriptor region) salt-okunur kilitlenmesi, işletim sistemi seviyesinden firmware'e yazılmasını engeller.
- **Firmware bütünlük tarayıcıları**: Bilinen-iyi (known-good) firmware hash veritabanlarıyla karşılaştırma yapan araçlar, sapmaları raporlar.
- **Yaygın hata**: Kurumlar genelde işletim sistemi yamalarına odaklanıp UEFI/BIOS güncellemelerini ihmal eder; üretici tarafından yayınlanan firmware güvenlik bültenleri takip edilmezse bilinen zafiyetler yıllarca açık kalır.

## Donanım Arayüzleri Üzerinden Erişim: UART, JTAG, SPI

Bu üç arayüz, firmware analizinde "yazılım tarafından kilitlenmiş" bir cihaza fiziksel/donanımsal erişim sağlamanın temel yollarıdır. Neden önemli oldukları, her birinin cihaz üzerindeki rolünden gelir:

- **UART (Universal Asynchronous Receiver/Transmitter)**: Çoğu gömülü cihazda üretici tarafından hata ayıklama/konsol çıktısı için bırakılmış seri bağlantı noktasıdır. Genelde PCB üzerinde etiketlenmemiş dört pin (VCC, GND, TX, RX) şeklinde bulunur. Doğru şekilde bağlanıldığında (mantıksal seviyeye ve baud rate'e dikkat ederek — yanlış voltaj devreye zarar verebilir) çoğu zaman doğrudan bootloader konsoluna veya hatta kimlik doğrulamasız root shell'e erişim verir. Bu, üretimde "unutulmuş" bir hata ayıklama kapısıdır ve gerçek dünyada en sık istismar edilen fiziksel zafiyetlerden biridir.
- **JTAG (Joint Test Action Group)**: Aslında donanım testi/debug amaçlı tasarlanmış bir arayüzdür ama CPU'ya doğrudan erişim (register okuma/yazma, bellek dökümü, çalışma zamanı durdurma) sağladığı için tersine mühendislikte çok güçlü bir araçtır. JTAG üzerinden tam bellek dökümü almak, şifrelenmiş/korumalı flash içeriğini çalışma anındaki açık haliyle görmeyi mümkün kılabilir.
- **SPI (Serial Peripheral Interface)**: Flash belleğin CPU ile konuştuğu veri yoludur. Flash çip üzerine doğrudan bir programlayıcı (clip ile) bağlanarak "chip-off" yöntemiyle tüm firmware imajı ham haliyle okunabilir — bu, cihaz çalışır durumda olmasa bile mümkündür ve extraction için en güvenilir yöntemdir çünkü çalışma zamanı gizleme/şifreleme katmanlarını (varsa) çoğu zaman by-pass eder (flash'taki veri zaten "dinlenme halindeki" formudur).

### Tespit ve Savunma — Donanım Katmanı

- **Üretim tarafında**: Kullanılmayan hata ayıklama arayüzleri (UART, JTAG) üretim aşamasında devre dışı bırakılmalı (fiziksel olarak pinlerin kesilmesi, fuse bit'lerin yakılması) veya en azından kimlik doğrulama arkasına alınmalıdır.
- **Flash şifreleme**: SPI flash içeriğinin şifrelenmesi (donanım destekli), chip-off saldırısını anlamsız kılar çünkü ham veri okunsa bile çözülemez.
- **Fiziksel güvenlik**: Kritik altyapıda (ICS/OT, ağ geçitleri) cihazlara fiziksel erişimin kısıtlanması, tamper-evident mühürler kullanılması, "donanım seviyesinde her zaman fiziksel erişim = tam kontrol" varsayımının kurumsal tehdit modeline dahil edilmesi gerekir.
- **Yaygın hata**: Üreticiler "kimse PCB'yi sökmez" varsayımıyla debug arayüzlerini açık bırakır (security through obscurity); bu, saldırgan motivasyonu yeterince yüksekse (ör. büyük ölçekli IoT botnet operatörü, donanım hacker'ı) her zaman kırılan bir varsayımdır.

## ARM/MIPS Mimarilerinde Tersine Mühendislik Farklılıkları

x86'ya alışkın bir analistin ARM/MIPS firmware'ine geçişte dikkat etmesi gereken kavramsal farklar:

- **Calling convention ve register kullanımı**: ARM'de fonksiyon argümanları genelde R0-R3 (veya AArch64'te X0-X7) registerlarında taşınır; MIPS'te ise $a0-$a3. x86'nın stack tabanlı argüman geçişine alışkın bir analist, disassembly'yi yanlış yorumlayabilir.
- **Endianness**: MIPS hem big-endian hem little-endian varyantlarda (router firmware'lerinde her ikisi de yaygın) bulunabilir; yanlış endianness varsayımı tüm sabitlerin ve adreslerin yanlış okunmasına yol açar.
- **Delay slot (MIPS'e özgü)**: MIPS'te bir dallanma (branch) komutundan hemen sonraki komut, dallanma gerçekleşmeden önce çalıştırılır (pipeline optimizasyonu nedeniyle). Bunu bilmeyen bir analist kontrol akışını yanlış çıkarır.
- **Thumb modu (ARM'e özgü)**: ARM işlemciler hem 32-bit ARM hem de yoğunlaştırılmış 16-bit Thumb komut setleri arasında geçiş yapabilir; disassembler'ın hangi modda olduğunu doğru tespit etmesi (veya analistin elle belirtmesi) gerekir, aksi halde anlamsız komutlar üretilir.
- **Cross-compilation izleri**: Gömülü firmware'ler genelde çapraz derleyici (cross-compiler, ör. bir masaüstünde ARM/MIPS hedefi için derleme) ile üretilir; toolchain'e özgü optimizasyon kalıpları ve statik link edilmiş kütüphane imzaları (BusyBox, uClibc, musl) fonksiyon tanımada (FLIRT benzeri imza eşleştirme mantığıyla) yardımcı olabilir.

### Savunma Açısı

Bu farklılıkların kurumsal savunma tarafındaki karşılığı: zafiyet araştırma/denetim ekiplerinin sadece x86 odaklı araç ve yetkinlikle IoT/router filosunu değerlendirememesidir. Kapsamlı bir donanım/firmware güvenlik programı, ARM/MIPS analiz yetkinliğini (statik analiz araçlarının mimari desteği dahil) organizasyon içinde ayrı bir uzmanlık alanı olarak planlamalıdır.

## Dinamik Analiz ve Emülasyon

Fiziksel donanıma her zaman erişim mümkün/pratik olmayabileceğinden, firmware'in kök dosya sistemi çıkarılıp bir emülatör (ör. QEMU'nun kullanıcı-modu veya sistem-modu emülasyonu, ilgili CPU mimarisini simüle ederek) içinde "canlandırılması" (emulation) yaygın bir tekniktir. Bu, binary'lerin gerçek çalışma zamanı davranışını (hangi dosyaları açtığı, hangi ağ soketlerini dinlediği, hangi komutları çalıştırdığı) donanım olmadan gözlemlemeye imkân verir. Zorluk genelde donanıma özgü çağrıların (GPIO, özel çevre birimleri) emülatörde karşılığının olmamasıdır; bu durumda bu çağrılar "stub"lanarak (taklit edilerek) ilerleme sağlanır.

**Savunma açısından değeri**: Kurumlar, satın almayı planladıkları IoT/router cihazlarının firmware'ini emülasyon ortamında çalıştırıp ağ davranışını (beklenmeyen dış bağlantılar, açık portlar, zayıf varsayılan kimlik bilgileri) tedarik öncesi test edebilir — bu bir tür "firmware sızma testi" / tedarik zinciri güvenlik kapısıdır.

## Yaygın Hatalar (Hem Saldırgan Hem Savunmacı Perspektifinden Ders Çıkarılacak Noktalar)

- **Üretici tarafı**: Debug arayüzlerini (UART/JTAG) üretimde açık bırakmak; firmware güncellemelerini imzasız veya zayıf imzalı dağıtmak; sabit kodlanmış (hardcoded) kimlik bilgilerini kök dosya sisteminde düz metin bırakmak.
- **Kurumsal tarafta**: UEFI/BIOS güncellemelerini işletim sistemi yamalarından daha az öncelikli görmek; IoT/router filosunun firmware envanterini (hangi cihazda hangi sürüm) tutmamak; "cihaz çalışıyor, dokunma" yaklaşımıyla end-of-life donanımı süresiz üretimde bırakmak.
- **Analist tarafında**: Extraction aşamasını atlayıp doğrudan ham binary'yi disassemble etmeye çalışmak (yanlış ofset, yanlış mimari varsayımı); endianness veya delay slot gibi mimariye özgü detayları göz ardı etmek; emülasyonda "çalışmıyor" görülen bir binary'yi hemen "korumalı/şifreli" diye yorumlayıp donanıma özgü eksik stub'ları düşünmemek.
- **Genel**: Firmware güvenliğini "bir kere değerlendirilir, bir daha bakılmaz" statik bir kontrol sanmak; oysa yeni sürümler, yeni zafiyetler ve yeni tedarik zinciri riskleri sürekli bir izleme gerektirir.

## Sonuç

Firmware ve gömülü sistem tersine mühendisliği, klasik uygulama güvenliği analizinden farklı bir zihniyet, farklı araç seti (extraction araçları, çoklu mimari disassembler desteği, donanım arayüz ekipmanı) ve farklı bir tehdit modeli (kalıcılık, görünürlük dışı çalışma, tedarik zinciri güveni) gerektirir. Savunma tarafında kritik olan; firmware'i "bir kere kurulup unutulan" bir bileşen değil, sürekli envanteri tutulan, bütünlüğü doğrulanan ve güncellenen bir yazılım katmanı olarak ele almaktır. UEFI/BIOS seviyesinde secure boot ve ölçümlü önyükleme, router/IoT tarafında imzalı güncelleme zinciri ve donanım debug arayüzlerinin üretimde kapatılması, bu alandaki en yüksek etkili savunma yatırımlarıdır.
