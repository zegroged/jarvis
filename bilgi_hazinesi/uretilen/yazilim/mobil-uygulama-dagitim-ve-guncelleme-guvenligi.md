# Mobil Uygulama Dağıtım ve Güncelleme Güvenliği

## Giriş ve Kapsam

Mobil uygulama güvenliği denilince akla genellikle çalışan uygulamanın kendisi gelir: bellek güvenliği, veri saklama, ağ trafiği. Ancak bir uygulamanın kullanıcının cihazına **nasıl ulaştığı** ve **nasıl güncellendiği** en az uygulamanın kendisi kadar kritik bir saldırı yüzeyidir. Saldırganlar, uygulamanın kod satırlarını hiç değiştirmeden, dağıtım ve güncelleme zincirinin bir halkasını ele geçirerek milyonlarca cihaza zararlı kod ulaştırabilir.

Bu makale üç birbirine bağlı katmanı inceler:

1. **Code signing (kod imzalama) ve provisioning zinciri** — uygulamanın kimliğinin ve bütünlüğünün nasıl kanıtlandığı.
2. **OTA (Over-The-Air) / CodePush türü güncelleme kanalları** — uygulamanın store dışından güncellenmesi ve bu kanalların ele geçirilmesi.
3. **App Store inceleme (review) süreci ve atlatma teknikleri** — kötü niyetli davranışın inceleme aşamasında nasıl gizlendiği.

Amaç mekanizmayı anlamak ve **tespit/savunma** kurmaktır. Operasyonel canlı saldırı reçetesi değil; kavramsal çalışma mantığı, gerçekçi tehdit modeli ve savunma stratejisi ele alınır.

---

## 1. Code Signing ve Provisioning Zinciri

### Tanım

**Code signing**, bir uygulama paketinin (iOS'ta `.ipa`, Android'de `.apk`/`.aab`) belirli bir yayıncı tarafından üretildiğini ve dağıtımdan sonra değiştirilmediğini kriptografik olarak kanıtlayan mekanizmadır. Temelde asimetrik kriptografi kullanır: yayıncı özel anahtarıyla (private key) paketin bir özetini (hash) imzalar; işletim sistemi, yayıncının açık anahtarıyla (public key) bu imzayı doğrular.

İki büyük ekosistem farklı güven modelleri kullanır ve bu fark güvenlik açısından belirleyicidir.

### iOS: Merkezi Güven Modeli

iOS'ta güven zinciri Apple'a demirlenmiştir (**centralized trust**):

- Geliştirici, Apple Developer Program üyeliğiyle bir **signing certificate** alır. Bu sertifika, Apple'ın kök otoritesi (Apple Worldwide Developer Relations CA) tarafından imzalanmıştır.
- **Provisioning profile**, uygulamanın hangi cihazlarda, hangi App ID ile, hangi yeteneklerle (entitlements — push, iCloud, keychain paylaşımı vb.) çalışabileceğini belirten, Apple tarafından imzalı bir dosyadır.
- Cihazdaki **AMFI (Apple Mobile File Integrity)** ve kernel seviyesindeki imza doğrulama mekanizması, her çalıştırılabilir sayfanın (executable page) imzasını kontrol eder. İmzasız kodun çalıştırılması engellenir (**code signing enforcement**).

