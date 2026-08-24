# Dosya Yükleme Zafiyetleri — Derin Dalış

Bu metin, aynı konudaki özet makalenin devamıdır ve onun tekrarı değildir. Özet makale "neden bir dosya yüklemesi kod çalıştırabilir?", uzantı/MIME bypass mantığı, web shell yaşam döngüsü ve katmanlı savunma mimarisini kavramsal düzeyde kurdu. Burada ise aynı zemini **çalışan kod** üzerinden yürüyeceğiz: gerçek zafiyetli bir yükleme uç noktasını adım adım kıracak, sonra aynı uç noktayı üretim kalitesinde sağlamlaştıracağız. Amaç savunmadır: mekanizmayı öyle net görmek ki, tespit ve engelleme kararlarını kendiniz verebilesiniz. Bu bir canlı saldırı reçetesi değil; her istismar adımı, o adımı imkânsız kılan savunmayı öğretmek için oradadır.

---

## 1. Çözümlü Yürüyüş

Senaryomuz gerçekçi ve sıradan: bir web uygulamasında kullanıcıların profil fotoğrafı yüklediği bir uç nokta. Backend Python/Flask, sunucu Apache + mod_php benzeri bir yorumlayıcı düşünün — ama zafiyetin özü dile bağlı değil, mimariye bağlı. Önce hatalı kodu, sonra sorunun nasıl doğduğunu, sonra düzeltilmiş kodu göreceğiz.

### 1.1 Zafiyetli kod

Aşağıda, sahada gerçekten karşılaştığınız türden bir yükleme handler'ı var. Geliştirici "güvenlik önlemi aldığını" düşünüyor: bir uzantı kara listesi ve bir `Content-Type` kontrolü koymuş.

```python
import os
from flask import Flask, request, redirect

app = Flask(__name__)

# Web kökünün ALTINDA, doğrudan URL ile erişilebilir bir dizin
UPLOAD_DIR = "/var/www/html/uploads"

BLOCKED_EXTENSIONS = {".php", ".asp", ".jsp", ".exe", ".sh"}

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("avatar")
    if not f:
        return "Dosya yok", 400

    filename = f.filename  # kullanıcının verdiği ad — DOĞRUDAN kullanılıyor

    # 1) "Güvenlik": uzantı kara listesi
    _, ext = os.path.splitext(filename)
    if ext.lower() in BLOCKED_EXTENSIONS:
        return "Bu dosya tipi yasak", 400

    # 2) "Güvenlik": beyan edilen Content-Type kontrolü
    if not f.content_type.startswith("image/"):
        return "Sadece görsel yükleyin", 400

    # Dosyayı, kullanıcının verdiği adla, web kökünün altına yaz
    save_path = os.path.join(UPLOAD_DIR, filename)
    f.save(save_path)

    return redirect(f"/uploads/{filename}")
```

İlk bakışta makul görünüyor. İki kontrol var, ikisi de "kötü" bir şeyi reddediyor gibi. Sorun tam da bu görünürde makullükte gizli.

### 1.2 Sorun kavramsal olarak nasıl ortaya çıkıyor?

Özet makalede RCE'nin üç önkoşulunu kurmuştuk: (a) saldırgan içeriği kontrol ediyor, (b) dosya çalıştırılabilir bir konuma yazılıyor, (c) dosya bir yorumlayıcıyı tetikleyecek biçimde adlandırılıyor. Bu kod, üç önkoşulu da saldırgana **bedava** veriyor. Nedenlerini tek tek görelim:

**Kara liste yapısal olarak eksik.** `BLOCKED_EXTENSIONS` yalnızca `.php`'yi engelliyor, ama Apache+mod_php yapılandırmalarında tarihsel olarak `.phtml`, `.php3`, `.php4`, `.php5`, `.pht` de PHP olarak koşabilir. Saldırganın tek yapması gereken, listede olmayan **bir** çalışabilir uzantı bulmak. `avatar.phtml` bu kontrolü hiç zorlanmadan geçer. Kara listenin doğası budur: savunmacı tüm kötü olasılıkları saymak zorundadır, saldırgan ise yalnızca birini bulmak zorundadır — asimetri tamamen saldırganın lehinedir.

