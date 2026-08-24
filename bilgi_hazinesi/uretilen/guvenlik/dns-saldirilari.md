# DNS Saldırıları: Spoofing, Cache Poisoning, Tünelleme, Rebinding ve Modern Savunmalar

## Giriş: DNS Neden Bu Kadar Kırılgan Bir Katman?

DNS (Domain Name System), internetin telefon rehberidir: insanların okuyabildiği alan adlarını (`ornek.com`) makinelerin yönlendirme için kullandığı IP adreslerine (`93.184.216.34`) çevirir. Ancak DNS, 1980'lerin başında, herkesin birbirine güvendiği küçük bir akademik ağ için tasarlandı. O günden bugüne DNS, dünyanın en kritik altyapı protokolü hâline geldi ama temel güven modeli neredeyse hiç değişmedi.

Buradaki kök sorun şudur: klasik DNS, **UDP üzerinden çalışan, kimlik doğrulaması olmayan (unauthenticated) ve şifrelenmemiş (unencrypted) bir protokoldür.** Bir DNS sorgusuna gelen yanıtın gerçekten sorgunun gönderildiği sunucudan gelip gelmediğini, yolda değiştirilip değiştirilmediğini protokol kendi başına doğrulayamaz. Yanıtı ilk gören ve doğru görünen (query'yi eşleştiren) paket kabul edilir. İşte DNS saldırılarının büyük çoğunluğu bu tek zaafiyeti sömürür.

Bu makale, DNS'e yönelik başlıca saldırı sınıflarını (spoofing, cache poisoning, tünelleme, rebinding) hem istismar mantığıyla hem de savunma perspektifinden ele alıyor; ardından modern savunma katmanları olan DNSSEC, DoH ve DoT'un ne yaptığını, neyi çözmediğini açıklıyor.

## DNS'in Çalışma Mantığı: Saldırıları Anlamak İçin Temel

Bir çözümleme (resolution) sürecini adım adım anlamak, zaafiyetlerin nerede oturduğunu görmek için şarttır.

1. İstemci (client) bir alan adını sorar. Genellikle bu sorgu, kuruluşun ya da ISP'nin **recursive resolver**'ına (özyinelemeli çözümleyici) gider.
2. Recursive resolver, cevabı **cache**'inde bulamazsa, hiyerarşinin tepesinden başlayarak sorar: önce **root** sunucuları, sonra **TLD** sunucuları (`.com`), en sonunda alan adının **authoritative** (yetkili) sunucusu.
3. Authoritative sunucu nihai cevabı verir. Recursive resolver bu cevabı, kaydın **TTL** (Time To Live) değeri kadar cache'ler ve istemciye döner.

Buradaki iki kritik nokta:

- **Cache mekanizması saldırganın hedefidir.** Bir resolver'ın cache'ine tek bir sahte kayıt sokabilirseniz, o kayıt TTL süresince (saatler olabilir) o resolver'ı kullanan **binlerce** kullanıcıyı etkiler. Saldırının kaldıraç etkisi budur.
- **UDP tabanlı sorgu/yanıt eşleştirmesi zayıftır.** Bir yanıtın "doğru" sayılması için eşleşmesi gereken alanlar tarihsel olarak çok azdı: kaynak/hedef IP ve port, ve 16-bit'lik **Transaction ID (TXID)**. 16 bit yalnızca 65.536 ihtimal demektir; bu, brute-force için gülünç derecede küçük bir uzaydır.

## DNS Spoofing (Sahtecilik): Genel Sınıf

**DNS spoofing**, bir DNS yanıtının sahtesini üretip kurbanı yanlış bir IP'ye yönlendirme saldırılarının şemsiye adıdır. Cache poisoning bunun kalıcı ve ölçekli bir alt türüdür; ama spoofing daha genel olarak "araya girip sahte cevap enjekte etme" anlamına gelir.

### Çalışma mantığı

İki temel senaryo vardır:

**1. On-path (yol üstü) saldırgan.** Saldırgan, kurbanla resolver arasındaki trafiği görebiliyorsa (örneğin aynı halka açık Wi-Fi'de, ARP spoofing ile veya ele geçirilmiş bir router'da), sorguyu görür, TXID'yi ve portu okur ve gerçek yanıttan **önce** mükemmel eşleşen sahte bir yanıt gönderir. DNS'te "ilk gelen ve eşleşen kazanır" kuralı olduğu için gerçek yanıt geldiğinde çoktan geç kalmıştır ve sessizce atılır. Bu senaryoda saldırı neredeyse deterministiktir çünkü tahmin etmesi gereken hiçbir şey yoktur; her şeyi görmektedir.

**2. Off-path (yol dışı) saldırgan.** Saldırgan trafiği göremiyorsa TXID ve kaynak portu **tahmin** etmek zorundadır. Bu, cache poisoning'in klasik zorlu problemidir ve aşağıda ayrıntısına giriyoruz.

### Somut örnek

Diyelim ki kurumsal bir kullanıcı `banka.com` yazıyor. Aynı ağdaki bir saldırgan, kullanıcının resolver'ına gönderdiği sorguyu yakalar; `banka.com A?` sorgusunun TXID'sini `0x1A2B` olarak okur ve anında `banka.com -> 6.6.6.6` diyen, aynı TXID'yi taşıyan sahte bir UDP yanıtı basar. Kullanıcının tarayıcısı `6.6.6.6`'ya bağlanır; burada saldırganın barındırdığı, gerçeğine tıpatıp benzeyen bir phishing sayfası vardır. TLS sertifikası uyarısı çıkabilir ama birçok kullanıcı bunu tıklayıp geçer, ya da saldırgan aynı zamanda TLS'i de düşürmeye (downgrade) çalışır.

## Cache Poisoning: Off-path Saldırının Zirvesi ve Kaminsky

Cache poisoning, off-path bir saldırganın recursive resolver'ın cache'ine sahte kayıt yerleştirmesidir. Bunun tarihi, DNS güvenliğinin dönüm noktasıdır.

### Neden zor, neden mümkün?

Off-path saldırganın sahte bir yanıtı kabul ettirebilmesi için şu alanları doğru eşleştirmesi gerekir:

- **TXID** (16 bit)
- **Kaynak port** (eskiden çoğu resolver sabit bir port kullanırdı; bu, 16 bit daha güvenlik demekti ama kullanılmıyordu)
- Sorgunun **tam adı** ve tipi
- Yanıtın, resolver'ın o an sorduğu authoritative sunucunun IP'sinden geliyormuş gibi görünmesi

Tarihsel olarak birçok resolver **sabit kaynak port** kullandığından, saldırganın tahmin etmesi gereken tek şey pratikte 16-bit TXID idi. Ama tek bir sahte yanıtın gerçek yanıştan önce varması gerekir; bir kaçırırsanız gerçek cevap cache'lenir ve TTL boyunca yeni deneme yapamazsınız. Bu, saldırıyı yavaşlatan doğal bir fren gibiydi.

### Kaminsky saldırısının dehası

2008'de Dan Kaminsky, bu freni ortadan kaldıran yöntemi kamuoyuna gösterdi. Fikrin özü şudur: hedef domain'in kendisini değil, o domain altında **var olmayan rastgele alt alan adlarını** sorgulat (`random1234.banka.com`, `random5678.banka.com`...). Her sorgu var olmayan bir isim olduğu için cache'te bulunmaz ve resolver her seferinde yeni bir dış sorgu yapar. Böylece saldırgan, TTL frenine takılmadan **sınırsız deneme** hakkı kazanır.

Asıl kritik hamle ise, sahte yanıtta **Authority/Additional** bölümlerini kullanmaktı: saldırgan, "`random1234.banka.com` için cevabı bilmiyorum ama `banka.com`'un yetkili sunucusu şudur: NS kaydı `ns.banka.com` -> **saldırganın IP'si**" gibi bir yönlendirme (delegation) enjekte eder. Bu tutarsa, artık `banka.com`'un **tüm** alt alanları için yetkili sunucu saldırgan olur. Yani tek bir başarılı enjeksiyonla saldırgan sadece bir kaydı değil, bütün domain'i ele geçirir.

### Savunma: entropiyi artırmak

Kaminsky'ye verilen ana yanıt yeni bir protokol değil, **belirsizliği (entropy) artırmak** oldu; çünkü kök sorun tahmin edilebilirlikti:

- **Source Port Randomization (kaynak port rastgeleleştirme):** Resolver her sorguda rastgele bir kaynak port kullanır. Bu, saldırganın tahmin etmesi gereken uzayı 16 bit'ten ~32 bit'e çıkarır ve brute-force'u pratikte devasa zorlaştırır. Bu, bugün her düzgün resolver'da varsayılandır ve o dönemin acil yamasıydı.
- **0x20 encoding (DNS-0x20):** Sorgudaki harflerin büyük/küçük hâli rastgeleleştirilir (`BaNka.CoM`). DNS isimleri büyük/küçük harfe duyarsız çözümlenir ama yanıt sorgudaki harf düzenini korumak zorundadır. Bu, ismin uzunluğuna bağlı ekstra entropi ekler.
- **DNSSEC:** Asıl kalıcı çözüm (aşağıda ayrıntılı).

Önemli bir dürüstlük notu: kaynak port rastgeleleştirme ve 0x20 saldırıyı **çok zorlaştırır ama teorik olarak imkânsız kılmaz.** Yıllar içinde (özellikle "SAD DNS" gibi araştırmalar) ICMP hız sınırlama gibi yan kanallardan yararlanarak kaynak portu daraltma teknikleri gösterildi; bu da entropi artırmanın palyatif, DNSSEC'in ise yapısal çözüm olduğunu kanıtlar.

## DNS Tünelleme (Tunneling): Veriyi DNS İçinde Kaçırmak

DNS tünelleme, cache poisoning'den tamamen farklı bir amaca hizmet eder. Burada amaç kandırmak değil, **DNS trafiğini gizli bir veri kanalı (covert channel) olarak kullanmaktır.**

### Kök neden: DNS neredeyse her zaman açıktır

Bir kurumsal ağ, HTTP ve HTTPS dahil çoğu giden trafiği firewall ve proxy ile kısıtlayabilir. Ama DNS'i tamamen kapatan bir ağ neredeyse yoktur; çünkü DNS olmadan hiçbir isim çözülemez, ağ çalışmaz. Dahası, iç istemciler genellikle doğrudan dış DNS sunucularına değil, iç resolver'a sorar; iç resolver ise **kendisi** dışarıya recursive sorgu yapar. Bu, saldırgan için mükemmel bir kaçış yoludur: veri, meşru DNS altyapısının içinden dışarı akar.

### Çalışma mantığı

Saldırgan, kontrolündeki bir domain'in (`kotu.com`) authoritative sunucusunu kendi çalıştırır. Ele geçirdiği iç makinedeki malware, kaçırmak istediği veriyi (örneğin çalınan bir parola ya da komut sonucu) encode ederek bir **alt alan adı** hâline getirir:

```
[encode-edilmis-veri].kotu.com
```

İç makine bu ismi sorunca, sorgu iç resolver üzerinden zorunlu olarak `kotu.com`'un authoritative sunucusuna (yani saldırgana) ulaşır. Saldırgan, alt alan adındaki veriyi decode eder; cevabı da (örneğin sonraki komutu) TXT veya CNAME kaydının içine encode ederek geri gönderir. Böylece iki yönlü, firewall'u aşan bir C2 (command and control) kanalı kurulmuş olur. Iomap, dnscat2, iodine gibi araçlar bu tekniğin bilinen örnekleridir.

### Neden fark edilmesi zor?

Çünkü tek tek her sorgu, teknik olarak geçerli bir DNS sorgusudur. Anomali, tek pakette değil, **davranış örüntüsünde** gizlidir: anormal derecede uzun alt alan adları, tek bir domain'e yönelik olağanüstü yüksek sorgu hacmi, yüksek oranda TXT/NULL kayıt talebi, sürekli var olmayan (NXDOMAIN) benzeri rastgele isimler, ve entropi bakımından "veri gibi" görünen etiketler.

### Savunma

- **DNS trafiği analizi ve baseline:** Domain başına sorgu hacmi, ortalama sorgu uzunluğu, kayıt tipi dağılımı gibi metrikleri izleyip normalden sapmaları yakalayın. Yüksek entropili, uzun alt alan adları güçlü bir sinyaldir.
- **Merkezî resolver zorunluluğu:** İstemcilerin doğrudan 53 numaralı porttan dışarı çıkmasını engelleyin; tüm DNS'i denetlenen iç resolver'lara zorlayın. Böylece görünürlük ve loglama tek noktada toplanır.
- **Threat intelligence ve yeni domain filtreleme:** Yeni kaydedilmiş (newly registered) veya itibarsız domain'lere giden çözümlemeleri kısıtlamak, tünel domain'lerini erkenden keser.
- **Payload boyutu ve tip kısıtları:** Beklenmedik ölçüde büyük TXT yanıtlarına ve olağandışı kayıt tiplerine karşı politika uygulayın.

## DNS Rebinding: Tarayıcıyı İç Ağa Karşı Silah Yapmak

DNS rebinding, diğerlerinden farklı olarak DNS altyapısını bozmaz; **tarayıcının same-origin policy (SOP) güven modelindeki bir boşluğu** DNS üzerinden sömürür. Amaç, kurbanın tarayıcısını, saldırganın **ulaşamadığı** iç ağ kaynaklarına (router yönetim paneli, iç API, IoT cihazı, cloud metadata servisi) erişmek için bir vekil (proxy) olarak kullanmaktır.

### Kök neden: SOP hostname'e bakar, IP'ye değil

Tarayıcının same-origin policy'si "origin"i şema + **hostname** + port üzerinden tanımlar; altındaki IP adresini umursamaz. İşte bu ayrım saldırının kalbidir. Eğer bir saldırgan aynı hostname'in çözümlendiği IP'yi zaman içinde değiştirebilirse, tarayıcı hâlâ "aynı origin"le konuştuğunu sanırken, arka planda tamamen başka (iç) bir sunucuya bağlanmış olur.

### Çalışma mantığı

1. Kurban, saldırganın `kotu.com` sitesini ziyaret eder. Saldırgan, bu domain için **çok kısa TTL** (örneğin birkaç saniye) ayarlamıştır.
2. İlk sorguda `kotu.com`, saldırganın gerçek sunucusunun genel IP'sine çözümlenir. Sayfa yüklenir, JavaScript çalışmaya başlar ve arka planda `kotu.com`'a tekrar tekrar istek atan bir döngü kurar.
3. TTL dolduktan sonra saldırganın authoritative DNS sunucusu, aynı `kotu.com` ismini bu kez bir **iç/özel IP**'ye (örneğin `192.168.1.1` router paneli ya da cloud'daki `169.254.169.254` metadata adresi) çözümler.
4. Tarayıcı, JavaScript hâlâ "aynı origin" `kotu.com` ile konuştuğunu sandığı için isteği o iç IP'ye gönderir; SOP itiraz etmez. Böylece saldırganın script'i, kurbanın ağ konumunu kullanarak iç servisin cevabını okuyup dışarı sızdırabilir.

