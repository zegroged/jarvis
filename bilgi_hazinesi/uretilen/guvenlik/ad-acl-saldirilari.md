# Active Directory ACL Tabanlı Saldırılar: GenericAll, WriteDACL ve Yetki Zincirleri

## Giriş ve Tanım

Active Directory (AD), bir kurumdaki kimlikleri, bilgisayarları, grupları ve politikaları merkezî olarak yöneten bir dizin hizmetidir. Bu dizin içindeki her nesne (kullanıcı, grup, bilgisayar, Organizational Unit, GPO bağlantısı vb.) bir **security descriptor** taşır. Bu security descriptor'ın en kritik parçası, nesne üzerinde kimin neyi yapabileceğini tanımlayan **DACL** (Discretionary Access Control List) yapısıdır. DACL, sıralı **ACE** (Access Control Entry) girişlerinden oluşur; her ACE, belirli bir güvenlik ilkesine (principal: kullanıcı, grup, bilgisayar) belirli bir hak (right) tanır veya reddeder.

ACL tabanlı saldırılar, bu izin yapısındaki yanlış yapılandırmaları (misconfiguration) kötüye kullanarak yetki yükseltmeyi (privilege escalation) ve yanal hareketi (lateral movement) hedefler. Buradaki kritik nokta şudur: Bu saldırılar bir yazılım açığı (exploit) değildir. Ortada patch'lenecek bir buffer overflow ya da bir CVE yoktur. Saldırgan, sistemin **tasarlandığı gibi** verdiği izinleri kullanır. Yani bu, "kırılmış bir kilit" değil, "yanlış kişiye verilmiş bir anahtar" problemidir. Bu ayrım, savunmayı da tümüyle şekillendirir: çözüm bir güncelleme yüklemek değil, izinleri denetlemek ve düzeltmektir.

## Kök Neden: ACL'ler Neden Bu Kadar Tehlikeli Hale Geliyor?

AD'nin izin modeli son derece granüler (ince taneli) tasarlanmıştır. Bir nesne üzerinde onlarca farklı hak türü tanımlanabilir. Sorun, bu esnekliğin zamanla kontrolden çıkmasıdır. Kök nedenleri anlamak, savunmanın da temelidir:

**1. İzin birikimi (permission sprawl):** Kurumlar yıllar içinde büyür. Bir yardım masası ekibine "kullanıcı şifresi sıfırlayabilsin" diye verilen geniş bir yetki, bir uygulama kurulumu için bir servis hesabına verilen "grup üyeliğini yönetme" hakkı, bir yönetici tarafından aceleyle atanan `GenericAll`... Bunlar tek tek zararsız görünür ama üst üste bindiğinde devasa bir saldırı yüzeyi oluşturur. Kimse bu izinleri geri almaz çünkü hangi izin neyi kırar bilinmez.

**2. Kalıtım (inheritance):** ACE'ler bir OU'ya atandığında, alt nesnelere miras yoluyla geçebilir. Bir OU seviyesinde yapılan hatalı bir atama, altındaki yüzlerce nesneyi etkiler. Bu, hatanın ölçeğini görünmez şekilde büyütür.

**3. Dolaylı haklar:** Bazı haklar doğrudan "tam yetki" gibi görünmez ama sonuçları öyledir. Örneğin bir kullanıcının parolasını sıfırlama hakkı (`User-Force-Change-Password`), o kullanıcının kimliğine bürünmeyi (impersonation) sağlar. Bir gruba üye ekleme hakkı, o grubun tüm ayrıcalıklarını devralmayı mümkün kılar. Savunmacılar genellikle sadece "Domain Admins üyeliğine" bakar; oysa bu dolaylı yollar aynı hedefe götürür.

**4. Görünmezlik:** Bu izinler AD'nin derinliklerinde, security descriptor'lar içinde saklıdır. Bir yönetici, "acaba bu servis hesabı domain'i ele geçirebilir mi?" sorusunu manuel olarak yanıtlayamaz, çünkü cevap binlerce ACE'nin oluşturduğu bir grafikte gizlidir. İşte BloodHound'un devreye girdiği ve hem saldırgan hem savunmacı için oyunu değiştirdiği nokta tam da burasıdır.

## Kritik Hak Türleri ve Çalışma Mantıkları

Saldırı zincirlerini anlamak için önce hangi ACE haklarının neye yol açtığını bilmek gerekir. En önemlileri şunlardır:

### GenericAll

