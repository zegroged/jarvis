# Sandbox/Isolation Kaçışı: AppContainer, Job Objects, seccomp/namespace Escape (Windows Odaklı)

## Tanım ve Kapsam

**Sandbox** (kum havuzu) ve **isolation** (izolasyon), güvenilmeyen kodun sistemin geri kalanına erişimini kısıtlamak için kurulan bir hapishane duvarıdır. Amaç, bir kod parçası ele geçirilse veya kötü niyetli olsa bile, hasarın o sınırlı alanda kalmasını sağlamaktır. **Sandbox escape**, bu duvarı aşarak izin verilenden daha yüksek ayrıcalık düzeyine veya daha geniş kaynak erişimine ulaşmaktır.

Konteyner (Docker) kaçışı ayrı bir konu olarak ele alınmıştı. Bu makale, konteyner soyutlamasının altında yatan ve konteynerlerden bağımsız olarak da kullanılan **işletim sistemi seviyesindeki izolasyon primitiflerine** odaklanır:

- **Windows tarafı:** AppContainer (ve Low Integrity), Job Objects, Windows Sandbox, Restricted Tokens.
- **Linux tarafı:** namespaces, seccomp-bpf, capabilities — Docker olmadan, doğrudan uygulama içi sandbox olarak kullanıldığında.

Ortak fikir şudur: İzolasyon, güvenlik sınırı olarak *tasarlanan* bir mekanizma ile yalnızca *hafifletme* (mitigation) olarak sunulan bir mekanizma arasındaki farkı bilmeyi gerektirir. Kaçışların büyük çoğunluğu bu ayrımın karıştırılmasından doğar.

## Kök Neden ve Çalışma Mantığı

### Güvenlik sınırı mı, hafifletme mi?

Microsoft'un kamuya açık güvenlik hizmet sınırları (servicing criteria) tanımı, hangi izolasyonun "gerçek" güvenlik sınırı sayıldığını belirler. Kritik ayrım:

- **AppContainer**, Microsoft tarafından bir **güvenlik sınırı** olarak kabul edilir. Kaçış, servislenebilir (patch'lenebilir) bir zafiyettir.
- **Low/Medium Integrity Level** tek başına *tam* bir sınır değildir; UAC ve integrity mekanizmaları uygulamaya bağlı olarak sınır sayılmayabilir.
- **Job Objects**, kaynak yönetimi ve süreç gruplama için tasarlanmıştır; **güvenlik sınırı değildir**. Bir process'i "hapsetmek" için tek başına Job Object'e güvenmek yanlıştır.

Bu ayrımı bilmemek en yaygın hatadır: Bir mekanizmayı, tasarlandığından daha güçlü bir güvenlik garantisi sunuyormuş gibi kullanmak.

### AppContainer'ın çalışma mantığı

AppContainer, Windows 8 ile gelen ve UWP uygulamaları ile modern tarayıcı sandbox'larının (örneğin bazı tarayıcı render process'leri) temelini oluşturan bir izolasyon modelidir. Mekanizması şu bileşenlere dayanır:

- **AppContainer SID:** Her AppContainer'a özgü bir güvenlik kimliğidir. Erişim kontrolü bu SID üzerinden yapılır.
- **Capability SID'leri:** Kaba taneli değil, *yetenek tabanlı* erişim. Bir AppContainer yalnızca kendisine açıkça verilen capability'lere (örneğin ağ istemcisi, özel klasör erişimi) sahiptir. Varsayılan olarak dosya sistemine, registry'ye ve diğer kaynaklara erişimi reddedilir.
- **Lowbox token:** AppContainer içindeki process, "lowbox" adı verilen kısıtlı bir token ile çalışır. Bu token, Low Integrity'den daha katı bir modeldir; kaynak erişimi için hem klasik DACL kontrolü hem de AppContainer SID/capability eşleşmesi gerekir.

Kaçış tipik olarak şu yollarla olur:
1. **Broker process istismarı:** Sandbox'lı process, dosya açma gibi ayrıcalıklı işlemleri kendisi yapamaz; bunları daha yüksek ayrıcalıklı bir **broker** process'e IPC ile devreder. Broker'daki bir mantık hatası (yetersiz path doğrulaması, yanlış canonicalization, yetki karıştırması) sandbox'ın izin vermediği bir kaynağa erişim sağlayabilir. Tarayıcı sandbox kaçışlarının çoğu bu kategoriye girer.
2. **Kernel saldırı yüzeyi:** AppContainer, kernel'e giden syscall yüzeyini tamamen kapatmaz. Bir kernel driver veya syscall'daki zafiyet, sandbox'ı atlayarak SYSTEM'e yükselmeye izin verebilir (klasik LPE zinciri). Sandbox kaçışı ve kernel LPE genellikle zincirlenir.
3. **Yanlış yapılandırılmış capability veya paylaşılan nesne:** AppContainer'a fazladan capability verilmişse ya da named object (named pipe, section, mutex) izinleri yanlış ACL'lenmişse, sandbox içindeki kod dışarıyla köprü kurabilir.

