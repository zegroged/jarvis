# MAC, HMAC ve Sabit-Zamanlı Karşılaştırma

## Giriş: Bütünlük Neden Gizlilikten Ayrı Bir Sorundur

Kriptografiye yeni başlayanların en yaygın hatası, "veriyi şifreledim, artık güvende" diye düşünmektir. Bu düşünce eksiktir. Şifreleme (encryption) yalnızca **gizliliği** (confidentiality) sağlar; yani veriyi okuyamayan birinin içeriğini anlamasını engeller. Ama şifreleme tek başına **bütünlüğü** (integrity) ve **kimlik doğrulamayı** (authentication) sağlamaz. Bir saldırgan şifreli metni okuyamasa bile, onu değiştirebilir, parçalarını yer değiştirebilir veya bit'lerini çevirebilir. Özellikle CTR, OFB gibi stream cipher modlarında saldırgan, şifreli metindeki bir bit'i çevirdiğinde çözülmüş (decrypt) metinde tam olarak karşılık gelen bit çevrilir. Yani "malleability" (yoğrulabilirlik) denen bu özellik yüzünden, gizlilik sağlansa bile bir düşman mesajı hedefli biçimde bozabilir.

İşte **MAC** (Message Authentication Code, Mesaj Doğrulama Kodu) bu boşluğu doldurur. MAC iki soruyu birden yanıtlar: "Bu mesaj yolda değiştirildi mi?" (bütünlük) ve "Bu mesaj gerçekten paylaşılan anahtarı bilen taraftan mı geliyor?" (kimlik doğrulama). Bu makale MAC'in ne olduğunu, HMAC'in neden bu kadar yaygınlaştığını, timing attack'ların MAC doğrulamasını nasıl sessizce çökerttiğini ve sabit-zamanlı (constant-time) karşılaştırmanın neden bir tercih değil zorunluluk olduğunu derinlemesine ele alır.

## MAC Nedir?

### Tanım ve Temel Çalışma Mantığı

Bir MAC, iki parametre alan bir fonksiyondur: gizli bir anahtar `K` ve mesaj `m`. Çıktı olarak sabit uzunlukta bir etiket (tag) üretir:

```
tag = MAC(K, m)
```

Gönderen taraf mesajı ve etiketi birlikte yollar: `(m, tag)`. Alıcı, aynı gizli anahtar `K` ile kendi tarafında `tag' = MAC(K, m)` hesaplar ve gelen `tag` ile hesapladığı `tag'` değerini karşılaştırır. Eğer eşitlerse mesaj hem değiştirilmemiştir hem de anahtarı bilen biri tarafından üretilmiştir. Çünkü anahtarı bilmeyen bir saldırgan, herhangi bir `m` için geçerli bir `tag` üretemez. MAC'in güvenlik tanımı tam olarak budur: **existential unforgeability under chosen-message attack** (EUF-CMA). Yani saldırgan istediği kadar mesaj için geçerli etiket görse bile, daha önce görmediği yeni bir mesaj için geçerli bir etiket üretememelidir.

### Kök Neden: Neden Simetrik Anahtar Yeterli?

MAC simetrik bir yapıdır; hem üreten hem de doğrulayan taraf aynı gizli anahtarı paylaşır. Bu, güvenliğin kaynağıdır ama aynı zamanda temel kısıtıdır. Anahtarı bilen herkes hem geçerli etiket üretebilir hem de doğrulayabilir. Bu simetri, MAC'i çok hızlı kılar (asimetrik kripto'ya göre onlarca-yüzlerce kat) ama önemli bir şeyi imkânsızlaştırır: **non-repudiation** (inkâr edilemezlik). Alıcı, bir mesajın gerçekten göndericiden geldiğini üçüncü bir tarafa (örneğin bir hâkime) kanıtlayamaz; çünkü alıcının kendisi de aynı anahtarla o etiketi üretebilirdi. Bu ayrım, ileride "imza vs MAC" bölümünde kritik olacak.

## HMAC: Hash Tabanlı MAC ve Neden Böyle Tasarlandı

### Naif Yaklaşımın Neden Çöktüğü

Sezgisel olarak insan şöyle düşünür: "Elimde SHA-256 gibi güçlü bir hash var. Anahtarı mesajın önüne ekleyip hash'lersem MAC olur, değil mi? `tag = H(K || m)`." Bu, **length extension attack** (uzunluk uzatma saldırısı) yüzünden tehlikelidir ve MD5, SHA-1, SHA-256 gibi Merkle-Damgard yapısındaki hash'lerde kırılır.

