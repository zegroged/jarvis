# Simetrik Şifreleme ve Modlar: AES, Çalışma Modları ve AEAD

## Giriş ve Tanım

Simetrik şifreleme, aynı gizli anahtarın hem şifreleme (encryption) hem de şifre çözme (decryption) işleminde kullanıldığı kriptografik yaklaşımdır. Asimetrik şifrelemenin (RSA, ECC gibi) aksine tek anahtar vardır; bu anahtarı bilen her taraf hem veriyi kilitleyebilir hem de açabilir. Bu basitlik simetrik şifrelemeyi son derece hızlı yapar. Modern işlemcilerde AES donanım hızlandırması (Intel AES-NI, ARM Cryptography Extensions) sayesinde saniyede gigabyte'larca veri şifrelenebilir. Bu yüzden pratikte büyük veri hacimleri neredeyse her zaman simetrik algoritmalarla korunur; asimetrik kriptografi ise sadece küçük bir simetrik anahtarı güvenli biçimde taşımak (key exchange) için kullanılır. TLS'in çalışma mantığı tam da budur: handshake sırasında asimetrik yöntemle bir simetrik oturum anahtarı üzerinde anlaşılır, sonra tüm trafik simetrik şifreyle akar.

Ancak burada kritik bir yanlış anlama var: "AES kullanıyorum, o hâlde güvendeyim" cümlesi neredeyse her zaman yanlıştır. Güvenliğin büyük kısmı algoritmanın kendisinde değil, onu **hangi modda** ve **hangi parametrelerle** kullandığınızda saklıdır. Pratikteki kriptografik felaketlerin ezici çoğunluğu AES'in kırılmasından değil, yanlış mod seçiminden, tekrar eden IV'lerden (initialization vector) ve bütünlük (integrity) korumasının unutulmasından kaynaklanır. Bu makalenin asıl konusu da budur.

## AES: Blok Şifrelemenin Temeli

AES (Advanced Encryption Standard), 128 bitlik (16 byte) sabit blok boyutuyla çalışan bir **block cipher**'dır. Anahtar boyutu 128, 192 veya 256 bit olabilir. Rijndael algoritması temel alınarak standartlaştırılmıştır ve bugün için pratikte kırılamaz kabul edilir; bilinen en iyi teorik saldırılar bile brute-force'a kıyasla ihmal edilebilir bir avantaj sağlar.

Buradaki kilit nokta şudur: AES tek başına yalnızca **tek bir 16 byte'lık bloğu** şifreleyebilir. Girdi olarak 16 byte alır, anahtarla karıştırır, 16 byte çıktı verir. Aynı anahtar ve aynı girdi bloğu her zaman aynı çıktıyı üretir; yani AES deterministik bir permütasyondur. Gerçek dünyada ise 16 byte'tan çok daha büyük veriler şifrelenir: dosyalar, HTTP gövdeleri, veritabanı alanları. İşte "mod" (mode of operation) kavramı tam burada devreye girer. Mod, AES'in bu tek-blok yeteneğini keyfi uzunluktaki verilere nasıl genişleteceğimizi tanımlayan kurallar bütünüdür. Mod seçimi, gerçek güvenlik sınırının çizildiği yerdir.

## ECB: Neden Asla Kullanılmamalı

En basit mod ECB'dir (Electronic Codebook). Mantığı naif biçimde doğrudandır: veriyi 16 byte'lık bloklara böl, her bloğu bağımsız olarak aynı anahtarla şifrele, sonuçları arka arkaya ekle. Kod yazması kolay, paralelleştirmesi basit. Ama kriptografik olarak neredeyse her senaryoda hatalıdır.

### Kök neden: Determinizm örüntüyü sızdırır

AES deterministik olduğu için, aynı düz metin bloğu (plaintext block) her zaman aynı şifreli metin bloğunu (ciphertext block) üretir. ECB bu determinizmi hiçbir karıştırma olmadan tüm veriye taşır. Sonuç şudur: düz metindeki tekrar eden örüntüler, şifreli metinde de tekrar eden örüntüler olarak **görünür kalır**. Şifreleme, verinin istatistiksel yapısını gizlemek zorundadır; ECB bunu yapmaz.

