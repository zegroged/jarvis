# Insider Threat Tespiti ve Kullanıcı Davranış Analitiği (UEBA, DLP, Ayrıcalıklı Kullanıcı İzleme, Anomali Skorlama)

## Tanım ve Kapsam

**Insider threat** (iç tehdit), bir kuruma ait meşru erişim yetkisine sahip bir kişinin — çalışan, yüklenici (contractor), iş ortağı veya servis hesabı sahibi — bu erişimi kurumun güvenliğine, verisine veya operasyonlarına zarar verecek şekilde kullanması riskidir. Dıştan gelen bir saldırganın aksine, iç tehdit aktörü zaten kapının içindedir: geçerli kimlik bilgileriyle oturum açar, kendisine tanımlı kaynaklara erişir ve çoğu zaman hiçbir "exploit" veya zafiyet kullanmaz. Bu, iç tehdidi geleneksel dış tehdit tespitinden temelde ayıran noktadır.

İç tehditler genellikle üç kategoride ele alınır:

- **Kötü niyetli iç tehdit (malicious insider):** Bilinçli olarak veri sızdıran, sabotaj yapan veya dolandırıcılık gerçekleştiren kişi. Örnek: işten ayrılmadan önce müşteri listesini kopyalayan satış temsilcisi.
- **İhmalkâr/dikkatsiz iç tehdit (negligent insider):** Kötü niyeti olmayan ama politika ihlaliyle veya dikkatsizlikle risk yaratan kişi. Örnek: hassas dosyaları kişisel bulut hesabına yükleyip iş kolaylığı sağlamaya çalışan çalışan.
- **Ele geçirilmiş iç tehdit (compromised insider):** Kimlik bilgileri çalınmış ve dış saldırgan tarafından kullanılan meşru hesap. Teknik olarak dıştan gelir ama davranışsal tespit açısından iç tehdit gibi görünür.

Bu üçüncü kategori, **insider threat programı** ile **ITDR (Identity Threat Detection and Response)** disiplinlerinin neden örtüştüğünü açıklar: ele geçirilmiş bir hesap, hem kimlik odaklı tespitin hem de davranış analitiğinin ilgi alanındadır.

### Neden EDR/davranışsal tespitten ayrı bir disiplin?

EDR (Endpoint Detection and Response) ve davranışsal malware tespiti, esas olarak **kötü amaçlı kodun** yürütülmesine, process injection'a, şüpheli parent-child process zincirlerine, C2 (command-and-control) trafiğine odaklanır. Bu telemetri, dış saldırgan/malware tespiti için mükemmeldir ama iç tehdit için büyük ölçüde kördür: bir çalışanın 5.000 dosyayı meşru bir uygulama (Explorer, tarayıcı, `robocopy`) ile kopyalaması hiçbir malware imzası tetiklemez, hiçbir enjeksiyon içermez.

İç tehdit tespiti farklı **veri kaynakları** ve farklı bir **taban çizgisi (baseline)** gerektirir:

- **DLP (Data Loss Prevention)** olayları — veri hareketi ve içerik sınıflandırması,
- **Dosya erişim/audit logları** — kim, hangi dosyaya, ne zaman, ne kadar erişti,
- **Kimlik/erişim logları** — oturum açma, ayrıcalık kullanımı, yetki değişiklikleri,
- **HR/insan kaynakları bağlamı** — işten çıkış süreci, performans uyarıları, rol değişiklikleri,
- **E-posta/işbirliği/bulut** telemetrisi — dışa gönderilen ekler, paylaşım linkleri.

Bu ayrım, kurumsal DFIR (Digital Forensics and Incident Response) programlarında iç tehdidin neden ayrı bir program (Insider Threat Program / InTP), ayrı bir veri modeli ve çoğu zaman ayrı bir yönetişim/hukuk/İK katmanıyla yürütüldüğünü açıklar.

## Kök Mantık: Neden Davranış Analitiği?

