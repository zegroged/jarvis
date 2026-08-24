# Feature Flag ve Kademeli Yayın Stratejileri (Canary, Blue-Green, Dark Launch)

## Giriş: Neden Kademeli Yayın?

Modern yazılım mühendisliğinde "kod yazmak" ile "kodu güvenle canlıya almak" birbirinden ayrı iki disiplindir. Bir değişikliği tek seferde tüm kullanıcı tabanına açmak (big-bang deployment) yüksek risklidir: test ortamında yakalanmayan bir hata, saniyeler içinde milyonlarca kullanıcıyı etkileyebilir. Kademeli yayın (progressive delivery) stratejileri, bu riski **kontrollü, geri alınabilir ve gözlemlenebilir** hâle getirmek için doğmuştur.

Temel fikir şudur: bir değişikliğin **deploy** (kodun sunuculara yerleştirilmesi) ile **release** (kodun kullanıcıya görünür olması) aşamalarını birbirinden ayırmak. Bu ayrım, kademeli yayının bel kemiğidir. Kodu üretime yerleştirebilir ama etkisini bir anahtarla açık/kapalı tutabilirsin. Bu makale, bu ayrımı mümkün kılan mekanizmaları -feature flag altyapısı, canary, blue-green, dark launch, rolling deployment ve rollback otomasyonu- derinlemesine ele alır.

## Temel Kavram: Deploy ile Release'in Ayrılması

Geleneksel akışta kod dallanır, birleştirilir, build alınır ve sunucuya çıkılır; çıktığı an kullanıcı onu görür. Progressive delivery bu zinciri kırar.

- **Deploy**: Yeni sürümün binary/artifact olarak üretim altyapısına yerleştirilmesi. Kullanıcı henüz etkilenmeyebilir.
- **Release**: Yerleştirilmiş kodun belirli bir kullanıcı kitlesine gerçekten servis edilmeye başlanması.

Bu ayrım sayesinde riskli bir özellik, üretim sunucularında `if (flag.isEnabled("yeni-odeme-akisi"))` gibi bir koşulun arkasında **kapalı** hâlde durabilir. Kod oradadır, çalışır durumdadır, ancak kimseye görünmez. Karar anı geldiğinde bir yapılandırma değişikliğiyle -kod deploy'u olmadan- açılır. Bu, kademeli yayının tüm stratejilerinin altında yatan zihinsel modeldir.

## Feature Flag (Feature Toggle) Yönetimi

### Tanım ve Çalışma Mantığı

Feature flag, kodun içindeki bir davranışı çalışma zamanında (runtime) açıp kapatmayı sağlayan bir koşullu daldır. En basit hâli bir boolean'dır, ancak olgun sistemlerde çok daha zengin bir yapıya sahiptir. Flag'in "değeri", genellikle merkezî bir yapılandırma servisinden veya bir feature flag yönetim platformundan (LaunchDarkly, Unleash, Flagsmith gibi ürünler ya da şirket içi çözümler) beslenir.

Kod tarafında akış tipik olarak şöyledir: uygulama başlarken veya periyodik olarak flag tanımlarını çeker, bunları bellekte tutar (yerel cache), her istekte bir **evaluation context** (kullanıcı kimliği, ülke, plan tipi, cihaz gibi öznitelikler) ile flag'i değerlendirir ve sonuca göre kod yolunu seçer.

```
karar = flagClient.degerlendir(
    flagAnahtari = "yeni-arama-algoritmasi",
    context = { kullaniciId, ulke, planTipi },
    varsayilan = false
)
if (karar) yeniAramaYolu() else eskiAramaYolu()
```

Buradaki kritik ayrıntı **varsayılan değer**dir: flag servisi erişilemezse (ağ hatası, servis çökmesi) kod hâlâ deterministik bir davranış sergilemelidir. İyi tasarlanmış bir flag istemcisi asla "flag servisi çöktü, uygulama da çöktü" durumuna düşmez; son bilinen değeri veya güvenli varsayılanı kullanır (fail-safe).

