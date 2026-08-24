# Dağıtık Sistem Temelleri — Derin Dalış

Bu metin, dağıtık sistem kavramlarını teorik özetten çıkarıp klavyenin başına oturtur. Amaç, "ağ güvenilmezdir" cümlesini duymak değil; bu cümlenin çalışan bir kod bloğunda tam olarak nasıl veri kaybına, çift ödemeye ve split-brain'e dönüştüğünü görmek, sonra da onu satır satır düzeltmektir. Örnekler Python ve Go ile yazıldı; hepsi gerçek, çalışır kod niyetiyle kurgulandı ve gerçek üretim sistemlerinde tam olarak bu şekilde karşınıza çıkar.

## 1. Çözümlü yürüyüş: "Bakiyeye ekle" retry'ında çift ödeme

Somut bir senaryoyla başlayalım. Bir ödeme servisi var; istemci bir HTTP çağrısıyla "bu kullanıcının cüzdanına 100 TL yükle" diyor. Servis basit görünüyor.

### Zafiyetli kod

```python
# payment_service.py — ZAFIYETLI SÜRÜM
from flask import Flask, request, jsonify
import psycopg2

app = Flask(__name__)

def get_conn():
    return psycopg2.connect("dbname=wallet user=app host=db")

@app.route("/topup", methods=["POST"])
def topup():
    data = request.get_json()
    user_id = data["user_id"]
    amount = data["amount"]

    conn = get_conn()
    cur = conn.cursor()
    # Doğrudan "ekle": relative bir işlem
    cur.execute(
        "UPDATE wallets SET balance = balance + %s WHERE user_id = %s",
        (amount, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"})
```

İstemci tarafı da makul görünüyor: bir yanıt gelmezse tekrar deniyor.

```python
# client.py — ZAFIYETLI SÜRÜM
import requests

def topup(user_id, amount):
    for attempt in range(3):
        try:
            r = requests.post(
                "http://payments/topup",
                json={"user_id": user_id, "amount": amount},
                timeout=2.0,
            )
            if r.status_code == 200:
                return
        except requests.exceptions.Timeout:
            continue  # yeniden dene
    raise RuntimeError("topup başarısız")
```

Bu kod çoğu zaman "çalışır". Sorun, çalışmadığı anlarda sessizce yanlış yapmasıdır.

### Sorun neden oluşuyor

Şu diziyi izleyin: istemci `/topup` çağrısını yapar. Sunucu isteği alır, `balance = balance + 100` UPDATE'ini işler, `commit` eder — yani **iş bitmiştir, para yüklenmiştir**. Ama tam commit'ten sonra, HTTP yanıtı istemciye dönerken ağ hıçkırır ve yanıt kaybolur. İstemci 2 saniye bekler, `Timeout` yakalar ve `continue` ile ikinci kez aynı isteği gönderir. Sunucu bunu **yepyeni bir istek** sanır ve bakiyeye 100 TL daha ekler. Kullanıcı 100 TL yükledi, hesabına 200 TL geçti.

Kök neden özetteki ayırt edilemezlik ilkesidir: istemci, "istek hiç ulaşmadı" ile "istek ulaştı, işlendi, ama yanıt kayboldu" durumlarını ayırt edemez. Timeout gördüğünde tek makul davranışı retry'dır; ama işlem `balance + amount` gibi **relative (görece)** olduğundan retry idempotent değildir ve tekrar zarar verir. Bu, güvenilmez ağ + relative işlem + retry üçlüsünün klasik tuzağıdır.

### Düzeltilmiş kod

Çözüm bir idempotency anahtarıdır: her mantıksal işlem benzersiz bir kimlik taşır, sunucu bu kimliği daha önce görüp görmediğini **atomik** olarak kontrol eder.

