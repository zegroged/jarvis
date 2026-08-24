# Kubernetes Ağ Politikaları, Servis Mesh ve mTLS Güvenliği (Istio/Linkerd/CNI)

## Giriş: Neden Ayrı Bir Konu?

Klasik ağ güvenliğinde segmentasyon, VLAN'lar ve firewall kuralları üzerinden IP adresleri ve portlar arasında sınırlar çizeriz. Kubernetes bu modeli kökten sarsar. Bir küme içinde onlarca, yüzlerce hatta binlerce `Pod` sürekli oluşup yok olur; her birinin IP adresi geçicidir (ephemeral), dakikalar içinde değişebilir. Geleneksel bir firewall için "kaynak IP" kavramı burada anlamsızlaşır çünkü o IP bir dakika sonra tamamen başka bir iş yüküne (workload) ait olabilir.

Dahası, Kubernetes'in varsayılan ağ modeli **düz ve tamamen açıktır**: aynı küme içindeki her `Pod`, diğer her `Pod` ile serbestçe konuşabilir. Bu "east-west" (doğu-batı, yani sunucular arası yatay) trafik hiçbir varsayılan kısıtlamaya tabi değildir. Bir saldırgan tek bir konteynerde uzaktan kod çalıştırma (RCE) elde ettiğinde, kümedeki `kube-system` bileşenlerine, veritabanlarına, iç API'lara doğrudan erişebilecek konumdadır. İşte konteyner segmentasyonunun temel taşları burada devreye girer: `NetworkPolicy` (CNI eklentileriyle uygulanır) ve servis mesh (mTLS ile kimlik tabanlı izolasyon).

Bu makale, bu iki katmanın çalışma mantığını, birbirini nasıl tamamladığını ve saldırganın hangi noktalardan sızabileceğini savunma perspektifinden ele alır.

---

## Bölüm 1: Kubernetes Ağ Modelinin Temelleri

### CNI Nedir?

**CNI (Container Network Interface)**, Kubernetes'in ağ katmanını soyutlayan bir eklenti standardıdır. Kubernetes'in kendisi ağ kurmaz; bu işi CNI eklentilerine (Calico, Cilium, Flannel, Weave, AWS VPC CNI vb.) devreder. Bir `Pod` başlatıldığında `kubelet`, CNI eklentisini çağırır; eklenti `Pod`'a bir IP atar, sanal ağ arayüzünü (veth pair) oluşturur ve yönlendirme kurallarını yazar.

Kritik nokta şudur: **`NetworkPolicy` nesneleri yalnızca CNI eklentisi onları uyguluyorsa çalışır.** Kubernetes API'sine bir `NetworkPolicy` yazabilirsiniz, `kubectl` bunu memnuniyetle kaydeder, ama eğer CNI eklentiniz bu özelliği desteklemiyorsa (örneğin bazı basit Flannel yapılandırmaları) politika **sessizce görmezden gelinir**. Bu, en tehlikeli yaygın hatalardan biridir: yönetici politikayı yazar, `kubectl get networkpolicy` çıktısında görür ve trafiğin kısıtlandığını sanır — oysa hiçbir şey filtrelenmemektedir.

### Düz Ağ Modeli ve Varsayılan İzin

Kubernetes ağ modelinin temel kuralı: her `Pod` her `Pod` ile NAT olmadan konuşabilir. Bu tasarım basitliği için harikadır, güvenlik için felakettir. Hiçbir `NetworkPolicy` uygulanmadığında bir namespace'teki bir `Pod`, başka bir namespace'teki bir `Pod`'a, node'un kendisine ve genellikle bulut sağlayıcının metadata servisine (örn. `169.254.169.254`) erişebilir. Bu metadata erişimi, bir SSRF veya konteyner ihlali sonrası bulut kimlik bilgilerinin (IAM credentials) çalınmasında klasik bir sıçrama noktasıdır.

---

## Bölüm 2: NetworkPolicy — L3/L4 Segmentasyon

### Çalışma Mantığı

`NetworkPolicy`, `Pod`'lar arası trafiği **etiketler (labels)** üzerinden kontrol eder. IP adresi yerine "hangi etikete sahip Pod'lar" konuşabilir sorusunu cevaplar. Bu, geçici IP sorununu zarifçe çözer: politika `role: frontend` etiketli `Pod`'lardan `role: backend` etiketlilere trafiğe izin verir; IP'ler değişse de etiketler sabit kalır.

