# Test Stratejileri — Derin Dalış

Test yazmak kolaydır; *doğru* test yazmak zordur. Bu metin, bir test paketinin nasıl yanlış güven ürettiğini, nerede gerçek hatayı kaçırdığını ve stratejik kararların koda nasıl yansıdığını somut, çalışır kod üzerinden inceliyor. Kavramsal çerçeveyi (piramit, test doubles, flaky testler, coverage) bildiğinizi varsayıp doğrudan uygulamaya iniyoruz.

---

## 1. Çözümlü Yürüyüş: "Yeşil Ama Yalancı" Bir Test

Gerçekçi bir senaryoyla başlayalım. Bir e-ticaret sisteminde sipariş toplamını hesaplayan ve ödeme sağlayıcısına gönderen bir servisimiz var. Ekip "test yazdık, coverage %95" diyor. Ama production'da yanlış tutarlar tahsil ediliyor. Neden?

### Zafiyetli/Hatalı Kod

Önce servis:

```python
# order_service.py
from decimal import Decimal

class OrderService:
    def __init__(self, payment_gateway, discount_repo):
        self.payment_gateway = payment_gateway
        self.discount_repo = discount_repo

    def checkout(self, items, coupon_code=None):
        subtotal = sum(item.price * item.quantity for item in items)

        discount_rate = Decimal("0")
        if subtotal >= 500:
            discount_rate = Decimal("0.20")
        elif subtotal >= 100:
            discount_rate = Decimal("0.10")

        if coupon_code:
            extra = self.discount_repo.get_coupon_rate(coupon_code)
            discount_rate = discount_rate + extra
            if discount_rate > Decimal("0.25"):
                discount_rate = Decimal("0.25")

        total = subtotal * (1 - discount_rate)
        self.payment_gateway.charge(total)
        return total
```

Şimdi ekibin gurur duyduğu test:

```python
# test_order_service.py  (HATALI TEST)
from unittest.mock import MagicMock, Mock

def test_checkout_with_discount():
    gateway = MagicMock()
    discount_repo = MagicMock()
    discount_repo.get_coupon_rate.return_value = 0.05

    service = OrderService(gateway, discount_repo)

    item = Mock()
    item.price = 300
    item.quantity = 1

    result = service.checkout([item], coupon_code="SAVE5")

    # "Test geçti, kod çalışıyor" — gerçekten mi?
    gateway.charge.assert_called_once()
```

Bu test **yeşil yanar** ve coverage aracı `checkout` metodunun her satırını "kapsanmış" gösterir. Ama üç ayrı gerçek hatayı birden gizliyor.

### Sorun Neden Oluşuyor?

**Birinci hata — assertion yok, sadece "çağrıldı mı" var.** Test yalnızca `gateway.charge`'ın çağrıldığını doğruluyor; *hangi tutarla* çağrıldığını hiç kontrol etmiyor. `checkout` metodu `total` olarak `-999` bile döndürse, `None` döndürse, test yine geçerdi. Bu, coverage'ın neden "çalıştırma"yı ölçüp "doğrulama"yı ölçmediğinin canlı örneğidir. Satır çalıştı, ama hiçbir şey iddia edilmedi.

**İkinci hata — tip karışımı mock'la maskeleniyor.** Gerçek kodda `subtotal` bir `Decimal` (fiyatlar `Decimal` ise), ama testte `item.price = 300` bir `int`. `discount_repo.get_coupon_rate.return_value = 0.05` ise bir `float`. Gerçek kodda `Decimal + float` bir `TypeError` fırlatır. Ama testte `item` bir `Mock` olduğu için `item.price * item.quantity` bile gerçek çarpma değil — `Mock` nesnesi her operatöre başka bir `Mock` döndürür. Yani testin çalıştırdığı aritmetik, production'daki aritmetikle *aynı değil*. Test gerçeği taklit etmiyor, gerçeği *baypas ediyor*.

**Üçüncü hata — sınır durumu (`> 0.25` kırpması) hiç test edilmemiş.** Kupon %5 + %20 kademe indirimi = %25, tam sınırda. `500 TL üstü + kupon` senaryosunda toplam %25'i geçebilir mi? Kademe zaten %20, kupon %5, toplam tam %25 — kırpma tetiklenmez. Ama başka bir kupon %10 olsaydı %30 çıkar ve %25'e kırpılırdı. Bu dal hiç çalıştırılmadı; ama "coverage %95" cümlesi bunu gizliyor çünkü ölçüm satır bazlı.

