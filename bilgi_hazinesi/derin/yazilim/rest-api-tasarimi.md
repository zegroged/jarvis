# REST API Tasarımı — Derin Dalış: Çözümlü Yürüyüş, Vaka, Karar ve Hata Modları

Bu metin, REST API tasarımının teorik özetinin üzerine oturur. Amaç kavramları tekrar tanımlamak değil, onları gerçek, çalışan kod üzerinde *kırılma noktalarında* göstermektir. Aşağıdaki bölümlerin hepsinde önce hatalı/zafiyetli kod, sonra nedenin anatomisi, sonra düzeltilmiş kod yer alır. Örnekler Python (FastAPI) ve yer yer Node.js (Express) üzerinden verilmiştir; ilkeler dile bağlı değildir.

## 1. Çözümlü yürüyüş: İdempotent olmayan ödeme uç noktasının anatomisi

Somut bir senaryo alalım: bir e-ticaret servisinde sipariş oluşturma ve ödeme alma. Bu, REST'in en çok yara aldığı yerdir çünkü `POST` ne safe ne de idempotenttir ve ağ güvenilmezdir. Ağın güvenilmezliği teorik bir endişe değildir: mobil şebekelerde bir isteğin gönderilip yanıtın kaybolması gündelik bir olaydır. İstemci açısından "istek işlendi ama yanıt kayboldu" ile "istek hiç ulaşmadı" durumları **ayırt edilemez**. İyi bir API bu ayırt edilemezliği tasarımın merkezine koyar; bunu yok sayan API, ilk yoğun trafik gününde çift çekim şikâyetleriyle tanışır.

### 1.1 Zafiyetli/hatalı kod

```python
# app.py — FastAPI, HATALI sürüm
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid

app = FastAPI()
DB_ORDERS = {}          # order_id -> order
DB_CHARGES = []         # kaydedilmiş ödeme çekimleri

class OrderIn(BaseModel):
    user_id: int
    amount: float

@app.post("/orders")
def create_order(body: OrderIn):
    order_id = str(uuid.uuid4())
    # 1) Siparişi kaydet
    DB_ORDERS[order_id] = {"user_id": body.user_id,
                           "amount": body.amount,
                           "status": "paid"}
    # 2) Kart çek (harici ödeme sağlayıcı çağrısı)
    charge_card(body.user_id, body.amount)
    DB_CHARGES.append({"user_id": body.user_id, "amount": body.amount})
    # 3) 200 ile dön
    return {"order_id": order_id, "status": "paid"}

def charge_card(user_id: int, amount: float):
    # Harici ödeme API çağrısını temsil eder — yavaş ve ağ-bağımlı
    ...
```

Bu kod ilk bakışta çalışır. İstemci `POST /orders` gönderir, sipariş oluşur, kart çekilir, `200` döner. Sorun, işlerin yolunda gittiği durumda görünmez.

### 1.2 Sorun neden oluşur

Üç ayrı hata iç içe geçmiş durumda:

**Birincisi, idempotency yokluğu.** İstemci `POST /orders` gönderdi. Sunucu isteği aldı, kartı çekti, ama yanıt istemciye ulaşmadan bağlantı koptu (mobil ağda çok sık). İstemcinin elinde hiçbir kanıt yok: istek işlendi mi, işlenmedi mi? Makul davranış yeniden denemektir. İkinci istek geldiğinde `create_order` yeni bir `order_id` üretir, `charge_card`'ı **tekrar** çağırır. Müşteriden iki kez para çekilir. `POST` idempotent olmadığı için bu davranış "doğru"dur — kusur tasarımdadır.

**İkincisi, yanlış durum kodu.** Yeni bir kaynak yaratıldığında dönmesi gereken kod `201 Created`'dır ve yanıt `Location` header'ı ile yeni kaynağın URI'sini içermelidir. `200` dönmek, ara katmanların (proxy, monitoring) ve istemcinin "kaynak yaratıldı" bilgisini kaybetmesine yol açar.

