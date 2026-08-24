# SIEM ve Detection Engineering: Korelasyon, Kural Yazımı, False Positive Dengesi ve ATT&CK Eşleme

## Giriş ve Tanım

SIEM (Security Information and Event Management), bir kurumun farklı kaynaklarından (sunucular, ağ cihazları, uç noktalar, kimlik sağlayıcılar, bulut servisleri) üretilen log ve olay verilerini merkezî bir yerde toplayan, normalize eden, ilişkilendiren (correlate) ve üzerinde tespit kuralları çalıştıran bir platformdur. Splunk, Microsoft Sentinel, Elastic Security, IBM QRadar ve Google Chronicle bu kategorinin bilinen örnekleridir.

Detection Engineering ise SIEM'in üzerine kurulan disiplinin adıdır: tehdit davranışlarını anlamlı, sürdürülebilir ve düşük gürültülü tespit kurallarına (detection rules / analytics) dönüştürme mühendisliğidir. Burada kritik ayrım şudur: SIEM bir *araçtır*, Detection Engineering ise bir *süreç ve mühendislik disiplinidir*. Bir kurumun elinde en pahalı SIEM olabilir ama iyi tasarlanmış tespit mantığı yoksa, o SIEM yalnızca pahalı bir log arşividir.

Detection Engineering'i geleneksel "imza tabanlı" güvenlikten ayıran şey, davranış odaklı düşünmesidir. Antivirüs bir dosyanın hash değerini bilinen kötücül hash'lerle karşılaştırır; Detection Engineering ise "bir kullanıcı hesabı, normalde hiç kullanmadığı bir saatte, olağandışı bir coğrafyadan, arka arkaya başarısız girişlerden sonra başarılı giriş yaptı ve hemen ardından ayrıcalık yükseltme girişiminde bulundu" gibi bir *anlatıyı* tespit etmeye çalışır.

## Kök Neden: Neden Korelasyon Gerekir?

Bu bölümde "neden böyle çalışıyor" sorusunu yanıtlayalım, çünkü Detection Engineering'in tüm mantığı tek bir gerçekten doğar: **tek başına hiçbir log satırı bir saldırıyı kanıtlamaz.**

Bir saldırı, doğası gereği çok adımlı bir süreçtir. Saldırgan önce keşif yapar, sonra bir yere sızar (initial access), kalıcılık sağlar (persistence), ayrıcalık yükseltir (privilege escalation), yatay hareket eder (lateral movement) ve nihayetinde veriyi dışarı çıkarır (exfiltration). Bu adımların her biri, kendi başına bakıldığında masum görünebilecek olaylar üretir:

- Bir başarısız giriş denemesi normaldir; kullanıcılar şifre yanlış girer.
- Bir PowerShell çalıştırılması normaldir; yöneticiler her gün kullanır.
- Bir dış IP'ye yapılan bağlantı normaldir; internet böyle çalışır.

İşte korelasyonun kök nedeni tam olarak burasıdır. **Korelasyon, tek başına anlamsız olan olayları zaman, varlık (host/user) ve mantıksal ilişki ekseninde birleştirerek anlamlı bir örüntü çıkarma işlemidir.** Başarısız 50 giriş + ardından 1 başarılı giriş + ardından yeni bir servis hesabı oluşturulması, ayrı ayrı "gürültü" iken birlikte bir "brute-force sonrası ele geçirme" anlatısı oluşturur.

Bu yüzden Detection Engineering'de sürekli sorulan soru şudur: *"Bu olay hangi diğer olaylarla birlikte görülürse anlam kazanır?"* Bir olayın tespit değeri, izole edilmiş halinde değil, bağlam içinde ortaya çıkar.

## Log Toplama ve Normalizasyon: Görünmezliğin Temeli

Korelasyona geçmeden önce anlaşılması gereken bir gerçek var: **tespit edemediğiniz şeyi savunamazsınız, log'unu toplamadığınız şeyi de tespit edemezsiniz.** Bu, Detection Engineering'in "görünürlük" (visibility) problemidir.

