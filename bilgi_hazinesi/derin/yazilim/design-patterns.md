# Tasarım Kalıpları — Derin Dalış

Bu metin, özet makaledeki kavramları (Factory, Strategy, Observer, Decorator, Singleton...) *çalışır kod* üzerinde derinleştirir. Amaç kalıpların adını ezberletmek değil; her kalıbın hangi somut acıyı hafiflettiğini, yanlış uygulandığında nasıl sırtınızdan bıçakladığını ve alternatiflerinin ne olduğunu göstermektir. Örnekler Python ve TypeScript ağırlıklıdır; çünkü her ikisi de kalıpları hem klasik OOP biçiminde hem de dile gömülü modern biçimde göstermeye elverişlidir.

---

## 1. Çözümlü Yürüyüş: `if/else` Cehenneminden Strategy'ye

Somut bir senaryoyla başlayalım. Bir e-ticaret sepeti için kargo ücreti hesaplayan bir servis yazıyoruz. İlk sürüm masum başlar, sonra her yeni gereksinimle şişer.

### 1.1 Zafiyetli / hatalı kod

```python
# kargo_hesaplayici.py — SORUNLU SÜRÜM
from decimal import Decimal

class KargoHesaplayici:
    def ucret_hesapla(self, siparis, yontem: str) -> Decimal:
        agirlik = siparis["agirlik_kg"]
        tutar = Decimal(str(siparis["tutar"]))

        if yontem == "standart":
            ucret = Decimal("15.00") + Decimal("2.00") * Decimal(str(agirlik))
            if tutar > Decimal("500"):
                ucret = Decimal("0")           # ücretsiz kargo
            return ucret

        elif yontem == "ekspres":
            ucret = Decimal("40.00") + Decimal("3.50") * Decimal(str(agirlik))
            if siparis.get("bolge") == "uzak":
                ucret += Decimal("25.00")
            return ucret

        elif yontem == "ayni_gun":
            if siparis.get("bolge") == "uzak":
                raise ValueError("Aynı gün teslimat uzak bölgeye yapılamaz")
            return Decimal("80.00") + Decimal("5.00") * Decimal(str(agirlik))

        elif yontem == "gel_al":
            return Decimal("0")

        else:
            # SESSİZ HATA: bilinmeyen yöntem 0 döner!
            return Decimal("0")
```

Bu kod bugün çalışıyor. Ama üç ay sonra "drone teslimatı", "yurt dışı kargo", "kargo firması X'e özel indirim" gereksinimleri gelince ne olur?

### 1.2 Sorun neden oluşuyor?

Üç ayrı kök neden iç içe geçmiş durumda:

1. **Open/Closed ihlali.** Her yeni kargo yöntemi, *var olan* `ucret_hesapla` metodunu değiştirmeyi zorunlu kılar. Test edilmiş, çalışan bir metoda her dokunuş bir regresyon riskidir. Kod "genişlemeye açık, değişime kapalı" olması gerekirken tam tersi.

2. **Tek Sorumluluk ihlali.** Bu tek metot beş farklı iş mantığını (standart fiyatlama, ekspres, aynı gün, gel-al kuralları) barındırıyor. Ekspres kargonun uzak bölge zammını değiştirmek isteyen biri, aynı gün teslimatın kodunu da okumak/riske atmak zorunda kalıyor.

3. **Sessiz hata (silent failure).** Son `else` bloğu bilinmeyen bir yöntem için `0` döndürüyor. Frontend'de bir yazım hatası (`"ekpres"`) yüzünden müşteriye ücretsiz kargo verirsiniz ve bunu aylarca fark etmezsiniz. Bu, kalıpların çözdüğü klasik "büyüyen switch zinciri" belirtisidir.

### 1.3 Düzeltilmiş / doğru kod (Strategy)

Her algoritmayı ortak bir arayüz arkasında ayrı bir nesneye taşıyoruz. Python'da bunu `Protocol` ile yapısal tiplemeye dayanarak yazmak, gereksiz kalıtımdan kaçınır:

```python
# kargo_strateji.py — DÜZELTİLMİŞ SÜRÜM
from decimal import Decimal
from typing import Protocol, Mapping, Any

Siparis = Mapping[str, Any]

class KargoStratejisi(Protocol):
    def hesapla(self, siparis: Siparis) -> Decimal: ...

class StandartKargo:
    UCRETSIZ_ESIK = Decimal("500")
    def hesapla(self, siparis: Siparis) -> Decimal:
        if Decimal(str(siparis["tutar"])) > self.UCRETSIZ_ESIK:
            return Decimal("0")
        return Decimal("15.00") + Decimal("2.00") * Decimal(str(siparis["agirlik_kg"]))

class EkspresKargo:
    def hesapla(self, siparis: Siparis) -> Decimal:
        ucret = Decimal("40.00") + Decimal("3.50") * Decimal(str(siparis["agirlik_kg"]))
        if siparis.get("bolge") == "uzak":
            ucret += Decimal("25.00")
        return ucret

class AyniGunKargo:
    def hesapla(self, siparis: Siparis) -> Decimal:
        if siparis.get("bolge") == "uzak":
            raise ValueError("Aynı gün teslimat uzak bölgeye yapılamaz")
        return Decimal("80.00") + Decimal("5.00") * Decimal(str(siparis["agirlik_kg"]))

class GelAlKargo:
    def hesapla(self, siparis: Siparis) -> Decimal:
        return Decimal("0")

# Kayıt (registry): yeni yöntem eklemek = bir satır. Var olan koda dokunulmaz.
STRATEJILER: dict[str, KargoStratejisi] = {
    "standart": StandartKargo(),
    "ekspres": EkspresKargo(),
    "ayni_gun": AyniGunKargo(),
    "gel_al": GelAlKargo(),
}

def kargo_ucreti(siparis: Siparis, yontem: str) -> Decimal:
    try:
        strateji = STRATEJILER[yontem]
    except KeyError:
        # Sessiz sıfır YOK: bilinmeyen yöntem gürültülü biçimde patlar.
        raise ValueError(f"Bilinmeyen kargo yöntemi: {yontem!r}")
    return strateji.hesapla(siparis)
```

Ne kazandık?

- **Drone teslimatı eklemek** artık `DroneKargo` sınıfı yazıp sözlüğe bir satır eklemektir. Var olan dört sınıfın hiçbiri değişmez, testleri kırılmaz.
- **Sessiz hata gitti.** `KeyError` yakalanıp anlamlı bir istisnaya çevriliyor; yazım hatası anında görünür.
- **Test edilebilirlik.** Her stratejiyi tek başına test edebilirsiniz; `EkspresKargo().hesapla(...)` için tüm sepet servisini ayağa kaldırmanıza gerek yok.

Dikkat edilmesi gereken incelik: `Protocol` kullandığımız için strateji sınıflarının ortak bir taban sınıftan *türemesi gerekmez*. Bu, Python'ın "duck typing" felsefesine uygun, gereksiz kalıtım katmanı eklemeyen modern bir Strategy uygulamasıdır. Java'da aynı şeyi `interface KargoStratejisi` ile, TypeScript'te `interface` veya sadece bir fonksiyon tipiyle yazardınız.

Hatta çoğu durumda Python'da tam sınıf bile gereksizdir; birinci sınıf fonksiyonlar Strategy'yi bedavaya getirir:

```python
STRATEJILER = {
    "gel_al": lambda s: Decimal("0"),
    # ... durum tutan stratejiler için sınıf, durumsuzlar için fonksiyon
}
```

Bu "kalıbı dile gömülü biçimde kullan" ilkesinin somut örneğidir: durum (state) tutmayan bir strateji için koca bir sınıf yazmak fazladan törendir.

Son bir incelik: yukarıdaki `STRATEJILER` sözlüğü aynı zamanda bir **registry** (kayıt) desenidir ve Factory ile Strategy'nin nasıl doğal biçimde birleştiğini gösterir. `kargo_ucreti` fonksiyonu bir yandan doğru stratejiyi *seçer* (Factory rolü), bir yandan onu *çalıştırır* (Strategy rolü). Gerçek sistemlerde bu kayıt genellikle bir decorator ile otomatik doldurulur:

```python
STRATEJILER: dict[str, KargoStratejisi] = {}

def kaydet(ad: str):
    def sarici(cls):
        STRATEJILER[ad] = cls()
        return cls
    return sarici

@kaydet("standart")
class StandartKargo:
    def hesapla(self, siparis): ...
```

Böylece yeni bir strateji eklemek, onu tanımlayan dosyayı yazmaktan ibaret olur; merkezî bir listeyi elle güncellemeyi (ve unutmayı) tamamen ortadan kaldırırsınız. Bu, plugin mimarilerinin ve Django/Flask gibi framework'lerin route/handler kaydının kalbindeki desendir.

---

## 2. Gerçek Sistem Örneği: Observer ve Bellek Sızıntısı

Özet makale Observer'ın tuzağını "abonelikler bırakılmazsa bellek sızar" diye bir cümleyle geçmişti. Bu cümlenin arkasındaki gerçek, üretim sistemlerinde en sinsi hatalardan biridir. Somut bir olay veriyolu (event bus) kuralım ve sızıntıyı gözle görelim.

### 2.1 Naif Observer ve sızıntı

```python
# olay_veriyolu.py
class OlayVeriyolu:
    def __init__(self):
        self._aboneler: dict[str, list] = {}

    def abone_ol(self, olay: str, geri_cagri):
        self._aboneler.setdefault(olay, []).append(geri_cagri)

    def yayinla(self, olay: str, veri):
        for geri_cagri in self._aboneler.get(olay, []):
            geri_cagri(veri)


class SiparisPaneli:
    """Kullanıcı bir sipariş açtığında oluşan, kapatınca yok olması gereken bir bileşen."""
    def __init__(self, veriyolu: OlayVeriyolu, siparis_id: int):
        self.siparis_id = siparis_id
        self.gecmis = []                      # büyük olabilir
        veriyolu.abone_ol("stok_guncellendi", self._stok_degisti)

    def _stok_degisti(self, veri):
        self.gecmis.append(veri)
```

Sorun: `SiparisPaneli` kullanıcı paneli kapatınca "gitmeli". Ama `OlayVeriyolu._aboneler` listesi hâlâ `self._stok_degisti`'ye — dolayısıyla `self`'e — güçlü bir referans tutuyor. Python'ın çöp toplayıcısı (garbage collector) bu paneli asla toplayamaz. Kullanıcı gün boyu 200 sipariş açıp kapatırsa, 200 panel bellekte `gecmis` listeleriyle birlikte yaşamaya devam eder. Bu, uzun ömürlü süreçlerde (bir masaüstü uygulaması, bir websocket sunucusu) yavaş yavaş belleği yer ve sonunda OOM ile çöker.

### 2.2 Doğru çözüm: zayıf referans + açık abonelik iptali

İki savunma katmanı ekliyoruz. Birincisi `abone_ol`'un bir *iptal fonksiyonu* döndürmesi (JavaScript ekosisteminde standart olan `unsubscribe` deseni). İkincisi, geri çağrının bir bound method olduğu durumda `weakref` ile zayıf referans tutmak, böylece nesne başka yerde bittiğinde veriyolu onu diri tutmaz.

```python
# olay_veriyolu_v2.py
import weakref
from typing import Callable

class OlayVeriyolu:
    def __init__(self):
        self._aboneler: dict[str, list[weakref.WeakMethod | weakref.ref]] = {}

    def abone_ol(self, olay: str, geri_cagri: Callable) -> Callable[[], None]:
        # Bound method ise WeakMethod, düz fonksiyon ise normal ref.
        if hasattr(geri_cagri, "__self__"):
            ref = weakref.WeakMethod(geri_cagri)
        else:
            ref = weakref.ref(geri_cagri)
        self._aboneler.setdefault(olay, []).append(ref)

        def iptal_et():
            liste = self._aboneler.get(olay, [])
            if ref in liste:
                liste.remove(ref)
        return iptal_et

    def yayinla(self, olay: str, veri):
        canli = []
        for ref in self._aboneler.get(olay, []):
            geri_cagri = ref()           # zayıf referansı çöz
            if geri_cagri is None:
                continue                 # nesne çoktan toplandı, atla
            canli.append(ref)
            geri_cagri(veri)
        # Ölü referansları temizle (self-healing)
        if olay in self._aboneler:
            self._aboneler[olay] = canli


class SiparisPaneli:
    def __init__(self, veriyolu: OlayVeriyolu, siparis_id: int):
        self.siparis_id = siparis_id
        self.gecmis = []
        self._iptal = veriyolu.abone_ol("stok_guncellendi", self._stok_degisti)

    def _stok_degisti(self, veri):
        self.gecmis.append(veri)

    def kapat(self):
        self._iptal()                    # açık iptal — en güvenli yol
```

