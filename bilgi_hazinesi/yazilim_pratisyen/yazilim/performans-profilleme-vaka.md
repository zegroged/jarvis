# Performans Profilleme ve Optimizasyon — Bir Saha Vakası

## 1. Problem ve bağlam: bu iş ne zaman devreye girer

Performans optimizasyonu, çoğu ekipte yanlış zamanda ve yanlış sebeple başlar. Gerçek şu: kimse "hız" için değil, bir **iş baskısı** için gelir. Ya bir müşteri "sayfa donuyor" diye şikâyet etmiştir, ya faturanız (bulut maliyeti) üç ayda ikiye katlanmıştır, ya da bir SLA'yı (p99 yanıt süresi < 300ms gibi) kaçırıyorsunuzdur ve sözleşme cezası konuşuluyordur. Bu ayrım önemli, çünkü optimizasyonun **hedefi** ve **durma noktası** buradan çıkar. "Ne kadar hızlı yeterli?" sorusunun cevabı teknik değil, iş cevabıdır.

Deneyimsiz mühendisin ilk hatası burada başlar: bir metod yavaş görününce hemen onu hızlandırmaya girişir. Kıdemli mühendis önce şunu sorar: "Bu yavaşlık kimi, ne kadar, hangi koşulda etkiliyor ve bunu düzeltmek neyi kazandırır?" Çünkü optimizasyonun kendisi bir maliyettir — okunabilirlik düşer, kod karmaşıklaşır, bakım zorlaşır, yeni buglar girer. Yani optimizasyon her zaman bir **takas**tır ve takası ancak ölçülebilir bir kazanç haklı çıkarır.

Devreye girme anları tipik olarak şunlardır: (1) kullanıcıdan gelen somut yavaşlık şikâyeti, (2) yük altında çöken/çok yavaşlayan bir sistem (Black Friday senaryosu), (3) beklenmedik bulut/altyapı maliyeti, (4) bir yeni özelliğin var olan sıcak yolu (hot path) bozması, (5) batch/ETL işinin gece penceresine sığmaması. Her birinin karakteri farklıdır: birincisi genelde latency (gecikme), ikincisi throughput (verim) ve kaynak doygunluğu, üçüncüsü verimlilik/israf problemidir. Neyle uğraştığınızı ilk baştan doğru adlandırmazsanız, yanlış aracı çıkarırsınız.

## 2. Metodoloji ve karar ağacı — asıl değer burada

### Önce ölç, sonra tahmin etme (ama tahmini de kullan)

Klasik kural: "Ölçmeden optimize etme." Doğru ama eksik. Kıdemli mühendis ölçmeden **önce** bir hipotez kurar — ama ona âşık olmaz. Hipotez, nereye bakacağınızı söyler; ölçüm, haklı olup olmadığınızı söyler. İkisini karıştırmayın. "Bence ORM yavaştır" bir hipotezdir; profiler çıktısı kanıttır. Pratikte insanların %80'i hipotezini kanıt sanıp yanlış yeri optimize eder ve haftasını çöpe atar.

### Karar ağacının kökü: Latency mi, Throughput mu?

İlk çatal budur. Bir kullanıcı isteği **tek başına** yavaşsa (boş sistemde bile) bu bir latency problemidir — sıralı bir işlem zinciri fazla uzuyordur. Sistem tek istekte hızlı ama yük altında çöküyorsa bu throughput/doygunluk problemidir — bir yerde kuyruk büyüyor, bir kaynak (CPU, bağlantı havuzu, kilit, disk IO) tükeniyordur. Bu ikisi taban tabana farklı teşhis yolları ister. Latency'de tek bir isteğin izini (trace) sürersiniz; throughput'ta toplam davranışı, kuyrukları ve doygunluğu izlersiniz.

### İkinci çatal: Nerede zaman harcanıyor? CPU mu, bekleme mi?

Bu, sahada en çok atlanan ayrımdır. Bir istek 800ms sürüyorsa, bu 800ms'nin ne kadarı CPU **hesaplıyor**, ne kadarı bir şeyi **bekliyor**? Bekleme (off-CPU) demek: veritabanı cevabı, ağ çağrısı, disk, kilit (lock), bir semafor. CPU-bound bir problemde algoritma/veri yapısı değiştirirsiniz; wait-bound bir problemde paralelleştirir, batch'lersiniz, N+1'i kırarsınız, cache koyarsınız. 

