# Python İleri Seviye: GIL, Eşzamanlılık, Bellek Modeli ve Güvenli Kod

Bu makale, Python'u yüzeysel olarak bilen bir geliştiriciyi dilin altındaki mekanizmalara götürmeyi amaçlar. Odak noktamız yalnızca "nasıl yazılır" değil, "neden böyle çalışır" sorusudur. Çünkü ileri seviyenin sınırı, bir özelliği kullanabilmek değil; o özelliğin arkasındaki tasarım kararını ve onun getirdiği tuzakları görebilmektir.

## GIL (Global Interpreter Lock)

### Tanım

GIL, CPython yorumlayıcısında (Python'un referans ve en yaygın kullanılan uygulaması) bulunan global bir kilittir. Aynı anda yalnızca **tek bir thread**'in Python bytecode'unu çalıştırmasına izin verir. Yani sekiz çekirdekli bir makinede çalışan çok thread'li saf Python kodunuz, aynı anda tek bir çekirdek üzerinde ilerler.

### Kök neden: neden böyle bir kilit var?

GIL, dilin kötü tasarlanmış olmasından değil, CPython'un bellek yönetiminin tarihsel bir tercihinden doğar. CPython'da her nesnenin bir **reference count** (referans sayacı) vardır; nesneye kaç yerden erişildiğini tutar. Sayaç sıfıra düştüğünde nesne bellekten temizlenir. Bu sayaçlar her atama, her fonksiyon çağrısı, her liste ekleme işleminde artıp azalır.

Eğer iki thread aynı nesnenin sayacını aynı anda güncellerse, klasik bir **race condition** oluşur: iki thread sayacı okur, ikisi de aynı değeri görür, ikisi de bir artırır ve bir güncelleme kaybolur. Bu, sayacın yanlış değerde kalmasına, dolayısıyla ya hâlâ kullanılan bir nesnenin erkenden silinmesine (use-after-free) ya da hiç silinmeyen bir nesneye (memory leak) yol açar.

Bu sorunu çözmenin iki yolu vardır: ya her nesnenin sayacını ayrı ayrı kilitlemek (fine-grained locking) ya da tek bir büyük kilit koymak. Her nesneye ayrı kilit koymak, kilitlerin alınıp bırakılmasının maliyeti ve **deadlock** riski yüzünden tek-thread performansını ciddi biçimde düşürürdü. CPython, tarihsel olarak tek büyük kilidi seçti: basit, hızlı (tek-thread senaryosunda) ve C uzantılarının yazımını kolaylaştıran bir çözüm. GIL'in yaşamayı sürdürmesinin asıl nedeni budur; sayısız C uzantısı onun sağladığı garantilere dayanır.

### GIL'in ne zaman sorun olduğu, ne zaman olmadığı

Kritik ayrım **CPU-bound** ile **I/O-bound** iş yükleri arasındadır.

CPU-bound bir işte (büyük sayısal döngü, saf Python'da hash hesabı, görüntü işleme) thread'ler sürekli bytecode çalıştırmak ister ve GIL için sıraya girerler. Burada thread eklemek hızlanma getirmez, hatta kilit devri (context switching) yüzünden yavaşlama getirebilir.

I/O-bound bir işte (ağ isteği, disk okuma, veritabanı sorgusu) thread çoğu zaman bir sonucu bekler. CPython, bir thread bloke edici bir I/O çağrısına girdiğinde GIL'i **bırakır**. Böylece diğer thread'ler bu bekleme süresince çalışabilir. İşte bu yüzden `threading` modülü, ağ ağırlıklı programlarda gerçekten faydalıdır; yaygın "Python thread'leri işe yaramaz" söylemi, yalnızca CPU-bound durum için doğrudur.

### Doğru kullanım ve alternatifler

- **CPU-bound paralellik** için `multiprocessing` veya `concurrent.futures.ProcessPoolExecutor` kullanın. Ayrı süreçler ayrı yorumlayıcı örneklerine ve ayrı GIL'lere sahiptir; gerçekten paralel çalışırlar. Bedeli, süreçler arası veri aktarımının serileştirme (pickle) maliyetidir.
- **I/O-bound eşzamanlılık** için thread veya async/await yeterlidir.
- NumPy gibi kütüphaneler ağır hesabı C katmanında yapar ve o sırada GIL'i bırakır; bu yüzden vektörel işlemler thread'lerle bile ölçeklenebilir.

Ayrıca Python'un yakın dönem sürümlerinde, GIL'i isteğe bağlı olarak devre dışı bırakabilen deneysel bir "free-threaded" derleme yolu üzerinde çalışılmaktadır. Bu yön umut verici olsa da, davranışının ve uyumluluğunun sürümler arasında değiştiğini unutmayın; üretim kararı vermeden önce kullandığınız tam sürümün resmî belgesini doğrulayın. Buradaki kesin bayrak veya sürüm numaralarını ezbere aktarmaktan kaçınıyorum, çünkü bu ayrıntı hızla değişmektedir.

## async/await ve Eşzamanlılık Modeli

### Tanım

`async`/`await`, tek bir thread içinde **cooperative multitasking** (işbirlikçi çok görevlilik) sağlayan bir sözdizimidir. `async def` ile tanımlanan bir fonksiyon çağrıldığında hemen çalışmaz; bir **coroutine** nesnesi döner. Bu coroutine, bir **event loop** tarafından çalıştırılır.

### Kök neden: neden yeni bir model?

Thread'lerle eşzamanlılığın iki bedeli vardır: her thread'in kendi yığın belleği (stack) vardır ve işletim sistemi thread'ler arasında geçiş yaparken önemli bir maliyet oluşur. On binlerce eşzamanlı ağ bağlantısını thread'le yönetmek pahalıdır. Ayrıca thread geçişi **preemptive**'dir; yani herhangi bir bytecode arasında olabilir, bu da race condition'ları kaçınılmaz kılar ve kilitlemeyi zorunlu hale getirir.

async modeli bu iki sorunu farklı çözer. Coroutine'ler işletim sistemi thread'i değildir; hepsi tek thread'te yaşar, dolayısıyla bellek maliyeti çok düşüktür. Geçiş **preemptive değil, cooperative**'dir: kontrol yalnızca sizin `await` yazdığınız noktada devredilir. Bu, kodun ne zaman kesileceğini bilebilmenizi sağlar; iki `await` arasındaki kod bölümü bölünmeden çalışır.

### Çalışma mantığı: await ne yapar?

`await`, "bu işlem bir süre bekleyecek, o sırada kontrolü event loop'a geri ver, başka hazır işleri çalıştırsın; sonuç geldiğinde beni kaldığım yerden sürdür" demektir. Event loop, bu bekleyen görevleri izleyen tek bir döngüdür. `await` noktasında coroutine'in durumu (yerel değişkenler dahil) askıya alınır ve sonra tam kaldığı yerden devam eder. Bu askıya alma yeteneği, generator'lardan miras alınan bir mekanizmadır; nitekim async/await altyapısı, generator'ların üzerine kurulmuştur.

### Somut örnek

```python
import asyncio

async def veri_getir(id):
    await asyncio.sleep(1)   # bir ağ isteğini temsil ediyor
    return f"veri-{id}"

async def main():
    # gather ile üç istek eşzamanlı yürür, toplam ~1 saniye
    sonuclar = await asyncio.gather(
        veri_getir(1), veri_getir(2), veri_getir(3)
    )
    print(sonuclar)

asyncio.run(main())
```

Bu üç işin toplamda üç değil bir saniye sürmesinin nedeni, `await asyncio.sleep` sırasında event loop'un diğer coroutine'leri çalıştırmasıdır.

### Tuzaklar ve yaygın hatalar

- **Bloke edici çağrıyı async fonksiyonda kullanmak.** `time.sleep(1)`, `requests.get(...)` veya ağır bir CPU döngüsü, event loop thread'ini kilitler. O anda hiçbir coroutine ilerleyemez; async'in tüm faydası kaybolur. Çözüm: async uyumlu kütüphaneler kullanmak (`asyncio.sleep`, `aiohttp` vb.) ya da bloke eden işi `loop.run_in_executor` ile ayrı bir thread/süreç havuzuna atmak.
- **Coroutine'i çağırıp await etmemek.** `veri_getir(1)` yazıp await etmezseniz iş asla çalışmaz; genellikle "coroutine was never awaited" uyarısı alırsınız.
- **CPU-bound işi async ile hızlandırmaya çalışmak.** async paralellik sağlamaz, yalnızca beklemeyi verimli kullanır. GIL hâlâ oradadır. CPU-bound iş için süreç havuzu gerekir.
- **`asyncio.gather` içinde hata yönetimi.** Bir görev hata fırlatırsa diğerlerinin durumu ihmal edilebilir; `return_exceptions` davranışını ve iptal (cancellation) semantiğini bilmek gerekir.

## Bellek Modeli

### Tanım ve çalışma mantığı

Python'da her değer bir **nesnedir** ve değişkenler nesnelere **referanstır** (isim etiketi gibi). `a = [1, 2]; b = a` yazdığınızda iki liste değil, aynı listeye işaret eden iki isim vardır. Bunu C'deki değişkenler (kutu içine değer koymak) gibi düşünmek en yaygın kavramsal hatadır.

Bellek geri kazanımı iki mekanizmayla çalışır: birincil olarak yukarıda anlatılan **reference counting**, ikincil olarak da **cyclic garbage collector**. Reference counting, sayaç sıfıra düşer düşmez nesneyi anında temizler; ancak birbirine referans veren döngüsel yapıları (A → B → A) tek başına temizleyemez, çünkü sayaçlar hiç sıfıra düşmez. İşte bu döngüleri tespit edip toplamak için ayrı bir generational (kuşak tabanlı) çöp toplayıcı devreye girer.

### Somut tuzaklar

**Değişmez varsayılan argüman tuzağı.** En klasik Python hatası:

```python
def ekle(deger, liste=[]):     # TEHLİKELİ
    liste.append(deger)
    return liste

print(ekle(1))   # [1]
print(ekle(2))   # [1, 2]  -- beklenen [2] idi!
```

Kök neden: varsayılan argüman **fonksiyon tanımlandığında bir kez** oluşturulur, her çağrıda değil. O tek liste tüm çağrılar arasında paylaşılır. Doğru kalıp:

```python
def ekle(deger, liste=None):
    if liste is None:
        liste = []
    liste.append(deger)
    return liste
```

**Kopyalama tuzağı.** `b = a[:]` veya `copy.copy(a)` yüzeysel (shallow) kopya yapar; iç içe nesneler hâlâ paylaşılır. Derin kopya için `copy.deepcopy` gerekir, ama onun da maliyeti ve döngüsel yapılarda dikkat gerektiren davranışı vardır.

**Küçük tamsayı ve string önbelleği.** CPython, küçük tamsayıları ve bazı string'leri önbelleğe alır; bu yüzden `a is b` bazen `True` görünür. Bu bir uygulama ayrıntısıdır. **Asla** değer eşitliği için `is` kullanmayın; `is` kimlik (identity) karşılaştırır, `==` değer karşılaştırır. `is` yalnızca `None`, `True`, `False` gibi tekil (singleton) nesnelerle kullanılmalıdır.

**Kapanışların (closure) geç bağlanması.** Döngü içinde lambda tanımlarken:

```python
fonksiyonlar = [lambda: i for i in range(3)]
print([f() for f in fonksiyonlar])   # [2, 2, 2] -- beklenen [0,1,2]
```

Kök neden: kapanış `i`'nin **değerini değil, kendisini** yakalar; hepsi döngü bittikten sonraki son değeri görür. Çözüm, değeri varsayılan argümanla o an sabitlemektir: `lambda i=i: i`.

## Generator'lar

### Tanım ve kök neden

Generator, `yield` içeren bir fonksiyondur ve tüm değerleri baştan üretip bellekte tutmak yerine **istendikçe (lazily)** üretir. Kök neden: bellek verimliliği ve sonsuz/çok büyük dizilerle çalışabilme. Bir milyar satırlık dosyayı listeye almak belleği tüketir; generator ile satır satır işlersiniz.

`yield`'in mekanizması şudur: fonksiyon bir değer ürettiğinde, tüm yerel durumu (değişkenler, program sayacı) **donar** ve kontrol çağırana döner. Bir sonraki değer istendiğinde tam kaldığı yerden devam eder. Bu askıya alma/sürdürme yeteneği, async/await'in de temelidir.

### Somut örnek

```python
def kareler(n):
    for i in range(n):
        yield i * i     # tek seferde tek değer üretir

for k in kareler(5):
    print(k)            # 0 1 4 9 16, hiçbir zaman tam liste bellekte durmaz
```

### Tuzaklar

- **Bir generator yalnızca bir kez tüketilir.** İlk döngüde tükettikten sonra ikinci `for` boş döner; hata değil, sessiz bir davranıştır. Tekrar gerekiyorsa ya listeye çevirin ya da generator'ı yeniden oluşturun.
- **`len()` çalışmaz** ve `list(generator)` ile tüm bellek avantajını kaybedebilirsiniz.
- **Tembel değerlendirme sürprizi.** Generator, üzerinden geçilene kadar çalışmaz; bir istisna, generator tanımlandığında değil ilk tüketildiğinde fırlar, bu da hata ayıklamayı şaşırtabilir.

## Dekoratörler

### Tanım ve çalışma mantığı

Dekoratör, bir fonksiyonu (ya da sınıfı) alıp genellikle onu saran yeni bir fonksiyon döndüren bir fonksiyondur. `@dekorator` sözdizimi yalnızca sözdizimsel şekerdir; `f = dekorator(f)` ifadesine eşdeğerdir. Kök amaç: asıl işlevi değiştirmeden ona davranış eklemek (logging, önbellekleme, yetki kontrolü, süre ölçümü) — tek sorumluluk ilkesini korumak.

### Somut örnek ve kritik ayrıntı

```python
import functools, time

def sureyi_olc(fn):
    @functools.wraps(fn)          # önemli: metadata'yı korur
    def sarmalayici(*args, **kwargs):
        baslangic = time.perf_counter()
        sonuc = fn(*args, **kwargs)
        print(f"{fn.__name__}: {time.perf_counter() - baslangic:.4f}s")
        return sonuc
    return sarmalayici

@sureyi_olc
def isle(veri):
    return sum(veri)
```

`*args, **kwargs` kullanımı, dekoratörün **her imzayı** desteklemesini sağlar. `functools.wraps` ise sarmalayıcının `__name__`, `__doc__` gibi bilgilerini asıl fonksiyondan devralmasını sağlar; bunu unutursanız `isle.__name__` "sarmalayici" görünür, bu da hata izleri ve otomatik dokümantasyon araçlarını bozar. Bu, en sık gözden kaçan dekoratör hatasıdır.

### Tuzaklar

- **`functools.wraps` unutmak** (yukarıda).
- **Parametre alan dekoratör** yazmak üç kat iç içe fonksiyon gerektirir; katmanları karıştırmak yaygındır.
- **Durum paylaşımı.** Bir önbellek dekoratörü kapanışta durum tutar; thread'li ortamda bu durum race condition kaynağı olabilir. Hazır ve güvenli çözüm için `functools.lru_cache` gibi standart araçları tercih edin.

## Güvenli Kod

Python'un yüksek seviyeli olması, güvenlik risklerini ortadan kaldırmaz; yalnızca farklılaştırır. Aşağıdakiler en kritik başlıklardır.

### Asla güvenilmeyen girdiyle çalıştırmayın

`eval`, `exec` ve `pickle.loads`, güvenilmeyen veriyle kullanıldığında **uzaktan kod çalıştırma (remote code execution)** kapısıdır. `pickle`, serileştirilmiş veriyi geri yüklerken keyfi nesne inşa edebilir ve bu süreçte kod tetiklenebilir; bu yüzden dışarıdan gelen pickle verisini asla açmayın. Ağ üzerinden veri alışverişi için `json` gibi veri-yalnızca (data-only) formatları kullanın.

Benzer şekilde, dış girdiyi doğrudan bir kabuk komutuna geçirmek **command injection** yaratır. `os.system("ping " + kullanici_girdisi)` yerine `subprocess.run([...], shell=False)` biçiminde, argümanları liste olarak ve `shell=False` ile verin; böylece kabuk metakarakterleri (`;`, `|`, `&&`) yorumlanmaz.

### YAML ve seri hâline getirme

Bazı YAML ayrıştırıcı fonksiyonları, YAML içinde belirtilen keyfi Python nesnelerini inşa edebilir; bu da yine kod çalıştırmaya açılır. Güvenilmeyen YAML için **her zaman** yükleyicinin "safe" (yalnızca temel veri tipleri üreten) çeşidini kullanın.

### Rastgelelik ve sırlar

Şifre sıfırlama token'ı, oturum anahtarı, geçici parola gibi güvenlik amaçlı değerlerde `random` modülünü **kullanmayın**. `random`, istatistiksel olarak iyi ama **kriptografik olarak öngörülebilir** bir üreteçtir; çıktısı geçmiş değerlerden tahmin edilebilir. Bunun yerine `secrets` modülünü kullanın (`secrets.token_hex`, `secrets.token_urlsafe`). Parola karşılaştırmasında da normal `==` yerine sabit zamanlı karşılaştırma (`secrets.compare_digest`) kullanın; aksi halde karşılaştırma süresi sızıntısıyla bir **timing attack** mümkün olabilir.

### Parola saklama

Parolaları asla düz metin veya basit hash (MD5, SHA-256 tek geçiş) ile saklamayın. Bunlar hız için tasarlanmıştır ve bu, saldırgan için avantajdır. Parola için özel olarak yavaş ve tuzlanmış (salted) algoritmalar kullanın (bcrypt, scrypt, Argon2 ailesi gibi). Amaç, doğrulamayı yeterince ucuz ama kaba kuvvet (brute force) denemesini yeterince pahalı tutmaktır.

### Bağımlılık ve tedarik zinciri

Modern uygulamalarda en büyük saldırı yüzeyi sizin kodunuz değil, bağımlılıklarınızdır. Sürümleri sabitleyin (pinning), bilinen açıklar için düzenli tarama yapın ve paket adlarını dikkatle yazın; bir harf hatası, saldırganın yerleştirdiği sahte bir paketi (typosquatting) çekebilir. Kesin bir CVE numarası veya araç bayrağı vermekten kaçınıyorum; önemli olan yöntemdir: bağımlılıkları düzenli denetleyin ve otomatik güvenlik taramasını CI hattınıza koyun.

## En İyi Pratikler: Özet

- **Doğru aracı seçin:** CPU-bound için süreç, I/O-bound için thread veya async. GIL'i bir kısıt değil, bir tasarım gerçeği olarak kabul edin.
- **async'te asla bloke etmeyin;** bloke eden işi executor'a taşıyın.
- **Değişmez varsayılan argüman** ve **geç bağlanan kapanış** tuzaklarını ezbere bilin; bunlar sessiz hatalardır.
- **Kimlik ve değer karşılaştırmasını** (`is` / `==`) karıştırmayın.
- Dekoratörlerde **`functools.wraps`** her zaman kullanılır.
- Güvenlikte varsayılan tavrınız **güvensizlik** olsun: dış girdiyi asla güvenmeyin, `eval`/`exec`/güvenilmeyen `pickle`'dan kaçının, kabuk komutlarında argümanları listeyle verin.
- Sırlar için `secrets`, parolalar için özel yavaş hash algoritmaları kullanın.
- Bağımlılıklarınızı bir saldırı yüzeyi olarak görün ve sürekli denetleyin.

İleri seviye Python, sözdizimi bilgisi değil, dilin altındaki maliyet ve garanti dengelerini görebilme becerisidir. Bir özelliği kullanırken kendinize "bunun kök nedeni ne, hangi durumda beni yanıltır?" diye sormak, sizi kod yazan biri olmaktan sistem tasarlayan biri olmaya taşır.
