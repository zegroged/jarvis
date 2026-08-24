# Güvensiz Deserialization — Derin Dalış

Bu metin, güvensiz deserialization'ı bir özet düzeyinde değil, çözümlü bir yürüyüş, gerçek CVE kayıtları, tasarım kararları ve hata-modu kataloğu üzerinden ele alır. Amaç savunma ve tespittir: mekanizmayı yeterince derin anlayıp kendi kodunuzda ve trafiğinizde bulabilecek, doğru mimari kararı verebilecek düzeye gelmek. Operasyonel bir saldırı reçetesi değil, bir savunmacının zihinsel modelidir.

Baştan bir çıpa: güvensiz deserialization çoğu zaman deserializer'daki bir "bug" değildir. Deserializer tam da tasarlandığı işi yapar — akıştaki tip bilgisine bakar, o tipi örnekler, alanlarını girdiden gelen değerlerle doldurur ve bazı dillerde bu sırada otomatik metotları tetikler. Sorun, bu güçlü yeteneğin *güvenilmeyen girdiye* açılmasıdır. Bu yüzden çözüm de tek satırlık bir yama değil, çoğu zaman mimari bir karardır.

---

## 1. Çözümlü yürüyüş

Somut ve gerçekçi bir örnek üzerinden gidelim. Senaryo: bir Python web servisi, kullanıcının oturum tercihlerini (tema, dil, son görüntülenen sayfa) bir cookie içinde istemciye taşıyor. Geliştirici, "nesneyi olduğu gibi saklamak pratik" diye düşünüp `pickle` seçmiş. Bu, sahada en sık gördüğümüz güvensiz deserialization desenlerinden biridir.

### Zafiyetli kod

```python
# app.py  — ZAFIYETLI SÜRÜM
import base64
import pickle
from flask import Flask, request, make_response

app = Flask(__name__)


class UserPrefs:
    def __init__(self, theme="light", lang="tr", last_page="/"):
        self.theme = theme
        self.lang = lang
        self.last_page = last_page


def load_prefs(cookie_value: str) -> UserPrefs:
    # Cookie base64 ile kodlanmis pickle verisi tasiyor.
    raw = base64.b64decode(cookie_value)
    return pickle.loads(raw)          # <-- KRITIK SATIR: guvenilmeyen veriyi pickle.loads


def save_prefs(prefs: UserPrefs) -> str:
    return base64.b64encode(pickle.dumps(prefs)).decode()


@app.route("/")
def index():
    cookie = request.cookies.get("prefs")
    if cookie:
        try:
            prefs = load_prefs(cookie)          # saldirganin kontrolundeki veri buraya akar
        except Exception:
            prefs = UserPrefs()
    else:
        prefs = UserPrefs()

    resp = make_response(f"Tema: {prefs.theme}, Dil: {prefs.lang}")
    resp.set_cookie("prefs", save_prefs(prefs))
    return resp
```

Kod ilk bakışta masum görünür. Nesneyi kaydediyor, geri yüklüyor, çalışıyor. Testlerden geçer. Sorun, `load_prefs` içindeki `pickle.loads(raw)` satırının, kaynağı doğrudan istemcinin cookie'si olan bir baytı geri serileştirmesidir.

### Sorun kavramsal olarak nasıl ortaya çıkıyor?

`pickle` formatı, düz bir veri formatı değildir. Aslında küçük, yığın-tabanlı (stack-based) bir sanal makine için opcode akışıdır. Bu opcode'lar arasında `REDUCE` gibi, "şu callable'ı şu argümanlarla çağır" diyen talimatlar bulunur. Yani pickle verisi, "şu değerler" değil, "şu işlemleri yap" der.

Bir nesne pickle'lanırken, sınıfı `__reduce__` metoduyla kendini nasıl geri kuracağını söyleyebilir: bir `(callable, args)` tuple'ı döndürür ve unpickle sırasında `callable(*args)` çağrılır. Meşru sınıflar bununla kurucularını çağırır. Ama saldırgan, cookie yerine kendi ürettiği bir pickle akışı koyarsa, o akış `os.system` gibi tehlikeli bir callable'ı işaret edebilir. Burada kritik nokta: saldırgan hedef sunucuda çalışan sınıflardan hiçbirine bağımlı değildir; `os` modülü zaten oradadır. Gadget chain aramaya bile gerek yoktur — format, callable çağırmayı birinci sınıf bir yetenek olarak sunar.

