# Kubernetes Güvenliği: RBAC, Pod Security, Secrets, Ağ Politikaları ve Saldırı Yolları

## Giriş: Neden Kubernetes Güvenliği Kendine Özgü Bir Disiplindir

Kubernetes, konteynerleştirilmiş uygulamaları ölçekli biçimde çalıştırmak için tasarlanmış bir orkestrasyon sistemidir. Ancak güvenlik açısından bakıldığında Kubernetes tek bir "sunucu" değil; birbirine güvenen bir dizi dağıtık bileşenin (API server, etcd, kubelet, scheduler, controller-manager) oluşturduğu, üstelik varsayılan ayarlarının çoğu zaman **kullanılabilirlik lehine, güvenlik aleyhine** dengelendiği bir platformdur.

Buradaki kök sorun şudur: geleneksel güvenlik modelinde savunma çevresi (perimeter) makinenin kendisidir. Kubernetes'te ise güvenlik sınırı bulanıklaşır. Bir pod içindeki uygulamanın ele geçirilmesi, doğru yapılandırılmamışsa, tüm cluster'ın ele geçirilmesine giden bir zincirin ilk halkası olabilir. Bu yüzden Kubernetes güvenliği tekil bir ayar değil, **katmanlı bir savunma (defense in depth)** meselesidir: kimlik doğrulama, yetkilendirme, pod izolasyonu, sır (secret) yönetimi ve ağ segmentasyonu birbirini tamamlar. Bir katman çökerse diğerinin devreye girmesi beklenir.

Bu makale beş kritik alanı ele alıyor: RBAC (yetkilendirme), pod security (çalışma zamanı izolasyonu), secrets (hassas veri), network policy (ağ segmentasyonu) ve tüm bunların üzerinden geçen tipik saldırı yolları.

---

## 1. RBAC (Role-Based Access Control): Kim Neyi Yapabilir

### Tanım ve Çalışma Mantığı

RBAC, Kubernetes API'sine gelen her isteğin **yetkilendirme** aşamasıdır. Bir istek önce kimlik doğrulamadan (authentication: "sen kimsin") geçer, sonra RBAC yetkilendirmesine (authorization: "sen bunu yapabilir misin") tabi tutulur. RBAC dört temel nesneyle çalışır:

- **Role**: Belirli bir namespace içindeki kaynaklar üzerinde izin kümesi tanımlar.
- **ClusterRole**: Tüm cluster genelinde ya da namespace bağımsız kaynaklar (node, persistentvolume gibi) üzerinde izin tanımlar.
- **RoleBinding**: Bir Role'ü bir özneye (kullanıcı, grup ya da ServiceAccount) bağlar.
- **ClusterRoleBinding**: Bir ClusterRole'ü cluster genelinde bir özneye bağlar.

İzinler **toplamsal (additive)** ve **beyaz liste** mantığıyla çalışır: varsayılan olarak hiçbir şeye izin yoktur, siz açıkça izin verirsiniz. RBAC'te "deny" (yasakla) kuralı yoktur; bir şeyi yasaklamanın tek yolu ona izin vermemektir. Bu tasarım, "unutulan bir deny kuralı yüzünden güvenlik açığı" riskini ortadan kaldırır ama karşılığında **fazla verilen bir izni fark etmek zorlaşır**, çünkü sistem size "bu çok geniş" demez.

### Kök Neden: Neden RBAC Yanlış Yapılandırılır

RBAC hatalarının kökeninde genellikle iki dürtü vardır. Birincisi, geliştirme sırasında "çalışsın da nasıl çalışırsa çalışsın" yaklaşımıyla geniş izinler verilmesi ve bunların prodüksiyona taşınması. İkincisi, `verbs` ve `resources` alanlarında `*` (wildcard) kullanımının cazip kolaylığıdır. `resources: ["*"]` ve `verbs: ["*"]` yazmak, tek tek izin listelemekten daha hızlıdır ama bu, öznenin cluster üzerinde neredeyse sınırsız yetki kazanması demektir.

### Somut Örnek: Görünüşte Masum, Aslında Ölümcül Bir Yetki

Düşünün ki bir ServiceAccount'a şu izinler verilmiş:

```yaml
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["create"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list"]
```