Bu, özellikle kimlik doğrulaması IP/ağ konumuna güvenen iç panellerde ve cloud metadata servislerinde çok tehlikelidir; çünkü o servisler "istek iç ağdan geliyorsa güvenilirdir" varsayımıyla çalışır.

### Savunma

Savunmanın büyük kısmı DNS'te değil, **uygulama ve tarayıcı katmanındadır** çünkü DNS burada yalnızca araçtır:

- **Host header doğrulaması:** İç servisler yalnızca beklenen `Host` başlığını kabul etmeli; `kotu.com` gibi tanımadığı bir host'la gelen isteği reddetmeli. Rebinding, saldırgan hostname'i taşıdığı için bu kontrol onu doğrudan keser.
- **Kimlik doğrulamayı ağ konumundan ayırmak:** "İç ağdan geliyorsa güvenilir" varsayımını terk edin; iç panellere de gerçek authentication koyun. Cloud metadata için IMDSv2 gibi token tabanlı erişim modelleri tam da bu tehdide karşı geliştirilmiştir.
- **DNS rebinding koruması olan resolver'lar:** Bazı resolver'lar, dış domain'lerin özel/iç IP aralıklarına (RFC 1918, loopback, link-local) çözümlenmesini engeller. Bu, klasik rebinding'i büyük ölçüde durdurur.
- **TLS zorunluluğu:** HTTPS kullanan iç servislerde sertifika hostname'i tutmayacağı için rebinding'in birçok varyantı kırılır.

