# Tehdit Modelleme (STRIDE): Kapsamlı Uzman Referansı

## Tehdit Modelleme Nedir?

Tehdit modelleme (threat modeling), bir sistemin henüz tasarım veya geliştirme aşamasındayken "bu sistemi kim, neden ve nasıl kötüye kullanabilir?" sorusuna sistematik bir yanıt üretme sürecidir. Amaç, saldırgan gözüyle bakarak güvenlik zafiyetlerini kod yazılmadan veya sisteme dokunulmadan önce ortaya çıkarmaktır. Klasik penetration test'in aksine tehdit modelleme reaktif değil proaktiftir: bir açığı sömürmeye çalışmaz, açığın var olma *ihtimalini* mimari düzeyde tespit eder.

STRIDE, Microsoft'ta 1999'da (Loren Kohnfelder ve Praerit Garg tarafından) geliştirilmiş, tehditleri altı kategoriye ayıran bir sınıflandırma (taxonomy) yöntemidir. STRIDE tek başına bir metodoloji değil, bir *tehdit türü kataloğudur*; genellikle Data Flow Diagram (DFD) tabanlı bir analiz süreciyle birlikte kullanılır. STRIDE'ın gücü, mühendisin "acaba başka ne olabilir?" diye boşlukta düşünmesi yerine, her sistem bileşeni için altı bilinen tehdit sınıfını tek tek gözden geçirmeye zorlamasıdır. Bu, insan yaratıcılığının kaçınılmaz kör noktalarını kapatan yapılandırılmış bir hatırlatıcıdır.

## STRIDE Kısaltmasının Açılımı ve Kök Mantığı

STRIDE, altı tehdit sınıfının baş harflerinden oluşur. Kritik nokta şudur: her tehdit sınıfı, ihlal ettiği bir güvenlik özelliğinin (security property) karşıtıdır. Bu ikili yapıyı anlamak, STRIDE'ı ezberlemek yerine *çıkarabilmenizi* sağlar.

| STRIDE Tehdidi | İhlal Edilen Özellik | Kısa Açıklama |
|---|---|---|
| **S** — Spoofing (Kimlik sahteciliği) | Authentication (Kimlik doğrulama) | Başkası gibi görünme |
| **T** — Tampering (Kurcalama) | Integrity (Bütünlük) | Veriyi/kodu izinsiz değiştirme |
| **R** — Repudiation (İnkâr) | Non-repudiation (İnkâr edilemezlik) | Yaptığını yapmadım deme |
| **I** — Information Disclosure (Bilgi ifşası) | Confidentiality (Gizlilik) | Yetkisiz veri sızması |
| **D** — Denial of Service (Hizmet reddi) | Availability (Erişilebilirlik) | Sistemi kullanılamaz kılma |
| **E** — Elevation of Privilege (Yetki yükseltme) | Authorization (Yetkilendirme) | Hakkı olmayan yetkiyi elde etme |

Bu tablonun sağ sütunu tesadüf değildir. Güvenliğin temel hedefleri olan CIA üçlüsü (Confidentiality, Integrity, Availability) ile authentication, authorization ve non-repudiation kavramları, STRIDE'ın tam olarak *ne koruduğunu* tanımlar. Bir tehdit bulmak istediğinizde aslında "bu bileşende bu altı özellikten hangisi kırılabilir?" diye soruyorsunuz. Bu yüzden STRIDE, güvenlik özelliklerinin sistematik olarak "tersine çevrilmiş" halidir.

## Data Flow Diagram (DFD): Analizin İskeleti

STRIDE'ı hava boşluğunda uygulayamazsınız; neyin nasıl aktığını gösteren bir haritaya ihtiyacınız vardır. Bu harita Data Flow Diagram'dır (DFD). DFD, sistemi dört temel eleman türüyle modeller:

- **External Entity (Dış varlık)** — kare/dikdörtgen ile gösterilir. Sistemin kontrolü dışındaki aktörler: son kullanıcı, üçüncü parti API, tarayıcı, bir başka şirketin servisi. Bunlar güven açısından "sıfır güven" ile başlanması gereken noktalardır çünkü davranışlarını denetleyemezsiniz.
- **Process (İşlem)** — daire ile gösterilir. Veriyi işleyen kod parçaları: web sunucusu, mikroservis, bir Lambda fonksiyonu, arka plan işleyicisi.
- **Data Store (Veri deposu)** — iki paralel çizgi arasında gösterilir. Veritabanı, dosya sistemi, cache, mesaj kuyruğu, log dosyası, S3 bucket.
- **Data Flow (Veri akışı)** — oklarla gösterilir. Elemanlar arası hareket eden veriyi temsil eder: HTTP isteği, SQL sorgusu, RPC çağrısı, dosya okuma.