Kök neden şudur: Merkle-Damgard hash'leri mesajı bloklara böler ve her bloğu bir iç durum (internal state) üzerinden işler. Fonksiyonun nihai çıktısı, aslında hash'in son iç durumudur. Saldırgan `H(K || m)` değerini biliyorsa, bu değeri iç durum olarak alıp hash'e devam edebilir ve anahtarı hiç bilmeden `H(K || m || padding || m')` için geçerli bir etiket üretebilir. Yani saldırgan mesajın sonuna kendi seçtiği veriyi ekleyip yine de geçerli bir etiket hesaplayabilir. Bu, MAC'in temel güvenlik hedefini (unforgeability) tamamen çökertir.

`tag = H(m || K)` (anahtarı sona koymak) length extension'ı önler ama bu kez hash fonksiyonunun collision (çakışma) dayanıklılığına fazla bel bağlar ve başka zayıflıklar doğurur.

### HMAC'in Çözümü: İç İçe Hash

HMAC tam olarak bu problemleri çözmek için tasarlandı. Yapısı iki iç içe hash çağrısıdır:

```
HMAC(K, m) = H( (K' XOR opad) || H( (K' XOR ipad) || m ) )
```

Burada:
- `K'`, anahtarın hash bloğu boyutuna getirilmiş (gerekirse hash'lenmiş veya sıfırlarla doldurulmuş) halidir.
- `ipad`, `0x36` bayt'ının blok boyunca tekrarıdır (inner pad).
- `opad`, `0x5c` bayt'ının blok boyunca tekrarıdır (outer pad).

Neden iki hash? Dıştaki hash çağrısı, içteki hash'in çıktısını bir kez daha anahtarla harmanlayarak length extension attack'ı imkânsızlaştırır. Saldırgan içteki `H((K' XOR ipad) || m)` değerini görmez; yalnızca en dıştaki sonucu görür, dolayısıyla iç durumu ele geçirip uzatma yapamaz. `ipad` ve `opad`'ın farklı olması ise, iki hash çağrısının efektif olarak iki farklı anahtardan türetilmiş gibi davranmasını sağlar; bu, güvenlik ispatının önemli bir parçasıdır.

HMAC'in güzelliği, güvenliğinin altında yatan varsayımın oldukça zayıf olmasıdır: Kullanılan hash fonksiyonunun tam anlamıyla çakışma dayanıklı olması bile şart değildir. Nitekim SHA-1 collision'a karşı kırıldığında bile, HMAC-SHA1 pratikte kırılmadı; çünkü HMAC'in güvenliği hash'in bir PRF (pseudorandom function) gibi davranmasına dayanır, çarpışma direncine değil. Yine de yeni sistemlerde HMAC-SHA256 veya HMAC-SHA512 tercih edilmelidir.

### Alternatifler: Yalnızca HMAC Yok

HMAC en yaygın MAC'tir ama tek seçenek değildir. Modern sistemlerde şu alternatifler önemlidir:

- **Poly1305**: Genellikle ChaCha20 ile birlikte (ChaCha20-Poly1305 AEAD) kullanılan, tek kullanımlık anahtar gerektiren, çok hızlı bir MAC'tir.
- **GMAC**: GCM modunun MAC bileşenidir; donanım hızlandırması (AES-NI, PCLMULQDQ) ile çok hızlıdır.
- **KMAC**: SHA-3 (Keccak) ailesine dayanır. Keccak sünger (sponge) yapısı length extension'a doğal olarak dayanıklı olduğundan, SHA-3 için HMAC'in iç içe yapısına gerek yoktur; anahtarı doğrudan önekleyerek MAC yapılabilir. KMAC bunun standartlaştırılmış halidir.

Modern uygulama tavsiyesi çoğu zaman şudur: MAC'i elle birleştirmek yerine bir **AEAD** (Authenticated Encryption with Associated Data) şeması kullan; örneğin AES-GCM veya ChaCha20-Poly1305. Bunlar şifreleme ve bütünlüğü tek, ispatlanmış bir yapıda birleştirir ve "encrypt-then-MAC"i doğru sırayla, senin yerine yapar.

## Encrypt-then-MAC: Sıralama Neden Önemli

Şifreleme ve MAC'i birlikte kullanırken sıralama güvenlik açısından belirleyicidir. Üç temel yaklaşım vardır:

- **Encrypt-and-MAC**: `C = Enc(m)`, `T = MAC(m)`. MAC düz metnin üzerine uygulanır. Sorunlu; çünkü MAC deterministik olduğundan aynı düz metin aynı etiketi verir ve bilgi sızdırabilir.
- **MAC-then-Encrypt**: `T = MAC(m)`, `C = Enc(m || T)`. Alıcı önce çözer, sonra MAC'i doğrular. Sorun: alıcı geçersiz bir şifreli metni bile önce çözmek zorunda kalır, bu da padding oracle gibi saldırılara kapı açar (eski TLS'in başına gelen budur).
- **Encrypt-then-MAC (EtM)**: `C = Enc(m)`, `T = MAC(C)`. MAC şifreli metnin üzerine uygulanır. Alıcı **önce** MAC'i doğrular; geçersizse şifreli metni hiç çözmeden reddeder. Bu, çoğu durumda ispatlanabilir biçimde en güvenli yaklaşımdır ve sektör standardıdır.

Kök neden: EtM'de saldırganın gönderdiği bozuk şifreli metin, çözme (decryption) koduna hiç ulaşmadan reddedilir. Böylece decryption sürecindeki hataları (padding hataları gibi) gözlemleyerek bilgi sızdıran oracle saldırıları baştan engellenmiş olur.

## Timing Attack: MAC Doğrulamasının Sessiz Katili

### Sorunun Tanımı

Diyelim ki HMAC'i kusursuz uyguladınız, doğru anahtarı, doğru yapıyı kullandınız. Şimdi doğrulama anı geldi: gelen `tag` ile hesapladığınız `expected` değerini karşılaştırıyorsunuz. Programcının içgüdüsel refleksi şudur:

```python
if received_tag == expected_tag:
    kabul_et()
```

Ya da C'de daha da tehlikelisi:

```c
if (memcmp(received_tag, expected_tag, 32) == 0) { ... }
```

Bu satır, tüm HMAC güvenliğinizi çöpe atabilir. Neden? Çünkü hem dillerin `==` operatörü hem de `memcmp`, byte dizilerini **soldan sağa karşılaştırır ve ilk farklılıkta hemen durur** (short-circuit / early return). Bu erken çıkış, karşılaştırmanın süresini veri-bağımlı (data-dependent) hale getirir.

### Kök Neden: Neden Süre Sızıntısı Anlamlı?

İlk byte'ı yanlış olan bir tahmin, karşılaştırmayı hemen (ilk adımda) bitirir. İlk 5 byte'ı doğru, 6.'sı yanlış olan bir tahmin ise 6 adım sürer; yani biraz daha uzun zaman alır. Bu zaman farkı nano-saniyeler mertebesindedir ama **istatistiksel olarak ölçülebilir**. Saldırgan, doğrulama endpoint'ine milyonlarca istek gönderip yanıt sürelerinin ortalamasını alarak gürültüyü bastırabilir.

İstismar mantığı şöyle işler: Saldırgan ilk byte için 256 olası değeri de dener. Hangi değer sistematik olarak biraz daha uzun sürüyorsa, ilk byte doğru tahmin edilmiş demektir (çünkü karşılaştırma bir adım daha ilerlemiştir). O byte'ı sabitler, ikinci byte'a geçer, yine 256 değeri dener. Böylece etiketi **byte byte** kurar. Kaba kuvvetle (brute force) 32 byte'lık bir etiketi tahmin etmek `2^256` denemedir; imkânsız. Ama byte-byte yaklaşımda maliyet yaklaşık `32 × 256 = 8192` denemeye (her byte için ortalama) düşer; pratikte bir saldırının erişebileceği bir sayıya iner. Üstel problem, doğrusal probleme dönüşür. Timing attack'ın yıkıcılığı tam olarak budur: forgery'i imkânsızlıktan uygulanabilirliğe taşır.

### Gerçek Dünyadan Bir Örnek Kalıbı

Bu saldırı akademik bir merak değildir. Web framework'lerinde, özellikle webhook imza doğrulama ve API token karşılaştırma noktalarında geçmişte ciddi zafiyetler bulunmuştur. Tipik senaryo şudur: Bir ödeme sağlayıcısı veya SaaS servisi, gönderdiği webhook'lara bir HMAC imzası ekler. Alıcı uygulama, bu imzayı normal string eşitliğiyle (`==`) doğrularsa, saldırgan kendi sahte webhook'una geçerli bir imza üretebilir hale gelir; çünkü imzayı byte-byte kurabilir. Bu da yetkisiz "ödeme başarılı" bildirimleri gibi felaketlere yol açar.

