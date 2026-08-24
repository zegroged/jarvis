# Oturum Yönetimi Zafiyetleri

## Giriş: Oturum Nedir ve Neden Kritiktir

HTTP protokolü tasarımı gereği "durumsuz" (stateless) bir protokoldür. Yani sunucu, art arda gelen iki isteğin aynı kullanıcıya ait olduğunu kendiliğinden bilemez. Bir kullanıcı giriş (login) yaptığında, kimliğinin sonraki her istekte yeniden doğrulanması gerekir; ama şifreyi her istekte tekrar sormak pratik değildir. İşte bu boşluğu **oturum yönetimi** (session management) doldurur: kullanıcı bir kez kimlik doğrulaması yapar, sunucu ona benzersiz bir **oturum kimliği** (session ID) verir ve bu kimlik sonraki isteklerde -genellikle bir cookie içinde- taşınır.

Bu noktada kritik bir gerçeği kavramak gerekir: Oturum kimliği, kullanıcının kimliğinin kendisidir. Şifreyi bilmek nasıl bir kullanıcı olmak demekse, o kullanıcının geçerli oturum kimliğini ele geçirmek de -en azından oturum süresince- o kullanıcı olmak demektir. Bu yüzden oturum yönetimindeki bir zafiyet, çoğu zaman "yetkisiz erişim" ile eşdeğerdir. Saldırgan şifreyi kırmaya hiç ihtiyaç duymadan, doğrudan doğrulanmış kimliğin taşıyıcısını çalar veya taklit eder.

Bu makalede oturum yönetiminin dört temel zafiyet ekseni ele alınacaktır: **session fixation**, **tahmin edilebilir oturum kimlikleri**, **cookie güvenlik bayrakları** ve **timeout / oturum yaşam döngüsü** yönetimi. Her birinde önce kök nedeni, sonra hem istismar mantığını hem de savunmayı işleyeceğiz.

---

## Session Fixation (Oturum Sabitleme)

### Tanım ve Kök Neden

Session fixation, saldırganın **kurbanın oturumunu, saldırganın önceden bildiği bir oturum kimliğiyle başlatmaya** zorladığı bir saldırı sınıfıdır. İsminin de işaret ettiği gibi saldırgan, oturum kimliğini kurban giriş yapmadan önce "sabitler" (fixate eder).

Bu zafiyetin kök nedeni çoğu zaman şu tasarım hatasıdır: **uygulama, kimlik doğrulama başarılı olduğunda oturum kimliğini yenilemez.** Yani kullanıcı anonimken sahip olduğu oturum kimliği, giriş yaptıktan sonra da aynı kalır. Anonim durumdaki bir kimliğin ele geçirilmesi tek başına değersizdir -henüz bir yetki taşımaz- ama eğer aynı kimlik, giriş sonrası ayrıcalıklı oturuma yükseltiliyorsa, saldırgan o kimliği önceden kurbana enjekte ederek giriş sonrası yetkiyi de devralır.

Buradaki asıl mantıksal kusur bir "güven sınırı" (trust boundary) ihlalidir: Yetki seviyesi değiştiğinde (anonim -> kimlik doğrulanmış, veya normal kullanıcı -> yönetici) taşıyıcı kimliğin de değişmesi gerekir. Değişmezse, düşük güvenli bağlamda üretilmiş bir kimlik yüksek güvenli bağlama sızar.

### İstismar Mantığı

Klasik bir fixation senaryosu şöyle işler:

1. Saldırgan hedef siteyi ziyaret eder ve kendisi için geçerli ama henüz giriş yapılmamış bir oturum kimliği alır. Diyelim `SESSIONID=abc123`.
2. Saldırgan, bu kimliği kurbana zorla kabul ettirmenin bir yolunu bulur. En klasik yöntem, oturum kimliğini URL parametresi olarak taşıyan uygulamalarda kurbana `https://banka.example/login?SESSIONID=abc123` gibi bir bağlantı göndermektir.
3. Kurban bu bağlantıya tıklar ve `abc123` kimliğiyle giriş yapar. Uygulama giriş sonrası kimliği yenilemediği için, kurbanın kimlik doğrulanmış oturumu hâlâ `abc123`'tür.
4. Saldırgan zaten `abc123`'ü bildiğinden, kendi tarayıcısına bu kimliği koyar ve kurbanın oturumunu paylaşır.