### Job Objects ve neden sınır olmadığı

Job Object, process'leri gruplayıp CPU/bellek kotası, priority ve `KILL_ON_JOB_CLOSE` gibi kaynak politikaları uygulamak için kullanılır. `UILimits` ile bazı UI kısıtlamaları (clipboard, global atom erişimi) da eklenebilir.

Ancak Job Object:
- Bir process'in başka bir process'e handle açmasını, disk/registry'ye erişimini kendi başına **güvenli biçimde** engellemez.
- Nested job desteği olsa da, yapılandırma hataları ve process'in job'dan çıkabildiği (breakaway) senaryolar mevcuttur.

Bir process `CreateProcess` sırasında `CREATE_BREAKAWAY_FROM_JOB` bayrağını kullanabiliyorsa ve job `JOB_OBJECT_LIMIT_BREAKAWAY_OK` (ya da silent breakaway) izniyle yapılandırılmışsa, yeni process job'dan kopar. Kaynak kotasına ve `KILL_ON_JOB_CLOSE` temizliğine güvenen bir sandbox bu noktada delinir. Bu yüzden ciddi sandbox mimarileri (örneğin Chromium) Job Object'i *tek başına* değil, restricted token + Low/AppContainer integrity + alternate desktop ile **katmanlı** kullanır.

### Windows Sandbox

Windows Sandbox, hafif bir sanallaştırma (Hyper-V tabanlı, hostla çekirdek görüntüsünü paylaşan container teknolojisi) üzerine kurulu, tek kullanımlık masaüstü ortamıdır. İzolasyonu process seviyesinden ziyade **VM/hypervisor sınırına** dayanır ki bu daha güçlü bir sınırdır. Buradaki kaçış senaryoları:
- **Hypervisor/VM escape:** Hyper-V veya paylaşılan bileşenlerdeki zafiyetler (guest-to-host). Bunlar nadir ama en kritik kaçışlardır.
- **Yanlış yapılandırma:** Sandbox config dosyasında (`.wsb`) `MappedFolders` ile host klasörünü yazılabilir paylaşmak, vGPU'yu açmak veya ağ erişimini bırakmak, saldırı yüzeyini host'a köprüler. Buradaki "kaçış" çoğu zaman zafiyet değil, kullanıcının izolasyonu kendi eliyle zayıflatmasıdır.

### Linux: seccomp / namespace / capabilities (konteyner dışı)

Bu primitifler Docker'a özgü değildir; herhangi bir uygulama kendi sandbox'ını doğrudan kurmak için kullanabilir (tarayıcılar, systemd servisleri, `nsjail`, `bubblewrap` gibi araçlar).

- **namespaces:** PID, mount, network, user, UTS, IPC, cgroup ad alanlarını izole eder. En kritiği **user namespace**'tir: İzinsiz kullanıcının kendi namespace'inde root (uid 0) olabilmesi, tarihsel olarak birçok LPE'ye zemin hazırlamıştır. `unprivileged_userns_clone` gibi sertleştirme anahtarları bu yüzden vardır.
- **seccomp-bpf:** Syscall'ları bir BPF filtresiyle beyaz/kara listeye alır. Zayıf tasarlanmış bir filtre kaçışın anahtarıdır:
  - `ptrace`, `process_vm_writev`, `clone`/`unshare`, `kexec`, `bpf`, `keyctl` gibi tehlikeli syscall'lara izin bırakmak.
  - **Argüman denetleme yanılgısı:** seccomp, syscall argümanlarının *pointer'la işaret ettiği belleği* güvenli biçimde inceleyemez (TOCTOU/dereference edilemez). Bu yüzden argüman değerine göre filtrelemek kırılgandır.
  - **Multiplexing syscall'lar:** `socketcall`, `ioctl` gibi tek numaranın altında birçok işlem barındıran syscall'ları yeterince incelememek.
- **capabilities:** `CAP_SYS_ADMIN` neredeyse "yeni root"tur; bırakılırsa çoğu izolasyon anlamsızlaşır. `CAP_SYS_PTRACE`, `CAP_DAC_READ_SEARCH`, `CAP_SYS_MODULE` gibi yetenekler de kaçış vektörüdür.

Ortak Linux kaçış deseni: Yetersiz kısıtlanmış primitiflerin bir kernel zafiyetiyle birleşmesi. Sandbox syscall yüzeyini daraltmak, tam da bu kernel saldırı yüzeyini küçültmek içindir.

