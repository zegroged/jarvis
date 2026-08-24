# Bulut IAM Yetki Yükseltme Zincirleri: Azure ve GCP'de "Bulut BloodHound" Metodolojisi

## Giriş: Neden Bu Konu Ayrı Bir Başlık Hak Ediyor

On-premise Active Directory dünyasında son on yılın en etkili savunma kırılımı BloodHound oldu: ACL/ACE ilişkilerini (`GenericAll`, `WriteDacl`, `ForceChangePassword` vb.) bir graf olarak modelleyip "A kullanıcısından Domain Admin'e giden en kısa yol nedir" sorusunu görsel ve sistematik hale getirdi. Bu, savunmacıların "hangi tekil izin tehlikeli" sorusundan "hangi izin **kombinasyonları** ve **zincirleri** tehlikeli" sorusuna geçmesini sağladı — çünkü gerçek risk neredeyse hiçbir zaman tek bir aşırı yetkide değil, birbirini besleyen birkaç "zararsız görünen" yetkinin toplamındadır.

Bulut IAM (Identity and Access Management) dünyasında aynı yapısal gerçek geçerli, ama araç ve kültür ekseni geride kaldı. Azure RBAC ve GCP IAM, on-prem AD'den çok daha fazla sayıda ince taneli rol, çok daha fazla kaynak türü ve çok daha hızlı değişen bir yapılandırma yüzeyi sunuyor — ama bunları bir graf olarak görüp "en kısa yükseltme yolu" sorusunu soran araç ekosistemi (ROADtool, PurpleCloud/Stormspotter, GCP tarafında çeşitli açık kaynak IAM-graph projeleri gibi) hâlâ AD tarafındaki olgunluğun gerisinde. Sonuç: kuruluşlar genellikle tek tek rol atamalarını "makul" bulur ama bu atamaların birleşiminin ne anlama geldiğini hiç haritalamaz. Bu makale, Azure RBAC ve GCP IAM'de yetki yükseltmenin **kök nedenini**, tipik zincir kalıplarını ve bunları bir savunmacı gözüyle nasıl tespit edip önleyeceğinizi ele alıyor. (Entra ID'ye özgü Graph API/Service Principal/Managed Identity zincirleri ve hibrit kimlik senaryoları ayrı makalelerde işlendiği için, burada odak **kaynak düzlemi RBAC/IAM mantığı** ve GCP'ye özgü impersonation zincirleridir.)

## Kök Neden: Yetkilendirme Modelinin Yapısal Ortak Noktası

Azure RBAC ve GCP IAM birbirinden farklı terminoloji kullanır ama ikisinin de yetki yükseltmeye açık olmasının altında yatan neden aynıdır: **"yetki yönetme yetkisi" ile "kaynağı kullanma yetkisi" aynı yetkilendirme sisteminin içinde, birbirinden ayrıştırılmadan modellenir.**

Klasik AD'de bile bu sorun vardı (`WriteDacl` bir ACE'yi değiştirme yetkisiydi), ama bulutta ölçek çok daha büyük çünkü:

1. **Rol tanımları (role definitions) veri düzlemi ile kontrol düzlemini net ayırmaz.** Bir rolün "bu kaynağı oku/yaz" izniyle "bu kaynak üzerinde kimin erişebileceğini belirle" izni çoğu zaman aynı rol paketinin içine sıkıştırılmıştır. Örneğin Azure'da `Contributor` rolü kaynakları yönetme yetkisi verir ama rol ataması yapamaz — oysa `Owner` hem kaynak yönetimi hem rol ataması yapabilir. Bu ayrım net görünse de, pratikte `Contributor` + ayrı bir "sınırlı rol atama" izni kombinasyonu, ya da belirli kaynak türlerinin (otomasyon hesapları, fonksiyonlar, sanal makineler) kod çalıştırma yeteneği üzerinden dolaylı olarak kimlik ödünç alması, çizgiyi bulanıklaştırır.

