# Living off the Land (LOLBAS / GTFOBins)

## Tanım

"Living off the Land" (LotL), Türkçesiyle "araziden beslenme" ya da "yerinde yaşama" tekniği, saldırganın hedef sisteme kendi kötü amaçlı araçlarını (custom malware, exploit kiti, özel binary) getirmek yerine, sistemde **zaten var olan, işletim sistemiyle birlikte gelen ya da güvenilir yazılımlarca kurulmuş meşru araçları** kötü amaçlarla kullanmasıdır. Windows dünyasında bu araçlara **LOLBAS** (Living Off the Land Binaries, Scripts and Libraries), Unix/Linux dünyasında ise **GTFOBins** (Get The F\* Out Binaries) denir. Her ikisi de aynı çekirdek fikri temsil eder: sistemin dijital olarak imzalı, işletim sisteminin bir parçası olan ve güvenlik ürünlerinin çoğunlukla "güvenilir" saydığı ikili dosyalarını, tasarım amaçlarının dışında saldırgan işlevler için istismar etmek.

LOLBAS ve GTFOBins ayrıca birer topluluk projesidir: bu meşru araçların hangi "beklenmedik" yeteneklere sahip olduğunu (dosya indirme, kod çalıştırma, kimlik bilgisi sızdırma, UAC atlama, AppLocker bypass, veri sızdırma vb.) kataloglayan açık kaynak veritabanlarıdır. Bir güvenlik uzmanının bu projeleri düzenli takip etmesi, hem saldırıyı öngörmek hem de tespit kuralı yazmak için kritik öneme sahiptir.

Konunun kalbinde üç kavram yatar: **meşru araçla saldırı**, **fileless (dosyasız) çalışma** ve **tespit zorluğu**. Bu makale bu üçünün neden ve nasıl birbirine bağlandığını çözümler.

## Kök neden: Neden meşru araçlar silaha dönüşüyor?

LotL tekniğinin var olabilmesinin temel nedeni, modern işletim sistemlerinin **çok amaçlı ve güçlü ikili dosyalarla** gelmesidir. `powershell.exe`, `certutil.exe`, `bitsadmin.exe`, `wmic.exe`, `mshta.exe`, `regsvr32.exe` gibi Windows araçları; `bash`, `curl`, `wget`, `python`, `perl`, `find`, `awk`, `tar`, `vim` gibi Unix araçları, meşru kullanım için tasarlanmış ama son derece genel amaçlı yeteneklere sahiptir. Bir araç ne kadar genel amaçlıysa (dosya okuma/yazma, ağ bağlantısı kurma, komut çalıştırma, kod yorumlama), saldırgan için o kadar kullanışlıdır.

Bunun ardındaki kök nedenleri sıralayalım:

**1. Güven modeli imzaya dayanır.** Çoğu güvenlik kontrolü (application allowlisting, AppLocker, WDAC, kimi EDR politikaları) bir binary'nin **kim tarafından imzalandığına** bakar. Microsoft imzalı `certutil.exe` "güvenilir"dir; Red Hat'in paket yöneticisiyle gelen `curl` "güvenilir"dir. Saldırgan kendi imzasız binary'sini çalıştıramayacağı bir ortamda, zaten allowlist'te olan bu imzalı araçları kullanarak güven modelinin altından geçer. Buna genellikle **"trusted binary abuse"** denir.

**2. Bu araçlar çalışırken normal görünür.** Bir kurumsal ağda `powershell.exe` günde binlerce kez, meşru yönetim betikleri tarafından çalıştırılır. Bir sistem yöneticisinin `certutil` ile sertifika işlemesi ya da `bitsadmin` ile bir güncelleme indirmesi olağandır. Saldırganın etkinliği bu "gürültünün" içinde eriyip kaybolur. Güvenlik ekibinin karşılaştığı zorluk artık "kötü bir binary buldum mu?" değil, "iyi bir binary'nin kötü bir amaçla mı yoksa iyi bir amaçla mı çalıştığını nasıl ayırt ederim?" sorusudur ki bu çok daha zordur.

