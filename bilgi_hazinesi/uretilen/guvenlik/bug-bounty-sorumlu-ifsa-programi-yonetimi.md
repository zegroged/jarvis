# Bug Bounty / Sorumlu İfşa Programı Yönetimi

## Tanım ve Kavramsal Çerçeve

**Bug bounty** ve **sorumlu ifşa (responsible disclosure)** programları, bir kuruluşun güvenlik açıklarını dış dünyadaki bağımsız araştırmacılar (security researcher, "hunter") aracılığıyla, kontrollü ve yasal bir çerçevede bulup düzeltmesini sağlayan yapılardır. Buradaki temel fikir, saldırganların zaten sürekli olarak sistemleri tarayıp zafiyet aradığı gerçeğini kabul edip; bu enerjiyi kötü niyetli sömürü (exploitation) yerine, ödüllendirilmiş ve belgelenmiş bir bildirim sürecine yönlendirmektir.

Bu disiplin, **pentest metodolojisinden** kavramsal olarak farklıdır. Pentest; belirli bir kapsamda, belirli bir süre için, sözleşmeli bir ekip tarafından yürütülen, çıktısı bir rapor olan **zaman kutulu (time-boxed)** bir çalışmadır. Bug bounty ise **sürekli**, **açık uçlu**, **sonuç-bazlı** (yalnızca gerçek bulguya ödeme yapılan) ve **çok sayıda bağımsız katılımcılı** bir modeldir. İkisi birbirinin alternatifi değil, tamamlayıcısıdır: pentest genişlik ve derinliği garanti eder, bounty ise çeşitlilik ve sürekliliği getirir.

Programı yöneten taraf için bu iş, teknik olduğu kadar **operasyonel**, **hukuki** ve **iletişimsel** bir disiplindir. Kötü yönetilen bir program; araştırmacı topluluğunu küstürür, iç ekipleri gereksiz gürültüyle boğar ve kuruluşu hukuki riske sokar. İyi yönetilen bir program ise, düşük maliyetle ve sürekli çalışan bir dış güvenlik katmanı yaratır.

## VDP ve Bug Bounty Ayrımı

Bir kuruluşun benimseyebileceği iki temel model vardır ve bunları karıştırmak yaygın bir hatadır.

**VDP (Vulnerability Disclosure Program):** Ödül **olmayan**, yalnızca bir "güvenli liman" (safe harbor) ve bildirim kanalı sunan programdır. Amaç, iyi niyetli araştırmacının bulduğu açığı kime, nasıl bildireceğini bilmesi ve bunu yaparken hukuki tehditle karşılaşmamasıdır. VDP, olgunlaşma yolundaki her kuruluşun **asgari** adımıdır; ABD'de federal kurumlar için, birçok sektörde ise regülasyon ve standartlar (örneğin ISO/IEC 29147 "vulnerability disclosure" ve ISO/IEC 30111 "vulnerability handling") bağlamında beklenen bir olgunluk göstergesidir.

**Bug Bounty:** Bulguların ciddiyetine göre **parasal ödül** ödenen programdır. VDP'nin üzerine kurulur; yani sağlam bir bildirim/triage altyapısı olmadan doğrudan bounty açmak, kuruluşu hazır olmadığı bir talep hacmiyle karşı karşıya bırakır.

Pratik bir olgunluk sırası şöyledir: önce **iç güvenlik hijyeni ve düzeltme kapasitesi** (gelen açıkları makul sürede kapatabilme), sonra **VDP**, ardından gerektiğinde **davetli (private) bounty**, en son **halka açık (public) bounty**. Bu sırayı atlamak, "gelen raporları kapatamayan ama para dağıtan" bir programa yol açar; bu da hem itibar hem bütçe açısından zarar verir.

## Program Politikasının Tasarımı

Program politikası (policy), araştırmacı ile kuruluş arasındaki sözleşmenin özüdür. Kötü yazılmış bir politika, en sık yaşanan çatışmaların kök nedenidir. İyi bir politika şu unsurları net biçimde içerir:

- **Kapsam (scope):** Hangi domainler, IP aralıkları, mobil uygulamalar, API'ler ve varlıklar dahildir. Kapsam **açık listelenmelidir**; "her şey dahil" gibi belirsiz ifadeler hem araştırmacıyı hem kuruluşu zora sokar.
- **Kapsam dışı (out-of-scope):** Test edilmemesi gereken varlıklar, üçüncü taraf servisler (kuruluşun yetkisi olmayan SaaS sağlayıcıları), ve **kabul edilmeyen açık sınıfları** (örneğin sadece self-XSS, rate limit yokluğu, SPF/DMARC eksikliği gibi düşük etkili bulgular çoğu programda peşinen dışlanır).
- **Yasak eylemler:** DoS/DDoS testleri, gerçek kullanıcı verisine erişim ve sızdırma, sosyal mühendislik (çalışanlara phishing), fiziksel saldırı, otomatik yüksek hacimli tarama gibi zarar verici davranışlar açıkça yasaklanır.
- **Güvenli liman (safe harbor) beyanı:** Politikaya uyan araştırmacıya karşı hukuki takip yapılmayacağının açık taahhüdü. Bu, programın **hukuki bel kemiğidir**; ilerideki bölümde ayrıca ele alınıyor.
- **İfşa politikası (disclosure policy):** Araştırmacının bulguyu ne zaman ve nasıl kamuya açıklayabileceği. Yaygın model **koordineli ifşadır**: kuruluş açığı düzeltene kadar veya belirli bir süre (örneğin 90 gün) geçene kadar bulgu gizli tutulur.

### Kapsam Belirlemenin Kök Mantığı

Kapsam yalnızca "nereye bakılabilir" sorusu değildir; aynı zamanda **kuruluşun kaldırabileceği yükün** ve **düzeltme kapasitesinin** bir yansımasıdır. Çok geniş kapsamla açılan ve arkasında düzeltme ekibi olmayan bir program, biriken açık yığınıyla boğulur. Bu nedenle olgun programlar kapsamı **kademeli genişletir**: önce iyi tanınan, sahiplenilmiş, kritik varlıklarla başlar; ekip triage ritmini yakaladıkça yeni varlıkları dahil eder.

Kapsam dışı olsa bile **kritik** bir bulgu gelirse (örneğin kapsam dışı bir alt alan üzerinden tüm ana sisteme erişim), olgun bir program bunu görmezden gelmez; çoğu politika "kapsam dışı ama yüksek etkili bulguları değerlendirme hakkını saklı tutarız" ifadesini içerir. Katı bir "kapsam dışı, reddedildi" tutumu, gerçek riski masada bırakabilir.

## Triage Süreci: Programın Motoru

**Triage**, gelen ham raporların incelenip; geçerlilik, önem (severity) ve tekrar (duplicate) açısından sınıflandırıldığı süreçtir. Bir programın kalitesi büyük ölçüde triage kalitesiyle ölçülür.

### Tipik Triage Akışı

1. **Alım (intake):** Rapor bir formatta gelir. İyi programlar zorunlu alanlar dayatır: etkilenen varlık, açık tipi, tekrar üretme adımları (steps to reproduce), etki (impact) ve kanıt (PoC).
2. **Geçerlilik doğrulaması (validation):** Triage ekibi bulguyu **kendisi tekrar üretmeye** çalışır. Üretilemeyen bulgu, araştırmacıdan ek bilgi istenerek beklemeye alınır; asla körlemesine kabul veya ret edilmez.
3. **Tekrar kontrolü (duplicate check):** Aynı açığın daha önce başka bir araştırmacı tarafından (veya iç ekipçe) bildirilip bildirilmediği kontrol edilir. Bug bounty'de **ödül genellikle ilk geçerli bildirime** gider; bu yüzden zaman damgaları ve iç bilgi tabanı kritiktir.
4. **Önem derecelendirmesi (severity scoring):** Bulguya bir ciddiyet atanır. Endüstride yaygın çerçeve **CVSS**'tir (Common Vulnerability Scoring System); ancak CVSS ham skoru, iş bağlamını (business context) her zaman yansıtmaz. Olgun programlar CVSS'i başlangıç noktası alıp, gerçek iş etkisiyle (veriye erişim, kullanıcı sayısı, düzeltme aciliyeti) düzeltir.
5. **Yönlendirme (routing):** Doğrulanmış bulgu, iç düzeltme ekibine (mühendislik, ilgili ürün takımı) bir iş kaydı (ticket) olarak açılır ve takip edilir.

