# SAML Saldırıları: XML Signature Wrapping, Comment Injection ve Savunma

## Tanım

SAML (Security Assertion Markup Language), federe kimlik doğrulamada (federated authentication) kullanılan, XML tabanlı bir standarttır. Temel amacı, bir kullanıcının kimliğini bir tarafın (Identity Provider, kısaca IdP) doğrulaması ve bu doğrulama sonucunu güvenilir bir şekilde başka bir tarafa (Service Provider, kısaca SP) aktarmasıdır. Kurumsal Single Sign-On (SSO) çözümlerinin önemli bir kısmı hâlâ SAML üzerine kuruludur; Okta, ADFS, Ping, Shibboleth gibi ürünler bu protokolü konuşur.

SAML'in kalbinde bir **assertion** (iddia) bulunur. Assertion, "Bu kullanıcı şu kimliğe sahiptir, şu yetkilere sahiptir ve bu bilgi şu zamana kadar geçerlidir" diyen imzalı bir XML belgesidir. İşte tam bu noktada güvenliğin tamamı tek bir varsayıma dayanır: **imzanın (signature) doğru mesajı koruduğu varsayımı.** SAML saldırılarının büyük çoğunluğu bu varsayımı kırmaya çalışır. Saldırgan, imzayı kırmaya değil (bu kriptografik olarak zordur), imzanın koruduğu şeyle SP'nin okuduğu şeyi birbirinden ayırmaya çalışır.

Bu makale, SAML dünyasının en klasik ve en öğretici iki saldırı sınıfına odaklanır: **XML Signature Wrapping (XSW)** ve **XML Comment Injection**. İkisi de aynı kök nedenden beslenir: XML imza doğrulamasının doğası gereği "hangi düğümü imzaladığım" ile "hangi düğümü işlediğim" arasındaki boşluktan.

## Kök Neden: XML İmzalamanın Neden Bu Kadar Kırılgan Olduğu

Sıradan bir HMAC imzasını düşünün: bir byte dizisini alır, bir anahtarla karıştırır, bir etiket üretir. Doğrulayan taraf tam olarak aynı byte'ları alır ve aynı etiketi üretir. Girdi ile korunan şey birebir aynıdır; arada yorumlama yoktur.

XML Signature (XML-DSig) ise bambaşka bir hayvandır ve bu farklılık tüm sorunun kaynağıdır. XML-DSig, byte'ları değil, **XML düğümlerini (nodes)** imzalar. Bir imza şu adımlardan geçer:

1. İmzalanacak öğe bir **Reference** ile işaret edilir. Bu referans genellikle öğenin `ID` özniteliğini (attribute) kullanır (`URI="#assertion_id_123"` gibi).
2. İşaret edilen öğe bir **canonicalization (C14N)** işleminden geçirilir. Bu adım, XML'i standart bir metin biçimine dönüştürür: boşlukları, öznitelik sırasını, namespace bildirimlerini normalize eder.
3. Bu normalize metnin **digest**'i (özeti) hesaplanır ve `<DigestValue>` içine yazılır.
4. `<SignedInfo>` bloğunun tamamı imzalanır ve `<SignatureValue>` üretilir.

Buradaki kritik gerçek şudur: **imza, XML ağacındaki bir düğüme `ID` referansı üzerinden bağlanır; belgedeki fiziksel konuma değil.** İmza "bu belgenin şu konumundaki içerik doğrudur" demez; "şu `ID`'ye sahip düğümün içeriği doğrudur" der.

Bu durum iki bağımsız işlemi ortaya çıkarır:

- **Doğrulama (validation):** İmza kütüphanesi, referans edilen `ID`'yi bulur, digest'ini kontrol eder, imzayı doğrular. Sonuç: "imza geçerli."
- **İşleme (processing):** Uygulama mantığı, assertion'dan kullanıcı adını, yetkileri, geçerlilik süresini okur. Ama uygulama bunu genellikle **tekrar aynı düğümü bularak** yapmaz; çoğu zaman "ilk assertion'ı al", "kök öğenin altındaki assertion'ı al" gibi konumsal ya da isimsel bir mantık kullanır.

