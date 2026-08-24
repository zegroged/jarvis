# Caching Stratejileri — Derin Dalış

Bu metin, caching konusunun özet seviyesini geride bırakıp gerçek kodun içine iner. Amaç, "cache ekle, hızlansın" refleksinin nasıl sessizce bozuk sistemler ürettiğini gerçek kod blokları üzerinden göstermek, ardından o hataların nasıl doğru biçimde düzeltildiğini adım adım kurmaktır. Odak noktamız çoğu zaman gecikme değil, **tutarlılık ve dayanıklılık** olacak — çünkü caching'in kolay kısmı doldurmak, zor kısmı doğru anda ve doğru sırayla boşaltmaktır.

---

## 1. Çözümlü yürüyüş: Sessizce bayat veri gösteren bir cache-aside

Somut bir senaryo üzerinden gidelim. Bir e-ticaret servisinde ürün detayı okunuyor ve fiyat güncelleniyor. Aşağıda gerçek dünyada sıkça karşılaştığım, "çalışıyor gibi görünen" ama üretimde sinsi hatalar üreten bir Python + Redis cache-aside implementasyonu var.

### Zafiyetli kod

```python
import json
import redis
import psycopg2

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def get_product(product_id):
    key = f"product:{product_id}"
    cached = r.get(key)
    if cached:                      # cache hit
        return json.loads(cached)

    row = db_fetch_product(product_id)   # cache miss -> DB
    r.set(key, json.dumps(row))          # DİKKAT: TTL yok
    return row

def update_price(product_id, new_price):
    key = f"product:{product_id}"
    # Önce cache'i güncelliyoruz ki okuma hemen taze görsün
    row = r.get(key)
    if row:
        row = json.loads(row)
        row["price"] = new_price
        r.set(key, json.dumps(row))      # cache'i "güncelle"
    db_update_price(product_id, new_price)   # sonra DB
```

İlk bakışta mantıklı görünüyor: okumada cache-aside var, yazmada hem cache'i hem veritabanını güncelliyoruz. Fakat bu kodda en az üç ayrı ciddi hata var ve üçü de üretimde ortaya çıkana kadar test ortamında görünmez.

### Sorun neden oluşuyor?

**Hata 1 — Yazma sırası ters ve "silme" değil "güncelleme" yapılıyor.** Kod önce cache'i güncelleyip *sonra* veritabanına yazıyor. İki eşzamanlı isteği düşünün:

- İşlem A: `update_price(42, 100)` — cache'e 100 yazdı, henüz DB'ye yazmadan CPU'yu kaybetti.
- İşlem B: `update_price(42, 120)` — cache'e 120 yazdı, DB'ye 120 yazdı, tamamlandı.
- İşlem A devam etti: DB'ye 100 yazdı.

Sonuç: veritabanında **100**, cache'te **120**. İki depo kalıcı olarak birbirinden ayrıştı ve TTL de olmadığı için bu tutarsızlık sonsuza kadar sürer. Bu klasik bir **write-write race**'tir ve "cache'i güncelle" deseninin kaçınılmaz sonucudur.

**Hata 2 — TTL yok.** `r.set(key, ...)` çağrılarının hiçbirinde süre sınırı yok. Yani yukarıdaki gibi bir tutarsızlık bir kez oluştuğunda, onu düzeltecek hiçbir mekanizma yoktur. TTL, invalidation mantığındaki hataların "en son savunma hattı"dır; onu kaldırmak emniyet ağını kaldırmaktır.

**Hata 3 — Read/update arası klasik stale-set race.** `get_product` içinde miss olan bir okuma DB'den eski değeri çekip cache'e yazarken, araya giren bir `update_price` cache'i güncelleyip DB'yi güncelleyebilir; ardından geç kalan okuma eski değeri cache'e geri yazar. `set`'te TTL olmadığı için bu eski değer kalıcılaşır.

### Düzeltilmiş kod

Doğru desen şudur: **önce veritabanına yaz, sonra cache girdisini sil (güncelleme değil, sil), her `set`'e TTL koy ve stale-set race'ini kapatmak için delayed double delete uygula.**