Bu tasarımın önemli detayı: `WeakMethod` bound method'ları özel olarak ele alır. Neden `weakref.ref(self._stok_degisti)` yetmez? Çünkü `self._stok_degisti` ifadesi her erişimde *yeni* bir bound method nesnesi üretir; ona düz `weakref.ref` koyarsanız referans anında ölür ve gözlemci hiç çağrılmaz. `WeakMethod` tam da bu tuzağı çözmek için vardır: altında yatan `self`'e zayıf, metoda ise doğru biçimde bağlanır.

Yine de "zayıf referans var, iptal etmesem de olur" diye düşünmeyin. Zayıf referans bir *güvenlik ağıdır*, birincil mekanizma değil. Doğru mühendislik hâlâ `kapat()` içinde açıkça `self._iptal()` çağırmaktır; zayıf referans sadece o çağrıyı unuttuğunuzda felaketi hafifletir.

### 2.3 Gerçek dünya karşılığı

Bu tam olarak React'in `useEffect` cleanup fonksiyonunun, Angular'ın `ngOnDestroy`'unun, RxJS'in `takeUntil`/`Subscription.unsubscribe`'ının çözdüğü problemdir. Bir bileşen bir olaya abone oluyorsa, o bileşen öldüğünde aboneliğin de ölmesi gerekir. Framework'ler bunu "cleanup döndür" API'siyle zorunlu kılar; kendi Observer'ınızı yazarken aynı disiplini elle kurmanız gerekir.

### 2.4 İkinci tuzak: senkron bildirim zinciri ve yeniden giriş (re-entrancy)

Naif `yayinla` metodunun görünmeyen bir tehlikesi daha var: bildirim *senkron* ve *sıralı* akar. Bir gözlemci, aynı olay döngüsü içinde yeni bir `yayinla` tetiklerse ya da abonelik listesini değiştirirse, üzerinde döndüğünüz liste ayağınızın altından kayar. Python'da bir listeyi döngüyle gezerken değiştirmek `RuntimeError` veya sessiz atlanan elemanlar doğurur:

```python
def yayinla(self, olay, veri):
    # SORUN: geri_cagri içinde abone_ol/iptal_et çağrılırsa liste döngü sırasında değişir.
    for ref in self._aboneler.get(olay, []):
        ...
```

Çözüm, `list(...)` ile bir kopya üzerinde gezmek ve bildirimleri mümkünse tampona alıp döngü bittikten sonra işlemektir. `v2` sürümünde zaten `canli` adında yeni bir liste kurduğumuz için bu tuzaktan büyük ölçüde korunuruz; ama iç içe `yayinla` çağrılarında sonsuz özyineleme (bir gözlemci kendi tetiklediği olayı yeniden yayınlar) hâlâ mümkündür. Üretim veri yollarında bu yüzden bir "yayınlanıyor mu?" bayrağı ya da olay kuyruğu tutulur; bildirimler eşzamanlı yerine sıraya alınıp tek tek boşaltılır. Bu, Observer'ı Command (kuyruğa alınabilir istek) kalıbıyla birleştirmenin pratik bir örneğidir.

---

## 3. Karşılaştırma / Karar: Inheritance mi, Composition mu? Ve Yakın Akraba Kalıplar

Kalıp seçiminin çoğu, üç ünlü ikili arasındaki karardır. Her birinin yapısı benzer, niyeti farklıdır; yanlışını seçmek kodu sessizce çürütür.

### 3.1 Strategy (composition) vs. Template Method (inheritance)

Aynı problemi — "bir algoritmanın bir adımını değiştirilebilir kılmak" — iki yol çözer.

**Template Method (kalıtım):**

