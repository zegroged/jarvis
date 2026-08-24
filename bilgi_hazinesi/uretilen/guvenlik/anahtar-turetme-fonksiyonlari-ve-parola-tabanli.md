# Anahtar Türetme Fonksiyonları (KDF) ve Parola Tabanlı Anahtar Türetme

## Giriş ve Kapsam

Kriptografide çoğu hata, algoritmanın kendisinde değil, **anahtarların nasıl elde edildiğinde** yatar. AES-256 kusursuz olabilir; ama o 256 bitlik anahtarı zayıf bir kaynaktan, yanlış bir dönüşümle ya da alan ayrımı (domain separation) yapmadan türetiyorsanız, sistemin güvenliği o türetme adımında çöker.

**Anahtar Türetme Fonksiyonu (Key Derivation Function, KDF)**, bir gizli girdiden (ana anahtar, paylaşılan sır, parola vb.) bir veya daha fazla kriptografik olarak güçlü anahtar üreten fonksiyondur. Bu konu, iki komşu başlığın tam arasında kalır: **Parola Saklama/Hashleme** (kullanıcı parolasını doğrulamak için sakladığınız değer) ve **Anahtar/Sır Yönetimi** (anahtarların dağıtımı, döngüsü, saklanması). KDF'ler bu ikisini birbirine bağlar ve kendine özgü tuzakları vardır: `salt` ile `info`'nun karıştırılması, alan ayrımının atlanması, yanlış fonksiyonun yanlış işe koşulması.

Bu makale KDF'leri iki büyük aileye ayırır ve her birinin çalışma mantığını, doğru kullanımını, tespit ve savunma noktalarını ele alır.

## Temel Kavram: İki Farklı KDF Ailesi

KDF'leri girdilerinin **entropi düzeyine** göre ayırmak, en kritik zihinsel modeldir. Bu ayrımı kaçırmak, en yaygın hataların köküdür.

### 1. Yüksek Entropili Girdi İçin KDF'ler (KBKDF / Extract-Expand)

Girdi zaten kriptografik olarak güçlüyse — örneğin bir Diffie-Hellman anlaşmasından çıkan paylaşılan sır, bir donanım rastgele sayı üreticisinin çıktısı, ya da başka bir 256 bitlik anahtar — amaç entropi *eklemek* değil, mevcut entropiyi **düzgün biçimlendirmek**, olası önyargıları (bias) silmek ve tek bir kaynaktan birden çok bağımsız anahtar üretmektir.

Bu ailenin kanonik örneği **HKDF**'tir (HMAC-based KDF). Bilinçli olarak **hızlıdır**; çünkü girdide zaten yeterli entropi vardır, saldırganı yavaşlatmaya (brute-force'a karşı) gerek yoktur.

### 2. Düşük Entropili Girdi İçin KDF'ler (PBKDF — Parola Tabanlı)

Girdi bir **parola** ise, sorun kökten değişir. İnsan parolaları düşük entropilidir; tahmin edilebilir, sözlük saldırılarına açıktır. Burada amaç, her tahmin denemesini **kasıtlı olarak pahalı** (yavaş, bellek-yoğun) hale getirerek toplu deneme saldırılarını (offline brute-force) ekonomik olarak imkânsız kılmaktır.

Bu ailenin üyeleri **PBKDF2**, **scrypt** ve **Argon2**'dir. Bunlar bilinçli olarak **yavaştır** ve/veya **bellek-yoğundur**.

> Altın kural: Yüksek entropili bir sırdan anahtar türetiyorsanız HKDF; bir paroladan türetiyorsanız Argon2 (ya da scrypt/PBKDF2). Bunları karıştırmak — örneğin bir DH sırrına Argon2 uygulamak veya bir parolaya sade HKDF uygulamak — ciddi bir tasarım hatasıdır.

## HKDF: Extract-then-Expand Modeli

HKDF'nin gücü, iki ayrı ve iyi tanımlı adıma dayanır. Bu iki adımı ayrı ayrı anlamak, HKDF'yi doğru kullanmanın anahtarıdır.

### Extract (Çıkarma) Adımı

```
PRK = HKDF-Extract(salt, IKM)
```

