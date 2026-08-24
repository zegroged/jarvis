# Kimlik Doğrulama Atlatma Teknikleri

Kimlik doğrulama (authentication), bir sistemin "sen gerçekten iddia ettiğin kişi misin?" sorusuna verdiği yanıttır. Yetkilendirme (authorization) ise "sen bu kaynağa erişebilir misin?" sorusunu yanıtlar. Bu iki kavram sık sık karıştırılır ve bu karışıklığın kendisi, bu yazıda inceleyeceğimiz zafiyetlerin kök nedenlerinden biridir. Kimlik doğrulama atlatma (authentication bypass), saldırganın geçerli kimlik bilgilerini (parola, token, biyometrik veri) ele geçirmeden veya kırmadan, doğrulama sürecinin **mantığındaki** bir boşluğu kullanarak korumalı bir kaynağa erişmesidir.

Buradaki kilit fark şudur: brute-force veya parola tahmini kimlik bilgisine *saldırır*; bypass ise doğrulama *sürecine* saldırır. Genellikle çok daha tehlikelidir, çünkü hiçbir parola karmaşıklığı politikası, mantık hatası olan bir akışı kurtaramaz. Bu yazıda dört ana yüzeyi derinlemesine ele alacağız: mantık hataları, response manipülasyonu, forced browsing ve 2FA bypass.

---

## Mantık Hataları (Logic Flaws)

### Tanım

Mantık hatası, kodun teknik olarak hatasız çalıştığı ancak iş akışının (business logic) saldırgan lehine sömürülebilecek bir varsayım üzerine kurulduğu durumdur. Bir SQL injection'da veriyi bozarsınız; bir mantık hatasında ise geliştiricinin "kullanıcı bu adımları şu sırayla yapacak" varsayımını kırarsınız.

### Kök neden: neden böyle oluyor?

Kimlik doğrulama akışları çoğu zaman **durum makinesi (state machine)** olarak tasarlanır: giriş → parola doğrulama → 2FA → oturum oluşturma. Ancak geliştiriciler bu durumların **sunucu tarafında** zorunlu tutulduğunu varsayarken, aslında geçişleri istemciden gelen bir parametreye veya bir önceki adımın "sessizce başarılı olduğu" varsayımına bağlar. Sunucu, her isteği bağımsız (stateless) değerlendirdiği hâlde iş mantığı bağlamlı (stateful) davranmaya çalışınca boşluk doğar.

Bir başka kök neden, **güven sınırının (trust boundary) yanlış çizilmesidir**. İstemciden gelen hiçbir veri güvenilir değildir; ama uygulamalar sık sık `isAdmin`, `authenticated`, `step_completed` gibi kararları istemcinin gönderdiği veriye dayandırır.

### Somut örnekler

**Parola sıfırlama akışında kullanıcı karıştırma:** Klasik bir örnek, parola sıfırlama isteğinde token'ın bir kullanıcıya, hedef e-postanın ise başka bir kullanıcıya ait olabilmesidir. Uygulama token'ı doğrular ("bu token geçerli mi?") ama token'ın gönderilen `username` ile eşleşip eşleşmediğini kontrol etmez ("bu token *bu* kullanıcıya mı ait?"). Saldırgan kendi geçerli token'ıyla başka birinin parolasını sıfırlar.

**"Remember me" veya oturum durumunun istemcide tutulması:** Bir çerezin içinde `role=user` yazıyorsa ve sunucu bunu imzalamadan okuyorsa, saldırgan `role=admin` yapar. Bu, mantık hatası ile response manipülasyonunun kesiştiği yerdir.

**Çok adımlı akışta adım atlama:** Kayıt akışı e-posta doğrulaması gerektiriyor ama son "hesabı etkinleştir" endpoint'i, e-posta doğrulama adımının tamamlanıp tamamlanmadığını kontrol etmeden çağrılabiliyorsa, saldırgan doğrulamayı atlar.

