# Kripto Kütüphane Güvenliği ve Yanlış API Kullanımı

## Giriş: Sorun algoritmada değil, kullanımda

Kriptografi konusunda yaygın bir yanılgı vardır: "AES kırıldı mı?", "RSA güvenli mi?" gibi sorular. Gerçekte, üretim sistemlerinde karşılaşılan kriptografik zafiyetlerin ezici çoğunluğu algoritmanın matematiksel olarak kırılmasından **kaynaklanmaz**. AES-256 pratikte kırılamaz; SHA-256'nın ön-görüntüsü (preimage) bulunamaz. Buna rağmen sistemler sürekli olarak kriptografik açıklardan sömürülür. Sebep neredeyse her zaman aynıdır: **kütüphanenin API'sinin yanlış, güvensiz veya varsayılan-tehlikeli biçimde kullanılması.**

Bu makale OpenSSL, libsodium ve BouncyCastle gibi yaygın kütüphaneler üzerinden yanlış kullanım kalıplarını (misuse patterns), bunların kök nedenlerini, tespit ve savunma yöntemlerini; ayrıca FIPS uyumluluğu ve kripto-çeviklik (crypto-agility) kavramlarını ele alır. Amaç mekanizmayı anlamak ve savunma kurmaktır.

## Neden kriptografik API'ler bu kadar yanlış kullanılıyor?

### Kök neden 1: Güvensiz varsayılanlar (insecure defaults)

Tarihsel olarak birçok kütüphane, geriye dönük uyumluluk uğruna güvensiz varsayılanlar sundu. Klasik örnek OpenSSL'in eski `EVP_EncryptInit` çağrılarında blok şifreleme modunun açıkça belirtilmemesi durumunda ECB gibi tehlikeli modlara düşülebilmesiydi. Bir API "çalışıyor" göründüğü an geliştirici durur; oysa "çalışmak" ile "güvenli olmak" bambaşka şeylerdir. Şifreli metin okunamaz görünür, testler geçer, fakat altta ECB modu deseni sızdırır.

### Kök neden 2: Kriptografik ön koşulların API'de görünmez olması

AES-GCM gibi bir AEAD (Authenticated Encryption with Associated Data) modunun mutlak kuralı vardır: **aynı anahtar altında aynı nonce iki kez kullanılamaz.** Fakat API imzası `encrypt(key, nonce, plaintext)` bunu size hatırlatmaz. Nonce'u sabit yazmak, sıfırdan başlatıp reset atmamak veya süreç yeniden başladığında sayacı sıfırlamak derleme hatası vermez, test kırmaz. Kriptografik felaket sessizce gerçekleşir.

### Kök neden 3: Yanlış soyutlama seviyesi

OpenSSL ve BouncyCastle "düşük seviyeli" kütüphanelerdir: size blok, mod, padding, IV, MAC gibi tüm bileşenleri ayrı ayrı verir ve doğru şekilde birleştirmeyi **size bırakır.** Bu, geliştiriciye kendi ayağına ateş etmesi için sonsuz fırsat sunar. libsodium'un felsefesi tam tersidir: az sayıda, yüksek seviyeli, kötüye kullanılması zor (misuse-resistant) fonksiyon sunar.

## Yaygın Yanlış Kullanım Kalıpları

### 1. Nonce / IV yeniden kullanımı (nonce reuse)

**Tanım:** Aynı anahtar altında aynı nonce'un tekrar kullanılması.

**Çalışma mantığı:** CTR tabanlı modlar (AES-CTR, AES-GCM, ChaCha20) nonce+sayaçtan bir anahtar akışı (keystream) üretip düz metinle XOR'lar. İki farklı düz metin aynı keystream ile XOR'lanırsa, iki şifreli metnin XOR'u iki düz metnin XOR'una eşit olur; anahtar tamamen devre dışı kalır. GCM'de durum daha kötüdür: nonce tekrarı sadece gizliliği değil, **kimlik doğrulama anahtarını (GHASH authentication key)** da açığa çıkarabilir, böylece saldırgan mesaj sahteciliği (forgery) yapabilir.

