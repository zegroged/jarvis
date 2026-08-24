# Güvenli Yazılım Geliştirme Yaşam Döngüsü (Secure SDLC)

## Tanım

Güvenli Yazılım Geliştirme Yaşam Döngüsü (Secure Software Development Life Cycle, SSDLC), güvenliğin yazılımın üretim sürecinin sonuna eklenen bir denetim aşaması olmaktan çıkarılıp; gereksinim toplamadan tasarıma, kodlamadan test etmeye, dağıtımdan bakıma kadar her aşamaya gömülü bir mühendislik disiplini haline getirilmesidir. Klasik SDLC "yazılımı nasıl üretirim" sorusunu sorar; güvenli SDLC bunun yanına "her adımda hangi güvenlik varsayımları geçerli, hangi tehditler ortaya çıkıyor ve bunları nasıl doğrularım" sorularını ekler.

Buradaki temel kavramsal kayma şudur: güvenlik bir *özellik* (feature) değil, sistemin bir *niteliğidir* (property). Bir özelliği en sona ekleyebilirsiniz; bir niteliği ise sonradan cıvatalayamazsınız çünkü nitelik, sistemin tüm bileşenlerinin ortak davranışından doğar. İşte bu yüzden "shift left", yani güvenliği zaman ekseninde sola, sürecin başına kaydırma fikri SSDLC'nin kalbindedir.

Bu makalede üç eksene odaklanacağız: (1) shift left felsefesinin *kök nedeni* ve neden ekonomik bir zorunluluk olduğu; (2) SAST, DAST ve SCA otomatik analiz araçlarının çalışma mantığı, güçlü ve zayıf yanları; (3) tehdit modellemenin (threat modeling) yaşam döngüsüne entegrasyonu. Her bölümde hem savunma tarafını hem de saldırganın bu kontrolleri nasıl atlattığını ele alacağız.

---

## Kök Neden: Neden "Shift Left" Ekonomik Bir Zorunluluk?

### Hatanın maliyeti zamanla üstel büyür

Shift left'in arkasındaki en güçlü argüman ahlaki değil, ekonomiktir. Bir güvenlik açığı yaşam döngüsünde ne kadar geç bulunursa, düzeltme maliyeti o kadar büyür. Bunun sebebi soyut değil, oldukça somuttur:

- Gereksinim/tasarım aşamasında bulunan bir kusur, bir cümlelik metin değişikliğiyle veya bir tasarım kararının tersine çevrilmesiyle düzeltilir. Henüz kod yazılmadığı için "atılan" iş azdır.
- Kodlama aşamasında bulunan aynı kusur, birkaç satır kodun yeniden yazılmasını ve birim testlerin (unit test) güncellenmesini gerektirir.
- Test aşamasında bulunduğunda, kusur artık birden çok modüle yayılmış, başka kod onun davranışına bağımlı hale gelmiş olabilir. Regresyon riski doğar.
- Üretimde (production) bulunduğunda ise maliyete olay müdahalesi (incident response), acil yama, olası veri ihlali bildirimleri, itibar kaybı ve yasal yükümlülükler eklenir.

Bu maliyet farkının tam katsayısı üzerine sektörde çeşitli rakamlar dolaşır (üretimdeki bir hatanın tasarımdaki hataya göre onlarca ila yüzlerce kat pahalı olabildiği söylenir). Kesin bir çarpanı iddia etmek yerine mekanizmayı vurgulamak daha dürüsttür: **maliyet, kusurun etrafında biriken bağımlılık ve varsayım katmanlarının sayısıyla birlikte büyür.** Bir tasarım kusurunu erken düzeltmek, üzerine hiçbir şey inşa edilmemiş bir temeli düzeltmek gibidir; geç düzeltmek ise binayı yıkmadan temeli değiştirmeye çalışmaktır.

### Tasarım kusurları vs. implementasyon hataları

Kritik bir ayrım vardır: güvenlik açıkları kabaca iki gruba düşer.

