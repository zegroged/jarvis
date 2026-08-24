# Gizlilik Mühendisliği (Privacy Engineering)

## Giriş ve Kapsam

Gizlilik mühendisliği, kişisel verinin bir sistem içinde nasıl toplandığını, işlendiğini, saklandığını ve imha edildiğini **teknik kontrollerle** güvence altına alan disiplindir. KVKK ve GDPR gibi düzenlemeler *ne yapılması gerektiğini* söyler; gizlilik mühendisliği *bunun mimaride nasıl gerçekleştirileceğini* çözer. GRC (Governance, Risk, Compliance) tarafındaki hukuki uyum ile SRE/AppSec tarafındaki teknik uygulama arasında köprü kuran bu alan; k-anonymity, differential privacy, veri minimizasyonu ve DPIA gibi somut mekanizmalara dayanır.

Bu makale kavramları, çalışma mantığını, tipik hataları ve savunma/tespit yaklaşımlarını açıklar. Amaç, "hukukçu uyumluluk maddesi işaretledi" seviyesinden, "mühendis re-identification saldırısını modelledi ve kontrolü ölçtü" seviyesine çıkmaktır.

## Privacy by Design (PbD) ve Privacy by Default

### Tanım

Privacy by Design, gizliliğin sistem yaşam döngüsünün başından itibaren mimariye gömülmesidir; sonradan eklenen bir yama değildir. GDPR Madde 25 bunu "data protection by design and by default" olarak yasal zorunluluk haline getirir. Ann Cavoukian'ın klasik yedi ilkesi (proaktif olma, varsayılan gizlilik, tasarıma gömülü olma, tam işlevsellik/pozitif toplam, uçtan uca güvenlik, görünürlük/şeffaflık, kullanıcı mahremiyetine saygı) kavramsal çerçeveyi verir; ancak bu ilkeler mühendislik açısından fazla soyuttur.

### Çalışma Mantığı ve Somut Karşılıkları

Pratikte PbD, mühendislik kararlarına şu şekilde tercüme edilir:

- **Data minimization**: Bir formda doğum tarihi yerine yalnızca "18 yaş üstü mü?" boolean'ı toplamak. Alanı hiç toplamamak, en güçlü kontroldür; toplanmayan veri sızmaz.
- **Purpose limitation**: Pazarlama için toplanan e-postanın fraud skorlama modeline beslenmemesi. Bu, veri tabanı şeması ve erişim politikalarıyla teknik olarak zorlanmalıdır (ör. ayrı schema, ayrı erişim rolleri).
- **Privacy by default**: Kullanıcı hiçbir ayara dokunmadan en gizli seçenekte olmalıdır. Profil "public" değil "private" başlamalı; opt-out değil opt-in tercih edilmelidir.
- **Storage limitation**: Verinin süresiz saklanmaması; retention süresi bitince otomatik silinmesi.

### Yaygın Hatalar

- Gizliliği ürünün sonuna, "compliance review" aşamasına bırakmak. Bu noktada mimari değişiklik pahalıdır ve genellikle kozmetik kontrollerle geçiştirilir.
- "Anonim topluyoruz" demek ama IP, device fingerprint, timestamp gibi quasi-identifier'ları da tutmak. Bunların birleşimi çoğu zaman kimliği geri getirir.
- Consent'i tek bir dev checkbox'a indirgeyip purpose limitation'ı ihlal etmek.

## PII Sınıflandırma ve Veri Haritalama (Data Mapping)

### Tanım

Bir kontrolü uygulamadan önce **neyin, nerede olduğunu** bilmek gerekir. Data mapping (veri haritalama), kişisel verinin sisteme giriş noktalarını, aktığı yolları (data flow), saklandığı depoları ve dışa aktarıldığı üçüncü tarafları envanterleyen çalışmadır. GDPR Madde 30 "records of processing activities" (RoPA) olarak bunun belgelenmesini ister.

### Veri Kategorileri

Sınıflandırma tipik olarak hassasiyet katmanlarına ayrılır:

- **PII (Personally Identifiable Information)**: Ad, e-posta, telefon, adres.
- **Direct identifiers**: Tek başına kimliği veren alanlar (TC kimlik no, pasaport no).
- **Quasi-identifiers**: Tek başına yetmeyen ama birleşince kimliği açan alanlar (posta kodu + doğum tarihi + cinsiyet). Latanya Sweeney'nin klasik çalışması, ABD nüfusunun büyük çoğunluğunun sadece bu üçlüyle tekilleştirilebildiğini göstermiştir.
- **Special category / hassas veri**: Sağlık, biyometrik, genetik, din, siyasi görüş, cinsel yönelim. KVKK'da "özel nitelikli kişisel veri" olarak ayrı ve daha ağır korunur.

### Çalışma Mantığı

Modern ortamda haritalama iki yaklaşımla yapılır:

1. **Data discovery / scanning**: Veri tabanları, object storage (S3 bucket'ları), log dosyaları ve data lake'ler otomatik taranır. Regex ve pattern kütüphaneleri (kredi kartı için Luhn kontrolü, e-posta, telefon formatları) ile birlikte ML tabanlı NER (Named Entity Recognition) sınıflandırıcılar kullanılır. Cloud tarafında bu işi yapan yönetilen servisler (ör. AWS Macie, Google DLP) yaygındır.
2. **Data lineage / flow tracking**: Verinin hangi servisten hangi servise, hangi API üzerinden aktığını izleyen tag/tainting yaklaşımları.

### Tespit ve Savunma

- **Tespit**: Beklenmedik yerlerde PII bulmak en değerli sinyaldir. Debug log'una yazılan tam kredi kartı numarası, error stack trace'e düşen session token, analytics event'ine giren e-posta. DLP taramaları düzenli (nightly) çalıştırılıp yeni bulgular alarm üretmelidir.
- **Savunma**: Her veri deposuna sensitivity tag'i atamak; erişim politikalarını bu tag'lere bağlamak (attribute-based access control). Yeni bir sütun eklendiğinde sınıflandırılmasını zorunlu kılan bir schema governance süreci.

### Yaygın Hatalar

- Haritayı bir kez çıkarıp güncellememek. Envanter, kod deploy hızında eskir. Haritalama, CI/CD'ye entegre sürekli bir süreç olmalıdır.
- Yapılandırılmamış veriyi (serbest metin alanları, destek biletleri, çağrı kayıtları) atlamak. Kullanıcı "yorum" kutusuna TC kimlik numarasını yazar ve bu hiçbir şemada görünmez.

## Anonimleştirme ve Pseudonymization Teknikleri

Bu ikisi sık karıştırılır ama hukuki ve teknik olarak çok farklıdır.

### Pseudonymization (Takma Adlandırma)

**Tanım**: Doğrudan tanımlayıcıyı, ayrı tutulan bir eşleştirme anahtarı (mapping/key) ile geri döndürülebilir bir token'a çevirmek. Örnek: `mert@x.com` yerine `user_8f3a...` kullanmak, gerçek eşleşmeyi ayrı ve sıkı korunan bir tabloda tutmak.

**Kritik nokta**: Pseudonymized veri **hâlâ kişisel veridir**. Anahtara erişimi olan biri kimliği geri getirebilir. GDPR bunu bir güvenlik önlemi olarak teşvik eder (Madde 32) ama anonimleştirme saymaz; yani düzenleme kapsamından çıkarmaz.

**Teknikler**:
- **Tokenization**: Değeri anlamsız bir token ile değiştirme, orijinali güvenli bir vault'ta saklama.
- **Deterministic vs. randomized**: Deterministik pseudonymization aynı girdiye hep aynı çıktıyı verir (join yapılabilir ama frekans analizine açıktır); randomized daha güvenli ama analitik faydası düşük.
- **HMAC ile hashing**: Basit `SHA-256(email)` **yeterli değildir**; e-posta uzayı küçük ve tahmin edilebilir olduğundan brute-force ve rainbow table ile kolayca kırılır. Gizli bir salt/key ile `HMAC` kullanmak ve anahtarı korumak gerekir.

### Anonymization (Anonimleştirme)

**Tanım**: Verinin, makul hiçbir yöntemle kimliğe geri bağlanamayacağı hale getirilmesi. Gerçekten anonimleştirilmiş veri düzenleme kapsamı dışına çıkar. Ancak **gerçek anonimleştirme zordur** ve çoğu "anonim" veri kümesi aslında pseudonymized'dır.

#### k-anonymity

Bir veri kümesinin **k-anonymous** olması, quasi-identifier kombinasyonu bakımından her kaydın en az `k-1` başka kayıtla ayırt edilemez olması demektir. Yani her "equivalence class"ta en az `k` kişi bulunur.

Sağlayan teknikler:
- **Generalization**: "34 yaş" → "30-40 yaş", tam posta kodu → ilk üç hane.
- **Suppression**: Nadir, tekilleştiren kayıtların tamamen çıkarılması.

**Zaafları**:
- **Homogeneity attack**: Bir equivalence class'taki `k` kişinin hepsinin hassas değeri aynıysa (hepsi aynı hastalığa sahipse), grubu bilmek yeter, tekil kişiyi bulmaya gerek yok. Buna karşı **l-diversity** (her grupta en az `l` farklı hassas değer) geliştirildi.
- **Background knowledge / skewness attack**: Saldırganın harici bilgisi grubu daraltabilir. Buna karşı **t-closeness** (grup içi hassas değer dağılımının, genel dağılıma yakın olması) önerildi.

#### Differential Privacy (DP)

**Tanım**: k-anonymity kümenin yapısına dayanırken, differential privacy **matematiksel bir garantidir**. DP, bir sorgunun/algoritmanın çıktısının, tek bir bireyin veri kümesinde olması ile olmaması arasında istatistiksel olarak ayırt edilememesini garanti eder. Formel olarak, bir mekanizmanın çıktı dağılımı, komşu (bir birey farklı) veri kümeleri için `e^ε` faktöründen daha fazla değişmemelidir. Buradaki **ε (epsilon)** "privacy budget"tir: küçük ε = güçlü gizlilik + gürültülü/az faydalı sonuç; büyük ε = zayıf gizlilik + doğru sonuç.

**Çalışma mantığı**: Sonuca kalibre edilmiş rastgele gürültü (Laplace veya Gaussian mekanizması) eklenir. Gürültünün büyüklüğü, sorgunun "sensitivity"sine (tek bir kaydın sonucu en fazla ne kadar değiştirebileceği) göre ayarlanır.

**İki mod**:
- **Global/central DP**: Güvenilen bir merkez ham veriyi tutar, sadece sorgu sonuçlarına gürültü ekler.
- **Local DP**: Veri cihazdan çıkmadan önce gürültülenir; merkez ham veriyi hiç görmez. Bazı büyük teknoloji şirketlerinin telemetri toplama yaklaşımı bu modeldir. Daha güçlü ama daha çok fayda kaybeder.

**Gerçek fayda**: DP, birçok "anonimleştirme" tekniğinin yenildiği **composition** (aynı kişiye ait çok sayıda sorgu/yayının birleşimi) ve **linkage** saldırılarına karşı formel bir sınır sunar. Privacy budget, birden çok sorgu üzerinde toplanarak takip edilmelidir.

### Re-identification: Neden Sadece "İsmi Silmek" Yetmez

Meşhur vakalar (bir video akış servisinin "anonim" izleme verisinin harici bir film puanlama sitesiyle eşleştirilerek çözülmesi; "anonim" arama loglarından bireylerin tespiti) hep aynı dersi verir: doğrudan tanımlayıcıları silmek yetmez, çünkü quasi-identifier'ların birleşimi ve harici veri kümeleriyle **linkage** kimliği geri getirir. Anonimleştirme bir "yaptım oldu" işi değil; bir saldırgan modeline karşı ölçülmesi gereken bir güvence seviyesidir.

### Yaygın Hatalar

- Pseudonymized veriyi "anonim" sanıp düzenleme kapsamı dışında değerlendirmek. Denetimde en sık cezalandırılan hatalardan biridir.
- Anahtar (mapping key) ile pseudonymized veriyi aynı yerde, aynı erişim altında tutmak. Ayrılık şart; aksi halde pseudonymization güvenlik değeri sağlamaz.
- Hash'i geri döndürülemez sanmak; oysa küçük/tahmin edilebilir girdi uzaylarında hash pratikte tersine çevrilebilir.
- Free-text alanlarını anonimleştirmeyi unutmak (metin içinde geçen isim, adres, teşhis).

## Veri Saklama ve İmha Politikaları (Retention & Disposal)

### Tanım

Storage limitation ilkesi gereği veri, işleme amacı için gereken süreden fazla tutulamaz. Retention policy her veri kategorisi için "ne kadar süre" ve "sonra ne olacak" sorularını cevaplar; imha politikası bunun teknik uygulanışıdır.

### Çalışma Mantığı

- **Retention schedule**: Her data class'a bir saklama süresi atanır (ör. fatura verisi yasal gereği X yıl, pazarlama consent'i geri çekilene kadar, ham log 90 gün). Süreler yasal zorunluluk ile minimizasyon arasında dengelenir.
- **Otomatik imha**: TTL (time-to-live) alanları, veri tabanı partition drop'ları, object storage lifecycle kuralları ile silme otomatikleştirilir. Manuel silmeye güvenmek sürdürülemez.
- **Crypto-shredding (kripto-parçalama)**: Veriyi kayıt başına/tenant başına ayrı anahtarla şifreleyip, silme zamanı geldiğinde **anahtarı imha etmek**. Şifreli veri artık okunamaz hale gelir. Dağıtık sistemlerde, immutable backup'larda ve çok sayıda replikada fiziksel silmenin zor olduğu durumlarda pratik bir çözümdür.

