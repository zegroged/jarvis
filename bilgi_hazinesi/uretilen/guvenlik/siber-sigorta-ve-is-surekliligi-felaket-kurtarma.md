# Siber Sigorta ve İş Sürekliliği / Felaket Kurtarma

## Giriş ve Kapsam

Incident Response (olay müdahalesi), bir siber olayın *anında* nasıl tespit edilip kontrol altına alınacağını anlatır. Ancak bir kurumun bir fidye yazılımı (ransomware) saldırısı, veri merkezi yangını veya tedarikçi kesintisi karşısında **ayakta kalıp kalamayacağını** belirleyen şey, olayın öncesinde kurulan yönetimsel süreçlerdir. Bu makale, GRC'nin (Governance, Risk, Compliance) yönetimsel tarafında yer alan dört bileşeni ele alır:

- **BCP/DRP** — İş Sürekliliği Planı ve Felaket Kurtarma Planı
- **RTO/RPO** — Kurtarma hedeflerinin hesaplanması ve anlamı
- **Siber Sigorta** — Poliçe kapsamı, istisnalar ve değerlendirme mantığı
- **Tabletop egzersizleri** — Planların masabaşı simülasyonla test edilmesi

Bu konular teknik değil, **süreç ve karar** odaklıdır; ama teknik ekibin ürettiği verilere (sistem envanteri, bağımlılık haritası, yedekleme metrikleri) doğrudan dayanır.

---

## 1. İş Sürekliliği (BCP) ve Felaket Kurtarma (DRP)

### Tanım

**Business Continuity Plan (BCP)**, bir kesinti anında kurumun **kritik iş fonksiyonlarını** (kritik business functions) sürdürmesini veya kabul edilebilir bir seviyede devam ettirmesini sağlayan üst düzey plandır. Odak *iştir*: müşteri siparişleri alınabiliyor mu, maaşlar ödenebiliyor mu, üretim durdu mu?

**Disaster Recovery Plan (DRP)**, BCP'nin **teknik alt kümesidir**. Odak *sistemlerdir*: sunucular, veritabanları, ağ, uygulamalar felaket sonrası nasıl geri getirilir?

Basit bir ayrım: BCP "İşi nasıl yürütmeye devam ederiz?" sorusunu, DRP "BT sistemlerini nasıl geri yükleriz?" sorusunu yanıtlar. DRP olmadan BCP havada kalır; BCP olmadan DRP ise iş önceliklerinden kopuk teknik bir liste olur.

### Kök Mantık: Neden İkisi Ayrı?

Bir kurum, tüm sistemlerini aynı anda geri yükleyemez — kaynak (personel, bant genişliği, lisans, zaman) sınırlıdır. Bu yüzden **hangi sistem önce** sorusu kritik hale gelir. Bu önceliklendirme iş tarafından (BCP) yapılır, teknik ekip (DRP) sırayı uygular. İş etki analizi olmadan yapılan bir DR planı, en kritik uygulamayı en sona bırakabilir.

### Business Impact Analysis (BIA)

BCP/DRP'nin temelinde **Business Impact Analysis (BIA)** yatar. BIA şu soruları sistematik olarak yanıtlar:

- Kurumun hangi süreçleri kritik? (örneğin ödeme sistemi, sipariş yönetimi)
- Bu süreç durursa saatte/günde ne kadar zarar (mali, itibar, yasal) oluşur?
- Bu süreç hangi BT sistemlerine ve dış tedarikçilere bağımlı?
- Maksimum ne kadar süre durabilir? (bu, RTO'yu belirler)

BIA çıktısı bir **kritiklik sıralaması** ve **bağımlılık haritasıdır** (dependency map). Örneğin bir e-ticaret firmasında sipariş servisi ödeme ağ geçidine, o da kimlik doğrulama servisine bağımlıysa; kimlik doğrulama servisi kurtarılmadan sipariş servisini geri getirmek anlamsızdır. Bu bağımlılık zinciri kurtarma sırasını dikte eder.

---

## 2. RTO ve RPO — Kurtarma Hedefleri

Bu iki metrik, tüm DR planlamasının **sayısal çekirdeğidir**. Karıştırılmaları çok yaygın bir hatadır.

### RTO — Recovery Time Objective

**RTO (Kurtarma Süresi Hedefi)**: Bir sistemin/sürecin kesinti anından itibaren **ne kadar sürede** yeniden çalışır hale getirilmesi gerektiğinin üst sınırıdır. "Ne kadar süre kapalı kalabiliriz?" sorusunun cevabıdır.

Örnek: Ödeme sistemi için RTO = 2 saat ise, felaketten sonra en geç 2 saat içinde ödemeler yeniden alınabilmelidir.

### RPO — Recovery Point Objective

**RPO (Kurtarma Noktası Hedefi)**: Kabul edilebilir **maksimum veri kaybının** zaman cinsinden ifadesidir. "Ne kadar veriyi kaybetmeyi göze alabiliriz?" sorusunun cevabıdır ve doğrudan **yedekleme sıklığını** belirler.

Örnek: Bir veritabanı için RPO = 15 dakika ise, en fazla 15 dakikalık veri kaybı tolere edilebilir; dolayısıyla yedekleme/replikasyon en az 15 dakikada bir çalışmalıdır.

### İki Metriğin Görsel Ayrımı

```
        <-- RPO -->        FELAKET        <-- RTO -->
 ...----[son yedek]-----------[X]-------------[geri geldi]---->
         (veri kaybı penceresi)   (kesinti süresi)   zaman
```

- **RPO geriye bakar**: felaket anıyla son geçerli yedek arasındaki mesafe → kaybedilen veri.
- **RTO ileriye bakar**: felaket anıyla sistemin geri gelmesi arasındaki mesafe → kesinti süresi.

### RTO/RPO Nasıl "Hesaplanır"?

Bu değerler mühendislik tarafından değil, **iş tarafından** belirlenir; teknik ekip sadece bunların **maliyetini** söyler. Süreç şöyledir:

1. **BIA'dan kesinti maliyetini al**: Süreç saatte X TL kaybettiriyor.
2. **Kabul edilebilir kayıp eşiğini belirle**: Yönetim "en fazla Y TL kayba katlanırız" der. Bu, RTO'yu belirler (Y / X = kabul edilebilir saat).
3. **Teknik maliyetle dengele**: RTO'yu 5 dakikaya çekmek, sıcak yedek (hot site) ve gerçek zamanlı replikasyon gerektirir; bu çok pahalıdır. RTO'yu 24 saate uzatmak ucuzdur ama iş kaybı artar. Optimum nokta, **kesinti maliyeti** ile **kurtarma altyapısı maliyetinin** kesiştiği yerdir.

Bu bir **maliyet-optimizasyon** problemidir: agresif (düşük) RTO/RPO pahalı altyapı ister; gevşek (yüksek) RTO/RPO ucuzdur ama olay anında büyük kayıp riski taşır.

### Kurtarma Stratejisi Seçenekleri (Site Tipleri)

RTO ne kadar kısaysa, altyapı o kadar "sıcak" olmalıdır:

- **Cold site**: Sadece boş altyapı (mekân, güç). Sistemler sıfırdan kurulur. RTO: günler. Ucuz.
- **Warm site**: Donanım hazır, veriler periyodik yüklenir. RTO: saatler.
- **Hot site**: Sistemler çalışır ve senkron/asenkron replike halde. RTO: dakikalar. Pahalı.
- **Active-active**: İki site de eşzamanlı çalışır; biri düşerse diğeri yükü alır. RTO ~ sıfıra yakın. En pahalı.

Yaygın bir modern yaklaşım, bulut tabanlı DR'dir (örneğin farklı bir bölge/region'a replikasyon), böylece "sıcak" bir siteyi sürekli çalıştırmanın maliyeti düşürülür.

---

## 3. Siber Sigorta — Poliçe Kapsamı ve İstisnalar

