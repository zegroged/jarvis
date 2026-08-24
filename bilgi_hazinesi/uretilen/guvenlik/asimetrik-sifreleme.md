# Asimetrik Şifreleme (RSA/ECC): Padding, Textbook RSA Tehlikesi ve ECC Avantajı

## Tanım ve Temel Kavram

Asimetrik şifreleme (public-key cryptography), matematiksel olarak birbirine bağlı ama birbirinden türetilmesi pratikte imkânsız olan bir anahtar çifti kullanan şifreleme yaklaşımıdır. Bir anahtar herkese açıktır (public key), diğeri gizli tutulur (private key). Simetrik şifrelemedeki temel sorunu, yani "iki tarafın aynı gizli anahtarı nasıl güvenli paylaşacağı" problemini ortadan kaldırır: herkes sizin public key'inizle size mesaj şifreleyebilir ama sadece siz private key ile açabilirsiniz.

İki büyük aile hâkimdir. **RSA** (Rivest-Shamir-Adleman) büyük tam sayıların çarpanlarına ayrılmasının (integer factorization) zorluğuna dayanır. **ECC** (Elliptic Curve Cryptography) ise eliptik eğriler üzerinde tanımlı ayrık logaritma probleminin (elliptic curve discrete logarithm problem, ECDLP) zorluğuna dayanır. Her ikisi de "tek yönlü fonksiyon" (one-way function) fikrini kullanır: bir yöne hesaplaması kolay, tersini almak ise astronomik derecede pahalı olan matematiksel işlemler.

Kritik bir noktayı baştan vurgulamak gerekir: asimetrik şifreleme pratikte **doğrudan veri şifrelemek için kullanılmaz**. Yavaştır ve şifreleyebileceği veri boyutu anahtar boyutuyla sınırlıdır. Bunun yerine gerçek dünyada iki işi yapar: (1) bir simetrik anahtarı güvenli şekilde taşımak veya anlaşmak (key encapsulation / key agreement), (2) dijital imza (digital signature) ile kimlik doğrulama ve bütünlük sağlamak. Asıl veri her zaman AES gibi bir simetrik algoritmayla şifrelenir. Bu "hibrit şifreleme" (hybrid encryption) modeli, TLS'ten PGP'ye kadar her yerde standarttır.

## Kök Neden: RSA Neden Çalışır ve Neden Padding Şart

RSA'nın çalışma mantığını anlamadan padding'in neden hayat memat meselesi olduğunu kavrayamayız. RSA'nın çekirdeği şu modüler üs alma işlemidir:

- Şifreleme: `c = m^e mod n`
- Deşifreleme: `m = c^d mod n`

Burada `n` iki büyük asalın çarpımıdır (`n = p * q`), `e` public exponent, `d` ise private exponent'tir. Güvenlik `n`'i çarpanlarına ayırmanın zorluğuna dayanır; çünkü `d`'yi hesaplamak için `p` ve `q`'yu bilmek gerekir.

İşte tehlike tam burada başlar. Bu ham matematiksel işlem, mesajı `m` sayısını doğrudan alıp üssünü alır. Buna **textbook RSA** (veya "raw RSA") denir. Textbook RSA, matematiksel bir fonksiyondur; **deterministiktir ve hiçbir rastgelelik içermez**. Aynı `m` mesajı, aynı public key ile her zaman tam olarak aynı `c` sonucunu üretir. Bu deterministik davranış, kriptografik olarak felakettir ve padding'in var oluş sebebidir.

Padding, ham mesajı üs alma işleminden önce yapılandırılmış, rastgelelik içeren bir formata dönüştürür. RSA'da iki amaç için iki ayrı padding şeması vardır:

- **OAEP** (Optimal Asymmetric Encryption Padding): şifreleme için.
- **PSS** (Probabilistic Signature Scheme): imza için.

## Textbook RSA'nın Somut Tehlikeleri

Textbook RSA'yı üretimde kullanmak, birden fazla bağımsız kırılma yolu açar. Bunları tek tek düşünmek, padding'in neyi çözdüğünü netleştirir.

### 1. Determinizm ve Sözlük Saldırısı

