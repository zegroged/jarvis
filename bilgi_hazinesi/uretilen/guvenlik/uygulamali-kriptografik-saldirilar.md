# Uygulamalı Kriptografik Saldırılar: Bleichenbacher, ROCA, Nonce Reuse, Bit-flipping, Length Extension

## Giriş: Neden Bu Konu Kritik

Kriptografik primitifler (RSA, ECC, HMAC, AES) matematiksel olarak kanıtlanabilir güvenlik seviyeleri sunar; ancak bu kanıtlar hep belirli bir **kullanım modeli** altında geçerlidir. Pratikte kırılan neredeyse hiçbir sistem "AES kırıldı" ya da "RSA çözüldü" şeklinde değildir — kırılan şey, primitifin **protokole entegrasyonu**dur: padding şeması, rastgelelik kaynağı, hata mesajı davranışı, anahtar üretim algoritması. Bu makale, teorik primitifin doğru olmasına rağmen mühendislik hatalarının nasıl tam sistem kırılmasına yol açtığını gösteren beş tarihsel saldırı sınıfını ele alır. Amaç, bir savunmacının bu saldırı sınıflarının **kök nedenini** kavraması, kod incelemesinde veya mimari tasarımda bu hataları tanıyabilmesi ve tespit/savunma mekanizmalarını kurabilmesidir.

Ortak tema şudur: **kriptografik bir işlemin başarı/başarısızlık durumu, bir yan kanal (oracle) haline geldiğinde, saldırgan bu oracle'ı binlerce/milyonlarca kez sorgulayarak gizli bilgiyi bit bit veya blok blok yeniden inşa edebilir.** Bu, kriptanalizin matematiksel kırılması değil, **protokolün bilgi sızdırmasıdır**.

---

## 1. Bleichenbacher Saldırısı (PKCS#1 v1.5 Padding Oracle)

### Tanım ve Kök Neden

1998'de Daniel Bleichenbacher'ın SSL/TLS'e karşı yayınladığı saldırı, RSA'nın PKCS#1 v1.5 padding şemasını hedef alır. RSA şifreli bir mesaj çözüldüğünde, sonuç şu formatta olmalıdır:

```
00 02 [rastgele dolgu, sıfır içermez] 00 [gerçek veri]
```

Kök neden şudur: sunucu, çözülen metnin bu formata **uyup uymadığını** istemciye bir şekilde bildirir (açık hata mesajı, farklı TLS alert kodu, zamanlama farkı veya bağlantının kesiliş şekli). Bu "uygun/uygun değil" bilgisi, matematiksel olarak RSA'yı kırmaz ama **bir padding oracle** yaratır. RSA'nın homomorfik çarpma özelliği (`(m1*m2)^e mod n = m1^e * m2^e mod n`) sayesinde saldırgan, ele geçirdiği şifreli metni belirli sabitlerle çarpıp oracle'a tekrar tekrar sorarak, geçerli/geçersiz padding cevaplarından adım adım orijinal düz metni (genellikle bir TLS pre-master secret) yeniden inşa eder. Bu binlerce ile milyonlarca sorgu gerektirebilir ama hesaplama açısından tam kaba kuvvetten kat kat ucuzdur.

### Neden Hâlâ Güncel: ROBOT ve Varyantları

2017'de "ROBOT" (Return Of Bleichenbacher's Oracle Threat) araştırması, aynı zafiyetin onlarca büyük vendor'ın TLS implementasyonunda hâlâ var olduğunu gösterdi — 19 yıl sonra. Neden? Çünkü PKCS#1 v1.5 hâlâ geriye dönük uyumluluk için kullanılıyor ve "sabit zamanlı, sabit davranışlı hata işleme" yazmak göründüğünden zor. Her yeni implementasyon, oracle'ı yeniden icat etme riski taşır: hata mesajı metni farklı olabilir, ama TCP bağlantı kapatma zamanlaması, TLS alert türü (decode_error vs decrypt_error) ya da yanıt süresi (timing side-channel) da bilgi sızdırabilir.

### Nasıl Çalıştığı (Kavramsal) ve Tespit

