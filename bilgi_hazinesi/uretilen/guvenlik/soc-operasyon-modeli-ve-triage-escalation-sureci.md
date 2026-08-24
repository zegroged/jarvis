# SOC Operasyon Modeli ve Triage/Escalation Süreci

## Giriş: Neden Bu Konu Incident Response'tan Ayrı Ele Alınmalı

Incident Response (IR) literatürü genelde "bir olay onaylandıktan sonra ne yapılır" sorusuna odaklanır: containment, eradication, recovery, lessons learned. Ama bir SOC'un (Security Operations Center) gerçek hayattaki gündelik mesaisinin büyük kısmı bu noktaya hiç ulaşmaz. Bir orta ölçekli kurumda SIEM günde on binlerce, bazen yüz binlerce alarm üretebilir; bunların ezici çoğunluğu gürültüdür, bir kısmı gerçek ama önemsizdir, çok küçük bir kısmı gerçekten bir "incident" seviyesine yükseltilmeyi hak eder. IR süreci bu son küçük dilimle ilgilenir. SOC operasyon modeli ise bütün huniyle, yani alarmın doğuşundan IR'ye devredilene (ya da kapatılana) kadarki tüm karar zincirini kapsar.

Bu ayrımı anlamak savunma mühendisliği açısından kritiktir çünkü SOC'un başarısızlıkları çoğunlukla IR aşamasında değil, daha önceki triage/eskalasyon aşamasında gerçekleşir. Saldırganlar da bunu bilir: "living off the land" teknikleri, düşük-ve-yavaş (low-and-slow) hareket, gürültüye gömülme stratejileri hep triage katmanının zaaflarını hedef alır. Bir analist gerçek bir tehdidi "false positive" diye kapatırsa, en iyi IR playbook'u bile devreye giremez.

## Kök Neden: Alarm Hacmi ile İnsan Kapasitesi Arasındaki Yapısal Uyumsuzluk

SOC operasyon modelinin var olma nedeni, temelde bir kapasite problemidir. Modern bir ortamda EDR, ağ IDS/IPS, firewall, cloud audit logları, kimlik sağlayıcı (IdP) logları, DLP, e-posta güvenlik ağ geçidi gibi onlarca kaynak sürekli sinyal üretir. Bu sinyallerin çok küçük bir yüzdesi gerçek kötü niyetli aktiviteyi temsil eder; geri kalanı meşru ama şüpheli görünen davranış, yanlış yapılandırılmış kural, ya da düşük fidelity'li imza eşleşmesidir (bkz. `tespit-imzalari.md` ve `sigma-kurallari.md`).

Bu durumun kök nedeni birkaç katmanlıdır:

1. **Tespit kurallarının doğası gereği trade-off içermesi.** Bir kural ne kadar geniş (broad) yazılırsa recall (gerçek pozitifleri yakalama oranı) artar ama precision (yakalananların gerçekten kötü olma oranı) düşer. SOC'lar genelde recall'ı kaybetmemek için geniş kurallar tercih eder, bu da alarm hacmini şişirir.
2. **Ortamın karmaşıklığı arttıkça "normal" davranışın çeşitliliği de artar.** Binlerce kullanıcı, yüzlerce servis hesabı, sürekli değişen SaaS entegrasyonları — hepsi baseline'ı bulanıklaştırır.
3. **İnsan analiz kapasitesinin doğrusal ölçeklenmemesi.** Alarm sayısı 2 katına çıktığında analist sayısını 2 katına çıkarmak nadiren mümkündür (bütçe, işe alım süresi, deneyim eğrisi). Bu yapısal darboğaz, SOC'u zorunlu olarak bir "triage" (önceliklendirme) mimarisine iter: her alarmı eşit derinlikte incelemek yerine, hangi alarmların derinlemesine incelemeyi hak ettiğine hızlı karar veren bir katmanlama kurulur.

Bu yapısal gerçek, tier modelinin (Tier 1/2/3), SOAR otomasyonunun ve alarm yorgunluğu yönetiminin hepsinin kökeninde yatar. Bunları ayrı ayrı icat edilmiş "best practice"ler olarak değil, aynı kapasite probleminin farklı çözüm katmanları olarak görmek gerekir.

## Tier Modeli: İş Akışının Anatomisi