**Üçüncüsü, atomiklik ihlali.** Sipariş `DB_ORDERS`'a yazıldıktan sonra `charge_card` bir exception fırlatırsa, ortada `status: "paid"` olan ama ödemesi alınmamış bir sipariş kalır. Kayıt sırası ve hata sınırları düşünülmemiş.

### 1.3 Düzeltilmiş/doğru kod

Çözüm, istemcinin ürettiği bir **idempotency key**'i header'da almak, aynı anahtarla gelen ikinci isteği yeni işlem yapmadan ilk sonucu döndürmek, doğru durum kodunu ve `Location` header'ını üretmek, ödeme başarısız olursa sipariş durumunu tutarlı tutmaktır.

```python
# app.py — DÜZELTİLMİŞ sürüm
from fastapi import FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel
import uuid

app = FastAPI()
DB_ORDERS = {}
# idempotency_key -> {"order_id":..., "response":...}
IDEMPOTENCY_STORE = {}

class OrderIn(BaseModel):
    user_id: int
    amount: float

@app.post("/orders", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderIn,
                 response: Response,
                 idempotency_key: str = Header(..., alias="Idempotency-Key")):

    # 1) Anahtar daha önce görüldüyse: ilk sonucu aynen döndür, YENİDEN İŞLEME
    if idempotency_key in IDEMPOTENCY_STORE:
        cached = IDEMPOTENCY_STORE[idempotency_key]
        response.status_code = status.HTTP_200_OK   # tekrar; yeni yaratım değil
        response.headers["Location"] = f"/orders/{cached['order_id']}"
        return cached["response"]

    order_id = str(uuid.uuid4())

    # 2) Önce "pending" durumla kaydet — ödeme başarısızsa tutarlı kalır
    DB_ORDERS[order_id] = {"user_id": body.user_id,
                           "amount": body.amount,
                           "status": "pending"}
    try:
        charge_card(body.user_id, body.amount, idempotency_key)
    except PaymentError as e:
        DB_ORDERS[order_id]["status"] = "payment_failed"
        raise HTTPException(status_code=402, detail=str(e))

    DB_ORDERS[order_id]["status"] = "paid"
    result = {"order_id": order_id, "status": "paid"}

    # 3) Anahtarı sonucuyla birlikte sakla ki tekrar gelirse aynı yanıt dönsün
    IDEMPOTENCY_STORE[idempotency_key] = {"order_id": order_id, "response": result}

    response.headers["Location"] = f"/orders/{order_id}"
    return result


class PaymentError(Exception):
    pass

def charge_card(user_id: int, amount: float, idempotency_key: str):
    # Kritik: idempotency_key'i ödeme sağlayıcısına da GEÇİR.
    # Stripe/Adyen gibi sağlayıcılar Idempotency-Key header'ını doğal destekler;
    # bu, çift çekimi son kalede de engeller.
    ...
```

Dikkat edilecek incelikler: idempotency anahtarı zincirin sonuna kadar taşınır (uygulama katmanı *ve* ödeme sağlayıcısı). Sipariş önce `pending` yazılır, ancak ödeme başarılıysa `paid`'e geçer; böylece kısmi başarısızlık durumunda "ödendi görünen ama ödenmemiş sipariş" oluşmaz. İlk çağrı `201`, aynı anahtarla gelen tekrar çağrı `200` döner — çünkü ikincisi yeni bir kaynak yaratmaz, var olanı raporlar. Gerçek üretimde `IDEMPOTENCY_STORE` bir Redis/veritabanı olmalı ve anahtarlara TTL (örneğin 24 saat) konmalıdır; bellekte tutmak yatay ölçeklemeyi kırar (durumsuzluk ihlali).

