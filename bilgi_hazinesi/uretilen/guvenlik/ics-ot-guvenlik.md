# ICS/OT Güvenliği — Genel Bakış

## Giriş: Neden IT güvenliği bilgisi burada yetmez

Endüstriyel Kontrol Sistemleri (ICS — Industrial Control Systems) ve daha geniş anlamıyla Operasyonel Teknoloji (OT — Operational Technology), fiziksel dünyayı yöneten bilişim sistemleridir. Bir su arıtma tesisindeki klor dozaj pompasını, bir elektrik şalt sahasındaki kesiciyi, bir petrokimya reaktörünün basınç vanasını ya da bir montaj hattındaki robot kolunu çalıştıran katman burasıdır. Klasik IT (Information Technology) dünyasında bir sunucu çöktüğünde en kötü ihtimalle veri kaybı veya hizmet kesintisi yaşanır; OT dünyasında bir kontrol döngüsü yanlış davrandığında türbin parçalanabilir, boru hattı patlayabilir, insan hayatı gidebilir. Bu temel fark, güvenliğe bakışı kökten değiştirir.

IT güvenliğinde önceliğin klasik sıralaması **CIA**'dır: Confidentiality (gizlilik), Integrity (bütünlük), Availability (erişilebilirlik). OT dünyasında bu piramit tersine döner ve genellikle **AIC** olur: önce erişilebilirlik ve güvenli süreklilik, sonra bütünlük, en sonda gizlilik. Bir SCADA operatörü için "sistemin sürekli ve öngörülebilir çalışması", verinin gizli kalmasından çok daha kritiktir. Bu makale, PLC/SCADA mimarisi, Modbus gibi endüstriyel protokoller, güvenlik (security) ile emniyet (safety) arasındaki hayati ayrım ve segmentasyon üzerinden OT güvenliğinin neden bu kadar farklı bir disiplin olduğunu açıklıyor.

## Bileşenler ve mimari: PLC, RTU, HMI, SCADA, DCS

### PLC — sahada karar veren mantık

**PLC (Programmable Logic Controller)**, sahadaki sensörlerden (sıcaklık, basınç, seviye, akış) girdi okuyup, içine yüklenmiş mantığa göre aktüatörlere (vana, motor, röle) çıktı veren dayanıklı bir gömülü bilgisayardır. PLC'nin çalışma mantığının kalbi **scan cycle** (tarama döngüsü) denen sonsuz döngüdür: girişleri oku → program mantığını (genellikle Ladder Logic, Structured Text veya Function Block ile yazılmış) çalıştır → çıkışları yaz → tekrar başa dön. Bu döngü milisaniyeler mertebesinde, deterministik bir zamanlamayla tekrar eder. Determinizm burada kritik kelimedir: PLC'nin bir kararı "ne zaman" vereceği, "ne verdiği" kadar önemlidir. Bir güvenlik çözümü bu döngüye gecikme (latency) veya belirsizlik (jitter) eklerse, kontrol süreci bozulur. IT dünyasında saniyelik gecikmeler tolere edilirken, OT'de birkaç milisaniyelik sapma bir dozaj hatasına dönüşebilir.

### RTU, HMI ve merkezi izleme

**RTU (Remote Terminal Unit)**, coğrafi olarak dağınık sahalarda (örneğin kilometrelerce uzanan bir doğalgaz hattı boyunca) veri toplayan ve merkeze ileten birimdir; işlevsel olarak PLC'ye benzer ancak telemetri ve uzak konum için optimize edilmiştir. **HMI (Human-Machine Interface)**, operatörün süreci gördüğü ve müdahale ettiği ekrandır — vanaların durumunu gösteren, alarm veren, komut girmeye izin veren arayüz.

**SCADA (Supervisory Control and Data Acquisition)** ise bunların üstündeki denetleme katmanıdır: coğrafi olarak dağılmış PLC/RTU'lardan veri toplar, merkezi bir yerde görüntüler ve operatöre denetleyici (supervisory) komut verme imkânı sağlar. SCADA "kontrolü" yapmaz — kontrolü PLC yapar; SCADA denetler ve yönlendirir. Bunun yanında **DCS (Distributed Control System)**, tek bir tesis (rafineri, enerji santrali) içindeki sıkı bağlı, sürekli süreçleri yönetmek için kullanılan, daha entegre bir mimaridir. SCADA "geniş alan, gevşek bağlı"; DCS "tek tesis, sıkı bağlı" diye kabaca ayrılabilir.

