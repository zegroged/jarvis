# Kerberoasting — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin Kerberoasting saldırısını önce kavramsal olarak anlamayı, sonra onu üreten log izlerini ve tespit mantığını kurmayı hedefler. Amaç savunma ve tespittir; canlı bir saldırı reçetesi değildir.

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Kerberoasting, Active Directory'nin Kerberos kimlik doğrulama protokolündeki **tasarımsal bir davranışı** istismar eder — bir zafiyet ya da yama eksikliği değil, protokolün normal işleyişini. Bu yüzden tespiti zorlaştıran şey de tam olarak budur: saldırı, meşru trafikle aynı boruların içinden akar.

Temeli anlamak için Kerberos'un servis bileti (TGS, Ticket Granting Service ticket) mantığını hatırlamak gerekir. Bir kullanıcı, bir servise (örneğin bir SQL Server, bir web uygulaması, bir dosya paylaşımı) erişmek istediğinde, Domain Controller'daki KDC'den (Key Distribution Center) o servise ait bir TGS bileti ister. Bu bilet, **servis hesabının parola özetinden (NTLM hash) türetilen bir anahtarla şifrelenir**. Mantık şudur: sadece o servis hesabının parolasını bilen taraf bileti çözebilir, dolayısıyla bilet kimlik kanıtı olarak iş görür.

Kritik nokta burada: KDC, TGS biletini vermeden önce kullanıcının o servise gerçekten erişim yetkisi olup olmadığını **kontrol etmez**. Domain'de kimliği doğrulanmış herhangi bir kullanıcı, herhangi bir **SPN (Service Principal Name)** kaydı olan hesap için TGS bileti isteyebilir. Ve o bilet, hedef servis hesabının parola özetiyle şifrelenmiş olarak kullanıcıya geri döner.

Saldırganın istismar ettiği zincir şu kavramsal adımlarla özetlenebilir:

- **Keşif:** Saldırgan, domain'de SPN'e sahip kullanıcı hesaplarını arar. Bilgisayar hesapları (sonu `$` ile biten) da SPN'e sahiptir ama onların parolaları makine tarafından otomatik üretilir, 120 karakter uzunluğunda ve rastgeledir — kırılamaz. Asıl hedef, bir insan ya da yönetici tarafından zayıf bir parola atanmış **servis kullanıcı hesaplarıdır** (örneğin `svc_sql`, `svc_backup`). Bu hesaplar çoğu zaman yüksek ayrıcalıklara sahiptir ve parolaları nadiren değişir.
- **Bilet talebi:** Saldırgan, seçtiği SPN'ler için KDC'den TGS bileti ister. Bu tamamen meşru bir Kerberos işlemidir; hiçbir alarm gerektirmeyen sıradan bir protokol akışıdır.
- **Şifrelemeyi düşürme:** Saldırgan mümkünse biletin **RC4-HMAC (etype 0x17 / 23)** ile şifrelenmesini tercih eder. RC4, servis hesabının NTLM hash'ini doğrudan anahtar olarak kullanır ve tuz (salt) ya da yavaşlatıcı iterasyon içermez; bu da offline kırmayı çok hızlandırır. AES (etype 17/18) çok daha dirençlidir.
- **Offline kırma:** Elde edilen şifreli bilet parçası domain dışına çıkarılır. Saldırgan kendi makinesinde, Domain Controller'a hiç dokunmadan, milyonlarca parola denemesiyle bileti çözmeye çalışır. Bilet çözülürse servis hesabının **açık parolası** ele geçer.

Bu tekniğin sinsiliği şurada: talep aşaması ağda görünür ama kırma aşaması **tamamen offline ve görünmezdir**. Savunmacının yakalayabileceği tek an, bilet talebinin kendisidir. Bu yüzden tespit tamamen "anormal TGS talebi" davranışına odaklanır. MITRE ATT&CK çerçevesinde bu teknik **T1558.003 (Kerberoasting)** olarak sınıflandırılır ve Credential Access taktiğine aittir.

