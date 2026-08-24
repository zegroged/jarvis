# BloodHound Metodolojisi: Active Directory Saldırı Yollarını Graf Teorisiyle Görmek

## Giriş ve Tanım

BloodHound, Active Directory (AD) ve Azure AD (Entra ID) ortamlarındaki yetki ilişkilerini bir **graf (graph)** olarak modelleyen ve bu graf üzerinde saldırganın hedefe ulaşmak için izleyebileceği yolları ortaya çıkaran bir analiz aracıdır. Klasik yaklaşımda bir sızma testçisi ya da savunmacı, "hangi kullanıcı hangi gruba üye, hangi grup hangi makinede yerel yönetici (local admin)" gibi soruları tek tek, elle sorgulayarak yanıtlamaya çalışır. Bu, orta ölçekli bir AD ortamında bile insanın kavrayamayacağı kadar büyük bir kombinatorik uzaya yol açar. BloodHound'un getirdiği devrimsel fikir şudur: bu ilişkiler aslında bir **yönlü graf (directed graph)** oluşturur ve "kimden kime yetki akar" sorusu, graf teorisindeki **en kısa yol (shortest path)** problemine indirgenebilir.

Aracın felsefesini özetleyen ünlü söz şudur: "Defenders think in lists, attackers think in graphs." Yani savunmacılar varlıkları liste hâlinde düşünür (kullanıcı listesi, grup listesi, makine listesi), saldırgan ise bu varlıklar arasındaki **ilişkileri** düşünür. Saldırgan için önemli olan tek tek nesnelerin güvenli olması değil, aralarındaki en zayıf ilişki zincirinin nereye gittiğidir. BloodHound tam da bu paradigma farkını savunmacının lehine çevirmeyi amaçlar.

## Kök Neden: AD Neden Bir Grafa Dönüşür?

Active Directory'nin doğası gereği yetkiler **geçişli (transitive)** ve **dolaylı (indirect)** olarak devrolur. Bu geçişlilik, güvenlik açığının kök nedenidir. Birkaç mekanizmayı ayrı ayrı düşünelim:

**Grup üyelikleri iç içedir (nested groups).** Bir kullanıcı A grubunun üyesidir, A grubu B grubunun üyesidir, B grubu da bir sunucuda yerel yönetici haklarına sahiptir. Bu kullanıcı, hiçbir yerde doğrudan "bu sunucunun yöneticisi" olarak görünmese de, geçişli üyelik zinciri sayesinde fiilen o sunucuyu yönetir. AD, iç içe grup üyeliğinde derinlik sınırı koymadığı için bu zincirler uzayabilir ve gözden kaçar.

**ACL'ler (Access Control List) nesneler arası yetki tanımlar.** AD'deki her nesnenin (kullanıcı, grup, bilgisayar, GPO, OU) bir güvenlik tanımlayıcısı (security descriptor) vardır. Bir principal'in başka bir nesne üzerinde `GenericAll`, `GenericWrite`, `WriteDACL`, `WriteOwner`, `ForceChangePassword`, `AddMember` gibi hakları olabilir. Bu haklar, "X kullanıcısı Y nesnesini ele geçirebilir" anlamına gelir. Örneğin bir kullanıcının başka bir kullanıcı üzerinde `ForceChangePassword` hakkı varsa, o kullanıcının parolasını sıfırlayıp kimliğine bürünebilir. Bu, çoğu yöneticinin farkında bile olmadığı, delegasyon (delegation) yapılandırmaları ve tarihsel birikimlerle oluşan devasa bir yetki ağı yaratır.

**Oturum bilgisi (sessions) yatay geçişi mümkün kılar.** Bir kullanıcı bir makinede oturum açtığında, o kullanıcının kimlik bilgileri (credentials) o makinenin belleğinde (LSASS process) tutulur. Saldırgan o makinede yerel yönetici olursa, orada oturum açmış bir Domain Admin'in token'ını veya hash'ini çalabilir. Yani "hangi ayrıcalıklı kullanıcı hangi makinede oturumda" bilgisi, saldırı yolunun kritik bir kenarıdır.

