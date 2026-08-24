# Kablosuz Ağ Güvenliği: WPA2/WPA3

Kablosuz ağlar, kablolu ağlardan temel bir farkla ayrılır: iletişim ortamı paylaşılan ve fiziksel olarak sınırlanamayan havadır. Bir Ethernet kablosuna erişmek için binaya girmeniz gerekir; ama bir Wi-Fi sinyali duvarların dışına, sokağa, hatta komşu binaya taşar. Bu nedenle kablosuz güvenlik, "kimin ağa bağlanabileceği" sorusundan önce "kimin trafiği dinleyebileceği" sorusuyla ilgilenmek zorundadır. Bu makale WPA2 ve WPA3 protokollerinin nasıl çalıştığını, nerede kırıldığını, saldırının ve savunmanın mantığını derinlemesine ele alıyor.

## Temel Kavramlar ve Terminoloji

Başlamadan önce ortak bir sözlük kuralım. Bir kablosuz ağın kimliğine **SSID** (ağ adı) denir. Erişim noktasına **AP** (Access Point), bağlanan cihaza **client** ya da **station** (STA) denir. Ağa katılmak isteyen istemci ile AP arasında, şifreleme anahtarlarının türetildiği bir el sıkışma sürecine **handshake** denir.

WPA2 ve WPA3'ün ev/küçük ofis kullanımındaki hali **PSK** (Pre-Shared Key) moduna, yani herkesin aynı parolayı bildiği "kişisel" moda dayanır. Kurumsal ortamlarda ise **802.1X / EAP** ile RADIUS sunucusu üzerinden kimlik doğrulama yapılan "enterprise" modu vardır. Bu makale ağırlıklı olarak PSK modundaki saldırı yüzeyine odaklanıyor, çünkü pratikte en yaygın kırılan hedef budur.

Kritik bir noktayı baştan koymak gerekir: WPA2-PSK'nın parolası **doğrudan** anahtar değildir. Parola, SSID ile birlikte **PBKDF2** adlı bir yavaş türetme fonksiyonundan geçirilerek **PMK** (Pairwise Master Key) üretilir. PMK'dan da her oturum için taze **PTK** (Pairwise Transient Key) türetilir. Bu katmanlı yapı, hem saldırının hem de savunmanın mantığını anlamanın anahtarıdır.

## WPA2 4-Way Handshake: Kök Mantık

WPA2, istemci ile AP arasında **4-way handshake** denen dört mesajlık bir protokol çalıştırır. Amaç iki taraftı: her iki tarafın da aynı PMK'yı bildiğini karşılıklı kanıtlamak, ve bu oturuma özgü şifreleme anahtarını (PTK) parolayı ağ üzerinden hiç göndermeden türetmek.

Süreç kabaca şöyle işler. AP, istemciye rastgele bir sayı gönderir; buna **ANonce** denir. İstemci de kendi rastgele sayısını (**SNonce**) üretir. Artık her iki taraf da şu bileşenlere sahiptir: PMK (ortak parola), her iki tarafın MAC adresi, ANonce ve SNonce. Bu beş girdi bir **PRF** (pseudo-random function) üzerinden birleştirilerek PTK türetilir. İstemci, ürettiği PTK'nın bir parçasıyla mesajına bir **MIC** (Message Integrity Code) ekleyerek geri gönderir. AP aynı hesabı kendi tarafında yapar; eğer MIC tutuyorsa, karşı tarafın gerçekten doğru parolayı bildiği kanıtlanmış olur.

Neden bu tasarım? Çünkü parola hiçbir zaman havada dolaşmaz. Dolaşan şey yalnızca nonce'lar (açıkça görülebilir) ve bir MIC değeridir. Teoride bu, pasif bir dinleyicinin parolayı öğrenmesini imkânsız kılar. Ama pratikte burada gizli bir zafiyet vardır: dinleyici, handshake sırasında geçen tüm açık bileşenleri (MAC'ler, nonce'lar, MIC) yakalarsa, elinde PTK'yı doğrulamak için gereken **her şey** vardır — PMK hariç. İşte offline kırmanın kapısı buradan açılır.