### Silmenin Zorlukları

Gerçek dünyada "sil" komutu verinin tamamen yok olduğu anlamına gelmez:

- **Backup ve snapshot'lar**: Silinen kayıt yedeklerde yaşamaya devam eder. Restore edildiğinde geri gelebilir. Politika, backup rotation süresini ve restore sonrası yeniden-silme prosedürünü ele almalıdır.
- **Cache, CDN, arama indeksi, replica**: Aynı veri birçok kopyada bulunur.
- **Log ve analytics**: PII genellikle log'lara sızar ve silme kapsamı dışında kalır.
- **Üçüncü taraflar**: Veriyi paylaştığınız işleyicilerin (processor) de silmesi gerekir.

### Tespit ve Savunma

- **Tespit**: Retention süresini aşmış veriyi bulan periyodik denetim sorguları (`WHERE created_at < now() - retention`). Kayıt hiç silinmiyorsa alarm.
- **Savunma**: "Right to erasure" (GDPR Madde 17, silme talebi) taleplerini tüm kopyalarda uygulayabilen merkezi bir deletion orchestration servisi. Crypto-shredding'i backup dahil kapsayacak şekilde kurgulamak.

### Yaygın Hatalar

- Soft-delete'i (kayda `deleted=true` bayrağı koymak) gerçek silme sanmak. Veri hâlâ oradadır.
- Silme taleplerini yalnızca ana veri tabanında uygulayıp log, backup ve data warehouse'ı unutmak.
- Retention'ı hiç uygulamamak, "belki lazım olur" diye her şeyi süresiz saklamak; bu, ihlal anındaki veri kaybını (blast radius) katlar.