Bu masum görünür: "pod oluşturabiliyor ve secret okuyabiliyor". Ancak **pod oluşturma yetkisi Kubernetes'te en tehlikeli izinlerden biridir**. Çünkü bu özne, istediği bir imajı, istediği bir ServiceAccount ile, istediği volume mount'larla çalıştıran bir pod tanımlayabilir. Örneğin node'un dosya sistemini `hostPath` ile mount eden ya da daha yetkili başka bir ServiceAccount'un token'ını kullanan bir pod yaratıp, o token üzerinden yetki yükseltebilir. Secret okuma yetkisiyle birleştiğinde ise saldırgan cluster genelindeki kimlik bilgilerini toplayabilir.

### Sömürü Mantığı (Saldırganın Bakışı)

Saldırgan, ele geçirdiği bir pod'un içinde `/var/run/secrets/kubernetes.io/serviceaccount/token` yolunda bir ServiceAccount token'ı bulur. Bu token ile API server'a sorgu atarak "ben ne yapabiliyorum" diye keşif yapar (`kubectl auth can-i --list` bunun meşru karşılığıdır). Eğer token'da geniş izinler varsa — özellikle `pods/exec`, `pods/create`, secret erişimi, ya da RBAC nesnelerini (`roles`, `rolebindings`) düzenleme izni — saldırgan bunları zincirleyerek yetki yükseltir. En kritik anti-pattern, bir öznenin kendi izinlerini artıracak RBAC nesneleri oluşturmasına (`escalate` ve `bind` verb'leri, ya da rolebinding create izni) sahip olmasıdır; bu doğrudan cluster-admin'e giden bir kaçış yoludur.

### Savunma Mantığı

Savunmanın temeli **en az yetki (least privilege)** ilkesidir: her ServiceAccount yalnızca işini yapması için gereken izne sahip olmalı. Somut olarak:

- Wildcard (`*`) kullanımından kaçının; `resources` ve `verbs` alanlarını açıkça listeleyin.
- `cluster-admin` gibi hazır güçlü ClusterRole'leri neredeyse hiç doğrudan bind etmeyin.
- Namespace'lere Role/RoleBinding'le sınırlı kalın; ClusterRoleBinding'i istisna olarak kullanın.
- Düzenli olarak RBAC'i denetleyin. `kubectl auth can-i` ile "bu özne şunu yapabilir mi" testleri yapın; açık kaynaklı analiz araçları (rbac odaklı görselleştiriciler) fazla geniş bindingleri tespit etmede yardımcı olur.
- `escalate`, `bind`, `impersonate` gibi meta-izinleri yalnızca gerçekten gereken yönetim hesaplarına verin.

---

## 2. Pod Security: Çalışma Zamanı İzolasyonu

### Tanım ve Kök Neden

Konteynerler sanal makine değildir. Bir konteyner, aynı Linux çekirdeğini (kernel) diğer konteynerlerle ve host ile **paylaşır**; izolasyon namespaces ve cgroups gibi çekirdek özellikleriyle sağlanır. Bu şu anlama gelir: konteyner izolasyonundaki bir kaçış (container escape), doğrudan host'a erişim demektir. Pod security'nin varlık nedeni tam da budur — konteynerin çekirdek ile temas yüzeyini daraltmak.

Kubernetes bir dönem bunu **PodSecurityPolicy (PSP)** ile yönetiyordu; ancak PSP karmaşıklığı ve tasarım sorunları nedeniyle kaldırıldı. Yerine daha basit, üç seviyeli (`privileged`, `baseline`, `restricted`) bir yerleşik mekanizma olan **Pod Security Admission (PSA)** getirildi. PSA, namespace düzeyinde etiketlerle uygulanır ve podları bu standartlara göre `enforce`, `audit` veya `warn` modlarında değerlendirir.

### Tehlikeli Ayarlar ve Neden Tehlikeli Oldukları

Pod güvenliğinde en kritik alan `securityContext`'tir. En sık istismar edilen zayıf ayarlar:

- **`privileged: true`**: Konteynere neredeyse host root'una eşdeğer yetki verir. Tüm cihazlara erişim, çekirdek yeteneklerinin (capabilities) tamamı açılır. Bu ayar, container escape'i "zor bir saldırı" olmaktan çıkarıp "önemsiz bir adım" haline getirir.
- **`hostPID`, `hostNetwork`, `hostIPC`**: Konteyneri host'un process, ağ veya IPC namespace'ine yerleştirir. `hostPID` ile saldırgan host üzerindeki diğer süreçleri görür ve bazı durumlarda bunlara müdahale edebilir; `hostNetwork` ile host'un ağ arayüzlerine ve localhost'a bağlı servislerine (örneğin kubelet API'sine) doğrudan erişir.
- **`hostPath` volume**: Host dosya sisteminin bir bölümünü (kötü senaryoda `/` kök dizinini) konteynere mount eder. Saldırgan bununla host'un dosyalarını okuyabilir/yazabilir, hatta `/var/run/docker.sock` benzeri bir soketi mount ederse doğrudan runtime'ı kontrol edebilir.
- **`allowPrivilegeEscalation: true`** ve gereksiz eklenmiş **capabilities** (örneğin `SYS_ADMIN`): Konteyner içinde yetki yükseltmeyi mümkün kılar.
- **Root olarak çalışma (`runAsNonRoot` ayarlanmamış)**: Konteyner içindeki UID 0, bir escape durumunda host'ta da avantaj sağlar.

### Somut Örnek: hostPath ile Node Ele Geçirme

Saldırgan, RBAC'te pod oluşturma yetkisi kazandıysa şöyle bir pod tanımlayabilir: `hostPath` ile host'un kök dizinini `/host` altına mount eden, `privileged: true` işaretli bir konteyner. Pod çalıştığında saldırgan `/host` üzerinden node'un dosya sistemine tam erişim kazanır — node'daki kubelet'in kimlik bilgilerini, diğer podların secret'larını, hatta cluster'a giriş sağlayan kubeconfig'leri okuyabilir. Bu, tek bir pod'dan tüm node'a, oradan cluster'a giden klasik saldırı zinciridir.

### Savunma Mantığı

- Namespace'lere PSA etiketlerini uygulayın; hassas iş yükleri için `restricted` profilini `enforce` modunda çalıştırın. `restricted`, root olmayan kullanıcı, salt okunur root dosya sistemi, düşürülmüş capabilities ve privilege escalation kapalı gibi kısıtları zorlar.
- `securityContext`'te şu ayarları standart yapın: `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities: drop: ["ALL"]` (yalnızca gerekenleri geri ekleyin).
- `hostPath`, `hostNetwork`, `hostPID`, `privileged` kullanımını ilke olarak yasaklayın; gerçekten gereken istisnaları (örneğin bir CNI ya da monitoring ajanı) belgeleyerek ve izole namespace'lerde tutun.
- Çekirdek düzeyinde ek sertleştirme için **seccomp** (sistem çağrılarını kısıtlar), **AppArmor** veya **SELinux** profillerini devreye alın. `seccomp: RuntimeDefault` bile birçok tehlikeli sistem çağrısını kapatır.
- Politika zorlaması için admission controller tabanlı policy motorları (OPA/Gatekeeper ya da Kyverno gibi) kullanarak PSA'nın yakalamadığı özel kuralları uygulayın.

---

## 3. Secrets: Hassas Verinin Yönetimi

### Tanım ve Kritik Bir Yanlış Anlama

Kubernetes'te `Secret` nesnesi, parolalar, token'lar, TLS anahtarları gibi hassas verileri saklamak için tasarlanmış bir kaynaktır. Buradaki en yaygın ve tehlikeli yanlış anlama şudur: **Secret'lar varsayılan olarak şifrelenmez, yalnızca base64 ile kodlanır.** base64 bir şifreleme değil, tersine çevrilebilir bir kodlamadır. `echo <deger> | base64 -d` ile herkes içeriği okur. Yani base64, "gözden kaçmasın" dışında hiçbir güvenlik sağlamaz.

### Kök Neden: Secret'lar Nerede ve Nasıl Sızar

Secret'lar birden fazla noktada risk altındadır:

1. **etcd'de bekleme (at rest)**: Tüm Kubernetes durumu (secret'lar dahil) etcd'de saklanır. Varsayılan kurulumların çoğunda etcd'deki veri şifrelenmez. etcd'ye erişebilen (ya da etcd yedeğini ele geçiren) biri tüm secret'ları düz metin okuyabilir.
2. **RBAC üzerinden**: Secret okuma yetkisi olan herhangi bir özne, API üzerinden secret'ı çekebilir.
3. **Pod'a mount edilirken**: Secret environment variable olarak enjekte edildiğinde, süreç ortam değişkenleri (`/proc/<pid>/environ`), loglar veya crash dump'lar aracılığıyla sızabilir.
4. **Git ve imaj katmanları**: En sık hata, secret'ların düz metin YAML olarak Git deposuna commit edilmesi ya da bir container imajının katmanına gömülmesidir. İmaj katmanları değiştirilemez olduğundan, silinen bir secret bile eski katmanda kalır.

### Sömürü Mantığı

Saldırgan bir pod ele geçirdiğinde önce mount edilmiş ServiceAccount token'ını ve environment variable'ları tarar. Ardından RBAC izinleri elveriyorsa `kubectl get secrets` benzeri sorgularla namespace (hatta tüm cluster) secret'larını toplar. Eğer etcd'ye ağ erişimi varsa ve etcd kimlik doğrulaması zayıfsa, doğrudan etcd'den okuma en verimli yoldur çünkü tek noktadan her şeyi verir.

### Savunma Mantığı

- **etcd encryption at rest** özelliğini etkinleştirin. Kubernetes, secret'ları etcd'ye yazmadan önce şifrelemek için bir `EncryptionConfiguration` destekler. İdeali, anahtar yönetimini harici bir KMS (Key Management Service) sağlayıcısına devreden bir yapılandırmadır; böylece şifreleme anahtarı etcd ile aynı yerde durmaz.
- **Secret'ları environment variable yerine dosya olarak mount edin.** Dosya mount'ları env'lere göre daha az sızıntı yüzeyine sahiptir (loglara ve child process ortamına yansımaz).
- **Harici secret yöneticileri** kullanın (örneğin HashiCorp Vault ya da bulut sağlayıcıların secret servisleri). Bunlar kısa ömürlü, döndürülen (rotated) kimlik bilgileri sağlar ve secret'ı hiç etcd'de tutmama seçeneği sunar (External Secrets Operator ya da CSI Secret Store sürücüleri bu entegrasyonu kolaylaştırır).
- **RBAC ile secret erişimini daraltın**: hangi ServiceAccount hangi secret'ı okuyabilir, mümkünse namespace ve ad bazında sınırlayın.
- **Secret'ları asla Git'e düz metin commit etmeyin.** Şifrelenmiş secret akışları (örneğin Sealed Secrets ya da SOPS ile şifrelenmiş dosyalar) GitOps ile güvenli çalışmayı sağlar.
- Secret'ları düzenli **döndürün (rotation)** ve sızıntı şüphesinde derhal iptal edin.

---

## 4. Network Policy: Ağ Segmentasyonu

### Tanım ve Kök Neden

Kubernetes'in varsayılan ağ modeli **düz (flat) ve tamamen açıktır**: aynı cluster içindeki her pod, başka herhangi bir pod ile ağ üzerinden konuşabilir. Namespace'ler ağ izolasyonu sağlamaz; yalnızca isimlendirme ve RBAC sınırıdır. Bu "varsayılan olarak her şey birbirine ulaşabilir" tasarımı, geliştirmeyi kolaylaştırır ama güvenlik açısından felakettir: tek bir ele geçirilmiş pod, cluster içindeki her servise yatay hareket (lateral movement) için serbest bir zemin bulur.

**NetworkPolicy**, bu düz ağı segmentlere ayırmak için kullanılan Kubernetes kaynağıdır. Pod'lar arası ve pod-dış dünya trafiğini `ingress` (gelen) ve `egress` (giden) kurallarıyla, etiket (label) seçicileri üzerinden kısıtlar.

Kritik bir nokta: **NetworkPolicy'yi cluster'ın CNI (Container Network Interface) eklentisi uygular.** Eğer kullandığınız CNI NetworkPolicy'yi desteklemiyorsa, yazdığınız politika nesnesi sessizce hiçbir şey yapmaz. Bu, "politika var sanıp aslında korumasız olmak" gibi sinsi bir yanlış güven duygusu yaratır.

### Çalışma Mantığı: Whitelist ve Additive

NetworkPolicy da RBAC gibi beyaz liste mantığıyla çalışır, ama bir inceliği vardır: bir pod'a **herhangi** bir NetworkPolicy seçici olarak eşleştiği anda, o pod için ilgili yön (ingress/egress) **varsayılan olarak reddedilir (default deny)** ve yalnızca politikalarda açıkça izin verilen trafiğe açılır. Hiçbir politika bir pod'u seçmiyorsa, o pod tümüyle açık kalır. Bu yüzden pratikte önce bir "default deny" politikası konur, sonra gereken bağlantılar tek tek açılır.

### Somut Örnek: Yatay Hareketin Engellenmesi

Bir e-ticaret cluster'ında `frontend`, `backend` ve `database` namespace'leri olduğunu düşünün. Doğru segmentasyonda: `frontend` yalnızca `backend`'e 8080 portundan gidebilmeli; `database`'e yalnızca `backend` 5432 portundan erişebilmeli; `frontend`'in `database`'e doğrudan erişimi hiç olmamalı. Bu politikalar yoksa, `frontend`'de bir uygulama açığından (örneğin bir SSRF ya da RCE) içeri giren saldırgan, doğrudan veritabanına bağlanıp veriyi çekebilir. Doğru NetworkPolicy'lerle saldırganın `frontend`'den `database`'e giden yolu ağ katmanında kesilir; RCE'yi başarsa bile veritabanına ulaşamaz.

### Savunma Mantığı

- Her namespace için bir **default-deny** ingress ve egress politikası ile başlayın; sonra yalnızca gereken akışları açın.
- **Egress kontrolünü ihmal etmeyin.** Çoğu ekip yalnızca ingress'e odaklanır; ama giden trafiği kısıtlamak, ele geçirilen bir pod'un komuta-kontrol (C2) sunucusuna bağlanmasını ya da veri sızdırmasını (data exfiltration) engellediği için en az ingress kadar önemlidir.
- CNI eklentinizin NetworkPolicy'yi (ve tercihen egress'i, DNS bazlı kuralları) gerçekten desteklediğini doğrulayın.
- Namespace bazlı ve label bazlı seçicileri birlikte kullanarak trafiği hem organizasyonel hem de fonksiyonel eksende bölün.
- Daha gelişmiş ihtiyaçlar için L7 (uygulama katmanı) politikaları ve mTLS sağlayan bir service mesh (kimlik bazlı, sıfır güven ağı) değerlendirin. Bu, "hangi IP" yerine "hangi kimlik" temelinde yetkilendirme sağlar ki IP'lerin sürekli değiştiği bir ortamda çok daha sağlamdır.

