# GraphQL ve gRPC: Modern API Tasarımında İki Farklı Felsefe

## Giriş: Neden Bu İki Teknolojiyi Birlikte Konuşuyoruz?

GraphQL ve gRPC, REST'in hâkim olduğu bir dünyada ortaya çıkmış, farklı problemleri çözmek için tasarlanmış iki teknolojidir. Sık sık birbirinin alternatifiymiş gibi karşılaştırılırlar, ama gerçekte çoğu zaman rakip değil, tamamlayıcıdırlar. GraphQL bir _sorgu dili_ ve çalışma zamanı (runtime), gRPC ise bir _uzak prosedür çağrısı_ (Remote Procedure Call, RPC) çerçevesidir. Birini seçmek, aslında bir problemi nasıl modellediğinizle ilgili felsefi bir tercihtir.

Bu makale, ikisinin de _kök mantığını_ (neden böyle tasarlandıklarını), somut çalışma biçimlerini, tuzaklarını ve hangi durumda hangisinin doğru olduğunu derinlemesine ele alıyor. Amaç, "şunu kullan" demek değil; kararınızı _neye dayanarak_ vereceğinizi göstermek.

## GraphQL: İstemcinin Veriyi Şekillendirdiği Dünya

### Tanım ve Kök Neden

GraphQL, Facebook'ta 2012 civarında, mobil istemcilerin karşılaştığı somut bir acıyı çözmek için doğdu. Sorun şuydu: mobil uygulamalar, zayıf ve değişken ağ koşullarında çalışır; her ekran farklı veri kombinasyonlarına ihtiyaç duyar; ve REST endpoint'leri bu ihtiyaçlara ya çok fazla ya çok az veri döndürür. Bir haber akışı ekranı için "kullanıcı adı, avatar ve son üç yorum" isterken, sunucu size kullanıcının doğum tarihinden adres bilgisine kadar her şeyi içeren şişkin bir JSON gönderir. Ya da istediğiniz veriyi tek istekte alamayıp arka arkaya birkaç endpoint'e istek atmak zorunda kalırsınız.

GraphQL'in temel fikri şudur: **veriyi hangi biçimde istediğine sunucu değil, istemci karar versin.** İstemci, ihtiyaç duyduğu alanları (field) tam olarak tanımlayan bir sorgu gönderir; sunucu da tam olarak o şekli döndürür. Bu, API'nin sözleşmesini (contract) sabit bir endpoint listesinden, esnek bir _tip grafiğine_ (type graph) taşır.

### Şema (Schema): GraphQL'in Kalbi

GraphQL'in her şeyi bir _şema_ etrafında döner. Şema, sunucunun sunabileceği tüm tipleri, alanları ve bunlar arasındaki ilişkileri güçlü tipli (strongly typed) biçimde tanımlar. Bu şema, hem makine tarafından okunabilir bir sözleşme hem de otomatik dokümantasyon kaynağıdır.

Basit bir şema örneği:

```graphql
type Kullanici {
  id: ID!
  ad: String!
  eposta: String!
  gonderiler: [Gonderi!]!
}

type Gonderi {
  id: ID!
  baslik: String!
  icerik: String
  yazar: Kullanici!
}

type Query {
  kullanici(id: ID!): Kullanici
}
```

Buradaki `!` işareti alanın null olamayacağını (non-nullable) belirtir. `[Gonderi!]!` ise "hiç null olmayan bir Gonderi dizisi" anlamına gelir. Bu tip sistemi, GraphQL'in en güçlü yanlarından biridir: istemci bir alan istemeden önce onun var olup olmadığını, tipini ve null davranışını bilir.

Şema neden bu kadar merkezî? Çünkü GraphQL'de her şey _grafik_ olarak modellenir. `Kullanici` üzerinden `gonderiler`e, oradan her gönderinin `yazar`ına gidebilirsiniz. İstemci bu grafiğin içinde istediği kadar derine inebilir. Bu, ilişkisel verinin doğasına REST'ten çok daha yakındır.

### Over-fetching ve Under-fetching: Çözülen Asıl Problem

GraphQL'i anlamanın en net yolu, çözdüğü iki problemi anlamaktır.