Kritik nokta: iOS, yalnızca uygulamanın başlangıçta imzalı olmasını değil, **çalışma zamanında dinamik kod yükleyememesini** de zorlar. `mmap` ile `PROT_EXEC` sayfa oluşturmak, geçerli bir imza olmadan reddedilir. Bu, "indirdiğim yeni native kodu çalıştırayım" saldırısını platform seviyesinde büyük ölçüde imkânsız kılar (JIT için ayrılmış özel entitlement'lar istisnadır).

### Android: Merkezi Olmayan Güven Modeli

Android farklı çalışır (**decentralized trust**):

- Geliştirici kendi anahtarını üretir (self-signed). Google bir kök otorite olarak imzalamaz; imza yalnızca **aynı imzalayanın ürettiğini** kanıtlar, "kim olduğunu" değil.
- Güvenlik modelinin çekirdeği **update integrity**'dir: bir uygulamanın güncellemesi, ilk sürümüyle **aynı imza anahtarıyla** imzalanmış olmalıdır. Aksi halde sistem güncellemeyi reddeder. Böylece bir saldırgan, yayıncının anahtarına sahip olmadan mevcut bir uygulamanın üzerine güncelleme kuramaz.
- İmza şemaları zaman içinde gelişmiştir: **v1 (JAR signing)** dosya bazlı ve zayıftı; **v2/v3 (APK Signature Scheme)** tüm APK'nın bütününü imzalar ve **v3** anahtar rotasyonuna (key rotation) izin verir; **v4** ise streaming doğrulama için hash ağacı ekler.
- **Play App Signing**: Google Play'e yükleyen geliştiriciler artık imzalama anahtarını Google'a emanet edebilir; geliştirici bir "upload key" ile yükler, Google gerçek dağıtım anahtarıyla imzalar. Bu, anahtar kaybı riskini azaltır ama güven merkezini Google'a kaydırır.

### Kök Neden: Neden İmza Zinciri Kırılır?

İmza matematiği sağlam olsa da pratikte zincir şu noktalardan kopar:

**Özel anahtar sızıntısı.** En yıkıcı senaryo. Yayıncının imzalama anahtarı sızarsa, saldırgan meşru görünen güncellemeler üretebilir. Anahtarlar sıklıkla CI/CD sistemlerinde, geliştirici makinelerinde veya paylaşımlı keystore dosyalarında zayıf parolayla saklanır. Bir keystore parolası zayıfsa, çevrimdışı brute-force mümkündür.

**v1 imza şemasının zayıflıkları (Android).** Tarihsel olarak, JAR imzalama şemasının bütünlüğü tüm dosyayı değil manifesti kapsadığı için, "master key" tipi mantık hataları imzayı bozmadan içeriğin değiştirilmesine izin vermiştir. Bu tür sınıf hataları, imza doğrulaması yapan kodun ayrıştırıcısıyla (parser) kurulum yapan kodun ayrıştırıcısının **aynı dosyayı farklı yorumlaması** (parser differential) kök nedenine dayanır. Modern v2+ şemaları bu yüzey için tasarlanmıştır; bu nedenle "minimum v2 imza şeması zorunlu" politikası temel bir savunmadır.

**Kurumsal / geliştirici imzalama kanallarının kötüye kullanımı (iOS).** iOS'ta App Store dışı dağıtım yolları vardır: **Enterprise (in-house) distribution** ve **ad-hoc / developer** dağıtımı. Enterprise sertifikaları, bir kurumun kendi çalışanlarına store dışı uygulama dağıtması için tasarlanmıştır. Saldırganlar bu sertifikaları kötüye kullanarak, App Store incelemesinden hiç geçmeyen uygulamaları geniş kitlelere "kurumsal uygulama" kisvesinde dağıtmıştır. Kullanıcının profili manuel "güvenilir" işaretlemesi gerekir ki bu sosyal mühendislikle aşılır. Apple bu sertifikaları iptal ederek (revocation) tepki verir, ama iptal ile kötüye kullanım arasında bir gecikme vardır.

### Tespit ve Savunma

- **Anahtar hijyeni:** İmzalama anahtarlarını asla kaynak deposunda tutmayın; HSM veya bulut KMS (donanım destekli anahtar saklama) kullanın. CI/CD'de anahtar erişimini en az ayrıcalıkla ve denetim günlüğüyle sınırlayın.
- **Sertifika sabitleme (pinning) ve doğrulama:** Uygulamanın kendi imza sertifikasını runtime'da kontrol etmesi (özellikle Android'de `PackageManager` üzerinden imza karşılaştırması), yeniden paketlenmiş (repackaged) sürümleri tespit edebilir. Ancak bu kontrol kolayca patch'lenebileceği için tek başına yeterli değildir.
- **Anahtar rotasyonu planı:** Android v3 rotasyonu ve Play App Signing, anahtar ele geçirilmesi durumunda kurtarma yolu sağlar. Bir rotasyon runbook'unuz olsun.
- **İptal izleme:** iOS enterprise sertifikalarının durumunu izleyin; kuruluş olarak dağıttığınız uygulamaların iptal edilme senaryosuna karşı süreklilik planı yapın.