## Handshake Yakalama: Neden Mümkün ve Nasıl Yapılır

Saldırının ilk adımı handshake'i ele geçirmektir. Saldırgan, ağın çalıştığı kanalı dinleyen **monitor mode**'da bir kablosuz arayüz kullanır. Monitor mode, kartın kendisine yönelik olmayan tüm çerçeveleri de yakalamasını sağlar — tıpkı bir Ethernet ağında promiscuous mode gibi, ama havadaki tüm 802.11 çerçeveleri için.

Sorun şu: handshake yalnızca bir istemci **yeni** bağlandığında gerçekleşir. Saldırgan sabırla bekleyebilir, ya da süreci hızlandırabilir. Hızlandırma yöntemi **deauthentication** saldırısıdır. WPA2'de yönetim çerçeveleri (management frames), özellikle deauth çerçeveleri, şifrelenmez ve doğrulanmaz. Saldırgan, AP'nin MAC adresini taklit ederek istemciye "bağlantın kesildi" anlamına gelen sahte bir deauth çerçevesi gönderir. İstemci bunu gerçek sanır, bağlantısını koparır ve otomatik olarak yeniden bağlanmaya çalışır — bu yeniden bağlanma sırasında handshake tekrar üretilir ve saldırgan onu yakalar.

Kök neden burada nettir: WPA2'nin yönetim çerçevelerinin kimliği doğrulanmadığı için, herkes AP adına "seni attım" diyebilir. Aircrack-ng ailesi (airodump-ng ile dinleme, aireplay-ng ile deauth) ya da hcxdumptool gibi araçlar bu işlemi rutin hale getirir. Yakalanan handshake genellikle `.pcap` ya da hashcat için `.hc22000` formatına dönüştürülür.

Önemli bir doğruluk notu: kırma için dört mesajın hepsi şart değildir. Genelde ilk iki mesaj (ANonce ve MIC içeren yanıt) yeterlidir, çünkü PTK'yı doğrulamak için gereken tüm bileşenler oradadır.

## Offline Kırma: Asıl Savaş Diskte Verilir

Handshake yakalandıktan sonra saldırı **çevrimdışı** (offline) hale gelir. Bu, savunma açısından son derece kritik bir dönüm noktasıdır: saldırgan artık ağa hiç dokunmaz, AP'nin herhangi bir hız sınırlaması, hesap kilitleme ya da log tutma mekanizması devreye giremez. Saldırgan, kendi donanımında sınırsız sayıda parola denemesi yapabilir.

Kırma şöyle işler: saldırgan bir parola adayı seçer, onu yakaladığı SSID ile birlikte PBKDF2'den geçirip aday bir PMK üretir, oradan aday bir PTK türetir, ve bu PTK ile handshake'te yakaladığı mesajın MIC'ini yeniden hesaplar. Hesapladığı MIC, yakaladığı MIC ile tutuyorsa parolayı bulmuş demektir. Tutmuyorsa bir sonraki parolaya geçer.

Buradaki tüm savunma **PBKDF2'nin yavaşlığına** ve **parolanın entropisine** dayanır. WPA2, PBKDF2'yi çok sayıda iterasyonla (spesifik iterasyon sayısını burada kesin vermeyeceğim, ama standart yüksek bir değerdir) çalıştırarak her tek deneme için saldırganı belirli bir hesap maliyetine mahkûm eder. Bu, saniyede yapılabilecek deneme sayısını sınırlar. Ancak modern GPU'lar ve hashcat gibi araçlar bu maliyeti bir GPU kümesinde saniyede yüzbinlerce-milyonlarca denemeye kadar çıkarabilir. Sonuç şudur: **zayıf parola matematiksel olarak zaten kaybetmiştir.**

