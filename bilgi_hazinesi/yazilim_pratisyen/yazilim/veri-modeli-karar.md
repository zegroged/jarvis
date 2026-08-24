# Veri Modeli Tasarım Kararı — Sahadan Pratisyen Notları

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Veri modeli, bir sistemin en kalıcı parçasıdır. Kod her hafta değişir, framework beş yılda bir değişir, ama şemanız (schema) migration üstüne migration ile taşınarak sistemin ömrü boyunca sizinle kalır. Bir metod imzasını yanlış tasarlarsan on dakikada refactor edersin. Bir tabloyu yanlış tasarlarsan, üstüne on servis, üç rapor, iki ETL job'ı ve bir mobil uygulama bağlandıktan sonra düzeltmen aylar sürer, hatta bazen hiç düzeltilmez, üstüne yama atılır. Bu yüzden veri modeli kararı, yazılımdaki en yüksek "yanlış yapma maliyeti" olan kararlardan biridir.

Bu iş şu anlarda masaya gelir: yeni bir özellik ("kullanıcılar artık birden fazla adres girebilecek"), yeni bir entity ("abonelik planları geliyor"), ya da mevcut modelin çatırdaması ("`users` tablosunda 47 kolon var ve yarısı `NULL`"). Kritik nokta şu: veri modeli kararı asla "veritabanı kararı" değildir. İş kurallarının veriye izdüşümüdür. Yanlış modelin kaynağı neredeyse her zaman iş alanını (domain) yeterince anlamamaktır, veritabanı bilgisi eksikliği değil.

Acemi mühendis "hangi tabloları açayım" diye sorar. Kıdemli mühendis "bu domainde gerçekte hangi şeyler var, aralarındaki ilişki ne, hangi kural zamanla değişir, neyi asla kaybetmemeliyim" diye sorar. Tablolar bu soruların cevabından türer, tersi değil.

## 2. Metodoloji ve karar ağacı: pro adım adım nasıl ilerler

### Adım 0: Erişim desenini (access pattern) önce çıkar, şemayı sonra

Bu, en çok atlanan ve en pahalı hatanın kaynağı olan adımdır. Şemayı tasarlamadan önce şu soruyu net cevaplarım: **bu veri nasıl okunacak, nasıl yazılacak, hangi sorgular sıcak yolda (hot path) çalışacak?**

İlişkisel dünyada bile bu belirleyicidir, ama NoSQL'de hayat-memat meselesidir. Bir belge veritabanında (document store) ya da anahtar-değer (key-value) deposunda şemayı erişim deseninden bağımsız tasarlarsan felaket olur, çünkü join yoktur, sorgu esnekliği yoktur. İlişkisel dünyada esneklik seni bir süre kurtarır ama sonsuza kadar değil.

Somut bir belirti-yön eşleşmesi: "Bu veriyi %95 zaman şu üç alanla birlikte okuyacağım" diyorsam, o üç alanı bölme, birlikte tut. "Bu alt-varlığı ana varlıktan bağımsız olarak, tek başına listelemem/güncellememem gerekecek" diyorsam, ayrı tabloya çıkar. Karar, veriye değil, veriye nasıl dokunacağıma bağlı.

### Adım 1: Normalizasyon — varsayılan olarak 3NF, bilinçli olarak geri çekil

Varsayılanım her zaman normalleştirmektir (en az 3. normal form). Sebebi estetik değil: normalize model, "tek gerçeğin tek yeri" (single source of truth) ilkesini garanti eder. Bir müşterinin adı tek bir yerde tutulur; değişince tek yerde değişir; tutarsızlık (anomaly) matematiksel olarak imkânsız hale gelir.

Denormalizasyon bir optimizasyondur ve tüm optimizasyonlar gibi **kanıt ister**. "Hızlı olsun diye" değil, "şu sorgu şu kadar QPS'te şu join'i kaldıramıyor, ölçtüm, o yüzden şu alanı kopyalıyorum ve tutarlılığı şu mekanizmayla sağlayacağım" diye denormalize ederim. Ölçmeden denormalize etmek, sorunu çözmeden karmaşıklık eklemektir.

