# Threat Hunting Metodolojisi: Hipotez, Varsayım-İhlal ve Pyramid of Pain

## Giriş: Threat Hunting Nedir ve Neden Var?

Threat hunting (tehdit avcılığı), bir ağda veya sistemde **halihazırda var olduğu varsayılan** ama otomatik güvenlik araçlarının henüz yakalayamadığı düşman aktivitesini, insan öncülüğünde ve proaktif olarak arama disiplinidir. Buradaki en kritik kelime "proaktif"tir. Klasik güvenlik operasyonları reaktiftir: bir alarm çalar (EDR, SIEM, IDS bir imza veya kural eşleşmesi bulur), analist alarmı inceler. Threat hunting ise alarmın olmadığı yerden başlar. Hiçbir uyarı üretilmemişken avcı sorar: "Eğer buraya sofistike bir saldırgan sızmış olsaydı, benim mevcut savunmalarım bunu neden kaçırırdı ve o iz nerede saklı olurdu?"

Bu ayrımı anlamak metodolojinin geri kalanının kökünü oluşturur. Otomatik tespit sistemleri, önceden bilinen kötücül davranışları (bilinen hash'ler, imzalar, IOC'ler) yakalamak için tasarlanmıştır. Ancak gerçek düşman -özellikle APT (Advanced Persistent Threat) seviyesindeki bir aktör- tam olarak bu bilinen kalıplardan kaçınmak için çaba harcar. Dolayısıyla imzaya dayalı savunmanın kör noktası, threat hunting'in var oluş sebebidir.

### Neden "Assume Breach" (İhlal Edilmiş Varsay) Zihniyeti?

Threat hunting'in felsefi temeli **assume breach** (varsayım-ihlal / ihlal edilmiş varsay) yaklaşımıdır. Geleneksel güvenlik, "sınırı yeterince yükseltirsem içeri kimse giremez" varsayımına dayanır. Assume breach ise bu varsayımı reddeder ve şunu kabul eder: Yeterince motive ve kaynaklı bir saldırgan, eninde sonunda bir yol bulur. Sıfır gün (zero-day) açıkları, tedarik zinciri saldırıları, sosyal mühendislik ve içeriden tehditler bu gerçeğin kanıtıdır.

Bu zihniyet neden önemli? Çünkü savunmacının odağını **önlemeden** (prevention) **tespite** ve **kısaltmaya** (dwell time azaltma) kaydırır. Sektörde "dwell time" olarak bilinen, saldırganın ilk sızmadan tespit edilmesine kadar geçen süre, kritik bir metriktir. Bu süre gün, hafta, hatta ay boyunca uzayabilir; her geçen gün saldırgana lateral movement (yanal hareket), veri sızdırma ve kalıcılık kurma için daha fazla fırsat verir. Threat hunting'in en somut iş değeri, işte bu dwell time'ı düşürmektir. İhlal edilmiş olabileceğinizi varsayarsanız, ihlali aramak için gerçekten harekete geçersiniz; içeri kimsenin giremeyeceğini varsayarsanız, aramazsınız.

## Metodolojinin Kalbi: Hipotez Odaklı Avlanma

### Hipotez Nedir ve Neden Zorunludur?

Threat hunting'i rastgele log karıştırmaktan ayıran tek şey **hipotezdir**. Hipotez, avın başında ortaya konan, test edilebilir ve yanlışlanabilir bir iddiadır. Örnek bir hipotez: "Etki alanımızdaki (domain) bir kullanıcı hesabı, olağandışı saatlerde WMI veya PsExec üzerinden birden fazla iş istasyonuna uzaktan komut çalıştırmak için kullanılıyor olabilir."

Neden hipotez zorunludur? Çünkü kurumsal bir ağ, günde milyarlarca log satırı üretir. Hedefsiz bir şekilde "kötü bir şey var mı?" diye bakmak, samanlıkta neyi aradığını bilmeden iğne aramaya benzer; hem tükenmişlik hem de yanlış güven doğurur. Hipotez, bu devasa arama uzayını yönetilebilir, ölçülebilir bir soruya daraltır. İyi bir hipotez üç özelliğe sahiptir:

- **Spesifiktir:** Belirli bir teknik, aktör davranışı veya varlığı hedef alır. "Ağda malware var mı" kötü; "Zamanlanmış görevler (scheduled tasks) aracılığıyla kalıcılık kuran bir tehdit var mı" iyi bir hipotezdir.
- **Test edilebilirdir:** Elimizdeki veriyle (log, telemetri) doğrulanabilir veya çürütülebilir olmalıdır. Toplamadığınız bir veri türüne dayanan hipotez, av değil dilek listesidir.
- **Yanlışlanabilirdir:** Avın "hipotez doğrulanmadı" ile bitmesi de geçerli, hatta değerli bir sonuçtur. Bu, o tespit yüzeyinin temiz olduğuna dair kanıt üretir ve gelecekteki avlar için taban çizgisi (baseline) oluşturur.

