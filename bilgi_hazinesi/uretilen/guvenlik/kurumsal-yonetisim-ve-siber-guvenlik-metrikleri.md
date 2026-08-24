# Kurumsal Yönetişim ve Siber Güvenlik Metrikleri

## Giriş: Neden "Governance" Teknikten Daha Az Değil?

Siber güvenlik dünyasında teknik derinlik -exploit yazmak, log analizi yapmak, ağ segmentasyonu tasarlamak- genellikle prestijli kabul edilir. Oysa GRC (Governance, Risk, Compliance) çatısının **G** ayağı, yani yönetişim, olgunlaşmış bir güvenlik programının gerçek belkemiğidir. Yönetim kuruluna raporlama, olgunluk modeli değerlendirmesi ve güvenlik yatırımının gerekçelendirilmesi, kıdemli bir güvenlik liderinin (CISO) gündelik işinin büyük kısmını oluşturur.

Bu makale, teknik olmayan bu katmanın nasıl çalıştığını, hangi mekanizmalarla işlediğini ve neden bir güvenlik programının başarısını doğrudan belirlediğini açıklar. Amaç, metrik "üretmek" değil; **doğru kararı tetikleyen** doğru metriği tasarlamaktır.

---

## Bölüm 1: Yönetim Kurulu Raporlama (Board Reporting)

### Tanım

Yönetim kurulu raporlaması, güvenlik programının durumunu, risklerini ve yatırım ihtiyaçlarını, **teknik olmayan** karar vericilerin (board members, executive committee) anlayacağı ve harekete geçebileceği bir dile çeviren iletişim disiplinidir.

### Kök Neden / Çalışma Mantığı

Yönetim kurulunun temel sorumluluğu **fiduciary duty** (özen yükümlülüğü) ve risk gözetimidir. 2020'lerden itibaren pek çok düzenleme (örneğin ABD'de SEC'in siber olay bildirim kuralları, AB'de NIS2 ve DORA) siber riski açıkça yönetim kurulu sorumluluğu haline getirdi. Yani board, artık "IT'nin işi" diyerek sorumluluktan kaçamaz.

Bu yüzden rapor, üç temel soruya cevap vermelidir:

1. **Ne kadar risk altındayız?** (Risk exposure)
2. **Bu risk kabul edilebilir mi?** (Risk appetite ile karşılaştırma)
3. **Yatırdığımız para işe yarıyor mu?** (Program etkinliği)

Kritik hata, teknik ekiplerin board'a "12.000 zararlı yazılım engellendi" gibi **vanity metric** (gösteriş metriği) sunmasıdır. Bu sayı board için anlamsızdır; ne bir karar tetikler ne de bir riski açıklar.

### İyi Bir Board Raporunun Yapısı

**Executive summary (yönetici özeti):** Bir sayfayı geçmeyen, kırmızı/sarı/yeşil durum, en kritik üç risk ve karar bekleyen konular.

**Risk-odaklı anlatı:** Metrikler tek başına değil, iş bağlamıyla sunulur. Örneğin "yama uygulama süremiz 45 günden 18 güne düştü" demek yerine "kritik açıkları kapatma süremiz, fidye yazılımı grubunun ortalama sömürü süresinin altına indi" demek çok daha güçlüdür.

**Trend gösterimi:** Board tek bir anlık fotoğraf değil, yön ister. İyileşiyor muyuz, kötüleşiyor muyuz?

**Peer benchmarking:** "Sektör ortalamasına göre neredeyiz?" sorusu board üyelerinin en sevdiği sorulardan biridir.

### Örnek

Zayıf sunum: *"Bu çeyrekte SIEM 4,2 milyon olay işledi, 380 alarm üretti."*

Güçlü sunum: *"Kritik varlıklarımıza yönelik saldırı tespit süremiz (MTTD) 6 saatten 40 dakikaya indi. Bu, bir saldırganın veri sızdırmaya başlamadan önce onu durdurma olasılığımızı önemli ölçüde artırıyor. Kalan boşluk, OT ağındaki görünürlük eksikliği; bunu kapatmak için X bütçe talep ediyoruz."*

