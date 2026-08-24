# Mobil Güvenlik Derinlemesine: Keychain/Keystore, Kök/Jailbreak Tespiti, Runtime Enstrümantasyon ve Pinning Atlatma

> **Eğitim amaçlı referans.** Bu belge mekanizmaları *anlamak* ve mobil uygulamalar için **tespit ve savunma** kurmak içindir. Amaç, saldırganın uygulamanıza karşı kullandığı teknikleri kavrayıp bunları etkisiz kılacak kontrolleri tasarlamaktır. Analizler yalnızca kendi sahibi olduğunuz uygulamalar ve yetkili test ortamlarında yapılmalıdır.

## Neden Ayrı Bir Konu?

Genel "Mobil Güvenlik" başlığı çoğu zaman OWASP MASVS gereksinim listesine ve OWASP MASTG test kılavuzuna atıfla geçiştirilir. Ancak pratikte mobil güvenliğin kalbi, **runtime (çalışma zamanı) davranışının değiştirilebilir olmasıdır**: mobil bir uygulama, saldırganın tam kontrolündeki bir cihazda çalışır. Sunucudan farklı olarak istemci, düşmanın elindeki bir kutudur. Bu yüzden Frida ile enstrümantasyon, SSL pinning atlatma, platform-özel anahtar deposu analizi ve kök/jailbreak tespiti atlatma gibi teknikler yüzeysel değil, tehdidin özüdür. Bu belge o özü ele alır.

Temel ilke: **Client-side kontroller, kararlı bir saldırganı durdurmaz; onu yavaşlatır.** Gerçek güvenlik sınırı her zaman sunucudur. Cihaz üzerindeki kontroller ise "maliyeti yükseltme" ve "otomatik/toplu saldırıyı elemedir".

---

## 1. Platform Anahtar Depoları: iOS Keychain ve Android Keystore

### Tanım

Her iki platform da hassas veriyi (token, kimlik bilgisi, kripto anahtar) uygulama tarafından değil, işletim sistemi tarafından yönetilen bir güvenli depoda tutmayı sunar.

- **iOS Keychain:** SQLite tabanlı, sistem daemon'ı (`securityd`) tarafından yönetilen şifreli bir depo. Veriye erişim, uygulamanın entitlement'ları ve `kSecAttrAccessible` erişilebilirlik sınıfı ile denetlenir.
- **Android Keystore:** Kriptografik anahtarları saklar. Kritik nokta: iyi tasarımda anahtar malzemesi hiçbir zaman uygulama bellek alanına çıkmaz; şifreleme/çözme işlemi donanım destekli güvenli bölgede (TEE — Trusted Execution Environment veya StrongBox güvenli öğe) yapılır.

### Kök Neden / Çalışma Mantığı

Bu depoların gücü **donanım köküne** dayanır. Modern iPhone'larda **Secure Enclave**, Android cihazlarda **TEE/StrongBox** ayrı bir güvenlik alanı sağlar. Anahtar burada üretildiğinde ("hardware-backed key"), private key donanımdan hiç dışarı çıkmaz — uygulama yalnızca "bu anahtarla imzala/çöz" der, sonucu alır.

Erişilebilirlik sınıfları savunmanın ince ayarıdır. iOS'ta örneğin `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` seçildiğinde veri hem yalnızca cihaz kilidi açıkken erişilebilir olur hem de yedeklere/başka cihaza taşınamaz. Android'de `setUserAuthenticationRequired(true)` ile anahtar kullanımı biyometrik/PIN doğrulamaya bağlanır.

### Örnek

Bir bankacılık uygulaması oturum token'ını saklarken:

