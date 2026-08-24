# Hypervisor / VM Escape: Sanallaştırma Sınır İhlalleri

## Tanım

**VM escape** (sanal makine kaçışı), bir misafir sanal makine (guest VM) içinde kod çalıştırma yeteneğine sahip bir saldırganın, sanallaştırma sınırını aşarak ya **hypervisor** (VMM — Virtual Machine Monitor) süreçlerini, ya host işletim sistemini, ya da aynı fiziksel makine üzerindeki komşu VM'leri ele geçirmesidir. Bu, izolasyon modelinin en temel varsayımını çökertir: bir VM'in içinden dışarısına dokunulamayacağı varsayımını.

Sanallaştırmanın güvenlik değeri tümüyle bu izolasyon sınırına dayanır. Bulut sağlayıcıları (AWS, Azure, GCP), farklı müşterilerin (tenant) iş yüklerini aynı fiziksel donanım üzerinde çalıştırırken güvenliği bu sınırdan alır. Dolayısıyla bir VM escape zafiyeti, tek bir müşterinin sınırını değil, **çok kiracılı (multi-tenant)** bulut altyapısının bütününü tehdit eder. Container escape ile karıştırılmamalıdır: container'lar aynı çekirdeği (kernel) paylaşır ve namespace/cgroup tabanlı mantıksal izolasyonla ayrılır; tam sanallaştırmada ise her VM'in kendi çekirdeği vardır ve izolasyon donanım destekli (Intel VT-x, AMD-V) bir katman tarafından zorlanır. Bu, çok daha güçlü ama yine de aşılabilir bir sınırdır.

## Kök Neden ve Çalışma Mantığı

### Saldırı yüzeyi nerede oluşur

Modern hypervisor'lar donanımı doğrudan taklit etmez; misafirin ayrıcalıklı işlemleri (I/O, MSR erişimi, belirli CPU komutları) bir **VM exit** ile hypervisor'a devredilir. Hypervisor bu isteği işler ve **VM entry** ile misafire geri döner. Saldırı yüzeyi, misafirden hypervisor'a geçen bu her sınır noktasında oluşur. Başlıca kategoriler:

1. **Emüle edilen aygıtlar (device emulation).** Klasik VM escape'lerin ezici çoğunluğu buradan gelir. QEMU gibi bir VMM, misafire sanal ağ kartları, disk denetleyicileri, ses/grafik kartları, USB denetleyicileri sunar. Bu aygıtların emülasyon kodu, host tarafında karmaşık C kodudur ve misafirin tam kontrol ettiği register/DMA verisini işler. Tarihi olarak en meşhur örnek **VENOM** (CVE-2015-3456) idi: QEMU'nun sanal floppy disk denetleyicisindeki (FDC) bir buffer overflow, misafirin host'ta kod çalıştırmasına yol açabiliyordu. Aygıt hiç kullanılmasa bile emülasyon kodu yüklü olduğu için etkiliydi — bu, "kullanmadığım aygıt beni etkilemez" yanılgısının klasik örneğidir.

2. **Paravirtualized (PV) arayüzler ve backend'ler.** Performans için modern sistemler **virtio** (KVM/QEMU) veya Xen'in ring-buffer tabanlı PV sürücülerini kullanır. Burada misafir ve host, paylaşılan bellek üzerindeki descriptor ring'leri aracılığıyla haberleşir. Misafirin manipüle ettiği descriptor uzunlukları, offset'leri veya adresleri, host backend'inde yetersiz doğrulanırsa out-of-bounds okuma/yazma doğar. Xen tarafında **grant table** ve **event channel** mekanizmaları da tarihsel olarak birçok zafiyetin kaynağı olmuştur.

3. **Hypercall arayüzü.** Misafirin hypervisor'a doğrudan çağrı yaptığı API'dir (Xen'de belirgin, KVM'de daha çok ioctl/MSR üzerinden). Argüman doğrulama hataları, tamsayı taşmaları veya durum makinesi (state machine) hataları burada exploit edilebilir.

4. **CPU emülasyonu / komut çözücü (instruction emulator).** Bazı durumlarda hypervisor, misafir komutlarını yazılımda emüle etmek zorunda kalır (örneğin MMIO erişimlerinde). KVM'in komut emülatörü tarihsel olarak zorlu bir zafiyet kaynağı olmuştur; nadir komut kombinasyonlarında yanlış bellek erişimleri oluşabilir.