### Yaygın Hatalar

- Teknik jargona boğmak (board üyeleri gözlerini kaçırır, güven kaybolur).
- Sadece kötü haber ya da sadece iyi haber vermek (dengesizlik güvenilirliği zedeler).
- Metrikleri bir karara bağlamamak. Her metrik "ne olmuş yani?" (so what?) testini geçmelidir.

---

## Bölüm 2: KRI ve KPI Tasarımı

### Tanım

- **KPI (Key Performance Indicator):** Bir sürecin ne kadar iyi çalıştığını ölçer. Geriye dönük ve performans odaklıdır. Örnek: "Kritik yamaların %95'i 14 gün içinde uygulandı."
- **KRI (Key Risk Indicator):** Gelecekteki bir risk seviyesinin **erken uyarı** göstergesidir. İleriye dönüktür. Örnek: "İnternete açık, yama uygulanmamış sistem sayısındaki artış."

Basit ayrım: KPI *"ne kadar iyi yaptık?"* der; KRI *"ne kadar tehlikedeyiz ve durum kötüleşiyor mu?"* der.

### Kök Neden / Çalışma Mantığı

KRI'lerin değeri, bir olay gerçekleşmeden önce risk seviyesindeki değişimi göstermeleridir. İyi bir KRI, bir eşiğe (threshold) bağlıdır ve bu eşik aşıldığında bir yönetim aksiyonunu tetikler. Eşiği olmayan bir KRI sadece bir sayıdır.

İyi bir metriğin taşıması gereken nitelikler:

- **Actionable (harekete geçirilebilir):** Değiştiğinde birinin bir şey yapması gerekir.
- **Measurable (ölçülebilir):** Tutarlı ve tekrarlanabilir şekilde toplanabilmeli.
- **Relevant (ilgili):** Gerçek bir iş riskiyle bağlantılı olmalı.
- **Time-bound (zaman sınırlı):** Bir zaman penceresine sahip olmalı.

### Yaygın ve Anlamlı Metrikler

- **MTTD (Mean Time To Detect):** Ortalama tespit süresi.
- **MTTR (Mean Time To Respond/Remediate):** Ortalama müdahale/giderme süresi.
- **Patch/remediation SLA uyumu:** Kritik açıkların hedef sürede kapatılma oranı.
- **Vulnerability aging:** Açık zafiyetlerin ne kadar süredir açık olduğu (yaşlanma).
- **Phishing simülasyonu tıklama oranı ve raporlama oranı.**
- **Kimlik hijyeni:** Dormant (atıl) hesap sayısı, MFA kapsama oranı, aşırı yetkili hesaplar.
- **Third-party risk:** Kritik tedarikçilerin risk değerlendirme kapsamı.

### Örnek: Bir KRI Eşik Tasarımı

*KRI: İnternete açık kritik sistemlerdeki, 30 günden uzun süredir açık olan "critical" seviye zafiyet sayısı.*

