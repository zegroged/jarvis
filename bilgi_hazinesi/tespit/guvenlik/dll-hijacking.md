# DLL Hijacking / Sideloading — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin önce saldırıyı kavramsal olarak anlamayı, sonra onu log ve telemetri üzerinden tespit etmeyi amaçlar. Amaç savunma ve detection engineering'dir; operasyonel canlı saldırı reçetesi değildir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

DLL Hijacking ve onun en yaygın alt türü olan DLL Sideloading, Windows'un dinamik kütüphaneleri (DLL) **nasıl bulup yüklediği** davranışını istismar eder. Mesele tek cümleyle şudur: bir uygulama bir DLL'e ihtiyaç duyduğunda, işletim sistemi o DLL'i belirli bir **arama sırasına (DLL search order)** göre arar. Saldırgan, bu arama sırasının erken bir basamağına kendi zararlı DLL'ini yerleştirerek, meşru ve genelde **imzalı** bir çalıştırılabilir dosyaya kendi kodunu yükletir.

Neyi istismar eder? Temelde iki tasarım gerçeğini:

- **Windows arama sırası davranışı.** Klasik (SafeDllSearchMode kapalı olmadığı sürece) sırada uygulama, DLL'i önce kendi çalıştığı dizinde arar. Yani bir `program.exe`'nin bulunduğu klasöre, onun yüklemeyi beklediği isimde bir DLL bırakırsanız, sistem çoğu durumda önce sizinkini bulur ve yükler. Bu, "search order hijacking" olarak bilinir.
- **Güven devri (trust inheritance).** İmzalı, itibarı yüksek bir `.exe` çalıştığında, onun yüklediği DLL'lere çoğu kontrol otomatik güvenir. Saldırgan zararlı kodunu doğrudan çalıştırmaz; **meşru bir sürecin içinden** çalıştırır. Böylece process ağacı, imza kontrolü ve birçok uygulama beyaz listesi (application allowlisting) atlanabilir hale gelir. Buna proxy execution denir.

**Sideloading** ise bunun paketlenmiş halidir: saldırgan meşru, imzalı bir uygulamanın (ör. bir antivirüs bileşeni, bir sıkıştırma aracı, Internet Explorer bileşenleri) orijinal `.exe`'sini alır, yanına aynı isimde ama zararlı bir DLL koyar ve ikisini birlikte kurbanın diskine bırakır. Meşru `.exe` çalışınca, kendi klasöründeki sahte DLL'i yükler. Yukarıdaki gerçek Sigma kurallarında geçen `7za.dll`, `vcruntime140.dll`, `iertutil.dll`, `log.dll` gibi isimler tam olarak bu senaryonun aktörleridir.

Kavramsal olarak saldırganın istismar ettiği zafiyet türleri:

- **Missing DLL (phantom DLL).** Uygulama var olmayan bir DLL'i yüklemeye çalışır; saldırgan o boşluğu doldurur.
- **Search order hijack.** DLL sistemde vardır ama saldırgan onu, arama sırasında daha önce gelen bir konuma kopyalar.
- **Sideloading / relocation.** Meşru `.exe` güvenilmez bir dizine (AppData, Public, Temp, USB) taşınır ve yanına zararlı DLL bırakılır.
- **DCOM/servis tetikli hijack.** `iertutil.dll` örneğindeki gibi, uzaktan bir DCOM nesnesi çağrılarak hedef makinede meşru sürecin zararlı DLL yüklemesi tetiklenir (lateral movement).

Saldırganın **motivasyonu** genelde şudur: kod çalıştırma (execution), kalıcılık (persistence — her `.exe` açıldığında DLL yeniden yüklenir), yetki yükseltme (privilege escalation — yüksek yetkili bir süreç zararlı DLL yüklerse) ve savunmadan kaçınma (defense evasion — imzalı bir sürecin arkasına saklanma). Gerçek kurallardaki `attack.t1574.001` etiketi tam olarak bu tekniği (Hijack Execution Flow: DLL Search Order Hijacking / Side-Loading) işaret eder.