Acemi, on-CPU profiler'ı (klasik sampling profiler) açar, "kod zaten çoğu zaman idle görünüyor" der ve kaybolur. Çünkü asıl zaman veritabanı beklemesinde geçiyordur ve on-CPU profiler bunu göstermez. Kıdemli mühendis burada **off-CPU** analizi ya da distributed tracing'e geçer. Genel kural: web/servis kodunun büyük çoğunluğunda darboğaz beklemededir, CPU değil. Ağır hesaplama (video, ML, sıkıştırma, kriptografi) yapmıyorsanız, muhtemelen IO'yu bekliyorsunuzdur.

### Üçüncü çatal: Sıcak yol gerçekten sıcak mı?

Amdahl Yasası'nın pratik hâli: toplam sürenin %5'ini tutan bir fonksiyonu ikiye katlasanız bile kazancınız %2.5'tir. Toplam sürenin %60'ını tutan fonksiyonu %30 iyileştirmek çok daha değerlidir. Bu yüzden profiler çıktısını **toplam etkisine göre** sıralarsınız — "self time" ve "total time" ayrımına dikkat ederek. Deneyimsizler en çok "en yavaş tek çağrıyı" düzeltir; kıdemliler "en çok toplam zaman yiyen yolu" düzeltir. Çağrı başına 200ms alan ama günde 3 kez çağrılan bir fonksiyon, çağrı başına 2ms alıp saniyede 5000 kez çağrılan fonksiyondan önemsizdir.

### Karar sırası, pratikte

