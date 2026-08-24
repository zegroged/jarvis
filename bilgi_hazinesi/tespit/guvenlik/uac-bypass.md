# UAC Bypass — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." UAC Bypass'i tespit etmek için önce onun ne olduğunu, hangi güven varsayımını sömürdüğünü ve Windows'ta arkasında hangi izleri bıraktığını anlamak gerekir. Bu metnin amacı savunma ve tespittir; canlı bir saldırı reçetesi değil. Odak, saldırganın davranışının log kaynaklarında nasıl göründüğü ve bunu gerçek Sigma kurallarıyla nasıl yakaladığımızdır.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

User Account Control (UAC), Windows'un ayrıcalık yükseltme (privilege escalation) için koyduğu bir onay bariyeridir. Bir kullanıcı yönetici (administrator) grubunda olsa bile, süreçleri varsayılan olarak "medium integrity" seviyesinde koşar. Gerçekten yönetici hakları (high integrity) gereken bir işlem yapılacağında UAC devreye girer ve kullanıcıya o meşhur onay penceresini (consent prompt) gösterir. Yani UAC, "kullanıcı yönetici bile olsa her yükseltmeyi görsün ve onaylasın" mantığıyla çalışan bir kapıdır.

Sorun şu: Microsoft, kullanılabilirlik için bazı imzalı, güvenilir Windows ikili dosyalarına (binary) UAC penceresini **hiç göstermeden** otomatik olarak yükselme yetkisi vermiştir. Bunlara **auto-elevate** ikili dosyaları denir. Bir program `manifest` içinde `autoElevate=true` bayrağına sahipse, Microsoft tarafından imzalıysa ve güvenilir bir dizinden (`C:\Windows\System32` gibi) çalışıyorsa, UAC penceresi görünmeden high integrity'ye çıkar. `eventvwr.exe`, `fodhelper.exe`, `iscsicpl.exe`, `dism.exe`, `sdclt.exe`, `computerdefaults.exe` bunlardan bazılarıdır.

UAC Bypass'in kavramsal özü şudur: **Saldırgan, kendi kodunu bu auto-elevate güvenilir sürecin bağlamına sokar.** Yani süreç yükselirken yanında saldırganın istediği şeyi de yukarı taşımasını sağlar. Bunu yapmanın başlıca kavramsal yolları:

- **Registry hijacking (fileless):** Auto-elevate bir süreç, açılışında belirli bir registry anahtarını okuyup oradaki bir komutu/handler'ı çalıştırır. Saldırgan, `HKCU` (mevcut kullanıcı, yükseltme gerektirmeyen) altındaki bu anahtarı kendi komutuyla doldurur. Süreç yükselince, saldırganın komutu da high integrity ile çalışır. `eventvwr.exe` + `mscfile` shell open command hijacking bunun klasik örneğidir. Dosya bırakmadığı için "fileless" denir.
- **DLL Search Order Hijacking / Sideloading:** Auto-elevate süreç, açılışında belirli bir DLL'i arar ve arama sırasında (search order) kullanıcının yazabildiği bir dizini kontrol eder. Saldırgan, aynı isimde kötü niyetli bir DLL'i o dizine bırakır; güvenilir süreç bunu yükler ve saldırganın kodu yükseltilmiş bağlamda koşar. `iscsicpl.exe` (`iscsiexe.dll`) ve `dism.exe` (`dismcore.dll`) örnekleri buna girer.
- **DLL Hijack varyantları (WOW64 logger vb.):** 32-bit (SysWOW64) süreçlerin yüklediği bazı yardımcı/logger DLL'leri hijack edilerek yükseltilmiş süreç belleğine kod enjekte edilir; bu genelde `process_access` seviyesinde iz bırakır.

Ortak nokta hep aynıdır: Saldırgan yeni bir zafiyet sömürmez; **Windows'un kendi güven modelindeki bir boşluğu** — auto-elevate + kullanıcının yazabildiği bir yol (registry veya dizin) — kullanır. Tüm bu teknikler MITRE ATT&CK'te **T1548.002 (Abuse Elevation Control Mechanism: Bypass User Account Control)** altında toplanır; DLL tabanlı olanlar ayrıca **T1574.001 (DLL Search Order Hijacking)** ile ilişkilenir. Bu, savunmacı için iyi haberdir: Teknik sayısı sınırlı ve davranışları oldukça karakteristiktir, dolayısıyla tespit edilebilirler.

