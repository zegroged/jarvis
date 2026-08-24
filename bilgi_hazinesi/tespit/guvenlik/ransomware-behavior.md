# Ransomware Davranışı — Tespiti

> İlke: "Hırsızı tanımadan mücevheri koruyamazsın." Önce fidye yazılımının kurbanın makinesinde
> gerçekte ne yaptığını davranışsal düzeyde anlayacağız, sonra bu davranışın diskte, bellekte ve
> loglarda bıraktığı izleri tespit mantığına dönüştüreceğiz. Amaç savunma ve tespittir; canlı bir
> saldırı reçetesi değil.

Fidye yazılımı imzasıyla değil, **davranışıyla** yakalanır. Şifreleyicinin (encryptor) her ailesi
farklı bir hash'e sahiptir; bugün AV'yi atlatan bir örnek yarın yeniden derlenir ve hash değişir.
Ama fidye yazılımının başarılı olabilmek için yapmak **zorunda** olduğu birkaç davranış vardır ve
bunlar aileden bağımsız olarak neredeyse hiç değişmez. Bu belge, o değişmeyen davranışların en
kritik olanına — **kurtarma yollarının imhası** (impact aşaması, MITRE ATT&CK **T1490 Inhibit System
Recovery** ve ilişkili **T1542.003 Bootkit / boot yapılandırması kurcalama**) — odaklanır. Çünkü
şifreleme başlamadan hemen önce saldırganın Volume Shadow Copy'leri ve boot kurtarma seçeneklerini
yok etmesi, hem en tahmin edilebilir hem de savunmacıya **erken uyarı penceresi** sunan davranıştır.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Fidye yazılımının iş modeli tek bir şeye dayanır: kurbanın verisini geri alma yolunu **tek elde
tutmak**. Eğer kurban dosyalarını bir yedekten veya Windows'un kendi anlık görüntülerinden
(shadow copy) kolayca geri getirebiliyorsa, fidye ödemesinin hiçbir anlamı kalmaz. Bu yüzden ciddi
her fidye yazılımı, asıl şifreleme rutinini çalıştırmadan **önce** kurbanın yerel kurtarma
mekanizmalarını sistematik olarak yok eder. Saldırgan kavramsal olarak üç kurtarma katmanını hedef
alır:

**1) Volume Shadow Copy Service (VSS) anlık görüntüleri.** Windows, System Restore ve yedekleme
için dosya/hacim seviyesinde anlık görüntüler tutar. Bir kullanıcı "önceki sürüme geri dön"
diyebilir. Saldırgan bu görüntüleri silerse, şifrelenmiş dosyanın temiz kopyası ortadan kalkar.
Bunun için `vssadmin delete shadows`, `wmic shadowcopy delete` gibi **Living-off-the-Land Binaries
(LOLBin)** kullanmak klasik yoldur. Ancak daha sinsi aktörler `vssadmin`'i hiç çağırmaz; bunun
yerine kendi süreçlerinden doğrudan **VSS COM/DLL bileşenlerini** (`vssapi.dll`, `vss_ps.dll`,
`vsstrace.dll`) belleğe yükleyip anlık görüntüleri programatik olarak silerler. Bu, komut satırı
tabanlı tespitleri atlatmak için tasarlanmış bilinçli bir kaçınma hamlesidir — nitekim
`DeleteShadowCopies` gibi açık kaynak PoC'ler tam olarak bu DLL yükleme yöntemini gösterir.

**2) Windows boot / kurtarma yapılandırması.** Saldırgan `bcdedit.exe` ile Boot Configuration Data
(BCD) mağazasını kurcalar. Tipik amaç iki yönlüdür: (a) `bcdedit /set {default} recoveryenabled no`
ve `bcdedit /set {default} bootstatuspolicy ignoreallfailures` ile Windows'un otomatik onarım /
kurtarma ortamına düşmesini engellemek — böylece kurban WinRE üzerinden sistemini tamir edemez;
(b) `bcdedit /set safeboot` gibi seçeneklerle makineyi güvenli moda zorlamak (bazı aileler
şifrelemeyi Safe Mode'da yapar çünkü orada çoğu EDR ve güvenlik ajanı yüklenmez).

**3) Windows Backup katalogu ve yerel geri yükleme.** `wbadmin delete catalog`, `Disable-System
Restore`, yedek gölgeleme alanının küçültülmesi (`vssadmin resize shadowstorage`) gibi ek adımlar.