### Hipotezler Nereden Gelir?

Hipotez üretimi, avcının ustalığının en çok belli olduğu aşamadır. Başlıca üç kaynak vardır:

**1. Threat Intelligence kaynaklı hipotezler.** Bir tehdit istihbaratı raporu, belirli bir aktör grubunun (örneğin finans sektörünü hedefleyen bir grup) hangi teknikleri kullandığını anlatır. Avcı bu bilgiyi alır ve "Bu aktörün TTP'leri (Tactics, Techniques, Procedures) benim ortamımda gözlemlenebilir mi?" sorusuna dönüştürür. Bu hipotezler MITRE ATT&CK çerçevesiyle çok iyi eşleşir; her teknik (örneğin T1053 Scheduled Task/Job gibi ATT&CK teknik kimlikleri) doğrudan bir av hipotezine çevrilebilir.

**2. Durumsal farkındalık / ortam bilgisi kaynaklı hipotezler.** Avcı kendi ortamını tanır: Hangi sunucular kritik? Normalde hangi hesap hangi makineye erişir? Bu "normal"in bilinmesi, "anormal"in tanımlanmasını sağlar. Örneğin bir yedekleme sunucusunun asla dışa doğru DNS sorgusu yapmaması gerektiğini bilen avcı, "Bu sunucudan çıkan olağandışı DNS trafiği, DNS tünelleme (DNS tunneling) yoluyla veri sızdırma olabilir mi?" hipotezini kurar.

**3. Anomali ve içgüdü kaynaklı hipotezler.** Bazen bir veride "yanlış" duran ama alarm üretmeyen bir şey dikkat çeker: beklenmedik bir PowerShell parametresi, garip bir üst-alt süreç (parent-child process) ilişkisi. Deneyimli avcının sezgisi, bunları formel bir hipoteze dönüştürür.

## Pyramid of Pain: Avcının Stratejik Pusulası

### Modelin Tanımı

**Pyramid of Pain** (Acı Piramidi), David Bianco tarafından ortaya konmuş, threat hunting ve tespit stratejisinin belki de en önemli kavramsal aracıdır. Model şu soruyu yanıtlar: "Bir saldırganın hangi göstergesini (indicator) tespit edip engellersem, o saldırgana en fazla acıyı çektiririm?" Piramit, IOC türlerini tabandan tepeye doğru, saldırgan için "değiştirilmesi ne kadar zor" olduklarına göre sıralar:

- **Hash değerleri (en alt, en kolay):** Bir dosyanın MD5/SHA hash'i. Saldırgan dosyada tek bir bit değiştirsin, hash tamamen değişir. Tespit değeri neredeyse sıfırdır.
- **IP adresleri:** Saldırgan yeni bir sunucu kiralayarak dakikalar içinde IP değiştirir.
- **Domain adları:** Değiştirmesi IP'den biraz daha zahmetlidir (kayıt, DNS ayarı gerekir) ama yine de ucuzdur.
- **Ağ ve host artefaktları (Network/Host Artifacts):** Belirli bir User-Agent string'i, kayıt defteri (registry) anahtarı, dosya adı deseni. Bunları değiştirmek saldırganın araçlarını ayarlamasını gerektirir; can sıkıcıdır.
- **Araçlar (Tools):** Saldırganın kullandığı belirli bir framework veya araç. Bunu tespit edip engellerseniz, saldırgan yeni bir araç bulmak veya geliştirmek zorunda kalır; ciddi çaba ister.
- **TTP'ler (en tepe, en zor):** Taktikler, Teknikler ve Prosedürler. Yani saldırganın *davranış biçimi* -nasıl keşif yaptığı, nasıl yanal hareket ettiği, nasıl kalıcılık kurduğu. Bunu tespit ederseniz, saldırgan kendi operasyonel yöntemini baştan öğrenmek zorunda kalır ki bu son derece maliyetlidir.

### Neden Bu Model Bu Kadar Merkezi?

Pyramid of Pain'in dehası, threat hunting'in nereye enerji harcaması gerektiğini net biçimde göstermesidir. Piramidin tabanı (hash, IP) otomatik tespitin ve tehdit beslemelerinin (threat feed) alanıdır; ucuz, hızlı ama kırılgan. Bir avcı zamanını burada harcarsa, saldırganın beş dakikada aşabileceği bir savunma kurmuş olur.

