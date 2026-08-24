# Kubernetes Şüpheli Aktivite — Tespit

> Saha notu. Bu metin "Kubernetes nedir" anlatmaz. Bir cluster'da düşmanın gerçekte ne yaptığını, audit log'un neyi gösterip neyi gizlediğini ve tek bir Sigma kuralının neden sizi yanlış güvene ittiğini anlatır. Referans kurallar gerçek Sigma reposundan alındı; field ve logsource adları orijinaldir.

---

## 1. Özet: saldırı + naif tespit (kısa)

Kubernetes'te düşmanın istediği tek şey vardır: cluster içinde **kalıcılık** ve **ayrıcalık yükseltme**. Bunu dört ana kapıdan yapar:

1. **Admission webhook** yerleştirir (`mutatingwebhookconfigurations` / `validatingwebhookconfigurations`) — her API isteğini kendi sunucusuna kopyalatır, kimlik bilgisi sızdırır veya pod'lara sessizce sidecar enjekte eder.
2. **CronJob/Job** yaratır (`batch` apiGroup) — zamanlanmış kod yürütme, reboot'a dayanıklı kalıcılık.
3. **`pods/exec`** ile çalışan bir container'ın içine düşer — dosyasız, canlı komut yürütme.
4. **`delete`** ile iz temizler — `events` siler, `deployments` siler (yıkım/kesinti).

Naif tespit her biri için tek bir Sigma imzası koyar. Örnek, referans setinden birebir:

```yaml
title: Potential Remote Command Execution In Pod Container
logsource: { category: application, product: kubernetes, service: audit }
detection:
    selection:
        verb: 'create'
        objectRef.resource: 'pods'
        objectRef.subresource: 'exec'
    condition: selection
level: medium
```

Bu kural teknik olarak doğru. `kubectl exec` yapan herkes API server audit log'unda `create pods/exec` üretir. Sorun kuralda değil; sorun **tek başına bu kuralın ne kadar gürültü ürettiğinde ve gerçek saldırının çoğunun bu kuralın altından geçmesinde**. Aşağısı bunun neden böyle olduğunu ve saha analistinin bununla ne yaptığını anlatır.

---

## 2. Naif tespit neden yetmez

### 2.1 Kör nokta: audit policy loglamıyorsa kural boştur

Bu, K8s tespitinde en çok gözden kaçan gerçektir. Yukarıdaki `pods/exec` kuralı, `mutatingwebhookconfigurations` kuralı, hepsi **audit log satırı var olduğu varsayımıyla** yazılır. Ama audit event'inin üretilip üretilmediğini kural değil, **cluster'ın audit policy dosyası** belirler.

Varsayılan gerçek şudur: birçok managed cluster (özellikle self-managed kube-apiserver veya yanlış yapılandırılmış EKS/GKE/AKS) audit log'u ya hiç açmaz ya da `Metadata` seviyesinde açar. `pods/exec` alt kaynağı, birçok default policy'de `RequestReceived` aşamasında veya düşük seviyede loglanır; `exec` içinde çalıştırılan **komutun kendisi** (`/bin/sh -c ...`) audit request body'sinde durur ama policy `Request`/`RequestResponse` seviyesinde değilse hiç görünmez. Yani kural tetiklense bile analiste "kim ne komutu çalıştırdı" gelmez — sadece "biri bir pod'a exec yaptı" gelir.

Sonuç: **kuralı SIEM'de görmeden önce audit policy'de o kaynağın `RequestResponse` seviyesinde loglandığını doğrulamadıysanız, tespitiniz kağıt üzerinde vardır, sahada yoktur.** Detection engineering'in ilk işi kural yazmak değil, `audit-policy.yaml` içinde `resources: ["pods/exec"]`, `["mutatingwebhookconfigurations"]`, `["cronjobs","jobs"]` satırlarının `level: RequestResponse` ile mevcut olduğunu doğrulamaktır.

### 2.2 `verb` alanı naif kuralı deler

`Deployment Deleted From Kubernetes Cluster` kuralına bakın:

```yaml
detection:
    selection:
        verb: 'delete'
        objectRef.resource: 'deployments'
    condition: selection
level: low
```