Bir başka önemli kavramsal ayrım: DLL Hijacking her zaman "kötü dosya çalıştırma" değildir, çoğu zaman "iyi dosyaya kötü şey yüklettirme"dir. Bu yüzden imza kontrolü, itibar (reputation) sistemleri ve klasik "bilinen kötü hash" yaklaşımları bu tekniğe karşı doğal olarak zayıftır: diskteki `.exe` gerçekten meşrudur, imzası gerçekten geçerlidir, hash'i gerçekten temizdir. Zararlı olan tek unsur, onun yanına bırakılmış DLL'dir — ve saldırgan onu her seferinde yeniden üretebildiği için hash-tabanlı imzalar hızla eskir. Tespit stratejisinin **davranış ve bağlam** odaklı olmasının kök nedeni budur.

Bir de kalıcılık boyutu var: sideloading yalnızca ilk erişim değil, aynı zamanda çok sağlam bir persistence mekanizmasıdır. Meşru `.exe`, kullanıcı her oturum açtığında ya da bir servis/scheduled task tetiklendiğinde otomatik çalışıyorsa, yanındaki zararlı DLL de her seferinde sessizce yeniden yüklenir. Savunmacı açısından bu, tespitin yalnızca ilk düşme (drop) anında değil, sonraki her yüklemede de fırsat penceresi sunduğu anlamına gelir.

Burada operasyonel adım adım komut vermiyoruz; savunmacı için önemli olan kavram şudur: **imzalı bir sürecin, o sürece ait olmayan veya olağandışı bir konumdan gelen bir DLL yüklemesi**, tespitin ana sinyalidir.

---

## 2. Bıraktığı izler / artefaktlar

DLL yükleme olayı, doğası gereği çok "gürültülü" bir aktivitedir — her süreç onlarca meşru DLL yükler. İşin zorluğu ve güzelliği, zararlı yüklemenin bıraktığı **bağlamsal** izleri ayıklamaktır. Başlıca artefakt kaynakları:

### Image Load telemetrisi (en kritik kaynak)
- **Sysmon Event ID 7 (Image Loaded).** DLL Hijacking tespitinin bel kemiği budur. Bu event şu alanları verir:
  - `Image` — DLL'i yükleyen sürecin tam yolu (ör. `...\iexplore.exe`).
  - `ImageLoaded` — yüklenen DLL'in tam yolu (ör. `...\iertutil.dll`).
  - `Signed`, `Signature`, `SignatureStatus` — DLL imzalı mı, imza geçerli mi.
  - `Hashes`, `OriginalFileName`, `Company`, `Product` — DLL'in kimlik/itibar bilgisi.
  Yukarıdaki gerçek kuralların hepsi `logsource: category: image_load` (yani Sysmon EID 7) üstüne kuruludur. Alan adları `Image`, `ImageLoaded` bu event'ten gelir.
- Sysmon Event ID 7'yi üretmek için Sysmon konfigürasyonunda `ImageLoad` bölümünün **açık** olması gerekir; varsayılan bazı config'lerde performans nedeniyle kapalı gelebilir — bu tespit için mutlaka etkinleştirilmelidir.

### Süreç oluşturma telemetrisi (bağlamı tamamlar)
- **Sysmon Event ID 1 / Windows Security Event ID 4688 (Process Creation).** İmzalı bir `.exe`'nin **olağandışı bir dizinden** (AppData, Temp, Public, USB) çalıştığını görmek sideloading'in klasik işaretidir. `Image`, `CommandLine`, `ParentImage`, `CurrentDirectory` alanları burada değerlidir. Meşru `7za.exe` normalde `Program Files` altında olur; `C:\Users\...\AppData\...` altında görülmesi şüphelidir.

