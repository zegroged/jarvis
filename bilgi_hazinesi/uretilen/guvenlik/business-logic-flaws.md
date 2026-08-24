# İş Mantığı Zafiyetleri (Business Logic Flaws)

## Tanım

İş mantığı zafiyetleri (business logic flaws), bir uygulamanın **teknik olarak doğru çalıştığı** ama **iş kurallarını yanlış uyguladığı** güvenlik açıklarıdır. Kod bir SQL injection ya da buffer overflow barındırmaz; her fonksiyon tam da yazıldığı gibi çalışır. Sorun, uygulamanın *ne yapması gerektiği* ile *saldırganın onu ne yapmaya zorlayabildiği* arasındaki boşluktadır.

Bunu ayıran temel özellik şudur: klasik bir zafiyet (örneğin XSS) uygulamanın **beklenmeyen bir girdiyi** yanlış işlemesinden doğar. İş mantığı zafiyeti ise çoğu zaman **tamamen geçerli, biçimsel olarak kusursuz girdilerin** iş akışının tasarımcısının hiç düşünmediği bir sırada ya da kombinasyonda gönderilmesinden doğar. Bir e-ticaret sitesinde sepete `-5` adet ürün eklemek, kupon kodunu 200 kez peş peşe uygulamak, ödeme adımını atlayıp doğrudan "sipariş onaylandı" sayfasına gitmek — bunların hepsi geçerli HTTP istekleridir. Sunucu her birini ayrı ayrı doğru işler. Yıkıcı olan, bunların **bütünüdür**.

Bu yüzden iş mantığı zafiyetleri, otomatik güvenlik tarayıcılarının en zorlandığı sınıftır. Tarayıcı "bu alana `<script>` sokarsam ne olur" diye deneyebilir ama "bu kullanıcı normalde 3 adımda yapması gereken işlemi 2 adımda yaparsa şirket para kaybeder mi" sorusunu soramaz — çünkü bu soru **uygulamanın iş amacını anlamayı** gerektirir.

## Kök Neden: Neden Böyle Oluyor?

İş mantığı zafiyetlerinin kökü tek bir yanlış varsayımda toplanır: **geliştirici, kullanıcının uygulamayı kendi tasarladığı "mutlu yol" (happy path) üzerinden kullanacağını sanır.**

Geliştirici zihninde bir akış vardır: kullanıcı ürünü seçer → sepete ekler → adres girer → ödeme yapar → onay alır. Kod bu sırayı varsayarak yazılır. Her adım, bir önceki adımın *zaten doğru şekilde tamamlandığını* varsayar. Ödeme sayfası "sepette geçerli ürünler var" varsayar; onay sayfası "ödeme başarılı oldu" varsayar. Bu varsayımlar **istemci tarafındaki akışa** güvenilerek yapılır — oysa saldırgan istemci değil, doğrudan sunucuya konuşur.

Kök nedeni birkaç katmanda açabiliriz:

1. **Durum (state) sunucuda değil, akışta tutulur.** Uygulama, "kullanıcı hangi adımda?" bilgisini formun gizli alanlarında, URL parametrelerinde ya da istemci tarafı JavaScript'te tutar. Saldırgan bu istemci tarafı durumu istediği gibi değiştirebildiği için, sunucu yanlış bir gerçekliğe inandırılabilir.

2. **Doğrulama yanlış katmanda yapılır.** "Bu kupon zaten kullanıldı mı?", "Bu kullanıcı bu işlemi yapmaya yetkili mi?", "Bu miktar mantıklı mı?" kontrolleri ya sadece istemcide (kolayca atlanır) ya da bir sonraki adıma bırakılmış (hiç ulaşılamayabilir) olur.

3. **İşlemler atomik değildir.** Bir "kontrol et, sonra uygula" (check-then-act) dizisi arasındaki mikrosaniyelik boşluk, eşzamanlı isteklerle sömürülebilir. Bu, aşağıda ayrıntılandıracağımız **race condition**'ın temelidir.

4. **Örtük güven zincirleri.** "Kullanıcı zaten şu ekranı gördüyse yetkisi vardır" gibi çıkarımlar. Ekranı görmek, arka uçta bir yetki kaydı oluşturmaz.

Özetle: iş mantığı zafiyeti, **kodun değil, kod hakkındaki varsayımların** açığıdır. Bu yüzden en tehlikeli olanıdır — çünkü kod incelemesinde "yanlış" görünen hiçbir satır yoktur.

---

