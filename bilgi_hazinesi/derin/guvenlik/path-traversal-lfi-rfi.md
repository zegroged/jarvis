# Path Traversal / LFI / RFI — Derin Dalış

Bu metin, özet makalenin devamıdır ve onun tekrarı değildir. Özet, kavramları ve savunma prensiplerini kuruyordu; burada ise gerçek kod üzerinden yürüyerek, gerçek CVE kayıtlarına demirleyerek, tasarım kararlarının takaslarını tartışarak ve sahadaki hataları kataloglayarak konuyu uygulamalı bir derinliğe taşıyoruz. Amaç savunma ve tespit: mekanizmayı bir mühendisin refleksle tanıyıp doğru kararı verebileceği kadar iyi anlamak. Operasyonel bir saldırı reçetesi değil, savunmacının zihin haritasıdır.

---

## 1. Çözümlü yürüyüş

Bu bölümde tek bir gerçekçi senaryoyu baştan sona götüreceğiz: çok dilli bir web uygulamasının "yardım merkezi" sayfası, kullanıcının seçtiği dile göre bir Markdown dosyasını okuyup HTML olarak render ediyor. Bu, sahada gördüğünüz en yaygın path-tabanlı endpoint kalıbıdır. Önce hatalı kodu yazacağız, sonra sorunun nasıl doğduğunu adım adım göstereceğiz, en sonda da doğru sürümü kuracağız.

### 1.1 Zafiyetli kod (Node.js / Express)

Aşağıdaki kod ilk bakışta masum görünür ve pek çok üretim sisteminde bu şekliyle çalışır:

```javascript
const express = require("express");
const fs = require("fs");
const path = require("path");
const app = express();

const DOKUMAN_KOKU = "/srv/app/yardim";

app.get("/yardim", (req, res) => {
  const konu = req.query.konu;            // örn. "kurulum"
  const dil = req.query.dil;              // örn. "tr"

  // Yolu düz string birleştirmeyle kuruyoruz:
  const dosyaYolu = DOKUMAN_KOKU + "/" + dil + "/" + konu + ".md";

  fs.readFile(dosyaYolu, "utf8", (err, icerik) => {
    if (err) return res.status(404).send("Belge bulunamadı");
    res.type("html").send(renderMarkdown(icerik));
  });
});
```

Geliştirici zihninde model nettir: `dil` ya `tr` ya `en`, `konu` ise `kurulum`, `sss` gibi bir dosya adı. Beklenen yol `/srv/app/yardim/tr/kurulum.md`. Uzantıyı sunucu kendi eklediği için "kullanıcı zaten uzantı seçemiyor" diye bir yanlış güven de kurulmuş.

### 1.2 Sorun nasıl ortaya çıkıyor (kavramsal)

Buradaki hata, yolun **anlamsal bir talimat** olduğunu ama kodun onu **düz metin** gibi ele almasıdır. `konu` ve `dil` değerleri hiçbir doğrulamadan geçmeden yola giriyor. Saldırgan `konu` yerine bir dizi `../` koyarsa, dosya sistemi bunları çözerken kök dizine kadar tırmanır:

```
konu = ../../../../etc/passwd%00
```

