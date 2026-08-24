# OSINT Metodolojisi: Pasif Keşif, Kaynaklar, Sertifika Şeffaflığı, Dork ve Gizlilik

## Tanım

OSINT (Open Source Intelligence — Açık Kaynak İstihbarat), herkese açık, yasal olarak erişilebilir kaynaklardan bilgi toplama, ilişkilendirme ve analiz etme disiplinidir. Buradaki "açık kaynak" ifadesi yazılım dünyasındaki açık kaynak koddan farklıdır; kastedilen, gizli/sınıflandırılmış olmayan, halka açık her türlü veri kaynağıdır: web siteleri, DNS kayıtları, arama motoru indeksleri, sosyal medya, resmi siciller, sertifika günlükleri, sızıntı veritabanları ve daha fazlası.

Bir sızma testi (penetration test) veya kırmızı takım (red team) operasyonunda OSINT, keşif (reconnaissance) fazının bel kemiğidir. Savunma tarafında (blue team, tehdit istihbaratı) ise saldırganın sizin hakkınızda ne görebileceğini anlamak, yani kendi saldırı yüzeyinizi (attack surface) dışarıdan bir gözle görmek için kullanılır. OSINT'i güçlü kılan şey, bir sistemle doğrudan temas etmeden dahi, o sistem hakkında kayda değer bir resim çıkarabilmesidir.

Bu makale OSINT metodolojisini beş eksende inceler: pasif keşif mantığı, kaynak çeşitliliği ve güvenilirlik, Certificate Transparency (sertifika şeffaflığı), arama motoru dork'ları ve operasyonel gizlilik (OPSEC).

## Pasif Keşif ve Aktif Keşif Ayrımı

### Tanım ve kök neden

Keşif iki temel moda ayrılır. **Aktif keşif** hedef altyapıyla doğrudan paket alışverişi yapar: port taraması (port scan), servis banner'ı okuma, DNS sorgusunu doğrudan hedef isim sunucusuna gönderme, web uygulamasına HTTP isteği atma. **Pasif keşif** ise hedefle hiç temas etmeden, üçüncü taraf kaynaklar üzerinden bilgi toplar: arama motoru önbellekleri, üçüncü taraf DNS veri sağlayıcıları, sertifika günlükleri, WHOIS arşivleri, sosyal medya.

Ayrımın kök nedeni **iz bırakma** meselesidir. Aktif keşifte gönderdiğiniz her paket hedefin log kayıtlarına, IDS/IPS (saldırı tespit/önleme sistemi) sensörlerine ve SIEM korelasyon motorlarına düşer. Kaynak IP adresiniz, atadığınız istek deseni, tarama hızınız hepsi görünür bir imzadır. Pasif keşifte ise hedef sizin varlığınızdan haberdar olmaz çünkü onunla asla konuşmazsınız; aradaki katman olan üçüncü tarafla konuşursunuz. Örneğin bir alan adının alt alan adlarını (subdomain) öğrenmek için hedefin DNS sunucusuna binlerce sorgu göndermek yerine, Certificate Transparency günlüklerinden geçmişte o alan adı için verilmiş sertifikaları okursanız hedef bunu asla göremez.

### Çalışma mantığı: neden pasif keşif işe yarar

Modern internet altyapısı, veriyi doğal olarak çoğaltır ve kalıcılaştırır. Bir alan adı için TLS sertifikası aldığınızda bu sertifika halka açık günlüklere yazılır. Bir sunucu kurduğunuzda IP'niz zamanla tarama servislerinin (internet çapında sürekli tarama yapan platformlar) veritabanına girer. Bir çalışanınız LinkedIn'e teknoloji yığınınızı yazdığında bu bilgi indekslenir. Pasif keşif, tam olarak bu "sızıntı yoluyla kamuya açılmış" veri okyanusunu hasat eder. İşin özü şudur: bilgi zaten dışarıda bir yerde durmaktadır; pasif OSINT sadece onu toplar ve birleştirir.

