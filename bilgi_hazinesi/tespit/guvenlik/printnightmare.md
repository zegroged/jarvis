# PrintNightmare (Spooler) — Tespit

> Saha notu. Bu metin "PrintNightmare nedir" anlatmaz; onu zaten biliyorsun. Bu metin, gerçek bir SOC'ta bu saldırıyı **yakalarken neyin bozulduğunu**, tek sinyalin neden yalan söylediğini ve yüksek güvenli bir tespiti hangi korelasyonla kurduğunu anlatır. CVE-2021-34527 (RCE) ve kardeşi CVE-2021-1675 (LPE) üzerinden.

---

## 1. Özet: saldırı + naif tespit

PrintNightmare, Windows Print Spooler servisinin (`spoolsv.exe`) `RpcAddPrinterDriverEx` çağrısında sürücü yükleme yetkisini yeterince doğrulamamasını sömürür. Saldırgan, kimliği doğrulanmış bir kullanıcı olarak Spooler'a kötü niyetli bir "yazıcı sürücüsü" DLL'i yükletir. Spooler `SYSTEM` yetkisiyle çalıştığı için bu DLL de `SYSTEM` olarak yüklenir. İki varyant var: yerel yetki yükseltme (LPE, CVE-2021-1675) ve uzaktan kod çalıştırma (RCE, CVE-2021-34527) — RCE'de sürücü DLL'i bir UNC yolundan (`\\attacker\share\evil.dll`) çekilir.

**Naif tespit** genelde şu üçünden biridir:

- `spoolsv.exe`'nin bir çocuk süreç (child process) doğurmasını izlemek — özellikle `cmd.exe`, `rundll32.exe`, `powershell.exe`.
- `%SystemRoot%\System32\spool\drivers\x64\3\` altına yeni DLL yazılmasını (file create) izlemek.
- Mimikatz `misc::printnightmare` anahtar kelimesini loglarda aramak (verilen `Mimikatz Use` Sigma kuralı bunu yapıyor: `keywords` listesinde `misc::printnightmare` ve `Kiwi Legit Printer` var).

Bu üçü de doğru sinyaller. Ama tek başlarına ne kör noktaları kapatır ne de false positive selini durdurur. Asıl iş bunları bağlamakta.

Bir noktayı baştan netleştireyim, çünkü sahada en çok burada zaman kaybedilir: PrintNightmare "tek bir olay" değildir. RpcAddPrinterDriverEx sömürüsünün diskte, bellekte, RPC katmanında ve print servis loglarında **birbirinden bağımsız dört farklı ayak izi** vardır ve hangi ayak izinin görüneceği tamamen payload'un nasıl yazıldığına bağlıdır. Bir tespit mühendisi olarak işin, bu dört yüzeyden hangilerini logladığını bilmek ve kuralı **görebildiğin** yüzeye kurmaktır. Görmediğin yüzeye kural yazmak, kâğıt üzerinde "PrintNightmare tespitimiz var" demenin en yaygın ve en tehlikeli biçimidir — çünkü kırmızı takım POC'unu yakalar, gerçek operatörü ıskalar.

---

## 2. Naif tespit neden yetmez

### Kör nokta 1: "Spooler child process" tüm exploitlerde yoktur

Tespit ekiplerinin en yaygın yanlış varsayımı: "PrintNightmare olursa `spoolsv.exe` bir `cmd.exe` doğurur." Bu, yalnızca payload bir komut satırı çalıştıran POC'lerde doğrudur. Gerçek saldırıda yüklenen DLL `DllMain` içinde doğrudan kendi işini yapar — beacon açar, `lsass`'a token çalmak için gider, bir servis kurar — ve **hiç çocuk süreç doğurmaz**. Süreç ağacında görünür hiçbir şey olmayabilir; kötü kod zaten `spoolsv.exe`'nin kendi bellek alanında `SYSTEM` olarak çalışıyordur. Yani süreç-oluşturma temelli tek kural, in-memory payload'da tamamen kördür.

Burada ikinci-derece iz devreye girer: DLL, `SYSTEM` olarak bir uzak thread enjekte etmek isterse, verilen **`Remote Thread Creation In Uncommon Target Image`** kuralı (id `a1a144b7-5c9b-4853-a559-2172be8d4a03`) `TargetImage|endswith` listesinde `\spoolsv.exe` içerir. Yani `spoolsv.exe`'ye *dışarıdan* enjeksiyon da, `spoolsv.exe`'den *dışarıya* çıkan hareket de ayrı kurallarla yakalanabilir — ama create_remote_thread kategorisi (Sysmon Event ID 8) çoğu kurumda kapalıdır. Kör nokta genelde teknik değil, **loglama eksikliğidir**.

Dikkat: bu kural `spoolsv.exe`'yi bir enjeksiyon **hedefi** olarak listeler; yani başka bir sürecin Spooler'a kod enjekte etmesini yakalar. PrintNightmare'de asıl senaryo çoğu zaman tersidir — kötü DLL zaten `spoolsv.exe`'nin *içinde* çalışır ve oradan `lsass`'a veya başka bir hedefe enjekte eder. O durumda `Rare Remote Thread Creation By Uncommon Source Image` kuralının mantığına ihtiyacın var ama `SourceImage`'a `\spoolsv.exe` eklenmiş haline. Verilen kural `spoolsv.exe`'yi kaynak listesinde saymıyor (çünkü Spooler'ın meşru olarak thread açtığı senaryolar var), bu yüzden bu iki kuralı olduğu gibi almak yetmez; PrintNightmare bağlamında `spoolsv.exe`'yi hem kaynak hem hedef olarak değerlendiren özel bir varyant gerekir. Bu, "hazır Sigma'yı indir, aç, bitti" ile "kuralın hangi yönü kapsadığını okuyup boşluğu görmek" arasındaki farktır.

### Kör nokta 2: DLL yolu tek sabit değildir

Naif kural sürücü dizinini `drivers\x64\3\` diye sabitler. Gerçekte sürücü sürüm klasörü değişir (`\3\`, bazen farklı alt yollar), mimari `x64` yerine farklı olabilir, ve RCE varyantında DLL diskte hedef makinede hiç oturmadan doğrudan UNC'den yüklenebilir. Dosya-oluşturma kuralını dizine göre sabitlemek, atlatmayı bir yol değişikliğine indirger.

### Atlatma: LOLBAS ve meşru araç kılıfı

Saldırgan `spoolsv.exe`'nin doğurduğu süreci gizlemek için `rundll32.exe` gibi meşru bir ikili kullanır — verilen **`Rare Remote Thread Creation By Uncommon Source Image`** kuralının (id `02d1d718-...`) `SourceImage|endswith` listesindeki `\rundll32.exe`, `\cscript.exe` gibi LOLBAS'lar tam da bu yüzden şüphelidir. Ama `rundll32.exe` günde binlerce kez meşru çalışır; tek başına alarm çöp üretir.

### False positive seli: yazdırma altyapısının kendisi

Print Spooler her gün meşru olarak yeni sürücü yükler: yeni yazıcı kurulumu, sürücü güncellemesi, GPO ile dağıtılan yazıcılar, print server'lar. Yani `spool\drivers` altına DLL yazılması **normal iştir**. `spoolsv.exe`'nin `conhost.exe` doğurması (verilen **`Conhost Spawned By Uncommon Parent`** kuralı bağlamında) bile bazı yazıcı sürücülerinde meşrudur. Tek boyutlu bir "yeni DLL yazıldı" kuralı, aktif bir print server'da saatte onlarca alarm üretir ve ekip onu **iki gün içinde kapatır** — bu tespitin gerçek ölümü budur: alarm yorgunluğu, kör noktadan daha çok tespit öldürür.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek güven, farklı bağlamlardaki sinyalleri **kısa bir zaman penceresinde** birbirine bağlamaktan gelir. PrintNightmare için pratik zincirim:

**Zincir A — RCE, uzaktan DLL yüklemesi (en yüksek güven):**

```
A: spoolsv.exe içeren süreç, kısa pencerede yeni DLL'e file-create yapar
   (ImageLoaded veya FileCreate, path: ...\spool\drivers\... )