URL üzerinden taşımanın giderek nadirleşmesiyle, saldırganlar cookie enjeksiyonuna yöneldi. Eğer saldırgan alt alan adı (subdomain) üzerinde bir XSS veya kontrol sağlayabiliyorsa, `Domain` kapsamı geniş bir cookie yazarak kurbanın tarayıcısına istediği oturum kimliğini sabitleyebilir. Bu, session fixation ile cookie güvenliği konularının nasıl iç içe geçtiğini gösterir.

### Savunma

Session fixation'a karşı en temel ve en etkili savunma tek cümleyle özetlenebilir: **Yetki seviyesi her yükseldiğinde oturum kimliğini yeniden üret.** Pratikte bu şu anlama gelir:

- Başarılı giriş anında eski oturum kimliğini geçersiz kıl ve tamamen yeni bir kimlik ata. Çoğu framework bunun için özel bir fonksiyon sunar (örneğin bazı framework'lerde "session regenerate" veya "renew" adında bir çağrı). Önemli olan yalnızca yeni bir kimlik üretmek değil, eski oturum verisini de yeni kimliğe güvenli biçimde taşıyıp eskisini iptal etmektir.
- Yalnızca girişte değil, ayrıcalık yükselten diğer geçişlerde de (örneğin normal kullanıcıdan yönetici paneline geçiş, hassas işlem öncesi yeniden kimlik doğrulama) kimliği yenilemeyi düşün.
- Oturum kimliğini asla URL'de taşıma. Yalnızca cookie üzerinden taşı; böylece bağlantı paylaşımıyla kimlik enjeksiyonu yolu baştan kapanır.
- Sunucunun, istemcinin ürettiği/önerdiği oturum kimliklerini kabul etmemesini sağla. Oturum kimliği yalnızca sunucu tarafından üretilmeli; sunucu bilmediği bir kimlikle gelen isteğe yeni ve taze bir oturum atamalıdır, o kimliği "tanıyormuş" gibi davranmamalıdır.

---

## Tahmin Edilebilir Oturum Kimlikleri

### Tanım ve Kök Neden

Oturum kimliği, bir kimliğin taşıyıcısı olduğuna göre, **tahmin edilemez** olmalıdır. Eğer bir saldırgan geçerli oturum kimliklerini makul bir çabayla tahmin edebiliyor veya numaralandırabiliyorsa (session prediction / brute force), kurbanı hiç hedef almadan, doğrudan başka kullanıcıların oturumlarını "bularak" ele geçirebilir.

Kök neden neredeyse her zaman **yetersiz entropi**dir. Entropi, kimliğin içerdiği gerçek rastgeleliğin ölçüsüdür. Sorun genellikle şu üç kaynaktan biridir:

1. **Sıralı veya öngörülebilir üretim:** Oturum kimliğinin bir sayaçtan, kullanıcı kimliğinden, zaman damgasından (timestamp) veya bunların basit birleşiminden türetilmesi. Böyle bir kimlik teknik olarak "benzersiz" olabilir ama "tahmin edilemez" değildir. Benzersizlik ile tahmin edilemezlik farklı özelliklerdir; oturum güvenliği ikincisini gerektirir.
2. **Zayıf rastgele sayı üreteci kullanımı:** Kriptografik olmayan bir sözde-rastgele üreteç (non-cryptographic PRNG) kullanmak. Bu tür üreteçler hız için tasarlanmıştır, öngörülemezlik için değil. Yeterince çıktı gözlemleyen bir saldırgan iç durumu geri hesaplayıp gelecekteki değerleri tahmin edebilir. Oturum kimlikleri mutlaka **CSPRNG** (kriptografik olarak güvenli sözde-rastgele üreteç) ile üretilmelidir.
3. **Yetersiz uzunluk:** Kimlik gerçekten rastgele olsa bile, çok kısaysa saldırgan tüm alanı deneyerek (brute force) geçerli oturumlara denk gelebilir. Genel kabul gören yaklaşım, oturum kimliğinin en az 128 bit civarı gerçek entropi taşımasıdır; bu, kaba kuvvet denemesini pratik olarak imkânsız kılar. (Not: Kesin bit sayısı ve öneriler kaynaktan kaynağa değişebilir; buradaki 128 bit yaygın bir alt sınır referansıdır, mutlak bir dogma değil.)

### İstismar Mantığı

Tahmin edilebilirliğin nasıl istismar edildiğini kavramanın en iyi yolu bir örnek düşünmektir. Diyelim bir uygulama oturum kimliğini `md5(kullanıcı_id + kayıt_zamanı)` biçiminde üretiyor. Bu kimlik uzun ve rastgele "görünür" -bir hash çıktısıdır- ama girdileri tahmin edilebilirse hash de tahmin edilebilir. Saldırgan hedef kullanıcının kayıt zamanını kabaca bilebilir (örneğin profil sayfasından) ve saniye saniye deneyerek hash uzayını çok küçük bir aralığa indirger. Hash'in "rastgele görünmesi" onu güvenli yapmaz; güvenliği belirleyen, girdilerin entropisidir.

Sıralı kimliklerde durum daha da vahimdir. Saldırgan kendi oturum kimliğini alır, bir öncekini ve bir sonrakini dener; sistemli biçimde artırıp azaltarak başka kullanıcıların aktif oturumlarını numaralandırabilir. Bu, otomatik bir betikle (script) dakikalar içinde binlerce oturumu tarayabilir.

### Savunma

- Oturum kimliğini **daima bir CSPRNG ile** üret. Uygulama seviyesinde kendi kimlik üretim mantığını yazmaktan kaçın; olgun framework'lerin oturum motorları bu işi doğru yapacak şekilde tasarlanmıştır. "Kendi kripton­unu yazma" ilkesi burada da geçerlidir.
- Kimliği **anlamsız ve opak** (opaque) tut. İçinde kullanıcı kimliği, rol, zaman gibi türetilebilir bilgi barındırma. Oturum kimliği yalnızca sunucu tarafındaki bir kayda işaret eden rastgele bir işaretçi olmalıdır.
- **Yeterli uzunluk ve entropi** sağla. Sadece uzun görünen değil, gerçekten yüksek entropili bir kimlik kullan.
- Sunucu tarafında **anomali tespiti** kur: kısa sürede çok sayıda geçersiz oturum kimliği denemesi, aktif bir numaralandırma saldırısının işaretidir; oran sınırlama (rate limiting) ve alarm mekanizmalarıyla bunu yakala.

---

## Cookie Güvenlik Bayrakları

### Neden Bayraklar Önemli

Oturum kimliği güçlü üretilmiş ve girişte yenileniyor olsa bile, taşındığı cookie yanlış yapılandırılmışsa tüm bu çaba boşa gider. Cookie bayrakları (cookie attributes/flags), tarayıcıya bu cookie'nin **ne zaman, nereye ve nasıl** gönderileceğini söyleyen kontrol düğmeleridir. Yanlış ayarlanmış bir bayrak, güvenli üretilmiş bir oturum kimliğini bile saldırgana açık hâle getirir. Bu bölümde ana bayrakları ve her birinin hangi saldırıyı engellediğini akıl yürüterek inceleyelim.

### HttpOnly

`HttpOnly` bayrağı işaretlenmiş bir cookie, tarayıcıdaki JavaScript'ten (`document.cookie`) **okunamaz**. Peki bu neden kritik? Çünkü bir sitede XSS (cross-site scripting) zafiyeti varsa, saldırganın enjekte ettiği JavaScript'in yapacağı ilk işlerden biri genellikle oturum cookie'sini okuyup kendi sunucusuna sızdırmaktır. `HttpOnly`, bu doğrudan hırsızlık yolunu kapatır.

Önemli bir nüansı vurgulamak gerekir: `HttpOnly`, XSS'i **engellemez**; yalnızca XSS'in oturum cookie'sini çalmasını zorlaştırır. XSS hâlâ kurbanın adına istek yapabilir. Yani `HttpOnly`, bir savunmanın tamamı değil, katmanlı savunmanın (defense in depth) bir katmanıdır. Ama oturum cookie'leri için neredeyse istisnasız açık olmalıdır -meşru bir uygulamanın oturum kimliğini JavaScript'ten okumaya ihtiyacı yoktur.

### Secure

`Secure` bayrağı işaretli bir cookie, tarayıcı tarafından **yalnızca şifreli (HTTPS) bağlantı üzerinden** gönderilir. Bu neden gerekli? `Secure` olmadan, kullanıcı yanlışlıkla bir `http://` bağlantısına tıklarsa, tarayıcı oturum cookie'sini şifresiz olarak ağa yollar. Aynı ağdaki bir saldırgan (örneğin halka açık Wi-Fi'de) bu trafiği dinleyerek (sniffing) cookie'yi düz metin olarak yakalayabilir. `Secure` bayrağı, cookie'nin asla şifresiz kanaldan çıkmamasını garanti eder.

