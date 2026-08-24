# PKI ve Sertifika Doğrulama: Güven Zinciri, CA, Pinning ve Yaygın Doğrulama Hataları

## Giriş ve Tanım

PKI (Public Key Infrastructure — Açık Anahtar Altyapısı), asimetrik kriptografiyi gerçek dünyada kullanılabilir kılan kurumsal, teknik ve prosedürel çerçevenin bütününe verilen isimdir. Temel problem şudur: elimizde bir açık anahtar (public key) var, ama bu anahtarın gerçekten karşımızdaki tarafa — örneğin `banka.com`'a — ait olduğunu nasıl bileceğiz? Asimetrik kriptografi tek başına "bu mesajı sadece bu anahtarın sahibi çözebilir" garantisini verir, ama "bu anahtarın sahibi kim?" sorusuna cevap vermez. İşte PKI tam olarak bu **kimlik-anahtar bağını** (identity-to-key binding) güvenilir bir şekilde kurmak için vardır.

Bu bağı kuran belge **dijital sertifikadır** (X.509 sertifikası). Bir sertifika, özünde şunları içeren imzalı bir veri yapısıdır: bir açık anahtar, bu anahtarın ait olduğu iddia edilen kimlik (domain adı, kuruluş bilgisi), geçerlilik tarihleri, ve bu iddiayı onaylayan bir üçüncü tarafın (CA — Certificate Authority) dijital imzası. Sertifika doğrulama ise, karşı tarafın sunduğu sertifikanın gerçekten güvenilir, geçerli ve beklenen kimliğe ait olduğunu programatik olarak denetleme sürecidir.

TLS handshake sırasında sunucu sertifikasını istemciye gönderir; istemcinin doğrulama mantığı burada devreye girer. Bu doğrulamanın hatalı yapılması, tüm TLS güvenliğini anlamsız hale getirir — çünkü şifreli bir kanal kursanız bile, kanalın **kiminle** kurulduğundan emin değilseniz, saldırgan araya girip (man-in-the-middle) sizi kendisiyle şifreli konuşturabilir.

## Kök Neden: Güven Neden Zincirle Kurulur?

### Ölçeklenme problemi

