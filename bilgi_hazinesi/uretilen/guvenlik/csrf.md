# Cross-Site Request Forgery (CSRF)

## Tanım

Cross-Site Request Forgery (CSRF), Türkçe yaygın karşılığıyla "siteler arası istek sahteciliği", bir saldırganın kurbanın kimliği doğrulanmış (authenticated) oturumunu kötüye kullanarak, kurbanın haberi ve rızası olmadan hedef uygulamaya durum değiştiren (state-changing) bir istek göndertmesidir. Saldırının özü şudur: saldırgan isteği kendisi göndermez; kurbanın tarayıcısını, kurbanın adına o isteği göndermeye kandırır. Yani saldırgan asla kurbanın oturum bilgisini (session cookie, token vb.) görmez veya çalmaz. Onun ihtiyacı olan tek şey, tarayıcının bir isteği yaparken kimlik doğrulama bilgilerini otomatik olarak eklemesidir.

Bu ayrım kritik. XSS (Cross-Site Scripting) saldırganın hedef sitede kod çalıştırmasıdır; CSRF ise saldırganın hiçbir kod çalıştırmadan, sadece tarayıcının otomatik davranışını sömürmesidir. CSRF'e bu yüzden bazen "confused deputy" (kafası karışmış vekil) saldırısı da denir: tarayıcı, kimlik bilgilerini taşıyan yetkili bir vekildir; saldırgan bu vekilin yetkisini, vekilin kendisi farkında olmadan kullanır.

Tipik sonuç: kurbanın parolasının değiştirilmesi, e-posta adresinin saldırganınkiyle değiştirilmesi (hesap ele geçirmenin klasik yolu), para transferi, yönetici hesabı ekleme, ayar değiştirme. CSRF durum değiştiren işlemleri hedefler; salt okuma yapan bir isteği tetiklemenin CSRF açısından bir anlamı yoktur çünkü saldırgan yanıtı zaten okuyamaz (Same-Origin Policy engeller).

## Kök Neden: Neden Böyle Oluyor?

CSRF'in kök nedeni tek bir tasarım kararında yatar: **tarayıcı, bir origin'e giden isteklerde o origin'e ait cookie'leri, isteği hangi sitenin başlattığından bağımsız olarak otomatik ekler (ambient authority).** Yani `banka.com` için oturum cookie'niz varsa, `banka.com`'a giden her istekte bu cookie eklenir; isteği `banka.com`'un kendi sayfası mı yoksa `saldirgan.com`'daki bir `<form>` mu tetiklemiş, tarayıcının umurunda değildir. Kimlik doğrulaması "ortamda" (ambient) durur; isteğin niyetiyle ilişkilendirilmemiştir.

Bunu daha derinden anlamak için iki tarayıcı mekanizmasını yan yana koymak gerekir:

**Same-Origin Policy (SOP)** JavaScript'in başka bir origin'in yanıtını *okumasını* engeller. Ama SOP, isteğin *gönderilmesini* engellemez. `<form>`, `<img>`, `<script>`, `<link>` gibi etiketler tarih boyunca siteler arası (cross-origin) istek yapabilir; web'in çalışması için bu gereklidir (bir CDN'den resim çekmek, bir başka siteye link vermek gibi). Dolayısıyla saldırgan yanıtı okuyamaz ama isteği gönderttirebilir. CSRF tam olarak bu boşlukta yaşar: **isteği yaptırabiliyorum, yanıtı okuyamıyorum ama durum değiştiren bir işlem için yanıtı okumama gerek de yok.**

Buradan çıkan temel prensip: Sunucu, gelen bir isteğin **kimden geldiğini** (cookie sayesinde) doğrulayabiliyor ama **isteğin gerçekten uygulamanın kendi arayüzünden, kullanıcının kastıyla başlatıldığını** doğrulayamıyor. CSRF savunmalarının tamamı aslında bu ikinci soruyu cevaplamaya çalışır: "Bu istek gerçekten benim sayfamdan mı geldi, yoksa başka bir origin'in kandırdığı tarayıcıdan mı?"