**Örnek kalıp:**
```
nonce = bytes(12)   # sabit sıfır nonce — felaket
ciphertext = aesgcm.encrypt(key, nonce, plaintext, None)
```

**Tespit:** Kod tabanında sabit nonce/IV literalleri arayın (sıfır dizisi, sabit hex). Statik analizde "nonce kaynağı rastgele değil" kuralları etkindir. Aynı anahtar+nonce çiftinin log/telemetride tekrarını yakalayacak invariant testleri yazın.

**Savunma:** Nonce'u CSPRNG'den üretin ve mümkünse anahtarla birlikte sayacın kalıcılığını garanti altına alın. Uzun ömürlü anahtarlarda XChaCha20 gibi geniş (24 baytlık) nonce alanı olan yapıları tercih edin — rastgele nonce çakışma olasılığı ihmal edilebilir hale gelir. En sağlam çözüm nonce-misuse-resistant modlardır (AES-GCM-SIV).

### 2. ECB modu kullanımı

**Tanım:** Elektronik Kod Kitabı modunda her blok bağımsız şifrelenir; aynı düz metin bloğu her zaman aynı şifreli blok üretir.

**Çalışma mantığı:** Blok seviyesinde desen korunduğu için veri yapısı sızar. Meşhur "ECB penguen" örneğinde şifreli görüntüde penguenin hatları hâlâ görülür. ECB asla mesaj gizliliği sağlamaz.

**Tespit:** `ECB` string'i, mod belirtmeden çağrılan blok şifreleme API'leri. Şifreli çıktıda tekrarlanan 16 baytlık blokların istatistiksel analizi.

**Savunma:** AEAD kullanın (GCM, ChaCha20-Poly1305). Ham blok şifreleme moduna doğrudan asla dokunmayın.

### 3. Kimlik doğrulamasız şifreleme — MAC'siz gizlilik

**Tanım:** Yalnızca gizlilik sağlayan bir mod (CBC, CTR) kullanmak ama bütünlük/kimlik doğrulaması (MAC) eklememek veya yanlış eklemek.

**Çalışma mantığı:** Kimlik doğrulaması olmayan şifreli metin, saldırgan tarafından değiştirilebilir. Klasik **padding oracle** saldırısı (CBC modunda), sunucunun geçersiz padding'e verdiği farklı yanıtları sömürerek şifreli metnin tümünü çözebilir — anahtarı hiç bilmeden. "Encrypt-then-MAC" yerine "MAC-then-encrypt" veya hiç MAC olmaması bu tür saldırıların kapısını açar.

**Tespit:** CBC/CTR modlarının HMAC olmadan kullanımı; şifre çözme sonrası padding/format hatalarının farklı hata mesajı veya farklı zamanlama ile döndürülmesi.

**Savunma:** Her zaman AEAD kullanın. Zorunluysa Encrypt-then-MAC yapısını sabit-zamanlı (constant-time) karşılaştırmayla uygulayın. Hata yanıtlarını tek tipleştirin (padding hatası ile MAC hatasını ayırt ettirmeyin).

### 4. Zayıf/yanlış anahtar türetme — parolayı doğrudan anahtar yapmak

**Tanım:** Kullanıcı parolasını doğrudan şifreleme anahtarı olarak kullanmak veya tek turlu düz hash (SHA-256(parola)) ile anahtar üretmek.

**Çalışma mantığı:** Parolaların entropisi düşüktür ve hızlı hash'ler GPU/ASIC ile saniyede milyarlarca deneme yapılmasına izin verir. Doğru yaklaşım, kasıtlı olarak yavaş ve bellek-zor (memory-hard) bir KDF kullanmaktır.

**Savunma:** Parola tabanlı anahtar için Argon2id (tercih), scrypt veya yeterli iterasyonlu PBKDF2 kullanın; her parola için benzersiz, rastgele salt saklayın. Şifreleme anahtarları için ise CSPRNG çıktısını kullanın.

### 5. Parola saklamada yanlış hash