## DPIA (Data Protection Impact Assessment / Veri Koruma Etki Değerlendirmesi)

### Tanım

DPIA, yüksek riskli bir işleme faaliyetine başlamadan **önce** yürütülen yapılandırılmış risk değerlendirmesidir. GDPR Madde 35 bunu, bireylerin hak ve özgürlükleri için "yüksek risk" doğuran işlemelerde zorunlu kılar. Amaç, riski önden görüp azaltmaktır; sonradan yazılan bir rapor değil, tasarımı yönlendiren bir süreçtir.

### Ne Zaman Gerekir

Tipik tetikleyiciler: büyük ölçekli özel nitelikli veri işleme, sistematik ve kapsamlı profilleme/otomatik karar verme, kamusal alanların sistematik izlenmesi (ör. yüz tanıma), yeni teknolojilerin kullanımı.

### Çalışma Mantığı (Süreç Adımları)

1. **İşlemeyi tanımla**: Data flow'lar, hangi veri, kim, hangi amaç, hangi yasal dayanak. Burada data mapping çıktısı doğrudan girdi olur.
2. **Gereklilik ve orantılılık değerlendirmesi**: Bu veri gerçekten gerekli mi? Daha az müdahaleci bir yol var mı? (minimizasyonu zorlayan soru)
3. **Riskleri tanımla**: Bireye yönelik zararlar (ayrımcılık, kimlik hırsızlığı, itibar kaybı, finansal zarar). Sadece kuruma yönelik değil, **veri sahibine** yönelik risk değerlendirilir; bu, DPIA'yı klasik güvenlik risk analizinden ayıran noktadır.
4. **Azaltıcı kontroller**: Her risk için mühendislik kontrolü eşleştir (pseudonymization, DP, erişim kısıtı, retention).
5. **Kalan riski değerlendir ve onayla**: Kalan risk hâlâ yüksekse, düzenleyici otoriteye danışma (prior consultation) gündeme gelir.

