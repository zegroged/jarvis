# RDP Güvenliği: BlueKeep, Session Hijacking, CredSSP/NLA ve RDP Üzerinden Pivoting

## Giriş: Neden RDP Bu Kadar Kritik Bir Saldırı Yüzeyi?

Remote Desktop Protocol (RDP), Windows sistemlere grafik arayüz üzerinden uzaktan erişim sağlayan, Microsoft'un mülkiyetinde olan bir protokoldür (varsayılan port TCP 3389). Kurumsal ortamlarda sistem yöneticileri, yardım masası personeli ve uzaktan çalışan kullanıcılar için birincil erişim yöntemi olduğundan, RDP hem meşru yönetim trafiğinin hem de saldırganların en çok tercih ettiği giriş noktalarından birinin kesişim noktasıdır.

Bu konunun bir eğitim korpusunda mutlaka yer alması gerekir çünkü RDP, modern saldırı zincirlerinin neredeyse her aşamasında karşımıza çıkar: ilk erişim (internete açık RDP servislerine kaba kuvvet veya çalıntı kimlik bilgileriyle giriş), yanal hareket (bir iç ağda RDP ile makineden makineye atlama), kalıcılık (RDP oturum kaçırma ile meşru bir kullanıcı kimliği altında saklanma) ve komuta-kontrol/pivoting (RDP tüneli üzerinden ağın derinliklerine inme). Fidye yazılımı (ransomware) operasyonlarının büyük çoğunluğunun kök nedeni analizlerinde, internete açık ve zayıf korunan RDP servisleri en sık rastlanan ilk giriş vektörü olarak öne çıkar. Bu nedenle RDP güvenliğini anlamak, hem saldırı yüzeyini daraltmak hem de saldırı sonrası izleri doğru okuyabilmek için savunma mühendisliğinin temel taşlarından biridir.

Bu makale dört ana ekseni ele alır: (1) protokolün kök nedenden kaynaklanan zafiyet sınıfı olarak BlueKeep benzeri RCE (remote code execution) açıkları, (2) RDP session hijacking (oturum kaçırma), (3) kimlik doğrulama katmanındaki CredSSP/NLA mekanizmaları ve bunların atlatılması, (4) RDP'nin bir pivoting/proxying aracı olarak kötüye kullanılması.

## Kısım 1: BlueKeep ve RDP'de Uzaktan Kod Çalıştırma Zafiyetleri

### Tanım

BlueKeep, RDP protokolünün temelini oluşturan Windows bileşeni olan Remote Desktop Services (eski adıyla Terminal Services) içindeki bir **pre-authentication** (kimlik doğrulamadan önce tetiklenebilen) uzaktan kod çalıştırma zafiyetidir. "Pre-auth" niteliği kritik önemdedir çünkü saldırganın hiçbir kimlik bilgisine ihtiyaç duymadan, sadece protokolün ilk el sıkışma (handshake) aşamasında özel hazırlanmış paketler göndererek sistemde kod çalıştırabilmesi anlamına gelir. Bu, zafiyeti "wormable" (solucan gibi kendi kendine yayılabilir) sınıfına sokar; 2017'deki WannaCry/EternalBlue benzeri bir küresel yayılma potansiyeli taşıdığı için sektörde geniş yankı uyandırmıştır.

### Kök Neden / Çalışma Mantığı

RDP protokolü, çok sayıda "kanal" (virtual channel) üzerinden veri taşıyan katmanlı bir yapıya sahiptir: alt katmanda ağ taşıma (TPKT/X.224), üstünde T.125 MCS (Multipoint Communication Service) katmanı bulunur. MCS katmanı, aynı RDP oturumu içinde birden fazla sanal kanalın (ses, pano, dosya paylaşımı gibi) çoklanmasını (multiplexing) yönetir ve bu kanallara **kanal ID'leri** atar.

BlueKeep tipi zafiyetlerin kök nedeni, bu kanal yönetiminde bellek yaşam döngüsü (memory lifecycle) hatalarıdır: sunucu tarafı kod, bir kanalın bağlantısı kesildiğinde veya beklenmeyen bir sırada istek geldiğinde, ilgili bellek nesnesini serbest bırakır fakat bu nesneye tutan başka bir referansı (pointer) temizlemeyi unutur. Sonuç, klasik bir **use-after-free** durumudur: bellek serbest bırakılmış, işletim sistemi o alanı başka bir amaçla yeniden kullanabilir hale gelmiş, ama eski kod yolu hâlâ o adrese erişmeye çalışır. Saldırgan, serbest bırakılan belleği kontrollü içerikle (saldırgan tarafından seçilmiş verilerle) yeniden doldurmayı (heap grooming/feng shui) başarabilirse, "free" edilmiş nesnenin sanal fonksiyon tablosu (vtable) gibi kritik alanlarını kendi seçtiği değerlerle değiştirebilir ve bu da kontrol akışını ele geçirmesine (kod çalıştırma) yol açar.