Kavramsal olarak bir başka önemli ayrıntı: saldırgan bu saldırıyı gerçekleştirmek için **yönetici olmaya gerek duymaz**. Domain'de geçerli, kimliği doğrulanmış herhangi bir düşük ayrıcalıklı kullanıcı hesabı yeterlidir. Bu, Kerberoasting'i post-exploitation aşamasında son derece cazip kılar: saldırgan bir kez herhangi bir kullanıcı olarak ayak bastığında, hiçbir ek ayrıcalık yükseltmeye ihtiyaç duymadan, domain'deki tüm servis hesaplarının parola özetlerini toplamayı deneyebilir. Elde edilen parolalardan biri yüksek ayrıcalıklı bir hesaba aitse (ki servis hesapları sıklıkla Domain Admin ya da benzeri gruplara üyedir), saldırgan bir anda yatay hareketten dikey ayrıcalık yükseltmeye geçer. İşte bu yüzden Kerberoasting, "düşük gürültü, yüksek getiri" profiliyle gerçek saldırılarda ve fidye yazılımı kampanyalarında (örneğin Conti gibi gruplarca) çok yaygın kullanılır.

Son bir kavramsal nüans: saldırının başarısı tamamen **hedef servis hesabının parola kalitesine** bağlıdır. Uzun, karmaşık, rastgele parolaya sahip bir hesabın bileti kırılamaz — saldırgan bileti alır ama offline kırma başarısız olur. Bu yüzden Kerberoasting aslında zayıf parola hijyeninin bir sonucudur; teknik, kötü parolaları görünür kılan bir "hasat" mekanizmasıdır. Tespit tarafında bu şunu ima eder: saldırgan talebi yaptığı anda henüz parolanın kırılıp kırılmayacağını bilmez, dolayısıyla **geniş bir hasat** yapma eğilimindedir — ve bu geniş hasat davranışı tespit için altın değerinde bir sinyaldir.

## 2. Bıraktığı izler / artefaktlar

Kerberoasting'in bıraktığı izler üç katmanda toplanır: Domain Controller güvenlik günlükleri, ağ trafiği ve saldırgan aracının çalıştığı endpoint'teki süreç izleri.

**Domain Controller — Kerberos servis bileti günlükleri.** En değerli iz, Domain Controller'ların Security event log'unda üretilen **Event ID 4769 (A Kerberos service ticket was requested)** kayıtlarıdır. Her TGS talebi bir 4769 üretir. Bu olayın içinde tespit için kritik alanlar bulunur:

- `Service Name` — talep edilen SPN'in bağlı olduğu hesap adı. Kerberoasting'de bunlar bilgisayar hesapları değil, insan/servis kullanıcı hesaplarıdır.
- `Ticket Encryption Type` — biletin şifreleme türü. RC4 için değer **0x17** (onlu 23) görünür; AES-256 için **0x12** (18), AES-128 için **0x11** (17). Bir domain modern yapılandırılmışsa AES beklenirken aniden çok sayıda **0x17** görülmesi güçlü bir sinyaldir.
- `Ticket Options` — bilet bayrakları.
- `Client Address` — talebi yapan istemcinin IP adresi.
- `Failure Code / Account Name` — talebi yapan hesap.

Not: Windows'ta 4769'un varsayılan olarak loglanması için **"Audit Kerberos Service Ticket Operations"** denetim politikasının Domain Controller'larda etkin olması gerekir. Bu tespitin ön koşuludur.

