# Windows/Linux Kernel İç Mimarisi: Process/Object Modeli, SRM, PatchGuard ve Kimlik Deposu İç Yapısı

## Giriş ve Neden Önemli

Saldırı tekniklerini ezberlemek başka, onların *neden* çalıştığını anlamak başkadır. Bir credential dump aracının LSASS belleğinden neyi neden çekebildiğini, bir token manipulation saldırısının neden işe yaradığını, bir rootkit'in kendini kernel'de nasıl gizleyebildiğini gerçekten kavramak için işletim sisteminin çekirdek (kernel) mimarisini bilmek gerekir. Bu makale hem savunma hem tespit perspektifiyle Windows ve Linux çekirdeklerinin güvenlikle ilgili iç yapılarını açıklar. Amaç mekanizmayı anlamak ve buradan **tespit** ile **savunma** kurmaktır; canlı saldırı reçetesi değil.

Modern işletim sistemleri iki ayrıcalık düzleminde çalışır: **user mode** (Ring 3) ve **kernel mode** (Ring 0). User mode'daki bir process, donanıma ve çekirdek yapılarına doğrudan dokunamaz; her hassas işlem için sistem çağrısı (system call) aracılığıyla çekirdekten hizmet ister. Güvenlik sınırının büyük kısmı bu geçiş noktasında ve çekirdeğin veri yapılarında yaşar. Saldırganın nihai hedefi çoğu zaman bu sınırı aşmak veya çekirdek içindeki güven kararlarını çarpıtmaktır.

---

## Windows Object Manager ve Process/Thread Modeli

### Tanım ve Çalışma Mantığı

Windows çekirdeğinin merkezinde **Object Manager** bulunur. Windows'ta neredeyse her kaynak; process, thread, file, event, mutex, registry key, token, section (paylaşımlı bellek) çekirdek tarafından bir **object** olarak temsil edilir. Object Manager bu nesneleri isimlendiren, referans sayan (reference counting), yaşam döngüsünü yöneten ve erişimi denetleyen bileşendir. Nesneler `\Device`, `\BaseNamedObjects`, `\GLOBAL??` gibi bir hiyerarşik namespace altında yaşar; bu yapı `WinObj` benzeri araçlarla gezilebilir.

Her nesnenin başında bir **object header** vardır ve burada nesneye ait **security descriptor** işaretçisi tutulur. Security descriptor, o nesneye kimin hangi haklarla erişebileceğini tanımlayan DACL (Discretionary Access Control List) ile sahiplik/denetim bilgisini (owner SID, SACL) içerir. Bir handle açıldığında Object Manager, çağıran process'in token'ı ile nesnenin DACL'ini karşılaştırıp erişime izin verir ya da reddeder. Bu, Windows erişim denetiminin temel çalışma mantığıdır.

### EPROCESS ve ETHREAD

Her çalışan process, çekirdekte bir **EPROCESS** yapısıyla temsil edilir. EPROCESS; process'in benzersiz kimliği (PID), üst process bilgisi, adres alanı (virtual address space) tanımı, açık handle'ları tutan **handle table**, ve o process'in güvenlik bağlamını taşıyan **token** işaretçisini içerir. Process'lerin EPROCESS yapıları çekirdekte çift yönlü bağlı bir listede (`ActiveProcessLinks`) zincirlenir. 

Bu liste yapısı, klasik bir gizlenme tekniğinin de zeminidir: **DKOM (Direct Kernel Object Manipulation)**. Bir kernel-mode rootkit, bir process'in EPROCESS düğümünü bu bağlı listeden çıkararak (unlinking) onu process listeleyen API'lerden görünmez kılabilir; oysa process çalışmaya devam eder çünkü thread'ler ayrı bir mekanizmayla (scheduler) zamanlanır. Buradan çıkan savunma dersi önemlidir: process varlığını yalnızca tek bir listeye bakarak doğrulamak güvenilmezdir.

Her thread bir **ETHREAD** yapısıyla temsil edilir; bu da bir **KTHREAD** çekirdek çekirdeğini içerir. Thread, zamanlamanın gerçek birimidir. Bir thread bir process'e ait olsa da, thread'in üzerinde geçici olarak farklı bir güvenlik bağlamı taşıyan bir **impersonation token** bulunabilir. Bu ayrım, token manipulation saldırılarının teknik temelidir.

