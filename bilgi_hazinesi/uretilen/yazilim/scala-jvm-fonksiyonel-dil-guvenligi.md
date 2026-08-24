# Scala / JVM Fonksiyonel Dil Güvenliği: Deserialization ve Akka Actor Güvenliği

## Giriş ve Kapsam

Scala, JVM üzerinde çalışan, fonksiyonel ve nesne yönelimli paradigmaları birleştiren bir dildir. Güvenlik açısından çift bir konumdadır: Bir yandan JVM'in bütün klasik zaafiyetlerini (özellikle **Java deserialization gadget zincirleri**) miras alır; öte yandan Scala'ya ve onun en yaygın ekosistemine, yani **Akka** aktör kütüphanesine özgü kendine has risk yüzeyleri vardır.

Bu makale iki eksene odaklanır:

1. **Deserialization güvenliği** — Scala'nın `case class`, `implicit` ve JSON kütüphaneleri (Jackson-Scala, circe, play-json) bağlamında veri okurken oluşan riskler ve JVM native serialization'ın tehlikeleri.
2. **Akka Actor / Akka Remoting güvenliği** — Mesaj tabanlı dağıtık modelde, ağ üzerinden gelen serileştirilmiş mesajların uzaktan kod çalıştırmaya (RCE) nasıl dönüşebildiği.

Amaç saldırı reçetesi vermek değil; **mekanizmayı anlamak** ve buna dayalı **savunma ile tespit** kurmaktır.

---

## 1. JVM Deserialization: Kök Neden

### Tanım

Deserialization, bir byte dizisini tekrar canlı bir nesne grafiğine dönüştürme işlemidir. Java'nın yerleşik (native) mekanizması `ObjectInputStream.readObject()` üzerinden çalışır. Sorun şudur: `readObject`, yalnızca veriyi kopyalamaz — deserialize edilen sınıfın `readObject`, `readResolve`, `readExternal` gibi magic method'larını ve sonuçta çağrılan `finalize`/setter/`toString` gibi noktaları **çalıştırır**.

### Kök Neden / Çalışma Mantığı

Klasik Java deserialization RCE'sinin özü **type confusion** değil, **type flexibility** kötüye kullanımıdır. `ObjectInputStream`, byte akışının içindeki sınıf adını okur ve o sınıfı classpath'ten yükler. Saldırgan, uygulama nihai olarak `Order` bekliyor olsa bile, akışa **classpath'te bulunan başka herhangi bir Serializable sınıfı** yerleştirebilir. Eğer classpath'te belirli bir kütüphane (klasik örnek: eski Apache Commons Collections'taki `InvokerTransformer`) varsa, bu sınıfların deserialize sırasında tetiklenen davranışları zincirlenerek keyfi metod çağrısına ("gadget chain") dönüştürülebilir.

Kritik nokta: **Güvenlik açığı verinin içeriğinde değil, "hangi tipin instantiate edileceğine saldırganın karar verebilmesinde"dir.** Bu yüzden imza doğrulaması veya "sadece kendi sınıfımı gönderiyorum" varsayımı yeterli değildir.

### Scala Bu Riski Nasıl Miras Alır?

Scala `case class`'ları derlendiğinde otomatik olarak `java.io.Serializable` implement eder. Bir Scala uygulaması JVM native serialization kullanıyorsa (örneğin eski Akka Remoting, bazı cache/session store'lar, `spark` shuffle katmanları), Java'nın gadget problemi Scala tarafında da birebir geçerlidir. Scala olmak bu riski **azaltmaz**.

---

## 2. Scala'ya Özgü Deserialization Yüzeyleri

### 2.1 case class + JSON kütüphaneleri

Scala'da en yaygın deserialization, JVM native değil, JSON üzerinden yapılır: **circe**, **play-json**, **jackson-module-scala**, **spray-json**, **ZIO-JSON**. Burada tehlike, native gadget zincirinden farklıdır ve daha ince noktalarda yaşanır.

#### Polymorphic deserialization ve `@JsonTypeInfo`

En keskin risk Jackson tarafındadır. Bir alan polymorphic ise (base type + alt tipler), Jackson'a hangi somut sınıfın kullanılacağını söylemek gerekir. Bunu yapmanın **tehlikeli** yolu şudur:

```scala
// TEHLİKELİ — asla kullanma
mapper.enableDefaultTyping()          // deprecated ve güvensiz
// veya
@JsonTypeInfo(use = Id.CLASS)         // sınıf adını JSON içine gömer
```

`Id.CLASS` veya `activateDefaultTyping`, JSON verisinin içine **sınıf adını** yazar ve okurken o adı classpath'ten yükler. Bu, tam olarak native deserialization'daki hatanın JSON'a taşınmış halidir: saldırgan JSON'a `"@class": "some.Gadget"` yazarak instantiate edilecek tipi seçer.

**Doğru yaklaşım:** Alt tipleri **açıkça, whitelist mantığıyla** tanımlamak:

```scala
@JsonTypeInfo(use = Id.NAME, ...)
@JsonSubTypes(Array(
  new Type(value = classOf[Cash]),
  new Type(value = classOf[Card])
))
sealed trait Payment
```

Burada JSON içinde sadece bir mantıksal isim (`"cash"`) taşınır, gerçek sınıf adı değil. Yüklenebilecek tipler kodda kapalı bir kümedir; saldırgan classpath'ten rastgele sınıf seçemez.

#### `sealed trait` avantajı

Scala'nın `sealed trait` + `case class` hiyerarşisi, güvenlik açısından değerlidir: alt tipler derleme zamanında bilinir ve **kapalı bir küme** oluşturur. Bu, tasarım gereği whitelist'e çok yakındır. Ancak `case object` ile Jackson tarafında bilinen bir tuzak vardır: `case object`'ler `@JsonSubTypes` ile beklendiği gibi çözülmeyebilir; yaygın pratik, alansız bir `case class` kullanmaktır.

### 2.2 akka-serialization-jackson: doğru varsayılan

Akka'nın önerdiği modern serializer olan `akka-serialization-jackson`, güvenlik açısından iyi tasarlanmıştır: Jackson databind'in bilinen **gadget sınıflarına karşı bir deny-list**'i uygulanır ve polymorphic tiplerde sınıf adları serileştirilmiş temsile gömülmez. Bu, kötü niyetli gadget yüklemesini engelleyen doğru varsayılandır. Yine de deny-list mantığı savunmanın tek katmanı olmamalıdır; whitelist temelli tip tasarımı esas güvencedir.

### 2.3 implicit tabanlı codec çözümü

circe/play-json gibi kütüphaneler, `implicit` decoder/encoder'larla çalışır. Buradaki risk RCE değil, **mantıksal ve kaynak tüketimi** risktir:

- **Derinlik/genişlik saldırıları:** Derin iç içe JSON veya devasa dizi, decode sırasında stack overflow veya bellek şişmesi yaratabilir. Girdi boyutu ve derinliği sınırlanmalıdır.
- **Sessiz varsayılanlar:** Bir `case class` alanı için `Option` veya default değer varsa, saldırgan alanı boş bırakarak beklenmedik "güvenli olmayan varsayılan" durumuna düşürebilir. İş kuralı doğrulaması, deserialization'dan **sonra** ayrı bir katmanda yapılmalıdır; tipin decode olması geçerli iş verisi olduğu anlamına gelmez.

---

## 3. Akka Actor Modeli ve Güvenlik

### Aktör Modelinin Kısa Tanımı

Akka'da temel birim **actor**'dür: kendi durumunu kapsülleyen, dış dünyayla yalnızca **asenkron mesajlaşma** üzerinden konuşan bir varlık. Her aktörün bir posta kutusu (mailbox) vardır; mesajlar sıraya girer ve tek tek işlenir. Bu model, paylaşımlı bellek kilitlerini ortadan kaldırdığı için concurrency güvenliği açısından güçlüdür.

Ancak güvenlik açısından iki ayrı düzlem vardır:

1. **Yerel (local) aktörler** — Aynı JVM içinde. Mesajlar serileştirilmez; nesne referansı geçer. Saldırı yüzeyi düşüktür.
2. **Uzak (remote) aktörler / Akka Cluster** — Farklı JVM'ler ağ üzerinden konuşur. Mesajlar **serialize edilip** TCP üzerinden taşınır. Asıl kritik güvenlik yüzeyi buradadır.