Kök neden tam olarak burada yatar: **Doğrulanan düğüm ile işlenen düğümün aynı düğüm olduğunu hiçbir şey garanti etmez.** İmza kütüphanesi bir düğümü doğrular, uygulama başka bir düğümü okur. Saldırgan bu ayrımı sömürür.

## XML Signature Wrapping (XSW)

### Çalışma Mantığı

XSW saldırısının temel fikri son derece zariftir: Saldırgan, IdP tarafından imzalanmış geçerli bir assertion'ı ele geçirir (kendi meşru girişinden elde edebilir). Bu assertion'ın imzası geçerlidir ve saldırgan bu imzayı bozmadan korur. Sonra belgeye **ikinci, sahte bir assertion** ekler; bu sahte assertion'da kullanıcı adı `admin` olur, yetkiler yükseltilir.

Saldırgan XML ağacını öyle bir yapılandırır ki:

- İmza doğrulama katmanı, hâlâ **orijinal, imzalı** assertion'ı bulup doğrular ve "imza geçerli" der.
- Uygulama işleme katmanı ise **saldırganın enjekte ettiği sahte** assertion'ı okur.

Yani imza doğrulaması dürüst bir şekilde geçer, ama uygulama tamamen farklı, imzasız bir içeriğe göre karar verir. Bu, kimlik doğrulamanın tam bir baypasıdır: parola bilmeden, imza anahtarına erişmeden başka bir kullanıcı (genellikle yönetici) olarak oturum açmak.

### Neden İşe Yarar: İki Katmanın Uyuşmazlığı

XSW'nin işe yaramasının nedeni, XML kütüphaneleri ile uygulama kodunun ağaçta gezinirken **farklı stratejiler** kullanmasıdır. Birkaç somut varyant vardır:

**Varyant 1 — ID kaymalı sarma:** İmza `URI="#id_A"` referansı taşır. Saldırgan, orijinal imzalı assertion'ı (id_A) belgede farklı bir yere gizler; örneğin sahte bir `<Object>` öğesinin ya da genişletilebilir bir bölümün içine. Sonra ekrana konumsal olarak "önce gelen" yere, id_B taşıyan sahte assertion'ı koyar. Doğrulayıcı `#id_A`'yı bulur ve doğrular; uygulama ise "kökün altındaki ilk assertion" olan id_B'yi okur.

**Varyant 2 — İmzayı sahtenin içine taşıma:** Bazı doğrulayıcılar imzayı, kapsadığı öğenin (enveloped signature) kardeşi olarak arar. Saldırgan, imzayı sahte assertion'ın altına yerleştirir ama referans hâlâ orijinal içeriği işaret eder. Doğrulayıcı referans edilen düğümü digest'ler ve doğru bulur, işleyici ise imzayı içeren sahte assertion'a güvenir.

Onlarca varyant, bu iki fikrin (imzalı düğümü nereye saklarsın, sahte düğümü nereye koyarsın) permütasyonlarıdır. Kilit gözlem şudur: **hangi düğümü sakladığın ve nereye koyduğun, hedef kütüphanenin gezinme mantığına göre ayarlanır.** Bir kütüphaneye karşı işe yarayan sarma, diğerine karşı işe yaramaz; bu yüzden XSW test araçları (örneğin bu iş için bilinen tarayıcı eklentileri ve test çerçeveleri) düzinelerce sarma varyantını sırayla dener.

### Somut Örnek (Kavramsal)

Basitleştirilmiş bir SAML Response'un normal hâli şöyledir:

```xml
<Response>
  <Assertion ID="id_orijinal">
    <Subject>meşru_kullanıci</Subject>
    <Signature>
      <SignedInfo>
        <Reference URI="#id_orijinal">
          <DigestValue>...</DigestValue>
        </Reference>
      </SignedInfo>
      <SignatureValue>...</SignatureValue>
    </Signature>
  </Assertion>
</Response>
```

XSW ile saldırgan bunu şu hâle getirir (kavramsal):