### Duplicate ve Bilgi Yönetimi

Tekrar yönetimi, araştırmacı memnuniyetinin en kırılgan noktasıdır. Bir araştırmacı, günler harcadığı bir bulgunun "duplicate" damgasıyla ödülsüz kapatılmasını sık yaşarsa küser. Bu yüzden:

- Duplicate ilan edilen her rapor için, **hangi orijinal rapora** tekrar olduğu (mümkünse gizliliği koruyarak, en azından zaman damgasıyla) gösterilmelidir. Kanıtsız "duplicate" damgası güveni yok eder.
- İç ekibin zaten bildiği ama **belgelenmemiş** bir açığı, dışarıdan gelince "duplicate" diye kapatmak (informed duplicate suistimali) ağır bir kötü niyet göstergesidir. Bu yüzden iç açık envanteri kayıt altında ve tarihli tutulmalıdır.

## Ödül Modelleri (Reward / Bounty Design)

Ödül tasarımı, programın hem bütçesini hem araştırmacı ilgisini belirleyen ekonomik motordur.

### Temel Yaklaşımlar

- **Sabit kademeli (fixed tiers):** Önem seviyesine göre önceden ilan edilmiş tutarlar (örneğin: düşük / orta / yüksek / kritik için ayrı bantlar). Öngörülebilirdir, adalet algısını güçlendirir.
- **Aralıklı (range) ödüller:** Her önem seviyesi için bir alt-üst aralık; içinde triage ekibi gerçek etkiye göre karar verir. Esnektir ama şeffaflığı düşürebilir.
- **Etki bazlı bonuslar:** Özellikle iyi yazılmış rapor, zincirlenmiş açıklar (exploit chain) veya kritik varlıklar için ek prim.

Ödül **iyi niyeti para karşılığı satın almanın** değil, **harcanan uzman emeğini adil karşılamanın** aracı olarak görülmelidir. Piyasa değerinin çok altında ödül veren programlar, ciddi araştırmacıları çeker ama tutamaz; onun yerine düşük kaliteli, otomatik tarama çıktısı gönderen katılımcılarla dolar.

### Kavramsal Denge Noktaları

- **Bütçe öngörülebilirliği vs. adalet:** Sabit kademeler bütçeyi öngörülebilir kılar; aralıklar adaleti iyileştirebilir ama itiraz yönetimini artırır.
- **Severity vs. gerçek etki:** Aynı CVSS skoruna sahip iki bulgunun iş etkisi çok farklı olabilir. Kimlik doğrulama gerektiren, sömürüsü zor bir "yüksek" ile, kimlik doğrulamasız kitlesel veri sızıntısına açan bir "yüksek" aynı tutarı hak etmez.
- **Non-monetary teşvikler:** Para dışında **itibar puanı (reputation)**, **liderlik tablosu**, **hall of fame** (teşekkür sayfası), swag ve özel davetler de güçlü motivasyonlardır. Özellikle VDP'de bunlar tek teşviktir.

## Raporlama Kalitesi

İyi bir bug bounty raporu, triage maliyetini doğrudan düşürür. Kaliteli raporun beklenen unsurları:

- **Net başlık ve açık sınıfı:** "IDOR ile başka kullanıcının faturasına erişim" gibi doğrudan, sınıflandırılmış bir ifade.
- **Etkilenen varlık ve tam konum:** URL, parametre, endpoint.
- **Tekrar üretme adımları (steps to reproduce):** Bir başkasının sıfırdan takip edip aynı sonucu alabileceği netlikte.
- **Kavramsal kanıt (PoC):** Zararsız, sınırlı, etkiyi gösteren ama gereğinden fazla veri sızdırmayan bir kanıt.
- **Etki analizi (impact):** "Bu açık neden önemli?" sorusuna iş diliyle cevap. Teknik bulgu ile iş etkisi arasında köprü kuran rapor, çok daha hızlı ve doğru derecelendirilir.