İnternette milyarlarca sunucu var. Her istemcinin her sunucunun açık anahtarını önceden bilmesi imkansızdır. Öte yandan, hiçbir doğrulama yapmadan gelen her anahtara güvenmek de saldırıya davetiye çıkarır. Çözüm, **güveni delege etmektir**: az sayıda son derece güvenilir otoriteye (kök CA'lara) güvenirsek ve bu otoriteler diğer kimlikleri onaylarsa, transitif olarak onların onayladıklarına da güvenebiliriz.

Bu, güven zincirinin (chain of trust) varoluş nedenidir. İşletim sistemleri ve tarayıcılar, önceden seçilmiş yaklaşık birkaç yüz kök CA sertifikasını içeren bir **trust store** (güven deposu) ile gelir. Bu kök sertifikalar **self-signed**'dır — kendi kendini imzalar, çünkü zincirin en tepesinde onları onaylayacak daha üst bir otorite yoktur. Onlara güvenmemizin sebebi kriptografik değil, **out-of-band** bir karardır: bu CA'ları OS/tarayıcı üreticisi denetlemiş ve trust store'a koymuştur.

### Neden ara CA'lar (intermediate CA) var?

Pratikte kök CA'ların özel anahtarları (private key) altın değerindedir; bunlar genelde çevrimdışı (offline), fiziksel olarak korunan HSM'lerde (Hardware Security Module) tutulur. Kök anahtarın günlük operasyonlarda kullanılması, ifşa olma riskini kabul edilemez seviyeye çıkarır. Bu yüzden kök CA, bir veya birkaç **ara CA** sertifikası imzalar; günlük son-varlık (end-entity / leaf) sertifikaları bu ara CA'lar tarafından imzalanır.

Böylece tipik bir zincir şöyle görünür:

```
Kök CA (self-signed, trust store'da)
   └── imzalar → Ara CA
            └── imzalar → Leaf sertifika (banka.com)
```

Bu yapının ikinci bir faydası: bir ara CA'nın anahtarı ifşa olursa, sadece o ara CA revoke edilir; kök CA ve trust store'daki milyarlarca cihaz etkilenmez. **Anahtar hijerarşisi, hasarı sınırlar.**

## Güven Zinciri Doğrulaması Adım Adım

İstemci bir leaf sertifikası aldığında, onu tek başına doğrulamaz; **kök CA'ya kadar geri giden zinciri** inşa eder ve her halkayı denetler. Kavramsal adımlar:

1. **Path building (yol inşası):** Leaf sertifikanın `Issuer` (imzalayan) alanı, bir ara CA'nın `Subject` alanıyla eşleşmeli. O ara CA'nın issuer'ı bir üst CA'nın subject'iyle eşleşmeli, ta ki trust store'daki bir kök sertifikaya ulaşana kadar.

2. **İmza doğrulaması:** Her sertifikanın imzası, bir üstteki sertifikanın açık anahtarıyla doğrulanır. Yani leaf'in imzasını ara CA'nın public key'i doğrular; ara CA'nın imzasını kök CA'nın public key'i doğrular. İmza bir tek bitte bile bozulsa, zincir kırılır.

3. **Geçerlilik süresi:** Her sertifikanın `notBefore`/`notAfter` aralığı, doğrulama anındaki sisteme göre geçerli olmalı. Süresi dolmuş (expired) veya henüz geçerli olmayan sertifika reddedilir.

4. **İsim/kimlik eşleşmesi (hostname verification):** Bu **en kritik ve en sık atlanan** adımdır. Leaf sertifikanın kimliği, bağlanılan host ile eşleşmeli. Modern doğrulamada bu, sertifikanın **SAN (Subject Alternative Name)** alanındaki DNS isimleriyle yapılır. Tarihî `CN` (Common Name) alanı bu iş için artık geçerli kabul edilmez; SAN yoksa modern istemciler genelde reddeder.

5. **Kullanım kısıtları:** `Basic Constraints` uzantısı bir sertifikanın CA olup olamayacağını (`CA:TRUE/FALSE`), `Key Usage` / `Extended Key Usage` ise anahtarın hangi amaçla kullanılabileceğini (örn. TLS sunucu kimlik doğrulaması) belirtir. Bunlar denetlenmezse ciddi güvenlik açıkları oluşur (aşağıda anlatacağım).

6. **İptal (revocation) kontrolü:** Sertifika süresi dolmadan iptal edilmiş olabilir (anahtar çalındı, yanlış verildi vb.). Bunun için CRL (Certificate Revocation List) veya OCSP (Online Certificate Status Protocol) mekanizmaları vardır.

Bu adımların **hepsi** geçerse zincir güvenilir kabul edilir. Herhangi biri başarısız olursa bağlantı reddedilmelidir.

## Somut Örnek: Bir Zincirin İncelenmesi

Diyelim `ornek-banka.com`'a bağlanıyorsunuz. Sunucu size iki sertifika gönderiyor: leaf ve ara CA. (İyi yapılandırılmış sunucular ara sertifikaları da gönderir; kök zaten istemcide olduğu için gönderilmez.)

İstemci şunu yapar: leaf sertifikanın SAN alanında `ornek-banka.com` var mı diye bakar. İmzasını ara CA'nın public key'iyle doğrular. Ara CA'nın issuer'ına bakar, trust store'da eşleşen kökü bulur, ara CA'nın imzasını o kökün public key'iyle doğrular. Tarihleri kontrol eder. OCSP/CRL ile iptal durumuna bakar. Hepsi geçerse handshake tamamlanır.

Komut satırında bir sunucunun sunduğu zinciri incelemek için OpenSSL'in `s_client` alt komutu yaygın olarak kullanılır; sunucuya bağlanıp sunulan sertifikaları ve zincir doğrulama sonucunu gösterir. (Kesin bayrak sözdizimini burada ezberden vermek yerine kavramı vurguluyorum: amaç, sunulan zinciri ve doğrulama dönüş kodunu görmektir.) Tek bir sertifika dosyasının içeriğini — subject, issuer, SAN, geçerlilik, uzantılar — okumak için ise sertifikayı metin olarak dökümleyen `x509` alt komutu kullanılır.

## Sömürü/İstismar Mantığı ve Savunma

PKI'nin gücü de zayıflığı da güven delegasyonundadır. Aşağıda başlıca saldırı sınıflarını **hem istismar mantığıyla hem savunmasıyla** ele alıyorum.

### 1. Man-in-the-Middle ve sahte sertifika

**İstismar:** Saldırgan trafiğin arasına girer (ARP spoofing, sahte Wi-Fi, DNS zehirlemesi, kötü niyetli proxy) ve kendi sertifikasını sunucununmuş gibi sunar. Eğer istemci sertifika doğrulamasını yapmıyorsa veya hatalı yapıyorsa, saldırganla şifreli konuşur ama şifreleme saldırganın anahtarıyla olduğu için tüm trafiği saldırgan okuyup değiştirebilir. Şifreleme burada bir yanılsama güvenliği yaratır.

**Savunma:** Zincirin tam doğrulaması + hostname doğrulaması. Saldırganın sunduğu sertifika ya güvenilir bir CA tarafından `ornek-banka.com` için imzalanmamıştır (zincir kırılır) ya da hostname eşleşmez. Doğru doğrulama yapan bir istemci bu bağlantıyı reddeder.

### 2. Hileli/ele geçirilmiş CA

**İstismar:** Trust store'daki her CA, herhangi bir domain için sertifika üretebilir. Bu, sistemin en zayıf noktasıdır: yüzlerce CA'dan **biri** bile kötü niyetli, ihmalkâr veya ele geçirilmişse, sizin domain'iniz için sahte ama teknik olarak "geçerli" bir sertifika üretebilir. Geçmişte büyük CA ihlalleri yaşandı ve bir CA'nın anahtarı ele geçirildiğinde, o CA'ya güvenen tüm dünyaya karşı MITM mümkün hale geldi.

**Savunma:** 
- **Certificate Transparency (CT):** Tüm güvenilir sertifikaların, herkese açık, ekle-yalnız (append-only) loglara kaydedilmesi zorunludur. Böylece bir domain sahibi, kendi adına habersizce üretilmiş bir sertifikayı bu logları izleyerek fark edebilir. CT, kötü niyetli sertifika üretimini gizli olmaktan çıkarıp **tespit edilebilir** kılar.
- **Pinning** (aşağıda ayrıntılı).
- **Kurumsal ortamlarda CA kısıtlama:** Gereksiz kök CA'ların trust store'dan çıkarılması, saldırı yüzeyini azaltır.

### 3. Kötü niyetli kök CA enjeksiyonu (cihaz seviyesinde)

**İstismar:** Saldırgan, kurbanın cihazının trust store'una kendi kök sertifikasını eklerse (kötü amaçlı yazılım, kandırma, veya "kurumsal proxy kurulumu" adı altında), artık kendi ürettiği tüm sahte sertifikalar o cihazda "geçerli" görünür. Kurumsal TLS-inspection proxy'leri tam olarak bu mekanizmayla, meşru ama gözetimci amaçla çalışır.

**Savunma:** Trust store'a yazma yetkisinin sıkı korunması, cihaz bütünlüğü, ve kritik uygulamalarda **pinning** — çünkü pinning sistem trust store'unu baypas edip yalnızca beklenen anahtara güvenir; enjekte edilmiş kök işe yaramaz.

### 4. Zayıf kriptografi ve downgrade

**İstismar:** Eski, kırılabilir imza algoritmalarıyla (örn. MD5/SHA-1 tabanlı imzalar) üretilmiş sertifikalar, collision saldırılarıyla taklit edilebilir. Saldırgan bir çakışma (collision) üretebilirse, meşru bir sertifikayla aynı imzaya sahip sahte bir sertifika üretebilir.

**Savunma:** Modern istemciler zayıf imza algoritmalarını reddeder. Yeterli anahtar uzunluğu (RSA için yeterli bit, veya ECDSA) ve güncel hash fonksiyonları (SHA-256 ailesi) şart. Doğrulama mantığında zayıf algoritmaları kabul etmemek gerekir.

## Certificate Pinning: Ne Zaman, Nasıl, Neden Dikkatli?

**Pinning**, bir istemcinin belirli bir sunucu için yalnızca **önceden belirlenmiş** bir sertifikaya veya açık anahtara güvenmesidir. Yani "güvenilir herhangi bir CA'nın imzaladığı sertifika olur" yerine, "yalnızca şu spesifik anahtar/sertifika olur" der.

### Neden pinning?

Standart doğrulamanın en büyük zaafı, **herhangi** bir güvenilir CA'nın domain'iniz için sertifika üretebilmesidir. Pinning bu geniş güven kümesini daraltır: bir CA ele geçirilse bile, saldırganın ürettiği sertifika sizin pin'inizle eşleşmediği için istemci reddeder. Özellikle mobil uygulamalarda (banka, mesajlaşma) ve kritik API iletişimlerinde değerlidir; çünkü bu uygulamalar kimin sunucusuna bağlanacaklarını önceden bilirler.

### Ne pin'lenir?

- **Sertifika pinning:** Tam sertifikanın hash'i pin'lenir. Basit ama kırılgan; sertifika yenilendiğinde (rotasyon) pin bozulur.
- **Public key pinning (tercih edilen):** Sertifikanın **açık anahtarının** hash'i (genelde SPKI — Subject Public Key Info üzerinden) pin'lenir. Sertifika yenilense de aynı anahtar çifti korunursa pin geçerli kalır. Bu, esneklik ile güvenlik arasında daha iyi bir dengedir.

### İstismar açısından pinning'in kırılması

Saldırganlar (özellikle uygulama analizi/tersine mühendislikte) pinning'i **atlatmaya** çalışır: uygulamanın belleğindeki pin kontrolünü runtime'da yamalayarak (hooking framework'leriyle) veya doğrulama fonksiyonunu her zaman "geçerli" döndürecek şekilde değiştirerek. Bu, pinning'in mutlak değil, **maliyet artırıcı** bir savunma olduğunu gösterir: cihaz saldırganın kontrolündeyse (rooted/jailbroken + tersine mühendislik), pinning baypas edilebilir. Yine de meşru MITM senaryolarını (ağ seviyesindeki saldırgan) etkili biçimde durdurur.

### Pinning'in tehlikesi: kendi ayağına sıkmak

Pinning'in en büyük operasyonel riski **brick** etmektir. Pin'lenen anahtar acil olarak değiştirilmek zorunda kalırsa (ör. anahtar ifşası) ve istemciler eski pin'e sıkı bağlıysa, uygulama sunucuya bağlanamaz hale gelir — kendinizi kilitlersiniz. Bu yüzden:

- **Yedek pin (backup pin)** bulundurulmalı: şu an kullanılmayan ama hazırda tutulan bir anahtarın hash'i de pin listesine konur. Böylece acil rotasyonda yedek anahtara geçilebilir.
- **Makul son kullanma / güncelleme mekanizması** olmalı: pin setini uygulama güncellemeleriyle güncelleyebilmek gerekir.
- Tarayıcı tabanlı HTTP başlık pinning'i (geçmişte denenen HPKP mekanizması) bu brick riski nedeniyle pratikte terk edildi; sektör daha çok CT + mobil uygulama içi pinning yönüne gitti. Bu, "yanlış pinning'in pinning yapmamaktan kötü olabileceğinin" somut bir dersidir.

## Sertifika İptali (Revocation): Zor Problem

Bir sertifika süresi dolmadan geçersiz kılınmak istenebilir. İki klasik mekanizma:

- **CRL:** CA, iptal edilmiş sertifikaların listesini yayınlar. Sorun: listeler büyür, güncel tutmak ve indirmek maliyetlidir, gecikmelidir.
- **OCSP:** İstemci, sertifikanın durumunu CA'ya (OCSP responder) canlı sorar. Sorun: gizlilik (istemcinin hangi siteye gittiği CA'ya sızar), gecikme, ve **fail-open** problemi.

**Fail-open problemi** kritiktir: OCSP responder'a ulaşılamazsa istemci ne yapmalı? Bağlantıyı reddederse (fail-closed), OCSP sunucusunun geçici kesintisi tüm bağlantıları koparır — kullanılabilirlik felaketi. Kabul ederse (fail-open), saldırgan OCSP trafiğini bloklayarak iptal kontrolünü etkisiz kılabilir. Pratikte birçok istemci fail-open davranır, bu da OCSP'nin saldırı karşısındaki değerini ciddi biçimde zayıflatır.

**OCSP Stapling** bu problemi hafifletir: sunucu, kendi sertifikası için CA'dan imzalı ve zaman damgalı bir "bu sertifika geçerli" cevabını önceden alır ve handshake sırasında istemciye **kendisi sunar (staple eder)**. Böylece istemci CA'ya ayrı sorgu yapmaz (gizlilik ve gecikme iyileşir), ve cevap CA imzalı olduğu için sunucu onu sahteleyemez. Modern en iyi pratik budur; ancak bunu da zorunlu kılmak (must-staple) gerekebilir, aksi halde saldırgan staple'ı düşürebilir.

Genel eğilim, iptal problemini kökten çözmek yerine **sertifika ömrünü kısaltmaktır**: kısa ömürlü sertifikalar (birkaç aya, hatta daha aza inen geçerlilik), iptalin önemini azaltır çünkü zaten kısa sürede kendiliğinden geçersiz olurlar.

## Yaygın Doğrulama Hataları

Bu hatalar teoride bilinse de, sahada sürekli tekrar ediyorlar. Kök nedenleri genelde "çalışıyor gibi görünüyor ama güvenli değil" tuzağıdır.

### 1. Hostname doğrulamasını atlamak

En yaygın ve en tehlikeli hata. Bir kütüphane zincir doğrulamasını yapar (sertifika güvenilir bir CA tarafından imzalanmış), ama sertifikanın **hangi host için** olduğunu kontrol etmez. Sonuç: saldırgan, başka bir domain için aldığı **tamamen geçerli** bir sertifikayla sizi kandırabilir. Zincir geçerlidir ama kimlik yanlıştır. Bazı HTTP kütüphanelerinde bu, ayrı bir adım olduğu için unutulur.

### 2. Doğrulamayı tamamen kapatmak

Geliştirme sırasında self-signed sertifika hatalarını susturmak için `verify=False`, `InsecureSkipVerify`, "tüm sertifikaları kabul et" gibi ayarlar konur — ve bu ayar **production'a sızar**. Bu, TLS'i tamamen anlamsızlaştırır. Kök neden: geliştirici, "hata veriyor, kapatayım" refleksiyle güvenlik denetimini bilerek devre dışı bırakır ama temizlemeyi unutur.

### 3. Boş/her-zaman-başarılı doğrulama callback'i

Bazı diller, sertifika doğrulaması için bir callback verir. Geliştirici bu callback'i her zaman "geçerli" döndürecek şekilde yazarsa (örneğin bir mobil trust manager'ın `checkServerTrusted` metodunu boş bırakmak), doğrulama görünüşte yapılıyormuş gibi durur ama hiçbir şey denetlemez. Bu, statik analizle bile yakalanması gereken klasik bir anti-pattern'dir.