**Ağ trafiği — Zeek/Bro Kerberos logları.** Ağ seviyesinde, KDC ile istemci arasındaki Kerberos protokol alışverişi izlenebilir. Zeek'in `kerberos.log`'u her TGS/AS işlemini `request_type` (örn. `TGS`), `cipher` (örn. `rc4-hmac`), `service`, `client` gibi alanlarla kaydeder. Bu, verilen gerçek Sigma kuralının (`Kerberos Network Traffic RC4 Ticket Encryption`) demirlendiği kaynaktır: `request_type: 'TGS'` ve `cipher: 'rc4-hmac'` kombinasyonu, RC4 ile şifrelenmiş servis biletlerini yakalar.

**Endpoint — saldırgan araçlarının süreç izleri.** Kerberoasting genellikle bilinen araçlarla yürütülür ve bu araçlar endpoint'te **process_creation** (Sysmon Event ID 1 ya da Windows 4688) izleri bırakır:

- **Rubeus** — `Rubeus.exe kerberoast`, `asreproast`, `dump /service:krbtgt` gibi komut satırı desenleri. Aracın `OriginalFileName` ve `Description` PE alanları `Rubeus` içerir.
- **PowerShell / Empire / PowerSploit** — `Invoke-Kerberoast` cmdlet'i. Bazen operatörün Cobalt Strike beacon konsolu yerine yanlışlıkla normal `cmd.exe`'ye komut girmesiyle bu komut satırında görünür ("operator blooper").
- **SharpView / PowerView** — SPN keşfi ve domain recon için kullanılır; doğrudan kerberoasting değildir ama sık sık öncülüdür.
- **`System.IdentityModel.Tokens.KerberosRequestorSecurityToken`** — PowerShell içinden bu .NET sınıfının kullanımı, harici araç olmadan tek satırla TGS bileti istemenin "living off the land" yoludur. Komut satırında bu sınıf adının geçmesi güçlü bir işarettir.

Ek olarak, kırılmış bilet dosyaları (`.kirbi`) ya da hashcat/John girdisi olarak diske yazılan hash dosyaları, endpoint forensiğinde ikincil artefakt olabilir.

**LDAP keşif izleri.** Kerberoasting'in bilet talebi aşamasından önce neredeyse her zaman bir **SPN keşfi** gelir. Saldırgan, hangi kullanıcı hesaplarının SPN'e sahip olduğunu öğrenmek için Domain Controller'a bir LDAP sorgusu gönderir; tipik filtre `(&(samAccountType=805306368)(servicePrincipalName=*))` biçimindedir — yani "SPN'i olan tüm kullanıcı hesapları". Bu sorgu, DC'de **Event ID 1644** (LDAP sorgu tanılama, ayrıca etkinleştirilmesi gerekir) ya da ağ tarafında Zeek LDAP loglarında görünebilir. Bu keşif izi, bilet talebiyle korele edildiğinde tespit güvenilirliğini ciddi biçimde artırır: önce toplu SPN sorgusu, hemen ardından o SPN'ler için RC4 bilet talepleri klasik bir Kerberoasting zinciridir.

**BloodHound / SharpHound toplama.** Modern saldırganlar SPN'li hesapları ve bunların ayrıcalık ilişkilerini haritalamak için BloodHound veri toplayıcısı SharpHound'u kullanır. Bu araç yoğun LDAP trafiği ve karakteristik process_creation izleri bırakır; Kerberoasting'in sık görülen bir öncülüdür.

**Şüpheli süreç soyağacı (parent-child).** Kerberoasting araçları çoğu zaman beklenmedik bir ebeveyn süreçten doğar — örneğin `w3wp.exe`, `services.exe` ya da bir Office uygulamasından türeyen bir PowerShell. `ParentImage` alanının bu tür anormal değerleri, komut satırı desenleriyle birlikte değerlendirildiğinde ek bir tespit boyutu sağlar.

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Tespit stratejisi iki bağımsız görüş açısını birleştirir: **davranış (anormal bilet talebi)** ve **araç (bilinen hacktool imzaları)**. İkisi birbirini tamamlar çünkü davranış tespiti aracı bilinmese de çalışır, araç tespiti ise davranış meşru trafiğe gömülü olsa da yakalar.