## DNSSEC: Yanıtları İmzalayarak Doğrulamak

Cache poisoning ve spoofing'in kök nedeni, DNS yanıtlarının **kimliğinin ve bütünlüğünün doğrulanamamasıydı.** DNSSEC (DNS Security Extensions) tam olarak bu problemi çözmek için tasarlandı.

### Nasıl çalışır?

DNSSEC, her DNS kaydına **kriptografik imza** ekler (RRSIG kayıtları). Yetkili sunucu, kayıt kümelerini özel anahtarıyla imzalar; resolver ise ilgili açık anahtarı (DNSKEY) kullanarak imzayı doğrular. İmza tutuyorsa, resolver yanıtın gerçekten yetkili sunucudan geldiğinden ve yolda değiştirilmediğinden emin olabilir. Sahte enjekte edilmiş bir yanıtın geçerli imzası olamayacağı için off-path saldırgan artık cache'i zehirleyemez.

Bu doğrulamanın güvenilir olması için imzalayan anahtarların da doğrulanması gerekir. DNSSEC bunu **chain of trust** (güven zinciri) ile çözer: root zone kendini imzalar, `.com` bölgesinin anahtarını root imzalar (DS kaydı ile), alan adının anahtarını da `.com` imzalar. Böylece root'tan yaprağa kadar kesintisiz bir imza zinciri oluşur.

