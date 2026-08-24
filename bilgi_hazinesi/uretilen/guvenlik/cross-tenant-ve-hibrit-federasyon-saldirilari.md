
# Cross-Tenant ve Hibrit Federasyon Saldırıları (AD FS Golden SAML, Guest/B2B Kötüye Kullanımı, Tenant-to-Tenant Pivot)

## Giriş: Neden Bu Konu Kritik

Kurumsal kimlik altyapısı artık tek bir sınırla tanımlanamıyor. Klasik Active Directory ormanının duvarları, bulut kimlik sağlayıcılarıyla (özellikle Microsoft Entra ID, eski adıyla Azure AD) kurulan federasyon güven ilişkileriyle delinmiş durumda. Bir organizasyon artık yalnızca kendi ormanını değil; federasyon kurduğu her ortağı, güvendiği her IdP'yi (Identity Provider) ve davet ettiği her guest kullanıcıyı da saldırı yüzeyine dahil ediyor.

Bu konu üç ayrı ama birbirine sıkı bağlı tehdit vektörünü kapsar:

1. **AD FS Golden SAML**: Şirket içi AD FS sunucusundan token imzalama sertifikasının çalınmasıyla, kimlik doğrulama sürecini tamamen atlayıp herhangi bir kullanıcı (dahil Global Admin) adına sahte SAML token üretme.
2. **Guest/B2B kötüye kullanımı**: Microsoft Entra B2B ile davet edilen dış (guest) hesapların yanlış yapılandırma veya yetki sızıntısı yoluyla yatay/dikey hareket için kullanılması.
3. **Tenant-to-tenant pivot**: Bir kiracıda (tenant) elde edilen erişimin, cross-tenant senkronizasyon, guest ilişkileri veya paylaşılan federasyon güveni üzerinden başka kiracılara sıçratılması.

Bunların hepsinin ortak paydası şudur: klasik "domain admin oldum, iş bitti" zihniyetinin artık yeterli olmaması. Saldırgan artık kimlik sınırının *ötesine* geçebiliyor ve bunu genellikle EDR/SIEM'in görüş alanı dışında, bulut tarafı loglama boşluklarından faydalanarak yapıyor. Savunma tarafında bu, "AD güvenliği" ile "bulut kimlik güvenliği" ekiplerinin artık ayrı çalışamayacağı anlamına geliyor — saldırgan bu ayrımı tanımıyor.

---

## Bölüm 1: AD FS Golden SAML

### 1.1 Tanım ve Kavramsal Temel

AD FS (Active Directory Federation Services), şirket içi AD kimlik doğrulamasını bulut servislerine (Microsoft 365, Entra ID veya üçüncü taraf SaaS) federe etmek için kullanılan bir STS'dir (Security Token Service). Kullanıcı bir bulut kaynağına erişmek istediğinde, AD FS'e yönlendirilir, orada kimlik doğrulanır ve AD FS kullanıcı adına dijital olarak **imzalanmış** bir SAML token üretir. Bu token, güvenilen tarafa (relying party — örneğin Entra ID) sunulur ve o taraf token'ın imzasını doğrulayarak kullanıcıyı güvenilir kabul eder.

"Golden SAML" terimi, "Golden Ticket" (Kerberos) saldırısıyla kavramsal benzerlikten geliyor: her ikisinde de saldırgan, kimlik doğrulama sürecinin **kendisini** atlayıp, sürecin **çıktısını taklit etmek** için gereken kriptografik malzemeyi (imzalama anahtarı/sertifikası) ele geçiriyor. AD FS'te bu malzeme, token imzalama sertifikasının özel anahtarıdır.

### 1.2 Kök Neden / Çalışma Mantığı

Buradaki kök neden, güven zincirinin **tek bir kriptografik nesneye** indirgenmiş olmasıdır: token imzalama sertifikası. Relying party (Entra ID dahil), gelen SAML token'ının imzasını bu sertifikanın genel anahtarıyla doğrular; imza geçerliyse token'a güvenir — token'ı *kimin, nasıl, hangi bağlamda* ürettiğini sorgulamaz. Yani güven modeli "imza doğruysa doğrudur" mantığına dayanır, ve bu imza doğru olduğu sürece backend AD FS sunucusunun o token'ı gerçekten "meşru" bir kimlik doğrulama akışında üretip üretmediğini denetleyen ikinci bir mekanizma genellikle yoktur.