### 3.1 Ağ katmanı — RC4 servis bileti (Zeek kerberos)

Verilen `Kerberos Network Traffic RC4 Ticket Encryption` kuralının mantığı şudur: `logsource` olarak Zeek `kerberos` servisi kullanılır. `selection` bölümü iki koşul arar — `request_type` alanı `'TGS'` ve `cipher` alanı `'rc4-hmac'`. Yani "RC4 ile şifrelenmiş bir servis bileti talebi". Ancak burada kritik bir **filtreleme** vardır: `computer_acct` koşulu, `service` alanı `$` ile başlayan (yani bilgisayar hesabına ait) talepleri ayıklar. Nihai koşul `selection and not computer_acct` olduğu için, kural yalnızca RC4 ile şifrelenmiş ve **bir kullanıcı hesabına** ait servis biletlerine alarm verir. Bu tam olarak Kerberoasting'in imzasıdır: bilgisayar hesapları için RC4 normaldir (ve onlar kırılamaz), tehlike insan/servis hesaplarındadır. Kural seviyesi `medium`'dur çünkü meşru eski uygulamalar da RC4 kullanabilir.

### 3.2 Endpoint katmanı — Rubeus ve araç imzaları

`HackTool - Rubeus Execution` kuralı, `process_creation` / Windows logsource üzerinde çalışır ve şu alanlardan **herhangi biri** eşleşirse tetiklenir: `Image` alanı `\Rubeus.exe` ile bitiyor, ya da `OriginalFileName` `Rubeus.exe`, ya da PE `Description` alanı `Rubeus`, ya da `CommandLine` içinde `kerberoast `, `asreproast `, `dump /service:krbtgt `, `dump /luid:0x`, `ptt` gibi karakteristik argümanlar geçiyor. Argüman tabanlı eşleşme özellikle değerlidir çünkü saldırgan `Rubeus.exe` dosyasını yeniden adlandırsa bile komut satırındaki `kerberoast` gibi argümanları değiştiremez. Bu kural `stable` durumdadır, yani düşük yanlış pozitifle güvenilir kabul edilir.

Benzer şekilde `Operator Bloopers Cobalt Strike Modules` kuralı, `cmd.exe` süreç oluşturma olaylarında `CommandLine` içinde `Invoke-Kerberoast` (ve `Invoke-UserHunter`, `Invoke-ShareFinder` gibi diğer offensive PowerShell modülleri) geçmesini arar. Mantık: bu cmdlet'ler normal bir CMD kabuğunda asla çalışmaz — görülmesi operatörün beacon yerine yanlış konsola komut girdiğini gösterir.

`Suspicious Kerberos Ticket Request via CLI` kuralı ise araçsız yaklaşımı hedefler: komut satırında `System.IdentityModel.Tokens.KerberosRequestorSecurityToken` sınıfının çağrılmasını arayarak, PowerShell ile doğrudan TGS bileti talebini yakalar. Bu, Kerberoasting'in "living off the land" varyantına karşı gerekli bir kapsama sağlar.

### 3.3 Basit Sigma-benzeri tespit mantığı örnekleri

**Örnek A — DC üzerinde RC4 servis bileti anomalisi (Event ID 4769 tabanlı):**

```yaml
title: Kerberoasting - RC4 TGS Talebi (Kullanici Hesabi)
logsource:
    product: windows
    service: security
detection:
    selection:
        EventID: 4769
        TicketEncryptionType: '0x17'   # RC4-HMAC
    filter_computer:
        ServiceName|endswith: '$'       # bilgisayar hesaplarini ele
    filter_krbtgt:
        ServiceName: 'krbtgt'
    condition: selection and not filter_computer and not filter_krbtgt
level: medium
```