- **Zayıf tasarım:** Token'ı `SharedPreferences` (Android) veya `UserDefaults`/`plist` (iOS) içinde düz metin yazmak. Kök/jailbreak'li cihazda bu dosyalar doğrudan okunur.
- **Güçlü tasarım:** Android'de Keystore'da üretilmiş, `AndroidKeyStore` sağlayıcılı bir AES anahtarıyla token'ı şifreleyip saklamak; anahtarın `setUserAuthenticationRequired` ile korunması. iOS'ta token'ı Keychain'e `ThisDeviceOnly` sınıfıyla, mümkünse Secure Enclave destekli anahtarla koymak.

### Saldırganın Bakışı — Neden Yine de Risk Var?

Anahtar donanımda kilitli olsa bile, **uygulama çalışırken şifre çözme işleminin *sonucu* bellekte oluşur**. Root/jailbreak'li cihazda Frida ile bu API çağrılarının dönüş değeri yakalanabilir. Yani Keystore/Keychain "veriyi diskte korur" ama "runtime'da hafızayı korumaz". Bu ayrımı anlamak kritiktir.

### Tespit ve Savunma

- Hassas veriyi asla düz depolamada (Prefs/UserDefaults/dosya/log) tutmayın.
- Android'de `AndroidKeyStore` sağlayıcısını, mümkünse StrongBox'ı (`setIsStrongBoxBacked(true)`) tercih edin; iOS'ta Secure Enclave destekli anahtarlar kullanın.
- Erişilebilirlik sınıfını en dar seçin: `ThisDeviceOnly` varyantları yedeklerle sızmayı engeller.
- Anahtar kullanımını kullanıcı doğrulamasına bağlayın (`setUserAuthenticationRequired`).
- **Yaygın hata:** Keystore'da anahtar üretip şifreli veriyi saklamak ama şifrelenmemiş kopyayı log'a veya geçici dosyaya yazmak. Diskteki tüm izleri denetleyin.

---

## 2. Jailbreak (iOS) ve Root (Android) Tespiti — ve Neden Atlatılır

### Tanım

Uygulamalar, çalıştıkları cihazın "güvenilir olmayan" bir duruma (jailbreak/root) getirilip getirilmediğini anlamaya çalışır. Amaç: OS güvenlik modelinin (sandbox, imza doğrulama) bozulduğu bir ortamda ekstra önlem almak ya da çalışmayı reddetmek.

### Çalışma Mantığı — Tipik Tespit Sinyalleri

Tespit rutinleri genellikle bir dizi "belirti" arar:

- **Dosya varlığı:** Jailbreak'te `Cydia`/`Sileo` gibi araç yolları; root'ta `su` ikili dosyası, `busybox`, bilinen root yönetici uygulaması paketleri.
- **Yazılabilirlik:** iOS'ta normalde salt-okunur olan sistem bölümüne yazabilme; sandbox dışına çıkabilme.
- **API/davranış anomalileri:** `fork()` başarısının beklenmedik olması, belirli dosya yollarının `stat` ile görülebilmesi.
- **Android'de:** `Build.TAGS` içinde `test-keys`, tehlikeli sistem özellikleri (`ro.debuggable`), SafetyNet/Play Integrity gibi platform onay servislerinin sonucu.

### Kök Neden — Neden Bu Kontroller Kırılgan?

Bütün bu kontroller **istemci üzerinde çalışan koddur** ve saldırgan o kodu değiştirebilir. Tespit fonksiyonu sonunda bir boolean döner: "jailbroken mı?". Saldırgan bu fonksiyonu Frida ile yakalayıp dönüşü her zaman `false` yapabilir; veya statik olarak binary'i yamalayabilir; veya kök gizleyici araçlarla (root'u/jailbreak izlerini uygulamadan saklayan çerçeveler) belirtileri görünmez kılabilir.

Yani tespit ile atlatma arasında sonsuz bir kedi-fare oyunu vardır. Tek bir kontrol noktası (single point of failure) varsa, o noktayı hooklamak yeterlidir.

### Örnek — Atlatmanın Kavramsal Akışı

