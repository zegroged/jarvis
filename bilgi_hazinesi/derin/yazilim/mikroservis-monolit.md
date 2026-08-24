# Mikroservis vs Monolit — Derin Dalış: Çözümlü Yürüyüş, Vaka, Karar ve Hata-Modu Kataloğu

Bu metin, aynı konudaki özet makalenin devamıdır. Özet makale "karmaşıklık yok olmaz, yer değiştirir", "dağıtık vergi", "bounded context" ve "monolith-first" gibi kavramsal çerçeveyi kurdu. Burada teoriyi bırakıp klavyeye iniyoruz: gerçek, çalışır kodla bir zafiyeti sahneleyip düzelteceğiz; gerçek bir sipariş akışını iki mimaride kodlayacağız; kararı takaslarıyla masaya yatıracağız; ve sahada tekrar tekrar görülen hataları kataloglayacağız.

---

## 1. Çözümlü yürüyüş: Kendi kendini ezen bir mikroservis

Somut bir sahne kuralım. Bir e-ticaret sisteminde `order-service` (sipariş servisi), her sipariş oluşturulduğunda `inventory-service`'ten (stok servisi) stok rezervasyonu ister. Aralarındaki iletişim senkron HTTP. Ekip bunu Python + `requests` ile şöyle yazdı ve aylarca "çalıştı":

### 1.1. Zafiyetli / hatalı kod

```python
# order_service/inventory_client.py  --- ZAFIYETLI SURUM
import requests

INVENTORY_URL = "http://inventory-service/reserve"

def reserve_stock(sku: str, quantity: int, order_id: str) -> bool:
    """Stok servisinden rezervasyon iste. True = basarili."""
    payload = {"sku": sku, "quantity": quantity, "order_id": order_id}
    resp = requests.post(INVENTORY_URL, json=payload)   # (1) timeout YOK
    resp.raise_for_status()                              # (2) hata = exception
    return resp.json()["reserved"]
```

```python
# order_service/handler.py  --- ZAFIYETLI SURUM
def create_order(request):
    order_id = new_order_id()
    save_order(order_id, status="PENDING")              # (3) once DB'ye yazildi

    for line in request.items:
        ok = reserve_stock(line.sku, line.qty, order_id)  # (4) her satir icin ayri cagri
        if not ok:
            raise OutOfStock(line.sku)

    charge_payment(request.payment, order_id)           # (5) sonra odeme
    set_order_status(order_id, "CONFIRMED")
    return {"order_id": order_id}
```

Kod okununca masum görünür. Ama üretimde Kara Cuma sabahı şu oldu: `inventory-service` yük altında yavaşladı — çökmedi, sadece yanıtları 8-10 saniyeye çıktı. Birkaç dakika içinde `order-service` tamamen kilitlendi ve *stok servisiyle hiç ilgisi olmayan* "sipariş geçmişini görüntüle" endpoint'i bile yanıt vermez oldu. Neden?

### 1.2. Sorun neden oluşuyor — kök neden zinciri

Burada tek bir bug değil, **üst üste binen dört tasarım hatası** var:

**(a) Timeout yok → thread'ler sonsuza kadar bloke.** `requests.post` varsayılan olarak süresiz bekler. `inventory-service` yavaşladığında, `order-service`'in her worker thread'i bir `reserve_stock` çağrısında "asılı" kalır. Sunucunun sabit bir thread havuzu vardır (diyelim 50 worker). 50 istek aynı anda stok servisini beklerken 51'inci istek — hangi endpoint olursa olsun — kuyruğa girer ve hizmet alamaz. Bu **kaynak tükenmesidir (resource exhaustion)**: bir servisin yavaşlığı, çağıran servisin *tüm* thread bütçesini yer. Özet makaledeki "cascading failure" tam olarak budur; burada onu satır satır görüyoruz.

**(b) Circuit breaker yok → umutsuz çağrılara devam.** Stok servisi açıkça hasta olduğu halde, `order-service` her yeni istekte tekrar tekrar ona gitmeye çalışır. Hızlı hata dönmek yerine, her istek 8 saniye bekleyip başarısız olur. Sistem "hızlı hata" yerine "yavaş hata" verir ki bu daha kötüdür.