### Flag Türleri

Bütün flag'ler aynı değildir ve karıştırılmaları teknik borç üretir:

- **Release toggle**: Yarım kalmış veya kademeli açılacak bir özelliği gizler. Kısa ömürlüdür; özellik tam açıldıktan sonra silinmelidir.
- **Experiment toggle**: A/B testleri için kullanıcıları varyantlara böler. Ölçüm süresi kadar yaşar.
- **Ops toggle**: Operasyonel kontrol içindir; ör. yük altında pahalı bir özelliği kapatmak (kill switch). Uzun ömürlü olabilir.
- **Permission toggle**: Belirli kullanıcı gruplarına (premium, beta, internal) özellik açmak için kullanılır. Kalıcıdır.

Bu ayrımı yapmamak, "geçici" bir release toggle'ının yıllarca kodda kalıp kimsenin dokunmaya cesaret edemediği bir mayına dönüşmesine yol açar.

### Targeting ve Kademeli Açılma

Feature flag'in gerçek gücü, boolean açık/kapalı olmasının ötesinde **targeting** (hedefleme) yeteneğindedir. Bir flag şu şekilde kademeli açılabilir:

1. Yalnızca kendi ekibine (internal dogfooding).
2. Beta kullanıcılarına (opt-in liste).
3. Kullanıcıların %1'ine, sonra %5, %25, %50 ve %100'üne.

Yüzdesel açılımda kritik nokta **tutarlı hashing**tir. Bir kullanıcının flag durumu istekten isteğe değişmemelidir; aksi halde kullanıcı bir istekte yeni özelliği görür, sonrakinde görmez, deneyim tutarsız olur. Bu yüzden `hash(kullaniciId + flagAnahtari)` gibi deterministik bir fonksiyonla kullanıcı sabit bir "bucket"a atanır ve yüzde eşiğiyle karşılaştırılır. Aynı kullanıcı, eşik değişene kadar hep aynı kovada kalır.

## Canary Deployment

### Tanım

Canary deployment adını, kömür madencilerinin zehirli gazı erken tespit için taşıdığı kanaryadan alır: yeni sürüm önce küçük bir trafik dilimine ("kanarya") verilir, sağlığı izlenir, sorun yoksa dilim büyütülür.

### Çalışma Mantığı

Yeni sürüm (v2), eski sürümle (v1) yan yana çalışır. Bir yönlendirme katmanı -service mesh, load balancer veya ingress controller- gelen trafiğin küçük bir yüzdesini (ör. %1-5) v2'ye, geri kalanını v1'e yönlendirir. Bu sırada v2'nin metrikleri (hata oranı, gecikme/latency, CPU, iş metrikleri) v1'inkiyle karşılaştırılır.

Buradaki en önemli ilke **karşılaştırmalı analiz**dir. "v2'nin hata oranı %2" tek başına anlamsızdır; asıl soru "v2, aynı anda çalışan v1'e göre daha mı kötü?" sorusudur. Bu yaklaşım, günün saatine veya genel trafik dalgalanmasına bağlı gürültüyü elimine eder. Otomatik canary analizi (bazı ekipler bunu "automated canary analysis" diye anar) tam olarak bu iki grubun metriklerini istatistiksel olarak kıyaslayıp bir güven skoru üretir.

### Doğru Kullanım ve Tuzaklar

- **Doğru**: Canary popülasyonu, üretim trafiğini temsil etmelidir. Yalnızca bir bölgeye veya bir kullanıcı tipine kanarya vermek yanıltıcı olabilir; küçük ama temsili bir örneklem gerekir.
- **Tuzak - yetersiz bekleme**: Kanaryayı 30 saniye izleyip "sorun yok" demek. Bazı hatalar (bellek sızıntısı, yavaş biriken kuyruk, saatlik cron işleri) ancak dakikalar/saatler sonra görünür. Yeterli **bake time** (olgunlaşma süresi) tanımlanmalıdır.
- **Tuzak - stateful yan etkiler**: Kanarya, geri alınamayan bir işlem yaparsa (ör. veritabanı şemasını değiştirmek, kalıcı mesaj yazmak) rollback yalnızca kodu geri alır, veriyi değil. Şema göçleri geriye dönük uyumlu (backward compatible) tasarlanmalıdır.

