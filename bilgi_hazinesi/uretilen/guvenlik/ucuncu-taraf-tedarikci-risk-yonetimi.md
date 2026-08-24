# Üçüncü Taraf / Tedarikçi Risk Yönetimi (TPRM)

## Tanım ve Kapsam

**Üçüncü Taraf Risk Yönetimi** (Third-Party Risk Management, TPRM), bir kurumun mal ve hizmet aldığı harici tarafların (tedarikçiler, bulut sağlayıcılar, SaaS ürünleri, danışmanlar, dış kaynak firmaları) kuruma taşıdığı riskleri sistematik olarak tanımlama, değerlendirme, azaltma ve izleme disiplinidir. GRC (Governance, Risk, Compliance) çerçevesinin merkezî pratiklerinden biridir.

Buradaki temel kavram şudur: bir kurum, güvenlik kontrollerini kendi sınırları içinde ne kadar iyi kurarsa kursun, iş süreçleri harici taraflarla iç içe geçtiği anda **güven sınırını (trust boundary)** o taraflara kadar genişletmiş olur. Tedarikçiye verilen her erişim, entegre edilen her API, kuruma gönderilen her yazılım güncellemesi potansiyel bir saldırı yüzeyidir. TPRM, bu genişlemiş saldırı yüzeyini yönetme çabasıdır.