Politika mantığının anlaşılması gereken en önemli davranışı **"varsayılan izin, ama seçildiğinde varsayılan ret"** ilkesidir:

- Bir `Pod` **hiçbir** `NetworkPolicy` tarafından seçilmiyorsa, o `Pod`'a tüm trafik açıktır.
- Bir `Pod` **en az bir** `NetworkPolicy` tarafından seçildiği anda, o politika türü (ingress veya egress) için **yalnızca açıkça izin verilen** trafik geçer; geri kalan her şey reddedilir.

Bu ikili davranış çok kritik. `NetworkPolicy` bir izin listesi (allowlist) modelidir; açık bir "deny" kuralı yazamazsınız, yalnızca "şuna izin ver" dersiniz ve seçilen `Pod` için kalan her şey örtük olarak reddedilir.

### Örnek: Default-Deny Temeli

En sağlam başlangıç, bir namespace'te tüm `Pod`'ları seçen ama hiçbir ingress trafiğine izin vermeyen bir politikadır:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: uygulama
spec:
  podSelector: {}          # namespace'teki TÜM Pod'ları seçer
  policyTypes:
  - Ingress
  # ingress kuralı yok => hiçbir gelen trafiğe izin yok
```

Bu temeli kurduktan sonra ihtiyaç duyulan trafiğe tek tek izin verilir. Aynı mantık `Egress` için de uygulanmalıdır — çünkü egress kontrolü, ihlal edilmiş bir `Pod`'un metadata servisine veya dış C2 (command-and-control) sunucusuna ulaşmasını engellemenin ana yoludur.

### NetworkPolicy'nin Sınırları

`NetworkPolicy` bir **L3/L4** aracıdır: IP, port ve protokol düzeyinde çalışır. Şunları **yapamaz**:

- **L7 (uygulama katmanı) kararı veremez.** "Bu `Pod` yalnızca `GET /health` isteği atabilsin ama `POST /admin` atamasın" diyemezsiniz.
- **Kimlik doğrulaması yapmaz.** Etiket bazlı izin, "bu etikete sahip `Pod` gerçekten o mu?" sorusunu sormaz; ağ konumuna güvenir. Bir saldırgan doğru namespace/etikete sahip bir `Pod`'u ihlal ederse, politika ona kapıyı açar.
- **Trafiği şifrelemez.** Küme içi trafik varsayılanda düz metindir; ağı dinleyebilen (örn. ihlal edilmiş bir node, hatalı yapılandırılmış CNI) trafiği okuyabilir.

Bu üç boşluk, servis mesh ve mTLS'in devreye girdiği yerdir.

---

## Bölüm 3: Servis Mesh ve mTLS

### Servis Mesh Nedir?

**Servis mesh** (Istio, Linkerd, Cilium'un mesh yetenekleri vb.), servisler arası iletişimi yöneten bir altyapı katmanıdır. Uygulama kodunu değiştirmeden trafik yönetimi, gözlemlenebilirlik (observability) ve güvenlik sağlar. Klasik mimaride bunu, her `Pod`'un yanına bir **sidecar proxy** (genellikle Envoy) enjekte ederek yapar. Uygulamanın tüm giden ve gelen trafiği bu proxy'den geçer; uygulama bunun farkında bile olmaz.

Linkerd daha hafif, Rust ile yazılmış kendi micro-proxy'sini kullanır; Istio ise Envoy tabanlıdır ve daha geniş özellik setine sahiptir. Yeni yaklaşımlar (Istio'nun **ambient mode**'u gibi) sidecar yerine node düzeyinde bir proxy kullanarak kaynak tüketimini azaltmayı hedefler — ama temel güvenlik mantığı aynı kalır.

### mTLS: Karşılıklı TLS'in Mantığı

Standart TLS'te yalnızca **sunucu** kendini bir sertifikayla kanıtlar (tarayıcının web sitesini doğrulaması gibi). **mTLS (mutual TLS)** ise iki taraflıdır: hem istemci hem sunucu birbirine sertifika sunar ve karşılıklı doğrular. Bu, servis mesh güvenliğinin kalbidir çünkü şu iki şeyi aynı anda sağlar:

1. **Şifreleme:** İki `Pod` arasındaki trafik uçtan uca şifrelenir. Ağı dinleyen bir saldırgan yalnızca şifreli baytları görür.
2. **Güçlü kimlik (identity):** Her iş yükü, ağ konumundan bağımsız kriptografik bir kimliğe sahip olur. Bu kimlik genellikle **SPIFFE** standardı ve **SVID** (SPIFFE Verifiable Identity Document) biçiminde ifade edilir; sertifikanın içine `spiffe://<trust-domain>/ns/<namespace>/sa/<serviceaccount>` gibi bir kimlik gömülür.