5. **Donanım/mikromimari sınır ihlalleri.** Yazılım hatası olmasa bile mimari, gizli kanallar (side channel) açabilir. **L1TF (Foreshadow)**, **MDS**, ve daha genel olarak spekülatif yürütme zafiyetleri, bir VM'in başka bir VM'in veya hypervisor'ın belleğinden veri sızdırmasına imkân tanıyabildi. Bunlar tam anlamıyla "kod çalıştırma" escape'i değildir ama izolasyon sınırını gizlilik açısından deler.

### Neden bu kadar kritik

Escape genelde tek bir hatayla olmaz; bir **zafiyet zinciri** gerektirir: (a) misafir içinde ayrıcalık, (b) hypervisor sürecinde bellek bozulması veya bilgi sızıntısı, (c) çoğu zaman ASLR'ı yenmek için ayrı bir bilgi sızıntısı, (d) host süreç bağlamında kod yürütme. Ancak host tarafındaki hypervisor süreci ele geçirildiğinde saldırgan artık **tüm komşu VM'lere** hükmeder. Ölçek etkisi budur.

## Örnek: Bir virtio Backend Zafiyetinin Anatomisi (kavramsal)

Saldırganın misafirde root olduğunu varsayalım. Kavramsal akış şöyledir:

1. Misafir, virtio-net (veya benzeri) bir aygıtın paylaşılan **virtqueue**'suna descriptor'lar yerleştirir. Descriptor, "şu adresteki şu uzunlukta tampon" der.
2. Saldırgan, host backend'in bu uzunluğu veya guest-physical adresi doğrularken yaptığı bir hataya (örn. uzunluğun tampon sınırıyla karşılaştırılmaması, ya da chained descriptor sayısının kontrol edilmemesi) güvenir.
3. Backend, misafirin belirttiği verinin peşine düşerken host adres alanında sınır dışı okuma/yazma yapar. Bu, host bellekteki fonksiyon işaretçilerini veya kontrol yapısını bozmaya kadar geliştirilebilir.
4. ASLR/DEP gibi korumaları yenmek için önce bir bilgi sızıntısı (host adreslerini öğrenme) kullanılır, sonra kontrollü yazma bir kod yürütme primitifine dönüştürülür.

Buradaki ders kavramsaldır: **misafirin sağladığı her uzunluk, offset ve adres düşman girdisidir** ve host tarafında güven sınırının dışında ele alınmalıdır. Gerçek exploit ayrıntıları (tam offset'ler, gadget'lar) yayımdan yayına değişir ve burada operasyonel olarak verilmez.

## Ana Platformların Farkları

- **QEMU/KVM.** KVM çekirdek modülü sadece CPU/bellek sanallaştırmasının donanım-yakın kısmını yapar; aygıt emülasyonunun çoğu **kullanıcı alanındaki (userspace) QEMU** sürecinde yaşar. Bu mimari savunma açısından değerlidir: QEMU süreci düşerse, doğru sertleştirilmişse etkisi o VM'e sınırlanabilir. Ancak QEMU çok geniş bir emülasyon yüzeyine sahip olduğundan tarihsel zafiyet yoğunluğu buradadır. **vhost** gibi bazı hızlandırmalar backend'i çekirdeğe taşır ve bu durumda bir zafiyet doğrudan host kernel'ini etkiler — daha tehlikeli.

- **Xen.** Type-1 (bare-metal) bir hypervisor'dır. Ayrıcalıklı **Dom0** yönetim domaini ve **hypervisor** çekirdeği ayrı güven katmanlarıdır. Xen'de hem hypervisor'ın kendi kodu (hypercall, grant table, memory management), hem de Dom0'daki aygıt emülasyonu (genelde QEMU) saldırı yüzeyidir. Xen Security Advisory (XSA) numaralarıyla izlenen çok sayıda düzeltme bu iki katmanı kapsar.

- **VMware (ESXi/Workstation).** Kapalı kaynak, olgun ve saldırı hedefi olarak yüksek değerli. Grafik/3D akselerasyonu (SVGA), USB, ve sanal aygıt katmanları tarihsel escape kaynaklarıdır; Pwn2Own gibi yarışmalarda ESXi/Workstation escape zincirleri sergilenmiştir. Yama disiplini burada kritiktir çünkü kod incelenemez.

- **Hyper-V.** Microsoft'un mimarisinde ayrıcalıklı **root partition** ve misafir **child partition**'lar vardır; VMBus üzerinden haberleşen sentetik aygıtlar ana saldırı yüzeyidir. Microsoft bu yüzeyi güçlendirmek için bazı bileşenleri daha az ayrıcalıklı kullanıcı süreçlerine (VSP/VSC ayrımı) taşımıştır.

## Tespit