Uygulama `isJailbroken()` çağırır → Frida bu metoda hook takar → hook orijinali çağırmadan `false` döndürür → uygulama cihazı temiz sanır. Objection gibi araçlar bu yaygın kontroller için hazır "bypass" yardımcıları sunar; bunlar da aynı hook mantığını otomatikleştirir.

### Tespit ve Savunma

- **Tek noktaya güvenmeyin.** Kontrolü çok sayıda, dağıtık ve tekrarlı yapın; tek bir boolean'a bağlamayın.
- **Platform onay servislerini kullanın:** Android'de **Play Integrity API**, iOS'ta **DeviceCheck / App Attest**. Bunların kritik farkı: cevabı **sunucu tarafında** kriptografik olarak doğrularsınız. İstemci içi boolean'dan çok daha güçlüdür çünkü hook edilse bile imzalı yanıtı üretemez.
- **Sonucu sunucuya taşıyın:** Cihaz bütünlüğü kararını istemcide verip orada uygulamak yerine, imzalı bir attestation'ı sunucuya gönderip erişim kararını orada alın.
- **Yaygın hata:** Jailbreak tespitini "aç-kapa" bir güvenlik özelliği sanmak. Bu bir *savunma katmanıdır*, güvenlik sınırı değildir. Onu hassas verinin tek koruyucusu yapmayın.

---

## 3. Frida ve Objection ile Runtime Enstrümantasyon

### Tanım

**Frida**, çalışan bir sürece bir JavaScript motoru enjekte ederek fonksiyonları gerçek zamanlı *hooklamayı* (araya girip parametre/dönüş değeri okuma-değiştirme) sağlayan dinamik enstrümantasyon çerçevesidir. **Objection**, Frida üzerine kurulmuş, mobil-özel görevleri (pinning bypass, depolama dökme, sınıf keşfi) komutlaştıran bir katmandır.

### Çalışma Mantığı

Frida iki modda çalışır:

- **Spawn:** Uygulamayı Frida başlatır ve daha ilk kod çalışmadan enjekte olur (erken kontrolleri yakalamak için).
- **Attach:** Zaten çalışan sürece bağlanır.

Enjeksiyondan sonra saldırgan, hedef metodun adresini/imzasını bulur ve bir "interceptor" takar. Bu interceptor metoda giriş (`onEnter`) ve çıkış (`onLeave`) anlarında çalışır; argümanları, dönüş değerini ve belleği okuyup değiştirebilir. Android'de Java katmanı için sınıf/metot isimleriyle, native katman için sembol/adresle çalışılır; iOS'ta Objective-C runtime'ının dinamik yapısı, metotları isimle bulup değiştirmeyi kolaylaştırır (Swift'te bu daha zordur).

Frida'nın gücü, **binary'i kalıcı değiştirmeden** davranışı runtime'da yeniden yazabilmesidir. Bu yüzden şifre çözme sonucunu, pinning kararını, jailbreak boolean'ını anlık olarak ele geçirmenin standart aracıdır.

### Örnek — Kavramsal

Bir metot `verifyLicense()` `true/false` döndürüyorsa, saldırgan `onLeave` içinde dönüş değerini `true` ile ezebilir. Bir şifreleme fonksiyonu düz metni parametre alıyorsa, `onEnter` içinde o parametre okunarak "cleartext capture" yapılabilir. Bu, TLS öncesi verinin yakalanmasının da temelidir.

### Tespit ve Savunma

