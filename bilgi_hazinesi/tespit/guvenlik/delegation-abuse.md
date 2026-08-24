# Kerberos Delegation Abuse (Unconstrained / Constrained / RBCD) — Tespiti

> Saha notu. Bu metin "event 4769'a bak" seviyesinin ötesine geçmek için yazıldı. Delegation istismarı, tek başına baktığınızda neredeyse hiç alarm üretmeyen, ama zincir olarak baktığınızda domain'in düştüğü sessiz saldırılardan biri. Asıl mesele sinyalleri bağlamak.

---

## 1. Özet: saldırı + naif tespit

Kerberos delegation, bir servisin kullanıcı adına başka bir servise kimlik doğrulaması yapabilmesi için tasarlanmış meşru bir özellik. Klasik örnek: web sunucusu, kullanıcının kimliğiyle arka plandaki SQL sunucusuna gider. Üç türü var ve tehdit modeli birbirinden çok farklı. **Unconstrained delegation** (TRUSTED_FOR_DELEGATION bayrağı) en tehlikelisi: bu bayrağa sahip bir hosta kimlik doğrulayan her hesabın TGT'si o hostun belleğine (LSASS) düşer; saldırgan hostu ele geçirmişse veya bir DC'yi o hosta doğru kimlik doğrulamaya zorlayabilirse, DC'nin TGT'sini alıp krbtgt seviyesine tırmanır. **Constrained delegation** (msDS-AllowedToDelegateTo dolu) bir hesabın yalnızca belirli SPN'lere delegasyon yapmasına izin verir; ama S4U2Self + S4U2Proxy kombinasyonuyla saldırgan, protocol transition açıksa herhangi bir kullanıcıyı (Administrator dahil) o hedef servise doğru taklit edebilir. **RBCD (Resource-Based Constrained Delegation)** ise izni kaynak nesnenin kendi üzerine (msDS-AllowedToActOnBehalfOfOtherIdentity) yazar; saldırgan bir bilgisayar hesabı oluşturup (MachineAccountQuota varsayılan 10) veya var olan bir bilgisayar nesnesine yazma yetkisi ele geçirip, o nesne üzerine kendi kontrolündeki hesabı yazar ve S4U ile hedefe admin olarak girer.