### Tanım ve Amaç

**Cyber insurance (siber sigorta)**, bir siber olayın mali sonuçlarının bir kısmını sigortacıya devreden bir **risk transfer** aracıdır. Risk yönetiminin dört ana stratejisinden birini temsil eder: *azaltma* (kontrol kur), *kabul etme*, *kaçınma* ve **transfer** (sigorta). Sigorta, riski ortadan kaldırmaz; olayın *mali etkisini* paylaşır.

Kritik ilke: **Sigorta bir kontrol değildir.** Fidye yazılımını engellemez; sadece olduğunda maliyetin bir kısmını karşılar. Sigortaya güvenip savunmayı ihmal etmek, hem bir güvenlik hatası hem de çoğu zaman poliçenin kendisini geçersiz kılan bir davranıştır.

### Tipik Kapsam Kalemleri

Siber poliçeler genelde iki büyük kategoriye ayrılır:

**First-party (kendi zararlarınız):**
- Olay müdahale ve adli bilişim (forensics) masrafları
- İş kesintisi kaybı (business interruption) — gelir kaybının telafisi
- Veri kurtarma / sistem yeniden inşa maliyeti
- Fidye ödemesi (bazı poliçelerde, yasal sınırlar dahilinde)
- Kriz iletişimi / halkla ilişkiler

**Third-party (üçüncü taraflara verilen zararlar):**
- Veri ihlali sonrası müşteri bildirimleri ve kredi izleme
- Regülasyon cezaları (kapsandığı ölçüde)
- Dava masrafları ve tazminatlar

### İstisnalar — Poliçenin En Kritik Kısmı

Bir siber poliçenin *gerçek değeri* kapsamında değil, **exclusions (istisnalar)** bölümündedir. Sık görülen istisnalar:

- **Bilinen açıkların yamalanmaması**: Sigortalı, yaması yayınlanmış bir açığı makul sürede kapatmadıysa, o açıktan kaynaklı olay reddedilebilir.
- **Temel güvenlik kontrollerinin eksikliği**: Poliçe başvurusunda "MFA kullanıyoruz", "yedekler offline tutuluyor" gibi beyanlar verilir. Bu beyan gerçeği yansıtmıyorsa, olay anında **yanlış beyan (misrepresentation)** gerekçesiyle tazminat reddedilebilir.
- **War / hostile act (savaş/düşmanca eylem)**: Devlet destekli (nation-state) saldırılar tartışmalı bir dışlama alanıdır. NotPetya sonrası açılan davalarda bu maddenin kapsamı ciddi biçimde tartışılmış, poliçe dilinin netliği belirleyici olmuştur.
- **Geç bildirim**: Olayın poliçede belirtilen süre içinde sigortacıya bildirilmemesi.
- **Önceden var olan / bilinen olaylar**: Poliçe başlamadan önce başlamış olan olaylar.

### Poliçe Değerlendirme Mantığı

Bir siber poliçeyi değerlendirirken bakılması gereken temel eksenler:

- **Coverage limits**: Toplam ve kalem bazında üst sınırlar. Olayın gerçek maliyetini karşılıyor mu?
- **Sublimits**: Belirli kalemler (örneğin fidye, sosyal mühendislik dolandırıcılığı) için ayrı ve genellikle daha düşük alt limitler.
- **Deductible / retention**: Sigortalının kendi cebinden ödeyeceği ilk dilim.
- **Waiting period**: İş kesintisi kaybının ne kadar süre sonra ödenmeye başlayacağı (örneğin ilk 8-12 saat karşılanmaz).
- **İstisnalar ile mevcut kontrol durumunun uyumu**: Poliçenin varsaydığı kontroller kurumda gerçekten var mı?

Modern sigortacılar poliçe öncesi bir **güvenlik olgunluk değerlendirmesi** yapar; MFA, EDR, offline yedek, ağ segmentasyonu gibi kontroller giderek **ön koşul** haline gelmiştir. Bu, sigortayı savunma yatırımını teşvik eden bir mekanizmaya dönüştürmüştür.