```xml
<Response>
  <!-- Sahte assertion: uygulamanın okuyacağı -->
  <Assertion ID="id_sahte">
    <Subject>admin</Subject>
  </Assertion>

  <!-- Orijinal imzalı assertion: doğrulayıcının bulacağı,
       imzası hâlâ #id_orijinal'i işaret ediyor ve geçerli -->
  <Assertion ID="id_orijinal">
    <Subject>meşru_kullanıci</Subject>
    <Signature>
      <SignedInfo>
        <Reference URI="#id_orijinal">...</Reference>
      </SignedInfo>
      <SignatureValue>...</SignatureValue>
    </Signature>
  </Assertion>
</Response>
```

İmza doğrulayıcı `#id_orijinal`'i bulur, digest'ini kontrol eder, imzayı doğru bulur. Ama uygulama "Response'un altındaki ilk Assertion" mantığıyla `id_sahte` içindeki `admin`'i okur. Sonuç: `admin` olarak oturum açma. İmza hiç dokunulmamıştır; sadece bağlamı değiştirilmiştir.

### Sömürü Mantığı

Saldırganın bakış açısıyla saldırı akışı şöyledir:

1. Saldırgan, meşru bir kullanıcı olarak SP'ye giriş yapar ve kendi geçerli, imzalı SAML Response'unu yakalar (bir proxy ile).
2. Response'u yukarıdaki gibi yeniden yapılandırır: sahte bir assertion enjekte eder, imzalı olanı bozmadan farklı bir konuma taşır.
3. Sahte assertion'da `NameID`, `Subject` ya da yetki attribute'larını yükseltir.
4. Değiştirilmiş Response'u SP'ye gönderir. Kütüphane hangi gezinme mantığını kullanıyorsa, saldırgan sarma varyantını ona göre seçer.

Bu, uzaktan, kimlik doğrulamayı tamamen baypas eden, genellikle "critical" seviyesinde bir açıktır. Anahtarı bilmeye gerek yoktur çünkü mevcut geçerli bir imza yeniden bağlamlandırılmaktadır.

### Savunma

XSW'ye karşı savunmanın özü tek bir ilkeye indirgenir: **Doğrulanan düğüm ile işlenen düğüm tam olarak aynı düğüm olmalıdır.** Bunu sağlamak için:

- **Doğrulanmış referansı zorla takip et.** İmza doğrulandıktan sonra, uygulama assertion'ı "ilk assertion" ya da "isimle bul" gibi mantıkla ARAMAMALIDIR. Bunun yerine, imzanın `Reference URI`'sinin işaret ettiği tam düğümü almalı ve yalnızca onu işlemelidir. "Doğrulanmış olanı işle" prensibi, "işlenecek olanı doğrula"dan çok daha güvenlidir.
- **Şema doğrulaması (schema validation) uygula.** Katı bir XSD şeması, beklenmedik konumlarda ekstra `Assertion` öğelerini ya da `Object` içine gizlenmiş yapıları reddedebilir. Ancak şema doğrulaması tek başına yeterli değildir; bazı sarma varyantları şemaya uyar.
- **Belgede kaç imza ve kaç assertion olduğunu say ve sınırla.** Birden fazla assertion, birden fazla imza veya beklenmeyen konumlarda imza gördüğünde reddet. Belirsizlik varsa (ambiguity) reddetmek doğru varsayılan tutumdur.
- **Absolute XPath yerine, doğrulanmış referans nesnesine tutun.** Bazı eski çözümler assertion'ı XPath ile bulur; XSW tam olarak bu XPath gezinmesini kandırmak için tasarlanmıştır. Kütüphanenin, doğrulama sırasında referans ettiği DOM düğümüne doğrudan bir tutamaç (handle) döndürmesi ve uygulamanın yalnızca o tutamağı kullanması gerekir.
- **Olgun, savaş testinden geçmiş bir kütüphane kullan** ve güncel tut. XSW sınıfı, birçok SAML kütüphanesinde yıllar içinde defalarca yamalandı. Kendi imza doğrulama mantığını yazmak neredeyse her zaman hatalıdır.

