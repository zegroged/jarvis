# GPU Programlama ve Paralel Hesaplama (CUDA/OpenCL, SIMD, Heterojen Bellek Modelleri)

## Giriş: Neden Bu Konu Sistem Güvenliği İçin Önemli

Modern makine öğrenmesi altyapısının, oyun motorlarının ve bilimsel hesaplamanın neredeyse tamamı GPU üzerinde çalışır. Bir mühendis CPU tarafında buffer overflow, race condition veya privilege escalation kavramlarına aşina olabilir; ama GPU tamamen farklı bir yürütme modeli kullanır ve bu model kendine özgü hata sınıfları, kendine özgü side-channel yüzeyleri ve kendine özgü savunma gereksinimleri doğurur. Bir ML altyapısını (örneğin çok kiracılı bir "GPU cluster" veya bulut GPU kirası) güvenli tasarlamak isteyen biri, önce GPU'nun *nasıl* çalıştığını anlamak zorundadır; aksi halde "izolasyon" gibi kelimeler boş laf olarak kalır. Bu makale önce yürütme ve bellek modelini derinlemesine anlatır, sonra bunun üzerine inşa edilen güvenlik/tespit düşüncesini ekler.

## Temel Yürütme Modeli: SIMT ve Warp Kavramı

CPU'da bir çekirdek (core) bağımsız bir kontrol akışı yürütür: kendi program sayacı (program counter), kendi dallanma (branch) kararı vardır. GPU ise SIMT (Single Instruction, Multiple Threads) modelini kullanır: NVIDIA mimarisinde 32 thread'lik bir grup ("warp"), AMD'de 32 veya 64 thread'lik grup ("wavefront") aynı anda **aynı komutu** yürütür, farklı veri üzerinde. Bu, klasik SIMD'nin (Single Instruction, Multiple Data — CPU'daki AVX/SSE vektör birimleri gibi) bir varyasyonudur, ama SIMT programcı açısından skaler kod yazıyormuş hissi verir; donanım bunu arka planda vektörleştirir.

Kök neden burada kritik: bir warp içindeki 32 thread fiziksel olarak tek bir kontrol biriminden (instruction fetch/decode) beslenir. Eğer kod içinde bir `if` dalı varsa ve warp'taki bazı thread'ler `true`, bazıları `false` yolunu almak zorundaysa, donanım **her iki dalı da sırayla yürütür**, uygun olmayan thread'leri bir "execution mask" ile susturur (predication). Buna **warp divergence** (thread divergence) denir. Sonuç: divergent kod, o warp için efektif olarak seri hale gelir — paralellik kazancı kaybolur, çünkü donanım aynı çevrimde farklı talimat çalıştıramaz.

### Neden Önemli: Performans ve Güvenlik Kesişimi

Warp divergence sadece bir performans sorunu değildir; aynı zamanda bir **timing side-channel** kaynağıdır. Eğer bir kernel'in çalışma süresi, gizli bir veriye (örneğin bir şifreleme anahtarının bitlerine) bağlı olarak farklı dallara giriyorsa, dışarıdan ölçülebilen toplam yürütme süresi o gizli veri hakkında bilgi sızdırabilir. CPU dünyasında bu constant-time kriptografi tartışmasının (branch-free karşılaştırma, sabit-zamanlı AES vb.) tıpatıp aynısı, ama GPU'da etkisi warp genelinde katlanarak büyür: tek bir thread'in aldığı dal değil, warp'taki thread'lerin *dağılımı* zamanlamayı belirler.

**Savunma prensibi:** GPU üzerinde çalışan kriptografik veya gizlilik-kritik kernel'lerde dallanmayı veriye bağımlı hale getirmemek, bunun yerine aritmetik/maskeleme tabanlı (branchless) teknikler kullanmak gerekir. Ayrıca shared GPU ortamlarında (bulut kiralama, çok kullanıcılı ML servisleri) kernel çalışma süreleri dışarıdan ölçülebiliyorsa, bu bir bilgi sızıntısı kanalı olarak değerlendirilmelidir.