**(c) İşlem sırası yanlış → orphan kayıt.** `create_order` önce siparişi `PENDING` kaydediyor (3), sonra stok/ödeme yapıyor. Ödeme adımı (5) bir exception fırlatırsa, DB'de asılı kalmış bir `PENDING` sipariş kalır ve rezerve edilen stok geri verilmez. Monolitteki tek transaction'ın atomikliği burada yok; kimse telafi (compensation) yazmamış.

**(d) Idempotency yok → retry stok çalar.** Diyelim client veya bir load balancer isteği retry etti (timeout gördüğü için). `reserve_stock` aynı `order_id` için ikinci kez çağrılır ve stok servisi bunu **yeni** bir rezervasyon sanıp ikinci kez düşer. Aynı sipariş iki kat stok yer.

Bunların hiçbiri "kod yanlış yazıldı" değil; hepsi "ağ çağrısı, fonksiyon çağrısı gibi ele alındı" hatasının farklı yüzleri. Monolitte `reserve_stock` bir metot çağrısı olsaydı, timeout/circuit breaker/idempotency kavramlarının hiçbirine ihtiyaç olmazdı.

### 1.3. Düzeltilmiş / doğru kod

Önce dayanıklı bir istemci. Timeout, sınırlı retry (exponential backoff + jitter), ve bir circuit breaker ekliyoruz:

```python
# order_service/inventory_client.py  --- DUZELTILMIS SURUM
import random
import time
import threading
import requests

INVENTORY_URL = "http://inventory-service/reserve"


class CircuitBreaker:
    """Basit ama dogru: ardisik hata esigi asilinca 'acik' olur ve
    OPEN suresi boyunca cagrilari hizli reddeder (fail-fast)."""
    def __init__(self, fail_threshold=5, reset_after=15.0):
        self.fail_threshold = fail_threshold
        self.reset_after = reset_after
        self._failures = 0
        self._opened_at = None
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            # OPEN suresi doldu mu? -> HALF-OPEN: tek bir deneme yap.
            if time.monotonic() - self._opened_at >= self.reset_after:
                self._opened_at = None
                self._failures = 0
                return True
            return False

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self.fail_threshold:
                self._opened_at = time.monotonic()


_breaker = CircuitBreaker()


class InventoryUnavailable(Exception):
    """Stok servisi su an cagirilamiyor (fail-fast)."""


def reserve_stock(sku: str, quantity: int, order_id: str) -> bool:
    if not _breaker.allow():
        # Devre acik: 8 saniye beklemeden, ANINDA hata don.
        raise InventoryUnavailable("circuit open")

    payload = {"sku": sku, "quantity": quantity, "order_id": order_id}
    # order_id + sku, rezervasyonun dogal idempotency anahtaridir.
    headers = {"Idempotency-Key": f"{order_id}:{sku}"}

    last_exc = None
    for attempt in range(3):                    # en fazla 3 deneme
        try:
            resp = requests.post(
                INVENTORY_URL,
                json=payload,
                headers=headers,
                timeout=(1.0, 2.0),             # (connect, read) timeout ZORUNLU
            )
            resp.raise_for_status()
            _breaker.record_success()
            return resp.json()["reserved"]
        except (requests.Timeout, requests.ConnectionError,
                requests.HTTPError) as exc:
            last_exc = exc
            _breaker.record_failure()
            # exponential backoff + jitter: retry firtinasi olusturma
            sleep = min(2 ** attempt * 0.1, 1.0) + random.uniform(0, 0.1)
            time.sleep(sleep)

    raise InventoryUnavailable(str(last_exc))
```

Şimdi handler'ı sıralama ve telafi açısından düzeltiyoruz:

```python
# order_service/handler.py  --- DUZELTILMIS SURUM
def create_order(request):
    order_id = new_order_id()
    reserved = []
    try:
        # (1) ONCE dis etkiler (rezervasyon), SON'da DB'yi CONFIRMED yap.
        for line in request.items:
            ok = reserve_stock(line.sku, line.qty, order_id)
            if not ok:
                raise OutOfStock(line.sku)
            reserved.append(line)

        charge_payment(request.payment, order_id)

        # Her sey basarili: tek atomik yerel yazim.
        save_order(order_id, status="CONFIRMED")
        return {"order_id": order_id}

    except (OutOfStock, PaymentFailed, InventoryUnavailable) as exc:
        # (2) TELAFI: rezerve edileni geri ver (compensating transaction).
        for line in reserved:
            release_stock(line.sku, line.qty, order_id)  # kendi idempotency'si var
        # Kalici hata kaydi tutmak istiyorsak ayri, iptal statusuyle yaz.
        save_order(order_id, status="FAILED", reason=str(exc))
        raise
```