Bunun mümkün olmasının arkasındaki daha derin sebep, RDP'nin tasarım döneminde (1990'ların sonu) güvenlik varsayımlarının bugünkünden çok farklı olmasıdır: protokol, "kurumsal güvenilir ağ içinde çalışır" varsayımıyla tasarlanmış, girdi doğrulama (input validation) ve durum makinesi (state machine) sıkılığı bugünün standartlarının gerisinde kalmıştır. Kanal numaraları, bağlantı durumları gibi düşük seviye protokol detaylarının doğrulanması eksik veya gevşek bırakılmış, bu da yıllar sonra keşfedilen bu tür zafiyetlerin temelini oluşturmuştur.

### Kavramsal Olarak Nasıl Çalışır

1. Saldırgan hedef sisteme kimlik doğrulaması yapmadan bir RDP bağlantısı başlatır (X.224 Connection Request aşaması).
2. MCS katmanında, normalde belirli bir sırayla açılması/kapanması gereken sanal kanallarla ilgili beklenmeyen bir istek dizisi gönderir (örneğin bir kanalı normalde olmayacak bir noktada serbest bıraktırır).
3. Sunucu tarafı, serbest bırakılan bellek nesnesine hâlâ referans tutan bir kod yolunu tetikler.
4. Saldırgan, bu boşluğu kendi kontrolündeki veriyle doldurarak (heap grooming) sunucunun bu "hayalet" nesneyi kendi hazırladığı veri gibi yorumlamasını sağlar.
5. Bu veri kontrol akışını (fonksiyon işaretçisi/vtable) saldırganın seçtiği bir konuma yönlendirir; sonuç olarak SYSTEM ayrıcalıklarıyla (RDP servisi genelde SYSTEM altında çalışır) kod çalıştırma elde edilir.

Bu adımların tamamı **kimlik doğrulama olmadan** ağ üzerinden gerçekleşir — saldırganın herhangi bir kullanıcı adı/parola bilmesi gerekmez, sadece hedef port 3389'a erişimi olması yeterlidir.

### Tespit

- **Ağ tabanlı tespit:** RDP trafiğinde MCS katmanı seviyesinde anormal kanal açma/kapama dizileri, protokol durum makinesine aykırı paket sıraları için imzalar (Snort/Suricata gibi IDS/IPS çözümlerinde yayınlanan RDP-özel kurallar). Ancak RDP genelde TLS ile şifrelendiğinden (Enhanced RDP Security), ağ tabanlı derin paket incelemesi (deep packet inspection) sınırlı olabilir; şifreleme öncesi el sıkışma kısmı yine de gözlemlenebilir.
- **Host tabanlı tespit:** `TermService` (Remote Desktop Services) sürecinin çökmesi veya beklenmeyen şekilde yeniden başlaması olay günlüklerinde (Windows Event Log, System/Application log) anomalili bir sinyal olabilir. EDR ürünleri, `svchost.exe` (TermService barındıran) sürecinde beklenmeyen bellek bozulması kalıplarını veya şüpheli bellek sayfası izinleri değişikliklerini (RWX bellek tahsisi gibi) tespit edebilir.
- **Zafiyet tarama/envanter tabanlı tespit:** Yama seviyesi ve build numarası bilgisiyle sistemlerin etkilenip etkilenmediğini belirlemek — bu, en güvenilir "tespit" yöntemidir çünkü exploit'in kendisini ağdan yakalamaya çalışmaktan çok daha az yanlış negatif üretir.
- **Honeypot/Canary yaklaşımı:** İzole bir ortamda kasıtlı olarak yamasız bir RDP sunucusu (canary) çalıştırıp bu sisteme yönelik herhangi bir bağlantı denemesini yüksek öncelikli alarm olarak işaretlemek, ağda BlueKeep tarzı bir tarama/istismar denemesinin erken sinyalini verebilir.

### Savunma