Bir nesne üzerindeki tam kontroldür. Nesnenin sahibi olmak gibidir. `GenericAll` hakkına sahip bir principal, o nesne üzerinde neredeyse her şeyi yapabilir: parolayı sıfırlayabilir, grup üyeliğini değiştirebilir, DACL'i yeniden yazabilir, SPN ekleyebilir. Bu yüzden `GenericAll` en tehlikeli ve saldırganların en çok aradığı haktır. Hedef türüne göre kullanımı değişir:
- Hedef bir **kullanıcı** ise: parolası sıfırlanabilir ya da Kerberoasting için SPN eklenebilir (targeted Kerberoasting).
- Hedef bir **grup** ise: gruba kendini ekleyerek grubun ayrıcalıkları devralınır.
- Hedef bir **bilgisayar** ise: Resource-Based Constrained Delegation (RBCD) kurularak o makinede yönetici bağlamı elde edilebilir.

### GenericWrite

`GenericAll`'dan biraz daha dardır ama pratikte çok güçlüdür. Nesnenin çoğu özniteliğini (attribute) yazma yetkisi verir. Bir kullanıcı nesnesinde `servicePrincipalName` yazılabilirse targeted Kerberoasting yapılabilir; `scriptPath` ya da logon script yönlendirilebilir. Bir grupta `member` özniteliği yazılabilirse üyelik değiştirilebilir.

### WriteDACL

Bu, saldırının "kendini besleyen" tarafıdır. `WriteDACL`, nesnenin DACL'ini, yani izin listesini yeniden yazma hakkıdır. Elinde `WriteDACL` olan bir saldırgan, kendisine o nesne üzerinde `GenericAll` veren yeni bir ACE ekler. Yani sınırlı bir hak, tam yetkiye dönüştürülür. Bu, ACL saldırılarındaki en zarif adımlardan biridir: az bir yetkiyi çok yetkiye çevirmenin kanonik yolu budur.

### WriteOwner

Nesnenin sahipliğini (owner) değiştirme hakkıdır. Bir nesnenin sahibi, DACL'i her zaman değiştirebilir (owner'ın örtük hakkı vardır). Dolayısıyla saldırgan önce kendini sahip yapar, sonra sahiplik hakkıyla DACL'i yeniden yazıp `GenericAll` alır. `WriteDACL` ile benzer sonuca farklı bir kapıdan ulaşır.

### ForceChangePassword (User-Force-Change-Password)

Bir kullanıcının mevcut parolasını bilmeden yeni parola atama hakkıdır. Bu, hedef kullanıcının kimliğine bürünmenin en doğrudan yoludur. Yüksek ayrıcalıklı bir hesabın parolası sıfırlanabiliyorsa, o hesap ele geçirilmiş demektir.

### AddMember / Self (Grup üyeliği)

Bir gruba üye ekleme hakkı (`WriteProperty` özelinde `member` özniteliği ya da self-membership hakkı). Saldırgan kendini kritik bir gruba ekler ve o grubun tüm ayrıcalıklarını anında kazanır.

### Domain nesnesinde DCSync hakları

Domain kök nesnesi üzerinde `DS-Replication-Get-Changes` ve `DS-Replication-Get-Changes-All` uzatılmış hakları (extended rights), bir principal'a domain'in tüm parola hash'lerini replikasyon protokolü üzerinden çekme imkânı verir. Buna **DCSync** denir. Bu haklar bir kullanıcıya yanlışlıkla verilmişse, o kullanıcı `krbtgt` dahil her hesabın hash'ini alarak domain'i tamamen ele geçirir (Golden Ticket üretimi dahil). ACL zincirlerinin nihai hedefi genellikle budur.

## Somut Örnek: Bir Zincirin Anatomisi

ACL saldırılarının gücü tek bir izinden değil, izinlerin **zincirlenmesinden** gelir. Hiçbir tek adım "Domain Admin" demez, ama adımlar birbirine bağlandığında yol domain'in tepesine çıkar. Tipik bir zinciri düşünelim:

Diyelim ki bir phishing ile ele geçirilen sıradan bir kullanıcı `ahmet` var. Tek başına hiçbir ayrıcalığı yok. Ama:

1. `ahmet`, `IT-Destek` grubuna `GenericWrite` hakkına sahip (belki eski bir proje kalıntısı). `ahmet` kendini bu gruba ekler.
2. `IT-Destek` grubu, `Yardim-Masasi-Yoneticileri` grubu üzerinde `ForceChangePassword` hakkına sahip. Artık `ahmet` bu üst grubun üyelerinin parolasını sıfırlayabilir.
3. `Yardim-Masasi-Yoneticileri` grubunun bir üyesi olan `sysadmin_svc` hesabının parolası sıfırlanır ve bu hesap ele geçirilir.
4. `sysadmin_svc`, bir sunucu OU'su üzerinde `WriteDACL` hakkına sahiptir. Saldırgan bu OU'daki kritik bir sunucuya `GenericAll` verir.
5. O sunucu üzerinde RBCD kurulur, sunucuda `SYSTEM` bağlamı elde edilir; sunucuda oturum açmış bir Domain Admin'in kimlik bilgileri ya da bileti çalınır.
6. Domain Admin bağlamıyla domain nesnesine DCSync hakları eklenir ya da doğrudan DCSync yapılır. Domain düşer.

Bu zincirin her halkası **ayrı ayrı** meşru bir işlem gibi görünür. Hiçbir log satırı "saldırı" demez. İşin dehşet verici tarafı budur: savunmacı her adımı normal bir yönetim faaliyetiyle karıştırabilir.

## Sömürü / İstismar Mantığı: Bu Nasıl Gerçekleştirilir?

İstismar tarafında mantık her zaman aynıdır: **elindeki hakkı kullanarak bir sonraki, daha ayrıcalıklı hedefe eriş.** Kullanılan araçlar bu ilkel işlemleri (primitive) otomatikleştirir:

- **PowerView** (PowerSploit ekosistemi): AD nesnelerini enumerate etmek, ACE'leri okumak ve `Add-DomainObjectAcl`, `Set-DomainObject` gibi fonksiyonlarla DACL değiştirmek, grup üyeliği eklemek için kullanılır. Yerleşik (living-off-the-land) yaklaşımına yakındır çünkü PowerShell ile çalışır.
- **Impacket** araç seti: `dacledit`, `addcomputer`, `rbcd`, `secretsdump` (DCSync için) gibi araçlarla Linux tarafından aynı işlemleri yapmayı sağlar. Örneğin DCSync, `secretsdump` ile replikasyon haklarına sahip bir hesap üzerinden çalıştırılır.
- **BloodHound / SharpHound**: Saldırının beyni. Aşağıda ayrıntısı var.
- **Rubeus / targetedKerberoast**: SPN yazma hakkı varsa targeted Kerberoasting ile servis biletini alıp offline kırmak için.

Genel akış: keşif (BloodHound ile grafiği çıkar) → en kısa yolu bul → her halkada uygun ilkel işlemi çalıştır (parola sıfırla, gruba ekle, DACL yaz) → bir sonraki bağlama geç → hedefe (genellikle DCSync) ulaş.

Önemli bir istismar detayı: bu değişiklikler kalıcı iz bırakır. Saldırgan bir gruba kendini ekler ya da bir DACL'i değiştirir. **Temizlik (cleanup)** saldırının parçasıdır; profesyonel saldırganlar işi bittikten sonra ekledikleri ACE'leri ve grup üyeliklerini geri alır. Bu da savunma açısından bir fırsattır: değişiklik anını yakalamak.

## Savunma: Aynı Silahı Ters Çevirmek

Savunma, saldırının mantığını tersine kullanmakla başlar. En güçlü savunma prensibi şudur: **saldırgan grafiği görebiliyorsa, savunmacı da görebilir ve yolları önceden kesebilir.**

### 1. Grafiği kendiniz çıkarın (BloodHound'u savunma için kullanın)
Kurum, kendi ortamında SharpHound ile toplama yapıp BloodHound grafiğini çizmelidir. Amaç, "sıradan bir kullanıcıdan Domain Admin'e kaç adımda ve hangi yollardan gidilebiliyor?" sorusunu yanıtlamaktır. Bu yollar (özellikle `Shortest Paths to Domain Admins` türü analizler) tespit edilip **kırılmalıdır**. Bir tek hatalı ACE'yi kaldırmak, bazen tüm bir saldırı yolunu imkânsız hale getirir. Bu "attack path management" yaklaşımı en yüksek getiriyi sağlar.

### 2. En küçük ayrıcalık (least privilege) ve izin denetimi
- Kritik nesneler (Domain Admins, `krbtgt`, domain kök nesnesi, DC bilgisayar hesapları, ayrıcalıklı OU'lar) üzerindeki DACL'ler düzenli olarak denetlenmelidir.
- "Bu principal'ın bu nesne üzerinde `GenericAll`/`WriteDACL`/`WriteOwner` hakkına gerçekten ihtiyacı var mı?" sorusu her ayrıcalıklı ACE için sorulmalıdır. Cevap çoğu zaman hayırdır.
- Servis hesaplarına verilen geniş haklar özellikle mercek altına alınmalı; bunlar en sık suistimal edilen zayıf halkalardır.

### 3. Katmanlı yönetim (tiering) modeli
Microsoft'un tiered administration modeli (Tier 0 / Tier 1 / Tier 2) uygulanmalıdır. Tier 0 (domain kimlik altyapısı: DC'ler, AD, ayrıcalıklı hesaplar) diğer katmanlardan izole edilmelidir. Bir Tier 2 (iş istasyonu) hesabının, ACL zinciri yoluyla bile Tier 0'a ulaşabilecek bir yolu olmamalıdır. Attack path'ler genellikle bu izolasyonun sızdırdığı yerlerde ortaya çıkar.