### Yaygın Hatalar

- Debug/test imzalama anahtarını production'a taşımak.
- Anahtarı Slack/e-posta üzerinden paylaşmak veya `.gitignore`'a güvenip anahtarı depoya yanlışlıkla commit etmek.
- Yalnızca imzanın "varlığını" doğrulamak, imzalayanın **kim olduğunu** doğrulamamak. Android'de "imzalı" demek "sizin tarafınızdan imzalı" demek değildir.

---

## 2. OTA / CodePush Türü Güncelleme Kanalları

### Tanım

**OTA (Over-The-Air) güncelleme**, uygulamanın store'a yeni bir sürüm göndermeden, kendi içeriğinin bir kısmını internet üzerinden güncellemesidir. React Native'de **CodePush** (ve halefleri/alternatifleri olan Expo Updates gibi çözümler), asıl JavaScript bundle'ını ve varlıkları (assets) bir sunucudan indirip mevcut native kabuğun üzerine uygular.

Bunun cazibesi büyüktür: bir hata düzeltmesini veya küçük özelliği, günler süren store inceleme kuyruğunu beklemeden dakikalar içinde tüm kullanıcılara ulaştırabilirsiniz.

### Kök Neden: Native Kabuk ile Yorumlanan Katman Ayrımı

OTA'nın mümkün olması, mimari bir ayrımdan kaynaklanır. React Native, Flutter (belirli modlarda), Cordova gibi çerçevelerde uygulama iki katmandan oluşur:

- **Native shell:** Store'dan gelen, imzalı, işletim sisteminin bütünlük kontrolünden geçen kısım.
- **Yorumlanan/paketlenmiş içerik:** JS bundle veya web varlıkları — genellikle native imza kontrolünün doğrudan kapsamı dışında, disk üzerindeki bir dosya olarak saklanır ve runtime'da yüklenir.

Platform imza zorlaması **native machine code** için geçerlidir; yorumlanan bir JS bundle, native kod olmadığı için bu zorlamaya tabi değildir. İşte OTA'nın hem gücü hem de zafiyeti tam olarak burada yatar: **store'un imza garantisi yorumlanan katmanı kapsamaz.**

### Tehdit Modeli: OTA Kanalının Ele Geçirilmesi

Bir saldırgan, OTA güncelleme kanalını ele geçirebilirse, store incelemesini hiç görmeden **tüm kullanıcı tabanına keyfi (yorumlanan) kod** dağıtabilir. Ele geçirme yolları:

**Güncelleme sunucusunun / hesabının ele geçirilmesi.** CodePush dağıtım anahtarları veya hesabı sızarsa, saldırgan meşru güncelleme kanalından zararlı bundle yayınlar. Bu, tedarik zinciri saldırısının klasik biçimidir: tek bir yönetim hesabı, milyonlarca cihaza doğrudan kod yolu açar.

**İmzasız veya doğrulanmayan bundle.** Eğer OTA istemcisi indirdiği bundle'ın kod imzasını (code signing for updates) doğrulamıyorsa, sadece TLS'e güveniyor demektir. TLS kanalın gizliliğini/bütünlüğünü korur ama **sunucunun kendisi ele geçirilirse** işe yaramaz. Bundle imzalama, sunucu ele geçirilse bile saldırganın geçerli imza üretememesini sağlar.

**Man-in-the-middle ve pinning eksikliği.** OTA istemcisi sertifika sabitleme (certificate pinning) yapmıyorsa ve cihaza kötü niyetli bir kök sertifika yüklenmişse, güncelleme trafiği araya girilerek değiştirilebilir.

