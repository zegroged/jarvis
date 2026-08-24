# AD Trust İlişkileri Saldırıları: Forest/Domain Trust Kötüye Kullanımı, SID History Injection ve Cross-Forest Kerberoasting

## Giriş: Neden Bu Konu Tekli Domain Bilgisinden Farklı ve Kritik

Kerberoasting, DCSync ve Golden Ticket gibi teknikler tek bir Active Directory (AD) domain'i içinde çalışan saldırganın nasıl yetki yükselttiğini ve kalıcılık kurduğunu anlatır. Ancak gerçek kurumsal ortamların büyük çoğunluğu tek domain değildir: şirket birleşmeleri, coğrafi ayrım, güvenlik izolasyonu veya tarihsel miras (legacy) nedenleriyle çok sayıda domain ve orman (forest) birbirine **trust (güven) ilişkileriyle** bağlıdır. Bir saldırgan tek bir domain'i tamamen ele geçirse bile, eğer o domain başka bir domain veya forest'a güveniyorsa (ya da güveniliyorsa), saldırı yüzeyi o sınırın ötesine geçebilir.

Bu konunun ayrı ve derinlemesine ele alınması gerekiyor çünkü:

1. **Güven sınırı, güvenlik sınırı değildir.** Çoğu yönetici "iki domain arasında trust var ama izin verilmiyor" diye düşünür; oysa trust'ın teknik mekanizması (özellikle SID History ve trust key'ler) çok daha geniş bir yetki devrini mümkün kılabilir.
2. **Forest, gerçek güvenlik sınırıdır; domain değildir.** Microsoft'un kendi dokümantasyonu da tarihsel olarak bunu netleştirmiştir: bir forest içindeki Enterprise Admins ve Domain Admins grupları, forest'taki her domain'i etkileyebilecek yetkilere sahiptir (özellikle şema ve yapılandırma bölümleri paylaşıldığı için).
3. **Cross-forest senaryolarda** (iki ayrı forest arasında kurulan trust) sınır teorik olarak daha güçlüdür, ancak yanlış yapılandırma (örneğin SID filtering'in kapalı olması, seçici kimlik doğrulamanın uygulanmaması) bu sınırı da eritir.
4. Bu teknikler, saldırganın "bir domain'i ele geçirdim, iş bitti" varsayımını çürütür — savunmacı için asıl risk genellikle **yatay/dikey geçiş yollarının haritalanmamış olmasıdır**.

Bu makale, defans mühendisi bakış açısıyla üç ana temayı işler: (1) trust ilişkilerinin mekaniği ve kötüye kullanımı, (2) SID History injection/sidejacking, (3) cross-forest Kerberoasting ve delegasyon istismarı.

---

## Bölüm 1: AD Trust Mimarisi — Temel Kavramlar

### Trust Nedir, Nasıl Çalışır

Bir trust, iki domain (veya forest) arasında kimlik doğrulama yollarının kurulmasıdır. Teknik olarak, trust ilişkisi her iki tarafta bir **trust account** (paylaşılan bir sır/şifre, "trust key") üzerinden temsil edilir. Bu trust key, iki domain'in Domain Controller'ları (DC) arasında Kerberos referral (yönlendirme) mekanizmasının ve NTLM pass-through kimlik doğrulamasının temelini oluşturur.

Trust'ların birkaç boyutu vardır ve her biri saldırı yüzeyini farklı şekillde etkiler:

- **Yön (directional):** Tek yönlü (one-way) veya iki yönlü (two-way, bidirectional). A domain'i B'ye güveniyorsa, B'deki kullanıcılar A'daki kaynaklara erişebilir (güvenen taraf A'dır, güvenilen taraf B'dir — yön kafa karıştırıcı olabilir: "A trusts B" demek "B'nin kullanıcıları A'da kimlik doğrulayabilir" demektir).
- **Geçişlilik (transitivity):** Transitive trust, A-B ve B-C trust'ları varsa A-C arasında da örtük bir yol oluşturabilir (forest içi domain'ler arasında varsayılan olarak transitive'dir — parent-child ve tree-root trust'lar). Forest trust'lar da transitive'dir ama forest sınırının ötesine (üçüncü bir forest'a) geçmez.
- **Kapsam:** Parent-child, tree-root, external (non-transitive, forest'lar arası noktasal bağlantı), forest trust (iki forest'ın kök domain'leri arasında, tüm forest'ları kapsayan transitive bağlantı), realm trust (Kerberos realm'leri arası, örn. AD ile MIT Kerberos).

### Neden Forest Güvenlik Sınırıdır, Domain Değildir

Bunun kök nedeni **şema ve yapılandırma paylaşımı**dır. Bir forest içindeki tüm domain'ler aynı şema bölümünü ve yapılandırma bölümünü paylaşır; bu da Enterprise Admins grubunun (forest kök domain'inde bulunur) forest genelinde nesne oluşturma/değiştirme yetkisine sahip olması, ve KRBTGT hesaplarının forest içi SID History mekanizmasıyla ilişkili olması anlamına gelir. Ayrıca **forest içindeki her DC, forest genelinde geçerli olan bazı güven zincirlerine (implicit trust) sahiptir.** Bu nedenle "child domain ele geçirildi ama parent domain etkilenmez" varsayımı yanlıştır — özellikle SID History enjeksiyonu (aşağıda) bu varsayımı doğrudan çürütür.

### Savunma Açısından İlk Çıkarım

Bir ortamı değerlendirirken sorulması gereken soru "kaç domain'im var" değil, **"kaç forest'ım var ve aralarındaki trust'ların yönü, geçişliliği ve SID filtering durumu nedir"** olmalıdır. `nltest /domain_trusts` veya `Get-ADTrust` (AD PowerShell modülü) ile trust envanteri çıkarmak, herhangi bir AD güvenlik değerlendirmesinin ilk adımı olmalıdır.

---

## Bölüm 2: SID History Injection / Sidejacking

### Tanım ve Amaç (Meşru Kullanım)

SID History, bir kullanıcı/grup nesnesinin `sIDHistory` özniteliğinde geçmiş SID'lerini taşımasını sağlayan bir mekanizmadır. Amacı **domain migrasyonlarında** (örneğin ADMT — Active Directory Migration Tool ile bir kullanıcıyı eski domain'den yeni domain'e taşırken) kullanıcının eski domain'deki kaynaklara erişimini kesintisiz sürdürmesidir: kullanıcının yeni SID'i farklı olsa da, token'ında eski SID'i de taşıdığı için eski ACL'lerde tanınmaya devam eder.

### Kök Neden / Çalışma Mantığı

Windows'ta bir kullanıcı oturum açtığında, Kerberos TGT'sinin **PAC (Privilege Attribute Certificate)** yapısı içine kullanıcının birincil SID'i VE `sIDHistory` alanındaki tüm SID'ler dahil edilir. Kaynak sunucu (örneğin bir dosya sunucusu) erişim kontrolü yaparken, gelen token'daki SID listesinin **tamamını** ACL karşısında değerlendirir — sadece birincil SID'i değil.

Buradaki kök neden şudur: **PAC, DC tarafından imzalanan ve DC'nin ürettiği bir yapıdır; istemci tarafından oluşturulmaz.** Yani normalde bir kullanıcı kendi SID History'sine rastgele bir SID ekleyemez — bu alan yalnızca DC'nin dizin verisinden (`sIDHistory` özniteliği) okunur ve PAC'a yazılır. Saldırı burada devreye girer: **eğer saldırgan bir domain'in DC'sinde yönetici (Domain Admin veya eşdeğeri, özellikle DCSync yetkisine sahip bir hesap) düzeyinde kontrol elde ederse**, o domain'deki herhangi bir kullanıcının `sIDHistory` özniteliğine, **başka bir (hedef) domain'deki ayrıcalıklı bir grubun SID'ini (örn. Domain Admins veya Enterprise Admins SID'i) yazabilir.** Bu işlem klasik olarak "SID History injection" veya "sidejacking" olarak adlandırılır.