VM escape'i tespit etmek zordur çünkü olayın çoğu misafirin içinde ve host süreç belleğinde geçer. Yine de anlamlı sinyaller vardır:

- **Host tarafında hypervisor süreç sağlığı.** QEMU/VMM süreçlerinin beklenmedik çökmeleri, yeniden başlamaları veya segmentation fault kayıtları güçlü bir erken uyarıdır. Bir escape denemesi, başarılı olmadan önce genellikle çok sayıda çökmeye yol açar. Host kernel log'larında (dmesg) VMM ile ilgili oops/panic, MCE (Machine Check) kayıtları izlenmelidir.
- **Beklenmedik host süreç davranışı.** VMM sürecinin normalde yapmadığı işlemler: yeni child process spawn etmesi, beklenmeyen dosya erişimleri, giden ağ bağlantıları, /proc veya cihaz dosyalarına anormal erişim. Host üzerinde **eBPF/auditd** tabanlı, VMM sürecinin syscall profilini izleyen kurallar değerlidir.
- **Seccomp ihlali sinyalleri.** QEMU seccomp-BPF ile kısıtlandığında, izin verilmeyen bir syscall denemesi süreç sonlanması ve log kaydı üretir — bu, backend'in beklenmedik davranışa zorlandığının işaretidir.
- **Misafir içi anomali.** Emüle aygıtlara yönelik olağandışı yoğun/malforme I/O, tekrarlayan aygıt reset'leri, bilinen zafiyetli aygıtları (örn. gereksiz floppy, ses, eski grafik aygıtları) yoklayan davranış.
- **Mikromimari kanallar için doğrudan tespit neredeyse yoktur;** bu tehdit yama ve konfigürasyonla (aşağıda) ele alınır, davranışsal olarak yakalanması pratik değildir.
- **Bulut kontrol düzlemi telemetrisi.** Bir tenant'ın host'unda anormal ölçüde çekirdek/hypervisor hata oranı, o host'taki bir kaçış girişiminin metriksel izidir; sağlayıcılar bunu filo genelinde toplar.

## Savunma

Savunma katmanlıdır ve tek bir denetime güvenmemek üzerine kuruludur.

### 1. Saldırı yüzeyini küçültmek
En etkili tedbir budur. Bir VM'e vermediğiniz aygıtı emüle etmeyin. QEMU başlatılırken minimal makine tipi, gereksiz aygıtların (floppy, paralel/seri portlar, ses, eski grafik) tamamen kaldırılması, mümkün olduğunda saf **virtio** aygıtlarının tercih edilmesi ideal duruştur. Kullanılmayan hypercall/paravirt özellikleri kapatılmalıdır. Yüzeyin her santimetresi potansiyel zafiyettir.