DFD'nin gücü basitliğinden gelir. Amaç mimari güzelliği değil, verinin *nereden gelip nereye gittiğini* ve bu yolculukta hangi güven seviyelerini geçtiğini görünür kılmaktır. Detay seviyesi (DFD Level 0, 1, 2) sisteme göre ayarlanır: Level 0 (context diagram) sistemi tek bir kutu olarak dış dünyayla ilişkisinde gösterir; Level 1 ana bileşenlere böler; Level 2 ve altı belirli bir bileşenin içine iner. Pratikte çoğu ekip için Level 1 tatlı noktadır — analiz yapacak kadar detaylı, boğulmayacak kadar sade.

### Kök Neden: Neden DFD Şart?

Zihinsel modellerimiz sistemleri "çalışırken" hayal eder — mutlu yol (happy path). Saldırgan ise mutsuz yolu arar. DFD, veriyi durağan bir resme dönüştürerek beynin kaçırdığı geçiş noktalarını gözle görülebilir hale getirir. Özellikle veri akışının bir güven seviyesinden diğerine geçtiği anları — yani güven sınırlarını — açığa çıkarır. İşte tehditlerin ezici çoğunluğu tam bu geçişlerde doğar.

## Güven Sınırı (Trust Boundary): Tehditlerin Doğduğu Yer

Güven sınırı (trust boundary), sistemin farklı güven seviyelerine sahip iki bölgesi arasındaki hayali çizgidir. DFD üzerinde genellikle kesikli bir çizgiyle gösterilir. Bir güven sınırının bir tarafında "daha güvenilir" (örneğin doğrulanmış, iç ağdaki kod), diğer tarafında "daha az güvenilir" (örneğin internetten gelen ham istek) veri veya aktör bulunur.

Örnek güven sınırları:
- Tarayıcı ile web sunucusu arasındaki çizgi (internet/DMZ sınırı).
- Uygulama katmanı ile veritabanı arasındaki çizgi.
- Bir mikroservis ile diğeri arasındaki çizgi.
- Kernel space ile user space arasındaki çizgi (işletim sistemi seviyesinde).
- Aynı sunucuda çalışan iki farklı ayrıcalık seviyesindeki proses arasındaki çizgi.
- Bir container ile host arasındaki çizgi.

### Kök Neden: Neden Güven Sınırları Bu Kadar Önemli?

Temel ilke şudur: **veri bir güven sınırını geçtiğinde, alıcı taraf o veriye asla güvenmemelidir**. Güvenlik açıklarının büyük çoğunluğu, geliştiricinin sınırın "iç" tarafındaki bir varsayımı, sınırın "dış" tarafındaki veriye uygulamasıyla oluşur. SQL injection, bir dış varlıktan gelen string'in içeriden gelmiş gibi güvenilerek sorguya konmasıdır. Yetki yükseltme, bir prosesin güven sınırının ötesindeki bir bileşene ait yetkilere sızmasıdır.

Pratik bir kural: **DFD'nizde bir veri akışı okunun bir güven sınırını kestiği her nokta, mutlaka bir tehdit modelleme dikkat noktasıdır.** Bu kesişim noktalarına STRIDE'ı uygularsanız, sistemdeki gerçek risk yoğunluğunun neredeyse tamamını yakalarsınız. Güven sınırlarını kesmeyen, tamamen "iç" bir veri akışı genellikle çok daha düşük risklidir (ama sıfır risk değildir — insider threat ve lateral movement senaryoları bunu kırar).

## STRIDE'ın DFD Elemanlarına Eşlenmesi

STRIDE'ın az bilinen ama son derece güçlü bir özelliği, her tehdit türünün her DFD eleman türünde eşit görülmemesidir. Microsoft'un orijinal yaklaşımında (STRIDE-per-element) belirli tehditler belirli eleman türleriyle ilişkilendirilir. Genel eğilim şöyledir:

- **External Entity**: Spoofing ve Repudiation açısından hassastır. Bir dış varlık başkası gibi davranabilir (spoofing) veya bir işlemi yaptığını inkâr edebilir (repudiation).
- **Process**: Altı tehdidin *tümüne* açıktır. Prosesler sistemin en zengin saldırı yüzeyidir.
- **Data Store**: Tampering, Information Disclosure, Denial of Service ve (log tutuyorsa) Repudiation açısından hassastır. Bir veri deposu genellikle "kimlik" iddiasında bulunmadığı için Spoofing daha az anlamlıdır.
- **Data Flow**: Tampering, Information Disclosure ve Denial of Service açısından hassastır. Ağ üzerinde akan veri değiştirilebilir (tampering), dinlenebilir (disclosure) veya kesilebilir (DoS).

Bu eşleme, analizi hızlandıran bir kontrol listesi sağlar. Her DFD elemanının başına gelip "bu eleman için geçerli STRIDE tehditleri hangileri?" diye sorarsanız, yüzlerce soruyu birkaç düzineye indirmiş olursunuz. Kör bir şekilde her elemana altı tehdidi de uygulamak da mümkündür ve daha kapsayıcıdır; hız/kapsam dengesini ekibiniz belirler.

## Her STRIDE Tehdidinin Derinlemesine İncelenmesi

Aşağıda her tehdit için: çalışma mantığı, somut örnek, saldırganın istismar yaklaşımı ve savunma (azaltma) birlikte verilmiştir. Çünkü savunmayı ancak saldırıyı anladığınızda doğru tasarlarsınız.

### S — Spoofing (Kimlik Sahteciliği)

**Çalışma mantığı:** Saldırgan, sistemin bir kullanıcının, servisin veya bileşenin kimliğini doğrularken kullandığı sinyali taklit eder. Kök neden neredeyse her zaman zayıf veya eksik authentication'dır: sistem "sen kimsin?" sorusuna verilen cevabı yeterince güçlü doğrulamaz.

**Somut örnek:** Bir API, isteğin kimliğini yalnızca istek gövdesindeki `user_id` alanına bakarak belirliyorsa, saldırgan bu alanı başka bir kullanıcının ID'siyle değiştirerek onun kimliğine bürünür. Ağ seviyesinde ise ARP spoofing veya DNS spoofing ile saldırgan kendini meşru bir sunucu gibi gösterebilir. E-postada, gönderen adresinin (From) taklit edilmesi klasik bir spoofing örneğidir.

**İstismar mantığı:** Saldırgan, kimlik iddiasının nasıl doğrulandığını tersine mühendislikle çözer, sonra bu iddiayı üretebildiği en ucuz yoldan taklit eder. Session token tahmin edilebiliyorsa üretir; sertifika doğrulaması yoksa sahte sertifika sunar.

**Savunma (azaltma):** Güçlü authentication mekanizmaları kullanın — mümkünse multi-factor authentication (MFA). Servisler arası iletişimde mutual TLS (mTLS) ile her iki tarafın sertifikasını doğrulayın. Session token'ları kriptografik olarak güçlü, tahmin edilemez ve süreli olsun. E-posta için SPF, DKIM ve DMARC uygulayın. Kimliği istemcinin gönderdiği bir alandan (örneğin gövdedeki `user_id`) değil, sunucunun doğruladığı bir oturumdan alın. Bu son nokta çok yaygın bir hatadır.

### T — Tampering (Kurcalama)

**Çalışma mantığı:** Saldırgan, aktarım halindeki (in-transit) veya durağan (at-rest) veriyi ya da çalışan kodu izinsiz değiştirir. Kök neden, bütünlüğü (integrity) doğrulayan bir mekanizmanın olmamasıdır.

**Somut örnek:** HTTPS kullanmayan bir bağlantıda, aradaki bir saldırgan (man-in-the-middle) indirilmekte olan yazılım paketine kötü amaçlı kod enjekte edebilir. Bir web uygulamasında fiyat bilgisi client-side'da tutulup sunucuya geri gönderiliyorsa, saldırgan fiyatı değiştirip 1 TL'ye ürün satın alabilir. Log dosyaları korunmuyorsa, saldırgan izlerini silmek için bunları düzenleyebilir.