- **Implementasyon hataları (bugs):** Yanlış yazılmış kod. Örneğin bir `strcpy` çağrısında sınır kontrolü yapmamak (buffer overflow), bir SQL sorgusunda kullanıcı girdisini string olarak birleştirmek (SQL injection). Bunlar tekil, lokal hatalardır ve otomatik araçlarla (SAST) çoğu zaman yakalanabilir.
- **Tasarım kusurları (flaws):** Mimarinin kendisinde saklı hatalar. Örneğin yetkilendirme kararının istemci tarafında (client-side) verilmesi, güven sınırlarının (trust boundary) yanlış çizilmesi, bir kimlik doğrulama akışının yeniden oynatma saldırısına (replay attack) açık tasarlanması. Bunlar tekil bir satırda değil, bileşenler *arasındaki* ilişkilerde yaşar.

Sektördeki gözlemlere göre üretimdeki güvenlik açıklarının kabaca yarısı tasarım kusurlarından kaynaklanır. İşte shift left'in en derin gerekçesi budur: **tasarım kusurları hiçbir kod tarayıcısıyla yakalanamaz çünkü ortada henüz bakılacak "yanlış kod" yoktur; sadece yanlış bir plan vardır.** Bunları yakalamanın tek yolu, kod yazılmadan önce tasarımı sistematik biçimde sorgulamaktır. Bu da bizi tehdit modellemeye götürür.

---

## SAST, DAST ve SCA: Otomatik Analizin Üç Bacağı

Otomatik güvenlik analizi tek bir teknoloji değildir; birbirini tamamlayan, farklı görüş açılarından bakan yöntemler ailesidir. Her birinin *neyi göremediğini* anlamak, onların ne bulduğunu anlamaktan daha önemlidir.

### SAST — Statik Uygulama Güvenliği Testi

**Çalışma mantığı.** SAST (Static Application Security Testing), uygulamayı *çalıştırmadan*, kaynak kodu veya derlenmiş byte kodu üzerinde inceler. Kodu tıpkı bir derleyici gibi ayrıştırır (parse eder), bir soyut sözdizim ağacı (Abstract Syntax Tree, AST) oluşturur ve genellikle veri akışı analizi (data flow analysis) ile "taint analysis" yapar.

Taint analysis'in mantığı şudur: dışarıdan gelen ve güvenilmeyen her girdi bir "kaynak" (source) olarak işaretlenir — HTTP parametreleri, dosya içerikleri, ortam değişkenleri. Bu "kirli" (tainted) veriyi kodun akışı boyunca izler. Eğer kirli veri, hiçbir temizleme (sanitization) veya doğrulama işleminden geçmeden tehlikeli bir "havuza" (sink) ulaşırsa — örneğin bir SQL sorgusu çalıştıran fonksiyona, bir sistem komutu yürüten çağrıya veya HTML çıktısına — SAST bunu bir bulgu olarak raporlar.

**Neden güçlü.** Çok erken çalıştırılabilir; hatta geliştirici kod yazarken IDE içinde anlık uyarı verebilir. Bu, shift left'in en somut aracıdır. Kodun *tamamını* teorik olarak inceleyebilir, çalışma zamanında hiç tetiklenmeyen yolları da görür.

**Neden yanılır — ve saldırgan bunu nasıl kullanır.** SAST'ın iki kronik zayıflığı vardır:

- **False positive (yanlış pozitif) bolluğu.** Statik analiz, çalışma zamanı bağlamını bilmez. Bir girdinin aslında güvenilir bir kaynaktan geldiğini veya başka bir katmanda zaten doğrulandığını göremeyebilir, bu yüzden zararsız kodu "açık" diye işaretler. Çok fazla yanlış pozitif, geliştiricilerde "alarm yorgunluğu" (alert fatigue) yaratır ve *gerçek* bulgular gürültü içinde kaybolur. Bu, SAST'ın en tehlikeli başarısızlık biçimidir.
- **Bağlam körlüğü (false negative).** Custom bir sanitization fonksiyonu yazdıysanız, SAST bunun gerçekten temizleyip temizlemediğini bilemez; onu güvenli varsayıp taint'i "temizlenmiş" sayarak gerçek bir açığı gözden kaçırabilir. Ayrıca yansıma (reflection), dinamik kod yükleme ve karmaşık framework "büyüsü" statik analizi kör eder.

