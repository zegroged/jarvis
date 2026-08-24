# Bulut Tespit ve Müdahale (Cloud-Native Detection & Response)

## Giriş ve Neden Ayrı Bir Konu?

Geleneksel SIEM ve Threat Hunting pratikleri, uzun yıllar boyunca sunucu, ağ ve endpoint (uç nokta) merkezli bir dünya için tasarlandı. Ancak bulut (cloud) ve konteyner (container) tabanlı mimariler, tespit ve müdahalenin oyun kurallarını kökten değiştirdi. Artık saldırgan bir "makineyi ele geçirmek" yerine bir **API çağrısıyla** bir kaynağı oluşturabilir, yetki yükseltebilir veya veri sızdırabilir. Kalıcılık (persistence) bir servis üzerinde değil, bir IAM (Identity and Access Management) rolünde saklanır. Konteynerler ise saniyeler içinde doğup ölen, kısa ömürlü (ephemeral) varlıklardır; bir sunucuya ajan (agent) kurup log toplamaya alışkın klasik yaklaşımlar burada çalışmaz.

Bu makale, buluta özgü tespit ve müdahalenin (Cloud-Native Detection & Response) üç ana katmanını inceler:

1. **Control plane (kontrol düzlemi) tespiti**: Bulut sağlayıcının API aktivitesi — AWS CloudTrail, Azure Activity Log, GCP Audit Logs.
2. **Runtime (çalışma zamanı) tespiti**: Konteyner ve iş yükü davranışının anlık izlenmesi — Falco ve eBPF tabanlı araçlar.
3. **CDR (Cloud Detection & Response)**: Bu sinyalleri bir araya getirip bulut bağlamıyla ilişkilendiren üst katman.

Amaç, mekanizmayı anlamak ve savunma/tespit kurmaktır.

---

## Bölüm 1: Control Plane Tespiti — Bulut API Kayıtlarının Analizi

### Tanım

Her büyük bulut sağlayıcı, kimin, ne zaman, hangi kaynağa, hangi API çağrısını yaptığını kaydeden bir **denetim günlüğü (audit log)** tutar:

- **AWS**: CloudTrail
- **Azure**: Activity Log (ve daha ayrıntılı olan Azure Monitor / Entra ID sign-in logs)
- **GCP**: Cloud Audit Logs (Admin Activity, Data Access, System Event, Policy Denied kategorileri)

Bu kayıtlar, bulut ortamındaki tespit çalışmasının **birincil kaynağıdır**. Çünkü bulutta hemen her eylem — bir sanal makine başlatmaktan bir S3 bucket'ının erişim politikasını değiştirmeye kadar — bir API çağrısı olarak geçer.

### Kök Neden / Çalışma Mantığı

Bulut ortamında saldırgan, geleneksel "shell erişimi" olmadan da büyük hasar verebilir. Örneğin ele geçirilmiş bir API anahtarıyla (access key) saldırgan doğrudan control plane ile konuşur. Bu nedenle savunmacının bakması gereken yer, tek tek sunucuların içi değil, **API çağrılarının akışıdır**.

CloudTrail bir olayı JSON formatında kaydeder ve tipik olarak şu alanları içerir:

- `eventName`: Yapılan API çağrısı (ör. `CreateUser`, `AssumeRole`, `GetObject`).
- `eventSource`: Hangi servis (ör. `iam.amazonaws.com`, `s3.amazonaws.com`).
- `userIdentity`: Çağrıyı kimin/neyin yaptığı (kullanıcı, rol, servis).
- `sourceIPAddress`: Kaynak IP.
- `userAgent`: İstemci (SDK, konsol, CLI).
- `errorCode` / `errorMessage`: Başarısız denemeler (ör. `AccessDenied`).

### Örnek

Ele geçirilmiş bir kimlikle yapılan tipik bir yatay hareket ve keşif dizisi şöyle görünür:

- Saldırgan önce `GetCallerIdentity` çağırır — "ben kimim, hangi hesaptayım?" diye sorar. Bu, ele geçirdikten sonraki ilk adımdır.
- Ardından `ListUsers`, `ListRoles`, `GetAccountAuthorizationDetails` gibi çağrılarla ortamı haritalar.
- Sonra `CreateAccessKey` (başka bir kullanıcı için ikinci bir anahtar oluşturarak kalıcılık) veya `AttachUserPolicy` ile `AdministratorAccess` politikasını kendine bağlamayı dener.

Bu çağrıların her biri tek başına meşru olabilir, ama **sıralaması ve bağlamı** anomali sinyalidir.

### Tespit + Savunma

**Tespit fikirleri:**

- **Yeni IAM kimlik bilgisi oluşturma**: `CreateAccessKey`, `CreateUser`, `CreateLoginProfile` olaylarını, özellikle olağandışı bir kullanıcı tarafından yapıldığında alarmla.
- **Yetki yükseltme kalıpları**: Bir kimliğin kendisine yönetici politikası bağlaması (`AttachUserPolicy` / `PutUserPolicy` ile geniş yetki), yeni bir rol için `iam:PassRole` kullanımı.
- **Savunmayı köreltme**: `StopLogging`, `DeleteTrail` (CloudTrail'i durdurma), `DeleteFlowLogs`, `DeleteDetector` (GuardDuty'yi kapatma) — bunlar saldırganın izini kaybettirme girişimidir ve **yüksek öncelikli** alarm olmalıdır.
- **Anlık patlayan AccessDenied fırtınası**: Kısa sürede çok sayıda `errorCode: AccessDenied`, bir kimliğin yetki sınırlarını yoklayan otomatik keşif aracına işaret edebilir.
- **Alışılmadık bölge (region) aktivitesi**: Hiç kullanılmayan bir AWS bölgesinde aniden EC2 instance açılması, sıklıkla kripto madenciliği (cryptojacking) belirtisidir.
- **Olağandışı `sourceIPAddress` / coğrafya** ve **beklenmedik `userAgent`** (ör. konsol yerine ham bir SDK'dan gelen hassas çağrılar).

**GuardDuty'nin rolü**: AWS GuardDuty, CloudTrail, VPC Flow Logs ve DNS loglarını arka planda tüketip makine öğrenmesi ve tehdit istihbaratıyla hazır bulgular (findings) üretir — ör. bilinen kötü amaçlı bir IP ile iletişim, anonimleştirme servisinden (Tor) yapılan API çağrısı, kimlik bilgisi sızıntısı şüphesi. GuardDuty, kendi kuralınızı yazmadan hızlı bir taban tespit katmanı sağlar; Azure tarafında **Microsoft Defender for Cloud**, GCP tarafında **Security Command Center** benzer rolü üstlenir.

**Savunma sertleştirmesi:**

- CloudTrail'i **çoklu bölge (multi-region)** ve **organizasyon düzeyinde** açık tutun; logları ayrı, yalnızca-ekleme (append-only) yetkili bir hesaptaki S3 bucket'ına yazın ki saldırgan kendi hesabında bile silemesin.
- Log bütünlüğü doğrulaması (log file integrity validation) açık olsun.
- Kök (root) hesabı günlük işlerde asla kullanmayın; MFA zorunlu kılın ve root aktivitesini ayrıca alarmlayın.
- IAM'de en az yetki (least privilege) ilkesi; uzun ömürlü access key yerine geçici rol (temporary credentials / STS) tercih edin.

---

## Bölüm 2: Runtime Tespiti — Falco ve eBPF Tabanlı Davranışsal İzleme

### Tanım

Control plane loglarını izlemek, bir konteynerin **içinde** neler olduğunu göstermez. Bir saldırgan bir web uygulamasındaki açıktan konteynere sızıp içeride shell açtığında, CloudTrail bunu görmez. İşte burada **runtime security** devreye girer.

**Falco**, CNCF (Cloud Native Computing Foundation) altında olgunlaşmış, açık kaynaklı bir runtime tehdit tespit aracıdır. Çekirdek (kernel) düzeyinde iş yükü davranışını gözlemler ve tanımlı kurallara aykırı davranışları anlık olarak tespit eder.

### Kök Neden / Çalışma Mantığı

Falco, işletim sistemi olaylarını (özellikle **syscall** — sistem çağrıları) yakalar. Bir süreç dosya açtığında, ağ bağlantısı kurduğunda, yeni bir process spawn ettiğinde veya bir dosyaya yazdığında bunların hepsi syscall üretir. Falco bu akışı gözlemler ve kural motoruyla eşleştirir.

Bu gözlemi yapmanın iki temel yolu vardır:

- **Kernel modülü**: Klasik yöntem; çekirdeğe yüklenen bir modül syscall'ları yakalar.
- **eBPF (extended Berkeley Packet Filter)**: Modern ve tercih edilen yöntem. eBPF, Linux çekirdeği içinde, çekirdeği değiştirmeden veya yeniden derlemeden, güvenli bir sanal makinede küçük programlar çalıştırmayı sağlar. Bu programlar syscall ve diğer kernel olaylarını düşük ek yükle (overhead) izleyebilir. eBPF'in gücü, gözlemin çekirdek içinden yapılması sayesinde bir saldırganın kullanıcı alanındaki (user space) araçlarla kolayca kandıramamasıdır.

Falco'nun mantığı **davranışsaldır**: Bir imza (signature) veri tabanına değil, "şu bağlamda şu davranış normal değil" mantığına dayanır.

### Örnek: Bir Falco Kuralının Anatomisi

Falco kuralları YAML formatında yazılır ve tipik olarak bir `condition` (koşul), `output` (üretilecek uyarı metni) ve `priority` (öncelik) içerir. Kavramsal olarak bir kural şöyle okunur:

> "Eğer bir konteyner içinde interaktif bir **shell** (bash, sh) çalıştırılıyorsa ve bu konteyner normalde shell içermeyen bir uygulama konteyneriyse — bu şüphelidir, uyar."

Falco'nun hazır (default) kural setinde sık karşılaşılan tespitler:

- **"Terminal shell in container"**: Bir konteyner içinde interaktif terminal açılması. Üretimdeki (production) bir konteynerde bunun olmaması beklenir; olması, canlı bir saldırgan (interactive intrusion) işareti olabilir.
- **"Write below etc"**: `/etc` gibi hassas sistem dizinlerine yazma girişimi.
- **"Read sensitive file untrusted"**: `/etc/shadow` gibi hassas dosyaların güvenilmeyen bir süreç tarafından okunması.
- **Beklenmeyen giden ağ bağlantısı**: Bir konteynerin bilinmeyen bir dış IP'ye bağlanması (olası C2 — command and control — veya veri sızdırma).
- **Paket yöneticisi çalıştırma**: Çalışan bir konteyner içinde `apt`, `yum`, `pip` çalıştırılması — immutable (değişmez) olması beklenen bir imajda araç indirme belirtisi.

> Not: Falco kural sözdiziminin tam alan adlarını veya belirli makro/liste isimlerini birebir ezberden yazmıyorum; buradaki amaç kuralların **mantığını** anlatmaktır. Gerçek kuralları yazarken güncel Falco kural referansına bakılmalıdır.

### Tespit + Savunma

**Tespit yaklaşımı:**

- Falco'yu Kubernetes'te genellikle her düğümde (node) bir **DaemonSet** olarak çalıştırın; böylece her düğümdeki tüm konteynerlerin syscall'larını görebilir.
- Falco çıktısını (alerts) **Falcosidekick** gibi bir yönlendirici ile SIEM'e, Slack'e veya bir olay yönetim sistemine gönderin — sadece log dosyasında kalması bir tespit sistemi değildir.
- Kubernetes audit log'larını da Falco'ya besleyerek control plane olaylarını (ör. yeni `privileged` pod oluşturma) da kapsayabilirsiniz.

**Savunma sertleştirmesi (Falco'yu tamamlayan önlemler):**

- Konteynerleri **read-only root filesystem** ile çalıştırın; `/etc`'e yazma zaten engellenir.
- **Distroless** veya minimal imajlar kullanın: içinde shell, paket yöneticisi bulunmayan imajlarda "shell in container" alarmı hem daha az yanlış pozitif üretir hem de saldırganın işini zorlaştırır.
- **Least privilege** container: `privileged` konteynerlerden kaçının, gereksiz Linux capability'lerini düşürün, root olmayan kullanıcı ile çalıştırın.
- Ağ politikaları (NetworkPolicy) ile pod'ların hangi hedeflerle konuşabileceğini kısıtlayın.

---

## Bölüm 3: CDR — Cloud Detection & Response

### Tanım

**CDR (Cloud Detection & Response)**, yukarıdaki iki katmanı (control plane + runtime) ve bulut konfigürasyon/duruş (posture) verilerini tek bir bağlamda birleştiren üst kategoridir. EDR'nin (Endpoint Detection & Response) buluta özgü karşılığı olarak düşünülebilir, ancak odak noktası uç nokta değil, **bulut kimlikleri, iş yükleri ve API'leridir**.

### Kök Neden / Çalışma Mantığı

Bulut saldırıları nadiren tek bir sinyalle anlaşılır. Gerçek bir olay genellikle bir **zincir** halinde ilerler:

1. Bir konteynerdeki uygulama açığından ilk erişim (bunu Falco görebilir),
2. Konteynerin bağlı olduğu servisin IAM rolünün ele geçirilmesi (instance/pod metadata üzerinden kimlik hırsızlığı),
3. Bu rolle control plane'de keşif ve yetki yükseltme (bunu CloudTrail görebilir),
4. Veri sızdırma veya kripto madencilik kaynağı oluşturma.

CDR'nin değeri, bu ayrı sinyalleri **korelasyonla** tek bir saldırı anlatısına (attack story) dönüştürmesidir. "Şu Falco alarmı" ile "şu CloudTrail anomalisi" ayrı ayrı bakıldığında gürültü, birlikte bakıldığında net bir ihlaldir.

CDR araçlarının tipik veri kaynakları: bulut denetim logları, runtime sensörleri (Falco/eBPF veya sağlayıcının ajanı), CSPM (Cloud Security Posture Management — yanlış yapılandırma tespiti) verileri ve CIEM (Cloud Infrastructure Entitlement Management — kimlik/yetki analizi) verileri.

### Örnek: Metadata Servisi ve SSRF

Buluta özgü klasik bir saldırı zinciri, **instance metadata servisi** (AWS'de 169.254.169.254 adresindeki IMDS) üzerinden çalışır. Bir uygulamada **SSRF (Server-Side Request Forgery)** açığı varsa, saldırgan uygulamayı bu iç adrese istek yapmaya zorlayarak, sanal makineye/pod'a bağlı IAM rolünün geçici kimlik bilgilerini (temporary credentials) çalabilir. Sonra bu kimlikle doğrudan control plane'e gider.

- **Runtime katmanı** bunu, konteynerin beklenmedik bir şekilde metadata adresine bağlanması olarak görebilir.
- **Control plane katmanı** bunu, o rolün aniden dışarıdan bir IP'den API çağrısı yapması olarak görebilir.
- **CDR**, ikisini birleştirip "çalınan pod kimliği ile control plane erişimi" tespitini üretir.

**Savunma**: AWS'de **IMDSv2** (oturum-tabanlı, ek başlık ve hop limiti gerektiren sürüm) zorunlu kılmak bu zincirin ilk halkasını büyük ölçüde kırar; ayrıca pod'lara metadata erişimini ağ düzeyinde kısıtlamak da etkilidir.

### Tespit + Savunma (Genel CDR Prensipleri)

- **Kimlik-merkezli tespit**: Bulutta yeni çevre (perimeter) kimliktir. "Bu kimlik daha önce hiç bu servisi/bölgeyi kullandı mı?" sorusu, IP tabanlı tespitten daha değerlidir.
- **Baseline (temel davranış) çıkarma**: Her rol/kullanıcı için normal davranış profili oluşturup sapmaları yakalamak.
- **Otomatik müdahale (response)**: Tespit yeterli değildir; CDR'nin "R" harfi müdahaledir. Örnek otomatik aksiyonlar: şüpheli access key'i devre dışı bırakma, ele geçmiş pod'u izole etme (network quarantine), oturumu iptal etme (session revocation). Bunlar genellikle olay yönetimi/SOAR akışlarıyla tetiklenir.

---

## Yaygın Hatalar

- **"CloudTrail açık, iş bitti" yanılgısı**: Log toplamak tespit değildir. Kural, korelasyon ve alarm olmadan log sadece adli inceleme (forensics) için bekler. Ayrıca **Data Events** (ör. S3 nesne düzeyi `GetObject`) varsayılan olarak kapalı olabilir; veri sızdırmayı görmek için bunları ayrıca açmak gerekir.
- **Runtime'ı atlayıp yalnızca konfigürasyona bakmak**: CSPM ile yanlış yapılandırmaları bulmak önemlidir ama **canlı saldırıyı** görmez. Duruş yönetimi (önleme) ile runtime tespit (yakalama) birbirini tamamlar, biri diğerinin yerini tutmaz.
- **Falco alarmlarını hiçbir yere yönlendirmemek**: Alarm sadece konteyner log'unda kalıyorsa kimse görmez. Falcosidekick benzeri bir çıkış ve merkezi bir alarm hedefi şarttır.
- **Yanlış pozitif yorgunluğu (alert fatigue)**: Falco'nun hazır kurallarını hiç ayarlamadan (tuning) çalıştırmak, meşru bakım işlemlerinden (deploy, debug) dolayı alarm bombardımanı yaratır. Ekip bir süre sonra alarmları görmezden gelir. Ortama özgü **exception/allowlist** tanımlamak kritiktir — ama bunu yaparken saldırganın kaçış deliği açmamaya dikkat edilmelidir.
- **GuardDuty/Defender'a körü körüne güvenmek**: Bunlar iyi bir taban sağlar ama her şeyi görmez; ortama özgü kurallar ve runtime katmanı ile tamamlanmalıdır.
- **Logların saldırgan tarafından silinebilmesi**: Loglar üretildikleri hesapta/aynı yetki alanında tutuluyorsa, control plane'i ele geçiren saldırgan bunları silebilir. Logları ayrı, sıkı yetkilendirilmiş, değişmez bir hedefe akıtmak temel bir olgunluk göstergesidir.
- **Kısa ömürlü konteynerleri gözden kaçırmak**: Saniyeler yaşayan bir pod'da olay yaşanıp pod ölürse, yalnızca periyodik tarama yapan araçlar hiçbir şey görmez. Runtime izleme sürekli ve olay-anlık (event-driven) olmalıdır.
- **Zaman ve kimlik bağlamını ihmal etmek**: Bulut loglarında saatler UTC'dir ve `AssumeRole` zincirleri kimliği maskeler. Kimin "gerçekte" hareket ettiğini çözmek için rol zincirini (role chaining) takip etmek gerekir.

---

## Özet

Buluta özgü tespit ve müdahale, üç katmanın birlikte çalışmasıdır: **control plane** (CloudTrail / Azure Activity Log / GCP Audit Logs ve GuardDuty gibi yönetilen servisler) ile "kim ne API çağrısı yaptı"yı; **runtime** (Falco ve eBPF) ile "konteynerin içinde ne oluyor"u; ve **CDR** ile bu sinyalleri kimlik-merkezli bir bağlamda birleştirip müdahaleyi görürüz. Temel zihniyet değişikliği şudur: Bulutta savunmacının baktığı yer artık sunucunun içi değil, **API akışı ve kimlik davranışıdır**. En az yetki, değişmez altyapı, ayrı ve silinemez loglama ve sürekli davranışsal izleme, bu modelin dört ayağıdır.
