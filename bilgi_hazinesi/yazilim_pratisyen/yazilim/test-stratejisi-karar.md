# Test Stratejisi Kararı: Neyi Test Etmeli, Neyi Test Etmemeli

## 1. Problem ve bağlam

Sınırsız zamanınız yok. Bir özellik için yazabileceğiniz test sayısı pratik olarak sonsuzdur; yazacağınız zaman ise sonlu. "Her şeyi test et" diyen kişi ya hiç üretim kodu göndermemiştir ya da nerede olduğunu bilmediği yüzlerce kırılgan testle boğulan bir ekibin içindedir. Test stratejisi kararı tam olarak şunu çözer: elimizdeki sınırlı test bütçesini, **hata olma olasılığı yüksek** ve **hata olduğunda maliyeti yüksek** yerlere nasıl yönlendiririz?

Bu karar üç anda devreye girer. Birincisi, yeni bir özellik yazarken: "bunun hangi kısmına test yazayım?" İkincisi, bir üretim hatası (incident) sonrası: "bunu bir daha yaşamamak için nereye kanca koyayım?" Üçüncüsü ve en sinsi olanı, mevcut bir kod tabanını devraldığınızda: "bu 400 testin hangisi gerçekten bir şey koruyor, hangisi sadece CI süresini uzatıyor ve refactor'ı engelliyor?"

Yüzeysel kaynaklar size test piramidini anlatır: çok birim testi, biraz entegrasyon, az uçtan uca. Bu bir başlangıç kuralıdır, karar değil. Gerçek karar, "bu spesifik kod parçası için piramidin neresindeyim ve neden?" sorusudur. Bunu bir sonraki bölümde açıyorum.

## 2. Metodoloji ve karar ağacı: pro nasıl düşünür

Kıdemli mühendisin kafasındaki asıl model piramit değil, bir **risk matrisidir**. Her kod parçasını iki eksende konumlandırırım:

- **Değişim olasılığı × hata olasılığı** (bu kod ne sıklıkta bozulur?)
- **Bozulunca maliyet** (bozulursa kim, ne kadar acı çeker?)

Testi bu iki değerin çarpımının yüksek olduğu yerlere koyarım. Düşük olduğu yere test yazmak, sıfıra yakın bir riski azaltmak için zaman harcamaktır ve o test ileride refactor'ı engelleyen bir ayak bağı olur.

### Karar ağacı, adım adım

**Adım 0 — "Bu mantık mı, yoksa sıhhi tesisat mı?"**
İlk ayrım budur. Kodu ikiye bölerim: *karar veren kod* (iş kuralları, hesaplama, durum geçişleri, ayrıştırma) ve *bağlayan kod* (bir fonksiyonu çağırıp sonucu başka yere veren glue). Karar veren kodda hata gizlenir; bağlayan kodda hata genelde ilk çalıştırmada gürültülü şekilde patlar. Test bütçemin ezici çoğunluğu karar veren koda gider.

Belirti → yön: Bir fonksiyonda çok sayıda `if`, sınır değeri, `null` durumu, para/tarih/zaman aritmetiği görüyorsam → yoğun birim testi. Sadece "şunu al, şuna ver, dönüşü ilet" görüyorsam → birim testi yazmam, bu satırı entegrasyon testinin yolu üzerinde dolaylı olarak kaplarım.

**Adım 1 — "Bu kodun sözleşmesi (contract) net mi?"**
Girdi-çıktı ilişkisi saf ve deterministikse (aynı girdi → aynı çıktı, yan etki yok) burası birim testinin altın bölgesidir. Ucuz, hızlı, kararlı testler buradan çıkar. Vergi hesabı, indirim mantığı, bir string parser, bir yetki kontrol fonksiyonu — bunları saf tutup masaya yatırırım.

Belirti → yön: Fonksiyon bir veritabanına, saate, rastgele sayıya, ağ çağrısına bağımlıysa, önce **bu bağımlılıkları dışarı iteklerim** (dependency injection). Saf çekirdeği test ederim; kirli kenarı ince tutar, entegrasyonda ölçerim. Bu, "test edilebilirlik için tasarım" dediğimiz şeydir ve testten önce gelir.