Program yöneticisi açısından raporlama kalitesini **yükseltmek** de bir tasarım işidir: zorunlu şablonlar, örnek "iyi rapor" bağlantıları, ve düşük kaliteli raporları eğitici geri bildirimle (küçümsemeden) yönlendirmek uzun vadede havuzun kalitesini artırır.

## İletişim ve Araştırmacı İlişkileri

Bug bounty, teknik olduğu kadar **insan ilişkileri** işidir. Araştırmacı topluluğu birbiriyle konuşur; bir programın "adil" veya "zorlayıcı" ünü hızla yayılır ve katılım kalitesini doğrudan etkiler.

İyi iletişimin ilkeleri:

- **Hız ve şeffaflık:** İlk yanıt süresi (time to first response), triage süresi, düzeltme süresi ve ödeme süresi için makul hedefler ilan edin ve tutun. Sessizlik, en çok küstüren şeydir.
- **Saygılı ret:** Geçersiz veya kapsam dışı bir bulgu bile, **neden** reddedildiği açıklanarak kapatılmalıdır. Gerekçesiz ret, araştırmacıyı hem küstürür hem de tekrar denemekten caydırır.
- **Duygusal olgunluk:** Araştırmacı bazen sinirli, sabırsız veya iddialı olabilir. Program tarafı savunmacılığa kaçmadan, olguya odaklı ve profesyonel kalmalıdır. Bir bulgunun ciddiyeti konusunda anlaşmazlıkta, itiraz (mediation) mekanizması olmalıdır.
- **Kredi ve tanınma:** Araştırmacının istediği takdirde adının hall of fame'de yer alması; istemezse anonim kalması saygıyla karşılanmalıdır.

## Hukuki Güvence ve Safe Harbor

Programın en kritik ama en çok atlanan yönü hukuktur. Bir araştırmacı sistemi test ederken, teknik olarak birçok ülkede yetkisiz erişim sayılabilecek eylemler yapar. **Safe harbor** beyanı bu belirsizliği ortadan kaldırır:

- Politikaya **uygun davranan** araştırmacıya karşı **hukuki takip başlatılmayacağının** açık, yazılı taahhüdü.
- Bu taahhüdün, ilgili yerel bilgisayar suçları mevzuatı (örneğin ABD'de CFAA benzeri düzenlemeler; her ülkede karşılığı farklıdır) çerçevesinde araştırmacıya "iyi niyetle hareket etti" zemini sağlaması.
- **Sınırların netliği:** Safe harbor'ın kapsamı, ancak politikaya uyulduğu sürece geçerlidir; kapsam dışına çıkan, veri sızdıran veya zarar veren eylemler koruma dışıdır. Bu sınır açıkça yazılmalıdır.

Not: Belirli yasa maddeleri, ceza eşikleri ve içtihat ülkeden ülkeye ciddi farklılık gösterir. Bir program açarken safe harbor metni **mutlaka hukuk danışmanıyla** ve yerel mevzuata göre hazırlanmalıdır; internetten kopyalanan bir İngilizce metin, farklı bir hukuk sisteminde koruma sağlamayabilir.

## Platform Kullanımı vs. Kendi Kendine Yönetim

Programlar ya bir **aracı platform** (managed platform) üzerinden ya da kuruluşun **kendi altyapısıyla** yürütülür.

- **Platform üzerinden:** Araştırmacı havuzuna erişim, hazır triage hizmeti, ödeme altyapısı ve tekrar/sınıflandırma araçları sağlar. Yeni başlayan kuruluşlar için triage yükünü ciddi biçimde azaltır. Karşılığında komisyon ve platforma bağımlılık gelir.
- **Kendi altyapısıyla (self-hosted VDP):** Genellikle `security.txt` dosyası (RFC 9116 ile standartlaşan, `/.well-known/security.txt` konumunda yayınlanan iletişim bilgisi) ve özel bir güvenlik e-postası ile yürütülür. Maliyeti düşüktür ama tüm triage, iletişim ve hukuki yük kuruluşta kalır.

`security.txt`, olgunluğun ucuz ama etkili bir işaretidir: iyi niyetli bir araştırmacının açığı kime bildireceğini bilmesini sağlar; bu dosyanın yokluğu, birçok açığın hiç bildirilmeden savrulmasına yol açar.

## Tespit ve Savunma Perspektifi

Program yöneten savunma ekibi için bug bounty aynı zamanda bir **tespit (detection)** ve **iyileştirme (defense)** aracıdır:

- **Gelen bulguları kök neden analizine bağlayın:** Tekil açığı kapatmak yeterli değildir. Aynı IDOR bir yerde varsa, muhtemelen kod tabanının başka yerlerinde de vardır. Her bulgu, **sınıf bazında** taranmalı ve kalıcı savunma (güvenli kütüphane, merkezi yetkilendirme kontrolü) ile giderilmelidir.
- **Test trafiğini normal trafikten ayırın:** Araştırmacı test ederken güvenlik izleme sistemleriniz (SIEM, WAF) alarm üretebilir. Olgun programlar, araştırmacılardan sabit bir `User-Agent` veya işaret (marker) kullanmalarını isteyerek bu trafiği ayırt eder; böylece hem gerçek saldırıyı kaçırmaz hem gereksiz alarmla boğulmaz.
- **Metrikleri savunma sağlığı göstergesi olarak izleyin:** Gelen bulgu sayısındaki ve türlerindeki değişim, kod tabanının güvenlik trendini gösterir. Belirli bir açık sınıfı azalıyorsa savunma çalışıyordur; artıyorsa bir regresyon veya yeni bir zayıflık vardır.
- **Bounty ile pentest/kod analizini birlikte konumlandırın:** Bounty reaktif ve dağınıktır; belirli bir alanın kapsamlı denetimini garanti etmez. Kritik varlıklar için düzenli pentest ve statik/dinamik analiz (SAST/DAST) hâlâ gereklidir.

## Yaygın Hatalar

- **Düzeltme kapasitesi olmadan program açmak:** Gelen açıkları kapatamayan bir kuruluş, biriken zafiyet yığınıyla ve küskün araştırmacılarla kalır. Önce iç düzeltme akışını kur.
- **VDP adımını atlayıp doğrudan public bounty'e geçmek:** Hazır olmayan bir triage ekibini talep seliyle boğar; kalite ve moral çöker.
- **Belirsiz kapsam ve gerekçesiz retler:** En sık çatışma kaynağı. Kapsam listesi net olmalı; her ret gerekçeli olmalı.
- **CVSS'i mutlak gerçek sanmak:** Ham skor, iş etkisini yansıtmaz. Bağlamla düzeltilmeden yapılan derecelendirme, hem haksız ödüller hem de küçümsenmiş kritik bulgular üretir.
- **Informed duplicate suistimali:** İç ekibin bildiği ama belgelemediği açığı "duplicate" diye kapatmak. Topluluk bunu affetmez.
- **Safe harbor'ı ihmal etmek veya kopyala-yapıştır yapmak:** Hukuki güvence olmadan hiçbir ciddi araştırmacı riske girmez; yerel mevzuata uymayan bir metin sahte bir güven yaratır.
- **İletişimde sessizlik:** Yanıtsız kalan rapor, en hızlı itibar kaybı yoludur.
- **Ödülü piyasanın çok altında tutmak:** Ucuz program, ucuz (düşük kaliteli, otomatik tarama) katılım çeker; ciddi araştırmacılar başka programa gider.
- **Bounty'i tek güvenlik katmanı sanmak:** Bounty reaktif bir katmandır; SDLC güvenliği, kod incelemesi, pentest ve mimari savunmanın yerini almaz.

## Özet

Bug bounty ve sorumlu ifşa programı yönetimi; kapsam tasarımı, triage disiplini, adil ödül ekonomisi, saygılı araştırmacı iletişimi ve sağlam hukuki güvenceyi bir araya getiren çok boyutlu bir disiplindir. Başarısı, "para dağıtmakta" değil; gelen her bulguyu kök nedene bağlayan, düzeltme kapasitesiyle desteklenen ve topluluğa güven veren bir işletim modeli kurmakta yatar.
