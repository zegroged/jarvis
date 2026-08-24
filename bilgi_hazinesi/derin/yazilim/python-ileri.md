# Python İleri Seviye — Derin Dalış: Eşzamanlılık, Bellek ve Üretimde Kırılan Yerler

Bu metin bir özet değil, bir kazı çalışmasıdır. Amacı, "async yaz, GIL var, generator kullan" düzeyindeki söylemleri bir kenara bırakıp gerçek bir sistemin nerede, neden ve nasıl kırıldığını satır satır göstermektir. Her bölüm gerçek, çalışır kod üzerinden ilerler; önce hatalı hâli görürsünüz, sonra hatanın kök nedenini, sonra düzeltilmişini. Sonunda bir gerçek vaka, bir karar tablosu ve saha deneyiminden derlenmiş bir hata-modu kataloğu var.

---

## 1. Çözümlü yürüyüş: `asyncio` içinde sessizce yutulan `CancelledError`

Gerçekçi bir senaryo alalım. Bir API gateway yazıyorsunuz. Gelen her istek için birden fazla downstream servise paralel çağrı atıyor, ilk başarılı yanıtı dönüyorsunuz ("hedging" deseni). Timeout aşılırsa işi iptal ediyorsunuz. Aşağıdaki kod ilk bakışta doğru görünür ve testlerde de geçer — ama üretimde bağlantı sızdırır ve arada bir yanlış sonuç döner.

### Zafiyetli/hatalı kod

```python
import asyncio
import aiohttp

class DownstreamClient:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def cagir(self, url):
        # Her çağrı bir bağlantı açar
        async with self.session.get(url) as resp:
            data = await resp.json()
            return data

    async def temizle(self):
        # Kritik: iş bitince çağrılması beklenen temizlik
        await self.kaynagi_serbest_birak()

    async def kaynagi_serbest_birak(self):
        await asyncio.sleep(0.1)  # bir kilidi bırakmayı temsil ediyor
        print("kaynak serbest bırakıldı")

async def islem(client, url):
    try:
        sonuc = await client.cagir(url)
        return sonuc
    except Exception as e:          # HATA BURADA
        print(f"hata yutuldu: {e}")
        return None
    finally:
        await client.temizle()      # HATA BURADA DA VAR

async def main():
    client = DownstreamClient()
    # 2 saniyelik timeout ile çalıştır
    try:
        sonuc = await asyncio.wait_for(
            islem(client, "http://yavas-servis/veri"), timeout=2.0
        )
    except asyncio.TimeoutError:
        print("zaman aşımı")
    await client.session.close()
```

### Sorun neden oluşuyor?

İki ayrı kök neden var, ikisi de `asyncio`'nun iptal (cancellation) semantiğinden kaynaklanıyor.

**Birincisi: `except Exception` iptali yutar.** `asyncio.wait_for` timeout'a uğradığında, sarmaladığı coroutine'e `asyncio.CancelledError` gönderir. Python 3.8'e kadar `CancelledError`, `Exception`'ın alt sınıfıydı; 3.8 ve sonrasında `BaseException`'a taşındı — tam da bu tür yanlış yutmaları engellemek için. Ancak eski koddaki `except Exception` alışkanlığı hâlâ her yerde. Eğer bu kod eski davranışa göre yazılmışsa ya da siz bilinçsizce `except BaseException` yazarsanız, `CancelledError` yakalanır, `return None` çalışır ve iptal edilmesi gereken görev **iptal edildiğini bilmeden normal bir sonuç dönmüş gibi davranır**. Çağıran taraf `TimeoutError` beklerken `None` alır; iptal zinciri kırılır.

**İkincisi: `finally` içinde `await` yapmak, iptal sırasında ikinci bir iptale açıktır.** Timeout sonrası `finally` bloğundaki `await client.temizle()` çalışmaya başlar. Ama bu görev zaten iptal ediliyor durumundadır; event loop `temizle()` içindeki ilk `await` noktasında ona tekrar `CancelledError` fırlatabilir. Sonuç: temizlik yarıda kalır, `kaynagi_serbest_birak` içindeki kilit hiç bırakılmaz. Bu, yavaş büyüyen bir kaynak sızıntısıdır — testlerde asla görünmez çünkü test timeout'a girmez.

### Düzeltilmiş/doğru kod