+  (≤ 5 sn) 
B: AYNI spoolsv.exe bir UNC yolundan DLL yükler
   (ImageLoaded, Image başlangıcı '\\' — network path)
+  (≤ 10 sn)
C: spoolsv.exe kaynaklı anormal davranış:
   - child process (cmd/powershell/rundll32), VEYA
   - create_remote_thread TargetImage=\spoolsv.exe (kural a1a144b7),
     VEYA SourceImage=\spoolsv.exe dışarı enjeksiyon
=  YÜKSEK GÜVENLİ İHLAL
```

Tek başına A (DLL yazıldı) meşru sürücü kurulumudur. Tek başına C (spoolsv child) nadir ama açıklanabilir. Ama **A + B + C aynı `spoolsv.exe` PID'inde, saniyeler içinde** — bunun meşru bir açıklaması yoktur. Meşru sürücü kurulumu UNC'den `SYSTEM` olarak DLL çekip hemen ardından remote thread enjekte etmez.

**Zincir B — kimlik bilgisi hedefi (post-exploitation ile birleştirme):**

PrintNightmare çoğu zaman kendisi hedef değil, `SYSTEM`'e ulaşmak için bir basamaktır. Bir sonraki adım neredeyse her zaman kimlik bilgisi hasadıdır. Bu yüzden Spooler anomalisini kimlik erişimiyle bağlarım:

```
A: spoolsv.exe anormalisi (yukarıdaki C)
+  (≤ 60 sn)
D: Mimikatz göstergesi — verilen 'Mimikatz Use' kuralı (06d71506-...)
   'lsadump::', 'kerberos::ptt', 'dpapi::masterkey' anahtar kelimeleri,
   VEYA lsass'a yönelik process access (Sysmon EID 10, GrantedAccess 0x1010/0x1410)
