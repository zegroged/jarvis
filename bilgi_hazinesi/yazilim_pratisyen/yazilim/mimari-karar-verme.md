# Mimari Karar Verme (Takaslarla)

## 1. Problem / bağlam: bu iş neyi çözer, ne zaman devreye girer

Mimari karar, "bugünkü bir satır kodu değil, önümüzdeki iki yılın maliyet eğrisini" seçtiğin karardır. Kodun içindeki bir `if` bloğunu yarın değiştirebilirsin; ama "veritabanını PostgreSQL mi yoksa üç ayrı mikroservis içinde üç ayrı veri deposu mu tutalım", "senkron REST mi yoksa event-driven mi", "monolit mi mikroservis mi" gibi kararları geri almak haftalar-aylar sürer ve genellikle ekibin moralini de yer. Mimari kararın tanımı budur zaten: **tersine çevirme maliyeti yüksek olan kararlar.** Martin Fowler'ın klasik cümlesi işi özetler: mimari, "değiştirmesi pahalı olan şeyler"dir.

Bu iş ne zaman devreye girer? Genellikle üç anda:

1. **Yeşil saha (greenfield):** Yeni proje, sıfırdan seçim. En tehlikeli an, çünkü belirsizlik en yüksek, geri bildirim yok, herkes en çok burada aşırı-mühendislik yapar.
2. **Ölçek duvarı:** Çalışan sistem büyüdü, eski karar artık sırıtıyor. Tek veritabanı yazma yükünü kaldıramıyor, deploy'lar birbirini kilitliyor, tek bir takım 40 kişilik ekibin darboğazı olmuş.
3. **Değişim baskısı:** İş modeli değişti (B2C'den B2B'ye geçildi, yeni ülkeye açılındı, regülasyon geldi — KVKK/GDPR veri yerelleştirme istiyor) ve mevcut mimari bu yeni gereksinimi doğal karşılamıyor.

Kilit içgörü: **mimari karar teknik bir karar değil, ekonomik ve organizasyonel bir karardır.** "Hangisi daha zarif" sorusu amatörün sorusudur. Pro'nun sorusu şudur: "Bu kararın bakım maliyeti, öğrenme maliyeti, işe alım maliyeti, hata durumunda kurtarma maliyeti nedir; ve bunları hangi belirsizliği satın almak için ödüyorum?"

## 2. Metodoloji ve karar ağacı (asıl değer)

Pro'nun kafasındaki akış aşağı yukarı şudur. Sırayı önemseyin — çoğu kötü karar, adımların atlanmasından değil, **yanlış sıradan** doğar.

### Adım 0: Kararı erteleyebilir miyim? (En değerli soru)

Kıdemli mühendisin ilk refleksi karar vermek değil, **kararı en son sorumlu ana (last responsible moment) ertelemektir.** Neden? Çünkü bilgi zamanla artar. Bugün elinde en az veri varken verdiğin karar, altı ay sonra elinde gerçek trafik/kullanım verisi varken vereceğin karardan neredeyse her zaman daha kötüdür.

Ertelemenin pratiği: kararı **tersine çevrilebilir** hale getirecek bir soyutlama koy, gerçek kararı sonraya bırak. Örnek: "Kafka mı RabbitMQ mı?" sorusuna bugün cevap vermek yerine, kodun sadece kendi `MessagePublisher` arayüzünü görmesini sağla, altına şimdilik en basit olanı (hatta bir Postgres tablosu + polling) koy. Trafik gerçekten gelince, arayüzün arkasını değiştir.

