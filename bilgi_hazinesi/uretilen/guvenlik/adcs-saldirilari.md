# Active Directory Certificate Services (ADCS) Saldırıları

## Giriş ve Neden Önemli

Active Directory Certificate Services (ADCS), Microsoft'un kurumsal ortamlarda PKI (Public Key Infrastructure) altyapısını yönetmek için sunduğu roldür. Akıllı kart kimlik doğrulaması, HTTPS sertifikaları, kod imzalama, EFS şifreleme ve en kritik olarak da **sertifika tabanlı kimlik doğrulama** (certificate-based authentication) gibi işlevler için sertifika dağıtır. Yıllarca bu servis "arka planda çalışan, kimsenin dokunmadığı" bir bileşen olarak görüldü. 2021'de SpecterOps araştırmacıları Will Schroeder ve Lee Christensen'in yayımladığı "Certified Pre-Owned" başlıklı çalışma, bu algıyı tamamen değiştirdi ve ESC1'den ESC8'e kadar numaralandırılan bir dizi yanlış yapılandırma (misconfiguration) sınıfını literatüre soktu. Sonraki yıllarda topluluk bu listeyi ESC13, ESC14, ESC15 ve ötesine kadar genişletti.

ADCS saldırılarının bu kadar tehlikeli olmasının temel nedeni şudur: Bir saldırgan çoğu senaryoda **düşük yetkili bir domain kullanıcısı** hesabıyla başlar ve yanlış yapılandırılmış bir sertifika şablonunu (certificate template) kötüye kullanarak **Domain Admin** ya da doğrudan **Domain Controller** kimliğine bürünen bir sertifika elde edebilir. Yani yetki yükseltme (privilege escalation) ve kalıcılık (persistence), tek bir yanlış ayarlanmış nesne üzerinden gerçekleşir. Üstelik elde edilen sertifika, parola değişikliğinden bağımsız olarak geçerlilik süresi boyunca kullanılabilir; bu da tespiti ve müdahaleyi zorlaştıran güçlü bir kalıcılık vektörü oluşturur.

## Kök Neden: Sertifikalar Neden Kimlik Yerine Geçer?