## Odak 1: Akış Atlama (Flow Bypass / Step Skipping)

### Çalışma Mantığı

Çok adımlı işlemler (kayıt, ödeme, iki faktörlü doğrulama, onay süreçleri) mantıksal bir **durum makinesi** (state machine) olarak tasarlanır: A → B → C → D. Akış atlama zafiyeti, saldırganın B ve C'yi atlayıp doğrudan A'dan D'ye geçebilmesidir. Bu mümkün olur çünkü sunucu her adımda "önceki adımlar gerçekten tamamlandı mı" diye **sunucu tarafında saklanan bir gerçeğe** bakmaz; bunun yerine isteğin kendisinin (URL, parametre, çerez) "doğru adımdayım" iddiasına inanır.

### Somut Örnek

Klasik bir örnek çok adımlı bir ödeme akışıdır:

- `POST /sepet/dogrula`
- `POST /odeme/basla`
- `POST /odeme/onayla`
- `GET  /siparis/tamamlandi?ref=...`

Geliştirici, kullanıcının bu URL'leri sırayla ziyaret edeceğini varsayar. Saldırgan ise doğrudan `GET /siparis/tamamlandi?ref=...` isteğini gönderir. Eğer bu son uç nokta, ödemenin gerçekten alındığını bir **ödeme sağlayıcısı doğrulaması** üzerinden kontrol etmiyorsa, saldırgan hiç para ödemeden siparişi "tamamlanmış" olarak işaretletebilir.

İkinci klasik örnek 2FA atlamadır: kullanıcı adı + parola doğru girildiğinde uygulama `/2fa-dogrula` sayfasına yönlendirir. Ama oturum çerezi (session cookie) parola doğrulandığı anda **tam yetkili** olarak verilmişse, saldırgan `/2fa-dogrula` sayfasını hiç ziyaret etmeden doğrudan `/panel` gibi korumalı bir sayfaya giderek 2FA'yı tamamen atlayabilir. Buradaki hata: oturum "yarı doğrulanmış" bir durumda tutulmalıydı; parola doğru diye tam yetki verilmemeliydi.

### Sömürü / İstismar Mantığı

Saldırganın yaklaşımı yöntemseldir:
1. **Normal akışı bir kez baştan sona çalıştırıp** tüm istekleri (bir proxy ile, örneğin araya giren bir proxy aracı kullanarak) kaydeder.
2. Adımları haritalar ve her isteğin **bir öncekine bağımlılığını** test eder.
3. Ara adımları teker teker atlayarak son adıma sıçramayı dener. "Onay" ya da "başarı" adımını doğrudan çağırmak en yüksek getirili denemedir.
4. Parametrelerle oynar: `adim=3` yerine `adim=5`, `durum=beklemede` yerine `durum=onaylandi`.

### Savunma

- **Sunucu tarafında durum makinesi zorunlu kıl.** Her isteğin başında, sunucuda saklanan oturum durumunu oku: "Bu kullanıcı gerçekten B ve C adımlarını tamamladı mı?" Tamamlamadıysa isteği reddet. Durum, istemcinin gönderdiği hiçbir parametreye değil, yalnızca sunucudaki kayda dayanmalı.
- **Son adımı, kritik ön koşulun *kendisini* yeniden doğrulayarak koru.** "Sipariş tamamlandı" sayfası, ödemenin gerçekten alındığını ödeme sağlayıcısına sorarak teyit etmeli; istemcinin "ödedim" demesine güvenmemeli.
- **2FA gibi durumlarda oturuma açık bir "doğrulama seviyesi" bayrağı koy** (`mfa_completed = false`). Korumalı kaynaklar bu bayrağı kontrol etsin.

---

## Odak 2: Yarış Durumu (Race Condition / TOCTOU)

### Çalışma Mantığı

Yarış durumu, iş mantığı zafiyetlerinin en sinsi ve en güçlü sınıfıdır. Kökü **TOCTOU** (Time-Of-Check to Time-Of-Use) sorunudur: uygulama bir koşulu **kontrol eder** (check), sonra bu kontrole dayanarak bir **işlem yapar** (act) — ama bu iki adım arasında atomik olmayan bir boşluk vardır. Eğer saldırgan bu boşluğun içinde ikinci (üçüncü, yüzüncü) bir eşzamanlı istek sıkıştırabilirse, tüm istekler kontrolü *aynı anda* geçer ve işlemi *aynı başlangıç durumuna* dayanarak yapar.

