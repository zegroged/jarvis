# Windows Access Token / Privilege Manipulation (SeDebugPrivilege, SeImpersonate, JuicyPotato Ailesi)

## Neden Bu Konu Ayrı Ele Alınmalı

Windows privilege escalation (privesc) eğitimlerinde genellikle "yanlış yapılandırılmış servis," "zayıf dosya izni," "unquoted service path" gibi başlıklar öne çıkar. Ancak gerçek dünyada, özellikle kurumsal ortamlarda ve CTF/red team senaryolarında en sık karşılaşılan ve en "güvenilir" çalışan yükseltme teknikleri, **access token** ve **privilege** mekanizmasının istismarından geçer. Token impersonation, "potato" saldırıları (JuicyPotato, RoguePotato, PrintSpoofer, GodPotato, vb.) ve named pipe impersonation, IIS/SQL Server/servis hesapları gibi "network service" veya "local service" ayrıcalığında çalışan ama yüksek privilege token'lara sahip hesapların SYSTEM'e dönüşmesini sağlar. Bu teknikler o kadar tekrarlayan bir kalıp oluşturur ki, ayrı ve derinlemesine anlaşılmadan "Windows privesc" konusu eksik kalır. Bu makale mekanizmayı kavramsal olarak açar; amaç saldırı script'i üretmek değil, savunma ekibinin NEDEN bu ayrıcalıkların tehlikeli olduğunu ve NASIL tespit edileceğini anlamasıdır.

## Temel Kavram: Windows Access Token Nedir

Windows'ta bir process veya thread "kim olarak" çalıştığını bir **access token** ile taşır. Token, kullanıcının SID'ini (Security Identifier), grup üyeliklerini, ve en önemlisi **privilege** listesini içerir (örnek: SeDebugPrivilege, SeImpersonatePrivilege, SeAssignPrimaryTokenPrivilege, SeBackupPrivilege, SeLoadDriverPrivilege gibi özel yetkiler). Bu privilege'lar, normal DACL (discretionary access control list) tabanlı izin kontrolünün ÜZERİNDE çalışan, kernel seviyesinde tanımlanmış özel yetkilerdir.

İki temel token türü vardır:

- **Primary token**: Bir process başlatıldığında o process'e atanan token. Process'in "kim olduğunu" tanımlar.
- **Impersonation token**: Bir thread'in, başka bir security context'i (genellikle bir client'in context'ini) GEÇİCİ olarak "taklit etmesini" (impersonate) sağlayan token. Bu, özellikle client-server iletişiminde (named pipes, RPC) "sunucunun, çağıranı adına işlem yapması" için tasarlanmıştır.

Impersonation token'ın kendi içinde 4 seviyesi vardır (SecurityImpersonationLevel): Anonymous, Identification, Impersonation, Delegation. Saldırıların çoğu, sunucunun client'i **Impersonation** seviyesinde temsil etmesine izin veren SeImpersonatePrivilege'i hedef alır; bu seviye, sunucunun client'in yerel makinedeki tüm yetkilerini kullanabilmesini sağlar (ağ üzerinden delegation olmadan).

## Kök Neden / Çalışma Mantığı: Neden Bu Ayrıcalıklar Tehlikeli

### SeDebugPrivilege

Bu privilege, sahibinin **herhangi bir process'in bellek alanına** (SYSTEM process'leri dahil) erişip debug edebilmesini sağlar. Normalde debugger'ların (WinDbg gibi) ihtiyaç duyduğu bu yetki, admin/SYSTEM hesaplarına varsayılan olarak atanır.

**Neden tehlikeli**: SeDebugPrivilege'e sahip bir process, `OpenProcess()` çağrısını DACL kontrolünü bypass ederek herhangi bir process üzerinde (örneğin `lsass.exe` veya SYSTEM olarak çalışan başka bir process) yapabilir. Bu, hem credential dumping (LSASS bellek okuma) hem de "token stealing" (bir SYSTEM process'inin token'ini çalıp kendi thread'ine impersonate etme) için kapıyı açar.

**Çalışma mantığı (kavramsal)**: Saldırgan zaten Administrator context'inde ama "SYSTEM değil" bir noktadaysa (bu sık görülen bir senaryo değildir çünkü Administrator zaten SeDebugPrivilege'i enable edebilir), SYSTEM olarak çalışan bir process'i (örnek: `winlogon.exe`, `lsass.exe`) hedef alır, `OpenProcess` ile handle alır, `OpenProcessToken` ile o process'in primary token'ına erişir, `DuplicateTokenEx` ile bu token'in bir kopyasını çıkartır ve `CreateProcessWithTokenW` / `ImpersonateLoggedOnUser` ile kendi process'ini bu token altında başlatır. Sonuç: SYSTEM olarak kod çalıştırma.