Burada `IKM` (Input Keying Material) girdi anahtar malzemesidir (örneğin DH paylaşılan sırrı). Extract adımı, girdideki entropiyi **yoğunlaştırılmış, düzgün dağılmış** bir sözde-rastgele anahtara (Pseudorandom Key, `PRK`) sıkıştırır. İçeride bu bir HMAC işlemidir: `PRK = HMAC(salt, IKM)`. Girdinin istatistiksel önyargıları burada silinir.

`salt` burada gizli olmak zorunda değildir; amacı, aynı IKM'nin farklı bağlamlarda farklı PRK'lar üretmesini sağlamaktır. Bu adım atlanabilir (skippable) — girdi zaten düzgün rastgele bir anahtarsa, doğrudan Expand'e geçilebilir.

### Expand (Genişletme) Adımı

```
OKM = HKDF-Expand(PRK, info, L)
```

Expand adımı, `PRK`'dan istenen uzunlukta (`L` bayt) çıktı anahtar malzemesi (Output Keying Material, `OKM`) üretir. Kritik parametre burada **`info`**'dur.

`info`, türetilen anahtarı belirli bir **bağlama bağlayan** bir etikettir. Aynı `PRK`'dan farklı `info` değerleriyle **birbirinden bağımsız** anahtarlar üretebilirsiniz:

```
şifreleme_anahtarı = HKDF-Expand(PRK, "uygulama-v1 sifreleme anahtari", 32)
mac_anahtarı        = HKDF-Expand(PRK, "uygulama-v1 mac anahtari",       32)
```

İki anahtar aynı sırdan çıkmasına rağmen, `info` farklı olduğu için kriptografik olarak ilişkisizdir. Birini ele geçirmek diğerini vermez.

### Domain Separation (Alan Ayrımı) — En Kritik Kavram

HKDF'nin `info` parametresi, **domain separation**'ın araçıdır ve KDF kullanımının en sık atlanan güvenlik ilkesidir.

Alan ayrımı, aynı ana sırdan üretilen farklı amaçlı anahtarların birbirine karışmasını önlemektir. Eğer aynı `PRK`'yı hem şifreleme hem imzalama için `info` etiketi kullanmadan doğrudan kesip kullanırsanız — örneğin ilk 32 baytı şifreleme, sonraki 32 baytı MAC olarak — protokoller arası (cross-protocol) saldırılara ve anahtar yeniden kullanımı (key reuse) zafiyetlerine kapı açarsınız. `info`'ya sürüm, protokol adı ve amaç yazmak, gelecekteki protokol değişikliklerini de güvenli kılar.

İyi bir `info` uygulaması genellikle şunları içerir: uygulama/protokol adı, sürüm numarası, anahtarın amacı, ve varsa taraf kimlikleri.

## PBKDF2: İterasyon Tabanlı Yavaşlatma

**PBKDF2** (Password-Based KDF 2), parola tabanlı türetmenin en eski ve en yaygın standardıdır. Mantığı basittir: bir HMAC (ya da başka bir PRF) işlemini `c` kez (iterasyon sayısı) art arda çalıştırır.

```
DK = PBKDF2(PRF, parola, salt, c, dkLen)
```

- **`salt`**: Her parola için benzersiz, rastgele değer. Önceden hesaplanmış tablo (rainbow table) saldırılarını ve iki kullanıcının aynı parolasının aynı hash'i vermesini engeller.
- **`c`**: İterasyon sayısı. Ne kadar yüksekse, hem meşru doğrulama hem de saldırganın her denemesi o kadar yavaşlar. Bu sayı, donanım hızlandıkça periyodik olarak artırılmalıdır.

### PBKDF2'nin Temel Zayıflığı: Bellek-Hafifliği

PBKDF2'nin kritik dezavantajı, **bellek-hafif** olmasıdır. Yalnızca CPU zamanı harcar, çok az bellek kullanır. Bu, saldırganın **GPU**, **FPGA** veya **ASIC** gibi yüksek paralellikli donanımlarla binlerce tahmini aynı anda, çok ucuza denemesine imkân verir. Modern parola kırma donanımları PBKDF2'ye karşı son derece etkilidir. Bu yüzden yeni tasarımlarda PBKDF2 artık ilk tercih değildir; ancak FIPS uyumluluğu gereken ortamlarda veya eski sistemlerle uyum için hâlâ kullanılır.