Bir eşzamanlılık inceliği daha var: iki istek *aynı anda* aynı anahtarla gelirse, yukarıdaki "kontrol et sonra yaz" (check-then-act) deseni yarış koşuluna açıktır. Üretimde anahtarı benzersiz kısıtlı (unique constraint) bir tabloya `INSERT`'lemek ve ihlalde ikinci isteği bekletip ilkin sonucunu döndürmek gerekir — kontrolü veritabanına yaptırmak, uygulama belleğine değil.

Bir adım daha ileri gidelim ve idempotency anahtarının **gövdeye bağlanması** meselesine değinelim. Diyelim ki istemci aynı `Idempotency-Key` ile ama farklı bir `amount` ile ikinci kez istek gönderdi (bir hata sonucu ya da kötü niyetle). Yukarıdaki basit sürüm, ilk sonucu körü körüne döndürür ve istemci "işlem başarılı" sanır, oysa istediği tutar hiç işlenmemiştir. Sağlam sistemler, anahtarı saklarken orijinal isteğin bir parmak izini (request fingerprint, örneğin gövdenin hash'i) de saklar; aynı anahtarla farklı bir gövde gelirse `422 Unprocessable Entity` döner. Böylece anahtar, "bu tam isteği bir kez işle" garantisine dönüşür, "bu anahtarı taşıyan her şeyi görmezden gel" gevşekliğine değil. Bu ayrım, ödeme sistemlerinde gerçek para kaybı ile veri bütünlüğü arasındaki çizgidir.

Son olarak anahtarın **yaşam süresi** politikasını düşünmek gerekir. Anahtarı sonsuza dek saklarsanız depolama sınırsız büyür; çok kısa tutarsanız (örneğin 5 dakika), istemcinin yavaş bir yeniden deneme döngüsü anahtarın süresi dolduktan sonra çift işlem üretebilir. Pratikte 24 saatlik bir TTL, mobil istemcilerin çevrimdışı kalıp sonra yeniden bağlandığı senaryoları örter ve makul bir denge kurar. TTL süresi, istemcinin en uzun makul yeniden deneme penceresinden uzun olmalıdır.

## 2. Gerçek sistem örneği: ETag ile optimistic concurrency ("lost update" problemi)

İkinci vaka, çok istemcili bir ortamda aynı kaynağın eşzamanlı güncellenmesidir. Bir kullanıcı profili düşünün: iki yönetici aynı anda düzenliyor.

### 2.1 Naif (hatalı) güncelleme

```python
@app.put("/users/{user_id}")
def update_user(user_id: int, body: UserIn):
    DB_USERS[user_id] = body.dict()   # son yazan kazanır
    return DB_USERS[user_id]
```

Yönetici A profili okur (`role=member`), düzenlemeye başlar. Yönetici B de okur, `email`'i değiştirip kaydeder. Sonra A, elindeki *eski* temsili (B'nin e-posta değişikliğini içermeyen) `PUT` ile gönderir. B'nin değişikliği sessizce kaybolur. Buna **lost update** denir. Sunucu iki isteği de `200` ile kabul eder; kimse hatayı fark etmez.

### 2.2 ETag + `If-Match` ile çözüm

Kaynağın her sürümüne bir **ETag** (içerikten türetilmiş bir sürüm etiketi) verilir. İstemci güncellerken elindeki sürümün ETag'ini `If-Match` header'ında gönderir. Sunucudaki güncel ETag farklıysa, istemci eski veriyle çalışıyordur ve istek `412 Precondition Failed` ile reddedilir.

