# Parola Saklama ve Hashleme

## Tanım

Parola saklama, bir sistemin kullanıcıların parolalarını kimlik doğrulama (authentication) için nasıl depoladığı ve daha sonra doğruladığı problemidir. Modern güvenlikte temel kural açıktır: parolalar hiçbir zaman düz metin (plaintext) olarak, hatta geri döndürülebilir bir şifreleme (reversible encryption) ile de saklanmaz. Bunun yerine, parolanın tek yönlü (one-way) bir dönüşümden geçirilmiş özeti, yani bir password hash saklanır. Kullanıcı giriş yaptığında, girdiği parola aynı dönüşümden geçirilir ve saklanan değerle karşılaştırılır. Eğer değerler eşleşiyorsa parola doğrudur.

Buradaki kritik nokta şudur: "hash" kelimesi genel bir kavramdır ama parola saklama için kullanılan hash, genel amaçlı bir hash (SHA-256, SHA-3 gibi) değildir. Parolalar için özel olarak tasarlanmış, kasıtlı olarak yavaş ve maliyetli olan **password hashing** fonksiyonları kullanılır: **Argon2id**, **bcrypt**, **scrypt** ve daha eski ama hâlâ standart kabul edilen **PBKDF2**. Bu makale, bu fonksiyonların neden var olduğunu, SHA-256 gibi hızlı hash'lerin neden yanlış bir tercih olduğunu, salt ve pepper kavramlarını, saldırı (istismar) mantığını ve savunma pratiklerini derinlemesine ele alır.

## Kök Neden: Parolalar Neden Özel Muamele Gerektirir

Parola saklamanın zorluğu, tehdit modelinden (threat model) doğar. Doğru varsayım şudur: **veri tabanı er ya da geç sızacaktır.** SQL injection, yanlış yapılandırılmış bir yedek (backup), içeriden bir tehdit (insider threat), çalınan bir disk imajı veya bir bulut deposunun (bucket) herkese açık kalması... Sızıntı olasılığı yeterince uzun bir zaman diliminde neredeyse kesindir. Dolayısıyla iyi bir parola saklama şeması, "veri tabanı çalınmayacak" varsayımına değil, "veri tabanı çalınsa bile parolalar mümkün olduğunca değersiz olmalı" varsayımına dayanır.

Bir saldırgan `password_hash` sütununu ele geçirdiğinde amacı, bu özetlerden gerçek parolaları geri elde etmektir. Hash fonksiyonu tek yönlü olduğu için özeti doğrudan "ters çeviremez"; bunun yerine **tahmin edip dener** (guess-and-check). Yani bir aday parola alır, onu hash'ler ve sonucu çalınan özetle karşılaştırır. Eşleşirse parolayı bulmuş olur. Bu yaklaşımın adı **offline brute-force** veya sözlük saldırısıdır (dictionary attack). "Offline" olması kritiktir: saldırgan artık sizin sunucunuza, rate limiting'inize veya hesap kilitleme (account lockout) mekanizmanıza bağlı değildir. Kendi donanımında, istediği hızda, saniyede milyarlarca tahmin yapabilir.

İşte kök neden burada yatar: **Eğer hash fonksiyonu hızlıysa, saldırganın tahmin-dene döngüsü de hızlıdır.** Güvenliğin tamamı, saldırganın bir tahmini deneme maliyetini kabul edilemez derecede yüksek yapmaya indirgenir. Password hashing fonksiyonlarının tüm varlık nedeni budur: onları **kasıtlı olarak yavaş ve pahalı** yaparak, savunmacı için tek bir doğrulama işlemi ihmal edilebilir bir maliyette (örneğin 250 ms) kalırken, saldırgan için milyarlarca tahmin astronomik bir maliyete dönüşür.

## Neden SHA-256 (ve Genel Amaçlı Hash'ler) Yanlış

SHA-256, SHA-512, SHA-3, MD5 ve benzeri fonksiyonlar mühendislik olarak **hız için** tasarlanmıştır. Bir dosyanın bütünlüğünü (integrity) doğrulamak, dijital imza için bir mesaj özeti üretmek veya blockchain'de bir bloğu doğrulamak istediğinizde, saniyede mümkün olduğunca çok hash hesaplamak istersiniz. Bu bağlamlarda hız bir erdemdir. Ancak parola saklamada tam olarak bu hız, ölümcül bir zafiyettir.