AD FS token imzalama sertifikasının özel anahtarı düz metin olarak saklanmaz; **DKM (Distributed Key Manager)** adı verilen bir mekanizma aracılığıyla AD'de (Configuration Partition altında, AD FS hizmet hesabının erişebileceği bir konteyner içinde) şifrelenmiş olarak tutulur. DKM'nin şifre çözme anahtarı, AD FS hizmet hesabının AD'deki izinlerine ve AD FS sunucusunun kendisine (DPAPI/makine bağlamı) bağlıdır.

Saldırganın izlediği mantıksal zincir şudur:
- AD FS sunucusuna (yerel Administrator) veya AD FS hizmet hesabının/DKM konteynerinin okunabileceği bir bağlama (örneğin Domain Admin) erişim sağla.
- DKM konteynerindeki şifreli materyali AD'den oku (LDAP sorgusu ile; bu bir "gizli" ACL korumalı obje değil, çoğu ortamda sadece hizmet hesabı ve yöneticilerin erişebildiği bir configuration partition objesidir).
- AD FS sunucusu bağlamında (veya hizmet hesabı kimlik bilgileriyle) şifreyi çöz ve token imzalama sertifikasının özel anahtarını elde et.
- Bu özel anahtarla, AD FS'in normal kimlik doğrulama akışını hiç tetiklemeden, istediğin herhangi bir kullanıcı için (UPN, immutableID, roller dahil) elle SAML token imzala.
- Bu sahte token'ı doğrudan relying party'ye (Entra ID) sun; Entra ID imzayı doğrular, geçerli bulur ve oturum açar.

Buradaki en kritik nokta: **saldırgan artık AD FS sunucusuna hiç dokunmadan, hatta AD FS sunucusu çökmüş/kapatılmış olsa bile**, bu sertifika elinde olduğu sürece istediği zaman istediği kimlikte token basabilir. Bu da onu MFA, Conditional Access politikaları (bazı senaryolarda) ve şifre değişikliklerinden bağımsız kılan, son derece kalıcı bir erişim tekniği haline getirir.

### 1.3 Neden Bu Kadar Güçlü (ve Tehlikeli)

- **MFA'yı atlar**: Token zaten "kimlik doğrulanmış" olarak imzalandığı için, relying party ikinci bir faktör istemez — federasyon modelinde MFA genelde IdP tarafında (AD FS'te) uygulanır, relying party bunu tekrar sorgulamaz.
- **Parola değişikliğinden etkilenmez**: Kullanıcının AD parolası değişse dahi, sahte token kullanıcı hesabının parolasına bağlı değildir; imzalama sertifikasına bağlıdır.
- **Herhangi bir kimliği taklit edebilir**: Saldırgan sadece var olan bir kullanıcıyı değil, teorik olarak var olmayan roller/iddialar (claims) da enjekte edebilir — örneğin Global Admin rolüne karşılık gelen bir claim seti.
- **Sertifika döndürülmedikçe kalıcıdır**: Token imzalama sertifikaları genelde uzun ömürlüdür (varsayılan olarak yıllar mertebesinde) ve rutin olarak döndürülmez.

### 1.4 Tespit

Golden SAML'i tespit etmek zordur çünkü üretilen token, kriptografik olarak "geçerli" görünür — imza doğrudur. Tespit noktaları şu katmanlara ayrılır:

**AD FS sunucusu tarafı (kaynak erişim izleri):**
- DKM konteynerine yönelik olağandışı LDAP sorguları (özellikle AD FS hizmet hesabı dışındaki hesaplardan gelen, `CN=ADFS,CN=Microsoft,CN=Program Data` benzeri configuration partition yollarına erişim). Bu, doğru yapılandırılmış AD denetim politikalarıyla (object access auditing, SACL) izlenebilir.
- AD FS sunucusuna yerel/RDP oturum açma olayları, özellikle normalde bu sunucuya bağlanmayan hesaplardan.
- AD FS hizmet hesabının olağandışı bağlamda (farklı bir makineden, interaktif oturumla) kullanılması.