İşletim sistemi `/srv/app/yardim/tr/../../../../etc/passwd\0.md` yolunu çözerken her `..` için bir üst dizine çıkar; kök dizine varınca fazla `..`'lar etkisizleşir, sonra `etc/passwd`'e iner. Sondaki `.md` uzantısı ise sunucunun eklediği savunma gibi görünür — ama işte kritik nokta: **eski Node sürümlerinde** ( v8 öncesi, path'e gömülü null byte kontrolü gelmeden önce) null byte (`%00`) C tabanlı `open()` çağrısında dize sonu olarak yorumlanabiliyordu ve `.md` göz ardı ediliyordu. Modern Node, path içinde null byte görürse `ERR_INVALID_ARG_VALUE` fırlatır; bu, dilin zaman içinde bir savunma katmanı kazanmasının güzel bir örneğidir. Ama null byte kapansa bile sorun bitmez, çünkü uzantı hilesine hiç ihtiyaç olmayan senaryolar vardır: örneğin `dil` parametresi de aynı şekilde kirlidir ve `dil=../../../../etc` verip `konu=passwd`... hayır, yine `.md` takılır. Asıl mesele şu: uzantı eklemek bir güvenlik kontrolü değildir; en fazla tesadüfi bir engeldir ve saldırgan bunu (null byte, hedefte gerçekten `.md` uzantılı hassas dosya olması, ya da uzantıyı sorgu diziyle etkisizleştiren bağlamlar aracılığıyla) çeşitli yollarla aşabilir.

Daha da önemlisi: `..` kontrolü yapsak bile, ham string üzerinde yapılan her kontrol kandırılabilir. `%2e%2e%2f` (URL-kodlu `../`), çift kodlama `%252e%252e%252f`, ya da `....//` gibi kendini yeniden üreten kalıplar naif filtreleri deler. Bu yüzden çözüm ham girdiyi denetlemek değil, **işletim sisteminin çözdüğü sonucu** denetlemektir.

### 1.3 Düzeltilmiş kod

Doğru sürüm iki ilkeyi birlikte uygular: (a) mümkün olan yerde serbest metni allowlist'e indirgemek, (b) serbest ada mecbur kaldığımız yerde **önce kanonikleştir, sonra taban dizinde kaldığını doğrula**.

```javascript
const express = require("express");
const fs = require("fs").promises;
const path = require("path");
const app = express();

const DOKUMAN_KOKU = path.resolve("/srv/app/yardim");

// dil için serbest metne hiç izin vermiyoruz: kapalı bir allowlist.
const IZINLI_DILLER = new Set(["tr", "en", "de"]);

app.get("/yardim", async (req, res) => {
  const dil = String(req.query.dil ?? "");
  const konu = String(req.query.konu ?? "");

  // 1) dil: allowlist. Haritada yoksa reddet.
  if (!IZINLI_DILLER.has(dil)) {
    return res.status(400).send("Geçersiz dil");
  }

  // 2) konu: sıkı bir biçim doğrulaması. Ayırıcı, nokta-nokta,
  //    null byte, yüzde işareti — hepsi baştan elenir.
  if (!/^[a-z0-9_-]{1,64}$/.test(konu)) {
    return res.status(400).send("Geçersiz konu");
  }

  // 3) Yolu kur ve KANONİKLEŞTİR (symlink'leri de çözer).
  const aday = path.join(DOKUMAN_KOKU, dil, konu + ".md");
  let gercek;
  try {
    gercek = await fs.realpath(aday);
  } catch {
    return res.status(404).send("Belge bulunamadı");
  }

  // 4) Kanonik sonuç taban dizinin İÇİNDE mi? (ayırıcı ekleyerek)
  const kokAyirici = DOKUMAN_KOKU + path.sep;
  if (gercek !== DOKUMAN_KOKU && !gercek.startsWith(kokAyirici)) {
    return res.status(403).send("Erişim reddedildi");
  }

  try {
    const icerik = await fs.readFile(gercek, "utf8");
    res.type("html").send(renderMarkdown(icerik));
  } catch {
    res.status(404).send("Belge bulunamadı");
  }
});
```

Bu kodda dikkat edilecek dört ince nokta:

1. **`dil` için allowlist**, `konu` için sıkı regex.** İkisi farklı çünkü `dil` sonlu bir kümedir (allowlist mükemmel uyar), `konu` ise açık uçlu bir isimdir (regex + kanonikleştirme). En güçlü savunma her zaman "girdiyi hiç yola koyma"dır; onu uygulayabildiğimiz yerde (dil) uyguladık.
2. **`path.join` değil, güvenliğin asıl garantisi `fs.realpath`.** `path.join` yalnızca `.` ve `..`'yı sözdizimsel olarak sadeleştirir; symlink çözmez. `realpath` işletim sistemine gerçek fiziksel yolu sordurur — sembolik bağlantı dışarı işaret ediyorsa bunu ortaya çıkarır.
3. **Öntek kontrolü ayırıcıyla.** `startsWith(DOKUMAN_KOKU + path.sep)` yazdık; çıplak `startsWith(DOKUMAN_KOKU)` yazsaydık `/srv/app/yardim-gizli` gibi bir kardeş dizin kontrolü geçerdi. `gercek === DOKUMAN_KOKU` özel durumunu da ekledik (kök dizinin kendisi meşrudur).
4. **`realpath` dosya yoksa hata fırlatır.** Okuma senaryosunda bu iyidir (olmayan dosya = 404). Ama **yazma** senaryosunda dosya henüz yok olabilir; orada üst dizini `realpath` ile çözüp doğrulamak, sonra dosya adını eklemek gerekir. Bu ayrımı unutmak yaygın bir hatadır (bkz. Bölüm 4).

Regex savunmasının kanonikleştirmenin yerine değil, önüne konduğuna dikkat edin. Regex bir "erken ret" katmanıdır (defense in depth); tek başına yeterli sayılmaz, çünkü ileride biri regex'i gevşetirse (`.` karakterine izin verirse) kanonikleştirme hâlâ arkada durur.

### 1.4 Tespit: bu saldırıyı loglarda nasıl görürsünüz?

Savunmanın yarısı doğru kod, diğer yarısı ise sömürü denemelerini fark etmektir. Path traversal denemeleri log kayıtlarında oldukça ayırt edici bir imza bırakır; bir SOC analisti ya da bir alerting kuralı için şu desenler kırmızı bayraktır:

- Ham veya kodlanmış `..` dizileri: `../`, `..\`, `%2e%2e%2f`, `%2e%2e/`, `..%2f`, `%252e%252e%252f` (çift kodlama), `..%5c` (Windows ters bölü).
- Bilinen hassas dosya adlarının istek yolunda geçmesi: `etc/passwd`, `win.ini`, `boot.ini`, `.env`, `web.config`, `id_rsa`, `wp-config.php`.
- `php://`, `data://`, `file://`, `expect://` gibi PHP sarmalayıcı şemalarının parametre değerlerinde belirmesi — bunlar neredeyse her zaman LFI/RFI sömürü girişimidir.
- İstek parametrelerinde `http://` veya `https://` ile başlayan değerlerin bir dosya/modül parametresine gelmesi — klasik RFI imzası.
- Anormal sayıda `4xx` yanıtın tek bir kaynaktan, tek bir endpoint'e, art arda farklı yol varyasyonlarıyla gelmesi — bu, otomatik bir traversal fuzzer'ının parmak izidir.

Somut bir alerting kuralı iskeleti (kavramsal, herhangi bir log platformunda uygulanabilir):

```
# Erişim logunda çözülmüş (decode edilmiş) istek yolunda
# ".." veya bilinen sarmalayıcı/hedef desenleri ara.
uyar_eğer:
  method in [GET, POST]
  ve decode(request_path + query) matches
     /(\.\.[\/\\])|(%2e%2e)|(php:\/\/)|(data:\/\/)|(etc\/passwd)|(win\.ini)/i
  ve kaynak_ip aynı_pencerede >= 10 farklı_varyasyon
```

Kritik ince nokta: alerting'i uygularken **istek yolunu önce decode edin**, aksi hâlde `%2e%2e` gibi kodlanmış denemeler ham desen eşleşmesini atlatır — bu, tam da kod düzeyinde tartıştığımız "ham dizeye değil çözülmüş sonuca bak" ilkesinin tespit tarafındaki yansımasıdır. Ayrıca başarılı bir sömürüyü ayırt etmek için yanıt tarafına da bakın: bir `/etc/passwd` denemesine `200` dönen ve gövdesinde `root:x:0:0:` içeren bir yanıt, denemenin *başarılı olduğuna* dair güçlü bir sinyaldir ve olay müdahalesini (incident response) tetiklemelidir.

---

## 2. Gerçek dünya (CVE ile)

Bu zafiyet ailesinin en çarpıcı yanı, ne kadar **eski ve ne kadar tekrar eden** olduğudur. Aşağıdaki kayıtlar 1999'a uzanır; yani directory traversal, web'in ilk günlerinden beri aynı kök nedenle karşımızdadır ve bugün hâlâ yeni CVE'ler alır. Bu tarihsel süreklilik tek başına öğreticidir: sorun bir "eski hata" değil, dosya sistemi semantiğiyle string birleştirme arasındaki kalıcı uçurumun bir sonucudur.

**CVE-1999-0270** — SGI Performer API Search Tool içindeki `pfdispaly.cgi` programında bir directory traversal zafiyeti. Uzak saldırganların keyfi dosyaları okumasına izin veriyor. Bu, ailenin arketipidir: bir CGI programı, kullanıcıdan gelen bir dosya adı parametresini doğrulamadan dosya sistemine iletiyor. 1999'da bu kalıp o kadar yaygındı ki, CGI script'leri directory traversal'ın en verimli avlanma alanıydı. Bugün de aynı hata, farklı teknolojide (bir REST endpoint'i, bir template loader) tekrar ediyor.