```python
import asyncio
import aiohttp

class DownstreamClient:
    def __init__(self, session):
        self.session = session       # session'ı dışarıdan al (sahiplik netleşsin)

    async def cagir(self, url):
        async with self.session.get(url) as resp:
            return await resp.json()

    async def temizle(self):
        # Temizliği iptalden koru: shield ile sarmala
        await asyncio.shield(self.kaynagi_serbest_birak())

    async def kaynagi_serbest_birak(self):
        await asyncio.sleep(0.1)
        print("kaynak serbest bırakıldı")

async def islem(client, url):
    try:
        return await client.cagir(url)
    except asyncio.CancelledError:
        # İptali ASLA yutma; temizle ve yeniden fırlat
        raise
    except aiohttp.ClientError as e:      # yalnızca beklenen hataları yakala
        print(f"downstream hatası: {e}")
        return None
    finally:
        # finally içinde await ederken iptalden korumak istiyorsak shield
        try:
            await client.temizle()
        except asyncio.CancelledError:
            # Temizlik yine iptal edilirse en azından kaydını tut
            print("temizlik iptal edildi, kaynak durumu belirsiz")
            raise

async def main():
    async with aiohttp.ClientSession() as session:   # yaşam döngüsü net
        client = DownstreamClient(session)
        try:
            sonuc = await asyncio.wait_for(
                islem(client, "http://yavas-servis/veri"), timeout=2.0
            )
            print(sonuc)
        except asyncio.TimeoutError:
            print("zaman aşımı — iptal doğru şekilde yayıldı")

asyncio.run(main())
```

Kritik değişiklikler: (1) `except Exception` yerine dar `except aiohttp.ClientError`; iptal artık yutulmaz. (2) `CancelledError` açıkça yakalanıp `raise` ile yeniden fırlatılır, böylece iptal zinciri bozulmaz. (3) Temizlik `asyncio.shield` ile iptalden korunur — böylece timeout, temizlik başladıktan sonra onu yarıda kesmez. (4) `session` yaşam döngüsü `async with` ile netleşir; sahibi kim olduğu belirsiz bir `session` sızıntının en yaygın kaynağıdır.

Python 3.11 ile gelen `asyncio.timeout()` context manager'ı bu deseni daha güvenli kılar çünkü iptal noktalarını daha öngörülebilir yönetir; yeni kodda `wait_for` yerine onu tercih edin. Ayrıca 3.11'in `TaskGroup`'u, bir görev başarısız olduğunda kardeşlerini otomatik iptal eder ve `ExceptionGroup` ile toplu hata verir — hedging/fan-out desenlerinde elle iptal yönetiminden çok daha güvenlidir.

### İkinci bir katman: `gather` içinde yutulan istisna ve sızan görevler

Aynı gateway'de sık görülen ikinci bir hata, `asyncio.gather` semantiğini yanlış anlamaktır. Varsayılan olarak `gather`, ilk görev istisna fırlattığında o istisnayı hemen çağırana yayar — ama **diğer görevleri iptal etmez**; onlar arka planda çalışmaya devam eder ve sonuçları/hataları sessizce kaybolur.

```python
async def gather_ile_hata():
    async def basarisiz():
        await asyncio.sleep(0.1)
        raise ValueError("downstream çöktü")

    async def uzun_is():
        await asyncio.sleep(5)      # gather döndükten sonra da çalışmaya devam eder
        print("uzun iş bitti — ama kimse dinlemiyor")

    # basarisiz() 0.1s'de fırlar; gather hemen döner ama uzun_is() İPTAL EDİLMEZ
    await asyncio.gather(basarisiz(), uzun_is())
```

Burada `ValueError` çağırana ulaşır, fakat `uzun_is` görevi hâlâ event loop'ta asılı kalır; 5 saniye sonra "kimse dinlemiyor" yazar, kaynaklarını tutmaya devam eder ve bu bir sızıntıdır. Doğru davranış için ya `TaskGroup` (bir görev patlayınca kardeşleri otomatik iptal eder) ya da `gather(..., return_exceptions=True)` ile tüm sonuçları toplayıp elle ayıklamak gerekir. `return_exceptions=True` seçtiğinizde ise ters tuzağa dikkat: istisnalar artık fırlamaz, dönen listede *değer* olarak gelir; bunları döngüyle kontrol etmezseniz hatayı büsbütün gözden kaçırırsınız. Yani her iki uçta da sessiz hata riski vardır — semantiği bilerek seçmek zorundasınız.

---

## 2. Gerçek sistem örneği: Bir arka plan worker'ında GIL, süreç havuzu ve pickle duvarı

