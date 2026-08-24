# Kubernetes (Geliştirici Bakışı)

Bu makale Kubernetes'i bir platform mühendisi gözünden değil, uygulamasını konteynerleştirip bu platforma teslim eden bir **geliştirici** gözünden ele alır. Yani cluster'ı kim kurdu, `etcd` nasıl yedekleniyor, kubelet hangi cgroup sürümünü kullanıyor gibi altyapı sorularına girmeyeceğiz. Odağımız şu: Yazdığım kod bir Pod içinde nasıl çalışır, nasıl ölçeklenir, konfigürasyonu ve gizli bilgileri (secret) nasıl güvenli biçimde alır, ve gerçek dünyada geliştiricilerin hangi tuzaklara düştüğü.

## Kubernetes Neden Var: Kök Neden

Konuya girmeden önce "neden böyle bir şeye ihtiyaç duyuldu" sorusunu cevaplamak, geri kalan her kararı anlamlı kılar. Docker bize tek bir konteyneri paketleyip çalıştırmayı verdi. Ama üretim ortamı tek bir konteyner değildir. Onlarca kopyanın çalışması, birinin çökünce yerine yenisinin gelmesi, trafiğin bunlar arasında dağıtılması, yeni sürümün eskisini kesintisiz devralması, makinelerden biri arızalanınca yükün başka makineye kayması gerekir.

Bu işleri elle veya kabuk scriptleriyle yapmak, hızla yönetilemez bir karmaşaya dönüşür. İşte Kubernetes'in çözdüğü asıl problem budur: **arzu edilen durumu (desired state) beyan edersin, o da gerçek durumu (actual state) sürekli buna yaklaştırır.** Bu "declarative" (bildirimsel) yaklaşım, Kubernetes'in kalbindeki **reconciliation loop** (uzlaştırma döngüsü) ile mümkün olur. Sen "3 kopya çalışsın" dersin; bir controller sürekli döner, "şu an kaç kopya var?" diye kontrol eder, eksikse yaratır, fazlaysa siler. Sen bir kere niyetini bildirdikten sonra sistem o niyeti korumaya çalışır. Bu, geliştirici olarak Kubernetes ile kurduğun ilişkinin temel felsefesidir: emir vermezsin, hedef tanımlarsın.

## Pod: Temel Yapı Taşı

### Tanım

Kubernetes'te dağıttığın en küçük birim konteyner değil, **Pod**'dur. Bu ayrım kritiktir. Bir Pod, bir veya birden çok konteyneri birlikte saran bir zarftır. Aynı Pod içindeki konteynerler aynı ağ ad alanını (network namespace) paylaşır; yani birbirlerine `localhost` üzerinden ulaşırlar ve aynı IP adresini kullanırlar. Ayrıca `volume` üzerinden aynı dosya sistemini paylaşabilirler.

### Kök Neden: Neden Konteyner Değil de Pod?

Buradaki tasarım kararı ilk bakışta gereksiz bir soyutlama gibi görünür. "Neden doğrudan konteyner dağıtmıyoruz?" Cevap, birlikte yaşamak zorunda olan yardımcı süreçlerle ilgilidir. Bazı durumlarda ana uygulamanın yanında bir yardımcı proses koşmak istersin: logları toplayan bir agent, trafiği yakalayan bir service mesh proxy'si (sidecar deseni), ya da ana konteyner başlamadan önce hazırlık yapan bir kurulum konteyneri (init container). Bunların ana uygulamayla aynı ağ ve yaşam döngüsünü paylaşması gerekir. Pod, "bu konteynerler ayrılamaz, birlikte planlanmalı, birlikte aynı makinede çalışmalı" demenin yoludur.

Ama pratikte önemli bir kural şu: **çoğu Pod tek konteyner içermelidir.** Sidecar gerçekten gerektiğinde çok-konteynerli Pod'a başvurulur. "Uygulama + veritabanı aynı Pod'da" gibi bir tasarım neredeyse her zaman hatadır, çünkü ikisinin ölçekleme ve yaşam döngüsü ihtiyaçları farklıdır.

