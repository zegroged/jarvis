# Dosya Yükleme Zafiyetleri (File Upload Vulnerabilities)

## Giriş ve Tanım

Dosya yükleme (file upload) işlevi, modern web uygulamalarının neredeyse her yerinde karşımıza çıkar: profil fotoğrafı, CV yükleme, fatura eki, ürün görseli, destek talebine dosya iliştirme. Kullanıcının kontrol ettiği ham veriyi (byte dizisini) sunucunun dosya sistemine yazma eylemi, doğası gereği güvenlik açısından en tehlikeli operasyonlardan biridir. Çünkü bu noktada uygulama, **güvenilmeyen girdiyi** (untrusted input) yalnızca hafızada işlemekle kalmaz, onu kalıcı bir varlık hâline getirir ve çoğu zaman aynı sunucunun erişebildiği bir konuma yerleştirir.

Dosya yükleme zafiyeti, en yıkıcı biçiminde saldırganın sunucu üzerinde **uzaktan kod çalıştırmasına** (RCE - Remote Code Execution) yol açar. Bunun klasik aracı da **web shell**'dir: sunucuda çalışabilen, saldırgana bir komut arayüzü veren küçük bir betik dosyası. Ancak web shell tek risk değildir; XSS'e yol açan HTML/SVG yüklemesi, path traversal ile dosya üzerine yazma, DoS amaçlı dev dosyalar veya "zip bomb", kütüphane ayrıştırma (parser) hatalarını tetikleyen bozuk medya dosyaları da bu başlığın altındadır.

Bu makalede önce sorunun **kök nedenine** ineceğiz (neden bir dosya yüklemesi kod çalıştırmaya dönüşebiliyor?), ardından uzantı ve MIME tabanlı doğrulamaların **nasıl bypass edildiğini**, web shell mantığını, ve nihayet gerçekten işe yarayan savunma katmanlarını (tip doğrulama, izole depolama, çalıştırma engelleme) tartışacağız.

---

## Kök Neden: Neden Bir Dosya Yüklemesi Kod Çalıştırabilir?

Sorunun özü tek bir cümlede toplanabilir: **Yüklenen dosya, sunucunun onu "veri" değil de "kod" olarak yorumlayabileceği bir konuma ve biçime düşerse, felaket başlar.**

Bunu anlamak için bir web sunucusunun bir isteğe nasıl yanıt verdiğini hatırlamak gerekir. Kullanıcı `/uploads/avatar.php` adresini istediğinde, web sunucusu (Apache, Nginx, IIS) bu yolu bir dosyaya eşler. Kritik soru şudur: sunucu bu dosyayı **olduğu gibi mi gönderecek** (statik içerik) yoksa bir **yorumlayıcıya (interpreter) mı devredecek**? Örneğin Apache + mod_php yapılandırmasında `.php` uzantılı dosyalar PHP motoruna verilir ve içindeki kod **çalıştırılır**. Yani saldırgan `<?php system($_GET['c']); ?>` içeren bir dosyayı `uploads` klasörüne `.php` uzantısıyla yerleştirebilirse, o dosyaya tarayıcıdan eriştiği anda kod sunucu bağlamında koşar.

Buradan üç temel önkoşul çıkar; bir dosya yükleme zafiyetinin RCE'ye dönüşmesi genellikle bu üçünün **aynı anda** sağlanmasını gerektirir:

1. **Saldırgan dosyanın içeriğini kontrol edebiliyor** (zararlı payload'ı koyabiliyor).
2. **Dosya, sunucunun çalıştırabileceği bir konuma yazılıyor** (web kök dizininin altında, doğrudan URL ile erişilebilir).
3. **Dosya, bir yorumlayıcıyı tetikleyecek biçimde adlandırılıyor/tanınıyor** (uzantı, MIME veya sunucu yapılandırması yüzünden kod olarak işleniyor).

Savunmanın mantığı da doğrudan buradan türetilir: bu üç koşuldan **herhangi birini** kırarsanız istismarı büyük ölçüde engellersiniz. İçeriği tam kontrol etmek zordur (dosya yüklemenin amacı zaten içerik almaktır), ama 2. ve 3. koşulları kırmak — yani dosyayı çalıştırılamaz bir yerde tutmak ve tipini katı biçimde doğrulamak — çok daha uygulanabilirdir. Bu yüzden ilerideki savunma bölümünde en çok bu iki eksene ağırlık vereceğiz.

---

## Uzantı Tabanlı Doğrulama ve Bypass Yöntemleri

En yaygın (ve tek başına en zayıf) savunma, dosya adının uzantısına bakmaktır. Geliştirici genellikle iki yaklaşımdan birini seçer:

- **Kara liste (blacklist):** "`.php`, `.asp`, `.jsp`, `.exe` yasak, gerisi serbest."
- **Beyaz liste (whitelist):** "Yalnızca `.jpg`, `.png`, `.gif` serbest, gerisi yasak."

**Kök neden olarak kara listeler yapısal olarak kusurludur.** Çünkü güvenliği "bilinen kötü olanı reddetmek" üzerine kurarlar; oysa saldırgan yalnızca listede olmayan **tek bir** çalışabilir uzantı bulmak zorundadır. Web sunucuları ise şaşırtıcı derecede çok sayıda uzantıyı kod olarak yorumlayabilir.

### Yaygın Kara Liste Bypass Teknikleri

**Alternatif çalışabilir uzantılar.** PHP ekosisteminde tarihsel olarak `.php` dışında `.php3`, `.php4`, `.php5`, `.phtml`, `.pht` gibi uzantılar da bazı yapılandırmalarda PHP olarak işlenmiştir. Geliştirici yalnızca `.php`'yi engellerse, bu türevler açık kalır. Aynı mantık ASP tarafında `.asp` / `.aspx` / `.cer` / `.asa` gibi türevler için de geçerlidir. Buradaki ders: engellemeyi tek bir uzantıya göre yapmak, o teknolojinin **tüm** çalışabilir uzantılarını bilmeyi gerektirir ki bu bilgi zamanla ve yapılandırmaya göre değişir.

**Büyük/küçük harf oynaması.** Kontrol `.php` string'ini birebir arıyorsa, `.PHP`, `.PhP` gibi varyantlar bazı platformlarda (özellikle büyük/küçük harfe duyarsız dosya sistemlerinde, Windows gibi) yine çalıştırılabilir. Kontrolün büyük/küçük harf normalizasyonu yapmaması klasik bir hatadır.

**Sondaki nokta, boşluk veya özel karakterler.** `shell.php.` (sonda nokta) veya `shell.php%20` gibi adlar, bazı işletim sistemi/dosya sistemi kombinasyonlarında yazılırken **normalize edilerek** sondaki fazlalık atılır ve dosya `shell.php` olarak kaydedilir. Uygulama uzantı kontrolünü ham string üzerinde yaparken, dosya sistemi başka bir isimle kaydeder — arada bir tutarsızlık (parsing farkı) doğar.

**Çift uzantı (double extension).** `shell.php.jpg` veya `shell.jpg.php` gibi adlar. Bunun sömürülebilirliği tamamen sunucunun uzantıyı **nasıl ayrıştırdığına** bağlıdır. Tarihsel olarak yanlış yapılandırılmış Apache kurulumları, bir dosyada birden fazla uzantı gördüğünde **tanıdığı ilk çalışabilir uzantıya** göre işlem yapabiliyordu; örneğin `shell.php.jpg` dosyasını PHP olarak koşabiliyordu. Bu davranış yapılandırmaya (`AddHandler` / `AddType` yönergelerine) bağlıdır; her kurulumda olmaz ama olduğunda çift uzantı beyaz listeyi de aşabilir.

**Null byte injection.** Eski PHP sürümlerinde (5.3.4 öncesi dönem) ve bazı C tabanlı alt katmanlarda, `shell.php%00.jpg` gibi bir ad, string'in C seviyesinde null byte'ta (`\0`) sonlanması nedeniyle dosya sistemine `shell.php` olarak yazılabiliyordu; oysa uygulamanın uzantı kontrolü `.jpg` gördüğü için geçiyordu. Bu bugün büyük ölçüde yamalanmış tarihsel bir tekniktir, ama mantığı öğreticidir: **uygulamanın gördüğü string ile dosya sistemine yazılan ad aynı olmayabilir.**

**Yapılandırma dosyası yükleme (.htaccess / web.config).** Bu incelikli ve güçlü bir vektördür. Saldırgan doğrudan bir `.php` yükleyemiyorsa bile, yazılabilir dizine bir `.htaccess` dosyası yükleyerek Apache'ye "bu dizindeki `.jpg` dosyalarını PHP olarak işle" dedirtebilir (`AddType application/x-httpd-php .jpg` benzeri bir yönergeyle). Ardından zararlı kodu `.jpg` olarak yükler. IIS tarafında benzer rol `web.config` dosyasındadır. Ders: yalnızca "çalışabilir uzantıları" düşünmek yetmez; **sunucunun davranışını değiştirebilecek** yapılandırma dosyalarını da yasaklamak gerekir.

### İstismar Mantığı

Saldırganın gözünden süreç şöyledir: önce yükleme formunun kabul ettiği/reddettiği uzantıları deneme-yanılmayla haritalar (fuzzing). Bir dosya kabul edildiğinde, onun **nereye kaydedildiğini** ve **doğrudan erişilebilir olup olmadığını** bulmaya çalışır (yükleme sonrası dönen URL, yanıt başlıkları, tahmin edilebilir yol desenleri). Erişilebilir ve çalıştırılabilir bir konum + kod olarak yorumlanan bir uzantı bir araya geldiğinde web shell'i çağırır.

---

## MIME / Content-Type Tabanlı Doğrulama ve Bypass

İkinci yaygın savunma, HTTP isteğindeki `Content-Type` başlığına veya multipart form verisindeki her parçanın MIME tipine bakmaktır. "Yalnızca `image/jpeg` ve `image/png` kabul et" gibi.

**Kök neden olarak bu da tek başına güvenilmezdir, çünkü `Content-Type` başlığını istemci gönderir ve istemci = saldırgandır.** MIME tipi dosyanın gerçek içeriğinden türetilmez; multipart isteğinde her parçanın yanında beyan edilen, tamamen değiştirilebilir bir metadata alanıdır. Saldırgan, içinde PHP kodu olan bir dosyayı `Content-Type: image/png` etiketiyle gönderebilir. Sunucu yalnızca bu beyan edilen değere bakıyorsa, kontrol anlamsızdır.

### MIME Bypass Teknikleri

**Beyan edilen Content-Type'ı elle değiştirme.** Bir proxy (Burp Suite gibi) veya basit bir script ile multipart parçadaki `Content-Type` satırı `image/jpeg` yapılır; gövde ise web shell'dir. Sunucu içeriği açmadan sadece etikete güveniyorsa geçer.

**Magic bytes / sihirli sayı taklidi.** Bazı sunucular, MIME tipini beyandan değil dosyanın ilk baytlarındaki **imzadan** (magic bytes / file signature) çıkarır — örneğin bir PNG dosyası `\x89PNG\r\n\x1a\n` ile başlar, JPEG `\xFF\xD8\xFF` ile başlar, GIF ise `GIF87a`/`GIF89a` ile. Bu daha iyi bir kontroldür ama tek başına yeterli değildir. Çünkü saldırgan **polyglot** bir dosya üretebilir: dosya geçerli bir GIF imzasıyla başlar (kontrolü geçer), ama devamında PHP kodu barındırır. Sunucu bu dosyayı `.php` olarak koşuyorsa, PHP yorumlayıcısı GIF başlığını "önemsiz metin" olarak geçer ve `<?php ... ?>` bloğunu çalıştırır. Yani "geçerli görsel imzası" ile "çalıştırılamaz içerik" aynı şey değildir.

**Görsel içine kod gömme (EXIF / metadata).** Gerçekten geçerli bir JPEG'in EXIF metadata alanına (örneğin `Comment` alanına) PHP payload'ı yerleştirilebilir. Dosya tam anlamıyla geçerli bir görseldir, açılır, görüntülenir — ama içine gömülü kod, dosya bir PHP yorumlayıcısına verildiğinde tetiklenir. Bu, "dosya gerçekten görsel olsa bile güvenli değildir" gerçeğinin altını çizer; asıl belirleyici, dosyanın **çalıştırılıp çalıştırılmadığıdır**, geçerli bir medya olup olmadığı değil.

Buradan çıkan derin ilke şudur: **İçerik doğrulama (dosyanın gerçekten görsel olması) ile çalıştırma engelleme (dosyanın asla kod olarak koşmaması) birbirinden bağımsız iki savunmadır ve ikisine de ihtiyaç vardır.** Tek başına içerik doğrulama, gömülü payload'lara karşı zayıftır; tek başına çalıştırma engelleme ise XSS/DoS gibi diğer riskleri kapatmaz.

---

## Web Shell: Mantığı, Yaşam Döngüsü ve Savunma

**Web shell**, sunucuda çalışabilen ve saldırgana uzaktan komut yürütme/dosya yönetimi imkânı veren bir betiktir. En küçük hâli tek satırdır (kavramsal olarak `system($_REQUEST['cmd'])` benzeri bir yapı); en gelişmişleri dosya gezgini, veritabanı arayüzü, ağ tarama ve yetki yükseltme araçları içeren tam panellerdir.

### Neden Bu Kadar Tehlikeli?

Web shell, uygulamanın çalıştığı kullanıcı bağlamında (örneğin `www-data`) koşar. Bu, saldırganın artık uygulamanın erişebildiği her şeye — yapılandırma dosyaları, veritabanı kimlik bilgileri, iç ağ — erişebilmesi demektir. Web shell çoğu zaman **kalıcılığın** (persistence) ve **yanal harekete** (lateral movement) geçişin ilk adımıdır: saldırgan buradan yetki yükseltmeyi (privilege escalation) dener, iç ağı tarar, başka sistemlere sıçrar.

### Saldırı Zinciri

1. Yükleme noktası bulunur ve doğrulama bypass edilir (uzantı veya MIME).
2. Web shell çalıştırılabilir bir konuma yazılır.
3. Dosyanın URL'i bulunur ve tarayıcı/curl ile çağrılır.
4. Komutlar çalıştırılır, kalıcılık ve keşif başlar.

### Savunma — Web Shell'i Anlamsız Kılmak

Web shell'e karşı en güçlü savunma, onu tespit etmeye çalışmak (imza/antivirüs) değil, **çalışamayacağı bir dünya kurmaktır**. Eğer yüklenen dosyalar hiçbir koşulda yorumlayıcıya verilmiyorsa, saldırgan mükemmel bir web shell yüklese bile o dosya yalnızca inert bir byte yığınıdır; URL'ine gidildiğinde çalıştırılmak yerine indirilir veya reddedilir. İzole depolama ve çalıştırma engelleme bölümünde bunu ayrıntılandıracağız. Bu yüzden sağlam mimaride web shell yüklemesi "kritik" olmaktan çıkıp "etkisiz denemeye" iner.

---

## Savunma Mimarisi: Katmanlı ve "Neden"leriyle

Etkili savunma tek bir kontrole değil, **derinlemesine savunmaya** (defense in depth) dayanır. Aşağıdaki katmanların hiçbiri tek başına yeterli değildir; birlikte, saldırganın aşması gereken engellerin sayısını ve maliyetini büyütürler.

### 1. Katı Tip Doğrulama (İçerik Tabanlı, Beyaz Liste)

- **Beyaz liste kullanın, kara liste değil.** "Neyin serbest olduğunu" tanımlamak, "neyin yasak olduğunu" saymaktan çok daha güvenlidir; çünkü beyaz liste, aklınıza gelmeyen tehlikeli uzantıyı da varsayılan olarak reddeder.
- **Uzantıya değil içeriğe bakın.** MIME'ı beyan edilen `Content-Type`'tan değil, dosyayı gerçekten inceleyerek belirleyin. Sunucu tarafında güvenilir bir dosya tipi tespit kütüphanesi (örneğin içeriği analiz eden magic-byte tabanlı çözümler) kullanın, ama bunun **da** tek başına yetmeyeceğini (polyglot/EXIF payload) unutmayın.
- **Mümkünse dosyayı yeniden işleyin (re-encode / sanitize).** Görseller için en güçlü tekniklerden biri, yüklenen görseli bir kütüphaneyle açıp **yeniden kodlayarak** (örneğin yeniden çizip yeni bir dosya olarak kaydederek) baştan üretmektir. Bu işlem, EXIF'e veya dosya kuyruğuna gömülü payload'ları büyük ölçüde yok eder; çünkü çıktı, girdinin baytları değil, ayrıştırılmış piksellerden yeniden üretilmiş temiz bir dosyadır. PDF/Office belgeleri için sanitizasyon daha zordur ve genellikle ayrı bir izole işleme gerektirir.
- **Boyut ve boyutları sınırlayın.** DoS ve zip-bomb risklerine karşı maksimum dosya boyutu, görseller için maksimum piksel boyutu (decompression bomb koruması) gibi sınırlar koyun.

### 2. İzole Depolama (Isolated Storage)

Bu, **kök nedeni doğrudan hedefleyen** en değerli savunmadır; çünkü yukarıda saydığımız üç önkoşuldan "çalıştırılabilir konuma yazma"yı kırar.

- **Dosyaları web kök dizininin (document root) DIŞINA yazın.** Uygulama dosyaları bir yola koyar, ama o yol web sunucusu tarafından doğrudan URL ile servis edilemez. İçerik kullanıcıya sunulacaksa, uygulama dosyayı **kod aracılığıyla** okuyup kontrollü biçimde (doğru `Content-Type`, `Content-Disposition: attachment` başlıklarıyla) geri verir. Böylece dosyaya doğrudan `/uploads/shell.php` gibi erişip yorumlayıcıyı tetiklemek mümkün olmaz.
- **Daha da iyisi: ayrı bir alan/altyapı.** Kullanıcı içeriğini uygulama sunucusundan tamamen ayrı bir servis üzerinden (ayrı bir depolama servisi veya en azından çerezsiz, kod çalıştırmayan ayrı bir alt alan adından) sunmak, hem RCE hem de XSS yüzeyini küçültür. Ayrı bir origin, yüklenen HTML/SVG'nin ana uygulamanın oturum bağlamında XSS yapmasını da engeller.
- **Dosya adlarını sunucu üretsin.** Kullanıcının verdiği adı asla doğrudan kullanmayın. Rastgele/rakamsal bir ad üretip (örneğin bir UUID) orijinal adı yalnızca metadata olarak saklayın. Bu, hem **path traversal** (`../../etc/passwd` gibi) saldırılarını, hem sondaki nokta/null-byte oyunlarını, hem de dosya üzerine yazma (overwrite) senaryolarını tek hamlede kapatır.

### 3. Depolama Konumunda Çalıştırmayı Engelleme

İzole depolamayı tamamlayan katman: yükleme dizinini web sunucusu düzeyinde **çalıştırılamaz** ilan edin.

- Web sunucusu yapılandırmasında yükleme dizini için tüm script işleyicilerini (PHP handler, CGI vb.) devre dışı bırakın; bu dizindeki her şey **statik** olarak servis edilsin.
- **Kullanıcının yapılandırma dosyası yüklemesini önleyin.** Yükleme dizininde `.htaccess`, `web.config` gibi dosyaların hem yüklenmesini engelleyin hem de sunucuyu bu dizindeki yerel yapılandırma dosyalarını yok sayacak biçimde ayarlayın (örneğin `AllowOverride None` benzeri bir yaklaşımla). Aksi hâlde saldırgan, çalıştırma engellemenizi kendi yüklediği yapılandırmayla geçersiz kılabilir.
- Dosya sistemi izinlerini kısın: yükleme dizini yazılabilir olmalı ama **çalıştırılabilir (execute) olmamalı**; uygulama süreci bu dizine yalnızca gereken minimum yetkiyle erişmeli (least privilege).

### 4. Sunum (Serving) Katmanı Sertleştirmesi

Dosya yüklendikten sonra **nasıl geri sunulduğu** da ayrı bir zafiyet kaynağıdır:

- İndirmelerde `Content-Disposition: attachment` ve doğru `Content-Type` verin; tarayıcının içeriği yorumlamasını değil indirmesini teşvik edin.
- **MIME sniffing'i kapatın:** `X-Content-Type-Options: nosniff` başlığı, tarayıcının beyan edilen tipi görmezden gelip içeriği "tahmin ederek" (örneğin bir `.txt`'yi HTML gibi) çalıştırmasını engeller. Aksi hâlde zararsız görünen bir dosya XSS'e dönüşebilir.
- SVG özel bir tehlikedir: geçerli bir "görsel" olmasına rağmen içine `<script>` gömülebilir ve tarayıcıda çalışır. SVG'leri ayrı origin'den sunun, mümkünse sanitize edin veya doğrudan render yerine indirme olarak verin.