Diyelim ki bir görüntü işleme servisi işletiyorsunuz. Kullanıcılar dosya yüklüyor, siz her dosya için (a) CPU-yoğun bir dönüşüm (yeniden boyutlandırma + filtre) ve (b) I/O-yoğun bir işlem (S3'e yükleme, DB'ye kayıt) yapıyorsunuz. İlk sürüm her şeyi `ThreadPoolExecutor` ile yaptı ve yük altında CPU'yu tam kullanamadı. Kök neden GIL.

### Naif (yavaş) mimari

```python
from concurrent.futures import ThreadPoolExecutor
import hashlib

def agir_donusum(goruntu_baytlari):
    # Saf-Python CPU-bound iş: GIL yüzünden thread'ler seri ilerler
    sonuc = goruntu_baytlari
    for _ in range(200):
        sonuc = hashlib.sha256(sonuc).digest()  # pahalı döngüyü temsil ediyor
    return sonuc

def isle_hepsini(dosyalar):
    with ThreadPoolExecutor(max_workers=8) as ex:
        # 8 worker ama GIL yüzünden aynı anda tek çekirdek çalışır
        return list(ex.map(agir_donusum, dosyalar))
```

8 çekirdekli makinede bile bu, tek çekirdek performansına yakın kalır çünkü `agir_donusum` sürekli Python bytecode çalıştırır ve GIL'i bırakmaz. (Not: `hashlib` çağrılarının bir kısmı GIL'i bırakır; burada saf-Python CPU-bound iş için bir yer tutucu olarak kullanılıyor — asıl derdimiz mimari.)

### Doğru mimari: CPU işi süreçlere, I/O işi async'e

Doğru bölünme "her işi paralelleştir" değil, **işin doğasına göre farklı araç** kullanmaktır. CPU-bound dönüşümü `ProcessPoolExecutor`'a, I/O-bound yüklemeyi `asyncio`'ya veriyoruz.

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
import hashlib

# --- CPU tarafı: ayrı süreçlerde, gerçek paralellik ---
def agir_donusum(goruntu_baytlari: bytes) -> bytes:
    sonuc = goruntu_baytlari
    for _ in range(200):
        sonuc = hashlib.sha256(sonuc).digest()
    return sonuc

# --- I/O tarafı: async ---
async def yukle_s3(baytlar: bytes) -> str:
    await asyncio.sleep(0.2)          # ağ yüklemesini temsil ediyor
    return f"s3://bucket/{len(baytlar)}"

async def isle_bir_dosya(loop, havuz, baytlar):
    # CPU işini süreç havuzuna at; event loop bu sırada bloke OLMAZ
    donusmus = await loop.run_in_executor(havuz, agir_donusum, baytlar)
    # I/O işini async yap
    url = await yukle_s3(donusmus)
    return url

async def main(dosyalar):
    loop = asyncio.get_running_loop()
    # Süreç havuzunu bir kez oluştur, tüm işlerde paylaş
    with ProcessPoolExecutor(max_workers=8) as havuz:
        gorevler = [isle_bir_dosya(loop, havuz, d) for d in dosyalar]
        return await asyncio.gather(*gorevler)

if __name__ == "__main__":       # Windows/macOS spawn için ZORUNLU
    dosyalar = [f"dosya-{i}".encode() * 1000 for i in range(16)]
    print(asyncio.run(main(dosyalar)))
