# Keylogging / Clipboard Capture — Tespiti

> Pratisyen notu: Bu iki teknik (T1056.001 Keylogging ve T1115 Clipboard Data) genelde aynı torbaya konur ama tespit açısından tamamen farklı hayvanlardır. Keylogging çoğu zaman **hiç log üretmez** — API çağrısıdır, komut satırı değildir. Clipboard capture ise ya bir yardımcı araç (`clip.exe`, `xclip`, `pbcopy`) ya da bir API kancasıyla olur. Bu metin ikisinin de neden naif tespitle yakalanmadığını, sinyalleri nasıl bağlayacağını ve sahada nerede bozulduğunu anlatıyor.

---

## 1. Özet: Saldırı ve naif tespit

Keylogging'in amacı basit: kullanıcının klavyeye bastığı her şeyi — parolalar, MFA kodları, RDP oturumları içine yazılan credential'lar, e-posta içerikleri — sessizce toplamak. Windows'ta bunun klasik yolu `SetWindowsHookEx` ile global bir `WH_KEYBOARD_LL` kancası kurmak, ya da bir döngü içinde `GetAsyncKeyState` / `GetKeyState` çağırıp hangi tuşların basılı olduğunu poll etmektir. Daha modern varyantlar Raw Input API (`RegisterRawInputDevices`) kullanır. Clipboard capture ise buna kardeş bir tekniktir: kullanıcı bir parolayı parola yöneticisinden kopyalayıp yapıştırdığında, o veri bir an için pano (clipboard) içinde durur. Saldırgan `GetClipboardData` ile ya da `AddClipboardFormatListener` / eski `SetClipboardViewer` zinciriyle her pano değişiminde tetiklenir. Linux'ta `xclip -selection clipboard -o`, macOS'ta `pbpaste` veya AppleScript `the clipboard` bunun komut satırı karşılıklarıdır.

Naif tespit yaklaşımı şuna benzer: "`clip.exe` çalıştırıldıysa alarm ver", "`xclip ... -o` gördüysen T1115 diye işaretle", "process içinde `SetWindowsHookEx` string'i geçen bir binary varsa şüphelen". SigmaHQ'nun `Data Copied To Clipboard Via Clip.EXE` (ddeff553-5233-4ae9-bbab-d64d2bd634be) kuralı, `Clipboard Collection with Xclip Tool` (ec127035) ve auditd karşılığı (214e7e6c) tam olarak bunu yapar: process_creation olayında Image/CommandLine eşlemesi. macOS tarafında `MacOS Scripting Interpreter AppleScript` (1bc2e6c5) `osascript` çağrılarını `-e`, `.scpt`, `.js` içerdiğinde yakalar.

Bu kurallar **kötü değil** — ama tek başlarına bir SOC'u boğar ya da hiçbir şey yakalamaz. Çünkü keylogging'in %90'ı hiç process yaratmaz (in-process API kancasıdır), clipboard capture'ın büyük kısmı da meşru kullanıcı davranışıyla bit bit aynıdır. Aşağıda neden yetmediğini ve gerçek tespitin nerede olduğunu anlatıyorum.

---

## 2. Naif tespit neden yetmez

**Kör nokta 1: Keylogging çoğunlukla telemetri üretmez.** Bu en büyük yanılgı. `SetWindowsHookEx(WH_KEYBOARD_LL, ...)` çağrısı bir kullanıcı-modu API'dir; bir process oluşturmaz, bir dosya yazmaz, ağa çıkmaz. Sysmon'un varsayılan konfigürasyonu bu çağrıyı **görmez**. ETW'de `Microsoft-Windows-Win32k` provider'ında bazı ipuçları vardır ama bunlar üretimde neredeyse hiç toplanmaz. Yani "keylogger tespiti" diye satılan çoğu Sigma kuralı aslında ya (a) bilinen keylogger binary'lerinin dosya adı/hash'ini yakalar ya da (b) keylogger'ın *çıktısını* (log dosyası yazması, veriyi exfil etmesi) yakalar — kancanın kendisini değil. Kancayı görmek için ya EDR'nin kernel/user callback görünürlüğü ya da hedeflenmiş bir ETW toplama (örn. Win32k, threat-intelligence ETW-Ti) gerekir; ikisi de "varsayılan"da yoktur.