```python
import json
import time
import threading
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
TTL = 300  # saniye — son savunma hattı

def get_product(product_id):
    key = f"product:{product_id}"
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)

    row = db_fetch_product(product_id)
    if row is None:
        # Negatif sonucu da KISA TTL ile cache'le -> cache penetration'a karşı
        r.set(key, json.dumps(None), ex=30)
        return None

    # SET NX: bu arada bir invalidation araya girdiyse üzerine yazma
    r.set(key, json.dumps(row), ex=TTL, nx=True)
    return row

def update_price(product_id, new_price):
    key = f"product:{product_id}"
    # 1) Önce gerçeğin kaynağını güncelle
    db_update_price(product_id, new_price)
    # 2) Cache'i SİL (güncelleme değil)
    r.delete(key)
    # 3) Delayed double delete: araya girmiş bir stale-okumayı temizle
    def second_delete():
        time.sleep(0.5)
        r.delete(key)
    threading.Thread(target=second_delete, daemon=True).start()
```

Neden bu doğru?

- **Önce DB, sonra sil:** Veritabanı her zaman gerçeğin tek kaynağıdır. Onu önce güncelleyip cache'i silince, bir sonraki okuma cache miss alır ve garanti taze değeri çeker.
- **Güncelleme yerine silme:** Silmek "bilmiyorum, tekrar öğren" demektir; yanlış güncelleme ise "yanlış biliyorum ama doğru sanıyorum"dur. Silme her zaman daha güvenli.
- **`nx=True` (SET if Not eXists):** Okuma tarafındaki `set`, eğer o an bir güncelleme girdiyi zaten sildiyse ve başka biri taze değer koyduysa, üzerine eski değeri yazmaz.
- **Delayed double delete:** DB güncellenip cache silindikten sonra, ama silme tamamlanmadan hemen önce başlamış bir okuma eski değeri geri koyabilir. Yarım saniye sonra ikinci silme bu "hayalet" girdiyi temizler.
- **TTL:** Tüm bu mantıkta yine de bir hata kalırsa, 5 dakika içinde girdi kendiliğinden tazelenir.

Not: Gerçek üretim sistemlerinde `second_delete` için ham thread yerine kalıcı bir kuyruk (ör. bir mesaj kuyruğu üzerinde gecikmeli iş) tercih edilir; süreç `sleep` sırasında çökerse ikinci silme kaybolmasın diye.

### Bu deseni neyin ötesine taşımak gerekir?

Delayed double delete pratik bir yamadır ama felsefi olarak hâlâ "uygulama kodunun doğru sırada iş yapmasına" güvenir. Yüksek tutarlılık gereken sistemlerde tercih edilen daha sağlam yaklaşım, invalidation'ı uygulama kodundan tamamen koparıp **veritabanının değişiklik akışına (change data capture / CDC)** bağlamaktır. Fikir şudur: uygulama sadece veritabanına yazar; ayrı bir tüketici, veritabanının replikasyon günlüğünü (ör. bir binlog/WAL akışı) dinler ve her `UPDATE`/`DELETE` olayında ilgili cache anahtarını siler. Bunun kritik avantajı, cache silmenin artık "yazma yolunda uygulamanın hatırlaması gereken bir adım" olmaktan çıkıp, **gerçeğin kaynağının kesin bir yan etkisi** haline gelmesidir. Uygulamanın bir yerinde bir yazma yolunu cache silmeden bırakmanız artık imkânsızdır çünkü silme kararı DB günlüğünden doğar, koddan değil. Bedeli ek altyapı ve olayların cache'e ulaşmasındaki küçük gecikmedir (bu süre boyunca kısa bir bayatlık penceresi kalır), bu yüzden yine TTL emniyet ağı korunur.

---

## 2. Gerçek sistem örneği: Cache stampede'i kilitle çözmek

