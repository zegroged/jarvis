# SQL Injection: Derinlemesine Referans

## Tanım

SQL Injection (SQLi), bir uygulamanın kullanıcıdan aldığı girdiyi, arka plandaki veritabanına gönderdiği SQL sorgusuna **veri** olarak değil, sorgunun **yapısının bir parçası** olarak dahil etmesinden doğan bir güvenlik açığıdır. Saldırgan, girdinin içine SQL sözdizimi (syntax) yerleştirerek uygulamanın orijinal sorgu mantığını değiştirir; sonuçta yetkisiz veri okuma, veri değiştirme, kimlik doğrulamayı atlatma (authentication bypass) ve bazı durumlarda işletim sistemi seviyesinde komut çalıştırma (RCE) mümkün hale gelir.

OWASP'ın yıllardır listelerinin tepesinde tuttuğu injection sınıfının en klasik ve en yıkıcı örneğidir. Onlarca yıldır bilinmesine rağmen hâlâ yaygın olmasının sebebi teknik değil mimaridir: geliştiriciler string birleştirme (concatenation) ile sorgu kurmaya devam ettiği sürece bu açık üretilmeye devam eder.

## Kök neden: Neden bu açık ortaya çıkıyor?

SQLi'yi anlamak için tek bir kavramı içselleştirmek gerekir: **kod ile verinin karışması (code/data confusion)**. Veritabanı motoru kendisine gelen metni ayrıştırırken (parse) hangi kısmın komut, hangi kısmın veri olduğunu ayırır. Sorun şu ki, geliştirici sorguyu bir metin (string) olarak elle kurduğunda, kullanıcı girdisi de o metnin içine düz metin olarak gömülür. Veritabanı motoru bu birleşmiş metni aldığında, saldırganın yazdığı `' OR '1'='1` parçasının "kötü niyetli veri" mi yoksa "meşru sorgu mantığı" mı olduğunu bilemez; çünkü ona ulaştığında ikisi arasında hiçbir sınır kalmamıştır.

Örneğin şu tehlikeli kalıbı düşünelim:

```
sorgu = "SELECT * FROM kullanicilar WHERE ad = '" + kullanici_adi + "'"
```

Kullanıcı `ali` yazarsa sorgu `... WHERE ad = 'ali'` olur, sorun yok. Ama kullanıcı `' OR '1'='1` yazarsa sorgu şuna dönüşür:

```
SELECT * FROM kullanicilar WHERE ad = '' OR '1'='1'
```

Burada `'1'='1'` her zaman doğru (true) olduğu için `WHERE` koşulu tüm satırlar için sağlanır. Saldırgan hiçbir geçerli kullanıcı adı bilmeden tüm tabloyu çeker. Dikkat edilirse saldırgan hiçbir "hack aracı" kullanmadı; sadece geliştiricinin açık bıraktığı tırnak sınırını kendi girdisiyle kapatıp ardından yeni mantık ekledi. İşte kök neden budur: **girdinin sorgu yapısını değiştirebilmesi.**

Bu noktayı vurgulamak önemli, çünkü birçok yanlış savunma (input filtreleme, tırnak temizleme) bu kök nedeni değil, semptomu hedef alır ve bu yüzden er ya da geç atlatılır. Kök nedeni ortadan kaldıran tek yaklaşım, veri ile kodu **daha veritabanına ulaşmadan** yapısal olarak ayırmaktır — bunu birazdan parametreli sorgular bölümünde ele alacağız.

## Türler ve sömürü mantığı

SQLi tek bir teknik değildir; saldırganın sorgu sonucunu nasıl geri okuyabildiğine göre birkaç aileye ayrılır. Buradaki asıl ayrım "hangi sözdizimi" değil, **"veri saldırgana hangi kanaldan geri dönüyor"** sorusudur.

### In-band SQLi: Union-based

Union-based teknik, saldırganın SQL'in `UNION SELECT` yapısını kullanarak orijinal sorgunun sonuç kümesine kendi seçtiği verileri **eklemesidir**. Sonuçlar doğrudan sayfada görüntülendiği için en hızlı ve en "gürültülü" tekniktir.

Çalışma mantığı şu koşula dayanır: `UNION` ile birleştirilecek iki `SELECT` **aynı sayıda sütuna** sahip olmalı ve sütun tipleri uyumlu olmalıdır. Bu yüzden sömürü genelde iki aşamalıdır:

1. **Sütun sayısını bulma:** Saldırgan `ORDER BY 1`, `ORDER BY 2` ... diye artırarak veya `UNION SELECT NULL`, `UNION SELECT NULL,NULL` diye deneyerek hata veren/vermeyen sınırı bulur. Hata değiştiği an sütun sayısı belli olur. Bunun mantığı, veritabanının uyumsuz kolon sayısında hata fırlatmasıdır; saldırgan bu hatayı bir "ölçüm aleti" gibi kullanır.
2. **Ekrana yansıyan sütunu bulma ve veri çekme:** Sütunlardan hangilerinin sayfada göründüğü tespit edilir, sonra o pozisyonlara `version()`, `current_user`, tablo/kolon isimleri veya gerçek veri yerleştirilir.

Savunma açısından kritik nokta: Union-based saldırının işe yaraması için genelde sorgunun sonucunun bir yerde gösterilmesi gerekir. Ama gösterilmemesi güvende olduğunuz anlamına gelmez — o zaman aşağıdaki blind teknikler devreye girer.

### Error-based SQLi

Error-based teknikte saldırgan, veritabanını **bilerek hata verecek** biçimde zorlar ve istediği veriyi o hata mesajının içine sızdırır. Mantık şudur: Bazı veritabanı fonksiyonları, işlerken bir alt-sorgunun sonucunu hata metnine dahil eder. Saldırgan `version()` gibi bir ifadeyi kasıtlı bir type/dönüşüm hatasının içine yerleştirir; veritabanı "şu değeri işleyemedim" derken o değeri ekrana basar.

Bu tekniğin ön koşulu, uygulamanın **ayrıntılı veritabanı hatalarını kullanıcıya göstermesidir**. Bu yüzden error-based, aynı zamanda en kolay kapatılabilen kanaldır: üretim ortamında ayrıntılı hata mesajlarını kapatmak (generic error page göstermek) bu vektörü büyük ölçüde kör eder. Yine de tek başına yeterli savunma değildir; sadece bir bilgi sızıntısı kanalını kapatır, açığın kendisini kapatmaz.

### Blind SQLi: Boolean-based

Blind (kör) SQLi, sonuçların **hiç görünmediği** durumlar içindir. Saldırgan veriyi doğrudan okuyamaz; onun yerine sorguya evet/hayır ile cevaplanabilecek koşullar ekleyip uygulamanın davranışındaki farktan sonucu **çıkarsar (infer)**.

Boolean-based varyantta saldırgan iki durumu ayırt eder: koşul doğruysa sayfa normal döner, yanlışsa farklı döner (örneğin "kullanıcı bulundu" vs "bulunamadı", ya da içeriğin var/yok olması). Örneğin `... AND SUBSTRING(sifre,1,1)='a'` gibi bir koşulla, parolanın ilk karakterinin `a` olup olmadığını sorar. Sayfa "doğru" davranışını gösterirse tahmin tutmuştur.

Bu, veriyi **tek tek bit/karakter** çıkaran son derece yavaş ama kesin bir yöntemdir. Sömürü mantığı özünde bir ikili aramadır (binary search): "İlk karakterin ASCII değeri 109'dan büyük mü?" gibi sorularla arama uzayı her adımda yarıya iner. Bu yüzden pratikte otomatize edilir. Savunma açısından ders şudur: Sayfada hiçbir SQL çıktısı görünmese bile, uygulamanın gözlemlenebilir herhangi bir davranış farkı (içerik, HTTP durum kodu, yönlendirme) bir sızıntı kanalıdır.

### Blind SQLi: Time-based

Bazen doğru/yanlış arasında gözlemlenebilir hiçbir içerik farkı yoktur — sayfa her iki durumda da aynı görünür. Bu durumda saldırgan **zamanı** bir sinyal kanalına dönüştürür. Koşul doğruysa veritabanına bir gecikme uygulatır (örneğin `SLEEP` benzeri fonksiyonlar veya ağır bir işlemle yapay bekleme), yanlışsa gecikme olmaz. Saldırgan cevabın gelme süresini ölçer: yanıt geç geldiyse koşul doğrudur.