**Tanım:** Kullanıcı parolalarını MD5, SHA-1 veya salt'sız SHA-256 ile saklamak.

**Savunma:** Parola **saklama** için Argon2id, scrypt veya bcrypt kullanın. Bunlar bilerek yavaştır ve salt yönetimini içerir. Hızlı hash fonksiyonları (SHA ailesi) parola saklamak için değil, bütünlük ve HMAC için tasarlanmıştır.

### 6. Zayıf rastgelelik kaynağı (weak RNG)

**Tanım:** Kriptografik anahtar, nonce, token veya IV üretiminde kriptografik olmayan PRNG kullanmak (`rand()`, `Math.random()`, `java.util.Random`, tohumu (seed) öngörülebilir üreticiler).

**Çalışma mantığı:** Bu üreticiler istatistiksel olarak "rastgele görünse" de deterministik ve öngörülebilirdir. Birkaç çıktı gözlemleyen saldırgan iç durumu geri çıkarıp gelecekteki tüm değerleri kestirebilir. Tarihsel olarak zayıf/tohumlanmamış RNG, tahmin edilebilir SSH ve TLS anahtarlarına yol açmıştır.

**Tespit:** Kripto bağlamında `Random`, `Math.random`, sabit tohum (`srand(time(NULL))`, `SecureRandom.setSeed(sabit)`) kullanımı.

**Savunma:** Java'da tohumlanmamış `SecureRandom`; işletim sistemi CSPRNG'si (`getrandom`, `/dev/urandom`); libsodium'da `randombytes_buf`. `SecureRandom`'a sabit tohum vermeyin — bu onu deterministik yapar.

### 7. Sertifika/host doğrulamasını kapatmak

**Tanım:** TLS istemcisinde sertifika zinciri veya hostname doğrulamasını devre dışı bırakmak (`verify=False`, "tüm sertifikaları kabul et" trust manager, host adı denetimini boş geçmek).

**Çalışma mantığı:** Doğrulama kapalıysa TLS'in şifrelemesi hâlâ çalışır ama **kiminle** konuştuğunuzun garantisi kalmaz. Araya giren bir saldırgan (man-in-the-middle) kendi sertifikasını sunar, istemci kabul eder ve tüm trafik saldırgan üzerinden akar. Şifreleme var ama koruma yok.

**Tespit:** `verify=False`, boş/her-şeyi-kabul eden TrustManager veya HostnameVerifier, sertifika hatalarını yutan try/catch blokları.

**Savunma:** Varsayılan doğrulamayı asla kapatmayın. Test için bile geçici kapatmalar üretime sızar; yapılandırmayı ortam bayrağıyla değil, kod incelemesiyle koruyun. Gerekiyorsa doğru CA'yı trust store'a ekleyin veya sertifika sabitleme (pinning) uygulayın.

### 8. Sabit-kodlanmış anahtarlar ve sırlar (hardcoded secrets)

**Tanım:** Şifreleme anahtarlarını, HMAC sırlarını veya API anahtarlarını kaynak koda, yapılandırma dosyasına veya konteyner imajına gömmek.

**Çalışma mantığı:** Depoya erişen herkes anahtara erişir; git geçmişinden silmek bile çoğu zaman yetmez. Anahtar rotasyonu imkânsızlaşır.

**Tespit:** Depo tarama araçları (secret scanning), yüksek entropili string dedektörleri, git geçmişi taraması.

**Savunma:** Sırları bir gizli yönetim sistemi (secrets manager / KMS / HSM) üzerinden yükleyin; anahtar rotasyonunu ve erişim denetimini merkezileştirin.

### 9. Sabit-zamanlı olmayan karşılaştırma (timing side-channel)

**Tanım:** MAC, token veya hash karşılaştırmasında normal `==` / `equals` / `memcmp` kullanmak.

**Çalışma mantığı:** Bu karşılaştırmalar ilk farklı baytta durur (short-circuit). Saldırgan yanıt süresini ölçerek doğru bayt sayısını bayt-bayt keşfedebilir ve zamanla geçerli bir MAC/token üretebilir.