---

## 4. Tabletop Egzersizleri

### Tanım

**Tabletop exercise (masabaşı tatbikatı)**, gerçek sistemlere dokunmadan, ilgili paydaşların bir toplantı masasında **kurgusal bir senaryoyu** adım adım tartıştığı bir plan testidir. Amaç, BCP/DRP/IR planlarının kâğıt üzerinde değil, **karar verme pratiğinde** ne kadar işlediğini görmektir.

### Neden Gerekli?

Yazılı bir plan, ancak insanlar onu baskı altında uygulayabildiğinde değerlidir. Tabletop'un ortaya çıkardığı tipik boşluklar:

- **Karar yetkisi belirsizliği**: "Fidye ödenecek mi?" kararını kim verir? CEO ulaşılamazsa yerine kim geçer?
- **İletişim kopuklukları**: E-posta ve telefon sistemleri de çöktüyse ekip nasıl haberleşecek? (out-of-band iletişim)
- **Bağımlılık sürprizleri**: "DR planımız yedekten geri dönmeye dayanıyordu, ama yedek sunucunun şifresi de şifrelenen Active Directory'de tutuluyormuş."
- **Rol çakışması**: İki kişi aynı işi yapmaya çalışırken kritik bir görev sahipsiz kalır.

### İyi Bir Tabletop'un Yapısı

1. **Senaryo tasarımı**: Gerçekçi ve kuruma özel (örneğin "Muhasebe biriminde bir kullanıcı oltalama e-postasına tıkladı, fidye yazılımı dosya sunucusuna yayıldı").
2. **Injects (enjeksiyonlar)**: Senaryo ilerledikçe eklenen sürprizler ("Basın olayı öğrendi ve arıyor", "Saldırgan çalınan veriyi sızdırmakla tehdit ediyor").
3. **Katılımcılar**: Sadece BT değil; hukuk, iletişim/PR, üst yönetim, İK ve gerekirse dış danışmanlar.
4. **Kolaylaştırıcı (facilitator)**: Senaryoyu yürütür, tarafsız kalır, kararları not eder.
5. **After-action report**: Egzersiz sonrası bulguları, boşlukları ve düzeltme aksiyonlarını içeren rapor. Bu rapor olmadan egzersiz sadece bir sohbete dönüşür.

### Egzersiz Türleri Spektrumu

- **Tabletop**: Tartışmaya dayalı, en düşük risk ve maliyet.
- **Walkthrough / drill**: Belirli bir prosedürün fiilen adım adım uygulanması.
- **Functional / full-scale**: Gerçek sistemlerde failover testi, ki bu iş kesintisi riski taşıdığı için planlı ve kontrollü yapılır.

Olgun kurumlar tabletop'tan başlayıp giderek daha gerçekçi testlere doğru ilerler.

---

## Tespit, İzleme ve Doğrulama

Bu konu "savunma kurma" değil, **hazırlığın doğrulanması** üzerinedir. İzlenmesi gereken sinyaller:

- **Yedeklerin geri yüklenebilirliği**: Yedek almak yeterli değildir; düzenli **restore testi** yapılmalıdır. "Yedeklerimiz var" diyen çok kurum, felaket anında yedeğin bozuk veya eksik olduğunu görür. Ölçülecek metrik: son başarılı restore testinin tarihi.
- **RTO/RPO uyum ölçümü**: Gerçek bir test/olayda ulaşılan gerçek kurtarma süresi (actual RTO), hedeflenen RTO'yu aşıyor mu? Aşıyorsa plan gerçekçi değildir.
- **Offline / immutable yedek doğrulaması**: Fidye yazılımlarının ilk hedefi yedeklerdir. Yedeklerin ağdan izole (air-gapped) veya değiştirilemez (immutable) olduğu doğrulanmalıdır.
- **Bağımlılık kayması (drift)**: BIA'daki bağımlılık haritası altı ay önce yapıldıysa ve o zamandan beri yeni servisler eklendiyse, plan güncelliğini yitirmiştir.
- **Poliçe-kontrol uyum kontrolü**: Sigorta başvurusunda beyan edilen kontroller (MFA, EDR vb.) hâlâ tüm sistemlerde aktif mi? Bir istisna kaldırılmışsa poliçe riske girer.