### 2. VMM sürecini hapsetmek (host-tarafı izolasyon)
KVM/QEMU'nun büyük gücü, aygıt emülasyonunun userspace'te olmasıdır — bunu sömürün:
- QEMU sürecini **ayrılmış, düşük ayrıcalıklı bir kullanıcı** olarak çalıştırın (root değil).
- **seccomp-BPF** ile syscall yüzeyini daraltın (QEMU'nun `-sandbox` desteği).
- **SELinux/AppArmor** ile zorunlu erişim denetimi uygulayın; **sVirt**, her VM'in QEMU sürecine benzersiz bir güvenlik etiketi atayarak bir escape'in komşu VM disklerine/kaynaklarına yayılmasını engellemeye çalışır.
- Süreci ayrı namespace/cgroup içinde çalıştırın, dosya sistemi görünürlüğünü kısıtlayın.
Bu katman, bir bellek bozulması zafiyeti başarılı olsa bile saldırganın kazanımını tek VM'e sınırlamayı hedefler: derinlemesine savunma.

### 3. Yama disiplini ve envanter
Escape zafiyetleri neredeyse tamamı yamayla kapanır. Hypervisor, QEMU, çekirdek KVM/Xen bileşenleri, ve **CPU mikrokodu** güncel tutulmalıdır (mikromimari zafiyetler için mikrokod ve çekirdek mitigasyonları birlikte gerekir). Hangi host'ta hangi hypervisor/QEMU sürümünün çalıştığını bilen bir envanter, bir XSA/CVE çıktığında hızlı yama için şarttır.

### 4. Mikromimari mitigasyonlar
L1TF, MDS ve benzeri sınıf zafiyetler için: ilgili çekirdek mitigasyonlarının etkin olması, gerektiğinde **SMT/Hyper-Threading'in kapatılması** (aynı fiziksel çekirdeği paylaşan iş parçacıkları arası sızıntıyı keser), ve yüksek güvenlik gereken tenant'lar için **çekirdek/host düzeyinde ayrıştırma (dedicated host / core scheduling)** düşünülür. Bunlar performansla güvenlik arasında bilinçli bir denge gerektirir.

### 5. Mimari sertleştirme ve daha küçük TCB
Modern eğilim, **Trusted Computing Base**'i küçültmektir. AWS'nin **Nitro** yaklaşımı, ağır aygıt emülasyonunu ana host CPU'sundan ayrık donanıma taşıyarak klasik QEMU saldırı yüzeyini büyük ölçüde ortadan kaldırır. Google/others tarafından geliştirilen **rust-vmm / crosvm / Firecracker** gibi minimal VMM'ler, çok az sayıda emüle aygıt sunar ve bellek-güvenli Rust ile yazılarak tüm bir zafiyet sınıfını (bellek bozulması) mimari olarak azaltmayı hedefler. Bulut altyapısı tasarlarken küçük, denetlenebilir bir VMM tercih etmek stratejik bir savunmadır.

### 6. Tenant yerleşim ve kabul edilen risk
Yüksek hassasiyetli iş yükleri için **dedicated host / bare-metal** kullanımı, komşu VM'lerin hiç var olmamasını sağlayarak cross-tenant escape riskini tanım gereği ortadan kaldırır. Bu bir sertleştirme değil, risk transferi/eliminasyonu kararıdır ve maliyetle tartılır.

## Yaygın Hatalar

- **"Container güvenliğini hallettik, sanallaştırma da güvenli" sanmak.** Bunlar farklı tehdit yüzeyleridir. Container escape çekirdek/namespace hatalarından, VM escape ise hypervisor/emülasyon hatalarından gelir. Biri diğerinin yerini tutmaz; hatta yüksek güvenlik senaryolarında container'ları VM içine koymak (gVisor, Kata Containers) ikisini birleştirir.
- **Kullanılmayan emüle aygıtları açık bırakmak.** VENOM dersinin özü: aygıtı hiç kullanmasanız da emülasyon kodu yüklüyse zafiyet aktiftir. Varsayılan makine tipleri çoğu zaman gereksiz aygıtlar içerir.
- **QEMU'yu root olarak, sandbox'sız çalıştırmak.** Bu, tek bir userspace zafiyetini doğrudan tam host ele geçirmeye çevirir ve KVM mimarisinin en büyük savunma avantajını çöpe atar.
- **Mikrokodu unutmak.** Yalnızca işletim sistemi yaması yeterli sanılır; birçok mikromimari mitigasyon çalışmak için güncel CPU mikrokoduna ihtiyaç duyar. Eksik mikrokod, etkinleştirilmiş sanılan bir korumayı sessizce işlevsiz bırakır.
- **SMT'yi ekonomik nedenlerle her yerde açık tutmak.** Çok kiracılı, güven sınırı zayıf ortamlarda Hyper-Threading, mikromimari sızıntı için birinci sınıf bir kanaldır; risk kabul edilmeden açık bırakılmamalıdır.
- **Host çökme telemetrisini izlememek.** VMM süreç çökmeleri escape denemelerinin en gürültülü ve en erken işaretidir; bu log'ları toplamamak, muhtemelen tek erken uyarıyı kaçırmak demektir.
- **Escape'i tek hata sanıp savunmayı tek katmana yaslamak.** Gerçek escape'ler zincirdir; savunma da zincirin her halkasını (yüzey küçültme + süreç hapsi + yama + mimari + yerleşim) hedeflemeli ki bir halka kırılsa bile bütün çökmesin.

## Özet

VM escape, sanallaştırmanın temel izolasyon vaadinin kırıldığı andır ve çok kiracılı bulutta tek bir zafiyetin filo ölçeğinde etki yaratmasına yol açar. Kök neden neredeyse her zaman misafir-hypervisor sınırındaki güvenilmeyen girdinin (özellikle emüle aygıtlar ve paravirt backend'ler) yetersiz doğrulanmasıdır; mikromimari kanallar ise yazılım hatası olmadan gizlilik sınırını deler. Savunma, saldırı yüzeyini küçültmek, VMM sürecini sıkıca hapsetmek (seccomp/MAC/sVirt), disiplinli yama ve mikrokod, mikromimari mitigasyonlar ve mümkünse küçük/bellek-güvenli bir VMM ile TCB'yi daraltmak üzerine kurulu, katmanlı bir yaklaşımdır. Tespit temel olarak host tarafındaki hypervisor süreç sağlığına ve davranış anomalilerine dayanır.
