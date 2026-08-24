# Bot Yönetimi, CAPTCHA Bypass ve Otomasyon Tespiti

## Tanım ve Kapsam

**Bot yönetimi (bot management)**, bir web uygulamasına gelen trafiği "insan mı yoksa otomatik bir istemci mi ürettiği" ekseninde ayırt etme, sınıflandırma ve buna göre karar verme disiplinidir. Klasik **rate limiting** (istek sınırlama) yalnızca "ne kadar hızlı istek geliyor" sorusuyla ilgilenir; bot yönetimi ise "bu isteği *kim* ve *nasıl* üretiyor" sorusuna odaklanır. Bu ayrım önemlidir çünkü modern kötü amaçlı otomasyon (**malicious automation**), rate limit eşiklerinin altında kalacak şekilde, binlerce IP ve tarayıcı profili arasına dağıtılarak çalışır.

Bu alanın hedef aldığı başlıca saldırı sınıfları şunlardır:

- **Credential stuffing**: Başka sızıntılardan elde edilmiş kullanıcı adı/parola çiftlerinin giriş formunda otomatik denenmesi.
- **Account takeover (ATO)** ve **otomatik hesap oluşturma (fake account creation)**: Sahte hesaplarla dolandırıcılık, spam veya promosyon istismarı.
- **Scraping / content theft**: Fiyat, envanter, içerik veya kişisel veri kazıma.
- **Scalping / inventory hoarding**: Sınırlı stok ürünleri (bilet, konsol, ayakkabı) otomatik satın alma.
- **Carding**: Çalıntı kart numaralarının küçük işlemlerle test edilmesi.

Bu alt disiplinin OWASP tarafında karşılığı **Automated Threats to Web Applications (OAT)** taksonomisidir; her saldırı tipine OAT-xxx kodu verilir (örneğin OAT-008 Credential Stuffing, OAT-011 Scraping, OAT-006 Expediting/Scalping gibi). Kodların birebir numarasından çok, bunun bir *sınıflandırma çerçevesi* olduğunu bilmek yeterlidir.

## Kök Neden ve Çalışma Mantığı

### Neden basit savunmalar yetmez

Web'in temel protokolü HTTP durumsuzdur ve istemcinin gerçekten bir insan mı yoksa bir script mi olduğunu doğrudan söyleyen bir alan yoktur. `User-Agent` başlığı istemci tarafından serbestçe uydurulabilir; IP adresi proxy/VPN ile değiştirilebilir; çerezler (cookie) klonlanabilir. Dolayısıyla savunma, "tek bir kesin sinyal" yerine **olasılıksal bir güven skoru** üretmek zorundadır. Bot yönetimi özünde bir **sınıflandırma (classification)** ve **risk skorlama** problemidir.

### Otomasyon araçlarının spektrumu

Saldırganın kullandığı araç, tespit zorluğunu belirler:

1. **Basit HTTP istemcileri** (curl, Python `requests`, Go `net/http`): JavaScript çalıştırmaz, gerçek bir tarayıcı DOM'u yoktur. Tespiti en kolay katman.
2. **Headless tarayıcılar** (Puppeteer, Playwright ile sürülen Chromium/Firefox): Gerçek bir tarayıcı motoru çalışır, JS yürütülür, ama otomasyon izleri bırakır.
3. **Anti-detect / stealth tarayıcılar** (yamalanmış headless, `puppeteer-extra-plugin-stealth`, ticari "antidetect browser"lar): Otomasyon izlerini gizlemeye çalışır, her oturum için ayrı bir sahte parmak izi (fingerprint) üretir.
4. **Gerçek tarayıcı + insan çiftlikleri (human farms) veya çözücü servisler**: Zorlukları ücretli insanlara veya makine öğrenmesi servislerine devreden hibrit yaklaşımlar.

### Fingerprinting: parmak izi çıkarma

**Browser fingerprinting**, istemcinin çok sayıda küçük özelliğini birleştirerek, çerez olmadan bile tekrar tanınabilen bir kimlik türetmektir. Başlıca sinyaller:

- **TLS/JA3(S) fingerprint**: Tarayıcının TLS el sıkışmasında (ClientHello) sunduğu cipher suite listesi, uzantı sırası ve eğri (curve) tercihleri, kullandığı kütüphaneye özgüdür. Chrome'un TLS parmak izi, Python `requests`'in TLS parmak izinden farklıdır. `User-Agent` "Chrome" derken TLS parmak izi Python `urllib` diyorsa, bu güçlü bir uyumsuzluk (mismatch) sinyalidir.
- **HTTP/2 fingerprint**: HTTP/2 SETTINGS çerçevesi, header sıralaması ve öncelik (priority) davranışı da istemciye özgü desenler taşır.
- **JavaScript ortam sinyalleri**: `navigator.webdriver` bayrağı, eksik veya sahte `navigator.plugins`, `window.chrome` nesnesinin varlığı/eksikliği, izin (permissions) API'sinin tutarsız yanıtları.
- **Canvas / WebGL fingerprint**: Aynı çizim komutunun GPU/sürücü/işletim sistemi kombinasyonuna göre piksel düzeyinde farklı sonuç vermesi; headless ortamlarda çoğu zaman yazılımsal render (SwiftShader) tespit edilir.
- **Fontlar, ekran çözünürlüğü, `devicePixelRatio`, saat dilimi, dil**: Bunların birbiriyle tutarlılığı önemlidir. Saat dilimi Tokyo, dil `en-US`, IP Almanya diyorsa tutarsızlık puanı yükselir.

Buradaki temel savunma prensibi **tutarlılık kontrolü (consistency checking)**'dir: Bir botun tek tek her sinyali taklit etmesi mümkündür, ama *tüm* sinyalleri birbiriyle tutarlı hale getirmesi çok zordur. Tespit, tek bir "yakalayıcı" sinyalden değil, katmanların çelişmesinden doğar.

### Davranışsal analiz (behavioral analysis)

Fingerprinting "istemci nasıl görünüyor" sorusunu yanıtlarken, davranışsal analiz "istemci nasıl davranıyor" sorusuna bakar:

- **Fare hareketleri ve dokunuş**: İnsan fare hareketi süreklidir, ivmelenir/yavaşlar, mikro-titremeler içerir; bot ya hiç fare hareketi göndermez ya da düz doğrusal/robotik yörüngeler üretir.
- **Yazma ritmi (keystroke dynamics)**: Tuşlar arası süreler ve hata/geri silme desenleri insanda değişkendir.
- **Sayfa etkileşim akışı**: Gerçek kullanıcı önce sayfayı yükler, kaydırır, alanlara tıklar; bot çoğu zaman doğrudan form gönderim uç noktasına (endpoint) POST atar ve ara adımları atlar.
- **Zamanlama (timing)**: İnsanın bir formu doldurması saniyeler alır; 40 milisaniyede gelen kusursuz bir POST güçlü bir bot sinyalidir.
- **Oturum grafiği**: Bir IP/parmak izi kümesinin çok sayıda farklı hesapta oturum açmayı denemesi, credential stuffing'in klasik "geniş ve sığ" (many accounts, few tries each) desenidir.

## CAPTCHA ve İnsan Doğrulama Mekanizmaları

**CAPTCHA** (Completely Automated Public Turing test to tell Computers and Humans Apart), insanın kolayca yapabildiği ama otomasyonun zorlandığı bir görevle ("challenge") istemciyi test eder. Modern nesiller giderek görünmez (invisible) hale gelmiştir:

- **Görsel/işitsel challenge'lar** (bozuk metin, "trafik ışıklarını seç"): Klasik ama giderek zayıflayan yöntem, çünkü görüntü tanıma modelleri bunları çözebiliyor.
- **Skor tabanlı, görünmez sistemler** (ör. reCAPTCHA v3 tarzı): Kullanıcıya bir bulmaca göstermek yerine, arka planda davranış ve sinyalleri toplayıp 0–1 arası bir risk skoru üretir. Uygulama bu skora göre eylem seçer (izin ver / ek doğrulama iste / engelle).
- **Proof-of-work ve gizli challenge tabanlı sistemler** (ör. Cloudflare Turnstile mantığı): Kullanıcıdan görsel çözüm istemeden, tarayıcıda küçük hesaplama/ortam kontrolleri çalıştırarak istemcinin gerçek bir tarayıcı olup olmadığını sınar ve bir doğrulama token'ı verir.

Bu token'lar sunucu tarafında **mutlaka doğrulanmalıdır**. CAPTCHA'nın en yaygın uygulama hatası, token'ı yalnızca istemcide kontrol edip sunucu tarafı doğrulama (siteverify çağrısı) yapmamaktır.

### "CAPTCHA Bypass" kavramsal olarak nasıl işler

Eğitim amacıyla, atlatma yaklaşımlarının *kategorilerini* anlamak savunma tasarımı için gereklidir (bu bir operasyonel tarif değil, savunma modelidir):

