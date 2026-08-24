# Mobil Güvenlik (Android / iOS)

Mobil güvenlik, akıllı telefon ve tablet uygulamalarının hem cihaz üzerinde hem de arka uç servisleriyle iletişim sırasında verileri, kimlik bilgilerini ve iş mantığını koruyup korumadığını inceleyen disiplindir. Web güvenliğinden ayrışan yönü, saldırganın çoğu zaman **cihaza fiziksel veya root/jailbreak seviyesinde erişimi olduğu** varsayımıdır. Bir web sunucusunda kod ve veri saldırganın erişemediği bir makinede durur; mobilde ise uygulamanın ikili dosyası (binary), yerel veri tabanları ve çalışan bellek, motive olmuş bir saldırganın kontrolündeki bir cihazda bulunur. Bu yüzden mobil güvenlikte "istemciye asla güvenme" ilkesi teoriden çıkıp somut bir tasarım kısıtına dönüşür.

Bu makale OWASP'ın **MASTG** (Mobile Application Security Testing Guide) ve onunla eşleşen **MASVS** (Mobile Application Security Verification Standard) çerçevesini omurga alarak; yerel depolama, uygulamalar arası iletişim (IPC), tersine mühendislik direnci ve certificate pinning konularını kök nedenleriyle birlikte ele alır.

## MASTG ve MASVS: Neden Bir Çerçeveye İhtiyaç Var

MASVS, mobil uygulamaların karşılaması gereken güvenlik gereksinimlerini kategori kategori tanımlayan bir **standarttır**; MASTG ise bu gereksinimlerin nasıl test edileceğini anlatan **teknik kılavuzdur**. İkisi birlikte, "uygulamam güvenli mi?" sorusunu ölçülebilir bir sürece dönüştürür.

Kök neden şudur: mobil ekosistem parçalıdır. Android'de üretici katmanları, farklı API seviyeleri ve OEM özelleştirmeleri; iOS'ta ise nispeten kapalı ama sürüm sürüm değişen koruma mekanizmaları vardır. Bu parçalılık, "şu ayarı açtım, güvendeyim" tarzı nokta çözümleri güvenilmez kılar. MASVS bunun yerine gereksinimleri seviyelendirir. Kabaca **MASVS-L1** genel amaçlı uygulamalar için temel hijyeni, **MASVS-L2** ise finans, sağlık gibi yüksek riskli uygulamalar için derinlemesine savunmayı hedefler. Ayrıca tersine mühendislik direncini ölçen ayrı bir dizi gereksinim (geçmişte MASVS-R olarak anılan resilience/direnç boyutu) vardır. Bu ayrım kritiktir: **direnç, güvenliğin yerine geçmez, üstüne eklenir.** Bir uygulamanın kodu ne kadar karmaşıklaştırılırsa karmaşıklaştırılsın, arkasında düzgün bir kriptografi ve sunucu tarafı doğrulama yoksa asıl açık kapanmaz.

En sık yapılan kavramsal hata, direnç kontrollerini (obfuscation, root tespiti) gerçek güvenlik kontrolü sanmaktır. Bunlar saldırganın maliyetini artırır ama tek başına belirleyici değildir.

## Yerel Depolama: Cihazdaki Verinin Korunması

### Tanım ve kök neden

Uygulamalar ayarları, oturum token'larını, önbelleği ve kullanıcı verisini cihazda saklar. Sorun, bu depolama alanlarının çeşitli koşullarda **uygulama sınırının dışına sızabilmesidir**: root/jailbreak yapılmış cihaz, cihaz yedeği (backup), adli bilişim imajı, paylaşılan depolama alanı veya kötü niyetli başka bir uygulama.

Android'de her uygulama kendi private dizinine sahiptir (`/data/data/<paket>/`), ve normal koşullarda başka uygulamalar buraya erişemez. Bu izolasyonu sağlayan mekanizma, her uygulamaya ayrı bir Linux UID atanması ve dosya izinlerinin bu UID'ye bağlanmasıdır. iOS'ta ise her uygulama kendi sandbox'ında çalışır ve dosya sistemi erişimi container'la sınırlıdır. Kök neden burada ortaya çıkar: **bu izolasyon işletim sistemi bütünlüğüne bağımlıdır.** Root/jailbreak, tam olarak bu bütünlüğü kırdığı için private dizin artık "private" olmaktan çıkar.

### Somut örnekler