**Adım 2 — "Hata buraya girerse ne kadar sessiz olur?"**
En tehlikeli hatalar patlamayan, yanlış cevap verip devam eden hatalardır. Bir ödeme tutarının yanlış yuvarlanması, bir yetkilendirme kontrolünün yanlış `true` dönmesi, bir rapor toplamının sessizce eksik olması. Bunlar log'a düşmez, exception fırlatmaz. Buralara **kesinlikle** test koyarım, üstelik mutlu yol değil, sınır ve kötü yol testleri.

Belirti → yön: "Bu yanlış çalışırsa fark eder miyiz?" sorusuna cevabım "hayır, aylarca fark etmeyiz" ise, bu kod test önceliğinde en tepeye çıkar.

**Adım 3 — "Bu davranışı bir kullanıcı/çağıran gerçekten görüyor mu?"**
Test etmem gereken şey **davranıştır (behavior), implementasyon değil**. Bir sınıfın private metoduna, bir değişkenin ara değerine test yazmak beni implementasyona kilitler; sonra o metodu refactor ettiğimde test kırılır ama sistem çalışmaya devam eder. Bu "false negative" testler zamanla ekibin teste güvenini öldürür.

Belirti → yön: Test yazmadan önce sorarım: "Bu testin kırıldığı gün, gerçekten bir kullanıcı acı çekecek mi, yoksa sadece kodu yeniden düzenledim diye mi kırıldı?" İkincisiyse testi ya daha yukarı seviyeye taşırım ya da hiç yazmam.

**Adım 4 — Seviye seçimi (birim mi, entegrasyon mı, e2e mi?)**
Kuralım şu: **testi, doğrulamak istediğim güvenin yaşadığı en düşük seviyede yaz.** Hesap doğruysa birim yeter. "Sipariş verilince stok düşüyor ve e-posta kuyruğa giriyor" gibi bir güven, birden çok bileşenin doğru konuşmasına dair; bu entegrasyon testi ister. "Kullanıcı sepete ekleyip ödeme yapabiliyor" gibi bir iş sonucu ise en pahalı ama en gerçekçi olan e2e/akış testini hak eder — ama sadece bir-iki kritik yol için.

Takas burada nettir: aşağı indikçe test hızlı, kararlı ve odaklı ama gerçeklikten uzak; yukarı çıktıkça gerçekçi ama yavaş, kırılgan ve arıza teşhisi zor. Ben her güveni mümkün olan en aşağıda yakalamaya, ama entegrasyon sınırlarında gerçek bir "birbirine bağlanıyor mu" testi bırakmaya çalışırım.

**Adım 5 — "Bu hata daha önce oldu mu?"**
Üretimde bir kez olan hata, olma olasılığı en yüksek hatadır. Her incident'ten sonra ilk yaptığım şey, düzeltmeden önce o hatayı **kırmızıya düşüren** bir regresyon testi yazmaktır. Bu, tüm test yazma kararları içinde getiri/maliyet oranı en yüksek olanıdır: gerçeklik size tam olarak neyin kırıldığını göstermiştir, tahmin etmenize gerek yok.

### Özet sezgi

Testi şuralara koyarım: karmaşık iş mantığı, sessizce yanlış olabilen hesaplar, güvenlik/yetki sınırları, para-tarih-zaman, geçmişte patlamış yerler, ve bileşenlerin buluştuğu entegrasyon dikişleri. Testi şuralardan esirgerim: saf glue kod, framework'ün zaten garanti ettiği şeyler (getter/setter, ORM'in kendi kaydetmesi), sık değişen deneysel UI, ve implementasyon detayına yapışan iç metodlar.

## 3. Gerçek kod üzerinden yürüyüş: teşhisten düzeltmeye

Somut bir senaryo alalım. Bir e-ticaret sisteminde indirim hesaplayan bir fonksiyon var. Dilden bağımsız anlatıyorum ama gerçek bir mantık:

```
fiyatHesapla(sepetTutari, kuponYuzdesi, uyeSeviyesi):
    indirim = sepetTutari * kuponYuzdesi / 100
    if uyeSeviyesi == "gold":
        indirim = indirim + sepetTutari * 0.10
    sonFiyat = sepetTutari - indirim
    return yuvarla(sonFiyat)
```

Acemi buraya bir test yazar:

```
test:
    fiyatHesapla(100, 20, "normal") == 80   // geçer, tamam
```

Mutlu yol geçer, kişi rahatlar, PR merge olur. **Üretimde ne olur?** Birkaç hafta sonra destek ekibi "gold üyeler eksi bakiyeyle sipariş verebiliyor" diye bir ticket açar. Çünkü kimse şunu test etmedi:

```
fiyatHesapla(100, 95, "gold")
// kupon indirimi: 95, gold indirimi: 10 → toplam indirim 105
// sonFiyat = 100 - 105 = -5
```

Sistem eksi fiyatı kabul etti, ödeme sağlayıcısı bunu 0'a mı yuvarladı yoksa müşteriye para mı iade etmeye kalktı, orası ayrı bir kâbus.

**Pro nasıl yaklaşırdı?** Bu fonksiyona bakar bakmaz "burada birleşen indirimler var, alt sınır yok" diye bir alarm çalar. Test setini davranış sözleşmesi etrafında kurar, mutlu yol değil sınırlar etrafında:

```
test: temel indirim doğru        → fiyatHesapla(100, 20, "normal") == 80
test: gold ek indirim uygulanır  → fiyatHesapla(100, 0, "gold")   == 90
test: indirim fiyatı sıfırın altına indiremez
      → fiyatHesapla(100, 95, "gold") == 0     // KIRMIZI, bug'ı yakalar
test: yuvarlama kuruş hatası yapmaz
      → fiyatHesapla(10, 33, "normal") == 6.70  // 10 - 3.30
test: negatif/sıfır sepet reddedilir veya 0 döner
test: bilinmeyen üye seviyesi normal gibi davranır (fallback)
```

Üçüncü test kırmızı yanar. Teşhis nettir: iş kuralında "son fiyat asla 0'ın altına inemez" görünmez bir varsayımı vardı, kod bunu zorlamıyordu. Düzeltme:

```
fiyatHesapla(sepetTutari, kuponYuzdesi, uyeSeviyesi):
    if sepetTutari <= 0: return 0
    indirim = sepetTutari * kuponYuzdesi / 100
    if uyeSeviyesi == "gold":
        indirim += sepetTutari * 0.10
    sonFiyat = max(0, sepetTutari - indirim)   // alt sınır zorlandı
    return yuvarla(sonFiyat)
```

Dikkat edin: değerli olan şey testin *varlığı* değil, testin *hangi soruyu sorduğuydu*. "Mutlu yol geçiyor mu" değil, "bu mantık hangi girdide utanç verici biçimde yanlış davranır" sorusu. Kıdemli mühendisin kafasındaki liste hep şudur: sınır değerleri (0, negatif, çok büyük), boş/null, birleşen kuralların çakışması, yuvarlama, ve "bilinmeyen enum" durumu.

### Para ve zaman: özel bir uyarı

Yukarıdaki `yuvarla` çağrısı bile bir tuzaktır. Eğer para float ile tutuluyorsa `0.1 + 0.2` bile size `0.30000000000000004` verir ve toplamlar zamanla kayar. Pro burada testten önce **tasarım** kararını sorgular: para tam sayı (kuruş) veya ondalık tip (decimal) olmalı, float olmamalı. Test bu kararı korur:

```
test: 0.1 + 0.2 toplamı tam 0.30 olur (para tipi float değil)
```

Bu test yeşilse, biri gelip float'a çevirdiğinde kırmızı yanar ve felaketi CI'da yakalarsınız, üretimde muhasebe farkı olarak değil.

## 4. Acemi vs pro: yaygın hatalar ve sinsi tuzaklar