```python
# payment_service.py — DÜZELTİLMİŞ SÜRÜM
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.errors import UniqueViolation

app = Flask(__name__)

def get_conn():
    return psycopg2.connect("dbname=wallet user=app host=db")

@app.route("/topup", methods=["POST"])
def topup():
    data = request.get_json()
    user_id = data["user_id"]
    amount = data["amount"]
    idem_key = request.headers["Idempotency-Key"]  # istemci üretir

    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # 1) Anahtarı REZERVE et. Aynı anahtar ikinci kez gelirse
        #    UNIQUE constraint patlar => bu bir retry'dır.
        cur.execute(
            "INSERT INTO idempotency_keys (key, user_id, status) "
            "VALUES (%s, %s, 'in_progress')",
            (idem_key, user_id),
        )
        # 2) Asıl iş: anahtar ekleme ile AYNI transaction içinde.
        cur.execute(
            "UPDATE wallets SET balance = balance + %s WHERE user_id = %s",
            (amount, user_id),
        )
        cur.execute(
            "UPDATE idempotency_keys SET status = 'done' WHERE key = %s",
            (idem_key,),
        )
        conn.commit()
        return jsonify({"status": "ok"})
    except UniqueViolation:
        # Anahtar zaten var: bu istek daha önce (belki de başarıyla)
        # işlenmiş. İşi TEKRAR YAPMA; idempotent yanıt dön.
        conn.rollback()
        return jsonify({"status": "ok", "duplicate": True})
    finally:
        cur.close()
        conn.close()
```

```sql
-- şema
CREATE TABLE idempotency_keys (
    key      TEXT PRIMARY KEY,          -- UNIQUE otomatik
    user_id  BIGINT NOT NULL,
    status   TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

İstemci de anahtarı **retry döngüsünün dışında bir kez** üretmeli — döngü içinde üretirse her deneme farklı anahtar taşır ve idempotency yine bozulur:

```python
# client.py — DÜZELTİLMİŞ SÜRÜM
import requests, uuid

def topup(user_id, amount):
    idem_key = str(uuid.uuid4())  # DÖNGÜNÜN DIŞINDA: her deneme aynı anahtar
    for attempt in range(3):
        try:
            r = requests.post(
                "http://payments/topup",
                json={"user_id": user_id, "amount": amount},
                headers={"Idempotency-Key": idem_key},
                timeout=2.0,
            )
            if r.status_code == 200:
                return
        except requests.exceptions.Timeout:
            continue
    raise RuntimeError("topup başarısız")
```

Kritik detay: anahtarın INSERT'i, bakiye UPDATE'i ve `status='done'` işareti **tek bir transaction** içinde. Böylece "para eklendi ama anahtar kaydedilmedi" gibi bir ara durum fiziksel olarak oluşamaz — commit ya ikisini birden yapar ya hiçbirini. UNIQUE PRIMARY KEY, iki eşzamanlı retry'ın ikisinin birden INSERT'i geçmesini de engeller: ikincisi mutlaka `UniqueViolation` alır. Atomiklik burada veritabanının işidir; uygulama kodu onu emülе etmeye çalışmamalıdır.

Bir incelik daha: `status='in_progress'` sütunu neden var? İlk istek işi yaparken çökerse, anahtar `in_progress` kalır. Naif tasarım, `in_progress` anahtar için retry'ı hemen "duplicate" sayıp asıl işi hiç yapmadan `ok` döner ve para hiç yüklenmez. Olgun tasarım, `in_progress` kayıtlara bir zaman aşımı koyup (örneğin ilk işlemin makul süresinden uzun) süresi geçmişse işi güvenle yeniden yürütür — bu yüzden asıl işin de idempotent olması gerekir (aşağıdaki hata-modu kataloğuna bakın).

Bu örneğin öğrettiği asıl ders, yüzeydeki "UUID ekle" değil, altındaki üç prensiptir. Birincisi, mantıksal işlemin sınırını doğru çizmek: idempotency birimi tek bir SQL cümlesi değil, kullanıcının kafasındaki tek bir "yükleme" eylemidir; anahtar bu eylemin ömrü boyunca sabit kalmalıdır. İkincisi, kontrol-yap-kaydet üçlüsünün asla ayrılamaması: bu üçlü ayrı transaction'lara bölünürse, tam aralarında bir çökme her zaman tutarsız bir ara durum bırakır. Üçüncüsü, "başarı" ile "çöktü ama belki başardı" durumlarını veritabanının otoritesine havale etmek: uygulama kodu bunu bellekte takip etmeye çalıştığında, process yeniden başladığında o bellek uçtuğu için garanti de uçar. Kalıcı, atomik, benzersiz kısıtlı bir tablo bu garantinin tek güvenilir taşıyıcısıdır.

## 2. Gerçek sistem örneği: Kafka'da "exactly-once" tüketici

Özet, saf exactly-once teslimatın imkânsıza yakın olduğunu, gerçekte hedeflenenin **exactly-once processing** olduğunu söylüyordu. Bunun üretimdeki en yaygın hâli bir Kafka tüketicisidir. Klasik hata, "auto-commit" ile offset yönetmektir.

### Zafiyetli tüketici

```python
# consumer.py — ZAFIYETLI: at-most-once veya duplicate riski
from confluent_kafka import Consumer