Bunun klasik ve çok öğretici örneği, bitmap bir görüntünün ECB ile şifrelenmesidir. Görüntüde geniş tek renkli alanlar aynı düz metin bloklarını üretir, bu bloklar aynı şifreli bloklara dönüşür ve şifrelenmiş çıktıya baktığınızda orijinal görüntünün ana hatları hâlâ seçilebilir. Meşhur "ECB penguen" örneği tam olarak bunu gösterir: veri şifrelenmiştir ama içerik hâlâ tanınabilir.

### İstismar mantığı ve savunma

Saldırgan açısından ECB birçok kapı açar. Blok tekrarlarını gözlemleyerek yapı çıkarımı yapılabilir; örneğin bir oturum çerezinde (cookie) hangi bölümlerin sabit olduğu anlaşılabilir. Daha ciddisi, bloklar bağımsız olduğu için saldırgan blokları **kesip yapıştırabilir** (cut-and-paste / block reordering). Bir mesajın bloklarını yeniden sıralayarak veya başka bir şifreli mesajdan blok taşıyarak anlamlı manipülasyonlar üretilebilir, çünkü hiçbir bütünlük koruması ve blok-zincirleme yoktur. Ayrıca "ECB byte-at-a-time" adı verilen bir saldırıyla, saldırgan kontrol ettiği veriyi bilinmeyen bir gizli değerin önüne ekleyip blok hizalamasını manipüle ederek gizli değeri byte byte çözebilir.

Savunma açık ve nettir: **ECB'yi kullanmayın.** Modern hiçbir protokolde ECB'nin yeri yoktur. Kod incelemesinde `AES/ECB` veya `MODE_ECB` ifadesini görmek neredeyse her zaman bir bulgu olarak raporlanmalıdır. Tek istisna, tek ve rastgele bir bloğun (örneğin başka bir anahtar) şifrelenmesi gibi çok özel durumlardır ki bu bile genellikle daha güvenli alternatiflerle yapılabilir.

## CBC: Zincirleme ve IV'nin Doğuşu

CBC (Cipher Block Chaining), ECB'nin örüntü sızdırma sorununu çözmek için tasarlanmıştır. Temel fikir zincirlemedir: her düz metin bloğu, şifrelenmeden **önce** bir önceki şifreli metin blağuyla XOR'lanır. Böylece aynı düz metin bloğu bile, kendinden önceki içerik farklıysa farklı bir şifreli blok üretir. Peki ilk bloğun "önceki bloğu" yok; işte IV (initialization vector) burada devreye girer. İlk blok, rastgele bir IV ile XOR'lanır. IV, aynı anahtarla aynı mesajı iki kez şifrelediğinizde bile tamamen farklı şifreli çıktılar almanızı sağlar.

### IV'nin doğru kullanımı: Kök neden

CBC için IV'nin iki kritik özelliği olmalıdır: **öngörülemez (unpredictable)** ve mesaj başına **benzersiz** olmalı. Öngörülemezlik önemlidir çünkü saldırgan bir sonraki IV'yi tahmin edebiliyorsa "chosen-plaintext" senaryolarında seçilen düz metin saldırıları mümkün hâle gelir. TLS 1.0'ın meşhur zafiyeti tam olarak buydu: IV, bir önceki kaydın son şifreli bloğundan alınıyordu ve bu tahmin edilebilirdi. Bu, BEAST olarak bilinen saldırının temelini oluşturdu. Alınması gereken ders şudur: CBC IV'si her mesaj için kriptografik olarak güvenli bir rastgele üreteçten (CSPRNG) üretilmelidir. IV gizli değildir, şifreli metinle birlikte açıkça iletilebilir; ama tahmin edilebilir olmamalıdır.

### CBC'nin en tehlikeli tuzağı: Padding oracle

CBC blok boyutunun katı olmayan verileri şifrelemek için padding (dolgu) gerektirir; genellikle PKCS#7 kullanılır. Şifre çözme sırasında sistem padding'in geçerli olup olmadığını kontrol eder. İşte kritik nokta: eğer sistem "padding hatalı" durumunu, "padding doğru ama başka bir şey hatalı" durumundan farklı biçimde davranarak (farklı hata mesajı, farklı yanıt süresi, farklı bağlantı davranışı) belli ederse, saldırgan bir **padding oracle** elde eder.

