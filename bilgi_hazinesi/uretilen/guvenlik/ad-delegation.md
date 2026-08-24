# Active Directory Delegation Saldırıları: Unconstrained, Constrained ve RBCD

## Giriş ve Bağlam

Kerberos delegation (yetki devri), Active Directory ortamlarında bir servisin, kullanıcının kimliğine bürünerek (impersonation) başka bir servise onun adına erişebilmesini sağlayan bir mekanizmadır. Kulağa masum gelen bu tasarım, saldırganlar için en verimli **privilege escalation** (yetki yükseltme) ve **lateral movement** (yanal hareket) yollarından birine dönüşmüştür. Sebebi basittir: delegation, tasarımı gereği "bir kimliğin başka bir yerde yeniden kullanılmasına" izin verir. Yani zaten kimlik hırsızlığının (credential/ticket theft) tam da amaçladığı sonucu, protokolün meşru bir özelliği olarak sunar.

Bu makale delegation'ın üç ana biçimini (unconstrained, constrained, resource-based constrained delegation / RBCD) hem çalışma mantığı hem de kök nedenleri açısından derinlemesine ele alır; her biri için istismar zincirlerini ve karşılık gelen savunma yaklaşımlarını birlikte verir. Amaç ezberlenecek bir komut listesi değil, "neden bu saldırı mümkün oluyor ve nasıl kırılıyor" sorusuna cevap veren bir zihinsel model kurmaktır.

## Kerberos Temeli: Delegation Neden Var?

Delegation'ı anlamak için önce sorunu anlamak gerekir. Klasik senaryo şudur: Bir kullanıcı web sunucusuna (örneğin bir intranet uygulaması) bağlanır. Web uygulaması, kullanıcı adına arka plandaki bir SQL veritabanına erişmek ister. Web sunucusu SQL'e kendi servis hesabıyla değil, **kullanıcının kimliğiyle** erişmelidir ki veritabanı tarafındaki yetkilendirme (authorization) doğru kişiye göre yapılabilsin. Buna "double hop" (çift sıçrama) problemi denir: kimliğin bir sunucudan diğerine taşınması gerekir.

Kerberos'ta kimlik, **ticket** (bilet) ile temsil edilir. Kullanıcı, Key Distribution Center (KDC) üzerinden önce bir **Ticket Granting Ticket (TGT)** alır, sonra bu TGT ile belirli servisler için **service ticket** (TGS) alır. Delegation'ın özü, bir servisin kullanıcının kimliğini temsil eden bir bileti alıp, bunu başka bir servise karşı yeniden kullanabilmesidir. Kök nedene inersek: **kimliğin taşınabilir bir kanıtı (ticket), o kanıta sahip olan tarafça yeniden sunulabildiği sürece, o tarafın güven sınırı kadar güçlüdür.** Bu tek cümle, aşağıdaki tüm saldırıların temelini oluşturur.

## Unconstrained Delegation (Kısıtlanmamış Yetki Devri)

### Tanım ve Çalışma Mantığı

Unconstrained delegation, delegation'ın en eski ve en tehlikeli biçimidir. Bir bilgisayar veya servis hesabı unconstrained delegation için işaretlendiğinde (account nesnesindeki `TRUSTED_FOR_DELEGATION` User Account Control bayrağı), o makineye kimliğiyle bağlanan her kullanıcı, KDC tarafından kendi **TGT'sinin bir kopyasını** o makineye gönderir. Daha teknik olarak: kullanıcı hedef servise ait bir service ticket talep ettiğinde, KDC bu bilete kullanıcının **forwardable TGT'sini** gömer. Hedef makine bu TGT'yi bellekte (LSASS) saklar ve gerektiğinde kullanıcı adına başka herhangi bir servise erişmek için kullanabilir.

Kritik nokta şudur: buradaki devir **kısıtlanmamıştır**. Yani makine, o kullanıcının TGT'siyle domain içindeki *herhangi bir* servise, herhangi bir sınır olmadan erişebilir. Bir kullanıcının TGT'sine sahip olmak, pratikte o kullanıcı olmak demektir.

### Kök Neden