**Over-fetching (aşırı veri çekme):** İstemcinin ihtiyacından fazla veri almasıdır. Klasik bir REST örneği: `/users/42` endpoint'i çağırdığınızda, siz sadece kullanıcının adını isterken sunucu 30 alanlık dev bir nesne döndürür. Bu, boşa harcanan bant genişliği (bandwidth), gereksiz serileştirme (serialization) maliyeti ve mobil cihazda daha fazla veri kullanımı demektir. GraphQL'de sadece `{ kullanici(id: 42) { ad } }` sorgusu yaparsınız ve yalnızca adı alırsınız.

**Under-fetching (yetersiz veri çekme):** Tek bir endpoint'in ihtiyacınız olan her şeyi vermemesi ve bunun sonucunda arka arkaya istek atmak zorunda kalmanızdır. Buna sık sık "N+1 istek problemi" de denir: önce kullanıcıyı çekersiniz, sonra her gönderisi için ayrı bir istek atarsınız. GraphQL'de tek bir sorguda kullanıcıyı, gönderilerini ve her gönderinin yorumlarını iç içe (nested) alabilirsiniz. Ağ gidiş-dönüş sayısı (round-trip) bire iner.

Bu ikisi, GraphQL'in var oluş sebebidir. Ancak dikkat: over/under-fetching'i _istemci tarafında_ çözerken, GraphQL bu karmaşıklığı _sunucu tarafına_ taşır. Bu, birazdan konuşacağımız N+1 tuzağının tam olarak nerede saklandığını açıklar.

### GraphQL Nasıl Çalışır: Resolver Zinciri

Bir GraphQL sorgusu geldiğinde ne olur? Sunucu sorguyu ayrıştırır (parse), şemaya karşı doğrular (validate) ve sonra _resolver_ adı verilen fonksiyonları çalıştırır. Her alan için bir resolver vardır. `kullanici` alanı için bir resolver, o kullanıcının `gonderiler` alanı için başka bir resolver çalışır.

Bu mimarî neden önemli? Çünkü GraphQL'in performans karakteristiği doğrudan bu resolver'ların nasıl yazıldığına bağlıdır. İşte meşhur **N+1 problemi** burada doğar: `kullanici` resolver'ı bir kullanıcı çeker, `gonderiler` resolver'ı o kullanıcının gönderilerini çeker, ama her gönderinin `yazar` alanı için ayrı ayrı veritabanı sorgusu yapılırsa, 100 gönderi için 100 ayrı sorgu atarsınız. İstemci tek bir zarif sorgu yazmıştır ama sunucu arka planda veritabanını yormaktadır.

Bunun standart çözümü **DataLoader** desenidir: aynı olay döngüsü (event loop) turunda talep edilen tüm ID'ler biriktirilir (batch) ve tek bir toplu sorguyla çözülür. Ayrıca sonuçlar önbelleğe (cache) alınır. Eğer GraphQL kullanıyorsanız ve DataLoader benzeri bir batching mekanizmanız yoksa, büyük ihtimalle sessizce N+1 problemi yaşıyorsunuz demektir.

### GraphQL'in Tuzakları

GraphQL'in esnekliği bedelsiz değildir:

- **Sorgu karmaşıklığı ve DoS riski:** İstemci istediği kadar derine inebildiği için, kötü niyetli ya da dikkatsiz bir istemci son derece pahalı sorgular yazabilir (derinlemesine iç içe geçmiş, döngüsel ilişkiler). Bunu önlemek için sorgu derinliği sınırı (depth limiting), karmaşıklık analizi (complexity analysis) ve zaman aşımı (timeout) gibi savunmalar gerekir.
- **Önbelleğe alma zorluğu:** REST'te URL'ye göre HTTP önbelleği (HTTP caching) neredeyse bedavadır. GraphQL'de genellikle her sorgu tek bir POST endpoint'ine gider, bu yüzden URL tabanlı önbellekleme çalışmaz. Önbellekleme uygulama katmanına taşınır ve daha zordur.
- **Hata yönetimi:** GraphQL, kısmî başarıya (partial success) izin verir; bir alan başarısız olurken diğerleri dönebilir. HTTP durum kodu genellikle 200'dür ve hatalar yanıtın `errors` alanında gelir. Bu, geleneksel HTTP durum kodu tabanlı hata yönetimini alışkanlık haline getirmiş ekipler için kafa karıştırıcıdır.
- **Dosya yükleme ve ikili veri (binary data):** GraphQL, JSON tabanlı olduğu için büyük ikili veriler için doğal bir çözüm değildir.

