# Hypervisor ve Sanallaştırma İç Yapısı (Tip-1/Tip-2, VM Kaçışı, VT-x/AMD-V)

## Giriş ve Tanım

Sanallaştırma (virtualization), tek bir fiziksel makinenin donanım kaynaklarını (CPU, bellek, disk, ağ) birden fazla yalıtılmış (isolated) sanal makineye (Virtual Machine, VM) bölerek her birine sanki kendi başına bir bilgisayarmış gibi çalışma ortamı sunan tekniktir. Bu bölmeyi yapan yazılım katmanına **hypervisor** ya da klasik adıyla **VMM (Virtual Machine Monitor)** denir.

Hypervisor'ın temel görevi, birden çok işletim sisteminin (guest OS) aynı donanımı paylaşmasını sağlarken her birinin diğerlerinden habersiz ve yalıtılmış kalmasıdır. Konteynerlerden (container) farklı olarak sanallaştırmada her guest kendi çekirdeğini (kernel) çalıştırır; konteynerler ise host çekirdeğini paylaşır. Bu ayrım, güvenlik sınırının nerede çizildiğini ve tehdit modelinin nasıl kurulması gerektiğini doğrudan belirler.

Bu makale, hypervisor'ın nasıl çalıştığını, donanım destekli sanallaştırma uzantılarını (VT-x, AMD-V), yalıtımın nasıl sağlandığını, **VM kaçışı (VM escape)** zafiyet sınıfını ve bulut ortamında bunun savunma/tespit yaklaşımlarını kavramsal düzeyde derinlemesine ele alır.

## Neden Sanallaştırma Zordur: Klasik Sanallaştırma Sorunu

Sanallaştırmanın kalbinde şu soru yatar: guest işletim sistemi, kendisinin en yetkili seviyede (kernel mode) çalıştığını sanır ama gerçekte çalışmaz; hypervisor daha yetkilidir. O halde guest, ayrıcalıklı (privileged) bir komut çalıştırdığında ne olur?

### Trap-and-Emulate Modeli

Popek ve Goldberg'in 1974'teki klasik teoremi bu problemi biçimlendirir. Bir mimarinin verimli şekilde sanallaştırılabilmesi için **sensitive instruction'ların** (sistem durumunu okuyan/değiştiren komutların) tamamının **privileged instruction** olması gerekir; yani düşük ayrıcalık seviyesinde çalıştırıldıklarında bir istisna (trap) fırlatmaları gerekir.

Mantık şudur: guest'i daha az ayrıcalıklı bir seviyede (örneğin ring 1 veya ring 3) çalıştırırsın. Guest ayrıcalıklı bir komut yürütmeye kalkınca CPU trap fırlatır, kontrol hypervisor'a geçer, hypervisor komutun ne yapmak istediğini anlar, sanal donanım üzerinde taklit eder (emulate) ve guest'e geri döner. Buna **trap-and-emulate** denir.

### x86'nın Sanallaştırılamaz Olma Sorunu

Sorun şuydu: klasik x86 mimarisi Popek-Goldberg kriterini sağlamıyordu. Yaklaşık 17 kadar "sorunlu" komut vardı (`POPF`, `SGDT`, `SIDT`, `SMSW` gibi) ki bunlar sensitive olmalarına rağmen düşük ayrıcalıkta çalıştırıldıklarında trap fırlatmadan sessizce yanlış davranıyorlardı. Örneğin `POPF` komutu, düşük ayrıcalıkta çalıştığında interrupt flag'ini değiştirmeye çalışmayı sessizce yutuyor, trap üretmiyordu. Bu, hypervisor'ın guest'in ne yaptığını fark edememesi demekti.

Bu yüzden ilk nesil x86 hypervisor'ları (VMware'in öncü çalışması gibi) yazılımsal hilelere başvurdu:

- **Binary translation:** Guest kernel kodu çalışmadan önce taranır, sorunlu komutlar güvenli çağrılarla değiştirilir (yeniden yazılır).
- **Paravirtualization:** Guest çekirdeği bilerek değiştirilir; ayrıcalıklı işlemler için doğrudan hypervisor'a **hypercall** yapar (Xen'in ilk yaklaşımı). Bu, kaynak koda erişim gerektirir, dolayısıyla değiştirilemeyen sistemlerde kullanılamaz.

Bu yaklaşımlar işe yaradı ama karmaşık, kırılgan ve performans açısından maliyetliydi.

## Donanım Destekli Sanallaştırma: VT-x ve AMD-V