- **Yamalama en birincil savunmadır.** Bu sınıf zafiyetler protokolün temel bileşenlerinde olduğu için, satıcı (Microsoft) tarafından yayınlanan güvenlik güncellemelerinin zamanında uygulanması tartışmasız en etkili önlemdir. Desteği sona ermiş eski işletim sistemleri (örneğin uzun süredir güncelleme almayan sürümler) için üretici bazen istisnai olarak eski sürümlere de yama yayınlamıştır — bu, zafiyetin ciddiyetinin bir göstergesidir.
- **Network Level Authentication (NLA) zorunlu kılmak** — BlueKeep özelinde önemli bir azaltıcı etkendir çünkü NLA, TCP bağlantısı kurulur kurulmaz ama RDP protokol oturumu tam olarak başlamadan önce kimlik doğrulamasını öne çeker. Bu, saldırganın pre-auth zafiyeti tetikleyebileceği kod yoluna kimlik doğrulamadan ulaşmasını engeller (NLA detayları Kısım 3'te ele alınıyor).
- **RDP'yi asla doğrudan internete açmamak.** RDP portunu (3389) genel internetten erişilebilir bırakmak, tek başına en yaygın ve en önlenebilir hatadır. Bunun yerine VPN, bastion host/jump server, veya ters proxy tabanlı erişim ağ geçitleri (Remote Desktop Gateway gibi) arkasına almak gerekir.
- **Ağ segmentasyonu ve güvenlik duvarı kuralları** ile RDP erişimini sadece belirli yönetim ağlarından/IP bloklarından gelen trafikle sınırlamak.
- **Saldırı yüzeyini azaltma:** RDP servisine ihtiyaç duymayan sistemlerde servisin tamamen kapatılması.

### Yaygın Hatalar

- "NLA açık, o zaman güvendeyim" yanılgısı: NLA, birçok pre-auth RCE senaryosunu azaltır ama tüm RDP zafiyet sınıflarına karşı evrensel bir kalkan değildir; savunma derinliği (defense in depth) prensibiyle yamalama ile birlikte uygulanmalıdır.
- Yalnızca dış sınır güvenlik duvarına güvenip iç ağda RDP'yi serbest bırakmak — yanal hareket senaryolarında bir uç nokta ele geçirildiğinde saldırganın iç ağda serbestçe RDP ile dolaşabilmesine yol açar.
- Yama yönetiminde "kritik olmayan" olarak sınıflandırıp ertelemek; RDP bileşenleri işletim sisteminin çekirdek ayrıcalık seviyesine yakın çalıştığından risk her zaman yüksektir.

## Kısım 2: RDP Session Hijacking (Oturum Kaçırma)

### Tanım

RDP session hijacking, bir saldırganın zaten kimliği doğrulanmış ve aktif ya da kopmuş (disconnected) durumda olan başka bir kullanıcının RDP oturumunu ele geçirerek, o kullanıcının parolasını bilmeden onun oturumuna (ve dolayısıyla erişim haklarına) geçmesidir. Bu saldırı genellikle bir sistemde zaten yönetici (yerel yönetici veya SYSTEM) ayrıcalığı elde etmiş bir saldırganın, o makinede oturumu açık bırakılmış (örneğin bir domain admin'in yardım masası çağrısı sırasında bağlanıp bağlantıyı kapatmadan ayrıldığı) başka bir hesabın kimliğine bürünmesiyle gerçekleşir.

### Kök Neden / Çalışma Mantığı

Windows'ta Terminal Services altyapısı, her oturumu bir **session ID** ile temsil eder ve bir kullanıcı RDP bağlantısını kapatmadan (disconnect) ayrıldığında, oturum sunucuda "askıda" (disconnected ama aktif) kalmaya devam eder — süreçleri çalışır durumda, kimlik doğrulama belirteçleri (token) bellekte tutulur.

Kök neden burada **ayrıcalık modelinin asimetrisidir**: yerel SYSTEM veya yerel yönetici ayrıcalığına sahip bir süreç, o makinedeki diğer tüm oturumların session context'ine (bağlam) geçiş yapma yetkisine sahiptir. Bu, işletim sisteminin tasarımı gereği meşru bir yönetim özelliğidir (yöneticinin bir kullanıcının oturumuna teknik destek amacıyla bağlanabilmesi için). Ancak bu meşru mekanizma, saldırgan bir şekilde yerel SYSTEM/yönetici ayrıcalığı kazandığında, kimlik bilgisi hırsızlığına (credential theft) hiç gerek kalmadan doğrudan başka bir kullanıcının — özellikle de o makineye daha önce bağlanmış bir **domain admin**'in — oturumuna "atlamasını" sağlayan bir yol haline gelir.

Bunun özellikle tehlikeli olmasının nedeni, klasik kimlik bilgisi hırsızlığı (credential dumping, pass-the-hash) tekniklerinin aksine, session hijacking'in parola hash'i veya Kerberos bileti gibi bir "kanıt" çalmaya ihtiyaç duymamasıdır — doğrudan işletim sisteminin oturum yönetim API'lerini kullanarak zaten kimliği doğrulanmış bir bağlamın "içine" geçilir. Bu da EDR/AV çözümlerinin kimlik bilgisi hırsızlığına özel imzalarını atlatabilir.

### Kavramsal Olarak Nasıl Çalışır

1. Saldırgan bir uç noktada (genellikle yanal hareketin bir sonucu olarak) yerel SYSTEM veya yönetici ayrıcalığı elde eder.
2. Sistemdeki aktif/kopuk oturumları listeler (hangi kullanıcıların session ID'lerinin var olduğunu görür).
3. Yerleşik işletim sistemi araçları veya API çağrıları aracılığıyla, kendi sürecinin bağlamını hedef session ID'ye geçirir — bu işlem tipik olarak SYSTEM ayrıcalığı gerektirir.
4. Sonuç: saldırgan artık o kullanıcının (örn. domain admin) masaüstü bağlamında, o kullanıcının açık kimlik doğrulama token'larıyla işlem yapabilir hale gelir; parolasını hiç bilmeden o kullanıcının ağ kaynaklarına erişim haklarını miras alır.

Ayrıca ilgili bir varyant, **RDP shadowing** (Windows'un yerleşik "gölgeleme/oturum izleme" özelliği) yanlış yapılandırılırsa, ilke gereği kullanıcı onayı istemeden bir başka kullanıcının oturumunu sessizce izlemeye/kontrol etmeye izin verebilir — bu da meşru bir uzaktan yardım özelliğinin kötüye kullanımına örnektir.

### Tespit

- **Oturum geçiş olayları:** Windows güvenlik günlüklerinde oturum bağlanma/koparma (logon/disconnect) olayları ve özellikle bir SYSTEM/yönetici bağlamından başka bir kullanıcı oturumuna geçiş anlamına gelebilecek session-switch ilişkili olay ID'lerinin izlenmesi.
- **Anomali tabanlı davranış analizi:** Bir kullanıcının oturumunun, o kullanıcı hiçbir kimlik doğrulama (logon) olayı üretmeden aniden aktif hale gelmesi — yani "yeni bir logon yok ama oturum aktifleşti" deseni güçlü bir şüphe sinyalidir.
- **Süreç soy ağacı (process lineage) analizi:** Yönetici ayrıcalıklı bir sürecin, oturum yönetimiyle ilgili sistem API'lerini/araçlarını çağırdıktan hemen sonra başka bir kullanıcının masaüstü bağlamında yeni süreçlerin (özellikle etkileşimli shell veya GUI süreçleri) ortaya çıkması.
- **EDR telemetrisi:** Session ID değişimlerini ve token/impersonation API çağrılarını izleyen davranışsal kurallar; MITRE ATT&CK çerçevesinde bu teknik "Remote Service Session Hijacking: RDP Hijacking" olarak sınıflandırılır ve kurumsal EDR/SIEM ürünlerinde bu tekniğe özel tespit içerikleri (detection content) bulunur.

### Savunma

- **En az ayrıcalık (least privilege) ve ayrıcalıklı hesap hijyeni:** Domain admin gibi yüksek ayrıcalıklı hesapların, günlük iş istasyonlarına veya paylaşımlı sunuculara RDP ile bağlanmaması — bunun yerine tiered admin modeli (katmanlı yönetim modeli, örn. Microsoft'un "Tiering" / PAW - Privileged Access Workstation modeli) uygulanması.
- **Oturum kapatma disiplini:** Kullanıcıların RDP oturumlarını "disconnect" yerine "log off" ile tamamen sonlandırmasının politika ve teknik olarak (grup ilkesiyle otomatik oturum sonlandırma zaman aşımı) zorunlu kılınması.
- **RDP shadowing özelliğinin kısıtlanması:** Gerekmiyorsa devre dışı bırakmak; gerekiyorsa yalnızca kullanıcı onayı gerektiren modda (sessiz/onaysız izleme kapalı) yapılandırmak.
- **Yerel yönetici ayrıcalıklarının sıkı kontrolü:** Session hijacking'in ön koşulu yerel SYSTEM/yönetici erişimidir; bu nedenle uç nokta sıkılaştırma (endpoint hardening), LAPS (Local Administrator Password Solution) benzeri yerel yönetici parola rotasyonu ve ayrıcalık yükseltmeyi (privilege escalation) zorlaştıran önlemler dolaylı olarak bu saldırıyı da engeller.

### Yaygın Hatalar

- Yönetici hesaplarının "hızlı bağlanıp iş bitince pencereyi kapatma" alışkanlığı — bu, disconnected oturumları arkada bırakır ve saldırgana zaman kazandırır.
- Paylaşımlı/çok kullanıcılı sunucularda (örn. Jump server, Terminal Server) farklı ayrıcalık seviyesindeki kullanıcıların aynı sistemde oturum açmasına izin vermek.

## Kısım 3: CredSSP ve NLA — Kimlik Doğrulama Katmanı ve Atlatma Senaryoları

### Tanım

**CredSSP** (Credential Security Support Provider), RDP istemcisinin kullanıcı kimlik bilgilerini, tam RDP oturumu başlamadan önce sunucuya güvenli bir şekilde iletmesini sağlayan bir SSP (Security Support Provider) katmanıdır. **NLA** (Network Level Authentication), CredSSP'yi kullanarak kimlik doğrulamasını RDP protokol el sıkışmasının çok öncesine, TCP bağlantısı kurulur kurulmaz gerçekleştiren bir güvenlik özelliğidir.

### Kök Neden / Tasarım Mantığı

NLA'nın var olma sebebinin kökeninde şu problem yatar: klasik (NLA'sız) RDP akışında, istemci önce tam bir RDP protokol oturumu (grafik masaüstü ortamı dahil) kurar ve kimlik doğrulama bu oturumun **içinde**, Windows logon ekranı üzerinden yapılır. Bu, kimliği doğrulanmamış bir bağlanan tarafın bile sunucuda önemli miktarda kaynak (bellek, işlemci, oturum nesnesi) tüketen bir ortamın oluşmasına neden olur — hem DoS (Denial of Service) riski hem de Kısım 1'de anlatılan türden pre-auth zafiyetlerin saldırı yüzeyini genişletir.

NLA'nın kök çözümü şudur: kimlik doğrulamasını CredSSP aracılığıyla **protokol seviyesinde çok daha erken** bir noktaya, TLS/SSP el sıkışması sırasına taşımak. Böylece kimliği doğrulanmamış bir bağlantı, tam RDP oturum nesnesinin oluşturulmasına neden olmadan reddedilir. Bu hem kaynak tüketimini azaltır hem de saldırı yüzeyinin büyük bir kısmını (özellikle Kısım 1'deki gibi RDP protokolünün üst katmanlarında yatan zafiyetleri) kimlik doğrulama duvarının arkasına iter.

CredSSP'nin kendisi ise, kimlik bilgilerini SPNEGO (Kerberos/NTLM'i sarmalayan bir müzakere protokolü) üzerinden TLS ile korunan bir kanaldan taşır. Burada kritik bir tasarım detayı vardır: CredSSP, TLS oturumunu doğrulamak için kullanılan kanalın bütünlüğünü kriptografik olarak kimlik doğrulama sürecine bağlamalıdır (channel binding); aksi halde bir ortadaki adam (Man-in-the-Middle) saldırganı, TLS katmanını kendi sahte sertifikasıyla ikiye bölüp CredSSP müzakeresini röle edebilir (relay).

### Bilinen Bir Zafiyet Sınıfı: CredSSP Kanal Bağlama Zayıflığı

Geçmişte CredSSP'de, istemci ile sunucu arasındaki TLS/kanal doğrulamasının yeterince sıkı bağlanmaması nedeniyle bir saldırganın ortadaki adam konumundan CredSSP kimlik doğrulama müzakeresini araya girip röle edebildiği bir zafiyet sınıfı kamuya açıklanmıştır (bu tür zafiyetler genel olarak "CredSSP relay/MITM" olarak anılır). Kök neden, protokolün kimlik doğrulama adımlarını, altındaki taşıma katmanı (TLS) kimliğine kriptografik olarak yeterince sıkı bağlamamasıdır — yani "bu kimlik doğrulama tam olarak hangi TLS kanalı için yapılıyor" sorusunun cevabı saldırgan tarafından manipüle edilebilir hale gelmiştir. Bu tür zafiyetlerin kesin CVE numarasını veya etkilenen tam sürüm aralığını burada iddialı biçimde vermek yanıltıcı olur; önemli olan kavram: **kimlik doğrulama protokolleri, altlarındaki taşıma katmanına kriptografik olarak bağlanmazsa relay saldırılarına açık hale gelir** — bu, NTLM relay ve diğer birçok kimlik doğrulama protokolünde de tekrar eden evrensel bir zafiyet desenidir.

### Kavramsal Olarak Nasıl Çalışır (MITM/Relay Senaryosu)

1. Saldırgan, kurban istemci ile gerçek RDP sunucusu arasına ağ seviyesinde girer (ARP spoofing, sahte DNS, kötü amaçlı Wi-Fi erişim noktası gibi klasik MITM önkoşullarıyla).
2. Kurban istemci bağlantıyı başlattığında, saldırgan kendini sunucu gibi tanıtır ve kurbanla kendi TLS oturumunu kurar; aynı anda gerçek sunucuyla ayrı bir TLS oturumu kurar.
3. Eğer CredSSP kanal bağlama doğrulaması yeterince sıkı değilse, saldırgan kurbandan aldığı CredSSP kimlik doğrulama mesajlarını gerçek sunucuya ilettiğinde (relay), sunucu bunu meşru bir istemci doğrulaması olarak kabul edebilir.
4. Sonuç olarak saldırgan, kurbanın kimlik bilgilerini hiç görmeden (parolayı çözmeden) kurban adına sunucuya kimlik doğrulamış olur.

### Tespit

- **Sertifika/TLS anomalileri:** İstemci tarafında beklenmeyen sertifika değişiklikleri veya güven zinciri uyarıları (kullanıcıların bu uyarıları "her zamanki gibi tıklayıp geçme" alışkanlığı saldırının en büyük yardımcısıdır) — bu davranışın loglanması ve merkezi izlenmesi önemlidir.
- **Ağ seviyesinde ARP/DNS anomali tespiti:** MITM'in önkoşulu olan ARP spoofing veya sahte DNS yanıtlarının ağ izleme araçlarıyla (arp izleme, DHCP snooping, dinamik ARP inceleme) tespiti — saldırı CredSSP'ye özgü değil, önce ağ katmanında bir konumlanma gerektirir.
- **Kimlik doğrulama günlüklerinde tutarsızlık:** Aynı kullanıcı hesabı için beklenmeyen kaynak IP'lerden gelen ardışık kimlik doğrulama denemeleri, ya da CredSSP protokol sürüm uyuşmazlığı uyarılarının (varsa) merkezi loglanması.

### Savunma

- **CredSSP ve istemci/sunucu yamalarının güncel tutulması** — bu tür kanal bağlama zayıflıkları satıcı tarafından yayınlanan düzeltmelerle (hem istemci hem sunucu tarafında) giderilir; tek taraflı yama yeterli olmayabilir, her iki uçta da güncelleme gerekir.
- **NLA'nın her zaman zorunlu kılınması** — NLA olmadan CredSSP hiç devrede olmaz ve kimlik doğrulama tam RDP oturumu içinde (daha zayıf garantilerle) gerçekleşir.
- **Ağ katmanında MITM'i önlemek:** 802.1X gibi port tabanlı ağ erişim kontrolü, dinamik ARP incelemesi (Dynamic ARP Inspection), ve genel olarak yerel ağ segmentasyonu — çünkü CredSSP relay saldırısının ön koşulu, saldırganın zaten ağ trafiğini araya girecek bir konumda olmasıdır.
- **Sertifika doğrulamasını atlamamak:** RDP istemcisi tarafında sunucu sertifikası uyarılarının kullanıcılar tarafından körü körüne kabul edilmemesi için farkındalık eğitimi ve mümkünse ilke tabanlı (group policy) sertifika güven listesi zorunluluğu.

### Yaygın Hatalar

- NLA'yı sadece "eski istemcilerle uyumluluk sorunu çıkarıyor" diye devre dışı bırakmak — bu, hem BlueKeep benzeri pre-auth RCE'lere hem de daha zayıf kimlik doğrulama akışına kapı açar.
- Sertifika uyarılarını rutin bir "tıkla-geç" adımı haline getiren kurumsal kültür; bu durum, teknik kontrollerin en güçlü olduğu senaryolarda bile insan faktörü üzerinden MITM'e alan açar.
- CredSSP güncellemesini yalnızca sunucularda yapıp istemcilerde ihmal etmek (veya tersi) — protokol karşılıklı olduğundan iki tarafın da güncel olması gerekir.

## Kısım 4: RDP Üzerinden Pivoting ve Proxying

### Tanım

Pivoting, bir saldırganın ele geçirdiği bir sistemi, normalde doğrudan erişemeyeceği başka ağ segmentlerine veya sistemlere ulaşmak için bir "sıçrama tahtası" (basamak) olarak kullanmasıdır. RDP bağlamında pivoting, hem RDP'nin **kendisinin hedefi** olduğu (bir sistemden diğerine RDP ile atlamak) hem de RDP protokolünün **taşıyıcı** olarak kullanıldığı (RDP oturumu içinde dinamik sanal kanallar aracılığıyla trafik tünelleme) iki farklı senaryoyu kapsar.

### Kök Neden / Çalışma Mantığı

**Senaryo A — RDP'den RDP'ye zincirleme:** Kök neden, kurumsal ağlarda güven ilişkilerinin (trust relationships) ve kimlik bilgisi yeniden kullanımının (credential reuse) yaygınlığıdır. Bir saldırgan bir iş istasyonunda yerel yönetici parolasını veya bir kullanıcının kimlik bilgilerini ele geçirdiğinde, aynı kimlik bilgisinin (özellikle yerel yönetici parolaları kurumda standartlaştırılmışsa veya bir domain hesabının birçok sistemde oturum açma hakkı varsa) başka sistemlere RDP ile bağlanmak için doğrudan kullanılabilmesi, saldırganın ağda "yatay" ilerlemesini son derece kolaylaştırır. Kök neden teknik bir protokol zafiyeti değil, **kimlik ve erişim yönetimi mimarisindeki zayıflıktır**: aynı yerel yönetici hesabının/parolasının birçok makinede tekrarlanması, aşırı geniş RDP erişim izinleri, ve ağ segmentasyonu eksikliği.

**Senaryo B — RDP'yi bir tünelleme/proxy taşıyıcısı olarak kullanmak:** RDP protokolü, **dinamik sanal kanallar (dynamic virtual channels)** adı verilen, oturum içinde keyfi ikili veri taşıyabilen genişletilebilir bir alt yapıya sahiptir (dosya paylaşımı, pano, ses yönlendirme gibi meşru özellikler bu kanallar üzerinden çalışır). Kök neden, bu kanalların genel amaçlı bir veri taşıyıcı olarak tasarlanmış olması ve gidiş-geliş (bidirectional) veri akışına izin vermesidir. Bu, meşru bir tasarım kararıdır (uzantı/eklenti mimarisi için gereklidir) ama aynı zamanda kötüye kullanılabilir: eğer bir saldırgan zaten kurduğu bir RDP oturumu üzerinden bu kanalları kötüye kullanabilirse, RDP oturumunun **kendisini** bir SOCKS proxy veya genel TCP tüneli gibi kullanarak, güvenlik duvarının yalnızca 3389 portuna izin verdiği ama diğer tüm portları/protokolleri engellediği bir ortamda dahi ek trafiği bu tek izinli kanaldan geçirebilir.

Ayrıca ilgili bir kavram olan **RDP dosya/sürücü yönlendirme (drive redirection)** özelliği kötüye kullanılabilir: bir saldırgan, ele geçirdiği bir "atlama sunucusu" (jump server) üzerinden RDP ile bağlandığında, kendi yerel sürücülerini/araçlarını o oturuma yönlendirerek (drive mapping) sunucuya araç taşıyabilir — bu da bir tür veri/araç pivotudur ve genellikle uç nokta güvenlik kontrollerinin gözden kaçırdığı bir kanaldır.

### Kavramsal Olarak Nasıl Çalışır

1. Saldırgan bir "beachhead" (ilk ele geçirilen) sistemde kimlik bilgisi toplama (credential harvesting/dumping) gerçekleştirir.
2. Elde edilen kimlik bilgilerinin (özellikle yerel yönetici veya ayrıcalıklı bir domain hesabının) başka hangi sistemlerde geçerli olduğunu keşif (network/credential reconnaissance) yoluyla belirler.
3. RDP istemcisi üzerinden bu kimlik bilgileriyle bir sonraki sisteme bağlanır; bu sistem artık yeni bir "basamak" haline gelir.
4. Alternatif olarak, saldırgan RDP protokolünün dinamik sanal kanal mekanizmasını kullanan araçlarla (bu, genel bir tünelleme aracı sınıfıdır), RDP oturumunun içine gömülü bir SOCKS proxy veya port yönlendirme kanalı kurar; böylece güvenlik duvarının izin verdiği tek bir portun (3389) arkasından, normalde erişilemeyecek iç ağ servislerine trafik gönderebilir.
5. Bu zincir, saldırganın ilk erişim noktasından ağın en kritik/hassas bölgelerine (örn. domain controller, dosya sunucuları, yedekleme altyapısı) adım adım ilerlemesini sağlar — fidye yazılımı operasyonlarının şifreleme öncesi "keşif ve yayılma" aşamasının tam olarak bu şekilde çalıştığı gözlemlenmiştir.

### Tespit

- **Kimlik bilgisi kullanım grafiği (lateral movement graph) analizi:** Aynı hesabın kısa süre içinde birçok farklı hostta RDP logon (özellikle Type 10 - RemoteInteractive logon type) olayı üretmesi, özellikle bu hostlar arasında normalde bir iş ilişkisi olmayan makineler varsa, güçlü bir yanal hareket sinyalidir.
- **RDP bağlantı grafiklerinin taban çizgisiyle (baseline) karşılaştırılması:** Her kullanıcı/hesabın normal RDP bağlantı desenlerinin (hangi kaynaktan hangi hedefe, hangi saatlerde) profillenmesi ve bu profilden sapan bağlantıların (özellikle bir yardım masası hesabının aniden domain controller'a bağlanması gibi) alarm üretmesi.
- **Ağ akış (netflow) analizi ile anormal veri hacmi:** Bir RDP oturumunun beklenenden çok daha uzun süre açık kalması veya beklenenden çok daha fazla veri taşıması, oturumun tünelleme amacıyla kötüye kullanıldığının bir işareti olabilir.
- **Dinamik sanal kanal kullanımının izlenmesi:** Kurumsal ortamlarda hangi sanal kanalların (drive redirection, clipboard, vs.) kullanıldığını loglayan araçlar/EDR entegrasyonları ile beklenmeyen kanal türlerinin (özellikle üçüncü parti/özel kanal isimleri) tespiti.
- **MITRE ATT&CK haritalaması:** Bu davranışlar "Lateral Movement: Remote Services (RDP)" ve "Command and Control: Protocol Tunneling" teknik kategorileri altında sınıflandırılır; SIEM/threat hunting programlarında bu tekniklere özel av (hunt) sorguları oluşturulması önerilir.

### Savunma

- **Kimlik bilgisi hijyeni ve segmentasyon:** Yerel yönetici parolalarının her makinede benzersiz olması (LAPS benzeri çözümlerle), ayrıcalıklı hesapların katmanlı erişim modeliyle (tiering) sınırlandırılması — böylece bir sistemde ele geçirilen kimlik bilgisi başka sistemlere otomatik "anahtar" haline gelmez.
- **RDP erişiminin "jump server/bastion host" modeliyle merkezileştirilmesi:** Kullanıcıların doğrudan makineden makineye RDP atlaması yerine, tüm RDP erişiminin denetlenen, loglanan ve tek bir kontrol noktasından geçen bir bastion üzerinden yapılması; bu hem tespiti kolaylaştırır hem de zincirleme pivotu zorlaştırır.
- **Ağ segmentasyonu ve mikrosegmentasyon:** İş istasyonları arası (workstation-to-workstation) RDP trafiğinin güvenlik duvarı kurallarıyla varsayılan olarak engellenmesi — çoğu kurumsal ortamda kullanıcı makineleri birbirine RDP ile bağlanmaya ihtiyaç duymaz; bu trafiğin engellenmesi yanal hareketi önemli ölçüde kısıtlar.
- **Sürücü/pano yönlendirme gibi sanal kanal özelliklerinin ihtiyaç yoksa devre dışı bırakılması:** Özellikle ayrıcalıklı yönetim oturumlarında (PAW gibi) drive redirection, clipboard redirection gibi özelliklerin grup ilkesiyle kapatılması, veri/araç pivotu yollarını azaltır.
- **Çok faktörlü kimlik doğrulama (MFA):** RDP erişiminde MFA zorunluluğu, çalıntı tek bir kimlik bilgisinin doğrudan pivot için yeterli olmasını engeller.
- **Çıkış (egress) trafiği kontrolü:** RDP oturumu içinde tünellenen bir C2/proxy trafiğinin nihayetinde dışarıya çıkması gerekiyorsa, güvenlik duvarında/proxy'de sıkı egress filtreleme ve anormal dış bağlantı tespiti bu tür pivotların etkisini sınırlar.

### Yaygın Hatalar

- "RDP zaten iç ağda, dışarıdan gelinmiyor, güvenli" varsayımı — yanal hareketin büyük kısmı zaten iç ağdan iç ağa gerçekleşir; dış çevre güvenliği tek başına yeterli değildir.
- Bastion/jump server modelini kurup, ardından aynı bastion sunucusunun kendisini yeterince sıkılaştırmamak (örn. bastion üzerinde gereksiz yazılımlar, güncel olmayan yamalar) — bastion tek hata noktası (single point of failure) haline gelebilir.
- Ayrıcalıklı hesapların günlük iş istasyonlarında (kahve molası verirken kilitlemeyi unutma dahil) oturum açık bırakılması — bu, hem session hijacking (Kısım 2) hem de pivoting risklerini birleştiren klasik bir operasyonel hatadır.

## Sonuç: Savunma Mühendisi Gözüyle Bütünsel Yaklaşım

RDP güvenliği, tek bir kontrolle çözülebilecek bir problem değildir; katmanlı bir savunma gerektirir. Yamalama (BlueKeep sınıfı zafiyetlere karşı), kimlik doğrulama sıkılaştırma (NLA/CredSSP ve MFA), ağ mimarisi (segmentasyon, bastion modeli, RDP'nin asla internete doğrudan açılmaması) ve operasyonel disiplin (oturum kapatma alışkanlıkları, ayrıcalıklı hesap hijyeni) birlikte ele alınmalıdır. Tespit tarafında ise, tek bir olayın değil, **davranışsal desenlerin** (beklenmeyen session geçişleri, anormal RDP bağlantı grafikleri, taban çizgisinden sapan kimlik bilgisi kullanımı) izlenmesi, saldırganın protokolün meşru esnekliğinden (sanal kanallar, oturum yönetimi API'leri, CredSSP'nin kimlik bilgisi iletim mekanizması) faydalanarak sisteme uyum sağlamasına karşı en dayanıklı yaklaşımdır. RDP'nin fidye yazılımı operasyonlarında bu denli sık birincil giriş noktası olmasının altında yatan ortak payda, çoğu zaman karmaşık bir sıfırıncı gün (zero-day) zafiyeti değil, temel hijyen eksiklikleridir: yamasız sistemler, internete açık portlar, tekrarlanan yerel yönetici parolaları ve MFA'sız erişim. Bu nedenle RDP savunmasının en yüksek getirili yatırımı, genellikle en sofistike teknik kontrol değil, bu temel disiplinlerin tutarlı ve kurum genelinde uygulanmasıdır.
