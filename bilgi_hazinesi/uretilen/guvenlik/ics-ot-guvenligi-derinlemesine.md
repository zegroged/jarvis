# ICS/OT Güvenliği Derinlemesine

## Giriş: OT Neden Farklıdır?

Endüstriyel Kontrol Sistemleri (ICS - Industrial Control Systems) ve daha geniş kavramıyla Operasyonel Teknoloji (OT - Operational Technology), fiziksel dünyayı yöneten bilişim sistemleridir: elektrik şebekeleri, su arıtma tesisleri, boru hatları, rafineriler, üretim bantları. Klasik BT (IT - Information Technology) güvenliğinden temel bir felsefe farkıyla ayrılır.

BT dünyasında öncelik sıralaması genellikle **CIA** üçlüsüdür: Confidentiality (gizlilik), Integrity (bütünlük), Availability (erişilebilirlik). OT dünyasında bu sıralama tersine döner ve **AIC** olur: önce Availability, sonra Integrity, en sonda Confidentiality. Bir türbini kontrol eden PLC'nin (Programmable Logic Controller) çalışmaya devam etmesi, verinin gizli kalmasından çok daha kritiktir. Bir su pompasının durması insan hayatını riske atabilir.

Bu felsefe farkı, güvenlik pratiklerini de değiştirir: OT'de "hemen yama uygula" (patch now) çoğu zaman geçersizdir; yama bir üretim durması gerektirir, sistem yıllarca yamalanmadan çalışır, cihazlar 20-30 yıllık ömre sahiptir. Dolayısıyla OT savunması, "yamalamak" yerine **segmentasyon, izleme ve erişim kontrolü** üzerine kuruludur.

## Purdue Modeli: Referans Mimari

Purdue Enterprise Reference Architecture (PERA), OT ağlarını katmanlara ayıran ve neredeyse tüm endüstri standartlarının temel aldığı referans modeldir. Amaç, güvenilirlik ve güvenlik için mantıksal segmentasyon sağlamaktır.

### Katmanlar

- **Level 0 - Saha (Field):** Fiziksel süreç. Sensörler (sensor), aktüatörler (actuator), valfler, motorlar. Sıcaklık ölçen bir termokupl veya bir valfi açan bir motor burada yer alır.
- **Level 1 - Temel Kontrol (Basic Control):** PLC'ler, RTU'lar (Remote Terminal Unit), IED'ler (Intelligent Electronic Device). Sensörlerden veri okur, mantık işletir ve aktüatörleri sürer.
- **Level 2 - Alan Denetimi (Area Supervisory):** SCADA (Supervisory Control and Data Acquisition) sunucuları, HMI'lar (Human-Machine Interface), operatör iş istasyonları. Operatörün süreci izlediği ve müdahale ettiği katman.
- **Level 3 - Site Operasyonları:** MES (Manufacturing Execution Systems), tarihsel veri sunucuları (historian), üretim planlama. OT'nin "üst" katmanı.
- **Level 3.5 - DMZ (Demilitarized Zone):** OT ve BT arasındaki tampon bölge. Güvenlik duvarları, data diyot'lar, jump server'lar burada bulunur. **Bu katman kritiktir**: BT ile OT arasındaki tüm trafik burada denetlenmeli, doğrudan geçişe izin verilmemelidir.
- **Level 4/5 - Kurumsal (Enterprise):** Kurumsal BT ağı, ERP, e-posta, internet.

### Kök Mantık

Modelin güvenlik değeri, **her katmanın yalnızca komşu katmanlarla, kontrollü şekilde konuşması** ilkesinden gelir. Level 4'teki bir kurumsal iş istasyonu, doğrudan Level 1'deki bir PLC'ye erişememelidir. Saldırganların en sık kullandığı yol, bu katmanlar arası ayrımın (özellikle IT/OT sınırının) yetersiz olmasıdır. Stuxnet ve birçok fidye yazılımı olayı, tam olarak bu segmentasyon eksikliğinden yayılmıştır.