### Sömürü mantığı

Saldırgan önce akışı normal şekilde tamamlayarak her isteği ve yanıtı bir proxy (örneğin Burp Suite) ile kaydeder. Ardından şu soruları sorar: Hangi adım hangi parametreye bağlı? Bir adımı atlarsam ne olur? Bir parametreyi başka bir kullanıcının değeriyle değiştirirsem sunucu itiraz eder mi? Sıralamayı bozarsam? Aynı token'ı iki kez kullanırsam? Sömürü, teknik bir açıktan çok, uygulamanın örtük varsayımlarını sistematik olarak test etmektir.

### Savunma

- **Her güvenlik kararını sunucu tarafında ve mevcut oturumun kimliğine bağlı olarak ver.** İstemciden gelen kullanıcı kimliği asla yetki kararında kullanılmamalı; oturumdan (session) türetilmeli.
- **Durum geçişlerini sunucu tarafında zorunlu kıl.** Her endpoint, kendisinden önce gelmesi gereken adımların tamamlandığını bağımsız olarak doğrulamalı. "Önceki sayfa bunu kontrol etti" varsayımı geçersizdir.
- **Nesne sahipliğini doğrula.** Bir token, bir sıfırlama isteği veya bir kaynak üzerinde işlem yaparken, o nesnenin talep eden kullanıcıya ait olduğunu her seferinde kontrol et (bu aynı zamanda IDOR savunmasıdır).

---

## Response Manipülasyonu

### Tanım

Response manipülasyonu, sunucunun istemciye döndürdüğü yanıtın, kimlik doğrulama kararını **istemci tarafında** belirlediği durumlarda ortaya çıkar. Saldırgan, bir proxy aracılığıyla dönen yanıtı gerçek zamanlı olarak değiştirerek uygulamayı "başarılı giriş" olduğuna ikna eder.

### Kök neden: neden böyle oluyor?

Bu zafiyetin temelinde **kararın yanlış yerde verilmesi** yatar. Doğru mimaride sunucu "giriş başarılı mı?" sorusunu yanıtlar ve buna göre bir oturum token'ı üretir; istemci sadece sonucu gösterir. Zayıf mimaride ise sunucu `{"success": false}` gibi bir bayrak döndürür ve **istemcideki JavaScript** bu bayrağa bakarak kullanıcıyı yönlendirir veya panele sokar. Karar mantığı istemciye kaydığında, saldırgan yanıtı değiştirerek `false`'u `true` yapar ve istemci onu içeri alır.

Kök neden, güven modelinin tersine çevrilmesidir: İstemci hiçbir zaman güvenlik otoritesi olmamalıdır; ama SPA (single-page application) mimarilerinin yaygınlaşmasıyla, geliştiriciler kolaylık uğruna kritik kararları frontend'e taşıyabiliyor.

### Somut örnek

Bir mobil veya web uygulaması giriş için `/api/login` çağırıyor ve sunucu şu yanıtı dönüyor:

```json
{ "authenticated": false, "role": "guest", "redirect": "/login" }
```

İstemci kodu şuna benzer bir mantık içeriyor: `if (response.authenticated) { showDashboard() }`. Saldırgan araya girip yanıtı `{ "authenticated": true, "role": "admin", "redirect": "/dashboard" }` olarak değiştirdiğinde, uygulama paneli açar. Eğer panel içeriği de aynı sunucu yanıtına gömülü geliyorsa (ve sunucu bu içeriği ayrı bir yetki kontrolüyle korumuyorsa), saldırgan gerçek veriye erişir.

Benzer bir varyant, HTTP durum kodunun manipülasyonudur: Uygulama `401 Unauthorized` yerine `200 OK` görünce içeri alıyorsa, proxy'de durum kodunu değiştirmek yeterli olabilir.

### Sömürü ile savunmanın ayrımı