**Kimlik doğrulama delegasyonu ve trust ilişkileri.** Kerberos'taki unconstrained/constrained/resource-based constrained delegation yapılandırmaları, bir hizmetin başka bir kullanıcı adına kimlik doğrulaması yapmasına izin verir. Domain trust ilişkileri ise bir orman (forest) içindeki farklı domain'ler arasında yetki köprüleri kurar.

İşte bu dört mekanizma birleştiğinde, ortaya varlıkların **düğüm (node)**, yetki ilişkilerinin **kenar (edge)** olduğu bir yönlü graf çıkar. BloodHound bu grafı toplar, bir veritabanına (Neo4j graf veritabanı) yükler ve üzerinde sorgular çalıştırır.

## Graf Modeli: Düğümler ve Kenarlar

BloodHound'un veri modelini anlamak, metodolojinin kalbidir. **Düğümler**, AD'deki temel nesne tiplerini temsil eder: `User` (kullanıcı), `Group` (grup), `Computer` (bilgisayar/makine), `Domain`, `GPO` (Group Policy Object), `OU` (Organizational Unit), `Container`. Azure tarafında ise `AZUser`, `AZServicePrincipal`, `AZApp`, `AZRole` gibi düğümler eklenir.

**Kenarlar**, bir düğümden diğerine akan yetki ya da ilişki tipini temsil eder ve yönlüdür. En sık karşılaşılanlardan bazıları:

- `MemberOf`: Bir principal'in bir grubun üyesi olması.
- `AdminTo`: Bir principal'in bir makinede yerel yönetici olması.
- `HasSession`: Bir makinede bir kullanıcının oturumunun bulunması.
- `GenericAll` / `GenericWrite`: Bir nesne üzerinde tam ya da geniş yazma yetkisi.
- `WriteDACL`: Bir nesnenin erişim kontrol listesini değiştirebilme (kendine hak ekleyebilme).
- `WriteOwner`: Bir nesnenin sahipliğini üstlenebilme.
- `ForceChangePassword`: Bir kullanıcının parolasını sıfırlayabilme.
- `AddMember`: Bir gruba üye ekleyebilme.
- `CanRDP` / `CanPSRemote`: Uzaktan erişim hakları.
- `AllowedToDelegate`: Kerberos delegasyon hakkı.
- `DCSync`: Domain'den parola hash'lerini replikasyon üzerinden çekebilme (kritik).
- `Owns`: Nesne sahipliği.

Buradaki kilit fikir, her kenarın bir **istismar tekniğine (abuse primitive)** karşılık gelmesidir. `ForceChangePassword` kenarı sadece "bu yetki var" demez; aynı zamanda "bu yetkiyi şu adımlarla kullanarak hedef kullanıcının kimliğine bürünebilirsin" demektir. BloodHound arayüzü, her kenar tipi için istismarın nasıl yapıldığını ve nasıl tespit/engellenebileceğini anlatan yerleşik yardım metinleri içerir. Bu, aracı yalnızca bir görselleştirici olmaktan çıkarıp bir metodoloji rehberine dönüştürür.

## Veri Toplama: SharpHound ve Toplama Yöntemleri