---

## 5. Saldırı Yolları: Katmanların Nasıl Zincirlendiği

Gerçek saldırılar tek bir açığı değil, bir dizi küçük zayıflığı zincirler. Kubernetes'te tipik bir saldırı yolunu adım adım görmek, savunmanın neden katmanlı olması gerektiğini netleştirir.

### Tipik Zincir: Uygulamadan Cluster-Admin'e

1. **İlk erişim (initial access)**: Saldırgan, bir pod içinde çalışan uygulamadaki bir açığı (RCE, SSRF, savunmasız bir bağımlılık) kullanarak konteyner içinde kod çalıştırma yeteneği kazanır.
2. **Keşif (discovery)**: Konteyner içinde mount edilmiş ServiceAccount token'ını (`/var/run/secrets/kubernetes.io/serviceaccount/`) bulur. API server'a "ben ne yapabiliyorum" diye sorar. Ayrıca metadata servislerini yoklar; bulut ortamında instance metadata endpoint'i (node'un IAM kimlik bilgilerini barındırabilir) sık bir hedeftir.
3. **Yanal hareket (lateral movement)**: NetworkPolicy yoksa, cluster içindeki diğer servisleri (veritabanları, dahili API'ler) tarar ve bağlanır.
4. **Yetki yükseltme (privilege escalation)**: ServiceAccount'un fazla izni varsa bunu kullanır. Örneğin pod oluşturma izni ile `hostPath` mount eden privileged bir pod yaratıp node'a kaçar (container escape). Ya da secret okuma izniyle daha yetkili kimlik bilgileri toplar.
5. **Kalıcılık ve genişleme**: Node'a eriştiğinde o node'daki tüm podların secret'larını ve kubelet kimliğini alır. Yeterince ayrıcalık toplandığında RBAC nesnelerini düzenleyerek ya da cluster-admin token'ı ele geçirerek tüm cluster'ın kontrolünü alır.

### Bu Zinciri Kıran Katmanlar

Dikkat edin: yukarıdaki her adım **farklı bir savunma katmanıyla** kesilebilir.

- 1. adımı **pod security** (root olmama, seccomp, salt okunur dosya sistemi) zorlaştırır.
- 2. adımı, ServiceAccount token'ının otomatik mount'unu kapatmak (`automountServiceAccountToken: false`) ve metadata servisine erişimi ağ katmanında engellemek zayıflatır.
- 3. adımı **NetworkPolicy** keser.
- 4. adımı **en az yetkili RBAC** ve **pod security** (hostPath/privileged yasağı) birlikte engeller.
- 5. adımı ise etcd encryption, harici secret yönetimi ve node izolasyonu sınırlar.

Tek bir katman kusursuz olmak zorunda değildir; birden fazla katmanın aynı anda delinmesi gerektiği için saldırının maliyeti ve gürültüsü çok artar. Savunmanın felsefesi budur.

### Kontrol Düzlemine Yönelik Riskler

Yukarıdaki iş yükü odaklı zincire ek olarak kontrol düzlemi (control plane) bileşenlerinin kendisi de hedeftir:

- **API server'ın anonim erişime açık olması**: Yanlış yapılandırmada kimlik doğrulamasız isteklere geniş yetki verilebilir. `anonymous-auth` ve yetkilendirme modu ayarları kritiktir.
- **etcd'nin kimlik doğrulamasız ya da şifresiz ağa açık olması**: etcd'yi ele geçiren cluster'ı ele geçirir.
- **kubelet API'sinin korumasız olması**: kubelet'in okuma-yazma portu yetkilendirmesiz bırakılırsa, saldırgan node üzerindeki podlarda komut çalıştırabilir.
- **Supply chain (tedarik zinciri)**: Güvenilmeyen ya da imzasız imajların çalıştırılması. İmaj imzalama ve doğrulama (örneğin Sigstore/cosign benzeri akışlar) ile admission aşamasında yalnızca güvenilir imajlar kabul edilmelidir.

---

## Yaygın Hatalar (Özet)

Sahada tekrar tekrar görülen hatalar, aslında yukarıdaki bölümlerin negatifidir:

- `cluster-admin` ya da wildcard RBAC izinlerini gündelik iş yüklerine bağlamak.
- Default ServiceAccount'u kullanmak ve token'ını her pod'a otomatik mount ettirmek.
- `privileged`, `hostPath`, `hostNetwork` gibi ayarları test kolaylığı için açık bırakıp prodüksiyona taşımak.
- Secret'ları base64 ile "güvenli" sanmak; düz metin Git commit'leri.
- etcd encryption at rest'i hiç açmamak.
- NetworkPolicy hiç yazmamak ya da CNI'nin bunu desteklemediğini fark etmeden yazmak; egress'i tümüyle unutmak.
- Güvenlik güncellemelerini geciktirmek; eski, yamanmamış Kubernetes ve konteyner runtime sürümleri çalıştırmak.
- Denetim (audit) loglarını toplamamak, dolayısıyla saldırıyı fark edememek.

## En İyi Pratikler (Özet)

1. **En az yetki her yerde**: RBAC'te wildcard'sız, namespace-scoped, düzenli denetlenen izinler.
2. **Pod security enforce**: hassas namespace'lerde `restricted` profili, root olmama, drop-all capabilities, seccomp `RuntimeDefault`.
3. **Secret'ları ciddiye alın**: etcd encryption (tercihen KMS ile), dosya mount, harici secret yöneticisi, düzenli rotation, Git'e asla düz metin.
4. **Default-deny ağ**: her namespace'te ingress ve egress default deny, sonra açık akışlar; egress'i unutma; CNI desteğini doğrula.
5. **Katmanları zincirle**: hiçbir tek kontrole güvenme; saldırı zincirinin her adımına en az bir savunma yerleştir.
6. **Görünürlük**: audit logging, çalışma zamanı tehdit tespiti ve düzenli konfigürasyon taraması (CIS Benchmark bazlı denetim araçları) ile bilinmeyeni bilinir kıl.
7. **Güncel kal**: kontrol düzlemi, kubelet, CNI ve base imajları yamalı tut; imaj imzalama ile tedarik zincirini koru.

Kubernetes güvenliği, tek bir ayarı doğru yapmakla değil, bu katmanların birbirini destekleyecek şekilde tutarlı biçimde kurulmasıyla sağlanır. Her katman, bir saldırının belirli bir adımını pahalı ve gürültülü kılar; birlikte çalıştıklarında ise saldırganın hata payını sıfıra yaklaştırırlar.
