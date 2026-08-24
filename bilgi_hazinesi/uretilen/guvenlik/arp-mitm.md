# ARP Spoofing ve Man-in-the-Middle (MITM) Saldırıları

## Tanım

**ARP spoofing** (ARP zehirlenmesi, İngilizce *ARP poisoning*), yerel ağda (LAN) çalışan bir saldırganın, Address Resolution Protocol'ün güvenden yoksun yapısını kötüye kullanarak kurbanların trafiğini kendi makinesi üzerinden geçirmesine olanak tanıyan bir Layer 2 (veri bağlantı katmanı) saldırısıdır. Saldırgan, kurbana "ben ağ geçidiyim" diye yalan söyler; ağ geçidine ise "ben kurbanım" der. Bu iki yalan birleştiğinde saldırgan, kurban ile ağ geçidi arasındaki tüm trafiğin ortasına oturur. İşte bu konum, klasik bir **Man-in-the-Middle (MITM)** durumudur: iki tarafın hâlâ birbiriyle doğrudan konuştuğunu sandığı, ama aslında araya birinin girdiği bir iletişim.

ARP spoofing tek başına bir amaç değil, bir *ön koşuldur*. Amaç genellikle trafiği yakalamak (sniffing), oturum çerezlerini çalmak, kimlik bilgilerini toplamak, trafiği değiştirmek (injection), DNS yanıtlarını sahtelemek veya TLS'i düşürmeye (downgrade) çalışmaktır. Bu yüzden ARP spoofing'i anlamak için önce ARP'ın *neden* bu kadar kolay kandırıldığını anlamak gerekir.

## Kök Neden: ARP Neden Bu Kadar Güvensiz?

ARP, IPv4 ağlarında bir mantıksal adres olan **IP adresini**, o ağda fiziksel olarak konuşabileceğimiz **MAC adresine** çeviren protokoldür. Bir cihaz aynı yerel ağdaki başka bir cihaza paket göndermek istediğinde, hedefin IP'sini bilir ama Ethernet çerçevesini (frame) gönderebilmek için hedefin MAC adresine ihtiyaç duyar. İşte ARP tam burada devreye girer.

Süreç şöyle işler: Cihaz bir **ARP Request** yayınlar (broadcast) — "192.168.1.1 IP'sine sahip olan kim? MAC adresini bana söylesin." Bu istek ağdaki herkese gider. İlgili cihaz bir **ARP Reply** ile cevap verir — "192.168.1.1 benim, MAC adresim şu." Cihaz bu eşleşmeyi kendi **ARP cache**'inde (ARP tablosunda) saklar ve bir süre kullanır.

Sorunun kökü şudur: **ARP'ın hiçbir doğrulama (authentication) mekanizması yoktur.** Protokol 1982'de (RFC 826) tasarlandığında, yerel ağdaki tüm cihazların güvenilir olduğu varsayılmıştı. Bu yüzden ARP şu üç ölümcül özelliği taşır:

1. **Durum takibi yoktur (stateless):** Bir cihaz, hiç ARP Request göndermemiş olsa bile gelen bir ARP Reply'ı kabul eder ve tablosunu günceller. Buna **gratuitous ARP** (istem dışı ARP) denir. Saldırgan istediği zaman, kimse sormamışken sahte cevaplar gönderebilir.

2. **Kimlik doğrulama yoktur:** "Bu ARP Reply'ı gerçekten 192.168.1.1 mi gönderdi?" sorusunun cevabı yoktur. MAC adresini iddia eden herkese inanılır. Bir imza, bir sertifika, bir sıra numarası — hiçbiri yoktur.

3. **Son gelen kazanır (last-write-wins):** ARP cache'e gelen yeni bir eşleşme, eskisinin üzerine yazar. Saldırgan sürekli sahte cevaplar göndererek (örneğin saniyede birkaç kez) tabloyu kendi lehine "taze" tutabilir; meşru cevaplar gelse bile hemen ardından saldırganın cevabı üzerine yazar.

Bu üç özelliğin birleşimi, ARP spoofing'i son derece güvenilir ve tespit edilmesi zor bir saldırı hâline getirir. Protokolün kendisi kusurlu değildir — yaptığı işi tam olarak yapar — ama tasarım varsayımı (güvenilir LAN) modern, paylaşımlı ve düşman içerebilen ağlarda geçerli değildir.