## gRPC: Servisler Arası İletişimin Yüksek Performanslı Yolu

### Tanım ve Kök Neden

gRPC, Google tarafından geliştirilen, dâhilî "Stubby" sisteminin açık kaynak halefi olan bir RPC çerçevesidir. Kök motivasyonu tamamen farklı bir dünyadan gelir: yüzlerce, binlerce mikroservisin birbiriyle _çok yüksek hacimde ve düşük gecikmeyle_ (low latency) konuştuğu bir veri merkezi ortamı.

RPC fikri eskidir: uzaktaki bir fonksiyonu, sanki yereldeymiş gibi çağırmak. `hesapla(x, y)` yazarsınız, arka planda bu bir ağ çağrısına dönüşür, sonuç size döner. gRPC bu fikri modern bir temele oturtur: sözleşmeyi Protocol Buffers (protobuf) ile tanımlar, taşımayı HTTP/2 üzerine kurar ve ikili (binary) serileştirme kullanır.

gRPC'nin felsefesi GraphQL'inkinin neredeyse tam tersidir. GraphQL "istemci veriyi şekillendirsin" derken, gRPC "sözleşme katı ve önceden tanımlı olsun, iletişim mümkün olduğunca hızlı olsun" der. Bu yüzden gRPC, esneklik yerine _verimlilik_ ve _performans_ üzerine kuruludur.

### Protocol Buffers (protobuf): Sözleşme ve Serileştirme

gRPC'nin merkezinde protobuf vardır. Protobuf hem bir _arayüz tanım dili_ (Interface Definition Language, IDL) hem de bir _serileştirme formatıdır_. Bir `.proto` dosyasında hem veri tiplerini (message) hem de çağrılabilecek servisleri (service) tanımlarsınız:

```protobuf
syntax = "proto3";

message KullaniciIstegi {
  int32 id = 1;
}

message KullaniciYaniti {
  int32 id = 1;
  string ad = 2;
  string eposta = 3;
}

service KullaniciServisi {
  rpc KullaniciGetir(KullaniciIstegi) returns (KullaniciYaniti);
}
```

Buradaki `= 1`, `= 2` gibi sayılar alan adı değil, **alan numaralarıdır** (field number) ve bunlar protobuf'un anlaşılması en kritik detayıdır. Serileştirilmiş veride alan _adları_ hiç gönderilmez; sadece bu numaralar ve değerler gönderilir. Bu, protobuf'un neden bu kadar kompakt olduğunu açıklar: JSON'da her nesnede `"eposta":` gibi metin tekrar tekrar gönderilirken, protobuf sadece `3` numarasını gönderir.

Bu tasarım aynı zamanda **geriye dönük uyumluluğun** (backward compatibility) da temelidir. Alan numaraları asla değişmediği ve yeniden kullanılmadığı sürece, yeni alanlar ekleyebilir, eski istemcileri kırmadan şemayı geliştirebilirsiniz. Eski istemci tanımadığı bir alan numarasını görür ve onu güvenle yok sayar. **Kritik kural:** yayınlanmış bir alan numarasını asla başka bir anlama gelecek şekilde yeniden kullanmayın; bu, sessiz veri bozulmasına (silent data corruption) yol açar.

Protobuf ikili (binary) olduğu için insan tarafından okunamaz; bu bir dezavantaj gibi görünse de, servisler arası iletişimde bu bir sorun değildir çünkü asıl önemli olan makine verimliliğidir. Kod üretimi (code generation) sayesinde `.proto` dosyasından her dil için istemci ve sunucu iskeletleri (stub) otomatik üretilir; bu da diller arası (polyglot) uyumu neredeyse bedavaya getirir.

### HTTP/2: gRPC'nin Performansının Temeli

