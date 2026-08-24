# SharpHound / BloodHound Toplama — Tespiti

> Saha notu. Bu metin "BloodHound nedir"i anlatmak için değil, o toplamayı gerçek bir SOC'ta *yakalamanın* neden zor olduğunu ve neyle yakalandığını anlatmak için yazıldı. Kural adları, field'lar ve event ID'ler orijinal bırakıldı.

## 1. Özet: saldırı + naif tespit

BloodHound, Active Directory'yi bir *graf* olarak modelleyen bir keşif ve saldırı-yolu haritalama aracıdır. Node'lar kullanıcılar, gruplar, bilgisayarlar, GPO'lar, OU'lar, sertifika şablonlarıdır; edge'ler ise "AdminTo", "MemberOf", "HasSession", "CanRDP", "GenericAll", "AddKeyCredentialLink" gibi ilişkilerdir. Toplama işini yapan bileşen **SharpHound** (klasik C# collector) ya da onun Rust portu (SharpHound'un yeni sürümleri) ve Azure tarafında **AzureHound**'dur. SharpHound bir domain'e authenticate olmuş herhangi bir düşük yetkili kullanıcıyla çalışır — çünkü topladığı şeylerin büyük kısmı zaten domain kullanıcılarının okumaya yetkili olduğu dizin bilgisidir. Saldırgan bu grafı "Kerberoastable kullanıcı → hangi makinede admin → o makinede kimin oturumu açık → o oturum bir Domain Admin mi" zincirini bulmak için kullanır. Yani BloodHound saldırı değil, *saldırının GPS'idir*.

Naif tespit herkesin bildiği yerden başlar. SharpHound toplarken üç ana kaynağa dokunur: LDAP (dizin nesneleri ve ACL'ler), SMB/RPC (oturum ve yerel grup üyeliği — SrvSvc ve WkstaSvc arayüzleri), ve bazen SAMR/GPO dosya paylaşımları. Klasik "kural" reçeteleri şunları söyler: SharpHound.exe image adını yakala, komut satırında `-c All` / `--collectionmethods` / `Invoke-BloodHound` gibi argümanları ara, kısa sürede *çok sayıda* hosta 445/135/389 bağlantısı gören bir davranışsal eşik koy, ve AV imzasına güven (Sigma'daki `Antivirus - Hacktool Signature` kuralı `Signature|contains: 'BloodH'` ile tam bunu yapar). Azure tarafında ise `Discovery Using AzureHound` kuralı `signinlogs`'ta `userAgent|contains: 'azurehound'` ve `ResultType: 0` ile default User-Agent'ı yakalar.

Bu kadarı bir demo ortamında çalışır. Kırmızı takımın gerçekten uğraştığı ve mavi takımın gerçekten kör kaldığı yer buranın hemen ötesinde başlar.

## 2. Naif tespit neden yetmez

**İmza/isim tabanlı tespit en kırılgan katmandır.** `SharpHound.exe` adını arayan bir kural, dosyanın adını `svc_report.exe` yapan herkese karşı kördür. Komut satırı argümanı aramak (`Invoke-BloodHound`, `-c All`) yalnızca PowerShell/CLI ile çalıştıranı yakalar; SharpHound'u bir loader'ın içine gömüp reflective load eden ya da execution-assembly olarak `execute-assembly` ile Cobalt Strike/Havoc beacon'ı içinden bellekten çalıştıran saldırgan process_creation event'i hiç üretmez — parent `beacon`, image ise `rundll32` veya legit bir host process olur. AV imzası (`BloodH`, `BloodyAD`, `Adfind`) yalnızca diskteki bilinen binary'yi yakalar; hafif bir obfuscation, sürüm değişikliği ya da yeni Rust collector imzayı ıskalatır. AV imzası tetiklendiğinde iş çoktan bitmiş de olabilir — o yüzden Nextron kuralının açıklaması boşuna "AV bloklamış olsa bile *nasıl geldiğini* araştır" diye ısrar etmez.

**LDAP tarafı varsayılan olarak neredeyse görünmezdir.** SharpHound'un topladığı dizin bilgisinin ezici çoğunluğu tek bir DC'ye yapılan LDAP sorgularıyla gelir. Windows, LDAP sorgularını *varsayılan olarak loglamaz*. Event 4662 (Directory Service Access) teorik olarak nesne erişimini görebilir ama default'ta SACL'lar bu kapsamı vermez ve etkinleştirildiğinde DC'yi olay seliyle boğar. Yani "SharpHound LDAP'a bağlandı" olayı çoğu ortamda *hiç yoktur*. Elinizde kalan, LDAP'ın kendisi değil, onun etrafındaki dolaylı sinyallerdir.

