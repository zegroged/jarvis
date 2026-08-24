# API Tasarım Kararı: Evrim ve Uyumluluk

## 1. Problem ve bağlam: bu iş gerçekte neyi çözer

Bir API yayına aldığın an, o API artık senin değildir. Onu tüketen istemciler,
mobil uygulamalar, üçüncü parti entegrasyonlar, kendi mikroservislerin, hatta
altı ay önce yazılıp unutulmuş bir cron job'ı senin sahibin olduğun kontratı
kullanmaya başlar. Asıl problem "iyi bir endpoint tasarlamak" değildir; asıl
problem **kontratı yıllar boyunca, sen onu değiştirmek zorunda kaldıkça, tüketen
tarafı kırmadan yaşatabilmektir.** API tasarım kararı dediğimiz şey neredeyse
her zaman bir *evrim* ve *uyumluluk* kararıdır.

Bu iş şu anlarda devreye girer: yeni bir alan (field) ekleyeceksin, bir alanın
tipini değiştirmen gerekiyor, bir endpoint'i emekliye ayıracaksın, bir enum'a
yeni değer ekleyeceksin, bir davranışın (validation kuralı, sıralama, sayfalama)
anlamını değiştireceksin. Bu değişikliklerin her biri masum görünür. "Sadece bir
alan ekliyorum, kimseye zararı olmaz" cümlesi üretimde en pahalı cümlelerden
biridir. Çünkü uyumluluğu kıran şey çoğu zaman *eklediğin* değil, eklerken
farkında olmadan *değiştirdiğin* varsayımdır.

Kıdemli mühendisin buradaki zihinsel modeli şudur: **bir API'nin iki ayrı zamanı
vardır.** Birincisi, senin kod deploy ettiğin an. İkincisi, istemcilerin senin
değişikliğine ayak uydurduğu an. Bu iki zaman arasında bazen dakikalar, bazen
*yıllar* vardır. Mobil dünyada bu fark özellikle acıdır: kullanıcı telefonundaki
üç yıl önceki uygulama sürümü hâlâ senin API'ni çağırıyor olabilir ve o
kullanıcı uygulamayı güncellemeyeceği için o kontratı sonsuza kadar taşımak
zorunda kalabilirsin. Web'de dağıtım senkron olduğu için bu esneklik vardır;
mobilde ve public API'de yoktur. İlk karar noktan bile burasıdır: *kim benim
istemcim ve onları ne kadar hızlı güncelleyebilirim?*

## 2. Metodoloji ve karar ağacı: pro adım adım nasıl ilerler

### Adım 0: Değişikliği "kırıcı mı, değil mi" diye sınıflandır

Her API değişikliğinin önünde durup şu soruyu sorarım: *mevcut bir istemci,
kodunu hiç değiştirmeden benim yeni sürümümle çalışmaya devam eder mi?* Cevap
evet ise geriye dönük uyumlu (backward compatible), hayır ise kırıcı (breaking).

Ama bu soru göründüğünden inceliklidir, çünkü uyumluluğun iki yönü vardır:

- **Geriye dönük uyumluluk (backward):** Yeni sunucu, eski istemciyi kırmaz.
- **İleriye dönük uyumluluk (forward):** Eski sunucu / eski istemci, yeni
  verinin içinden geçebilir. Yani eski istemci, tanımadığı bir alan gördüğünde
  çökmez, onu görmezden gelir.

Acemi sadece birinciyi düşünür. Pro ikincisini de düşünür, çünkü gerçek
sistemlerde veri her iki yönde de akar. Örneğin bir istemci senin verini okuyup,
üstünde değişiklik yapıp, geri PUT eder. Eğer istemci tanımadığı alanları
sessizce düşürüyorsa, o istemci senin yeni eklediğin alanı *silen* bir aktöre
dönüşür. Buna "read-modify-write veri kaybı" denir ve bir alan eklemek gibi
"masum" bir işlemin nasıl veri sildiğinin klasik örneğidir.

### Adım 1: Genişletilebilir varsayılanlar seç

Kırıcı değişiklikten kaçınmanın en ucuz yolu, kırılmayacak şekilde başlamaktır.
Sahada öğrendiğim temel kurallar:

- **Yanıtlar (response) her zaman büyüyebilir, asla küçülemez veya anlam
  değiştiremez.** Bir alan eklemek uyumludur; bir alanı çıkarmak veya tipini
  değiştirmek kırıcıdır.
- **İstekler (request) her zaman esnemeli.** Bilinmeyen alanları reddeden katı
  bir doğrulayıcı (strict validation), gelecekteki her eklemeyi kırıcı yapar.
- **Enum'ları asla kapalı küme (closed set) saymayın.** İstemci koduna
  "bilinmeyen değer gelirse şu olur" davranışı koyulmalı. Yeni bir enum değeri
  eklemek, tüketen taraf "default" dalı yazmadıysa kırıcıdır.
- **Zorunlu alan eklemek her zaman kırıcıdır.** Yeni bir alanı zorunlu yapmak
  istiyorsan, önce opsiyonel olarak ekle, istemciler benimsesin, sonra
  (istemci telemetrisiyle doğrulayarak) zorunlu yap.
- **Boş/eksik ile null'ı ayırt et.** "Alan yok" ile "alan var ama null" farklı
  anlamlara gelir; PATCH semantiğinde bu ayrım hayat kurtarır ya da veri siler.

### Adım 2: "Bu değişiklik gerçekten kırıcıysa" karar ağacı

Kırıcı bir değişiklik yapmam gerektiğine karar verdiğimde şu sırayı izlerim:

1. **Kaçınabilir miyim?** Çoğu zaman kırıcı değişikliği, yeni bir opsiyonel alan
   veya yeni bir endpoint ekleyerek uyumlu bir değişikliğe dönüştürebilirim.
   İlk refleksim her zaman budur. Yeni davranışı eskisinin *yanına* koyarım,
   *yerine* değil.

2. **Additive (eklemeli) yapabilir miyim?** Örneğin `name` alanını `first_name`
   ve `last_name`'e bölmem gerekiyorsa: eskisini silmem. İkisini de tutarım.
   Yazarken ikisini de doldururum, okurken ikisini de sunarım. Eski alanı
   "deprecated" işaretlerim ama yaşatırım.

3. **Versiyonlamam gerekiyor mu?** Eğer değişiklik gerçekten uyumsuzsa ve
   eklemeyle çözülemiyorsa, o zaman versiyonlama devreye girer. Ama versiyonlama
   *son çare*dir, ilk çare değil. Çünkü her versiyon, sonsuza kadar bakım
   yükümlülüğü demektir.

Versiyonlama stratejisi seçerken takas şudur:

- **URL versiyonlama (`/v1/users`, `/v2/users`):** En görünür, en kaba araçlı,
  en anlaşılır. Cache ve yönlendirme (routing) kolaydır. Dezavantajı: her
  "versiyon" tüm yüzeyi kopyalamaya iter, oysa değişen belki tek bir endpoint'tir.
  Pratikte v2'ye geçen çoğu takım yüzeyin %95'ini v1'den aynen kopyalar ve iki
  kopyayı senkron tutmak kâbusa döner.
- **Header/media-type versiyonlama (`Accept: application/vnd.x.v2+json`):** Daha
  temiz, endpoint bazında evrimleşir. Dezavantajı: görünmez, test etmesi ve
  debug etmesi zor, "curl ile hızlı deneyeyim" refleksini kırar.
- **Alan/kaynak bazında evrim (versiyonsuz):** En olgun yaklaşım. Hiç major
  versiyon çıkarmadan, sadece eklemeli değişikliklerle ve deprecation ile
  yaşarsın. Büyük ve başarılı public API'lerin çoğu yıllarca "v1"de kalır.
  Bunu yapabilmek disiplin ister ama bakım maliyeti en düşük olandır.

Benim varsayılan tercihim: **mümkün olduğunca versiyonsuz kal, eklemeli
evrimleş, kırıcı değişikliği zorunlu kılan gerçek bir sebep çıkana kadar major
versiyon açma.**