```python
import hashlib, json
from fastapi import FastAPI, Header, HTTPException, Response

app = FastAPI()
DB_USERS = {42: {"email": "a@x.com", "role": "member", "_rev": 1}}

def etag_of(user: dict) -> str:
    # Sürümü içerikten türet — sabit, tekrarlanabilir olmalı
    raw = json.dumps(user, sort_keys=True).encode()
    return '"' + hashlib.sha256(raw).hexdigest()[:16] + '"'

@app.get("/users/{user_id}")
def get_user(user_id: int, response: Response):
    user = DB_USERS.get(user_id)
    if not user:
        raise HTTPException(404)
    response.headers["ETag"] = etag_of(user)
    return user

@app.put("/users/{user_id}")
def update_user(user_id: int,
                body: dict,
                response: Response,
                if_match: str | None = Header(None, alias="If-Match")):
    user = DB_USERS.get(user_id)
    if not user:
        raise HTTPException(404)

    current = etag_of(user)
    if if_match is None:
        # Kör güncellemeyi reddet — istemci sürüm belirtmeli
        raise HTTPException(428, detail="If-Match header zorunlu")
    if if_match != current:
        # İstemci eski bir sürümle çalışıyor
        raise HTTPException(412, detail="Kaynak bu arada değişti; yeniden oku")

    body["_rev"] = user["_rev"] + 1
    DB_USERS[user_id] = body
    response.headers["ETag"] = etag_of(body)
    return body
```

Bu tasarımın gerçek sistemdeki karşılığı şudur: A `If-Match: "abc..."` ile gönderir ama B araya girip kaynağı değiştirmiştir, dolayısıyla sunucudaki ETag artık `"def..."`. A'nın isteği `412` alır; istemci bunu yakalayıp kaynağı yeniden okur, değişiklikleri birleştirir ve tekrar dener. Kimse veri kaybetmez. `428 Precondition Required`, `If-Match` hiç gönderilmediğinde kör üzerine yazmayı önlemek için kullanılır.

Aynı ETag altyapısı okuma tarafında da kazandırır: istemci `If-None-Match: "abc..."` ile GET yaparsa ve kaynak değişmemişse sunucu `304 Not Modified` döner (gövde yok), bant genişliğinden tasarruf edilir. Böylece tek mekanizma hem "lost update"i önler hem de önbellek doğrulaması sağlar.

Burada gözden kaçan bir tasarım kararı, ETag'in **güçlü (strong) mü zayıf (weak) mı** olacağıdır. Yukarıdaki örnekte ETag'i içeriğin sha256 hash'inden ürettik; bu güçlü bir ETag'dir çünkü byte-düzeyinde eşitliği garanti eder. Ancak içeriği her istekte hash'lemek, büyük kaynaklarda pahalıdır. Alternatif, kaynağın bir sürüm sayacını (`_rev`) ya da son güncelleme zaman damgasını ETag olarak kullanmaktır: `W/"rev-7"` gibi zayıf bir ETag, "semantik olarak aynı" demeyi yeterli görür. Karar noktası şudur: byte-tam önbellek doğrulaması (aynı sıkıştırma, aynı serileştirme) gerekiyorsa güçlü ETag; sadece "değişti mi değişmedi mi" bilgisi yeterliyse sürüm sayacına dayalı zayıf ETag daha ucuzdur. Optimistic concurrency için sürüm sayacı zaten yeterlidir ve hash hesaplamaktan çok daha hızlıdır; bu yüzden pratikte `_rev` tabanlı bir ETag çoğu sistem için doğru tercihtir.

Bir uyarı: ETag'i hesaplarken yanıtın *tüm* temsilini hesaba katmalısınız. Eğer kaynağı farklı `Accept` header'larına göre (JSON vs XML) farklı serileştiriyorsanız, aynı `_rev` iki farklı temsile karşılık gelir ve tek bir ETag ikisini de temsil edemez. Bu durumda `Vary: Accept` header'ı ile önbelleğe temsilin içeriğe göre değiştiğini bildirmek ve ETag'i temsil biçimini de içerecek şekilde türetmek gerekir; aksi halde bir istemci XML ETag'i ile JSON önbelleğini yanlışlıkla geçerli sayabilir.

## 3. Karşılaştırma / karar: tasarım seçenekleri ve takasları

Bu bölüm, tek bir "doğru" olmayan kararları takasları üzerinden ele alır.

### 3.1 PUT vs PATCH — tam değiştirme mi, kısmi güncelleme mi

