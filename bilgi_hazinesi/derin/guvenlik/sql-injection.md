# SQL Injection: Derin Dalış

> Bu metin, `bilgi_hazinesi/uretilen/guvenlik/sql-injection.md` altındaki kavramsal referansın uygulamalı devamıdır. Orada SQLi'nin *ne* olduğu, türleri ve savunma felsefesi ele alındı. Burada ise ellerimizi kirletiyoruz: gerçek kod üzerinde bir açığı doğuruyoruz, sömürünün nasıl göründüğünü izliyoruz, düzeltiyoruz; sonra bunun sahada gerçek CVE'lerde nasıl tezahür ettiğini, hangi savunma tasarımını ne zaman seçmeniz gerektiğini ve geliştiricilerin bu konuda tekrar tekrar düştüğü tuzakları inceliyoruz. Amaç eğitim ve savunmadır: mekanizmayı anlamak, tespit etmek ve kapatmak — canlı bir saldırı reçetesi vermek değil.

---

## 1. Çözümlü yürüyüş

Somut bir senaryo seçelim: klasik bir web uygulamasının login endpoint'i. Bu, SQLi'nin tarihsel olarak en çok sömürüldüğü noktadır (aşağıda göreceğimiz CVE-2001-1460 ve CVE-2001-1379 tam da authentication bypass örnekleridir). Python + Flask + SQLite ile yazalım, çünkü kalıp dilden bağımsızdır ve kopyalayıp çalıştırabilirsiniz.

### 1.1 Zafiyetli kod (gerçek, çalışır)

```python
import sqlite3
from flask import Flask, request

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect("uygulama.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/login", methods=["POST"])
def login():
    kullanici_adi = request.form.get("kullanici", "")
    sifre = request.form.get("sifre", "")

    conn = get_db()
    cur = conn.cursor()

    # TEHLIKELI: kullanici girdisi dogrudan sorgu metnine gomuluyor.
    sorgu = (
        "SELECT id, kullanici, rol FROM kullanicilar "
        "WHERE kullanici = '" + kullanici_adi + "' "
        "AND sifre = '" + sifre + "'"
    )
    cur.execute(sorgu)
    satir = cur.fetchone()
    conn.close()

    if satir:
        return f"Hos geldin, {satir['kullanici']} (rol: {satir['rol']})", 200
    return "Giris basarisiz", 401
```

Ve tabloyu hazırlayan kod:

```python
def kurulum():
    conn = sqlite3.connect("uygulama.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY,
            kullanici TEXT NOT NULL,
            sifre TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO kullanicilar (kullanici, sifre, rol) VALUES (?, ?, ?)",
        ("admin", "cok-gizli-parola", "yonetici"),
    )
    conn.commit()
    conn.close()
```

İlginç bir ayrıntı: kurulum kodunda `INSERT` zaten parametreli sorgu (`?` yer tutucuları) kullanıyor. Yani geliştiricinin bir yerde doğru kalıbı bildiğini görüyoruz. Sorun tam da bu: SQLi genelde "hiç bilmemekten" değil, **bir yerde tutarsızlık göstermekten** doğar. `login` fonksiyonunda geliştirici string birleştirmeye kaymış, ve tek bir yer yeterlidir.

### 1.2 Sorun kavramsal olarak nasıl ortaya çıkıyor?

`sorgu` değişkeninin çalışma anında ne hale geldiğine bakalım. Normal bir girişte, `kullanici = "admin"` ve `sifre = "cok-gizli-parola"` için sorgu şudur:

```sql
SELECT id, kullanici, rol FROM kullanicilar
WHERE kullanici = 'admin' AND sifre = 'cok-gizli-parola'
```

