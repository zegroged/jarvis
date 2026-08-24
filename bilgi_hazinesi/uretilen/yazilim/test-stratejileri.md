# Test Stratejileri

## Giriş: Test Neden Bir "Strateji" Meselesidir?

Yazılım testi, çoğu geliştiricinin sandığının aksine "kod çalışıyor mu?" sorusuna evet/hayır cevabı veren mekanik bir aktivite değildir. Test, sınırlı zaman ve para bütçesiyle sistemin doğru davrandığına dair **güven** satın aldığımız bir yatırım kararıdır. Her testin bir maliyeti vardır: yazma maliyeti, çalıştırma maliyeti (süre, altyapı) ve en sinsisi olan **bakım maliyeti**. Aynı şekilde her testin bir getirisi vardır: hata yakalama olasılığı ve regresyona karşı koruma. Strateji dediğimiz şey, bu maliyet/getiri dengesini bilinçli kurmaktır.

Bu yüzden "her şeyi test et" veya "yüzde 100 kapsama (coverage) hedefle" gibi sloganlar strateji değildir; strateji yokluğunun kılık değiştirmiş halidir. İyi bir test stratejisi, hangi seviyede, ne kadar, hangi teknikle test yazacağımıza dair **açık ödünleşimlere** dayanır. Bu makale, bu ödünleşimleri piramit modeli, test seviyeleri, mock kullanımı, flaky testler ve kapsama metrikleri ekseninde derinlemesine inceliyor.

## Test Piramidi: Neden Şekli Bir Piramit?

Test piramidi, Mike Cohn tarafından popülerleştirilmiş bir modeldir. Tabanda çok sayıda hızlı ve ucuz **unit test**, ortada daha az sayıda **integration test**, tepede ise az sayıda yavaş ve pahalı **end-to-end (e2e) test** bulunur. Piramidin görsel olarak bir üçgen olması tesadüf değildir; alttan yukarı çıktıkça test sayısı azalır.

### Kök Neden: Neden Tabanı Geniş Tutuyoruz?

Piramidin bu şekli iki temel fiziksel gerçekten doğar: **hız** ve **izolasyon**.

Unit testler tek bir fonksiyonu ya da sınıfı, veritabanı, ağ veya dosya sistemi gibi dış bağımlılıklar olmadan bellekte çalıştırır. Bir unit test tipik olarak milisaniyenin altında çalışır. On bin unit testi birkaç saniyede koşabilirsiniz. Bu hız, geliştiricinin kod yazarken saniyeler içinde geri bildirim almasını sağlar; bu geri bildirim döngüsü kısaldıkça hatayı yaratan değişikliği hatırlamak kolaylaşır, dolayısıyla düzeltme maliyeti düşer.

E2e testler ise sistemin tümünü gerçek bir tarayıcı, gerçek bir veritabanı ve gerçek ağ çağrılarıyla ayağa kaldırır. Tek bir e2e test saniyeler hatta dakikalar sürebilir. Bu yavaşlığın matematiği acımasızdır: eğer tüm test paketinizi e2e testlerle doldurursanız, geri bildirim döngüsü onlarca dakikaya çıkar, geliştiriciler testi çalıştırmaktan kaçınır ve testin varlık sebebi ortadan kalkar.

İkinci neden **hata lokalizasyonudur** (fault localization). Bir unit test kırıldığında, sorunun hangi fonksiyonda olduğunu neredeyse kesin bilirsiniz çünkü test yalnızca o birimi çalıştırır. Bir e2e test kırıldığında ise sorun frontend'de mi, API'de mi, veritabanı sorgusunda mı, yoksa test ortamının kendisinde mi olduğunu anlamak için uzun bir araştırma gerekir. Yani üst seviye testler yalnızca yavaş değil, aynı zamanda **tanısal olarak bulanıktır**.

### Ters Piramit ve "Dondurma Külahı" Anti-Pattern'i