```python
from abc import ABC, abstractmethod

class RaporUretici(ABC):
    def uret(self, veri) -> str:           # iskelet — sabit
        baslik = self._baslik()
        govde = self._govde_bicimlendir(veri)
        return f"{baslik}\n{govde}"

    def _baslik(self) -> str:
        return "=== RAPOR ==="            # ortak, override edilebilir

    @abstractmethod
    def _govde_bicimlendir(self, veri) -> str: ...

class CsvRapor(RaporUretici):
    def _govde_bicimlendir(self, veri) -> str:
        return "\n".join(",".join(map(str, satir)) for satir in veri)
```

**Strategy (bileşim):**

```python
class RaporUretici:
    def __init__(self, bicimlendirici):   # davranış dışarıdan enjekte
        self._bicimlendirici = bicimlendirici

    def uret(self, veri) -> str:
        return f"=== RAPOR ===\n{self._bicimlendirici(veri)}"

csv_rapor = RaporUretici(lambda veri: "\n".join(",".join(map(str, s)) for s in veri))
```

**Takas:**

| Ölçüt | Template Method | Strategy |
|---|---|---|
| Bağlanma zamanı | Derleme zamanı (sınıf sabit) | Çalışma zamanı (nesne değişebilir) |
| Değişebilir adım sayısı | Çok adım kolayca | Tek/az davranış için ideal |
| Çalışma anında değiştirme | Hayır | Evet (`.bicimlendirici = ...`) |
| Bağ (coupling) | Sıkı — alt sınıf üst sınıfa bağlı | Gevşek — sadece arayüze bağlı |
| Test | Alt sınıf üzerinden | Davranışı izole test edilebilir |

**Karar kuralı:** Algoritmanın *iskeleti* gerçekten sabit ve sadece birkaç noktası oynuyorsa, ve bu noktaları çalışma anında değiştirmeniz gerekmiyorsa Template Method sadedir. Davranışı çalışma anında takmak/çıkarmak, ya da aynı davranışı birden çok bağlamda paylaşmak istiyorsanız Strategy kazanır. GoF'un "composition over inheritance" pusulası genelde Strategy'yi işaret eder; Template Method'u ancak "birden çok kancası olan gerçek bir iskelet" varken seçin.

### 3.2 Decorator vs. Proxy vs. Inheritance

Üçü de "bir nesnenin davranışını sarmalar" gibi görünür.

- **Inheritance** ile davranış eklemek kombinatoryal patlar. "Tamponlu + şifreli + sıkıştırılmış akış" için ayrı ayrı `TamponluSifreliSikistirilmisStream` sınıfları üretemezsiniz.
- **Decorator** aynı arayüzü koruyarak davranış *ekler* ve serbestçe dizilir: `Sikistirilmis(Sifreli(DosyaAkisi()))`.
- **Proxy** aynı arayüzü sunar ama niyeti davranış eklemek değil, erişimi *denetlemektir* (lazy loading, yetkilendirme, önbellek, uzak çağrı).

```typescript
// TypeScript: Decorator ve Proxy yapıca aynı, niyetçe farklı
interface Depo { oku(anahtar: string): string; }

class DiskDepo implements Depo {
  oku(anahtar: string): string { /* pahalı disk okuması */ return `veri:${anahtar}`; }
}

// DECORATOR — davranış ekler (loglama)
class LoglayanDepo implements Depo {
  constructor(private ic: Depo) {}
  oku(anahtar: string): string {
    console.log(`okunuyor: ${anahtar}`);
    return this.ic.oku(anahtar);         // davranış EKLENDİ, sonuç değişmedi
  }
}

// PROXY — erişimi denetler (önbellek + yetki)
class OnbellekliDepo implements Depo {
  private cache = new Map<string, string>();
  constructor(private ic: Depo, private yetkili: boolean) {}
  oku(anahtar: string): string {
    if (!this.yetkili) throw new Error("Yetkisiz erişim");  // erişim DENETİMİ
    if (!this.cache.has(anahtar)) this.cache.set(anahtar, this.ic.oku(anahtar));
    return this.cache.get(anahtar)!;     // gerçek nesneye erişimi kontrol ediyor
  }
}
```