Sömürü tarafında saldırgan, proxy'nin "yanıtı yakala ve düzenle" özelliğini kullanır; başarısız girişin yanıtını yakalar, kritik bayrakları çevirir ve istemcinin tepkisini gözlemler. Kritik test şudur: Bayrağı çevirmek panele *görsel* erişim mi veriyor, yoksa gerçek *veriye* erişim mi? İlki kozmetiktir; ikincisi ciddi bir açıktır.

Savunma tarafında ana ilke nettir: **İstemci yanıtındaki hiçbir alan güvenlik kararı vermemeli.** Panel içeriğini döndüren her endpoint, oturumun geçerliliğini ve yetkisini bağımsız olarak sunucuda kontrol etmeli. Yani saldırgan `authenticated: true` yaparak paneli "görebilse" bile, panelin çektiği `/api/admin/users` gibi her endpoint, sunucu tarafında geçerli bir yönetici oturumu olmadığı için `403` dönmelidir. Doğru tasarlanmış bir sistemde response manipülasyonu en fazla boş bir kabuk gösterir, veri sızdırmaz.

Ek olarak, kritik yanıtlar bütünlük koruması altında olmalı; ancak TLS zaten aktarım bütünlüğünü sağladığı için asıl savunma, kararı istemciye hiç bırakmamaktır — TLS, kullanıcının kendi cihazındaki proxy'ye karşı koruma sağlamaz.

---

## Forced Browsing (Zorlamalı Gezinme)

### Tanım

Forced browsing, saldırganın uygulamanın arayüzünde bağlantısı bulunmayan ama sunucuda var olan kaynaklara (URL, endpoint, dosya) doğrudan istek göndererek erişmeye çalışmasıdır. Genellikle "güvenlik gizlilikle sağlanır" (security through obscurity) yanılgısının somut sonucudur.

### Kök neden: neden böyle oluyor?

Uygulama, bir kaynağa erişimi **sadece o kaynağa giden linki menüde göstermeyerek** kısıtladığını sanır. Yani `/admin/panel` sayfasına link normal kullanıcıya gösterilmez, ama sayfanın kendisi erişim kontrolü ile korunmaz. Buradaki hatalı varsayım, "kullanıcı URL'yi bilmiyorsa erişemez" düşüncesidir. Oysa URL'ler tahmin edilebilir, sızabilir veya kaba kuvvetle (dizin listeleme, kelime listeleri) keşfedilebilir.

Bu, **eksik fonksiyon seviyesi erişim kontrolü** (missing function-level access control) olarak da bilinen bozuk erişim kontrolünün (broken access control) bir alt kümesidir. Kök neden, erişim kontrolünün her endpoint'e tek tek uygulanması gerekirken merkezi ve varsayılan-reddet (default-deny) bir katman olarak tasarlanmamasıdır.

### Somut örnekler

- **Yönetim panelleri:** `/admin`, `/dashboard/admin`, `/manage` gibi yollar kimlik doğrulama kontrolü olmadan erişilebilir kalır.
- **Numaralandırılabilir kaynaklar:** `/invoice?id=1001` çalışıyorsa, `1002` başka kullanıcının faturasını verebilir (forced browsing + IDOR).
- **Yedek ve geçici dosyalar:** `.bak`, `.old`, `config.php.swp`, `/backup.zip` gibi dosyaların sunucuda erişilebilir kalması.
- **API sürüm veya endpoint keşfi:** `/api/v1/users` korunuyorken `/api/v2/users` veya `/api/internal/users` unutulmuş olabilir.
- **Kimlik doğrulama sonrası sayfalara doğrudan erişim:** Giriş yapmadan doğrudan `/account/settings` çağırmak, eğer sayfa oturum kontrolü yapmıyorsa içeriği açar.

### Sömürü mantığı

