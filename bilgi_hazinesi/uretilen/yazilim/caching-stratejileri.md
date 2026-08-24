# Caching Stratejileri

## Giriş: Cache Nedir ve Neden Var?

Bir bilgisayar sisteminde veriye erişim maliyeti her katmanda farklıdır. CPU'nun kendi register'ına erişmesi nanosaniyenin altında sürerken, RAM'e erişim onlarca nanosaniye, yerel bir SSD'ye erişim yüz mikrosaniyeler, uzaktaki bir veritabanına ağ üzerinden yapılan sorgu ise milisaniyeler alır. Bu maliyetler arasındaki fark birkaç kat değil, çoğu zaman binlerce kattır. İşte **cache** (önbellek), pahalı bir kaynaktan alınan bir sonucu, daha ucuz ve daha hızlı erişilebilir bir yerde geçici olarak saklayıp tekrar tekrar oradan sunma tekniğidir.

Cache'in temel varsayımı iki gözleme dayanır: **temporal locality** (zamansal yerellik) ve **spatial locality** (uzamsal yerellik). Zamansal yerellik, yakın zamanda erişilen bir verinin yakın gelecekte tekrar erişilme olasılığının yüksek olduğunu söyler. Uzamsal yerellik ise erişilen bir verinin yakınındaki verilere de erişilme olasılığının yüksek olduğunu ifade eder. Gerçek dünyadaki iş yükleri neredeyse her zaman bu yerellik özelliklerini gösterir; örneğin bir haber sitesinde birkaç popüler makale trafiğin çoğunu çeker, bir e-ticaret sitesinde belli ürünler defalarca görüntülenir. Cache bu tekrarları ucuza kapatarak sistemin hem gecikmesini (latency) hem de arka uçtaki yükü (backend load) dramatik biçimde düşürür.

Ancak cache "bedava hız" değildir. Cache eklediğiniz an sisteme bir **tutarlılık (consistency)** problemi sokmuş olursunuz: artık aynı verinin iki kopyası vardır ve bunların senkron kalması gerekir. Ünlü bir söz vardır: bilgisayar bilimindeki en zor iki şey cache invalidation, isimlendirme ve birden fazla nesneden kaynaklanan hatalardır. Bu makalenin büyük bölümü tam da bu tutarlılık problemini yönetme stratejileri üzerinedir.

## Cache Katmanları (Caching Layers)

Cache tek bir yerde yaşamaz; modern bir sistemde istek, kullanıcıdan veritabanına kadar birçok katmandan geçer ve neredeyse her katmanda bir cache fırsatı vardır. Bu katmanları anlamak, "neyi nerede cache'lemeliyim" sorusuna doğru cevap vermenin ön koşuludur.

### 1. İstemci tarafı (Client-side) cache

Tarayıcının bellek ve disk cache'i, mobil uygulamanın yerel deposu buraya girer. Bir görsel, CSS dosyası veya API cevabı bir kez indirildikten sonra tekrar indirilmez. Bu, ağ trafiğini tamamen ortadan kaldırdığı için en ucuz cache katmanıdır. HTTP dünyasında `Cache-Control`, `ETag` ve `Last-Modified` başlıkları bu davranışı yönetir. Buradaki zorluk, cache'i geçersiz kılmanın (invalidation) sunucunun kontrolünde olmamasıdır; kullanıcı zaten eski kopyayı indirdiyse, siz artık onu geri çağıramazsınız.

### 2. CDN ve edge cache

Content Delivery Network, içeriği coğrafi olarak kullanıcıya yakın edge sunucularda tutar. Statik varlıklar (resim, video, JavaScript) için idealdir, çünkü hem gecikmeyi hem origin sunucuya inen yükü azaltır. Giderek daha fazla mimari, kişiselleştirilmemiş HTML sayfalarını ve hatta bazı API cevaplarını da edge'de cache'ler.

### 3. Reverse proxy / gateway cache

