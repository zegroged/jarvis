# Kimlik Odaklı Tespit ve Identity Threat Detection and Response (ITDR)

## Giriş: Neden Kimlik Katmanı Yeni Savaş Alanı

Klasik saldırı anlatısında kötü adam bir zafiyet bulur, exploit yazar, bir makineye kod çalıştırır. Bu hâlâ olur, ama modern kurumsal ortamda -özellikle bulut kimlik sağlayıcıları (Azure AD / Entra ID, Okta, Ping, vb.) merkeze oturduğundan beri- en verimli saldırı yolu artık "bir kimliği çalmak ve onunla giriş yapmak" hâline geldi. Sebebi basit bir ekonomi: MFA yorgunluğu, token çalma, oturum ele geçirme (session hijacking) gibi teknikler, bir 0-day bulup silahlandırmaktan çok daha ucuz, çok daha az iz bırakan ve "meşru kullanıcı gibi görünme" avantajı sunan yöntemler. Saldırgan login olduğunda EDR'in gördüğü şey bir malware değil, geçerli bir oturum açmadır (login event). Bu da savunmayı endpoint/network katmanından kimlik katmanına taşımayı zorunlu kılar.

On-premise Active Directory dünyasında Kerberoasting, Pass-the-Hash, Golden Ticket gibi teknikler çok iyi belgelenmiş; bunların AD iç ağında nasıl çalıştığı bilinir. Ama bu teknikleri "bulut kimlik katmanında TESPİT etme" tarafı ayrı bir disiplin: çünkü bulut kimlik sağlayıcısı (IdP) kendi log şemasına, kendi risk motoruna, kendi anomalilik tanımlarına sahip. Bir SOC analisti Azure AD sign-in log'unu okuyamıyorsa ya da Okta'nın ThreatInsight sinyalini anlamlandıramıyorsa, saldırgan token'ı çalıp kurumsal e-postaya, SharePoint'e, hatta CI/CD pipeline'ına VPN'siz, zafiyetsiz, sadece "geçerli oturum açma" ile girer. Bu makale, bu tespit disiplinini -Identity Threat Detection and Response (ITDR)- savunmacı gözüyle ele alıyor.

## Kök Neden: Kimlik Neden Yeni Çevre (Perimeter)

Geleneksel güvenlik modeli "ağ çevresi" (network perimeter) üzerine kuruluydu: firewall dışarıyı, VPN içerdekini tanımlıyordu. Bulut ve uzaktan çalışma bu sınırı eritti. Artık kullanıcılar her yerden, her cihazdan bağlanıyor; kaynaklar SaaS uygulamalarında. Bu durumda "kim olduğunu kanıtlayan şey" (kimlik doğrulama - authentication ve onu takip eden oturum/token) tek gerçek sınır hâline geldi. Zero Trust felsefesinin "never trust, always verify" ilkesi de tam bunun üzerine kurulu: ağdaki konum güven vermez, kimlik ve context (cihaz durumu, konum, risk skoru) güven verir.

Bunun sonucu: saldırganlar da stratejilerini kaydırdı. "Identity is the new perimeter" çok tekrarlanan bir slogan ama arkasındaki mantık sağlam: eğer bir saldırgan geçerli bir kullanıcı adı + parola + (mümkünse) MFA onayı ya da geçerli bir oturum token'ı elde ederse, o noktadan sonra sistem onu "meşru kullanıcı" olarak işler. EDR/AV bu noktada körleşir çünkü ortada çalıştırılan zararlı bir binary yoktur -sadece bir web login'i veya bir API çağrısı vardır. Bu yüzden tespit sorumluluğu network/endpoint katmanından **kimlik sağlayıcısının (IdP) telemetrisine** kayar: sign-in log'ları, risk skorları, conditional access karar kayıtları, token yaşam döngüsü olayları.

## Temel Kavramlar ve Mimari

### Azure AD / Entra ID Sign-in Modeli