### SeImpersonatePrivilege ve "Potato" Ailesi

Bu, pratikte EN SIK istismar edilen privilege'dir çünkü IIS application pool hesapları (`IIS APPPOOL\*`), MSSQL Server hesabı, ve birçok servis hesabı **varsayılan olarak** SeImpersonatePrivilege'e sahiptir -- ama Administrator değildir. Yani "düşük yetkili ama SeImpersonatePrivilege'i olan" bir hesap ele geçirildiğinde (örneğin bir web shell aracılığıyla), SYSTEM'e giden yol açılır.

**Kök neden**: Windows'ta COM/DCOM ve RPC alt sistemleri, bir client "localhost" üzerinden bir servise bağlanınca, o servisin (eğer SeImpersonatePrivilege'i varsa) client'i **Impersonation seviyesinde** temsil etmesine izin verir. Tarihsel olarak birçok Windows RPC/COM servisi (örnek: `BITS`, `DCOM`, `EFSRPC`, `Print Spooler`), NTLM authentication'ı localhost üzerinden zorlanabildiğinde, "SYSTEM olarak kimlik doğrulayan" bir bağlantı başlatılabiliyordu (loopback üzerinden, aynı makine, aynı oturum kabul edildiği için doğrulama basitleştiriliyordu). Saldırgan bu bağlantıyı kendi named pipe'ına veya local RPC endpoint'ine yönlendirdiğinde, SYSTEM context'inde bir NTLM handshake'i kendi kontrolündeki bir named pipe server'ında "yakalayabiliyordu."

**Potato ailesinin ortak mantığı (jenerik anlatım, komut/exploit detayı değil)**:

1. Saldırganın process'i SeImpersonatePrivilege'e sahip ama sınırlandırılmış bir hesap altında çalışır (örnek: IIS worker process).
2. Saldırgan, yerel makinede SYSTEM ayrıcalığına sahip bir Windows bileşenini (COM servisi, BITS, print spooler, veya benzer bir NT AUTHORITY\SYSTEM servisi), kendisiyle -- yani saldırganın kontrolü altındaki bir soket/named pipe ile -- iletişim kurmaya zorlar veya kandırır (coercion). Bu zorlama genellikle "belirli bir DCOM nesnesini instantiate et" ya da "belirli bir URL/UNC yoluna bağlan" şeklinde bir tetikleyici kullanır.
3. SYSTEM servisi bu bağlantıyı kurarken NTLM ile kimlik doğrular; saldırganın dinleyen named pipe/soket'i bu authentication trafiğini yakalar ve **NTLM relay** tekniğiyle kendi üzerinden localhost'a geri yönlendirir (relay), böylece SYSTEM olarak "authenticate olmuş" bir bağlantı elde eder.
4. Bu bağlantı üzerinden saldırgan artık SYSTEM'i impersonate eden bir token elde eder (`ImpersonateNamedPipeClient` gibi bir API çağrısıyla).
5. SeImpersonatePrivilege'i sayesinde saldırgan bu impersonation token'ını `DuplicateTokenEx` ile bir **primary token**'a çevirir ve `CreateProcessWithTokenW` ile SYSTEM olarak yeni bir process başlatır.

Zaman içinde bu ailenin varyantları, Windows'un aldığı önlemlere (örnek: RPC filtreleme, port kısıtlamaları, `OXID resolver` değişiklikleri) karşı farklı coercion teknikleri kullanmıştır (JuicyPotato belirli bir CLSID/COM nesnesini kullanırken, RoguePotato ve PrintSpoofer farklı servisleri -- print spooler RPC gibi -- tetikleyici olarak kullanmıştır, GodPotato ise daha geniş Windows sürümlerinde çalışacak şekilde farklı bir OXID resolver zayıflığından yararlanmıştır). Kavramsal ortak nokta hep aynıdır: **SeImpersonatePrivilege + yerel makinede SYSTEM'i kimlik doğrulamaya zorlayabilme (coercion) + NTLM relay-benzeri bir yakalama**.

