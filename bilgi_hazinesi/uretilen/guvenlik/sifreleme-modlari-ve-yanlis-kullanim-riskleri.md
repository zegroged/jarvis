# Şifreleme Modları ve Yanlış Kullanım Riskleri (ECB/CBC/CTR/GCM, IV/Nonce Yönetimi, AEAD)

## Giriş: Neden "Simetrik Şifreleme" Başlığı Yetmez

AES gibi bir blok şifresi (block cipher), tek başına yalnızca sabit uzunlukta bir blok (AES için 128 bit) veriyi şifreler. Gerçek dünyada şifrelenecek veri neredeyse hiçbir zaman tam olarak bu boyutta değildir — bir HTTP isteği, bir dosya, bir JSON belgesi genellikle kilobaytlarca, megabaytlarca uzundur. Bu uzun veriyi blok blok şifrelemek için kullanılan yönteme **çalışma modu (mode of operation)** denir.

İşte tam bu noktada, "algoritma güçlü ama uygulama kırılgan" paradoksu ortaya çıkar: AES algoritmasının kendisi (anahtar kurtarma anlamında) pratikte kırılmamıştır, ama yanlış mod seçimi, tekrar eden bir IV (initialization vector) ya da nonce (number used once), ya da bütünlük korumasının (integrity/authentication) hiç olmaması, sistemi tamamen kırılabilir hale getirir. Bu makalenin amacı, "Simetrik Şifreleme" gibi genel bir başlığın atladığı bu **pratik, operasyonel katmanı** derinlemesine incelemektir — çünkü gerçek dünyadaki kriptografik zafiyetlerin büyük çoğunluğu algoritmadan değil, modun ve nonce yönetiminin yanlış kullanımından kaynaklanır.

Bir savunmacı/mühendis için doğru soru genelde "AES mi RC4 mü?" değil, "bu AES hangi modda çalışıyor, IV nasıl üretiliyor, ve bütünlük kontrolü var mı?" sorusudur.

---

## Kavramsal Temel: Blok Şifresi Neden Tek Başına Yetmez

Bir blok şifresi, sabit bir anahtarla sabit boyutlu bir bloğu sabit boyutlu bir bloğa dönüştüren **deterministik bir permütasyondur**. Aynı anahtar ve aynı girdi blok her zaman aynı çıktı bloğunu üretir. Bu determinizm, algoritmanın matematiksel gücü açısından bir sorun değildir, ama çok bloklu veriyi şifrelerken kritik bir tasarım sorusu doğurur:

- Bloklar birbirinden bağımsız mı işlenecek (paralellik, ama örüntü sızıntısı riski)?
- Her blok bir önceki bloğa mı bağlı olacak (örüntü gizlenir, ama paralellik ve hata toleransı azalır)?
- Blok şifresi bir akış şifresine (stream cipher) mi dönüştürülecek (sayaç tabanlı yaklaşım)?

Bu sorulara verilen farklı cevaplar, farklı **çalışma modlarını** oluşturur: ECB, CBC, CTR, GCM vb. Her mod, kendi güvenlik varsayımlarını ve kendi yanlış kullanım (misuse) risklerini beraberinde getirir.

---

## ECB (Electronic Codebook): "Neden Asla Kullanılmamalı" Sorusunun Kök Nedeni

### Çalışma Mantığı
ECB modunda, her düz metin (plaintext) bloğu, birbirinden tamamen bağımsız olarak aynı anahtarla şifrelenir. Blok 1, blok 2'den habersizdir; aralarında hiçbir zincirleme (chaining) yoktur.

### Kök Neden / Neden Kırılgan
Blok şifresinin determinizm özelliğini hatırlayın: aynı girdi her zaman aynı çıktıyı üretir. ECB modunda bu özellik doğrudan şifreli metne (ciphertext) yansır: **aynı düz metin bloğu, aynı anahtarla, her zaman aynı şifreli metin bloğunu üretir.** Bu, kriptografide "semantic security" (anlamsal güvenlik) kavramının ihlalidir — bir şifreleme şemasının güvenli sayılması için, şifreli metnin düz metin hakkında (uzunluk dışında) hiçbir örüntü bilgisi sızdırmaması gerekir. ECB bunu tam olarak ihlal eder.

