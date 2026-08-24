# Loglama ve Telemetri (Blue Team): Sysmon, Windows Event, Merkezîleştirme ve Görünürlük

## Giriş: Görünürlük Olmayan Yerde Savunma da Yoktur

Mavi takımın (Blue Team) en temel gerçeği şudur: göremediğin bir şeyi savunamazsın. Bir saldırganın ağınızda haftalarca, hatta aylarca fark edilmeden kaldığı vakaların ezici çoğunluğunda kök neden gelişmiş bir sıfırıncı gün (zero-day) değil, basitçe **görünürlük eksikliğidir**. Log kaydı doğru toplanmamış, doğru olaylar (event) hiç üretilmemiş, üretilenler de merkezî bir yerde birleştirilmemiştir. Saldırı gerçekleştikten sonra olay müdahale (incident response) ekibi geriye dönüp bakmak istediğinde ellerinde ya hiç veri olmaz ya da veriler çoktan rotasyona (rotation) uğrayıp silinmiştir.

Bu makale, kurumsal bir Windows ortamında **telemetri** üretmenin, bu telemetriyi **merkezîleştirmenin** ve ondan gerçek savunma değeri çıkarmanın mantığını derinlemesine ele alır. Odak noktaları Sysmon, Windows Event Log altyapısı, log merkezîleştirme mimarileri ve görünürlüğün nasıl ölçülüp genişletileceğidir. Amaç bir komut listesi vermek değil; **neden** böyle çalıştığını ve **nasıl** doğru kurgulanacağını akıl yürüterek anlatmaktır.

## Telemetri Nedir, Log'dan Farkı Nedir

Terimleri netleştirmekle başlayalım, çünkü kavram karışıklığı doğrudan mimari hatalarına yol açar.

**Log**, bir sistemin ürettiği ham olay kaydıdır: "şu zamanda şu kullanıcı giriş yaptı", "şu servis başladı" gibi. Loglar tarihsel olarak sistemlerin kendi ihtiyaçları (hata ayıklama, denetim) için tasarlanmıştır; güvenlik onların birincil amacı değildir.

**Telemetri** ise güvenlik gözlemlenebilirliği (observability) amacıyla, bilinçli olarak üretilen, zenginleştirilmiş ve normalize edilmiş sinyal akışıdır. Sysmon telemetrinin en tipik örneğidir: Windows'un kendi başına üretmediği (veya çok yetersiz ürettiği) süreç oluşturma (process creation), ağ bağlantısı, dosya yaratma gibi olayları yakalar ve zengin bağlamla (hash, ebeveyn süreç, komut satırı) işaretleyerek verir.

Kritik fark şudur: log "ne oldu" der, iyi telemetri "ne oldu, kim yaptı, neyin altında yaptı, neyle yaptı" der. Saldırı tespiti için gereken bağlam ikincisindedir.

## Windows Event Log Altyapısı: Kök Mantık

### Kanallar (Channels) ve Sağlayıcılar (Providers)

Windows olay günlüğü mimarisi, olayları üreten **sağlayıcılar** (providers) ve bunların yazıldığı **kanallar** (channels) üzerine kuruludur. Klasik üç kanal — Application, System, Security — herkesin bildiği yüzeydir. Ancak modern Windows'ta yüzlerce operasyonel kanal bulunur; bunlar `Microsoft-Windows-<Bileşen>/Operational` biçiminde adlandırılır ve mavi takım açısından asıl değerli veri çoğu zaman buralardadır.

Neden bu ayrım önemli? Çünkü birçok kurum yalnızca Security kanalını izler ve PowerShell, WMI, Task Scheduler, Windows Defender, WinRM gibi saldırganların yoğun kullandığı bileşenlerin operasyonel kanallarını hiç toplamaz. Sonuç olarak, saldırgan Security kanalında iz bırakmayan bir teknik kullandığında tamamen görünmez hâle gelir.

### En Kritik Event ID'ler ve Neden Önemli Oldukları

Güvenlik açısından belkemiği oluşturan olay kimliklerini (Event ID) ve arkasındaki mantığı ele alalım:

- **4624 / 4625 (Başarılı / başarısız oturum açma):** Kimlik doğrulama telemetrisinin temelidir. Buradaki asıl değer **Logon Type** alanındadır. Type 3 (network), Type 10 (RemoteInteractive/RDP), Type 4/5 (batch/service) ayrımı, bir hareketin kullanıcı mı yoksa yanal hareket (lateral movement) mi olduğunu anlamanın anahtarıdır. Örneğin bir servis hesabının aniden Type 10 ile giriş yapması güçlü bir anomali sinyalidir.
- **4672 (Özel ayrıcalıklarla oturum açma):** Yönetici seviyesi ayrıcalık atanmasını gösterir; ayrıcalık yükseltme (privilege escalation) ve yönetici hesap kötüye kullanımı takibinin temelidir.
- **4688 (Süreç oluşturma):** Windows'un yerleşik süreç izleme olayıdır. Kritik nokta: komut satırı (command line) kaydını içermesi için ayrı bir grup ilkesi (Group Policy) ayarının açılması gerekir. Bu açılmadığında 4688 neredeyse değersizdir; açıldığında ise Sysmon Event 1'e ciddi bir alternatif olur.
- **4698 / 4702 (Zamanlanmış görev oluşturma/değiştirme):** Kalıcılık (persistence) tespitinin ana kaynağıdır.
- **7045 (Yeni servis kurulumu):** Saldırganların kalıcılık ve SYSTEM ayrıcalığı için servis oluşturması klasik bir tekniktir; bu olay onu yakalar.
- **1102 (Güvenlik günlüğünün temizlenmesi):** Saldırgan iz temizlemeye (anti-forensics) çalıştığında üretilir. Bu olayın kendisi yüksek öncelikli bir alarmdır — "birileri kanıtları silmeye çalışıyor" demektir.

### PowerShell ve Betik Bloğu Loglaması

PowerShell, modern saldırıların ortak paydasıdır çünkü "kara topraktan geçinme" (living off the land) felsefesine mükemmel uyar: sistemde zaten vardır, güçlüdür ve bellekte çalışabilir. Bu yüzden PowerShell telemetrisi ayrı bir başlığı hak eder:

- **Modül Loglama (Module Logging):** Çalıştırılan cmdlet'leri kaydeder.
- **Betik Bloğu Loglama (Script Block Logging, genelde Event ID 4104):** Asıl güç buradadır. Çalıştırılan ham betik bloğunu, hatta gizlenmiş (obfuscated) kodun çözülmüş (deobfuscated) hâlini kaydeder. Saldırganlar Base64 kodlaması, string birleştirme gibi yöntemlerle kod gizlese bile, PowerShell motoru kodu çalıştırmadan önce çözmek zorunda olduğu için betik bloğu loglaması bu çözülmüş hâli yakalar. Bu, gizlemeye karşı savunmanın en güçlü noktalarından biridir.
- **Transcription:** Oturum boyunca girdi/çıktının metin dosyasına dökülmesidir.

Neden bunların hepsi varsayılan kapalı? Çünkü hacim ve gizlilik endişeleri. Script block logging açıkça büyük veri üretebilir. Ama savunma değeri o kadar yüksektir ki, uzman görüşü neredeyse istisnasız açılması yönündedir.

## Sysmon: Neden Windows'un Yerleşik Loglaması Yetmez

### Sysmon'un Var Oluş Nedeni

Sysmon (System Monitor), Windows'un yerleşik olay altyapısının bıraktığı görünürlük boşluklarını doldurmak için tasarlanmış bir çekirdek modu (kernel-mode) sürücüsü ve servisidir. Bir kez kurulduğunda önyükleme sırasında erken başlar, kendi olay kanalına (`Microsoft-Windows-Sysmon/Operational`) zengin telemetri yazar ve yeniden başlatmalar arasında kalıcıdır.

Peki yerleşik 4688 varken neden Sysmon? Çünkü Sysmon olayları çok daha zengin ve tespite yönelik tasarlanmıştır. En kritik olay tiplerini ve arkasındaki mantığı görelim:

- **Event ID 1 (Process Create):** Süreç oluşturmayı yakalar ama 4688'in ötesinde şeyler verir: sürecin **hash'leri** (MD5/SHA1/SHA256/IMPHASH), tam komut satırı, ebeveyn sürecin komut satırı, ve en değerlisi **ProcessGUID**. Bu GUID, farklı olayları tek bir sürece bağlamayı sağlar; bu olmadan olay korelasyonu (correlation) çok zorlaşır. IMPHASH (import hash) ise farklı isimlerle derlenmiş aynı zararlı yazılımı yakalamaya yarar çünkü içe aktarılan fonksiyon tablosu benzer kalır.
- **Event ID 3 (Network Connection):** TCP/UDP bağlantılarını, bağlantıyı başlatan süreçle ilişkilendirerek kaydeder. "Hangi süreç dışarıya bağlandı" sorusunun cevabıdır — komuta-kontrol (C2) tespitinin temeli.
- **Event ID 7 (Image Loaded):** DLL yüklemelerini yakalar. DLL yandan yükleme (DLL side-loading) gibi teknikleri tespit için değerlidir ama hacmi çok yüksek olduğundan dikkatli filtrelenmelidir.
- **Event ID 8 (CreateRemoteThread):** Bir sürecin başka bir sürece iş parçacığı (thread) enjekte etmesini yakalar. Süreç enjeksiyonu (process injection) ve kod enjeksiyonu tekniklerinin klasik imzasıdır.
- **Event ID 10 (Process Access):** Bir sürecin başka bir sürecin belleğine erişmesini (OpenProcess) gösterir. Kimlik bilgisi hırsızlığında (credential dumping) LSASS sürecine erişim bunun tipik örneğidir.
- **Event ID 11 (File Create):** Dosya oluşturmayı yakalar; fidye yazılımı (ransomware) davranışı ve kalıcılık dosyalarını izlemede değerlidir.
- **Event ID 12/13/14 (Registry):** Kayıt defteri (registry) değişikliklerini yakalar; Run anahtarları gibi kalıcılık noktalarını izlemenin temelidir.
- **Event ID 22 (DNS Query):** DNS sorgularını süreçle ilişkilendirir. DNS tüneli ve alan adı üzerinden C2 tespitinde çok kıymetlidir.

### Konfigürasyon Felsefesi: Asıl İş Filtrelemede

Sysmon'un gücü, kuruluşundan değil **konfigürasyonundan** gelir. Varsayılan/boş bir konfigürasyonla Sysmon ya her şeyi yakalar (dayanılmaz gürültü) ya da hiçbir şeyi. İyi bir konfigürasyon şu felsefeyi izler: **gürültüyü dışla, sinyali dâhil et.**

Sysmon konfigürasyonu XML tabanlıdır ve iki temel mantık kullanır:

- **Include/Exclude mantığı:** Her olay tipi için ya belirli koşulları dâhil edersiniz ya da hariç tutarsınız. Doğru yaklaşım genellikle "bilinen iyi/gürültülü olanı hariç tut, gerisini yakala" değildir; tam tersine "bilinen kötü davranışları dâhil et" de tek başına yetmez. Olgun ekipler ikisini bilinçli harmanlar.
- **Kural gruplandırma ve öncelik:** Kurallar arasında `Onmatch` ve mantıksal operatörlerle karmaşık koşullar kurulabilir.

Bu alanda topluluk standardı olmuş, açık kaynak, sürekli güncellenen konfigürasyon şablonları vardır (örneğin SwiftOnSecurity'nin ve Olaf Hartong'un yaygın olarak referans alınan konfigürasyonları). Bunların değeri, binlerce ortamda test edilmiş gürültü filtrelerini hazır sunmalarıdır. Uzman tavsiyesi: sıfırdan yazmak yerine olgun bir tabanla başlayıp kendi ortamınıza göre uyarlamaktır.

Önemli bir uyarı: konfigürasyon **statik değildir**. Ortam değiştikçe, yeni uygulamalar geldikçe gürültü profili değişir; konfigürasyon sürüm kontrolünde (version control) tutulmalı ve düzenli gözden geçirilmelidir.

## Saldırganın Bakışı: Telemetriyi Kör Etmek

Savunmayı doğru kurmak için saldırganın telemetriye nasıl saldırdığını anlamak şarttır. Görünürlük iki yönlü bir savaştır ve saldırganlar tam olarak sizin görmenizi engellemeye çalışır.