**Davranışsal eşik (fan-out) false positive üretir ve kolayca atlatılır.** "Kısa sürede N farklı hosta bağlanan process" mantığı iyi bir sezgidir ama iki yönden bozulur. Bir yandan meşru araçlar tam olarak bunu yapar: SCCM/MECM envanter ajanı, vulnerability scanner (Nessus/Qualys/Tenable), yedekleme yazılımı, EDR'ın kendi discovery taraması, ağ envanter araçları — hepsi tek makineden yüzlerce hosta dokunur. Öte yandan saldırgan `--stealth` moduyla yalnızca zaten bağlı olduğu oturumlardan veri toplayarak, `--throttle` ve `--jitter` ile istekleri güne yayarak fan-out grafiğini düzleştirir. Bir günde 800 host yerine üç günde saatte 10 host taradığında eşiğinizin altında kalır.

**RPC Firewall kuralları güçlüdür ama çoğu ortamda mevcut değildir.** Verilen Sigma kurallarının ikisi (`SharpHound Recon Account Discovery` ve `SharpHound Recon Sessions`) çok değerli çünkü SharpHound'un *SMB/RPC toplama davranışının kalbini* hedefler — ama `logsource: product: rpc_firewall`. Bu, Zero Networks RPC Firewall'un kurulu, tüm process'lere uygulanmış ve `audit:true` ile yapılandırılmış olmasını gerektirir. Sahada bu ürün olan ortam nadirdir. Yani bu kurallar "doğru sinyali" tarif eder ama telemetriyi *sizin üretmeniz* gerekir; kutudan çıkan Windows loglarında bu event'ler yoktur.

Özet: naif katman ismi, argümanı, imzayı ve kaba hacmi yakalar. Olgun saldırgan hepsini ayrı ayrı devre dışı bırakabilir. Değer, tek başına zayıf olan sinyalleri *birbirine bağlamakta*.

## 3. Korelasyon zinciri (asıl değer)

Buradaki fikir şu: SharpHound toplaması tek bir "gürültülü" event değil, birbirini takip eden bir *davranış imzasıdır*. Hiçbiri tek başına alarm etmeye değmez; birlikte gelince yüksek güven verir.

