# LOLBin Kötüye Kullanımı — TESPİTİ

> İlke: "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin önce saldırganın LOLBin'leri neden ve nasıl kullandığını kavramsal olarak anlatır, ardından bu davranışın diskte, bellekte, log'larda ve ağ üzerinde bıraktığı izleri tespit mühendisliği gözüyle çözümler. Amaç savunma ve tespittir; canlı bir saldırı reçetesi değildir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

LOLBin (Living Off the Land Binary) terimi, işletim sistemiyle birlikte gelen, dijital olarak imzalı ve meşru amaçlarla var olan çalıştırılabilir dosyaların, saldırgan tarafından beklenmedik ve kötü niyetli işler için kullanılmasını anlatır. "Living off the land" (araziden geçinmek) ifadesi buradaki felsefeyi özetler: saldırgan kendi araçlarını sisteme taşımak yerine, sistemin zaten sahip olduğu araçlarla iş görür. Windows'ta `bitsadmin.exe`, `certutil.exe`, `mshta.exe`, `rundll32.exe`, `regsvr32.exe`, `wmic.exe`, `powershell.exe`, `msiexec.exe` ve daha onlarcası bu kategoriye girer.

Saldırganın bu tekniğe yönelmesinin arkasında net bir mantık vardır. Klasik bir saldırıda, saldırgan kendi zararlı ikili dosyasını (implant, RAT, downloader) hedefe indirir ve çalıştırır. Ancak bu dosya; imzasız olması, itibar (reputation) skorunun düşük olması veya doğrudan zararlı imzalarla eşleşmesi nedeniyle antivirüs (AV) ve EDR ürünleri tarafından yakalanabilir. LOLBin yaklaşımı bu sürtünmeyi ortadan kaldırır. Saldırgan, zaten işletim sistemine ait, Microsoft tarafından imzalanmış ve güvenilir kabul edilen bir dosyayı çağırır. Böylece:

- **İmza ve itibar temelli engellemeyi atlatır.** `bitsadmin.exe` Microsoft imzalıdır; bir AV ürünü bu dosyayı "kötü" olarak işaretleyemez, çünkü sistemin normal parçasıdır.
- **Allowlisting (uygulama beyaz listesi) kontrollerini geçer.** AppLocker veya WDAC gibi mekanizmalar genellikle sistem dizinlerindeki imzalı ikili dosyalara güvenir. LOLBin tam da bu güven bölgesinde yaşar.
- **Görünürlüğü azaltır ve tespiti zorlaştırır.** Saldırgan davranışı, meşru yönetimsel etkinliğin gürültüsü içinde kaybolabilir. Bir sistem yöneticisi de `bitsadmin` ile dosya indirebilir; saldırgan da. Ayırt etmek bağlam (context) gerektirir.

Kavramsal olarak LOLBin'ler saldırı zincirinin farklı halkalarında işe koşulur: **execution** (kodu çalıştırma), **download/ingress tool transfer** (ikinci aşama yükü indirme), **defense evasion** (savunmayı atlatma), **persistence** (kalıcılık) ve bazen **credential access** (kimlik bilgisi erişimi). MITRE ATT&CK çerçevesinde bu davranışların büyük kısmı **T1105 (Ingress Tool Transfer)** ve **T1218 (System Binary Proxy Execution)** teknikleriyle örtüşür.

Bu metinde tespit mantığını somutlamak için elimizdeki gerçek Sigma kurallarının odaklandığı LOLBin'e, yani `bitsadmin.exe`'ye demirleneceğiz. BITS (Background Intelligent Transfer Service), Windows'un dosya aktarımlarını arka planda, düşük öncelikle ve ağ koptuğunda kaldığı yerden devam edecek biçimde yapan meşru bir servisidir; Windows Update de bunu kullanır. `bitsadmin.exe` bu servisi komut satırından yönetmeye yarar. Saldırgan gözüyle mantık şudur: "Kendi indirme aracımı taşıyıp yakalanmaktansa, sistemde hazır duran, imzalı, güvenilir `bitsadmin`'e uzaktaki bir URL'den dosyayı benim yerime indirtirim." İndirme işlemi arka plan servisi üzerinden yürüdüğü için, oluşturan süreç ile ağ bağlantısını kuran süreç bile farklı görünebilir. Bu, saldırgan için hem araç taşıma yükünü kaldırır hem de tespit yüzeyini değiştirir.