Time-based tekniğin ince mantığı şudur: Veritabanı motoruna koşullu bir bekleme koydurabiliyorsanız, çıktı görmenize hiç gerek yoktur; ölçüm aletiniz kronometredir. Bu, en yavaş ama en "körlükte bile çalışan" tekniktir. Ağ gecikmesi (jitter) ölçümü kirlettiği için saldırganlar genellikle birden fazla ölçüm alıp istatistiksel olarak karar verir.

Savunma perspektifinden time-based saldırıların varlığı önemli bir şeyi kanıtlar: "Hiçbir veriyi ekrana basmıyoruz" demek SQLi'ye karşı koruma sağlamaz. Kanal ne kadar zayıf olursa olsun (tek bir bit'lik zamanlama farkı bile) veri sızdırmaya yeter.

### Out-of-band (OOB) SQLi

Bazı ortamlarda ne çıktı ne de güvenilir bir zamanlama kanalı vardır; ama veritabanı dışarıya ağ isteği (DNS/HTTP çözümlemesi gibi) yapabiliyorsa, saldırgan veriyi bu isteğin içine gömerek kendi kontrolündeki bir sunucuya sızdırır. Mantık aynı: veriyi geri getirmenin herhangi bir yan kanalını (side channel) kullanmak. Bu teknik veritabanının dış ağ erişimine bağlı olduğu için savunmada güçlü bir ders verir: **veritabanının dışa doğru ağ erişimini kısıtlamak** (egress filtering) bu kanalı kapatır.

## Farklı veritabanları: Neden fark eder?

SQLi'nin çekirdek mantığı tüm veritabanlarında aynıdır, ama sömürünün **detayları** motora göre ciddi biçimde değişir. Bir pentester'ın önce "hangi DB?" diye sormasının sebebi budur. Farklar şu eksenlerde toplanır:

- **String birleştirme sözdizimi:** Örneğin klasik olarak MySQL `CONCAT()` fonksiyonunu tercih ederken, Oracle ve PostgreSQL `||` operatörünü, Microsoft SQL Server ise `+` operatörünü string birleştirme için kullanır. Saldırgan payload'unu hedef motora göre uyarlamak zorundadır.
- **Yorum (comment) karakterleri:** Sorgunun geri kalanını iptal etmek için kullanılan yorum işaretleri farklıdır (yaygın örnekler `--`, `#` ve `/* */` bloklarıdır; hangisinin geçerli olduğu motora ve bağlama bağlıdır).
- **Metadata / sistem katalogları:** Tablo ve kolon isimlerini keşfetmek için sorgulanan yerler değişir. Birçok modern veritabanı `information_schema` standardını desteklerken, Oracle geleneksel olarak kendi sözlük görünümlerini (`ALL_TABLES` gibi) kullanır ve klasik olarak her `SELECT`'in bir `FROM` gerektirmesi nedeniyle `DUAL` sözde-tablosuyla anılır.
- **Zaman geciktirme fonksiyonları:** Time-based saldırıda kullanılan bekletme yöntemi motora özgüdür (bazılarında doğrudan bir uyku fonksiyonu, bazılarında ağır hesap yaptırma veya zaman ekleme mantığı).
- **Yığın sorgu (stacked queries) desteği:** Bazı sürücü/motor kombinasyonları noktalı virgülle ayrılmış birden çok ifadeyi tek çağrıda çalıştırmaya izin verir; bu, `INSERT`/`UPDATE`/`DROP` gibi ikinci bir komut enjekte etmeyi mümkün kılar. Bu davranış hem motora hem de kullanılan veritabanı sürücüsüne (driver) bağlıdır — örneğin bazı arayüzler tek çağrıda çoklu ifadeyi güvenlik gereği reddeder.

Buradan çıkan savunma dersi: Uygulamanızın hangi motoru kullandığı saldırganın işini kolaylaştırır ama savunmanızı değiştirmez. Parametreli sorgular tüm bu motorlarda çalışan tek, tutarlı savunmadır.

## WAF bypass mantığı: Neden imza tabanlı savunma yetersiz kalır?

Web Application Firewall (WAF), gelen isteklerde bilinen saldırı desenlerini (imza/signature) arayarak SQLi'yi durdurmaya çalışan bir ara katmandır. Faydalıdır ama kavramsal olarak kusurludur ve bunun **neden** böyle olduğunu anlamak, WAF'a fazla güvenmemek için kritiktir.