Sağlıklı. Ama saldırgan `kullanici` alanına `admin' --` yazarsa (SQLite'ta `--` satır-sonu yorumudur), oluşan metin şudur:

```sql
SELECT id, kullanici, rol FROM kullanicilar
WHERE kullanici = 'admin' --' AND sifre = '...'
```

`--`'den sonrası yorum satırı olarak ölür; `AND sifre = ...` koşulu tamamen iptal olur. Uygulama artık parolayı hiç kontrol etmez ve `admin` olarak içeri girersiniz. Parola bilmenize gerek kalmadı.

Kök neden, üretilen referansta vurguladığımız **kod/veri karışması**dır: geliştirici `'` tırnağını sorgunun *sınırı* olarak yazdı, ama kullanıcı girdisi de o sınırın içine düz metin olarak aktığı için, saldırgan kendi girdisiyle o tırnağı kapatıp ardından SQL sözdizimi (bir yorum işareti) ekleyebildi. Veritabanı motoruna ulaşan birleşik metinde artık "geliştiricinin yazdığı kod" ile "kullanıcının yazdığı veri" arasında hiçbir sınır kalmamıştır; motor her ikisini de eşit olarak ayrıştırır.

Aynı zafiyetin ikinci bir yüzü de vardır. Saldırgan `sifre` alanına `' OR '1'='1` yazarsa:

```sql
SELECT id, kullanici, rol FROM kullanicilar
WHERE kullanici = 'olmayan' AND sifre = '' OR '1'='1'
```

`OR '1'='1'` her satır için doğru olduğundan, `WHERE` tüm tabloyu döndürür; `fetchone()` ilk satırı (genelde ilk kayıtlı kullanıcı) alır ve o kimlikle giriş yapılır. Bu, referansta ele aldığımız tautoloji (her zaman doğru koşul) saldırısının canlı halidir.

Dikkat edin: SQLite'ın `execute()` metodu varsayılan olarak tek ifade çalıştırır, bu yüzden `'; DROP TABLE kullanicilar; --` gibi bir *stacked query* burada doğrudan çalışmaz — ama bu bir savunma değil, motorun bir davranışıdır ve başka motorlarda (veya `executescript` kullanılırsa) geçerli olmaz. Güvende olduğunuzu sanmanıza yol açan tam da bu tür "kazara koruma"lardır.

### 1.3 Düzeltilmiş kod (doğru)

Doğru çözüm girdiyi "temizlemek" değil, **kodu veriden yapısal olarak ayırmak**tır. Parametreli sorgu kullanıyoruz:

```python
@app.route("/login", methods=["POST"])
def login():
    kullanici_adi = request.form.get("kullanici", "")
    sifre = request.form.get("sifre", "")

    conn = get_db()
    cur = conn.cursor()

    # DOGRU: sorgu iskeleti sabit, girdi ayri kanaldan "veri" olarak gidiyor.
    sorgu = (
        "SELECT id, kullanici, rol, sifre_hash FROM kullanicilar "
        "WHERE kullanici = ?"
    )
    cur.execute(sorgu, (kullanici_adi,))
    satir = cur.fetchone()
    conn.close()

    # Parola dogrulamasini SQL'de degil, sabit-zamanli hash karsilastirmasiyla yap.
    if satir and _sifre_dogru(sifre, satir["sifre_hash"]):
        return f"Hos geldin, {satir['kullanici']} (rol: {satir['rol']})", 200
    return "Giris basarisiz", 401
```

Burada iki ayrı iyileştirme var ve ikisini de bilinçli yaptık:

**Birincisi, parametreli sorgu.** `?` yer tutucusu ile veritabanı sorgu iskeletini `kullanici_adi` daha ona ulaşmadan ayrıştırır ve sorgu planını sabitler. Girdi sonradan, "bu yalnızca veridir" etiketiyle ayrı bir kanaldan gider. Artık saldırgan `admin' --` yazsa bile bu, "adı tam olarak `admin' --` olan kullanıcıyı ara" anlamına gelir; öyle bir kullanıcı olmadığı için hiçbir satır dönmez. Yorum işareti veya tırnak, motor için artık sadece karakterlerdir, sözdizimi değil — çünkü ayrıştırma aşaması çoktan bitmiştir.

**İkincisi, parolayı SQL'in içinde karşılaştırmayı bıraktık.** Orijinal zafiyetli kod parolayı `WHERE ... AND sifre = '...'` ile eşliyordu; bu hem SQLi yüzeyini genişletiyor hem de parolayı düz metin (plaintext) tuttuğunu ele veriyordu. Doğru mimaride önce kullanıcıyı adıyla çekeriz, sonra parolayı uygulama katmanında, saklanan hash'e karşı sabit-zamanlı (constant-time) doğrularız:

```python
import hashlib
import hmac
import os

def _sifre_hashle(sifre: str, tuz: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), tuz, 200_000)