Bu oracle'ın istismar mantığı zariftir ve öğreticidir. Saldırgan bir şifreli bloğu ele alır, bir önceki bloğun byte'larını sistematik olarak değiştirir ve sistemin "padding geçerli mi?" cevabını gözlemler. CBC'nin şifre çözme yapısı gereği, düz metnin son byte'ı, çözülen ara değer ile bir önceki şifreli bloğun XOR'una eşittir. Saldırgan önceki bloğu manipüle ederek, çözülen düz metnin son byte'ının geçerli bir padding değeri (0x01) oluşturmasını sağlayacak değeri deneme-yanılma ile bulur. Bulduğunda o byte'ın ara değerini, dolayısıyla gerçek düz metin byte'ını hesaplayabilir. Bu işlem byte byte tekrarlanarak **anahtarı hiç bilmeden tüm mesaj çözülebilir.** Padding oracle saldırıları TLS'te (POODLE, Lucky Thirteen ailesi) ve sayısız web uygulamasında gerçek ihlallere yol açmıştır.

### Savunma

CBC'nin bu tuzağının temel dersi, bütünlük korumasının şart olduğudur. Doğru savunma şudur: şifreli metni bir MAC (Message Authentication Code, örneğin HMAC) ile koruyun ve **encrypt-then-MAC** düzeninde çalışın; yani önce şifrele, sonra şifreli metnin üzerine MAC hesapla. Şifre çözerken önce MAC'i doğrula, MAC geçersizse padding'e hiç bakmadan reddet. Bu sayede saldırgan şifreli metni değiştiremez, padding oracle oluşamaz. MAC doğrulaması sabit zamanlı (constant-time) karşılaştırmayla yapılmalıdır ki timing sızıntısı olmasın. Ancak pratikte bu doğru düzeni elle kurmak hataya çok açıktır; bu yüzden modern öneri, bu işi kendi başına doğru yapan AEAD modlarına geçmektir.

## CTR: Blok Şifresini Akış Şifresine Dönüştürmek

CTR (Counter) modu farklı ve şık bir yaklaşım benimser: AES'i doğrudan veriyi şifrelemek için değil, bir **keystream** (anahtar akışı) üretmek için kullanır. Bir nonce ile bir sayacın (counter) birleşimini AES'ten geçirir, çıkan bloğu düz metinle XOR'lar. Sayaç her blok için bir artırılır, böylece uzun bir pseudo-rastgele keystream elde edilir. Bu, block cipher'ı etkin biçimde bir **stream cipher**'a dönüştürür.

CTR'nin avantajları belirgindir: padding gerektirmez (herhangi bir uzunluğu şifreler), tamamen paralelleştirilebilir (her blok bağımsız hesaplanabilir), ve rastgele erişime izin verir (bir bloğu çözmek için öncekileri çözmeye gerek yok). Bu yüzden yüksek performanslı sistemlerin ve disk şifrelemenin temelinde sıkça yer alır.

### CTR'nin ölümcül tuzağı: Nonce tekrarı

CTR modunun tek ama son derece yıkıcı kuralı vardır: **aynı anahtarla aynı nonce/sayaç kombinasyonu asla iki kez kullanılmamalıdır.** Nedenini anlamak kritik. Keystream tamamen anahtar ve sayacın fonksiyonudur; düz metne bağlı değildir. Eğer iki farklı mesajı aynı nonce'la şifrelerseniz, ikisi de **aynı keystream** ile XOR'lanır. Bu durumda saldırgan iki şifreli metni birbiriyle XOR'larsa, keystream sadeleşir ve elinde iki düz metnin birbiriyle XOR'u kalır. Bu, "two-time pad" olarak bilinen klasik felakettir; dil istatistikleri ve bilinen düz metin parçalarıyla her iki mesaj da büyük ölçüde kurtarılabilir. Anahtar hiç kırılmadan gizlilik tamamen çöker.

### İstismar ve savunma

