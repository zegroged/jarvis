# GraphQL Güvenliği

GraphQL, istemcinin sunucudan tam olarak istediği veriyi tek bir uç noktadan (endpoint) talep etmesini sağlayan bir sorgu dilidir. REST mimarisinden farkı burada başlar: REST'te her kaynak için ayrı bir URL ve genellikle sabit bir yanıt şekli vardır. GraphQL'de ise tipik olarak `/graphql` gibi tek bir uç nokta bulunur ve istemci, isteğinin gövdesinde (body) hangi alanları, hangi ilişkileri ve ne kadar derinlikte veri istediğini kendisi tarif eder. Bu esneklik, GraphQL'i geliştiriciler için güçlü kılan şeydir; ama aynı esneklik, güvenlik açısından saldırı yüzeyini (attack surface) kökten değiştirir.

Bu makalede GraphQL'e özgü dört ana risk üzerinde derinleşeceğiz: introspection'ın sızdırdığı şema bilgisi, sorgu derinliği ve karmaşıklığı üzerinden yapılan DoS saldırıları, ilişkili nesne erişiminde ortaya çıkan IDOR ve batching mekanizmasının güvenlik kontrollerini nasıl aştığı. Her başlıkta önce nasıl çalıştığını, sonra neden bir zafiyete dönüştüğünü, ardından hem istismar (exploitation) mantığını hem de savunmayı ele alacağız.

## GraphQL'in güvenlik modelini REST'ten ayıran şey

Güvenlik açısından temel farkı anlamadan diğer başlıklar havada kalır. REST'te sunucu, hangi verinin döneceğini büyük ölçüde kendisi belirler. İstemci `/users/42` der, sunucu o kullanıcının önceden tanımlı temsilini döner. Yani veri erişim şeklini sunucu kontrol eder.

GraphQL'de ise **sorgunun şeklini istemci belirler**. İstemci "bana bu kullanıcıyı, onun tüm siparişlerini, her siparişin içindeki ürünleri, o ürünlerin üreticilerini ve üreticilerin diğer ürünlerini ver" diyebilir. Sunucu bu sorguyu, resolver adı verilen fonksiyonlar zinciriyle çalıştırır. Her alan (field) için bir resolver vardır ve bu resolver'lar sorgu ağacında dolaşılırken tek tek tetiklenir.

Bu mimarinin doğurduğu iki kritik sonuç vardır. Birincisi: yetkilendirme (authorization) kararı artık tek bir uç noktada değil, her resolver seviyesinde verilmesi gereken bir sorumluluktur. İkincisi: istemci sorgunun maliyetini belirlediği için, sunucunun harcayacağı kaynak miktarını da dolaylı olarak istemci belirler. Bu iki nokta, aşağıdaki dört zafiyet sınıfının kök nedenidir.

## Introspection: Şemanın Kendini İfşa Etmesi

### Tanım ve çalışma mantığı

Introspection, GraphQL'in yerleşik bir özelliğidir: bir istemci, sunucuya "şemanı bana anlat" diyebilir. `__schema` ve `__type` gibi özel meta-alanlar aracılığıyla; tüm tipleri, alanları, argümanları, mutation'ları, enum değerlerini ve alan açıklamalarını (description) tek bir sorguyla çekebilir. Bu özellik geliştirme sırasında son derece faydalıdır; GraphiQL, Apollo Sandbox gibi araçlar ve otomatik istemci kod üreticileri tam olarak buna dayanır.

Neden var? Çünkü GraphQL'in tasarım felsefesi "şema, sözleşmedir" fikri üzerine kurulu. Şemanın makine tarafından okunabilir olması, ekosistemin tamamını (tip güvenli istemciler, dokümantasyon araçları, otomatik testler) mümkün kılar.

### Neden bir zafiyete dönüşür

Sorun şu: introspection üretim (production) ortamında da açık bırakıldığında, saldırgana API'nin tam haritasını hediye eder. Normalde bir saldırganın körlemesine tahmin etmesi, alan isimlerini brute-force ile denemesi gereken her şey — `deleteUser`, `internalAdminNotes`, `resetPasswordToken`, `impersonate` gibi mutation ve alanlar — introspection açıkken bir sorgu uzağındadır.