Kavramsal olarak saldırganın ürettiği zararlı sınıf şuna benzer (savunmacının *ne tür* bir girdiyle karşılaşacağını anlaması için gösteriliyor):

```python
# Saldirganin urettigi payload sinifi — savunmaci bunu anlamali
import os

class Exploit:
    def __reduce__(self):
        # unpickle aninda os.system("...") tetiklenir
        return (os.system, ("id > /tmp/pwned",))

# base64(pickle.dumps(Exploit())) ciktisi "prefs" cookie'sine konur.
```

Kurban sunucu bu cookie'yi aldığında `pickle.loads` çalışır, `REDUCE` opcode'u `os.system("id > /tmp/pwned")` çağrısını tetikler ve saldırgan Remote Code Execution (RCE) elde eder. Uygulamanın `UserPrefs` beklemesi hiçbir şeyi değiştirmez; `pickle.loads` akıştaki *ne* söyleniyorsa onu kurar.

### Düzeltilmiş kod

Doğru çözüm, "pickle'ı güvenli hale getirmeye çalışmak" değil, güvenilmeyen sınırda **tip inşa eden bir serializer kullanmamaktır**. Oturum tercihi sadece veridir; onu düz veri formatıyla (JSON) taşıyın ve bütünlüğünü bir HMAC imzasıyla koruyun ki saldırgan içeriği değiştiremesin.

```python
# app.py  — DUZELTILMIS SURUM
import base64
import hashlib
import hmac
import json
from flask import Flask, request, make_response

app = Flask(__name__)

# Gercekte bir gizli anahtar yonetim sistemi/ortam degiskeninden gelir.
SECRET_KEY = b"ortamdan-gelen-uzun-rastgele-anahtar-degil-hardcode"

ALLOWED_THEMES = {"light", "dark"}
ALLOWED_LANGS = {"tr", "en"}


def _sign(payload: bytes) -> str:
    return hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest()


def load_prefs(cookie_value: str) -> dict:
    # Bicim: base64(json).imza
    try:
        b64, sig = cookie_value.rsplit(".", 1)
    except ValueError:
        raise ValueError("bicimsiz cookie")

    payload = base64.urlsafe_b64decode(b64)

    # 1) Imzayi deserialize etmeden ONCE, sabit-zamanli karsilastirmayla dogrula
    expected = _sign(payload)
    if not hmac.compare_digest(expected, sig):
        raise ValueError("imza dogrulanamadi")

    # 2) Sadece VERI cozumle; hicbir tip/kod insa edilmez
    data = json.loads(payload)

    # 3) Alanlari beyaz listeye gore dogrula (defensive parsing)
    theme = data.get("theme")
    lang = data.get("lang")
    last_page = data.get("last_page", "/")
    if theme not in ALLOWED_THEMES:
        theme = "light"
    if lang not in ALLOWED_LANGS:
        lang = "tr"
    if not isinstance(last_page, str) or not last_page.startswith("/"):
        last_page = "/"

    return {"theme": theme, "lang": lang, "last_page": last_page}


def save_prefs(prefs: dict) -> str:
    payload = json.dumps(prefs, separators=(",", ":")).encode()
    b64 = base64.urlsafe_b64encode(payload).decode()
    return f"{b64}.{_sign(payload)}"


@app.route("/")
def index():
    cookie = request.cookies.get("prefs")
    if cookie:
        try:
            prefs = load_prefs(cookie)
        except Exception:
            prefs = {"theme": "light", "lang": "tr", "last_page": "/"}
    else:
        prefs = {"theme": "light", "lang": "tr", "last_page": "/"}

    resp = make_response(f"Tema: {prefs['theme']}, Dil: {prefs['lang']}")
    resp.set_cookie("prefs", save_prefs(prefs), httponly=True, samesite="Lax")
    return resp
```