Bunun mümkün olmasının teknik önkoşulları:
- Saldırganın hedef yazma işlemini yapabilmesi için genellikle **DC'ye replikasyon düzeyinde erişim** (DCSync benzeri, `Replicating Directory Changes` haklarına sahip bir hesap) veya doğrudan NTDS.dit üzerinde manipülasyon gerekir — bu, `sIDHistory` özniteliğinin normal LDAP yazma izinleriyle korunmuş olmasındandır (varsayılan olarak yalnızca sistem düzeyi replikasyon mekanizmaları bunu yazabilir).
- Hedef domain/forest, kaynak domain'den gelen SID History'yi **filtrelemiyor** olmalıdır (bkz. SID Filtering, aşağıda).

### Neden Bu Kadar Tehlikeli: Cross-Domain / Cross-Forest Ayrıcalık Yükseltme

Bir saldırgan A domain'inde (görece daha az kritik, belki bir yan şirket domain'i) Domain Admin düzeyinde ele geçirme sağladığında ve A ile B (kritik/ana forest) arasında bir trust varsa: A domain'indeki bir kullanıcının `sIDHistory`'sine B domain'inin Enterprise Admins SID'ini enjekte ederse, bu kullanıcı B domain'inde oturum açtığında (veya B'deki bir kaynağa eriştiğinde) PAC içinde B'nin Enterprise Admins SID'i taşınır ve **B domain'i bu kullanıcıyı kendi Enterprise Admin'i gibi değerlendirir.** Bu, "düşük değerli domain'i ele geçir, yüksek değerli forest'a SID History ile atla" saldırı zincirinin temelidir.