Entra ID (eski adıyla Azure AD), her kimlik doğrulama girişimini bir **sign-in log** kaydı olarak tutar. Bu kayıt sadece "başarılı/başarısız" değil, zengin bir context taşır: kullanıcı, uygulama, IP adresi, coğrafi konum (IP'den türetilmiş), cihaz bilgisi (uyumlu mu, kayıtlı mı), kimlik doğrulama yöntemi (parola, MFA, FIDO2 vb.), conditional access politikalarının sonucu, ve **risk seviyesi** (Identity Protection tarafından hesaplanan).

Identity Protection (Entra ID P2 özelliği), makine öğrenmesi tabanlı sinyallerle iki tür risk üretir:
- **Risky sign-in (oturum bazlı risk)**: o anki giriş girişiminin anomalik olduğu (örnek: anonim IP, atipik seyahat, bilinen kötü amaçlı IP, token replay belirtisi).
- **Risky user (kullanıcı bazlı risk)**: kullanıcının kimlik bilgilerinin sızdırılmış olabileceğine dair birikimli sinyal (örnek: leaked credentials listelerinde görülmüş parola).

Bu ikisi farklı şeylerdir ve karıştırılmamalıdır: risky sign-in anlık bir olayı, risky user zaman içinde biriken bir itibar/güven skorunu ifade eder.

### Okta Tarafında Eşdeğer Kavramlar

Okta'da benzer işlevi **System Log (Sysevents)** ve **ThreatInsight** ile **Okta Behavior Detection** üstlenir. System Log her authentication, MFA challenge, policy değerlendirmesi gibi olayı kayıt altına alır (`eventType`, `outcome`, `client.geographicalContext`, `client.device`, `securityContext.isProxy` gibi alanlarla). Behavior Detection ise "yeni cihaz", "yeni konum", "yeni IP", "imkansız seyahat" gibi davranışsal sapmaları işaretler ve bunları politika kurallarında (örnek: "eğer yeni konum + yeni cihaz ise MFA'yı zorunlu kıl") kullanılabilir hale getirir.

Kavramsal olarak her iki platform da aynı üç bileşene dayanır:
1. **Zengin telemetri** (kim, ne zaman, nereden, hangi cihazdan, hangi yöntemle).
2. **Bir risk/anomali motoru** (kural tabanlı + istatistiksel/ML tabanlı).
3. **Politika uygulama noktası** (Conditional Access / Okta Sign-On Policy) - riski gördükten sonra ne yapılacağına karar veren mekanizma (ek MFA iste, engelle, oturumu kısalt).

## İmkansız Seyahat (Impossible Travel) Tespiti - Çalışma Mantığı

### Kavram

İmkansız seyahat, aynı kullanıcı hesabının kısa bir zaman aralığında, fiziksel olarak ulaşılması imkansız iki farklı coğrafi konumdan giriş yapması durumudur. Örnek: kullanıcı saat 09:00'da İstanbul'dan giriş yapıyor, saat 09:20'de Sao Paulo'dan giriş yapıyor. Uçak yolculuğu bile bu süreyi karşılayamayacağından, bu iki oturumdan en az biri (genelde ikinci) meşru değildir - büyük ihtimalle çalınmış kimlik bilgisi veya çalınmış token uzak bir yerden kullanılıyordur.

### Nasıl Çalışır (Kavramsal)

Motor, her başarılı girişin IP adresinden bir coğrafi konum (lat/long) çıkarır (IP geolocation veritabanı ile). Sonra aynı kullanıcının önceki başarılı girişiyle karşılaştırır: iki nokta arası mesafe / geçen süre = gerekli ortalama hız hesaplanır. Bu hız, gerçekçi bir ulaşım yöntemiyle (uçak dahil) aşılamayacak kadar yüksekse (örnek: 1000+ km/saat), sinyal tetiklenir.

Gerçek üretim sistemleri bunu saf mesafe/hız hesabından daha zengin yapar:
- **VPN/proxy/anonimleştirici tespiti** ile yanlış pozitifleri azaltır (kurumsal VPN çıkış noktası değişimi imkansız seyahat gibi görünebilir).
- **Bilinen/güvenilir konum listesi** (named locations) tanımlanarak şirket ofisleri, bilinen VPN çıkışları hariç tutulur.
- **Cihaz/tarayıcı parmak izi** ile aynı "kullanıcı" farklı cihazdan mı geliyor kontrol edilir - aynı cihazdan farklı konum, farklı anlam taşır.
- Microsoft'un Identity Protection'ı bunu "atypical travel" adı altında ayrı bir risk tespiti olarak sunar ve kullanıcının **geçmiş giriş alışkanlıklarına** (öğrenilmiş konum/cihaz modeli) göre anomalik olanı belirler - sadece iki nokta arası değil, kullanıcıya özel bir baseline.

### Tespit - Pratik Uygulama

- **Entra ID**: Identity Protection > Risky sign-ins raporunda "Atypical travel" risk detection type'ı filtrelenir. `SigninLogs` tablosunda (Log Analytics / Sentinel) `RiskDetail`, `RiskLevelDuringSignIn`, `Location`, `IPAddress` alanları üzerinden KQL sorgusu ile aynı kullanıcı için ardışık girişler arasındaki konum/zaman farkı hesaplanabilir.
- **Okta**: System Log'da `security.threat.detected` veya behavior sinyalleri (`New Geolocation`, `Velocity` behavior) filtrelenir; `client.geographicalContext` alanları zaman serisi olarak karşılaştırılır.
- **SIEM tarafında genel yaklaşım**: kullanıcı bazında son N başarılı giriş kaydını tut, her yeni girişte önceki ile mesafe/süre oranı hesapla, eşik değeri aşanı alarm üret. Bu mantığı kendi Sentinel/Splunk/Elastic korelasyon kuralınla da yazabilirsin - IdP'nin yerleşik özelliğine bağlı kalmak zorunda değilsin.

### Yaygın Hatalar / Yanlış Pozitif Kaynakları

- Kurumsal **çıkış proxy'sinin** (örnek: bulut güvenlik geçidi - CASB/SWG) dinamik olarak çıkış IP'sini değiştirmesi, tüm kullanıcılarda toplu yanlış alarm üretebilir. Named location ve bilinen ASN/IP aralığı listeleri bu gürültüyü azaltır.
- **Mobil operatörlerin carrier-grade NAT'ı** yüzünden IP tabanlı geolocation hatalı olabilir; cihaz sinyali (compliant device, hybrid join) ile çapraz doğrulama şarttır.
- Sadece "iki nokta arası hız" hesaplayıp **baseline/öğrenme olmadan** sabit eşik kullanmak - gerçek kullanıcı davranışını modellemeyen kaba kurallar hem çok fazla gürültü hem de kaçırılan gerçek vaka üretir.

## Oturum Ele Geçirme (Session Hijacking) ve Token Replay Tespiti

### Kavram ve Kök Neden

MFA yaygınlaştıkça saldırganlar doğrudan parola + MFA kodu çalmak yerine, **kimlik doğrulama tamamlandıktan SONRA** oluşan oturum token'ını (session token, refresh token, cookie) çalmaya yöneldi. Bunun kök nedeni şu: MFA sadece "authentication" anını korur; ama authentication sonrası verilen token, tipik olarak saatler/günler boyunca geçerlidir ve o token'ı elinde tutan herkes, MFA'yı tekrar yapmadan sistemi kullanabilir. Yani **token, kimliğin kendisi haline gelir**. Bu teknikler genellikle "Adversary-in-the-Middle" (AiTM) phishing kitleri (örnek: ters proxy tabanlı phishing sayfaları) veya tarayıcı/cihaz üzerindeki bir kötü amaçlı yazılım aracılığıyla token/cookie'yi çalarak çalışır; çalınan token başka bir cihaza/IP'ye taşınıp orada "replay" edilir (yeniden kullanılır).

Bu, klasik "parola çalma" tehdit modelinden farklıdır: MFA dahi bu senaryoda tek başına yeterli koruma değildir, çünkü saldırgan MFA'yı atlatmıyor, MFA'nın ürettiği *sonucu* (geçerli oturumu) çalıyor.

### Nasıl Çalışır (Kavramsal) ve Tespit Sinyalleri

Token replay'i tespit etmenin mantığı, çalınan token'ın **orijinal oluşturulduğu bağlamdan farklı bir bağlamda kullanıldığını** yakalamaktır:

- **Token/oturum özellikleri tutarsızlığı**: Token bir IP/cihaz/tarayıcıdan alındı, ama farklı bir IP/cihaz/konumdan kullanıldı. Entra ID'de bu **"token protection" / "sign-in session token binding"** kavramıyla ilişkilidir - token'ı belirli bir cihaza kriptografik olarak bağlayarak (device-bound tokens) çalınan token'ın başka bir makinede işe yaramamasını sağlama yaklaşımı.
- **Impossible travel benzeri ama oturum-içi versiyon**: aynı oturum ID'sinin çok kısa sürede farklı coğrafi konumlardan API çağrısı yapması.
- **Anomalik kullanım deseni**: token normalde interaktif tarayıcı trafiğinde görülüyorken, anında otomatize/script benzeri istek paternine (User-Agent değişimi, hızlı ardışık API çağrısı, olağandışı Graph API kullanımı - örnek MailboxSettings, mail arama, forwarding kural oluşturma gibi post-compromise davranışlar) dönüşmesi.
- **"Continuous Access Evaluation" (CAE)** benzeri mekanizmalar: Entra ID'de kritik olaylar (parola değişimi, hesap devre dışı bırakma, konum/IP risk değişimi) gerçekleştiğinde token'ları **near-real-time** iptal edebilme yeteneği - token'ın doğal süresi dolmasını beklemeden.

### Tespit - Pratik Uygulama

- **Entra ID / Microsoft 365 Defender**: `SigninLogs` ve `AADNonInteractiveUserSignInLogs`'da aynı `sessionId` veya `correlationId` için IP/User-Agent/cihaz tutarlılığını kontrol eden korelasyon kuralları. Microsoft'un "Token Theft" / "Anomalous Token" risk detection'ı (Identity Protection içinde) bu paternleri işaretler. Exchange Online tarafında inbox rule oluşturma, mail forwarding gibi post-compromise göstergeleri **UAL (Unified Audit Log)** üzerinden izlenir.
- **Genel SIEM yaklaşımı**: oturum/token ID bazında IP değişimi, User-Agent değişimi, coğrafi sıçrama olaylarını korelasyonlayan bir kural yaz; "authentication olayı" ile "sonraki kaynak erişim olaylarını" aynı oturum kimliği üzerinden zincirleyerek anomaliyi yakala.
- **AiTM phishing'e özel tespit**: reverse-proxy tabanlı phishing kitleri genelde gerçek IdP domainini taklit eden ama farklı bir alt alan adı/sertifika kullanan bir ara sunucu üzerinden geçer; bu da sign-in log'larında **beklenmedik bir "referrer"/"redirect URI"** ya da bilinmeyen bir uygulama kimliği (app ID) olarak iz bırakabilir. Conditional Access log'larında "unfamiliar sign-in properties" sinyali de bu aşamada faydalıdır.

### Yaygın Hatalar

- Sadece "MFA var, yeterli" varsayımıyla token/oturum katmanını hiç izlememek - MFA sonrası tehdit yüzeyini yok saymak.
- Token'ları çok uzun süreli (long-lived refresh token) ve cihaz kısıtlamasız vermek; token binding / conditional access session control uygulamamak.
- UAL/audit log retansiyonunu kısa tutmak - token çalma sonrası post-exploitation genelde günler sonra fark edilir, log kısa sürede silinmişse adli analiz imkansızlaşır.

## Conditional Access ve Politika İhlali Tespiti

Conditional Access (CA), Entra ID'nin "IF-THEN" politika motorudur: sinyal (kullanıcı, konum, cihaz, uygulama, risk seviyesi) + kural = eylem (izin ver, MFA iste, engelle, oturum süresini kısıtla). Kavramsal olarak CA, kimlik doğrulamanın **sonucu** değil, kimlik doğrulama **sürecine gömülü karar noktasıdır**.

Tespit açısından önemli olan, CA loglarının kendisinin bir tehdit istihbaratı kaynağı olmasıdır:
- **Tekrarlanan CA reddi (block) sonrası başarılı giriş**: saldırganın farklı IP/cihaz kombinasyonlarıyla politikayı "bypass etmeye çalıştığı" (deneme-yanılma) paterni.
- **"Legacy authentication" (temel kimlik doğrulama - basic auth, POP/IMAP gibi eski protokoller) kullanım girişimleri**: bu protokoller çoğunlukla MFA'yı desteklemez ve CA politikalarını atlatmak için tercih edilir; bu protokollerin engellenmiş olması gerekir, engellenmemişse aktif kullanımı kritik bir sinyaldir.
- **Riskli oturumda "grant edildi" sonuçları**: eğer politika yanlış yapılandırılmışsa (örnek: belirli bir uygulama CA kapsamına alınmamış, ya da bir "break-glass" hesap yanlışlıkla geniş muafiyete sahip), yüksek riskli bir sign-in politika tarafından yakalanmadan geçebilir - bu bir **politika kapsama boşluğu (policy gap)** ve düzenli olarak "what-if" aracı ile test edilmelidir.
- **Named location manipülasyonu**: saldırgan bilinen/güvenilir IP aralığına benzer görünmeye çalışıyorsa (örnek: kurumsal VPN çıkışına yakın bir IP kiralamak), bu da bir tespit hedefi olabilir ama tespiti zordur - bu yüzden CA tek başına yeterli değildir, davranışsal/oturum sinyalleriyle katmanlanmalıdır (defense in depth).

Okta tarafında eşdeğer kavram **Sign-On Policy** ve **Authentication Policy** kombinasyonudur; aynı mantık (context + kural + eylem) geçerlidir ve ihlal/bypass girişimleri System Log'da policy evaluation sonuçları üzerinden izlenir.

## ITDR: Identity Threat Detection and Response - Bir Disiplin Olarak

ITDR, Gartner tarafından tanımlanan, kimlik altyapısına özel (IdP, dizin servisleri, PAM sistemleri, sertifika otoriteleri dahil) tehdit tespiti ve müdahale disiplinidir. Kök mantığı şöyle: EDR endpoint'i, NDR ağı izler, ama kimlik katmanının **kendine özgü saldırı yüzeyi** (token çalma, MFA yorgunluğu/fatigue saldırısı, on-prem AD'den bulut kimliğe "hybrid" kötü amaçlı senkronizasyon, service principal/App registration suistimali, gölge yönetici - shadow admin hakları) genel amaçlı araçların görüş alanının dışındadır. ITDR bu boşluğu, kimliğe özel telemetriyi merkeze koyarak kapatır.

