# Firewall ve Ağ Segmentasyonu

## Giriş ve Tanımlar

Ağ güvenliğinin temelinde tek ve basit bir soru yatar: **"Bu paketin bir yerden başka bir yere gitmesine izin verilmeli mi?"** Firewall (güvenlik duvarı) ve ağ segmentasyonu, bu soruyu ölçeklenebilir, denetlenebilir ve sürdürülebilir biçimde cevaplayan iki tamamlayıcı disiplindir.

**Firewall**, iki ağ bölgesi arasındaki trafiği önceden tanımlanmış kurallara göre denetleyen kontrol noktasıdır. Klasik bir firewall paketin kaynak/hedef IP adresine, portuna ve protokolüne bakar. Daha modern nesli (NGFW — Next Generation Firewall) ise Layer 7'ye çıkar; hangi uygulamanın konuştuğunu (örneğin 443 portundan geçenin gerçekten TLS mi yoksa tünellenmiş bir SSH mi olduğunu), hangi kullanıcının oturum açtığını ve trafiğin içinde bilinen bir saldırı imzası olup olmadığını değerlendirir.

**Ağ segmentasyonu** ise firewall'un koruduğu bölgeleri yaratma sanatıdır. Tek düz (flat) bir ağ, bir saldırgan için düz bir ova gibidir: bir makineye girmek, tümüne girmek demektir. Segmentasyon bu ovayı duvarlarla bölerek, bir bölgedeki ihlalin diğerine sıçramasını (lateral movement — yanal hareket) zorlaştırır.

Bu makalenin odak noktaları — **default deny**, **DMZ**, **mikrosegmentasyon** ve **zero trust ağ** — aslında aynı fikrin giderek incelen katmanlarıdır: güveni azalt, sınırları çoğalt, her isteği doğrula.

## Kök Neden: Neden Segmentasyona İhtiyaç Duyuyoruz?

Segmentasyonun neden var olduğunu anlamak için önce güvenlik ihlallerinin nasıl büyüdüğünü anlamak gerekir. Bir saldırı neredeyse hiçbir zaman tek adımda hedefe ulaşmaz. Tipik bir ihlal zinciri şöyle işler:

1. **İlk erişim (initial access):** Genellikle çevresel (perimeter) bir zayıflık — phishing ile ele geçirilmiş bir kullanıcı, internete açık savunmasız bir servis, ya da bir tedarikçi bağlantısı.
2. **Ayakta kalma ve keşif:** Saldırgan bulunduğu makineden ağı tarar, komşu sistemleri, açık portları ve kimlik bilgilerini keşfeder.
3. **Yanal hareket (lateral movement):** Keşfettiği zafiyetler ve çalınan kimlik bilgileriyle bir sistemden diğerine atlar.
4. **Ayrıcalık yükseltme ve hedefe ulaşma:** Nihai olarak domain controller, veritabanı veya yedek sunucusu gibi "taç mücevherlere" ulaşır.

İşte segmentasyonun kök mantığı burada: **Bu zincirin en pahalı, en gürültülü ve savunanın lehine olan aşaması yanal harekettir.** Saldırgan ilk makineye girdiğinde henüz hedefine varmamıştır; asıl değer, girdiği yerden ilerleyebilmesindedir. Ağı bölgelere ayırıp bölgeler arası trafiği zorunlu kontrol noktalarından geçirdiğinizde, saldırganın her adımı bir duvara toslar. Her duvar hem bir engel hem de bir alarm noktasıdır. Bu yüzden segmentasyon aynı zamanda **tespit** (detection) stratejisidir: bölgeler arası anormal trafik, düz bir ağda görünmez olan sinyali görünür kılar.

Bir başka kök neden **patlama yarıçapını (blast radius) sınırlamaktır.** Sıfır ihlal hedefi gerçekçi değildir; er ya da geç bir sistem düşecektir. Doğru soru "ihlal olacak mı" değil, "ihlal olduğunda ne kadar yayılacak" sorusudur. Segmentasyon bu yarıçapı küçültür: bir web sunucusunun ele geçmesi, tüm iç ağın ele geçmesi anlamına gelmemelidir.

## Default Deny: Güvenliğin Varsayılan Duruşu

### Tanım ve Çalışma Mantığı