1. **İş hedefini netleştir.** Hangi metrik, hangi eşik, kimi etkiliyor. (p50 mi p99 mu? Ortalama neredeyse hep yalan söyler; kuyruk kullanıcıları p99'da yaşar.)
2. **Ölçüm altyapısını kur.** Reprodüksiyon (yeniden üretim) yoksa hiçbir şey yapma. Yavaşlığı laboratuvarda tetikleyemiyorsan, düzelttiğini de doğrulayamazsın.
3. **Kaba kesim: latency mi throughput mu, CPU mu wait mi.** Yukarıdaki çatallar.
4. **En büyük tek katkıyı bul.** Flame graph ya da trace ile. Genelde tek bir baskın sebep vardır (Pareto). 
5. **Bir şeyi değiştir, tekrar ölç.** Aynı anda iki şey değiştirmek, hangisinin işe yaradığını bilmemek demektir. Bilimsel deney disiplini.
6. **Dur.** İş hedefine ulaştıysan dur. "Daha da hızlanabilir" cümlesi sonsuza kadar doğrudur; durma noktası iş hedefidir, mühendis egosu değil.

### Dördüncü çatal: Bu tekil bir istek problemi mi, sistemik bir örüntü mü?

Bazen tek bir endpoint yavaştır ve orada biter. Ama sahada asıl sinsi olan, **birçok yere yayılmış** aynı örüntüdür. Örneğin bir ORM'in "lazy loading" özelliği yüzünden N+1 problemi uygulamanın onlarca yerinde tekrar eder; siz birini düzeltirsiniz, üç ay sonra başka bir sayfada aynı belirti çıkar. Kıdemli mühendis, tekil bir vakayı çözerken "bu örüntü başka nerede var?" diye sorar ve mümkünse **sınıfsal** bir çözüm getirir — bir linter kuralı, bir kod inceleme kontrol listesi maddesi, ya da framework seviyesinde bir uyarı. Tek tek bug ezmek yerine bug'ın **üreme kaynağını** kesmek, kıdemliyi acemiden ayıran şeylerden biridir.

### Beşinci çatal: Doğru mu ölçüyorum, yoksa gözlemci etkisi mi var?

Ölçüm aracının kendisi sistemi değiştirir. Ağır enstrümantasyon (her fonksiyona zamanlayıcı koymak gibi) o kadar çok ek yük getirebilir ki, profiler açıkken darboğaz görünen yer, profiler kapalıyken hiç darboğaz olmayabilir. Buna gözlemci etkisi (observer effect) denir. Kıdemli mühendis, ölçtüğü rakamların ölçüm aracından mı yoksa gerçek koddan mı geldiğini sorgular; ölçümü hem düşük ek yüklü sampling ile hem de kaba duvar-saati (wall-clock) ile çapraz kontrol eder. Ayrıca "ısınma" (warmup) etkisini bilir: JIT derleyicili ya da cache ısınması gereken sistemlerde ilk çağrılar her zaman yavaştır; kararlı hâli ölçmek için önce sistemi ısıtır, sonra ölçer. İlk isteğin süresini "normal" sanmak klasik acemi hatasıdır.

### Kritik takaslar

- **Cache** en güçlü ama en tehlikeli araçtır: latency'yi uçurur, ama tutarlılık (stale data), invalidasyon karmaşıklığı ve bellek maliyeti getirir. "Bilgisayar bilimindeki iki zor şeyden biri cache invalidasyonudur" lafı boşuna değil.
- **Paralelleştirme** wait-bound işlerde harikadır, CPU-bound işlerde çekirdek sayısıyla sınırlıdır ve senkronizasyon maliyeti getirir.
- **Batch'leme** ağ/DB turlarını azaltır ama latency ile throughput arasında takas yapar (bir isteği bekletip toplu gönderirsiniz).
- **Bellek vs hız**: precompute/lookup table hız kazandırır, bellek yer. Bazen doğru cevap "daha çok RAM al" — mühendis saatinden ucuzdur.

## 3. Gerçek bir vaka üzerinden yürüyüş: yavaş sipariş listesi

Somut bir senaryo alalım. Bir e-ticaret panelinde "Siparişlerim" sayfası, bazı müşterilerde 6-8 saniyede açılıyor, çoğunda hızlı. Klasik "bende çalışıyor" vakası.

### Belirti ve ilk teşhis

İlk refleks (acemi): kodu açıp okumak, "burada bir döngü var, optimize edeyim" demek. Doğru refleks (kıdemli): önce **kimde yavaş** olduğunu bulmak. Loglara p99 latency'yi kullanıcı bazında kırarak bakıyoruz. Görülüyor ki yavaşlık, **çok sayıda siparişi olan** müşterilerde çıkıyor. Bu tek bilgi bile karar ağacını daraltır: süre veri boyutuyla büyüyor → muhtemelen bir O(n) veya daha kötü bir örüntü, ya da istek başına iş sayısı sipariş sayısıyla artıyor.

Tracing açıyoruz. Tek bir yavaş isteğin izinde şunu görüyoruz: uygulama, ana sorgudan sonra **her sipariş için ayrı bir veritabanı sorgusu** atıyor. 300 siparişi olan kullanıcıda 1 + 300 sorgu. Bu, meşhur **N+1 sorgu problemi**. Off-CPU zamanının neredeyse tamamı DB round-trip beklemesinde. On-CPU profiler açsaydık kod "boşta" görünürdü ve yanlış yere bakardık — çatal ikiyi (CPU mu wait mi?) doğru geçmenin bedeli budur.

### Zafiyetli kod (dilden bağımsız, pseudo)

```
orders = db.query("SELECT * FROM orders WHERE user_id = ?", userId)

for order in orders:
    # HER sipariş için ayrı sorgu — N+1'in kalbi
    order.customer = db.query("SELECT * FROM users WHERE id = ?", order.customer_id)
    order.items    = db.query("SELECT * FROM order_items WHERE order_id = ?", order.id)
    order.total    = 0
    for item in order.items:
        # üstüne bir sorgu daha — N*M patlaması
        product = db.query("SELECT price FROM products WHERE id = ?", item.product_id)
        order.total += product.price * item.qty

render(orders)
```

Bu kod code review'dan geçer, testleri yeşildir, demo'da uçar. Çünkü demo verisinde kullanıcının 3 siparişi vardır. Üretimde sadık müşterinin 300 siparişi olunca çöker. Bu, "işe yarar gibi görünüp üretimde patlayan" tuzağın ders kitabı örneğidir.

### Teşhisi doğrulama

Değiştirmeden önce hipotezi kanıtlıyoruz. DB'nin slow query log'unu ya da bir tracing aracını açıp o tek istekte kaç sorgu atıldığını sayıyoruz: 1 + 300 + 300×(ortalama kalem). Sayı, hipotezle bire bir uyuşuyor. Şimdi düzeltmenin **neyi ne kadar** kazandıracağını da tahmin edebiliyoruz: sorgu sayısını binlerden 2-3'e indireceğiz.

### Düzeltilmiş kod

```
orders = db.query("SELECT * FROM orders WHERE user_id = ?", userId)
orderIds    = orders.map(o => o.id)
customerIds = orders.map(o => o.customer_id)

# Tek seferde toplu çek (IN sorgusu) — N+1 kırıldı
customers = db.query("SELECT * FROM users WHERE id IN (?)", customerIds)
items     = db.query("SELECT * FROM order_items WHERE order_id IN (?)", orderIds)
productIds = items.map(i => i.product_id)
products  = db.query("SELECT id, price FROM products WHERE id IN (?)", productIds)

# Bellekte hash map'lerle O(1) eşleştir
customerById = index_by(customers, c => c.id)
productById  = index_by(products,  p => p.id)
itemsByOrder = group_by(items, i => i.order_id)

for order in orders:
    order.customer = customerById[order.customer_id]
    order.items    = itemsByOrder[order.id]
    order.total    = sum(order.items, i => productById[i.product_id].price * i.qty)

render(orders)
```

Sorgu sayısı: **4**, sipariş sayısından bağımsız. 300 siparişli kullanıcıda süre 7 saniyeden ~120ms'ye indi. Kritik nokta: burada tek bir satır bile "daha hızlı algoritma" değil. Sadece **iş sayısını** (DB round-trip) azalttık. Sahadaki performans işlerinin çoğu böyledir — akıllı algoritma değil, gereksiz işi silmek.

### Bir sonraki katman: gerçekten dur mu, devam mı?

120ms iş hedefini karşılıyorsa **dururuz**. Ama diyelim ki bu sayfa saniyede 500 kez çağrılıyor ve `products` tablosu neredeyse hiç değişmiyor. O zaman ürün fiyatlarını bir cache'e koymak DB yükünü daha da düşürür. Ama dikkat: fiyat değişince cache invalidasyonu gerekir. Fiyat yanlış gösterirsek bu bir **iş hatası**, performans kazancından beter. İşte takas kararı: kazanç (DB yükü) net mi, invalidasyon riskini haklı çıkarıyor mu? Çoğu zaman kısa TTL'li (örn. 60 sn) bir cache doğru orta yoldur — ama bu kararı iş sahibiyle konuşarak verirsiniz, sessizce değil.

## 4. Acemi vs pro: yaygın hatalar ve gözden kaçanlar

**Ortalamaya bakmak.** Acemi ortalama yanıt süresine bakar, "180ms, gayet iyi" der. Kullanıcıların yarısı belki 40ms yaşıyor, ama p99'daki kullanıcı 4 saniye yaşıyordur ve şikâyet eden odur. Kıdemli her zaman dağılıma bakar: p50, p95, p99, p999. Ortalama, birkaç yavaş isteği okyanusta gizler. "Kuyruk latency'si" (tail latency) çoğu sistemin gerçek problemidir.

**Mikro-benchmark'a kanmak.** Bir fonksiyonu izole edip "10 milyon kez çağırdım, çok hızlı" demek. Ama JIT ısınması, cache locality, gerçek veri dağılımı, eşzamanlılık — hiçbiri o benchmark'ta yok. Üretimde farklı davranır. Mikro-benchmark bir ipucudur, kanıt değildir. Kıdemli, mümkünse üretim benzeri yükle ölçer.

**Erken optimizasyon.** Knuth'un lafı ("premature optimization is the root of all evil") sürekli yanlış anlaşılır. Demek istediği: **ölçmeden**, sıcak yolu bilmeden yapılan optimizasyon kötüdür. Yoksa "hiç düşünme" demek değil. Acemi ya hiç düşünmez ya da her satırı erkenden optimize edip kodu okunmaz hâle getirir. Doğrusu: temiz ve doğru yaz, ölç, sadece kanıtlanmış darboğazı optimize et.

**Tek istekte ölçüp yük altında ölçmemek.** Kod tek kullanıcıda uçar, 1000 eşzamanlı kullanıcıda çöker. Neden? Bağlantı havuzu tükenir, bir kilit (lock) etrafında kuyruk oluşur, GC baskısı artar, thread'ler birbirini bekler. Doğrusal ölçeklenme varsayımı yük altında kırılır. Kıdemli, yük testi yapmadan "ölçekleniyor" demez.

**Coordinated omission.** Yük test araçlarında sinsi bir tuzak: araç bir istek yavaşladığında bir sonrakini geç gönderir, böylece kötü sonuçları "kaydetmez". Ölçtüğünüz latency gerçekte yaşanandan iyi görünür. Bunu bilmeyen mühendis, sistemin p99'unu olduğundan iyi sanır.

**Yanlış katmanı suçlamak.** "ORM yavaş", "GC yavaş", "dil yavaş" — çoğu zaman günah keçisi. Gerçek sebep neredeyse hep **sizin kodunuzun** ürettiği örüntüdür: N+1, gereksiz serileştirme, yanlış index, döngü içinde IO. Aracı suçlamadan önce kendi çağrı örüntünüzü profilleyin.

**Index'i unutmak / yanlış index.** DB tarafında bir `WHERE` ya da `JOIN` kolonunda index yoksa, sorgu tam tablo taraması yapar. 1000 satırda fark etmez, 10 milyon satırda ölümdür. Ama tersi de tuzak: her kolona index koymak yazma (INSERT/UPDATE) hızını düşürür ve yer yer. Ayrıca bileşik (composite) index'lerde kolon **sırası** önemlidir: `(user_id, created_at)` index'i, `user_id` ile filtreleyip `created_at` ile sıralayan sorguyu hızlandırır ama sadece `created_at` ile filtreleyen sorguya yaramaz. Kıdemli, sorgu planına (EXPLAIN) bakar, index'i körlemesine eklemez.

**"Bende çalışıyor" ve veri ölçeği körlüğü.** Geliştirici makinesinde tablo 500 satırdır, üretimde 50 milyon. Geliştiricinin ağı DB'ye 0.2ms, üretimde uygulama ile DB farklı erişim bölgelerinde 30ms. Aynı N+1 kodu, birinde 60ms toplam gecikme yaparken diğerinde 9 saniye. Acemi, kendi makinesindeki hızı gerçeklik sanır. Kıdemli, üretim veri ölçeğini ve ağ topolojisini kafasında tutar; mümkünse üretime yakın boyutta test verisiyle çalışır.

**Gereksiz serileştirme ve veri taşıma.** Bir API'nin her istekte 2 MB JSON döndürdüğünü ama istemcinin sadece 5 alanı kullandığını düşünün. Serileştirme CPU yer, ağ bant genişliği yer, istemci tarafında ayrıştırma (parse) yer. Sıcak yolda "her ihtimale karşı tüm alanları döndürelim" tembelliği, ölçekte pahalı bir israftır. Kıdemli, sıcak yolda taşınan veri miktarını da bir maliyet kalemi olarak görür.

**Optimize ederken doğruluğu bozmak.** Cache koyup stale veri göstermek, paralelleştirip race condition sokmak, batch'leyip bir hatada tüm batch'i kaybetmek. Hız için doğruluğu feda etmek, çoğu zaman en pahalı hatadır. "Yanlış cevabı çok hızlı vermenin" bir değeri yoktur.

## 5. Araçlar ve saha notları

**Sampling profiler (on-CPU).** Belirli aralıklarla stack'in fotoğrafını çeker, hangi fonksiyonun CPU'da en çok göründüğünü verir. CPU-bound problemlerde birinci araç. Düşük ek yük getirir, üretimde bile açık tutulabilen türleri var. Çıktıyı **flame graph** olarak okuyun: genişlik = toplam zaman, yükseklik = çağrı derinliği. Geniş "plato"lar sıcak yollardır. Dar ve yüksek kuleler değil, **geniş tabanlar** ilgilendirir sizi.

**Off-CPU / wait analizi.** Kod CPU'da değil de beklerken zaman harcıyorsa (IO, lock, DB) bunu gösteren araçlar. Web servislerinde asıl cevap genelde buradadır. On-CPU profiler "kod boşta" diyorsa mutlaka off-CPU'ya bakın — yoksa asıl zamanı hiç görmezsiniz.

**Distributed tracing.** Mikroservis dünyasında tek isteğin servisler arası yolculuğunu span span gösterir. "Hangi servis / hangi DB çağrısı zamanı yedi" sorusunun tek pratik cevabı. Bir isteğin waterfall görünümünde, uzun bir span hemen göze çarpar. N+1'i, seri yapılan ama paralel yapılabilecek çağrıları burada yakalarsınız.

**Veritabanı tarafı: EXPLAIN / query plan ve slow query log.** Bir sorgunun neden yavaş olduğunu tahminle değil, planla anlarsınız. Full table scan mı, index mi kullanıyor, kaç satır tarıyor, join stratejisi ne? Slow query log, eşik üstü süren sorguları toplar — üretimdeki gerçek suçluları bulmanın en dürüst yolu. Sahada altın kural: performans şikâyetinin çoğu, sonunda bir DB sorgusuna iner.

**APM / observability (metrikler + loglar + tracing bir arada).** Üretimde neyin yavaşladığını **canlı** görmek için. p50/p99 grafikleri, hata oranı, doygunluk (CPU, bellek, bağlantı havuzu). Google'ın "dört altın sinyali" pratik bir çerçeve: Latency, Traffic, Errors, Saturation. Bu dördünü panoya koyun; çoğu olayı önce burada görürsünüz.

**Yük/stres testi araçları.** Üretime çıkmadan davranışı yük altında görmek için. Kademeli yük artırıp sistemin nerede dizinin üstüne çöktüğünü (knee point) bulursunuz. Coordinated omission'a dikkat eden, gerçekçi yük profili üreten araçları tercih edin. Test verisi **gerçek dağılıma** benzemeli — hepsi aynı kullanıcıya ait 3 sipariş değil, gerçekteki gibi çarpık dağılım.

**Bellek profilleyiciler ve heap analizi.** Yavaşlığın sebebi bazen GC baskısıdır: çok fazla kısa ömürlü nesne üretmek, GC'yi sürekli tetikler ve "duraklama"lar (pause) latency'de tümsek yapar. Heap profiler, en çok allocation yapan yolu gösterir. Bellek sızıntısı (leak) da zamanla sistemi yavaşlatıp çökertir; heap büyümesini zaman içinde izleyin.

### Pratik saha tüyoları

- **Reprodüksiyon her şeydir.** Yavaşlığı isteyerek tetikleyemiyorsan, düzelttiğini de kanıtlayamazsın. İlk saatini güvenilir bir tekrar senaryosu kurmaya harca; gerisi hızlanır.
- **Bir seferde tek değişiklik.** İki şeyi aynı anda değiştirip iyileşme görürsen, hangisinin işe yaradığını bilmezsin — ve biri gizlice bir şeyi bozmuş olabilir.
- **Önce en ucuz kazanç.** Bir index eklemek 10 dakika, mimariyi paralelleştirmek 2 hafta sürebilir. Aynı kazancı veriyorsa ucuzunu al. En pahalı ama gösterişli çözüme koşmak, mühendisliğin değil egonun kararıdır.
- **Ölçüm ek yükünü unutma.** Profiler'ın kendisi de yük getirir; ağır enstrümantasyon, ölçtüğün şeyi değiştirebilir (gözlemci etkisi). Üretimde düşük ek yüklü sampling'i tercih et.
- **Rakamları yaz.** "Öncesi 7000ms, sonrası 120ms, sorgu 301→4." Bu rakamlar hem kararını haklı çıkarır hem de altı ay sonra "burayı neden böyle yaptık" sorusuna cevaptır.
- **Durmayı bil.** İş hedefine ulaştın mı dur. Kalan %5'i kovalamak, çoğu zaman kodun okunabilirliğini ve senin haftanı yakar, karşılığında kimsenin fark etmeyeceği bir kazanç verir.
- **Cache'i en son düşün, ilk değil.** Cache bir kazanç değil, bir borçtur (invalidasyon, tutarlılık, bellek). Önce gereksiz işi sil (N+1, kötü index, fazladan serileştirme); cache'i o borcu üstlenmeye değecek net kazanç varken koy.

Özetle: performans işi bir dedektiflik işidir, kahramanlık değil. Belirtiyi doğru adlandır, çatalları doğru geç (latency/throughput, CPU/wait, sıcak yol gerçekten sıcak mı), en büyük tek katkıyı bul, tek değişiklik yap, tekrar ölç, iş hedefine ulaşınca dur. Sahadaki performans kazançlarının çoğu zekice bir algoritma değil, birinin fark etmeden yerleştirdiği gereksiz işi silmektir.
