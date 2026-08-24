# Test Driven Development (TDD)

## Tanım

Test Driven Development (TDD), Türkçe karşılığıyla "test güdümlü geliştirme", üretim kodunu yazmadan **önce** o kodun sağlaması gereken davranışı bir testle ifade etmeyi temel alan bir yazılım geliştirme disiplinidir. Kavramı bugünkü haliyle yaygınlaştıran isim Kent Beck'tir; yöntem, Extreme Programming (XP) pratiklerinin merkezinde yer alır.

TDD'yi bir "test etme faaliyeti" sanmak en sık yapılan kavram hatasıdır. TDD aslında bir **tasarım disiplinidir**; testler bu disiplinin yan ürünü olarak ortaya çıkar. Testi önce yazmak, geliştiriciyi henüz var olmayan kodun arayüzünü (interface), sorumluluklarını ve bağımlılıklarını kullanıcı gözünden düşünmeye zorlar. Yani TDD'nin ürettiği asıl değer, biriken test paketinden çok, o testleri yazarken alınan tasarım kararlarıdır.

Yöntem üç adımlı bir döngü etrafında döner: **kırmızı (red) - yeşil (green) - refactor**. Bu döngü o kadar merkezidir ki TDD çoğu zaman "red-green-refactor döngüsü" ile eş anlamlı kullanılır.

## Kök neden: Neden testi önce yazmak işe yarar?

TDD'nin neden çalıştığını anlamak için önce çözdüğü problemi görmek gerekir. Geleneksel yaklaşımda kod önce yazılır, test (yazılırsa) sonradan gelir. Bu sıralamanın üç yapısal sorunu vardır:

**1. Testi sonra yazmak, kodu test edilebilir kılmaz.** Kod önce yazıldığında, geliştirici çoğu zaman bağımlılıkları sıkıca birbirine geçmiş (tightly coupled), gizli durum (hidden state) taşıyan, yan etkileri (side effect) her yere yayılmış bir yapı üretir. Sonradan test yazmaya çalışıldığında bu kodun izole edilemediği fark edilir. Testi önce yazmak ise bu problemi kaynağında engeller: eğer bir davranışı test etmek zorsa, bunu kodu yazmadan önce hissedersiniz ve tasarımı daha en baştan test edilebilir (dolayısıyla gevşek bağlı, gözlemlenebilir) kurarsınız. Testin zorluğu, tasarım kokusuna (design smell) dair erken bir sinyaldir.