Intel (VT-x, kod adı Vanderpool) ve AMD (AMD-V, kod adı Pacifica) yaklaşık 2005-2006'da CPU'ya doğrudan sanallaştırma desteği ekledi. Temel fikir: sensitive komutları donanım seviyesinde trap edilebilir hale getirmek ve hypervisor için ayrı bir çalışma modu tanımlamak.

### Root ve Non-Root Mod

VT-x, mevcut ring yapısına dik bir yeni boyut ekledi:

- **VMX root operation:** Hypervisor burada çalışır. Tam yetkilidir.
- **VMX non-root operation:** Guest burada çalışır. Guest kendi ring 0'ında (kernel) çalışabilir ve kendini tam yetkili sanır, ama belirli olaylar host'a kontrolü geri devreder.

Böylece guest kernel'i gerçekten ring 0'da çalışır; artık ring deprivileging veya binary translation gerekmez. Guest tarafından yürütülen kritik işlemler, yapılandırmaya bağlı olarak otomatik trap oluşturur.

### VM Entry, VM Exit ve VMCS

İki mod arasındaki geçişler temel mekanizmadır:

- **VM entry:** root'tan non-root'a geçiş; hypervisor guest'i çalıştırmaya başlar (Intel'de `VMLAUNCH`/`VMRESUME`).
- **VM exit:** non-root'tan root'a dönüş; guest bir "sanallaştırılması gereken" olay tetikledi ve kontrol hypervisor'a döndü.