## Somut Örnek: Saldırının Adım Adım Anatomisi

Diyelim ki bir kafenin Wi-Fi ağındayız:

- Kurban (laptop): `192.168.1.50`, MAC `AA:AA:AA:AA:AA:AA`
- Ağ geçidi (router): `192.168.1.1`, MAC `BB:BB:BB:BB:BB:BB`
- Saldırgan: `192.168.1.99`, MAC `CC:CC:CC:CC:CC:CC`

Normal durumda kurbanın ARP tablosunda `192.168.1.1 → BB:BB:BB:BB:BB:BB` yazar. Saldırgan bunu bozmak ister.

**Adım 1 — İki yönlü zehirleme:** Saldırgan kurbana sürekli gratuitous ARP Reply gönderir: "192.168.1.1 → CC:CC:CC:CC:CC:CC". Aynı anda ağ geçidine de gönderir: "192.168.1.50 → CC:CC:CC:CC:CC:CC". Artık kurbanın tablosunda ağ geçidi = saldırganın MAC'i; ağ geçidinin tablosunda kurban = saldırganın MAC'i olur.

**Adım 2 — Trafiğin yönlenmesi:** Kurban internete bir paket göndermek istediğinde, Ethernet çerçevesini `CC:CC:CC:CC:CC:CC`'ye (saldırgana) gönderir çünkü tablosuna göre ağ geçidi orasıdır. Saldırgan paketi alır.

**Adım 3 — Yönlendirme (IP forwarding):** Burada kritik bir nokta var. Eğer saldırgan aldığı paketi ağ geçidine iletmezse, kurbanın interneti kesilir ve saldırı hemen fark edilir. Bu yüzden saldırgan kendi işletim sisteminde **IP forwarding**'i açar (Linux'ta `net.ipv4.ip_forward` değerini 1 yapar). Böylece saldırgan trafiği okur/kaydeder ve sonra gerçek hedefe iletir. Kurban açısından her şey normal görünür — internet çalışıyordur, sadece trafik saldırganın gözünden geçmektedir.

Bu iş için yaygın araçlar `arpspoof` (dsniff paketi), `ettercap`, `bettercap` ve Python tarafında `scapy` ile yazılmış özel scriptlerdir. Bettercap gibi araçlar bu adımları (zehirleme + forwarding + sniffing) otomatikleştirir.

## İstismar Mantığı: ARP Zehirlenmesi Neyi Mümkün Kılar?

Trafik saldırganın üzerinden geçmeye başladığında, MITM konumu bir dizi ileri saldırının kapısını açar. Bunları anlamak, savunmanın neden bu şekilde tasarlandığını da açıklar.

**Pasif dinleme (sniffing):** En temel istismar, şifrelenmemiş trafiği okumaktır. HTTP, FTP, Telnet, eski POP3/IMAP gibi düz metin (plaintext) protokoller açık kimlik bilgileri, çerezler ve içerik sızdırır. Bugün web trafiğinin çoğu HTTPS olduğu için bu tek başına eskisi kadar etkili değildir, ama iç ağlardaki yönetim panelleri, IoT cihazları ve eski servisler hâlâ düz metin konuşabilir.

**DNS spoofing:** Saldırgan araya girdiği için kurbanın DNS sorgularını da görür. Sahte bir DNS yanıtı enjekte ederek `banka.com`'u kendi sunucusuna yönlendirebilir. Bu, phishing sayfaları için güçlü bir vektördür.

**SSL/TLS stripping:** Bu, MITM'in en önemli tekniklerinden biridir. Kullanıcı genelde `http://banka.com` yazar veya bir HTTP bağlantısına tıklar; sunucu normalde onu HTTPS'e yönlendirir. Saldırgan araya girip bu yönlendirmeyi engeller: kurban ile kendisi arasında bağlantıyı HTTP olarak tutar, kendisi ile gerçek sunucu arasında HTTPS kurar. Kurban tarayıcısında kilit simgesi görmez ama çoğu kullanıcı bunu fark etmez. `sslstrip` bu tekniği popülerleştiren araçtır. Bu saldırının panzehiri **HSTS**'tir (aşağıda savunma bölümünde).

**Trafik enjeksiyonu ve değiştirme:** Saldırgan sadece okuyup iletmek zorunda değildir; içeriği değiştirebilir. HTTP yanıtlarına JavaScript enjekte etmek, indirilen dosyaları zararlıyla değiştirmek, form gönderimlerini manipüle etmek mümkündür.