Kavramsal olarak neden bu "boşluk" var sorusunu da anlamak, tespit stratejisini şekillendirir. Microsoft, UAC'yi bir **güvenlik sınırı (security boundary)** olarak tanımlamaz; resmi duruşu UAC'nin bir "kolaylık özelliği" olduğu ve tek başına bir güvenlik garantisi vermediği yönündedir. Bu, savunmacı açısından iki sonuç doğurur: Birincisi, Microsoft bu bypass'ler için genelde acil yama çıkarmaz — yani bunlar "her zaman mevcut" tekniklerdir ve tespit ile sertleştirme (hardening) savunmanın asıl yükünü taşır. İkincisi, saldırgan zaten **medium integrity kod çalıştırabildiği** bir bağlamdan başlar (yani sistemde bir dayanağı vardır); UAC bypass onun için bir "ilk erişim" değil, **ayrıcalık yükseltme** adımıdır. Bu yüzden tespit, izole bir olaya değil, bir saldırı zincirinin (kill chain) ortasındaki bir sıçramaya bakar — ve komşu olaylarla korelasyon (öncesinde bir indirilen dosya, sonrasında bir C2 bağlantısı) tespitin güvenini ciddi biçimde artırır.

---

## 2. Bıraktığı izler / artefaktlar

UAC Bypass "sessiz" görünse de aslında oldukça gürültülü izler bırakır, çünkü güvenilir bir sürecin normalde yapmadığı bir şeyi yapmasını gerektirir. Tespitin dayanacağı ham veriyi anlamak için izleri kaynak bazında ayıralım.

**a) Process oluşturma izleri (process_creation)**
En değerli kaynaklardan biri. İdeali **Sysmon Event ID 1** veya zenginleştirilmiş **Windows Security Event ID 4688** (Process Creation) — command line loglaması açık olmalı. Aranan davranış:
- Anormal **parent-child** ilişkileri. Örneğin `eventvwr.exe` normalde çocuk süreç olarak yalnızca `mmc.exe` (veya hata durumunda `WerFault.exe`) doğurur. Bunun dışında bir çocuk süreç (örn. `cmd.exe`, `powershell.exe`) doğması güçlü bir UAC bypass sinyalidir. Burada kritik alanlar `ParentImage` ve `Image`.
- `fodhelper.exe`, `computerdefaults.exe`, `sdclt.exe` gibi auto-elevate ikililerinin beklenmedik çocuk süreçler doğurması.
- Yükseltme sonrası çalışan payload'ın komut satırı desenleri: `powershell.exe` ile `-NoP -sta -NonI -W Hidden -Enc <base64>` gibi kodlanmış/gizli çalışma bayrakları (`CommandLine` alanı). Bu desen özellikle Empire gibi framework'lerin `Invoke-EventVwrBypass` modülünde görülür.