**Content-Type istemciden gelir.** `f.content_type`, multipart isteğinde o parçanın yanında **beyan edilen** değerdir; dosyanın gerçek içeriğinden türetilmez. Saldırgan isteği bir proxy'den geçirip `Content-Type: image/png` yazar, gövdeye PHP kodunu koyar. Kontrol `startswith("image/")` diyor, beyan `image/png` diyor — geçer. Sunucu dosyanın içine hiç bakmadı.

**Dosya adı kullanıcıdan geliyor ve konum çalıştırılabilir.** `save_path = os.path.join(UPLOAD_DIR, filename)` satırı iki felaketi birden barındırır. Birincisi, `filename` içinde `../` varsa (`../../var/www/html/config.php` gibi) yazma işlemi hedef dizinin dışına taşabilir — path traversal. İkincisi, `UPLOAD_DIR` doğrudan `/var/www/html` altında; yani buraya yazılan `.phtml` dosyasına tarayıcıdan `/uploads/avatar.phtml` diye erişildiğinde Apache onu mod_php'ye devreder ve **çalıştırır**.

Somut istismar zinciri (kavramsal): saldırgan, içeriği `<?php system($_GET['c']); ?>` olan bir dosyayı `avatar.phtml` adıyla ve `Content-Type: image/png` etiketiyle gönderir. Kara liste `.phtml`'i tanımaz — geçer. Content-Type `image/` ile başlar — geçer. Dosya `/var/www/html/uploads/avatar.phtml` olarak yazılır. Saldırgan `/uploads/avatar.phtml?c=id` adresine gider; Apache dosyayı PHP olarak koşar, `system("id")` çalışır, çıktı ekrana döner. Bu noktada saldırgan `www-data` bağlamında komut çalıştırıyor demektir — web shell yerleşmiştir.

Dikkat edin: iki "güvenlik kontrolü" de vardı ve ikisi de aşıldı, çünkü ikisi de **yanlış katmanı** koruyordu. Kontrol, dosyanın adına ve istemcinin beyanına güveniyordu; oysa belirleyici olan, dosyanın gerçek içeriği ve yazıldığı yerin çalıştırılabilir olup olmadığıdır.

### 1.3 Düzeltilmiş kod

Şimdi aynı uç noktayı, özet makaledeki savunma katmanlarını **koda dökerek** yeniden yazalım. Buradaki her satır, yukarıdaki üç önkoşuldan en az birini kırmak için var.

```python
import os
import uuid
import imghdr
from io import BytesIO
from flask import Flask, request, jsonify, send_file, abort
from PIL import Image  # görsel yeniden kodlama için

app = Flask(__name__)

# KRİTİK: web kökünün DIŞINDA. Apache bu yolu doğrudan servis edemez.
UPLOAD_DIR = "/srv/app_data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Beyaz liste: uzantı DEĞİL, gerçek içerik tipini eşleyeceğiz
ALLOWED = {
    "jpeg": ".jpg",
    "png": ".png",
    "gif": ".gif",
}
MAX_BYTES = 5 * 1024 * 1024          # 5 MB — DoS sınırı
MAX_PIXELS = 6000 * 6000             # decompression bomb sınırı


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("avatar")
    if not f:
        return jsonify(error="Dosya yok"), 400

    # 1) Boyut sınırı — belleğe almadan önce oku ve tavanla
    raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return jsonify(error="Dosya çok büyük"), 413

    # 2) İçerik tabanlı tip tespiti (beyan edilen Content-Type'a GÜVENMİYORUZ)
    kind = imghdr.what(None, h=raw)   # magic-byte tabanlı gerçek tip
    if kind not in ALLOWED:
        return jsonify(error="Geçersiz görsel"), 400

    # 3) Görseli AÇ ve YENİDEN KODLA — gömülü payload'ı (EXIF/polyglot) yok et
    try:
        img = Image.open(BytesIO(raw))
        img.verify()                  # bozuk/tuzaklı dosyayı ayıkla
        img = Image.open(BytesIO(raw))  # verify sonrası yeniden aç (Pillow gereği)
        if img.width * img.height > MAX_PIXELS:
            return jsonify(error="Görsel boyutları çok büyük"), 400
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))   # yalnızca pikselleri taşı, metadata'yı DEĞİL
    except Exception:
        return jsonify(error="Görsel işlenemedi"), 400

    # 4) Dosya adını SUNUCU üretsin — path traversal ve uzantı oyunları biter
    ext = ALLOWED[kind]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, stored_name)

    # 5) Temiz görseli, güvenli formatta, güvenli konuma yaz
    fmt = "JPEG" if kind == "jpeg" else kind.upper()
    clean.save(save_path, format=fmt)

    return jsonify(id=stored_name), 201


@app.route("/media/<file_id>")
def serve(file_id):
    # Kontrollü sunum: kullanıcı doğrudan dosya sistemine erişemez
    if not file_id.replace(".", "").isalnum():   # sadece bizim ürettiğimiz adlar
        abort(404)
    path = os.path.join(UPLOAD_DIR, os.path.basename(file_id))
    if not os.path.isfile(path):
        abort(404)
    resp = send_file(path, mimetype="application/octet-stream")
    resp.headers["Content-Disposition"] = "attachment"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
```