**CVE-1999-1050** — Matt Wright'ın `FormHandler.cgi` script'inde bir directory traversal. İki farklı vektörle sömürülebiliyor: (1) `reply_message_attach` ek (attachment) parametresine `..` (dot dot) koyarak, ya da (2) dosya adını bir *template* olarak belirterek. Bu kayıt iki açıdan derslidir. Birincisi, **aynı endpoint'te birden fazla kirli parametre** olabileceğini gösterir — bizim 1.1'deki örnekte hem `dil` hem `konu` kirliydi; savunmacı *her* girdi yolunu izlemek zorundadır, sadece "belli olanı" değil. İkincisi, "template olarak belirtme" vektörü, bir parametrenin dosya adı olarak yorumlanmasının uygulama mantığına gömülü olabileceğini gösterir; yani kirlilik her zaman apaçık bir `?dosya=` parametresi biçiminde gelmez.

**CVE-1999-1069** — iCat Carbo Server 3.0.0'daki `carbo.dll` içinde, `icatcommand` parametresine `..` koyarak keyfi dosya okuma. Bu kayıt, zafiyetin **CGI'ye özgü olmadığını**, derlenmiş bir sunucu eklentisinde (DLL) de aynen ortaya çıktığını gösterir. Dil ve platform değişir, kök neden değişmez.