- **Frida artefaktı tespiti:** Frida tipik olarak bir ajanla veya port/pipe üzerinden çalışır; süreçte enjekte edilmiş kütüphane isimleri, açık belirli portlar veya bellek imzaları aranabilir. Ancak Frida "gadget" gömülü ve isimler değiştirilmiş modda çalışabildiği için bu tespit de atlatılabilir.
- **Trap/kanarya fonksiyonları:** Hooklanması beklenen kritik fonksiyonların bütünlüğünü (kod bölgesinin checksum'ını) periyodik doğrulamak; beklenmedik değişimde tepki vermek.
- **Anti-debug:** `ptrace` tabanlı hile önleme (Android/Linux), iOS'ta debugger bağlı mı kontrolü. Yine katman, kesin sınır değil.
- **Sunucu tarafı davranış analizi:** Enstrümante edilen istemci sıklıkla "insan dışı" desenler üretir (imkânsız hızda istekler, tutarsız cihaz parmak izi). Bu anomalileri sunucuda yakalayın.
- **En önemlisi — attestation:** Play Integrity / App Attest ile "bu isteği gerçekten değiştirilmemiş uygulamam mı gönderdi?" sorusunu kriptografik olarak sunucuda cevaplayın. Runtime enstrümantasyona karşı en dayanıklı savunma budur.
- **Yaygın hata:** Anti-Frida kontrolünü uygulamanın kendi içinde, atlatılabilir bir boolean olarak kurmak. Frida'nın kendisi o kontrolü hookladığında savunma çöker.

---

## 4. Mobil Uygulama Tersine Mühendislik (Reverse Engineering)

### Tanım

Uygulamanın derlenmiş paketinden (Android'de `APK`/`AAB`, iOS'ta `IPA`) kaynak/mantık çıkarma sürecidir. Amaç: sırların bulunması, iş mantığının anlaşılması, güvenlik kontrollerinin yerinin tespiti.

### Çalışma Mantığı

- **Android:** DEX bytecode, `smali` ara diline veya kararlı araçlarla okunabilir Java benzeri koda çevrilir (decompilation). `AndroidManifest.xml`, exported bileşenler, izinler ve endpoint ipuçları burada okunur. Native kütüphaneler (`.so`) ayrı disassembler'larla incelenir.
- **iOS:** `IPA` içindeki Mach-O binary disassembler'larla analiz edilir. Objective-C metadata (sınıf/metot isimleri) çoğunlukla binary'de kalır ve tersine mühendisliği kolaylaştırır; Swift daha çok gizlenir. App Store binary'leri geçmişte FairPlay ile şifreliydi; analiz için çözülmüş (decrypted) kopya gerekir.

Statik analizle hard-coded API anahtarları, endpoint URL'leri, zayıf kripto kullanımı ve kontrol akışı ortaya çıkar. Dinamik analiz (Frida) bunu tamamlar: statikte gizli görüneni runtime'da yakalar.

### Örnek

Bir uygulamada API anahtarının doğrudan koda gömülü (`hardcoded`) olması klasik bir bulgudur. Tersine mühendisle string olarak çekilir. Benzer şekilde, "premium" kontrolünün istemcide bir `if` bloğu olması, o bloğun yamalanıp atlatılabileceği anlamına gelir.

### Tespit ve Savunma

- **Sır gömülmez.** API anahtarları, imzalama sırları istemcide bulunmamalı; gerekiyorsa dar kapsamlı, sunucuda döndürülebilen token'lar kullanılmalı.
- **Kod karıştırma (obfuscation):** İsim gizleme, string şifreleme ve kontrol akışı düzleştirme, tersine mühendisliğin maliyetini yükseltir. **Kesin engel değildir**; kararlı analisti yalnızca yavaşlatır.
- **Bütünlük/imza doğrulama:** Uygulamanın kendi imzasını runtime'da kontrol etmesi, yeniden paketleme (repackaging) girişimlerine karşı bir katmandır — ama bu kontrol de hooklanabilir, o yüzden attestation ile birleştirin.
- **Sunucu tarafı yetkilendirme:** Her yetki ve iş kuralı kararını sunucuda tekrar doğrulayın. İstemcideki hiçbir `if`'e güvenmeyin.
- **Yaygın hata:** Obfuscation'ı güvenlik sınırı sanmak. Obfuscation gizlilik değil, gecikme sağlar.

---

## 5. Sertifika Sabitleme (Certificate/SSL Pinning) ve Atlatılması

### Tanım

**Pinning**, uygulamanın yalnızca önceden bildiği belirli bir sertifikaya veya public key'e ait bağlantıyı kabul etmesidir. Amaç: cihazın güven deposuna eklenmiş sahte/araya-giren CA'lar üzerinden yapılan **MITM (man-in-the-middle)** saldırılarını engellemek.

### Çalışma Mantığı

Normal TLS, cihazın güvendiği herhangi bir CA'nın imzaladığı sertifikayı kabul eder. Saldırgan kendi CA'sını cihaza güvenilir olarak eklerse (test/proxy kurulumu gibi) trafiği çözebilir. Pinning bunu keser: uygulama, sunucudan gelen sertifika zincirinin **beklenen bir pin** (genellikle public key'in SHA-256 özeti) içermesini şart koşar. Eşleşmezse bağlantıyı reddeder.

En sağlam varyant **public key pinning**'dir çünkü sertifika yenilendiğinde anahtar aynı kalırsa pin bozulmaz. Yaygın hata, kısa ömürlü yaprak sertifikayı pinlemektir — yenilemede uygulama kırılır.

### Kök Neden — Neden Atlatılabilir?

Pinning kararı da istemcide, bir doğrulama fonksiyonunda verilir. Bu fonksiyon "zincir geçerli mi?" sorusuna cevap verir. Frida/Objection ile:

- Yüksek seviye TLS doğrulama metotları (platformun ve popüler HTTP kütüphanelerinin sertifika kontrol noktaları) hooklanıp "her zaman geçerli" yapılabilir.
- Objection'ın hazır pinning-bypass rutinleri, bilinen kütüphanelerin kontrol noktalarını topluca devre dışı bırakır.
- Native/statik pinning'de ilgili karşılaştırma disassemble edilip yamalanabilir.

Sonuç: pinning atlatıldığında saldırgan uygulamanın TLS trafiğini proxy üzerinden düz görebilir. **Ancak bu yalnızca o cihazda, o oturumda geçerlidir** — sunucu güvenliğini bozmaz; saldırganın kendi trafiğini analiz etmesini sağlar (uygulama iç işleyişini keşfetmek için).

### Örnek

Bir test cihazında proxy kurulur, proxy'nin CA'sı güvenilir yapılır. Pinning olmasa trafik hemen görülür. Pinning varsa bağlantı reddedilir. Objection ile pinning bypass çalıştırıldığında uygulama proxy sertifikasını kabul eder ve API çağrıları okunabilir hale gelir. Bu, uygulamanın API'sini ve olası zayıf yetkilendirmesini keşfetmenin klasik yoludur.

### Tespit ve Savunma

- **Pinning'i uygulayın ama tek savunma yapmayın.** Pinning, ağ katmanı saldırısını zorlaştırır; ancak kök/hook'lu cihazda atlatılır. Değeri, geniş kitleye/otomatik MITM'e karşı yüksektir.
- **Public key pinning + yedek pin:** Anahtar rotasyonu için birden fazla pin bulundurun ki meşru sertifika yenilemesi uygulamayı kırmasın.
- **Attestation ile birleştirin:** İstek gerçekten değiştirilmemiş uygulamadan mı geliyor sorusunu sunucuda doğrulayın; pinning atlatan istemcinin ürettiği anomali desenlerini izleyin.
- **Sunucu tarafı sağlamlık:** Pinning atlatan bir saldırgan API'yi düz görse bile, sunucu tarafında her endpoint'te yetkilendirme, rate limiting ve girdi doğrulaması sağlamsa gerçek zarar sınırlıdır. **Pinning bir gizlilik/keşif engelidir; yetkilendirme sınırı değildir.**
- **Yaygın hatalar:**
  - Yaprak sertifikayı pinlemek → yenilemede kitlesel çökme.
  - Pinning'i yalnızca bir HTTP istemcisine uygulayıp, uygulamanın başka bir yoldan (WebView, üçüncü parti SDK) yaptığı çağrıları unutmak.
  - Pinning'i "hassas veriyi tek başına koruyan şey" sanmak.

---

## 6. IPC / Intent İstismarı ve Bileşen Güvenliği (Kısa Ama Kritik)

### Tanım

Mobil uygulamalar birbirleriyle ve OS ile bileşenler üzerinden konuşur: Android'de `Activity`, `Service`, `BroadcastReceiver`, `ContentProvider` ve `Intent`; iOS'ta URL şemaları/universal links ve app extension'lar. Yanlış yapılandırılmış bileşenler, başka uygulamaların ayrıcalıklı işlevleri tetiklemesine yol açar.

### Çalışma Mantığı ve Risk

- Android'de bir bileşen **`exported`** ise, başka uygulamalar ona Intent gönderebilir. Yetkilendirme kontrolü zayıfsa, kötü niyetli uygulama korunması gereken işlevi (veri okuma, ayrıcalıklı ekran açma) tetikler.
- **ContentProvider** yanlış izinlerle dışa açıldığında, başka uygulama private veriyi sorgulayabilir.
- **Deep link / URL şeması** doğrulanmadan işleme alınırsa, dışarıdan gelen parametrelerle hassas akış tetiklenebilir (örneğin doğrulama adımını atlayan bir yönlendirme).

### Tespit ve Savunma

- Manifest'te yalnızca gerçekten gerekli bileşenleri `exported` yapın; gerisini kapatın.
- Exported bileşenlere gelen tüm Intent/parametreleri **güvenilmez girdi** kabul edip doğrulayın; ayrıca imza-düzeyi (signature-level) izinlerle koruyun.
- ContentProvider'da satır/erişim düzeyinde yetki uygulayın; `grantUriPermissions`'ı dikkatle yönetin.
- Deep link ile gelen her parametreyi doğrulayın; kimlik/yetki gerektiren akışları deep link'in tek başına açmasına izin vermeyin.
- **Yaygın hata:** `exported`'ı geliştirme kolaylığı için açık bırakıp yayına öyle çıkmak.

---

## Genel Savunma Felsefesi — Katmanların Doğru Sıralaması

1. **Sunucu her zaman gerçek sınırdır.** İstemcideki hiçbir kontrol (jailbreak tespiti, pinning, obfuscation, istemci `if`'leri) yetkilendirme yerine geçmez. Her karar sunucuda yeniden doğrulanmalıdır.
2. **Attestation en dayanıklı istemci sinyalidir.** Play Integrity (Android) ve DeviceCheck/App Attest (iOS) ile üretilen imzalı bütünlük kanıtı, sunucuda doğrulandığında runtime enstrümantasyona ve yeniden paketlemeye karşı en güçlü tekil savunmadır — çünkü hook edilen istemci imzalı yanıtı üretemez.
3. **İstemci kontrolleri "maliyet yükseltir", "sınır çizmez".** Pinning, obfuscation, anti-Frida, kök tespiti — hepsi saldırganı yavaşlatan katmanlardır. Çok sayıda, dağıtık ve tek boolean'a bağlı olmayacak şekilde kurun.
4. **Hassas veri diskten uzak, donanım destekli.** Keychain/Keystore'u doğru erişilebilirlik sınıfı ve kullanıcı doğrulaması ile kullanın; runtime'da çözülen verinin ömrünü kısaltın.
5. **Anomaliyi sunucuda izleyin.** Enstrümante/atlatılmış istemciler tanımlanabilir davranış desenleri üretir; tespiti istemciden çıkarıp sunucudaki telemetriye taşımak, atlatma oyununu saldırganın aleyhine çevirir.

Özetle: mobil güvenlik, istemcinin *düşman toprağı* olduğunu kabul etmekle başlar. Bütün istemci kontrolleri değerlidir ama hiçbiri güvenlik sınırı değildir; gerçek güvenlik, sunucu tarafı yetkilendirme ile kriptografik attestation'ın birleşiminde kurulur.