SharpHound'un SMB/RPC toplaması, hedef makinelerde belirli RPC arayüzlerine ardışık çağrılar üretir. Sigma kurallarındaki UUID'ler tam olarak bunlardır:
- `4b324fc8-1670-01d3-1278-5a47bf6ee188` OpNum 12 → **SrvSvc / NetSessionEnum** (bir hosttaki açık oturumları listeleme — "HasSession" edge'inin kaynağı, T1033).
- `6bffd098-a112-3610-9833-46c3f87e345a` OpNum 2 → **WkstaSvc / NetrWkstaUserEnum** (uzaktan oturum açmış kullanıcıları sayma, T1087).

Bunlara pratikte SAMR (yerel grup üyeliği — "AdminTo" edge'i, `12345778-1234-abcd-ef00-0123456789ac`) da eşlik eder.

**Korelasyon deseni — tek host imzası:**
`A) Tek bir kaynak host/kullanıcıdan, kısa pencere içinde (dakikalar), çok sayıda hedef makinede peş peşe SrvSvc NetSessionEnum + WkstaSvc NetrWkstaUserEnum + SAMR çağrıları` +
`B) aynı kaynak sürecin/oturumun kısa süre önce DC'ye anormal hacimde LDAP/389 (veya 636) trafiği açmış olması` +
`C) bu üç RPC arayüzünün *aynı hedeflere aynı sırayla* dokunulması`.
Tek başına NetSessionEnum meşrudur (monitoring araçları yapar). Ama "önce DC'ye toplu LDAP → sonra onlarca hosta SrvSvc+WkstaSvc+SAMR üçlüsü, hepsi aynı süreçten, dakikalar içinde" deseni SharpHound `-c All`'un *parmak izidir* ve meşru bir aracın bu tam kombinasyonu bu sırayla yapması nadirdir.

**Çok aşamalı, çok hostlu desen (gerçek ihlal sinyali):**
Bunu bir zaman çizgisine oturttuğunuzda ihlal hikâyesi çıkar:
1. `T+0`: Bir workstation'da (kullanıcı `jdoe`) anormal bir parent-child zinciri — Outlook/Word → `powershell`/`rundll32` → dışa C2 benzeri beacon (uzun aralıklı, düşük hacimli giden bağlantı).
2. `T+3dk`: *Aynı* host `jdoe`'dan DC'ye yoğun LDAP + ardından iç ağda geniş SrvSvc/WkstaSvc fan-out (SharpHound toplama).
3. `T+15dk`: Toplama biter, kısa bir sessizlik (saldırgan grafı analiz ediyor).
4. `T+40dk`: *Farklı bir bağlamda* — `jdoe`'nun normalde hiç dokunmadığı bir sunucuya doğru Kerberos TGS isteği (4769) ve ardından bir servis hesabına yönelik erişim, ya da `jdoe`'nun BloodHound'un "en kısa yol"unda çıkan bir makinede ilk kez oturum açması / WMI-PsExec ile lateral movement.

İşte korelasyonun kalbi bu: **keşiften eyleme geçiş.** BloodHound toplaması izole bir merak değildir; onu takip eden 30-90 dakika içinde saldırgan *grafın gösterdiği yolu yürür*. Bu yüzden en değerli tespit, "SharpHound gördüm" alarmı değil, "aynı kimlik/host, keşiften sonra daha önce hiç yapmadığı bir ayrıcalıklı erişimi ilk kez deniyor" korelasyonudur. SharpHound sinyali burada *bağlam güçlendiricidir*: tek başına orta güven olan lateral movement alarmını, öncesinde bir toplama gördüğünüz için yüksek güvene çıkarır.

Pratik SIEM ifadesi olarak: SrvSvc/WkstaSvc/SAMR RPC olaylarını (ya da RPC Firewall yoksa, aşağıda anlatılan Sysmon Network + 4624/4672 vekilleri) bir kaynak host kimliği etrafında *distinct hedef sayısına* göre grupla; aynı kaynağın 60 dakikalık penceresinde bir de "yeni/anormal ayrıcalıklı erişim" (4769 anormal servis, 4672 beklenmedik host, ilk-kez admin oturumu) varsa risk skorunu birleştir. İki orta sinyal = bir yüksek incident.

## 4. False positive gerçeği ve triage yargısı

Bu alarmların meşru üreticileri her ortamda vardır ve isimleriyle bilmek triage'ı dakikalar yerine saniyelere indirir:

- **SCCM / MECM (ConfigMgr):** Envanter döngüleri makinelerden kullanıcı/oturum ve yerel grup bilgisi toplar. Kaynak genelde bilinen bir management point sunucusu ve `svc_sccm` benzeri bir servis hesabıdır.
- **Vulnerability scanner'lar (Nessus, Qualys, Tenable.io, Rapid7):** "Authenticated scan" modunda tam olarak SharpHound gibi görünürler — tek kaynaktan tüm ağa SMB/RPC/SAMR. Genelde sabit bir scanner IP'si ve bir `svc_scan` hesabı, ve *düzenli, zamanlanmış* bir profilleri vardır.
- **Yedekleme ve DR yazılımı (Veeam, CommVault):** Geniş SMB erişimi.
- **AD hijyen/keşif araçları:** PingCastle, Purple Knight, ADRecon, BloodHound'un *mavi takım tarafından* çalıştırılan meşru sürümü. Burası özellikle sinsi: kendi güvenlik ekibiniz aylık bir BloodHound taraması çalıştırıyor olabilir — bu *birebir aynı* telemetriyi üretir.
- **Admin script'leri:** `PSExec`, `Get-NetSession`, envanter için elle çalıştırılan PowerShell.

**Kıdemli analist gerçek/gürültü ayrımını nasıl yapar?** Sıralı bir yargı uygular:

1. **Kaynak kimliği ve host'un doğası.** Alarm bir sunucudan (SCCM MP, scanner appliance) ve bir *servis hesabından* mı geliyor, yoksa bir insan kullanıcının workstation'ından ve *interaktif* bir oturumdan mı? SharpHound'un tehlikeli hâli neredeyse her zaman ikincisidir. `svc_scan@scanner01`'den gelen fan-out büyük olasılıkla gürültü; `jdoe@WKS-4471`'den gelen aynı fan-out kırmızı bayrak.
2. **Periyodiklik.** Meşru toplayıcılar *zamanlanmıştır*. Bu tam desen her Salı 02:00'de mi görülüyor? O zaman baseline'dır. Rastgele bir Çarşamba 14:37'de, bir insan oturumundan, ilk kez mi? Şüpheli.
3. **Öncesi ve sonrası (bu en kritik yargıdır).** Analist tek başına fan-out'a bakmaz; *o kimliğin o penceredeki bağlamına* bakar. Kaynak process ne? Parent zinciri normal mi (SCCM ajanı `ccmexec.exe`) yoksa `winword.exe → powershell.exe` gibi phishing kokan bir şey mi? Fan-out'tan *önce* bir C2 benzeri beacon var mı? *Sonra* bir lateral movement / anormal Kerberos var mı? Meşru scanner'ın öncesinde beacon, sonrasında lateral movement olmaz.
4. **Kapsam ve seçicilik.** Authenticated vuln scan *her şeyi* tarar — tüm portlar, tüm servisler, tutarlı. SharpHound *seçicidir* — sadece dizin/oturum/grup ile ilgili RPC'ler, LDAP ağırlıklı, port taraması yok. Telemetrideki bu "profil farkı" ayırt edicidir.

**Çoklu alarmda önce neye bakar?** Skor toplamına değil, *kill-chain'de en ileri* olan sinyale. Elinde aynı anda "SharpHound fan-out", "yeni admin oturumu" ve "anormal 4769" varsa, analist toplama alarmını değil, *ayrıcalık kazanımını/lateral movement'ı* önce doğrular — çünkü keşif geri alınamaz değildir ama aktif lateral movement devam eden bir ihlaldir. Toplama alarmı burada "bu tesadüf değil" diyen bağlamı sağlar, ama saatin durdurulması gereken yer zincirin ucudur.

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan kural dokümanında *yazmayan* yolları dener. Her birinin ikinci-derece bir tespiti vardır.

**Kaçınma 1 — In-memory execution (`execute-assembly`).** SharpHound'u diske hiç yazmadan, bir C2 beacon'ı içinden .NET assembly olarak bellekte çalıştırır. process_creation kuralı ve AV disk imzası kör kalır.
*Karşı-tespit:* Ağ katmanı yalan söylemez. Assembly bellekte olsa da, NetSessionEnum/NetrWkstaUserEnum çağrıları hâlâ *ağdan* gitmek zorundadır. Sysmon Event ID 3 (Network Connection) ve RPC telemetrisi hedeflere giden bağlantı desenini yakalar; kaynak process'in beklenmedik oluşu (host bir surrogate process ise .NET CLR yüklenmesi — Sysmon Image/DLL load, `clr.dll`/`mscoree.dll`'in olmaması gereken bir process'e enjekte olması) ikinci sinyaldir. Ayrıca ETW-based .NET assembly load telemetrisi (bazı EDR'lar) belleğe yüklenen assembly adını görebilir.

**Kaçınma 2 — Stealth / oturum-tabanlı toplama (`--stealth`).** Fan-out'u minimize eder; yalnızca zaten var olan oturumlardan ve DC'nin kendisinden veri çeker, agresif host enumerasyonu yapmaz.
*Karşı-tespit:* Fan-out düşünce LDAP tarafı görece artar. DC üzerinde LDAP telemetrisi (aşağıda) ya da DC'ye anormal hacimli LDAP sorgusu deseni öne çıkar. Ayrıca stealth mod hâlâ SharpHound'un karakteristik LDAP sorgu setini (özellikle ACL/`nTSecurityDescriptor` toplaması) üretir — bu ağır ACL okuması meşru uygulamalarda nadirdir.

**Kaçınma 3 — Throttle/jitter ile zamana yayma.** Toplamayı günlere böler, saatlik eşiklerin altına iner.
*Karşı-tespit:* Kısa pencere eşikleri iflas eder; *uzun ufuklu baseline* gerekir. "Bu kimlik son 24-72 saatte kaç *distinct* hosta SrvSvc/WkstaSvc çağrısı yaptı" metriğini kullanıcı bazında baseline'a göre değerlendirmek gerekir. Yavaş toplama zamanı yayar ama *toplam kapsamı* yaydığında hâlâ o kullanıcının normalinin çok üstündedir. Kümülatif distinct-host sayacı jitter'ı yener.

**Kaçınma 4 — Meşru User-Agent / imza taklidi (özellikle AzureHound).** `Discovery Using AzureHound` kuralı default User-Agent `azurehound`'a bağlıdır. Saldırgan User-Agent'ı `python-requests` ya da normal bir tarayıcı stringiyle değiştirir; kural anında kör olur.
*Karşı-tespit:* User-Agent zayıf bir çapadır. Bunun yerine *davranışa* bak: Graph/AzureAD'ye kısa sürede geniş dizin enumerasyonu (kullanıcılar, gruplar, rol atamaları, service principal'lar) yapan bir kimlik, tek bir OAuth token'ıyla anormal genişlikte okuma. Azure tarafında sign-in'in konumu/cihazı (impossible travel, yeni cihaz) ve token'ın kapsamı ikinci sinyaldir. UEBA burada User-Agent'tan çok daha dayanıklıdır.