**3. Diske kötü amaçlı bir artefakt düşmez (fileless).** Saldırgan kendi payload'unu bir dosya olarak diske yazmadığında, imza tabanlı (signature-based) antivirüs, dosya bütünlüğü izleme ve "yeni oluşturulmuş şüpheli exe" tabanlı tespitler çalışmaz. Kod bellekte (in-memory) yorumlanır, ağ üzerinden akar, ya da mevcut sistem bileşenlerinin (WMI deposu, registry, planlanmış görevler, servisler) içine gömülür. Adli analizde (forensics) "kanıt" fiziksel bir dosya olmadığı için toplanması güçtür.

**4. En az ayrıcalık ihlali ve zincirleme.** GTFOBins bağlamında özellikle kritik olan nokta, çoğu Unix aracının **beklenmedik biçimde bir shell doğurabilmesi ya da dosya okuyup yazabilmesidir**. `sudo` ile ayrıcalıklı çalıştırılmasına izin verilmiş masum görünen bir araç (`find`, `less`, `vi`, `tar`, `awk`), aslında root shell'e giden bir kapı olabilir. Benzer şekilde SUID biti set edilmiş bir binary, ayrıcalık yükseltme (privilege escalation) için silaha dönüşür. Burada kök neden, aracın işlevinin sistem yöneticisinin farkında olmadığı yan yeteneklere sahip olmasıdır.

Özetle: LotL, güvenlik denetimlerinin "kötü olan bilinir ve engellenir" (blocklist) varsayımını kırar. Kötü olan, iyi olanın ta kendisidir; sadece niyet değişmiştir. Niyeti tespit etmek imzayı tespit etmekten kat kat zordur.

## Çalışma mantığı: Bir LOLBIN neyi mümkün kılar?

Bir binary'nin "LOLBIN" niteliği kazanması için genellikle şu yeteneklerden birine sahip olması gerekir:

- **Download / veri getirme:** Uzak bir sunucudan dosya indirebilme. Saldırganın ikinci aşama payload'unu C2 sunucusundan çekmesini sağlar.
- **Execute / kod çalıştırma:** Doğrudan ya da dolaylı olarak keyfi kod, script ya da başka bir binary çalıştırabilme.
- **Encode / decode:** Base64 gibi kodlamalarla veri dönüştürebilme. Hem payload'ı gizlemek hem de veri sızdırmak (exfiltration) için kullanılır.
- **Bypass:** UAC, AppLocker/WDAC, güvenlik politikası ya da loglama mekanizmalarını atlatabilme.
- **Credential access / dump:** Kimlik bilgisi ya da hassas veri okuyabilme.
- **Shell spawn / privilege escalation:** (Özellikle Unix) alt kabuk doğurabilme, ayrıcalıklı bağlamda kod çalıştırma.

Aynı binary birden fazla kategoriye girebilir. LOLBAS/GTFOBins veritabanlarının değerli olma sebebi de budur: her binary için hangi yeteneğin **hangi çağrı biçimiyle** (invocation) tetiklendiğini belgelerler.

## Somut örnekler

Aşağıdaki örnekler kavramı göstermek içindir. Komutların tam bayrakları ve sözdizimi işletim sistemi sürümüne ve araç sürümüne göre değişebilir; buradaki amaç **mantığı** anlatmaktır, ezber komut vermek değil.

### Windows tarafı (LOLBAS)

**certutil ile dosya indirme.** `certutil`, adından anlaşılacağı üzere sertifika yönetimi için gelen bir Microsoft aracıdır. Ancak `-urlcache` benzeri seçeneklerle uzak bir URL'den dosya indirme yeteneğine sahiptir. Saldırgan bunu, ağa `curl/wget` getirmeden ikinci aşama payload'unu indirmek için kullanır. Aynı araç base64 encode/decode de yapabildiği için, hem payload'ı gizlemede hem de sızdırmada iki kat kullanışlıdır. Mantık: "İndirme aracına ihtiyacım yok, çünkü sertifika aracı zaten indirme yapabiliyor ve o Microsoft imzalı."

**mshta ve regsvr32 ile kod çalıştırma.** `mshta.exe` HTML uygulamalarını (.hta) çalıştırmak için gelen bir bileşendir ve içinde script (VBScript/JScript) yorumlayabilir. `regsvr32.exe` ise COM bileşenlerini kaydetmek için gelir ama uzaktaki bir scriptlet'i (.sct) çağırıp çalıştırabilir; bu, tarihsel olarak "Squiblydoo" adıyla bilinen bir AppLocker bypass tekniğinin çekirdeğidir. Her iki durumda da diske hiçbir exe düşmeden, güvenilir bir Windows bileşeni üzerinden kod belleğe yüklenip çalışır.