### Somut örnek

Diyelim ki `ornek-sirket.com` alan adını hedefliyorsunuz ve tek bir paket bile göndermek istemiyorsunuz. Pasif akış şöyle işleyebilir:

1. WHOIS ve tarihsel WHOIS arşivlerinden alan adının kayıt tarihini, (maskelenmemişse) kayıt sahibi e-postasını ve isim sunucularını çıkarırsınız.
2. Certificate Transparency günlüklerinden `*.ornek-sirket.com` için verilmiş tüm sertifikaları çeker, böylece `vpn.`, `mail.`, `test-panel.` gibi alt alan adlarını hedefe hiç sormadan öğrenirsiniz.
3. Arama motoru dork'larıyla açıkta kalmış dosyaları, dizin listelemelerini, yönetim panellerini indeks üzerinden bulursunuz.
4. İnternet çapında tarama yapan servislerin geçmiş verisinden bu alan adına ait IP'lerde hangi portların/servislerin açık göründüğünü, hedefe dokunmadan, o servisin kaydından okursunuz.
5. Kod deposu platformlarında sızmış API anahtarlarını veya iç yapıya dair referansları ararsınız.

Bu beş adımın hiçbiri `ornek-sirket.com` sunucularına bir istek göndermez, ama sonunda elinizde bir alt alan adı haritası, olası açık servisler ve muhtemel giriş noktaları listesi olur.

### İstismar mantığı ve savunma birlikte

**Saldırgan tarafı:** Pasif keşifle toplanan alt alan adları, saldırı yüzeyinin en verimli genişleme yoludur. Kurumlar ana sitelerini sıkı korurken unutulmuş bir `eski-test.ornek-sirket.com` sunucusu yamalanmamış (unpatched) halde durabilir. Subdomain takeover (alt alan adı devralma) da burada doğar: DNS'te CNAME kaydı hâlâ artık var olmayan bir bulut kaynağına işaret ediyorsa, saldırgan o kaynağı kendi adına oluşturup alt alan adını ele geçirebilir.

**Savunma tarafı:** Aynı pasif teknikleri savunma için kullanmak zorundasınız. Kendi Certificate Transparency günlüklerinizi düzenli izleyin; adınıza beklenmedik bir sertifika verildiyse bu ya bir yanlış yapılandırma ya da bir saldırı işaretidir. Envanterinizde olmayan ama dışarıdan görünen alt alan adlarını tespit edip kapatın (attack surface management). Ölü DNS kayıtlarını (dangling DNS) düzenli temizleyerek subdomain takeover riskini kesin. Kritik nokta: saldırganın gördüğünü siz de görmelisiniz, çünkü pasif keşif verisi çift taraflı bir aynadır.

## Kaynaklar ve Kaynak Güvenilirliği

### Neden kaynak çeşitliliği ve doğrulama şart

OSINT'in en büyük tuzağı, tek kaynağa güvenmektir. Açık kaynak veriler eskir, çelişir ve kasıtlı olarak kirletilebilir (disinformation). Bir WHOIS kaydı bir yıl önceki gerçeği yansıtabilir; bir DNS önbelleği eski bir IP gösterebilir; bir sosyal medya profili tuzak (honeypot) olabilir. Bu yüzden OSINT metodolojisinin kalbinde **çapraz doğrulama** (cross-verification) yatar: aynı bulguyu birbirinden bağımsız en az iki kaynakta teyit etmeden onu "gerçek" saymazsınız.

### Kaynak kategorileri

Uzman bir analist kaynakları katmanlar halinde düşünür:

- **Ağ ve altyapı katmanı:** DNS kayıtları, tarihsel DNS (passive DNS — üçüncü tarafların zaman içinde topladığı çözümleme kayıtları), WHOIS ve tarihsel WHOIS, IP tahsis kayıtları (RIR verileri), ASN bilgisi. Passive DNS özellikle değerlidir çünkü bir IP'nin geçmişte hangi alan adlarını barındırdığını gösterir; bu, altyapı ilişkilerini ortaya çıkarır.
- **Sertifika katmanı:** Certificate Transparency günlükleri (ayrı başlıkta detaylı).
- **İçerik katmanı:** Arama motoru indeksleri, web arşivleri (sayfaların tarihsel kopyaları), önbellekler. Web arşivi, silinmiş ama arşivlenmiş bir yapılandırma dosyasını ortaya çıkarabildiği için çok kıymetlidir.
- **İnsan katmanı:** Sosyal medya, profesyonel ağlar, konferans konuşmaları, iş ilanları. İş ilanları bir kurumun teknoloji yığınını sızdırır: "X teknolojisinde 5 yıl deneyim aranıyor" ifadesi, o kurumun X'i kullandığını doğrudan söyler.
- **Kod ve sır katmanı:** Herkese açık kod depoları, paket kayıtları, yanlışlıkla commit edilmiş kimlik bilgileri (credentials), yapılandırma dosyaları.
- **Sızıntı katmanı:** Halka açılmış ihlal (breach) veritabanları. Bir e-postanın geçmişte hangi sızıntılarda yer aldığını gösteren servisler, parola yeniden kullanımı (password reuse) saldırıları için başlangıç noktası olur.

### Somut örnek: kaynakların birleşimi

Bir kimlik avı (phishing) kampanyasının arkasındaki altyapıyı analiz ettiğinizi düşünün. Şüpheli alan adının IP'sini passive DNS'ten alırsınız; aynı IP'de barınan diğer alan adlarını çıkarırsınız (bu, saldırganın diğer kampanyalarını ortaya döker); o alan adlarının Certificate Transparency kayıtlarından ortak bir sertifika deseni yakalarsınız; WHOIS'ten ortak bir kayıt e-postası veya isim sunucusu bulursunuz. Tek başına her ipucu zayıftır, ama dört kaynağın kesişimi güçlü bir atıf (attribution) örüntüsü oluşturur.

### Yaygın hata ve en iyi pratik

En yaygın hata, bir aracın çıktısını sorgusuz kabul etmektir. Araçlar önbellekten çalışır ve önbellek eskir. En iyi pratik: her bulguya bir **güven derecesi** ve bir **zaman damgası** atayın. "Bu IP şu an aktif" demeyin; "bu kaydın son güncellenme tarihi şudur, dolayısıyla güven derecem ortadır" deyin. Ayrıca kaynağın kaynağını sorgulayın: bir toplayıcı servis veriyi nereden alıyor, ne sıklıkla tazeliyor?

## Certificate Transparency (Sertifika Şeffaflığı)

### Tanım

Certificate Transparency (CT), TLS sertifikalarının halka açık, yalnızca-ekleme (append-only) günlüklerine kaydedilmesini sağlayan bir sistemdir. Bir sertifika otoritesi (Certificate Authority — CA) bir sertifika verdiğinde, bu sertifika bir veya daha fazla CT günlüğüne yazılır ve bu kayıt kriptografik olarak kalıcı hale gelir. Amaç, hatalı veya kötü niyetli verilmiş sertifikaların gizli kalamamasıdır.

### Kök neden: CT neden var

CT'nin doğuş sebebi, geçmişte yaşanan CA ihlalleridir. Bir CA ele geçirildiğinde veya hata yaptığında, alan adı sahibinin haberi olmadan onun adına sahte sertifika üretilebiliyordu; bu da ortadaki adam (man-in-the-middle) saldırılarına kapı açıyordu. CT'nin çözümü şudur: eğer verilen her sertifika halka açık bir günlüğe düşerse, alan adı sahibi kendi adına verilmiş beklenmedik sertifikaları tespit edebilir. Yani CT bir **hesap verebilirlik** mekanizmasıdır; güvenliği "önle" mantığıyla değil, "her şeyi görünür kıl, kötüyü yakala" mantığıyla sağlar. Modern tarayıcılar, halka açık güvenilen bir sertifikanın CT günlüğüne kaydedilmiş olmasını (SCT — Signed Certificate Timestamp aracılığıyla) genellikle zorunlu tutar.