Buradaki en sık hata, "v2" açmayı bir *çözüm* sanmaktır. v2 açmak sorunu çözmez,
sadece erteler ve ikiye katlar: artık iki kontrat, iki test yüzeyi, iki bakım
hattın vardır ve v1'i kapatana kadar (ki genelde asla kapatamazsın) bu yük
sürer. Deneyimli takımlar v2'ye ancak "domain modeli o kadar temelden değişti ki
eskisini eklemeli evrimle taşımak imkânsız" olduğunda geçer — örneğin kimlik
modelinin, para akışının, veya güvenlik varsayımlarının tümden değiştiği
durumlar. Küçük bir alan değişikliği için asla yeni major versiyon açılmaz;
bunu yapan ekip birkaç yıl sonra beş tane "ölü ama kapatılamayan" versiyonla
boğuşur. Versiyon sayın, teknik borcunun görünür bir sayacıdır.

Bir başka incelik: versiyonlama yaparken bile, iki versiyon *aynı* alttaki veri
modelini paylaşır. Yani v1 ve v2 sadece sunum katmanında (serialization) ayrılır,
altta tek bir kaynak vardır. İki versiyonu iki ayrı veri tablosuyla implemente
etmeye kalkarsan, senkronizasyon problemi API uyumluluğu probleminden çok daha
beter hale gelir. Doğru mimari: tek çekirdek model, versiyona özel ince bir
çeviri (adapter) katmanı. Böylece bir bug'ı iki yerde düzeltmezsin.

### Adım 3: Emeklilik (deprecation) sürecini baştan tasarla

Bir şeyi kaldırmadan önce onu ölçebiliyor olmam gerekir. "Bu alanı kimse
kullanmıyor" cümlesini *veriyle* söyleyebilmeliyim, tahminle değil. Bu yüzden
kırıcı değişiklik kararının bir parçası her zaman şudur: *hangi istemcinin,
hangi sürümün, ne sıklıkla eski davranışı kullandığını görebiliyor muyum?*
Göremiyorsam, önce görünürlük (observability) eklerim, sonra emekliliği
konuşuruz.

## 3. Gerçek örnek üzerinden yürüyüş: bir alan eklemenin veri silmesi

Somut bir senaryo. Bir kullanıcı profili API'miz var. Başlangıçta kaynak şöyle:

```
GET /users/42
{
  "id": 42,
  "email": "ayse@example.com",
  "display_name": "Ayşe"
}
```

Mobil uygulama bu profili gösteriyor. Kullanıcı adını değiştirince uygulama
şunu yapıyor: önce GET ile mevcut profili çeker, `display_name` alanını
değiştirir, sonra tüm nesneyi PUT ile geri gönderir (read-modify-write):

```
PUT /users/42
{
  "id": 42,
  "email": "ayse@example.com",
  "display_name": "Ayşe K."
}
```

Sunucu tarafı basit: gelen gövdeyi alır, kaydı komple değiştirir (replace
semantiği). Şimdiye kadar sorun yok.

### Zafiyetli değişiklik

Ürün ekibi "kullanıcılara telefon numarası ekleyelim" diyor. Backend geliştirici
şunu yapıyor: veritabanına `phone` kolonu ekliyor, response'a `phone` alanını
ekliyor. Kendince güvenli, çünkü "sadece alan ekledim, response büyüdü, geriye
dönük uyumlu." Deploy ediliyor:

```
GET /users/42
{
  "id": 42,
  "email": "ayse@example.com",
  "display_name": "Ayşe K.",
  "phone": "+90 555 111 22 33"
}
```

Kullanıcı telefonunu web arayüzünden ekliyor, mükemmel çalışıyor. Ama iki gün
sonra destek talepleri geliyor: "telefon numaramı kaydediyorum, kayboluyor."

### Teşhis

Sorun mobil istemcide. Mobil uygulamanın eski sürümü `User` modelini üç alanla
tanımlamış: `id`, `email`, `display_name`. Serileştirme (deserialization)
sırasında tanımadığı `phone` alanını sessizce *düşürüyor*. Kullanıcı mobilden
adını değiştirdiğinde read-modify-write döngüsü çalışıyor: eski istemci profili
GET ediyor, `phone` alanını modeline hiç almadığı için elinde olmayan bir alanı,
PUT gövdesinde de göndermiyor:

```
PUT /users/42
{
  "id": 42,
  "email": "ayse@example.com",
  "display_name": "Ayşe"
}
```