gRPC'nin HTTP/2 üzerine kurulmuş olması tesadüf değildir; performans karakteristiğinin büyük kısmı buradan gelir. HTTP/1.1'in temel kısıtı, bir bağlantı üzerinde bir anda tek bir isteğin işlenmesiydi (head-of-line blocking); paralellik için birden çok TCP bağlantısı açmanız gerekiyordu.

HTTP/2 bunu birkaç önemli özellikle çözer:

- **Multiplexing (çoğullama):** Tek bir TCP bağlantısı üzerinde birden çok istek ve yanıt aynı anda, birbirini engellemeden akabilir. Bu, gRPC'nin binlerce eşzamanlı çağrıyı az sayıda bağlantıyla yönetmesini sağlar.
- **Başlık sıkıştırma (header compression, HPACK):** HTTP başlıkları tekrar tekrar gönderilmek yerine sıkıştırılır. Çok sayıda küçük istekte bu ciddi tasarruf sağlar.
- **İkili çerçeveleme (binary framing):** HTTP/2 metin yerine ikili çerçevelerle çalışır, bu da ayrıştırmayı hızlandırır.
- **Sunucu itmesi ve akışlar (streams):** İki yönlü akışın (bidirectional streaming) temelini oluşturur.

Multiplexing sayesinde gRPC, dört çağrı türünü doğal olarak destekler: birim çağrı (unary; bir istek, bir yanıt), sunucu akışı (server streaming; bir istek, çok yanıt), istemci akışı (client streaming; çok istek, bir yanıt) ve iki yönlü akış (bidirectional streaming). Bu akış yeteneği, gRPC'yi gerçek zamanlı veri, telemetri ve olay akışları için doğal bir seçim yapar. REST'te bunu yapmak için WebSocket gibi ek mekanizmalara ihtiyaç duyarsınız.

### gRPC'nin Tuzakları

gRPC'nin gücü belirli bağlamlara özgüdür ve o bağlamların dışında ciddi sürtünme yaratır:

- **Tarayıcı desteği doğrudan değildir:** Tarayıcılar, gRPC'nin ihtiyaç duyduğu düşük seviyeli HTTP/2 çerçevelerine tam erişim vermez. Bu yüzden tarayıcıdan gRPC servisine doğrudan konuşmak için genellikle gRPC-Web adında bir ara katman ve bir proxy gerekir. Bu, gRPC'nin neden ağırlıklı olarak _servisler arası_ (backend-to-backend) kullanıldığını açıklar.
- **İnsan tarafından okunamazlık:** İkili format, hata ayıklamayı (debugging) zorlaştırır. `curl` ile bir isteği hızlıca deneyemezsiniz; grpcurl gibi özel araçlara ihtiyaç duyarsınız.
- **Yük dengeleme karmaşıklığı:** HTTP/2 bağlantıları uzun ömürlü ve çoğullanmış olduğu için, klasik bağlantı başına yük dengeleme (connection-level load balancing) gRPC ile iyi çalışmaz. Yük dengeleyicinin istek düzeyinde (request-level, yani L7) çalışması gerekir; aksi halde tüm trafik tek bir sunucuya yığılabilir.
- **Şema evrimi disiplini:** protobuf esnekliği yalnızca alan numaralarına saygı gösterilirse işe yarar. Disiplinsiz bir ekipte bu bir tehlike kaynağıdır.

## GraphQL ve gRPC: Doğrudan Karşılaştırma

Bu iki teknolojiyi gerçekten anlamak için, aynı eksenler üzerinde yan yana koymak gerekir.

### Kimin İhtiyacına Göre Tasarlandı?

GraphQL _istemci merkezlidir_. Sorusu şudur: "Farklı istemciler (mobil, web, üçüncü taraf) çok değişken veri ihtiyaçlarını nasıl tek bir esnek API'den karşılar?" Bu yüzden esnekliği maksimize eder.

gRPC _sunucu-sunucu merkezlidir_. Sorusu şudur: "İki servis, minimum gecikme ve maksimum verimle, katı bir sözleşme üzerinden nasıl konuşur?" Bu yüzden performansı ve tipsel katılığı maksimize eder.

