# Kubernetes RBAC ve Pod Security Admission (PSA) Derinlemesine

## Giriş: Neden Bu Konu Ayrı Ele Alınmalı

Genel "Kubernetes Güvenliği" başlığı altında RBAC ve Pod Security genellikle yüzeysel geçilir: "en az yetki verin", "root çalıştırmayın" gibi tavsiyelerle sınırlı kalır. Oysa gerçek dünyada Kubernetes cluster'larının ele geçirilmesinin büyük çoğunluğu, tek bir kritik zafiyetten değil, **RBAC yanlış yapılandırmalarının ve pod güvenlik kısıtlarının eksikliğinin bir araya gelmesinden** doğar. Bir saldırgan tipik olarak önce düşük yetkili bir konteynerde çalışma hakkı bulur (SSRF, CI/CD pipeline zafiyeti, savunmasız bir uygulama), sonra bu konteynerin ServiceAccount token'ini kullanarak Kubernetes API'siyle konuşur ve RBAC'in fazla cömert olması sayesinde cluster-admin seviyesine tırmanır. Bu makale, bu zincirin her halkasını kavramsal olarak, savunmacı gözüyle açıklıyor: RBAC modelinin iç mantığı, en tehlikeli yanlış yapılandırma kalıpları, Pod Security Standards'ın (PSS) çalışma mantığı ve eski PodSecurityPolicy'den (PSP) geçiş sürecinin doğurduğu riskler.

## RBAC Temel Mimarisi ve Çalışma Mantığı

Kubernetes RBAC (Role-Based Access Control), API sunucusuna gelen her isteği dört ana nesne türü üzerinden yetkilendirir: **Role/ClusterRole** (izin setleri) ve **RoleBinding/ClusterRoleBinding** (bu izinleri kime bağladığı). Role, bir namespace'e hapsedilmişken ClusterRole cluster genelinde veya namespace'e bind edilerek kullanılabilir. Bir izin kuralının üç bileşeni vardır: **apiGroups** (hangi kaynak grubu), **resources** (pods, secrets, deployments vb.) ve **verbs** (get, list, watch, create, update, patch, delete, ve kritik olarak **escalate**, **bind**, **impersonate**).

Kök mantık şu: API sunucusu her istekte "bu kimlik (user/group/ServiceAccount), bu kaynak üzerinde, bu eylemi yapmaya yetkili mi?" sorusunu RBAC yetkilendiricisine sorar. Yetkilendirici, ilgili kimliğe bağlanmış tüm RoleBinding/ClusterRoleBinding'leri tarar; **herhangi bir** binding izin veriyorsa istek kabul edilir (RBAC additive/toplayıcı bir modeldir, deny kuralı yoktur). Bu toplayıcı yapı, RBAC'in en çok yanlış anlaşılan yanı: bir yerde aşırı geniş bir binding varsa, başka bir yerde ne kadar sıkı kurallar olursa olsun o geniş yetki geçerlidir. "En kısıtlayıcı kural kazanır" mantığı (örneğin firewall kurallarındaki gibi) RBAC'te yoktur.

### Escalate, Bind ve Impersonate: Ayrıcalık Yükseltmenin Yerleşik Kapıları

RBAC'in kendi içi, tasarım gereği ayrıcalık yükseltme (privilege escalation) için resmi mekanizmalar barındırır:

- **bind verb'ü**: Normalde bir kullanıcının sahip olmadığı izinleri içeren bir Role'u başkasına bind etmesi engellenir (self-escalation koruma kuralı). Ancak `clusterroles` kaynağı üzerinde `bind` verb'ü verilmiş bir kullanıcı, kendi sahip olmadığı izinleri barındıran bir ClusterRole'u bir ServiceAccount'a veya kendisine bağlayabilir. Bu, "yetki verme yetkisi"nin kendisinin bir ayrıcalık olduğunu gösterir.
- **escalate verb'ü**: `clusterroles` kaynağında `escalate` verb'ine sahip bir kullanıcı, kendi sahip olmadığı izinleri de içeren yeni bir ClusterRole oluşturabilir/düzenleyebilir — normal ayrıcalık yükseltme korumasını bilinçli olarak by-pass eden tek verb budur.
- **impersonate verb'ü**: `users`, `groups` veya `serviceaccounts` kaynaklarında `impersonate` verb'ü, sahibinin başka bir kimlik gibi (örneğin `system:masters` grubundaki bir kullanıcı gibi) istek göndermesine izin verir. `Impersonate-User` / `Impersonate-Group` header'larıyla çalışır; doğru RBAC kısıtı olmadan bu, dolaylı cluster-admin demektir.