Sık karıştırılan iki terimi ayıralım:
- **Third-party risk**: Doğrudan sözleşme yaptığınız tarafın taşıdığı risk.
- **Fourth-party (ve n'inci taraf) risk**: Tedarikçinizin kendi tedarikçilerinin taşıdığı, size dolaylı yansıyan risk. Örneğin bulut CRM sağlayıcınızın kullandığı e-posta gönderim servisi sizin dördüncü tarafınızdır. Modern **tedarik zinciri (supply chain)** ihlallerinin çoğu bu görünmeyen katmanlardan gelir.

TPRM, klasik "yazılım bağımlılık zinciri güvenliği"nden (dependency/SBOM tarafı) daha geniştir: teknik riskin yanında **sözleşmesel, operasyonel, finansal, uyumluluk ve itibar** risklerini de kapsar.

## Kök Neden ve Çalışma Mantığı

### Neden ihlallerin büyük kısmı tedarikçiden geliyor?

Birkaç yapısal neden var:

1. **Güven aktarımı, kontrol aktarımı değildir.** Bir tedarikçiye erişim verdiğinizde ona güvenirsiniz, ama onun güvenlik olgunluğunu kontrol edemezsiniz. Saldırgan için bu asimetri altın değerindedir: zayıf korunan küçük bir tedarikçiyi ele geçirip, onun üzerinden iyi korunan büyük kuruma sıçramak (lateral pivot) çok daha ucuzdur.

2. **Tek noktadan çoğa erişim (one-to-many).** Özellikle yönetilen hizmet sağlayıcıları (MSP), yazılım güncelleme kanalları ve ortak platformlar, tek bir başarılı saldırıyla yüzlerce müşteriye ulaşma imkânı sunar. Saldırgan açısından "ölçek ekonomisi" oluşur.

3. **Güncelleme kanalının doğal güveni.** Yazılım güncellemeleri tanım gereği ayrıcalıklı, imzalı ve otomatik uygulanan bir kanaldır. Bu kanalı ele geçiren saldırgan, kurbanların savunmasını "meşru" görünerek aşar. SolarWinds tipi olaylarda mekanizma budur: build (derleme) sürecine kod enjekte edilir, çıktı meşru sertifikayla imzalanır ve binlerce kuruma dağıtılır.

4. **Görünürlük eksikliği.** Kurumlar kendi ağını izler, ama tedarikçinin iç ağını izleyemez. İhlal tedarikçide başlarsa, kurum çoğu zaman ancak veri sızdıktan sonra haberdar olur.

### Somut örüntüler

**MOVEit (2023) tipi örüntü:** Yaygın kullanılan bir dosya transfer (managed file transfer) ürünündeki bir zafiyet, ürünü kullanan yüzlerce kurumu aynı anda etkiledi. Buradaki ders, kurbanların çoğunun MOVEit'i doğrudan değil, **bir hizmet sağlayıcısı üzerinden** kullanıyor olmasıdır. Yani veri kaybı yaşayan birçok kurum, ürünün adını bile duymamıştı; risk dördüncü/beşinci taraf katmanından geldi.

**Kaseya (2021) tipi örüntü:** Bir MSP yönetim aracındaki zafiyet, aracı kullanan MSP'ler üzerinden onların müşterilerine fidye yazılımı dağıtımıyla sonuçlandı. Bu, yukarıdaki "one-to-many" ve "güncelleme/yönetim kanalının doğal güveni" mekanizmalarının birleşimidir.

Bu olayların ortak dersi: **risk tekil bir üründe değil, güven topolojisindedir.** Kimin kime hangi ayrıcalıkla eriştiği haritalanmadıkça, risk görünmez kalır.

## TPRM Yaşam Döngüsü

Olgun bir TPRM programı bir yaşam döngüsü olarak işler. Aşamalar:

### 1. Tedarikçi Envanteri ve Sınıflandırma (Inventory & Tiering)

Yönetemediğiniz şeyi koruyamazsınız. İlk adım, tüm üçüncü tarafların envanterini çıkarmaktır. Ardından **risk katmanlandırması (tiering)** yapılır: her tedarikçiye aynı derinlikte durum tespiti yapmak hem imkânsız hem israftır. Katmanlandırma tipik olarak şu kriterlere bakar:

- Tedarikçi hangi **veri türlerine** erişiyor? (kişisel veri / PII, sağlık verisi, ödeme verisi, fikrî mülkiyet)
- Erişim **derinliği** nedir? (salt okuma bir rapor mu, yoksa üretim sistemlerine yönetici erişimi mi?)
- İş sürekliliği açısından **kritiklik** nedir? (bu tedarikçi çökerse ana iş süreci durur mu?)
- **Entegrasyon** biçimi nedir? (izole bir araç mı, yoksa ağınıza kalıcı bağlantısı olan bir sistem mi?)

Genellikle Tier 1 (kritik), Tier 2 (orta), Tier 3 (düşük) şeklinde bir ölçek kullanılır ve durum tespiti derinliği bu katmana göre ayarlanır.

### 2. Durum Tespiti (Due Diligence)

Sözleşme öncesi risk değerlendirmesidir. Araçları:

- **Due diligence anketleri (security questionnaires):** Tedarikçiye gönderilen yapılandırılmış sorular. Sektörde standartlaşmış formlar vardır; örneğin **SIG (Standardized Information Gathering)** ve **CAIQ (Consensus Assessments Initiative Questionnaire, CSA'nın bulut odaklı anketi)** yaygın kullanılır. Amaç, tedarikçinin kontrol ortamını yapılandırılmış biçimde görmektir.
- **Bağımsız denetim raporları:** En değerli kanıtlardan biridir çünkü üçüncü bir denetçi tarafından doğrulanmıştır. **SOC 2 Type II** raporu (kontrollerin belli bir dönem boyunca işlediğini gösterir; Type I sadece belirli bir andaki tasarımı gösterir), **ISO/IEC 27001** sertifikası, ödeme verisi için **PCI DSS** uyumluluğu bu kategoridedir.
- **Teknik doğrulama:** Sızma testi (penetration test) özetleri, zafiyet tarama raporları, dış saldırı yüzeyi taraması, güvenlik derecelendirme servisleri (security ratings) gibi dışarıdan gözlemlenebilir sinyaller.

Önemli bir ilke: **anket bir başlangıç noktasıdır, kanıt değildir.** Anket tedarikçinin kendi beyanıdır; onu bağımsız kanıtla (SOC 2, sertifika, test raporu) çapraz doğrulamak gerekir. Sadece anket cevabına güvenmek, TPRM'in en yaygın hatasıdır.

### 3. Risk Değerlendirmesi ve Karar

Toplanan kanıtlar bir **risk skoruna / kararına** dönüştürülür. Tespit edilen boşluklar (findings) için üç yol vardır: kabul et (accept), azalt (mitigate — tedarikçiden düzeltme iste ya da telafi edici kontrol koy), ya da reddet (reject — tedarikçiyle çalışma). Kabul edilen artık riskler (residual risk) mutlaka kayıt altına alınır ve bir yetkili tarafından onaylanır.

### 4. Sözleşmesel Kontroller (Contractual Safeguards)

Teknik değerlendirme kadar önemli, ama sıkça atlanan katman. Sözleşme, riski yönetmenin hukukî çapasıdır. Aranması gereken maddeler:

- **Güvenlik gereksinimleri eki:** Tedarikçinin uyması gereken asgari kontroller (şifreleme, erişim yönetimi, log tutma) sözleşmeye yazılmalı.
- **İhlal bildirim yükümlülüğü:** İhlal durumunda tedarikçinin sizi kaç saat/gün içinde bilgilendireceği net olmalı. Bu, gecikmeli fark edilen ihlallerin en önemli panzehiridir.
- **Denetim hakkı (right to audit):** Tedarikçiyi denetleme ya da bağımsız denetim raporlarını talep etme hakkı.
- **Veri işleme sözleşmesi (DPA):** KVKK / GDPR gibi düzenlemeler gereği, kişisel veri işleyen tedarikçiyle veri sorumlusu–veri işleyen ilişkisini tanımlayan sözleşme. Alt işleyen (sub-processor, yani dördüncü taraf) kullanımını da düzenlemelidir.
- **Sorumluluk ve tazminat (liability, indemnification):** İhlal maliyetinin taraflar arasında nasıl paylaşılacağı.
- **Çıkış / sonlandırma maddeleri:** Sözleşme bittiğinde verinin geri verilmesi ve güvenli imhası.

### 5. Sürekli İzleme (Continuous Monitoring)

TPRM'in en çok ihmal edilen aşaması budur. Durum tespiti bir **anlık fotoğraftır**; tedarikçinin güvenlik durumu zamanla bozulabilir. Sürekli izleme yaklaşımları:

- **Güvenlik derecelendirme servisleri:** Tedarikçinin dışarıdan gözlemlenebilir güvenlik hijyenini (açık portlar, süresi geçmiş sertifikalar, sızmış kimlik bilgileri, yama gecikmeleri) sürekli puanlayan servisler.
- **Tehdit istihbaratı:** Tedarikçinin adının veri ihlali haberlerinde, sızıntı forumlarında ya da fidye yazılımı gruplarının sızıntı sitelerinde geçip geçmediğini izleme.
- **Periyodik yeniden değerlendirme:** Kritik tedarikçiler için yıllık (ya da daha sık) anket/denetim yenileme.

### 6. Sonlandırma / Offboarding

Genellikle unutulan aşama. Bir tedarikçiyle ilişki bittiğinde: erişim yetkileri iptal edilmeli (API anahtarları, VPN erişimleri, servis hesapları), paylaşılan veriler geri alınıp imha ettirilmeli, entegrasyonlar sökülmeli. Aktif kalan "unutulmuş" tedarikçi erişimleri, sessiz ama ciddi bir risktir.

## Bulut Servis Sağlayıcı Risk Değerlendirmesi

Bulut sağlayıcıları özel bir alt başlıktır çünkü buradaki risk paylaşımı farklı işler.

### Paylaşılan Sorumluluk Modeli (Shared Responsibility Model)

Bulutta güvenlik, sağlayıcı ile müşteri arasında paylaşılır ve sınır hizmet türüne göre kayar:

- **IaaS**'ta sağlayıcı fiziksel altyapıdan, müşteri işletim sisteminden yukarısına kadar her şeyden sorumludur.
- **PaaS**'ta çizgi yukarı kayar; sağlayıcı platformu, müşteri uygulama ve verisini yönetir.
- **SaaS**'ta sağlayıcı neredeyse her şeyi yönetir, ama **veri, kimlik ve erişim yönetimi ile yapılandırma her zaman müşteride kalır.**

Buradaki en yaygın ve tehlikeli yanılgı şudur: **"buluta taşıdım, artık sağlayıcı koruyor" varsayımı.** Bulut ihlallerinin çok büyük kısmı sağlayıcının zafiyetinden değil, **müşterinin yanlış yapılandırmasından** (misconfiguration) kaynaklanır — herkese açık bırakılmış depolama kovaları (public bucket), fazla geniş IAM izinleri, açık kalmış yönetim panelleri gibi. Bu yapılandırma sorumluluğu, paylaşılan modelde daima müşteridedir.

### Bulut sağlayıcı değerlendirilirken bakılacaklar

- **Bağımsız güvence:** Sağlayıcının SOC 2 Type II, ISO 27001, ve varsa sektörel sertifikaları. CSA'nın **STAR** kayıt defteri gibi kamuya açık güvence kaynakları da faydalıdır.
- **Veri yerleşimi (data residency):** Verinin fiziksel olarak hangi ülkede tutulduğu — düzenleyici uyum açısından kritik.
- **Şifreleme:** Bekleyen (at rest) ve aktarımdaki (in transit) veri şifrelemesi; anahtar yönetiminin kimde olduğu.
- **Kilitlenme ve çıkış (lock-in / exit):** Veriyi geri alma ve başka sağlayıcıya taşıma imkânı; sağlayıcı çökerse iş sürekliliği planı.
- **Alt işleyenler:** Sağlayıcının kullandığı dördüncü taraflar ve onların şeffaflığı.

## Tespit ve İzleme

TPRM'de "tespit", geleneksel bir SOC alarmından farklıdır; hem yönetişim hem teknik katmanı kapsar.

**Yönetişim katmanında tespit:**
- Envanterle gerçeğin karşılaştırılması: Ağınıza bağlanan, sözleşmesi/onayı olmayan tedarikçileri bulmak. **Shadow IT** ve onaysız SaaS kullanımı burada ortaya çıkar. Kurumsal SSO loglarını ve giden ağ trafiğini tarayarak "envanterde olmayan ama fiilen kullanılan" servisleri tespit etmek güçlü bir kontroldür.
- Durum tespiti kanıtlarının **geçerlilik takibi**: Süresi dolmuş SOC 2 raporları, yenilenmemiş sertifikalar birer risk sinyalidir.

**Teknik katmanda tespit:**
- **Tedarikçi erişim davranışının izlenmesi:** Tedarikçi hesaplarının olağandışı saatlerde, olağandışı hacimde ya da normalde dokunmadığı sistemlere erişmesi, ele geçirilmiş bir tedarikçi erişiminin işareti olabilir. Tedarikçi erişimleri ayrı bir kimlik grubu olarak etiketlenip ayrı baseline'lanmalıdır.
- **Yazılım bütünlüğü doğrulama:** Tedarikçiden gelen güncellemelerin imza doğrulaması, hash kontrolü ve mümkünse davranışsal analizle (yeni bir güncelleme beklenmedik ağ bağlantıları açıyor mu?) izlenmesi. SolarWinds tipi tedarik zinciri saldırılarına karşı en pratik savunma katmanlarından biri budur.
- **Fourth-party görünürlüğü:** Giden bağlantıların, tedarikçinin kendi tedarikçilerine (ör. onun kullandığı analytics ya da CDN servisi) doğru trafiği de gösterebileceğini bilerek DNS/ağ loglarını incelemek.

## Savunma

TPRM'de savunma, tekil bir kontrol değil, katmanlı bir yaklaşımdır:

- **En az ayrıcalık (least privilege):** Tedarikçiye yalnızca işini yapması için gereken minimum erişimi verin. Kalıcı geniş erişim yerine, ihtiyaç anında verilen ve süreli **just-in-time** erişim tercih edilmelidir. Tedarikçi erişimleri düzenli olarak gözden geçirilip fazlalıklar kaldırılmalıdır.
- **Segmentasyon:** Tedarikçinin eriştiği sistemleri ağ segmentasyonuyla izole edin. Ele geçirilmiş bir tedarikçi hesabının kurumun geri kalanına yatay hareketini (lateral movement) sınırlamak, tek bir ihlalin felakete dönüşmesini engeller.
- **Sıfır güven (Zero Trust) prensibi:** Tedarikçiyi ağa girdi diye güvenilir sayma; her erişim isteğini doğrula. "İçerideki güvenilir taraf" varsayımı, tedarik zinciri saldırılarının tam olarak sömürdüğü zayıflıktır.
- **Sözleşmesel savunma:** Yukarıda anlatılan ihlal bildirim süreleri, denetim hakkı ve sorumluluk maddeleri, teknik kontrollerin başarısız olduğu durumda geri düşüş katmanıdır.
- **Olay müdahale planında tedarikçi senaryosu:** IR planınız "tedarikçimizde ihlal oldu, bize erişimi vardı" senaryosunu kapsamalı — kimi arayacağız, erişimi nasıl kesecğiz, hangi verilerin risk altında olduğunu nasıl belirleyeceğiz sorularının önceden yanıtı olmalı.
- **Konsantrasyon riskini yönetme:** Birçok kritik sürecin tek bir sağlayıcıya bağlı olması (ör. tüm altyapınızın tek bulut sağlayıcıda olması) sistemik risktir. Kritik tedarikçiler için yedeklilik ve çıkış planı düşünülmelidir.

## Yaygın Hatalar

1. **Anketi kanıt sanmak.** Tedarikçinin doldurduğu anket bir öz-beyandır. Bağımsız denetimle (SOC 2 Type II vb.) doğrulanmadıkça sınırlı değer taşır. "Anketi geçti, güvenli" yaklaşımı yanıltıcıdır.

2. **"Kur ve unut" (point-in-time) değerlendirme.** Sadece sözleşme öncesi bir kez değerlendirip sonra hiç bakmamak. Güvenlik durumu zamanla bozulur; sürekli izleme olmadan TPRM eksik kalır.

3. **Tüm tedarikçilere aynı muamele.** Katmanlandırma yapmadan ya küçük tedarikçileri aşırı yormak ya da kritik olanları yeterince incelememek. Risk odaklı önceliklendirme şarttır.

4. **Fourth-party körlüğü.** Sadece doğrudan tedarikçiye bakıp onun alt tedarikçilerini görmezden gelmek. MOVEit örneğinin gösterdiği gibi, en büyük sürprizler bu görünmeyen katmandan gelir.

5. **Bulutta paylaşılan sorumluluğu yanlış anlamak.** "Buluta taşıdık, sağlayıcı korur" varsayımı. Yapılandırma ve kimlik yönetimi daima müşterinin sorumluluğundadır.

6. **Sözleşmeyi güvenlikten ayrı görmek.** Güvenlik ekibinin teknik değerlendirme yapıp hukuk ekibinin sözleşmeyi ayrı imzalaması; ihlal bildirim süresi ya da denetim hakkı gibi kritik maddelerin sözleşmeye girmemesi.

7. **Offboarding'i atlamak.** İlişki bittiğinde erişimleri iptal etmemek. Unutulmuş API anahtarları ve servis hesapları, aylar sonra saldırı vektörü olur.

8. **Onboarding'i geciktiren, "kutu doldurma" haline gelen süreç.** Aşırı bürokratik TPRM, iş birimlerini süreci atlamaya (shadow IT'ye) iter. TPRM risk odaklı ve iş hızına uyumlu olmalı; aksi halde kendi amacını baltalar.

## Özet

TPRM, kurumun güven sınırını dışarı taşıyan her ilişkiyi yönetilebilir bir risk sürecine bağlama disiplinidir. Temel içgörü şudur: **modern kurum bir güven topolojisidir ve saldırgan bu topolojinin en zayıf halkasından girer.** Etkili bir program envanter ve katmanlandırmayla başlar, kanıta dayalı durum tespiti ve sözleşmesel kontrollerle güçlenir, sürekli izlemeyle canlı tutulur ve offboarding'le kapanır. Teknik kontrol (least privilege, segmentasyon, zero trust) ile yönetişim kontrolünün (anketler, denetimler, sözleşme maddeleri) birlikte çalışması gerekir; birini diğeri olmadan uygulamak, tedarik zinciri ihlallerinin defalarca kanıtladığı gibi, sahte bir güvenlik hissi yaratır.