Gerçek avcılık, piramidin **üst katmanlarına** -araçlara ve özellikle TTP'lere- odaklanır. Neden? Çünkü bir saldırgan IP'sini kolayca değiştirebilir ama örneğin "credential dumping" (kimlik bilgisi çalma) için LSASS bellek alanına erişme *davranışını* değiştiremez; bu, saldırının doğasında olan bir adımdır. Eğer siz bu davranışı yakalayacak bir av ve tespit yeteneği kurarsanız, saldırgan hangi aracı, hangi IP'yi kullanırsa kullansın yakalanır. İşte bu yüzden olgun threat hunting programları hipotezlerini TTP seviyesinde kurar ve MITRE ATT&CK ile bu yüzden bu kadar sıkı entegre çalışır: ATT&CK, esasen TTP'lerin kataloglanmış halidir.

## Veri: Avın Olmazsa Olmaz Yakıtı

### Veri Olmadan Av Olmaz

En zarif hipotez bile, onu test edecek veri yoksa hükümsüzdür. Threat hunting bir veri disiplinidir. Avcının şu soruyu her hipotezden önce sorması gerekir: "Bu hipotezi doğrulamak için hangi telemetriye ihtiyacım var ve o telemetri gerçekten toplanıyor mu, ne kadar süre saklanıyor?"

Bu, sıklıkla ihmal edilen ama kritik bir noktadır. Örneğin süreç oluşturma (process creation) loglarını -komut satırı argümanlarıyla birlikte- toplamıyorsanız, komut satırına dayalı hiçbir avı yapamazsınız. Windows ortamında bu genellikle Sysmon gibi bir telemetri aracının konuşlandırılmasını ve gelişmiş denetim (audit) politikalarının açılmasını gerektirir. Ağ tarafında NetFlow, DNS logları ve proxy logları; kimlik tarafında authentication (kimlik doğrulama) logları temel veri kaynaklarıdır.

### Veri Kaynağı Kategorileri ve Neden Önemli Oldukları

- **Endpoint/host telemetrisi:** Süreç oluşturma, üst-alt süreç ilişkileri, DLL yüklemeleri, registry değişiklikleri, dosya oluşturma. Piramidin üst katmanlarındaki (TTP) avların çoğu buradan beslenir çünkü davranış çoğunlukla host üzerinde gerçekleşir.
- **Ağ telemetrisi:** DNS sorguları, bağlantı meta verisi (flow), TLS handshake bilgileri. Command-and-control (C2) trafiği, veri sızdırma ve lateral movement izleri burada görülür.
- **Kimlik ve erişim logları:** Kim, ne zaman, nereye giriş yaptı. Ele geçirilmiş hesapların ve yetki yükseltmenin (privilege escalation) tespiti buna dayanır.

Veri kalitesi de en az veri varlığı kadar önemlidir. Zaman senkronizasyonu (tüm logların ortak ve doğru bir saat kaynağından beslenmesi) olmadan olayları bir zaman çizelgesinde birleştiremezsiniz. Alan normalizasyonu (bir kaynağın "src_ip" dediğine diğerinin "source" demesi sorunu) olmadan kaynaklar arası korelasyon yapamazsınız.

## Somut Bir Av Örneği: Baştan Sona

Kavramları bir arada görmek için tam bir av senaryosu izleyelim.

**Hipotez:** "Ortamımızda bir saldırgan, meşru bir Windows sistem aracını (living-off-the-land binary, kısaca LOLBin) kötüye kullanarak uzak bir sunucudan yük (payload) indiriyor olabilir." Bu, piramidin TTP katmanında yer alan güçlü bir hipotezdir çünkü belirli bir aracı değil, bir *davranışı* hedefler.

**Veri ihtiyacı:** Süreç oluşturma logları (komut satırı argümanlarıyla), ağ bağlantı logları ve DNS logları.

**Arama mantığı:** Avcı, normalde ağdan indirme yapmaması beklenen sistem araçlarının, dış bir adrese bağlantı kuran süreçlerini arar. Örneğin, bir betik yorumlayıcısının veya bir sertifika yönetim aracının, beklenmedik bir şekilde HTTP üzerinden dosya çeken bir komut satırıyla çalıştırıldığı örnekleri tespit etmeye çalışır. Burada avcı, "izin verilenler listesi" (allow-listing) mantığıyla çalışır: Bilinen ve meşru kullanımları eleyip geriye kalan olağandışı örneklere odaklanır.