### 5. Diğer Katmanlar

- **Kimlik doğrulama ve yetkilendirme:** Yükleme uçlarını yalnızca yetkili kullanıcılara açın; her yükleme noktası ek bir saldırı yüzeyidir.
- **Antivirüs / zararlı yazılım taraması:** Yüklenen dosyaları bir tarayıcıdan geçirmek, özellikle dosyaların başka kullanıcılara dağıtıldığı senaryolarda (belge paylaşımı) değerlidir. Ama bunu bir "ek katman" olarak görün, birincil savunma olarak değil — imza tabanlı tarama yeni/özelleştirilmiş payload'ları kaçırabilir.
- **Loglama ve izleme:** Yükleme dizininde beklenmedik dosya türleri veya bu dizinden gelen çalıştırma girişimleri için uyarılar kurun.

---

## Yaygın Hatalar

Aşağıdakiler, tecrübeli ekiplerin bile düştüğü, kök nedeni "yanlış katmana güvenmek" olan hatalardır:

- **Yalnızca istemci tarafı (client-side) doğrulama.** JavaScript ile uzantı/boyut kontrolü sadece kullanım kolaylığı içindir; saldırgan isteği doğrudan üreterek bunu tamamen atlar. Doğrulama **her zaman** sunucu tarafında, otoriter biçimde yapılmalıdır.
- **Beyan edilen `Content-Type`'a güvenmek.** İstemcinin gönderdiği başlığı dosyanın gerçek tipi sanmak, en yaygın MIME bypass'ının kapısıdır.
- **Kara liste ile uzantı engelleme.** Eksik kalması neredeyse garantidir; bir türev uzantı, harf büyüklüğü oyunu veya yapılandırma dosyası mutlaka atlanır.
- **"Geçerli görsel = güvenli" varsayımı.** EXIF'e gömülü payload ve polyglot dosyalar bu varsayımı çürütür. Geçerlilik, çalıştırılamazlıkla aynı şey değildir.
- **Dosyayı web kökünün altına, tahmin edilebilir adla yazmak.** Bu, üç önkoşuldan ikisini saldırgana bedava sunar (erişilebilir konum + kontrol edilebilir ad).
- **Kullanıcının verdiği dosya adını doğrudan kullanmak.** Path traversal, üzerine yazma ve uzantı oyunlarının hepsini davet eder.
- **Yeniden kodlamayı atlayıp yalnızca imza kontrolüne güvenmek.** Magic-byte kontrolü gerekli ama yeterli değildir.
- **Sunum başlıklarını unutmak.** İçeriği güvenli sakladıktan sonra `nosniff` ve doğru `Content-Type` olmadan geri sunmak, XSS kapısını açık bırakır.