Şifreleme deterministik olduğu için, saldırgan olası mesajların şifreli hâllerini önceden hesaplayabilir. Diyelim ki bir sistem "EVET" veya "HAYIR" yanıtını public key ile şifreliyor. Saldırgan bu iki kelimeyi kendisi şifreleyip çıkan `c` değerlerini bir tabloya koyar; sonra ağdaki trafiği izleyip hangisinin geçtiğini eşleştirerek içeriği okur. Anahtarı hiç kırmadan gizliliği delmiş olur. Bu, semantic security'nin (anlamsal güvenlik) yokluğudur: iyi bir şifreleme şemasında saldırgan, iki farklı mesajdan hangisinin şifrelendiğini ayırt edememelidir. OAEP, her şifrelemede rastgele bir tohum (seed) kullanarak aynı mesajın bile her seferinde tamamen farklı bir ciphertext üretmesini sağlar.

### 2. Küçük Public Exponent ve Küp Kök Saldırısı

Performans için `e = 3` gibi küçük bir public exponent tercih edildiğinde, textbook RSA çok tehlikeli hâle gelir. Eğer mesaj `m` yeterince küçükse (`m^3 < n` olacak kadar), o zaman `c = m^3 mod n` işlemindeki modüler indirgeme hiç devreye girmez ve `c = m^3` olur. Saldırgan yalnızca `c`'nin normal tam sayı küp kökünü alarak `m`'yi bulur; hiçbir gizli anahtara ihtiyaç yoktur. Padding, mesajı `n`'e yakın büyüklükte bir sayıya doldurarak modüler indirgemenin her zaman devreye girmesini garanti eder ve bu saldırıyı kapatır.

### 3. Håstad Broadcast ve İlgili Saldırılar

Aynı küçük exponent ile aynı mesaj farklı `n` değerlerine sahip birden çok alıcıya gönderilirse (örneğin `e = 3` ile üç ayrı alıcıya), Çin Kalan Teoremi (Chinese Remainder Theorem) kullanılarak orijinal mesaj kurtarılabilir. Bunun kök nedeni yine determinizmdir: her alıcıya aynı `m` gider. Rastgelelik içeren padding, her alıcıya giden mesajı farklılaştırdığı için bu sınıf saldırıları da etkisiz kılar.

### 4. Çarpımsal Homomorfizm ve İmza Sahteciliği

Textbook RSA çarpımsal homomorfik bir özelliğe sahiptir: `(m1^e) * (m2^e) = (m1 * m2)^e mod n`. Bu, iki şifreli metnin çarpımının, mesajların çarpımının şifresi olması demektir. İmza tarafında bu özellik doğrudan sahtecilik imkânı verir. Saldırgan, meşru iki imzayı çarparak hiç imzalanmamış bir üçüncü mesaj için geçerli imza üretebilir (existential forgery). Bu yüzden imzada da ham RSA asla kullanılmaz; PSS bu cebirsel yapıyı bir hash ve rastgele tuz (salt) katmanıyla kırar.

## OAEP: Şifrelemede Doğru Padding

OAEP, mesajı üs almadan önce bir "iki turlu Feistel benzeri" karıştırma yapısından geçirir. Kabaca çalışma mantığı şöyledir: mesaja rastgele bir tohum eklenir, bu tohum ve mesaj birbirine mask generation function (MGF, tipik olarak bir hash tabanlı fonksiyon) aracılığıyla karşılıklı maskelenir. Sonuç, hem rastgeleliğin hem de mesajın tüm çıktı bitlerine yayıldığı bir bloktur.

Bunun iki kritik güvenlik sonucu vardır. Birincisi, şifreleme artık **olasılıksaldır** (probabilistic): aynı mesaj her seferinde farklı ciphertext üretir, böylece semantic security sağlanır. İkincisi, deşifreleme sırasında padding yapısı bozuksa işlem reddedilir; bu, seçilmiş şifreli metin saldırılarına (chosen-ciphertext attack, CCA) karşı direnç kazandırır. OAEP, uygun şekilde uygulandığında IND-CCA2 güvenliği hedefler; yani saldırgan deşifreleme oracle'ına erişse bile anlamlı bilgi sızdıramaz.

Burada tarihî bir dersi anmak gerekir: OAEP'in çözdüğü sorunun bir örneği **Bleichenbacher saldırısıdır**. Daha eski bir padding şeması olan PKCS#1 v1.5, deşifreleme sırasında padding'in geçerli olup olmadığını farklı hata mesajları veya farklı davranışlarla sızdırdığında, saldırgan bunu bir "padding oracle" olarak kullanarak adım adım private key işlemini tersine çevirebiliyordu. Bu, sadece matematiğin değil, **uygulamanın** da güvende olması gerektiğini gösteren klasik bir örnektir. Modern öneri OAEP kullanmaktır; PKCS#1 v1.5 şifreleme yeni tasarımlarda önerilmez.