Saldırgan açısından nonce tekrarını tespit etmek çoğu zaman şifreli metinleri gözlemlemek kadar basittir. Zayıf nonce üretimi (küçük rastgele uzayı, sayaç sıfırlama, çoklu sunucunun aynı nonce alanını paylaşması) pratikte sıkça görülür. Savunma disiplin gerektirir: nonce yönetimini merkezî ve titiz yapın. İki yaygın strateji vardır: ya kriptografik rastgele nonce kullanın (ancak yeterince geniş, tipik olarak 96 bit veya daha fazla, ki tekrar olasılığı ihmal edilebilsin), ya da monoton artan bir sayaç kullanıp bunun asla geri sarılmadığını veya çakışmadığını garanti edin. Ayrıca CTR de tek başına bütünlük sağlamaz; saldırgan şifreli metnin bir byte'ını çevirirse, çözülen düz metnin tam o konumundaki byte'ı öngörülebilir biçimde değişir (bit-flipping saldırısı). Bu yüzden CTR de mutlaka bir kimlik doğrulama katmanıyla kullanılmalıdır.

## AEAD ve GCM: Gizlilik ve Bütünlüğün Birleşimi

Şimdiye kadarki tüm modların (ECB hariç, o zaten kullanılmamalı) ortak zayıflığı ortaya çıktı: hepsi yalnızca **gizlilik** (confidentiality) sağlar, **bütünlük ve kimlik doğrulama** (integrity/authenticity) sağlamaz. Ve gördük ki bütünlük olmadan gizlilik de çoğu zaman çöküyor: padding oracle, bit-flipping, cut-and-paste. Kriptografide olgunlaşan görüş şudur: şifreleme ve kimlik doğrulama birbirinden ayrılmamalı, tek bir doğru tasarımda birleştirilmelidir. Bu birleşimin adı **AEAD**'dir: Authenticated Encryption with Associated Data (İlişkili Veriyle Kimlik Doğrulamalı Şifreleme).

AEAD üç şeyi tek işlemde yapar: veriyi şifreler, şifreli metnin değiştirilmediğini garanti eden bir **authentication tag** üretir, ve isteğe bağlı olarak **ilişkili veriyi** (associated data / AAD) korur. AAD, şifrelenmeyen ama bütünlüğü doğrulanan veridir; örneğin bir paketin başlık (header) bilgileri gibi açık kalması gereken ama kurcalanmaması gereken alanlar. Şifre çözme sırasında tag doğrulanmazsa, işlem hiçbir düz metin döndürmeden **hata verir**. Bu "ya hep ya hiç" davranışı, önceki tüm oracle saldırılarını kökten ortadan kaldırır.

### GCM'in çalışma mantığı

En yaygın AEAD modu AES-GCM'dir (Galois/Counter Mode). İki bileşeni birleştirir: gizlilik için CTR modu (yukarıda anlatılan keystream mantığı), bütünlük için ise GHASH adı verilen, Galois alanında (GF(2^128)) çalışan bir kimlik doğrulama fonksiyonu. GCM, CTR ile veriyi şifreler ve aynı zamanda hem şifreli metin hem de AAD üzerinden GHASH ile bir authentication tag hesaplar. Sonuç hızlıdır (CTR gibi paralelleşir, donanım desteğiyle çok hızlıdır) ve tek geçişte hem şifreleme hem doğrulama sağlar. TLS 1.2 ve 1.3'ün, IPsec'in ve modern protokollerin bel kemiğidir.

### GCM'in devraldığı tuzak: Nonce yine kritik

GCM, CTR üzerine kurulu olduğu için CTR'nin nonce kuralını **aynen** devralır, hatta sonuçları daha ağırdır. GCM'de bir nonce'un aynı anahtarla iki kez kullanılması iki felaketi birden getirir. Birincisi, CTR keystream'i tekrar eder ve gizlilik two-time pad ile çöker. İkincisi ve daha sinsisi: nonce tekrarı, GHASH'in bütünlük anahtarının (authentication key H) sızmasına yol açar. İki mesajın tag'lerini ve şifreli metinlerini eline geçiren saldırgan, GHASH'in cebirsel yapısından yararlanarak H değerini çözebilir. H çözüldüğünde saldırgan **kendi sahte mesajları için geçerli tag'ler üretebilir** hâle gelir; yani sadece geçmiş mesajlar değil, gelecekteki tüm bütünlük garantisi de yıkılır. Bu, "forbidden attack" olarak bilinir ve gerçek dünyada nonce'ları tekrar eden hatalı TLS sunucularında gösterilmiştir.

