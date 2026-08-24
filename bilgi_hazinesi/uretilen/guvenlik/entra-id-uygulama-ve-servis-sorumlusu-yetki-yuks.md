# Entra ID Uygulama ve Servis Sorumlusu (Service Principal / Managed Identity) Yetki Yükseltme Zincirleri

## Giriş: Neden Bu Konu Kritik

Klasik Active Directory dünyasında yetki yükseltme genellikle kullanıcı hesapları, gruplar ve ACL'ler (DACL/ACE yapıları) üzerinden işlerdi — `GenericAll`, `WriteDacl`, `ForceChangePassword` gibi zincirler BloodHound ile haritalanırdı. Bulut kimliğine (Entra ID, eski adıyla Azure AD) geçişte saldırı yüzeyi kaybolmadı, biçim değiştirdi: artık merkezde **kullanıcılar değil, uygulamalar** var. Her uygulama kaydı (App Registration) bir **Service Principal** ile temsil edilir; her Azure kaynağına (VM, Function App, Logic App, Automation Account) bağlanabilen **Managed Identity** de aslında özel bir Service Principal türüdür. Bu kimlikler, insan kullanıcılardan farklı olarak MFA'ya tabi değildir, genellikle şifre yerine sertifika/anahtar veya platform tarafından yönetilen token kullanır ve çoğu zaman kimse onların gerçekte ne yapabildiğini denetlemez.

Bu makalenin odak noktası şu: bir saldırganın (veya içeriden bir tehdidin) düşük yetkili bir noktadan başlayıp, **Microsoft Graph API izinleri** ve **Azure RBAC rol atamaları** arasındaki etkileşimi kötüye kullanarak nasıl Global Administrator seviyesine veya Azure abonelik sahipliğine kadar tırmanabildiğidir. Bu, "AD sonrası" kimlik saldırı yüzeyinin tam merkezinde duruyor çünkü modern ortamların neredeyse tamamı CI/CD boru hatlarında, otomasyon script'lerinde ve bulut-yerel uygulamalarda Service Principal/Managed Identity kullanıyor ve bunlara verilen izinler çoğu zaman "çalışsın da nasıl olursa olsun" mantığıyla aşırı geniş tutuluyor.

## Temel Kavramlar: Kim Kimdir

İlerlemeden önce terminolojiyi netleştirmek şart, çünkü bu alan kavram kargaşasından besleniyor.

- **App Registration (Uygulama Kaydı)**: Bir uygulamanın Entra ID'deki "şablonu" — Application ID, izin talepleri (API permissions), yönlendirme URI'leri gibi metadata'yı taşır. Tek başına hiçbir işlem yapamaz.
- **Service Principal**: Bir App Registration'ın belirli bir tenant'taki "somut örneği" — asıl yetkilendirme ve erişim buradan geçer. Bir uygulama birden fazla tenant'ta kullanılıyorsa (multi-tenant app), her tenant'ta ayrı bir Service Principal oluşur.
- **Managed Identity**: Azure'un kimlik bilgisi yönetimini (anahtar rotasyonu, saklama) sizin yerinize üstlendiği özel bir Service Principal türü. İki alt türü var:
  - **System-assigned**: Belirli bir Azure kaynağına (örneğin bir VM) bağlıdır, kaynakla birlikte doğar ve ölür.
  - **User-assigned**: Bağımsız bir kaynak olarak oluşturulur, birden fazla Azure kaynağına atanabilir — bu da onu daha "taşınabilir" ve dolayısıyla zincirleme saldırılarda daha ilginç kılar.