Uygulamanın tamamının HTTPS zorunlu (ve tercihen HSTS ile pekiştirilmiş) olduğu bir dünyada bile `Secure` bayrağı önemlidir, çünkü karma içerik veya yanlış yapılandırılmış bir bağlantı ihtimaline karşı son bir emniyet kemeridir.

### SameSite

`SameSite` bayrağı, cookie'nin **siteler arası (cross-site) isteklerde** gönderilip gönderilmeyeceğini kontrol eder ve öncelikli olarak CSRF (cross-site request forgery) saldırılarına karşı bir savunma katmanıdır. Mantığı şudur: CSRF saldırısında, kötü niyetli bir site kurbanın tarayıcısını, kurbanın oturum açık olduğu başka bir siteye istek göndermeye kandırır. Tarayıcı otomatik olarak cookie'leri eklediği için istek "kurban adına" yetkili görünür. `SameSite`, tarayıcının cookie'yi bu tür siteler arası isteklere eklemesini kısıtlar.

Genel olarak üç davranış vardır:

- **Strict:** Cookie yalnızca aynı siteden gelen isteklerde gönderilir. En güvenli, ama başka bir siteden gelen meşru bir bağlantıyla girildiğinde kullanıcı oturumunun "açık gelmemesi" gibi kullanılabilirlik etkileri olabilir.
- **Lax:** Cookie, üst düzey gezinme (kullanıcının bir bağlantıya tıklayıp siteye gitmesi gibi) durumlarında gönderilir ama arka planda tetiklenen siteler arası isteklerde (form gönderimi, resim yükleme vb.) gönderilmez. Güvenlik ve kullanılabilirlik arasında makul bir dengedir ve birçok modern tarayıcıda varsayılana yakındır.
- **None:** Cookie her durumda gönderilir; bu modda cookie'nin `Secure` de olması gerekir. Yalnızca meşru siteler arası senaryolar (örneğin gömülü üçüncü taraf içerik) gerçekten gerektiriyorsa kullanılmalıdır.