Sunucu replace semantiğiyle çalıştığı için, gövdede `phone` olmamasını
"telefonu sil" olarak yorumluyor ve kaydı siliyor. Yani *sunucu tarafında masum
bir alan eklemesi, hiç dokunmadığın bir istemci yüzünden veri kaybına yol
açtı.* İki uyumluluk kararının çarpışması: yeni sunucu geriye dönük uyumlu
sandın ama eski istemci ileriye dönük uyumlu değildi ve replace semantiği bu
ikisini birbirine kırdırdı.

### Düzeltilmiş yaklaşım

Birkaç katmanlı düzeltme var, ve pro bunların *hepsini* düşünür:

**1. Semantik seçimi.** Kısmi güncellemeler için replace (PUT, "gövde neyse
kaynak odur") yerine merge/patch (PATCH, "sadece gönderdiğim alanları değiştir")
semantiği kullanmak bu sınıf hatayı baştan öldürür. PATCH ile eski istemci
`phone` göndermediğinde sunucu onu "değiştirme" olarak yorumlar, "sil" olarak
değil. Burada kritik ayrım şudur: *alanın gövdede olmaması* ile *alanın gövdede
null olması* farklı şeylerdir. "Gönderilmedi = dokunma", "null gönderildi =
temizle". Bu ayrımı koruyabilmek için gövdeyi ham haliyle (hangi anahtarların
*var olduğu* bilgisiyle) işlemek gerekir; nesneyi düz bir tipe deserialize edip
"null mı geldi yoksa hiç mi gelmedi" bilgisini kaybedersen bu ayrımı da
kaybedersin. Bu, birçok statik dilde gerçek bir tuzaktır.

**2. İstemci dayanıklılığı.** İstemci modelleri bilinmeyen alanları *korumalı*.
Ya tam bir "passthrough" (bilinmeyen alanları ayrı bir sözlükte tut ve geri
gönder) ya da hiç değilse read-modify-write yerine sadece değişen alanı gönderen
PATCH kullanmalı. "Tüm nesneyi geri gönder" en kırılgan istemci desenidir.

**3. Sunucu savunması.** Sunucu, bir alanın "yokluğunu" asla otomatik "silme"ye
çevirmemeli, hele hassas verilerde. Kritik alanlar için ayrı, açık niyetli
endpoint'ler (örn. telefonu silmek için ayrı bir işlem) daha güvenlidir.

Bu örnek şunu gösterir: API tasarım kararı hiçbir zaman sadece "şemaya ne
koyayım" değildir. **Semantik (PUT mı PATCH mı), istemci davranışı, ve verinin
tam yolculuğu** birlikte düşünülmek zorundadır. Şemadaki tek satırlık ekleme,
sistemin uçtan uca davranışında bir zincir tepkimesi başlatır.

### İkinci örnek: enum genişletmesi

Bir ödeme API'sinde `status` alanı var: `pending`, `completed`, `failed`.
İstemci kodu şöyle:

```
if status == "completed":
    kullaniciyi_bilgilendir_basarili()
elif status == "failed":
    kullaniciyi_bilgilendir_basarisiz()
else:
    bekleme_ekrani_goster()
```

Bu istemci iyi yazılmış, çünkü bilmediği her durumu "bekleme" olarak ele alıyor
(default dalı var). Şimdi backend `refunded` durumunu ekliyor. İyi yazılmış
istemci `refunded`'ı görünce çökmez, "bekleme ekranı" gösterir — yanlış ama
çökmüyor.

Ama başka bir istemci şöyle yazılmış olsaydı:

```
switch status:
    case "pending": ...
    case "completed": ...
    case "failed": ...
    // default yok, exhaustive olduğunu varsayıyor
```

Bazı dillerde bu, çalışma zamanında istisna fırlatır. Yani *aynı enum eklemesi*
bir istemci için uyumlu, diğeri için kırıcıdır. Bu yüzden pro'nun kuralı:
**enum'a değer eklemek yalnızca istemciler bilinmeyen değerleri güvenli ele
aldığında uyumludur ve bunu sen dokümantasyonla en baştan zorlamalısın.**
"Yeni durum değerleri zamanla eklenebilir, bilinmediğinde X yapın" ifadesi
kontratın bir parçası olmalıdır. Bunu baştan söylemediysen, enum eklemek pratikte
kırıcı bir değişikliktir ve öyle davranmalısın.

## 4. Acemi vs pro: tuzaklar ve gözden kaçanlar

