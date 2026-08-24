# SOLID İlkeleri: Nesne Yönelimli Tasarımın Beş Temel Direği

## Giriş ve Tanım

SOLID, nesne yönelimli tasarımda (OOP) sürdürülebilir, değiştirilebilir ve genişletilebilir yazılım üretmek için formüle edilmiş beş tasarım ilkesinin baş harflerinden oluşan bir kısaltmadır. İlkelerin çoğu Robert C. Martin (yaygın adıyla "Uncle Bob") tarafından 2000'li yılların başında derlenmiş ve popülerleştirilmiş, kısaltma ise Michael Feathers tarafından önerilmiştir. Beş ilke şunlardır:

- **S** — Single Responsibility Principle (Tek Sorumluluk İlkesi)
- **O** — Open/Closed Principle (Açık/Kapalı İlkesi)
- **L** — Liskov Substitution Principle (Liskov Yerine Geçme İlkesi)
- **I** — Interface Segregation Principle (Arayüz Ayrımı İlkesi)
- **D** — Dependency Inversion Principle (Bağımlılığın Tersine Çevrilmesi İlkesi)

Bu ilkelerin her biri bağımsız bir kural gibi görünse de, hepsi tek bir ortak amaca hizmet eder: **gevşek bağlılık** (loose coupling) ve **yüksek uyum** (high cohesion). Yani bir sistemin parçalarının birbirine mümkün olduğunca az bağımlı olması, ama her parçanın kendi içinde anlamlı bir bütün oluşturması. Bu makalede her ilkeyi tek tek ele alacak, ilkenin neden var olduğunu (kök neden), nasıl çalıştığını, somut örneklerle nasıl uygulandığını ve hangi tuzaklara düşülmemesi gerektiğini inceleyeceğiz.

## Neden SOLID? Kök Neden ve Motivasyon

SOLID'i anlamadan önce hangi problemi çözdüğünü anlamak gerekir. Yazılım, doğası gereği zamanla değişir: yeni gereksinimler gelir, hatalar düzeltilir, ölçek büyür. Değişmeyen tek şey değişimin kendisidir. Kötü tasarlanmış bir kod tabanında küçük bir değişiklik yapmak, birbirine görünmez ipliklerle bağlı düzinelerce yeri kırar. Martin bu tür kod tabanlarını üç semptomla tanımlar:

- **Katılık (rigidity):** Bir değişiklik zincirleme başka değişiklikleri zorunlu kılar; küçük bir istek büyük bir çabaya dönüşür.
- **Kırılganlık (fragility):** Bir yerde yapılan değişiklik, mantıksal olarak ilgisiz görünen başka yerleri bozar.
- **Hareketsizlik (immobility):** Bir modülü başka bir projede yeniden kullanmak, taşınması gereken bağımlılıkların ağırlığı yüzünden imkânsızlaşır.

Bu üç semptomun ortak kök nedeni **sıkı bağlılıktır** (tight coupling). Modüller birbirinin somut (concrete) ayrıntılarına bağımlı olduğunda, birinin değişmesi diğerini etkilemek zorunda kalır. SOLID ilkeleri esasen bu bağımlılıkların yönünü, biçimini ve dozunu düzenleyen kurallardır. Bağımlılık asla tümüyle ortadan kalkmaz; amaç onu **soyutlamalar üzerinden, tek yönlü ve az sayıda** hâle getirmektir. İşte "gevşek bağlılık" tam olarak budur.

## 1. Single Responsibility Principle — Tek Sorumluluk İlkesi

### Tanım

Bir sınıfın (veya modülün) **değişmek için yalnızca tek bir nedeni** olmalıdır. Martin bu ilkeyi zamanla şöyle keskinleştirdi: bir modül, tek bir **aktöre** (paydaş grubuna) karşı sorumlu olmalıdır.

### Kök Neden ve Çalışma Mantığı

