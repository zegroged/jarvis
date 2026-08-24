# VPN ve IPsec: Tünelleme, IKE, Zayıflıklar ve ZTNA'ya Geçiş

## Giriş ve Tanım

VPN (Virtual Private Network), güvenilmez bir taşıyıcı ağ (çoğunlukla açık internet) üzerinden, sanki iki taraf aynı özel ağ üzerindeymiş gibi mahrem bir iletişim kanalı kuran teknolojilerin genel adıdır. Temel vaadi üç güvenlik özelliğini bir arada sunmaktır: gizlilik (confidentiality) yani trafiğin araya girenler tarafından okunamaması, bütünlük (integrity) yani trafiğin yolda değiştirilememesi, ve kimlik doğrulama (authentication) yani karşı tarafın gerçekten iddia ettiği kişi olması. Bu üçlü sağlanmadan kurulan bir "tünel" sadece bir yanılsama olur.

IPsec (Internet Protocol Security), IP katmanında (Layer 3) çalışan ve bu güvenlik özelliklerini standartlaştıran bir protokol ailesidir. IPsec'i özel kılan, uygulamalardan bağımsız çalışmasıdır: TCP, UDP ya da ICMP fark etmeksizin, IP paketinin kendisini koruma altına aldığı için üstteki uygulamaların IPsec'ten haberdar olması gerekmez. Bu yüzden site-to-site (ofisler arası) bağlantılarda ve klasik kurumsal remote-access VPN'lerde onlarca yıldır omurga olmuştur.

IPsec üç ana yapı taşından oluşur: **AH** (Authentication Header), **ESP** (Encapsulating Security Payload) ve **IKE** (Internet Key Exchange). AH sadece bütünlük ve kimlik doğrulama sağlar, şifreleme yapmaz ve NAT ile geçinemediği için bugün pratikte neredeyse terk edilmiştir. Gerçek işi ESP yapar; hem şifreleme hem bütünlük sunar. IKE ise bu şifrelemenin anahtarlarını taraflar arasında güvenli biçimde pazarlığa oturtan beyindir.

## Kök Neden: IPsec Neden Bu Kadar Katmanlı ve Karmaşık?

IPsec'in karmaşıklığını anlamak için çözmeye çalıştığı temel probleme bakmak gerekir. İki taraf açık internet üzerinden konuşacaksa, önce ortak bir gizli anahtar (shared secret) üretmeleri lazım. Ama bu anahtarı düz metin olarak gönderemezler, çünkü dinleyen biri onu yakalayıp tüm iletişimi çözebilir. İşte buradaki "yumurta-tavuk" problemi IPsec'in iki fazlı yapısının kök nedenidir.

Çözüm, **Diffie-Hellman (DH)** anahtar değişimidir. DH'nin dahiyane yanı, iki tarafın hattı dinleyen birinin bile hesaplayamayacağı ortak bir sırra, hiç o sırrı hattan geçirmeden ulaşabilmesidir. Her iki taraf kendi özel değerini gizli tutar, sadece açık değerlerini paylaşır ve matematiksel olarak aynı ortak sonuca varırlar. Dinleyici açık değerleri görse bile, ayrık logaritma probleminin (discrete logarithm problem) zorluğu yüzünden ortak sırrı geriye doğru hesaplayamaz. IPsec işte bu yüzden önce bir "anahtar üretme kanalı" kurar, sonra o kanalın içinde asıl veri anahtarlarını pazarlıkla belirler. Bu ikilik gereksiz bulunabilir, ama aslında güvenliğin temelidir: kimlik doğrulama ve anahtar üretimi ile veri şifrelemesini birbirinden yalıtmak, birinin ele geçirilmesinin diğerini otomatik çökertmesini engeller.

### Tünel Modu ve Transport Modu

ESP iki farklı modda çalışabilir ve aralarındaki fark, VPN mimarisini doğrudan belirler.

