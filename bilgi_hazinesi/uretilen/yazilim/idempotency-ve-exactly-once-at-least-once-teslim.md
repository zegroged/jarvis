# Idempotency ve Exactly-Once / At-Least-Once Teslimat Semantikleri

## Giriş ve Neden Önemli

Dağıtık sistemlerde iki bileşen bir ağ üzerinden konuştuğu anda, "mesaj gitti mi, işlendi mi?" sorusuna kesin ve anlık bir cevap vermek fiziksel olarak imkânsız hâle gelir. Bir servis diğerine bir istek gönderir, ama cevap gelmezse bunun sebebi isteğin hiç varmaması mı, yoksa isteğin varıp işlendikten sonra cevabın yolda kaybolması mı olduğunu ayırt edemez. İşte tüm teslimat semantikleri (delivery semantics) tartışması bu tek belirsizlikten doğar.

Bu belirsizliği yönetmenin iki temel yolu vardır: ya mesajı tekrar göndeririz (ve muhtemelen mükerrer işlenme riskini alırız), ya da göndermeyiz (ve muhtemelen kaybolma riskini alırız). Bu tercih doğrudan **at-least-once** ve **at-most-once** semantiklerini tanımlar. **Idempotency** ise bu iki dünyayı birleştiren pratik köprüdür: mükerrer işlemeyi zararsız hâle getirerek, at-least-once teslimatı sanki exactly-once gibi davranan bir sisteme dönüştürmenin yoludur.

Bu makale mekanizmaları derinlemesine anlatmayı, doğru kullanım desenlerini ve yaygın tuzakları göstermeyi amaçlar. Konu bir güvenlik konusu değil güvenilirlik (reliability) konusudur; ama aynı prensipler ödeme sistemlerinde tekrarlı ücretlendirmeyi önlemek gibi kritik doğruluk gereksinimlerini de kapsar.

## Temel Tanımlar

### At-Most-Once (En Fazla Bir Kez)

Mesaj sıfır veya bir kez teslim edilir; asla mükerrer teslim edilmez, ama kaybolabilir. Gönderici mesajı yollar ve sonucu takip etmez, yeniden denemez (retry yapmaz). Uygulaması en basit ve en hızlı olan semantiktir çünkü hiçbir onay (acknowledgement) ve durum takibi gerektirmez.

