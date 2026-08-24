# Clickjacking (Tıklama Kaçırma)

## Tanım

Clickjacking, Türkçe adıyla "tıklama kaçırma", bir saldırganın kurbanı görünürde masum bir arayüzle etkileşime girdiğine inandırırken, aslında farkında olmadan başka bir web uygulaması üzerinde eylemler gerçekleştirmesini sağlayan bir kullanıcı arayüzü (UI) manipülasyon saldırısıdır. Saldırı, teknik anlamda sunucuyu veya kullanıcının oturumunu doğrudan hedef almaz; onun yerine kullanıcının **niyeti** ile **gerçekte tetiklediği eylem** arasındaki boşluğu istismar eder. Kullanıcı bir yere tıkladığını sanır, ama tıklaması "kaçırılarak" görünmeyen başka bir hedefe yönlendirilir.

Literatürde bu saldırı ailesine daha genel olarak **UI redressing** (arayüz yeniden giydirme) adı verilir. Clickjacking en yaygın türüdür ama tek türü değildir. Aynı temel mantık üzerine kurulu varyantlar arasında **likejacking** (sosyal medyada beğeni kaçırma), **cursorjacking** (imleç konumunu sahte gösterme), **filejacking** ve **keyjacking** (klavye odağını kaçırma) bulunur.

Clickjacking'in tehlikeli olmasının nedeni, kurbanın tarayıcısının **meşru olarak kimlik doğrulanmış** olmasıdır. Kullanıcı hedef siteye zaten giriş yapmışsa (oturum cookie'si tarayıcıda mevcutsa), saldırgan o oturumun yetkisini kullanarak kritik eylemleri kullanıcının kendi elleriyle tetikletebilir: bir ödeme onayı, bir hesap silme, bir izin verme (OAuth consent), bir aygıtın kamerasını açma veya para transferi.

## Kök Neden: Neden Böyle Oluyor?

Clickjacking'in kök nedeni, web'in en temel tasarım özelliklerinden birinde yatar: **bir sayfanın, başka bir origin'e (köken) ait sayfayı bir `iframe` içine gömebilmesi.** Web başlangıçtan itibaren "composability" (bileşenleri bir araya getirebilme) üzerine kuruldu. Bir sayfa harita widget'ı, video oynatıcı, ödeme çerçevesi veya sosyal paylaşım butonu gibi başka sitelerin içeriğini kendi içine gömebilsin diye `iframe` mekanizması sunuldu.

Ancak bu esneklik iki kritik güvenlik varsayımını beraberinde getirmedi:

**Birincisi**, bir sayfa kendini bir `iframe` içine gömen üst sayfanın (parent) kim olduğunu **varsayılan olarak denetlemez.** Yani `banka.com` hiçbir önlem almadıysa, `kotu-site.com` onu bir `iframe` içine gömebilir ve `banka.com` bundan haberdar olmaz.

**İkincisi**, tarayıcı bir `iframe` içindeki sayfaya gönderilen cookie'leri (üçüncü taraf kısıtlamaları hariç) yine de ekler. Yani gömülen çerçeve, kullanıcının **oturumu açık** haliyle yüklenir. Kullanıcı `banka.com`'a giriş yaptıysa, o çerçeve içinde de giriş yapmış görünür.

Burada devreye saldırının asıl mekanizması girer: **CSS ile görsel katmanlama.** Modern CSS, herhangi bir elementi şeffaf yapabilir (`opacity: 0`), üst üste bindirebilir (`z-index`), tam olarak konumlandırabilir (`position: absolute`) ve boyutlandırabilir. Saldırgan, hedef sitenin `iframe`'ini `opacity: 0` ile tamamen görünmez yapar, ama `z-index` ile kullanıcının etkileşimde bulunacağı katmanın **en üstüne** koyar. Altına ise cazip, tıklanmaya davet eden sahte bir arayüz (örneğin "Ödülü Kazan!" butonu) yerleştirir.