---

## Security Reference Monitor (SRM) ve Token Modeli

### Tanım

**Security Reference Monitor (SRM)** çekirdekte yaşayan ve tüm erişim denetimi kararlarının nihai merciidir. "Bu process bu nesneye bu hakla erişebilir mi?" sorusunun cevabını SRM, nesnenin security descriptor'ı ile çağıranın token'ını karşılaştırarak verir. User mode tarafındaki karşılığı **LSASS** (Local Security Authority Subsystem Service) process'i içinde çalışan LSA'dır; kimlik doğrulama LSA'da yapılır, ama erişim denetimi kararı çekirdekteki SRM'de verilir.

### Access Token'ın İç Yapısı

Bir **access token**, bir process veya thread'in güvenlik kimliğini paketleyen çekirdek nesnesidir. İçinde şunlar bulunur:

- **User SID**: kullanıcıyı benzersiz tanımlayan Security Identifier.
- **Group SID'ler**: kullanıcının üyesi olduğu grupların SID listesi.
- **Privileges**: `SeDebugPrivilege`, `SeImpersonatePrivilege`, `SeBackupPrivilege` gibi sistem çapında yetkiler ve bunların etkin (enabled) olup olmadığı.
- **Integrity level**: Low / Medium / High / System bütünlük etiketi (Mandatory Integrity Control).

Erişim kararı verilirken SRM, token'daki SID'ler ve privilege'lar ile nesnenin DACL'indeki ACE (Access Control Entry) girişlerini karşılaştırır. Bu modeli anlamak, birçok yükseltme (privilege escalation) tekniğinin *neden* mümkün olduğunu açıklar:

- **Token theft / impersonation**: `SeImpersonatePrivilege` yetkisine sahip bir bağlam, başka bir yüksek yetkili token'ı taklit ederek onun bağlamında iş yaptırabilir. Bu yüzden servis hesaplarına bu yetkinin dağıtılması dikkatle yönetilmelidir.
- **SeDebugPrivilege**: Bu yetki, başka process'lerin bellek alanına tam erişim verir; LSASS gibi hassas process'lere okuma yolunu açan asıl anahtar budur.

### Tespit ve Savunma

- Token bütünlük düzeylerini ve `SeDebugPrivilege`/`SeImpersonatePrivilege` atamalarını en az yetki (least privilege) ilkesiyle sınırlayın.
- LSASS'a yönelik `PROCESS_VM_READ` ve `PROCESS_QUERY_INFORMATION` gibi erişim maskeleriyle açılan handle olaylarını izleyin; Sysmon Event ID 10 (ProcessAccess) bu telemetriyi verir.
- Beklenmedik parent-child process ilişkileri (örneğin `services.exe` dışı bir process'in yüksek yetkili token taşıması) davranışsal bir alarm sinyalidir.

---

## LSASS, SAM ve SYSTEM: Kimlik Deposu İç Yapısı

### LSASS Neyi Tutar

**LSASS**, kimlik doğrulamanın kalbidir. Kullanıcı oturum açtığında LSA, kimlik bilgilerini doğrular ve oturum boyunca çeşitli kimlik materyallerini bellekte tutabilir: NTLM hash'leri, Kerberos bilet ve anahtarları (TGT, session key'ler), bazı yapılandırmalarda düz metin sırlar. Bu materyaller LSASS process'inin sanal belleğinde yaşar. `SeDebugPrivilege` sahibi bir yönetici bağlamı LSASS'ın bellek görüntüsünü (memory dump) alabilir ve içindeki credential yapılarını çözümleyebilir; **credential dumping** dediğimiz tekniğin özü budur. Saldırı sihir değildir; sadece çekirdeğin process belleğine okuma erişimi sağladığı meşru mekanizmanın kötüye kullanılmasıdır.

### SAM ve SYSTEM Registry Hive'ları

Yerel kullanıcı hesapları ve parola doğrulayıcıları (NTLM hash) diskte **SAM** (Security Account Manager) registry hive'ında saklanır. SAM'daki hash'ler, **SYSTEM** hive'ında saklanan bir sistem anahtarı (bootkey / SysKey) ile ek olarak şifrelenir. Yani SAM'ı çözümlemek için hem SAM hem SYSTEM hive'ına ihtiyaç vardır; ikisi birlikte offline hash çıkarımını mümkün kılar. Aynı şekilde **SECURITY** hive'ı, servis hesabı parolaları ve makine sırları gibi LSA secrets'ları barındırır.

