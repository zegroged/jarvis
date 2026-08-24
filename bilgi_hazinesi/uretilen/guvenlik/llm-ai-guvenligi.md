# LLM/AI Güvenliği: OWASP Top 10 for LLM, Prompt Injection, Jailbreak, RAG Zehirleme, Model/Veri Zehirleme, Agentic AI Güvenliği

## Neden bu konu ayrı bir güvenlik disiplini haline geldi

Geleneksel uygulama güvenliği, girdi ile kod arasında net bir sınır varsayımına dayanır: SQL sorgusu ile kullanıcı girdisi ayrıdır, bu yüzden parametrize sorgular ile ayrıştırılabilir. Büyük dil modellerinde (LLM) bu sınır yoktur. Bir LLM'e "sistem talimatı" ile "kullanıcı girdisi" ve "araçtan/RAG'dan gelen dış veri" hepsi aynı kanaldan, doğal dil olarak, tek bir token dizisi içinde girer. Model, bu metnin hangi kısmının "komut" hangi kısmının "veri" olduğunu yapısal olarak değil, istatistiksel olarak (eğitim sırasında öğrendiği örüntülerle) ayırt etmeye çalışır. Bu, **kök neden**dir: LLM mimarisinde talimat kanalı ile veri kanalı ayrık değildir (no privilege separation between instruction and data channel). SQL injection'da "kod/veri karışımı" bir programlama hatasıydı; LLM'de bu, mevcut transformer mimarisinin doğasında olan bir özelliktir. Bu yüzden "tamamen çözülmüş" bir savunma yoktur; sadece risk azaltma katmanları vardır.

İkinci kök neden: LLM'ler **non-deterministik ve olasılıksaldır**. Aynı savunma promptu bazen işe yarar, bazen yaratıcı bir yeniden ifade (rephrasing) ile atlatılır. Bu, güvenliği "kural tabanlı filtre" yerine "olasılıksal risk yönetimi" haline getirir.

Üçüncü kök neden: Modern sistemler artık sadece metin üreten pasif bir kutu değil, **araç çağırabilen (tool-calling), dosya okuyabilen, kod çalıştırabilen, e-posta gönderebilen ajanlardır (agentic AI)**. Bu, saldırı yüzeyini "yanlış metin üretme" riskinden "gerçek dünyada eylem gerçekleştirme" riskine taşır. Bir jailbreak artık sadece utandırıcı bir çıktı değil, gerçek bir veri sızıntısı veya yetkisiz işlem anlamına gelebilir.

2024-2026 döneminde bu konunun hızla büyümesinin nedeni budur: kurumlar LLM'leri müşteri destek botlarından kod asistanlarına, RAG tabanlı iç bilgi sistemlerinden otonom ajanlara kadar hızla üretime soktu, ancak bu sistemlerin güvenlik modeli geleneksel web uygulamalarınınkinden temelde farklı ve olgunlaşmamış durumda.

## OWASP Top 10 for LLM Applications: genel çerçeve

OWASP'ın LLM uygulamaları için yayınladığı liste, klasik OWASP Top 10'un (web uygulamaları) LLM'e uyarlanmış halidir ve zamanla güncellenmektedir. Kesin madde numaralarını ve sürüm tarihini burada iddialı biçimde vermek yerine, kavramsal kategorileri anlatacağım (liste yıllar içinde revize edildi, tam güncel sıralama için OWASP'ın kendi güncel yayınına bakılmalı):

