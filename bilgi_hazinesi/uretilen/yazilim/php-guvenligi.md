# PHP Güvenliği: Type Juggling, Object Injection/Unserialize, LFI Zincirleri, Wrapper'lar

## Neden Bu Konu Kapsanmalı

PHP, popüler "modern dil" listelerinde nadiren anılsa da, WordPress, Laravel, Symfony, Drupal ve sayısız özel kurumsal uygulama üzerinden web'in çok büyük bir kısmını hâlâ çalıştırıyor. Bu ölçek, PHP'ye özgü zafiyet sınıflarını -diğer dillerde doğrudan karşılığı olmayan veya çok farklı şekilde ortaya çıkan hata kalıplarını- profesyonel bir güvenlik korpusunda zorunlu kılıyor. Type juggling (tip zorlama), `unserialize()` tabanlı nesne enjeksiyonu, Local File Inclusion (LFI) zincirleri ve PHP stream wrapper'larının (`phar://`, `php://filter` gibi) istismarı, dilin tasarım kararlarından (gevşek tip sistemi, otomatik nesne serileştirme/deserileştirme, esnek dosya dahil etme mekanizması) doğrudan kaynaklanır. Bu makale, bu mekanizmaları savunmacı bir bakış açısıyla -nasıl çalıştıklarını, neden var olduklarını, nasıl tespit edilip önlendiklerini- anlatır.

## Type Juggling (Tip Zorlama)

### Tanım ve Kök Neden

PHP zayıf ve dinamik tipli bir dildir. `==` (gevşek eşitlik) operatörü, karşılaştırma yapmadan önce operandları ortak bir tipe **dönüştürür**. Bu dönüştürme kuralları bazı sezgisel olmayan sonuçlar doğurur. Kök neden şudur: dil, geliştirici kolaylığı için otomatik tip dönüşümü sağlar, ancak bu dönüşüm kuralları güvenlik açısından "en az şaşırtıcı" davranışı garanti etmez.

Klasik örnek: bir dizeyle sayısal görünümlü bir dizenin `==` ile karşılaştırılması. PHP'nin eski sürümlerinde (PHP 8 öncesi), sayısal olmayan bir dize ile sayısal bir dizenin karşılaştırılmasında ilginç davranışlar vardı; özellikle "magic hashes" olarak bilinen olgu, bazı dizelerin bilimsel gösterim (`0e123...` gibi "0e" ile başlayıp devamı sadece rakamlardan oluşan) hash çıktılarının, `==` ile karşılaştırıldığında sayısal olarak `0` gibi yorumlanıp birbirine eşit sayılması sorunuydu. Bir kimlik doğrulama kontrolü:

```php
if ($hash_from_db == $hash_from_user) {
    // giriş başarılı
}
```

şeklinde yazıldıysa ve her iki taraf da "0e" ile başlayan farklı magic-hash değerlerine sahipse, aslında karakter olarak eşit olmayan iki hash `==` karşısında eşit sayılabiliyordu. Bu, MD5/SHA1 gibi hash fonksiyonlarının çıktısının bazı girdiler için bu deseni üretebilmesinden kaynaklanıyordu.