- **Microsoft Graph API İzinleri**: Bir Service Principal'ın Entra ID/Microsoft 365 nesneleri (kullanıcılar, gruplar, uygulamalar, rol atamaları) üzerinde ne yapabileceğini tanımlayan izinler. İki tür vardır: **delegated** (bir kullanıcı adına, o kullanıcının yetkisiyle sınırlı) ve **application** (kullanıcısız, uygulamanın kendi başına sahip olduğu geniş yetki — asıl tehlike burada).
- **Azure RBAC**: Azure kaynakları (abonelikler, kaynak grupları, sanal makineler, key vault'lar) üzerindeki yetkilendirme katmanı. Entra ID'den ayrı bir yetki düzlemidir ama ikisi arasında kritik köprüler vardır.

Bu iki dünya — Graph API (kimlik yönetim düzlemi) ve Azure RBAC (kaynak yönetim düzlemi) — birbirinden bağımsız görünse de, aralarında saldırganın tam olarak aradığı türden köprüler mevcuttur. Bu makalenin kalbi bu köprülerdir.

## Kök Neden: Ayrıcalık Modelinin Yapısal Zafiyetleri

Bu saldırı sınıfının var olmasının birkaç temel nedeni var, birbirinden bağımsız ama birbirini güçlendiren:

**1. En az yetki ilkesinin pratikte uygulanmaması.** Geliştiriciler ve platform ekipleri, bir uygulamanın tam olarak neye ihtiyacı olduğunu analiz etmek yerine, "işe yarasın" diye en geniş izni verme eğilimindedir. `User.Read.All` yeterliyken `Directory.ReadWrite.All` verilir; bir otomasyon betiği sadece bir grup üyeliğini okumak isterken `RoleManagement.ReadWrite.Directory` verilir.

**2. Application-level izinlerin doğası gereği "kullanıcısız ve sınırsız" olması.** Delegated izinlerde işlem, oturum açmış bir kullanıcının yetkisiyle sınırlandırılır (kullanıcı Global Admin değilse, uygulama da o kullanıcı adına Global Admin işlemi yapamaz). Application izinlerinde ise bu sınırlama yoktur — izin verildiği anda Service Principal, tenant genelinde o izin neyi kapsıyorsa onu yapabilir, arkasında hiçbir insan kullanıcı olmadan.

**3. Kimlik bilgisi (credential) yönetiminin dağınıklığı.** App Registration'lara eklenen client secret'lar veya sertifikalar (`addPassword`/`addKey` işlemleriyle) genellikle uzun ömürlü, rotasyonsuz ve kod deposu/CI pipeline/Key Vault gibi farklı yerlerde saklanır. Bir Service Principal'ın "sahibi" (owner) olan herhangi bir kullanıcı, o Service Principal'a yeni bir credential ekleyerek onun kimliğine bürünebilir — bu, çoğu zaman fark edilmeyen bir yetki devridir.

**4. Azure RBAC ile Entra ID rollerinin farklı yönetim düzlemleri olmasına rağmen, bazı Entra ID rollerinin (özellikle `Application Administrator`, `Cloud Application Administrator`, `Hybrid Identity Administrator`, `Partner Tier2 Support`) Service Principal'lar üzerinde credential ekleme yetkisi vermesi — ve bunun üzerinden kaynak düzlemine sıçrama.** Bu, "AD sonrası" özgünlüğün asıl kaynağı: eski AD'de ayrı olan "kimlik yönetimi" ile "kaynak erişimi" bulutta iç içe geçmiş durumda.

**5. Managed Identity'lerin "görünmezlik" avantajı.** Bir Managed Identity'nin şifresi yoktur, token'ı otomatik yenilenir, IMDS (Instance Metadata Service) üzerinden istenildiğinde alınır. Bu, operasyonel kolaylık sağlarken, "bu kimlik nerede kullanılabilir" sorusunu da bulanıklaştırır — özellikle user-assigned Managed Identity birden fazla kaynağa atanmışsa, bir kaynaktaki zafiyet diğerlerine sıçrama noktası olur.

## Yetki Yükseltme Zincirlerinin Anatomisi

### Zincir 1: Graph API İzni Üzerinden Rol Atama Manipülasyonu

En doğrudan ve en tehlikeli zincir, bir Service Principal'a `RoleManagement.ReadWrite.Directory` (application izni) verilmesiyle ortaya çıkar. Bu izin, sahibine Entra ID dizinindeki **herhangi bir** dizin rolünü **herhangi bir** asıl (principal — kullanıcı veya Service Principal) üzerine atama yetkisi verir.

**Çalışma mantığı (kavramsal):** Saldırgan, düşük yetkili ama bu application iznine sahip bir Service Principal'ın kimlik bilgisini ele geçirdiğinde (örneğin sızdırılmış bir client secret, açık kalmış bir CI/CD ortam değişkeni veya kaynak kodunda hard-code edilmiş bir sertifika üzerinden), Graph API'ye kimlik doğrulaması yaparak kendisine veya kontrol ettiği başka bir asıla `Global Administrator` rolünü atayabilir. Bu, tek bir API çağrısıyla tüm tenant'ın en üst kimlik düzlemine sıçramaktır — insan onayı, MFA veya ek doğrulama gerekmez, çünkü uygulama zaten bu işlemi yapmaya "yetkilidir".

Benzer şekilde tehlikeli izinler: `AppRoleAssignment.ReadWrite.All` (herhangi bir uygulamaya herhangi bir uygulama rolü atayabilme — bu da dolaylı olarak Graph üzerindeki başka güçlü izinleri "kendine atama" imkânı doğurur), `Directory.ReadWrite.All` (dizin nesnelerini geniş çapta değiştirebilme, dolaylı yetki zincirlerine kapı açar), ve `User.ReadWrite.All` + parola sıfırlama kombinasyonu (bir Global Admin'in parolasını değiştirip o kimliğe bürünme potansiyeli, koşullu erişim ve rol kısıtlamaları yeterince sıkı değilse).

### Zincir 2: Service Principal Owner Üzerinden Credential Enjeksiyonu

**Çalışma mantığı:** Entra ID'de bir kullanıcı veya grup, bir Service Principal'ın "owner"ı (sahibi) olabilir. Sahiplik, o Service Principal'ın Graph API izinlerinden bağımsız bir yetkidir — sahip olan kişi, ilgili Service Principal'a yeni bir client secret veya sertifika ekleyebilir (`addPassword` işlemi). Eğer o Service Principal zaten güçlü Graph izinlerine veya Azure RBAC rollerine sahipse, sahiplik ele geçirmek = o Service Principal'ın tüm yetkilerini devralmak demektir.

Bu zincir özellikle tehlikelidir çünkü sahiplik ilişkileri genellikle klasik "izin" denetimlerinin dışında kalır — güvenlik ekipleri Graph API izinlerini (App Permissions sekmesi) denetler ama "kim bu Service Principal'ın sahibi" sorusunu çoğu zaman sormaz. Owner rolü bir nevi gölge yetki katmanıdır.

**Zincirleme örneği (kavramsal, adım adım akıl yürütme):**
1. Saldırgan, düşük yetkili bir kullanıcı hesabını ele geçirir (phishing, parola spreyi vb.).
2. Bu kullanıcı, ayrıcalıklı bir Service Principal'ın owner'ı olarak atanmıştır (belki geçmişte bir geliştirici görevi devraldığında bu atama unutulmuş, temizlenmemiştir).
3. Saldırgan Graph API üzerinden bu Service Principal'a yeni bir client secret ekler.
4. Bu yeni secret ile Service Principal olarak kimlik doğrulaması yapar — artık o Service Principal'ın sahip olduğu tüm Graph izinlerine ve Azure RBAC rollerine sahiptir.
5. Eğer bu Service Principal'ın Azure üzerinde `Owner` veya `User Access Administrator` rolü varsa, saldırgan artık Azure kaynak düzleminde de rol atayabilir — döngü tamamlanmıştır.

### Zincir 3: Managed Identity Üzerinden Azure Kaynak Düzleminden Yatay/Dikey Sıçrama

Bu zincir, Entra ID'den değil **Azure kaynak düzleminden** başlar ve Azure RBAC rol atama mekanizmasını hedef alır.

**Kök neden:** Azure RBAC'te `Owner` ve `User Access Administrator` rolleri, sahibine **rol ataması yapma** (`Microsoft.Authorization/roleAssignments/write`) yetkisi verir. Bir Managed Identity'ye (örneğin bir Automation Account'a veya Function App'e bağlı system-assigned identity) bir kaynak grubu veya abonelik düzeyinde `Owner`/`Contributor`+`User Access Administrator` kombinasyonu verildiyse, ve saldırgan bu kaynağı çalıştıran kodu (Function App'in kodu, Automation Runbook'u, VM üzerindeki bir işlemi) ele geçirebiliyorsa — kod yürütme yetkisini kimlik yükseltme yetkisine çevirebilir.

**Çalışma mantığı (kavramsal):**
1. Saldırgan, bir Azure kaynağında (örneğin halka açık bir Function App, savunmasız bir web uygulaması veya kötü yapılandırılmış bir VM) uzaktan kod çalıştırma (RCE) veya komut enjeksiyonu elde eder.
2. Bu kaynağa bağlı bir Managed Identity varsa, saldırgan yerel IMDS uç noktasından (kaynağın kendi içinden, kimlik doğrulaması gerektirmeden erişilebilen bir yerel metadata servisi) bu kimliğe ait bir erişim token'ı talep edebilir.
3. Eğer bu Managed Identity'nin Azure RBAC üzerinde geniş bir rolü varsa (örneğin abonelik düzeyinde `Contributor`), saldırgan artık o abonelikteki diğer tüm kaynaklara token üzerinden erişebilir — yatay hareket.
4. Eğer rol `Owner` veya `User Access Administrator` ise, saldırgan kendine (veya kontrol ettiği başka bir asıla) doğrudan Azure üzerinde daha da geniş roller atayabilir, hatta bir Service Principal'a Entra ID tarafında da etkili olacak Graph API izinleri kazandıracak dolaylı yollar arayabilir — dikey tırmanış.

**User-assigned Managed Identity'nin özel riski:** Aynı user-assigned kimlik birden fazla kaynağa (örneğin 10 farklı Function App'e) atanmışsa, bu kaynaklardan **en zayıf** olanı ele geçirmek, o kimliğin sahip olduğu **tüm** yetkileri açığa çıkarır. Bu, "en zayıf halka" prensibinin bulut kimliğindeki doğrudan yansımasıdır — geniş yetkili bir kimliği paylaşan kaynak sayısı arttıkça saldırı yüzeyi de büyür.

### Zincir 4: Karma Zincir — Graph İzninden Azure RBAC'e (veya Tersi) Geçiş

En sofistike ve gerçek dünyada en çok göz ardı edilen zincir, iki düzlem arasındaki köprüleri kullanır:

- Bir Service Principal'ın **Azure RBAC** tarafında Key Vault üzerinde `Key Vault Secrets Officer` veya benzeri bir rolü varsa ve o Key Vault içinde başka bir ayrıcalıklı Service Principal'ın client secret'ı/sertifikası saklanıyorsa, bu ilk Service Principal'ı ele geçirmek, ikinci (daha ayrıcalıklı) Service Principal'a geçiş kapısı olur.
- Entra ID rollerinden `Application Administrator` veya `Cloud Application Administrator`, **tüm** Service Principal'lara (bazı korumalı roller hariç) credential ekleme yetkisi verir. Bu rolün kendisi "sadece uygulama yönetimi" gibi görünse de, hedef Service Principal'ın Azure RBAC üzerinde güçlü bir rolü varsa, bu Entra ID rolü dolaylı olarak Azure kaynak düzleminde de tam kontrol sağlar. Bu, Microsoft'un da resmî olarak "yüksek ayrıcalıklı roller" listesinde işaretlediği, iyi bilinen bir kalıptır (rol atarken bu tür dolaylı etkilerin göz önünde bulundurulması tavsiye edilir).

Bu zincirin kritik dersi şudur: **yetki değerlendirmesi tek bir düzlemde yapılamaz.** Bir kimliğin gerçek "blast radius"ını (etki yarıçapını) anlamak için hem Graph API izinlerine hem Azure RBAC rol atamalarına hem de sahiplik/credential ilişkilerine birlikte bakmak gerekir — tek başına hiçbiri tam resmi vermez.

## Tespit (Detection)

Savunma tarafında akıl yürütme şu soruya dayanır: *"Bu kimlik normalde yapmadığı bir şeyi mi yapıyor, yoksa yapabileceği ama yapmaması gereken bir şeyi mi yapıyor?"*

**Loglama ve izlenecek sinyaller:**
- **Entra ID Audit Logs**: `Add app role assignment to service principal`, `Add owner to application`, `Add service principal credentials` (yani `addPassword`/`addKey` çağrıları), `Add member to role` gibi olayların, özellikle mesai dışı saatlerde veya alışılmadık kaynak IP'lerden gerçekleştiği zaman uyarı üretilmesi.
- **Yüksek riskli izin kullanımı**: `RoleManagement.ReadWrite.Directory`, `AppRoleAssignment.ReadWrite.All`, `Directory.ReadWrite.All` gibi izinlere sahip Service Principal'ların **gerçekte** bu izinleri kullandığı anları (Graph API çağrı logları üzerinden — Microsoft Graph Activity Logs) ayrı bir izleme kuralına bağlamak. Bir Service Principal aylardır bu izne sahip ama hiç kullanmamışsa, aniden kullanmaya başlaması güçlü bir anomali sinyalidir.
- **Azure Activity Log**: `Microsoft.Authorization/roleAssignments/write` işlemlerinin, özellikle bir Managed Identity veya Service Principal tarafından gerçekleştirildiği durumlarda (kullanıcı değil, uygulama kimliği) izlenmesi — bu, otomasyonun normal işleyişinde nadiren beklenen bir davranıştır.
- **IMDS erişim anomalileri**: Bir kaynağın normalde talep etmediği bir kapsam (scope) için token istemesi veya token talep sıklığının aniden artması, o kaynakta bir RCE/kod yürütme sonrası kimlik hırsızlığı denemesi olabilir.
- **Envanter tabanlı tespit (proaktif)**: Düzenli olarak (idealde otomatik bir script/BloodHound benzeri araçla) şu soruları cevaplayan bir envanter çıkarmak: Hangi Service Principal'lar `RoleManagement.ReadWrite.Directory` veya benzeri "tier-0" izinlere sahip? Bu Service Principal'ların owner'ları kim? Hangi Managed Identity'ler Azure RBAC'te `Owner`/`User Access Administrator` rolüne sahip ve hangi kaynaklara bağlı? Bu envanterin periyodik farkını (diff) almak, sessizce eklenen yetkileri yakalar.

**Microsoft Entra ID Protection ve Privileged Identity Management (PIM)** gibi yerleşik araçlar, insan kullanıcılar için risk tabanlı sinyaller sunar, ancak Service Principal'lar için bu kapsamın tarihsel olarak daha sınırlı olduğunu ve **PIM for Groups / Workload Identity** gibi daha yeni yeteneklerin bu boşluğu kapatmaya çalıştığını not etmek gerekir — bu alan hızlı geliştiği için güncel dokümantasyon kontrol edilmelidir.

## Savunma (Prevention/Hardening)

Akıl yürütme zinciri şudur: *önce yetkiyi azalt, sonra izin ver, sonra izle, sonra da otomatik olarak süresi dolsun.*

**1. En az yetki — application izinlerinde özellikle katı olun.** Her Graph API application izni talebi, "bu uygulama gerçekten dizin genelinde mi yoksa tek bir kaynak/kapsam üzerinde mi çalışıyor" sorusuyla gözden geçirilmeli. Mümkün olduğunda `RoleManagement.ReadWrite.Directory` gibi geniş izinler yerine, hedeflenen amaç için daha dar kapsamlı alternatifler (örneğin belirli bir uygulamaya sınırlı roller, ya da Graph'ın kısıtlı/koşullu izin modelleri) araştırılmalı.

**2. Yönetici onay akışını (admin consent workflow) zorunlu kılın.** Application izinleri için kullanıcıların kendi kendine onay (self-service consent) vermesini kapatın; tüm yüksek riskli izin talepleri merkezi bir güvenlik/IAM ekibinin onayından geçsin.

**3. Service Principal sahipliğini (ownership) periyodik denetleyin.** Sahiplik atamalarının "neden var" olduğu belgelenmeli; kullanılmayan veya gerekçesi belirsiz sahiplikler kaldırılmalı. Sahiplik, credential ekleme yetkisi verdiği için pratikte bir yetkilendirme mekanizması gibi davranılmalı.

**4. Managed Identity'lere Azure RBAC rolü verirken kapsamı (scope) daraltın.** Abonelik düzeyinde `Owner` yerine, mümkün olan en dar kaynak grubu/kaynak düzeyinde, gereken en az rolü (custom role tanımlarıyla, sadece ihtiyaç duyulan eylemleri içerecek şekilde) atayın. `User Access Administrator` rolünü Managed Identity'lere vermekten mümkün olduğunca kaçının — bu rol doğrudan yetki yükseltme aracıdır.

**5. Credential/secret yaşam döngüsünü yönetin.** Client secret'lar için kısa ömür (rotasyon zorunluluğu) belirleyin; mümkün olduğunca sertifika tabanlı veya federe kimlik doğrulama (workload identity federation — OIDC tabanlı, secret'sız CI/CD entegrasyonu) tercih edin. Sızdırılmış secret'ların etkisini süre sınırlayarak azaltın.

**6. Düzenli erişim gözden geçirmesi (access review) ve "tier-0 varlık" haritası çıkarın.** Hangi Service Principal'ların/Managed Identity'lerin fiilen "tier-0" (yani ele geçirilirse tüm tenant'ı etkileyebilecek) olduğunu belirleyip bu listeyi ayrı, sıkı izlenen bir varlık grubu olarak yönetin — tıpkı klasik AD'de Domain Admin hesaplarına yaklaşıldığı gibi.

**7. Koşullu erişim politikalarını iş yükü kimliklerine (workload identities) de genişletin.** Microsoft'un daha yeni sunduğu iş yükü kimlikleri için koşullu erişim (belirli konumlardan/ağlardan gelen istekleri kısıtlama gibi) özellikleri, Service Principal token hırsızlığının etkisini azaltabilir.

## Yaygın Hatalar

- **"Uygulama izinleri de delegated izinler gibi sınırlıdır" varsayımı.** Gerçekte application izinleri arkasında bir kullanıcı olmadan, tüm dizin/kaynak kapsamında çalışır — bu ayrımı anlamamak, en sık rastlanan kavramsal hatadır.
- **Sadece Graph API izinlerine bakıp Azure RBAC'i ihmal etmek (veya tam tersi).** İki düzlem birbirinden bağımsız yönetildiği için güvenlik ekipleri genellikle sadece birini denetler; asıl risk ikisinin kesişiminde saklıdır.
- **Service Principal sahipliğini "önemsiz bir detay" sanmak.** Sahiplik, izinlerden bağımsız ama en az onlar kadar güçlü bir yetki devridir; genellikle güvenlik gözden geçirmelerinde atlanır.
- **Wildcard/aşırı geniş custom rol tanımları.** Azure'da `*` eylemlerini içeren custom roller, "sadece belirli bir işlem için" oluşturulsa bile zamanla kapsam sürünmesi (scope creep) yaşar.
- **Test/geliştirme ortamlarında verilen geniş yetkilerin prodüksiyona taşınması.** "Şimdilik çalışsın, sonra kısarız" mantığıyla verilen izinler neredeyse hiç kısılmaz.
- **Managed Identity'nin "şifresi olmadığı için güvenli" sanılması.** Şifre olmaması kimlik bilgisi hırsızlığı riskini azaltır ama kod yürütme yoluyla token çalınmasını (yerel IMDS üzerinden) engellemez; bu farklı bir tehdit modelidir ve ayrı ele alınmalıdır.

## Sonuç

Entra ID'de Service Principal ve Managed Identity etrafında şekillenen yetki yükseltme zincirleri, klasik AD'deki ACL kötüye kullanımının doğrudan kavramsal mirasçısıdır — ama saldırı yüzeyi artık insan kimliklerinden makine kimliklerine kaymıştır. Kök neden hep aynı yerde toplanır: **aşırı geniş yetki verme + iki ayrı yetkilendirme düzleminin (Graph API ve Azure RBAC) birlikte değil ayrı ayrı denetlenmesi + credential/sahiplik ilişkilerinin gözden kaçması.** Savunma tarafında başarı, tek bir araç veya kuraldan değil, sürekli envanter çıkarma, en az yetki disiplini ve iki düzlemi birlikte değerlendiren bir görünürlük kültüründen gelir. Bu alan hâlâ hızla evrildiği için (Microsoft'un workload identity özellikleri, PIM genişlemeleri gibi), güncel resmî dokümantasyonun ve tehdit istihbaratının düzenli takip edilmesi şarttır.