Burada önemli bir kavramsal noktayı netleştirmek gerekir: **introspection'ı kapatmak tek başına güvenlik değildir.** Bu, "güvenlik belirsizlik yoluyla" (security through obscurity) kategorisine girer. Şema gizli olsa bile alan isimleri tahmin edilebilir, hata mesajlarından sızabilir veya istemci tarafındaki JavaScript paketlerinden çıkarılabilir. Dolayısıyla introspection'ı kapatmak saldırganın işini zorlaştıran bir katmandır, gerçek yetkilendirme kontrollerinin yerini almaz.

### Somut örnek

Bir saldırganın atacağı ilk adım tipik olarak tam şema dökümüdür. Kavramsal olarak sorgu şuna benzer:

```graphql
query {
  __schema {
    types {
      name
      fields {
        name
        args { name }
      }
    }
    mutationType { fields { name } }
  }
}
```

Bu döküm elde edildiğinde, saldırgan mutation listesinde `updateUserRole` gibi bir alan görürse, dikkatini oraya yöneltir. Şema, saldırganın keşif (reconnaissance) aşamasını dakikalara indirir.

### Sömürü ve savunma

Sömürü tarafı basittir: introspection açıksa, otomatik araçlar (örneğin şema dökümü alıp saldırı yüzeyini analiz eden araçlar) şemayı çeker, gizli veya "internal" olması gereken alanları listeler ve bunları test etmeye başlar.

Savunma tarafında birkaç katman düşünmek gerekir:

- **Üretimde introspection'ı devre dışı bırakma.** Çoğu sunucu kütüphanesi bunu bir yapılandırma seçeneğiyle sunar. Ancak burada dikkat: bazı kütüphaneler introspection'ı kapattığınızda alan öneri/otomatik tamamlama (field suggestion) mesajlarını hâlâ açık bırakır. Yani "`nam` diye bir alan yok, `name` mi demek istediniz?" tarzı yardımcı hata mesajları, kapalı introspection'a rağmen şemayı kısmen sızdırabilir. Bu suggestion özelliğini de ayrıca kapatmak gerekir.
- **Gerçek yetkilendirmeyi resolver seviyesinde uygulama.** Şema gizli olsun ya da olmasın, hassas mutation'ların çağıran kişinin rolünü kontrol etmesi zorunludur.
- **Ortama göre farklılaştırma.** Geliştirme ortamında introspection açık, üretimde kapalı olacak şekilde ortam değişkenine bağlı yapılandırma en sağlıklı yaklaşımdır.

## Derinlik ve Karmaşıklık Üzerinden DoS

### Tanım ve kök neden

Bu, GraphQL'e en özgü ve en tehlikeli zafiyet sınıflarından biridir. Kök neden, yukarıda bahsettiğimiz "sorgunun maliyetini istemci belirler" gerçeğidir. GraphQL şemalarında tipler genellikle birbirine döngüsel (cyclic) referanslarla bağlıdır. Örneğin bir `User`'ın `posts` alanı vardır, her `Post`'un bir `author` alanı vardır, o `author` yine bir `User`'dır ve onun da `posts`'u vardır. Bu döngü, teorik olarak sonsuz derinlikte iç içe geçmiş bir sorgu yazmayı mümkün kılar.

### Neden bu kadar tehlikeli

Küçük, birkaç yüz baytlık bir sorgu, sunucuda katlanarak (exponential) büyüyen bir iş yükü doğurabilir. Her derinlik seviyesi, bir önceki seviyenin sonuçları üzerinde yeni resolver çağrıları tetikler. Eğer `posts` alanı 100 gönderi, her `author`'ın `posts`'u yine 100 gönderi dönüyorsa, birkaç seviye derinlikte milyonlarca resolver çağrısına ve veritabanı sorgusuna ulaşırsınız. Saldırgan tek bir HTTP isteğiyle sunucunun CPU'sunu, bellek kullanımını ve veritabanı bağlantı havuzunu tüketebilir. Bu, klasik bir amplification (yükseltme) saldırısıdır: küçük girdi, devasa çıktı.

