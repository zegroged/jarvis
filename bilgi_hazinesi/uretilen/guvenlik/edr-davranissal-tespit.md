# EDR ve Davranışsal Tespit

## Giriş ve Tanım

EDR (Endpoint Detection and Response), uç noktalarda (endpoint) çalışan işlemleri, dosya erişimlerini, ağ bağlantılarını, registry değişikliklerini ve process oluşturma olaylarını sürekli izleyen, bu telemetriyi merkezî bir arka uca akıtan ve şüpheli davranışları tespit edip yanıt (response) verebilen bir güvenlik teknolojisidir. Klasik antivirüsten (AV) temel farkı şudur: AV çoğunlukla dosya tabanlı ve imza (signature) odaklı çalışır, "bu dosyanın hash değeri kötü listesinde mi?" sorusunu sorar. EDR ise dosyanın ne olduğundan çok, sistemde **ne yaptığına** bakar. Bir dosyanın imzası temiz olabilir, hatta dosya hiç olmayabilir (fileless saldırılar), ama davranış zinciri kötü niyeti ele verir.

Bu makale davranışsal tespitin dört ekseni etrafında dönüyor: process ağacı (process tree), şüpheli komut satırı analizi, IOA ile IOC arasındaki kavramsal fark ve son olarak EDR bypass teknikleri ile bunlara karşı savunma. Amaç, hem saldırganın neden belirli yollara başvurduğunu hem de savunmacının bu yolları neden ve nasıl kapatabileceğini akıl yürüterek göstermek.

## Kök Neden: EDR Neden Davranışa Bakmak Zorunda?

Bunun kök nedeni neredeyse matematikseldir. İmza tabanlı tespit, sonlu bir "kötü" kümesini tanımaya çalışır. Ancak saldırgan tek bir bayt değiştirerek (polymorphism), payload'ı runtime'da çözerek (packing/crypting) veya hiç dosya diske yazmadan (living-off-the-land) imza kümesinin dışına kolayca çıkabilir. İmza uzayı sonsuz genişleyebilirken, imza veritabanı hep bir adım geridedir. Buna karşılık, saldırganın **hedefe ulaşmak için yapması gereken eylemler** görece sabittir. Bir credential çalmak isteyen saldırgan, er ya da geç LSASS process'inin belleğine erişmek zorundadır. Bir persistence kurmak isteyen, registry'de bir Run anahtarı, bir scheduled task veya bir service yaratmak zorundadır. İşte bu "zorunluluk", davranışsal tespitin dayanak noktasıdır. Payload'ın kılığını değiştirmek ucuzdur; hedefe giden davranışsal yolu değiştirmek pahalıdır. EDR bu asimetriyi sömürür.

Bunu somutlaştıran çerçeve MITRE ATT&CK'tir. ATT&CK, saldırganların gerçek dünyada gözlemlenmiş taktik (neden yaptığı) ve tekniklerini (nasıl yaptığı) kataloglar. Davranışsal tespit kuralları çoğu zaman bu tekniklere referansla yazılır: "T1003 Credential Dumping'i gösteren davranış deseni nedir?" gibi. Böylece tespit, tekil bir örnek yerine tüm bir teknik ailesini hedefler.

## Process Ağacı: Tespitin Omurgası

### Neden Process Ağacı Önemli?

Windows'ta ve Unix türevlerinde her process'in bir ebeveyni (parent) vardır. Bir process başka bir process'i başlattığında, çekirdek bu ilişkiyi kaydeder: PPID (Parent Process ID). Bu ebeveyn-çocuk ilişkileri zinciri bir ağaç oluşturur. Davranışsal tespitin en güçlü tek sinyali çoğu zaman bu ağaçtır, çünkü **normal yazılımların process ağaçları öngörülebilir bir düzene sahiptir, saldırı ise bu düzeni bozar.**