Bu geçişlerin durumunu tutan yapıya **VMCS (Virtual Machine Control Structure)** denir (AMD'de eşdeğeri **VMCB**). VMCS, guest'in ve host'un CPU durumunu (register'lar, kontrol register'ları), hangi olayların VM exit tetikleyeceğini belirleyen kontrol bitlerini ve exit'in nedenini (exit reason) barındıran bellek yapısıdır. Hypervisor, hangi olayların kendisine devredileceğini VMCS'teki kontrol alanlarıyla ince ayarlar (örneğin belirli `CPUID`, `RDMSR`/`WRMSR`, port I/O, harici kesme olaylarında exit alıp almamak).

VM exit maliyetlidir (yüzlerce ila binlerce çevrim). Bu yüzden modern hypervisor tasarımının büyük bölümü **VM exit sayısını azaltmaya** odaklanır. Performansı belirleyen ana metrik çoğu zaman exit sıklığıdır.

### Bellek Sanallaştırma: EPT / NPT

Guest'in belleği de sanallaştırılmalıdır. Guest, kendi fiziksel adreslerini (guest physical address) gerçek fiziksel adres sanır, ama değildir. Başlangıçta bu, **shadow page table** ile çözülüyordu: hypervisor, guest'in sayfa tablolarını izleyip gölge bir kopya tutuyordu; bu, her guest sayfa tablosu değişiminde masraflı müdahale gerektiriyordu.

Donanım bunu **ikinci seviye adres çevirisi (Second Level Address Translation, SLAT)** ile çözdü:

- Intel'de **EPT (Extended Page Tables)**
- AMD'de **NPT (Nested Page Tables)** ya da RVI

Artık iki katmanlı çeviri var: guest virtual → guest physical (guest'in kendi sayfa tabloları) ve guest physical → host physical (hypervisor'ın kontrol ettiği EPT/NPT tabloları). Donanım her iki katmanı da yürütür; hypervisor guest sayfa tablosu değişimlerine karışmak zorunda kalmaz. Bu, hem performansı ciddi artırır hem de yalıtımı donanım seviyesinde güçlendirir: bir guest, EPT eşlemesi olmayan host belleğine hiçbir şekilde erişemez.

### IOMMU ve Cihaz Sanallaştırma

CPU ve bellek yalıtımı yeterli değildir; **DMA (Direct Memory Access)** yapabilen cihazlar (ağ kartı, GPU) doğrudan belleğe erişir ve bir guest'e cihaz atanmışsa (device passthrough) o cihaz teorik olarak tüm fiziksel belleğe DMA yapabilir. Bunu engellemek için **IOMMU** (Intel'de **VT-d**, AMD'de AMD-Vi) kullanılır: IOMMU, cihazların DMA adreslerini de çevirir ve sınırlar, böylece bir guest'e atanmış cihaz başka guest'in veya host'un belleğine erişemez. IOMMU, passthrough güvenliğinin temel taşıdır; yanlış yapılandırılmış IOMMU, doğrudan bellek sızıntısına yol açar.

## Tip-1 ve Tip-2 Hypervisor Ayrımı

Bu sınıflandırma, hypervisor'ın donanıma göre nerede konumlandığına bakar.

### Tip-1 (Bare-Metal) Hypervisor

Doğrudan donanım üzerinde çalışır; altında bir işletim sistemi yoktur, hypervisor'ın kendisi minimal bir çekirdek görevi görür.

- Örnekler: VMware ESXi, Microsoft Hyper-V, Xen, KVM (KVM tartışmalı bir sınırda; Linux çekirdeğini hypervisor'a dönüştürdüğü için genelde Tip-1 kabul edilir).
- Avantaj: daha düşük katman, daha küçük **saldırı yüzeyi (attack surface)** potansiyeli, daha iyi performans, doğrudan donanım kontrolü.
- Bulut sağlayıcılar (AWS, Azure, GCP) neredeyse tümüyle Tip-1 mimariler kullanır.

### Tip-2 (Hosted) Hypervisor

Normal bir işletim sistemi üzerinde bir uygulama olarak çalışır. Host OS ile guest'ler arasında aracılık yapar.

- Örnekler: VMware Workstation/Fusion, Oracle VirtualBox, QEMU (tek başına yazılımsal).
- Avantaj: kurulumu kolay, masaüstünde geliştirici/test için idealdir.
- Dezavantaj: host OS'in tüm karmaşıklığı ve zafiyetleri de tehdit modeline dahil olur; performans genelde daha düşüktür.

Not: Hyper-V etkinleştirildiğinde Windows'un kendisi bir Tip-1 hypervisor'ın üstünde çalışan bir "root partition" haline gelir; bu, ikili sınıflandırmanın gerçekte bulanık olduğunu gösterir. KVM de "Linux'un modül olarak hypervisor'a dönüşmesi" nedeniyle net bir kutuya sığmaz. Sınıflandırmayı katı bir kural değil, konumlandırmayı anlamak için bir sezgi olarak kullanmak doğru olur.

## VM Kaçışı (VM Escape) Zafiyet Sınıfı

### Tanım ve Neden Kritik Olduğu

**VM escape**, bir guest içinde çalışan saldırganın yalıtım sınırını kırıp hypervisor'a veya host'a, oradan da diğer guest'lere erişim kazanmasıdır. Bu, sanallaştırmanın en ciddi zafiyet sınıfıdır çünkü tüm çok-kiracılı (multi-tenant) bulut güvenlik modeli "guest, host'tan çıkamaz" varsayımına dayanır. Bir VM escape, bu temel güven sınırını yok eder: aynı fiziksel sunucudaki başka bir müşterinin verisine erişim, tüm hypervisor'ın ele geçirilmesi anlamına gelebilir.

### Kök Neden: Saldırı Yüzeyi Nerededir

Guest, doğrudan hypervisor çekirdeğiyle konuşmaz; asıl saldırı yüzeyi hypervisor'ın guest'e sunmak zorunda olduğu **arayüzlerdir**:

1. **Emüle edilen cihazlar (emulated devices):** Guest'e sunulan sanal ağ kartı, disk denetleyicisi, ses kartı, USB denetleyicisi, grafik adaptörü gibi cihazların hepsi hypervisor içinde (veya QEMU gibi bir yardımcı süreçte) yazılımla taklit edilir. Bu emülasyon kodu karmaşıktır ve tarihsel olarak VM escape zafiyetlerinin en büyük kaynağıdır. Meşhur "VENOM" zafiyeti sanal floppy disk denetleyicisi (FDC) emülasyonundaki bir buffer overflow'du; guest'ten host süreç belleğine taşma sağlıyordu.
2. **Paravirtual arayüzler ve hypercall'lar:** Guest'in hypervisor'dan hizmet istediği çağrılar (virtio, Xen hypercall'ları). Yetersiz doğrulama burada da kaçışa yol açabilir.
3. **Paylaşılan bileşenler:** Ortak bellek bölgeleri, panolar (clipboard sharing), sürükle-bırak, misafir eklentileri (guest additions/tools).
4. **CPU/mikromimari kanallar:** Speculative execution zafiyetleri (Spectre, Meltdown, L1TF/Foreshadow, MDS) doğrudan "kod çalıştırma" anlamında escape olmasa da, yalıtım sınırını aşan **bilgi sızıntısı (information disclosure)** sağlayabilir; bir guest'in başka guest'in veya host'un belleğinden veri okumasına imkân verebilir.

Genel örüntü: **kod çalıştırma escape'i neredeyse her zaman emülasyon katmanındaki bellek güvenliği hatasından (memory corruption) doğar; sızıntı escape'i ise mikromimari yan kanallardan doğar.**

### Saldırı Yüzeyini Küçültme Prensibi

Modern hypervisor tasarımı bu gerçeği kabul eder ve **saldırı yüzeyini bilinçli olarak daraltır**:

- **Cihaz modeli izolasyonu:** QEMU/emülasyon kodunu ayrı, düşük ayrıcalıklı bir süreçte, sandbox içinde (seccomp, namespace) çalıştırmak. Böylece emülasyondaki bir hata, hemen root hypervisor'ı değil sadece o daraltılmış süreci ele geçirir. AWS'nin Nitro mimarisi ve modern KVM/QEMU dağıtımları bu prensibi izler.
- **Gereksiz cihazları kapatmak:** Kullanılmayan sanal cihazları (floppy, ses, USB) guest'ten tamamen kaldırmak. Var olmayan cihaz saldırılamaz.
- **Küçük TCB (Trusted Computing Base):** Hypervisor'ı olabildiğince küçük tutmak; ne kadar az kod o kadar az zafiyet.
- **Donanıma iş devretmek:** Emülasyon yerine SLAT (EPT/NPT), IOMMU (VT-d) ve SR-IOV gibi donanım özellikleriyle yazılımsal aracılığı azaltmak.

## Nested Virtualization (İç İçe Sanallaştırma)

**Nested virtualization**, bir hypervisor'ın içinde başka bir hypervisor çalıştırmaktır (L0 host, L1 guest-hypervisor, L2 iç guest). Örnek kullanımlar: bir bulut VM'i içinde kendi hypervisor'ını çalıştırmak (bulutta CI/CD, Windows'ta WSL2 + Docker, güvenlik kum havuzları).