**2. Testi önce yazmak, "bittiğini" tanımlanabilir kılar.** Kod önce yazıldığında "bitti mi?" sorusunun objektif bir cevabı yoktur; geliştirici sezgisiyle karar verir. Testi önce yazdığınızda "bitti" tanımı somuttur: kırmızı test yeşile döndüğünde, tam olarak istediğiniz davranışı, ne eksik ne fazla, elde etmiş olursunuz. Bu, "yeterince kod yazma" (You Aren't Gonna Need It - YAGNI) prensibini kendiliğinden dayatır.

**3. Testi önce yazmak, testin kendisini test eder.** İyi bilinen bir tuzak, hiçbir zaman başarısız olmamış bir testtir; böyle bir test hiçbir şey doğrulamıyor olabilir. TDD döngüsünde her test önce **kırmızı** görülür. Testin doğru sebepten başarısız olduğunu gözlemlemek, testin gerçekten bir şey ölçtüğünün kanıtıdır. Bu adım atlanırsa, yanlış yazılmış ama her koşulda yeşil kalan bir test paketi birikir; bu, gerçek koruma sağlamayan sahte bir güven verir.

Bu üç mekanizma birlikte çalıştığında ortaya çıkan sonuç şudur: TDD hız kaybettiriyormuş gibi hissedilir ama orta vadede hata ayıklama (debugging) süresini ve regresyon (regression) riskini düşürerek net hız kazandırır. "Hissedilen yavaşlık" gerçek değil, dikkatin öne çekilmesidir; iş, sonradan hata avlamak yerine baştan doğru yapmaya kaydırılır.

## Kırmızı - Yeşil - Refactor döngüsü

Döngünün her adımının kendine has bir amacı ve kendine has bir disiplini vardır. Adımları birbirine karıştırmak TDD'nin faydasını büyük ölçüde yok eder.

### Kırmızı (Red): Başarısız test yaz

İlk adımda, henüz var olmayan bir davranışı tanımlayan bir test yazarsınız ve bu testin **başarısız olduğunu** görürsünüz. Burada kritik nokta, testin **doğru sebepten** başarısız olmasıdır: davranış henüz yazılmadığı için, bir syntax hatası veya derleme hatası (compile error) yüzünden değil.

Bu adımda geliştirici, üretim kodunun arayüzünü tasarlar. Örneğin bir fonksiyonu nasıl çağıracağınızı, hangi parametreleri alacağını, ne döndüreceğini test satırında yazarken kararlaştırırsınız. Yani kodu **kullanıcı** olarak deneyimlersiniz. Kullanışsız bir arayüz burada, yazması hantal bir test olarak kendini belli eder.

Kırmızı adımın altın kuralı: **sadece bir sonraki küçük davranış kadar test yaz.** Büyük, her şeyi kapsayan bir testle başlamak döngüyü kilitler.

### Yeşil (Green): Testi geçecek en basit kodu yaz

İkinci adımda amaç tek şeydir: testi yeşile döndürmek. Ve bunu yapmanın **en basit, hatta utanç verici derecede basit** yolunu seçmek gerekir. Kent Beck bu adım için "fake it till you make it" (numarasını yap, sonra gerçeğini yap) ve sabit değer döndürme (return a constant) gibi teknikleri savunur.

Bu, ilk bakışta saçma görünür: neden test istenen değeri bekliyorsa o değeri doğrudan `return` edeyim? Sebep şudur: bu adımda amaç doğru algoritmayı bulmak değil, **döngüyü kapatıp yeşile ulaşmaktır**. Doğru genelleme (generalization) bir sonraki testi eklediğinizde, sabit değerin artık yetmediğini gördüğünüzde kendiliğinden gelir. Bu tekniğe **triangulation** (üçgenleme) denir: birden fazla örnek testi, kodu tek bir sabit değerden gerçek algoritmaya doğru "çeker".

Yeşil adımın disiplini, **fazladan hiçbir şey yazmamaktır**. "Nasılsa gerekecek" diye ekstra durum (case), ekstra parametre, ekstra soyutlama eklemek YAGNI ihlalidir ve testin kapsamadığı, dolayısıyla korunmayan kod üretir.

### Refactor: Yeşilken temizle

Üçüncü adımda, testler yeşilken kodun iç yapısını iyileştirirsiniz: tekrarı (duplication) yok edersiniz, isimleri düzeltirsiniz, sorumlulukları ayırırsınız, "fake it" ile bıraktığınız sabit değerleri gerçek mantığa dönüştürürsünüz. Refactoring'in tanımı gereği **dışarıdan gözlemlenen davranış değişmez**; sadece iç yapı değişir. Testlerin yeşil kalması bunun kanıtıdır.

Refactor adımı çoğu zaman atlanır ve TDD'nin en çok değer kaybettiği yer burasıdır. Kırmızı-yeşil ile çalışan ama kirli bir kod yığını üretmek mümkündür; refactor adımı olmadan TDD, iyi test edilmiş kötü tasarıma dönüşür. Beck'in ünlü sözü bu adımı özetler: "Make it work, make it right, make it fast" (önce çalıştır, sonra doğru yap, sonra hızlandır). Kırmızı-yeşil "çalıştırır", refactor "doğru yapar".

Refactor için güvenli olmanın bir ön koşulu vardır: **testlerin yeşil olması.** Kırmızı bir testin üzerinde refactor yapmak, iki değişken anda hata aramak demektir; ayakta durmayan bir binanın duvarını yenilemeye benzer.

## Somut örnek: Roma rakamı çevirici

Kavramı somutlaştırmak için basit bir örneği döngü döngü ilerletelim: bir tam sayıyı Roma rakamına çeviren bir fonksiyon.

**1. Kırmızı.** İlk davranışı yazarız:

```python
def test_bir_I_verir():
    assert roma(1) == "I"
```

`roma` fonksiyonu daha yok, test başarısız (kırmızı). Ama dikkat: bu tek satırda çok karar aldık. Fonksiyonun adı `roma`, tek bir tam sayı alıyor, string döndürüyor. Arayüzü tasarladık.

**2. Yeşil (utanç verici basitlikte).**

```python
def roma(sayi):
    return "I"
```

Sabit değer döndürdük. Test yeşil. Evet, saçma görünüyor; ama döngüyü kapattık.

**3. Kırmızı (triangulation).** Şimdi sabit değeri kıracak ikinci bir örnek:

```python
def test_iki_II_verir():
    assert roma(2) == "II"
```

Artık `return "I"` yetmiyor. İki örnek, kodu gerçek mantığa çekmeye başladı.

**4. Yeşil.**

```python
def roma(sayi):
    return "I" * sayi
```

İki test de yeşil.

**5. Kırmızı.** `roma(4)` "IIII" değil "IV" olmalı. Bu test, algoritmanın yetersizliğini açığa çıkarır ve bizi çıkarma (subtractive) kuralına yönlendirir. Böylece her yeni test, kodu bir adım daha gerçek çözüme doğru iter; hiçbir adımda "ihtiyaç olmayan" kod yazmayız.

Bu örnekteki önemli ders şudur: **algoritmayı baştan tasarlamadık; testlerin baskısı altında ortaya çıkarttık.** Her sabit değer bir sonraki test tarafından kırıldı ve kod, örneklerin zorladığı kadar genelleşti; ne eksik ne fazla.

## Tasarıma etkisi: TDD neden daha iyi tasarım üretir?

TDD'nin en güçlü ve en az anlaşılan tarafı tasarıma etkisidir. Bunu birkaç mekanizma üzerinden anlatmak gerekir.

**Testlenebilirlik, gevşek bağlılığı zorunlu kılar.** Bir sınıfı izole test edebilmek için, bağımlılıklarını dışarıdan verebilmeniz (dependency injection), yan etkilerini gözlemleyebilmeniz gerekir. TDD, testi önce yazdığı için bu ihtiyaçları tasarımın en başında dayatır. Sonuçta ortaya çıkan kod, bileşenleri değiştirilebilir (test için sahte bir bileşenle -mock, stub, fake- değiştirilebilen) bir yapıya sahip olur. Yani test edilebilirlik ve iyi modülerlik büyük ölçüde aynı şeyin iki yüzüdür.

**Küçük arayüzler ve tek sorumluluk.** Test etmesi kolay olan birim, az sayıda girdi alan, tek bir işi yapan, çıktısı öngörülebilir olan birimdir. Onlarca bağımlılığı olan bir "tanrı sınıfı" (god class) test etmek işkencedir. Testin bu acısı, geliştiriciyi doğal olarak daha küçük, daha odaklı birimlere böler. Yani TDD, Single Responsibility Principle'ı (tek sorumluluk ilkesi) dışarıdan bir kural olarak değil, testin verdiği acı üzerinden içselleştirir.

**Testler yaşayan dokümantasyon olur.** İyi yazılmış bir test paketi, kodun nasıl kullanılacağını gösteren, her zaman güncel (çünkü derlenip çalıştırılan) örnekler bütünüdür. Yorum satırları eskir; testler eskiyemez, çünkü eskirlerse kırmızı olurlar.

Burada önemli bir nüans var: TDD **otomatik olarak** iyi tasarım üretmez. TDD, kötü tasarımın acısını **erken** hissettirir. Bu acıyı refactor adımında iyi tasarıma çevirmek geliştiricinin işidir. TDD iyi tasarımın garantisi değil, iyi tasarım için bir geri bildirim (feedback) mekanizmasıdır. Refactor becerisi olmayan birinin elinde TDD, iyi test edilmiş kötü kod üretir.

## Sınırlar: TDD nerede zayıflar, nerede uygun değildir?

Dürüst bir TDD anlatısı, yöntemin sınırlarını gizlemez. TDD her yerde ve her ölçekte eşit derecede uygun değildir.

**1. Keşif ve prototipleme (spike).** Bir problemi henüz anlamadığınız, çözümün ne olacağını bilmediğiniz durumlarda testi önce yazmak anlamsızdır; test edilecek davranışı henüz kendiniz bilmiyorsunuz. Bu tür keşif çalışmalarına "spike" denir. Doğru pratik, önce atılabilir bir prototiple problemi anlamak, sonra öğrendiklerinizle TDD'ye geçmektir. TDD'yi keşif aracı sanmak zaman kaybettirir.

**2. Birim testinin doğal olarak zayıf olduğu alanlar.** TDD, en güçlü haliyle mantık (logic) yoğun, deterministik kod için işler. Şu alanlarda birim testi hem yazması zordur hem de az değer verir:
- **Kullanıcı arayüzü (UI) düzeni ve görsel doğruluk:** "Buton doğru yerde mi, renk hoş mu" gibi sorular otomatik birim testiyle iyi yakalanamaz.
- **Ağ, disk, dış servis entegrasyonları:** Bunları birim testinde taklit etmek (mock) mümkündür ama aşırı mock kullanımı, gerçekte var olmayan bir dünyayı test eden kırılgan testler üretir. Burada entegrasyon testi (integration test) daha uygundur.
- **Eşzamanlılık (concurrency) ve zamanlama:** Race condition gibi hataları deterministik bir birim testiyle güvenilir biçimde yakalamak çok zordur.

**3. Test paketinin kendi bakım maliyeti.** Testler de koddur; onlar da bakım ister. Uygulama koduna aşırı bağlı (implementation-coupled), her küçük iç değişiklikte kırılan testler, refactoring'i kolaylaştırmak yerine zorlaştırır. Bu, TDD'nin vaadinin tam tersidir. Testler **davranışı** doğrulamalı, **uygulama detayını** değil.

**4. TDD, iyi test tasarımını garanti etmez.** TDD size testi önce yazmayı söyler ama **doğru** testi yazmayı öğretmez. Yanlış sınır durumlarını (edge case) düşünmeyen, yalnızca mutlu yolu (happy path) test eden bir geliştirici, TDD uygulasa bile eksik korumalı bir paket üretir. TDD bir süreç disiplinidir; test tasarımı ayrı bir beceridir.

**5. Ampirik kanıt karışıktır.** TDD'nin kalite ve verimlilik üzerindeki etkisini ölçen akademik çalışmalar tutarlı, tek yönlü bir sonuç vermez. Bazı çalışmalar hata oranında düşüş bildirirken, kimi çalışmalar etkiyi TDD'nin kendisine değil, TDD uygulayanların ürettiği daha küçük ve daha çok test edilen birimlere bağlar. Dürüst tavır şudur: TDD güçlü bir disiplindir, ama "her koşulda kanıtlanmış bir hızlandırıcı" diye pazarlanması abartıdır.

## Yaygın hatalar

**Kırmızıyı atlamak.** Testi yazıp hiç çalıştırmadan koda geçmek. Böylece testin gerçekten bir şey ölçtüğü hiç doğrulanmaz. Her zaman önce kırmızıyı, doğru sebeple, gözünüzle görün.

**Refactor'ı atlamak.** Kırmızı-yeşil ile yetinip kodu temizlememek. Zamanla iyi test edilmiş bir teknik borç (technical debt) yığını oluşur. TDD'nin tasarım değeri büyük ölçüde bu adımda üretilir.

**Bir seferde çok büyük adım.** Devasa bir test yazıp onu geçirmek için yüzlerce satır kod yazmak. Bu, TDD'yi "önce büyük test, sonra büyük kod"a çevirir ve küçük geri bildirim döngüsünün tüm faydasını yok eder. Adımlar rahatsız edici derecede küçük olmalıdır.

**Uygulama detayına test yazmak.** Private metotları, iç değişkenleri, çağrı sıralamalarını test etmek. Bu testler her refactoring'de kırılır ve testleri, iyileştirmenin önünde bir engele dönüştürür. Testler gözlemlenebilir davranışa odaklanmalıdır.

**Aşırı mock kullanımı (mock hell).** Her bağımlılığı mock'layan testler, gerçek entegrasyonu hiç doğrulamaz; kodun kendi hayal ettiği bir dünyayı test eder. Mock'lanan bir bileşenin gerçek davranışı değiştiğinde testler yeşil kalır ama sistem çalışmaz.

**Test kapsamını (coverage) hedef sanmak.** %100 satır kapsamı, kodun doğru olduğunu göstermez; yalnızca her satırın en az bir kez çalıştırıldığını gösterir. Kapsam bir araç, bir hedef değildir. Yüksek kapsamlı ama zayıf iddialı (assertion) testler yanıltıcı güven verir.

**TDD'yi test yazma zorunluluğu sanmak.** "TDD yapıyoruz" deyip aslında kodu yazıp sonra test eklemek. Bu test-sonrası (test-after) bir pratiktir; faydalı olabilir ama TDD'nin tasarım baskısını vermez. TDD'nin özü sıralamadadır.

## En iyi pratikler

**Adımları küçük tut.** İdeal döngü dakikalar, bazen saniyeler sürer. Bir kırmızı-yeşil-refactor turu ne kadar kısaysa, geri bildirim o kadar hızlı, hata ayıklama alanı o kadar dardır. Bir şeyler ters gittiğinde "son yeşilden bu yana ne değişti?" sorusunun cevabı küçük olmalıdır.

**Testi davranışa göre yaz, uygulamaya göre değil.** "Bu fonksiyon şu private metodu çağırıyor mu?" değil, "bu girdiye bu çıktı geliyor mu?" sorusunu test edin. Böylece iç yapıyı özgürce refactor edebilirsiniz.

**Her test tek bir şeyi doğrulasın.** Bir test başarısız olduğunda, neyin bozulduğu tek bakışta anlaşılmalı. Onlarca iddiaya sahip bir test, kırıldığında teşhis koymayı zorlaştırır.

**Testleri okunur ve niyet belli olacak şekilde yaz.** Test adları davranışı anlatmalı ("negatif_girdide_hata_verir" gibi). İyi bir test paketi, kodu ilk kez gören birine kodun ne yaptığını anlatan bir spesifikasyondur.

**Arrange-Act-Assert (hazırla-uygula-doğrula) düzenini benimse.** Testi üç net bölüme ayırmak (girdiyi hazırla, davranışı çağır, sonucu doğrula) hem okunurluğu hem de her testin tek bir davranışa odaklanmasını sağlar.

**Testleri hızlı tut.** Yavaş bir test paketi çalıştırılmaz; çalıştırılmayan test yoktur. Birim testleri saniyeler içinde bitmelidir ki döngü akıcı kalsın. Yavaş, dış bağımlılıklı testleri ayrı bir katmana (entegrasyon/uçtan uca) çekin.

**TDD'yi test piramidine (test pyramid) yerleştir.** TDD çoğunlukla birim seviyesinde parlar; ama tek başına yeterli değildir. Altta çok sayıda hızlı birim testi, ortada daha az entegrasyon testi, tepede az sayıda uçtan uca (end-to-end) test bulunan dengeli bir piramit hedeflenmelidir. TDD bu piramidin tabanını inşa etmenin bir yoludur, tamamını değil.

**Refactor'ı ciddiye al.** Her yeşilden sonra "burada tekrar var mı, bu isim doğru mu, bu sorumluluk buraya mı ait?" diye sorun. TDD'nin tasarım getirisi bu küçük, sürekli temizliklerde birikir.

**Testlenmesi zor bir noktada durup dinle.** Bir davranışı test etmek zorlaşıyorsa, bu bir tasarım sinyalidir. Zorluğu "test framework'ü ile boğuşarak" değil, tasarımı gevşeterek çözün. TDD'nin en değerli anları, testin size tasarım hakkında bir şey söylediği anlardır.

## Kapanış

TDD'yi tek cümleyle özetlemek gerekirse: **testi önce yazmak, kodu kullanıcı gözünden tasarlamaya zorlayan ve "bitti"yi somutlaştıran bir tasarım disiplinidir; testler bunun kanıtı ve yan ürünüdür.** Kırmızı-yeşil-refactor döngüsünün her adımı ayrı bir amaca hizmet eder: kırmızı arayüzü tasarlar ve testin geçerliliğini kanıtlar, yeşil en basit çözümle döngüyü kapatır, refactor kaliteyi ekler. Yöntemin gücü küçük adımlarda, hızlı geri bildirimde ve tasarım baskısındadır; sınırları ise keşif işlerinde, UI ve eşzamanlılık gibi alanlarda, ve en önemlisi test tasarımı becerisinin yerini tutamamasındadır. TDD bir düşünce ve çalışma disiplinidir; onu bir tören ya da kapsam metriği avına indirgemek, aslında değerli olan tarafını kaybetmek demektir.