Naif tespit herkesin bildiği kısım: Kerberos servis bileti taleplerinde **Event ID 4769** (A Kerberos service ticket was requested) izlenir; delegation için özellikle S4U akışlarında görülen desenlere, `krbtgt` servis biletlerine, ya da RBCD kurulumunda değişen **Event ID 5136** (A directory service object was modified — özellikle msDS-AllowedToActOnBehalfOfOtherIdentity attribute'u) alarmlarına bakılır. Unconstrained tarafında ise "delegation zorlaması" için kullanılan **SMB spoolss named pipe** tespiti klasiktir; ekteki gerçek Sigma kuralı (`SMB Spoolss Name Piped Usage`, id `bae2865c-...`, logsource `zeek/smb_files`, `path|endswith: 'IPC$'` + `name: spoolss`) tam olarak PrinterBug/SpoolSample'ın DC'yi zorlamak için açtığı pipe'ı yakalar. Hacktool tarafında **Rubeus.exe** (`7ec2c172-...`), **KrbRelay.exe** (`e96253b8-...`), **RemoteKrbRelay.exe** (`a7664b14-...`) process_creation kuralları var — `Image|endswith` ve `OriginalFileName` üzerinden.

Bu kadarı bir sunum slaytını doldurur. Gerçek ortamda ise bu kuralların büyük kısmı ya sessiz kalır ya da yanlış pozitif seli üretir. Değer buradan sonra başlıyor.

---

## 2. Naif tespit neden yetmez

**"4769'a bak" tavsiyesinin temel sorunu: 4769 her yerde.** Sağlıklı bir domain'de saniyede onlarca, yüzlerce servis bileti talebi olur. Kullanıcı Outlook açıyor, dosya paylaşımına gidiyor, SharePoint'e bağlanıyor — hepsi 4769. Delegation istismarını "normal" 4769'lardan ayıran şey çoğu zaman **bilet içindeki tek bir alan**, ve o alan çoğu SIEM'e default gelmiyor ya da index'lenmiyor. S4U2Self akışını gerçekten yakalamak isterseniz, 4769'da **Transited Services** alanının dolu olmasına bakmanız gerekir (bir hesap başka bir kullanıcı adına bilet istediğinde bu alan populate olur). Ama pek çok kurum bu alanı ne parse eder ne de saklar. Yani "4769 izliyoruz" diyen SOC'ların çoğu, aslında sadece 4769'un var olduğunu görüyor; ayırt edici alanı görmüyor.

**Unconstrained tespitinin kör noktası: olay hosta düşmez, DC'ye düşer.** Unconstrained delegation istismarının kritik anı — TGT'nin saldırganın hostunun LSASS'ına düşmesi — Windows Security log'unda **hiçbir event üretmez**. LSASS belleğinde bilet olması normal bir Kerberos davranışı. Saldırgan orada Rubeus `monitor` ile oturup gelen TGT'leri toplar; bu tamamen pasif, ağ üzerinde spoolss zorlaması yapmadıysa hiçbir iz yok. Yani "unconstrained'i 4769 ile yakalarız" beklentisi yanlış; istismarın en önemli anı log'suz.

**Spoolss kuralının atlatılması çok kolay.** Ekteki spoolss Sigma kuralı yalnızca MS-RPRN (Print System Remote Protocol) named pipe'ını yakalar. Ama coercion yöntemleri çoğaldı: **PetitPotam (MS-EFSRPC)**, **DFSCoerce (MS-DFSNM)**, **ShadowCoerce (MS-FSRVP)** aynı "DC'yi bana kimlik doğrulamaya zorla" sonucunu farklı RPC protokolleriyle üretir ve spoolss pipe'ına hiç dokunmaz. Print Spooler servisini kapatmış (ki birçok kurum ZeroLogon/PrintNightmare sonrası kapattı) bir ortamda saldırgan zaten spoolss kullanamaz, PetitPotam'a geçer. Yani o Sigma kuralı yeşil yanarken domain düşebilir.

**Hacktool imza kuralları en zayıf halka.** `Rubeus.exe`, `KrbRelay.exe` kuralları `Image|endswith` ve `OriginalFileName`'a dayanır. Rubeus'un kaynağı public; saldırgan yeniden derler, sınıf/namespace isimlerini değiştirir, string'leri obfuscate eder, PE metadata'sındaki `Description: 'Rubeus'` ve `OriginalFileName`'ı temizler. Kuralın `CommandLine|contains: 'kerberoast '` gibi arg tabanlı selection'ları bile Rubeus'un dahili komut isimleri değiştirilirse ya da araç `.NET reflection` ile bellekten (Cobalt Strike `execute-assembly`, `inline-execute`) çalıştırılırsa — ki gerçek operasyonlarda diskte Rubeus.exe **hiç olmaz** — tamamen boşa düşer. Bu kurallar "script kiddie yakalama" değeri taşır, hedefli aktöre karşı değil.

**RBCD 5136 kuralının FP'si ve kör noktası.** msDS-AllowedToActOnBehalfOfOtherIdentity değişikliğini yakalamak mantıklı, ama iki sorun: (1) Bu attribute'un yazımını loglamak için DC'de **SACL'ler ve "Audit Directory Service Changes" advanced audit policy'sinin** açık olması şart; default GPO'da değil. Açmamışsanız 5136 hiç gelmez. (2) RBCD meşru olarak da kurulur — özellikle Exchange, SCCM, bazı sanallaştırma ve yedekleme çözümleri kurulum sırasında delegation attribute'larına dokunur. Bağlam olmadan her 5136 alarm ederseniz gürültüde boğulursunuz.

Özetle: naif kurallar ya ölçtükleri şeyi eksik ölçüyor, ya istismarın gerçek anını hiç görmüyor, ya tek bir alternatif teknikle atlatılıyor. Tespit, tekil kuraldan çıkıp **desen** olmak zorunda.

---

## 3. Korelasyon zinciri (asıl değer)

Delegation istismarında hiçbir tekil sinyal tek başına "ihlal" demeye yetmez. Yüksek güven, **zaman ve nesne ekseninde birbirini besleyen olayların** üst üste gelmesinden çıkar. Somut zincirler:

### Zincir A — Unconstrained delegation ile DC coercion (klasik "domain düşüşü")

1. **Anomali: yeni bir unconstrained delegation nesnesi.** Bir bilgisayar (veya daha kötüsü kullanıcı) hesabında `userAccountControl` içinde `TRUSTED_FOR_DELEGATION` (0x80000) bayrağı set edilir → **Event 4742** (computer account changed) ya da 4738, `userAccountControl` alanında bu bit. Meşru ortamda bu **çok nadir** olur; yeni bir unconstrained host haftada bir çıkmaz. Bu, zincirin "kurulum" adımı — saldırgan zaten böyle bir hosta erişimi varsa bu adımı atlar.
2. **Coercion:** kısa süre içinde o hosttan bir DC'ye doğru **spoolss/PetitPotam/DFSCoerce** — spoolss ise ekteki Zeek kuralı (`IPC$` + `spoolss`) tetikler; ağ tarafında bir DC hesabının (`DC01$`) kaynak IP'si **beklenmedik bir workstation/host** olur.
3. **DC'nin machine hesabıyla kimlik doğrulaması:** coercion başarılıysa DC, o unconstrained hosta Kerberos ile gider; hedef hostta **4624 Logon Type 3**, hesap = `DC01$`. Bir DC makine hesabının rastgele bir member server'a inbound kimlik doğrulaması **son derece anormal**.
4. **Tırmanış:** ele geçirilen DC TGT'siyle DCSync → **Event 4662** üzerinde `DS-Replication-Get-Changes` / `DS-Replication-Get-Changes-All` GUID'leri, kaynak bir DC olmayan hesap.

Tek başına adım 1 bir yapılandırma değişikliği. Tek başına adım 2 bir yazıcı taraması olabilir. Ama **"yeni unconstrained bayrağı (4742) + dakikalar içinde o hosttan DC'ye coercion + DC$ hesabının o hosta inbound logon'u + ardından anormal kaynaktan DCSync"** = kaçınılmaz olarak gerçek ihlal. Bu dört sinyalin ayrı ayrı FP oranı yüksek; **art arda ve aynı host ekseninde** gelme olasılıkları meşru dünyada neredeyse sıfır.

### Zincir B — RBCD takeover

1. **Yeni bir bilgisayar hesabı yaratılır:** düşük yetkili bir kullanıcı MachineAccountQuota'yı kullanarak `FAKE01$` oluşturur → **Event 4741** (computer account created), yaratan hesap = **normal bir domain user** (bir admin/join-server süreci değil). Bir stajyer hesabının bilgisayar nesnesi yaratması sinyal.
2. **RBCD attribute yazılır:** hedef bilgisayar nesnesi üzerinde `msDS-AllowedToActOnBehalfOfOtherIdentity` değişir → **Event 5136**, değeri az önce yaratılan `FAKE01$`'in SID'ini içeren bir security descriptor.
3. **S4U akışı:** kısa süre sonra `FAKE01$` hesabından **4769** — S4U2Self ve S4U2Proxy imzası; Transited Services alanı dolu; talep edilen servis hedef hostun `cifs/` veya `host/` SPN'i; kullanıcı alanı **Administrator** ya da yüksek yetkili biri.
4. **Erişim:** hedef hostta admin logon (**4624 Type 3**, `FAKE01$`), ardından muhtemelen SMB üzerinden lateral hareket / servis oluşturma.

Yine: adım 1 tek başına MAQ suistimali (bazı ortamlarda gürültülü). Adım 2 tek başına Exchange kurulumuyla karışır. Ama **"normal user'ın bilgisayar hesabı yaratması + o hesabın SID'inin dakikalar içinde başka bir bilgisayarın RBCD attribute'una yazılması + o hesaptan S4U ile Administrator taklidi"** zinciri tek yorumu olan bir olaydır.

### Zincir C — Constrained delegation + protocol transition

Constrained + protocol transition (TRUSTED_TO_AUTH_FOR_DELEGATION) olan bir servis hesabı ele geçirildiğinde, saldırgan S4U2Self ile herhangi bir kullanıcıyı o hesap adına "kendine" doğrulayabilir, sonra S4U2Proxy ile msDS-AllowedToDelegateTo'daki SPN'e gider. Sinyal: o servis hesabından **normalde hiç görülmeyen bir kullanıcı adına** (özellikle privileged/Protected Users olması gereken hesaplar) 4769. Buradaki değer **baseline**: her constrained servis hesabının delege ettiği kullanıcı kümesi dar ve tekrarlıdır; birden "Administrator adına" bilet çıkması sapmadır. Ayrıca **"non-forwardable" olması gereken bir biletin forwardable görünmesi** (Protected Users grubunun ve `Account is sensitive and cannot be delegated` bayrağının koruması) — bu korumaların olması gereken ama olmayan hesaplar hedef listesidir.

Bağlamı kuran cümle: delegation tespiti, "bir olay gördüm" değil, **"bir grafik gördüm"** işidir — nesne (hangi hesap), zaman (dakikalar penceresi), yön (kim kime doğruluyor) ve yetki (kim taklit ediliyor) eksenlerini aynı anda tutmak gerekir. Google size 4769'un ne olduğunu verir; bu dört eksenli grafiği vermez.

---

## 4. False positive gerçeği ve triage yargısı

Bu alarmları gerçek ortamda meşru üreten şeylerin listesi uzun ve onları tanımamak sizi ya kör tuning'e ya alarm yorgunluğuna sürükler:

- **SCCM / MECM:** İstemci push, OSD, task sequence'ler yoğun Kerberos ve bazen delegation yapılandırması yapar. SCCM site sunucularının ve dağıtım noktalarının davranışı "anormal servis biletleri" gibi görünebilir. SCCM'in "Network Access Account" ve site sistem hesapları baseline'a alınmalı.
- **Yedekleme yazılımları (Veeam, CommVault, NetBackup):** Bunlar servis hesaplarıyla çok sayıda hosta erişir; bazı kurulumlar constrained delegation ister. Yedek pencerelerinde (gece) 4769/4624 patlaması normaldir; saldırı da genelde geceyi sever — yani zaman tek başına ayırt edici değil, **kaynak host ve hedef SPN deseni** ayırt edicidir.
- **Vulnerability scanner'lar (Nessus, Qualys authenticated scan):** Kimlik doğrulamalı tarama, tek bir servis hesabından **çok geniş bir host kümesine** kısa sürede logon üretir. Bu, Kerberoasting/lateral hareketle en çok karışan meşru davranıştır. Scanner hesabının IP'si ve zamanlaması sabittir — allowlist edilmeli.
- **Exchange:** Klasik olarak geniş delegation hakları ve RBCD/attribute dokunuşları yapar. Exchange kurulumu ve CU güncellemeleri sırasında 5136 seli beklenir.
- **Admin scriptleri ve join otomasyonu:** Toplu bilgisayar join eden bir provisioning servisi 4741'i normalleştirir — ama o **belirli** provisioning hesabı için; rastgele bir kullanıcı için değil.

**Kıdemli analist gerçek/gürültü ayrımını nasıl yapar?** Sıra şu:

1. **Önce aktör hesabının kimliğine bak, olayın kendisine değil.** 5136 gördüğünde ilk soru "bu attribute'u kim değiştirdi?" — SCCM/Exchange servis hesabı mı, yoksa bir helpdesk kullanıcısı mı? Meşru üreticiler bilinen, sabit, servis hesaplarıdır. Bir insan kullanıcının (özellikle bir workstation'dan interaktif oturumla) RBCD attribute'una dokunması tek başına yüksek şüphe.
2. **İkinci olarak nesne yeniliğine bak.** Zincirdeki bilgisayar/servis hesabı **ne zaman yaratıldı?** Saldırı senaryosunda RBCD'ye yazılan SID genellikle **dakikalar önce** yaratılmış bir hesaba aittir. whenCreated ile olay zamanı arasındaki mesafe çok kısaysa, bu meşru operasyon değildir — meşru delegation kurulumu var olan yerleşik hesaplarla yapılır.
3. **Üçüncü, taklit edilen kimliğe bak.** S4U akışında hangi kullanıcı adına bilet çıktı? Meşru delegation son kullanıcıları taşır; saldırı **privileged hesapları** (Domain Admins, Administrator) taşır. "Administrator adına, daha önce hiç delege etmemiş bir hesaptan" en yüksek öncelikli triage sinyali.
4. **Çoklu alarmda önce zinciri kapatanı ele al.** Aynı anda 4741 + 5136 + 4769(S4U) + 4624 yanıyorsa, bunları **ayrı olaylar** olarak sıraya koymak hatadır — hepsi tek bir incident. Analist bunları `FAKE01$` nesne ekseninde birleştirir ve "coercion/DCSync var mı?" diye zincirin **sonuna** bakar; çünkü asıl hasar orada.

Kısacası triage burada "alarm skoruna" değil, **hesabın kimliği + nesnenin yaşı + taklit edilen yetki** üçlüsüne dayanır. Bu üçlü meşru üreticilerde neredeyse hep "tanıdık servis hesabı + eski nesne + son kullanıcı" verir; saldırıda "tanınmayan/insan hesap + yeni nesne + privileged taklit" verir.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan, yukarıdaki tespitlerin farkında ve kural dokümanlarında yazmayan yollarla atlatır. Her atlatmanın ikinci-derece bir tespiti vardır:

**Kaçınma 1 — Spoolss yerine PetitPotam/DFSCoerce/ShadowCoerce.** Ekteki spoolss kuralını atlatmak için MS-RPRN'e hiç dokunmaz.
→ *Karşı-tespit:* Zeek/SMB tarafında pipe adını `spoolss` ile sınırlamayın; `lsarpc`, `efsrpc`, `netdfs`, `fssagentrpc` named pipe'larına da bakın. Ama daha dayanıklı olan **davranışsal** tespit: kaynağı ne olursa olsun, bir **DC makine hesabının (`*$` ve DC OU'sundaki) beklenmedik bir member server/workstation'a inbound Kerberos/NTLM kimlik doğrulaması** (4624 Type 3, hesap bir DC$, hedef bir DC değil). Coercion protokolü ne olursa olsun bu son etki değişmez — DC dışarı doğru doğrulanır. Protokolü değil sonucu izleyin.

**Kaçınma 2 — Rubeus/KrbRelay'i diskten çalıştırmamak.** `execute-assembly`, `inline-execute`, ya da PowerShell reflection ile bellekte çalıştırır; `Image|endswith: '\Rubeus.exe'` boşa düşer.
→ *Karşı-tespit:* İmza yerine **Kerberos protokol anomalisine** in. Rubeus'un ürettiği bilet talepleri bazı karakteristikler taşır: örneğin `overpass-the-hash`/`asktgt` ile üretilen AS-REQ'lerde şifreleme türü (etype) ortamın normalinden sapabilir — özellikle **RC4 (etype 0x17)** talepleri, AES'in zorunlu olduğu bir ortamda kırmızı bayraktır (4768/4769 Ticket Encryption Type alanı). Ayrıca `execute-assembly` için **CLR yüklenmesi** ve `.NET` assembly load telemetrisi (Sysmon Event ID 7 — Image/ModuleLoad, `clr.dll`/`clrjit.dll`'in beklenmedik bir process'e — örn. `rundll32`, `notepad`, bir beacon host process'ine — yüklenmesi). Yani araç imzası yerine "olmaması gereken yerde .NET runtime + anormal etype".