Sunucu tarafında da `inventory-service`'in idempotent olması şart — istemci `Idempotency-Key` gönderiyor ama karşı taraf onu onurlandırmalı:

```python
# inventory_service/reserve_handler.py  --- DUZELTILMIS SURUM (sunucu)
def reserve(request):
    key = request.headers["Idempotency-Key"]
    # Ayni anahtarla daha once islenmisse, ESKI sonucu don; stogu TEKRAR dusme.
    existing = get_reservation_result(key)
    if existing is not None:
        return existing

    with db.transaction():                       # yerel ACID transaction
        if current_stock(request.sku) < request.quantity:
            result = {"reserved": False}
        else:
            decrement_stock(request.sku, request.quantity)
            result = {"reserved": True}
        store_reservation_result(key, result)    # anahtar + sonuc birlikte commit
    return result
```

Ne değişti, özet olarak:

- **Timeout** thread bloke olmasını engeller — kaynak tükenmesi biter.
- **Circuit breaker** hasta servise umutsuz çağrıları keser; sistem 8 saniye "yavaş hata" yerine milisaniyede "hızlı hata" verir ve toparlanmaya alan tanır.
- **Backoff + jitter'lı sınırlı retry**, geçici hataları maskeler ama retry fırtınası (bkz. hata #7) çıkarmaz.
- **Idempotency anahtarı** (hem istemci gönderir hem sunucu onurlandırır) retry'ların çift-düşme yapmasını engeller.
- **İşlem sırası + telafi**, dağıtık ortamda ACID'in yokluğunu saga tarzı el işçiliğiyle kapatır.

Dikkat: düzeltilmiş kod, hatalı koddan **kat kat uzun**. Bu tesadüf değil — özet makaledeki "dağıtık vergi" tam olarak bu ek koddur. Hiçbiri iş değeri üretmez; sadece ağın üstünde olmanın bedelidir.

---

## 2. Gerçek sistem örneği / vaka: Paylaşılan veritabanı tuzağı ve çıkış

En sık görülen gerçek felaket, kod düzeyinde değil **veri düzeyindedir**. Ekipler servisleri güzelce ayırır ama hepsi hâlâ aynı veritabanına bakar. "Nasılsa aynı tablo, iki servis de okusun" der. Sonra bu, sistemi görünmez şekilde bir distributed monolith'e çevirir.

### 2.1. Vaka: İki servis, tek `orders` tablosu

Diyelim `order-service` ve `analytics-service` aynı PostgreSQL `orders` tablosunu paylaşıyor. Analytics ekibi rapor sorgularını hızlandırmak için doğrudan tabloya bir kolon ekliyor ve bir kolonun tipini değiştiriyor:

```sql
-- analytics ekibi, order ekibine haber vermeden calistirdi:
ALTER TABLE orders ALTER COLUMN total_amount TYPE numeric(12,2);
ALTER TABLE orders ADD COLUMN analytics_bucket text;
```

`order-service`'in ORM'i `total_amount`'ı `integer` (kuruş) olarak map ediyordu. Tip değişince `order-service`'in yazımları sessizce yanlış ölçekte kaydedilmeye başladı — kimse deploy yapmadığı halde bir servis bozuldu. **Şema, iki servisin gizli ve yazısız API'sıdır.** Paylaşılan DB'de bir servisin özgürce yaptığı değişiklik, diğerinin sözleşmesini haber vermeden kırar.

### 2.2. Doğru desen: Veri sahipliği + event ile yayılma

Kural nettir: **her veriye tek bir servis sahiptir; dışarısı sadece o servisin API'sı veya yayınladığı event'ler üzerinden erişir.** Analytics'in `orders` verisine ihtiyacı varsa, tabloyu okumaz; `order-service`'in yayınladığı event'leri dinler ve kendi okuma modelini (read model) kurar.