### Purdue modeli — neden katmanlı düşünülür

OT mimarisini anlamanın standart çerçevesi **Purdue Enterprise Reference Architecture** (Purdue modeli) ve onun ISA-95 uyarlamasıdır. Katmanlar kabaca şöyledir:

- **Level 0** — Saha aygıtları: sensörler, aktüatörler, motorlar.
- **Level 1** — Temel kontrol: PLC, RTU, kontrolörler.
- **Level 2** — Denetleme: SCADA sunucuları, HMI'lar, mühendislik iş istasyonları.
- **Level 3** — Site operasyonları: MES, tarihçe sunucuları (historian), üretim yönetimi.
- **Level 3.5** — **DMZ (Demilitarized Zone)**: IT ile OT arasındaki tampon bölge.
- **Level 4/5** — Kurumsal IT: ERP, e-posta, iş uygulamaları.

Bu model salt akademik değildir; segmentasyonun ve trafik akış kurallarının temelini oluşturur. "Level 4'teki bir kullanıcı doğrudan Level 1'deki bir PLC'ye konuşabilmeli mi?" sorusunun cevabı neredeyse her zaman "hayır"dır ve mimari bu ilkeyi zorlamak için kurgulanır.

## Kök neden: OT protokolleri neden savunmasız doğdu

OT güvenliğinin en derin kök nedeni tarihseldir. Bugün kullanılan endüstriyel protokollerin çoğu 1970'ler ve 1980'lerde tasarlandı. O dönemde bu sistemler fiziksel olarak izole, tescilli seri hatlar üzerinde çalışıyordu; bir saldırganın protokole erişmesi demek, zaten fiziksel olarak tesise girmiş olması demekti. Dolayısıyla tasarımcılar makul bir varsayımla **kimlik doğrulama (authentication), şifreleme (encryption) ve bütünlük kontrolü (integrity) eklemediler.** Protokol "ağdaki her aygıt güvenilir" varsayımı üzerine kuruluydu.

Sorun, bu protokollerin onlarca yıl sonra Ethernet ve TCP/IP üzerine taşınıp kurumsal ağlara, hatta zaman zaman internete bağlanmasıyla ortaya çıktı. Güvenlik varsayımı ("izole seri hat") ortadan kalktı, ama protokol aynı kaldı. İşte OT'nin temel açığı budur: **güvenlik, protokolün DNA'sında yok; sonradan sarılan bir katman olarak var.**

Bunu ağırlaştıran ikinci kök neden **uzun yaşam döngüsüdür**. Bir IT sunucusu 3-5 yılda yenilenir; bir PLC 15-25 yıl sahada kalabilir. Bu, on yıllar önce üretilmiş, güncelleme almayan, bilinen zafiyetleri kapatılmamış cihazların hâlâ kritik süreçleri çalıştırdığı anlamına gelir. Yama (patch) uygulamak da IT'deki kadar kolay değildir; çünkü sistemi durdurmak üretimi durdurmak demektir ve bir yama, doğrulanmamış davranış değişikliği getirerek emniyeti tehlikeye atabilir.

## Modbus örneği: bir protokolün anatomisi ve açıkları

**Modbus**, endüstride en yaygın protokoldür ve OT'nin güvenlik felsefesini örneklemek için mükemmel bir vakadır. 1979'da Modicon (bugün Schneider Electric) tarafından tasarlanmıştır. Modbus'ın çalışma mantığı basit bir **master/slave** (ya da güncel terminolojiyle client/server) modelidir: bir master aygıt sorgu gönderir, slave aygıt cevap verir. Modbus TCP versiyonunda bu trafik genellikle **TCP portu 502** üzerinden akar.