## Bellek Hiyerarşisi ve Heterojen Bellek Modelleri

GPU programlamanın en çok kafa karıştıran ve en çok hataya yol açan yanı bellek hiyerarşisidir. CPU'da tek bir "düz" adres uzayı varmış gibi düşünülür (sanal bellek soyutlaması arkasında); GPU'da ise programcı farklı bellek türlerini **açıkça** yönetmek zorundadır:

- **Global memory (device memory):** GPU'nun kendi DRAM'i (VRAM). Büyük, ama yüksek gecikmeli (latency). Tüm thread'ler erişebilir.
- **Shared memory (local memory / LDS):** Bir thread block'u (CUDA) ya da work-group'u (OpenCL) içindeki thread'lerin ortak kullandığı, çip-üzeri (on-chip), çok düşük gecikmeli, ama küçük kapasiteli bellek. Programcı tarafından elle yönetilen bir "scratchpad" gibidir — donanım cache'i değildir, yazılım önbelleğidir.
- **Registers:** Her thread'e özel, en hızlı katman. Kernel'in kullandığı register sayısı, aynı anda kaç warp'ın aktif olabileceğini (occupancy) sınırlar.
- **Constant / texture memory:** Salt okunur, cache'lenmiş, özel erişim desenleri için optimize edilmiş bölgeler.
- **Host memory (CPU RAM):** GPU'nun doğrudan erişemediği (unified memory özellikleri hariç), PCIe/NVLink üzerinden kopyalanması gereken ayrı bir adres uzayı.

### Heterojen Bellek Modeli Neden Karmaşık

"Heterojen" kelimesi burada anahtar: CPU (host) ve GPU (device) **fiziksel olarak ayrı bellek** kullanır (discrete GPU'larda). Veri, PCIe veya NVLink üzerinden kopyalanmak zorundadır; bu kopyalama hem bir performans darboğazı hem de bir tutarlılık (coherency) sorunudur. `cudaMemcpy` gibi bir çağrı yapılana kadar host'taki değişiklikler device'a, device'taki sonuçlar host'a otomatik yansımaz. Modern sistemler "unified memory" (CUDA'da `cudaMallocManaged`) ile bunu programcıya soyutlar, ama alt seviyede hâlâ sayfa hatası (page fault) tabanlı göç (migration) mekanizması çalışır — sihir yoktur, sadece gizlenmiş maliyet vardır.

**Kök neden / tuzak:** Birçok güvenlik açığı ve doğruluk hatası, "host ve device'in aynı belleği gördüğü" yanlış varsayımından kaynaklanır. Örneğin bir kernel çalışırken host tarafında aynı belleği okumaya çalışmak (senkronizasyon olmadan) tanımsız davranıştır (undefined behavior) — race condition'in GPU versiyonu. Savunma: her zaman açık senkronizasyon noktaları (`cudaDeviceSynchronize`, event/stream tabanlı senkronizasyon, OpenCL'de `clFinish`/event nesneleri) kullanmak ve "hangi belleğin ne zaman geçerli olduğunu" kod içinde açıkça belgelemek.

## CUDA ve OpenCL: Programlama Modeli Karşılaştırması