### 3.1 Akka Remoting: Tarihsel RCE Sınıfı

Akka Remoting'in kritik zaafiyet sınıfı, bir aktör sisteminin ağ üzerinden erişilebilir olması ve gelen mesajları **Java native serializer** ile deserialize etmesiydi.

**Zincir mantığı:**

1. `ActorSystem` bir TCP portu üzerinden Akka Remote ile dışarı açılır.
2. Saldırgan bu porta bağlanabilir (ağ segmentasyonu yoksa).
3. Saldırgan, uygulamanın beklediği mesaj yerine, **classpath'te var olan bir gadget sınıfını** içeren serileştirilmiş bir mesaj gönderir.
4. Alıcı JVM, mesajı native deserialize ederken gadget zincirini tetikler → **JVM sürecinin bağlamında keyfi kod çalışması (RCE)**.

Bu, Java native deserialization probleminin dağıtık mesajlaşmaya taşınmış halidir. Kayıtlara geçmiş güvenlik bildirimlerinde bu zaafiyet **orta şiddet** (CVSS ~6.8) olarak sınıflandırıldı ve düzeltmenin özü şuydu: **Java serializer varsayılan olmaktan çıkarıldı ve untrusted ağda kapatılması önerildi.** (Kesin sürüm ve düzeltme detaylarını üretim ortamınızda resmi Akka güvenlik bildirimlerinden doğrulayın.)

Tehlikeyi büyüten ek faktörler:

- **TLS'in kapalı olması** ya da açık olsa bile **karşılıklı (mutual) kimlik doğrulamanın zorunlu olmaması.** Yalnızca sunucu tarafı TLS, "kim bağlanıyor" sorusunu çözmez; herhangi biri bağlanabiliyorsa şifreli kanal RCE'yi engellemez.

### 3.2 Modern Savunma: Serializer Seçimi

Doğru duruş nettir:

- **Java native serializer'ı kapat.** Akka'da native serializer üretim için uygun değildir; hem güvenlik hem uyumluluk (schema evolution) nedeniyle. `akka.actor.allow-java-serialization = off` tarzı bir konfigürasyon, native yolun kaza eseri kullanılmasını engeller.
- **Jackson (akka-serialization-jackson) veya Protobuf** gibi, gadget deny-list ve/veya şema tabanlı serializer kullan. Protobuf, tipi şemaya bağladığı için "keyfi sınıf yükleme" yüzeyini tamamen ortadan kaldırır.
- **Serialize edilebilecek mesaj tiplerini kısıtla.** Akka'da mesaj bind'lerini yalnızca beklenen (genellikle bir `CborSerializable`/`JsonSerializable` marker trait implement eden) tiplerle sınırlamak, "her Serializable her yere gidebilir" varsayımını kırar.

### 3.3 Ağ ve Kimlik Katmanı

Serializer güvenliği tek başına yeterli değildir; **erişimin kim tarafından yapıldığı** da kontrol edilmelidir:

- **Mutual TLS (mTLS):** Cluster/Remoting trafiğinde her iki taraf da sertifika sunmalı ve doğrulanmalıdır. Yalnız-sunucu TLS, dinleyen porta rastgele istemcinin bağlanmasını engellemez.
- **Ağ segmentasyonu:** Remoting/Cluster portları asla internete veya geniş iç ağa açılmamalı; yalnızca cluster üyelerinin bulunduğu güvenli segmentte erişilebilir olmalıdır. Bu, "port erişilebilir" ön koşulunu ortadan kaldırdığı için çok etkili bir savunma katmanıdır.
- **En az yetki:** Aktör JVM'i, ele geçirilirse hasarı sınırlamak için minimal işletim sistemi yetkileriyle çalışmalıdır.

---

## 4. Doğru Kullanım, Tuzaklar ve Yaygın Hatalar

### Doğru Kullanım Kalıpları