Bu tek cümle, çoğu kararı belirler: veri _tüketicisinin_ ihtiyaçları öngörülemez ve çeşitliyse GraphQL, iletişim _iç altyapıda_ ve performans-kritikse gRPC.

### Serileştirme ve Taşıma

GraphQL genellikle JSON kullanır (metin tabanlı, okunabilir, ama hantal) ve çoğunlukla HTTP/1.1 üzerinde tek bir POST endpoint'iyle çalışır. gRPC, protobuf (ikili, kompakt, okunamaz) kullanır ve HTTP/2 üzerinde çoğullamalı akışlarla çalışır. Ham performans karşılaştırıldığında gRPC neredeyse her zaman öndedir: daha küçük yük (payload), daha hızlı ayrıştırma, daha az bağlantı yükü.

### Esneklik ve Katılık Dengesi

GraphQL'de istemci veriyi şekillendirir; bu güçlüdür ama sunucuya performans yönetimi yükü bindirir (N+1, sorgu karmaşıklığı). gRPC'de sözleşme sabittir; bu daha az esnektir ama daha öngörülebilir ve optimize edilmesi kolaydır. GraphQL'de "yeni bir görünüm" çoğu zaman sunucu değişikliği gerektirmez; gRPC'de yeni bir yetenek genellikle `.proto` güncellemesi ve yeniden üretim (regeneration) gerektirir.

## Ne Zaman Hangisi? Karar Çerçevesi

### GraphQL'i Şu Durumlarda Seçin

- **Zengin, çeşitli istemcileriniz varsa:** Aynı backend'i mobil, web ve belki üçüncü taraf geliştiriciler tüketiyorsa ve her birinin veri ihtiyacı farklıysa, GraphQL'in esnekliği paha biçilmezdir. Her ekran için yeni endpoint yazmak yerine, istemciler ihtiyaçlarını kendileri ifade eder.
- **Çok sayıda arka uç kaynağını birleştirmeniz gerekiyorsa:** GraphQL, birden çok mikroservisi ve veri kaynağını tek bir birleşik grafik (unified graph) arkasında toplamak için mükemmeldir. İstemci, verinin nereden geldiğini bilmez.
- **Under-fetching (N+1 istek) sizin için gerçek bir acıysa:** Mobil ekiplerin arka arkaya istek atma derdi varsa, GraphQL bunu tek sorguya indirir.
- **Frontend ekipleri hızlı iterasyon istiyorsa:** Backend değişikliği beklemeden yeni veri kombinasyonları kullanabilmek büyük bir çeviklik sağlar.

### gRPC'yi Şu Durumlarda Seçin

- **Servisler arası (internal) iletişim performans-kritikse:** Mikroservisleriniz birbiriyle yüksek hacimde konuşuyorsa, gRPC'nin düşük gecikmesi ve verimli serileştirmesi somut fark yaratır.
- **Akış (streaming) ihtiyacınız varsa:** Gerçek zamanlı telemetri, olay akışları, iki yönlü iletişim gibi senaryolarda HTTP/2 tabanlı akış doğal bir avantajdır.
- **Polyglot (çok dilli) bir ortamınız varsa:** Farklı diller yazılmış servisler tek bir `.proto` sözleşmesiyle sorunsuz konuşabilir; kod üretimi bu köprüyü otomatik kurar.
- **Katı, versiyonlanabilir bir sözleşme istiyorsanız:** protobuf'un alan numarası tabanlı evrim modeli, uzun ömürlü ve dikkatle yönetilen API'ler için sağlam bir temeldir.

### İkisini Birlikte Kullanmak: Yaygın ve Sağlam Bir Mimari

Gerçek dünyadaki pek çok olgun sistem her ikisini de kullanır ve bu bir çelişki değildir. Tipik desen şudur: **Dış dünyaya (tarayıcı, mobil) bakan API katmanı GraphQL, iç servisler arası iletişim gRPC.** GraphQL sunucusu, resolver'larının içinde arka uç mikroservislerine gRPC ile konuşur. Böylece istemci esnekliğini GraphQL'den, iç iletişim verimliliğini gRPC'den alırsınız. Bu, "ya biri ya öteki" tuzağına düşmeden her iki teknolojinin güçlü yanlarını birleştirmenin en yaygın yoludur.