### Pod'ların Ölümlü (Ephemeral) Doğası

Geliştiricilerin en çok yanıldığı nokta budur: **Pod'lar kalıcı değildir.** Bir Pod her an ölebilir; node arızalanır, sürüm güncellenir, cluster yeniden dengeler. Yeni gelen Pod'un IP adresi farklı olur, adı farklı olur, üzerindeki yerel disk sıfırlanır. Bu yüzden bir Pod'a doğrudan bağlanmak, yerel diske kalıcı veri yazmak veya "hep aynı Pod bana cevap versin" beklemek, mimarinin ruhuna aykırıdır. Bu ölümlülüğü kabul etmek, stateless (durumsuz) uygulama tasarlamayı zorunlu kılar; durumu Pod'un dışına (veritabanı, nesne deposu, cache servisi) taşırsın.

## Deployment: Pod'ları Yönetmenin Doğru Yolu

### Tanım

Neredeyse hiçbir zaman Pod'u elle (çıplak Pod olarak) oluşturmazsın. Bunun yerine bir **Deployment** tanımlarsın. Deployment, "şu imajdan, şu ayarlarla, şu kadar kopya (replica) çalışsın" diyen üst seviye bir nesnedir. Arada bir de **ReplicaSet** vardır; Deployment aslında ReplicaSet'leri yönetir, ReplicaSet de Pod'ları yönetir. Geliştirici olarak çoğunlukla Deployment ile ilgilenirsin, ReplicaSet perde arkasında kalır.

### Kök Neden: Deployment Ne Sağlar?

Deployment'ın asıl değeri iki yerde ortaya çıkar. Birincisi **kendini iyileştirme (self-healing)**: Bir Pod çökerse Deployment'ın altındaki ReplicaSet controller'ı bunu fark eder ve yenisini başlatır, çünkü "3 replica olmalı" hedefiyle gerçek durum arasındaki farkı kapatmak onun görevidir. İkincisi **kontrollü güncelleme (rolling update)**: Yeni bir imaj sürümü dağıttığında Deployment eski Pod'ları hepsini birden öldürmez. Bunun yerine adım adım yeni Pod'ları ayağa kaldırır, hazır olduklarını doğrular, sonra eskilerini kapatır. Böylece kesintisiz geçiş sağlanır ve bir şey ters giderse `rollback` (önceki sürüme dönüş) mümkün olur.

### Somut Örnek