Bir Modbus mesajı temelde şu unsurları taşır: hedef aygıtın adresi, bir **function code** (fonksiyon kodu — ne yapılacağını söyler) ve veri. Fonksiyon kodları neyin okunup yazılacağını belirtir; örneğin bobin (coil) okuma/yazma, register okuma/yazma gibi işlemler ayrı kodlarla ifade edilir. Kritik nokta şudur: bu mesajda **kimlik doğrulama alanı yoktur, oturum kavramı yoktur, şifreleme yoktur, mesaj bütünlüğünü kriptografik olarak garanti eden bir imza yoktur.** Modbus TCP'de hata denetimi TCP'nin checksum'ına bırakılmıştır; bu checksum kazara bozulmalara karşıdır, kasıtlı manipülasyona karşı değildir.

### İstismar mantığı

Bu tasarımın doğal sonucu şudur: Modbus trafiğine erişebilen herkes, geçerli görünen komutlar üretebilir. Somut senaryolar:

- **Yetkisiz komut yazma:** Saldırgan, master gibi davranıp bir slave PLC'ye "şu bobini aç/kapat" ya da "şu register'a şu değeri yaz" komutu gönderebilir. Protokol bu komutun gerçek operatörden mi yoksa saldırgandan mı geldiğini ayırt edemez. Bir vananın açılması, bir pompanın durdurulması bu şekilde tetiklenebilir.
- **Sahte cevap / veri manipülasyonu:** Saldırgan araya girip (Man-in-the-Middle) HMI'a giden cevapları değiştirebilir. Operatör ekranında "her şey normal" görünürken saha gerçekte tehlikeli bir duruma sürükleniyor olabilir. Stuxnet vakasının felsefi özü buydu: operatöre yanlış "her şey yolunda" tablosu göstermek.
- **Keşif (reconnaissance):** Function code'ları tarayarak aygıt tipini, register haritasını ve süreç mantığını çıkarmak mümkündür. Bu, hedeflenmiş bir saldırının hazırlık aşamasıdır.
- **DoS (Denial of Service):** Yavaş yanıt veren, sınırlı işlemci gücüne sahip eski PLC'lere yoğun sorgu göndermek onları kilitleyebilir; bu da kontrol döngüsünün durması demektir.

### Savunma mantığı

Modbus'ın kendisini "güvenli" hale getiremeyeceğinizi kabul etmek, savunmanın başlangıç noktasıdır. Yaklaşımlar şöyle katmanlanır:

- **Ağ katmanında hapsetme:** Modbus trafiğinin yalnızca meşru master-slave çiftleri arasında, yalnızca 502 portunda akmasına izin verin. Firewall kurallarını "kaynak-hedef-port" üçlüsüyle sıkın. Kimin kime Modbus konuşabileceğini bir beyaz liste (whitelist) ile sabitleyin.
- **Protokol-farkında (protocol-aware) denetim:** Sıradan bir firewall "502 portu açık mı" der; endüstriyel **DPI (Deep Packet Inspection)** yapan bir firewall ise "bu Modbus mesajının function code'u yazma mı, okuma mı" diye bakar. Kritik yazma komutlarını yalnızca belirli kaynaklardan geçmeye izin verebilir, register aralıklarını sınırlayabilirsiniz.
- **Şifreli tünelleme:** Modbus'ı olduğu gibi bırakıp trafiği bir VPN/TLS tüneli içinden geçirmek, hat üzerinde dinleme ve araya girmeyi zorlaştırır. Ayrıca protokolün TLS ile korunan güncel bir varyantı da tanımlanmıştır; imkân varsa tercih edilmelidir.
- **Tek yönlü ağ geçitleri (data diode):** Historian gibi sadece "okuma" gereken senaryolarda, fiziksel olarak tek yönlü veri akışına izin veren donanımlar (data diode) kullanılabilir. Veri OT'den IT'ye akar ama IT'den OT'ye hiçbir paket fiziksel olarak dönemez.
- **İzleme:** OT ağ trafiğini pasif olarak dinleyip anormallik tespiti yapan sistemler, beklenmedik bir function code'u ya da yeni bir master'ın belirmesini alarma dönüştürebilir.

DNP3, EtherNet/IP, PROFINET, OPC gibi diğer protokoller detaylarda farklılaşsa da felsefi zafiyet benzerdir: eski nesil, kimlik doğrulaması zayıf, sonradan güvenlik giydirilen protokoller. DNP3'ün "Secure Authentication" uzantısı gibi iyileştirmeler mevcuttur ama sahada yaygınlığı sınırlıdır.

