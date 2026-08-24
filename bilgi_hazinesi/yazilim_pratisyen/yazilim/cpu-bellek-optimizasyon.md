# CPU/Bellek Optimizasyon Yargısı

> Bu metin "profiler nasıl açılır" anlatmıyor. Onu dokümantasyon zaten anlatıyor. Bu metin, 15 yıl üretim sistemi taşımış birinin kafasının içindeki karar ağacını anlatıyor: bir yavaşlık raporu geldiğinde nereye bakarım, hangi belirti beni hangi yöne iter, acemiyi hangi tuzak yer, ve "mikro-optimizasyon" dediğimiz şeyin çoğunun neden zaman kaybı olduğunu.

---

## 1. Problem / bağlam: bu iş neyi çözer, ne zaman devreye girer

Optimizasyon bir "faaliyet" değil, bir **cevap**tır. Cevap verdiği soru şudur: *"Bu sistem, kabul edilebilir maliyetle karşılayamadığı bir talep altında mı?"* Eğer sistem yeterince hızlı ve yeterince ucuzsa, optimizasyon yapmak sadece risk üretir — çalışan koda dokunursun, bug ekleme ihtimalin artar, okunabilirliği düşürürsün ve karşılığında kullanıcının hissetmeyeceği 4 milisaniye kazanırsın.

Bu yüzden kıdemli mühendisin optimizasyona bakışı temelde **savunmacıdır**. İlk soru "nasıl hızlandırırım" değil, "**gerçekten bir problem var mı, varsa nerede ve ne kadar**" sorusudur.

Optimizasyon tipik olarak şu durumlarda devreye girer ve bu durumlar birbirinden **çok farklı** disiplinlerdir — karıştırmak en yaygın hatadır:

- **Latency (gecikme) problemi:** Tek bir isteğin cevap süresi uzun. Kullanıcı bekliyor. p99 latency SLA'yı deliyor. Burada dert "iş miktarı" değil, "kritik yol"dur.
- **Throughput (verim) problemi:** Sistem saniyede yeterince iş çıkaramıyor. Tek istek hızlı ama toplamda tıkanıyor. Burada dert paralellik, kilitlenme, kaynak doygunluğudur.
- **Kaynak maliyeti problemi:** Sistem hızlı ama çok RAM/CPU yiyor, bulut faturası şişiyor, ya da OOM (Out Of Memory) ile çöküyor. Burada dert verimlilik ve ayak izidir.
- **Kararlılık problemi (en sinsisi):** Sistem çoğu zaman iyi ama arada bir "takılıyor". Bu genellikle bellek yönetimiyle (GC duraklamaları, allocation fırtınaları, bellek sızıntısı) ya da kuyruk birikmesiyle ilgilidir.

Bir junior gelip "uygulamayı optimize edelim" der. Senior sorar: **"Hangisini? Latency mi, throughput mu, maliyet mi, kuyruk mu? Ölçün ne? Hedef ne?"** Bu dört soruya cevap yoksa optimizasyon başlamamalıdır, çünkü yön yoktur.

---

## 2. Metodoloji ve karar ağacı (asıl değer)

### 2.0. Altın kural: önce ölç, tahmin etme

Bu klişe gibi gelir ama 15 yılın en pahalı dersidir. **İnsanın darboğaz sezgisi neredeyse her zaman yanlıştır.** "Şu döngü yavaştır herhalde" diye başlayıp üç gün optimize ettiğin şeyin toplam sürenin %0.3'ü olduğunu, asıl zamanın bir yerdeki senkron DNS çözümlemesinde ya da gizli bir N+1 sorgusunda geçtiğini defalarca görürsün. Ölçmeden dokunmak, karanlıkta ameliyat yapmaktır.

### 2.1. İlk ayrım: sistem CPU-bound mu, bekleme-bound mu?

Bu, karar ağacının kökü. Yanlış dalı seçersen günlerini kaybedersin.

Belirtiye bak:
- **CPU %100'e yakın, çekirdekler yanıyor, iş de ilerliyor** → CPU-bound. Optimizasyon = daha az iş yap ya da işi daha iyi dağıt.
- **CPU düşük (%15) ama sistem gene de yavaş, istekler bekliyor** → bu **bekleme-bound (I/O-bound / lock-bound)**. CPU'yu optimize etmek buraya hiçbir şey katmaz. İşlemci boş boş oturuyor; sistem bir yerde *bekliyor*: disk, ağ, veritabanı, bir mutex, bir bağlantı havuzunun tükenmesi.