### Somut örnek

Derinlik saldırısının kavramsal iskeleti:

```graphql
query {
  user(id: "1") {
    posts {
      author {
        posts {
          author {
            posts {
              author { name }
            }
          }
        }
      }
    }
  }
}
```

Bu iç içe geçmeyi istediğiniz kadar tekrarlayabilirsiniz. Buna ek olarak, karmaşıklık (complexity) saldırısı derinlikten farklıdır: sorgu çok derin olmayabilir ama aynı seviyede binlerce alanı veya yüksek maliyetli bir alanı (örneğin büyük bir `first: 100000` sayfalama argümanı) çağırarak yükü artırabilir. Yani sadece derinliği sınırlamak yetmez, alan başına maliyeti de düşünmek gerekir.

### Sömürü ve savunma

Sömürü mantığı: saldırgan ya derinlik yoluyla katlanan bir ağaç oluşturur ya da genişlik/sayfalama argümanlarıyla tek seviyede aşırı yük yaratır ya da alias (takma ad) kullanarak aynı pahalı alanı defalarca çağırır.

Savunma çok katmanlı olmalıdır ve bu başlıkta tek bir önlem asla yeterli değildir:

- **Sorgu derinliği sınırı (depth limiting).** Sorgu ağacının izin verilen maksimum derinliğini sabitleyin. Çoğu gerçek uygulama için 7-10 seviye fazlasıyla yeterlidir; bunun ötesi büyük olasılıkla kötü niyetlidir.
- **Karmaşıklık/maliyet analizi (query cost analysis).** Her alana bir maliyet puanı atayıp, sorgunun toplam maliyetini çalıştırmadan önce hesaplayın ve bir eşiği aşarsa reddedin. Liste dönen ve sayfalama argümanı alan alanlar, dönebilecekleri eleman sayısıyla çarpılarak puanlanmalıdır. Bu, derinlik sınırından daha akıllı bir yaklaşımdır çünkü genişlik saldırılarını da kapsar.
- **Sayfalama zorunluluğu ve üst sınır.** Liste dönen alanlarda `first`/`limit` argümanına makul bir tavan koyun; sınırsız liste dönüşüne asla izin vermeyin.
- **Zaman aşımı (timeout) ve kaynak kotaları.** Tek bir sorgunun harcayabileceği süreyi ve kaynağı sınırlayın; bu, diğer önlemler atlatılsa bile son bir güvenlik ağıdır.
- **Rate limiting.** İstek başına maliyet tabanlı sınırlama (sadece istek sayısına değil, sorgunun hesaplanan maliyetine göre kota düşme) en sağlam yaklaşımdır.