Graf oluşmadan önce verinin toplanması gerekir. BloodHound ekosisteminde toplayıcı (collector) bileşen **SharpHound** olarak adlandırılır (C# ile yazılmış; ayrıca AzureHound Azure tarafı için kullanılır). SharpHound, bir domain kullanıcısı bağlamında çalışır ve genelde LDAP sorguları, SMB üzerinden oturum sorgulama, yerel grup üyeliği sorgulama gibi yöntemlerle veriyi toplar.

Toplama, farklı **collection method** kümeleri hâlinde yapılabilir. Örneğin grup üyeliklerini ve ACL'leri toplamak LDAP üzerinden nispeten "sessiz" iken; oturum bilgisi toplamak makinelere tek tek bağlanmayı gerektirdiği için hem daha gürültülüdür hem de zaman içinde değişen anlık bir görüntüdür. Bu ayrım önemlidir: **oturum verisi zamana bağlıdır (time-sensitive)**. Bir Domain Admin bir makinede yalnızca birkaç dakika oturumda kalmış olabilir; SharpHound o an çalışmadıysa o kritik kenar grafta hiç görünmez. Bu yüzden olgun bir metodoloji, oturum toplamayı zaman içinde tekrarlayarak (loop modu) yapar; böylece ayrıcalıklı oturumların hangi makinelerde belirdiği istatistiksel olarak yakalanır.

Toplama sonrası veri JSON dosyaları olarak çıkar ve BloodHound arayüzüne yüklenerek Neo4j veritabanına aktarılır. Modern sürümlerde (BloodHound Community Edition ve BloodHound Enterprise) mimari değişmiş, veri toplama ve ingest süreçleri farklılaşmış olsa da temel graf mantığı aynı kalır.

Burada bir dürüstlük notu düşmek gerekir: SharpHound'un tam komut satırı bayrakları, collection method isimleri ve çıktı formatları sürümden sürüme değişmiştir. Belirli bir bayrağı ezberden kesin olarak vermek yerine, prensibi akılda tutmak daha sağlıklıdır: "önce yapısal veri (LDAP: gruplar, ACL'ler, delegasyon), sonra zamana bağlı veri (oturumlar, döngüsel toplama)".

## En Kısa Yol: DA'ya Giden Yolu Bulmak

Metodolojinin en çok bilinen ve en güçlü kullanımı, **"Shortest Paths to Domain Admins"** sorgusudur. Saldırgan tipik olarak düşük yetkili bir kullanıcı hesabıyla başlar (örneğin bir phishing ile ele geçirilmiş standart bir çalışan hesabı) ve nihai hedefi domain üzerinde tam kontrol sağlamaktır; bu da genellikle `Domain Admins` grubuna üye olmak ya da `DCSync` yeteneği kazanmak demektir.

Graf teorisi açısından bu, "başlangıç düğümünden (ele geçirilen kullanıcı) hedef düğüme (Domain Admins) giden en kısa yönlü yolu bul" problemidir. Neo4j'nin altında yatan yol bulma algoritmaları (BFS türevleri ve ağırlıklı en kısa yol algoritmaları) bu sorguyu saniyeler içinde yanıtlar. **Neden "en kısa" yol önemlidir?** Çünkü saldırgan en az adım, en az gürültü ve en az tespit riski ile hedefe ulaşmak ister. Her ek adım (her ek kenar), yeni bir kimlik bilgisi çalma, yeni bir makineye geçme ve dolayısıyla yeni bir tespit fırsatı demektir. En kısa yol, saldırganın "path of least resistance" (en az direnç yolu) dediği şeydir.

Somut bir örnek üzerinden gidelim. Diyelim ki graf şu yolu ortaya çıkardı:

```
[Standart Kullanıcı: ahmet]
      │ MemberOf
      ▼
[Grup: BT-Destek]
      │ AdminTo
      ▼
[Makine: WKS-042]
      │ HasSession
      ▼
[Kullanıcı: yardim_masasi_svc]
      │ ForceChangePassword
      ▼
[Kullanıcı: yedek_admin]
      │ MemberOf
      ▼
[Grup: Domain Admins]
```

Bu yolu adım adım okuyalım, çünkü metodolojinin özü bu okumadadır. `ahmet` normal bir kullanıcıdır ama `BT-Destek` grubunun üyesidir. Bu grup, `WKS-042` iş istasyonunda yerel yöneticidir (belki bir zamanlar destek ekibi kolayca müdahale edebilsin diye verilmiş, sonra unutulmuş bir yetki). Saldırgan `ahmet`'i ele geçirdiğinde `WKS-042` üzerinde yönetici olur. O makinede tam o sırada `yardim_masasi_svc` hesabı oturumdadır; saldırgan LSASS belleğinden bu hesabın kimlik bilgilerini çalar. `yardim_masasi_svc` hesabının ise `yedek_admin` kullanıcısı üzerinde `ForceChangePassword` hakkı vardır; saldırgan bu hakla `yedek_admin`'in parolasını sıfırlar. Ve `yedek_admin`, geçmişte bir bakım işi için `Domain Admins` grubuna eklenip çıkarılmayı unutmuş bir hesaptır. Zincir tamamlanır: standart bir çalışan hesabından tam domain kontrolüne dört kenarda ulaşılmıştır.