**Neden bu kadar güçlü bir teknik**: Çünkü bu saldırı, işletim sisteminin kendi "meşru" mimarisini (COM/DCOM localhost authentication, named pipe impersonation) kullanır; bir "bug" değil, bir **tasarım varsayımı istismarı**dır (yerel makinedeki tüm process'lerin aynı güven seviyesinde olduğu varsayımı). Bu yüzden yama (patch) ile tamamen kapatmak zordur; Microsoft yıllar içinde belirli coercion vektörlerini kapatmış, ama SeImpersonatePrivilege'in kendisi ortadan kaldırılmamıştır çünkü IIS/MSSQL gibi meşru servisler bu privilege'a ihtiyaç duyar (client isteklerini o client adına dosya sistemine/DB'ye erişirken temsil etmek için).

### Named Pipe Impersonation (Genel Kavram)

Named pipe'lar, process'ler arası iletişimde (IPC) yaygın kullanılır. Bir sunucu process bir named pipe oluşturur, client bağlanır ve veri yazar; sunucu `ImpersonateNamedPipeClient()` çağırarak client'in token'ını impersonate edebilir -- bu, "sunucunun client adına işlem yapması gerektiği" senaryolar için tasarlanmıştır (örnek: bir print spooler servisinin, dosyayı çağıran kullanıcının izinleriyle yazdırması).

**Kök neden istismar**: Eğer bir saldırgan, SYSTEM'in bağlanacağı bir named pipe'ı ÖNCEDEN oluşturabilirse (race condition ya da öngörülebilir isim kullanarak) VE sunucu tarafının SeImpersonatePrivilege'e sahip olduğu bir process olduğunu biliyorsa, SYSTEM'in o pipe'a bağlanıp authenticate olmasını tetikleyebilir, ardından bu bağlantı üzerinden SYSTEM token'ını impersonate edebilir. Potato saldırılarının çoğu, aslında bu named pipe impersonation mekanizmasının bir COM/RPC coercion ile birleştirilmiş halidir.

## Nasıl Çalıştığı: Kavramsal Akış (Savunma Gözüyle)

Aşağıdaki akış, tespit ve savunma amacıyla "hangi adımda ne oluyor" sorusuna cevap verir; bu bir sömürü rehberi değildir.

```
[Dusuk yetkili ama SeImpersonatePrivilege'li process]
        |
        | 1. SYSTEM servisini localhost'a baglanmaya zorla (coercion)
        v
[SYSTEM servisi, saldirganin named pipe'ina NTLM ile authenticate olur]
        |
        | 2. Named pipe server bu handshake'i yakalar / relay eder
        v
[ImpersonateNamedPipeClient -> impersonation token (SYSTEM)]
        |
        | 3. DuplicateTokenEx (impersonation -> primary token donusumu)
        v
[CreateProcessWithTokenW / CreateProcessAsUser]
        |
        v
[Yeni process SYSTEM olarak calisir]
```

Bu akışın her adımı, Windows'un normal ve meşru API'lerini kullanır (`ImpersonateNamedPipeClient`, `DuplicateTokenEx`, `CreateProcessWithTokenW` hepsi dokümante edilmiş Win32 API'leridir). Bu yüzden AV/EDR imza tabanlı tespitte zorlanır; davranışsal tespit gerekir.

## Tespit (Detection)

Savunma tarafında odaklanılması gereken katmanlar:

### 1. Privilege Kullanım Telemetrisi

- **Windows Security Event ID 4672** (Special privileges assigned to new logon): Bir logon SeDebugPrivilege, SeImpersonatePrivilege gibi hassas privilege'lar ile oluştuğunda tetiklenir. Bu event, "hangi hesaplar bu privilege'ları ne sıklıkta kullanıyor" sorusuna temel oluşturur. IIS/SQL servis hesapları için beklenen bir "baseline" oluşturup sapmaları izlemek önemlidir.
- **Event ID 4673 / 4674** (Privileged service called / privileged object operation): Bir process'in `OpenProcess` gibi çağrıları SeDebugPrivilege kullanarak yaptığı durumlar loglanabilir (audit policy'de "Audit Sensitive Privilege Use" açık olmalı).
- Sysmon veya EDR ile **process creation zinciri** izlenmeli: özellikle `w3wp.exe` (IIS worker), `sqlservr.exe` (MSSQL) gibi normalde "SYSTEM process'i doğurmaması gereken" process'lerin `cmd.exe`, `powershell.exe` ya da beklenmedik bir SYSTEM context'inde çocuk process oluşturması güçlü bir kırmızı bayraktır.

### 2. Named Pipe ve RPC Anomalileri

