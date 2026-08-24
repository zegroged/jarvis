# Sistem Tasarımı Akıl Yürütme (Vaka Çalışması)

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Sistem tasarımı, "kod yazmadan önce zihinde ve tahtada çözdüğümüz" iştir. Amaç, bir özelliği çalıştırmak değil; o özelliği 10 kullanıcıda çalışan haliyle 10 milyon kullanıcıda çalışan hali arasındaki uçurumu görüp, hangi kararların hangi noktada seni sırtından bıçaklayacağını önceden fiyatlamaktır.

Sahada sistem tasarımı üç anda devreye girer:

1. **Sıfırdan bir servis kurarken** (greenfield). En tehlikeli an değildir aslında; çünkü henüz kimse yükte değil, geri dönmek ucuz.
2. **Var olan bir sistem çatırdarken** (p99 gecikme tırmanıyor, veritabanı CPU'su tavan yapıyor, bir servis diğerini boğuyor). En değerli akıl yürütmenin yapıldığı an burasıdır, çünkü artık soyut değil; elinde metrik var.
3. **Bir kararı geri almak pahalıya bindiğinde** (şema göçü, veri modeli değişimi, senkron API'yi asenkrona çevirmek). Burada tasarım, "yanlış yapıldığında haftalarca migration yazdıran" bir borç aracıdır.

Kilit gerçek şu: sistem tasarımı bir "doğru cevap bulma" işi değil, **bir takas uzayında bilinçli konum alma** işidir. Acemi "en iyi mimari ne?" diye sorar. Pro "hangi boyutta yanılmayı göze alabilirim?" diye sorar. Doğru cevap yoktur; savunulabilir cevap vardır.

Bu metinde tek bir somut vakayı baştan sona yürüteceğim: **bir e-ticaret sitesinde "sipariş ver" akışı ve onun etrafındaki stok/ödeme/bildirim zinciri.** Klasik görünür ama içinde neredeyse tüm dağıtık sistem tuzakları saklıdır.

---

## 2. Metodoloji ve karar ağacı (asıl değer): pro adım adım nasıl ilerler

### 2.1. Önce sayılandırmadan hiçbir mimari kelimesi etme

Acemi doğrudan "Kafka koyalım, mikroservis yapalım" der. Pro'nun ilk 15 dakikası tek bir tahtaya şu dört sayıyı yazmakla geçer:

- **QPS (saniyedeki istek):** Ortalama mı, tepe mi? E-ticarette Kara Cuma tepe/ortalama oranı rahatça 20x-50x olur. "Ortalama 200 QPS" cümlesi bir tuzaktır; asıl karar tepeye göre verilir.
- **Okuma/yazma oranı:** Ürün sayfası okuması yazmanın belki 1000 katıdır. Sipariş yazması ise nadir ama **kritik ve para taşıyan** yazmadır. Bu iki iş yükü aynı sistemde ama farklı garantilerle yaşamalıdır.
- **Veri boyutu ve büyüme:** Sipariş satırı yılda kaç GB büyür? 100 GB mı 100 TB mı? Bu, "tek Postgres yeter mi yoksa sharding konuşmalı mıyız" sorusunun kapısıdır.
- **Tutarlılık gereksinimi — ama alan alan:** Bütün sistemi "güçlü tutarlı" ya da "eventual" diye etiketlemek acemiliktir. Stok düşümü güçlü tutarlılık ister (aynı son ürünü iki kişiye satamazsın). Sipariş sonrası "kargonuz yola çıktı" bildirimi birkaç saniye gecikebilir, eventual olur.

Bu dördünü yazmadan mimari tartışması yapmak, hedefe bakmadan ateş etmektir.

### 2.2. "Belirtiden yöne" karar sezgileri

Sahada tanıdığın belirtiler seni belli bir yöne iter. Birkaç gerçek eşleme:

- **"Aynı kaydı iki kişi aynı anda güncelliyor ve biri diğerini eziyor"** görürsen → yön: **eşzamanlılık kontrolü** (optimistic locking / `SELECT ... FOR UPDATE` / atomik `UPDATE ... WHERE stok >= n`). Bunu mesajlaşmayla, kuyrukla çözmeye kalkma; sorun veri katmanında.
- **"Yazma tarafı iyi ama okuma p99'u dalgalı"** görürsen → yön: **okuma çoğaltması (read replica) + cache**, ama önce cache. Read replica replikasyon gecikmesi getirir; "kendi yazdığını okuyamama" bug'ı buradan doğar.
- **"İki işlem birbirini beklerken sistem yavaşlıyor, CPU boşta"** görürsen → yön: **kilitlenme (lock contention) ya da bağlantı havuzu tükenmesi**. CPU boşsa sorun hesaplama değil, bekleme. Profiler değil, önce bağlantı havuzu metriği ve `pg_stat_activity`.
- **"Bir bağımlı servis yavaşlayınca bizim servis de çöküyor"** görürsen → yön: **timeout + circuit breaker + bulkhead izolasyonu**. Zincirleme çökme (cascading failure) neredeyse her zaman "sonsuz/uzun timeout + sınırsız retry" ikilisinden doğar.
- **"Ölçek arttıkça tek bir tablo/tek bir servis darboğaz"** görürsen → yön: önce **dikey (daha büyük makine, index, sorgu düzeltme)**, sonra **yatay (sharding/partition)**. Acemi ilk günden shard'lar; pro sharding'i mümkün olduğunca geciktirir çünkü sharding geri dönüşü en pahalı karardır.

### 2.3. Senkron mu asenkron mı? — en çok yanlış verilen karar

Karar ağacının kalbi burası. Basit kural:

- **Kullanıcı sonucu şu an görmek zorunda mı ve sonuç kararı etkiliyor mu?** → Senkron. (Ödeme onayı: kullanıcı "başarılı" görmeden gidemez.)
- **İş, "olmuş bir gerçeğin sonucu" mu ve gecikmesi tolere edilebilir mi?** → Asenkron. (Sipariş oluştuktan sonra e-posta, fatura üretimi, öneri motoruna sinyal.)

Pro'nun burada yaptığı ince ayrım: **"para hattı"nı (stok + ödeme) senkron ve tutarlı tutar, "anlatı hattı"nı (bildirim, analitik, arama indeksleme) asenkron ve dayanıklı (durable queue) yapar.** Bu ikisini karıştırmak — örneğin ödeme onayını kuyruğa atıp kullanıcıya "başarılı" demek — klasik felakettir: kullanıcı parayı ödemiş görünür, kuyruk tıkanır, sipariş oluşmaz.

### 2.4. Takaslar tablosu (pro'nun kafasındaki)

| Karar | Kazanç | Bedel | Ne zaman öde |
|---|---|---|---|
| Cache ekle | Okuma p99 düşer, DB rahatlar | Bayat veri, invalidation karmaşası | Okuma ağır + hafif bayatlık kabul edilebilir |
| Read replica | Okuma ölçeği | Replikasyon gecikmesi, read-your-write bug'ı | Okuma DB'yi boğuyor ve gecikme tolere edilir |
| Kuyruk (async) | Dayanıklılık, decoupling, tepe yükü yayma | Sıralama, tam-bir-kez zorluğu, gözlemlenebilirlik zorlaşır | İş "gerçeğin sonucu" ve gecikme tolere edilir |
| Sharding | Yatay yazma ölçeği | Cross-shard sorgu/işlem cehennemi, ops yükü | Tek düğüm gerçekten yetmiyor (kanıtla) |
| Güçlü tutarlılık | Doğruluk | Gecikme, düşük erişilebilirlik (CAP) | Para/stok gibi yanlışı pahalı alanlar |

Bu tablo ezberlenmez; her satırın "bedel" sütunu bir gece nöbetinde öğrenilir.

---

## 3. Gerçek kod üzerinden yürüyüş: "sipariş ver" akışı

Somut senaryo: Kara Cuma. Elimizde son 5 adet "sınırlı üretim" ürün var. Aynı anda 300 kişi "Sepeti onayla"ya basıyor. Beklenen: en fazla 5 sipariş oluşur, 6. kişi "stok tükendi" görür, kimseden **fazla para çekilmez**, kimseye "aldınız" deyip sonra "aslında yok" denmez.

### 3.1. Zafiyetli (naif) sürüm

Aşağıdaki, gerçekten üretimde gördüğüm türden bir yaklaşım. Dil önemli değil; mantık her yerde aynı patlar. Pseudo-kod:

```
function siparisVer(kullanici, urunId, adet):
    urun = db.query("SELECT stok FROM urunler WHERE id = ?", urunId)   # (1) OKU
    if urun.stok < adet:
        return "stok yetersiz"

    odeme = odemeServisi.cek(kullanici.kart, urun.fiyat * adet)        # (2) DIŞ ÇAĞRI
    if not odeme.basarili:
        return "ödeme başarısız"

    db.execute("UPDATE urunler SET stok = stok - ? WHERE id = ?",       # (3) YAZ
               adet, urunId)
    db.execute("INSERT INTO siparisler (...) VALUES (...)")             # (4) YAZ
    bildirimServisi.gonder(kullanici, "Siparişiniz alındı")            # (5) DIŞ ÇAĞRI
    return "başarılı"
```

Bu kod demo'da kusursuz çalışır, code review'dan geçer, staging'de yeşil. Kara Cuma'da ise şu dört yerden patlar:

**Kusur A — Kontrol-sonra-hareket yarışı (TOCTOU):** (1)'de stoku okuyup (3)'te düşürmek arasında zaman var. 300 istek de aynı anda `stok = 5` okur, hepsi "yeterli" der, hepsi ödeme çeker, hepsi stok düşürür. Sonuç: `stok = -295` ve **5 yerine 300 sipariş, 295 kişiden haksız tahsilat.** Bu satır satır doğru, mantıken yanlış koddur.

**Kusur B — Dış çağrı ile DB yazımı arasında atomiklik yok:** Ödeme (2) başarılı oldu ama (3)/(4) sırasında uygulama sunucusu çöktü/deploy oldu. Para çekildi, sipariş yok. Kullanıcı parasını ödedi, hiçbir şey almadı. Bu, "dağıtık işlem" probleminin ta kendisi ve **tek bir DB transaction'ı bunu çözemez**, çünkü ödeme servisi başka bir sistem.

**Kusur C — İç içe/uzun transaction + dış çağrı:** Eğer (2)-(4) tek bir DB transaction'ına sarılırsa (acemi refleksi), transaction ödeme servisinin cevabını beklerken **DB satır kilidini tutar**. Ödeme servisi 8 saniye yavaşladığında, o satırın kilidi 8 saniye tutulur, arkadaki 299 istek kilitte bekler, bağlantı havuzu dolar, **tüm site yanıt vermez hale gelir.** Tek bir yavaş ürün, bütün siteyi çökertir.

**Kusur D — Bildirim başarısızlığı ana akışı kırıyor:** (5) bir dış çağrı. Bildirim servisi down'sa ve exception fırlatıyorsa, sipariş DB'ye yazıldıktan **sonra** patlarsa kullanıcı hata görür, belki tekrar dener, çift sipariş oluşur. Kritik olmayan bir iş, kritik yolu kırar.

### 3.2. Teşhis: her kusuru belirtisiyle eşle

- Kusur A'nın belirtisi: "stok negatife düştü", "sattığımızdan çok sipariş var". Loglarda görünmez, **veride** görünür. Teşhis aracı: veri tutarlılık sorgusu (`SELECT id FROM urunler WHERE stok < 0`).
- Kusur B'nin belirtisi: müşteri şikayeti "param gitti sipariş yok". Teşhis: ödeme sağlayıcı mutabakat raporu ile siparişler tablosunun karşılaştırılması (reconciliation). Bu bug'ı test ortamında yakalamak neredeyse imkânsızdır; **üretimde mutabakatla** yakalanır.
- Kusur C'nin belirtisi: dış servis yavaşlayınca kendi p99'unun patlaması, DB'de `lock_waits` artışı, bağlantı havuzu "pool exhausted" hatası. Teşhis: `pg_stat_activity` içinde `wait_event = Lock`.
- Kusur D'nin belirtisi: bildirim servisi olayları ile hata oranı korelasyonu. Teşhis: dağıtık trace'te span'ın nerede patladığı.

### 3.3. Düzeltilmiş sürüm — akıl yürütmeyle

Prensipler:

1. **Stok düşümünü atomik yap; oku-sonra-yaz yerine koşullu tek yazım.**
2. **Ödemeyi ana transaction'ın içine, DB kilidi tutarken sokma.** Önce stoku rezerve et, sonra öde, sonra kesinleştir.
3. **Kritik olmayan işleri (bildirim) ana akıştan çıkar, dayanıklı kuyruğa (outbox) at.**
4. **Tekrar denemeye dayanıklı ol: idempotency key.**

```
function siparisVer(kullanici, urunId, adet, idempotencyKey):
    # 0) Aynı isteğin tekrarı mı? (retry / çift tık koruması)
    varOlan = db.query("SELECT sonuc FROM siparis_istekleri WHERE key = ?", idempotencyKey)
    if varOlan: return varOlan.sonuc

    # 1) ATOMİK stok rezervasyonu: oku-kontrol-yaz'ı tek satırda birleştir
    etkilenen = db.execute(
        "UPDATE urunler SET stok = stok - ? WHERE id = ? AND stok >= ?",
        adet, urunId, adet)
    if etkilenen == 0:
        return kaydet(idempotencyKey, "stok yetersiz")   # yarış yok: DB karar verdi

    # Buraya geldiysek stok GARANTİLİ ayrıldı. Şimdi para hattı.
    try:
        # 2) Ödeme — idempotencyKey ödeme sağlayıcıya da geçir (çift çekim koruması)
        odeme = odemeServisi.cek(kullanici.kart, urun.fiyat * adet,
                                 idempotencyKey=idempotencyKey, timeout=3s)
        if not odeme.basarili:
            db.execute("UPDATE urunler SET stok = stok + ? WHERE id = ?", adet, urunId) # telafi
            return kaydet(idempotencyKey, "ödeme başarısız")
    except TimeoutError:
        # Belirsizlik hali: para çekildi mi bilmiyoruz -> stoku bekletmede tut,
        # kesin kararı mutabakat/webhook versin. Kör telafi yapma.
        return kaydet(idempotencyKey, "beklemede", geciciDurum=true)

    # 3) Sipariş + outbox'u AYNI DB transaction'ında yaz (atomik)
    with db.transaction():
        db.execute("INSERT INTO siparisler (...) VALUES (...)")
        db.execute("INSERT INTO outbox (tip, payload) VALUES ('siparis_olustu', ?)", ...)
    # bildirim, fatura, analitik: outbox'tan ayrı bir worker okuyup gönderir (async)

    return kaydet(idempotencyKey, "başarılı")
```

Bu sürümde ne değişti, neden:

- **Kusur A çözüldü:** `UPDATE ... WHERE stok >= adet` tek atomik işlem. DB satır kilidi yarışı bizim yerimize serileştirir. 300 istekten yalnızca 5'i `etkilenen == 1` alır. Uygulama katmanında hiçbir "if" bunu güvenli yapamazdı; **doğru katman veritabanı.**
- **Kusur C çözüldü:** Ödemenin dış çağrısı, uzun bir DB transaction'ının içinde değil. Stok rezervasyonu tek atomik statement (kilit milisaniye tutulur), ödeme onu tutmadan yapılır. Bir bağlantı havuzu boğulması yok.
- **Kusur B kısmen çözüldü, dürüstçe:** Ödeme timeout'unda "para çekildi mi?" sorusunun kesin cevabı **bizde yok**. Doğru davranış, uydurma telafi değil, durumu "beklemede" bırakıp ödeme sağlayıcının webhook'u/mutabakatının kesinleştirmesidir. Sipariş + outbox'un aynı transaction'da yazılması, "sipariş var ama bildirim tetiği yok" ihtimalini sıfırlar (transactional outbox deseni).
- **Kusur D çözüldü:** Bildirim artık ana yolda değil; outbox satırı yazıldı, ayrı worker gönderir, başarısız olursa **siparişi etkilemeden** yeniden dener.
- **Idempotency:** Kullanıcı iki kez tıklarsa, ağ isteği yeniden gönderilirse, ödeme retry olursa — hepsinde aynı `idempotencyKey` ile ikinci çağrı sonucu tekrarlar, çift sipariş/çift tahsilat olmaz.

Dikkat: Bu hâlâ "mükemmel" değil. `stok + adet` telafisi ile aynı anda başka bir satın alım arasında bile yarış düşünülmelidir (yine atomik UPDATE olduğu için güvenli). Ama önemli olan şu: **her satırı bir başarısızlık senaryosuna karşı savunabiliyoruz.** Sistem tasarımı budur.

---

## 4. Acemi vs pro: tuzaklar, gözden kaçanlar, "çalışır gibi görünüp patlayanlar"

**1. "Oku-sonra-yaz"ı güvenli sanmak.** Acemi `if stok yeterli: stok düş` yazar ve testte çalıştığı için doğru sanır. Tek kullanıcıda her zaman çalışır. Eşzamanlılık altında her zaman bozulur. Kural: **iki ayrı sorguyla yapılan kontrol-ve-değiştir, eşzamanlılık altında yanlıştır.** Ya atomik tek statement ya açık kilit ya versiyon (optimistic).

**2. Retry'ı düşünmeden eklemek.** "Hata olursa 3 kez dene" cümlesi, idempotent olmayan bir işlemde para çekme işlemini 3'e katlar. Daha kötüsü: bir servis yavaşladığında herkes retry yapar, hedef servis zaten boğuk, retry seli onu tamamen öldürür (retry storm). Pro retry'a **exponential backoff + jitter + idempotency** olmadan dokunmaz.

**3. Timeout'suz dış çağrı.** Varsayılan HTTP istemcisi çoğu dilde ya sonsuz ya çok uzun timeout'la gelir. Üretimde bir bağımlılık asılı kalınca senin thread'lerin/bağlantıların birer birer o çağrıda ölür, havuz dolar, sen de ölürsün. **Timeout'suz her dış çağrı bir saatli bombadır.** Gördüğüm en yaygın üretim çökmesi nedeni budur.

**4. "Sonra ölçekleriz" derken geri dönülmez karar vermek.** Ölçeklemeyi ertelemek genelde doğrudur. Ama **veri modeli** ve **ID stratejisi** ertelenemez. Auto-increment integer ID seçtin, sonra sharding gerekti — artık ID çakışmaları ve migration cehennemi. Pro, "bunu değiştirmek 6 ay sürer mi?" diye sorup **sadece o kararları** öne çeker; gerisini erteler.

**5. Tutarlılığı "hep ya da hiç" sanmak.** "Mikroservis yaptık, artık her şey eventual consistent" cümlesi bir facia habercisidir. Stok ve bakiye eventual olamaz. Pro alan alan karar verir; sistemin %90'ı eventual olabilir ama %10'luk para hattı güçlü tutarlı kalır.

**6. Cache invalidation'ı sonradan düşünmek.** Cache eklemek okuma p99'unu anında düşürür — demo harika. Sonra "fiyat güncellendi ama kullanıcı eski fiyatı görüyor ve o fiyattan alıyor" gelir. Cache eklerken **aynı anda invalidation stratejisini** yazmayan biri, borcu faiziyle öder.

**7. "Happy path" testine güvenmek.** Kod happy path'te çalışıyor diye bitmiş sanmak. Pro'nun kafası başarısızlıkla meşguldür: "Bu satırdan sonra süreç ölürse ne olur? Bu çağrı iki kez gelirse? Bu servis 5 saniye yavaşlarsa? Ağ bölünürse?" Sistem tasarımının %70'i mutlu yolu değil, **kısmi başarısızlıkları** tasarlamaktır.

**8. Kuyruğu sihirli çözüm sanmak.** "Kafka koyduk, artık ölçekliyiz." Kuyruk decoupling ve tepe yayma verir ama **yeni sorunlar** getirir: mesaj sırası, tekrarlı teslim (at-least-once), tüketici geride kalması (consumer lag), zehirli mesaj (poison message). Kuyruk sorunu taşır, yok etmez. Async yapılan iş artık gözlemlemesi zor bir iştir.

**9. Gözlemlenebilirliği sona bırakmak.** Sistem büyüdükçe "neden yavaş?" sorusuna cevap veremeyen ekip kördür. Pro, log/metric/trace'i özelliğin parçası olarak yazar; sonradan eklenen gözlemlenebilirlik hep eksiktir.

**10. N+1 sorgusunu mimariden önce dert etmemek.** Bazen sorun mimaride değil, tek bir döngü içindeki sorgudadır. 200 ürünlü sepet için 200 ayrı DB sorgusu. Sharding tartışmadan önce, **kendi kodundaki N+1'i** ara.

---

## 5. Araçlar ve saha notları: hangi araç ne için

**Yük hesabı ve kapasite:** Tahta ve zarf-arkası hesap. Ciddi bir aracın adı yok; disiplinin adı var: her mimari kararın önüne QPS × istek boyutu × büyüme çarpımını koymak. "Bu tablo günde X satır büyür, yılda Y GB eder, index'i belleğe sığar mı?" hesabı çoğu felaketi tahtada önler.

**Veritabanı teşhisi:**
- PostgreSQL'de `EXPLAIN (ANALYZE, BUFFERS)` — sorgunun gerçekten ne yaptığını, index kullanıp kullanmadığını, kaç satır taradığını gösterir. Yavaş sorgu avında ilk durak.
- `pg_stat_activity` — o an ne bekliyor? `wait_event` kilit mi, I/O mu? Kilit contention'ını buradan görürsün.
- `pg_stat_statements` — hangi sorgu toplam zamanın çoğunu yiyor? "En yavaş tek sorgu" değil, "toplamda en pahalı" sorguyu bulmak için. Genelde suçlu, tek başına hızlı ama milyon kez çağrılan sorgudur.
- Yavaş sorgu logu (`log_min_duration_statement`) — eşiği aşan sorguları biriktir, sabah bak.

**Yük testi:** k6, Gatling, Locust, wrk gibi araçlar. Saha notu: **tepe yükünü ve tepe yükün gerçek dağılımını** simüle et, düz ortalama değil. Kara Cuma "300 istek eşzamanlı, aynı ürüne" senaryosunu düz 200 QPS testi asla yakalamaz. Yarış koşullarını yük testinde **kasıtlı olarak** aynı kaynağa yığarak tetikle.

**Profiler:** CPU sınırlı mı bekleme sınırlı mı ayrımı için. CPU %100 ise CPU profiler (flame graph) doğru katman kızgın kodu gösterir. Ama CPU boştayken sistem yavaşsa profiler yanıltır; oradaki sorun **bekleme** (kilit, I/O, dış çağrı) — o zaman trace ve DB metriğine geç.

**Dağıtık trace (OpenTelemetry, Jaeger, Zipkin):** Bir isteğin servisler arası yolculuğunu span span gösterir. "İstek 2 saniye sürdü, 1.8 saniyesi ödeme servisinde" tespiti bununla saniyeler alır; logla saatler. Async akışlarda trace context'i kuyruğun içinden geçirmezsen (propagation) trace kopar — sık yapılan hata.

**Metrikler (Prometheus + Grafana benzeri):** Dört altın sinyal: gecikme (latency, özellikle p99/p999, ortalama yalan söyler), trafik, hata oranı, doygunluk (saturation — CPU, bellek, bağlantı havuzu doluluğu). **Bağlantı havuzu doluluğunu izlemeyen ekip, çöküşü ancak site düşünce öğrenir.** p50 iyiyken p99 berbat olabilir; para kaybettiren p99'dur.

**Circuit breaker / bulkhead:** Resilience kütüphaneleri (ör. JVM dünyasında Resilience4j) ya da servis mesh (Istio/Envoy) seviyesinde. Amaç: yavaş bağımlılığı hızlı reddederek kendi kaynaklarını korumak. Saha kuralı: **her dış çağrının bir timeout'u, bir de "bağımlılık ölürse ne yaparım" cevabı olmalı** (varsayılan değer döndür, bozulmuş çalış — graceful degradation).

**Idempotency ve mutabakat (reconciliation):** Kod aracı değil, disiplin. Para taşıyan her akışta, günün sonunda "bizim kayıtlarımız ile ödeme sağlayıcının kayıtları tutuyor mu?" işini yapan bir mutabakat işi (batch job) yaz. Kod ne kadar iyi olsa da dağıtık sistemde tutarsızlık sızar; mutabakat onu yakalar. Bunu yazmayan ekip, tutarsızlığı müşteri şikayetiyle öğrenir.

**Feature flag ve kademeli açılım:** Riskli tasarım değişikliğini %1 trafikle aç, metrikleri izle, sonra %10, %50. "Deploy ettik, umarız tutar" yerine "deploy ettik, %1'de p99 ve hata oranı sabit, açmaya devam." Geri alma (rollback) her zaman ileriye düzeltmeden hızlı olmalı.

**Son saha notu — en değerli alışkanlık:** Bir tasarım kararı verirken kendine tek soru sor: **"Bu yanlışsa, ne zaman ve nasıl öğrenirim, ve geri almak ne kadar sürer?"** Ucuz ve erken öğrenilen, hızlı geri alınan kararlarda cesur ol. Pahalı, geç öğrenilen, geri alması aylar süren kararlarda (veri modeli, ID stratejisi, senkron/asenkron sınırı, tutarlılık garantileri) yavaşla, yaz, tartış, ikinci göz al. Kıdemli mühendisi acemiden ayıran şey daha çok mimari deseni bilmek değil; **hangi kararın geri dönülmez olduğunu koklayabilmek** ve iğneyi orada yavaşlatabilmektir.