**Oturum ele geçirme (session hijacking):** Şifrelenmemiş bir oturumda çerez yakalandığında, saldırgan kullanıcının oturumunu doğrudan devralabilir.

Bu istismar zincirinin tamamı tek bir zaafa dayanır: Layer 2'de kimliğin doğrulanmaması. Savunma da tam olarak bu iki eksende kurulur — ya Layer 2'de doğrulama getir, ya da Layer 2'ye hiç güvenme ve üst katmanda (TLS) kendini koru.

## Savunma: Katmanlı Bir Yaklaşım

ARP spoofing'e karşı savunmayı iki felsefeye ayırmak doğru olur. Birincisi, "ağı temizle" felsefesi — Layer 2'de zehirlemeyi baştan engelle. İkincisi, "ağa güvenme" felsefesi — trafiği zaten düşman bir ağ üzerinden geçiyormuş gibi şifrele. Olgun bir güvenlik duruşu ikisini birden uygular.

### Dynamic ARP Inspection (DAI)

**DAI**, yönetilebilir (managed) switch'lerde bulunan ve ARP spoofing'e karşı en etkili ağ tarafı savunmadır. Mantığı şudur: Switch, ağdan geçen her ARP paketini denetler ve "bu IP-MAC eşleşmesi meşru mu?" diye sorar. Meşruysa geçirir, değilse düşürür (drop).

DAI'nin çalışabilmesi için bir **güvenilir eşleşme kaynağına** ihtiyacı vardır. Bu kaynak genellikle **DHCP snooping** tablosudur. DHCP snooping, switch'in DHCP trafiğini izleyerek "hangi port'a hangi MAC atandı, hangi IP verildi" bilgisini bir bağlanma tablosunda (binding table) tutmasıdır. DAI bu tabloya bakar: eğer bir port'tan gelen ARP paketi, o port'a ait olmayan bir IP-MAC eşleşmesini iddia ediyorsa, saldırı olarak değerlendirilir ve paket engellenir.

Burada anahtar bir kavram var: **trusted (güvenilir) ve untrusted (güvenilmez) port ayrımı.** Uplink port'ları (switch'ler arası, router'a giden) genelde trusted işaretlenir; son kullanıcı port'ları untrusted bırakılır ve tüm ARP denetimi bu port'larda uygulanır. Statik IP kullanan sunucular için ise DHCP snooping tablosu bilgi vermez; bu durumda manuel olarak tanımlanan **ARP ACL**'leri (erişim listeleri) kullanılır.

DAI'nin güçlü yanı, saldırıyı *ağın kalbinde*, switch seviyesinde durdurmasıdır; kurban cihazın hiçbir şey yapmasına gerek kalmaz. Zayıf yanı, doğru yapılandırma gerektirmesidir: DHCP snooping'in düzgün kurulmaması, trusted port'ların yanlış işaretlenmesi savunmayı işlevsiz bırakır. Ayrıca sadece yönetilebilir switch'lerde bulunur; ucuz "dumb" switch'ler ve çoğu ev tipi cihaz bunu sunmaz.

DAI'yi tamamlayan diğer switch özellikleri **port security** (bir port'a bağlanabilecek MAC sayısını sınırlama, MAC flooding'e karşı) ve **802.1X** (port'a erişmeden önce kimlik doğrulama) mekanizmalarıdır. Bunlar birlikte, yetkisiz bir cihazın ağa girip zehirleme yapmasını çok zorlaştırır.

### TLS ve Uçtan Uca Şifreleme

DAI ağı temizler, ama her ağ DAI destekli değildir — halka açık Wi-Fi, misafir ağları, ele geçirilmiş iç ağlar. Bu yüzden ikinci ve daha temel savunma katmanı, **trafiğin kendisini şifrelemektir**. Felsefe basittir: *Ağa hiç güvenme.* Saldırgan araya girse bile, okuyabildiği tek şey şifreli baytlarsa ve içeriği değiştiremiyorsa, MITM konumunun değeri büyük ölçüde düşer.

