# Diffie-Hellman ve Forward Secrecy

## Giriş: İki İnsan Nasıl Ortak Bir Sırra Ulaşır?

Modern şifreli iletişimin en temel problemi şudur: Birbirini hiç görmemiş, aralarındaki hattı da düşmanların dinlediği iki taraf, nasıl olur da yalnızca ikisinin bildiği ortak bir gizli anahtar (shared secret) üretebilir? Bütün trafik açıkça izlenirken, dinleyicinin (eavesdropper) ele geçiremeyeceği bir sır nasıl kurulur?

Bu problemin çözümü **Diffie-Hellman anahtar değişimi** (Diffie-Hellman key exchange, kısaca DH) ile 1976'da yayımlandı ve kriptografi tarihinin dönüm noktalarından biri oldu. DH, tarafların gizli anahtarı **hiçbir zaman hat üzerinden göndermeden**, onu her iki uçta bağımsız olarak "hesaplayarak" elde etmesini sağlar. Bu makalede DH'nin çalışma mantığını, neden güvenli olduğunu, üzerine inşa edilen **ephemeral** (geçici) varyantları (DHE/ECDHE) ve bunların getirdiği en kıymetli güvenlik özelliği olan **forward secrecy**'yi (ileriye dönük gizlilik) derinlemesine inceleyeceğiz.

## Diffie-Hellman'ın Kök Mantığı: Tek Yönlü Zorluk

DH'nin kalbinde **tek yönlü fonksiyon** (one-way function) fikri yatar: Bir yönde hesaplaması kolay, ters yönde ise pratikte imkânsız derecede zor olan matematiksel bir işlem. Klasik DH, sonlu bir grupta **ayrık logaritma probleminin** (discrete logarithm problem, DLP) zorluğuna dayanır.

Mekanizmayı adım adım kuralım. Taraflar önce herkese açık iki parametre üzerinde anlaşır:

- Büyük bir asal sayı `p` (modülüs)
- Bir üreteç (generator) `g` — genellikle küçük bir sayı, örneğin 2 ya da 5

Bu iki değer **gizli değildir**; dinleyici de bilir. Sonra:

1. Alice gizli bir sayı `a` seçer (kimseye söylemez) ve `A = g^a mod p` hesaplayıp `A`'yı karşıya gönderir.
2. Bob gizli bir sayı `b` seçer, `B = g^b mod p` hesaplayıp `B`'yi gönderir.
3. Alice, Bob'dan gelen `B`'yi alıp `s = B^a mod p` hesaplar.
4. Bob, Alice'ten gelen `A`'yı alıp `s = A^b mod p` hesaplar.

İşin matematiksel sihri şudur: Her iki tarafın ulaştığı değer aynıdır, çünkü:

```
B^a = (g^b)^a = g^(ab) = (g^a)^b = A^b   (hepsi mod p)
```

Yani ortak sır `s = g^(ab) mod p`. Dikkat edin: `g^(ab)` değeri hiçbir zaman hat üzerinden geçmedi. Dinleyici yalnızca `g`, `p`, `A = g^a` ve `B = g^b` değerlerini gördü.

### Neden Dinleyici Sırrı Bulamıyor?

Dinleyicinin ortak sırra ulaşabilmesi için `A = g^a`'dan `a`'yı ya da `B = g^b`'den `b`'yi geri çözmesi gerekir. İşte bu, ayrık logaritma problemidir: "`g`, `p` ve `g^a mod p` biliniyorken `a`'yı bul." Modülo aritmetiğinde üs alma tek yönde kolaydır; ama sonuçtan üssü geri bulmak, yeterince büyük `p` için (günümüzde en az 2048 bit, tercihen daha fazla) bilinen klasik algoritmalarla astronomik zaman alır. Bu asimetri — ileri kolay, geri imkânsız — güvenliğin temelidir.