**Acemi "response'a alan eklemek her zaman güvenli" sanır.** Yukarıda gördük:
read-modify-write ve strict deserialization varlığında güvenli değildir. Pro,
verinin sadece sunucudan istemciye değil, *geri* de aktığını hatırlar.

**Acemi opsiyonel/zorunlu ayrımını hafife alır.** Yeni bir alanı doğrudan
zorunlu yapar. Deploy anında, o alanı göndermeyen tüm eski istemciler 400 hatası
almaya başlar. Pro her yeni alanı opsiyonel doğar, telemetriyle benimsenmeyi
izler, ancak istemcilerin %100'ü gönderdiğinde (ve grace period geçtiğinde)
zorunluya çevirir — çevirirse.

**Acemi "hata mesajının metnini" değiştirmeyi zararsız sanır.** Ama sahada
birçok istemci hata mesajının *metnine* göre dallanma yapar (çünkü stabil bir
hata kodu vermemişsindir). Metni değiştirdiğinde onların dallanmasını kırarsın.
Pro her hataya makinece okunabilir, stabil bir kod verir ve mesaj metnini
"insan içindir, değişebilir" diye deklare eder. Hata kontratı da API
kontratıdır; çoğu kişi bunu unutur.

**Acemi sayfalama (pagination) ve sıralama varsayımlarını atlar.** Varsayılan
sıralamayı "created_at" iken "updated_at"e çevirmek şemada hiçbir şey
değiştirmez ama istemcinin gördüğü veri sırasını değiştirir; sayfalama üstünde
duran istemciler kayıt atlar veya tekrar eder. Bu, "şema uyumlu ama davranış
kırıcı" değişikliklerin klasiğidir. Pro, *gözlemlenebilir her davranışın*
kontratın parçası olduğunu bilir — sadece şemanın değil.

**Acemi "kimse kullanmıyordur" diye siler.** Pro asla varsayımla silmez.
Kaldırmadan önce kullanım telemetrisi koyar, ölçer, tüketicilere haber verir,
grace period tanır, ve ancak kullanım sıfıra (veya kabul edilebilir eşiğe)
indiğinde kaldırır. "Sessiz kaldırma" üretimde en çok geceyarısı çağrısı
üreten davranışlardan biridir.

**Acemi null ile "alan yok"u aynı sanar.** Pro bu ikisini titizlikle ayırır,
çünkü PATCH semantiğinde "gönderilmedi" ve "null olarak gönderildi" taban tabana
zıt niyetlerdir; birini diğeriyle karıştırmak ya veri siler ya da güncellemeyi
sessizce yutar.

**Acemi tarih/saat, para ve sayı temsillerinde gevşektir.** Parayı float
tutmak, tarihi zaman dilimsiz string yapmak, büyük id'leri JSON number olarak
göndermek (çünkü bazı istemci ortamlarında 53 bit üstü tamsayılar sessizce
bozulur) — bunların hepsi başta çalışır, üretimde yıllar sonra sinsi biçimde
patlar. Pro parayı tamsayı minor birimde (kuruş) veya string olarak, tarihi
ISO-8601 UTC olarak, büyük id'leri string olarak tutar. Bunlar sonradan
düzeltilemeyen, çünkü kırıcı olan kararlardır; bu yüzden *ilk günden* doğru
seçilmeleri gerekir.

**"İşe yarar gibi görünüp üretimde patlayan" en büyük tuzak:** staging'de tek
bir güncel istemciyle test edip "uyumlu" ilan etmek. Uyumluluk, *en eski canlı
istemcinle* test edilir. Elinde eski istemcilerin bir matrisi ve onlara karşı
koşan kontrat testleri yoksa, "geriye dönük uyumlu" iddian bir temenniden
ibarettir.

## 5. Araçlar ve saha notları

**Şema ve kontrat tanımı.** API'nin makinece okunabilir bir şeması olmalı
(OpenAPI/JSON Schema tarzı bir tanım, ya da IDL tabanlı sistemlerde şema
dosyaları). Şemasız API, "kontratım kafamda" demektir; kimse evrimi
denetleyemez. Şema dosyasını versiyon kontrolüne koy ve *değişikliklerini*
gözden geçir.