Örnek kullanım alanı: yüksek frekanslı metrik/telemetri toplama. Saniyede binlerce CPU kullanım örneği gönderiyorsanız, birkaç örneğin kaybolması istatistiksel resmi bozmaz; ama her örneği garantilemek için harcanacak overhead sistemi yavaşlatır. UDP tabanlı log/metrik protokolleri (örneğin statsd'nin klasik UDP modu) bu semantiğe örnektir.

### At-Least-Once (En Az Bir Kez)

Mesaj bir veya daha fazla kez teslim edilir; asla kaybolmaz, ama mükerrer teslim edilebilir. Gönderici, alıcıdan bir onay (ack) alana kadar mesajı yeniden dener. Ack kaybolursa gönderici mesajı gereksiz yere tekrar yollar ve alıcı aynı mesajı ikinci kez işleyebilir.

Bu, pratikte en yaygın ve en gerçekçi semantiktir. Kafka, RabbitMQ, Amazon SQS (standart kuyruk), Google Pub/Sub gibi sistemlerin varsayılan güvenilir modu esasen at-least-once sunar. "Kaybetmemek" çoğu iş uygulaması için "kopya işlememek"ten daha zor sağlanan bir garantidir, bu yüzden endüstri bu tarafı temel alır ve mükerrer sorununu tüketici (consumer) tarafında idempotency ile çözer.

### Exactly-Once (Tam Bir Kez)

Mesaj tam olarak bir kez işlenmiş etkisi yaratır: ne kaybolur ne de mükerrer etki bırakır. Kulağa ideal gelir, ama saf anlamıyla — yani "ağ üzerinden mesajın fiziksel olarak yalnızca bir kez iletilmesi" — dağıtık ve asenkron bir sistemde teorik olarak sağlanamaz. Bunun kanıtı, iki ordu problemi (Two Generals Problem) ve FLP imkânsızlık sonucu gibi klasik sonuçlarla ilişkilidir.

Bu nedenle gerçek dünyada "exactly-once" dediğimiz şey neredeyse her zaman **exactly-once processing** veya **effectively-once**'tır: mesaj birden çok kez teslim edilse bile *etkisi* (state değişikliği, yan etki) yalnızca bir kez oluşur. Bunu sağlayan mekanizma genellikle "at-least-once teslimat + idempotent işleme + deduplication"dır. Yani exactly-once, sıfırdan farklı bir sihir değil, at-least-once üzerine kurulmuş bir doğruluk katmanıdır.

## Kök Neden: Neden Exactly-Once Zordur?

Sorunun çekirdeği şudur: bir mesajı işlemek ve bu işlemi "işledim" diye kaydetmek iki ayrı adımdır ve aralarında sistem çökebilir.

Bir tüketici mesajı alır, veritabanına yazar, sonra kuyruğa "ack" gönderir. Şu iki sıralama düşünün:

- **Önce ack, sonra işle:** İşlemeden önce ack gönderirseniz ve tam o anda çökerseniz, kuyruk "işlendi" sanır ve mesajı bir daha vermez. Sonuç: **mesaj kaybı** (at-most-once davranışı).
- **Önce işle, sonra ack:** İşledikten sonra ack göndermeden çökerseniz, kuyruk cevabı almadığı için mesajı yeniden verir. Sonuç: **mükerrer işleme** (at-least-once davranışı).

İki adımı atomik yapamadığınız sürece (ki farklı sistemler — kuyruk ve veritabanı — arasında ucuz atomiklik yoktur) bu ikilemden kaçamazsınız. Endüstri neredeyse evrensel olarak ikinci seçeneği (önce işle, sonra ack) tercih eder, çünkü mükerrer işlemeyi idempotency ile zararsız kılmak, kaybolan veriyi geri getirmekten çok daha kolaydır. Kaybolan mesaj geri gelmez; kopya mesaj filtrelenebilir.

## Idempotency: Tanım ve Çalışma Mantığı

**Idempotent** bir operasyon, bir kez veya defalarca uygulandığında sistemin son durumunun aynı kaldığı operasyondur. Matematikteki tanımı: `f(f(x)) = f(x)`.

Dikkat: idempotent olan şey operasyonun *sonucu* değil, *etkisidir*. HTTP dünyasından bilinen örneklerle:

- `PUT /users/42 {ad: "Ali"}` idempotenttir: iki kez çağırsanız da 42 numaralı kullanıcının adı "Ali" olur. İkinci çağrı yeni bir değişiklik yaratmaz.
- `DELETE /users/42` idempotenttir: kullanıcı zaten silinmişse ikinci silme durumu değiştirmez (dönen HTTP kodu farklı olsa bile, *durum* aynıdır).
- `POST /users {ad: "Ali"}` idempotent **değildir**: her çağrı yeni bir kullanıcı yaratır. İki kez çağrılırsa iki Ali oluşur.

`x = x + 1` (bir sayacı artırmak) idempotent değildir; `x = 5` (mutlak değer atamak) idempotenttir. İşte at-least-once teslimatın tehlikesi tam olarak bu artırma tipi operasyonlarda ortaya çıkar: "hesabı 100 TL ile ücretlendir" mesajı iki kez işlenirse müşteri 200 TL öder.

### Doğal Idempotency vs. Yapay Idempotency

Bazı operasyonlar doğası gereği idempotenttir (mutlak set etme, "durumu X yap"). Bunlar için ekstra bir şey yapmanız gerekmez. Ama çoğu iş operasyonu (para çekme, stok düşme, e-posta gönderme, sipariş oluşturma) doğal olarak idempotent değildir. Bunları idempotent yapmanın standart yolu **idempotency anahtarı (idempotency key)** ve **deduplication**tır.

## Idempotency Anahtarları (Idempotency Keys)

Fikir basittir: her mantıksal isteğe, gönderen tarafın ürettiği benzersiz bir kimlik (genellikle bir UUID) iliştirilir. Sunucu bu anahtarı hatırlar. Aynı anahtarla ikinci bir istek geldiğinde, sunucu operasyonu tekrar çalıştırmak yerine ilk çalıştırmanın kaydedilmiş sonucunu döner.

Kritik nokta anahtarın **kim tarafından** üretildiğidir. Anahtar, retry yapabilen taraf (yani istemci/gönderici) tarafından üretilmeli ve retry'lar arasında **aynı kalmalıdır**. Eğer istemci her retry'da yeni bir anahtar üretirse, sunucu bunları farklı istekler sanar ve deduplication çalışmaz. Anahtar, "aynı mantıksal niyet"i temsil eder, "aynı ağ paketini" değil.

### Tipik Akış

1. İstemci bir idempotency anahtarı üretir: `k = uuid4()`.
2. İsteği bu anahtarla gönderir (örneğin `Idempotency-Key: <k>` başlığında — bu Stripe, Square gibi ödeme API'lerinin yaygın deseni).
3. Sunucu anahtarı bir deposunda (dedup store) arar:
   - **Yoksa:** Anahtarı "işleniyor" olarak kaydeder (ideal olarak operasyonla aynı transaction içinde), operasyonu çalıştırır, sonucu anahtara bağlı olarak saklar, sonucu döner.
   - **Varsa ve tamamlanmışsa:** Operasyonu tekrar çalıştırmaz; saklanmış sonucu döner. Yan etki tekrarlanmaz.
   - **Varsa ama hâlâ işleniyorsa:** Eşzamanlı bir retry gelmiştir; ya bekler ya da "çakışma, tekrar dene" hatası döner.

Bu akışın kalbi, "anahtarı kaydetme" ile "operasyonu yapma"nın atomik olmasıdır. Aksi hâlde ikisi arasındaki çökme yine kopyaya yol açar.

## Deduplication Stratejileri

Deduplication (dedup), gelen mesajın daha önce işlenip işlenmediğini tespit edip kopyaları elemektir. Birkaç temel strateji:

### 1. Dedup Store (Görülen Anahtarlar Tablosu)

En yaygın ve en genel yöntem. İşlenmiş her mesajın kimliğini (message ID veya idempotency key) bir tabloda/anahtar-değer deposunda tutarsınız. Yeni mesaj gelince kimliğe bakarsınız; varsa atlarsınız.

Uygulama detayı: bu deponun kaydını **iş operasyonuyla aynı atomik işlem** içinde yazmak gerekir. Örneğin, veritabanınızda `processed_messages(message_id PRIMARY KEY)` tablosu ve iş tablosu aynı transaction içinde güncellenir. `message_id` üzerindeki UNIQUE/PRIMARY KEY kısıtı, kopya insert'i veritabanının kendisine reddettirir. Bu, "kontrol et sonra yaz" (check-then-act) yarış koşulunu (race condition) veritabanının atomik kısıtına devrederek çözer — uygulama seviyesinde iki adım yerine tek atomik adım olur.

### 2. Doğal Anahtar (Natural Key) / Upsert

Eğer mesajın kendi içinde benzersiz bir iş kimliği varsa (örneğin `siparis_id`), ayrı bir dedup tablosuna gerek kalmadan doğrudan bu kimliği birincil anahtar yapıp `INSERT ... ON CONFLICT DO NOTHING` (PostgreSQL) veya eşdeğeri bir upsert kullanabilirsiniz. Bu, dedup'ı iş verisinin doğal yapısına gömer ve ayrıca depo bakımını ortadan kaldırır.

### 3. Zaman Pencereli Dedup (Windowed Deduplication)

Görülen tüm kimlikleri sonsuza dek saklamak pahalıdır. Birçok sistem yalnızca son N dakika/saatteki kimlikleri tutar. Amazon SQS FIFO kuyrukları örneğin belirli bir dedup penceresi (dokümante edilmiş, sınırlı bir süre) içinde `MessageDeduplicationId` bazlı kopyaları eler. Bu pencere dışında gelen çok geç bir kopya yakalanamaz. Kafka'nın idempotent producer'ı da benzer şekilde producer başına bir kimlik ve sequence numarası ile *broker'a yazma* seviyesinde kopyaları önler, ama bu uçtan uca değil, üretici-broker segmentiyle sınırlı bir garantidir.

### 4. Content Hash (İçerik Özeti)

Mesajın kimliği yoksa, içeriğinin bir hash'ini (örneğin SHA-256) kimlik olarak kullanabilirsiniz. Dikkat: iki farklı ama meşru şekilde aynı içerikli mesaj (örneğin "kullanıcı sayfayı iki kez ziyaret etti") yanlışlıkla kopya sayılabilir. Bu yüzden content hash yalnızca içeriğin gerçekten benzersizliği garantilediği durumlarda güvenlidir.

## Transactional Outbox ve İki Sistem Problemi

En sinsi kopya/kayıp kaynağı, **iki farklı sistemi atomik güncelleyememektir**: "veritabanına siparişi yaz VE kuyruğa mesaj yolla". Bu ikisi tek transaction'da olmadığı için, biri başarılı olup diğeri başarısız olabilir. Veritabanına yazıp mesajı yollamadan çökerseniz olay kaybolur; mesajı yollayıp veritabanına yazmadan çökerseniz hayalet mesaj oluşur.

Standart çözüm **Transactional Outbox** desenidir:

1. İş verisini ve gönderilecek mesajı **aynı veritabanı transaction'ında** yazarsınız. Mesaj, `outbox` adlı bir tabloya satır olarak eklenir. Transaction atomik olduğu için ya ikisi de olur ya hiçbiri.
2. Ayrı bir süreç (relay/publisher, sıklıkla Change Data Capture — CDC ile, örneğin Debezium) `outbox` tablosunu okuyup mesajları gerçek kuyruğa yollar ve gönderilenleri işaretler.

Bu relay adımı at-least-once çalışır (mesajı yolladıktan sonra "gönderildi" işaretini koymadan çökebilir), dolayısıyla kuyruğa kopya düşebilir. İşte bu yüzden **tüketici tarafı yine idempotent olmak zorundadır**. Outbox, kayıp problemini çözer; kopya problemini tüketiciye devreder. Bu, "exactly-once = at-least-once teslimat + idempotent tüketici" formülünün gerçek hayattaki tam görünümüdür.

## Doğru Kullanım Desenleri

- **Tüketicini her zaman idempotent yaz.** Kuyruğun ne söz verdiğine bakma; en az bir kez teslim varsayarak tasarla. Bu, tüm sistemin en dayanıklı kuralıdır.
- **Idempotency anahtarını istemci/kaynak üretsin ve retry'lar boyunca sabit tutsun.** Anahtar mantıksal niyeti temsil etmeli.
- **Dedup kaydını iş verisiyle aynı atomik işleme koy.** Ayrı adımlar yarış koşulu ve çökme penceresi yaratır.
- **Mümkünse operasyonları doğal olarak idempotent tasarla.** "Bakiyeyi 100 yap" (set), "bakiyeyi 100 azalt"tan (delta) daha güvenlidir. Delta gerektiğinde işlem kimliğiyle dedup şart.
- **Dedup penceresini retry ufkuna göre boyutlandır.** Retry'lar en fazla T süre boyunca olabiliyorsa, dedup penceresi T'den rahatça büyük olmalı.
- **İdempotent yanıtı sakla ve tekrar sun.** Aynı anahtarla gelen ikinci isteğe ilk işlemin *aynı* sonucunu dön; yeniden hesaplama.

## Yaygın Tuzaklar ve Hatalar

### Retry'da Yeni Anahtar Üretmek
En sık hata. İstemci her denemede yeni bir idempotency key üretirse, sunucu retry'ı yeni istek sanar. Anahtar retry döngüsünün *dışında*, isteğin mantıksal başlangıcında bir kez üretilmeli.

### Check-Then-Act Yarış Koşulu
"Önce anahtar var mı diye bak, yoksa işle" iki ayrı adımdır. İki kopya eşzamanlı gelirse ikisi de "yok" görüp ikisi de işleyebilir. Çözüm: kontrolü atomik kısıta (UNIQUE constraint, `INSERT ... ON CONFLICT`, atomik `SETNX`) devretmek. Uygulama seviyesinde "önce oku sonra yaz" neredeyse her zaman hatalıdır.

### Ack Zamanlamasını Yanlış Kurmak
İşlemeden önce ack (mesaj kaybı) veya işledikten çok sonra ack (gereksiz kopya) yerine, işlem tamamlanıp durum kalıcılaştıktan hemen sonra ack en güvenli konumdur. Auto-ack (otomatik onay) modları çoğu kuyrukta "önce ack" davranır ve sessizce veri kaybına yol açar.

### Idempotent Olmayan Yan Etkiler
Veritabanı yazmasını idempotent yaptınız ama aynı işleyicide bir de e-posta gönderiyorsunuz — e-posta gönderimi idempotent değildir, müşteri iki kez "siparişiniz alındı" e-postası alır. Kural: işleyicideki *her* yan etki ayrı ayrı idempotent olmalı, yoksa dış etkileri de outbox/dedup ile koruyun.

### "Kuyruk Bana Exactly-Once Sözü Verdi" Yanılgısı
Bir kuyruk "exactly-once" pazarlasa bile bu garanti çoğu zaman yalnızca kuyruğun kendi sınırları içindedir (örn. producer→broker veya broker içi), sizin harici veritabanınıza ve yan etkilerinize kadar uzanmaz. Uçtan uca exactly-once *etki* hâlâ sizin idempotent tasarımınıza bağlıdır. Kuyruğun garantisini uygulamanın doğruluk garantisiyle karıştırmak, üretimdeki en pahalı hatalardandır.

### Dedup Deposunu Sonsuza Kadar Büyütmek
Her mesaj kimliğini kalıcı tutmak depoyu şişirir ve sorguları yavaşlatır. TTL (time-to-live) ile pencereli tutun; ama pencerenin retry ufkundan kısa olmadığından emin olun, yoksa geç gelen bir kopya dedup dışına düşer.

### At-Most-Once'ı Yanlış Yere Uygulamak
Telemetri için makul olan "kaybolabilir" davranışını ödeme, sipariş, envanter gibi yerlerde kullanmak sessiz veri kaybı yaratır. Semantik seçimini işin veri kaybına toleransına göre yapın.

## Karar Rehberi (Özet)

- Veri **kaybolabilir**, hız kritik (metrik/telemetri) → **at-most-once**.
- Veri **kaybolmamalı**, kopya işleme zararsız hâle getirilebilir (çoğu iş sistemi) → **at-least-once + idempotent tüketici** (pratikte "effectively-once").
- İki sistemi (DB + kuyruk) atomik güncelleyemiyorsan → **Transactional Outbox**, artı idempotent tüketici.
- Doğruluk kritik ödeme/sipariş → **idempotency key** (istemci üretimli) + **atomik dedup** + **saklanmış yanıt**.

## Sonuç

Teslimat semantikleri, dağıtık sistemlerdeki temel belirsizliğin — "gitti mi, işlendi mi bilinemez" — mühendislik cevabıdır. Saf exactly-once teslimat bir serap olsa da, at-least-once teslimatı idempotent işleme ve deduplication ile birleştirerek **effectively-once** doğruluk elde etmek tamamen ulaşılabilirdir ve endüstrinin fiilî standardıdır. Aklınızda kalması gereken tek cümle: kuyruğunuzun garantisi ne olursa olsun, tüketicinizi kopya mesaj alacakmış gibi tasarlayın; çünkü er ya da geç alacaktır. Idempotency, bu kaçınılmaz kopyayı bir felaketten sıradan bir olaya çevirir.