Bu hive dosyaları çalışan bir sistemde çekirdek tarafından kilitli tutulur. Saldırganların bunları elde etmek için Volume Shadow Copy veya `reg save` benzeri meşru mekanizmaları kötüye kullanması, savunmada izlenmesi gereken davranışsal göstergelerdir.

### Savunma ve Tespit

- **Credential Guard**: LSA'nın sırlarını, VBS (Virtualization-Based Security) ile izole edilmiş bir "isolated LSA" bağlamına taşır. Böylece normal yönetici bağlamı bile bu sırlara doğrudan erişemez; sanallaştırma katmanı bir güven sınırı ekler.
- **Protected Process Light (PPL)**: LSASS'ı korumalı process olarak işaretlemek, ona handle açmayı sınırlar. Bu tek başına yeterli değildir ama saldırı yüzeyini daraltır.
- **Telemetri**: SAM/SYSTEM hive'larına erişim, `reg save` kullanımı, Shadow Copy oluşturma olayları ve LSASS'a okuma amaçlı handle açılışları izlenmeli; bunlar yüksek değerli tespit kuralları için doğal noktalardır.

---

## PatchGuard (Kernel Patch Protection)

### Tanım ve Kök Neden

64-bit Windows'ta **PatchGuard** (resmi adıyla Kernel Patch Protection), çekirdeğin kritik yapılarının izinsiz değiştirilmesini caydırmak için tasarlanmış bir bütünlük denetimi mekanizmasıdır. Tarihsel olarak rootkit'ler; system call tablosu (SSDT), Interrupt Descriptor Table (IDT), belirli çekirdek fonksiyonları ve MSR (Model Specific Register) gibi yapıları yamalayarak (hooking) kendilerini gizler ya da davranışı değiştirirdi. PatchGuard, bu kritik yapıların bütünlüğünü periyodik ve öngörülemez zamanlarda kontrol eder; bir sapma bulursa sistemi kasıtlı olarak `CRITICAL_STRUCTURE_CORRUPTION` (bug check kodu genelde 0x109) ile durdurur (BSOD).

### Çalışma Mantığı ve Sınırları

PatchGuard bir **caydırıcıdır**, mutlak bir güvenlik sınırı değil. Kendini gizlemeye, doğrulama zamanlamasını rastgeleleştirmeye ve şifrelenmiş bağlam kullanmaya dayanır. Kararlı bir bütünlük güvencesi değildir; çünkü aynı ayrıcalık düzleminde (Ring 0) çalışan yeterince güçlü bir aktör onunla yarışabilir. Gerçek çekirdek bütünlüğü, kod imzalama (Driver Signature Enforcement), HVCI (Hypervisor-Enforced Code Integrity) ve Secure Boot gibi katmanlarla, yani ayrıcalık düzlemini gerçekten ayıran donanım destekli sanallaştırmayla sağlanır.

### Savunma Perspektifi

- **HVCI/VBS**: Çekirdek kod bütünlüğünü hypervisor düzeyinde zorlar; imzasız veya değiştirilmiş kernel kodunun çalışmasını engeller. PatchGuard'ın tespit ettiği türden manipülasyonları önlemede daha güçlü bir katmandır.
- **DSE (Driver Signature Enforcement)**: Yalnızca imzalı sürücülerin yüklenmesine izin verir. "Bring Your Own Vulnerable Driver" (BYOVD) saldırıları tam da bu katmanı, imzalı ama açıklı bir sürücüyü kötüye kullanarak aşmaya çalışır; bu yüzden bilinen açıklı sürücülerin engellenmesi (blocklist) önemli bir savunmadır.
- Beklenmedik `CRITICAL_STRUCTURE_CORRUPTION` bug check'leri, çekirdek manipülasyonu denemesinin bir işareti olabilir ve incelenmelidir.

---

## Linux Kernel İç Mimarisi: task_struct, Credential ve İzolasyon

### Process Modeli: task_struct