Saldırgan, içerik keşfi (content discovery) araçlarıyla — kelime listeleri kullanarak sistematik olarak yolları dener. Robots.txt, sitemap.xml, JavaScript dosyalarındaki gömülü endpoint referansları, hata mesajlarındaki yol sızıntıları ve HTTP yanıt kodlarındaki farklar (var olan ama yetkisiz kaynak `403`, olmayan `404` döner) haritayı çıkarmaya yarar. Amaç, "gizlenmiş ama korunmamış" kaynakları bulmaktır.

### Savunma

- **Varsayılan-reddet (default-deny) mimarisi kur.** Yeni bir endpoint eklendiğinde, açıkça izin verilmedikçe erişim reddedilmeli. Bu, "erişim kontrolünü unutmak" hatasını yapısal olarak imkânsızlaştırır.
- **Erişim kontrolünü merkezi bir katmanda (middleware/filter) uygula**, her controller'a dağıtma. Dağıtık kontroller kaçınılmaz olarak bazı endpoint'lerde unutulur.
- **Yetkiyi kaynak seviyesinde ve oturuma bağlı doğrula.** URL'nin bilinmemesine değil, kullanıcının o kaynağa hakkı olmasına dayan.
- **Gereksiz dosyaları üretim ortamından kaldır**; yedekler, `.git` dizinleri, geçici dosyalar web köküne erişilebilir olmamalı.
- **Var olan ama yetkisiz kaynaklar için `404` dönmeyi değerlendir**; `403` ile `404` farkı kaynağın varlığını sızdırır, ancak bu ikincil bir önlemdir — asıl koruma erişim kontrolüdür, gizlilik değil.

---

## 2FA / MFA Bypass

### Tanım

İki faktörlü kimlik doğrulama (2FA) veya çok faktörlü kimlik doğrulama (MFA), "bildiğin bir şey" (parola) ile "sahip olduğun bir şey" (telefon, token) veya "olduğun bir şey" (biyometri) faktörlerini birleştirir. 2FA bypass, saldırganın ikinci faktörü sağlamadan ya da onu geçersiz kılarak oturuma erişmesidir. 2FA'nın sağladığı temel değer, parola sızsa bile hesabın korunmasıdır; bypass bu değeri sıfırlar.

### Kök neden: neden böyle oluyor?

2FA, mevcut bir kimlik doğrulama akışına **sonradan eklenen bir katman** olduğunda en kırılgan hâlini alır. Geliştirici parola doğrulama akışını zaten yazmıştır ve 2FA'yı araya sıkıştırır; ama akışın her dalının 2FA'dan geçtiğinden emin olmaz. Kök nedenler genellikle şunlardır: ikinci faktörün **sunucu tarafında zorunlu tutulmaması**, geçici oturum durumunun yanlış yönetilmesi ve doğrulama kodunun yeterince korunmaması.

### Somut örnekler ve alt teknikler

