# Network Access Control ve 802.1X Kimlik Doğrulama (NAC, Port Security, MACsec)

## Giriş: Ağ Katmanında "Kimsin ve Bağlanabilir misin?"

Zero Trust felsefesi "hiçbir şeye örtük güvenme, her erişimi doğrula" der ama bunu genellikle uygulama ve kullanıcı katmanında anlatırız. Oysa güven ihlallerinin çoğu çok daha aşağıda, fiziksel/veri bağı katmanında (Layer 2) başlar: birisi lobideki bir IP telefonun kablosunu çıkarıp kendi laptopunu takar, bir toplantı odasındaki boş prize sızma cihazı bağlar, ya da kurumsal Wi-Fi'a yetkisiz bir cihaz katılır. **Network Access Control (NAC)** tam olarak bu sorunu çözer: bir cihaz ağa fiziksel veya kablosuz olarak bağlandığı anda, ona trafik akışına izin vermeden önce "sen kimsin, uyumlu musun, hangi ağ segmentine aitsin?" sorularını sorar.

Bu makale NAC'ın çekirdek mekanizmalarını, özellikle **IEEE 802.1X** kimlik doğrulama çerçevesini, **port security** kontrollerini ve **MACsec (IEEE 802.1AE)** ile hat şifrelemesini derinlemesine açıklar. Amaç mekanizmayı gerçekten anlamak ve buna dayalı tespit/savunma kurabilmektir.

## NAC Nedir? Tanım ve Temel Mantık

**Network Access Control**, bir cihazın ağa katılımını politika temelli olarak yöneten bir kontrol katmanıdır. NAC üç temel soruyu yanıtlar:

1. **Authentication (kimlik doğrulama):** Cihaz veya kullanıcı gerçekten iddia ettiği kişi/şey mi?
2. **Authorization (yetkilendirme):** Doğrulandıktan sonra hangi ağ kaynaklarına, hangi VLAN'a veya hangi segmente erişebilir?
3. **Posture assessment (uyumluluk/duruş değerlendirmesi):** Cihaz güvenlik gereksinimlerini karşılıyor mu? (güncel antivirüs, disk şifreleme, yama seviyesi, EDR ajanı çalışıyor mu vb.)

NAC iki temel zamanlamada çalışabilir:

- **Pre-admission (kabul öncesi):** Cihaz ağa girmeden önce doğrulanır ve değerlendirilir. En güçlü modeldir.
- **Post-admission (kabul sonrası):** Cihaz ağa girer ama davranışına göre sonradan kısıtlanabilir. Genellikle davranışsal izleme ile birleşir.

NAC'ın uygulama biçimleri de değişir: **agent-based** (cihazda çalışan bir istemci ajanı posture bilgisi toplar) ya da **agentless** (ajan gerektirmeden fingerprinting, DHCP/HTTP parmak izi, aktif tarama ile cihaz sınıflandırılır). Yönetilmeyen cihazlar (IoT, yazıcı, kamera) için agentless yaklaşım zorunludur.

## 802.1X: NAC'ın Kalbindeki Kimlik Doğrulama Çerçevesi

802.1X, port-based network access control için IEEE standardıdır. Kablolu switch portlarında ve kablosuz erişim noktalarında (WPA2/WPA3-Enterprise) çalışır. Üç aktörden oluşan bir mimariye sahiptir:

- **Supplicant:** Kimlik doğrulanmak isteyen istemci (laptop, telefon). Üzerinde 802.1X supplicant yazılımı çalışır (Windows'ta yerleşik, Linux'ta wpa_supplicant vb.).
- **Authenticator:** Portu kontrol eden ağ cihazı (switch veya kablosuz AP). Kapı bekçisidir; kararı kendisi vermez, mesajları taşır.
- **Authentication Server:** Kararı veren sunucu, tipik olarak bir **RADIUS** sunucusu (Microsoft NPS, FreeRADIUS, Cisco ISE, Aruba ClearPass vb.). Kullanıcı/cihaz kimliğini bir dizin servisiyle (Active Directory, LDAP) veya sertifika altyapısıyla doğrular.

### Çalışma Mantığı: EAP ve EAPOL

802.1X'in taşıdığı asıl protokol **EAP (Extensible Authentication Protocol)**'tur. EAP tek bir kimlik doğrulama yöntemi değil, birçok yöntemi taşıyabilen bir çerçevedir. Supplicant ile authenticator arasında EAP mesajları **EAPOL (EAP over LAN)** ile Layer 2 üzerinde taşınır; authenticator ile RADIUS sunucusu arasında ise EAP mesajları RADIUS paketleri içine sarılarak iletilir.

Temel akış şöyledir:

1. Port başlangıçta **"unauthorized"** durumundadır. Bu durumda porttan yalnızca EAPOL trafiği geçebilir; başka hiçbir veri (IP, DHCP dahil) geçmez.
2. Cihaz bağlanınca supplicant `EAPOL-Start` gönderir ya da authenticator `EAP-Request/Identity` ile kimlik ister.
3. Kimlik ve kimlik doğrulama mesajları supplicant → authenticator → RADIUS zinciri boyunca gidip gelir.
4. RADIUS başarılı doğrulamada `Access-Accept`, başarısızda `Access-Reject` döndürür.
5. `Access-Accept` gelince authenticator portu **"authorized"** durumuna alır ve normal trafik akmaya başlar. RADIUS yanıtı ayrıca hangi VLAN'a atanacağı, hangi ACL'nin uygulanacağı gibi yetkilendirme öznitelikleri de taşıyabilir (dynamic VLAN assignment).

### EAP Yöntemleri ve Güvenlik Farkları

Hangi EAP yönteminin kullanıldığı güvenlik açısından kritiktir:

- **EAP-TLS:** Her iki taraf da X.509 sertifikası kullanır (mutual authentication). En güçlü yöntemdir çünkü paylaşılan/çalınabilir parola yoktur; kimlik özel anahtara bağlıdır. Bir PKI altyapısı gerektirir, bu yüzden işletmesi daha zahmetlidir.
- **PEAP (Protected EAP) ve EAP-TTLS:** Önce sunucu sertifikasıyla bir TLS tüneli kurulur, iç kimlik doğrulama (genellikle kullanıcı adı/parola, MSCHAPv2) bu tünelin içinde yapılır. Doğru yapılandırıldığında güvenlidir ama zayıf iç yöntemler ve yanlış istemci ayarları risk taşır.
- **EAP-FAST:** Cisco kökenli, tünel tabanlı bir yöntem.

Genel kural: mümkünse **sertifika tabanlı EAP-TLS** tercih edilir. Parola tabanlı yöntemlerde tehlike, supplicant'ın sunucu sertifikasını **doğrulamamasıdır** — bu doğrulama kapalıysa saldırgan sahte bir RADIUS/AP kurarak kullanıcının iç kimlik bilgilerini (özellikle MSCHAPv2 challenge/response'unu) yakalayıp offline kırabilir. Bu, kurumsal Wi-Fi'a yönelik "evil twin" saldırılarının temelidir.

## Kritik Zayıflık: MAB ve 802.1X Bypass

802.1X'i her cihaz konuşamaz. Yazıcılar, IP kameralar, bazı IoT cihazları supplicant çalıştıramaz. Bunlar için **MAB (MAC Authentication Bypass)** kullanılır: cihazın MAC adresi RADIUS'ta bir izin listesine karşı doğrulanır. Bu pratik bir gerekliliktir ama **temel bir zayıflıktır**, çünkü MAC adresleri kolayca taklit edilebilir (spoof). Saldırgan izinli bir yazıcının MAC'ini kopyalayarak ağa MAB üzerinden girebilir.

Daha sinsi bir bypass tekniği ise, 802.1X ile doğrulanmış meşru bir cihazın arkasına şeffaf bir cihaz yerleştirmektir. Doğrulanmış cihaz (örneğin bir masaüstü) porta bağlıyken, araya giren cihaz onun MAC ve IP kimliğini kullanarak aynı authorized oturumun üzerinden trafik enjekte edebilir. Bunun nedeni birçok 802.1X kurulumunun yalnızca **oturum başında** doğrulama yapıp sonrasında paket bazında bütünlük/kimlik kontrolü yapmamasıdır. İşte MACsec'in devreye girdiği yer tam da burasıdır.

## MACsec (IEEE 802.1AE): Hattın Kendisini Şifrelemek

**MACsec**, Layer 2'de hop-by-hop (bağlantı bazında) şifreleme ve bütünlük sağlar. TLS/IPsec uygulama veya ağ katmanında çalışırken, MACsec doğrudan Ethernet çerçevelerini korur. Sağladıkları:

- **Confidentiality:** Ethernet payload'u şifrelenir (GCM-AES ile).
- **Integrity & authenticity:** Her çerçeveye bir bütünlük etiketi (ICV) eklenir; değiştirilen veya sahte çerçeveler reddedilir.
- **Replay protection:** Paket numaralandırma ile tekrar saldırıları engellenir.

