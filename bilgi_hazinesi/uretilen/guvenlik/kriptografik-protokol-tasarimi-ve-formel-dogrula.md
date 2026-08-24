# Kriptografik Protokol Tasarımı ve Formel Doğrulama

## Giriş ve Kapsam

Kriptografik ilkelciler (primitives) - AES, SHA-256, Curve25519, RSA - tek başlarına güvenli iletişim sağlamaz. Bunları bir araya getiren, taraflar arasında hangi mesajın hangi sırayla, hangi anahtarla ve hangi doğrulamalarla değiştirileceğini tanımlayan **protokoller** güvenliğin gerçek belirleyicisidir. Tarihsel olarak protokol seviyesindeki hatalar, ilkelcilerin kendisindeki matematiksel kırılmalardan çok daha sık ve yıkıcı olmuştur.

Bu makale, TLS'in ötesinde iki kritik alanı kapsar: (1) **uçtan uca şifreleme (end-to-end encryption, E2EE)** mesajlaşma protokollerinin tasarım ilkeleri - özellikle Noise Protocol Framework ve Signal'in Double Ratchet algoritması; (2) protokollerin matematiksel olarak kanıtlanması için **formel doğrulama (formal verification)** araçları - Tamarin Prover ve ProVerif. Amaç, mekanizmayı derinlemesine anlamak ve savunma/tespit perspektifi kazanmaktır.

## Bölüm 1: Neden Protokol Tasarımı Zordur?

### Tehdit Modeli: Dolev-Yao Saldırganı

Protokol güvenliğinde standart tehdit modeli **Dolev-Yao** modelidir. Bu modelde saldırgan, ağdaki tüm mesajları okuyabilir, silebilir, değiştirebilir, yeniden gönderebilir (replay) ve kendi mesajlarını enjekte edebilir. Yani saldırgan aslında **ağın kendisidir**. Ancak kriptografiyi "kutu" olarak kabul eder: doğru anahtar olmadan şifreli metni çözemez, hash'i tersine çeviremez. Bu, "kriptografi kusursuz olsa bile protokol yine de kırılabilir mi?" sorusunu sormamızı sağlar - ki cevap sıklıkla "evet"tir.

### Kök Neden: Kombinatoryal Karmaşıklık

Protokoller eşzamanlı (concurrent) çalışır; saldırgan farklı oturumları (sessions) birbirine karıştırabilir. Bir tarafın "bu mesaj Alice'ten geldi" varsayımı, aslında saldırganın başka bir oturumdan aldığı mesajı yeniden yönlendirmesi olabilir. İnsan zihni, aynı anda çalışan sonsuz sayıda oturumun tüm olası mesaj sıralamalarını (interleavings) takip edemez. Bu yüzden formel doğrulama vazgeçilmezdir.

Klasik örnek **Needham-Schroeder** açık anahtar protokolüdür: 1978'de yayınlandı, 17 yıl sonra Gavin Lowe tarafından bir **man-in-the-middle** açığı bulundu (Lowe attack). Saldırgan, meşru bir tarafın kendisiyle başlattığı oturumu, üçüncü bir tarafla eşleştirerek kimlik taklidi yapabiliyordu. Lowe bu açığı FDR adlı bir formel doğrulama aracıyla buldu - bu, alanın dönüm noktasıydı.

## Bölüm 2: Modern Güvenlik Hedefleri

E2EE mesajlaşma protokolleri klasik "gizlilik + kimlik doğrulama"nın ötesinde hedefler güder:

- **Confidentiality (Gizlilik):** Yalnızca hedef taraf içeriği okuyabilir.
- **Authentication (Kimlik doğrulama):** Mesajın gerçekten iddia edilen taraftan geldiği garanti edilir.
- **Forward Secrecy (İleri gizlilik, FS):** Uzun ömürlü anahtar bir gün ele geçirilse bile, geçmiş oturumlara ait şifreli trafik çözülemez. Her oturum için geçici (ephemeral) anahtarlar kullanılması gerekir.
- **Post-Compromise Security (PCS / "self-healing"):** Bir cihazın anahtar durumu (state) tamamen ele geçirildikten sonra bile, taraflar yeni mesaj alışverişiyle güvenliği **geri kazanabilir**; saldırgan pasifse belli bir noktadan sonra dışarıda kalır. Double Ratchet'in getirdiği en önemli yeniliktir.
- **Deniability (İnkar edilebilirlik):** Mesajları imzalamak yerine simetrik MAC kullanılarak, hiçbir tarafın üçüncü kişilere "bu mesajı kesinlikle o gönderdi" diye matematiksel kanıt sunamaması. Signal bunu bilinçli olarak hedefler.

## Bölüm 3: Noise Protocol Framework

### Tanım

Noise (Trevor Perrin tarafından tasarlandı), sıfırdan güvenli bir handshake protokolü yazmak yerine, **iyi tanımlanmış yapı taşlarından güvenli protokoller üretmenizi** sağlayan bir çerçevedir. WireGuard VPN, WhatsApp'ın istemci-sunucu katmanı ve birçok modern sistem Noise tabanlıdır.

### Çalışma Mantığı: Handshake Patterns

Noise'ın kalbi, **token dizileriyle** ifade edilen handshake pattern'lardır. Temel token'lar:

- `e` : geçici (ephemeral) public key gönder
- `s` : statik (static/uzun ömürlü) public key gönder
- `ee`, `es`, `se`, `ss` : ilgili anahtar çiftleri arasında **Diffie-Hellman (DH)** işlemi yap

Her DH işleminin sonucu, çalışan bir **hash zincirine (chaining key)** karıştırılır (`MixKey`, `MixHash`). Handshake ilerledikçe, önceki tüm token'ların katkısı bu zincirde birikir. Sonunda "transport keys" (asıl trafik anahtarları) türetilir.

Pattern isimleri iki harften oluşur ve ilk harf başlatanın (initiator), ikincisi cevaplayanın (responder) statik anahtarının nasıl doğrulandığını belirtir:

- **N**: statik anahtar yok (anonim)
- **K**: statik anahtar önceden biliniyor (known)
- **X**: statik anahtar handshake sırasında iletiliyor (transmitted)

Örneğin **Noise_XX**, her iki tarafın da statik anahtarını handshake sırasında birbirine ilettiği, karşılıklı kimlik doğrulamalı, en yaygın kullanılan mutual-auth pattern'dır. **Noise_IK** (WhatsApp'ta kullanılır) ise başlatanın, cevaplayanın statik anahtarını önceden bildiği senaryodur - böylece daha az round-trip ile 0-RTT'ye yakın bağlantı sağlanır.

### Örnek: Noise_XX Akışı (kavramsal)

```
-> e
<- e, ee, s, es
-> s, se
```

1. Başlatan geçici anahtarını (`e`) gönderir.
2. Cevaplayan kendi `e`'sini gönderir, `ee` DH'ini yapar (ileri gizlilik başlar), statik anahtarını (`s`) gönderir ve `es` DH'iyle onu doğrular.
3. Başlatan kendi statik anahtarını gönderir ve `se` ile doğrulanır.

Bu noktada her iki taraf da simetrik transport anahtarlarına sahiptir ve trafik şifrelenir. Noise'ın gücü, bu pattern'ların formel olarak analiz edilmiş olması ve mühendisin "hangi DH'i unuttum?" gibi hatalar yapmasını engellemesidir.

### Yaygın Hatalar

- **Yanlış pattern seçimi:** İhtiyaç mutual-auth iken `Noise_N` gibi anonim pattern seçmek, kimlik doğrulamayı tamamen ortadan kaldırır.
- **Nonce yönetimi:** Transport aşamasında her mesaj için nonce'un tekrarsız artması gerekir; nonce tekrarı AEAD güvenliğini (ör. ChaCha20-Poly1305) tamamen çökertir.
- **Prologue/Pre-shared key'in kimlik doğrulama katkısını ihmal etmek.**