Neden özellikle cookie tabanlı oturumlar risklidir? Çünkü cookie tarayıcı tarafından otomatik ve şeffaf biçimde eklenir. Buna karşın, kimlik doğrulama bilgisini `Authorization: Bearer ...` başlığında taşıyan ve bu başlığı JavaScript'in elle eklediği bir uygulama, doğası gereği büyük ölçüde CSRF'e dirençlidir: çünkü saldırganın sayfasındaki JavaScript, cross-origin bir isteğe kurbanın token'ını ekleyemez (token'a erişimi yoktur ve tarayıcı bu başlığı otomatik eklemez). Kök nedeni anlamak, savunmanın da nereden geleceğini gösterir.

## Somut Örnek

Diyelim ki `banka.com` para transferini şöyle bir istekle yapıyor:

```
POST /transfer HTTP/1.1
Host: banka.com
Content-Type: application/x-www-form-urlencoded
Cookie: session=oturum_kimligi

alici=IBAN123&miktar=10000
```

Bu uygulamada CSRF koruması yoksa, saldırgan `saldirgan.com` üzerinde şu HTML'i barındırır:

```html
<form action="https://banka.com/transfer" method="POST" id="f">
  <input type="hidden" name="alici" value="SALDIRGAN_IBAN">
  <input type="hidden" name="miktar" value="10000">
</form>
<script>document.getElementById('f').submit();</script>
```

Kurban `banka.com`'da açık oturumu varken saldırganın gönderdiği bir linke tıklar (veya bu sayfa bir `<iframe>`, bir reklam, bir e-posta içindeki bir tuzak olabilir). Sayfa yüklenir yüklenmez form otomatik gönderilir. Tarayıcı `banka.com`'a giden bu isteğe `session` cookie'sini otomatik ekler. Sunucu isteği geçerli bir oturumdan geliyormuş gibi görür ve parayı transfer eder. Kurban hiçbir şey yazmadı, hiçbir onay vermedi; sadece yanlış sayfayı açtı.

GET tabanlı durum değiştiren işlemler ise en tehlikeli hatadır. Eğer uygulama `https://banka.com/transfer?alici=X&miktar=1000` gibi bir GET isteğiyle işlem yapıyorsa, saldırganın tek yapması gereken bir `<img src="...">` etiketi yerleştirmektir. Kullanıcı bir foruma yapıştırılan bu görseli gördüğü an istek gider. Bu yüzden **durum değiştiren hiçbir işlem asla GET ile yapılmamalıdır** — bu HTTP semantiğinin de gereğidir (GET güvenli/safe ve idempotent olmalı).

## Sömürü Mantığı ve Savunma: İkisi Birlikte

CSRF'i savunmak için önce saldırganın hangi kısıtlar altında çalıştığını netleştirmek gerekir. Saldırganın gücü ve sınırları şunlardır:

- **Yapabildiği:** Kurbanın tarayıcısından hedef origin'e istek göndertmek; bu isteğe cookie'lerin otomatik eklenmesini sağlamak; `<form>` ile POST yapmak; basit Content-Type'larla (`application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`) gövde göndermek.
- **Yapamadığı:** Yanıtı okumak (SOP engeller); bir yanıttaki gizli token'ı çıkarıp yeni isteğe koymak; keyfi bir custom HTTP başlığı (`X-Requested-With` gibi) eklemek (bu, CORS preflight tetikler ve sunucu izin vermedikçe istek gitmez); `Content-Type: application/json`'u basit bir form ile göndermek.

Savunmalar tam olarak saldırganın bu "yapamadığı" listesini istismar eder. Her savunma, isteğe saldırganın taklit edemeyeceği bir kanıt ekler.

### 1. Synchronizer Token Pattern (Anti-CSRF Token)

**Mantık:** Sunucu, her oturum (veya her form) için tahmin edilemez, kriptografik olarak güçlü rastgele bir token üretir. Bu token'ı sayfaya, formun gizli bir alanına gömer. Kullanıcı formu gönderdiğinde token istekle birlikte döner. Sunucu, gelen token ile oturumda sakladığı beklenen token'ı karşılaştırır. Eşleşmezse istek reddedilir.