### Tier 1 — İlk Triage

Tier 1 analistler alarm kuyruğunun ön hattıdır. Görevleri derin analiz değil, **hızlı sınıflandırma**dır: Bu alarm gerçek mi (true positive) yoksa gürültü mü (false positive)? Gerçekse, ciddiyeti ne, ivedilik seviyesi ne?

Tipik Tier 1 iş akışı şu soruları sırayla cevaplar:
- Alarmı tetikleyen varlık (host, kullanıcı, IP) hangi iş bağlamında (business context) yer alıyor? (Örn. bir DevOps sunucusunda script çalıştırma normalken, bir muhasebe iş istasyonunda PowerShell encoded command şüphelidir.)
- Bu davranış kalıbı, bilinen zararsız bir örüntüyle (allowlist, bilinen yazılım, zamanlanmış bakım penceresi) örtüşüyor mu?
- Alarmın eşlik ettiği bağlam (aynı host'ta başka alarmlar, aynı kullanıcı için son 24 saatteki aktivite) tekil mi yoksa bir zincirin parçası mı?

Tier 1'in kritik başarı kriteri **hız ve tutarlılıktır**, derinlik değil. Bu seviyede genelde runbook'lar (adım adım karar ağaçları) kullanılır; analistin yorumuna bırakılan alan kasıtlı olarak dardır, çünkü tutarsızlık (aynı alarmın bir gün kapatılıp bir gün yükseltilmesi) sistemin güvenilirliğini bozar.

### Tier 2 — Derinlemesine Araştırma

Tier 1'in "muhtemelen gerçek ve önemli" diye işaretlediği alarmlar Tier 2'ye eskale edilir. Burada analiz genişler: log correlation (birden fazla kaynağın çapraz sorgulanması), timeline oluşturma, etkilenen varlıkların tam kapsamının (scope) çıkarılması, ilk erişim vektörünün hipotez edilmesi.

Tier 2, MITRE ATT&CK gibi bir çerçeveyi (bkz. `mitre-attack-kullanimi.md`) kullanarak gözlemlenen davranışı taktik/teknik seviyesinde konumlandırır — bu, hem iletişimi standartlaştırır hem de "bu tekil bir olay mı yoksa bir saldırı zincirinin bir adımı mı" sorusuna yapısal bir cevap verir. Tier 2 aynı zamanda containment kararlarını başlatabilir (host izolasyonu, hesap devre dışı bırakma) ama genelde tam IR sürecinin resmi olarak açılıp açılmayacağına karar veren eşiktir.

### Tier 3 — Uzman Müdahale ve Threat Hunting

Tier 3, en deneyimli analistleri ve genelde threat hunting, malware analizi, adli bilişim (forensics) yeteneklerini barındırır. Buraya gelen vakalar ya çok karmaşıktır (APT şüphesi, çok aşamalı saldırı, sıfırıncı gün şüphesi) ya da Tier 2'nin araçlarının/yetkisinin ötesine geçer (memory forensics, malware reverse engineering — bkz. `memory-forensics.md`, `dinamik-analiz.md`).

Tier 3 aynı zamanda **proaktif** çalışır: sadece eskale edilen alarmları beklemez, hipotez temelli threat hunting yaparak (bkz. `threat-hunting.md`) tespit kurallarının kaçırdığı boşlukları arar ve bu bulguları yeni Sigma kurallarına, yeni korelasyon mantığına dönüştürerek Tier 1/2'nin gelecekteki işini kolaylaştırır. Bu geri besleme döngüsü olmazsa SOC statik kalır ve saldırganların evrilen tekniklerine karşı geriler.

### Eskalasyon Kriterleri: Neye Göre Yükseltilir

Tier'lar arası geçiş rastgele değil, tanımlı kriterlere dayanmalıdır; aksi halde eskalasyon kararı analiste göre değişir ve tutarsızlık üretir. Tipik kriterler:

- **Varlık kritikliği**: Domain controller, ödeme sistemi, yönetici hesabı gibi yüksek değerli varlıklar düşük confidence'lı alarmda bile daha hızlı eskale edilir.
- **Confidence skoru**: Tespit kuralının kendi güven seviyesi (bazı SIEM/SOAR platformları kural bazında bir "severity x confidence" matrisi tutar).
- **Correlation yoğunluğu**: Aynı varlıkta/kullanıcıda kısa sürede birden fazla farklı alarmın tetiklenmesi (örn. başarısız kimlik doğrulama + coğrafi anomali + yeni cihaz kaydı), tekil alarmlardan çok daha güçlü bir sinyaldir ve otomatik olarak eskalasyonu tetikleyebilir.
- **Zaman baskısı**: Ransomware öncüsü davranışlar (toplu dosya yeniden adlandırma, gölge kopya silme, EDR devre dışı bırakma girişimi) SLA'yı atlayıp doğrudan en üst tier'a / IR'ye gider.

## SOAR ve Playbook Otomasyonu: Çalışma Mantığı

SOAR (Security Orchestration, Automation and Response), tier modelinin kapasite darboğazını azaltmak için var olan katmandır. Temel fikir: Tier 1'in yaptığı tekrarlayan, kural tabanlı, "eğer-o zaman" mantığına indirgenebilir işlerin bir kısmını yazılıma devretmek.

### Kavramsal Çalışma Mantığı

Bir SOAR playbook'u genelde şu yapıdadır:
1. **Tetikleyici (trigger)**: SIEM'den gelen belirli bir alarm tipi veya korelasyon kuralı.
2. **Zenginleştirme (enrichment)**: Otomatik olarak ek bağlam toplama — IP itibar sorgusu (threat intel feed), kullanıcının son giriş geçmişi, dosya hash'inin sandbox/VirusTotal benzeri bir kaynakta sorgulanması, ilgili varlığın varlık envanterindeki kritiklik etiketi.
3. **Karar mantığı**: Toplanan zenginleştirme verisine göre otomatik bir dallanma — "IP bilinen kötü niyetli listede VE hedef kritik sistemse → otomatik izolasyon" gibi.
4. **Eylem (response)**: Otomatik containment (host izolasyonu, hesap kilitleme, e-posta karantinaya alma), ticket açma, analiste bildirim, ya da sadece bağlamı zenginleştirilmiş halde insan onayına sunma.

Kritik nokta: SOAR'ın değeri "otomatik saldırıya karşılık verme" değil, **analistin tekrar tekrar elle yaptığı zenginleştirme ve ilk müdahale adımlarını hızlandırmaktır**. Tam otomatik, insan onayı olmadan yıkıcı aksiyon alan (host'u kapatma, hesabı silme) playbook'lar yüksek risklidir çünkü yanlış pozitif durumunda iş sürekliliğine zarar verebilir; bu yüzden olgun SOC'lar genelde "otomatik zenginleştirme + insan onaylı aksiyon" modelini tercih eder, tam otonom aksiyonu yalnızca çok yüksek confidence senaryolarında (örn. bilinen ransomware imzası) kullanır.