Bu tehlikenin kök nedeni tasarımsal bir güven varsayımıdır: unconstrained delegation, "bu makineye güveniyorum, dolayısıyla ona bağlanan herkesin tam kimliğini ona emanet edebilirim" der. Sorun, güvenin **makinenin bütünlüğüne** dayanmasıdır. Eğer saldırgan o makinede local admin olursa (ya da makine zaten güvenilmezse), o makineden geçen tüm kullanıcıların TGT'lerini hasat edebilir. TGT'ler bellekte tutulduğu için, LSASS belleğini okuyabilen biri (örneğin Mimikatz benzeri araçlarla) bu biletleri dışarı çıkarabilir.

### İstismar Zinciri

Klasik istismar iki aşamalıdır. Birincisi **pasif hasat**: saldırgan unconstrained delegation'a sahip bir makinede yetki elde eder ve bekler; ayrıcalıklı bir kullanıcı (örneğin bir domain admin) o makineye bağlandığında TGT'si bellekte belirir ve çalınır. Bu pasiftir çünkü kurbanın bağlanmasını beklemek gerekir.

İkincisi ve çok daha güçlüsü **aktif zorlama**dır. Saldırgan, bir Domain Controller'ı (DC) unconstrained delegation makinesine kimlik doğrulamaya *zorlar*. Bunun için MS-RPRN (Print Spooler) üzerinden "printer bug" olarak bilinen teknik ya da benzeri **authentication coercion** (kimlik doğrulama zorlama) yöntemleri kullanılır; bu ailedeki teknikler genellikle PetitPotam, PrinterBug gibi isimlerle anılır. Zorlama sonucunda DC'nin bilgisayar hesabı (`DC$`), unconstrained makineye kimlik doğrular ve TGT'sini oraya yollar. DC'nin makine hesabının TGT'si ele geçirildiğinde, saldırgan bununla bir **DCSync** saldırısı yaparak tüm domain'in parola hash'lerini (krbtgt dahil) çekebilir. Bu noktada domain tamamen ele geçmiştir.

Bu zincirin neden bu kadar yıkıcı olduğunu vurgulamak gerekir: unconstrained delegation'a sahip *tek bir* düşük öncelikli sunucu bile, coercion ile birleştiğinde tüm domain'in düşmesine yol açabilir. Saldırının başlangıç noktasının önemsiz görünmesi, savunmacıların bu riski hafife almasına neden olur.

### Savunma

Savunmanın birinci kuralı: **unconstrained delegation'dan kaçının.** Modern ortamlarda constrained delegation ya da RBCD neredeyse her zaman yeterlidir. Mevcut unconstrained yapılandırmalarını envanterleyin (`userAccountControl` içinde ilgili bayrağı taşıyan nesneleri LDAP ile sorgulayarak) ve gerekçesiz olanları kaldırın.

İkinci savunma, ayrıcalıklı hesapları korumaktır. Kritik hesapları **"Account is sensitive and cannot be delegated"** olarak işaretlemek (nesne üzerindeki ilgili UAC bayrağı) ya da onları **Protected Users** grubuna eklemek, bu hesapların TGT'lerinin delegation için forwardable olmasını engeller. Böylece bir domain admin unconstrained bir makineye bağlansa bile TGT'si oraya taşınmaz.

