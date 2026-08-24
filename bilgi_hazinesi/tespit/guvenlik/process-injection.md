# Process Injection — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Önce saldırganın kod enjeksiyonuyla ne başardığını kavramsal olarak anla; sonra bu davranışın Windows'ta bıraktığı izleri, gerçek Sigma kurallarının mantığıyla tespit et. Bu metnin amacı savunma ve tespit mühendisliğidir; canlı operasyonel saldırı reçetesi değildir.

Process injection (T1055), mavi takımın en sık karşılaştığı ve en çok yanlış anladığı tekniklerden biridir. Yanlış anlaşılır çünkü tek bir teknik değildir: bir teknik ailesidir. Ortak paydaları şudur — saldırganın kendi kötü niyetli kodu, meşru ve güvenilir bir sürecin (process) adres uzayı içinde çalışır. Bu yüzden EDR'de "hangi süreç kötü?" sorusu çoğu zaman yanlış sorudur; doğru soru "hangi süreç, kim tarafından, nasıl manipüle edildi?" olur.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Process injection'ın çekirdek fikri **güven devralmadır** (trust inheritance). İşletim sistemi, ağ güvenlik duvarı, application allow-listing ve hatta bir analist gözü, süreçlere kimliklerine göre güvenir. `notepad.exe`, `explorer.exe`, `svchost.exe`, `dialer.exe` gibi süreçler "normal" kabul edilir. Saldırgan kendi kodunu diskte ayrı bir kötü amaçlı EXE olarak çalıştırırsa, hem imza tabanlı tespit hem de davranışsal analiz onu hedef alır. Ama kodunu güvenilir bir sürecin belleğine yerleştirip oradan çalıştırırsa:

- **Ağ trafiği** o güvenilir sürecin adına çıkar (C2 beacon'ı `notepad.exe`'den geliyormuş gibi görünür).
- **Disk üzerinde** yeni bir kötü amaçlı dosya çoğu zaman kalmaz (in-memory / fileless).
- **Application control** kuralları meşru süreci zaten izin listesine almıştır.
- **Süreç ağacı** (process tree) beklenen ebeveyn-çocuk ilişkilerini bozmaz — çünkü yeni bir çocuk süreç doğmayabilir.

Saldırganın bunu başarmak için kavramsal olarak yapması gerekenler dizisi şudur: (1) hedef bir sürecin belleğine **yazma erişimi** elde etmek, (2) o belleğe kendi kodunu veya kod işaretçilerini **yerleştirmek**, (3) hedef süreci bu kodu **çalıştırmaya** ikna etmek. Klasik yaklaşımda bu üç adım, sırasıyla hedef süreçte bellek ayırma, o belleğe payload yazma ve o bellek bölgesinde yeni bir yürütme akışı başlatma biçiminde gerçekleşir. Yürütme akışını başlatmanın en görünür ve klasik yolu, hedef süreçte **uzaktan bir thread oluşturmaktır** (remote thread creation) — savunma açısından bizim en değerli tespit kancamız da tam burasıdır.

Aynı aile içinde çok sayıda varyant vardır: DLL yolunu hedefe yazıp bir yükleyici fonksiyonu tetiklemek (classic DLL injection), meşru bir sürecin kod bölümünü kötü amaçlı kodla değiştirmek, bir süreci askıya alınmış halde başlatıp bellek görüntüsünü boşaltıp yeniden doldurmak (process hollowing — T1055.012), bir thread'in yürütme bağlamını (context) manipüle etmek, ya da Asynchronous Procedure Call kuyruklarını istismar etmek. Cobalt Strike gibi ticari sızma araçları ve onu kopyalayan gerçek tehdit aktörleri, bu tekniklerin çoğunu beacon yerleştirmek için kullanır. Bu metnin sağladığı gerçek Sigma kuralları özellikle iki gözlemlenebilir davranışa demir atar: **create_remote_thread olayları** ve **beklenmedik süreçlerden çıkan ağ bağlantıları**.