Ama dikkat — bu bir bahane değil. Bazı kararlar ertelenemez çünkü tüm veri modelini şekillendirir (örn. multi-tenancy stratejisi: tek DB'de `tenant_id` kolonu mu, tenant başına şema mı, tenant başına DB mi?). Bunları erteleyemezsin çünkü sonradan migrasyonu cehennemdir. Ayrım şudur: **veri modeline ve tenant sınırına dokunan kararlar erken; teknoloji/altyapı seçimleri geç.**

### Adım 1: Gerçek kısıtları ve kalite gereksinimlerini yaz (NFR'ler)

Fonksiyonel gereksinim ("kullanıcı sipariş verebilmeli") mimariyi belirlemez. Mimariyi **fonksiyonel olmayan gereksinimler (NFR)** belirler:

- **Ölçek:** Kaç eşzamanlı kullanıcı? Saniyede kaç istek? Bugün mü, iki yıl sonra mı? (Rakam yoksa, karar da yoktur — "ölçeklenebilir olsun" cümlesi bilgi taşımaz.)
- **Tutarlılık:** Paranın/stoğun anlık doğru olması şart mı (güçlü tutarlılık), yoksa birkaç saniye gecikme kabul mü (nihai tutarlılık)? Bu tek soru, senkron/asenkron seçimini çoğu zaman tek başına belirler.
- **Gecikme (latency):** p50 değil, p99. Kullanıcı 200ms mi bekleyebilir, 2s mi?
- **Kullanılabilirlik:** Üç dokuz mu (%99.9, yılda ~8.7 saat kesinti), dört dokuz mu? Her ek dokuz maliyeti katlar.
- **Ekip:** Kaç kişi, hangi tecrübe? 4 kişilik ekibe 12 mikroservis vermek intihardır.

Pro bu adımda **sayı ister.** "Çok kullanıcı olacak" der müşteri; pro "günde kaç, pikte saniyede kaç?" diye sorar. Çoğu zaman cevap "günde 5.000" çıkar — ki bu tek bir mütevazı sunucunun gülerek kaldıracağı bir yüktür ve tüm "mikroservis" tartışmasını gereksiz kılar.

### Adım 2: Baskın kalite özelliğini (dominant quality) belirle

Her mimari bir şeyi optimize eder ve karşılığında başka bir şeyi feda eder. Aynı anda hem en yüksek tutarlılığı, hem en düşük gecikmeyi, hem en yüksek kullanılabilirliği alamazsın — bu fiziksel değil, matematiksel bir sınır (CAP teoreminin pratikteki yansıması: ağ bölünmesi olduğunda tutarlılık ile kullanılabilirlik arasında seçim yapmak zorundasın).

Pro şunu sorar: **"Bu sistemde tek bir şeyi mükemmel yapabilseydim, hangisi olurdu?"** Bir bankada cevap tutarlılıktır (yanlış bakiye kabul edilemez). Bir sosyal medya beğeni sayacında cevap kullanılabilirlik ve gecikmedir (beğeni sayısı 3 saniye geç güncellense kimse ölmez). Bu tek cevap, aşağıdaki tüm dalları belirler.

### Adım 3: Karar ağacı — "şu belirtiyi görünce şu yöne giderim"

Sahada kafamda çalışan pratik ağaç:

- **Belirti: Ekip küçük (< 8), ürün-pazar uyumu daha yok, gereksinimler her hafta değişiyor.**
  → **Modolit.** İstisnasız. Modüler bir monolit (net modül sınırları, ama tek deploy). Mikroservisin dağıtık sistem vergisini (ağ hataları, dağıtık transaction, gözlemlenebilirlik karmaşası) ödeyecek ne insanın ne de zamanın var. "Sonra bölmek zor olur" korkusu genç mühendisin korkusudur; iyi modüllenmiş bir monoliti bölmek, kötü tasarlanmış mikroservisleri birleştirmekten çok daha kolaydır.

- **Belirti: Sistemin farklı parçaları çok farklı ölçek/kaynak profiline sahip (biri CPU-yoğun video işleme, diğeri hafif CRUD).**
  → Sadece o parçayı ayır. "Mikroservis" diye topyekûn bölme; **sadece bağımsız ölçeklenmesi gereken parçayı** ayrı servise çıkar. Geri kalan monolit kalsın.

- **Belirti: İki takım sürekli aynı kod tabanında birbirini blokluyor, deploy'lar kuyruğa giriyor.**
  → Servis sınırını **organizasyon sınırına** göre çiz (Conway Yasası: sistemin yapısı, onu üreten ekiplerin iletişim yapısını taklit eder). Burada bölme kararı teknik değil, insani bir darboğaza çözümdür — ve bu meşru bir sebeptir.

- **Belirti: "A olayı olunca B, C, D tetiklenmeli" ve bu tetiklenenler zamanla artıyor.**
  → Event-driven mimari düşün. Ama takas nettir: senkron çağrının hata ayıklaması basittir (stack trace bir uçtan diğerine gider), event-driven'da bir olayın nereye gittiğini takip etmek gözlemlenebilirlik altyapısı ister. Correlation ID'siz event mimarisi, karanlıkta kör dövüşüdür.

- **Belirti: Güçlü tutarlılık ve transaction şart (para, stok, rezervasyon).**
  → Tek ilişkisel veritabanı, tek transaction sınırı içinde tut. Bunu mikroservislere bölersen "distributed transaction" veya "saga" desenine mahkûm olursun — ki bu, çözdüğünden çok problem yaratan bir karmaşıklıktır ve ancak gerçekten mecbur kalınca girilir.

- **Belirti: Okuma yükü yazma yükünden 100 kat fazla.**
  → Read replica, cache katmanı (ama cache invalidation'ın bilgisayar bilimlerinin en zor iki probleminden biri olduğunu bilerek). CQRS'i düşünebilirsin ama acele etme.

Genel prensip: **her ek dağıtık bileşen, sistemin "hareketli parça" sayısını artırır ve arıza yüzeyini genişletir.** Pro varsayılan olarak en az hareketli parçalı çözümü seçer ve ancak somut bir belirti onu zorlayınca karmaşıklık ekler. Bu yüzden iyi mimarinin sırrı çoğu zaman "ne eklediğin" değil, **"neyi eklemediğin"dir.**

### Adım 4: Kararı yaz (ADR)

Karar verildiyse ama yazılmadıysa, verilmemiştir. Altı ay sonra kimse "neden Kafka seçmiştik?" sorusunu hatırlamaz ve birileri "bu saçmalık, değiştirelim" der — halbuki o karar bilinçli bir takastı. **ADR (Architecture Decision Record)** bunun için var: kısa bir markdown dosyası — bağlam, verilen karar, değerlendirilen alternatifler, ve **sonuçlar/takaslar.** Reddedilen alternatifleri ve *neden* reddedildiklerini yazmak, kararın kendisinden daha değerlidir; çünkü gelecekteki tartışmaların yarısını baştan keser.

## 3. Gerçek senaryo üzerinden yürüyüş: "Sipariş sistemi"

Somut bir örnek üzerinden yürüyelim — dilden bağımsız ama gerçek. Bir e-ticaret ekibi, "modern olmak için" siparişi şöyle kurmuş (yaygın, kitaptan fırlamış gibi görünen ama üretimde patlayan tasarım):

**Zafiyetli tasarım — senkron mikroservis zinciri:**

Kullanıcı "Sipariş Ver" butonuna basınca, `OrderService` sırayla şunları senkron HTTP çağrısıyla yapıyor:

```
OrderService.createOrder():
    stok = InventoryService.reserve(items)      # HTTP çağrı 1
    odeme = PaymentService.charge(card, total)   # HTTP çağrı 2
    kargo = ShippingService.schedule(address)    # HTTP çağrı 3
    bildirim = EmailService.send(user)           # HTTP çağrı 4
    return OK
```

Demo'da harika çalışır. Üretimde şöyle patlar:

1. **Ölü kilit / kısmi hata:** 2. adım (ödeme) başarılı, 3. adım (kargo servisi) o an çökmüş. Şimdi paran çekildi ama siparişin yok. Sistem tutarsız durumda. Rollback? Ödemeyi geri almak için `PaymentService.refund` çağırman lazım ama ya o çağrı da başarısız olursa? Elle müdahale, öfkeli müşteri, muhasebe kâbusu.

2. **Gecikmelerin toplanması:** Her servis p99'da 300ms sürüyorsa, zincir 4×300 = 1.2s. Ama daha kötüsü: **kullanılabilirlikler çarpılır.** Her servis %99.9 çalışıyorsa, dördünün senkron zinciri 0.999⁴ ≈ %99.6 eder — yani kullanılabilirliğin her servis eklendikçe düşer. Bağımlılık zinciri uzadıkça sistem daha kırılgan olur.

3. **Tekrar deneme fırtınası (retry storm):** `EmailService` yavaşladı, `OrderService` timeout'a düşüp yeniden deniyor, yeniden denemeler `EmailService`'i daha da boğuyor, tüm sistem çöküyor. Bir servisin yavaşlaması, retry'lar üzerinden tüm sisteme yayılıyor (cascading failure).

**Teşhis:** Buradaki kök hata, **kritik yol (siparişin oluşması + para) ile kritik olmayan yan etkileri (email, hatta kargo planlaması) aynı senkron transaction'a koymak.** Kullanıcının "Sipariş Ver" dediği anda gerçekten *anında* olması gereken tek şey: para güvence altına alınsın ve sipariş kaydedilsin. Email'in 5 saniye sonra gitmesi, hatta kargo etiketinin 30 saniye sonra oluşması kabul edilebilir.

**Düzeltilmiş tasarım — kritik yolu daralt, gerisini olaya çevir:**

```
OrderService.createOrder():
    # Tek transaction, tek veritabanı, güçlü tutarlılık:
    with db.transaction():
        stok_ok = reserve_inventory(items)   # aynı DB, satır kilidi
        if not stok_ok: return OUT_OF_STOCK
        order = save_order(status="PENDING_PAYMENT")

    # Ödeme: idempotency key ile, senkron ama tek dış bağımlılık
    result = PaymentService.charge(card, total, idempotency_key=order.id)
    if result.failed:
        release_inventory(items)             # telafi
        return PAYMENT_FAILED

    order.status = "CONFIRMED"
    db.save(order)

    # Kritik olmayanlar: olay yayınla, dön. Bunlar arka planda tüketilir.
    publish_event("OrderConfirmed", order.id)
    return OK   # kullanıcı burada cevabını aldı — hızlı
```

`ShippingService` ve `EmailService` artık `OrderConfirmed` olayına **abone.** Kargo servisi çökse bile olay kuyrukta bekler, servis ayağa kalkınca tüketir; sipariş kaybolmaz. Kullanıcı hızlı cevap alır. Kritik yol iki dış çağrıya (stok — ki aslında aynı DB, ve ödeme) indi.

Dikkat edilecek üç saha detayı:

- **Idempotency key:** Ödeme çağrısına `order.id`'yi idempotency anahtarı olarak veriyoruz. Ağ timeout olup çağrıyı tekrarlarsak, ödeme sağlayıcı aynı anahtarı görüp **ikinci kez para çekmez.** Bu tek satır, "müşteriden iki kez para çekildi" felaketini önler. Dağıtık sistemlerde altın kural: **her yan etkili işlem idempotent olmalı**, çünkü "tam bir kez teslim" (exactly-once) ağ üzerinde pratikte yoktur; elimizde "en az bir kez" vardır, onu idempotency ile "etkisi bir kez"e çeviririz.

- **Telafi (compensation), rollback değil:** Ödeme başarısızsa stoğu `release_inventory` ile bırakıyoruz. Dağıtık dünyada gerçek transaction rollback yoktur; ileri giden telafi işlemleri vardır. Bu Saga desenidir ve bilinçli seçilmelidir, refleksle değil.

- **Nihai tutarlılık kabulü:** Kullanıcı "Sipariş onaylandı" gördü ama kargo etiketi henüz oluşmadı. Bu kabul edilebilir mi? İş biriminden **açık onay** almalısın. Mimari karar burada teknik değil, iş kararıdır: "email'in 10 saniye gecikmesi kabul, ama sipariş numarasının anında görünmesi şart." Bunu ürün sahibiyle netleştirmeden kodlamak, amatörün en sık hatasıdır.

## 4. Acemi vs pro: yaygın hatalar ve tuzaklar

**Amatör "en yeni ve en zarif"i seçer; pro "en sıkıcı ve kanıtlanmış"ı seçer.** "Boring technology" felsefesi: her ekibin sınırlı sayıda "yenilik jetonu" vardır. Bu jetonları asıl işini farklılaştıran yere harca (senin ürününü özel yapan algoritma), altyapıya değil. Veritabanın Postgres olsun, kuyruk ihtiyacın için başta Postgres tablosu bile yeter. Jetonu "en trend NoSQL"e harcarsan, altı ay sonra kimsenin çözemediği bir tutarlılık hatasıyla uğraşırsın.

**Amatör bugünü değil, hayali yarını çözer (aşırı mühendislik).** "Ya milyon kullanıcı gelirse?" 5.000 kullanıcın varken 12 mikroservisli, Kubernetes'li, event-sourcing'li mimari kurmak — çözmediğin bir problem için, çözebileceğin problemleri feda etmektir. Netflix'in mimarisini kopyalamak istersin ama senin Netflix'in problemi yok; Netflix o mimariye **problemleri zorladığı için** vardı, önden tasarlayarak değil. Gerçek kural: **YAGNI (You Ain't Gonna Need It)** — ihtiyaç kanıtlanana kadar ekleme.

**Amatör dağıtık sistemin gizli vergilerini görmez.** "Mikroservise bölelim" der, çünkü bloglar öyle diyor. Görmediği vergiler: ağ artık güvenilmez (her çağrı başarısız olabilir), gözlemlenebilirlik artık zorunlu (tek log dosyası yok, dağıtık izleme lazım), yerel fonksiyon çağrısı `foo()` iken artık serialization + ağ + deserialization var, veri artık tek yerde değil (her rapor bir "join" kâbusu), ve en acısı: **basit bir "iki tabloyu birleştir" sorgusu artık iki servis arası API danışına dönüşür.** Dağıtık monolit — mikroservise böldün ama hepsi birbirine senkron bağımlı — her iki dünyanın en kötüsüdür: monolitin bağımlılığı + mikroservisin operasyonel acısı.

**Amatör "geri alınamaz" ile "geri alınabilir" kararı ayırt etmez.** Jeff Bezos'un "tek yönlü / çift yönlü kapı" ayrımı: çift yönlü kapıdan (geri alınabilir karar — hangi loglama kütüphanesi) geç ve gerekirse dön; hızlı karar ver. Tek yönlü kapıda (veri modeli, tenant sınırı, API sözleşmesi — dışa açtıysan artık kırılamaz) yavaşla, tartış, prototiple. Amatör her kararı aynı ağırlıkta ele alır: ya önemsiz bir kararı haftalarca tartışır, ya da veri modeli gibi kritik kararı beş dakikada "sonra düzeltiriz" diyerek geçer.

**Amatör Conway Yasası'nı görmez.** İki ekip aynı servisi paylaşınca sürekli çakışırlar; kod sınırı ekip sınırıyla uyuşmadığı için. Ya da üç ekip var, biri illa dört servis üretir çünkü organizasyon iletişimi öyle akıyor. Pro mimariyi çizerken **organigrama bakar.** "Ters Conway manevrası" — istediğin mimariyi almak için önce ekip yapısını ona göre düzenle.

**"İşe yarar gibi görünüp üretimde patlayan" klasikler:**

- **Cache invalidation'ı hafife almak:** Cache eklemek performansı demoda uçurur; üretimde "kullanıcı eski fiyatı görüyor" hatası ay sonu faturayı patlatır. Cache eklemek kolaydır; *ne zaman geçersiz kılınacağını* doğru yapmak zordur.
- **N+1 sorgusu:** ORM ile liste dönerken her eleman için ayrı sorgu atılır. 10 kayıtlı test verisinde görünmez, 10.000 kayıtlı üretimde veritabanını dize getirir. Profil almadan fark edilmez.
- **Senkron çağrı zinciriyle kullanılabilirliği çarpmak:** yukarıda anlattık.
- **"Sonra ölçekleriz" diye state'i sunucuya koymak:** Oturumu bellekte tuttun, tek sunucuda çalışıyor; ikinci sunucu ekleyince kullanıcılar rastgele logout oluyor. Yatay ölçeklemeyi baştan düşünmemenin bedeli.

## 5. Araçlar ve saha notları

Karar vermek yarısı; kararın doğruluğunu **ölçmek** diğer yarısı. Sahada işe yarayanlar:

- **ADR araçları:** `adr-tools` (basit CLI) ya da sadece repo içinde `docs/adr/0001-...md` dosyaları. Aracın önemi yok; **alışkanlığın** önemi var. Her tersine çevrilmesi zor karardan sonra 15 dakika ayır, yaz. Bu, ekibin kurumsal hafızasıdır.

- **Yük testi — karar öncesi:** "Tek sunucu yeter mi?" tartışmasını konuşarak değil, ölçerek bitir. `k6`, `Gatling`, `wrk`, `Locust` gibi araçlarla gerçekçi yük üret, p99 gecikmeye bak. Çoğu "ölçeklenmez" korkusu, gerçek sayılarla buharlaşır. **Tahmin etme, ölç.**

- **Profiler — darboğazı bulmak:** "Yavaş" hissiyle mimari değiştirme; önce profille. CPU/bellek profiler (dile göre: `pprof`, `async-profiler`, `py-spy`, Chrome DevTools) sana darboğazın gerçekte nerede olduğunu söyler. Sahada tekrar tekrar gördüğüm gerçek: geliştirici mimariyi suçlar, profiler tek bir kötü sorguyu ya da eksik index'i gösterir. Mimariyi değiştirmeden önce, ucuz düzeltmeyi kontrol et.

- **Veritabanı `EXPLAIN ANALYZE`:** Mimari kararların yarısı aslında veritabanı kararıdır. Sorgunun planına bakmadan "DB ölçeklenmiyor, sharding lazım" demek — çoğu zaman eksik bir index'i milyon dolarlık bir mimari projeye çevirmektir. Önce `EXPLAIN`.

- **Gözlemlenebilirlik (observability) — dağıtık gidiyorsan zorunlu, opsiyonel değil:** Dağıtık izleme (distributed tracing — OpenTelemetry standart, Jaeger/Tempo backend), yapılandırılmış loglama ve **correlation ID.** Kural: mikroservise geçme kararı verdiğin an, gözlemlenebilirlik altyapısını *aynı sprint'te* kur. Sonraya bırakırsan, ilk üretim olayında körsün ve o gece hiç bitmez. Tek başına bir metrik: bir isteğin uçtan uca yolunu 30 saniyede takip edemiyorsan, dağıtık sisteme henüz hazır değilsin.

- **Circuit breaker ve timeout kütüphaneleri:** Senkron dış çağrı yapıyorsan, timeout olmadan çağrı yapmak = sistemin bir servisin yavaşlamasıyla kilitlenmesine davetiye. Devre kesici (bir bağımlılık sürekli hata verince çağrıları bir süre kesip hızlı-başarısız olma) deseni, cascading failure'ı durdurur. Kütüphane dilden dile değişir ama desen evrenseldir.

- **Fitness fonksiyonları:** Mimari kararın zamanla erozyona uğramasını engellemek için, mimari kuralları otomatik teste bağla (örn. "sunum katmanı doğrudan veritabanı katmanını import edemez" — `ArchUnit` benzeri araçlarla CI'da kontrol). Karar sadece belgede kalırsa, altı ay içinde ihlal edilir; teste bağlarsan yaşar.

**Kapanış saha notu:** En iyi mimari kararı, en akıllı kararı değil, **ekibinin taşıyabileceği en basit kararı** verendir. Bir mimari, üzerinde çalışan insanlardan daha akıllıysa, o mimari başarısızdır — çünkü onu kimse doğru işletemez. Kararı verirken kendine sürekli sor: "Bunu gece 3'te, nöbetçi mühendis (belki de en tecrübesizi) bir üretim olayında anlayıp müdahale edebilir mi?" Cevap "hayır"sa, ne kadar zarif olursa olsun yanlış karardır. Basitlik bir estetik tercih değil, operasyonel bir hayatta kalma stratejisidir.