Bu kodun her savunması bir önkoşulu kırıyor:

- **Beyaz liste + `imghdr.what`** beyan edilen Content-Type'ı devre dışı bırakır; dosyanın ilk baytlarındaki gerçek imzaya bakar. `.phtml` gönderen saldırgan artık `imghdr` "bu bir görsel değil" dediği için elenir.
- **Yeniden kodlama (`putdata` ile piksel taşıma)** polyglot ve EXIF-gömülü payload'ları imha eder: çıktı, girdinin baytları değil, ayrıştırılmış piksellerden yeniden üretilmiş yepyeni bir dosyadır. Bir GIF başlığıyla başlayıp içinde `<?php`
 barındıran polyglot, yeniden çizildiğinde o PHP metni fiziksel olarak kaybolur.
- **Sunucu-üretimli UUID ad** path traversal'i (`../`), sondaki nokta/null-byte oyunlarını ve üzerine yazma senaryolarını tek hamlede kapatır. Kullanıcının verdiği ad hiçbir yerde dosya sistemine geçmez.
- **Web kökü dışı depolama + kontrollü `serve`** çalıştırma önkoşulunu kırar: dosya artık `/uploads/...` diye doğrudan çağrılamaz; yalnızca `application/octet-stream` + `attachment` + `nosniff` başlıklarıyla, indirme olarak döner. Saldırgan mükemmel bir web shell yazsa bile o dosya inert bir byte yığınıdır.

Kritik gözlem: düzeltilmiş kod, tek bir "sihirli kontrol" eklemedi. Bağımsız katmanlar üst üste bindi. Herhangi biri delinse bile bir sonraki felaketi durdurur — özet makaledeki derinlemesine savunma felsefesinin somut hali budur.

---

## 2. Gerçek Dünya (CVE ile)

Yukarıdaki soyut zincirin sahada nasıl göründüğünü, gerçek kayıtlar üzerinden demirleyelim. Bu konu, kamuya açık zafiyet veritabanlarının en eski ve en tekrar eden başlıklarından biridir; bu da onun "çözülmüş bir sorun" değil, mimari bir tuzak olduğunu gösterir.

**CVE-2003-1552** bu makalenin tam kalbindeki senaryodur. Kayıt, Uploader 1.1 yazılımındaki `uploader.php` için bir **unrestricted file upload** zafiyetini tanımlar: saldırgan çalıştırılabilir uzantılı bir dosya yükler, sonra onu `uploads/` altında doğrudan bir istekle çağırarak keyfi kod çalıştırır. Bu, 1.2'deki zafiyetli kodumuzun birebir gerçek dünyadaki karşılığıdır — çalıştırılabilir uzantı + web kökü altında erişilebilir dizin + kontrolsüz kabul. Ders nettir: "dosyayı `uploads/` altına at ve doğrudan servis et" kalıbı, 2003'te de felaketti, bugün de. Düzeltilmiş kodumuzdaki "web kökü dışına yaz + kontrollü serve et" katmanı, tam olarak bu CVE sınıfını hedefler.

**CVE-2003-1501**, Gast Arbeiter 1.3'ün yükleme CGI'sındaki bir **directory traversal** zafiyetini kaydeder: `req_file` parametresine `..` (dot dot) enjekte edilerek keyfi dosyalar yazılabiliyor. Bu, 1.2'deki `os.path.join(UPLOAD_DIR, filename)` satırının neden bu kadar tehlikeli olduğunu sahadan doğrular. Kullanıcı kontrollü bir yol bileşeni, dosyanın hedef dizinin dışına — belki bir yapılandırma dosyasının veya başka bir çalıştırılabilir betiğin üzerine — yazılmasına imkân verir. Düzeltilmiş kodumuzun UUID-tabanlı sunucu-üretimli ad stratejisi, bu vektörü kökten kapatır: kullanıcı yol üzerinde hiçbir söz sahibi değildir.