2. **Özel roller (custom roles) modelin gücünü aynı zamanda en büyük risk kaynağına çevirir.** Hem Azure hem GCP, kuruluşların "en az yetki" ilkesini pratik hale getirmesi için ince taneli izinlerden kendi rollerini bileşenlerine ayırıp oluşturmasına izin verir. Ama bu esneklik, bir mühendisin "işe yarasın" diye bir custom role'e -- fark etmeden -- yetki yönetme izni (`*.setIamPolicy`, `Microsoft.Authorization/roleAssignments/write` gibi) eklemesine de kapı açar. Custom role'ler merkezi bir onay sürecinden geçmediği veya periyodik denetlenmediği sürece, zamanla "gölge Owner" rolüne dönüşürler.

3. **Kimliğe bürünme (impersonation) mekanizmaları, RBAC/IAM denetiminin dışında ikinci bir yetki katmanı yaratır.** GCP'de bir hizmet hesabına (service account) `roles/iam.serviceAccountTokenCreator` verilmesi, o hizmet hesabının kimliğine bürünme (impersonation) yetkisi anlamına gelir — ve bu, hedef hizmet hesabının IAM politikasında değil, **onu impersonate eden asılın** izin setinde tanımlıdır. Böyle bir izni denetlemek için hem "kim impersonate edebilir" hem "kim tarafından impersonate edilebilir" ilişkisini aynı anda görebilmeniz gerekir — tek yönlü bir rol listesi bunu göstermez.

4. **Kaynak hiyerarşisinin (organizasyon → klasör/yönetim grubu → proje/abonelik → kaynak) miras (inheritance) mantığı, "bu kişi burada ne yapabilir" sorusunu tek bir kaynağa bakarak cevaplanamaz hale getirir.** Üst düzeyde verilen bir rol, farkında olunmadan alt kademedeki onlarca kaynağa sirayet eder. Bir yönetici GCP'de organizasyon düzeyinde `roles/resourcemanager.folderIamAdmin` verdiğinde, bunun altındaki her projede rol atama yetkisi devretmiş olduğunu genellikle görselleştirmez.

5. **Denetim araçlarının olgunluk eksikliği.** AD dünyasında BloodHound'un yarattığı "saldırgan gözüyle düşün" kültürü, bulut IAM'de henüz aynı yaygınlıkta değil. Çoğu kuruluş IAM Recommender/Access Analyzer gibi tekil-izin odaklı araçlarla yetiniyor; "A rolünden B rolüne zincirli yol var mı" sorusunu soran graf tabanlı analiz nadiren rutin bir güvenlik pratiği.

## Azure RBAC Yetki Yükseltme Zincirleri

### Zincir 1: `Owner` / `User Access Administrator` — Doğrudan Rol Atama Yetkisi

Azure RBAC'te iki rol özellikle kritik çünkü `Microsoft.Authorization/roleAssignments/write` işlemini içerir: **Owner** (kaynağı tam yönetme + rol atama) ve **User Access Administrator** (sadece rol atama, kaynağı değiştiremez ama erişimi yönetebilir).

**Çalışma mantığı:** Bir asıl (kullanıcı, grup veya service principal), bir kaynak grubunda veya abonelikte bu rollerden birine sahipse, kendine veya kontrol ettiği başka bir asıla **daha yüksek kapsamda** ya da **daha geniş** bir rol atayabilir. Kritik nokta şu: rol ataması genellikle "aşağı doğru" (daha dar kapsamda) düşünülür ama teknik olarak sınırlama kapsam (scope) ile ilgilidir, rolün gücüyle değil — bir kaynak grubunda `Owner` olan biri, o kaynak grubu içindeki herhangi bir kaynağa herhangi bir rolü atayabilir, kendisi dahil.