**Acemi kapsama oranını (coverage) hedef sanır.** "%90 coverage'a ulaşalım" der. Coverage bir *satırın çalıştırıldığını* söyler, *doğrulandığını* değil. Assertion'ı olmayan, sadece fonksiyonu çağırıp exception fırlatmadığına bakan testler %100 coverage üretir ve sıfır güven verir. Pro coverage'a bir teşhis aracı olarak bakar ("hiç dokunulmayan kritik dal var mı?"), hedef olarak değil. Coverage'ın peşine düşmek, insanları glue kod ve getter'lara anlamsız test yazmaya iter — yani en düşük değerli yere.

**Acemi implementasyonu test eder, pro davranışı.** Acemi mock'u öyle kurar ki test kodun *nasıl* yaptığını doğrular: "şu metod tam 2 kez çağrıldı, önce şunu sonra bunu yaptı." Bu testler kod doğru çalışmaya devam etse bile en ufak refactor'da kırılır. Sonuç: ekip refactor yapmaktan korkar, çünkü "yeşili bozmak" istemez. Testler kodu iyileştirmenizi engelleyen bir kafese dönüşür. Pro, mümkün olduğunca *sonucu* doğrular, iç adımları değil.

**Acemi her şeyi mock'lar, sonra hiçbir şeyi test etmemiş olur.** Aşırı mock'lama klasik tuzaktır: veritabanını, servisi, saati, her şeyi taklit edersiniz; test yeşildir; ama gerçekte iki bileşen birbiriyle konuşamıyordur çünkü mock'un davranışı gerçek bağımlılığın davranışıyla uyuşmuyordur. En yaygın hâli: mock, gerçek API'nin artık döndürmediği bir formatı döndürür. Test "yeşil yalan" söyler. Pro, mock'un doğruluğunu belirli aralıklarla gerçek bağımlılığa karşı bir *contract test* ile sabitler veya kritik dikişleri gerçek (ama izole, örneğin bellek-içi veya container'da) bağımlılıkla test eder.

**"İşe yarar gibi görünüp üretimde patlayan" tuzakların kısa listesi:**

- **Zaman ve zaman dilimi.** `bugün()` çağıran kod, testi yazdığınız gün yeşildir; yılbaşı gecesi, artık gün, veya farklı timezone'daki sunucuda kırmızıdır. Saati enjekte edin, sabit bir tarihe göre test edin.
- **Sıralama varsayımı.** Bir map/set üzerinde dönen kodun testi yerelde belli bir sırada geçer, üretimde farklı sırada patlar. Test sıraya bağlıysa ya sırayı garanti edin ya da sıradan bağımsız doğrulayın.
- **Testler arası sızıntı (shared state).** Testler tek başına geçer, birlikte çalışınca rastgele biri düşer. Bir test global durumu/veritabanını kirletir, diğeri ondan etkilenir. Bu "flaky" testtir ve ekibin teste güvenini en hızlı öldüren şeydir. Kural: her test kendi durumunu kurar ve temizler, sıraya bağlı olmaz.
- **Mutlu yol tiryakiliği.** Her şeye "doğru girdiyle doğru çıktı" testi yazılır, hiç kötü girdi denenmez. Oysa üretimdeki hataların çoğu beklenmeyen girdiden çıkar: boş liste, null, çok uzun string, eş zamanlı iki istek.
- **Assertion'sız test.** `çalıştır(); // hata fırlatmadı, demek ki çalışıyor`. Bu test bir şeyi doğrulamaz; sadece kod çöküyor mu ona bakar. Sessiz yanlışları asla yakalamaz.

**Pro'nun karşı-sezgili bir davranışı:** Bazen doğru karar *test silmektir*. Devraldığınız kod tabanında refactor'ı engelleyen, implementasyona yapışmış, hiçbir gerçek riski korumayan 50 testi silmek; yerine 5 tane davranış-odaklı test koymak, net bir kazançtır. Acemi test silmekten korkar ("ya bir şey koruyorsa?"); pro her testin *hangi somut hatayı* yakaladığını sorar, cevap yoksa siler.

**Test edilmesi gerekenle edilmemesi gerekenin özeti (saha kuralı):**

