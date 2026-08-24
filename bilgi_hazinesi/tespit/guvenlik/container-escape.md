# Container Escape — Tespiti

> Saha notu: "Container escape" konusunda internetteki metinlerin %90'ı
> saldırı tarafını anlatır — `nsenter`, `release_agent`, `/proc/self/exe`.
> Tespit tarafı ise neredeyse hep tek cümleye indirgenir: "ayrıcalıklı
> konteyner oluşturulmasını izleyin". Bu cümle *doğru* ama gerçek ortamda
> işe yaramaz, çünkü (a) ayrıcalıklı konteyner meşru olarak her yerde vardır,
> (b) asıl kaçış anı çoğu kez pod spec'inde hiç görünmez, (c) izlemeniz
> gereken log çoğu kümede varsayılan olarak hiç toplanmaz. Bu metin, iki
> katmanı — Kubernetes admission katmanı ile host çalışma-zamanı katmanı —
> nasıl bağladığını, tespitin nerede çöktüğünü ve analistin gürültü içinde
> nasıl karar verdiğini anlatır.

---

## 1. Özet: saldırı + naif tespit

Container escape, bir konteyner içinde kod çalıştırabilen saldırganın
konteyner izolasyon sınırını (namespace + cgroup + capability + seccomp/
AppArmor) aşarak *host* düğüm üzerinde kod çalıştırmasıdır. Kubernetes
bağlamında bu, tek bir pod'u ele geçirmiş bir saldırganın o pod'un koştuğu
worker node'un tamamına — ve node'daki kubelet kimlik bilgileri, diğer
pod'ların secret'ları, servis hesabı token'ları üzerinden potansiyel olarak
tüm kümeye — yayılması demektir. Bu yüzden konteyner kaçışı bir "privilege
escalation + lateral movement" olayıdır, izole bir olay değil.