Junior'ın klasik hatası: latency yüksek diye algoritmayı optimize etmeye girişmek, oysa istek zamanının %95'i veritabanı cevabını beklemekte geçiyor. Kodun ne kadar hızlı olduğu önemsiz — thread orada uyuyor.

**Pratik teşhis:** İstek düşük CPU altında yavaşsa, bir "bekleme profili" (wall-clock / off-CPU analiz) çıkar. "On-CPU" profiler sana sadece meşgul olduğun zamanı gösterir; bekleme problemini gizler. Bu ayrımı bilmemek en sık yapılan profiling hatasıdır.

### 2.2. Latency probleminde karar ağacı

1. **Kritik yolu izole et.** Bir isteğin uçtan uca zamanını parçalara böl (distributed tracing / span'ler). Zamanın çoğu nerede? %80 kural: genelde tek bir aşama zamanın çoğunu yer.
2. **O aşama I/O mu, hesaplama mı?**
   - I/O ise: gereksiz round-trip var mı? (N+1 sorgu klasiği.) Batch'lenebilir mi? Paralelleştirilebilir mi? Cache'lenebilir mi? Senkron olan asenkron olabilir mi?
   - Hesaplama ise: algoritmik karmaşıklık mı sorun (O(n²) bir yerde gizli mi?), yoksa sabit-çarpan mı (allocation, kopyalama, serialization)?
3. **Kuyruk gecikmesi mi var?** p50 iyi ama p99 kötüyse, çoğu zaman sorun "kod yavaş" değil, "istek işlenmeden önce bir kuyrukta bekliyor". Bu thread pool doygunluğu, GC duraklaması ya da lock contention'dır. p99'u p50'den ayırmak, "ortalama" bakan junior'ın göremediği şeydir.

**Takas:** Cache eklemek latency'yi düşürür ama tutarlılık (stale data) ve bellek maliyeti getirir. Paralelleştirme latency'yi düşürür ama karmaşıklık ve race condition riski getirir. Bedava öğle yemeği yoktur; her optimizasyon bir yeri şişirir.

### 2.3. Throughput probleminde karar ağacı

1. **Doygun kaynak hangisi?** CPU mu, bellek bandgenişliği mi, disk IOPS mu, ağ mı, bir downstream servis mi? Doygun olmayanı optimize etmek hiçbir şey değiştirmez — Amdahl yasası acımasızdır.
2. **Seri bir darboğaz var mı?** 32 çekirdeğin var ama throughput tek çekirdek gibi mi davranıyor? Muhtemelen global bir kilit (lock) ya da tek bir paylaşılan kaynak (tek bağlantı, tek kuyruk, tek mutex) her şeyi seri hale getiriyor. Bu, "ölçeklenmiyor" şikâyetinin en yaygın kök nedenidir.
3. **Contention mı, coherency mi?** İki thread aynı cache line'a yazıyorsa (false sharing), fiziksel olarak ayrı değişkenler bile birbirini yavaşlatır. İleri seviye ama üretimde gerçek.

### 2.4. Bellek probleminde karar ağacı

Bellek iki farklı derdi barındırır, karıştırma:

- **Sızıntı (leak) / sınırsız büyüme:** Bellek zamanla monoton artıyor, sonunda OOM. Kök neden: bir yerde referans bırakılıyor ve serbest kalmıyor (unbounded cache, dinlenmeyen event listener, büyüyen bir liste, kapatılmayan kaynak). Çözüm profiling değil, **heap'in zaman içindeki sahiplik grafiğini** incelemektir: "bu nesneleri kim tutuyor?"
- **Allocation basıncı (churn):** Toplam bellek sabit ama sürekli nesne yaratılıp atılıyor. GC'li dillerde bu, sık ve uzun GC duraklamalarına dönüşür — CPU'nu yer ve latency spike'ları üretir. Belirti: CPU'nun önemli kısmı GC'de, latency grafiğinde düzenli dişler. Çözüm: sıcak yolda allocation'ı azaltmak (nesne yeniden kullanımı, buffer havuzu, değer tipleri, gereksiz kopya/serialization kaldırma).

**Karar:** Bellek grafiği "testere dişi ama tavanı sabit" ise → churn/GC problemi. "Sürekli yukarı, düşmüyor" ise → sızıntı. Bu iki grafiği ayırt etmek teşhisin yarısıdır.

### 2.5. Genel felsefe: optimizasyon sırası

Kıdemli mühendisin izlediği maliyet/fayda sırası (ucuzdan pahalıya, güvenliden riskliye):

1. **İşi tümden yapma.** En hızlı kod çalışmayan koddur. Gereksiz sorguyu, gereksiz hesabı, gereksiz kopyayı sil. En büyük kazançlar burada.
2. **İşi daha az sıklıkta yap.** Cache, memoization, debounce, batch.
3. **İşi daha iyi algoritmayla yap.** O(n²) → O(n log n). Veri yapısını değiştir (yanlış veri yapısı en sık ve en görünmez darboğaz).
4. **İşi paralel yap.** Ancak seri darboğazı çözdükten sonra.
5. **İşi daha hızlı yap (mikro-optimizasyon).** En son, en riskli, en az getirili. Sıcak yolun gerçekten sıcak olduğunu ölçüyle kanıtladıktan sonra.

Junior 5'ten başlar. Senior 1'den başlar ve çoğu zaman 3'e varmadan problemi çözer.

---

## 3. Gerçek örnek üzerinden yürüyüş: zafiyetli → teşhis → düzeltilmiş

Somut, üretimde defalarca görülen bir senaryo. Dil-bağımsız anlatıyorum ama gerçek.

### Senaryo: "Sipariş listesi sayfası yavaşladı"

Bir e-ticaret panelinde admin sipariş listesini açıyor. Başta 200 ms'de açılan sayfa, veri büyüdükçe 8 saniyeye çıkmış. Junior refleksi: "Veritabanı yavaş, index ekleyelim" ya da "sunucuyu büyütelim".

**Zafiyetli kod (mantığı):**

```
siparisler = db.sorgula("SELECT * FROM orders WHERE tarih > ? LIMIT 100", buGun)
for siparis in siparisler:
    musteri   = db.sorgula("SELECT * FROM customers WHERE id = ?", siparis.musteri_id)
    kalemler  = db.sorgula("SELECT * FROM order_items WHERE order_id = ?", siparis.id)
    siparis.musteri_adi   = musteri.ad
    siparis.toplam        = kalemleri_topla(kalemler)
render(siparisler)
```

**Adım 1 — Ölç, tahmin etme.** Tracing açılır. Toplam 8 saniyenin dağılımı:
- Ana sorgu: 15 ms
- Döngü içi: 7.9 saniye (!)
- Render: 40 ms

CPU %12. Yani sistem **CPU-bound değil, bekleme-bound**. Junior burada "kod yavaş" der ve döngüyü optimize etmeye çalışır — yanlış dal.

**Adım 2 — Kök neden.** Döngü 100 kez dönüyor, her dönüşte 2 sorgu = 200 ek veritabanı gidiş-gelişi. Klasik **N+1 problemi**. Her sorgu tek başına hızlı (2 ms), ama 200 × ağ round-trip'i = saniyeler. Sorun sorgunun *yavaşlığı* değil, *sayısı* ve her birinin bekleme maliyeti.

Index eklemek buraya neredeyse hiçbir şey katmaz — sorgular zaten hızlı. Sunucuyu büyütmek de katmaz — CPU zaten boş. İkisi de junior'ın yaptığı ve para/zaman harcayıp problemi çözmeyen hamlelerdir.

**Adım 3 — Düzeltme (optimizasyon sırası #1: işi daha az sıklıkta yap).** 200 sorguyu 2'ye indir:

```
siparisler = db.sorgula("SELECT * FROM orders WHERE tarih > ? LIMIT 100", buGun)
musteri_idler = benzersiz(s.musteri_id for s in siparisler)
siparis_idler = [s.id for s in siparisler]

musteriler = db.sorgula("SELECT * FROM customers WHERE id IN (?)", musteri_idler)
              |> id_ile_indeksle
kalemler   = db.sorgula("SELECT order_id, ... FROM order_items WHERE order_id IN (?)", siparis_idler)
              |> order_id_ile_grupla

for siparis in siparisler:
    siparis.musteri_adi = musteriler[siparis.musteri_id].ad
    siparis.toplam      = kalemleri_topla(kalemler[siparis.id])
render(siparisler)
```

Sonuç: 8 saniye → ~120 ms. Kod satır sayısı arttı ama gidiş-gelişten kurtulduk. **Not:** `IN (...)` listesi de çok büyürse yeni bir problem doğar (sorgu planı bozulabilir); o zaman batch'leme ya da JOIN'e geçilir. Her çözümün bir sonraki ölçekte yeni bir sınırı vardır — bunu bilmek senior'ı junior'dan ayırır.

**Adım 4 — İkinci kat problem.** Diyelim düzelttik ama sayfa ayda bir 3 saniyeye zıplıyor. Tracing gösteriyor ki spike anında ana sorgu 15 ms değil 2.5 saniye. Bu artık **gerçekten** bir veritabanı problemi — ama ilk teşhis yanlış olsaydı hiç buraya gelemezdik. Burada `EXPLAIN` çekilir, index'in kullanılıp kullanılmadığına, tablo taraması olup olmadığına bakılır. İşte index tartışması *burada* anlamlı — junior'ın en baştan atladığı yerde değil.

### İkinci senaryo: bellek — sinsi churn

Bir veri işleme servisi çalışıyor, latency çoğu zaman 20 ms ama saniyede bir 300 ms'ye fırlıyor. CPU'nun %40'ı GC'de.

**Zafiyetli mantık:** Sıcak yolda her kayıt için yeni geçici nesneler, yeni string birleştirmeleri, yeni ara diziler yaratılıyor. Saniyede yüz binlerce kısa ömürlü nesne. GC yetişmeye çalışırken düzenli olarak durakla­tıyor (stop-the-world).

**Teşhis:** Allocation profili çıkarılır — "byte cinsinden en çok nereden allocation geliyor?" Bu, CPU profilinden farklı bir görünümdür ve çoğu junior bunu hiç açmaz. Görülür ki sıcak yolda log formatlaması ve gereksiz bir kopyalama toplam allocation'ın %70'ini üretiyor.

**Düzeltme:** Sıcak yoldan formatlamayı çıkar (lazy/koşullu logla), tekrar kullanılabilir buffer'a geç, gereksiz kopyayı kaldır. Allocation %70 düşer, GC duraklamaları kaybolur, p99 latency düzelir. Dikkat: tek bir satırlık CPU bile değişmedi — kazanç tamamen *bellek davranışından* geldi. CPU profiler'a bakan biri bu problemi asla göremezdi.

---

## 4. Acemi vs pro: yaygın hatalar ve sinsi tuzaklar

**1. Ölçmeden optimize etmek.** En temel hata. "Şurası yavaştır herhalde." Sezgi neredeyse hep yanlış yeri gösterir. Pro önce profiler/tracing açar, hipotezini ölçüyle kanıtlar.

**2. Yanlış metriğe bakmak — ortalamaya güvenmek.** Junior "ortalama latency 50 ms, iyi" der. Pro p50, p95, p99, p999'a bakar. Kullanıcı deneyimini bozan ortalama değil, **kuyruk** (tail latency)'tur. Ortalama, arada bir 5 saniye bekleyen %1'lik kullanıcıyı gizler — ve o %1 genelde en değerli, en çok veri üreten kullanıcıdır.

**3. Mikro-benchmark yanılgısı.** İki fonksiyonu izole bir döngüde kıyaslayıp "bu %30 hızlı" demek. Gerçekte: (a) o fonksiyon toplam sürenin %0.5'i, (b) izole benchmark'ta CPU cache sıcak, gerçekte soğuk, (c) derleyici ölü kodu eleyip benchmark'ı anlamsızlaştırmış. Mikro-benchmark'lar yalan söyler; asıl kanıt üretim benzeri yük altında uçtan uca ölçümdür.

**4. Erken optimizasyon.** Henüz problem yokken, "ileride lazım olur" diye kodu karmaşıklaştırmak. Bunun bedeli okunabilirlik ve bug'dır, karşılığı ise çoğu zaman hiç gelmeyecek bir yük. Pro basit ve doğru yazar, ölçer, sadece kanıtlanmış darboğazı optimize eder.

**5. CPU/bekleme ayrımını atlamak.** Düşük CPU altında yavaş sistemi algoritma optimize ederek düzeltmeye çalışmak. Thread orada I/O bekliyorsa kodun hızı önemsizdir.

**6. Cache'i "çözüm" sanıp tutarlılık borcunu görmezden gelmek.** Cache eklemek kolay; ama cache invalidation, stale data, cache stampede (aynı anda binlerce istek boş cache'i doldurmaya çalışır ve backend'i çökertir), bellek şişmesi gelir. "Cache ekledik, hızlandı" diyen junior, üç hafta sonra "kullanıcılar eski fiyat görüyor" bug'ıyla döner. Cache bir optimizasyon değil, bir **dağıtık sistem problemi**dir.

**7. Yerelde hızlı, üretimde patlayan.** Yerelde 10 kayıtla test edip "hızlı" demek. Üretimde 10 milyon kayıt var, O(n²) davranış yerelde görünmez. Ölçek, davranışı niteliksel olarak değiştirir — küçük veride gizlenen her şey büyük veride patlar.

**8. GC'yi düşman sanmak.** "GC'yi kapatalım / elle tune edelim." Çoğu zaman problem GC değil, GC'ye iş yaratan allocation churn'ü. Kaynağı düzeltmeden GC parametreleriyle oynamak, musluğu açık bırakıp yeri paspaslamaktır.

**9. Paralelleştirmenin bedava olduğunu sanmak.** "Thread ekleyelim, hızlanır." Seri bir darboğaz varsa (paylaşılan kilit) thread eklemek işleri **yavaşlatır** — contention artar, cache coherency trafiği patlar. Amdahl yasası: seri kısım %5 ise, sonsuz çekirdekle bile en fazla 20 kat hızlanırsın.

**10. String ve serialization'ı ucuz sanmak.** Sıcak yolda log formatlaması, JSON serialize/deserialize, gereksiz string birleştirme — bunlar sessiz allocation ve CPU canavarlarıdır. Profilde çıkana kadar kimse şüphelenmez.

**11. "İşe yarar gibi görünüp üretimde patlayan" bağlantı havuzu.** Junior havuz boyutunu yükseltir, yerelde düzelir. Üretimde veritabanının bağlantı limiti dolu, sistem daha da kötü çöker. Kaynak havuzları alt sistemin kapasitesine göre boyutlanır, "büyük iyidir" diye değil.

---

## 5. Araçlar ve saha notları

Araç isimlerinden çok **hangi soruyu hangi araç cevaplar** önemli; ekosistem değişir ama kategoriler kalıcıdır.

**On-CPU profiler (örnekleyici / sampling profiler):** "CPU zamanı nerede yanıyor?" sorusunu cevaplar. Flame graph üretenler en okunabilirdir: geniş kutu = çok zaman. Sadece CPU-bound problemler için. Not: sampling profiler düşük maliyetlidir (üretimde bile çalıştırılabilir); instrumenting profiler daha detaylı ama yükü ağır ve davranışı çarpıtabilir (gözlemci etkisi).

**Off-CPU / wall-clock profiler:** "Thread nerede bekliyor?" — I/O, lock, uyku. Bekleme-bound problemlerin *tek* doğru aracı. Çoğu junior'ın varlığından habersiz olduğu ama latency avında hayat kurtaran şey. On-CPU profiler'ın kör noktasını görür.

**Distributed tracing (span'ler):** Bir isteğin servisler/aşamalar arası zaman dağılımı. "Uçtan uca 8 saniyenin nerede geçtiği" sorusunun cevabı. Mikroservis dünyasında ilk açacağın şey. N+1 sorguları burada apaçık görünür (aynı sorgu 200 kez yan yana).

**Heap profiler / memory analyzer:** İki farklı görünüm sunar, ikisini de öğren: (a) **allocation profili** — "byte olarak en çok nereden nesne doğuyor" (churn/GC teşhisi), (b) **heap snapshot / dominator ağacı** — "bu anda bellekte ne var ve onları kim tutuyor" (sızıntı teşhisi). Sızıntı avlarken iki snapshot al (T ve T+10dk), farkına bak: büyüyen nesne tipi kimdir, retain eden kimdir.

**GC/runtime metrikleri:** GC sıklığı, duraklama süresi, duraklama dağılımı. p99 latency spike'larını GC duraklamalarıyla ilişkilendirmek en güçlü teşhis hamlelerinden biridir — iki grafiği üst üste koy, dişler çakışıyorsa suçlu bellek davranışıdır.

**İşletim sistemi seviyesi araçlar:** CPU/bellek/IO/ağ doygunluğunu gösteren temel sistem monitörleri. İlk 60 saniyede bakılacak yer: hangi kaynak doygun? CPU mu, IO bekleme mi (iowait yüksek mi?), bellek baskısı (swap'a mı giriliyor?), ağ mı? Bu "üst düzey triage" yapılmadan profiler açmak, hastayı muayene etmeden ameliyata almaktır.

**Load / benchmark araçları:** Optimizasyonu *kanıtlamak* için. Değişiklikten önce ve sonra, üretim-benzeri yük altında ölç. "Hızlandı" demek yetmez; rakamla göster, yoksa placebo optimizasyon yaparsın.

### Saha notları (yıllarla damıtılmış)

- **Her optimizasyondan önce ve sonra ölç, aradaki farkı kaydet.** Ölçemediğin iyileştirme, iyileştirme değil temennidir. Regresyonu da ancak böyle yakalarsın.
- **Tek değişken kuralı.** Aynı anda üç şey değiştirip "hızlandı" dersen, hangisinin işe yaradığını (ve hangisinin gizli regresyon getirdiğini) asla bilemezsin. Bilimsel yöntem burada da geçerli.
- **%80'i getiren %20'yi bul, orada dur.** İlk büyük darboğazı çözünce genelde problem biter. Kalan mikro-kazançlar için harcayacağın gün, yeni bir feature'a ya da başka bir gerçek darboğaza gitmeli. Optimizasyon getiri azalan bir eğridir; nerede durulacağını bilmek beceridir.
- **Üretimde gözlemle, yerelde değil.** Gerçek veri dağılımı, gerçek eşzamanlılık, gerçek cache sıcaklığı yerelde yeniden üretilemez. Mümkünse düşük yüklü sampling profiler'ı üretimde çalıştır. Gerçek darboğaz çoğu zaman yerelde hiç görünmez.
- **Okunabilirlik bir performans özelliğidir.** Anlaşılmayan "optimize" kod, altı ay sonra birinin yanlış değiştirip performansı ve doğruluğu birlikte bozacağı koddur. Bir optimizasyonu kabul etmeden önce sor: kazanç, eklenen karmaşıklığa değer mi? Çoğu zaman değmez.
- **Regresyon sinsidir.** Bugün optimize ettiğin yol, altı ay sonra masum görünen bir değişiklikle eski haline döner. Kritik yolların performans testi CI'da olmalı — insan gözü fark etmeden yavaşlama birikir.
- **Doğruluğu bozan optimizasyon, optimizasyon değildir.** Hızlı ama yanlış cevap, yavaş doğru cevaptan kötüdür. Özellikle eşzamanlılık optimizasyonlarında (kilit kaldırma, lock-free hüneri) yarış koşulu (race) getirip veri bozarsan, kazandığın milisaniyenin bedelini haftalarca süren "arada bir yanlış sonuç" bug'ıyla ödersin.
- **En büyük optimizasyon mimaridedir.** Yanlış veri modeli, yanlış senkron/asenkron sınırı, yanlış servis parçalaması — bunları kod seviyesinde optimize edemezsin. Bazen doğru cevap "bu döngüyü hızlandır" değil, "bu işi hiç burada yapma, önceden hesaplayıp sakla" ya da "bu senkron çağrıyı bir olaya çevir"dir. Kod mikro-optimizasyonu, mimari yanlışın üstünü örtmez.

### Kapanış: yargının özü

CPU/bellek optimizasyonunda kıdem, "daha hızlı kod yazmayı bilmek" değildir. Kıdem şudur: **çalışan bir sisteme dokunmadan önce durmak; problemin gerçek olduğunu, ölçülebilir olduğunu ve doğru problem olduğunu kanıtlamak; en ucuz ve en güvenli çözümden başlamak; kazancı rakamla göstermek; ve getiri azaldığında durmayı bilmek.** Acemi hız arar; usta önce *nereye* bakacağını bilir, çünkü zamanın ve riskin nerede yattığını yıllarca yanılarak öğrenmiştir. Optimizasyonun asıl becerisi hızlandırmak değil, **neyi hızlandırmayacağına karar vermektir.**