**Rollback / downgrade saldırısı.** Saldırgan, güncelleme metadata'sını manipüle ederek istemciyi bilinen zafiyetli bir eski bundle'a döndürmeye zorlayabilir. Sürüm numarasının monotonik artışının kriptografik olarak doğrulanmaması bu saldırıyı mümkün kılar.

### Doğru Kullanım

- **Bundle imzalama (mandatory):** OTA bundle'ları imzalanmalı ve istemci **public key'i uygulama içine gömülü** olarak doğrulamalıdır. Böylece güncelleme sunucusu ele geçirilse bile, saldırgan imzalı bundle üretemez. CodePush ve benzeri sistemler bu özelliği "code signing for updates" olarak sunar; **açık değilse açın.**
- **TLS + pinning:** OTA uç noktasına sertifika sabitleme uygulayın. TLS bundle imzalamanın yerine değil, tamamlayıcısıdır.
- **Rollback koruması:** Sürüm numarasını imzalı metadata'nın parçası yapın ve istemcide monotonik kontrol uygulayın; eski sürüme dönüşe izin vermeyin (veya yalnızca imzalı bir "emergency rollback" komutuyla izin verin).
- **Kademeli yayın (staged rollout):** Yeni bundle'ı önce küçük bir yüzdeye açın, telemetriyle çökme/anomali izleyin, sonra yaygınlaştırın. Bu hem operasyonel güvenlik hem de kötü niyetli/hatalı güncellemenin **patlama yarıçapını** sınırlar.
- **En az ayrıcalık:** OTA yayınlama yetkisini ayrı bir role bağlayın, MFA zorunlu kılın, tüm yayınları denetim günlüğüne yazın.

### Tuzaklar ve Yaygın Hatalar

- **"TLS var, güvendeyiz" yanılgısı.** TLS ağdaki saldırganı durdurur; **sunucuyu/hesabı** ele geçiren saldırganı durdurmaz. Bundle imzalaması olmayan bir OTA sistemi, güncelleme altyapısının ele geçirilmesine karşı savunmasızdır.
- **Public key'i sunucudan çekmek.** İmza doğrulama için gerekli public key'i güncelleme sunucusundan indirmek, tüm modeli anlamsız kılar; sunucu ele geçirilirse saldırgan kendi anahtar çiftini gönderir. Public key uygulama binary'sine gömülü ve store imzasıyla korunmalıdır.
- **OTA ile mağaza politikasını dolanmak.** OTA'yı, store'un incelediği davranışı sonradan sessizce değiştirmek için kullanmak yalnızca teknik değil politika ihlalidir (aşağıya bakınız). Platformlar, yorumlanan kodun uygulamanın onaylanmış amacını **önemli ölçüde değiştirmesini** yasaklar.
- **Sonsuz güncelleme döngüleri ve kararlılık:** Hatalı bir OTA bundle çökmeye yol açarsa, cihaz düzeltmeyi indiremeden çökebilir. Bir "safe mode" / son iyi bilinen sürüme geri dönme mekanizması tasarlayın.

---

## 3. App Store İnceleme (Review) Süreci ve Atlatma Teknikleri

### Tanım