`PUT` tam değiştirmedir ve **idempotenttir**: aynı temsili on kez göndermek kaynağı hep aynı hale getirir. Bedeli, istemcinin kaynağın *tamamını* göndermesi gerektiğidir; göndermediği alan varsayılana döner ya da silinir. `PATCH` sadece değişen alanları taşır ama semantiği patch biçimine bağlıdır ve garantili idempotent değildir.

Kısmi güncellemede iki format çatışır:

- **JSON Merge Patch (RFC 7396)**: Basit. `{"email": "yeni@x.com"}` gönderirsiniz, sadece email değişir. Ama `null` çift anlamlıdır: `{"nickname": null}` "nickname alanını sil" mi demek, yoksa "değerini null yap" mı? Merge Patch bunu "sil" olarak yorumlar; bu da bir alanı gerçekten `null`'a set etmeyi imkânsız kılar.
- **JSON Patch (RFC 6902)**: Operasyon tabanlı: `[{"op":"replace","path":"/email","value":"..."}, {"op":"add","path":"/tags/-","value":"vip"}]`. İfade gücü yüksektir, `null` belirsizliği yoktur, ama `add ...tags/-` gibi bir ekleme operasyonu idempotent değildir (iki kez uygularsan iki kez ekler).

Karar: alan-değeri tabanlı basit güncellemeler için Merge Patch, dizi/koleksiyon üzerinde hassas operasyonlar veya `null`-set gereksinimi için JSON Patch. Idempotency kritikse Patch operasyonlarını ETag `If-Match` ile veya idempotency key ile korumaya al.

Pratik bir ek: birçok ekip PATCH'in karmaşıklığından kaçınmak için "PUT ama esnek" denilen bir orta yol seçer — istemci tam temsili gönderir ama sunucu göndermeyen alanları eskisiyle birleştirir. Bu, adı PUT olan ama semantiği PATCH olan bir uçtur ve tam da özette uyarılan tuzaktır: idempotency garantisini korur gibi görünür ama "tam değiştirme" sözleşmesini sessizce bozar. Bir alanı gerçekten silmek isteyen istemci artık bunu yapamaz. Sonuç olarak method adı ile davranışın uyuşması, dokümantasyondan daha güçlü bir sözleşmedir; PUT diyorsanız tam değiştirin, birleştirme yapacaksanız PATCH deyin.

### 3.2 Sayfalama: offset vs cursor (keyset)

| Kriter | Offset/limit | Cursor (keyset) |
|---|---|---|
| Uygulama kolaylığı | Yüksek | Orta |
| "Sayfa 50'ye atla" | Mümkün | Mümkün değil |
| Büyük veride performans | Kötüleşir (derin offset yavaş) | Sabit, hızlı |
| Araya ekleme/silmede tutarlılık | Bozulur (page drift) | Dayanıklı |
| Toplam sayfa sayısı gösterme | Kolay | Zor/pahalı |

Karar kuralı: sayfa numaralı klasik yönetim panelinde ve küçük-orta veride offset yeterlidir. Sonsuz kaydırma, akış (feed), büyük ve sık değişen veri kümesinde cursor tercih edilir. Cursor için sıralama anahtarı **benzersiz ve stabil** olmalı; sadece `created_at` yeterli değildir (aynı milisaniyede iki kayıt varsa öğe atlanır), `(created_at, id)` bileşik anahtar kullanılır.

### 3.3 Versiyonlama yeri: URI path vs header (content negotiation)

`/v1/users` gibi URI path versiyonlama en görünür ve keşfedilebilir olandır; tarayıcıdan test edilir, cache anahtarı doğal olarak versiyonu içerir. Purist itiraz, aynı kavramsal kaynağın iki URI'ya sahip olmasıdır. Header/media-type versiyonlama URI'yi sabit tutar ama keşfedilebilirliği düşürür ve basit test zorlaşır. Karar: kamuya açık, geniş kitleli API'lerde keşfedilebilirlik ağır bastığından path; iç ve olgun ekipler arası API'lerde media-type makul. Her hâlde altın kural, versiyonu **yalnızca bozan değişikliklerde** artırmaktır — non-breaking eklemeler (yeni opsiyonel alan, yeni endpoint) versiyon gerektirmez.