**1. Adım atlama (2FA endpoint'ini es geçme):** Parola doğrulandıktan sonra kullanıcıya bir "2FA kodu gir" sayfası gösterilir. Ama korumalı `/dashboard` endpoint'i, oturumun 2FA'yı geçip geçmediğini kontrol etmeden erişilebilirse, saldırgan 2FA sayfasını atlayıp doğrudan panele gider. Bu, forced browsing'in 2FA'ya uygulanmış hâlidir. Kök neden: sunucu oturumu "parola doğrulandı ama 2FA bekliyor" ile "tam doğrulandı" arasında ayırmıyor; her ikisini de "giriş yapılmış" sayıyor.

**2. Kod brute-force (rate limiting eksikliği):** OTP kodları genellikle 6 haneli, yani bir milyon olasılık. Deneme sayısı sınırlanmamışsa, saldırgan kodu makul sürede kaba kuvvetle bulur. Kritik detay: rate limiting sadece IP başına değil, **kod/hesap başına** olmalı; yoksa saldırgan IP rotasyonuyla sınırı aşar. Ayrıca kod her başarısız denemede değil, belirli bir deneme sayısından sonra geçersizleşmeli veya oturum kilitlenmeli.

**3. Response manipülasyonu ile 2FA atlama:** 2FA doğrulama yanıtı istemcide değerlendiriliyorsa (`{"2fa_valid": false}`), saldırgan bunu `true` yaparak geçer. Bu, response manipülasyonu bölümünün 2FA'ya özel hâlidir.

**4. Yeniden kullanılabilir veya süresi dolmayan kodlar:** OTP tek kullanımlık (one-time) olmalı ve kısa bir süre (tipik olarak birkaç dakika) içinde geçersizleşmelidir. Kod bir kez kullanıldıktan sonra geçersiz kılınmıyorsa veya süresi dolmuyorsa, sızmış bir kod tekrar kullanılabilir.

**5. Kurtarma/yedek akışlarının zayıflığı:** 2FA'nın kendisi güçlü olsa bile, "cihazımı kaybettim" akışı yalnızca e-postaya güveniyorsa, saldırgan e-postayı ele geçirerek 2FA'yı komple atlar. Zincir en zayıf halkası kadar güçlüdür; kurtarma akışı çoğu zaman o zayıf halkadır.

**6. Faktörün mantıksal olarak devre dışı bırakılması:** Kullanıcı ayarlarında 2FA'yı kapatan endpoint, mevcut 2FA doğrulaması istemeden çağrılabiliyorsa, saldırgan parola ile giriş yapıp (2FA'yı henüz geçmeden, eğer akış izin veriyorsa) 2FA'yı kapatabilir.

**7. "Remember this device" token'ının zayıflığı:** Cihazı hatırlama token'ı tahmin edilebilir veya çalınabilirse, saldırgan 2FA'yı tümüyle atlayan bir çerezle gelir.

**8. OAuth/SSO veya alternatif giriş yolları:** Hesaba sosyal giriş (social login) gibi ikincil bir yol 2FA gerektirmiyorsa, saldırgan güçlü kapıyı değil zayıf yan kapıyı kullanır.

### Sömürü ile savunmanın ayrımı

Sömürü tarafında saldırgan sistematik olarak şunu sorar: 2FA akışının *her* dalı gerçekten zorunlu mu? Parola doğru olduktan sonra hangi endpoint'ler erişilebilir? Kod kaç kez denenebilir? Kod tekrar kullanılabilir mi, ne kadar geçerli? 2FA'yı kapatmak veya güvenli cihaz eklemek yeniden doğrulama istiyor mu? Kurtarma yolu zayıf mı? Alternatif giriş var mı?

Savunma tarafında temel ilkeler:

- **Geçici oturum durumunu ayır.** "Parola doğrulandı, 2FA bekleniyor" durumu ile "tam kimlik doğrulandı" durumu farklı olmalı; korumalı hiçbir endpoint yarım oturumla erişilemez. Bu, en yaygın ve en kritik 2FA bypass'ı (adım atlama) yapısal olarak engeller.
- **Doğrulamayı sunucuda zorunlu tut.** İkinci faktörün geçildiği kararı asla istemci yanıtına bağlanmamalı.
- **Rate limiting'i hesap/kod başına uygula** ve belirli sayıda başarısız denemeden sonra kodu geçersiz kıl. Kodun tahmin uzayını (entropi) makul tut ve süreyi kısa sınırla.
- **Kodları tek kullanımlık ve kısa ömürlü yap.** Kullanılan kod anında geçersizleşmeli.
- **Hassas işlemlerde yeniden doğrulama (step-up authentication) iste.** 2FA'yı kapatma, parola değiştirme, güvenli cihaz ekleme gibi işlemler mevcut bir 2FA doğrulaması gerektirmeli.
- **Kurtarma ve alternatif giriş yollarını ana akış kadar güçlü koru.** Zincirin tüm halkaları aynı güvenlik seviyesinde olmalı; aksi hâlde saldırgan en zayıf yolu seçer.

---

## Yaygın Hatalar