Saldırgan akışı: (1) hedeflenen şifreli metni ele geçir, (2) rastgele bir çarpan ile çarparak varyantlar üret, (3) her varyantı sunucuya gönder, (4) sunucunun cevabından (hata tipi, gecikme, bağlantı davranışı) padding'in geçerli olup olmadığını çıkar, (5) Bleichenbacher'ın adaptif aralık daraltma algoritmasıyla arama uzayını iteratif küçült.

**Tespit açısından**: SOC/WAF seviyesinde, aynı istemciden aynı hedef bağlantı/sertifika için anormal sayıda TLS handshake hatası (özellikle `decrypt_error` / `bad_record_mac` patlaması) klasik bir Bleichenbacher/ROBOT tarama imzasıdır. Saniyeler içinde binlerce el sıkışma denemesi, otomatik oracle sorgulamasının işaretidir.

**Savunma**: Modern TLS (1.3) PKCS#1 v1.5'i tamamen kaldırıp RSA-OAEP veya ECDHE tabanlı anahtar değişimini zorunlu kılar — bu en sağlam çözümdür (zafiyet sınıfını protokolden çıkarmak). PKCS#1 v1.5 desteklenmesi gerekiyorsa: **sabit zamanlı ve sabit davranışlı hata işleme** (padding hatasında bile rastgele bir pre-master secret üretip normal akışa devam etme — RFC 5246'nın önerdiği "Bleichenbacher countermeasure"), tüm hata yollarının aynı gecikmeye ve aynı TLS alert koduna sahip olmasının garanti edilmesi. Kod incelemesinde aranacak anti-pattern: decrypt fonksiyonunun padding kontrolüne göre **farklı early-return** yolları içermesi.

---

## 2. ROCA Zafiyeti (Zayıf RSA Anahtar Üretimi)

### Tanım ve Kök Neden

