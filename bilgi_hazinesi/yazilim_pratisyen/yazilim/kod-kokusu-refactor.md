# Kod Kokuları ve Refactor Kararı — Saha Notları

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

"Kod kokusu" (code smell) terimi acemiye çoğu zaman yanlış öğretilir: sanki bir kural ihlali, bir doğru/yanlış tablosu gibi. Değil. Kod kokusu bir **belirtidir** — tıptaki ateş gibi. Ateş bir hastalık değildir; altta bir şey olduğunun işaretidir. Bazen zatürredir, bazen üç saat sonra geçen bir üşütmedir. Kokunun kendisi de öyle: bir yerde tasarımın gerçek ihtiyaçla uyuşmadığını **haber verir**, ama sana "hemen ameliyat ol" demez.

Refactor kararı tam da burada başlar. Refactor, davranışı değiştirmeden iç yapıyı iyileştirmektir — Fowler'ın klasik tanımı. Kritik nokta "davranışı değiştirmeden" kısmı: eğer bir bug düzeltiyorsan, yeni özellik ekliyorsan, performans için algoritma değiştiriyorsan, o refactor değildir. O başka bir iştir ve karışırsa ikisi de batar.

Bu iş ne zaman devreye girer? Üç gerçek tetikleyici vardır, kitap tanımı değil:

- **Değişiklik acısı.** Bir özelliği eklemek için beş dosyada aynı şeyi değiştirmen gerekiyorsa, kod sana "buranın yapısı yanlış" diyor. Refactor bu acıyı ödemek içindir.
- **Anlama acısı.** Kodu okuyup ne yaptığını anlamak 20 dakika sürüyorsa, her okuyan aynı vergiyi ödeyecek. Bu bileşik faizle büyür.
- **Kırılganlık.** Bir yeri değiştirdiğinde alakasız bir yer patlıyorsa, gizli bağımlılıklar var demektir.

Bu üçü yoksa — kod çirkin ama çalışıyor, kimse dokunmuyor, değişmiyor — refactor **çoğu zaman israftır**. Bunu en baştan söylüyorum çünkü kariyerimde gördüğüm en pahalı hataların bir kısmı "temizlik" adı altında çalışan, dokunulmayan, riski sıfır olan kodun kurcalanıp bozulmasıydı.

## 2. Metodoloji ve karar ağacı — asıl değer burada

Pro bir belirti gördüğünde refactor'a atlamaz. Bir dizi soruyu sırayla geçirir. Bu sırayı yıllar içinde acı çekerek öğrenirsin; ben doğrudan vereyim.

### Adım 0: "Bu kod değişiyor mu?" — her şeyden önce bu

Refactor kararının tek en önemli girdisi kod kalitesi değil, **değişim frekansıdır**. Git'te `git log --format= --name-only | sort | uniq -c | sort -rn` çalıştır. Son bir yılda 40 kez değişen dosya ile 2 kez değişen dosyaya aynı gözle bakamazsın.

Karar ağacının kökü budur:
- **Sık değişen + çirkin** → refactor'un en yüksek getirili olduğu yer. Buraya yatırım yap.
- **Sık değişen + temiz** → koru, bozma.
- **Nadir değişen + çirkin** → **dokunma.** Çirkinliği "borç" olarak görme; faizi ödenmeyen borç borç değildir. Çalışıyorsa bırak.
- **Nadir değişen + temiz** → zaten sorun yok.

Acemi tüm çirkin kodu eşit görür ve hepsini düzeltmek ister. Pro, çirkinliğin *nerede* olduğuna bakar. Michael Feathers'ın deyimiyle: değişim ve karmaşıklığın kesiştiği yer, ilgini hak eden tek yerdir.

### Adım 1: "Belirti ne, altındaki hastalık ne?"

Kokuyu isimlendir ama isimde durma. Yaygın kokular ve altlarında **gerçekte** yatan şey:

- **Uzun fonksiyon (Long Method):** Genelde birden fazla soyutlama seviyesinin tek yere sıkışması. Hastalık: fonksiyon bir şey değil, üç şey yapıyor.
- **Tekrar (Duplication):** İki tür vardır ve bunları ayırmak kritik. **Gerçek tekrar** — aynı bilgi, aynı sebep, hep birlikte değişecek. **Tesadüfi tekrar** — bugün aynı görünüyor ama farklı sebeplerle var ve ayrı ayrı değişecek. İkincisini birleştirmek felakettir; buna aşağıda döneceğim.
- **Feature Envy:** Bir metod başka bir sınıfın verisine sürekli uzanıyor. Hastalık: davranış yanlış yerde duruyor.
- **Shotgun Surgery:** Tek bir kavramsal değişiklik için on yere dokunuyorsun. Hastalık: bir kavram koda dağılmış, tek yerde toplanması gerek.
- **Primitive Obsession:** Para `float`, e-posta `string`, tarih aralığı iki ayrı parametre. Hastalık: domain kavramları tip sistemine geçmemiş.
- **Data Clumps:** Aynı üç-dört parametre hep birlikte geziyor. Bunlar aslında isimsiz bir nesne.

Anahtar disiplin: **koku ismi teşhisin sonu değil başıdır.** "Uzun fonksiyon" demek "kısalt" demek değildir; neden uzadığını anlamak demektir.

### Adım 2: "Şimdi mi, sonra mı, hiç mi?"

Karar ağacının en çok atlanan dalı. Üç seçenek var, acemi sadece "şimdi düzelt"i görür:

1. **Şimdi refactor et** — ancak dokunacağın özellik/bug tam bu bölgede geçiyorsa. "Kampçı kuralı": girdiğin alanı geldiğinden biraz temiz bırak. Ama *biraz*. Uğradığın için oradasın.
2. **Sonraya işaretle** — kokuyu gördün ama şimdi ilgisiz. `// TODO` yeterli değil; bir issue aç, *neden* değişmesi gerektiğini ve *hangi değişikliğin* bunu tetikleyeceğini yaz. Bağlamsız TODO çürür.
3. **Hiç dokunma** — Adım 0'daki "nadir değişen" durumu. Bilinçli karar olarak bırak.

### Adım 3: "Testim var mı?" — geçilmez kapı

Bu pazarlık edilemez. Refactor'un tanımı "davranışı değiştirmeden"dir; davranışı **doğrulayamıyorsan** değiştirmediğini nasıl bileceksin? Test yoksa iki yol:

- Önce **karakterizasyon testi** yaz (characterization test): kodun *şu an ne yapıyorsa* onu — doğru olduğunu değil, *mevcut* davranışı — kilitle. Feathers'ın "Legacy Code" kitabının bel kemiği budur. Bu testler kodun "doğru" olduğunu iddia etmez; "değişmediğini" garanti eder.
- Test yazmak imkânsızsa (kod test edilemez şekilde örülmüşse), o zaman ilk refactor **test edilebilir hale getirmektir** — bağımlılığı bir seam'den ayırmak. Ve bunu en küçük, en riskli adımla yap.

Test olmadan yapılan refactor refactor değildir; kumar oynamaktır. Kariyerimde "sadece isim değiştiriyordum" diye başlayıp prodüksiyonu düşüren insanlar gördüm.

### Adım 4: Küçük adımlar ve takaslar

Refactor bir "büyük yeniden yazım" değildir. Büyük yeniden yazımlar (rewrite) genelde başarısız olur çünkü çalışan sistemin içine gömülü binlerce görünmez kararı yeniden keşfetmen gerekir. Pro bunun yerine **küçük, davranış-koruyan adımlar** atar ve her adımdan sonra testleri çalıştırır. IDE'nin otomatik refactor'ları (rename, extract method) tam da bu yüzden altındır: makine garantili doğru dönüşüm yapar.

Ana takaslar, her zaman kafanda tut:
- **Şimdiki hız vs. gelecekteki hız.** Refactor bugünü yavaşlatır, yarını hızlandırır — *eğer* o kod yarın değişecekse. Değişmeyecekse net kayıp.
- **DRY vs. gevşek bağlılık.** İki kodu birleştirip tekrarı yok edersen, onları *birbirine bağlamış* olursun. Bilgi gerçekten aynıysa bu doğru. Değilse, tekrarı silerken yeni bir bağımlılık yarattın — ki bu tekrardan çok daha pahalıdır.
- **Soyutlama vs. dolaysızlık.** Her soyutlama bir dolaylama katmanıdır; okuyanın zihninde bir sıçrama daha demektir. Yanlış soyutlama, kopyala-yapıştırdan daha kötüdür çünkü onu geri sökmek zordur.