**PowerShell ile fileless indir-çalıştır.** Klasik LotL kalıbı, PowerShell'in bir web isteği yapıp gelen script'i doğrudan bellekte yorumlamasıdır (`IEX`/Invoke-Expression mantığı). Burada payload asla diske yazılmaz. PowerShell ayrıca `-EncodedCommand` ile base64 kodlanmış komut alabildiği için, komut satırı loglarında bile içeriği gizlemeye çalışır. Bu, savunmacıların neden **script block logging** ve **AMSI**'ye (Antimalware Scan Interface) ihtiyaç duyduğunu açıklar; çünkü encode edilmiş komut ancak çalıştırılma anında çözülür.

**bitsadmin / BITS servisi.** Windows'un arka plan aktarım servisi (Background Intelligent Transfer Service), meşru güncelleme indirmeleri için vardır. Saldırgan bunu hem dosya indirmek hem de kalıcılık (persistence) sağlamak için kötüye kullanabilir; BITS transfer işleri sistem yeniden başlasa bile hayatta kalabilir ve indirme trafiği "güncelleme trafiği" gibi görünür.

**wmic ve WMI.** WMI (Windows Management Instrumentation), meşru sistem yönetim çerçevesidir. Saldırganlar WMI'yi uzaktan komut çalıştırma (lateral movement), kalıcılık (WMI event subscription ile tetiklenen payload) ve keşif (recon) için kullanır. WMI tabanlı kalıcılık özellikle sinsidir çünkü artefakt WMI deposunun içindedir, dosya sisteminde belirgin bir iz bırakmaz.

### Unix / Linux tarafı (GTFOBins)

**sudo ile izin verilmiş bir aracın shell doğurması.** Diyelim ki bir kullanıcıya `sudo` ile `find` çalıştırma izni verilmiş (örneğin log temizlemek için). `find` aracının `-exec` yeteneği vardır; yani bir dosya bulunca komut çalıştırabilir. Kullanıcı `find` ile `-exec` üzerinden bir shell çağırırsa, bu shell `sudo`'nun sağladığı root ayrıcalığıyla açılır. Sonuç: masum bir "dosya bul" izni, tam root erişimine dönüşür. Kök neden yine aynı: aracın niyet edilmeyen yan yeteneği (komut çalıştırma).

**SUID bit ile ayrıcalık yükseltme.** Bir binary'de SUID biti set edilmişse, o binary sahibinin (çoğunlukla root) ayrıcalığıyla çalışır. Eğer bu binary bir shell doğurabiliyor ya da keyfi dosya okuyabiliyorsa (`/etc/shadow` okumak gibi), saldırgan bunu ayrıcalık yükseltmek için kullanır. GTFOBins tam olarak "şu binary SUID ise, root'a şu çağrıyla ulaşılır" bilgisini kataloglar.

**Pager ve editörlerin shell'i.** `less`, `more`, `man`, `vi`/`vim` gibi araçlar içlerinden komut çalıştırma yeteneği taşır (örneğin `less` içinde `!komut` ile shell çağırma). Bir kullanıcı bunlardan birini ayrıcalıklı bağlamda açtığında (özellikle `sudo` ile ya da kısıtlı bir "restricted shell" içinde), aracın içindeki bu kaçış yolu (shell escape) hem kısıtlı kabuğu kırar hem de ayrıcalığı taşır.