Pratikte ekipler sık sık piramidi ters çevirir: az unit test, çok sayıda e2e test. Bu duruma bazen "dondurma külahı" (ice cream cone) anti-pattern'i denir; üstte manuel testlerden ve e2e testlerden oluşan şişkin bir kütle, altta ise incecik bir unit test tabanı. Bu genellikle bilinçli bir tercih değildir; unit test yazma disiplininin eksikliğinin ve "bir tıklayıp göreyim çalışıyor mu" kültürünün doğal sonucudur. Sonuç, yavaş, kırılgan ve pahalı bakımlı bir test paketidir.

Öte yandan modern görüşlerde piramidin katı yorumu da eleştirilir. Kent C. Dodds'un "test kupası" (testing trophy) fikri, özellikle çok sayıda küçük servisin birbiriyle konuştuğu modern mimarilerde **integration** katmanına piramidin öngördüğünden daha fazla ağırlık verilmesi gerektiğini savunur. Buradaki temel argüman şudur: kullanıcı tek bir fonksiyonun doğruluğunu değil, parçaların birlikte doğru çalışmasını umursar; dolayısıyla en yüksek güven getirisini birim başına integration testler verir. Piramit ile kupa arasındaki gerilim aslında sağlıklıdır: her ikisi de "yavaş ve kırılgan testleri az tut" ana ilkesinde birleşir, yalnızca orta katmanın ağırlığı konusunda ayrışır.

## Test Seviyeleri: Unit, Integration, E2E

### Unit Test

Unit test, sistemin en küçük anlamlı biriminin (genellikle bir fonksiyon veya sınıf metodu) davranışını dış dünyadan yalıtarak doğrular. Buradaki kritik kelime **yalıtım**dır. İyi bir unit test deterministiktir: aynı girdiye her zaman aynı sonucu verir, bugün de yarın da, senin makinende de CI sunucusunda da.

Unit testin gerçek değeri, en iyi olduğu yerde en iyidir: **karmaşık iş mantığı** ve **saf (pure) fonksiyonlar**. Bir vergi hesaplama fonksiyonu, bir tarih aralığı çakışması kontrolü, bir fiyatlandırma algoritması — bunların onlarca sınır durumunu (edge case) unit testlerle taramak hem hızlı hem güvenilirdir. Şu örnekteki gibi bir indirim hesaplama fonksiyonunu düşünün:

```
İndirim kuralları:
- 100 TL altı: indirim yok
- 100-500 TL: %10
- 500 TL üstü: %20
- Kupon varsa ek %5, ama toplam indirim %25'i geçemez
```

Bu fonksiyonun sınırlarını (99.99, 100.00, 500.01, kupon + üst limit) unit testlerle taramak dakikalar sürer ve regresyona karşı kalıcı bir kalkan oluşturur. Aynı mantığı e2e testle doğrulamaya çalışmak — her senaryo için gerçek bir sipariş oluşturup ödeme akışını çalıştırmak — hem yüzlerce kat yavaş hem de anlamsızdır.

### Integration Test

Integration test, iki veya daha fazla birimin (veya bir birim ile gerçek bir dış sistemin) birlikte doğru çalışıp çalışmadığını doğrular. En yaygın ve değerli örneği, uygulamanızın kodunun **gerçek bir veritabanıyla** konuştuğu testlerdir.