## 3. Gerçek kod üzerinden yürüyüş

Somut bir senaryo. Bir e-ticaret sisteminde sipariş toplamını hesaplayan bir fonksiyon. Dil bağımsız anlatacağım ama gerçek bir örnek — bunun binlerce varyantını sahada gördüm.

### Başlangıç: kokan kod

```
function siparisiIsle(siparis):
    toplam = 0
    for kalem in siparis.kalemler:
        toplam += kalem.fiyat * kalem.adet

    # indirim
    if siparis.musteri.tip == "VIP":
        toplam = toplam * 0.9
    elif siparis.musteri.tip == "STANDART":
        if toplam > 500:
            toplam = toplam * 0.95

    # kargo
    if toplam < 150:
        toplam = toplam + 30
    else:
        toplam = toplam + 0

    # vergi
    toplam = toplam + (toplam * 0.20)

    # kayıt
    veritabani.kaydet(siparis.id, toplam)
    epostaGonder(siparis.musteri.eposta, "Siparişiniz alındı: " + toplam)

    return toplam
```

Kokular listesi (teşhis):
- **Uzun fonksiyon / karışık soyutlama seviyeleri:** hesaplama, kargo, vergi, DB kaydı ve e-posta gönderimi hep aynı yerde. En üst seviye iş kuralı ile en alt seviye yan etki (I/O) iç içe.
- **Magic number'lar:** `0.9`, `0.95`, `500`, `150`, `30`, `0.20`. Bunların her biri bir iş kuralı ama koda gömülü, isimsiz.
- **Yan etki gizli:** Fonksiyon "işle" diyor ama aynı zamanda DB'ye yazıyor ve e-posta atıyor. İsmi yalan söylüyor.
- **Test edilemez:** Bu fonksiyonu test etmek için gerçek DB ve e-posta sunucusu gerekiyor. Sadece "VIP indirimi doğru mu?" diye sormak için bile.

### Teşhis: en zararlı koku hangisi?

Acemi buraya bakıp "magic number'ları sabit yapayım" der — en görünür ama **en az önemli** sorun. Pro şunu sorar: bu fonksiyon neden değişir? Yanıt: kargo kuralı değişince, vergi oranı değişince, indirim politikası değişince, e-posta metni değişince, DB şeması değişince. **Beş farklı sebep, tek fonksiyon.** Bu Single Responsibility ihlalidir ve asıl hastalık budur. Yan etkilerin (DB, e-posta) saf hesaplamayla karışması da test edilemezliğin kaynağı.

O yüzden ilk hamle magic number değil, **saf hesaplamayı yan etkilerden ayırmak.**

### Adım adım düzeltme

Önce — test yazamadığımız için — I/O'yu dışarı iteriz ki saf kısmı test edebilelim:

```
# SAF: sadece hesap, hiç yan etki yok. Test edilebilir.
function siparisToplamiHesapla(siparis) -> Money:
    araToplam = kalemToplami(siparis.kalemler)
    indirim   = indirimUygula(araToplam, siparis.musteri.tip)
    kargo     = kargoUcreti(indirim)
    return vergiEkle(indirim + kargo)

function kalemToplami(kalemler) -> Money:
    return sum(k.fiyat * k.adet for k in kalemler)

function indirimUygula(tutar, musteriTipi) -> Money:
    match musteriTipi:
        VIP:      return tutar * (1 - VIP_INDIRIM_ORANI)
        STANDART: return tutar > STANDART_INDIRIM_ESIGI
                         ? tutar * (1 - STANDART_INDIRIM_ORANI)
                         : tutar
        default:  return tutar

function kargoUcreti(tutar) -> Money:
    return tutar < UCRETSIZ_KARGO_ESIGI ? SABIT_KARGO_UCRETI : 0

function vergiEkle(tutar) -> Money:
    return tutar * (1 + KDV_ORANI)
```