İç tehdidin merkezî sorunu şudur: **"yetkili erişim" ile "kötüye kullanım" arasında imza düzeyinde bir fark yoktur.** Aynı eylem (dosya indirme, veritabanı sorgusu, ayrıcalık kullanımı) hem meşru hem kötü niyetli olabilir. Ayrımı yapan şey, eylemin **bağlamı ve normalden sapmasıdır**. Bu yüzden statik kural yerine **davranışsal taban çizgisi** kurulur.

### UEBA (User and Entity Behavior Analytics) çalışma mantığı

UEBA, her **kullanıcı** ve **varlık** (entity — sunucu, servis hesabı, uç nokta, uygulama) için "normal" davranışın istatistiksel bir profilini öğrenir, ardından bu profilden **anlamlı sapmaları** skorlar. Temel bileşenler:

1. **Baselining (taban çizgisi öğrenme):** Genellikle 2–8 haftalık bir öğrenme penceresinde, her varlık için normal davranış dağılımı çıkarılır. "Normal" hem bireysel (Ahmet genelde 09:00–18:00 arası, İstanbul IP'sinden, muhasebe paylaşımına erişir) hem de akran-grubu (peer group) düzeyinde (muhasebe ekibinin tipik davranışı) tanımlanır.

2. **Peer group analizi:** Bir kullanıcının davranışı, izole değil, benzer rol/departmandaki akranlarına göre değerlendirilir. Ahmet tek başına 500 dosya indirdiğinde bu tuhaf; ama tüm ekip ay sonu raporlaması için yoğun indirme yapıyorsa, akran grubu normali kayar ve yanlış pozitif önlenir. Bu, UEBA'nın statik eşiklere göre en büyük üstünlüğüdür.

3. **Özellik çıkarımı (feature engineering):** Ham loglardan davranışsal özellikler türetilir — oturum saati, erişilen veri hacmi, benzersiz kaynak sayısı, coğrafi konum, cihaz, ayrıcalık yükseltme olayları, başarısız erişim denemeleri, ilk-kez-görülen (first-seen) erişimler.

4. **Anomali skorlama:** Sapmalar tek tek değil, **birikimli bir risk skoru** olarak toplanır. Tek bir anomali (geç saatte oturum) düşük skorlu; ama aynı gün içinde geç oturum + ilk kez erişilen hassas paylaşım + yüksek hacimli dışa aktarım + USB kullanımı üst üste geldiğinde skor eşiği aşar. Buna **risk-based / kill-chain temelli birikim** denir.

### Anomali skorlama teknikleri

Skorlama tipik olarak birkaç yaklaşımın karışımıdır:

- **İstatistiksel sapma:** Z-skoru, yüzdelik dilim, MAD (median absolute deviation). "Bu kullanıcının bugünkü indirme hacmi, kendi 30 günlük ortalamasının kaç standart sapma üstünde?"
- **Denetimsiz ML (unsupervised):** Isolation Forest, clustering (DBSCAN), autoencoder rekonstrüksiyon hatası gibi yöntemlerle etiketsiz veride aykırı davranış tespiti. İç tehditte etiketli veri neredeyse hiç yoktur (olaylar nadirdir), bu yüzden denetimsiz yaklaşım baskındır.
- **Kural + istatistik hibriti:** Saf ML'in açıklanabilirliği zayıf olduğundan, olgun programlar ML skorunu insan-okunur kurallarla (örn. "işten çıkış bildirimi + hassas veri erişimi") harmanlar. Açıklanabilirlik, hukuki/İK süreçte kritiktir.

Önemli bir kavram: **anomali ≠ tehdit.** Anomali sadece "normalden farklı" demektir; kötü niyet ima etmez. UEBA çıktısı bir **triage sinyali** üretir, kesin karar değil. Bu ayrımı unutmak, iç tehdit programlarının en yaygın çöküş nedenidir.

## Veri Kaynakları ve Taban Çizgisi Detayı

İç tehdit tespitinin kalitesi, doğrudan telemetrinin genişliğine bağlıdır. Kör noktalar burada oluşur.

### DLP (Data Loss Prevention)

DLP, verinin **içeriğine ve hareketine** odaklanır. İki ana boyut:

- **Data-in-motion:** E-posta ekleri, web yüklemeleri, bulut senkronizasyonu, mesajlaşma. DLP, içerik denetimiyle (regex, fingerprinting, exact/partial data match, sınıflandırma etiketleri) hassas verinin dışarı çıkışını tespit veya bloke eder.
- **Data-at-rest / data-in-use:** Endpoint DLP, USB'ye kopyalama, yazdırma, panoya (clipboard) alma, ekran görüntüsü, kişisel buluta yükleme gibi eylemleri yakalar.

DLP tek başına yüksek yanlış-pozitif üretir çünkü niyetten habersizdir. Gücü, UEBA ile birleştiğinde ortaya çıkar: "hassas etiketli veri" + "kişisel e-postaya" + "işten çıkış sürecindeki kullanıcı" birleşince zayıf sinyaller güçlü bir olaya dönüşür.

### Dosya erişim ve audit logları

Windows tarafında dosya/paylaşım erişimi için **object access auditing** (Event ID 4663 — nesneye erişim denemesi, 4656 — handle isteği, 5140/5145 — ağ paylaşımı erişimi) kullanılır. Bunlar varsayılan kapalıdır ve **SACL (System Access Control List)** ile hedef klasörlerde açıkça etkinleştirilmelidir; aksi halde iç tehdit için en değerli veri hiç üretilmez. Linux tarafında `auditd` ile dosya izleme (watch rules) benzer görevi görür. Not: Bu Event ID'lerin tam anlamı sürüme göre nüans gösterebilir; tasarımda resmi Microsoft/dağıtım dokümantasyonuyla doğrulayın.

Bu loglardan türetilen kritik davranışsal metrikler: **erişim hacmi** (kısa sürede çok sayıda dosya = potansiyel toplu kopyalama/staging), **benzersiz kaynak genişliği** (normalde 3 klasöre erişen kullanıcı 40 klasör taradığında = keşif/collection), **first-seen erişim** (hiç dokunmadığı bir hassas depoya ilk erişim).

### Ayrıcalıklı kullanıcı (privileged user) izleme

Ayrıcalıklı hesaplar (domain admin, root, DBA, bulut admin, servis hesapları) en yüksek riski taşır çünkü tek bir kötüye kullanım maksimum etkiye sahiptir ve bu hesaplar sıklıkla **denetim kör noktasıdır** — "admin zaten her şeyi yapabilir" varsayımı yüzünden. İzleme unsurları:

- **PAM (Privileged Access Management) entegrasyonu:** Ayrıcalıklı oturumların vault üzerinden geçmesi, oturum kaydı (session recording), just-in-time (JIT) yetkilendirme. Kalıcı admin yetkisi yerine talep-üzerine, süreli yetki, saldırı yüzeyini ve izleme yükünü daraltır.
- **Ayrıcalık kullanımı korelasyonu:** Yetki yükseltme, yeni admin grubu üyeliği, güvenlik logu temizleme (Windows Event ID 1102 — audit log temizlendi), yeni servis/görev oluşturma gibi olayların ayrıcalıklı kullanıcı bağlamında ayrıca skorlanması.
- **Servis hesapları için katı baseline:** İnsan olmayan kimlikler (non-human identities) davranışça çok düzenlidir (aynı kaynaklar, aynı saatler, aynı IP). Bir servis hesabının aniden interaktif oturum açması veya yeni bir hedefe bağlanması, insandan çok daha güçlü bir anomali sinyalidir — çünkü meşru varyans neredeyse sıfırdır.

### HR/insan kaynakları bağlamı

İç tehdidin en güçlü tek belirleyicisi çoğu zaman **davranışsal değil bağlamsaldır:** işten ayrılık bildirimi (resignation), performans düşük değerlendirmesi (PIP), erişim düşürme, disiplin süreci. **"Leaver" (ayrılan çalışan)** penceresi — istifa bildirimi ile son gün arası — veri sızıntısı için en yüksek riskli dönemdir. Olgun programlar, İK olayını tetikleyici olarak alıp o kullanıcının izleme hassasiyetini geçici olarak yükseltir (heightened monitoring). Bu entegrasyon aynı zamanda ciddi gizlilik ve hukuk yükümlülüğü doğurur (aşağıya bakınız).

## Örnek Senaryo: Ayrılan Satış Temsilcisi

Somut bir vaka, sinyallerin nasıl birikerek olaya dönüştüğünü gösterir:

Bir satış temsilcisi Cuma günü istifa eder (İK olayı → risk skoru tabanı yükselir). Takip eden hafta:

1. **Salı 22:40** — normalde mesai içi çalışan kullanıcı, geç saatte VPN ile oturum açar (zamansal anomali, düşük skor).
2. Aynı oturumda daha önce **hiç erişmediği** "Tüm Müşteri Kontratları" paylaşımına erişir (first-seen + hassas kaynak, orta skor).
3. **1.200 dosyayı** 15 dakikada indirir — kendi 30 günlük ortalamasının ~40 standart sapma üstü (hacim anomalisi, yüksek skor).
4. Endpoint DLP, aynı içeriğin **kişisel Gmail** hesabına yüklendiğini ve bir **USB** belleğe kopyalandığını raporlar (exfiltration kanalı, yüksek skor).

Tek tek her sinyal göz ardı edilebilir; ama İK bağlamıyla birikimli skor kısa sürede kritik eşiği aşar ve **yüksek öncelikli bir vaka** üretir. UEBA'nın değeri tam olarak bu **zayıf sinyalleri kronolojik/bağlamsal olarak birleştirme** yeteneğidir — hiçbiri tek başına imza tetiklemezdi.

## Tespit ve Savunma

### Tespit tarafı

- **Telemetriyi önce kur:** Object access auditing (SACL), DLP, kimlik logları, bulut audit (örn. CloudTrail benzeri), e-posta gateway logları merkezî bir SIEM/data lake'e akmalı. Ham veri yoksa hiçbir analitik iş görmez.
- **Katmanlı korelasyon:** Tek olay yerine **kill-chain / birikimli risk** modeli kur: keşif (unusual browsing) → erişim (first-seen sensitive) → toplama (staging/yüksek hacim) → dışa aktarım (exfil kanalı). Bu zincirin bir arada görülmesi, tekil anomaliden çok daha yüksek kesinlik taşır.
- **Peer group ve zamansal baseline kullan:** Statik eşik (örn. "günde 100 dosyadan fazla = alarm") kaçınılmaz olarak ya çok gürültülü ya çok kör olur. Dinamik, akrana ve kişinin kendi geçmişine göre normalleştirilmiş eşik kullan.
- **Exfiltration kanallarını çok noktadan izle:** E-posta (kişisel adrese ek), web upload, bulut sync (kişisel OneDrive/Drive), USB, yazdırma, panoya kopyalama, DNS tünelleme/steganografi gibi kaçamak kanallar. Sadece bir kanalı izlemek, diğerlerine kaymayı davet eder.
- **First-seen ve nadir olay analitiği:** "Bu kullanıcının/varlığın ilk kez yaptığı X" tespiti, ML'siz bile güçlü ve açıklanabilir bir sinyaldir.

### Savunma/önleme tarafı (tespit tek başına yeterli değil)

Tespit reaktiftir; olgun bir program **önleyici kontrolleri** öne alır:

- **Least privilege ve veri sınıflandırması:** Kullanıcı erişemediği veriyi sızdıramaz. Düzenli erişim gözden geçirmesi (access recertification), aşırı yetkileri (privilege creep) budar. Veriyi sınıflandırmadan DLP'yi etkin kuramazsınız.
- **Just-in-time / PAM:** Kalıcı ayrıcalık yerine süreli, onaylı, kaydedilen ayrıcalık. Ayrıcalıklı oturum yüzeyini daraltır.
- **DLP blocking modu (dikkatli):** Yüksek güvenli sınıflandırılmış veri için gerçek engelleme; ama önce uzun bir **monitor-only** aşamasıyla yanlış-pozitifleri kalibre et, aksi halde iş sürekliliği kırılır ve kullanıcılar "shadow IT" ile etrafından dolaşır.
- **Segmentasyon ve staging engelleme:** Toplu veri toplamayı zorlaştıran mimari (paylaşım erişim kotaları, DRM/IRM ile dosyaların dışarıda açılamaması).
- **Leaver süreci sıkılaştırma:** İstifa anında yükseltilmiş izleme + erişim daraltma + çıkış görüşmesi + varlık teslim kontrolü.

## Yaygın Hatalar

- **Anomaliyi tehdit sanmak:** UEBA çıktısını otomatik "olay" gibi işlemek. Anomali bir hipotezdir; her yükseklik skoru bir insan triyajı gerektirir. Bunu atlamak, analistleri gürültüde boğar (alert fatigue) ve programı çöpe atar.
- **Baseline'i statik zannetmek:** Rol değişikliği, reorganizasyon, proje döngüleri normali kaydırır. Baseline sürekli güncellenmezse ya yalancı alarm patlaması ya körlük oluşur. Öğrenme penceresi yaşayan bir mekanizma olmalı.
- **Sadece kötü niyetliye odaklanmak:** Vakaların büyük kısmı **ihmalkâr** iç tehdittir (yanlış paylaşım, kişisel buluta yükleme). Bunları "saldırgan" muamelesiyle işlemek hem yanlış tepki üretir hem programı düşmanlaştırır; farklı müdahale (eğitim, uyarı) gerekir.
- **Telemetriyi kurmadan analitik satın almak:** Pahalı UEBA ürünü, altında object access log, DLP ve İK entegrasyonu yoksa boş çalışır. "Garbage in, garbage out."
- **Ayrıcalıklı hesapları kör nokta bırakmak:** En büyük risk taşıyan hesapları "onlar zaten yetkili" diye izlememek. Servis hesaplarının düşük varyansı, tam tersine, onları en verimli izleme hedefi yapar.
- **Gizlilik/hukuk boyutunu atlamak:** İç tehdit programı, çalışanları izler. Bu; İK, hukuk, veri koruma (KVKK/GDPR — amaç sınırlaması, orantılılık, çalışan bilgilendirmesi, işçi temsilcisi onayı) ve etik gözetim gerektirir. Yetkisiz veya orantısız izleme hem yasal yaptırım hem güven kaybı doğurur. Teknik program, yönetişim çerçevesi olmadan kurulmamalıdır.
- **Tespiti önlemenin yerine koymak:** Sadece sızıntıyı "görmek" veriyi geri getirmez. En etkili kontrol, erişimi baştan sınırlamak ve kanalları kapatmaktır.

## Özet

İç tehdit tespiti, dış tehdit/EDR disiplininden ayrı durur çünkü tehdit **meşru erişimin kötüye kullanımıdır** — imza değil, bağlamdan-sapma tespiti gerektirir. UEBA, kullanıcı ve varlıklar için dinamik, akran-duyarlı bir taban çizgisi kurar ve zayıf anomalileri birikimli risk skoruna dönüştürür. Başarı; DLP, dosya audit logları, kimlik/ayrıcalık telemetrisi ve İK bağlamının birlikte akmasına, anomalinin tehditten ayrı tutulmasına, önleyici kontrollerin (least privilege, PAM, sınıflandırma) tespitin önüne konmasına ve tüm bunların sağlam bir gizlilik/hukuk yönetişimi altında yürütülmesine bağlıdır.