Ağ üzerindeki jitter (gecikme dalgalanması) timing attack'ı zorlaştırır ama yeterli örnekle imkânsız kılmaz. Aynı makinede çalışan (co-located) süreçler veya düşük gecikmeli ağlar söz konusuysa saldırı çok daha kolaylaşır. "Ağ gürültüsü beni korur" varsayımı güvenli bir dayanak değildir.

## Savunma: Sabit-Zamanlı (Constant-Time) Karşılaştırma

### Temel Fikir

Çözüm, karşılaştırmanın süresini **verilere bağımlı olmaktan çıkarmaktır**. Sabit-zamanlı karşılaştırma, iki dizinin ilk byte'ı da son byte'ı da farklı olsa, aynı sürede tamamlanır. Bunu başarmanın yolu, erken çıkışı ortadan kaldırmak ve **her zaman tüm byte'ları taramaktır**. Klasık kalıp XOR-biriktirme yöntemidir:

```c
int constant_time_equals(const unsigned char *a,
                         const unsigned char *b,
                         size_t len) {
    unsigned char diff = 0;
    for (size_t i = 0; i < len; i++) {
        diff |= a[i] ^ b[i];   // hicbir zaman erken cikma yok
    }
    return diff == 0;          // tum byte'lar esitse diff 0 kalir
}
```

Kök neden: `a[i] ^ b[i]` iki byte eşitse 0, farklıysa sıfırdan farklı üretir. Bunları `|=` ile biriktirdiğimizde, herhangi bir byte farklıysa `diff` sıfırdan farklı olur. Döngü **her koşulda** baştan sona işler; farkın nerede olduğu süreyi değiştirmez. Böylece saldırganın byte-byte ilerlemesini sağlayan sinyal ortadan kalkar.

Not: İki dizinin uzunlukları farklıysa bile süre sızıntısına dikkat edilmelidir. Genelde önce uzunlukları sabit-zamanlı biçimde kontrol etmek veya uzunluk farkını dizinin içeriğinden ayrı ele almak gerekir. Bir de HMAC etiketleri sabit uzunlukta olduğundan, iyi tasarlanmış bir sistemde uzunluk zaten bilinen ve sabit bir değerdir.

### Dillerin Hazır Fonksiyonları: Kendin Yazma

En iyi pratik, bu fonksiyonu kendin yazmamaktır; çünkü modern derleyiciler agresif optimizasyon yapar ve senin "sabit zamanlı" döngünü fark edip erken-çıkışlı bir sürümle değiştirebilir ya da branch prediction devreye girebilir. Bunun yerine standart kütüphanelerin kendi denetlenmiş, sabit-zamanlı fonksiyonlarını kullan. Genel kalıplar (kesin isim ve imzaları kullandığınız sürümde doğrulayın):

- **Python**: `hmac.compare_digest(a, b)`. Standart kütüphanenin `secrets` ve `hmac` modüllerinde sabit-zamanlı karşılaştırma için tasarlanmıştır.
- **Node.js**: `crypto.timingSafeEqual(a, b)`. İki `Buffer` alır ve eşit uzunlukta olmalarını bekler.
- **Go**: `crypto/subtle` paketindeki `subtle.ConstantTimeCompare(x, y)`.
- **Java**: `java.security.MessageDigest.isEqual(a, b)` (modern JDK sürümlerinde sabit-zamanlı olacak biçimde uygulanmıştır).
- **OpenSSL / C**: `CRYPTO_memcmp` sabit-zamanlı karşılaştırma amacıyla sağlanır; `memcmp` yerine bu kullanılmalıdır.

Bu fonksiyonların adları ve tam imzaları sürümden sürüme değişebilir; üretime almadan önce kullandığınız sürümün dokümanından teyit edin. Kavram sabittir: **kripto sırlarını asla `==`, `memcmp`, `equals()` gibi erken-çıkışlı karşılaştırmalarla kıyaslama.**

### Daha Derin Bir Savunma: Etiketi Hash'le

Bazı kütüphanelerde ekstra bir savunma katmanı vardır: karşılaştırmadan önce her iki etiketi de rastgele (oturuma özel) bir anahtarla tekrar HMAC'lemek, sonra sonuçları karşılaştırmak. Böylece saldırgan zamanlama sinyalini gözlemlese bile, gözlemlediği şey gerçek etiketin byte'ları değil, tahmin edemeyeceği bir anahtarla dönüştürülmüş halidir. Bu "double HMAC" tekniği, sabit-zamanlı karşılaştırmanın ele alınmasının zor olduğu ortamlarda (örneğin timing garantisi vermeyen üst düzey diller) ek güvence sağlar. Yine de birincil savunma her zaman doğru bir constant-time karşılaştırma fonksiyonu kullanmaktır.