### Dosya sistemi ve registry izleri
- **Sysmon Event ID 11 (FileCreate).** Zararlı DLL diske düştüğü an: meşru bir `.exe`'nin yanında yeni oluşan bir `.dll`, özellikle `Users\Public`, `AppData`, `Temp`, `PerfLogs` gibi dizinlerde.
- Meşru uygulama klasörünün **dışına kopyalanmış imzalı `.exe`** + yanına konmuş **imzasız veya imzası uyumsuz `.dll`** ikilisi. Klasik "yetim ikili" (orphan binary) deseni.
- Kalıcılık için kullanılıyorsa: Run anahtarları, servis tanımları veya Scheduled Task ile o taşınmış `.exe`'nin otomatik başlatılması (Sysmon EID 12/13/14 registry, EID 1 ile task tetikleme).

### Ağ izleri
- Zararlı DLL yüklendikten sonra genelde bir **C2 bağlantısı** açar. **Sysmon Event ID 3 (Network Connection)**, `Image` alanında **meşru bir `.exe`'nin beklenmedik bir dış IP/porta** bağlandığını gösterir — ör. bir sıkıştırma aracının ya da IE bileşeninin internete çıkması olağandışıdır.
- `iertutil.dll` DCOM hijack senaryosunda ayrıca **uzaktan** tetikleme olduğu için ağ tarafında SMB/DCOM/RPC trafiği ve hedefte `iexplore.exe`'nin uzak bir istekle uyanması görülür (gerçek kuralda `attack.t1021.002`/`t1021.003` — remote services etiketleri).

### Komut satırı / davranış desenleri
- Meşru `.exe`'nin `ParentImage`'ının olağandışı olması (ör. bir Office ürünü ya da script motorunun imzalı bir aracı beklenmedik biçimde başlatması).
- Kısa ömürlü, "drop-and-execute" deseni: FileCreate → ProcessCreate → ImageLoad → NetworkConnection zincirinin dakikalar içinde aynı klasörde gerçekleşmesi.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Verilen gerçek kuralların hepsinin ortak paydası: **`logsource: category: image_load` (Sysmon EID 7)** üzerinde, `ImageLoaded` ve `Image` alanlarını değerlendirip **beklenen konum/eşleşme dışındaki** yüklemelere alarm vermek. Dört farklı mantık kalıbı görüyoruz; her birini Türkçe açıklayalım.

### Kalıp A — Sabit eşleşme (known-pair) yaklaşımı
`Potential DCOM InternetExplorer.Application DLL Hijack` (id `f354eba5-...`) kuralı en dar ve en yüksek güvenli kalıptır. Mantığı basit:

```
selection:
    Image|endswith: '\Internet Explorer\iexplore.exe'
    ImageLoaded|endswith: '\Internet Explorer\iertutil.dll'
condition: selection
```

Yani: "`iexplore.exe`, `iertutil.dll`'i yüklerse alarm ver." Neden bu kadar kesin (`level: critical`)? Çünkü bu spesifik DLL, DCOM `InternetExplorer.Application` sınıfı üzerinden uzaktan hijack için bilinen bir vektördür; bu eşleşmenin görülmesi neredeyse her zaman lateral movement girişimidir. Buradaki ders: **belirli exe–DLL çiftleri istismar için "işaretli" olduğunda, o çifti doğrudan yakala**, bağlam gerektirmez.

### Kalıp B — DLL adı + "meşru yol değilse" (path-anchored) yaklaşımı
`Potential 7za.DLL Sideloading` (id `4f6edb78-...`) kuralı, DLL adının kendisini yakalar ama meşru dizinleri **dışlar (filter)**:

```
selection:
    ImageLoaded|endswith: '\7za.dll'
filter_main_legit_path:
    Image|startswith:
        - 'C:\Program Files (x86)\'
        - 'C:\Program Files\'
    ImageLoaded|startswith:
        - 'C:\Program Files (x86)\'
        - 'C:\Program Files\'
condition: selection and not 1 of filter_main_*
```