**Kaçınma 3 — MachineAccountQuota'yı tetiklememek.** 4741 üretmemek için yeni hesap yaratmak yerine, **zaten yazma yetkisi olan var olan bir bilgisayar nesnesini** RBCD hedefi yapar (GenericWrite/WriteDACL ele geçirilmiş bir nesne). 4741 hiç oluşmaz.
→ *Karşı-tespit:* Zincirden 4741'i çıkarıp **5136'ya + ACL değişikliklerine** ağırlık verin. msDS-AllowedToActOnBehalfOfOtherIdentity'ye yazılan security descriptor'daki SID'in **ne olduğunu** çözün: yerleşik bir servis hesabı mı, yoksa saldırganın kontrolündeki bir hesap mı? Ayrıca bir bilgisayar nesnesi üzerinde **WriteDACL/GenericAll'un yeni verilmesi** (4670 — permissions on an object were changed, ya da 5136 nTSecurityDescriptor) kendi başına saldırının "kurulum" adımını yakalar.

**Kaçınma 4 — Yavaş/düşük profil (low and slow).** Zincir adımlarını dakikalar yerine **günlere** yayarak zaman-pencereli korelasyonu bozar.
→ *Karşı-tespit:* Zaman penceresini gevşetip **nesne kimliğini sabit tut.** Korelasyonu "5 dakika içinde" yerine "aynı `FAKE01$` nesnesi ekseninde, yaratıldığından beri" kur. Nesne ömrü boyu grafiğe bakmak, low-and-slow'u yakalayan tek yaklaşım. Ayrıca yaratılmış ama **hiç normal iş yükü olmayan** (sadece delegation/S4U trafiği üreten) bilgisayar hesapları başlı başına hunting sinyali.