**Kaçınma 5 — LDAP yerine ADWS / farklı transport.** SharpHound'un bazı sürümleri ve türev araçlar (SOAPHound gibi) veriyi klasik LDAP yerine ADWS (Active Directory Web Services, 9389/tcp) üzerinden çeker — LDAP odaklı tespitleri tamamen atlar.
*Karşı-tespit:* 9389 portuna (ADWS) giden anormal client trafiği başlı başına nadir ve şüphelidir; normalde yalnızca belirli yönetim araçları (`Get-ADUser` vb.) bu portu kullanır. Bir workstation'dan DC'nin 9389'una toplu SOAP sorgusu güçlü bir ikinci-derece sinyaldir. Transport değişimi bir tespiti öldürür ama yeni, daha nadir bir imza açar.

**Kaçınma 6 — Yeniden derleme / obfuscation / yeni collector.** İsmi değiştir, string'leri obfuscate et, Rust collector'ı kullan.
*Karşı-tespit:* Bu tam olarak neden isim/imza tabanlı katmana güvenilmemesi gerektiğini gösterir. Cevap davranışsal invariant'lardır: hangi dilde yazılırsa yazılsın, SharpHound *NetSessionEnum + NetrWkstaUserEnum + SAMR + ağır ACL LDAP* yapmak *zorundadır* — çünkü BloodHound grafının edge'leri bu API'lerden gelir. Fonksiyonel invariant'ı hedefleyen tespit yeniden derlemeye karşı bağışıktır; string'i hedefleyen tespit değildir.