Buradaki asıl mesaj metodolojiktir: Sorun "imza yanlış doğrulanıyor" değil, "doğru doğrulanan şey yanlış şeymiş" sorunudur. O yüzden savunma da kriptografik değil, **mimaridir**: doğrulama ve işleme katmanlarının aynı gerçeği paylaşmasını garanti etmek.

## XML Comment Injection

### Çalışma Mantığı

Comment injection, XSW'den daha ince ve bir dönem birçok büyük kütüphaneyi aynı anda vuran bir saldırıdır. Kök nedeni imza değil, **XML metin ayrıştırmanın (text parsing) ayrıntısıdır.**

Sorun şu gözlemden doğar: SAML'de kullanıcı kimliği genellikle `<NameID>` gibi bir öğenin metin içeriğidir:

```xml
<NameID>admin@sirket.com</NameID>
```

Şimdi bu metnin ortasına bir XML yorumu (comment) enjekte edildiğini düşünün:

```xml
<NameID>admin@sirket.com<!--saldirgan-->.evil.com</NameID>
```

Kritik soru şudur: Bir XML ayrıştırıcı, bu öğenin metin içeriğini ne olarak okur? Cevap, **kullanılan API'ye ve o API'nin metin düğümlerini (text nodes) nasıl birleştirdiğine bağlıdır** ve tam olarak buradaki tutarsızlık saldırıyı doğurur.

XML standardına göre bir yorum, iki metin düğümünü ayırır. Yorumdan önce bir text node (`admin@sirket.com`), yorumdan sonra ayrı bir text node (`.evil.com`) vardır. Şimdi:

- **Bazı API'ler** (özellikle `getTextContent` benzeri, tüm alt metin düğümlerini birleştiren fonksiyonlar) yorumu atlar ve `admin@sirket.com.evil.com` döndürür.
- **Bazı API'ler** (yalnızca ilk text node'u okuyan naif erişimler) sadece `admin@sirket.com` döndürür.

### Neden İşe Yarar: İmza Geçerli Kalırken Yorumlama Değişir

İşin en sinsi tarafı budur: **XML canonicalization (C14N), yorumları imzadan hariç tutar.** Standart canonicalization algoritması, imza digest'i hesaplanırken yorumları kaldırır. Bu, tasarım gereği böyledir; yorumlar anlamsal olmayan içerik sayılır.

Sonuç dramatiktir: Saldırgan mevcut, imzalı bir assertion'ın içindeki `NameID`'ye bir yorum enjekte ederse, **imza hâlâ geçerli kalır** çünkü digest yorumsuz metin üzerinden hesaplanmıştır. İmza doğrulayıcı hiçbir sorun görmez. Ama uygulama, imza doğrulamasından SONRA, DOM'dan `NameID`'yi okurken kullandığı API'ye göre farklı bir string elde edebilir.

Klasik yükseltme senaryosu şöyledir: Saldırganın meşru hesabı `admin@sirket.com.evil.com` olsun (kendi kontrolündeki bir alan adı). Bu hesap IdP tarafından meşru şekilde imzalanır. Saldırgan sonra `admin@sirket.com<!--x-->.evil.com` biçiminde yorum enjekte eder. Eğer SP'nin okuma API'si yorumdan önceki ilk text node'u alıyorsa, saldırgan `admin@sirket.com` olarak, yani başka birinin hesabıyla oturum açar. İmza geçerli, kullanıcı yanlış.

### Somut Örnek

Saldırganın kontrol ettiği, meşru şekilde imzalanmış assertion:

```xml
<NameID>saldirgan@evil.com</NameID>
```

Hedeflenen kurban kimliği `kurban@evil.com` ise ve saldırgan bu ön eke sahipse, enjeksiyon şöyle olur:

```xml
<NameID>kurban@evil.com<!---->.uzanti</NameID>
```