`verb: delete` tek başına yeterli değil çünkü Kubernetes'te silme iki farklı şekilde olur:
- `delete` — tek nesne.
- `deletecollection` — bir seferde tüm namespace'i süpürme. Düşman izini toplu temizlerken `deletecollection` kullanır ve bu kural onu **kaçırır** çünkü selection tam string `'delete'` eşlemesi yapar.

Aynı şekilde `Kubernetes Events Deleted` kuralı da `verb: 'delete'` arar; saldırgan `kubectl delete events --all` yerine API'ye `deletecollection` verb'ü ile giderse veya event'leri hiç silmeyip **TTL ile kendiliğinden düşmelerini beklerse** (K8s event'leri default 1 saat sonra kaybolur) hiç iz bırakmadan kaçar. Yani "event silme" tespiti aslında sabırlı saldırgana karşı işlemez; event'ler zaten uçucu.

### 2.3 Kalıcılık kuralları ayrıcalıklı ile ayrıcalıksızı ayırmaz

`Kubernetes CronJob/Job Modification` kuralı `objectRef.apiGroup: batch` + `verb: create/update` yakalar. Ama bir cluster'da **her CI/CD pipeline, her backup operator, her cert yenileme job'u** normalde CronJob/Job yaratır. Kural `level` bile koymadan tetiklerse, analistin önüne günde yüzlerce satır gelir ve 3 gün sonra kuralı susturur. Kör nokta burada: kural **kim** yarattığını (`user.username`, `user.groups`) ve **nereden** (source IP, serviceaccount) yaratıldığını selection'a katmadığı için sinyal/gürültü oranı çöker.

### 2.4 False positive selleri

- **Webhook kuralı**: Istio/Linkerd sidecar injection, cert-manager, OPA Gatekeeper, Kyverno — hepsi meşru `mutatingwebhookconfigurations` yaratır/günceller. Bir Kyverno kurulumu tek başına o kuralı onlarca kez tetikler.
- **exec kuralı**: canlı debugging, `kubectl exec -it` ile troubleshooting, hatta bazı liveness prob mekanizmaları.
- **deployment delete**: her `helm uninstall`, her GitOps (ArgoCD/Flux) reconcile döngüsü, her blue/green kesme.

Tek başına hiçbiri "olay" değil. Değer, aşağıdaki korelasyonda.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıftır. Yüksek güven, **farklı bağlamlardaki sinyalleri kısa pencerede birbirine bağlamaktan** gelir. Somut, sahada gördüğünüz bir kompromize giden zincir:

### Senaryo: Sızan bir serviceaccount token'ından cluster ele geçirme

**A — İlk dayanak (anomali, tek başına düşük):**
Bir pod'a `create pods/exec` geliyor (`Potential Remote Command Execution In Pod Container` tetikliyor). Tek başına: meşru debug olabilir. Ama `user.username` bir **serviceaccount** (`system:serviceaccount:prod:web-frontend`), insan değil. İnsan olmayan bir kimliğin interaktif exec yapması anormaldir — CI dışında serviceaccount'lar exec yapmaz.

**B — Kısa pencere (~10 dk), farklı bağlam — keşif + ayrıcalık:**
Aynı `user.username` veya aynı source IP'den art arda:
- `get secrets` (`objectRef.resource: secrets`, `verb: get/list`) — token ve kimlik toplama,
- ardından `create mutatingwebhookconfigurations` (`Kubernetes Admission Controller Modification` tetikliyor, `objectRef.apiGroup: admissionregistration.k8s.io`).

Webhook yaratma **tek başına** meşum değil (Kyverno da yapar). Ama bunu yapan kimlik **10 dk önce bir pod'dan exec ile içeri düşen aynı frontend serviceaccount'sa**, bu artık Kyverno değil. Frontend'in webhook yaratma yetkisi olmamalı — RBAC'i buna izin veriyorsa o ayrı bir bulgu.

**C — Kalıcılık + iz temizleme (ihlali kesinleştirir):**
Aynı aktörden dakikalar içinde:
- `create cronjobs` (`batch` apiGroup, `Kubernetes CronJob/Job Modification` tetikliyor) — `*/5 * * * *` ile dışa reverse shell,
- ve `delete events` (`Kubernetes Events Deleted` tetikliyor) veya `deletecollection` denemesi.