Zorluğu: CPU tek bir VMX/SVM köküne sahiptir. L1 hypervisor kendi VMCS'ini oluşturup `VMLAUNCH` çalıştırmaya kalkınca bu aslında L0 tarafından yakalanmalı ve L0, L1'in VMCS'ini gerçek donanım VMCS'iyle "birleştirmeli" (VMCS shadowing). Bu, ek karmaşıklık ve daha fazla saldırı yüzeyi demektir: nested katman, hem performansı düşürür hem de yeni bir zafiyet katmanı ekler. Güvenlik açısından bilinmesi gereken şey, nested virtualization'ın TCB'yi büyüttüğü ve bu yüzden yalnızca gerçekten gerektiğinde etkinleştirilmesi gerektiğidir.

## Tespit ve Savunma

### Host/Hypervisor Tarafı

- **Yama disiplini:** VM escape zafiyetleri neredeyse tümüyle hypervisor/emülasyon kodundaki hatalardır. Hypervisor (ESXi, Hyper-V, KVM/QEMU) ve mikrokod güncellemelerini hızlı uygulamak en yüksek etkili savunmadır. Mikromimari zafiyetler (Spectre türevleri) genelde mikrokod + çekirdek yaması + bazen SMT (Hyper-Threading) devre dışı bırakmayı gerektirir.
- **En az yetki ve süreç yalıtımı:** Emülasyon süreçlerini sandbox (seccomp-bpf, ayrı kullanıcı, namespace) altında çalıştırmak. KVM'de cihaz modelini kısıtlamak.
- **Saldırı yüzeyini kısmak:** Gereksiz emüle cihazları, paylaşılan panoyu, guest tools entegrasyonlarını kapatmak.
- **IOMMU'yu zorunlu kılmak:** Cihaz passthrough kullanılıyorsa VT-d/AMD-Vi'nin etkin ve doğru yapılandırılmış olduğunu doğrulamak.
- **Bellek güvenliği:** Mümkünse emülasyon kodunu bellek-güvenli dillerde yazılmış bileşenlerle değiştirmek (bazı projeler cihaz modellerini Rust ile yeniden yazıyor).

### Tespit ve İzleme

- **Anormal VM exit örüntüleri:** Aşırı ve olağandışı `CPUID`, MSR erişimi veya belirli cihaz portlarına yoğun trafik, guest içinden yürütülen bir keşif/istismar girişiminin işareti olabilir.
- **Hypervisor süreç bütünlüğü:** Host üzerindeki hypervisor süreçlerinin (örneğin QEMU) beklenmeyen çocuk süreç oluşturması, kabuk çağırması veya olağandışı sistem çağrıları yapması güçlü bir escape sinyalidir. Host EDR/telemetri bunu yakalamalıdır.
- **Kaynak ve komşuluk anomalileri:** Bir guest'in beklenmeyen bellek/CPU örüntüsü, yan kanal saldırısı belirtisi olabilir.
- **Bütünlük ölçümü:** TPM ve **measured/secure boot** ile hypervisor'ın başlangıç bütünlüğünü doğrulamak; kök seviyede kalıcılığı zorlaştırmak.