## Endüstriyel Protokoller ve Saldırı Yüzeyleri

OT protokollerinin ortak ve kritik özelliği: **çoğu, güvenlik düşünülmeden, izole ve güvenilir ağlar varsayımıyla tasarlanmıştır.** Kimlik doğrulama (authentication), şifreleme (encryption) ve bütünlük kontrolü çoğunda yoktur veya sonradan eklenmiştir.

### Modbus

1979'da Modicon tarafından tasarlanan, muhtemelen en yaygın endüstriyel protokoldür. TCP/502 portu üzerinden çalışan Modbus/TCP versiyonu ağlarda sık görülür.

**Çalışma mantığı:** Basit bir istek/yanıt (request/response) modeli. Bir master (client), bir slave'e (server) "şu register'ları oku" veya "şu coil'i yaz" komutu gönderir. Fonksiyon kodları (function code) işlemi belirler: `01` coil oku, `05` tek coil yaz, `06` register yaz, `16` çoklu register yaz gibi.

**Zayıflıklar:** Modbus'ta kimlik doğrulama, oturum kavramı veya şifreleme **yoktur**. Ağa erişebilen herkes geçerli komut üretebilir. Tipik saldırı senaryoları:
- **Unauthorized command injection:** Ağa erişen bir aktörün "coil yaz" komutuyla bir valfi açması/kapatması.
- **Replay:** Yakalanan meşru bir paketin tekrar gönderilmesi.
- **Response manipulation / spoofing:** HMI'a sahte "her şey yolunda" değerleri gönderilerek operatörün kör bırakılması (Stuxnet ve Triton'un mantığına benzer kavram).

### DNP3

DNP3 (Distributed Network Protocol 3), özellikle Kuzey Amerika'da elektrik ve su altyapılarında yaygındır. Modbus'a göre daha zengindir: zaman damgalı olaylar (time-stamped events), report-by-exception (sadece değişimi bildirme) ve daha karmaşık veri modeli destekler.

**Zayıflıklar:** Orijinal DNP3 de kimlik doğrulamasız tasarlandı. Sonradan **DNP3 Secure Authentication (SAv5)** eklenerek komutlara HMAC tabanlı kimlik doğrulama getirildi; ancak birçok sahada bu özellik devrede değildir. Protokolün karmaşıklığı, ayrıştırıcı (parser) hataları ve DoS (Denial of Service) yüzeyi de yaratır; hatalı biçimlendirilmiş paketler eski cihazları çökertebilir.

### OPC-UA

OPC-UA (Open Platform Communications - Unified Architecture), modern OT'nin standart entegrasyon protokolüdür ve öncüllerinden (COM/DCOM tabanlı OPC Classic) çok daha güvenli tasarlanmıştır. **Yerleşik güvenlik özellikleri vardır**: sertifika tabanlı kimlik doğrulama, imzalama (signing) ve şifreleme (encryption), güvenlik politikaları (security policy).

**Kritik nokta:** OPC-UA güvenli *olabilir*, ama sık sık güvensiz yapılandırılır. En yaygın hata **"SecurityPolicy = None"** modunda, yani hiçbir imzalama/şifreleme olmadan çalıştırılmasıdır. Ayrıca kendinden imzalı (self-signed) sertifikaların körü körüne kabul edilmesi, "anonymous" kullanıcıya izin verilmesi ve karmaşık ayrıştırıcının kendi zafiyetleri (geçmişte çeşitli stack implementasyonlarında bulunmuştur) risk oluşturur. Yani OPC-UA'da mesele protokolün kendisi değil, **yapılandırmadır**.

## PLC/RTU Güvenliği

PLC ve RTU'lar OT'nin kalbidir; fiziksel süreci doğrudan kontrol ederler. Güvenlik açısından temel sorunları:

- **Zayıf/olmayan kimlik doğrulama:** Birçok PLC, programını (ladder logic, function block) indirmek/yüklemek için hiç parola istemez veya varsayılan parolayla gelir.
- **Kontrolsüz program yükleme (logic download):** Mühendislik yazılımıyla (engineering workstation) PLC'ye yeni mantık yüklenebilir. Bir saldırgan bu iş istasyonunu ele geçirirse PLC mantığını değiştirebilir; Stuxnet'in yaptığı buydu.
- **Firmware bütünlüğü:** İmzasız firmware, kötü niyetli firmware yüklenmesine (örn. Triton'un kontrolörün belleğine kod enjekte etmesi) kapı açar.
- **Anahtar konumu (key switch):** Birçok PLC'de RUN / REMOTE / PROGRAM konumu vardır. **Fiziksel olarak RUN konumunda kilitlemek**, uzaktan mantık değişikliğini engelleyen basit ama etkili bir savunmadır.

**Kavramsal not:** OT saldırılarının çoğu, PLC'nin "kırılmasından" değil, **PLC'ye meşru arayüzlerle meşru olmayan komutlar verilmesinden** kaynaklanır. Protokolde açık aramaya gerek yoktur; protokolün kendisi zaten kimlik sormamaktadır.

## SCADA ve Tarihsel Olaylar

### Stuxnet (keşfi 2010)

OT güvenliğinin milat kabul edilen olayıdır. İran'ın uranyum zenginleştirme santrifüjlerini hedef alan, son derece hedefli bir kötü amaçlı yazılımdır.

**Çalışma mantığı (kavramsal):**
- Hava boşluğuyla izole (air-gapped) ağa muhtemelen USB üzerinden sızdı; birden fazla Windows sıfırıncı gün (zero-day) zafiyetini kullanarak yayıldı.
- Hedefi çok spesifikti: yalnızca belirli bir Siemens PLC ve belirli frekans sürücüsü (variable frequency drive) yapılandırmasını arıyordu. Eşleşme yoksa zarar vermeden bekliyordu.
- PLC mantığını değiştirerek santrifüjlerin dönüş hızlarını periyodik olarak bozdu (aşındırıcı, fark edilmesi zor hasar).
- **En sinsi kısmı:** Operatörlerin HMI'larına *normal* değerler gösterdi. Yani süreç sabote edilirken izleme ekranları "her şey yolunda" diyordu. Bu, klasik bir **process visibility manipulation** örneğidir.

**Ders:** Air-gap tek başına yeterli değildir; taşınabilir medya ve tedarik zinciri (supply chain) bir vektördür. İzleme verisinin doğruluğu asla peşinen varsayılamaz.

### Ukrayna Elektrik Şebekesi (2015 ve 2016)

2015'te saldırganlar, kimlik avı (spear-phishing) ve çalınan kimlik bilgileriyle dağıtım şirketlerinin ağlarına girdi, meşru SCADA/HMI arayüzlerini kullanarak kesici (breaker) devrelerini açtı ve yüz binlerce kişiyi elektriksiz bıraktı. 2016'daki ikinci olayda ise **Industroyer/CrashOverride** adlı, doğrudan elektrik protokollerini (IEC 60870-5-101/104, IEC 61850 gibi) "konuşabilen" özel bir kötü amaçlı yazılım kullanıldı; bu, protokol seviyesinde otomatikleştirilmiş ilk şebeke saldırısı olarak öne çıkar.

**Ders:** Saldırgan çoğu zaman zafiyet sömürmez; **meşru operatör araçlarını meşru olmayan amaçla** kullanır. Bu yüzden komut anomalilerinin tespiti, imza tabanlı tespitten daha değerlidir.

### Triton / Trisis (keşfi 2017)

En tehlikeli olaylardan biridir çünkü doğrudan bir **SIS'i (Safety Instrumented System)** hedef aldı. SIS, süreç tehlikeli bir noktaya geldiğinde tesisi güvenli şekilde durduran son savunma hattıdır (örn. basınç kritik seviyeye çıkınca acil kapatma).

Triton, belirli bir Schneider Electric Triconex güvenlik kontrolörünü hedefledi ve kontrolörün belleğine kod enjekte etmeye çalıştı. Amaç, güvenlik fonksiyonunu devre dışı bırakıp fiziksel bir felaketin önünü açmaktı. Saldırı, bir kodlama hatası yüzünden kontrolörleri "safe state"e (güvenli durma) düşürdü ve böylece fark edildi.

**Ders:** Güvenlik sistemleri (SIS) mutlaka kontrol sisteminden (BPCS - Basic Process Control System) **ayrı ağda ve ayrı yetkiyle** tutulmalıdır. SIS'in tehlikeye girmesi, siber olayın fiziksel/insani zarara dönüştüğü çizgidir.

## IEC 62443: Endüstri Standardı

IEC 62443, ICS/OT güvenliği için uçtan uca standart ailesidir. IEC 62443'ün en pratik iki kavramı:

### Zones ve Conduits (Bölgeler ve Kanallar)

- **Zone (bölge):** Benzer güvenlik gereksinimlerine sahip varlıkların gruplandığı mantıksal segment (örn. "SIS bölgesi", "SCADA bölgesi").
- **Conduit (kanal):** Bölgeler arasındaki, kontrollü ve izlenen iletişim yolu. Tüm bölgeler-arası trafik bir conduit üzerinden ve denetlenerek akmalıdır.

Bu, Purdue segmentasyonunun standartlaştırılmış ve risk tabanlı halidir.

### Security Levels (SL 1-4)

IEC 62443, korunma hedefini saldırgan yeteneğine göre derecelendirir:
- **SL 1:** Tesadüfi/kazara ihlallere karşı.
- **SL 2:** Basit araçlarla, düşük motivasyonlu kasıtlı saldırıya karşı.
- **SL 3:** OT'ye özel bilgi ve orta kaynakla, kararlı bir saldırgana karşı.
- **SL 4:** Devlet destekli, yüksek kaynaklı ve OT uzmanı bir saldırgana karşı (Stuxnet/Triton sınıfı).

Her bölge için hedef bir SL belirlenir ve kontroller buna göre seçilir. Standart ayrıca **Foundational Requirements (FR)** olarak 7 temel gereksinim tanımlar: erişim kontrolü, kullanım kontrolü, sistem bütünlüğü, veri gizliliği, veri akışı kısıtlama, olaylara zamanında yanıt ve kaynak erişilebilirliği.

## Tespit (Detection)

OT tespiti, BT'den farklı düşünülmelidir çünkü OT trafiği **son derece öngörülebilir ve tekrarlıdır**. Bu, güçlü bir tespit avantajıdır.

- **Pasif ağ izleme:** OT'de aktif tarama (aktif nmap gibi) hassas cihazları çökertebilir. Bu yüzden **pasif** izleme tercih edilir: SPAN/TAP portundan trafik dinlenerek varlık envanteri ve iletişim matrisi (baseline) çıkarılır.
- **Baseline / anomali tespiti:** Normalde HMI-A yalnızca PLC-B ile Modbus konuşur. Aniden bir mühendislik iş istasyonundan PLC'ye "logic download" görülmesi, gece yarısı yeni bir kaynağın valf komutu yazması güçlü bir anomalidir.
- **Protokol farkındalıklı derin paket incelemesi (DPI):** Modbus/DNP3/OPC-UA'yı "anlayan" izleme araçları, tehlikeli fonksiyon kodlarını (örn. beklenmedik "write" veya "program" komutlarını) tespit edebilir.
- **Historian ve süreç değeri çapraz kontrolü:** Stuxnet dersi gereği, HMI'ın gösterdiği değer ile bağımsız bir sensör/historian kaydı karşılaştırılarak "operatör körlüğü" tespit edilebilir.
- **Mühendislik istasyonu izleme:** OT saldırılarının başlangıç noktası genelde bir Windows mühendislik iş istasyonudur; EDR ve sıkı erişim logu burada kritiktir.

## Savunma (Defense)

1. **Segmentasyon önce gelir:** Purdue/62443 zone-conduit modelini uygula. IT ile OT arasında **kesin bir DMZ** kur; doğrudan geçişe izin verme. Kritik bölgeler (özellikle SIS) fiziksel/mantıksal olarak ayrı olmalı.
2. **Data diyot:** Yalnızca tek yönlü veri akışının gerektiği yerlerde (örn. historian'dan kurumsala veri iletimi) donanımsal tek yönlü ağ geçidi kullan.
3. **En az ayrıcalık ve güçlü kimlik doğrulama:** Ortak/paylaşımlı hesapları kaldır, mühendislik erişimini MFA'lı jump server üzerinden yönlendir, uzaktan erişimi denetle.
4. **PLC key switch'i RUN'da kilitle:** Uzaktan mantık değişikliğini fiziksel olarak engelle.
5. **Güvenli protokol yapılandırması:** OPC-UA'da "SecurityPolicy = None"u yasakla, imzalama+şifreleme zorunlu kıl, sertifika güvenini yönet. DNP3'te Secure Authentication'ı etkinleştir. Modbus için mümkünse üstüne VPN/segmentasyon katmanı ekle (protokolün kendisi güvenli hale gelemez).
6. **Taşınabilir medya kontrolü:** USB'yi yönet; mühendislik istasyonlarına yalnızca taranmış medya girsin (Stuxnet dersi).
7. **Yedekleme ve kurtarma:** PLC mantığı, HMI projeleri ve konfigürasyonların çevrimdışı ve doğrulanmış yedekleri; olay sonrası hızlı geri dönüş için.
8. **OT'ye özel olay müdahalesi (IR):** Planda **fiziksel güvenlik ve güvenli durma** öncelikli olmalı; "sistemi kapatıp temizle" refleksi OT'de tehlikelidir.

## Yaygın Hatalar

- **BT güvenliğini OT'ye kopyalamak:** Otomatik yama, agresif aktif tarama, sürekli reboot OT'de üretim ve emniyet riski yaratır.
- **"Air-gap var, güvendeyiz" yanılgısı:** Gerçek air-gap nadirdir; USB, laptop, geçici bağlantılar ve tedarik zinciri sınırı deler.
- **DMZ'i atlayan "geçici" bağlantılar:** Bir bakım için açılan doğrudan IT-OT yolu çoğu zaman kapatılmaz ve kalıcı bir açık kapı olur.
- **OPC-UA'yı güvenli sanmak:** Protokol güvenli olabilir ama varsayılan/yanlış yapılandırma (None policy, anonymous) onu güvensiz kılar.
- **SIS'i BPCS ile aynı ağda tutmak:** Güvenlik sistemi ve kontrol sistemi karışırsa Triton sınıfı bir olay felakete dönüşebilir.
- **Varlık envanteri olmaması:** Görmediğini koruyamazsın; birçok tesis kendi OT ağındaki cihazların tam listesini bilmez.
- **HMI değerine körü körüne güvenmek:** Ekrandaki "yeşil" değerler manipüle edilebilir; bağımsız doğrulama şarttır.

## Özet

ICS/OT güvenliği, klasik siber güvenliğin değil, **mühendislik güvenilirliği ile siber savunmanın kesişiminin** bir disiplinidir. Protokollerin çoğu (Modbus, DNP3, klasik OPC) güvenilir ağ varsayımıyla tasarlandığı için kimlik sormaz; bu yüzden savunma protokolü "düzeltmeye" değil, **segmentasyon, erişim kontrolü, pasif izleme ve anomali tespiti** üzerine kurulur. Stuxnet, Ukrayna ve Triton olayları ortak bir dersi tekrarlar: saldırgan genellikle zafiyet değil, meşru araçları ve zayıf mimariyi kullanır; ve fiziksel/insani zarar çizgisi, güvenlik sistemleri (SIS) tehlikeye girdiğinde aşılır. IEC 62443'ün zone-conduit ve Security Level yaklaşımı ile Purdue modeli, bu savunmayı sistematik hale getiren çerçevelerdir.