**CVE-2000-0435**, Allmanage 2.6'daki `allmanageup.pl` yükleme CGI betiğinin uzaktan **doğrudan çağrılabilmesiyle** kullanıcı hesaplarının veya web sayfalarının değiştirilebilmesini kaydeder. Buradaki ek boyut, yükleme fonksiyonelliğinin **kimlik doğrulama/yetkilendirme** eksikliğidir. Yükleme uç noktası korumasız çağrılabiliyorsa, en iyi tip doğrulaması bile yalnızca "kimin" felaket yükleyebileceğini belirsizleştirir. Bu, savunma listemizdeki "yükleme uçlarını yetkilendirmeyle koru" maddesinin neden birincil savunmalarla eşdeğer önemde olduğunu gösterir.

Bir tarihsel not olarak **CVE-2000-0860** ise ilginç bir ters yönü aydınlatır: PHP 3 ve 4'ün dosya yükleme yeteneğindeki bir kusur, saldırganın gizli form alanlarını iç PHP betik değişkenlerinin adlarıyla eşleşecek şekilde ayarlayarak **keyfi dosyaları okumasına** imkân veriyordu. Yani "dosya yükleme" mekanizmasının kendisi, dikkatsiz değişken enjeksiyonuyla bir dosya-okuma primitifine dönüşebiliyordu. Bu, yükleme kodunun yalnızca "yazma" tarafını değil, çevresindeki tüm değişken/parametre işleme mantığını da güvenlik sınırı saymamız gerektiğini hatırlatır. Yükleme uç noktası izole bir işlev değildir; içinde yaşadığı framework'ün parametre bağlama (parameter binding) davranışıyla iç içedir ve bu bağlamı görmezden gelmek yeni saldırı yüzeyleri açar.