## Yaygın Hatalar

Her iki teknolojide de tekrar tekrar görülen hatalar vardır:

- **GraphQL'i her yere uygulamak:** İç servisler arası basit, sabit çağrılar için GraphQL kullanmak gereksiz karmaşıklık ekler. GraphQL'in esnekliği ancak istemci çeşitliliği varsa değer katar; yoksa sadece resolver katmanı yükü ve N+1 riski getirir.
- **DataLoader/batching olmadan GraphQL:** N+1 problemini görmezden gelmek, üretimde sessizce ölçeklenme sorunları yaratır. GraphQL'e geçen ekiplerin en sık düştüğü tuzak budur.
- **gRPC'yi tarayıcıdan doğrudan çağırmaya çalışmak:** gRPC-Web ve proxy gerekliliğini gözden kaçırmak, tarayıcı tabanlı entegrasyonu beklenmedik biçimde tıkar.
- **protobuf alan numaralarını yeniden kullanmak:** Silinmiş bir alanın numarasını yeni bir alana vermek, eski verilerle konuşan istemcilerde sessiz bozulmaya yol açar. Silinen alan numaralarını `reserved` olarak işaretlemek bu hatayı önler.
- **GraphQL'de sorgu karmaşıklığını sınırlamamak:** Kötü niyetli ya da dikkatsiz sorgulara karşı derinlik ve karmaşıklık sınırları koymamak, sunucuyu DoS'a açık bırakır.
- **gRPC ile yanlış yük dengeleme:** L4 (bağlantı düzeyi) yük dengeleyici kullanmak, uzun ömürlü HTTP/2 bağlantıları yüzünden trafiğin dengesiz dağılmasına yol açar; L7 yük dengeleme gerekir.

## En İyi Pratikler

**GraphQL için:**
- Her ilişkisel alan çözümlemesinde batching (DataLoader deseni) kullanın; N+1'i baştan tasarımla önleyin.
- Sorgu derinliği ve karmaşıklık sınırları koyun; üretim ortamında zorunlu kabul edin.
- Şemayı sürüm yerine _evrimle_ yönetin: alanları kaldırmak yerine önce `@deprecated` ile işaretleyip zamanla emekliye ayırın.
- Persisted queries (önceden kaydedilmiş sorgular) ile hem güvenliği hem önbeklemeyi iyileştirin.

**gRPC için:**
- `.proto` dosyalarını tek doğruluk kaynağı (single source of truth) olarak tutun ve sürüm kontrolünde yönetin.
- Alan numaralarına dokunmayın; silinen alanları `reserved` yapın; asla numara yeniden kullanmayın.
- Zaman aşımı (deadline/timeout) ve iptal (cancellation) mekanizmalarını her çağrıda kullanın; RPC'lerin sonsuza kadar asılı kalmasını önleyin.
- Servisler arası iletişimde L7 farkında yük dengeleme ve bağlantı yönetimi kurgulayın.

**İkisi için ortak:**
- Sözleşmeyi (schema veya `.proto`) API'nin kalbi olarak görün; kod üretiminden dokümantasyona kadar her şeyi bu sözleşmeden türetin.
- Geriye dönük uyumluluğu bir disiplin olarak benimseyin; tüketicileri kırmadan evrilmeyi tasarımın parçası yapın.

## Sonuç

GraphQL ve gRPC, aynı sorunu iki farklı ölçekte çözer. GraphQL, _istemci ile sunucu arasındaki_ veri sözleşmesini esnetir ve over/under-fetching acısını dindirir. gRPC, _servisler arasındaki_ iletişimi protobuf ve HTTP/2 ile mümkün olan en verimli hâle getirir. Doğru soru "hangisi daha iyi?" değil, "hangi sınırda, kimin ihtiyacını çözüyorum?" sorusudur. Çoğu olgun mimaride cevap "ikisi de" olur: dışa GraphQL'in esnekliği, içe gRPC'nin verimliliği. Her ikisinin de kök mantığını anladığınızda, karar kendiliğinden netleşir.
