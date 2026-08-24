# DCSync ve DCShadow: Active Directory Replikasyonunun Silahlaştırılması

## Giriş ve Tanım

DCSync ve DCShadow, Active Directory (AD) ortamlarında saldırganların en tehlikeli sonraki adımlarından ikisidir. Her ikisi de ortak bir kök fikri sömürür: **Domain Controller'lar (DC) birbirleriyle sürekli veri replikasyonu yapar ve bu replikasyon, protokol seviyesinde "güvenilir" kabul edilir.** Saldırgan bu güveni istismar ederek, ya bir DC gibi *veri isteyerek* (DCSync) ya da bir DC gibi *veri yazarak* (DCShadow) domain'in kalbine ulaşır.

İki teknik arasındaki temel ayrım şudur:

- **DCSync** bir *okuma* saldırısıdır. Saldırgan, kendisini geçerli bir DC gibi gösterip diğer DC'lerden hesap parola hash'lerini (NTLM hash'i, Kerberos anahtarları, `krbtgt` hash'i dahil) çeker. Amaç kimlik bilgisi hırsızlığıdır (credential theft).
- **DCShadow** bir *yazma* saldırısıdır. Saldırgan sahte (rogue) bir DC kaydı oluşturup, kötü niyetli değişiklikleri (backdoor'lar, yetki yükseltme) meşru replikasyon trafiği üzerinden domain'e enjekte eder. Amaç kalıcılık (persistence) ve tespit atlatmadır.

Her ikisi de **Mimikatz** araç ailesi tarafından popülerleştirilmiştir; DCSync `lsadump::dcsync`, DCShadow ise `lsadump::dcshadow` modülü ile bilinir. Ancak bunlar bir "exploit" değildir — hiçbir yamayla kapanmazlar. Bunlar AD'nin *tasarlanmış* replikasyon davranışının meşru API'lerini kullanan istismarlardır. Bu yüzden savunma, yama değil, **yetki hijyeni ve davranış tespiti** üzerine kuruludur.

---

## Kök Neden: Replikasyon Neden Bu Kadar Güçlü?

Bir AD domain'inde birden fazla DC olduğunda, bunların veritabanı (`NTDS.dit`) senkron kalmalıdır. Bir kullanıcı parolasını A DC'sinde değiştirdiğinde, bu değişikliğin B ve C DC'lerine de yayılması gerekir. Bu senkronizasyonu sağlayan mekanizma **Directory Replication Service (DRS)** ve onun uzak protokolü **DRSUAPI**'dir (Directory Replication Service Remote Protocol, MS-DRSR).

Replikasyon sırasında DC'ler birbirlerinden `GetNCChanges` adlı bir RPC operasyonu ile "değişen naming context verilerini bana gönder" der. Kritik nokta şudur: **parola hash'leri de replike edilmesi gereken hassas niteliklerdir (attributes).** Yani DC'ler zaten normal işleyişte birbirlerine hash gönderir. Saldırgan yeni bir açık bulmaz; sadece *bu meşru konuşmaya kendini davet ettirir.*

Bunu mümkün kılan şey **yetki modelidir.** `GetNCChanges` çağrısını yapabilmek için çağıranın domain nesnesi üzerinde belirli genişletilmiş haklara (extended rights) sahip olması gerekir. Bunların başlıcaları:

- **DS-Replication-Get-Changes**
- **DS-Replication-Get-Changes-All** (parola hash'leri dahil tüm veriyi çekmek için gereken kritik hak)
- (DCShadow tarafında ek olarak) **DS-Replication-Get-Changes-In-Filtered-Set**

Varsayılan olarak bu haklar yalnızca **Domain Admins**, **Enterprise Admins**, **Administrators** ve **Domain Controllers** gruplarına verilmiştir. Sorun şu ki: bu ACL'ler domain kökündeki güvenlik tanımlayıcısında (security descriptor) durur ve zaman içinde **yanlış delegasyonlarla** başka principal'lere de sızabilir. İşte DCSync saldırısının gerçek zemini burasıdır — saldırgan bu hakları elde etmiş herhangi bir hesabı ele geçirdiğinde, DC olmaya gerek kalmadan tüm hash'leri çekebilir.

Buradaki kök neden özetle: **AD, "bir DC olduğunu iddia eden ama gerçekte DC olmayan" bir istemciyi protokol seviyesinde ayırt etmez.** Kimlik doğrulama, makinenin *gerçekten* DC olup olmadığına değil, çağıran principal'in *replikasyon hakkına sahip olup olmadığına* bakar. Bu, tasarımsal bir güven varsayımıdır ve tam da istismar edilen şeydir.

---

## DCSync: Nasıl Çalışır?

### Saldırının Mantığı

DCSync'in dehası şudur: saldırgan **hedef DC üzerinde kod çalıştırmak zorunda değildir.** Klasik `NTDS.dit` çalma yöntemlerinde (örneğin `ntdsutil` ile veritabanı dökümü ya da Volume Shadow Copy ile dosya kopyalama) saldırganın DC üzerinde bir shell'e ihtiyacı vardır ve bu, EDR ve olay günlükleri tarafından gürültülü şekilde yakalanır. DCSync ise **ağ üzerinden, uzaktan** çalışır: saldırgan kendi makinesinden (yeterli yetkiye sahip bir hesapla) hedef DC'ye bir replikasyon isteği gönderir ve DC hash'leri nazikçe geri döndürür.

Akış şöyledir:

1. Saldırgan, replikasyon haklarına sahip bir hesap ele geçirir (örneğin bir Domain Admin, ya da yanlışlıkla bu hakları almış bir servis hesabı).
2. Mimikatz ya da eşdeğeri, hedef DC'ye bir DRSUAPI bağlantısı açar ve `IDL_DRSGetNCChanges` operasyonunu çağırarak belirli bir kullanıcının (ör. `krbtgt` ya da `Administrator`) "değişikliklerini" ister.
3. DC, sanki karşısında meşru bir replikasyon partner'ı varmış gibi, o kullanıcının hassas nitelik verilerini — NTLM hash'i, LM hash'i (varsa), Kerberos anahtarları, parola geçmişi — geri gönderir.
4. Saldırgan bu hash'leri offline olarak kullanır.

### Neden `krbtgt` Kritik?

DCSync'in en yıkıcı hedefi `krbtgt` hesabıdır. Bu hesabın hash'i, domain'deki tüm Kerberos TGT (Ticket Granting Ticket) biletlerini imzalamak için kullanılır. Saldırgan `krbtgt` hash'ini DCSync ile çektiğinde, artık **Golden Ticket** üretebilir: istediği herhangi bir kullanıcı için, istediği grup üyelikleriyle, geçerli görünen Kerberos biletleri oluşturabilir. Bu, tüm domain'in tam ve neredeyse tespit edilemez ele geçirilmesi anlamına gelir. Bu yüzden DCSync genellikle Golden Ticket saldırısının bir ön adımıdır.

### Somut Örnek (kavramsal)

Kavramsal olarak saldırgan şuna benzer bir komut çalıştırır (Mimikatz sözdizimi, tam bayrak yazımı sürüme göre değişebilir):

```
lsadump::dcsync /domain:kurumsal.local /user:krbtgt
```

Burada saldırgan yalnızca domain adını ve hedef kullanıcıyı belirtir. Mimikatz gerisini — DC bulma, DRSUAPI çağrısı, hash ayrıştırma — otomatik halleder. `Impacket` paketindeki `secretsdump.py` aracı da aynı DCSync tekniğini "DRSUAPI metodu" ile Linux tarafından uygulayabilir; bu, kırmızı takımların ve saldırganların sık kullandığı çapraz-platform bir yoldur.

---

## DCShadow: Nasıl Çalışır?

### Saldırının Mantığı

DCShadow, DCSync'ten kavramsal olarak bir adım daha ileridedir ve daha sinsidir. DCSync veri *okurken*, DCShadow domain'e veri *yazar* — ama bunu meşru bir DC'nin yaptığı replikasyon push'u kılığında yapar.

Fikir şudur: Eğer saldırgan, AD'yi kendi kontrolündeki bir makinenin "geçici olarak bir DC" olduğuna ikna edebilirse, o makine üzerinden yaptığı değişiklikleri diğer gerçek DC'lere replike edebilir. Bu değişiklikler normal AD değişiklik günlüklerinden (ör. güvenlik olay günlüğü 4662, 5136 gibi) **kaçabilir**, çünkü değişiklik bir yönetim aracıyla değil, DC-to-DC replikasyonu üzerinden gelir ve replikasyon trafiği tipik denetim politikalarınca aynı ayrıntıda loglanmaz.

### Kök Neden ve Mekanik

DCShadow'un çalışması için saldırganın AD'de iki şeyi geçici olarak oluşturması gerekir:

1. **Configuration naming context içinde sahte bir "DC" nesnesi** — yani `nTDSDSA` nesnesi ve ilgili `Server` nesnesi. Bu, AD'nin o makineyi replikasyon topolojisinde bir partner olarak tanıması için gereklidir.
2. **SPN (Service Principal Name) kaydı** — özellikle DRS (Directory Replication Service) ve GC (Global Catalog) ile ilişkili SPN'ler — böylece Kerberos kimlik doğrulaması sırasında diğer DC'ler bu sahte makineye replikasyon için bağlanabilir.

Bunlar kurulduktan sonra saldırgan, hedef nesnede (ör. bir kullanıcı) değiştirmek istediği nitelikleri belirler ve ardından bir replikasyon tetikler (`DsReplicaAdd` benzeri çağrı ile "hey, benimle senkronize ol" der). Gerçek DC'ler sahte DC'ye bağlanıp değişen nitelikleri çeker ve kendi veritabanlarına yazar. Değişiklik yayıldıktan sonra saldırgan sahte DC nesnesini siler ve iz büyük ölçüde temizlenir.

Kritik gereksinim: **Bu işlemler için tipik olarak Domain Admin (ya da eşdeğeri) yetkisi gerekir**, çünkü Configuration partition'a yazmak ve DC nesneleri oluşturmak yüksek ayrıcalık ister. Bu nedenle DCShadow genellikle bir *ilk erişim* tekniği değil, zaten yüksek yetki elde etmiş bir saldırganın **kalıcılık ve gizlilik** aracıdır. Mimikatz'ın orijinal uygulamasında saldırı iki süreç ister: biri yüksek yetkiyle (SYSTEM) sahte DC'yi ayağa kaldırır (`/push`), diğeri değişiklikleri tanımlar.

### DCShadow ile Neler Yazılabilir? (İstismar Senaryoları)

DCShadow'un tehlikesi, *hangi* nitelikleri değiştirebildiğinde yatar. Tipik kötü niyetli kullanımlar:

- **`sIDHistory` enjeksiyonu**: Bir kullanıcının SID History'sine Enterprise Admins ya da Domain Admins SID'i eklenerek, o kullanıcı log'larda "normal kullanıcı" görünürken efektif olarak domain yöneticisi yapılır. Bu son derece sinsi bir yetki yükseltmedir.
- **`primaryGroupID` değiştirme**: Bir hesabın birincil grubunu değiştirerek grup üyeliği manipüle edilir.
- **AdminSDHolder / ACL manipülasyonu**: Nesne izinleri değiştirilerek kalıcı arka kapılar bırakılır.
- **`ntPwdHistory` / parola nitelikleri**: Belirli hesaplar için gizli kimlik bilgisi enjeksiyonu.

Bunların hepsinin ortak noktası: değişiklik "bir yönetici bir aracı açıp elle yaptı" gibi görünmez; "iki DC birbiriyle replike oldu" gibi görünür. Tespit atlatmanın özü budur.

---

## Sömürü ve Savunma: İki Tarafı Birlikte Görmek

Bir saldırının nasıl işlediğini anlamak, savunmasını tasarlamanın önkoşuludur. Aşağıda her iki teknik için istismar mantığını ve buna karşılık gelen savunmayı yan yana ele alıyorum.

### DCSync — İstismar vs. Savunma

**İstismar mantığı:** Saldırgan, `DS-Replication-Get-Changes-All` hakkına sahip bir principal'i ele geçirir ve uzaktan hash çeker. Saldırının en zayıf halkası, bu hakkı taşıyan hesabın *ele geçirilebilir* olmasıdır. Yani saldırı, aslında **yetki delegasyon hatalarının** bir semptomudur.

**Savunma:**

1. **Replikasyon haklarını denetle.** Domain kökündeki ACL'yi düzenli tara; `DS-Replication-Get-Changes-All` hakkının *yalnızca* DC'ler ve beklenen yüksek ayrıcalıklı gruplarda olduğundan emin ol. BloodHound gibi araçlar tam da bu "DCSync yapabilen" principal'leri (`GetChanges` + `GetChangesAll` kenarları) grafik üzerinde gösterir. Beklenmedik bir kullanıcı ya da servis hesabı bu hakka sahipse, bu doğrudan bir bulgu (finding) sayılmalıdır.
2. **Ağ seviyesinde tespit.** DCSync trafiği bir DRSUAPI `GetNCChanges` çağrısıdır. **DC olmayan bir kaynak IP'den gelen replikasyon isteği** neredeyse kesin bir alarmdır — çünkü meşru replikasyon yalnızca DC'ler arasında olur. IDS/network sensörleri ya da domain kontrolcü ağ segmentasyonu bunu yakalayabilir. Microsoft Defender for Identity (eski adıyla ATA/Azure ATP) bu davranışı özellikle "şüpheli replikasyon isteği" olarak tespit etmek üzere tasarlanmıştır.
3. **Olay günlükleri.** DC üzerinde denetim etkinse, replikasyon niteliklerine erişim **Event ID 4662** ile loglanabilir — özellikle replikasyon genişletilmiş haklarının GUID'lerine (`Replicating Directory Changes All` gibi) yapılan erişimler. Bunları bilinen DC hesaplarına göre filtreleyip anomalileri aramak güçlü bir tespit sağlar.
4. **`krbtgt` rotasyonu.** Bir DCSync şüphesi ya da ihlali sonrası `krbtgt` parolasını **iki kez** (aradaki replikasyon tamamlanma süresini bekleyerek) döndürmek, çalınmış hash ile üretilebilecek Golden Ticket'ları geçersiz kılar. Bu, düzenli bir hijyen adımı olarak da uygulanmalıdır.

### DCShadow — İstismar vs. Savunma

**İstismar mantığı:** Saldırgan zaten yüksek yetkilidir ve tespit atlatarak kalıcı olmak ister. Saldırının imzası, **Configuration partition'da geçici olarak beliren sahte bir DC nesnesi** ve **anormal replikasyon push'larıdır.**

**Savunma:**

1. **Configuration partition değişikliklerini izle.** `nTDSDSA` nesnelerinin oluşturulması/silinmesi son derece nadir ve yönetimsel olarak planlı bir olaydır. `CN=Sites,CN=Configuration` altında beklenmedik `Server`/`nTDSDSA` nesnesi belirmesi güçlü bir DCShadow göstergesidir. Bu değişiklikler **Event ID 5137 (nesne oluşturma)** ve ilgili dizin servisi denetim olaylarıyla yakalanabilir.
2. **Yetkili DC listesini bir "allowlist" olarak tut.** Ortamdaki gerçek DC'lerin sayısı ve kimliği bilinir ve nadiren değişir. Replikasyon yapan kaynakları bu bilinen listeyle karşılaştır; listede olmayan bir "DC"den gelen replikasyon push'u alarm olmalıdır.
3. **RPC/SPN anomalileri.** DCShadow, sahte makineye DRS/GC SPN'leri ekler. `servicePrincipalName` niteliğine bir bilgisayar hesabına DRS SPN eklenmesi gibi olaylar izlenmelidir.
4. **En temel savunma: yetkiyi kısıtla.** DCShadow Domain Admin gerektirdiğinden, gerçek koruma **Tier 0 izolasyonu** ile başlar. Eğer saldırgan zaten Domain Admin ise, DCShadow onun elindeki araçlardan yalnızca biridir; asıl mesele o yetkiye ilk etapta ulaşmasını engellemektir.

Burada önemli bir dürüstlük notu: DCShadow "önlenebilir bir güvenlik açığı" değildir; meşru bir AD özelliğinin kötüye kullanımıdır. Bu yüzden onu tamamen "engellemek" yerine, **tespit edilebilir kılmak** ve **ona ulaşmak için gereken yetkiyi korumak** gerçekçi hedeflerdir.

---

## Yaygın Hatalar

Sahada tekrar tekrar görülen ve bu saldırıları mümkün kılan ya da tespitini kaçıran hatalar:

- **Replikasyon haklarının farkında olmadan delege edilmesi.** En sık kök neden budur. Bir yazılım kurulumu, bir Exchange/Azure AD Connect entegrasyonu ya da bir "geçici" yönetim ihtiyacı, bir servis hesabına `DS-Replication-Get-Changes-All` hakkını verir ve bu asla geri alınmaz. Saldırgan o servis hesabını ele geçirdiğinde DCSync bedava gelir. **Azure AD Connect senkronizasyon hesabı** meşru olarak bu hakka sahip olabilir — bu yüzden o hesabın korunması kritiktir; onu ele geçirmek DCSync yapabilmek demektir.

- **"DCSync bir exploit, yamalarım korur" yanılgısı.** Bu bir yamayla kapanmaz. Yama beklentisi, yanlış bir güvenlik hissi yaratır. Kontrol ACL hijyeni ve tespittir.

- **Yalnızca DC'lerde değil, tüm ayrıcalıklı hesaplarda log'a bakmak gerektiğini unutmak.** DCSync uzaktan çalışır; DC'nin *kendi* logunda çağrıyı görürsünüz ama çağıran hesap başka bir yerden gelir. Sadece endpoint EDR'a güvenmek yetmez.

- **Denetim politikasının replikasyon olaylarını kapsamaması.** Event ID 4662 gibi olaylar için "Directory Service Access" denetimi ve doğru SACL'ler yapılandırılmamışsa, DCSync sessizce gerçekleşir. Birçok kurumda bu denetim varsayılan olarak yeterli ayrıntıda değildir.

- **`krbtgt`'yi hiç döndürmemek ya da yalnızca bir kez döndürmek.** İki DC arasındaki replikasyon nedeniyle, güvenli rotasyon iki adımlıdır. Tek rotasyon, eski hash'in geçerli kalmasına yol açabilir.

- **DCShadow'u "imkânsız" sanmak çünkü Domain Admin gerekir.** Domain Admin'e ulaşmak, olgun bir saldırı zincirinde beklenen bir aşamadır (kimlik avı → yanal hareket → yetki yükseltme). DA'yı elde eden saldırgan için DCShadow, tespit atlatmalı kalıcılığın en temiz yollarından biridir; bu yüzden Tier 0 izlemesi ihmal edilmemelidir.

---

## En İyi Pratikler

Bu iki tekniğe karşı savunmayı olgunlaştırmak için önceliklendirilmiş bir yol haritası:

**1. Tier 0 / ayrıcalıklı erişim modeli uygula.** DC'ler, Domain/Enterprise Admin hesapları ve AD'yi yöneten her şey Tier 0'dır. Bu hesaplar yalnızca güvenli, ayrılmış yönetim iş istasyonlarından (PAW — Privileged Access Workstation) kullanılmalı; günlük iş makinelerinde asla oturum açmamalıdır. DCSync ve DCShadow'un her ikisi de yüksek yetkiye dayandığından, en etkili savunma bu yetkiye erişimi daraltmaktır.

**2. Replikasyon hakları ACL'lerini periyodik denetle ve azalt.** Domain kökündeki güvenlik tanımlayıcısını düzenli tarayarak `Get-Changes` / `Get-Changes-All` haklarını taşıyan tüm principal'leri listele. Beklenmeyen her giriş bir bulgudur. BloodHound ile "kim DCSync yapabilir" sorusunu grafik olarak yanıtla ve saldırı yollarını kapat.

**3. Kimlik odaklı tespit dağıt.** Microsoft Defender for Identity ya da eşdeğeri bir çözüm, hem "DC olmayan kaynaktan replikasyon isteği" (DCSync) hem de "sahte DC" (DCShadow) davranışlarını protokol seviyesinde tespit edecek şekilde tasarlanmıştır. Bu tür bir sensör, DC'lerin ağ trafiğini görebildiği bir konumda konuşlandırılmalıdır.

**4. Denetim ve loglamayı doğru yapılandır.** "Audit Directory Service Access" ve "Audit Directory Service Changes" politikalarını etkinleştir; replikasyon genişletilmiş haklarının GUID'lerine erişimin Event ID 4662 ile, Configuration partition nesne oluşturmalarının 5137 ile yakalandığından emin ol. Bu olayları merkezi bir SIEM'e yollayıp DC-dışı kaynak ve nadir Configuration değişiklikleri için korelasyon kuralları yaz.

**5. `krbtgt` için düzenli, iki adımlı rotasyon.** Planlı bir hijyen olarak (ör. periyodik) ve her ihlal şüphesinde `krbtgt` parolasını, replikasyon tamamlanma süresini bekleyerek iki kez döndür. Microsoft'un yayımladığı `krbtgt` sıfırlama betiği bu iki adımlı süreci güvenli yönetmek için kullanılabilir.

**6. Ağ segmentasyonu ve replikasyonu DC'lere kısıtla.** DC'ler arası replikasyon trafiğini (RPC/DRSUAPI) yalnızca bilinen DC IP'leri arasında olacak şekilde ağ seviyesinde daralt. Bir istemci makinesinin bir DC'ye replikasyon isteği göndermesi normal ağ akışında hiçbir zaman olmamalıdır; bu akışı kısıtlamak ya da en azından alarm üretecek şekilde izlemek DCSync'i hem zorlaştırır hem de gürültülü hale getirir.

**7. Azure AD Connect / dizin senkronizasyon hesaplarını Tier 0 gibi koru.** Bu hesaplar meşru replikasyon haklarına sahip olabilir; ele geçirilmeleri doğrudan DCSync yeteneği verir. Parolalarını güçlü tut, ayrıcalıklarını en aza indir, üzerlerinde MFA ve sıkı erişim kontrolü uygula.

---

## Sonuç

DCSync ve DCShadow'un ortak dersi şudur: **Active Directory'de en tehlikeli saldırılar bir yazılım açığından değil, meşru mekanizmaların ve gevşek yetki modellerinin kötüye kullanımından doğar.** DCSync, replikasyon hakkını ele geçirip uzaktan tüm hash'leri (özellikle `krbtgt`'yi) çeker ve Golden Ticket'a zemin hazırlar. DCShadow ise sahte bir DC kurup domain'e tespit edilmesi zor kötü niyetli değişiklikler yazarak kalıcılık sağlar.

Her ikisine karşı da savunmanın çekirdeği yama değil, **yetki hijyeni (kimin replikasyon hakkı var?), izolasyon (Tier 0) ve davranışsal tespittir (DC-dışı replikasyon ve sahte DC nesneleri).** Bu üç ayağı sağlam kuran bir kurum, bu tekniklerin her ikisini de ya baştan zorlaştırır ya da gerçekleştikleri anda görünür kılar.