Neden böyle oluyor? Çünkü geliştirici kodu **sıralı (sequential)** düşünür:

```
bakiye = hesabi_oku()          # bakiye = 100
if bakiye >= 100:              # kontrol: geçer
    urunu_ver()
    bakiye = bakiye - 100      # bakiye = 0
    hesabi_yaz(bakiye)
```

Bu kod tek başına çalışırsa kusursuzdur. Ama aynı anda gelen 10 istek, `hesabi_oku()` satırını **hepsi bakiye 100 iken** çalıştırırsa, 10'u da `if` kontrolünü geçer, 10'u da ürünü verir. Sonuçta kullanıcı 100 birim bakiye ile 1000 birimlik ürün almış olur. Bakiye sonunda `-900` bile olabilir.

### Somut Örnekler

- **Hediye çeki / kupon çoklama:** Bir hediye çeki tek kullanımlıktır. Kullanıcı aynı çeki 50 hesaba/istekte eşzamanlı olarak uygular. "Bu çek kullanıldı mı?" kontrolü hepsinde henüz "hayır" iken geçer; sonra 50'si birden bakiyeyi yükler.
- **Para çekme / transfer:** 100 TL bakiyeli hesaptan 100 TL çekme isteği 20 kez paralel gönderilir; bakiye kontrolü hepsinde 100 TL görür.
- **Stok / sınırlı envanter:** "Kişi başı 1 adet" kampanyasında aynı ürünü aynı anda 100 kez sipariş etme.
- **Oy / puanlama / referans bonusu:** Bir kez verilmesi gereken referans bonusunun eşzamanlı isteklerle defalarca tetiklenmesi.

### Sömürü / İstismar Mantığı

Modern web'de bu saldırının kilit tekniği, isteklerin sunucuya **neredeyse tam aynı anda** ulaşmasını sağlamaktır. HTTP/2 üzerinde birden çok isteği **tek bir TCP paketinde** göndererek (single-packet attack olarak bilinen yaklaşım) ağ jitter'ini büyük ölçüde eleyip mikrosaniye seviyesinde eşzamanlılık elde edilebilir. Amaç, tüm isteklerin sunucuda "kontrol" aşamasını "uygulama" aşaması başlamadan geçirdiği o dar pencereyi yakalamaktır. Saldırgan tek bir isteğin başarılı olmasına değil, **paralel isteklerden bir kaçının** kontrolü aynı başlangıç durumuyla geçmesine ihtiyaç duyar.

### Savunma

Race condition'a karşı savunmanın özü **atomiklik** ve **serileştirme**dir. "Kontrol et sonra uygula" boşluğunu kapatmak gerekir:

- **Veritabanı seviyesinde atomik işlemler kullan.** Bakiye düşürmeyi uygulama kodunda `oku → hesapla → yaz` şeklinde değil, tek bir atomik güncellemeyle yap: `UPDATE hesap SET bakiye = bakiye - 100 WHERE id = ? AND bakiye >= 100`. Bu ifade, koşulu ve güncellemeyi **tek atomik adımda** birleştirir; etkilenen satır sayısı 0 ise işlem başarısızdır. Böylece "kontrol" ile "uygulama" arasında sömürülebilir boşluk kalmaz.
- **Pessimistic locking (kötümser kilitleme):** İlgili satırı işlem boyunca kilitle (örneğin `SELECT ... FOR UPDATE`) ki eşzamanlı istekler sıraya girsin.
- **Optimistic locking (iyimser kilitleme):** Kayda bir sürüm numarası (version) ekle; güncelleme sırasında sürüm değişmişse işlemi reddet ve tekrar dene.
- **Idempotency (idempotentlik) anahtarları:** Her mantıksal işleme benzersiz bir anahtar ata; aynı anahtarla gelen ikinci istek yeni bir etki yaratmadan ilk sonucu döndürsün. Özellikle ödeme ve kupon kullanımında kritiktir.
- **Benzersizlik kısıtları:** "Bir kullanıcı bir kuponu bir kez kullanabilir" kuralını veritabanı seviyesinde `UNIQUE(kullanici_id, kupon_id)` kısıtıyla zorla. Eşzamanlı ikinci ekleme, veritabanı tarafından reddedilir.
- **Dağıtık sistemlerde** tek bir veritabanı satırına güvenemiyorsan dağıtık kilit (distributed lock) mekanizmaları gerekir.

Kritik nokta: uygulama kodundaki `if` kontrolleri race condition'ı **çözmez**. Güvenlik, işlemin atomik olarak yürütüldüğü **tek doğruluk kaynağında** (genelde veritabanı) sağlanmalıdır.