Bunun kavramsal olarak Golden Ticket'tan farkı şudur: Golden Ticket, KRBTGT hash'i çalınarak **sahte** bir TGT üretmektir (offline forge). SID History injection ise **gerçek** bir DC replikasyon mekanizmasını kötüye kullanarak dizindeki veriyi kalıcı olarak değiştirmektir — yani kalıcılık (persistence) açısından daha "meşru veri" gibi görünür ve tespiti farklı sinyaller gerektirir.

### SID Filtering: Birincil Savunma Mekanizması

Microsoft, bu riski azaltmak için **SID Filtering (Quarantine)** özelliğini varsayılan olarak devreye almıştır:

- **External trust'larda ve forest trust'larda SID Filtering varsayılan olarak açıktır.** Bu, gelen kimlik doğrulama isteklerinde, güvenen tarafın DC'sinin, güvenilen domain'in **kendi SID namespace'i dışındaki** SID'leri (yani sIDHistory'de taşınan yabancı domain SID'lerini) PAC'tan **temizlemesi (strip)** anlamına gelir.
- **Forest içi (intra-forest) trust'larda (parent-child, tree-root) SID Filtering varsayılan olarak KAPALIDIR.** Bunun nedeni, meşru forest içi migrasyon senaryolarının SID History'ye ihtiyaç duyması ve forest'ın zaten tek güvenlik sınırı olarak kabul edilmesidir. Bu, **kök neden**dir: forest içindeki bir child domain'i ele geçiren saldırgan, SID Filtering devre dışı olduğu için forest'ın kök (root) domain'ine veya kardeş domain'lere SID History enjeksiyonuyla sıçrayabilir. Bu senaryo genellikle "child domain'i ele geçir, forest'ı ele geçir" olarak anılır ve **forest'ın neden gerçek güvenlik sınırı olduğunu** doğrudan kanıtlar.

Yöneticilerin sıkça düştüğü yanlış varsayım: "SID Filtering her trust'ta otomatik açıktır." Gerçekte bu yalnızca forest sınırını aşan (external, forest) trust'lar için geçerlidir; forest içi trust'larda manuel olarak ek önlem (`quarantine` bayrağı, `netdom trust /quarantine:yes` benzeri araçlarla) alınmadıkça koruma yoktur — ve bu genellikle child domain'lerdeki meşru migrasyon senaryolarını bozacağı için manuel olarak da açılmaz.

### Selective Authentication ile Ayrım