## Bölüm 4: Signal ve Double Ratchet

### X3DH: İlk Anahtar Anlaşması

Signal oturumu **X3DH (Extended Triple Diffie-Hellman)** ile başlar. Sorun şudur: mesajlaşmada karşı taraf çevrimdışı olabilir. Bu yüzden Signal, kullanıcıların önceden sunucuya yüklediği anahtar demetlerini (prekey bundles) kullanır:

- **Identity key (IK):** uzun ömürlü kimlik anahtarı
- **Signed prekey (SPK):** kimlik anahtarıyla imzalanmış, periyodik değişen anahtar
- **One-time prekeys (OPK):** tek kullanımlık anahtarlar

Başlatan, alıcının bundle'ını çeker ve birden fazla DH işlemini (tipik olarak IK-SPK, EK-IK, EK-SPK, EK-OPK) birleştirerek ortak bir gizli (shared secret) türetir. Birden çok DH'in birleştirilmesi hem kimlik doğrulama hem ileri gizlilik sağlar. İmzalı prekey, bir MITM saldırganın sahte anahtar enjekte etmesini engeller.

### Double Ratchet: İki Cırcır Mekanizması

X3DH'ten elde edilen kök gizli, **Double Ratchet** algoritmasını besler. "Ratchet" (cırcır dişlisi) benzetmesi: anahtarlar yalnızca ileri döner, geri gitmek imkânsızdır. İki ayrı cırcır vardır:

**1. Symmetric-key ratchet (KDF zinciri):** Gönderilen/alınan her mesaj için bir "chain key" bir **KDF (Key Derivation Function)** ile ilerletilir. Her mesaj benzersiz bir message key alır ve chain key güncellenir. KDF tek yönlü olduğundan, bir message key ele geçse bile önceki mesaj anahtarları geri hesaplanamaz - bu **fine-grained forward secrecy** sağlar.

**2. Diffie-Hellman ratchet:** Taraflar her cevap turunda yeni bir geçici DH public key'i gönderir. Karşı taraf yeni bir public key gördüğünde, yeni bir DH işlemi yapar ve kök zinciri (root chain) yeniler. İşte **post-compromise security** buradan gelir: saldırgan mevcut durumu ele geçirse bile, taraflar bir sonraki DH ratchet turunda üreteceği yeni geçici anahtarı bilmez; birkaç mesaj sonra saldırgan tekrar dışarıda kalır ("self-healing").

### Örnek: Mesajlaşma Akışı (kavramsal)

Alice, Bob'a üç mesaj gönderir (Bob henüz cevap vermeden): symmetric ratchet üç kez ilerler, her mesajın anahtarı farklıdır. Bob cevap verdiğinde yeni bir DH public key ekler; Alice bunu görünce DH ratchet döner, root key yenilenir ve yeni bir gönderme zinciri başlar. Böylece sürekli değişen, geri döndürülemez bir anahtar akışı oluşur.

**Out-of-order mesajlar:** Mesajlar sırasız gelebilir. Double Ratchet, atlanan message key'leri geçici olarak saklayarak sonradan gelen eski mesajları çözebilir - ancak bu saklama, bir bellek/güvenlik ödünleşimidir (saklanan anahtarlar ele geçirilirse FS zayıflar).

### Yaygın Hatalar

- **Skipped-message key'lerin sınırsız saklanması:** DoS'a ve FS erozyonuna yol açar; makul bir üst sınır gerekir.
- **Kimlik anahtarı doğrulamasının atlanması:** Kullanıcılar "safety number / güvenlik kodu" karşılaştırmazsa, sunucu tabanlı MITM (kötü niyetli sunucunun sahte anahtar servis etmesi) tespit edilemez. E2EE'nin kök güven sorunu buradadır.
- **Randomness (rastgelelik) kalitesizliği:** Zayıf RNG, geçici anahtarları tahmin edilebilir kılarak tüm FS/PCS garantilerini yok eder.

