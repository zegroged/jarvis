# Subdomain Takeover (Alt Alan Adı Ele Geçirme)

## Tanım

Subdomain takeover, bir kuruluşa ait bir alt alan adının (örneğin `blog.sirket.com` veya `magaza.sirket.com`), o alt alan adının işaret ettiği arka uç servisin artık var olmaması sayesinde bir saldırgan tarafından ele geçirilmesidir. Kritik nokta şudur: alt alan adının kaydı hâlâ kuruluşun DNS bölgesinde durmaktadır, ancak işaret ettiği hedef (bir bulut kovası, bir PaaS uygulaması, bir CDN dağıtımı) serbest kalmıştır. Saldırgan bu serbest hedefi kendi adına yeniden talep ederek, kurbanın alan adı altında kendi içeriğini sunmaya başlar.

Bunun sonucu görünürde masum bir "kayıp bağlantı" değildir. Saldırgan artık kuruluşun meşru alan adı altında çalıştığı için; tarayıcı adres çubuğunda gerçek marka görünür, TLS sertifikası çoğu durumda geçerli şekilde alınabilir, ve kullanıcı ile diğer sistemler bu alt alan adına duydukları güveni saldırgana devrederler. Bu yüzden subdomain takeover, düşük teknik karmaşıklığına rağmen etkisi yüksek bir zafiyet sınıfıdır: phishing, oturum çerezi (cookie) çalma, OAuth akışlarının kaçırılması ve içerik güvenlik politikalarının (CSP) delinmesi gibi zincirleme saldırılara kapı açar.

## Kök Neden ve Çalışma Mantığı

Sorunun özü, DNS kaydının ömrü ile arka uç kaynağının ömrü arasındaki senkronizasyon kopukluğudur. Bunu anlamak için önce DNS'in nasıl devredilen (delegation) bir sistem olduğunu hatırlamak gerekir.

Bir kuruluş `sirket.com` bölgesini yönetir. Bir alt alan adını dış bir servise bağlamak istediğinde genellikle bir `CNAME` kaydı oluşturur. Örneğin:

```
blog.sirket.com.   CNAME   sirket-blog.hosting-saglayici.net.
```

Bu kayıt şunu söyler: "`blog.sirket.com` için gelen isteklerde nihai adres çözümlemesi için `sirket-blog.hosting-saglayici.net` adına bak." Yani `sirket.com` alan adı, bu alt alanın içerik sorumluluğunu üçüncü taraf bir platforma **devreder**. Buradaki güven modeli örtük bir varsayıma dayanır: hedefteki `sirket-blog.hosting-saglayici.net` kaynağı bize aittir ve bize ait kalacaktır.

Kök neden tam olarak bu varsayımın kırıldığı anda ortaya çıkar. Şu tipik yaşam döngüsünü düşünelim:

1. Ekip bir kampanya için bir PaaS platformunda (örneğin bir statik site barındırma servisi) uygulama oluşturur ve buna `blog.sirket.com` CNAME'ini bağlar.
2. Kampanya biter. Ekip PaaS panelinden uygulamayı **siler** veya aboneliği iptal eder. Kaynak artık platformda yoktur.
3. Ancak `sirket.com` DNS bölgesindeki `CNAME blog.sirket.com -> sirket-blog.hosting-saglayici.net` kaydı **silinmez**. Kimse bu adımı yapmayı hatırlamaz ya da DNS'i yöneten ekip ayrı olduğu için haberi olmaz.