**Token/oturum tarafı (relying party — Entra ID):**
- Entra ID sign-in loglarında, **beklenmedik IP/coğrafya/cihazdan** gelen ama "başarılı federasyon girişi" olarak görünen oturumlar — özellikle Conditional Access'in "atlanmış" göründüğü ya da hiç MFA istemi tetiklenmeden tamamlanan girişler.
- `NotBefore`/`NotOnOrAfter` alanları ile token'ın gerçek üretim zamanı arasında tutarsızlık; ya da token yaşam süresinin AD FS'in kurumsal politikasıyla uyuşmaması.
- IssuerID/Certificate thumbprint izleme: Aynı sertifika ile normalde beklenen hacimden çok farklı bir hızda/paternde token üretimi (bu, merkezi loglama olmadan AD FS tarafında görülmez, ancak Entra ID tarafında oturum sıklığı anomalisi olarak iz bırakabilir).
- Microsoft'un yayımladığı ilgili tespit araçları (örneğin AD FS token imzalama sertifikası export/erişim olaylarını izleyen betikler) ve Entra ID Identity Protection'ın "atypical travel" veya "anomalous token" tipi risk sinyalleri destekleyici kanıt sağlayabilir.

**Genel prensip**: Golden SAML tespitinin özü, "token geçerli mi" sorusundan "bu token'ın üretildiği bağlam mantıklı mı" sorusuna geçmektir — yani davranışsal/bağlamsal analiz, saf kriptografik doğrulamanın yerini almalıdır.

### 1.5 Savunma

- **DKM/token imzalama sertifikasına erişimi minimize et**: AD FS sunucularını Tier-0 varlık olarak ele al; sadece sıkı kontrollü, PAW (Privileged Access Workstation) üzerinden yönetim yap.
- **AD FS sunucularını izole et**: Gereksiz ağ erişimini kapat, RDP'yi jump host üzerinden sınırla, yerel yönetici grubu üyeliğini minimumda tut.
- **Sertifika rotasyonu**: Token imzalama sertifikasını düzenli aralıklarla (ve şüpheli bir olaydan hemen sonra) döndür; AD FS varsayılan olarak "auto certificate rollover" sunar, bunu aktif tut ve izle.
- **Modern federasyon protokolüne geçişi değerlendir**: Mümkünse kritik/yüksek riskli senaryolarda AD FS yerine Entra ID native (password hash sync / pass-through authentication) modeline geçiş, federasyon güven yüzeyini tamamen ortadan kaldırır. Bu en güçlü yapısal savunmadır — saldırı yüzeyinin kendisini yok eder.
- **Conditional Access ile bulut tarafında bağımsız katmanlar kur**: Device compliance, sign-in risk, location tabanlı politikalar; bunlar federasyon tarafında atlatılsa bile bulut tarafında ek sürtünme yaratabilir (örneğin token replay/impersonation girişimlerinde cihaz uyumluluğu talebi).
- **AD FS olay günlüklerini merkezi SIEM'e taşı**, DKM erişimi ve sertifika export olaylarına özel alarm kur.
- **Federasyon güvenini düzenli denetle**: `Get-MsolDomainFederationSettings` (veya güncel Graph/PowerShell eşdeğerleri) ile hangi domain'lerin federe olduğunu, IssuerURI ve sertifika parmak izlerini periyodik doğrula; beklenmedik değişiklik kırmızı bayraktır.

### 1.6 Yaygın Hatalar

- AD FS sunucusunu "sadece bir SSO aracı" sanıp Tier-0 seviyesinde korumamak.
- Token imzalama sertifikasını yıllarca hiç döndürmemek.
- DKM konteynerine yönelik ACL/SACL denetimini hiç kurmamış olmak — yani bu erişim türü loglanmıyor bile.
- Federasyon güvenini kurduktan sonra "kur ve unut" yaklaşımı; IssuerURI/sertifika değişikliklerinin izlenmemesi.

---

## Bölüm 2: Guest/B2B Kötüye Kullanımı

### 2.1 Tanım ve Kavramsal Temel

Microsoft Entra B2B (Business-to-Business), bir organizasyonun kendi kiracısına dış kullanıcıları (ortak şirket çalışanları, danışmanlar, müşteriler) "guest" olarak davet edip, onlara kendi kimlik bilgileriyle (kendi kiracılarındaki hesap ya da kişisel Microsoft/Google hesabı) sınırlı erişim vermesini sağlayan bir federasyon-benzeri modeldir. Guest kullanıcı teknik olarak host tenant'ın dizinine bir kullanıcı nesnesi olarak eklenir ama kimlik doğrulaması kendi "home" tenant'ında gerçekleşir — bu da onu **çapraz kiracı güven ilişkisinin** en yaygın günlük örneği yapar.