### OSINT açısından neden bir altın madeni

CT günlükleri OSINT için paha biçilmezdir çünkü **hedefe hiç dokunmadan** onun alt alan adlarını ifşa ederler. Bir kurum `wildcard` yerine her servis için ayrı sertifika alıyorsa, `intranet.ornek-sirket.com`, `vpn-test.ornek-sirket.com`, `odeme-staging.ornek-sirket.com` gibi isimlerin hepsi CT günlüklerinde yazılıdır. Saldırgan bu günlükleri tarayarak kurumun tüm dijital ayak izini, tek bir DNS sorgusu yapmadan çıkarabilir. Özellikle "staging", "dev", "test", "old" gibi ön ekler taşıyan alt alan adları, çoğu zaman en zayıf korunan sistemlerdir ve CT günlükleri bunları açık eder.

### Somut örnek

Bir saldırgan, hedefin ana sitesinde hiçbir zafiyet bulamamış olsun. CT günlüklerini sorgulayarak `beta-panel.ornek-sirket.com` adlı, ana envanterde unutulmuş bir alt alan adı keşfeder. Bu panel eski bir sürüm çalıştırmaktadır ve varsayılan kimlik bilgileriyle korunmaktadır. Saldırgan CT sayesinde bu kapıyı, hedefin altyapısını hiç taramadan bulmuştur.

### İstismar mantığı ve savunma

**Saldırgan tarafı:** CT, saldırı yüzeyi keşfinin en hızlı yoludur. Ayrıca, henüz yayına alınmamış bir servisin sertifikası CT'ye düştüğünde, saldırgan o servisin varlığını lansmandan önce öğrenebilir; bu bir bilgi sızıntısıdır.

**Savunma tarafı:** CT sizin de en güçlü erken uyarı aracınızdır. Kendi alan adlarınız için **CT monitoring** kurun; adınıza yeni bir sertifika verildiğinde bildirim alın. Bu, iki kritik senaryoyu yakalar: birincisi, birinin sizin adınıza sahte sertifika aldığı bir saldırı; ikincisi, gölge BT (shadow IT) — bir ekibin merkezî onaydan geçmeden yayına aldığı bir servis. CT monitoring'i attack surface management ile birleştirin; günlüklerden çıkan her yeni isim ya envanterinizde olmalı ya da soruşturulmalıdır. Ek olarak, CT'nin sunduğu görünürlüğü kabul edin ve alt alan adı isimlerinizi "güvenlik için gizlilik" (security through obscurity) varsayımıyla seçmeyin; `test`, `admin`, `internal` gibi isimler zaten günlüklerde görünecektir, dolayısıyla asıl korumayı kimlik doğrulama ve ağ segmentasyonu sağlamalıdır.

## Arama Motoru Dork'ları (Google Dorking)

### Tanım

Dork, arama motorlarının gelişmiş operatörlerini kullanarak sıradan bir aramanın ulaşamayacağı hassas bilgileri indeks üzerinden bulma tekniğidir. "Google dorking" veya "Google hacking" olarak da bilinir, ama aynı mantık indeks tabanlı tüm arama motorları için geçerlidir. Operatörler, aramayı belirli bir alan adına, dosya türüne, URL desenine veya sayfa başlığına daraltmanızı sağlar.

Yaygın operatör aileleri şunlardır (kavramsal olarak, motordan motora sözdizimi değişebilir):

