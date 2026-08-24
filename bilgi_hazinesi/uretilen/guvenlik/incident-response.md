# Olay Müdahalesi (Incident Response / IR) Süreci

## Tanım

Olay müdahalesi (Incident Response, kısaca IR), bir kurumun bir güvenlik olayını (security incident) tespit ettikten sonra bu olayı kontrol altına almak, etkisini sınırlamak, kök nedenini ortadan kaldırmak, normal operasyona geri dönmek ve olaydan ders çıkarmak için izlediği yapılandırılmış süreçtir. Burada önemli bir ayrım vardır: "olay" (event) ile "güvenlik olayı" (incident) aynı şey değildir. Her log satırı bir event'tir; bunların çok küçük bir yüzdesi gerçek bir güvenlik ihlalinin belirtisidir. IR süreci tam olarak bu filtreleme, doğrulama ve tepki verme işini disipline eder.

IR'ı sadece "hack olunca ne yaparız" sorusunun cevabı gibi görmek yaygın ve tehlikeli bir hatadır. IR aslında bir **hazırlık disiplinidir**: olay anındaki başarının büyük kısmı, olay olmadan aylar önce yapılan hazırlıkla belirlenir. Panik anında iyi kararlar üretilmez; iyi kararlar önceden yazılmış runbook'larda, önceden dağıtılmış yetkilerde ve önceden yapılmış tatbikatlarda saklıdır.

## Kök Neden / Çalışma Mantığı: Neden Yapılandırılmış Bir Sürece İhtiyaç Var?

Bir ihlal anında insan beyni en kötü kararları verecek koşullar altındadır: yüksek stres, eksik bilgi, zaman baskısı ve genellikle gecenin bir yarısı. Bu koşullarda insanlar iki uçtan birine kayar. Birinci uç **donup kalma**: kimse sorumluluk almak istemez, "önce yönetime soralım" denir, saatler kaybedilir ve saldırgan bu sırada rahatça yatay hareket (lateral movement) yapar. İkinci uç ise **panikle refleks tepki**: teknik ekip hemen sunucuyu kapatır, makineyi formatlar, "temizler". Bu ikinci uç, birincisinden daha az zararlı gibi görünse de aslında çoğu zaman daha yıkıcıdır; çünkü kanıtları yok eder, saldırganın nereden girdiğini asla öğrenemezsiniz ve büyük ihtimalle arka kapı (backdoor) yerinde kalır, birkaç hafta sonra saldırgan geri döner.

Yapılandırılmış IR süreci tam olarak bu iki uca karşı bir **karar mimarisi**dir. Amaç, olay anında "ne yapacağız?" diye düşünmek zorunda kalmamaktır. Kararlar, roller, iletişim kanalları ve teknik adımlar önceden tanımlanmıştır; olay anında sadece uygulanır. Bu yüzden olgun bir IR programı, olay sıklığından çok, **olayın ortalama tespit ve müdahale süresini** (MTTD ve MTTR — Mean Time To Detect / Respond) düşürmeye odaklanır.

## İki Referans Model: NIST ve SANS Döngüsü

Sektörde iki yaygın referans çerçeve vardır. Bunlar rakip değil, aynı fikrin farklı granülaritede ifadeleridir.

### NIST Modeli (dört ana faz)

NIST'in olay müdahale kılavuzu (Special Publication serisinden, olay müdahalesine ayrılmış doküman) süreci **dört ana faza** ayırır:

1. **Hazırlık (Preparation)**
2. **Tespit ve Analiz (Detection & Analysis)**
3. **Kontrol Altına Alma, Yok Etme ve Kurtarma (Containment, Eradication & Recovery)**
4. **Olay Sonrası Faaliyet (Post-Incident Activity)**

NIST modelinin can alıcı noktası, bunun düz bir çizgi değil bir **döngü** olmasıdır. Post-incident aşamasında çıkarılan dersler doğrudan Preparation aşamasını besler; yani her olay, bir sonraki olaya hazırlığın hammaddesidir.

### SANS Modeli (altı adım — PICERL)

SANS ise aynı süreci altı adımda ifade eder; İngilizce baş harfleriyle **PICERL** olarak hatırlanır:

1. **Preparation (Hazırlık)**
2. **Identification (Tanımlama / Tespit)**
3. **Containment (Kontrol altına alma)**
4. **Eradication (Yok etme)**
5. **Recovery (Kurtarma)**
6. **Lessons Learned (Çıkarılan dersler)**

