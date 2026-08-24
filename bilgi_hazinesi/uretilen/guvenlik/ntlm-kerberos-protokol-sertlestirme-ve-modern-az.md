# NTLM/Kerberos Protokol Sertleştirme ve Modern Azaltmalar

> Eğitim amaçlı referans. Amaç, kimlik doğrulama protokollerinin zayıf noktalarını **anlamak** ve bunlara karşı **savunma/tespit** kurmaktır. Buradaki içerik saldırı talimatı değil; mekanizma, çalışma mantığı, tespit ve sertleştirme odaklıdır.

## Giriş: Saldırı-Savunma Dengesi

Active Directory (AD) ortamlarında **NTLM Relay**, **Pass-the-Hash (PtH)** ve **Kerberos** kötüye kullanımları çok konuşulur; ancak bu saldırıların karşı tarafı olan **protokol sertleştirme** mekanizmaları genellikle dağınık ele alınır. Oysa gerçek dünyada bir saldırının başarılı olup olmaması büyük ölçüde şu üç sorunun cevabına bağlıdır:

1. Kimlik doğrulama trafiği **imzalanıyor / bağlanıyor** mu (signing / channel binding)?
2. Zayıf protokol (NTLM) hâlâ **kullanılabiliyor** mu?
3. Kimlik bilgileri (hash/ticket) bellekte **çalınabilir** durumda mı (Credential Guard)?

Bu makale, bu üç ekseni oluşturan mekanizmaları (LDAP Signing, EPA/Channel Binding, NTLM devre dışı bırakma, Kerberos Armoring/FAST, Credential Guard) derinlemesine açıklar. Her bölümde tanım, kök neden/çalışma mantığı, örnek, tespit + savunma ve yaygın hatalar yer alır.

---

## 1. Temel Kavramlar: NTLM ve Kerberos Neden Zayıflar?

### NTLM'in yapısal sorunu

NTLM, **challenge-response** temelli bir protokoldür. İstemci kullanıcının parolasının hash'ini (NT hash) doğrudan kanıt olarak kullanır; parola hiçbir zaman "tuz" (salt) ile makineye/oturuma bağlanmaz. Bunun iki kritik sonucu vardır:

- **Pass-the-Hash**: NT hash, parolanın kendisi kadar değerlidir. Saldırgan parolayı bilmeden hash ile kimlik doğrulayabilir; çünkü protokol hash'i kanıt olarak kabul eder.
- **Relay edilebilirlik**: NTLM oturumu, hangi TCP/TLS kanalı üzerinden geldiğine **yapısal olarak bağlı değildir**. "Man-in-the-middle" konumundaki bir aktör, bir istemciden gelen kimlik doğrulama mesajlarını başka bir sunucuya **aynen aktararak (relay)** o istemci adına oturum açabilir. NTLM'de challenge, kanalın kimliğini (TLS sertifikası, hedef sunucu adı) içermez.

### Kerberos'un görece güçlü ama kusursuz olmayan yapısı

Kerberos, KDC (Key Distribution Center — pratikte Domain Controller) tarafından imzalanan **ticket**'lara dayanır. NTLM'e göre çok daha güçlüdür çünkü:

- Zaman damgası ve önceden paylaşılmış anahtar (kullanıcı parolasından türetilen anahtar) kullanır.
- Hizmet biletleri (service tickets) hedef hizmete özeldir.

Ancak Kerberos da ön kimlik doğrulama (pre-authentication) aşamasında ve TGT talebinde bazı zayıflıklara açıktır: **AS-REP Roasting** (pre-auth kapalıysa), **Kerberoasting** (zayıf servis hesabı parolaları) ve armoring yoksa AS/TGS değişimlerinin bir kısmının açık kalması gibi.