**CVE-1999-1082 ve CVE-1999-1083** — Jana proxy web server'ın iki ardışık sürümündeki (1.40 ve 1.45) directory traversal kayıtları özellikle öğreticidir. 1.40 sürümü (**CVE-1999-1082**) "`......`" (değiştirilmiş dot dot) saldırısına açıktı; 1.45 sürümü ise (**CVE-1999-1083**) klasik `..` saldırısına. Bu ikili, özet makalede anlattığımız `....//` mantığının canlı bir örneğidir: satıcı muhtemelen bir sürümde bir filtre eklemiş, ama filtre naif olduğu için **başka bir varyasyon** hâlâ geçmiştir. İki CVE'nin aynı üründe peş peşe çıkması, "kara liste ile yama" yaklaşımının klasik başarısızlık desenidir — bir kalıbı kapatırsınız, saldırgan kodlama/varyasyon uzayının başka bir köşesinden girer. Doğru çözüm hiçbir sürümde varyasyon avlamak değil, kanonikleştir-ve-doğrula disiplinini kurmaktı.

Bu beş kayıttan çıkan ortak ders: (1) zafiyet teknolojiden bağımsızdır — CGI, DLL, proxy, hepsinde aynıdır; (2) tek bir parametreyi değil tüm girdi yollarını denetlemek gerekir; (3) filtreyle varyasyon kovalamak (Jana örneği) kaybeden bir stratejidir. Kayıtlardaki CWE alanları "n/a" olsa da, bunlar modern sınıflandırmada **CWE-22 (Improper Limitation of a Pathname to a Restricted Directory)** başlığı altındadır; bugün bir zafiyeti raporlarken bu CWE'yi kullanmak, aramada ve önceliklendirmede işinizi kolaylaştırır.