Burada niyet, ayrıştırıcının yorumdan önceki `kurban@evil.com` parçasını "gerçek kimlik" olarak okumasını sağlamaktır. Yorum imzayı bozmaz (C14N onu siler), ama kimlik yorumlamasını böler. İmza katmanı ile kimlik-çıkarma katmanı aynı string üzerinde anlaşamaz.

### Sömürü Mantığı

1. Saldırgan, kendi kontrolündeki bir kimlikle meşru giriş yapar ve imzalı assertion'ı elde eder.
2. `NameID` (ya da benzeri kimlik taşıyan bir alan) içine, hedef kimliğin sınırında bir yorum enjekte eder.
3. İmza dokunulmadan geçerli kalır; SP'nin naif text-okuma davranışı kimliği yanlış parçalar ve kurbanın hesabıyla oturum açılır.

### Savunma

Comment injection'a karşı savunma iki cephede yürür:

- **Metin okuma davranışını tam olarak canonicalization ile hizala.** Uygulama, kimliği okurken tüm alt text node'ları birleştiren, yorumları göz ardı eden bir API kullanmalıdır; böylece imzanın gördüğü metinle uygulamanın gördüğü metin aynı olur. Sorun, "ilk text node'u al" gibi kısayolların, yorumla bölünmüş metni yanlış birleştirmesidir.
- **Yorumları girdi olarak tamamen ele.** Assertion'ı işlemeden önce DOM'dan tüm yorum düğümlerini kaldırmak (comment stripping / normalization), bu saldırı sınıfını tek hamlede kapatır. Meşru bir SAML assertion'ının kimlik alanlarında yorum bulunmasının hiçbir sebebi yoktur; o yüzden agresif normalizasyon güvenlidir.
- **Kimlik alanlarını (identity strings) katı bir formatla doğrula.** `NameID` bir e-posta ise, izin verilen karakter kümesini kısıtlayın; enjekte edilmiş ayraçlar ve beklenmeyen alt dizeler reddedilir.
- **Kütüphaneyi güncel tut.** Bu saldırı ortaya çıktığında birçok büyük SAML kütüphanesi aynı anda yamaladı; yamalar tam da yukarıdaki normalizasyon ve tutarlı okuma mantığını getirdi. Eski sürümler hâlâ savunmasızdır.

Comment injection ile XSW'nin ortak dersi şudur: **İmzanın koruduğu byte'lar ile uygulamanın anlamlandırdığı değer arasında en ufak bir yorumlama boşluğu bırakırsanız, saldırgan o boşluğa yerleşir.** Biri düğüm seviyesinde (XSW), diğeri text-node seviyesinde (comment injection) çalışır ama zafiyet felsefesi aynıdır.

## SAML'e Özgü Diğer Yaygın Hatalar

XSW ve comment injection en öğretici olanlar olsa da, gerçek dünyada SP'leri deviren birkaç ek hata daha vardır ve bunlar sıklıkla birbirini besler:

- **İmzasız Response'u kabul etmek.** Bazı SP'ler sadece assertion imzalıysa yetinir, Response zarfını (envelope) hiç imzalamaz; ya da bazıları hiç imza aramaz ("signature not required" yanlış yapılandırması). Saldırgan imzasız, tamamen kendi ürettiği bir Response gönderirse ve SP bunu reddetmezse, bütün mekanizma çöker. **İmzanın var olduğunu ve doğru anahtarla yapıldığını mutlaka zorunlu kılın.**
- **Yanlış anahtara güvenmek (key confusion).** SP, imzayı doğrularken hangi sertifikaya güveneceğini metadata'dan almalıdır. Eğer imzanın içine gömülü `<KeyInfo>`/sertifikayı sorgusuz kabul ederse, saldırgan kendi anahtarıyla imzalar ve kendi sertifikasını ekler; imza "geçerli" görünür. **Doğrulama anahtarı önceden yapılandırılmış, güvenilen IdP metadata'sından gelmelidir; assertion'ın içinden değil.**
- **Recipient / Audience / süre kontrollerini atlamak.** Assertion'daki `Audience`, `Recipient`, `NotBefore`, `NotOnOrAfter` alanları doğrulanmazsa, bir SP için üretilmiş assertion başka bir SP'de tekrar kullanılabilir (token yeniden yönlendirme) ya da süresi geçmiş assertion kabul edilir. Bu alanlar imzayla korunsa bile, **SP onları anlamsal olarak kontrol etmezse** imza tek başına yeterli değildir.
- **Replay koruması olmaması.** Aynı geçerli assertion tekrar tekrar gönderilebiliyorsa, yakalanan bir Response yeniden oynatılabilir. `NotOnOrAfter` penceresi içinde kullanılmış assertion `ID`'lerinin bir kez kullanıldıktan sonra reddedilmesi (one-time-use) gerekir.
- **XXE ve DTD'ye açık ayrıştırıcı.** SAML sonuçta XML'dir. Ayrıştırıcı external entity ve DTD işlemeye açıksa, SAML mesajı bir XXE taşıyıcısına dönüşebilir; dosya okuma ve SSRF kapısı açılır. **DTD işlemeyi ve external entity çözümlemeyi kapatın.**