def _sifre_dogru(girilen: str, saklanan_hash_hex: str) -> bool:
    # saklanan format: "tuz_hex$hash_hex"
    try:
        tuz_hex, beklenen_hex = saklanan_hash_hex.split("$", 1)
    except ValueError:
        return False
    tuz = bytes.fromhex(tuz_hex)
    hesaplanan = _sifre_hashle(girilen, tuz)
    # hmac.compare_digest: zamanlama sizintisina (timing attack) karsi sabit zaman.
    return hmac.compare_digest(hesaplanan, bytes.fromhex(beklenen_hex))
```

Bu iki değişikliğin birlikteliği önemlidir: SQLi'yi kapatmak *tek başına* yeterli değildir; düzeltirken çevredeki mimariyi (parola saklama, hata mesajları, en az yetki) de gözden geçirmek gerçek güvenlik hijyenidir. Referansta "bir alanı düzeltip diğerlerini unutmak" hatasından bahsetmiştik; burada tersini yapıyoruz — bir açığı düzeltirken komşularına da bakıyoruz.

Son bir uygulamalı not: dinamik sıralama gibi *parametreleştirilemeyen* durumlar için allowlist kalıbı şöyle görünür:

```python
IZINLI_SIRALAMA = {"ad": "kullanici", "tarih": "olusturma_tarihi"}

def kullanicilari_listele(siralama_anahtari: str):
    # Kullanici girdisi ASLA dogrudan sorguya girmez; yalnizca eslesen sabit kolon adi girer.
    kolon = IZINLI_SIRALAMA.get(siralama_anahtari, "kullanici")
    sorgu = f"SELECT kullanici, rol FROM kullanicilar ORDER BY {kolon} ASC"
    # 'kolon' burada kullanici girdisinden degil, bizim sabit sozlugumuzden gelir.
    return sorgu
```

Yer tutucu (`?`) tablo/kolon adlarını parametreleştiremez; bu yüzden `ORDER BY` kolonu gibi tanımlayıcılar (identifier) için tek güvenli yol, gelen değeri önceden tanımlı geçerli değerler kümesiyle eşleyip yalnızca eşleşeni kullanmaktır. Bu, SQLi'nin en sık atlanan arka kapısıdır.

---

## 2. Gerçek dünya (CVE ile)

Yukarıdaki `login` senaryosu bir laboratuvar örneği gibi görünebilir, ama sahada tam olarak böyle görünür. Verilen gerçek CVE kayıtlarından üçünü inceleyelim; hepsi 2000-2001 dönemine ait ve SQLi'nin "erken web" çağında ne kadar sistemik olduğunu gösteriyor.

### 2.1 CVE-2001-1460 — PostNuke'ta authentication bypass

**CVE-2001-1460**: PostNuke 0.62–0.64 sürümlerinde `article.php` dosyasında, `user` parametresi üzerinden bir SQL injection açığı vardır ve uzak saldırganların **kimlik doğrulamayı atlatmasına (authentication bypass)** izin verir.

Bu, bölüm 1'de kurduğumuz senaryonun neredeyse birebir aynısıdır. `user` parametresi doğrudan bir SQL sorgusuna gömülmüş, saldırgan da tıpkı `admin' --` örneğimizde olduğu gibi sorgunun kimlik doğrulama mantığını iptal ederek yetkili oturum elde edebiliyor. Buradaki ders şudur: authentication bypass, SQLi'nin en yüksek etkili sonuçlarından biridir çünkü tek bir istekle "hiçbir hesabım yok" durumundan "yönetici hesabındayım" durumuna atlarsınız — veri çekmeye bile gerek kalmadan. Savunma açısından, kimlik doğrulama sorgularının parametreli olması pazarlık edilemezdir; bu endpoint'ler saldırganın ilk hedefidir.