---

## 3. Karşılaştırma / karar

Savunmanın birden fazla yolu vardır ve hepsi her bağlama uymaz. Aşağıda ana yaklaşımları takaslarıyla karşılaştırıyoruz; sondaki karar rehberi hangi durumda hangisini seçeceğinizi özetliyor.

### 3.1 Allowlist (dolaylı tanımlayıcı) vs. serbest ad + kanonikleştirme

**Allowlist / dolaylı tanımlayıcı:** Kullanıcı `?dil=tr` gibi bir anahtar verir; sunucu bunu bir haritadan gerçek dosya adına çevirir. Kullanıcının enjekte edeceği hiçbir yol dizesi yoktur.
- *Artıları:* Zafiyeti kökten yok eder. Denetlenmesi kolaydır (harita sonlu). Kodlama hilelerinin hiçbiri uygulanamaz çünkü girdi zaten yola girmiyor.
- *Eksileri:* Yalnızca dosya kümesi **sonlu ve bilinebilir** olduğunda uygulanır. Binlerce belge, kullanıcı yüklemeleri, dinamik dosya adları varsa harita tutulamaz.
- *Ne zaman:* Dil dosyaları, tema adları, sabit sayfa listeleri, rapor tipleri gibi kapalı kümeler. **Uygulanabildiği her yerde ilk tercih budur.**

**Serbest ad + kanonikleştir-ve-doğrula:** Kullanıcı gerçek bir ad verir (`?konu=kurulum`); yolu `realpath` ile çözer, taban dizinde kaldığını doğrularız.
- *Artıları:* Açık uçlu dosya kümelerini destekler. Doğru yapıldığında sağlamdır.
- *Eksileri:* Doğru yapmak zordur — sıra (önce çöz, sonra doğrula), ayırıcılı öntek, symlink, yoksa-dosya durumu gibi ince noktalar var. Her birini kaçırmak bir zafiyettir.
- *Ne zaman:* Dosya adları önceden bilinemediğinde. Allowlist mümkün değilse **mecburi** yöntemdir.

### 3.2 Kanonikleştirme (`realpath`) vs. sözdizimsel normalize (`path.normalize` / `path.join`)

Bu ayrım hayatidir ve çok sık karıştırılır. `path.normalize`/`path.join` yalnızca **string düzeyinde** `.` ve `..`'yı sadeleştirir; dosya sistemine hiç sormaz, dolayısıyla **symlink çözmez**. `realpath` ise işletim sistemine gidip fiziksel gerçek yolu döndürür.
- Yalnızca `normalize` kullanırsanız, taban dizin içindeki bir symlink dışarı işaret ediyorsa (`/srv/app/yardim/dis -> /etc`) `..` hiç kullanmadan dışarı çıkılır ve `normalize` bunu göremez.
- `realpath` daha güvenlidir ama bir **dosya sistemi çağrısı** yapar (maliyet + dosya var olmalı). Yüksek hacimli, çok kısa ömürlü isteklerde bu maliyet önemsizdir ama bilinçli olun.
- *Karar:* Güvenlik sınırı doğrulaması için **her zaman `realpath` sınıfı** (symlink çözen) bir fonksiyon kullanın. `normalize` yalnızca kozmetik/performans amaçlı ön-sadeleştirme için, doğrulamanın *yerine değil önüne* konabilir.