```python
# order_service/events.py  --- order-service KENDI verisini sahiplenir
def confirm_order(order_id):
    with db.transaction():
        set_order_status(order_id, "CONFIRMED")
        # Outbox pattern: event'i AYNI transaction icinde bir outbox tablosuna yaz.
        # Boylece "DB commit oldu ama event yayinlanmadi" tutarsizligi olusmaz.
        write_outbox(
            topic="order.confirmed",
            payload={"order_id": order_id, "total_cents": total_of(order_id)},
        )
    # ayri bir relay sureci outbox'i okuyup broker'a (Kafka/RabbitMQ) basar
```

```python
# analytics_service/consumer.py  --- analytics KENDI kopyasini tutar
def on_order_confirmed(event):
    # Kendi semasi, kendi tablosu. order-service semasindan BAGIMSIZ.
    upsert_fact_row(
        order_id=event["order_id"],
        amount=event["total_cents"] / 100.0,
        bucket=classify(event),          # analytics'e ozgu alan, orders'i kirletmez
    )
```

Buradaki kritik detay **outbox pattern**'dir. "Önce DB'ye yaz, sonra event yayınla" naif yaklaşımı, tam ortada süreç çökerse "sipariş CONFIRMED ama kimse haberdar değil" tutarsızlığı bırakır. Event'i iş verisiyle *aynı yerel transaction'da* bir outbox tablosuna yazıp, ayrı bir relay ile broker'a taşımak bu ikili-yazım (dual-write) problemini çözer. Böylece:

- `order-service` şemasını istediği gibi evriltir; analytics kırılmaz.
- Analytics, order servisi çökse bile eldeki event'lerle çalışmaya devam eder (temporal decoupling).
- Her servis kendi ölçekleme ve dayanıklılık profiline sahip olur.

Bu vaka, özet makaledeki "her servis kendi verisinin tek sahibidir" ilkesinin *neden* pazarlık konusu olmadığını gösterir: paylaşılan DB, mikroservisin tüm faydasını iptal edip vergisini bırakır.

---

## 3. Karşılaştırma / karar: Hangi mimari, ne zaman, neden

Kararı üç eksende netleştirelim. Aşağıdaki tablo "genel doğru" değil, **takas haritasıdır** — hangi baskı hangi tarafa iter.

| Eksen | Monolit / Modüler monolit lehine | Mikroservis lehine |
|---|---|---|
| Takım büyüklüğü | 1-2 takım, <~20-30 mühendis: tek kod tabanı koordinasyonu kolay | 5+ bağımsız takım: her takım kendi servisini ayrı deploy eder, merge/deploy koordinasyonu dağılır |
| Domain bilgisi | Yeni/belirsiz domain: sınırlar henüz bilinmiyor, monolit hataları affeder | Olgun domain: bounded context'ler netleşmiş, sınırı betona dökmek güvenli |
| Ölçek profili | Homojen yük: her şey birlikte büyür/küçülür | Heterojen yük: bir bileşen (ör. arama, ödeme) diğerlerinden bağımsız ölçeklenmeli |
| Tutarlılık ihtiyacı | Güçlü ACID gerektiren, sıkı bağlı işlemler | Eventual consistency'nin kabul edilebildiği, gevşek bağlı akışlar |
| Operasyonel olgunluk | Zayıf CI/CD, gözlemlenebilirlik yok: dağıtık vergiyi ödeyemezsin | Güçlü platform: tracing, service mesh, otomatik deploy hazır |
| Teknoloji çeşitliliği | Tek dil/stack yeterli | Servis başına farklı dil/DB gerçekten gerekli (ör. ML servisi Python, ödeme Go) |
| Hata izolasyonu ihtiyacı | Kabul edilebilir: tek nokta ama basit | Yüksek: bir bileşenin çökmesi diğerlerini etkilememeli (bulkhead) |

### 3.1. Ara seçenek: Modüler monolit (çoğu ekip için doğru cevap)

Karar ikili değildir. Üçüncü ve genelde **en isabetli** seçenek modüler monolittir: tek deploy birimi ama içinde sert modül sınırları. Modüller birbirine sadece açık arayüzle bağlanır, birbirinin tablolarına uzanmaz. Dilde ifade edersek:

```
monolith/
  modules/
    order/        <- sadece order/api uzerinden disari acilir
      api.py      (public: create_order, get_order)
      internal/   (disaridan import YASAK - linter/arch-test ile zorlanir)
      db/         (sadece order modulu bu tablolara dokunur)
    inventory/
      api.py
      internal/
      db/
    payment/
      ...
```

Modüller arası çağrı hâlâ in-process fonksiyon çağrısıdır (ağ yok, ACID transaction mümkün, tek deploy). Ama sınırlar zaten çizildiği için, ileride `payment` modülü bağımsız ölçekleme isterse, onu servise **çıkarmak** (extract) bir yeniden yazım değil, bir mekanik ameliyattır: arayüz zaten net, veri zaten ayrık. Sınır disiplinini `ArchUnit` (Java), `import-linter` (Python) gibi mimari testlerle **derleme/CI aşamasında zorlarsınız** — böylece "yanlışlıkla internal'a dokunma" mümkün olmaz.

### 3.2. Sayılarla düşünmek: verginin faydayı geçtiği nokta

Kararı "his" ile değil, kaba bir maliyet muhasebesiyle verin. Mikroservise geçmenin **peşin** (sabit) maliyeti vardır ve ölçekten bağımsızdır: her yeni servis bir deploy pipeline'ı, bir on-call rotasyonu, bir ölçekleme politikası, tracing/metrik entegrasyonu ve dayanıklılık kodu ister. Faydası ise **ölçekle** büyür: bağımsız deploy sayesinde takımların birbirini beklememesi, sıcak bileşenin ayrı ölçeklenmesi, hata izolasyonu.

Küçük ekipte (2-3 takım) grafik acıdır: sabit maliyet yüksektir, fayda düşüktür — net negatif. Ekip 8-10 bağımsız takıma çıktığında monolitin *koordinasyon* maliyeti (aynı kod tabanına yüzlerce mühendisin commit atması, merge çakışmaları, "senin değişikliğin benim deploy'umu bloke etti" durumları) süper-lineer büyür; işte o zaman mikroservisin bağımsız deploy faydası sabit vergiyi geçmeye başlar. Kritik gözlem şudur: kırılım noktası genellikle **ham trafikte değil, insan/organizasyon karmaşıklığındadır.** 5 kişilik bir ekip günde milyonlarca istek alan bir monoliti gayet iyi işletebilir; ama 200 kişilik bir ekip, düşük trafikli bir monolitte bile deploy koordinasyonu yüzünden boğulur.

### 3.3. Karar kuralı (tek cümle)

Varsayılan modüler monolittir; bir modülü servise çıkarmak için **somut bir sinyal** ararsınız: (a) o modül diğerlerinden farklı hızda ölçekleniyor, (b) ayrı bir takım onu bağımsız deploy etmek istiyor, (c) farklı bir dayanıklılık/teknoloji profili gerekiyor. Sinyal yoksa çıkarmazsınız — çünkü sinyalsiz çıkarma, faydasız vergidir. Bu, özet makaledeki "geri dönüşü mümkün kıl" ilkesinin operasyonel karşılığıdır: modüler monolit hem ileri (extraction) hem geri (consolidation) yönde ucuz kapıdır. Netflix ve Amazon örneklerini kopyalamadan önce hatırlayın: onlar bu geçişi *zaten olgun ve devasa* monolitleri ölçeklerken yaptılar, sıfırdan başlarken değil — sizin başlangıç koşulunuz onların değil.

---

## 4. Hata-modu kataloğu: Sahada tekrar tekrar görülen 12 hata

**1. Ağ çağrısını fonksiyon çağrısı sanmak.** En kök hata. Timeout, kısmi başarısızlık, serializasyon, gecikme yok sayılır; ilk yavaşlamada sistem kilitlenir. Bölüm 1'deki tüm alt-hataların atası budur.

**2. Timeout yazmamak.** Varsayılan istemciler süresiz bekler. Tek bir yavaş bağımlılık, çağıran servisin tüm thread/bağlantı havuzunu tüketir ve alakasız endpoint'ler bile ölür (kaynak tükenmesi).