c = Consumer({
    "bootstrap.servers": "kafka:9092",
    "group.id": "order-processor",
    "enable.auto.commit": True,        # offset arka planda otomatik commit
    "auto.commit.interval.ms": 5000,
})
c.subscribe(["orders"])

while True:
    msg = c.poll(1.0)
    if msg is None:
        continue
    order = parse(msg.value())
    charge_customer(order)   # DIŞ ETKİ: müşteriyi tahsil et
    ship_order(order)        # DIŞ ETKİ: kargo tetikle
```

Burada iki ayrı felaket senaryosu var. Birincisi: `charge_customer` çalıştı ama tam ondan sonra process çöktü ve offset henüz commit edilmemişti (auto-commit 5 saniyede bir). Yeniden başlayınca aynı mesaj tekrar gelir, müşteri **iki kez** tahsil edilir. İkincisi: auto-commit tam işi yapmadan önce offset'i commit etti; process çökerse mesaj **hiç** işlenmez, sipariş kaybolur. Auto-commit, işleme ile offset commit'i arasındaki bağı kopardığı için ikisinden birini garanti edemez.

### Düzeltilmiş tüketici: idempotent işleme + manuel offset

Doğru yaklaşım özetteki iki tekniği birleştirir: teslimatı at-least-once bırak (offset'i işten **sonra** commit et), işlemenin etkisini idempotent yap (mesaj kimliğini kaydet).

```python
# consumer.py — DÜZELTİLMİŞ: effectively-once
from confluent_kafka import Consumer
import psycopg2

c = Consumer({
    "bootstrap.servers": "kafka:9092",
    "group.id": "order-processor",
    "enable.auto.commit": False,   # offset'i BİZ yöneteceğiz
})
c.subscribe(["orders"])

def process(order, conn):
    cur = conn.cursor()
    # Mesajın kendine ait deterministik bir kimliği var (event_id).
    # İşlenmişse bir daha işleme.
    cur.execute(
        "INSERT INTO processed_events (event_id) VALUES (%s) "
        "ON CONFLICT (event_id) DO NOTHING RETURNING event_id",
        (order["event_id"],),
    )
    if cur.fetchone() is None:
        return False   # zaten işlenmiş -> atla, ama offset yine commit edilir

    # İş yükünü, kimlik kaydıyla AYNI transaction içinde yap.
    cur.execute(
        "UPDATE customers SET balance = balance - %s WHERE id = %s",
        (order["amount"], order["customer_id"]),
    )
    cur.execute(
        "INSERT INTO shipments (order_id, status) VALUES (%s, 'queued')",
        (order["order_id"],),
    )
    return True

while True:
    msg = c.poll(1.0)
    if msg is None:
        continue
    order = parse(msg.value())
    conn = get_conn()
    conn.autocommit = False
    try:
        process(order, conn)
        conn.commit()          # 1) önce DB transaction'ı commit
        c.commit(msg)          # 2) SONRA offset commit
    except Exception:
        conn.rollback()
        # offset commit ETMEDİK => mesaj tekrar gelecek => güvenli retry
    finally:
        conn.close()