"Tek sorumluluk" ifadesi çoğu zaman yanlış anlaşılır; sanki bir sınıf yalnızca tek bir metod yapmalıymış gibi okunur. Oysa ilkenin özü "sorumluluk = değişme nedeni" denklemidir. Farklı paydaşlar farklı gereksinimlerle gelir. Örneğin muhasebe departmanının bir ücret hesaplama mantığını değiştirmesi ile İK departmanının çalışma saati raporunu değiştirmesi, tamamen farklı nedenlerdir. İki sorumluluk aynı sınıfta buluşursa, birini değiştirmek diğerini tehlikeye atar — bu tam olarak yukarıda bahsettiğimiz kırılganlıktır.

### Somut Örnek

Aşağıdaki sınıf üç ayrı sorumluluğu bir araya getiriyor:

```python
class Calisan:
    def maas_hesapla(self):
        # muhasebe departmanının kuralları
        ...
    def calisma_saati_raporu(self):
        # İK departmanının kuralları
        ...
    def veritabanina_kaydet(self):
        # veritabanı yönetiminin kuralları
        ...
```

Burada üç farklı aktör (muhasebe, İK, DBA) tek bir sınıfta çakışıyor. Muhasebenin maaş formülünü değiştirmesi, yanlışlıkla raporlama mantığını etkileyebilir. Doğru yaklaşım her sorumluluğu ayırmaktır:

```python
class MaasHesaplayici:
    def hesapla(self, calisan): ...

class SaatRaporlayici:
    def rapor(self, calisan): ...

class CalisanDeposu:
    def kaydet(self, calisan): ...
```

Artık her sınıfın değişmesi için tek bir neden ve tek bir paydaş vardır.

### Tuzaklar ve Yaygın Hatalar

- **Aşırı bölme:** Her metodu ayrı sınıfa koymak, ilkenin ruhu değildir. Bu, "anemik" bir tasarıma ve gereksiz karmaşıklığa yol açar. Ölçüt, "kaç metod" değil, "kaç değişme nedeni"dir.
- **"Tanrı sınıfı" (God object):** Her şeyi yapan devasa sınıflar, ilkenin en sık ihlalidir. Bir sınıf adını "...Manager", "...Helper", "...Util" koyuyorsanız, genellikle sorumlulukların bulanıklaştığının işaretidir.

## 2. Open/Closed Principle — Açık/Kapalı İlkesi

### Tanım

Yazılım varlıkları (sınıflar, modüller, fonksiyonlar) **genişletmeye açık, ama değiştirmeye kapalı** olmalıdır. Yani yeni davranış eklerken var olan, test edilmiş ve çalışan kodu değiştirmek zorunda kalmamalısınız.

### Kök Neden ve Çalışma Mantığı

İlk bakışta bu bir paradoks gibi görünür: bir şeyi hem değiştirmeden hem de davranışını genişleterek nasıl büyütebilirsiniz? Cevap **soyutlama ve polimorfizmde** yatar. Çalışan koda dokunmak risklidir; her dokunuş yeni hata (regresyon) ihtimali taşır ve o kodun tüm testlerini yeniden geçersiz kılar. İlke der ki: sık değişen davranışları bir soyutlamanın (arayüz veya soyut sınıf) arkasına koy; yeni bir varyant gerektiğinde, var olanı düzenlemek yerine yeni bir uygulama ekle.

Kök neden, "değişimin izole edilmesi"dir. Değişimin nerede olacağını önceden tahmin edip, o ekseni bir genişleme noktası (extension point) hâline getirirsiniz.

### Somut Örnek

Aşağıdaki kod her yeni ödeme türünde `if/elif` bloğunun düzenlenmesini gerektirir — yani değiştirmeye açıktır:

```python
class OdemeIslemci:
    def ode(self, tur, tutar):
        if tur == "kredi_karti":
            ...
        elif tur == "havale":
            ...
        elif tur == "kripto":   # her yeni tür buraya eklenir
            ...
```

Açık/Kapalı ilkesine uygun tasarımda her ödeme türü ortak bir arayüzü uygular:

```python
from abc import ABC, abstractmethod

class OdemeYontemi(ABC):
    @abstractmethod
    def ode(self, tutar): ...

class KrediKarti(OdemeYontemi):
    def ode(self, tutar): ...

class Havale(OdemeYontemi):
    def ode(self, tutar): ...

class OdemeIslemci:
    def isle(self, yontem: OdemeYontemi, tutar):
        yontem.ode(tutar)
```

Yeni bir ödeme türü (örneğin `Kripto`) eklemek için `OdemeIslemci` sınıfına hiç dokunmazsınız; yalnızca yeni bir sınıf yazarsınız. Sistem genişlemeye açık, değişmeye kapalıdır.

### Tuzaklar ve Yaygın Hatalar

- **Spekülatif genellik:** Her olası değişimi önceden soyutlamaya çalışmak, gereksiz karmaşıklık yaratır (YAGNI — "You Aren't Gonna Need It" ihlali). İlke, gerçekleşmesi muhtemel değişim eksenleri için düşünülmelidir, her şey için değil. Pratikte, aynı türden ikinci veya üçüncü varyant belirdiğinde soyutlamayı devreye almak sağlıklı bir sezgidir.
- **Yanlış eksen seçimi:** Değişimin hangi eksende olacağını yanlış tahmin ederseniz, soyutlama işe yaramaz ve yine çalışan kodu değiştirmek zorunda kalırsınız.

## 3. Liskov Substitution Principle — Liskov Yerine Geçme İlkesi

### Tanım

Barbara Liskov'un 1987'de formüle ettiği fikirden türeyen bu ilke şunu söyler: bir programda bir üst tipin (base type) nesneleri, alt tiplerinin (subtype) nesneleriyle **programın doğruluğunu bozmadan** değiştirilebilmelidir. Kısaca: alt sınıf, üst sınıfın vaadini çiğnememelidir.

### Kök Neden ve Çalışma Mantığı

Bu ilke, kalıtımın (inheritance) yüzeysel değil davranışsal bir sözleşme olduğunu vurgular. "B, A'nın bir alt sınıfıdır" demek, "B her yerde A gibi davranabilir" demektir. Eğer alt sınıf, üst sınıfın beklenen davranışını daraltıyor, ön koşulları güçlendiriyor veya son koşulları zayıflatıyorsa, o zaman polimorfizm güvenilmez hâle gelir. Açık/Kapalı ilkesi polimorfizme dayandığı için, Liskov ihlali aslında Açık/Kapalı ilkesini de dolaylı olarak yıkar: soyutlamanın arkasındaki uygulamalar birbirinin yerine geçemiyorsa, genişleme noktası çöker.

### Somut Örnek: Klasik Dikdörtgen–Kare Sorunu

Matematiksel olarak kare bir dikdörtgendir; bu yüzden `Kare` sınıfını `Dikdortgen`den türetmek doğal görünür:

```python
class Dikdortgen:
    def genislik_ayarla(self, g): self._g = g
    def yukseklik_ayarla(self, y): self._y = y
    def alan(self): return self._g * self._y

class Kare(Dikdortgen):
    def genislik_ayarla(self, g):
        self._g = g
        self._y = g   # kare olduğu için ikisi de değişir
    def yukseklik_ayarla(self, y):
        self._g = y
        self._y = y
```

Şimdi `Dikdortgen` bekleyen bir fonksiyon düşünün:

```python
def test_alan(d: Dikdortgen):
    d.genislik_ayarla(5)
    d.yukseklik_ayarla(4)
    assert d.alan() == 20   # Dikdortgen için doğru, Kare için 16!
```

`Kare` nesnesi verildiğinde bu doğrulama başarısız olur. `Kare`, `Dikdortgen`in "genişlik ve yükseklik bağımsız ayarlanabilir" vaadini çiğnediği için yerine geçemez. Bu, Liskov ihlalinin klasik örneğidir ve şunu öğretir: kalıtım hiyerarşisi gerçek dünya sınıflandırmasına değil, **davranışsal ikame edilebilirliğe** dayanmalıdır. Çözüm genellikle kalıtım yerine kompozisyon kullanmak veya ortak bir soyut `Sekil` arayüzü tanımlamaktır.