Örnekleyelim. "12345678", "password", "sifre123" ya da telefon numarası gibi bir parola, sözlük saldırısında (dictionary attack) saniyeler içinde düşer. Salt olarak yalnızca SSID kullanıldığı için, saldırganlar yaygın SSID'ler için önceden hesaplanmış tablolar (rainbow-table benzeri, bu bağlamda tarihsel olarak "WPA PMK tabloları") bile hazırlayabilmiştir. Buna karşılık, 20 karakterli, tamamen rastgele bir parola, mevcut hesap gücüyle pratik olarak kırılamaz — çünkü arama uzayı astronomik büyüklüğe ulaşır ve PBKDF2 maliyeti her denemeyi pahalı tutar.

### PMKID Saldırısı: Handshake'e Bile Gerek Yok

WPA2'de daha da rahatsız edici bir varyant vardır. Bazı AP'ler, ilk çerçevede **PMKID** denen bir değer sunar. PMKID, PMK'dan ve sabit bileşenlerden türetilen bir karma değeridir ve — kritik olan nokta — bir istemcinin bağlanmasını beklemeye gerek kalmadan doğrudan AP'den istenebilir. Yani saldırgan, hiç kullanıcı bağlı olmasa bile tek bir çerçeveyle kırılabilir bir hash elde edebilir. Bu, deauth ihtiyacını ve "istemci bekleme" adımını tamamen ortadan kaldırır. Savunması, AP üzerinde PMKID sunumunu (roaming amaçlı bir özelliktir) kapatmak ve yine güçlü parola kullanmaktır.

## WPA3 ve SAE: Offline Kırmayı Kökten Bozan Tasarım

WPA2'nin yapısal zafiyeti şuydu: handshake'i yakalayan biri, offline'da sınırsız parola denemesi yapabiliyordu. WPA3 bu sorunu doğrudan hedef alarak tasarlandı. Kişisel modda WPA3, 4-way handshake yerine **SAE** (Simultaneous Authentication of Equals) adlı bir kimlik doğrulama kullanır. SAE, halk arasında bilinen adıyla **Dragonfly** anahtar değişimidir ve bir **PAKE** (Password Authenticated Key Exchange) protokolüdür.

SAE'nin dâhiyane yanı şudur: iki taraf, parolayı bir eliptik eğri (ya da sonlu alan) üzerinde bir noktaya dönüştürür ve bir **commit-confirm** akışıyla, parolayı bilip bilmediklerini karşılıklı kanıtlarken **parola hakkında offline'da işe yarar hiçbir bilgi sızdırmazlar.** Matematiksel olarak, alışverişi dinleyen biri, elindeki verilerle offline'da bir parola adayını doğrulayamaz. Yanlış bir parolayı elemek için mutlaka **canlı olarak AP ile bir tur daha konuşması** gerekir. Bu tek başına oyunu değiştirir.

Sonuç şudur: WPA3-SAE'de offline sözlük saldırısı prensip olarak devre dışı bırakılır. Saldırgan artık her parola denemesi için gerçek AP'ye bağlanmak zorundadır, bu da online bir saldırıdır — yavaştır, tespit edilebilir, hız sınırlamasına ve kilitlemeye tabidir. WPA3 ayrıca handshake'ten sonra ele geçen anahtarların, geçmiş trafiği çözmesini engelleyen **forward secrecy** özelliği getirir; WPA2'de doğru parolayı sonradan bulan biri, önceden kaydettiği tüm trafiği çözebilirken, WPA3'te bu mümkün değildir.

WPA3, deauth sorununa karşı da bir zırh getirir: **PMF** (Protected Management Frames, 802.11w). PMF, yönetim çerçevelerinin (özellikle deauth/disassoc) kimliğini doğrular ve bütünlüğünü korur. Böylece saldırgan artık AP adına sahte deauth gönderip istemciyi düşüremez — çünkü sahte çerçeve doğrulamayı geçemez. PMF, WPA3'te zorunludur; WPA2'de ise opsiyoneldir ve çoğu ağda kapalıdır.