Origin sunucunun hemen önünde duran bir katman (örneğin bir reverse proxy) sık istenen cevapları tutar ve uygulama sunucusuna hiç ulaşmadan yanıt verebilir. Bu, uygulama katmanını hesaplama yükünden korur.

### 4. Uygulama içi (in-process / in-memory) cache

Uygulama sürecinin kendi bellek alanında tutulan cache'tir; bir dilin içindeki bir map/dictionary yapısı ya da bir LRU cache kütüphanesi olabilir. Erişimi en hızlı olanıdır çünkü ağ katmanı yoktur — sadece bellek erişimidir. Dezavantajı, her uygulama örneğinin (instance) kendi kopyasını tutmasıdır; bu da hem bellek israfına hem de örnekler arası tutarsızlığa yol açar. Yatay ölçeklenen (horizontally scaled) sistemlerde bu ciddi bir sorundur.

### 5. Dağıtık (distributed) cache

Ayrı bir servis olarak çalışan, tüm uygulama örneklerinin paylaştığı bir cache katmanıdır (in-memory key-value store'lar bu rolü üstlenir). Ağ üzerinden erişildiği için in-process cache'ten yavaştır ama veritabanından hâlâ çok daha hızlıdır ve tek bir tutarlı görünüm sunar. Bu, ölçekli sistemlerin bel kemiğidir.

### 6. Veritabanı katmanı cache'leri

Veritabanının kendi buffer pool'u, sorgu planı cache'i ve materialized view'ları da birer cache'tir. Genellikle görünmezdirler ama sistem davranışını çok etkilerler.

Bu katmanlar birbirini dışlamaz; gerçek sistemlerde üst üste yığılırlar. Kritik nokta şudur: **bir veri ne kadar üst katmanda cache'lenirse o kadar ucuz sunulur, ama o kadar zor geçersiz kılınır.** Katman seçimi bu iki gücün dengesidir.

## Cache Yazma ve Okuma Desenleri

Cache ile veritabanı arasındaki koordinasyonu belirleyen belirli desenler vardır. Hangisini seçtiğiniz; tutarlılık, gecikme ve karmaşıklık arasındaki takasınızı belirler. En yaygın dördü cache-aside, read-through, write-through ve write-behind'dir.

### Cache-Aside (Lazy Loading)

Bu, uygulamada en sık gördüğünüz desendir çünkü basit ve dayanıklıdır. Mantığı okuma tarafında şöyle işler:

1. Uygulama önce cache'e sorar.
2. Veri cache'te varsa (**cache hit**), doğrudan döner.
3. Veri yoksa (**cache miss**), uygulama veritabanından okur, sonucu cache'e yazar ve döner.

```
def get_user(user_id):
    user = cache.get(f"user:{user_id}")
    if user is not None:          # cache hit
        return user
    user = db.query_user(user_id) # cache miss
    cache.set(f"user:{user_id}", user, ttl=300)
    return user
```

Yazma tarafında ise klasik cache-aside, veritabanını günceller ve **ilgili cache girdisini siler** (invalidate). Silmek, yeni değeri cache'e yazmaktan (update) genellikle daha güvenlidir; nedenini birazdan "invalidation" bölümünde göreceğiz.

**Kök neden — neden bu kadar yaygın?** Cache-aside'ın en büyük avantajı **cache ile veritabanının birbirinden bağımsız (decoupled) olmasıdır.** Cache çökerse sistem yavaşlar ama çalışmaya devam eder; her istek doğrudan veritabanına düşer. Ayrıca sadece gerçekten istenen veri cache'e girer, yani cache "sıcak" (hot) veriyle dolar, kullanılmayan veriyle değil. Dezavantajı, ilk isteğin her zaman yavaş olmasıdır (cache miss cezası) ve uygulama kodunun cache mantığını taşımak zorunda olmasıdır.

### Read-Through

Read-through, cache-aside'ın okuma mantığını cache katmanının kendisine taşır. Uygulama sadece cache'e sorar; cache miss durumunda cache, arka plandaki veri kaynağından veriyi kendisi çeker ve doldurur. Fark inceliklidir ama önemlidir: cache-aside'da veri yükleme mantığı uygulamada, read-through'da cache kütüphanesinde/servisinde yaşar. Bu, uygulama kodunu sadeleştirir ama size cache'in nasıl doldurulacağı üzerinde daha az kontrol verir.

### Write-Through

Write-through'da her yazma işlemi **hem cache'e hem veritabanına, senkron olarak** yapılır. Uygulama cache'e yazar, cache aynı işlem içinde veritabanına da yazar ve ancak ikisi de başarılı olunca işlem tamamlanır.

**Kök neden — ne kazandırır?** Bu desenin amacı **cache ile veritabanını her zaman senkron tutmaktır.** Yazılan veri anında cache'te taze halde bulunur, dolayısıyla yazma sonrası okumalar (read-after-write) hep hit olur ve tutarlıdır. Bedeli, yazma gecikmesinin artmasıdır: her yazma artık iki depoyu birden beklemek zorundadır. Ayrıca çok yazılan ama az okunan veriler için cache'i boşuna doldurursunuz. Bu yüzden write-through genellikle write-behind veya read-through ile birlikte kullanılır.

### Write-Behind (Write-Back)

Write-behind'da uygulama cache'e yazar ve **hemen döner**; veritabanına yazma işlemi asenkron olarak, bir kuyruk üzerinden, arka planda gerçekleşir. Bu, yazma gecikmesini büyük ölçüde düşürür ve çok sayıda yazmayı toplu (batch) hale getirerek veritabanı yükünü azaltır.

**Takas neden ağırdır?** Buradaki tehlike **dayanıklılıktır (durability).** Veri henüz sadece cache'te (çoğunlukla bellekte) dururken cache çökerse, kalıcı depoya yazılmamış yazmalar **kalıcı olarak kaybolur.** Ayrıca veritabanı bir süre eski değeri gösterir (eventual consistency). Write-behind, yüksek yazma hacminin gecikmeden daha önemli olduğu, veri kaybı riskinin tolere edilebildiği veya kuyruğun kalıcı hale getirildiği senaryolarda yerindedir; finansal işlemler gibi kritik yazmalarda dikkatle kullanılmalıdır.

### Write-Around

Yazmaların doğrudan veritabanına yapıldığı, cache'in atlandığı bir varyanttır; cache yalnızca okuma sırasında (cache-aside gibi) dolar. Bir kez yazılıp nadiren okunan verilerde cache'i gereksiz doldurmayı önler.

## Invalidation: En Zor Kısım

Cache invalidation, artık geçerliliğini yitirmiş bir cache girdisini kaldırma ya da güncelleme işidir. Zor olmasının nedeni felsefidir: cache eklediğiniz an, "gerçeğin tek kaynağı" (source of truth) olan veritabanı ile onun bir kopyası arasında bir **senkronizasyon problemi** yaratmış olursunuz ve dağıtık sistemlerde iki kopyayı atomik olarak güncellemek son derece zordur.

### Neden "sil", "güncelle" değil?

Cache-aside'da yazma anında girdiyi güncellemek yerine silmenin tavsiye edilmesinin somut bir nedeni vardır: **race condition**. İki eşzamanlı işlem düşünün. İşlem A veriyi eski haliyle veritabanından okumuş ama henüz cache'e yazamamışken, işlem B veritabanını yeni değerle güncelleyip cache'i güncelliyor; ardından A geç kalmış eski değerini cache'e yazıyor. Sonuç: cache'te kalıcı olarak eski (stale) veri kalır. Girdiyi güncellemek yerine silmek bu pencereyi daraltır — bir sonraki okuma cache miss alır ve veritabanından taze değeri çeker. Silme, "bilmediğimi kabul ediyorum" demenin güvenli yoludur; yanlış güncelleme ise "yanlış bildiğimi doğru sanıyorum" durumudur ki çok daha tehlikelidir.

### Yazma sırası: önce veritabanı mı, önce cache mi?

Yaygın ve doğru kabul edilen sıra **önce veritabanına yaz, sonra cache'i sil** (cache-aside invalidation) şeklindedir. Ama bunun bile bir açığı vardır: veritabanı güncellendikten sonra, cache silinmeden önce başka bir okuma gelirse eski değeri cache'e doldurabilir. Bu inceliği tamamen kapatmak için endüstride kullanılan tekniklerden biri **delayed double delete**'tir: veritabanını güncelle, cache'i sil, kısa bir süre bekle, cache'i **bir kez daha sil**. İkinci silme, bu arada araya girmiş eski okumanın doldurduğu girdiyi temizler. Bir başka yaklaşım, tutarlılığı veritabanının değişiklik akışına (change data capture / binlog takibi) bağlayıp cache'i oradan güncellemektir; böylece uygulama koduna güvenmek yerine kaynağın gerçeğini takip edersiniz.

### Invalidation stratejileri

- **Doğrudan (explicit) invalidation:** Veri değiştiğinde ilgili anahtarı bilerek silersiniz. En kesin yöntemdir ama "hangi anahtarlar etkilendi" sorusunu doğru cevaplamak zordur. Örneğin bir ürünün fiyatı değişince, o ürünü içeren kategori listesi cache'i, arama sonucu cache'i ve öneriler cache'i de bayatlar. Bu bağımlılık grafiğini kaçırmak, invalidation hatalarının başlıca kaynağıdır.
- **TTL tabanlı (süreyle) invalidation:** Girdiye bir yaşam süresi verirsiniz; süre dolunca girdi kendiliğinden geçersiz olur. Bağımlılıkları takip etme derdinden kurtarır ama bu sürenin sonuna kadar bayat veri gösterme riskini kabul edersiniz.
- **Olay tabanlı (event-driven) invalidation:** Veri değişikliği bir mesaj/olay yayınlar, cache'i dinleyen bileşenler ilgili girdileri temizler. Dağıtık sistemlerde birden çok cache düğümünü senkron tutmak için güçlüdür.
- **Etiket/grup (tag-based) invalidation:** İlgili girdileri bir etikete bağlar, tek bir işlemde bütün bir grubu geçersiz kılarsınız. "Şu kullanıcıya ait tüm cache'i temizle" gibi durumlar için pratiktir.

Dağıtık cache'lerde ek bir zorluk vardır: bir düğümde sildiğiniz girdi başka bir uygulama örneğinin in-process cache'inde hâlâ yaşıyor olabilir. Bu yüzden çok katmanlı cache mimarilerinde invalidation olaylarını **tüm katmanlara yaymak** gerekir; yoksa üst katman alt katmanı sürekli "kirletir".

## TTL (Time To Live): Ne Kadar Bayatlığa Razısınız?

TTL, bir cache girdisinin ne kadar süre geçerli sayılacağını belirleyen değerdir. Süre dolunca girdi ya silinir ya da bir sonraki erişimde geçersiz kabul edilir. TTL, invalidation'ın en basit ve en yaygın biçimidir çünkü bağımlılık takibi gerektirmez — zaman geçtikçe her şey kendiliğinden tazelenir.

### TTL'i seçmenin mantığı

TTL seçimi aslında tek bir soruyu cevaplamaktır: **"Bu veri için ne kadar bayatlığı (staleness) kabul edebilirim?"** Cevap tamamen verinin doğasına bağlıdır:

- Bir ürünün stok adedi saniyeler içinde değişebilir ve yanlış göstermek satış kaybettirir; kısa TTL (saniyeler) gerekir.
- Bir kullanıcının profil fotoğrafı nadiren değişir; uzun TTL (saatler) sorun değildir.
- Bir para birimi kuru dakikalarla ölçülen tazelik ister.

Kısa TTL tutarlılığı artırır ama hit oranını düşürür (daha çok cache miss, daha çok veritabanı yükü). Uzun TTL yükü azaltır ama bayat veri riskini artırır. TTL ayarlamak bu iki uç arasında bilinçli bir denge kurmaktır; "her şeye bir saat" gibi düşünmeden verilen değerler en yaygın performans ve tutarlılık sorunlarının kaynağıdır.

### TTL'in görünmez tuzakları

**Cache stampede (thundering herd):** Popüler bir anahtarın TTL'i dolduğu anda, o anahtarı isteyen yüzlerce eşzamanlı istek aynı anda cache miss alır ve hepsi birden veritabanına yüklenir. Cache tam da yükü azaltması gereken anda veritabanını çökertir. Çözümler: girdinin süresi dolduğunda yalnızca **tek bir isteğin** yeniden hesaplamasına izin veren bir kilit (lock / mutex) kullanmak; süre dolmadan **kısa süre önce** proaktif yenileme yapmak (early recomputation); ya da süresi dolmuş değeri yeniden hesaplama tamamlanana kadar geçici olarak sunmaya devam etmek (stale-while-revalidate).

**Senkronize sona erme:** Birçok girdiyi aynı anda, aynı TTL ile doldurursanız (örneğin bir toplu ısıtma / cache warming işlemiyle), hepsi aynı anda expire olur ve toplu bir stampede yaratır. Bunu önlemek için TTL'lere küçük rastgele bir sapma (**jitter**) eklenir; böylece sona ermeler zamana yayılır.

## Eviction: TTL ile Karıştırılmamalı

Önemli bir ayrım: TTL bir girdinin **zaman** nedeniyle geçersiz olmasıdır; **eviction** ise cache'in **belleği dolduğu için** girdi atmasıdır. Cache sonlu bir bellekte yaşar; dolduğunda yeni veriye yer açmak için birilerini çıkarmak zorundadır. Bunu yöneten kurallar eviction politikalarıdır:

- **LRU (Least Recently Used):** En uzun süredir dokunulmamış girdiyi atar. Zamansal yerelliğe iyi uyar; en yaygın varsayılan seçimdir.
- **LFU (Least Frequently Used):** En az erişilen girdiyi atar. Erişim sıklığı belirgin biçimde farklıysa LRU'dan iyi olabilir ama eski ama sık kullanılmış girdilere takılıp kalabilir.
- **FIFO:** En eski girdiyi atar; basittir ama erişim desenini görmezden geldiği için genellikle zayıftır.

Doğru eviction politikası da yine iş yükünün yerellik profiline bağlıdır; körlemesine varsayılana güvenmek yerine hit oranını ölçüp seçmek gerekir.

## Yaygın Hatalar

**Her şeyi cache'lemek.** Cache bir bütçedir. Nadiren okunan ya da sürekli değişen veriyi cache'lemek bellek harcar, hit oranını düşürür ve invalidation yükünü artırır. Cache yalnızca **okuma/yazma oranı yüksek** ve **maliyeti yüksek** veriler için kazançlıdır.

**Cache miss cezasını unutmak.** Cache'e alışan bir sistem, cache çöktüğünde ya da soğuk başladığında (cold start) tüm yükü aniden veritabanına yıkar. Eğer veritabanı bu tam yükü kaldıramıyorsa, cache aslında gizli bir tek nokta hatasına (single point of failure) dönüşmüştür. Sağlam sistemler "cache olmadan da ayakta kalabilir miyim?" sorusunu ciddiye alır.

**Bayat veriyi görmezden gelmek.** Invalidation'ı eksik kurgulamak, kullanıcıya sessizce yanlış veri gösterir. Bu, çökme gibi gürültülü bir hata değildir; bu yüzden fark edilmesi aylar alabilir ve çok daha zararlı olabilir.

**Negatif sonuçları cache'lememek.** Bir sorgu "sonuç yok" dönüyorsa ve bunu cache'lemiyorsanız, var olmayan bir kaydı arayan istekler her seferinde veritabanına düşer. Bu, **cache penetration** denen bir saldırı/aşınma yüzeyidir. Var olmayan anahtarları da kısa TTL ile (null caching) işaretlemek gerekir.

**Cache anahtarı tasarımını ihmal etmek.** Tutarsız veya çakışan anahtar isimleri (örneğin versiyonu, dili, kullanıcı bağlamını anahtara katmamak) yanlış kullanıcıya yanlış veri sunma gibi ciddi güvenlik ve doğruluk hatalarına yol açar. Anahtar şeması cache mimarisinin sözleşmesidir.

**Serialization maliyetini gözden kaçırmak.** Dağıtık cache'te her okuma/yazma bir serialize/deserialize işlemidir. Çok büyük nesneleri cache'lemek, kazandığınız veritabanı süresini serialization'da geri kaybettirir.

## En İyi Pratikler

**Cache'i bir optimizasyon olarak ekleyin, mimari zorunluluk olarak değil.** Sistem cache olmadan da doğru çalışabilmeli; cache yalnızca hızlandırmalı. Bu ilke, cache'i güvenli biçimde devre dışı bırakabilmenizi ve arıza anında sistemin çalışmaya devam etmesini sağlar.

**Ölçün, tahmin etmeyin.** Hit oranı (hit rate), gecikme dağılımı ve veritabanına inen yük düzenli izlenmelidir. Düşük hit oranı, cache'in yanlış veriyi tuttuğunu ya da TTL'in yanlış olduğunu haber verir. Cache "kurulup unutulan" değil, sürekli gözlenen bir bileşendir.

**Tutarlılık ihtiyacını veri bazında belirleyin.** Her verinin tutarlılık gereksinimi aynı değildir. Kritik olan (bakiye, stok) için write-through veya kısa TTL, tolere edilebilir olan (öneriler, sayaçlar) için uzun TTL veya write-behind seçin. Tek bir strateji tüm sisteme dayatılmamalıdır.

**Stampede'e karşı baştan tasarlayın.** Popüler anahtarlar için kilitleme, erken yenileme veya stale-while-revalidate gibi bir koruma en baştan konmalıdır; stampede genellikle test ortamında değil, gerçek trafik zirvesinde ortaya çıkar.

**TTL'lere jitter ekleyin.** Senkronize sona ermeyi önlemek için TTL değerlerine küçük rastgele sapmalar katın.

**Invalidation'ı tek bir yerden yönetin.** Cache anahtarlarını üreten ve geçersiz kılan mantığı dağıtmak yerine merkezî bir katmanda toplayın. Böylece "hangi anahtar hangi veriye bağlı" bilgisi tek bir yerde tutulur ve bağımlılık kaçırma hataları azalır.

**Çok katmanlı cache'te invalidation'ı tüm katmanlara yayın.** In-process ve distributed cache birlikte kullanılıyorsa, bir geçersiz kılma olayının her iki katmana da ulaştığından emin olun.

## Kapanış

Cache, doğru uygulandığında bir sistemin ölçeklenebilirliğini ve kullanıcı deneyimini kökten değiştiren en güçlü araçlardan biridir. Ama özünde bir **takas mühendisliğidir**: hız karşılığında tutarlılık, basitlik karşılığında bellek, tazelik karşılığında yük dengesi. Cache-aside, write-through ve write-behind desenleri bu takasın farklı noktalarını temsil eder; invalidation ve TTL ise bu takasın günlük yönetim araçlarıdır. Usta bir mühendis, "cache ekleyeyim de hızlansın" diye düşünmez; "hangi veriyi, hangi katmanda, ne kadar bayatlıkla, hangi yazma desenıyle ve nasıl geçersiz kılarak cache'leyeceğim" sorusunu her seferinde bilinçli olarak cevaplar. Cache'in zor kısmı onu doldurmak değil, ne zaman ve nasıl boşaltacağını doğru bilmektir.