### Tespit ve Savunma Açısından SOAR'ın Rolü

Savunmacı gözüyle SOAR'ın asıl kazanımı **MTTD ve MTTR'ı düşürmesidir** (aşağıda tanımlanıyor), çünkü:
- Zenginleştirme adımı insan tarafından yapıldığında dakikalar sürerken otomasyonla saniyeler sürer.
- Tutarlılık artar: her alarm için aynı zenginleştirme adımları aynı sırayla uygulanır, bu da analiste bağlı hataları azaltır.
- Playbook'lar kendisi bir tespit varlığı gibi versiyonlanabilir, test edilebilir ve denetlenebilir hale gelir (bkz. `secure-sdlc.md` prensipleri playbook geliştirmeye de uygulanabilir).

Ama SOAR'ın kendisi de bir saldırı yüzeyidir: playbook'un mantığı öngörülebilirse (örn. saldırgan "bu davranış otomatik olarak sadece bildirim üretir, aksiyon almaz" bilgisine sahipse), saldırgan playbook'un boşluklarını hedefleyebilir. Ayrıca SOAR'ın kendi kimlik bilgileri (API anahtarları, EDR/IdP'ye entegrasyon token'ları) ele geçirilirse, saldırgan meşru "response" mekanizmasını kötüye kullanarak (örn. gerçek incident'ları kapatarak, log'ları sildirerek) SOC'un görüşünü kör edebilir — bu yüzden SOAR platformunun kendisi de en az SIEM kadar sıkı erişim kontrolü ve loglama gerektirir.