1. **Token yeniden kullanımı / replay**: Sunucu, çözülmüş bir token'ın tek kullanımlık (single-use) olduğunu, süresini (expiry) ve hangi eyleme/host'a bağlı (action/hostname binding) olduğunu doğrulamazsa, saldırgan tek bir çözümü çok kez kullanabilir. **Kök neden: eksik sunucu tarafı doğrulama.**
2. **Çözüm devri (solver services / human farms)**: Challenge, API üzerinden ücretli insan çözücülere veya ML servislerine iletilir; dönen cevap saldırganın oturumuna enjekte edilir. Burada CAPTCHA "kırılmaz", *dışarıya taşınır*.
3. **Otomasyon izlerini gizleme (stealth)**: Skor tabanlı sistemlerin bot skorunu düşürmek için `navigator.webdriver` gibi bayrakları gizlemek, gerçekçi fare hareketi enjekte etmek, tutarlı parmak izi sunmak.
4. **İş akışını atlama (flow bypass)**: CAPTCHA'nın korumadığı bir alternatif uç noktayı (ör. eski bir mobil API sürümü, korumasız bir GraphQL mutasyonu) bulup asıl korumalı akışı hiç tetiklememek. **En sık görülen ve en ucuz bypass budur** — CAPTCHA aslında atlatılmaz, sadece etrafından dolaşılır.

Buradan çıkan savunma dersi: CAPTCHA tek başına bir kapı değil, **birçok sinyalden biridir**; ve korunması gereken *eylem* (giriş, kayıt, ödeme) tüm giriş yollarında (web, mobil API, third-party entegrasyon) tutarlı biçimde korunmalıdır.

## Örnek Senaryo: Credential Stuffing Kampanyası

Bir e-ticaret sitesinin giriş formunu düşünelim. Saldırgan elinde 2 milyon sızmış e-posta/parola çifti ve 50.000 residential proxy IP'si var.

- **Naif rate limit**: "IP başına dakikada 10 giriş" kuralı, saldırgan trafiği 50.000 IP'ye yaydığı için hiç tetiklenmez. Her IP dakikada 1–2 deneme yapar, eşiğin çok altında kalır.
- **Trafik profili**: Tüm istekler doğrudan `/api/login` uç noktasına POST atar; hiçbiri ana sayfayı yüklememiş, hiçbiri JavaScript çalıştırmamıştır. TLS parmak izi bir HTTP kütüphanesine işaret eder, `User-Agent` ise Chrome iddiasındadır (uyumsuzluk).
- **Sonuç sinyali**: Başarısız giriş oranı normalde %2 iken saniyeler içinde tüm platformda %40'a fırlar; başarılı girişlerin coğrafyası aniden dağılır (aynı hesaba dakikalar arayla farklı ülkelerden başarılı giriş).

Bu senaryo, tek bir sinyalin (IP hızı) neden yetmediğini ve **çok sinyalli, sunucu tarafı ve popülasyon düzeyinde** analiz gerektiğini gösterir.

## Tespit

Etkili tespit, tek istek düzeyinden popülasyon düzeyine kadar katmanlıdır:

**İstek/oturum düzeyi:**
- **Parmak izi uyumsuzluğu**: `User-Agent` ile TLS/JA3, HTTP/2 ve JS ortam sinyalleri arasındaki çelişkiler.
- **Otomasyon bayrakları**: `navigator.webdriver`, eksik `window.chrome`, yazılımsal WebGL render, tutarsız permission yanıtları.
- **Eksik ön adımlar**: Korumalı uç noktaya, beklenen sayfa yüklemesi / statik varlık (asset) talebi olmadan doğrudan gelen istekler.
- **Zamanlama anomalileri**: İnsan için imkânsız derecede hızlı form gönderimi.

**Popülasyon/istatistik düzeyi (bunlar genelde tek istekten daha güçlüdür):**
- **Başarısız giriş oranındaki ani artış** (credential stuffing imzası).
- **Yeni hesap kayıtlarında patlama** ve bu hesapların benzer parmak izi/IP bloğu paylaşması.
- **Impossible travel**: Aynı hesaba kısa sürede coğrafi olarak imkânsız konumlardan erişim.
- **Fingerprint yeniden kullanımı**: Tek bir parmak izinin yüzlerce farklı hesapla ilişkilenmesi.
- **Endpoint dağılımı anomalisi**: Trafiğin normal kullanıcı akışının aksine yalnızca "değerli" uç noktalara yoğunlaşması.

**Telemetri ve loglama gereksinimleri:** Bunları görebilmek için giriş/kayıt olaylarını, IP + parmak izi + sonuç (başarı/başarısızlık) + zaman damgası ile merkezi olarak (SIEM/log platformu) toplamak şarttır. Sadece "erişim logu" yetmez; **kimlik odaklı (identity-centric)** olaylar gerekir. Cihaz parmak izi ve challenge sonucu da bu olaylara iliştirilmelidir.

## Savunma

Savunma bir "gümüş kurşun" değil, **katmanlı ve maliyet asimetrisi kuran** bir tasarımdır. Amaç saldırganın maliyetini savunanın maliyetinin üzerine çıkarmaktır.

1. **Katmanlı doğrulama (defense in depth):** Rate limiting (hem IP hem hesap hem cihaz bazlı) + fingerprinting + davranışsal skorlama + CAPTCHA/challenge, birlikte kullanılır. Her katman farklı bir otomasyon seviyesini yakalar.