**İstismar mantığı:** Saldırgan, sistemin bir veriyi değiştirilmemiş kabul ettiği noktayı bulur ve o veriyi değiştirir. Değişikliğin fark edilip edilmediğini test eder; eğer bütünlük kontrolü yoksa değişiklik başarılı olur.

**Savunma (azaltma):** Aktarımda TLS ile bütünlük ve şifreleme sağlayın. Kritik veriler için cryptographic hash, HMAC veya digital signature kullanarak alıcı tarafın değişikliği tespit edebilmesini sağlayın. Yazılım dağıtımında code signing uygulayın. Client'tan gelen hiçbir güvenlik-kritik değeri (fiyat, yetki, kullanıcı kimliği) doğrulamadan kabul etmeyin; sunucu tarafında yeniden hesaplayın veya doğrulayın. Veritabanı ve dosya sistemlerinde uygun erişim kontrolleri ve mümkünse değişmezlik (immutability) veya append-only log yapıları kullanın.

### R — Repudiation (İnkâr)

**Çalışma mantığı:** Bir aktör, gerçekleştirdiği bir eylemi yapmadığını iddia eder ve sistemde bunun aksini kanıtlayacak güvenilir bir kayıt yoktur. Kök neden, yetersiz veya güvenilmez logging ve audit trail'dir.

**Somut örnek:** Bir kullanıcı bir para transferi yapar, sonra "ben yapmadım" der. Eğer sistem bu işlemi kim, ne zaman, hangi IP'den yaptığına dair güvenli bir kayıt tutmuyorsa, işlemi ne şirket kanıtlayabilir ne de kullanıcının iddiası çürütülebilir. Loglar saldırgan tarafından değiştirilebiliyorsa, meşru loglar bile mahkemede delil değeri taşımaz.

**İstismar mantığı:** Kötü niyetli aktör, ya hiç iz bırakmayan bir yol bulur ya da bıraktığı izleri sonradan siler/değiştirir. Repudiation genellikle diğer bir saldırının (dolandırıcılık, veri hırsızlığı) sonrasında "hesap verebilirliği" ortadan kaldırmak için kullanılır.

**Savunma (azaltma):** Güvenli, değiştirilemez (tamper-evident) audit log'lar tutun. Her önemli işlemi kim, ne, ne zaman, nereden bilgisiyle kaydedin. Log'ların bütünlüğünü hash zincirleri veya harici bir güvenli log servisi (write-once medya, SIEM) ile koruyun. Kritik işlemler için digital signature kullanarak inkâr edilemezlik (non-repudiation) sağlayın — kullanıcının özel anahtarıyla imzaladığı bir işlemi inkâr etmesi kriptografik olarak zorlaşır. Log'ları üreten sistemden ayrı bir yerde saklayın ki saldırgan sistemi ele geçirse bile log'ları silemesin.

### I — Information Disclosure (Bilgi İfşası)

**Çalışma mantığı:** Yetkisiz bir tarafın görmemesi gereken bilgiye erişmesidir. Kök neden, gizliliği (confidentiality) koruyan mekanizmaların eksikliği veya yanlış yapılandırılmasıdır.

**Somut örnek:** Şifrelenmemiş bir bağlantıda ağ trafiğini dinleyen saldırgan, oturum çerezlerini veya parolaları görebilir. Bir hata mesajı, veritabanı şemasını veya stack trace'i son kullanıcıya sızdırabilir. Yanlış yapılandırılmış bir S3 bucket veya erişim kontrolü olmayan bir API endpoint'i, tüm müşteri verisini internete açabilir. Zamanlama farklarından bilgi sızdıran timing attack'ler daha incelikli bir örnektir.

**İstismar mantığı:** Saldırgan, sistemin sızdırdığı her kırıntıyı toplar — hata mesajları, response header'ları, yanıt sürelerindeki farklar, erişim kontrolü zayıf endpoint'ler. Bu kırıntılar hem doğrudan hassas veri olabilir hem de daha büyük bir saldırının keşif (reconnaissance) aşamasını besler.

