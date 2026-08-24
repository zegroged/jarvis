# Programlama Paradigmaları

Programlama paradigması, bir programın nasıl yapılandırıldığını ve bir hesaplamanın nasıl ifade edildiğini belirleyen temel bir düşünce biçimidir. Bir dilin sözdiziminden (syntax) daha derin bir kavramdır; problemi zihinde nasıl parçalara ayırdığınızı, durumu (state) nasıl yönettiğinizi ve kodun akışını nasıl kurguladığınızı tanımlar. Aynı problemi imperative, nesne yönelimli (OOP), fonksiyonel veya bildirimsel (declarative) yaklaşımlarla çözebilirsiniz; sonuç aynı olsa bile kodun okunabilirliği, test edilebilirliği, hata eğilimi ve bakım maliyeti çarpıcı biçimde farklılaşır.

Bu makale bu dört ana paradigmayı derinlemesine ele alır. Amaç, her birini birbirinin rakibi gibi göstermek değildir; çünkü modern diller (Python, JavaScript, Rust, Scala, C#) çok paradigmalıdır (multi-paradigm) ve gerçek uzmanlık, hangi problemde hangi yaklaşımın daha az sürtünme yarattığını bilmekte yatar. Önce her paradigmanın kök mantığını, ardından somut örnekleri, tuzakları ve doğru kullanım koşullarını inceleyeceğiz.

## Temel Ayrım: Nasıl mı, Ne mi?

Tüm paradigmaları anlamanın en sağlam çerçevesi tek bir soruyla başlar: Bilgisayara *nasıl* yapacağını mı söylüyorsunuz, yoksa *ne* istediğinizi mi? Bu ayrım imperative ile declarative arasındaki temel çizgidir.

Imperative (buyurgan) yaklaşımda, sonuca ulaşmak için gereken adımları tek tek, sırayla siz yazarsınız: "şu değişkeni sıfırla, döngüye gir, her elemanda şunu topla, döngüden çık". Declarative (bildirimsel) yaklaşımda ise hedeflenen sonucu tanımlar, adımların bulunmasını altyapıya (dil, kütüphane, sorgu motoru) bırakırsınız: "bu listedeki çift sayıların toplamını istiyorum".

Bu ayrımın kök nedeni şudur: İnsan zihni karmaşık adım dizilerini takip etmekte zorlanır, ama bir *niyeti* okumakta çok iyidir. Adımları gizleyebildiğiniz ölçüde kodun okuyucusu "ne olduğunu" hızla kavrar. Ancak adımları gizlemek performans ve kontrol üzerindeki hakimiyeti azaltır. Paradigma seçimi büyük ölçüde bu denge etrafında döner.

OOP ve fonksiyonel programlama bu ana eksenin üzerine oturan iki farklı organizasyon felsefesidir. OOP genellikle imperative köklüdür ama durumu nesneler içinde kapsüller; fonksiyonel programlama ise declarative eğilimlidir ve durumu mümkün olduğunca dışlar.

## Imperative Programlama

### Tanım ve kök mantık

Imperative programlama, hesaplamayı bir dizi komut (statement) olarak ifade eder; bu komutlar programın durumunu adım adım değiştirir. Merkezinde *mutable state* (değiştirilebilir durum) ve *control flow* (denetim akışı: if, for, while, goto) vardır. Bu paradigma bilgisayarın gerçekte nasıl çalıştığına en yakın olanıdır: İşlemci, bellekteki bir konumu okur, bir işlem yapar, sonucu geri yazar. Assembly ve C bu modelin doğrudan yansımalarıdır.

Kök neden burada donanım gerçekliğidir. Von Neumann mimarisinde program, belleği ardışık olarak değiştiren talimatlar dizisidir. Imperative diller bu modeli soyutlamadan çok az uzaklaşır; bu yüzden düşük seviyeli kontrol ve öngörülebilir performans gerektiğinde en doğal seçimdir.

### Somut örnek

Bir listedeki çift sayıların toplamını imperative tarzda hesaplayalım (Python):

```python
def cift_toplami(sayilar):
    toplam = 0
    for s in sayilar:
        if s % 2 == 0:
            toplam += s
    return toplam
```

Burada `toplam` değişkenini biz yönetiyoruz. Döngü sayacı, koşul kontrolü, birikim (accumulation) hepsi açıkça yazılı. Bilgisayara tam olarak *nasıl* yapacağını söylüyoruz.

### Doğru kullanım ve tuzaklar

Imperative yaklaşım, performansın kritik olduğu sıcak yollarda (hot path), gömülü sistemlerde (embedded), sürücü (driver) ve işletim sistemi kodunda, ve donanıma yakın işlemlerde yeri doldurulamaz. Belleğin nasıl kullanıldığını, hangi işlemin ne zaman gerçekleştiğini tam olarak görürsünüz.

En büyük tuzak *paylaşılan değiştirilebilir durumdur* (shared mutable state). Birden fazla fonksiyon veya thread aynı değişkeni değiştirdiğinde, programın davranışı çalışma zamanındaki sıralamaya bağlı hale gelir. Bu, en sinsi hataların kaynağıdır: race condition (birden çok thread'in aynı veriye kontrolsüz erişimiyle oluşan öngörülemez sonuç) ve zamanlamaya bağlı, yeniden üretilmesi zor kusurlar. Kodun bir bölümünü okurken, o değişkenin başka nerede değiştiğini bilmeden davranışını tahmin edemezsiniz. Buna "spooky action at a distance" (uzaktan gizemli etki) denir.

### Yaygın hatalar

- Fonksiyonların gizli yan etkiler (side effects) üretmesi: Bir fonksiyon, imzasında görünmeyen global bir değişkeni değiştirdiğinde çağıran taraf şaşırır.
- Uzun ve iç içe geçmiş döngüler ile koşulların "bilişsel yük" (cognitive load) yaratması; okuyucunun aynı anda çok fazla durumu zihninde tutmak zorunda kalması.
- Off-by-one hataları (döngü sınırlarında bir eksik/fazla ilerleme) gibi manuel indeks yönetiminden doğan klasik kusurlar.

## Nesne Yönelimli Programlama (OOP)

### Tanım ve kök mantık

OOP, veriyi ve o veriyi işleyen davranışı tek bir birimde, *nesnede* (object) birleştirir. Nesneler, sınıflardan (class) üretilir ve dört temel ilke etrafında kurgulanır: encapsulation (kapsülleme), inheritance (kalıtım), polymorphism (çok biçimlilik) ve abstraction (soyutlama).

Kök neden, büyük sistemlerdeki karmaşıklığı yönetme ihtiyacıdır. Imperative kodda durum her yere dağılmışken, OOP bu durumu nesnelerin içine hapseder ve sadece tanımlı arayüzler (interface, public metotlar) üzerinden erişime izin verir. Bu kapsülleme sayesinde bir nesnenin iç işleyişini değiştirebilir, ama dış dünyaya sunduğu sözleşmeyi (contract) koruyabilirsiniz. Böylece sistemin bir parçasındaki değişikliğin dalga etkisi (ripple effect) sınırlanır.

Encapsulation'ın asıl gücü budur: "Bilgi gizleme" (information hiding). Bir `BankaHesabi` nesnesi bakiyeyi private tutar; dışarıdan doğrudan `bakiye = -1000` yapılamaz, ancak `para_cek()` metodu üzerinden, iş kurallarının denetiminden geçerek değiştirilebilir. Bu, geçersiz durumların (invalid state) oluşmasını yapısal olarak engeller.

### Somut örnek

```python
class BankaHesabi:
    def __init__(self, bakiye=0):
        self._bakiye = bakiye  # önek _ ile "private" niyeti

    def para_yatir(self, miktar):
        if miktar <= 0:
            raise ValueError("Miktar pozitif olmali")
        self._bakiye += miktar

    def para_cek(self, miktar):
        if miktar > self._bakiye:
            raise ValueError("Yetersiz bakiye")
        self._bakiye -= miktar

    @property
    def bakiye(self):
        return self._bakiye
```

Burada bakiyeye erişim kontrollüdür. İş kuralları (negatif yatırma yok, bakiyeden fazla çekme yok) nesnenin içinde korunur ve her yerde tekrar yazılmak zorunda kalmaz.

Polymorphism ise farklı türlerin aynı arayüz üzerinden işlenmesini sağlar. Örneğin bir `Sekil` üst tipinin `alan()` metodu; `Daire`, `Dikdortgen` ve `Ucgen` alt tiplerinde farklı biçimde uygulanabilir, ama çağıran kod hepsini aynı şekilde kullanır. Bu, `if tur == "daire" ... elif tur == "dikdortgen"` gibi dallanma zincirlerini ortadan kaldırır.

### Doğru kullanım ve tuzaklar

OOP, belirgin "şeyler" (varlıklar) barındıran alan modellerinde (domain model) parlar: kullanıcılar, siparişler, ürünler, hesaplar. Durum ile davranışın doğal olarak birbirine bağlı olduğu, sistemin uzun ömürlü nesneler etrafında döndüğü yerlerde uygundur. GUI çerçeveleri, oyun motorlarındaki varlıklar ve iş uygulamalarının alan katmanları tipik örnekleridir.

En büyük tuzak, kalıtımın (inheritance) aşırı ve yanlış kullanılmasıdır. Yeni gelenler kalıtımı "kod tekrarını önleme" aracı sanır ve derin, kırılgan hiyerarşiler kurar. Oysa kalıtım güçlü bir *bağlanmadır* (coupling): Alt sınıf, üst sınıfın iç davranışına bağımlı hale gelir. Üst sınıftaki bir değişiklik, farkında olmadan tüm alt sınıfları bozabilir. Bu, "fragile base class" (kırılgan taban sınıf) problemidir. Genel ilke şudur: *kalıtım yerine kompozisyonu tercih et* (composition over inheritance). Bir nesnenin yeteneğini, onu miras almak yerine, o yeteneğe sahip başka bir nesneyi içinde tutarak kazanmak daha esnek ve daha az kırılgandır.

İkinci tuzak, *anemic domain model* (kansız alan modeli) denen anti-desendir: Nesneler yalnızca veri taşır (getter/setter yığını), tüm mantık ise dışarıdaki "servis" sınıflarındadır. Bu, OOP'nin özünü (veri + davranış birlikteliği) ortadan kaldırır ve aslında kılık değiştirmiş prosedürel koda dönüşür.

### Yaygın hatalar

- Her şeyi bir sınıf yapmak: İki fonksiyondan ibaret bir "Manager" veya "Helper" sınıfı çoğu zaman gereksiz seremonidir.
- Liskov Substitution Principle (LSP) ihlali: Bir alt tipin, üst tipin yerine geçtiğinde beklentileri bozması (klasik "kare, dikdörtgenden türer mi?" problemi). Alt tip, üst tipin sözleşmesini daraltmamalıdır.
- Kapsüllemeyi getter/setter ile delik deşik etmek: Her private alan için otomatik getter/setter üretmek, kapsüllemeyi sözde yapar ama gerçekte durumu yine dışarıya açar.

## Fonksiyonel Programlama

### Tanım ve kök mantık

Fonksiyonel programlama (FP), hesaplamayı matematiksel fonksiyonların değerlendirilmesi olarak ele alır ve *değiştirilebilir durumdan ve yan etkilerden kaçınır*. Merkezinde üç kavram vardır: pure function (saf fonksiyon), immutability (değişmezlik) ve first-class functions (fonksiyonların birinci sınıf değer olması).

Pure function, aynı girdiye her zaman aynı çıktıyı veren ve dış dünyada hiçbir gözlenebilir etki bırakmayan fonksiyondur (dosyaya yazmaz, global değişkeni değiştirmez, ekrana basmaz). Kök neden burada *referential transparency* (atıfsal saydamlık) kavramıdır: Bir ifadeyi, sonucuyla değiştirdiğinizde programın anlamı değişmez. Bu özellik akıl yürütmeyi devasa ölçüde basitleştirir; çünkü bir fonksiyonun ne yaptığını anlamak için yalnızca imzasına ve gövdesine bakmak yeterlidir, programın geri kalanının o anki durumunu bilmeniz gerekmez.

Immutability ise verinin oluşturulduktan sonra değiştirilmemesi ilkesidir. Değişiklik gerektiğinde, mevcut veri değiştirilmez; değiştirilmiş bir *kopya* üretilir. Bu, paylaşılan durumu ortadan kaldırdığı için, FP'yi eşzamanlılık (concurrency) için doğal olarak güvenli kılar. Race condition'ın kök nedeni paylaşılan değiştirilebilir durumdur; o durum yoksa problem de yoktur.

### Somut örnek

Aynı çift-sayı toplamını fonksiyonel tarzda yazalım:

```python
def cift_toplami(sayilar):
    return sum(s for s in sayilar if s % 2 == 0)
```

Burada döngü sayacı, biriktirme değişkeni yok. Veriyi bir dönüşümler zinciriyle (filtrele, topla) ifade ediyoruz. Daha da açık bir fonksiyonel biçim, fonksiyonların değer gibi taşınmasını gösterir:

```python
from functools import reduce

ciftler = filter(lambda s: s % 2 == 0, sayilar)
toplam = reduce(lambda a, b: a + b, ciftler, 0)
```

`filter`, `map`, `reduce` gibi higher-order functions (yüksek mertebeli fonksiyonlar) başka fonksiyonları argüman olarak alır. Bu, davranışı veri gibi paketleyip aktarabilmeyi sağlar ve declarative bir ifade gücü kazandırır.

### Doğru kullanım ve tuzaklar

FP, veri dönüşümü ağırlıklı işlerde (data transformation pipeline'ları, ETL, analitik), eşzamanlı ve paralel sistemlerde, ve doğruluğun kritik olduğu alanlarda (finansal hesaplama, derleyiciler) güçlüdür. Pure fonksiyonlar test etmesi en kolay birimlerdir: girdiyi ver, çıktıyı doğrula; mock, kurulum (setup), temizleme (teardown) gerekmez.

Tuzak şudur: Gerçek dünya yan etkilerle doludur. Bir programın er ya da geç dosyaya yazması, ağ isteği yapması, ekrana bir şey basması gerekir. Yan etkileri tamamen yok edemezsiniz; onları *kenara itmeyi* (push to the edges) amaçlarsınız. İdeal mimari, saf bir çekirdek (functional core) ile onu saran ince bir yan-etkili kabuktan (imperative shell) oluşur. Yeni başlayanlar ya yan etkileri her yere dağıtarak FP'nin faydasını kaybeder, ya da her şeyi saf tutmaya çalışıp monad gibi ileri soyutlamalarda gereksiz karmaşıklık üretir.

İkinci tuzak performanstır. Immutability, her değişiklikte kopya üretmek anlamına gelebilir; bu, dikkatsiz kullanıldığında bellek ve zaman maliyeti doğurur. Modern FP dilleri bunu *persistent data structures* (kalıcı veri yapıları) ve structural sharing (yapısal paylaşım) ile hafifletir: Kopya, değişmeyen kısımları eskisiyle paylaşır, yalnızca değişen dalları yeniden oluşturur.

### Yaygın hatalar

- "Pure" sandığı fonksiyonun gizlice global durum okuması veya günün saatine / rastgele sayıya bağlı olması; bu, atıfsal saydamlığı bozar.
- Aşırı soyutlama: Basit bir döngüyü, okunması zorlaşan iç içe higher-order function zincirine çevirmek. Amaç netlik olmalı, akademik gösteriş değil.
- Recursion'ı (özyineleme) tail-call optimizasyonu olmayan bir dilde derin veri üzerinde kullanıp stack overflow'a yol açmak.

## Declarative Programlama

### Tanım ve kök mantık

Declarative programlama, *ne* istendiğini tanımlayıp *nasıl* yapılacağını altyapıya bırakan geniş bir şemsiyedir. Fonksiyonel programlama declarative'in bir alt kümesi sayılabilir, ama en saf declarative örnekler genellikle alana özgü dillerdir (domain-specific languages): SQL, HTML/CSS, Prolog, Terraform gibi altyapı-kod (infrastructure-as-code) araçları ve React gibi UI kütüphaneleri.

Kök neden, soyutlama düzeyini yükselterek "nasıl" ayrıntılarını uzman bir motora devretmektir. SQL'de `SELECT` yazarken, veritabanının hangi index'i kullanacağını, hangi join algoritmasını (nested loop, hash join, merge join) seçeceğini, satırları hangi sırada okuyacağını siz belirtmezsiniz. Bunu *query optimizer* (sorgu iyileştirici) yapar; üstelik verinin dağılımına ve istatistiklerine bakarak çoğu zaman sizin elle yazacağınızdan daha iyi bir plan bulur.

### Somut örnek

```sql
SELECT musteri_adi, SUM(tutar) AS toplam
FROM siparisler
WHERE tarih >= '2026-01-01'
GROUP BY musteri_adi
HAVING SUM(tutar) > 1000
ORDER BY toplam DESC;
```

Bu ifade, sonucun *ne* olması gerektiğini eksiksiz tanımlar ama tek bir döngü, tek bir index seçimi içermez. Aynı işi imperative yazsaydınız yüzlerce satır ve elle optimize edilmiş veri erişimi gerekirdi.

React'te de benzer bir düşünce vardır: Arayüzün, belirli bir duruma karşılık *nasıl görünmesi gerektiğini* tanımlarsınız (declarative UI); DOM'u adım adım güncelleme (imperative DOM manipülasyonu) işini çerçeve üstlenir.

### Doğru kullanım ve tuzaklar

Declarative yaklaşım, olgun ve iyi anlaşılmış bir alanda (veri sorgulama, arayüz tanımı, yapı yönetimi, altyapı sağlama) muazzam üretkenlik sağlar. Kod kısa, niyet açık, hata yüzeyi küçüktür.

En büyük tuzak, soyutlamanın *sızması*dır (leaky abstraction). "Nasıl" gizlenmiştir, ta ki performans sorunu çıkana kadar. Yavaş bir SQL sorgusunu düzeltmek için query optimizer'ın altında ne olduğunu (execution plan, index kullanımı, kardinalite tahmini) anlamak zorunda kalırsınız. Yani declarative kod yazmak kolaydır ama onu *hata ayıklamak* (debug) çoğu zaman altındaki imperative gerçekliği bilmeyi gerektirir. Soyutlamanın sınırlarını bilmeden kullanmak, çalışma zamanında sürpriz maliyetler doğurur.

İkinci tuzak, declarative aracın ifade sınırına dayanmaktır: Alanına uygun olmayan mantığı zorla declarative biçime sokmaya çalışmak (örneğin karmaşık prosedürel iş akışını salt SQL ile kotarmak) okunması ve bakımı imkânsız yapılara yol açar.

### Yaygın hatalar

- Execution plan'a hiç bakmadan yavaş sorgu yazmak; index eksikliğini fark etmemek.
- Declarative aracı, tasarlandığı alan dışında zorlamak.
- Soyutlamaya "sihir" gibi güvenip sınırlarını test etmemek; ölçek büyüdüğünde gizli maliyetlerin patlaması.

## Ne Zaman Hangisi? Karar Çerçevesi

Paradigmalar birbirinin düşmanı değildir; farklı problem sınıfları için farklı araçlardır. Kararı yönlendiren birkaç güçlü sezgi vardır.

**Problem "şeyler" mi, yoksa "dönüşümler" mi?** Alan doğal olarak durum taşıyan, kimliği olan, zaman içinde yaşayan varlıklardan oluşuyorsa (bir oyundaki karakterler, bir sistemdeki kullanıcı oturumları), OOP'nin kapsülleme ve polymorphism güçleri işe yarar. Problem esas olarak "veri gir, dönüştür, veri çık" biçimindeyse (raporlama, analitik, derleme), fonksiyonel akış daha temiz ve test edilebilir olur.

**Eşzamanlılık ne kadar kritik?** Çok çekirdekli ve paralel işlemenin ağır bastığı, paylaşılan durumun race condition riski taşıdığı yerlerde immutability ve pure fonksiyonlar (FP) baştan güvenli bir zemin sunar. Durumu paylaşmazsanız, kilitlemeyle (locking) uğraşmazsınız.

**Performans ve donanım kontrolü ne kadar kritik?** Gömülü sistem, sürücü, gerçek zamanlı düşük gecikmeli yol ise imperative kontrol vazgeçilmezdir; her byte ve her cycle görünür olmalıdır.

**Alan olgun ve iyi tanımlı mı?** Veri sorgulama, arayüz, altyapı gibi çözülmüş alanlarda declarative bir DSL, elle yazacağınız her şeyden daha kısa ve daha sağlam olur.

Gerçek uzmanlıkta bu paradigmalar tek bir kod tabanında iç içe geçer. Tipik ve sağlıklı bir mimari şöyledir: dışta iş varlıklarını modelleyen bir OOP katmanı; içinde iş kurallarını uygulayan pure fonksiyonlardan oluşan bir functional core; verinin diskten geldiği yerde declarative SQL; ve performansın kritik olduğu dar bir sıcak yolda elle optimize edilmiş imperative kod. Buna genellikle "functional core, imperative shell" denir ve her paradigmayı en iyi olduğu yerde kullanmanın somut ifadesidir.

## En İyi Pratikler

- **Paradigmayı probleme göre seç, modaya göre değil.** "Her şey nesne olmalı" veya "her şey saf olmalı" gibi dogmalar, uygun olmayan yerde sürtünme yaratır. Aracı işe uydurun, işi araca değil.

- **Durumu bilinçli yönet.** Mutable state'i mümkün olduğunca aza indirin ve nerede olduğunu net biçimde işaretleyin. Değişebilen her durum, gelecekteki bir hatanın potansiyel yuvasıdır.

- **Yan etkileri kenara it.** Programın çekirdeğini saf ve öngörülebilir tutun; dosya, ağ, veritabanı gibi yan etkileri ince bir dış kabukta toplayın. Bu, hem test edilebilirliği hem de akıl yürütmeyi kolaylaştırır.

- **Kalıtım yerine kompozisyonu tercih et.** OOP kullanırken derin hiyerarşilerden kaçının; davranışı miras almak yerine, davranış sahibi nesneleri birleştirin.

- **Soyutlamanın sınırını bil.** Declarative araçlar güçlüdür ama sihir değildir. En azından bir kez altına inip nasıl çalıştığını (SQL için execution plan, çerçeveler için render döngüsü) anlayın; performans sorunları çıktığında bu bilgi zorunlu hale gelir.

- **Okunabilirliği zekâya tercih et.** İster fonksiyonel zincir olsun ister sınıf hiyerarşisi, kodun bir sonraki okuyucusu (çoğu zaman altı ay sonraki siz) niyeti hızla kavrayabilmelidir. Gösterişli soyutlama, anlaşılır koddan her zaman daha kötüdür.

- **Çok paradigmalı düşün.** Modern diller zaten çok paradigmalıdır. Uzmanlık, tek bir paradigmaya sadakat değil; her birinin güçlü olduğu yeri görüp doğru anda doğru olanı seçebilme esnekliğidir.

Sonuç olarak programlama paradigmaları, kodu düzenlemenin farklı zihinsel modelleridir. Imperative kontrol verir, OOP karmaşıklığı kapsüller, fonksiyonel öngörülebilirlik ve güvenli eşzamanlılık sağlar, declarative ise ifade gücünü ve üretkenliği yükseltir. Her birinin bir bedeli ve bir armağanı vardır. İyi mühendis, bu bedelleri ve armağanları tanır ve verdiği her kararın arkasındaki "neden"i açıklayabilir.