**Karar kuralı:** Kendinize "asıl nesnenin davranışına bir şey mi *ekliyorum* (Decorator), yoksa ona erişimi mi *yönetiyorum* — geç yaratma, yetki, önbellek, uzaklık (Proxy)?" sorusunu sorun. İkisi karışırsa isimlendirme yalan söyler ve okuyucu niyeti kaybeder.

### 3.3 Singleton vs. Dependency Injection

Özet makale Singleton'ın gizli global durum olduğunu söyledi. Kararı somutlaştıralım. İhtiyaç genelde "tüm uygulamada tek bir veritabanı havuzu olsun". Singleton bunu şöyle çözer:

```python
class DbHavuzu:
    _ornek = None
    @classmethod
    def al(cls):
        if cls._ornek is None:
            cls._ornek = cls()           # thread-unsafe! race condition riski
        return cls._ornek
```

Sorunlar: (1) `DbHavuzu.al()` çağıran her sınıf ona *gizlice* bağımlıdır — imzasına bakarak anlayamazsınız. (2) Testte sahte bir havuz koyamazsınız çünkü global sınıf durumu testler arasında sızar. (3) Yukarıdaki tembel kurulum çok iş parçacıklı ortamda race condition'dır.

DI çözümü aynı "tek örnek" garantisini yaşam döngüsüne bırakır ama bağımlılığı *görünür* kılar:

```python
class SiparisServisi:
    def __init__(self, db: DbHavuzu):    # bağımlılık imzada AÇIK
        self._db = db

# Kompozisyon kökü (composition root): tek örnek burada bir kez üretilir.
db = DbHavuzu()
servis = SiparisServisi(db)             # testte sahte db geçmek serbest
```

**Karar kuralı:** "Tek örnek gerek" düşüncesi sizi refleksle Singleton'a atmasın. Tek örnek bir *yaşam döngüsü* kararıdır (uygulama boyunca bir tane üret), bir *erişim* kararı (her yerden global eriş) değil. DI konteynerleri "singleton scope" ile tam da bunu, global durumun zararı olmadan verir. Singleton'ı yalnızca gerçekten durumsuz yardımcılar veya dilin garanti ettiği güvenli sabitler için düşünün.

---

## 4. Hata-Modu Kataloğu

Aşağıda tasarım kalıplarıyla çalışırken sahada tekrar tekrar görülen tipik hatalar. Her biri belirli bir acıya karşılık gelir.

1. **Sessiz `else` / default sıfır.** Büyüyen bir `if/else` ya da `switch`'i Strategy'ye çevirirken bilinmeyen durumu sessizce "makul bir varsayılan"a düşürmek. Bir yazım hatası (`"ekpres"`) aylarca ücretsiz kargo dağıtabilir. Bilinmeyen anahtarı her zaman gürültülü biçimde (istisna) patlatın.

2. **Observer'da abonelik bırakmamak.** Gözlemci öldüğünde `unsubscribe` çağrılmazsa, özne (subject) ona güçlü referans tuttuğu için çöp toplayıcı onu asla toplayamaz — klasik bellek sızıntısı. Uzun ömürlü süreçlerde yavaş çöküş getirir.

3. **Bound method'a düz `weakref.ref` koymak.** `weakref.ref(self.metot)` anında ölür çünkü `self.metot` her erişimde yeni bir bound method üretir. Gözlemci hiç tetiklenmez ve bunu fark etmek saatler alır; `WeakMethod` kullanmak gerekir.

4. **Decorator ile Proxy'yi karıştırmak.** Yapıları aynı olduğu için niyeti taklit etmeden yapıyı kopyalamak. Erişim denetleyen bir sınıfı `XxxDecorator`, davranış ekleyen bir sınıfı `XxxProxy` diye adlandırmak, sonraki okuyucuyu tam ters yönde yanıltır.

5. **Strategy ile State'i eş sanmak.** İkisi de "davranışı ayrı nesneye taşır" ama Strategy'de *dışarıdaki istemci* seçimi yapar; State'te *durumların kendisi* bir sonraki duruma geçişi yönetir. State'i Strategy gibi kurup geçiş mantığını dışarı sızdırmak, durum makinesini yeniden `if` çorbasına döndürür.