Bu sürümde üç kat savunma vardır ve sıraları önemlidir. Önce imza doğrulanır (deserialize etmeden *önce*), böylece kurcalanmış payload hiç işlenmez. Sonra yalnızca `json.loads` ile *veri* çözümlenir — JSON, tip inşasına ve otomatik callback'e izin vermediği için gadget yüzeyi kökten kapanır. Son olarak alanlar beyaz listeye göre doğrulanır, böylece imza bir şekilde atlansa bile mantıksal kötüye kullanım engellenir.

Dikkat: HMAC imzası tek başına yeterli sanılmamalıdır. İmza, veriyi *değiştirilemez* kılar; ama eğer hâlâ `pickle.loads` kullanıyor olsaydınız ve anahtar sızsaydı, saldırgan yine geçerli imzalı bir kötü pickle üretip RCE elde ederdi. Nitekim .NET ViewState açıklarının klasik hikâyesi tam olarak budur: imzalama vardı, ama anahtar sızınca imza saldırganı durdurmadı. Bu yüzden asıl kazanç, native deserializer'ı sınırdan çıkarmaktan gelir; imza onu tamamlar, yerini tutmaz.

Eğer pickle'ı bir sebeple bırakamıyorsanız (örneğin dahili bir cache), en azından `find_class` override ile bir allow-list dayatın:

```python
import pickle
import io

SAFE_CLASSES = {
    ("__main__", "UserPrefs"),
}

class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in SAFE_CLASSES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"Yasak sinif: {module}.{name}")

def safe_loads(data: bytes):
    return RestrictedUnpickler(io.BytesIO(data)).load()
```

Bu, `os.system` gibi callable'ların çözümlenmesini reddeder. Yine de en sağlıklısı, güvenilmeyen sınırdan pickle'ı tamamen çıkarmaktır.

Aynı yürüyüşün Java karşılığını da kısaca görmek, açığın dile bağlı olmadığını gösterir. Java'da `Serializable` bir sınıf, deserialization sırasında çağrılan özel bir `private void readObject(ObjectInputStream in)` metodu tanımlayabilir; gadget'ların dayanağı budur. Klasik zincir, eski Apache Commons Collections sürümlerindeki `InvokerTransformer` benzeri sınıfların, reflection yoluyla adı sonradan belirlenen bir metodu çağırabilmesine dayanır. Bir `Map`/`Set` inşası tetiklendiğinde transformer zinciri çalışır ve sonunda `Runtime.getRuntime().exec(...)` çağrılır — saldırgan hiçbir yeni sınıf yüklemeden, sadece o kütüphane classpath'te olduğu için komut çalıştırır. Serialized Java verisi hex olarak `AC ED 00 05` (Base64'te `rO0AB...`) sabit magic number'ıyla başlar; trafikte bu imzayı görmek güçlü bir tespit sinyalidir. Java'daki doğru düzeltme de aynı felsefeyi izler: güvenilmeyen sınırda `ObjectInputStream` yerine DTO tabanlı JSON/protobuf kullanmak; bırakılamıyorsa `ObjectInputFilter` (JEP 290) ile sınıf allow-list'i ve derinlik/nesne-sayısı limitleri dayatmaktır.

---

## 2. Gerçek dünya (CVE ile)

Yukarıdaki kavramsal yürüyüş soyut değildir; on yıllardır sahada tekrarlayan bir açık sınıfıdır. Verilen gerçek CVE kayıtlarından üçü, bu açığın iki farklı yüzünü — hem doğrudan RCE'yi hem de "sessiz" bozulma ve DoS'u — güzel gösteriyor.