### 4. Tespit (detection)
- **Değişiklik denetimi:** DACL değişiklikleri ve ayrıcalıklı grup üyeliği değişiklikleri için gelişmiş denetim (advanced auditing) açık olmalıdır. Nesne security descriptor'ının değiştirilmesi, güvenlik olay günlüklerinde ilgili olay kimlikleriyle (örneğin nesne erişimi ve dizin hizmeti değişikliği kategorileri) yakalanabilir. Buradaki tam olay ID'lerini uygulamadan önce kendi ortamınızda doğrulayın; sürüme göre değişebilir.
- **DCSync tespiti:** Bir Domain Controller olmayan bir kaynaktan gelen replikasyon istekleri (Get-Changes) güçlü bir DCSync göstergesidir. Ağ ve dizin tarafında bu anomali izlenmelidir.
- **SharpHound toplama tespiti:** SharpHound'un yaptığı yoğun LDAP ve SAMR enumerate faaliyeti anormal davranış olarak işaretlenebilir. Bal küpü (honeypot) hesaplar ve honey ACE'ler (kimsenin dokunmaması gereken sahte ayrıcalıklı yollar) tetikleyici olarak kullanılabilir.

### 5. Sertleştirme
- Ayrıcalıklı hesaplar için "Protected Users" grubu, korumalı ayrıcalıklı OU'lar ve `AdminSDHolder` üzerindeki DACL'in doğru olması sağlanmalıdır. `AdminSDHolder`, korunan grupların ACL'lerini periyodik olarak zorlayan özel bir nesnedir; buraya eklenen hatalı bir ACE tüm korunan hesaplara yayılır, dolayısıyla bu nesne özel dikkat ister.
- Gereksiz güven ilişkileri ve delegasyon yapılandırmaları (özellikle unconstrained delegation) kaldırılmalıdır; bunlar ACL zincirlerinin sıçrama tahtası olur.

## BloodHound'un Merkezî Rolü

BloodHound, AD ortamındaki tüm principal'ları düğüm (node), aralarındaki hakları ve ilişkileri kenar (edge) olarak modelleyen bir grafik analiz aracıdır. SharpHound (toplayıcı) LDAP, SAMR ve diğer protokollerle veriyi toplar; BloodHound bu veriyi bir grafik veritabanında sorgulanabilir hale getirir.

Neden bu kadar dönüştürücü? Çünkü ACL saldırısının en zor kısmı **görmektir**. Onlarca izin arasından "hangi ardışık haklar zinciri beni Domain Admin'e götürür?" sorusunu insan gözüyle yanıtlamak imkânsıza yakındır. BloodHound bunu bir **en kısa yol (shortest path)** grafik problemine indirger. Saldırgan "Mark as Owned" ile ele geçirdiği hesabı işaretler, "Shortest Path to Domain Admins" sorgusunu çalıştırır ve önündeki tam yol haritasını görür: hangi grupta, hangi ACE'yi, hangi sırayla kullanacağını.

Kenar türleri doğrudan yukarıda anlatılan hakları temsil eder: `GenericAll`, `WriteDacl`, `WriteOwner`, `ForceChangePassword`, `AddMember`, `GenericWrite`, `GetChanges`/`GetChangesAll` (DCSync) gibi. BloodHound her kenar için nasıl istismar edileceğine dair yardım metni bile sunar.

Kritik felsefi nokta: **BloodHound saldırgan için ne yapıyorsa, savunmacı için de aynısını yapar.** Aynı grafik, savunmacının elinde bir "saldırı yolu haritası" ve önceliklendirme aracıdır. En çok saldırı yolunun geçtiği düğümler (choke points / darboğazlar) tespit edilip düzeltildiğinde, tek bir müdahaleyle yüzlerce yol kesilir. Bu yüzden modern AD güvenliğinde BloodHound bir sızma testi aracı olduğu kadar bir savunma / hijyen aracıdır.

## Yaygın Hatalar