### Tuzaklar ve Yaygın Hatalar

- **`NotImplementedError` fırlatan geçersiz kılmalar:** Alt sınıf, üst sınıftaki bir metodu "bu benim için geçerli değil" diye istisna fırlatarak devre dışı bırakıyorsa, muhtemelen yanlış hiyerarşi kurulmuştur. Klasik örnek: `Kus` sınıfından türeyen `Penguen`in `uc()` metodunda hata fırlatması.
- **Ön/son koşul dengesizliği:** Alt sınıf girdileri üst sınıftan daha katı kabul ediyorsa (ön koşulu güçlendirme) ya da daha zayıf garantiler veriyorsa (son koşulu zayıflatma) ilke ihlal edilir.

## 4. Interface Segregation Principle — Arayüz Ayrımı İlkesi

### Tanım

Hiçbir istemci (client), **kullanmadığı** metodlara bağımlı olmaya zorlanmamalıdır. Yani büyük, "her şeyi içeren" arayüzler yerine, istemciye özel, küçük ve odaklı arayüzler tercih edilmelidir.

### Kök Neden ve Çalışma Mantığı

Bir istemci, ihtiyaç duymadığı metodları da barındıran şişkin bir arayüze bağlandığında, o arayüzdeki hiç kullanmadığı metodların değişmesinden bile etkilenir. Bu gizli bir bağımlılıktır: kullanmadığınız bir şeye kod düzeyinde bağlısınızdır ve derleme/dağıtım zinciri sizi de o değişikliğe ortak eder. Kök neden yine gevşek bağlılıktır; arayüzü bölerek bağımlılık yüzeyini daraltırsınız. İlke aslında Tek Sorumluluk İlkesi'nin arayüz seviyesindeki yansımasıdır: bir arayüz de tek bir uyumlu rolü temsil etmelidir.

### Somut Örnek

Şu "şişman" arayüzü düşünün:

```python
class CokFonksiyonluCihaz(ABC):
    @abstractmethod
    def yazdir(self, belge): ...
    @abstractmethod
    def tara(self, belge): ...
    @abstractmethod
    def faks_gonder(self, belge): ...
```

Sadece yazıcı olan basit bir cihaz bu arayüzü uyguladığında, kullanmadığı `tara` ve `faks_gonder` metodlarını da (çoğu zaman boş ya da istisna fırlatan gövdelerle — dikkat, bu aynı zamanda Liskov ihlalidir) uygulamak zorunda kalır. Doğru yaklaşım, arayüzü rollere göre bölmektir:

```python
class Yazici(ABC):
    @abstractmethod
    def yazdir(self, belge): ...

class Tarayici(ABC):
    @abstractmethod
    def tara(self, belge): ...

class Faks(ABC):
    @abstractmethod
    def faks_gonder(self, belge): ...
```

Artık basit yazıcı yalnızca `Yazici` arayüzünü uygular; çok fonksiyonlu bir cihaz ise üçünü birden uygulayabilir. Her istemci yalnızca gerçekten kullandığı role bağımlı olur.

### Tuzaklar ve Yaygın Hatalar

- **Aşırı parçalama:** Her metodu ayrı bir arayüze koymak da sağlıklı değildir; birbirine ait, uyumlu metodları anlamlı rollerde gruplamak gerekir. Ölçüt, "bu metodları hep birlikte mi kullanan istemciler var?" sorusudur.
- **Şişman arayüzlerin "kolaylık" bahanesi:** "Hepsini tek arayüze koyayım da kolay olsun" düşüncesi kısa vadede pratik görünür, uzun vadede bağımlılık kirliliği yaratır.