- **Prompt Injection**: Modelin talimatlarını, istenmeyen bir davranış üretecek şekilde manipüle eden girdiler.
- **Insecure Output Handling / Hassas Çıktı İşleme**: Modelin ürettiği çıktının, doğrulanmadan aşağı akışta (downstream) bir yorumlayıcıya (shell, SQL, HTML/DOM, başka bir sistem) güvenilir gibi verilmesi.
- **Training Data Poisoning / Eğitim Verisi Zehirleme**: Modelin eğitim veya fine-tuning verisine kötü niyetli örnekler ekleyerek davranışını kalıcı olarak bozmak.
Bunlara ek olarak: aşırı ajan yetkisi (Excessive Agency), hassas bilgi ifşası (Sensitive Information Disclosure), tedarik zinciri riskleri (Model Supply Chain), sistem promptu sızdırma (System Prompt Leakage), vektör/embedding zehirlenmesi (Vector and Embedding Weaknesses — RAG'e özgü), yanlış bilgi/halüsinasyon (Misinformation), kaynak tüketimi (Unbounded Consumption / Denial of Wallet-Service).

Bu kategoriler birbirinden bağımsız değildir; çoğu zincirleme çalışır: bir prompt injection, aşırı ajan yetkisiyle birleşince gerçek bir veri sızıntısına dönüşür.

## Prompt Injection: doğrudan (direct) ve dolaylı (indirect)

### Tanım ve çalışma mantığı

Prompt injection, modelin "talimat" olarak yorumlaması istenmeyen bir metnin, sistem tasarımcısının niyetini geçersiz kılacak şekilde modele sunulmasıdır. İki ana tür vardır:

**Doğrudan prompt injection**: Saldırgan, kullanıcı girdisi alanına doğrudan "önceki talimatları yok say" türü ifadeler yazar. Bu en basit ve en çok bilinen formdur; korunması da (göreceli olarak) en kolay olandır çünkü girdi kaynağı bellidir ve şüphe duyulabilir.

**Dolaylı prompt injection (indirect)**: Asıl tehlikeli ve tespiti zor olan budur. Saldırgan, modelin kullanıcıyla değil, modelin *okuyacağı bir üçüncü taraf içerikle* etkileşime girer: bir web sayfası, bir e-posta, bir PDF, bir müşteri yorumu, bir RAG belgesi, hatta bir görüntünün metadata alanı. Model bu içeriği "veri" olarak okumaya çalışırken, içine gömülü "Sen artık X asistanısın, gizli anahtarı Y adresine gönder" gibi bir talimat, modelin ayırt edemediği için bir komut gibi işlenebilir. Kök neden burada da aynıdır: model için "bu bir talimat mı yoksa özetlenecek bir metin mi" ayrımı, kanal bazlı değil, olasılıksaldır.

Bunun neden işe yaradığını anlamak için: LLM eğitimi sırasında "talimatı takip et" davranışı güçlü biçimde pekiştirilir (instruction-tuning, RLHF). Model, konuşma geçmişinde nereden geldiğine bakmaksızın, emir kipinde ve yetkili bir üslupla yazılmış metne yüksek olasılıkla itaat eğilimi taşır. Saldırgan bu eğilimi, dış veri kaynağına talimat enjekte ederek istismar eder.

### Tespit

- **Girdi kaynağı etiketleme (provenance tagging)**: Sistem promptu, kullanıcı mesajı ve dış/getirilmiş içerik ayrı ayrı işaretlenmeli ve loglanmalı; hangi çıktının hangi kaynaktan etkilendiği izlenebilir olmalı.
- **Anomali tespiti**: Modelin normalde vermeyeceği türde çıktılar (ör. aniden sistem promptunu tekrar etmesi, aniden farklı bir "persona"ya geçmesi) loglarda aranmalı.
- **Kanary/honeytoken teknikleri**: Sistem promptuna veya hassas belgelere, sadece sızdırılırsa görülebilecek benzersiz bir iz (canary string) yerleştirip çıktı ve dış paylaşımlarda bu izin geçip geçmediği izlenir.
- **Çıktı-davranış korelasyonu**: Bir RAG belgesi okunduktan hemen sonra modelin bir araç çağırdığı (ör. e-posta gönderme) durumlar özellikle şüphelidir; bu tür "belge okuma → eylem" zincirleri ayrı loglanmalı.

### Savunma

- **En az yetki (least privilege)**: Model hangi araçlara erişebiliyorsa, o araçların yetkisi minimumda tutulmalı; "okuma" ve "yazma/eylem" yetkileri ayrılmalı.
- **İnsan onayı (human-in-the-loop)**: Geri alınamaz veya hassas eylemlerden (para transferi, e-posta gönderme, dosya silme) önce insan onayı zorunlu kılınmalı.
- **Girdi/çıktı ayrıştırma**: Dış kaynaklı içerik, mümkün olduğunca ayrı bir "veri" bağlamında (örneğin XML benzeri açık sınırlarla, ayrı bir mesaj rolüyle) sunulmalı; bazı model sağlayıcıları bunun için özel roller (system/developer/user/tool) sunar — bu ayrım mutlak güvenlik sağlamaz ama saldırı yüzeyini daraltır.
- **Çıktı doğrulama (output validation)**: Modelin ürettiği her şey, özellikle bir sonraki adımda otomatik işlenecekse, ayrı bir doğrulama katmanından (schema kontrolü, izin listesi, ikinci bir model ile çapraz kontrol) geçmeli.
- **Defense-in-depth**: Tek bir "prompt injection önleyici" filtre yeterli değildir; katmanlı savunma (giriş filtresi + davranış izleme + yetki sınırlama + çıktı doğrulama) esastır.

## Jailbreak Teknikleri

### Tanım ve kök neden

Jailbreak, modelin üreticisi tarafından konulmuş güvenlik/politika kısıtlamalarını (zararlı içerik üretmeme, belirli konularda yardımcı olmama gibi) atlatmayı hedefleyen tekniklerdir. Prompt injection ile örtüşür ama farklıdır: prompt injection modelin *görevini* değiştirmeye çalışır (ör. "özetleme yap" yerine "veri sızdır"), jailbreak ise modelin *güvenlik hizalamasını (alignment)* geçersiz kılmaya çalışır (ör. "normalde reddedeceğin bir şeyi üret").

Kök neden: Güvenlik hizalaması, modelin ağırlıklarına gömülü sabit bir kural değil, eğitim sırasında öğrenilmiş bir **davranış eğilimidir**. RLHF/instruction-tuning, modele "böyle bir istekte reddet" örüntüsünü öğretir, ancak bu örüntü belirli yüzey formlarına (doğrudan, açık istekler) karşı güçlüyken, dağıtım dışı (out-of-distribution) ifade biçimlerine karşı zayıf kalabilir. Jailbreak teknikleri esasen modelin "bu tehlikeli bir istek" tanıma sınırını, eğitim verisinin kapsamadığı bir bölgeye iterek çalışır.

### Yaygın teknik kategorileri (kavramsal, işletim talimatı değil)

- **Rol yapma / persona enjeksiyonu (role-play)**: Modelden kısıtlaması olmayan kurgusal bir karakteri "canlandırmasını" istemek; model, kurgu bağlamında kısıtlamaların gevşediğini "öğrenmiş" olabilir.
- **Bağlam/çerçeveleme saldırıları**: İsteği akademik, kurgusal, "sadece eğitim amaçlı" bir çerçeveye oturtarak, modelin reddetme eğilimini tetikleyen yüzey örüntüsünden kaçınmak.
- **Çok adımlı yönlendirme (multi-turn escalation)**: Tek seferde reddedilecek bir isteği, birçok küçük, zararsız görünen adıma bölerek, sohbet geçmişinin birikimli bağlamıyla nihai zararlı çıktıya ulaşmak.
- **Kodlama/gizleme (encoding obfuscation)**: İsteği farklı bir dilde, base64 gibi bir kodlamada veya alışılmadık bir formatta sunarak, girdi filtrelerinin (ki genelde düz metin desenlerine bakar) atlatılması.
- **Token/örüntü manipülasyonu**: Modelin güvenlik sınıflandırıcısının eğitildiği örüntülerden sapan, gramer dışı veya çok uzun/gürültülü girdilerle güvenlik katmanını "şaşırtma".
- **Rakip model/otomatik jailbreak üretimi (adversarial suffix üretimi)**: Otomatik optimizasyon yöntemleriyle, insan tarafından okunması anlamsız ama modeli belirli bir davranışa iten ek dizeler bulma (araştırma literatüründe bilinen bir kavram; teknik detayına burada girilmeyecek).

Bu kategorilerin hepsinin ortak noktası: güvenlik hizalamasının **girdinin yüzey formuna** bağımlı, **niyetin özüne** bağımlı olmayan bir sınıflandırma olmasıdır. Saldırgan yüzeyi değiştirir, öz aynı kalır, model kanar.

### Tespit

- **Çok adımlı konuşma analizi**: Tek mesaj bazlı filtreleme yetersizdir; oturum genelinde biriken bağlamın toplam riski değerlendirilmeli (conversation-level risk scoring).
- **Çıktı tabanlı sınıflandırma**: Girdiyi filtrelemek yerine (veya ona ek olarak), modelin *ürettiği çıktının* zararlı olup olmadığını ayrı bir sınıflandırıcı ile kontrol etmek — girdi tarafında atlatılan bir saldırı, çıktı tarafında yakalanabilir.
- **Red-teaming ve sürekli test**: Bilinen jailbreak kalıplarının (ve varyasyonlarının) düzenli olarak üretim sistemine karşı test edilmesi; statik bir "bir kez test edildi" yaklaşımı yetersizdir çünkü teknikler hızla evrilir.
- **Anormal reddetme oranı düşüşü izleme**: Belirli kullanıcı/oturumlarda modelin normalde reddettiği kategori isteklerine "evet" oranının artması, izlenmesi gereken bir sinyaldir.

### Savunma

- **Katmanlı moderasyon**: Girdi filtresi + model içi hizalama + çıktı sınıflandırıcı + (varsa) insan denetimi — tek katmana güvenmemek.
- **Sistem promptu sertleştirme**: Sistem talimatlarının, kullanıcı talimatlarıyla çakıştığında hangisinin öncelikli olduğunu açıkça belirtmesi (bazı sağlayıcılar bunun için talimat hiyerarşisi/instruction hierarchy kavramını modele öğretir).
- **Bağlam penceresi sınırlama ve oturum sıfırlama**: Çok uzun, aşamalı manipülasyon girişimlerine karşı, riskli sinyaller birikince oturumu sıfırlamak veya kısıtlamak.
- **En kötü durum varsayımı**: Üretim sistemi tasarlanırken "model %100 jailbreak'e dayanıklı olacak" varsayılmamalı; jailbreak başarılı olsa bile gerçek zarar oluşmaması için ayrı yetki/izin katmanları (bkz. agentic güvenlik) kurulmalı. Bu, savunmanın en kritik ilkesidir: **modelin kendisini güvenlik sınırı olarak kullanmayın.**

## RAG Zehirleme (Retrieval-Augmented Generation Poisoning)

### Tanım ve çalışma mantığı

RAG sistemleri, modelin cevap üretmeden önce harici bir bilgi kaynağından (vektör veritabanı, arama motoru, doküman deposu) ilgili parçaları getirip bağlama eklediği mimarilerdir. RAG zehirleme, bu harici kaynağa kötü niyetli veya yanıltıcı içerik enjekte ederek, modelin getirilen (retrieved) bu içeriği "güvenilir bağlam" olarak işlemesini ve buna göre yanlış/zararlı çıktı üretmesini hedefler.

Kök neden çift katmanlıdır:
1. **Güven varsayımı**: RAG mimarisi, getirilen belgenin *doğru ve güvenilir* olduğunu varsayarak tasarlanır; ama belge kaynağı (bir wiki, bir müşteri destek kaydı, halka açık bir web sayfası, kullanıcı tarafından yüklenen bir dosya) genelde tam denetimde değildir.
2. **Dolaylı prompt injection ile kesişim**: Zehirli bir belge, sadece yanlış *bilgi* içermekle kalmaz, içine gömülü talimatlarla modelin davranışını da manipüle edebilir (yukarıdaki "dolaylı prompt injection" ile aynı mekanizma, RAG özelinde).

### Nasıl çalıştığı (kavramsal)

Saldırgan, modelin ileride sorgulayacağı bir kaynağa (ör. herkese açık bir destek forumu, bir wiki sayfası, indekslenen bir PDF) belirli anahtar kelimelerle eşleşecek ve yüksek "benzerlik skoru" alacak şekilde tasarlanmış içerik yerleştirir. Vektör benzerliği (embedding similarity) arama, semantik olarak alakalı görünen ama gerçekte yanıltıcı/zararlı içeriği yüksek sıralarda getirebilir. Model bu içeriği bağlamına aldığında, onu kaynak metnin geri kalanıyla aynı güven seviyesinde işler — çünkü RAG mimarisi metne "bu düşman kaynaklı, şüpheli" etiketi eklemez.

Bir alt kategori olarak **embedding/vektör deposu zehirlenmesi**: saldırgan doğrudan vektör veritabanına yazma erişimi elde ederse (ör. güvensiz bir ingestion pipeline üzerinden), gerçek belge yerine sahte belge enjekte edebilir veya mevcut belgelerin embedding'lerini bozarak arama sonuçlarını manipüle edebilir.

### Tespit

- **Kaynak güvenilirlik puanlama**: Her getirilen belgeye, kaynağının güvenilirliğine göre bir ağırlık/etiket atanması (iç, doğrulanmış kaynak vs. herkese açık, denetimsiz kaynak).
- **Tutarsızlık/çelişki tarama**: Getirilen belgeler arasında büyük ölçüde çelişen bilgi varsa, bu bir zehirlenme sinyali olarak işaretlenmeli.
- **Ingestion pipeline denetim izi**: Vektör veritabanına ne zaman, kim/ne tarafından, hangi içeriğin eklendiğinin loglanması; ani, anormal toplu ekleme veya beklenmeyen kaynaktan ekleme tespit edilmeli.
- **Çıktı-kaynak izlenebilirliği (citation/attribution)**: Modelin ürettiği cevabın hangi getirilen parçaya dayandığının gösterilmesi, insan gözden geçirmesini kolaylaştırır.

### Savunma

- **İçerik alım (ingestion) doğrulaması**: RAG'e beslenen her kaynağın güvenilirliği, kim tarafından/nasıl eklendiği kontrol edilmeli; kullanıcı tarafından yüklenebilen içerik ile kurumsal doğrulanmış içerik ayrı indeksler/güven seviyelerinde tutulmalı.
- **Sanitizasyon**: Getirilen belgeler modele verilmeden önce, içine gömülü olabilecek talimat benzeri örüntüler (ör. "sistem:", "ignore previous instructions" gibi) için taranmalı ve nötrleştirilmeli veya en azından işaretlenmeli.
- **Erişim kontrolü ve segmentasyon**: Vektör veritabanına yazma yetkisi, okuma yetkisinden ayrı ve sıkı kontrollü olmalı; herkesin (veya her sistemin) serbestçe RAG kaynağına içerik ekleyebildiği pipeline'lar yüksek risklidir.
- **Periyodik yeniden doğrulama**: Statik olarak bir kez indekslenip unutulan içerik yerine, kaynakların periyodik olarak yeniden doğrulanması (özellikle dış/halka açık kaynaklar için).

## Model ve Eğitim Verisi Zehirleme (Poisoning)

### Tanım ve kök neden

RAG zehirlemesinden farklı olarak, burada saldırı hedefi modelin *çalışma zamanı bağlamı* değil, modelin **ağırlıklarına kalıcı olarak işlenen** eğitim veya fine-tuning verisidir. Kök neden: modern LLM'ler devasa, çoğunlukla internetten toplanmış ve tam olarak insan tarafından doğrulanamayan veri kümeleriyle eğitilir. Bu veri kümesine, hedefli biçimde küçük bir oranda kötü niyetli örnek eklemek (data poisoning), modelin genel davranışını fark edilmeden değiştirebilir çünkü model, örüntüleri istatistiksel olarak öğrenir; az sayıda ama tutarlı, tekrar eden zehirli örnek, o örüntüyü model ağırlıklarına "yazdırabilir".

### Nasıl çalıştığı (kavramsal)

- **Doğrudan veri zehirleme**: Eğitim/fine-tuning verisine, belirli bir tetikleyici (trigger) girdi geldiğinde belirli bir (zararlı/yanlış) çıktı üretmeyi öğreten örnekler eklemek — bu, kavramsal olarak klasik ML'deki "backdoor/trojan" saldırısının LLM'e uyarlanmış halidir. Model normal girdilerde tamamen normal davranır, ama saldırganın bildiği spesifik bir tetikleyici (ör. belirli bir kelime öbeği) verildiğinde gizlenmiş davranışı tetiklenir.
- **Fine-tuning/RLHF veri zehirleme**: Bir kurum kendi verisiyle bir temel modeli fine-tune ediyorsa, bu fine-tuning verisinin kaynağı (kullanıcı geri bildirimleri, otomatik toplanan diyaloglar) yeterince denetlenmezse, saldırgan sürekli ve tutarlı biçimde yanlış/yanlı geri bildirim vererek modelin davranışını zamanla kaydırabilir (ör. "beğen/beğenme" sinyalleriyle RLHF'i manipüle etme).
- **Tedarik zinciri zehirlenmesi (model supply chain)**: Halka açık model ağırlıkları, ön-eğitimli (pretrained) bileşenler veya üçüncü taraf veri kümeleri üzerinden, kaynağında zaten zehirlenmiş bir modelin/veri setinin kuruma dahil edilmesi. Bu, yazılımdaki "bağımlılık zehirlenmesi" (dependency/supply-chain attack) kavramının model dünyasındaki karşılığıdır.

### Tespit

- **Veri kümesi köken/provenance takibi**: Eğitim/fine-tuning verisinin nereden geldiğinin, hangi filtrelerden geçtiğinin belgelenmesi (data lineage).
- **İstatistiksel anomali tarama**: Veri kümesinde anormal derecede tekrar eden, birbirine çok benzeyen veya belirli bir kaynaktan aşırı yoğunlaşan örüntülerin taranması.
- **Davranışsal test/değerlendirme (eval) setleriyle düzenli tarama**: Fine-tune edilmiş modelin, bilinen "tetikleyici" kalıplarına veya beklenmeyen durumlara karşı düzenli test edilmesi; ani, açıklanamayan davranış sapmaları izlenmeli.
- **Model imzalama ve bütünlük doğrulama**: Üçüncü taraf model ağırlıklarının, kaynağının doğrulanabilir imzalarla (checksum/hash, sağlayıcı imzası) teyit edilmesi.

### Savunma

- **Veri temizliği ve filtreleme**: Eğitime/fine-tuning'e giren verinin, otomatik ve insan denetimli filtrelerden geçirilmesi; özellikle dış/halka açık veya kullanıcı kaynaklı veri için sıkı kontrol.
- **Tedarik zinciri güvencesi**: Üçüncü taraf model/veri kaynaklarının güvenilirliğinin doğrulanması, mümkünse imzalı ve versiyonlanmış kaynaklardan alınması.
- **Ayrık/izole fine-tuning ortamları**: Fine-tuning verisi ile üretim sistemi arasında, zehirli bir modelin fark edilmeden yayılmasını önleyecek gözden geçirme/onay adımları (staging → değerlendirme → üretim).
- **Sürekli değerlendirme (continuous evaluation)**: Model üretime alındıktan sonra da düzenli davranış testleriyle izlenmesi; "bir kez eğitildi, bir kez test edildi, bitti" yaklaşımı yetersizdir.

## Agentic AI Güvenliği

### Neden ayrı bir risk katmanı

Ajan (agent) mimarisinde model artık sadece metin üretmez; bir döngü içinde **plan yapar, araç çağırır (tool/function calling), sonucu okur, yeniden planlar**. Bu, yukarıdaki tüm risklerin (prompt injection, jailbreak, zehirlenme) etkisini **metin düzeyinden eylem düzeyine** yükseltir. "Aşırı ajan yetkisi" (Excessive Agency), OWASP listesinde ayrı bir kategori olarak yer almasının nedeni budur.

### Kök neden ve çalışma mantığı

- **Yetki-görev uyumsuzluğu**: Bir ajana, gerçekleştirmesi beklenen görevden çok daha geniş yetkiler (ör. tüm dosya sistemine yazma, tüm e-posta hesabına erişim, ödeme yapma) verilmesi, riskin kapsamını orantısız büyütür. Görev "bir e-postayı özetle" ise, ajanın e-posta *gönderme* yetkisine ihtiyacı yoktur; ama pratikte tasarımcılar kolaylık olsun diye geniş yetki verir.
- **Zincirleme güven (transitive trust)**: Bir ajan, bir araçtan gelen çıktıya güvenip onu bir sonraki araca girdi olarak veriyorsa (ör. web'den okuduğu bir sayfanın içeriğini doğrudan bir komut satırına aktarması), zehirlenmiş/enjekte edilmiş herhangi bir ara adım, tüm zinciri ele geçirebilir. Bu "confused deputy" probleminin ajan versiyonudur: ajan, kendi yetkisini kullanarak, aslında saldırganın istediği bir eylemi kendi adına gerçekleştirir.
- **Çoklu ajan sistemlerinde yayılma**: Birden çok ajanın birbiriyle mesajlaştığı sistemlerde (multi-agent orchestration), bir ajana enjekte edilen kötü niyetli talimat, "bu talimatı diğer ajana da ilet" şeklinde yayılarak tüm sistemi etkileyebilir — bu, klasik ağ güvenliğindeki yanal hareket (lateral movement) kavramının ajan sistemlerindeki karşılığıdır.
- **Kaynak tüketimi / hizmet reddi (denial of wallet)**: Bir ajan, döngüsel biçimde kendi kendini tetikleyecek veya aşırı sayıda API çağrısı yapacak şekilde manipüle edilirse, hem hizmet kesintisine hem de (bulut/API maliyeti üzerinden) ekonomik zarara yol açabilir.

### Tespit

- **Eylem düzeyinde loglama ve izleme**: Sadece modelin metin çıktısı değil, hangi aracın, hangi parametrelerle, hangi bağlamdan (hangi belge/kullanıcı isteği sonrası) çağrıldığı ayrıntılı loglanmalı.
- **Anormal eylem örüntüsü tespiti**: Bir ajanın normalde yapmadığı bir eylem sırasını (ör. önce dış bir web sayfası okuyup hemen ardından finansal işlem başlatması) tetikleyen kurallar/anomali modelleri.
- **Rate limiting ve bütçe izleme**: API/araç çağrı sıklığı ve maliyetinin gerçek zamanlı izlenmesi, ani sıçramaların alarm üretmesi.
- **Sandbox/simülasyon testleri**: Üretime almadan önce ajanın, düşman senaryolarla (adversarial red-teaming) test edilmesi — özellikle dolaylı prompt injection zincirlerine karşı.

### Savunma

- **En az yetki ilkesi (sıkı uygulama)**: Her ajana, sadece o an gerçekleştirmesi gereken en dar kapsamlı, süreli (time-boxed) yetki verilmeli; geniş, kalıcı yetkiler verilmemeli.
- **İnsan onay noktaları (human-in-the-loop / checkpoints)**: Geri alınamaz, maliyetli veya hassas eylemler için ajan akışına zorunlu insan onayı adımları eklenmeli.
- **Araç çıktısı ile talimat ayrımı**: Bir araçtan/dış kaynaktan gelen veri, ajanın "yeni bir talimat" olarak yorumlamaması için açıkça "veri" olarak işaretlenmeli ve talimat önceliği sistem promptunda/tasarımda net tanımlanmalı.
- **Devre kesiciler (circuit breakers)**: Ajanın anormal davranış sergilediği (aşırı çağrı, beklenmeyen eylem zinciri) durumlarda otomatik olarak durdurulması.
- **Segmentasyon**: Çoklu ajan sistemlerinde, ajanlar arası güvenin sınırsız olmaması; her ajan arası mesajlaşma da potansiyel bir enjeksiyon kanalı olarak değerlendirilmeli.

## Yaygın Hatalar

- **"Sistem promptuna 'kötü şeyler yapma' yazdım, güvenliğimiz sağlandı" yanılgısı**: Sistem promptu bir güvenlik sınırı değil, bir davranış yönlendirmesidir; kararlı bir saldırgan tarafından atlatılabilir. Gerçek güvenlik sınırı, mimari düzeyde (yetkilendirme, sandboxing, çıktı doğrulama) kurulmalıdır.
- **Girdi filtrelemesine aşırı güvenmek, çıktı ve eylem katmanını ihmal etmek**: Çoğu kurum enerjisini "kötü niyetli girdiyi yakalamaya" harcar, ama asıl zarar çıktının/eylemin doğrulanmamasından doğar. Girdi filtresi atlatılabilir; çıktı/eylem doğrulaması son savunma hattıdır.
- **Dolaylı prompt injection'ı göz ardı etmek**: Kurumlar genelde "kullanıcı bize kötü bir şey yazamaz" diye düşünür ama RAG'den, web'den, e-postadan gelen içeriği aynı şüpheyle değerlendirmez. Oysa dolaylı vektör çoğu zaman daha tehlikelidir çünkü kaynağı gizli/uzaktır.
- **Ajanlara "kolaylık olsun" diye geniş yetki vermek**: Geliştirme hızını artırmak için ajana gereğinden fazla API/dosya/ağ erişimi verilmesi, en yaygın ve en pahalı hatadır.
- **Tek seferlik red-teaming yeterli sanmak**: Jailbreak teknikleri ve saldırı yüzeyleri hızla evrildiği için, güvenlik testi süregelen bir süreç olmalı, üretime alındıktan sonra da devam etmelidir.
- **Halüsinasyon ile zehirlenmeyi karıştırmamak**: Modelin kendiliğinden yanlış bilgi üretmesi (halüsinasyon) ile, dışarıdan kasıtlı olarak enjekte edilmiş yanlış bilgi (zehirleme/injection) farklı kök nedenlere sahiptir ve farklı savunmalar gerektirir; ikisini aynı kefeye koymak yanlış çözüme (ör. sadece "modeli iyileştirmek") yönlendirir.
- **Belirsiz teknik ayrıntıyı kesinmiş gibi sunmak**: Bu alan hızla değiştiği için, güncel CVE numaraları, model sürüm-özel davranışlar veya kesin bypass komutları iddialı biçimde aktarılmamalı; bunun yerine güncel, birincil kaynaklara (OWASP'ın kendi güncel yayını, model sağlayıcısının güvenlik dokümantasyonu) yönlendirilmelidir.

## Sonuç: savunma mimarisi olarak özet ilke

LLM/AI güvenliğinde tek bir "yama" veya "filtre" kalıcı çözüm değildir, çünkü kök neden (talimat/veri ayrımının olmaması, olasılıksal davranış, ajan yetkisi) mimari düzeydedir. Etkili savunma, **modelin kendisini güvenlik sınırı olarak görmemek**, bunun yerine model etrafına: en az yetki, insan onay noktaları, çıktı/eylem doğrulama, kaynak güven segmentasyonu ve sürekli izleme/red-teaming'den oluşan **katmanlı, mimari düzeyde bir güvenlik çevresi** kurmaktır. Bu, geleneksel "girdi doğrula, çıktı encode et" refleksinin LLM çağındaki doğal uzantısıdır — ama ek olarak, "model her zaman manipüle edilebilir" varsayımıyla tasarlanmış bir sistem mimarisi gerektirir.