### 3.4 Hata gövdesi: ad-hoc vs RFC 9457 (Problem Details)

Her endpoint'in kendi hata biçimini uydurması, istemcinin genel hata işleyici yazamamasına yol açar. RFC 9457 (eski adıyla RFC 7807 Problem Details) standart bir zarf sunar: `type`, `title`, `status`, `detail`, `instance` alanları ve genişletilebilir ek alanlar. Somut bir örnek:

```json
{
  "type": "https://api.example.com/errors/insufficient-funds",
  "title": "Yetersiz bakiye",
  "status": 402,
  "detail": "Hesap bakiyesi 50.00, gereken tutar 250.00",
  "instance": "/orders/17",
  "balance": 50.00,
  "required": 250.00
}
```

Buradaki `type`, makine tarafından dallanılacak kararlı bir tanımlayıcıdır (URI, dokümantasyona da işaret edebilir); `title` insan-okunur sabit bir başlık; `detail` isteğe özgü açıklama; `balance`/`required` ise genişletme alanlarıdır. İstemci `type` üzerinden kod yazar, `detail`'i log'a basar. Karar: yeni sistemlerde RFC 9457 varsayılan olmalı; kendi ad-hoc yapını icat etmenin tek gerekçesi mevcut geniş bir istemci tabanının başka biçime kilitli olmasıdır. Kritik bir kural, `type`'ı asla lokalize etmemek (dil bağımsız kalmalı) ve HTTP durum kodu ile gövde `status` alanını her zaman tutarlı tutmaktır — ikisi çeliştiğinde ara katmanlar ve istemciler farklı davranır.

## 4. Hata-modu katalogu

Aşağıdaki hatalar üretimde tekrar tekrar görülür. Her biri bir-iki cümlelik teşhisle verilmiştir.

1. **GET ile durum değiştirmek.** `GET /orders/17/cancel` gibi safe olmayan bir eylemi GET arkasına koymak; bir web crawler, prefetcher ya da link önizleyici siteyi tararken bu bağlantıları çağırıp veriyi bozar. GET her zaman yan etkisiz kalmalı.

2. **Her şeyi `200 OK` ile dönüp hatayı gövdede saklamak.** `{"success": false}` gibi bir alanla hata bildirmek; proxy, monitoring ve otomatik retry katmanları isteği başarılı sanar, gerçek hata oranları görünmez olur ve HTTP'nin sözleşme katmanı çöker.

3. **`PUT`'u kısmi güncelleme için kullanmak.** PUT tam değiştirme olduğundan gövdede göndermediğiniz alanlar silinir/varsayılana döner; kullanıcı sadece email güncellemek isterken rolünü ve tercihlerini sıfırlar. Kısmi için PATCH gerekir.

4. **Idempotency key'i atlamak.** Özellikle `POST` ile ödeme/oluşturma işlemlerinde ağ kesintisinde istemci yeniden dener ve çift kayıt/çift çekim oluşur. İstemci üretimli anahtar + sunucu tarafı benzersizlik kısıtı şarttır.

5. **`401` ile `403`'ü karıştırmak.** `401` "kimliğini kanıtla" (unauthenticated), `403` "kimliğin var ama izin yok" (unauthorized) demektir; karıştırmak istemciyi gereksiz yere login'e yönlendirir veya var olan yetki hatasını kimlik sorunu sanır.

6. **Aşırı iç içe URI.** `/users/42/orders/17/items/3/product/reviews/9` gibi derin hiyerarşi bakımı imkânsızlaştırır ve kırılgan yapar; tekil erişilebilen kaynak kendi kök yolundan (`/reviews/9`) sunulmalı, iç içe geçme bir-iki seviyeyle sınırlanmalı.