Kritik uyarı: `SameSite` tek başına eksiksiz bir CSRF savunması **değildir.** Anti-CSRF token gibi ek mekanizmalarla birlikte, katmanlı olarak düşünülmelidir.

### Domain ve Path (Kapsam Bayrakları)

`Domain` ve `Path` bayrakları cookie'nin kapsamını belirler. Buradaki tehlike genellikle kapsamı gereğinden **geniş** tutmaktır. Örneğin cookie'yi `Domain=.example.com` ile tüm alt alan adlarına açmak, güvenilmeyen veya daha zayıf korunan bir alt alan adının (örneğin bir pazarlama mikro-sitesi) ele geçirilmesi durumunda oturum cookie'sinin de riske girmesi demektir. İlke şudur: cookie kapsamını, işlevin gerektirdiği **en dar** aralıkta tut. Bir cookie'yi ne kadar geniş paylaşırsan, saldırı yüzeyini o kadar büyütürsün.

### Bir Ek: Cookie Ön Ekleri

Bazı tarayıcılar, cookie adının belirli ön eklerle başlaması durumunda ek güvenlik garantileri uygular (örneğin cookie'nin `Secure` olması ve belirli kapsam kurallarına uyması zorunluluğu). Bu, tarayıcı düzeyinde ek bir sağlamlaştırma katmanı sunar. (Kesin ön ek adlarını ve davranışlarını uygulamadan önce güncel tarayıcı dokümantasyonundan doğrulamanı öneririm; ezberden ön ek yazmak yerine kavramı bilmek yeterlidir.)

---

## Timeout ve Oturum Yaşam Döngüsü

### Neden Oturumların Bir Sonu Olmalı

Bir oturum kimliği ne kadar güçlü üretilmiş olursa olsun, süresiz geçerli kaldığı sürece bir sorumluluktur. Timeout mantığının kök nedeni basittir: **Bir kimliğin ele geçirilmesi kaçınılmaz bir ihtimaldir; timeout, ele geçirilen kimliğin işe yarar kalacağı süreyi sınırlar.** Yani timeout, ihlal olmayacağını varsaymaz; ihlalin etkisini zamanla sınırlar. Bu, "varsayılan güvenlik" değil, "hasar sınırlama" düşüncesidir.

İki farklı timeout kavramını ayırmak önemlidir:

- **Hareketsizlik (idle / inaktivite) timeout'u:** Kullanıcı belirli bir süre hiçbir istek yapmazsa oturum sonlandırılır. Bu, ortak bir bilgisayarda oturumu açık unutan kullanıcıyı ve terk edilmiş bir oturumun ele geçirilme penceresini korur. Süre, uygulamanın hassasiyetine göre ayarlanır: bir bankacılık uygulamasında dakikalarla ölçülebilecek kadar kısa, düşük riskli bir uygulamada daha uzun olabilir.
- **Mutlak (absolute) timeout:** Oturum, ne kadar aktif olursa olsun, başlangıcından itibaren belirli bir azami süre sonra kesin olarak sonlandırılır. Bu, çalınmış bir kimliğin "sürekli aktif tutularak" sonsuza dek yaşatılmasını engeller. Sadece idle timeout'a güvenmek yetmez, çünkü saldırgan çaldığı oturumu periyodik istekler atarak canlı tutabilir; mutlak timeout bu kaçış yolunu kapatır.

### Sunucu Tarafı Geçersiz Kılma: Asıl Mesele

Burada çok yaygın ve tehlikeli bir yanılgıyı vurgulamak gerekir: **Oturumun bitmesi, sunucu tarafında geçersiz kılınması demektir; istemci tarafında cookie'yi silmek değil.**

Çıkış (logout) işlevini yalnızca tarayıcıdan cookie'yi silerek gerçekleştiren bir uygulama düşün. Kullanıcı "çıkış" yapar, cookie silinir, ama sunucu o oturum kimliğini hâlâ geçerli sayar. Eğer saldırgan kimliği daha önce kopyalamışsa (örneğin ağdan yakalayarak veya XSS ile), kullanıcı "çıkış" yaptıktan sonra bile o kimlikle erişmeye devam eder. Gerçek güvenlik, sunucunun ilgili oturum kaydını **aktif olarak yok etmesiyle** sağlanır; ondan sonra o kimlik kimin elinde olursa olsun işe yaramaz.

Aynı ilke timeout için de geçerlidir: cookie'nin son kullanma (expiry) tarihi yalnızca bir "öneridir" ve istemci ona uymayabilir; saldırgan süresi dolmuş bir cookie'yi bile elle isteğe ekleyebilir. Bu yüzden geçerlilik kararı her zaman sunucuda, oturum kaydının yaşına ve son erişim zamanına bakılarak verilmelidir.

### İyi Bir Oturum Yaşam Döngüsünün Bileşenleri

- **Anlamlı çıkış:** Çıkış, sunucu tarafında oturumu kesin olarak geçersiz kılmalı.
- **Kritik olaylarda toplu geçersiz kılma:** Şifre değişikliği, şüpheli etkinlik tespiti veya kullanıcının "diğer tüm cihazlardan çıkış yap" talebi gibi durumlarda, o kullanıcının ilgili tüm aktif oturumları geçersiz kılınabilmelidir. Bu, oturum kayıtlarını kullanıcıya bağlı biçimde tutmayı gerektirir.
- **Şifre değişikliğinde oturum tazeleme:** Kullanıcı şifresini değiştirdiğinde (özellikle hesabın ele geçirildiğinden şüphelenildiği için değiştiriyorsa), eski oturumların otomatik olarak sonlandırılması beklenen davranıştır.

---

## Yaygın Hatalar

Sahada tekrar tekrar karşılaşılan hataları bir arada görmek, bunlardan kaçınmayı kolaylaştırır:

1. **Girişte oturum kimliğini yenilememek.** Session fixation'ın birincil sebebidir. "Kullanıcı zaten bir oturuma sahipti, giriş yapınca aynısını kullanmaya devam etsin" düşüncesi tam da açığı yaratır.
2. **Çıkışta yalnızca cookie silmek, sunucu oturumunu bırakmak.** Kullanıcıya "çıktın" der ama saldırgana kapı açık kalır.
3. **Oturum kimliğini URL'de taşımak.** Bağlantı paylaşımı, tarayıcı geçmişi, `Referer` başlığı, sunucu logları -hepsi kimliğin sızma kanalıdır.
4. **Zayıf entropi / kendi kimlik üretim mantığını yazmak.** "Rastgele görünen" bir dize üretmek ile "kriptografik olarak öngörülemez" bir dize üretmek aynı şey değildir.
5. **Cookie bayraklarını eksik bırakmak.** `HttpOnly` yok -> XSS ile cookie hırsızlığı kolaylaşır. `Secure` yok -> ağ dinlemeyle sızma. `SameSite` yok -> CSRF yüzeyi genişler.
6. **Timeout'u yalnızca istemciye bırakmak veya hiç koymamak.** Süresiz oturum, çalınan kimliğin süresiz kullanımı demektir.
7. **Oturum kimliğinin içine hassas veri gömmek.** Kimliği çözülebilir hâle getirmek, hem bilgi sızıntısı hem de kurcalama (tampering) riski yaratır.
8. **Tek bir savunmaya güvenmek.** `SameSite` var diye anti-CSRF token'ı atlamak, `HttpOnly` var diye XSS'i önemsememek gibi. Her mekanizma bir katmandır, bütün değildir.

---

## En İyi Pratikler

Yukarıdaki tüm tartışmayı uygulanabilir bir kontrol listesine dönüştürelim:

- **Framework'ün oturum motorunu kullan.** Oturum kimliği üretimini, saklamayı ve doğrulamayı sıfırdan yazma; olgun kütüphaneler bu zor sorunları çoktan çözmüştür. Enerjini doğru yapılandırmaya harca, yeniden icat etmeye değil.
- **Girişte ve ayrıcalık yükselmelerinde kimliği yeniden üret.** Fixation'a karşı tek en etkili önlem budur.
- **Kimliği CSPRNG ile, yüksek entropili ve opak üret.** İçine anlam gömme; yalnızca sunucudaki bir kayda işaret eden rastgele bir işaretçi olsun.
- **Oturum cookie'lerini `HttpOnly`, `Secure` ve uygun bir `SameSite` değeriyle ayarla.** Kapsamı (`Domain`/`Path`) mümkün olan en dar tut.
- **Tüm trafiği HTTPS'e taşı** ve `Secure` bayrağını bununla pekiştir.
- **Hem idle hem mutlak timeout uygula.** Uygulamanın risk seviyesine göre süreleri ayarla; hassas uygulamalarda kısa tut.
- **Çıkış ve timeout'u sunucu tarafında gerçek geçersiz kılma olarak uygula.** İstemci tarafı temizliği yalnızca kozmetiktir.
- **Kritik olaylarda (şifre değişimi, ihlal şüphesi) oturumları toplu geçersiz kılabil.** Kullanıcıya "tüm cihazlardan çıkış" gibi bir kontrol sun.
- **Anormal oturum aktivitesini izle.** Numaralandırma denemeleri, ani IP/istemci değişiklikleri, çok sayıda geçersiz kimlik -bunlar erken uyarı işaretleridir.
- **Katmanlı düşün (defense in depth).** Hiçbir tek mekanizmayı "yeterli" varsayma; oturum güvenliği ancak üretim, taşıma ve yaşam döngüsü katmanlarının birlikte doğru yapılmasıyla sağlanır.

---

## Sonuç

Oturum yönetimi zafiyetleri, çoğu zaman "şifreyi kırmaya" hiç gerek kalmadan kimliği ele geçirmenin yolunu açtığı için son derece kritiktir. Dört ekseni tekrar hatırlayalım: **fixation**, kimliğin girişte yenilenmemesinden doğar ve savunması kimliği yeniden üretmektir. **Tahmin edilebilirlik**, yetersiz entropiden kaynaklanır ve savunması CSPRNG ile üretilmiş yüksek entropili, opak kimliklerdir. **Cookie bayrakları**, güçlü bir kimliği bile taşıma katmanında koruyan düğmelerdir; `HttpOnly`, `Secure`, `SameSite` ve dar kapsam birlikte çalışır. **Timeout ve yaşam döngüsü** ise ihlalin kaçınılmazlığını kabul edip hasarı zamanla sınırlar ve mutlaka sunucu tarafında gerçek geçersiz kılmayla hayata geçirilmelidir.

Ortak ilke tektir: Oturum kimliği kimliğin kendisidir. Onu güçlü üret, güvenli taşı, doğru zamanda öldür. Bu üç fiili doğru yaptığında, oturum katmanı bir zafiyet kaynağı olmaktan çıkıp katmanlı savunmanın sağlam bir halkasına dönüşür.