**CVE-2004-1019 (PHP `unserialize`).** Bu kayıt, PHP 4.3.10 öncesi ve 5.0.2'ye kadar olan sürümlerdeki deserialization kodunun, güvenilmeyen veri `unserialize` fonksiyonuna ulaştığında "information disclosure, double-free ve negatif referans indeksi array underflow" gibi sonuçlar üretebildiğini, denial of service ve keyfi kod yürütmeye kadar gidebildiğini anlatıyor. Bu vaka, güvensiz deserialization'ın iki farklı mekanizmasını aynı anda barındırır. Birincisi, benim 1. bölümde anlattığım "tip/nesne inşası" katmanı (uygulama-seviyesi POP chain'ler); ikincisi, deserializer'ın *kendi bellek yönetiminde* çıkan bug'lar (double-free, underflow). Sahada dersi şudur: `unserialize`'a güvenilmeyen veri vermek, sadece POP chain riski değil, aynı zamanda motorun belleğini bozma riski demektir. Bu yüzden savunma "girdiyi doğrula" ile bitmez; motorun kendisi de o girdiyle boğuşurken çökebilir.

**CVE-2006-4812 ve CVE-2007-1286 (PHP `unserialize`, integer overflow).** Bu iki kayıt aynı ailedendir ve deserializer'ın *ayrıştırma matematiğindeki* zayıflığı gösterir. CVE-2006-4812, PHP 5'te (5.1.6'ya kadar) `unserialize`'a verilen ve çok büyük bir dizi eleman sayısı belirten argümanın, Zend Engine'in `ecalloc` bellek ayırma fonksiyonunda (`Zend/zend_alloc.c`) bir integer overflow tetikleyerek keyfi kod yürütmeye izin verdiğini söyler. CVE-2007-1286 ise PHP 4.4.4 ve öncesinde, `unserialize`'a verilen uzun bir string'in ZVAL referans sayacında (reference counter) overflow tetikleyerek yine keyfi kod yürütmeye yol açtığını belirtir. Bu iki vaka bir savunmacı için çok öğreticidir: burada saldırgan bir "sınıf" ya da "gadget" seçmiyor; sadece serialized biçimdeki *sayısal alanları* (eleman sayısı, string uzunluğu) uç değerlerle dolduruyor ve motorun kendisini çökertiyor. Yani "hangi sınıflar inşa edilebilir?" sorusuyla kurulan allow-list savunması, bu tür motor-içi overflow'lara karşı bir şey yapmaz — bunlara karşı savunma, deserializer'ı güncel tutmak (yamalı sürüm) ve güvenilmeyen veriyi native `unserialize`'a hiç sokmamaktır.

Bu üç PHP CVE'sini yan yana koyunca ortaya net bir tablo çıkar: `unserialize`'ın tehlikesi tek katmanlı değildir. Üst katmanda uygulama sınıflarını kötüye kullanan POP chain'ler (2004-1019'un RCE yüzü), alt katmanda motorun bellek/aritmetik hataları (2006-4812, 2007-1286) vardır. İkisinin de ortak çözümü aynıdır: güvenilmeyen sınırda `unserialize` yerine `json_decode` kullanmak veya en azından `unserialize($data, ['allowed_classes' => false])` ile hiçbir nesnenin örneklenmemesini zorlamak; ve PHP'yi yamalı tutmak.

Bu kayıtların yılları (2004–2007) da bir mesaj verir: güvensiz deserialization yeni bir moda değildir. On yıllardır bilinen, tekrar tekrar keşfedilen ve dilin *tasarım tercihinden* doğan yapısal bir sorundur. Verilen listedeki diğer kayıtlar da (CVE-2003-0791'de Mozilla'nın `script.thaw` ile deserialize edilen string'in native metot çalıştırması; CVE-2005-0223'te Tru64 UNIX Java SDK'sında nesne deserialization'ıyla JVM hang'i; CVE-2004-2779 ve CVE-2005-1643'te bozuk biçimli girdinin OOM/DoS'a yol açması) aynı temayı farklı dillerde tekrar eder: bir bileşen, girdideki yapıya *körlemesine güvenip* onu inşa etmeye kalkarsa, sonuç kod yürütme veya hizmet reddi olur.

---

## 3. Karşılaştırma / karar

Bir sistemde nesne/durum taşımanız gerektiğinde, birkaç yaklaşım arasında seçim yaparsınız. Her birinin takası vardır. Doğru karar, "en güvenli olanı her yerde kullan" değil, tehdit modeline göre en düşük yüzeyi seçmektir.

**Native binary serialization (Java `ObjectInputStream`, .NET `BinaryFormatter`, Python `pickle`).** Avantajı: neredeyse sıfır kod, keyfi nesne grafiklerini otomatik taşır, hızlıdır ve döngüsel referansları çözer. Dezavantajı: tam da bu güç, güvenilmeyen sınırda felakettir — tip inşası + otomatik callback = gadget yüzeyi. **Ne zaman?** Yalnızca tamamen *güvenilen*, aynı güven alanı içindeki bileşenler arasında (ve idealde imzalı/kısıtlı). Kullanıcıya, ağa, cookie'ye, kuyruğa açık hiçbir sınırda kullanılmamalı. .NET'te `BinaryFormatter` Microsoft tarafından resmen güvensiz ilan edilip kaldırma yoluna sokulmuştur; bu tercihin kendisi bir sinyaldir.

**Şemaya bağlı, tip-güvenli formatlar (Protocol Buffers, Avro, Thrift, Cap'n Proto).** Avantajı: veri bir şema tarafından tanımlanır; deserializer girdiye bakıp "hangi tipi kurayım?" diye sormaz, şemadaki sabit tipe göre alanları doldurur. Bu, gadget yüzeyini yapısal olarak kapatır ve ayrıca versiyonlama/uyumluluk sağlar. Dezavantajı: şema tanımlama ve build adımı zorunludur; keyfi/dinamik yapılar için hantaldır. **Ne zaman?** Servisler arası RPC, yüksek hacimli mesajlaşma, güven sınırını aşan yapılandırılmış veri. Performans ve güvenliği birlikte isteyen sistemlerin varsayılanı budur.

**Düz veri formatları (JSON, CSV, düz XML).** Avantajı: insanlarca okunur, her dilde desteklenir, *doğru kullanıldığında* yalnızca skaler/liste/harita taşır ve tip inşa etmez. Dezavantajı: iki gizli tuzak vardır. (1) "Polymorphic" tip çözümlemesini açan ayarlar — Jackson'da gevşek yapılandırma, .NET'te `TypeNameHandling`, Python'da `yaml.load`'un güvensiz loader'ı — JSON/YAML'ı native serialization kadar tehlikeli hale getirir. (2) XML'de external entity (XXE) ve entity expansion (billion laughs) ayrı bir DoS/veri-sızma sınıfıdır. **Ne zaman?** Güvenilmeyen sınırda ilk tercih — ama tip çözümlemesi *kapalı* ve şema doğrulaması *açık* olarak.

**Allow-list ile kısıtlanmış native deserialization.** Native'i bırakamadığınız (eski sistem, mevcut protokol) durumlarda ara çözüm. Java'da `ObjectInputFilter` (JEP 290) ile hem sınıf allow-list'i hem derinlik/nesne-sayısı limitleri; PHP'de `allowed_classes`; .NET'te `SerializationBinder`; Python'da `find_class` override. Avantajı: mevcut protokolü kırmadan yüzeyi daraltır. Dezavantajı: liste bakımı ister; yanlış yapılandırma (deny-list'e kayma) korumayı boşa çıkarır. **Ne zaman?** Geçiş dönemi köprüsü olarak — nihai hedef değil.

Karar için pratik hiyerarşi: (1) Güvenilmeyen sınırda native deserialize *etme*. (2) Yapısal veri gerekiyorsa şemaya bağlı format (protobuf) veya tip-kapalı JSON. (3) Durumu istemciye taşımak zorunda değilsen sunucuda tut, istemciye opak referans ver. (4) Native kaçınılmazsa allow-list + kaynak limiti + imza. (5) Her katmanda en az ayrıcalık ve egress filtering ile RCE'nin patlama yarıçapını küçült.

Deny-list mi allow-list mi tartışması burada net biçimde allow-list lehine kapanır. Deny-list ("bilinen tehlikeli sınıfları engelle") her zaman geriden gelir: `ysoserial`, `ysoserial.net`, `PHPGGC` gibi kataloglar sürekli yeni gadget zincirleri ekler; siz dünkü listeyi engellerken saldırgan bugünkü zinciri kullanır. Allow-list ("yalnızca şu birkaç bilinen DTO'ya izin ver") ise saldırı yüzeyini bilinen-iyi kümesine sabitler ve yarının gadget'ından etkilenmez.

Bir başka tasarım kararı da "durumu nerede tutmalı?" sorusudur ve çoğu zaman en ucuz güvenlik kazancını burası verir. Oturum/nesne durumunu istemciye serialized olarak taşımak yerine sunucu tarafında (session store, Redis, veritabanı) tutup istemciye yalnızca opak, rastgele bir referans (session id) vermek, deserialization yüzeyini tamamen ortadan kaldırır — çünkü saldırganın kurcalayabileceği bir serialized nesne artık istemcide yoktur. Bu yaklaşımın takası, sunucu tarafında durum yönetimi (bellek/store maliyeti, yatay ölçeklemede yapışkan oturum veya paylaşımlı store ihtiyacı) getirmesidir. Ölçek ve gecikme hassasiyeti düşükse bu takas neredeyse her zaman güvenlik lehine verilmelidir; çünkü "istemcide serialized durum yok" garantisi, en güçlü savunmadır. Durumu istemciye taşımak *gerçekten* zorunluysa (stateless mimari tercihi), o zaman düz veri formatı + HMAC + tip kısıtlaması üçlüsüne inersiniz — yani 1. bölümdeki düzeltilmiş koda.

Son bir boyut: performans-güvenlik takası. Native binary serialization çoğu zaman JSON'dan hızlı ve kompakttır; ekipler bu yüzden onu seçer. Ancak güvenilmeyen sınırda bu performans avantajı yanıltıcıdır: tek bir başarılı deserialization RCE'sinin maliyeti, milyonlarca isteğin kazandırdığı milisaniyelerin çok ötesindedir. Performans gerçekten kritikse doğru cevap "native serialization'a geri dön" değil, "şemaya bağlı protobuf/Avro kullan" olur — bu formatlar hem native kadar hızlı/kompakt olabilir hem de tip inşası yapmadıkları için gadget yüzeyi taşımaz. Yani performans ile güvenlik arasında gerçek bir çatışma çoğu zaman *yoktur*; sadece yanlış aday (native serialization) seçildiğinde varmış gibi görünür.

---

## 4. Hata-modu kataloğu

Aşağıdakiler, geliştiricilerin ve savunmacıların bu konuda tekrar tekrar yaptığı tipik hatalardır. Her biri sahada gördüğümüz gerçek desenlerdir.

1. **"JSON kullanıyoruz, güvendeyiz" yanılgısı.** Tehlike formatta değil, tip inşasına izin verip vermediğindedir. Jackson'ın polymorphic tip çözümlemesi, .NET'in `TypeNameHandling`'i veya `yaml.load`'un güvensiz loader'ı açıkken JSON/YAML, native serialization kadar tehlikelidir.

2. **Sadece `unserialize`/`readObject`/`loads` çağrısını grep'lemek.** PHP'de `phar://` sarmalayıcısı, `file_exists`/`fopen`/`getimagesize` gibi masum görünen dosya fonksiyonlarında metadata'yı otomatik unserialize eder. Framework içi dolaylı deserialization yolları da (RMI/JMX, XStream, mesaj dönüştürücüler) görünür bir çağrı olmadan tetiklenir. Statik arama tek başına yetmez.

3. **Deny-list'e güvenmek.** Bilinen kötü sınıfları engellemek, yarın keşfedilecek gadget'a karşı korumasızdır. Allow-list (yalnızca bilinen-iyi tiplere izin) şarttır.

4. **İmzalamayı girdi doğrulamasının yerine koymak.** HMAC veriyi *değiştirilemez* kılar ama anahtar sızarsa çöker (ViewState dersi) ve zaten native deserializer'ı sınırdan çıkarmanın yerini tutmaz. İmza tamamlayıcıdır, çözüm değil.

5. **İmzayı deserialize'dan *sonra* doğrulamak.** Doğru sıra: önce imzayı sabit-zamanlı (`hmac.compare_digest`) doğrula, *sonra* payload'ı çözümle. Ters yaparsanız kurcalanmış payload zaten işlenmiş olur ve deserialization anındaki callback/overflow çoktan tetiklenir.

6. **"Bu sınıfı hiç kullanmıyoruz" savunması.** Gadget'ın uygulama tarafından *çağrılması* gerekmez; classpath/bağımlılıkta *var olması* saldırgan için yeterlidir. Kullanılmayan kütüphaneler saldırı yüzeyidir.

7. **Şifrelemeyi bütünlükle karıştırmak.** Veriyi şifrelemek gizliliği sağlar; ama bazı mod/senaryolarda saldırgan içeriği görmeden değiştirebilir (bit-flipping, padding oracle). Deserialization güvenliği için gereken öncelik *bütünlük ve tip kısıtlamasıdır*, gizlilik değil.

8. **Cache/kuyruk/model dosyalarını "iç kaynak = güvenli" saymak.** Redis, mesaj kuyrukları veya diske `pickle`'lanmış ML modelleri saldırgan tarafından zehirlenebiliyorsa, bunlar güvenilmeyen kaynaktır. Özellikle eğitilmiş model dosyalarını (`pickle`, bazı `.pt`/`.h5` yolları) güvenilmeyen yerden yükleyip `loads` etmek doğrudan RCE demektir. "İç ağ = güven sınırı" varsayımı yanlıştır.

9. **Kaynak limiti koymamak (DoS'u unutmak).** Nesne sayısı, derinlik, dizi boyutu ve toplam byte için limit yoksa; iç içe/dev koleksiyonlar bellek tüketip servisi çökertir. Verilen CVE'lerden CVE-2004-2779 (libid3tag'de UTF-16 deserialization'ının OOM'a kadar döngüye girmesi) ve CVE-2005-1643 (Zoidcom'da büyük boyut değerinin bellek hatası/out-of-bounds okuma) tam olarak bu sınıftır. Java'da `ObjectInputFilter` bu limitleri de destekler.

10. **Deserializer motorunu güncel tutmamak.** POP chain'ler uygulama katmanındadır ama CVE-2006-4812 ve CVE-2007-1286 gibi integer/reference-counter overflow'ları motorun *kendisindedir*. Allow-list bunları durdurmaz; yalnızca yamalı sürüm durdurur. Dil/runtime güncellemesi bir güvenlik kontrolüdür.

11. **En az ayrıcalık ve egress filtering'i atlamak.** Deserialization RCE'sinin ilk adımı çoğu zaman "out-of-band" bir sinyaldir (saldırganın sunucusuna DNS/HTTP isteği — blind exploitation). Dışa giden trafik kısıtlanmamışsa hem doğrulama hem veri sızma kolaylaşır. Uygulamayı düşük yetkiyle, sandbox/container içinde ve egress kısıtlı çalıştırmak patlama yarıçapını küçültür.

12. **Hata mesajlarıyla teknoloji/versiyon sızdırmak.** Deserialization exception'larının stack trace'i, hangi kütüphane ve sürümün classpath'te olduğunu ele verir; bu, saldırganın doğru gadget'ı seçmesini kolaylaştırır. Ayrıntılı hata mesajlarını istemciye dönmeyin, sunucu tarafında loglayın.

---

## Kapanış

Güvensiz deserialization, "bir input doğrulama hatası" olmaktan çok, güçlü ama tehlikeli bir dil özelliğinin yanlış yerde — güvenilmeyen sınırda — açık bırakılmasıdır. Verilen CVE kayıtları on yıldan uzun bir dönemi (2003–2007 ve ötesi) kapsar ve hep aynı dersi verir: bir bileşen girdideki yapıya körlemesine güvenip onu inşa etmeye kalkarsa, sonuç RCE veya DoS olur. En kalıcı çözüm, güvenilmeyen veriyi hiçbir zaman keyfi nesnelere dönüştürmemek; buna mecburseniz hangi tiplerin inşa edilebileceğini sıkı sıkıya sınırlamak, imza ile bütünlüğü korumak, kaynak limiti koymak ve motoru güncel tutmaktır. Bu, yama uygulamaktan çok mimari disiplin gerektiren bir konudur.