## Blue-Green Deployment

### Tanım ve Mantık

Blue-green'de iki tam üretim ortamı bulunur: **blue** (şu an canlı) ve **green** (yeni sürümün deploy edildiği, hazırda bekleyen). Yeni sürüm green'e çıkılır, orada duman testleri (smoke test) yapılır, hazır olduğunda yönlendirici trafiği **tek seferde** blue'dan green'e çevirir. Sorun çıkarsa trafik anında blue'ya geri döndürülür.

Canary'den farkı: canary trafiği **yüzdesel ve kademeli** böler; blue-green ise **atomik bir geçiş** (cutover) yapar. Blue-green'in en büyük avantajı, çok hızlı ve net bir rollback yoludur -eski ortam hâlâ ayakta ve çalışır durumdadır.

### Tuzaklar

- **Veritabanı paylaşımı**: Genellikle blue ve green aynı veritabanını paylaşır. Bu durumda şema değişiklikleri iki sürümle de uyumlu olmalıdır; aksi halde geri dönüş imkânsızlaşır. "Expand and contract" (önce genişlet, kod geçişini tamamla, sonra daralt) deseni burada zorunludur.
- **Maliyet**: İki tam ortam çalıştırmak kaynak açısından pahalıdır. Konteyner ve otomatik ölçeklendirme ile hafiflese de göz ardı edilmemelidir.
- **Uzun ömürlü bağlantılar**: WebSocket veya uzun süren istekler cutover anında kesilebilir; connection draining (mevcut bağlantıların bitmesini bekleme) düşünülmelidir.

## Dark Launch

### Tanım

Dark launch (karanlık yayın), yeni bir özelliğin veya kod yolunun kullanıcıya **görünmeden** üretim yükü altında çalıştırılmasıdır. Amaç, işlevsel doğruluğu değil, **üretim ölçeğinde davranışı ve performansı** ölçmektir.

### Çalışma Mantığı

En yaygın biçim **shadow traffic** (gölge trafik) veya **traffic mirroring**tir: gerçek üretim istekleri hem eski sisteme (yanıtı kullanıcıya döner) hem de yeni sisteme (yanıtı atılır) kopyalanır. Yeni sistem gerçek yük altında sınanır ama çıktısı kullanıcıyı etkilemez.

Ünlü bir tarihsel örnek, büyük ölçekli bir sosyal medya platformunun yeni bir arka uç bileşenini, kullanıcı arayüzünde hiçbir şey göstermeden, gerçek trafiği bu yeni bileşene de göndererek aylarca "karanlıkta" test etmesidir. Böylece açılış günü, altyapı zaten üretim yükünü taşımayı öğrenmiş olur.

### Doğru Kullanım ve Tuzaklar