---

## Odak 3: Negatif Değer ve Tam Sayı Sınırı İstismarı

### Çalışma Mantığı

Geliştiriciler, bir sayının anlamını (miktar, fiyat, adet) doğrularken çoğu zaman yalnızca **üst sınırı** ya da **biçimi** kontrol eder; **negatif değerleri** ve **taşma (overflow) sınırlarını** unutur. Çünkü "hiç kimse -5 adet ürün sipariş etmez" varsayımı zihinde o kadar doğaldır ki kod bunu hesaba katmaz. Oysa saldırgan tam da bu doğal varsayımı hedef alır.

Negatif değerin yıkıcılığı, çoğu iş mantığında sayıların **aritmetiğe** girmesindendir. Bir toplam hesaplanırken `fiyat × adet` yapılır. Adet negatifse toplam negatife döner. Bu negatif toplam başka bir kalemle toplandığında **genel toplamı düşürür** — hatta bakiyeyi artırabilir.

### Somut Örnekler

- **Negatif miktarla iade/geri ödeme:** Bir para transferinde `-500` TL göndermek, mantık ters çalışırsa parayı *karşıdan çekip* saldırgana aktarabilir.
- **Sepette negatif adet:** Sepete `+2` pahalı ürün ve `-3` ucuz olmayan ürün ekleyip genel toplamı sıfıra ya da eksiye düşürmek. Ödeme tutarı `0` ya da negatifse ödeme adımı atlanabilir.
- **Kupon/indirim ile toplamı eksiye çekmek:** İndirim tutarı fiyattan büyükse ve alt sınır kontrolü yoksa, "ödenecek tutar" negatif olur ve sisteme göre bu kullanıcı bakiyesine iade olarak yansıyabilir.
- **Integer overflow (tam sayı taşması):** Çok büyük bir adet (örneğin 32-bit tam sayının üst sınırına yakın) gönderildiğinde, `fiyat × adet` çarpımı veri tipinin sınırını aşıp **sarmalayarak (wrap-around)** küçük hatta negatif bir sayıya dönebilir. Böylece devasa bir sipariş, çok küçük bir tutara mal olur.

### Sömürü / İstismar Mantığı

Saldırgan sayısal alanlara sistematik olarak şu değerleri dener: `-1`, `0`, çok büyük pozitif sayılar, ondalıklı değerler (`0.001`), bilimsel gösterim, ve tip sınırına yakın değerler. Her birinin **nihai tutar** ve **bakiye** üzerindeki etkisini gözler. Özellikle birden fazla kalemi birleştirerek (pozitif + negatif) net sonucu manipüle etmeye çalışır. Amaç: ödeme tutarını sıfıra/eksiye çekmek ya da bir bakiyeyi haksız yere artırmak.

### Savunma

- **Beyaz liste mantığıyla doğrula (allow-list, deny-list değil):** "Adet, `1` ile `makul_ust_sinir` arasında bir *tam sayı* olmalı" kuralını sunucuda zorla. Sadece "sayı mı?" diye sorma; **aralık** ve **işaret** (sign) kontrolü yap.
- **Negatif değerleri açıkça reddet.** Miktarların doğası gereği pozitif olması gereken her alanda `deger > 0` kontrolü olsun.
- **İş kurallarının değişmezlerini (invariants) sunucuda doğrula:** "Ödenecek tutar asla negatif olamaz", "Sepet toplamı ≥ 0", "İndirim ≤ ara toplam" gibi kuralları son hesaplamadan sonra bir kez daha teyit et.
- **Taşmaya dayanıklı tipler kullan.** Parasal değerlerde kayan noktalı (floating point) sayılardan kaçın; tam sayı tabanlı kuruş/cent ya da keyfi hassasiyetli decimal tipleri kullan. Çarpımların taşma sınırını aşmadığını kontrol et.
- **Doğrulamayı işe en yakın katmanda tekrar et.** İstemci doğrulaması yalnızca kullanıcı deneyimi içindir; güvenlik değildir.

---

## Odak 4: Otomasyon Güçlüğü (Otomatik Tespitin Zorluğu)

### Neden Otomatikleştirmek Zor?

Bu, iş mantığı zafiyetlerinin en ayırt edici yönüdür ve ayrı bir başlığı hak eder: **iş mantığı zafiyetleri, otomatik araçlarla neredeyse hiç bulunamaz.** Nedenini anlamak, savunmayı da anlamak demektir.