Dikkat edilmesi gereken nokta, bu zincirdeki hiçbir tek adımın kendi başına "kritik açık" gibi görünmemesidir. Her biri makul bir operasyonel gerekçeyle konulmuş, ama toplamı felaket olan yapılandırmalardır. İnsan gözü bu zinciri bir liste bakışıyla asla göremez; graf bakışıyla ise anında görünür hâle gelir.

## Sömürü Mantığı: Kenarları Nasıl İstismar Etmek

Saldırgan bakış açısından metodoloji şöyle işler. Önce bir dayanak (foothold) elde edilir ve o hesap grafta işaretlenir ("Mark as Owned"). Ardından "bu sahip olduğum hesaptan Domain Admins'e giden yollar" sorgulanır. Yol bulunduğunda, saldırgan yolu kenar kenar istismar eder; her kenar tipi kendi tekniğini gerektirir:

- `AdminTo` kenarında hedef makinede kod çalıştırılıp kimlik bilgileri (mimikatz benzeri araçlarla LSASS'tan) çekilir.
- `HasSession` kenarında o oturumdaki kullanıcının token'ı ya da hash'i çalınır; `pass-the-hash` veya `pass-the-ticket` teknikleriyle o kimliğe bürünülür.
- `ForceChangePassword` kenarında hedef kullanıcının parolası sıfırlanır (bu hedef kullanıcıyı uyarabilir, bu yüzden dikkatli kullanılır).
- `GenericAll` / `GenericWrite` kenarında hedef nesneye göre farklı teknikler devreye girer: bir kullanıcıya karşı `targeted Kerberoasting` (SPN ekleyip hizmet biletini çıkarıp offline kırma) ya da parola sıfırlama; bir gruba karşı üye ekleme; bir bilgisayara karşı resource-based constrained delegation kurma.
- `WriteDACL` kenarında saldırgan önce kendine `GenericAll` gibi bir hak ekler, sonra onu istismar eder.
- `DCSync` kenarında domain'in tüm parola hash'leri replikasyon protokolü taklit edilerek çekilir; bu, `krbtgt` hesabının hash'ini de içerir ve **Golden Ticket** saldırısına kapı açar.

Metodolojinin saldırgan için değeri, bu tekniklerin **tek tek ezberlenmesi gerekmemesidir**. Graf hangi yolun mevcut olduğunu söyler, aracın yerleşik dokümantasyonu da o kenarın nasıl istismar edileceğini adım adım anlatır. Bu yüzden BloodHound, saldırının "keşif ve planlama" fazını neredeyse otomatikleştirir.

## Savunma Analizi: Grafı Savunmacı Lehine Kullanmak

BloodHound bir saldırı aracı gibi görünse de, asıl kalıcı değeri **savunma** tarafındadır ve metodolojinin en olgun kullanımı budur. Savunmacı, aynı grafı kullanarak saldırganın göremediği bir avantaja sahiptir: tüm grafı bir bütün olarak görür, saldırgan ise ancak keşfettiği kadarını görür.

**Choke point (darboğaz) analizi.** Savunmanın en verimli yaklaşımı, tek tek yolları kapatmaya çalışmak değil, birçok yolun ortak geçtiği **darboğaz düğümlerini** bulup onları güçlendirmektir. Grafta öyle düğümler vardır ki, DA'ya giden yolların büyük çoğunluğu o düğümden geçer. Bu bir servis hesabı, bir yardım masası grubu ya da aşırı yetkilendirilmiş bir GPO olabilir. O tek düğümü düzeltmek (yetkisini kısmak, üyeliğini temizlemek), yüzlerce saldırı yolunu tek hamlede ortadan kaldırabilir. Graf teorisinde buna kabaca "yüksek betweenness centrality'ye sahip düğüm" denir; savunmacı bu düğümleri öncelik sırasına koyar. Bu, kısıtlı savunma bütçesini en yüksek etkili yere yatırmanın matematiksel yoludur.

**Tier 0 / katmanlı model (tiering) doğrulaması.** Microsoft'un ayrıcalıklı erişim modeli, en kritik varlıkları (domain controller'lar, DA hesapları) Tier 0 olarak izole etmeyi öngörür. İlke şudur: Tier 0 kimlik bilgileri asla daha düşük güvenlikli makinelerde (iş istasyonları, uygulama sunucuları) açığa çıkmamalıdır. BloodHound, bu ilkenin ihlal edilip edilmediğini doğrulamak için mükemmel bir araçtır: "Herhangi bir düşük katman düğümünden Tier 0'a giden bir yol var mı?" sorusu, katmanlı modelin gerçekten uygulanıp uygulanmadığını ampirik olarak test eder. Eğer böyle bir yol varsa, katmanlama kâğıt üzerinde vardır ama pratikte delinmiştir.