Ham log'lar birbirinden çok farklı formatlarda gelir. Bir Windows olay log'unda kullanıcı alanı `TargetUserName` iken, bir Linux `auth.log` satırında `user=`, bir bulut sağlayıcısında `actor.email` olabilir. Normalizasyon, bu farklı alanları ortak bir şemaya (örneğin Elastic'in ECS'i veya OSSEM gibi topluluk şemaları) haritalamaktır.

Normalizasyonun neden bu kadar kritik olduğunu bir örnekle görelim: Eğer "başarısız giriş" olayını yalnızca Windows'a özel alan adıyla arayan bir kuralınız varsa, aynı davranış Linux tarafında gerçekleştiğinde kurallarınız kör kalır. İyi Detection Engineering, kuralları mümkün olduğunca *normalize edilmiş alanlar* üzerine yazar; böylece tek bir kural birden fazla kaynağı kapsar ve bakımı kolaylaşır.

Burada yaygın bir tuzak şudur: Kurumlar "her şeyi topla" der ve depolama maliyeti patlar, ama gerçekten ihtiyaç duyulan yüksek değerli log'lar (örneğin PowerShell script block logging, Windows Sysmon, kimlik doğrulama olayları, DNS sorguları) çoğu zaman varsayılan olarak *kapalıdır*. Görünürlüğün gerçek darboğazı depolama değil, doğru log kaynaklarının etkinleştirilmemiş olmasıdır.

## Korelasyon Mantığı ve Türleri

Korelasyonu nasıl kurgulayacağımızı anlamak için farklı korelasyon desenlerini ayırt etmek gerekir.

### Zaman Penceresine Dayalı Korelasyon (Temporal)

En yaygın desendir. "Belirli bir zaman penceresi içinde, aynı varlık üzerinde, X olayının ardından Y olayı gerçekleşti mi?" Örneğin: Aynı kaynak IP'den 5 dakika içinde 20'den fazla başarısız giriş, ardından bir başarılı giriş. Buradaki mühendislik kararı zaman penceresinin genişliğidir. Pencere çok darsa, yavaş ("low and slow") saldırıları kaçırırsınız; çok genişse, ilgisiz olaylar birbirine bulaşır ve false positive artar.

### Eşik Tabanlı Korelasyon (Threshold / Aggregation)