## scrypt: Bellek-Zorluğu (Memory-Hard) Kavramı

**scrypt**, PBKDF2'nin GPU/ASIC zafiyetine bir yanıt olarak tasarlandı. Temel fikir **memory-hard** olmaktır: fonksiyon yalnızca CPU değil, aynı zamanda büyük miktarda **RAM** kullanmaya zorlanır.

Neden bu önemli? GPU ve ASIC'ler binlerce paralel çekirdeğe sahiptir ama her çekirdeğe düşen hızlı bellek pahalıdır ve sınırlıdır. Bir fonksiyon büyük bellek gerektiriyorsa, saldırgan bin tahmini paralel çalıştırmak için bin kat bellek de almak zorunda kalır — bu, saldırının ekonomisini bozar. scrypt'in ana parametreleri şunlardır:

- **`N`**: CPU/bellek maliyet parametresi (bellek kullanımını belirler).
- **`r`**: Blok boyutu.
- **`p`**: Paralellik derecesi.

scrypt, memory-hard KDF fikrini pratiğe geçiren ilk yaygın örnektir. Ancak parametre ayarı biraz karmaşıktır ve `N`, `r`, `p` arasındaki etkileşim yanlış ayarlanırsa beklenen bellek-zorluğu elde edilemeyebilir.

## Argon2: Modern Standart

**Argon2**, 2015 Password Hashing Competition'ın kazananıdır ve bugün parola tabanlı türetme için **önerilen ilk tercihtir**. Memory-hardness kavramını olgunlaştırır ve ayarlanabilir üç boyut sunar. Üç varyantı vardır:

- **Argon2d**: Bellek erişimi veriye bağımlıdır (data-dependent). Maksimum GPU direnci sağlar ama yan kanal (side-channel) saldırılarına teorik olarak açıktır. Kripto para madenciliği gibi yan kanalın tehdit olmadığı yerlerde uygundur.
- **Argon2i**: Bellek erişimi veriden bağımsızdır (data-independent). Yan kanal dirençlidir, parola hashleme için daha güvenlidir.
- **Argon2id**: İkisinin melezidir — ilk geçişte i, sonrakilerde d davranışı. **Genel amaçlı kullanım için önerilen varyant budur.**

### Argon2 Parametreleri

Argon2, üç eksende ayar sunar ve bu esneklik onu güçlü kılar:

- **Bellek maliyeti (memory cost, `m`)**: Kullanılacak RAM miktarı. Bellek-zorluğunun ana kaldıracıdır.
- **Zaman maliyeti (time cost / iterations, `t`)**: Geçiş sayısı.
- **Paralellik (parallelism, `p`)**: Kaç iş parçacığının kullanılacağı.

Bu parametreler, sunucunuzun kaldırabileceği en yüksek maliyeti verecek şekilde ayarlanmalıdır. Kesin sayılar sürüme, donanıma ve kabul edilebilir gecikmeye göre değişir; bu yüzden burada belirli bir "doğru" değer vermek yanıltıcı olur. Pratik yaklaşım: hedef doğrulama süresini (örneğin kullanıcı girişinde birkaç yüz milisaniye) belirleyip, o süreyi verecek bellek/iterasyon değerlerini ölçerek bulmaktır. OWASP gibi kaynaklar dönemsel olarak güncel taban değerleri yayımlar; üretimde bu güncel rehberlere bakılmalıdır.

## Karşılaştırma Tablosu

