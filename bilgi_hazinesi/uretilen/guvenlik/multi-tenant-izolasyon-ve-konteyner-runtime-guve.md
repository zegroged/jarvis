# Multi-Tenant İzolasyon ve Konteyner Runtime Güvenliği (gVisor / Kata / seccomp / AppArmor)

## Giriş ve Kapsam

Konteyner teknolojisi, uygulama dağıtımını hızlandırırken güvenlik açısından yanıltıcı bir zihinsel model yaratır: "Konteyner bir sanal makine gibidir, izole çalışır." Bu doğru değildir. Standart bir Linux konteyneri, ana makinedeki (host) **paylaşılan çekirdek (shared kernel)** üzerinde çalışan, yalnızca **namespace** ve **cgroup** mekanizmalarıyla ayrıştırılmış bir süreç kümesidir. Bu makale, özellikle birden fazla kiracının (multi-tenant) aynı fiziksel altyapıyı paylaştığı ortamlarda izolasyonun neden zayıf olduğunu, ve savunma tarafında runtime sandboxing (gVisor, Kata Containers), seccomp, AppArmor/SELinux ve capability kısıtlamasının bu zayıflığı nasıl kapattığını inceler.

Amaç saldırı talimatı vermek değil; izolasyon mekanizmasının çalışma mantığını anlamak ve buna karşılık gelen sertleştirme (hardening) ile tespit katmanlarını kurmaktır.

## Temel Problem: Paylaşılan Çekirdek ve Saldırı Yüzeyi

### Konteyner İzolasyonu Aslında Nedir?

Klasik konteyner izolasyonu üç yapı taşına dayanır:

- **Namespaces**: Bir sürecin gördüğü kaynak evrenini (PID, ağ, mount, UTS, IPC, user, cgroup) ayırır. Konteyner içindeki bir süreç kendi PID 1'ini görür, ama bu yalnızca bir "görünüm" ayrımıdır.
- **cgroups**: Kaynak sınırlaması (CPU, bellek, I/O) sağlar. Güvenlik değil, kaynak yönetimi mekanizmasıdır; ancak `denial-of-service` (kaynak tüketimi) saldırılarını sınırlamada rol oynar.
- **Capabilities**: Geleneksel `root` yetkisini parçalayan ayrıcalık bitleridir (`CAP_NET_ADMIN`, `CAP_SYS_ADMIN` vb.).

Kritik nokta şudur: Tüm bu mekanizmalar **aynı Linux çekirdeğinin** sunduğu soyutlamalardır. Konteyner içindeki uygulama `syscall` (sistem çağrısı) yaptığında, doğrudan host çekirdeğiyle konuşur. Sanal makinede araya bir hypervisor ve misafir çekirdek girerken, konteynerde bu arabulucu yoktur.

### Kök Neden: Çekirdek Ortak Bir Güven Sınırıdır