## İmza vs MAC: Kritik Ayrım

Bu iki kavram sık karıştırılır ama güvenlik modelleri temelden farklıdır.

### Simetrik vs Asimetrik

**MAC simetriktir**: Tek bir gizli anahtar hem etiketi üretir hem de doğrular. Üreten ve doğrulayan aynı anahtarı paylaşmak zorundadır.

**Dijital imza (digital signature) asimetriktir**: İmzalayan tarafın **özel anahtarı** (private key) ile imza üretilir, herkese açık **açık anahtar** (public key) ile doğrulanır. Doğrulayan tarafın imza üretme yeteneği yoktur; yalnızca doğrulayabilir. RSA, ECDSA, Ed25519 bu kategoridedir.

### Non-Repudiation: En Önemli Fark

Bu asimetri, temel bir güvenlik özelliğini doğurur: **inkâr edilemezlik (non-repudiation)**. İmzayı yalnızca özel anahtarın sahibi üretebildiği için, geçerli bir imza, mesajın o kişiden geldiğine dair üçüncü taraflara karşı kanıttır. İmzalayan "ben yapmadım" diyemez; çünkü kimsenin onun özel anahtarı yoktur.

MAC'te bu mümkün değildir. Alıcı da anahtarı bildiği için, herhangi bir mesajın gönderenden mi yoksa alıcının kendisinden mi geldiğini üçüncü bir tarafa kanıtlayamaz. İkisi de aynı etiketi üretebilir. Bu yüzden hukukî belge imzalama, kod imzalama (code signing), sertifika zincirleri gibi "kim yaptı?" sorusunun kanıtlanması gereken yerlerde MAC değil, **dijital imza** kullanılır.

### Hangisini Ne Zaman?

- **MAC/HMAC kullan**: İki tarafın zaten güvenli bir anahtar paylaştığı, hızın önemli olduğu, inkâr edilemezliğe ihtiyaç olmayan durumlar. Örnek: TLS oturumu içindeki kayıt (record) bütünlüğü, API isteklerinin HMAC ile imzalanması (paylaşılan gizli anahtarla), oturum çerezlerinin (session cookie) bütünlüğü.
- **Dijital imza kullan**: İmzalayanın kimliğinin üçüncü taraflarca kanıtlanması gereken, tarafların ortak sır paylaşmadığı, ölçeklenebilir açık-anahtar dağıtımı gereken durumlar. Örnek: TLS sertifikaları, yazılım güncellemelerinin imzalanması, JWT'lerin asimetrik imzalanması (RS256/ES256), blockchain işlemleri.

Bir ayrıntı: JWT dünyasındaki `HS256` aslında HMAC-SHA256'dır (simetrik, MAC), `RS256` ise RSA imzasıdır (asimetrik). Bu ikisini karıştırmak ciddi bir güvenlik açığı sınıfı doğurmuştur: Bazı kütüphaneler `alg` alanına körü körüne güvendiğinden, saldırgan `alg`'ı `RS256`'dan `HS256`'ya çevirip **açık anahtarı HMAC anahtarı gibi kullanarak** geçerli token üretebilmiştir. Kök neden, doğrulama tarafının algoritmayı token'ın kendisinden okuyup güvenmesidir. Savunma: Doğrulayıcıda beklenen algoritmayı **sabit olarak** belirtmek ve token'ın `alg` alanına asla güvenmemektir.

## Yaygın Hatalar

Uzman gözüyle en sık görülen ve en pahalıya patlayan hatalar şunlardır:

1. **Sadece şifreleme, MAC yok**: "Şifreledim, güvende" yanılgısı. Bütünlük yoksa saldırgan malleability ile mesajı bozar. Çözüm: AEAD kullan veya encrypt-then-MAC uygula.

2. **`H(K || m)` ile elle MAC yapmak**: Length extension attack'a açık. Çözüm: HMAC veya standart bir MAC kullan, elle hash birleştirme.

3. **Etiketi `==` / `memcmp` ile karşılaştırmak**: Timing attack'a davetiye. Çözüm: dilin constant-time karşılaştırma fonksiyonu.