- **Alan adı daraltma:** Aramayı tek bir alan adıyla sınırlayan operatör (ör. `site:` mantığı).
- **Dosya türü daraltma:** Belirli uzantıdaki dosyaları getiren operatör (ör. `filetype:` mantığı). PDF, konfigürasyon, yedek, elektronik tablo dosyaları için kullanılır.
- **URL/başlık deseni:** URL'de veya sayfa başlığında belirli bir kelimeyi arayan operatörler (ör. `inurl:`, `intitle:` mantığı). Yönetim panellerini, dizin listelemelerini ve giriş sayfalarını bulmakta etkilidir.

### Kök neden: dork neden çalışır

Dork'un işe yaramasının kök nedeni, **yanlış yapılandırma ve arama motoru indekslemesinin buluşmasıdır**. Bir sunucu dizin listelemesini açık bırakırsa, kimlik doğrulama koymadan bir yönetim panelini yayına alırsa, ya da hassas bir dosyayı web köküne koyup `robots.txt` ile "gizlemeye" çalışırsa, arama motoru botu er ya da geç bu içeriği tarar ve indeksler. Dork, indekslenmiş bu hataları hedefli sorgularla süzer. Yani dork bir "hacking" değil, aslında halka zaten açılmış içeriğin akıllıca sorgulanmasıdır. Önemli bir yanılgıyı düzeltmek gerekir: `robots.txt` dosyasına bir yolu yazmak onu gizlemez; aksine, o dosya herkese açıktır ve saldırganlara "işte gizlemeye çalıştığım hassas yollar" listesini sunar.

### Somut örnek

Bir kurumun açık kaldığından şüphelendiğiniz yedek dosyalarını aramak için, o kurumun alan adıyla sınırlı bir aramayı belirli yedek/veritabanı uzantılarıyla birleştirirsiniz. Dizin listelemesi açık sunucuları bulmak için, sayfa başlığında tipik dizin-listeleme ifadesini arayan bir sorgu kurarsınız. Giriş panellerini bulmak için, URL'de `admin`, `login`, `panel` gibi kelimeleri, hedef alan adı sınırıyla birlikte ararsınız. Bu sorguların hiçbiri hedefe istek atmaz; hepsi arama motorunun indeksinde çalışır, bu yüzden tamamen pasiftir.

### İstismar mantığı ve savunma

**Saldırgan tarafı:** Dork'lar, düşük maliyetle yüksek değerli bulgular sağlar: açıkta kalmış yapılandırma dosyaları, veritabanı yedekleri, kimlik bilgileri, iç dokümanlar, kimlik doğrulaması olmayan paneller. Toplu (bulk) dork listeleriyle geniş bir hedef kümesi taranarak "asılı meyveler" hızla toplanabilir.

**Savunma tarafı:** İlk savunma, indekslememeyi engellemek değil, **açıkta hassas içerik bırakmamaktır**. Dizin listelemesini kapatın, yönetim panellerini kimlik doğrulama ve IP kısıtlaması arkasına alın, yedek ve yapılandırma dosyalarını web kökünden çıkarın. `robots.txt`'ye hassas yolları yazarak gizlendiğinizi sanmayın. Proaktif olarak, kendi kurumunuza dork uygulayın: saldırganın bulacağı şeyi önce siz bulun ve kapatın. Arama motorlarının sunduğu kaldırma araçlarıyla yanlışlıkla indekslenmiş içeriği kaldırtabilirsiniz, ama asıl kök çözüm içeriği kaynakta korumaktır; indeksten kaldırmak, içerik hâlâ erişilebilir olduğu sürece yalnızca yüzeysel bir düzeltmedir.

## Operasyonel Gizlilik (OPSEC)

### Tanım ve neden kritik

OPSEC (Operational Security), OSINT çalışmasını yürütürken **kendi izlerinizi ve kimliğinizi** koruma disiplinidir. Paradoks şudur: siz hedef hakkında istihbarat toplarken, hedef de dikkatliyse sizin hakkınızda istihbarat toplayabilir. Aktif keşifte kaynak IP'niz görünür; hatta pasif zannettiğiniz bazı eylemler (bir bağlantıya tıklamak, bir profili ziyaret etmek, bir belge açmak) hedefe sinyal gönderebilir. OPSEC'in kök nedeni, keşfin çift yönlü olmasıdır.