PHP 8 ile birlikte sayı-dize karşılaştırma kuralları önemli ölçüde değiştirildi (dize sayısal değilse artık sayıya değil, sayı dizeye çevrilerek karşılaştırılıyor), bu da klasik "magic hash" sınıfının büyük kısmını ortadan kaldırdı. Ancak burada önemli olan **kesin sürüm davranışını ezberlemek değil, ilkeyi kavramaktır**: `==` bir tip dönüştürme operatörüdür, güvenlik açısından hassas karşılaştırmalarda (parola hash'i, token, imza, MAC değeri) asla güvenilmemelidir.

### Diğer Type Juggling Tuzakları

- `in_array()` ve `switch` gibi yapılar, varsayılan olarak gevşek karşılaştırma kullanır; bir dizi içinde arama yaparken beklenmedik eşleşmeler oluşabilir (örn. `in_array("abc", $array)` bazı sayısal elemanlarla eşleşebilir gevşek modda).
- Boolean dönüşümü: boş dize, `"0"` dizesi, `0`, `null`, boş dizi hepsi "falsy" kabul edilir. Bir API anahtarının veya kullanıcı girdisinin "boş mu değil mi" kontrolü `empty()` ile yapılırsa, `"0"` gibi meşru bir değer yanlışlıkla boş sayılabilir.
- `strcmp()` gibi bazı fonksiyonlar tarihsel olarak tip uyuşmazlığında `NULL` dönebiliyordu, bu da `if (strcmp($a, $b) == 0)` gibi bir kontrolde tip zorlama nedeniyle beklenmedik eşleşmeye yol açabiliyordu (`NULL == 0` gevşek karşılaştırmada `true`'dur).

### Savunma ve En İyi Pratikler

1. **Katı karşılaştırma kullanın**: Güvenlikle ilgili her karşılaştırmada `===` ve `!==` kullanın. `==` sadece tip dönüşümünün kasıtlı ve zararsız olduğu yerlerde tercih edilmelidir.
2. **Sabit zamanlı karşılaştırma**: Hash/token/imza karşılaştırmalarında `===` bile yeterli değildir çünkü dize karşılaştırması genellikle erken çıkışlıdır (timing side-channel riski). Bunun yerine `hash_equals()` fonksiyonu kullanılmalı; bu fonksiyon hem tip zorlamasından kaçınır hem de sabit zamanlı çalışacak şekilde tasarlanmıştır.
3. **Açık tip dönüştürme**: Girdiyi kullanmadan önce beklenen tipe açıkça dönüştürün (`(int)`, `intval()` gibi) ve ardından katı karşılaştırma yapın.
4. **`in_array()` ve `array_search()`** çağrılarında üçüncü parametre olan `strict` bayrağını `true` geçirin.
5. Statik analiz araçları (PHPStan, Psalm) ve linter kuralları, `==` kullanımını hassas bölgelerde işaretleyecek şekilde yapılandırılabilir.

## Object Injection / Unserialize İstismarı

### Tanım

PHP'de `serialize()` bir nesneyi (veya diziyi/skaler değeri) bayt dizisine dönüştürür; `unserialize()` bu diziyi tekrar bir PHP değerine (nesne dahil) dönüştürür. Sorun şudur: `unserialize()`'a **güvenilmeyen, kullanıcı kontrollü veri** verilirse, saldırgan serileştirilmiş veri içinde istediği sınıfın bir örneğini talep edebilir. Uygulama o sınıfı zaten tanımlamışsa (autoload veya include edilmiş herhangi bir yerde), PHP bu sınıfın bir nesnesini kullanıcının belirlediği özellik değerleriyle oluşturur.

### Kök Neden / Çalışma Mantığı

Buradaki gerçek tehlike, nesnenin "oluşturulması" değil, PHP'nin bazı **sihirli metotları (magic methods)** nesnenin yaşam döngüsünün belirli noktalarında **otomatik olarak** çağırmasıdır:

- `__wakeup()`: `unserialize()` çağrıldığı anda, nesne yeniden oluşturulduktan hemen sonra otomatik çalışır.
- `__destruct()`: nesne kapsam dışına çıktığında veya script sonunda çöp toplanırken otomatik çalışır.
- `__toString()`, `__call()`, `__get()`, `__set()` gibi diğerleri de zincirleme (chaining) yoluyla tetiklenebilir.

Saldırganın amacı, uygulamanın zaten içerdiği sınıflar arasında, bu sihirli metotları zincirleyerek zararlı bir yan etkiye (dosya silme, dosya yazma, SQL sorgusu çalıştırma, hatta kod çalıştırma) ulaşan bir dizi bulmaktır. Buna güvenlik literatüründe **POP chain (Property-Oriented Programming chain)** denir. Saldırgan kendi kodunu enjekte etmez; mevcut kod tabanındaki sınıfları, tasarlanmamış bir sırayla birbirine zincirleyerek "silahlandırır". Bu nedenle object injection, "kodun kendisi zararsız görünse de, kompozisyonu zararlı olabilir" ilkesinin klasik bir örneğidir.

Tipik bir zincir şöyle işler: saldırgan `unserialize()`'a özel hazırlanmış bir payload verir → nesne A oluşturulur, `__wakeup()` tetiklenir → A'nın bir özelliği aslında nesne B'dir, B'nin `__toString()`'i tetiklenir → B, dosya sistemine yazan bir sınıfı çağırır → sonuçta rastgele dosya yazma veya silme elde edilir. Zincirin uzunluğu ve karmaşıklığı framework'e göre değişir; bu yüzden bilinen framework'lerde (özellikle eklenti/paket ekosistemi zengin olan CMS'lerde) "gadget chain" araştırması ayrı bir güvenlik alt dalıdır.

### PHAR Deserileştirme Saldırıları

`phar://` wrapper'ı ile birlikte gelen özellikle sinsi bir varyant vardır: PHAR arşiv dosyalarının başında bir **meta-veri bölümü** bulunur ve bu meta-veri, dosya `unserialize()` ile açıkça işlenmese bile, dosya sistemi fonksiyonları (`file_exists()`, `is_file()`, `filemtime()`, `getimagesize()` gibi) `phar://` öneki üzerinden bu dosyaya dokunduğunda **PHP tarafından otomatik olarak deserileştirilir**. Yani "unserialize çağrısı hiçbir yerde yok" görünse de, saldırgan yükleyebildiği herhangi bir dosyayı `.phar` uzantısı olmasa bile PHAR formatında hazırlayıp, uygulamanın bu dosyaya `phar://` şeması üzerinden herhangi bir dosya işlemi yapmasını sağlayarak nesne enjeksiyonunu tetikleyebilir. Bu, "sadece unserialize() çağrılarını arıyorum" şeklindeki dar kapsamlı bir kod incelemesinin neden yetersiz kaldığının iyi bir örneğidir; dosya yolu işleyen her fonksiyon potansiyel bir deserileştirme giriş noktası olabilir.

### Savunma ve En İyi Pratikler

1. **Kullanıcı girdisini asla `unserialize()` ile işlemeyin.** Veri taşıma/depolama formatı olarak `json_encode()`/`json_decode()` kullanın; JSON, nesne örnekleme yapmaz, sadece veri yapılarını temsil eder.
2. Zorunlu olarak `unserialize()` kullanılması gereken yerlerde (eski kod, üçüncü parti entegrasyon), PHP'nin sağladığı `allowed_classes` seçeneğini kullanın: `unserialize($data, ['allowed_classes' => false])` hiçbir nesne örneklemesine izin vermez, sadece skaler ve dizi döner. Gerekiyorsa `allowed_classes` içine yalnızca güvenli, yan etkisiz sınıfların bir beyaz listesi verilebilir.
3. `phar://` girdisini kullanıcı kontrollü dosya yolu alan hiçbir fonksiyona (özellikle dosya var mı/boyutu ne kadar gibi "zararsız görünen" kontrollerde) ulaştırmayın. Dosya yolu şemasını (`phar://`, `zip://`, `data://` vb.) beyaz listeye almadan asla kabul etmeyin; gerekirse `parse_url()` ile şema kısmını çıkarıp yalnızca beklenen (`file://` veya şemasız) girdileri kabul edin.
4. Yüklenen dosyaların içeriğini (magic byte / dosya imzası) doğrulayın; sadece uzantıya güvenmeyin. Bir `.jpg` uzantılı dosya PHAR formatında hazırlanmış olabilir.
5. `__wakeup()`, `__destruct()`, `__toString()` gibi sihirli metotları olan sınıflarda, bu metotların içinde dış kaynaklara erişim (dosya, veritabanı, ağ) varsa, bu metotların hiçbir güvenilmeyen girdiden tetiklenemeyeceğinden emin olun; mümkünse bu metotlarda savunmacı tip kontrolü (`instanceof`, özellik tipleri) yapın.
6. Composer bağımlılıklarını güncel tutun; bilinen gadget chain'ler genellikle popüler kütüphanelerin (loglama, HTTP client, ORM) belirli sürümlerinde bulunur ve güncellemelerle kapatılır.

## Local File Inclusion (LFI) Zincirleri

### Tanım

LFI, uygulamanın `include()`, `require()`, `include_once()`, `require_once()` gibi dosya dahil etme fonksiyonlarına, sunucu üzerindeki dosya yolunu **kısmen veya tamamen kullanıcı kontrolüne** bırakarak besliyor olmasıdır. En basit hâli:

```php
$page = $_GET['page'];
include($page . '.php');
```

Saldırgan `page` parametresini `../../etc/passwd%00` gibi (null byte injection, artık modern PHP sürümlerinde kapatılmış eski bir teknik) veya dizin gezintisi (`../../../`) ile manipüle ederek beklenmeyen dosyaları dahil etmeye çalışır.

### Neden "Zincir" Denir

Saf LFI genellikle tek başına sadece **bilgi ifşası** (dosya içeriğini okuma) sağlar. Ancak gerçek etki -uzaktan kod çalıştırma (RCE)- çoğunlukla LFI'nin başka bir zafiyetle **zincirlenmesiyle** ortaya çıkar. Kök neden: `include()` dahil ettiği dosyanın içeriğini, dosya uzantısından bağımsız olarak PHP kodu gibi yorumlar. Yani "kod" ile "veri" arasındaki sınır, dosya sistemi düzeyinde değil, `include()`'un davranışıyla belirlenir. Eğer saldırgan sunucuya *herhangi bir şekilde* kendi kontrolündeki metni yazdırabiliyorsa (log dosyası, upload edilen resim, oturum dosyası, e-posta başlığı, ortam değişkeni), bunu LFI ile birleştirerek kod çalıştırmaya dönüştürebilir. Yaygın zincirleme teknikleri:

- **Log Poisoning**: Web sunucusu veya PHP-FPM erişim/hata loglarına, User-Agent veya benzeri bir HTTP başlığı aracılığıyla `<?php ... ?>` içeren bir dize yazdırılır; ardından LFI ile log dosyası dahil edilerek kod çalıştırılır.
- **Session Poisoning**: Oturum verisine (session dosyasına) saldırgan kontrollü bir alan (örn. kullanıcı adı) PHP kodu içerecek şekilde yazılır; session dosyasının disk üzerindeki konumu tahmin edilebilirse (`/tmp/sess_<id>` gibi tipik PHP session dosya adlandırması), LFI ile bu dosya dahil edilir.
- **Dosya Yükleme + LFI**: Uygulama resim yüklemeye izin veriyorsa ve dosya içeriği doğrulanmıyorsa, saldırgan PHP kodu içeren ama `.jpg` uzantılı bir dosya yükler, sonra LFI ile bu dosyayı `include()` ettirir (uzantı `include()` için önemsizdir, sadece dosya yolu önemlidir).
- **`phar://` ile RCE'siz Deserileştirme**: LFI'nin `phar://` şemasıyla birleşmesi durumunda, yukarıda anlatılan PHAR deserileştirme zinciri devreye girer ve doğrudan kod çalıştırmaya gerek kalmadan nesne enjeksiyonu tetiklenebilir.

Bu örüntülerin ortak paydası şudur: LFI tek başına "okuma" zafiyetidir, ama sunucu üzerinde saldırgan-kontrollü içerik barındıran **herhangi bir yazma birincil ilkeli (write primitive)** ile birleştiğinde "yazma + dahil etme = kod çalıştırma" zincirine dönüşür. Savunmacı bir mühendis için asıl ders, LFI'yi izole bir bulgu olarak değil, "bu uygulamada saldırgan hangi dosyalara kısmen de olsa içerik yazdırabilir" sorusuyla birlikte değerlendirmektir.

### Remote File Inclusion (RFI) Farkı

LFI'nin kuzeni RFI'dır: `include()`'a doğrudan uzak bir URL verilebiliyorsa (`allow_url_include` etkinse), saldırgan kendi sunucusundan doğrudan PHP kodu dahil ettirebilir; bu, zincirlemeye gerek kalmadan doğrudan RCE'dir. Modern PHP kurulumlarında `allow_url_include` varsayılan olarak kapalıdır, ancak eski/yanlış yapılandırılmış sunucularda hâlâ karşılaşılabilir.

### Savunma ve En İyi Pratikler

1. **Kullanıcı girdisini asla doğrudan dosya yolu olarak `include`/`require`'a vermeyin.** Sayfa/şablon seçimi gerekiyorsa, kullanıcı girdisini bir **beyaz liste** (izin verilen anahtar → sabit dosya yolu eşlemesi, dizi/switch üzerinden) ile eşleyin; girdi doğrudan yol bileşenine akmasın.
2. Dosya yolu birleştirme zorunluysa, `basename()` ile dizin gezintisi bileşenlerini temizleyin ve ardından oluşan mutlak yolun beklenen kök dizin altında kaldığını (`realpath()` ile çözüp beklenen prefix ile karşılaştırarak) doğrulayın.
3. `allow_url_include` ve mümkünse `allow_url_fopen` üretim ortamında kapatılmalıdır.
4. `open_basedir` kısıtlamasını yapılandırarak PHP'nin dosya sistemi erişimini belirli dizinlerle sınırlayın; bu, LFI'nin `/etc/passwd` gibi dosyalara erişimini sınırlamasa da (open_basedir dosya okuma fonksiyonlarını kısıtlar ama bazı stream wrapper senaryolarında atlatılabilir), savunma katmanlarından biridir.
5. Log dosyalarına yazılan kullanıcı kontrollü verileri (User-Agent, Referer vb.) mümkünse encode edin veya loglama formatında PHP tag'lerinin yorumlanmasını engelleyecek şekilde işleyin; log dosyalarının web kökü dışında, PHP olarak yorumlanamayacak bir dizinde tutulmasını sağlayın.
6. Dosya yükleme özelliklerinde: uzantı beyaz listesi + içerik/magic-byte doğrulaması + yüklenen dosyaların PHP çalıştırma yetkisi olmayan bir dizine (veya web sunucusu düzeyinde `.php` çalıştırmayı engelleyen bir dizine) konması.

## PHP Stream Wrapper'ları: Genel Saldırı Yüzeyi

`fopen()`, `file_get_contents()`, `include()`, `copy()` gibi dosya işlemi yapan tüm fonksiyonlar aslında PHP'nin **stream wrapper** soyutlaması üzerinden çalışır. `php://`, `phar://`, `zip://`, `data://`, `expect://`, `ftp://`, `http://` gibi şemalar, "dosya yolu" gibi görünen bir string'in aslında çok farklı davranışlar tetikleyebileceği anlamına gelir:

- `php://filter/convert.base64-encode/resource=dosya.php`: bir dosyayı çalıştırmadan, base64 kodlanmış hâlde okumaya yarar -- bazı LFI senaryolarında `.php` dosyasının kaynak kodunu (çalıştırmadan) sızdırmak için kullanılır, çünkü `include()` normalde `.php` dosyasını çalıştırır ama filter zinciriyle "dosyayı oku, kodu çalıştırma" davranışı elde edilebilir.
- `php://input`: HTTP istek gövdesini bir stream olarak sunar; LFI ile birleşirse saldırgan doğrudan istek gövdesine yazdığı PHP kodunu dahil ettirebilir (RFI olmadan, ama `allow_url_include` gerektirmeden).
- `data://text/plain;base64,...`: doğrudan istek içinde base64 kodlanmış veri/kod taşır; `allow_url_fopen` açık olduğunda LFI ile birleşerek kod çalıştırmaya izin verebilir.
- `phar://`: yukarıda anlatıldığı gibi deserileştirme tetikleyicisi.

Bu wrapper zenginliği PHP'nin bir gücüdür (aynı fonksiyonla dosya, ağ, bellek, arşiv erişimi) ama girdi doğrulaması yapılmadan kullanıcı verisine açıldığında saldırı yüzeyini ciddi biçimde genişletir. Savunmacı ilke: bir fonksiyon "dosya yolu" bekliyor görünse de, aslında **şema + yol** ikilisi bekler; şema kısmı kontrol edilmezse fonksiyonun gerçek davranışı tahmin edilemez hâle gelir.

## Genel Tespit Yaklaşımları

- **Statik analiz**: `unserialize(`, `include(`/`require(` çağrılarının kaynağını (data-flow) kullanıcı girdisine kadar geriye izleyen SAST araçları (Psalm taint analysis, PHPStan + eklentiler, Semgrep kuralları) bu üç zafiyet sınıfını da büyük ölçüde yakalayabilir.
- **Loglama ve WAF**: `phar://`, `php://filter`, `data://`, `expect://` gibi şema isimlerinin HTTP parametrelerinde görünmesi genellikle meşru kullanım senaryosu değildir; bir WAF kuralı veya günlük analizi bu desenleri erken uyarı olarak işaretleyebilir.
- **Dinamik test**: Fuzzing ile dosya yolu parametrelerine dizin gezintisi ve şema önekleri enjekte ederek yanıt farklarını (hata mesajı, zaman gecikmesi, içerik farkı) gözlemlemek klasik bir tespit yöntemidir.
- **Bağımlılık taraması**: Composer üzerinden gelen bilinen "gadget chain" içeren kütüphane sürümlerini tespit etmek için `composer audit` ve benzeri güvenlik açığı veritabanı taramaları düzenli çalıştırılmalıdır.

## Sonuç

PHP'ye özgü bu zafiyet sınıflarının ortak paydası, dilin esnekliğinin (gevşek tipler, otomatik serileştirme/deserileştirme, zengin stream soyutlaması) güvenlik varsayımlarıyla çatışmasıdır. Savunma stratejisi her zaman aynı üç ilkeye dayanır: **girdiyi asla örtük güvenle işlemdegen**, kritik karşılaştırmalarda ve veri formatlarında **açık ve katı davranışı tercih et** (`===`, `hash_equals()`, JSON), ve dosya/nesne işleyen her fonksiyonu "bu girdi ne kadar kullanıcı kontrolünde, hangi şema/tip üzerinden yorumlanıyor" sorusuyla değerlendir. Bu üç zafiyet sınıfı ayrı ayrı görünse de kökeninde aynı dersi paylaşır: dilin sunduğu üstü kapalı kolaylıklar, güvenlik açısından açık ve kısıtlayıcı hâle getirilmediği sürece saldırı yüzeyine dönüşür.