CUDA (NVIDIA'ya özel) ve OpenCL (açık standart, çoklu satıcı) benzer kavramsal modeli farklı terminolojiyle sunar:

| Kavram | CUDA | OpenCL |
|---|---|---|
| Çalışma birimi | Thread | Work-item |
| Grup | Block | Work-group |
| Tüm grid | Grid | NDRange |
| Çip-üzeri bellek | Shared memory | Local memory |
| Çekirdek fonksiyon | Kernel (`__global__`) | Kernel (`__kernel`) |

İkisinin de temel çalışma mantığı aynı: çok sayıda hafif thread'i binlerce/milyonlarca kez aynı kodu (kernel) farklı veri parçaları üzerinde çalıştırmak için başlatmak (launch). Fark, CUDA'nın NVIDIA donanımına sıkı bağlı olup daha derin donanım kontrolü (örneğin tensor core'lara doğrudan erişim, PTX assembly seviyesine inme) sunması; OpenCL'in ise donanım-bağımsız olup Intel/AMD/NVIDIA/FPGA gibi farklı hedeflerde çalışabilmesidir — bu taşınabilirlik genelde ince ayar (tuning) esnekliğinden feragat anlamına gelir.

### Doğru Kullanım ve En İyi Pratikler

1. **Coalesced memory access (birleşik bellek erişimi):** Bir warp'taki 32 thread, global memory'den ardışık ve hizalanmış adreslere erişiyorsa donanım bunları tek bir işlemde birleştirir. Rastgele veya dağıtık erişim, her thread için ayrı bellek işlemi anlamına gelip ciddi performans kaybına yol açar. Bu sadece hız meselesi değil — kötü tasarlanmış erişim desenleri, GPU'yu "görünmez" şekilde aşırı işli hale getirip DoS benzeri kaynak tükenmesine de zemin hazırlayabilir çok kiracılı sistemlerde.
2. **Bank conflict:** Shared memory, paralel erişim için bankalara (banks) bölünmüştür. Aynı bankaya aynı anda birden fazla thread erişmeye çalışırsa erişimler serileşir (serialize). Veri yapılarını banka sayısına göre (tipik olarak 32) hizalamak/padding eklemek performans için önemlidir.
3. **Occupancy yönetimi:** Register ve shared memory kullanımını aşırı artırmak, aynı anda çalışabilecek warp sayısını düşürür; bu da gecikmeyi (latency) gizleme kapasitesini azaltır. Denge, kernel'e göre deneysel olarak (profiling ile) bulunmalıdır.
4. **Senkronizasyon doğruluğu:** `__syncthreads()` (CUDA) veya `barrier()` (OpenCL) gibi block-seviyesi bariyerler, tüm thread'lerin aynı noktaya varmasını garanti eder — ama bunlar **koşullu dallar içinde** (bazı thread'ler bariyere ulaşırken bazıları ulaşmazsa) kullanılırsa deadlock veya tanımsız davranışa yol açar. Bariyerin, warp/block içindeki tüm thread'lerce ulaşılabilir olduğundan emin olunmalıdır.

### Yaygın Hatalar

- **Race condition (device-level):** Birden fazla thread'in senkronizasyon olmadan aynı global/shared bellek adresine yazması. CPU'daki race condition'in doğrudan analoğudur, ama ölçek çok daha büyüktür (binlerce eş zamanlı thread).
- **Bellek dışı erişim (out-of-bounds access):** Kernel'lerde sınır kontrolü (bounds check) atlanırsa, GPU bellek koruma modeli CPU kadar granüler olmayabilir; bu durum sessiz veri bozulmasına veya, bazı mimarilerde, komşu bellek bölgelerinin okunmasına/yazılmasına yol açabilir — klasik buffer overflow mantığının GPU bağlamındaki karşılığı.
- **Host-device senkronizasyon eksikliği:** Kernel launch'ları varsayılan olarak asenkrondur (host, kernel bitmeden bir sonraki satıra geçer). Sonucu okumadan önce senkronize etmemek, "eski veri" okuma hatasına (stale read) yol açar.
- **Hatalı hata kontrolü:** CUDA/OpenCL API çağrıları hata kodu döndürür ama kernel launch hataları genelde **asenkron** olarak raporlanır (bir sonraki senkronizasyon noktasında ortaya çıkar). Hata kontrolünü atlamak, sessizce yanlış sonuç üretmeye (silent corruption) yol açar — güvenlik açısından da tehlikelidir çünkü bir saldırı/anormallik "sessizce" görünmez kalabilir.

## Güvenlik Yüzeyi: GPU'ya Özgü Tehdit Modelleri

### 1. Bellek İzolasyonu ve Çok Kiracılı (Multi-Tenant) Riskler

Bulut ortamlarında aynı fiziksel GPU birden fazla kiracı (VM, konteyner, veya aynı makinedeki farklı kullanıcı süreçleri) tarafından zaman paylaşımlı veya MIG (Multi-Instance GPU) gibi bölümlemeyle paylaşılabilir. Kök risk: GPU bellek yöneticisi ve sürücü (driver) katmanı, CPU tarafındaki işletim sistemi kadar olgun izolasyon mekanizmalarına (örneğin sayfa tablosu tabanlı tam izolasyon, ASLR benzeri önlemler) her zaman aynı olgunlukta sahip olmayabilir. Önceki kiracının GPU global memory'de bıraktığı veriler, eğer tahsis (allocation) sonrası bellek sıfırlanmıyorsa, yeni kiracı tarafından okunabilir hale gelebilir — bu **"bellek artığı" (memory residue) sızıntısı** olarak bilinen bir sınıf sorundur, CPU dünyasındaki "uninitialized memory disclosure" hatalarının doğrudan karşılığıdır.

**Tespit/savunma:** Kiracılar arası GPU tahsisinde belleğin sıfırlanıp sıfırlanmadığını doğrulamak, sağlayıcının (cloud provider) izolasyon garantilerini (MIG, tam sanallaştırma vGPU vb.) anlamak, ve mümkünse kendi uygulama katmanında hassas veriyi iş bitince açıkça sıfırlamak (`cudaMemset` ile temizleme) iyi bir savunma katmanıdır.

### 2. Mikromimari Side-Channel'lar

CPU dünyasında bilinen cache-timing (Spectre/Meltdown ailesi) ve benzeri mikromimari sızıntı sınıflarının GPU karşılıkları da araştırma literatüründe gösterilmiştir: paylaşılan GPU çekirdeklerinde bellek erişim zamanlaması veya kaynak çekişmesi (contention) üzerinden, aynı GPU'yu paylaşan farklı süreçler/kiracılar arasında bilgi sızabileceği gösterilmiştir. Burada spesifik CVE numaralarını veya kesin sürümleri vermek yanlış olur — bu, aktif araştırılan ve donanım/sürücü satıcı tarafından sürekli yamalanan bir alandır. Önemli olan **kavram**: paylaşılan donanım kaynağı = potansiyel yan kanal. GPU'da bu kaynaklar arasında L2 cache, bellek denetleyici (memory controller) bant genişliği, ve güç/ısı tabanlı (power/thermal) sınırlamalar sayılabilir.

**Savunma prensibi:** Gerçekten hassas iş yüklerini (örneğin çok kiracılı ortamda çalışan gizli anahtar işlemleri) mümkünse ayrılmış (dedicated) donanımda çalıştırmak, sağlayıcının güvenlik danışmanlıklarını (security advisories) takip etmek, ve "aynı fiziksel GPU'yu paylaşmak = tam izolasyon" varsayımından kaçınmaktır.

### 3. Kernel Kodu Enjeksiyonu ve Girdi Doğrulama

CUDA/OpenCL kernel'leri, host tarafından gönderilen parametrelerle çalışır. Eğer bir uygulama, kullanıcıdan gelen boyut/indeks değerlerini doğrudan kernel launch parametrelerine (grid/block boyutları, bellek offsetleri) doğrulama yapmadan geçiriyorsa, bu klasik bir **girdi doğrulama (input validation)** eksikliğidir ve out-of-bounds erişimlere, hatta bazı senaryolarda kernel'in bellek dışına yazarak sürücü/sistem kararlılığını bozmasına (crash, DoS) yol açabilir. Ayrıca bazı çerçevelerde (örneğin JIT ile derlenen kernel kodu — OpenCL'in çalışırken kaynaktan derlemesi gibi) dinamik olarak inşa edilen kernel kaynak kodunun içine güvenilmeyen veri enjekte edilmesi, bir tür kod enjeksiyonu riski doğurabilir (SQL injection'in derleme-zamanı/kernel-kaynağı analojisi).

**Savunma:** Kernel'e giden tüm boyut/indeks parametrelerini host tarafında doğrulamak, JIT-derlenen kernel kaynağı oluşturuluyorsa kullanıcı girdisini asla doğrudan kaynak koduna string-birleştirme (string concatenation) ile eklememek, parametrize/şablon tabanlı yaklaşımlar kullanmak.

### 4. Denial of Service ve Kaynak Tüketimi

GPU'lar, uzun süren veya sonsuz döngüye giren kernel'ler yüzünden tüm sistemi (özellikle GUI/display bağlantılı GPU'larda) yanıt vermez hale getirebilir ("watchdog timeout" koruması bazı platformlarda vardır, ama tüm ortamlarda garanti değildir — özellikle headless compute GPU'larında watchdog kapalı olabilir). Çok kiracılı bir ML servisinde, kötü niyetli veya hatalı bir kullanıcı kernel'i, aşırı uzun çalışan veya aşırı bellek talep eden bir iş yükü gönderip diğer kiracıların GPU'ya erişimini engelleyebilir.

**Savunma:** Kernel çalışma süresi ve bellek tahsisi için uygulama-seviyesi kotalar/zaman aşımları (timeout) koymak, zamanlama adaletini (scheduling fairness) sağlayan bir kuyruklama katmanı kullanmak, ve anormal derecede uzun süren işleri izlemek (monitoring/alerting).

## Tespit ve İzleme (Detection) Yaklaşımları

Savunma amaçlı bir mühendis için pratik tespit noktaları:

- **Profiling araçları** (NVIDIA Nsight, `nvidia-smi`, ROCm tarafında `rocm-smi` benzeri araçlar) ile GPU kullanım oranlarını, bellek tahsislerini ve çalışma sürelerini sürekli izlemek; beklenmedik/anormal desenler (ani bellek tüketim artışı, süreklilik gösteren yüksek işgal oranı, açıklanamayan uzun kernel süreleri) erken uyarı sinyali olabilir.
- **Bellek tahsis denetimi:** Uygulama katmanında, kiracılar arası geçişlerde bellek havuzunun (memory pool) sıfırlanıp sıfırlanmadığını test etmek (örneğin yeni tahsis edilen belleği okuyup beklenmedik sıfır-dışı veri olup olmadığına bakmak — kontrollü bir test ortamında).
- **Zamanlama varyansı analizi:** Kriptografik veya gizlilik-kritik kernel'lerin çalışma süresinin, girdiye bağlı olarak istatistiksel olarak değişip değişmediğini ölçmek (bir tür kendi kendine side-channel denetimi).
- **Sürücü ve firmware güncel tutma:** GPU sürücü/firmware katmanı, mikromimari zafiyetlerin çoğunlukla yamalandığı yerdir; güncel tutulmamış sürücü, bilinen sızıntı sınıflarına karşı savunmasız kalır.

## Sonuç

GPU programlama, CPU'dan kökten farklı bir yürütme (SIMT/warp) ve bellek (heterojen, elle yönetilen hiyerarşi) modeline dayanır. Bu farklılık iki yönlü sonuç doğurur: bir yandan warp divergence, coalescing, occupancy gibi CPU'da karşılığı olmayan performans kavramlarını anlamayı gerektirir; diğer yandan da bu aynı mekanizmalar (paylaşılan donanım, asenkron yürütme, elle yönetilen bellek, çoklu-kiracılı paylaşım) kendine özgü bir güvenlik yüzeyi (timing side-channel, bellek artığı sızıntısı, girdi doğrulama açığı, DoS) yaratır. Savunma yaklaşımı CPU dünyasındaki temel ilkelerin (girdi doğrulama, sabit-zamanlı hesaplama, kaynak kotalama, bellek temizleme) GPU'nun kendine özgü yürütme modeline uyarlanmasıdır — kopyala-yapıştır değil, mekanizmayı anlayarak yeniden düşünerek.