### WPA3'ün Kendi Zayıf Noktaları: Dürüst Bir Değerlendirme

WPA3 "kırılamaz" değildir; onu öyle sunmak yanıltıcı olur. Araştırmacılar (özellikle Dragonfly/SAE üzerine yapılan meşhur "Dragonblood" adı verilen çalışmalar dizisi) SAE'nin ilk uygulamalarında ciddi sorunlar buldu. Bunlar ağırlıklı olarak protokolün matematiğinden değil, **implementasyon** ve **geçiş modlarından** kaynaklanıyordu:

Birincisi, **yan kanal sızıntıları** (side-channel). SAE'de parolayı eğri üzerindeki bir noktaya çeviren "hash-to-curve" işleminin bazı erken uygulamaları, işlem süresine ya da önbellek erişim desenlerine bağlı olarak parola hakkında ölçülebilir ipuçları sızdırıyordu. Bir saldırgan bu zamanlama/cache farklarını istatistiksel olarak toplayıp offline elemeye yeniden kapı aralayabiliyordu. Bu, protokolün değil, sabit-zamanlı yazılmamış kodun hatasıydı ve yamalarla düzeltildi.

İkincisi, **downgrade (geriye düşürme) saldırıları**. Gerçek dünyada eski cihazlarla uyum için çoğu ağ **WPA3-Transition** modunda çalışır: aynı SSID hem WPA3-SAE hem de WPA2-PSK kabul eder. Saldırgan, evil twin ya da manipülasyonla istemciyi WPA2 tarafına konuşmaya zorlayabilirse, klasik handshake yakalama + offline kırma yolu yeniden açılır. WPA3'ün tüm garantileri, ancak ağ **saf WPA3 (transition kapalı)** çalıştığında geçerlidir.

Üçüncüsü, SAE'nin commit hesabının maliyetli olması nedeniyle görülen **DoS** riski: saldırgan sahte commit'lerle AP'yi pahalı hesaplamalara boğabilir. Standart, bunu hafifleten anti-clogging token mekanizmaları içerir.

Bu tabloyu dürüstçe koymak gerekir: WPA3, WPA2'ye göre büyük bir sıçramadır ve offline kırmayı ilkesel olarak kapatır; ama yanlış yapılandırılmış transition modu ve eski implementasyonlar onu WPA2 seviyesine geri düşürebilir.

## Evil Twin: Şifrelemeyi Kırmadan İnsanı Kandırmak

Şimdiye kadarki saldırılar kriptografiyle uğraşıyordu. **Evil twin** bambaşka bir felsefeye dayanır: parolayı kırmaya çalışma, kullanıcıyı sana parolayı **kendi elleriyle vermeye** ikna et. Bu, kablosuz güvenliğin en zayıf halkasının çoğu zaman insan olduğunu gösteren bir saldırıdır.

Mantık şudur. Saldırgan, hedef ağla **aynı SSID'ye** sahip sahte bir AP kurar. Cihazlar bir ağı adıyla hatırlar ve sinyali güçlü olana bağlanma eğilimindedir. Saldırgan sahte AP'yi hedefe yakın ve güçlü tutarsa — çoğu zaman gerçek AP'ye deauth saldırısı yaparak onu erişilemez kılarak — kurbanın cihazı sahte AP'ye bağlanır. Sahte AP genellikle **açık** (parolasız) kurulur ve kurban bağlandığında, her HTTP isteğini bir **captive portal**'a yönlendirir. Bu sahte portal, gerçek ağın markasını taklit ederek "Wi-Fi parolanızı yeniden girin / router güncellemesi için doğrulama gerekiyor" gibi bir bahaneyle parolayı ister. Kurban parolayı yazdığı anda saldırgan onu ele geçirir.