2. **Risk tabanlı (adaptive) yaklaşım:** Herkese sürtünme (friction) dayatmak yerine, düşük riskli istekleri sessizce geçir, orta riskli istekte görünmez challenge tetikle, yüksek riskli istekte MFA / adım doğrulama iste veya engelle. Bu, gerçek kullanıcı deneyimini korurken botları filtreler.

3. **Sunucu tarafı token doğrulaması:** CAPTCHA/Turnstile token'ları daima sunucuda doğrulanmalı; **tek kullanımlık** olmalı, **süresi**, **hedef eylemi (action)** ve **host'u** kontrol edilmeli. Token replay'i mutlaka engellenmelidir.

4. **Tutarlı koruma yüzeyi:** Aynı hassas eylem (giriş, kayıt, ödeme) web, mobil ve API dahil *tüm* yollarda aynı korumaya sahip olmalıdır. Unutulmuş eski API sürümleri en yaygın kaçış deliğidir.

5. **Kimlik güvenliği takviyeleri:** Sızmış parola kontrolü (breached password check), zorunlu/isteğe bağlı MFA, şüpheli girişte cihaz doğrulama, hesap kilitleme yerine akıllı adaptif kilit (aptal kilit, kullanıcıyı DoS'a açar).

6. **İzleme ve geri bildirim döngüsü:** Popülasyon metriklerini (başarısız oran, kayıt hızı, impossible travel) izleyen alarmlar ve bu alarmları yeni tespit kurallarına dönüştüren bir yaşam döngüsü (detection engineering) kurun. Bot davranışı sürekli evrildiği için savunma da statik olamaz.

7. **Honeypot ve tuzak alanlar:** Gerçek kullanıcının görmediği ama otomasyonun dolduracağı gizli form alanları (honeypot field), ucuz ve etkili bir erken bot filtresidir.

## Yaygın Hatalar

- **Rate limiting'i tek savunma sanmak.** Dağıtık, "geniş ve sığ" saldırılar eşiklerin altında kalır. Rate limit gerekli ama tek başına yetersizdir.
- **CAPTCHA token'ını sunucuda doğrulamamak.** İstemci tarafında "geçti" görünmesi hiçbir şey ispat etmez; token replay ve atlama buradan girer.
- **Sadece `User-Agent`'a güvenmek.** Tümüyle istemci kontrollü, önemsiz derecede sahtelenebilir bir alandır. Tek başına ne engelleme ne tespit için güvenilirdir.
- **Sadece IP bazlı engelleme / kalıcı ban.** Residential proxy ve CGNAT nedeniyle IP hem kolay değişir hem de masum kullanıcıları toplu cezalandırır (yanlış pozitif).
- **Korumayı tek bir giriş yoluna koyup diğerlerini unutmak.** Web formu CAPTCHA'lıyken korumasız kalan mobil/legacy API, saldırganın ilk hedefidir.
- **Agresif challenge ile gerçek kullanıcıyı boğmak.** Erişilebilirlik (accessibility) sorunları ve terk oranı artışı; kör/az gören kullanıcılar görsel CAPTCHA'da tıkanır. Risk tabanlı, görünmez yaklaşım tercih edilmelidir.
- **Hesap kilitlemeyi düşünmeden uygulamak.** "5 hatalı denemede hesabı kilitle" kuralı, saldırganın bilerek yanlış parola göndererek meşru kullanıcıları kitlemesine (account lockout DoS) olanak tanır.
- **Statik kurallara yaslanmak.** Bot ekosistemi (stealth araçları, solver servisleri) sürekli evrilir; tespit kuralları düzenli güncellenmezse hızla eskir.

## Özet

Bot yönetimi, "insan mı otomasyon mu" sorusunu tek bir kesin sinyalle değil, birbirini destekleyen ve çelişkileri açığa çıkaran **çok katmanlı, olasılıksal** bir yaklaşımla yanıtlar. Fingerprinting (TLS/JA3, HTTP/2, canvas, JS ortamı) istemcinin *ne olduğunu*, davranışsal analiz *nasıl davrandığını*, CAPTCHA/challenge ise *insan olduğunu ispatlayıp ispatlayamadığını* ölçer. CAPTCHA "bypass"ının çoğu, kriptografik bir kırılma değil; eksik sunucu doğrulaması, korumasız alternatif akışlar veya çözümün insan/servis çiftliklerine devredilmesidir. Sağlam savunma; katmanlı, risk-adaptif, tüm giriş yollarında tutarlı, popülasyon düzeyinde izlenen ve sürekli güncellenen bir sistemdir — amaç mükemmel engelleme değil, saldırganın maliyetini savunulamaz hale getirmektir.