### ITDR'in Kapsadığı Temel Alanlar

1. **Kimlik sağlayıcı telemetrisi korelasyonu**: Entra ID + Okta + on-prem AD (varsa hybrid) log'larını tek bir görünümde birleştirme. Saldırganlar genelde birden fazla kimlik sistemi arasında "en zayıf halkayı" bulur (örnek: on-prem AD'de Kerberoasting ile elde edilen bir hesabın, hybrid sync üzerinden bulut kimliğine yansıması).
2. **Ayrıcalıklı kimlik izleme**: Global Administrator, Privileged Role Administrator gibi yüksek yetkili rollerin kullanımını, PIM (Privileged Identity Management) ile "just-in-time" erişime zorlama ve bu rollerin aktivasyon/kullanımını anomali tespiti kapsamına alma.
3. **Service Principal / App Registration suistimali**: insan olmayan kimlikler (non-human identities - servis hesapları, OAuth uygulamaları) genelde MFA'ya tabi olmadığı ve daha az izlendiği için saldırganların kalıcı erişim (persistence) için tercih ettiği bir vektördür. Aşırı izinli (over-privileged) API izinlerine sahip, az kullanılan veya şüphe çekici davranış gösteren app registration'ları izlemek ITDR'in önemli bir parçasıdır.
4. **Honeytoken / deception**: kasıtlı olarak "cazip" görünen ama gerçekte kullanılmayan sahte ayrıcalıklı hesaplar veya credential'lar yerleştirip, bunlara dokunulmasını "kesin ihlal sinyali" (yanlış pozitifsiz) olarak kullanma. Bu, Kerberoasting/AD iç ağ tekniklerinin bulut eşdeğeridir - hiçbir meşru süreç bu hesabı kullanmıyorsa, kullanan her şeyi saldırgan kabul edilebilir.
5. **Otomatik müdahale (response)**: risk tespit edildiğinde otomatik olarak oturumu sonlandırma, parolayı sıfırlamaya zorlama, hesabı geçici olarak askıya alma - tespit ile müdahale arasındaki süreyi (dwell time) minimize etme. Buradaki felsefe SIEM'in "gözlemle" mantığının ötesine geçip, SOAR benzeri otomatik aksiyon almaktır.

