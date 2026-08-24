# Credential Dumping Derinlemesine: LSASS, DPAPI, Credential Guard/LSA Protection Atlatma

## Giriş ve Kapsam

Credential Access, MITRE ATT&CK matrisinde kimlik doğrulama materyalinin (parola hash'leri, Kerberos biletleri, DPAPI ile korunan sırlar, doğrudan parolalar) sistemden çıkarılmasını ifade eder. Pass-the-Hash, Pass-the-Ticket ve Kerberoasting gibi teknikler bu materyalin *kullanımını* anlatır; bu makale ise materyalin *nereden ve nasıl çıkarıldığını* — yani dumping aşamasını — ele alır. Windows ekosisteminde bu aşamanın merkezinde üç bileşen vardır: **LSASS** (Local Security Authority Subsystem Service) süreç belleği, **DPAPI** (Data Protection API) ile korunan disk-üzeri sırlar, ve bunları korumak için geliştirilen **Credential Guard / LSA Protection (PPL)** savunma katmanları. Bir savunmacı veya sistem mühendisi açısından bu üçgeni anlamak, "neden bir EDR bazen dump'ı yakalayıp bazen kaçırır" sorusuna cevap verir.

## KÖK NEDEN: LSASS Neden Bu Kadar Değerli Bir Hedef?

Windows'ta kullanıcı oturum açtığı anda, kimlik doğrulama paketleri (MSV1_0/NTLM, Kerberos, WDigest, CredSSP, Negotiate) kullanıcının kimlik bilgilerini bir sonraki tek-oturum-açma (SSO) işlemi için bellekte tutar. Bu, kullanıcıya her ağ kaynağına eriştiğinde parolasını tekrar sormamak içindir — yani SSO'nun *kendisi* kök nedendir. Bu materyal LSASS.exe sürecinin adres alanında, çeşitli veri yapılarında (örneğin `LogonSessionList`, kimlik doğrulama paketlerinin kendi iç yapıları) saklanır:

- **NTLM hash'i**: MSV1_0 paketi tarafından tutulur, Pass-the-Hash'e girdi sağlar.
- **Kerberos biletleri (TGT/TGS) ve anahtarlar**: Kerberos paketi tarafından tutulur.
- **Düz metin parola (bazı koşullarda)**: WDigest etkinse (eski sistemlerde varsayılan açıktı, modern Windows'ta varsayılan kapalı ama registry ile geri açılabilir) veya Credential Manager/CredSSP gibi bazı akışlarda düz metne yakın formda tutulabilir.

Kök neden budur: **kullanılabilirlik (usability) ile güvenlik arasındaki klasik gerilim**. SSO olmadan kurumsal ortam kullanılamaz hale gelir; ama SSO'yu mümkün kılan mekanizmanın kendisi, "yerel yönetici hakkına erişen herkes tüm oturum açmış kullanıcıların kimlik materyaline erişebilir" riskini doğurur. Bu yüzden LSASS dump'ı "bir zafiyet" değil, **tasarımın doğal bir sonucudur** — savunma bu gerçekten kaçamaz, sadece erişim maliyetini yükseltmeye çalışır.

## LSASS Bellek Dump Teknikleri: Çalışma Mantığı

### 1. MiniDump API ile Klasik Yaklaşım

Windows'un `MiniDumpWriteDump` (DbgHelp/comsvcs.dll üzerinden erişilebilen) API'si, herhangi bir sürecin bellek görüntüsünü bir `.dmp` dosyasına yazmak için tasarlanmıştır — asıl amacı **çökme (crash) analizi ve hata ayıklamadır**, kötü amaçlı değildir. Bir saldırgan yeterli ayrıcalığa (tipik olarak `SeDebugPrivilege` + yerel yönetici) sahipse, bu API'yi LSASS sürecine karşı çağırarak tam bir bellek kopyası alabilir. Kopya diskte veya bellekte oluşturulduktan sonra, saldırgan kendi ortamında offline olarak (örneğin Mimikatz benzeri bir araç ile) bu dump'ı parselleyip kimlik doğrulama paketlerinin veri yapılarını bulur ve materyali çıkarır.

**Neden çalışır**: MiniDump legitim bir Windows API'sidir, imzalı `rundll32.exe` veya `comsvcs.dll`'in `MiniDump` export'u gibi "living-off-the-land" ikilileri üzerinden bile tetiklenebilir. Bu, saldırıya özel bir "hacking aracı" getirmeden, sisteme zaten ait bir yeteneği kötüye kullanmak anlamına gelir.

**TESPİT**: 
- LSASS'e yönelik `PROCESS_VM_READ` / `PROCESS_ALL_ACCESS` seviyesinde handle açan süreçlerin izlenmesi (Sysmon Event ID 10 — ProcessAccess, `TargetImage` alanında `lsass.exe`).
- `rundll32.exe comsvcs.dll, MiniDump` çağrı desenlerinin komut satırı telemetrisinde yakalanması.
- LSASS süreç belleği üzerinde disk'e yazma işlemi yapan (`CreateFile` + `WriteProcessMemory`/`MiniDumpWriteDump` çağrısı zinciri) süreçlerin ETW (Event Tracing for Windows) üzerinden korelasyonu.
- Dosya sistemi seviyesinde `.dmp` uzantılı, büyük boyutlu dosyaların olağandışı dizinlerde oluşması.

**SAVUNMA**:
- LSASS'e erişimi PPL (Protected Process Light) ile kısıtlamak (aşağıda detaylı).
- EDR'ın ProcessAccess olaylarını `GrantedAccess` maskesine göre filtrelemesi (örneğin `0x1010` veya `0x1438` gibi şüpheli maskeler bilinen dump araçlarının imzasıdır, ama bu imzalar değişebilir — davranışsal tespit daha dayanıklı).
- `SeDebugPrivilege`'in gereksiz hesaplardan alınması ve yönetici hesaplarının ayrılması (Tiering / PAW modeli).

### 2. Direct Syscalls ve Kullanıcı-Modu Hook'larını Atlatma

EDR ürünlerinin çoğu, kullanıcı modunda çalışan DLL'ler (`ntdll.dll` gibi) içindeki kritik fonksiyonların (`NtOpenProcess`, `NtReadVirtualMemory` vb.) başına "inline hook" yerleştirerek her çağrıyı kendi tarama motoruna yönlendirir (bu "userland hooking" olarak bilinir). Saldırgan, `ntdll.dll` içindeki bu fonksiyonların **hook'lanmamış** (temiz) versiyonlarını diskten veya başka bir süreçten okuyarak, ya da doğrudan syscall numarasını bilip **kullanıcı-modu DLL'i tamamen atlayarak** çekirdeğe (kernel) geçiş yapabilir. Buna "direct/indirect syscall" tekniği denir.

**KÖK NEDEN**: EDR'lerin çoğu tespiti kullanıcı modunda (ring 3) yapar çünkü çekirdek moduna (ring 0) müdahale etmek daha riskli ve karmaşıktır (BSOD riski, imzalı sürücü gereksinimi). Bu mimari tercih, saldırganın "kullanıcı modunu atlayıp doğrudan çekirdeğe konuşma" stratejisine açık bir alan bırakır.

**NASIL ÇALIŞTIĞI (kavramsal)**: Her Windows API çağrısı sonunda bir syscall numarası ile `syscall`/`sysenter` komutuna iner. Normalde bu, `ntdll.dll` içindeki küçük "stub" fonksiyonlar aracılığıyla olur. Saldırgan bu stub'ları EDR hook'undan etkilenmeyecek şekilde kendi kodunda yeniden oluşturur (doğru syscall numarasını bularak) ve böylece kullanıcı-modu izleme noktasını devre dışı bırakmadan, sadece "görmesini" engeller.

**TESPİT**:
- Çekirdek seviyesinde ETW sağlayıcıları (örneğin `Microsoft-Windows-Threat-Intelligence` — ETW-TI) kullanıcı-modu hook'undan bağımsız çalıştığı için bu tekniğe karşı daha dayanıklıdır; modern EDR'ler bu nedenle ETW-TI'a yönelmiştir.
- Çağıran modülün bellek bölgesinin (`ntdll.dll` olması beklenirken) anormal/RWX bir bellek sayfasından syscall yapması şüpheli bir imzadır (call-stack anomaly detection).
- Bellek taraması ile "unbacked/floating" executable bellek bölgelerinin (dosya sistemine bağlı olmayan) tespiti.

**SAVUNMA**: Kernel-mode telemetriye (ETW-TI, minifilter sürücüler) yatırım yapan bir EDR seçmek; call-stack doğrulama (stack unwinding) yapabilen ürünler tercih etmek; sadece kullanıcı-modu hook'una güvenen çözümlerin bu sınıfta zayıf kaldığını bilmek.

### 3. Handle Duplication (Var Olan Handle'ı Çalma)

LSASS'e zaten açık bir handle'a sahip başka bir süreç varsa (örneğin bir AV/EDR'ın kendisi tarama amacıyla LSASS'e handle açmış olabilir), saldırgan yeni bir `OpenProcess` çağrısı yapmadan, `DuplicateHandle` API'si ile **var olan handle'ı kendi sürecine kopyalayabilir**. Bu, LSASS'e "yeni" bir erişim talebinde bulunmadığı için, sadece `OpenProcess` çağrılarını izleyen basit tespit kurallarını atlatır.

**KÖK NEDEN**: Windows'un handle tablosu süreç-yerel değil, çekirdek-yönetimlidir; bir sürecin sahip olduğu handle, doğru izinlerle başka bir sürece devredilebilir. Bu, iletişim ve kaynak paylaşımı için gerekli bir mekanizmadır, ama güven sınırı yanlış yerde çizildiğinde kötüye kullanılabilir.

**TESPİT**: `DuplicateHandle` çağrılarının izlenmesi zordur (native API telemetrisi gerektirir); daha pratik yaklaşım, **hangi süreçlerin LSASS'e handle açtığını** başlangıçta beyaz listeye almak ve bu listenin dışında LSASS belleğine erişen her süreci (doğrudan açılmış ya da devralınmış handle fark etmeksizin) şüpheli saymaktır. Sysmon Event ID 10 hem `OpenProcess` hem bazı handle olaylarını yakalayabilir, ama tam kapsama için kernel-callback tabanlı EDR telemetrisi gerekir.

**SAVUNMA**: PPL/LSA Protection burada da devreye girer — çünkü PPL korumalı bir sürece, korumasız bir sürecin (EDR dahil, eğer EDR de PPL değilse) açtığı handle zaten sınırlıdır; koruma seviyesi (protection level) uyumsuzsa `DuplicateHandle` da başarısız olur.

### 4. PPL (Protected Process Light) / LSA Protection Atlatma

Microsoft, Windows 8.1'den itibaren LSASS'i **PPL** olarak çalıştırma seçeneği sundu (registry: `RunAsPPL`). PPL, sürecin çekirdek tarafından bir "koruma seviyesi" (protection level) ile işaretlenmesi ve sadece eşit veya daha yüksek koruma seviyesine sahip süreçlerin ona tam erişim (`PROCESS_VM_READ` gibi) alabilmesi anlamına gelir. İmzasız veya düşük seviyeli imzaya sahip bir süreç (tipik bir kullanıcı-modu saldırı aracı) LSASS'e `OpenProcess(PROCESS_VM_READ)` çağırdığında erişim reddedilir.

**KÖK NEDEN / neden atlatılabiliyor**: PPL bir **erişim kontrolü** katmanıdır, bir **izolasyon (sandboxing)** katmanı değildir — LSASS hala aynı çekirdek adres uzayını, aynı sürücü (driver) arayüzlerini kullanır. Bu nedenle bilinen atlatma vektörleri şunlardır:
- **İmzalı savunmasız sürücü (Bring Your Own Vulnerable Driver — BYOVD)**: Saldırgan, çekirdek modunda çalışan ve bilinen bir zafiyete sahip imzalı bir sürücüyü sisteme yükleyip, bu sürücü aracılığıyla çekirdek seviyesinde keyfi bellek okuma/yazma yapar; PPL kontrolü kullanıcı-modu `OpenProcess` çağrısında devreye girdiği için, çekirdek moduna zaten geçmiş bir saldırganı durduramaz.
- **PPL seviyesini kendi sürecine atama**: Eğer saldırgan zaten SYSTEM/çekirdek seviyesinde çalışıyorsa, kendi sürecini de PPL olarak işaretleyip LSASS ile "eşit seviye" elde edebilir (bu, PPL'in "erişimi kısıtlar ama çekirdek-önce ayrıcalığı değiştirmez" doğasından kaynaklanır).
- **LSA eklentisi (plugin) enjeksiyonu**: LSASS'in kendisi bazı özel DLL'leri (authentication package, security package, notification package) yüklemeyi bekler; eğer saldırgan bu mekanizmaya (registry üzerinden, yönetici hakkıyla) kendi imzalı/veya politika gereği kabul edilen bir DLL'i ekleyebilirse, kod LSASS'in **içinde**, PPL sınırının **dışarıda değil içerde** çalışır — bu bir bypass değil, "güvenilir içerden çalışma" durumudur ve genellikle yönetici hakkının zaten ele geçirildiği senaryolarda görülür.

**TESPİT**:
- BYOVD tespiti: bilinen savunmasız sürücü hash/isim listelerine (örneğin Microsoft'un sürücü engelleme listesi, HVCI/WDAC politikaları) dayalı tarama; yeni sürücü yüklemelerinin (Event ID 6 in System log, veya Sysmon Event ID 6 — DriverLoad) izlenmesi.
- LSA eklenti değişikliklerinin izlenmesi: `HKLM\SYSTEM\CurrentControlSet\Control\Lsa` altındaki `Authentication Packages`, `Security Packages`, `Notification Packages` değerlerinin değişim denetimi (registry auditing).
- PPL seviyesinin fiilen aktif olup olmadığının doğrulanması (bazı ortamlarda uyumluluk sorunları nedeniyle PPL kapatılır/kapalı kalır — bu başlı başına bir bulgu).

**SAVUNMA**:
- **HVCI (Hypervisor-protected Code Integrity)** ve **WDAC/Device Guard** ile imzasız veya bilinen-savunmasız sürücü yüklenmesini engellemek — BYOVD'nin önüne geçmenin en etkili yolu budur, çünkü PPL'in kendisi kernel'i güvenmiş varsayar.
- Microsoft'un "vulnerable driver blocklist" mekanizmasının güncel tutulması.
- Mümkünse **Credential Guard** ile birlikte kullanmak (aşağıda) — çünkü Credential Guard, PPL'in aksine, sırları LSASS'in adres uzayının tamamen dışına, ayrı bir izole ortama taşır.

## Credential Guard: Mimari ve Neden Farklı Bir Savunma Katmanı

### KÖK NEDEN / Tasarım Mantığı

PPL'in temel zaafı, korumanın **aynı ayrıcalık halkasında (ring 0/kernel)** uygulanmasıdır — çekirdeği ele geçiren bir saldırgan için PPL anlamsızlaşır. Credential Guard bu sorunu **donanım destekli sanallaştırma tabanlı izolasyon (VBS — Virtualization-Based Security)** ile çözer: Hyper-V'nin sağladığı bir hipervizör kullanılarak, normal Windows çekirdeğinin (VTL0 — Virtual Trust Level 0) bile erişemeyeceği ayrı, daha yüksek güvenli bir bölge (VTL1) oluşturulur. Kimlik doğrulama sırlarının işlendiği süreç (**LSAIso** — LSA Isolated, "LsaIso.exe" olarak da bilinir) bu VTL1 içinde çalışır.

Buradaki mantık: **normal çekirdek (VTL0) tehlikeye girse bile (rootkit, BYOVD, çekirdek exploit'i), VTL1'deki sırlara erişemez** — çünkü VTL0'ın kendisi VTL1'e göre daha düşük yetki seviyesindedir; bu, işletim sistemi içindeki bir "güven sınırını" işletim sisteminin altına, hipervizör seviyesine taşımaktır.

### Nasıl Çalışır (Kavramsal)

- NTLM hash'leri ve Kerberos TGT'leri artık normal LSASS sürecinde değil, VTL1 içindeki LSAIso sürecinde tutulur.
- LSASS (VTL0'da), kimlik doğrulama işlemlerini gerçekleştirmek için VTL1'e **RPC benzeri güvenli bir kanal** (secure kernel call) üzerinden istek gönderir; ham materyal hiçbir zaman VTL0'ın adres uzayına kopyalanmaz, sadece "bu istek geçerli mi" sorusunun cevabı (token, ticket vb. türetilmiş/sarılmış veri) dönmesi sağlanır.
- Sonuç olarak klasik Mimikatz tarzı "LSASS belleğini dump'la, hash'i çıkar" yaklaşımı, **hash'in artık o bellek bölgesinde bulunmaması** nedeniyle başarısız olur.

### Sınırlamaları ve Yaygın Atlatma/Yanlış Anlama Noktaları

- Credential Guard **NTLM/Kerberos anahtarlarını** korur ama sistemdeki **her türlü kimlik bilgisini değil**; örneğin bazı eski/uyumluluk protokolleri (WDigest gibi devre dışı bırakılmamışsa) veya uygulama seviyesinde saklanan parolalar (tarayıcı, RDP kayıtlı kimlik bilgileri) kapsam dışında kalabilir.
- Credential Guard, **NTLMv1** gibi zayıf/eski protokollerin veya bazı üçüncü parti SSP'lerin (Security Support Provider) kapsama alınamaması nedeniyle tam koruma sağlamayabilir — bu protokollerin devre dışı bırakılması tamamlayıcı bir adımdır.
- **Downgrade/devre dışı bırakma riski**: Credential Guard bir UEFI/registry politikası ile açılır; yerel yönetici hakkına sahip bir saldırgan (veya bir gruppolicy hatası) bunu kapatıp sistemi yeniden başlatarak korumayı devre dışı bırakabilir — bu nedenle **değişiklik izleme** (Credential Guard durumunun periyodik denetimi, `Device Guard` WMI sınıfı veya `msinfo32` çıktısı üzerinden) şart. UEFI Secure Boot ile birlikte kilitleme (Secure Boot + VBS lock), bu kapatmayı zorlaştırır.
- Credential Guard, donanım gereksinimleri (SLAT desteği, UEFI Secure Boot, Hyper-V) nedeniyle her makinede aktif olmayabilir; envanterde "hangi makinelerde açık/kapalı" bilgisinin güncel tutulması kritik bir savunma hijyeni maddesidir.

**TESPİT**: Credential Guard durumunun değişmesi (kapatılması) olay olarak loglanmalı; VBS/HVCI durumunu raporlayan sistem envanteri araçlarının (örneğin `Get-CimInstance -ClassName Win32_DeviceGuard`) düzenli çalıştırılması önerilir. LSAIso sürecine (`LsaIso.exe`) yönelik anormal erişim denemeleri de (başarısız olsa bile) bir tespit sinyalidir.

## DPAPI: Disk Üzerindeki Sırların Çözülmesi

### KÖK NEDEN

LSASS bellek dump'ı "o an bellekte olan" sırları hedefler; ama Windows'ta çok sayıda sır **diskte, şifreli halde** durur: kayıtlı tarayıcı parolaları, Wi-Fi anahtarları, RDP kimlik bilgileri, bazı uygulama sırları (örneğin bazı VPN istemcileri) — bunların hepsi **DPAPI** ile korunur. DPAPI'nin kök tasarım mantığı şudur: uygulamaların kendi şifreleme anahtar yönetimi yapmasına gerek bırakmadan, işletim sistemine "bunu benim için şifrele/çöz" demesini sağlamak. Bu kolaylık, anahtar zincirinin **kullanıcının oturum açma parolasına bağlanmasını** gerektirir — yani DPAPI'nin güvenliği nihayetinde kullanıcının parolasına (ya da domain ortamında bir yedek mekanizmaya) dayanır.

### Çalışma Mantığı (Kavramsal)

- DPAPI ile korunan her sır, kullanıcıya özel bir **master key** ile şifrelenir (AES gibi simetrik bir şifre kullanılarak); bu master key'in kendisi de kullanıcının parolasından türetilen bir anahtarla şifreli olarak diskte saklanır (`%APPDATA%\Microsoft\Protect\<SID>\` altında).
- Böylece zincir şöyle işler: **kullanıcı parolası -> türetilmiş anahtar -> master key çözümü -> master key ile asıl sırrın çözümü**.
- Domain ortamında, kullanıcı parolasını unutma/değiştirme senaryolarında master key'in kaybolmaması için bir **domain yedek anahtarı (backup key)**, domain denetleyicisinde tutulur; bu, kullanıcının parolası bilinmese bile, **domain yedek anahtarına erişimi olan biri (tipik olarak Domain Admin) tüm kullanıcıların DPAPI sırlarını çözebilir** demektir.

**Bu ikinci nokta kritik bir kök neden bulgusudur**: DPAPI'nin kurumsal kurtarılabilirlik özelliği (parola sıfırlamada veri kaybını önlemek), Domain Admin seviyesinde bir "herşey anahtarı" yaratır — Credential Access açısından bu, DPAPI'yi Golden Ticket'a benzer bir "domain çapında master key" riskine dönüştürür.

### TESPİT

- Domain yedek anahtarına erişim taleplerinin (`BackupKey` RPC çağrıları, örneğin `MS-BKRP` protokolü üzerinden) domain denetleyicisi loglarında izlenmesi; bu çağrılar normal iş akışında nadirdir, bir iş istasyonundan/servis hesabından gelen anormal BackupKey talepleri şüpheli sayılmalıdır.
- `%APPDATA%\Microsoft\Protect\` dizinine toplu/otomatik erişim (özellikle EDR/betik aracılığıyla, kullanıcının kendi oturumu dışında) davranışsal bir sinyal olabilir.
- Master key dosyalarının dışarı kopyalanması (exfiltration) sonrası offline çözme girişimleri ağda tespit edilemez; bu nedenle **önleme** (aşağıda) burada tespitten daha değerlidir.

### SAVUNMA

- Domain yedek anahtarının korunması = Domain Admin/Tier-0 korumasının bir parçasıdır; bu anahtara erişimi olanların kapsamı mümkün olduğunca daraltılmalı ve bu hesaplar için PAW (Privileged Access Workstation) zorunlu kılınmalıdır.
- Kullanıcıların tarayıcı/uygulama kayıtlı parolalarına güvenmesi yerine kurumsal parola yöneticisi kullanması teşvik edilmeli (DPAPI'ye bağlı riskin yüzey alanını küçültür).
- Windows Hello for Business / FIDO2 gibi parola-dışı kimlik doğrulama yöntemlerine geçiş, DPAPI zincirinin "kullanıcı parolasına bağlı" zayıf halkasını kısmen azaltır (ama DPAPI'nin kendisi hala farklı anahtar türetme yollarıyla çalışmaya devam eder; detaylar kimlik doğrulama yöntemine göre değişir).
- Master key dosyalarına erişimin denetlenmesi (auditing) ve bu dizinlere anormal erişen süreçlerin izlenmesi.

## Yaygın Hatalar (Savunma Tarafında)

1. **"AV/EDR var, LSASS korunuyor" varsayımı**: Çoğu EDR yalnızca bilinen imzaları (örneğin belirli bir aracın dosya hash'i) yakalar; MiniDump API'sinin kendisi legitim olduğu için, davranışsal/erişim-tabanlı tespit kurulmadan yalnızca imza tabanlı savunma yetersiz kalır.
2. **PPL'i "yeterli" sanmak**: PPL, kullanıcı-modu saldırılarına karşı etkilidir ama çekirdek seviyesini (BYOVD) ele geçirmiş bir saldırgana karşı tek başına yetersizdir; HVCI/WDAC olmadan PPL yarım bir önlemdir.
3. **Credential Guard'ı açıp unutmak**: Durumun periyodik doğrulanmadığı ortamlarda, bir grup politikası hatası veya kasıtlı devre dışı bırakma fark edilmeden aylarca sürebilir.
4. **DPAPI domain yedek anahtarını göz ardı etmek**: Kurumlar genelde LSASS/Golden Ticket riskine odaklanıp, aynı derecede kritik olan DPAPI domain backup key'ini Tier-0 varlığı olarak sınıflandırmayı atlar.
5. **WDigest'in kapalı olduğunu varsaymak**: Varsayılan kapalı olsa da, eski sistem görüntüleri veya yanlış yapılandırılmış GPO'lar nedeniyle bazı ortamlarda hala açık kalabilir; periyodik denetim gerekir.
6. **Yalnızca `OpenProcess` olaylarını izlemek**: Handle duplication ve direct syscall teknikleri, sadece `OpenProcess` çağrısına bakan basit kuralları atlatır; çok katmanlı (ETW-TI + kernel callback + davranışsal) tespit şarttır.

## Sonuç: Savunma Katmanlarının Birlikte Çalışması

Tek bir kontrol yeterli değildir; etkili bir savunma modeli şu katmanların **bir arada** çalışmasını gerektirir: **PPL/LSA Protection** (kullanıcı-modu erişimi kısıtlar) + **HVCI/WDAC** (çekirdek seviyesini korur, BYOVD'yi engeller) + **Credential Guard** (sırları VTL0'ın tamamen dışına taşır) + **DPAPI domain yedek anahtarının Tier-0 olarak korunması** + **davranışsal/ETW-TI tabanlı tespit** (bilinmeyen/yeni araçlara karşı). Bu katmanların herhangi biri eksik olduğunda, saldırgan diğer katmanları atlayarak hedefe ulaşabilir — bu yüzden Credential Access savunması, tek bir ürün/ayarın değil, **mimari bir bütünün** sonucudur.