| Özellik | PBKDF2 | scrypt | Argon2 (id) | HKDF |
|---|---|---|---|---|
| Girdi türü | Parola | Parola | Parola | Yüksek entropili sır |
| Amaç | Yavaşlatma | Yavaşlatma + bellek | Yavaşlatma + bellek + zaman | Biçimlendirme + genişletme |
| Memory-hard | Hayır | Evet | Evet (ayarlanabilir) | Uygulanmaz |
| GPU/ASIC direnci | Zayıf | İyi | Çok iyi | Uygulanmaz |
| Hız | Kasıtlı yavaş | Kasıtlı yavaş | Kasıtlı yavaş | Kasıtlı hızlı |
| Ana parametre | İterasyon (`c`) | `N, r, p` | `m, t, p` | `salt, info` |
| Yeni tasarımda öneri | Sadece FIPS/uyum | Kabul edilebilir | Birincil tercih | Sır genişletme için birincil |

## salt ve info: İki Farklı Kavramın Karıştırılması

En sık kavramsal hata, `salt` ile `info`'yu aynı şey sanmaktır. İkisi de "ekstra girdi"dir ama işlevleri tamamen farklıdır:

- **`salt`** (PBKDF/parola dünyasında): **Benzersizlik** sağlar. Her kullanıcı/kayıt için rastgele ve farklı olmalıdır. Amacı, aynı parolanın farklı hash üretmesini ve önhesaplanmış tabloları etkisiz kılmaktır. Salt gizli değildir; hash'in yanında saklanır.
- **`info`** (HKDF dünyasında): **Bağlam/alan ayrımı** sağlar. Rastgele olması gerekmez; genellikle sabit, anlamlı bir etikettir ("app-v2-encryption-key" gibi). Amacı, aynı sırdan farklı amaçlar için ilişkisiz anahtarlar üretmektir.
- HKDF'nin **`salt`**'ı ise Extract adımında entropiyi çeşitlendirir; parola salt'ından farklı bir rol oynar (benzersizlik değil, çıkarma çeşitlemesi).

Bu üç kavramı ayırt edememek, örneğin her HKDF çağrısında `info`'yu boş bırakıp alan ayrımını hiç yapmamak gibi somut zafiyetlere yol açar.

## Yaygın Hatalar

1. **Yanlış aileyi seçmek.** Bir paroladan sade SHA-256 ya da tek geçişli HKDF ile anahtar türetmek. Parola düşük entropilidir; yavaşlatma olmadan offline kırma önemsiz hale gelir. Tersine, yüksek entropili bir sırra Argon2 uygulamak gereksiz maliyet getirir (ama en azından güvenlik açığı değildir).

2. **Alan ayrımını atlamak.** Aynı `PRK`'yı `info` etiketi olmadan birden çok amaç için kullanmak; ya da aynı ana anahtarı hem şifreleme hem MAC için doğrudan kullanmak. Bu, anahtar yeniden kullanımı ve protokoller arası saldırı riski doğurur.

3. **Sabit ya da tekrar eden salt.** Salt'ı koda gömmek (hardcode) veya tüm kullanıcılar için aynı salt'ı kullanmak, salt'ın tüm amacını yok eder; önhesaplanmış tablolar yeniden etkili olur.

4. **Yetersiz maliyet parametreleri.** İterasyon/bellek/zaman değerlerini yıllar önce ayarlayıp hiç güncellememek. Donanım hızlandıkça bu değerler geride kalır; periyodik olarak yükseltilmeli ve idealde saklanan hash formatına parametreler gömülmelidir ki kademeli yükseltme (rehash on login) yapılabilsin.

5. **Türetilmiş anahtarı yeniden KDF'lemek yerine parolayı saklamak.** Parolanın kendisini ya da geri döndürülebilir bir dönüşümünü saklamak. KDF çıktısı doğrulama için saklanır; parolanın kendisi asla.

6. **HKDF-Extract'i entropisiz girdiyle kullanmak.** HKDF entropi *üretmez*, yalnızca mevcut entropiyi biçimlendirir. Zayıf bir girdiye HKDF uygulamak onu güçlü yapmaz. Girdi paroluysa önce bir PBKDF gerekir.

7. **Çıktı uzunluğunu (`dkLen`/`L`) fonksiyonun güvenli sınırının ötesine zorlamak.** HKDF-Expand'in üretebileceği maksimum uzunluk, kullanılan hash fonksiyonunun çıktı boyutuna bağlı bir üst sınırla (255 × HashLen) kısıtlıdır; bunu aşan istekler tanımsız/güvensizdir.

## Tespit ve Savunma