**TLS** (ve onu kullanan HTTPS) tam olarak bu işi yapar. TLS iki koruma sağlar: gizlilik (şifreleme) ve **bütünlük + kimlik doğrulama** (sunucunun sertifikası aracılığıyla). Kritik nokta ikincisidir. TLS handshake sırasında sunucu, güvenilir bir Certificate Authority (CA) tarafından imzalanmış bir sertifika sunar. İstemci bu sertifikayı doğrular. Saldırgan araya girip trafiği okumaya çalışırsa, kurbana ya geçersiz (CA tarafından imzalanmamış) bir sertifika sunmak zorunda kalır — ki tarayıcı bunu büyük bir uyarıyla reddeder — ya da hiç şifre çözemeden baytları körü körüne iletir. Yani doğru yapılandırılmış TLS, MITM'i pasif bir taşıyıcıya indirger.

Ancak TLS'i etkili kılan detaylardır:

**HSTS (HTTP Strict Transport Security):** SSL stripping saldırısının panzehridir. Sunucu bir HTTP başlığıyla tarayıcıya "bu siteye bundan sonra *sadece* HTTPS ile bağlan, http'yi hiç deneme bile" der. Tarayıcı bu talimatı hafızasında tutar. Böylece saldırganın HTTP'ye düşürme numarası işe yaramaz. Daha da güçlüsü, **HSTS preload** listesidir: siteler tarayıcılara önceden gömülür, böylece kullanıcının siteyi *ilk* ziyaretinde bile HTTP hiç denenmez (aksi hâlde ilk ziyaret hâlâ savunmasız olurdu — buna "trust on first use" boşluğu denir).

**Sertifika doğrulamasının ciddiye alınması:** TLS'in tüm güvenliği, istemcinin geçersiz sertifikayı reddetmesine dayanır. Kullanıcıların sertifika uyarılarını "İleri" diyerek geçmesi, mobil uygulamaların sertifika doğrulamayı kapatması, geliştiricilerin `verify=False` benzeri ayarlar bırakması bu savunmayı çökertir. MITM saldırganları tam olarak bu insan/yapılandırma hatasını hedefler.

**Certificate pinning:** Yüksek güvenlik gerektiren uygulamalar (özellikle mobil bankacılık), sadece belirli bir sertifikaya veya public key'e güvenerek CA katmanındaki potansiyel zafiyetleri de aşar. Böylece ele geçirilmiş veya hileli bir CA tarafından üretilmiş sahte bir sertifika bile kabul edilmez.

TLS ve DAI birbirini tamamlar: DAI saldırının *gerçekleşmesini* zorlaştırır; TLS ise saldırı gerçekleşse bile *işe yaramaz kalmasını* sağlar. Derinlemesine savunma (defense in depth) tam da budur.

### Ek Ağ Savunmaları

Bunların dışında bazı tamamlayıcı önlemler vardır. **Statik ARP girdileri**, kritik cihazlar (örneğin sunucu ile ağ geçidi arası) için IP-MAC eşleşmesini elle sabitler; bu eşleşme artık ARP Reply ile değiştirilemez. Güçlüdür ama ölçeklenmez — her cihaz çifti için elle bakım gerektirir, bu yüzden sadece küçük ve kritik segmentlerde pratiktir. **Ağ segmentasyonu ve VLAN'lar**, broadcast alanını daraltarak bir saldırganın erişebileceği hedef sayısını azaltır; ARP bir VLAN sınırını aşamaz. **arpwatch** gibi izleme araçları, bir IP'nin MAC adresinin aniden değişmesi gibi anomalileri tespit edip alarm üretir — bu tespit odaklı bir savunmadır, engellemez ama görünürlük sağlar.

## Yaygın Hatalar

Uygulamada savunmayı çökerten en sık hatalar şunlardır:

**"HTTPS var, güvendeyiz" yanılgısı.** HTTPS gerekli ama yeterli değildir. HSTS olmadan HTTPS, SSL stripping'e açıktır. Karışık içerik (mixed content) — HTTPS sayfa içinde HTTP kaynak yüklemek — de bir sızıntı noktasıdır. Ayrıca iç ağdaki servislerin (yönetim panelleri, veritabanları, API'ler) çoğu hâlâ TLS'siz konuşur ve bunlar MITM için verimli hedeflerdir.

**DAI'yi DHCP snooping olmadan kurmaya çalışmak.** DAI, güvenilir bir binding table'a dayanır. DHCP snooping düzgün yapılandırılmadan DAI ya çalışmaz ya da meşru trafiği engelleyerek ağı bozar. İkisi bir bütündür.