Otomatik bir tarayıcı iki şeyi bilir: (1) yaygın zafiyet imzaları (XSS payload'ları, SQL injection kalıpları), (2) "hatalı" bir yanıtın nasıl göründüğü (500 hatası, veritabanı hata mesajı). İş mantığı zafiyetlerinde bunların **ikisi de yoktur**:

1. **Zafiyetin bir imzası yoktur.** `-5` sayısı, `<script>` gibi evrensel olarak "kötü" bir girdi değildir. Bir bağlamda tamamen normal (sıcaklık `-5` derece), başka bir bağlamda felakettir (adet `-5`). Tarayıcı bağlamı bilmez.

2. **"Doğru" ile "yanlış" davranışı ayırt etmek için uygulamanın *amacını* bilmek gerekir.** Tarayıcı, `HTTP 200 OK` dönen ve "Siparişiniz alındı" yazan bir yanıtı **başarı** sayar. Oysa o sipariş, ödeme atlanarak alınmış olabilir. Tarayıcının bakış açısından her şey yolundadır. Yalnızca **iş bağlamını bilen bir insan** "ama bu ücretsiz olmamalıydı" diyebilir.

3. **Sömürü, tekil bir istekte değil, isteklerin *dizisinde/kombinasyonunda* saklıdır.** Tarayıcılar tek tek istekleri fuzz'lar; "önce bunu, sonra şunu, sonra ilkini tekrar yaparsam" gibi durum bağımlı senaryoları kuramaz.

### Bu Durumun Sonuçları (Hem Saldırı Hem Savunma İçin)

**Saldırgan açısından:** İş mantığı zafiyetleri, otomatik savunmalardan (WAF, tarayıcı temelli tarama) doğal olarak kaçar. Bu yüzden manuel, yaratıcı, iş sürecini anlamaya dayalı testler yüksek getiri sağlar. Saldırgan "bu özelliğin arkasındaki iş kuralı ne, bu kuralı nasıl kırarım" diye düşünür.

**Savunan açısından:** Tam da otomatikleştirilemediği için bu zafiyetler **tasarım ve süreç** ile önlenmelidir, koddan sonra taranarak değil. Savunma stratejisi kaymalıdır:

- **Manuel güvenlik gözden geçirmeleri (manual review) ve tehdit modelleme (threat modeling)** vazgeçilmezdir. Her kritik iş akışı için "bu adım atlanırsa?", "bu değer negatifse?", "bu iki kez yapılırsa?", "bu farklı sırada yapılırsa?" soruları sistematik sorulmalı.
- **İş kuralları açıkça belgelenmeli ve *sunucu tarafı değişmezler* (invariants) olarak kodlanmalı.** "Bir kullanıcı bir siparişi yalnızca kendisi görebilir", "toplam negatif olamaz" gibi.
- **Kısmen otomatikleştirilebilir kısımlar:** Belirlenmiş iş kurallarına dayalı **özel yazılmış testler** (unit/integration testleri) ile "negatif adet reddediliyor mu?", "kupon iki kez kullanılabiliyor mu?" gibi bilinen sınıflar regresyon olarak korunabilir. Ayrıca eşzamanlılık için kasıtlı **yük/paralellik testleri** yazılarak race condition'lar yakalanabilir. Ama bunlar önce **insan tarafından tanımlanmış** kural gerektirir; kör tarama işe yaramaz.

---

## Yaygın Hatalar

Aşağıdaki hatalar, iş mantığı zafiyetlerinin ezici çoğunluğunun kökünde yatar:

- **İstemci tarafı doğrulamaya güvenmek.** JavaScript ile "adet 0'dan büyük olmalı" kontrolü yapıp sunucuda tekrar etmemek. Saldırgan istemciyi tamamen atlar (doğrudan API'ye istek atar); istemci doğrulaması yalnızca dürüst kullanıcı için vardır.
- **Durumu istemcide taşımak.** Fiyat, indirim tutarı, yetki seviyesi gibi kritik verileri gizli form alanlarında, URL'de ya da çerezde tutup sunucuda yeniden hesaplamamak/doğrulamamak.
- **"Kontrol et, sonra uygula" desenini atomik olmayan biçimde yazmak.** Race condition'ların birincil sebebi.
- **Yetkilendirmeyi görünürlükle karıştırmak.** "Kullanıcı bu butonu görmüyorsa bu işlemi yapamaz" varsaymak. Buton görünmese de API uç noktası açıktır; her istekte **sunucu tarafı yetki kontrolü** şart.
- **Sadece "mutlu yolu" test etmek.** Test senaryoları hep işlemin doğru sırada, makul değerlerle yapıldığını varsayar. Negatif, sıfır, aşırı büyük, sıra dışı, eşzamanlı senaryolar hiç test edilmez.
- **İş kurallarını hiç yazılı hale getirmemek.** Kural belgelenmemişse, doğrulanamaz. "Herkesin bildiği" örtük kurallar en kolay ihlal edilenlerdir.
- **Hata mesajlarıyla iş mantığını sızdırmak.** "Bu kupon zaten kullanıldı" vs "geçersiz kupon" gibi farklı mesajlar, saldırgana iş akışının iç durumunu haritalama imkanı verir.

## En İyi Pratikler

1. **Tek doğruluk kaynağı sunucudur.** Tüm kritik kararlar (fiyat, yetki, miktar, akış durumu, indirim) yalnızca sunucuda, istemciden gelen hiçbir veriye güvenilmeden hesaplanmalı ve doğrulanmalıdır. İstemcinin gönderdiği her sayıya "düşmanca" muamele et.

2. **İş kurallarını değişmezler (invariants) olarak kodla.** "Toplam ≥ 0", "bir kupon bir kez", "her adım öncekini gerektirir" gibi kuralları kodun içinde açık, test edilebilir kontroller haline getir. Bunları merkezi bir yerde topla; iş kuralı kodun her yanına dağılmışsa tutarlı korunamaz.

3. **Durum makinelerini sunucu tarafında zorla.** Çok adımlı akışlarda kullanıcının hangi adımda olduğunu sunucudaki oturumda tut; her adımda önceki adımların gerçekten tamamlandığını doğrula.

4. **Atomiklik ve idempotentlik tasarla.** Kritik işlemleri (ödeme, bakiye değişimi, tek kullanımlık kaynaklar) atomik veritabanı işlemleri, uygun kilitleme ve idempotency anahtarları ile koru. "Kontrol et sonra uygula" boşluğunu tasarım gereği ortadan kaldır.

5. **Girdileri beyaz liste ile doğrula.** Her sayısal alan için tip + işaret + aralık; her akış parametresi için izin verilen değerler kümesi. "Kötüyü ara" değil, "sadece iyiye izin ver" yaklaşımı.

6. **Tehdit modellemeyi iş akışına odakla.** Her kritik özellik için sistematik olarak dört soruyu sor: *Bu adım atlanabilir mi? Bu değer sınır dışına çıkabilir mi? Bu işlem eşzamanlı tekrarlanabilir mi? Bu sıra değiştirilebilir mi?* Bu dört soru, dört odak konumuzun (akış atlama, negatif değer, race, sıra manipülasyonu) doğrudan karşılığıdır.

7. **En az ayrıcalık ve açık yetkilendirme.** Her istek, her kaynak için "bu kullanıcı bunu yapmaya yetkili mi" sorusunu sunucuda sorsun. Görünürlüğü asla yetkilendirme yerine koyma.

8. **İş mantığını otomatik testlerle regresyona karşı koru.** İnsan bir kez zafiyet sınıfını tanımladıktan sonra, o kuralı doğrulayan birim/entegrasyon testleri ve eşzamanlılık testleri yaz. Böylece bulunan bir açık, gelecekte yeniden açılmaz.

9. **Derinlemesine savunma (defense in depth).** Tek bir kontrol katmanına güvenme. İstemci doğrulaması (deneyim için) + sunucu doğrulaması (güvenlik için) + veritabanı kısıtları (son savunma hattı) birlikte kullanılmalı.

---

### Kapanış

İş mantığı zafiyetlerinin özü tek cümlede toplanır: **uygulamanın kodu değil, kod hakkındaki varsayımlar açıktır.** Bu yüzden ne bir tarayıcı ne bir WAF onları güvenilir biçimde bulur; onları bulmanın ve önlemenin yolu, uygulamanın iş amacını anlayan bir zihnin "peki ya kullanıcı bunu yapması gerektiği gibi *yapmazsa*?" sorusunu her kritik akış için sistematik sormasından geçer. Akış atlama, race condition, negatif değer ve otomasyon güçlüğü — bunların hepsi aynı temel dersin farklı yüzleridir: **hiçbir varsayıma güvenme; her kritik kararı sunucuda, atomik olarak ve açıkça doğrula.**