**Kör nokta 2: `clip.exe` ve `xclip` çift yönlüdür.** SigmaHQ clip.exe kuralı process_creation'da eşleşir ama `clip.exe` aslında pano *okumak* için değil, pano *yazmak* için tasarlanmış bir araçtır (`dir | clip`). Saldırgan pano *okumak* istiyorsa `clip.exe` işine yaramaz — `Get-Clipboard` PowerShell cmdlet'i, `powershell -c "Get-Clipboard"` ya da doğrudan API kullanır. Yani clip.exe kuralı aslında collection'ı değil, admin/kullanıcı kolaylığını yakalar. Gerçek clipboard *exfiltration* PowerShell `Get-Clipboard` ya da .NET `[Windows.Forms.Clipboard]::GetText()` üzerinden gelir ve bunlar process_creation'da farklı görünür.

**Kolay atlatma:** Kancayı LOLBin ile değil, kendi process'in içinde kurarsan hiçbir komut satırı sinyali kalmaz. Clipboard için `Get-Clipboard` yerine .NET assembly'yi reflection'la yükleyip `System.Windows.Forms.Clipboard.GetText()` çağırırsan CommandLine'da ne "clip" ne "clipboard" geçer. Linux'ta `xclip` yerine `/dev/clipboard` benzeri bir yol yoktur ama `xsel`, `wl-paste` (Wayland) gibi alternatifler kuralın Image|contains 'xclip' filtresini tamamen atlar.

**False positive selleri:** Clipboard araçları kullanıcı iş istasyonlarında sürekli çalışır. Bu yüzden Sigma kurallarının kendisi bile "sunucularda kullanın, iş istasyonlarında clipboard yoğun" uyarısı koyar ve `level: low` verir. macOS'ta `osascript` kuralı en beteridir: Alfred, Raycast, birçok not uygulaması, hatta OpenCode TUI'si (kuralın kendi `filter_optional_opencode` istisnasında görüldüğü gibi) pano işlemleri için `osascript` kullanır. Filtre eklemeye başlarsın, filtreler kuralı delik deşik eder, sonunda ya gürültüden kör olursun ya da o kadar filtre koyarsın ki gerçek saldırgan istisnaların arasından geçer.

Özetle: naif kural ya **yanlış katmanda** dinliyor (process_creation, oysa teknik in-process), ya **yanlış aracı** yakalıyor (clip.exe yazma amaçlı), ya da **meşru kullanımdan ayırt edilemeyecek** kadar geniş. Değer, tek sinyalde değil; sinyali bağlamda ve zincirde okumakta.

---

## 3. Korelasyon zinciri — asıl değer

Tek başına "`xclip -o` çalıştı" ya da "`Get-Clipboard` çağrıldı" düşük güvenli bir sinyaldir. Onu yüksek güvenli bir tespite çeviren şey, **capture olayını daha büyük bir saldırı akışının içine oturtmaktır**. İşte sahada işe yarayan korelasyon desenleri:

**Desen A — Collection + Staging + Exfil üçlemesi (klasik casusluk zinciri):**
```
[T1056/T1115] Clipboard/keystroke capture (Get-Clipboard, hook kurulumu)
     + (aynı 10-30 dk pencerede)
[T1074] Local staging — %TEMP%, %APPDATA% altında büyüyen .txt/.log/.dat dosyası
     + (kısa süre sonra)
[T1041 / T1071] Bu dosyanın ağa çıkışı — nadir C2 domaini, DNS tüneli, ya da normalde outbound yapmayan bir process'in HTTPS POST'u
```
Tek başına `Get-Clipboard` = gürültü. Ama **aynı parent process** hem `Get-Clipboard` çağırıp hem 20 dakika içinde `%APPDATA%\Microsoft\keys.log` gibi bir dosyaya periyodik yazıp hem de o dosyayı bir webhook'a POST ediyorsa — bu artık casusluktur. Bağlayıcı anahtar: **process soyağacı (ProcessGuid/parent-child) ve zaman penceresi**. Sysmon Event ID 1 (process), 11 (file create), 3 (network) aynı ProcessGuid altında birleştirildiğinde zincir ortaya çıkar.

**Desen B — Keylogger'ın "sessiz" olduğu yerde davranışsal proxy:**
Kancayı doğrudan göremiyorsan, keylogger'ın **ihtiyaç duyduğu yan davranışları** korele et. Klasik in-memory keylogger'lar:
- Bir foreground-window takibi yapar (`GetForegroundWindow` çağrısı) — hangi uygulamaya yazıldığını bilmek için,
- Yakaladığı tuşları bir yere yazar (dosya I/O ya da named pipe),
- Persistence kurar (Run key, scheduled task, WMI subscription).

Tek başına persistence sinyali (T1547.001 Registry Run Key) gürültüdür. Ama **imzasız, yeni yazılmış, kullanıcı-yazılabilir bir dizinden (%APPDATA%, %TEMP%) çalışan** + **Run key persistence kuran** + **düzenli aralıklarla küçük dosya yazımı yapan** bir process = yüksek güvenli keylogger adayı. Burada capture'ı doğrudan görmesen de, çevresel imza yeterince spesifiktir.

**Desen C — Kimlik bağlamı korelasyonu (en güçlüsü):**
Clipboard/keylog collection'ın *amacı* credential çalmaktır. Dolayısıyla en değerli korelasyon, capture olayını **sonraki kimlik olayına** bağlamaktır:
```
Host X'te clipboard/keylog capture (T1115/T1056)
     + (dakikalar-saatler içinde)
Aynı kullanıcının credential'ıyla FARKLI bir host'tan/IP'den atipik oturum açma
     (T1078 — impossible travel, yeni cihaz, off-hours logon)
     + 
O kullanıcının normalde erişmediği kaynaklara erişim (lateral movement)
```
"A host'unda pano yakalandı + B kaynağında aynı hesapla anormal erişim" — bu iki sinyal ayrı ayrı düşük, birlikte **gerçek ihlal** işaretidir. Google tek sayfada bunu vermez çünkü bu bir cross-source korelasyondur: endpoint telemetrisi (Sysmon/EDR) + identity telemetrisi (Windows Security 4624/4625, Azure AD/Entra ID sign-in logları). SIEM'de bu ancak asset+identity graph kurulmuşsa çıkar.

Pratikte kurduğum kural mantığı şöyle: capture sinyaline bir **"risk boyası" (risk annotation)** koyarım, alarm üretmem. Sonra aynı host veya kullanıcı 6 saat içinde ikinci bir suspicious sinyal (persistence, anormal outbound, kimlik anomalisi) üretirse, korelasyon motoru boyalı olayı çeker ve **birleşik yüksek-öncelikli** bir case açar. Tek sinyal = telemetri; iki bağlı sinyal = incident.