Genel ders: her atlatma bir kapıyı kapatırken başka, çoğu zaman *daha nadir ve dolayısıyla daha yüksek sinyalli* bir kapı açar. Kedi-fare, saldırganı imzadan davranışa, davranıştan da giderek daha egzotik ve tespiti kolay transport'lara itmekle kazanılır.

## 6. SIEM / saha gerçeği

**Varsayılan loglanmayan şeyler — önce telemetriyi kur.** En büyük yanılgı, kuralı yazınca tespitin var olduğunu sanmaktır. Gerçek:
- **LDAP sorguları default'ta loglanmaz.** Görünürlük istiyorsanız ya DC'de bir SACL/4662 stratejisi (dikkatli, seçici — yoksa boğulursunuz) ya da bir ağ sensörü (Zeek/Corelight LDAP protokol ayrıştırması) gerekir. Windows 2022+ ve bazı ortamlarda **AD LDAP Diagnostic / "expensive & inefficient LDAP queries" (Event 1644)** açılabilir ama bu operasyonel yük getirir.
- **SrvSvc/WkstaSvc RPC çağrıları** kutudan çıkmaz. Verilen iki Sigma kuralının çalışması için **RPC Firewall (Zero Networks)** kurmanız gerekir — `EventLog: RPCFW`, `EventID: 3`. Bu yoksa kural "test" statüsünde kalır, sizde hiç tetiklenmez. Alternatif vekil: **Sysmon Event ID 3** ile 445/135 hedeflerine fan-out + **Windows Security 5140/5145** (network share access, "File Share" audit policy açıksa) + hedef hostlarda **4624 Type 3** oturumları.
- **SAMR ve yerel grup enumerasyonu** için **"Audit Detailed Directory Service Replication" değil**, hedef makinede yerel SAM erişimini görmek istersiniz — bu da genelde ayrı audit gerektirir ve pahalıdır.
- **Sysmon config şart.** Boş/varsayılan Sysmon işe yaramaz. Network connection (EID 3), image load (EID 7, .NET CLR enjeksiyonu için), process creation (EID 1, tam komut satırı ve hash ile) *etkin ve tuned* olmalı. `-c All` argümanını yakalamak istiyorsanız komut satırı loglaması (Security 4688 + "Include command line" GPO, ya da Sysmon EID 1) açık olmalı — 4688 default'ta komut satırını *yazmaz*.