**Savunma:** Sabit-zamanlı karşılaştırma kullanın: OpenSSL'de `CRYPTO_memcmp`, libsodium'da `sodium_memcmp`, Java'da `MessageDigest.isEqual`, Python'da `hmac.compare_digest`.

### 10. RSA'da yanlış padding — tekstbook RSA ve eski PKCS#1 v1.5

**Tanım:** RSA şifrelemede padding kullanmamak (textbook RSA) veya güvenlik açığı bilinen eski şemaları dikkatsiz kullanmak.

**Çalışma mantığı:** Padding'siz RSA deterministiktir ve çok sayıda saldırıya açıktır. PKCS#1 v1.5 şifreleme padding'i tarihsel olarak padding-oracle tipi (Bleichenbacher) saldırılara zemin hazırlamıştır.

**Savunma:** RSA şifreleme için OAEP; RSA imza için PSS tercih edin. Mümkünse anahtar taşıma için tamamen ECDH/hibrit şemalara geçin.

## FIPS Uyumluluğu

### Tanım

FIPS 140-2/140-3, ABD federal standartlarıdır ve kriptografik modüllerin doğrulanması (validation) için gereksinimler tanımlar. Devlet, savunma, sağlık ve finans alanlarında sözleşme gereği talep edilir. "FIPS uyumlu" olmak yalnızca güçlü algoritma kullanmak değildir; **doğrulanmış (validated) bir kriptografik modülün, onaylı (approved) algoritmalarla, onaylı modda kullanılması** demektir.

### Çalışma mantığı ve kısıtları