Klasik hata, oturum token'ını veya parolayı düz metin olarak `SharedPreferences` (Android) ya da `NSUserDefaults`/`plist` (iOS) içine yazmaktır. Bu alanlar şifresiz XML/plist dosyalarıdır; root'lu bir cihazda veya bir yedekte doğrudan okunabilir. Bir diğer örnek, SQLite veri tabanına hassas veriyi şifrelemeden koymaktır.

Doğru yaklaşım, işletim sisteminin donanım destekli anahtar deposunu kullanmaktır:

- **Android:** Kriptografik anahtarlar **Android Keystore** içinde üretilir ve mümkünse donanımdaki güvenli öğede (TEE veya StrongBox) tutulur. Buradaki anahtarın önemli özelliği, uygulamanın anahtarın ham baytlarını hiç görmemesidir; sadece "bununla şifrele/çöz" diye çağrı yapar. Modern pratikte hassas veri için Jetpack Security'nin `EncryptedSharedPreferences`/`EncryptedFile` gibi sarmalayıcıları ya da doğrudan Keystore ile şifreleme tercih edilir. (Not: Bu kütüphanelerin bakım durumu sürümden sürüme değişebildiği için, uygulamayı yazdığınız dönemdeki güncel öneriyi doğrulamak gerekir.)
- **iOS:** Hassas kısa veriler (token, anahtar, parola) **Keychain** içinde saklanır. Keychain, donanım destekli koruma sunar ve `kSecAttrAccessible...` erişilebilirlik sınıflarıyla verinin ne zaman okunabilir olacağını belirler. Örneğin cihaz kilitliyken okunamayan bir sınıf seçmek, çalınmış ama kilitli bir cihazda korumayı güçlendirir. `...ThisDeviceOnly` ekli sınıflar, verinin başka cihaza taşınan yedeklere gitmesini engeller.

Büyük veri gövdeleri (dosyalar, veri tabanı) için verinin kendisi bir simetrik anahtarla şifrelenir; o simetrik anahtar Keystore/Keychain'de korunur. Böylece "asıl sır" hiçbir zaman düz olarak diske yazılmaz.

### İstismar mantığı ve savunma

**Saldırgan tarafı:** Root/jailbreak sonrası saldırgan private dizini gezer, düz metin token bulursa oturumu ele geçirir. Yedek üzerinden veri çıkarır. Uygulama arka plana alındığında ekran görüntüsü OS tarafından snapshot olarak diske yazılır; hassas ekranlar bu snapshot'larda sızabilir. Pano (clipboard) üzerinden kopyalanan parolalar başka uygulamalarca okunabilir. Log dosyalarına düşen token'lar `logcat` veya cihaz loglarından toplanabilir.

**Savunma tarafı:**
- Hassas veriyi mümkünse hiç saklama; saklaman gerekiyorsa Keystore/Keychain temelli şifrele.
- Android'de eski `allowBackup` davranışına dikkat et; hassas veriyi yedek dışında tut ya da yedeği düzgün yapılandır.
- Arka plana geçişte hassas ekranı bir örtü (blur/boş ekran) ile maskele ki snapshot sızmasın.
- Loglara asla token/parola/PII yazma; üretim derlemesinde log seviyesini kıs.
- WebView kullanıyorsan cache, form verisi ve `localStorage`'ın hassas veri biriktirmesini engelle.

Yaygın hata: "SharedPreferences private, o yüzden güvenli" varsayımı. Private olması root'lu cihaza karşı değil, sadece normal başka uygulamalara karşı korur.

## Uygulamalar Arası İletişim (IPC)

### Tanım ve kök neden

Mobil uygulamalar birbirinden ve OS'tan yalıtılmıştır; ama tamamen kapalı da değildirler. Bildirim, paylaşım, derin bağlantı (deep link), eklenti gibi işlevler için **bileşenlerin dışarıya açık kapıları** olur. IPC güvenliği, bu kapıların yanlışlıkla fazla açık bırakılmasıyla ilgilidir.

Android'in bileşen modeli bunu belirgin kılar. **Activity, Service, BroadcastReceiver ve ContentProvider** bileşenleri `AndroidManifest.xml` içinde tanımlanır. Bir bileşen `exported="true"` ise (ya da bir `intent-filter` tanımlandığı için örtük olarak exported hale geldiyse) başka uygulamalar ona `Intent` gönderebilir. Kök neden: geliştirici çoğu zaman bileşeni kendi uygulaması içinde kullanmak ister ama farkında olmadan dışarıya açar. iOS tarafında yüzey daha dardır; başlıca IPC kanalları **URL scheme / Universal Links**, paylaşım eklentileri ve pasteboard'dur.