```

Bu mimarinin sağladığı: CPU dönüşümleri 8 çekirdekte gerçekten paralel akar (her sürecin kendi GIL'i vardır), yükleme beklemeleri tek thread'te async olarak örtüşür, ve event loop hiçbir zaman CPU işi yüzünden kilitlenmez çünkü ağır iş `run_in_executor` ile havuza gider.

Ama bedava değil. **Pickle duvarı:** `ProcessPoolExecutor`, argümanları ve dönüş değerlerini süreçler arası taşımak için `pickle` ile serileştirir. Bunun üç sonucu var:

1. Argüman ve sonuçlar picklable olmalı. Bir lambda, bir açık dosya tanıtıcısı, bir DB bağlantısı, bir `aiohttp.ClientSession` gönderemezsiniz — `PicklingError` alırsınız. Gerçek görüntü verisi (bytes) sorunsuzdur; ama "şu bağlantıyı da worker'a geçireyim" dediğiniz an duvara toslarsınız.
2. Büyük veriyi serileştirme maliyeti ciddidir. 50 MB'lık bir görüntüyü sürece gönderip geri almak, hesabın kendisinden pahalı olabilir. Bu durumda veriyi paylaşımlı bellek (`multiprocessing.shared_memory`) ile taşımak ya da işi süreç içinde diskten okumak gerekir.
3. `spawn` başlangıç yöntemi (Windows ve macOS'ta Python 3.8+ varsayılanı olan macOS dahil) alt süreçte modülü baştan import eder. Bu yüzden `ProcessPoolExecutor` kullanan kod **mutlaka** `if __name__ == "__main__":` koruması altında olmalıdır; aksi halde alt süreç ana modülü tekrar çalıştırıp havuzu tekrar kurmaya çalışır ve süreç sonsuz çoğalır (fork bomb benzeri davranış).

Buradaki mühendislik dersi: paralellik bedava değildir; GIL'i aştığınız her yerde onun yerine **serileştirme ve süreç başlatma maliyeti** geçer. Karar, "GIL kötü, süreç iyi" değil, iş yükünüzün CPU/veri oranını ölçüp doğru sınırı çizmektir.

---

## 3. Karşılaştırma / karar: `threading` mi, `asyncio` mı, `multiprocessing` mi?

Bu üç modelin seçimi ileri Python'un en çok yanlış yapılan kararıdır. Aşağıda takaslarıyla birlikte.

### threading
- **Ne zaman:** I/O-bound iş, orta sayıda eşzamanlılık (onlarca–yüzlerce), ve bloke edici (senkron) kütüphaneler kullanmak zorunda olduğunuzda. Örn. senkron bir DB sürücüsü ya da `requests` etrafında paralellik istiyorsanız.
- **Takas:** GIL yüzünden CPU-bound işte hızlanma yok. Preemptive geçiş nedeniyle race condition riski yüksek; kilit (lock) yönetimi zorunlu ve deadlock kapısı açık. Her thread bir OS thread'i olduğundan on binlerce bağlantıya ölçeklenmez (thread başına ~MB'lik stack).
- **Gizli avantaj:** Mevcut senkron kod tabanını async'e çevirmeden paralelleştirmenin en ucuz yolu. Kodu yeniden yazmadan `ThreadPoolExecutor` sarmak çoğu zaman yeterlidir.

### asyncio
- **Ne zaman:** Yüksek eşzamanlılıklı I/O-bound iş (binlerce–on binlerce eşzamanlı bağlantı): web sunucuları, proxy'ler, WebSocket, çok sayıda downstream'e fan-out.
- **Takas:** Tüm yığın async olmak zorunda ("renk problemi" — async fonksiyon yalnızca async'ten çağrılır). Tek bir senkron bloke çağrı (bir `time.sleep`, bir senkron DB sorgusu) tüm event loop'u dondurur. CPU-bound işte tamamen faydasız — paralellik sağlamaz. Hata ayıklaması thread'den daha kavramsaldır: stack trace'ler coroutine sınırlarında kopar.
- **Gizli avantaj:** İşbirlikçi (cooperative) geçiş, yalnızca `await` noktalarında olduğundan iki `await` arasındaki kod atomiktir; bu, birçok race condition'ı kilitsiz elimine eder.

### multiprocessing / ProcessPoolExecutor
- **Ne zaman:** Gerçek CPU-bound paralellik: sayısal hesap, saf-Python veri işleme, kriptografi, sıkıştırma.
- **Takas:** Süreçler arası her şey pickle ile taşınır (yukarıdaki duvar). Süreç başlatma pahalı; kısa görevler için başlatma maliyeti işin kendisini gölgeler. Paylaşımlı durum zordur (shared memory / manager gerekir). Bellek ayak izi yüksek (her süreç kendi yorumlayıcısı).
- **Gizli avantaj:** GIL tamamen ortadan kalkar; N çekirdekte gerçek N kat.

### Somut ölçüm: aynı işin üç modeldeki davranışı

Karar sezgisel değil, ölçülerek verilmelidir. Aşağıdaki iskelet, saf-Python CPU-bound bir işi üç modelde de çalıştırıp süreyi karşılaştırmanın doğru yolunu gösterir:

```python
import time, threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

def cpu_is(n):
    s = 0
    for i in range(n):
        s += i * i        # saf-Python CPU-bound döngü
    return s

def olc(etiket, fn):
    t = time.perf_counter()
    fn()
    print(f"{etiket}: {time.perf_counter() - t:.2f}s")

N = 20_000_000
isler = [N] * 4