---

## Savunma ve İyi Uygulamalar

- **3-2-1 yedekleme kuralı**: 3 kopya, 2 farklı ortam, 1 tanesi tesis dışında (offline/immutable eklemesiyle "3-2-1-1-0" varyantı yaygınlaşmıştır).
- **RTO/RPO'yu iş ile birlikte belirle**: Teknik ekip tek başına karar veremez; kesinti maliyetini bilen iş birimleri masada olmalı.
- **DR planını erişilebilir tut**: Plan yalnızca kurumsal ağdaki bir wiki'de duruyorsa, ağ çökünce plana ulaşılamaz. Basılı/çevrimdışı kopya ve out-of-band iletişim listesi bulundurulmalı.
- **Runbook'ları güncel tut**: Adım adım kurtarma prosedürleri, sistem değiştikçe güncellenmeli.
- **Sigortayı savunma stratejisinin tamamlayıcısı olarak konumla**: Transfer, azaltmanın (kontrol) yerini almaz.
- **Düzenli tatbikat takvimi**: En az yılda bir tabletop; kritik sistemler için daha sık.

---

## Yaygın Hatalar

- **RTO ile RPO'yu karıştırmak**: En sık hata. RTO = süre (downtime), RPO = veri (kayıp). İkisi bağımsızdır; bir sistemin RTO'su kısa ama RPO'su uzun olabilir (hızlı ayağa kalkar ama son bir günün verisi gitmiştir).
- **Yedek almak = kurtarma sanmak**: Restore testi yapılmayan yedek, olmayan yedektir.
- **Sigortayı kontrol yerine koymak**: Poliçe fidye yazılımını engellemez ve çoğu istisna, savunma zaafiyetinizi zaten cezalandırır.
- **İstisnaları okumamak**: Poliçenin değeri istisnalarında saklıdır; kapsam başlığına bakıp geçmek büyük bir risktir.
- **Poliçe başvurusunda abartılı beyan**: "MFA her yerde var" deyip olmaması, olay anında tazminatın reddine yol açar.
- **BIA'sız DR planı**: Neyin önce kurtarılacağı iş etkisine göre değil, teknik ekibin sezgisine göre belirlenir ve genelde yanlış çıkar.
- **Bağımlılıkları göz ardı etmek**: Kurtarma sırasında "bu servisin ayakta olması için önce şu servis lazımmış" sürprizi, tabletop yapılmadıysa gerçek olayda ortaya çıkar.
- **Tabletop'u sadece BT ile yapmak**: Hukuk, PR ve üst yönetim masada olmazsa, gerçek olaydaki en yavaş kararlar (fidye ödeme, kamuya açıklama) hiç prova edilmemiş olur.
- **After-action raporu yazmamak**: Bulgular aksiyona dönüşmezse egzersiz zaman kaybıdır.

---

## Özet

Incident Response bir olayın *anlık* teknik müdahalesidir; bu makalenin konusu ise olayın *öncesinde* kurulan yönetimsel dayanıklılıktır. BCP işi, DRP sistemleri ayakta tutar; ikisinin de temeli BIA'dır. RTO kesinti süresini, RPO veri kaybını sınırlar ve bunlar iş maliyeti ile altyapı maliyeti arasında bir denge olarak *hesaplanır*. Siber sigorta riski transfer eder ama kontrolün yerini almaz — asıl değeri istisnalarında gizlidir. Tabletop egzersizleri ise tüm bu planların kâğıt üzerinde değil, baskı altında karar verme pratiğinde işlediğini kanıtlayan tek gerçekçi yöntemdir. Bu bileşenler birlikte, bir kurumun siber felaket karşısında sadece *müdahale etmesini* değil, **hayatta kalmasını** sağlar.