Bu dört alanı bir arada düşününce, tekrar eden kök hatalar belirginleşir:

- **Güvenlik kararını istemciye bırakmak.** Response manipülasyonunun tamamı, 2FA bypass'ın büyük kısmı ve pek çok mantık hatası bu tek hatadan doğar. İstemci hiçbir zaman güvenlik otoritesi değildir.
- **"Bilinmiyorsa güvenli" (security through obscurity) yanılgısı.** Forced browsing'in tamamı bu yanılgının ürünüdür. Bir kaynağın URL'sinin gizli olması onu korumaz.
- **Oturum durumlarını ayırt etmemek.** "Kimliği kısmen doğrulanmış" ile "tam doğrulanmış" oturumu aynı saymak, adım atlama saldırılarının kapısını açar.
- **Erişim kontrolünü dağıtık ve opsiyonel yapmak.** Her endpoint'te tek tek kontrol yazmak, kaçınılmaz olarak bazılarında unutmaya yol açar. Varsayılan reddet ve merkezi katman şarttır.
- **Nesne sahipliğini doğrulamamak.** Token, kayıt veya kaynak üzerinde işlem yaparken "bu talep edene mi ait?" sorusunu atlamak, hem mantık hatalarına hem IDOR'a yol açar.
- **Rate limiting'i yanlış boyutta uygulamak.** Sadece IP başına sınırlama, hesap başına brute-force'u durdurmaz.
- **Zincirin bir halkasını güçlendirip diğerlerini unutmak.** Güçlü 2FA ama zayıf kurtarma; güçlü giriş ama korumasız alternatif yol.

## En İyi Pratikler

En sağlam savunma, tek tek zafiyetleri yamamaktan çok, doğru güvenlik ilkelerini mimariye gömmekten geçer:

**Sunucu tek doğruluk kaynağıdır.** Her kimlik ve yetki kararı sunucuda, mevcut oturumun doğrulanmış kimliğine dayanarak verilmeli. İstemciden gelen her veri düşman kabul edilmeli.

**Varsayılan reddet (default-deny) ilkesi.** Sistem, açıkça izin verilmedikçe erişimi reddedecek şekilde tasarlanmalı. Bu, geliştiricinin bir kontrolü unutması durumunda bile sistemi güvenli tarafta bırakır (fail-safe).

**Durum makinesini sunucuda zorunlu tut.** Çok adımlı akışlarda her adım, önceki adımların tamamlandığını bağımsız doğrulamalı. Giriş, 2FA ve oturum durumları net biçimde ayrılmalı.

**Derinlemesine savunma (defense in depth).** Tek bir kontrole güvenme. Response manipülasyonu paneli açsa bile, arkadaki her veri endpoint'i ayrı yetki kontrolüyle korunmalı; böylece tek bir atlatma tüm sistemi düşürmez.

**Erişim kontrolünü merkezi ve test edilebilir yap.** Middleware/filter katmanı kullan; erişim kurallarını otomatik testlerle doğrula. "Yetkisiz kullanıcı bu endpoint'e erişebiliyor mu?" testleri regresyonları yakalar.

**Kimlik doğrulama akışının tüm dallarını tehdit modellemesiyle gözden geçir.** Ana akış kadar kurtarma, alternatif giriş, hesap ayarları ve API varyantlarını da incele. Saldırgan her zaman en zayıf yolu seçer; sen de tüm yolları düşünmelisin.

**Hassas işlemlerde step-up authentication uygula** ve rate limiting'i doğru boyutta (hesap/kod başına) kur.

Sonuç olarak kimlik doğrulama atlatma, çoğunlukla bir kriptografi veya bellek güvenliği sorunu değil, bir **güven ve durum yönetimi** sorunudur. Kararı doğru yerde (sunucuda) verirsen, durumu doğru ayırırsan ve varsayılan olarak reddedersen, bu yazıdaki tekniklerin büyük çoğunluğu yapısal olarak etkisiz kalır.