## Örnek: Katmanlı Bir Sandbox'ın Delinmesi (Kavramsal)

Bir tarayıcı render process'ini düşünelim. Tasarım katmanları:

1. Render process, AppContainer + lowbox token ile çalışır; dosya sistemine doğrudan erişemez.
2. Kaynak istekleri named pipe üzerinden broker process'e gider.
3. Job Object ile process grubu ve kaynak kotası uygulanır.

Kavramsal kaçış zinciri:
- Saldırgan önce render process içinde bir bellek bozulması (memory corruption) zafiyetiyle kod çalıştırma elde eder. Bu noktada hâlâ sandbox içindedir; dosya okuyamaz, yeni yüksek ayrıcalıklı process başlatamaz.
- Ardından **broker'daki bir path doğrulama hatasını** istismar eder: Broker, `\\?\` ön eki veya symbolic link/junction ile canonicalize edilmemiş bir yolu kabul eder ve sandbox'ın erişmemesi gereken bir dosyayı render process adına açar. Sandbox sınırı burada delinir.
- Alternatif olarak, sandbox içinden ulaşılabilen bir **kernel driver IOCTL zafiyeti** ile doğrudan SYSTEM'e yükselerek tüm izolasyon katmanları atlanır.

Buradaki ders: Katmanlı savunmada en zayıf halka broker mantığı ve kernel saldırı yüzeyidir; token/integrity kısıtlaması bunları tek başına kapatmaz.

## Tespit

Sandbox kaçışını tespit etmek, "izolasyon sınırının beklenmedik biçimde aşıldığı" davranışı yakalamaktır.

**Windows tarafı:**
- **Beklenmeyen child process:** AppContainer/Low Integrity bir process'in (örneğin bir tarayıcı render alt process'inin) `cmd.exe`, `powershell.exe`, `rundll32.exe` gibi bir çocuğu doğurması güçlü bir sinyaldir. Sysmon Event ID 1 (process create) + parent-child integrity düzeyi ilişkisiyle kural yazın.
- **Integrity level yükselmesi:** Bir token'ın integrity düzeyinin ya da AppContainer bağlamının beklenmedik değişimi. Process token bilgisini (WPP/ETW, Sysmon) izleyin.
- **Named pipe ve section anomalileri:** Sandbox'lı process'in bilinen broker pipe'ları dışında pipe oluşturması/bağlanması (Sysmon Event ID 17/18).
- **Job breakaway:** `CREATE_BREAKAWAY_FROM_JOB` kullanımına dair ETW telemetrisi ve job'dan kopan process'ler.
- **Kernel LPE göstergeleri:** Şüpheli driver yüklemeleri (Sysmon Event ID 6), bilinen zafiyetli driver'lar (BYOVD), anormal `\Device\` handle erişimleri.
- **Windows Sandbox:** `.wsb` config'lerinde `MappedFolders` (özellikle `ReadOnly=false`) ve host'a yazan paylaşımların denetimi.

**Linux tarafı:**
- **seccomp reddi:** Kernel, filtre ihlallerini `SIGSYS`/audit ile loglayabilir. `auditd` üzerinden `SECCOMP` kayıtlarını toplayın; bir process'in filtrenin dışına çıkmaya çalışması net bir istismar sinyalidir.
- **user namespace oluşturma:** `unshare`/`clone` ile `CLONE_NEWUSER` çağrıları; özellikle beklenmeyen servislerden gelenler. eBPF/audit ile izlenebilir.
- **capability kullanımı:** `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE` gerektiren işlemlerin sandbox'lı bağlamdan gelmesi.
- **Anormal syscall profili:** eBPF tabanlı runtime güvenlik araçları (Falco, Tetragon vb.) ile process'in beklenen syscall setinin dışına çıkması.

Genel prensip: Sandbox'ın *tanımladığı* beklenen davranış profilini bir "allow-list" gibi ele alıp, sapmaları alarm üretin. İzolasyon zaten davranışı daralttığı için, sapma yüksek sinyalli olur.

## Savunma

1. **Doğru sınırı seç.** Gerçek güvenlik gerektiren yerde güvenlik *sınırı* olan mekanizmayı kullanın: AppContainer veya hypervisor izolasyonu (Windows Sandbox / Hyper-V). Job Object'i güvenlik sınırı olarak kullanmayın; onu yalnızca kaynak yönetimi için, restricted token ve integrity ile birlikte katmanlayın.