### DNSSEC neyi çözer, neyi çözmez? (Dürüstlük bölümü)

DNSSEC'i doğru konumlandırmak kritik, çünkü sık yanlış anlaşılır:

- **Çözdüğü:** Yanıtın **doğruluğu ve bütünlüğü.** Yani "bu cevap gerçekten yetkili sunucudan mı ve değiştirilmemiş mi?" sorusunu güvenle cevaplar. Cache poisoning'e karşı yapısal savunmadır.
- **Çözmediği #1 — Gizlilik yok:** DNSSEC **şifreleme değildir.** İmzalar bütünlüğü sağlar ama sorgu ve yanıt hâlâ **açık (plaintext)** gider. Yani araya giren biri hangi siteleri ziyaret ettiğinizi görebilir. Gizlilik için DoH/DoT gerekir.
- **Çözmediği #2 — "Son adım" sorunu:** DNSSEC doğrulaması genellikle recursive resolver'da yapılır. Resolver ile istemci arasındaki son adım (last mile) çoğunlukla doğrulanmaz; oradaki bir on-path saldırgan hâlâ tehdit olabilir. Bunun için stub resolver'da doğrulama gerekir.
- **Dağıtım (deployment) zorlukları:** DNSSEC operasyonel olarak karmaşıktır. Anahtar rollover (anahtar değişimi) hataları, süresi dolmuş imzalar, ya da zincirdeki bir kopukluk, alan adını **komple erişilemez** hâle getirebilir. Bu operasyonel kırılganlık, benimsenmesini yıllarca yavaşlatmıştır. Ayrıca NSEC kayıtları üzerinden **zone enumeration** (bölgedeki tüm isimleri listeleme) gibi yan etkiler doğmuş, buna karşı NSEC3 gibi hafifletmeler geliştirilmiştir.