Bu dört kayıt farklı on yıllardan, farklı dillerden ve farklı ürünlerden gelir — ama hepsi aynı üç önkoşulun bir alt kümesini paylaşır. Zafiyetin kalıcılığı, onun bir "bug" değil bir **tasarım cazibesi** olmasından kaynaklanır: dosyayı en kolay yere (web kökü altı), en kolay adla (kullanıcının verdiği) yazmak her zaman en az kod yazılan yoldur. Güvenli yol ise her zaman daha fazla kod, daha fazla katman ve daha fazla düşünme gerektirir — bu yüzden ekipler baskı altında sürekli aynı tuzağa geri döner. Tarayıcı tarafındaki eski kusurlar (örneğin IE'nin "untrusted scripted paste" ailesinden CVE-1999-0870 ve CVE-2001-0089) ise madalyonun öteki yüzünü, yani istemcinin dosya-yükleme kontrolünün kendisinin bir sızıntı vektörü olabileceğini gösterir; bugün sunucu tarafına odaklansak da, güven sınırının iki uçlu olduğunu akılda tutmak gerekir.

---

## 3. Karşılaştırma / Karar

Savunma seçeneklerinin hepsi eşit değildir ve her birinin bir takası vardır. Doğru kararı verebilmek için seçenekleri karşılaştırmalı görmek gerekir.

**Kara liste vs. beyaz liste (uzantı).** Kara liste "bilinen kötüyü reddet" der; beyaz liste "bilinen iyiyi kabul et" der. Takas: kara liste yazması kolaydır ve mevcut sistemi bozmadan devreye alınır, ama yapısal olarak eksiktir — bir türev uzantı, harf büyüklüğü oyunu veya yapılandırma dosyası mutlaka atlar. Beyaz liste ise varsayılan-reddet olduğu için aklınıza gelmeyen tehlikeli uzantıyı da otomatik kapatır; bedeli, meşru ama listede olmayan bir formatı istemeden reddetme riskidir. **Karar: neredeyse her zaman beyaz liste.** Kara liste yalnızca beyaz listeyi tamamlayan ikincil bir filtre olarak (örneğin `.htaccess` gibi yapılandırma dosyalarını ek olarak reddetmek için) anlamlıdır.

**Magic-byte kontrolü vs. yeniden kodlama (re-encode).** Magic-byte kontrolü ucuzdur, hızlıdır ve dosyayı değiştirmez — ama polyglot ve EXIF-gömülü payload'lara karşı zayıftır; "geçerli imza" ile "zararsız içerik" aynı şey değildir. Yeniden kodlama pahalıdır (CPU, bellek), dosyayı bozabilir (kalite kaybı, animasyon/şeffaflık kaybı) ve her format için uygulanamaz — ama gömülü payload'ı fiziksel olarak imha eder. **Karar: ikisi birlikte.** Magic-byte ile hızlıca ele, sonra kabul edilenleri yeniden kodla. Görseller için yeniden kodlama uygulanabilirdir; PDF/Office belgeleri için yeniden kodlama zordur, orada izole sanitizasyon servisi veya salt-indirme sunumu tercih edilir.

**Web kökü içi + çalıştırma engelleme vs. web kökü dışı depolama.** İlk yaklaşımda dosya `uploads/` altında durur ama sunucu bu dizinde script işleyicilerini kapatır (`AllowOverride None`, handler kaldırma). İkincisinde dosya web kökünün tamamen dışındadır ve yalnızca uygulama kodu aracılığıyla sunulur. Takas: web kökü içi + handler kapatma, mevcut mimariyi az değiştirir ve statik sunum hızlıdır — ama tek bir yapılandırma hatası (yanlışlıkla `.htaccess` etkin kalması, bir vhost'un handler'ı geri getirmesi) tüm korumayı deler. Web kökü dışı depolama daha sağlamdır çünkü "çalıştırılabilir konuma yazma" önkoşulunu mimariden siler, ama sunum için ek uygulama kodu (streaming, yetki kontrolü) gerektirir ve biraz daha yavaştır. **Karar: kritik sistemlerde web kökü dışı depolama esas alınmalı;** çalıştırma engelleme onun yerine değil, üstüne eklenen bir emniyet kemeridir.

**Aynı origin vs. ayrı origin sunum.** Kullanıcı içeriğini ana uygulama alan adından sunmak basittir ama SVG/HTML yüklemelerinin ana uygulamanın oturum bağlamında XSS yapmasına ve çerez sızıntısına kapı açar. Ayrı bir origin (çerezsiz, kod çalıştırmayan alt alan veya ayrı depolama servisi) bu yüzeyi küçültür — bedeli ek altyapı ve CORS/karmaşıklıktır. **Karar: kullanıcının başka kullanıcılara görünen içerik yüklediği her senaryoda ayrı origin.** Yalnızca yükleyenin gördüğü, kısa ömürlü içerikte aynı origin tolere edilebilir.

**Senkron işleme vs. asenkron kuyruk.** Yeniden kodlama, antivirüs taraması ve derin doğrulama pahalıdır; bunu istek-yanıt döngüsünde senkron yapmak, büyük dosyalarda zaman aşımına ve DoS'a açıktır. Asenkron kuyruk (dosyayı önce karantinaya al, arka planda işle, sonra "hazır" işaretle) ölçeklenir ama kullanıcı deneyimini karmaşıklaştırır ve karantina alanının kendisini güvenli tutmayı gerektirir. **Karar: düşük hacimde senkron yeterli; yüksek hacim veya ağır işlemede asenkron karantina modeli.**

Genel karar ilkesi: hiçbir tek katman "yeterli" değildir; soru "hangisini seçeyim" değil, "bu tehdit modeli için hangi katmanların bileşimi maliyet/fayda açısından doğru" sorusudur. RCE riskini web kökü dışı depolama + yeniden kodlama taşır; XSS riskini ayrı origin + `nosniff` taşır; DoS riskini boyut/piksel sınırları + asenkron işleme taşır. Tehdit modeliniz hangilerini içeriyorsa o eksende yatırım yapın.

---

## 4. Hata-Modu Kataloğu

Aşağıdakiler, dosya yükleme güvenliğinde geliştiricilerin ve savunmacıların tekrar tekrar düştüğü tipik hatalardır. Ortak kökleri "yanlış katmana güvenmek"tir.

1. **Yalnızca istemci tarafı doğrulama.** JavaScript ile uzantı/boyut kontrolü sadece kullanım kolaylığı içindir; saldırgan isteği proxy'den doğrudan üreterek bunu tümüyle atlar. Otoriter doğrulama her zaman sunucudadır.

2. **Beyan edilen `Content-Type`'a güvenmek.** İstemcinin gönderdiği multipart etiketini dosyanın gerçek tipi sanmak, en yaygın MIME bypass'ının açık kapısıdır; etiket bir saniyede değiştirilir.

3. **Uzantıyı kara liste ile engellemek.** Eksik kalması pratikte garantidir: `.phtml`, `.pht`, harf büyüklüğü varyantı veya bir `.htaccess` mutlaka atlanır. Beyaz liste dışında güvenli değildir.

4. **"Geçerli görsel = güvenli" varsaymak.** EXIF'e gömülü kod ve polyglot dosyalar bu varsayımı çürütür. Bir dosyanın geçerli medya olması, çalıştırılamaz olduğu anlamına gelmez; belirleyici olan çalıştırılıp çalıştırılmadığıdır.

5. **Dosyayı web kökü altına, tahmin edilebilir adla yazmak.** Bu, üç RCE önkoşulundan ikisini (erişilebilir konum + kontrol edilebilir ad) saldırgana hediye eder; CVE-2003-1552'nin özüdür.

6. **Kullanıcının verdiği dosya adını doğrudan kullanmak.** Path traversal (CVE-2003-1501), üzerine yazma ve sondaki-nokta/null-byte oyunlarının hepsini aynı anda davet eder. Ad her zaman sunucu üretmeli.

7. **`verify()`/yeniden kodlama sonrası dosyayı yeniden açmayı unutmak.** Pillow gibi kütüphanelerde `verify()` çağrısı akışı tüketir; sonra aynı buffer'dan işlem yapmaya çalışmak sessizce hatalı davranışa yol açar ve doğrulamanın etkisiz kaldığı bir açık bırakır.

8. **Yeniden kodlamayı atlayıp yalnızca magic-byte'a güvenmek.** İmza kontrolü gereklidir ama yeterli değildir; polyglot dosya geçerli bir imzayla başlayıp içinde kod taşır. Yeniden kodlama olmadan bu vektör açık kalır.

9. **Yapılandırma dosyası yüklemesini gözden kaçırmak.** Saldırgan `.htaccess` (Apache) veya `web.config` (IIS) yükleyerek "bu dizindeki `.jpg`'leri kod olarak işle" dedirtir ve tüm uzantı savunmanızı geçersiz kılar. Bu dosyalar ayrıca reddedilmeli ve sunucu yerel yapılandırmayı yok saymalı.

10. **Sunum başlıklarını unutmak.** İçeriği güvenli sakladıktan sonra `X-Content-Type-Options: nosniff` ve doğru `Content-Type`/`Content-Disposition` olmadan geri sunmak, tarayıcının MIME-sniffing yaparak zararsız görünen bir dosyayı HTML/script gibi yorumlamasına ve XSS'e yol açar.

11. **SVG'yi "görsel" sayıp güvenli varsaymak.** SVG geçerli bir görsel olmasına rağmen içine `<script>` gömülebilir ve tarayıcıda çalışır. Ayrı origin'den sunulmalı, sanitize edilmeli veya render yerine indirme olarak verilmeli.

12. **Boyut ve piksel sınırı koymamak.** Sınırsız yükleme, disk doldurma DoS'una; sınırsız piksel ise "decompression bomb"a (küçük dosyanın açıldığında belleği tüketmesi) kapı açar. Hem byte hem piksel tavanı şarttır.

13. **Antivirüs/imza taramasını birincil savunma sanmak.** Tarama, dosyaların başka kullanıcılara dağıtıldığı senaryolarda değerli bir ek katmandır; ama yeni/özelleştirilmiş payload'ları kaçırır. Onu emniyet ağı olarak görün, ana savunma olarak değil.

14. **Yetkilendirmeyi atlamak.** Yükleme uç noktası korumasız veya doğrudan çağrılabilir olduğunda (CVE-2000-0435), en iyi tip doğrulaması bile yalnızca kimin felaket yükleyeceğini belirsizleştirir. Her yükleme ucu kimlik doğrulama, yetkilendirme ve loglama gerektirir.

---

Bu derin dalışın özündeki tek cümle, özet makaleyle aynıdır ama artık kodla kanıtlanmıştır: **Tek bir kontrolün başarısız olacağını varsay ve o başarısızlığın felakete dönüşmesini bir sonraki bağımsız katmanın engellemesini sağla.** Uzantı kontrolü aşılsa dosya çalıştırılamayan yerde durur; çalıştırma engellemesi delinse dosya web kökü dışındadır; hepsi delinse yeniden kodlama payload'ı çoktan imha etmiştir. Dosya yükleme güvenliği, üst üste binen bu bağımsız savunmaların toplamıdır — sihirli bir tek kontrol değil.