## En İyi Pratikler

Yukarıdaki her şeyi tek bir savunma duruşunda toplarsak, sağlam bir SAML SP şu ilkelere uymalıdır:

1. **Doğrula, sonra doğrulanmış olanı işle — asla tersini yapma.** İmza doğrulamasından sonra, uygulama yalnızca imzanın referans ettiği tam düğümü kullanmalı; ağaçta bağımsız arama yapmamalıdır. XSW'nin panzehiri budur.

2. **İmza ve kimlik metnini tek bir tutarlı kaynaktan oku.** Canonicalization'ın gördüğü metinle uygulamanın okuduğu metin bit bit aynı olmalı. Yorumları normalizasyonla temizle. Comment injection'ın panzehiri budur.

3. **Belirsizliği reddet.** Birden fazla assertion, birden fazla imza, beklenmeyen konumda imza, imzasız zarf — hepsi anında reddedilmeli. Güvenlik açısından "kabul edilebilir ama tuhaf" diye bir kategori olmamalıdır.

4. **Güven çıpasını (trust anchor) dışarıda tut.** Doğrulama sertifikası, güvenilen IdP metadata'sından gelmeli; asla gelen mesajın kendisinden alınmamalıdır. Key confusion'ın panzehiri budur.

5. **Anlamsal kontrolleri eksiksiz yap.** `Audience`, `Recipient`, zaman pencereleri, `InResponseTo` (istekle yanıtın eşleşmesi) ve replay koruması, imzadan bağımsız olarak zorunludur. İmza sadece "değiştirilmedi" der; "bana, şimdi, bir kez için geçerli" demez — onu bu kontroller söyler.

6. **XML ayrıştırıcıyı sertleştir.** DTD ve external entity kapalı, katı şema doğrulaması açık. SAML'i "güvenilir XML" gibi değil, "düşman girdisi" gibi ayrıştır.

7. **Kendi kriptografini yazma; olgun kütüphaneyi güncel tut.** SAML imza doğrulaması, yıllarca süren saldırı-yama döngülerinin biriktirdiği ince bir alandır. Bakımlı bir kütüphane ve düzenli güncelleme, elle yazılmış herhangi bir çözümden neredeyse her zaman daha güvenlidir.

8. **Mümkünse daha yeni protokollere geç.** Yeşil alan (greenfield) projelerde, OpenID Connect gibi JSON/JWT tabanlı ve XML-DSig'in yorumlama boşluklarını taşımayan daha modern protokoller genellikle daha küçük bir saldırı yüzeyi sunar. SAML'i sürdürmek gereken yerlerde ise yukarıdaki disiplin şarttır.

Sonuç olarak SAML saldırılarının neredeyse tamamı tek bir cümlede özetlenebilir: **İmzalanan şey ile inanılan şey birbirinden ayrıldığı an, kimlik doğrulama çöker.** XSW bu ayrımı düğüm seviyesinde, comment injection text seviyesinde açar; ama savunma her ikisinde de aynı ilkeye — doğrulama ile işlemeyi tek bir gerçeğe kilitlemeye — dayanır.