Karar ağacı şöyle işler:
- Veri doğal olarak ilişkisel mi (varlıklar arası net bağlar, tutarlılık kritik, raporlama var)? → İlişkisel, normalize başla.
- Okuma ağır basıyor ve join maliyeti ölçülmüş bir darboğaz mı? → Hedefli denormalizasyon, ama yazma yolunda tutarlılığı nasıl koruyacağını yazılı olarak belirle.
- Şema sık ve öngörülemez şekilde değişiyor, varlıklar heterojen mi? → Belge modeli düşün, ama "şemasız" demenin "şema uygulamada, doğrulanmamış" demek olduğunu bil.

### Adım 2: Anahtar (key) seçimi — burada acemi en çok kanar

Birincil anahtar (primary key) seçimi göründüğünden çok daha stratejik bir karardır. Üç seçenek ve gerçek takasları:

**Auto-increment integer:** Küçük, hızlı, indeks dostu, insan tarafından okunabilir. Ama: dağıtık sistemde çakışır, tahmin edilebilir olması güvenlik/mahremiyet sızıntısıdır (URL'de `/invoice/1042` görünce rakibin kaç fatura kestiğini anlar), ve tabloları merge etmek istediğinde cehennem yaşarsın.

**UUID (v4):** Global benzersiz, dağıtık üretilebilir, tahmin edilemez. Ama: 16 byte, ve rastgele olduğu için B-tree indekste yazma sırasında sayfa bölünmelerine (page split) ve indeks şişmesine yol açar. Yüksek yazma hacminde bu ölçülebilir bir performans vergisidir.

**UUID v7 / ULID (zaman-sıralı):** Son yılların pratik kazananı. UUID'nin benzersizliğini verir ama zaman-önekli olduğu için indekste ardışık yazılır, page split sorununu büyük ölçüde çözer. Yeni sistem kuruyorsam ve dağıtık kimlik gerekiyorsa varsayılanım budur.

Pratik kalıbım: **iç birincil anahtar ayrı, dış kimlik ayrı.** İçeride `bigint` auto-increment (join'ler ve indeksler için ucuz), dışarıda API'de gösterdiğim tahmin edilemez bir `public_id` (UUID/ULID). Bu, hem performansı hem güvenliği verir. Tek bir anahtarı hem iç join'lerde hem dış API'de kullanmaya çalışmak, iki farklı ihtiyacı tek çözüme sıkıştırmaktır.

Bir de doğal anahtar (natural key) tuzağı: e-posta adresini, TC kimlik numarasını, telefon numarasını birincil anahtar yapma. "Değişmez" sandığın her şey değişir. E-posta değişir, insan yanlış girer, birleşen şirketlerde çakışır. Bunları benzersiz kısıt (unique constraint) yap ama birincil anahtar yapma.

### Adım 3: NULL, opsiyonellik ve "eksik veri"nin anlamı

`NULL` bir değer değil, bir bilgi yokluğudur ve semantiği zehirlidir. Bir kolonda `NULL` görünce sormam gereken: "bu 'bilinmiyor' mu, 'uygulanamaz' mı, 'henüz girilmedi' mi?" Üç farklı şey, tek gösterim. Pro, kolonun `NULL` olabilirliğini bilinçli bir domain kararı olarak verir, "ne olur ne olmaz açık bırakayım" diye değil.

Çok `NULL`'lı bir tablo çoğu zaman gizli bir alt-tip (subtype) hiyerarşisinin çığlığıdır. `users` tablosunda `company_name`, `tax_id`, `vat_rate` kolonları sürekli `NULL` ise, orada aslında "bireysel kullanıcı" ve "kurumsal kullanıcı" diye iki farklı tip var ve sen onları tek tabloya tıkıştırmışsın.

### Adım 4: Zaman, değişmezlik ve tarihçe

En kritik ayrımlardan biri: **bu veri "şu anki durum" mu, yoksa "olan biten olay" mı?** Bir müşterinin adresi güncellenebilir bir durumdur. Ama bir siparişin teslimat adresi, sipariş anındaki değeri sonsuza dek korumalıdır — müşteri taşınınca eski faturasının adresi değişmemeli.

Acemi, sipariş tablosunda `customer_id` tutar ve adresi join'le çeker. Altı ay sonra müşteri taşınır ve tüm eski faturalar yanlış adresi göstermeye başlar. Bu bir felakettir ve muhasebe/hukuk açısından gerçek bir sorundur. Pro, sipariş anında adresi **kopyalar** (snapshot alır), çünkü o veri o anda dondurulmalıdır. Burada denormalizasyon bir bug değil, doğru domain modelidir: sipariş satırı finansal bir olayın değişmez kaydıdır.

Genel ilke: parasal/hukuki/denetim gerektiren kayıtları olabildiğince **append-only** (yalnızca ekleme, güncelleme yok) tasarla. Bir faturayı `UPDATE` ile değiştirmek yerine iptal+yeni fatura kes. Bu, hem denetlenebilirlik hem de eşzamanlılık (concurrency) sorunlarını baştan yok eder.

### Adım 5: İlişki kardinalitesi ve "gizli çoklu"

Her ilişki için sorarım: bir-e-bir mi, bir-e-çok mu, çok-e-çok mu? Ve asıl kritik soru: **bu bugün böyle, yarın değişecek mi?** "Bir kullanıcının bir adresi vardır" bugün doğru olabilir ama iş büyüyünce "bir kullanıcının birden fazla adresi" olur. Kardinaliteyi çok erken sabitleyip kolon olarak gömmek (adres alanlarını `users` içine koymak), o değişim geldiğinde acı bir migration'a mal olur.

Kuralım: yakın gelecekte çoğullaşma ihtimali ciddi olan her "bir-e-bir"i, en baştan ayrı tablo + foreign key olarak tasarlarım. Bu ucuz bir sigortadır. Ama abartma — her şeyi "belki bir gün çok olur" diye ayırırsan aşırı-mühendislik (over-engineering) yaparsın. Karar, domain bilgisine dayanır: e-posta çoğullaşabilir (iş+kişisel), doğum tarihi çoğullaşamaz.

## 3. Gerçek senaryo üzerinden yürüyüş: zafiyetli → teşhis → düzeltilmiş

Bir e-ticaret sisteminde işe başladığımı düşünelim. Ürünlerin fiyatları var, siparişler var. İlk (hatalı) tasarım şöyle:

**Zafiyetli model:**

```
products
  id            bigint PK
  name          text
  price         numeric(10,2)
  category      text          -- "Elektronik", "Ev", ...

orders
  id            bigint PK
  user_id       bigint FK
  product_id    bigint FK
  quantity      int
  created_at    timestamptz
```

Sipariş toplamını hesaplarken `products.price * orders.quantity` yapılıyor. Kategori, ürün tablosunda düz metin olarak tutuluyor. İlk bakışta temiz görünüyor, testler geçiyor, demo çalışıyor. Üretimde ne patlar?

**Teşhis — üç ayrı bomba:**

**Bomba 1 (fiyat tarihçesi):** Sipariş toplamı, ürünün *güncel* fiyatından hesaplanıyor. Ürün fiyatı 100 TL iken müşteri sipariş verdi. Ertesi gün fiyatı 150'ye çıkardık. Şimdi dünkü siparişin toplamı raporlarda 150 görünüyor. Müşteri 100 ödedi, sistem 150 diyor. Bu bir muhasebe felaketidir. Belirti: "raporlardaki gelir, tahsil edilen parayla tutmuyor." Kök neden: finansal bir olay (sipariş), değişebilen bir referansa (güncel fiyat) bağlanmış. Sipariş anındaki fiyat dondurulmamış.

**Bomba 2 (kategori düz metin):** `category` bir metin kolonu. Birisi "Elektronik", biri "elektronik", biri "Elektronık" (Türkçe klavye) girmiş. Kategoriye göre gruplama yapan rapor üç ayrı kategori gösteriyor. Belirti: "dropdown'da aynı kategori üç kez çıkıyor, rapor bozuk." Kök neden: bir enum/referans verisi olması gereken şey, serbest metin olarak modellenmiş; tekliğini (canonical set) veritabanı garanti etmiyor.

**Bomba 3 (sipariş = tek ürün):** `orders` tablosu ürünü doğrudan taşıyor, yani bir sipariş = bir ürün. Sepete iki farklı ürün koyunca ne olacak? İki ayrı `order` satırı mı? O zaman "sipariş" kavramı kırılıyor — tek kargo, tek ödeme, ama iki sipariş kaydı. Belirti: "kargo ücretini nasıl bölüştüreceğiz, ödeme hangi siparişe ait?" Kök neden: gerçek domainde sipariş (order) ile sipariş satırı (order line) iki ayrı kavram; model bunları tek varlığa ezmiş.

**Düzeltilmiş model:**

```
categories
  id            bigint PK
  slug          text UNIQUE        -- "elektronik" (canonical, tek biçim)
  display_name  text

products
  id            bigint PK
  public_id     uuid UNIQUE         -- dışarı gösterilen kimlik
  name          text NOT NULL
  category_id   bigint FK -> categories
  current_price numeric(12,2) NOT NULL   -- "şimdiki" fiyat, sadece görüntü/yeni sipariş için

orders
  id            bigint PK
  public_id     uuid UNIQUE
  user_id       bigint FK
  status        text NOT NULL       -- 'pending','paid','shipped',...
  ship_address  jsonb NOT NULL      -- sipariş anında dondurulmuş adres snapshot'ı
  created_at    timestamptz NOT NULL DEFAULT now()

order_lines
  id            bigint PK
  order_id      bigint FK -> orders
  product_id    bigint FK -> products     -- referans (hangi ürün olduğunu bilmek için)
  product_name  text NOT NULL             -- sipariş anındaki ad (snapshot)
  unit_price    numeric(12,2) NOT NULL    -- sipariş anındaki fiyat (DONDURULMUŞ)
  quantity      int NOT NULL CHECK (quantity > 0)
```

Kritik farklar ve *neden*:

- **`order_lines.unit_price`**: fiyat, sipariş satırına kopyalanıyor. Ürünün fiyatı sonra değişse de bu satır dokunulmaz kalıyor. Finansal olay dondurulmuş oldu. Bomba 1 çözüldü. Burada denormalizasyon *doğru* karardır çünkü modellediğimiz şey "şu anki fiyat" değil, "o anda anlaşılan fiyat."
- **`categories` tablosu + FK**: kategori artık referans veri. Yeni kategori girmek kontrollü, yazım hatası imkânsız, çünkü foreign key olmayan bir kategoriyi kabul etmez. Bomba 2 çözüldü.
- **`orders` / `order_lines` ayrımı**: bir sipariş, birden çok satır içerir. Ödeme, kargo, durum siparişe ait; ürün-adet bilgisi satıra ait. Bomba 3 çözüldü.
- **`public_id uuid`**: iç join'ler ucuz `bigint` üstünden, dış API tahmin-edilemez UUID üstünden. Kimlik sızıntısı kapandı.
- **`ship_address jsonb` snapshot**: teslimat adresi sipariş anında donduruldu; müşteri taşınsa da eski fatura doğru adresi gösterir.
- **`CHECK (quantity > 0)`**: veri bütünlüğü kuralı uygulama katmanında değil, veritabanında. Uygulama kodu ne kadar buglı olursa olsun negatif adet giremez.

Buradaki genel ders: **veri bütünlüğü kurallarını mümkün olduğunca veritabanına yaklaştır.** `NOT NULL`, `UNIQUE`, `CHECK`, `FOREIGN KEY` bedava değil ama ucuz sigortalardır. Uygulama katmanındaki doğrulama atlanabilir (yeni bir servis, bir migration script, bir manuel `INSERT`), ama veritabanı kısıtı asla atlanmaz. "Kod nasılsa kontrol ediyor" cümlesi, üretimde bozuk veri gördüğün her seferde yalan çıkar.

## 4. Acemi vs pro: yaygın hatalar ve gizli tuzaklar

**EAV (Entity-Attribute-Value) tuzağı.** Acemi, "şema esnek olsun, ileride her türlü alan eklenebilsin" diye şu tabloyu kurar: `entity_id | attribute_name | value`. Her şey bu üç kolonda. İlk başta müthiş esnek görünür. Üretimde: hiçbir sorgu yazılamaz hale gelir, tip güvenliği yoktur (her şey text), tek bir "kullanıcıyı tüm alanlarıyla getir" sorgusu 20 tabloya self-join olur, indeksleme çöker. EAV, "şema tasarlamaktan kaçınmak için tasarlanmış anti-şema"dır. Gerçekten dinamik alan gerekiyorsa (kullanıcı-tanımlı özel alanlar gibi dar bir senaryo) modern çözüm `jsonb` kolonudur — ama bunu bile "çekirdek domain alanlarım için değil, gerçekten öngörülemeyen uçtaki veriler için" kuralıyla kullanırım.

**Erken denormalizasyon / performans batıl inancı.** "Join yavaştır" cümlesi acemi ağzında dolaşan ve çoğu zaman yanlış olan bir inançtır. Doğru indekslenmiş bir join, milyonlarca satırda bile milisaniyelerdir. Ölçmeden "hızlı olsun diye" veri kopyalamak, sana somut bir hız kazandırmadan kesin bir tutarlılık borcu yükler. Pro'nun sırası: önce temiz normalize model → gerçek veriyle yükle → yavaş sorguyu ölç (`EXPLAIN ANALYZE`) → önce indeks dene → hâlâ yetmiyorsa hedefli denormalize et. Denormalizasyon son çare, ilk hamle değil.

**"Soft delete" her yere serpiştirme.** Acemi her tabloya `is_deleted` kolonu ekler, "veri kaybetmeyelim" diye. Sonuç: her sorguya `WHERE is_deleted = false` eklemeyi unutan biri silinmiş veriyi görür; unique constraint'ler silinmiş kayıtlarla çakışır (silinmiş e-postayı tekrar kaydedemezsin); tablolar çöple şişer. Soft delete bir araçtır, refleks değil. Gerçekten gerekiyorsa (denetim, geri alma) bilinçli uygula; gerekmiyorsa gerçekten sil ve tarihçe gerekiyorsa ayrı bir arşiv/audit tablosu tut.

**Para için `float`/`double` kullanmak.** Bu klasiktir ve hâlâ olur. `0.1 + 0.2` kayan noktada `0.30000000000000004`'tür. Parayı `float` tutan sistem, binlerce işlem sonra kuruş kuruş kayar ve mutabakat tutmaz. Para her zaman `numeric`/`decimal` (sabit ondalık) ya da tam sayı olarak en küçük birim (kuruş) cinsinden tutulur. Belirti: "muhasebe raporu birkaç kuruş tutmuyor." Bu, tip seçiminin domain kararı olduğunun en net örneğidir.

**Enum'u veritabanı enum tipi olarak sabitlemek.** Native `ENUM` tipi cazip görünür ama değer eklemek/çıkarmak migration gerektirir ve bazı veritabanlarında sancılıdır. Değerler zamanla değişecekse (statü listesi genişleyecek), referans tablo + FK genelde daha esnektir. Değerler gerçekten sabitse (`'M'/'F'/'X'` gibi) native enum ya da `CHECK` kısıtı uygundur. Karar, "bu liste ne sıklıkla değişir"e bağlı.

**Tarih/saatte zaman dilimi (timezone) körlüğü.** `timestamp` (tz'siz) kullanıp veriyi sunucunun yerel saatinde yazmak, sunucu taşınınca ya da farklı bölgeden kullanıcı gelince tüm zamanları kaydırır. Kuralım basit: her şeyi UTC olarak `timestamptz` sakla, sadece görüntülerken kullanıcının diliminde göster. "Sadece tarih" (doğum günü gibi) için `date` kullan — ona saat/dilim bulaştırma.

**Migration'ı düşünmeden şema tasarlamak.** Acemi mühendis şemayı "boş veritabanına ilk kez kuruluyormuş" gibi tasarlar. Pro her kararı "bu tabloda 50 milyon satır varken bu değişikliği nasıl yaparım" gözüyle test eder. `NOT NULL` bir kolonu dolu tabloya varsayılansız eklemek tabloyu kilitleyip üretimi durdurabilir. Büyük tabloda kolon eklemenin, indeks oluşturmanın (çoğu modern DB'de `CONCURRENTLY` gibi kilitsiz yollar var) maliyetini önceden bilmek, tasarımın parçasıdır. Şema, ilk hali değil, evrimi düşünülerek tasarlanır.

**Aşırı-mühendislik: gelmeyecek esneklik için karmaşıklık.** Ters yöndeki hata da gerçektir. Henüz tek ülkede çalışan bir uygulamaya çok-para-birimli, çok-dilli, çok-kiracılı (multi-tenant) devasa bir şema kurmak, hiç gelmeyen bir geleceğe bugünün hızını feda etmektir. Pro dengeyi domain bilgisiyle kurar: "çoğullaşma neredeyse kesin" olanı bugünden ayır, "belki bir gün" olanı YAGNI (You Aren't Gonna Need It) ile ertele. İkisi arasındaki fark tecrübe ve domaini gerçekten anlamaktır.

## 5. Araçlar ve saha notları

**`EXPLAIN ANALYZE` — en önemli araç.** Bir sorgunun gerçekte nasıl çalıştığını (indeks kullanıyor mu, sequential scan mı yapıyor, join sırası ne, kaç satır tarıyor) gösterir. Denormalize etme kararı vermeden önce mutlaka bu çıktıya bakarım. "Yavaş" bir sorgunun çoğu zaman çözümü şema değişikliği değil, eksik bir indekstir. Şemayı bozmadan önce planı oku.

**Şema migration araçları (Flyway, Liquibase, Alembic, Django/Rails migrations vb.).** Şema değişikliğini asla elle canlı veritabanında yapmam. Her değişiklik versiyonlanmış, geri-alınabilir (down migration'lı), kod incelemesinden geçmiş bir migration dosyasıdır. Altın kural: **her migration hem ileri hem geri çalışabilmeli** ve büyük tablolarda kilitleme davranışı önceden bilinmeli. "Genişlet-daralt" (expand-contract) deseni: önce yeni kolonu ekle (expand), kod iki durumu da yazacak şekilde deploy et, veriyi taşı, sonra eski kolonu kaldır (contract). Bu, sıfır-kesinti (zero-downtime) şema değişiminin temel tekniğidir.

**`pg_stats` / veritabanı istatistikleri ve `pg_stat_user_tables`.** Hangi tablo büyüyor, hangi indeks kullanılmıyor (ölü indeks yazma maliyeti getirir ama kimseye fayda sağlamaz), hangi tabloda sequential scan patlıyor — bunları izlerim. Kullanılmayan indeksi silmek, kullanılmayan kolonu temizlemek de veri modeli bakımının parçasıdır.

**Kısıt (constraint) testleri.** Şemanın doğruluğunu iddia ediyorsam, kanıtlarım. Negatif adet `INSERT`'i reddediliyor mu, çift e-posta `UNIQUE` kısıtına takılıyor mu, silinen üst kayıt alt kayıtları doğru davranışla (cascade/restrict) etkiliyor mu — bunları entegrasyon testinde gerçek veritabanına (in-memory sahte değil, mümkünse aynı motorun bir konteyneri, Testcontainers gibi) karşı çalıştırırım. SQLite'a karşı test edip PostgreSQL'e deploy etmek, farklı tip/kısıt davranışları yüzünden sahte güven verir.

**`jsonb`'i disiplinle kullanmak.** Modern ilişkisel veritabanlarında `jsonb` güçlü bir kaçış valfidir — gerçekten yapısız/değişken veri için. Ama tuzağı şudur: her şeyi `jsonb`'e atıp "şemasız hızlıyım" demek, aslında şemayı doğrulanmamış ve indekslenmemiş hale getirmektir. Kuralım: çekirdek, sorgulanan, kısıtlanan alanlar gerçek kolon olur; yalnızca uçtaki, öngörülemeyen, nadiren sorgulanan veri `jsonb`'e gider. `jsonb` içindeki bir alanı sürekli `WHERE` ile filtreliyorsam, o alan aslında kolon olmalıydı (ya da en azından ifade indeksi ister).

**Domain uzmanıyla konuşmak — en yüksek getirili "araç".** En iyi veri modeli aracı bir sorgu profilcisi değil, iş tarafındaki insana sorduğun doğru sorulardır: "Bir müşterinin aynı anda iki aktif aboneliği olabilir mi?", "Bir fatura kesildikten sonra kalemi değişir mi, yoksa iptal-yeniden mi kesilir?", "Bu tutar hangi para biriminde, kur ne zaman kilitlenir?" Bu soruların cevapları, kardinaliteyi, değişmezliği ve tip kararlarını doğrudan belirler. Yanlış veri modellerinin ezici çoğunluğu teknik cehaletten değil, domaini yeterince sorgulamamaktan doğar.

### Kapanış: hangi belirtide hangi yöne giderim (özet karar refleksleri)

- Bir tabloda sürekli `NULL` görüyorsam → gizli bir alt-tip var, ayır.
- Bir metin kolonunda tekrar eden sabit değerler görüyorsam → referans tablo + FK, serbest metni bırak.
- Finansal/hukuki bir kaydın değeri sonradan değişebilen bir referansa bağlıysa → o değeri sipariş/işlem anında dondur (snapshot).
- "Bir-e-bir" bir ilişki ama çoğullaşma domain açısından muhtemel → bugünden ayrı tabloya çıkar.
- Sorgu yavaş → önce `EXPLAIN ANALYZE` ve indeks, denormalizasyon en son.
- "Esnek olsun" diye EAV/her-şey-jsonb düşünüyorsam → dur, çekirdek alanları gerçek kolonla modelle, esnekliği yalnızca uca uygula.
- Para → asla `float`, her zaman `decimal`/tamsayı-kuruş.
- Zaman → UTC `timestamptz` sakla, görüntüde çevir.
- Kimlik → iç `bigint`, dış tahmin-edilemez `uuid/ulid`; doğal anahtarı PK yapma.
- Her şema kararında → "50 milyon satırda migration nasıl olur" diye sor.

Veri modeli tasarımı, kod yazmaktan çok yargı işidir. Doğru yapıldığında sistemin geri kalanı üstüne huzurla oturur; yanlış yapıldığında her yeni özellik biraz daha acı verir. En pahalı ders şudur: veri modeli, veritabanı bilgisiyle değil, domaini derinlemesine anlamakla iyi tasarlanır. Şema, iş kurallarının taşa kazınmış halidir — o yüzden taşı yontmadan önce kuralı gerçekten anla.