```

Sıralamanın anlamı hayatidir: **önce iş, sonra offset**. Eğer DB commit'i geçtikten sonra ama `c.commit(msg)` çağrısından önce çökersek, mesaj tekrar gelir; ama `processed_events` tablosundaki `ON CONFLICT DO NOTHING` sayesinde iş ikinci kez yapılmaz, tüketici mesajı atlar ve bu kez offset'i commit eder. Yani duplicate teslimat vardır ama duplicate **etki** yoktur. Bu tam olarak "at-least-once teslimat + idempotent işleme = effectively-once" denklemidir.

Dikkat: `charge_customer` ve `ship_order` yukarıda DB satırlarına indirgendi. Gerçekte kargo tetiklemek bir dış API çağrısıysa, o çağrının kendisi de idempotency anahtarıyla korunmalıdır (transactional outbox deseni tam bunun için vardır: dış çağrıyı doğrudan yapmak yerine aynı transaction'da bir `outbox` tablosuna yazarsınız, ayrı bir yayıcı process onu at-least-once ve idempotent şekilde dünyaya iter).

Bu tasarımın neden dış çağrıyı transaction'ın içine sokmadığına dikkat edin. Bir HTTP çağrısını veritabanı transaction'ının içinde yapmak, ilk bakışta "her şey atomik olsun" diye cazip görünür ama gerçekte iki ayrı felaket doğurur. Birincisi, dış çağrı yavaşsa veya asılı kalırsa transaction o süre boyunca açık kalır, satır kilitlerini tutar ve veritabanı bağlantı havuzunu tüketir; birkaç yavaş dış çağrı tüm servisi kilitleyebilir. İkincisi ve daha sinsisi, dış çağrı başarıyla döndükten sonra ama `commit`'ten önce process çökerse, dünyada gerçekleşmiş bir yan etki (müşteri tahsil edildi) veritabanında hiç iz bırakmaz — çünkü transaction geri alındı. Outbox deseni bu ikilemi, dış çağrıyı transaction sınırının **dışına** taşıyıp yerine transaction içinde yalnızca "şu çağrı yapılmalı" niyetini kalıcılaştırarak çözer; niyet güvenle kaydedildikten sonra ayrı bir süreç onu idempotent biçimde gerçekleştirir. Böylece "yerel DB durumu" ile "dış dünyaya gönderilen mesaj" arasındaki tutarlılık, iki farklı sistem üzerinde dağıtık bir commit denemeden sağlanır — ki iki farklı sistemi tek atomik adımda commit etmek (dual write problemi) tam olarak dağıtık sistemlerin çözemediği şeydir.

## 3. Karşılaştırma / karar: hangi tutarlılık ve koordinasyon modeli?

Dağıtık sistemde her problem için "en iyi" bir cevap yoktur; her seçim bir takas taşır. En sık verilen üç kararı ve takaslarını ele alalım.

### Güçlü tutarlılık (consensus) vs. eventual consistency

**Raft/Paxos temelli güçlü tutarlılık**, her okumanın en son yazılan değeri görmesini garanti eder ama bunun bedeli her yazma için çoğunluk onayı beklemek, yani gecikme ve sınırlı yazma throughput'udur. Ağ bölünmesinde azınlık taraf hizmet veremez (CAP üçgeninde tutarlılığı seçip erişilebilirlikten ödün verirsiniz).

**Eventual consistency** (örneğin Dynamo tarzı, vektör saatleriyle çakışma tespiti yapan sistemler) her node'un yerel yazma kabul etmesine izin verir; erişilebilirlik ve düşük gecikme yüksektir, ama iki node aynı anahtara farklı değer yazabilir ve bir uzlaştırma (conflict resolution) stratejisi gerektirir.

Karar kuralı: Veri **doğruluk-kritik ve düşük hacimliyse** (lider kimliği, konfigürasyon, hesap bakiyesinin otoritesi, kilit sahipliği) güçlü tutarlılık kullanın — burada yanlış bir değer felakettir, ekstra gecikme kabul edilebilir. Veri **yüksek hacimli ve geçici tutarsızlığa toleranslıysa** (beğeni sayısı, sepet, aktivite akışı, öneri sayaçları) eventual consistency seçin — kullanıcı 200 ms sonra güncellenen bir beğeni sayacını umursamaz, ama yavaş bir sepet dönüşüm oranını düşürür.

### Kendi consensus'unu yazmak vs. hazır koordinasyon servisi

Cazip görünse de sıfırdan consensus yazmak neredeyse her zaman yanlış karardır. Doğru yaptığınızı sandığınız algoritmanın, yalnızca belirli bir mesaj sırası + belirli bir çökme anında ortaya çıkan ve **sessizce commit edilmiş veri kaybına** yol açan bir köşe durumu olması çok olasıdır; bu tür hatalar aylarca gizlenir. Takas: hazır bir koordinasyon servisi (Raft/ZAB temelli) operasyonel bağımlılık ve biraz gecikme ekler, ama on yıllardır sınanmış doğruluk verir. Kural: koordinasyon primitiflerini (lider seçimi, dağıtık kilit, üyelik) bu servise devredin; kendi iş mantığınızı onun verdiği kararların üstüne kurun.

### Optimistik vs. pesimistik eşzamanlılık kontrolü

Aynı kaydı güncelleyecek iki istek için iki strateji vardır. **Pesimistik kilit** (satırı `SELECT ... FOR UPDATE` ile kilitlemek) çakışmayı baştan engeller ama kilit tutulduğu sürece diğerlerini bloklar ve dağıtık ortamda kilit sahibinin çökmesi tehlikelidir (kilit sonsuza asılı kalabilir; bu yüzden lease/TTL gerekir). **Optimistik kilit** (bir `version` sütunu tutup `UPDATE ... WHERE version = beklenen` yapmak, etkilenen satır 0 ise retry) çakışma **nadirse** çok daha hızlıdır çünkü kilit tutmaz; ama çakışma **sıksa** sürekli retry israfı yaratır. Karar: çakışma olasılığı düşükse optimistik, kaçınılmaz ve maliyetliyse pesimistik. Aşağıdaki optimistik kontrol örneği, tek başına önemli bir hata sınıfını da kapatır:

```sql
-- Optimistik eşzamanlılık: lost update'i önler
UPDATE accounts
SET balance = %(new_balance)s, version = version + 1
WHERE id = %(id)s AND version = %(expected_version)s;
-- etkilenen satır 0 ise: başka biri araya girdi, oku ve yeniden dene
```

### Dağıtık kilit: lease + fencing token

Pesimistik kilidi dağıtık ortamda kullanacaksanız, "kilit sahibi çökerse ne olur" sorusunu çözmek zorundasınız. Çözüm iki parçalıdır ve ikisi birden gereklidir. Birincisi kilide bir **lease (kira süresi)** vermek: kilit belirli bir süre sonra otomatik serbest kalır, böylece çökmüş bir sahip sistemi sonsuza kilitlemez. Ama lease tek başına yetmez ve tam burada geliştiricilerin en çok gözden kaçırdığı incelik yatar: lease dolduğunda eski sahip **hâlâ çalışıyor** ama duraklamış (uzun bir GC pause, ağ gecikmesi veya disk beklemesi) olabilir. Bu sırada lease başkasına verilir, sonra eski sahip uyanıp "bende hâlâ kilit var" sanarak yazma yapar. Artık iki taraf da kendini kilit sahibi sanıyordur.

İkinci parça **fencing token** bu senaryoyu kapatır: kilit her verildiğinde monoton artan bir sayı üretilir ve korunan kaynak, kendisine gelen her yazmada token'ı kontrol edip daha küçük (eski) token'lı yazmayı reddeder.

```python
# Fencing: kaynak, gördüğü en büyük token'dan küçük yazmayı reddeder
def write_with_fence(resource, token, data):
    if token <= resource.last_seen_token:
        raise StaleTokenError("eski kilit sahibi, yazma reddedildi")
    resource.last_seen_token = token
    resource.data = data