Buradaki kritik ayrım, güvenliğin **sırrın gizlenmesinden değil, matematiksel zorluktan** gelmesidir. Trafiği kaydeden biri her şeyi görür ama işine yaramaz; çünkü elindeki veriden sırra giden yol hesaplanamaz.

## Eliptik Eğriler: ECDH ve Verimlilik

Klasik DH'nin (bazen "sonlu alan DH" ya da FFDH denir) bir bedeli vardır: Güvenlik için modülüsün çok büyük olması gerekir, bu da hesaplamayı ve gönderilen verinin boyutunu artırır. **ECDH** (Elliptic Curve Diffie-Hellman) aynı fikri, çarpımsal modülo grubu yerine bir **eliptik eğri** üzerindeki nokta grubuna taşır.

Mantık birebir aynıdır, yalnızca işlem değişir. `g^a` üs alma yerine, eğri üzerinde bir `G` başlangıç noktasının skaler ile çarpımını kullanırız: `a·G`. Ortak sır `a·b·G` noktası olur. Buradaki tek yönlü zorluk **eliptik eğri ayrık logaritma problemidir** (ECDLP): `G` ve `a·G` biliniyorken `a` skalerini bulmak.

ECDH'nin cazibesi güvenlik yoğunluğundadır: Eliptik eğrilerde bilinen saldırılar çarpımsal gruplara göre çok daha az verimli olduğundan, yaklaşık 256 bitlik bir eğri (örneğin Curve25519 ya da NIST P-256), 3072 bitlik klasik DH ile kabaca aynı güvenlik seviyesini sunar. Yani daha küçük anahtar, daha az bant genişliği, daha hızlı hesaplama, aynı güvenlik. Bu yüzden günümüzde el sıkışmalarda (handshake) ezici çoğunlukla ECDH tercih edilir.

## Asıl Mesele: Kimlik Doğrulama Eksikliği ve MITM

Şimdi DH'nin en sık yanlış anlaşılan noktasına gelelim. Ham DH, **kiminle** sır kurduğunuzu **doğrulamaz**. Matematik yalnızca "karşımdaki her kimse onunla ortak bir sır kurdum" der; ama o karşıdakinin gerçekten Bob olduğunu garanti etmez.

Bu boşluk, klasik **ortadaki adam** (man-in-the-middle, MITM) saldırısına kapı açar. Araya giren Mallory, Alice'e karşı kendini Bob gibi, Bob'a karşı kendini Alice gibi gösterir:

- Alice `A` gönderir; Mallory yakalar, yerine kendi `M1`'ini Bob'a iletir.
- Bob `B` gönderir; Mallory yakalar, yerine kendi `M2`'sini Alice'e iletir.
- Sonuçta Alice-Mallory arasında bir ortak sır, Mallory-Bob arasında ayrı bir ortak sır kurulur.

Mallory ortadadır: Alice'ten geleni deşifre eder, okur, yeniden şifreleyip Bob'a yollar. İki taraf da güvenli konuştuğunu sanır. **İstismar mantığı** budur ve tamamen kimlik doğrulama eksikliğinden kaynaklanır.

**Savunma:** DH değişimi mutlaka bir **kimlik doğrulama** (authentication) katmanıyla birleştirilmelidir. Pratikte tarafların gönderdiği DH açık değerleri (`A`, `B`), kimliği bir sertifika ile doğrulanmış bir uzun ömürlü anahtar tarafından **imzalanır** (signed). TLS'de sunucu, kendi ephemeral DH açık değerini sertifikasındaki özel anahtarla imzalar; istemci sertifika zincirini bir CA'ya kadar doğrulayarak "bu DH değerini gerçekten bu sunucu üretti" güvencesini alır. Mallory araya girse bile geçerli bir imza üretemez, çünkü sunucunun özel anahtarına sahip değildir. Buna genellikle **authenticated key exchange** denir. Ders şudur: DH gizliliği verir, imza/sertifika ise kimliği; ikisi bir arada olmadan güvenlik eksiktir.