**Field mapping tuzakları.** Sigma kuralı soyuttur; ürüne indirdiğinizde field adları değişir:
- RPC Firewall kuralındaki `InterfaceUuid` ve `OpNum` yalnızca RPCFW logunda vardır. Sysmon'a çevirirken bu semantik *yoktur* — Sysmon size UUID/OpNum vermez, sadece hedef IP/port verir. Yani kuralı birebir "map"leyemezsiniz; toplama davranışının *ağ vekilini* yazmak zorundasınız. Bu, "aynı tespit farklı telemetride bambaşka bir kural" gerçeğinin tipik örneğidir.
- AzureHound kuralındaki `userAgent` alanı Azure AD sign-in loglarında `userAgent` iken, aynı veriyi Sentinel'e aldığınızda `SigninLogs` tablosunda genelde farklı bir kolon adı ve JSON iç içe yapısı olur; `ResultType: 0` (başarılı) filtresini unutmak, başarısız denemeleri de saymanıza ve gürültüye yol açar.
- AV kuralındaki `Signature|contains: 'BloodH'` gibi alanlar EDR'dan EDR'a (`ThreatName`, `DetectionName`, `Signature`, `malware.name`) değişir. Normalize edilmiş bir şema (ECS/ASIM) yoksa her kaynağa ayrı map gerekir.

**Splunk vs Sentinel vs Elastic farkı.**
- **Splunk:** Fan-out korelasyonu için `stats dc(dest_host) by src_user, _time span=10m` doğal bir kalıptır; distinct-host eşiği ve baseline'ı `streamstats`/lookup ile kurarsınız. Zaman-pencereli korelasyon güçlü ama *yavaş yayılan* (jitter) saldırıyı yakalamak için summary index'te kümülatif sayaç tutmanız gerekir.
- **Sentinel (KQL):** ASIM normalize şeması ve `SecurityEvent`/`DeviceNetworkEvents` tabloları ile; `make_set`/`dcount` ile fan-out, ve *scheduled analytics rule*'da 24 saatlik lookback ile jitter'ı yakalamak Splunk'a göre daha rahat. AzureHound tespiti Sentinel'in doğal sahasıdır (SigninLogs zaten oradadır).
- **Elastic:** ECS alan adları (`source.user.name`, `destination.ip`, `network.protocol`) ile; EQL *sequence* sorguları korelasyon zinciri için ideal — "LDAP burst *sonra* SrvSvc fan-out *sonra* lateral movement" desenini `sequence by host.id with maxspan=1h` ile birebir yazabilirsiniz. Bu üç platform içinde çok-aşamalı deseni en doğal ifade edeni EQL sequence'tir.

**Tuning gerçeği.** Bu tespit *allowlist olmadan yaşamaz*. Devreye alır almaz SCCM MP'leri, scanner IP/hesaplarını, yedekleme sunucularını ve kendi mavi-takım BloodHound tarayıcınızı istisna listesine koymadan alarm seli alırsınız — ve o selin içinde gerçek saldırgan kaybolur. Ama allowlist'i *çok geniş* tutarsanız (örn. "tüm servis hesaplarını yok say"), saldırgan ele geçirdiği bir servis hesabıyla toplama yaparak istisnanın arkasına saklanır. Doğru tuning: kaynağı *hem kimlik hem host hem davranış profili* ile daralt (yani "svc_scan yalnızca scanner01'den ve yalnızca tam-kapsam profiliyle geldiğinde meşru; aynı hesap bir workstation'dan gelirse alarm"). İyi tespit bir tekil kural değil, birkaç orta sinyali risk skoruyla birleştiren ve iyi tutulmuş bir baseline'a dayanan bir *sistemdir*. Kuralı yazmak işin %20'si; telemetriyi kurmak ve altı ay boyunca tune etmek %80'idir.