MACsec her bağlantı segmentinde ayrı çalışır (host-switch veya switch-switch). Anahtar yönetimi genellikle **MKA (MACsec Key Agreement, IEEE 802.1X-2010 içinde tanımlı)** ile yapılır; ilk kimlik doğrulama (örneğin EAP-TLS) sonucunda türetilen bir anahtardan MACsec oturum anahtarları üretilir. Bu, 802.1X ile MACsec'in doğal olarak birlikte konumlandığını gösterir: 802.1X "kim olduğunu" doğrular, MACsec o bağlantı üzerindeki "her çerçeveyi" korur.

MACsec'in çözdüğü asıl tehdit, fiziksel hatta erişimi olan bir saldırganın trafiği dinlemesi (tap) veya araya girmesidir (yukarıda anlatılan port bypass dahil). Şifreli ve bütünlük korumalı bir bağlantıda, araya giren cihaz geçerli çerçeve üretemez.

## Port Security: Basit Ama Değerli Katman

**Port security** switch üzerinde çalışan ve 802.1X'ten daha basit bir kontroldür. Temel işlevleri:

- Bir portta öğrenilen **MAC adresi sayısını sınırlamak** (örneğin tek MAC). Bu, bir porta hub/switch takıp çok sayıda cihaz bağlamayı ya da MAC flooding saldırılarını sınırlar.
- **Sticky MAC:** Portun ilk gördüğü MAC'i kalıcı olarak öğrenmesi.
- **Violation action:** İhlal olduğunda portu kapatma (shutdown/err-disable), trafiği düşürme (restrict) veya sessizce engelleme (protect).

Port security tek başına zayıftır çünkü MAC spoofing'e dayanıklı değildir — saldırgan izinli MAC'i taklit ederse sınırı aşmaz. Bu yüzden port security, 802.1X'in yerine değil, onun tamamlayıcısı ve derinlemesine savunmanın bir katmanı olarak düşünülmelidir. Ayrıca MAC flooding'e karşı switch'in CAM tablosunu koruyarak MAC'in dinlemeye açılmasını (fail-open davranışını) engeller.

## Somut Örnek: Bir Portun Yaşam Döngüsü

Diyelim bir çalışan laptopunu toplantı odasındaki bir prize taktı:

1. Port unauthorized; yalnızca EAPOL geçiyor.
2. Laptop'un supplicant'ı EAP-TLS ile makine sertifikasını sunuyor.
3. RADIUS sunucusu sertifikayı PKI'ye karşı doğruluyor, cihazın AD'de "Kurumsal Laptoplar" grubunda olduğunu görüyor.
4. Posture kontrolü: EDR ajanı aktif, disk şifreli. Uyumlu.
5. RADIUS `Access-Accept` + "VLAN 20 (Çalışan)" özniteliğini döndürüyor.
6. Port authorized; laptop VLAN 20'ye atanıyor.
7. Aynı porta yetkisiz bir cihaz takılırsa, geçerli sertifikası olmadığından `Access-Reject` alıyor ve port ona kapalı kalıyor — ya da politika gereği kısıtlı bir "quarantine/remediation VLAN"ına düşürülüyor.

Bu örnekte 802.1X kimliği, RADIUS yetkilendirmeyi ve VLAN atamasını, posture uyumluluğu sağlıyor; MACsec eklenirse laptop-switch hattı şifreleniyor.

## Tespit (Detection)

NAC katmanında görünürlük ve tespit için odaklanılacak sinyaller:

- **RADIUS Access-Reject spike'ları:** Belirli bir portta veya bölgede ani ret artışı, yetkisiz bağlanma denemelerine işaret eder. RADIUS loglarını SIEM'e aktarın ve başarısız kimlik doğrulama oranını izleyin.
- **Aynı MAC'in farklı portlarda görünmesi:** MAC spoofing veya cihaz taşınması belirtisi. Switch MAC tablosu değişikliklerini ve NAC envanterini korele edin.
- **MAB ile giren cihazlarda anormallik:** Bir yazıcı olması gereken bir MAC'in aniden farklı bir cihaz parmak izi (OS fingerprint, açık portlar) sergilemesi, MAC taklidini gösterir. Agentless profiling ile beklenen davranıştan sapmayı yakalayın.
- **EAPOL anomali ve sahte RADIUS/AP:** Evil twin tespiti için kablosuz ortamda beklenmeyen SSID/BSSID ve sertifika parmak izi değişikliklerini izleyin.
- **Port security ihlal olayları (err-disable):** Bunları gürültü olarak değil, olay olarak toplayın; fiziksel yetkisiz cihaz göstergesi olabilir.
- **Posture değişimi:** Uyumluyken uyumsuza düşen (EDR devre dışı, şifreleme kapalı) cihazlar, ele geçirilme veya politika kaçırma belirtisi olabilir.

## Savunma (Defense) ve İyi Uygulamalar