Kavramsal özet: **şifreleme = verinin rehin alınması, kurtarma imhası = kaçış yolunun kapatılması.**
İkisi zaman ekseninde peş peşe gelir. Savunmacı için altın değerindeki gerçek şudur: kurtarma imhası
davranışı, şifreleme fırtınası patlamadan saniyeler/dakikalar önce gerçekleşir. Yani bunu tespit
etmek, henüz yangını söndürebileceğiniz an demektir.

---

## 2. Bıraktığı izler / artefaktlar

Bu davranışlar Windows'ta gürültülü, spesifik ve tekrar eden telemetri üretir. Ana artefakt
kategorileri:

**A) Process creation (Sysmon Event ID 1 veya Windows Security Event ID 4688).** Kurtarma imhasının
en görünür yüzü. İzlenecek alanlar: `Image` (çalışan ikilinin tam yolu), `OriginalFileName` (PE
başlığındaki orijinal ad — yeniden adlandırmaya dayanıklıdır), `CommandLine`, `ParentImage`
(ebeveyn süreç). Klasik desenler:

- `bcdedit.exe ... /set {default} bootstatuspolicy ignoreallfailures`
- `bcdedit.exe ... /set {default} recoveryenabled no`
- `bcdedit.exe /set {default} safeboot network`
- `bcdedit.exe /deletevalue` veya `/import`
- `vssadmin.exe delete shadows /all /quiet`
- `wmic.exe shadowcopy delete`
- `wbadmin.exe delete catalog -quiet`

**B) Image load / DLL yükleme (Sysmon Event ID 7, `category: image_load`).** Komut satırından
kaçınan aktörlerin ihanet noktası. İzlenecek alan: `ImageLoaded` (yüklenen DLL'in tam yolu) ve
`Image` (DLL'i yükleyen sürecin yolu). VSS'e özgü şüpheli yükler:

- `ImageLoaded` = `...\vssapi.dll`
- `ImageLoaded` = `...\vss_ps.dll`
- `ImageLoaded` = `...\vsstrace.dll`

Bu DLL'ler normalde `svchost.exe`, `wmiprvse.exe`, sistem yedekleme araçları veya
`System32`/`SysWOW64`/`WinSxS` altından çalışan meşru süreçler tarafından yüklenir. **Kullanıcının
İndirilenler klasöründen, `C:\Users\...\AppData\Temp` altından ya da imzasız bir ikiliden** bu
DLL'lerin yüklenmesi son derece anormaldir.

**C) Boot / BCD registry ve dosya izleri.** BCD deposunun (`\Boot\BCD`) değişmesi, System Restore'un
kapatılması (`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore` altındaki
`DisableSR` / `RPSessionInterval` değerleri).

**D) Dosya sistemi ve ağ izleri (şifreleme fazının kendisi).** Kısa sürede binlerce dosyanın
yeniden adlandırılması, yeni ve tekdüze uzantı eklenmesi (`.locked`, `.crypt` vb.), her klasöre
düşen fidye notu (`README.txt`, `HOW_TO_DECRYPT.html`). Dosya entropisinin ani yükselmesi
(şifrelenmiş içerik yüksek entropilidir). Bunlar T1490'ın kapsamı dışında olsa da korelasyon için
değerlidir.

**E) Servis / süreç sonlandırma.** `taskkill`, `net stop`, `sc stop` ile veritabanı, yedekleme ve
güvenlik servislerinin durdurulması — şifrelenecek dosyaların kilidini açmak için.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki tespit mantığı tamamen elimizdeki **gerçek** Sigma kurallarına dayanır. İki farklı log
kaynağı üzerinden iki bağımsız görüş açısı elde ederiz: **image_load** (DLL tabanlı sinsi VSS
manipülasyonu) ve **process_creation** (bcdedit tabanlı boot kurcalama).

### 3.1 Görüş açısı 1 — Anormal VSS DLL yüklemesi (`image_load`)

`Suspicious Volume Shadow Copy Vssapi.dll Load` (id `37774c23-...`) ve kardeş kuralları
(`vss_ps.dll` → `333cdbe8-...`, `vsstrace.dll` → `48bfd177-...`) hepsi aynı mantığı paylaşır ve
`attack.t1490` ile etiketlidir. Mantık şudur:

- **logsource:** `category: image_load`, `product: windows` (yani Sysmon Event ID 7).
- **selection:** `ImageLoaded|endswith: '\vssapi.dll'` (kardeş kurallarda `\vss_ps.dll`,
  `\vsstrace.dll`). Yani "biri VSS DLL'ini yükledi" olayını yakalar.
- **filter (allowlist):** Yükleyen `Image` **meşru** yollardan biriyse elenir. Kuralda beyaz
  listeye alınan yollar: `C:\Windows\explorer.exe`,
  `C:\Windows\ImmersiveControlPanel\SystemSettings.exe`, ve `Image|startswith` ile
  `C:\Windows\System32\`, `C:\Windows\SysWOW64\`, `C:\Windows\WinSxS\`, kurulum için
  `C:\Windows\Temp\{`, ve `C:\$WinREAgent\Scratch\`. `vsstrace.dll` kuralı ayrıca Visual C++
  yeniden dağıtılabilir yükleyicisi için `C:\ProgramData\Package Cache\{` yolunu da beyaz listeye
  alır.
- **condition:** `selection and not filter` mantığı. Yani: **VSS DLL yüklendi VE onu yükleyen süreç
  bilinen meşru yollardan değil** → alarm.

Bu tam olarak "hırsızı tanı" ilkesinin uygulanışıdır: meşru VSS kullanıcılarını (System32 servisleri,
explorer, kurulumcular) beyaz listeye alıp geriye kalan **her** yükleyiciyi şüpheli sayarız. Çünkü
`vssapi.dll`'i `C:\Users\kurban\Downloads\invoice.exe` yüklüyorsa, bu neredeyse kesinlikle shadow
copy silmeye hazırlanan bir aktördür.

Basit Sigma-benzeri tespit örneği (uydurulmuş field yok, gerçek kural mantığının sadeleştirilmişi):

```yaml
title: Anormal Sürecin VSS DLL Yüklemesi (T1490)
logsource:
    category: image_load
    product: windows
detection:
    selection:
        ImageLoaded|endswith:
            - '\vssapi.dll'
            - '\vss_ps.dll'
            - '\vsstrace.dll'
    filter_legit:
        - Image:
            - 'C:\Windows\explorer.exe'
            - 'C:\Windows\ImmersiveControlPanel\SystemSettings.exe'
        - Image|startswith:
            - 'C:\Windows\System32\'
            - 'C:\Windows\SysWOW64\'
            - 'C:\Windows\WinSxS\'
    condition: selection and not filter_legit
level: high
```

### 3.2 Görüş açısı 2 — bcdedit ile boot kurcalama (`process_creation`)

Burada iki gerçek kuralımız var ve ikisini birlikte kullanmak katman sağlar.

**Kural A — `Boot Configuration Tampering Via Bcdedit.EXE` (id `1444443e-...`, `attack.t1490`).**
Mantık:

- **logsource:** `category: process_creation`, `product: windows` (Sysmon EID 1 / Security EID 4688).
- **selection_img:** `Image|endswith: '\bcdedit.exe'` **VEYA** `OriginalFileName: 'bcdedit.exe'`.
  `OriginalFileName` kullanımı kritik — saldırgan `bcdedit.exe`'yi `svc.exe` diye yeniden
  adlandırsa bile PE başlığındaki orijinal ad değişmez, tespit ayakta kalır.
- **selection_set:** `CommandLine|contains: 'set'`.
- **selection_cli:** `CommandLine|contains|all` ile hem `'bootstatuspolicy'` hem
  `'ignoreallfailures'` içermesi.
- **condition:** tüm `selection_*` birlikte. Yani: bu bcdedit VE `set` VE
  `bootstatuspolicy ignoreallfailures` → alarm. Bu, "Windows otomatik kurtarmayı sustur" komutunun
  neredeyse birebir imzasıdır ve meşru ortamda çok nadirdir.

**Kural B — `Potential Ransomware or Unauthorized MBR Tampering Via Bcdedit.EXE`
(id `c9fbe8e9-...`, `attack.t1070` + `attack.t1542.003`).** Mantık:

- Aynı `logsource: process_creation`.
- **selection_img:** yine `Image|endswith: '\bcdedit.exe'` veya `OriginalFileName: 'bcdedit.exe'`.
- **selection_cli:** `CommandLine|contains` içinde şu **tehlikeli fiillerden herhangi biri**:
  `'delete'`, `'deletevalue'`, `'import'`, `'safeboot'`, `'network'`.
- **condition:** `all of selection_*`. `level: medium`.

Bu kural A'dan daha geniştir: sadece kurtarmayı kapatmayı değil, BCD girdilerini silmeyi
(`delete`/`deletevalue`), harici bir BCD içe aktarmayı (`import`) ve güvenli moda zorlamayı
(`safeboot`, `safeboot network`) da yakalar. `level: medium` olması bilinçlidir — `bcdedit`'in
meşru IT kullanımı daha yaygın olduğundan A kuralına göre daha fazla FP taşır.

Bu ikisini birleştiren sadeleştirilmiş örnek:

```yaml
title: Fidye Öncesi bcdedit ile Boot/Kurtarma Kurcalama
logsource:
    category: process_creation
    product: windows
detection:
    selection_img:
        - Image|endswith: '\bcdedit.exe'
        - OriginalFileName: 'bcdedit.exe'
    selection_cli:
        CommandLine|contains:
            - 'ignoreallfailures'
            - 'recoveryenabled no'
            - 'delete'
            - 'deletevalue'
            - 'safeboot'
    condition: selection_img and selection_cli
level: high
```

### 3.3 Korelasyon — asıl güç eşleşmede

Tek başına bir bcdedit veya bir VSS DLL yüklemesi bazen meşru olabilir. Ama **kısa bir zaman
penceresi içinde** (örneğin 5 dakika, aynı host) şu zincir görülürse güven skoru tavana vurur:

1. Anormal süreç `vssapi.dll`/`vss_ps.dll` yükledi (3.1), **VE**
2. `bcdedit ... ignoreallfailures` veya `safeboot` çalıştı (3.2), **VE**
3. Hemen ardından kısa sürede yüzlerce dosya yeniden adlandırıldı / yeni uzantı aldı.

SIEM tarafında bu üç sinyali aynı `Computer`/`Host` üzerinde zaman-pencereli korelasyon kuralıyla
birleştirmek, tekil kuralların FP'sini eleyip yüksek kesinlikli bir "aktif fidye yazılımı" alarmı
üretir. Erken kesmek istiyorsanız 1 ve 2'yi tetikleyicide tutun — 3 geldiğinde şifreleme çoktan
başlamış olur.

---

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırgan bu tespiti nasıl atlatmaya çalışır

- **LOLBin'den kaçış / DLL'e geçiş.** `vssadmin delete shadows` komut satırı tespitleri artık çok
  yaygın olduğundan, olgun aktörler komut satırını hiç kullanmaz; doğrudan `vssapi.dll` / `vss_ps.dll`
  yükleyip VSS COM arayüzünden anlık görüntüleri silerler. **Karşı-tespit:** tam da bu yüzden
  `image_load` kaynağını (Sysmon EID 7) etkinleştirmek şarttır; 3.1'deki kural bu kaçışı kapatmak
  için vardır. Komut satırını izlemek tek başına yetmez.
- **Yeniden adlandırma (renamed binary).** `bcdedit.exe` başka bir isimle kopyalanır. **Karşı-tespit:**
  gerçek kurallar `OriginalFileName: 'bcdedit.exe'` alanını `Image|endswith` ile OR bağlar; PE
  metaverisi yeniden adlandırmadan etkilenmez. Sadece `Image` yoluna güvenmeyin.
- **Meşru yoldan LOLBin çalıştırma.** Saldırgan `System32\bcdedit.exe`'i olduğu yerden çağırır;
  yol tabanlı beyaz liste onu elemez çünkü kurallar `Image` yolunu değil `CommandLine`
  içeriğini/OriginalFileName'i baz alır — bu yüzden komut satırı içeriği (`ignoreallfailures`,
  `safeboot`) tespitin çıpasıdır.
- **DLL'i beyaz listedeki bir yola koyma (path spoofing).** 3.1 kuralı `System32`, `WinSxS` gibi
  yolları beyaz listeye aldığından, saldırgan kötü amaçlı yükleyiciyi bu dizinlere yerleştirmeye
  çalışabilir. **Karşı-tespit:** bu dizinlere yazma işleminin kendisi ayrıcalık ister ve nadirdir;
  `System32`'ye yeni ikili düşmesini (file_creation) ayrı izleyin ve imza/parent-process
  bağlamıyla zenginleştirin.
- **Zamanlama ve parçalama.** VSS silme ile şifrelemeyi zamana yayarak korelasyon penceresini
  şaşırtmak. **Karşı-tespit:** korelasyon penceresini makul tutun ve tekil `image_load`/`bcdedit`
  sinyallerini pencereye bakmaksızın da en azından orta seviye alarm olarak koruyun.
- **Safe Mode'a geçip EDR'ı devre dışı bırakma.** `bcdedit /set safeboot` ile güvenli moda alıp
  ajanları atlatma. **Karşı-tespit:** Kural B (`c9fbe8e9-...`) tam olarak `safeboot` ve `network`
  anahtar kelimelerini yakalar; ayrıca beklenmedik bir yeniden başlatma + Safe Mode girişini olay
  olarak izleyin.

### 4.2 Tipik false positive kaynakları ve nasıl ayıklanır

- **Windows kurulum/güncelleme ve yedekleme yazılımları.** Meşru VSS kullanıcıları: sistem
  yedekleme araçları, imaj alma çözümleri, Windows güncelleme bileşenleri. 3.1 kuralı bunu
  `System32`, `SysWOW64`, `WinSxS`, `C:\Windows\Temp\{...}` (installer), `C:\$WinREAgent\Scratch\`
  ve (vsstrace için) `C:\ProgramData\Package Cache\{...}` yollarını beyaz listeye alarak azaltır.
  **Ayıklama:** kendi ortamınızdaki meşru yedekleme aracının **tam kurulum yolunu** filtreye ekleyin;
  ürünün imza/publisher bilgisiyle doğrulayın.
- **IT/sysadmin'in meşru bcdedit kullanımı.** Yöneticiler dual-boot, bellek testi, boot onarımı
  için `bcdedit` çalıştırır. Bu yüzden Kural B `level: medium`. **Ayıklama:** kurulan
  `ParentImage`'e bakın — meşru kullanım genellikle interaktif `cmd.exe`/`powershell.exe` altından
  bir yönetici oturumundan gelir; fidye yazılımında ebeveyn çoğu zaman beklenmedik bir süreç
  (örneğin bir Office ürünü, bir script host veya imzasız bir ikili) olur. Değişiklik yönetimi
  kayıtlarıyla eşleştirin: planlı bir bakım penceresinde mi gerçekleşti?
- **`ignoreallfailures` özgüllüğü.** Kural A'nın `bootstatuspolicy` + `ignoreallfailures` ikilisini
  `contains|all` ile araması FP'yi çok düşürür çünkü bu spesifik kombinasyon meşru ortamda nadirdir.
  Bu yüzden A kuralı B'den daha yüksek güvenle alarmlanabilir.
- **Beyaz listenin fazla genişlemesi riski.** FP'yi susturmak için yol beyaz listesini gereğinden
  fazla genişletmek (örneğin tüm `C:\ProgramData\` altını) saldırgana saklanma alanı açar.
  **Kural:** beyaz listeyi mümkün olduğunca **dar** ve **tam yol** bazlı tutun; joker dizinlerden
  kaçının.

### 4.3 Kör noktaları kapatma

Bu tespitlerin çalışması için **telemetrinin var olması** şarttır. `image_load` (Sysmon EID 7) çoğu
kurulumda performans kaygısıyla kapalıdır; VSS DLL tespiti için en azından `vssapi.dll`,
`vss_ps.dll`, `vsstrace.dll` yüklemelerini kapsayacak biçimde açık olmalıdır. `process_creation`
tarafında ise komut satırı loglamanın (Security EID 4688 için `Include command line` politikası ya
da Sysmon EID 1) etkin olması gerekir — aksi halde `CommandLine|contains` koşulları hiç eşleşmez ve
kurallar sessizce körleşir. Son olarak `OriginalFileName` alanının toplandığından emin olun; yeniden
adlandırılmış LOLBin kaçışına karşı en sağlam çıpa odur.

---

**Kapanış.** Fidye yazılımını yakalamanın en güvenilir yolu, onun kaçınamayacağı davranışı —
kurtarma yollarını yok etmesini — izlemektir. Yukarıdaki gerçek Sigma kuralları (VSS DLL yükleme
üçlüsü ve iki bcdedit kuralı) bu davranışın hem sinsi (DLL) hem gürültülü (komut satırı) biçimlerini
kapsar. Bunları `image_load` + `process_creation` telemetrisi üzerine kurup zaman-pencereli
korelasyonla birleştirdiğinizde, şifreleme fırtınası kopmadan **önce** müdahale penceresini
yakalarsınız. Hırsızı bu adımda tanırsanız, mücevheri hâlâ kurtarabilirsiniz.