## DoH ve DoT: DNS'i Şifrelemek

DNSSEC bütünlüğü çözerken **gizliliği** çözmez. DoH (DNS over HTTPS) ve DoT (DNS over TLS) tam da bu boşluğu doldurur: DNS sorgu ve yanıtlarını **TLS ile şifreleyerek** istemci ile resolver arasındaki trafiği araya girenlerden gizler.

### Aralarındaki fark

- **DoT:** DNS trafiğini kendine ait, ayrılmış bir port üzerinden TLS tüneli içinde taşır. DNS trafiği olduğu **ağ seviyesinde ayırt edilebilir** ve gerekirse politikayla yönetilebilir.
- **DoH:** DNS sorgularını normal HTTPS trafiğinin içine gömer ve standart HTTPS portunu kullanır. Bu, DNS'i diğer web trafiğinden **ayırt edilemez** kılar; gizlilik açısından güçlüdür ama kurumsal görünürlük açısından tartışmalıdır.

### Neyi çözer, hangi ikilemi getirir? (Dürüstlük bölümü)

DoH/DoT, on-path bir gözlemcinin sorgularınızı okumasını ve içeriği değiştirmesini engeller; bu, kamuya açık Wi-Fi gibi ortamlarda gerçek bir kazanımdır. Ancak önemli bir gerilim vardır:

- **DoH ile güvenlik ekibinin görünürlüğü azalır.** Birçok kurumsal savunma, DNS loglarını izleyerek malware C2 alan adlarını, tünelleme davranışını ve veri sızıntısını yakalar. DoH, DNS'i HTTPS içine gömdüğü için bu görünürlüğü zayıflatabilir; hatta bazı malware'ler tam da bu yüzden DoH'u tercih eder. Yani aynı teknoloji, son kullanıcının mahremiyetini korurken kurumsal savunmayı köreltebilir. Doğru yaklaşım genellikle **kurumsal, denetlenen bir DoH/DoT resolver'ına yönlendirmektir** ki hem şifreleme hem görünürlük korunsun.
- **Güven, resolver'a kayar.** Şifreli kanal, sizinle resolver arasını korur ama resolver'ın kendisi hâlâ tüm sorgularınızı görür. Yani güveni ISP'den, seçtiğiniz DoH sağlayıcısına devretmiş olursunuz.
- **DoH/DoT şifreleme sağlar, doğrulama değil.** Yanıtın içeriğinin doğru olduğunu garanti etmez; onu DNSSEC yapar. Bu yüzden **DoH/DoT ve DNSSEC birbirinin rakibi değil, tamamlayıcısıdır:** biri gizliliği (confidentiality), diğeri bütünlüğü (integrity) sağlar. İkisini birlikte kullanmak tam korumaya yaklaştırır.

## Yaygın Hatalar

Sahadaki en sık görülen ve pahalıya patlayan hatalar şunlardır:

- **Açık (open) recursive resolver çalıştırmak.** İnternete açık, herkesin sorgulayabildiği bir recursive resolver, hem cache poisoning'e daha açıktır hem de **DNS amplification DDoS** saldırılarında bir silah olarak kötüye kullanılır (küçük bir sorgu, büyük bir yanıt üretip kurbanın IP'sine yönlendirilir). Resolver'lar yalnızca meşru istemcilere hizmet verecek şekilde kısıtlanmalıdır.
- **Kaynak port rastgeleleştirmenin kapalı olduğunu fark etmemek.** Eski konfigürasyonlar ya da araya giren NAT/firewall'lar port rastgeleliğini bozabilir; bu, resolver'ı Kaminsky sınıfı saldırılara yeniden açar. Bunun doğrulanması gerekir.
- **DNSSEC'i "kurdum, bitti" sanmak.** İmzaların süresi dolar; anahtar rollover süreçleri otomatikleştirilmezse imzalar geçersiz olur ve alan adı erişilemez hâle gelir. DNSSEC sürekli operasyonel bakım ister.
- **İç servisleri ağ konumuna güvenerek korumasız bırakmak.** "İç ağdan gelen isteğe güvenilir" varsayımı, DNS rebinding ve SSRF sınıfı saldırıların can damarıdır. İç panellere de gerçek authentication ve Host header doğrulaması konmalıdır.
- **DNS trafiğini loglamamak/izlememek.** DNS logları, tünelleme ve C2 tespitinde en değerli veri kaynaklarından biridir. Toplanmadıkları takdirde saldırı görünmez kalır.
- **Registrar/DNS hesabını zayıf korumak.** Saldırının en yıkıcı ama en gözden kaçan biçimi, doğrudan **domain hijacking**'tir: registrar hesabı ele geçirilirse (zayıf parola, MFA yokluğu) saldırgan nameserver'ları değiştirerek tüm trafiği yönlendirir. Hiçbir teknik DNS koruması bunu telafi etmez.