## Ephemeral Kavramı ve Forward Secrecy'nin Doğuşu

Şimdi makalenin kalbine geliyoruz. DH iki temel biçimde kullanılabilir:

**Statik (static) DH:** Tarafların DH gizli değerleri uzun ömürlüdür; örneğin bir sertifikaya gömülüdür ve her oturumda aynı `a`, aynı `b` kullanılır. Ortak sır her seferinde aynı çıkar ya da uzun süreli bir anahtardan türetilir.

**Ephemeral DH (DHE / ECDHE):** "Ephemeral" kelimesi "geçici, kısa ömürlü" demektir. Burada taraflar **her oturum için taze, rastgele** bir gizli değer (`a`, `b`) üretir, el sıkışma biter bitmez bu değerleri bellekten siler. "E" harfi (DH**E**, ECDH**E**) tam olarak bunu, ephemeral'i işaret eder.

Bu ayrımın neden hayati olduğunu anlamak için **forward secrecy** kavramını tanımlayalım.

### Forward Secrecy Nedir ve Neden Önemlidir?

**Forward secrecy** (ileriye dönük gizlilik; "perfect forward secrecy" / PFS de denir), şu güvenceyi verir: Sunucunun uzun ömürlü özel anahtarı **gelecekte** ele geçirilse bile, **geçmişte** kaydedilmiş oturumlar deşifre edilemez.

Bunun neden büyük bir mesele olduğunu somutlaştıralım. Forward secrecy **olmayan** bir senaryo düşünün — örneğin eski, statik RSA anahtar taşımalı (RSA key transport) el sıkışması. Orada istemci, oturum anahtarını sunucunun **açık RSA anahtarıyla** şifreleyip gönderir. Bir saldırgan bugün tüm trafiği pasifçe kaydeder (bunu depolar). Aradan yıllar geçer; bir gün sunucunun özel anahtarı sızar (bir ihlal, bir mahkeme kararı, bir çalışanın ihmali, ya da ileride yeterince güçlü bir bilgisayar). O andan itibaren saldırgan, kaydettiği **tüm eski trafiği** geriye dönük deşifre edebilir; çünkü her oturumun anahtarı o tek özel anahtarla korunuyordu. Buna genellikle **"store now, decrypt later"** (şimdi kaydet, sonra çöz) saldırısı denir.

İşte ephemeral DH bu felaketi engeller. ECDHE/DHE'de:

- Oturum anahtarı, o oturuma özgü taze `a` ve `b`'den türeyen `g^(ab)`'den doğar.
- Sunucunun uzun ömürlü özel anahtarı yalnızca **kimlik doğrulamak** (DH değerini imzalamak) için kullanılır, oturum anahtarını **korumak** için değil.
- El sıkışma bitince `a` ve `b` silinir; artık dünyada hiçbir yerde durmazlar.

Sonuç: Saldırgan yıllar sonra sunucunun özel anahtarını çalsa bile, geçmiş oturumun anahtarını hesaplayamaz. Çünkü o anahtar `g^(ab)`'den geliyordu ve `a` ile `b` çoktan yok edildi; imza anahtarı ise sırrı hesaplamaya yaramaz, yalnızca kimliği kanıtlar. Kaydedilmiş trafik ebediyen okunamaz kalır. Bir oturumun anahtarı sızsa bile bu, yalnızca **o tek oturumu** açık eder; diğer oturumlar bağımsız `a`, `b` kullandığından etkilenmez. Yani hasar tek oturuma **kompartımanlanır** (compartmentalization).

"Perfect" sıfatı burada, her oturumun kriptografik olarak birbirinden **bağımsız** olmasına atıfta bulunur — bir oturumun ele geçmesi ne geçmişe ne geleceğe yayılır.

## Somut Örnek: TLS El Sıkışmasında ECDHE