Kök neden tek cümlede: **test, davranışı değil "kodun çağrıldığını" doğruluyor ve mock'lar gerçeğin yerine geçmek yerine gerçeği yok ediyor.**

### Düzeltilmiş/Doğru Kod

Önce testi, sonra gerekirse servisi düzeltelim. Doğru test, gerçek değerlerle çalışır, tutarı iddia eder ve sınırları tarar:

```python
# test_order_service.py  (DOĞRU TEST)
from decimal import Decimal
from dataclasses import dataclass
import pytest

@dataclass
class LineItem:              # Mock yerine gerçek, hafif bir veri tipi
    price: Decimal
    quantity: int

class FakeDiscountRepo:      # MagicMock yerine kontrol edilebilir bir Fake
    def __init__(self, rates):
        self._rates = rates
    def get_coupon_rate(self, code):
        return self._rates.get(code, Decimal("0"))

class SpyGateway:           # charge'a geçen tutarı yakalayan basit spy
    def __init__(self):
        self.charged = None
    def charge(self, amount):
        self.charged = amount

@pytest.mark.parametrize("subtotal, coupon, expected_total", [
    (Decimal("99.99"),  None,    Decimal("99.99")),   # 100 altı: indirim yok
    (Decimal("100.00"), None,    Decimal("90.00")),   # sınır: %10 başlar
    (Decimal("499.99"), None,    Decimal("449.991")), # hala %10
    (Decimal("500.00"), None,    Decimal("400.00")),  # sınır: %20 başlar
    (Decimal("500.00"), "SAVE5", Decimal("375.00")),  # %20 + %5 = %25 (tam sınır)
    (Decimal("500.00"), "SAVE10",Decimal("375.00")),  # %20 + %10 = %30 -> %25 kırpma
])
def test_checkout_totals(subtotal, coupon, expected_total):
    repo = FakeDiscountRepo({
        "SAVE5":  Decimal("0.05"),
        "SAVE10": Decimal("0.10"),
    })
    gateway = SpyGateway()
    service = OrderService(gateway, repo)

    item = LineItem(price=subtotal, quantity=1)
    total = service.checkout([item], coupon_code=coupon)

    assert total == expected_total          # DÖNEN değeri iddia et
    assert gateway.charge == expected_total or gateway.charged == expected_total
```

Bu test yazılınca `SAVE10` senaryosu **kırılır** — çünkü servis `1 - discount_rate` hesabında `Decimal` ile `int` karıştırıyor ve %25 kırpma dalı ilk kez gerçekten çalıştığında ortaya bir kusur çıkar. Servisi de tiplerde tutarlı hale getiriyoruz:

```python
# order_service.py  (DÜZELTİLMİŞ)
from decimal import Decimal

MAX_DISCOUNT = Decimal("0.25")

class OrderService:
    def __init__(self, payment_gateway, discount_repo):
        self.payment_gateway = payment_gateway
        self.discount_repo = discount_repo

    def checkout(self, items, coupon_code=None):
        subtotal = sum(
            (item.price * item.quantity for item in items),
            start=Decimal("0"),
        )

        if subtotal >= Decimal("500"):
            discount_rate = Decimal("0.20")
        elif subtotal >= Decimal("100"):
            discount_rate = Decimal("0.10")
        else:
            discount_rate = Decimal("0")

        if coupon_code:
            discount_rate += self.discount_repo.get_coupon_rate(coupon_code)
            discount_rate = min(discount_rate, MAX_DISCOUNT)

        total = subtotal * (Decimal("1") - discount_rate)
        self.payment_gateway.charge(total)
        return total
```

Değişen şey yalnızca kod değil, **testin niteliği**: artık dönen değeri iddia ediyor, gerçek `Decimal` aritmetiğini çalıştırıyor (Mock değil), sınırları parametrik olarak tarıyor ve `charge`'a geçen tutarı bir spy ile yakalıyor. Coverage aynı %95'te kalsa bile, bu test paketinin *güven değeri* on kat arttı. İşte "yeşil ekran" ile "gerçek güven" arasındaki fark tam olarak budur.

---

## 2. Gerçek Sistem Örneği: Testcontainers ile Integration Testin Yakaladığı Hata