**Neden çalışır:** Saldırgan bu token'ı bilemez. Çünkü token'ı öğrenmesi için `banka.com`'daki sayfayı okuyup token'ı çıkarması gerekir; ama SOP, saldırganın sayfasındaki JavaScript'in `banka.com`'un yanıtını okumasını engeller. Saldırgan formunu her ne kadar gönderebilse de, o forma doğru token'ı koyamaz. Böylece savunma, kök nedendeki eksik parçayı — "bu istek gerçekten benim sayfamdan mı geldi" sorusunu — token'ın varlığıyla cevaplar.

**Kritik ayrıntılar ve yaygın hatalar:**
- Token karşılaştırması **timing-safe** (sabit zamanlı) yapılmalıdır; naif string karşılaştırması timing attack'e zemin hazırlayabilir.
- Token yeterince entropili olmalı ve tahmin edilemez bir CSPRNG'den (cryptographically secure random) üretilmelidir; `rand()` gibi zayıf kaynaklar kullanılmamalı.
- Token **URL'de (query string) taşınmamalıdır**; Referer başlığı, tarayıcı geçmişi, sunucu logları yoluyla sızabilir. Gövdede veya bir custom başlıkta taşınmalı.
- Token'ın sadece varlığı değil, oturumla bağının da doğrulanması gerekir; aksi halde saldırgan kendi geçerli token'ını kurbanın oturumuna monte etmeye çalışabilir (token fixation).

**Double Submit Cookie** bu desenin durum tutmayan (stateless) bir çeşididir: token hem bir cookie'de hem de istek gövdesinde/başlığında gönderilir; sunucu ikisinin eşitliğini kontrol eder, sunucuda saklamaya gerek kalmaz. Ancak bu yöntem naif uygulandığında zayıftır: saldırgan alt domain (subdomain) üzerinden veya bir cookie enjeksiyonu ile cookie'yi set edebiliyorsa iki değeri de kendi bildiği bir değere sabitleyerek korumayı atlatabilir. Bu yüzden double submit token'ının imzalanması (HMAC ile oturuma bağlanması) önerilir; buna "signed double submit" denir.

### 2. SameSite Cookie Özniteliği

**Mantık:** CSRF'in kök nedeni cookie'nin cross-site isteklere otomatik eklenmesiydi. `SameSite` özniteliği tam olarak bu davranışı denetler. Tarayıcıya "bu cookie'yi hangi durumlarda cross-site isteklere ekle" talimatını verir.

- **`SameSite=Strict`:** Cookie yalnızca isteğin kaynağı da aynı site olduğunda gönderilir. Cross-site hiçbir istekte (başka bir siteden gelen link tıklaması dahil) cookie eklenmez. En güçlü koruma ama kullanıcı deneyimini bozabilir: kullanıcı bir dış linkle sitenize geldiğinde oturumu kapalıymış gibi görünür.
- **`SameSite=Lax`:** Cookie, cross-site GET navigasyonlarında (üst düzey sayfa geçişi, adres çubuğuna yazma, link tıklama) gönderilir ama cross-site POST, `<img>`, `<iframe>`, `fetch`, form-POST gibi isteklerde gönderilmez. Bu, kullanılabilirlik ile güvenlik arasında iyi bir denge kurar ve modern tarayıcıların çoğunda cookie için varsayılan davranıştır.
- **`SameSite=None`:** Cookie her cross-site istekte gönderilir (eski davranış). Bu değer kullanılırsa mutlaka `Secure` bayrağıyla birlikte olmalıdır; CSRF açısından koruma sağlamaz.

**Neden tek başına yeterli değil — ve buradaki önemli nüanslar:**

`SameSite=Lax`'ın klasik POST-CSRF'i büyük ölçüde durdurduğu doğrudur; saldırganın otomatik gönderdiği cross-site form-POST'a cookie eklenmez. Ancak SameSite'a *tek savunma* olarak güvenmek hatadır, birkaç nedenle:

- **GET ile durum değiştirme:** Lax, cross-site top-level GET navigasyonlarında cookie'yi yollar. Eğer uygulamanız durum değiştiren bir GET endpoint'ine sahipse, saldırgan kullanıcıyı o URL'e yönlendirerek Lax korumasını atlatır. Bu yüzden SameSite, "durum değiştiren işlemler GET olmasın" kuralıyla birlikte anlam kazanır.
- **Same-site ama cross-origin:** SameSite "site" bazında çalışır (eTLD+1), origin bazında değil. Yani `alt.banka.com` ile `banka.com` aynı "site" sayılır. Bir alt domain'de XSS veya kontrol edilemeyen içerik varsa, istek same-site sayılıp cookie eklenir ve SameSite koruması devreye girmez.
- **Tarayıcı ve varsayılan tutarsızlıkları:** SameSite belirtilmemiş cookie'lerin varsayılan davranışı tarayıcıdan tarayıcıya ve zamanla değişebilir; ayrıca bazı tarayıcılar yeni set edilen cookie'ler için kısa bir süre "Lax" istisnası uygulayabilir. Güvenliği tarayıcının varsayılanına bırakmak yerine değeri açıkça belirtmek gerekir.

Doğru yaklaşım: SameSite'ı **derinlemesine savunmanın (defense in depth) bir katmanı** olarak kullan, token savunmasının yerine değil. `SameSite=Lax` (veya uygunsa `Strict`) + anti-CSRF token birlikte kullanıldığında koruma çok daha sağlamdır.

### 3. Origin ve Referer Doğrulaması