Basit bir Deployment tanımı şöyle görünür:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-api
  template:
    metadata:
      labels:
        app: web-api
    spec:
      containers:
        - name: web-api
          image: kayit-defterim/web-api:1.4.2
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              memory: "512Mi"
```

Burada dikkat edilmesi gereken birkaç kritik nokta var. `selector.matchLabels` ile `template.metadata.labels` **birbiriyle eşleşmek zorundadır**; Deployment, hangi Pod'ların kendisine ait olduğunu bu etiket (label) üzerinden anlar. Eşleşmezse Kubernetes tanımı reddeder. Bu label mekanizması Kubernetes'in her yerinde tekrar eder: nesneler birbirini isimle değil, etiketle bulur. Bu, gevşek bağlı (loosely coupled) bir sistem kurmanın anahtarıdır.

### İmaj Etiketleme Tuzağı: `latest` Kullanma

Yukarıdaki örnekte imajı `1.4.2` gibi belirli bir sürümle etiketledim, `latest` ile değil. Bu bilinçli bir tercih. `latest` etiketi kullanmak, hangi kodun çalıştığını belirsizleştirir ve reconciliation mantığını bozar: Kubernetes Pod spec'i değişmediği sürece yeniden dağıtım yapmaz, ama `latest`'in arkasındaki gerçek imaj sessizce değişmiş olabilir. Sonuç, iki farklı node'da iki farklı kodun çalışması gibi hata ayıklaması cehennem olan durumlardır. Her zaman değişmez (immutable), sürümlenmiş imaj etiketleri kullan.

## Service: Kararsız Pod'lara Kararlı Adres

### Tanım ve Kök Neden

Az önce Pod'ların ölümlü olduğunu ve IP'lerinin değiştiğini söyledik. Peki uygulaman başka bir uygulamaya nasıl ulaşacak, eğer hedefin adresi sürekli değişiyorsa? İşte **Service** tam olarak bu problemi çözer. Service, arkasındaki (etiketle seçtiği) Pod grubunun önüne sabit bir sanal IP (ClusterIP) ve sabit bir DNS adı koyar. Sen `web-api` adına istek atarsın; Service bu isteği o an sağlıklı olan Pod'lardan birine dağıtır (load balancing). Pod'lar gelip gitse de Service'in adresi sabit kalır.

Buradaki mekanizmayı anlamak önemli: Service, hangi Pod'ların sağlıklı olduğunu **Endpoints** (veya daha yeni EndpointSlice) üzerinden takip eder. Bir Pod hazır olduğunu (readiness probe ile) bildirdiğinde Service'in trafik dağıttığı listeye eklenir; sağlıksızsa listeden çıkarılır. Bu yüzden readiness probe tanımlamak, kesintisiz dağıtımın gizli kahramanıdır; onsuz Service henüz hazır olmayan bir Pod'a trafik gönderebilir.

### Service Türleri

Geliştirici olarak en çok karşılaşacağın türler şunlardır:

- **ClusterIP** (varsayılan): Service'e yalnızca cluster içinden erişilebilir. Cluster içi servisler arası iletişim için idealdir. Dışarıya açık değildir.
- **NodePort**: Her node üzerinde belirli bir portu açar. Basit ama kaba bir dışarı açma yöntemidir; üretimde nadiren doğrudan tercih edilir.
- **LoadBalancer**: Bulut sağlayıcının yük dengeleyicisini devreye sokarak Service'i dışarı açar. Bulut ortamlarında dış erişim için yaygın yoldur.

HTTP tabanlı dış trafik için çoğu ekip Service türlerinin ötesinde **Ingress** ya da daha yeni **Gateway API** kullanır; bunlar tek bir giriş noktasından yol (path) ve alan adına (host) göre yönlendirme, TLS sonlandırma gibi işleri yapar. Bir geliştirici olarak "içeriden konuşuyorsam ClusterIP + DNS adı, dışarıya HTTP açıyorsam Ingress" diye kabaca konumlandırabilirsin.

### Somut Örnek: DNS ile Servis Keşfi

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-api
spec:
  selector:
    app: web-api
  ports:
    - port: 80
      targetPort: 8080
```

Bu Service, `app: web-api` etiketli Pod'ları seçer, dışarıya 80 portundan bakar, ama trafiği Pod'un 8080 portuna (`targetPort`) yönlendirir. Artık aynı namespace içindeki başka bir uygulama, koda IP gömmek yerine sadece `http://web-api` adresine istek atabilir. Kubernetes'in iç DNS'i bu adı otomatik çözer. Farklı namespace'ten ulaşmak gerekiyorsa tam ad `web-api.<namespace>.svc.cluster.local` biçimindedir. Bu servis keşfi (service discovery) mekanizması, mikroservislerin birbirini sabit adreslerle bulmasını sağlar ve konfigürasyona IP gömme kötü alışkanlığını ortadan kaldırır.

## Ölçekleme: Yatay, Dikey ve Otomatik

### Yatay Ölçekleme (Horizontal Scaling)

Ölçeklemenin en doğal biçimi yataydır: aynı uygulamanın daha çok kopyasını çalıştırmak. Deployment'taki `replicas` değerini artırırsın, yeni Pod'lar doğar, Service trafiği aralarında paylaştırır. Bunun neden çalıştığını hatırla: Pod'lar stateless olduğu için birbirinin yerine geçebilirler, hangi kopyanın cevap verdiği önemli değildir. İşte bu yüzden "state'i dışarı taşı" ilkesi bu kadar önemliydi; durumsuz uygulama sınırsıza yakın yatay ölçeklenebilir, durumlu uygulama ise ölçeklerken tutarlılık problemleriyle boğuşur.