Bölüm 1'deki `discount_repo` bir sınıftı, mock'ladık. Ama gerçek sistemde o repository bir veritabanına konuşur ve unit testin *asla* yakalayamayacağı bir hata sınıfı tam burada, kodun ile veritabanının *sınır yüzeyinde* yaşar. Somut bir vaka kuralım.

Diyelim ki `discount_repo` şöyle:

```python
# discount_repo.py
class DiscountRepo:
    def __init__(self, conn):
        self.conn = conn

    def get_coupon_rate(self, code):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT rate FROM coupons WHERE coupon_code = %s AND active = true",
            (code,),
        )
        row = cur.fetchone()
        return row[0] if row else Decimal("0")
```

Unit testte `conn`'u mock'larsanız, `SELECT rate FROM coupons WHERE coupon_code = ...` sorgusunun **sütun adı `coupon_code` mı yoksa `code` mu**, tablo adı `coupons` mu `coupon` mu, `active` sütunu var mı — hiçbirini test etmezsiniz. Mock, sorgu metnini bir string olarak yutar ve sizin verdiğiniz `return_value`'yu döndürür. SQL yanlış olsa bile unit test yeşildir. Bu, "mock drift" değil, doğrudan **mock körlüğü**: gerçek şemayla hiç temas yok.

Integration test bu boşluğu kapatır. Testcontainers ile her koşuda temiz, gerçek bir PostgreSQL ayağa kaldırıyoruz:

```python
# test_discount_repo_integration.py
import pytest
import psycopg2
from decimal import Decimal
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="module")
def pg_conn():
    with PostgresContainer("postgres:16") as postgres:
        conn = psycopg2.connect(
            host=postgres.get_container_host_ip(),
            port=postgres.get_exposed_port(5432),
            user=postgres.username,
            password=postgres.password,
            dbname=postgres.dbname,
        )
        cur = conn.cursor()
        # Şema, production migration'larıyla AYNI olmalı
        cur.execute("""
            CREATE TABLE coupons (
                coupon_code TEXT PRIMARY KEY,
                rate NUMERIC(4,2) NOT NULL,
                active BOOLEAN NOT NULL DEFAULT true
            );
        """)
        cur.execute(
            "INSERT INTO coupons (coupon_code, rate, active) VALUES "
            "('SAVE5', 0.05, true), ('EXPIRED', 0.30, false);"
        )
        conn.commit()
        yield conn
        conn.close()

@pytest.fixture(autouse=True)
def clean_state(pg_conn):
    # Her testten sonra izolasyonu koru: eklenen satırları geri al
    yield
    pg_conn.rollback()

def test_active_coupon_returns_rate(pg_conn):
    repo = DiscountRepo(pg_conn)
    assert repo.get_coupon_rate("SAVE5") == Decimal("0.05")

def test_inactive_coupon_ignored(pg_conn):
    repo = DiscountRepo(pg_conn)
    # 'active = false' filtresi gerçekten çalışıyor mu?
    assert repo.get_coupon_rate("EXPIRED") == Decimal("0")

def test_unknown_coupon_returns_zero(pg_conn):
    repo = DiscountRepo(pg_conn)
    assert repo.get_coupon_rate("NOPE") == Decimal("0")
```

Bu test paketi, unit testin göremediği en az üç gerçek riski yakalar:

1. **Şema uyumsuzluğu.** SQL'de `coupon_code` yazıp tabloda `code` sütunu varsa, `psycopg2` `UndefinedColumn` fırlatır. Test anında kırmızıya döner. Mock'lu unit test bunu asla yakalayamazdı.
2. **`active = false` filtresinin doğruluğu.** `EXPIRED` kuponu %30 oranıyla veritabanında var ama pasif. Eğer `WHERE ... AND active = true` koşulunu yanlışlıkla silerseniz, `test_inactive_coupon_ignored` %30 döner ve kırılır. Bu, gerçek bir iş kuralı regresyonudur — pasif kupon uygulanırsa şirket para kaybeder.
3. **`NUMERIC(4,2)` tip dönüşümü.** Veritabanı `NUMERIC` döndürür; `psycopg2` bunu `Decimal`'e çevirir. Eğer koddaki karşılaştırma `float` beklerse, ince yuvarlama hataları çıkardı. Gerçek sürücüyle çalışmak bunu ortaya döker.