### Çalışma mantığı ve somut riskler

Birkaç somut sızıntı örneği OPSEC'in neden önemli olduğunu gösterir:

- **Referrer sızıntısı:** Bir sosyal ağ profilinden hedefin sitesine tıklarsanız, ziyaretiniz hedefin loglarına belirli bir kaynak bilgisiyle düşebilir. Analiz için ziyaret ettiğiniz şey, sizin varlığınızı ele verir.
- **Tuzak belgeler ve web işaretçileri (canary/beacon):** Hedef, sızdırdığını düşündürdüğü bir belgeye görünmez bir izleme pikseli koymuş olabilir. Belgeyi açtığınızda IP'niz ve zaman bilgisi hedefe gider. Bu yüzden analistler bilinmeyen belgeleri izole ve ağdan yalıtılmış ortamlarda açar.
- **Sorgu deseni:** Bazı toplayıcı servisler, kime baktığınızı kaydeder veya hedefe sinyal verebilir. Kendi altyapınızdan yoğun ve tekdüze sorgu atmak, sizi profillenebilir kılar.
- **Sahte kimlik (sockpuppet) hijyeni:** Sosyal medya keşfi için kullanılan araştırma hesapları, gerçek kimliğinizle ilişkilendirilebilecek hiçbir sinyal taşımamalıdır. Aynı telefon numarası, aynı fotoğraf, aynı yazım alışkanlığı bir hesabı gerçek kimliğinize bağlayabilir.

### İstismar mantığı ve savunma birlikte

Burada roller ilginç biçimde tersine döner. **Savunmacı gözüyle**, kendi loglarınızı OSINT karşıtı bir sensör olarak kullanabilirsiniz: sitenize gelen olağandışı kaynaklı ziyaretler, CT günlüğü sorguları, WHOIS erişim desenleri bir keşif fazının işareti olabilir. Tuzak belgeler (honeytoken) yerleştirerek, biri iç dosyalarınıza eriştiğinde uyarı alabilirsiniz.

**Analist/kırmızı takım gözüyle**, OPSEC şu prensiplere dayanır: keşif kimliğinizi gerçek kimliğinizden ayırın; pasif kaynakları hedefe sinyal göndermeyecek şekilde tercih edin; bilinmeyen içerikleri yalıtılmış ortamda açın; ve en önemlisi, **yetki sınırları** içinde kalın. OSINT çoğu zaman yasaldır çünkü açık kaynak kullanır, ancak toplanan verinin kullanımı, saklanması ve özellikle kişisel verilerin işlenmesi hukuki ve etik sınırlara tabidir.

### Gizliliğin etik ve hukuki boyutu

OSINT'in gücü aynı zamanda tehlikesidir. Bireyler hakkında açık kaynaklardan derlenen parçalı bilgiler birleştirildiğinde, tek başına zararsız verilerden mahremiyet ihlali doğabilir (mozaik etkisi). Bu yüzden metodolojik OSINT, "erişilebilir olması yapmanın meşru olduğu anlamına gelmez" ilkesiyle çalışır. Bir sızma testinde kapsam (scope) ve yazılı yetkilendirme (rules of engagement) OSINT'i de kapsamalıdır; kişisel verilerin toplanması, saklanması ve raporlanması ilgili veri koruma mevzuatına (ör. genel veri koruma düzenlemeleri) uygun olmalıdır. Bir savunmacı olarak da, kendi çalışanlarınız hakkında dışarıda ne kadar veri bulunduğunu bilmek ve gerektiğinde farkındalık eğitimi vermek, bu mozaik etkisini yönetmenin parçasıdır.

## Yaygın Hatalar