Kavramsal olarak önemli nokta: Enjeksiyonun kendisi (bellek işlemleri) çoğu zaman API katmanında gizlidir ve normal loglarda görünmez. Ama enjeksiyonun **sonuçları** — bir thread'in bir süreçten diğerine oluşturulması, ya da normalde ağa çıkmayan bir sürecin C2'ye bağlanması — gözlemlenebilir artefaktlar bırakır. Tespit mühendisliği bu sonuçları avlar.

---

## 2. Bıraktığı izler / artefaktlar

Process injection'ı avlarken beslendiğimiz temel telemetri kaynakları ve bıraktıkları izler:

### create_remote_thread telemetrisi
En kritik kaynaktır. **Sysmon Event ID 8 (CreateRemoteThread)** bir sürecin başka bir sürecte thread oluşturduğu anı yakalar. Bu olayın taşıdığı alanlar tespitin bel kemiğidir:

- `SourceImage` — thread'i oluşturan (enjekte eden) süreç.
- `TargetImage` — thread'in içine oluşturulduğu (kurban) süreç.
- `StartAddress` — yeni thread'in başlangıç bellek adresi.
- `SourceProcessId` / `TargetProcessId`, `StartFunction`, `StartModule`.

Gerçek dünyada meşru remote thread oluşturma nadirdir ve genellikle belirli sistem süreçlerine (`csrss.exe`, `wininit.exe` gibi) aittir. Bir kullanıcı uygulamasının ya da bir betik yorumlayıcısının başka bir sürece thread enjekte etmesi kuvvetli bir sinyaldir. Bu telemetri, sağlanan Sigma kurallarında `logsource.category: create_remote_thread` olarak soyutlanır.

### StartAddress deseni artefaktı
Cobalt Strike beacon'ları geçmişte, enjekte ettikleri thread'in başlangıç adresinin belleğe hizalanma biçimi nedeniyle karakteristik son baytlar bırakmıştır. Bu, "HackTool - Potential CobaltStrike Process Injection" kuralının demir attığı somut artefakttır: `StartAddress` alanının belirli hex kalıplarıyla (`0B80`, `0C7C`, `0C88`) bitmesi.

### Anomalili ağ bağlantısı artefaktı
Enjeksiyon başarılı olduğunda, kurban süreç beacon'un C2 trafiğini taşır. Burada iz, **Sysmon Event ID 3 (Network Connection)** ya da eşdeğer network_connection telemetrisidir. Alanlar:

- `Image` — bağlantıyı başlatan sürecin yolu.
- `Initiated` — bağlantının giden (outbound) olup olmadığı.
- `DestinationPort`, `DestinationIp`.

Kritik gözlem: Bazı süreçlerin ağa çıkması doğaları gereği anormaldir. `notepad.exe` normalde internete bağlanmaz (yazdırma istisnası hariç). `wordpad.exe`, `dialer.exe` gibi süreçler de öyle. Bu süreçlerden gelen giden bağlantı, arkalarında enjekte edilmiş bir beacon olduğunun güçlü işaretidir. Özellikle `dialer.exe`, Rhadamanthys gibi info-stealer'ların process injection ile C2 kurmak için hedef aldığı, modern kullanımda köhne kalmış bir ikilidir.

### Komut satırı ve süreç köken artefaktları
- **Sysmon Event ID 1 / Windows Security Event ID 4688 (Process Creation)** — process hollowing gibi tekniklerde bir sürecin askıya alınmış (suspended) başlatılması, olağandışı ebeveyn-çocuk ilişkileri, `SourceImage`'ın olağandışı bir konumdan (`\AppData\`, `\Temp\`, `\Users\Public\`) çalışması.
- Beklenmedik ebeveyn: örneğin `winword.exe`'nin çocuğu olarak beliren bir betik yorumlayıcısı, sonrasında remote thread oluşturması.