Burada kritik bir uyarı: **statik sorgu analizi (allow-list / persisted queries) bu sorunu kökten çözer.** İstemcinin sadece önceden onaylanmış, sunucuda kayıtlı sorguları çalıştırmasına izin verirseniz, saldırgan keyfi derin sorgular gönderemez. Genel API sunmuyorsanız (yani API'niz sadece kendi ön yüzünüz tarafından kullanılıyorsa) persisted queries en güçlü savunmadır.

## IDOR: İlişkili Nesnelere Yetkisiz Erişim

### Tanım ve kök neden

IDOR (Insecure Direct Object Reference), bir kullanıcının kendisine ait olmayan bir nesneye, sadece o nesnenin tanımlayıcısını (ID) değiştirerek erişebilmesidir. Bu zafiyet GraphQL'e özgü değildir, ancak GraphQL'in mimarisi onu hem daha yaygın hem de tespiti daha zor hâle getirir.

Kök neden yine mimaridedir: GraphQL'de yetkilendirme her resolver'da ayrı ayrı yapılmalıdır. REST'te `/orders/55` uç noktasına bir kez yetki kontrolü koyarsınız. GraphQL'de ise aynı `order` nesnesine birden fazla yoldan ulaşılabilir: doğrudan `order(id: 55)` sorgusuyla, ya da `user(id: 1) { orders }` üzerinden dolaylı olarak, ya da başka bir tipin ilişkili alanı üzerinden. Geliştirici bir yolu korurken diğerini korumayı unutabilir.

### Neden GraphQL'de daha sinsi

GraphQL'in ilişkisel (graph) yapısı, her nesnenin farklı yollardan gezilebilmesini sağlar. Ekip, en görünür sorgu yolunu (örneğin ana `node` veya `order` sorgusunu) sıkıca korurken; iç içe geçmiş bir alan üzerinden (örneğin `paymentMethod`, `internalNotes` gibi ilişkili nesneler) yetki kontrolünün atlanabildiği bir yol açık kalabilir. Saldırgan introspection ya da tahmin yoluyla bu alternatif yolları keşfeder ve zayıf halkayı hedefler.

### Somut örnek

Kullanıcı kendi profilini çekerken normal davranır. Ama şu sorguyu deneyerek başkasının siparişine erişmeye çalışır:

```graphql
query {
  order(id: "9d3f-...-başkasının-id'si") {
    total
    shippingAddress
    paymentMethod { last4 cardHolderName }
  }
}
```

Eğer `order` resolver'ı sadece "böyle bir sipariş var mı" diye bakıp "bu sipariş çağıran kullanıcıya mı ait" kontrolünü yapmıyorsa, saldırgan başka kullanıcıların adres ve ödeme bilgilerine ulaşır. Tehlike, `paymentMethod` gibi iç içe alanların kendi resolver'larında da ayrı bir kontrol gerektirmesidir.

### Sömürü ve savunma

Sömürü mantığı: saldırgan kendi meşru isteğini yakalar, içindeki ID'yi başka değerlerle (ardışık sayılar, tahmin edilen ya da sızdırılmış UUID'ler) değiştirir ve dönen veriyi gözlemler. Tahmin edilebilir, ardışık ID'ler bu saldırıyı kolaylaştırır.

Savunma tarafında:

- **Yetkilendirmeyi veri erişim katmanında merkezileştirme.** En sağlam yaklaşım, "bu kullanıcı bu nesneye erişebilir mi" kararını her resolver'ın manuel olarak tekrarlamasına bırakmak yerine, tüm veri erişimini kaynak sahipliğini (ownership) kontrol eden ortak bir katmandan geçirmektir. Böylece bir resolver'da kontrolü unutmak sistemik bir açık yaratmaz.
- **Nesne seviyesinde (object-level) yetki kontrolü.** Her hassas nesne döndüren resolver, çağıran kimliğin (context içindeki authenticated user) o nesneyle ilişkisini doğrulamalıdır. "Kimlik doğrulaması yapılmış olması" yeterli değildir; "bu spesifik nesneye yetkili mi" sorusu ayrıca sorulmalıdır.
- **Tahmin edilemez tanımlayıcılar.** Ardışık tamsayı ID'ler yerine UUID gibi tahmin edilemez tanımlayıcılar kullanmak IDOR'u zorlaştırır. Ancak bu bir savunma katmanıdır, gerçek yetki kontrolünün yerini tutmaz — UUID sızdırılabilir.
- **İç içe alanları unutmama.** İlişkili nesne döndüren her alanın (özellikle hassas olanların) kendi yetki kontrolüne sahip olduğundan emin olun. En sık yapılan hata, ana sorguyu korurken ilişkili alanları savunmasız bırakmaktır.

## Batching: Kontrolleri Toplu İstekle Aşmak

### Tanım ve çalışma mantığı

GraphQL, tek bir HTTP isteğinde birden fazla işlemi barındırmaya olanak tanır. Bunun iki ana biçimi vardır. Birincisi, birçok GraphQL sunucusunun desteklediği **istek dizisi (array batching)**: HTTP gövdesine tek bir sorgu nesnesi yerine bir sorgu dizisi (JSON array) koyarsınız ve sunucu hepsini işler. İkincisi, tek bir sorgu içinde **alias kullanarak** aynı alanı farklı argümanlarla defalarca çağırmaktır:

```graphql
mutation {
  a1: login(user: "admin", pass: "deneme1") { token }
  a2: login(user: "admin", pass: "deneme2") { token }
  a3: login(user: "admin", pass: "deneme3") { token }
  # ... yüzlerce alias
}
```