**Neden bu tasarım böyle**: Kubernetes, cluster yöneticilerine ("bootstrap" senaryoları, controller'lar, operator'lar) başka kimlikler adına hareket etme veya yetki devretme yeteneği vermek zorunda. Ancak bu esneklik, bu üç verb'ün dikkatsizce dağıtılması durumunda doğrudan sandbox kaçışı anlamına gelir. Çoğu ihlal olayında "developer'lara kolaylık olsun diye" bu verb'ler geniş ClusterRole'lara sızdırılmış olarak bulunur.

## En Yaygın ve En Tehlikeli RBAC Yanlış Yapılandırmaları

### 1. Wildcard ClusterRoleBinding (`*` Apigroups/Resources/Verbs)

`cluster-admin` ClusterRole'unun kendisi `apiGroups: ["*"]`, `resources: ["*"]`, `verbs: ["*"]` içeren tek bir kuraldan oluşur — yani her kaynak üzerinde her işlem. Sorun, kullanıcıların kendi özel ClusterRole'larını yazarken aynı wildcard kalıbını "işler kolay olsun" diye kopyalaması. Örneğin bir CI/CD servis hesabına sadece deployment güncellemesi için yetki gerekirken, `resources: ["*"]` verilirse bu hesap secrets, RBAC nesnelerinin kendisi ve node'lar dahil her şeye erişebilir hale gelir. Wildcard'ın en tehlikeli hali, `resources: ["*"]` ile birlikte `apiGroups: ["*"]` verilmesidir; çünkü bu durumda `rbac.authorization.k8s.io` API grubu da kapsanır ve sahibi kendi RBAC nesnelerini değiştirebilir — yani kendine sınırsız yetki tanımlayabilir (self-escalation).

**Tespit**: `kubectl get clusterrolebindings -o json` çıkışını tarayıp subject'leri `cluster-admin` veya wildcard içeren özel role'lere bağlayan binding'leri listelemek. RBAC denetim araçları (örneğin `rbac-lookup`, `kubectl-who-can` tarzı yaklaşımlar — spesifik sürüm/komut iddia etmeden kavramsal olarak: "hangi subject hangi kaynakta hangi verb'e sahip" sorgusunu tersine çeviren araçlar) bu taramayı otomatikleştirir.

**Savunma**: En az yetki prensibini Role/ClusterRole yazarken kelime kelime uygulamak — her verb ve resource'u açıkça listelemek, wildcard'ı sadece gerçekten bütün kaynaklara erişim gerektiren (ve ayrıca sıkıca izlenen) sistem bileşenlerine saklamak.

### 2. ServiceAccount Token'in Otomatik Mount Edilmesi

Varsayılan olarak her Pod, çalıştığı namespace'teki ServiceAccount'un API token'ini otomatik olarak `/var/run/secrets/kubernetes.io/serviceaccount/` altına mount eder — pod bu token'a hiçbir zaman ihtiyaç duymasa bile. Kök neden, Kubernetes'in erken tasarımında "her pod'un API sunucusuyla konuşabilmesi gerekebilir" varsayımıdır; ancak pratikte çoğu uygulama pod'u (bir web sunucusu, bir veritabanı) Kubernetes API'siyle hiç konuşmaz.

