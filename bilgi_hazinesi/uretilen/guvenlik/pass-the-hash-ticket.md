# Pass-the-Hash / Pass-the-Ticket / Overpass-the-Hash: Kimlik Bilgisi Yeniden Kullanım Saldırıları ve Savunma

## Giriş ve Tanım

Windows ve Active Directory ortamlarında en yıkıcı saldırı sınıflarından biri, parolanın kendisine hiç ihtiyaç duymadan kimlik doğrulamayı ele geçirmeye dayanır. **Pass-the-Hash (PtH)**, **Pass-the-Ticket (PtT)** ve **Overpass-the-Hash (OtH)** olarak bilinen bu teknikler, ortak bir kök gerçeği paylaşır: Windows'ta kimlik doğrulama, çoğu zaman parolanın *düz metin* haliyle değil, ondan türetilmiş bir *kriptografik gizli değer* (NTLM hash, Kerberos anahtarı veya bilet) ile yürür. Eğer saldırgan bu türetilmiş gizli değeri ele geçirirse, parolayı kırmasına dahi gerek kalmaz; çünkü protokol zaten parolayı değil, o gizli değeri kabul eder.

Bu makale, bu üç tekniğin *neden* mümkün olduğunu, protokol düzeyinde *nasıl* çalıştığını, saldırganın istismar mantığını ve buna karşılık savunma tarafının hangi kontrolleri devreye almak zorunda olduğunu derinlemesine inceler. Amaç, bir komut listesi ezberletmek değil; bu saldırı ailesinin altında yatan tasarım gerçeğini kavratmaktır. Çünkü bu tekniklere karşı savunma yapan mühendisin en büyük hatası, onları "bir açık" gibi görüp yama beklemesidir. Bunlar birer yazılım hatası (bug) değil, kimlik doğrulama protokolünün *tasarım gereği* çalışma biçimidir.

## Kök Neden: Neden Hash "Parola Kadar" Değerli?

Bu saldırıların anlaşılması için önce **"hash eşittir kimlik"** ilkesini içselleştirmek gerekir. Bir kullanıcı parolasını girdiğinde, bu parola diskte veya hafızada genellikle açık metin olarak saklanmaz. Bunun yerine ondan matematiksel olarak türetilmiş temsiller tutulur:

- **NT hash (NTLM hash):** Kullanıcı parolasının, tuzlanmamış (unsalted) bir MD4 türevi ile hesaplanmış özetidir. Kritik ve rahatsız edici nokta şudur: NTLM kimlik doğrulama protokolünde, sunucuya karşı kimliği ispatlamak için kullanılan asıl gizli değer, parolanın kendisi değil bu NT hash'tir. Yani hash, challenge-response hesaplamasına doğrudan girer.
- **Kerberos anahtarları:** Kerberos'ta kullanıcının parolasından türetilen simetrik anahtarlar (özellikle AES tabanlı anahtarlar, eski ortamlarda RC4-HMAC anahtarı ki bu RC4 anahtarı çoğu zaman NT hash ile aynıdır) kullanılır. Bu anahtar, kullanıcının Key Distribution Center (KDC) karşısında kimliğini kanıtladığı ilk adımın (pre-authentication) ve TGT talebinin temelini oluşturur.

Buradaki kök neden nettir: **Protokol, ispatın malzemesi olarak türetilmiş gizli değeri kabul eder.** Dolayısıyla saldırganın parolayı kırması gerekmez; türetilmiş değeri ele geçirmesi yeterlidir. Bu, "tuzlama" (salting) eksikliğiyle daha da ağırlaşır: NT hash tuzlanmadığı için aynı parola her makinede aynı hash'i üretir. Bu, bir makinede ele geçirilen bir hash'in başka makinelerde de aynen geçerli olması demektir — saldırganın yanal hareket (lateral movement) için ihtiyaç duyduğu tam da budur.

Bir diğer kök neden, **Single Sign-On (SSO)** ihtiyacıdır. Kullanıcının her ağ kaynağına eriştiğinde tekrar tekrar parola girmesini istemeyiz. Bunu sağlamak için Windows, oturum açık olduğu sürece kimlik doğrulama gizli değerlerini (NT hash, Kerberos biletleri ve anahtarları) **LSASS (Local Security Authority Subsystem Service)** sürecinin hafızasında tutar. İşte saldırıların hedeflediği hazine burasıdır: LSASS bellek alanı. Yönetici (veya SeDebugPrivilege sahibi) yetkisine ulaşan bir saldırgan, LSASS belleğini okuyarak bu gizli değerleri çıkarabilir.