**3. Idempotency'siz retry.** Retry eklemek iyidir; ama sunucu isteği idempotent işlemezse, retry edilen "stok düş" veya "ödeme al" çağrısı işlemi ikinci kez uygular. Retry ve idempotency ayrılmaz ikilidir.

**4. Paylaşılan veritabanı.** Birden çok servisin aynı tabloya doğrudan erişmesi. Şema, yazısız bir API'ya dönüşür; bir servisin masum `ALTER TABLE`'ı diğerini deploysuz kırar (Bölüm 2). Gizli bağımlılığın en yaygın biçimi.

**5. Dual-write tutarsızlığı (outbox atlamak).** "Önce DB'ye yaz, sonra event yayınla" deyip ortada çökmek. Sipariş CONFIRMED ama event yayınlanmamış olur; downstream servisler sonsuza kadar tutarsız kalır. Çözüm: outbox pattern.

**6. Saga'sız dağıtık işlem (unutulan telafi).** Servis sınırını geçen bir işlemde ACID rollback yoktur. Compensating transaction yazılmazsa, "stok düştü, ödeme başarısız" durumunda stok sonsuza kadar kilitli kalır (orphan rezervasyon).

**7. Retry fırtınası (retry storm).** Backoff ve jitter olmadan konulan agresif retry'lar, zaten yük altında olan servisi daha da ezer; kısmi bir yavaşlamayı tam çöküşe çevirir. Exponential backoff + jitter zorunludur, retry sayısı sınırlı olmalıdır.

**8. Uzun senkron çağrı zinciri.** A→B→C→D biçiminde senkron zincirler gecikmeleri toplar (tail latency çarpışır) ve en zayıf halkanın çökmesini tüm zincirin çökmesine çevirir. Zincirler kısa tutulmalı, mümkünse asenkron/event-driven'e dönmelidir.

**9. Nano-servis aşırı bölünmesi.** Her fonksiyonu ayrı servis yapmak, ağ çağrısı sayısını ve operasyonel yükü patlatır. "Mikro" küçüklük değil, bağımsız değişebilirlik demektir; doğru büyüklük bir bounded context kadardır.

**10. Sınırı teknik katmandan çizmek.** UI-servisi / logic-servisi / DB-servisi biçiminde yatay bölme. Tek bir kullanıcı özelliği üç servisi birden değiştirtir; bağımsız deploy faydası hiç alınmaz. Bölme dikey (iş yeteneğine göre) olmalı.

**11. Observability'yi sonraya bırakmak.** Distributed tracing (correlation/trace ID), merkezi log ve servis başına metrik olmadan üretime çıkmak. İlk ciddi hatada, 15 servise yayılmış bir isteğin nerede takıldığını görmek imkânsız hale gelir; kör uçuş başlar. Bu altyapı ilk servisten *önce* hazır olmalı.

**12. Conway Yasası'nı yok saymak.** Servis sınırlarını takım sınırlarından bağımsız çizmek. Tek servisin birçok takıma dağıldığı ya da tek takımın onlarca servise baktığı yapılar, sürekli koordinasyon çatışması üretir; mimari organizasyonel olarak işlemez. Mimariyi takım yapısıyla hizalayın veya inverse Conway maneuver ile takımı mimariye göre kurun.

---

## Kapanış

Derin dalışın verdiği tek pratik ders şudur: mikroservisteki "kod" görünürde iş mantığıdır, ama gerçek kütlenin önemli kısmı **ağın üstünde hayatta kalma koduna** gider — timeout, circuit breaker, idempotency, outbox, saga, tracing. Bölüm 1'de bu kodun hatalı halinin bir servisi nasıl kendi kendine kilitlediğini; Bölüm 2'de paylaşılan verinin sınırları nasıl görünmez şekilde kırdığını; Bölüm 3'te kararın moda değil, ölçülebilir bir takas olduğunu; Bölüm 4'te aynı hataların neden tekrar tekrar geldiğini gördük. Doğru varsayılan çoğu ekip için modüler monolittir; mikroservise geçiş, kanıtlanmış bir sinyalle verilen bilinçli ve geri dönüşü mümkün bir karar olmalıdır — hiçbir zaman peşin ödenen ama faydası hiç gelmeyen bir vergi değil.