### 4. Ara sertifikaları göndermemek (sunucu tarafı hata)

Sunucu yalnızca leaf sertifikayı gönderir, ara CA'yı göndermez. Bazı istemciler eksik halkayı kendi başına bulabilir (AIA fetch), bazıları bulamaz ve zincir kırılır. Bu bir güvenlik açığı değil ama yaygın bir yapılandırma hatasıdır ve kullanıcıları "sertifika hatasını görmezden gelme" davranışına iter — ki bu dolaylı olarak güvenliği bozar.

### 5. Zaman kaynağına güvenmemek / yanlış saat

Doğrulama sistem saatine dayanır. Cihazın saati çok yanlışsa, geçerli sertifikalar "süresi dolmuş" ya da "henüz geçerli değil" görünür; kullanıcı hatayı baypas etmeye alışırsa, gerçekten süresi dolmuş/iptal edilmiş sertifikaları da kabul eder hale gelir.

### 6. Key Usage / Basic Constraints denetimini atlamak

Tarihte kritik bir hata sınıfı: istemci, zincirdeki bir sertifikanın **CA olmaya yetkili olup olmadığını** (`Basic Constraints: CA:TRUE`) kontrol etmezse, herhangi bir geçerli leaf sertifika sahibi, o sertifikayı kullanarak başka domainler için sertifika "imzalayabilir". Yani sıradan bir kullanıcı sertifikası, ara CA gibi davranarak zinciri kötüye kullanabilir. Bu tam olarak neden `Basic Constraints` denetiminin zorunlu olduğunu gösterir.