**Kırıcı değişiklik dedektörleri.** Şema diff araçları (OpenAPI için
oasdiff/openapi-diff gibi, protobuf için buf breaking gibi) iki şema sürümünü
karşılaştırıp "bu değişiklik kırıcı" uyarısı verir. Bunu CI'a kur: pull
request, kontratı kırıcı biçimde değiştiriyorsa build kırmızıya dönsün. Bu tek
adım, "sadece bir alan çıkardım" hatalarının çoğunu merge edilmeden yakalar.
Ekibimde bunu koyduktan sonra kırıcı-kaza sayısı ciddi düştü.

**Kontrat testleri (consumer-driven contracts).** Pact tarzı tüketici-güdümlü
kontrat testleri, "sağlayıcı tarafında yaptığım değişiklik hangi tüketicileri
kırar" sorusunu deploy öncesi cevaplar. Her tüketici beklentisini bir kontrat
olarak yazar; sağlayıcı build'i o kontratlara karşı doğrulanır. Mikroservis
ortamında bu, uyumluluk için en yüksek getirili yatırımlardan biridir.

**Gözlemlenebilirlik (observability).** Emeklilik kararı veriyle verilir. Bunun
için: her istekte istemci sürümünü ve API sürümünü logla; deprecated alan/endpoint
kullanımına özel metrik/sayaç koy; "hangi istemci hangi eski davranışı ne sıklıkta
kullanıyor" panosu kur. `Deprecation` ve `Sunset` HTTP başlıklarıyla tüketicilere
mühlet ilan et. Deprecated bir şeyi kaldırmadan önce cevaplamam gereken soru
"kullanım sıfıra indi mi" ve buna ancak telemetriyle *evet* diyebilirim.

**Debug ve inceleme.** Uyumluluk sorunlarını ayıklarken en değerli araç, ham
istek/yanıt gövdesini olduğu gibi görebilmektir — bir proxy (mitmproxy, Charles
benzeri) ya da yapılandırılmış istek logları. "Modelin ne deserialize etti"
değil, "tel üzerinde ne gitti" bilgisi lazım; çünkü çoğu uyumluluk bug'ı tam da
deserialization katmanında, alanların sessizce düşürüldüğü yerde saklıdır.
İstemci tarafında "bilinmeyen alan geldiğinde uyar" modunu geliştirme
ortamında açık tutmak, ileriye dönük uyumsuzlukları erkenden ortaya çıkarır.

**Roll-out disiplini.** Kırıcıya yakın bir değişikliği canlıya alırken feature
flag ve kademeli açılım (canary) kullan. Yeni davranışı önce trafiğin %1'ine
aç, hata oranlarını ve o "eski istemci" metriklerini izle, sorun yoksa yükselt.
Böylece kırıcı bir sürprizi tüm kullanıcı tabanına değil, küçük bir dilime
patlatırsın ve geri alabilirsin.

**Dokümantasyon ve iletişim.** Public veya ekipler-arası API'de değişiklik
günlüğü (changelog) ve net bir deprecation politikası ("bir şeyi ilan
ettikten en az N ay sonra kaldırırız") kontratın sosyal yarısıdır. Teknik olarak
uyumlu ama habersiz yapılan bir davranış değişikliği bile tüketicide güven
kırar. Uyumluluk sadece kodda değil, beklenti yönetiminde de sağlanır.

### Kapanış: kıdemli refleks

Bir API değişikliği önüme geldiğinde kafamdaki sıralı kontrol şudur: (1) Bu
gerçekten kırıcı mı — hem şema hem de gözlemlenebilir davranış açısından? (2)
Eklemeli yaparak kırıcı olmaktan çıkarabilir miyim? (3) Verinin geri yolculuğu
(read-modify-write) bunu bozar mı? (4) En eski canlı istemcim bununla ne yapar?
(5) Kaldıracaksam, önce ölçebiliyor muyum? (6) Yanlış giderse geri alabileceğim
bir roll-out planım var mı?

Bu altı sorunun hepsine tatmin edici cevap vermeden hiçbir kontrat değişikliğini
merge etmem. Çünkü API'de yapılan hatanın maliyeti anında değil, *gecikmelidir*:
bugün masum görünen değişiklik, altı ay sonra güncelleme yapmamış bir istemci
yüzünden, hafta sonu bir veri kaybı olarak geri döner. API tasarımında olgunluk,
bu gecikmeli maliyeti bugünden görebilmektir.