## Güvenlik (security) ile emniyet (safety): kritik ayrım

OT dünyasında en çok karıştırılan ama en hayati kavram çifti budur. İngilizcede ikisi de bazen "safety/security" diye ayrışır ama Türkçede özel dikkat gerekir:

- **Safety (emniyet):** Sistemin, arıza veya insan hatası durumunda bile insanlara ve çevreye zarar vermeyecek şekilde davranmasıdır. Bir kazanın aşırı basınçta otomatik ventil açması, bir asansörün fren sistemi, bir reaktörün acil soğutması emniyet fonksiyonlarıdır.
- **Security (güvenlik):** Sistemin kötü niyetli saldırıya karşı korunmasıdır.

Bu iki kavram tarihsel olarak farklı ekipler tarafından, farklı standartlarla yönetildi. Emniyet tarafında **SIS (Safety Instrumented System)** ve **SIL (Safety Integrity Level)** kavramları vardır; SIS, ana kontrol sisteminden bağımsız, tek işi "süreç tehlikeli bölgeye girerse onu güvenli duruma (safe state) getirmek" olan ayrı bir sistemdir. IEC 61508 ve süreç endüstrisi için IEC 61511 bu alanın standartlarıdır.

### Neden bu ayrım güvenlikte hayati oldu

Klasik anlayış, SIS'i ana kontrol sisteminden ayrı ve dokunulmaz sayıyordu: "Kontrol sistemi ele geçirilse bile, SIS bağımsız olduğu için felaketi önler." Bu varsayım, SIS'lerin de dijitalleşip ağa bağlanmasıyla çöktü. Bir saldırgan hem kontrol sistemini manipüle edip tehlikeli durum yaratır, hem de SIS'i devre dışı bırakır ya da manipüle ederse, son savunma hattı da düşer.

Bunun en çarpıcı örneği, bir güvenlik sisteminin doğrudan hedeflendiği **Triton/Trisis** olarak bilinen saldırıdır: Bir petrokimya tesisindeki emniyet sistemi kontrolörüne kötü amaçlı yazılım yerleştirilmeye çalışılmış, amaç emniyet fonksiyonunu manipüle ederek fiziksel felakete zemin hazırlamaktı. Bu vaka, "security" ile "safety"nin artık ayrılamaz olduğunu, bir emniyet sistemine yönelik bir siber saldırının doğrudan can güvenliği tehdidi anlamına geldiğini kanıtladı.

Buradaki mühendislik ilkesi şudur: **SIS ile BPCS (Basic Process Control System) mümkün olduğunca birbirinden bağımsız, ayrı ağlarda ve ayrı erişim rejimlerinde tutulmalıdır.** Aynı saldırganın tek bir hamleyle her ikisine birden erişememesi gerekir. Emniyet fonksiyonlarının değiştirilmesi en sıkı erişim kontrolüne, en katı değişiklik yönetimine tabi olmalıdır.

## Segmentasyon: en güçlü ve en pratik savunma

OT güvenliğinde uygulanabilir en yüksek getirili tek önlem sorulsa, cevap **segmentasyon** olur. Kök nedeni hatırlayalım: protokoller güvenli değil, cihazlar yamalanamıyor, sistem tehdit modeli değişti. Bu koşullarda tek gerçekçi strateji, saldırganın erişebileceği alanı fiziksel ve mantıksal olarak daraltmaktır.

### IT/OT ayrımı ve DMZ

En temel segmentasyon çizgisi IT ile OT arasındadır. Purdue modelindeki **Level 3.5 DMZ** tam da bunun içindir. İlke şudur: IT ağındaki hiçbir sistem doğrudan OT ağındaki bir cihaza konuşamamalı; her akış DMZ'deki bir aracı üzerinden geçmelidir. Örneğin OT'deki historian verisi IT'ye lazımsa, veri önce DMZ'deki bir replika sunucuya akıtılır, IT o replikadan okur — kurumsal ağdan hiçbir bağlantı doğrudan OT'ye uzanmaz. Bu, bir IT ihlalinin OT'ye "atlamasını" (pivot) engelleyen tampon bölgedir.