### İz Temizleme ve Log Manipülasyonu

En kaba yöntem log temizlemedir (`wevtutil cl` benzeri veya API çağrılarıyla). Ama bu gürültülüdür: Security günlüğünün temizlenmesi 1102 olayını üretir ve dikkatli bir ekipte anında alarm çalar. Bu yüzden gelişmiş saldırganlar toptan silme yerine **seçici manipülasyon** dener — belirli olayları çıkarmaya çalışan tekniklerdir. Buradaki savunma dersi: **logu yerinde bırakma.** Log yerel diskte kaldığı sürece saldırganın manipülasyon menzilindedir. Merkezîleştirme bu yüzden yalnızca kolaylık değil, bütünlük (integrity) meselesidir.

### Servisi Durdurmak ve Olay Kanalını Etkisiz Bırakmak

Saldırgan yeterli ayrıcalığa (genelde SYSTEM) ulaştığında Sysmon servisini durdurmayı, sürücüsünü kaldırmayı veya Windows Event Log servisini askıya almayı deneyebilir. Bunun bir varyantı, olay toplama iş parçacıklarını hedef alan tekniklerdir. 

Savunma mantığı çok nettir ve çoğu ekibin gözden kaçırdığı yerdir: **kendi telemetri altyapınızın sağlığını izlemelisiniz.** Sysmon servisinin durması, Event Log servisinin kesilmesi, ya da bir ana bilgisayardan (host) beklenen log akışının aniden kesilmesi başlı başına yüksek öncelikli bir alarm olmalıdır. "Log yokluğu" da bir sinyaldir — belki de en önemli sinyaldir.

### DLL Yandan Yükleme ve Gizleme ile Sinyal Zayıflatma

Saldırganlar tespit edilmemek için imzalı ikili dosyaların içine yerleşir (living off the land binaries — LOLBins), komut satırlarını gizler, PowerShell kodunu Base64/sıkıştırma ile maskeler. Buradaki savunma, daha önce anlattığımız script block logging gibi **çözülmüş içeriği yakalayan** telemetriye ve komut satırı loglamasına dayanır. Gizleme ham metni bozar ama davranış izini bozamaz — enjeksiyon hâlâ Event 8/10 üretir, ağ bağlantısı hâlâ Event 3 üretir. Bu yüzden davranış temelli telemetri, imza/string temelli tespitten daha dayanıklıdır.

### Telemetriyi Boğmak (Log Flooding)

İnce bir teknik, kasıtlı olarak devasa miktarda gürültü olay üretip gerçek saldırı izini boğmaktır veya log toplama boru hattını (pipeline) çökertmektir. Savunma: hız sınırlama (rate limiting), anomali bazlı hacim izleme ve toplama katmanının dayanıklı tasarlanması.

## Merkezîleştirme: Neden ve Nasıl

### Neden Merkezîleştirme Zorunludur

Yerel logların üç ölümcül zayıflığı vardır:
1. **Bütünlük:** Az önce anlatıldığı gibi, saldırgan makinede kaldıkça yerel logu değiştirebilir/silebilir.
2. **Erişilebilirlik:** Bir olay incelemesinde binlerce makineye tek tek bağlanmak imkânsızdır; korelasyon için tüm veriler tek yerde olmalıdır.
3. **Kalıcılık ve saklama:** Yerel loglar sınırlı boyutlu döngüsel dosyalardır; rotasyona uğrar. Merkezî depoda saklama süresini (retention) siz belirlersiniz.

Merkezîleştirmenin en derin gerekçesi korelasyondur: tek bir makinedeki 4624 anlamsızken, on farklı makinede kısa sürede aynı hesapla oluşan 4624 dizisi net bir yanal hareket örüntüsüdür. Bunu ancak veriler birleştiğinde görebilirsiniz.

### Toplama Mimarileri

Windows dünyasında iki temel yaklaşım vardır:

- **Windows Event Forwarding (WEF):** Windows'un yerleşik, ajansız (agentless) mekanizmasıdır. Kaynak bilgisayarlar olaylarını bir toplayıcıya (collector, WEC) iletir. Avantajı: ek ajan gerektirmez, WinRM üzerinden çalışır, Microsoft tarafından desteklenir. Abonelikler (subscriptions) push veya pull modunda kurulabilir. Dezavantajı: zenginleştirme ve dönüştürme yetenekleri sınırlıdır; genellikle WEC'ten sonra bir SIEM'e beslenir.
- **Ajan tabanlı toplama (agent-based):** Her makineye bir toplama ajanı kurulur (örneğin bir log gönderici veya EDR ajanı). Avantajı: yerel filtreleme, ayrıştırma (parsing), zenginleştirme, tamponlama (buffering) ve güvenli iletim. Ağ kesintisinde tamponlayıp sonra gönderebilme özelliği kritik dayanıklılık sağlar.

Pratikte olgun kurumlar ikisini de kullanır: WEF'i geniş kapsama için, ajanları derin telemetri ve dayanıklılık için.

### SIEM ve Veri Boru Hattı

Toplanan veri bir SIEM (Security Information and Event Management) veya günlük analiz platformunda (Splunk, Elastic/ELK, Microsoft Sentinel, vb.) toplanır. Burada asıl mühendislik zorluğu **normalizasyondur**: farklı kaynaklardan gelen alanların ortak bir şemaya oturtulması. Bu olmadan tespit kuralları her kaynak için ayrı yazılmak zorunda kalır ve bakım kâbusa döner.

Bir olgun boru hattı şu katmanlardan geçer: **üretim** (Sysmon/Windows) → **toplama** (WEF/ajan) → **taşıma** (güvenli, tamponlu) → **ayrıştırma ve normalizasyon** → **zenginleştirme** (tehdit istihbaratı, varlık bağlamı, coğrafi konum) → **saklama ve indeksleme** → **tespit ve uyarı** → **arşiv**. Her katman bir arıza noktasıdır; her birinin izlenmesi gerekir.

## Görünürlük: Ölçmek ve Genişletmek

### Görünürlüğü Ölçmek — MITRE ATT&CK Haritalama

"Yeterince görüyor muyuz?" sorusunun cevabı hislerle verilemez; ölçülmelidir. Sektör pratiği, telemetriyi **MITRE ATT&CK** çerçevesine haritalamaktır. Her tekniğin (technique) tespiti için hangi veri kaynağının gerektiğini belirler, sahip olduğunuz kaynaklarla karşılaştırır ve **görünürlük boşluklarını** (visibility gaps) ortaya çıkarırsınız. Örneğin "credential dumping" tespiti için LSASS'a process access telemetrisi (Sysmon Event 10) gerekir; bunu toplamıyorsanız o tekniğe karşı körsünüz ve bunu bilerek karar vermelisiniz.

Bu haritalama, güvenlik yatırımını duygusal değil kanıta dayalı hâle getirir: "en çok hangi tekniklere karşı körüz ve bunları kapatmak için hangi veri kaynağını eklemeliyiz?"

### Kritik Kör Noktalar

Görünürlüğün sık atlanan alanları:
- **Kimlik katmanı:** Kerberos anomalileri (örneğin altın/gümüş bilet göstergeleri), zayıf şifreleme türleri, olağandışı bilet talepleri. Domain Controller olay loglaması bu yüzden ayrıca kritiktir.
- **Bulut ve kimlik sağlayıcı logları:** Hibrit ortamlarda saldırı çoğu zaman şirket içi ile bulut arasında hareket eder; sadece Windows host telemetrisi bakmak yarım resim verir.
- **Şifreli trafik:** Ağ görünürlüğü şifreleme ile azalır; bu yüzden host tabanlı telemetri (Sysmon Event 3/22) giderek daha kritik hâle gelir.

## Yaygın Hatalar

Sahada tekrar tekrar görülen ve pahalıya patlayan hatalar:

- **Sadece Security kanalını toplamak.** PowerShell, WMI, Task Scheduler, Defender operasyonel kanalları toplanmaz ve saldırgan bu boşluklarda çalışır.
- **Sysmon'u varsayılan/boş konfigürasyonla kurmak.** Ya boğucu gürültü ya değersiz sessizlik üretir. Konfigürasyon işin ta kendisidir.
- **4688 komut satırı loglamasını açmamak veya PowerShell script block logging'i kapalı bırakmak.** En değerli iki telemetri kaynağı varsayılan kapalıdır ve çoğu ortamda öyle kalır.
- **Logu yalnızca yerelde tutmak.** Bütünlük ve korelasyon imkânsızlaşır; saldırgan izini yok eder.
- **Log akışı sağlığını izlememek.** Bir host'tan log akışının kesilmesi fark edilmez; oysa bu güçlü bir uzlaşma (compromise) sinyalidir.
- **Saklama süresini çok kısa tutmak.** Saldırganların ortalama tespit süresi genelde haftalarla ölçülür; birkaç günlük saklama, olay geriye dönük incelenirken veriyi çoktan yok etmiş olur.
- **Toplayıp hiç bakmamak.** Alarm ve tespit kuralı olmadan veri sadece disk maliyetidir. Toplama tespitin ön koşuludur, yerine geçmez.
- **Zaman senkronizasyonu ihmali.** Farklı makineler farklı saatlerde çalışırsa korelasyon bozulur. Tutarlı zaman kaynağı (NTP) ve tercihen UTC standardı şarttır.

## En İyi Pratikler

Yukarıdakilerin karşısına akıl yürütmeyle konumlanan sağlam pratikler:

1. **Görünürlüğü tehditlere göre planla, çıktısını ATT&CK'e haritala.** Neyi topladığını değil, hangi saldırı tekniğine karşı görüş sağladığını takip et. Boşlukları bilinçli kabul et veya kapat.
2. **Sysmon konfigürasyonunu olgun bir tabana dayandır, sürüm kontrolünde tut, düzenli gözden geçir.** Konfigürasyon canlı bir varlıktır, tek seferlik bir kurulum değildir.
3. **Yüksek değerli telemetriyi mutlaka aç:** process creation komut satırı, PowerShell script block logging, DNS ve ağ ilişkilendirme, kimlik/oturum tipi ayrıntısı.
4. **Merkezîleştir ve logu hızla host'tan çıkar.** Yerel diskteki her dakika, saldırganın manipülasyon fırsatıdır. İletimi güvenli (şifreli) ve tamponlu tasarla.
5. **Telemetri altyapının kendisini izle.** Servis durması, ajan sessizliği, log akışı kesintisi ve log temizleme olayları (1102 gibi) birinci sınıf alarmlar olmalı.
6. **Davranış temelli tespite ağırlık ver.** İmza ve string gizlenebilir; enjeksiyon, süreç erişimi, olağandışı ebeveyn-çocuk süreç ilişkileri gibi davranışlar çok daha dayanıklı sinyallerdir.
7. **Normalizasyon ve zenginleştirmeye yatırım yap.** Ham veri değil, bağlamla zenginleştirilmiş ve ortak şemaya oturmuş veri tespit üretir.
8. **Saklama süresini tehdit gerçekliğine göre belirle.** En azından tespit-müdahale döngüsünü kapsayacak, tercihen aylara uzanan bir sıcak/soğuk saklama katmanı kur.
9. **Zaman tutarlılığını garanti et.** UTC ve senkron NTP, korelasyonun görünmez ama vazgeçilmez temelidir.
10. **Kör noktaları düzenli test et — mor takım (purple team).** Bilinen teknikleri kontrollü çalıştırıp telemetride görünüp görünmediklerini doğrula. Tespit ancak sınandığında gerçektir.

## Sonuç

Loglama ve telemetri, mavi takımın gösterişsiz ama en belirleyici disiplinidir. Parlak bir tespit kuralı, altında doğru veri yoksa boşluğa bakar. Bu yüzden mimarinin sırası nettir: önce **doğru telemetriyi üret** (Sysmon ve Windows'un derin kanalları), sonra onu **bütünlüğünü koruyarak merkezîleştir**, ardından **normalize edip zenginleştir**, en sonunda üzerine **tespit ve altyapı sağlık izlemesi** kur. Ve tüm bunları ATT&CK gibi bir çerçeveyle ölçerek görünürlüğünü kanıta dayandır. Saldırgan sizin göremediğiniz yerde yaşar; bu makalenin tek bir cümlelik özü, o karanlık bölgeleri sistematik olarak aydınlatmaktır.