Bu bölümde bilinçli olarak adım adım komut reçetesi verilmiyor; savunmacının bilmesi gereken şey, **hangi meşru aracın hangi kötü amaç için istismar edildiği** ve bunun **hangi gözlemlenebilir davranışı** ürettiğidir.

---

## 2. Bıraktığı izler / artefaktlar

LOLBin kötüye kullanımı "dosyasız" (fileless) diye anılsa da, tamamen izsiz değildir. Aksine, doğru log kaynakları açıksa oldukça zengin bir telemetri bırakır. `bitsadmin` özelinde ve genel LOLBin davranışında aranacak başlıca artefaktlar:

### Süreç oluşturma (Process Creation) log'ları

En kritik kaynak budur. İki tamamlayıcı sağlayıcı vardır:

- **Sysmon Event ID 1 (Process Create):** `Image`, `CommandLine`, `ParentImage`, `ParentCommandLine`, `User`, `Hashes`, `OriginalFileName` gibi zengin alanlar sunar. LOLBin tespitinde bel kemiğidir.
- **Windows Security Event ID 4688 (A new process has been created):** Yerel denetim etkinse `NewProcessName` ve (komut satırı denetimi açıksa) `CommandLine` alanlarını verir. Sysmon yoksa temel görünürlük buradan gelir.

`bitsadmin` için burada aranan; `Image` alanının `\bitsadmin.exe` ile bitmesi (veya `OriginalFileName` alanının `bitsadmin.exe` olması, yeniden adlandırmaya karşı) ve `CommandLine` içinde indirme davranışını ele veren argümanların bulunmasıdır.

### Komut satırı desenleri

`bitsadmin` ile dosya indirme davranışı, komut satırında karakteristik izler bırakır. Elimizdeki Sigma kurallarının demirlendiği desenler:

- `/transfer` — bir aktarım işi (job) oluşturmanın çekirdek argümanı. İndirme davranışının en güçlü tek göstergesidir.
- `/create` ve ardından `/addfile` — bir işi manuel adımlarla kurmanın alternatif yolu; tespit `/transfer`'e ek olarak bunu da kapsamalıdır.
- Komut satırında `http`, `https`, `ftp` şemalı bir URL veya doğrudan bir IP adresi bulunması.

Bu desenlerin türevleri, elimizdeki beş gerçek Sigma kuralının her birinin ayrı bir "kötü sinyal" boyutunu yakalamak için nasıl bölündüğünü gösterir:

- **Doğrudan IP'ye indirme:** URL yerine `http://185.x.x.x/...` gibi çıplak bir IP adresi. Meşru yazılım genellikle alan adı (domain) kullanır; çıplak IP indirmeleri anormaldir.
- **Dosya paylaşım sitelerinden indirme:** `bitsadmin` komut satırında bilinen dosya paylaşım/paste hizmeti alan adları geçmesi (ör. anonim dosya barındırıcıları). Kurumsal bir güncelleme bu tür sitelerden gelmez.
- **Şüpheli uzantı indirme:** İndirilen hedef dosyanın `.exe`, `.dll`, `.scr`, `.ps1`, `.bat`, `.hta`, `.dat` gibi çalıştırılabilir veya betik uzantısına sahip olması.
- **Şüpheli hedef klasör:** İndirilen dosyanın `\Users\Public\`, `\AppData\`, `\ProgramData\`, `\Windows\Temp\`, `\Temp\` gibi kullanıcı tarafından yazılabilir ve saldırganların sıkça tercih ettiği geçici konumlara yazılması.

### Ebeveyn-çocuk süreç ilişkisi (parent-child lineage)

Aracın kim tarafından çağrıldığı, aracın kendisi kadar önemlidir. `bitsadmin.exe`'nin ebeveyni normalde bir yönetici komut istemi (`cmd.exe`) veya bir betik olabilir. Ancak ebeveyn `winword.exe`, `excel.exe`, `outlook.exe`, `mshta.exe`, `wscript.exe` gibi bir uygulama ise, bu Office makrosundan veya bir phishing zincirinden gelen bir istismarın güçlü işaretidir. `ParentImage` ve `ParentCommandLine` alanları bu bağlamı verir.

### BITS'e özgü operasyonel log'lar

`bitsadmin` özelinde, süreç log'larının ötesinde bir de servis düzeyinde telemetri vardır: **Microsoft-Windows-Bits-Client/Operational** log kanalı. Burada özellikle **Event ID 59 (BITS started transfer)** ve **Event ID 60/4** gibi olaylar, oluşturulan aktarım işlerini ve hedef URL'leri kaydeder. Bu kanal, `bitsadmin` yerine PowerShell'in `Start-BitsTransfer` cmdlet'i gibi başka bir arayüz üzerinden BITS istismar edildiğinde bile görünürlük sağladığı için tamamlayıcı bir kaynaktır.

### Ağ ve disk izleri

- **Ağ:** Sysmon Event ID 3 (Network Connection) veya güvenlik duvarı/proxy log'ları, `svchost.exe` (BITS servisini barındırır) veya `bitsadmin.exe` kaynaklı, dış bir IP'ye giden ve iş yükü profiline uymayan bağlantıları gösterebilir. BITS aktarımının asıl ağ trafiğinin `svchost.exe` üzerinden gitmesi, saldırgan için bir gizlenme; savunmacı için ise korelasyon gerektiren bir nokta yaratır.
- **Disk:** İndirilen dosyanın kendisi (Sysmon Event ID 11 — File Create), ve BITS'in iş durumunu sakladığı `qmgr.db` veri tabanı (`%ProgramData%\Microsoft\Network\Downloader\`) adli açıdan değerli artefaktlardır.

### Telemetrinin ön koşulu

Yukarıdaki izlerin çoğu, ilgili denetimin önceden açık olmasına bağlıdır. `CommandLine` alanı olmadan bir `bitsadmin` çağrısı neredeyse hiçbir tespit değeri taşımaz; bu yüzden ortamda ya Sysmon (uygun bir config ile) ya da Windows'un yerleşik **Include command line in process creation events** grup ilkesi (Event ID 4688 için) etkinleştirilmiş olmalıdır. Detection engineering açısından ilk adım, kural yazmadan önce bu telemetrinin gerçekten aktığını doğrulamaktır; aksi halde en iyi kural bile boş veri üzerinde çalışır. Aynı şekilde `OriginalFileName` alanı yalnızca Sysmon EID 1'de zenginleştirilmiş olarak gelir; salt 4688'e dayanan ortamlarda yeniden adlandırma tespiti zayıflar ve bu boşluğu davranışsal korelasyonla (indirme + yazma + çalıştırma) kapatmak gerekir.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Elimizdeki gerçek Sigma kuralları (yazar: Swachchhanda Shrawan Poudel, Nextron Systems), `bitsadmin` üzerinden indirme davranışını **tek bir dev kural yerine, birbirini tamamlayan beş odaklı kurala** bölerek çok katmanlı bir tespit stratejisi kurar. Bu, tespit mühendisliğinde önemli bir tasarım tercihidir: her kural farklı bir "kötülük sinyali" boyutunu ölçer ve bunları risk skorlamayla birleştirebilirsiniz.

Beş kural ve odakları:

1. **`d059842b-...` — File Download Via Bitsadmin:** Temel davranış. `bitsadmin` ile herhangi bir dosya indirme.
2. **`99c840f2-...` — Suspicious Download From Direct IP Via Bitsadmin:** İndirmenin çıplak IP adresine yapılması.
3. **`8518ed3d-...` — Suspicious Download From File-Sharing Website Via Bitsadmin:** İndirmenin bilinen dosya paylaşım sitelerinden yapılması.
4. **`5b80a791-...` — File With Suspicious Extension Downloaded Via Bitsadmin:** İndirilen dosyanın şüpheli uzantıya sahip olması.
5. **`2ddef153-...` — File Download Via Bitsadmin To A Suspicious Target Folder:** Dosyanın şüpheli hedef klasöre yazılması.

Bu kuralların tümü aynı **logsource** üzerine oturur: `category: process_creation`, `product: windows`. Regresyon testleri (positive detection test) Sysmon (Microsoft-Windows-Sysmon) EVTX örnekleriyle doğrulanmıştır, yani pratikte bu kuralları **Sysmon Event ID 1** veya **Security Event ID 4688** akışına uygularsınız. Kullanılan alanlar: `Image` (veya `OriginalFileName`), `CommandLine`. Bazı kurallarda ek olarak indirilen dosya yolunu/uzantısını yakalamak için yine `CommandLine` içi desen eşleştirmesi kullanılır.

### Ortak temel: aracı tanımlama

Tüm kuralların ortak selection bloğu, önce aracın `bitsadmin` olduğunu doğrular. Yeniden adlandırmaya (renaming) karşı hem `Image` hem de `OriginalFileName` kontrol edilir:

```
selection_img:
    - Image|endswith: '\bitsadmin.exe'
    - OriginalFileName: 'bitsadmin.exe'