Hem Apple App Store hem Google Play, uygulamaları yayına almadan önce bir **review (inceleme)** sürecinden geçirir. İnceleme; otomatik statik/dinamik analiz ve (özellikle Apple'da) manuel insan incelemesinin bir karışımıdır. Amaç kötü amaçlı yazılımı, politika ihlallerini, gizlilik ihlallerini ve kalite sorunlarını yayına çıkmadan yakalamaktır.

İnceleme, dağıtım güvenliğinde bir **kapı bekçisi (gatekeeper)** kontrolüdür. Saldırganların hedefi bu kapıdan kötü niyetli davranışı gizleyerek geçmektir. Bu tekniklerin çalışma mantığını anlamak, savunmacı tarafın (hem platform hem de kurumsal güvenlik ekipleri) neyi araması gerektiğini belirler.

### Kök Neden: İnceleme Ortamı ile Üretim Ortamı Farkı

İnceleme atlatmanın (review evasion) neredeyse tüm biçimleri tek bir temel gerçeğe dayanır: **inceleme sırasında gözlemlenen davranış, gerçek kullanıcıda gözlemlenen davranıştan farklı olabilir.** Uygulama, "şu an inceleniyorum" durumunu tespit edebilirse, incelemede masum, üretimde zararlı davranabilir. Bu, sistemin temel varsayımını — "test ettiğim şey, dağıttığım şeydir" — çürütür.

### Yaygın İnceleme Atlatma Kalıpları (Kavramsal)

Aşağıdakiler, savunma tespiti için bilinmesi gereken **kalıplardır**; adım adım saldırı reçetesi değildir.

**Zaman bombası (time-gating).** Zararlı davranış, uygulamanın yayınlanmasından belli bir süre sonra veya belli bir tarihte etkinleşir. İnceleme dönemi kısa olduğu için tetiklenmez.

**Coğrafi / cihaz kapılaması (geo/device gating).** Kötü davranış yalnızca belirli ülkelerde, dillerde veya belirli cihaz özelliklerinde tetiklenir. İnceleme merkezleri bilinen konumlardan/cihazlardan gelir; uygulama bu profilleri tanıyıp "temiz" davranabilir.

**Sunucu tarafı feature flag ile açma.** Uygulama, davranışını uzak bir sunucudan gelen bir bayrağa (flag) göre değiştirir. İnceleme sırasında sunucu "kapalı" der, uygulama masum görünür; onaydan sonra bayrak açılır. Bu, meşru feature-flag altyapısının kötüye kullanımıdır ve tespiti zordur çünkü ikili dosyada zararlı hiçbir şey yoktur.

**Dinamik/uzak kod yükleme.** Özellikle yorumlanan katmanlarda (OTA/JS bundle, WebView içeriği), asıl mantık inceleme sonrası indirilir. iOS'un native imza zorlaması bunu native kod için engeller, ama yorumlanan içerik ve WebView'de yüklenen uzak JavaScript bu boşluğu istismar edebilir.

**Ortam algılama (anti-analysis).** Uygulama, jailbreak/emülatör/hata ayıklayıcı (debugger) veya bilinen analiz araçlarını algılamaya çalışır. Bu meşru bir anti-tamper tekniğidir; kötüye kullanımda ise "analiz ortamındayım" tespit edilince zararlı davranış susturulur.

**Gizli / ödeme dışı akışlar.** İncelemeye sunulan akışın yanında, yalnızca belirli bir kod/hesapla erişilen gizli bir ekran veya işlev bulunur (örneğin politika dışı ödeme, kumar, içerik). İnceleyen bu akışı görmez.

### Kök Neden Özeti

Bu kalıpların hepsi iki mekanizmadan birine dayanır:
1. **Davranışın dışsal bir girdiye (zaman, konum, sunucu bayrağı, uzak kod) bağlanması** — böylece binary statik olarak temizdir.
2. **İnceleme ortamının tanınması** — böylece dinamik analiz de aldatılır.

Bu yüzden yalnızca statik analiz **veya** yalnızca kısa süreli dinamik analiz yetersizdir.

### Savunma ve Tespit (Platform ve Kurumsal Perspektif)

**Platform tarafı:**
- **Ortam çeşitlendirme:** İnceleme cihazlarının/IP'lerinin parmak izini gizlemek, gerçek kullanıcı ortamlarını taklit etmek, farklı coğrafyalardan çalıştırmak.
- **Uzun kuyruklu / gecikmeli analiz:** Yayından sonra da davranışı izlemek; zaman bombalarını yakalamak için sürekli izleme.
- **Sunucu iletişimi analizi:** Uygulamanın feature-flag/config uç noktalarına yaptığı çağrıları modelleyip anomalileri (yayın sonrası davranış değişimi) tespit etmek.
- **Yorumlanan kod politikası:** OTA/uzak kodun uygulamanın onaylı amacını değiştirmesini yasaklamak ve teknik olarak izlemek.

**Kurumsal / MDM tarafı (kendi cihaz filonuzu koruyorsanız):**
- Yalnızca imzalı ve bilinen yayıncılardan uygulama; **enterprise sertifika kötüye kullanımına** karşı yüklü profilleri denetlemek.
- Ağ seviyesinde, uygulamaların beklenmedik uç noktalarla konuşmasını izlemek (OTA/config çağrılarının anomali tespiti).
- MDM ile store dışı kurulumu ve "güvenilmeyen geliştirici" profillerini kısıtlamak.

**Geliştirici tarafı (kendi uygulamanızı savunuyorsanız):**
- OTA'ya yalnızca imzalı bundle koymak, public key'i gömmek, rollback koruması eklemek (Bölüm 2).
- Feature-flag altyapısını denetlenebilir kılmak: kim, ne zaman, hangi bayrağı açtı — audit log.
- Anti-tamper tekniklerini savunma amacıyla kullanmak; ama bunun tek katman olmadığını, kararlı bir saldırgan tarafından atlatılabileceğini bilmek.

### Yaygın Hatalar

- **İncelemeyi tek savunma sanmak.** İnceleme bir örnekleme/tarama kontrolüdür; zaman/konum/bayrak kapılamasına karşı garanti değildir. Yayın sonrası izleme şarttır.
- **Feature-flag ile "gizli davranış" arasındaki çizgiyi bulanıklaştırmak.** Meşru kademeli yayın ile "incelemeyi kandırmak için davranış saklama" arasındaki fark niyet ve şeffaflıktır. İkincisi platform politikası ihlalidir ve uygulamanın kaldırılmasıyla sonuçlanır.
- **Anti-analiz tekniklerini aşırı yorumlamak.** Emülatör/jailbreak tespiti meşru olsa da, çok agresif tespit meşru güvenlik araştırmacılarını ve hata avcılarını da engeller; ayrıca yanlış pozitiflerle gerçek kullanıcıları bloke edebilir.

---

## Bütünsel Bakış: Zincirin Zayıf Halkası

Üç katman aslında tek bir güven zincirinin halkalarıdır:

1. **Code signing**, "bu binary gerçekten yayıncıdan geldi ve değişmedi" der — ama yalnızca **native/imzalı kısım** için.
2. **OTA**, imzalı kabuğun içine store denetimi görmemiş **yorumlanan kod** enjekte eder — bu, imza garantisinin dışındaki bir yüzeydir.
3. **Review**, kötü niyetli davranışı yayından önce yakalamayı hedefler — ama davranış dışsal girdilere bağlanınca **statik/kısa dinamik analiz** yetersiz kalır.

Savunmanın altın kuralı **defense in depth**'tir: hiçbir tek katmana güvenmeyin. Code signing'i doğru anahtar hijyeniyle koruyun; OTA'yı bundle imzalama, pinning ve rollback korumasıyla sağlamlaştırın; review'i sürekli yayın-sonrası izlemeyle destekleyin. En zayıf halka — genellikle sızmış bir imzalama anahtarı veya ele geçirilmiş bir OTA hesabı — tüm zincirin gücünü belirler.

### Pratik Kontrol Listesi

- İmzalama anahtarları HSM/KMS'te, CI/CD erişimi en az ayrıcalıkla ve denetim günlüğüyle.
- Android'de minimum v2+ imza şeması; anahtar rotasyon planı hazır.
- iOS'ta enterprise sertifika kullanımının denetimi ve iptal izleme.
- OTA bundle imzalama **zorunlu**; public key uygulamaya gömülü; rollback/downgrade koruması aktif.
- OTA uç noktasında TLS + sertifika sabitleme.
- Kademeli yayın + telemetri ile patlama yarıçapı sınırlaması.
- Feature-flag değişikliklerinin tam audit log'u.
- Yayın sonrası davranış izleme ve config/OTA çağrılarının anomali tespiti.