- **Doğru**: Ölçek ve performans belirsizliği yüksek yeniden yazımlar (rewrite) ve migrasyonlar için idealdir.
- **Tuzak - yan etki**: Gölge sistem, yan etkisi olan işlemler yaparsa (e-posta gönderme, ödeme alma, üçüncü parti API'ye yazma) çift işlem gerçekleşir. Shadow yolları mutlaka yan etkisiz (idempotent veya no-op) olmalıdır.
- **Tuzak - maliyet ve gizlilik**: Trafiği ikiye katlamak kaynak maliyeti getirir; ayrıca gerçek kullanıcı verisi ikinci bir sisteme akıtıldığından veri koruma/uyumluluk (KVKK, GDPR) değerlendirilmelidir.

## Rolling Deployment

Rolling deployment, sürümü örneklerin (instance/pod) üzerinde **parti parti** günceller: birkaç örnek yeni sürüme geçer, sağlıklı olduğu doğrulanır, sonraki parti güncellenir. Kubernetes'in varsayılan Deployment davranışı budur (`maxSurge` ve `maxUnavailable` parametreleriyle ne kadar hızlı ve ne kadar fazladan kapasiteyle ilerleyeceği ayarlanır).

Rolling'in canary'den farkı incedir ama önemlidir: rolling'in amacı **kesintisiz güncelleme**dir, hedefli risk analizi değil. Rolling sırasında trafik yüzdesi otomatik olarak yeni sürüme kayar ama "önce ölç, sonra ilerle" mantığı zorunlu değildir. Canary bu ölçüm adımını merkeze koyar. Pratikte ekipler ikisini birleştirir: rolling ile ilerlerken metrik eşiği aşılırsa güncelleme durur (health gate).

## Rollback Otomasyonu

Kademeli yayının değeri, **hızlı ve güvenilir geri alma** olmadan yarım kalır. Rollback otomasyonu şu bileşenlere dayanır:

- **Sağlık göstergeleri (SLO/hata bütçesi)**: Otomasyonun "kötüye gidiyor" kararını verebilmesi için net eşikler gerekir: hata oranı, p99 gecikme, doygunluk metrikleri.
- **Otomatik tetikleme**: Metrik eşiği aşıldığında insan müdahalesi beklemeden canary'yi durdurup trafiği eski sürüme çekmek. Bu, gece yarısı bir olayda dakikalar yerine saniyelerle ölçülen bir tepki süresi kazandırır.
- **Kill switch olarak flag**: En hızlı rollback, çoğu zaman yeni bir deploy değil, ilgili feature flag'i kapatmaktır. Yeni sürümü deploy etmek dakikalar sürerken, bir flag'i kapatmak saniyeler sürer. Bu yüzden riskli özellikler daima bir kill switch flag'i arkasına konur.

### Rollback'in Sınırları

Otomatik rollback her şeyi çözmez. Kod geri alınabilir ama şu üçü geri alınmaz veya zordur:

1. **Veri**: Yeni sürüm bozuk veri yazdıysa rollback bunu düzeltmez.
2. **Şema göçleri**: Geriye uyumsuz bir migration çalıştıysa eski kod yeni şemayla çalışamaz.
3. **Dış etkiler**: Gönderilmiş e-postalar, tetiklenmiş webhook'lar geri alınamaz.

Bu nedenle rollback'i mümkün kılan asıl disiplin, **her değişikliği ileriye ve geriye uyumlu (forward/backward compatible)** tasarlamaktır.

## Deney ve A/B Test Altyapısı

Feature flag altyapısı olgunlaştığında doğal olarak **deney (experimentation)** altyapısına evrilir. A/B testinde amaç sadece güvenli açmak değil, iki varyantın **iş metriklerine etkisini istatistiksel olarak** karşılaştırmaktır.

Bunun için gereken bileşenler:

- **Deterministik atama**: Kullanıcılar A/B varyantlarına tutarlı hashing ile atanır ve deney boyunca aynı grupta kalır (sticky assignment).
- **Metrik toplama**: Her varyantın dönüşüm, gelir, elde tutma (retention) gibi metrikleri gruplanarak toplanır.
- **İstatistiksel anlamlılık**: İki grup arasındaki farkın şansa mı yoksa gerçek etkiye mi bağlı olduğunu ayırt etmek için hipotez testleri kullanılır. Yeterli örneklem büyüklüğü toplanmadan sonuç okumak (peeking) yanıltıcıdır.

Kritik bir mühendislik hatası, deney atamasını release toggle'la karıştırmaktır. Bir kullanıcı hem "özellik açık" hem "kontrol grubu" olmamalıdır; deney ve yayın flag'leri katmanlanmalı, çakışmamalıdır.

## Yaygın Hatalar ve Anti-Pattern'ler

- **Flag borcu (flag debt)**: Kullanım ömrü biten flag'lerin koddan temizlenmemesi. Her flag bir dallanma (branch) demektir; yüzlerce ölü flag, test edilmesi imkânsız kombinatoryal bir karmaşa üretir. Her flag'e bir "son kullanma" sahibi ve tarihi atanmalıdır.
- **Flag'lerin bağımlılaşması**: Bir flag'in davranışının başka bir flag'e gizlice bağlı olması. Kombinasyonlar test edilmediğinde, tek başına güvenli iki flag birlikte açıldığında sistemi bozabilir.
- **Yapılandırmanın izlenmemesi**: Flag değişikliklerinin bir olay/audit kaydı olmaması. Bir kesinti anında "10 dakika önce hangi flag açıldı?" sorusuna yanıt verilemiyorsa, en hızlı kök neden analizi aracı kaybedilmiş demektir. Flag değişiklikleri versiyonlanmalı ve izlenmelidir.
- **Gözlemlenebilirlik olmadan canary**: Metrik ve dağıtık izleme (distributed tracing) olmadan canary yapmak, gözü kapalı ilerlemektir. "Yeni sürüm çalışıyor mu?" sorusunu ancak metrikler yanıtlar; canary'nin ön koşulu sağlam observability'dir.
- **"Geçici" olanın kalıcılaşması**: Bir kill switch veya ops toggle çıkarılıp "sonra hallederiz" denilerek unutulur. Ops toggle'lar meşrudur ama bilinçli ve dokümante edilmiş olmalıdır.

## Güvenlik ve Yönetişim Boyutu

Feature flag altyapısı, üretim davranışını değiştiren güçlü bir kontrol düzlemidir; bu da onu bir **saldırı ve hata yüzeyi** yapar. Savunma açısından dikkat edilmesi gerekenler:

- **Yetkilendirme**: Bir flag'i kimin değiştirebileceği sıkı biçimde kontrol edilmelidir. Üretimde bir flag'i açmak, kod deploy etmek kadar güçlü bir eylemdir ve aynı ciddiyetle yetkilendirilmelidir.
- **Audit ve değişmezlik**: Kim, ne zaman, hangi flag'i değiştirdi bilgisi değiştirilemez şekilde loglanmalıdır. Bu hem güvenlik hem de olay müdahalesi için kritiktir.
- **Client-side flag riski**: Tarayıcıda değerlendirilen flag'ler, kullanıcı tarafından görülebilir/manipüle edilebilir. Güvenlik sınırı olarak feature flag'e güvenilmemelidir; ör. "premium özelliği" yalnızca bir client-side flag ile gizlemek, kararlı bir kullanıcının onu açmasını engellemez. Yetki kontrolü sunucu tarafında yapılmalıdır.
- **Fail-safe varsayılanlar**: Flag servisi ele geçirilir veya çökerse sistemin güvenli tarafta kalması (en az yetki, kapalı varsayılan) tercih edilmelidir.

## Sonuç

Kademeli yayın stratejileri, tek bir "en iyi" yöntem değil, farklı risk profillerine karşılık gelen bir araç setidir. **Feature flag'ler** deploy ile release'i ayırarak tümünün temelini kurar. **Canary** riski küçük ve temsili bir dilimde ölçerek büyütür. **Blue-green** anlık ve net bir geçiş/geri dönüş sağlar. **Dark launch** görünmeden üretim ölçeğinde test eder. **Rolling** kesintisiz günceller. Hepsinin ortak koşulu üç şeydir: değişiklikleri geriye/ileriye uyumlu tasarlamak, sağlam gözlemlenebilirlik kurmak ve hızlı, otomatik geri alma yollarını hazır tutmak. Bu üçlü olmadan hangi strateji seçilirse seçilsin, kademeli yayın yalnızca bir güvenlik hissi -gerçek bir güvenlik değil- sağlar.