Temel sorun şudur: WAF, isteğin **metnini** görür; veritabanının o metni **nasıl yorumlayacağını** tam olarak modelleyemez. Saldırgan ile WAF, aynı stringin farklı yorumları üzerinden bir kedi-fare oyunu oynar. Bypass mantığı birkaç temel fikre dayanır:

- **Denklik / eşdeğer ifadeler:** WAF `OR 1=1` desenini bloklayabilir, ama aynı mantığı ifade etmenin sonsuz yolu vardır (`OR 2>1`, `OR 'a'='a'`, farklı boşluk/parantez düzenleri). İmza belirli bir metni yakalar; mantığı yakalayamaz.
- **Kodlama katmanları (encoding):** Aynı payload URL-encoding, çift kodlama (double encoding), hex, Unicode veya farklı karakter kodlamaları ile yazılabilir. WAF girdiyi bir kez çözerken, arka uçtaki teknoloji yığını onu başka türlü normalize edip farklı yorumlayabilir. Aradaki bu **normalizasyon uyuşmazlığı** bypass'ın kalbidir.
- **Boşluk ve yorum hileleri:** Boşluk yerine yorum bloklarının, sekmelerin, satır sonlarının veya alternatif ayraçların kullanılması, katı imzaları atlatabilir.
- **Büyük/küçük harf ve parçalama:** Anahtar kelimeleri karıştırmak veya WAF'ın yeniden birleştirmediği biçimde bölmek.

Buradaki **kavramsal ders** çok önemli: WAF bir "yorum farkı" saldırısına karşı savunmasızdır çünkü WAF ile veritabanı aynı stringi asla birebir aynı şekilde yorumlamaz. Bu yüzden WAF **derinlemesine savunmanın (defense in depth)** bir katmanı olarak değerlidir — gürültüyü azaltır, otomatik tarayıcıları yavaşlatır, tespit sağlar — ama **birincil savunma asla WAF olmamalıdır**. Açığı kaynağında (parametreli sorgu ile) kapatmayıp WAF'a güvenmek, deliği yamalamak yerine önüne perde çekmektir.

## Birincil savunma: Parametreli sorgular (prepared statements)

SQLi'nin doğru çözümü girdiyi temizlemek değil, **kodu veriden yapısal olarak ayırmaktır**. Parametreli sorgular (parameterized queries / prepared statements) tam olarak bunu yapar ve bu yüzden altın standarttır.

Mantığı şudur: Sorgunun iskeletini yer tutucularla (placeholder) önceden veritabanına gönderirsiniz:

```
SELECT * FROM kullanicilar WHERE ad = ? AND sifre = ?
```

Veritabanı bu iskeleti **kullanıcı girdisini görmeden** ayrıştırır ve sorgu planını sabitler. Sonra girdiyi ayrı bir kanaldan, "bu sadece veridir" etiketiyle gönderirsiniz. Kritik nokta budur: Girdi, sorgu **zaten ayrıştırıldıktan sonra** geldiği için, içinde ne kadar tırnak, `OR '1'='1'` veya `;DROP TABLE` olursa olsun, veritabanı bunu asla komut olarak yorumlayamaz — çünkü yorumlama aşaması çoktan bitmiştir. Saldırganın `' OR '1'='1` girdisi burada sadece "adı tam olarak `' OR '1'='1` olan kullanıcıyı ara" anlamına gelir ve hiçbir satır dönmez.

Neden filtrelemeden üstün? Çünkü kök nedeni ortadan kaldırır. Filtreleme (kara liste/blacklist) "kötü şeyleri tahmin edip yasaklamaya" çalışır ve bu asla eksiksiz olamaz — saldırgan düşünmediğiniz bir formu bulur. Parametreli sorgu ise problemi tersine çevirir: kötü girdiyi tanımaya çalışmaz, girdinin **kod olma ihtimalini** tamamen imkânsız kılar. Beyaz liste (whitelist) mantığıyla çalışan, "güvenli tarafta olma" (fail-safe) yaklaşımıdır.