| Test et | Esirge |
|---|---|
| Dallanan iş mantığı, sınır değerleri | Getter/setter, saf glue |
| Para, tarih, zaman, yuvarlama | Framework/ORM'in kendi garantisi |
| Yetki ve güvenlik sınırları | Sık değişen deneysel UI detayı |
| Sessizce yanlış olabilen hesaplar | Private metodun ara adımı |
| Geçmişte patlamış yerler (regresyon) | Üçüncü parti kütüphanenin içi |
| Bileşenlerin buluştuğu entegrasyon dikişleri | Log mesajının tam metni |

## 5. Araçlar ve saha notları

**Coverage araçları (satır/dal kapsama).** Dile göre değişir ama hepsi aynı işi görür: hangi satır ve dalların hiç çalıştırılmadığını gösterir. Doğru kullanım: raporu açıp "kritik iş mantığında hiç dokunulmamış `else` dalı var mı?" diye bakmak. Yanlış kullanım: yüzdeyi bir KPI'a çevirmek. Ekibe bir sayı hedefi koyduğunuz an, insanlar o sayıyı en kolay yerden (glue kod) doldurur, en zor ve en değerli yerden değil. Kapsama oranını *dal kapsaması* (branch coverage) olarak okuyun; satır kapsaması bir `if`'in sadece bir tarafına girip %100 gösterebilir.

**Mutation testing (mutasyon testi).** Bu, testlerinizin kalitesini test eden araçtır ve az bilinir ama çok değerlidir. Kodunuzda küçük bozmalar yapar (`>` yerine `>=`, `+` yerine `-`) ve testlerinizin bu bozmayı yakalayıp yakalamadığına bakar. Testleriniz hâlâ yeşilse, o testler aslında hiçbir şey doğrulamıyor demektir ("hayatta kalan mutant"). Coverage'ın söyleyemediği "testlerim gerçekten bir şey koruyor mu?" sorusunu bu cevaplar. Kritik iş mantığı modüllerinde ara sıra çalıştırmak, sahte güvenli testleri ortaya çıkarır. Yavaştır, tüm kod tabanına değil sadece en kritik modüllere uygulayın.

**Property-based testing (özellik tabanlı test).** Tek tek örnek yazmak yerine bir *özellik* tanımlarsınız ("ters çevir, tekrar ters çevir → orijinali elde et" veya "indirimli fiyat asla negatif olamaz") ve araç yüzlerce rastgele girdiyle bunu sınar, kırıldığında da en küçük kırıcı girdiyi (shrinking) size verir. Sınır değeri tuzaklarını insan hayal gücünden çok daha iyi bulur. Yukarıdaki indirim örneğinde "sonFiyat >= 0 her zaman doğru olmalı" bir property'dir ve araç size `(100, 95, "gold")` gibi bir örneği kendisi bulup verirdi.

**Debugger ve gözlemlenebilirlik (observability), teşhis tarafında.** Test yazarken değil, testin *neden* düştüğünü anlarken devreye girer. Flaky bir test için önce debugger'la değil, testi yüzlerce kez döngüde çalıştırıp (`--repeat`) hangi koşulda düştüğünü izole ederim; genelde sebep paylaşılan durum ya da zamanlamadır. Üretim tarafında ise şu ilkeyi tutarım: **teste değil de üretimde yakalanabilecek şeyleri observability ile yakala.** Her şeyi test edemezsiniz; edemediğiniz kombinasyonlar için üretimde iyi log, metrik ve alarm, ikinci savunma hattınızdır. "Son fiyat negatif çıktı" bir üretim alarmı olarak da durmalıdır, çünkü hiçbir test seti tüm girdi uzayını kaplayamaz.

**CI'da test seviyeleri.** Pratik düzen: her commit'te hızlı birim testleri (saniyeler), her PR'da entegrasyon testleri (dakikalar), gecelik veya merge öncesi ağır e2e (on dakikalar). Amaç, geliştiriciye en sık ve en hızlı geri bildirimi en ucuz testlerden vermek. E2e testini her commit'e koyarsanız CI 40 dakika sürer, insanlar test yazmaktan nefret eder ve "flaky diye" geçmeyen testleri retry ile geçmeye zorlar — ki bu, testin tüm anlamını öldürür.

