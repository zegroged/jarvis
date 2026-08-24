# SMB Protokol Güvenliği ve Saldırıları (SMB Relay, EternalBlue/MS17-010, SMB Signing, Null Session Enum)

## Giriş: SMB Neden Kurumsal Ağların Bel Kemiği ve Aynı Zamanda Zaafı

SMB (Server Message Block), Windows dünyasında dosya paylaşımı, yazıcı paylaşımı, named pipe iletişimi ve hatta domain trafiğinin (Group Policy dağıtımı, login script'leri, SYSVOL erişimi) taşıyıcısıdır. Bir kurumsal iç ağda neredeyse her workstation ve sunucu SMB dinler (TCP 445, tarihsel olarak 139/NetBIOS üzerinden de). Bu evrensellik SMB'yi saldırganlar için doğal bir hedef haline getirir: her makinede açık, genellikle kimlik doğrulama akışı zayıf yapılandırılmış, ve protokolün kendisi tasarım gereği ağ üzerinden kimlik bilgisi (credential) taşıyan bir yapı.

LLMNR/NTLM Relay ve Pass-the-Hash gibi konular "SMB'yi nasıl kötüye kullanırım" sorusuna cevap verir, ama bu makalenin odağı farklı: SMB'nin kendisi -- protokolün iç yapısı, sürüm farkları, imzalama (signing) mekanizması, kernel seviyesinde SMBv1'i çökerten zafiyet sınıfı (EternalBlue/MS17-010) ve kimlik doğrulamasız keşif (null session enumeration). Bunları anlamadan relay veya PtH saldırılarının neden işlediğini gerçekten kavramak mümkün değil; SMB'nin protokol düzeyindeki zaafları, üstüne kurulan saldırıların temelini oluşturur.

## SMB Protokolüne Genel Bakış: Katmanlar ve Sürümler

### SMB'nin Rolü ve Taşıma Katmanı

SMB, uygulama katmanında çalışan bir istemci-sunucu protokolüdür. Tarihsel olarak NetBIOS over TCP/IP (NBT, port 139) üzerinden taşınırdı; modern Windows sürümlerinde "direct hosting" adı verilen yöntemle doğrudan TCP 445 üzerinden çalışır (NetBIOS katmanına ihtiyaç duymadan). Bir ağ taramasında hem 139 hem 445'in açık görünmesi, eski uyumluluk mekanizmalarının hâlâ etkin olduğunun işaretidir.

SMB üzerinden taşınan temel soyutlamalar şunlardır: **share** (paylaşılan dizin veya kaynak, ör. `\\sunucu\paylasim`), **session** (kimlik doğrulanmış oturum), **tree connect** (bir share'e bağlanma), ve **named pipe** (IPC$ gibi, RPC çağrılarını taşıyan sanal kanallar). IPC$ payı özellikle önemlidir çünkü kimlik doğrulama, RPC (SAMR, LSARPC gibi arayüzler) ve enumerasyon büyük ölçüde bu kanal üzerinden yürür.

### SMBv1, SMBv2, SMBv3: Neden Önemli

- **SMBv1**: 1980'lerin sonu/1990'ların başına dayanan, orijinal CIFS (Common Internet File System) temelli tasarım. Protokol basit, ama güvenlik düşünülerek tasarlanmamış: zayıf mesaj imzalama desteği, verimsiz (chatty) istek-cevap modeli, ve en önemlisi kernel modunda (SMB sunucu tarafı `srv.sys`/`srv2.sys` gibi sürücülerde) işlenen, bellek yönetimi hatalarına açık bir kod tabanı. EternalBlue sınıfı zafiyetler tam olarak bu eski, kernel'de çalışan SMBv1 işleyicisinde ortaya çıkmıştır.
- **SMBv2** (Windows Vista/Server 2008 ile gelen): Protokolü sadeleştirdi, komut sayısını azalttı, performansı artırdı (compounding, credit-based akış kontrolü) ve **zorunlu olabilen mesaj imzalama** desteğini modernize etti.
- **SMBv3** (Windows 8/Server 2012+): Şifreleme (AES-CCM/GCM ile SMB Encryption), çok kanallı bağlantı (multichannel), küme (cluster) senaryoları için sürekli kullanılabilirlik gibi özellikler ekledi. SMBv3.1.1 (Windows 10/Server 2016+) ayrıca **pre-authentication integrity** getirdi -- bu, aşağıda anlatılacak downgrade saldırılarına karşı önemli bir savunma katmanıdır.

Kök neden mantığı şudur: SMBv1 tasarlandığı dönemde tehdit modeli "güvenilir yerel ağ" varsayımına dayanıyordu. Kimlik doğrulama isteğe bağlıydı, imzalama varsayılan kapalıydı, ve protokol ayrıştırma (parsing) kodu modern bellek güvenliği pratikleriyle yazılmamıştı. Ağların İnternet'e açılması ve saldırganların iç ağa erişim kazanması bu varsayımı geçersiz kıldı; SMBv1 o günden beri bir miras (legacy) yüküdür.

## SMB Signing: Mekanizma, Kök Neden ve Zafiyeti Kapatma Mantığı

### Sorun: Neden İmzalama Gerekli

SMB, kimlik doğrulamasını (authentication) genellikle NTLM veya Kerberos ile bağlantı kurulumunda yapar, ama **her paket** varsayılan olarak bütünlük (integrity) korumasına sahip değildir. Bu, bir saldırganın ağda araya girip (on-path / man-in-the-middle konumunda) paketleri değiştirebileceği, hatta bir SMB oturumunu "relay" edebileceği anlamına gelir: kimlik doğrulama handshake'i araya alınıp başka bir hedefe iletilerek, orijinal kullanıcının kimliğiyle o hedefte oturum açılabilir. Bunun kök nedeni protokolün "kimliği doğrula, sonra veriyi düz/imzasız aktar" modelidir -- oturumun kimliği doğrulandıktan sonra paket bütünlüğünü garanti eden bir mekanizma yoksa, araya giren taraf paketleri değiştirebilir veya replay/relay edebilir.

### SMB Signing Nasıl Çalışır (Kavramsal)

SMB signing etkinleştirildiğinde, her SMB mesajına, oturum anahtarından (session key, kimlik doğrulama sırasında türetilen) türetilmiş bir mesaj kimlik doğrulama kodu (MAC benzeri imza) eklenir. Alıcı taraf, kendi hesapladığı imzayla gelen imzayı karşılaştırır; uyuşmazsa paket reddedilir. Bu, mesajın kimlik doğrulanmış oturumun tarafı olan gerçek istemci/sunucudan geldiğini ve yolda değiştirilmediğini garanti eder.

Kritik nokta: imzalama **relay saldırısını doğrudan durdurur**, çünkü relay eden saldırgan geçerli bir oturum anahtarına sahip değildir -- kurbanın kimlik doğrulama yanıtını başka bir hedefe iletebilir, ama o hedefle kurulan oturumda sonraki her paketi kurbanın oturum anahtarıyla imzalamak zorundadır ve bunu bilmediği için yapamaz. Sunucu tarafı "signing required" (imzalama zorunlu) olarak ayarlanmışsa, imzasız veya yanlış imzalı istekler reddedilir ve relay pratikte işe yaramaz hale gelir.

### Nasıl Zafiyet Oluşur ve Nasıl Tespit Edilir

- **Kök neden**: Signing "required" değil "enabled but not required" (destekleniyor ama zorunlu değil) ya da tamamen kapalı yapılandırıldığında, saldırgan imzasız bağlantı teklif ederek imzalamayı bypass edebilir. Tarihsel olarak Windows istemcilerinde signing zorunluluğu varsayılan kapalıydı (özellikle iş istasyonu tarafında); sunucularda (Domain Controller gibi) daha sık zorunluydu ama tüm sunucu/servis türlerinde tutarlı değildi.
- **Tespit**: Ağ taraması araçları (ör. protokol destekleyen tarayıcılar) bir SMB sunucusuna bağlanıp "signing negotiate" alanına bakarak imzalamanın "enabled", "required" mi yoksa "disabled" mi olduğunu raporlayabilir. Savunma tarafında düzenli olarak iç ağ taraması yapıp "SMB signing not required" bulgusu veren hostları envanterlemek, relay saldırı yüzeyinin haritasını çıkarır.
- **Savunma**: Grup İlkesi (Group Policy) üzerinden `Microsoft network client/server: Digitally sign communications (always)` ayarlarını tüm istemci ve sunucularda zorunlu kılmak temel önlemdir. Domain Controller'larda bu zaten kritik önemdedir çünkü DC'ler en değerli relay hedefidir. Ayrıca SMBv3.1.1'in pre-authentication integrity özelliği, kimlik doğrulama öncesi mesajlaşmanın da bütünlüğünü koruyarak downgrade tabanlı bazı saldırı varyantlarını zorlaştırır.

### Yaygın Hata

"Signing enabled" ile "signing required" birbirine karıştırılır. Enabled, sunucunun imzalamayı desteklediği ama istemci imzalamadan bağlanmayı denerse buna izin verebileceği anlamına gelir -- bu durumda saldırgan basitçe imzasız bağlantı teklif ederek korumayı devre dışı bırakabilir. Zorunluluk (required) olmadan "signing var" demek yanlış bir güvenlik hissi yaratır.

## Null Session ve Anonim Enumerasyon: Kimlik Doğrulamasız Bilgi Sızıntısı

### Kavram ve Kök Neden

"Null session", kullanıcı adı ve parola olmadan (anonim, boş kimlik bilgileriyle) bir SMB/IPC$ bağlantısı kurma yeteneğidir. Tarihsel olarak Windows NT/2000 döneminde, ağ üzerindeki servislerin birbirini keşfedebilmesi (trust ilişkileri, domain bilgisi paylaşımı) için IPC$ payına anonim erişime belirli ölçüde izin verilirdi. Bunun kök nedeni, o dönemde ağ içi güvenin varsayılan olması ve NetBIOS/SMB tabanlı servis keşfinin bu anonim kanal üzerine inşa edilmiş olmasıydı.

Anonim bir IPC$ bağlantısı kurulduğunda, saldırgan kimlik doğrulaması yapmadan belirli RPC arayüzlerini (SAMR -- Security Account Manager Remote, LSARPC -- Local Security Authority) çağırabilir ve şunları elde edebilir:

- Domain ve yerel kullanıcı listesi (kullanıcı adları)
- Grup üyelikleri, yerleşik (built-in) grup bilgisi
- Paylaşılan dizin (share) listesi
- Parola politikası (minimum uzunluk, kilitlenme eşiği gibi)
- Bazı yapılandırmalarda SID'den kullanıcı adına (veya tersine) çeviri (SID/name lookup)

### Neden Tehlikeli

Bu bilgi kendi başına bir "ihlal" değildir ama saldırı zincirinin ilk halkasıdır: geçerli kullanıcı adlarının listesi, parola püskürtme (password spraying) ve brute-force saldırılarının hedef kitlesini daraltır; parola politikasının bilinmesi (ör. kilitlenme eşiği yüksek/yok) saldırganın kaç deneme yapabileceğini hesaplamasını sağlar. Yani null session enumeration, doğrudan zarar vermez ama sonraki adımların isabet oranını dramatik biçimde artırır -- keşif (reconnaissance) aşamasının temel taşıdır.

Bilinen araçlar arasında `enum4linux` (ve modern `enum4linux-ng`), `rpcclient`, ve `smbclient` gibi Samba paket araçları bulunur; bunlar SAMR/LSARPC çağrılarını kullanıcı dostu biçimde sarmalar. Tam bayrak/komut ayrıntılarını burada vermiyorum çünkü amaç aracı ezberletmek değil, hangi RPC arayüzünün hangi bilgiyi ifşa ettiğini ve bunun neden mümkün olduğunu anlamaktır.

### Tespit ve Savunma

- **Savunma**: Modern Windows sürümlerinde varsayılan yapılandırma anonim erişimi büyük ölçüde kısıtlar (`RestrictAnonymous` ve ilişkili ayarlar üzerinden). Kurumsal ortamlarda bu ayarların açıkça doğrulanması, eski/legacy sistemlerde (özellikle uzun süredir yükseltilmemiş sunucularda) varsayılanın gevşetilmiş olup olmadığının kontrol edilmesi gerekir. "Network access: Do not allow anonymous enumeration of SAM accounts and shares" gibi ilkelerin etkin olması hedeftir.
- **Tespit**: Kimlik doğrulaması olmadan IPC$'ye bağlanma ve SAMR/LSARPC çağrıları yapma girişimleri, SMB sunucu tarafında (Windows Security Event Log, ilgili oturum açma/erişim olayları) ve ağ izleme (IDS/IPS imzaları, anormal null-session bağlantı sayısı) ile tespit edilebilir. Bir host'a çok sayıda farklı kaynak IP'den kısa sürede null session denemesi, otomatik keşif aracının (enum4linux vb.) çalıştığının işareti olabilir.
- **Yaygın hata**: "Modern Windows zaten null session'ı engeller" diye düşünüp hiç doğrulamamak. Yanlış yapılandırılmış legacy sunucular, üçüncü parti NAS/depolama cihazları (SMB implementasyonu gömülü, güncellenmesi zor) veya Samba tabanlı Linux sunucular hâlâ gevşek varsayılanlarla çalışıyor olabilir.

## EternalBlue / MS17-010: Kernel Seviyesinde SMBv1 Zafiyeti

### Zafiyet Sınıfı Ne Anlatır

MS17-010 (kamuoyunda en çok EternalBlue exploit'i ile anılan güvenlik bülteni), SMBv1 sunucu tarafı işleyicisinde (kernel modunda çalışan sürücülerde) bulunan bellek bozulması (memory corruption) sınıfı zafiyetlerin bir kümesidir. Kök neden, SMBv1'in bazı komutlarının (özellikle "Transaction2" ailesi gibi eski, karmaşık ve az kullanılan alt komutlar) istemciden gelen boyut/uzunluk alanlarını yeterince doğrulamadan işlemesidir. Saldırgan, özel biçimlendirilmiş (crafted) bir SMB isteğiyle sunucunun kernel belleğinde beklenmeyen bir yazma/okuma tetikleyebilir; bu da (exploit zincirinin ilerleyen adımlarıyla birleşince) kernel modunda, yani SYSTEM ayrıcalığıyla, uzaktan kod çalıştırmaya (remote code execution) kadar gidebilir.

Bunun kritik önemi şuradan gelir: exploit **kimlik doğrulaması gerektirmez** (pre-auth) ve etkilenen host'ta doğrudan SYSTEM yetkisiyle kod çalıştırma sağlar. Bu iki özelliğin birleşimi -- kimlik doğrulamasız + en yüksek ayrıcalık -- onu kurumsal ağlarda solucan (worm) benzeri, kendi kendine yayılan zararlı yazılımların (WannaCry, NotPetya gibi vakalarda görüldüğü üzere) tercih ettiği bir birincil yayılma vektörü haline getirdi. Bir host ele geçirildiğinde, aynı zafiyeti taşıyan diğer hostlara SMB üzerinden otomatik olarak sıçranabildi.

### Neden Bu Kadar Yıkıcı Oldu (Kök Neden Zinciri)

1. **Tasarım mirası**: SMBv1'in eski komut kümesi, modern güvenli kodlama standartlarından önce yazılmıştı; sınır kontrolleri (bounds checking) tutarsızdı.
2. **Kernel'de çalışma**: SMB sunucu işleme mantığının bir kısmı kullanıcı modunda değil kernel modunda (sürücü seviyesinde) yer alıyordu -- bu da bir bellek hatasının doğrudan en yüksek ayrıcalık seviyesinde (ring 0) istismar edilebilir olması anlamına geliyordu.
3. **Yama uygulama gecikmesi**: Microsoft yamayı yayınladıktan sonra bile (yama, saldırı kamuoyuna sızmadan kısa süre önce çıkmıştı) kurumsal ortamlarda yama yönetimi süreçlerinin yavaşlığı, özellikle üretim kesintisi riski nedeniyle sunucu yamalamanın ertelenmesi, geniş bir savunmasız yüzey bıraktı.
4. **Gereksiz protokol yüzeyi**: SMBv1'e ihtiyacı olmayan sistemlerde bile protokolün varsayılan olarak etkin kalması, saldırı yüzeyini gereksiz yere büyüttü.

### Tespit

- Ağ taraması: Bir hostun SMBv1 konuştuğunu ve MS17-010 yamasının eksik olduğunu doğrulayan zafiyet tarayıcıları (vulnerability scanner) veya protokol-özel kontrol scriptleri ile pasif/aktif tespit yapılabilir.
- Host tabanlı: Windows üzerinde SMBv1 sunucu/istemci özelliğinin etkin olup olmadığı denetlenebilir (özellik envanteri). Ayrıca güncelleme/yama envanteri sistemleri (WSUS, SCCM, veya üçüncü parti yama yönetimi) ilgili güvenlik bülteninin uygulanıp uygulanmadığını raporlamalı.
- Ağ izleme: IDS/IPS imzaları, EternalBlue exploit trafiğinin karakteristik desenlerini (anormal Transaction2 alt komutları, olağandışı paket boyutları) tespit edebilir; ancak imza tabanlı tespit varyantlara karşı kırılgan olabilir, bu yüzden host tabanlı yama/özellik denetimi asıl güvenilir kontroldür.

### Savunma

- **En etkili önlem: SMBv1'i tamamen devre dışı bırakmak.** Modern Windows sürümleri SMBv1'i varsayılan olarak kaldırmış/isteğe bağlı özellik haline getirmiştir; ihtiyaç yoksa (eski yazıcı, NAS gibi uyumluluk gereksinimleri hariç) hem istemci hem sunucu tarafında kapatılmalıdır.
- Yama yönetiminde kritik/yüksek şiddetli bültenler için hızlandırılmış (expedited) uygulama süreci tanımlamak.
- Ağ segmentasyonu: SMB trafiğinin (445/139) segmentler arası, özellikle kullanıcı ağlarından sunucu ağlarına ve İnternet'e serbestçe geçmesini engellemek; bu, tekil bir zafiyetin solucan gibi yayılmasını sınırlar.
- Uç nokta koruması (EDR/AV) ile bilinen exploit davranış imzalarının izlenmesi ek bir katman sağlar, ama birincil bağımlılık olmamalıdır.

### Yaygın Hata

"Yama uyguladık, iş bitti" düşüncesi. SMBv1'i devre dışı bırakmadan sadece yama uygulamak, protokolün kendisindeki tasarım zafiyeti sınıfını (gelecekteki benzer bulgular için) yüzeyde bırakır. Kök nedene (SMBv1'in varlığı ve gereksizliği) değil, semptoma (tek bir CVE) odaklanmak, sonraki benzer zafiyetlere karşı savunmasız kalmaya devam etmek demektir.

## SMB Relay: Protokol Zaafının Kimlik Doğrulamayla Kesişimi

Bu makale relay saldırısının ayrıntılı mekaniğine (LLMNR/NTLM Relay başlığı altında ayrı işlendiği belirtiliyor) girmiyor, ama SMB tarafındaki kök nedeni netleştirmek gerekiyor: relay, SMB'nin taşıdığı NTLM kimlik doğrulama mesajlarının (challenge-response) **hedef bağımsız** olmasından ve az önce anlatılan **imzalama eksikliğinden** beslenir. Saldırgan bir istemcinin kimlik doğrulama girişimini yakalayıp farklı bir SMB sunucusuna ilettiğinde, o sunucu isteği kendi imzalama politikasına göre kabul veya reddeder. Yani relay'in SMB tarafındaki tek gerçek engeli imzalama zorunluluğudur -- bu da neden "SMB signing required" ayarının relay saldırılarına karşı tekil en önemli kontrol olarak öne çıktığını açıklar.

Ayrıca relay hedefinin genellikle **başka bir makine** olması (kimlik doğrulamanın yakalandığı makineden farklı), imzalamanın host bazında değil ağ genelinde tutarlı uygulanması gerektiğini gösterir: tek bir zayıf yapılandırılmış host, tüm ağdaki relay saldırıları için giriş noktası olabilir.

## Enumerasyon Araçlarının Mantığı: smbclient ve enum4linux Ne Yapar

Kavramsal olarak bu araçlar iki temel işlevi otomatikleştirir:

1. **Share/dosya sistemi keşfi** (`smbclient` sınıfı araçlar): Bir SMB sunucusuna bağlanıp mevcut payları listeler, erişim izinlerini (okuma/yazma) test eder, ve yetki varsa dosya listeleme/indirme yapar. Kök işlev, SMB'nin "tree connect" ve dosya işlemleri protokolünü kimlik doğrulanmış veya anonim bir oturumdan çağırmaktır.
2. **RPC tabanlı hesap/politika keşfi** (`enum4linux`, `rpcclient` sınıfı araçlar): Yukarıda anlatılan SAMR/LSARPC çağrılarını IPC$ üzerinden yaparak kullanıcı, grup, parola politikası bilgisi toplar.

Savunma açısından önemli olan, bu araçların "yeni bir zafiyet" istismar etmediği, sadece **protokolün izin verdiği meşru işlevleri** (dosya listeleme, RPC sorgulama) kimlik doğrulaması olmadan veya düşük ayrıcalıklı bir hesapla çalıştırdığıdır. Bu yüzden savunma, "bu aracı engelle" değil, "bu işlevlerin anonim/düşük ayrıcalıklı erişime açık olmasını engelle" mantığıyla kurulmalıdır -- yani kök nedene (gevşek erişim kontrolü ve varsayılan yapılandırma) odaklanmak.

## Genel Savunma Mimarisi: Katmanlı Yaklaşım

SMB güvenliği tek bir ayarla çözülmez; birbirini tamamlayan katmanlar gerekir:

- **Protokol hijyeni**: SMBv1'i kapat, mümkün olan en yüksek SMB sürümünü ve şifrelemeyi (SMBv3 encryption) zorunlu kıl.
- **Kimlik doğrulama bütünlüğü**: SMB signing'i tüm istemci/sunucu/DC'lerde zorunlu yap; mümkünse NTLM'i kısıtlayıp Kerberos'u tercih et (bu, relay ve bazı hash tabanlı saldırıların etki alanını daraltır).
- **Erişim kısıtlama**: Anonim/null session erişimini kapat; IPC$ ve diğer paylara varsayılan geniş erişimi (Everyone, Authenticated Users gibi geniş gruplara aşırı izin) daralt.
- **Ağ segmentasyonu**: SMB portlarının (139/445) gereksiz yere segmentler arası veya İnternet'e açık olmamasını sağla; bu tek başına EternalBlue sınıfı solucanların yayılma hızını büyük ölçüde sınırlar.
- **İzleme**: SMB oturum açma olaylarını, null session denemelerini, imzasız bağlantı reddedilme/oluşum oranlarını ve anormal RPC çağrı hacimlerini merkezi log/SIEM üzerinden izle.
- **Yama ve envanter disiplini**: SMB sunucu bileşenlerinin (Windows, Samba, gömülü NAS cihazları) sürüm ve yama durumunu düzenli envanterle; kritik bültenler için hızlandırılmış uygulama süreci tanımla.

## Sonuç

SMB'nin güvenlik hikâyesi, eski bir protokolün modern bir tehdit ortamına uyum sağlama çabasının özeti gibidir: SMBv1'in kernel'de işlenen, gevşek doğrulamalı komutları EternalBlue sınıfı yıkıcı zafiyetlere yol açtı; imzalamanın isteğe bağlı bırakılması relay saldırılarını mümkün kıldı; ve null session gibi "güvenilir ağ" varsayımıyla tasarlanmış özellikler bugün keşif için altın madeni haline geldi. Bu üç sorunun ortak kök nedeni aynıdır: protokol, düşmanca (adversarial) bir ağ modeli düşünülmeden tasarlandı ve geriye dönük uyumluluk kaygısıyla güvensiz varsayılanlar uzun yıllar korundu. Savunma tarafında çözüm de aynı ortak noktadan geçer -- gereksiz eski protokol yüzeyini kapatmak, kimlik doğrulama ve bütünlük kontrollerini zorunlu kılmak, ve varsayılan olarak açık bırakılmış anonim erişimi daraltmak. Bu üç ilke uygulandığında, SMB üzerinden gerçekleşen iç ağ sızmalarının büyük çoğunluğu pratikte engellenmiş olur.