### 7. İptal kontrolünü sessizce fail-open geçmek

Yukarıda anlatıldığı gibi, iptal kontrolü başarısız olduğunda sessizce "geçerli" kabul etmek, revocation mekanizmasını saldırgan için etkisizleştirir.

## En İyi Pratikler

Doğrulama mantığını doğru kurmak için pratikte izlenmesi gereken ilkeler:

- **Kendi TLS/doğrulama kodunu yazma.** Olgun, iyi bakım gören kütüphanelerin varsayılan doğrulama davranışını kullan. Kriptografik doğrulama, elle yeniden yazıldığında neredeyse her zaman hatalı çıkar. Kendi X.509 parser'ını yazmak felakete davetiyedir.

- **Hostname doğrulamasının açık ve etkin olduğundan emin ol.** Zincir doğrulaması ile hostname doğrulamasının **ayrı** olabileceğini bil; ikisini de kontrol et.

- **Doğrulamayı asla production'da kapatma.** Geliştirme ortamı için gerekiyorsa, `verify=False` yerine geliştirme CA'sını yalnızca dev trust store'una ekle. "Kapat ve unut" en tehlikeli yoldur.

- **Certificate Transparency'yi kullan.** Kendi domain'lerin için CT loglarını izle; adına habersiz üretilmiş sertifikaları erken yakala.