İşte bu, `NetworkPolicy`'nin çözemediği "kimlik" boşluğunu kapatır. Artık "IP'si şu olan `Pod`" değil, "kriptografik olarak `payment-service` servis hesabı olduğunu kanıtlayan iş yükü" diyebiliriz. Bir saldırgan doğru namespace'te bir `Pod` ele geçirse bile, hedef servisin kabul edeceği geçerli bir iş yükü sertifikasına sahip değilse mTLS el sıkışması başarısız olur.

### Kimlik Nasıl Dağıtılır?

Mesh'in kontrol düzlemi (Istio'da `istiod`) bir dahili CA (Certificate Authority) gibi davranır. Her `Pod` başladığında sidecar, kendi kimliği (genellikle `Pod`'un `ServiceAccount` token'ı üzerinden doğrulanır) karşılığında kısa ömürlü bir iş yükü sertifikası alır. Bu sertifikalar genellikle saatler mertebesinde geçerlidir ve otomatik yenilenir. Kısa ömür kritik bir savunma özelliğidir: çalınan bir sertifika saldırgana yalnızca dar bir zaman penceresi tanır.

### Yetkilendirme (Authorization) Katmanı

mTLS kimliği doğrular; **yetkilendirme** ise o kimliğin ne yapabileceğini belirler. Istio'da `AuthorizationPolicy`, Linkerd'de `Server` + `ServerAuthorization` benzeri nesnelerle L7 kurallar yazılır. Örneğin: "yalnızca `frontend` servis hesabından gelen ve yalnızca `GET /api/products` yolundaki istekler `catalog` servisine ulaşabilir." Bu, `NetworkPolicy`'nin asla yapamadığı uygulama katmanı segmentasyonudur.

Kavramsal bir Istio örneği:

```yaml
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: catalog-erisim
  namespace: uygulama
spec:
  selector:
    matchLabels:
      app: catalog
  action: ALLOW
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/uygulama/sa/frontend"]
    to:
    - operation:
        methods: ["GET"]
        paths: ["/api/products*"]
```

Buradaki `principals` alanı bir IP değil, mTLS ile kanıtlanmış kriptografik kimliktir. Bu, kimlik tabanlı segmentasyonun (bazen "identity-based microsegmentation" denir) somut halidir.

---

## Bölüm 4: Katmanların Birlikte Çalışması

`NetworkPolicy` ve servis mesh birbirinin **alternatifi değil, tamamlayıcısıdır**. Sağlam bir savunmada:

- **NetworkPolicy (L3/L4):** Ağ düzeyinde geniş, kaba taneli izolasyon sağlar. Mesh'e hiç dahil olmayan trafiği (örn. sidecar'ı olmayan `Pod`'lar, doğrudan node erişimi denemeleri) de kısıtlar. Mesh'i baypas eden trafiği yakalayan bir güvenlik ağıdır.
- **Servis Mesh + mTLS (L7 + kimlik):** İnce taneli, kimlik doğrulamalı, şifreli iletişim sağlar. "Kim, kime, hangi yöntemle" sorusunu cevaplar.

Kritik bir tuzak: Servis mesh mTLS'i "sidecar'dan sidecar'a" şifreler. Ama trafik sidecar'a **ulaşmadan önce**, aynı `Pod` içindeki uygulama ile sidecar arasında localhost üzerinden düz metin akar. Ayrıca sidecar'ı olmayan bir `Pod`, mesh'in yetkilendirmesini tamamen atlayabilir. Bu yüzden mTLS'in **STRICT** modda zorunlu kılınması (aksi halde `PERMISSIVE` mod hem şifreli hem düz metni kabul eder) ve `NetworkPolicy` ile mesh dışı trafiğin kesilmesi birlikte gereklidir.

---

## Bölüm 5: Saldırı Yüzeyi ve Tehditler

### Sidecar Injection'ın Kötüye Kullanımı