**Yorumlayıcılar (interpreter'lar).** `python`, `perl`, `ruby`, `awk` gibi araçlar tanım gereği keyfi kod çalıştırır. `sudo python -c '...'` biçiminde tek satırlık bir çağrı, doğrudan root shell doğurabilir. Bu yüzden bir yorumlayıcıya `sudo` izni vermek, pratikte tam `sudo ALL` vermeye eşdeğerdir.

**Dosya okuma/yazma primitifleri.** `tar`, `cp`, `dd`, `tee`, `cat` gibi araçlar; ayrıcalıklı çalıştırıldıklarında hassas dosyaları okuyabilir ya da sistem dosyalarının (örneğin `/etc/passwd`, cron dosyaları, sudoers) üzerine yazabilir. Bu, doğrudan shell doğurmadan da ayrıcalık yükseltmenin bir yoludur: dosya yazma yeteneği + doğru hedef dosya = root.

## Sömürü/istismar mantığı: Saldırgan neden LotL'i tercih eder?

Saldırgan açısından LotL bir zorunluluk değil, **stratejik bir seçimdir** ve şu avantajları sunar:

**Görünmezlik (stealth).** Ana motivasyon budur. EDR/AV'nin, imzalı ve meşru bir sistem aracının çalışmasına alarm vermesi zordur. Saldırgan böylece tespit yüzeyini (detection surface) küçültür.

**Araç getirme ihtiyacının ortadan kalkması.** Kendi malware'ini indirmek hem tespit riski yaratır hem de ağ kısıtlamalarına takılabilir. Sistemde zaten olan araçları kullanmak bu riski sıfırlar. "Ne kadar az iz, o kadar iyi" ilkesi.

**Application allowlisting'i atlatma.** Sadece imzalı/onaylı binary'lerin çalışmasına izin veren sıkı ortamlarda bile, LOLBIN'ler zaten onaylı listede olduğu için kod çalıştırmanın yolunu açarlar.

**Atıf zorluğu (attribution).** Özel malware, geliştiricinin izlerini (kod stili, altyapı, TTP) taşır ve threat intelligence ile bir gruba bağlanabilir. Sistem araçlarını kullanmak bu izleri siler; hangi grubun `certutil` çağırdığını ayırt etmek çok zordur.

**Yaşam döngüsünün her aşamasında kullanım.** LotL yalnızca ilk erişimde değil; keşif (WMI/net komutları), kod çalıştırma (mshta/PowerShell), ayrıcalık yükseltme (GTFOBins), kalıcılık (WMI/BITS/scheduled task), yatay hareket (WMI/PsExec-benzeri) ve veri sızdırma (certutil encode) dahil kill chain'in tamamına yayılır.

Buradan çıkan savunmacı ders şudur: LotL'yi tek bir noktada "engellemek" mümkün değildir çünkü aracın kendisi meşrudur. Savunma, aracın **nasıl, hangi bağlamda, hangi ebeveyn süreçle (parent process), hangi argümanlarla** çağrıldığına bakan davranışsal (behavioral) yaklaşımı gerektirir.

## Savunma: Meşru araç kötüye kullanımını nasıl tespit ve engellersiniz?

Savunma çok katmanlıdır çünkü tek bir sihirli çözüm yoktur. Temel prensip **davranış ve bağlam** izlemektir, imza değil.

**1. Ebeveyn-çocuk süreç ilişkisi (process ancestry).** LotL tespitinin en güçlü sinyali, sürecin **kim tarafından doğurulduğudur**. `winword.exe` (Word) ya da `outlook.exe`'nin bir çocuğu olarak `powershell.exe` ya da `mshta.exe` çalışıyorsa, bu neredeyse her zaman kötü amaçlıdır; çünkü bir ofis belgesinin PowerShell doğurması normal iş akışı değildir. Benzer şekilde bir web sunucusu sürecinin (w3wp, nginx) bir shell doğurması, web shell istismarının klasik göstergesidir. Burada araç meşru olsa da **bağlam anormaldir**.

**2. Komut satırı argümanı analizi.** Aracın kendisi değil, **nasıl çağrıldığı** ele verir. `certutil`'in bir `http://` URL'siyle çağrılması, PowerShell'in `-EncodedCommand`/`-nop -w hidden` gibi tipik saldırgan bayraklarıyla çağrılması, `regsvr32`'nin uzak bir scriptlet'e işaret etmesi güçlü tespit sinyalleridir. Bu yüzden komut satırı loglamasını (Windows'ta process creation + command line auditing, Sysmon Event ID 1) etkinleştirmek şarttır.

**3. Zengin loglama ve görünürlük.** Windows tarafında: PowerShell **script block logging** ve **module logging**, Sysmon, gelişmiş süreç denetim politikaları. **AMSI**, encode edilmiş/gizlenmiş script'i çalıştırma anında çözülmüş haliyle güvenlik ürününe sunarak fileless kod tespitinde kritik rol oynar. Unix tarafında: `auditd`, `sudo` loglaması, shell geçmişi ve exec izleme (execve syscall auditing) LotL etkinliğini görünür kılar.