- **Native serialization'ı tamamen kapat**, yalnızca şema/whitelist temelli serializer kullan.
- **Polymorphic tipleri `sealed trait` + açık `@JsonSubTypes` (Id.NAME)** ile modelle; sınıf adı asla wire'a gitmesin.
- **Girdi boyutu, iç içe derinlik ve koleksiyon eleman sayısı için sert limitler** koy (DoS'a karşı).
- **Decode sonrası ayrı doğrulama katmanı:** Tipin oluşması, iş kuralının sağlandığı anlamına gelmez.
- **Remoting/Cluster'da mTLS + ağ segmentasyonu** birlikte uygulanmalı — biri diğerinin yerini tutmaz.
- **Bağımlılıkları güncel tut ve tara:** Gadget zincirleri classpath'teki kütüphanelerden gelir. `commons-collections`, eski `jackson-databind` gibi bileşenlerde bilinen gadget'lar için SCA (Software Composition Analysis) araçları çalıştır.

### Yaygın Hatalar

- **"JSON kullanıyorum, o yüzden güvendeyim" yanılgısı.** `activateDefaultTyping`/`Id.CLASS` açıksa JSON da native kadar tehlikelidir.
- **"TLS var, o yüzden güvendeyim" yanılgısı.** Karşılıklı kimlik doğrulama yoksa, şifreli kanal saldırgana açık kapıdan girme imkânı bırakır.
- **`enableDefaultTyping` / `enableDefaultTyping()` gibi eski API'lerin kod tabanında kalması.** Bunlar deprecated ve güvensizdir; grep ile aranıp temizlenmelidir.
- **Native serializer'ı prod'da varsayılan bırakmak.** Genellikle "çalışıyor" diye fark edilmez, ta ki port dışarı açılana kadar.
- **Mesaj tiplerini kısıtlamamak.** Marker trait/whitelist yoksa, classpath'teki her Serializable tip potansiyel bir yüktür.
- **Deserialization'ı iş-mantığı doğrulaması sanmak.** Deserialize başarı ≠ veri geçerli/yetkili.

---

## 5. Tespit (Detection)

Savunmanın yanında **tespit** katmanı da kurulmalıdır:

- **Konfigürasyon denetimi (statik):** `allow-java-serialization`, `enable-additional-serialization-bindings`, `Id.CLASS`, `activateDefaultTyping`, native serializer bind'leri için kod ve konfigürasyonu tara. CI'da bunları kıran bir lint kuralı ekle.
- **Bağımlılık taraması:** Bilinen gadget içeren kütüphane sürümlerini SCA ile sürekli izle.
- **Ağ görünürlüğü:** Remoting/Cluster portlarına beklenmeyen kaynaklardan gelen bağlantıları logla ve alarma bağla. Cluster üyesi olmayan IP'lerden gelen handshake denemeleri güçlü bir gösterge.
- **Runtime davranış:** Deserialization sırasında beklenmedik sınıfların yüklenmesi (özellikle `Runtime.exec`, `ProcessBuilder`, `ScriptEngine` çağrıları) EDR/uygulama loglarında izlenmeli. Bir aktör JVM'inin child process spawn etmesi neredeyse her zaman anomalidir.
- **Kaynak anomalileri:** Ani bellek/CPU sıçraması, deserialization DoS'unun işareti olabilir.

---

## Özet

Scala, JVM'in deserialization risklerini olduğu gibi devralır: kök neden, verinin içeriği değil, **instantiate edilecek tipi saldırganın seçebilmesidir.** Scala'ya özgü katman, `case class`/`sealed trait` tabanlı modelleme ile polymorphic JSON deserialization'ın (`@JsonTypeInfo`) doğru veya yanlış yapılandırılabilmesidir. Akka ise bu riski dağıtık mesajlaşmaya taşır: Remoting/Cluster üzerinde native serializer + zayıf kimlik doğrulama, klasik olarak RCE'ye açılan bir yüzeydir.

Sağlam duruş üç sacayağıdır: (1) **native serialization'ı kapat, şema/whitelist temelli serializer kullan**; (2) **polymorphic tipleri kapalı küme olarak, sınıf adını wire'a koymadan** modelle; (3) **Remoting/Cluster'ı mTLS ve ağ segmentasyonuyla** koru. Buna decode sonrası doğrulama, bağımlılık tarama ve ağ/runtime tespiti eklendiğinde, düşük öncelikli ama profesyonel kapsamda ihmal edilmemesi gereken bu yüzey büyük ölçüde kapatılmış olur.