- **Mümkün olan her yerde EAP-TLS (sertifika tabanlı) kullanın.** Parola tabanlı yöntemler kaçınılmazsa, supplicant tarafında **sunucu sertifikası doğrulamasını zorunlu kılın** (güvenilen CA'yı ve sunucu adını pinleyin). Bu tek ayar birçok evil-twin/kimlik hırsızlığı senaryosunu kapatır.
- **MAB'ı asgariye indirin ve sıkılaştırın.** MAB kullanılan cihazları ayrı, kısıtlı VLAN'lara koyun; bu cihazlara mikro-segmentasyon ve ACL uygulayın ki taklit edilen MAC ile girilse bile hareket alanı dar olsun.
- **Dynamic segmentation / VLAN assignment ile Zero Trust'ı Layer 2'ye indirin.** Cihaz sınıfına ve posture'a göre segment atayın; misafir, IoT, kurumsal trafiği ayırın.
- **802.1X'i MACsec ile birlikte konumlandırın.** Kritik segmentlerde (data center switch-to-switch, hassas kullanıcı bağlantıları) MACsec ile hattı şifreleyerek fiziksel tap ve port bypass tehdidini ortadan kaldırın.
- **Port security'yi tamamlayıcı olarak açık tutun.** Erişim portlarında MAC sayısını sınırlayın, sticky MAC ve uygun violation action tanımlayın; trunk/uplink portlarında dikkatli olun.
- **Fail durumu politikasını bilinçli seçin.** RADIUS erişilemezse ne olacak? "Fail-open" (herkesi al) operasyonel süreklilik sağlar ama güvenliği delebilir; "fail-closed" güvenlidir ama kesinti riski taşır. Kritik ortamlarda kademeli/kritik-erişim politikaları tanımlayın.
- **RADIUS altyapısını yedekli ve sertleştirilmiş tutun.** RADIUS shared secret'lar güçlü olsun, yönetim düzlemi izole olsun; RADIUS'un ele geçirilmesi tüm NAC'ı çökertir.
- **Posture assessment'ı gerçek bir gate olarak kullanın**, sadece raporlama için değil. Uyumsuz cihazları remediation VLAN'ına yönlendirin.
- **Envanter ve görünürlüğü sürekli tutun.** NAC ancak gördüğü cihazları kontrol edebilir; agentless profiling ile yönetilmeyen cihazları da kapsayın.

## Yaygın Hatalar

- **802.1X'i açıp supplicant'ta sunucu doğrulamasını yapılandırmamak.** En sık ve en tehlikeli hata. Kimlik doğrulama var gibi görünür ama saldırgan sahte sunucuyla araya girebilir.
- **Her şeyi MAB'a düşürmek.** "802.1X sorun çıkarıyor" diye çok sayıda portu kalıcı MAB'a almak, NAC'ı fiilen MAC izin listesine indirger — kolayca aşılır.
- **Fail-open'ı fark etmeden bırakmak.** RADIUS erişilemediğinde portların açılması, saldırgana RADIUS'u DoS ile devre dışı bırakıp serbest giriş fırsatı verebilir.
- **MACsec'i "IPsec/TLS var, gerek yok" diye atlamak.** Bunlar farklı katmanlardır; Layer 2 tap ve bypass tehdidini yalnızca MACsec kapatır.
- **Port security'yi 802.1X yerine kullanmak.** MAC tabanlı olduğu için tek başına gerçek kimlik doğrulama sağlamaz.
- **Dinamik VLAN/ACL'yi test etmeden devreye almak.** Yanlış öznitelik eşlemesi ya herkesi yanlış segmente atar ya da meşru cihazları dışarıda bırakıp geniş kesintiye yol açar.
- **RADIUS ve switch loglarını SIEM'e aktarmamak.** NAC'ın en değerli tespit sinyalleri log'lardadır; toplanmazsa tüm bu mekanizma sessiz çalışır ve ihlaller görünmez kalır.

## Özet

NAC, Zero Trust'ı ağın en alt katmanına indirir: cihaz bağlandığı anda kimliğini (802.1X/EAP), yetkisini (RADIUS ile dinamik VLAN/ACL) ve uyumluluğunu (posture) doğrular. 802.1X kimliği kurar, MAB kaçınılmaz istisnaları yönetir ama zayıf halkadır, port security ucuz bir tamamlayıcı katmandır ve MACsec hattın kendisini şifreleyerek fiziksel/bypass tehditlerini kapatır. Güçlü bir NAC mimarisi bu bileşenleri derinlemesine savunma olarak birlikte kullanır, sunucu sertifikası doğrulamasını zorunlu kılar, fail politikasını bilinçle seçer ve her şeyi SIEM'e loglayarak sürekli tespit sağlar.