```

Uyuyup geç kalan eski sahip token=33 taşırken, yeni sahip token=34 ile çoktan yazmıştır; kaynak 33'ü görünce reddeder. Lease "çökmeyi tolere et" der, fencing token "duraklamayı tolere et" der; ikisi olmadan dağıtık kilit güvenli değildir.

## 4. Hata-modu kataloğu

Geliştiricilerin dağıtık sistemlerde tekrar tekrar düştüğü tipik hatalar:

1. **Retry'ı idempotency olmadan eklemek.** En yaygın hata. Timeout görünce körlemesine yeniden denemek, relative bir işlemi (bakiyeye ekle, sayaç artır, e-posta gönder) çift çalıştırır. Retry ve idempotency ayrılmaz bir ikilidir; birini ekliyorsanız diğeri zorunludur.

2. **Idempotency anahtarını retry döngüsünün içinde üretmek.** Her deneme farklı UUID taşırsa sunucu her birini yeni istek sanır ve idempotency hiç devreye girmez. Anahtar, mantıksal işlem başına bir kez, döngü dışında üretilmelidir.

3. **Süre ölçümünü duvar saatiyle (wall clock) yapmak.** `end_time - start_time` hesabını sistem saatiyle yapmak, NTP saati geriye ayarladığında negatif süre üretir ve timeout mantığını çökertir. Süre için daima monotonik saat kullanın.

4. **İki node'un saatinin eşit olduğunu varsaymak.** "Timestamp'i büyük olan daha yeni yazmadır, o kazanır" (last-write-wins) mantığı, saat kaymasıyla eski bir yazmanın yeni bir yazmayı ezmesine ve sessiz veri kaybına yol açar. Sıralama için mantıksal saat (Lamport/vektör) kullanın.

5. **Yan etkileri idempotency kapsamının dışında bırakmak.** DB yazması idempotent ama aynı işlemdeki e-posta/SMS/webhook çağrısı korunmasızsa, retry ikinci bir e-posta yollar. Idempotency, dış dünyaya olan tüm etkileri kapsamalıdır (outbox deseni).

6. **Auto-commit ile offset yönetip işleme garantisini kaybetmek.** Kafka/kuyruk tüketicisinde offset'i iş bitmeden veya işten bağımsız commit etmek, ya duplicate işleme ya mesaj kaybı üretir. Offset her zaman işten **sonra**, tercihen işin sonucuyla ilişkili biçimde commit edilmelidir.

7. **Çift sayıda node ile quorum kurmak.** 4 node'luk kümede 2'ye 2 bölünme iki tarafı da çoğunluksuz bırakır; sistem tamamen durur veya belirsizleşir. Küme boyutu tek sayı (3, 5, 7) seçilmelidir ki tam ortadan bölünme mümkün olmasın.

8. **Split-brain'i quorum olmadan "sağlık kontrolü" ile çözmeye çalışmak.** "Diğer lider ping'e cevap vermiyorsa ben lider olurum" mantığı, ağ bölünmesinde iki tarafı da lider yapar. Liderlik ancak çoğunluk oyuyla verilmelidir; ping ile ölüm tespiti yalnızca şüphe üretir, karar değil.

9. **Dağıtık kilidi lease/TTL olmadan tutmak.** Kilit sahibi çökerse veya donarsa kilit sonsuza asılı kalır ve tüm sistem bloke olur. Kilitlere mutlaka bir kira süresi (lease) ve otomatik serbest bırakma verilmelidir; ayrıca kilit sahibi işini bitirmeden lease dolabileceği için kritik işlemi fencing token ile korumak gerekir.

10. **`in_progress` idempotency kaydını asla temizlememek/kurtarmamak.** İlk istek işi yaparken çökerse anahtar `in_progress` takılır; naif kod bunu ya sonsuza dek "duplicate" sayıp işi hiç yapmaz ya da kilitli sanır. Bu kayıtlara bir zaman aşımı ve güvenli yeniden yürütme yolu gerekir.

11. **Timeout'u sabit ve tek değer seçmek.** Ağ gecikmesi değişkendir; tek bir sabit timeout ya çok agresif olup sağlıklı node'u ölü ilan eder (false positive, gereksiz failover) ya çok gevşek olup gerçek ölümü geç fark eder. Olgun sistemler ölçülen gecikmeye göre adaptif timeout kullanır.

12. **Retry'ları backoff ve jitter olmadan yapmak.** Sabit aralıkla yeniden deneyen binlerce istemci aynı anda tekrar saldırıp toparlanmakta olan servisi ikinci kez çökertir (thundering herd). Retry'lar üstel geri çekilme (exponential backoff) ve rastgelelik (jitter) ile dağıtılmalıdır.

13. **`read-modify-write`'ı eşzamanlılık kontrolü olmadan yapmak.** Oku, hesapla, geri yaz akışında iki eşzamanlı istek birbirinin yazmasını ezer (lost update). Optimistik (version sütunu) veya pesimistik kilit gerekir; naif okuma-yazma dağıtık ortamda sessizce veri kaybeder.

## Kapanış

Bu derin dalışın omurgası tek bir gözlemdir: özetteki her kavram, klavyenin başında **belirli bir kod deseniyle** ihlal edilir ve yine belirli bir desenle düzeltilir. Retry'ı idempotency olmadan yazmak, offset'i işten önce commit etmek, süreyi duvar saatiyle ölçmek, quorum'u çift node ile kurmak — bunların hepsi "ağ güvenilmezdir ve saatler senkron değildir" gerçeğinin somut, hata ayıklanabilir yüzleridir. Doğru mühendislik, bu belirsizliği yok etmeye çalışmak değil; her kod yolunda "istek iki kez gelirse ne olur, node tam burada çökerse ne olur, saat geri giderse ne olur" sorularını önceden sorup cevabı koda gömmektir.