İki model arasındaki tek gerçek fark granülariteydir. NIST, "Containment, Eradication & Recovery" adımlarını tek bir faz altında topluca sunarken, SANS bunları ayrı adımlara böler. Pratikte SANS'ın ayrımı sahada daha kullanışlıdır; çünkü containment ile eradication arasındaki geçiş, bir IR operasyonundaki en kritik ve en çok hata yapılan noktadır — bunu ayrı adım olarak düşünmek disiplin sağlar.

## Fazların Derinlemesine İncelenmesi

### 1. Hazırlık (Preparation)

Bu faz olay olmadan yaşanır ve IR programının başarısını en çok belirleyen fazdır. Hazırlık üç katmanda düşünülmelidir:

**İnsan katmanı:** Kimin neyi yapacağı önceden bellidir. Bir IR ekibinde tipik roller: olay komutanı (incident commander — teknik değil, koordinasyon rolü), teknik analistler (DFIR — Digital Forensics & Incident Response), iletişim/hukuk sorumlusu ve yönetim köprüsü. Olay komutanının teknik işi yapmaması önemlidir; onun işi kararları vermek, kaynak yönlendirmek ve dış paydaşlarla köprü olmaktır. Teknikçi hem analiz yapıp hem koordinasyon yapmaya çalışırsa ikisini de kötü yapar.

**Süreç katmanı:** Runbook'lar (belirli senaryolar için adım adım talimatlar — ör. "fidye yazılımı şüphesi", "veri sızıntısı şüphesi", "yetkili hesap ele geçirilmesi"), iletişim planı (kimi, hangi kanaldan, hangi eşikte bilgilendireceğiz — özellikle **band dışı / out-of-band** iletişim, çünkü saldırgan kurum e-postasını okuyor olabilir), ve eskalasyon eşikleri.

**Teknik katman:** Log toplama ve merkezileştirme (SIEM), EDR/XDR ajanlarının yaygınlığı, ağ görünürlüğü, ve en önemlisi **log saklama süresinin** yeterliliği. Burada çok yaygın bir gerçek acı vardır: saldırganların ortalama fark edilmeden kalma süresi (dwell time) çoğu zaman haftaları hatta ayları bulur, ama birçok kurum logları sadece birkaç hafta saklar. Sonuç: saldırganın ilk giriş anını gösteren log çoktan silinmiştir ve kök nedene asla ulaşılamaz. Hazırlık aşamasının en somut çıktısı, dwell time'dan uzun bir log saklama politikasıdır.

### 2. Tespit ve Analiz (Detection & Identification)

Bu faz iki ayrı zorluğu içerir. Birincisi **tespit**: olayı fark etmek. Tespit kaynakları çok çeşitlidir — SIEM korelasyon kuralları, EDR uyarıları, kullanıcı ihbarı, üçüncü taraf bildirimi (örneğin bir güvenlik firması veya kolluk kuvvetinin "verileriniz forumda satılıyor" demesi ki bu utanç verici ama sık rastlanan bir tespit yoludur), veya olağandışı sistem davranışı.

İkincisi **analiz / triyaj**: bu bir false positive mi, yoksa gerçek bir olay mı? Gerçekse kapsamı ne? Analiz aşamasında en kritik kavram **kapsam belirleme (scoping)**dir. Klasik ve pahalı hata şudur: analist tek bir ele geçirilmiş makineyi görür, onu izole eder ve "hallettik" der. Oysa saldırgan çoktan üç makineye daha yayılmış, bir servis hesabı çalmış ve kalıcılık (persistence) kurmuştur. Yetersiz scoping ile yapılan containment, saldırgana sizin onu fark ettiğinizi haber vermekten başka işe yaramaz — bu da onu daha hızlı ve daha yıkıcı davranmaya iter.

Analiz sırasında **uzlaşma göstergeleri (Indicators of Compromise, IoC)** toplanır: kötü niyetli IP'ler, domain'ler, dosya hash'leri, kayıt defteri (registry) değişiklikleri, anormal kullanıcı hesapları. Ancak olgun ekipler IoC'lerin ötesine geçip **saldırgan davranışlarını (TTP — Tactics, Techniques and Procedures)** çıkarmaya çalışır. Bunun için MITRE ATT&CK gibi bir çerçeveyle eşleştirme yapmak, saldırganın hangi tekniği kullandığını ve sırada hangi adımın gelebileceğini öngörmeyi sağlar. IoC bugün geçerlidir, saldırgan yarın IP'sini değiştirir; ama davranış kalıbı (ör. "çalınan servis hesabıyla yatay hareket") daha kalıcı ve avlanabilir bir imzadır.