**Yargı:** A + B + C ayrı ayrı düşük/orta seviye. Ama **tek kimlik, tek source, < 15 dakika, exec → secret okuma → webhook → cronjob → event silme** dizisi tek bir kompromizedir. Bunu tek Sigma kuralı göremez; bir **korelasyon kuralı** (Sentinel'de `Scheduled Analytics` / Splunk'ta `transaction` veya `stats by user.username`) görebilir. Korelasyonun bağlama alması gereken alanlar:

- `user.username` + `user.groups` (aktör kimliği),
- `sourceIPs[]` (nereden),
- `objectRef.namespace` (yatay hareket: prod'dan kube-system'e sıçrama var mı),
- `responseStatus.code` (200 başarılı mı, 403 denendi mi — 403 fırtınası keşif demektir),
- `requestReceivedTimestamp` (pencere).

Somut korelasyon mantığı (sözde-Splunk):

```
index=k8s_audit
| stats values(verb) as verbs values(objectRef.resource) as res
        dc(objectRef.resource) as res_variety
        min(_time) as t0 max(_time) as t1
        by user.username sourceIPs{}
| where res_variety>=4
  AND match(verbs,"exec")
  AND (match(res,"secrets") OR match(res,"webhook"))
  AND (t1 - t0) < 900
```

Bu sorgu tek başına gürültücü kuralların hiçbirini alarm etmez; sadece **birlikte** göründüklerinde alarm eder. Değer burada.

### 3.1 Zincirdeki "farklı bağlam" niçin önemli

Naif yaklaşım "aynı kaynağa çok istek" arar (rate-based). Ama gerçek K8s kompromizesinin imzası **kaynak çeşitliliğidir**, hacim değil. Meşru bir CI job'u tek tip iş yapar: sürekli `create pods`, sürekli `get configmaps`. Kompromize ise **birbirine benzemeyen kaynaklara** dokunur — bir exec, sonra bir secret, sonra bir webhook, sonra bir rolebinding. `dc(objectRef.resource)` (distinct count) bu yüzden en ayırt edici tek metriktir. Tek kimliğin 15 dakikada 5+ farklı hassas kaynak tipine yazma/okuma yapması, hacimden bağımsız olarak, otomasyonun değil elle gezinen bir aktörün imzasıdır.

### 3.2 Yatay hareket sinyali: namespace sıçraması

Zincire eklenecek güçlü bir dördüncü boyut: `objectRef.namespace` değişimi. Kompromize olan `web-frontend` SA'sı normalde sadece `prod` namespace'ine dokunur. Aynı token ile aniden `kube-system` namespace'inde `get secrets` veya `default` namespace'inde exec görülüyorsa, bu **yetki alanının dışına taşma**dır. Korelasyona `dc(objectRef.namespace) > beklenen` koşulu eklemek, tek namespace'e hapsolmuş meşru iş yükünü elerken cluster genelinde gezinen saldırganı öne çıkarır. Özellikle `kube-system`'e ilk temas her zaman incelemelik: orada control-plane SA token'ları ve `cluster-admin` binding'leri durur.

---

## 4. False positive gerçeği ve triage yargısı

Sahada bu kuralların FP kaynakları isim isim bellidir. Analist önce bunları elemeyi bilmeli.

**Webhook modifikasyonu FP'leri:**
- **Kyverno / OPA Gatekeeper**: policy engine'ler webhook config'i kendileri yönetir, düzenli reconcile eder. `user.username` = `system:serviceaccount:kyverno:kyverno-admission-controller` gibi bilinen bir SA ise → gürültü.
- **cert-manager**: TLS `caBundle` rotasyonunda webhook config'i günceller (`update`). Periyodik ve öngörülebilir.
- **Istio/Linkerd**: sidecar injection webhook'u kurulum ve upgrade'de değişir.

**CronJob/Job FP'leri:**
- **Velero/Kasten** backup job'ları, **external-dns**, **cluster-autoscaler**, her CI runner (GitLab/Jenkins/Argo Workflows) sürekli Job yaratır.

**exec FP'leri:**
- SRE'nin `kubectl exec` ile canlı debug'ı, **ephemeral debug container** (`kubectl debug`), bazı operator'ların health-check'i.

**deployment delete FP'leri:**
- ArgoCD/Flux prune, `helm uninstall`, namespace teardown otomasyonu.