### Mimari Savunma: Bulut Bağlamı

Modern bulut, "tek fiziksel makinede çok kiracı" riskini mimariyle azaltır:

- **Donanım kökenli güven ve küçük hypervisor:** Nitro gibi tasarımlar sanallaştırma işini özel donanım kartlarına devredip host hypervisor'ı minimize eder.
- **Kiracı yalıtımı katmanları:** Kritik iş yükleri için "dedicated host" veya "bare-metal instance" seçenekleriyle fiziksel komşuluk (co-tenancy) tamamen kaldırılabilir; bu, yan kanal ve escape risklerini kökten azaltır.
- **Confidential computing:** Intel SGX/TDX, AMD SEV-SNP gibi teknolojiler guest belleğini hypervisor'a karşı bile şifreler; artık "hypervisor'a güven" varsayımı gevşetilir. Tehdit modeli tersine döner: hypervisor ele geçirilse bile guest verisi şifreli kalır.

## Yaygın Hatalar ve Yanlış Anlamalar

- **"VM, konteynerden her zaman daha güvenlidir" mutlaklaştırması:** Genelde doğrudur çünkü yalıtım sınırı donanım destekli ve daha derindir; ama yanlış yapılandırılmış, yamasız, gereksiz cihazlarla dolu bir hypervisor, iyi sertleştirilmiş bir konteyner platformundan daha zayıf olabilir. Güvenlik konfigürasyona ve yama durumuna bağlıdır, kategoriye değil.
- **Emülasyon saldırı yüzeyini görmezden gelmek:** İnsanlar "guest kernel'i ele geçirdim, hâlâ VM içindeyim" der ve durur. Oysa asıl kritik yüzey emüle cihazlardır; kullanılmayan cihazları açık bırakmak tam da bu yüzden tehlikelidir.
- **Nested virtualization'ı gereksiz açmak:** Ekstra katman, ekstra saldırı yüzeyi ve performans kaybıdır. İhtiyaç yoksa kapatılmalıdır.
- **Mikromimari sızıntıları "escape değil" diye küçümsemek:** Kod çalıştırma olmasa da başka kiracının belleğini okuyabilmek, çok-kiracılı ortamda tam bir güvenlik ihlalidir.
- **VM exit maliyetini göz ardı etmek:** Performans sorunlarında çoğu zaman kök neden aşırı VM exit'tir; SLAT, paravirtual sürücüler (virtio) ve exit'i azaltan yapılandırma bu yüzden önemlidir.
- **IOMMU'yu passthrough'da unutmak:** Cihaz doğrudan atanıp IOMMU etkinleştirilmezse, guest'e atanan cihaz tüm host belleğine DMA yapabilir; bu, sanallaştırma yalıtımını tamamen delen bir hatadır.
- **Tip-1/Tip-2 sınırını mutlak sanmak:** KVM ve Hyper-V gibi örnekler ikili sınıflandırmaya tam oturmaz; sınıflandırmayı sezgi olarak kullanmak, kesin bir taksonomi olarak değil.

## Özet

Sanallaştırma, Popek-Goldberg'in trap-and-emulate modeline dayanır; x86'nın bu modele uymayan doğası önce yazılımsal hilelerle (binary translation, paravirtualization), sonra donanım uzantılarıyla (VT-x/AMD-V, root/non-root mod, VMCS, VM entry/exit) çözülmüştür. Bellek yalıtımı EPT/NPT (SLAT) ile, cihaz DMA yalıtımı ise IOMMU (VT-d/AMD-Vi) ile donanıma devredilmiştir. Hypervisor'lar konumlarına göre Tip-1 (bare-metal) ve Tip-2 (hosted) diye ayrılır, ama bu sınır bulanıktır. En kritik zafiyet sınıfı **VM escape**'tir; kök nedeni çoğunlukla emüle cihazlardaki bellek güvenliği hatalarıdır ve mikromimari yan kanallar bilgi sızıntısı yoluyla yalıtımı deler. Savunma; hızlı yama, saldırı yüzeyini daraltma, süreç sandbox'lama, IOMMU zorunluluğu, hypervisor süreç bütünlüğü izleme ve confidential computing gibi mimari önlemlerle kurulur. Temel ilke değişmez: **ne kadar az kod ve ne kadar az açık arayüz, o kadar küçük saldırı yüzeyi ve o kadar güçlü yalıtım.**