Servis mesh sidecar'ları genellikle bir **mutating admission webhook** ile otomatik enjekte edilir: belirli bir etiket (`istio-injection: enabled` gibi) taşıyan namespace'lerdeki yeni `Pod`'lara Envoy konteyneri eklenir. Bu mekanizmanın güvenlik sonuçları:

- **Enjeksiyondan kaçış:** Bir saldırgan `Pod`'unu, injection etiketi olmayan bir namespace'te veya injection'ı devre dışı bırakan bir annotation ile (`sidecar.istio.io/inject: "false"`) başlatabilirse, mesh'in tüm yetkilendirme ve mTLS katmanını atlar. Sidecar olmadan `Pod`, mesh politikalarına görünmez hale gelir. Bu yüzden savunmada, mesh dışı `Pod`'ların ağ erişimi `NetworkPolicy` ile kısıtlanmalıdır.
- **Webhook'un kendisi bir hedeftir:** Admission webhook'u ele geçiren veya değiştirebilen bir saldırgan, enjekte edilen sidecar yapılandırmasını manipüle ederek trafiği yönlendirebilir veya kimlik doğrulamasını zayıflatabilir.

### Sidecar'ın İmtiyazlı Doğası

Sidecar proxy'nin trafiği yakalayabilmesi için, `Pod` başlatılırken bir **init container** (Istio'da `istio-init`) `iptables` kurallarını yazar. Bu init container genellikle `NET_ADMIN` ve `NET_RAW` yeteneklerine (capabilities) ihtiyaç duyar. Bu imtiyazlar, konteyner ihlali senaryolarında saldırganın ağ katmanını manipüle etmesi için bir kaldıraç olabilir. CNI-tabanlı injection yöntemleri (init container yerine CNI eklentisinin kuralları yazması) bu imtiyaz ihtiyacını azaltmak için tercih edilir.

### mTLS'in Yanlış Yapılandırılması

- **PERMISSIVE mod tuzağı:** Geçiş kolaylığı için mesh'ler genellikle `PERMISSIVE` mTLS ile başlar; bu mod hem mTLS hem düz metin trafiği kabul eder. Yönetici "mTLS açık" sanır ama saldırgan basitçe düz metin bağlantısı kurarak sertifika doğrulamasını atlar. Üretimde **STRICT** mod zorunludur.
- **Yetkilendirme boşlukları:** mTLS açık ama hiçbir `AuthorizationPolicy` yoksa, kimlik doğrulanır ama herkes her şeye erişebilir — kimlik var, ama kural yok. Bir "default-deny" `AuthorizationPolicy` temeli, tıpkı `NetworkPolicy`'deki gibi, esastır.

### Kontrol Düzlemi ve Metadata Saldırıları

Mesh'in kontrol düzlemi CA olarak davrandığı için, `istiod` benzeri bileşenlerin ele geçirilmesi tüm kümenin kimlik sistemini çökertir — saldırgan istediği kimlikte sertifika basabilir. Ayrıca egress kontrolü zayıfsa, ihlal edilmiş bir `Pod` bulut metadata servisine ulaşıp node'un IAM rolünü çalabilir; mesh içi mTLS bu dış hedefe giden trafiği korumaz.

---

## Bölüm 6: Tespit ve Savunma

### Savunma Kontrol Listesi

**Ağ katmanı (NetworkPolicy / CNI):**
- CNI eklentinizin `NetworkPolicy`'yi gerçekten uyguladığını **doğrulayın** (Calico, Cilium destekler; bazı Flannel kurulumları desteklemez). Test için: bir default-deny politikası uygulayın ve engellenmesi gereken trafiğin gerçekten engellendiğini aktif olarak test edin — "kaydedildi" görmek yetmez.
- Her namespace için **default-deny ingress ve egress** temeli kurun, sonra ihtiyaç kadar açın.
- **Egress kontrolünü ihmal etmeyin:** metadata servisine (`169.254.169.254`) ve bilinmeyen dış IP'lere giden trafiği kısıtlayın. Bu, veri sızdırma ve kimlik bilgisi hırsızlığına karşı en etkili tek kontroldür.
- `kube-system` ve hassas namespace'leri katı politikalarla izole edin.

**Mesh katmanı (mTLS / yetkilendirme):**
- mTLS'i küme genelinde **STRICT** moda alın; `PERMISSIVE`'i yalnızca geçiş sırasında ve geçici tutun.
- **Default-deny `AuthorizationPolicy`** temeli kurun; erişimi açıkça izin verilen kimlik ve yollarla sınırlayın.
- Sidecar injection'ın **zorunlu** olduğundan emin olun; injection'ı atlayan `Pod`'ları admission control (örn. bir policy engine ile) reddedin veya en azından `NetworkPolicy` ile mesh dışı trafiği kesin.
- İş yükü sertifikalarının kısa ömürlü ve otomatik rotasyonlu olduğunu doğrulayın.