Örneğin normal bir kullanıcı `winword.exe` (Microsoft Word) çalıştırdığında, bu process'in ebeveyni tipik olarak `explorer.exe`'dir (kullanıcı çift tıklamıştır) ve Word'ün çocukları da genellikle yardımcı bileşenlerdir. Word'ün `cmd.exe` veya `powershell.exe` doğurması **anormaldir**. Çünkü bir belge açan kullanıcının Word'ünün komut satırı başlatmasının meşru bir sebebi neredeyse yoktur. İşte bu "parent-child anomalisi" makro tabanlı saldırıların (bir belgeye gömülü VBA makrosunun kabuk açması) klasik imzasıdır.

### Somut Örnek: Şüpheli Ağaç

Tipik bir phishing zincirinin process ağacı şöyle görünür:

```
explorer.exe
 └─ outlook.exe
     └─ winword.exe            (kullanıcı eki açtı)
         └─ cmd.exe            (makro kabuk açtı — ANORMAL)
             └─ powershell.exe -nop -w hidden -enc <base64>
                 └─ rundll32.exe   (indirilen payload çalışıyor)
```

Bu ağaçta her ok bir alarm sebebidir. `winword.exe → cmd.exe` geçişi başlı başına yüksek güvenilirlikli bir dedektördür. EDR bunu değerlendirirken tek bir process'e değil, **ilişkiye** bakar. Bir başka klasik desen, `services.exe` veya `svchost.exe` altında başlaması gereken bir sistem process'inin yanlış ebeveyn altında görünmesidir; bu, process hollowing veya masquerading işareti olabilir. Örneğin gerçek `svchost.exe` her zaman `services.exe` tarafından ve belirli `-k` grup argümanlarıyla başlatılır; ebeveyni farklı olan ya da bu argümanı taşımayan bir `svchost.exe` güçlü bir şüphe sebebidir.

### LOLBins ve Ağaç Bağlamı

Saldırganlar tespitten kaçmak için sistemin kendi meşru ikili dosyalarını kötüye kullanır; bunlara LOLBin (Living Off the Land Binary) denir: `rundll32.exe`, `mshta.exe`, `regsvr32.exe`, `certutil.exe`, `wmic.exe` gibi. Bu araçlar Microsoft imzalıdır, yani imza tabanlı savunma onlara güvenir. Ama davranışsal tespit "certutil neden bir URL'den dosya indiriyor?" veya "regsvr32 neden internetten bir scriptlet çağırıyor?" diye sorar. Burada da ağaç bağlamı belirleyicidir: tekil olarak masum görünen bir araç, bütünün içinde suçlu hale gelir. `certutil.exe`'nin ebeveyni bir `powershell.exe` ise ve o da bir Office uygulamasından geliyorsa, zincirin tamamı niyeti açığa çıkarır. Bu, davranışsal tespitin özüdür: anlam, tekil olayda değil, olaylar arasındaki ilişkidedir.

## Şüpheli Komut Satırı Analizi

### Komut Satırı Neden Bu Kadar Zengin Bir Sinyal?