KDF hataları çoğunlukla **statik olarak**, kod ve konfigürasyon düzeyinde yakalanır; çünkü çalışma anında "yanlış KDF" görünmez bir şekilde çalışır.

### Tespit (Detection)

- **Kod taraması / SAST.** Parola işleyen yollarda sade `MD5`, `SHA-1`, `SHA-256` çağrılarını arayın. Parola bağlamında düz hash kullanımı neredeyse her zaman bir zafiyettir. `PBKDF2`, `scrypt`, `Argon2` çağrılarının varlığını doğrulayın.
- **Konfigürasyon denetimi.** İterasyon/bellek/zaman parametrelerinin güncel taban değerlerin altında olup olmadığını kontrol edin. Sabit salt'ları (kaynak kodda gömülü rastgele olmayan salt) tarayın.
- **Depolanan hash formatı denetimi.** Veritabanındaki parola alanının, algoritma ve parametreleri kendi içinde taşıyan bir formatta (ör. Argon2/bcrypt'in standart kodlanmış dizesi) olup olmadığını doğrulayın. Ham, algoritma bilgisi taşımayan hash'ler kademeli yükseltmeyi imkânsızlaştırır.
- **HKDF çağrılarında `info`/`salt` denetimi.** Boş ya da sabit tek bir `info` ile birden çok anahtar üreten kod yolları, alan ayrımı eksikliğinin işaretidir.
- **Anormal doğrulama süresi.** Giriş uç noktalarının çok hızlı (mikrosaniye düzeyi) yanıt vermesi, arkada güçlü bir KDF olmadığının telemetrik ipucu olabilir.

### Savunma (Defense)

- **Doğru aileyi doğru işe koşun.** Parola → Argon2id (birinci tercih), gerekirse scrypt; FIPS zorunluysa yüksek iterasyonlu PBKDF2-HMAC-SHA-256. Yüksek entropili sır → HKDF.
- **Her zaman benzersiz, rastgele salt.** Kriptografik olarak güvenli bir üreteçten, kayıt başına.
- **`info` ile alan ayrımı yapın.** HKDF-Expand çağrılarında amaç + sürüm + protokol içeren anlamlı `info` etiketleri kullanın.
- **Maliyet parametrelerini ölçüye dayalı ayarlayın ve saklayın.** Parametreleri hash formatına gömün; kullanıcı girişinde parametreler eskimişse şeffaf biçimde yeniden hashleyin (rehash-on-login).
- **Pepper (biber) katmanını değerlendirin.** Salt'a ek olarak, tüm kullanıcılar için ortak ama veritabanı dışında (ör. bir HSM veya secret manager'da) tutulan gizli bir `pepper`, veritabanı sızıntısında dahi ek koruma sağlar. Pepper anahtar yönetimi disiplini gerektirir.
- **Kütüphaneye güvenin, kendiniz yazmayın.** KDF'leri elle uygulamak yerine iyi denetlenmiş, bakımı yapılan kriptografik kütüphaneleri kullanın. Zamanlama-güvenli karşılaştırma (constant-time comparison) gibi ayrıntılar bu kütüphanelerde zaten çözülmüştür.

## Özet

KDF'ler, kriptografik sistemin güvenlik zincirini "gizli bir değer"den "kullanılabilir bir anahtar"a bağlayan halkadır ve tam da bu ara konumları nedeniyle sıkça yanlış kullanılır. İki soruyu net ayırmak, hataların çoğunu önler: **Girdim yüksek entropili mi, yoksa parola mı?** ve **Bu anahtarı hangi bağlama, hangi amaca bağlıyorum?** Birincisi HKDF ile parola tabanlı KDF'ler arasındaki seçimi belirler; ikincisi `salt` (benzersizlik) ile `info` (alan ayrımı) arasındaki ayrımı zorunlu kılar. Modern varsayılanlar bugün nettir: paroladan türetme için Argon2id, yüksek entropili sırdan genişletme için `info` etiketli HKDF. Geri kalan güvenlik, parametrelerin donanımla birlikte güncel tutulmasına ve alan ayrımının hiçbir zaman atlanmamasına bağlıdır.