**Desen D — RDP/VDI clipboard hijack (sık atlanan):** Uzak masaüstü ve VDI ortamlarında pano, oturumlar arası köprülenir. Saldırgan bir jump box'ta oturmuş bir kullanıcının panosunu okuyarak, o kullanıcının yerel makinesinden kopyaladığı credential'ı ele geçirebilir — hiç keylogger kurmadan. Buradaki korelasyon: **RDP oturum başlangıcı (Event ID 4624 Type 10 / TerminalServices logları)** + aynı oturum içinde **clipboard okuma yönlü erişim** + oturumu açan kaynağın atipik olması. Tek başına "RDP oturumunda clipboard okundu" gürültüdür (kopyala-yapıştır normaldir); ama düşük-prevalence bir process'in, kullanıcı etkileşimi olmadan, oturum açılır açılmaz panoyu okuması desendir. Sysmon Event ID 24 (clipboard change) bu senaryoda kimin yazdığını/okuduğunu gösterdiği için burada özellikle değerlidir.

Bu dört deseni birbirine bağlayan ortak fikir şu: capture olayı asla **birincil** alarm değildir; her zaman bir **doğrulayıcı** sinyaldir. Birincil tetikleyici ya kimlik anomalisi, ya persistence, ya anormal outbound, ya da atipik oturum olur — capture olayı o birincil sinyalin *niyetini* açıklayan ikinci kanıttır. Bu yüzden capture kurallarını "ateşleyen alarm" olarak değil, korelasyon motorunun çektiği "kanıt havuzu" olarak konumlandırırım.

---

## 4. False positive gerçeği ve triage yargısı

Bu kuralları meşru üreten şeyler, sahada gerçekten gördüklerim:

- **`clip.exe`:** Admin scriptleri sürekli `command | clip` yapar (çıktıyı panoya alıp bir yere yapıştırmak için). PowerShell profilleri, kurulum scriptleri, IT self-service araçları. Neredeyse tamamı yazma amaçlıdır, okuma değil.
- **`Get-Clipboard` / .NET Clipboard:** RMM araçları (ConnectWise, N-able), yardım masası uzaktan destek yazılımları, clipboard manager uygulamaları (Ditto, ClipboardFusion), pano senkronizasyon araçları.
- **`xclip` / `xsel`:** Linux sunucularda bile, özellikle tmux/vim entegrasyonu olan geliştirici iş istasyonlarında sürekli. CI/CD scriptlerinde de görülür.
- **`osascript ... the clipboard`:** macOS'ta Alfred, Raycast, Paste, TextExpander, birçok not uygulaması ve — kuralın kendi istisnasında belgelendiği gibi — OpenCode/terminal TUI'leri. Bu **en gürültülü** olanıdır.
- **Vuln scanner / SCCM / yedek yazılımı:** Bunlar keylog kurallarını değil ama çevresel korelasyon sinyallerini (geniş process yaratma, dosya erişimi, WMI sorguları) tetikleyip Desen B/C'nin false positive üretmesine yol açar. Örneğin bir SCCM ajanı imzasız geçici binary'ler çalıştırıp Run key'lere dokunabilir.

**Kıdemli analistin gerçek/gürültü ayrımı — sorduğum sorular:**