### Otomatik Ölçekleme (HPA)

Yükü elle tahmin edip `replicas` sayısını sürekli değiştirmek pratik değildir. **HorizontalPodAutoscaler (HPA)** bu işi otomatikleştirir: Bir metriği (tipik olarak CPU kullanımı veya özel bir metrik) izler, hedef eşiğin üstüne çıkınca replica sayısını artırır, altına inince azaltır. Bu yine bir reconciliation loop'tur; "ortalama CPU %60 olsun" hedefini korumaya çalışır.

HPA'nın kritik ön koşulu şudur: **Pod'ların `resources.requests` değeri tanımlı olmalıdır.** HPA, CPU kullanımını bu `request` değerine oranla hesaplar. Request tanımlamazsan HPA CPU tabanlı ölçeklemeyi doğru yapamaz. Bu, geliştiricilerin en sık atladığı ve "neden ölçeklenmiyor?" diye saatlerce uğraştığı noktalardan biridir.

### Dikey Ölçekleme ve Kaynak İstekleri

Dikey ölçekleme, tek bir Pod'a daha çok CPU/bellek vermektir. Genelde yatay ölçekleme tercih edilse de, kaynak taleplerini doğru ayarlamak her iki durumda da hayatidir. Burada `requests` ve `limits` ayrımını netleştirmek gerekir, çünkü bu ayrım yanlış anlaşıldığında ciddi sorunlar doğurur:

- **`requests`**: Scheduler'ın (planlayıcının) Pod'u bir node'a yerleştirirken garanti ettiği minimum kaynaktır. "Bu Pod en az bu kadar CPU/belleğe ihtiyaç duyar" demektir. Scheduler yerleştirme kararını buna göre verir.
- **`limits`**: Pod'un aşamayacağı üst sınırdır.

Bu ikisi arasındaki fark, en tehlikeli tuzaklardan birine yol açar. Bellek `limit`ini aşan bir konteyner **OOMKilled** (Out Of Memory ile öldürülme) olur; işletim sistemi onu anında sonlandırır. CPU `limit`ini aşan bir konteyner ise öldürülmez, **throttle** edilir (yavaşlatılır). Bu yüzden bellek limitlerini gerçekçi vermek kritiktir; çok düşük verirsen uygulaman sebepsiz yere sürekli yeniden başlıyor gibi görünür, oysa gizli sebep OOMKilled'dır.

### CPU Limit Tartışması

Deneyimli ekiplerde sık tartışılan bir konu: bazı durumlarda CPU `limit` koymamak, yalnızca `request` koymak daha iyi sonuç verebilir, çünkü CPU throttling gecikme (latency) sıçramalarına yol açabilir. Bunun doğru cevabı iş yüküne bağlıdır ve tek bir kesin kural yoktur; ama önemli olan, geliştiricinin `limit`in "izin verilen tavan" değil, "aşınca ceza" anlamına geldiğini bilmesidir. Bellekte ceza ölüm, CPU'da ceza yavaşlamadır.

## Konfigürasyon: ConfigMap

### Tanım ve Kök Neden

Uygulamanın davranışını değiştiren ama gizli olmayan ayarları (veritabanı adresi, özellik bayrakları, log seviyesi, zaman aşımı değerleri) koda ya da imaja gömmemelisin. Neden? Çünkü aynı imajı farklı ortamlarda (development, staging, production) çalıştırmak istersin ve her ortam için imajı yeniden derlemek büyük bir israftır. Bu, on iki faktörlü uygulama (twelve-factor app) prensiplerinden birinin doğrudan uygulamasıdır: **konfigürasyonu koddan ayır.**

**ConfigMap** tam olarak bu ayrımı sağlar. Ayarları cluster'da ayrı bir nesne olarak tutarsın, uygulaman bunları çalışma anında okur. Aynı imaj, farklı ConfigMap ile farklı ortamda farklı davranır.