- **Kritik uygulamalarda public-key pinning kullan — ama yedek pin ve güncelleme mekanizmasıyla.** Pinning'i brick riski olmadan uygula; yedeksiz pinning yapma.

- **OCSP Stapling'i (mümkünse must-staple ile) etkinleştir.** İptal bilgisini gizlilik ve dayanıklılık açısından en sağlam şekilde ilet.

- **Kısa ömürlü sertifikaları ve otomatik yenilemeyi benimse.** Otomasyon (ACME tabanlı akışlar gibi) hem insan hatasını hem de iptal problemini azaltır.

- **Zayıf algoritmaları reddet.** Güncel imza algoritmaları ve yeterli anahtar uzunlukları dışındaki her şeyi kapat.

- **Gereksiz kök CA'ları güven deposundan çıkar (kurumsal ortamda).** Güvendiğin CA sayısı ne kadar azsa, saldırı yüzeyin o kadar küçüktür.

- **Sertifika hatalarını kullanıcıya "geç/kabul et" seçeneğiyle sunmaktan kaçın.** Kullanıcıları hata baypas etmeye alıştırmak, tüm doğrulama zincirini sosyal mühendislikle çökertir.

- **Denetim ve otomatik test yap.** Doğrulama mantığını, geçersiz/expired/yanlış-hostname/self-signed sertifikalarla test et; bunların **reddedildiğini** doğrula. Pozitif testin yanında negatif test şart: sadece "geçerli sertifika geçiyor mu" değil, "geçersiz sertifika gerçekten reddediliyor mu" da test edilmeli.