1. **Yön sorusu (clipboard için):** Pano *yazılıyor* mu *okunuyor* mu? `command | clip` yazmadır, düşük risk. `Get-Clipboard` / `xclip -o` / `pbpaste` okumadır — collection budur, daha çok bakılır.
2. **Kim çalıştırdı?** İnteraktif bir kullanıcı oturumu mu (kullanıcı vim'de kopyalıyor — muhtemelen meşru), yoksa bir servis hesabı / non-interactive session / garip parent (winword.exe → powershell → Get-Clipboard) mı? İkincisi kırmızı bayrak. Parent-child soyağacı burada her şeydir.
3. **Süreklilik/frekans:** Tek seferlik pano okuma = kullanıcı davranışı. **Döngü halinde** (her N saniyede bir) pano poll'lama = keylogger/clipboard monitor deseni. Frekans ve düzenlilik, meşru kullanımdan en ayırt edici özelliktir.
4. **Binary'nin kökeni:** İmzalı, bilinen kurulum yolundan mı çalışıyor (Program Files) yoksa %TEMP%/%APPDATA%'dan, imzasız, yeni indirilmiş bir binary mi? Prevalence düşükse (ortamda tek host'ta görülüyorsa) risk yükselir.

**Çoklu alarmda öncelik sırası** (benim triage sıram):
1. **En yüksek:** Capture + kimlik anomalisi korelasyonu (Desen C) — gerçek ihlal olasılığı en yüksek, iş etkisi en büyük.
2. Capture + persistence + anormal outbound aynı soyağacında (Desen A/B).
3. İmzasız/düşük-prevalence binary'den okuma-yönlü clipboard/hook + persistence.
4. İnteraktif kullanıcı oturumunda tek seferlik okuma-yönlü capture, tanınmayan araç.
5. **En düşük / genelde kapatılır:** `command | clip` yazma, bilinen clipboard manager, geliştirici iş istasyonunda `xclip`/`osascript`. Bunları risk boyası olarak tutarım ama tek başına case açtırmam.

---

## 5. Kaçınma → karşı-tespit

Saldırganın kural dokümanında **yazmayan** atlatma yolları ve her birine ikinci-derece tespit:

**Kaçınma 1: LOLBin yerine in-process API.** Saldırgan `clip.exe`/`xclip` çağırmaz; kendi implant'ı içinde `GetClipboardData` / `SetWindowsHookEx` çağırır. Komut satırı sinyali sıfırdır.
→ **Karşı-tespit:** Process_creation ölür, ama EDR'nin API/callback görünürlüğü ya da hedefli ETW yardım eder. Pratikte daha ulaşılabilir olan: **davranışsal proxy** (Desen B) — hook kuran process'lerin genelde `WH_KEYBOARD_LL` için bir DLL/module yüklemesi ve foreground-window takibi yapması. Ayrıca clipboard listener process'leri `AddClipboardFormatListener` için gizli bir mesaj penceresi (message-only window) oluşturur; bunu doğrudan göremeyiz ama bu tür implant'lar genelde persistence + outbound zinciriyle ele verir. Kesin çözüm yoksa, **çevresel imzaya** dayan.

**Kaçınma 2: PowerShell'i gizlemek.** `Get-Clipboard` yerine `[Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [Windows.Forms.Clipboard]::GetText()` — CommandLine'da "clipboard" string'i `Get-Clipboard` cmdlet adı olarak geçmez.
→ **Karşı-tespit:** Script Block Logging (Event ID 4104) burada kurtarır. Cmdlet adı gizlenebilir ama .NET tür adı (`Windows.Forms.Clipboard`, `GetText`) script block içinde çıplak durur. Process CommandLine'a değil, **4104 içeriğine** kural yaz. Ayrıca AMSI, in-memory script içeriğini deobfuscate edilmiş halde görebilir.

**Kaçınma 3: Alternatif araçlar.** `xclip` yerine `xsel`, `wl-paste` (Wayland), `wl-clipboard`; macOS'ta `pbpaste` yerine AppleScript `the clipboard`; Windows'ta `Get-Clipboard` yerine WSL içinden `powershell.exe Get-Clipboard`.
→ **Karşı-tespit:** Kuralı tek araç adına (`xclip`) sabitlemek yerine **davranışa** genişlet: pano okuma yeteneği olan tüm araçların allowlist'ini çıkar, dışındaki her clipboard erişimini boya. Sigma'nın `Image|contains: 'xclip'` yaklaşımı kırılgan; bunun yerine "clipboard okuyan bilinen ikili değil + `-o`/`paste`/`clipboard` argümanı" gibi genişletilmiş bir mantık kur. Wayland `wl-paste` ve `xsel`'i açıkça kural setine ekle (çoğu ortam unutur).

**Kaçınma 4: Capture'ı sömürüden ayırmak (zamansal parçalama).** Saldırgan clipboard/keylog'u toplar ama exfil'i günler sonra, farklı bir process'le, farklı bir kanaldan yapar. Böylece Desen A'nın "kısa zaman penceresi" korelasyonu kırılır.
→ **Karşı-tespit:** Korelasyon penceresini olay-tipine göre esnet. Capture → staging arasını dar tut (dakikalar), ama staging dosyasına **file-access based** izleme koy: o dosyaya *okuma* amaçlı erişen ikinci bir process (özellikle outbound yapan) günler sonra bile gelse case'i yeniden aç. Staging dosyasını bir "honeytoken/kanarya izleme noktası" gibi kullan.

**Kaçınma 5: Meşru araca sığınma (living-off-trusted-software).** RMM aracı ya da clipboard manager'ın kendi meşru pano erişimini kötüye kullanmak/piggyback etmek — allowlist'e giren bir process adı altında çalışmak.
→ **Karşı-tespit:** Allowlist'i sadece process adına değil, **imza + yol + davranış profiline** bağla. Meşru clipboard manager pano okur ama outbound C2 yapmaz ve %TEMP%'e keylog yazmaz. Allowlist'lenen process bile ani bir davranış sapması (yeni network destination, yeni dosya yazımı) gösterirse boyanmalı.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları:**
- Sigma `CommandLine|contains|all` mantığı Splunk'ta `Processes.process`, Sentinel'de `ProcessCommandLine`, Elastic ECS'te `process.command_line`'a düşer. Ama **argüman sırası**: auditd kuralı (214e7e6c) `a0/a1/a2/a3` diye ayrı EXECVE argümanlarını eşler — Splunk/Elastic tarafında komut satırı çoğu zaman tek string'e birleşmiş (flatten) gelir, ayrı `a0..aN` alanları olmayabilir. auditd'yi olduğu gibi başka platforma taşırsan eşleşme bozulur; birleşik-string mantığına çevirmen gerekir.
- macOS `osascript` kuralı `Image|endswith: '/osascript'` diyor. Bazı EDR'ler bunu tam yol (`/usr/bin/osascript`) verir, bazıları sadece `osascript`. `endswith` genelde güvenlidir ama Image alanının EDR'de dolu geldiğini doğrula — bazı macOS telemetrisinde process path yerine yalnızca bundle bilgisi gelir.
- Windows'ta `clip.exe`: bazı ortamlarda `Image` `C:\Windows\System32\clip.exe`, WOW64'te `SysWOW64\clip.exe`. Kural yalnızca System32'ye bakıyorsa SysWOW64 kaçar.

**Varsayılan loglanmayan şeyler — bu en kritik saha gerçeği:**
- **`clip.exe` çalıştığını görmek için Sysmon Event ID 1 (process creation) veya Windows Security 4688 şart.** 4688 varsayılan olarak **kapalıdır**; "Audit Process Creation" advanced audit policy'sini açman gerekir. Üstüne komut satırını görmek için ayrıca `Include command line in process creation events` registry/GPO ayarını (`ProcessCreationIncludeCmdLine_Enabled`) açmalısın — yoksa 4688 gelir ama CommandLine boş olur ve `CommandLine|contains` mantığı **hiçbir zaman eşleşmez**. Bu, sahada en sık gördüğüm sessiz başarısızlıktır: kural "çalışıyor" ama komut satırı boş olduğu için hiç ateşlemiyor.
- **PowerShell `Get-Clipboard` / .NET Clipboard için Script Block Logging (4104) şart** ve bu da varsayılan kapalı. Sadece module logging (4103) açıksa cmdlet adını yakalarsın ama obfuscation'ı kaçırırsın. 4104 + AMSI kombinasyonu gerçek görünürlüğü verir.
- **Keylogging kancasının kendisi hiçbir standart logda yoktur.** Ne Security, ne Sysmon (varsayılan config), ne PowerShell logları `SetWindowsHookEx`'i gösterir. Buna görünürlük ancak EDR'nin user-mode API telemetrisiyle ya da özel ETW (`Microsoft-Windows-Threat-Intelligence` — sadece PPL/EDR erişebilir) ile gelir. Yani "keylogger tespit kuralım var" diyen çoğu ekip aslında keylogger'ın *çıktısını/persistence'ını* tespit ediyor, kancayı değil. Bunu ekibe dürüstçe söyle: kancanın kendisi normalde görünmez.
- **Sysmon config kalitesi belirleyici.** Boş/SwiftOnSecurity temel config'i clipboard araçlarını process olarak yakalar ama Sysmon Event ID 24 (clipboard change — Sysmon v11+) çoğu config'te **açık değildir**. Event ID 24 açıksa, pano içeriğinin *değiştiği* anı ve hangi process'in yazdığını görürsün (RDP üzerinden clipboard hijack tespiti için altın değerinde), ama gürültülü olduğu için genelde kapalı tutulur. Bunu bilinçli bir tuning kararı olarak, yüksek-değerli sunucularda aç.

**Splunk vs Sentinel vs Elastic farkları:**
- **Splunk:** Korelasyonu genelde `transaction` ya da `stats` ile ProcessGuid üzerinden yaparsın; Desen A/B için `| stats values(*) by process_guid` sonra multi-condition eval. Cross-source (endpoint+identity) korelasyon için data model uyumu (CIM) şart, yoksa clipboard olayı `Endpoint` model'inde, logon `Authentication` model'inde kalır ve join elle yazılır.
- **Sentinel:** KQL ile `join`/`union` doğal; capture olayını (`DeviceProcessEvents`) sign-in ile (`SigninLogs`/`SecurityEvent`) `AccountName`/`AccountUpn` üzerinden birleştirmek Desen C için idealdir. Ama `DeviceProcessEvents` yalnızca Defender for Endpoint varsa dolar; salt Sysmon-to-Sentinel akışında farklı tabloda (`Event` / custom) olur ve field adları değişir.
- **Elastic:** ECS normalizasyonu güçlü; `process.command_line`, `process.parent.entity_id` ile soyağacı korelasyonu EQL sequence sorgusuyla (`sequence by process.entity_id`) Desen A'yı zarifçe ifade eder — EQL bu tür zaman-sıralı çoklu-olay desenleri için en iyi dildir. Ama auditd `a0..aN` alanları ECS'e tam oturmaz; Auditbeat kullanıyorsan `process.args` array'ine bakman gerekir, ham `a1/a2` alanlarına değil.

**Tuning tavsiyem:** Bu aileyi tek bir "alarm" olarak değil, **katmanlı** kur. Ham capture kurallarını (clip.exe, xclip, osascript, Get-Clipboard) `level: low` / **alarm üretmeyen risk boyası** olarak bırak — Sigma'nın kendi seviyelendirmesi doğru. Gerçek case'i, bu boyaların Desen A/B/C korelasyonuyla ikinci bir yüksek-değerli sinyale bağlandığı korelasyon kuralından çıkart. İş istasyonlarında ham kuralları neredeyse tamamen bastır (Sigma zaten "sunucularda kullan" diyor); sunucularda ve yüksek-değerli host'larda (jump box, DC, geliştirici makinesi değil ama admin makineleri) sıkı tut. En büyük operasyonel kazancı, allowlist'i process-adından imza+yol+davranış profiline taşıyarak alırsın — çünkü bu ailedeki gürültünün kaynağı neredeyse her zaman meşru clipboard/otomasyon araçlarıdır, egzotik saldırı değil.

**Son söz — dürüst beklenti:** Keylogging'in kancasını komut satırı loglarıyla yakalayamazsın; bunu iddia eden kural seni yanıltır. Clipboard capture'ı ise yakalarsın ama meşru kullanımdan ancak yön + frekans + soyağacı + korelasyon ile ayırırsın. Bu ailede tek imza değil, **bağlanmış sinyal** kazandırır.