if __name__ == "__main__":
    olc("seri",     lambda: [cpu_is(n) for n in isler])
    olc("thread",   lambda: list(ThreadPoolExecutor(4).map(cpu_is, isler)))
    olc("process",  lambda: list(ProcessPoolExecutor(4).map(cpu_is, isler)))
```

Çok çekirdekli bir makinede beklenen sonuç şudur: **seri** ve **thread** neredeyse aynı süreyi verir (GIL yüzünden thread'ler seri akar, hatta kilit devriyle biraz daha yavaş olabilir), **process** ise çekirdek sayısına yakın oranda hızlanır. Bu üç satırlık deney, "thread ekleyince neden hızlanmadı?" sorusunun cevabını gözle görülür kılar. Aynı işi NumPy vektör işlemiyle yapsaydınız thread de hızlanırdı, çünkü hesap C katmanında GIL bırakılarak yapılır — bu yüzden "önce iş gerçekten saf Python mı?" sorusu kritiktir.

### Karar kuralı
Önce işi ölçün, sonra sınıflandırın:
- **Zamanın çoğu beklemekle mi geçiyor?** → I/O-bound. Çok yüksek eşzamanlılık ve yeni kod → `asyncio`. Mevcut senkron kod ya da orta eşzamanlılık → `threading`.
- **Zamanın çoğu hesaplamada mı geçiyor?** → CPU-bound → `multiprocessing`. Ama önce şunu sorun: hesap gerçekten saf Python'da mı? NumPy/Pandas/PyTorch gibi kütüphaneler ağır işi C/BLAS katmanında yapar ve o sırada GIL'i bırakır — bu durumda thread'ler bile ölçeklenebilir ve süreç havuzuna hiç ihtiyacınız olmaz.
- **Karışık mı?** → Bölün: CPU parçası süreç havuzuna, I/O parçası async'e (Bölüm 2'deki desen). Tek bir modelle her şeyi çözmeye çalışmak en yaygın hatadır.

Serbest-thread'li (free-threaded, "no-GIL") CPython üzerinde deneysel çalışmalar sürüyor; bu yön CPU-bound thread'lemeyi mümkün kılabilir ama davranışı ve C-uzantı uyumluluğu sürümler arasında değişir. Üretim kararı vermeden önce kullandığınız tam sürümün resmî belgesini doğrulayın; burada kesin bayrak/sürüm numarası ezberlemek risklidir çünkü hızla değişiyor.

---

## 4. Hata-modu kataloğu: İleri Python'da tekrar tekrar yapılan hatalar

Aşağıdakiler saha deneyiminde sürekli tekrar eden, çoğu "sessiz" (istisna fırlatmadan yanlış davranan) hatalardır.

1. **Değişmez varsayılan argüman.** `def f(x, kutu=[])` — varsayılan liste fonksiyon *tanımlanırken bir kez* oluşur ve tüm çağrılar arasında paylaşılır; birikimli, gizemli hatalar verir. Doğrusu `kutu=None` verip gövdede `if kutu is None: kutu = []`.

2. **Geç bağlanan kapanış (late binding closure).** `[lambda: i for i in range(3)]` üç fonksiyonun hepsi son `i` değerini (2) görür çünkü kapanış değeri değil değişkenin *kendisini* yakalar. Çözüm: `lambda i=i: i` ile o anki değeri sabitlemek.

3. **`except Exception` ile `CancelledError` / `KeyboardInterrupt` yutmak.** Geniş yakalama, iptal ve kesme sinyallerini yutarak async görevlerin iptalini ve Ctrl+C'yi kırar. Yalnızca beklediğiniz istisnayı yakalayın; iptali gördüyseniz `raise` ile yeniden fırlatın.

4. **async içinde bloke edici çağrı.** `time.sleep`, senkron `requests.get`, ağır saf-Python döngüsü event loop'u dondurur; o an *tüm* coroutine'ler durur. Bloke işi `run_in_executor`'a atın ya da async uyumlu kütüphane (`asyncio.sleep`, `aiohttp`) kullanın.

5. **Coroutine'i await etmemek / oluşturup bırakmak.** `f()` yazıp `await` etmezseniz iş hiç çalışmaz ("coroutine was never awaited"). `asyncio.create_task(f())` ile başlatıp referansını tutmazsanız görev çöp toplayıcıyla sessizce iptal edilebilir — task referanslarını bir kümede saklayın.

6. **`ProcessPoolExecutor`'ı `if __name__ == "__main__"` korumasız kullanmak.** `spawn` başlatmalı platformlarda (Windows, macOS) alt süreç ana modülü tekrar import edip havuzu tekrar kurar; süreçler kontrolsüz çoğalır. Ayrıca picklable olmayan argüman göndermek `PicklingError` verir.

7. **`is` ile değer karşılaştırmak.** `x is 256` bazen `True`, `x is 257` `False` — küçük tamsayı önbelleği bir uygulama ayrıntısıdır. `is` yalnızca `None`/`True`/`False` gibi singleton'lar içindir; değer için her zaman `==`.

8. **Generator'ı iki kez tüketmek.** İlk `for` tükettikten sonra ikincisi sessizce boş döner — hata değil, veri kaybı. Tekrar gerekiyorsa `list()`'e alın (bellek bedeliyle) ya da generator'ı yeniden üretin.

9. **`functools.wraps` unutmak.** Dekoratör sarmalayıcısı asıl fonksiyonun `__name__`, `__doc__`, tip ipuçlarını devralmaz; stack trace'ler, dokümantasyon araçları ve `inspect` tabanlı çerçeveler (örn. bazı web framework route çözücüleri) yanlış çalışır.

10. **Mutable nesneyi paylaşılan durumda kilitsiz güncellemek.** Thread'li ortamda bir `dict`/`list`/sayacı kilitsiz güncellemek race condition üretir. GIL bunu *çözmez*: GIL yalnızca tek bytecode'un atomikliğini garanti eder; `sayac += 1` üç ayrı bytecode'dur (oku, artır, yaz) ve arada thread değişebilir. Paylaşılan mutasyon için `threading.Lock` ya da atomik yapı kullanın.

11. **`copy.copy` ile derin kopya beklemek.** Shallow kopya iç içe nesneleri paylaşır; iç listeyi değiştirince "kopya" da değişir. Bağımsızlık gerekiyorsa `copy.deepcopy` (maliyeti ve döngüsel yapı davranışıyla) kullanın.

12. **`__del__` ve referans döngülerine güvenmek.** Döngüsel referanslar reference counting ile temizlenmez; cyclic GC'ye kalır ve zamanlaması belirsizdir. Kaynak temizliğini (dosya, soket, kilit) asla `__del__`'e bırakmayın; `with`/context manager (`contextlib.contextmanager` ya da `__enter__`/`__exit__`) kullanın. `__del__`'de istisna fırlatmak ayrıca sessizce yutulur.

13. **Güvenilmeyen veriyle `pickle.loads` / `yaml.load` / `eval`.** Üçü de keyfi kod çalıştırmaya (RCE) açılır: `pickle` deserialize sırasında nesne inşa ederken kod tetikler, güvensiz YAML yükleyici Python nesnesi kurabilir. Dış veri için `json` gibi data-only formatlar ve YAML'ın "safe" yükleyicisini kullanın.

14. **Kabuk komutuna string ile girdi geçmek.** `os.system("ping " + girdi)` command injection'dır; `;`, `|`, `&&` yorumlanır. `subprocess.run([...], shell=False)` ile argümanları liste olarak verin.

15. **Sırlar için `random`, parola karşılaştırmasında `==`.** `random` kriptografik olarak öngörülebilir; token/anahtar için `secrets` kullanın. Sabit-zamanlı olmayan `==` karşılaştırması timing attack'e açıktır; `secrets.compare_digest` kullanın. Parolayı hızlı hash (MD5/SHA-256 tek geçiş) ile değil, yavaş+tuzlu algoritmayla (bcrypt/scrypt/Argon2) saklayın.

---

## Kapanış

İleri seviye Python, daha çok sözdizimi bilmek değil; her özelliğin arkasındaki *maliyet ve garanti dengesini* görebilmektir. GIL bir kusur değil, referans sayımını basit tutmak için ödenmiş bir tasarım bedelidir — ve o bedelin sizi CPU-bound işte nerede durduracağını bilmek, doğru aracı seçmenizi sağlar. `asyncio`'nun iptal semantiği, süreç havuzunun pickle duvarı, kapanışların geç bağlanması — bunların hepsi "çalışıyor gibi görünen ama üretimde kırılan" sınıfındandır. Bir özelliği kullanırken kendinize sormanız gereken tek soru şudur: "Bunun kök nedeni ne ve hangi koşulda beni sessizce yanıltır?" Bu soruyu sorabilen geliştirici, kod yazan biri olmaktan çıkıp sistem tasarlayan biri olur.