Windows'taki EPROCESS'in Linux karşılığı **task_struct** yapısıdır. Linux'ta ilginç bir tasarım tercihi vardır: çekirdek process ile thread'i büyük ölçüde aynı şekilde ("task") temsil eder; thread'ler yalnızca belirli kaynakları (adres alanı, dosya tanımlayıcıları) paylaşan task'lardır. `fork()` yeni bir adres alanıyla kopya oluştururken, thread yaratımı aynı adres alanını paylaşan bir task üretir. task_struct; PID/TGID bilgisini, ebeveyn/çocuk ilişkilerini, bellek tanımını (`mm_struct`), açık dosya tablosunu ve güvenlik bağlamını bir arada tutar.

### Credential Yapısı (struct cred)

Linux'ta bir task'ın güvenlik kimliği **struct cred** içinde yaşar. Burada gerçek ve etkin kullanıcı/grup kimlikleri bulunur: **UID/GID**, **EUID/EGID** (etkin kimlik, erişim kararlarında kullanılan), ve **saved UID** gibi alanlar. Ayrıca modern Linux'ta ayrıcalıklar kaba `root`/`non-root` ikilisinden **capabilities** modeline bölünmüştür: `CAP_SYS_ADMIN`, `CAP_NET_ADMIN`, `CAP_SETUID`, `CAP_DAC_OVERRIDE` gibi ince taneli yetkiler. 

Bu yapıyı anlamak, Linux privilege escalation'ın özünü açıklar: pek çok yerel yükseltme saldırısının nihai hedefi, çekirdek belleğindeki cred yapısını manipüle ederek çağıran task'ın UID/EUID alanını 0 (root) yapmaktır. Klasik anlatımıyla "`commit_creds(prepare_kernel_cred(0))`" çağrısını tetiklemek, bir kernel açığının sömürülmesinde sık görülen son adımdır: kernel bağlamında yeni bir root cred oluşturup mevcut task'a atamak. Yani saldırganın esas kazandığı şey bir shell değil, cred yapısının içeriğidir.

### LSM: SELinux ve AppArmor

**LSM (Linux Security Modules)** çerçevesi, çekirdeğin kritik erişim noktalarına zorunlu erişim denetimi (Mandatory Access Control) kancaları yerleştirir. **SELinux** ve **AppArmor** bu çerçeve üzerine kuruludur. Standart UNIX izinleri (DAC) bir process root olduğunda çoğunlukla devre dışı kalırken, MAC katmanı root'un bile ne yapabileceğini politika ile sınırlar. Bir web sunucusu process'inin yalnızca belirli dizinlere erişebilmesi, cred'i ele geçirilse bile hasarı sınırlayan bir savunma derinliği katmanıdır.

### Namespace ve cgroup: İzolasyonun İç İşleyişi

Konteynerlerin (container) temeli iki çekirdek mekanizmasıdır:

- **Namespaces**: Bir task'ın gördüğü kaynak dünyasını izole eder. PID namespace ayrı bir process ağacı, mount namespace ayrı bir dosya sistemi görünümü, network namespace ayrı bir ağ yığını, user namespace ayrı bir UID eşlemesi sağlar. Bir konteynerdeki "root" (UID 0), user namespace sayesinde ana sistemde yetkisiz bir kullanıcıya eşlenebilir; bu, konteyner kaçışlarının (container escape) neden bu kadar kritik olduğunu ve neden user namespace eşlemesinin doğru yapılandırılması gerektiğini açıklar.
- **cgroups (control groups)**: Kaynak *sınırlaması* ve muhasebesiyle ilgilenir; CPU, bellek, I/O kotalarını uygular. cgroup bir güvenlik izolasyonu değil, kaynak yönetimi mekanizmasıdır, ama denial-of-service savunmasında rol oynar.

Konteyner güvenliğinin temel dersi şudur: konteyner bir sanal makine değildir; aynı çekirdeği paylaşır. Bir kernel açığı, konteyner izolasyonunu doğrudan bypass edebilir. Bu yüzden çekirdek yamalaması, seccomp ile system call kısıtlaması ve capability düşürme (drop) konteyner güvenliğinin ayrılmaz parçalarıdır.

### Tespit ve Savunma

- **auditd** ile hassas system call'lar (`execve`, `setuid`, capability değişimleri) ve dosya erişimleri izlenebilir.
- **eBPF** tabanlı araçlar (örneğin Falco, Tetragon türü çözümler), çekirdek olaylarını düşük maliyetle gözlemleyip cred değişimi, beklenmedik namespace geçişi veya şüpheli process davranışı için gerçek zamanlı tespit sağlar.
- Konteynerlerde: gereksiz capability'leri düşürün, seccomp profilleri uygulayın, user namespace kullanın ve konteynerleri privileged modda çalıştırmaktan kaçının.