## PSS: İmzada Doğru Padding

İmza ile şifreleme birbirine karıştırılmamalıdır; farklı garantiler ister. İmzada amaç gizlilik değil, kimlik doğrulama ve bütünlüktür. PSS, imzalanacak mesajın hash'ini alır, buna rastgele bir tuz (salt) ekler ve MGF ile yapılandırılmış olasılıksal bir kodlama üretir. Rastgele tuz sayesinde aynı mesaj her imzalandığında farklı bir imza değeri çıkar; bu, imza şemasının güvenlik kanıtını güçlendirir ve textbook RSA'nın çarpımsal sahtecilik sınıfını kapatır.

PSS'nin sağladığı temel özellik, güçlü var oluşsal sahtecilik direncidir (existential unforgeability): saldırgan çok sayıda geçerli imza görse bile, imzalatmadığı yeni bir mesaj için geçerli imza üretemez. Yaygın alternatif olan PKCS#1 v1.5 imza hâlâ pek çok yerde (örneğin bazı sertifika ekosistemlerinde) kullanılır ve doğru uygulandığında pratikte kırılmış sayılmaz; ancak yeni tasarımlar için PSS, daha sağlam güvenlik argümanına sahip olduğu için tercih edilir.

Kritik bir uyarı: hiçbir zaman "önce imzala sonra şifrele" veya "aynı anahtar çiftini hem imza hem şifreleme için kullan" gibi kestirmelere gidilmemelidir. Bir RSA anahtarı ya imza içindir ya şifreleme; ikisini karıştırmak, bir işlevin oracle'ının diğerini kırmasına yol açabilir.

## ECC Avantajı: Neden Aynı Güvenlik Daha Küçük Anahtarla

ECC'nin RSA karşısındaki asıl üstünlüğü matematiksel zorluğun "yoğunluğundadır". RSA'yı kırmak için en iyi bilinen genel yöntemler (general number field sieve gibi alt-üstel algoritmalar) yeterince hızlıdır ki, güvenliği artırmak için anahtar boyutunu **çok hızlı** büyütmek gerekir. ECDLP'yi kırmak için ise bilinen en iyi genel saldırılar temelde tam üstel karmaşıklıktadır (Pollard rho gibi). Bu, aynı güvenlik seviyesine çok daha küçük anahtarlarla ulaşılabileceği anlamına gelir.

Kabaca büyüklük sıralaması olarak (kesin rakamlar standart kılavuzlarda tanımlıdır, burada mertebe olarak veriyorum): 128-bit simetrik güvenlik seviyesine yakın koruma için RSA yaklaşık 3072-bit anahtar isterken, ECC yaklaşık 256-bit eğri ile aynı seviyeye ulaşır. Güvenlik seviyesi arttıkça bu makas daha da açılır; RSA'nın anahtarları kübik-benzeri hızda büyürken ECC'ninkiler doğrusala yakın büyür.

Bunun pratik sonuçları ciddidir ve neden mobil, IoT ve modern TLS'te ECC'nin baskın hâle geldiğini açıklar:

- **Daha küçük anahtar ve imza boyutu**: daha az bant genişliği, daha küçük sertifikalar, TLS handshake'inde daha az veri.
- **Daha hızlı anahtar üretimi ve imza**: RSA anahtar üretimi büyük asal aramayı gerektirir ve pahalıdır; ECC anahtar üretimi çok daha hafiftir.
- **Daha düşük güç ve bellek tüketimi**: kısıtlı cihazlar için belirleyici.

ECC'nin somut kullanımları: anahtar anlaşması için **ECDH** (Elliptic Curve Diffie-Hellman), tercihen geçici formu **ECDHE** ile ileri gizlilik (forward secrecy) sağlar; imza için **ECDSA** ve daha modern, uygulama hataları riski daha düşük olan **EdDSA** (örneğin Ed25519). Modern eğriler arasında Curve25519 ailesi, dikkatli tasarımı ve yan kanal saldırılarına karşı daha dirençli implementasyon dostu yapısıyla öne çıkar.

### ECC'nin Kendine Özgü Tehlikeleri

ECC "daha küçük anahtar" derken bedava güvenlik vermez; kendi tuzakları vardır ve bunları bilmemek RSA'dan daha tehlikeli olabilir.