FIPS modu açıldığında kütüphane yalnızca onaylı algoritmalara (AES, SHA-2, onaylı KDF'ler, onaylı imza şemaları vb.) izin verir ve onaylanmamış olanları (örneğin MD5, bazı bağlamlarda kimi eğri veya modlar) reddeder. Bu, uygulamanın FIPS-dışı algoritma çağırdığında **çalışma zamanında hata** almasına yol açabilir — bu beklenen bir davranıştır.

### Yaygın hatalar

- FIPS modunu açtığını sanıp modülün doğrulanmış sürümünü kullanmamak. Doğrulama sürüme ve modüle özgüdür; rastgele bir OpenSSL derlemesi FIPS-doğrulanmış değildir.
- "Güçlü algoritma kullanıyorum, o halde FIPS uyumluyum" yanılgısı. Uyumluluk süreç ve doğrulama meselesidir, algoritma seçimi meselesi değildir.
- FIPS modunda MD5 gibi çağrıların hata vermesini beklemeyip uygulamanın sessizce çökmesi. Uygulama kodunu FIPS-dışı ilkellerden temizlemek gerekir.

### Savunma / pratik

Gereksinim gerçekten varsa doğrulanmış modül sürümünü, satıcı belgeleriyle eşleşecek şekilde kullanın; FIPS modunu üretim benzeri ortamda test edin; onaylı olmayan algoritmaların kod tabanından çıkarıldığını doğrulayın.

## Kripto-Çeviklik (Crypto-Agility)

### Tanım

Kripto-çeviklik, bir sistemin kullandığı kriptografik algoritmaları, anahtar boyutlarını veya protokolleri, uygulamayı baştan yazmadan **değiştirebilme** yeteneğidir. Bir algoritma zayıfladığında (örneğin SHA-1'in terk edilmesi) veya yeni bir tehdit ortaya çıktığında (post-kuantum geçiş) hızlı geçişi mümkün kılar.

### Neden kritik

Kriptografik ilkeller sonsuza dek güvenli değildir. Bugün post-kuantum kriptografiye (PQC) geçiş gündemdedir; kuantum bilgisayarlar olgunlaştığında mevcut RSA ve eliptik eğri temelli açık-anahtar şemaları tehdit altına girecektir. Algoritma seçimleri koda sabit gömülü sistemler bu geçişi yıllar süren, maliyetli projelere dönüştürür.

### Çalışma mantığı ve tasarım ilkeleri

- **Algoritma tanımlayıcılarını (algorithm identifiers) veriyle birlikte taşıyın:** Şifreli veriye hangi algoritma/mod/versiyon ile üretildiğini belirten bir başlık ekleyin ki gelecekte geçiş yapılabilsin ve eski veri okunabilir kalsın.
- **Soyutlama katmanı:** Kriptografik çağrıları doğrudan iş mantığına serpiştirmek yerine tek bir arayüz arkasında toplayın. Böylece algoritma değişimi tek noktada yapılır.
- **Sürümleme ve geriye dönük okuma:** Yeni algoritmaya geçerken eski formatı çözebilmeli ama yenisini yazmalısınız.
- **Hibrit yaklaşımlar:** PQC geçişinde klasik + post-kuantum algoritmaları birlikte kullanan hibrit şemalar, birinin ileride kırılmasına karşı sigorta sağlar.

### Yaygın hatalar

- Algoritmayı, anahtar boyutunu ve modu koda sabit gömmek.
- Format başlığına sürüm/algoritma bilgisi koymamak; bu, sonradan geçişi imkânsıza yakın kılar.
- "Şimdilik yeterince güvenli" diye çevikliği ertelemek — geçiş ihtiyacı geldiğinde çok geç olur.

## libsodium'un Misuse-Resistant Felsefesi

libsodium, yukarıdaki hataların çoğunu tasarım gereği önlemeyi hedefler: az sayıda yüksek seviyeli fonksiyon (`crypto_secretbox`, `crypto_box`, `crypto_aead_*`), güvenli varsayılanlar, otomatik CSPRNG (`randombytes_buf`), sabit-zamanlı karşılaştırma (`sodium_memcmp`) ve hassas belleği temizleme (`sodium_memzero`) sunar. Yeni geliştirmede, düşük seviyeli API'lerle uğraşmak yerine bu tür kötüye-kullanılması-zor kütüphaneleri tercih etmek en etkili savunmadır — çünkü hatayı yapmayı **zorlaştırır.**

## Genel Tespit ve Savunma Stratejisi

**Tespit katmanları:**
- **Statik analiz (SAST):** Zayıf algoritmalar (MD5, SHA-1, DES, RC4), ECB modu, sabit IV/nonce, `verify=False`, zayıf RNG, sabit-kodlanmış anahtarlar için kurallar.
- **Sır tarama (secret scanning):** Depo ve git geçmişinde gömülü anahtarlar.
- **Bağımlılık taraması:** Bilinen zafiyetli kütüphane sürümleri.
- **Kod incelemesi:** Kriptografik kod her zaman ikinci bir gözle, tercihen kripto bilgisi olan biriyle gözden geçirilmelidir.

**Savunma ilkeleri:**
1. Ham blok şifreleme yerine daima AEAD kullanın.
2. Nonce/IV'yi CSPRNG'den üretin; tekrarını mümkün kılmayan tasarımlar seçin.
3. Parola saklama için Argon2id/scrypt/bcrypt; anahtar türetme için memory-hard KDF.
4. Karşılaştırmalarda sabit-zamanlı fonksiyonlar.
5. TLS doğrulamasını asla kapatmayın.
6. Sırları kod dışında, gizli yönetim sistemlerinde tutun.
7. Kriptografiyi tek bir soyutlama katmanı arkasına alarak kripto-çeviklik kazanın.
8. Mümkünse düşük seviyeli değil, misuse-resistant yüksek seviyeli kütüphaneler kullanın.

## Sonuç

Kriptografide gerçek risk, matematikte değil mühendislikte yatar. Güçlü algoritmalar yanlış API kullanımıyla değersizleşir: tekrar eden bir nonce, kapatılmış bir sertifika doğrulaması veya kimlik doğrulamasız bir CBC şifreleme, en güçlü şifreyi bile anlamsız kılar. Doğru savunma; güvenli varsayılanları benimsemek, kötüye kullanılması zor kütüphaneleri seçmek, kriptografik kodu titiz incelemeye tabi tutmak ve sistemi baştan kripto-çevik tasarlamaktır. Amaç algoritmayı güçlendirmek değil — onu doğru kullanmaktır.