```

`OriginalFileName`, PE dosyasının kaynak kodundaki gerçek adını taşır ve saldırgan `bitsadmin.exe`'yi `svc.exe` olarak kopyalasa bile değişmez; bu yüzden yeniden adlandırma kaçınmasına karşı kritiktir.

### Örnek 1 — Temel indirme davranışı (Sigma-benzeri)

Aşağıdaki mantık, temel "File Download Via Bitsadmin" kuralının Türkçe açıklamalı basitleştirilmiş halidir. Araç `bitsadmin` ise ve komut satırı bir indirme işi kuruyorsa alarm üretir:

```yaml
title: Bitsadmin Üzerinden Dosya İndirme (basitleştirilmiş)
logsource:
    category: process_creation
    product: windows
detection:
    selection_img:
        - Image|endswith: '\bitsadmin.exe'
        - OriginalFileName: 'bitsadmin.exe'
    selection_flags:
        CommandLine|contains:
            - '/transfer'
            - '/create'
            - '/addfile'
    condition: selection_img and selection_flags
level: medium
```

Buradaki mantık: aracın kimliği (`selection_img`) VE indirme niyetini ele veren argümanlar (`selection_flags`) birlikte bulunmalıdır. `/transfer` tek başına güçlü bir sinyaldir; `/create` + `/addfile` ise aynı davranışın çok adımlı kurulumunu yakalar.

### Örnek 2 — Yüksek güvenli sinyalleri birleştirme (doğrudan IP + şüpheli uzantı)

Temel kural orta seviye (medium) bir sinyaldir çünkü meşru yönetimsel kullanım da tetikleyebilir. Gerçek kural setinin dehası, bunun üzerine **daha spesifik ve yüksek güvenli** kuralları katmanlamasıdır. Aşağıda "doğrudan IP'ye indirme" ile "şüpheli uzantı" boyutlarını birleştiren bir mantık örneği:

```yaml
title: Bitsadmin ile Doğrudan IP'den Şüpheli Uzantı İndirme (basitleştirilmiş)
logsource:
    category: process_creation
    product: windows
detection:
    selection_img:
        - Image|endswith: '\bitsadmin.exe'
        - OriginalFileName: 'bitsadmin.exe'
    selection_transfer:
        CommandLine|contains: '/transfer'
    selection_direct_ip:
        CommandLine|re: 'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    selection_susp_ext:
        CommandLine|contains:
            - '.exe'
            - '.dll'
            - '.ps1'
            - '.scr'
            - '.hta'
    condition: selection_img and selection_transfer and (selection_direct_ip or selection_susp_ext)