- **Nonce tekrarı ECDSA'da felakettir.** ECDSA imzası her seferinde `k` adı verilen rastgele bir değer (nonce) gerektirir. Aynı `k` iki farklı mesajı imzalamak için kullanılırsa, saldırgan basit cebirle private key'i **tamamen** kurtarır. Öngörülebilir veya taraflı (biased) `k` de aynı sonucu verir. Bunun tarihteki en bilinen örneği, bir oyun konsolu ekosisteminde sabit nonce kullanımının imza anahtarını sızdırmasıdır. Çözüm: RFC 6979 ile tanımlanan deterministik nonce türetimi veya EdDSA gibi nonce'u mesaj ve anahtardan deterministik türeten şemalar.
- **Zayıf veya arka kapılı eğriler.** Rastgele üretilmiş gibi görünen ama parametreleri şüpheli seçilmiş eğrilerden kaçınılmalı; iyi incelenmiş standart eğriler (Curve25519, iyi tanımlı NIST eğrileri vb.) tercih edilmelidir.
- **Invalid curve / point validation eksikliği.** Karşı taraftan gelen bir noktanın gerçekten kullanılan eğri üzerinde olup olmadığı doğrulanmazsa, saldırgan zayıf bir eğriye ait nokta göndererek özel anahtar hakkında bilgi sızdırabilir. Alınan her genel nokta doğrulanmalıdır.

## Sömürü/İstismar Mantığı ile Savunma Yan Yana

Saldırı ve savunmayı birlikte düşünmek, hangi tedbirin neyi kapattığını netleştirir.

### Padding Oracle (Bleichenbacher tarzı)

- **İstismar mantığı**: Saldırgan çok sayıda özenle seçilmiş ciphertext'i sunucuya gönderir. Sunucu, padding geçerliyse ve geçersizse farklı tepkiler verir (farklı hata kodu, farklı yanıt süresi, bağlantıyı farklı kapatma). Bu ikili "geçerli/geçersiz" sızıntısı bir oracle'dır; saldırgan bunu binlerce sorgu boyunca kullanarak hedef ciphertext'in düz metnini adım adım daraltır.
- **Savunma**: Padding hatalarını sabit, ayırt edilemez şekilde ele alın; padding geçerli ya da değil, dışarıya aynı davranışı gösterin (constant-time davranış, aynı hata mesajı, aynı zamanlama). Mümkün olan her yerde şifrelemede OAEP kullanın. Protokol seviyesinde, sürüm düşürme (downgrade) ile eski PKCS#1 v1.5 moduna zorlanmayı engelleyin.

### Zamanlama / Yan Kanal Saldırıları

- **İstismar mantığı**: Modüler üs alma veya eğri üzerinde skaler çarpım, işlenen bit'e göre farklı süre veya güç tüketirse, saldırgan bu farkı ölçerek private key bitlerini çıkarır.
- **Savunma**: Constant-time implementasyonlar kullanın; RSA'da blinding (körleme) uygulayın; ECC'de branch'siz, tabloya-veriye-bağlı-erişimsiz skaler çarpım rutinleri seçin. Kendi kriptografinizi yazmayın; iyi denetlenmiş kütüphaneleri kullanın.

### Zayıf Rastgelelik

- **İstismar mantığı**: Anahtar üretimi veya ECDSA nonce üretimi zayıf bir rastgele kaynaktan besleniyorsa, saldırgan anahtar uzayını daraltır. Zayıf entropiyle üretilmiş RSA modülleri, farklı sistemler arasında ortak asal çarpan paylaşabilir; büyük ölçekli tarama ile bu ortak çarpanlar bulunup anahtarlar çarpanlarına ayrılabilir.
- **Savunma**: Kriptografik olarak güvenli rastgele sayı üreteci (CSPRNG) kullanın; işletim sisteminin entropi kaynağına güvenin; gömülü cihazlarda açılış anındaki düşük entropi problemini ciddiye alın; ECDSA yerine deterministik nonce (RFC 6979) veya EdDSA tercih edin.

## Yaygın Hatalar