4. **Anahtar yeniden kullanımı ve karıştırma**: Aynı anahtarı hem şifreleme hem MAC için kullanmak. Farklı amaçlar için ayrı anahtarlar türetilmelidir (örneğin bir KDF ile). Anahtar ayrımı (key separation) ilkesi ihlal edilmemelidir.

5. **Nonce/tek kullanımlık anahtarların tekrarı**: Poly1305 ve GCM gibi yapılarda aynı nonce'un aynı anahtarla iki kez kullanılması MAC anahtarını ifşa edebilir ve kimlik doğrulamayı tamamen çökertir. Nonce yönetimi kritiktir.

6. **`alg` alanına güvenmek (JWT)**: Algoritma karıştırma saldırısı. Çözüm: beklenen algoritmayı doğrulayıcıda sabitle.

7. **Doğrulama başarısızlığında ayrıntılı hata mesajı vermek**: "Etiketin 6. byte'ı yanlış" gibi bir mesaj başlı başına bir oracle'dır. Reddetme her zaman aynı, genel ve sabit-zamanlı olmalıdır.

8. **Kısa etiket kırpma**: Etiketi ilk birkaç byte'a kırpmak (truncation) bazı standartlarda kabul edilir ama fazla kısaltmak brute-force forgery şansını artırır. Etiketi gereğinden fazla kısaltma.

## En İyi Pratikler

Bu konudaki uzman konsensüsünü şöyle özetleyebiliriz:

- **Elle şema kurma, AEAD kullan**: Mümkünse AES-GCM veya ChaCha20-Poly1305 gibi ispatlanmış bir authenticated encryption şeması tercih et. Şifreleme ve bütünlüğü doğru sırayla birlikte halleder.
- **Ayrı bir MAC gerekiyorsa HMAC-SHA256/512 kullan**: İyi denetlenmiş, ispatlanmış, yaygın. Kendi MAC'ini icat etme.
- **Encrypt-then-MAC ilkesine uy**: MAC'i şifreli metnin üzerine uygula ve çözmeden önce doğrula.
- **Karşılaştırmalar daima sabit-zamanlı olsun**: Kripto sırlarını (etiket, token, parola hash'i, imza) asla `==`/`memcmp` ile karşılaştırma; dilin `compare_digest`, `timingSafeEqual`, `ConstantTimeCompare`, `CRYPTO_memcmp` gibi fonksiyonlarını kullan.
- **Anahtar ayrımı uygula**: Her amaç için ayrı anahtar; anahtarları bir KDF (örneğin HKDF) ile türet. Aynı anahtarı birden fazla rolde kullanma.
- **Nonce/IV yönetimini ciddiye al**: Nonce tekrarını mutlak surette engelle. Sayaç tabanlı veya rastgele-yeterli nonce stratejisi seç ve tekrar olmadığını garanti et.
- **İnkâr edilemezlik gerekiyorsa imzaya geç**: "Kim yaptı?" kanıtlanmalıysa MAC yetmez; Ed25519 / ECDSA gibi dijital imza kullan.
- **Doğrulama başarısızlığı sessiz ve tek tip olsun**: Genel bir hata döndür; ayrıntı sızdırma, süre sızdırma.
- **Kütüphaneye güven, kripto'yu kendin yazma**: Denetlenmiş, güncel tutulan kripto kütüphanelerini kullan. "Kendi kripto'nu yazma" ilkesi burada da geçerlidir; hataların bedeli çok yüksektir.

## Sonuç

MAC ve HMAC, modern güvenli iletişimin görünmez ama vazgeçilmez temelleridir. Şifreleme gizliliği verir; MAC ise mesajın hem değişmediğini hem de doğru taraftan geldiğini garanti eder. HMAC, naif hash-tabanlı MAC'lerin length extension gibi tuzaklarını iç içe yapısıyla aşan, sağlam ve ispatlanmış bir tasarımdır. Ancak en güçlü MAC bile, doğrulama anındaki tek bir dikkatsiz `==` satırıyla timing attack üzerinden çökertilebilir; bu yüzden sabit-zamanlı karşılaştırma bir zarafet değil, bir zorunluluktur. Son olarak, MAC ile dijital imza arasındaki ayrımı (simetrik vs asimetrik, inkâr edilemezliğin var/yok oluşu) doğru anlamak, hangi problemde hangi aracın kullanılacağını belirler. Kriptografide güvenlik, doğru primitifi seçmek kadar, onu doğru uygulamakta yatar; ve bu konuda ayrıntılar her zaman belirleyicidir.