SID Filtering'e ek olarak **Selective Authentication**, forest/external trust'larda kullanılabilecek ikinci bir kontrol katmanıdır: bu özellik açıkken, güvenilen domain'deki kullanıcıların güvenen domain'deki kaynaklara erişebilmesi için o kaynak üzerinde **açıkça "Allowed to Authenticate" izni** verilmiş olması gerekir (varsayılan olarak serbest geçiş yoktur). Bu, SID History'nin geçerli olduğu durumlarda bile **yatay hareketi** (lateral movement) sınırlar çünkü saldırgan sadece PAC'a doğru SID'i koydursa da, hedef makinede oturum açma iznine sahip olmayabilir.

### Tespit (Detection)

SID History istismarını tespit etmek için birkaç sinyal katmanı vardır:

1. **Dizin değişikliği izleme:** `sIDHistory` özniteliğine yapılan her yazma işlemi, Windows Security Event Log'da domain denetimi (auditing) açıksa **Event ID 4738 (a user account was changed)** veya replikasyon bağlamında **4928/4929/4932 gibi replikasyon olayları** ile ilişkilendirilebilir. Kritik olan, `sIDHistory` alanının değiştiği anları ayırt edebilecek granularity'de directory service değişikliği denetiminin (`Audit Directory Service Changes`) açık olmasıdır — bu varsayılan olarak kapalıdır ve çoğu ortamda etkinleştirilmemiştir.
2. **Anormal SID History varlığı:** Ortamda meşru bir migrasyon projesi yürütülmüyorsa, herhangi bir kullanıcı nesnesinde `sIDHistory` dolu olması başlı başına şüpheli bir bulgudur. BloodHound benzeri araçlarla veya `Get-ADUser -Filter * -Properties SIDHistory` ile periyodik envanter çıkarmak, "beklenmeyen SID History" anomalisini yakalar.
3. **Yüksek ayrıcalıklı SID'lerin foreign domain'lerden PAC içinde görülmesi:** DC'lerde Kerberos PAC doğrulama olaylarını izleyen (özellikle domain controller'ların KDC event log'ları) SIEM kuralları, bir kullanıcının token'ında **kendi domain'ine ait olmayan** yüksek ayrıcalıklı grup SID'i (örneğin Enterprise Admins'in well-known SID formatı, `S-1-5-21-<root-domain-id>-519`) taşıyıp taşımadığını karşılaştırabilir.
4. **DCSync/replikasyon izleme:** SID History enjeksiyonu genellikle bir DCSync benzeri erişim gerektirdiğinden, `dcsync-dcshadow.md` konusunda anlatılan tespit yöntemleri (beklenmeyen kaynaklardan `DS-Replication-Get-Changes-All` çağrıları) burada da doğrudan uygulanır.

### Savunma (Defense)

- **Forest sınırını gerçek güvenlik sınırı olarak yönetin:** Ayrı forest'lar arasında olduğu gibi, tek bir forest içindeki child domain'leri de "aynı düzeyde güvenilir" varsaymayın; child domain'e Domain Admin yetkisi olan hesapları forest'ın en yüksek değerli varlığı gibi koruyun (Tier 0 muamelesi).
- **SID Filtering'i mümkün olan her yerde (özellikle external ve forest trust'larda) doğrulayın ve açık tutun**; kapatma talepleri (bazı meşru senaryolarda geçici olarak istenir) mutlaka zaman sınırlı ve loglu olmalıdır.
- **Selective Authentication'ı, özellikle kritik kaynaklar barındıran domain'lere gelen trust'larda etkinleştirin.**
- **Directory Service Changes denetimini** kritik özniteliklerde (sIDHistory dahil) etkinleştirin ve SIEM'e yönlendirin.
- **Düzenli SID History envanteri** çıkarıp beklenmeyen girdileri inceleyin; migrasyon projeleri bittikten sonra `sIDHistory` alanlarının temizlenmesi (ADMT'nin de önerdiği bir uygulamadır) saldırı yüzeyini kalıcı olarak azaltır.

---

## Bölüm 3: Cross-Forest Kerberoasting ve Delegasyon İstismarı

### Kerberoasting'in Cross-Forest Bağlamda Nasıl Farklılaştığı

Klasik Kerberoasting, bir SPN'ye (Service Principal Name) sahip hesap için TGS (service ticket) talep edip, bu ticket'ın şifreli kısmını (hizmet hesabının parola hash'iyle şifrelenmiş) offline kırmaya çalışmaktır. Bu teknik **tek domain içinde** doğrudan çalışır çünkü saldırgan zaten o domain'in KDC'sinden ticket talep edebilir.

Cross-forest senaryoda kök soru şudur: **Forest trust varken, A forest'ındaki bir kullanıcı B forest'ındaki bir SPN için ticket talep edebilir mi?** Cevap: **Evet, eğer forest trust bunu destekliyorsa (Kerberos referral mekanizması üzerinden).** Bu mekanizmanın nasıl çalıştığını anlamak, saldırının kök nedenini anlamanın anahtarıdır.

### Kerberos Referral Mekanizması (Kök Neden)

Forest trust'lar transitive'dir ve Kerberos, **referral ticket** zinciri ile çalışır: A forest'ındaki bir kullanıcı, B forest'ındaki bir kaynağın SPN'i için TGS talep ettiğinde, kendi DC'sine gider; kendi DC'si bu SPN'i tanımadığı için (kendi domain'inde yok), kullanıcıya **kendi forest'ının trust hesabı üzerinden şifrelenmiş bir referral ticket** verir. Kullanıcı bu referral ticket'ı B forest'ının (veya B forest'ındaki ilgili domain'in) DC'sine sunar; B'nin DC'si, referral ticket'ı **iki forest arasındaki paylaşılan trust key** ile doğrular ve eğer geçerliyse, sonunda hedef SPN için gerçek bir TGS üretir.

Bu zincirin kritik noktası: **B forest'ının DC'si, sonunda talep edilen SPN sahibi hesabın (hizmet hesabının) kendi parola hash'i ile TGS'yi şifreler** — tıpkı tek domain senaryosunda olduğu gibi. Yani zincir ne kadar uzun olursa olsun (birden fazla domain/forest referral'ı üzerinden geçse bile), **son adımda üretilen ticket, hedef hizmet hesabının hash'iyle korunur** ve bu, saldırgana yine offline kırma (kerberoasting) fırsatı verir.

Buradan çıkan kök neden şudur: **Forest trust, kimlik doğrulamayı forest sınırının ötesine taşıyabilen bir Kerberos referral zinciri kurar; ve bu zincirin sonunda hedeflenen her SPN, tek domain'deki gibi Kerberoasting'e karşı savunmasızdır — trust bunu engellemez, sadece kimin kime ulaşabileceğini (SID filtering, selective auth) kısıtlayabilir.**

### Nasıl Çalışır (Kavramsal Akış)

1. Saldırgan A forest'ında (düşük güvenlik seviyeli, örneğin ele geçirilmiş bir yan kuruluş domain'i) sıradan, kimliği doğrulanmış bir kullanıcı hesabına sahiptir.
2. A ile B forest'ı arasında iki yönlü (veya en azından A→B yönünde) bir forest trust vardır ve Selective Authentication **etkin değildir** (yani A'daki her kullanıcı B'deki her kaynağa erişim için kimlik doğrulayabilir).
3. Saldırgan, B forest'ında SPN kayıtlı hizmet hesaplarını keşfeder (LDAP sorgusu, global catalog üzerinden `servicePrincipalName` dolu hesapları listeleyerek — global catalog forest genelinde arama sağladığı için bu adım cross-forest'ta bile mümkündür).
4. Saldırgan, bu SPN'ler için TGS talep eder; istek referral zinciri üzerinden B forest'ının ilgili DC'sine ulaşır ve B, hizmet hesabının hash'iyle şifrelenmiş TGS döner.
5. Saldırgan bu TGS'yi offline olarak kırmaya çalışır (hizmet hesabının parolası zayıfsa başarılı olur) — sonuç, B forest'ında geçerli bir hizmet hesabı kimlik bilgisi elde etmektir.

### Cross-Forest Delegasyon İstismarı (Constrained/Unconstrained Delegation ile Kesişim)

Delegasyon (bir hizmetin başka bir hizmete kullanıcı adına erişebilmesi) cross-forest bağlamda ek risk katar:

- **Unconstrained delegation**, forest sınırları arasında genellikle kısıtlıdır çünkü TGT'nin tamamen forwarding'i doğası gereği daha tehlikeli kabul edilir ve modern AD forest trust yapılandırmalarında varsayılan olarak bu tür genişletilmiş güven zinciri önerilmez.
- **Resource-Based Constrained Delegation (RBCD)**, hedef kaynağın kendi üzerinde (`msDS-AllowedToActOnBehalfOfOtherIdentity` özniteliği) kimin delegasyon yapabileceğini tanımladığı bir modeldir. Cross-forest RBCD'nin kök nedeni tartışmalıdır ve ortam sürümüne göre davranış farklılık gösterebilir; kesin davranışı iddia etmek yerine **kavramsal riski** vurgulamak daha doğrudur: eğer bir forest'taki bir hesap/nesne, diğer forest'taki bir kaynağın delegasyon listesine (doğrudan SID referansıyla veya SID History üzerinden) girebiliyorsa, bu da forest sınırını aşan bir yetki devri yoludur. Bu nedenle RBCD yapılandırmalarının forest trust'lar bağlamında **düzenli olarak denetlenmesi** gerekir; spesifik sürüm davranışları için üretici dokümantasyonu esas alınmalıdır.

### Neden Bu Yaygın Bir Kör Nokta

Kurumlar genellikle "iş ortağı forest trust'ı" veya "birleşme sonrası geçici trust" kurarken şu iki adımı atlar:
1. Selective Authentication'ı etkinleştirmek (çünkü bu, iş süreçlerini yavaşlatır ve her kaynağa manuel izin gerektirir — operasyonel sürtünme yaratır).
2. Karşı taraftaki hizmet hesabı parola hijyenini (uzunluk, rastgelelik, gMSA kullanımı) trust kurulmadan önce denetlemek.

Sonuç: düşük güvenlik seviyeli bir ortakla kurulan trust, aslında ana forest'taki zayıf parolalı hizmet hesaplarını **dışarıdan erişilebilir Kerberoasting hedefi** haline getirir.

### Tespit

- **Cross-forest TGS taleplerinin izlenmesi:** DC'lerdeki Kerberos Event ID 4769 (a Kerberos service ticket was requested) olayları, talep eden hesabın realm/domain bilgisiyle birlikte incelenmelidir. Aynı kısa zaman diliminde **çok sayıda farklı SPN için RC4 şifreleme türü (etype 0x17) ile TGS talebi**, klasik Kerberoasting imzasıdır ve cross-forest kaynaklı istekler için de geçerlidir — burada ek olarak isteğin **hangi trust/realm üzerinden geldiğinin** loglanması ayırt edici sinyaldir.
- **Global Catalog sorgu anomalileri:** Normalde etkileşimde olmayan bir forest'tan gelen hesapların, kısa sürede çok sayıda SPN'li nesneyi sorgulaması (LDAP arama desenleri) keşif (recon) aşamasının işaretidir.
- **RC4 kullanımının izlenmesi:** Modern ortamlarda AES destekleniyorsa, servis ticket taleplerinde hâlâ RC4 görülmesi (etype downgrade), hem tek domain hem cross-forest Kerberoasting için önemli bir erken uyarı sinyalidir çünkü RC4 hash'leri kırmaya karşı görece daha zayıftır.
- **Trust üzerinden gelen kimlik doğrulama hacminin baseline'lanması:** Bir forest trust'ının normalde çok düşük hacimde kullanıldığı biliniyorsa, ani bir artış (özellikle SPN keşfi ve TGS taleplerinde) anomali tespiti için güçlü bir sinyaldir.

### Savunma

- **Selective Authentication'ı forest trust'larda varsayılan uygulama haline getirin**, özellikle iş ortağı veya birleşme senaryolarında; bu, kimlik doğrulamanın gerçekleşebileceği kaynak kümesini daraltarak referral zincirinin sonuna ulaşabilecek SPN sayısını azaltır.
- **Hizmet hesaplarında gMSA (group Managed Service Account) kullanımını yaygınlaştırın:** gMSA'lar otomatik, uzun ve rastgele parolalar kullandığından offline kırma pratik olarak anlamsız hale gelir — bu, Kerberoasting'in kök nedenini (zayıf/insan tarafından belirlenen hizmet hesabı parolaları) doğrudan ortadan kaldırır.
- **AES zorunluluğu:** Mümkün olan her yerde RC4'ü devre dışı bırakıp yalnızca AES128/AES256 destekleyen yapılandırmaya geçin; bu, hem kırma maliyetini artırır hem de RC4 kullanımını başlı başına bir anomali sinyaline dönüştürür.
- **Trust envanterini ve gerekliliğini periyodik gözden geçirin:** Artık ihtiyaç duyulmayan (proje bitmiş, birleşme tamamlanmış) trust'ları kaldırın; "geçici" trust'lar sıkça kalıcı hale gelir ve unutulmuş saldırı yolu oluşturur.
- **Delegasyon yapılandırmalarını (özellikle RBCD ve herhangi bir cross-forest SID referansı) düzenli denetleyin**; BloodHound gibi ilişki haritalama araçlarıyla (forest genelinde veri toplanabiliyorsa) "hangi düşük ayrıcalıklı hesap, hangi zincir üzerinden yüksek ayrıcalıklı bir kaynağa ulaşabiliyor" sorusunu görselleştirin.
- **Tier modelini forest sınırını da kapsayacak şekilde genişletin:** Tier 0 varlıkları (DC'ler, KRBTGT, Enterprise/Domain Admins) yalnızca kendi domain'inizde değil, güvenilen tüm forest'larda da tanımlayıp izleyin.

---

## Yaygın Hatalar (Genel Özet)

1. **"Trust var ama kimse kullanmıyor, risksiz" varsayımı.** Kullanılmayan bir trust, saldırgan için hâlâ geçerli bir yoldur; kullanım hacmi düşük olması riski azaltmaz, sadece tespiti zorlaştırır.
2. **SID Filtering'in her trust türünde otomatik olduğunu sanmak.** Forest içi trust'larda varsayılan olarak kapalıdır; bu netleştirilmezse child domain'ler sessizce tam forest riski taşır.
3. **Forest'ı değil domain'i güvenlik sınırı sanmak.** Bu varsayım, Tier 0 kapsamının yanlış çizilmesine ve child domain'lerdeki zayıf kontrol seviyesinin fark edilmemesine yol açar.
4. **Cross-forest senaryoda hizmet hesabı hijyenini denetlemeden trust kurmak.** Bir ortakla kurulan trust, kendi zayıf hizmet hesaplarınızı ortağa açık hale getirebilir — ve tam tersi.
5. **Directory Service Changes denetimini açmamak.** Bu olmadan, `sIDHistory` gibi kritik özniteliklerdeki değişiklikler tamamen görünmez kalır; olay sonrası adli inceleme de imkansızlaşır.
6. **Selective Authentication'ı "operasyonel yük" gerekçesiyle atlamak.** Kısa vadeli sürtünme, uzun vadeli açık uçlu bir güven genişlemesine tercih edilmelidir.

---

## Sonuç

AD trust ilişkileri, tek domain güvenlik modelini kurumsal ölçekte genişletirken, aynı zamanda o modelin sınırlarını da genişletir. SID History injection, DC düzeyinde kontrol elde eden bir saldırganın normalde yalnızca migrasyon senaryoları için var olan bir mekanizmayı, forest içi veya (SID filtering yoksa) forest'lar arası ayrıcalık yükseltme aracına dönüştürmesidir. Cross-forest Kerberoasting ise Kerberos referral zincirinin doğal bir sonucu olarak, forest trust'ın kimlik doğrulamayı taşıdığı her yerde klasik Kerberoasting riskinin de taşındığını gösterir. Savunma tarafında kilit ilke değişmez: **güven sınırlarını haritalayın, varsayılan izinleri daraltın (Selective Authentication, SID Filtering), Tier 0 kapsamını forest genelinde tanımlayın ve dizin düzeyindeki kritik değişiklikleri (özellikle sIDHistory ve replikasyon hakları) görünür kılın.** Trust ilişkilerini "bir kere kurulur, unutulur" değil, sürekli denetlenmesi gereken canlı bir saldırı yüzeyi olarak yönetmek gerekir.