Şimdi gerçek bir üretim vakasına bakalım. Popüler bir "ana sayfa öne çıkanlar" listesi düşünün: hesaplanması pahalı (birden çok tabloyu birleştiren, saniyeler süren bir sorgu), çok okunuyor ve tek bir cache anahtarında tutuluyor. TTL doldu diyelim. O milisaniyede gelen 800 eşzamanlı istek aynı anda cache miss alır ve **hepsi birden** o pahalı sorguyu veritabanına gönderir. Cache tam da yükü emmesi gereken anda veritabanını çökertir. Buna **cache stampede** (thundering herd) denir.

### Naif hali (stampede'e açık)

```python
def get_featured():
    key = "home:featured"
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)
    # 800 istek AYNI ANDA buraya düşer
    data = expensive_featured_query()   # ~2 saniye, DB'yi ezer
    r.set(key, json.dumps(data), ex=60)
    return data
```

### Çözüm: tek-uçuş kilidi (single-flight) + stale-while-revalidate

Fikir iki katmanlı: (1) sadece **bir** istek yeniden hesaplasın, diğerleri beklesin veya eski değeri görsün; (2) değeri "yumuşak" bir son kullanma zamanıyla (soft TTL) sarıp, süre dolduğunda eskisini sunmaya devam ederken arka planda bir tek istek yenilesin.

```python
import json, time, redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

SOFT_TTL = 60      # bu süreden sonra "bayat ama sunulabilir"
HARD_TTL = 600     # bu süreden sonra girdi tamamen yok
LOCK_TTL = 10      # yeniden hesaplama kilidinin ömrü

def get_featured():
    key = "home:featured"
    raw = r.get(key)

    if raw is not None:
        entry = json.loads(raw)
        # Henüz taze mi?
        if time.time() < entry["soft_expire"]:
            return entry["data"]
        # Bayat: yenilemeyi TEK bir istek üstlensin, gerisi eskiyi görsün
        if _try_acquire_lock(key):
            try:
                fresh = expensive_featured_query()
                _store(key, fresh)
                return fresh
            finally:
                r.delete(f"lock:{key}")
        # Kilidi alamayan istekler bayat veriyi döner (stale-while-revalidate)
        return entry["data"]

    # Hiç yoksa (cold start): kilitle, tek istek doldursun
    if _try_acquire_lock(key):
        try:
            fresh = expensive_featured_query()
            _store(key, fresh)
            return fresh
        finally:
            r.delete(f"lock:{key}")
    else:
        # Başka biri dolduruyor; kısa bekleyip cache'i tekrar dene
        time.sleep(0.05)
        raw = r.get(key)
        return json.loads(raw)["data"] if raw else expensive_featured_query()

def _try_acquire_lock(key):
    # SET NX EX: atomik kilit; sadece bir istek True alır
    return bool(r.set(f"lock:{key}", "1", nx=True, ex=LOCK_TTL))

def _store(key, data):
    entry = {"data": data, "soft_expire": time.time() + SOFT_TTL}
    r.set(key, json.dumps(entry), ex=HARD_TTL)
```

Bu mimaride:

- **Soft/Hard TTL ayrımı:** Girdi soft_expire'ı geçtiğinde silinmez; hâlâ orada ve sunulabilir. Sadece "yenilenmeli" işareti taşır. Girdi ancak hard TTL'de (Redis'in gerçek `ex`'i) fiziksel olarak silinir.
- **`SET NX EX` kilidi:** Redis'te atomik olduğu için, 800 istekten yalnızca biri kilidi alır ve pahalı sorguyu çalıştırır. Diğerleri saniyenin binde biri kadar bile beklemeden bayat veriyle yanıtlanır. Kullanıcı deneyimi bozulmaz, veritabanı yükü 800x'ten 1x'e iner.
- **Kilit TTL'i (LOCK_TTL):** Kilidi tutan istek çökerse kilit sonsuza kadar kalmasın diye kilidin de bir son kullanma süresi vardır. Bu **çok önemli**: TTL'siz kilit, bir crash sonrası tüm anahtarı kalıcı olarak "yenilenemez" hale getirir.

### Ek koruma: jitter

Eğer sistem açılışında yüzlerce anahtarı toplu ısıtırsanız (cache warming), hepsine aynı `HARD_TTL`'i verirseniz hepsi aynı saniyede expire olup senkronize bir stampede yaratır. Çözüm, her TTL'e küçük rastgele bir sapma eklemektir:

```python
import random
def jittered(ttl):
    return ttl + random.randint(-ttl // 10, ttl // 10)  # ±%10
r.set(key, json.dumps(entry), ex=jittered(HARD_TTL))
```

Böylece sona ermeler zamana yayılır ve eşzamanlı çöküş dalgası oluşmaz.

### Kilit tutarken dikkat: kilit sızıntısı ve "herd of two"

Yukarıdaki `_try_acquire_lock` / `r.delete(f"lock:{key}")` çiftinde ince bir tehlike gizlidir. Kilidi alan istek, `LOCK_TTL` süresini aşan bir yeniden hesaplama yaparsa (ör. veritabanı o an yavaşladı ve sorgu 12 saniye sürdü), kilit 10 saniyede kendiliğinden expire olur. Bu sırada ikinci bir istek gelir, kilidi *taze* alır ve kendi hesaplamasına başlar. Şimdi iki istek aynı anda pahalı sorguyu çalıştırıyordur — stampede'i tam çözemediniz, sadece küçülttünüz. Daha kötüsü: yavaş kalan ilk istek sonunda bitip `r.delete(f"lock:{key}")` çağırdığında, artık **ikinci isteğe ait** kilidi siler. Bu, dağıtık kilitlerde klasik bir "başkasının kilidini açma" hatasıdır.

Doğru düzeltme, kilidi alırken benzersiz bir jeton (token) yazmak ve silerken yalnızca jeton hâlâ *senin* jetonunsa silmektir; bu kontrolü atomik yapmak için Redis'te Lua script kullanılır:

```python
import uuid

RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

def acquire_lock(key):
    token = uuid.uuid4().hex
    ok = r.set(f"lock:{key}", token, nx=True, ex=LOCK_TTL)
    return token if ok else None

def release_lock(key, token):
    # Sadece kilit hâlâ bizimse sil (compare-and-delete, atomik)
    r.eval(RELEASE_SCRIPT, 1, f"lock:{key}", token)
```

Buradaki ders geneldir: dağıtık kilitler "al ve unut" değildir. Kilit ömrünü hesaplamanın en kötü durum süresinden uzun tutmak, ve silmeyi sahiplik kontrolüyle korumak zorunludur. Aksi halde stampede çözümünüz, kendisi yeni bir yarış koşulu kaynağı olur.

---

## 3. Karşılaştırma / karar: Hangi yazma deseni, ne zaman?

Yazma deseni seçimi, caching'in en çok yanlış yapılan karar noktasıdır çünkü çoğu ekip tek bir deseni tüm sisteme dayatır. Doğru yaklaşım veri bazında seçmektir. İşte takaslar.

### Cache-aside (lazy loading) + invalidate

- **Tutarlılık:** Orta. Yazmada silme + TTL ile yönetilir; yukarıdaki race'lere karşı dikkat gerektirir.
- **Dayanıklılık:** Yüksek. Gerçeğin kaynağı hep veritabanı; cache çökse veri kaybolmaz.
- **Gecikme:** Okumada ilk istek yavaş (miss cezası), sonrası hızlı.
- **Ne zaman:** Varsayılan seçim. Okuma ağırlıklı, cache'in çökmesine dayanıklı olması gereken çoğu web servisi için. Cache ile DB decoupled olduğu için en dayanıklı desen.

### Write-through

- **Tutarlılık:** Yüksek. Yazma hem cache'e hem DB'ye senkron gider; read-after-write hep taze.
- **Dayanıklılık:** Yüksek. DB senkron yazıldığı için veri kaybı yok.
- **Gecikme:** Yazma yavaş — her yazma iki depoyu birden bekler.
- **Ne zaman:** Yazılan verinin hemen ardından okunması çok olası olduğunda (ör. kullanıcı profilini güncelleyip aynı sayfada gösterme). Çok yazılıp az okunan veride cache'i boşuna doldurur.

### Write-behind (write-back)