**Kök fikir:** Sertleştirme mekanizmaları, bu yapısal boşlukları kapatır — ya oturumu kanala bağlayarak (relay'i kırar), ya zayıf protokolü kaldırarak, ya bileti zırhlayarak, ya da kimlik bilgisini bellekte erişilemez kılarak.

---

## 2. LDAP Signing ve LDAP Channel Binding

### 2.1 Tanım

**LDAP**, AD'nin dizin protokolüdür ve Domain Controller (DC) ile yapılan hemen her yönetimsel işlem burada gerçekleşir. İki ilgili sertleştirme özelliği vardır:

- **LDAP Signing (integrity)**: LDAP oturumundaki her mesajın kriptografik olarak imzalanmasını (bütünlük koruması) zorunlu kılar. İmzalanmış oturuma araya girip mesaj enjekte edilemez veya relay edilemez.
- **LDAP Channel Binding (CBT — Channel Binding Token)**: LDAPS (TLS üzerinden LDAP) kullanıldığında, kimlik doğrulama katmanını **alttaki TLS kanalına bağlar**. İstemcinin gördüğü TLS sertifikası ile kimlik doğrulaması aynı kanala aittir; farklı bir kanala relay edilemez.

### 2.2 Kök Neden / Çalışma Mantığı

Klasik NTLM relay senaryosunun en tehlikeli hedeflerinden biri DC'nin LDAP servisidir. Saldırgan, bir kurbanı (örneğin LLMNR/NBT-NS zehirlemesiyle) kendisine NTLM ile kimlik doğrulamaya zorlar, ardından bu kimlik doğrulamayı DC'nin **LDAP** ya da **LDAPS** servisine aktarır. Eğer aktarım başarılı olursa, saldırgan kurbanın yetkisiyle dizinde değişiklik yapabilir (örneğin RBCD — Resource-Based Constrained Delegation ekleme).

Bunu iki katman engeller:

- **Signing**, imzasız (plaintext) LDAP bağlantılarında relay'i kırar; çünkü relay edilen oturum bütünlük anahtarını üretemez.
- **Channel Binding**, LDAPS üzerinde relay'i kırar; çünkü saldırganın DC ile kurduğu TLS kanalının binding token'ı, kurbanın istemcisinin beklediğinden farklıdır. Kanal uyuşmazlığı DC tarafından reddedilir.

> Kritik nüans: Yalnızca signing açmak yeterli değildir. Signing, imzasız bağlantıları korur ama **LDAPS (TLS'li) bağlantılar signing'den muaf sayılır** — çünkü TLS zaten bir bütünlük sağlar. Bu yüzden LDAPS relay'ini durdurmak için **Channel Binding** gereklidir. İki mekanizma birbirini tamamlar; yalnız biri bırakılırsa boşluk kalır.

### 2.3 Örnek Senaryo

Bir yönetici iş istasyonu, hatalı bir isim çözümlemesi sonucu saldırganın makinesine NTLM kimlik doğrulaması gönderir. Saldırgan bunu DC'nin LDAPS servisine aktarmaya çalışır:

- **Channel Binding zorunluysa**: DC, gelen oturumun channel binding token'ının kendi TLS oturumuyla eşleşmediğini görür ve reddeder. Relay başarısız olur.
- **Channel Binding kapalıysa**: Aktarım başarılı olabilir; saldırgan kurbanın yetkisiyle dizin nesneleri üzerinde işlem yapabilir.

### 2.4 Tespit + Savunma

**Savunma:**
- DC'lerde LDAP Signing'i **Require Signing** seviyesine getirin (Group Policy: *Domain controller: LDAP server signing requirements*).
- LDAP Channel Binding'i **Always** (zorunlu) seviyesine getirin. Microsoft, uyumluluğu ölçmek için önce **audit** modunu, sonra enforcement'ı önerir.
- İstemci tarafında da imzalamayı zorunlu kılın (*Network security: LDAP client signing requirements*).

**Tespit:**
- DC'ler channel binding/signing uyumsuzluklarını olay günlüğüne yazabilir (uygun audit ayarı açıkken). Enforcement öncesi bu olayları toplayıp hangi istemcilerin/uygulamaların uyumsuz olduğunu tespit edin.
- Beklenmedik LDAP yazma işlemleri (özellikle `msDS-AllowedToActOnBehalfOfOtherIdentity` gibi delegasyon niteliklerine yazma) relay göstergesidir.

### 2.5 Yaygın Hatalar

- **"Signing açtım, güvendeyim" yanılgısı:** LDAPS relay'i signing ile kapanmaz; channel binding şart.
- **Doğrudan enforcement'a geçmek:** Audit yapmadan zorunlu moda geçmek eski/uyumsuz uygulamaları (bazı yazıcılar, eski LDAP istemcileri, appliance'lar) kırabilir.
- **Sadece DC'yi düşünmek:** İstemci tarafı imzalama politikası unutulursa istemciler imzasız pazarlığa razı olabilir.

---

## 3. SMB Signing ve EPA (Extended Protection for Authentication)

### 3.1 Tanım

- **SMB Signing**, SMB oturumundaki paketlerin imzalanmasını zorunlu kılar; SMB üzerinden relay'i kırar. Modern Windows sürümlerinde SMB signing giderek varsayılan olarak zorunlu hâle getirilmektedir.
- **EPA (Extended Protection for Authentication)**, HTTP(S) ve benzeri TLS'li servislerde channel binding'in genelleştirilmiş adıdır. Kimlik doğrulamayı TLS kanalına bağlar. AD CS Web Enrollment (HTTP tabanlı sertifika kayıt uçları) gibi servisler için kritik önemdedir.

### 3.2 Çalışma Mantığı

EPA, TLS sertifikasından türetilen bir **channel binding token**'ı kimlik doğrulama akışına dahil eder. İstemci ile sunucu arasındaki TLS kanalı ile kimlik doğrulama aynı "kimliğe" sahip olmak zorundadır. Saldırgan araya girip trafiği başka bir TLS kanalına aktardığında token uyuşmaz ve reddedilir.

Bu, özellikle **ADCS relay** sınıfı saldırılarda (bir DC'yi veya makineyi web tabanlı sertifika kayıt ucuna kimlik doğrulamaya zorlayıp onun adına sertifika alma) belirleyicidir: EPA zorunluysa relay çalışmaz.

### 3.3 Tespit + Savunma

**Savunma:**
- SMB Signing'i tüm sunucu ve istemcilerde zorunlu kılın.
- IIS tabanlı AD servislerinde (AD CS Web Enrollment vb.) **EPA'yı Required** yapın ve mümkünse HTTP'yi tamamen kapatıp yalnızca HTTPS bırakın.
- NTLM kimlik doğrulamasını web kayıt uçlarında devre dışı bırakıp yalnızca Kerberos'a izin vermek relay yüzeyini daraltır.

**Tespit:**
- "Authentication coercion" tetikleyicileri (MS-RPRN/PrinterBug, MS-EFSR/PetitPotam benzeri zorlamalar) için beklenmedik makine-hesabı kimlik doğrulama trafiğini izleyin.
- Bir makine hesabının kısa sürede birden çok sertifika talep etmesi ADCS relay işareti olabilir.

### 3.4 Yaygın Hatalar

- EPA'yı yalnızca bir serviste açıp diğer HTTP uçlarını unutmak.
- SMB signing'i "performans" gerekçesiyle kapalı bırakmak — modern donanımda maliyeti pratikte ihmal edilebilirdir.

---

## 4. NTLM'i Kısıtlama ve Devre Dışı Bırakma

### 4.1 Tanım

En kökten azaltma, zayıf protokolü ortamdan kaldırmaktır. Windows, NTLM kullanımını **denetleme (audit)**, **kısıtlama** ve nihayetinde **engelleme** için politikalar sunar (*Network security: Restrict NTLM* politika ailesi). Modern Windows sürümlerinde NTLM'in adım adım kullanımdan kaldırılması resmi bir yön olarak belirtilmiştir; Kerberos'un kapsamı (örneğin IP tabanlı bağlantılar için) genişletilmeye çalışılmaktadır.

### 4.2 Çalışma Mantığı ve Sıralama

NTLM'i doğrudan kapatmak riskli olabilir çünkü birçok eski uygulama, appliance ve senaryo (IP ile bağlanma, çalışma grubu makineleri, bazı SaaS ajanları) hâlâ NTLM'e bel bağlar. Doğru yaklaşım kademelidir:

1. **Audit:** *Restrict NTLM: Audit NTLM authentication in this domain* politikalarını açın. Olay günlüklerinde (Operational NTLM logları) hangi istemci → sunucu çiftlerinin NTLM kullandığını toplayın.
2. **Envanter/istisna:** Gerçekten NTLM'e ihtiyaç duyan uygulamaları belirleyip mümkünse Kerberos'a taşıyın; taşınamayanlar için dar istisna listeleri (*Add server exceptions*) tanımlayın.
3. **Kısıtlama/engelleme:** Gelen/giden/domain NTLM trafiğini adım adım *Deny* seviyesine çekin.

### 4.3 Tespit + Savunma

**Savunma:**
- NTLMv1 ve LM'i kesinlikle yasaklayın (*LAN Manager authentication level* → yalnızca NTLMv2'yi kabul et, LM/NTLMv1 gönderme). NTLMv1 kriptografik olarak zayıftır ve kırılabilir.
- Ayrıcalıklı hesapları **Protected Users** grubuna alın; bu grup üyeleri için NTLM (ve zayıf Kerberos şifrelemesi, delegasyon vb.) kullanımı otomatik olarak engellenir.

**Tespit:**
- NTLM audit olaylarında NTLMv1/LM kullanımı, güncel bir ortamda güçlü bir yanlış yapılandırma ya da saldırı işaretidir.
- Ayrıcalıklı hesapların NTLM ile kimlik doğrulaması (relay veya PtH göstergesi olarak) alarm üretmelidir.

### 4.4 Yaygın Hatalar

- Denetim yapmadan NTLM'i kapatıp iş sistemlerini kırmak.
- NTLMv1'i "geriye uyumluluk" için açık bırakmak — bu, tüm NTLMv2 sertleştirmesini anlamsız kılabilir.
- Protected Users'a servis hesaplarını düşünmeden eklemek; grup, NTLM ve bazı delegasyon senaryolarını kırar, önce test gerekir.

---

## 5. Kerberos Armoring (FAST)

### 5.1 Tanım

**FAST (Flexible Authentication Secure Tunneling)**, RFC 6113 ile tanımlanan bir Kerberos genişletmesidir; Microsoft dünyasında **Kerberos Armoring** olarak bilinir. Amacı, Kerberos ön kimlik doğrulama (pre-authentication) ve bilet değişimlerini bir "zırh (armor)" anahtarıyla korunan güvenli bir tünel içine almaktır.

### 5.2 Çalışma Mantığı

Armoring olmadan, AS-REQ/AS-REP ve TGS değişimlerinin bir kısmı, kullanıcı parolasından türetilen anahtarla korunur. Bu, iki soruna açık kapı bırakır:

- **AS-REP Roasting** ve **çevrimdışı parola tahmini**: Zayıf parolalı bir hesabın ön kimlik doğrulama yanıtı çevrimdışı kaba kuvvete açık olabilir.
- Bazı **downgrade** ve manipülasyon senaryoları.

FAST/Armoring devreye girdiğinde, makinenin (device) TGT'sinden türetilen bir armor anahtarı, kullanıcının kimlik doğrulama akışını dış katmanda şifreler. Böylece:

- Ön kimlik doğrulama verisi çevrimdışı saldırıya karşı zorlaşır.
- KDC hataları da korunur (hata mesajlarından bilgi sızması azalır).
- **Compound Identity** (kullanıcı + cihaz kimliğini birlikte değerlendirme) gibi ileri özellikler mümkün olur.

### 5.3 Örnek

Armoring zorunlu bir alanda, cihaz kimliği doğrulanmadan (geçerli bir armor TGT olmadan) yapılan Kerberos istekleri, KDC politikasına göre reddedilebilir. Bu, çevrimdışı roasting yüzeyini ve bazı relay/downgrade senaryolarını daraltır.

### 5.4 Tespit + Savunma

**Savunma:**
- Armoring'i (KDC ve istemci tarafında Group Policy ile) önce **destekle**, sonra ortam olgunlaştıkça **zorunlu kıl**. Zorunlu mod, armor sağlayamayan eski istemcileri (ör. domaine bağlı olmayan cihazlar) etkileyeceği için kademeli geçiş gerekir.
- Pre-authentication'ın **her hesapta açık** olduğundan emin olun (AS-REP roasting'in ön koşulu pre-auth'un kapalı olmasıdır).

**Tespit:**
- Pre-authentication'ı kapalı hesaplar (`DONT_REQ_PREAUTH` bayrağı) periyodik olarak taranmalı ve raporlanmalıdır — bunlar AS-REP roasting hedefidir.
- Alışılmadık şifreleme türü talepleri (örneğin RC4'e downgrade) Kerberos günlüklerinde izlenmelidir.

### 5.5 Yaygın Hatalar

- Armoring'i tüm istemciler desteklemeden zorunlu kılıp bağlantı sorunları yaratmak.
- Armoring'i açıp pre-auth kapalı hesapları unutmak; iki konu ayrı ele alınmalıdır.

---

## 6. Credential Guard ve Pass-the-Hash'in Engellenmesi

### 6.1 Tanım

**Windows Defender Credential Guard**, sanallaştırma tabanlı güvenlik (VBS — Virtualization-Based Security) kullanarak kimlik doğrulama sırlarını (NT hash, Kerberos TGT ve anahtarları) işletim sisteminin ana belleğinden (LSASS süreci) izole eder.

### 6.2 Çalışma Mantığı

Klasik PtH ve Pass-the-Ticket saldırılarının kökü şudur: LSASS süreci, tekli oturum açma (SSO) için kullanıcının NT hash'ini ve Kerberos anahtarlarını bellekte tutar. Yönetici/SYSTEM yetkisi ele geçiren saldırgan bu belleği okuyup sırları çalabilir.

Credential Guard, bu sırları **izole bir LSA süreci (LSAIso)** içinde, hypervisor tarafından korunan ayrı bir bellek dünyasında (VTL1 — daha güvenilir sanallaştırma katmanı) tutar. Normal işletim sistemi (VTL0), sırların **kendisini** değil yalnızca hypervisor aracılığıyla yapılan kimlik doğrulama işlemlerinin **sonuçlarını** görür.

Sonuç:
- **Pass-the-Hash için gereken NT hash artık düz bellekte bulunmaz.** Saldırgan LSASS'ı okusa bile sırrı çıkaramaz.
- Aynı şekilde **Kerberos anahtarları ve TGT'ler** izole edilir; Pass-the-Ticket zorlaşır.

### 6.3 Önemli Sınırlar (Dürüstlük Notu)

Credential Guard her şeyi çözmez; kapsamını doğru anlamak kritiktir:

- **Yalnızca yerel makinede depolanan/önbelleğe alınan sırları korur.** Ağ üzerinde canlı gerçekleşen bir kimlik doğrulama sırasında oturum devam ederken yapılan **relay** saldırılarını engellemez — o iş signing/channel binding'in görevidir.
- **Klavye kaydı, kimlik avı (phishing) ile parola çalma**, kullanıcının kendisinin girdiği parolayı hedefleyen saldırıları engellemez.
- **NTLMv1/eski protokoller** ortamda hâlâ açıksa, o protokollerin kendi zayıflıkları devam eder.
- Bazı eski uygulama/sürücü uyumsuzlukları olabilir; donanım gereksinimleri (VBS, güvenli önyükleme, uygun CPU özellikleri) vardır. Modern Windows sürümlerinde uygun donanımda varsayılan olarak açılma yönünde ilerlenmektedir.

### 6.4 Tespit + Savunma

**Savunma:**
- Credential Guard'ı ayrıcalıklı ve yönetici iş istasyonlarında öncelikli olarak etkinleştirin.
- **Tiering (katmanlı yönetim)** uygulayın: Tier 0 kimlik bilgileri (Domain Admin) yalnızca Tier 0 sistemlerinde kullanılmalı; bir yöneticinin hash'i sıradan bir iş istasyonuna hiç düşmemelidir.
- **LAPS** ile yerel yönetici parolalarını rastgele/benzersiz kılın; bir makinenin ele geçirilmesi diğerlerine yayılmasın (lateral movement kırılır).

**Tespit:**
- LSASS'a olağandışı erişim/handle açma (Sysmon ile) klasik credential dumping göstergesidir; Credential Guard olsa bile bu davranış izlenmelidir.
- Aynı kullanıcı hash'inin kısa sürede birçok makinede görünmesi PtH/lateral movement işaretidir.

### 6.5 Yaygın Hatalar

- Credential Guard'ı "her şeyi çözer" sanmak; relay ve phishing'i kapsamadığını unutmak.
- Yalnızca birkaç makinede açıp ayrıcalıklı hesapların korumasız makinelere düşmesine izin vermek (tiering eksikliği).
- Donanım/uyumluluk testini atlayarak toplu dağıtım yapmak.

---

## 7. Bütünsel Bakış: Katmanların Nasıl Birlikte Çalıştığı

Hiçbir tek mekanizma tek başına yeterli değildir. Saldırı sınıflarına karşı hangi savunmanın devreye girdiğini bir arada görmek gerekir:

| Saldırı sınıfı | Birincil savunma | Tamamlayıcı |
|---|---|---|
| NTLM Relay → LDAP (imzasız) | LDAP Signing (Require) | NTLM kısıtlama |
| NTLM Relay → LDAPS | LDAP Channel Binding | LDAPS zorunlu |
| NTLM Relay → SMB | SMB Signing (Require) | NTLM kısıtlama |
| NTLM Relay → HTTP/ADCS | EPA (Required) | HTTP kapatma, Kerberos-only |
| Pass-the-Hash / PtT | Credential Guard | Tiering, LAPS |
| AS-REP Roasting | Pre-auth zorunlu | Güçlü parola politikası |
| Kerberoasting | Güçlü servis hesabı parolaları / gMSA | AES şifreleme, RC4 devre dışı |
| Çevrimdışı pre-auth kırma / downgrade | Kerberos Armoring (FAST) | Protected Users |

**Genel ilke — kademeli sertleştirme:** Her mekanizmada önce **audit**, sonra **enforcement**. Doğrudan zorunlu moda geçmek uyumsuz sistemleri kırar ve savunmayı geri almaya zorlar; bu da güvenlik açığının kalıcılaşmasına yol açar. Ölç, envanter çıkar, istisna yönet, sonra zorunlu kıl.

**Zorlama (coercion) yüzeyini unutmayın:** Relay'ler genellikle bir kurbanı kimlik doğrulamaya "zorlayan" (coercion) tetikleyicilerle başlar. Bu tetikleyicileri kapatmak/izlemek, signing ve channel binding kadar önemlidir; savunma derinliği bu iki katmanın birlikte çalışmasıyla oluşur.

---

## 8. Özet

- **NTLM** yapısal olarak relay ve Pass-the-Hash'e açıktır; nihai çözüm onu ortamdan kademeli olarak kaldırmaktır.
- **LDAP Signing** imzasız relay'i, **Channel Binding/EPA** ise TLS'li relay'i kırar; ikisi birlikte gerekir. Sadece signing yeterli değildir.
- **SMB Signing** SMB relay'ini kapatır ve modern Windows'ta giderek varsayılandır.
- **Kerberos Armoring (FAST)** ön kimlik doğrulamayı zırhlayarak çevrimdışı ve downgrade saldırılarını zorlaştırır; pre-auth'un açık olması ayrıca sağlanmalıdır.
- **Credential Guard**, hash ve ticket'ları izole ederek PtH/PtT'yi engeller; ancak **relay ve phishing'i kapsamaz** — bu yüzden tek başına yeterli değildir.
- Tüm mekanizmalarda doğru yöntem: **önce denetle, uyumsuzları düzelt, sonra zorunlu kıl.** Savunma derinliği, bu katmanların ve **tiering/LAPS** gibi mimari önlemlerin birlikte uygulanmasıyla kurulur.

Belirsiz bırakılan noktalar (tam CVE numaraları, kesin sürüm eşikleri, spesifik komut bayrakları) burada kasıtlı olarak kavramsal düzeyde tutulmuştur; kesin operasyonel değerler dağıtımdan önce ilgili resmi belgelerden doğrulanmalıdır.