---

## En İyi Pratikler (Özet Kontrol Listesi)

Bir dosya yükleme işlevini güvenli kabul etmeden önce şu soruların hepsine "evet" diyebilmelisiniz:

1. **Doğrulama sunucu tarafında ve beyaz liste temelli mi?** Uzantı, gerçek içerik tipi ve boyut ayrı ayrı doğrulanıyor mu?
2. **Dosya web kök dizininin dışında mı saklanıyor** ve yalnızca kontrollü bir uygulama kanalıyla mı sunuluyor?
3. **Depolama dizininde script çalıştırma tümüyle kapalı mı?** `.htaccess`/`web.config` gibi yapılandırma dosyaları hem yüklenemez hem de yok sayılıyor mu?
4. **Dosya adı sunucu tarafından üretiliyor mu** (kullanıcı girdisinden bağımsız, rastgele), path traversal imkânsız mı?
5. **Görseller yeniden kodlanıp sanitize ediliyor mu;** SVG/HTML için özel önlemler alınmış mı?
6. **Sunum başlıkları sert mi?** `Content-Disposition: attachment`, doğru `Content-Type`, `X-Content-Type-Options: nosniff`.
7. **Kullanıcı içeriği ayrı bir origin'den mi** servis ediliyor (XSS ve çerez sızıntısını azaltmak için)?
8. **Boyut, piksel ve oran sınırları var mı** (DoS ve decompression bomb koruması)?
9. **Uygulama süreci least privilege ile mi** çalışıyor; yükleme dizinine yazma dışında yetkisi kısıtlı mı?
10. **Yükleme uçları kimlik doğrulama/yetkilendirmeyle mi** korunuyor ve loglanıyor mu?

Bu listenin özündeki felsefe şudur: **Tek bir kontrolün başarısız olacağını varsay ve o başarısızlığın felakete dönüşmesini bir sonraki katmanın engellemesini sağla.** Uzantı kontrolü aşılsa bile dosya çalıştırılamayan bir yerde durur; çalıştırma engellemesi bir yapılandırma hatasıyla delinse bile dosya web kökünün dışındadır; hepsi delinse bile yeniden kodlama payload'ı yok etmiştir. Dosya yükleme güvenliği, işte bu üst üste binen bağımsız savunmaların toplamıdır — tek bir "sihirli kontrol" değil.