Kavramı gerçek dünyaya oturtalım. Bir HTTPS bağlantısı kurulurken tipik bir ECDHE akışı şöyle işler (kavramsal olarak; TLS 1.2 ve TLS 1.3'te ayrıntılar farklılaşır):

1. İstemci, desteklediği şifre paketlerini (cipher suites) ve kendi ephemeral ECDH açık değerini (ya da TLS 1.2'de önce yalnızca niyetini) bildirir.
2. Sunucu, sertifikasını ve **kendi taze ephemeral ECDH açık değerini** gönderir. Kritik nokta: Bu ephemeral değeri, sertifikasındaki uzun ömürlü özel anahtarla **imzalar**.
3. İstemci sertifika zincirini doğrular (kimlik onayı) ve imzayı kontrol eder (bu ECDH değerinin gerçekten bu sunucudan geldiğini teyit eder).
4. Her iki taraf da karşıdakinin ECDH açık değerini kendi ephemeral gizliyle birleştirerek ortak sırra ulaşır.
5. Ortak sır doğrudan anahtar olarak kullanılmaz; bir **anahtar türetme fonksiyonundan** (key derivation function, örneğin HKDF) geçirilerek asıl simetrik oturum anahtarları elde edilir.
6. El sıkışma biter, ephemeral gizli değerler silinir. Bundan sonra veri, türetilen simetrik anahtarlarla (örneğin AES-GCM ile) şifrelenir.

Şifre paketi adında bunu okuyabilirsiniz. `TLS_ECDHE_RSA_WITH_AES_128_GCM_...` gibi bir isimde: `ECDHE` anahtar değişiminin ephemeral eliptik eğri DH olduğunu, `RSA` ise sunucunun kimliğini kanıtlamak için imzada kullandığı anahtar türünü söyler. Yani ECDHE **gizliliği**, RSA (ya da ECDSA) **kimliği** sağlar — tam da yukarıda anlattığımız iş bölümü.

TLS 1.3'te bu tasarım felsefesi zorunlu hâle getirilmiştir: Forward secrecy sağlamayan statik RSA anahtar taşıması ve statik DH tamamen kaldırılmış, yalnızca ephemeral (ECDHE/DHE) anahtar değişimine izin verilmiştir. Bu, protokolün "forward secrecy artık pazarlık konusu değil, varsayılan" dediği anlamına gelir.

## Saldırı Yüzeyi: Ephemeral'in Yanlış Uygulanması Nasıl İstismar Edilir?

Forward secrecy sağlam bir kavramdır; ama yanlış uygulama güvenceyi sessizce çökertir. Saldırgan gözüyle zayıf noktalara bakalım — çünkü savunmayı ancak istismarı anlayınca doğru kurabilirsiniz.

**1. Sahte ephemeral — aslında yeniden kullanılan gizli.** Bir sunucu, performans kaygısıyla "ephemeral" değeri birçok oturumda **yeniden kullanırsa** (örneğin `a`'yı saatlerce sabit tutarsa), aslında statik DH yapıyor demektir. Ephemeral etiketi yanıltıcıdır. Saldırgan açısından: O tek `a` sızarsa, onunla yapılmış **tüm** oturumlar açılır — forward secrecy fiilen yoktur. **Savunma:** Ephemeral değer gerçekten oturum başına (ya da çok kısa ömürle) üretilmeli ve kullanımdan sonra bellekten güvenilir biçimde silinmelidir.

**2. Zayıf ya da paylaşılan DH parametreleri.** Klasik DHE'de küçük ya da yaygın olarak paylaşılan asal parametreler ciddi risktir. Ayrık logaritma kırma çalışmasının pahalı kısmı belirli bir `p` asalı için bir kez yapılır; sonrasında o `p`'yi kullanan tüm oturumlara ucuz saldırı uygulanabilir. Birçok sunucu aynı, gömülü, zayıf (örneğin 1024 bit ya da altı) parametreyi paylaştığında saldırgan tek bir ön hesaplamayla geniş bir hedef kümesini vurabilir. Ayrıca protokolü zayıf, "ihracat sınıfı" (export-grade) küçük parametrelere **düşürmeye** (downgrade) zorlayan saldırı sınıfları geçmişte gösterilmiştir. **Savunma:** Yeterince büyük (en az 2048 bit, tercihen daha büyük) ve mümkünse sunucuya özgü ya da iyi bilinen sağlam gruplar kullanın; küçük/export parametrelerini tamamen devre dışı bırakın; downgrade'e karşı protokol düzeyinde koruma sağlayan güncel TLS sürümlerini zorunlu kılın.

**3. Zayıf rastgelelik (RNG).** Ephemeral gizli `a` ve `b` **öngörülemez** olmalıdır. Rastgele sayı üreteci (random number generator, RNG) zayıfsa, tahmin edilebilirse ya da tohumu (seed) sızmışsa, saldırgan `a`'yı yeniden üretebilir ve forward secrecy'nin tüm faydası buharlaşır. Gömülü cihazlarda önyükleme anında yetersiz entropi bu riskin klasik kaynağıdır. **Savunma:** Kriptografik olarak güvenli bir RNG (CSPRNG) kullanın; entropinin, özellikle cihaz açılışında, gerçekten yeterli olduğundan emin olun.

**4. Eliptik eğri girdi doğrulaması eksikliği.** ECDHE'de karşıdan gelen açık noktanın gerçekten geçerli, doğru eğri üzerinde bir nokta olup olmadığı kontrol edilmelidir. Aksi hâlde saldırgan, dikkatle seçilmiş "eğri dışı" ya da küçük altgrup noktaları göndererek gizli skaler hakkında bilgi sızdıran saldırılar (invalid-curve / small-subgroup türü) deneyebilir. **Savunma:** Gelen noktaları eğri üzerinde ve doğru altgrupta olduklarını doğrulamadan işleme almayın; bu doğrulamayı yerleşik olarak yapan modern, denetlenmiş kütüphaneler kullanın.

**5. Silinmeyen anahtar malzemesi.** Forward secrecy'nin tüm vaadi, ephemeral gizlinin **gerçekten yok edilmesine** dayanır. Gizli, oturum bittikten sonra bellekte, log'da, çekirdek dökümünde (core dump) ya da takas alanında (swap) kalırsa, bir bellek okuma zafiyeti (Heartbleed benzeri sınıf saldırılar bunun ünlü örneğidir) onu çekip çıkarabilir. **Savunma:** Anahtar malzemesini kullanım biter bitmez güvenilir biçimde silin, hassas bellekleri swap dışında tutmaya çalışın ve bellek sızdıran zafiyetlere karşı bağımlılıklarınızı güncel tutun.

## Yaygın Hatalar

Uygulamada tekrar tekrar görülen yanlışları toplayalım:

- **DH'yi kimlik doğrulama olmadan kullanmak.** En temel hata. Ham DH gizlilik verir ama MITM'e açıktır; imza/sertifika şart.
- **"Ephemeral" etiketine güvenip yeniden kullanım yapmak.** Gizli değer oturumlar arası paylaşılıyorsa forward secrecy yalnızca kâğıt üzerindedir.
- **Küçük ya da paylaşılan klasik DH parametreleri.** 1024 bit ve altı artık güvenli kabul edilmemelidir; ortak gömülü parametreler toplu saldırıya davetiyedir.
- **Statik anahtar taşımalı (RSA key transport) el sıkışmalarını hâlâ desteklemek.** Bu, "store now, decrypt later" saldırısına kapıyı açık bırakır. Forward secrecy sağlayan paketleri önceliklendirip statik olanları devre dışı bırakın.
- **Downgrade'e izin vermek.** Saldırganın tarafları zayıf parametrelere/sürümlere düşürmesine engel olacak korumaları kapatmak.
- **Zayıf entropi.** Özellikle gömülü sistemlerde öngörülebilir ephemeral üretmek.
- **ECDH nokta doğrulamasını atlamak** ya da güvenilmeyen, elde yazılmış kripto kullanmak.
- **Forward secrecy'yi "her şeyi çözer" sanmak.** FS, uzun ömürlü anahtar sızsa geçmişi korur; ama **aktif** MITM'i, uç nokta ele geçirilmesini ya da oturum devam ederken bellekten anahtar çalınmasını engellemez. Kapsamı doğru anlaşılmalıdır.

## En İyi Pratikler

Kavramları eyleme dökelim:

- **Yalnızca ephemeral anahtar değişimini zorunlu kılın.** ECDHE'yi birincil, DHE'yi (yeterince büyük parametrelerle) yedek olarak sunun; statik DH ve statik RSA anahtar taşımasını kapatın. Mümkünse forward secrecy'yi varsayılan yapan modern TLS sürümlerini tercih edin.
- **Güçlü, doğrulanmış eğriler ve parametreler seçin.** ECDHE için yaygın kabul görmüş, denetlenmiş eğrileri (örneğin Curve25519 ailesi ya da sağlam NIST eğrileri) kullanın. Klasik DHE kullanacaksanız en az 2048 bitlik, iyi bilinen ya da sunucuya özgü güçlü gruplar seçin.
- **Ephemeral'i gerçekten ephemeral tutun.** Gizli değeri oturum başına üretin, kısa ömürlü tutun ve kullanımdan sonra bellekten güvenilir biçimde silin. Performans için yeniden kullanacaksanız ömrü çok kısa tutun ve riski bilinçli değerlendirin.
- **Sağlam rastgelelik sağlayın.** CSPRNG kullanın, entropiyi özellikle açılışta güvence altına alın; öngörülebilir tohumdan kaçının.
- **Girdileri doğrulayın.** Gelen DH/ECDH açık değerlerini işleme almadan önce geçerlilik kontrolünden geçirin; nokta doğrulaması, altgrup kontrolü.
- **Kimlik doğrulamayı asla ihmal etmeyin.** DH'yi her zaman güçlü bir imza ve düzgün doğrulanan bir sertifika zinciriyle birleştirin; sertifika doğrulamasını gevşetmeyin.
- **Olgun kütüphaneler kullanın, kendi kriptonuzu yazmayın.** İyi denetlenmiş kütüphaneler nokta doğrulaması, sabit zamanlı işlemler ve bellek temizliği gibi tuzakları sizin yerinize halleder.
- **Kripto çevikliği (crypto agility) planlayın.** Post-kuantum tehdidi (yeterince güçlü bir kuantum bilgisayarın ayrık logaritmayı çözebileceği ihtimali) "store now, decrypt later" saldırısını bugünden ciddi kılar. Kaydedilen trafiğin gelecekte açılma riskine karşı, algoritmaları değiştirebilir ve gerektiğinde post-kuantum ya da hibrit anahtar değişimine geçebilir bir mimari kurun.

## Kapanış

Diffie-Hellman'ın dehası, sırrı hiç göndermeden ortak sır kurabilmesinde; forward secrecy'nin kıymeti ise bu sırrı **geçmişe dönük** koruma altına almasındadır. ECDHE ile her oturum kendi taze, tek kullanımlık gizlisini alır ve iş bitince onu yok eder; böylece bir gün sunucunun uzun ömürlü anahtarı ele geçse dahi, kaydedilmiş eski konuşmalar açılamaz kalır. Ama unutmayın: Bu güvence yalnızca ephemeral gerçekten geçiciyse, parametreler güçlüyse, rastgelelik sağlamsa, girdiler doğrulanıyorsa ve DH bir kimlik doğrulama katmanıyla birleştirilmişse geçerlidir. Kavram sağlamdır; güvenlik, ayrıntılardaki disiplinden doğar.