**4. Uygulama allowlisting'i ve LOLBIN kısıtlaması.** WDAC (Windows Defender Application Control) ve AppLocker ile yalnızca onaylı binary'leri çalıştırmak temeldir; ancak bunun ötesinde, **bilinen LOLBIN'lerin bloklanması** gerekir. Microsoft, kötüye kullanılabilen sürücü ve binary'ler için önerilen **blocklist** kuralları yayımlar. İhtiyaç duyulmayan araçları (örneğin `mshta`, kimi eski bileşenler) tamamen engellemek saldırı yüzeyini azaltır.

**5. En az ayrıcalık ve GTFOBins sertleştirmesi.** Unix tarafında en etkili savunma, `sudo` izinlerini **sıkı ve spesifik** tutmaktır. Bir kullanıcıya asla bir yorumlayıcıya (`python`, `perl`), bir editöre (`vi`), bir pager'a (`less`) ya da `-exec` yeteneği olan araçlara (`find`, `awk`, `tar`) sınırsız `sudo` verilmemelidir. SUID biti olan binary'ler düzenli denetlenmeli, gereksiz olanlar kaldırılmalıdır. Bir `sudo` kuralı yazmadan önce o binary'nin GTFOBins'te bir kaçış yolu olup olmadığı mutlaka kontrol edilmelidir.

**6. Ağ tabanlı tespit.** LotL indirmeleri ve C2 trafiği meşru araçlardan çıksa da, hedeflenen **domain/IP itibarı**, olağandışı çıkış bağlantıları ve DNS anomalileri ağ katmanında yakalanabilir. `certutil`'in bir sistem sürecinden beklenmedik bir dış IP'ye bağlanması, süreç meşru olsa da ağda anormaldir.

**7. Davranışsal EDR ve tehdit avı (threat hunting).** Modern EDR'ler, tekil olayları değil, olay zincirlerini (behavioral chains) puanlar: "belge açıldı → PowerShell doğdu → şifreli komut çalıştı → dış bağlantı kuruldu" zinciri, her adım tek başına masum olsa da toplamda yüksek risklidir. Proaktif threat hunting'de MITRE ATT&CK çerçevesinin ilgili tekniklerini (özellikle T1218 - System Binary Proxy Execution ve ilgili alt teknikler) referans almak, avlanacak davranışları sistematik hale getirir.

## Yaygın hatalar

**"Antivirüsüm var, korunuyorum" yanılgısı.** İmza tabanlı AV, fileless LotL'ye karşı büyük ölçüde etkisizdir çünkü tarayacak kötü amaçlı dosya yoktur. Davranışsal EDR olmadan LotL'yi görmek çok zordur.

**Komut satırı loglamasını etkinleştirmemek.** Birçok kurum süreç oluşturma olaylarını loglar ama **komut satırı argümanlarını** loglamaz. Oysa LotL'de bütün kötü niyet argümanlardadır. Argüman olmadan log neredeyse değersizdir.

**PowerShell'i tamamen engellemeye çalışmak.** PowerShell meşru yönetim için gereklidir; kör bir yasak hem işi bozar hem de saldırganın PowerShell v2'ye düşürme (downgrade), `.NET` üzerinden doğrudan çağırma ya da başka bir LOLBIN'e geçme gibi atlatma yollarını görmezden gelir. Doğru yaklaşım engellemek değil, **kısıtlamak ve loglamaktır** (Constrained Language Mode, AMSI, script block logging).

**Sudo izinlerini "kolaylık" için gevşek vermek.** GTFOBins bağlamındaki en yaygın gerçek dünya hatası budur. "Kullanıcı sadece log dosyası düzenlesin diye `sudo vi` verdim" gibi izinler, doğrudan root shell'e giden kapılardır. Bir araca `sudo` vermeden önce onun shell escape yeteneği sorgulanmalıdır.

**SUID binary'lerini denetlememek.** Sisteme kurulan üçüncü parti yazılımlar bazen gereksiz yere SUID binary bırakır. Bu binary'ler GTFOBins'te listeliyse, tam bir yerel ayrıcalık yükseltme (LPE) yoludur. Düzenli SUID envanteri şarttır.

**LOLBIN blocklist'ini güncel tutmamak.** Yeni LOLBIN'ler sürekli keşfedilir. Bir kez yazılan blocklist yeterli değildir; LOLBAS/GTFOBins projeleri ve satıcı önerileri düzenli izlenmelidir.