- Sysmon Event ID 17/18 (Pipe Created / Pipe Connected) ile beklenmeyen isimlerde (rastgele/rasgele görünümlü, kısa ömürlü) named pipe'ların oluşturulup hemen sonra SYSTEM tarafından bağlanıldığı olaylar izlenmeli.
- Üst üste, aynı saniyeler içinde bir "kullanıcı context'inde pipe oluşturma" ve "SYSTEM'in o pipe'a bağlanması" korelasyonu, potato-tarzı saldırıların imzasal davranışıdır.
- COM/DCOM aktivasyon logları (Component Object Model event log'ları) izlenerek beklenmeyen CLSID'lerin düşük yetkili process'ler tarafından instantiate edilmesi tespit edilebilir.

### 3. Token Anomali Tespiti (EDR / Davranışsal)

- Bir process'in kendi başlangıç token'ından FARKLI (daha yüksek yetkili) bir token ile işlem yapmaya başladığı "token elevation without corresponding logon event" durumu; EDR'lerin çoğu bunu `NtDuplicateToken`, `NtImpersonateThread` gibi kernel çağrılarını izleyerek yakalar.
- Process integrity level değişiklikleri: bir process'in "Medium" integrity'den beklenmedik şekilde "System" integrity davranışı sergilemesi (örnek: SYSTEM'e özgü dosyalara yazma).

### 4. Loglama Önerileri (Özet)

| Kaynak | Ne izlenir |
|---|---|
| Windows Security Log | 4672, 4673, 4688 (process creation, command line dahil) |
| Sysmon | Event 1 (process create + parent), 17/18 (pipe), 10 (process access -- SeDebugPrivilege'in OpenProcess kullanımını yakalamak için önemli) |
| EDR | Token duplication API zinciri, anormal parent-child process ilişkisi (`w3wp.exe -> cmd.exe -> whoami /priv` gibi klasik zincir) |
| IIS/SQL logları | Worker process'in beklenmedik komut çalıştırması (web shell göstergesi) |

`whoami /priv` komutunun bir web uygulama havuzu veya SQL hesabı tarafından çalıştırılması (loglarda process command line olarak görülür), pratikte çok güçlü bir erken uyarı sinyalidir -- bu genellikle saldırganın önce hangi privilege'lara sahip olduğunu kontrol ettiği adımdır.

## Savunma (Mitigation / Hardening)

### 1. Privilege Minimizasyonu (En Etkili Önlem)

- Servis hesaplarına (özellikle IIS application pool identity, SQL Server service account) **gerekmedikçe SeImpersonatePrivilege verilmemeli**. Bu privilege varsayılan olarak `IIS_IUSRS`, `NETWORK SERVICE`, `LOCAL SERVICE` gibi hesaplara atanmış gelir; iş gereksinimi yoksa Local Security Policy (`secpol.msc` -> User Rights Assignment) üzerinden kaldırılması değerlendirilmelidir. Dikkat: bu, bazı meşru IIS/COM işlevlerini bozabilir, bu yüzden önce test ortamında doğrulanmalıdır.
- "Least privilege" prensibi gereği servis hesaplarının gerekli olmayan hiçbir özel privilege'i (SeDebugPrivilege, SeLoadDriverPrivilege, SeTakeOwnershipPrivilege vb.) taşımaması sağlanmalı.

### 2. Servis Yapılandırması ve İzolasyon

- Web uygulamalarını çalıştıran hesapları **ayrı, özel, minimum yetkili** service account'lar olarak yapılandırın; varsayılan `NETWORK SERVICE` gibi geniş paylaşılan hesaplar yerine dedicated gMSA (group Managed Service Account) kullanımı tercih edilmeli.
- IIS uygulama havuzlarında **"Load User Profile"** ve gereksiz COM erişim izinlerini kısıtlayın.
- Mümkünse web-facing servisleri, saldırı yüzeyini azaltmak için container/sandbox (AppContainer, Windows Sandbox mantığı, veya tam izolasyon için ayrı VM) içinde çalıştırın.

### 3. Windows Güncellemeleri ve Yapılandırma Sertleştirme

- Microsoft, yıllar içinde belirli coercion vektörlerini (örnek: belirli RPC/COM zayıflıkları, Print Spooler ile ilgili sorunlar) yamalamıştır; **güncel patch seviyesini korumak** kritik.
- Print Spooler servisi iş gereksinimi yoksa (özellikle sunucularda) devre dışı bırakılmalı -- birçok coercion/relay saldırısında tetikleyici olarak kullanılmıştır.
- NTLM'i mümkün olduğunca kısıtlayın / Kerberos'a zorlayın (`Network security: Restrict NTLM` politikaları); NTLM relay saldırılarının çoğu, Kerberos zorunlu kılındığında çalışmaz hale gelir. **NTLM'in tamamen kapatılamadığı ortamlarda bile**, "Restrict NTLM: Incoming NTLM traffic" ve "Audit NTLM authentication" politikaları görünürlüğü artırır.
- SMB signing ve LDAP signing/channel binding gibi genel relay-karşıtı önlemler, bu ailenin bazı varyantlarının etkisini azaltır (doğrudan bu potato saldırılarının hepsini engellemese de savunma derinliğine katkı sağlar).

### 4. Tespit ve Yanıt Süreçlerini Olgunlaştırma

- SYSTEM olarak çalışan beklenmeyen process'lerin (özellikle web/DB servis hesaplarından türeyen) otomatik olarak izole edilip incelenmesi için EDR playbook'ları kurun.
- Düzenli "privilege audit": hangi servis hesaplarının hangi özel privilege'lara sahip olduğunu periyodik olarak taramak (örnek: `secedit /export` veya PowerShell ile Local Security Policy dump'ı alıp fark analizi yapmak).
- Purple team / tabletop egzersizlerinde bu senaryoyu simüle ederek (izin verilen, kontrollü bir lab ortamında) tespit kurallarının gerçekten tetiklendiğini doğrulayın.

## Yaygın Hatalar

1. **"Sadece Administrator hesapları tehlikeli" varsayımı**: SeImpersonatePrivilege gibi yetkiler Administrator olmayan, görünürde "zararsız" servis hesaplarına da varsayılan olarak atanır. Bu yüzden "bu hesap zaten düşük yetkili, önemli değil" değerlendirmesi yanlıştır -- privilege bazlı risk değerlendirmesi yapılmalıdır, sadece grup üyeliği bazlı değil.
2. **İmza tabanlı AV'ye güvenmek**: Bu teknikler meşru Win32 API'lerini kullandığı için, sadece "bilinen kötü amaçlı dosya hash'i" arayan çözümler bu saldırıları genelde yakalayamaz. Davranışsal/telemetri tabanlı tespit şart.
3. **Print Spooler'ı "sadece yazdırma servisi" olarak görmek**: Gereksiz yere açık bırakılan Print Spooler, tarihsel olarak çoklu coercion tekniğinde kritik rol oynamıştır; iş ihtiyacı yoksa kapatılması basit ama etkili bir önlemdir.
4. **Privilege'ları "tümden kaldırmaya çalışmak" (test etmeden)**: SeImpersonatePrivilege gibi yetkileri kör bir şekilde tüm servis hesaplarından kaldırmak, IIS/COM+ gibi bileşenlerin meşru işlevlerini bozabilir (örnek: kimlik doğrulanmış kullanıcı adına dosya erişimi çalışmayabilir). Değişiklikler önce test/staging ortamında doğrulanmalıdır.
5. **"Yama yaptık, kapandı" yanılgısı**: Potato ailesi zamanla evrimleşmiştir (JuicyPotato -> RoguePotato -> PrintSpoofer -> GodPotato gibi); belirli bir CVE/teknik yamalansa da mekanizmanın KÖKÜ (SeImpersonatePrivilege + yerel coercion imkanı) durdukça yeni varyantlar çıkma potansiyeli vardır. Bu yüzden tek bir yama değil, katmanlı savunma (privilege minimizasyonu + davranışsal tespit + NTLM sertleştirme) esastır.
6. **Sadece network tarafına odaklanmak**: Bu saldırıların çoğu tamamen **yerel (localhost)** gerçekleşir; network segmentasyonu veya firewall kuralları bu saldırı sınıfına karşı tek başına yetersizdir. Host-based kontroller (EDR, audit policy, privilege minimizasyonu) esas savunma hattıdır.

## Özet

SeDebugPrivilege ve SeImpersonatePrivilege, Windows'un meşru işlevsellik için tasarladığı ama yanlış yapılandırma veya aşırı geniş atama durumunda güçlü bir privesc vektörüne dönüşen özel yetkilerdir. "Potato" ailesi saldırıları, bu privilege'ları, Windows'un yerel COM/RPC/named pipe mimarisindeki NTLM authentication varsayımlarıyla birleştirerek düşük yetkili bir servis hesabından SYSTEM'e zıplamayı mümkün kılar. Savunma tarafında tek bir "silver bullet" yoktur: privilege minimizasyonu, servis hesabı izolasyonu, NTLM/Print Spooler sertleştirmesi ve davranışsal telemetri (process zinciri, named pipe anomalileri, privilege kullanım logları) birlikte uygulanmalıdır. Bu konu, "Windows Privesc" başlığı altında kaybolmayacak kadar somut ve sık karşılaşılan bir teknik olduğu için ayrı incelenmeyi hak eder.