**Attack path'lerin sürekli izlenmesi.** AD statik bir yapı değildir; her gün yeni gruplar, yeni delegasyonlar, yeni oturumlar oluşur. Dolayısıyla bir kez temizlenmiş bir ortam, haftalar içinde yeniden yollarla dolabilir. BloodHound Enterprise'ın felsefesi tam da budur: grafı bir kereye mahsus değil, sürekli toplayıp izleyerek yeni açılan saldırı yollarını ve darboğazların risk skorunun zaman içindeki değişimini takip etmek. Savunma, tek seferlik bir temizlik değil, sürekli bir hijyen sürecine dönüşür.

**"Owned"tan geriye çalışma.** Bir olay müdahalesinde (incident response), belirli bir hesabın ele geçirildiği biliniyorsa, o hesap "owned" işaretlenip "buradan nereye gidebilirdi" sorgulanarak saldırganın olası hareket alanı ve bir sonraki hedefleri önceden kestirilebilir. Bu, savunmacıya proaktif bir avantaj verir.

## Yaygın Hatalar

Metodolojiyi uygularken sık yapılan hatalar, hem saldırı testinin hem de savunmanın değerini düşürür.

**Yalnızca en kısa yola odaklanmak.** "Shortest Paths to DA" güçlü bir başlangıçtır ama tuzaktır. En kısa yolu kapatmak, saldırganı ikinci en kısa yola iter; graf hâlâ yollarla doludur. Doğru yaklaşım tek yolları kesmek değil, darboğazları hedeflemektir. Aksi hâlde bir "whack-a-mole" (köstebek vurma) oyununa dönüşür.

**Oturum verisinin zaman bağımlılığını göz ardı etmek.** Tek seferlik toplama, o an oturumda olmayan ayrıcalıklı kullanıcıları kaçırır. Grafta yol görünmemesi, yolun olmadığı anlamına gelmez; sadece o anlık görüntüde yakalanmadığı anlamına gelir. Olgun ekipler oturumu döngüsel ve farklı zaman dilimlerinde toplar.

**Grafın verdiği yolu doğrulamadan gerçek kabul etmek.** BloodHound bazen mantıksal olarak var olan ama pratikte işlemeyen kenarlar gösterebilir (örneğin bir hesap devre dışı bırakılmış, bir yetki başka bir denetimle engellenmiş olabilir). Yol, bir hipotezdir; istismar edilebilirliği doğrulanmalıdır.