---

## İki Dünyanın Karşılaştırması

| Kavram | Windows | Linux |
|---|---|---|
| Process yapısı | EPROCESS | task_struct |
| Thread yapısı | ETHREAD/KTHREAD | task_struct (paylaşımlı) |
| Güvenlik bağlamı | Access Token (SID + privileges) | struct cred (UID/GID + capabilities) |
| Erişim denetimi merci | Security Reference Monitor | LSM kancaları + DAC |
| Zorunlu erişim denetimi | Mandatory Integrity Control | SELinux / AppArmor |
| Kimlik deposu | LSASS + SAM/SECURITY hive | /etc/shadow, PAM, keyring |
| Kernel bütünlüğü | PatchGuard, HVCI, DSE | Lockdown mode, module signing, IMA |

Her iki dünyada da ortak ilke aynıdır: güvenlik kararı, çekirdekteki bir veri yapısının (token ya da cred) içeriğine dayanır. Saldırgan bu yapının içeriğini çarpıtabilirse, üstündeki tüm denetim mantığı yanlış sonuç verir. Savunma da bu yüzden tek katmana değil, veri bütünlüğü, ayrıcalık ayrımı ve davranışsal telemetriyi birleştiren derinlemesine bir yaklaşıma dayanmalıdır.

---

## Yaygın Hatalar ve Yanlış Anlamalar

- **"Rootkit process'i listeden silerse tamamen görünmez olur."** Yanlış. DKOM ile bir liste manipüle edilse bile thread zamanlaması, bellek artıkları, handle sayaçları ve çapraz kaynak (cross-view) analizleri tutarsızlık gösterir. İyi tespit, tek bir kaynağa güvenmez; birden fazla görünümü karşılaştırır.
- **"PatchGuard çekirdeği hack'lenemez yapar."** Yanlış. PatchGuard bir caydırıcıdır, garanti değildir. Gerçek bütünlük güvencesi HVCI/VBS gibi donanım destekli izolasyondan gelir.
- **"LSASS'ı korumak için PPL yeterli."** Eksik. PPL ve Credential Guard birbirini tamamlar; PPL handle erişimini zorlaştırır, Credential Guard sırları VBS ile izole eder. İkisi birlikte anlamlıdır.
- **"Konteyner sanal makine gibi izole eder."** Yanlış. Konteynerler ana çekirdeği paylaşır; bir kernel açığı izolasyonu kırabilir. VM düzeyi izolasyon isteniyorsa ayrı bir çekirdek (mikro-VM yaklaşımları) gerekir.
- **"root olan her şeyi yapar, MAC anlamsız."** Yanlış. SELinux/AppArmor gibi MAC katmanları, root bağlamını bile politika ile sınırlar ve ele geçirme sonrası hasarı azaltır.
- **"Credential dumping sıfırıncı gün bir sihirdir."** Yanlış. Çoğu credential dumping, çekirdeğin sağladığı meşru bellek okuma ve registry erişim mekanizmalarının, yeterli ayrıcalıkla (özellikle `SeDebugPrivilege`) kötüye kullanılmasıdır. Bu yüzden ayrıcalık yönetimi ve telemetri en etkili savunmadır.

## Özet

İşletim sistemi güvenliğinin çoğu, çekirdekteki birkaç kritik veri yapısında (Windows'ta token ve EPROCESS, Linux'ta cred ve task_struct) ve bu yapıları yorumlayan tek merkezlerde (SRM, LSM) düğümlenir. Kimlik materyalleri LSASS ve SAM/SYSTEM (Windows) ya da shadow ve keyring (Linux) gibi belirli depolarda yaşar. PatchGuard, HVCI, Credential Guard ve LSM/SELinux gibi mekanizmalar bu yapıların bütünlüğünü ve erişimini korumaya çalışır. Bu iç mimariyi anlayan bir savunmacı, saldırının hangi veri yapısını hedeflediğini görebilir ve tespiti tam olması gereken noktaya, yani ayrıcalık kullanımına, hassas process erişimine ve çekirdek bütünlük olaylarına yerleştirebilir.