**Savunma (azaltma):** Hassas veriyi hem aktarımda (TLS) hem durağan halde (encryption at rest) şifreleyin. En az yetki (least privilege) ilkesiyle erişim kontrolü uygulayın. Hata mesajlarını genelleştirin; kullanıcıya iç detay vermeyin, detayı yalnızca sunucu log'una yazın. Parolaları asla düz metin saklamayın; güçlü, tuzlanmış (salted) bir password hashing algoritması (örneğin bcrypt, scrypt veya Argon2 ailesinden biri) kullanın. Depolama servislerinin erişim politikalarını düzenli denetleyin. Response'larda yalnızca gerekli alanları döndürün (over-fetching'i engelleyin).

### D — Denial of Service (Hizmet Reddi)

**Çalışma mantığı:** Saldırgan, sistemi meşru kullanıcılar için kullanılamaz hale getirir. Kök neden, kaynak tüketiminin sınırsız olması veya erişilebilirliği (availability) koruyan mekanizmaların eksikliğidir.

**Somut örnek:** Bir saldırgan çok sayıda kaynaktan aynı anda istek göndererek (distributed denial of service — DDoS) sunucunun kapasitesini tüketir. Uygulama seviyesinde ise tek bir pahalı sorgu — örneğin regular expression'daki catastrophic backtracking (ReDoS) veya sınırsız bir arama — az sayıda istekle sunucuyu kilitleyebilir. Bir dosya yükleme endpoint'i boyut sınırı koymuyorsa, saldırgan diski doldurabilir.

**İstismar mantığı:** Saldırgan, sistemde "girdi başına maliyet" oranının kendi lehine olduğu noktaları arar: küçük bir istekle büyük bir iş yaptırabildiği yerler. Bu asimetriyi sömürerek düşük maliyetle sistemi çökertir.

**Savunma (azaltma):** Rate limiting ve throttling ile istek hızını sınırlayın. Kaynak kotaları koyun: istek boyutu, sorgu karmaşıklığı, timeout, bağlantı sayısı. Pahalı işlemleri asenkron kuyruklara alın. Girdi doğrulamayı erken ve ucuz yapın (fail fast). Altyapı seviyesinde CDN ve DDoS koruma servisleri, auto-scaling ve load balancing kullanın. ReDoS için regex'leri denetleyin veya güvenli regex motorları tercih edin. Unutmayın: DoS'a karşı tam bağışıklık yoktur; hedef, saldırının maliyetini yükseltmek ve etkiyi sınırlamaktır.

### E — Elevation of Privilege (Yetki Yükseltme)

**Çalışma mantığı:** Saldırgan, sahip olduğundan daha yüksek yetkiler elde eder — normal kullanıcıdan admin'e, veya sistem dışından sistem içine. Kök neden, yetkilendirmenin (authorization) hatalı, eksik veya atlanabilir olmasıdır. STRIDE tehditleri içinde genellikle en yüksek etkiye sahip olanıdır çünkü çoğu zaman sistemin tam kontrolüne götürür.

**Somut örnek:** Bir web uygulamasında `/admin` paneline erişim yalnızca menüde linkin gizlenmesiyle "korunuyorsa", URL'yi doğrudan yazan herhangi bir kullanıcı admin işlevlerine erişebilir (missing function-level authorization). Bir başka kullanıcının kaynağına, sadece URL'deki ID'yi değiştirerek erişmek Insecure Direct Object Reference (IDOR) örneğidir. İşletim sistemi seviyesinde, buffer overflow veya kernel açığı ile normal bir prosesin root/SYSTEM yetkisine yükselmesi klasik bir örnektir.

**İstismar mantığı:** Saldırgan önce düşük yetkili bir konum elde eder (spoofing veya başka bir açıkla), sonra yetki kontrollerinin eksik veya tutarsız olduğu bir noktayı bularak yatay (aynı seviyede başka hesaba) veya dikey (daha yüksek seviyeye) hareket eder. Genellikle STRIDE zinciridir: spoofing → elevation → tampering.

**Savunma (azaltma):** Her istekte, sunucu tarafında, yetkilendirmeyi merkezi ve tutarlı biçimde denetleyin — asla client'a veya UI'ın bir şeyi gizlemesine güvenmeyin. En az yetki ilkesini uygulayın: her bileşen yalnızca işini yapmaya yetecek kadar hak alsın. Object-level authorization uygulayın (kullanıcı gerçekten *bu* kaydın sahibi mi?). Sandboxing, ayrıcalık ayrımı (privilege separation) ve prosesleri düşük yetkiyle çalıştırma ile bir bileşenin ele geçirilmesinin etkisini sınırlayın. Güvenlik yamalarını güncel tutun; bellek güvenliği açıkları (memory safety) için mümkünse bellek-güvenli diller veya derleyici korumaları kullanın.

## Risk Değerlendirmesi ve Önceliklendirme

Tehditleri bulmak yeterli değildir; hangisiyle önce ilgileneceğinizi bilmeniz gerekir çünkü kaynaklar sınırlıdır. Risk, kabaca **etki (impact) × olasılık (likelihood)** ile ifade edilir. Yüksek etkili ama olasılığı düşük bir tehdit ile düşük etkili ama çok olası bir tehdit farklı önceliklendirilir.

Microsoft'un eski DREAD modeli (Damage, Reproducibility, Exploitability, Affected users, Discoverability) bir zamanlar yaygındı, ancak öznel puanlaması nedeniyle tutarsız sonuçlar verdiği için bugün gözden düşmüştür ve ben size sahte bir kesinlik önermemek adına puanlama ağırlıklarını uydurmam. Bugün daha yaygın ve savunulabilir yaklaşımlar şunlardır:

- **CVSS (Common Vulnerability Scoring System):** Bilinen zafiyetleri standart bir formülle 0–10 arası puanlar. Tehdit modellemede doğrudan zafiyet değil tehdit değerlendirdiğiniz için birebir uymayabilir ama etki boyutlandırmada faydalıdır.
- **Nitel risk matrisi:** Etki (düşük/orta/yüksek/kritik) ve olasılık (nadir/olası/muhtemel) eksenlerinde basit bir ızgara. Ekipler için hızlı ve iletişimi kolaydır.
- **Saldırgan maliyeti perspektifi:** "Bu saldırıyı gerçekleştirmek saldırgana ne kadar zaman, beceri ve kaynağa mal olur, karşılığında ne kazanır?" Bu ekonomik bakış, gerçekçi önceliklendirmenin özüdür.

Pratik öneri: her tehdide bir azaltma stratejisi bağlayın. Dört seçenek vardır: **mitigate** (azalt — kontrol ekle), **eliminate** (ortadan kaldır — özelliği/veriyi tamamen çıkar), **transfer** (aktar — sigortala veya üçüncü tarafa devret), **accept** (kabul et — bilinçli olarak riski üstlen ve belgele). "Accept" meşru bir seçimdir ama *bilinçli ve yazılı* olmalıdır; sessizce görmezden gelmek değildir.

## Tehdit Modelleme Sürecinin Dört Sorusu

Adam Shostack'in popülerleştirdiği çerçeve, sürecin özünü dört soruya indirger. Bu çerçeve STRIDE'ı da kapsayan pratik bir omurgadır:

1. **Neyin üzerinde çalışıyoruz?** — Sistemi modelle (DFD çiz, güven sınırlarını işaretle).
2. **Ne ters gidebilir?** — Tehditleri bul (her eleman ve her güven sınırı kesişimine STRIDE uygula).
3. **Bu konuda ne yapacağız?** — Azaltmaları belirle (mitigate/eliminate/transfer/accept).
4. **İşimizi iyi yaptık mı?** — Doğrula (azaltmalar uygulandı mı, model güncel mi, yeni tehditler doğdu mu).

Bu döngü tek seferlik değildir. Sistem değiştikçe (yeni özellik, yeni entegrasyon, yeni veri akışı) model de güncellenmelidir. Tehdit modelleme yaşayan bir belgedir, bir kerelik bir tören değildir.

## Yaygın Hatalar

**Tehdit modellemeyi çok geç yapmak.** En büyük değeri tasarım aşamasında verir. Kod yazıldıktan sonra bulunan bir mimari zafiyeti düzeltmek katbekat pahalıdır. "Önce yapalım sonra güvenliğe bakarız" yaklaşımı, güvenliği en pahalı olduğu ana erteler.

**DFD'yi aşırı detaylandırmak.** Her fonksiyon çağrısını çizmeye kalkmak modeli kullanılamaz ve bakımı imkânsız hale getirir. Amaç mimari haritadır, kaynak kod dökümü değil. Level 1 çoğu durumda yeterlidir.

**Güven sınırlarını atlamak veya yanlış çizmek.** Güven sınırları yoksa STRIDE havada kalır. En sık atlanan sınırlar: aynı ağ içindeki servisler arası (herkes "iç ağ güvenli" varsayar — yanlıştır), ve üçüncü parti kütüphane/servis entegrasyonları.

**STRIDE'ı mekanik bir kutu doldurma egzersizine indirgemek.** Her hücreye "yok" yazıp geçmek, güvenlik tiyatrosudur. Her "yok" bir gerekçe istemelidir: *neden* bu tehdit burada geçerli değil?

**Sadece dış saldırganı düşünmek.** Insider threat, ele geçirilmiş bir bağımlılık (supply chain), veya yanlışlıkla açığa çıkan bir sır da tehdittir. Güven sınırları içeriden gelen tehditleri de kapsamalıdır.

**Azaltmaları takip etmemek.** Tehdit bulup azaltma önerip sonra bunu bir yere bağlamamak. Bulunan her tehdit izlenebilir bir işe (ticket, backlog item) dönüşmeli, kapatılana kadar takip edilmelidir.

**Modeli güncel tutmamak.** İlk sürümde harika bir tehdit modeli yapıp sonra sistem beş kez değişirken modele hiç dokunmamak, modeli zamanla yalancı bir güvenlik hissi kaynağına çevirir.

## En İyi Pratikler

**Erken ve sık yapın.** Tehdit modellemeyi tasarım fazına ve her önemli mimari değişikliğe entegre edin. Küçük, sık modelleme oturumları büyük, seyrek olanlardan daha etkilidir.

**Doğru insanları toplayın.** Tehdit modelleme takım işidir: geliştirici (sistemi bilir), güvenlik uzmanı (saldırıyı bilir), ürün sahibi (neyin kritik olduğunu bilir). Farklı perspektifler kör noktaları kapatır. Salt güvenlik ekibinin tek başına yaptığı modelleme, sistemin gerçek işleyişini ıskalar.

**DFD'yi basit ve okunur tutun.** Beyaz tahta veya basit bir diyagram aracı yeterlidir. Model, ekibin ortak zihinsel haritası olmalı; kimsenin anlamadığı bir sanat eseri değil.

**STRIDE'ı bir düşünme rehberi olarak kullanın, dogma olarak değil.** Altı kategori aklınıza gelmeyen tehditleri hatırlatmak içindir. Bir tehdit iki kategoriye de giriyorsa takılmayın; önemli olan onu yakalamış olmanız.

**Güven sınırı kesişimlerine odaklanın.** Sınırlı zamanınız varsa, veri akışlarının güven sınırlarını kestiği noktalara STRIDE uygulayın. Risk yoğunluğu oradadır.

**Azaltmaları somut ve izlenebilir yapın.** "Güvenliği artır" bir azaltma değildir. "Bu endpoint'e sunucu tarafı object-level authorization ekle" bir azaltmadır. Her azaltmayı bir sorumluya ve bir takip kalemine bağlayın.

**Otomasyonla destekleyin ama ona teslim olmayın.** Tehdit modelleme araçları (kod veya diyagramdan otomatik tehdit üreten araçlar dahil) süreci hızlandırır, ancak insan muhakemesinin yerini tutmaz. Araçlar bilinen kalıpları yakalar; sistemin kendine özgü mantık hatalarını insan bulur.

**Sonuçları belgeleyin ve paylaşın.** Tehdit modelinin çıktısı yaşayan bir belge olmalı: bulunan tehditler, kararlar (özellikle "accept" edilenler ve gerekçeleri), açık kalan işler. Bu belge hem denetim (audit) hem de kurumsal hafıza için değerlidir.

## Özet

STRIDE, altı bilinen tehdit sınıfını (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) sistematik olarak gözden geçirmeye zorlayan bir tehdit sınıflandırma çerçevesidir; her sınıf bir güvenlik özelliğinin (authentication, integrity, non-repudiation, confidentiality, availability, authorization) karşıtıdır. Gerçek gücü, bir Data Flow Diagram (DFD) üzerinde — özellikle verinin güven sınırlarını (trust boundary) kestiği noktalarda — uygulandığında ortaya çıkar; çünkü tehditlerin ezici çoğunluğu bu güven geçişlerinde doğar. Etkili bir tehdit modelleme; erken yapılır, doğru insanları bir araya getirir, her tehdidi somut ve izlenebilir bir azaltmaya bağlar, riski etki ve olasılıkla önceliklendirir ve sistem değiştikçe güncellenen yaşayan bir belge olarak sürdürülür.