2. **En az yetki (least privilege).**
   - Windows: AppContainer'a yalnızca zorunlu capability'leri verin. Named object'lere sıkı ACL uygulayın (herkese erişilebilir named pipe/section bırakmayın).
   - Linux: `CAP_SYS_ADMIN` başta olmak üzere gereksiz tüm capability'leri düşürün. `no_new_privs` bayrağını set edin (privilege yükselmeyi kalıcı olarak kapatır ve seccomp'un güvenli çalışması için önkoşuldur).

3. **Broker'ı düşman gibi tasarla.** Sandbox içindeki tarafı güvenilmez kabul edin. Broker'da tüm path'leri kanonikleştirip doğrulayın (symlink/junction/`\\?\` tuzaklarına karşı), tüm IPC girdilerini şema doğrulamasından geçirin, TOCTOU'yu handle-temelli işlemlerle kapatın.

4. **seccomp filtresini kısıtlayıcı kur.** Beyaz liste (default-deny) yaklaşımı kullanın. `ptrace`, `bpf`, `keyctl`, `clone`(namespace bayraklarıyla), `unshare`, `kexec_load`, modül yükleme gibi syscall'ları filtreleyin. Argüman-temelli filtrelemeye tek savunma olarak güvenmeyin.

5. **Kernel saldırı yüzeyini küçült.** En güncel yamaları uygulayın (kaçışların çoğu kernel/broker zincirine dayanır). BYOVD'ye karşı zafiyetli driver blok listelerini (Microsoft vulnerable driver blocklist / HVCI) etkinleştirin. Linux'ta gereksiz kernel modüllerini ve `unprivileged_userns_clone`'u ortam gereksiniminize göre kısıtlayın.

6. **Katmanlı savunma (defense in depth).** Tek mekanizmaya güvenmeyin: token kısıtlaması + integrity + AppContainer + broker doğrulaması + kernel sertleştirme birlikte. Bir katman delinse diğerleri hasarı sınırlar.

7. **Windows Sandbox'ı sıkı yapılandır.** `.wsb` dosyalarında host klasörlerini yazılabilir map etmeyin; ağı ve vGPU'yu ihtiyaç yoksa kapatın.

## Yaygın Hatalar

- **Job Object'i güvenlik hapishanesi sanmak.** En sık ve en tehlikeli yanılgı. Job, kaynak yönetimi aracıdır; breakaway ve handle erişimi sınırlarını tam kapatmaz.
- **Low Integrity'yi AppContainer ile eşdeğer görmek.** Low Integrity daha zayıf ve daha kolay aşılabilir bir katmandır; tek başına modern bir güvenlik sınırı değildir.
- **Capability'leri cömertçe vermek.** Windows'ta gereksiz capability, Linux'ta özellikle `CAP_SYS_ADMIN` bırakmak, izolasyonu kâğıttan yapar.
- **seccomp'ta argüman filtresine tek güvenmek.** Pointer argümanları güvenli incelenemez; sağlam savunma syscall numarası temelli beyaz listedir.
- **`no_new_privs` set etmeyi unutmak.** Bu bayrak olmadan sandbox içinden setuid ikililerle ayrıcalık yükseltilebilir.
- **Broker'ı güvenilir kabul etmek.** Sandbox'ın asıl güvenlik sınırı çoğu zaman broker mantığıdır; orayı ihmal etmek tüm modeli çökertir.
- **user namespace'i düşünmeden açık bırakmak.** Unprivileged user namespace, birçok Linux LPE'nin başlangıç noktasıdır; ortama göre kısıtlanmalıdır.
- **Yalnızca izolasyona güvenip yamayı ertelemek.** Sandbox, güncel olmayan kernel/broker'ı korumaz; kaçışlar tam da bu boşluktan zincirlenir.

## Özet

Sandbox kaçışının özü, bir izolasyon mekanizmasının *sunduğunu sandığımız* garanti ile *gerçekten sunduğu* garanti arasındaki farktır. Windows'ta AppContainer bir güvenlik sınırıdır ve capability tabanlı en az yetkiyle güçlüdür; Job Objects ise güvenlik sınırı değildir ve yalnızca katmanlı kullanılmalıdır; Windows Sandbox hypervisor sınırıyla en güçlü izolasyonu verir ama yanlış yapılandırma bunu delebilir. Linux'ta seccomp, namespaces ve capabilities Docker'dan bağımsız güçlü primitiflerdir, ancak zayıf filtre, cömert capability veya açık user namespace kaçış kapısıdır. Her iki dünyada da savunma aynı ilkelere dayanır: doğru sınırı seçmek, en az yetki, broker'ı düşman kabul etmek, kernel yüzeyini küçültmek ve katmanlı derinlik. Tespitin anahtarı, izolasyonun daralttığı davranış profilinden sapmaları yüksek sinyal olarak yakalamaktır.