### Analistin öncelik sırası (triage yargısı)

Bir alarm geldiğinde sıralama şu:

1. **Kimlik insan mı, serviceaccount mı?** İnsan kullanıcının exec'i normaldir; bilinen operatör SA'sının webhook güncellemesi normaldir. **Ters kombinasyon** (SA exec yapıyor, ya da bilinmeyen insan kullanıcı webhook yaratıyor) → yükselt.
2. **Kaynak IP allowlist'te mi?** CI/CD runner subnet'i, bastion IP'si, VPN aralığı biliniyorsa → düşür. Bilinmeyen/dış IP, hele pod CIDR'ından geliyorsa (yani cluster içinden bir pod API'ye vuruyorsa) → yükselt.
3. **`responseStatus.code`**: 403'ler önce keşif işaretidir ama tek başına ihlal değil; **403 fırtınasının ardından bir 200 gelmesi** yetki bulmuş demektir → yükselt.
4. **Nesnenin adı/namespace'i**: `kube-system`, `kube-node-lease`, `cluster-admin` clusterrolebinding'e dokunuş her zaman öncelik. Uygulama namespace'inde rutin Job → düşür.
5. **Zaman**: mesai dışı + hafta sonu + otomasyon penceresi dışı → ağırlık ekle (tek başına delil değil).

Kural: **tek FP kaynağını suppress ederken kimlik+kaynak ikilisiyle suppress et, sadece kaynak tipiyle değil.** "Tüm cronjob create'lerini sustur" yanlış; "kyverno SA'sından gelen webhook update'lerini sustur" doğru. Aksi halde saldırgan tam da meşru SA'yı taklit ederek geçer.

---

## 5. Kaçınma → karşı-tespit

Dokümantasyonda yazmayan, sahada görülen atlatmalar ve bunların ikinci-derece tespiti:

### 5.1 `pods/exec` yerine `pods/attach` ve efemeral container

Analistler `pods/exec` izler; saldırgan aynı sonucu `objectRef.subresource: attach` (bir process'in stdin/stdout'una bağlanma) veya **ephemeral debug container** (`objectRef.subresource: ephemeralcontainers`, `verb: update` / `patch`) ile alır. Referans exec kuralı `subresource: 'exec'` tam eşlediği için **attach ve ephemeralcontainers onun altından geçer.**

**Karşı-tespit:** selection'ı `objectRef.subresource` in `[exec, attach, ephemeralcontainers, proxy]` şeklinde genişletin. `ephemeralcontainers` özellikle önemli: dosyasız yürütmenin yeni gözde yolu ve çoğu kural setinde yoktur.

### 5.2 Webhook yerine doğrudan RBAC ile kalıcılık

Saldırgan gürültülü webhook yerine, sessizce bir `clusterrolebinding` yaratıp kendi SA'sını `cluster-admin`'e bağlayabilir (`objectRef.apiGroup: rbac.authorization.k8s.io`, `resource: clusterrolebindings`, `verb: create`). Referans set bunu **kapsamıyor** — bu bir kör nokta.

**Karşı-tespit:** `rbac.authorization.k8s.io` üzerinde `create/update` + hedef rolün `cluster-admin` veya `*` verb/resource içermesi. Bu, webhook kuralından daha yüksek değerlidir çünkü RBAC manipülasyonu neredeyse her cluster ele geçirmede vardır.

### 5.3 Audit log'a hiç düşmeyen yürütme: node üzerinden

En sinsi atlatma: API server'ı hiç kullanmamak. Saldırgan bir pod'da RCE aldıysa ve pod privileged/hostPID ise, **kubelet'in kendi API'sine (`:10250/exec`)** doğrudan gider veya node'un container runtime'ına (`crictl`, `nerdctl`) düşer. Bu trafiğin **hiçbiri kube-apiserver audit log'una girmez** — çünkü API server'dan geçmez.

**Karşı-tespit (ikinci derece):** Burada K8s audit log kördür; tespit **node seviyesine** iner. Falco / eBPF sensörü (`clone`, `execve` syscall'ları), kubelet'in kendi log'u, ve `:10250` portuna cluster içi anormal bağlantılar (network policy log'u). Yani "K8s şüpheli aktivite" tespiti API-audit ile bitmez; node telemetrisi olmadan privileged pod escape'i görünmez.

### 5.4 Webhook'u yaratıp hemen silme (hit-and-run credential harvest)

Saldırgan `validatingwebhookconfigurations` yaratır, `failurePolicy: Ignore` ve geniş bir `rules` ile birkaç dakika API isteklerini kendi sunucusuna kopyalatıp token toplar, sonra config'i **siler**. Kalıcı bir webhook aramak yanıltıcıdır; obje artık cluster'da yoktur.

**Karşı-tespit:** webhook config'in `create`'ini yakalayın ama asıl olarak **kısa ömür** desenini korele edin: aynı obje için `create` sonrası < N dakika `delete`. Ayrıca yaratılan webhook'un `clientConfig.url`'inin **cluster dışı bir adres** olması güçlü bir sinyaldir (meşru webhook'lar çoğunlukla cluster içi `service` referansı kullanır, harici `url` değil).

### 5.5 CronJob yerine "meşru görünümlü" kalıcılık

Gürültülü CronJob yerine saldırgan mevcut bir Deployment'ı `patch` ile değiştirip container image'ını veya `command`'ını sessizce güncelleyebilir (`objectRef.resource: deployments`, `verb: patch/update`). Bu, `Kubernetes CronJob/Job Modification` kuralının **tamamen dışında** kalır çünkü o kural `batch` apiGroup'a bakar, Deployment `apps` apiGroup'tadır. Kalıcılık aynı, tespit yolu farklı.

**Karşı-tespit:** `apps` apiGroup'ta (`deployments`, `daemonsets`, `statefulsets`) `patch`/`update` + değişen alanın `spec.template.spec.containers[].image` veya `command`/`args` olması. Özellikle image'ın **bilinmeyen bir registry**'den gelmesi (kurumsal registry allowlist'i dışı) yüksek değerli bir alt sinyaldir. DaemonSet manipülasyonu ayrıca kritiktir: DaemonSet her node'da pod çalıştırdığı için tek bir zehirli DaemonSet tüm cluster node'larına yayılır.

### 5.6 `impersonate` ile kimlik gizleme

İleri saldırgan, kendi yetkili token'ıyla doğrudan iş yapmak yerine `impersonate` verb'ü / `Impersonate-User` header'ı ile başka bir kimliğe bürünür. Audit log'da `user.username` gerçek aktörü, `impersonatedUser` bürünülen kimliği taşır. Naif kurallar sadece `user.username`'e baktığı için impersonation'ı gözden kaçırır ve olayı yanlış kimliğe atfeder.

**Karşı-tespit:** `verb: impersonate` veya audit event'te `impersonatedUser` alanının dolu olması tek başına incelemelik — meşru impersonation nadirdir (çoğunlukla `kubectl --as` ile debug). Korelasyonda **gerçek** aktörü `user.username` ile, bürünüleni ayrı izleyin; ikisini karıştırmak atıf hatasına yol açar.

---

## 6. SIEM / saha gerçeği

### 6.1 Field mapping — audit JSON'dan SIEM alanına

Sigma `objectRef.resource` yazar; gerçek kube-apiserver audit event'i iç içe JSON'dur:

```json
{
  "verb": "create",
  "user": { "username": "system:serviceaccount:prod:web", "groups": [...] },
  "objectRef": { "resource": "pods", "subresource": "exec",
                 "namespace": "prod", "apiGroup": "" },
  "sourceIPs": ["10.0.3.14"],
  "responseStatus": { "code": 201 },
  "requestReceivedTimestamp": "..."
}
```

SIEM'e girerken bu düzleşir ve platforma göre değişir:
- **Splunk**: genelde `objectRef.resource` → `objectRef.resource` (nokta korunur, `spath` ile) veya kaynak yapılandırmasına göre `object_ref_resource`. Sigma→Splunk çeviricisi bunu bilmeli.
- **Sentinel**: audit log AKS Diagnostic Settings ile gelir, `kube-audit` kategorisinde, `log_s` alanının içine **string olarak gömülü JSON** düşer. Yani `objectRef.resource` doğrudan sorgulanamaz; önce `parse_json(log_s)` ile açmanız gerekir. Bu, Sentinel'de en sık kaçırılan noktadır — kural KQL'de `log_s` ham string üzerinde çalışırsa hiç eşleşmez.
- **Elastic**: ECS'e maplenir, `kubernetes.audit.objectRef.resource`, `kubernetes.audit.verb`, `kubernetes.audit.user.username`. Filebeat kubernetes audit modülü bu prefix'i koyar.

**Pratik sonuç:** aynı Sigma kuralı üç platformda üç farklı field yolu ister. "Sigma yazdım, her yere gider" yanlıştır; backend field mapping'i doğrulanmadan deploy edilen kural sessizce hiçbir şey eşleşmeden çalışır — en tehlikeli hata türü (yeşil dashboard, sıfır tespit).

### 6.2 Varsayılan loglanmayan

- **AKS**: `kube-audit` **ve** daha az gürültülü `kube-audit-admin` kategorileri vardır. `kube-audit-admin` `get`/`list`/`watch` gibi okuma verb'lerini eler — yani `get secrets` keşfini görmek istiyorsanız pahalı olan tam `kube-audit`'i açmalısınız. Çoğu ekip maliyet için sadece `-admin`'i açar ve keşif fazına kör kalır.
- **EKS**: control plane logging'de `audit` bileşeni **default kapalıdır**. Açılmadan hiçbir K8s audit tespiti çalışmaz; ilk kontrol budur.
- **GKE**: Cloud Audit Logs'ta `DATA_READ` default kapalı — yine `get`/`list` görünmez.

### 6.3 Gürültü ve maliyet gerçeği

Tam `RequestResponse` audit + tüm read verb'leri, büyük bir cluster'da **günde yüz GB'lara** çıkar. Sınırsız açmak SIEM lisansını yakar; hiç açmamak kör bırakır. Saha dengesi:
- Yazma verb'leri (`create/update/patch/delete/deletecollection`) → her zaman `RequestResponse`.
- Okuma verb'leri (`get/list`) → sadece hassas kaynaklarda (`secrets`, `configmaps`, `serviceaccounts/token`).
- `pods/exec`, `pods/attach`, `ephemeralcontainers` → her zaman `RequestResponse` (komut satırını görmek için).

### 6.4 Tuning — kuralları sahaya oturtmak

1. **Envanter çıkar**: cluster'daki tüm meşru operatör SA'larını (kyverno, cert-manager, argocd, velero, autoscaler) listeleyip her kuralın `user.username NOT IN (...)` allowlist'ini bunlarla besle. Bu tek adım FP'nin ~%80'ini eler.
2. **Referans kurallardaki `level`'e güvenme**: `Deployment Deleted` `level: low` gelir ama sizin cluster'ınızda GitOps prune sürekli deployment siliyorsa bunu `informational`'a düşür; tersine, prod'da manuel delete hiç olmuyorsa `high`'a çıkar. Level, cluster'ın operasyon modeline göre yeniden kalibre edilir — Sigma'nın default'u başlangıç noktasıdır, son söz değildir.
3. **Korelasyonu ayrı katmana koy**: tekil kurallar `informational`/`low` kalsın, gürültü olsun ama saklansın; **alarm üreten katman Bölüm 3'teki korelasyon kuralı olsun.** Tekil kuralları alarm yapmak analist yorgunluğunun bir numaralı sebebidir.
4. **`sourceIPs` zenginleştir**: pod CIDR'dan mı, node'dan mı, dış IP'den mi geldiğini etiketle. Cluster içinden (bir pod'dan) gelen yönetimsel API çağrısı neredeyse her zaman incelenmeye değer — meşru yönetim bastion/CI'den gelir, iş yükü pod'undan değil.

### 6.5 Son yargı

Kubernetes tespitinde başarı, daha çok kural yazmakta değil, **üç şeyi doğrulamakta**: (1) audit policy o event'i gerçekten üretiyor mu, (2) SIEM'de field yolu doğru maplenmiş mi, (3) tekil gürültü korelasyon katmanında birleşiyor mu. Bu üçü olmadan en iyi Sigma kuralı bile yeşil bir dashboard ve sıfır görünürlük üretir. Ve unutmayın: privileged pod escape, kubelet API ve node runtime üzerinden yürüyen saldırılar **API audit'in tamamen dışındadır** — K8s tespitiniz node telemetrisi (Falco/eBPF) ile tamamlanmadıkça yarısı eksiktir.