**Trusted port'ları yanlış işaretlemek.** Bir son kullanıcı port'unu yanlışlıkla trusted işaretlemek, o port'tan gelen tüm ARP paketlerini denetimsiz geçirir ve savunmada büyük bir delik açar. Tam tersi, uplink'i untrusted bırakmak meşru ARP trafiğini engeller.

**Sertifika uyarılarını normalleştirmek.** İç sistemlerde self-signed sertifika kullanıp kullanıcıları uyarıyı geçmeye alıştırmak, onları gerçek bir MITM saldırısındaki uyarıya karşı da körleştirir. Uyarı yorgunluğu (alert fatigue) bir insan zafiyetidir.

**Wi-Fi'yi güvenli sanmak.** Aynı WPA2/WPA3 ağındaki cihazlar birbirini görebilir ve ARP spoofing yapabilir. Şifre bilmek yeterlidir — kafede herkes şifreyi bilir. **Client isolation** (AP isolation) özelliği kapalıysa, misafir ağı bile MITM'e açıktır.

**Sadece engellemeye odaklanıp tespiti unutmak.** Hiçbir savunma yüzde yüz değildir. arpwatch benzeri izleme ve loglama olmadan, savunma delindiğinde kimse fark etmez.

## En İyi Pratikler

Sağlam bir duruş için önerilenler, önem sırasıyla:

**Her yerde, iç ağ dahil, güçlü TLS kullanın.** "Zero trust network" yaklaşımını benimseyin: ağın hiçbir bölümünü otomatik güvenli saymayın. İç servisler dahil tüm iletişimi TLS ile şifreleyin, sertifikaları düzgün doğrulayın. Bu, ARP spoofing gerçekleşse bile trafiği koruyan en dayanıklı katmandır.

**HSTS'i preload ile birlikte açın.** HTTPS sunan her site için HSTS başlığını uzun bir süreyle (ve uygunsa `includeSubDomains` ve preload ile) yapılandırın. Bu, SSL stripping'i büyük ölçüde etkisiz kılar.

**Yönetilebilir switch'lerde DAI + DHCP snooping + port security üçlüsünü etkinleştirin.** Trusted/untrusted port ayrımını dikkatli yapın, statik IP'li sunucular için ARP ACL tanımlayın. Bu, saldırının kaynağını ağ altyapısında keser.

**Kritik cihaz çiftleri için statik ARP kullanın.** Sunucu-ağ geçidi gibi az sayıda ama kritik eşleşme için manuel sabitleme, ekstra bir güvence katmanıdır.

**Ağı segmentlere ve VLAN'lara ayırın.** Saldırı yüzeyini daraltın; bir saldırganın erişebileceği hedefleri sınırlayın. Misafir ağlarında client isolation'ı mutlaka açın.

**Sürekli izleme kurun.** arpwatch veya SIEM entegrasyonu ile ARP anomalilerini (bir IP'nin MAC'inin değişmesi, aynı MAC'in birden çok IP iddia etmesi) tespit edin ve alarma bağlayın.

**Mobil ve hassas uygulamalarda certificate pinning uygulayın.** CA katmanındaki zafiyetlere karşı ek güvence sağlar.

**İnsan katmanını unutmayın.** Kullanıcıları sertifika uyarılarını ciddiye almaları konusunda eğitin; geliştirici tarafında sertifika doğrulamayı asla kapatmayın (`verify=False` gibi ayarlar production'da yasaklanmalı).

## Kapanış

ARP spoofing, kırk yıl önce güvenilir bir ağ varsayımıyla tasarlanmış bir protokolün, düşman içerebilen modern ağlarda nasıl bir zafiyete dönüştüğünün ders kitabı örneğidir. Saldırının kalbinde tek bir eksiklik yatar: Layer 2'de kimlik doğrulanmaz. Bu yüzden savunma da iki cepheden yürütülür — ağ altyapısında zehirlemeyi engellemek (DAI, DHCP snooping, statik ARP, segmentasyon) ve trafiği ağdan bağımsız olarak korumak (TLS, HSTS, pinning). Bu iki cephe birbirinin yerine değil, tamamlayıcısıdır. Ağa hiç güvenmeyen ama yine de ağı da sertleştiren bir mimari, MITM saldırganını en zayıf konumuna — okuyamadığı, değiştiremediği baytları kör bir şekilde ileten pasif bir aktöre — indirger.