Integration testin varlık sebebi, unit testin en büyük zayıflığından doğar: unit testte dış bağımlılıkları taklit ettiğiniz (mock'ladığınız) için, **taklidin gerçeğe uymadığı** durumları asla yakalayamazsınız. SQL sorgunuzda bir sütun adı yanlış yazılmış olabilir; unit testte veritabanını mock'ladığınız için bu hata görünmezdir. Gerçek veritabanına karşı çalışan bir integration test bunu anında yakalar. İşte kupa modelinin integration katmanına ağırlık vermesinin sebebi budur: birçok gerçek hata birimlerin *kendisinde* değil, aralarındaki *sınır yüzeylerinde* (contract, serialization, sorgu, protokol) yaşar.

Modern pratikte integration testler için gerçek bağımlılıkları hafif ve tekrarlanabilir biçimde ayağa kaldırma teknikleri yaygınlaşmıştır; örneğin testlik container'lar (bir kütüphane olarak Testcontainers bu yaklaşımı somutlaştırır) her test koşusunda temiz bir veritabanı örneği başlatır. Bu, "benim makinemde çalışıyor" sorununu büyük ölçüde ortadan kaldırır çünkü herkes ve CI, birebir aynı bağımlılık sürümüne karşı test eder.

### End-to-End (E2E) Test

E2e test, sistemi gerçek bir kullanıcı gibi, dışarıdan, tüm katmanlar ayaktayken çalıştırır. Bir web uygulamasında bu genellikle gerçek bir tarayıcının otomasyonu demektir (Playwright, Cypress veya Selenium gibi araçlarla). E2e testin cevapladığı soru şudur: "Kullanıcı gerçekten giriş yapıp sepete ürün ekleyip ödeme yapabiliyor mu?"

E2e testler en yüksek güveni verir çünkü gerçeğe en yakın olanlardır — hiçbir şey mock'lanmamıştır. Ama aynı sebepten en pahalı ve en kırılgan olanlardır. Bu yüzden strateji, e2e testleri **kritik kullanıcı yolculuklarıyla** (critical user journeys) sınırlamaktır: kayıt olma, giriş, satın alma gibi işi doğrudan besleyen az sayıda ana akış. Her buton ve her form alanını e2e ile test etmeye kalkmak, piramidi tepesinden şişirmenin reçetesidir.

## Mock, Stub, Fake ve Test Doubles

"Mock" kelimesi günlük konuşmada tüm sahte nesneleri kapsayacak şekilde gevşek kullanılır, ama bu gevşeklik zararlı düşünme alışkanlıklarına yol açar. Gerard Meszaros'un terminolojisiyle bu nesnelerin genel adı **test doubles**'dır (dublörler) ve aralarındaki fark önemlidir.

- **Dummy**: Sadece parametre listesini doldurmak için var olan, hiç kullanılmayan nesne.
- **Stub**: Çağrıldığında önceden belirlenmiş sabit cevaplar döndüren nesne. "Bu veritabanı sorgusu her zaman şu kullanıcıyı döndürsün" demek istediğinizde stub kullanırsınız. Stub, **state** (durum) doğrulaması içindir.
- **Fake**: Gerçek davranışın basitleştirilmiş ama işleyen bir versiyonu. Örneğin gerçek veritabanı yerine bellek içi bir sözlükle çalışan bir repository. Fake gerçekten "çalışır", sadece production'a uygun değildir.
- **Mock**: Beklenen etkileşimleri önceden programladığınız ve test sonunda "bu metot gerçekten çağrıldı mı, kaç kez, hangi argümanlarla" diye **doğruladığınız** nesne. Mock, **behavior** (davranış/etkileşim) doğrulaması içindir.

### Kök Neden: Neden Bu Ayrım Önemli?

Stub ile mock arasındaki fark yüzeyde ince görünür ama testinizin *neyi* doğruladığını belirler. Stub kullandığınızda "sistem doğru sonucu üretti mi?" sorusuna cevap ararsınız. Mock kullandığınızda "sistem doğru etkileşimi *yaptı* mı?" sorusuna cevap ararsınız. İkincisi tehlikeli bir tuzak barındırır: **implementasyona bağımlı test**. Eğer testiniz "şu servis, tam olarak şu üç metodu şu sırayla çağırmalı" diye doğruluyorsa, kodun *davranışı* aynı kalsa bile *iç yapısını* değiştirdiğinizde test kırılır. Bu tür testler refactoring'i cezalandırır; oysa iyi test refactoring'i güvenli kılmalıdır.

### Mock'un Meşru ve Meşru Olmayan Kullanımı

Mock'lamanın altın kuralı şudur: **sahip olmadığınız ve kontrol etmediğiniz sınırları mock'layın**. Üçüncü parti bir ödeme sağlayıcısına yapılan HTTP çağrısı, bir e-posta gönderim servisi, saat/zaman, rastgele sayı üreteci — bunları mock'lamak mantıklıdır çünkü gerçeklerini her testte çalıştırmak yavaş, pahalı, kararsız (non-deterministic) veya yan etkilidir (gerçekten e-posta göndermek istemezsiniz).

Buna karşılık **kendi iç mantığınızı aşırı mock'lamak** en yaygın hatalardan biridir. İki iç sınıf arasındaki her etkileşimi mock'larsanız, ortaya "tautolojik test" çıkar: test yalnızca kodun yazdığınız gibi yazıldığını doğrular, doğru olduğunu değil. Böyle testler yeşil kalır ama gerçek entegrasyon hatalarını asla yakalamaz. Bu, güvenlik hissi veren ama güvenlik vermeyen en aldatıcı durumdur.

Ayrıca **mock drift** (mock kayması) sorunu vardır: mock'ladığınız dış servisin gerçek davranışı zamanla değişir (API bir alanı artık farklı formatta döndürür), ama sizin mock'unuz eski hali taklit etmeye devam eder. Testleriniz yeşildir, production ise kırıktır. Bu riski azaltmak için **contract testing** (sözleşme testi) yaklaşımı vardır: tüketici ile sağlayıcı, üzerinde anlaştıkları sözleşmeyi otomatik olarak doğrular, böylece mock'ların gerçeğe sadık kaldığı garanti altına alınır.

## Flaky Testler: Sinsi Güven Katili

Flaky (kararsız) test, kod hiç değişmediği halde bazen geçen, bazen kalan testtir. Yüzeyde küçük bir sinir bozukluğu gibi görünür; gerçekte ise bir test paketinin en yıkıcı hastalığıdır.

### Kök Neden: Neden Flakiness Öldürücüdür?

Flaky testlerin asıl zararı yakaladıkları veya kaçırdıkları hatalar değildir; **güveni aşındırmalarıdır**. Bir test rastgele kırılmaya başladığında, geliştiriciler onu ciddiye almayı bırakır. "Ha, yine o flaky test, tekrar çalıştır geçer" refleksi yerleşir. Ama bu refleks yerleştiği anda, o testin *gerçek* bir hatayı yakaladığı gün de aynı umursamazlıkla "tekrar çalıştır" denecektir. Yani flaky test yalnızca kendini değil, tüm test paketinin sinyal değerini zehirler. Kırık camlar teorisi gibidir: bir kararsız test tolere edilirse, kısa sürede on tanesi olur ve yeşil bir build'in artık hiçbir anlamı kalmaz.

### Flakiness'in Kök Sebepleri

Flaky testlerin neredeyse tamamı **gizli non-determinizm** kaynaklıdır. En yaygın sebepler:

- **Zamanlama ve async yarışları (race condition)**: Test, bir asenkron işlemin bitmesini "yeterince uzun bir sleep" ile bekler. Makine yavaşladığında sleep yetmez, test kırılır. Doğru çözüm sabit süre beklemek değil, **koşula dayalı bekleme** (belirli bir eleman görünene veya belirli bir durum sağlanana kadar bekle) kullanmaktır.
- **Test sırası bağımlılığı**: Bir test, önceki testin bıraktığı state'e (paylaşılan veritabanı kaydı, global değişken) gizlice bel bağlar. Testler farklı sırada veya paralel koştuğunda kırılır. Çözüm: her testin kendi verisini kurup temizlemesi, izolasyon.
- **Zaman ve saat**: `now()` kullanan testler gece yarısında, ay sonunda, saat değişiminde veya farklı zaman diliminde kırılır. Çözüm: saati enjekte edilebilir bir bağımlılık yapıp testte sabitlemek.
- **Sıralama varsayımı**: Bir veritabanı sorgusunun sonucunu `ORDER BY` olmadan belirli bir sırada beklemek. Veritabanı sırayı garanti etmez.
- **Dış bağımlılıklar**: Gerçek bir ağ servisine giden test, o servis yavaşladığında veya kesildiğinde kırılır.

### Flaky Testlerle Doğru Mücadele

Yanlış yaklaşım, flaky testi otomatik "retry" (yeniden dene) ile örtbas etmektir. Retry bazen operasyonel bir zorunluluktur ama körü körüne uygulanırsa **semptomu gizleyip hastalığı büyütür** — çünkü bazı flakiness gerçek bir race condition'ın habercisidir ve bu, production'da gerçek kullanıcıyı da etkileyecek bir hatadır. Doğru yaklaşım flaky testleri tespit edip **karantinaya almak** (ana sinyalden ayırmak), kök sebebi bulmak ve düzeltmek veya silmektir. Kararsız bir test, hiç test olmamasından daha kötüdür çünkü hem güven vermez hem de gürültü üretir.

## Kod Kapsama (Coverage): Faydalı Ama Aldatıcı Metrik

Kod kapsama, testleriniz çalışırken kaynak kodun ne kadarının **çalıştırıldığını** ölçen bir metriktir. Satır kapsama (line coverage), dal kapsama (branch coverage) ve daha katı olan mutation coverage gibi çeşitleri vardır.

### Kök Neden: Coverage Aslında Neyi Ölçer, Neyi Ölçmez?

Kapsamanın en kritik ve en yanlış anlaşılan gerçeği şudur: **kapsama, kodun çalıştırıldığını ölçer, doğrulandığını değil.** Bir satırın "kapsandı" sayılması için test sırasında o satırın *çalışması* yeterlidir; o satırın ürettiği sonucun bir `assert` ile *kontrol edilmesi* gerekmez. Bunun somut sonucu şudur: hiç `assert` içermeyen, sadece fonksiyonu çağırıp sonucu görmezden gelen bir test bile yüzde 100 kapsama üretebilir. Böyle bir test hiçbir şeyi doğrulamaz ama metrik yeşil yanar.

Dal kapsaması satır kapsamasından daha bilgilendiricidir çünkü sadece satırların çalışıp çalışmadığına değil, `if` koşulunun hem doğru hem yanlış dalının denenip denenmediğine bakar. Yine de temel yanılgı sürer: dal kapsaması da çalıştırmayı ölçer, doğrulamayı değil.

Bu yüzden kapsamanın en dürüst yorumu **negatif** yöndedir: düşük kapsama size *kesinlikle* test edilmemiş kod olduğunu söyler ve bu değerli bir uyarıdır. Ama yüksek kapsama size testlerin *iyi* olduğunu söylemez; sadece kodun çoğunun çalıştırıldığını söyler. Yani coverage iyi bir "eksik" dedektörüdür, kötü bir "kalite" ölçeridir.

### Coverage Hedefi Bir Amaç Haline Gelince: Goodhart Yasası

"Yüzde 100 coverage" zorunluluğu getiren ekipler tehlikeli bir tuzağa düşer. Goodhart Yasası'nın dediği gibi: "Bir ölçüt hedef haline geldiğinde, iyi bir ölçüt olmaktan çıkar." Coverage yüzdesi zorunlu bir kapı (quality gate) yapıldığında, geliştiriciler yüzdeyi yükseltmek için `assert`'sız, anlamsız testler yazmaya başlar. Metrik yeşile döner, gerçek güven ise hiç artmaz, hatta bakım yükü yüzünden azalır. Bu, ölçmek istediğiniz şeyi ölçmeyi bırakıp ölçütü optimize etmenin klasik örneğidir.

Daha güçlü bir alternatif **mutation testing**'dir (mutasyon testi). Bu teknik kaynak koda kasıtlı küçük hatalar (mutantlar) enjekte eder — bir `+`'yı `-` yapmak, bir `>`'yi `>=` yapmak gibi — ve testlerinizin bu hatayı yakalayıp yakalamadığına (mutantı "öldürüp" öldürmediğine) bakar. Eğer kodu bozdunuz ve hiçbir test kırılmadıysa, o kod satırı "kapsanmış" görünse bile **gerçekte doğrulanmıyor** demektir. Mutation testing, `assert`'siz testlerin blöfünü açığa çıkarır; bu yüzden coverage'dan çok daha dürüst bir kalite sinyalidir. Bedeli ise hesaplama maliyetidir: her mutant için test paketini çalıştırmak gerektiğinden yavaştır ve genellikle kritik modüllere odaklı uygulanır.

## Yaygın Hatalar ve Anti-Pattern'ler

**Testleri implementasyona kilitlemek.** İç yapının her ayrıntısını mock'larla ve etkileşim doğrulamalarıyla sabitlerseniz, davranış aynı kalırken yapıyı değiştirmek testleri kırar. Testler, refactoring'i güvenli kılmak yerine engel haline gelir. İlke: **davranışı test et, implementasyonu değil.**

**Test kodunu ikinci sınıf vatandaş görmek.** Kopyala-yapıştır, sihirli sabitler, anlaşılmaz kurulum blokları... Test kodu da bakılır kod olduğu unutulunca test paketi zamanla çürür ve ekip ondan korkmaya başlar. Test kodu üretim kodu kadar özenle yazılmalıdır.

**Her şeyi e2e ile test etmek.** Sınır durumlarını en yavaş ve en kırılgan katmanda taramak; hem israf hem de flakiness kaynağıdır. Sınır durumları unit'e, entegrasyon noktaları integration'a, kritik akışlar e2e'ye aittir.

**Testleri düşünmeden retry ile geçirmek.** Kararsızlığı gizlemek, gerçek bir race condition'ı production'a taşımak demek olabilir.

**Coverage yüzdesini kutsamak.** Sayıyı hedef yapıp `assert`'siz testlerle şişirmek; ölçülen şeyi anlamsızlaştırır.

**Testleri paylaşılan, kirli state üzerine kurmak.** İzolasyonsuz testler sıra bağımlılığı ve flakiness üretir; her test kendi dünyasını kurup yıkmalıdır.

## En İyi Pratikler

**Piramidi kılavuz al, dogma yapma.** Çok sayıda hızlı unit test, sağlam bir integration katmanı, az sayıda kritik e2e test genel olarak sağlıklı bir dağılımdır. Mimarinize göre orta katmanın ağırlığını ayarlayın; mikroservis ağırlıklı bir sistemde integration'a daha çok yaslanmak makuldür.

**Testler hızlı, izole ve deterministik olsun.** Hız geri bildirim döngüsünü kısaltır; izolasyon hata lokalizasyonunu keskinleştirir; determinizm güveni korur. Bu üçü bir test paketinin sağlık göstergeleridir.

**Davranışı doğrula, iç yapıyı değil.** Testin bir kullanıcının veya bir modülün *dışarıdan gözlemlenebilir* davranışına odaklanması, hem daha anlamlı hem de refactoring'e dayanıklıdır.

**Sadece sahip olmadığın sınırları mock'la.** Dış servisler, zaman, rastgelelik gibi kontrol edemediğin ve yan etkili şeyleri taklit et; kendi iç mantığını mümkün olduğunca gerçek bileşenlerle test et.

**Mock'ları gerçeğe sadık tut.** Dış bağımlılıkları mock'larken contract testing ile mock'ların gerçek davranışa uygunluğunu doğrula; mock drift'i sessizce production hatasına dönüşmesin.

**Flaky testi asla normalleştirme.** İlk flaky belirtisinde tespit et, karantinaya al, kök sebebini bul. Retry'ı bir görmezden gelme aracı değil, bilinçli ve ölçülen bir operasyonel karar olarak kullan.

**Coverage'ı pusula olarak kullan, hedef olarak değil.** Düşük kapsama alanlarını gözden geçir ama yüzde peşinde koşma. Gerçek kalite sinyali için kritik modüllerde mutation testing'i değerlendir.

**Testi kod tabanının birinci sınıf parçası yap.** Okunur, bakımlı, anlamlı isimlendirmeye sahip testler; ekibin değişikliği güvenle yapmasını sağlayan asıl varlıktır.

## Sonuç

Test stratejisi, özünde bir **güven ekonomisidir**. Sınırlı bütçeyle mümkün olan en yüksek güveni satın almaya çalışırız. Piramit bize bu bütçeyi seviyelere nasıl dağıtacağımızı; mock ve test doubles ayrımı neyi yalıtıp neyi gerçekten test edeceğimizi; flaky testlerle mücadele güven sinyalimizi nasıl temiz tutacağımızı; coverage metriği ise nerelerin karanlıkta kaldığını gösterir — ama asla kalitenin kendisini garanti etmez. İyi bir test stratejisi bu araçların hiçbirini kutsamaz, hepsini birer ödünleşim olarak görür ve her kararı "bu bana hangi güveni, hangi maliyetle kazandırıyor?" sorusuyla verir. Testin amacı yeşil bir ekran değil, değişikliği korkusuzca yapabilme özgürlüğüdür.