Sonuç şudur: Kullanıcının gözü sahte butonu görür, ama faresi tıkladığında olay (event), görünmez `iframe`'deki gerçek butona ulaşır. Tarayıcı açısından bu tıklama tamamen meşrudur: gerçek bir kullanıcı, gerçek bir fareyle, gerçek bir elemente tıklamıştır. Hiçbir otomasyon, hiçbir script enjeksiyonu, hiçbir CSRF token ihlali yoktur. İşte bu yüzden clickjacking'e karşı klasik CSRF token savunmaları **işe yaramaz** — çünkü isteği kullanıcının kendi tarayıcısı, tam yetkili şekilde, kendi eylemiyle gönderir.

Özetle kök neden üç faktörün birleşimidir:
1. Sayfaların çapraz-origin `iframe` içine gömülebilmesi (varsayılan izin).
2. Gömülen sayfanın oturumlu (cookie'li) yüklenmesi.
3. CSS'in görsel katmanları, kullanıcının algısını gerçek tıklama hedefinden ayıracak kadar özgürce manipüle edebilmesi.

## Somut Örnek: Saldırı Nasıl Kurgulanır?

Bir "hesabımı sil" senaryosu üzerinden düşünelim. Diyelim ki `hedefsite.com/ayarlar` sayfasında "Hesabı Sil" butonu var ve kullanıcı bu siteye giriş yapmış durumda.

Saldırgan `kotu-site.com` adında bir sayfa hazırlar. Bu sayfada iki katman vardır. Alttaki katman göze hitap eden bir tuzaktır; üstteki görünmez katman ise hedef sitenin gerçek sayfasıdır.

```html
<style>
  .tuzak {
    position: absolute;
    top: 300px;
    left: 100px;
    z-index: 1;
  }
  iframe {
    position: absolute;
    top: 0;
    left: 0;
    width: 1000px;
    height: 800px;
    opacity: 0;        /* Tamamen seffaf */
    z-index: 2;        /* Tuzagin ustunde */
    /* Hedef butonu, sahte butonun tam ustune denk gelecek
       sekilde konumlandirilir (ornegin negatif top ile kaydirilir) */
  }
</style>

<div class="tuzak">
  <button>Bedava iPhone Kazan!</button>
</div>

<iframe src="https://hedefsite.com/ayarlar"></iframe>
```

Burada saldırganın işi, hedef sitedeki "Hesabı Sil" butonunun ekrandaki koordinatını, alttaki "Bedava iPhone Kazan!" butonunun tam üstüne oturtacak biçimde `iframe`'i kaydırmaktır. Kullanıcı "Bedava iPhone" butonuna tıkladığını sanır; oysa tıklama görünmez çerçevedeki "Hesabı Sil" butonuna gider ve kullanıcı, oturumu açık olduğu için, kendi hesabını kendi eliyle siler.

Daha sofistike varyantlarda saldırgan tek tık yerine bir **sürükleme (drag-and-drop)** dizisi de kurgulayabilir; örneğin kullanıcıya bir oyun oynattırıp aslında bir metni bir alandan diğerine sürükleterek gizli veri sızdırabilir. Bir başka varyant olan **cursorjacking**'de sahte bir imleç görseli gösterilir; kullanıcı gördüğü imlecin bir yeri işaret ettiğini sanırken gerçek imleç bambaşka bir noktadadır.

## İstismar Mantığı ve Savunma: İkisi Bir Arada

Bu bölümde saldırganın her adımını, hemen karşısına konulan savunmayla birlikte ele alacağım; çünkü bir savunmanın neden gerekli olduğunu ancak neyi engellediğini bilerek anlayabiliriz.

### 1. Adım — Hedefi bir iframe içine gömmek

**İstismar:** Saldırının olmazsa olmaz ilk koşulu, hedef sayfanın bir `iframe` içine gömülebilmesidir. Eğer tarayıcı hedef sayfayı `iframe` içinde yüklemeyi reddederse, tüm saldırı zinciri daha başlamadan kırılır.

**Savunma — X-Frame-Options (XFO):** Bu, framing'i engellemek için tarihsel olarak ilk yaygınlaşan HTTP yanıt başlığıdır. Sunucu, yanıtına bu başlığı ekleyerek tarayıcıya sayfanın hangi koşullarda çerçevelenebileceğini söyler. İki temel ve geçerli değeri vardır:

- `X-Frame-Options: DENY` — Sayfa hiçbir koşulda, hiçbir `iframe` içine gömülemez; aynı origin bile olsa.
- `X-Frame-Options: SAMEORIGIN` — Sayfa yalnızca kendisiyle **aynı origin**'e ait bir sayfa tarafından çerçevelenebilir; çapraz origin framing engellenir.

Tarihsel olarak `ALLOW-FROM https://guvenli-site.com` diye bir üçüncü değer de tanımlanmıştı; belirli bir origin'e izin vermeyi amaçlıyordu. Ancak bu değer birçok modern tarayıcı tarafından hiçbir zaman düzgün desteklenmedi ve pratikte terk edildi. Bu yüzden tek bir izinli origin belirtmek istiyorsanız `ALLOW-FROM`'a **güvenmeyin**; onun yerine aşağıda anlatacağım CSP `frame-ancestors` direktifini kullanın.

X-Frame-Options'ın önemli bir sınırlaması, **yalnızca tek bir başlık değeri** taşıyabilmesi ve **birden fazla izinli origin listeleyememesidir.** "A ve B sitelerinin gömmesine izin ver, gerisini engelle" gibi bir ihtiyaç XFO ile ifade edilemez. Ayrıca XFO resmi bir W3C standardı olmaktan çok, tarayıcıların ortaklaşa benimsediği fiili (de facto) bir mekanizma olarak yaygınlaştı; davranışında tarayıcılar arası ince farklar olabilir.

### 2. Adım — Modern ve doğru savunma: CSP frame-ancestors

**Savunma — Content-Security-Policy: frame-ancestors:** Bugün clickjacking'e karşı **birincil ve tercih edilmesi gereken** savunma budur. `frame-ancestors`, Content Security Policy (CSP) çerçevesinin bir direktifidir ve X-Frame-Options'ın tüm yeteneklerini kapsayıp üzerine ekler. Sayfanın hangi origin'ler tarafından `iframe`, `frame`, `object` ya da `embed` içine gömülebileceğini denetler.

Kullanım örnekleri:

- `Content-Security-Policy: frame-ancestors 'none';` — Hiçbir yerden gömülemez. XFO'daki `DENY` karşılığı.
- `Content-Security-Policy: frame-ancestors 'self';` — Yalnızca aynı origin gömebilir. XFO'daki `SAMEORIGIN` karşılığı.
- `Content-Security-Policy: frame-ancestors 'self' https://partner.example.com;` — Aynı origin **ve** belirtilen ortak site gömebilir. XFO'nun asla düzgün yapamadığı şey budur: **birden fazla izinli origin listelemek.**

`frame-ancestors`'ın X-Frame-Options'a üstünlükleri şunlardır:

1. **Çoklu origin desteği:** Birden fazla güvenli origin'i tek direktifte listeleyebilirsiniz.
2. **Standart ve tutarlılık:** CSP resmi bir standarttır; modern tarayıcılarda davranışı daha öngörülebilirdir.
3. **Şema ve joker esnekliği:** `https:` gibi şema kısıtlamaları veya alt alan adı kalıpları gibi daha ince kontroller ifade edilebilir.

Önemli bir davranış kuralı: `frame-ancestors` direktifi, HTML içindeki bir `<meta>` etiketiyle **verilemez**; yalnızca gerçek bir **HTTP yanıt başlığı** olarak gönderildiğinde geçerlidir. Bunun nedeni, framing kararının sayfa henüz render edilmeden, tarayıcının HTTP katmanında verilmesi gerektiğidir. `<meta>` etiketiyle konulan bir `frame-ancestors` yok sayılır — bu, sık yapılan ve tehlikeli bir hatadır.

### Eski ve yeni savunmayı birlikte kullanmak

Modern tarayıcılar `frame-ancestors`'ı desteklediğinde XFO'yu genellikle göz ardı eder ve CSP'yi esas alır. Yine de, çok eski istemcileri de düşünen savunma derinliği (defense in depth) yaklaşımıyla **her ikisini birden** göndermek yaygın ve makul bir pratiktir:

```
Content-Security-Policy: frame-ancestors 'none';
X-Frame-Options: DENY
```

Bu ikisinin **çelişmemesine** dikkat edilmelidir. Örneğin CSP'de `frame-ancestors 'self'` derken XFO'da `DENY` demek mantıksal bir çelişkidir ve karışıklığa yol açar; ikisini aynı politikayı ifade edecek şekilde hizalayın.

### 3. Adım — İstemci tarafı ek savunmalar

Başlık tabanlı savunmalar birincil ve en güvenilir katmandır, ancak bazı ek istemci tarafı önlemler de vardır:

**SameSite cookie'leri:** Cookie'lere `SameSite=Lax` veya `SameSite=Strict` özniteliği eklemek, çapraz-site bağlamda oturum cookie'sinin gönderilmesini kısıtlar. Bu, gömülü çerçevenin **oturumsuz** yüklenmesine yol açabileceğinden, saldırının "kullanıcı zaten giriş yapmış" ön koşulunu zayıflatır. Tek başına yeterli bir clickjacking savunması değildir, ama savunma derinliğine katkı sağlar.

**Frame-busting scriptleri (tarihsel yöntem):** CSP öncesi dönemde siteler, JavaScript ile "ben bir çerçeve içindeysem kendimi en üste çıkar" mantığı kurardı (kabaca `if (top !== self) top.location = self.location`). Bu yaklaşım **kırılgandır** ve güvenilmez; `sandbox` öznitelikli `iframe`'ler, çeşitli tarayıcı kısıtlamaları ve akıllı saldırgan teknikleriyle atlatılabilir. Bugün frame-busting'e **birincil savunma olarak asla güvenilmemelidir**; olsa olsa çok eski tarayıcılar için zayıf bir yedek katmandır.

## Yaygın Hatalar

Uygulamada clickjacking savunmasını etkisiz kılan tekrar eden hatalar şunlardır:

**1. Başlığı yalnızca bazı sayfalara koymak.** Geliştiriciler çoğu zaman sadece "login" veya "ayarlar" gibi bariz hassas sayfalara koruma ekler; ama hassas bir eylemi tetikleyen her endpoint korunmalıdır. En güvenli yaklaşım, savunmayı **uygulama genelinde varsayılan** kılıp, framing'e gerçekten ihtiyaç duyan istisnaları tek tek açmaktır.

**2. `frame-ancestors`'ı `<meta>` etiketiyle vermeye çalışmak.** Yukarıda vurguladığım gibi bu direktif yalnızca HTTP başlığı olarak çalışır; `<meta>` içinde yazılırsa sessizce yok sayılır ve site korunmasız kalır — üstelik geliştirici korumalı olduğunu sanır. Bu, yanlış güven duygusu yarattığı için özellikle tehlikelidir.

**3. Terk edilmiş `ALLOW-FROM`'a güvenmek.** `X-Frame-Options: ALLOW-FROM ...` birçok tarayıcıda desteklenmez. Buna dayanan bir "belirli ortağa izin ver" politikası, o tarayıcılarda ya tümüyle engelleme ya da hiç engellememe gibi öngörülemez davranışlara yol açar. Doğrusu `frame-ancestors` kullanmaktır.

**4. Sadece CSRF token'ına güvenmek.** Bir geliştirici "formumda CSRF token var, o halde güvendeyim" diye düşünebilir. Ancak clickjacking'de istek, kullanıcının **kendi** tarayıcısından, geçerli token dahil her şeyiyle meşru biçimde gider. CSRF token clickjacking'i engellemez; bunlar farklı saldırı sınıflarıdır ve ayrı savunmalar gerektirir.

**5. XFO ve CSP'yi çelişkili değerlerle koymak.** İki başlığı birden koymak iyidir, ama farklı politikalar ifade etmeleri (biri `SAMEORIGIN` derken diğeri `DENY` demesi) kafa karışıklığına ve tarayıcıya göre değişen davranışa yol açar.

**6. Framing gereksinimini analiz etmeden gevşek politika koymak.** "Ne olur ne olmaz, ortaklar gömebilsin" diye geniş bir izin listesi vermek saldırı yüzeyini gereksiz büyütür. İzin verilen her origin, o origin ele geçirilirse bir clickjacking vektörü olur.

**7. Yalnızca görsel/UX önlemlerine güvenmek.** "Silme butonuna ikinci bir onay ekranı koyduk" gibi UX önlemleri iyidir ama tek başına yetmez; saldırgan çok adımlı senaryoları da kaçırabilir. Başlık tabanlı framing engeli olmadan UX önlemleri güvenli sayılmaz.

## En İyi Pratikler

Sağlam bir clickjacking savunması için önerilen yaklaşım şudur:

**Birincil savunmayı `frame-ancestors` ile kurun.** Framing'e ihtiyacınız yoksa uygulama genelinde `Content-Security-Policy: frame-ancestors 'none';` varsayılanını uygulayın. Belirli sayfaların güvenilir ortaklarca gömülmesi gerekiyorsa `frame-ancestors 'self' https://guvenilir-ortak.com;` gibi **dar ve açıkça listelenmiş** bir politika kullanın.

**Savunma derinliği için X-Frame-Options'ı da ekleyin.** Çok eski istemcileri düşünerek CSP ile hizalı (çelişmeyen) bir `X-Frame-Options: DENY` veya `SAMEORIGIN` gönderin. Modern tarayıcı CSP'yi esas alacak, eski tarayıcı XFO'dan faydalanacaktır.

**Korumayı merkezi ve varsayılan yapın.** Başlıkları tek tek sayfalara elle eklemek yerine; reverse proxy, web sunucusu yapılandırması, güvenlik middleware'i veya framework düzeyinde bir güvenlik başlığı katmanı ile **tüm yanıtlara otomatik** ekleyin. İstisnalar bilinçli ve gözden geçirilmiş olsun.

**Cookie'leri `SameSite` ile sertleştirin.** Oturum cookie'lerine uygun `SameSite` değeri (mümkünse `Strict`, değilse `Lax`) atayarak gömülü bağlamda oturumun taşınmasını zorlaştırın. Bu, ek bir güvenlik katmanı sağlar.

**Kritik eylemleri niyet doğrulamasıyla güçlendirin.** Para transferi, hesap silme, izin verme gibi geri dönüşü olmayan eylemler için ek bir onay adımı, yeniden kimlik doğrulama (re-authentication) veya CAPTCHA gibi "kasıtlı insan eylemi" gerektiren bir engel koyun. Bu, başlık savunması bir şekilde atlatılsa bile son bir bariyer sunar.

**Politikanızı test edin ve raporlayın.** Sitenizin gerçekten çerçevelenemediğini, basit bir test `iframe`'i ile doğrulayın; başlıkların her endpoint'te var olduğunu tarayıcı geliştirici araçlarının "Network" sekmesinden veya otomatik güvenlik tarayıcılarıyla denetleyin. CSP'nin genelini kurarken `report-uri` / `report-to` gibi raporlama mekanizmalarıyla ihlalleri izleyebilirsiniz.

**Frame-busting scriptlerine birincil savunma olarak güvenmeyin.** Bunları en fazla, başlık desteği olmayan çok eski istemciler için zayıf bir yedek katman olarak düşünün; asıl korumanız her zaman `frame-ancestors` başlığı olsun.

## Kapanış Değerlendirmesi

Clickjacking, teknik olarak "sunucuyu hackleme" değil, **kullanıcının algısını hackleme** saldırısıdır. Gücünü, web'in gömülebilirlik esnekliğinden ve kullanıcının oturumunun tarayıcıda meşru olarak açık olmasından alır. İşin iyi tarafı, savunması kavramsal olarak nettir: sayfanızın **kimler tarafından çerçevelenebileceğini** açıkça beyan edin. Bunu bugün yapmanın doğru yolu `Content-Security-Policy: frame-ancestors` başlığıdır; `X-Frame-Options` ise geriye dönük uyumluluk için tutulan tarihsel bir yardımcıdır. Bu iki başlığı doğru, hizalı ve uygulama genelinde varsayılan olacak biçimde kurarsanız, clickjacking saldırı zincirini daha ilk adımda — hedefinizin bir `iframe`'e gömülmesi anında — kırmış olursunuz.