**Yaygın kök neden:** Kaynak grupları oluşturulurken "bu ekip burada tam yetkili olsun" kolaylığıyla `Owner` verilir; zamanla bu kaynak grubuna daha kritik kaynaklar (Key Vault, veritabanları, ağ geçitleri) eklenir ama rol ataması gözden geçirilmez. Başlangıçta düşük riskli görünen bir atama, kaynak grubunun içeriği büyüdükçe sessizce yüksek riskli hale gelir.

### Zincir 2: Yönetilen Kimlik (Managed Identity) + Geniş Kapsamlı Rol → Kod Yürütmeden Yetki Yükseltmeye

Bu zincir kaynak düzleminde başlar: bir hesaplama kaynağına (VM, Function App, Automation Account, AKS pod'u) bağlı bir managed identity'ye, gerçek ihtiyacından çok daha geniş bir kapsamda (abonelik düzeyinde `Contributor` gibi) rol verilmiştir.

**Çalışma mantığı (kavramsal):** Saldırgan bu kaynağı çalıştıran uygulamada bir zafiyet (RCE, SSRF, komut enjeksiyonu) bulduğunda, kaynağın yerel metadata uç noktasından (dışa kapalı, kimlik doğrulama gerektirmeyen bir yerel servis) o kimliğe ait bir erişim token'ı elde edebilir. Token elindeyken, artık o kimliğin sahip olduğu Azure RBAC rolünün kapsadığı her şeyi yapabilir. Eğer rol `Contributor` ise, kaynak oluşturma/silme/değiştirme yetkisi kazanır (yatay+dikey hareket); eğer rol `Owner` veya `User Access Administrator` ise, doğrudan Zincir 1'e geçiş yapar.

**Kritik gözlem — SSRF'in bulutta neden özellikle tehlikeli olduğu:** Klasik SSRF zafiyetleri genelde "iç ağa erişim" riski olarak değerlendirilir. Bulutta SSRF, doğrudan kimlik hırsızlığına dönüşür çünkü metadata servisi HTTP üzerinden, genellikle ekstra bir doğrulama katmanı olmadan erişilebilir bir iç adrestedir. Bu yüzden bulut ortamlarında SSRF risk sınıflandırması, on-prem eşdeğerinden sistematik olarak daha yüksek tutulmalıdır.

### Zincir 3: Custom Role İçinde Gizli Yetki Yönetim İzni

**Çalışma mantığı:** Bir platform ekibi, "sadece sanal makineleri yeniden başlatabilsin" niyetiyle bir custom role tanımlar, ama rolü genişletirken (kopyala-yapıştır ile başka bir rolden devraldığı için) `Microsoft.Authorization/*` gibi bir wildcard izin kalır, ya da `roleAssignments/write` açıkça eklenmemiş olsa da `Microsoft.Authorization/*/write` gibi geniş bir desen bunu kapsar. Bu role sahip her asıl, aslında görünenin çok ötesinde bir yetki yükseltme kapasitesine sahiptir. Custom role'lerin JSON tanımı incelenmeden onaylandığında bu tür "gizli" izinler fark edilmez.

### Zincir 4: Kaynak Grubu/Abonelik Sınırları Arası Devretme (Delegasyon Zinciri)

Büyük kuruluşlarda abonelikler arası kaynak paylaşımı (paylaşılan ağ, merkezi log toplama, paylaşılan Key Vault) yaygındır. Bir abonelikte düşük yetkili görünen bir asıl, paylaşılan bir kaynağa (örn. merkezi bir Automation Account veya paylaşılan bir Key Vault) erişimi olduğunda ve bu paylaşılan kaynağın kendisi başka bir abonelikte geniş yetkili bir managed identity çalıştırıyorsa, iki abonelik arasında beklenmedik bir yükseltme köprüsü oluşur. Bu, "tek abonelik düşünme" alışkanlığının en büyük kör noktasıdır.

## GCP IAM Yetki Yükseltme Zincirleri

GCP IAM'in mimarisi Azure'dan farklı iki eksen ekler: **hizmet hesabı kimliğine bürünme (service account impersonation)** ve **özel rol (custom role) oluşturma yetkisinin kendisinin bir yükseltme aracı olması**.

### Zincir 1: `iam.serviceAccountTokenCreator` — Doğrudan İmpersonation Zinciri

**Çalışma mantığı (kavramsal):** GCP'de bir hizmet hesabı (service account, SA), insan olmayan bir kimliktir ve genellikle iş yüklerine (Compute Engine, Cloud Functions, GKE) bağlanır. `roles/iam.serviceAccountTokenCreator` (veya bunu içeren daha geniş bir rol) bir kullanıcıya veya başka bir SA'ya verildiğinde, sahibi o hedef SA adına kısa ömürlü token üretebilir hale gelir — yani **hedef SA'nın kimliğine bürünebilir**, hedef SA'nın parolasını veya anahtarını bilmeye gerek kalmadan.

Bunun yetki yükseltmeye dönüşmesi şöyle işler: A kullanıcısının doğrudan projede sınırlı bir rolü (örn. `roles/viewer`) olsun, ama A, B hizmet hesabı üzerinde `serviceAccountTokenCreator` rolüne sahip olsun. B hizmet hesabının ise projede `roles/owner` veya `roles/editor` gibi geniş bir rolü varsa: A, B'nin kimliğine bürünerek B'nin tüm yetkilerini devralır. Kritik nokta: **A'nın kendi IAM politikasına bakarak bu riski görmek mümkün değildir** — risk B'nin IAM politikasında (kim B'yi impersonate edebilir listesinde) gizlidir. Bu, tam olarak AD'deki "B kullanıcısı üzerinde GenericAll'a sahip olan A, B'nin tüm yetkilerini miras alır" mantığının bulut IAM karşılığıdır ve ROADtool/BloodHound tarzı graf analizinin GCP'de neden gerekli olduğunun en net kanıtıdır.

**Zincirleme örneği:**
1. Proje A'da düşük yetkili bir kullanıcı hesabı ele geçirilir.
2. Bu kullanıcının, gözden kaçmış eski bir CI/CD entegrasyonundan kalma `roles/iam.serviceAccountTokenCreator` izni, üretim ortamında `roles/editor` yetkisine sahip bir SA üzerinde vardır.
3. Saldırgan bu SA'yı impersonate eden bir erişim token'ı üretir (GCP'nin standart token değişim mekanizması üzerinden).
4. Artık `roles/editor` yetkisiyle, projedeki neredeyse tüm kaynakları okuyup değiştirebilir — ve editor rolü genellikle IAM politikalarını da değiştirme kapasitesine sahip olabildiğinden (kaynak türüne göre değişir), tam kontrol noktasına yaklaşır.

### Zincir 2: Hizmet Hesabı Anahtarı Oluşturma Yetkisi (`iam.serviceAccountKeyAdmin` / `iam.serviceAccounts.keys.create`)

**Çalışma mantığı:** Impersonation'a alternatif ikinci bir yol, hedef SA için **uzun ömürlü bir JSON anahtarı** üretmektir. Bu anahtar oluşturulduğu anda indirilebilir bir dosyadır ve dışarı sızması durumunda GCP'nin kısa ömürlü token mekanizmasının sağladığı zaman sınırlaması ve merkezi iptal kolaylığı ortadan kalkar. Bu izne sahip bir asıl, hedef SA'nın tüm yetkilerini süresiz, denetim dışı bir kimlik bilgisine dönüştürebilir. Bu yüzden `serviceAccountKeyAdmin` rolü, `serviceAccountTokenCreator`'dan bile daha risklidir — çünkü ürettiği kimlik bilgisi, ortam dışına taşınabilir ve merkezi oturum iptal mekanizmalarının kapsama alanının dışına çıkabilir.

### Zincir 3: Custom Role Oluşturma/Değiştirme Yetkisi Üzerinden Kendine Yetki Verme

**Çalışma mantığı (kavramsal):** `roles/iam.roleAdmin` (veya proje düzeyinde eşdeğeri) bir asıla, o proje kapsamında yeni custom role tanımlama veya var olan bir custom role'ün izin listesini değiştirme yetkisi verir. Eğer bu asıl aynı zamanda kendine (veya kontrol ettiği başka bir asıla) bir rol atayabiliyorsa (`roles/resourcemanager.projectIamAdmin` gibi ayrı ama sık birlikte verilen bir rolle), iki izni birleştirerek şu döngüyü kurabilir: önce izin listesi geniş bir custom role tanımla, sonra bu role'ü kendine ata. Bu zincir özellikle tehlikelidir çünkü her iki rol de tek başına "makul" görünür (rol yönetimi + kullanıcı ataması ayrı sorumluluklar gibi algılanır) ama ikisinin birleşimi sınırsız yetki yükseltme anlamına gelir.

### Zincir 4: Organizasyon Politikası ve Kaynak Hiyerarşisi Miras Zinciri

GCP'nin kaynak hiyerarşisi (Organization → Folder → Project) IAM rollerini yukarıdan aşağıya miras verir. Bir klasör (folder) düzeyinde verilen `roles/owner` veya `roles/resourcemanager.folderIamAdmin`, o klasörün altındaki **her** projeye otomatik olarak sirayet eder — bu projeler daha sonra oluşturulmuş olsa bile. Kök neden: yöneticiler genellikle "bugün bu klasörün altında ne var" sorusuna bakarak yetki verir, "gelecekte bu klasörün altına ne eklenebilir" sorusunu sormaz. Bu, statik bir yetki değerlendirmesinin dinamik bir organizasyon yapısında neden yetersiz kaldığının klasik örneğidir.

### Zincir 5: Workload Identity Federation Üzerinden Dış Kimlikten SA İmpersonation

Modern GCP ortamlarında CI/CD sistemleri (GitHub Actions, GitLab CI gibi) genellikle statik anahtar yerine Workload Identity Federation kullanarak bir SA'yı impersonate eder. Buradaki risk: federasyon havuzunun (workload identity pool) hangi dış kimliklerin (hangi repo, hangi branch, hangi ortam) impersonation yapabileceğini tanımlayan koşul (attribute condition) çok gevşek yazıldığında — örneğin belirli bir organizasyonun **herhangi bir** GitHub reposuna izin verildiğinde — o organizasyondaki herhangi bir repo üzerinde yazma yetkisi olan biri (ki bu çoğu zaman geniş bir geliştirici kitlesidir), hedef SA'yı impersonate edip onun GCP yetkilerini kazanabilir. Bu, kimlik federasyonunun kolaylığının, dikkatli koşul yazılmadığında nasıl bir yetki yükseltme yüzeyine dönüştüğünün iyi bir örneğidir.

## Tespit: Bir Savunmacı Bu Zincirleri Nasıl Görür

Tekil izin denetimi yeterli değildir; aşağıdaki yaklaşımlar zincir düzeyinde görünürlük sağlar:

**1. Graf tabanlı IAM haritalama.** Azure'da ROADtool ve benzeri açık kaynak araçlar, Graph API ve Azure Resource Manager verilerini çekip asıl-rol-kaynak ilişkilerini bir graf olarak modelleyebilir; GCP'de benzer mantıkla Cloud Asset Inventory (`gcloud asset search-all-iam-policies`) çıktısı bir graf veritabanına (Neo4j gibi) aktarılarak "A'dan B'ye giden en kısa yetki yükseltme yolu" sorgulanabilir hale getirilebilir. Amaç, AD BloodHound'da olduğu gibi "hangi düşük yetkili kimlikler, kaç adımda Owner/Editor'a ulaşıyor" sorusuna somut cevap üretmektir.

**2. Native bulut araçlarının düzenli taranması.**
- Azure: Microsoft Defender for Cloud'un kimlik ve erişim önerileri, Azure AD Privileged Identity Management (PIM) denetim kayıtları, `Microsoft.Authorization/roleAssignments` değişikliklerinin Activity Log üzerinden izlenmesi.
- GCP: IAM Recommender (aşırı geniş rolleri işaretler), Policy Analyzer / Policy Troubleshooter (belirli bir asılın belirli bir kaynağa nasıl eriştiğini geriye doğru izler), Cloud Asset Inventory'nin periyodik export'u.

**3. Anomali odaklı loglama — özellikle şu olaylara özel uyarı kurulmalı:**
- Rol atama olaylarının kendisi (`roleAssignments/write` benzeri Azure Activity Log kayıtları; GCP'de `SetIamPolicy` audit log girdileri), özellikle iş saatleri dışı veya nadiren rol yöneten bir kimlik tarafından yapıldığında.
- GCP'de `GenerateAccessToken` veya `GenerateIdToken` çağrılarının, özellikle daha önce o SA'yı hiç impersonate etmemiş bir asıl tarafından ilk kez yapıldığı anlar.
- Yeni service account key oluşturma olayları (`google.iam.admin.v1.CreateServiceAccountKey`) — bu olay nadir ve genellikle otomasyon dışı bağlamlarda şüpheli kabul edilmelidir.
- Custom role tanımı veya güncellemesi olayları, özellikle wildcard (`*`) içeren izin eklemeleri.

**4. Kimlik ile kaynak arasındaki "kimin kimi impersonate edebildiği" ilişkisinin ayrı bir denetim maddesi olarak ele alınması.** Standart IAM politika denetimleri genelde "bu kaynağa kim erişebilir" sorusuna odaklanır; "bu kimliği kim taklit edebilir" sorusu ayrı bir sorgu gerektirir ve çoğu denetim listesinde eksiktir.

## Savunma: Yapısal Önlemler

**En az yetki ve kapsam daraltma.** `Owner`/`User Access Administrator` (Azure) ve `roles/owner`/`roles/iam.serviceAccountTokenCreator`/`roles/iam.serviceAccountKeyAdmin` (GCP) gibi yetki-yönetimi içeren rolleri, mümkün olan en dar kapsamda (tekil kaynak, tekil kaynak grubu/proje) ve mümkün olan en az sayıda asıla verin. "Abonelik/proje düzeyinde Owner" varsayılan bir kolaylık değil, istisnai bir onay gerektiren bir karar olmalı.

**Zaman sınırlı ve onay gerektiren ayrıcalıklı erişim.** Azure PIM (Privileged Identity Management) benzeri "just-in-time" erişim modelleri, ayrıcalıklı rollerin sürekli aktif olması yerine ihtiyaç anında, süreli ve onaylı şekilde etkinleştirilmesini sağlar. GCP tarafında benzer mantık, zaman sınırlı IAM koşulları (IAM Conditions ile `request.time` bazlı kısıtlamalar) ve geçici rol ataması süreçleriyle uygulanabilir.

**Service account key kullanımının minimize edilmesi.** Mümkün olduğunca statik JSON anahtarları yerine Workload Identity Federation veya kısa ömürlü token mekanizmaları tercih edilmeli; zorunlu olarak var olan anahtarlar için rotasyon zorunluluğu ve kullanılmayan anahtarların otomatik devre dışı bırakılması politikası kurulmalı.

**Federasyon koşullarının (attribute conditions) daraltılması.** Workload Identity Federation havuzlarında, hangi dış kimliğin (belirli repo, belirli branch, belirli ortam etiketi) impersonation yapabileceği mümkün olduğunca spesifik yazılmalı; "bu organizasyona ait her şey" gibi geniş koşullardan kaçınılmalı.

**Custom role yaşam döngüsü yönetimi.** Custom role tanımları merkezi bir inceleme sürecinden (kod incelemesi gibi) geçmeli, periyodik olarak yeniden değerlendirilmeli ve kullanılmayanlar kaldırılmalı. Rol tanımının JSON/YAML gösterimi, sadece "isim" üzerinden değil içerik üzerinden onaylanmalı.

**Düzenli erişim gözden geçirmesi (access review) — özellikle sahiplik ve impersonation ilişkileri için.** Kaynak sahipliği, SA impersonation izinleri ve kaynak hiyerarşisi miras zincirleri, standart "kullanıcı hangi rollere sahip" denetiminin dışında kaldığı için ayrı bir gözden geçirme döngüsüne dahil edilmeli.

**Kaynak hiyerarşisinin sadeleştirilmesi.** Gereksiz derin klasör/kaynak grubu hiyerarşileri ve üst düzeyde verilen geniş roller, miras zincirlerinin öngörülemez büyümesine yol açar. Hiyerarşi, "bugün ne var" değil "gelecekte ne eklenebilir" varsayımıyla tasarlanmalı.

## Yaygın Hatalar

**"Tekil rol makul, dolayısıyla güvenli" varsayımı.** En sık yapılan hata, her rol atamasını izole değerlendirip zincir etkisini hiç sorgulamamaktır. Bir SA üzerindeki `serviceAccountTokenCreator` rolü tek başına zararsız görünür — ama hedef SA'nın kendi yetkisiyle birleştiğinde tablo tamamen değişir.

**Custom role'lerin "bir kere yazıldı, bitti" muamelesi görmesi.** Zamanla değişen kaynak türleri ve API'ler, eskiden dar olan bir custom role'ün kapsamını genişletebilir; periyodik yeniden değerlendirme yapılmazsa rol sessizce daha riskli hale gelir.

**Service account'ların "insan olmadığı için daha az risk taşıdığı" yanılgısı.** Tam tersine, SA'lar MFA'ya tabi değildir, çoğunlukla otomasyon nedeniyle geniş yetkilerle donatılır ve kimlik bilgisi sızıntısına karşı insan kullanıcılardan daha az izlenir — bu onları saldırganlar için daha çekici hedef yapar.

**Kaynak hiyerarşisi mirasının göz ardı edilmesi.** Bir üst düzey rol ataması yapılırken "şu an altında ne var" diye bakılır, "gelecekte buraya ne eklenebilir" hiç sorulmaz — bu, statik denetimlerin dinamik ortamlarda neden yetersiz kaldığının özeti niteliğindedir.

**Native önerilerin (IAM Recommender, Access Advisor) tek başına yeterli sayılması.** Bu araçlar tekil aşırı yetkileri işaretlemekte iyidir ama çok adımlı zincirleri (A→B→C yetki yükseltme yolu) genellikle göremez; graf tabanlı analiz olmadan zincir riski kör nokta olarak kalır.

**Impersonation ve sahiplik ilişkilerinin denetim kapsamı dışında bırakılması.** Güvenlik ekipleri genellikle "kim hangi role sahip" sorusuna odaklanır, "kim kimin kimliğine bürünebilir" veya "kim kimin sahibi" sorularını aynı titizlikle sormaz — oysa bu ikinci katman, zincirlerin asıl kurulduğu yerdir.

## Sonuç

Azure RBAC ve GCP IAM, farklı terminoloji ve mekanizmalarla aynı temel gerçeği paylaşır: yetki yönetme yeteneği ile kaynak kullanma yeteneği aynı sistemde iç içe geçtiğinde, tekil olarak makul görünen izinler zincirlendiğinde tam kontrol noktasına dönüşebilir. Bunun savunması, AD dünyasında BloodHound'un getirdiği zihniyetin bulut IAM'e taşınmasından geçiyor: her rol atamasını izole değil, "buradan nereye ulaşılabilir" sorusuyla, graf tabanlı ve sürekli güncellenen bir görünürlükle değerlendirmek. Bu konuyu on-prem AD ACL analizinden ayrı ele almanın nedeni tam olarak bu — mekanizmalar farklı, ama zihniyet aynı ve bulut tarafında bu zihniyetin araç/kültür olgunluğu henüz aynı seviyede değil.