Mantık: "`7za.dll` yüklendiyse **ve** hem yükleyen `.exe` hem de DLL `Program Files` altında **değilse** alarm ver." Yani meşru kurulum yolları beyaz listeye alınır; kalan her şey (AppData, Temp, Public...) şüphelidir. `level: low` olması dikkat çekici — çünkü üçüncü parti meşru uygulamalar da `7za.dll`'i AppData'dan yükleyebilir, bu yüzden false positive potansiyeli yüksek ve ek filtre gerektirir. Bu, **allowlist (izinli yol) temelli** tespitin klasik örneğidir: "DLL var olabilir, önemli olan **nereden** yüklendiği."

### Kalıp C — Bilinen istismara açık DLL + şüpheli konum
`Abusable DLL Potential Sideloading From Suspicious Location` (id `799a5f48-...`) kuralı, tek bir uygulamaya bağlanamayan **jenerik, çok istismar edilen DLL'lerin** (`coreclr.dll`, `libcef.dll`, `ZIPDLL.dll`, `facesdk.dll`, `HPCustPartUI.dll`) **açıkça şüpheli klasörlerden** yüklenmesini arar:

```
selection_dll:
    ImageLoaded|endswith:
        - '\coreclr.dll'
        - '\libcef.dll'
        - '\ZIPDLL.dll'
        - ...
selection_folders_1:
    ImageLoaded|contains:
        - ':\Perflogs\'
        - ':\Users\Public\'
        - '\Temporary Internet'
```

Mantık: "Bu bilinen sideloading DLL'lerinden biri **ve** `PerfLogs`, `Users\Public`, `Temporary Internet Files` gibi normalde uygulama barındırmayan bir dizinden yüklendiyse alarm." Burada iki koşul **birlikte** aranır (DLL adı VE kötü konum) — bu, tek başına DLL adına göre alarmın yaratacağı gürültüyü kırar. Ders: **kötü DLL + kötü konum kesişimi**, tek boyutlu bir imzadan çok daha güvenlidir.

### Kalıp D — Uygulama-spesifik meşru yol doğrulaması
`Potential Antivirus Software DLL Sideloading` (id `552b6b65-...`) kuralı, antivirüs bileşenlerinin (`log.dll` gibi çok jenerik adlı) DLL'lerini yakalayıp, o ürünün **beklenen kurulum dizinini** filtre olarak kullanır:

```
selection_bitdefender:
    ImageLoaded|endswith: '\log.dll'
filter_log_dll_bitdefender:
    ImageLoaded|startswith:
        - 'C:\Program Files\Bitdefender Antivirus Free\'
        - 'C:\Program Files (x86)\Bitdefender Antivirus Free\'
```

Mantık: "`log.dll` yüklendiyse ama Bitdefender'ın gerçek kurulum yolundan **değilse** şüpheli." `log.dll` gibi son derece yaygın bir adın hijack için cazip olmasının nedeni de budur — o yüzden kural, meşru ürün yolunu bilerek dışlar. Ders: **jenerik DLL adları için, sahibi olan ürünün kanonik yolunu bilmek** ayırt ediciliğin anahtarıdır.

### Basit Sigma-benzeri tespit örnekleri

**Örnek 1 — İmzalı sistem bileşeninin yanlış konumdan DLL yüklemesi (genelleştirilmiş sideloading):**

```yaml
title: Sideloading Suphesi - Kullanici Yazilabilir Dizinden DLL Yukleme
logsource:
    category: image_load
    product: windows
detection:
    selection:
        ImageLoaded|contains:
            - '\AppData\Local\Temp\'
            - '\Users\Public\'
            - ':\PerfLogs\'
    filter_signed_ok:
        Signed: 'true'
        SignatureStatus: 'Valid'
    condition: selection and not filter_signed_ok
level: medium
```
Mantık: Kullanıcı-yazılabilir dizinlerden yüklenen DLL'ler arasında, imzası geçerli olmayanlara alarm ver. `Signed` / `SignatureStatus` alanları Sysmon EID 7'den gelir. Bu, "yer + imza" kesişimidir.