**Sadece grup üyeliklerine bakmak.** Birçok yönetici güvenliği "kim Domain Admins üyesi?" sorusuna indirger. Oysa ACL zincirleri, hiç grup üyesi olmadan da aynı sona ulaşır. Görünmeyen tehlike ACE'lerdedir.

**"Bu sadece bir kullanıcıya parola sıfırlama hakkı" diye küçümsemek.** Hedef kullanıcının kim olduğu her şeyi belirler. Ayrıcalıklı bir hesaba giden bir parola sıfırlama hakkı, tam yetkiye eşdeğerdir.

**Kalıtımı unutmak.** Bir OU seviyesindeki tek bir hatalı ACE, altındaki tüm nesnelere miras yoluyla yayılır. Denetim yaparken sadece nesnenin doğrudan ACL'ine değil, miras alınan ACE'lere de bakılmalıdır.

**Servis hesaplarını görmezden gelmek.** Uygulama servis hesaplarına kurulum sırasında verilen geniş ACL'ler, yıllarca kimsenin dokunmadığı en verimli saldırı zinciri başlangıç noktalarıdır.

**Değişiklik denetimini kapalı bırakmak.** DACL ve ayrıcalıklı üyelik değişiklikleri denetlenmiyorsa, saldırganın attığı ACE'ler ve yaptığı temizlik tamamen görünmez kalır.

**BloodHound'u sadece kırmızı takıma bırakmak.** Bir sızma testinde bir kez çalıştırılıp raporlanan grafiği, tehdit sürekli evrildiği için değersizleşir. Attack path yönetimi sürekli bir süreç olmalıdır.

**AdminSDHolder'ı gözden kaçırmak.** Bu nesne üzerindeki hatalı bir ACE, tüm korunan gruplara otomatik yayıldığı için tek noktadan felakete yol açabilir.

## En İyi Pratikler

1. **Sürekli attack path yönetimi:** BloodHound tarzı analizi periyodik ve otomatik hale getirin. Yolları bulun, önceliklendirin (en çok yolun geçtiği darboğazlardan başlayın) ve kapatın.
2. **En küçük ayrıcalık ilkesini ACL'lere uygulayın:** Özellikle `GenericAll`, `WriteDACL`, `WriteOwner` gibi tehlikeli hakları yalnızca kesin gereken yerde ve mümkünse süreli olarak verin.
3. **Katmanlı yönetim (tiering):** Tier 0 varlıklarını mutlak olarak izole edin; alt katmanlardan Tier 0'a hiçbir ACL yolu kalmasın.
4. **Kritik nesneleri düzenli denetleyin:** domain kök nesnesi (DCSync hakları), `AdminSDHolder`, ayrıcalıklı gruplar, DC hesapları ve ayrıcalıklı OU'lar öncelikli denetim kapsamında olsun.
5. **Değişiklik tespitini açın:** DACL değişiklikleri, ayrıcalıklı grup üyeliği değişiklikleri ve replikasyon (DCSync) anomalileri için denetim ve alarm kurun. Olay kimliklerini kendi ortamınızda doğrulayarak yapılandırın.
6. **Delegasyon ve güven ilişkilerini sadeleştirin:** Gereksiz delegasyonları (özellikle unconstrained) ve eski güven ilişkilerini kaldırın.
7. **Servis hesabı hijyeni:** Servis hesaplarının ACL'lerini denetleyin, mümkünse gMSA (group Managed Service Accounts) gibi daha yönetilebilir yapılara geçin.
8. **Honeypot / honey-ACE kullanın:** Kimsenin meşru olarak dokunmaması gereken cazip ayrıcalıklı yollar bırakın; bunlara temas anında saldırganı erken yakalarsınız.

## Sonuç

AD ACL tabanlı saldırılar, bir yazılım açığından değil, birikmiş ve denetlenmemiş izinlerden doğar. Güçleri, tek başına zararsız görünen hakların bir zincir halinde birleşerek sıradan bir kullanıcıyı domain'in tepesine taşımasından gelir. `GenericAll`, `WriteDACL`, `WriteOwner`, `ForceChangePassword` gibi haklar bu zincirin halkalarıdır; DCSync ise sıklıkla nihai hedeftir. BloodHound, bu görünmez zinciri hem saldırgan hem savunmacı için görünür kılar ve tam da bu yüzden savunmanın en güçlü kozudur: Saldırganın grafiği çıkarabildiğini bilerek, savunmacı aynı grafiği önce çıkarır, darboğazları bulur ve yolları peşinen keser. AD güvenliğinde asıl mesele, tek tek izinleri değil, izinlerin oluşturduğu **yolları** yönetmektir.