## 5. Dependency Inversion Principle — Bağımlılığın Tersine Çevrilmesi İlkesi

### Tanım

İki kural içerir:

1. Üst seviye modüller, alt seviye modüllere bağımlı olmamalıdır; her ikisi de **soyutlamalara** bağımlı olmalıdır.
2. Soyutlamalar ayrıntılara bağımlı olmamalıdır; ayrıntılar soyutlamalara bağımlı olmalıdır.

### Kök Neden ve Çalışma Mantığı

Geleneksel, üstten alta akan tasarımda üst seviye iş mantığı doğrudan alt seviye ayrıntılara (veritabanı, dosya sistemi, harici servis) bağlanır. Bu, bağımlılık okunun "yukarıdan aşağıya", yani iş mantığından ayrıntıya doğru akması demektir. Sorun şudur: en değerli ve en kararlı olması gereken iş mantığı, en oynak ve en teknik ayrıntılara tutsak olur. Bir veritabanı değişikliği, iş kuralını değiştirmeye zorlar.

İlkenin adındaki "tersine çevirme" (inversion) tam olarak bu ok yönünü tersine çevirmeyi anlatır. Bir soyutlama katmanı araya koyduğunuzda, hem üst seviye hem de alt seviye bu soyutlamaya bağımlı hâle gelir. Alt seviye ayrıntı artık soyutlamanın **altına** düşer; ok yönü tersine döner. Bu, üç ilkeyi (Açık/Kapalı, Liskov, Bağımlılık Tersine Çevirme) tek çatı altında birleştiren en güçlü mekanizmadır ve modern mimarilerin (hexagonal/ports-and-adapters, clean architecture) temelidir.

Not: Bağımlılığın Tersine Çevrilmesi (DIP) bir **ilke**, Bağımlılık Enjeksiyonu (Dependency Injection, DI) ise bu ilkeyi hayata geçiren bir **tekniktir**. İkisi karıştırılmamalıdır.

### Somut Örnek

Sıkı bağlı, kötü tasarım:

```python
class MySQLVeritabani:
    def kaydet(self, veri): ...

class SiparisServisi:
    def __init__(self):
        self.db = MySQLVeritabani()   # somut sınıfa doğrudan bağımlılık
    def siparis_olustur(self, siparis):
        self.db.kaydet(siparis)
```

Burada `SiparisServisi` (üst seviye iş mantığı) doğrudan `MySQLVeritabani` (alt seviye ayrıntı) sınıfına yapışmıştır. Veritabanını PostgreSQL'e taşımak ya da testte sahte (mock) bir depo kullanmak imkânsıza yakındır. İlkeye uygun hâli:

```python
class Depo(ABC):
    @abstractmethod
    def kaydet(self, veri): ...

class MySQLDepo(Depo):
    def kaydet(self, veri): ...

class SiparisServisi:
    def __init__(self, depo: Depo):   # soyutlama enjekte edilir
        self.depo = depo
    def siparis_olustur(self, siparis):
        self.depo.kaydet(siparis)
```

Artık `SiparisServisi` yalnızca `Depo` soyutlamasını bilir. Hangi somut deponun geleceğine dışarıdan, yapıcı (constructor) aracılığıyla karar verilir — bu Bağımlılık Enjeksiyonu'dur. Testte `SahteDepo`, üretimde `MySQLDepo` veya `PostgreDepo` verilebilir. İş mantığı ayrıntılardan tamamen bağımsızlaşmıştır.

### Tuzaklar ve Yaygın Hatalar

- **Gereksiz soyutlama:** Her sınıf için bir arayüz üretmek (özellikle tek uygulaması olacak ve değişmesi beklenmeyen sınıflar için) gereksiz dolaylılık (indirection) yaratır. Soyutlama, gerçek bir değişkenlik veya test edilebilirlik ihtiyacı olduğunda değerlidir.
- **DIP'i sadece DI çerçevesi kullanmak sanmak:** Bir DI konteyneri kullanmak, otomatik olarak ilkeye uyduğunuz anlamına gelmez. Somut sınıflara bağımlıysanız, konteyner bunu değiştirmez.