Özetle üç tasarım tercihi birleşerek bu saldırı ailesini doğurur: (1) protokolün parola yerine türev gizli değeri kabul etmesi, (2) NT hash'in tuzlanmaması nedeniyle taşınabilir olması, (3) SSO için bu gizli değerlerin bellekte canlı tutulması.

## Pass-the-Hash (PtH): NTLM Hash Yeniden Kullanımı

### Çalışma mantığı

NTLM kimlik doğrulaması, klasik bir **challenge-response** akışı izler. Basitleştirilmiş haliyle:

1. İstemci sunucuya "bağlanmak istiyorum" der (NEGOTIATE).
2. Sunucu rastgele bir **challenge** (nonce) gönderir (CHALLENGE).
3. İstemci, bu challenge'ı kullanıcının **NT hash'i** ile işleyerek bir yanıt (response) hesaplar ve gönderir (AUTHENTICATE).
4. Sunucu (ya da domain controller aracılığıyla) aynı hesabı NT hash'iyle yapar ve yanıtları karşılaştırır.

Dikkat edilmesi gereken can alıcı nokta: Bu hesaplamanın hiçbir adımında parolanın *düz metni* gerekmez. İstemci tarafında gereken tek şey NT hash'tir. İşte Pass-the-Hash bunu istismar eder — saldırgan parolayı bilmese bile, ele geçirdiği NT hash'i doğrudan bu challenge-response hesabına besleyerek geçerli bir yanıt üretir. Windows'un standart oturum açma arayüzü parola beklediği için, saldırgan LSASS'ın kimlik doğrulama katmanına hash'i doğrudan enjekte eden özel araçlar kullanır.

### İstismar mantığı

Tipik bir saldırı zinciri şöyle akar: Saldırgan bir uç noktada yerel yönetici olur (örneğin bir phishing veya bir zafiyet üzerinden). LSASS belleğinden o makinede oturum açmış kullanıcıların NT hash'lerini çıkarır. Bu hash'lerden biri, ağdaki başka makinelerde de yönetici yetkisine sahip bir hesaba aitse (örneğin ortak bir yerel yönetici parolası veya ayrıcalıklı bir domain hesabı), saldırgan o hash ile diğer makinelere NTLM üzerinden kimlik doğrular. SMB, WMI, WinRM gibi protokollerle uzaktan komut çalıştırır. Bu döngü — hash topla, yanal hareket et, yeni hash topla — bir domain admin hesabı ele geçene kadar tekrarlanır.

PtH'nin en tehlikeli tarafı, **parola değişikliğine karşı dayanıklı** olmasıdır sanılmasının aksine, hash yalnızca parola değiştiğinde geçersiz olur; ancak parola sabit kaldığı sürece süresizdir. Ayrıca hash'i kırmak (crack) gerekmez, bu yüzden parolanın uzun ve karmaşık olması PtH'yi *tek başına* engellemez.

## Overpass-the-Hash (OtH / Pass-the-Key): NTLM'den Kerberos'a Köprü

### Neden var?

PtH, NTLM protokolüne bağımlıdır. Peki bir kuruluş NTLM'i büyük ölçüde kısıtladıysa veya saldırgan tespit edilmeden Kerberos dünyasına geçmek istiyorsa? İşte **Overpass-the-Hash** (bazı kaynaklarda **Pass-the-Key**) bu köprüyü kurar.

### Çalışma mantığı

Kerberos ön kimlik doğrulamasında istemci, zaman damgasını kullanıcının parolasından türetilen anahtarla şifreleyerek KDC'ye gönderir. Burada dikkat: RC4-HMAC şifreleme türü kullanıldığında, bu Kerberos anahtarı **NT hash ile aynıdır**. Yani saldırgan elindeki NT hash'i kullanarak, sanki parolayı biliyormuş gibi geçerli bir Kerberos **TGT (Ticket Granting Ticket)** talep edebilir.

Overpass-the-Hash tam olarak budur: NT hash'i (veya doğrudan AES anahtarını) alıp, onunla KDC'den taze bir TGT istemek. Elde edilen TGT, saldırgana Kerberos dünyasının kapılarını açar — artık NTLM izleri bırakmadan, meşru bir Kerberos kullanıcısı gibi hizmet biletleri (service ticket) alabilir. Bu, hem daha "sessiz" bir tekniktir (Kerberos trafiği normal görünür) hem de NTLM'i devre dışı bırakmış ortamlarda bile işe yarar.