Artık ortada **sahipsiz bir CNAME** (dangling CNAME) vardır: geçerli bir DNS kaydı, artık kimseye ait olmayan bir hedefe işaret etmektedir. Saldırganın yapması gereken tek şey, o hedefi platformda yeniden talep etmektir. Çünkü çoğu PaaS/bulut platformu, alt alan adlarını (subdomain'leri) veya kaynak adlarını **ilk gelen alır** mantığıyla dağıtır. Saldırgan aynı platformda yeni bir hesap açıp `sirket-blog.hosting-saglayici.net` adını (veya platformun eşdeğer talep mekanizmasını) kendisine bağladığında, DNS zinciri artık saldırganın içeriğini `blog.sirket.com` üzerinden sunar.

Buradaki asıl zafiyet DNS protokolünde değil, **kaynak yaşam döngüsü yönetimindeki** boşluktadır. DNS "sadık" davranır; kendisine verilen hedefe yönlendirmeye devam eder. Sadakatin yanlış tarafa yönelmesi problemi doğurur.

### Neden her sahipsiz kayıt ele geçirilemez?

Önemli bir nüans: her dangling CNAME otomatik olarak takeover'a açık değildir. Ele geçirilebilirlik, hedef platformun **isim talep etme (claiming) modeline** bağlıdır. İki uçtan bakalım:

- **Ele geçirilebilir platformlar:** Kullanıcının seçtiği alt alan adını serbest bırakınca başkasının aynı adı alabildiği, ve özel alan adı (custom domain) doğrulamasını yalnızca CNAME varlığına dayandıran servisler. Burada saldırgan aynı ismi alıp CNAME zincirini tamamlayabilir.

- **Ele geçirilemeyen (veya zorlaştırılmış) platformlar:** Bir kaynak silindiğinde ismi bir süre karantinaya alan (hold-down), ya da özel alan bağlantısı için CNAME'e ek olarak benzersiz bir `TXT` doğrulama kaydı veya hesap kimliği zorunlu kılan servisler. Bu ikinci grupta saldırgan CNAME'i görse bile talebi tamamlayamaz, çünkü sizin hesabınıza özel doğrulama jetonunu üretemez.

Bu ayrım savunma için kritiktir çünkü hangi servislerin riskli olduğunu bilmek, envanterinizde önceliklendirme yapmanızı sağlar. Genel kural: **bir servisin özel alan adı doğrulaması ne kadar zayıfsa (yalnızca CNAME'e bakıyorsa), takeover riski o kadar yüksektir.**

### CNAME dışındaki vektörler

Sorun sadece CNAME ile sınırlı değildir, aynı mantık farklı kayıt türlerinde de yaşanır:

- **Sahipsiz `NS` kayıtları:** Bir alt bölge (subzone), artık sizin hesabınızda olmayan bir yetkili ad sunucusuna (authoritative name server) devredilmişse, o ad sunucusunu kontrol eden taraf tüm alt bölgeyi ele geçirebilir. Bu, tek bir kaynaktan çok daha geniş bir etki alanı demektir çünkü saldırgan alt bölgedeki tüm kayıtları uydurabilir.
- **Sahipsiz `MX`, `A`/`AAAA` kayıtları:** Statik bir IP'ye işaret eden `A` kaydı, o IP artık paylaşımlı bir bulut IP havuzuna dönmüşse ve saldırgan aynı havuzdan o IP'yi alabiliyorsa benzer riske girer (bu, IP tahsis modeline bağlı olduğundan CNAME kadar sık değildir ama gözden kaçırılmamalıdır).

## Somut Örnekler

### Örnek 1: Silinen statik site barındırma

Bir e-ticaret ekibi indirim kampanyası için `firsatlar.sirket.com` alt alanını bir statik site barındırma servisine bağlar:

```
firsatlar.sirket.com.   CNAME   sirket-firsatlar.staticpages.example.
```

Kampanya bitince PaaS projesi silinir ama DNS kaydı kalır. `firsatlar.sirket.com` adresine giden bir kullanıcı, platformun "böyle bir proje bulunamadı" (404 / "no such app") sayfasını görür. İşte bu jenerik hata sayfası, ele geçirmeye açık bir dangling CNAME'in en klasik parmak izidir (fingerprint). Saldırgan aynı platformda `sirket-firsatlar` projesini yeniden oluşturur, kendi HTML'ini yükler ve artık `firsatlar.sirket.com` saldırganın sahte "hesabınıza giriş yapın" formunu marka alan adı altında sunar.

### Örnek 2: Bulut nesne depolama kovası

Bir ekip statik varlıkları (görseller, JS) bir nesne depolama (object storage) kovasında yayınlar ve `varliklar.sirket.com` alt alanını kova adına bağlar. Kova silindiğinde ama DNS kaydı kaldığında, kova adı isim alanında yeniden serbest kalır. Saldırgan aynı isimde kova oluşturursa, `varliklar.sirket.com` üzerinden yüklenen tüm JS dosyalarını saldırgan kontrol eder. Bu senaryo özellikle tehlikelidir: eğer ana sitedeki sayfalar bu alt alandan script çekiyorsa (`<script src="https://varliklar.sirket.com/app.js">`), saldırgan ana siteye **doğrudan JavaScript enjekte edebilir**, yani etkili bir stored XSS zincirine ulaşır.

### Örnek 3: Sahipsiz NS devri

`eski-proje.sirket.com` bir zamanlar ayrı bir DNS sağlayıcısına devredilmiştir:

```
eski-proje.sirket.com.   NS   ns1.eski-saglayici.example.
eski-proje.sirket.com.   NS   ns2.eski-saglayici.example.
```

Proje kapanınca eski sağlayıcıdaki bölge silinir ama üst bölgedeki NS kayıtları kalır. Saldırgan aynı sağlayıcıda `eski-proje.sirket.com` bölgesini oluşturabilirse, bu alt bölge için tüm A, CNAME, MX, TXT kayıtlarını kendi belirler; hatta bu alt alan için e-posta alabilir ve onu kullanarak sertifika otoritelerinden (CA) alan doğrulaması geçirebilir.

## İstismar Mantığı (Sömürü)

Saldırgan açısından süreç genellikle şu adımları izler; savunmayı doğru kurgulayabilmek için bu bakış açısını anlamak şarttır.

**1. Keşif ve envanter çıkarma.** Saldırgan önce hedefin alt alan adlarını toplar. Bunun için pasif kaynaklar (Certificate Transparency logları, yani her verilen TLS sertifikasının kamuya açık kaydı; pasif DNS veri tabanları; arama motoru sonuçları) ve aktif kaynaklar (DNS brute-force, kelime listeleriyle olası alt alan tahmini) kullanılır. Certificate Transparency özellikle güçlüdür çünkü kuruluşun geçmişte sertifika aldığı her alt alanı ifşa eder, hatta artık aktif olmayanları bile.

**2. Sahipsiz kayıtları ayıklama.** Toplanan her alt alan için DNS çözümlemesi yapılır. Saldırgan `CNAME` zincirini takip eder ve zincirin ucundaki hedefin durumuna bakar. İki temel sinyal aranır: (a) hedef isim çözümlenmiyor (NXDOMAIN dönüyor) ama CNAME hâlâ ona işaret ediyor; (b) hedef çözümleniyor ama servis, o kaynağın var olmadığını gösteren jenerik bir hata sayfası (fingerprint) döndürüyor. Bu parmak izleri her platform için farklıdır ("no such bucket", "there isn't a site here yet", "404 not found" gibi platforma özgü metinler) ve otomatik araçlar bunları imza olarak tanır.

**3. Talep etme (claiming).** Saldırgan tespit ettiği platformda bir hesap açar ve serbest kaynağı (proje adı, kova adı, uygulama adı) kendi adına oluşturur. DNS zinciri değişmeden aynı hedefe işaret etmeye devam ettiği için, çözümleme artık saldırganın kaynağına ulaşır.

**4. Silahlandırma.** Ele geçirilen alt alan meşru marka altında olduğu için güçlü saldırılara dönüştürülür:
- **Phishing:** Gerçek alan adı altında sahte giriş sayfaları; kullanıcı adres çubuğunu doğru gördüğü için kanar.
- **TLS ile güvenilirlik:** Saldırgan, kontrol ettiği alt alan için otomatik CA'lardan geçerli sertifika alır (domain doğrulaması artık saldırganın içeriğine dayandığından geçer). Kilit ikonu kullanıcıyı yanıltır.
- **Çerez ve oturum çalma:** Eğer ana site çerezleri `Domain=.sirket.com` kapsamıyla ayarlıyorsa, bu çerezler tüm alt alanlara gönderilir. Saldırgan alt alandan bu çerezleri okuyabilir. Aynı şekilde `SameSite` ve alan tabanlı güven kararları delinir.
- **OAuth/SSO kaçırma:** Eğer OAuth `redirect_uri` beyaz listesi tüm `*.sirket.com` alt alanlarına güveniyorsa, saldırgan yetkilendirme kodlarını (authorization code) kendi alt alanına yönlendirtebilir.
- **CSP delme:** İçerik güvenlik politikası `script-src` yönergesinde `*.sirket.com`'a izin veriyorsa, ele geçirilen alt alandan ana siteye script yüklenmesinin önü açılır.

Bu zincirleme etkiler, subdomain takeover'ın neden "sadece bir 404 sayfası" olmadığını gösterir: asıl değer, kaybedilen sayfada değil, o alan adına başka sistemlerin duyduğu **güvenin devralınmasındadır**.

## Tespit

Tespit, savunmanın kalbidir çünkü bu zafiyet sinsi bir şekilde birikir. Her yeni bulut kaynağı bir sonraki dangling CNAME adayıdır. Sağlam bir tespit programı şu katmanlardan oluşur.

**Alt alan adı envanteri çıkarma.** Savunan taraf, saldırganla aynı keşif tekniklerini kendine karşı uygulamalıdır. Certificate Transparency loglarından geçmişte sertifika alınmış tüm alt alanları toplayın, DNS bölge dosyalarınızı (varsa) dışa aktarın, ve pasif DNS kaynaklarıyla karşılaştırın. Amaç, "bildiğinizi sandığınız" alt alan listesi ile "gerçekten var olan" liste arasındaki farkı görmektir; unutulan kayıtlar tam da bu farkta saklanır.

**Sahipsiz kayıt taraması.** Envanterdeki her alt alan için düzenli olarak DNS çözümlemesi yapın ve CNAME zincirinin ucunu inceleyin. İki durumu işaretleyin: (1) CNAME hedefi NXDOMAIN dönüyorsa; (2) hedef bir üçüncü taraf platforma işaret ediyor ve o platform "kaynak yok" fingerprint'i döndürüyorsa. Bu iş için açık kaynak araçlar mevcuttur — bunlar bilinen platformların parmak izlerini bir imza veri tabanında tutar ve otomatik eşleştirir. Bu tür araçlara güvenirken bilinmesi gereken bir sınır vardır: imza veri tabanı güncel değilse yeni platformları kaçırabilir, ve fingerprint eşleşmesi "ele geçirilebilir" demek değildir; her bulguyu manuel doğrulamak gerekir.

**Sürekli izleme (continuous monitoring).** Tek seferlik tarama yetmez, çünkü risk her kaynak silme işleminde yeniden doğar. Envanter taramasını periyodik (ideal olarak günlük) ve otomatik hale getirin. Yeni bir alt alanın çözümlenmeye başlaması veya çözümlemeyi bırakması bir uyarı tetiklemelidir.

**Manuel doğrulama.** Otomatik bir araç "ele geçirilebilir" dediğinde, üretim sistemine zarar vermeden bunu teyit edin. Doğrulama, ilgili platformda kaynağı gerçekten talep edip edemeyeceğinizi kontrolü şeklindedir; bunu yaparken kendi kontrolünüzdeki bir kanıt (örneğin benzersiz bir doğrulama dizesi) yerleştirip başka sistemlere zarar vermemeye dikkat edin.

## Savunma ve En İyi Pratikler

Savunmanın merkezindeki ilke tektir ve tekrar etmeye değer: **DNS kaydının ömrü, arka uç kaynağının ömrüne bağlanmalıdır.** Aşağıdaki pratikler bu ilkeyi hayata geçirir.

**1. Yıkım sırasını (deprovisioning) tersine çevirin.** En önemli operasyonel kural: bir kaynağı kapatırken önce **DNS kaydını silin**, sonra arka uç kaynağını serbest bırakın. Yaygın hata bunun tersidir — önce kaynak silinir, DNS unutulur. Doğru sıra, dangling CNAME'in oluştuğu pencereyi ortadan kaldırır. Bu adımı bir kontrol listesi maddesi değil, otomatik bir iş akışı zorunluluğu haline getirin.

**2. Kaynak yaşam döngüsünü otomatikleştirin (IaC).** Altyapıyı kod (Infrastructure as Code) ile yönetin. DNS kaydı ile arka uç kaynağı aynı kod modülünde tanımlanırsa, kaynak yok edildiğinde DNS kaydı da aynı işlemde silinir. Manuel DNS düzenlemelerini mümkün olduğunca yasaklayın; çünkü el ile eklenen ve envanterde takip edilmeyen kayıtlar en sık ele geçirilenlerdir.

**3. Güçlü alan doğrulaması olan servisleri tercih edin.** Yeni bir servisi özel alan adına bağlarken, o servisin doğrulama modelini değerlendirin. CNAME'e ek olarak benzersiz bir `TXT` jetonu veya hesap bağlı doğrulama isteyen servisler, dangling CNAME oluşsa bile saldırganın talebini engeller. Tedarikçi seçim kriterlerinize "custom domain claim güvenliği" maddesini ekleyin.

**4. Merkezî ve otoritatif bir alt alan envanteri tutun.** "Hangi alt alanlar var ve her biri hangi kaynağa, hangi ekibe, hangi amaca ait?" sorusunun yaşayan bir cevabı olmalıdır. Envanter, hem tespit taramasının girdisidir hem de bir kaynak sahibini bulup temizletebilmenizin önkoşuludur. Sahipsiz kayıtların çoğu, "kimse artık kimin olduğunu bilmediği için" temizlenmeden kalır.

**5. Certificate Transparency izlemesini kurumsallaştırın.** CT loglarını kendi alan adınız için izleyerek hem beklenmedik sertifikaları (olası ele geçirme veya yanlış yapılandırma sinyali) hem de unuttuğunuz alt alanları erken yakalarsınız.

**6. Güven kararlarını alt alan bazında daraltın.** Derinlemesine savunma (defense in depth) için: çerezleri gereksiz yere `Domain=.sirket.com` kapsamıyla vermeyin, mümkünse host'a özel çerez kullanın. OAuth `redirect_uri` beyaz listesinde joker (`*.sirket.com`) yerine tam alan adları listeleyin. CSP `script-src` yönergesinde geniş joker alanlar yerine belirli kaynakları belirtin. Böylece bir alt alan ele geçirilse bile hasar o alanla sınırlı kalır, ana sisteme sıçramaz.

**7. Yeni alt alan oluşturmayı kontrollü hale getirin.** Alt alan oluşturma yetkisini gözden geçirme (review) süreciyle sınırlayın; her yeni CNAME için "bu kaynak nasıl ve ne zaman sökülecek?" sorusunun cevabı baştan kayıt altına alınsın.

## Yaygın Hatalar

Sahadaki tekrar eden yanlışları bilmek, kendi süreçlerinizdeki boşlukları görmenizi kolaylaştırır.

- **"Önce kaynağı sil, DNS'i sonra hallederim" alışkanlığı.** Neredeyse tüm takeover vakalarının kök nedeni budur. "Sonra" çoğu zaman hiç gelmez.

- **DNS ile bulut yönetiminin ayrı ekiplerde olması ve iletişim kopukluğu.** Platform ekibi bir kaynağı siler ama DNS'i başka bir ekip yönettiği için haber gitmez. Organizasyonel sınırlar, teknik sınırlardan daha çok dangling kayıt üretir.

- **Envanteri tek seferlik çıkarıp güncel tutmamak.** Bulut ortamı dinamiktir; altı ay önceki envanter bugünün gerçeğini yansıtmaz. Tespit sürekli olmalıdır.

- **Fingerprint eşleşmesini kesin ele geçirilebilirlik sanmak.** Bir aracın "vulnerable" demesi otomatik teyit değildir; platform karantina veya ek doğrulama uyguluyor olabilir. Her bulgu manuel doğrulanmalı, ama üretim sistemlerine zarar verilmeden.

- **Sadece CNAME'e odaklanıp NS, MX ve A kayıtlarını gözden kaçırmak.** Özellikle sahipsiz NS devirleri, tek bir alt alandan çok daha geniş etki yarattığından en tehlikeli ama en az bakılan vektördür.

- **Alt alan güvenini fazla geniş tutmak.** `*.sirket.com`'a kör güvenen çerez kapsamları, OAuth beyaz listeleri ve CSP yönergeleri, tek bir ele geçirmenin tüm sisteme sıçramasını sağlar. Bu, zafiyeti olaydan felakete çeviren çarpandır.

- **Test/staging alt alanlarını unutmak.** `test.`, `dev.`, `staging.` gibi geçici amaçlı alt alanlar en sık üretilip en az temizlenenlerdir ve genellikle daha zayıf gözetim altındadır.

## Sonuç

Subdomain takeover, tek bir yazılım hatasından değil, **kaynak yaşam döngüsündeki bir yönetim boşluğundan** doğar. DNS, kendisine söyleneni sadakatle yapar; sorun, arka uç kaynağı yok olduğunda kimsenin DNS'e "artık oraya bakma" dememesidir. Bu yüzden çözüm de tek bir yama değil, süreçseldir: DNS kaydının ömrünü kaynağın ömrüne bağlamak, otoritatif bir envanter tutmak, sürekli tarama yapmak ve alt alan bazlı güveni daraltmak. Bu dört pratik birlikte uygulandığında, hem ele geçirilebilir kayıtların oluşması engellenir hem de kaçınılmaz olarak oluşacak birkaç tanesi güvenlik olayına dönüşmeden yakalanır. Düşük teknik karmaşıklığına karşın yüksek etkisi nedeniyle, bu zafiyet sınıfı her olgun uygulama güvenliği ve saldırı yüzeyi yönetimi programının rutin bir kalemi olmalıdır.