### Neden Ayrı Bir Araç/Disiplin Gerekli

Genel SIEM'e tüm log'ları atmak teorik olarak mümkün, ama pratikte iki sorun çıkar: (1) kimlik sağlayıcılarının log şeması ve risk kavramları kendine özgü olduğundan, genel amaçlı korelasyon kuralları bu nüansları yakalamakta zorlanır (örnek: "risky user" ile "risky sign-in" arasındaki farkı bilmeyen bir analist yanlış önceliklendirme yapar); (2) hacim - sign-in log hacmi genelde çok yüksektir ve doğru "baseline" (kullanıcıya özel normal davranış modeli) olmadan kural tabanlı tespit ya çok gürültülü ya da çok kör olur. Bu yüzden ITDR araçları (Microsoft Defender for Identity, Entra ID Protection, Okta ThreatInsight gibi) kimliğe özel ML modelleri ve baseline'ları devreye sokar.

## Savunma Önerileri (Özet, Uygulanabilir)

- **Conditional Access'i "varsayılan reddet" mantığıyla kur**: her uygulama, her kullanıcı grubu için açık bir politika olsun; kapsam dışı kalan (uncovered) uygulama olmadığından emin ol, düzenli "what-if" testi yap.
- **Legacy authentication'ı tamamen kapat**: MFA'yı bypass edebilen eski protokolleri (POP, IMAP, SMTP AUTH gibi) devre dışı bırak.
- **Token binding / device-bound token / Continuous Access Evaluation gibi özellikleri etkinleştir**: token'ın çalınsa bile başka bir cihazda/bağlamda işe yaramamasını hedefle.
- **PIM ile ayrıcalıklı rolleri "daimi" değil "geçici/JIT" yap**: Global Admin gibi roller sürekli aktif olmasın, aktivasyon loglansın ve anomali tespitine dahil edilsin.
- **Risky user / risky sign-in raporlarını düzenli ve otomatik işlemden geçir**: manuel inceleme yerine, otomatik politika (yüksek risk = zorunlu parola sıfırlama + oturum iptali) bağla.
- **Sign-in log'ları merkezi SIEM'e aktar ve uzun süreli sakla**: hem korelasyon hem de adli analiz için gerekli; kimlik olaylarını endpoint ve ağ telemetrisiyle birlikte incele (izole bakma).
- **Non-human identity envanterini çıkar**: hangi service principal / OAuth app'in hangi izinlere sahip olduğunu bil, az kullanılanları/aşırı yetkili olanları periyodik gözden geçir.
- **Honeytoken/deception hesapları yerleştir**: düşük maliyetli, yüksek sinyal kalitesi olan bir erken uyarı katmanı ekler.