**Transport modunda**, orijinal IP başlığı korunur, sadece paketin taşıdığı veri (payload) şifrelenir. Bu, uçtan uca (host-to-host) senaryolarda kullanılır; iki sunucu doğrudan birbiriyle güvenli konuşacaksa mantıklıdır. Ancak kaynak ve hedef IP adresleri açıkta kaldığı için, trafik analizi (traffic analysis) yapan biri kimin kiminle konuştuğunu görebilir.

**Tünel modunda** ise tüm orijinal IP paketi (başlık dahil) şifrelenip yeni bir IP başlığının içine sarılır (encapsulation). Dışarıdan bakan biri sadece iki VPN gateway'inin IP adreslerini görür; içerideki gerçek kaynak ve hedef gizlenir. Site-to-site VPN'lerin tamamı ve klasik remote-access senaryoları tünel modunu kullanır. "Tünel" metaforu tam da buradan gelir: paketiniz, dışarıdan içi görünmeyen bir boru içinden geçer. Tünel modunun bedeli ek başlık yükü (overhead) ve dolayısıyla MTU sorunlarıdır; bu, ilerideki "yaygın hatalar" bölümünün ana temalarından biri olacak.

## IKE: Tünelin Kalbi

IKE, IPsec'in en kritik ve en çok yanlış anlaşılan parçasıdır. Görevi, iki tarafın hangi şifreleme algoritmalarını kullanacağına karar vermesi, birbirlerinin kimliğini doğrulaması ve ortak anahtarları üretmesidir. Bu pazarlığın sonucunda kurulan mutabakata **SA** (Security Association) denir. Bir SA, "şu algoritmayla, şu anahtarla, şu kadar süre boyunca konuşacağız" anlaşmasının teknik karşılığıdır.

### IKEv1 vs IKEv2: Neden Yeni Sürüm Geldi?

**IKEv1** iki fazda çalışır. Phase 1'de taraflar bir "yönetim kanalı" (ISAKMP SA) kurar; burada Diffie-Hellman ile ortak sır üretilir ve kimlik doğrulaması yapılır. Phase 1'in kendisi iki alt moddan birinde işler: **Main Mode** (altı mesaj, kimlik bilgilerini şifreli gönderir, daha güvenli) veya **Aggressive Mode** (üç mesaj, hızlı ama kimlik bilgilerini yeterince korumaz). Phase 2 (Quick Mode) ise Phase 1'in koruması altında asıl veri trafiği için IPsec SA'larını pazarlıkla belirler.

**IKEv2**, IKEv1'in yıllar içinde ortaya çıkan tasarım eksikliklerini gidermek için geliştirildi ve bugün tercih edilen sürümdür. Farkları rastgele değil, hepsi somut bir soruna cevap:

- **Daha az mesaj, daha hızlı kurulum**: IKEv2 tüneli tipik olarak dört mesajlık tek bir alışverişte kurar. Bu sadece performans değil, aynı zamanda saldırı yüzeyinin küçülmesi demektir.
- **Yerleşik DoS koruması**: IKEv2, sunucuyu yormadan önce istemciden bir "cookie" ile kendini kanıtlamasını isteyebilir. Böylece saldırganın sahte kaynak IP'lerle sunucuyu Diffie-Hellman hesaplamalarına boğması (bir tür kaynak tüketme saldırısı) zorlaşır.
- **MOBIKE desteği**: İstemcinin IP adresi değişse bile (Wi-Fi'den mobil veriye geçiş gibi) tünel kopmaz. Mobil kullanıcılar için kritik bir özelliktir.
- **Güvenilir mesaj yapısı**: IKEv2 request/response mimarisi sayesinde kaybolan mesajları düzgün yönetir; IKEv1'in yer yer belirsiz durum makinesi (state machine) davranışını ortadan kaldırır.

Pratik bir kural olarak: yeni bir kurulum yapıyorsanız ve karşı taraf destekliyorsa, IKEv1'i tercih etmek için neredeyse hiçbir teknik gerekçe kalmamıştır.

### Perfect Forward Secrecy (PFS)

IKE anlatılırken atlanmaması gereken kavram **PFS**'tir. PFS, her yeni oturum anahtarının bağımsız bir Diffie-Hellman değişimiyle üretilmesi demektir. Neden önemli? Diyelim ki bir saldırgan bugün tüm şifreli trafiğinizi kaydediyor ve yıllar sonra sunucunuzun uzun ömürlü özel anahtarını ele geçiriyor. PFS yoksa, o anahtarla geçmişteki tüm trafiği geriye dönük çözebilir. PFS varsa, her oturumun anahtarı ayrı ve geçici (ephemeral) DH ile üretildiği için, uzun ömürlü anahtarın ele geçmesi geçmiş oturumları açığa çıkarmaz. Bu, "şimdi topla, sonra çöz" (harvest now, decrypt later) saldırı modeline karşı temel savunmadır ve post-quantum tehdit tartışmalarında giderek daha kritik hale gelmektedir.

## Somut Örnek: Bir Site-to-Site Tünelin Kurulması

İki ofis düşünelim: İstanbul ve Ankara. Her ofiste bir VPN gateway var. Süreç şöyle işler:

1. İstanbul gateway'i, önceden paylaşılmış bir anahtar (pre-shared key, PSK) ya da sertifika ile Ankara gateway'ine IKE üzerinden ulaşır.
2. IKE Phase 1 (ya da IKEv2'nin ilk alışverişi) çalışır: taraflar DH ile ortak sır üretir, birbirlerinin kimliğini PSK veya sertifikayla doğrular. Yönetim kanalı kurulmuştur.
3. Phase 2 çalışır: "İstanbul'un 10.1.0.0/16 ağından Ankara'nın 10.2.0.0/16 ağına giden trafik ESP ile şifrelenecek" gibi kurallar (traffic selectors) belirlenir ve veri SA'ları üretilir.
4. Artık İstanbul'daki bir bilgisayar Ankara'daki bir sunucuya paket gönderdiğinde, gateway o paketi ESP ile şifreleyip tünel modunda sarar, internet üzerinden Ankara gateway'ine ulaştırır, orada açılır ve iç ağa iletilir.

Bu akıştaki en kırılgan nokta genellikle üçüncü adımdaki traffic selector uyumsuzluklarıdır: iki taraf hangi trafiğin tünele gireceği konusunda birebir mutabık kalmazsa, Phase 1 kurulsa bile Phase 2 sürekli düşer ve "tünel bir kuruluyor bir kopuyor" tablosu ortaya çıkar.

## İstismar Mantığı ve Savunma

Bir güvenlik uzmanı için IPsec'i anlamak, sadece nasıl çalıştığını değil, nasıl kırıldığını da bilmek demektir. Aşağıda hem saldırı mantığını hem de savunmayı birlikte veriyorum, çünkü biri olmadan diğeri havada kalır.

### 1. Aggressive Mode ve PSK Kırma

**İstismar mantığı**: IKEv1 Aggressive Mode'un ölümcül kusuru, kimlik doğrulama tamamlanmadan önce PSK'ye dayalı bir hash değerini şifresiz biçimde hattan geçirmesidir. Bir saldırgan bu hash'i yakalayabilirse, onu çevrimdışı (offline) sözlük ve brute-force saldırısına tabi tutabilir. Çevrimdışı olmasının önemi büyüktür: saldırgan artık sunucuyla etkileşime girmeden, kendi donanımının hızıyla milyonlarca parola denemesi yapabilir. Zayıf bir PSK seçilmişse, bu genellikle saatler ya da günler içinde kırılır. Ike-scan gibi araçlar bu tür bilgi toplamada klasikleşmiştir.

**Savunma**: Aggressive Mode'u mümkünse tamamen devre dışı bırakın. Zorunluysa PSK'yi çok uzun ve rastgele (en az 20+ karakter, yüksek entropi) yapın; ama asıl doğru çözüm PSK'yi bırakıp **sertifika tabanlı kimlik doğrulamaya** geçmektir. Sertifikalarda kırılacak bir "parola hash'i" yoktur; kimlik doğrulama asimetrik kriptografiye dayanır. En temiz çözüm ise IKEv2'ye geçmektir, çünkü IKEv2 kimlik bilgilerini bu şekilde açığa çıkarmaz.

### 2. Zayıf Diffie-Hellman Grupları ve Logjam Sınıfı Saldırılar

**İstismar mantığı**: Diffie-Hellman'ın güvenliği kullanılan grubun (asal sayının) büyüklüğüne bağlıdır. Yıllar önce yaygın olan 768-bit ve 1024-bit DH grupları, devlet düzeyinde kaynağa sahip aktörler için artık kırılabilir kabul edilmektedir. Buradaki içgörü şudur: birçok sunucu aynı, standartlaştırılmış DH asal sayılarını kullanır. Saldırgan tek bir asal sayı için muazzam bir önhesaplama (precomputation) yaparsa, o asalı kullanan tüm bağlantıları görece ucuza kırabilir. Bu, Logjam sınıfı saldırıların temel fikridir. Downgrade saldırısıyla birleştiğinde, saldırgan tarafları zayıf gruba düşmeye zorlayabilir.

**Savunma**: 1024-bit ve altı DH gruplarını tamamen yasaklayın. En az 2048-bit MODP grupları kullanın, mümkünse **eliptik eğri (ECDH)** gruplarını tercih edin çünkü aynı güvenlik seviyesini çok daha küçük anahtarlarla ve daha hızlı sağlarlar. Konfigürasyonda sadece güçlü grupları teklif edin ki downgrade zorlaması işlemesin.

### 3. NULL Encryption ve Yanlış Yapılandırma

**İstismar mantığı**: IPsec, ESP içinde teorik olarak "NULL encryption" (şifreleme yok, sadece bütünlük) yapılandırmasına izin verir. Bu, hata ayıklama için düşünülmüştür ama yanlışlıkla üretimde kalırsa, trafik "IPsec ile korunuyor" sanılırken aslında düz metin akar. Benzer şekilde, sadece AH kullanan ya da MD5/DES gibi kırık algoritmaları teklif eden eski konfigürasyonlar sessiz bir felakettir.

**Savunma**: Şifreleme paketlerinizi (cipher suites) açıkça denetleyin. AES-GCM gibi hem şifreleme hem bütünlüğü birlikte sağlayan AEAD modlarını tercih edin. DES, 3DES, MD5 ve SHA-1 gibi eskimiş algoritmaları konfigürasyondan tamamen çıkarın. Periyodik olarak gerçek trafiği yakalayıp şifreli olduğunu fiziksel olarak doğrulayın; "yapılandırdım, çalışıyordur" varsayımı burada en tehlikeli tuzaktır.

### 4. IKE'nin Kendisine Yönelik Saldırılar ve Bilgi Sızıntısı

**İstismar mantığı**: IKE, UDP 500 (ve NAT-Traversal için 4500) portlarında dinler. Bu, saldırganın keşif yapabileceği açık bir yüzeydir. Saldırgan, IKE'ye çeşitli teklifler göndererek cihazın markasını, sürümünü ve desteklediği algoritmaları parmak izi (fingerprinting) yoluyla çıkarabilir. Ayrıca sahte kaynak IP'lerle çok sayıda yarım IKE oturumu başlatarak, sunucuyu pahalı DH hesaplamalarına zorlayan bir kaynak tüketme (DoS) saldırısı deneyebilir. Geçmişte belirli VPN gateway ürünlerinde IKE/SSL-VPN bileşenlerinde bellek bozulması (memory corruption) sınıfı, kimlik doğrulama öncesi (pre-authentication) sömürülebilen kritik açıklar görülmüştür; bu tür açıklar VPN cihazını doğrudan ağa açılan bir kapıya çevirir.

**Savunma**: IKE'ye erişimi mümkün olduğunca kısıtlayın; site-to-site tünellerde peer IP'lerini beyaz listeye alın. IKEv2'nin cookie tabanlı DoS korumasını etkinleştirin. En önemlisi: VPN gateway'lerinizi güncel tutun. VPN cihazları saldırganların bir numaralı hedeflerindendir çünkü internete bakan, kimlik doğrulama öncesi kod çalıştıran, ve başarıyla sömürülürse doğrudan iç ağa erişim veren cihazlardır. Yama yönetimini burada "acil" kategorisinde ele almak gerekir; bir VPN gateway açığı yayınlandığında saldırganların onu kitlesel taramaya alması genellikle günler değil saatler meselesidir.

### 5. Kimlik Bilgisi Hırsızlığı ve MFA Eksikliği

**İstismar mantığı**: Modern saldırıların çoğu IPsec'in kriptografisini kırmaya çalışmaz; çok daha kolay bir yol vardır. Kullanıcının VPN parolasını phishing, keylogger ya da veri sızıntılarından ele geçiren saldırgan, meşru bir kullanıcı gibi tünele girer. Klasik VPN mimarisinin en büyük zaafı tam burada ortaya çıkar: **kullanıcı tünele girdikten sonra çoğu zaman iç ağa geniş, düz (flat) erişim kazanır**. Yani bir kimlik bilgisi, tüm ağın kapısını açar. Bu, fidye yazılımı (ransomware) operasyonlarının favori giriş vektörlerinden biridir.

**Savunma**: VPN erişimini kesinlikle **çok faktörlü kimlik doğrulama (MFA)** ile koruyun; mümkünse phishing'e dirençli faktörler (donanım güvenlik anahtarları) kullanın. Ama daha derin çözüm, mimarinin kendisini sorgulamaktır: neden bir kullanıcı VPN'e girdikten sonra tüm ağa erişebilsin? İşte bu soru, bizi doğrudan bir sonraki bölüme, ZTNA'ya götürür.

## Klasik VPN'in Yapısal Zaafı ve ZTNA'ya Geçiş

Buraya kadar anlattığımız zayıflıkların çoğu yamayla, güçlü kriptoyla, MFA ile ele alınabilir. Ancak klasik VPN modelinin bir zaafı vardır ki bu bir "hata" değil, tasarımın kendisinden kaynaklanır: **VPN, güven modelini "ağ konumuna" bağlar.** Klasik yaklaşımda, tünelin dışı düşman, içi ise güvenilir kabul edilir. Bir kez tünele girdiniz mi, artık "içeridesiniz" ve iç ağın büyük kısmına erişiminiz olur. Bu, kalesi ve hendeği olan ortaçağ savunmasına benzer: dış duvarı aşan düşman, artık kale içinde serbestçe dolaşır. Buna güvenlik dünyasında **lateral movement** (yanal hareket) denir ve modern ihlallerin yıkıcı hale gelmesinin baş sebebidir.

### Zero Trust ve ZTNA'nın Temel Fikri

**ZTNA** (Zero Trust Network Access), bu modeli kökünden çevirir. Temel ilke şu cümleyle özetlenir: **"Asla güvenme, her zaman doğrula" (never trust, always verify).** ZTNA'da ağ konumu artık güven kaynağı değildir. Bir kullanıcının iç ağda olması ona hiçbir ayrıcalık kazandırmaz. Her erişim isteği, sanki güvenilmez bir ağdan geliyormuş gibi ayrı ayrı değerlendirilir.

ZTNA ile klasik VPN arasındaki farkları kök nedenleriyle açalım:

- **Ağa erişim değil, uygulamaya erişim**: Klasik VPN sizi bir ağ segmentine bağlar. ZTNA sizi bir ağa değil, sadece yetkili olduğunuz **spesifik uygulamalara** bağlar. Muhasebe uygulamasına erişim yetkiniz varsa, sadece onu görürsünüz; ağın geri kalanı sizin için görünmez bile değil, hiç yoktur. Bu, lateral movement'ı temelden imkansızlaştırır çünkü hareket edecek bir "ağ" görmüyorsunuz.

- **Bağlantı öncesi kimlik ve cihaz doğrulaması**: ZTNA'da erişim verilmeden önce hem kullanıcının kimliği (MFA ile) hem de cihazın durumu (device posture: güncel mi, disk şifreli mi, EDR çalışıyor mu) denetlenir. Sağlıksız cihaz meşru kullanıcının elinde olsa bile erişemez.

- **"Kara delik" prensibi (dark cloud)**: Klasik VPN gateway'i internette görünür bir port açar ve bu port tarama ve sömürü hedefidir. Birçok ZTNA mimarisi, kaynakları internete hiç açmaz; bağlantılar içeriden dışarıya (outbound) kurulur ve bir aracı üzerinden yönlendirilir. Böylece taranacak, sömürülecek açık bir IKE portu ortada kalmaz. Saldırgan, göremediği bir şeye saldıramaz.

- **Sürekli ve bağlamsal değerlendirme**: Klasik VPN'de kimlik doğrulama bir kez, girişte yapılır; sonrası "güvenilir"dir. ZTNA'da erişim süreklidir ve bağlama (konum, saat, davranış anomalisi) göre dinamik olarak yeniden değerlendirilebilir. Tünel açıkken bile şüpheli davranış erişimi anında kesebilir.

### Geçiş Gerçekçi mi? Dürüst Bir Değerlendirme

Burada bir güvenlik uzmanı olarak dürüst olmak gerekir: ZTNA klasik VPN'i her senaryoda anında ortadan kaldırmaz. IPsec, özellikle **site-to-site** bağlantılar için (iki veri merkezini, iki ofisi kalıcı olarak birbirine bağlamak) hâlâ son derece uygundur ve ZTNA bu problemi çözmeyi hedeflemez bile. ZTNA'nın asıl güçlü olduğu alan **kullanıcı-uygulama erişimi**, yani klasik remote-access VPN'in yerini almaktır.

Ayrıca geçiş bir gecede olmaz. Çoğu kurum hibrit bir dönem yaşar: eski sistemler (legacy) hâlâ VPN gerektirirken, yeni ve kritik uygulamalar ZTNA arkasına alınır. ZTNA'nın kendisi de yeni bir güven noktası (aracı/broker) yaratır ve bu aracının güvenliği, yüksek erişilebilirliği ve doğru yapılandırılması kritik önem taşır; yanlış yapılandırılmış bir ZTNA, kötü yapılandırılmış bir VPN'den daha güvenli değildir. Zero Trust bir ürün değil, bir mimari felsefedir; tek bir kutu satın alarak "Zero Trust olduk" demek yaygın ve tehlikeli bir yanılgıdır.

## Yaygın Hatalar

- **PSK'ye güvenmek**: Zayıf ya da tüm tüneller arasında paylaşılan tek bir PSK, en sık görülen ve en ciddi hatalardan biridir. Bir PSK sızarsa etkilediği tüm tüneller riske girer.
- **MTU ve fragmentation'ı ihmal etmek**: Tünel modu her pakete ek başlık ekler. Orijinal paket zaten MTU sınırındaysa, tünellenmiş hali sınırı aşar ve parçalanma (fragmentation) ya da sessiz paket düşmesi yaşanır. Belirtisi klasiktir: "ping çalışıyor ama büyük dosya transferleri ya da HTTPS takılıyor." Çözüm genellikle MSS clamping'dir.
- **NAT-Traversal'ı unutmak**: ESP protokolü NAT ile doğal olarak geçinmez çünkü NAT, IPsec'in bütünlük kontrolü altındaki başlıkları değiştirir. NAT arkasındaki istemciler için NAT-T (UDP 4500 üzerinden kapsülleme) gereklidir; unutulursa tünel Phase 1'i geçer ama veri akmaz.
- **Yama gecikmesi**: VPN gateway'lerini "çalışıyorsa dokunma" mantığıyla aylarca yamasız bırakmak. Bu cihazlar internete bakan, kimlik doğrulama öncesi kod çalıştıran en riskli varlıklardır; yama önceliğinde en üstte olmalıdırlar.
- **Girişten sonra düz ağ erişimi**: MFA konur, kripto güçlendirilir ama kullanıcı içeri girdikten sonra tüm ağa erişebilir. Segmentasyon eksikliği, bir ihlali felakete çevirir.
- **Log ve izlemenin olmaması**: VPN oturumlarının, başarısız IKE denemelerinin ve olağandışı erişim desenlerinin izlenmemesi. Saldırgan çalınmış meşru bir kimlikle girdiğinde, tek yakalama şansınız davranışsal anomali izlemedir.

## En İyi Pratikler

1. **IKEv2'yi ve sertifika tabanlı kimlik doğrulamayı varsayılan yapın.** IKEv1 ve PSK'yi ancak zorunlu eski uyumluluk için, o zaman da azami sıkılaştırmayla kullanın.
2. **Yalnızca güçlü, modern kriptografi teklif edin.** AES-GCM (AEAD), en az 2048-bit MODP ya da eliptik eğri DH grupları, SHA-2 ailesi. Zayıf algoritmaları teklif listesinden tamamen çıkarın ki downgrade saldırıları başarısız olsun.
3. **PFS'i her zaman etkinleştirin.** "Harvest now, decrypt later" tehdidine karşı bugünkü en temel savunmadır.
4. **MFA'yı zorunlu kılın**, mümkünse phishing'e dirençli donanım anahtarlarıyla. Kimlik bilgisi hırsızlığı, kriptografiden çok daha yaygın bir giriş vektörüdür.
5. **En az ayrıcalık ve mikro-segmentasyon uygulayın.** Kullanıcı içeri girdiğinde tüm ağı değil, sadece işi için gereken kaynakları görmeli. Bu, lateral movement'a karşı en etkili yapısal önlemdir.
6. **VPN gateway yamalarını acil önceliklendirin.** Yeni kullanıcı-uygulama erişim ihtiyaçları için ZTNA modelini ciddi biçimde değerlendirin; site-to-site için IPsec'i sürdürün.
7. **Sürekli izleyin.** IKE hatalarını, olağandışı oturum sürelerini, coğrafi imkansızlıkları (impossible travel) ve davranış anomalilerini loglayıp alarmlayın.
8. **Varsayımları değil gerçeği doğrulayın.** Periyodik olarak trafiği yakalayıp gerçekten şifreli aktığını, doğru algoritmaların pazarlıkla seçildiğini ve NULL encryption gibi tuzaklara düşülmediğini fiziksel olarak teyit edin.

## Sonuç

IPsec, IP katmanında gizlilik, bütünlük ve kimlik doğrulama sağlayan olgun ve güçlü bir teknolojidir; site-to-site bağlantılar için hâlâ endüstri standardıdır. Ancak gücü, doğru yapılandırmaya sıkı sıkıya bağlıdır: zayıf DH grupları, Aggressive Mode, PSK ve yamasız gateway'ler onu bir savunma aracından bir saldırı yüzeyine dönüştürebilir. Daha da önemlisi, klasik VPN'in "ağ konumuna dayalı güven" modeli, modern tehdit ortamının gerçekleriyle artık uyumsuzdur; bir kimlik bilgisinin tüm ağı açması kabul edilemez bir risktir. ZTNA, güveni ağdan kimliğe, cihaza ve bağlama taşıyarak bu yapısal zaafı çözer. Doğru yol, IPsec'i olması gereken yerde (site-to-site) ustaca çalıştırmak, kullanıcı erişimini ise adım adım Zero Trust ilkelerine taşımaktır. Güvenlik bir ürün değil, sürekli doğrulanan bir disiplindir.
