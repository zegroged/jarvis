# Eliptik Eğri Güvenlik Tuzakları

Eliptik Eğri Kriptografisi (ECC), aynı güvenlik seviyesini RSA'ya göre çok daha küçük anahtarlarla sağladığı için modern sistemlerin belkemiği hâline geldi: TLS, SSH, imzalar (ECDSA/EdDSA), anahtar değişimi (ECDH/ECDHE) ve blok zinciri cüzdanları hep ECC'ye dayanır. Matematiksel temeli (Elliptic Curve Discrete Logarithm Problem, ECDLP) doğru parametrelerle son derece sağlamdır. Ancak ECC'nin gerçek dünyadaki zafiyetleri neredeyse hiçbir zaman "matematiği kırma" değildir; hemen tümü **implementasyon hatalarından** ve **parametre/nokta doğrulama eksikliklerinden** kaynaklanır. Bu makale, ECC'ye özgü tuzakları — eğri seçimi, invalid curve/twist saldırıları, small subgroup saldırıları ve side-channel'a açık implementasyonları — mekanizma seviyesinde anlatır ve savunma/tespit kurmaya odaklanır.

## Kısa Ön Bilgi: Eliptik Eğri Grubu

Kriptografide kullanılan eğriler sonlu bir cisim (finite field) üzerinde tanımlanır, tipik olarak asal cisim `F_p` üzerinde Weierstrass formunda:

```
y² = x³ + a·x + b   (mod p)
```

Bu denklemi sağlayan `(x, y)` noktaları ve "sonsuzdaki nokta" (point at infinity, `O`) bir **grup** oluşturur. Nokta toplama (point addition) ve skaler çarpma (scalar multiplication, `k·P`) tanımlıdır. Güvenlik şu zorluğa dayanır: `P` ve `Q = k·P` verildiğinde `k`'yı bulmak (ECDLP) pratikte imkânsızdır.

Kritik iki kavram:

- **Grup mertebesi (order) `n`**: Baz noktası `G`'nin ürettiği alt grubun eleman sayısı. Güvenli eğrilerde `n` büyük bir asaldır (ya da küçük bir kofaktörle çarpılmış büyük asaldır).
- **Kofaktör (cofactor) `h`**: Eğrinin toplam nokta sayısı `#E = h · n` şeklindedir. `h` küçük bir tam sayıdır (P-256 için 1, Curve25519 için 8). Kofaktörün 1'den büyük olması, "küçük mertebeli alt gruplar" (small subgroups) barındırdığı anlamına gelir ve bu, small subgroup saldırılarının kapısını aralar.

Bu tuzakların çoğunun kökü tek bir cümlede özetlenebilir: **Sistem, karşı taraftan gelen bir noktanın gerçekten doğru eğri üzerinde ve doğru alt grupta olup olmadığını doğrulamaz.**

## Eğri Seçimi Tuzakları

### Tanım ve Kök Neden

Her eliptik eğri güvenli değildir. Belirli matematiksel özellikler, ECDLP'yi genel durumdan çok daha kolay çözülebilir hâle getirir. Zayıf bir eğri seçmek, ne kadar mükemmel kod yazarsanız yazın sistemi baştan çürütür.

Bilinen zayıf eğri sınıfları:

- **Anomalous eğriler**: Eğrinin nokta sayısı cismin karakteristiğine eşit olduğunda (`#E = p`), ECDLP polinom zamanda çözülebilir (Smart / SSSA saldırısı). Bu tür eğriler "additive transfer" ile kırılır.
- **Supersingular ve düşük embedding degree eğriler**: MOV / Frey-Rück saldırısı, ECDLP'yi daha zayıf bir sonlu cisim üzerindeki klasik ayrık logaritma problemine indirger. "Embedding degree" (gömme derecesi) küçükse problem çözülebilir hâle gelir.
- **Küçük veya çarpanlarına kolay ayrılan mertebe**: Eğer `n` büyük bir asal değilse, Pohlig-Hellman yöntemiyle problem küçük parçalara bölünüp çözülür.
- **Zayıf twist**: Eğrinin "quadratic twist"i (bkz. aşağıda) küçük çarpanlara ayrılan bir mertebeye sahipse, twist güvenliği (twist security) yoktur ve twist saldırıları kolaylaşır.