- Yeşil: 0-2
- Sarı: 3-5 (güvenlik ekibi eskalasyon yapar)
- Kırmızı: 6+ (CISO'ya ve risk komitesine anlık bildirim, acil düzeltme planı)

Bu tasarım, sayının kendisini bir **yönetim kararına** bağlar. KRI'nin amacı budur.

### Yaygın Hatalar

- **Ölçmesi kolay olanı ölçmek**, gerçekten önemli olanı değil. Alarm sayısı ölçmesi kolaydır ama risk hakkında az şey söyler.
- **Metrik enflasyonu:** 40 metrikli bir dashboard kimse tarafından okunmaz. Board için 5-8 anlamlı metrik yeterlidir.
- **Vanity metrics:** "Engellenen saldırı sayısı" gibi büyük ama karar üretmeyen sayılar.
- **Gaming (metriği kandırma):** Ekipler ölçülen şeyi optimize eder. Eğer sadece "kapatılan ticket sayısını" ölçerseniz, insanlar önemsiz ticket'ları kapatmaya yönelir. Metrikleri tasarlarken bu davranışsal etkiyi (Goodhart Yasası: bir ölçüm hedefe dönüşünce iyi bir ölçüm olmaktan çıkar) hesaba katın.

---

## Bölüm 3: Güvenlik Olgunluk Modelleri (CMMI / C2M2 / NIST CSF)

### Tanım

Olgunluk modelleri, bir organizasyonun güvenlik yeteneklerini yapısal, tekrarlanabilir ve karşılaştırılabilir şekilde değerlendiren çerçevelerdir. "İyi miyiz?" gibi öznel bir soruyu, ölçülebilir seviyelere dönüştürürler.

### Yaygın Modeller

**CMMI tabanlı olgunluk seviyeleri** (geniş kabul gören genel yapı):

1. **Initial / Ad-hoc:** Süreçler tanımsız, kişilere bağımlı, tepkisel.
2. **Managed / Repeatable:** Bazı süreçler tanımlı ve tekrarlanabilir.
3. **Defined:** Süreçler kurumsal olarak standartlaştırılmış ve dokümante edilmiş.
4. **Quantitatively Managed:** Süreçler metriklerle ölçülüyor ve yönetiliyor.
5. **Optimizing:** Sürekli iyileştirme, metriklere dayalı proaktif optimizasyon.

**C2M2 (Cybersecurity Capability Maturity Model):** ABD Enerji Bakanlığı (DOE) kaynaklı, özellikle kritik altyapı için tasarlanmış bir modeldir. Yetenek alanlarını (domain) MIL (Maturity Indicator Level) seviyelerinde -tipik olarak MIL0'dan MIL3'e- değerlendirir. Risk yönetimi, varlık yönetimi, olay müdahalesi gibi alanları kapsar.

**NIST CSF (Cybersecurity Framework):** Kesin olarak bir "olgunluk modeli" değildir; fonksiyonlar (Identify, Protect, Detect, Respond, Recover ve son sürümde eklenen Govern) etrafında organize bir çerçevedir. Uygulama tiers (Tier 1-4) bir olgunluk hissi verir ama asıl amacı öncelik ve profil belirlemektir.

### Kök Neden / Çalışma Mantığı

Olgunluk modelinin gerçek gücü **tek bir puan üretmek değil**, mevcut durum (current state) ile hedef durum (target state) arasındaki **boşluğu (gap)** görünür kılmaktır. Bu gap analizi, bütçe ve yol haritası tartışmalarının temelini oluşturur.

Kritik nüans: Her alanda 5. seviyeye ulaşmak **hedef değildir ve genellikle yanlıştır.** Bir düşük riskli alanda "Defined" seviyesi yeterliyken, kritik bir alanda "Quantitatively Managed" gerekebilir. Olgunluk hedefi, o alanın **risk profiliyle** orantılı olmalıdır. Aşırı olgunluk, kaynak israfıdır.

### Örnek

Bir bankanın olgunluk değerlendirmesi:

- Identity & Access Management: Seviye 4 (hedef 4) — yeterli.
- Third-Party Risk Management: Seviye 2 (hedef 4) — **gap: 2 seviye.**
- Incident Response: Seviye 3 (hedef 4) — küçük gap.

Bu tablo, board'a "parayı nereye koymamız gerektiğini" tek bakışta gösterir: Tedarikçi risk yönetimi.

### Değerlendirme Nasıl Yapılır (Tespit / Doğrulama)

- **Self-assessment yeterli değildir;** ekipler kendilerini olduğundan olgun görme eğilimindedir. Kanıta (evidence-based) dayalı değerlendirme şarttır: politika dokümanları, log örnekleri, süreç kayıtları, tatbikat sonuçları.
- **Bağımsız doğrulama:** İç denetim ya da dış değerlendirici, iddia edilen olgunluğu kanıtla test etmelidir.
- **Tekrarlanabilirlik:** Aynı model, yıldan yıla aynı yöntemle uygulanmalı ki trend anlamlı olsun.

### Yaygın Hatalar

- **"5. seviye her yerde iyidir"** yanılgısı. Olgunluk, riske orantılı olmalı.
- **Puanı hedefe dönüştürmek** (Goodhart Yasası tekrar). Ekip olgunluğu "artırmak" için gerçek güvenlik yerine dokümantasyon üretimine kaçabilir.
- **Kanıtsız öz-değerlendirme** ile şişirilmiş, gerçeği yansıtmayan olgunluk tabloları.

---

## Bölüm 4: Bütçe ve ROI Gerekçelendirme

### Tanım

Güvenlik yatırımının gerekçelendirilmesi, teknik ihtiyacı **finansal bir dile** çevirerek karar vericilerden kaynak almanın disiplinidir. Güvenlik doğrudan gelir üretmediği için, değerini "önlenen kayıp" ve "olası zarar azaltımı" üzerinden anlatmak gerekir.

### Kök Neden / Çalışma Mantığı

Klasik risk hesabı: **ALE (Annualized Loss Expectancy)**.

- **SLE (Single Loss Expectancy):** Tek bir olayın beklenen maliyeti = Varlık değeri × Exposure Factor (etki oranı).
- **ARO (Annualized Rate of Occurrence):** Olayın yıllık gerçekleşme sıklığı.
- **ALE = SLE × ARO.**

Bir kontrolün ROI'si (Return on Security Investment, ROSI) kabaca şöyle mantıklanır: Kontrol öncesi ALE ile kontrol sonrası ALE arasındaki fark (yani önlenen kayıp), kontrolün maliyetinden büyükse yatırım gerekçelidir.

Basitleştirilmiş ROSI mantığı:

*(Kontrolün önlediği yıllık beklenen kayıp − Kontrolün yıllık maliyeti) / Kontrolün yıllık maliyeti.*

### Kritik Dürüstlük Notu

Bu hesaplar **sahte kesinlik (false precision)** tuzağı taşır. ARO ve exposure factor genellikle tahminidir; nadir ama yıkıcı olayların (fidye yazılımı, büyük veri ihlali) sıklığını kesin bilmek mümkün değildir. Sayıları "kesin gerçek" gibi sunmak, deneyimli bir CFO tarafından hemen fark edilir ve güvenilirliği yok eder.

Bu yüzden olgun yaklaşım:

- **Aralık (range) kullanmak:** "3-8 milyon TL beklenen kayıp" demek, "5,4 milyon TL" demekten daha dürüst ve daha güvenilirdir.
- **FAIR (Factor Analysis of Information Risk)** gibi yöntemler, riski nokta değer yerine olasılık dağılımı (Monte Carlo simülasyonu ile) olarak modelleyerek bu belirsizliği açıkça yönetir. Bu, giderek tercih edilen yaklaşımdır.
- **Varsayımları şeffaf sunmak:** "Şu sıklığı şu kaynağa dayanarak varsaydık" demek, sayının kendisinden daha değerlidir.

### Gerekçelendirme Argümanının Türleri

1. **Risk azaltımı (loss avoidance):** En yaygın ama en zor kanıtlanan argüman.
2. **Uyumluluk / regülasyon zorunluluğu:** "Bu kontrol olmadan KVKK/GDPR/DORA cezası riski var." Board bu argümana genellikle daha hızlı yanıt verir çünkü ceza somuttur.
3. **Operasyonel verimlilik:** Otomasyon ile insan-saat tasarrufu; bu somut ve ölçülebilir bir tasarruftur.
4. **İş etkinleştirme (business enablement):** "Bu güvenlik yatırımı olmadan şu yeni pazara/müşteriye giremeyiz." Güvenliği maliyet değil, gelir etkinleştirici olarak konumlandırmak en güçlü çerçevedir.

### Örnek

Zayıf gerekçe: *"EDR çözümüne ihtiyacımız var çünkü tehditler artıyor."*

Güçlü gerekçe: *"Sektörümüzde fidye yazılımı olayının olası yıllık maliyeti (iş durması + kurtarma + itibar) 5-15 milyon TL aralığında tahmin ediliyor. EDR yatırımı yıllık 1,2 milyon TL. Bu kontrolün olay olasılığını önemli ölçüde düşürdüğüne dair sektör kanıtı var. Ayrıca siber sigorta poliçemiz bu kontrolü şart koşuyor; olmadan primimiz artıyor veya teminat düşüyor."*

Son cümle -sigorta bağlantısı- çoğu zaman en ikna edici olandır çünkü doğrudan, ölçülebilir bir finansal etki içerir.

### Yaygın Hatalar

- **FUD (Fear, Uncertainty, Doubt) ile satış yapmak.** Korku kısa vadede işe yarar ama tekrarlandıkça güvenilirliği aşındırır ("kurt geldi" sendromu).
- **Sahte kesinlik** ile şişirilmiş ROI rakamları sunmak.
- **Yatırımı iş sonucuna bağlamamak.** Board para değil, sonuç satın alır.
- **Sadece ilk maliyeti (CapEx) göstermek**, işletme maliyetini (OpEx: lisans yenileme, personel, eğitim) gizlemek. Toplam sahip olma maliyeti (TCO) dürüstçe sunulmalı.

---

## Bölüm 5: Bütünsel Bakış — Metrikleri Bir Yönetişim Döngüsüne Bağlamak

Bu dört alan izole değildir; bir döngü oluşturur:

1. **Olgunluk modeli** mevcut durumu ve gap'i belirler.
2. **KRI/KPI'ler** bu gap'lerin nasıl değiştiğini sürekli ölçer.
3. **Bütçe/ROI gerekçesi**, gap'i kapatmak için kaynak alır.
4. **Board raporu**, tüm bunları karar vericilere sunar ve döngüyü kapatır.

Bu döngünün kalbindeki ilke: **Her metrik bir karara hizmet etmelidir.** Karar tetiklemeyen metrik gürültüdür.

### Savunma Perspektifi: Yönetişim Bir Güvenlik Kontrolüdür

Yönetişim "kağıt işi" gibi görünse de doğrudan savunma etkisi vardır:

- **Risk appetite tanımı**, ekiplerin hangi riski kabul edip hangisini gidereceğini netleştirir; belirsizlik saldırganın en sevdiği ortamdır.
- **Metrik trendleri**, bir kontrolün sessizce bozulduğunu (örneğin MFA kapsamının düşmesi) erken yakalar.
- **Olgunluk gap analizi**, saldırganın hedefleyeceği zayıf alanları savunmadan önce görünür kılar.
- **Bütçe gerekçesi**, savunmanın sürdürülebilir finansmanını garanti eder; kaynağı olmayan bir güvenlik programı zamanla çürür.

---

## Sonuç

GRC'nin governance ayağı, teknik güvenliğin "daha az önemli" bir tamamlayıcısı değil, onu yönlendiren ve finanse eden yönetim katmanıdır. İyi bir güvenlik lideri, bir zafiyeti kapatmayı bildiği kadar, o zafiyetin neden kapatılması gerektiğini board'a **karar üretecek** bir dille anlatabilmelidir.

Bu makalenin taşıdığı üç temel ilke:

1. **Her metrik "ne olmuş yani?" testini geçmeli** ve bir karara bağlanmalı.
2. **Olgunluk ve risk hedefleri, riske orantılı olmalı;** her yerde maksimum olgunluk israftır.
3. **Finansal gerekçelendirmede dürüstlük** -aralık, varsayım şeffaflığı, sahte kesinlikten kaçınma- uzun vadeli güvenilirliğin temelidir.

Sayılar kolaydır; **doğru sayıyı doğru karara bağlamak** uzmanlıktır.