ROCA (Return of Coppersmith's Attack), 2017'de keşfedilen ve Infineon'un RSALib kütüphanesindeki RSA anahtar üretim algoritmasını etkileyen bir zafiyettir. Bu, bir protokol hatası değil, **anahtar üretim algoritmasının matematiksel yapısındaki bir zayıflıktır**: performans optimizasyonu için asal sayılar (`p`, `q`) tamamen rastgele seçilmek yerine belirli bir yapıya (primoryal tabanlı bir formda, `p = k*M + (65537^a mod M)` benzeri bir kalıba) sahip olacak şekilde üretiliyordu. Bu yapı, asal üretimini hızlandırıyordu ama modülün (`n = p*q`) **entropisini ciddi şekilde azaltıyordu**.

Kök neden: **rastgelelik/arama uzayı optimizasyonu, kriptografik güvenlik marjını sessizce yiyip bitirdi.** Coppersmith'in kısmi bilgiyle asal çarpanlara ayırma tekniklerini bu yapısal kalıpla birleştiren araştırmacılar (Nemec ve ekibi), belirli anahtar boyutlarında (özellikle 2048-bit) pratik sürede (bulut hesaplama gücüyle günler/haftalar mertebesinde, anahtar boyutuna göre değişir) özel anahtarı tam çarpanlarına ayırabildiklerini gösterdi.

### Neden Önemli: Gerçek Dünya Etkisi

ROCA'nın etkisi çok genişti çünkü bu kütüphane akıllı kartlarda, TPM (Trusted Platform Module) çiplerinde, kimlik kartlarında (bazı ülkelerin e-kimlik sistemleri dahil) ve donanım güvenlik token'larında kullanılıyordu. Bu, "yazılım hatası düzeltilir, güncelleme yapılır" senaryosunun ötesinde bir sorundu: **donanıma gömülü anahtar üretim algoritması**, saha değişimi (anahtarların yeniden üretilmesi) gerektiriyordu, bu da milyonlarca fiziksel kartın/cihazın etkilenmesi anlamına geliyordu.

### Tespit ve Savunma

**Tespit**: ROCA açığı olan anahtarlar, modülün matematiksel yapısından **pasif olarak** (özel anahtara erişim gerekmeden, sadece genel anahtardan) tespit edilebilir — bu, zafiyetin en öğretici yanıdır. Modülün belirli bir kalıba uyup uymadığını kontrol eden fingerprint testleri (araştırmacıların yayınladığı açık kaynak tarayıcılar) ile bir ortamdaki tüm X.509 sertifikaları/genel anahtarlar taranarak etkilenen anahtarlar bulunabilir. Bu, savunmacılar için önemli bir derstir: **genel anahtarın kendisi, üretim algoritmasının kalitesi hakkında bilgi sızdırabilir.**

**Savunma**: Anahtar üretimini asla kendi yazdığınız veya doğrulanmamış özel bir algoritmayla yapmayın; FIPS 186-4/186-5 gibi standartlara uygun, iyi denetlenmiş kütüphaneler (OpenSSL, BoringSSL, libsodium) kullanın. Donanım güvenlik modülü (HSM) veya akıllı kart tedarikçisi seçerken, anahtar üretim algoritmasının bağımsız kriptografik denetimden geçmiş olmasını sözleşmesel şart koşun. Kurumsal ortamda periyodik olarak sertifika envanterinizi bilinen zayıf anahtar kalıplarına karşı taramak (ROCA benzeri gelecekteki zafiyetler için de) makul bir hijyen pratiğidir.

---

## 3. Nonce Reuse / ECDSA Nonce Sızıntısı (Sony PS3 Vakası)

### Tanım ve Kök Neden

ECDSA (Eliptik Eğri Dijital İmza Algoritması) imzalama işlemi, her imza için **tek kullanımlık, kriptografik olarak rastgele bir sayı** (nonce, genellikle `k` olarak adlandırılır) gerektirir. Sony'nin PlayStation 3 kod imzalama sisteminde 2010 civarında keşfedilen ve fail0verflow/geohot ekiplerince kamuya duyurulan zafiyette, Sony **her imza için aynı sabit `k` değerini** kullanmıştı — rastgele üretmesi gerekirken.

Kök neden matematiksel olarak nettir: ECDSA imza denklemi `s = k^-1 * (h + r*d) mod n` şeklindedir (`d` özel anahtar, `h` mesaj özeti, `r` ve `s` imza bileşenleri). Eğer aynı `k` iki farklı mesaj için kullanılırsa, iki imza denklemi arasında `k` bilinmeyeni **cebirsel olarak elenebilir** ve bu da özel anahtar `d`'yi doğrudan (basit bir lineer denklem çözümüyle) verir. Yani: **aynı nonce ile imzalanmış iki mesaj görürseniz, özel anahtarı doğrudan hesaplayabilirsiniz** — hiçbir kaba kuvvet veya faktörizasyon gerekmez, sadece modüler aritmetik.

Bu, "RSA/ECC matematiksel olarak güçlü" iddiasının **rastgelelik varsayımına bağımlı** olduğunu gösteren en çarpıcı örnektir. Primitifin kendisi kırılmadı; protokolün bir girdisi (nonce) determinize edildiğinde tüm güvenlik modeli çöktü.

### Genelleştirilmiş Risk: Kısmi Nonce Sızıntısı

Tam nonce tekrarı en bariz hata olsa da, daha ince varyantlar da vardır: nonce'un yalnızca birkaç biti sızdırılırsa (ör. zayıf RNG, yan kanal, biased nonce üretimi), Minerva/LadderLeak gibi kafile saldırıları (lattice-based, Hidden Number Problem çözümleriyle) yeterli sayıda imza toplandığında yine özel anahtarı geri çıkarabilir. Bu, "sadece tam tekrarı önlemek yeterli değil, nonce'un **istatistiksel olarak da** kusursuz rastgele olması gerekir" dersini verir.

### Tespit ve Savunma

**Tespit**: Bir sistemin ürettiği imzaları toplayıp `r` değerlerinin (ki `r`, `k`'nin bir fonksiyonudur) tekrarlanıp tekrarlanmadığını kontrol etmek basit ama etkili bir denetim adımıdır — aynı `r` iki farklı imzada görülüyorsa bu kırmızı alarmdır. Daha genel olarak, imza üretiminde kullanılan RNG'nin entropi kaynağının denetlenmesi (özellikle gömülü sistemlerde, sanal makinelerde ilk boot anında veya donanım RNG arızalarında düşük entropi riski yüksektir).

**Savunma**: RFC 6979, nonce'u mesaj ve özel anahtardan **deterministik ama kriptografik olarak güvenli** biçimde türeterek (HMAC tabanlı), harici bir rastgelelik kaynağına bağımlılığı ortadan kaldırır — bu, aynı girdi için aynı nonce üretse bile, güvenlik zafiyeti yaratmaz çünkü nonce mesaja bağlıdır (iki farklı mesaj asla aynı nonce'u üretmez, ama aynı mesaj-anahtar çifti tekrar imzalanırsa aynı sonucu verir, ki bu zararsızdır). Alternatif olarak Ed25519 gibi imza şemaları nonce türetimini şemanın kendi tasarımına gömerek bu sınıf hatayı yapısal olarak imkânsız kılar. Mühendislik ilkesi: **güvenlik-kritik rastgelelik üretimini asla "biz de basit bir implementasyon yazalım" mantığıyla ele almayın; standart, denetlenmiş RNG/nonce türetim yöntemlerini kullanın.**

---

## 4. Bit-flipping Saldırıları (CBC Modunda Kimlik Doğrulamasız Şifreleme)

### Tanım ve Kök Neden

CBC (Cipher Block Chaining) modunda şifreleme, her blok bir öncekinin şifreli çıktısıyla XOR'lanarak zincirlenir. Şifre çözme sırasında: `P_i = D(C_i) XOR C_{i-1}`. Kök neden şudur: **CBC modu gizliliği (confidentiality) sağlar ama bütünlüğü (integrity) sağlamaz.** Eğer bir sistem şifreli veriyi sadece şifreliyor ve ayrı bir MAC/imza ile doğrulamıyorsa (yani "encrypt-then-MAC" veya AEAD kullanmıyorsa), saldırgan şifreli metni **çözmeden** değiştirebilir ve bu değişiklik düz metinde öngörülebilir bir etkiye yol açar.

Spesifik olarak: bir önceki şifreli blokta (`C_{i-1}`) bit çevirirseniz, bu değişiklik o bloğun kendi düz metnini (`P_{i-1}`) rastgele bozar (yan etki) ama **bir sonraki bloğun düz metninde** (`P_i`) tam olarak aynı bit pozisyonlarında öngörülebilir bir değişiklik yaratır — çünkü XOR ilişkisi doğrusaldır: `P_i' = P_i XOR (delta uygulanan bit)`. Saldırgan, düz metnin o kısmının içeriğini biliyorsa veya tahmin edebiliyorsa (ör. bir çerezde `role=user` alanı), tam olarak istediği bitleri çevirerek `role=user`'ı `role=admin`'e dönüştürebilir — şifreleme anahtarını hiç bilmeden.

CTR modu da benzer şekilde savunmasızdır (keystream ile XOR olduğundan doğrudan bit çevirme daha da kolaydır), ama CBC'nin ek olarak bir önceki bloğu bozma "yan etkisi" vardır ki bu genelde ihmal edilir.

### Nasıl Çalıştığı ve Tespit

Saldırı akışı: (1) saldırgan hedef düz metnin yapısını bilir/tahmin eder (formatlı veriler — JSON, çerez, sabit uzunluklu alanlar — bu konuda idealdir), (2) ilgili bloğun bir önceki şifreli bloğunda hedeflenen bit pozisyonlarını XOR ile değiştirir, (3) değiştirilmiş şifreli metni sisteme gönderir, (4) sistem MAC/imza kontrolü yapmadığı için kabul eder ve bozulmuş düz metni işler.

**Tespit**: Uygulama loglarında, şifre çözme sonrası **format doğrulama hatalarının** anormal sıklıkta oluşması (çünkü bit-flipping çoğunlukla hedef dışı blokları da bozar, bu da parse hatalarına yol açar) bir gösterge olabilir. Ayrıca aynı kaynak IP'den kısa aralıklarla çok sayıda "geçersiz format" hatası, deneme-yanılma temelli bit-flipping taramasının imzasıdır.

**Savunma**: Kesin çözüm **kimlik doğrulamalı şifrelemedir (AEAD)**: AES-GCM, ChaCha20-Poly1305 gibi modlar hem şifreler hem de bütünlüğü doğrular; herhangi bir bit değişikliği doğrulama aşamasında reddedilir. Eğer AEAD kullanılamıyorsa, "encrypt-then-MAC" deseni (önce şifrele, sonra şifreli metin üzerinden ayrı bir HMAC hesapla, şifre çözmeden önce MAC'i doğrula) zorunlu olmalıdır — asla "MAC-then-encrypt" veya "encrypt-and-MAC" (aynı anda ama bağımsız) desenleri kullanılmamalıdır çünkü bunlar farklı oracle sınıflarına açık kapı bırakabilir. Kod incelemesinde aranacak anti-pattern: `AES.new(key, AES.MODE_CBC, iv)` çağrısının hemen ardından ayrı bir MAC doğrulama adımı **olmadan** doğrudan `decrypt()` çıktısının işlenmesi.

---

## 5. Length Extension Saldırısı (Merkle-Damgård Hash Fonksiyonlarında MAC Kötüye Kullanımı)

### Tanım ve Kök Neden

MD5, SHA-1 ve SHA-256 gibi hash fonksiyonları **Merkle-Damgård yapısı** kullanır: mesaj bloklara bölünür, her blok önceki bloğun iç durumuyla (internal state) işlenir ve son iç durum, hash çıktısı olarak döndürülür. Kök neden: **hash fonksiyonunun son iç durumu, hash çıktısının kendisiyle aynıdır** (ekstra bir "finalization" adımı olmadan). Bu, saldırgana şu imkânı verir: eğer bir mesajın hash'ini biliyorsanız (`H(mesaj)`), bu hash'i **iç durum olarak yeniden başlatıp**, mesaja görünmeden ek veri (`ek_veri`) ekleyerek `H(mesaj || padding || ek_veri)` hesaplayabilirsiniz — orijinal mesajın veya gizli anahtarın **içeriğini bilmeden**.

Bu saldırı özellikle `MAC = H(gizli_anahtar || mesaj)` şeklinde (yani anahtarı basitçe mesajın başına ekleyerek MAC üreten) naif kimlik doğrulama şemalarını hedef alır. Saldırgan geçerli bir `(mesaj, MAC)` çiftini görünce, gizli anahtarın uzunluğunu bilmese/tahmin etse bile, `mesaj || padding || ek_veri` için geçerli yeni bir MAC üretebilir — anahtarı hiç bilmeden. Bu, örneğin bir API imza şemasında `signature=MD5(secret+params)` deseni kullanıldığında, saldırganın parametrelere yetkisiz ek alanlar (`&admin=true` gibi) ekleyip hâlâ geçerli görünen bir imza üretmesine yol açar.

### Neden Bu Kadar Şaşırtıcı: Sezgiye Aykırılık

Bu saldırı öğretim açısından değerlidir çünkü "hash fonksiyonu tek yönlüdür, tersine çevrilemez" sezgisiyle çelişiyor gibi görünür — ama aslında tersine çevirme yapılmaz; **hash'in iç durumu ileriye doğru devam ettirilir**. Kavramsal hata, geliştiricilerin hash fonksiyonunu bir "kara kutu MAC" gibi ele alıp, `H(anahtar+mesaj)`'ın otomatik olarak güvenli bir MAC olduğunu varsaymasıdır — oysa MAC güvenliği için tasarlanmış özel bir yapı (HMAC) gereklidir.

### Tespit ve Savunma

**Tespit**: Bir API'de imza doğrulama mantığı incelenirken, imzanın nasıl hesaplandığına bakmak en doğrudan tespit yoludur: `hashlib.md5(secret + data).hexdigest()` veya `sha1(key . $data)` gibi bir kod deseni görüldüğünde bu **kesin bir zafiyettir**, sömürülüp sömürülmediğini test etmeye gerek kalmadan düzeltilmelidir. Ayrıca dışarıdan test ederken, bilinen bir `(mesaj, imza)` çifti alınıp, hash'in blok boyutuna (MD5/SHA-1/SHA-256 için 64 bayt) göre hesaplanan padding ile birlikte veri eklenip yeni imzanın sunucu tarafından kabul edilip edilmediği kontrol edilerek doğrulanabilir (bu, savunma amaçlı bir pentest/doğrulama adımıdır).

**Savunma**: Asla ham hash birleştirmesiyle (`H(key||message)`) MAC üretmeyin. **HMAC** (`HMAC(key, message) = H((key XOR opad) || H((key XOR ipad) || message))`) bu saldırıyı yapısal olarak imkânsız kılar çünkü iç durum, anahtarla iki kat sarmalanmıştır ve saldırgan tek bir hash çıktısından iç durumu yeniden başlatamaz. Alternatif olarak SHA-3 (Keccak) ailesi, sponge yapısı kullandığından length extension saldırısına doğası gereği bağışıktır — bu yüzden SHA-3 tabanlı MAC'ler ekstra HMAC sarmalaması olmadan da güvenli kabul edilir (yine de en yaygın pratik HMAC kullanmaktır, çünkü geniş kütüphane desteği ve denetim geçmişi vardır).

---

## Ortak Savunma Prensipleri: Beş Saldırının Kesişim Kümesi

Bu beş saldırı sınıfı yüzeyde farklı görünse de, savunma mühendisliği açısından ortak bir felsefeyi paylaşır:

1. **Oracle'ları yok edin, gizlemeyin.** Bleichenbacher/ROBOT'ta olduğu gibi, "hata mesajını aynı yap ama zamanlamayı gizleme" gibi yarım önlemler genellikle yetersiz kalır; kalıcı çözüm protokolü oracle üretmeyecek şekilde yeniden tasarlamaktır (TLS 1.3'ün PKCS#1 v1.5'i kaldırması gibi).
2. **Rastgeleliği asla kendiniz icat etmeyin.** ROCA (zayıf anahtar üretimi) ve nonce reuse (zayıf/sabit `k`) aynı kök nedenin iki yüzüdür: kriptografik rastgelelik, standartlaştırılmış ve denetlenmiş mekanizmalarla (CSPRNG, RFC 6979) üretilmelidir.
3. **Gizlilik ile bütünlük farklı şeylerdir, ikisi de ayrı ayrı sağlanmalı.** Bit-flipping, sadece şifrelemenin (CBC) bütünlük sağlamadığını unutmanın bedelidir. AEAD bu ayrımı ortadan kaldırıp tek adımda ikisini de garanti eder.
4. **Primitifi amacı dışında kullanmayın.** Length extension, bir hash fonksiyonunu (bütünlük/özet amaçlı) bir MAC (kimlik doğrulama amaçlı) yerine doğrudan kullanmanın cezasıdır. Her primitifin güvenlik varsayımlarını (hangi tehdit modelinde, hangi kullanım deseninde güvenli olduğunu) bilmeden kullanmak risklidir.
5. **Kod incelemesi kriptografik "el yapımı" desenleri aramalıdır.** Bu beş saldırının hepsi, birinin "standart kütüphane yerine kendi basit implementasyonumu yazayım" kararıyla başlamıştır. Savunmacı için en yüksek getirili aktivite, kod tabanında `MD5(`, `SHA1(secret`, elle yazılmış padding kontrolü, elle yazılmış RSA/ECDSA anahtar üretimi gibi desenleri aramak ve bunları denetlenmiş kütüphane çağrılarıyla (libsodium, OpenSSL yüksek seviye API'leri, `cryptography` gibi modern SDK'lar) değiştirmektir.

## Sonuç

Bu beş vaka, kriptografinin "matematiksel olarak güvenli primitif seçmek" ile bitmediğini, asıl zorluğun **primitifi protokole doğru entegre etmek** olduğunu gösterir. Bir savunma mühendisi için pratik çıkarım: yeni bir kriptografik özellik tasarlarken önce "bu tasarımda bir oracle var mı, rastgelelik nereden geliyor, bütünlük ayrı mı doğrulanıyor, primitif amacına uygun mu kullanılıyor" sorularını sormak, çoğu tarihsel CVE'nin tekrarını önler.