Buradaki incelik şudur: saldırgan girilen parolanın doğruluğunu, önceden yakaladığı gerçek handshake'e karşı **anında offline doğrulayabilir.** Yani kurban yanlış parola yazarsa portal "yanlış, tekrar deneyin" der; doğru yazınca kabul eder. Bu, saldırıya inandırıcılık katar. Bu yaklaşım "wifiphisher" gibi araçlarla otomatikleştirilmiştir.

Evil twin'in daha tehlikeli hedefi WPA2-Enterprise ağlardır. Burada saldırgan sahte bir RADIUS sunucusu kurar; eğer istemci sunucu sertifikasını doğrulamıyorsa (yaygın bir yanlış yapılandırma), istemcinin gönderdiği MSCHAPv2 gibi kimlik doğrulama yanıtlarını yakalayıp offline kırarak **kullanıcı adı ve parolayı** ele geçirebilir. Bu genellikle Wi-Fi parolasından daha değerlidir, çünkü çoğu kurumda o kimlik bilgisi e-postaya, VPN'e, her şeye açılır.

Kritik nokta: evil twin, WPA3'ün kriptografik gücünü **atlar**. SAE'yi kırmaya çalışmaz; kullanıcıyı bambaşka, sahte bir ağa çeker. Bu yüzden WPA3'e geçmek evil twin'i tek başına çözmez — çözüm insan ve doğrulama katmanındadır.

## Savunma: Katman Katman

Şimdi tabloyu tersine çevirip savunmayı sistematik kuralım. Saldırıların kök nedenlerini gördüğümüz için savunmalar artık rastgele bir kontrol listesi değil, her biri belirli bir zafiyeti kapatan mantıklı adımlar.

**Parola, her şeyin temelidir.** Offline kırmanın tek gerçek panzehiri yüksek entropili paroladır. Uzunluk, karmaşıklıktan daha değerlidir; 20+ karakterli, rastgele ya da birbiriyle ilgisiz kelimelerden oluşan bir parola arama uzayını PBKDF2 maliyetiyle birleştiğinde pratik olarak kırılamaz kılar. Sözlükte geçen kelimeler, tarihler, isimler ve klavye desenleri felakettir.

**Mümkünse WPA3'e, mümkün değilse WPA2-AES'e geçin.** WPA3 offline kırmayı ilkesel olarak kapatır ve forward secrecy getirir. Ama transition modunun WPA2'ye geri düşme kapısı açtığını unutmayın: güvenlik kritikse, eski cihazları emekliye ayırıp **saf WPA3** çalıştırmak en güçlü duruştur.

**PMF (802.11w) etkinleştirin.** Bu, deauth temelli saldırıları — hem handshake yakalamayı hızlandıran hem de evil twin'i besleyen deauth'u — engeller. WPA3'te zaten zorunlu; WPA2'de ise elle açılması gereken ama sıklıkla ihmal edilen bir ayardır.

**PMKID sunumunu ve gereksiz roaming özelliklerini kapatın.** Bu, istemci beklemeden kırılabilir hash sızmasını önler.

**Enterprise ağlarda sunucu sertifikası doğrulamasını zorunlu kılın.** İstemci cihazlar yalnızca bilinen bir CA tarafından imzalanmış, doğru isimli RADIUS sunucusuna bağlanacak şekilde yapılandırılmalıdır. Bu tek ayar, sahte RADIUS temelli evil twin saldırılarını etkisiz kılar. Kullanıcıya "sertifikaya güven?" sorusunu sormamak, cevabını cihaz politikasıyla önceden vermek gerekir.

**Kullanıcı farkındalığı, evil twin'e karşı asıl savunmadır.** Hiçbir meşru sistem, tarayıcıda açılan bir sayfada Wi-Fi parolanızı yeniden istemez. Kullanıcılar, açık ağlara otomatik bağlanmayı kapatmalı, hassas işlemler için doğrulanmış VPN kullanmalı, ve captive portal'lara kimlik bilgisi girmeden önce şüpheyle yaklaşmalıdır. HTTPS ve HSTS, sahte portalların TLS uyarısı vermeden araya girmesini zorlaştırır.