**Azure/hibrit ortamı unutmak.** Modern kurumlar saf on-prem AD değildir. On-prem ile Entra ID arasındaki senkronizasyon hesapları (örneğin dizin senkronizasyon hesabı) ve bulut rolleri, bir taraftan diğerine köprü kuran kritik saldırı yolları içerir. Yalnızca on-prem grafına bakmak, resmin yarısını kaçırmaktır.

**Toplayıcıyı çok yüksek yetkiyle çalıştırıp gürültü yaratmak veya güvenlik kontrollerini tetiklemek.** Bir sızma testinde SharpHound'un agresif toplaması EDR/tespit sistemlerini tetikleyebilir; savunmacı açısından ise toplayıcıyı gereğinden yetkili çalıştırmak yeni riskler doğurabilir.

## En İyi Pratikler

Sağlıklı bir BloodHound metodolojisi şu ilkeler üzerine kurulur.

**Saldırı yolu yönetimini süreç hâline getirin.** Tek seferlik bir "audit" yerine, grafı düzenli aralıklarla toplayıp darboğazları risk sırasına koyan, düzelttikçe skorun düştüğünü ölçen sürekli bir program kurun. AD güvenliği bir durum değil, bir eğilimdir.

**Darboğaz odaklı önceliklendirme yapın.** Her yolu değil, en çok yolun geçtiği düğümleri hedefleyin. Bir servis hesabının aşırı yetkisini kısmak, tek başına yüzlerce yolu kapatabilir. Etkiyi maksimize eden bu az sayıda değişikliğe odaklanın.

**Katmanlı yönetim modelini graf ile doğrulayın.** Tier 0 varlıklarına düşük katmandan yol olmadığını düzenli olarak test edin. Ayrıcalıklı hesapların iş istasyonlarında oturum açmasını engelleyen politikalar (ayrı yönetim iş istasyonları — PAW), grafta "session tabanlı" yolların büyük kısmını kurutur.

**En küçük yetki (least privilege) ilkesini ACL'lere kadar taşıyın.** Sorun çoğu zaman grup üyeliklerinde değil, kimsenin bakmadığı ACL'lerde gizlidir. Nesneler üzerinde gereksiz `GenericAll`, `WriteDACL`, `Owns` haklarını periyodik olarak temizleyin. Delegasyonları gözden geçirin; özellikle unconstrained delegation son derece tehlikelidir ve nadiren gereklidir.

**Ayrıcalıklı grupları ve kullanıcıları düzenli denetleyin.** `Domain Admins`, `Enterprise Admins`, `Backup Operators` gibi grupların üyeliğini periyodik gözden geçirin; "bir kerelik iş için eklenip unutulmuş" hesapları bulup çıkarın. Örneğimizdeki `yedek_admin` tam da bu tür bir unutulmuş yetkiydi.

**Toplamayı ve analizi yetkili bir bağlamda, izole edilmiş şekilde yapın.** Graf verisi (Neo4j veritabanı, JSON çıktıları) aslında saldırgan için bir hazine haritasıdır. Bu veriyi güvenli saklayın; yanlış ellere geçmesi, saldırganın tüm keşif işini onun yerine yapmış olmanız demektir.

## Sonuç

BloodHound metodolojisinin gücü, tek bir açıktan değil, masum görünen yapılandırmaların **bir araya gelerek** oluşturduğu saldırı zincirlerini görünür kılmasından gelir. Active Directory'nin geçişli yetki doğası, insan gözünün kavrayamayacağı bir graf üretir; BloodHound bu grafı toplar, en kısa yol algoritmalarıyla saldırganın izleyeceği patikayı ortaya çıkarır ve aynı grafı savunmacının darboğazları kapatması için kullanılabilir hâle getirir. Saldırgan için bu, keşif ve planlamanın otomasyonu; savunmacı için ise "listeler yerine graf düşünme" avantajının nihayet kendi lehlerine dönmesidir. Metodolojiyi doğru uygulamanın anahtarı, tek tek yolları kovalamak değil; grafın topolojisini anlayıp en yüksek etkili darboğazları, sürekli ve ölçülebilir bir hijyen süreciyle kapatmaktır.