**Bulgu ve zenginleştirme:** Diyelim ki avcı, tek bir iş istasyonunda, bir kullanıcının profil klasöründen çalışan ve dış bir IP'ye bağlanan şüpheli bir süreç buldu. Şimdi zenginleştirme (enrichment) devreye girer: O IP'nin itibarı nedir? O makinede aynı zaman diliminde başka ne oldu? Üst süreç (parent process) neydi -bir e-posta ekinden mi, bir tarayıcıdan mı doğdu? Bu adım, tek bir veri noktasını bir olay anlatısına dönüştürür.

**Sonuç:** Hipotez doğrulanırsa, av bir incident response (olay müdahale) sürecine devredilir. Doğrulanmazsa bile avcı değerli çıktı üretir: Bu davranışı yakalayacak yeni bir kalıcı tespit kuralı (detection rule) yazılabilir. **İyi bir avın en önemli çıktısı, o avı bir daha elle yapmak zorunda kalmamak için otomatikleştirilmiş bir tespit üretmesidir.** Buna genellikle "hunt-to-detection pipeline" denir.

## İki Cephe: Hem İstismar Mantığı Hem Savunma

Etkili bir avcı, saldırganın kafasının içine girmeden avlanamaz. Bu yüzden her tekniğin hem sömürü hem savunma yüzünü anlamak gerekir.

### İstismar Tarafından Bakış: Saldırgan Neden Böyle Davranır?

Saldırgan, tespit edilmemek için sürekli olarak "meşru görünme" çabasındadır. Bu, threat hunting'i zorlaştıran temel gerilimdir:

- **Living-off-the-land:** Saldırgan kendi araçlarını getirmek yerine, sistemde zaten var olan meşru araçları kullanır. Neden? Çünkü kendi kötücül dosyası bir hash veya imza bırakır (piramidin tabanı, kolay yakalanır); oysa meşru bir sistem aracı, savunmacının "gürültü" olarak görmezden gelebileceği milyonlarca meşru kullanım arasında kaybolur.
- **Yaşayan hesapları kullanma:** Saldırgan yeni hesap oluşturmak yerine ele geçirdiği meşru hesapları kullanır; çünkü meşru bir kullanıcının girişleri alarm üretmez.
- **Yavaşlık ve sabır:** APT aktörleri kasıtlı olarak yavaş hareket eder ("low and slow"). Veri sızdırmayı küçük parçalara böler, işlemleri normal iş saatlerine yayar. Amaç, eşik tabanlı (threshold-based) alarmları tetiklememektir.

Bu mantığı anlamak, avcının neden piramidin tepesine odaklanması gerektiğini bir kez daha kanıtlar: Saldırgan araçlarını ve göstergelerini gizleyebilir ama işini yapabilmek için *bir yerde* karakteristik bir davranış sergilemek zorundadır.

### Savunma Tarafından Bakış

Savunma stratejisi, bu istismar mantığının aynadaki yansımasıdır:

- **Baseline (taban çizgisi) oluşturma:** "Meşru görünme" saldırısını yenmenin tek yolu, gerçek meşrunun ne olduğunu çok iyi bilmektir. Bir sistem aracının normalde hangi üst süreçten, hangi kullanıcı tarafından, hangi argümanlarla çalıştığını bilirseniz, sapmayı yakalarsınız.
- **Davranışsal tespit:** İmza yerine davranış kuralları yazmak. "Şu spesifik dosyayı ara" yerine "bir ofis uygulamasının bir komut satırı süreci doğurması" gibi kalıpları aramak.
- **Least privilege ve segmentasyon:** Saldırganın lateral movement'ini zorlaştırmak, onu daha fazla ve daha gürültülü adım atmaya zorlar; her ek adım, yakalanma yüzeyini genişletir.
- **Katmanlı görünürlük:** Bir katmanı atlatan saldırgan (örneğin endpoint'te gizlenen), başka bir katmanda (ağ trafiğinde C2 beacon'u olarak) iz bırakır. Savunmacının avantajı budur.

## Yaygın Hatalar

Threat hunting programlarını başarısızlığa götüren tekrar eden hatalar vardır:

**1. Hipotezsiz avlanmak.** En sık hata. Analist bir SIEM konsolu açıp amaçsızca log karıştırır. Bu, saatler harcatır, tükenmişlik yaratır ve "bir şey bulamadık, demek ki güvendeyiz" gibi tehlikeli ve yanlış bir güven doğurur. Aramadığınız şeyi bulamazsınız.