Bu yüzden GCM'de nonce yönetimi hayati önemdedir. GCM için standart nonce boyutu 96 bittir (12 byte) ve bu boyut özellikle önerilir çünkü GCM'in iç yapısıyla en verimli ve en güvenli biçimde çalışır. 96 bit rastgele nonce ile bile, aynı anahtar altında çok büyük sayıda (milyarlarca mesajın çok üzerinde) mesaj şifrelendiğinde çakışma (birthday bound) riski oluşmaya başlar. Bu yüzden yüksek hacimli sistemlerde iki iyi pratik vardır: ya anahtarları yeterince sık döndürün (key rotation), ya da rastgele nonce yerine sayaç-tabanlı nonce kullanıp benzersizliği deterministik olarak garanti edin. Çok yüksek mesaj hacimlerinde, tasarımı gereği nonce çakışmasına karşı daha dayanıklı olan **AES-GCM-SIV** gibi nonce-misuse-resistant AEAD modları tercih edilmelidir; bu modlar bir nonce yanlışlıkla tekrar etse bile felaketi sınırlar (tekrarın yalnızca o iki mesajın eşitliğini sızdırmasına indirger, anahtarı ifşa etmez).

### Tag doğrulama ve kesme tuzağı

GCM ile ilgili bir başka pratik hata, authentication tag'in yanlış işlenmesidir. Tag'i kısaltmak (truncation) doğrulama gücünü zayıflatır; saldırganın rastgele bir tag ile geçme olasılığını artırır, bu yüzden tam boyutlu tag (128 bit) tercih edilmelidir. Daha da kritik olanı: şifre çözme mantığı, tag doğrulaması **başarısız olduğunda çözülen düz metni asla döndürmemelidir.** Bazı hatalı implementasyonlar veriyi çözer, kullanıcıya verir, sonra tag'i kontrol eder. Bu, AEAD'nin tüm amacını boşa çıkarır; düz metin bir kez sızdıktan sonra bütünlük kontrolünün geç gelmesi anlamsızdır. Doğru davranış: önce doğrula, geçmezse hiçbir şey döndürmeden reddet.

## Yaygın Hatalar

Bu konudaki hataların çoğu birbirini tekrar eden birkaç kök nedene dayanır ve bir arada görmek öğreticidir:

- **ECB kullanmak.** Genellikle "en basit mod" olduğu için varsayılan seçilir; örüntü sızdırır ve kullanılmamalıdır.
- **Statik veya sabit kodlanmış (hardcoded) IV/nonce.** Kaynak kodda gömülü, sıfır, ya da her mesajda aynı olan IV; CBC'de öngörülebilirlik, CTR/GCM'de tekrar felaketi demektir.
- **Rastgele olmayan IV üreteci.** `rand()` gibi kriptografik olmayan üreteçler veya zaman damgası tabanlı IV'ler; öngörülebilir ve tahmin edilebilir olur. Her zaman CSPRNG kullanılmalı.
- **Bütünlüğü unutmak.** Sadece gizlilik sağlayan bir mod (CBC, CTR) kullanıp MAC eklememek; bit-flipping ve oracle saldırılarına açık kapı bırakır.
- **Yanlış kompozisyon.** MAC-then-encrypt veya encrypt-and-MAC gibi kırılgan düzenler; doğru olan encrypt-then-MAC'tir veya daha iyisi hazır bir AEAD kullanmaktır.
- **Nonce'u anahtarla birlikte yeniden kullanmak.** Özellikle çoklu sunucu/instance'ın nonce alanını koordinasyonsuz paylaşması, sayaç sıfırlanması, veya sanal makine anlık görüntüsünden (snapshot) geri dönme durumlarında.
- **Sabit zamanlı olmayan karşılaştırma.** MAC/tag doğrulamasını normal string karşılaştırmasıyla yapmak, timing side-channel sızdırır.
- **Anahtar ve IV'yi karıştırmak.** IV'yi gizli sanıp gizlemek gereksiz ve bazen zararlıdır; asıl gizli tutulması gereken anahtardır.
- **Kendi kriptografini yazmak.** Modları elle birleştirip özgün bir şema kurmak; neredeyse her zaman bir yerde tuzağa düşer.

