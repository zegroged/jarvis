# Service Mesh Mimarisi: Istio/Linkerd, Sidecar Proxy ve mTLS Otomasyonu

## Giriş: Bu Katman Neden Var?

Bir mikroservis mimarisinde onlarca, yüzlerce servis birbiriyle konuşur. Her servisin kendi içinde "B servisine bağlanırken TLS kullan, 3 kez retry dene, 500ms timeout uygula, hata oranında circuit breaker aç" gibi mantığı tekrar tekrar yazması hem iş gücü hem tutarsızlık demektir. Java servisi retry'i bir kütüphaneyle yapar, Go servisi başka bir kütüphaneyle, Python servisi belki hiç yapmaz. Gözlemlenebilirlik (observability) de dağılır: her dilde farklı metrik/trace kütüphanesi.

Service mesh, bu "servisler-arası iletişim" sorumluluğunu uygulama kodundan çıkarıp altyapı katmanına taşır. Fikir şöyle: her servis instance'ının yanına (pod içine) küçük bir ağ proxy'si (sidecar) koy; servisin bütün giden/gelen trafiği bu proxy'den geçsin. Proxy; şifreleme, kimlik doğrulama, retry, timeout, devre kesici (circuit breaker), trafik yönlendirme (canary/A-B), ve telemetri toplama işini merkezi ve tutarlı şekilde yapar. Uygulama kodu bunlardan habersizdir — sadece localhost'a konuşur, gerisini proxy halleder.

Bunu anlamak savunma açısından kritiktir çünkü mesh, network katmanındaki güveni (trust) uygulamadan platforma taşır. Bu hem çok güçlü bir savunma katmanı (otomatik mTLS, ağ genelinde politika) hem de yeni, tek bir hata noktası (control plane, sidecar) yaratır. Bu makale mekanizmayı, doğru kullanımı ve bu yeni saldırı yüzeyini savunmacı gözüyle ele alıyor.

## Temel Mimari: Data Plane ve Control Plane Ayrımı

Her service mesh iki katmandan oluşur:

**Data plane**: Gerçek trafiğin aktığı yer. Her pod'a enjekte edilen sidecar proxy'ler (Istio'da Envoy, Linkerd'de Rust ile yazılmış kendi hafif proxy'si — linkerd2-proxy) burada yaşar. Bir servisten giden her paket, önce kendi sidecar'ından çıkar, hedef servisin sidecar'ına girer, oradan hedef container'a ulaşır. Yani A -> B çağrısı aslında A -> A'nın sidecar'ı -> B'nin sidecar'ı -> B şeklinde ilerler.

**Control plane**: Sidecar'lara ne yapacaklarını söyleyen merkezi beyin. Istio'da bu `istiod` bileşeni; sertifika üretimi/dağıtımı (Citadel işlevi), trafik politikalarının (VirtualService, DestinationRule gibi Kubernetes CRD'leri) Envoy konfigürasyonuna (xDS protokolü ile) çevrilip sidecar'lara push edilmesi ve servis keşfi (service discovery) buradan yönetilir. Linkerd'de benzer rolü `linkerd-destination`, `linkerd-identity` gibi bileşenler üstlenir.

Bu ayrımı anlamak önemli: data plane'de binlerce proxy dağıtık çalışırken, control plane genelde az sayıda, merkezi ve kritik bir bileşendir. Control plane'i ele geçiren biri, teorik olarak bütün mesh'in güven zincirini (trust chain) kontrol eder — bu yazının saldırı yüzeyi bölümünde derinlemesine işlenecek.

## Sidecar Proxy Modeli: Nasıl Çalışır?

Kubernetes'te sidecar enjeksiyonu genelde bir "mutating admission webhook" aracılığıyla olur. Bir pod oluşturulurken (create edilirken), Kubernetes API server bu webhook'a sorar: "bu pod'a ek container eklemem gerekiyor mu?" Cevap evetse, orijinal pod spec'ine otomatik olarak proxy container'ı (ve genelde bir de init container, iptables kurallarını ayarlamak için) eklenir. Geliştirici pod tanımına sidecar'ı elle yazmaz; bir namespace veya pod'u "mesh'e dahil et" diye etiketler (label), gerisini webhook yapar.

**Trafiğin yakalanması (traffic interception)**: Sidecar trafiği nasıl "yakalar"? Init container çalışırken, pod'un network namespace'i içinde iptables (veya Linkerd/Istio Ambient modunda eBPF) kuralları yazılır. Bu kurallar, container'ın bütün giden/gelen TCP trafiğini sidecar'ın dinlediği porta yönlendirir (redirect). Yani uygulama kodu `http://b-service:8080` diye normal bir istek attığında, bu paket aslında önce localhost üzerindeki sidecar'a düşer, sidecar TLS sarmalaması, retry, metrik toplama gibi işlemleri yapıp gerçek hedefe gönderir.

**Neden bu model çalışır**: Uygulama kodunu değiştirmeden (kod-dışı/out-of-process) network davranışını kontrol etmeyi sağlar. Bir Java servisiyle bir Go servisi aynı retry/mTLS politikasına, kod tekrarı olmadan, tabi olur. Bu "polyglot" (çok dilli) ortamlarda büyük kazanç.

**Maliyeti**: Her pod'a ek bir container demek — ek CPU/bellek, ek network hop'u (latency artışı, genelde tek haneli milisaniye), ve ek bir process'in güvenliği/yamalanması gereken saldırı yüzeyi demek.

### Ambient Mesh / Sidecar-sız Yaklaşımlar

Istio'nun daha yeni "Ambient" modu ve bazı alternatifler, sidecar'ı pod başına değil node başına (ya da katmanlı: ztunnel + waypoint proxy) çalıştırarak "sidecar tax"ini (ek kaynak/latency maliyetini) azaltmayı hedefler. Bu, mimariyi değiştirir ama temel güven modeli (mTLS, politika uygulama) aynı kalır. Bunu bilmek önemli çünkü ortamda "sidecar yok" demek "mesh yok" anlamına gelmez — trafik yakalama mekanizması farklı (örn. eBPF ile node seviyesinde) olabilir.

## mTLS Otomasyonu: Kök Neden ve Çalışma Mantığı

**Neden mTLS?** Klasik TLS'de sadece sunucu kimliğini doğrularsınız (tarayıcı bankanın sertifikasına bakar). Servisler-arası iletişimde ise her iki tarafın da birbirini doğrulaması gerekir: B servisi, kendisine bağlanan A servisinin gerçekten A olduğunu bilmeli (sahte/rogue bir pod'un B'ye bağlanıp veri sızdırmasını engellemek için). Bu karşılıklı doğrulamaya mutual TLS (mTLS) denir — her iki taraf da sertifika sunar.

**Neden otomasyon şart?** Yüzlerce servis, sürekli oluşup yok olan pod'lar (scale up/down, yeniden başlatma) için sertifika üretmek, dağıtmak, rotasyonunu yapmak elle yapılamaz. Bir sertifika süresi dolduğunda unutulursa (expired cert) o servis bütün mesh'ten kopar — bu operasyonel olarak kırılgan bir sistemdir. Service mesh'in en somut faydalarından biri budur: sertifika yaşam döngüsünü tamamen otomatikleştirir.

**Nasıl çalışır (tipik akış, Istio örneği)**:

1. Mesh içinde bir Certificate Authority (CA) vardır — control plane'in bir parçası (istiod) veya harici bir CA (Vault, cert-manager entegrasyonu vb.) olabilir.
2. Her sidecar (veya onun ajanı), ayağa kalktığında kendi kimliği için bir sertifika isteği (CSR) oluşturur. Kimlik genelde SPIFFE benzeri bir formatta ifade edilir: servis hesabı (Kubernetes ServiceAccount), namespace, cluster bilgisini içeren bir URI (SPIFFE ID).
3. Control plane, pod'un Kubernetes kimliğini (service account token, node kimliği vb.) doğrulayarak CSR'i imzalar ve kısa ömürlü (short-lived, genelde saatler mertebesinde) bir sertifika döner.
4. Sidecar bu sertifikayı bellekte tutar (diske yazılmaz — bu önemli bir tasarım kararı, çünkü diske yazılan sertifika çalınabilir), ve süresi dolmadan otomatik olarak yeniler (rotasyon).
5. İki sidecar birbirine bağlandığında TLS handshake sırasında bu sertifikaları karşılıklı sunar ve doğrular; SPIFFE ID'ler beklenen kimliğe uyuyor mu diye kontrol eder (yani sadece "geçerli bir sertifika" değil, "beklenen servisin sertifikası" mı diye bakar — buna kimlik doğrulama/authorization aşaması da denebilir).

**Kısa ömürlü sertifikaların savunma değeri**: Klasik uzun ömürlü (1 yıllık) sertifikalarla çalışan sistemlerde bir anahtar çalınırsa, iptal (revocation) altyapısı (CRL/OCSP) genelde zayıf çalışır ve saldırgan uzun süre geçerli kalır. Kısa ömürlü + otomatik rotasyon modeli, çalınan bir anahtarın faydalı ömrünü saatler mertebesine indirir — bu "blast radius" (etki alanı) küçültme stratejisinin somut bir örneğidir.

**Permissive mod tuzağı**: Istio gibi sistemler geçiş kolaylığı için "PERMISSIVE" mTLS modu sunar — sidecar hem mTLS hem düz metin (plaintext) bağlantıyı kabul eder. Bu, eski servisleri kırmadan mesh'e kademeli geçiş için faydalıdır ama unutulup kalıcı hale gelen bir permissive politika, mesh dışından (veya mesh içi ama mTLS uygulamayan bir noktadan) gelen düz metin trafiğin sessizce kabul edilmesi demektir. Bu, "mTLS var" zannedip aslında korumasız olmanın en yaygın operasyonel hatasıdır. Üretimde nihai hedef "STRICT" moda geçmek olmalıdır; bunun doğrulanması (audit) ayrı bir süreç gerektirir.

## Trafik Politikaları: Retry, Timeout, Circuit Breaking

Mesh'in ikinci büyük faydası, güvenilirlik (reliability) mantığının merkezileşmesidir.

**Retry**: Bir çağrı başarısız olursa (örneğin 503 dönerse) sidecar, uygulamanın haberi olmadan otomatik olarak yeniden dener. Bunun tuzağı: retry politikası dikkatsizce ayarlanırsa, zaten yük altında boğulan bir servise retry'lar ek yük bindirir ve "retry storm" ile durumu daha da kötüleştirir (bir tür kendi kendini besleyen cascading failure). İyi pratik: retry sayısını sınırlamak, exponential backoff kullanmak, ve retry bütçesi (retry budget — toplam trafiğin belli bir yüzdesinden fazlasının retry olmasına izin vermemek) uygulamak.

**Timeout**: Sidecar seviyesinde tanımlanan timeout'lar, uygulama kodundaki (varsa) timeout'larla çelişebilir. İki katmanda farklı timeout değerleri varsa, hangisinin önce devreye gireceği kestirilemez hale gelir — bu bir yaygın hata kaynağıdır. Kural: mesh seviyesindeki timeout, uygulama seviyesindekinden kısa veya ona eşit tutulmalı, aksi halde mesh sessizce bağlantıyı keserken uygulama hala cevap bekliyor olabilir.

**Circuit breaking (devre kesici)**: Bir hedef servis sürekli hata veriyorsa veya yavaşsa, sidecar o hedefe yeni istek göndermeyi geçici olarak durdurur (devreyi açar), böylece hem çağıran servisi boşuna bekletmez hem de zaten sıkıntılı olan hedefi ek yükten korur. Bu, "bir servisin çökmesi bütün sistemi domino gibi devirmesin" (cascading failure önleme) hedefine hizmet eder. Kök neden mantığı: dağıtık sistemlerde hata izolasyonu, hatanın kaynağında değil, hatayı tüketen tarafta da uygulanmalıdır.

**En iyi pratik özeti**: Bu politikaları tanımlarken "varsayılan/permissive" değil "explicit/restrictive" başlamak, hangi servisin hangi servise, hangi protokolde, hangi kimlikle konuşabileceğini açıkça (AuthorizationPolicy gibi mekanizmalarla) tanımlamak. Mesh'in gücü, varsayılan-kapalı (default-deny) bir modelde ortaya çıkar; varsayılan-açık bırakılırsa mesh sadece gözlemlenebilirlik sağlayan pahalı bir katman olur, gerçek bir güvenlik sınırı olmaz.

## Mesh'e Özgü Saldırı Yüzeyi

Mesh, yeni bir soyutlama katmanı getirdiği için kendine has risk noktaları da getirir. Savunmacı bakış açısıyla bunları bilmek, doğru izleme (monitoring) ve sertleştirme (hardening) için şarttır.

### 1. Sidecar Bypass

Trafik yakalama iptables kurallarıyla yapılıyorsa, teorik olarak bu kuralların dışına çıkan bir yol bulunabilir mi sorusu önemlidir: örneğin pod içinde ayrıcalıklı (privileged) çalışan bir container, ağ namespace'ini manipüle ederek veya doğrudan hedefin IP'sine, sidecar'ı atlayarak bağlanmaya çalışabilir. Bunun önüne geçmek için mesh'ler genelde NetworkPolicy (Kubernetes seviyesinde, sidecar dışı trafiği tamamen engelleyen) ile mesh politikalarını birlikte kullanmayı önerir — mTLS/AuthorizationPolicy tek başına yeterli değildir, çünkü bunlar sidecar'ın gördüğü trafik için geçerlidir; sidecar'ı hiç görmeyen trafik için ayrı bir savunma katmanı (NetworkPolicy, pod güvenlik standartları, ayrıcalıklı container'ları kısıtlama) gerekir.

Savunma tespiti: pod'ların sidecar container'sız çalışmasını engelleyen admission control kuralları (örneğin "bu namespace'te sidecar enjeksiyonu olmayan pod çalışmasın" politikası), ve çıkan trafiğin sidecar dışına sızıp sızmadığını gözlemleyen ağ izleme (egress monitoring, beklenmeyen doğrudan IP bağlantılarını flag'leme).

### 2. Control Plane Ele Geçirme

Control plane, mesh'in bütün güven köküdür (root of trust) — CA'nın kendisini veya CA'ya erişimi olan bileşeni ele geçiren biri, mesh içindeki herhangi bir kimlik için geçerli sertifika üretebilir, yani mesh'teki her servisin kimliğine bürünebilir (impersonation). Bu, tek bir bileşenin ele geçirilmesinin bütün mesh'in güven varsayımını geçersiz kılması anlamına gelir — çok yüksek değer taşıyan bir hedeftir.

Savunma pratikleri: control plane'e erişimi en aza indirmek (least privilege — kim istiod/control plane API'sine erişebilir, kim CA anahtarına dokunabilir), CA'nın kök anahtarını (root key) mümkünse harici, donanım destekli bir kasada (HSM, ya da bulut KMS) tutmak ve control plane'e sadece kısa ömürlü ara sertifika yetkisi vermek, control plane bileşenlerinin kendisinin de en az ayrıcalıkla ve sıkı RBAC ile çalıştırılması, ve control plane API'sine erişimin (kubectl üzerinden CRD değiştirme dahil) denetim kaydının (audit log) tutulması.

Tespit açısından önemli sinyal: control plane bileşenlerinde beklenmeyen konfigürasyon değişiklikleri (örneğin AuthorizationPolicy'nin aniden gevşetilmesi, mTLS modunun STRICT'ten PERMISSIVE'e çekilmesi) — bunlar hem yanlışlıkla hem kötü niyetle olabilir, ikisi de izlenmeli.

### 3. Yanlış Yapılandırılmış Yetkilendirme Politikaları

En yaygın gerçek dünya riski genelde egzotik bir saldırı değil, basit bir yapılandırma hatasıdır: çok geniş kapsamlı bir AuthorizationPolicy (örneğin yanlışlıkla "*" kaynağa izin veren bir kural), yanlış namespace seçici (selector), ya da test için açılıp geri kapatılmayı unutulan geçici bir kural. Mesh, doğru yapılandırılmadığında "her yerde mTLS var, o yüzden güvenliyiz" yanılgısına yol açabilir — halbuki mTLS sadece şifreleme+kimlik doğrulamadır, kimin kime, hangi eylemi yapabileceğini (yetkilendirme) ayrı ve doğru tanımlamak gerekir. Şifreli ama yetkisiz erişim serbest bırakılmış bir mesh, "güvenli görünen" ama aslında açık bir sistemdir.

En iyi pratik: politika değişikliklerini kod incelemesinden (code review) geçirmek (politikalar genelde YAML/CRD olarak GitOps akışında tutulur), periyodik olarak "efektif politika" denetimi yapmak (hangi servis gerçekte hangi servise erişebiliyor, statik tanımdan değil çalışan sistemden doğrulamak), ve deny-by-default ile başlayıp açıkça izin verilenleri eklemek.

### 4. Gözlemlenebilirlik Verisinin Kendisinin Sızması

Mesh, zengin telemetri (kim kime, ne sıklıkta, ne kadar veriyle konuşuyor) üretir. Bu veri savunma için değerlidir ama kendisi de hassastır — trafik metadatası (kim kiminle konuşuyor, hangi sıklıkta), içeriği görmeden bile iş mantığını (hangi servis kritik, hangi servis düş, olası bir veri tabanı hangisi) çıkarılabilir hale getirebilir. Telemetri toplama ve saklama altyapısına erişim de en az ayrıcalık ilkesiyle kısıtlanmalıdır.

## Yaygın Hatalar Özeti

- **mTLS'in "STRICT" olduğunu varsaymak, doğrulamamak**: Permissive modda takılı kalan namespace'ler sessizce açık kapı bırakır. Periyodik denetim şart.
- **Yetkilendirmeyi mTLS ile karıştırmak**: Şifreleme kimlik doğrulamadır, yetkilendirme değildir. İkisi ayrı ayrı tasarlanmalı.
- **Retry/timeout katmanlarını (uygulama + mesh) senkronize etmemek**: Çelişen değerler kestirilemeyen davranışa yol açar.
- **Sidecar dışı trafiği unutmak**: NetworkPolicy gibi tamamlayıcı katmanlar olmadan sidecar bypass riski göz ardı edilir.
- **Control plane'i "sadece bir başka servis" gibi görmek**: Aslında bütün güven zincirinin köküdür, ayrı ve daha sıkı bir güvenlik çemberi gerektirir.
- **Mesh'i performans/latency maliyetini ölçmeden her yere uygulamak**: Her sidecar ek kaynak ve hop demektir; kritik düşük-gecikme yolları için bu maliyet ölçülmeli, gerekirse Ambient gibi hafif modeller değerlendirilmeli.

## Sonuç

Service mesh, servisler-arası iletişimi uygulama kodundan ayırıp platform seviyesinde, tutarlı ve otomatik hale getiren bir mimari desendir. Sidecar proxy modeli bunu kod değişikliği gerektirmeden yapar; mTLS otomasyonu, kısa ömürlü sertifikalarla güvenlik hijyenini insan hatasından bağımsızlaştırır; trafik politikaları (retry/timeout/circuit breaking) dağıtık sistem güvenilirliğini merkezileştirir. Ama bu güç, control plane'i ekosistemin en değerli hedefine, sidecar'ı ise potansiyel bir bypass noktasına dönüştürür. Savunma açısından doğru soru "mesh var mı" değil, "mTLS gerçekten STRICT mi, yetkilendirme deny-by-default mi, control plane'e erişim ne kadar kısıtlı, ve sidecar'ı atlayan bir yol var mı" sorularıdır. Mekanizmayı anlamak, bu soruları sorabilmenin ön koşuludur.