"Bir varlık, bir metrikte normalden anlamlı ölçüde saptı mı?" Bir kullanıcının bir saatte 500 dosyaya erişmesi, tek bir dosyaya erişmesinden farklı bir sinyaldir. Eşikler statik (sabit sayı) veya dinamik (baseline'a göre) olabilir.

### Varlık/Kimlik Korelasyonu (Entity Correlation)

Farklı kaynaklardaki olayları aynı gerçek dünya varlığına (bir kullanıcı, bir cihaz) bağlar. VPN log'undaki bir kullanıcı adı, EDR log'undaki bir makine adı ve bulut log'undaki bir e-posta aslında aynı kişiye ait olabilir. Bu "kimlik grafiği" kurulmadan, bir saldırganın adımlarını uçtan uca izlemek mümkün olmaz.

### İstatistiksel / Davranışsal Korelasyon (UEBA)

Kurallar "bilinen kötüyü" arar; davranış analitiği (User and Entity Behavior Analytics) ise "bilinen iyiden sapmayı" arar. Bir kullanıcının normal giriş saatleri, eriştiği sistemler, kullandığı coğrafyalar bir baseline oluşturur; bundan anlamlı sapma bir sinyal üretir. Bunun kök mantığı şudur: Saldırgan geçerli kimlik bilgileriyle giriş yaptığında hiçbir "kötü imza" üretmez, ama *davranışı* meşru kullanıcınınkinden farklıdır.

## Somut Örnek: Bir Kimlik Bilgisi Ele Geçirme Senaryosu

Kavramları somutlaştıralım. Diyelim ki bir saldırgan, phishing yoluyla bir çalışanın Office/kurumsal kimlik bilgilerini ele geçirdi. Log'larda şunları gözlemleriz:

1. Kullanıcı `ahmet` normalde İstanbul'dan, mesai saatlerinde giriş yapar.
2. Saat 03:14'te, bilinmeyen bir coğrafyadan (farklı bir ülke IP bloğu) `ahmet` hesabıyla başarılı bir giriş gerçekleşir.
3. Aynı oturumdan 2 dakika içinde e-posta yönlendirme kuralı (mail forwarding rule) oluşturulur.
4. Ardından, kullanıcının daha önce hiç erişmediği bir dosya deposuna toplu erişim başlar.

Tek tek bakıldığında: Yeni coğrafyadan giriş olabilir (seyahat), yönlendirme kuralı olabilir (kullanıcı isteyebilir), dosya erişimi olabilir. Ama bir korelasyon kuralı şöyle düşünür: *"İmkânsız seyahat (impossible travel) + hemen ardından posta yönlendirme kuralı + olağandışı veri erişimi"* birleşince, bu bir "hesap ele geçirme" (account takeover) anlatısıdır.

İşte "impossible travel" mantığının kök nedeni: İki başarılı giriş arasındaki coğrafi mesafe, o süre içinde fiziksel olarak kat edilemeyecek kadar büyükse (örneğin İstanbul'dan 20 dakika sonra başka bir kıtadan giriş), bu ya bir VPN karmaşasıdır ya da iki farklı aktörün aynı hesabı kullandığının işaretidir. Buradaki mühendislik zorluğu, VPN ve kurumsal proxy'lerin bu sinyali doğal olarak tetiklemesidir; bu yüzden bilinen VPN çıkış IP'lerinin allowlist'lenmesi gerekir.

## Kural Yazımı: Bir Hipotezden Analitiğe

İyi bir tespit kuralı havadan yazılmaz; bir *hipotezden* doğar. Detection Engineering süreci genellikle şöyle ilerler:

**1. Hipotez / Tehdit modeli.** "Saldırgan Windows'ta kalıcılık için scheduled task oluşturabilir." Bu, tespit etmek istediğimiz davranıştır.

**2. Veri kaynağı belirleme.** Bu davranış hangi log'da görünür? Windows olay log'larında görev oluşturma olayları ve/veya Sysmon'un process creation olayları. Eğer bu log'u toplamıyorsak, kural yazmadan önce görünürlüğü sağlamamız gerekir.

**3. Mantığın yazılması.** Kuralı, gürültüyü minimize edecek şekilde daraltmak. Örneğin yalnızca "scheduled task oluşturuldu" demek yetmez, çünkü meşru yazılım kurulumları bunu sürekli yapar. Bunun yerine: "Beklenmedik bir ebeveyn süreç (örneğin bir Office uygulaması veya bir betik yorumlayıcı) tarafından oluşturulan, komut satırında şüpheli indirme/çalıştırma kalıpları barındıran görevler."

**4. Test ve doğrulama.** Kuralı gerçek kötücül davranışa karşı test etmek. Bunun için Atomic Red Team gibi açık kaynak saldırı simülasyon kütüphaneleri kullanılır; belirli bir ATT&CK tekniğini kontrollü şekilde çalıştırır ve kuralınızın tetiklenip tetiklenmediğini görürsünüz.

**5. Ayar (tuning) ve devreye alma.** Üretimde bir süre "sessiz" (alarm üretmeden, sadece kaydederek) çalıştırıp false positive oranını ölçmek, sonra allowlist'lerle daraltmak.

Kural yazımında en önemli mühendislik prensibi şudur: **Kuralı davranışın en değişmez (invariant) parçasına dayandır.** Saldırganlar dosya adlarını, IP'leri, hash'leri kolayca değiştirir; ama tekniğin özündeki davranış (örneğin bir sürecin LSASS bellek alanına erişmesi) daha zor değiştirilir. Bu, David Bianco'nun "Pyramid of Pain" (Acı Piramidi) kavramının özüdür: Hash gibi göstergelere dayanan tespit saldırgana çok az acı verir (kolayca değiştirir), TTP'lere (taktik, teknik, prosedür) dayanan tespit ise en çok acıyı verir.

### Detection-as-Code

Modern Detection Engineering, kuralları yazılım gibi ele alır. Kurallar YAML/kod olarak sürüm kontrolünde (Git) tutulur, kod incelemesinden geçer, otomatik testlerle doğrulanır ve CI/CD ile devreye alınır. Sigma bu yaklaşımın merkezindedir: Sigma, SIEM'den bağımsız, üretici-nötr bir kural yazım formatıdır. Bir kuralı Sigma'da bir kez yazar, sonra onu Splunk sorgusuna, Sentinel KQL'ine veya Elastic sorgusuna *çevirirsiniz*. Bunun kök faydası, tespit mantığını belirli bir ürüne kilitlenmekten kurtarmasıdır.

## En Zorlu Denge: False Positive ve False Negative

Detection Engineering'in kalbinde bir gerilim vardır ve bu gerilim asla tamamen çözülemez, yalnızca dengelenebilir.

- **False Positive (Yanlış Pozitif):** Kural alarm verdi ama gerçek bir saldırı yoktu. Meşru davranışı kötücül sandı.
- **False Negative (Yanlış Negatif):** Gerçek bir saldırı vardı ama kural sessiz kaldı. Kaçırdı.

Bu ikisi arasında doğrudan bir gerilim vardır. Kuralı gevşetirseniz (daha geniş yakalarsanız) false negative azalır ama false positive artar. Kuralı sıkarsanız (daha dar yakalarsanız) false positive azalır ama gerçek saldırıları kaçırma riski (false negative) artar.

Neden bu denge bu kadar kritik? Çünkü **false positive'in gerçek maliyeti analistin dikkatidir.** Bir SOC analisti günde yüzlerce alarma bakamaz. Eğer kurallarınızın çoğu yanlış alarm üretiyorsa, "alarm yorgunluğu" (alert fatigue) oluşur. Alarm yorgunluğunun en tehlikeli sonucu, gerçek bir saldırı alarmının bu gürültü yığınının içinde fark edilmeden kaybolmasıdır. Yani ironik biçimde, *çok fazla false positive, dolaylı olarak false negative'e yol açar.* Meşhur büyük ihlallerin birçoğunda SIEM aslında alarm üretmiştir; ama o alarm binlerce gürültülü alarmın arasında boğulmuştur.

Bu dengeyi yönetmenin pratik yolları:

**Bağlam zenginleştirme (enrichment).** Bir alarma, karar vermeyi kolaylaştıran bağlamı eklemek: Bu IP tehdit istihbaratında (threat intel) kötü olarak biliniyor mu? Bu kullanıcı bir yönetici mi? Bu makine kritik bir sunucu mu? Zengin bağlam, hem false positive'i azaltır hem de analistin doğrulama süresini kısaltır.

**Risk tabanlı alarmlama (risk-based alerting).** Her tespiti tek başına alarma dönüştürmek yerine, her tespite bir *risk puanı* atamak ve yalnızca bir varlığın biriken risk puanı bir eşiği aştığında alarm üretmek. Böylece tek başına düşük değerli olan sinyaller (bir başarısız giriş, bir olağandışı erişim) tek tek gürültü üretmez; ama aynı varlıkta birikirlerse anlamlı bir alarm oluştururlar. Bu, "her sinyal bir alarm" yaklaşımının modern alternatifidir ve alarm sayısını dramatik biçimde azaltır.

**Baseline ve allowlist yönetimi.** Ortamınızdaki meşru ama "tuhaf görünen" davranışları (yedekleme yazılımının gece toplu dosya erişimi, güvenlik tarayıcısının port taraması) bilmek ve bunları kuraldan hariç tutmak. Ancak burada dikkatli olmak gerekir: Aşırı geniş bir allowlist, saldırganın taklit edebileceği bir kör nokta yaratır.

**Precision ölçümü.** Kuralın kalitesini "kaç alarm ürettiğiyle" değil, ürettiği alarmların ne kadarının gerçek olduğuyla (precision / true positive oranı) ölçmek. Düşük precision'lı kurallar ya iyileştirilmeli ya emekliye ayrılmalıdır.

## MITRE ATT&CK Eşleme: Neden ve Nasıl

MITRE ATT&CK, gerçek saldırganların gözlemlenmiş taktik ve tekniklerinin bir bilgi tabanıdır. "Taktikler" saldırganın *amacını* (neden yaptığını: kalıcılık, keşif, veri çıkarma), "teknikler" ise o amaca *nasıl* ulaştığını tanımlar. Her tekniğin bir kimliği vardır (örneğin T1053 Scheduled Task/Job gibi).

ATT&CK eşlemenin kök faydası, tespit yeteneğinizi *ortak ve ölçülebilir bir dile* bağlamasıdır. Her tespit kuralını ilgili ATT&CK tekniğine etiketlediğinizde şunlar mümkün olur:

**Kapsam analizi (coverage).** Hangi tekniklere karşı tespitiniz var, hangilerine yok? MITRE ATT&CK Navigator adlı ücretsiz araçla ATT&CK matrisini bir "ısı haritası" gibi renklendirerek görebilirsiniz. Kırmızı bölgeler kör noktalarınızdır. Bu, "nereye yatırım yapmalıyım" sorusuna veriyle cevap verir.

**Önceliklendirme.** Tüm teknikleri aynı anda kapatamazsınız. Sektörünüzü hedefleyen tehdit gruplarının (ATT&CK bunları da belgeler) en çok kullandığı tekniklere öncelik verirsiniz. Bu, "tehdit-bilgilendirilmiş savunma" (threat-informed defense) yaklaşımıdır.

**İletişim.** Bir olay yöneticiye anlatılırken "bir uyarı geldi" demek yerine "gözlemlenen davranış Credential Access taktiğindeki bir tekniğe karşılık geliyordu" demek, olayı ortak bir çerçeveye oturtur.

Burada bir uyarı gerekiyor: **ATT&CK eşleme, kapsamı olduğundan iyi gösterme tuzağı taşır.** Bir tekniğe bir kural etiketlemiş olmanız, o tekniği *gerçekten* tespit ettiğiniz anlamına gelmez. Bir tekniğin onlarca farklı uygulama (prosedür) varyasyonu olabilir; sizin kuralınız yalnızca birini yakalıyor olabilir. "Bir teknik için bir kuralım var, demek ki kapsandı" yanılgısı, sahte bir güven duygusu yaratır. Doğru yaklaşım, kapsamı ikili (var/yok) değil, *derinlik* olarak (o teknik için kaç farklı prosedürü yakalıyorum) düşünmektir.

## Sömürü/İstismar Mantığı ile Savunmanın Birlikte Düşünülmesi

Detection Engineering'in en güçlü tarafı, saldırganın perspektifini içselleştirmesidir. İyi bir tespit mühendisi, "bu tekniği ben olsam nasıl kullanır ve tespitten nasıl kaçardım?" diye düşünür. Bunu birkaç örnekle görelim.

**Log manipülasyonu ve tespitten kaçış (evasion).** Deneyimli bir saldırgan, SIEM'in gördüğü şeyi bilir ve buna göre davranır. Örneğin olay log'larını temizleyebilir, PowerShell'in script block logging'ini devre dışı bırakmaya çalışabilir, ya da "living off the land" (LOLBins) denilen, sistemde zaten var olan meşru araçları (yönetim araçları, betik yorumlayıcıları) kullanarak kendi kötücül aracını çalıştırmadan iş görebilir. İstismar mantığı şudur: Meşru araçla yapılan kötücül iş, "kötü dosya" imzası üretmez ve gürültünün içinde kaybolur.

*Savunma tarafı:* Bunun panzehiri, aracın *kendisine* değil, *davranışa* ve *bağlama* bakmaktır. Meşru bir yönetim aracının olağandışı bir ebeveyn süreç tarafından, olağandışı bir kullanıcı bağlamında, olağandışı komut satırı argümanlarıyla çalıştırılması bir sinyaldir. Ayrıca "log temizleme olayının kendisi" güçlü bir tespit fırsatıdır: Bir aktör log'ları temizlediğinde, bu temizleme eyleminin ürettiği olay (log servisinin durması, temizleme olayı) tespit edilebilir. Saldırganın kaçış girişimi, yeni bir tespit yüzeyi yaratır.

**Yavaş ve sessiz saldırı (low and slow).** Saldırgan, eşik tabanlı kuralları bildiği için hızlı brute-force yerine, saatte bir deneme yaparak eşiğin altında kalmaya çalışır (password spraying'in yavaş versiyonu). İstismar mantığı, savunmanın zaman penceresini ve eşiğini istismar etmektir.

*Savunma tarafı:* Zaman penceresini genişletmek (dakikalar yerine günler bazında birçok hesaba yayılan az sayıda deneme aramak), ve tek bir hesaba değil "birçok hesapta az sayıda başarısızlık" desenine (password spraying imzası) bakmak. Yani savunma, saldırganın istismar ettiği boyutu (tek hesap → çok hesap) tersine çevirir.

**Allowlist zehirlemesi.** Saldırgan, savunmanın hangi süreçleri/yolları güvenli kabul edip hariç tuttuğunu tahmin eder ve kendini o güvenli bölgeye yerleştirmeye çalışır (örneğin geçici klasörler veya sık hariç tutulan sistem yolları).

*Savunma tarafı:* Allowlist'leri mümkün olduğunca dar tutmak, yol bazlı değil imza/davranış bazlı hariç tutmalar yapmak ve hariç tutulan bölgeleri periyodik olarak gözden geçirmek.

Buradaki bütünsel ders şudur: **Savunma ve saldırı ayrılamaz.** Bir tespit kuralı yazarken, o kuralın nasıl atlatılacağını düşünmeden yazmak, saldırganın hediye ettiği bir kör nokta bırakmaktır.

## Yaygın Hatalar

**1. "Her şeyi yakala" yanılgısı.** Yeni başlayan ekipler, mümkün olduğunca çok alarm üretmenin daha güvenli olduğunu sanır. Gerçek tam tersidir: Gürültü, gerçek tehdidi gizler. Kalite, nicelikten üstündür.

**2. Kaynak verilerini doğrulamadan kural yazmak.** Toplandığını sandığınız log aslında gelmiyorsa (log kaynağı sessizce kesilmişse), kuralınız hiç tetiklenmez ve siz "sistem sessiz, demek ki güvenli" yanılgısına düşersiniz. Log kaynaklarının canlılığını (log source health) izlemek, kuralların kendisi kadar önemlidir. Görünmez bir false negative, gördüğünüz bir false positive'den çok daha tehlikelidir.

**3. Kuralları emekliye ayırmamak.** Bir ortam sürekli değişir; yeni yazılımlar gelir, altyapı değişir. Bir zamanlar iyi çalışan kural, bugün ya gürültü üretiyordur ya da hiç anlam ifade etmiyordur. Kurallar canlı varlıklardır; bakım ve emeklilik süreci gerektirir.

**4. Statik eşiklere aşırı güvenmek.** "50 başarısız giriş" eşiği küçük bir ekip için makul, büyük bir kurumsal ortam için gülünç derecede düşük olabilir. Eşikler ortama göre ölçeklenmeli, mümkünse baseline'a dayanmalıdır.

**5. Test edilmemiş kural.** Kuralı gerçek saldırı davranışına karşı hiç test etmeden üretime almak, çalıştığını *varsaymaktır*. Detection Engineering'de "çalışıyor sanmak", çalışmamaktan daha tehlikelidir çünkü sahte güven yaratır.

**6. Bağlamsız alarm.** Analiste "şu IP şüpheli" deyip onu araştırma yükünün tamamıyla baş başa bırakmak, ortalama müdahale süresini (MTTR) uzatır. Alarm, kendini açıklayacak bağlamı taşımalıdır.

**7. ATT&CK'i pazarlama olarak kullanmak.** Kapsamı gerçekte olduğundan geniş göstermek için tekniklere gevşekçe etiket yapıştırmak, kurumun kendi kendini kandırmasıdır.

## En İyi Pratikler

**Görünürlükle başla.** Kural yazmadan önce, tespit etmek istediğin davranışın hangi log'da göründüğünü doğrula ve o log'un gerçekten toplandığından emin ol. Yüksek değerli kaynakları (process creation/Sysmon, PowerShell logging, kimlik doğrulama, DNS, bulut denetim log'ları) önceliklendir.

**Davranışa göre yaz, göstergeye göre değil.** Pyramid of Pain'i rehber al: Mümkün olduğunca TTP seviyesinde tespit yaz. Hash ve IP tabanlı tespitler hızlı ve ucuzdur ama kısa ömürlüdür; tamamlayıcı olarak kullan, temel dayanak yapma.

**Detection-as-code benimse.** Kuralları Git'te sürümle, kod incelemesinden geçir, mümkünse Sigma gibi taşınabilir bir formatta yaz. Bu, tespit mantığını denetlenebilir, tekrar üretilebilir ve ürün-bağımsız kılar.

**Sürekli test et.** Atomic Red Team gibi araçlarla tespitlerini düzenli olarak provoke et. "Purple team" tatbikatları (saldırı ve savunma ekiplerinin birlikte çalışması) kör noktaları ortaya çıkarmanın en etkili yoludur. Bir kuralın gerçekten çalıştığının tek kanıtı, gerçek saldırı davranışını yakaladığını görmektir.

**Precision'ı ölç ve tuning'i sürekli kıl.** Her kural için gerçek pozitif oranını izle. Düşük precision'lı kuralları ya iyileştir ya emekli et. Tuning bir defalık iş değil, süregelen bir döngüdür.

**Risk tabanlı alarmlamaya geç.** "Her sinyal bir alarm" modelinden, sinyalleri varlık bazında biriktirip eşik aşımında alarm üreten modele geç. Bu, alarm yorgunluğunu azaltmanın en etkili yapısal çözümüdür.

**ATT&CK ile kapsamını haritalandır ama dürüst ol.** Navigator ile kör noktalarını görselleştir, ama kapsamı ikili değil derinlik olarak değerlendir. "Bu teknik için bir kuralım var" ile "bu tekniğin bilinen prosedürlerinin çoğunu yakalıyorum" arasındaki farkı asla unutma.

**Saldırgan gibi düşün.** Her kuralı yazarken "bunu nasıl atlatırdım?" diye sor. Tespitin ve kaçışın birlikte evrimleştiğini kabul et; savunmanı statik değil, saldırganın adaptasyonuna cevap veren yaşayan bir sistem olarak tasarla.

**Belgelendir.** Her kuralın ne aradığını, hangi hipoteze dayandığını, bilinen false positive kaynaklarını ve analistin ne yapması gerektiğini (runbook) belgele. Bir kural, onu yazan kişi ekipten ayrıldığında da anlaşılabilir olmalıdır.

## Sonuç

SIEM ve Detection Engineering, özünde bir *anlam çıkarma* disiplinidir: Tek başına gürültü olan milyonlarca olayı, saldırganın anlatısını ortaya çıkaracak şekilde ilişkilendirmek. Bu disiplinin ustalığı, ne kadar çok kural yazdığınızda değil, ürettiğiniz alarmların ne kadar güvenilir, bağlamlı ve eyleme dönüştürülebilir olduğunda saklıdır. Korelasyon size anlatıyı verir, iyi kural yazımı o anlatıyı yakalar, false positive dengesi analistinizin dikkatini korur ve ATT&CK eşleme tüm bunları ölçülebilir ve iletilebilir bir çerçeveye oturtur. En kritik gerçek ise değişmez: Tespit ve kaçış birlikte evrilir; bu yüzden Detection Engineering asla "bitmiş" bir iş değil, saldırganla birlikte sürekli öğrenen yaşayan bir süreçtir.