## En İyi Pratikler

Somut ve savunulabilir bir yaklaşım için özet öneriler:

**Varsayılan olarak AEAD seçin.** Yeni bir tasarımda tercih AES-GCM veya ChaCha20-Poly1305 olmalı. ChaCha20-Poly1305, AES donanım hızlandırması olmayan ortamlarda (bazı mobil ve gömülü sistemler) AES-GCM'e göre daha hızlı ve yan-kanal saldırılarına doğası gereği daha dirençli bir AEAD alternatifidir. İkisi de aynı bütünlük garantilerini verir.

**Nonce'u disiplinli yönetin.** Nonce üretimini tek bir merkezî, iyi test edilmiş bileşene toplayın. Rastgele nonce kullanıyorsanız CSPRNG'den ve yeterli genişlikte üretin; sayaç kullanıyorsanız benzersizliğini kalıcı olarak garanti edin. Aynı anahtar altında nonce çakışması riskini birthday bound hesabıyla değerlendirin ve gerekiyorsa anahtar rotasyonuna geçin. Çok yüksek hacimde veya nonce yönetimini garanti edemediğiniz durumlarda AES-GCM-SIV gibi nonce-misuse-resistant modları düşünün.

**Bütünlüğü hiçbir zaman ihmal etmeyin.** Eğer bir sebeple AEAD kullanamıyorsanız, encrypt-then-MAC düzenini sabit zamanlı doğrulamayla uygulayın. Ama bunu elle kurmaktansa hazır AEAD kullanmak neredeyse her zaman daha güvenlidir.

**Anahtar yönetimini ciddiye alın.** Şifrelemenin gücü anahtarın gizliliği kadardır. Anahtarları güvenli bir kaynaktan (KMS, HSM, ya da uygun bir secret store) alın, koda gömmeyin, düzenli olarak döndürün. Farklı amaçlar için farklı anahtar kullanın; şifreleme anahtarını MAC anahtarından ayırın. Anahtar türetme için uygun bir KDF (örneğin HKDF) kullanın.

**Anahtar boyutunu bağlama göre seçin.** AES-128 bugün için güvenlidir ve çoğu senaryo için yeterlidir; AES-256, post-quantum tehdit modeli veya çok uzun ömürlü veriler için ek marj sağlar. Fark performansta küçük, güvenlik marjında ise anlamlıdır.

**Olgun kütüphaneler kullanın.** Kendi mod kompozisyonunuzu yazmayın. libsodium gibi, güvenli varsayılanları zorlayan ve yanlış kullanımı zorlaştıran yüksek seviyeli kütüphaneler tercih edilmelidir. Bu kütüphaneler nonce yönetimi, tag doğrulama ve sabit zamanlı işlemleri sizin yerinize doğru yapar.

**Kod incelemesinde kırmızı bayrakları arayın.** `ECB`, sabit IV/nonce, `Math.random`/`rand()` ile IV üretimi, MAC olmayan CBC/CTR, ve tag doğrulamadan önce düz metin döndüren kod yolları; bunlar sistematik olarak taranmalı ve bulgu olarak işlenmelidir.

## Sonuç

Simetrik şifrelemede güvenliğin kalbi algoritmada değil, kullanımdadır. AES sağlamdır; kırılan neredeyse hiçbir zaman AES olmaz. Kırılan; tekrar eden nonce'lar, öngörülebilir IV'ler, unutulan bütünlük kontrolleri ve yanlış mod seçimleridir. Modların evrimi aslında tek bir dersin tarihidir: gizlilik tek başına yeterli değildir, bütünlükle birleşmelidir. Bu dersin bugünkü kristalleşmiş hâli AEAD'dir. Pratik özet basittir: bir AEAD modu (AES-GCM ya da ChaCha20-Poly1305) seçin, nonce'ları asla tekrar etmeyin, anahtarları düzgün yönetin, ve olgun kütüphanelere güvenin. Bu dört kuralı tutarsanız, simetrik şifrelemenin tarihindeki felaketlerin ezici çoğunluğundan zaten kaçınmış olursunuz.