- **Tutarlılık:** Zayıf/eventual. DB bir süre eskiyi gösterir.
- **Dayanıklılık:** RİSKLİ. Cache (bellek) çökerse, DB'ye henüz yazılmamış yazmalar **kalıcı kaybolur** — kuyruk kalıcı değilse.
- **Gecikme:** Yazma çok hızlı (hemen döner), DB yükü batch ile düşer.
- **Ne zaman:** Çok yüksek yazma hacmi + gecikmenin kritik olduğu + bir miktar veri kaybının tolere edilebildiği durumlar (ör. görüntülenme sayaçları, analitik olayları, "beğeni" sayıları). Finansal bakiye gibi kritik yazmalarda kuyruğu kalıcılaştırmadan asla kullanılmaz.

### Write-around

- **Tutarlılık:** İyi (cache atlandığı için yazmada tutarsızlık üretmez).
- **Gecikme:** İlk okuma hep miss.
- **Ne zaman:** Bir kez yazılıp nadiren okunan veri (ör. log kayıtları, arşiv). Cache'i "bir daha okunmayacak" veriyle kirletmemek için.

### Karar özeti

| Veri örneği | Önerilen | Neden |
|---|---|---|
| Hesap bakiyesi | Write-through veya kısa TTL cache-aside | Tutarlılık ve dayanıklılık kritik, bayatlık kabul edilemez |
| Ürün fiyatı | Cache-aside + delete + kısa TTL | Okuma ağırlıklı, kısa bayatlık tolere edilebilir |
| Profil fotoğrafı URL'i | Cache-aside + uzun TTL | Nadiren değişir, uzun bayatlık sorun değil |
| Görüntülenme sayacı | Write-behind (kalıcı kuyrukla) | Çok yazma, yüksek gecikme kabul edilemez, minik kayıp tolere edilir |
| Arama/öneri sonucu | Read-through + stale-while-revalidate | Pahalı hesaplama, bayatlık göze alınır |

Altın kural: **Tek strateji tüm sisteme dayatılmaz.** Her veri kümesi için "ne kadar bayatlığa razıyım, veri kaybını tolere eder miyim, okuma/yazma oranı ne" sorularını ayrı ayrı cevaplayıp seçim yapılır.

### Bir ek karar: `DELETE` mi `UPDATE` mi?

Cache-aside'da yazma anında girdiyi güncellemek yerine silmek neredeyse her zaman doğrudur (Bölüm 1'deki write-write race). Tek istisna: girdiyi hesaplamak çok pahalıysa ve güncelleme değeri elinizde hazırsa, atomik bir compare-and-set (ör. Lua script veya versiyon damgası) ile güncellemeyi düşünebilirsiniz — ama bu, karmaşıklığı ciddi biçimde artırır ve çoğu ekip için gereksizdir.

---

## 4. Hata-modu kataloğu

Aşağıda caching'te sık gördüğüm 12 tipik hata, her biri kısa açıklamasıyla. Bunların çoğu üretimde, gerçek trafik altında ortaya çıkar; testte görünmezler.

1. **Cache'i silmek yerine güncellemek.** Eşzamanlı iki yazma birbirinin üzerine yazarak cache ile DB'yi kalıcı ayrıştırır. Silme, "bilmiyorum, yeniden öğren" der ve güvenlidir.

2. **Yazma sırasını ters kurmak (önce cache, sonra DB).** DB yazması başarısız olursa cache taze, DB eski kalır. Her zaman önce gerçeğin kaynağına (DB) yaz, sonra cache'i geçersiz kıl.

3. **TTL koymamak.** Invalidation mantığındaki her hata TTL olmadan kalıcılaşır. TTL, tutarlılık hatalarına karşı son savunma hattıdır; en azından güvenli bir üst sınır koyun.

4. **Cache stampede'i öngörmemek.** Popüler bir anahtarın TTL'i dolduğu an yüzlerce istek aynı anda DB'ye yüklenir. Single-flight kilidi, early recompute veya stale-while-revalidate ile baştan tasarlanmalıdır.

5. **Senkronize sona erme (jitter yokluğu).** Toplu ısıtılan anahtarlar aynı saniyede expire olup senkronize stampede yaratır. TTL'lere ±%10 rastgele sapma ekleyin.