Mantık: 4769 olaylarından yalnızca RC4 (`0x17`) ile şifrelenmiş ve bir bilgisayar hesabına (`$` ile biten) ya da `krbtgt` hizmetine ait olmayanları seçer. Bu, ağ kuralının Windows Security log karşılığıdır. `krbtgt` filtresi eklenir çünkü o normal TGT trafiğidir.

**Örnek B — Eşik/frekans tabanlı toplu talep tespiti:**

```yaml
title: Kerberoasting - Tek Kaynaktan Toplu SPN Talebi
logsource:
    product: windows
    service: security
detection:
    selection:
        EventID: 4769
        TicketEncryptionType: '0x17'
    timeframe: 10m
    condition: selection | count(ServiceName) by AccountName > 10
level: high
```

Mantık: Tek bir hesabın (`AccountName`) 10 dakika içinde 10'dan fazla farklı SPN için RC4 bileti istemesi, tekil bir RC4 talebinden çok daha güçlü bir sinyaldir. Meşru bir kullanıcı kısa sürede onlarca farklı servise erişmez; toplu SPN keşfi + toplu talep Kerberoasting davranışının kalbidir. Eşik tabanlı yaklaşım tekil RC4 gürültüsünü büyük ölçüde bastırır ve bu yüzden `high` seviyesindedir.

Bu iki örnekte de kullanılan alan adları (`EventID` 4769, `TicketEncryptionType`, `ServiceName`, `AccountName`) gerçek Windows Security log şemasından gelir; uydurma değildir.

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırganın kaçınma teknikleri ve savunmacı yanıtı

**AES bileti isteme.** En etkili kaçınma, RC4 yerine **AES şifreli bilet** istemektir. Böylece `cipher: rc4-hmac` ve `TicketEncryptionType: 0x17` tabanlı tüm kurallar sessiz kalır. Ancak bunun bir bedeli var: AES bileti offline kırmak katbekat yavaştır, dolayısıyla saldırgan ancak servis parolası gerçekten zayıfsa başarılı olur.
*Savunmacı yanıtı:* Şifreleme türüne bakan kurallara **güvenip durmayın**; bunları frekans/davranış tespitiyle (Örnek B) katmanlayın. Ayrıca, ortamınızda hâlâ RC4'e izin verilmesinin başlı başına bir zayıflık olduğunu unutmayın — mümkünse hesap düzeyinde AES'i zorunlu kılmak (msDS-SupportedEncryptionTypes) hem saldırıyı zorlaştırır hem de RC4 gürültüsünü azaltıp RC4 alarmını daha anlamlı hale getirir.

**Yavaş ve dağıtık talep (low-and-slow).** Saldırgan, eşik kurallarını atlatmak için SPN taleplerini saatlere/günlere yayabilir ve birden çok hesaptan gerçekleştirebilir.
*Savunmacı yanıtı:* Eşik penceresini kısa tutmanın yanı sıra, uzun dönemli **baseline** (temel davranış) analizi kullanın: bir kullanıcının geçmişte hiç talep etmediği SPN'ler için ilk kez bilet istemesi, düşük hacimde bile şüphelidir. UEBA/anomali skorlaması bu tür yavaş kampanyaları yakalar.

**Araç yeniden adlandırma ve in-memory çalıştırma.** `Rubeus.exe` yeniden adlandırılabilir ya da bellekte reflective olarak yüklenip diske hiç yazılmayabilir; bu, `Image|endswith` eşleşmesini boşa çıkarır.
*Savunmacı yanıtı:* Rubeus kuralının **CommandLine argümanı** (`kerberoast `, `asreproast `) ve PE `OriginalFileName`/`Description` eşleşme dallarına güvenin — bunlar yeniden adlandırmaya dayanıklıdır. Bellekte çalıştırma için ise PowerShell Script Block Logging (Event ID 4104) ve AMSI telemetrisi ekleyin; `Invoke-Kerberoast` ve `KerberosRequestorSecurityToken` bu katmanda yakalanır. Endpoint tespitini asla tek başına DC/ağ tespitinin yerine koymayın — üçünü birlikte kullanın.