**Örnek 2 — İmzalı exe / imzasız DLL uyumsuzluğu (known-pair mantığının genellemesi):**

```yaml
title: Imzali Surec Imzasiz DLL Yukluyor
logsource:
    category: image_load
    product: windows
detection:
    selection:
        ImageLoaded|endswith: '.dll'
        Signed: 'false'
    filter_system_paths:
        ImageLoaded|startswith:
            - 'C:\Windows\System32\'
            - 'C:\Program Files\'
            - 'C:\Program Files (x86)\'
    condition: selection and not filter_system_paths
level: low
```
Mantık: İmzasız DLL'lerden, sistem/uygulama dizinleri dışında yüklenenleri işaretle. Tek başına gürültülüdür (bu yüzden `level: low`), ama Kalıp A/B/D ile birleştirilerek zenginleştirme sinyali olarak kullanılır.

**Eşik ve önceliklendirme:** Gerçek kuralların seviyeleri iyi bir rehberdir — bilinen kötü çift (`iertutil.dll`) = `critical`, jenerik DLL + geniş filtre (`7za.dll`) = `low`. Pratikte SOC, `critical`/`high` kuralları anında incelemeye, `low` kuralları ise korelasyon/hunting bağlamına alır. Tekil EID 7 alarmı nadiren tek başına aksiyon aldırır; değeri, ProcessCreate (EID 1) ve NetworkConnection (EID 3) ile **zincir** haline geldiğinde ortaya çıkar.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırganın tespiti atlatma yolları (ve savunmacının cevabı)

**1. Meşru dizinden çalıştırma (path filter'ları atlatma).**
Kalıp B ve D, DLL'in `Program Files` dışından gelmesine dayanır. Saldırgan, hedef uygulama zaten kullanıcı-yazılabilir bir yola kurulmuşsa (bazı üçüncü parti araçlar AppData'ya kurulur) ya da meşru klasöre yazma yetkisi ele geçirmişse, filtreyi tetiklemeden DLL'i "meşru" yola koyabilir.
*Savunma:* Yalnızca konuma değil, **imza + hash + OriginalFileName** uyumuna bak. `ImageLoaded` yolu doğru olsa bile `Signed: false` veya `OriginalFileName` beklenenle uyuşmuyorsa şüphelen. Kalıp A gibi **known-pair** kuralları konumdan bağımsız olduğu için bu kaçışa dirençlidir.

**2. Zararlı DLL'i imzalama / imza taklidi.**
Saldırgan DLL'ini geçerli bir sertifikayla imzalarsa `Signed: true` olur ve imza tabanlı filtreleri atlatır.
*Savunma:* İmza **varlığına** değil, **kime ait olduğuna** bak. `Signature` (imzalayan kurum) alanı, DLL'i yükleyen ürünün üreticisiyle uyumsuzsa (ör. bir sıkıştırma aracının yüklediği DLL bambaşka bir firmaca imzalanmışsa) bu güçlü bir sinyaldir. Ayrıca sertifika itibar/thumbprint allowlisting uygulanır.

**3. Farklı/az bilinen DLL adı seçme.**
Bilinen kurallar belirli DLL adlarına (`7za.dll`, `coreclr.dll`, `log.dll`...) demirlidir. Saldırgan, kural listelerinde olmayan başka bir sideload-edilebilir DLL seçerse ad-tabanlı seçimleri atlatır.
*Savunma:* Ad listelerini `hijacklibs.net` gibi topluluk kaynaklarıyla güncel tut (Antivirüs kuralı zaten bu kaynağa referans verir). Ayrıca **davranışsal** kuralla tamamla: "imzalı `.exe`, kullanıcı-yazılabilir dizinden **daha önce hiç görülmemiş** bir DLL yüklüyor" (baseline/anomali yaklaşımı) ad-bağımsızdır.