Yan etkiler ayrı bir katmana, iş akışına taşınır:

```
# YAN ETKİLİ KABUK: ince, hesabı çağırır, sonra I/O yapar.
function siparisiIsle(siparis):
    toplam = siparisToplamiHesapla(siparis)   # saf
    veritabani.kaydet(siparis.id, toplam)      # yan etki
    epostaGonder(siparis.musteri.eposta, siparisOnayMetni(toplam))
    return toplam
```

Ne kazandık?
- `siparisToplamiHesapla` artık **DB'siz, e-postasız** test edilebilir. "VIP + 600 TL + kargo eşiği" gibi onlarca senaryoyu milisaniyede test edersin.
- Her iş kuralının bir **ismi** var. `UCRETSIZ_KARGO_ESIGI` gören biri ne olduğunu anlar; `150` gören anlamaz.
- Kargo kuralı değişince sadece `kargoUcreti` değişir. Shotgun surgery bitti.
- Üst seviye `siparisToplamiHesapla` bir **hikâye** gibi okunuyor: ara toplam, indirim, kargo, vergi. Soyutlama seviyeleri hizalandı.

### Dikkat: bir tuzak

`if toplam < 150 ... else toplam + 0` gibi ölü dalları temizledik. Ama daha kritik bir nokta: para hesabında `float` kullanılıyorsa (`toplam * 0.9`), refactor'un asıl işi **davranışı korumak** olduğundan bunu *bu refactor'da* değiştirmemelisin — `float`→`Decimal` değişimi davranışı değiştirir (yuvarlama farkları), o ayrı bir görevdir ve ayrı test ister. Refactor ile bug-fix'i karıştırma disiplini tam da budur. Gördüğün bir hatayı not al, ayrı commit'te düzelt.

## 4. Acemi vs. pro: tuzaklar ve gözden kaçanlar

**Tuzak 1: Yanlış DRY — tesadüfi tekrarı birleştirmek.**
Acemi iki kod bloğu benzer görününce hemen ortak bir fonksiyona çeker. Altı ay sonra iki iş kuralı farklı yönlere evrilir; ortak fonksiyona `if tip == A ... else ...` parametreleri eklenmeye başlar. Bir yıl sonra o fonksiyon on parametreli, kimsenin anlamadığı bir canavardır. Sanchez'in ünlü sözü: **"biraz kopyalama, yanlış soyutlamadan ucuzdur."** Pro şu testi yapar: *bu iki kod aynı sebeple mi değişecek?* Evetse birleştir. Emin değilsen bekle — tekrarı görmek kolaydır, yanlış soyutlamayı geri sökmek zordur.

**Tuzak 2: Refactor ile davranış değişikliğini karıştırmak.**
En pahalı hata. Aynı PR'da hem "yapıyı temizledim" hem "şu bug'ı düzelttim" hem "şu özelliği ekledim" olunca, bir şey patladığında hangisinin yaptığını bilemezsin. Ve mutlaka patlar. Kural: bir commit ya tamamen davranış-koruyandır (refactor) ya da davranış değiştirir. İkisi asla aynı commit'te olmaz. Review yaparken "bu diff'te davranış değişti mi?" sorusuna net "hayır" diyebilmelisin.

**Tuzak 3: Erken soyutlama / spekülatif genellik.**
"İleride lazım olur" diye eklenen interface'ler, "gelecekte başka ödeme sağlayıcısı gelirse" diye kurulan strateji desenleri. YAGNI. Gelecek genelde tahmin ettiğin gibi gelmez; kurduğun soyutlama yanlış eksende olur ve gerçek ihtiyaç geldiğinde hem soyutlamayı sökmen hem yenisini kurman gerekir. Pro **üçüncü tekrarı görene kadar** soyutlamayı erteler ("rule of three"). İki örnek soyutlama için yeterli veri değildir.