## Yaygın Hatalar (Genel Toparlama)

- Kimlik telemetrisini "sadece compliance için tutulan log" sanmak; aktif tespit/korelasyon katmanına dahil etmemek.
- MFA'nın tüm kimlik tehditlerini çözdüğünü düşünmek; oturum/token katmanını ihmal etmek.
- Risk skorlarını (risky sign-in / risky user) otomatik aksiyona bağlamadan sadece dashboard'da izlemek - operasyonel yorgunluk (alert fatigue) yaratır ve gerçek olay kaybolur.
- Hybrid ortamlarda on-prem AD ile bulut kimlik arasındaki senkronizasyon zincirini tek bir tehdit yüzeyi olarak değerlendirmemek - saldırganlar tam da bu sınırı kullanır.
- Named location / güvenilir IP listelerini güncel tutmamak, bu da hem yanlış pozitif hem de yanlış negatif üretir.

## Sonuç

Kimlik odaklı tespit, "saldırgan zafiyet bulup exploit çalıştırır" varsayımından "saldırgan geçerli gibi görünen bir oturum açar" gerçekliğine geçişin savunma tarafıdır. Azure AD/Entra ID ve Okta gibi platformların sunduğu sign-in log'ları, risk skorları ve conditional access karar kayıtları, bu yeni tehdit yüzeyinin birincil kanıtı haline geldi. İmkansız seyahat, token replay ve conditional access ihlali tespiti; hepsi aynı kök mantığa dayanır: **kimlik doğrulama anını değil, kimliğin tüm yaşam döngüsünü (authentication + oturum + token + sonraki kaynak erişimi) bağlamsal olarak izlemek**. ITDR bu bakışı bir disipline dönüştürür ve modern SOC'un EDR/NDR kadar merkezi bir parçası olmak zorundadır - çünkü bugünün en verimli saldırı yolu, artık bir zafiyetten değil, çalınmış bir kimlikten geçiyor.