### Somut örnekler ve istismar

- **Exported edilmiş yetkili bir Activity:** Örneğin sadece giriş yapmış kullanıcıya gösterilmesi gereken bir "para transferi onay" ekranı yanlışlıkla exported ise, başka bir kötü niyetli uygulama doğrudan o Activity'yi belirli parametrelerle başlatarak kimlik doğrulama akışını atlayabilir.
- **Korumasız BroadcastReceiver:** Hassas bilgiyi (ör. bir doğrulama kodu) broadcast ile yayan bir uygulama, receiver'ı korumazsa başka uygulama bu broadcast'i dinleyebilir.
- **Yanlış yapılandırılmış ContentProvider:** `grantUriPermissions` ve path izinleri gevşek bırakılırsa, provider'ın arkasındaki veri tabanına parametre enjeksiyonuyla (SQL enjeksiyonu benzeri) veya path traversal ile erişilebilir.
- **Deep link / Intent doğrulaması eksikliği:** Uygulama, gelen bir `Intent`'in içindeki URL'yi veya `extra` alanlarını sorgulamadan güvenip iş yapıyorsa, dışarıdan tetiklenen istenmeyen davranışlar (yetkisiz işlem, açık yönlendirme) mümkün olur. Özellikle bir Intent'in içinde başka bir Intent taşınıp (nested/`PendingIntent`) ayrıcalıklı bir bileşende çalıştırılması tehlikelidir.

### Savunma

- Bileşeni dışarıya açman gerekmiyorsa **`exported="false"`** yap. Modern Android'de `intent-filter` olan bileşenler için `exported`'ı açıkça belirtmek zorunludur; bunu bilinçli seç.
- Dışarıya açman gerekiyorsa özel (signature seviyesinde) **permission** ile koru; böylece sadece aynı anahtarla imzalanmış uygulamalar çağırabilir.
- Gelen tüm `Intent` verisini **güvenilmez girdi** kabul et: doğrula, tip/aralık kontrolü yap, deserialization'a dikkat et.
- ContentProvider'da parametreli sorgu kullan, path izinlerini daralt, gereksiz `exported` provider bırakma.
- iOS'ta Universal Links'i tercih et (alan adı doğrulaması sağlar); ham URL scheme'lere gelen veriyi doğrula, pasteboard'a hassas veri koyma.

Yaygın hata: bir bileşene `intent-filter` eklemenin onu sessizce exported yaptığını fark etmemek. İkinci yaygın hata: IPC ile gelen kimliği (çağıran uygulama) doğrulamadan güvenmek.

## Tersine Mühendislik (Reverse Engineering)

### Tanım ve kök neden

Tersine mühendislik, uygulamanın ikili dosyasından kaynağa yakın bir gösterime ulaşıp mantığını anlama sürecidir. Kök neden yapısaldır: **uygulama kullanıcının cihazında çalışmak zorundadır**, dolayısıyla kod ve içindeki her şey (endpoint'ler, gömülü anahtarlar, iş mantığı) prensipte incelenebilir. Güvenlik açısından tersine mühendislik iki yönlüdür: savunmacı için kendi uygulamasını denetleme aracı, saldırgan için ise açık ve sır avlama aracıdır.

Android uygulamaları çoğunlukla Java/Kotlin'den **DEX bytecode**'a derlenir; bu, orijinal koda oldukça yakın biçimde geri çözülebilir. Bu yüzden Android tarafında tersine mühendislik görece kolaydır. iOS uygulamaları native ARM makine koduna derlenir (App Store dağıtımında ek bir katman şifreleme de vardır); bu yüzden analiz daha zahmetlidir ama imkânsız değildir.

### Somut örnekler ve araç mantığı

Tipik analiz akışı: paketten (Android'de APK/AAB, iOS'ta IPA) dosyaları çıkarmak; statik olarak kodu incelemek (disassembler/decompiler ile); sonra **dinamik analiz** ile çalışan uygulamaya bağlanıp fonksiyonları izlemek. Dinamik analizde en güçlü teknik **instrumentation**'dır: çalışan sürece kod enjekte ederek fonksiyon çağrılarını yakalamak, argümanları/dönüş değerlerini değiştirmek. Bu, örneğin bir doğrulama fonksiyonunun sonucunu her zaman "başarılı" döndürecek şekilde canlıyken (hooking) değiştirmeyi mümkün kılar. (Bu tür araçların spesifik komut bayraklarını burada uydurmuyorum; kavram, çalışan sürecin fonksiyonlarını hook'layıp davranışını değiştirmektir.)