### Tespit ve Savunma Perspektifi

- **Tespit**: Yüksek riskli yeni özelliklerin DPIA yapılmadan production'a çıkmasını yakalamak. Bunu bir "privacy gate" olarak release sürecine gömmek gerekir; yeni PII toplama veya yeni profilleme içeren PR'lar bir kontrol listesini tetiklemelidir.
- **Savunma**: DPIA'yı canlı bir doküman olarak tutmak; sistem değiştikçe güncellemek. Threat modeling ile DPIA'yı birleştirmek, tekrar eden çabayı azaltır.

### Yaygın Hatalar

- DPIA'yı ürün bittikten sonra "kutuyu işaretlemek" için yazmak; azaltıcı kontrolleri artık tasarıma sokamamak.
- Riski yalnızca kurum açısından (ceza, itibar) değerlendirip veri sahibinin zararını atlamak.
- DPIA sonucundaki azaltıcı aksiyonları takip etmemek; rapor rafta kalır, kontroller uygulanmaz.

## Sentez: Gizlilik Mühendisliğini Bir Kontrol Zinciri Olarak Görmek

Bu bileşenler birbirini besler ve tek bir zincir oluşturur:

- **Data mapping** neyin nerede olduğunu söyler; her şeyin girdisidir.
- **PbD ve minimization** en baştan ne kadar veri toplanacağını düşürür; toplanmayan veri korunacak yük değildir.
- **Pseudonymization/anonymization** kalan veriyi kırılganlaştırır; ama seviyesi (geri döndürülebilir mi, k-anonymous mı, DP garantili mi) doğru anlaşılmalıdır.
- **Retention/disposal** verinin ömrünü sınırlar, ihlal anındaki blast radius'u küçültür.
- **DPIA** tüm bunların yüksek riskli işlemelerde önden ve sistemli uygulanmasını zorunlu kılar.

Kilit zihniyet: gizlilik mühendisliği "compliance checkbox" değil, ölçülebilir bir **saldırgan modeline** (re-identification yapan, linkage kuran, privacy budget'i tüketen bir düşman) karşı savunma tasarımıdır. Bir tekniği uygularken sorulacak doğru soru "düzenleme bunu istiyor mu?" değil, "bu veriyi elinde tutan makul bir saldırgan kimliği geri getirebilir mi, hangi maliyetle?" sorusudur.