Saldırgan perspektifinden: SAST'ın gördüğü havuzların *dışında* kalan tehlikeli davranışlar (örneğin iş mantığı hataları, yetkilendirme atlamaları) SAST için görünmezdir. Bir saldırgan, kodun sözdizimsel olarak "temiz" görünüp semantik olarak güvensiz olduğu boşlukları hedefler.

### DAST — Dinamik Uygulama Güvenliği Testi

**Çalışma mantığı.** DAST (Dynamic Application Security Testing), uygulamayı *çalışırken*, dışarıdan bir saldırgan gibi test eder. Kaynak koda erişimi yoktur; uygulamaya "kara kutu" (black box) olarak bakar. Çalışan uygulamaya kötü niyetli olabilecek girdiler gönderir (örneğin bir form alanına SQL injection yükü, bir parametreye XSS payload'u) ve yanıtları gözlemleyerek zafiyeti tespit eder.

**Neden güçlü — ve SAST'ı nasıl tamamlar.** DAST'ın bulduğu her şey, tanım gereği *çalışan sistemde gerçekten sömürülebilir* olma eğilimindedir; çünkü teoriyi değil, gerçek davranışı gözlemler. Bu yüzden DAST bulguları genellikle SAST bulgularından daha az yanlış pozitif içerir. Ayrıca sunucu yapılandırması, TLS ayarları, HTTP başlıkları gibi *çalışma zamanı ortamına* ait sorunları görür — SAST bunları hiç göremez çünkü bunlar kodda değildir.

**Neden yanılır.** DAST'ın kör noktaları SAST'ınkinin tam tersidir:

- **Kapsam sorunu (coverage).** DAST yalnızca ulaşabildiği ve tetikleyebildiği kod yollarını test edebilir. Bir saldırı yüzeyini (attack surface) keşfedemezse — örneğin karmaşık çok adımlı bir iş akışının arkasındaki bir uç noktayı bulamazsa — orada gizlenen açığı asla göremez. Uygulamanın hangi bölümünün test edildiği, tarayıcının o bölüme ulaşabilmesine bağlıdır.
- **Kök neden körlüğü.** DAST size "burada bir SQL injection var" der ama *kodun neresinde* olduğunu söylemez. Geliştirici zafiyeti bulup düzeltmek için ek kazı yapmalıdır. SAST ise doğrudan satıra işaret eder. İkisinin birbirini tamamlaması tam da bu yüzdendir.
- **Zamanlama.** DAST çalışan bir uygulama gerektirdiği için doğal olarak daha "sağda" konumlanır; genellikle staging ortamında koşar. Bu onu shift left açısından SAST kadar erken kullanılamaz kılar.

Modern bir varyant olan **IAST** (Interactive Application Security Testing) bu ikisini birleştirmeye çalışır: uygulamanın içine yerleştirilmiş bir ajan (instrumentation), DAST tarzı testler koşarken kod düzeyinde ne olduğunu izler; böylece hem sömürülebilirliği doğrular hem de kök nedene işaret eder.

### SCA — Yazılım Bileşen Analizi

**Çalışma mantığı.** SCA (Software Composition Analysis), *sizin yazmadığınız* kodu hedefler: üçüncü taraf kütüphaneler, açık kaynak bağımlılıklar ve bunların bağımlılıkları (transitive dependencies). Projenin bağımlılık manifestolarını (örneğin `package.json`, `pom.xml`, `requirements.txt`) ve lock dosyalarını okur, kullanılan her bileşenin sürümünü çıkarır ve bunları bilinen açık veritabanlarıyla (örneğin CVE kayıtları, ekosisteme özgü advisory veritabanları) karşılaştırır.

**Neden vazgeçilmez.** Modern bir uygulamanın kod tabanının büyük çoğunluğu — çoğu zaman ezici bir çoğunluğu — geliştiricinin kendi yazdığı değil, çektiği bağımlılıklardan gelir. Dolayısıyla saldırı yüzeyinin çoğu da oradadır. SAST sizin kodunuza bakar; ama Log4Shell tarzı, popüler bir logging kütüphanesindeki bir zafiyet gibi olaylar gösterdi ki asıl felaket çoğu kez *sizin yazmadığınız* koddan gelir. SCA olmadan bu risk tamamen görünmezdir.

SCA'nın ikinci işlevi **lisans uyumluluğudur**: bir bağımlılığın lisansının (örneğin kopyasol/copyleft bir lisans) ticari kullanımınızla çelişip çelişmediğini denetler. Bu güvenlik değil ama SSDLC yönetişiminin bir parçasıdır.

**Neden yanılır — ve tedarik zinciri saldırıları.**

- **Erişilebilirlik vs. kullanılabilirlik.** SCA, "şu kütüphanenin şu sürümünde bir açık var" der; ama sizin uygulamanızın o açığı içeren *fonksiyonu gerçekten çağırıp çağırmadığını* çoğu zaman bilmez. Sonuç: çok sayıda "teorik olarak var ama pratikte erişilemez" bulgu. Gelişmiş SCA araçları "reachability analysis" ile bu gürültüyü azaltmaya çalışır.
- **Bilinmeyen bilinmeyenler.** SCA yalnızca *bilinen* (yayımlanmış) açıkları bulabilir. Henüz keşfedilmemiş bir zafiyet (zero-day) veritabanında olmadığı için görünmezdir.
- **Tedarik zinciri saldırıları (supply chain attacks).** Buradaki asıl modern tehdit budur. Saldırgan artık sizin kodunuza değil, *güvendiğiniz bir bağımlılığa* saldırır: meşru bir paketin bakımını ele geçirir, ona benzer isimli kötü niyetli bir paket yayımlar (typosquatting), veya var olmayan bir bağımlılık adını genel depoya yükleyerek iç derleme sistemlerinizin onu çekmesini umar (dependency confusion). SCA klasik biçimiyle bunların bir kısmını kaçırır; bu yüzden bağımlılık bütünlüğünü kanıtlamak için imzalı artefaktlar, kilit dosyalarında hash sabitleme (pinning) ve bir yazılım malzeme listesi (Software Bill of Materials, SBOM) üretmek kritik hale gelmiştir.

### Üçünün birleşik resmi

Bu üç araç birbirinin yerine geçmez, birbirinin kör noktasını kapatır:

| Boyut | SAST | DAST | SCA |
|---|---|---|---|
| Bakış açısı | İçeriden, kodu okur | Dışarıdan, saldırgan gibi | Bağımlılıklara bakar |
| Uygulama çalışıyor mu? | Hayır | Evet | Hayır |
| Kök nedene işaret | Güçlü (satır düzeyi) | Zayıf | Orta (paket/sürüm) |
| Yanlış pozitif eğilimi | Yüksek | Düşük-orta | Orta-yüksek |
| Erken çalışabilir mi (shift left)? | Çok erken | Geç (çalışan ortam) | Çok erken |
| Kör noktası | İş mantığı, çalışma zamanı yapılandırması | Ulaşamadığı kod yolları | Bilinmeyen açıklar, kendi kodunuz |

Olgun bir SSDLC bu üçünü CI/CD boru hattının (pipeline) farklı aşamalarına yerleştirir; hiçbirini "gümüş kurşun" saymaz.

---

## Tehdit Modelleme Entegrasyonu

### Neden tehdit modelleme, otomatik araçların yapamadığını yapar

Yukarıda gördük: otomatik araçlar implementasyon hatalarını (bugs) iyi yakalar ama tasarım kusurlarını (flaws) yakalayamaz. Tehdit modelleme tam olarak bu boşluğu doldurur. Kod yazılmadan, tasarım üzerinde yapılan yapısal bir "peki bu nasıl bozulur?" sorgulamasıdır.

Tehdit modelleme dört temel soruyu sorar ve bu çerçeve pratikte oldukça sağlamdır:

1. **Ne inşa ediyoruz?** — Sistemi modelleyin. Genellikle bir veri akış diyagramı (Data Flow Diagram, DFD) çizilir: süreçler, veri depoları, dış varlıklar ve aralarındaki veri akışları. En kritik unsur **güven sınırlarıdır** (trust boundaries) — verinin bir güven seviyesinden diğerine geçtiği çizgiler (örneğin internetten sunucuya, uygulamadan veritabanına). Neredeyse tüm ilginç saldırılar bir güven sınırını geçerken olur.
2. **Ne ters gidebilir?** — Tehditleri sistematik olarak listeleyin.
3. **Bu konuda ne yapacağız?** — Her tehdit için karar verin: azalt (mitigate), ortadan kaldır (eliminate), aktar (transfer, örneğin sigorta) veya kabul et (accept).
4. **Yeterince iyi iş çıkardık mı?** — Doğrulayın; sonraki iterasyonda modeli güncelleyin.

### STRIDE: tehditleri sistematik keşfetmek

En yaygın çerçeve **STRIDE**'dır. STRIDE, "ne ters gidebilir?" sorusunu tahmine bırakmayıp altı tehdit kategorisini sistematik biçimde her bileşene karşı kontrol etmenizi sağlar. Her kategori, bir güvenlik özelliğinin ihlalidir:

- **S — Spoofing (Kimlik sahteciliği):** Başkası gibi davranmak. İhlal ettiği özellik: *kimlik doğrulama* (authentication). Örnek: çalınmış bir oturum çerezi (session cookie) ile başka bir kullanıcı gibi giriş yapmak.
- **T — Tampering (Kurcalama):** Veriyi veya kodu yetkisiz değiştirmek. İhlal ettiği özellik: *bütünlük* (integrity). Örnek: transferi sırasında bir parametreyi değiştirmek, disk üzerindeki bir dosyayı bozmak.
- **R — Repudiation (İnkar):** Bir eylemi yaptığını inkar edebilmek. İhlal ettiği özellik: *inkar edilemezlik* (non-repudiation). Örnek: yeterli log tutulmadığı için bir kullanıcının yaptığı zararlı işlemi kanıtlayamamak.
- **I — Information Disclosure (Bilgi ifşası):** Yetkisiz kişilerin veriye erişmesi. İhlal ettiği özellik: *gizlilik* (confidentiality). Örnek: hata mesajlarında iç yol veya stack trace sızdırmak.
- **D — Denial of Service (Hizmet reddi):** Sistemi meşru kullanıcılara kullanılamaz hale getirmek. İhlal ettiği özellik: *erişilebilirlik* (availability). Örnek: pahalı bir işlemi tetikleyen girdilerle kaynakları tüketmek.
- **E — Elevation of Privilege (Yetki yükseltme):** Yetkisiz yüksek ayrıcalıklar elde etmek. İhlal ettiği özellik: *yetkilendirme* (authorization). Örnek: normal bir kullanıcının admin işlevlerine erişmesi.

STRIDE'ın gücü, DFD ile birleştiğinde ortaya çıkar: diyagramdaki *her* öğeyi ve *her* veri akışını alıp altı kategoriyi tek tek sorarsınız. "Bu veri akışı spoof edilebilir mi? Kurcalanabilir mi?..." Bu mekanik disiplin, deneyimli bir uzmanın bile "unutabileceği" saldırı vektörlerini yüzeye çıkarır. Tehdit modellemenin değeri, dahiyane bir sezgiden çok, *sistematik olarak hiçbir kutuyu atlamamaktan* gelir.

Bir başka çerçeve, saldırganın hedefinden geriye doğru çalışan **saldırı ağaçlarıdır** (attack trees): kök düğüm saldırganın amacıdır (örneğin "yönetici hesabını ele geçir"), dallar bu amaca ulaşmanın alternatif yollarıdır. Bu, savunmacıyı saldırgan gibi düşünmeye zorlar.

### Saldırgan mantığı ile savunmayı birlikte kurmak

Tehdit modellemenin özü, savunmayı *saldırının mantığından türetmektir*. Somut bir örnek üzerinden gidelim.

**Senaryo:** Bir e-ticaret uygulamasında "kupon uygula" özelliği var. Kullanıcı bir kupon kodu girer, sunucu indirimi hesaplar.

**Saldırgan mantığı (istismar):**
- *Tampering:* İstek gövdesindeki indirim tutarını doğrudan istemciden gönderiyorsa, saldırgan tutarı manipüle eder. Kök neden: sunucunun istemci verisine güvenmesi.
- *Elevation/Business logic:* Aynı kuponu koşutzamanlı (concurrent) yüzlerce istekle uygularsa, bir "kontrol et sonra uygula" (check-then-act) yarış durumu (race condition) sayesinde tek kullanımlık kuponu defalarca kullanabilir. Kök neden: kontrol ile uygulama arasındaki işlemin atomik olmaması.
- *Information Disclosure:* Geçersiz kupon "kod yok" derken süresi dolmuş kupon "süresi doldu" diyorsa, saldırgan bu farktan geçerli kod uzayını çıkarabilir (bir oracle). Kök neden: hata mesajlarının bilgi sızdırması.

**Savunma (aynı mantıktan türetilmiş):**
- İndirim tutarına *asla* istemciden gelen değere göre karar verme; sunucu tarafında yeniden hesapla. (Tampering karşılığı: güven sınırının doğru yerde olması.)
- Kupon kullanımını atomik bir veritabanı işlemiyle, örneğin koşullu bir güncelleme (compare-and-set) veya uygun kilitleme ile gerçekleştir. (Race condition karşılığı: check-then-act'i tek atomik operasyona indirgemek.)
- Hata mesajlarını tek biçime indir: geçerli, süresi dolmuş ve olmayan kupon aynı jenerik yanıtı dönsün. (Bilgi ifşası karşılığı: yan kanal kapatma.)

Dikkat edin: her savunma, belirli bir saldırı mantığının doğrudan negatifidir. **İyi bir savunma, tehdidi soyut bir "güvenli ol" tavsiyesiyle değil, o tehdidin kök nedenini ortadan kaldırarak kurulur.** Tehdit modelleme bu eşleşmeyi zorunlu kılar.

### Tehdit modellemeyi yaşam döngüsüne gömmek

Tehdit modellemenin en yaygın hatası onu bir kereye mahsus, ağır bir ritüel yapmaktır. Modern SSDLC'de bunun yerine:

- **Tasarım aşamasında** ilk modeli çizin — mimari kararlar henüz ucuzken.
- **Her önemli mimari değişiklikte** modeli güncelleyin. Yeni bir dış entegrasyon, yeni bir güven sınırı demektir.
- **Hafif tutun.** Bütün sistemi bir oturumda modellemeye çalışmak yerine, en riskli akışları (kimlik doğrulama, ödeme, yetkilendirme) önceliklendirin. "Kusursuz ama hiç yapılmayan" bir tehdit modeli yerine "kaba ama düzenli güncellenen" bir model tercih edilir.
- **Sonuçları izlenebilir kılın.** Her tehdit, ya bir azaltma kontrolüne ya bir güvenlik test senaryosuna ya da bilinçli kabul edilmiş bir riske bağlanmalıdır. Aksi halde model bir belge olarak ölür.

---

## CI/CD Boru Hattına Entegrasyon: Güvenlik Kapıları

Shift left'in pratikteki bedeni CI/CD entegrasyonudur. Araçlar boru hattının farklı noktalarına yerleştirilir:

- **Commit / pre-commit:** Hafif sırlar taraması (secret scanning — koda gömülmüş API anahtarları, parolalar), linter tabanlı hızlı kontroller. Amaç: en ucuz noktada en bariz hataları durdurmak.
- **Pull request / build:** SAST ve SCA burada koşar. Sadece *değişen* dosyalara odaklanan artımlı (incremental) tarama, geliştiricinin geri bildirim döngüsünü hızlı tutar.
- **Staging / deploy öncesi:** DAST ve daha derin dinamik testler çalışan uygulamaya karşı koşar.
- **Runtime / production:** Sürekli izleme, çalışma zamanı koruması ve SCA'nın yeni yayımlanan açıklara karşı sürekli yeniden değerlendirmesi (bir bağımlılık dün güvenliyken bugün açık ilan edilebilir).

**Kritik tasarım kararı: kapı (gate) mı, uyarı mı?** Bir bulgu build'i durdurmalı mı (blocking), yoksa yalnızca uyarı mı vermeli? Aşırı katı kapılar (her düşük önemli bulguda build kırmak) geliştiricileri güvenliği bir düşman gibi görmeye iter ve insanlar kapıları atlamanın yollarını arar. Aşırı gevşek olması ise kontrolü anlamsız kılar. Olgun yaklaşım risk temellidir: yüksek güven + yüksek önem taşıyan bulgular build'i kırar; belirsiz veya düşük önemli bulgular bilgilendirir. Ayrıca yeni kod (net-new) daha katı; mevcut teknik borç ise "kanamayı durdur" mantığıyla ayrı ele alınır.

---

## Yaygın Hatalar

Sahada tekrar tekrar görülen, SSDLC'yi başarısız kılan kalıplar:

- **Güvenliği bir aracın satın alınmasına indirgemek.** Kuruluşlar bir SAST aracı alır, CI'ya takar ve "artık güvenliyiz" der. Oysa hiç kimse çıktıya bakmıyor veya herkes yanlış pozitiflerden bıkıp tümünü görmezden geliyorsa araç değersizdir. Araç bir süreç değildir.
- **Alarm yorgunluğunu yönetmemek.** İnceleme kapasitenizin çok üstünde bulgu üreten ayarsız bir tarayıcı, güvenliği artırmaz — azaltır; çünkü gerçek bulgular gürültüde boğulur. Bulguları önceliklendirme, üçgenleme (triage) ve ele alma süreci olmadan tarama teatral bir eylemdir.
- **Tehdit modellemeyi atlayıp yalnızca araçlara güvenmek.** SAST/DAST/SCA implementasyon hatalarını bulur; tasarım kusurlarını bulamaz. Yalnızca araçlara güvenen ekipler, üretimdeki açıkların yarısına yapısal olarak kördür.
- **Güvenlik ekibini kapı bekçisi (gatekeeper) yapmak.** Güvenlik, geliştiriciden bağımsız, en sonda "hayır" diyen bir departman olduğunda gerçek shift left olmaz; sadece "shift right + veto" olur. Amaç, güvenlik yeteneğini geliştirme ekibinin *içine* dağıtmaktır (örneğin "security champions" modeli).
- **SCA'yı bir kez çalıştırıp bırakmak.** Bağımlılıklardaki açıklar sürekli yeni keşfedilir. Dün temiz olan bir kütüphane bugün kritik açıklı olabilir. SCA sürekli, otomatik ve bağımlılık envanteri (SBOM) üzerinden koşmalıdır.
- **Sırları (secrets) koda gömmek.** API anahtarları, parolalar, özel sertifikalar kod deposuna girdiğinde, git geçmişinde kalıcı olurlar; sonradan silmek yetmez, sızan sır *iptal edilip yenilenmelidir* (rotate). Otomatik secret scanning bu yüzden en erken kapıda olmalıdır.
- **"Düzeltildi" ile "doğrulandı"yı karıştırmak.** Bir bulgu için kod değiştirmek, açığın gerçekten kapandığı anlamına gelmez. Her düzeltme, mümkünse açığı yeniden tetikleyen bir güvenlik regresyon testiyle doğrulanmalı ki gelecekte geri gelmesin.

---

## En İyi Pratikler

- **Güvenliği kodun kendisinde varsayılan yap.** Kütüphane ve framework seçimlerinde "güvenli varsayılanlar" (secure by default) sunanları tercih et: otomatik çıktı kodlaması yapan template motorları, parametreli sorguları zorunlu kılan ORM'ler. En iyi güvenlik, geliştiricinin güvensiz olanı yazmasını *zorlaştıran* güvenliktir.
- **Minimum ayrıcalık ve derinlemesine savunma (defense in depth).** Her bileşen yalnızca ihtiyacı olan yetkiye sahip olsun; tek bir kontrol başarısız olduğunda arkasında ikinci bir katman bulunsun. Tehdit modelleme bu katmanların nereye konacağını söyler.
- **Araçları CI/CD'ye risk temelli kapılarla entegre et.** SAST + SCA pull request'te, DAST staging'de, secret scanning commit'te. Kör "her şeyi kır" değil, "önemli olanı kır" politikası kullan.
- **Bulguları bir geri bildirim döngüsüne bağla.** Her bulgunun bir sahibi, bir önceliği ve bir yaşam döngüsü olsun. Triage yapılmayan bir bulgu, olmayan bir bulgudur.
- **Tehdit modellemeyi tasarımın rutini yap.** Ağır değil, sık ve hafif. En riskli akışlardan başla; her mimari değişiklikte güncelle.
- **Yazılım tedarik zincirini kanıtla.** SBOM üret, bağımlılıkları hash ile sabitle (pin), mümkünse imzalı artefakt kullan, dependency confusion'a karşı iç depolarını koru.
- **Ölçütü "araç sayısı" değil, "ortalama düzeltme süresi" yap.** Bir SSDLC'nin olgunluğu kaç araç koştuğuyla değil, bir açığın keşfinden kapanmasına kadar geçen sürenin (mean time to remediate) ne kadar kısa olduğuyla ölçülür.
- **İnsanı unutma.** Güvenli kodlama eğitimi, security champions programı ve tehdit modelleme oturumları, hiçbir aracın veremeyeceği tasarım-düzeyi savunmayı sağlar. Araçlar hataları yakalar; insanlar kusurları önler.

---

## Özet

Güvenli SDLC'nin merkezi fikri, güvenliği zamanda sola kaydırmak (shift left) ve onu bir son-denetim değil, her aşamaya gömülü bir nitelik yapmaktır. Bunun ekonomik gerekçesi, kusur maliyetinin yaşam döngüsünde geç bulundukça biriken bağımlılıklarla birlikte büyümesidir. SAST kodu içeriden okur ama tasarım kusurlarına ve çalışma zamanına kördür; DAST çalışan sistemi dışarıdan sınar ama kök nedeni ve ulaşamadığı yolları göremez; SCA sizin yazmadığınız bağımlılık kodundaki bilinen açıkları yakalar ama bilinmeyenlere ve tedarik zinciri saldırılarına karşı takviye gerektirir. Bu üç aracın hiçbiri tek başına yeterli değildir ve hiçbiri tasarım kusurlarını bulamaz — o boşluğu STRIDE gibi çerçevelerle sistematik yürütülen tehdit modelleme doldurur. En sağlam savunmalar, tehdidin kök nedeninden doğrudan türetilen, saldırı mantığının negatifi olan kontrollerdir. Ve nihayetinde SSDLC bir araç yığını değil, insan, süreç ve otomasyonu birlikte çalıştıran bir mühendislik kültürüdür.