**Default deny** (varsayılan olarak reddet), bir firewall veya erişim kontrol politikasının temel duruşudur: **Açıkça izin verilmemiş her şey yasaktır.** Bunun karşıtı olan **default allow** (varsayılan olarak izin ver), açıkça yasaklanmamış her şeye izin verir.

Bu ikisi arasındaki fark yalnızca teknik bir tercih değil, felsefi bir tutumdur. Default allow ile çalışıyorsanız, güvende olmak için gelecekteki *tüm* kötü şeyleri önceden tahmin edip yasaklamanız gerekir — bu imkânsızdır, çünkü yarın keşfedilecek saldırı yöntemini bugün listeleyemezsiniz. Default deny ile ise, yalnızca *bilinen ve gerekli* iyi şeyleri tanımlarsınız; bilmediğiniz her şey otomatik olarak kapalıdır. Güvenlikte bilgi asimetriği her zaman saldırgan lehinedir; default deny bu asimetriği tersine çevirir, çünkü "iyi trafik" kümesi sonlu ve bilinirken "kötü trafik" kümesi sonsuzdur.

### Kök Neden: Neden Sonsuzu Değil Sonluyu Tanımlarsınız

Bir kurumsal ağda meşru trafik akışları aslında şaşırtıcı derecede azdır ve öngörülebilir. Web sunucusu veritabanına 5432 portundan konuşur; kullanıcı istasyonları DNS ve HTTPS kullanır; yönetim trafiği belirli bir yönetim ağından gelir. Bu "iyi" liste onlarca, belki yüzlerce kuraldan oluşur. Buna karşılık, engellenmesi gereken "kötü" olasılıklar milyarlarcadır. Sonlu bir kümeyi doğru tanımlamak, sonsuz bir kümeyi tam kapsamlı yasaklamaktan çok daha kolaydır. Default deny'in matematiksel üstünlüğü tam olarak budur.

### İstismar Mantığı ve Savunma

**İstismar tarafı:** Saldırgan, default allow yapılandırmalarının bıraktığı "kör noktaları" arar. Örneğin bir firewall'da içeriden dışarıya (egress/çıkış) trafik çoğu kurumda hiç kısıtlanmaz — herkes default allow ile serbestçe internete çıkabilir. Saldırgan tam da bunu sömürür: ele geçirdiği makineden C2 (command and control) sunucusuna dışarı bağlantı kurar, verileri dışarı sızdırır (exfiltration), genellikle 443 gibi her yerde açık olan portlar üzerinden. Çünkü çoğu kurum içeriye gelen trafiği titizlikle kısıtlarken, dışarı gideni "zaten bizim insanlarımız" diye serbest bırakır.

**Savunma tarafı:** Default deny yalnızca içeri (ingress) değil, **dışarı (egress) yönde de uygulanmalıdır.** İç sistemlerin yalnızca gerçekten ihtiyaç duyduğu hedeflere çıkmasına izin verin. Bir veritabanı sunucusunun internete hiç çıkmaması gerekir; çıkıyorsa bu zaten bir alarmdır. Egress filtreleme, veri sızdırmayı ve C2 iletişimini kıran en etkili ama en çok ihmal edilen kontroldür.

Default deny'i uygularken dikkat edilmesi gereken kritik bir ayrıntı: **DROP mı yoksa REJECT mi?** DROP paketi sessizce yutar; kaynak hiçbir yanıt almaz ve zaman aşımına kadar bekler. REJECT ise "reddedildi" mesajı (örneğin TCP RST veya ICMP unreachable) döner. Dışa bakan (internet yüzü) arayüzlerde genellikle DROP tercih edilir, çünkü saldırgana port taramasında bilgi vermez ve tarama sürecini yavaşlatır. İç ağda ise REJECT bazen tercih edilir, çünkü meşru uygulamalar hızlı hata alıp beklemeden devam eder — kullanıcı deneyimi ve sorun teşhisi kolaylaşır.

## DMZ: Çevre ile İç Ağ Arasındaki Tampon

### Tanım ve Çalışma Mantığı