Saldırganın peşinde olduğu şeyler tipik olarak: koda gömülü API anahtarları/sırlar, şifreleme anahtarları, sunucu endpoint'leri ve parametreleri, root/pinning tespitini yapan kod (bunu bulup atlatmak için) ve iş mantığındaki mantık hataları.

### Savunma: direnç ama abartısız

- **Koda sır gömme.** En temel kural: gömülü hiçbir sır (API anahtarı, imzalama sırrı) güvenli değildir; er ya da geç çıkarılır. Sırlar sunucuda kalmalı, istemci en az yetkiyle çalışmalı.
- **Obfuscation** (ör. Android'de ProGuard/R8 ile isim karartma) analizi yavaşlatır; okunabilir sınıf/metot isimlerini kaldırır. Ama bu bir yavaşlatmadır, engelleme değildir.
- **Root/jailbreak tespiti**, **anti-debug**, **integrity/imza doğrulaması** ve **emülatör tespiti** birer direnç katmanıdır. Amaçları saldırganın işini zorlaştırmaktır. Ancak instrumentation ile bu kontroller atlatılabildiği için, kritik kararları **tek başına** bunlara dayandırmak yanlıştır.
- Kritik güvenlik kararları (yetkilendirme, ödeme onayı, lisans doğrulama) mümkün olduğunca **sunucu tarafında** verilmeli. Sunucu, istemcinin manipüle edilebileceğini varsaymalıdır.

Yaygın hata: "kodumu obfuscate ettim, artık kimse pinning'imi kıramaz / anahtarımı bulamaz" güveni. Direnç katmanları maliyeti artırır, kesinlik sağlamaz. İkinci yaygın hata: root tespitini istemcide yapıp sonucu yine istemcide kullanmak; bu sonuç hook'lanabilir.

## Certificate Pinning (Sertifika Sabitleme)

### Tanım ve kök neden

TLS handshake sırasında istemci, sunucunun sunduğu sertifika zincirini cihazın güvendiği kök sertifika deposuna (trust store) göre doğrular. Sorun şudur: cihaza yeni bir güvenilir kök sertifika **eklenebilir**. Kurumsal MDM, kullanıcının kendi eklediği bir proxy sertifikası ya da kötü niyetli biri bir CA'yı ele geçirdiğinde, saldırgan geçerli görünen bir sertifika üretip **man-in-the-middle (MITM)** yapabilir. Uygulama sadece "zincir geçerli mi?" diye baktığı için bu sahte ama teknik olarak geçerli sertifikayı kabul eder.

**Certificate pinning**, uygulamanın yalnızca cihazın güvendiği herhangi bir CA'ya değil, **beklediği belirli sertifikaya veya public key'e** güvenmesini sağlar. Böylece cihaza sonradan eklenen bir kök sertifikayla üretilmiş sahte sertifika, doğru anahtara sahip olmadığı için reddedilir.

### Nasıl çalışır ve somut biçimler

Pinning genelde iki biçimde yapılır:
- **Sertifika pinning:** Belirli bir sertifikanın kendisini sabitlemek. Sertifika yenilenince pin de güncellenmeli; yoksa uygulama sunucuya bağlanamaz.
- **Public key pinning (SPKI):** Sertifikanın public key'inin (veya onun hash'inin) sabitlenmesi. Sertifika yenilense de anahtar aynı kaldıysa pin bozulmaz; bu yüzden operasyonel olarak daha esnektir ve genelde tercih edilir.

Android'de bunu deklaratif olarak yapmanın modern yolu **Network Security Configuration** ile `pin-set` tanımlamaktır; ayrıca OkHttp gibi kütüphanelerin `CertificatePinner` mekanizması vardır. iOS'ta `URLSession` delegesindeki sunucu güven doğrulama (`URLAuthenticationChallenge`) noktasında sunulan anahtar/sertifika beklenen pin'le karşılaştırılır. Her iki platformda da kritik detay, pin karşılaştırmasının doğru katmanda yapılması ve doğrulama başarısızsa bağlantının **kesin olarak reddedilmesidir**.

### İstismar ve savunma