7. **Fiil tabanlı URI.** `/createOrder`, `/getUserById` gibi yollar method semantiğini yok sayar ve endpoint sayısını patlatır; fiil HTTP method'unun, isim URI'nin işidir.

8. **Durumsuzluğu ihlal etmek.** Çok adımlı bir işlemin ara durumunu sunucu belleğinde tutmak (sticky session gerektirir), yatay ölçeklemeyi kırar; durum istemcide ya da paylaşılan kalıcı katmanda (DB, dağıtık cache) olmalı.

9. **Optimistic concurrency'yi ihmal etmek.** ETag/`If-Match` olmadan eşzamanlı `PUT`'larda "son yazan kazanır" ve lost update sessizce veri kaybettirir; sürüm kontrolü olmayan güncelleme uçları eşzamanlı yükte tehlikelidir.

10. **Hata yanıtlarında hassas bilgi sızdırmak.** Stack trace, SQL sorgusu, iç servis adresleri ya da dosya yollarını `5xx` gövdesinde istemciye göndermek saldırgana keşif haritası verir; istemciye kararlı bir kod + genel mesaj, ayrıntı ise yalnızca log'a.

11. **`5xx`/`429` ile `4xx`'i retry açısından ayırmamak.** İstemci `400`/`422` gibi kalıcı hataları yeniden denerse aynı hatayı sonsuza dek alır; sadece `5xx` ve `429` (tercihen `Retry-After` sinyaliyle, exponential backoff'la) yeniden denenmelidir.

12. **Pydantic/şema doğrulamasını atlayıp ham gövdeye güvenmek.** Gelen JSON'u doğrulamadan doğrudan veri katmanına geçirmek, tip karışıklığı, mass-assignment (istemcinin `is_admin: true` enjekte etmesi) ve enjeksiyon zafiyetlerine kapı açar; her girdi şema ile doğrulanıp beyaz listeye indirgenmeli.

13. **Sözde-koleksiyon dönüşlerinde zarfsız ham dizi.** Üst düzeyde çıplak JSON dizisi (`[ ... ]`) döndürmek, ileride sayfalama/meta bilgisi eklemeyi bozan değişikliğe dönüştürür; koleksiyonu `{"data": [...], "next": "..."}` gibi bir zarfla dönmek geleceğe dönük esneklik sağlar.

---

Bütün bu hataların ortak kökü, HTTP'yi yalnızca bir taşıma borusu olarak görüp semantiğini yok saymaktır. REST'in kazandırdığı öngörülebilirlik, method'ların safe/idempotent özelliklerini, durum kodlarının sözleşme rolünü ve koşullu isteklerin eşzamanlılık garantisini bilinçli kullanmaktan doğar. Her tasarım kararında "bu davranış ağ koptuğunda, iki istemci çakıştığında ve bir crawler uğradığında ne yapar?" sorusunu sormak, sağlam bir API ile kırılgan bir API arasındaki farktır.

Son bir sentez: bu metindeki iki çözümlü yürüyüş — idempotency key'li ödeme ve ETag'li optimistic concurrency — aslında aynı temel probleme, farklı iki yüzden bakar. İlki zaman ekseninde tekrarı (aynı istemci, aynı isteği iki kez) güvenli kılar; ikincisi uzay ekseninde çakışmayı (iki istemci, aynı kaynağı aynı anda) güvenli kılar. HTTP her ikisi için de yerleşik mekanizmalar (idempotency semantiği, koşullu istek header'ları, durum kodları) sunar; bize düşen bunları icat etmek değil, doğru yerde kullanmaktır. Bir API'yi "RESTful" yapan, HAL zarfları ya da mükemmel URI'lar değil, bu tür kenar durumlarında öngörülebilir ve doğru davranmasıdır. Richardson Maturity Model'in seviyelerini bir hedef listesi gibi kovalamak yerine, sisteminizin gerçek yük ve hata desenleri altında nasıl davrandığını ölçüp bilinçli kararlar vermek, olgun API tasarımının özüdür.