- **Textbook/raw RSA kullanmak.** Bir kütüphanenin "no padding" seçeneğini seçmek, yukarıdaki tüm saldırı sınıflarını açar. Padding asla isteğe bağlı bir süsleme değildir.
- **Şifreleme ve imza padding'ini karıştırmak.** OAEP şifreleme içindir, PSS imza içindir. Birini diğerinin yerine kullanmak güvenlik kanıtını geçersiz kılar.
- **Aynı anahtar çiftini hem imza hem şifreleme için kullanmak.** İki işlevin oracle'ları birbirini besleyebilir.
- **Asimetrik şifreyle büyük veri şifrelemeye çalışmak.** RSA ile büyük veriyi doğrudan şifrelemek yanlıştır; hibrit model kullanın (asimetrik ile bir simetrik anahtarı taşıyın, veriyi AES-GCM gibi authenticated encryption ile şifreleyin).
- **ECDSA nonce'unu tekrarlamak veya zayıf üretmek.** Tek bir nonce tekrarı bile özel anahtarın tamamını sızdırır.
- **Gelen ECC noktalarını doğrulamamak.** Point validation eksikliği invalid-curve saldırılarına kapı açar.
- **Padding hatalarını farklı işleyerek oracle sızdırmak.** Hata yolları da constant-time ve ayırt edilemez olmalıdır.
- **İmza doğrulamada algoritmayı mesajın söylediğine güvenmek.** Örneğin bir token'ın header'ının belirttiği algoritmayı sorgusuz kabul etmek (algoritma karışıklığı) imza doğrulamasını atlatabilir; beklenen algoritmayı sunucu tarafında sabitleyin.

## En İyi Pratikler

- **Doğrulanmış, bakımlı kriptografi kütüphaneleri kullanın.** Kendi RSA/ECC matematiğinizi yazmayın; padding, constant-time davranış ve nokta doğrulaması gibi ayrıntılar uzman denetimi ister.
- **Şifrelemede RSA-OAEP, imzada RSA-PSS** tercih edin; yeni tasarımlarda PKCS#1 v1.5 şifrelemeden kaçının.
- **Anahtar boyutlarını güncel kılavuzlara göre seçin.** RSA için en az 3072-bit mertebesi çağdaş bir referanstır; ECC için 256-bit sınıfı eğriler (Curve25519/Ed25519 gibi) modern varsayılan olarak güçlüdür.
- **Hibrit şifreleme uygulayın.** Asimetrik ile simetrik anahtar taşıyın/anlaşın, veriyi authenticated encryption (AES-GCM, ChaCha20-Poly1305) ile koruyun.
- **İleri gizlilik için geçici anahtar anlaşması** kullanın (ECDHE). Böylece uzun ömürlü özel anahtar ileride ele geçse bile geçmiş oturumlar çözülemez.
- **ECDSA yerine mümkünse EdDSA (Ed25519)** kullanın; deterministik nonce sayesinde en yıkıcı ECC hatasını tasarımla kapatır. ECDSA gerekiyorsa RFC 6979 deterministik nonce uygulayın.
- **Tüm harici girdileri doğrulayın**: gelen ECC noktalarını eğri üzerinde olup olmadığına göre kontrol edin; imza doğrulamada beklenen algoritmayı sabitleyin.
- **Constant-time ve blinding** garantilerini kütüphane seviyesinde sağlayın; yan kanal yüzeyini küçültün.
- **Anahtar yaşam döngüsünü yönetin**: anahtarları HSM veya güvenli anahtar deposunda tutun, rotasyon ve iptal (revocation) süreçlerini tanımlayın, özel anahtarları asla kod deposuna veya log'lara koymayın.
- **Post-quantum ufkunu gözden kaçırmayın.** Hem RSA hem ECC, yeterince büyük bir kuantum bilgisayarına karşı (Shor algoritması) teorik olarak kırılabilir. Uzun ömürlü verileri koruyan sistemler için, standartlaşan post-quantum algoritmalara geçiş veya hibrit (klasik + PQC) yaklaşımlar orta vadeli planınızda yer almalıdır.

## Özet

Asimetrik şifrelemenin gücü matematiktedir ama güvenliği **uygulamada** kazanılır veya kaybedilir. RSA'nın çekirdek matematiği deterministik ve homomorfiktir; bu yüzden ham/textbook hâli felakettir ve OAEP (şifreleme) ile PSS (imza) padding şemaları, rastgelelik ve yapılandırılmış kodlama ekleyerek semantic security ve sahtecilik direnci sağlar. ECC ise aynı güvenlik seviyesini çok daha küçük anahtarlarla, daha hızlı ve daha az kaynakla sunarak modern sistemlerde baskın hâle gelmiştir; fakat nonce tekrarı ve nokta doğrulama eksikliği gibi kendine has, çok yıkıcı tuzakları vardır. Doğru yaklaşım her zaman aynıdır: denetlenmiş kütüphaneler, doğru padding, hibrit şifreleme, ileri gizlilik, deterministik/güvenli rastgelelik ve girdi doğrulama.