=  Yetki yükseltme + kimlik hasadı zinciri → kritik
```

Buradaki incelik: `misc::printnightmare` anahtar kelimesi (aynı Mimikatz kuralında) hem sömürüyü hem de aracı tek satırda ele verir. Ama olgun saldırgan Mimikatz'ı diskten çalıştırmaz; bu anahtar kelime kuralı imza-temellidir ve **komut satırı yeniden adlandırma / in-memory PPL bypass** ile atlatılır. Bu yüzden D adımını sadece anahtar kelimeye değil, `lsass` erişim davranışına da bağlamak gerekir.

**Neden bu zincir çalışır:** Her adımın kendi false positive profili farklıdır. A'nın FP'si print server'lardır; B'nin FP'si neredeyse yoktur (Spooler UNC'den sürücü yüklemez); C'nin FP'si bazı sürücü kurulumlarıdır; D'nin FP'si güvenlik tarayıcılarıdır. Bir olayın **hepsinde birden** FP olması istatistiksel olarak neredeyse imkânsız — korelasyonun matematiği budur. İki bağımsız sinyalin FP oranı %1 ise, kesişimlerinin FP oranı (bağımsızlarsa) %0.01'e iner; üç sinyalde milyonda birlere düşer. Korelasyonun değeri buradan gelir, "daha çok kural"dan değil.

**Zaman penceresini nasıl seçersin:** Pencere ne kadar geniş olursa o kadar çok FP yakalar, ne kadar dar olursa gerçek zinciri kaçırma riski artar. Pratikte A→B için ≤5 sn agresif ama doğru — exploit bu adımları programatik ve ardışık yapar, insan hızında değil. A→C için ≤10 sn, çünkü DLL yüklendikten sonra beacon/enjeksiyon başlaması milisaniyeler sürer. A→D için ≤60 sn daha gevşek, çünkü operatör `SYSTEM` aldıktan sonra kimlik hasadına geçmeden önce keşif yapabilir. Bu pencereleri kurumundaki gerçek exploit tatbikatı (purple team) verisiyle kalibre et; tahminle değil, ölçümle.

**Korelasyonu SIEM'de nasıl kurarsın:** Splunk'ta `transaction` yerine `stats ... by process_guid` (Sysmon ProcessGuid aynı PID'i garanti eder, PID yeniden kullanımına bağışıktır) tercih et; Sentinel'de `DeviceEvents`/`DeviceImageLoadEvents` tablolarını `InitiatingProcessId` + `Timestamp` bin'iyle `join`; Elastic'te EQL `sequence by process.entity_id with maxspan=10s`. EQL'in `sequence` yapısı bu iş için biçilmiş kaftandır çünkü sıra ve zaman penceresini dilin kendisi zorlar.

---

## 4. False positive gerçeği ve triage yargısı

Sahada bu kuralı açtığında gelen "gürültü" gerçek kaynakları:

1. **Print server'lar ve baskı kümeleri.** En büyük FP kaynağı. Aktif bir print server, `spool\drivers` altına gün boyu yazar. Yargı: print server rollerini varlık envanterinden (asset inventory) çıkar, bu sunucularda A adımını baskıla ama B (UNC yükleme) ve C (child/enjeksiyon) adımlarını **baskılama** — çünkü meşru print server bile UNC'den sürücü çekip `powershell` doğurmaz.

2. **SCCM / yazılım dağıtımı.** SCCM yazıcı sürücülerini iter, bu meşru DLL yazımı üretir. Yargı: SCCM istemci sürecinin (`ccmexec.exe`) parent olduğu zincirleri güven listesine al — ama yalnızca file-create adımı için, enjeksiyon adımı için değil.

3. **Yedekleme ve EDR ajanları.** Bazı yedek/EDR ajanları `spoolsv`'ye legit kod enjekte eder veya remote thread açar. `Remote Thread Creation In Uncommon Target Image` kuralı bunlarla dolar. Yargı: kuralın kendi `filter_main_*` blokları (verilen kuralda `csrss.exe` ve sistem yollarını dışlıyor) yetmez; kurumdaki EDR/yedek ajanının `SourceImage` yolunu kendin ekle.

4. **Güvenlik tarayıcıları / pentest araçları.** Mimikatz anahtar kelime kuralı, bir tarayıcı imza veritabanı veya bir kırmızı takım deposu diske indiğinde bile tetiklenir — çünkü `lsadump::` metni bir dosya içeriğinde geçebilir. Yargı: anahtar kelime eşleşmesini komut satırı / süreç bağlamıyla sınırla, ham dosya içeriği taramasından ayır.

**Analistin öncelik sırası (triage):**

1. Önce **B adımı var mı** diye bak — UNC'den Spooler sürücü yüklemesi neredeyse hiç meşru değildir; varsa en tepeye al.
2. Sonra **süreç bağlamı**: `spoolsv.exe` gerçekten sürücü mü yüklüyor yoksa `powershell`/`rundll32` mu doğuruyor? İkincisi kritik.
3. **Varlık türü**: makine print server mı? Değilse ve sürücü yazılıyorsa şüphe katsayısı çok yükselir.
4. **Zaman yoğunluğu**: adımlar saniyeler içinde mi? Meşru sürücü kurulumu dakikalar sürer ve kullanıcı etkileşimi içerir; exploit saniyeler içindedir.
5. **Kimlik erişimi takibi** (D): olaydan sonraki 1-2 dakikada `lsass` erişimi geldiyse eskale et.

Yanlış öncelik: yeni analistler önce Mimikatz anahtar kelimesine koşar çünkü "kesin kanıt" gibi görünür. Ama o adım en kolay atlatılandır ve en çok FP üretendir. Doğru başlangıç noktası B (UNC yükleme) ve C'nin (davranış) kesişimidir.

---

## 5. Kaçınma → karşı-tespit

Dokümanlarda yazmayan, sahada gördüğüm atlatmalar ve bunların ikinci-derece tespiti:

**Atlatma 1 — Child process hiç doğurmamak.** Payload tümüyle `DllMain` içinde in-memory çalışır. Süreç-ağacı kuralları kördür.
**Karşı-tespit:** Süreç oluşturma yerine **modül yükleme (ImageLoad, Sysmon EID 7)** izle. `spoolsv.exe`'nin yüklediği DLL'lerin **imza durumu ve yolu** anomalidir: imzasız DLL, kullanıcı-yazılabilir dizinden yükleme, veya UNC yükleme. Meşru yazıcı sürücüleri neredeyse her zaman imzalıdır (WHQL). "spoolsv imzasız DLL yükledi" tek başına güçlü bir sinyaldir ve child-process atlatmasına bağışıktır.

**Atlatma 2 — LOLBAS ile gizlenme.** Çocuk süreç `rundll32.exe` ise, "spoolsv → cmd.exe" kuralı ıskalar.
**Karşı-tespit:** Parent-child ilişkisini image adına göre değil, **parent = spoolsv.exe + child'ın alışılmadıklığı** kombinasyonuyla kur. `Rare Remote Thread Creation By Uncommon Source Image` kuralının `\rundll32.exe`'yi zaten şüpheli LOLBAS sayması bunun için. `spoolsv.exe` parent'ının doğurduğu **herhangi** bir süreç (allowlist dışı) şüphelidir — allowlist yaklaşımı (izin verilmeyenleri değil, izin verilenleri say) burada blocklist'ten üstündür.

**Atlatma 3 — Sürücü dizinini/yolunu değiştirme, sürüm klasörü oynatma.** Yol-sabitli file-create kuralını ıskalatır.
**Karşı-tespit:** Yolu değil **davranışı** sabitle: "`spoolsv.exe` bir DLL'i file-create yaptı VE aynı PID onu ImageLoad etti" — dizin adından bağımsız. Yol filtresini genişletme yarışına girme; süreç kimliğine (PID) ve zaman yakınlığına dayan.

**Atlatma 4 — Named pipe / RPC seviyesinde kalıp EDR telemetrisinden kaçmak.** Bazı varyantlar sömürüyü RPC katmanında yapıp diske hiç DLL düşürmemeye çalışır.
**Karşı-tespit:** **Windows-PrintService/Operational** log kanalı (özellikle Event ID 808 — "The print spooler failed to load a plug-in module" ve sürücü yükleme olayları) sömürü denemesinde, DLL bozuk/engellenmiş olsa bile iz bırakır. Bu kanal varsayılan kapalıdır; açmak PrintNightmare tespitinde en yüksek getirili tek ayardır. EDR süreç telemetrisi kör olduğunda bu operasyonel log konuşur.

**Atlatma 5 — `Point and Print` kötüye kullanımı.** GPO ile `Point and Print` gevşek bırakılmışsa, saldırgan istemciye "sürücü" iterek `NoWarningNoElevationOnInstall` üzerinden yükselir; bu klasik exploit imzasına benzemez.
**Karşı-tespit:** Registry izleme — `HKLM\...\PointAndPrint` altındaki `NoWarningNoElevationOnInstall` ve `UpdatePromptSettings` değerlerinin değişimi. Bu bir yapılandırma sinyalidir, süreç sinyali değil; süreç-temelli tespitin tamamen dışında ikinci bir katman. Ek olarak, kurumdaki azaltma (mitigation) durumunu da tespit yüzeyi olarak izle: Microsoft'un yayımladığı yamalar sonrası `RestrictDriverInstallationToAdministrators` değeri `1` olmalı; bu değerin `0`'a çekilmesi ya bir yanlış yapılandırmadır ya da saldırganın sömürü için zemin hazırlamasıdır — her ikisi de alarm konusudur.

**Atlatma 6 — Diske hiç dokunmadan, tamamen imzalı bir "proxy" DLL kullanma.** Olgun operatör, imzalı ama savunmasız (vulnerable/hijack edilebilir) bir DLL'i yükleterek imza-temelli "imzasız DLL" kuralını atlatmaya çalışır.
**Karşı-tespit:** Sadece imza durumuna değil, **imzalayanın kimliğine ve DLL'in yüklendiği yola** bak. `SYSTEM` olarak çalışan `spoolsv.exe`'nin, kullanıcı profilinden veya `Temp`/`Downloads` gibi kullanıcı-yazılabilir bir dizinden — imzalı olsa bile — DLL yüklemesi anomalidir. Meşru sürücüler `System32\spool\drivers` veya `DriverStore` altından gelir; imza geçerli ama **yol yanlışsa** sinyal hâlâ güçlüdür. İmza tek başına güven kararı olamaz; imza + yol + yükleyen sürecin bağlamı birlikte değerlendirilir.

---

## 6. SIEM / saha gerçeği

**Field mapping — platformlar arası farklar.** Verilen Sigma kuralları `Image`, `SourceImage`, `TargetImage`, `ParentImage`, `SourceImage|endswith` alanlarını kullanır; bunlar **Sysmon** şemasıdır. Gerçekte:

- **Splunk (Sysmon TA ile):** `Image`, `ParentImage`, `SourceImage`, `TargetImage` genelde CIM'e map edilir ama create_remote_thread (EID 8) çoğu kurumda `WinEventLog:Microsoft-Windows-Sysmon/Operational` içinde toplanmaz — Sysmon config'de `<CreateRemoteThread onmatch>` bloğu kapalıysa `TargetImage=\spoolsv.exe` kuralı **hiçbir zaman veri görmez**. Kuralı açmadan önce `index=... EventCode=8` sorgusuyla veri var mı diye bak.
- **Microsoft Sentinel (MDE):** Alan adları tamamen farklıdır. `Image` → `FolderPath`/`InitiatingProcessFolderPath`, `ParentImage` → `InitiatingProcessParentFileName`, remote thread → `DeviceEvents` tablosunda `ActionType == "CreateRemoteThreadApiCall"`, ImageLoad → `DeviceImageLoadEvents`. Sigma'yı olduğu gibi taşıyamazsın; `spoolsv.exe`'nin yüklediği imzasız DLL sorgusu `DeviceImageLoadEvents | where InitiatingProcessFileName == "spoolsv.exe" and IsTrusted == false` olur.
- **Elastic (ECS):** `Image` → `process.executable`, `ParentImage` → `process.parent.executable`, `TargetImage` → `process.Ext.target...` (Elastic'in kendi genişletmesi). Elastic'te ImageLoad `library` event category'de gelir; imza durumu `dll.code_signature.trusted`.

**Varsayılan loglanmayan, kritik olan:**

1. **Sysmon EID 7 (ImageLoad)** — çok gürültülü olduğu için çoğu Sysmon config'inde ya kapalı ya da agresif filtrelidir. Ama PrintNightmare'in child-process-yapmayan varyantı **yalnızca** burada görünür. `spoolsv.exe` için ImageLoad'ı hedefli açmak (sadece bu süreç için) hem gürültüyü sınırlar hem kör noktayı kapatır.
2. **Sysmon EID 8 (CreateRemoteThread)** — verilen iki remote-thread kuralının veri kaynağı. Varsayılan config'lerde sık kapalı.
3. **Microsoft-Windows-PrintService/Operational** — Windows'ta varsayılan **kapalı**. Event ID 808/810 sürücü yükleme hatalarını, plug-in yüklemelerini gösterir. GPO veya `wevtutil sl Microsoft-Windows-PrintService/Operational /e:true` ile açılır.
4. **Sysmon EID 10 (ProcessAccess)** — D adımındaki `lsass` erişimi için. GrantedAccess maskeleri (`0x1010`, `0x1410`) çok gürültülüdür; `lsass.exe` hedefine daralt.

**Tuning gerçeği.** Bu kuralları "aç ve unut" yapamazsın. Sıra:

1. Önce **7 gün gözlem modunda** çalıştır, alarm yazma. Print server'ları, SCCM'i, EDR/yedek ajanlarını FP olarak topla.
2. Bu meşru kaynakları `SourceImage`/`InitiatingProcess` bazında dışla — **yol ve imza ile**, sadece isimle değil (isim taklit edilir).
3. Tek-adım kuralları alarm seviyesinden **sinyal (correlation input)** seviyesine indir; sadece korelasyon zinciri (Bölüm 3) alarm üretsin.
4. `misc::printnightmare` ve `Kiwi Legit Printer` anahtar kelimelerini (verilen Mimikatz kuralından) **yüksek öncelikli ama düşük hacimli** tut — bunlar nadir tetikler ve tetiklerse gerçek olma olasılığı yüksektir; ama tek başına eskalasyon değil, zincire girdi say.

**Veri kaynağı önceliği — sınırlı bütçeyle nereye yatırım yaparsın:** Her kurumda Sysmon EID 7'yi (ImageLoad) tam açacak depolama/lisans bütçesi yoktur; bu event tek başına EPS'in (event per second) yarısını yiyebilir. Bu yüzden hedefli aç: Sysmon config'de sadece `spoolsv.exe`'nin yüklediği modülleri logla (`<ImageLoad onmatch="include"><Image condition="end with">spoolsv.exe</Image></ImageLoad>`). Bu, gürültüyü %95 kırpar ve PrintNightmare kör noktasını kapatır. Aynı disiplinle PrintService/Operational kanalını aç; bu kanal düşük hacimlidir (yazdırma altyapısı olayları saniyede binlerce değildir) ama getirisi yüksektir. Bütçe sıralaması: (1) PrintService/Operational — ucuz ve yüksek getiri, (2) spoolsv-hedefli ImageLoad — orta maliyet yüksek getiri, (3) EID 8 CreateRemoteThread spoolsv filtresi, (4) EID 10 ProcessAccess lsass hedefli.

**Bir uyarı — telemetri boşluğunu kapatmadan kural açma tuzağı:** Sık gördüğüm bir olgunluk yanılsaması, ekibin Sigma deposundan PrintNightmare kurallarını içeri alıp "kapsama var" kutucuğunu işaretlemesidir; oysa alttaki EID 7/8 kaynağı hiç toplanmıyordur. Kural motoru hata vermez, sadece **hiçbir zaman veri görmez** — sessiz bir kör nokta, açık bir boşluktan daha tehlikelidir çünkü yanlış güven verir. Her kuralı açarken şu soruyu sor: "Bu kuralın sorguladığı alan, önümüzdeki 24 saatte gerçekten bu SIEM'e akıyor mu?" Cevap "emin değilim" ise kural değil, önce veri hattı üzerinde çalış.

**Kapsama doğrulaması (validation):** Kuralları açtıktan sonra bir kontrollü test şart. Atomic Red Team T1547/T1068 testlerini veya bir izole makinede public POC'u (yalnızca imzalı, zararsız bir DLL yükleten sürümünü) çalıştır; zincirin her adımının — A, B, C, D — SIEM'de gerçekten tetiklendiğini gör. Tetiklenmeyen adım, kör noktan demektir; kâğıttaki kapsama değil, tetiklenmiş kapsama gerçektir.

**Son yargı.** PrintNightmare tespitinde başarı, daha çok kural yazmaktan değil, **doğru üç sinyali (imzasız/UNC modül yükleme + spoolsv davranış anomalisi + kimlik erişimi) tek PID ve dar zaman penceresinde bağlamaktan** gelir. Naif "spoolsv child" kuralı ne kör noktayı kapatır ne FP'yi keser; ama modül-yükleme temelli tespit + PrintService/Operational logu + korelasyon, hem in-memory atlatmaya bağışıktır hem de print server gürültüsünde boğulmaz. Loglama boşluklarını (EID 7, EID 8, PrintService/Operational) kapatmadan hiçbir kural seti bu saldırıyı güvenilir yakalamaz — burada tespitin en zayıf halkası kural değil, **açık olmayan log kanalıdır**.