Üçüncüsü, coercion vektörlerini kapatmaktır: Print Spooler servisini gerekmeyen sunucularda (özellikle DC'lerde) devre dışı bırakmak, coercion tekniklerine karşı SMB signing ve ilgili sertlestirmeleri uygulamak. Son olarak, DC'lerin ve Tier 0 varlıklarının delegation makinelerine kimlik doğrulamasını mimari olarak sınırlayın.

## Constrained Delegation (Kısıtlanmış Yetki Devri)

### Tanım ve Çalışma Mantığı

Constrained delegation, unconstrained'in tehlikesini sınırlamak için tasarlanmıştır. Fikir şudur: bir servisin kullanıcı adına delegation yapmasına izin verilir, ama **yalnızca önceden belirlenmiş belirli hedef servislere** karşı. Bu izin, kaynak nesne (delegation yapan hesap) üzerindeki `msDS-AllowedToDelegateTo` özniteliğinde, hedef servislerin **Service Principal Name (SPN)** listesi olarak tutulur.

Constrained delegation iki Kerberos genişletmesine dayanır: **S4U2Self** ve **S4U2Proxy** (Service-for-User protokol ailesi). Çalışma mantığı şöyledir:

- **S4U2Self**: Servis, bir kullanıcının kendisine Kerberos ile bağlanmasa bile (örneğin kullanıcı web'e NTLM ile geldiyse), o kullanıcı adına *kendisine* yönelik bir service ticket üretebilir. Yani "bu kullanıcı benim" diyen bir bilet elde eder. Bu bilet önemlidir çünkü bir sonraki adımda kullanılacaktır.
- **S4U2Proxy**: Servis, S4U2Self ile elde ettiği (kullanıcıyı temsil eden) bileti KDC'ye sunar ve "bu kullanıcı adına şu hedef servise bir bilet ver" der. KDC, kaynak hesabın `msDS-AllowedToDelegateTo` listesinde o hedef SPN varsa isteği onaylar.

### Kök Neden ve İnce Ayrıntı

Constrained delegation'ın güvenliği, "sadece izin verilen SPN'lere gidebilir" varsayımına dayanır. Ancak burada kritik ve sık gözden kaçan bir ince ayrıntı vardır: **KDC, delegation sırasında hedef servisi SPN'in tamamıyla değil, esas olarak hedef hesapla ilişkilendirir; ve dönen service ticket'ın içindeki hizmet sınıfı (service class) kısmı saldırgan tarafından değiştirilebilir.** Yani `msDS-AllowedToDelegateTo` listesinde bir hedef için `CIFS/server` yazıyorsa, saldırgan aynı hedef hesaba karşı `HTTP/server`, `HOST/server`, hatta `LDAP/server` gibi başka servis sınıflarına da bilet elde edebilir. Çünkü Kerberos, service ticket'ın hizmet sınıfı alanını bütünlük açısından aynı sıkılıkta korumaz. Sonuç: "constrained" göründüğü kadar kısıtlı değildir; izin verilen *hedef host* üzerindeki neredeyse tüm servislere erişim anlamına gelebilir.

Daha da tehlikelisi, **"protocol transition"** (protokol geçişi) ile yapılandırılmış constrained delegation'dır. Buradaki fark, kaynak hesabın "Use any authentication protocol" seçeneğiyle işaretlenmiş olması (`TRUSTED_TO_AUTH_FOR_DELEGATION` bayrağı) durumudur. Bu durumda S4U2Self, kullanıcı hiç kimlik doğrulamamış olsa bile *herhangi bir* kullanıcı adına bilet üretebilir. Yani saldırgan, kaynak hesabın kimlik bilgilerini (parola hash'i veya AES anahtarı) ele geçirdiyse, hiçbir kullanıcının etkileşimine ihtiyaç duymadan, `Administrator` dahil **istediği kullanıcıyı taklit edebilir** ve izin verilen hedeflere onun kimliğiyle erişebilir.

### İstismar Zinciri

Tipik zincir şudur: Saldırgan, constrained delegation (protocol transition ile) yapılandırılmış bir servis hesabının kimlik bilgilerini ele geçirir (parola hash'i ya da AES key). Bu hesabın `msDS-AllowedToDelegateTo` listesinde, örneğin bir dosya sunucusuna ait `CIFS/fileserver` SPN'i olduğunu görür. S4U2Self + S4U2Proxy zincirini çalıştırarak, `Administrator` kullanıcısı adına o dosya sunucusuna karşı bir CIFS bileti üretir. Hizmet sınıfı manipülasyonuyla aynı hedef üzerinde `HOST` veya `HTTP` gibi başka servislere de bilet elde ederek, hedef makine üzerinde geniş erişim (örneğin uzaktan komut yürütme) sağlar. Elde edilen biletler doğrudan bellekte kullanılır (pass-the-ticket).

Buradaki zincirin can alıcı halkası şu içgörüdür: constrained delegation'lı bir hesabın parolasını çalmak, o hesabın delegation yetkisi kadar değerlidir. Yani saldırgan için hedef, "yönetici parolası" değil, "delegation yetkisi olan herhangi bir servis hesabının parolası"dır. Bu, saldırı yüzeyini beklenenden çok daha geniş hale getirir.

### Savunma

Öncelikle, protocol transition'ı gerçekten gerekmedikçe kullanmayın; "Kerberos only" (yalnızca S4U2Proxy, protokol geçişi olmadan) seçeneği çok daha güvenlidir çünkü keyfi kullanıcı taklidine izin vermez. İkincisi, delegation hedeflerini mümkün olan en dar SPN kümesiyle sınırlayın ve hangi hedef host'lara delegasyon verildiğini bilinçli seçin (unutmayın: bir host'a delegation, o host'un neredeyse tüm servislerine delegation demektir). Üçüncüsü, delegation yetkisine sahip servis hesaplarını yüksek değerli varlık olarak sınıflandırın: güçlü, uzun ve düzenli döndürülen parolalar kullanın; mümkünse **group Managed Service Accounts (gMSA)** ile yönetin, böylece parola otomatik ve güçlü şekilde yönetilir. Son olarak, kritik hesapları yine "sensitive / cannot be delegated" işaretleyerek ya da Protected Users'a ekleyerek bu hesapların taklidini KDC seviyesinde reddettirin.

## Resource-Based Constrained Delegation (RBCD)

### Tanım ve Çalışma Mantığı

RBCD, delegation'ın yönünü tersine çevirir ve bu ters çevirme onu hem daha esnek hem de saldırı açısından daha ilginç kılar. Klasik constrained delegation'da izin, **delegation yapan (kaynak) hesap** üzerinde tutulur ve genelde bu yapılandırmayı yapmak için yüksek yetki (SeEnableDelegationPrivilege, tipik olarak domain admin) gerekir. RBCD'de ise izin, **delegasyona hedef olan (kaynak/resource) hesap** üzerinde tutulur: hedef nesnenin `msDS-AllowedToActOnBehalfOfOtherIdentity` özniteliği, "hangi hesapların benim adıma başkalarını taklit edebileceğini" tanımlar.

Bu tersine çevirmenin pratik sonucu şudur: bir kaynağa (örneğin bir bilgisayar hesabına) RBCD tanımlamak için, o kaynağın **kendisi üzerinde yazma yetkisine** sahip olmak yeterlidir; tüm domain üzerinde ayrıcalık gerekmez. Yani "bu makine nesnesinin özniteliklerini düzenleme yetkim var" diyen biri, o makineye kimin delegation yapabileceğini kendisi belirleyebilir.

### Kök Neden

RBCD'nin istismar edilebilirliğinin kök nedeni, iki tasarım gerçeğinin birleşmesidir. Birincisi: delegation iznini vermek için gereken yetki, artık **hedef nesne üzerindeki yazma hakkına** indirgenmiştir (örneğin `GenericWrite`, `GenericAll`, `WriteProperty` gibi ACL hakları). İkincisi: saldırgan, delegation yapacak "kaynak" tarafı da kontrol etmelidir; ve bunun için genellikle **kendi kontrolünde bir computer hesabı** oluşturur. Varsayılan olarak birçok domain'de sıradan kullanıcılar `ms-DS-MachineAccountQuota` sayesinde domain'e yeni bilgisayar hesapları ekleyebilir (klasik varsayılan 10'dur). Saldırgan kendi oluşturduğu computer hesabının parolasını bildiği için, o hesap adına S4U2Self/S4U2Proxy zincirini çalıştırabilir.

Yani RBCD istismarı özünde şu iki parçayı birleştirir: (1) hedef makine nesnesi üzerinde bir yazma hakkı, (2) parolasını bildiğiniz, delegation yapabilen bir "kaynak" hesap. Bu iki parça bir araya geldiğinde, saldırgan hedef makine üzerinde istediği kullanıcıyı (örneğin `Administrator`) taklit edebilir.

### İstismar Zinciri

Klasik RBCD zinciri şu adımları izler:

1. **Kaynak hesabı hazırla.** Saldırgan, machine account quota'yı kullanarak yeni bir computer hesabı oluşturur (örneğin `EVIL$`) ve parolasını/anahtarını bilir. Alternatif olarak, parolasını zaten bildiği herhangi bir SPN'e sahip hesabı kullanabilir.
2. **Hedef üzerinde yazma hakkı bul.** Saldırgan, ele geçirmek istediği bir makine hesabı (örneğin `TARGET$`) üzerinde `GenericWrite`/`GenericAll` gibi bir ACL hakkına sahip olmalıdır. Bu hak, çoğu zaman başka bir yanlış yapılandırmadan (delegasyonu zincirlemeye olanak veren ACL misconfig'leri) türetilir.
3. **RBCD'yi yaz.** Saldırgan, `TARGET$` nesnesinin `msDS-AllowedToActOnBehalfOfOtherIdentity` özniteliğine, kendi `EVIL$` hesabının SID'ini içeren bir security descriptor yazar. Artık `EVIL$`, `TARGET$` adına başkalarını taklit edebilir.
4. **S4U zincirini çalıştır.** `EVIL$` hesabının kimlik bilgileriyle S4U2Self ve S4U2Proxy'yi kullanarak, `Administrator` (ya da `TARGET$` üzerinde local admin olan herhangi bir kullanıcı) adına `TARGET$`'a yönelik bir service ticket üretilir.
5. **Erişimi kullan.** Elde edilen biletle `TARGET$` makinesine örneğin CIFS/HOST üzerinden bağlanılarak uzaktan komut yürütme veya dosya erişimi sağlanır (pass-the-ticket).

Bu zincirin öğretici yanı, çok küçük bir yanlış yapılandırmanın (tek bir makine nesnesi üzerinde yazma hakkı) tam makine ele geçirmesine dönüşmesidir. RBCD, ACL tabanlı saldırı zincirlerinin (ör. BloodHound ile keşfedilen yolların) en sık kullanılan son halkalarından biridir çünkü "X nesnesi üzerinde yazma hakkım var"ı doğrudan "X makinesinde kod çalıştırıyorum"a çevirir.

### Savunma

RBCD savunmasının kök noktası **ACL hijyenidir**: makine ve kullanıcı nesneleri üzerindeki yazma haklarını düzenli olarak denetleyin. Özellikle geniş grupların (Authenticated Users, Everyone benzeri) ya da beklenmedik hesapların bilgisayar nesneleri üzerinde `GenericWrite`/`GenericAll`/`WriteDACL` gibi haklara sahip olmadığından emin olun. Bu haklar RBCD zincirinin girişidir.

İkinci önemli sertlestirme: `ms-DS-MachineAccountQuota` değerini **0'a çekmek** (ya da bu yetkiyi yalnızca belirli, denetlenen bir gruba vermek). Sıradan kullanıcıların domain'e keyfi computer hesapları eklemesini engellemek, saldırganın "kontrol ettiği kaynak hesabı" oluşturmasını çok zorlaştırır. Bu tek değişiklik, birçok RBCD zincirini kırar.

Üçüncüsü, kritik hesapları (Tier 0, domain admin'ler) yine Protected Users grubuna eklemek ve/veya "cannot be delegated" işaretlemek; böylece bir saldırgan RBCD kursa bile bu hesapları taklit edemez. Dördüncüsü, `msDS-AllowedToActOnBehalfOfOtherIdentity` özniteliğindeki değişiklikleri **izleyin ve alarm kurun**: bu öznitelik meşru senaryolarda nadiren ve kontrollü değişir; beklenmedik bir yazma güçlü bir tehdit sinyalidir.

## Ortak Tespit ve İzleme Yaklaşımları

Delegation saldırılarının çoğu, KDC etkileşimlerinde iz bırakır. S4U2Self ve S4U2Proxy kullanımı, Kerberos servis bileti taleplerinde (event log'larda TGS istekleri) belirir; özellikle bir hesabın kısa sürede birçok farklı kullanıcı adına bilet talep etmesi anormaldir. Delegation'a ilişkin öznitelik değişiklikleri (`msDS-AllowedToDelegateTo`, `msDS-AllowedToActOnBehalfOfOtherIdentity`, ilgili UAC bayrakları) directory değişiklik denetimiyle (directory service changes auditing) yakalanabilir ve bunlar üzerine alarm kurulmalıdır.

Coercion tabanlı unconstrained saldırılarında, DC'lerin beklenmedik sunuculara giden kimlik doğrulama trafiği ve TGT forwarding, ağ ve kimlik telemetrisinde tespit edilebilir. Ayrıca, ayrıcalıklı hesapların delegation'a açık makinelere oturum açması başlı başına araştırılması gereken bir durumdur.

Envanter tarafında, düzenli olarak şu üç sınıfı çıkarın ve gözden geçirin: (1) unconstrained delegation'a sahip tüm hesaplar, (2) `msDS-AllowedToDelegateTo` dolu olan tüm hesaplar ve hedefleri, (3) `msDS-AllowedToActOnBehalfOfOtherIdentity` tanımlı tüm nesneler. Bu üç liste, delegation saldırı yüzeyinizin tamamını verir. BloodHound gibi araçlar bu ilişkileri ve bunlara giden ACL yollarını görselleştirmede oldukça etkilidir; savunmacılar da saldırganlar gibi bu haritayı çıkarıp en kısa saldırı yollarını proaktif kapatmalıdır.

## Yaygın Hatalar

**"Constrained yeterince güvenli" yanılgısı.** En sık hata, constrained delegation'ın adındaki "constrained" kelimesine güvenip onu tam bir sınır sanmaktır. Oysa hizmet sınıfı manipülasyonu nedeniyle, bir host'a verilen delegation pratikte o host'un çoğu servisine erişim demektir; protocol transition açıksa keyfi kullanıcı taklidi de mümkündür.

**Machine account quota'yı unutmak.** Varsayılan quota'nın sıfırlanmaması, RBCD ve benzeri saldırıların en kolay girdisidir. Birçok ortam bu ayarı hiç değiştirmez ve saldırgana bedava bir "kontrol edilen hesap" kaynağı sunar.

**Ayrıcalıklı hesapları delegation'a karşı korumamak.** "Cannot be delegated" bayrağını ve Protected Users grubunu kullanmamak, domain admin'lerin biletlerinin delegation'la taşınmasına ve taklit edilmesine kapı açar. Bu koruma çoğu zaman ihmal edilir.

**Print Spooler ve coercion vektörlerini açık bırakmak.** DC'lerde gereksiz servisleri (özellikle Spooler) kapatmamak, unconstrained + coercion zincirini domain ele geçirmesine dönüştürür.

**ACL'leri denetlememek.** Makine nesneleri üzerindeki geniş yazma haklarını görmezden gelmek, RBCD zincirinin fark edilmeden kurulmasına izin verir. Delegation risklerini yalnızca "delegation ayarları"nda aramak, asıl girdinin ACL'ler olduğunu gözden kaçırır.

**Legacy delegation'ı temizlememek.** Zamanla oluşmuş, artık gerekçesi kalmamış unconstrained/constrained yapılandırmaları envanterden çıkarılmaz ve sonsuza kadar risk taşımaya devam eder.

## En İyi Pratikler (Özet)

- Unconstrained delegation'ı ortamdan kaldırmayı hedefleyin; kaçınılmazsa Tier 0 varlıklarını sıkıca izole edin.
- Constrained delegation kullanırken protocol transition'dan kaçının ("Kerberos only" tercih edin) ve hedef SPN kümesini olabildiğince daraltın.
- RBCD için ACL hijyenini birinci öncelik yapın; makine nesneleri üzerindeki geniş yazma haklarını temizleyin.
- `ms-DS-MachineAccountQuota` değerini 0'a çekin veya kontrollü bir gruba devredin.
- Tüm ayrıcalıklı ve Tier 0 hesaplarını Protected Users'a ekleyin ve/veya "sensitive, cannot be delegated" işaretleyin.
- Delegation yetkisine sahip servis hesaplarını gMSA ile yönetin, güçlü ve döndürülen parolalar kullanın.
- Coercion vektörlerini (Print Spooler vb.) DC ve kritik sunucularda kapatın; SMB signing ve ilgili sertlestirmeleri uygulayın.
- Delegation ilişkilerini ve ACL yollarını düzenli olarak (örneğin BloodHound benzeri araçlarla) haritalayın ve en kısa saldırı yollarını proaktif kapatın.
- Delegation'a ilişkin öznitelik değişikliklerini ve anormal S4U bilet taleplerini denetleyip alarm kurun.

## Kapanış

Delegation saldırılarının tümünü birbirine bağlayan tek bir ilke vardır: **taşınabilir bir kimlik kanıtı, onu yeniden sunabilen tarafın gücü kadar güçlüdür.** Unconstrained delegation bu ilkeyi en gevşek, RBCD ise en esnek biçimde uygular; ama üçünde de saldırganın peşinde olduğu şey aynıdır: bir kimliği, ait olmadığı bir yerde yeniden kullanmak. Savunma da bu yüzden tek bir ayara değil, katmanlı bir yaklaşıma dayanır: gereksiz delegation'ı kaldırmak, ayrıcalıklı kimlikleri delegation'a karşı korumak, ACL ve quota hijyenini sağlamak, coercion vektörlerini kapatmak ve delegation değişikliklerini sürekli izlemek. Bu katmanlar birlikte uygulandığında, delegation güçlü ve meşru bir özellik olarak kalır; tek başına bırakıldığında ise domain'in en kısa düşüş yoluna dönüşür.