6. **Kilide TTL koymamak.** Stampede kilidini alan istek çökerse, TTL'siz kilit anahtarı sonsuza dek "yenilenemez" bırakır. Dağıtık kilitlerin mutlaka son kullanma süresi olmalı.

7. **Negatif sonucu cache'lememek (cache penetration).** "Kayıt yok" cevabını cache'lemezseniz, var olmayan bir anahtarı arayan her istek DB'ye düşer; kötü niyetli trafik bunu bir aşınma yüzeyine çevirir. Null sonuçları kısa TTL ile cache'leyin.

8. **Her şeyi cache'lemek.** Nadiren okunan ya da sürekli değişen veriyi cache'lemek belleği harcar, hit oranını düşürür ve invalidation yükünü artırır. Cache yalnızca yüksek okuma/yazma oranlı ve pahalı veriler için kazançlıdır.

9. **Cache'i zorunlu bileşen sanmak (gizli SPOF).** Sistem cache olmadan ayakta kalamıyorsa, cache çöktüğünde tüm yük DB'ye biner ve cache aslında bir single point of failure'a dönüşür. "Cache'siz de ayakta kalır mıyım?" sorusu ciddiye alınmalı.

10. **Cache anahtarı tasarımını ihmal etmek.** Dil, sürüm, kullanıcı bağlamı veya kiracı (tenant) bilgisini anahtara katmamak, yanlış kullanıcıya yanlış veri sunma gibi ciddi güvenlik/doğruluk hataları doğurur. Anahtar şeması cache'in sözleşmesidir.

11. **Bağımlılık grafiğini kaçırmak.** Bir ürünün fiyatı değişince yalnız `product:42`'yi değil, o ürünü içeren kategori listesi, arama sonucu ve öneri cache'lerini de bayatlatmak gerekir. Kaçırılan bağımlılıklar sessiz bayat veri üretir.

12. **Çok katmanlı cache'te invalidation'ı tüm katmanlara yaymamak.** Distributed cache'ten sildiğiniz girdi, başka bir uygulama örneğinin in-process cache'inde hâlâ yaşıyor olabilir. Invalidation olayı her katmana (ve CDN varsa oraya da) yayılmalı; yoksa üst katman alt katmanı sürekli eski veriyle kirletir.

### Bonus: gözden kaçan iki hata

13. **Serialization maliyetini unutmak.** Dağıtık cache'te her okuma/yazma bir serialize/deserialize'dır. Çok büyük nesneleri cache'lemek, DB'den kazandığınız süreyi serialization'da geri kaybettirir; büyük nesneleri parçalayın ya da cache'lemeyin.

14. **Cache miss cezasını ölçmemek.** Cold start veya cache flush anında sistemin DB'ye bindirdiği ani yükü test etmezseniz, ilk büyük trafik zirvesinde öğrenirsiniz. Hit oranı, gecikme dağılımı ve DB'ye inen yük düzenli izlenmelidir — cache "kurulup unutulan" değil, sürekli gözlenen bir bileşendir.

---

## Kapanış

Caching özünde bir **takas mühendisliğidir**: hız karşılığında tutarlılık, basitlik karşılığında bellek, tazelik karşılığında yük dengesi. Bu derin dalışta gördük ki hataların büyük çoğunluğu doldurma tarafında değil, **geçersiz kılma ve sıralama** tarafında yatıyor: yanlış yazma sırası, silme yerine güncelleme, TTL'siz kilitler, jitter'sız toplu expire. Doğru mühendislik refleksi "cache ekleyeyim de hızlansın" değil; "hangi veriyi, hangi katmanda, ne kadar bayatlıkla, hangi yazma desenıyle ve nasıl geçersiz kılarak cache'leyeceğim" sorusunu her seferinde bilinçli cevaplamaktır. Kod düzeyinde bu; `SET NX EX` ile atomik kilitler, önce-DB-sonra-delete sırası, soft/hard TTL ayrımı ve stale-while-revalidate gibi somut tekniklere dönüşür. Cache'in zor kısmı onu doldurmak değil, ne zaman ve nasıl boşaltacağını doğru bilmektir.