Önemli bir sınır: Parametreli sorgular **değerleri** parametreleştirebilir, ama tablo/kolon isimleri veya `ORDER BY` yönü gibi **tanımlayıcıları (identifier)** parametreleştiremez. Bu kısımlar dinamik olmak zorundaysa, kullanıcı girdisini doğrudan koymak yerine katı bir **izin verilenler listesiyle (allowlist)** eşleştirmelisiniz: gelen değeri önceden tanımlı geçerli kolon adları kümesiyle karşılaştırıp yalnızca eşleşeni kullanmak. Bu, SQLi'nin sık atlanan bir arka kapısıdır.

## ORM tuzakları: "ORM kullanıyorum, güvendeyim" yanılgısı

Object-Relational Mapping (ORM) kütüphaneleri (Hibernate, Entity Framework, Django ORM, SQLAlchemy, Sequelize gibi) sorguları sizin yerinize üretir ve **varsayılan kullanımda** genellikle parametreli sorgu ürettikleri için SQLi'ye karşı iyi bir taban sağlar. Ama ORM kullanmak sihirli bir muafiyet değildir; asıl tehlike, geliştiricilerin ORM'e körü körüne güvenip **güvenliği delen kapıları** fark etmemesidir. Başlıca tuzaklar:

- **Ham SQL / native query kaçış kapıları:** Hemen her ORM, karmaşık sorgular için "ham SQL çalıştır" imkânı sunar (`raw()`, `nativeQuery`, `execute` gibi). Geliştirici bu ham SQL'i string birleştirmeyle kurarsa, ORM'in tüm koruması buharlaşır ve klasik SQLi geri gelir. ORM'in güvenliği, ORM'i **doğru katmanda** kullanmaya bağlıdır.
- **Fonksiyon içinde string interpolation:** ORM'in bir metodu string aldığında (örneğin bir `WHERE` ifadesini serbest metin olarak kabul eden API'ler, ya da bazı ORM'lerdeki `extra`/raw fragment özellikleri), geliştirici o metne kullanıcı girdisini gömerse yine açık oluşur. ORM metodu "parametreli" görünse de içine kod gömülebilen bir string alıyorsa tuzak vardır.
- **Sıralama, kolon adı ve LIMIT gibi tanımlayıcılar:** Yukarıda değinildiği gibi bunlar parametreleştirilemez. Birçok ORM API'si `order_by` gibi alanlara gelen kolon adını doğrudan sorguya yazar; kullanıcının kontrol ettiği kolon adı doğrudan geçerse enjeksiyon riski doğar. Çözüm yine allowlist.
- **Toplu / dinamik sorgu üretimi:** Geliştirici filtreleri dinamik olarak birleştirirken ORM'in query builder'ını doğru kullanmak yerine string parçaları eklerse, güvenlik yeniden geliştiricinin eline geçer.
- **Yanlış güven ve denetim eksikliği:** En sinsi tuzak psikolojiktir. "ORM kullanıyoruz" cümlesi, kod incelemelerinde (code review) SQL güvenliğinin hiç sorgulanmamasına yol açar; oysa tek bir yanlış kullanılmış ham sorgu yeterlidir.

Özetle ORM, doğru kullanıldığında güçlü bir savunmadır ama **savunmayı garanti eden şey ORM'in varlığı değil, parametreleştirmenin korunmasıdır**. ORM sadece bu doğru davranışı varsayılan hale getirir; onu bilerek devre dışı bırakabilirsiniz.

## Yaygın hatalar

Sahada tekrar tekrar görülen ve neden yanlış olduğunu bilmenin önemli olduğu hatalar:

- **Kara liste (blacklist) filtreleme:** "Şu kelimeleri yasakla" yaklaşımı asla eksiksiz olamaz; kodlama, eşdeğer ifadeler ve motor farklarıyla atlatılır. Kök nedeni değil semptomu hedef alır.
- **Sadece tırnak temizleme / kaçırma (escaping):** Elle escaping yapmak hem hataya açıktır hem de sayısal (numeric) bağlamlarda çoğu zaman işe yaramaz — sayısal alanlarda tırnak zaten kullanılmadığı için tırnak kaçırmak hiçbir şey korumaz. Ayrıca farklı karakter kodlamalarıyla bozulabilir.
- **Sadece istemci tarafı (client-side) doğrulama:** JavaScript ile yapılan girdi kontrolü sadece kullanıcı deneyimi içindir; saldırgan isteği doğrudan sunucuya gönderir. Güvenlik daima sunucu tarafında olmalıdır.
- **WAF'ı birincil savunma sanmak:** Yukarıda açıklandığı gibi WAF atlatılabilir; tek başına güven kaynağı olamaz.
- **Ayrıntılı hata mesajlarını üretimde açık bırakmak:** Error-based sızıntıya ve keşfe davetiye çıkarır.
- **En az yetki (least privilege) ilkesini ihmal etmek:** Uygulamanın veritabanına `admin`/`root` yetkileriyle bağlanması, bir SQLi'nin etkisini "veri okuma"dan "tüm veritabanını silme veya OS komutu çalıştırma"ya yükseltir.
- **Stored procedure'ün otomatik güvenli olduğunu sanmak:** Stored procedure içinde dinamik SQL string'i birleştiriliyorsa, prosedür olması hiçbir koruma sağlamaz; açık prosedürün içine taşınmış olur.
- **Bir alanı düzeltip diğerlerini unutmak:** Login formunu parametreleştirip arama, sıralama, rapor filtresi gibi ikincil yerleri gözden kaçırmak. SQLi tek bir açık noktadan girer.

## En iyi pratikler

Derinlemesine savunma (defense in depth) mantığıyla, katmanlı ve öncelik sırasına göre:

1. **Her yerde parametreli sorgu / prepared statement kullanın.** Bu birincil ve pazarlık edilemez savunmadır. Kod tabanında string birleştirmeyle kurulmuş hiçbir sorgu kalmamalıdır.
2. **Dinamik tanımlayıcılar için katı allowlist uygulayın.** Kolon adı, sıralama yönü, tablo adı gibi parametreleştirilemeyen kısımları önceden tanımlı geçerli değerler kümesiyle eşleştirin.
3. **En az yetki ilkesini uygulayın.** Uygulamanın veritabanı hesabına yalnızca ihtiyaç duyduğu tablolar ve işlemler için yetki verin; sızıntının etki alanını (blast radius) sınırlayın.
4. **Girdi doğrulamayı ikincil katman olarak, beyaz liste mantığıyla yapın.** Beklenen tip, uzunluk ve format doğrulanmalı — bu SQLi'nin tek başına çözümü değildir ama savunma derinliği ekler.
5. **Üretimde ayrıntılı hataları gizleyin, arka planda loglayın.** Kullanıcıya generic hata, sunucuda tam ayrıntı.
6. **WAF'ı bir katman olarak konumlandırın**, birincil savunma olarak değil; tespit ve gürültü azaltma için değerlidir.
7. **Veritabanının dışa ağ erişimini kısıtlayın (egress filtering)** ki OOB kanalları kapansın.
8. **ORM kullanıyorsanız ham SQL yollarını denetleyin;** kod incelemesinde `raw`/`native`/string interpolation kalıplarını özel olarak arayın.
9. **Otomatik test ve tarama entegre edin.** SAST/DAST araçlarını ve düzenli sızma testlerini (penetration testing) geliştirme sürecine dahil edin.
10. **Güvenli tarafta hata verin (fail securely) ve kodu düzenli gözden geçirin.** Tek bir gözden kaçmış sorgu tüm sistemi açar; bu yüzden savunma bir defalık düzeltme değil, sürekli bir disiplindir.

## Kapanış

SQL Injection, ileri düzey bir "hackleme" tekniğinden çok, bir yazılım tasarım hatasının sonucudur: kod ile verinin karışması. Türleri (union, error, blind boolean, time-based, OOB) aslında aynı kök nedenin, saldırganın veriyi hangi kanaldan geri okuyabildiğine göre farklılaşan yüzleridir. Farklı veritabanları sömürünün ayrıntısını değiştirir ama savunmasını değiştirmez. WAF ve filtreleme semptomu geciktirir; kök nedeni yalnızca **kodu veriden yapısal olarak ayıran parametreli sorgular** çözer. ORM'ler bu doğru davranışı varsayılan yapar ama ham SQL kaçış kapılarıyla delinebilir. Nihai ders nettir: Güvenlik, girdiyi temizlemeye çalışmakta değil, girdinin asla kod olarak yorumlanamayacağı bir mimari kurmaktadır.