Multi-tenant ortamda tehlike buradan doğar. Eğer çekirdekte istismar edilebilir bir zafiyet varsa (örneğin bir syscall'ın hatalı bellek yönetimi, bir race condition, ya da `overlayfs`/`user namespace` sınırındaki bir mantık hatası), bir kiracının konteynerinden yapılan bir çağrı çekirdeği bozabilir. Çekirdek bozulduğunda, tüm namespace ayrımları anlamsızlaşır — çünkü namespace'i uygulayan da o çekirdektir. Sonuç: **konteyner kaçışı (container escape)** ve yatay olarak diğer kiracıların verilerine erişim.

Saldırı yüzeyinin büyüklüğü doğrudan çekirdeğe açık syscall sayısıyla orantılıdır. Modern Linux çekirdeği 300'den fazla syscall sunar. Bir web uygulamasının aslında bunların belki 40-60'ına ihtiyacı vardır. Geri kalan yüzlerce syscall, kiracının ihtiyaç duymadığı ama yine de istismar edebileceği bir yüzeydir. Runtime güvenliğinin temel felsefesi bu yüzeyi daraltmaktır.

## Savunma Katmanı 1: seccomp ile Syscall Filtreleme

### Çalışma Mantığı

`seccomp` (secure computing mode), bir sürecin yapabileceği syscall'ları çekirdek düzeyinde filtreleyen bir mekanizmadır. Modern kullanımı `seccomp-bpf` olarak bilinir: bir BPF (Berkeley Packet Filter) programı, her syscall çağrısında syscall numarasına ve argümanlarına bakarak karar verir — izin ver (`ALLOW`), reddet (`ERRNO` ile hata döndür), sonlandır (`KILL`) ya da izle (`TRACE`).

Buradaki güzellik, filtrenin syscall daha çekirdek mantığına girmeden değerlendirilmesidir. Yani zafiyetli bir syscall'a hiç ulaşılamaz; saldırı yüzeyi doğrudan küçülür.

### Uygulama ve Varsayılanlar

Docker ve containerd, kutudan çıktığı haliyle bir **varsayılan seccomp profili** uygular. Bu profil, tehlikeli ya da nadiren gerekli syscall'ların önemli bir kısmını (örneğin `mount`, `ptrace`, `kexec_load`, `bpf` gibi güçlü çağrılar) bloke eder. Bu, kritik bir güvenli varsayılandır (secure default).

Yaygın ve tehlikeli hata: `--privileged` kullanımı ya da `--security-opt seccomp=unconfined` ile bu profili tamamen devre dışı bırakmak. Bunu yaptığınızda konteyner, çekirdeğin tüm syscall yüzeyine ham erişir. Multi-tenant bir ortamda bu, izolasyonun temel taşını kaldırmak demektir.

Kubernetes tarafında, `securityContext` altında `seccompProfile` alanıyla `RuntimeDefault` seçilebilir. Kavramsal olarak doğru yaklaşım, cluster genelinde `RuntimeDefault`'u zorunlu kılmak ve gerektiğinde uygulamaya özel daraltılmış profiller yazmaktır.

### Uygulamaya Özel Profil

En güçlü yaklaşım, uygulamanın gerçekte kullandığı syscall kümesini gözlemleyip (örneğin `strace` ya da audit tabanlı araçlarla profilleme) yalnızca o kümeye izin veren minimal bir profil üretmektir. Not: Kesin syscall listelerini uydurmak yerine ilkeyi vurgulamak gerekir — profili gözleme dayalı türetin, elle tahmin etmeyin, aksi halde ya çalışmayan bir uygulama ya da fazla geniş bir yüzey elde edersiniz.

## Savunma Katmanı 2: Capabilities'i Kısıtlama

### İlke: Least Privilege

Docker varsayılan olarak konteynerlere sınırlı bir capability kümesi verir, ama bu küme çoğu uygulama için hâlâ fazladır. Doğru yaklaşım, **tüm capability'leri düşürüp** (`cap_drop: ALL`) yalnızca kesinlikle gerekli olanları geri eklemektir (`cap_add`).

Örneğin 1024'ün altındaki bir porta bağlanması gereken bir servis yalnızca `CAP_NET_BIND_SERVICE`'e ihtiyaç duyar. Buna karşılık `CAP_SYS_ADMIN` neredeyse "yeni root"tur — mount işlemleri, namespace manipülasyonu ve çok sayıda hassas işlemi kapsar; bir konteynere verildiğinde kaçış riskini dramatik ölçüde artırır.

### Kubernetes Örneği (Kavramsal)

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
    add:
      - NET_BIND_SERVICE   # yalnızca gerçekten gerekiyorsa
  seccompProfile:
    type: RuntimeDefault
```

Buradaki her satır bir savunma prensibidir:
- `runAsNonRoot`: Konteyner içinde root olarak çalışmamak, bir user namespace yanlış yapılandırıldığında host root'una eşleşme riskini azaltır.
- `allowPrivilegeEscalation: false`: `setuid` ikili dosyalar aracılığıyla yetki yükseltmeyi engeller (`no_new_privs` biti).
- `readOnlyRootFilesystem`: Dosya sisteminin değiştirilemez olması, kalıcılık (persistence) ve araç indirmeyi zorlaştırır.

## Savunma Katmanı 3: AppArmor ve SELinux (MAC)

### Zorunlu Erişim Kontrolü Nedir?

AppArmor ve SELinux, **Mandatory Access Control (MAC)** sistemleridir. Klasik izinler (DAC — dosya sahipliği/rwx) sürecin kendi kararına bırakılırken, MAC ayrı bir politika katmanı olarak dayatılır: root bile olsanız, politika izin vermiyorsa erişemezsiniz.

- **AppArmor**: Yol tabanlı (path-based) profillerle çalışır. Bir sürecin hangi dosyalara, hangi ağ işlemlerine, hangi capability'lere erişebileceğini bir profil dosyasında tanımlar. Debian/Ubuntu ekosisteminde yaygındır.
- **SELinux**: Etiket tabanlı (label-based) çalışır. Her nesneye ve sürece bir güvenlik bağlamı (context) atanır ve erişim bu etiketler arası kurallarla belirlenir. RHEL/Fedora ekosisteminde varsayılandır. Konteynerler için `container_t` gibi özel tipler kullanılır ve bu, konteynerin host dosyalarına erişimini sıkı biçimde kısıtlar.

### seccomp'tan Farkı

Bu ikisini karıştırmamak önemlidir. seccomp **syscall düzeyinde** filtreler (hangi çekirdek girişine dokunulabilir). AppArmor/SELinux ise **kaynak/nesne düzeyinde** yetkilendirir (hangi dosyaya, sockete, aygıta erişilebilir). Bunlar birbirini tamamlar: seccomp `mount` syscall'ını bloke ederken, AppArmor `/etc/shadow` okumasını ya da `/proc/sys` yazmasını engelleyebilir. Katmanlı savunma (defense in depth) tam olarak bu birlikte kullanımdır.

Docker varsayılan bir AppArmor profili (`docker-default`) uygular. `--security-opt apparmor=unconfined` ile bunu kaldırmak, yine izolasyonu zayıflatan yaygın bir hatadır.

## Savunma Katmanı 4: Runtime Sandboxing — gVisor ve Kata

Yukarıdaki katmanlar saldırı yüzeyini daraltır ama paylaşılan çekirdek gerçeğini ortadan kaldırmaz. Gerçekten güçlü kiracı izolasyonu için mimariyi değiştirmek gerekir. İki temel yaklaşım vardır.

### gVisor: Kullanıcı Alanı Çekirdek

gVisor (Google), konteyner ile host çekirdeği arasına **kullanıcı alanında çalışan bir uygulama çekirdeği** (`Sentry` bileşeni) yerleştirir. Konteynerin yaptığı syscall'lar doğrudan host çekirdeğine gitmez; gVisor bunları yakalar ve syscall'ların büyük çoğunluğunu kendi Go dilinde yeniden yazılmış çekirdek mantığıyla karşılar.

Sonuç: Konteyner ile host çekirdeği arasındaki doğrudan syscall yüzeyi dramatik biçimde küçülür. Host çekirdeğinde bir zafiyet olsa bile, konteyner ona doğrudan ham argümanlarla ulaşamaz; araya gVisor'ın kendi güvenlik sınırı girer. Bedeli, bazı syscall-yoğun iş yüklerinde performans ek yükü (overhead) ve nadir/eksik syscall'lar nedeniyle bazı uygulamaların uyumsuzluğudur. `runsc` runtime'ı, containerd ile entegre edilerek kullanılır.

### Kata Containers: Hafif Sanal Makine

Kata Containers farklı bir yol izler: Her konteyneri (ya da pod'u) hafif bir sanal makine içinde, **kendi ayrı çekirdeğiyle** çalıştırır. Burada araya bir hypervisor (örneğin QEMU tabanlı ya da Firecracker gibi hafif bir VMM) girer. Böylece kiracının konteyneri host çekirdeğini değil, kendine ait misafir çekirdeği kullanır.

Bu, VM düzeyinde donanım destekli izolasyon (donanım sanallaştırma uzantıları) sağlar; güven sınırı hypervisor olur. Bedeli, VM başlatma gecikmesi ve daha yüksek bellek ayak izidir; ancak bu maliyet güçlü izolasyon karşılığında ödenir. Kata, standart konteyner arayüzleriyle (OCI/CRI) uyumlu olacak biçimde tasarlanmıştır, dolayısıyla Kubernetes'e bir `RuntimeClass` olarak entegre edilir.

### Hangisini Ne Zaman?

- **Güvenilmeyen kod / gerçek multi-tenancy** (örneğin müşteri kodu çalıştıran SaaS, CI runner'lar): Sandboxing neredeyse zorunludur. gVisor syscall yüzeyini daraltır; Kata daha kalın bir VM sınırı sunar.
- **Güvenilen dahili iş yükleri**: seccomp + capability drop + MAC çoğu zaman yeterlidir; sandboxing ek yükü gereksiz olabilir.
- Karar, tehdit modeline ve "aynı node'da yan yana çalışan kiracıların birbirine güvenip güvenmediğine" bağlıdır.

## Kubernetes'te RuntimeClass ve Katmanların Birleştirilmesi

Kubernetes'te farklı runtime'lar `RuntimeClass` nesnesiyle tanımlanır. Kavramsal olarak, güvenilmeyen iş yüklerini `runsc` (gVisor) ya da `kata` handler'ına yönlendiren bir RuntimeClass tanımlanır ve pod spec'inde `runtimeClassName` ile seçilir. Böylece hassas kiracılar sandboxlı runtime'a, güvenilen sistem bileşenleri standart runtime'a düşürülebilir.

Bunun üstüne **Pod Security Admission** (Kubernetes'in yerleşik `baseline`/`restricted` politikaları) eklenerek `privileged` konteynerler, host namespace paylaşımı (`hostPID`, `hostNetwork`), hostPath mount'ları gibi tehlikeli desenler admission düzeyinde reddedilir. Namespace düzeyinde `restricted` profilini zorunlu kılmak güçlü bir güvenli varsayılandır.

## Tespit (Detection)

Sertleştirme kadar tespit de kritiktir. İzlenmesi gereken sinyaller:

- **seccomp ihlalleri**: Bir konteynerin normalde çağırmadığı bir syscall'ı denemesi ve `KILL`/`ERRNO` ile durdurulması, ya profil hatasıdır ya da anomalidir. Audit loglarında bu denemeler görünür.
- **Beklenmeyen syscall davranışı**: Runtime güvenlik araçları (örneğin eBPF tabanlı çözümler — Falco, Tetragon gibi) syscall ve çekirdek olaylarını gözlemleyerek "bir konteynerden `mount` çağrısı", "beklenmeyen bir çocuk sürecin spawn edilmesi", "`/proc` içindeki hassas yollara erişim" gibi davranışsal kuralları tetikleyebilir.
- **Yetki yükseltme göstergeleri**: `setuid` binary çalıştırma, yeni capability edinme, `/proc/self/status` üzerinden capability haritasında beklenmeyen değişiklikler.
- **Dosya bütünlüğü**: `readOnlyRootFilesystem` ihlali denemeleri, `/dev` ya da host mount noktalarına yazma girişimleri.
- **Runtime uyumsuzluğu**: Sandboxlı çalışması gereken bir pod'un standart runtime'da başlaması — RuntimeClass zorlamasının kaçtığına işaret eder; admission log'ları ve node üzerindeki runtime metadata'sı ile doğrulanmalıdır.

eBPF tabanlı gözlem, host çekirdeğinden konteyner davranışını izlediği için konteyner içindeki bir saldırganın kolayca göremeyeceği bir avantaj sağlar.

## Yaygın Hatalar

- **`--privileged` kullanımı**: Neredeyse tüm izolasyonu kaldırır (tüm capability'ler, seccomp/AppArmor devre dışı, aygıtlara erişim). Multi-tenant ortamda kesinlikle kaçınılmalıdır.
- **Güvenlik profillerini `unconfined` yapmak**: seccomp ya da AppArmor'u "uygulama çalışmıyor" diye kapatmak, kök nedeni çözmek yerine yüzeyi sonuna kadar açar. Doğrusu, eksik izni tespit edip profile ekleyerek daraltmaktır.
- **Konteyner içinde root çalıştırmak**: `runAsNonRoot` kullanmamak, user namespace yanlış yapılandırıldığında ya da bir kaçış zafiyetinde host root'una köprü kurabilir.
- **Docker socket'ini konteynere mount etmek** (`/var/run/docker.sock`): Bu, konteynere host üzerinde yeni ayrıcalıklı konteyner başlatma yetkisi verir — pratikte doğrudan host ele geçirmeye eşdeğerdir.
- **hostPath, hostPID, hostNetwork paylaşımı**: Namespace izolasyonunu delerek konteyneri host'un dosya sistemine/süreçlerine/ağına açar.
- **"Konteyner = sanal makine" varsayımı**: En temel kavramsal hata. Standart konteyner paylaşılan çekirdek üzerinde çalışır; VM düzeyi izolasyon istiyorsanız Kata gibi bir sandbox gerekir.
- **Tek katmana güvenmek**: Yalnızca seccomp ya da yalnızca capability drop yeterli değildir. Güç, katmanların birlikteliğinden gelir.
- **Sandbox'ı yanlış iş yükünde konumlandırmak**: gVisor/Kata'yı her yere uygulamak gereksiz performans maliyeti; hiç uygulamamak güvenilmeyen kod için kabul edilemez risktir. Tehdit modeline göre seçilmelidir.

## Özet ve Katmanlı Model

Güvenli bir multi-tenant konteyner mimarisi tek bir sihirli ayara değil, üst üste binen katmanlara dayanır:

1. **Güvenli varsayılanlar**: `RuntimeDefault` seccomp, `docker-default` AppArmor, non-root, read-only root FS — bunları kapatmayın.
2. **Least privilege**: `cap_drop: ALL` + minimum ekleme, `allowPrivilegeEscalation: false`.
3. **MAC katmanı**: AppArmor ya da SELinux ile nesne düzeyinde kısıtlama.
4. **Admission zorlaması**: Pod Security Admission `restricted`, privileged/hostPath yasağı.
5. **Runtime sandboxing**: Güvenilmeyen kiracı kodu için gVisor (syscall yüzeyi daraltma) ya da Kata (VM sınırı).
6. **Tespit**: eBPF tabanlı davranışsal izleme, seccomp ihlal logları, dosya bütünlüğü.

Temel içgörü değişmez: Konteyner izolasyonunun zayıf halkası paylaşılan çekirdektir. Her savunma katmanı ya bu çekirdeğe ulaşan yüzeyi daraltır (seccomp, capabilities, MAC) ya da araya yeni bir güven sınırı koyar (gVisor, Kata). Doğru güvenlik, saldırı yüzeyini uygulamanın gerçek ihtiyacına indirgemek ve her katmanı güvenli varsayılanlarla kurup gözlemlenebilir kılmaktır.