### 3. Kontrol Altına Alma (Containment)

Containment, IR sürecinin kalbidir ve en fazla yargı gerektiren adımdır. Amaç, hasarın yayılmasını durdurmaktır — ama bunu kanıtları yok etmeden ve saldırganı gereksiz yere paniğe sokmadan yapmak gerekir.

Containment genelde iki aşamada düşünülür:

**Kısa vadeli (acil) containment:** Kanamayı durdurmak. Ele geçirilmiş bir makineyi ağdan izole etmek (tercihen kapatmak yerine — kapatmak RAM'deki uçucu kanıtı yok eder ve bazı zararlılar kapanışta iz temizler), ele geçirilmiş bir hesabı devre dışı bırakmak, bir C2 (command-and-control) domain'ini firewall'da engellemek gibi.

**Uzun vadeli containment:** Sistemi tam olarak temizlemeden (eradication'a geçmeden) önce operasyonun sürmesini sağlayacak geçici tedbirler — ör. yamalanmış geçici sistemler devreye almak, ek segmentasyon uygulamak, izleme yoğunluğunu artırmak.

Containment'taki en kritik ve mantıksal olarak en zor karar şudur: **"Hemen izole et" mi, yoksa "izle ve öğren" mi?** Eğer saldırganı hemen izole ederseniz onu fark ettiğinizi belli edersiniz; bu, henüz tüm dayanaklarını (footholds) haritalamadıysanız felakete yol açabilir — saldırgan geri kalan erişimlerini gizler veya sabote (destroy) moduna geçer. Ama izlemeye devam ederseniz, her geçen dakika daha fazla veri sızabilir. Bu karar, olayın türüne göre değişir: aktif veri hırsızlığı (exfiltration) görülüyorsa hız önceliklidir; kapsam belirsizse ve saldırgan henüz zarar vermiyorsa kontrollü gözlem daha akıllıca olabilir. Bu kararı ölçekleyen kişi olay komutanıdır, tek başına bir analist değil.

Önemli bir alt disiplin: **eş zamanlı (synchronized / all-at-once) eradication**. Saldırgan birden fazla dayanağa sahipse (örneğin iki farklı arka kapı ve bir çalıntı VPN kimlik bilgisi), bunları tek tek kapatırsanız, ilkini kapattığınızda saldırgan diğerinden içeri girip kaybettiği erişimi yeniler. Bu yüzden olgun IR ekipleri tüm dayanakları önce haritalar, sonra **hepsini aynı anda** keser. Bu, containment ile eradication arasındaki geçişin neden bu kadar hassas olduğunun ana nedenidir.

### 4. Yok Etme (Eradication)

Eradication, saldırganın erişim araçlarını ve varlığını ortamdan tamamen sökmektir: zararlı yazılımı kaldırmak, saldırganın oluşturduğu hesapları silmek, sömürülen açığı (vulnerability) yamalamak, ele geçirilen tüm kimlik bilgilerini (özellikle servis hesapları ve ayrıcalıklı hesaplar) sıfırlamak.

Buradaki temel prensip şudur: **sadece belirtiyi değil, kök nedeni yok et.** Zararlıyı silmek yetmez; zararlının nasıl girdiği (ilk erişim vektörü — bir phishing e-postası mı, yamalanmamış bir internete açık servis mi, çalıntı bir kimlik bilgisi mi) çözülmeden ortam temizlenmiş sayılmaz. Aksi halde aynı kapıdan tekrar girilir.

Ciddi ihlallerde, özellikle domain controller seviyesinde bir ele geçirme (ör. saldırganın Active Directory'de en üst düzey yetkiye ulaşması) söz konusuysa, tek tek temizlik güvenilmez hale gelir. Bu durumda profesyonel yaklaşım genellikle **temiz kaynaktan yeniden inşa (rebuild from known-good)**dır: sistemleri temiz imajlardan yeniden kurmak, tüm parolaları ve gizli anahtarları döndürmek (rotate). Çünkü bir kez üst düzey yetki ele geçirildiyse, saldırganın hangi arka kapıyı bıraktığını %100 bilemezsiniz — "temizledim" iddiası kanıtlanamaz bir varsayımdır.

### 5. Kurtarma (Recovery)

Kurtarma, sistemleri güvenli bir şekilde üretime geri döndürmektir. Buradaki mantık kritik: geri dönüş **doğrulanmış ve izlenen** bir dönüş olmalıdır. Bir sistemi geri açtıktan sonra iş bitmez; tam tersine, saldırganın geri dönüp dönmediğini görmek için o sistemler **yoğun izleme** altında tutulur. Recovery, "eski haline döndük" değil, "temiz olduğundan emin olarak ve gözetim altında döndük" demektir.

Recovery aşamasında iş sürekliliği (business continuity) ve felaket kurtarma (disaster recovery) planlarıyla kesişme olur. Yedeklerden geri dönülüyorsa, kritik soru şudur: **yedek temiz mi?** Özellikle fidye yazılımı vakalarında saldırganlar günlerce hatta haftalarca ortamda kalıp yedekleri de şifreler veya bozar. Bu yüzden immutable (değiştirilemez) ve offline yedekler, IR açısından hayati öneme sahiptir; ve geri dönülen yedeğin, ilk ele geçirme tarihinden önceki bir noktaya ait olduğundan emin olunmalıdır.

### 6. Olay Sonrası / Çıkarılan Dersler (Post-Incident / Lessons Learned)

Bu faz en çok atlanan ama uzun vadede en değerli fazdır. Olay bittiğinde herkes yorgundur ve "bir daha bu konuya dönmeyelim" hissi hakimdir. Oysa post-mortem (olay sonrası inceleme) yapılmadan, aynı olay tekrar yaşanır.

İyi bir post-mortem'in en önemli kültürel ilkesi **suçsuz / blameless** olmasıdır. Amaç "kim hata yaptı" değil, "sürecin ve sistemin hangi zaafı bu olayı mümkün kıldı" sorusudur. Neden? Çünkü suçlayıcı bir kültürde insanlar bir sonraki olayı gizlemeye başlar; erken haber verilmeyen olay ise çok daha büyür. Blameless post-mortem, dürüst raporlamayı ödüllendirdiği için aslında güvenliği artıran bir mekanizmadır.

İyi bir post-mortem şu sorulara net cevap üretir: Tam olarak ne oldu ve zaman çizelgesi (timeline) neydi? İlk erişim vektörü tam olarak neydi? Saldırganı fark etmemiz neden bu kadar sürdü (MTTD)? Müdahale ederken hangi adım işe yaradı, hangisi zaman kaybettirdi? Hangi kontrol olsaydı bu olay olmazdı ya da erken yakalanırdı? Bu çıktılar somut, sahibi atanmış ve tarihli aksiyon maddelerine (action items) dönüşmelidir — dönüşmezse post-mortem sadece bir terapiden ibaret kalır.

## Delil Koruma ve Adli Bütünlük (Forensic Integrity)

Delil koruma, IR sürecinin tüm fazlarına yayılan bir alt disiplindir ve doğru yapılmazsa hem hukuki hem teknik açıdan felaket olur. Temel kurallar:

**Uçuculuk sırası (order of volatility):** Kanıt topланırken en uçucudan en kalıcıya doğru gidilir. RAM içeriği ve çalışan process'ler saniyeler içinde kaybolur; disk üzerindeki dosyalar çok daha kalıcıdır. Bu yüzden bir makineyi hemen kapatmak, en değerli kanıtı (bellek — çalışan zararlı, şifre çözme anahtarları, ağ bağlantıları) yok etmek anlamına gelir. Doğru sıra kabaca: bellek → çalışan bağlantılar/process'ler → geçici dosyalar → disk → arşiv/yedekler.

**İmaj alma ve write-blocking:** Bir disk üzerinde asla doğrudan çalışılmaz. Bit-bit birebir kopya (forensic image) alınır ve inceleme kopya üzerinde yapılır. Orijinale yazma olmasın diye donanımsal veya yazılımsal **write blocker** kullanılır. Neden? Çünkü orijinal delil üzerinde yapılan en küçük değişiklik bile (bir dosyayı açmak bile erişim zaman damgasını değiştirebilir) delilin mahkemede geçerliliğini yok eder.

**Hash ile bütünlük doğrulama:** İmaj alındığında kriptografik bir hash (bütünlük özeti) hesaplanır. İnceleme sonrası aynı hash tekrar hesaplanıp orijinaliyle karşılaştırılır. Hash'ler eşitse, delilin süreç boyunca değişmediği matematiksel olarak kanıtlanmış olur. Burada dikkat: adli geçerlilik için çarpışmaya (collision) dayanıklı, güncel bir hash algoritması tercih edilmelidir; eski ve kırılmış algoritmalara güvenmek delilin itiraz edilebilir hale gelmesine yol açabilir.

**Vesayet zinciri (chain of custody):** Delil, ele geçirildiği andan mahkemeye (veya nihai raporlamaya) kadar kimin elinden geçtiği, ne zaman, nerede saklandığı belgelenir. Zincirde bir kopukluk olursa — örneğin delilin bir süre kilitsiz bir masada durduğu anlar — karşı taraf "bu delile müdahale edilmiş olabilir" iddiasıyla tüm bulguyu geçersiz kılabilir. Chain of custody teknik değil, prosedürel bir kontroldür ama teknik kanıt kadar önemlidir.

## Sömürü/İstismar Mantığı ile Savunma Mantığının Karşılıklı Okunması

IR'ı gerçekten anlamak için saldırganın bakış açısını okumak gerekir; çünkü her savunma adımı, belirli bir saldırgan davranışına verilen cevaptır.

**Saldırganın istismar ettiği zaaf — görünürlük boşluğu:** Saldırganların en büyük avantajı, savunmacının kör noktalarıdır. Loglanmayan bir sistem, EDR ajanı olmayan bir sunucu, izlenmeyen bir çıkış (egress) noktası saldırgan için altın değerindedir. Saldırgan bilinçli olarak "yaşayan araçlarla saldırı" (living-off-the-land) yapar — yani sisteme özgü meşru araçları kullanır ki EDR'ler onu zararlı yazılım gibi yakalayamasın.
**Savunma cevabı:** Görünürlüğü tamamlamak (log kapsamı, EDR yaygınlığı) ve davranışsal tespit (bir yönetim aracının olağandışı bir bağlamda, olağandışı bir hesap tarafından, olağandışı bir saatte çalışması gibi anomaliler) kurmak. Yani savunma, "kötü dosya" aramaktan "kötü davranış" aramaya evrilir.

**Saldırganın istismar ettiği zaaf — yavaş ve parçalı müdahale:** Saldırgan, savunmacının koordinasyonsuzluğuna oynar. Eğer siz dayanakları tek tek kapatıyorsanız, o her kapatmada yenisini açar. Eğer siz kanıt toplarken kapsamı dar tutuyorsanız, o fark edilmeyen makinelerde bekler.
**Savunma cevabı:** Önce tam kapsam belirleme, sonra eş zamanlı eradication. Ve band dışı iletişim — çünkü saldırgan e-postanızı, Slack/Teams'inizi okuyorsa, sizin müdahale planınızı da okuyor demektir.

**Saldırganın istismar ettiği zaaf — kanıt yok etme reflexi:** İronik olarak savunmacının kendisi, panikle makineyi formatlayıp kanıtı yok ederek saldırganın işini kolaylaştırır. Kök neden bulunamayınca aynı açık açık kalır ve saldırgan geri döner.
**Savunma cevabı:** Delil koruma disiplini (uçuculuk sırası, imaj, hash, chain of custody) ve "önce koru, sonra temizle" prensibi.

**Anti-forensics — saldırganın kanıt gizlemesi:** Gelişmiş saldırganlar log silme, zaman damgası değiştirme (timestomping), bellekte çalışıp diske yazmama (fileless) gibi anti-forensic teknikler kullanır.
**Savunma cevabı:** Logları üretildikleri yerde bırakmak yerine anlık olarak merkezi ve **değiştirilemez (append-only/immutable)** bir depoya göndermek. Saldırgan ele geçirdiği makinedeki logu silse bile, merkezi kopya sağlam kalır. Bu, saldırganın en güçlü gizlenme aracını etkisiz hale getirir.

## Yaygın Hatalar

- **Kanıt tutmadan temizleme:** Belki de en pahalı hata. Makineyi formatlayınca kök neden de kaybolur; saldırgan aynı yoldan geri döner.
- **Yetersiz kapsam belirleme (scoping):** İlk görülen makineyi izole edip "bitti" demek. Saldırgan zaten yayılmıştır; yarım kalan müdahale ona sadece fark edildiğini haber verir.
- **Panikle erken izolasyon:** Tüm dayanaklar haritalanmadan yapılan izolasyon, saldırganı gizlenmeye veya sabotaja iter.
- **Band içi iletişim:** Müdahaleyi ele geçirilmiş kurumsal e-posta veya mesajlaşma üzerinden koordine etmek — saldırgana canlı yayın vermek demektir.
- **Yetersiz log saklama:** Saldırganın dwell time'ından kısa log saklama süresi. İlk erişim anını gösteren log çoktan silinmiştir.
- **Rollerin belirsizliği:** Olay anında "kim karar veriyor?" sorusunun cevabının olmaması. Olay komutanı rolünün önceden atanmamış olması müdahaleyi felç eder.
- **Yedeklerin güvenilmezliği:** Fidye yazılımı sonrası geri dönülecek yedeğin de şifrelenmiş ya da ele geçirme sonrasına ait olması. Immutable/offline yedek eksikliği.
- **Post-mortem'in atlanması veya suçlayıcı olması:** Ders çıkarılmayan olay tekrar eder; suçlayıcı kültür ise bir sonraki olayın gizlenmesine yol açar.
- **Tatbikatsız plan:** Hiç denenmemiş bir IR planı, kağıt üzerinde vardır ama olay anında çöker. Plan ancak tatbikatta test edildiği kadar gerçektir.

## En İyi Pratikler

**Olay olmadan hazırlan.** IR programının değeri sükûnet zamanında yapılan yatırımla belirlenir: rollerin atanması, runbook'ların yazılması, log/EDR görünürlüğünün sağlanması, immutable yedeklerin kurulması.

**Masaüstü tatbikatları (tabletop exercises) yap.** Ekibi bir masa etrafında toplayıp gerçekçi bir senaryoyu (ör. "muhasebe departmanından fidye notu geldi") adım adım oynatmak, planın boşluklarını kanlı bir olay yaşamadan ortaya çıkarır. Tatbikat, ucuz bir gerçek olaydır.

**Olay komutanı rolünü teknikten ayır.** Karar verme ve koordinasyon işi ile teknik analiz işi farklı kişilerde olmalı. İkisini aynı kişide toplamak her ikisini de zayıflatır.

**"Önce koru, sonra hareket et" delil prensibini kurumsallaştır.** Uçuculuk sırasına saygı, imaj alma, hash ile doğrulama ve chain of custody, hukuki süreç ihtimali olmasa bile kök nedeni doğru bulmak için gereklidir.

**Kapsamı önce belirle, sonra eş zamanlı hareket et.** Tüm dayanakları haritalamadan izolasyona veya eradication'a başlama. Kestiğinde hepsini aynı anda kes.

**Band dışı iletişim kanalı hazır tut.** Saldırganın erişemeyeceği, önceden kurulmuş bir iletişim yolu (ayrı bir mesajlaşma ortamı, hatta telefon) olay planının parçası olmalı.

**Görünürlüğü davranışa taşı.** IoC tabanlı tespitten (kırılgan ve geçici) TTP/davranış tabanlı tespide (MITRE ATT&CK ile eşleştirme) geç. Saldırgan IP'sini değiştirir ama davranış kalıbını kolay değiştiremez.

**Logları merkezi ve değiştirilemez tut.** Log'u üretildiği makinede bırakmak, saldırgana onu silme fırsatı verir. Anlık merkezi ve append-only depolama, anti-forensic tekniklerin çoğunu boşa çıkarır.

**Her olayı bir sonraki hazırlığa dönüştür.** Blameless post-mortem'den çıkan aksiyon maddelerini sahibi ve tarihiyle takip et. Döngünün son adımını ilk adıma bağlamak, IR'ı statik bir plandan öğrenen bir sisteme çevirir.

**Dış yardımı önceden ayarla.** Ciddi bir ihlalde kurum içi kapasite yetmeyebilir. DFIR danışmanlığı, hukuk ve gerekiyorsa siber sigorta ile ilişkileri olay öncesinde kurmak, olay anında değerli saatler kazandırır. Olay ortasında sözleşme müzakere etmek, en kötü zamanlamadır.

## Kapanış

Olay müdahalesi, teknik bir refleks değil, bir karar disiplinidir. NIST ve SANS döngüleri özünde aynı şeyi söyler: hazırlan, tespit et, yayılmayı durdur (containment), kökü sök (eradication), doğrulanmış şekilde geri dön (recovery) ve öğrendiklerini bir sonraki hazırlığa geri besle. Bu döngünün her adımını birbirine bağlayan iki değişmez ilke vardır: **kanıtı koru** (çünkü kök neden bilinmeden temizlik yanılsamadır) ve **panikle değil, planla hareket et** (çünkü kötü kararlar tam da olay anının stresinde üretilir). Olgun bir kurumun IR programı, olay sayısıyla değil, olayı ne kadar hızlı görüp ne kadar temiz kapattığıyla — ve her olaydan sonra ne kadar iyileştiğiyle — ölçülür.