### 2.2 CVE-2001-1379 — mod_auth_pgsql'de kullanıcı adı üzerinden bypass

**CVE-2001-1379**: PostgreSQL kimlik doğrulama modülleri `mod_auth_pgsql` 0.9.5 ve `mod_auth_pgsql_sys` 0.9.4, **kullanıcı adı (user name)** alanına yapılan bir SQL injection saldırısı ile uzak saldırganların kimlik doğrulamayı atlatmasına ve keyfi SQL çalıştırmasına izin verir.

Bu kayıt öğreticidir çünkü açık, uygulama kodunda değil bir **kimlik doğrulama altyapı modülünde**dir — yani "framework/kütüphane bizi korur" varsayımının ne kadar tehlikeli olduğunu gösterir. Bölüm 1'deki düzeltilmiş kodda parolayı SQL'den çıkarıp uygulama katmanına taşımamızın bir sebebi buydu: kimlik doğrulama mantığının kendisi bir string birleştirme ile SQL kuruyorsa, kimliği doğrulaması gereken katman aynı zamanda en kritik SQLi yüzeyine dönüşür. `mod_auth_pgsql` örneğinde kullanıcı adı hem sorguya gömülüyor hem de doğrulama kararı o sorgunun sonucuna bağlı; saldırgan sorguyu manipüle ederek doğrulama kararını kendi lehine çeviriyor.

### 2.3 CVE-2001-1472 ve CVE-2001-1482 — phpBB'de yetki yükseltme ve veri sızıntısı

**CVE-2001-1472**: phpBB 1.4.0 ve 1.4.1 sürümlerinde `prefs.php` dosyasında, `viewemail` parametresi üzerinden bir SQL injection açığı vardır; bu açık, **kimliği doğrulanmış (authenticated)** uzak kullanıcıların keyfi SQL komutları çalıştırmasına ve **yönetici erişimi elde etmesine** izin verir.

**CVE-2001-1482**: phpBB 1.4.2 sürümünde `bb_memberlist.php` dosyasında, `$sortby` değişkeni üzerinden bir SQL injection açığı vardır ve uzak saldırganların keyfi SQL sorguları çalıştırmasına izin verir.

Bu iki phpBB kaydını birlikte ele almak öğreticidir çünkü farklı iki hata sınıfını temsil ederler:

- **CVE-2001-1472** (`viewemail`) bir **yetki yükseltme (privilege escalation)** vakasıdır: saldırganın zaten geçerli bir hesabı vardır (authenticated), ama SQLi ile normal kullanıcıdan yöneticiye tırmanır. Bu, "sadece dışarıdan gelenlere karşı savunuruz" yanılgısını çürütür — içeriden gelen kimliği doğrulanmış istekler de aynı derecede parametreli olmalıdır.

- **CVE-2001-1482** (`$sortby`) ise tam olarak bölüm 1'de allowlist ile çözdüğümüz **sıralama parametresi** açığıdır. Değişkenin adı bile (`$sortby`) bunun bir `ORDER BY` bağlamı olduğunu düşündürür — ve `ORDER BY` kolonu parametreleştirilemeyen bir tanımlayıcı olduğu için, geliştirici muhtemelen değişkeni doğrudan sorguya gömmüştür. Eğer bu kodda bizim `IZINLI_SIRALAMA` allowlist kalıbımız kullanılsaydı, açık doğmazdı. Bu CVE, "parametreli sorgu her şeyi çözer" cümlesinin eksik kaldığı yeri gösteriyor: sıralama/kolon adı gibi tanımlayıcılarda allowlist şarttır.