**Bağlamı görmezden gelip yalnızca binary adına odaklanmak.** "certutil çalıştı" tek başına alarm üretmek gürültü yaratır (meşru kullanım vardır). Doğru tespit, **certutil + URL argümanı + anormal ebeveyn** gibi bağlamsal korelasyondur.

## En iyi pratikler

**Görünürlüğü maksimize edin.** Sysmon (iyi bir konfigürasyonla), PowerShell script block/module logging, komut satırı denetimi, Unix'te `auditd` ve `execve` izleme. Göremediğiniz şeyi savunamazsınız; LotL'de savunmanın ilk adımı zengin telemetridir.

**Süreç soyağacına (process ancestry) dayalı tespit kuralları yazın.** "Ofis uygulaması → script yorumlayıcı", "web sunucusu → shell", "sistem servisi → dış ağ bağlantısı" gibi anormal ebeveyn-çocuk zincirlerini yakalayan kurallar, LotL tespitinin en yüksek getirili yatırımıdır.

**En az ayrıcalık ilkesini titizlikle uygulayın.** Özellikle Unix'te `sudo` kurallarını mümkün olan en dar biçimde yazın; yorumlayıcılara, editörlere, pager'lara ve komut çalıştırabilen araçlara ayrıcalıklı erişim vermekten kaçının. Her `sudo` ve her SUID binary'sini GTFOBins gözüyle denetleyin.

**Uygulama denetimini (WDAC/AppLocker) LOLBIN blocklist ile birleştirin.** Yalnızca imzalı binary'lere izin vermek yetmez; bilinen kötüye kullanılabilir binary'leri (ve Microsoft'un önerdiği sürücü/binary blocklist'ini) da engelleyin. Kullanılmayan riskli bileşenleri sistemden kaldırın ya da bloklayın.

**AMSI ve fileless tespit yeteneklerini etkin tutun.** Bellekte çalışan, şifrelenmiş/gizlenmiş script'i çalışma anında görmenin başlıca yolu AMSI'dir. AMSI bypass girişimlerini de ayrı bir tespit sinyali olarak izleyin.

**MITRE ATT&CK ile eşleyin ve düzenli threat hunting yapın.** LotL tekniklerini ATT&CK'e haritalayarak tespit boşluklarınızı sistematik biçimde kapatın; özellikle "System Binary Proxy Execution" ailesini av senaryolarınıza dahil edin. Tekil olay değil, davranış zinciri avlayın.

**LOLBAS ve GTFOBins projelerini sürekli takip edin.** Bu iki proje hem saldırganın hem savunmacının başvuru kaynağıdır. Yeni eklenen binary'ler için tespit ve engelleme kurallarınızı güncel tutun; kırmızı takım (red team) tatbikatlarında bu araçlarla tespit kabiliyetinizi test edin.

**Katmanlı düşünün.** Tek bir kontrol LotL'yi durdurmaz. Görünürlük + davranışsal tespit + en az ayrıcalık + uygulama denetimi + ağ izleme katmanlarının birleşimi, meşru araçların kötüye kullanımını hem güçleştirir hem de gerçekleştiğinde görünür kılar. LotL'de zafer, "engellemek" değil çoğu zaman "hızlı görmek ve daraltmaktır".

## Özet

Living off the Land, saldırganın kendi silahını getirmek yerine sistemin meşru, imzalı araçlarını istismar etmesidir. Bunu mümkün kılan kök neden, bu araçların genel amaçlı güçlü yetenekleri (kod çalıştırma, dosya indirme, shell doğurma) ile güvenlik modellerinin imza/güven temelli olmasıdır. Sonuç, fileless çalışabilen ve olağan sistem gürültüsü içinde erimiş, tespiti son derece zor bir saldırıdır. Savunma imzaya değil **davranış, bağlam ve en az ayrıcalık** ilkesine dayanmalıdır: süreç soyağacı analizi, komut satırı loglaması, AMSI, uygulama denetimi, LOLBIN/SUID/sudo sertleştirmesi ve sürekli tehdit avı. LOLBAS ve GTFOBins projeleri, bu mücadelede hem tehdidi anlamanın hem de savunmayı kurmanın vazgeçilmez başvuru kaynaklarıdır.