level: high
```

Buradaki risk mantığı katmanlıdır: aracın `bitsadmin` olması + `/transfer` ile aktarım kurulması temel zemini oluşturur; bunun üzerine **çıplak IP** VEYA **çalıştırılabilir/betik uzantısı** eklendiğinde güven seviyesi `high`'a çıkar. Nextron kural setindeki `99c840f2` (direct IP) ve `5b80a791` (susp extensions) kuralları tam da bu iki boyutu ayrı ayrı ölçer; bir SIEM'de bunları aynı olay üzerinde çakıştığında (correlation) skoru daha da yükseltebilirsiniz.

### Eşik ve skorlama yaklaşımı

Pratikte önerilen kurgu: temel kural (`d059842b`) düşük-orta bir risk puanı ekler; "şüpheli hedef klasör" (`2ddef153`), "şüpheli uzantı" (`5b80a791`), "doğrudan IP" (`99c840f2`) ve "dosya paylaşım sitesi" (`8518ed3d`) kurallarının her biri ayrı ayrı puan ekler. Aynı süreç olayında birden fazla kural tetiklendiğinde toplam skor bir eşiği (ör. yüksek öncelikli alarm) aşar. Böylece meşru bir tek-boyutlu kullanım gürültü üretmezken, gerçek saldırının tipik olarak birden çok kötü sinyali aynı anda taşıması yakalanır. Bu, tek başına gürültülü olabilecek `/transfer` eşleşmesini, bağlamla zenginleştirerek yüksek isabetli bir alarma dönüştürmenin doğru yoludur.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırgan tespiti nasıl atlatmaya çalışır

LOLBin tespitini bilen bir saldırgan, yukarıdaki imzalardan kaçmak için birkaç yola başvurur. Savunmacının bunları önceden bilmesi, tespit tasarımını dayanıklı kılar:

- **İkiliyi yeniden adlandırma (renaming):** `bitsadmin.exe`'yi `update.exe` olarak kopyalayıp çağırmak. Bu, yalnızca `Image|endswith: '\bitsadmin.exe'` filtresini atlatır. **Karşı-tespit:** kural setinin yaptığı gibi `OriginalFileName` alanını da kontrol etmek; bu alan PE meta verisinden geldiği için yeniden adlandırmadan etkilenmez.
- **Alternatif LOLBin'e geçmek:** `bitsadmin` yakalanıyorsa saldırgan aynı indirme işini `certutil -urlcache`, `curl.exe`, PowerShell'in `Start-BitsTransfer` / `Invoke-WebRequest`'ı veya `mshta` ile yapabilir. **Karşı-tespit:** LOLBin tespitini tek araca kilitlememek; davranış temelli (indirme + yazma + çalıştırma zinciri) ve LOLBAS projesindeki bilinen ikili listesine dayanan geniş bir kural ailesi işletmek. BITS özelinde, `bitsadmin` yerine PowerShell arayüzü kullanılsa bile **Bits-Client/Operational** log kanalı (Event ID 59) görünürlük sağlar.
- **Komut satırını gizleme/karıştırma (obfuscation):** Argümanları büyük/küçük harf karıştırma, kısa/uzun form değişimleri, çevresel değişken (environment variable) genişletmesi, gereksiz boşluk veya alıntı karakterleri eklemek. **Karşı-tespit:** Sigma'nın alan modifikatörlerini (`|contains`, `|re`) büyük/küçük harf duyarsız kullanmak ve URL/IP için normalize edilmiş regex desenleri yazmak; komut satırı denetiminin (4688 için `Include command line in process creation events` politikası) mutlaka açık olması.
- **URL'yi bölme veya kısaltma servisleri:** IP yerine domain, domain yerine kısaltıcı kullanmak "direct IP" kuralını atlatabilir. **Karşı-tespit:** proxy/DNS log'larıyla korelasyon ve indirilen dosyanın uzantısı/hedef klasörü gibi IP'den bağımsız boyutlara güvenmek.
- **Komut satırı denetimini kapatma veya Sysmon'ı devre dışı bırakma:** Görünürlüğün kaynağını kurutmak. **Karşı-tespit:** Sysmon servis durumu ve yapılandırma değişikliklerini (Event ID 4719 — denetim politikası değişikliği; Sysmon'ın kendi Event ID 4/16'sı) izlemek; log akışında ani sessizliği anomali olarak alarmlamak.

### Tipik false positive kaynakları ve nasıl ayıklanır

`bitsadmin` meşru bir araçtır, dolayısıyla iyi huylu tetiklemeler beklenir. Başlıcaları:

- **Yazılım dağıtımı ve yönetim araçları:** SCCM/MECM, WSUS yardımcıları, kurumsal imaj/provizyon betikleri ve bazı kurulum sihirbazları BITS ile dosya çeker. **Ayıklama:** ebeveyn sürecin (`ParentImage`) bilinen dağıtım aracı olduğu, kaynağın kurum içi güncelleme sunucusu (bilinen iç IP/domain) olduğu durumları allowlist'e almak. Kullanıcı ve host bağlamıyla (yönetim sunucuları) daraltmak.
- **Meşru yönetici etkinliği:** Bir sistem yöneticisinin elle dosya indirmesi. **Ayıklama:** hedef URL'nin itibarını (threat intel), hedef klasörün meşruluğunu ve saatini değerlendirmek; tek boyutlu temel kural yerine skor eşiğiyle çalışmak (bkz. Bölüm 3).
- **Kurumsal güncelleme trafiği:** Bazı üçüncü parti uygulamalar güncellemelerini BITS üzerinden alır ve domain kullanır. **Ayıklama:** "direct IP" ve "file-sharing website" kurallarının domain temelli meşru güncellemeyi zaten dışarıda bıraktığını hatırlamak; bu kuralların gürültüsü düşüktür çünkü meşru yazılım çıplak IP veya anonim paylaşım sitesi kullanmaz.

**Ayıklama stratejisinin özü:** Temel indirme kuralını (`d059842b`) düşük öncelikli/telemetri amaçlı tutup, yüksek güvenli boyut kurallarını (doğrudan IP, dosya paylaşım sitesi, şüpheli uzantı, şüpheli klasör) alarm eşiğine yükseltmek. Meşru kullanım genellikle bu yüksek güvenli sinyallerin hiçbirini taşımaz; saldırı ise tipik olarak birden fazlasını aynı anda taşır. Böylece hem görünürlük korunur hem de analistin önüne yalnızca gerçekten şüpheli, çok sinyalli olaylar düşer. Son olarak, allowlist'leri host rolü, ebeveyn süreç ve hedef itibarı gibi bağlamsal alanlarla dar tutmak; geniş, yalnızca komut adına dayanan istisnalar yazmaktan kaçınmak, tespitin uzun vadeli sağlığı için şarttır.

---

### Özet

LOLBin kötüye kullanımı, saldırganın kendi silahını taşımak yerine sistemin imzalı, güvenilir araçlarını (burada `bitsadmin.exe`) istismar etmesidir. Tespit; süreç oluşturma log'larına (Sysmon EID 1 / Security EID 4688), komut satırı desenlerine (`/transfer`, `/create`, `/addfile`, URL/IP), ebeveyn-çocuk ilişkisine ve BITS'e özgü operasyonel log'lara dayanır. Nextron/Poudel imzalı beş gerçek Sigma kuralı, davranışı tek dev kural yerine boyutlara (temel indirme, doğrudan IP, dosya paylaşım sitesi, şüpheli uzantı, şüpheli klasör) ayırarak skorlanabilir, dayanıklı ve düşük yanlış-pozitifli bir tespit ailesi kurar. Kaçınmaya karşı savunmanın anahtarı `OriginalFileName` denetimi, davranış temelli geniş kapsam, komut satırı görünürlüğünün korunması ve bağlamsal skorlamadır.