**Tuzak 4: Metrik fetişizmi.**
"Fonksiyon 10 satırı geçmesin", "cyclomatic complexity 5'in altında olsun". Bu metrikler *belirti göstergesidir*, hedef değil. 40 satırlık, düz, yukarıdan aşağı okunan, dallanması olmayan bir fonksiyon; 8 satırlık ama üç seviye iç içe callback'i olan bir fonksiyondan **çok daha iyidir**. Metriği optimize etmek için kodu beş minik fonksiyona bölüp okumayı zorlaştıran insanlar gördüm — buna "lasagna code" denir, her katmana bakmak için zıplarsın. Metriğe değil, "bunu altı ay sonra biri okuyunca anlar mı" sorusuna bak.

**Tuzak 5: Test olmadan büyük refactor.**
"Sadece isim değiştiriyorum, IDE yapıyor, ne olacak ki." Sonra IDE'nin görmediği bir string'de, bir reflection çağrısında, bir config dosyasında o isim geçer ve prodüksiyon sessizce yanlış davranır. Otomatik refactor bile %100 güvenli değildir; testin yoksa gözün kapalı yürüyorsun.

**Gözden kaçan 1: Kokunun kendisi değil, dağılımı.** Tek bir uzun fonksiyon problem değildir. Kod tabanının *her yerinde* aynı kokunun tekrarlaması bir sistemik tasarım sorununun işaretidir. Tek ağaca değil ormana bak.

**Gözden kaçan 2: "İyileştirdim" ama ölçmedin.** Refactor'un getirisi "kod daha güzel" değil, "sonraki değişiklik daha ucuz". Bunu sahiden test etmek istiyorsan: refactor'dan sonra gelen ilk özellik gerçekten daha kolay eklendi mi? Eklenmedi mi? Bu geri bildirim döngüsünü kuran çok az mühendis var.

**Gözden kaçan 3: Sosyal maliyet.** Büyük refactor, ekibin geri kalanının açık branch'lerini merge cehennemine sokar. Herkesin dokunduğu bir dosyayı bir Cuma öğleden sonra baştan aşağı yeniden düzenlersen, Pazartesi beş kişi rebase savaşı verir. Refactor'un zamanlaması teknik değil, sosyal bir karardır da. Pro büyük bir yapısal değişikliği önce ekibe haber verir, mümkünse açık PR'ları merge ettirir, sonra dokunur. Ayrıca dosya taşıma (move/rename) refactor'larını *ayrı* commit'te yapar ki review eden `git log --follow` ile geçmişi izleyebilsin — kod değişikliğiyle dosya taşımayı aynı commit'e koyarsan diff okunamaz hale gelir ve blame geçmişi kopar.

**Gözden kaçan 4: "Boy scout" kuralını abartmak.** Kampçı kuralı ("geldiğinden temiz bırak") iyidir ama sınırı vardır. Küçük bir bug fix için açtığın PR'a 300 satırlık "yolu geçmişken temizledim" refactor'u eklersen, review eden asıl değişikliği göremez, riski değerlendiremez ve ya körlemesine onaylar ya da haftalarca bekletir. Asıl değişiklik ile fırsatçı temizliği **ayrı PR'lara** böl. Küçük bir isim düzeltmesi yolun üstündeyse sorun yok; ama temizlik asıl işten büyükse, o artık "yolun üstünde" değildir, ayrı bir iştir.

## 5. Araçlar ve saha notları

**IDE otomatik refactor'ları** (IntelliJ, ReSharper, Rider, VS Code'un dil sunucuları): Rename, Extract Method/Variable, Inline, Move, Change Signature. Bunlar altındır çünkü AST üzerinde çalışır — string arama-değiştirme değil, dilin anladığı yapı üzerinde garantili dönüşüm. Elle yapabileceğin bir refactor'u IDE yapabiliyorsa, **elle yapma.** Ben "extract method"u manuel yapıp bir değişkeni dışarıda unutan insanlar gördüm.

**Test koşucusu — watch modu:** Refactor sırasında testleri sürekli çalışan bir watch modunda tut (jest --watch, pytest-watch, dotnet watch test, vb.). Her küçük adımdan sonra saniyeler içinde yeşil/kırmızı geri bildirim al. Refactor'un ritmi budur: değiştir → koş → yeşil → devam. Kırmızı olursa son adımı geri al, düşün.