**Kaçınma 5 — S4U yerine sadece TGT toplama (unconstrained).** RBCD/constrained akışlarının hiçbirini kullanmaz; sadece unconstrained hostta oturup pasif TGT toplar. S4U imzası hiç oluşmaz.
→ *Karşı-tespit:* Buradaki tek gerçekçi savunma **saldırının öncesine ve sonrasına** bakmaktır, çünkü toplama anı log'suz. Öncesi: unconstrained bayrağının varlığı ve **coercion** (mutlaka bir DC'yi çekmesi gerekir). Sonrası: toplanan DC TGT'sinin **kullanımı** — DCSync (4662 replication GUID'leri), ya da başka bir hostta o DC kimliğiyle ani aktivite. Ayrıca **proaktif azaltma tespit kadar önemli:** Domain Controller'ları ve hassas hesapları **Protected Users** grubuna almak ve `Account is sensitive and cannot be delegated` işaretlemek, unconstrained toplamayı büyük ölçüde etkisizleştirir; bu bayrakların **eksik olduğu** privileged hesapları hunting ile bulmak, tespit kadar değerli bir kontroldür.

Kedi-fare özeti: imza katmanı en kolay atlatılan, protokol/davranış katmanı (etype anomalisi, DC$ inbound logon, nesne-ekseni korelasyonu) en dayanıklı olanı. Saldırganın değiştiremeyeceği şey **Kerberos'un çalışma biçiminin kendisidir** — S4U akışının bilet yapısı, DC'nin coercion'da dışarı doğrulanması, delege edilen kimliğin bilette görünmesi. Tespiti bu değişmezlere bağlarsanız araç değişse de ayakta kalır.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** Delegation tespitinin en sinsi başarısızlığı, ihtiyacınız olan alanın olay şemasında farklı adla gelmesi ya da hiç gelmemesidir:

- **4769'daki ayırt edici alanlar** — `Service Name`, `Ticket Encryption Type`, `Transited Services`, `Client Address` — Windows'un XML şemasında `TargetUserName`, `ServiceName`, `TicketEncryptionType`, `TransmittedServices` gibi adlar taşır. Splunk'ta `TicketEncryptionType=0x17` ararken Sentinel'de aynı alan `SecurityEvent` tablosunda farklı normalize edilir; Elastic ECS'de `winlog.event_data.TicketEncryptionType` altındadır. Kuralı bir platformda yazıp diğerine "kopyalarsanız" sessizce hiçbir şey eşleşmez.
- **RC4 tespiti için Ticket Encryption Type = 0x17** kritik ama ortamınızda AES'e geçiş tam değilse bu alan gürültülüdür; önce **baseline**: normalde RC4 üreten legacy hesap/uygulama var mı?

**Varsayılan loglanmayan şeyler (bunlar açık değilse tespit yok):**

- **Audit Directory Service Changes** (Advanced Audit Policy → DS Access) — 5136 için **şart**. Default domain policy'de kapalı. Üstelik sadece policy'yi açmak yetmez; ilgili nesnelerde (özellikle bilgisayar nesneleri ve delegation attribute'ları) **SACL** tanımlı olmalı. SACL yoksa policy açık olsa bile event gelmez. Bu, RBCD tespitinin en sık atlanan ön koşulu.
- **Audit Kerberos Service Ticket Operations** — 4769 için gerekli; çoğu ortamda DC'lerde açıktır ama **hacim** nedeniyle bazı kurumlar filtreler ya da sadece failure'ları toplar (başarılı S4U'yu kaçırırsınız).
- **Audit Computer Account Management** — 4741 için.
- **Sysmon:** Event ID 7 (ImageLoad — CLR tespiti) ve Event ID 1 (process creation, hacktool arg'ları) için **doğru config şart.** ImageLoad çok gürültülüdür ve default SwiftOnSecurity config'i bile onu geniş filtreler; `clr.dll`/`clrjit.dll`'i beklenmedik process'lerde yakalamak için özel dahil-etme kuralı gerekir. Ayrıca Sysmon Event ID 8 (CreateRemoteThread) ve 10 (ProcessAccess — LSASS'a erişim) unconstrained toplama sonrası bellekten bilet okuma için tamamlayıcı.
- **Ağ tarafı (spoolss/PetitPotam):** Ekteki Zeek kuralının çalışması için SMB trafiğini gören bir **Zeek/network sensor** gerekir; salt Windows log'larıyla named pipe adını (`spoolss`) güvenilir yakalamak zordur. Endpoint'te RPC filtresi (RPC Firewall gibi) yoksa bu görünürlük ağdan gelmek zorunda.

**Platform farkları (tuning gerçeği):**

- **Splunk:** Ham esneklik yüksek; korelasyonu genelde `transaction`/`stats` ile nesne ekseninde (`ComputerName`/`TargetUserName`) pencereleyerek kurarsınız. Risk: 4769 hacmi indexer maliyetini patlatır; delegation için genelde **saha filtrelemesi** (yalnızca S4U/Transited dolu, yalnızca RC4, yalnızca DC$ inbound) yaparak hacmi düşürmek şart. `tstats` ve data model (özellikle Authentication data model) kullanmak performans için gerekli.
- **Sentinel:** KQL ile çok-tablo join doğal (`SecurityEvent` + `IdentityInfo` + UEBA). Avantaj: **Entity Behavior** ve built-in UEBA, "bu servis hesabı ilk kez privileged bir kullanıcı adına bilet istedi" tarzı baseline sapmasını hazır verir. Dezavantaj: ingest maliyeti ve DC log'larının AMA/DCR ile doğru toplanması; DCR'de yanlış filtre koyarsanız 5136/4769'u hiç görmezsiniz. `Watchlist` ile bilinen servis hesaplarını (SCCM, Veeam, scanner) allowlist etmek pratik yol.
- **Elastic:** ECS normalizasyonu güçlü ama `winlog.event_data` altındaki Kerberos alanları çoğu zaman ECS'ye tam map'lenmez — custom ingest pipeline gerekir. EQL sequence sorguları (`sequence by winlog.computer_object ...`) zincir tespiti için biçilmiş kaftandır; nesne-ekseni korelasyonunu EQL `sequence` ile kurmak Splunk transaction'dan daha temiz olur.

**En büyük tuning gerçeği:** Bu tespitlerin hiçbiri "kural aç, bitti" değildir. Her biri bir **envanter** ister — ortamdaki tüm meşru delegation'ların (hangi hesap, hangi SPN, protocol transition açık mı) çıkarılmış listesi (`Get-ADObject` ile `TrustedForDelegation`, `TrustedToAuthForDelegation`, `msDS-AllowedToDelegateTo`, `msDS-AllowedToActOnBehalfOfOtherIdentity` dolu tüm nesneler). Bu envanter hem allowlist'inizin temeli hem de saldırı yüzeyinizin haritasıdır: **"olmaması gereken bir yerde delegation"** çoğu zaman istismardan önce, konfigürasyon anomalisi olarak yakalanır. Kıdemli detection engineer'ın işi çoğunlukla alarm yazmak değil, önce bu envanteri çıkarıp normalin sınırlarını çizmektir — çünkü delegation'da "anormal" ancak "normal"i tam bildiğinizde görünür hale gelir.

---

*Kapanış yargısı: Delegation istismarı, tekil olay avcılığının en çok yanılttığı alanlardan biri. 4769'u izlemek sizi güvende hissettirir ama korumaz. Gerçek tespit üç şeye dayanır — (1) meşru delegation envanterini bilmek, (2) nesne/zaman/yön/yetki eksenlerinde zincir kurmak, (3) imza yerine Kerberos'un değişmez davranışlarına (DC$ inbound logon, etype anomalisi, S4U'da privileged taklit, coercion'un DC'yi dışarı doğrulaması) bağlamak. Araç ve protokol değişir; bu değişmezler kalır.*