## Alarm Yorgunluğu (Alert Fatigue): Kök Neden ve Yönetim

### Neden Oluşur

Alert fatigue, bir analistin sürekli yüksek hacimli, çoğunlukla düşük değerli alarmlara maruz kalması sonucu dikkatinin ve karar kalitesinin sistematik olarak düşmesidir. Bu psikolojik bir olgudur (dikkat kaynaklarının tükenmesi, "cry wolf" etkisi) ama kök nedeni teknik bir tasarım hatasıdır: **tespit kurallarının precision/recall dengesinin yanlış kalibre edilmesi ve kural kütüphanesinin zaman içinde temizlenmemesi**.

Somut mekanizma şöyle işler: Yeni bir tespit kuralı yazılır, test ortamında iyi çalışır, prod'a alınır. Zamanla ortam değişir (yeni bir yazılım devreye girer, bir iş süreci normal hale gelir) ama kural güncellenmez. Kural artık sürekli false positive üretir. Analist bu kuralı defalarca "zararsız" olarak kapatır, bu davranış zamanla otomatikleşir (öğrenilmiş körlük) — ve bir gün aynı kural gerçek bir saldırıyı yakaladığında, analist onu da reflekssel olarak kapatır. Bu, tarihsel olarak büyük ihlallerde tekrar eden bir başarısızlık örüntüsüdür: tespit sistemi doğru alarmı üretmiştir ama insan katmanı onu gürültüye gömmüştür.

### Yönetim ve Savunma Stratejileri

1. **Kural yaşam döngüsü yönetimi**: Her tespit kuralının bir sahibi, bir false-positive-rate metriği ve periyodik gözden geçirme takvimi olmalı. Sürekli yüksek FP oranı üreten kurallar ya iyileştirilmeli (daha spesifik koşullar, ek bağlam filtreleri) ya da devre dışı bırakılmalı.
2. **Risk bazlı skorlama (risk-based alerting)**: Tekil kural eşleşmesi yerine, birden fazla düşük-confidence sinyalin birikerek bir risk skoru oluşturduğu modeller (UEBA — User and Entity Behavior Analytics mantığına yakın) analistin dikkatini gerçekten anormal olan birikimlere yönlendirir, tekil gürültülü olaylara değil.
3. **Alarm gruplama / correlation**: Aynı kök nedenden doğan onlarca alarmı tek bir "case"e toplamak (örneğin bir phishing kampanyasının 200 kullanıcıya ulaşması 200 ayrı alarm değil, 1 case olmalı) analistin kognitif yükünü doğrudan azaltır.
4. **Otomatik triage önceliklendirmesi**: SOAR'ın zenginleştirme çıktısına göre kuyruğu otomatik sıralaması (en yüksek risk skoru en üstte), analistin "sırayla" değil "önem sırasıyla" çalışmasını sağlar.
5. **Rotasyon ve iş yükü yönetimi**: Operasyonel/insani boyut — sürekli aynı düşük değerli kuyrukta çalışmak yerine analistlerin threat hunting, kural geliştirme gibi daha yüksek katma değerli işlerle rotasyona sokulması, tükenmeyi azaltır ve dolaylı olarak tespit kalitesini artırır (yorgun analist hata yapar).

Bu yönetim pratiklerinin hepsinin ortak paydası şudur: alarm yorgunluğu bir "disiplin" veya "dikkat" sorunu değil, bir **sinyal-gürültü mühendisliği** sorunudur. Çözüm insanı daha dikkatli olmaya zorlamak değil, sistemin ürettiği sinyalin kalitesini yükseltmektir.

## Metrikler: MTTD ve MTTR

SOC operasyonel olgunluğunun ölçülmesinde iki temel metrik öne çıkar:

- **MTTD (Mean Time to Detect)**: Bir kötü niyetli aktivitenin başlangıcından, SOC'un onu bir alarm/sinyal olarak fark etmesine kadar geçen ortalama süre. Yüksek MTTD, ya tespit kapsamında (coverage) boşluk olduğunu ya da mevcut sinyalin gürültüye gömüldüğünü (alert fatigue'in dolaylı sonucu) gösterir.
- **MTTR (Mean Time to Respond/Resolve)**: Tespitten, olayın etkisiz hale getirilmesine (containment/eradication) kadar geçen ortalama süre. Yüksek MTTR genelde triage/eskalasyon sürecinde darboğaz olduğuna, ya da containment yetkisinin/araçlarının (örn. otomatik izolasyon yeteneği olmaması) yetersiz olduğuna işaret eder.