Bu özellik neden var? Performans için. İstemci, birçok küçük isteği tek bir tur (round-trip) içinde birleştirerek ağ gecikmesini azaltır. GraphQL'in vaadi zaten "az istek, çok veri"dir.

### Neden bir zafiyete dönüşür

Sorun, güvenlik kontrollerinin çoğunun **HTTP isteği seviyesinde** çalışmasıdır. Klasik bir rate limiter, "bu IP dakikada 10 istek yapabilir" der. Ama batching sayesinde saldırgan, tek bir HTTP isteğinin içine 1000 tane login denemesi sıkıştırırsa, rate limiter bunu "1 istek" olarak sayar. Böylece brute-force koruması, OTP/2FA kod deneme sınırı, kupon kodu deneme sınırı gibi sayıya dayalı tüm kontroller tek hamlede atlatılır.

Bu, batching'i özellikle tehlikeli yapan şeydir: mevcut güvenlik altyapınızın sağlam görünen bir parçasını (rate limiting) sessizce etkisiz kılar. Ayrıca batching, yukarıda anlatılan karmaşıklık DoS saldırısını da güçlendirir — tek istekte birçok pahalı sorgu paketlenebilir.

### Somut örnek ve sömürü mantığı

Alias tabanlı batching ile şifre veya OTP brute-force en klasik senaryodur. Bir 2FA doğrulama alanını düşünün: normalde kullanıcı 5 yanlış kod girince kilitlenir. Ama saldırgan tek istekte, `a1` ... `a10000` alias'larıyla 6 haneli tüm kod aralığını (bir milyon olasılık) birkaç istekte tarayabilir. Sunucu her alias'ı ayrı bir işlem olarak resolve ederken, istek sayısı tabanlı kilit mekanizması hiç devreye girmez.

### Savunma

- **Batch boyutunu sınırlama.** Hem array batching'te dizi uzunluğuna hem de tek sorgudaki alias/işlem sayısına makul bir üst sınır koyun. Aynı mutation'ın bir sorguda kaç kez çağrılabileceğini kısıtlamak, alias brute-force'unu doğrudan engeller.
- **Rate limiting'i işlem seviyesine taşıma.** Kotayı HTTP isteği başına değil, çalıştırılan işlem (operation/resolver) başına düşürün. Böylece batch içindeki her login denemesi ayrı ayrı sayılır ve limit gerçekten korur.
- **Hassas mutation'larda batching'i kısıtlama.** `login`, `verifyOtp`, `redeemCoupon` gibi doğası gereği "deneme sayısı" hassasiyeti olan işlemler için batching'i tamamen kapatmayı veya çok sıkı sınırlamayı düşünün.
- **İş mantığı seviyesinde kilitleme.** Brute-force korumasını sadece istek sayısına değil, hedef hesaba/kaynağa bağlayın. "Bu hesap için son dakikada kaç kod denendi" gibi durum tabanlı (stateful) bir sayaç, isteğin nasıl paketlendiğinden bağımsız olarak korur.
- **Array batching'i gerekmiyorsa kapatma.** Uygulamanız array batching'e ihtiyaç duymuyorsa, bu özelliği tamamen devre dışı bırakmak saldırı yüzeyini azaltır.

## Yaygın Hatalar

Bu dört başlığı bir arada düşündüğümüzde, sahada tekrar tekrar görülen hatalar belli bir örüntü oluşturur:

- **Introspection'ı kapatıp güvenliği sağladığını sanmak.** Şemayı gizlemek keşfi zorlaştırır ama yetkilendirme boşluklarını kapatmaz. Gerçek koruma resolver seviyesindeki yetki kontrolüdür.
- **Yetkilendirmeyi sadece en görünür sorgu yolunda yapmak.** Ana `node`/`order` sorgusu korunurken iç içe geçmiş ilişkili alanların savunmasız kalması en sık görülen IDOR kaynağıdır. GraphQL'de bir nesneye giden birden fazla yol olduğunu unutmayın.
- **Kimlik doğrulama (authentication) ile yetkilendirmeyi (authorization) karıştırmak.** "Kullanıcı giriş yapmış" olması, "bu spesifik veriye erişebilir" anlamına gelmez. İkisi ayrı kontrollerdir.
- **Rate limiting'i sadece HTTP istek sayısına bağlamak.** Batching bu varsayımı çökertir. Kota, işlem ve maliyet tabanlı olmalıdır.
- **Sadece derinlik sınırı koyup karmaşıklığı görmezden gelmek.** Genişlik ve sayfalama tabanlı saldırılar derinlik sınırını atlatır; maliyet analizi şarttır.
- **Ayrıntılı hata mesajlarını üretimde açık bırakmak.** Stack trace'ler, veritabanı hataları ve alan öneri (field suggestion) mesajları, kapalı introspection'a rağmen şema ve altyapı hakkında bilgi sızdırır. Üretimde hata mesajları sadeleştirilmelidir.
- **Güvenliği tek bir katmana yıkmak.** Her başlıkta tek önlem yetersizdir; savunma katmanlı (defense in depth) olmalıdır.

## En İyi Pratikler

Bütünsel bir GraphQL güvenlik duruşu şu prensipler üzerine kurulur:

**Yetkilendirmeyi merkezileştirin ve her resolver'da uygulayın.** İdeal olan, veri erişimini kaynak sahipliğini kontrol eden ortak bir katmandan geçirmektir. Bu, "bir resolver'da kontrolü unutma" hatasını sistemik olarak imkânsız hâle getirir. Alan seviyesinde yetkilendirme (field-level authorization) düşünün: bazı alanlar sadece belirli rollere görünmelidir.

**Sorgu maliyetini çalıştırmadan önce sınırlayın.** Derinlik sınırı, karmaşıklık/maliyet analizi, sayfalama üst sınırı ve zaman aşımını birlikte kullanın. Mümkünse, genel API sunmuyorsanız, persisted queries (allow-list) yaklaşımıyla sadece önceden onaylanmış sorguların çalışmasına izin verin — bu, keyfi sorgu tabanlı saldırıların çoğunu kökten keser.

**Rate limiting'i istek değil işlem ve maliyet tabanlı yapın.** Batching ve alias'ların istek sayısı sayacını atlatabileceğini varsayın. Hassas işlemleri (login, OTP, kupon) durum tabanlı, hedefe bağlı kilit mekanizmalarıyla koruyun ve bu işlemlerde batch/alias tekrarını sıkıca sınırlayın.

**Ortama göre yapılandırın.** Üretimde introspection'ı ve alan öneri mesajlarını kapatın, hata mesajlarını sadeleştirin, geliştirme araçlarını (açık GraphiQL/Sandbox gibi) devre dışı bırakın. Geliştirme ortamında bunlar açık kalabilir.

**Girdi doğrulaması ve tip güvenliğini iş mantığı kontrolünün yerine koymayın.** GraphQL'in şema tabanlı tip kontrolü, bir string'in string olduğunu garanti eder; ama o string'in kötü niyetli bir içerik (örneğin altta yatan bir veritabanına giden bir enjeksiyon yükü) taşımadığını garanti etmez. Resolver'lar hâlâ enjeksiyon (injection) risklerine karşı parametreli sorgular ve doğru çıkış kodlaması (output encoding) kullanmalıdır.

**Gözlemlenebilirlik (observability) kurun.** Anormal derinlikte, yüksek maliyetli veya çok sayıda alias içeren sorguları loglayın ve alarma bağlayın. Batch içindeki başarısız login yoğunluğu gibi örüntüleri izlemek, hem saldırıyı erken yakalar hem de sınırların doğru ayarlanıp ayarlanmadığını gösterir.

**Katmanlı savunmayı bir bütün olarak görün.** Introspection'ı kapatmak, derinlik sınırı, maliyet analizi, işlem tabanlı rate limiting, resolver seviyesinde yetkilendirme ve persisted queries — bunların her biri farklı bir saldırı sınıfını hedefler ve tek başına yeterli değildir. GraphQL'in esnekliği, ancak bu katmanların hepsi birlikte devredeyken güvenli bir güce dönüşür.