Mimari not: fixture'ın `scope="module"` olması container'ı bir kez ayağa kaldırıp tüm modül için paylaşır — hız için. Ama izolasyon `clean_state` fixture'ıyla korunur (her test sonrası `rollback`). Bu, bölüm 4'te göreceğimiz "test sırası bağımlılığı" hata-modunun panzehiridir: testler paylaşılan container'ı kullanır ama paylaşılan *state*'i kullanmaz. Testcontainers'ın asıl kazancı da budur — "benim makinemde çalışıyor" sorunu ortadan kalkar, çünkü geliştirici de CI de `postgres:16` imajının birebir aynısına karşı test eder.

---

## 3. Karşılaştırma / Karar: Test Double Seçimi ve Katman Dengesi

Bölüm 1'de bir Fake ve bir Spy kullandık; bölüm 2'de gerçek bir veritabanı. Bu seçimler keyfi değil. İşte kararların takas tablosu.

### Test Double Türü Seçimi

| Yaklaşım | Ne zaman kullan | Kazanç | Bedel / Risk |
|---|---|---|---|
| **Gerçek nesne** (mock yok) | Kendi iç mantığın, saf fonksiyonlar, ucuz bağımlılıklar | En yüksek güven; refactoring'e dayanıklı | Yavaş veya yan etkiliyse pratik değil |
| **Stub** | Sabit bir cevap yeterli; sonucu (state) doğrulayacaksın | Basit, okunur; implementasyona bağlanmaz | Etkileşimi doğrulamaz |
| **Fake** (bellek-içi repo vb.) | Bağımlılık gerçekçi davranmalı ama gerçeği pahalı | Hızlı + davranışsal olarak gerçekçi | Fake ile gerçek zamanla ayrışabilir |
| **Spy** | Bir çağrının argümanını yakalayıp iddia edeceksin | State doğrulamayı korur, argümanı görür | Fazla kullanılırsa etkileşim testine kayar |
| **Mock** (etkileşim doğrulama) | Yalnızca "çağrıldı mı" gerçekten önemliyse (ör. e-posta gönderildi mi) | Yan etkinin gerçekleştiğini kanıtlar | Implementasyona kilitler; refactoring'i kırar |
| **Gerçek bağımlılık (Testcontainers)** | Sınır yüzeyi kritik: SQL, serialization, protokol | Şema/kontrat hatalarını yakalar | Yavaş; container altyapısı gerekir |