**b) Image / DLL yükleme izleri (image_load)**
DLL sideloading temelli bypass'lar için **Sysmon Event ID 7** (Image Loaded) belirleyicidir. Aranan:
- Güvenilir bir sürecin **beklenmedik bir yoldan** DLL yüklemesi. Örneğin `C:\Windows\SysWOW64\iscsicpl.exe`'nin `\iscsiexe.dll`'i `C:\Windows\` dışından (temp veya kullanıcının yazabildiği bir dizinden) yüklemesi. Kritik alanlar: `Image` (yükleyen süreç) ve `ImageLoaded` (yüklenen DLL yolu).
- `dism.exe`'in `dismcore.dll`'i meşru `C:\Windows\System32\Dism\` dizini yerine başka bir yerden yüklemesi.
- İz kalıbı hep şudur: doğru DLL adı + yanlış (kullanıcı kontrollü) dizin.

**c) Process erişim / enjeksiyon izleri (process_access)**
**Sysmon Event ID 10** (ProcessAccess). WOW64 logger DLL hijack gibi bellek enjeksiyonu içeren varyantlarda:
- `SourceImage`'in `SysWOW64` altından gelmesi, `GrantedAccess` değerinin `0x1fffff` (tam erişim — PROCESS_ALL_ACCESS) olması, ve `CallTrace`'in tanınmayan/adreslenemeyen modüllerle (`UNKNOWN(0000000000000000)`) başlaması. Meşru yazılımlar genelde böyle tam erişimli ve izi kaybolmuş bir çağrı yığını üretmez.

**d) Registry izleri (registry_event)**
Fileless registry-hijack varyantları için **Sysmon Event ID 12/13/14** (Registry Object Add/Set/Rename). Aranan:
- `HKCU\Software\Classes\...\shell\open\command` gibi anahtarlara yazma (örneğin `mscfile`, `ms-settings`, `Folder`, `exefile` sınıfları için).
- `DelegateExecute` değerinin boş olarak set edilmesi (fodhelper varyantının imzası).
- Bu yazmalar çoğunlukla payload çalıştıktan hemen sonra silinir; dolayısıyla **hem oluşturma hem silme** olayları değerlidir.

**e) Dosya sistemi izleri**
Sideloading varyantlarında saldırganın DLL'i bıraktığı an: kullanıcının yazabildiği bir dizine (Temp, Downloads, `%APPDATA%`) `iscsiexe.dll`, `dismcore.dll` gibi Windows'a ait olması gereken bir DLL adının belirmesi. Bunlar **Sysmon Event ID 11** (FileCreate) ile görülür ve image_load ile korelasyona sokulabilir.

**f) Integrity level değişimi (bağlamsal)**
Doğrudan bir "bypass gerçekleşti" event'i olmasa da, bir sürecin **medium** integrity'den **high** integrity'ye UAC penceresi görülmeden geçmesi, süreç ağacında dolaylı olarak izlenebilir. Sysmon Event ID 1 kayıtlarında `IntegrityLevel` alanı bulunur; auto-elevate bir ebeveynden doğan `High` veya `System` integrity'li beklenmedik bir çocuk süreç, önceki normal kullanıcı aktivitesiyle kıyaslandığında dikkat çeker. Bu alan tek başına alarm için zayıftır ama korelasyonda zenginleştirici olarak değerlidir: "Bu kullanıcı oturumunda gizli PowerShell high integrity ile mi çalıştı?" sorusunu yanıtlar.

Özetle üç güçlü sinyal grubu vardır: (1) auto-elevate ikilinin anormal çocuk süreci, (2) güvenilir sürecin yanlış yoldan DLL yüklemesi, (3) yükseltilmiş bağlamda kodlanmış/gizli PowerShell çalışması. Bu üçüne (4) fileless registry-hijack yazma/silme desenini ve (5) process_access seviyesindeki tam-erişimli enjeksiyon izini eklersek, verilen Sigma kurallarının hepsinin dayandığı ham telemetri tablosunu tamamlamış oluruz.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Şimdi bu izleri, verilen gerçek Sigma kurallarının mantığına oturtalım. Her biri farklı bir varyantı ve log kaynağını yakalar; birlikte katmanlı bir kapsama sağlarlar.

### 3.1 DLL Sideloading — `iscsicpl.exe` (image_load)

`UAC Bypass Using Iscsicpl - ImageLoad` (id: `9ed5959a-c43c-4c59-84e3-d28628429456`) kuralı `image_load` (Sysmon EID 7) kaynağına bakar. Mantığı iki parçalıdır:

- **selection:** `Image` tam olarak `C:\Windows\SysWOW64\iscsicpl.exe` ve `ImageLoaded` `\iscsiexe.dll` ile bitiyor. Yani "iscsicpl bu DLL'i yükledi" durumunu yakalar.
- **filter:** `ImageLoaded` hem `C:\Windows\` hem `iscsiexe.dll` içeriyorsa (yani meşru sistem dizininden yükleniyorsa) bunu eler.
- **condition:** `selection and not filter`.

Buradaki tespit dehası şudur: DLL adı zaten meşru; ayırt edici olan **yol**dur. Meşru senaryoda DLL `C:\Windows\` altından gelir; saldırıda temp veya kullanıcı `%PATH%`'inden gelir. Kural "doğru isim + yanlış dizin" desenini `not filter` ile izole eder. Eşik yok, davranış ikili: yanlış yerden yüklendiyse `high` seviye alarm.

### 3.2 DLL Sideloading — `dism.exe` / `dismcore.dll` (image_load)

`UAC Bypass With Fake DLL` (id: `a5ea83a7-05a5-44c1-be2e-addccbbd8c03`) aynı mantığın `dism.exe` versiyonudur:
- **selection:** `Image` `\dism.exe` ile bitiyor ve `ImageLoaded` `\dismcore.dll` ile bitiyor.
- **filter:** `ImageLoaded` tam olarak meşru yol `C:\Windows\System32\Dism\dismcore.dll` ise ele.
- **condition:** `selection and not filter`.

Yine "doğru DLL adı, yanlış konum" prensibi. Bu kural aynı zamanda `attack.t1574.001` (DLL Search Order Hijacking) etiketiyle işaretlenmiştir; çünkü teknik özünde arama sırası hijack'idir.

### 3.3 Registry-hijack davranışı — Event Viewer çocuk süreçleri (process_creation)

`Potentially Suspicious Event Viewer Child Process` (id: `be344333-921d-4c4d-8bb8-e584cf584780`) fileless registry-hijack varyantını **davranış üzerinden** yakalar. Enigma0x3'ün `eventvwr.exe` + registry hijack tekniğine dayanır:
- **selection:** `ParentImage` `\eventvwr.exe` ile bitiyor.
- **filter_main_generic:** `Image` meşru çocuklar olan `mmc.exe`, `WerFault.exe` (System32 veya SysWOW64) ise ele.
- **condition:** `selection and not 1 of filter_main_*`.

Mantık şu: `eventvwr.exe`, hijack başarılı olduğunda registry'deki komutu çalıştırarak saldırganın sürecini **kendi çocuğu** olarak doğurur. Meşru durumda tek çocuk `mmc.exe`'dir (hata olursa `WerFault.exe`). Bunların dışında herhangi bir çocuk süreç (`cmd.exe`, `powershell.exe`, `rundll32.exe` vb.) güçlü bir bypass göstergesidir. Bu kural, registry'yi izlemeye gerek kalmadan sonucu — anormal parent-child — yakaladığı için çok değerlidir.

### 3.4 Yükseltme sonrası payload — Empire PowerShell bayrakları (process_creation)

`HackTool - Empire PowerShell Launch Parameters` (id: `79f4ede3-402e-41c8-bc3e-ebbf5f162581`), bypass'ın **sonucunu** yakalar. Referansları arasında `Invoke-EventVwrBypass.ps1` vardır:
- **selection:** `CommandLine` `' -NoP -sta -NonI -W Hidden -Enc '` veya `' -noP '` gibi gizli/kodlanmış çalışma bayraklarını içeriyor.

Mantık: UAC bypass ile yükseltilen payload sıklıkla PowerShell'i `-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand` kombinasyonuyla, gizli ve base64-kodlu çalıştırır. Bu bayrak dizilimi normal yönetim işlerinde nadirdir. Bu kural teknik-agnostiktir: hangi bypass kullanılmış olursa olsun, sonundaki gizli PowerShell çalışmasını yakalar.

### 3.5 Bellek enjeksiyonu — WOW64 logger hijack (process_access)

`UAC Bypass Using WOW64 Logger DLL Hijack` (id: `4f6c43e2-f989-4ea5-bcd8-843b49a0317c`) `process_access` (Sysmon EID 10) kaynağına bakar:
- **selection:** `SourceImage` `:\Windows\SysWOW64\` içeriyor, `GrantedAccess` `0x1fffff` (tam erişim), ve `CallTrace` `UNKNOWN(0000000000000000)|UNKNOWN(0000000000000000)|` ile başlıyor.

Mantık: UACMe'nin 30 numaralı yöntemi bir logger DLL'i hijack ederek yükseltilmiş sürece erişir. Meşru yazılımların çağrı yığını genelde modül isimleriyle çözümlenir; burada ise iz kaybolmuş (`UNKNOWN`) ve maksimum erişim istenmiştir. Bu üçlü kombinasyon karakteristiktir.

### Basit Sigma-benzeri tespit mantığı örnekleri

**Örnek 1 — Genelleştirilmiş auto-elevate anormal çocuk süreç (davranışsal):**
```yaml
title: Auto-Elevate İkilisinden Şüpheli Çocuk Süreç (Genelleştirilmiş)
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        ParentImage|endswith:
            - '\fodhelper.exe'
            - '\computerdefaults.exe'
            - '\sdclt.exe'
            - '\eventvwr.exe'
    filter_legit:
        Image|endswith:
            - ':\Windows\System32\mmc.exe'
            - ':\Windows\System32\WerFault.exe'
    condition: selection and not filter_legit