## En İyi Pratikler

Katmanlı bir savunma (defense in depth) yaklaşımı, tek bir sihirli çözümden çok daha etkilidir:

1. **Entropiyi ve modern resolver ayarlarını sağlamlaştırın.** Kaynak port rastgeleleştirme açık, resolver güncel ve mümkünse 0x20 gibi ek entropi teknikleri etkin olmalı. Bu, spoofing/poisoning'in maliyetini tavana çıkarır.
2. **DNSSEC'i hem imzalama hem doğrulama tarafında uygulayın.** Kendi bölgelerinizi imzalayın; resolver'larınızda doğrulamayı açın. Anahtar yönetimini ve rollover'ı otomatikleştirin ki operasyonel kırılganlık riske dönüşmesin.
3. **Şifreli DNS'i (DoH/DoT) bilinçli konumlandırın.** Kullanıcı gizliliğini korurken kurumsal görünürlüğü kaybetmemek için trafiği denetlenen kurumsal bir şifreli resolver'a yönlendirin. Şifreleme (DoH/DoT) ile bütünlüğü (DNSSEC) birlikte düşünün.
4. **Merkezî, denetlenen resolver mimarisi kurun.** İstemcilerin doğrudan dışa DNS sorgusu yapmasını engelleyin; tüm çözümlemeyi loglayan iç resolver'lardan geçirin. Bu, hem tünelleme tespitini hem politika uygulamasını mümkün kılar.
5. **DNS trafiğini sürekli izleyin ve baseline oluşturun.** Domain başına hacim, sorgu uzunluğu, kayıt tipi dağılımı ve entropi metriklerini takip edin; yeni kaydedilmiş ve itibarsız domain'leri filtreleyin. Tünelleme ve C2 imzaları çoğunlukla davranışta gizlidir.
6. **İç servisleri ağ konumundan bağımsız koruyun.** Gerçek authentication, Host header doğrulaması ve token tabanlı metadata erişimi (IMDSv2 benzeri) uygulayarak rebinding ve SSRF yüzeyini kapatın; resolver seviyesinde iç IP'ye çözümlemeyi engelleyin.
7. **Registrar ve DNS yönetim hesaplarını en yüksek seviyede koruyun.** Güçlü MFA, registrar lock (transfer/değişiklik kilidi) ve erişimin sıkı kısıtlanması; çünkü bu hesap, tüm DNS güvenliğinizin tek noktadan çökme (single point of failure) noktasıdır.

## Sonuç

DNS saldırılarının neredeyse tamamı, aynı kök nedene farklı açılardan yaklaşır: klasik DNS'in kimlik doğrulaması ve şifrelemesi olmayan güven modeline. Spoofing ve cache poisoning bu güven boşluğunu doğrudan sömürür; tünelleme DNS'in her yerde açık oluşunu bir kaçış kanalına çevirir; rebinding ise DNS'i, tarayıcının güven modelini kandırmak için bir kaldıraç olarak kullanır. Modern savunmalar bunu iki eksende kapatır: **DNSSEC bütünlüğü, DoH/DoT gizliliği** getirir. Ama hiçbiri tek başına yeterli değildir; gerçek koruma, entropiden imzalamaya, şifrelemeden davranış analizine ve hesap güvenliğine uzanan katmanlı bir yaklaşımdan gelir. DNS'i "sadece çalışan, görünmez bir altyapı" olarak görmek en büyük hatadır; çünkü saldırgan için o, internetin en değerli ve en az korunan kavşağıdır.