### İki Kullanım Biçimi: Env Değişkeni ve Dosya

ConfigMap'i uygulamana iki yolla verebilirsin:

1. **Ortam değişkeni (environment variable) olarak**: Basit anahtar-değer ayarlar için idealdir.
2. **Bağlanmış dosya (mounted volume) olarak**: Bir konfigürasyon dosyasının tamamını (örneğin bir `.json` veya `.yaml` ayar dosyası) Pod'un dosya sistemine yerleştirmek için kullanılır.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-api-config
data:
  LOG_LEVEL: "info"
  REQUEST_TIMEOUT: "30"
```

Deployment içinde bunu ortam değişkeni olarak şöyle bağlarsın:

```yaml
      containers:
        - name: web-api
          image: kayit-defterim/web-api:1.4.2
          envFrom:
            - configMapRef:
                name: web-api-config
```

### Kritik Tuzak: ConfigMap Güncellemesi Otomatik Yeniden Başlatmaz

Burada geliştiricileri en çok şaşırtan davranış şudur: ConfigMap'i ortam değişkeni olarak bağladıysan ve sonradan ConfigMap'i değiştirdiysen, çalışan Pod'lar **eski değeri kullanmaya devam eder.** Ortam değişkenleri konteyner başlarken bir kez okunur; canlı olarak güncellenmez. Değişikliğin geçerli olması için Pod'un yeniden başlatılması (rollout restart) gerekir.

Volume olarak bağlanan ConfigMap'ler bir süre sonra güncellenir (kubelet dosyayı tazeler), ama uygulaman bu dosyayı yeniden okumadıkça yine eski değerle çalışır. Yani "ConfigMap'i değiştirdim ama uygulama hâlâ eskisini görüyor" şikâyetinin neredeyse tamamı bu mekanizmayı yanlış anlamaktan kaynaklanır. Doğru refleks: konfigürasyon değişince ilgili Deployment'a bilinçli bir yeniden dağıtım tetiklemek.

## Secret: Gizli Bilgilerin Yönetimi

### Tanım ve ConfigMap'ten Farkı

Veritabanı parolası, API anahtarı, TLS sertifikası gibi hassas bilgileri ConfigMap'te tutmamalısın. Bunlar için **Secret** vardır. Kullanım biçimi ConfigMap'e çok benzer (env değişkeni veya dosya olarak bağlanır), ama amacı ve muamelesi farklıdır: Secret gizli veriler içindir ve Kubernetes bunları biraz daha dikkatli ele alır.

### Kök Neden ve Yaygın Yanılgı: base64 Şifreleme Değildir

Burada en tehlikeli yanılgıyı hemen düzeltmek gerekir: **Secret'lar varsayılan olarak base64 ile kodlanır, ama base64 bir şifreleme (encryption) değil, yalnızca bir kodlamadır (encoding).** Yani Secret manifesti eline geçen herkes değeri anında çözebilir. base64, gizliliği değil, ikili (binary) veriyi metin olarak taşınabilir kılmayı sağlar. Bu ayrımı bilmemek, "Secret kullandım demek ki güvende" gibi yanlış bir güven duygusuna yol açar.

Gerçek koruma birkaç katmandan gelir:

- **`etcd` şifrelemesi (encryption at rest)**: Cluster yöneticisinin Secret'ların depoda şifreli tutulmasını yapılandırması gerekir. Bu geliştiricinin değil, platform ekibinin sorumluluğudur ama geliştirici olarak bunun yapılıp yapılmadığını sormalısın.
- **RBAC (Role-Based Access Control)**: Secret'ları kimin okuyabileceğini sınırlar. Herkesin her Secret'ı okuyabildiği bir cluster, base64'ün zaten sağlamadığı gizliliği tümüyle yok eder.
- **Harici secret yönetimi**: Ciddi ortamlarda Secret'lar çoğunlukla harici bir gizli bilgi kasasında (external secrets operator gibi araçlarla dış bir vault sistemine bağlanarak) tutulur ve cluster'a senkronlanır.

### Somut Örnek

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  DB_PASSWORD: "gercek-parola-buraya"
```