**Flaky test politikası.** Bir saha kuralı: ara sıra düşen testi *retry ile gizlemeyin*. Flaky test, ya gerçek bir yarış koşulunu (race condition) ya da testin kötü izolasyonunu işaret eder; ikisi de gerçek bilgidir. Retry ile üzerini örttüğünüzde, üretimdeki gerçek yarış koşulunu da kör etmiş olursunuz. Flaky testi ya düzeltin ya karantinaya alıp sebebini bulun, ama yeşil görünsün diye tekrar tekrar çalıştırmayın.

**Test verisi ve fixture'lar.** Devasa, paylaşılan fixture dosyaları bir anti-pattern'dir: her test onlarca alanı olan dev bir nesneye bağımlı olur, biri o nesneyi değiştirince alakasız 30 test kırılır. Pro, her testin ihtiyaç duyduğu veriyi test içinde, mümkün olduğunca küçük ve okunur şekilde kurar (builder deseni işe yarar: "varsayılan geçerli sipariş, sadece tutarı 0 yap"). Test, ne test ettiğini tek başına okununca anlatmalıdır; başka dosyalardaki gizli kurulumu okumaya zorlamamalıdır.

**Testin adı bir spesifikasyondur.** Saha notu olarak küçük ama etkili: test adını "test1", "testHesapla" gibi değil, doğruladığı davranışı cümle olarak yazın — "indirim son fiyatı sıfırın altına indiremez". Bir test kırıldığında CI çıktısında sadece adını görürsünüz; ad size ne bozulduğunu kodu açmadan söylüyorsa dakikalar kazanırsınız. İyi adlandırılmış testler aynı zamanda o modülün yaşayan dokümantasyonudur: yeni gelen biri testlerin adlarını okuyarak iş kurallarını öğrenir. Kötü adlandırılmış bir test seti ise, kırıldığında panik, okunduğunda sessizliktir.

**Test yazma zamanlaması: önce mi sonra mı?** Dogmaya girmeden pratik duruş: karmaşık iş mantığında testi önce yazmak (test-first) tasarımı zorladığı için işe yarar — test edilemez bir arayüz yazdıysanız daha ilk dakikada anlarsınız. Ama keşif hâlindeki, şekli henüz belli olmayan kodda önce test yazmak sizi yanlış bir tasarıma çiviler; orada önce prototipi yapıp şekil oturunca testi eklemek daha akıllıcadır. Kritik olan "ne zaman" değil, kod tabana girmeden önce o davranışın bir güvenceyle korunmuş olmasıdır. Bir incident düzeltmesinde ise sıra tartışmasızdır: önce hatayı kırmızıya düşüren test, sonra düzeltme; çünkü testin gerçekten hatayı yakaladığını, yeşile döndüğünde de düzelttiğinizi ancak bu sırayla kanıtlarsınız.

**"Bu değişikliği geri alsam hangi test yanar?" testi.** Devraldığınız yabancı bir kod tabanında bir modülün gerçekten korunup korunmadığını anlamanın en hızlı yolu: kodun kritik bir satırını kasten bozun (bir koşulu tersine çevirin) ve test setini çalıştırın. Hiçbir test yanmıyorsa, o modül test edilmiş *görünüyor* ama aslında korunmuyor. Bu, coverage raporunun yalan söylediği yerleri elle bulmanın pratik yoludur ve bir mutasyon testi aracınız yoksa parmakla yapılan mini versiyonudur.

### Kapanış: kararın özü

Test stratejisi bir kapsama yüzdesi değil, bir **bahis dağılımıdır**. Sınırlı zamanınızı hata olasılığı ve hata maliyeti en yüksek yerlere yatırırsınız. İyi mühendisin ayırt edici özelliği çok test yazması değil, *hangi testi yazmayacağını* bilmesidir. "Bu test kırıldığı gün gerçek bir kullanıcı acı çekecek mi?" sorusuna dürüst cevap veremediğiniz her test, gelecekteki refactor'ınızın önünde bir engel, CI'nızda bir yük ve ekibinizin teste güveninde bir aşınmadır. Az ama davranışa bağlı, sınırları zorlayan, regresyonları çivileyen testler; çok ama implementasyona yapışmış, mutlu-yol, assertion'sız testlerden her zaman üstündür.