## Bölüm 5: Formel Doğrulama - Tamarin ve ProVerif

### Neden Gerekli?

"Protokolü dikkatlice tasarladık, güvenli görünüyor" yeterli değildir. Formel doğrulama, protokolü matematiksel bir modele döker ve **Dolev-Yao saldırganına karşı tüm olası oturum sıralamalarında** güvenlik özelliklerinin sağlanıp sağlanmadığını otomatik olarak kanıtlar (veya bir saldırı senaryosu - counterexample/attack trace - üretir).

### Symbolic Model (Sembolik Model)

Her iki araç da **sembolik model**de çalışır. Kriptografik işlemler somut bitler yerine cebirsel terimler olarak temsil edilir: örneğin `dec(enc(m, k), k) = m` gibi denklemlerle. Kriptografinin "kusursuz" olduğu varsayılır (perfect cryptography assumption). Bu, protokolün **mantık hatalarını** yakalar - ama ilkelcinin kendisindeki zayıflığı (ör. zayıf bir hash) yakalamaz. Bu yüzden sembolik model, hesaplamalı (computational) model kanıtlarını (ör. CryptoVerif, oyun tabanlı ispatlar) tamamlar, onların yerini almaz.

### ProVerif

ProVerif (Bruno Blanchet), protokolü **applied pi-calculus** adı verilen bir süreç cebirinde tanımlar. İç mekanizması, protokolü **Horn clause**'lara çevirip saldırganın türetebileceği bilgi kümesini hesaplayan bir çözümleyicidir (resolution). Güçlü yönü: hızlı, yüksek otomasyon, sonsuz sayıda oturumu tek seferde ele alabilir. Zayıf yönü: bazen **yanlış pozitif** (aslında olmayan bir saldırı) bildirebilir çünkü yaptığı soyutlama over-approximation'dır (özellikle durum/state içeren protokollerde). `reachability`, `secrecy`, `authentication` (correspondence assertions) ve gözlemsel denklik (observational equivalence, ör. deniability/privacy için) sorgularını destekler.

### Tamarin Prover

Tamarin (David Basin, Cas Cremers ekipleri), **multiset rewriting rules** ile protokolü modeller ve özellikleri **first-order logic** temelli bir mantıkta (trace properties) ifade eder. Çözümlemeyi geriye doğru arama (backward search / constraint solving) ile yapar. Güçlü yönleri:

- **Diffie-Hellman ve XOR** gibi denklemsel teorileri yerel olarak destekler - bu, DH tabanlı modern protokoller (Signal, Noise, TLS 1.3) için kritiktir.
- **Kalıcı durumu (mutable global state)** ProVerif'ten daha doğru modeller.
- Otomatik ispat başarısız olursa, kullanıcı **interaktif modda** ispat ağacına müdahale edip "yardımcı lemma"lar (helping lemmas, oracle) sağlayabilir.

Ödünleşim: Tamarin daha ifade gücü yüksek ama daha çok manuel emek gerektirebilir; ProVerif daha otomatik ama daha kısıtlı. Pratikte ciddi analizlerde her ikisi de kullanılır. TLS 1.3, 5G-AKA, Noise pattern'ları ve Signal bileşenleri bu araçlarla analiz edilmiştir ve bu analizler standartların olgunlaşmasına doğrudan katkı yapmıştır.

### Örnek: Bir Formel İspatın Anatomisi (kavramsal)