Modern ortamlarda RC4 kısıtlanmış olabilir; bu durumda saldırganın NT hash yerine kullanıcının **AES anahtarını** ele geçirmesi gerekir. Bu anahtar da paroladan türediği için LSASS'tan veya DCSync gibi tekniklerle elde edilebilir. Buradaki önemli savunma dersi şudur: RC4'ü kapatmak OtH'yi zorlaştırır ama AES anahtarı sızarsa tek başına engellemez.

## Pass-the-Ticket (PtT): Kerberos Biletlerinin Yeniden Kullanımı

### Çalışma mantığı

Kerberos'ta iki tür bilet vardır:

- **TGT (Ticket Granting Ticket):** KDC'nin verdiği ana bilettir; kullanıcının kimliğini kanıtlayan ve başka bilet almasını sağlayan üst düzey bilettir.
- **TGS / Service Ticket:** Belirli bir hizmete (örneğin bir dosya sunucusu, SQL sunucusu) erişim için verilen bilettir.

Bu biletler, kullanılabilmesi için istemcinin belleğinde tutulur. **Pass-the-Ticket**, bu biletleri (özellikle TGT'yi) LSASS belleğinden çalıp, saldırganın kendi oturumuna enjekte etmesidir. Saldırgan artık ne parolaya ne hash'e ihtiyaç duyar — doğrudan geçerli, imzalı bir kimlik kanıtına sahiptir.

### İstismar mantığı ve neden bu kadar etkili?

PtT'nin gücü, çalınan biletin **KDC tarafından zaten imzalanmış ve doğrulanmış** olmasından gelir. Özellikle bir domain admin'in TGT'si çalınırsa, saldırgan o TGT'yi kendi makinesine enjekte ederek domain admin gibi davranabilir. Biletin geçerlilik süresi (genellikle TGT için 10 saat, yenilenebilir süresi 7 gün gibi tipik değerler) boyunca bu erişim canlıdır.

PtT ailesinin en tehlikeli iki uzantısı vardır:

- **Golden Ticket:** Saldırgan, domainin `krbtgt` hesabının anahtarını (NT hash veya AES anahtarı) ele geçirirse — ki bu genellikle DCSync veya bir domain controller'ın tam ele geçirilmesiyle olur — KDC'yi taklit ederek **kendi TGT'lerini sıfırdan üretebilir**. Bu bilet tamamen sahtedir ama `krbtgt` anahtarıyla imzalandığı için domaindeki her sunucu onu gerçek kabul eder. Golden Ticket, istenen herhangi bir kullanıcı adına, istenen grup üyelikleriyle, uzun geçerlilik süreleriyle üretilebilir. Bu, bir domainde "tanrı modu" demektir ve tek gerçek çözümü `krbtgt` parolasının (art arda iki kez, replikasyon nedeniyle) sıfırlanmasıdır.
- **Silver Ticket:** Saldırgan `krbtgt` yerine belirli bir *hizmet hesabının* anahtarını ele geçirirse, yalnızca o hizmete yönelik sahte service ticket üretebilir. KDC'ye hiç uğramadığı için daha sessizdir; ama kapsamı tek hizmetle sınırlıdır.

## Somut Bir Senaryo

Bir kurumsal ağı düşünelim. Saldırgan, bir çalışanın iş istasyonunda phishing yoluyla kod çalıştırıp yerel yönetici oldu. LSASS belleğinden, o makinede oturum açmış bir yardım masası (helpdesk) teknisyeninin NT hash'ini çıkardı. Bu teknisyen, çok sayıda iş istasyonunda yerel yönetici yetkisine sahip.

1. **PtH:** Saldırgan bu hash'i kullanarak SMB üzerinden başka bir iş istasyonuna kimlik doğrular ve komut çalıştırır. Parolayı bilmiyor, kırmadı — sadece hash'i "geçirdi".
2. **Yeni avlanma:** Yeni makinenin LSASS'ında bir sunucu yöneticisinin biletleri var. Saldırgan bu makinede oturum açmış olan bir domain hesabının TGT'sini çıkarır.
3. **PtT:** Çalınan TGT'yi kendi oturumuna enjekte eder ve o hesabın erişebildiği tüm hizmetlere ulaşır.
4. **Overpass:** Bir noktada elindeki NT hash ile KDC'den taze bir TGT alarak (OtH) tamamen Kerberos üzerinden, NTLM izi bırakmadan hareket etmeyi seçer.
5. **Nihai hedef:** Bir domain controller'a ulaşıp `krbtgt` anahtarını çıkarır (DCSync). Artık Golden Ticket üretebilir ve domaine kalıcı erişim kazanır.

Bu senaryonun her adımı, "parola çalma" değil "kimlik kanıtı çalma ve yeniden kullanma" üzerine kuruludur. Bu yüzden yalnızca parola politikaları bu zinciri kırmakta yetersizdir.

## Savunma: Katmanlı ve Kök Nedene Yönelik

Bu saldırılar tasarım gereği olduğundan, savunma tek bir yamaya değil, **saldırı yüzeyini daraltan katmanlı kontrollere** dayanır. Savunma mantığını üç eksende düşünmek faydalıdır: *gizli değeri çaldırmamak*, *çalınsa bile yeniden kullanımı sınırlamak* ve *kullanımı tespit etmek*.

### 1. Ayrıcalıklı kimlik bilgilerinin bellekte birikmesini önle

- **Yerel yönetici hesaplarını izole et.** En kritik kontrollerden biri, her makinenin **benzersiz yerel yönetici parolasına** sahip olmasıdır. Microsoft'un **LAPS (Local Administrator Password Solution)** çözümü tam bu amaca hizmet eder: bir makineden çalınan yerel yönetici hash'i, başka makinelerde işe yaramaz hale gelir. Bu, PtH'nin yanal yayılma yeteneğini tek başına ciddi biçimde kırar.
- **Ayrıcalıklı hesapları düşük güven düzeyindeki makinelerde oturum açtırma.** Bir domain admin, sıradan bir iş istasyonunda oturum açarsa, kimlik bilgisi o makinenin LSASS'ında birikir ve makine ele geçince çalınır. **Tiering (katmanlama) modeli** (Tier 0 / Tier 1 / Tier 2) bunu engeller: Tier 0 kimlikleri yalnızca Tier 0 varlıklarında kullanılır.
- **Privileged Access Workstations (PAW)** kullan: yönetim işlemleri, internete ve e-postaya kapalı, sıkılaştırılmış ayrı makinelerden yapılır.

### 2. Gizli değere erişimi zorlaştır

- **Credential Guard** gibi sanallaştırma tabanlı güvenlik (VBS) çözümlerini etkinleştir. Bu, kimlik doğrulama gizli değerlerini (NTLM hash'leri, Kerberos TGT'leri) LSASS'tan izole edilmiş, donanım destekli korumalı bir sanal ortama taşır. Böylece klasik LSASS bellek okuma teknikleri bu gizli değerlere ulaşamaz. Bu, PtH ve PtT'ye karşı en güçlü uç nokta kontrollerinden biridir.
- **LSASS korumasını** (Protected Process Light — PPL) devreye al; bu, sıradan araçların LSASS belleğine erişimini zorlaştırır.
- **EDR/antivirüs** ile LSASS'a erişen anormal süreçleri izle ve engelle.

### 3. Protokol yüzeyini daralt

- **NTLM'i kademeli olarak devre dışı bırak.** NTLM, PtH ve OtH'nin temelidir. Ortam envanterini çıkarıp NTLM kullanımını denetle (audit), sonra kademeli olarak Kerberos'a geçir ve NTLM'i kısıtla. NTLM tamamen kaldırıldığında klasik PtH imkânsız hale gelir.
- **RC4-HMAC'i Kerberos'ta kapat, AES'i zorunlu kıl.** RC4 anahtarının NT hash'e eşit olması OtH'yi kolaylaştırır; AES zorunluluğu bu köprüyü zayıflatır.
- **SMB imzalama (signing)** ve **LDAP imzalama/kanal bağlama (channel binding)** ile relay saldırılarını (NTLM relay) engelle.

### 4. Bileti/hash'i çalınsa bile etkiyi sınırla ve tespit et

- **Kısa oturum ve bilet ömürleri**, ayrıcalıklı hesaplar için oturum sonlandırma politikaları, çalınan biletin kullanılabilir penceresini daraltır.
- **`krbtgt` parolasını düzenli ve doğru şekilde (art arda iki kez, replikasyon süresine dikkat ederek) sıfırla.** Bu, mevcut tüm Golden Ticket'ları geçersiz kılar. Bir ihlal şüphesinde bu bir zorunluluktur.
- **Protected Users grubu** ve **Authentication Policies/Silos** ile ayrıcalıklı hesapların NTLM ile kimlik doğrulamasını ve delege edilmesini engelle; bu hesaplar için daha katı Kerberos kuralları uygula.
- **Tespit (detection):** Anormal bilet kullanımlarını izle. Örneğin, olağandışı uzun ömürlü TGT'ler, var olmayan hesaplara ait biletler, RC4 kullanan beklenmedik Kerberos istekleri, aynı hesabın kısa sürede birçok makineden kimlik doğrulaması. **Microsoft Defender for Identity** gibi çözümler tam da bu anormallikleri (Golden Ticket, OtH, PtT göstergeleri) yakalamaya odaklanır. SIEM tarafında ilgili Windows olay kimliklerini (oturum açma, Kerberos hizmet bileti talepleri, kimlik doğrulama olayları) korele et.

## Yaygın Hatalar

Sahada tekrar tekrar görülen ve savunmayı boşa çıkaran yanlış inanışlar şunlardır:

- **"Uzun ve karmaşık parola PtH'yi durdurur."** Yanlış. PtH parolayı kırmaz, hash'i olduğu gibi kullanır. Parola karmaşıklığı offline crack'i zorlaştırır ama hash'in doğrudan yeniden kullanımını etkilemez.
- **"Sık parola değişimi yeterli."** Kısmen yardımcı olur (hash'i eskitir) ama saldırgan zaten erişim penceresinde hareket eder; asıl mesele kimliğin bellekte birikmesini ve taşınmasını önlemektir.
- **"Antivirüsümüz var, LSASS okumasını yakalar."** Modern saldırganlar imzasız, bellek içi (fileless) veya meşru araçları kötüye kullanan (LOLBins) yöntemler kullanır. Yalnızca imza tabanlı korumaya güvenmek yetersizdir.
- **"Golden Ticket için parolayı bir kez sıfırlamak yeter."** `krbtgt` için tek sıfırlama, replikasyon nedeniyle eski anahtarı bir süre geçerli bırakır; doğru prosedür kontrollü aralıkla iki kez sıfırlamaktır.
- **"Domain admin ile her yere bağlanmak pratik."** Bu, ayrıcalıklı kimliğin en savunmasız makinelere yayılmasının bir numaralı nedenidir. Kimlik hijyeninin ihlalidir.
- **NTLM'i "eski ama zararsız" görmek.** NTLM'in varlığı, tüm PtH/OtH/relay ailesinin zeminidir; envanter çıkarmadan bırakmak büyük bir kör noktadır.

## En İyi Pratikler (Özet)

1. **Kimlik katmanlama (tiering) modelini uygula.** Tier 0 (domain controller'lar, kimlik altyapısı) kimlikleri asla alt katmanlarda kullanılmaz.
2. **Her makineye benzersiz yerel yönetici parolası** (LAPS türü çözüm) ver — yanal hareketi kökten kır.
3. **Credential Guard + LSASS korumasını (PPL) + VBS'i** destekleyen tüm sistemlerde etkinleştir.
4. **NTLM'i denetle ve kademeli kaldır; Kerberos'ta AES zorunlu kıl, RC4'ü kapat.**
5. **SMB/LDAP imzalama ve kanal bağlamayı** zorunlu kılarak relay saldırılarını engelle.
6. **Protected Users, Authentication Policies/Silos** ile ayrıcalıklı hesapları sertleştir.
7. **PAW** üzerinden yönetim yap; yönetim makinelerini internetten izole et.
8. **`krbtgt` sıfırlamasını** olay müdahale planına doğru prosedürle dahil et; düzenli rotasyonu değerlendir.
9. **En az ayrıcalık (least privilege)** ilkesini uygula; kalıcı ayrıcalık yerine **Just-In-Time / Just-Enough-Access** (PIM) modeli kullan.
10. **Sürekli tespit:** kimlik odaklı davranışsal analiz (anormal bilet, OtH, Golden/Silver Ticket göstergeleri) kur ve SIEM ile korele et.

## Sonuç

Pass-the-Hash, Pass-the-Ticket ve Overpass-the-Hash, Windows kimlik doğrulamasının bir hatası değil, tasarımının doğal bir sonucudur: protokol parolayı değil ondan türeyen gizli değeri kabul eder, bu değerler SSO için bellekte canlı tutulur ve NT hash tuzlanmadığı için taşınabilir. Bu üç gerçeği kavradığınızda savunma da netleşir — çünkü artık "hangi yamayı kuracağım" değil, "gizli değerin nerede biriktiğini, nasıl korunduğunu, çalınırsa yeniden kullanımının nasıl sınırlandığını ve nasıl tespit edildiğini" sorarsınız. Etkili savunma tek bir üründe değil, kimlik hijyeni, katmanlama, bellek koruması, protokol sıkılaştırması ve davranışsal tespitin bir arada uygulandığı katmanlı bir mimaride yatar. Bu saldırı ailesine karşı en büyük zafiyet teknik değil, mimari ve operasyoneldir: ayrıcalıklı kimliği yanlış yere koymak.