**DMZ (Demilitarized Zone — Silahsızlandırılmış Bölge)**, internete hizmet vermek zorunda olan sistemlerin (web sunucuları, mail geçitleri, reverse proxy'ler, VPN başlıkları) yerleştirildiği, iç ağdan yalıtılmış bir ara bölgedir. Adı askeri terminolojiden gelir: iki cephe arasındaki, hiçbir tarafın tam hâkim olmadığı tampon bölge.

DMZ'nin mantığı basittir: **İnternete açık olan her sistem, tanımı gereği en yüksek ihlal riskini taşır.** Bir web sunucusu milyonlarca yabancıyla konuşur; içlerinden biri kesinlikle saldırgandır. Bu sunucu bir gün ele geçecektir. Soru, ele geçtiğinde saldırganın nereye ulaşabileceğidir. DMZ, bu kaçınılmaz ihlali önceden kabul ederek onu izole bir kutunun içine koyar.

### Kök Neden: İki Firewall'lu Mimari

Klasik ve sağlam DMZ tasarımı iki firewall (ya da tek firewall üzerinde üç ayrı arayüz/bölge) kullanır ve trafik akışını şöyle kısıtlar:

- **İnternet → DMZ:** Yalnızca gerekli servis portlarına izin (örneğin web sunucusuna 443).
- **DMZ → İç ağ:** **Son derece kısıtlı.** Web sunucusunun *yalnızca* konuşması gereken belirli bir uygulama/veritabanı sunucusuna, *yalnızca* belirli bir porttan bağlanmasına izin verilir. Genel bir "DMZ iç ağa erişebilir" kuralı asla olmamalıdır.
- **İç ağ → DMZ:** Yönetim amaçlı, kontrollü.
- **DMZ → İnternet:** Kısıtlı egress (güncelleme, DNS gibi zorunlu olanlar dışında kapalı).

Bu asimetrinin kök nedeni şudur: DMZ'yi ihlal edilmiş kabul ederiz. Eğer DMZ'deki bir sunucu düşerse, saldırganın DMZ→iç ağ yönünde elinde yalnızca birkaç dar kural kalır. İç ağa serbestçe geçemez. Böylece DMZ, saldırgan için bir cam kavanoz olur: içine girebilir ama dışarı, iç ağa sızamaz.

### İstismar ve Savunma

**İstismar mantığı:** Saldırganın DMZ'de aradığı şey **pivot** noktasıdır. Web sunucusunu ele geçirdikten sonra, oradan iç ağa açılan o dar kuralları sömürmeye çalışır. Örneğin web sunucusunun veritabanına erişimi varsa, saldırgan bu bağlantıyı kullanarak veritabanına SQL injection ya da çalınan kimlik bilgileriyle saldırır. Bir başka klasik hata: DMZ sunucusunun iç ağdaki bir yönetim sunucusuna (Active Directory, bastion host) erişebilmesi — bu, kavanozun kapağının aralık kalması demektir.

**Savunma:** DMZ→iç ağ kurallarını cerrahi hassasiyetle daraltın. Web sunucusu veritabanına doğrudan değil, bir uygulama katmanı (application tier) üzerinden erişsin. DMZ sistemlerinde iç ağın domain'ine katılmış makineler bulundurmamaya çalışın; ele geçen bir DMZ makinesinin cache'inde domain kimlik bilgileri bulunması yanal harekete davetiye çıkarır. DMZ trafiğini yoğun biçimde loglayın — burası ihlalin ilk görüneceği yerdir.

## Mikrosegmentasyon: Duvarları İnceltmek

### Tanım ve Çalışma Mantığı

Klasik segmentasyon ağı büyük bölgelere ayırır (DMZ, kullanıcı ağı, sunucu ağı). Ama bir bölgenin *içinde* ne olur? Geleneksel modelde bölge içi trafik genellikle serbesttir — aynı sunucu VLAN'ındaki 200 sunucu birbirleriyle sınırsızca konuşabilir. Saldırgan bir sunucuyu ele geçirdiğinde, aynı VLAN'daki diğer 199'a duvar tanımadan ulaşır. Buna **east-west trafiği** (doğu-batı, yani aynı seviyedeki sistemler arası yatay trafik) denir ve klasik firewall'lar bunu görmez bile, çünkü trafik firewall'a hiç uğramadan switch üzerinden akar.

**Mikrosegmentasyon**, bu duvarları tek tek iş yüklerine (workload) kadar inceltir. Her sunucu, her konteyner, hatta her uygulama kendi güvenlik sınırına sahip olur. "Web sunucusu yalnızca uygulama sunucusuyla 8080'den konuşabilir, başka hiçbir sunucuyla konuşamaz" gibi kurallar, VLAN sınırından bağımsız olarak, iş yükünün kendisine yapıştırılır.

### Kök Neden: East-West Trafiği Kör Noktasıdır

Neden mikrosegmentasyona ihtiyaç var? Çünkü modern veri merkezlerinde trafiğin büyük çoğunluğu kuzey-güney (dışarı-içeri) değil, **doğu-batı** yöndedir. Uygulamalar mikroservislere bölündükçe, sunucular birbirleriyle sürekli konuşur. Klasik perimeter firewall bu iç trafiği hiç görmez. Saldırgan için bu, korunmasız bir iç dünya demektir. Mikrosegmentasyon, güvenlik denetimini ağın çekirdeğine, iş yüklerinin yanına taşıyarak bu kör noktayı kapatır.

### Uygulama Yöntemleri

Mikrosegmentasyon pratikte birkaç şekilde uygulanır:

- **Host tabanlı (agent):** Her sunucuya kurulan bir agent, o makinenin kendi ateş duvarını (host firewall) merkezi politikayla yönetir. Trafik ağa çıkmadan, kaynağında denetlenir.
- **Hypervisor / SDN tabanlı:** Sanallaştırma katmanında (örneğin dağıtık firewall) her sanal makinenin sanal ağ arayüzüne politika uygulanır.
- **Kimlik tabanlı etiketleme:** Kurallar IP adreslerine değil, iş yükünün *kimliğine* veya *etiketine* (tag/label) bağlanır — "role:web olan her şey, role:db olan her şeyle yalnızca 5432'den konuşur". Bu, bulut ve konteyner ortamlarında IP'lerin sürekli değiştiği gerçeğiyle başa çıkmanın tek sürdürülebilir yoludur. Kubernetes'teki NetworkPolicy nesneleri bu yaklaşımın bir örneğidir.

### İstismar ve Savunma

**İstismar:** Mikrosegmentasyonun olmadığı yerde saldırgan **yanal harekette özgürdür**: SMB, RDP, WinRM, SSH gibi protokollerle komşu makinelere atlar; Pass-the-Hash ve benzeri kimlik bilgisi tekrar kullanımı teknikleriyle yayılır. Fidye yazılımlarının bir makineden tüm ağı şifrelemesinin nedeni budur — düz east-west trafiği.

**Savunma:** Mikrosegmentasyon fidye yazılımının en büyük düşmanıdır. Her iş yükü yalnızca zorunlu komşularıyla konuşabildiğinde, fidye yazılımının yayılma yolları kesilir. Uygulamada **allow-list** mantığı esastır: önce trafiği bir süre gözlemleyip (discovery/mapping) gerçek akışları haritalandırın, sonra bu akışları izin listesine alıp gerisini kapatın. Yaygın bir hata, önce her şeyi kısıtlayıp uygulamaları kırmaktır; doğru yaklaşım gözlem → modelleme → uygulama sırasıdır.

## Zero Trust Ağ: Konumun Güven Anlamına Gelmediği Model

### Tanım ve Paradigma Değişimi

Geleneksel güvenlik modeli bir **kale-hendek (castle-and-moat)** mantığına dayanır: dışarısı tehlikeli, içerisi güvenli. Perimeter'ı geçtiyseniz, güvenilir sayılırsınız. Bu modelin ölümcül kusuru, ilk savunmayı geçen saldırganın içeride serbest kalmasıdır.

**Zero Trust (Sıfır Güven)** bu varsayımı tümden reddeder. Temel ilkesi tek cümleyle şudur: **"Never trust, always verify" — Asla güvenme, her zaman doğrula.** Ağdaki konumunuz (içeride ya da dışarıda olmanız) size hiçbir güven kazandırmaz. Her erişim isteği, sanki güvenilmez bir ağdan geliyormuş gibi, kendi başına doğrulanır.

Zero Trust'ın taşıdığı zihniyeti özetleyen üç ilke vardır:

1. **Açıkça doğrula (verify explicitly):** Her erişimde kimlik, cihaz sağlığı, konum ve davranışı değerlendir.
2. **En az ayrıcalık (least privilege):** Kullanıcı ve iş yüklerine yalnızca o an gereken minimum erişimi ver; erişim geniş ve kalıcı değil, dar ve geçici (just-in-time) olsun.
3. **İhlali varsay (assume breach):** Sistemi, ağın içinde zaten bir saldırgan varmış gibi tasarla. Bu yüzden segmentasyon, şifreleme ve sürekli izleme zorunludur.

### Kök Neden: Perimeter Neden Çöktü

Zero Trust bir moda değil, bir zorunluluğun cevabıdır. Kale-hendek modeli, net bir "içerisi" olduğu sürece işe yarıyordu. Ama üç gelişme bu netliği yok etti:

- **Bulut:** İş yükleriniz artık sizin veri merkezinizde değil; "içerisi" nerede başlıyor?
- **Uzaktan çalışma:** Kullanıcılar ofis ağının dışından, ev ve kafe ağlarından bağlanıyor.
- **Mobil ve SaaS:** Veriler ve uygulamalar kurumsal perimeter'ın tamamen dışında yaşıyor.

Perimeter bulanıklaştığında, "içeride olan güvenilir" varsayımı çöker. Zero Trust, güveni ağ konumundan alıp **kimliğe ve bağlama (context)** taşıyarak bu boşluğu doldurur.

### Zero Trust Ağını Mikrosegmentasyonla İlişkisi

Zero Trust bir üründen çok bir mimari yaklaşımdır ve mikrosegmentasyon onun ağ katmanındaki somut uygulamasıdır. **ZTNA (Zero Trust Network Access)** ise geleneksel VPN'in yerini alan erişim modelidir. Klasik VPN sizi ağa alır ve içerideki her şeye erişim sağlar (aşırı geniş güven). ZTNA ise sizi ağa almaz; yalnızca yetkili olduğunuz *belirli uygulamaya*, kimlik ve cihaz doğrulamasından sonra, uygulama bazında bağlar. Ağ hiç görünmez kalır — buna bazen **dark network** veya uygulamaların gizlendiği yaklaşım denir.

### İstismar ve Savunma

**İstismar (Zero Trust'ın çözdüğü sorunlar):** Geleneksel modelde saldırgan bir VPN kimlik bilgisi çalarsa tüm iç ağa açılan kapıyı elde eder. Ele geçirilmiş bir kullanıcı hesabı, ağda serbestçe dolaşabilir. Zero Trust bu istismarı büyük ölçüde etkisizleştirir: çalınan kimlik bilgisi tek bir uygulamaya sınırlı erişim verir, cihaz sağlığı doğrulanmazsa erişim reddedilir, anormal davranış oturumu kesebilir.

**Savunma / Doğru Uygulama:** Zero Trust'ı bir ürün satın alarak "açmak" mümkün değildir; bu bir olgunlaşma yolculuğudur. Kimlik altyapısını (güçlü MFA, cihaz kimliği) sağlamlaştırmadan ağ tarafına geçmek temelsiz bir bina inşa etmektir. Erişim politikalarını sürekli değerlendirin; oturum bir kez açıldı diye sonsuza dek güvenmeyin (continuous verification). Ve **least privilege**'ı gerçekten uygulayın — çoğu "Zero Trust" projesi burada takılır, çünkü kimin neye ihtiyacı olduğunu haritalandırmak zahmetlidir ama vazgeçilmezdir.

## Yaygın Hatalar

Bu alandaki başarısızlıklar neredeyse her zaman aynı birkaç kalıptan gelir:

- **"Any-any" kuralları:** Firewall'a hızlı bir çözüm için konulan "her kaynak, her hedef, her port" izni. Genellikle geçici konur, kalıcı olur ve segmentasyonun tüm anlamını yok eder. Bir firewall kural setini denetlerken ilk aranan şey budur.
- **Egress'i unutmak:** İçeri gelen trafiği titizlikle kısıtlayıp dışarı gideni tamamen serbest bırakmak. Veri sızdırma ve C2 iletişimi tam bu boşluktan akar.
- **Düz iç ağ (flat network):** Perimeter'a milyonlar harcayıp iç ağı tek büyük VLAN olarak bırakmak. Perimeter'ı geçen saldırgan için ödül, korumasız bir iç dünyadır.
- **Kural birikmesi (rule sprawl) ve ölü kurallar:** Yıllar içinde biriken, artık hangi sistem için konduğu bilinmeyen yüzlerce kural. Kimse silmeye cesaret edemez, herkes ekler. Zamanla kural seti hem güvenlik açığı hem de operasyonel kâbus olur. Düzenli **kural denetimi (rule review)** şarttır.
- **VLAN'ı güvenlik sınırı sanmak:** VLAN'lar öncelikle bir *segmentasyon* aracıdır, tek başına *güvenlik* sınırı değildir. VLAN'lar arası trafik bir Layer 3 cihazda (firewall/router) kısıtlanmıyorsa, VLAN yalnızca broadcast domain'i böler, saldırganı durdurmaz. Ayrıca yanlış yapılandırılmış trunk portları VLAN hopping saldırılarına açık kapı bırakabilir.
- **Zero Trust'ı ürün sanmak:** "Zero Trust çözümü" satın alıp kurulumu bitince işin bittiğini sanmak. Zero Trust bir mimaridir ve kimlik olgunluğu olmadan hiçbir anlam ifade etmez.
- **Yönetim düzlemini (management plane) segmente etmemek:** Firewall, hypervisor ve switch yönetim arayüzlerinin genel ağdan erişilebilir olması. Saldırgan buraya ulaşırsa segmentasyonu bizzat kaldırabilir. Yönetim trafiği ayrı bir out-of-band ağda olmalıdır.

## En İyi Pratikler

- **Default deny'i her yönde uygulayın.** Hem ingress hem egress. İzin verilen her akışın bir gerekçesi ve sahibi olsun.
- **Least privilege'ı ağa taşıyın.** Her sistem yalnızca gerçekten ihtiyaç duyduğu komşularla, yalnızca gereken portlardan konuşsun. "Belki lazım olur" mantığı segmentasyonun düşmanıdır.
- **Defense in depth (derinlemesine savunma).** Tek bir firewall katmanına güvenmeyin. Perimeter, DMZ, iç segmentler ve mikrosegmentasyon üst üste binen katmanlar oluşturur; bir katman aşılsa bile diğerleri saldırganı yavaşlatır ve görünür kılar.
- **Önce haritalandırın, sonra kısıtlayın.** Özellikle mikrosegmentasyonda, mevcut trafik akışlarını gözlemleyip modellemeden kural yazmak uygulamaları kırar. Discovery → modelleme → allow-list → uygulama sırasını izleyin.
- **Kimlik/etiket tabanlı kurallar tercih edin.** Bulut ve konteyner ortamlarında IP tabanlı kurallar sürdürülemez. Kuralları rol ve etikete bağlayın.
- **Logla ve izle.** Segmentasyonun ikinci işlevi tespittir. Reddedilen trafiği, özellikle bölgeler arası ve egress denemelerini loglayın; bunlar genellikle ihlalin ilk sinyalidir. Bölgeler arası anormal bağlantı, düz ağda görünmeyen bir alarmdır.
- **Kuralları düzenli denetleyin.** Ölü kuralları temizleyin, any-any'leri daraltın, her kuralın hâlâ gerekli olduğunu doğrulayın. Kural seti yaşayan bir belgedir.
- **Yönetim düzlemini ayırın.** Yönetim erişimini out-of-band ve sıkı kontrollü tutun; buraya erişim tüm segmentasyonu iptal edebilir.
- **Kademeli ilerleyin.** Ne mikrosegmentasyon ne de Zero Trust bir gecede kurulur. En kritik varlıklardan (taç mücevherler) başlayıp dışa doğru genişleyin; ilk günden tüm ağı kilitlemeye çalışmak hem operasyonu kırar hem projeyi öldürür.

## Sonuç

Firewall ve segmentasyon aslında tek bir stratejik fikrin farklı çözünürlükteki ifadeleridir: **güveni azalt, sınırları çoğalt, her akışı gerekçelendir.** Default deny bu fikrin duruşudur; DMZ onu çevrede, mikrosegmentasyon çekirdekte uygular; Zero Trust ise güveni ağ konumundan söküp kimliğe bağlayarak fikri mantıksal sonucuna götürür.

Bu katmanların ortak hedefi çoğu zaman yanlış anlaşılır. Amaç ihlali *önlemek* değildir — ihlal er ya da geç olacaktır. Amaç, ihlalin **yayılamamasını**, hızla **görülmesini** ve **patlama yarıçapının küçük kalmasını** sağlamaktır. İyi segmente edilmiş bir ağda tek bir sunucunun düşmesi bir olay, kötü segmente edilmiş bir ağda ise bir felakettir. Aradaki farkı belirleyen, çoğu zaman görkemli bir teknoloji değil, disiplinli biçimde uygulanmış bu temel ilkelerdir.