Bu dört CVE'nin ortak dersi: SQLi bir "gelişmiş saldırı" değil, string birleştirmenin kaçınılmaz bir sonucudur. Yıllar geçse de kök neden aynı kalıyor; sadece diller ve framework'ler değişiyor.

---

## 3. Karşılaştırma / karar

Elinizde birden fazla savunma seçeneği var. Hepsi eşit değildir ve "hepsini birden yap" cevabı doğru olsa da, hangisinin *birincil*, hangisinin *destekleyici* katman olduğunu bilmek kritiktir. Aşağıda gerçek karar takaslarıyla birlikte veriyorum.

### 3.1 Parametreli sorgu vs. manuel escaping

| Ölçüt | Parametreli sorgu (prepared statement) | Manuel escaping (tırnak kaçırma) |
|---|---|---|
| Kök nedeni çözer mi? | Evet — kod/veri sınırını yapısal olarak korur | Hayır — semptomu geciktirir |
| Sayısal (numeric) bağlam | Otomatik korunur | Sıklıkla korumasız (sayısal alanda tırnak yok) |
| Karakter kodlama saldırıları | Dayanıklı | Kırılgan (multibyte/encoding hileleriyle bozulur) |
| Geliştirici hatasına açıklık | Düşük | Yüksek (bir alan unutulur, biter) |

**Karar:** Parametreli sorgu her zaman birincil savunmadır. Manuel escaping yalnızca parametreli sorgunun *hiç mümkün olmadığı* eski/legacy ortamlarda, o da ancak dilin sağladığı resmi escaping fonksiyonuyla (asla elle `replace("'", "''")` ile değil) düşünülmelidir. Elle escaping, CVE-2001-1379'daki gibi kullanıcı adı alanlarında tekrar tekrar başarısız olmuştur.

### 3.2 Parametreli sorgu vs. ORM vs. saklı yordam (stored procedure)

- **ORM:** Varsayılan kullanımında genellikle parametreli sorgu üretir, yani iyi bir taban sağlar. Takas: geliştiriciye "güvendeyim" yanılgısı verir. `raw()`, `nativeQuery`, string interpolation kaçış kapıları ORM'in korumasını buharlaştırır. **Ne zaman:** Genel uygulama geliştirme için varsayılan tercih; ancak code review'da ham SQL yolları özellikle aranmalı.

- **Saklı yordam (stored procedure):** Sorgu mantığını veritabanında tutar. Takas: *otomatik* güvenlik sağlamaz. İçinde dinamik SQL string'i birleştiriliyorsa (`EXEC('SELECT ... ' + @girdi)`), açık prosedürün içine taşınmış olur. **Ne zaman:** Parametreli girdilerle çağrılan, içinde string birleştirme yapmayan saklı yordamlar iyidir; ama "prosedür kullanıyoruz" tek başına bir güvence değildir.

- **Ham parametreli sorgu:** En açık, en denetlenebilir seçenek. Takas: tekrar eden kod ve daha fazla el emeği. **Ne zaman:** Performans-kritik veya ORM'in beceremediği karmaşık sorgularda — ama mutlaka `?`/`:isim` yer tutucularıyla.

**Karar:** Üçünün de temelinde aynı ilke vardır — girdi asla kod olarak yorumlanmamalı. Seçim ergonomi ve ekip disiplini meselesidir, güvenlik garantisi hep parametreleştirmeden gelir.

### 3.3 Kaynağında düzeltme vs. WAF ile perdeleme

Bu, en sık yanlış yapılan karardır. Bir WAF (Web Application Firewall) hızlıca devreye alınabilir ve "hemen bir şey yapmış olmak" hissi verir. Ama:

- **WAF'ın gücü:** Tespit ve gürültü azaltma; otomatik tarayıcıları yavaşlatır; henüz yamalanmamış açıklar için geçici bir *sanal yama* (virtual patch) olabilir.
- **WAF'ın zayıflığı:** İmza tabanlıdır ve WAF ile veritabanı aynı string'i asla birebir aynı yorumlamaz. Kodlama katmanları, eşdeğer ifadeler (`OR 1=1` yerine `OR 2>1`), boşluk/yorum hileleriyle atlatılır.

**Karar:** WAF *birincil* savunma olamaz. Kaynağında (parametreli sorgu) düzeltmek zorunludur; WAF derinlemesine savunmanın (defense in depth) bir katmanıdır. Tek istisna: elinizde kaynak kodu olmayan üçüncü-parti bir bileşen varsa (örneğin yamalanmamış eski bir phpBB), WAF *geçici* bir sanal yama olarak makuldür — ama asıl çözüm güncelleme/yamadır.

### 3.4 En az yetki (least privilege): etkiyi sınırlama kararı

Bu bir *önleme* değil, *zarar azaltma* kararıdır ve bu yüzden diğerlerinden bağımsız olarak her zaman uygulanmalıdır. Uygulama veritabanına hangi yetkiyle bağlanıyor?

- Uygulama `root`/`admin` ile bağlanıyorsa, bir SQLi "veri okuma"dan "tüm tabloları silme, dosya yazma, hatta OS komutu çalıştırma"ya yükselir.
- Uygulama yalnızca ihtiyaç duyduğu tablolara `SELECT/INSERT/UPDATE` yetkisiyle bağlanıyorsa, aynı açık çok daha sınırlı bir etki yaratır.

**Karar:** En az yetki, açığı *kapatmaz* ama sömürünün patlama yarıçapını (blast radius) küçültür. Parametreli sorgunun ikamesi değil, tamamlayıcısıdır. CVE-2001-1379 ve CVE-2001-1472'deki gibi "keyfi SQL çalıştırma / yönetici erişimi" sonuçlarının şiddeti, doğrudan uygulamanın DB yetkileriyle orantılıdır.

---

## 4. Hata-modu kataloğu

Aşağıdakiler, geliştiricilerin ve savunmacıların SQLi konusunda sahada tekrar tekrar yaptığı tipik hatalardır. Her biri, neden yanlış olduğunun kısa açıklamasıyla.

1. **String birleştirmeyle sorgu kurmak.** Kök hata budur; `"... WHERE x = '" + girdi + "'"` kalıbı, kod ile veriyi motora ulaşmadan karıştırır. Diğer her şey bunun türevidir.

2. **Sadece bir endpoint'i parametreleştirmek.** Login formunu düzeltip arama, sıralama (`$sortby` — CVE-2001-1482), rapor filtresi, `viewemail` gibi ikincil alanları unutmak. SQLi tek bir gözden kaçmış noktadan girer; %99 kapsam %0 kadar iyidir.

3. **Kara liste (blacklist) filtrelemeye güvenmek.** "`OR`, `UNION`, `--` gibi kelimeleri yasakla" yaklaşımı asla eksiksiz olamaz; eşdeğer ifadeler, kodlama ve motor farklarıyla atlatılır. Semptomu hedefler, kök nedeni değil.

4. **Sayısal alanlarda tırnak kaçırmanın yeteceğini sanmak.** Sayısal bağlamda (`WHERE id = 5`) tırnak zaten kullanılmaz; `5 OR 1=1` gibi bir payload hiç tırnak içermez, dolayısıyla tırnak escaping'i bu alanı hiç korumaz.

5. **Sadece istemci tarafı (client-side) doğrulamaya güvenmek.** JavaScript girdi kontrolü yalnızca kullanıcı deneyimi içindir; saldırgan isteği tarayıcıyı atlayıp doğrudan sunucuya gönderir. Güvenlik daima sunucuda olmalıdır.