### 2.2 Kök Neden

Kök neden, B2B modelinin doğası gereği **"kolaylaştırma" ile "izolasyon" arasında bir gerilim** taşımasıdır. Guest erişimini kolaylaştırmak için tasarlanan varsayılan ayarlar (örneğin "tüm üyeler guest davet edebilir", varsayılan guest izin seviyesinin üyeye yakın olması) genellikle güvenlikten çok kullanılabilirlik lehine ayarlanmıştır. Sonuç olarak:

- Guest hesapları, host tenant'ta genellikle **üye (member) kullanıcılara çok yakın görünürlük** kazanır (dizin okuma, grup üyeliklerini görme, bazen uygulama listelerini keşfetme).
- Kaynak paylaşımı (SharePoint, Teams, uygulama rol ataması) genellikle **guest'in kim olduğu ve ne kadar güvenilir olduğu** yeterince sorgulanmadan, "e-posta davet et → kabul et → eriş" akışıyla otomatikleşmiştir.
- Guest hesabının kendi "home" tenant'ındaki güvenlik duruşu (MFA var mı, hesap ele geçirilmiş mi) **host tenant'ın kontrolü dışındadır** — host, guest'in kimlik doğrulama gücünü miras alır ama onu doğrudan yönetemez.
- Cross-tenant access ayarları (inbound/outbound trust — MFA/cihaz uyumluluğu güvenini diğer kiracıdan "miras alma") yanlış yapılandırılırsa, host tenant kendi Conditional Access sıkılığını fiilen dış kiracıya devretmiş olur.

### 2.3 Nasıl Çalışır (Kavramsal) — Saldırgan Bakış Açısı

1. **Keşif**: Saldırgan (veya ele geçirdiği bir hesap), hedef organizasyonun hangi dış domain'lerle guest ilişkisi olduğunu keşfeder (Teams/SharePoint paylaşımları, Entra ID dizin sorguları, `Get-MgUser` / Graph API üzerinden guest filtreleme).
2. **İlk erişim vektörleri**: 
   - Meşru bir dış ortaklık üzerinden davet edilmiş, sonradan ele geçirilmiş bir guest hesabı.
   - Self-service guest davet akışının kötüye kullanılması (bazı organizasyonlarda herhangi bir çalışan dışarıdan birini guest olarak davet edebilir; saldırgan sosyal mühendislikle kendi kontrolündeki bir hesabı davet ettirtebilir).
   - Guest hesabının kendi home tenant'ının ele geçirilmesi (host tenant hiç ihlal edilmeden, sadece güvenin geldiği kaynak tenant çökertilerek).
3. **Yanal hareket / yetki yükseltme**: Guest hesabı host tenant içinde;
   - Aşırı geniş paylaşılmış kaynaklara (yanlışlıkla "herkese" veya "organizasyondaki herkese" paylaşılmış dosyalar/siteler) erişir.
   - Guest'e host tarafından yanlışlıkla atanmış aşırı roller (örneğin bir uygulama yöneticisi rolü) varsa bunları kullanır.
   - Dizin keşfi yaparak iç yapı, grup üyelikleri, admin hesap adlandırma kalıpları hakkında istihbarat toplar (sonraki phishing/spear-phishing için).
4. **Kalıcılık**: Guest hesabı silinmediği/gözden geçirilmediği sürece (çoğu organizasyon guest erişimini periyodik gözden geçirmez), uzun süre sessiz bir arka kapı olarak kalabilir.

### 2.4 Tespit