Ayrı bir endişe **eğrinin nasıl üretildiği**dir. Bazı standart eğrilerin sabitleri (seed'leri) "nereden geldiği açıklanmayan" (unexplained) sayılardır. Bu, teorik bir arka kapı (backdoor) endişesi doğurur. Buna karşı **"nothing-up-my-sleeve"** ilkesiyle üretilen eğriler (sabitleri π gibi evrensel sabitlerden türetilenler) tercih edilir.

### Örnek

Bir geliştirici, bir kütüphanenin "custom curve" desteğini kullanarak kendi eğri parametrelerini girer ya da bir protokolde karşı tarafın eğri parametrelerini önerebilmesine izin verir. Saldırgan, kırılabilir (örneğin anomalous) bir eğri önerir; el sıkışma bu eğri üzerinden yapılırsa saldırgan özel anahtarı hesaplayabilir. Bu yüzden ciddi protokoller (örneğin TLS'in modern sürümleri) eğri parametrelerini pazarlığa açmaz; yalnızca **adlandırılmış, denetlenmiş eğrileri** (named curves) kabul eder.

### Tespit ve Savunma

- **Yalnızca yerleşik, iyi incelenmiş eğriler kullanın**: NIST P-256/P-384, Curve25519/Ed25519, Curve448, veya brainpool eğrileri. Kendi eğrinizi üretmeyin.
- **Named curve zorunlu kılın**: Protokolde "explicit curve parameters" desteğini kapatın. X.509 sertifikalarında explicit EC parametrelerini reddedin; yalnızca named curve OID'lerini kabul edin.
- **Twist güvenliği olan eğrileri tercih edin**: Curve25519 gibi modern eğriler hem eğrinin kendisi hem de twist'i için güvenlik hedefler; bu, tek koordinatlı (x-only) implementasyonları büyük ölçüde korur.
- **Tespit**: Konfigürasyon ve sertifika taramalarında, beklenmeyen/özel eğri parametrelerini işaretleyin. Kabul edilen eğri listesini (allow-list) merkezî olarak sabitleyin.

## Invalid Curve (Geçersiz Eğri) Saldırıları

### Tanım

Bu, ECC'ye en özgü ve en klasik implementasyon tuzağıdır. Çoğu ECC işleminin merkezinde skaler çarpma vardır: sistem kendi gizli skaleri `d` ile karşı taraftan gelen `Q` noktasını çarpar (`d·Q`). Kritik nokta şudur: **Weierstrass eğrilerinin standart nokta toplama formülleri, denklemdeki `b` katsayısını hiç kullanmaz.** Toplama ve ikiye katlama (doubling) formülleri yalnızca `a`, `p` ve koordinatları içerir.

Bunun sonucu ölümcüldür: Saldırgan, `y² = x³ + a·x + b'` biçiminde, **aynı `a` ve `p`'ye ama farklı bir `b'`'ye** sahip, dolayısıyla **zayıf bir eğri** üzerinde yer alan bir nokta gönderirse, kurbanın kodu bu noktanın "yanlış eğride" olduğunu fark etmez. Formüller sorunsuz çalışır ama artık işlemler saldırganın seçtiği zayıf eğri üzerinde yürür.

### Kök Neden / Çalışma Mantığı

Saldırgan, mertebesi küçük çarpanlara ayrılan bir eğri seçer ve bu eğri üzerinde **küçük mertebeli** (örneğin mertebesi `r` = küçük bir asal) bir `Q` noktası bulur. Kurbana bu `Q`'yu gönderir. Kurban `d·Q` hesaplar. Sonucun `Q`'nun küçük alt grubu içinde kalması nedeniyle:

- Sonuç yalnızca `r` farklı değer alabilir.
- Saldırgan sonucu (ya da sonuçtan türeyen bir çıktıyı, örneğin bir MAC'i) gözlemleyerek `d mod r`'yi öğrenir.

Bunu farklı küçük asal mertebeler için tekrarlayıp, **Çin Kalan Teoremi (CRT)** ile `d`'nin tamamını parça parça birleştirir. Yeterli sayıda küçük modül biriktiğinde tüm özel anahtar `d` ele geçirilir. Bu, statik (uzun ömürlü) ECDH anahtarları için özellikle yıkıcıdır, çünkü saldırgan aynı `d`'ye karşı defalarca sorgu yapabilir.

### Örnek Senaryo

Statik ECDH kullanan bir sunucu düşünün: sunucunun sabit özel anahtarı `d` vardır. Protokol, istemciden gelen public key noktasını alıp `d` ile çarparak paylaşılan sırrı üretir ve bu sırdan türetilen bir oturum anahtarıyla bir doğrulama mesajı gönderir. Saldırgan, gerçek public key yerine, düşük mertebeli bir invalid-curve noktası gönderir. Sunucunun ürettiği doğrulama mesajından `d mod r` sızar. Yüzlerce farklı `r` için tekrarlandığında `d` çözülür. Tarihsel olarak bu sınıf zafiyet, nokta doğrulaması yapmayan birçok TLS/kripto kütüphanesinde bulunmuştur.

### Tespit ve Savunma

- **Public key doğrulaması (point validation) ZORUNLUDUR.** Karşı taraftan gelen her nokta için, kullanmadan önce şunları doğrulayın:
  1. Nokta "sonsuzdaki nokta" değil.
  2. `x` ve `y` koordinatları `[0, p-1]` aralığında (cisim içinde).
  3. Nokta **beklenen eğri denklemini sağlıyor**: `y² ≡ x³ + a·x + b (mod p)`. Bu, `b`'yi işin içine soktuğu için invalid-curve noktalarını yakalar.
  4. Nokta doğru alt grupta: kofaktör `h > 1` ise `n·Q = O` kontrolü (aşağıda small subgroup bölümüne bakın).
- **Compressed point kullanırken dikkat**: Sıkıştırılmış noktanın açılması (decompression) sırasında `y`, eğri denkleminden türetildiği için otomatik olarak eğri üstünde olur; yine de cisim aralığı ve alt grup kontrolleri gereklidir.
- **Ephemeral anahtar tercih edin**: Statik ECDH yerine ECDHE (her oturumda yeni anahtar) kullanmak, saldırganın aynı `d`'ye tekrar tekrar sorgu yapmasını engelleyerek bu saldırıyı pratikte etkisizleştirir.
- **Twist-güvenli, tek koordinatlı eğriler**: Curve25519'un X25519 fonksiyonu yalnızca `x` koordinatıyla çalışır ve tasarımı gereği hem invalid-curve hem twist noktalarına dayanıklıdır — bu yüzden modern sistemlerde tercih edilir.
- **Tespit**: Trafik/telemetri analizinde, aynı statik uç noktaya çok sayıda **düşük mertebeli / geçersiz noktalı** el sıkışma denemesi güçlü bir gösterge sayılır. Başarısız point-validation olaylarını loglayın ve eşiklendirin.

## Twist (Bükülme) Saldırıları

### Tanım ve İlişki

Twist saldırısı, invalid curve saldırısının bir akrabasıdır ve özellikle **x-only (tek koordinatlı) Montgomery ladder** implementasyonlarında ortaya çıkar. Bir eğrinin **quadratic twist**i, aynı `x` koordinat uzayını paylaşan ama farklı bir eğri olan eşlik eğrisidir. x-only işlemlerde `y` hiç taşınmadığı için, verilen bir `x` değeri ya orijinal eğriye ya da onun twist'ine ait olabilir; kod bunu ayırt etmez.

### Çalışma Mantığı ve Savunma

Saldırgan, twist eğrisi üzerinde küçük mertebeli bir noktaya karşılık gelen bir `x` gönderir. Eğer twist'in mertebesi küçük çarpanlara ayrılabiliyorsa, tıpkı invalid-curve saldırısında olduğu gibi gizli skalerin kalanları sızdırılabilir. Savunma iki katmanlıdır:

- **Twist-secure eğri seçmek**: Curve25519 ve Curve448 bilinçli olarak seçilmiştir; hem eğrinin hem twist'inin mertebesi büyük asal çarpan içerir. Böylece twist üzerinde küçük mertebeli faydalı nokta bulunamaz.
- **Kofaktörü temizlemek**: X25519 spesifikasyonundaki skaler "clamping" (belirli bitlerin sıfırlanıp sabitlenmesi) ve kofaktör çarpanı, küçük alt grup katkılarını nötrler.

Bu yüzden "x-only hız optimizasyonu yapıyorum ama rastgele bir eğri kullanıyorum" tehlikeli bir kombinasyondur; x-only kullanacaksanız twist güvenliği kanıtlanmış bir eğri kullanın.

## Small Subgroup (Küçük Alt Grup) Saldırıları

### Tanım

Kofaktör `h > 1` olan eğrilerde (örn. Curve25519, h=8), eğri **küçük mertebeli alt gruplar** içerir. Small subgroup saldırısı, saldırganın bu küçük alt gruplardan birine ait bir nokta göndererek gizli skalerin küçük bir modül altındaki kalanını sızdırmasına dayanır. Invalid-curve saldırısından farkı: burada nokta **doğru eğri üzerindedir** ama **yanlış (küçük) alt gruptadır**.

### Çalışma Mantığı

`P` mertebesi küçük `t` olan bir nokta ise, `d·P` yalnızca `t` farklı değer alabilir (`d·P = (d mod t)·P`). Kofaktör `h` küçük olduğu için sızan bilgi tek seferde küçüktür, ama:

- Statik anahtarlı sistemlerde tekrar sorguyla `d mod h` öğrenilebilir.
- Bazı protokollerde bu, oturum anahtarını zayıflatan ya da anahtar-doğrulama özelliklerini bozan "contributory behavior" ihlallerine yol açar.
- En kritik etki, **anahtar mutabakatı bütünlüğü** üzerindedir: küçük alt grup noktaları, iki tarafın farklı sanıp aynı sırrı üretmesine ya da öngörülebilir sırlara zorlanmasına neden olabilir.

### Örnek

İki taraf ECDH yapar. Kötü niyetli bir taraf, karşı tarafa mertebesi 8'e bölünen küçük bir alt gruptan nokta gönderir. Ortak sır, saldırganın küçük bir küme içinden tahmin edebileceği bir değere sıkışır. Kofaktör temizliği yapılmazsa, ortaya çıkan sır "düşük entropili" olur.

### Tespit ve Savunma

- **Alt grup kontrolü**: `h > 1` olan eğrilerde, gelen `Q` için `n·Q = O` (O = sonsuzdaki nokta) doğrulaması yapın. `n·Q ≠ O` ise nokta küçük bir alt grup bileşeni taşıyor demektir; reddedin.
- **Kofaktör çarpımı (cofactor multiplication)**: İşleme başlamadan önce noktayı `h` ile çarpın (`h·Q`). Bu, küçük alt grup bileşenini sonsuzdaki noktaya götürerek etkisiz kılar. X25519/X448 bu yaklaşımı tasarımına gömer (clamping + cofactor).
- **Prime-order eğri kullanmak**: NIST P-256 gibi kofaktörü 1 olan eğrilerde küçük alt grup yoktur; bu saldırı sınıfı tanım gereği geçersizdir (ancak invalid-curve ve side-channel hâlâ geçerlidir).
- **Ed25519/X25519'da dikkat**: EdDSA imza doğrulamasında "cofactored vs cofactorless" doğrulama farkları ve küçük-mertebeli noktalar, imza esnekliği (malleability) ve batch-doğrulama tutarsızlıklarına yol açabilir. Konsensüs gerektiren sistemlerde (blok zinciri) doğrulama kurallarını netleştirin.

## Side-Channel'a Açık Implementasyonlar

Matematik doğru, nokta doğrulaması tam olsa bile, **gizli skalerin nasıl işlendiği** anahtarı sızdırabilir. Side-channel saldırıları, hesaplamanın çıktısını değil, **fiziksel/gözlemlenebilir yan etkilerini** (süre, güç tüketimi, cache davranışı, elektromanyetik yayılım, hatalar) hedefler.

### Timing ve Cache Saldırıları

**Kök neden**: Skaler çarpma `k·P` naif olarak "double-and-add" ile yazılır: her bit için ikiye katlama yap, bit 1 ise topla. Bu, **çalışma süresinin ve bellek erişim deseninin gizli bit değerlerine bağlı** olması demektir. Saldırgan süreyi ya da cache erişim izlerini (Flush+Reload, Prime+Probe) ölçerek anahtar bitlerini geri kazanır.

**Savunma — constant-time (sabit-zamanlı) programlama**:

- **Montgomery ladder** kullanın: her bit için aynı işlem dizisini yürütür; dallanma gizli bite bağlı değildir.
- **Gizli veriye bağlı dallanma (branch) ve bellek indeksleme yapmayın.** Tablo aramalarında (windowed methods) constant-time seçim / masking kullanın; gizli indeksle doğrudan bellek erişimi yapmayın.
- Karşılaştırmaları constant-time yapın (`memcmp` yerine sabit-zamanlı eşitlik).

### ECDSA'ya Özgü Nonce Sızıntıları

ECDSA imzada her imza için rastgele bir **nonce `k`** kullanılır. Bu, ECC'nin en kırılgan noktalarından biridir:

- **Nonce tekrar kullanımı**: Aynı `k` iki farklı mesajda kullanılırsa, iki imzadan **özel anahtar cebirsel olarak çözülür**. Bu, gerçek dünyada (zayıf RNG, gömülü cihazlar, kötü kütüphaneler) tekrar tekrar görülmüş, cüzdan ve oyun konsolu ölçeğinde anahtar sızıntılarına yol açmıştır.
- **Kısmi/öngörülebilir nonce (biased nonce)**: `k`'nin birkaç bitinin bile öngörülebilir ya da yanlı olması, çok sayıda imza toplandığında **lattice (kafes) saldırılarıyla** (Hidden Number Problem) anahtarı çözer. "Az sızıntı × çok imza = tam anahtar."
- **Nonce üretiminde zayıf RNG**: Entropi yetersizse `k`'ler çakışır ya da tahmin edilebilir olur.

**Savunma**:

- **Deterministik nonce (RFC 6979)**: `k`'yı özel anahtar ve mesaj hash'inden HMAC ile türetin. RNG'ye bağımlılığı kaldırır, tekrar kullanımı imkânsızlaştırır.
- **EdDSA'ya geçin**: Ed25519 nonce'u deterministik olarak türetir ve tasarımı gereği bu sınıf hataya kapalıdır; yeni sistemlerde tercih edilmelidir.
- Nonce'u tüm kod yollarında constant-time üretip constant-time işleyin.

### Fault (Hata Enjeksiyonu) Saldırıları

**Kök neden**: Fiziksel erişimi olan saldırgan (gömülü/HSM/smartcard), hesaplama sırasında voltaj/saat/lazer ile bilerek hata oluşturur (fault injection). ECC'de, örneğin bir imza hesaplamasına enjekte edilen tek bir hata, "bozuk" bir çıktı üretir; doğru ve bozuk çıktının karşılaştırılması özel anahtarı sızdırabilir. Ayrıca hatalı bir hesap, noktayı kurbanın farkında olmadan zayıf bir eğriye taşıyabilir.

**Savunma**:

- **Sonuç doğrulama**: İmzayı üretir üretmez doğrulayın; bozuksa yayınlamayın. Skaler çarpma sonucunun beklenen eğri üzerinde olduğunu tekrar kontrol edin (point-on-curve).
- **Redundancy / hesabı iki kez yapıp karşılaştırma**, kritik gömülü sistemlerde uygulanır.
- Fiziksel/donanımsal karşı önlemler (sensörler, shielding) HSM ve smartcard tasarımına aittir.

## Yaygın Hatalar (Kontrol Listesi)

- **Gelen public key'i doğrulamamak.** En yaygın ve en yıkıcı hata. Her dış nokta için "on-curve" + "cisim aralığı" + (kofaktör varsa) "alt grup" kontrolü yapılmalı.
- **`b` katsayısını doğrulamada atlamak.** On-curve kontrolü `b`'yi içermezse invalid-curve saldırısı açık kalır.
- **Statik ECDH kullanıp ephemeral'a geçmemek.** Uzun ömürlü `d`, tekrar-sorgu saldırılarını mümkün kılar; ECDHE tercih edin.
- **Kofaktör temizliği yapmadan h>1 eğri kullanmak.** Small subgroup katkısını `n·Q=O` kontrolü ya da `h·Q` çarpımıyla nötrleyin.
- **x-only optimizasyonunu twist-güvensiz eğriyle birleştirmek.** x-only kullanacaksanız Curve25519/Curve448 gibi twist-güvenli eğri kullanın.
- **Kendi eğrinizi / explicit parametreleri kabul etmek.** Yalnızca denetlenmiş named curve'lere izin verin.
- **Naif double-and-add ile gizli bite bağlı dallanma.** Constant-time (Montgomery ladder, masking) zorunlu.
- **ECDSA'da RNG-tabanlı nonce.** RFC 6979 deterministik nonce ya da EdDSA kullanın; nonce'u asla tekrar kullanmayın.
- **İmzayı üretmeden önce doğrulamamak (fault'a açık kalmak).** Kritik ortamlarda çıktıyı yayınlamadan doğrulayın.
- **Kendi ECC matematiğinizi yazmak.** Denetlenmiş, constant-time, yan-kanal sertleştirilmiş kütüphaneler (ör. libsodium, olgun TLS yığınları) kullanın; kripto primitiflerini elle yeniden yazmayın.

## Özet Zihinsel Model

ECC güvenliği üç halkadan oluşur ve zincir en zayıf halka kadar güçlüdür:

1. **Doğru eğri** (parametre/eğri seçimi zayıf eğrileri, explicit parametreleri, twist-güvensizliği eler).
2. **Doğru nokta** (point validation: on-curve + cisim aralığı + alt grup, invalid-curve ve small subgroup saldırılarını eler).
3. **Doğru işlem** (constant-time skaler çarpma + deterministik/tekilsiz nonce + fault kontrolü, side-channel sızıntılarını eler).

Pratik yön: mümkün olduğunca **Curve25519/Ed25519 ailesini ve olgun, denetlenmiş kütüphaneleri** kullanın; bunlar bu tuzakların çoğunu tasarımla kapatır. Kendi implementasyonunuzu yazmak zorundaysanız, yukarıdaki üç halkanın her birini ayrı ayrı test edin ve düşman gözüyle (adversarial) doğrulama testleri (geçersiz nokta, düşük mertebeli nokta, twist noktası) ekleyin.