Saldırıları anlamak için önce sertifikaların AD içinde kimliği **nasıl** temsil ettiğini kavramak gerekir. Bir kullanıcı sertifika ile kimlik doğrularken (özellikle PKINIT üzerinden Kerberos'ta), Domain Controller sertifikanın içindeki kimliği okur ve bunu bir AD nesnesiyle eşleştirir. Bu eşleştirmede iki alan kritiktir:

- **Subject Alternative Name (SAN)**: Sertifikanın hangi kimliğe ait olduğunu söyleyen alandır. İçinde bir UPN (User Principal Name) ya da DNS adı bulunabilir. Kimlik doğrulama sırasında `administrator@domain.local` gibi bir UPN, doğrudan o hesaba eşlenir.
- **Extended Key Usage (EKU)**: Sertifikanın **ne için** kullanılabileceğini belirler. `Client Authentication`, `Smart Card Logon`, `PKINIT Client Authentication` ya da her şeye izin veren `Any Purpose` gibi OID değerleri buradadır.

İşte kök neden burada yatar: Eğer bir saldırgan, **kimlik doğrulamaya yarayan bir EKU** taşıyan ve **SAN alanını kendi belirleyebildiği** bir sertifika elde edebilirse, o sertifikanın SAN'ına istediği ayrıcalıklı hesabın UPN'ini yazarak o hesap gibi kimlik doğrular. Sertifika şablonlarındaki yanlış yapılandırmaların çoğu, tam olarak bu iki koşulun (kimlik doğrulama EKU'su + saldırgan kontrollü SAN) istemeden bir araya gelmesinden kaynaklanır.

Bir sertifika şablonunun güvenliğini belirleyen temel parametreler şunlardır ve saldırı analizinde her seferinde bunlara bakılır:

- **Enrollment rights (kayıt hakları)**: Şablonu kimler talep edebilir? Genelde `Domain Users` ya da `Authenticated Users` gibi geniş gruplar burada olduğunda risk başlar.
- **`ENROLLEE_SUPPLIES_SUBJECT` bayrağı**: Bu bayrak aktifse, talep eden kişi sertifikanın Subject ve SAN alanını **kendisi** doldurabilir. Saldırgan kontrollü SAN'ın kaynağı budur.
- **Manager approval / yetkili imzası**: Talebin manuel onay ya da ek imza gerektirip gerektirmediği. Bunlar kapalıysa saldırı otomatikleşir.
- **CA yetkileri ve erişim kontrolleri**: Sertifika Otoritesi (CA) sunucusunun kendisi üzerindeki izinler.

## ESC1-ESC8 Genel Bakış

Aşağıda her bir yanlış yapılandırma sınıfının çalışma mantığını, neden ortaya çıktığını ve nasıl kötüye kullanıldığını ele alıyorum. Bu numaralandırma bir standart değil, topluluğun ortak dilidir; bu yüzden kavramı ezberlemek yerine altındaki mekanizmayı anlamak önemlidir.

### ESC1 — Saldırgan Kontrollü SAN ile Kimliğe Bürünme

ESC1, en klasik ve en anlaşılır senaryodur. Bir sertifika şablonu şu üç özelliği aynı anda taşırsa ESC1 açığı vardır:

1. Düşük yetkili kullanıcılar (örneğin `Domain Users`) şablona kayıt yapabilir,
2. Şablon `ENROLLEE_SUPPLIES_SUBJECT` bayrağıyla SAN'ı talep edene bıraktığı için saldırgan SAN'ı belirleyebilir,
3. Şablon `Client Authentication` ya da `Smart Card Logon` gibi kimlik doğrulama EKU'su içerir ve manager approval kapalıdır.

**Neden çalışır:** Saldırgan, kendi düşük yetkili hesabıyla bir sertifika talep eder ama SAN alanına `administrator@domain.local` yazar. CA bunu sorgulamadan imzalar çünkü şablon "talep eden SAN'ı belirlesin" diye ayarlanmıştır. Sonuç, Domain Admin'in UPN'ini taşıyan geçerli bir kimlik doğrulama sertifikasıdır. Saldırgan bu sertifikayı PKINIT ile Kerberos TGT almak için kullanır ve artık Domain Admin'dir.

**İstismar mantığı:** Certipy ya da Certify gibi araçlarla `template` ve `upn` parametreleri verilerek talep gönderilir, dönen sertifikayla `auth` işlemi yapılıp TGT/NT hash elde edilir.

**Savunma:** `ENROLLEE_SUPPLIES_SUBJECT` bayrağını kimlik doğrulama EKU'su taşıyan şablonlardan kaldırın. Eğer SAN'ın talep eden tarafından verilmesi zorunluysa, mutlaka manager approval açın ve kayıt haklarını daraltın.

### ESC2 — "Any Purpose" veya Aşırı Geniş EKU

ESC2, şablonun EKU'sunun `Any Purpose` olması ya da hiç EKU olmaması (SubCA benzeri) durumudur. `Any Purpose` EKU'su, sertifikanın kimlik doğrulama dahil her amaçla kullanılabileceği anlamına gelir.

**Neden tehlikeli:** ESC1'de saldırganın SAN'ı belirleyebilmesi gerekiyordu; ESC2'de ise şablonun sınırsız kullanım yetkisi, sertifikanın çok geniş bir saldırı yüzeyi kazanmasına yol açar. Bu tür bir sertifika, kimlik doğrulamadan kod imzalamaya kadar farklı senaryolarda silah olarak kullanılabilir.

**Savunma:** Şablonlara mümkün olan **en dar** EKU setini atayın. `Any Purpose` EKU'sunu üretim şablonlarında kullanmaktan kaçının; her şablonun tek ve net bir amacı olsun.

### ESC3 — Enrollment Agent Sertifikalarının Kötüye Kullanımı

ESC3, `Certificate Request Agent` (enrollment agent) EKU'sunu içeren şablonlarla ilgilidir. Enrollment agent, normalde bir yönetici adına **başkaları için** sertifika talep etme yetkisidir; örneğin bir IT çalışanının kullanıcılar adına akıllı kart sertifikası kayıt etmesi için tasarlanmıştır.

**Neden tehlikeli:** Saldırgan önce bir enrollment agent sertifikası elde eder, sonra bu sertifikayı kullanarak **başka bir kullanıcı (örneğin Domain Admin) adına** ikinci bir kimlik doğrulama sertifikası talep eder. İki adımlı bir zincirdir ama sonuçta yine ayrıcalıklı bir hesaba bürünme elde edilir.

**Savunma:** Enrollment agent şablonlarına kayıt haklarını sıkı tutun. CA üzerinde enrollment agent kısıtlamaları tanımlayarak hangi agent'ın hangi şablonlar ve hangi kullanıcılar için talep yapabileceğini sınırlayın.

### ESC4 — Şablon Nesnesi Üzerinde Zayıf Erişim Kontrolleri

ESC4, sertifika şablonunun **kendisine** yazma yetkisi (write permission) olan yanlış yapılandırmalardır. Yani sorun şablonun içeriği değil, şablon nesnesinin AD içindeki ACL'idir (Access Control List).

**Neden kritik:** Bir saldırgan şablon üzerinde `WriteDacl`, `WriteOwner` ya da genel yazma yetkisine sahipse, güvenli bir şablonu **geçici olarak ESC1'e dönüştürebilir**. Yani şablonun bayraklarını değiştirir, EKU ekler, `ENROLLEE_SUPPLIES_SUBJECT` açar, saldırısını yapar, sonra ayarları geri alarak izini örtmeye çalışır. ESC4 bu yüzden diğer ESC'lere açılan bir kapıdır.

**Savunma:** Sertifika şablonlarının ACL'lerini düzenli denetleyin. `Domain Users`, `Authenticated Users` ya da düşük yetkili gruplara şablonlar üzerinde yazma yetkisi verilmediğinden emin olun. Değişiklikleri izleyin (aşağıda tespit bölümüne bakın).

### ESC5 — PKI Nesne Hiyerarşisi Üzerinde Zayıf ACL'ler

ESC5, ESC4'ün daha geniş halidir. Burada sadece şablonlar değil, CA sunucusunun AD bilgisayar nesnesi, CA'yı barındıran nesneler ve PKI ile ilgili konteynerler (örneğin Configuration partition altındaki Public Key Services konteyneri) üzerindeki zayıf izinler söz konusudur.

**Neden önemli:** PKI güveni bir hiyerarşidir. Bu hiyerarşinin herhangi bir üst düğümünü kontrol eden biri, alt seviyedeki güven ilişkilerini manipüle edebilir. Örneğin CA'nın bilgisayar nesnesi üzerinde yetki, saldırgana geniş bir kontrol alanı açar.

**Savunma:** PKI ile ilgili tüm AD nesnelerinin sahipliğini ve izinlerini sadece yetkili PKI yöneticilerine bırakın. Bu nesneleri Tier 0 varlıkları olarak sınıflandırın.

### ESC6 — `EDITF_ATTRIBUTESUBJECTALTNAME2` Bayrağı

ESC6, CA'nın kendisindeki bir yapılandırma bayrağıdır: `EDITF_ATTRIBUTESUBJECTALTNAME2`. Bu bayrak açık olduğunda, **hangi şablon kullanılırsa kullanılsın**, talep eden kişi talebine bir SAN ekleyebilir ve CA bunu onurlandırır.

**Neden yıkıcı:** Bu, ESC1'in şablon bazlı sınırını ortadan kaldırır. Şablon `ENROLLEE_SUPPLIES_SUBJECT` içermese bile, bayrak açıksa saldırgan herhangi bir kimlik doğrulama şablonuyla keyfi SAN belirtip ayrıcalıklı hesaba bürünebilir. Yani tek bir CA ayarı, tüm PKI'yi ESC1'e açık hale getirir.

**Savunma:** CA üzerinde bu bayrağın kapalı olduğunu doğrulayın. Yönetim yapılandırmasında SAN'ın talep içinden okunmasına izin veren bu ayar üretim ortamlarında kesinlikle kapalı olmalıdır. Not: 2022 Mayıs güncellemeleri (KB5014754 ve ilişkili değişiklikler) sertifika eşleme davranışını sıkılaştırmıştır; ancak bu bayrak hâlâ ayrı ve kritik bir kontrol noktasıdır.

### ESC7 — CA Üzerinde Zayıf Erişim Kontrolleri (CA Yönetim Hakları)

ESC7, CA sunucusunun **kendisi** üzerindeki yönetimsel izinlerle ilgilidir; özellikle `ManageCA` ve `ManageCertificates` haklarıdır.

**Neden tehlikeli:** `ManageCA` hakkına sahip biri, yukarıda bahsedilen `EDITF_ATTRIBUTESUBJECTALTNAME2` bayrağını **kendisi açabilir** ve böylece ESC6'yı kendi elleriyle oluşturabilir. `ManageCertificates` hakkına sahip biri ise bekleyen (pending) talepleri onaylayabilir; yani manager approval korumasını devre dışı bırakır. Bu iki hak birleştiğinde, saldırgan onay gerektiren bir talebi gönderip sonra kendisi onaylayabilir.

**Savunma:** CA yönetim haklarını (`ManageCA`, `ManageCertificates`) yalnızca güvenilir PKI yöneticilerine verin. Bu hakları düşük yetkili gruplardan tamamen kaldırın ve düzenli denetleyin.

### ESC8 — NTLM Relay ile CA Web Enrollment (HTTP) Saldırısı

ESC8, diğerlerinden farklı bir sınıftır çünkü şablon yanlış yapılandırmasına değil, CA'nın **web enrollment** arayüzüne (genellikle `certsrv` HTTP endpoint'i) dayanır. Bu arayüz varsayılan olarak NTLM kimlik doğrulaması kabul eder ve HTTP üzerinden çalışabilir.

**Neden çalışır:** Saldırgan bir makineyi (örneğin bir Domain Controller'ı) coerce ederek, yani `PetitPotam` benzeri zorlama teknikleriyle kendisine NTLM kimlik doğrulaması yaptırır. Ardından bu kimlik doğrulamasını CA'nın web enrollment arayüzüne **relay** eder. Relay sonucunda CA, coerce edilen makine hesabı (örneğin `DC$`) adına bir kimlik doğrulama sertifikası verir. Saldırgan artık Domain Controller'ın makine hesabı gibi kimlik doğrulayabilir ki bu, DCSync gibi saldırılarla tam domain ele geçirmesine yol açar.

**İstismar mantığı:** `PetitPotam`/`Coercer` ile zorlama + `ntlmrelayx` ile ADCS web endpoint'ine relay + dönen sertifikayla `DC$` olarak kimlik doğrulama.

**Savunma:** Web enrollment arayüzünde NTLM'i devre dışı bırakıp Extended Protection for Authentication (EPA) ve HTTPS'i zorunlu kılın. Kullanılmayan web enrollment rolünü tamamen kaldırın. Ağ genelinde NTLM'i azaltın ve coercion (zorlama) yollarını (MS-EFSRPC vb.) kısıtlayın.

## ESC8'in Ötesi: Kısaca Genişleyen Aile

Topluluk numaralandırmayı sürdürdü. Kısaca değinmek gerekirse: **ESC9/ESC10**, KB5014754 ile gelen güçlü sertifika eşleme (strong certificate mapping) davranışının atlatılmasıyla ilgilidir; `msPKI-Enrollment-Flag` içindeki `no security extension` ayarı ya da zayıf eşleme registry değerleri sömürülür. **ESC11**, RPC üzerinden sertifika kaydında (ICertPassage) relay imkânıdır. **ESC13**, bir sertifika şablonunun bir OID grup bağlantısı (issuance policy) üzerinden dolaylı grup üyeliği kazandırmasıyla ilgilidir. Bu genişlemelerin ortak dersi: PKI'nin her yeni özelliği, yanlış yapılandırıldığında yeni bir kimliğe bürünme yolu açabilir. Spesifik registry anahtarları ve bayrak adları sürüme ve güncellemeye göre değişebildiğinden, üretimde bunları doğrulamadan uygulamayın.

## Sömürü Zinciri: Tüm Resim Nasıl Birleşir

Gerçek bir saldırıda adımlar tipik olarak şöyle akar. Bunu bilmek savunmacının hangi aşamada araya girebileceğini gösterir:

1. **Keşif (enumeration):** Saldırgan düşük yetkili bir hesapla, CA'ları ve şablonları listeleyip yanlış yapılandırılmış olanları bulur. Certipy'nin `find` işlevi bu yanlış yapılandırmaları otomatik olarak "vulnerable" olarak işaretler.
2. **Talep (request):** Uygun bir şablon bulunca, saldırgan kendi hesabıyla ama ayrıcalıklı bir SAN ile sertifika talep eder.
3. **Kimlik doğrulama (auth):** Dönen sertifikayla PKINIT üzerinden bir TGT alır. Ayrıca birçok araç, PKINIT sırasında NT hash'i de geri getirebilir (UnPAC-the-hash tekniği).
4. **Kalıcılık:** Elde edilen sertifika uzun süre geçerli olduğundan, saldırgan parola sıfırlansa bile erişimini korur. Bu yüzden ADCS kalıcılığın da favori aracıdır.

## Yaygın Hatalar (Savunmacı Tarafında)

- **"CA sunucusu bir uygulama sunucusu gibi ele alınıyor."** ADCS, Tier 0'dır. CA'yı, DC'lerle aynı güvenlik seviyesinde korunması gereken bir varlık olarak görmemek en temel hatadır.
- **Şablon ACL'lerinin hiç denetlenmemesi.** Şablonlar bir kez oluşturulup unutulur; oysa üzerlerindeki yazma yetkileri (ESC4) sessiz bir Domain Admin yolu olabilir.
- **`Domain Users`/`Authenticated Users`'a geniş kayıt hakları vermek.** Kolaylık için verilen bu geniş haklar, ESC1 ve ESC2'nin ön koşuludur.
- **Web enrollment'ı ihtiyaç yokken açık bırakmak.** Birçok ortamda `certsrv` HTTP arayüzü hiç kullanılmadığı halde açık kalır ve ESC8'e davetiye çıkarır.
- **Sadece parola tabanlı düşünmek.** Ekipler bir hesabın parolasını sıfırlayınca güvende sandıklarını düşünür; ama saldırgan zaten geçerli bir sertifika almışsa, parola sıfırlama onu durdurmaz.
- **`EDITF_ATTRIBUTESUBJECTALTNAME2` bayrağını hiç kontrol etmemek.** Tek bir CA ayarı tüm PKI'yi savunmasız bırakabilir; buna rağmen çoğu denetimde gözden kaçar.
- **Süresi dolmuş/kötüye kullanılmış sertifikaların iptal edilememesi.** İptal (revocation) süreçlerinin olgun olmaması, tespit edilse bile temizliği zorlaştırır.

## Tespit ve İzleme

Savunmanın önleme kadar önemli bir ayağı tespittir. Odaklanılacak olay kaynakları:

- **CA denetim günlükleri (audit logs):** Sertifika talep ve verme olayları, özellikle SAN'ında ayrıcalıklı bir UPN taşıyan talepler dikkat çekicidir. CA'da sertifika verme olaylarını (issued certificate events) ve başarısız/onay bekleyen talepleri izleyin.
- **Anormal SAN eşleşmeleri:** Düşük yetkili bir hesabın, SAN'ında yönetici UPN'i olan bir sertifika alması güçlü bir sömürü göstergesidir.
- **Kerberos PKINIT kullanımı:** Beklenmedik hesaplarda sertifika tabanlı kimlik doğrulama (özellikle akıllı kart normalde kullanılmayan bir ortamda) araştırılmalıdır.
- **Şablon ve CA yapılandırma değişiklikleri:** Şablonların bayraklarının, EKU'larının ya da ACL'lerinin değişmesi (ESC4/ESC7 belirtisi) bir alarm tetiklemelidir. AD nesne değişikliklerini denetim (SACL) ile izleyin.
- **Web enrollment erişimleri ve coercion imzaları:** `certsrv` endpoint'ine gelen NTLM kimlik doğrulama trafiği ve makine hesaplarının beklenmedik kimlik doğrulamaları, ESC8 relay saldırısına işaret edebilir.

## En İyi Pratikler ve Sertleştirme (Hardening)

Aşağıdaki ilkeler, ADCS saldırı yüzeyini sistematik olarak daraltır:

- **CA'yı Tier 0 olarak koruyun.** CA sunucularına yalnızca ayrıcalıklı yönetim iş istasyonlarından (PAW) erişin. CA'yı fiziksel/mantıksal olarak izole edin.
- **Her şablonu en az yetki (least privilege) ilkesiyle tasarlayın.** Kayıt haklarını daraltın, `ENROLLEE_SUPPLIES_SUBJECT`'i yalnızca kesinlikle gerektiğinde ve manager approval ile kullanın, EKU'ları mümkün olan en dar sete indirin, `Any Purpose` EKU'sundan kaçının.
- **Manager approval'ı yüksek riskli şablonlarda zorunlu kılın.** İnsan onayı, otomatik sömürü zincirini kırar.
- **`EDITF_ATTRIBUTESUBJECTALTNAME2` bayrağının kapalı olduğunu doğrulayın** ve CA yönetim haklarını (`ManageCA`/`ManageCertificates`) sıkı tutun.
- **Web enrollment'ı kaldırın ya da sertleştirin.** İhtiyaç yoksa kaldırın; varsa HTTPS + EPA zorunlu, NTLM kapalı olsun. Ağ genelinde NTLM kullanımını azaltın ve coercion vektörlerini kısıtlayın.
- **Güçlü sertifika eşlemeyi (strong certificate mapping) uygulayın.** Microsoft'un 2022'de duyurduğu sertifika eşleme sertleştirmesini (KB5014754 ile gelen tam uygulama moduna geçiş) planlı biçimde devreye alın; bu, SAN'a dayalı zayıf eşlemeleri kırarak birçok ESC senaryosunun etkisini azaltır.
- **Düzenli denetim yapın.** Certipy'nin `find` benzeri araçlarını **savunma amaçlı** kullanarak ortamınızı saldırgan gözüyle tarayın; ESC1-ESC8 kontrol listesini periyodik olarak geçirin.
- **Sertifika yaşam döngüsünü yönetin.** İptal (revocation), yenileme ve envanter süreçlerini olgunlaştırın; şüpheli sertifikaları hızla iptal edebilecek yeteneğe sahip olun.
- **İzleme ve loglamayı açın.** CA denetim günlüklerini merkezî SIEM'e aktarın ve yukarıdaki tespit senaryolarını kural haline getirin.

## Sonuç

ADCS saldırılarının ortak paydası tek bir gerçektir: **Sertifikalar AD içinde kimliğin ta kendisidir.** Kimlik doğrulamaya yarayan bir EKU ile saldırgan kontrollü bir SAN yan yana geldiğinde, düşük yetkili bir kullanıcı Domain Admin'e dönüşebilir. ESC1'den ESC8'e (ve ötesine) kadar sıralanan tüm sınıflar, bu iki koşulun farklı yollarla bir araya gelmesinin varyasyonlarıdır: kimi şablon bayrağından (ESC1, ESC6), kimi EKU'dan (ESC2, ESC3), kimi ACL'den (ESC4, ESC5, ESC7), kimi de ağ katmanındaki relay'den (ESC8) doğar.

Savunma stratejisi de bu farkındalık üzerine kurulmalıdır: CA'yı Tier 0 varlığı olarak koru, şablonları en az yetkiyle tasarla, tehlikeli bayrakları ve yönetim haklarını denetle, web enrollment'ı sertleştir, güçlü sertifika eşlemeyi uygula ve tüm PKI olaylarını izle. ADCS "arka planda sessizce çalışan servis" olmaktan çıkıp, en az Domain Controller kadar dikkatle korunan bir varlık haline geldiğinde, bu saldırı ailesinin büyük kısmı kökten etkisiz kalır.