Burada `stringData` alanını kullandım; bu alan değerleri düz metin girmene izin verir ve Kubernetes base64 kodlamayı senin yerine yapar (elle base64'e çevirip `data` alanına yazma zahmetini ortadan kaldırır). Deployment içinde tek bir Secret anahtarını ortam değişkeni olarak bağlamak şöyle görünür:

```yaml
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: DB_PASSWORD
```

### En Büyük Secret Hatası: Git'e Sızdırmak

Geliştiricilerin başına gelen en yıkıcı hata, Secret manifestini (içindeki base64 değeriyle birlikte) doğrudan Git deposuna commit etmektir. base64 çözülebilir olduğu için, bu commit'i gören herkes parolayı ele geçirir. Ve Git geçmişi kalıcıdır; dosyayı sonradan silsen bile geçmişte durur. Doğru yaklaşım, gerçek Secret değerlerini asla kod deposuna koymamaktır. GitOps kullanan ekipler bunun için `sealed secrets` gibi şifreleyen araçlara ya da harici vault sistemlerine başvurur; böylece depoda yalnızca şifreli veya referans halinde bilgi durur, gerçek sır durmaz.

## Sağlık Kontrolleri: Probe'lar

Ölçekleme ve kesintisiz dağıtımın işe yaraması, Kubernetes'in bir Pod'un ne zaman "sağlıklı" ve "hazır" olduğunu bilmesine bağlıdır. Bunu **probe** (yoklama) mekanizmasıyla yapar ve geliştirici olarak bunları doğru tanımlamak senin sorumluluğundadır:

- **Liveness probe**: "Bu konteyner hâlâ hayatta mı?" Başarısız olursa Kubernetes konteyneri yeniden başlatır. Ölü kilitlenmiş (deadlock) bir uygulamayı kurtarmak içindir.
- **Readiness probe**: "Bu konteyner trafik almaya hazır mı?" Başarısız olursa konteyner öldürülmez ama Service'in trafik dağıttığı listeden çıkarılır. Uygulama açılışta bir önbelleği ısıtıyor veya bağlantı kuruyorsa, hazır olana kadar trafik gönderilmemesini bu sağlar.
- **Startup probe**: Yavaş açılan uygulamalar içindir; liveness probe'un erken tetiklenip yavaş başlayan bir uygulamayı boş yere öldürmesini engeller.

Buradaki en yaygın hata, liveness ve readiness probe'u aynı ağır kontrole bağlamaktır. Örneğin liveness probe'un veritabanına bağlanmayı denemesi tehlikelidir: Veritabanı geçici olarak yavaşlarsa liveness başarısız olur, Kubernetes tüm Pod'ları yeniden başlatır, bu da yükü artırır ve sorunu büyütür (ölüm sarmalı). Liveness probe olabildiğince hafif ve yalnızca "süreç kilitlenmemiş mi" sorusunu yanıtlayan bir kontrol olmalıdır; bağımlılıkların durumu readiness probe'a aittir.

## Namespace ve Kaynak Yönetimi

**Namespace**, cluster'ı mantıksal bölmelere ayıran bir mekanizmadır. Farklı ekipler, farklı ortamlar veya farklı uygulamalar ayrı namespace'lerde yaşayabilir. İsim çakışmalarını önler (aynı `web-api` adı iki namespace'te sorunsuz var olabilir) ve RBAC ile erişim sınırlarını çizmeyi kolaylaştırır. DNS çözümlemesinin namespace'e duyarlı olduğunu Service bölümünde görmüştük; bu yüzden farklı namespace'teki bir servise ulaşırken tam adı kullanmak gerekir.

Namespace düzeyinde **ResourceQuota** ve **LimitRange** ile kaynak kullanımı sınırlanabilir. Bu genelde platform ekibinin işidir ama geliştirici olarak "Pod'um neden yaratılamıyor?" sorusunun cevabı bazen namespace kotasının dolmasıdır; `resources.requests` tanımlamayan bir Pod, LimitRange olan bir namespace'te reddedilebilir.

## Geliştiriciler İçin Yaygın Hatalar ve En İyi Pratikler

Buraya kadar anlattıklarımızı geliştirici perspektifinden bir kontrol listesine dönüştürelim. Bunlar gerçek dünyada tekrar tekrar karşılaşılan tuzaklardır.

**1. `latest` imaj etiketi kullanmak.** Hangi kodun çalıştığını belirsizleştirir ve yeniden dağıtımı öngörülemez kılar. Her zaman değişmez, sürümlü etiketler kullan.

**2. Kaynak `requests` ve `limits` tanımlamamak.** Requests olmadan scheduler kör kalır, HPA çalışmaz, ve bir Pod bir node'un tüm kaynağını yiyip komşularını aç bırakabilir (noisy neighbor). Her konteyner için en azından anlamlı bir memory limit ve CPU/memory request tanımla.

**3. Probe'ları eksik veya yanlış tanımlamak.** Readiness probe olmadan kesintisiz dağıtım hayaldir; hazır olmayan Pod'a trafik gider. Liveness probe'u ağır bağımlılık kontrolüne bağlamak ise ölüm sarmalı doğurur.

**4. State'i Pod'un yerel diskine yazmak.** Pod öldüğünde veri kaybolur. Kalıcı veri için `PersistentVolume` kullan ya da durumu tümüyle harici servise taşı.

**5. Secret'ı base64 ile "güvenli" sanmak veya Git'e commit etmek.** base64 şifreleme değildir. Gerçek sırları depoya asla koyma; etcd şifrelemesi ve RBAC'ın devrede olduğundan emin ol.

**6. ConfigMap/Secret değişince yeniden dağıtımı unutmak.** Env değişkeni olarak bağlı konfigürasyon canlı güncellenmez. Değişiklikten sonra Deployment'ı bilinçli yeniden başlat.

**7. Her şeyi tek Pod'a tıkıştırmak.** Uygulama ve veritabanını, ya da bağımsız ölçeklenmesi gereken bileşenleri aynı Pod'a koymak yanlıştır. Ayrı yaşam döngüleri ayrı Deployment'lar ister.

**8. Namespace ve label disiplinsizliği.** Tutarlı etiketleme, Service'lerin doğru Pod'ları bulmasını ve senin kaynakları filtreleyip yönetmeni sağlar. Label şeması baştan düşünülmelidir.

**En iyi pratiklerin özü** ise şu felsefeye dayanır: Bildirimsel düşün, her şeyi versiyon kontrollü YAML olarak tanımla (GitOps), uygulamanı durumsuz ve öldürülmeye hazır tasarla, konfigürasyonu ve sırları koddan ayır, ve Kubernetes'e "hedefini" söyle, "adımlarını" değil. Bu ilkeleri içselleştirdiğinde, platformun karmaşıklığının büyük kısmı senin için görünmez hale gelir; çünkü sistem, senin bildirdiğin niyeti korumak üzere zaten sürekli çalışmaktadır.

## Kapanış

Geliştirici olarak Kubernetes ile ilişkin, birkaç temel nesne etrafında döner: kodun bir **Pod**'da yaşar, bir **Deployment** onu çoğaltıp iyileştirir, bir **Service** ona kararlı bir adres verir, **HPA** yükü karşılamak için otomatik ölçekler, **ConfigMap** ve **Secret** ise davranışı ve sırları koddan ayrı tutar. Bunların hepsinin altında yatan tek fikir uzlaştırma döngüsüdür: sen niyetini bildirirsin, sistem gerçeği o niyete yaklaştırır. Bu makalede altını çizdiğimiz tuzakların çoğu, bu bildirimsel ve ölümlü doğayı yeterince ciddiye almamaktan kaynaklanır. Pod'ların öleceğini, konfigürasyonun canlı yenilenmediğini, base64'ün şifreleme olmadığını içselleştirdiğinde, Kubernetes şaşırtıcı bir platformdan öngörülebilir bir araca dönüşür.