## Sonuç

PKI'nin tüm mimarisi tek bir soruya cevap vermek için vardır: "Bu açık anahtar gerçekten iddia edilen kimliğe mi ait?" Cevap, kök CA'lardan leaf sertifikalara uzanan bir **güven zinciriyle** verilir; bu zincirin her halkası imza, süre, kimlik, kullanım kısıtı ve iptal açısından denetlenmelidir. Sistemin gücü güven delegasyonunda, zayıflığı da aynı yerdedir: güvenilen herhangi bir CA'nın herhangi bir domain için sertifika üretebilmesi, hem Certificate Transparency gibi tespit mekanizmalarını hem de pinning gibi güven kümesini daraltan savunmaları gerekli kılar.

Sahadaki gerçek felaketler ise nadiren kriptografinin kırılmasından, neredeyse her zaman **doğrulamanın atlanmasından** doğar: kapatılmış doğrulama, unutulmuş hostname kontrolü, boş callback'ler, fail-open iptal. Bu yüzden altın kural nettir: doğrulamayı sen yazma, olgun kütüphanenin doğru varsayılanlarını bozmadan kullan, ve her zaman negatif testle "geçersiz sertifika gerçekten reddediliyor mu" sorusunu doğrula. TLS'in şifrelemesi, ancak arkasındaki kimlik doğrulaması sağlamsa bir anlam ifade eder.