- **Tek kaynağa güvenmek.** Eskimiş ya da kirletilmiş bir veriyi doğrulamadan gerçek saymak, tüm analizi zehirler. Her bulguyu bağımsız ikinci bir kaynakla teyit edin.
- **Pasif zannedip aktif iz bırakmak.** Bazı araçlar arka planda hedefe doğrudan istek atar. Aracın gerçekten pasif mi çalıştığını, verisini üçüncü taraftan mı yoksa hedeften mi aldığını bilmeden "pasifim" demeyin.
- **Zaman damgasını göz ardı etmek.** Bir IP, alt alan adı veya kayıt bugün geçerli olmayabilir. Verinin ne zaman toplandığını bilmeden karar vermeyin.
- **`robots.txt` ve gizlilikle güvenlik yanılgısı.** Bir yolu gizlemek koruma değildir; koruma kimlik doğrulama ve yetkilendirmedir. CT günlükleri ve indeksler zaten isimlerinizi açık eder.
- **OPSEC'i ihmal etmek.** Kendi kimliğinizi korumadan yürütülen keşif, hedefe sizi tanıtabilir ve operasyonu ya da analisti riske atar.
- **Yetki ve etik sınırı aşmak.** Verinin açık olması, onu toplamanın ve kullanmanın her koşulda meşru olduğu anlamına gelmez. Kapsam ve mevzuat sınırlarını netleştirin.
- **Otomasyona körü körüne güvenmek.** Araç çıktısı önbellekten gelir, gürültü içerir ve yanlış pozitif üretir. İnsan analizi ve bağlam, aracın yerini tutamaz.

## En İyi Pratikler

- **Pasifle başla, aktife dikkatli geç.** Önce hedefe hiç dokunmadan CT, passive DNS, WHOIS, arşiv ve dork ile mümkün olan her şeyi topla; aktif adımlara ancak yetkin ve gerekliyse, iz bırakacağını bilerek geç.
- **Her bulguya güven derecesi ve zaman damgası ata.** Analizin değeri, bulguların ne kadar taze ve ne kadar doğrulanmış olduğuyla ölçülür.
- **Çapraz doğrulamayı kural yap.** İki bağımsız kaynakta teyit edilmemiş hiçbir bulgu kesin değildir.
- **Kendi kurumuna saldırganın gözüyle bak.** CT monitoring kur, düzenli dork ve alt alan adı keşfi yap, dangling DNS kayıtlarını temizle, attack surface management uygula. Savunma, saldırganın gördüğünü önce görmekle başlar.
- **OPSEC'i baştan planla.** Keşif kimliğini gerçek kimlikten ayır, bilinmeyen içerikleri yalıt, sinyal sızdıran eylemlerden kaçın.
- **Bulguları eyleme çevir.** OSINT'in amacı liste üretmek değil, karar vermektir: hangi alt alan adı kapatılmalı, hangi panel korunmalı, hangi sertifika soruşturulmalı, hangi sızmış kimlik bilgisi döndürülmeli (rotate).
- **Yasal ve etik çerçeveyi koru.** Yetkilendirme, kapsam ve veri koruma mevzuatı OSINT çalışmasının ayrılmaz parçasıdır; teknik yetkinlik hukuki disiplini ikame etmez.

## Kapanış

OSINT metodolojisinin özü tek bir cümlede toplanır: **bilgi zaten dışarıda, mesele onu görebilmek ve ilişkilendirebilmektir.** Pasif keşif iz bırakmadan geniş bir resim çıkarır; çeşitli kaynaklar çapraz doğrulamayla güvenilir hale gelir; Certificate Transparency saldırı yüzeyini hem saldırgana hem savunmacıya açar; dork'lar yanlış yapılandırmaları indeks üzerinden ifşa eder; OPSEC ise bu gücü kullanırken analisti korur. Uzman yaklaşımı, bu tekniklerin hepsini bir savunma refleksine çevirmektir: saldırganın sizin hakkınızda toplayabileceği her veriyi önce siz toplayın, doğrulayın ve kapatın.