### Tespit ve İzleme

- **Sidecar'sız `Pod`'ları avlayın:** Mesh'e dahil olması beklenen namespace'lerde sidecar konteyneri olmayan `Pod`'lar bir kaçış/atlama işaretidir. Beklenen ve gerçek sidecar sayısını periyodik karşılaştırın.
- **mTLS reddedilme ve düz metin bağlantı metriklerini** izleyin. Envoy/proxy telemetrisi, başarısız mTLS el sıkışmalarını ve `PERMISSIVE` modda kabul edilen düz metin bağlantılarını raporlar; bu ikincisi bir alarm konusudur.
- **`AuthorizationPolicy` reddedilmeleri (deny logs):** Beklenmedik kaynaklardan gelen ve reddedilen istek artışı, yanal hareket (lateral movement) denemesinin işareti olabilir.
- **Ağ akış logları (flow logs):** Cilium (Hubble ile) veya Calico gibi CNI'lar, `NetworkPolicy` tarafından reddedilen akışları loglayabilir. `default-deny` sonrası reddedilen trafik desenleri hem yanlış yapılandırmayı hem de saldırıyı ortaya çıkarır.
- **Admission webhook değişikliklerini** izleyin: injection webhook'unun yapılandırmasının veya `MutatingWebhookConfiguration` nesnelerinin beklenmedik değişimi kritik bir olaydır.
- **Metadata servisine giden trafiği** özellikle izleyin; `Pod`'lardan `169.254.169.254`'e beklenmedik erişim, kimlik bilgisi hırsızlığı denemesinin klasik göstergesidir.

---

## Bölüm 7: Yaygın Hatalar Özeti

1. **"Politika yazdım, güvendeyim" yanılgısı:** CNI'ın politikayı desteklemediği durumda `NetworkPolicy` sessizce yok sayılır. Her zaman aktif test edin.
2. **Egress'i unutmak:** Çoğu ekip yalnızca ingress'i kısıtlar; oysa veri sızdırma ve C2 iletişimi egress üzerinden gerçekleşir.
3. **PERMISSIVE mTLS'i üretimde bırakmak:** Şifreleme "açık görünür" ama düz metin hâlâ kabul edilir.
4. **mTLS'i yetkilendirme olmadan kullanmak:** Kimlik doğrulanır ama herkes her yere erişir; default-deny yetkilendirme temeli yoktur.
5. **Sidecar injection'ı isteğe bağlı bırakmak:** Injection'ı atlayan `Pod`'lar tüm mesh güvenliğini baypas eder.
6. **Mesh'i tek savunma sanmak:** Mesh dışı ve node düzeyi trafik için `NetworkPolicy` gereklidir; iki katman birbirini tamamlar.
7. **Kontrol düzlemini zayıf korumak:** CA rolündeki mesh kontrol düzlemi ele geçirilirse tüm kimlik sistemi çöker.

---

## Sonuç

Kubernetes'te ağ güvenliği, IP ve port düşüncesinden **etiket ve kimlik** düşüncesine geçmeyi gerektirir. `NetworkPolicy` (CNI eklentileriyle) L3/L4 düzeyinde etiket tabanlı segmentasyonu sağlar; servis mesh ve mTLS ise L7 düzeyinde kriptografik kimlik, şifreleme ve ince taneli yetkilendirme ekler. İkisi birlikte, geçici IP'ler dünyasında güvenilir bir east-west izolasyon oluşturur.

Savunmanın özü üç ilkede toplanır: **her katmanda default-deny temeli kur**, **mesh'i zorunlu ve STRICT yap**, ve **hiçbir katmanın tek başına yeterli olmadığını bilerek katmanları üst üste bindir (defense in depth)**. En tehlikeli açık, çoğu zaman egzotik bir zafiyet değil, "politika yazdım ama uygulanmıyor" ya da "mTLS açık ama düz metin de kabul ediliyor" gibi sessiz yanlış yapılandırmalardır. Bu yüzden yazmak yetmez; her kontrolü aktif olarak test etmek ve sürekli izlemek şarttır.