level: high
```
Mantık: 3.3'teki `eventvwr` kuralının prensibini diğer auto-elevate ikililerine genişletir. Bu ikililer normalde `cmd`/`powershell` doğurmaz; doğurursa şüphelidir.

**Örnek 2 — Windows sistem DLL'inin kullanıcı-yazılabilir dizinden yüklenmesi (sideloading):**
```yaml
title: Sistem DLL'i Yanlış Yoldan Yüklendi
logsource:
    category: image_load
    product: windows
detection:
    selection:
        ImageLoaded|endswith:
            - '\iscsiexe.dll'
            - '\dismcore.dll'
    filter_system:
        ImageLoaded|startswith: 'C:\Windows\'
    condition: selection and not filter_system
level: high
```
Mantık: 3.1 ve 3.2'nin ortak "doğru isim + yanlış dizin" prensibini tek kuralda toplar. `C:\Windows\` dışından gelen bu DLL adları alarm üretir.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırganın tespiti atlatma girişimleri

Deneyimli saldırganlar yukarıdaki kuralları bildiği için kaçınma dener; savunmacı bu hamleleri öngörmelidir:

- **Bilinmeyen/yeni auto-elevate ikilileri:** Yukarıdaki kurallar isim-bazlıdır (`iscsicpl`, `dism`, `eventvwr`). Saldırgan henüz kurala girmemiş başka bir auto-elevate ikilisini (örn. yeni bir `.exe`) hedeflerse imza-bazlı kural sessiz kalır. **Karşı-tespit:** İsim listesine güvenmek yerine davranışa demirlemek. Örnek 1'deki gibi "System32'deki imzalı bir ikili beklenmedik bir çocuk doğurdu" veya "güvenilir bir süreç kullanıcı-yazılabilir dizinden DLL yükledi" gibi genel davranış kuralları yeni varyantları da yakalar. `image_load` kurallarını tek DLL adına değil, "kullanıcı dizininden yüklenen herhangi bir Windows DLL adı" desenine genişletmek dayanıklılığı artırır.

- **PowerShell bayraklarını gizleme:** 3.4'teki kural `-Enc`, `-W Hidden` gibi sabit dizeleri arar. Saldırgan bayrak sırasını değiştirebilir, kısaltmalar yerine tam adlar (`-EncodedCommand`) kullanabilir veya PowerShell yerine başka bir yükleyici (rundll32, mshta) seçebilir. **Karşı-tespit:** Command-line loglamasını **Script Block Logging (Event ID 4104)** ve **Module Logging** ile tamamlamak; kodlanmış komutları decode edilmiş içerik üzerinden yakalamak. Ayrıca parent-child anomalisine (Örnek 1) yaslanmak, çünkü yükleyici ne olursa olsun auto-elevate ebeveyn izi kalır.

- **Meşru yola yazma:** Sideloading kaçınması için saldırgan `C:\Windows\` altına yazmaya çalışabilir; ancak buraya yazmak zaten yükseltilmiş hak ister — yani bypass'in çözmeye çalıştığı problemin ta kendisi. Bu yüzden `not filter (C:\Windows\ dışı)` mantığı sağlamdır; saldırganı doğası gereği kullanıcı-yazılabilir dizine iter.

- **Registry izini hızla silme:** Fileless varyantlar anahtarı payload çalışır çalışmaz siler. **Karşı-tespit:** Registry oluşturma **ve** silme olaylarını (EID 12/13/14) birlikte toplamak; ayrıca sonucu — anormal çocuk süreç — yakalayan 3.3 gibi davranış kurallarına yaslanmak, çünkü registry temizlense bile process ağacı loglanmıştır.

### Tipik false positive kaynakları ve ayıklama

Verilen kuralların çoğu `high` seviye ve `falsepositives: Unknown` olsa da, pratikte gürültü kaynakları vardır:

- **Meşru DLL yükleme (image_load kuralları):** Bir telnet client veya kurumsal yazılımın `dismcore.dll` benzeri DLL'leri farklı yollardan yüklemesi (`UAC Bypass With Fake DLL` kuralı bunu "legitimate telnet client" olarak not eder). **Ayıklama:** Yükleyen sürecin dijital imzasını (Sysmon `Signed`/`Signature` alanları) ve tam yol/hash'i incelemek; bilinen kurumsal yazılım yollarını `filter`'a eklemek.

- **Yönetim araçları (process_creation kuralları):** IT yönetim ajanları, SCCM, yazılım dağıtım araçları auto-elevate ikililerini otomatikleştirebilir ve gizli PowerShell çalıştırabilir. **Ayıklama:** Bilinen yönetim sunucularından/servis hesaplarından gelen aktiviteyi bağlamla (kullanıcı, host rolü, zamanlama) allowlist'e almak; ama bunu dar tutmak — çok geniş allowlist tespiti kör eder.

- **eventvwr → mmc dışı meşru çocuk:** Nadir de olsa bazı üçüncü parti MMC snap-in'leri farklı çocuklar doğurabilir. **Ayıklama:** 3.3'teki kural zaten `mmc.exe` ve `WerFault.exe`'yi eler; kalan eşleşmeleri süreç imzası ve komut satırıyla teyit etmek.

- **process_access gürültüsü:** `GrantedAccess: 0x1fffff` bazı meşru güvenlik/yedekleme yazılımlarında görülebilir. **Ayıklama:** Kuralın gücü üç koşulun birleşiminde (`SysWOW64` kaynağı + tam erişim + `UNKNOWN` CallTrace); tek başına `GrantedAccess`'e alarm vermemek. Bilinen EDR/AV `SourceImage`'lerini filtrelemek.

### Savunmacı için pratik özet

1. **Katmanlı kural:** İsim-bazlı kurallar (3.1, 3.2, 3.3, 3.5) hızlı ve düşük FP; davranış-bazlı genelleştirmeler (Örnek 1 ve 2) yeni varyant dayanıklılığı sağlar. İkisini birlikte kullan.
2. **Telemetriyi zenginleştir:** Sysmon (EID 1, 7, 10, 11, 12/13) + PowerShell Script Block Logging (4104) + process command-line auditing (4688) olmadan bu kuralların çoğu boş çalışır. Önce görünürlük.
3. **Korelasyon:** DLL bırakma (EID 11) → DLL yükleme (EID 7) → yükseltilmiş çocuk süreç (EID 1) zincirini birbirine bağlamak tek başına olaylardan çok daha yüksek güvenli alarm üretir.
4. **Sertleştirme:** UAC'yi "always notify" seviyesine çekmek çoğu auto-elevate bypass'ini kırar; auto-elevate suistimalini azaltır ve tespiti kolaylaştırır. Tespit ile sertleştirme birlikte yürümelidir.

Sonuç olarak UAC Bypass, yeni bir zafiyet değil, Windows'un güven modelindeki bir boşluğun kötüye kullanımıdır — ve tam da bu yüzden davranışı öngörülebilir ve tespit edilebilirdir. Hırsızın nasıl içeri girdiğini (auto-elevate + kullanıcı-yazılabilir yol) anladığımızda, mücevheri (high integrity bağlamı) hangi log kaynağında ve hangi field ile koruyacağımız netleşir.