Karar kuralı iki eksende netleşir. Birincisi **sahiplik**: sahip olmadığın ve kontrol edemediğin sınırı (üçüncü parti ödeme API'si, e-posta, saat, rastgelelik) mock/stub'la; sahip olduğun iç mantığı gerçek nesnelerle test et. İkincisi **doğrulama tipi**: sonucu mu yoksa etkileşimi mi umursuyorsun? "Doğru tutar tahsil edildi mi" bir *sonuç* sorusudur → spy/stub yeter. "E-posta gerçekten *gönderildi* mi" bir *etkileşim* sorusudur → mock meşrudur, çünkü burada tek gözlemlenebilir davranış zaten çağrının kendisidir.

En sık yapılan yanlış takas: iç mantık için mock (etkileşim doğrulama) seçmek. Bölüm 1'deki `MagicMock` cehennemi tam buydu — `item` bir mock olunca aritmetik hiç çalışmadı. Kural: **etkileşim doğrulamayı yalnızca dış, yan etkili sınırlarda kullan.**

### Katman Dengesi: Piramit mi, Kupa mı?

Aynı `checkout` özelliğini üç katmanda da test edebilirdik. Hangisi kaç tane olmalı?

- **Unit** (bölüm 1): İndirim kademelerinin *tüm* sınır kombinasyonları burada. On beş parametrik senaryo milisaniyelerde koşar. İş mantığının kombinatoryal derinliği unit katmanına aittir; e2e'de her senaryo için gerçek sipariş oluşturmak delilik olurdu.
- **Integration** (bölüm 2): `checkout` mantığının *bir* temsili yolu + repository'nin veritabanıyla teması. Amaç kombinasyon taramak değil, *sınır yüzeyinin* çalıştığını kanıtlamak. Bir-iki senaryo yeter.
- **E2E**: Yalnızca "kullanıcı sepete ürün ekleyip kupon girip ödeme yapabiliyor mu" — tek bir kritik yolculuk. Kademelerin doğruluğu değil, katmanların *birlikte ayakta olduğu* doğrulanır.

Piramit ile kupa arasındaki gerçek gerilim şu soruda düğümlenir: bu sistemde hatalar nerede yaşıyor? Monolitik, ağır iş-mantıklı bir sistemde hatalar birimlerin *içinde* yaşar → piramit haklıdır, unit tabanı geniş tut. Çok sayıda küçük servisin HTTP/JSON ile konuştuğu bir sistemde hatalar birimlerin *arasında* (serialization, kontrat, timeout) yaşar → kupa haklıdır, integration'a yaslan. İkisi de "yavaş ve kırılgan e2e'yi az tut" ilkesinde birleşir; yalnızca orta katmanın ağırlığında ayrışırlar. Dogma değil, mimariye bakıp karar verilir.

### Flaky Test: Retry mı, Kök Sebep mi?

Üçüncü kritik karar. Bir e2e test %2 oranında rastgele kırılıyor. Seçenekler:

- **Kör retry (3 kez dene, biri geçerse yeşil):** Ucuz, build'i yeşil tutar. Ama gerçek bir race condition'ı — production'da gerçek kullanıcıyı da etkileyecek olanı — halının altına süpürür. Sinyal değeri düşer.
- **Karantina + kök sebep:** Flaky testi ana sinyalden ayır, ayrı raporla, kök sebebi bul ve düzelt (koşula-dayalı bekleme, saat enjeksiyonu, izolasyon). Pahalı ama sinyal temiz kalır.

Ölçülü orta yol pratikte şudur: retry'ı bir *görmezden gelme* aracı değil, *ölçülen* bir operasyonel karar yap. Flakiness oranını metrikle takip et; bir test retry ile kurtarılıyorsa bunu bir "borç" olarak kaydet ve kök sebebini kapatana kadar karantinada tut. Retry'ın kendisi kötü değil; retry'ı *görünmez* yapmak kötü.

Somut bir örnek üzerinden bakalım. Diyelim bir e2e test şöyle yazılmış:

```python
def test_checkout_flow(page):
    page.click("#add-to-cart")
    time.sleep(2)                      # KÖTÜ: sabit bekleme
    page.click("#checkout")
    assert "Teşekkürler" in page.content()
```

Bu test iki gizli non-determinizm barındırır. Birincisi `sleep(2)` — sepet güncellemesi bazen 2.3 saniye sürerse test kırılır, ve ekip refleks olarak retry açar. İkincisi, `#checkout` butonu asenkron bir istekten sonra *aktifleşiyorsa*, sleep süresi tesadüfen tuttuğu için sorun uzun süre gizli kalır. Doğru çözüm koşula-dayalı beklemedir:

```python
def test_checkout_flow(page):
    page.click("#add-to-cart")
    page.wait_for_selector("#checkout:not([disabled])")  # koşula dayalı
    page.click("#checkout")
    page.wait_for_selector("text=Teşekkürler")
    assert page.is_visible("text=Teşekkürler")
```

Bu değişiklikten sonra test, makine hızından bağımsız hale gelir; ve eğer buton hiç aktifleşmezse, retry ile maskelemek yerine gerçek zaman aşımıyla *anlamlı* bir hata verir. Kök sebebi çözmek, flaky'i saklamaktan her zaman daha ucuzdur — çünkü saklanan her flaky, günün birinde gerçek bir hatayı da sessizce yutar.

---

## 4. Hata-Modu Kataloğu

Geliştiricilerin test yazarken tekrar tekrar düştüğü tipik tuzaklar:

1. **Assertion'sız test.** Fonksiyonu çağırıp dönen değeri hiç iddia etmemek; yalnızca "çağrıldı" veya "patlamadı" diye kontrol etmek. Coverage yeşil yanar ama davranış doğrulanmaz — bölüm 1'in çekirdek hatası.

2. **Mock ile gerçeği baypaslamak.** Test edilen nesnenin *içindeki* değerleri (`item.price` gibi) mock yapmak, böylece gerçek aritmetik/mantık hiç çalışmaz. Mock her operatöre başka bir mock döndürür ve test, production'dan tamamen kopuk bir kodu çalıştırır.

3. **İç mantığı aşırı mock'lamak (tautolojik test).** İki iç sınıf arasındaki her etkileşimi mock'layıp doğrulamak; test yalnızca "kodu yazdığım gibi yazdım" der, doğru olduğunu değil. Refactoring anında kırılır, gerçek entegrasyon hatasını asla yakalamaz.

4. **Sabit `sleep` ile async beklemek.** `time.sleep(2)` ile bir asenkron işlemin bitmesini ummak. CI makinesi yavaşlayınca 2 saniye yetmez, test flaky olur. Doğrusu: belirli bir koşul (eleman göründü, durum X oldu) sağlanana kadar polling ile beklemek.

5. **Saat/tarih bağımlılığı.** `datetime.now()` kullanan testler ay sonunda, gece yarısında, DST geçişinde veya farklı timezone'da kırılır. Saati enjekte edilebilir bir bağımlılık (`clock` parametresi) yapıp testte sabitlemek gerekir.

6. **Sıralama garantisi olmayan sorguyu sıralı beklemek.** `ORDER BY` olmadan gelen sonucun belirli bir sırada olduğunu varsaymak. Veritabanı sırayı garanti etmez; farklı çalıştırmada veya farklı planlayıcıda sıra değişir ve test flaky olur.

7. **Test sırası / paylaşılan state bağımlılığı.** Bir testin, önceki testin bıraktığı veritabanı satırına veya global değişkene bel bağlaması. Testler paralel veya farklı sırada koşunca kırılır. Her test kendi verisini kurup temizlemeli (bölüm 2'deki `rollback` fixture'ı).

8. **Mock drift + contract testinin yokluğu.** Dış servisin gerçek davranışı değişir (bir alan artık farklı formatta), ama mock eski hali taklit etmeye devam eder. Testler yeşil, production kırık. Contract testing ile mock'un gerçeğe sadakati doğrulanmadıkça bu risk sessizce büyür.

9. **Şemayı hiç test etmemek (mock körlüğü).** Repository'nin SQL'ini yalnızca mock'lu unit testle test etmek; yanlış sütun/tablo adı, eksik `WHERE` filtresi görünmez kalır. Gerçek veritabanına karşı bir integration test şart (bölüm 2).

10. **Coverage yüzdesini hedefe çevirmek (Goodhart).** "%100 coverage zorunlu" kapısı koymak; geliştiriciler yüzdeyi yükseltmek için assertion'sız, anlamsız test yazmaya başlar. Metrik yükselir, güven artmaz, bakım yükü artar.

11. **Her şeyi e2e ile test etmek (dondurma külahı).** Sınır durumlarını en yavaş, en kırılgan katmanda taramak. Geri bildirim döngüsü onlarca dakikaya çıkar, flakiness patlar, ekip testi çalıştırmaktan kaçınır.

12. **Test kodunu ikinci sınıf görmek.** Kopyala-yapıştır kurulum blokları, sihirli sabitler, anlamsız isimler (`test_1`, `test_2`). Test kodu da bakımlı koddur; çürüdüğünde ekip test paketinden korkmaya başlar ve değişiklik yapma cesaretini kaybeder.

13. **Flaky'i kör retry ile normalleştirmek.** Kararsız testi otomatik yeniden denemeyle örtbas etmek. Bazı flakiness gerçek bir race condition'ın habercisidir; retry onu production'a taşır. Retry ölçülen bir karar olmalı, görünmez bir alışkanlık değil.

14. **Hata yolunu (unhappy path) hiç test etmemek.** Yalnızca "her şey yolunda" senaryosunu test edip; geçersiz kupon, bağlantı kopması, negatif miktar, boş sepet gibi durumları atlamak. Gerçek production hatalarının çoğu tam bu test edilmemiş kenar durumlarında yaşar.

---

## Kapanış

Bu metnin çekirdek dersi tek cümlede: **test, kodun çağrıldığını değil doğru davrandığını kanıtlamalıdır; ve bu kanıtı en ucuz katmanda, gerçeği baypaslamadan, deterministik biçimde üretmelidir.** Bölüm 1 assertion'sız yeşil yalanı, bölüm 2 sınır yüzeyindeki görünmez hatayı, bölüm 3 hangi aracın hangi takasla seçileceğini, bölüm 4 ise bu derslerin ihlal edildiği tipik anları gösterdi. İyi test stratejisi bir araç kutsamaz; her testi "bu bana hangi güveni, hangi maliyetle kazandırıyor?" sorusuyla tartar. Nihai amaç yeşil ekran değil, değişikliği korkusuzca yapabilme özgürlüğüdür.