### 3.3 Kod düzeyi savunma vs. WAF (imza tabanlı)

- **WAF** bilinen traversal imzalarını (`../`, `%2e%2e`) yakalar. *Artısı:* kod değişikliği gerektirmeden hızlı bir katman ekler, gürültüyü ve otomatik taramaları azaltır. *Eksisi:* çift kodlama, overlong UTF-8, `....//` gibi varyasyonlarla atlatılır; **birincil savunma sayılamaz**.
- **Kod düzeyi savunma** (allowlist / kanonikleştirme) asıl güvenliği verir ama geliştirme gerektirir.
- *Karar:* İkisi rakip değil, katmandır. WAF'ı **erken filtre / gürültü azaltıcı** olarak konumlayın; gerçek garantiyi koda koyun. "WAF var, güvendeyiz" cümlesi bir hata modudur (Bölüm 4).

### 3.4 İzolasyon: chroot / konteyner / `open_basedir` vs. hiçbiri

- **Least privilege + chroot/konteyner/namespace**, traversal başarılı *olsa bile* ödülü küçültür. Proses `/etc/shadow`'u okuyamıyorsa, başarılı bir traversal bile sınırlı hasar verir.
- *Artısı:* Kod bug'ından **bağımsız** ikinci savunma hattıdır; kod yanılırsa hâlâ korur.
- *Eksisi:* Tek başına yeterli değildir — hapis içindeki hassas dosyalar (uygulama config'i, DB parolaları) yine sızabilir.
- *Karar:* Her zaman uygulayın, ama **asla tek savunma olarak değil.** İzolasyon, kod savunmasının başarısız olduğu günü hafifletmek içindir.

### 3.5 RFI'ye özel: yapılandırma sıkılaştırma

RFI büyük ölçüde bir yapılandırma zafiyetidir. PHP'de `allow_url_include`'ı kapalı tutmak, klasik RFI'yi ve `php://input`/`data://` üzerinden uzak kod çalıştırmayı tek hamlede engeller. Modern PHP'de varsayılan kapalıdır; ama karar şudur: bunu **doğrulanmış bir baseline** olarak ele alın, "muhtemelen kapalıdır" diye varsaymayın — eski/yanlış yapılandırılmış sunucularda açık kalabilir.

**Özet karar rehberi:** Kapalı küme mi? → Allowlist. Açık küme mi? → Kanonikleştir-ve-doğrula (`realpath` + ayırıcılı öntek). Her iki durumda da → least privilege + izolasyon + (varsa) WAF'ı ek katman olarak. PHP'de → `allow_url_include` kapalı baseline. Hiçbir zaman → tek katmana güvenme.

---

## 4. Hata-modu kataloğu

Aşağıdakiler, geliştiricilerin ve savunmacıların bu konuda tekrar tekrar yaptığı, zafiyeti açık bırakan tipik hatalardır. Her biri sahada gerçek ihlallere yol açmıştır.

1. **Kara liste ile temizleme.** Girdiden `../` dizisini silmek ya da arayıp reddetmek. `%2e%2e`, çift kodlama (`%252e`), `....//` (kendini yeniden üreten) ve karışık ayırıcılar bunu deler; aynı anlama gelen sonsuz varyasyon vardır, hepsini sayamazsınız.

2. **Doğrulamayı yanlış sırada yapmak.** Kanonikleştirmeden *önce* ham dizede kontrol etmek. İşletim sisteminin çözeceği sonuç ile sizin denetlediğiniz farklı iki şey olur. Doğru sıra değişmez: önce çöz (`realpath`), sonra doğrula.

3. **Sözdizimsel normalize'ı kanonikleştirme sanmak.** `path.normalize`/`path.join` symlink çözmez; yalnızca string'i sadeleştirir. Taban dizin içindeki bir symlink dışarı işaret ediyorsa `..` olmadan dışarı çıkılır ve normalize bunu göremez. Güvenlik doğrulaması `realpath` sınıfı bir çağrı ister.

4. **Öntek karşılaştırmasında ayırıcıyı unutmak.** `startsWith("/srv/app/yardim")` kontrolü `/srv/app/yardim-gizli`'yi de geçirir. Karşılaştırmayı sondaki ayırıcıyla (`+ path.sep`) yapmak ve kökün kendisini ayrı ele almak gerekir.

5. **Uzantı ekleyerek güvende olduğunu sanmak.** Sunucunun `.md`/`.php` eklemesi bir kontrol değildir. Null byte (eski yığınlarda), sorgu dizesi hilesi (`?`/`#`) ve hedefte gerçekten o uzantılı hassas dosya olması bu "savunmayı" boşa çıkarır.

6. **LFI'yi "sadece okuma, düşük risk" diye küçümsemek.** Yorumlanan bir bağlamda LFI, log zehirleme (`access.log`/`auth.log`), session dosyası zehirleme, upload edilen dosya veya `php://input`/`php://filter` sarmalayıcıları yoluyla neredeyse her zaman RCE'ye tırmanır. Risk sınıflandırmasını yüksek tutun.

7. **Aynı endpoint'te birden fazla kirli parametreyi gözden kaçırmak.** CVE-1999-1050'nin iki ayrı vektörü gibi, bir endpoint'te birden çok parametre dosya sistemine akabilir. "Belli olan" parametreyi doğrulayıp diğerini unutmak yaygındır; *tüm* girdi yollarını izleyin.

8. **Yazma senaryosunu okuma gibi ele almak.** `realpath` olmayan dosyada hata fırlatır; okuma için bu iyidir ama yazma/upload yolunda dosya henüz yoktur. Üst dizini çözüp orada doğrulamadan dosya adı eklerseniz, traversal keyfi dosya *yazmaya* (dolayısıyla RCE'ye) dönüşür.

9. **WAF'ı birincil savunma sanmak.** İmza tabanlı filtreler yardımcıdır ama kodlama varyasyonlarıyla atlatılır. "WAF koruyor" diye kodu savunmasız bırakmak klasik bir yanılgıdır.

10. **`allow_url_include`/`allow_url_fopen`'ı varsayımla geçmek.** "Modern PHP'de kapalıdır" diyerek doğrulamadan geçmek. Eski veya elle değiştirilmiş yapılandırmalarda açık kalabilir; baseline'ı ölçün, varsaymayın.

11. **Symlink ve hardlink'i tehdit modeline almamak.** Taban dizinin içine yerleştirilmiş (ör. bir yükleme mekanizmasıyla) bir symlink dışarı işaret edebilir. `realpath` bunu çözer; `normalize` çözmez. Symlink'i unutan her doğrulama eksiktir.

12. **Hata mesajlarıyla bilgi sızdırmak.** "Belge bulunamadı" yerine tam dosya yolunu veya stack trace'i döndürmek, saldırgana dosya sistemi yapısını ve hangi yolların var olduğunu (var/yok ayrımıyla) haritalama imkânı verir. Traversal'ın kendisi kadar tehlikeli olan bu yan kanal (oracle) sık ihmal edilir; genel, ayırt etmeyen hata yanıtları verin.

---

## Kapanış

Bu üç zafiyet — Path Traversal, LFI, RFI — kökeninde tek bir hatanın farklı yüzleridir: kullanıcı girdisine dosya sistemi bağlamında körü körüne güvenmek. 1999'un CGI script'lerinden bugünün REST endpoint'lerine kadar aynı kök neden tekrar eder; teknoloji değişir, hata değişmez. Çözüm de değişmez: ya girdiyi bir yola hiç sokma (allowlist), ya da işletim sisteminin çözdüğü kanonik sonucu izin verilen sınıra karşı katı bir biçimde doğrula. Saldırganın sonsuz kodlama hilelerini kovalamak kaybeden bir oyundur; sonucu doğrulamak kazanan tek stratejidir.