- **Guest hesap envanteri ve anomali izleme**: Entra ID'de `userType eq 'Guest'` filtresiyle düzenli envanter çıkar; beklenmeyen yeni guest davetlerini (özellikle bilinmeyen/serbest e-posta domainlerinden — gmail, outlook.com gibi kişisel hesaplardan gelen davetleri) izle.
- **Sign-in loglarında guest davranış analizi**: Guest hesabının normalde erişmediği kaynaklara (özellikle hassas SharePoint siteleri, iç uygulamalar) erişim denemesi.
- **Cross-tenant access ayarları denetimi**: Hangi dış tenant'lara "inbound trust" (MFA/cihaz uyumu güvenini kabul etme) verildiğini düzenli denetle; bu ayarların sessizce genişletilip genişletilmediğini izlemek kritik.
- **Guest rol atama denetimi (access reviews)**: Entra ID Access Reviews özelliğiyle guest hesaplarına atanmış rol ve grup üyeliklerinin periyodik, otomatik gözden geçirmesini kur; onaylanmayan guest'ler otomatik olarak devre dışı bırakılmalı.
- **Paylaşım telemetrisi**: SharePoint/OneDrive/Teams paylaşım loglarında "Everyone including guests" tipi geniş paylaşımların ne zaman, kim tarafından, hangi kaynağa yapıldığını izle — DLP ve paylaşım politikası ihlali olarak alarm üret.

### 2.5 Savunma

- **En az ayrıcalık ile guest varsayılanları**: Guest kullanıcı izin seviyesini "sınırlı" olarak ayarla (dizin keşfini, diğer kullanıcı/grup görünürlüğünü kısıtla).
- **Guest davet iznini sınırla**: "Kim guest davet edebilir" ayarını sadece yetkilendirilmiş roller ile sınırla (herkesin davet edebildiği varsayılan yapılandırmadan uzaklaş).
- **Cross-tenant access policy'lerini varsayılan-reddet mantığıyla kur**: Sadece bilinen, iş gerekçesi olan ortak tenant'lara özel (organization-specific) inbound/outbound güven tanımla; genel varsayılanı kısıtlayıcı tut.
- **Erişim gözden geçirmelerini (access reviews) zorunlu ve periyodik yap**: Guest hesapları için otomatik son kullanma tarihi (guest expiration policy) tanımla; kullanılmayan guest hesaplarını otomatik temizle.
- **Conditional Access'i guest'lere de tam uygula**: Guest kullanıcılar için de MFA zorunluluğu, cihaz uyumluluğu ve konum tabanlı kısıtlamalar tanımla — "guest olduğu için daha az kontrol" yaklaşımından kaçın.
- **Hassas kaynaklarda guest erişimini tamamen engelle**: Kritik SharePoint siteleri, hassas uygulamalar için "guest erişimine kapalı" politikası uygula; segmentasyon prensipiyle guest'lerin varsayılan olarak hiçbir hassas kaynağa erişemeyeceği bir mimari kur.

### 2.6 Yaygın Hatalar

- Guest hesaplarını "geçici, önemsiz" kabul edip erişim gözden geçirmesine hiç dahil etmemek.
- Self-service guest davetini kısıtlamadan bırakmak.
- Cross-tenant access ayarlarını hiç özelleştirmeden Microsoft varsayılanlarında bırakmak (varsayılanlar genelde daha "açık" davranış sergiler).
- Guest hesaplarına, iç kullanıcı gibi geniş rol/grup ataması yapmak ("kolaylık olsun" diye).

---

## Bölüm 3: Tenant-to-Tenant Pivot

### 3.1 Tanım ve Kavramsal Temel

Tenant-to-tenant pivot, bir kiracıda elde edilen erişimin — guest ilişkileri, cross-tenant senkronizasyon (Entra ID Cross-Tenant Synchronization / CTS), paylaşılan federasyon güveni veya çoklu kiracı yönetim modelleri (örneğin Microsoft Entra Lighthouse, GDAP — Granular Delegated Admin Privileges, ya da CSP/partner ilişkileri) üzerinden — başka bir kiracıya sıçratılmasıdır. Bu, özellikle çok şirketli holding yapılarında, M&A (birleşme/satın alma) sonrası hâlâ ayrı duran ama kısmen entegre edilmiş kiracılarda, veya MSP (Managed Service Provider) müşteri ilişkilerinde kritik bir risktir.

### 3.2 Kök Neden

Kök neden, çoklu kiracı yönetimini kolaylaştırmak için tasarlanan mekanizmaların (CTS, GDAP, Lighthouse, guest-tabanlı yönetim delegasyonu) **her biri kendi kiracı sınırını aşan, kalıcı bir güven kanalı** oluşturmasıdır. Bu kanallar genelde:

- **Tek yönlü değil çift yönlü görünürlük** taşıyabilir (özellikle CTS'de otomatik senkronizasyon kuralları doğru kısıtlanmazsa).
- **Merkezi olarak denetlenmesi zor**dur çünkü her kiracının kendi güvenlik ekibi, kendi loglama pratiği vardır; saldırı izleri iki ayrı güvenlik telemetrisi arasında bölünür ve hiçbir taraf tam resmi göremez.
- **MSP/partner ilişkilerinde aşırı geniş yetki** ile kurulur — GDAP öncesi eski CSP delege yönetici modelinde partner'a Global Admin benzeri geniş roller verilebiliyordu; bu tek bir partner kiracısının ihlalinin, ona bağlı **onlarca müşteri kiracısının** ele geçirilmesine yol açabileceği anlamına gelir (gerçek dünyada MSP zincirleme ihlalleri bu desenle gerçekleşmiştir).

### 3.3 Nasıl Çalışır (Kavramsal)

- **CTS (Cross-Tenant Synchronization) istismarı**: İki kiracı arasında kullanıcı senkronizasyonu kurulduğunda, kaynak kiracıda bir kullanıcı nesnesi/grup üyeliği manipüle edilirse, bu değişiklik otomatik olarak hedef kiracıya senkronize kullanıcı olarak yansıyabilir. Kaynak kiracıda yetki yükseltme yapan bir saldırgan, senkronizasyon kapsamına giren bir grup/rol atamasıyla hedef kiracıda da otomatik olarak eşdeğer erişim kazanabilir.
- **MSP/partner delegasyon zinciri istismarı**: Saldırgan bir MSP'nin kendi kiracısını ele geçirirse, o MSP'nin GDAP/delege yönetici ilişkisi olduğu **tüm müşteri kiracılarına** partner bağlamından erişebilir. Bu, "tek ihlal, çoklu kurban" senaryosunun klasik örneğidir — saldırgan güvenlik açısından en zayıf halkayı (genelde küçük bir MSP) hedef alıp, oradan büyük/iyi korunan kurumlara sıçrar.
- **Guest zinciri üzerinden pivot**: A kiracısı B kiracısına guest erişimi vermiş, B kiracısı da C kiracısına guest erişimi vermişse; A'da ele geçirilen bir hesap, B üzerinden C'ye kadar zincirleme iz sürebilir (özellikle B'nin guest'lere verdiği izinler gevşekse).
- **Ortak/paylaşılan uygulama kayıtları (app registrations) ve service principal'lar**: Çok kiracılı (multi-tenant) uygulamalarda, uygulamanın bir kiracıdaki client secret'i veya sertifikası ele geçirilirse ve uygulama başka kiracılarda da onaylanmışsa (consent verilmişse), saldırgan o uygulamanın kimliğiyle diğer kiracılarda da işlem yapabilir.

### 3.4 Tespit

- **Cross-tenant senkronizasyon kurallarının düzenli denetimi**: Hangi kullanıcı/grupların hangi kiracılara senkronize edildiğini, senkronizasyon kapsamının (scope) ne kadar geniş tanımlandığını izle; kapsam genişlemesi (yeni gruplar eklenmesi) alarm üretmeli.
- **GDAP/delege yönetici ilişkilerinin envanteri**: Hangi partner/MSP kiracılarının hangi rollerle bağlı olduğunu düzenli çıkar; "Global Admin" gibi aşırı geniş delege rollerin varlığını kırmızı bayrak olarak işaretle.
- **Çok kiracılı uygulama consent'lerini izle**: Hangi uygulamaların hangi kiracılarda onaylandığını, hangi API izinlerine (özellikle `Directory.ReadWrite.All`, `RoleManagement.ReadWrite.Directory` gibi yüksek etkili izinlere) sahip olduğunu periyodik denetle.
- **Partner/MSP oturum aktivitesini iş saatleri ve iş gerekçesi bağlamında değerlendir**: Beklenmeyen saatlerde, beklenmeyen partner hesabından gelen yönetimsel işlemler (rol atama, uygulama izni verme) şüpheli sinyal olarak ele alınmalı.
- **Kiracılar arası korelasyon**: Mümkünse (özellikle aynı holding altındaki kiracılarda) merkezi bir SIEM'e her iki/tüm kiracının loglarını toplayıp, zaman senkronize korelasyon kurmak — bir kiracıdaki anomalinin diğerindeki bir olayla zamansal örtüşmesini yakalamak.

### 3.5 Savunma

- **GDAP'ı en az ayrıcalık ile kur, eski geniş-yetkili CSP delege modelinden uzaklaş**: Partner ilişkilerinde sadece gerekli, süreli (time-bound) roller ver; süresiz/geniş roller vermekten kaçın.
- **CTS kapsamını mümkün olan en dar şekilde tanımla**: Senkronizasyonu "tüm kullanıcılar" yerine belirli, iyi tanımlanmış gruplarla sınırla; otomatik rol/grup mirasını dikkatlice denetle.
- **Çok kiracılı uygulamalarda consent'i merkezi yönet**: Kullanıcı bazlı serbest consent yerine yönetici onaylı (admin consent) akış zorunlu kıl; yüksek etkili API izinlerine sahip uygulamaları düzenli envanterle.
- **Partner/MSP ilişkilerini periyodik olarak yeniden değerlendir**: Artık iş ilişkisi bitmiş partner'ların GDAP/delege erişimini derhal iptal et; bu genelde unutulan ve uzun süre açık kalan bir risk yüzeyidir.
- **Segmentasyon ve "blast radius" düşüncesiyle tasarla**: Bir kiracının ihlalinin diğerine otomatik sıçramaması için, kiracılar arası güven ilişkilerini mimari düzeyde minimumda tut; "neden bu iki kiracı arasında bu kadar geniş bir güven var" sorusunu düzenli sor.
- **Olay müdahale planını çoklu kiracı senaryosuna göre güncelle**: IR (Incident Response) sürecinin, bir kiracıdaki ihlalde otomatik olarak ilişkili tüm kiracıların/partner'ların güven ilişkilerini gözden geçirmesini/gerekirse askıya almasını içerdiğinden emin ol.

### 3.6 Yaygın Hatalar

- MSP/partner ilişkilerini kurup sonra hiç gözden geçirmemek — "bir kere kuruldu, sorun yok" yaklaşımı.
- Cross-tenant senkronizasyon kapsamını "kolaylık olsun" diye aşırı geniş tanımlamak.
- Çok kiracılı uygulama consent'lerinin bir defa verildikten sonra unutulması, izinlerin zamanla genişletilip genişletilmediğinin izlenmemesi.
- İki kiracı arasındaki güveni tek yönlü sanıp, aslında çift yönlü görünürlük/etki taşıdığının fark edilmemesi.

---

## Sonuç: Birleşik Savunma Perspektifi

Bu üç vektörün (Golden SAML, guest/B2B kötüye kullanımı, tenant-to-tenant pivot) ortak paydası, güvenin **tek bir kriptografik nesneye, tek bir hesap türüne veya tek bir yapılandırma ayarına aşırı yoğunlaşmış** olmasıdır. Golden SAML'de bu yoğunlaşma token imzalama sertifikasıdır; guest kötüye kullanımında varsayılan izin seviyeleridir; tenant pivot'ta ise kiracılar arası güven kanallarının kapsamıdır.

Savunma stratejisi bu nedenle üç ortak ilkeye dayanmalı:

1. **Kimlik altyapısını (AD FS dahil) Tier-0 varlık olarak ele almak** ve bu varlıklara erişimi PAW/jump host gibi izole mekanizmalarla sıkılaştırmak.
2. **Her güven ilişkisini (federasyon, guest davet, cross-tenant sync, GDAP) "neden var, ne kadar geniş, ne zaman gözden geçirildi" sorularıyla periyodik denetlemek** — kurulduktan sonra unutulan güven ilişkisi, saldırganın en sevdiği kalıcılık türüdür.
3. **Bulut tarafı (Entra ID sign-in logs, audit logs) ile şirket içi (AD FS, AD audit) telemetriyi tek bir korelasyon katmanında birleştirmek** — çünkü bu saldırı sınıfı tam olarak iki dünyanın arasındaki görünürlük boşluğunda yaşar. Hiçbir taraf tek başına tam resmi göremez; savunmacı bu iki dünyayı birleştiren kişi olmak zorundadır.

Sonuç olarak, hibrit ve çok kiracılı ortamlarda güvenlik, artık "bu kiracıyı/bu ormanı koru" sorusundan "bu güven zincirinin her halkasını anla ve denetle" sorusuna evrilmiştir.