### Mikro-segmentasyon ve conduit kavramı

**IEC 62443** — bugün OT güvenliğinin fiili ana standardı — bu düşünceyi **zone (bölge)** ve **conduit (kanal)** kavramlarıyla formelleştirir. Benzer güvenlik gereksinimine sahip varlıklar bir "zone" içinde gruplanır; iki zone arasındaki her iletişim tanımlı, kontrollü, denetlenen bir "conduit" üzerinden yapılır. Bu, mimariyi "düz ve açık bir ağ" olmaktan çıkarıp, "aralarındaki her kapı kilitli ve loglanan odalar" düzenine getirir.

Segmentasyonun neden bu kadar etkili olduğunu bir felaket senaryosuyla düşünelim: Bir saldırgan phishing ile bir mühendisin kurumsal laptop'unu ele geçirdi. Düz bir ağda bu laptop doğrudan PLC'lere ulaşabilir ve Modbus komutu gönderebilir — felaket. İyi segmente edilmiş bir ağda ise o laptop OT ağını bile "göremez"; araya DMZ, firewall'lar ve jump host'lar girer. Saldırganın sahaya ulaşması için birçok ek katmanı aşması gerekir ve her katman hem gecikme hem tespit fırsatı yaratır.

### Uzaktan erişim: en sık kırılan yer

Segmentasyonu delen en yaygın gerçek dünya sebebi uzaktan erişimdir. Bakım için PLC'ye uzaktan bağlanan bir entegratör, dışarı açılmış bir RDP, üretici desteği için bırakılmış bir modem — bunlar segmentasyon duvarında delik açar. Doğru yaklaşım: uzaktan erişimi tek bir kontrollü **jump host** (bastion) üzerinden, **MFA (Multi-Factor Authentication)** ile, oturum kaydı alınarak, yalnızca gerektiğinde açılan (just-in-time) erişimle sağlamaktır. Kalıcı, denetimsiz uzaktan erişim, OT dünyasının en tehlikeli açıklarından biridir.

## Yaygın hatalar

OT güvenliği projelerinde tekrar tekrar görülen hatalar, çoğu zaman IT alışkanlıklarının OT'ye yanlış aktarılmasından doğar:

- **IT güvenlik araçlarını körlemesine OT'ye uygulamak.** Bir IT antivirüsünün agresif taraması veya bir aktif ağ tarayıcısının (örneğin bir güvenlik açığı tarayıcısının) OT ağına salınması, hassas eski PLC'leri kilitleyebilir. Aktif tarama OT'de üretimi durdurabilir; bu yüzden OT'de öncelik **pasif** izleme ve trafik dinlemedir.
- **"Hava boşluğu var" yanılgısı (air gap myth).** Birçok tesis "bizim OT ağı internetten tamamen izole" der; gerçekte USB bellekler, bakım laptop'ları, geçici VPN'ler, unutulmuş modemler ve IT/OT arası "geçici" bağlantılar nedeniyle bu izolasyon neredeyse hiç tam değildir. Stuxnet'in izole bir tesise USB ile taşınması bu yanılgının klasik dersidir.
- **Varlık envanterinin olmaması.** Sahada tam olarak hangi cihazların, hangi firmware'lerle, hangi IP'lerle olduğunu bilmeden güvenlik yapılamaz. Birçok tesis kendi OT envanterini bilmez; "koruyamazsın, çünkü ne olduğunu bilmiyorsun".
- **Ortak/varsayılan parolalar ve sabit kimlik bilgileri (hardcoded credentials).** Birçok PLC ve HMI, varsayılan fabrika parolalarıyla sahada çalışır; bazı cihazlarda parola firmware'e gömülüdür ve değiştirilemez. Bu, protokol açıklarına gerek bırakmadan tam erişim demektir.
- **Yama saplantısı ile yama korkusunun her ikisi de.** Bir uçta "her şeyi hemen yamalayalım" (üretimi ve emniyeti riske atar), diğer uçta "hiç dokunmayalım" (bilinen açıklar yıllarca açık kalır). Doğrusu, risk temelli ve test edilmiş bir yama yönetimi ile telafi edici kontrollerdir (compensating controls).
- **Emniyet ve güvenliği ayrı silolarda yönetmek.** Emniyet mühendisleri ile siber güvenlik ekiplerinin konuşmaması, Triton benzeri saldırıların önünü açar. İki disiplin birlikte tehdit modeli çıkarmalıdır.