Bir kimlik doğrulama özelliğini kanıtlamak için tipik adımlar:
1. Protokol kurallarını yaz (mesaj gönderme/alma, anahtar üretme).
2. Saldırgan yeteneklerini (Dolev-Yao) modele dahil et - araçlar bunu genellikle yerleşik sağlar.
3. Güvenlik hedefini bir lemma olarak ifade et: "Bob bir oturumu Alice ile tamamladıysa, Alice gerçekten karşılık gelen bir oturum başlatmıştır" (agreement/injective agreement).
4. Aracı çalıştır: ya `verified` (kanıt bulundu) ya da bir **attack trace** döner. Attack trace, tam olarak hangi mesaj yeniden yönlendirmesinin özelliği ihlal ettiğini gösterir - bu, tasarımı düzeltmek için paha biçilmezdir.

## Bölüm 6: Tespit ve Savunma Perspektifi

Formel doğrulama tasarım zamanı bir güvencedir; ama çalışma zamanında (runtime) da savunma gerekir.

**Tespit:**
- **Anahtar değişimi izleme:** E2EE istemcilerinde, karşı tarafın kimlik anahtarının (safety number) beklenmedik şekilde değişmesi olası bir MITM/hesap ele geçirme işaretidir. İyi istemciler bunu kullanıcıya uyarı olarak gösterir; kurumsal ortamda bu olayların loglanması tespit sağlar.
- **Handshake anomalileri:** Beklenmeyen pattern downgrade denemeleri, tekrarlayan handshake başarısızlıkları veya replay göstergeleri (aynı nonce/ephemeral key) ağ/uygulama seviyesinde izlenebilir.
- **Sertifika/anahtar şeffaflığı (transparency logs):** Sunucunun servis ettiği anahtarların bir append-only log'da yayınlanması, sessiz anahtar değişimlerinin tespitini sağlar (Key Transparency yaklaşımı).

**Savunma:**
- **Kanıtlanmış çerçeveler kullanın:** Kendi handshake'inizi yazmak yerine Noise veya libsignal gibi formel olarak analiz edilmiş, olgun kütüphaneleri kullanın. "Roll your own crypto protocol" en yaygın hata kaynağıdır.
- **Out-of-band doğrulama:** Kullanıcıları safety number karşılaştırmaya teşvik edin; kurumsal senaryolarda anahtar sabitleme (pinning).
- **Downgrade koruması:** Handshake'in tüm parametrelerini (versiyon, pattern, cipher suite) transkript hash'ine dahil ederek, ortadaki bir saldırganın parametreleri zayıflatmasını (downgrade attack) engelleyin. TLS 1.3'ün transcript hash tasarımı ve Noise'ın chaining key'i bu prensibi uygular.
- **Nonce ve state hijyeni:** Nonce'ların asla tekrarlanmadığından, RNG'nin kaliteli olduğundan ve skipped-key saklama sınırlarının makul olduğundan emin olun.
- **Yeni protokolleri formel doğrulamadan geçirin:** Bir protokolde değişiklik yapıyorsanız (yeni bir mod, yeni bir pattern), Tamarin/ProVerif modelini güncelleyip yeniden kanıtlayın - küçük değişiklikler güvenlik özelliklerini sessizce bozabilir.

## Sonuç

Kriptografik ilkelciler güçlüdür, ama güvenlik onları birbirine bağlayan protokolde kazanılır veya kaybedilir. Noise Framework, güvenli handshake tasarımını yapı taşlarına indirgeyerek insan hatasını azaltır. Signal'in X3DH + Double Ratchet kombinasyonu, forward secrecy ve post-compromise security gibi modern hedefleri pratik ve inkar edilebilir bir mesajlaşmada birleştirir. Tamarin ve ProVerif ise, "güvenli görünüyor"u "matematiksel olarak güvenli olduğu kanıtlandı"ya dönüştürür. Kıdemli bir güvenlik pratisyeni için ders nettir: kendi protokolünüzü icat etmeyin, kanıtlanmış olanları kullanın; değiştirdiğinizde yeniden kanıtlayın; ve runtime'da anahtar değişimlerini izleyin. Protokol güvenliği bir kerelik bir başarı değil, tasarım-kanıt-izleme döngüsünün sürekliliğidir.