Somut bir karşılaştırma yapalım. Modern bir GPU (grafik işlemcisi), SHA-256 için saniyede **milyarlarca** hash hesaplayabilir. Sıradan tüketici donanımıyla kurulan bir kümede (cluster), rakamlar on milyarlar mertebesine çıkar. Bu, şu anlama gelir: 8 karakterlik, yaygın karakter kümesinden oluşan bir parolanın tüm olası kombinasyonları, SHA-256 kullanıldığında pratik bir sürede (saatler, bazen dakikalar) tümüyle denenebilir. Buna karşın Argon2id veya uygun parametrelerle yapılandırılmış bcrypt, aynı donanımda saniyede yalnızca birkaç bin hash hesaplayabilir. Aradaki fark **milyonlarca kattır**. Saldırganın işini milyonlarca kat pahalılaştırmak, savunmanın özüdür.

SHA-256'nın yanlışlığı yalnızca hızdan da ibaret değildir:

- **Tek başına salt kullanmaz.** Ham SHA-256 aynı parolayı her zaman aynı özete dönüştürür. Bu, birebir sıralanmış saldırıları (aşağıda anlatılan rainbow table) mümkün kılar.
- **Ayarlanabilir bir maliyet (cost) parametresi yoktur.** Donanım her yıl hızlanır. bcrypt/scrypt/Argon2 fonksiyonlarında bir "iş faktörü" (work factor) vardır ve bunu yıllar geçtikçe artırarak fonksiyonu donanımla birlikte yavaşlatmaya devam edebilirsiniz. SHA-256'da böyle bir kaldıraç yoktur.
- **Bellek-sertliği (memory-hardness) yoktur.** GPU'lar ve ASIC'ler (özel amaçlı çipler), az bellek gerektiren, saf hesaplama ağırlıklı işlemleri paralelleştirmede olağanüstü iyidir. SHA-256 tam olarak böyle bir işlemdir, bu yüzden GPU ile korkunç derecede hızlanır.

Sık yapılan bir hata, "SHA-256'yı çok kez döngüye sokarsam (örneğin 100.000 kez) yavaşlatmış olurum" diye düşünmektir. Bu fikrin doğru bir yönü vardır ve aslında PBKDF2'nin temel mantığı budur. Ancak bunu elle, dikkatsizce uygulamak tehlikelidir; üstelik SHA tabanlı iterasyon hâlâ **GPU/ASIC-dostu** kalır, çünkü bellek-sertliği sağlamaz. Yani doğru çözüm "SHA'yı elle döngüye sokmak" değil, bu işi doğru yapan, denenmiş ve standartlaşmış bir password hashing fonksiyonu kullanmaktır.

## Salt: Aynı Parolaların Aynı Görünmesini Engellemek

**Salt**, her parola için üretilen, gizli olması gerekmeyen ama benzersiz (unique) ve rastgele (random) olması gereken bir veridir. Parola hash'lenmeden önce parolaya eklenir (birleştirilir), böylece iki farklı kullanıcı aynı parolayı seçse bile veri tabanında saklanan özetleri tamamen farklı olur.

Salt'ın çözdüğü kök problem şudur. Salt olmadan, "123456" parolasının SHA-256 özeti evrende her zaman aynı sabit değerdir. Bu, saldırganlara devasa bir avantaj verir:

- **Rainbow table saldırısı:** Saldırgan, milyarlarca yaygın parolanın özetini önceden hesaplayıp (precompute) devasa bir arama tablosunda saklar. Çalınan bir özeti bu tabloda arar ve karşılığındaki parolayı anında bulur. Hesaplama işi bir kereye mahsus yapılmış, sonra defalarca kullanılmıştır.
- **Toplu kırma:** Salt yoksa, saldırgan bir tahmini hash'ler ve bunu veri tabanındaki **tüm** kullanıcıların özetleriyle aynı anda karşılaştırabilir. Yani tek bir hesaplama tüm kullanıcı tabanına karşı işler.

Salt bu iki avantajı da yok eder. Her kullanıcının benzersiz bir salt'ı olduğunda:

- Önceden hesaplanmış tablolar işe yaramaz, çünkü tabloların her olası salt için ayrı ayrı hesaplanması gerekir ki bu pratikte imkânsızdır.
- Saldırgan her kullanıcıyı **ayrı ayrı** hedeflemek zorunda kalır. Bir tahmini bir kullanıcı için hash'lemek, başka kullanıcılar için işe yaramaz.