Bu iki metrik doğrudan tier modeli ve SOAR yatırımının etkinliğini yansıtır: iyi kalibre edilmiş bir triage süreci ve etkili otomasyon MTTD'yi düşürürken (sinyal daha hızlı doğru kişiye ulaşır), iyi tanımlanmış eskalasyon kriterleri ve otomatik ilk-müdahale playbook'ları MTTR'ı düşürür. Bu metriklerin izole değil, birlikte trend halinde takip edilmesi önemlidir çünkü biri diğerinin pahasına iyileştirilebilir (örn. her şeyi otomatik kapatarak MTTR düşürülebilir ama bu, gerçek incident'ların erken kapatılıp gözden kaçmasına, dolayısıyla dolaylı olarak gerçek zararın gecikmeli fark edilmesine yol açabilir).

Metriklerin kullanımında dikkat edilmesi gereken bir tuzak: bu sayılar hedefe (KPI) dönüştüğünde, analistler sayıyı iyileştirmek için vakaları yüzeysel kapatmaya (gaming the metric) yönelebilir. Bu yüzden MTTD/MTTR her zaman kalite metrikleriyle (yeniden açılan vaka oranı, kaçırılan tespit sonradan fark edilen olay sayısı) birlikte okunmalıdır.

## Yaygın Hatalar

1. **Runbook'suz Tier 1 kurmak**: Deneyimsiz analistlere net karar kriterleri vermeden "şüpheli görünüyorsa eskale et" demek, tutarsız ve öngörülemez triage üretir.
2. **Eskalasyon kriterlerini dokümante etmemek**: Tier'lar arası geçiş analistin sezgisine bırakıldığında, kritik vakalar gecikir ya da önemsiz vakalar gereksiz yere üst katmanı meşgul eder.
3. **SOAR'ı "kur-unut" (set and forget) olarak görmek**: Ortam değiştikçe playbook'lar da güncellenmeli; eski playbook, artık geçerli olmayan bir varsayıma (örn. eski bir EDR API'si) dayanarak sessizce başarısız olabilir.
4. **Tam otomatik yıkıcı aksiyonu erken ölçekte devreye almak**: Yüksek yanlış pozitif riski taşıyan bir ortamda otomatik host izolasyonu, iş sürekliliğinde ciddi yan etkiler (üretim sunucusunun yanlışlıkla izole edilmesi) yaratabilir.
5. **Kural kütüphanesini hiç budamamak**: Zamanla artan, hiç temizlenmeyen kural seti hem performans sorunlarına hem alert fatigue'e yol açar.
6. **Tier 3/threat hunting bulgularını geri beslememek**: Threat hunting sonuçları yeni kurallara dönüştürülmezse, aynı boşluk tekrar tekrar manuel olarak keşfedilir; SOC öğrenmez, sadece tekrar eder.
7. **Metrikleri tek başına hedef haline getirmek**: Yalnızca MTTD/MTTR'a odaklanıp vaka kalitesini (doğru scope belirleme, kök neden analizi) göz ardı etmek, hızlı ama yüzeysel bir SOC üretir.

## Sonuç

SOC operasyon modeli, temelde bir ölçeklenebilirlik mühendisliğidir: sınırlı insan dikkatini, sınırsız görünen alarm hacmine karşı en verimli şekilde dağıtma problemi. Tier modeli bu dağıtımı hiyerarşik uzmanlık katmanlarıyla çözer, SOAR tekrarlayan bilişsel yükü otomasyona devrederek insan kapasitesini çoğaltır, alarm yorgunluğu yönetimi ise sinyal kalitesini sürekli iyileştirerek insanın dikkatini gerçekten önemli olana yönlendirir. Bu üç bileşen ayrı ayrı değil, birbirini besleyen tek bir sistem olarak tasarlandığında, IR sürecine ulaşan vakaların hem daha az sayıda hem de daha yüksek doğrulukta olması sağlanır — ki bu da nihayetinde IR'nin kendisinin etkinliğini belirleyen ön koşuldur.