Process oluşturma olayı (Windows'ta Sysmon Event ID 1 ya da çekirdek düzeyi ETW telemetrisi) sadece hangi ikilinin çalıştığını değil, **hangi argümanlarla** çalıştığını da taşır. Argümanlar saldırganın niyetini sızdırır, çünkü aynı ikili argümana göre masum ya da yıkıcı olabilir. `powershell.exe` masumdur; `powershell.exe -nop -w hidden -ep bypass -enc SQBFAF...` neredeyse her zaman kötü niyetlidir.

Bu satırdaki her bayrağın bir anlamı ve bir kötü niyet sinyali vardır:

- `-nop` (NoProfile): Kullanıcının profil scriptini atlar. Meşru interaktif kullanıcı bunu nadiren yapar; otomasyon ve saldırgan sıklıkla yapar.
- `-w hidden` (WindowStyle Hidden): Pencereyi gizler. Kullanıcının görmesini istemeyen kod bunu ister.
- `-ep bypass` (ExecutionPolicy Bypass): PowerShell'in yürütme politikasını devre dışı bırakır. Not: ExecutionPolicy gerçek bir güvenlik sınırı değildir, daha çok bir kaza önleyicidir; ama bilinçli olarak bypass edilmesi niyeti gösterir.
- `-enc` (EncodedCommand): Base64 ile kodlanmış komut. Kodlamanın amacı ya karakter kaçışını kolaylaştırmak ya da göz denetiminden ve basit imza eşleştirmelerinden kaçmaktır.

Tek başına her bayrak zayıf bir sinyaldir; hepsinin bir arada olması güçlü bir sinyaldir. İyi tespit kuralları bu yüzden **kombinasyon ve olasılık** üzerine kuruludur; tekil bir bayrağa alarm bağlamak yüksek yanlış-pozitif üretir.

### Somut Örnek ve Deobfuscation Mantığı

Base64 kodlu komut aslında savunmacının işine yarar, çünkü çözüldüğünde niyet açığa çıkar. Yukarıdaki `-enc` payload'ı çözüldüğünde çoğu zaman `IEX (New-Object Net.WebClient).DownloadString('http://...')` gibi bir indir-ve-çalıştır (download cradle) deseni ortaya çıkar. Olgun EDR'ler, AMSI (Antimalware Scan Interface) üzerinden PowerShell'in **çalışma anında çözülmüş** script içeriğini görebilir; yani saldırgan ne kadar katman eklerse eklesin, kod çalışmadan hemen önce düz metne dönmek zorundadır. Bu, obfuscation'ın temel sınırıdır: kod eninde sonunda yorumlanmak için açığa çıkar, o an da savunmacının görme fırsatıdır.

Komut satırında aranan diğer desenler arasında şunlar sayılabilir: alışılmadık base64/hex yoğunluğu ve yüksek entropi, `IEX`, `DownloadString`, `FromBase64String` gibi anahtar kelimeler, aşırı uzun komut satırları, `bitsadmin` veya `certutil` ile dosya indirme, `vssadmin delete shadows` (ransomware'in shadow copy'leri silip kurtarmayı engellemesi), `wevtutil cl` (olay günlüğü temizleme, anti-forensics) ve `net user /add` gibi hesap manipülasyonları. Bunların her biri bir ATT&CK tekniğine karşılık gelir ve tekil olarak değil bağlamıyla değerlendirildiğinde anlam kazanır.

## IOA vs IOC: Kavramsal Ayrım

Bu ayrım davranışsal tespitin felsefi kalbidir, bu yüzden dikkatle açmak gerekir.

### IOC (Indicator of Compromise)

IOC, bir ihlalin **geçmişte gerçekleştiğine** dair kanıt niteliğindeki somut, atomik veridir: kötü bir dosya hash'i (MD5/SHA256), bir C2 (komuta-kontrol) sunucusunun IP adresi ya da domaini, belirli bir mutex adı, bir dosya yolu. IOC'nin gücü kesinliğidir: eşleşme olduğunda büyük ölçüde kesindir ve düşük yanlış-pozitif üretir. Zaafı ise kırılganlığı ve **geçmişe dönük** olmasıdır. Saldırgan hash'i tek baytla, IP'yi yeni bir sunucuyla, domaini yeni bir kayıtla değiştirdiği an, IOC değersizleşir. Ünlü "Pyramid of Pain" modelinin tabanında bu yüzden hash ve IP vardır: saldırgan için değiştirmesi en ucuz, savunmacı için kaybı en az acı verici olanlar bunlardır.

### IOA (Indicator of Attack)

IOA ise atomik bir veriyi değil, bir **niyeti ve davranış dizisini** yakalar. "Bir Office uygulaması bir kabuk process'i başlattı, o kabuk kodlanmış PowerShell çalıştırdı, o da LSASS belleğine erişmeye çalıştı" — bu bir IOA'dır. Hangi dosya, hangi hash, hangi IP kullanıldığından bağımsızdır. IOA'nın gücü **dayanıklılığıdır**: saldırgan payload'ını sıfırdan yeniden yazsa bile, credential çalmak için LSASS'a gitmek zorunda olduğundan IOA yine tetiklenir. Pyramid of Pain'in tepesindeki TTP (Tactics, Techniques, Procedures) katmanı budur; saldırgan için değiştirmesi en pahalı, savunmacı için en değerli katman.

### Neden İkisi de Gerekli?

Pratikte IOC ve IOA rakip değil, tamamlayıcıdır. IOC ucuz, hızlı ve düşük yanlış-pozitiflidir; bilinen bir tehdidi anında bloklamak için idealdir. Ama sıfırıncı gün (novel) saldırılarda kördür, çünkü henüz bilinen bir göstergesi yoktur. IOA yeni saldırıları yakalar ama daha fazla bağlam, ayarlama (tuning) ve yanlış-pozitif yönetimi gerektirir. Olgun bir savunma her ikisini katmanlar: IOC'ler bilineni hızla eler, IOA'lar bilinmeyeni avlar. Yalnızca IOC'ye yaslanan bir organizasyon, imza değiştiren her yeni kampanyaya karşı savunmasızdır; bu, klasik AV'den EDR'e geçmenin asıl gerekçesidir.

## Sömürü Tarafı: EDR Bypass Nasıl Çalışır?

Saldırganın bakış açısını anlamak, savunmayı doğru kurmak için şarttır. EDR'in gördüğü telemetri kabaca üç kaynaktan gelir: user-mode API hook'ları, çekirdek callback'leri (kernel callbacks) ve ETW (Event Tracing for Windows) olayları. Bypass teknikleri bu üç görme kanalını körleştirmeye çalışır. Aşağıdaki her teknik için önce sömürü mantığını, ardından savunmayı veriyorum.

### 1. User-Mode Hook Kaçınma

Birçok EDR izleme için hedef process'in adres alanına kendi DLL'ini enjekte eder ve `ntdll.dll` içindeki kritik syscall wrapper fonksiyonlarının (örneğin bellek ayırma, thread yaratma, process açma çağrıları) başına bir atlama (jump) yerleştirir; buna inline hooking denir. Böylece process bir syscall yapmadan önce kontrol önce EDR'in izleme koduna geçer. Saldırgan bunu çeşitli yollarla atlatmaya çalışır. **Unhooking**: EDR'in değiştirdiği `ntdll` kopyasını, diskteki temiz orijinaliyle (ya da yeni bir suspended process'ten alınan bozulmamış kopyayla) yeniden yükleyerek hook'ları siler. **Direct syscalls**: `ntdll`'i hiç çağırmadan, syscall numarasını doğrudan koda gömüp CPU'ya kendisi `syscall` talimatını çalıştırır; böylece hook'lanan fonksiyonun üzerinden atlar. Bunun daha gelişmiş biçimi, syscall talimatının yine gerçek `ntdll` içinde çalışıyormuş gibi görünmesini sağlayan "indirect syscall" yaklaşımıdır.

**Savunma:** User-mode hook'lara tek başına güvenmemek. Bu yüzden olgun EDR'ler asıl güvenilir telemetriyi çekirdekten (kernel) alır. Windows, `PsSetCreateProcessNotifyRoutine`, `PsSetCreateThreadNotifyRoutine` ve `ObRegisterCallbacks` gibi çekirdek callback mekanizmaları sunar; bunlar user-mode'dan silinemez veya atlanamaz, çünkü process/thread yaratma ve handle açma olayları çekirdek tarafından, saldırganın kodu çalışmadan önce raporlanır. Direct syscall'lar da user-mode hook'u atlar ama çekirdek callback'inin kör noktası değildir; ayrıca "bir process'in `ntdll` dışından, yığından (stack) gelmeyen bir syscall yapması" başlı başına anomali olarak tespit edilebilir (call-stack telemetrisi). Savunmacı için ders: görünürlüğü mümkün olan en düşük katmana, yani çekirdeğe indirmek.

### 2. ETW ve AMSI Körleştirme

ETW, Windows'un olay izleme altyapısıdır ve .NET assembly yükleme, PowerShell script bloğu çalıştırma gibi zengin sinyaller üretir. AMSI ise script ve bellek içeriğinin taranmasını sağlayan arayüzdür. Saldırgan, kendi process'i içinde bu mekanizmaların bellekteki fonksiyonlarını runtime'da yamalayarak (in-memory patching) etkisiz hale getirmeye çalışır: örneğin AMSI'nin tarama fonksiyonunun ilk baytlarını "her zaman temiz döndür" olacak şekilde değiştirmek, ya da ETW olay yazma fonksiyonunu erken dönecek şekilde kırpmak. Bunlar sık kullanılan, blogların bolca anlattığı tekniklerdir.

**Savunma:** Bu yamaların kendisi bir davranıştır ve tespit edilebilir. Bir process'in kendi belleğindeki AMSI/ETW fonksiyonlarını `RWX` (okuma-yazma-yürütme) izinleriyle değiştirmesi son derece anormaldir; EDR bu bellek koruması değişikliklerini ve kritik fonksiyonların bütünlük ihlalini izleyebilir. Ayrıca çekirdek düzeyi telemetri, user-mode'da AMSI kör edilmiş olsa bile process yaratma ve bellek olaylarını görmeye devam eder. Yine aynı ilke: bir görme kanalı kör edildiğinde diğer katmanların telafi etmesi.

### 3. Process Injection ve Yaşayan Süreçlerin İçine Saklanma

Saldırgan, kendi kötü koduna ait yeni bir process açmak yerine, meşru bir process'in (örneğin `explorer.exe`) içine kod enjekte ederek onun kimliği altında çalışmayı tercih eder; böylece process ağacında yeni ve şüpheli bir dal görünmez. Klasik teknikler: uzak process'te bellek ayırıp koda yazmak ve yeni bir thread başlatmak; ya da yasal bir process'i askıya alınmış (suspended) başlatıp içeriğini kendi kötü imajıyla değiştirmek (process hollowing); ya da APC (Asynchronous Procedure Call) kuyruğuna kod enjekte etmek.

**Savunma:** Bu tekniklerin ortak imzası, bir process'in **başka bir process'in belleğine yazması** ve orada **yürütülebilir bellek** oluşturmasıdır. Bunlar çekirdek callback'leri ve bellek olayları üzerinden görünür. `RWX` bellek tahsisi, başka process'e uzaktan thread yaratma, `explorer.exe` gibi bir process'in daha önce hiç dokunmadığı bir ağ adresine bağlanması gibi davranışlar IOA olarak yakalanır. Burada process ağacı ve bellek telemetrisinin birleşimi belirleyicidir.

### 4. BYOVD: Zafiyetli Sürücüyle EDR'i Öldürme

Daha agresif bir yol, "Bring Your Own Vulnerable Driver" (BYOVD) tekniğidir. Saldırgan, imzalı ama içinde zafiyet barındıran meşru bir çekirdek sürücüsünü sisteme yükler ve bu sürücünün zafiyetini kullanarak çekirdek düzeyinde keyfi işlem yapar; bununla EDR'in çekirdek callback'lerini kaldırabilir ya da EDR process'lerini korumalı olsalar bile sonlandırabilir. Bu, çekirdeğe güvenen savunma modelini bile hedef aldığı için özellikle tehlikelidir.

**Savunma:** Microsoft'un yayımladığı zafiyetli sürücü engelleme listelerini (driver blocklist) etkinleştirmek, HVCI/memory integrity gibi hipervizör tabanlı korumaları açmak ve yeni/nadir sürücü yüklemelerini bir IOA olarak izlemek. "Alışılmadık bir sürücünün yüklenmesinin hemen ardından EDR servisinin susması" başlı başına çok güçlü bir alarm desenidir; savunmacı bu korelasyonu kurmalıdır.

## Yaygın Hatalar

Sahada en sık görülen ve tespiti sessizce zayıflatan hatalar şunlardır:

- **Sadece "engelleme" moduna güvenip avlanmayı (threat hunting) ihmal etmek.** EDR bir buton değil, bir teleskoptur. Alarm üretmeyen ama telemetride duran zayıf sinyalleri kimse aramıyorsa, gelişmiş saldırgan gürültüsüzce ilerler.
- **IOC'yi tek savunma sanmak.** Yalnızca hash/IP blokları, imza değiştiren her kampanyada bir gün geriden gelir. IOA katmanı olmadan EDR bir "gecikmeli AV"e dönüşür.
- **Aşırı ayarlama (over-tuning) ve alarm yorgunluğu.** Yanlış-pozitiflerden bunalan ekip, gürültülü kuralları körü körüne susturur (whitelist); saldırgan da tam bu susturulan alanda çalışır. Doğru yaklaşım, kuralı silmek değil, bağlamla daraltmaktır.
- **Görünürlük boşlukları.** EDR'in kurulu olmadığı sunucular, çekirdek görünürlüğünün kapalı olduğu yapılandırmalar, komut satırı loglamanın kapalı olması ya da PowerShell script-block logging'in devre dışı olması, saldırganın koştuğu kör noktalar yaratır.
- **EDR'in kendisini bir güven sınırı sanmak.** EDR ihlali geciktirir ve görünür kılar; ama tek başına ne yama eksikliğini ne de zayıf kimlik yönetimini kapatır. Savunma katmanlıdır.
- **Zaman senkronizasyonu ve merkezî toplama eksikliği.** Uç noktalardaki saatler kaymışsa veya telemetri merkezî olarak korele edilmiyorsa, process ağacını olaylar arası bağlamak imkânsızlaşır.

## En İyi Pratikler

Kavramları savunmaya dönüştüren temel ilkeler:

- **Katmanlı görünürlük.** User-mode hook'lar, çekirdek callback'leri ve ETW/AMSI birbirinin yedeğidir. Bir katman kör edildiğinde diğerlerinin görmesi için hepsini birlikte kullanın; asıl güveni en alt (çekirdek) katmana yaslayın.
- **IOA öncelikli, IOC destekli tespit.** Tespit kurallarını ATT&CK teknikleri etrafında, davranış dizileri olarak kurgulayın; IOC'leri hızlı eleme için ekleyin ama omurga olarak değil.
- **Process ağacını birinci sınıf veri olarak ele alın.** Ebeveyn-çocuk anomalilerini (Office'in kabuk doğurması, `svchost`'un yanlış ebeveyni, LOLBin'lerin beklenmedik zincirleri) kural haline getirin. Anlamı olaylar arası ilişkide arayın.
- **Zenginleştirilmiş komut satırı loglaması.** Process oluşturma olaylarını komut satırıyla birlikte toplayın; PowerShell script-block logging ve AMSI entegrasyonunu açın ki obfuscation çözüldüğü an yakalanabilsin.
- **Saldırı yüzeyini önden daraltın.** Office makrolarını politika ile kısıtlamak, riskli LOLBin'leri ASR (Attack Surface Reduction) kuralları ve uygulama kontrolüyle sınırlamak, zafiyetli sürücü engelleme listelerini ve memory integrity korumalarını açmak, saldırganın davranışsal seçeneklerini baştan azaltır.
- **Sürekli avlanma ve düzenli doğrulama.** Alarmları beklemeden telemetride hipotez tabanlı avlanın; savunmanın gerçekten görüp göremediğini kontrollü saldırı simülasyonları (purple team, atomic testler) ile ölçün. Kör noktaları saldırgan değil, siz keşfedin.
- **EDR'i katmanlı savunmanın bir parçası olarak konumlandırın.** Yama yönetimi, en az ayrıcalık (least privilege), güçlü kimlik ve ağ segmentasyonuyla birlikte çalıştığında EDR gerçek değerini verir; tek başına bir sihirli değnek değildir.

## Sonuç

EDR'in davranışsal tespitteki gücü, saldırganın payload'ını sonsuz çeşitleyebilse de hedefe giden davranışsal yolu değiştirmesinin pahalı olması gerçeğinden gelir. Process ağacı bu davranışın iskeletini, komut satırı niyetini, IOA ise bu ikisinin oluşturduğu anlamı yakalar. Bypass teknikleri EDR'in görme kanallarını körleştirmeye çalışır; ama her körleştirme girişimi kendi başına yeni bir davranışsal iz bırakır. Bu yüzden olgun savunma, tek bir tespit noktasına değil, birbirini telafi eden katmanlı görünürlüğe ve sürekli avlanmaya dayanır. Saldırgan bir kanalı kör ettiğinde diğer kanalın konuşması, bu oyunun temel dengesidir.