**Saldırgan tarafı:** MITM için tipik akış, cihaz ile sunucu arasına bir proxy koymak ve cihaza proxy'nin kök sertifikasını güvenilir olarak eklemektir. Pinning yoksa tüm trafik okunur ve değiştirilir. Pinning varsa saldırgan tersine mühendislikle pin doğrulama fonksiyonunu bulup instrumentation ile atlatmaya (bypass) çalışır; örneğin doğrulama fonksiyonunu her zaman "geçerli" döndürecek şekilde hook'lar. Bu yüzden pinning, tersine mühendislik direnci ile birlikte anlam kazanır.

**Savunma tarafı:**
- Pinning'i **public key (SPKI) hash** üzerinden yap; sertifika rotasyonunda uygulamanın kırılmaması için.
- **Yedek pin (backup pin)** bulundur. Tek pin'e bağlanırsan, o anahtarı acil değiştirmen gereken bir durumda (anahtar sızıntısı) uygulaman toptan bağlanamaz hale gelir. En az bir yedek pin, güvenli rotasyon sağlar.
- **Pin'in son kullanma / güncelleme stratejisini** planla. Uygulama mağazadan güncellenmeden pin değiştirilemeyeceği için, pin süresi dolduğunda eski istemcilerin ne olacağını düşün.
- Pinning'i savunmanın **tek** katmanı sayma. TLS'in doğru sürümünü zorunlu kıl, zayıf cipher'ları kapat, sertifika doğrulamasını asla tamamen devre dışı bırakma.

**Kritik ve yaygın hata:** Geliştirme sırasında MITM proxy ile test yapabilmek için sunucu doğrulamasını tamamen kapatan (örneğin tüm sertifikaları kabul eden bir `TrustManager` veya "her host'a güven" diyen bir delege) kodun **üretime sızması**. Bu, pinning'in tam tersi bir açıktır: uygulama artık herhangi bir sertifikayı kabul eder ve MITM'e tamamen açıktır. İkinci yaygın hata: yedek pin koymadan pinning yapıp, bir sertifika/anahtar değişiminde tüm kullanıcı tabanını kilitlemek. Üçüncüsü: pinning'i doğru yapıp ama uygulamanın kullandığı bir WebView veya üçüncü parti SDK'nın kendi ağ yığınında pinning uygulanmadığını gözden kaçırmak.

## Genel En İyi Pratikler ve Bütünsel Bakış

Yukarıdaki dört başlık aslında tek bir ilkeye bağlanır: **cihaz ve istemci saldırganın kontrolünde olabilir.** Bu kabulle tasarlanan bir uygulamada güvenlik katmanlıdır ve hiçbir tek kontrol belirleyici değildir.

- **Sunucu tarafını otorite kabul et.** Yetkilendirme, iş kuralları ve hassas hesaplamalar sunucuda doğrulanmalı. İstemci kolaylık ve deneyim içindir, güven sınırı değil.
- **En az veri, en az yetki.** Cihazda tutulan hassas veriyi ve istemciye verilen ayrıcalığı en aza indir. Tutulması zorunlu olan sırrı donanım destekli anahtar deposuyla koru.
- **Girdiyi her yerde doğrula.** IPC ile gelen Intent'ler, deep link'ler, WebView'a giren içerik, tümü güvenilmez girdidir.
- **Kriptografiyi kendin yazma.** Platformun sağladığı Keystore/Keychain ve standart TLS yığınlarını kullan; kendi şifreleme şemanı icat etme.
- **Direnç katmanlarını ekle ama abartma.** Obfuscation, root/jailbreak tespiti, anti-debug ve pinning saldırganın maliyetini artırır. Bunları gerçek kriptografi ve sunucu doğrulamasının yerine değil, üstüne koy.
- **MASVS'i hedef, MASTG'yi yöntem olarak kullan.** Uygulamanın risk seviyesine göre (genel amaçlı mı, finans/sağlık mı) uygun MASVS seviyesini belirle ve test sürecini MASTG üzerinden yürüt. Böylece güvenlik, tek seferlik bir kontrol değil, sürüm sürüm tekrarlanan ölçülebilir bir süreç olur.

Sonuç olarak mobil güvenlik, tekil bir ayar ya da kütüphane değil; **cihazın düşman olabileceği** varsayımını her tasarım kararına yediren bir zihniyettir. Depolamayı donanım destekli koru, IPC yüzeyini daralt, tersine mühendisliğe karşı direnç ekle ama ona bel bağlama, ağ trafiğini pinning ile MITM'e kapat ve asıl güveni her zaman kontrol ettiğin sunucuya yasla.