**2. Piramidin tabanında takılıp kalmak.** Tehdit beslemelerinden gelen IP ve hash listelerini kontrol etmeyi "threat hunting" sanmak. Bu değerli bir aktivite olabilir ama otomatik tespittir, av değildir; saldırgana neredeyse hiç acı çektirmez.

**3. Veriyi doğrulamamak.** Toplanmadığını veya yeterince uzun saklanmadığını fark etmeden bir hipotez üzerinde çalışmak. Av sonunda "temiz" çıkabilir ama bu, ortam temiz olduğu için değil, veri olmadığı için "körüz" demektir. Bu iki durumu karıştırmak felakettir.

**4. Bulguları operasyonelleştirmemek.** Aynı avı her ay elle tekrarlamak. İyi bir av, sonunda otomatik bir tespit kuralına, yeni bir dashboard'a veya iyileştirilmiş bir baseline'a dönüşmelidir. Aksi halde program ölçeklenemez.

**5. Sonucu yanlış yorumlamak (base rate hatası).** Anormal olan her şeyi kötücül sanmak. Kurumsal ağlar tuhaf ama meşru davranışlarla doludur. Avcı, "olağandışı" ile "kötücül" arasındaki farkı ayırt etmek için zenginleştirme ve bağlam kullanmalıdır; aksi halde ekibi yanlış pozitiflerle (false positive) boğar.

**6. Belgelememek.** Avın hipotezini, sorgusunu, kapsamını ve sonucunu kaydetmemek. Belgelenmeyen av, tekrarlanamaz ve öğrenilemez; her seferinde sıfırdan başlanır.

## En İyi Pratikler

**Hipotezle başla, hipotezle bitir.** Her avın yazılı bir hipotezi, tanımlı bir kapsamı ve net bir "başarı/başarısızlık" kriteri olsun. Avın sonucu -pozitif veya negatif- kaydedilsin.

**MITRE ATT&CK'i omurga olarak kullan.** Hipotezlerini ATT&CK teknikleriyle eşleştir. Bu, hem sistematik kapsama (hangi teknikleri avladın, hangilerini avlamadın) sağlar hem de avlarını TTP seviyesinde -yani piramidin en acı verici katmanında- tutar.

**Görünürlüğünü ve boşluklarını haritalandır.** Hangi ATT&CK tekniğini tespit edecek verinin olup olmadığını bir matris üzerinde takip et. Av yapamadığın alanlar, veri toplama önceliklerini belirler. Görünürlük boşluğu, saldırganın en sevdiği yerdir.

**Zenginleştirmeyi kurumsallaştır.** Bir IP, host veya hesap bulunduğunda otomatik olarak bağlam getiren süreçler kur. Avcının değerli zamanı manuel arama yerine analizde harcanmalıdır.

**Hunt-to-detection döngüsünü kapat.** Her doğrulanmış (veya doğrulanabilir) av bulgusundan kalıcı bir tespit üret. Threat hunting'in başarı ölçütü sadece "kaç saldırgan yakaladık" değil, "manuel avı otomatik tespite kaç kez dönüştürdük" olmalıdır.

**Purple team ile besle.** Kırmızı takımın (red team) simüle ettiği saldırıları, avcının o davranışı yakalayıp yakalayamadığını test etmek için kullan. Bu, avların ve tespitlerin gerçekten çalıştığını kanıtlayan en dürüst yöntemdir.

**Assume breach'i gerçekten yaşa.** Programın ölçütü, "hiçbir şey bulamadık" değil, "eğer düşman içeride olsaydı görebilecek durumda mıydık" olsun. Bulamamak, iyi bir haber değildir; iyi haber, bulabilecek yetenekte olduğunu kanıtlamaktır.

## Sonuç

Threat hunting, üç sütun üzerinde durur: **doğru sorulmuş bir hipotez**, o hipotezi test edecek **kaliteli veri** ve enerjiyi doğru yere yönlendiren **stratejik bir pusula (Pyramid of Pain)**. Bunları birbirine bağlayan zihniyet ise **assume breach**'tir. Bu disiplin, savunmayı imzaların bittiği yerde başlatır; saldırganın en zor değiştirebileceği şeye -davranışına- odaklanır ve her manuel keşfi kalıcı bir yeteneğe dönüştürerek savunmayı zamanla ölçekler. İyi bir avcı, ağda hiçbir şey bulamadığında rahatlamaz; yalnızca, eğer orada bir şey olsaydı onu görebilecek görünürlüğe ve yönteme sahip olduğundan emin olduğunda rahatlar.