## En iyi pratikler

İyi bir OT güvenlik programı, tek bir üründen değil, kök nedenlere yanıt veren katmanlı bir yaklaşımdan oluşur:

- **Envanter ve görünürlük önce gelir.** Pasif trafik dinlemeyle tüm varlıkları, protokolleri ve iletişim akışlarını haritalandırın. Neyi koruduğunuzu bilmeden savunma kurgulanamaz.
- **Segmente edin, sonra mikro-segmente edin.** Önce IT/OT ayrımını ve DMZ'yi kurun; ardından IEC 62443'ün zone/conduit yaklaşımıyla OT'yi kendi içinde bölün. Kritik SIS'i BPCS'ten ayırın.
- **En az ayrıcalık (least privilege) ve varsayılan reddet (default deny).** Ağ akışlarını beyaz listeyle tanımlayın; "izin verilmeyen her şey yasak" ilkesini benimseyin. Bir cihazın konuşması gerekmeyen hiçbir yere paket gitmesin.
- **Uzaktan erişimi disipline edin.** Jump host, MFA, oturum kaydı, just-in-time açılma. Kalıcı üretici erişimlerini kesin.
- **Kimlik bilgilerini ciddiye alın.** Varsayılan parolaları değiştirin, değiştirilemeyen cihazları ağ katmanında izole edin, mühendislik iş istasyonlarına erişimi sıkın.
- **Pasif izleme ve OT'ye özel anomali tespiti kurun.** Yeni bir master'ın belirmesi, beklenmedik bir yazma komutu, olağandışı bir function code alarma dönüşmeli. IT SIEM'ini OT bağlamıyla besleyin.
- **Risk temelli yama ve telafi edici kontroller.** Hemen yamalanamayan cihazlar için sanal yama (virtual patching), sıkı segmentasyon ve izleme ile riski azaltın.
- **Standartları çerçeve olarak kullanın.** IEC 62443 (OT güvenlik yönetimi), IEC 61511 (süreç emniyeti), NIST'in ICS güvenlik rehberliği ve MITRE ATT&CK for ICS (saldırı taktiklerini modellemek için) sağlam bir temel sunar.
- **Olay müdahalesini OT'ye göre tasarlayın.** IT'de bir sunucuyu izole etmek çözümdür; OT'de bir kontrolörü aniden kapatmak felaket olabilir. OT olay müdahale planı, emniyet ve süreç sürekliliğini gözeterek yazılmalıdır. Yedeklerin (PLC programları dahil) alınması ve düzenli test edilmesi hayatidir.
- **Güvenli ve emniyetli tasarımı en baştan kurun.** Yeni projelerde güvenliği sonradan eklenen bir katman değil, tasarımın (secure-by-design) parçası yapın. Retrofit her zaman baştan doğru yapmaktan pahalı ve eksiktir.

## Sonuç

OT güvenliği, IT güvenliğinin "biraz farklı" bir versiyonu değildir; tehdit modeli, öncelik sıralaması, protokol mirası ve sonucun fiziksel doğası tamamen başkadır. Kök neden nettir: fiziksel izolasyon varsayımıyla tasarlanmış, güvenlik içermeyen protokoller, yamalanması zor ve on yıllarca sahada kalan cihazlar, artık birbirine bağlı ve kurumsal ağlara temas eden dünyada çalışıyor. Bu gerçeği değiştiremeyeceğimiz için savunma stratejisi de değişir: protokolü güvenli kılmaya çalışmak yerine, saldırganın erişebileceği alanı segmentasyonla daraltır, görünürlük kurar, güvenlik ile emniyeti birlikte düşünür ve en az ayrıcalık ilkesini fiziksel dünyaya kadar taşırız. OT'de bir güvenlik açığının bedeli veri değil, çoğu zaman insan hayatı ve çevre olduğundan, bu disiplin en yüksek titizliği hak eder.