## İlkeler Nasıl Birlikte Çalışır: Gevşek Bağlılığın Bütünsel Resmi

SOLID'in gerçek gücü, ilkeleri tek tek değil bir bütün olarak uyguladığınızda ortaya çıkar. Aralarındaki bağı şöyle özetleyebiliriz:

- **Tek Sorumluluk**, sistemi anlamlı, tek gerekçeli parçalara böler — bağımlılıkların nerede olacağını netleştirir.
- **Arayüz Ayrımı**, bu parçalar arasındaki temas yüzeyini (arayüzleri) mümkün olduğunca dar tutar.
- **Bağımlılığın Tersine Çevrilmesi**, bu dar arayüzler üzerinden bağımlılık okunu ayrıntıdan soyutlamaya çevirir.
- **Açık/Kapalı**, bu soyutlamaların arkasına yeni davranışların çalışan kodu bozmadan eklenebilmesini sağlar.
- **Liskov**, bu soyutlamaların arkasındaki uygulamaların gerçekten birbirinin yerine geçebilmesini garantiler; yoksa polimorfizm ve dolayısıyla Açık/Kapalı çöker.

Görüldüğü gibi beş ilke, "somut ayrıntılar yerine kararlı soyutlamalara bağlan" fikrinin farklı açılardan ifadeleridir. Hepsinin buluştuğu ortak nokta **gevşek bağlılıktır**: bir parçayı değiştirdiğinizde dalga etkisinin (ripple effect) diğer parçalara yayılmaması. Bu da bizi başlangıçtaki katılık, kırılganlık ve hareketsizlik semptomlarından kurtarır.

## En İyi Pratikler ve Kapanış

- **İlkeler amaç değil araçtır.** SOLID'in nihai hedefi değişime dayanıklı yazılımdır; ilkelere körü körüne uymak, aşırı mühendisliğe (over-engineering) yol açabilir. Her soyutlamanın bir bedeli vardır: fazladan dolaylılık, okunması daha zor kod, daha çok dosya. Soyutlamayı gerçek bir değişkenlik sinyali gördüğünüzde ekleyin.
- **YAGNI ve KISS ile dengeleyin.** "Belki ileride lazım olur" diye yapılan soyutlamalar çoğu zaman yanlış eksende olur. Genellikle en sağlıklı yol, ikinci varyant belirdiğinde soyutlamayı devreye almaktır (kural üç: "rule of three").
- **Test edilebilirlik iyi bir pusuladır.** Bir sınıfı izole test etmek zorsa, bu genellikle gizli sıkı bağlılığın işaretidir. Kolay mock'lanabilirlik, çoğunlukla DIP'e iyi uyduğunuzun göstergesidir.
- **İsimlendirmeye dikkat edin.** "Manager", "Helper", "Util", "Processor" gibi belirsiz adlar sıklıkla bulanık sorumlulukların ve ihlallerin habercisidir.
- **Bağlama saygı gösterin.** Küçük bir script'te SOLID'i tam uygulamak gereksiz olabilir; büyük, uzun ömürlü ve çok kişili bir kod tabanında ise hayatidir. İlkelerin değeri, sistemin ömrü ve değişim sıklığıyla doğru orantılıdır.

Sonuç olarak SOLID, ezberlenecek beş kural değil, "değişime nasıl dayanıklı olunur?" sorusunun beş farklı cevabıdır. Hepsi aynı kök fikre bağlanır: somut ayrıntılara değil kararlı soyutlamalara bağımlı olun, bağımlılıkları az ve tek yönlü tutun, her parçanın tek ve net bir gerekçesi olsun. Bu ilkeleri sezgiye dönüştürebildiğinizde, yazdığınız kod yıllar sonra bile korkusuzca değiştirilebilir kalır — ki iyi yazılım mühendisliğinin asıl ölçütü budur.