### Ana log kaynakları özeti
- Sysmon (Event ID 1, 3, 8, 10 — ProcessAccess dahil).
- Windows Security log (4688 process creation, komut satırı denetimi açıksa).
- EDR ham telemetrisi (bellek işlemleri, API çağrı zincirleri).
- Ağ kenar/proxy logları (beacon'ın hedef IP/domain korelasyonu için).

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki mantık tamamen sağlanan gerçek kurallara dayanır. Uydurma alan veya event yoktur.

### 3.1 StartAddress imza tabanlı tespit — CobaltStrike beacon'ı
"HackTool - Potential CobaltStrike Process Injection" kuralı en dolaysız mantığı taşır. Logsource `windows / create_remote_thread` (yani Sysmon Event ID 8). Koşul: `StartAddress` alanı belirli hex kalıplarıyla bitiyorsa alarm ver.

```
logsource:
    product: windows
    category: create_remote_thread
detection:
    selection:
        StartAddress|endswith:
            - '0B80'
            - '0C7C'
            - '0C88'
    condition: selection
```

Mantık: Bu, davranışsal değil, **artefakt-imza** tabanlı bir kuraldır. Cobalt Strike'ın belirli sürümlerinde enjekte edilen thread'lerin başlangıç adresi bu son baytlara denk düşer. Tek başına yüksek güvenli (level: high) bir sinyaldir, çünkü meşru remote thread'lerin başlangıç adresinin bu kesin kalıplarla bitme olasılığı düşüktür. Zaafı: imza tabanlı olduğu için saldırgan araç sürümünü/yapılandırmasını değiştirdiğinde adres kalıbı kayar. Bu yüzden onu davranışsal kurallarla desteklemek gerekir.

### 3.2 Olağandışı kaynaktan remote thread — davranışsal tespit
"Rare Remote Thread Creation By Uncommon Source Image" kuralı daha dayanıklı, davranış tabanlı mantığı temsil eder. Yine logsource `windows / create_remote_thread`. Koşul: `SourceImage`, normalde başka bir sürece thread enjekte etmesi beklenmeyen ikililerden biriyle bitiyorsa alarm ver. Kuralın listesinde `\cscript.exe`, `\bash.exe`, `\excel.exe`, `\findstr.exe`, `\gpupdate.exe`, `\installutil.exe`, `\hh.exe` gibi onlarca "beklenmedik enjeksiyon kaynağı" bulunur.

```
logsource:
    product: windows
    category: create_remote_thread
detection:
    selection:
        SourceImage|endswith:
            - '\cscript.exe'
            - '\excel.exe'
            - '\findstr.exe'
            - '\installutil.exe'
            - '\hh.exe'
            # ... (kuralın tam listesi)
    condition: selection
```

Mantık: Buradaki varsayım istatistikseldir — bu ikililerin meşru bir sebeple başka bir sürece thread oluşturması son derece nadirdir. Bir Office uygulaması (`excel.exe`) ya da bir LOLBAS ikilisi (`installutil.exe`, `cscript.exe`) remote thread oluşturuyorsa, bu neredeyse her zaman ya makro tabanlı bir yükleyici ya da bir living-off-the-land enjeksiyon zinciridir. İmza kalıbına bağlı olmadığı için 3.1'e göre araç değişikliklerine daha dayanıklıdır.

### 3.3 Ağ tarafı — güvenilir süreçten anomalili çıkış
Enjeksiyonun `StartAddress`/`SourceImage` izini kaçırsanız bile, sonucunu ağ tarafında yakalayabilirsiniz. Üç kural aynı mantık ailesini paylaşır: **normalde ağa çıkmayan bir süreçten giden bağlantı = muhtemel enjekte beacon.**

"Network Connection Initiated Via Notepad.EXE" en temiz örnektir. Logsource `windows / network_connection` (Sysmon Event ID 3). Koşul: `Image` `\notepad.exe` ile bitiyor ve bu yazdırma portu (9100) değilse alarm ver:

```
logsource:
    category: network_connection
    product: windows
detection:
    selection:
        Image|endswith: '\notepad.exe'
    filter_optional_printing:
        DestinationPort: 9100
    condition: selection and not 1 of filter_optional_*
```

Mantık: `notepad.exe` neredeyse hiç ağa çıkmaz; belge yazdırma (port 9100) meşru istisnadır ve `filter_optional_printing` ile elenir. Geriye kalan her giden bağlantı şüphelidir.

"Suspicious Wordpad Outbound Connections" aynı fikri `wordpad.exe` için, ama tersine mantıkla uygular: yaygın/meşru portları (80, 139, 443, 445, 465, 587, 993, 995) filtreler, geriye kalan **olağandışı portlara** giden `Initiated: true` bağlantılarına alarm verir. Beacon'lar sıklıkla standart dışı portlar kullandığından bu filtreleme mantıklıdır.

"Outbound Network Connection Initiated By Microsoft Dialer" ise `dialer.exe`'nin ağa çıkışını hedefler — çünkü bu köhne ikili, Rhadamanthys gibi stealer'ların enjeksiyon yoluyla C2 kurmakta kullandığı bilinen bir hedeftir.

### 3.4 Basit Sigma-benzeri tespit mantığı örnekleri

**Örnek A — LOLBAS ikilisinden remote thread + hemen ardından ağ çıkışı (korelasyon):**
```
title: Suspicious Remote Thread From Scripting Host
logsource:
    product: windows
    category: create_remote_thread
detection:
    selection:
        SourceImage|endswith:
            - '\cscript.exe'
            - '\wscript.exe'
            - '\mshta.exe'
    condition: selection
level: high
```
Bu, 3.2'nin daraltılmış, betik yorumlayıcılarına odaklı bir alt kümesidir; SIEM tarafında aynı host'ta kısa süre içinde bir Event ID 3 (network_connection) ile korele edilerek güven yükseltilir.

**Örnek B — Office uygulamasından remote thread:**
```
title: Office Application Injecting Remote Thread
logsource:
    product: windows
    category: create_remote_thread
detection:
    selection:
        SourceImage|endswith:
            - '\winword.exe'
            - '\excel.exe'
            - '\powerpnt.exe'
        TargetImage|endswith: '\svchost.exe'
    condition: selection
level: high
```
Bir Office ikilisinin `svchost.exe`'ye thread enjekte etmesi neredeyse kesin olarak makro tabanlı bir saldırı zinciridir; meşru karşılığı yok denecek kadar azdır.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırganın kaçınma yolları ve savunmacının karşı hamlesi

**StartAddress imzasından kaçış.** 3.1'deki kural belirli hex son baytlarına bağlıdır. Saldırgan beacon araç sürümünü değiştirerek, farklı bellek ayırma stratejileri kullanarak veya thread başlangıç adresini rastgeleleştirerek bu imzayı kaçırabilir. **Karşı hamle:** İmza tabanlı kuralı tek savunma katmanı yapma. Onu 3.2'deki `SourceImage` davranışsal kuralı ve 3.3'teki ağ anomalisi kurallarıyla birlikte çalıştır. İmzalar aşınır; davranışlar (beklenmedik bir süreçten thread oluşması, ağa çıkmayan sürecin bağlanması) daha yavaş değişir.

**Klasik CreateRemoteThread'ten kaçış.** İleri seviye aktörler Event ID 8 üretmemek için thread hijacking, APC injection, ya da doğrudan sistem çağrısı (direct syscall) gibi Sysmon'un görmediği yollara kayabilir. **Karşı hamle:** ProcessAccess telemetrisini (Sysmon Event ID 10) devreye al — enjeksiyon çoğu zaman hedef sürece yüksek ayrıcalıklı bir handle açmayı gerektirir (`PROCESS_VM_WRITE`, `PROCESS_CREATE_THREAD` gibi granted access maskeleri). Ayrıca ağ tarafındaki 3.3 kuralları thread oluşturma tekniğinden bağımsızdır; enjeksiyon yöntemi ne olursa olsun beacon ağa çıktığında yakalanır. Bu, katmanlı tespitin neden önemli olduğunu gösterir.

**Güvenilir süreç ama meşru port seçimi.** Saldırgan `notepad.exe` yerine gerçekten ağa çıkması olağan bir sürece (örn. tarayıcı) enjekte ederse ya da beacon'ı 443 gibi meşru bir porttan konuşturursa, 3.3'ün port tabanlı filtreleri onu eler. **Karşı hamle:** Ağ tarafını yalnız port değil, hedef itibarı (IP/domain reputation), JA3/TLS parmak izi anomalisi ve beacon periyodisitesi (düzenli aralıklı "kalp atışı" trafiği) ile zenginleştir. Kaynak süreç güvenilir olsa bile trafik deseni beacon'ı ele verir.

**Hedef süreç seçimini normalleştirme.** Saldırgan `TargetImage` olarak gerçekten remote thread almasına alışık bir sistem sürecini seçerek 3.2/örnek B mantığını atlatmaya çalışabilir. **Karşı hamle:** Kendi ortamının temel çizgisini (baseline) çıkar — hangi SourceImage → TargetImage çiftleri normalde görülüyor? Ortama özgü allow-list, jenerik kuraldan daha keskin ayrım yapar.

### Tipik false positive kaynakları ve ayıklama

- **Meşru yazdırma (notepad).** `notepad.exe`'nin port 9100'e bağlanması gerçek yazdırmadır — kuralın `filter_optional_printing` filtresi tam olarak bunu eler. Ortamında farklı yazdırma portları varsa filtreyi genişlet.
- **Wordpad'in beklenen trafiği.** Bazı ortamlarda `wordpad.exe` güncelleme/telemetri için standart portlara çıkabilir; kural zaten yaygın portları (80, 443, 445 vb.) filtreler. Kalan uyarıları hedef IP itibarıyla doğrula.
- **Güvenlik/EDR ajanları ve yönetim araçları.** Bazı meşru güvenlik ürünleri, yedekleme ajanları ve uygulama sanallaştırma (application virtualization) çözümleri gerçekten remote thread oluşturur. Bunlar 3.2'nin `SourceImage` listesindeki ikililerden gelirse false positive üretir. **Ayıklama:** Bilinen güvenlik ürünü yollarını ve imzalı, doğrulanmış yayıncıları filter bloğuyla ele; ama yolu ele alırken saldırganın aynı adı taklit etmesine karşı imza/hash doğrulaması ekle.
- **Yazılım kurulum/güncelleme süreçleri.** `installutil.exe`, `gpupdate.exe` gibi ikililer meşru yönetim faaliyetlerinde çalışır; ancak remote thread oluşturmaları hâlâ nadirdir. Kurulum pencereleri (change window) sırasında gelen uyarıları değişiklik yönetimi kayıtlarıyla korele ederek ele.
- **StartAddress kalıbı çakışması.** Nadiren meşru bir thread'in başlangıç adresi 3.1'deki kalıplardan biriyle bitebilir. Tek başına bu uyarıyı "yüksek güven" saymadan önce, aynı host'taki SourceImage/TargetImage bağlamıyla ve ağ tarafındaki korelasyonla teyit et.

### Pratik dedektif mimarisi
Sağlam bir process injection tespiti tek kurala değil, bir **kural katmanına** dayanır: (1) create_remote_thread üzerinde hem imza (StartAddress) hem davranış (SourceImage/TargetImage) kuralları, (2) ProcessAccess handle maskeleri, (3) network_connection üzerinde güvenilir-süreç-anomalisi kuralları, (4) bu sinyallerin SIEM'de host ve zaman ekseninde korelasyonu. Hiçbiri tek başına kusursuz değildir; ama birlikte, saldırganın "güven devralma" stratejisinin bıraktığı izlerin birini kaçırsa bile diğerini yakalayacak bir ağ örerler. Hırsızın maskesi (güvenilir süreç adı) ne kadar iyi olursa olsun, mücevheri çalmak için yaptığı hareketler — bellek yazma, thread oluşturma, ağa çıkma — iz bırakır; işimiz o izleri, gerçek telemetriye demirlenmiş kurallarla okumaktır.

### Tespiti güçlendirmek için pratik öneriler ve olgunluk basamakları

Tespit mühendisliği açısından process injection kurallarını devreye alırken sıralı bir olgunluk yaklaşımı en verimli sonucu verir.

**Basamak 1 — Görünürlük.** Hiçbir davranışsal kural, altında yatan telemetri toplanmıyorsa çalışmaz. İlk iş, uç noktalarda Sysmon'un doğru bir yapılandırma (config) ile dağıtılmış olmasıdır: en azından Event ID 1 (process creation), Event ID 3 (network connection), Event ID 8 (create remote thread) ve Event ID 10 (process access) toplanmalıdır. `StartAddress`, `SourceImage`, `TargetImage`, `Initiated`, `DestinationPort` gibi alanların loglara gerçekten yazıldığını doğrula; birçok kuruluşta kural yazılır ama alan hiç toplanmadığı için sessizce hiç tetiklenmez. Windows Security tarafında da process creation denetimi (4688) ve mümkünse komut satırı denetimi (Include command line in process creation events) açık olmalıdır.

**Basamak 2 — İmza tabanlı hızlı kazanımlar.** 3.1'deki gibi `StartAddress` kalıp kuralları düşük efor, yüksek getiri sağlar. Bunları önce devreye al; yanlış pozitif oranları düşüktür ve bilinen araçlara karşı anında değer üretir. Ancak bunları "geçici" katman olarak konumlandır — araç sürümü değiştiğinde aşınacaklarını bilerek.

**Basamak 3 — Davranışsal ve istatistiksel kurallar.** 3.2'deki `SourceImage` tabanlı "olağandışı kaynaktan remote thread" mantığı ve 3.3'teki güvenilir-süreç-ağ-anomalisi kuralları asıl dayanıklı katmandır. Bunları devreye alırken kendi ortamının temel çizgisini çıkararak (hangi kaynak süreç hangi hedefe normalde thread oluşturuyor, hangi süreç normalde ağa çıkıyor) kuruma özgü filter blokları hazırla. Genel amaçlı Sigma kuralları iyi bir başlangıçtır; ama ortama özgü tuning olmadan gürültü üretirler.

**Basamak 4 — Korelasyon ve zenginleştirme.** En yüksek güveni, tek başına orta seviye sinyallerin birleşiminden elde edersin. Örneğin aynı host üzerinde kısa bir zaman penceresinde: bir Office ikilisinden Event ID 8 (remote thread) + hemen ardından hedef süreçten Event ID 3 (giden bağlantı) + hedef IP'nin düşük itibarı. Tek tek her sinyal "medium" olabilir; korelasyon çıktısı "critical" olur. SIEM tarafında bu tür çok-aşamalı korelasyon kuralları, saldırganın tek bir tespit katmanını atlatmasını anlamsız kılar.

**Basamak 5 — Avcılık (threat hunting) döngüsü.** Kurallar reaktiftir; proaktif olmak için düzenli hunt sorguları çalıştır: "Son 30 günde `notepad.exe`, `wordpad.exe`, `dialer.exe` gibi ağa çıkmaması gereken süreçlerden kaç giden bağlantı oldu?", "Hangi olağandışı SourceImage → TargetImage remote thread çiftleri ilk kez göründü (new/rare)?". İlk-görülme (first-seen) ve nadirlik (rarity) tabanlı avcılık, henüz imzası olmayan yeni enjeksiyon zincirlerini ortaya çıkarır ve bir sonraki kuralın tohumunu atar.

Bu beş basamak, sağlanan gerçek Sigma kurallarını izole imzalardan, saldırganın "güvenilir süreç kimliğini çalma" stratejisini bütün olarak kuşatan bir savunma dokusuna dönüştürür. Hedef, tek bir dahiyane kural değil; birbirini yedekleyen, ortama demirlenmiş ve sürekli ayarlanan bir tespit ekosistemidir.