6. **ORM'in mutlak koruma sağladığını varsaymak.** ORM varsayılan olarak parametreli sorgu üretir ama `raw()`/`nativeQuery`/string interpolation kaçış kapıları bu korumayı deler. "ORM kullanıyoruz" cümlesi, code review'da SQL güvenliğinin hiç sorgulanmamasına yol açan sinsi bir psikolojik tuzaktır.

7. **Saklı yordamı otomatik güvenli saymak.** İçinde dinamik SQL string'i birleştiren bir stored procedure, açığı sadece veritabanının içine taşımış olur; "prosedür" olması hiçbir koruma sağlamaz.

8. **WAF'ı birincil savunma sanmak.** WAF imza tabanlıdır ve normalizasyon uyuşmazlığı nedeniyle atlatılabilir; tespit/geciktirme katmanıdır, kaynağındaki düzeltmenin yerini tutmaz.

9. **Tanımlayıcıları (identifier) parametreleştirmeye çalışmak veya doğrudan gömmek.** Kolon adı, tablo adı, `ORDER BY` yönü `?` ile parametreleştirilemez. Geliştirici ya boşuna uğraşır ya da vazgeçip doğrudan gömer (CVE-2001-1482 senaryosu). Doğru çözüm allowlist eşlemesidir.

10. **Üretimde ayrıntılı DB hata mesajlarını açık bırakmak.** Ayrıntılı hatalar error-based sızıntıya ve keşfe davetiye çıkarır; saldırgana tablo/kolon isimlerini ve motor türünü bedava verir. Kullanıcıya generic hata, loga tam ayrıntı.

11. **En az yetki ilkesini ihmal edip uygulamayı `root`/`admin` ile bağlamak.** Bu, tek bir SQLi'nin etkisini veri okumadan tüm veritabanını silmeye/OS komutuna yükseltir. Açığı önlemez ama şiddetini katlar.

12. **Veritabanının dışa ağ erişimini (egress) kısıtlamamak.** Out-of-band (OOB) SQLi, veritabanının dışarıya DNS/HTTP isteği yapabilmesine dayanır; egress filtering yapılmazsa, ne çıktı ne zamanlama kanalı olmasa bile veri sızdırılabilir.

13. **Bir açığı düzeltirken çevresini gözden geçirmemek.** Bölüm 1'de gördük: SQLi'yi kapatırken parolanın düz metin tutulduğunu, hata mesajlarının fazla konuştuğunu fark etmemek. Güvenlik açıkları genelde küme halinde bulunur; birini bulduğunuz yer, diğerlerine bakmanız gereken yerdir.

---

## Kapanış

Derin dalışın özeti tek cümlede: **SQL Injection, girdiyi temizleme problemi değil, mimari bir sınır problemidir.** Bölüm 1'de aynı `login` kodunu hem kırdık hem düzelttik; fark, akıllıca bir filtre değil, kod ile veriyi motora ulaşmadan ayıran parametreli sorgu oldu. Bölüm 2'deki gerçek CVE'ler (CVE-2001-1460, CVE-2001-1379, CVE-2001-1472, CVE-2001-1482) bu aynı kök nedenin — string birleştirmenin — yıllar ve framework'ler boyunca nasıl tekrarlandığını gösterdi; hatta `$sortby` gibi bir değişken adı bile bize allowlist gerektiren bir tanımlayıcı bağlamını fısıldadı. Bölüm 3, savunma seçenekleri arasındaki takasları netleştirdi: birincil savunma her zaman parametreleştirme, WAF ve en az yetki ise onu tamamlayan ama asla ikame edemeyen katmanlar. Bölüm 4 ise, bilmeniz gereken hata modlarını topladı; çünkü savunmayı öğrenmenin en hızlı yolu, başkalarının tekrar tekrar düştüğü tuzakları önceden tanımaktır. Nihai ilke değişmez: girdinin asla kod olarak yorumlanamayacağı bir sistem kurun, gerisini o mimari halleder.
