# Rootkit/Bootkit Teknikleri ve UEFI/Firmware Güvenliği

## Giriş: Neden En Derin Katman Önemli?

Kalıcılık (persistence) ve yetki yükseltme (privilege escalation) tartışmaları genellikle iki katmanda kalır: kullanıcı alanı (user-mode) ve çekirdek alanı (kernel-mode). Ancak modern bir bilgisayarda güç düğmesine bastığınız andan işletim sisteminin yüklendiği ana kadar geçen sürede çalışan başka bir yazılım katmanı vardır: **firmware**. UEFI firmware, boot süreci ve System Management Mode (SMM) gibi mekanizmalar, işletim sisteminden daha yüksek ayrıcalıkla ve ondan görünmez biçimde çalışır.

Bir saldırgan bu katmana yerleşirse, işletim sistemini tamamen yeniden kurmak, hatta diski değiştirmek bile tehdidi ortadan kaldırmaz. Bu yüzden firmware seviyesindeki tehditler, kalıcılık zincirinin **en derin ve en zor tespit edilen** halkasıdır. Bu makalenin amacı, bu mekanizmaların nasıl çalıştığını ANLAMAK ve buna karşı **tespit ile savunma** kurmaktır. Amaç operasyonel saldırı talimatı vermek değil; kavramsal derinlik ve savunma perspektifidir.

## Ayrıcalık Halkaları (Protection Rings) ve Katman Haritası

Klasik güvenlik modeli, ayrıcalık seviyelerini "ring" olarak tanımlar:

- **Ring 3**: Kullanıcı uygulamaları (user-mode). En kısıtlı seviye.
- **Ring 0**: İşletim sistemi çekirdeği (kernel). Donanıma doğrudan erişim.
- **Ring -1**: Hypervisor katmanı (VMX root / donanım sanallaştırma).
- **Ring -2**: System Management Mode (SMM). İşletim sisteminden bile gizli, en ayrıcalıklı x86 modu.
- **Ring -3**: Yönetim yardımcı işlemcisi (örneğin Intel Management Engine / ME, AMD PSP gibi ana CPU'dan bağımsız çalışan alt sistemler). Kavramsal olarak işletim sistemi kapalıyken bile çalışabilen bağımsız bir mikrodenetleyici alanı.

Rootkit tanımı ring'e göre değişir. **Rootkit**, varlığını ve etkinliğini gizleyerek ayrıcalıklı erişimi sürdüren yazılımdır. **Bootkit** ise özel olarak boot sürecine (bootloader, boot manager ya da firmware) yerleşerek işletim sistemi yüklenmeden önce kontrolü ele geçiren bir rootkit türüdür. Ne kadar aşağı inersen, işletim sistemi tabanlı savunma araçları o kadar kör kalır.

## UEFI ve Boot Süreci: Kök Neden

### UEFI Nedir?

UEFI (Unified Extensible Firmware Interface), eski BIOS'un yerini alan modern firmware mimarisidir. Bir mini işletim sistemi gibi düşünülebilir: kendi sürücüleri (DXE driver), uygulamaları (UEFI application), dosya sistemi erişimi ve ağ yığını olabilir. Boot süreci kabaca şu fazlardan geçer:

1. **SEC (Security)**: Reset sonrası ilk çalışan kod; güven kökünü başlatır.
2. **PEI (Pre-EFI Initialization)**: Bellek ve temel donanım başlatılır.
3. **DXE (Driver Execution Environment)**: Sürücüler yüklenir, asıl UEFI ortamı burada oluşur. Rootkit'lerin en çok hedef aldığı faz.
4. **BDS (Boot Device Selection)**: Boot aygıtı seçilir, bootloader çağrılır.
5. **İşletim sistemi bootloader'ı** (örneğin Windows Boot Manager, GRUB) devreye girer.

### Firmware Nerede Saklanır?

UEFI firmware genellikle anakart üzerindeki **SPI flash** çipinde tutulur. Bir saldırganın kalıcı UEFI rootkit'i için amacı, bu flash'a kötü amaçlı bir modül yazmaktır. Kritik gerçek şudur: eğer kod SPI flash'a yazılabilirse, disk formatlamak veya işletim sistemini yeniden kurmak temizlik sağlamaz. Bu yüzden SPI flash'ın **yazma korumaları** (write protection) savunmanın temelidir.

### NVRAM ve ESP

İki farklı kalıcılık noktası vardır ve karıştırılmamalıdır:

- **SPI flash / firmware volume**: Fiziksel olarak firmware'in yaşadığı yer. Buraya yazmak zordur ama en kalıcı sonucu verir.
- **ESP (EFI System Partition)**: Diskteki normal bir FAT bölümü; bootloader dosyaları burada durur. Buraya yerleşen bir bootkit, işletim sistemi yeniden kurulunca ya da disk değişince kaybolur — yani "firmware kalıcılığı" DEĞİLDİR, ama yine de işletim sistemi öncesi çalıştığı için tehlikelidir.

Bu ayrım kritiktir çünkü kamuoyunda görülen birçok UEFI bootkit örneği aslında ESP'de yaşar ve gerçek SPI flash implantından çok daha kolay temizlenir.

## Secure Boot: Mekanizma ve Bypass Mantığı

### Secure Boot Nasıl Çalışır?

Secure Boot, boot zincirindeki her aşamanın bir sonraki aşamayı **imza doğrulaması** yaparak yüklemesini sağlayan bir mekanizmadır. Amaç, imzasız veya bilinmeyen anahtarla imzalı kodun boot sırasında çalışmasını engellemektir. Anahtar hiyerarşisi kabaca şöyledir:

- **PK (Platform Key)**: En üstteki sahiplik anahtarı.
- **KEK (Key Exchange Key)**: PK altında, imza veritabanlarını güncelleme yetkisi.
- **db (allowed)**: İzin verilen imzalar/hash'ler veritabanı.
- **dbx (forbidden / revocation)**: Yasaklı, iptal edilmiş imzalar ve hash'ler.

Boot manager, yükleyeceği her binary'i `db`'ye göre doğrular ve `dbx`'te varsa reddeder. Bu, "zincirleme güven" (chain of trust) modelidir.

### Bypass Mantığı (Kavramsal)

Secure Boot'u atlatma girişimleri kavramsal olarak birkaç sınıfa ayrılır. Bunları tespit ve savunma perspektifiyle anlamak önemlidir; burada adım adım saldırı reçetesi verilmez:

1. **İmzalı ama zafiyetli bileşenden yararlanma**: Meşru bir anahtarla imzalanmış ama güvenlik açığı bulunan bir bootloader ya da UEFI uygulaması, saldırganın imzasız kod çalıştırmasına aracı olabilir. Meşru imza taşıdığı için `db`'yi geçer. Bu, kamuya açık birçok gerçek olayın kök nedenidir. Savunma yanıtı, bu zafiyetli bileşenlerin hash'lerinin `dbx`'e eklenerek iptal edilmesidir.
2. **Yanlış yapılandırma / kapalı Secure Boot**: Birçok sistemde Secure Boot ya kapalıdır ya da "setup mode"dadır. Bu durumda hiçbir doğrulama yapılmaz. En yaygın "bypass" aslında saldırı değil, güvenliğin hiç açık olmamasıdır.
3. **NVRAM değişkeni manipülasyonu**: Secure Boot politikası ve anahtarları NVRAM değişkenlerinde tutulur. İşletim sistemi seviyesinde ayrıcalık kazanmış bir saldırgan, bu değişkenleri (yeterli koruma yoksa) değiştirmeye çalışabilir. Doğru tasarımda bu değişkenler kimlik doğrulamalı (authenticated variable) olmalıdır.
4. **Fiziksel / flash seviyesi müdahale**: SPI flash'a doğrudan yazma korumaları atlatılabilirse, Secure Boot mantığının kendisi devre dışı bırakılabilir.

Önemli dürüstlük notu: Belirli bir CVE numarası, kesin sürüm ya da tam komut bayrağı vermekten kaçınıyorum çünkü bu ayrıntılar sürüme ve platforma göre değişir; burada anlatılan mekanizma seviyesidir.

## SMM (System Management Mode) ve Ring -2 Saldırıları

### SMM Nedir?

SMM, x86 mimarisinde çok özel bir işlemci modudur. Bir **SMI (System Management Interrupt)** tetiklendiğinde CPU normal yürütmeyi durdurur, durumunu **SMRAM** adlı korumalı bir bellek bölgesine kaydeder ve SMM handler kodunu çalıştırır. İşletim sistemi bu geçişi doğrudan göremez; SMM işletim sisteminin altında, ondan bağımsız çalışır. Orijinal amacı güç yönetimi, donanım hataları, termal kontrol gibi düşük seviye görevlerdir.

### Neden Bir Saldırı Hedefidir?

SMM kodu Ring -2'de, işletim sistemi çekirdeğinden bile yüksek ayrıcalıkla çalışır ve SMRAM içeriği doğru korunmazsa işletim sistemi tarafından okunamaz/değiştirilemez olmalıdır. Bir saldırgan SMM içine kod yerleştirebilirse:

- İşletim sisteminin tüm belleğine erişebilir (fiziksel bellek okuma/yazma).
- Antivirüs ve EDR araçlarından tamamen gizlenebilir; çünkü bu araçlar Ring 0'da çalışır ve Ring -2'yi göremez.
- Kalıcılık ve gizlilik için ideal bir sığınak elde eder.

### SMM Saldırılarının Kök Nedenleri

Kavramsal olarak SMM güvenliği birkaç temel korumaya dayanır:

- **SMRAM kilidi (D_LCK gibi kilit bitleri)**: SMRAM'ın konfigürasyonu boot sırasında kilitlenmelidir. Firmware bu kilidi ayarlamayı unutursa, işletim sistemi seviyesinden SMRAM yeniden yönlendirilip erişilebilir hale gelebilir.
- **SMM_Code_Chk / yürütme kısıtları**: SMM'in yalnızca SMRAM içindeki koda dallanmasını sağlamak, SMRAM dışındaki (işletim sistemi kontrolündeki) belleğe atlayarak ayrıcalık kazanmayı engeller.
- **SMI handler'daki doğrulama eksikliği**: SMI handler'lar işletim sisteminden gelen işaretçileri (pointer) kullanabilir. Bu işaretçiler SMRAM sınırlarına karşı doğrulanmazsa, saldırgan SMM'i kendi verisine yazması için kandırabilir — buna kavramsal olarak "confused deputy" ya da SMM callout/pointer zafiyeti denir.

Bu koruma bitlerinin doğru ayarlanıp ayarlanmadığı, savunma açısından ölçülebilir ve denetlenebilir noktalardır.

## TPM ile İlgili Zayıflıklar ve Measured Boot

### TPM ve Secure Boot Farkı

Yaygın bir kafa karışıklığı: TPM Secure Boot değildir. **Secure Boot** kodun çalışmasını ENGELLER (enforcement). **TPM (Trusted Platform Module)** ise çalışan kodu ÖLÇER ve kaydeder (measurement); "measured boot" kavramı buradan gelir. TPM, boot bileşenlerinin hash'lerini **PCR (Platform Configuration Register)** adlı özel yazmaçlara "extend" ederek biriktirir. Bu PCR değerleri sonradan **remote attestation** ile bir sunucuya kanıtlanabilir ya da disk şifreleme anahtarını (örneğin BitLocker) PCR durumuna bağlamak için kullanılabilir.

Kritik nokta: TPM saldırıyı tek başına önlemez; **kanıt üretir**. Yani bir bootkit sisteme girse bile, ölçüm zinciri bozulursa PCR değerleri beklenenden farklı olur ve buna bağlı sırlar açılmaz veya attestation başarısız olur. Savunma değeri buradadır.

### TPM ile İlgili Zayıflık Sınıfları

- **Bus interception / sniffing**: Ayrık (discrete) TPM çipi, ana işlemciyle genellikle bir seri veri yolu (örneğin LPC ya da SPI benzeri bir bus) üzerinden konuşur. Bu yol şifrelenmiyorsa, fiziksel erişimi olan biri sırların (örneğin şifreleme anahtarı) hattan okunmasını deneyebilir. Bunun karşı önlemi, TPM ile CPU arasında **parameter encryption / oturum şifrelemesi** kullanmaktır.
- **PCR yanlış bağlama (weak sealing policy)**: BitLocker gibi çözümlerin sırrı yalnızca zayıf bir PCR kümesine bağlanması, saldırganın ölçüm zincirini "beklenen" görünecek şekilde manipüle etmesine alan açabilir. İyi politika, firmware ve boot bileşenlerini kapsayan uygun PCR'lara bağlanmaktır.
- **Fiziksel reset / güç analizi**: TPM çiplerine yönelik fiziksel donanım saldırıları (reset hattı manipülasyonu, yan kanal) kavramsal olarak mümkündür; bunlar fiziksel erişim gerektirir ve savunması genellikle donanım tasarımı ve şifreli oturumlardır.

Burada da spesifik ürün/sürüm zafiyeti uydurmuyorum; anlatılan sınıf seviyesindedir.

## Gerçek Dünya Örneği: Kavramsal Bir Senaryo

Kamuya açık firmware bootkit olaylarının ortak anatomisi şöyledir (genelleştirilmiş, tek bir gerçek örneği taklit etmeden):

1. Saldırgan önce işletim sistemi içinde yüksek ayrıcalık kazanır (Ring 0).
2. SPI flash yazma korumaları eksikse ya da imzalı-zafiyetli bir bileşen mevcutsa, DXE fazına kötü amaçlı bir modül yerleştirilir.
3. Bu modül her boot'ta işletim sistemi yüklenmeden önce çalışır ve işletim sistemi çekirdeğine kancalar (hook) yerleştirir; örneğin bir sürücüyü değiştirerek kalıcı bir arka kapı kurar.
4. İşletim sistemi tarafındaki bileşen silinse bile firmware modülü onu her açılışta yeniden kurar. Bu yüzden klasik temizlik işe yaramaz.

Bu senaryonun eğitim değeri, savunmanın nerede kırıldığını göstermesidir: yazma koruması yoksa ya da iptal (revocation) yapılmamışsa zincir çöker.

## Tespit ve Savunma

### Savunma (Önleme)

- **Secure Boot'u etkinleştir ve doğru yapılandır**: "user mode"da, özelleştirilmiş anahtarlarla ve kapalı değil açık halde tut. Kapalı Secure Boot en yaygın zafiyettir.
- **SPI flash yazma korumalarını uygula**: BIOS write enable / protection bitleri ve flash bölge kilitlerinin firmware tarafından doğru ayarlandığından emin ol. Bu, kalıcı flash implantına karşı birincil bariyerdir.
- **SMRAM'ı kilitle**: Firmware'in D_LCK benzeri kilitleri ayarladığını, SMM yürütme kısıtlarının açık olduğunu doğrula.
- **`dbx` (revocation) güncel tut**: İşletim sistemi ve firmware güncellemeleriyle gelen iptal listelerini uygula ki bilinen zafiyetli imzalı bileşenler reddedilsin. Bu, "imzalı ama zafiyetli" sınıfına karşı en pratik savunmadır.
- **Firmware güncellemelerini imzalı ve düzenli yap**: Anakart/OEM firmware güncellemeleri kritik SMM ve boot zafiyetlerini kapatır.
- **TPM tabanlı measured boot + disk şifreleme**: BitLocker benzeri çözümleri uygun PCR politikasıyla kullan; mümkünse TPM oturum şifrelemesini etkinleştir.
- **Fiziksel güvenlik ve boot menüsü/BIOS parolası**: Fiziksel erişim çoğu firmware saldırısını kolaylaştırır.

### Tespit

- **Firmware bütünlük denetimi**: SPI flash içeriğinin bilinen-iyi bir referansa göre karşılaştırılması. Bazı platformlar firmware ölçümünü ve raporlamasını destekler.
- **Açık kaynak firmware güvenlik araçları**: Firmware yapılandırma bitlerini (SMRAM kilidi, flash koruma, SecureBoot durumu) denetleyen topluluk araçları vardır. Bunlar "kilit ayarlanmış mı?" sorusunu ölçülebilir kılar. Kesin araç sürümü/komutu vermek yerine kavramı belirtiyorum: bunlar konfigürasyon-zafiyet tarayıcılarıdır.
- **Measured boot / remote attestation**: PCR değerlerinin beklenen bilinen-iyi değerlerle uyuşup uyuşmadığını merkezi olarak doğrulamak. Uyuşmazlık, boot zincirinde bir değişimin (olası bootkit) sinyalidir.
- **ESP izleme**: EFI System Partition'daki bootloader dosyalarının beklenmedik değişimini izlemek; ESP tabanlı bootkitler (firmware olmayanlar) burada yakalanabilir.
- **NVRAM değişken denetimi**: Secure Boot politikası ve boot sırası değişkenlerinde beklenmedik değişikliklerin izlenmesi.

Not: EDR/antivirüs Ring 0'da çalıştığı için Ring -2 ve firmware seviyesini doğrudan göremez. Bu yüzden firmware tespiti, işletim sistemi içi araçlardan çok **firmware ölçümü, attestation ve harici bütünlük denetimine** dayanmalıdır.

## Yaygın Hatalar ve Yanılgılar

- **"Diski formatlarsam / işletim sistemini yeniden kurarsam temizlenir" yanılgısı**: SPI flash implantı için bu yanlıştır. ESP bootkiti için doğru olabilir; ikisini ayırt etmek şarttır.
- **TPM'i Secure Boot sanmak**: TPM ölçer/kanıtlar, engellemez. İkisi farklı ve tamamlayıcı mekanizmalardır.
- **Secure Boot açık = güvenli varsaymak**: "Setup mode", boş anahtar veritabanı, güncellenmemiş `dbx` ya da imzalı-zafiyetli bileşenler Secure Boot'u fiilen etkisiz kılabilir. Etkin olması yapılandırmanın doğru olduğunu garanti etmez.
- **SMM'i önemsiz saymak**: SMRAM kilidinin ayarlanmaması yaygın bir firmware hatasıdır ve Ring -2 kalıcılığına kapı açar.
- **Firmware güncellemelerini ihmal etmek**: SMM ve boot zafiyetlerinin çoğu yalnızca OEM firmware güncellemesiyle kapanır; işletim sistemi yamaları bu katmana ulaşmaz.
- **`dbx` güncellemesini atlamak**: İptal listesi güncellenmezse, iptal edilmiş zafiyetli bootloader'lar hâlâ Secure Boot'u geçer.
- **Spesifik ayrıntı ezberlemek yerine mekanizmayı anlamamak**: CVE numaraları ve sürümler değişir; kalıcı olan güven kökü, ölçüm zinciri ve yazma koruması mantığıdır.

## Sonuç

Firmware ve boot seviyesi, kalıcılık zincirinin en derin katmanıdır: işletim sisteminin altında, çoğu güvenlik aracının kör noktasında çalışır. Buna karşı savunma tek bir üründe değil, bir **güven kökü** anlayışında yatar: kod flash'a yazılamıyorsa (yazma koruması), yalnızca doğrulanmış kod çalışıyorsa (Secure Boot + güncel `dbx`), en ayrıcalıklı mod korunuyorsa (SMRAM kilidi) ve her aşama ölçülüp kanıtlanabiliyorsa (TPM/measured boot), saldırganın bu katmana yerleşmesi çok daha zorlaşır. Tespit ise işletim sistemi içi tarayıcılardan çok firmware bütünlüğü ve attestation üzerine kurulmalıdır. Mekanizmayı anlamak, doğru soruları sorabilmenin — "kilit ayarlı mı?", "revocation güncel mi?", "PCR beklenen değerde mi?" — ön koşuludur.