**Honeypot / decoy SPN.** Aktif savunma tarafında güçlü bir teknik: kasıtlı olarak cazip görünen (örneğin `svc_sqladmin`), yüksek ayrıcalıklı görünümlü ama **hiçbir servis tarafından kullanılmayan** bir tuzak hesap oluşturmak. Meşru hiçbir istemci bu SPN için bilet istemez; dolayısıyla bu hesap için gelen **herhangi bir** 4769 talebi neredeyse kesin kötü niyetlidir. Bu, false positive'i sıfıra yakın bir yüksek güvenilirlikli tetikleyici sağlar.

### 4.2 Tipik false positive kaynakları ve ayıklama

Verilen kuralların da `falsepositives` bölümünde belirttiği gibi ("Normal enterprise SPN requests activity"), Kerberoasting tespiti gürültüye açıktır. Başlıca yanlış pozitif kaynakları:

- **Eski/uyumsuz uygulamalar.** Bazı eski servisler ya da üçüncü parti ürünler hâlâ RC4 talep eder. Bunlar sürekli `0x17` üretir. *Ayıklama:* Bu servis hesaplarını ve istemci IP'lerini bir allowlist'e alın; ya da uzun vadede AES'e geçirin. Kaynağı bilinen, sabit ve tekrarlayan RC4 trafiğini baseline'a dahil edin.
- **Yasal güvenlik tarama araçları.** Şirket içi pentest, kırmızı takım tatbikatları ve otomatik AD hijyen tarayıcıları (BloodHound toplama dahil) gerçek Kerberoasting davranışını taklit eder. *Ayıklama:* Bilinen tarama pencerelerini ve tarayıcı kaynak host'larını istisna listesine ekleyin; tatbikat takvimiyle korelasyon kurun.
- **Vulnerability scanner / envanter araçları.** Bazı araçlar geniş SPN keşfi ve bilet talebi yapar. Kaynak host'a göre ayıklanır.
- **Meşru yoğun kullanıcılar.** Çok sayıda backend servise bağlanan uygulama sunucuları ya da yönetici iş istasyonları kısa sürede birçok TGS üretebilir ve eşik kuralını tetikleyebilir. *Ayıklama:* Bu host/hesapları kimlik bazında baseline'layın; eşiği bu bilinen davranışın üstüne kalibre edin, aynı istemci için sürekli aynı SPN kümesini normal sayın.

Genel ayıklama prensibi: **tekil sinyale değil, sinyal birleşimine güvenin.** Tek başına bir RC4 4769 zayıf kanıttır; ama "beklenmedik bir kaynak host + kısa sürede çok sayıda farklı kullanıcı-SPN'i + RC4 + daha önce hiç görülmemiş talep deseni" birleşimi yüksek güvenilirlikli bir Kerberoasting alarmıdır. Tespit mühendisliğinde hedef, RC4'e alarm vermek değil, **anormal RC4'e** alarm vermektir; normalin ne olduğunu bilmek (baseline) tespitin yarısıdır.

### 4.3 Tespiti güçlendiren yapılandırma önlemleri

Tespitin işe yaraması için bazı ön koşullar sağlanmalıdır: Domain Controller'larda "Audit Kerberos Service Ticket Operations" politikasının etkin olması (4769 için), PowerShell Script Block Logging'in açık olması (in-memory araçlar için) ve mümkünse Sysmon ile zenginleştirilmiş `process_creation` telemetrisi. Ayrıca servis hesaplarına **gMSA (group Managed Service Accounts)** kullanmak, parolayı otomatik, uzun ve rastgele yaparak biletin kırılmasını pratikte imkânsız hale getirir — bu, tespitten önce gelen en güçlü önleyici kontroldür. Tespit, önleme başarısız olduğunda devreye giren ikinci savunma hattıdır; ikisi birlikte katmanlı savunmayı oluşturur.