Kaçış yollarının çoğu ya *yanlış yapılandırmadan* ya da *çalışma-zamanı
zafiyetinden* beslenir. Yanlış yapılandırma tarafı: `securityContext.
privileged: true` (konteyner host'un tüm cihazlarına ve capability'lerine
erişir), `hostPID: true` (host süreç namespace'ini paylaşır — `nsenter`
ile PID 1'e girilir), `hostNetwork`/`hostIPC`, tehlikeli bir tekil
capability (`CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`, `CAP_SYS_MODULE`,
`CAP_DAC_READ_SEARCH`), ya da hassas bir `hostPath` mount'u
(`/var/run/docker.sock`, `/`, kubelet dizini, `/proc`, `/sys`).
Çalışma-zamanı zafiyeti tarafı: `runc` binary üzerine yazan CVE-2019-5736,
cgroups v1 `release_agent` istismarı CVE-2022-0492, "Leaky Vessels"
CVE-2024-21626 (runc'un sızan dosya tanıtıcısı / `/proc/self/fd` çalışma
dizini — burada *ayrıcalık bile gerekmez*), ya da konteynerin içinden host
çekirdeğini vuran DirtyPipe (CVE-2022-0847) türü çekirdek açıkları.

Naif tespit iki noktaya bakar. **Birincisi Kubernetes denetim (audit)
katmanı**: yukarıdaki *Privileged Container Deployed*
(`c5cd1b20-36bb-488d-8c05-486be3d0cb97`) Sigma kuralı, `product: kubernetes`
denetim loglarında bir pod'un `securityContext.privileged` bayrağı, standart
dışı Linux capability'leri veya `hostNetwork`/`hostPID` alanlarıyla
oluşturulmasını yakalar. **İkincisi host çalışma-zamanı katmanı**: Falco'nun
varsayılan kuralları (*Launch Privileged Container*, *Change thread
namespace*, *Terminal shell in container*) veya Linux `auditd`/Sysmon-for-
Linux üzerinde `nsenter`, `unshare`, `mount`, `setns` çağrıları.

Bu kadarı "ayrıcalıklı bir şey koştu" der. Sorun, bu "şey"in ya hiç
loglanmaması, ya günde yüzlerce meşru olayın içinde boğulması, ya da asıl
kaçış anının pod spec'inde *hiç görünmemesidir*. Değer buradan sonrası.

---

## 2. Naif tespit neden yetmez

**Birincisi ve en kritiği: `requestObject` çoğu kümede loglanmaz.**
*Privileged Container Deployed* kuralının çalışması için Kubernetes denetim
politikasının pod kaynakları için `Request` ya da `RequestResponse`
seviyesinde loglama yapması gerekir — çünkü `securityContext.privileged`,
`hostPID`, `capabilities` alanlarının hepsi `requestObject.spec` içinde
yaşar. Ama üretimdeki denetim politikalarının büyük kısmı, log hacmini
kısmak için pod'ları `Metadata` seviyesinde loglar. `Metadata` seviyesinde
olay *kimin, ne zaman, hangi pod'u yarattığını* söyler ama **spec gövdesini
taşımaz** — yani `privileged: true`nin *kendisi loga hiç düşmez*. Kural
teknik olarak doğru field'a bakar; o field kaynakta hiç yoktur. Bu, ADCS'de
SAN'ın loglanmaması gibi sessiz bir kör noktadır: kural "yeşil" görünür,
hiç ateşlemez, kimse fark etmez.

**İkincisi: managed kümelerde denetim logu varsayılan olarak kapalı ya da
farklı.** EKS'te control-plane audit loglaması ayrıca açılmalı
(CloudWatch'a `audit` log tipi). AKS'te tanı ayarları (diagnostic settings)
ile `kube-audit`/`kube-audit-admin` akıtılmalı — ve `kube-audit-admin` zaten
get/list'leri eler, hacmi düşürür ama bazı okuma olaylarını da kaybettirir.
GKE'de Cloud Audit Logs var ama admin-activity ile data-access ayrımı ve
hangi kaynakların loglandığı yapılandırmaya bağlı. Yani Sigma kuralının
beslendiği `product: kubernetes` kaynağı birçok kurumda *fiziksel olarak
yok*.

**Üçüncüsü: `privileged: true` kaçışın gerekli koşulu değil.** Kural adı
"Privileged Container" ama gerçek kaçışların önemli bir kısmı `privileged`
bayrağını hiç kullanmaz:
- Tek başına `CAP_SYS_ADMIN` (privileged olmadan `capabilities.add` ile) —
  cgroup `release_agent` istismarı ve mount için yeterlidir. `privileged`
  selection'ı bunu görmez; capability ekleme ayrıca izlenmelidir.
- `hostPath` ile `/var/run/docker.sock` mount'u + root — konteyner
  ayrıcalıksızdır ama Docker soketi üzerinden *yeni* bir privileged konteyner
  yaratıp host'u mount edebilir. Pod "temiz" görünür.
- CVE-2024-21626 (Leaky Vessels) — saldırgan sadece imajın `WORKDIR`'ını
  `/proc/self/fd/N` yapar; ne privileged, ne capability, ne hostPath. Pod
  spec'i tamamen masumdur; kaçış runc'un kendi hatasından gelir. Hiçbir
  admission-katmanı kuralı bunu göremez.
- Çekirdek açığı (DirtyPipe vb.) — standart, kısıtlı bir konteynerden bile
  host root'a çıkabilir. Pod spec'inde hiçbir anormallik yoktur.

**Dördüncüsü: array (dizi) problemi imzayı sessizce kör eder.** Bir pod
spec'inde `containers` bir dizidir; çok konteynerli bir pod'da (sidecar'lı
Istio, logging agent'lı uygulama) `privileged: true` dizinin *hangi*
elemanında olduğu önemlidir. Splunk/Elastic tarafında naif bir anahtar
kelime araması (`privileged=true`) doğru ateşlese bile, hangi konteynerin
ayrıcalıklı olduğunu, hangi capability'nin hangi konteynere eklendiğini
`spath`/`mvexpand` (Splunk) veya nested `painless`/runtime field (Elastic)
olmadan söyleyemez. Analiste "pod X ayrıcalıklı" demek, "pod X'in *init*
konteyneri ayrıcalıklı ve o zaten CNI kurulumu için normal" ile "pod X'in
*app* konteyneri ayrıcalıklı ve bu anormal" arasındaki farkı gizler.

**Beşincisi: host katmanı tek başına gürültülüdür ve pod bağlamını
bilmez.** Falco'nun *Terminal shell in container* kuralı her `kubectl exec`'te
ateşler — geliştiriciler, CI, canlı hata ayıklama sürekli tetikler. *Change
thread namespace* (setns) kuralı meşru araçlarda (bazı CNI/CSI ajanları,
`crictl`, çalışma-zamanının kendisi) de görülür. Bu sinyaller tek başına
"yüksek" değildir; anlam kazanmaları için pod kimliğiyle (namespace, image,
service account) ve zaman/sıra ile birleştirilmeleri gerekir.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf; container escape yüksek-güvenli tespiti **iki katmanı
zaman penceresiyle bağlamayı** gerektirir: admission katmanı (pod *ne* olarak
doğdu) + host çalışma-zamanı katmanı (o pod'un içinden host'a *doğru ne
yapıldı*) + host-tarafı ikinci-derece etki (kaçış *gerçekleşti* mi).

**Somut zincir (yanlış-yapılandırma yolu):**

> **A —** Denetim logunda `verb: create`, `objectRef.resource: pods`,
> `requestObject.spec.hostPID: true` ve bir konteynerde
> `securityContext.privileged: true`; **kritik ayrıştırıcı:**
> `user.username` bir *insan* ya da CI kimliği (örn.
> `oidc:ahmet@kurum` veya `system:serviceaccount:default:ci-runner`), bir
> altyapı servis hesabı (`system:serviceaccount:kube-system:*`) *değil*; ve
> `objectRef.namespace` `kube-system`/`monitoring` gibi bir sistem alanı
> *değil*, `default`/uygulama alanı. Ayrıca pod'u yaratan bir Deployment/
> DaemonSet denetleyicisi değil, doğrudan `kubectl run`/apply (yani
> `requestObject.metadata.ownerReferences` *yok*) — bu "interaktif,
> elle atılmış ayrıcalıklı pod" imzasıdır.
>
> **B — (dakikalar içinde, farklı bağlam: host çalışma-zamanı)** Aynı
> pod'un konteyner ID'sine bağlı bir süreçten `nsenter -t 1 -m -u -i -n -p`
> ya da `setns` çağrısı (Falco *Change thread namespace*; auditd `execve`
> `nsenter`/`unshare`; Sysmon-for-Linux `ProcessCreate`). Alternatif dal:
> `mount` ile host disk cihazının (`/dev/sda1`, `/dev/nvme0n1p*`) konteyner
> içine bağlanması, ya da `/sys/fs/cgroup/.../release_agent` veya
> `/proc/sys/kernel/core_pattern` dosyasına *yazma* (CVE-2022-0492 imzası).
>
> **C — (ikinci-derece etki)** Host üzerinde, *hiçbir konteyner cgroup'una
> ait olmayan* ama bir `containerd-shim`/`runc` soyundan gelen bir süreç
> belirir — yani PID host namespace'inde koşan bir `bash`/`sh`. Ya da
> kubelet kimlik dosyasına (`/var/lib/kubelet/pki/`, `/etc/kubernetes/`)
> konteyner-kökenli bir süreçten erişim. Bu, kaçışın *başarıya ulaştığının*
> doğrulamasıdır.

**A + kısa pencere B + C = ihlal.** Tek başına A yüzlerce kez masumca olur
(aşağıda). Tek başına B, meşru CNI/CSI araçlarında görülür. Tek başına C
nadirdir ama bazı düğüm ajanlarında olur. Üçünün *aynı konteyner kimliği
etrafında ve dakikalar içinde* dizilmesi, tek tek her sinyalin false
positive oranını çarpımsal olarak çökertir ve "keşif" ile "istismar"ı ayırır.

**İkinci somut zincir (çalışma-zamanı-zafiyeti yolu, spec temiz):** Burada
A adımı *yoktur* — pod ayrıcalıksızdır. Zincir host katmanında başlar:
`runc`/`containerd` sürümü CVE-2024-21626'ya açık + Falco/auditd'de konteyner
`init`'inin `/proc/self/fd/*` üzerinden host dosya sistemine (örn.
`/proc/self/fd/7/../../../etc/shadow` deseni) erişmesi + hemen ardından host
namespace'inde beklenmedik süreç. Bu yolun *tek* güvenilir tespit noktası
host katmanıdır; admission katmanı tanım gereği kördür. Bu yüzden "sadece
audit loguna bakan" bir SOC bu sınıfı *hiç* göremez.

---

## 4. False positive gerçeği ve triage yargısı

Container escape tespitinin en acı gerçeği şudur: **ayrıcalıklı konteyner
üretimde her yerde meşru olarak vardır.** Kör bir "privileged container
deployed = alarm" kuralı, SOC'u ilk gün boğar. Kimler meşru olarak
ayrıcalıklı/host-erişimli koşar:

- **CNI eklentileri**: Calico, Cilium, Flannel — node ağını kurmak için
  `privileged` + `hostNetwork`, çoğu zaman `CAP_NET_ADMIN`/`CAP_SYS_ADMIN`.
- **CSI/depolama sürücüleri ve operatörler**: disk mount için `privileged`
  + hassas `hostPath`.
- **Gözlemlenebilirlik/güvenlik ajanları**: node-exporter, Datadog agent,
  Falco'nun *kendisi*, Wazuh, EDR sensörleri — `hostPID`, `hostPath`
  (`/proc`, `/sys`, `/var/log`), sıkça `privileged`.
- **Log toplayıcılar**: Fluentd/Fluent Bit/Filebeat — `hostPath` ile
  `/var/log/containers`, `/var/lib/docker/containers`.
- **kube-proxy, node-problem-detector, GPU device plugin, Istio CNI init**:
  hepsi meşru host erişimi ister.

Yani `securityContext.privileged: true`nin *frekansı* günde onlarca-yüzlerce
olabilir. Bu bir "false positive seli" değil, **beklenen taban gürültüsüdür**;
tespiti bunun *üstüne* kurmak gerekir.

**Analistin öncelik sırası (triage yargısı):**

1. **Yaratıcı kim? (`user.username` / `ownerReferences`)** En güçlü
   ayrıştırıcı. Ayrıcalıklı pod bir DaemonSet/Deployment denetleyicisi
   tarafından, bir altyapı servis hesabıyla yaratıldıysa → neredeyse kesin
   meşru (allowlist adayı). *İnsan* bir kullanıcı ya da beklenmedik bir CI
   kimliği tarafından, `kubectl run`/`apply` ile *doğrudan* (ownerReference
   yok) yaratıldıysa → önceliği yükselt.
2. **Namespace + image kaynağı.** `kube-system`/`monitoring`/vendor
   namespace'inde, güvenilir registry'den (kurumun kendi ECR/GCR/Harbor'u,
   bilinen vendor imajı) → düşük. `default`/uygulama namespace'inde, umumi
   ya da bilinmeyen registry'den (Docker Hub `latest`, ephemeral) → yüksek.
3. **Ne kadar "çıplak"?** DaemonSet ajanı belirli, dar bir profil ister
   (belirli capability, belirli hostPath). Saldırganın pod'u genelde
   *aşırı* geniştir: `privileged` + `hostPID` + `hostNetwork` + `hostPath: /`
   birlikte, ya da `nsenter`/pause imajı yerine genel amaçlı bir imaj
   (`ubuntu`, `alpine`, `busybox`) interaktif komutla.
4. **`pods/exec`, `pods/attach`, `pods/ephemeralcontainers` alt kaynakları.**
   `kubectl debug --target`/`kubectl exec` ile *var olan* ayrıcalıklı bir
   pod'a bağlanmak, yeni pod yaratmadan kaçış zemini sağlar. Bu alt
   kaynaklara erişim (denetim logunda `objectRef.subresource: exec`) insan
   kimliğiyle + ayrıcalıklı hedefte görülürse önceliklidir.
5. **Host katmanı ateşledi mi?** Nihai karar: admission alarmı *tek başına*
   orta önceliktir; ama aynı pod ID'sinden host katmanında (Bölüm 3-B/C) bir
   sinyal geldiyse → kritik, hemen müdahale.

Pratikte "ayrıcalıklı pod yaratıldı" alarmını tek başına bir P1 yapmak
yanlıştır; onu bir *zenginleştirme sinyali* olarak tutup, yaratıcı-kimlik +
namespace + host-katmanı korelasyonuyla önceliklendirmek doğru yargıdır.

---

## 5. Kaçınma → karşı-tespit

Dokümanların yazmadığı atlatmalar ve bunların ikinci-derece tespitleri:

**Atlatma 1 — `privileged` yerine tekil capability.** Saldırgan
`privileged: true` yazmaz (bu en çok izlenen bayrak), yerine
`capabilities.add: ["SYS_ADMIN"]` (ya da `CAP_DAC_READ_SEARCH` ile
`open_by_handle_at` üzerinden host inode okuma — klasik "shocker") kullanır.
`privileged` selection'ı kördür.
→ **Karşı-tespit:** `requestObject.spec.containers[].securityContext.
capabilities.add` alanında `SYS_ADMIN`/`SYS_MODULE`/`SYS_PTRACE`/
`DAC_READ_SEARCH`/`NET_ADMIN` gibi tehlikeli capability'leri ayrıca izle;
dizi elemanları için `mvexpand`. Admission katmanında ise OPA/Gatekeeper ya
da Pod Security Admission (`restricted`/`baseline`) *reddini* logla — reddin
kendisi bir sinyaldir.

**Atlatma 2 — Var olan meşru ayrıcalıklı pod'u ele geçir.** Saldırgan yeni
pod yaratmaz; zaten çalışan bir CNI/monitoring pod'unu (privileged, hostPID)
uygulama zafiyetiyle ele geçirip *onun içinden* kaçar. `create pods`
denetim olayı hiç oluşmaz.
→ **Karşı-tespit:** Kaçış tespiti pod yaşam döngüsünden bağımsız, *host
çalışma-zamanı* katmanında olmalı: setns/nsenter/mount/`release_agent`
yazımı hangi pod'dan gelirse gelsin ateşlemeli. Ayrıca "bu pod'un imajı X
ama içinde `nsenter`/`bash` çalışıyor" tarzı image-drift (Falco *Container
Drift*/binary çalıştırma) sinyali: CNI ajanı normalde interaktif shell
açmaz.

**Atlatma 3 — Ephemeral container / `kubectl debug --target`.** Var olan bir
pod'a geçici bir konteyner enjekte etmek (`pods/ephemeralcontainers`), klasik
pod-create izlemesini atlar; hedef `--target` ile başka bir konteynerin
namespace'ini paylaşabilir.
→ **Karşı-tespit:** `objectRef.subresource: ephemeralcontainers` üzerinde
`verb: patch`/`update` denetimi; ayrıca `pods/exec` ve `pods/attach`. Bu alt
kaynaklar üretimde nadir kullanılır; insan kimliğiyle + ayrıcalıklı bağlamda
görülmesi yüksek sinyaldir.

**Atlatma 4 — Spec'i tamamen temiz bırakan çalışma-zamanı zafiyeti.**
CVE-2024-21626 (Leaky Vessels) / CVE-2019-5736 (runc üzerine yazma): pod
ayrıcalıksız, capability yok, hostPath yok. Admission katmanı tanım gereği
kör.
→ **Karşı-tespit:** (a) Çalışma-zamanı sürüm envanteri — açık runc/
containerd sürümlerini kümede tespit et (bu bir *detection* değil, ama tespit
edilemeyen sınıf için tek gerçekçi savunma). (b) Host katmanında: konteyner
`init` sürecinin `/proc/self/fd/*` üzerinden host FS'e erişimi, ya da host
`runc` binary'sinin *değiştirilmesi* (dosya bütünlüğü — auditd `-w /usr/bin/
runc -p wa`). CVE-2019-5736 host runc'una *yazar*; bu yazma auditd/EDR ile
görülebilir.

**Atlatma 5 — Docker soketi üzerinden dolaylı kaçış.** Pod ayrıcalıksızdır,
ama `hostPath` ile `/var/run/docker.sock` (ya da `containerd`/CRI soketi)
mount edilmiştir. Saldırgan konteyner içinden host'un konteyner
çalışma-zamanına *doğrudan* API çağrısı yaparak, host kök dizinini (`/`)
mount eden yeni bir ayrıcalıklı konteyner yaratır — kaçış, kendi pod'unda
hiç syscall üretmeden host runtime'ında gerçekleşir. Naif `privileged`
selection'ı ve host setns/nsenter izlemesi bile sessiz kalabilir.
→ **Karşı-tespit:** Admission katmanında `volumes[].hostPath.path` içinde
`docker.sock`/`containerd.sock`/`crio.sock` desenlerini *reddedilecek/
alarm verilecek* liste olarak izle; host katmanında ise "kısa ömürlü,
`/` mount'lu, image'ı genel amaçlı" yeni konteyner doğuşunu (Falco
*Launch Privileged Container* + host root mount) yakala.

**Atlatma 6 — Statik/manifest yerine kabul kontrolünü baypas.** kubelet'in
statik pod'ları (`/etc/kubernetes/manifests/`) API server'ı ve admission'ı
*atlar*; node'a dosya yazabilen saldırgan buraya ayrıcalıklı bir pod manifesti
koyarak admission katmanını tamamen baypas eder.
→ **Karşı-tespit:** Host katmanında `/etc/kubernetes/manifests/` dizinine
dosya yazımını izle (auditd watch / EDR FIM). Bu dizine yeni bir YAML,
denetim logunda hiç görünmeden ayrıcalıklı pod başlatır.

---

## 6. SIEM/saha gerçeği

**Field haritası ve nerede yaşadıkları.** Kubernetes denetim olayı düz değil,
derin iç içe JSON'dur. Kritik ayrım: **pod-seviye vs konteyner-seviye**
alanlar analistleri sürekli yanıltır.
- `hostPID`, `hostNetwork`, `hostIPC` → **pod seviyesi**:
  `requestObject.spec.hostPID`.
- `privileged` → **yalnızca konteyner seviyesi**:
  `requestObject.spec.containers[].securityContext.privileged`. Pod-seviye
  `spec.securityContext`'te `privileged` *yoktur*; orada arayan analist boş
  döner.
- `capabilities.add` → konteyner seviyesi:
  `...containers[].securityContext.capabilities.add[]`.
- `hostPath` volume → `requestObject.spec.volumes[].hostPath.path`.
- Kimlik/bağlam: `user.username`, `user.groups[]`, `sourceIPs[]`,
  `objectRef.namespace`, `objectRef.resource`, `objectRef.subresource`,
  `verb`, `responseStatus.code`, `annotations` (admission karar
  açıklamaları — reddi burada görürsünüz).

**Varsayılan loglanmayan.** Bölüm 2'deki en büyük kör nokta: pod'lar için
denetim seviyesi `Metadata` ise `requestObject` *hiç yoktur* — `privileged`,
`hostPID`, `capabilities`, `hostPath` alanlarının **hiçbiri** loga düşmez.
Bu kuralın çalışması için denetim politikasında pod create/update'lerin
`RequestResponse` (en azından `Request`) seviyesinde olması *ön koşuldur*.
Bunu doğrulamadan kuralı "aktif" saymak, sahte bir güven duygusudur.

**Splunk.** `containers` ve `volumes` dizidir; naif `privileged=true` araması
hangi konteyneri gösterdiğini bilmez ve capability eşlemesini yapamaz.
Doğrusu: `spath` ile `requestObject.spec.containers{}` açıp `mvexpand`
etmek, sonra `securityContext.privileged=true OR
capabilities.add{}=SYS_ADMIN` filtrelemek. Frekans yüksek olduğundan asıl iş
korelasyondadır: pod-create olayını, aynı `objectRef.name`/konteyner ID'sine
sahip host-katmanı olaylarıyla (Sysmon-for-Linux / Falco → HEC) `transaction`
ya da `stats` ile bağlamak. Allowlist'i `user.username` +
`objectRef.namespace` üzerinden lookup tablosuyla dışlamak zorunludur.

**Microsoft Sentinel.** K8s denetim logu Sentinel'e *doğal* akmaz; AKS için
tanı ayarlarından `kube-audit`/`kube-audit-admin` Log Analytics'e
gönderilmeli (ayrı bir `AKSAudit`/`AzureDiagnostics` tablosu). Dikkat:
`kube-audit-admin` get/list gürültüsünü kırpar ama bazı okuma olaylarını da
kaybettirir; create/update genelde kalır. Host-katmanı (nsenter/mount) için
AKS düğümlerinde ayrıca Defender for Containers ya da bir EDR gerekir —
Sentinel tek başına host syscall görmez. Sorgular KQL'de nested JSON'u
`parse_json`/`mv-expand` ile açar; `containers` dizisi yine `mv-expand`
ister.

**Elastic.** İki ayrı yol vardır ve ikisi de gerekir. (a) Denetim tarafı:
Filebeat kubernetes/audit modülü ile pod-create alanları
`kubernetes.audit.*` altına gelir. (b) Host tarafı: Elastic Defend
(endpoint) / Auditbeat, konteyner kaçışına özel yerleşik kurallar sağlar —
`nsenter`/setns, ayrıcalıklı konteyner içinde shell, host FS drift. Elastic'in
avantajı host + orchestration'ı tek şemada (ECS `container.id`,
`orchestrator.*`) birleştirebilmesidir; korelasyonu `container.id` üzerinden
kurmak Splunk'a göre daha temizdir. Array için nested field/runtime field.

**Host katmanı = asıl savaş alanı.** Admission katmanı gördüğü şeyle
sınırlıdır ve çalışma-zamanı zafiyetlerine tamamen kördür. Gerçek kaçış
tespiti host çalışma-zamanında olur ve varsayılan olarak *kurulmaz*:
- **Falco** de-facto standarttır: *Launch Privileged Container*, *Change
  thread namespace* (setns), *Terminal shell in container*, *Container
  Drift/Write below root*, `release_agent`/`core_pattern` yazımı. Ama
  varsayılan kural seti gürültülüdür; namespace/image bazlı tuning ve exec
  gürültüsünün bastırılması şarttır.
- **auditd**: `setns`/`unshare`/`mount` syscall'ları ve
  `/etc/kubernetes/manifests/`, `/usr/bin/runc`, `/var/run/docker.sock`
  üzerine watch (`-w ... -p wa`) kuralları **elle eklenmelidir**; varsayılan
  auditd bunları izlemez.
- **Sysmon for Linux**: `ProcessCreate` ile `nsenter`/`unshare` ve host FS
  erişimi; yine özel config gerekir.

**Tuning özeti.** (1) Denetim seviyesini pod'lar için `RequestResponse`e
çıkar — yoksa kural anlamsız. (2) `user.username` + `objectRef.namespace`
bazlı meşru ayrıcalıklı iş yükü allowlist'i kur (CNI/CSI/monitoring servis
hesapları). (3) Alarmı "ayrıcalıklı pod = P1" değil, "ayrıcalıklı pod +
insan/beklenmedik kimlik + sistem-dışı namespace + (host-katmanı sinyali)"
korelasyonu olarak kur. (4) Host katmanını (Falco/auditd) mutlaka devreye al;
admission-only bir tespit, kaçışların çalışma-zamanı-zafiyeti sınıfını yapısal
olarak kaçırır. (5) OPA/Gatekeeper veya Pod Security Admission *reddi* dahil
her red olayını sinyal olarak topla — engellenen ayrıcalıklı pod denemesi,
başarılı olandan daha net bir niyet göstergesidir.

Özetle: container escape'te "ayrıcalıklı konteyner oluşturuldu"yu izlemek
başlangıçtır, tespit değildir. Tespit, admission katmanının *ne gördüğü* ile
host katmanının *ne olduğu* arasındaki boşluğu kapatmak; meşru ayrıcalıklı
taban gürültüsünü kimlik ve bağlamla elemek; ve pod spec'inin asla göremeyeceği
çalışma-zamanı-zafiyeti sınıfı için host syscall görünürlüğünü baştan kurmaktır.