**Ağı segmente edin ve misafir ağını ayırın.** Bir istemci ele geçirilse bile yanal hareketi (lateral movement) sınırlamak, olayın etkisini küçültür. Kurumsal WPA-Enterprise, PSK'nın "herkes aynı parolayı bilir" sorununu ortadan kaldırdığı için, ölçekli ortamlarda tercih edilmelidir.

## Yaygın Hatalar

Sahada tekrar tekrar görülen ve neredeyse her ciddi ihlalin kökünde yatan hataları toplayalım.

**Zayıf ya da tahmin edilebilir parola.** En yaygın ve en ölümcül hata. WPA2'nin tüm güvenliği buna dayanır; zayıf parola tüm protokolü çürütür. Kurumsal ortamda tek bir paylaşılan PSK'nın onlarca cihaza dağıtılması ve hiç değiştirilmemesi de aynı kategoridedir.

**WPA3 transition moduna körü körüne güvenmek.** "WPA3 açık" demek güvende olduğunuz anlamına gelmez; transition açıksa saldırgan WPA2 tarafından girip klasik saldırıları uygular. Birçok yönetici bunun farkında değildir.

**PMF'i kapalı bırakmak.** Deauth saldırısı, hâlâ en kolay ve en etkili ilk adımdır; PMF olmadan handshake yakalama ve evil twin çok kolaylaşır.

**Enterprise'da sertifika doğrulamasını atlamak.** "Bağlanamıyoruz, doğrulamayı kapatın" diye verilen destek talimatları, kurumsal kimlik bilgilerini sahte RADIUS'a açık hedef yapar. Bu, tek bir tık'la tüm dizini riske atan bir hatadır.

**WPS'i açık bırakmak.** WPS'in PIN temelli tarihsel zafiyetleri, güçlü bir WPA2 parolasını tümüyle baypas edebilir. Genellikle kapatılması gereken bir kolaylık özelliğidir.

**"Gizli SSID" ya da MAC filtrelemeyi güvenlik sanmak.** Gizli SSID sinyalden çıkarılabilir; MAC adresleri havada açıkça görünür ve taklit edilebilir. Bunlar güvenlik değil, en fazla hafif bir gizlilik teatridir ve kimseyi ciddi bir saldırgana karşı korumaz.

## En İyi Pratikler

Bir cümlelik bir zihinsel model bırakmak gerekirse: **WPA2'nin güvenliği parolanızın entropisi kadardır, WPA3'ün güvenliği ise yapılandırmanızın saflığı kadardır.**

Somut olarak: WPA3 destekleniyorsa transition modunu kapatarak saf çalıştırın; desteklenmiyorsa WPA2-AES (asla TKIP değil) ile 20+ karakterli rastgele parola kullanın. PMF'i her yerde açın. Ev ortamında güçlü tek bir parola yeterken, kurumsal ölçekte 802.1X/EAP-TLS gibi sertifika temelli, kişi başına ayrı kimlikli enterprise moda geçin — böylece bir kişinin ayrılması ya da bir kimliğin sızması tüm ağı çökertmez. Sunucu sertifikası doğrulamasını cihaz politikasıyla zorunlu kılın. Misafir trafiğini üretim ağından izole edin, WPS'i kapatın, yönetim arayüzlerini güncel tutun.

Ve son olarak, teknik hiçbir kontrolün kapatamadığı katmanı unutmayın: insan. Evil twin ve captive portal phishing'i, en güçlü şifrelemeyi bile atlayarak doğrudan kullanıcıyı hedef alır. Düzenli farkındalık eğitimi, "parolanı asla bir web sayfasına tekrar girme" refleksi ve doğrulanmış VPN kullanımı, kriptografinin bittiği yerde savunmanın devam etmesini sağlar. Kablosuz güvenlik, sonuçta bir protokol meselesi olduğu kadar bir disiplin ve yapılandırma meselesidir.