Bu durum, bir konteyner ele geçirildiğinde (örneğin bir RCE zafiyeti üzerinden), saldırganın ekstra bir kimlik bilgisi çalmasına gerek kalmadan doğrudan cluster içindeki API sunucusuna o pod'un ServiceAccount kimliğiyle istek atabilmesi anlamına gelir. Eğer o ServiceAccount'a (default ServiceAccount dahil, çünkü default SA'ya da geniş bir Role bind edilmiş olabilir) geniş RBAC izinleri verilmişse, tek bir uygulama zafiyeti tüm cluster'in ele geçirilmesine kadar uzanan bir zincire dönüşür.

**Tespit**: Pod spesifikasyonlarında `automountServiceAccountToken: false` ayarının olup olmadığını denetlemek; özellikle dışarıya açık (internet-facing) veya kullanıcı girdisi işleyen pod'larda bu bayrağın kapalı olması beklenir. Ayrıca `default` ServiceAccount'a herhangi bir RoleBinding bağlanıp bağlanmadığı kontrol edilmeli (idealde default SA hiçbir yetkiye sahip olmamalı).

**Savunma**: Token mount'unu ihtiyacı olmayan her pod'da ServiceAccount veya Pod seviyesinde `automountServiceAccountToken: false` ile kapatmak; her iş yükü için ayrı, dar kapsamlı, tek amaçlı ServiceAccount oluşturmak (paylaşılan/genel ServiceAccount kullanmaktan kaçınmak); mümkünse projected token'lar için audience/expiration kısıtlamalarını (bound service account tokens) kullanmak, böylece çalınan bir token'in ömrü ve kullanım alanı sınırlanır.

### 3. Namespace Sınırlarını Aşan RoleBinding Karışıklığı

Bir Role namespace'e özgüdür, ancak bir ClusterRole hem cluster genelinde hem de belirli bir namespace'e RoleBinding ile bağlanarak kullanılabilir. Bu esneklik, "biz zaten cluster-admin ClusterRole'unu tanımlamıştık, sadece bu namespace'e bind edelim" şeklinde düşünülüp, aslında o namespace'teki bir kullanıcıya o namespace içinde çok geniş (secrets okuma, pod exec, vb.) yetkiler verilmesine yol açar. Çok-kiracılı (multi-tenant) cluster'larda bu, namespace izolasyonunun RBAC seviyesinde deldiği en yaygın noktadır.

**Savunma**: Namespace'e özgü ihtiyaçlar için ClusterRole yerine doğrudan Role tanımlamak; ClusterRole'u sadece gerçekten cluster genelinde geçerli olması gereken kaynaklar (node'lar, PersistentVolume'lar, namespace'siz kaynaklar) için kullanmak.

### 4. `secrets` Kaynağına Geniş Erişim ve Dolaylı Ayrıcalık Yükseltme

`get`/`list` yetkisi olan `secrets` kaynağı, doğrudan RBAC verb'ü olmasa bile pratikte ayrıcalık yükseltme aracı olabilir: bir namespace'teki tüm secret'ları okuyabilen bir kimlik, o namespace'teki diğer ServiceAccount'ların token'larını (varsa uzun ömürlü Secret tabanlı token'lar) veya başka sistemlerin (veritabanı, bulut API) kimlik bilgilerini ele geçirebilir. Bu, RBAC'in "verb bazında doğru" ama "sonuç bazında tehlikeli" olabileceği klasik bir örnek — teknik yetki doğru görünse de iş bağlamında aşırı geniş olabilir.

**Savunma**: `secrets` için `list`/`get` yetkisini mümkün olduğunca isim bazlı (resourceNames alanıyla) kısıtlamak; geniş "tüm secret'ları oku" yetkisini sadece secret yönetim operator'lerine ayırmak; harici secret yöneticileri (Vault, bulut KMS entegrasyonları — kavramsal olarak) kullanarak hassas verinin Kubernetes Secret nesnesinde düz metne yakın durmamasını sağlamak.

## Tespit ve Sürekli Denetim Yaklaşımı (RBAC)

Savunmacı perspektiften RBAC'i tek seferlik değil, **sürekli denetlenen** bir yüzey olarak ele almak gerekir:

- **Statik analiz**: Cluster'daki tüm Role/ClusterRole/RoleBinding/ClusterRoleBinding nesnelerini periyodik olarak dışa aktarıp, wildcard kullanımı, `escalate`/`bind`/`impersonate` verb dağıtımını ve `cluster-admin` bağlantılarını raporlayan bir sorgu/script çalıştırmak.
- **Etkin yetki grafik analizi**: Hangi kimliğin (özellikle her ServiceAccount'un) fiili olarak hangi kaynaklara erişebildiğini görselleştiren araç zinciri (BloodHound'un Active Directory için yaptığına benzer mantık, Kubernetes RBAC grafiğinde de geçerlidir — "kim, hangi zincir üzerinden cluster-admin'e ulaşabilir" sorusu).
- **Audit log'ları izleme**: API sunucusu audit log'larında `impersonate` header'i kullanılan istekleri, beklenmedik `create` istekleri (`clusterrolebindings`, `rolebindings` nesnelerine) ve normalde API'yle konuşmayan pod'lardan gelen ani API çağrılarını alarmlamak (SIEM/log korelasyon katmanında).
- **En az yetki testi**: Yeni bir Role/ClusterRole tanımlanırken "bu iş yükü gerçekten bu verb'e ihtiyaç duyuyor mu" sorusunu CI/CD aşamasında otomatik kontrol eden politika motorları (OPA/Gatekeeper veya benzeri politika-as-kod yaklaşımları — kavramsal) kullanmak.

## Pod Security Admission (PSA) ve Pod Security Standards (PSS)

### Kök Neden: Neden Pod'un Kendisini Kısıtlamak Gerekir

RBAC, "kim hangi API işlemini yapabilir" sorusunu çözer ama "oluşturulmasına izin verilen bir Pod'un **çalışma zamanı davranışı** ne olabilir" sorusunu çözmez. Bir kullanıcının `pods` kaynağında `create` yetkisi olması yeterlidir; RBAC kontrolü geçince, o Pod spesifikasyonunun `privileged: true`, `hostNetwork: true`, `hostPID: true` veya tehlikeli `hostPath` mount'ları içermesini API sunucusu RBAC katmanı tek başına engellemez. İşte bu boşluk, **Pod Security Standards (PSS)** ve bunu uygulayan **Pod Security Admission (PSA)** kontrolcüsü tarafından doldurulur.

PSS üç seviye tanımlar:

- **Privileged**: Kısıtlama yok; her türlü ayrıcalık yükseltme ve host'a erişim serbest. Sadece güvenilen sistem/infra bileşenleri (CNI eklentileri, storage driver'ları) için düşünülür.
- **Baseline**: Bilinen en yaygın ayrıcalık yükseltme yollarını engeller (privileged container'lar, host namespace paylaşımları — hostNetwork/hostPID/hostIPC —, tehlikeli hostPath'ler, belirli capability'lerin eklenmesi gibi) ama geçiş kolaylığı için bazı esnekliklere izin verir.
- **Restricted**: En sıkı seviye; container'ın root olmayan kullanıcı olarak çalışmasını zorunlu kılar, `allowPrivilegeEscalation: false` ister, tüm Linux capability'lerini düşürüp sadece gerekenleri (genelde hiçbirini) ekletmeye izin verir, seccomp profilini zorunlu kılar.

**Çalışma mantığı**: PSA, bir **admission controller** olarak API sunucusuna entegre çalışır — yani bir Pod oluşturma/güncelleme isteği RBAC yetkilendirmesinden geçtikten sonra, API sunucusu tarafından persist edilmeden önce devreye girer. Namespace üzerine eklenen `pod-security.kubernetes.io/enforce`, `audit`, `warn` etiketleri hangi PSS seviyesinin o namespace'te nasıl uygulanacağını belirler: `enforce` ihlal eden Pod'u reddeder, `audit` sadece audit log'una yazar, `warn` kullanıcıya uyarı döner ama engellemez. Bu üçü ayrı tutmanın nedeni, bir cluster yöneticisinin önce `audit`/`warn` ile mevcut iş yüklerinin ne kadarının ihlal ettiğini görmesini, sonra kademeli olarak `enforce`'a geçmesini sağlamaktır — aniden production'i kırmadan sıkılaştırma yapılabilmesi için.

### Yaygın İhlal Kalıpları ve Neden Tehlikeli Oldukları

- **`privileged: true`**: Container'i host'un çekirdeğine neredeyse doğrudan erişimi olan bir sürece dönüştürür; container içinden host dosya sistemine, cihazlarına ve potansiyel olarak çekirdek modüllerine erişim mümkün hale gelir. Bu tek ayar, container izolasyonunun büyük kısmını etkisiz kılar.
- **`hostPID`/`hostNetwork`/`hostIPC: true`**: Container'in host'un process, ağ veya IPC namespace'ini paylaşması anlamına gelir. hostPID ile container içinden host üzerindeki tüm process'ler görülebilir (ve bazı durumlarda `/proc/<pid>/root` üzerinden erişilebilir); hostNetwork ile container host'un ağ arayüzlerini doğrudan kullanır, bu da ağ tabanlı izolasyonu (NetworkPolicy dahil) by-pass edebilir.
- **Tehlikeli hostPath mount'ları**: `/`, `/etc`, `/var/run/docker.sock` gibi yolların container'a mount edilmesi, container'dan host dosya sistemine yazma/okuma imkanı tanır — `docker.sock` mount edilmişse container, host üzerinde yeni ve privileged bir container başlatarak doğrudan container kaçışı (container escape) gerçekleştirebilir.
- **`allowPrivilegeEscalation: true` (varsayılan)**: Bu alan false olarak ayarlanmadığı sürece, container içindeki bir process setuid/setgid binary'ler aracılığıyla ebeveyninden daha fazla yetkiye ulaşabilir.
- **Gereksiz Linux capability'leri** (`NET_ADMIN`, `SYS_ADMIN`, `NET_RAW` vb.): Çoğu uygulama hiçbir özel capability'ye ihtiyaç duymaz; varsayılan capability seti bile bazı durumlarda fazla geniştir, restricted profil bunların tümünü düşürüp yalnızca açıkça eklenenlere izin verir.
- **Root kullanıcı olarak çalışma (`runAsNonRoot` yok)**: Container içinde root olarak çalışmak, bir container escape zafiyeti bulunduğunda saldırganın host'ta da root yetkisiyle çıkması riskini büyük ölçüde artırır (tam bir escape garantisi değildir, ama saldırı yüzeyini önemli ölçüde genişletir).

### PodSecurityPolicy'den (PSP) Geçiş: Neden Bir Boşluk Riski Doğurur

PodSecurityPolicy, PSA'nın selefiydi ve cluster genelinde bir admission controller kaynağı olarak çalışıyordu; kullanımı RBAC üzerinden dolaylı olarak kontrol ediliyordu (bir ServiceAccount/kullanıcının belirli bir PSP'yi "kullanma" yetkisi olması gerekiyordu), bu da PSP'yi anlaması ve doğru yapılandırması zor, hataya açık bir mekanizma haline getiriyordu. PSP kullanımdan kaldırılıp yerini PSA/PSS aldı (Kubernetes'in resmi geçiş takvimi vardı; tam sürüm numaralarını iddia etmek yerine kavramsal olarak: PSP önce deprecated edildi sonra kaldırıldı).

**Bu geçişin doğurduğu somut risk**: Eski PSP'lere dayanan cluster'lar, güncelleme sırasında hiçbir Pod Security kısıtı olmayan bir "boşluk dönemi" yaşayabilir — PSP kaldırılmış ama yerine PSA/PSS namespace etiketleri henüz eklenmemişse, o aralıktaki tüm namespace'ler fiilen "privileged" seviyesinde, yani hiçbir pod-seviyesi kısıt olmadan çalışır. Ayrıca PSP'nin esnek/geniş politika kurgusu ile çalışan eski iş yükleri, restricted PSS'e geçildiğinde aniden reddedilebilir (örneğin hala root olarak çalışan eski bir imaj) — bu da yöneticileri "kısıtlamayı tamamen kapatma" yoluna itebilir, ki bu en kötü sonuç olur.

**Savunma / Geçiş Önerisi**:
1. Önce tüm namespace'lere `audit` ve `warn` modlarında `restricted` (veya en azından `baseline`) etiketi ekleyip, mevcut iş yüklerinin ihlallerini audit log'ları ve `warn` mesajları üzerinden envanterlemek.
2. İhlal eden iş yüklerini (imaj güncellemesi, capability azaltma, non-root kullanıcı tanımlama yoluyla) düzeltmek.
3. Namespace bazında kademeli olarak `enforce: restricted` seviyesine geçmek; sistem bileşenlerinin çalıştığı namespace'ler (kube-system vb.) için gerçeve dışı/istisnai durumlarda daha gevşek seviye bırakılabilir ama bu istisnalar açıkça dokümante edilmeli.
4. PSP'den PSA'ya geçerken araya başka bir admission-kontrol katmanı (politika motoru tabanlı özel kurallar) koyarak, PSS'in kapsamadığı organizasyona-özgü kısıtların (örneğin belirli registry dışından imaj çekilmesini engelleme) boşluğunu kapatmak.

## RBAC ve PSA'nın Birlikte Çalışması: Savunma Katmanlarının Bütünlüğü

Bu iki mekanizma birbirini tamamlar, biri diğerinin yerini tutmaz:

- RBAC olmadan PSA: Bir kullanıcı istediği kadar restricted namespace'te pod oluşturabilir ama eğer RBAC ona `secrets` veya `clusterrolebindings` üzerinde aşırı yetki vermişse, pod'un kendisi kısıtlı olsa da o kullanıcının API üzerinden yapabilecekleri sınırsız kalır.
- PSA olmadan RBAC: Bir ServiceAccount'a sadece "pods create" yetkisi verilmiş olsa bile, PSS namespace'te enforce edilmiyorsa bu ServiceAccount privileged bir pod oluşturup doğrudan node'u ele geçirebilir — RBAC'in "sadece pod oluşturabilir" sınırlaması, pod'un içeriği üzerinde hiçbir kısıt yoksa anlamsızlaşır.

Gerçek savunma derinliği, ikisinin kesişiminde ortaya çıkar: RBAC "kim ne oluşturabilir"i, PSA "oluşturulan şeyin nasıl davranabileceği"ni kısıtlar. Bunlara ek olarak NetworkPolicy (ağ seviyesi izolasyon) ve admission-zamanı özel politika motorları (imaj kaynağı doğrulama, kaynak limiti zorunluluğu gibi) da aynı savunma katmanına eklenmelidir — RBAC ve PSA tek başına "Kubernetes güvenliği" değil, bu geniş resmin iki kritik ama birbirini tamamlayan parçasıdır.

## Özet Kontrol Listesi (Savunma Perspektifi)

- ClusterRole/Role tanımlarında wildcard (`*`) kullanımını minimuma indirin; her binding'i düzenli denetleyin.
- `escalate`, `bind`, `impersonate` verb'lerini yalnızca gerçekten gereken, sıkıca izlenen kimliklere verin.
- Her iş yükü için özel, dar kapsamlı ServiceAccount tanımlayın; `default` ServiceAccount'a hiçbir yetki bağlamayın.
- API'ye ihtiyacı olmayan pod'larda `automountServiceAccountToken: false` ayarlayın.
- Tüm namespace'lere `pod-security.kubernetes.io/enforce` etiketiyle en azından `baseline`, mümkünse `restricted` seviyesini uygulayın; geçişi `audit`/`warn` ile kademeli yapın.
- `privileged`, `hostNetwork`, `hostPID`, `hostIPC` ve tehlikeli `hostPath` mount'larını enforce eden namespace'lerde varsayılan olarak reddedin.
- RBAC etkin-yetki grafiğini ve PSA ihlal loglarını sürekli/periyodik olarak denetleyin; audit log'larında anormal `impersonate` ve RBAC nesnesi değişikliklerini alarmlayın.
- PSP'den PSA'ya geçerken boşluk dönemi oluşturmamaya özellikle dikkat edin; geçiş öncesi/sonrası kısıtların kesintisiz uygulandığını doğrulayın.