Salt'ın gizli olması gerekmez; genellikle özetin yanında, aynı satırda saklanır. Zaten Argon2id/bcrypt/scrypt fonksiyonlarının ürettiği çıktı dizesi, salt'ı ve maliyet parametrelerini kendi içinde kodlanmış olarak taşır; bunları elle yönetmenize gerek kalmaz. Kritik gereksinimler salt'ın **kriptografik olarak güvenli bir rastgele kaynaktan** (CSPRNG) üretilmesi ve her parola için benzersiz olmasıdır. Sabit bir salt kullanmak (herkes için aynı), salt kullanmamakla neredeyse eşdeğerdir; çünkü toplu kırma yeniden mümkün hâle gelir.

## Pepper: Sırrı Veri Tabanının Dışında Tutmak

**Pepper**, salt'a benzer ama farklı bir amaca hizmet eden ek bir savunma katmanıdır. Salt her kullanıcı için benzersiz ve genellikle veri tabanında açıkça saklanırken, pepper tüm parolalar için **ortak** olan ve kritik olarak **veri tabanının dışında** tutulan gizli bir değerdir. Pepper genellikle uygulama yapılandırmasında, bir ortam değişkeninde (environment variable), bir secrets manager'da ya da ideal olarak bir donanım güvenlik modülünde (HSM) saklanır.

Pepper'ın çözdüğü senaryo şudur: saldırgan **yalnızca veri tabanını** ele geçirir ama uygulama sunucusunun sırlarına erişemez. Salt'lar veri tabanında olduğu için saldırgan onlara sahiptir, ama pepper'a sahip değildir. Pepper bilinmeden yapılan hiçbir tahmin doğru sonucu üretmez; yani saldırgan salt bilinse bile parolaları kıramaz. Böylece pepper, "sadece veri tabanı sızdı" senaryosunu, "hiçbir şey kıramıyorum" senaryosuna dönüştürebilir.

Pepper'ı uygulamanın makul yolları vardır ve bazı yaygın hataları içerir:

- **Doğru yaklaşım:** Pepper'ı, parola hash'inin sonucuna anahtarlı bir işlem olarak, örneğin bir HMAC ile uygulamak (`HMAC(pepper, sifre)` gibi bir ön işlemden geçirip ardından password hashing fonksiyonuna vermek) temiz bir yöntemdir. Böyle bir HMAC katmanı, pepper'ı ayrı bir anahtar gibi ele alır ve gerektiğinde döndürülmesini (rotation) kolaylaştırabilecek bir yapı sunar.
- **Sınırları:** Pepper, uygulama sunucusu da tümüyle ele geçirildiğinde (remote code execution ile pepper'ın belleğe okunması gibi) hiçbir koruma sağlamaz. Yani pepper, salt'ın yerine geçmez; onun **üstüne** eklenen, tehdit modelini "sadece DB sızması" senaryosuna karşı güçlendiren bir katmandır.
- **Anahtar rotasyonu zorluğu:** Pepper'ı değiştirmek, eski pepper ile üretilmiş tüm hash'leri geçersiz kılar. Bu yüzden pepper'ı sürümlemek (versiyon etiketi tutmak) ya da kullanıcı bir sonraki girişinde yeniden hash'lemek gibi bir geçiş stratejisi gerekir.

Özetle: **salt zorunludur, pepper ise iyi bir ek savunmadır (defense in depth).** Pepper'ı, salt'ı ve yavaş hash fonksiyonunu doğru kullanmadan uygulamak yanlış öncelik sıralaması olur.

## Argon2id, bcrypt, scrypt: Hangisi ve Neden

Bu üç fonksiyon da password hashing için tasarlanmıştır; hepsi yavaştır ve ayarlanabilir maliyet parametrelerine sahiptir. Aralarındaki temel fark, saldırgan donanımına (özellikle GPU ve ASIC) karşı ne kadar dirençli olduklarıdır.

### bcrypt

bcrypt, uzun yıllardır sahada olan, iyi test edilmiş ve güvenilir bir seçimdir. Blowfish şifresinin anahtar çizelgeleme (key schedule) mantığından türetilmiştir ve bir **cost / work factor** parametresi alır. Bu parametre üstel (exponential) olarak çalışır: değeri bir artırdığınızda gereken iş kabaca iki katına çıkar. Böylece donanım hızlandıkça cost değerini artırarak fonksiyonu yavaş tutmaya devam edebilirsiniz.

bcrypt'in modest bir miktar bellek kullanması, onu saf SHA iterasyonlarına göre GPU'ya karşı daha dirençli yapar. Ancak iki önemli sınırlaması vardır. Birincisi, bellek kullanımı sabittir ve düşüktür; yani Argon2/scrypt kadar güçlü bir bellek-sertliği sunmaz. İkincisi ve pratikte daha önemlisi, bcrypt'in bir **girdi uzunluğu sınırı** vardır; belirli bir bayt sayısının ötesindeki karakterleri dikkate almaz. Bu sınır, uzun parolalar veya parola yerine geçen uzun ifadeler (passphrase) kullanıldığında bir zafiyete yol açabilir; ayrıca içinde null bayt geçen girdilerde bazı uygulamalarda beklenmedik davranışlar görülmüştür. Bu yüzden bcrypt kullanılıyorsa, parolanın önce bir HMAC veya SHA ile sabit uzunlukta bir değere dönüştürülüp (base64 kodlanarak) bcrypt'e verilmesi yaygın ve makul bir çözümdür; bu hem uzunluk sınırını hem de null bayt sorununu aşar.

### scrypt

scrypt, tasarım hedefi olarak **bellek-sertliği** (memory-hardness) getirir. Fikir şudur: fonksiyon yalnızca çok işlem değil, aynı zamanda çok **bellek** gerektirsin. GPU'lar ve ASIC'ler çok sayıda hesaplama birimine sahiptir ama her birime bol miktarda hızlı bellek vermek pahalıdır. Bellek gereksinimini yükseltmek, saldırganın paralellik avantajını kırar, çünkü her paralel iş kolu için ayrı bellek gerekir. scrypt üç parametre alır: bir maliyet/iterasyon faktörü, bir blok boyutu (bellek kullanımını etkiler) ve bir paralellik faktörü. Doğru ayarlandığında GPU'ya karşı bcrypt'ten daha güçlüdür.

### Argon2id

Argon2, bir açık yarışma (Password Hashing Competition) sonucunda kazanan ve bugün **birinci tercih** olarak önerilen fonksiyondur. Üç varyantı vardır: Argon2d, Argon2i ve Argon2id. Bunlardan **Argon2id**, ötekilerin güçlü yanlarını birleştiren melez (hybrid) varyanttır ve genel parola saklama için tavsiye edilen odur. Argon2i, belleğe erişim desenini girdiden bağımsız yaparak yan kanal saldırılarına (side-channel, örneğin cache-timing) karşı direnç sağlar; Argon2d ise girdi-bağımlı erişimle GPU'ya karşı daha güçlü kırma direnci verir. Argon2id ikisini birleştirir: ilk geçişte side-channel direnci, sonraki geçişlerde GPU direnci.

Argon2'nin gücü, üç bağımsız parametreyi ayarlayabilmenizden gelir:

- **Bellek maliyeti (memory cost):** Ne kadar RAM kullanılacağı. Yüksek bellek, saldırganın bellek-sertliği duvarına çarpmasını sağlar.
- **Zaman maliyeti / iterasyon (time cost):** Bellek üzerinden kaç geçiş yapılacağı.
- **Paralellik (parallelism):** Kaç iş kolu kullanılacağı.

Bu üç eksen, fonksiyonu hem savunmacının donanımına göre kalibre etmenizi hem de gelecekteki donanım gelişmelerine karşı ayarlamanızı sağlar. Genel yaklaşım şudur: sunucunuzun karşılayabileceği bellek ve gecikme bütçesini belirleyin (örneğin doğrulama başına birkaç yüz milisaniye ve makul bir RAM tahsisi), sonra parametreleri bu bütçeyi dolduracak şekilde ayarlayın. Somut değerler donanıma ve trafiğe bağlı olduğu için tek bir "doğru sayı" yoktur; buradaki doğru yöntem, üretim donanımınızda ölçüm yapıp hedef gecikmeye göre kalibre etmektir. OWASP gibi kaynaklar dönemsel olarak güncellenen başlangıç parametreleri önerir; güncel değerleri oradan teyit etmek en sağlıklısıdır.

**Pratik öneri sırası:** Yeni bir sistemde önce **Argon2id**'yi tercih edin. Argon2id yoksa veya ortamınızda düzgün desteklenmiyorsa **scrypt** iyi bir ikinci seçenektir. **bcrypt**, olgun ve güvenilir olduğu için hâlâ tamamen kabul edilebilir; özellikle uzunluk sınırı doğru ele alındığında. FIPS uyumluluğu gibi düzenleyici zorunluluklar varsa **PBKDF2** (yeterince yüksek iterasyon sayısıyla) hâlâ standart olarak kullanılabilir, ancak bellek-sertliği olmadığı için modern seçeneklere göre GPU'ya daha az dirençlidir.

## Sömürü / İstismar Mantığı: Saldırgan Nasıl Düşünür

Savunmayı doğru kurmak için saldırının nasıl işlediğini somut olarak anlamak gerekir. Saldırgan çalınan hash'leri eline aldığında tipik akış şudur:

1. **Formatı tanıma.** Çalınan özetin başındaki etiket (`$argon2id$`, `$2b$` gibi bcrypt işareti veya ham onaltılık bir SHA dizesi) hangi algoritmanın kullanıldığını ele verir. Ham, salt'sız bir SHA-256 gördüğünde saldırgan sevinir, çünkü bu en kolay hedeftir.

2. **Düşük asılı meyveyi toplama.** Saldırgan işe en olası parolalarla başlar: sızmış parola listeleri (gerçek dünyadaki ihlallerden derlenmiş milyarlarca gerçek parola), yaygın kalıplar ("Sirket2024!" gibi), klavye desenleri ve sözlük kelimeleri. Gerçekte kullanıcıların büyük bir bölümü zayıf ve tahmin edilebilir parolalar seçtiği için, hızlı bir hash ile bu aşama bile kullanıcıların önemli bir yüzdesini kısa sürede ele geçirir.

3. **Kural tabanlı mutasyon.** Saldırı araçları, sözlük kelimelerine sistematik kurallar uygular: baş harfi büyütme, sona rakam/işaret ekleme, harf-rakam değişimleri (a→@, o→0) gibi. İnsanların parola "karmaşıklaştırma" alışkanlıkları öngörülebilir olduğu için bu kurallar çok etkilidir.

4. **Kaba kuvvet (brute-force).** Kalan, kırılmamış hash'ler için tüm karakter kombinasyonları denenir. Bunun fizibilitesi tamamen hash'in hızına bağlıdır. Hızlı hash'te kısa parolalar tümüyle taranabilir; yavaş, bellek-sert bir hash'te aynı tarama ekonomik olarak imkânsız hâle gelir.

Bu akıştan çıkan savunma dersi nettir: yavaş hash, salt ve pepper her adımı pahalılaştırır. Salt, 1. ve 2. adımdaki hazır tabloları ve toplu saldırıyı öldürür. Yavaş hash, 2., 3. ve 4. adımdaki tahmin hızını milyonlarca kat düşürür. Pepper, saldırganın gerekli tüm sırlara sahip olmadığı senaryoda tüm zinciri işlevsiz bırakır.

## Savunma: Doğru Şemayı Kurmak

Savunma tarafında, bir bütün olarak doğru şema şöyle özetlenebilir:

- Her parola için **CSPRNG ile üretilmiş benzersiz bir salt** kullanın. Modern kütüphanelerde bunu sizin yerinize fonksiyon yapar; salt zaten çıktı dizesine gömülüdür.
- **Argon2id** (veya scrypt/bcrypt) kullanın; parametreleri üretim donanımınızda ölçerek hedef gecikmeye göre kalibre edin. Doğrulama başına birkaç yüz milisaniyelik bir maliyet, kullanıcı deneyimini bozmadan saldırganı ciddi biçimde yavaşlatan makul bir denge noktasıdır.
- Mümkünse **pepper**'ı, veri tabanı dışında saklanan gizli bir anahtar olarak ekleyin (örneğin bir HMAC katmanıyla).
- **Sabit zamanlı karşılaştırma (constant-time comparison)** kullanın. Saklanan hash ile hesaplanan hash'i karşılaştırırken sıradan bir eşitlik kontrolü, ilk farklı bayt'ta erken döndüğü için ölçülebilir bir zaman sızıntısı (timing side-channel) yaratabilir. Password hashing kütüphaneleri genellikle doğrulamayı sabit zamanlı yapar; kendiniz bir karşılaştırma yazıyorsanız mutlaka sabit zamanlı fonksiyon kullanın.
- **Parametre yükseltmeye hazır olun.** Kullanıcı her başarılı girişte, saklanan hash'in parametreleri güncel hedefin altında kalmışsa parolayı yeni parametrelerle sessizce yeniden hash'leyin (kütüphaneler bunun için `needs rehash` benzeri bir kontrol sunar). Böylece donanım hızlandıkça sisteminiz de sertleşerek onu takip eder.
- **Katmanları birleştirin.** Parola hash'i son savunma hattıdır. Önünde rate limiting, hesap kilitleme, şüpheli giriş tespiti ve mümkünse **çok faktörlü kimlik doğrulama (MFA)** olmalıdır. MFA, parola tümüyle kırılsa bile hesabı korumaya devam eder ve pratikte parolayı tek başına yeterli olmaktan çıkarır.

## Yaygın Hatalar

- **Parola saklamak için SHA-256 / MD5 / düz SHA kullanmak.** En sık ve en ciddi hata. Hız burada zaaftır.
- **SHA'yı elle döngüye sokup "yavaşlattığını" sanmak.** İterasyon yardımcı olsa da bellek-sertliği yoktur ve elle uygulama hataya açıktır. Bunun yerine denenmiş bir password hashing fonksiyonu kullanın.
- **Salt kullanmamak veya herkes için aynı sabit salt'ı kullanmak.** Rainbow table ve toplu kırma saldırılarına kapıyı açar.
- **Salt'ı gizli sanıp pepper ile karıştırmak.** Salt gizli olmak zorunda değildir ve genellikle özetin yanında saklanır; benzersizliği önemlidir. Pepper ise gizlidir ve DB dışında durur. İkisi farklı amaçlara hizmet eder.
- **Parolayı geri döndürülebilir şekilde şifrelemek (encryption).** "Kullanıcı unutursa geri gönderelim" düşüncesiyle parolayı şifreleyip saklamak yanlıştır; anahtar sızarsa tüm parolalar açığa çıkar. Parola hash'lenmeli, asla geri döndürülebilir saklanmamalıdır.
- **Parolayı log'lamak veya hata mesajlarına, izleme (telemetry) verisine sızdırmak.** Düz metin parolanın log'lara düşmesi, tüm hashleme çabasını boşa çıkarır.
- **Karşılaştırmayı sabit zamanlı yapmamak.** Timing side-channel'a yol açabilir.
- **Aşırı kısıtlayıcı parola politikaları.** Zorunlu karmaşıklık kuralları ve sık zorunlu değişiklik, kullanıcıları öngörülebilir kalıplara iter (sona "1!" ekleme gibi) ve güvenliği düşürebilir. Güncel rehberler uzunluğu teşvik etmeyi, çok kısa/sık değişim zorunluluklarını kaldırmayı ve parolayı bilinen sızmış listeler karşısında kontrol etmeyi önerir.
- **bcrypt'in uzunluk sınırını göz ardı etmek.** Uzun parolalarda sessizce kesilme yaşanabilir; ön HMAC/SHA katmanıyla çözülmelidir.

## En İyi Pratikler (Özet)

- Yeni sistemlerde **Argon2id**'yi varsayılan seçin; scrypt ve bcrypt kabul edilebilir alternatiflerdir; PBKDF2'yi yalnızca uyumluluk zorunluluğunda tercih edin.
- Parametreleri **kendi üretim donanımınızda ölçerek** hedef gecikmeye göre kalibre edin; güncel başlangıç değerleri için OWASP gibi periyodik güncellenen kaynakları teyit edin.
- Her parola için **benzersiz, CSPRNG üretimi salt** kullanın (kütüphane zaten yapar).
- Ek katman olarak **pepper**'ı DB dışında, bir HMAC anahtarı gibi tutun.
- Doğrulamada **sabit zamanlı karşılaştırma** kullanın; başarılı girişte gerekirse **yeniden hash'leyin**.
- Parola hash'ini tek başına bırakmayın; **rate limiting, hesap kilitleme ve MFA** ile birlikte katmanlı bir savunma kurun.
- Parolayı asla düz metin saklamayın, log'lamayın veya geri döndürülebilir şekilde şifrelemeyin.
- Kullanıcıları uzun parolalara / passphrase'lere teşvik edin ve bilinen sızmış parolaları reddedin.

Sonuç olarak parola saklamanın özü tek bir cümlede toplanabilir: **veri tabanının sızacağını varsay ve o gün geldiğinde parolaların saldırgan için mümkün olduğunca değersiz olmasını sağla.** Bunu yapmanın yolu, hızlı genel amaçlı hash'lerden kaçınmak; kasıtlı olarak yavaş ve bellek-sert bir password hashing fonksiyonu (tercihen Argon2id) kullanmak; her parolaya benzersiz salt eklemek; mümkünse veri tabanı dışında bir pepper ile savunmayı derinleştirmek; ve tüm bunları rate limiting, sabit zamanlı doğrulama ve MFA ile tamamlamaktır.