**Mantık:** Sunucu, gelen durum değiştiren isteklerde `Origin` başlığını (yoksa `Referer`) kontrol eder ve bunun beklenen kendi origin'iyle eşleşip eşleşmediğine bakar. Cross-site bir istekte `Origin` başlığı saldırganın origin'ini taşır; saldırgan bu başlığı tarayıcıda kendi lehine değiştiremez (forbidden header'dır, JavaScript ile yazılamaz).

**Neden değerli:** `Origin` başlığı güvenilirdir çünkü tarayıcı tarafından kontrol edilir ve saldırganın sayfasından sahte bir değere ayarlanamaz. Modern uygulamalarda özellikle POST/PUT/DELETE isteklerinde Origin doğrulaması, token'a ek pratik ve güçlü bir katmandır.

**Dikkat edilecek noktalar:**
- `Origin` bazı durumlarda gelmeyebilir (bazı eski istemciler, bazı GET istekleri). `Origin` yoksa `Referer`'a düşmek, o da yoksa isteği reddetmek makul bir politikadır — ama bazı gizlilik ayarları Referer'ı da temizleyebileceğinden, tek savunma yapmak yerine token ile birleştirmek gerekir.
- Doğrulama **allowlist** (izin listesi) mantığıyla yapılmalı; string içinde `banka.com` geçiyor mu diye bakmak (`saldirgan-banka.com` veya `banka.com.saldirgan.com` gibi baypaslara açık) tehlikelidir. Tam origin eşleşmesi aranmalıdır.

## JSON API Dirençliliği

Modern uygulamaların çoğu tarayıcıdan `fetch`/`XMLHttpRequest` ile `Content-Type: application/json` göndererek JSON API'lerle konuşur. Buradaki tablo klasik form-tabanlı CSRF'ten farklıdır ve iyi anlaşılması gerekir.

**Neden JSON API'ler doğal olarak daha dirençlidir:** Bir HTML `<form>`, gövdeyi yalnızca üç "basit" (CORS terminolojisinde *simple*) Content-Type ile gönderebilir: `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`. Formla `application/json` Content-Type'ı üretilemez. Eğer API'niz **isteğin `Content-Type: application/json` olmasını zorunlu kılıyorsa**, saldırganın basit bir formla bu isteği taklit etmesi mümkün olmaz. Saldırgan bunu ancak `fetch` ile cross-origin çağırarak deneyebilir; ama `application/json` Content-Type'ı isteği "non-simple" yaptığı için tarayıcı önce bir **CORS preflight** (`OPTIONS`) isteği gönderir. Sunucu preflight'a saldırganın origin'ine izin veren bir yanıt dönmezse, tarayıcı gerçek isteği hiç göndermez. Böylece saldırı daha başlamadan durur.

Aynı mantık **custom başlık zorunluluğu** için de geçerlidir. Örneğin API'niz her istekte `X-Requested-With: XMLHttpRequest` veya benzeri bir custom başlık arıyorsa: `<form>` custom başlık ekleyemez ve `fetch` ile custom başlık eklemek de isteği non-simple yapıp preflight tetikler. Preflight'ı geçemeyen saldırgan isteği yollayamaz. Bu, eski ama hâlâ etkili bir CSRF savunmasıdır.

**Ancak buradaki tuzaklar — "JSON API'm var, o yüzden CSRF'ten muafım" yanılgısı:**

1. **Content-Type gerçekten zorunlu mu?** Birçok framework, gövdeyi Content-Type'a bakmadan ayrıştırır (parse eder). Eğer sunucunuz `text/plain` gövdesini de JSON olarak ayrıştırıyorsa, saldırgan `<form>` ile `text/plain` Content-Type'lı, gövdesi geçerli bir JSON olan bir istek gönderebilir. Bu preflight tetiklemez (çünkü `text/plain` simple'dır) ve cookie'niz otomatik eklenir. Bu klasik bir baypastır. **Savunma:** Sunucu, `Content-Type`'ın tam olarak `application/json` olmasını *katı* biçimde doğrulamalı; öyle değilse isteği reddetmelidir.

2. **CORS yanlış yapılandırılmışsa preflight koruması çöker.** Eğer sunucu `Access-Control-Allow-Origin`'i yansıtmalı (reflected) olarak gelen Origin'e geri veriyor ve `Access-Control-Allow-Credentials: true` diyorsa, saldırganın origin'i de "izinli" hale gelir; preflight geçer, istek gider, cookie eklenir. Bu durumda CORS'un koruyucu etkisi tamamen ortadan kalkar, hatta CORS bir saldırı vektörüne dönüşür. **Savunma:** İzin verilen origin'ler sıkı bir allowlist olmalı; `*` ile `credentials: true` asla birlikte kullanılmamalı; Origin'i körü körüne yansıtmamalı.

3. **Cookie ile kimlik doğrulama sürdüğü sürece risk sürer.** JSON API dirençliliğinin çoğu, "saldırgan cookie'li isteği kolayca oluşturamaz" mantığına dayanır. Ama kimlik doğrulamayı cookie yerine `Authorization: Bearer` başlığıyla yapan ve bu başlığı istemci JavaScript'inin elle eklediği bir mimari, CSRF'e neredeyse tümüyle bağışıktır — çünkü tarayıcı bu başlığı otomatik eklemez ve saldırganın token'a erişimi yoktur. Buradaki maliyet, token'ı XSS'ten koruma sorumluluğunun artmasıdır (token'ı `localStorage`'da tutmak XSS'e karşı daha kırılgandır). Yani CSRF ile XSS arasındaki savunma dengesini bilinçli kurmak gerekir.

Özetle JSON API'ler CSRF'e daha dirençlidir ama muaf değildir; bu direnç, "Content-Type katı doğrulaması + doğru CORS + gerekiyorsa token/custom başlık" üçlüsüyle güvence altına alınmalıdır.

## Yaygın Hatalar

- **Durum değiştiren işlemleri GET ile yapmak.** Bu, `<img src>` ile tetiklenebilen, SameSite=Lax'ın bile koruyamadığı en temel hatadır. GET güvenli/idempotent olmalı, yan etki üretmemelidir.
- **CSRF token'ını URL query string'inde taşımak.** Referer başlığı, loglar ve tarayıcı geçmişi yoluyla sızar. Gövdede veya custom başlıkta taşınmalı.
- **SameSite'ı tek savunma sanmak.** Alt domain riskleri, GET endpoint'leri ve tarayıcı tutarsızlıkları nedeniyle tek başına yetmez.
- **Double submit cookie'yi imzasız kullanmak.** Alt domain'den veya cookie enjeksiyonuyla cookie sabitlenebiliyorsa koruma çöker; HMAC ile oturuma bağlanmalı.
- **Content-Type'ı katı doğrulamamak.** `text/plain` veya boş Content-Type'lı gövdeyi JSON olarak ayrıştıran API, form tabanlı CSRF'e açıktır.
- **CORS'u gevşek yapılandırmak.** Origin'i yansıtan + credentials'a izin veren yapılandırma, preflight korumasını yok eder.
- **Token'ı naif string karşılaştırmasıyla doğrulamak.** Sabit zamanlı (timing-safe) karşılaştırma kullanılmalı.
- **CSRF'i XSS ile karıştırmak/yeterli sanmak.** XSS varsa CSRF savunmaları anlamsızlaşır: XSS ile saldırgan zaten sayfada kod çalıştırıp token'ı okuyabilir. CSRF savunması, XSS savunmasının yerini tutmaz; ikisi ayrı ayrı gereklidir.
- **Login formunda CSRF korumasını atlamak.** "Login CSRF" gerçek bir tehdittir: saldırgan kurbanı, saldırganın hesabına giriş yaptırarak kurbanın verilerini saldırganın hesabında biriktirmesine yol açabilir. Login akışı da korunmalı.
- **Salt okuma endpoint'leri sanılan işlemlerin aslında yan etki üretmesi.** "Görüntüle" gibi görünen ama arkada bir işlem tetikleyen endpoint'ler gözden kaçar.

## En İyi Pratikler

1. **Katmanlı savunma (defense in depth) uygula.** Tek bir mekanizmaya güvenme. Pratik ve sağlam bir kombinasyon: `SameSite=Lax` (veya uygunsa `Strict`) cookie + anti-CSRF token (synchronizer veya signed double submit) + durum değiştiren isteklerde `Origin`/`Referer` doğrulaması.
2. **HTTP semantiğine uy.** Durum değiştiren her işlem POST/PUT/PATCH/DELETE olsun; GET yalnızca güvenli/idempotent okumalar için. Bu, birçok CSRF vektörünü tasarım gereği kapatır.
3. **Framework'ünün hazır CSRF korumasını kullan.** Olgun web framework'lerinin çoğu test edilmiş anti-CSRF mekanizmaları sunar. Kendi kripto/kod'unu yazmaktansa bunları doğru yapılandır. "Kendi güvenlik primitifini yazma" ilkesi burada da geçerli.
4. **JSON API'lerde Content-Type'ı katı doğrula.** Yalnızca `application/json` kabul et; `text/plain` ve form Content-Type'larını durum değiştiren endpoint'lerde reddet.
5. **CORS'u sıkı yapılandır.** İzinli origin'leri açık bir allowlist ile tut; Origin'i yansıtma; `credentials: true` ile `*` origin'i asla birleştirme.
6. **Token'ları güvenli üret ve doğrula.** CSPRNG kaynaklı, yeterli entropili, oturuma bağlı token; sabit zamanlı karşılaştırma; token'ı gövdede/başlıkta taşı, URL'de değil.
7. **Kimlik doğrulama mimarisini bilinçli seç.** Cookie tabanlı oturumda CSRF savunmasına yatırım yap; `Authorization` başlığı tabanlı token kullanıyorsan CSRF riski düşer ama XSS'e karşı token saklama stratejine ekstra özen göster.
8. **Kritik işlemlerde ek doğrulama iste.** Parola değişimi, e-posta değişimi, para transferi gibi yüksek riskli işlemlerde mevcut parolayı yeniden isteme veya adım doğrulama (step-up authentication) ekle; bu, tüm CSRF savunmaları aşılsa bile ikinci bir bariyer sağlar.
9. **Login ve logout dahil tüm durum değiştiren akışları koru.** Login CSRF ve logout CSRF gerçek tehditlerdir.
10. **Güvenliği açıkça belirt, varsayılana güvenme.** SameSite gibi öznitelikleri elle ata; `Secure` ve `HttpOnly` bayraklarını oturum cookie'lerinde kullan (`HttpOnly` CSRF'i doğrudan çözmez ama oturum cookie'sinin XSS ile çalınmasını engelleyerek toplam güvenliği artırır).

## Kapanış

CSRF, karmaşık bir kripto zafiyeti değil, web'in temel bir tasarım kararının — cookie'lerin ambient authority olarak otomatik eklenmesinin — mantıksal bir sonucudur. Bu yüzden savunması da tek bir sihirli çözümden değil, "bu istek gerçekten benim uygulamamın kastıyla mı geldi" sorusunu güvenilir biçimde cevaplayan katmanlardan oluşur: taklit edilemeyen bir token, cookie'nin cross-site davranışını kısan SameSite, saldırganın sahtelemediği Origin başlığı ve JSON API'lerde preflight ile Content-Type katılığı. Bu katmanları birlikte ve doğru yapılandırmak, CSRF'i pratikte çözülmüş bir problem haline getirir.