**Version control disiplini:** Refactor'ları küçük, atomik, davranış-koruyan commit'ler olarak yap. `git commit -m "refactor: extract kargoUcreti"` — her biri tek başına derlenip testleri geçen commit'ler. Bir şey ters giderse `git bisect` ile tam hangi adımda bozulduğunu bulursun. Dev bir "büyük temizlik" commit'i debug edilemez.

**Coverage araçları — ama tuzağına düşme:** Coverage sana *hangi kodun test edilmediğini* söyler; refactor'a girmeden önce dokunacağın bölgenin kapsamını gör. Ama yüksek coverage kaliteli test demek değildir — assertion'ı olmayan, sadece "çağırıp çökmedi" diyen testler coverage'ı şişirir ama refactor'da seni korumaz. Coverage'a değil, "bu test yanlış davranışı yakalar mı" sorusuna güven.

**Statik analiz / linter'lar** (SonarQube, ESLint, Ruff, RuboCop, Clang-Tidy): Kokuları *otomatik* işaretler — duplication, uzun fonksiyon, karmaşıklık. Değeri: dikkatini yönlendirir. Tehlikesi: her uyarıyı düzeltilecek bir görev sanmak. Linter'ı bir *danışman* gibi kullan, patron gibi değil. "SonarQube 400 issue buldu, hepsini kapatalım" diyen ekipler haftalarca değer üretmeyen kozmetik değişiklik yapar.

**Hotspot analizi — en çok atlanan, en değerli araç:** `git log`'dan değişim frekansını çıkar, statik analizden karmaşıklığı çıkar, ikisini çarp. Yüksek değişim × yüksek karmaşıklık = refactor'un en yüksek getirili olduğu nokta. Adam Tornhill'in "Your Code as a Crime Scene" yaklaşımı bunu formalleştirir; CodeScene aracı bunu görselleştirir ama kabaca elle de yapabilirsin:
```
git log --format= --name-only --since="1 year" | \
  grep -v '^$' | sort | uniq -c | sort -rn | head -20
```
Bu liste sana refactor bütçeni **nereye** harcayacağını söyler. Sezgiyle "şu dosya çirkin" demekten çok daha güvenilirdir; çünkü çirkin ama dokunulmayan koda harcanan efor israftır.

**Observability — refactor sonrası:** Davranış-koruyan olduğunu iddia ettiğin bir değişikliği prodüksiyona verdikten sonra hata oranı, latency, ilgili iş metriklerini izle. Testlerin yakalamadığı bir davranış farkı varsa, grafik sana söyler. Özellikle sıcak yollarda (hot path) yapılan refactor'da performans regresyonunu ancak prodüksiyon telemetrisi gösterir; unit test göstermez.

**Feature flag / dallı dağıtım — riskli refactor için:** Büyük ve riskli bir yeniden yapılanmada eski ve yeni yolu yan yana çalıştırıp sonuçları karşılaştıran bir "parallel run" kur (eski yolu çağır, yeni yolu da çağır, farkı logla, ama eskinin sonucunu döndür). GitHub'ın Scientist kütüphanesinin fikri budur. Farklar sıfırlanınca yeni yola geç. Kritik yollarda "davranış korundu"yu prodüksiyon verisiyle ispatlamanın en sağlam yolu.

---

**Kapanış yargısı:** Refactor bir erdem gösterisi değildir. "Temiz kod" ahlaki bir hedef değil, ekonomik bir araçtır — değişimin maliyetini düşürmek için. Kod değişmiyorsa temizliğinin bir getirisi yoktur. O yüzden pro'nun ilk sorusu "bu kod çirkin mi" değil, "bu kod değişecek mi ve değişmesi acı veriyor mu"dur. Belirtiyi (kokuyu) hastalıktan (yanlış tasarım kararı) ayır, en yüksek getirili yere odaklan, testle kendini koru, küçük adımlarla ilerle, davranış değişikliğiyle karıştırma. Kariyerinin sonunda seni ayıran şey ne kadar çok refactor yaptığın değil, ne zaman **yapmadığını** bildiğin olacak.
