# Windows Yetki Yükseltme (Privilege Escalation)

## Tanım ve Kapsam

Windows üzerinde **yetki yükseltme (privilege escalation)**, sınırlı haklara sahip bir hesabın (örneğin standart bir kullanıcı veya bir servis hesabı) sahip olduğu ayrıcalıkların ötesine geçerek daha yüksek yetkili bir bağlama — tipik olarak `NT AUTHORITY\SYSTEM`, yerel yönetici (`Administrators`) grubu veya bir domain ortamında `Domain Admin` — erişmesi sürecidir. Saldırgan bakış açısından bu, "ilk erişim" (initial access) sonrası gelen kritik bir adımdır: bir phishing e-postası veya zayıf bir servis üzerinden düşük yetkili bir shell elde edildikten sonra, kalıcılık (persistence), yanal hareket (lateral movement) ve veri sızdırma için genellikle yüksek yetki gerekir.

Windows'ta yetki yükseltme iki ana eksende incelenir. **Dikey (vertical) yükseltme**, düşük yetkiden yüksek yetkiye geçiştir (kullanıcı → SYSTEM). **Yatay (horizontal) yükseltme** ise aynı yetki seviyesinde başka bir kullanıcının bağlamına geçmektir (kullanıcı A → kullanıcı B). Bu makale ağırlıklı olarak dikey yükseltmenin en yaygın ve öğretici vektörlerine odaklanıyor: servis yanlış yapılandırmaları, access token manipülasyonu, saklı/açıkta kalan kimlik bilgileri, DLL hijacking ve UAC bypass.

Windows'un güvenlik modelini anlamadan bu vektörlerin hiçbiri tam oturmaz, o yüzden temel mekanizmayla başlayalım.

## Kök Neden: Windows Güvenlik Modeli Neden Bu Kadar İstismar Edilebilir?

Windows'ta her process bir **access token** taşır. Bu token, o process'in "kimliği"dir: hangi kullanıcı olarak çalıştığını (SID — Security Identifier), hangi gruplara üye olduğunu ve hangi **privilege**'lere (örneğin `SeDebugPrivilege`, `SeImpersonatePrivilege`) sahip olduğunu içerir. Bir kaynağa (dosya, registry anahtarı, servis) erişim istendiğinde, Windows bu token'daki SID'leri ve privilege'leri kaynağın **DACL**'ı (Discretionary Access Control List) ile karşılaştırarak karar verir.

Buradaki temel gerilim şudur: Windows, geriye dönük uyumluluk (backward compatibility) ve idari kolaylık uğruna son derece esnek bir izin modeline sahiptir. Bir yöneticinin bir servisi, bir dosyayı veya bir registry anahtarını yanlışlıkla fazla geniş izinlerle bırakması çok kolaydır. Yetki yükseltmenin kök nedeni neredeyse her zaman **bir güven sınırının (trust boundary) yanlış çizilmesidir**: yüksek yetkiyle çalışan bir bileşenin (SYSTEM olarak koşan bir servis), düşük yetkili bir kullanıcının kontrol edebildiği bir girdiye (yazılabilir bir dosya yolu, bir DLL arama sırası, bir kullanıcı-kontrollü path) güvenmesi.

Saldırgan bu asimetriyi arar: "SYSTEM olarak çalışan ama benim değiştirebildiğim bir şeye bağımlı olan ne var?" Sorunun cevabı, aşağıdaki her vektörün özüdür.

## Servis Yanlış Yapılandırmaları (Service Misconfigurations)

Windows servisleri (`services.exe` tarafından yönetilen) genellikle `LocalSystem` bağlamında, yani en yüksek yetkiyle çalışır. Bir servis düşük yetkili bir kullanıcının müdahale edebileceği şekilde yapılandırıldıysa, o kullanıcı SYSTEM'e yükselebilir. Başlıca alt-vektörler şunlardır.

### Unquoted Service Path (Tırnaksız Servis Yolu)

Bir servisin çalıştırılabilir yolu boşluk içeriyor ve tırnak içine alınmamışsa, Windows'un servis yolunu çözümleme (path resolution) mantığı istismar edilebilir. Örneğin bir servisin `ImagePath` değeri şöyle olsun:

```
C:\Program Files\Bir Uygulama\hizmet servisi\service.exe
```

Tırnak yoksa, Windows bu yolu soldan sağa parçalayarak sırasıyla şunları çalıştırmayı dener:

```
C:\Program.exe
C:\Program Files\Bir.exe
C:\Program Files\Bir Uygulama\hizmet.exe
C:\Program Files\Bir Uygulama\hizmet servisi\service.exe
```

Neden böyle? Çünkü boşluk komut satırında argüman ayırıcıdır ve Windows, açık bir tırnak yokluğunda her boşluğa kadar olan kısmı bir çalıştırılabilir aday olarak yorumlar. Eğer saldırgan bu ara dizinlerden birine (örneğin `C:\Program Files\Bir Uygulama\` içine `hizmet.exe`) yazma iznine sahipse, kendi payload'unu oraya koyar; servis yeniden başlatıldığında SYSTEM olarak saldırganın binary'si çalışır.

**İstismar mantığı:** Önce tırnaksız yollu servisleri bul (WMI/`sc qc` ile `ImagePath` incelenir), ardından ara dizinlerde yazma izni olan bir noktayı tespit et, sahte binary'i yerleştir ve servisi (mümkünse) yeniden başlat.

**Savunma:** Tüm servis `ImagePath` değerlerini tırnak içine al. Daha önemlisi, `Program Files` ve alt dizinlerinde standart kullanıcılara yazma izni **verme** — varsayılan olarak verilmez, ama üçüncü parti kurulumcular bunu bozabilir. Düzenli olarak ACL denetimi yap.

### Zayıf Servis İzinleri (Weak Service Permissions)

Asıl kritik olan, servisin *konfigürasyonunu* değiştirme yetkisidir. Bir servisin DACL'ı standart bir kullanıcıya `SERVICE_CHANGE_CONFIG` hakkı veriyorsa, o kullanıcı servisin çalıştırdığı binary yolunu (`binPath`) doğrudan kendi komutuyla değiştirebilir. Örneğin `binPath`, bir kullanıcı ekleyen ve onu yöneticiler grubuna atan bir komuta yönlendirilir; servis yeniden başlatıldığında bu komut SYSTEM olarak koşar.

Benzer şekilde, bir kullanıcının servisin bağlı olduğu **çalıştırılabilir dosyaya** (`service.exe` dosyasının kendisine) yazma izni varsa, dosyayı doğrudan payload ile değiştirmek yeterlidir. Bir üçüncü grup ise, servisi durdurup başlatma (`SERVICE_START`/`SERVICE_STOP`) haklarının, yukarıdaki değişikliği tetiklemek için gerekli tamamlayıcı yetki olmasıdır.

**Savunma:** Servis DACL'larını düzenli denetle; standart kullanıcıların `SERVICE_CHANGE_CONFIG`, `WRITE_DAC`, `WRITE_OWNER` gibi haklara sahip olmadığından emin ol. Servis binary'lerinin bulunduğu dizinlere yazma iznini kısıtla. Sysinternals `AccessChk` benzeri araçlarla bu denetim otomatikleştirilebilir. Konfigürasyon değişikliklerini ve şüpheli `binPath` güncellemelerini (Event ID tabanlı) izle.

### Yeniden Yazılabilir Registry ve Görev Zamanlayıcı

Servis parametrelerinin bir kısmı registry altında (`HKLM\SYSTEM\CurrentControlSet\Services\...`) tutulur. Kullanıcı bu anahtarlara yazabiliyorsa, `ImagePath`'i doğrudan registry üzerinden de değiştirebilir. Aynı mantık, SYSTEM olarak çalışan ve kullanıcı-yazılabilir bir script/binary'e işaret eden zamanlanmış görevler (Scheduled Tasks) için de geçerlidir.

## Access Token Manipülasyonu ve Impersonation

Token vektörü, servis vektöründen daha inceliklidir ve modern Windows istismarının kalbindedir. Windows, bir process'in başka bir kullanıcının kimliğine bürünmesine (impersonation) imkân tanır — bu, örneğin bir web sunucusunun istemci adına dosya açması gibi meşru senaryolar için tasarlanmıştır. Ancak bu yetenek kötüye kullanılabilir.

### SeImpersonatePrivilege ve "Potato" Ailesi

`SeImpersonatePrivilege`, sahip olan process'e "kendisine sunulan bir token'ı impersonate etme" hakkı verir. Bu privilege, ilginç biçimde, birçok servis hesabında (özellikle web ve veritabanı servislerinin çalıştığı `IIS AppPool`, `NETWORK SERVICE`, `LOCAL SERVICE` gibi hesaplarda) **varsayılan olarak bulunur**. Neden? Çünkü bu servis hesaplarının meşru işlevi zaten istemci kimliğine bürünmeyi gerektirir.

İstismar fikri şudur: Saldırgan, düşük yetkili ama `SeImpersonatePrivilege`'a sahip bir bağlamdadır (örneğin ele geçirilmiş bir web uygulaması üzerinden `IIS AppPool` olarak). Bir Windows bileşenini (tarihsel olarak COM/DCOM veya RPC üzerinden çalışan bir SYSTEM servisi) kandırarak, o SYSTEM bileşeninin saldırgana bir **kimlik doğrulama (authentication)** yapmasını sağlar. Bu authentication sırasında oluşan SYSTEM token'ı, `SeImpersonatePrivilege` sayesinde yakalanıp impersonate edilir ve saldırgan artık SYSTEM olarak yeni bir process başlatabilir.

Bu tekniğin çeşitli isimlerle anılan bir ailesi vardır (kamuoyunda "Potato" olarak bilinen bir dizi araç: RottenPotato, JuicyPotato, PrintSpoofer ve benzeri türevler). Bunların ortak paydası, bir SYSTEM servisini bir named pipe veya benzeri bir kanal üzerinden saldırgana authenticate olmaya zorlamak ve ortaya çıkan token'ı ele geçirmektir. Tam olarak hangi aracın hangi Windows sürümünde çalıştığı zaman içinde değişmiştir çünkü Microsoft ilgili tetikleyicileri (örneğin belirli DCOM davranışlarını) sürüm sürüm sertleştirmiştir; bu nedenle kesin sürüm-araç eşleşmesi vermek yerine mekanizmayı vurguluyorum: **impersonate hakkı + SYSTEM'i authenticate olmaya zorlayan bir tetikleyici = SYSTEM.**

**Savunma:** Servis hesaplarına gereğinden fazla privilege verme; `SeImpersonatePrivilege`'a gerçekten ihtiyacı olmayan hesaplardan bunu kaldır. Web/DB servislerini en az yetki ilkesiyle yapılandır ve yönetilen servis hesapları (gMSA) kullan. Sistemleri güncel tut — bu tekniklerin çoğu, belirli tetikleyicilerin yamalanmasıyla kapanır. Anormal token impersonation ve beklenmedik SYSTEM process başlatmalarını EDR ile izle.

### SeDebugPrivilege ve Token Çalma

`SeDebugPrivilege`, herhangi bir process'e (SYSTEM dahil) debugger olarak bağlanma hakkı verir. Bu privilege'a sahip bir saldırgan, SYSTEM olarak çalışan bir process'in (örneğin `lsass.exe` veya `winlogon.exe`) handle'ını açıp onun token'ını çoğaltabilir (`DuplicateToken`) ve o token'la yeni bir process oluşturabilir. Bu, meşru olarak yalnızca yöneticilerde bulunması gereken bir yetkidir; bir standart kullanıcıda görülüyorsa bu zaten bir yanlış yapılandırma işaretidir.

**Savunma:** `SeDebugPrivilege`'ı yalnızca gereken idari hesaplarda tut. `lsass.exe`'yi korumak için Credential Guard ve LSA Protection (RunAsPPL) etkinleştir; bunlar token/kimlik hırsızlığını ciddi şekilde zorlaştırır.

## Saklı ve Açıkta Kalan Kimlik Bilgileri (Stored/Exposed Credentials)

Belki de en sık işleyen ve en az "zarif" vektör: kimlik bilgilerinin sistemde açıkta durmasıdır. Yetki yükseltme her zaman bir yazılım açığı gerektirmez; çoğu zaman bir yönetici parolası bir dosyanın içinde beklemektedir.

Tipik saklı kimlik bilgisi kaynakları şunlardır:

- **Unattended kurulum dosyaları:** `Unattend.xml`, `sysprep.xml` gibi otomatik kurulum dosyaları bazen yönetici parolasını düz metin veya zayıf (Base64) kodlanmış halde içerir ve disk üzerinde kalır.
- **Registry içindeki parolalar:** Özellikle **AutoLogon** yapılandırması, kullanıcı adını ve parolayı `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon` altında düz metin `DefaultPassword` değeri olarak tutabilir. Ayrıca üçüncü parti uygulamalar da registry'e parola gömer.
- **PowerShell geçmişi:** `ConsoleHost_history.txt` dosyası, kullanıcının komut satırına yazdığı — bazen parola içeren — komutları saklar.
- **Grup İlkesi ve GPP:** Tarihsel olarak Group Policy Preferences, `SYSVOL` üzerinde parolaları geri döndürülebilir bir şekilde (bilinen, sabit bir anahtarla) şifreli tutuyordu; bu, domain çapında bir yükseltme vektörüydü ve Microsoft bunu yamalarla kapattı, ancak eski GPP kalıntıları hâlâ ortamlarda bulunabilir.
- **Credential Manager, uygulama config dosyaları, script'ler, `.git` içindeki gömülü sırlar:** Kaynak kod ve yapılandırma dosyalarında gömülü bağlantı dizeleri ve API anahtarları.

**İstismar mantığı:** İlk erişim sonrası saldırgan sistematik olarak bu konumları tarar (dosya sistemi, registry, komut geçmişi) ve bulduğu her kimlik bilgisini yatay/dikey yükseltme için dener. Bir servis hesabının parolası bulunursa, o hesabın yetkileri devralınır.

**Savunma:** Unattended kurulum dosyalarını dağıtım sonrası **sil**. AutoLogon kullanma; zorunluysa LAPS gibi yönetilen çözümlerle yerel yönetici parolalarını rotasyona sok. Sırları asla script veya config dosyasına gömme; bir secret manager kullan. Düzenli olarak disk üzerinde açıkta kalan sırları tarayan araçlar çalıştır. PowerShell komut geçmişini duyarlı komutlar için devre dışı bırakmayı veya temizlemeyi değerlendir.

## DLL Hijacking (DLL Arama Sırası İstismarı)

DLL hijacking, Windows'un bir process çalışırken ihtiyaç duyduğu dinamik kütüphaneleri (DLL) **nasıl bulduğu** üzerine kuruludur. Bir uygulama `LoadLibrary("örnek.dll")` gibi tam yol vermeden bir DLL istediğinde, Windows belirli bir **arama sırası (search order)** izler: kabaca uygulamanın kendi dizini, sistem dizinleri (`System32` vb.), Windows dizini ve `PATH` ortam değişkenindeki dizinler.

Kök neden şudur: Eğer yüksek yetkiyle çalışan bir uygulama, aradığı bir DLL'i sistem dizinlerinde **bulamazsa** ve arama sırasındaki dizinlerden birine saldırgan yazabiliyorsa, saldırgan oraya aynı isimde kötü niyetli bir DLL koyabilir. Uygulama bu sahte DLL'i yükler ve içindeki kod, uygulamanın yetkisiyle (örneğin SYSTEM) çalışır.

İki temel senaryo vardır. **Birincisi**, uygulamanın var olmayan bir DLL'i araması (ör. yazılımın hiç dağıtmadığı isteğe bağlı bir bileşen) — bu boşluk saldırganın DLL'i ile doldurulur. **İkincisi**, arama sırasında uygulama dizininin sistem dizinlerinden **önce** gelmesinden yararlanarak, meşru bir sistem DLL'inin adaşını uygulama dizinine koymak; ancak modern Windows'ta "known DLLs" mekanizması ve güvenli arama sırası (`SafeDllSearchMode`, varsayılan olarak açık) bunun bir kısmını engeller.

Yetki yükseltme bağlamında kritik nokta: **hedef, yüksek yetkiyle çalışan ama saldırganın yazabildiği bir dizinden DLL yükleyen bir process olmalıdır.** En sık rastlanan durum, üçüncü parti yazılımların kurulum dizinlerinin (özellikle `Program Files` dışındaki, gevşek ACL'li dizinlerin) yazılabilir olması ve buradaki bir servisin/uygulamanın eksik bir DLL aramasıdır.

**İstismar mantığı:** Eksik DLL yüklemelerini tespit et (Sysinternals `Process Monitor` ile "NAME NOT FOUND" sonucu veren `.dll` erişimleri izlenerek), bu dizinlerden birine yazma iznin olup olmadığını kontrol et, aynı isimli payload DLL'ini yerleştir ve process'in yeniden başlamasını (veya tetiklenmesini) bekle.

**Savunma:** DLL'leri her zaman tam yolla yükle veya `SetDefaultDllDirectories` ile arama dizinlerini sıkılaştır. Uygulama kurulum dizinlerinde standart kullanıcı yazma iznini kaldır. `SafeDllSearchMode`'un açık olduğundan emin ol. Uygulama beyaz listeleme (WDAC / AppLocker) ile imzasız DLL yüklenmesini engelle — bu, DLL hijacking'e karşı en güçlü savunmalardan biridir. `PATH` içindeki dünya-yazılabilir dizinleri temizle.

## UAC (User Account Control) Bypass

Burada bir nüans var ve dürüst olmak gerekir: **UAC, Microsoft'un resmî tanımına göre bir güvenlik sınırı (security boundary) değildir.** UAC, bir yöneticinin oturumunda bile process'lerin varsayılan olarak "medium integrity" (orta bütünlük) seviyesinde çalışmasını sağlayan bir kolaylık/rıza mekanizmasıdır; yükseltme gerektiğinde kullanıcıya onay penceresi gösterir. Yani UAC bypass, teknik olarak "SYSTEM'e yükselme" değil, çoğunlukla **zaten yönetici grubunda olan bir kullanıcının, onay istemi (prompt) olmadan medium integrity'den high integrity'ye geçmesidir.**

Bunu anlamak önemli çünkü UAC bypass, standart bir kullanıcıyı yöneticiye çevirmez — kullanıcının zaten yerel yönetici olması gerekir. Değeri, saldırının sessiz (prompt'suz) ilerlemesini sağlamaktır.

### Çalışma Mantığı: Auto-Elevate ve Güvenilen Binary'ler

Windows, sürtünmeyi azaltmak için bazı imzalı sistem binary'lerinin (belirli Microsoft araçları) UAC istemi göstermeden otomatik yükselmesine (auto-elevate) izin verir. UAC bypass teknikleri genellikle şu deseni kullanır: Bu auto-elevate olan güvenilir bir binary'i, saldırganın kontrol ettiği bir girdiyi çalıştıracak şekilde kandırmak. Yaygın mekanizmalar:

- **Registry hijack:** Auto-elevate bir binary, çalışırken belirli bir registry anahtarını okur (örneğin bir komut yolu). Bu anahtar `HKCU` altında ve kullanıcı-yazılabilirse, saldırgan oraya kendi komutunu yazar; binary yükseldiğinde saldırganın komutunu high integrity ile çalıştırır. Kamuoyunda bilinen örnekler `fodhelper` ve `eventvwr` tabanlı tekniklerdir (belirli registry yollarının kaçırılması).
- **DLL yandan yükleme:** Auto-elevate binary'e, yukarıda anlatılan DLL hijacking mantığıyla sahte bir DLL yükletmek.

Bu tekniklerin belirli olanları zamanla yamalanmıştır; hangi anahtarın hangi build'de çalıştığı değişkendir. Yine ilkeyi vurgulayayım: **güvenilen + auto-elevate bir binary + saldırganın etkileyebildiği bir girdi (registry/DLL/dosya) = sessiz yükseltme.**

**Savunma:** UAC seviyesini **en yüksek ("Always notify")** ayarına çek — bu, birçok registry tabanlı bypass'ın dayandığı sessiz auto-elevate davranışını kırar. Kullanıcıları gündelik işlerde yerel yönetici yapma; ayrı bir yönetici hesabı modeli uygula (böylece bypass edilecek yönetici bağlamı zaten yoktur). Güncel kal. Bilinen bypass binary'lerinin (fodhelper vb.) anormal çocuk process'lerini ve `HKCU` altındaki ilgili registry anahtarlarına yazımları EDR ile izle. WDAC/AppLocker ile beklenmedik process zincirlerini engelle.

## Yaygın Hatalar

Aşağıdakiler hem sistem yöneticilerinin hem de bu konuyu yeni öğrenenlerin sıkça düştüğü tuzaklardır.

- **"Servis Program Files'ta, o yüzden güvenli" varsayımı.** Kurulumcular sık sık alt dizinlere veya `C:\` köküne gevşek ACL'ler bırakır. Konumun kendisi güvenlik garantisi değildir; ACL'i denetlemek gerekir.
- **UAC'yi bir güvenlik sınırı sanmak.** UAC istemine güvenip kullanıcıları yerel yönetici yapmak, UAC bypass'ı önemsiz hale getirir. Gerçek sınır, kullanıcının yönetici olup olmamasıdır.
- **Servis hesaplarına aşırı privilege vermek.** `SeImpersonatePrivilege` ve `SeDebugPrivilege` gibi güçlü hakları gereksiz yere servis hesaplarında bırakmak, "Potato" tarzı yükseltmelerin kapısını açık tutar.
- **Kimlik bilgilerini disk üzerinde bırakmak.** Unattended dosyaları silmemek, AutoLogon parolalarını registry'de tutmak, script'lere sır gömmek — hepsi yamaya bile gerek kalmadan sömürülür.
- **DLL arama sırasını göz ardı etmek.** Tam yol vermeden DLL yüklemek ve yazılabilir dizinlerden yükleme yapmak, sessiz bir yükseltme yüzeyi yaratır.
- **Yalnızca yamaya güvenmek.** Yetki yükseltme vektörlerinin büyük kısmı yama değil **yapılandırma** sorunudur; sistem tam güncel olsa bile zayıf ACL'ler ve açıkta kalan sırlar iş görür.
- **Denetim ve loglamayı ihmal etmek.** Servis binPath değişiklikleri, anormal token impersonation, `HKCU` registry yazımları — bunlar loglanmıyorsa saldırı sessizce ilerler.

## En İyi Pratikler (Savunma Özeti)

Yetki yükseltmeye karşı savunma, tek bir sihirli ayar değil, katmanlı bir yaklaşımdır. Öncelik sırasıyla:

**1. En az yetki ilkesi (least privilege).** Kullanıcıları gündelik işlerde yerel yönetici yapma. Servis hesaplarına yalnızca ihtiyaç duydukları privilege'leri ver; `SeImpersonate`/`SeDebug` gibi hakları gereksiz hesaplardan kaldır. Mümkün olan her yerde yönetilen servis hesapları (gMSA) kullan.

**2. ACL hijyeni.** Servisleri, binary dizinlerini, registry anahtarlarını ve `PATH` dizinlerini standart kullanıcıların yazamayacağı şekilde yapılandır. Tırnaksız servis yollarını düzelt. Sysinternals `AccessChk` / `Autoruns` gibi araçlarla ve WinPEAS benzeri güvenli-kontrollü denetim araçlarıyla periyodik tarama yap — kendi zayıflıklarını saldırgandan önce bul.

**3. Kimlik bilgisi hijyeni.** Unattended dosyalarını sil, AutoLogon'dan kaçın, yerel yönetici parolaları için LAPS kullan, sırları secret manager'da tut. LSA Protection (RunAsPPL) ve Credential Guard ile `lsass` içindeki kimlikleri koru.

**4. UAC'yi en yüksek seviyede tut** ve gerçek güven sınırının UAC değil hesap yetkisi olduğunu unutma.

**5. Uygulama kontrolü (WDAC / AppLocker).** İmzasız/beklenmedik binary ve DLL'lerin çalışmasını engellemek, hem DLL hijacking'i hem de birçok yükseltme aracını doğrudan etkisiz kılar. Bu, en yüksek getirili savunmalardan biridir.

**6. İzleme ve tespit (detection).** EDR ile: anormal token impersonation, beklenmedik SYSTEM/high-integrity process başlatmaları, servis konfigürasyon değişiklikleri, `HKCU` altındaki bilinen bypass anahtarlarına yazımlar ve "NAME NOT FOUND" veren şüpheli DLL yüklemeleri izlenmelidir. Görünürlük olmadan savunma eksik kalır.

**7. Yama yönetimi.** Yapılandırma çoğu vektörün kökü olsa da, "Potato" tetikleyicileri ve belirli UAC bypass'ları gibi kod-seviyesi zayıflıklar yalnızca yamayla kapanır; sistemleri güncel tut.

## Kapanış

Windows yetki yükseltmesinin tüm vektörleri tek bir ortak kök nedene indirgenir: **yüksek yetkili bir bileşenin, düşük yetkili birinin kontrol edebildiği bir girdiye güvenmesi.** İster tırnaksız bir servis yolu, ister impersonate edilebilir bir token, ister disk üzerinde bekleyen bir parola, ister kaçırılabilir bir DLL, ister sessizce yükselen bir binary olsun — mekanizma hep aynı güven sınırı ihlalidir. Savunmanın özü de buradan çıkar: her yüksek yetkili bileşenin bağımlı olduğu girdilerin (dosya, registry, token, DLL, path) düşük yetkili aktörlerce değiştirilemediğinden emin olmak. En az yetki, sıkı ACL'ler, kimlik hijyeni ve güçlü görünürlük bir araya geldiğinde bu vektörlerin çoğu daha ilk adımda kapanır.