6. **Telescoping constructor'ı Builder yerine kullanmayı sürdürmek.** `User("Ali", None, None, 30, None, True)` gibi çağrılarda hangi konumun ne olduğu okunamaz; yanlış sıraya dizilen iki `None` sessiz hataya döner. Çok opsiyonel alanı olan nesnelerde Builder (ya da adlandırılmış argümanlar) şart.

7. **Prototype'ta sığ kopya tuzağı.** Bir nesneyi klonlarken iç referansların (liste, sözlük) paylaşıldığını gözden kaçırmak. Klonun listesine eklediğinizde orijinal de değişir; `copy.copy` yerine gereken yerde `copy.deepcopy` kullanılmalı — ama körlemesine deepcopy de performansı öldürür, ayrımı bilinçli yapın.

8. **Singleton'ı refleksle seçip test edilemez kod üretmek.** "Her yerden erişmek kolay olsun" diye global durum sokmak; sonra testlerde onu sahtelemeye çalışırken testlerin birbirine sızan durumla kırılgan hale gelmesi. Çoğu vakada DI daha temizdir.

9. **Thread-unsafe lazy Singleton.** Çok iş parçacıklı ortamda `if _ornek is None: _ornek = ...` kalıbı iki thread'in aynı anda iki örnek yaratmasına yol açar. Modül düzeyi başlatma, `functools.lru_cache`, ya da güvenli başlatma mekanizması gerekir; naif double-check yanlış yazılırsa hâlâ kırıktır.

10. **Kalıbı problemi kanıtlanmadan kurmak (speküle soyutlama).** "İleride üç veritabanı olur" diye baştan Abstract Factory kurmak. Gelmeyen gelecek için bugünün kodunu dört dosyaya yayarsınız; YAGNI ihlali. Soyutlamayı tekrarın üçüncü kez göründüğü ana erteleyin.

11. **Dile gömülü çözümü elle yeniden yazmak.** Kendi `Iterator`'ınızı yazmak (Python generator / `__iter__` varken), durumsuz bir Strategy için koca sınıf hiyerarşisi kurmak (birinci sınıf fonksiyon yeterken), ya da event kütüphanesi varken Observer'ı sıfırdan örmek. Bu, test edilmemiş, gereksiz koddur.

12. **İsimlendirmeyi tören diline çevirmek.** Her sınıfı `XxxManager`, `XxxFactory`, `XxxStrategy` diye etiketlemek ama yapının kalıbı gerçekten uygulamaması. İsim niyeti taşımalı; gerçek yapıyla örtüşmeyen kalıp adı belge değil, yalan hâline gelir.

13. **Composite'te tip kontrolüyle yaprağı/dalı ayırmak.** `if isinstance(node, Yaprak)` yazmaya başladığınız an Composite'in bütün faydasını kaybedersiniz — kalıbın amacı tam da bu ayrımı ortadan kaldırmaktı. Yaprak ve dal aynı arayüzü uygulamalı, istemci ikisini ayırt etmemeli.

14. **Chain of Responsibility'de zinciri sonlandırmamak.** Hiçbir işleyici isteği ele almazsa ne olacağını tanımlamamak; istek sessizce düşer ya da sonsuz döngüye girer. Zincirin sonunda açık bir "hiçbiri işlemedi" davranışı olmalı.

---

## Kapanış

Bu örneklerin ortak dersi şudur: bir kalıp, belirli bir *değişim baskısına* verilmiş cerrahi bir yanıttır. Strategy, büyüyen `switch`'in baskısını; Observer, gevşek bağlı bildirimin baskısını; Decorator, kombinatoryal alt sınıf patlamasının baskısını çözer. Baskı yokken kalıp sadece maliyettir — fazladan dolaylılık, fazladan dosya, okuyucunun zihninde tutması gereken fazladan katman. Doğru mühendislik, kalıbı *baştan* değil, tekrarın kendini kanıtladığı anda, testler yerindeyken güvenli bir refactoring adımıyla ekler. En değerli beceri hâlâ aynıdır: bazen hiçbir kalıp kullanmamanın en iyi tasarım olduğunu bilmek.