**4. Meşru sürecin içine kod enjekte edip DLL'i diskten yüklememe.**
İleri saldırgan reflective/manual DLL loading ile DLL'i diske hiç yazmadan bellekte yükleyebilir; bu durumda EID 7 (Image Load) çoğu zaman tetiklenmez.
*Savunma:* Bu tekniği image_load tespiti kaçırabilir; bunun için ayrıca process access / remote thread (Sysmon EID 8, EID 10) ve bellek tarama telemetrisi gerekir. Yani DLL sideloading tespiti, diske-düşen klasik varyanta güçlüdür; fileless varyant ayrı bir tespit yüzeyidir.

**5. Zamanlama ve gürültüye karışma.**
Saldırgan DLL'i, meşru bir güncelleme/kurulum sırasında bırakarak FileCreate gürültüsüne karışabilir.
*Savunma:* FileCreate (EID 11) → ImageLoad (EID 7) → NetworkConnection (EID 3) **zinciri** ve kısa zaman penceresi korelasyonu, tekil olayların kaybolduğu gürültüde deseni ortaya çıkarır.

### Tipik false positive kaynakları ve ayıklama

- **Meşru üçüncü parti uygulamalar AppData'dan çalışır.** `7za.dll` kuralının kendi notunda belirtildiği gibi, AppData'ya kurulan meşru araçlar sıkıştırma işlevi için bu DLL'i yükleyebilir. *Ayıklama:* bu uygulamaların bilinen kurulum yollarını ve hash'lerini organizasyona özel allowlist'e ekle.
- **Kurumsal yazılım dağıtımı / installer'lar.** Kurulum sırasında imzalı exe'ler geçici dizinlerden çalışıp DLL yükler; bu meşru sideloading'e benzer. *Ayıklama:* bilinen dağıtım araçlarının (SCCM, Intune, PDQ vb.) `ParentImage` ve imza bağlamına göre filtre.
- **Antivirüs/EDR bileşenleri.** `log.dll` kuralındaki Dell SARemediation `TelemetryUtility.exe` istisnası tam da bunun için var — meşru güvenlik ürünleri jenerik adlı DLL'ler yükler. *Ayıklama:* ürünün kanonik `Image` yolunu ve imzalayanını filtre olarak ekle (kuralın `filter_log_dll_dell_sar` yaptığı gibi).
- **Portable uygulamalar / geliştirici araçları.** Geliştiriciler USB veya proje klasörlerinden portable araç çalıştırır; bu, "suspicious location"lardan meşru DLL yüklemeye benzer. *Ayıklama:* geliştirici makinelerini ayrı bir baseline'a al, host/kullanıcı bağlamıyla önceliklendir.

### Pratik savunma özeti

DLL Hijacking tespitinin özü **tek bir sihirli imza değil, kesişimlerdir**: (a) bilinen kötü exe–DLL çiftleri (Kalıp A), (b) DLL adı + meşru-olmayan yol (Kalıp B/D), (c) istismara açık DLL + açıkça kötü konum (Kalıp C), (d) imza/imzalayan uyumsuzluğu, (e) FileCreate→ImageLoad→NetworkConnection zinciri. Bunları Sysmon EID 7'yi merkeze alıp EID 1/3/11 ile zenginleştirerek kurduğunda, hem klasik sideloading'i yakalar hem de false positive'i yönetilebilir tutarsın. Ve en baştaki ilkeye dönersek: bu tekniğin neyi istismar ettiğini — imzalı sürece duyulan güveni ve arama sırasını — anladığın için, artık o güvenin nerede kötüye kullanıldığını log içinde görebiliyorsun.