En bilinen görsel kanıt "ECB Penguin" örneğidir: bir bitmap görüntü ECB modunda şifrelendiğinde, görüntüdeki tekrarlayan renk/desen blokları şifreli halde de aynı kalır, böylece penguen silueti şifreli veride bile görünür kalır. Bu, ECB'nin sadece teorik değil, doğrudan gözle görülebilir bir zafiyet olduğunu gösterir.

### Tespit
- Kod incelemesinde `AES/ECB/...` (Java Cipher string'i), `MODE_ECB`, veya IV/nonce parametresi **hiç almayan** bir şifreleme çağrısı görürseniz, bu doğrudan bir bulgudur.
- Ağ trafiğinde veya disk üzerindeki şifreli veride, aynı byte dizisinin tekrarlandığı blok hizalı örüntüler (örneğin sabit başlıklı dosya formatlarında) ECB kullanımına işaret edebilir.
- Statik analiz araçları (semgrep, bandit, kod tabanlı grep kuralları) `ECB` string'ini API çağrılarında aramak için basit ama etkilidir.

### Savunma
- ECB'yi hiçbir zaman kullanmayın; kütüphane varsayılanlarını kontrol edin (bazı eski API'lerde varsayılan mod ECB'dir).
- Kod incelemesi ve statik analiz kurallarına "ECB modu kullanımı yasak" kuralı ekleyin.
- Mümkünse düşük seviyeli mod seçimini geliştiriciye bırakmayan, yalnızca güvenli/AEAD modlarını sunan yüksek seviyeli kriptografi kütüphaneleri (libsodium gibi "misuse-resistant" tasarımlar) tercih edin.

---

## CBC (Cipher Block Chaining): Zincirleme ile Örüntü Gizleme, Yeni Riskler

### Çalışma Mantığı
CBC modunda her düz metin bloğu, şifrelenmeden önce bir önceki şifreli metin bloğuyla XOR'lanır. İlk blok için "önceki şifreli blok" olmadığından, bir **IV (initialization vector)** kullanılır — rastgele veya en azından öngörülemez bir başlangıç bloğu.

Matematiksel olarak: `C_i = Enc(K, P_i XOR C_{i-1})`, ve `C_0 = IV`.

Bu zincirleme sayesinde, aynı düz metin bloğu farklı konumlarda farklı şifreli metin üretir (çünkü her blok kendinden önceki şifreli bloğa bağlıdır) — ECB'nin örüntü sızıntısı sorunu büyük ölçüde çözülür.

### Kök Neden / Yanlış Kullanım Riskleri

**1. IV Tekrarı veya Öngörülebilirlik**
CBC güvenliğinin temel varsayımı, IV'nin **öngörülemez** olmasıdır (rastgele veya en azından saldırganın önceden tahmin edemeyeceği bir değer). Eğer IV sabitse (örneğin kodda hard-code edilmiş) veya öngörülebilirse (örneğin bir önceki mesajın son bloğu, ya da artan bir sayaç saldırgan tarafından tahmin edilebiliyorsa), aynı düz metinle başlayan mesajlar arasında ilişki sızdırılabilir. Bu, özellikle "chosen-plaintext" saldırı senaryolarında (saldırganın şifrelenecek metni kısmen kontrol edebildiği durumlarda) ciddi bir zafiyettir — TLS'teki tarihsel BEAST saldırısının kök nedeni de öngörülebilir/zincirlenmiş IV kullanımıydı.

**2. Padding Oracle Saldırıları**
CBC, blok boyutuna tam bölünmeyen veriler için padding (dolgu) gerektirir (örneğin PKCS#7 padding). Eğer şifre çözme (decryption) tarafı, "padding geçerli mi değil mi" bilgisini bir şekilde dışarı sızdırıyorsa (farklı hata mesajı, farklı yanıt süresi, farklı HTTP durum kodu), saldırgan bu bilgiyi kullanarak düz metni **hiç anahtarı bilmeden**, blok blok, byte byte kurtarabilir. Bu saldırı sınıfına **padding oracle** denir ve pratikte tam çalışan araçları vardır (POODLE, Vaudenay'nin orijinal saldırısı gibi kavramlar bu ailededir).

Kök neden burada kriptografik değil, **bilgi sızıntısı (side-channel)** kaynaklıdır: sistem, "padding hatası" ile "MAC/bütünlük hatası"nı veya "başarılı çözme"yi ayırt edilebilir şekilde dışarı yansıtıyorsa, oracle oluşur.

**3. Bütünlük Eksikliği (Malleability)**
CBC modu tek başına yalnızca **gizlilik (confidentiality)** sağlar, **bütünlük (integrity)** veya **kimlik doğrulama (authenticity)** sağlamaz. Bir saldırgan, şifreli metnin bloklarını değiştirebilir (bit-flipping) ve bu değişiklik, çözüldüğünde öngörülebilir şekilde düz metnin belirli bitlerini değiştirir — çünkü XOR işlemi doğrusaldır. Sistem bu değişikliği fark etmeden kabul ederse, saldırgan mesajın içeriğini kontrollü biçimde manipüle edebilir.

### Tespit
- Kod incelemesinde IV'nin nasıl üretildiğine bakın: sabit bir string mi, sıfır blok mu (`IV = 00000...`), yoksa kriptografik olarak güvenli rastgele üreteçten mi geliyor?
- Hata işleme yollarını inceleyin: şifre çözme başarısız olduğunda "padding hatası" ile "MAC doğrulama hatası" farklı mesaj/durum kodu/yanıt süresi üretiyor mu? Üretiyorsa padding oracle riski vardır.
- CBC kullanılan yerlerde ayrı bir MAC (HMAC gibi) uygulanıp uygulanmadığını, uygulanmışsa **encrypt-then-MAC** mi yoksa **MAC-then-encrypt** mi olduğunu kontrol edin (sıralama hatası da bir zafiyet kaynağıdır — doğru ve genel kabul gören yaklaşım encrypt-then-MAC'tir).

### Savunma
- IV her mesaj için kriptografik olarak güvenli bir rastgele sayı üretecinden (CSPRNG) türetilmeli, asla sabit veya tahmin edilebilir olmamalıdır.
- Padding hatası ile bütünlük hatası arasında **ayırt edilemez** bir hata yanıtı verin (tek tip genel hata, sabit zamanlı karşılaştırma — constant-time comparison).
- CBC'yi çıplak kullanmak yerine, mümkünse doğrudan bir AEAD moduna (GCM gibi) geçin; geçilemiyorsa mutlaka encrypt-then-MAC deseni uygulayın.

---

## CTR (Counter Mode): Blok Şifresini Akış Şifresine Çevirmek

### Çalışma Mantığı
CTR modu, blok şifresini bir **akış şifresi (stream cipher)** gibi davranacak şekilde kullanır. Şifrelenecek asıl veri değil, bir **sayaç (counter)** değeri şifrelenir; ortaya çıkan çıktı (keystream) düz metinle XOR'lanır: `C_i = P_i XOR Enc(K, Nonce || Counter_i)`.

Bu yaklaşımın avantajları: paralelleştirilebilir (her blok bağımsız hesaplanabilir), padding gerektirmez (herhangi bir uzunlukta veri XOR'lanabilir), ve şifre çözme de aynı keystream'i üretip XOR'lamaktan ibarettir (decrypt işlemi de encrypt fonksiyonunu kullanır, ayrı bir decrypt fonksiyonuna gerek yoktur).

### Kök Neden / Yanlış Kullanım Riski: Nonce/Counter Tekrarı — Kritik Zafiyet

CTR modunun güvenliği, **her mesaj için (nonce, counter) çiftinin asla tekrar etmemesine** dayanır. Eğer aynı anahtarla iki farklı mesaj, aynı nonce (veya aynı nonce+counter kombinasyonu) ile şifrelenirse, aynı keystream bloğu iki kez üretilir. Bu durumda:

`C1 = P1 XOR KS` ve `C2 = P2 XOR KS`

İki şifreli metni XOR'larsanız: `C1 XOR C2 = P1 XOR P2` — keystream tamamen iptal olur ve saldırgan, iki düz metnin XOR'unu elde eder. Düz metinlerden biri hakkında herhangi bir bilgi (örneğin bilinen bir başlık, tahmin edilebilir bir format) varsa, diğer düz metin doğrudan kurtarılabilir. Bu, klasik "two-time pad" zafiyetidir ve tarihte gerçek kriptografik sistemleri (örneğin bazı WEP ve hatta bazı devlet düzeyinde şifreleme sistemlerinin) kırmış olan kök nedendir.

Bu, CTR modunu **nonce yönetimi konusunda en hassas** modlardan biri yapar: anahtar aynı kaldığı sürece, nonce'un **hiçbir zaman** tekrar etmemesi gerekir — rastgelelik burada yeterli değildir, **benzersizlik (uniqueness)** garanti edilmelidir. (Rastgele üretilen nonce'larda "doğum günü paradoksu" nedeniyle yeterince çok mesaj şifrelendiğinde çakışma olasılığı artar; bu yüzden CTR'de genelde sayaç tabanlı, garantili benzersiz nonce üretimi tercih edilir.)

Ayrıca CTR, CBC gibi tek başına bütünlük/kimlik doğrulama sağlamaz — bu da onu bit-flipping saldırılarına açık bırakır (CBC'dekiyle benzer mantık, hatta CTR'de XOR doğrudan olduğu için manipülasyon daha da "temiz"dir).

### Tespit
- Kod incelemesinde nonce/counter üretim mantığını izleyin: her şifreleme çağrısında sıfırdan mı başlıyor, yoksa global/kalıcı bir sayaç mı kullanılıyor?
- Anahtar yeniden kullanımı (key reuse) olan sistemlerde, nonce'un mesajlar arasında çakışıp çakışmadığını loglardan veya üretim mantığından doğrulayın.
- Dağıtık sistemlerde (birden fazla sunucu aynı anahtarı paylaşıyorsa) her düğümün bağımsız/çakışmayan bir nonce alanı kullandığından emin olun (örneğin sunucu kimliğini nonce'un bir parçası yapmak).

### Savunma
- Nonce üretimi için garantili benzersizlik sağlayan bir mekanizma kullanın (kalıcı, izlenen sayaç; veya anahtar başına yeterince geniş rastgele nonce alanı).
- CTR'yi çıplak kullanmak yerine AEAD modlarına (özellikle GCM, CTR'nin kimlik doğrulamalı versiyonu gibi düşünülebilir) yönelin.
- Anahtar rotasyon politikası uygulayın: bir anahtarla şifrelenebilecek mesaj sayısına/veri hacmine üst sınır koyun, böylece nonce alanının tükenme/çakışma riski azalır.

---

## GCM (Galois/Counter Mode) ve AEAD Kavramı

### AEAD Nedir, Neden Önemlidir
**AEAD (Authenticated Encryption with Associated Data)**, bir şifreleme modunun hem **gizlilik** hem **bütünlük/kimlik doğrulama** sağlamasıdır — ayrıca şifrelenmeyen ama kimliği doğrulanması gereken ek veri (associated data — örneğin bir paket başlığı) için de destek sunar. CBC+ayrı-HMAC gibi "elle birleştirilmiş" yaklaşımların (ve bunların sıralama hatalarının) yerini, tek, bütünleşik, doğru sırayı garanti eden bir yapı alır.

GCM, CTR modunun kimlik doğrulamalı bir versiyonu olarak düşünülebilir: veri CTR moduna benzer şekilde şifrelenir, ayrıca Galois alanında (GF(2^128)) bir çarpma işlemiyle bir **kimlik doğrulama etiketi (authentication tag)** hesaplanır. Şifre çözme tarafında bu etiket doğrulanmadan düz metin kabul edilmez — bu, CBC'nin bit-flipping ve padding oracle sorununu kökten çözer.

### Kök Neden / GCM'e Özgü Kritik Risk: Nonce Tekrarının Felaket Sonucu

GCM, CTR temelli olduğu için **aynı nonce tekrarı riskini miras alır**, ama GCM'de bu risk daha da ağırdır çünkü nonce tekrarı yalnızca keystream'in XOR ile iptal olmasına değil, aynı zamanda **kimlik doğrulama anahtarının (authentication subkey, "H") kurtarılabilmesine** de yol açabilir. Bir kez aynı nonce ile iki mesaj gözlemlendiğinde, saldırgan GCM'in kimlik doğrulama mekanizmasının matematiksel yapısını (polinom değerlendirmesi) kullanarak "H" değerini çözebilir ve bundan sonra **o anahtarla şifrelenen herhangi bir mesaj için geçerli sahte etiketler üretebilir** — yani hem gizlilik hem de kimlik doğrulama aynı anda çöker. Bu, GCM'i "yanlış kullanıldığında en pahalıya mal olan" modlardan biri yapar: nonce tekrarı GCM'de CTR'den bile daha yıkıcıdır.

Bu yüzden GCM kullanılan sistemlerde, standart 96 bitlik (12 bayt) nonce'un **anahtar başına asla tekrarlanmaması** kritik bir gereksinimdir. Rastgele üretilen 96 bit nonce'larda, doğum günü paradoksu nedeniyle belirli bir mesaj sayısından sonra çakışma olasılığı pratik risk seviyesine ulaşır — bu yüzden çoğu ciddi rehber, tek bir anahtarla şifrelenebilecek mesaj sayısına ve rastgele nonce kullanımına temkinli sınırlar koyulmasını önerir; sayaç tabanlı (deterministik, garantili benzersiz) nonce üretimi genelde daha güvenli kabul edilir.

### Diğer Yaygın GCM Hataları
- **Etiket kesme (tag truncation):** Kimlik doğrulama etiketinin çok kısa tutulması (bazı yanlış yapılandırmalarda), saldırganın kaba kuvvetle (brute-force) sahte etiket bulma şansını artırır.
- **Etiket doğrulamasını atlamak:** Performans veya "hata toleransı" gerekçesiyle etiket doğrulama başarısız olduğunda düz metni yine de kullanan uygulamalar — bu, AEAD'in tüm amacını ortadan kaldırır.
- **Aynı anahtarı hem GCM hem başka bir modda kullanmak:** Anahtar/nonce alanı ayrımı net değilse çapraz kullanım riskleri doğar.

### Tespit
- Kod incelemesinde nonce üretiminin kaynağını izleyin: her şifreleme öncesi taze mi üretiliyor, kalıcı bir sayaç mı, yoksa yanlışlıkla sabit/varsayılan bir değer mi kullanılıyor?
- Şifre çözme fonksiyonunun, kimlik doğrulama hatası durumunda **hiçbir düz metin baytı döndürmediğini** (exception/hata ile derhal durduğunu) doğrulayın.
- Log/telemetri sistemlerinde aynı (anahtar, nonce) çiftinin birden fazla kayıtta göründüğü anomalileri aramak (mümkünse) erken uyarı sağlar.
- Kütüphane/SDK sürümlerinde bilinen nonce yönetimi zafiyeti olup olmadığını (genel olarak, spesifik sürüm/CVE iddiasında bulunmadan) değişiklik günlüklerinden takip edin.

### Savunma
- Nonce üretimi için deterministik, garantili-benzersiz bir sayaç mekanizması tercih edin; rastgele nonce kullanılıyorsa anahtar başına mesaj sayısını güvenli sınırlar içinde tutun.
- Anahtar rotasyonunu otomatikleştirin: belirli bir veri hacmi/mesaj sayısı/süre sonunda anahtar değiştirilsin (bkz. anahtar yönetimi konuları — KMS/HSM entegrasyonu).
- Mümkünse **nonce yanlış kullanımına dayanıklı (misuse-resistant)** AEAD modlarını değerlendirin — bu tür modlar, nonce tekrarı durumunda bile hasarı sınırlamak üzere tasarlanmıştır (klasik GCM bu sınıfta değildir, bu yüzden nonce disiplinine tam bağımlıdır).
- Şifre çözme başarısız olduğunda uygulama mantığının **hiçbir koşulda** kısmi/doğrulanmamış düz metni işlemediğinden emin olun.

---

## Modlar Arası Karşılaştırma: Mühendislik Kararı

| Mod | Gizlilik | Bütünlük/Auth | Paralellik | Ana Risk |
|---|---|---|---|---|
| ECB | Zayıf (örüntü sızdırır) | Yok | Var | Determinizm → örüntü sızıntısı |
| CBC | İyi (doğru IV ile) | Yok (ayrı MAC şart) | Şifrelemede yok, çözmede var | IV öngörülebilirliği, padding oracle, malleability |
| CTR | İyi (nonce benzersizse) | Yok | Var | Nonce/counter tekrarı → keystream iptali |
| GCM | İyi | Var (AEAD) | Var | Nonce tekrarı → auth key kurtarma (çift kırılma) |

Bu tablo, "hangi modu seçmeliyim" sorusunun cevabının aslında "hangi garantilere ihtiyacım var ve nonce/IV yönetimini ne kadar güvenilir yapabilirim" sorusuna indirgendiğini gösterir. Modern rehberler neredeyse evrensel olarak AEAD modlarını (GCM veya benzeri) varsayılan seçim olarak önerir, çünkü bütünlük garantisini "sonradan eklenen" bir katman olmaktan çıkarıp tasarımın merkezine koyar.

---

## Yaygın Hatalar Özeti (Kod İncelemesi Kontrol Listesi)

1. **Mod seçiminde ECB'nin varsayılan/farkında olmadan seçilmesi** — bazı eski API'lerde (özellikle bazı dillerin standart kütüphanelerinde) mod belirtilmezse ECB varsayılan olabilir.
2. **IV/nonce'un sabit kodlanması (hard-code)** — genelde "çalışıyor" görünür çünkü testler tutarlıdır, ama üretimde ciddi risktir.
3. **IV/nonce'un anahtarla birlikte yeniden kullanılması** — özellikle anahtar rotasyonu olmayan uzun ömürlü sistemlerde.
4. **Bütünlük kontrolünün olmaması veya yanlış sırada uygulanması** (MAC-then-encrypt yerine encrypt-then-MAC tercih edilmeli, ya da doğrudan AEAD kullanılmalı).
5. **Şifre çözme hatalarının ayırt edilebilir olması** (padding oracle'a zemin hazırlar) — timing, hata mesajı, veya durum kodu farkı.
6. **Kimlik doğrulama etiketi doğrulanmadan düz metnin kullanılması** ("fail open" davranışı — hata durumunda yine de devam etmek).
7. **Anahtar başına veri hacmi/mesaj sayısı sınırının izlenmemesi** — nonce alanı tükenmesi/çakışma olasılığının artmasına yol açar.
8. **Aynı anahtar-nonce çiftinin dağıtık sistemde birden fazla düğüm tarafından bağımsız üretilmesi** (koordinasyon eksikliği).

## Sonuç: Savunmacı Bakış Açısı

Bir güvenlik mühendisi için bu konudaki pratik disiplin şu şekilde özetlenebilir: mod seçimini asla "işe yarıyor" testine göre değil, tehdit modeline göre yapın; IV/nonce üretimini rastgeleliğe değil **garantili benzersizliğe** dayandırın; bütünlük korumasını sona eklenen bir özellik değil, tasarımın ayrılmaz parçası (AEAD) olarak görün; ve kod incelemelerinde/statik analizde yukarıdaki kontrol listesini sistematik olarak arayın. Kriptografik algoritmanın matematiksel gücü, çevresindeki mod ve nonce disiplini kadar değerlidir — zincirin en zayıf halkası çoğu zaman algoritma değil, onun etrafındaki mühendislik kararlarıdır.
