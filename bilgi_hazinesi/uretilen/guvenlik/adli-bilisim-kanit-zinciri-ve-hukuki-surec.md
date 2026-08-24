# Adli Bilişim Kanıt Zinciri ve Hukuki Süreç

## Giriş: Teknik Analizin Görünmeyen Omurgası

Disk, bellek (memory) ve ağ (network) forensics analizi ne kadar derin olursa olsun, elde edilen bulgular hukuki bir süreçte ancak **kanıt zinciri (chain of custody)** doğru işletildiğinde değer taşır. Bir adli bilişim uzmanının yazdığı en teknik rapor bile, delilin nasıl toplandığı, korunduğu ve analiz edildiği belgelenmemişse mahkemede itiraz edilerek **kabul edilemez (inadmissible)** ilan edilebilir. GCFE ve GCFA gibi profesyonel DFIR sertifikasyonlarının teknik araç bilgisi kadar prosedürel disiplini de vurgulamasının nedeni budur.

Bu makale, adli bilişimin hukuki/prosedürel omurgasını ele alır: kanıt zinciri belgeleme, adli imaj (forensic image) alma standartları, hash doğrulama, mahkemede kabul edilebilirlik kriterleri ve adli rapor yazımı. Amaç, savunma tarafında çalışan bir uzmanın hem kendi delilini kurşun geçirmez hâle getirmesi hem de karşı tarafın delilindeki zayıflıkları tespit edebilmesidir.

## Kanıt Zinciri (Chain of Custody) Nedir?

### Tanım

**Chain of custody**, bir dijital delilin ilk el konulduğu (seizure) andan mahkemede sunulduğu ana kadar, kimin, ne zaman, nerede ve hangi amaçla o delile temas ettiğini kesintisiz olarak belgeleyen kayıt sistemidir. Amaç iki temel soruya her an cevap verebilmektir: "Bu delil, olay yerinden alınan delille aynı mıdır?" ve "Bu delil, alındıktan sonra değiştirilmemiş midir?"

### Kök Neden / Çalışma Mantığı

Dijital deliller doğaları gereği **kolayca değiştirilebilir (volatile ve mutable)**. Bir dosyaya çift tıklamak bile `last accessed` zaman damgasını değiştirebilir; bir sistemi kapatmak bellekteki tüm uçucu veriyi yok eder. Bu nedenle hukuk, dijital delile fiziksel delilden (örneğin bir bıçaktan) daha yüksek bir belgeleme titizliği bekler. Chain of custody, mahkemeye şunu ispatlar: delil, insan eliyle veya teknik hatayla **kirletilmemiştir (evidence tampering / contamination olmamıştır)**.

Belgelemenin taşıması gereken minimum bileşenler:

- **Ne:** Delilin tanımı (marka, model, seri numarası, kapasite, varsa etiket/barkod).
- **Kim:** Deli temas eden her kişinin kimliği.
- **Ne zaman:** Her el değiştirmenin tarih ve saati (mümkünse saniye hassasiyetinde ve saat dilimi belirtilerek).
- **Nerede:** Delilin fiziksel konumu (olay yeri, delil dolabı/kasa, laboratuvar).
- **Neden:** Her temasın gerekçesi (imaj alma, analiz, taşıma, saklama).

### Örnek: Bir Chain of Custody Kaydı

Bir dizüstü bilgisayara el konulduğunu düşünelim. İdeal kayıt akışı şöyle ilerler:

1. Olay yerinde delil etiketlenir: `EVIDENCE-2026-0142`, Dell Latitude, S/N `ABC123`, 512 GB SSD. Fotoğraflanır, imzalı tutanağa geçirilir.
2. Delil, **tamper-evident (kurcalanma belirtisi gösteren) mühürlü poşete** konur; poşet numarası kayda işlenir.
3. Delil, kilitli ve erişimi loglanan bir **delil kasasına (evidence locker)** koyulur.
4. Laboratuvara çıkarılırken kayıt güncellenir: "12.03.2026 09:14, X kişisi, imaj alma amacıyla laboratuvara aldı."
5. İmaj alındıktan sonra orijinal disk yeniden mühürlenip kasaya iade edilir; tüm analiz **kopya (working copy)** üzerinde yapılır.

Buradaki altın kural: **orijinal delile mümkün olan en az temas.** Analiz her zaman bit-birebir kopya üzerinde yürütülür.

## Adli İmaj Alma (Forensic Imaging) Standartları

### Tanım

**Forensic imaging**, bir depolama biriminin (disk, USB, telefon belleği) bit düzeyinde birebir kopyasını çıkarmaktır. Bu, dosyaları kopyalamaktan (logical copy) temelde farklıdır: adli imaj; silinmiş dosyaları, `slack space`, `unallocated space` ve dosya sistemi meta verisini de içeren **tam bir fiziksel kopyadır (bit-stream image)**.

### Write Blocker: Değiştirmeden Okuma

İmaj almanın en kritik ilkesi orijinal medyayı **değiştirmemektir**. Bir diski sıradan bir bilgisayara bağlamak bile işletim sisteminin diske yazması (journaling, indexing, mount kayıtları) ile sonuçlanabilir. Bunu engellemek için **write blocker** kullanılır: donanım ya da yazılım tabanlı bu araç, hedef medyaya giden tüm yazma komutlarını fiziksel/mantıksal olarak bloke ederken okumaya izin verir. Write blocker kullanılmadan alınan bir imajın bütünlüğü mahkemede ciddi biçimde tartışmaya açıktır.

### İmaj Formatları: RAW (dd), E01, AFF4

Adli imajlar farklı konteyner formatlarında saklanır:

- **RAW / dd:** Ham bit dizisi; hiçbir meta veri veya sıkıştırma içermez. Evrensel uyumludur ancak imaj bütünlük bilgisi (hash) formatın kendi içinde taşınmaz, ayrı tutulur.
- **E01 (EnCase Evidence File / Expert Witness Format):** Adli sektörün fiili standartlarından biridir. Sıkıştırma, imaj içine gömülü meta veri (dava numarası, uzman adı, tarih) ve en önemlisi **imaj içine yerleştirilmiş hash doğrulama** ile bütünlük kontrolünü destekler. Veri, doğrulanabilir bloklar hâlinde saklanır.
- **AFF4 (Advanced Forensic Format 4):** Daha modern, açık bir formattır. Büyük ve seyrek (sparse) imajları verimli ele almak, birden çok kanıt nesnesini tek konteynerde birleştirmek ve zaman damgalı meta veriyi zengin biçimde saklamak için tasarlanmıştır. Özellikle çok büyük depolama birimlerinde ve bulut/uzak edinim senaryolarında avantaj sunar.

Format seçimi kurumun araç zincirine bağlıdır; kritik olan, seçilen format ne olursa olsun **hash tabanlı bütünlük doğrulamasının** yapılmasıdır.

### İmaj Doğrulama (Verification)

İmaj alındıktan sonra araç genellikle iki hash üretir: kaynağın (source) hash'i ve yazılan imajın (image) hash'i. Bu iki değer eşleşmelidir. Bu, imajın alma sürecinde bit hatası olmadan, orijinalle **birebir aynı** çıktığını kanıtlar. E01 gibi formatlar bu doğrulamayı blok blok yapıp imaj dosyasının içine gömer.

## Hash Doğrulama: Delilin Dijital Parmak İzi

### Tanım ve Çalışma Mantığı

**Hash fonksiyonu (cryptographic hash)**, herhangi boyuttaki bir veriyi sabit uzunlukta bir özet değere dönüştüren tek yönlü matematiksel fonksiyondur. Adli bilişimde iki temel amaca hizmet eder:

1. **Bütünlük (integrity):** İmajın alındığı andan sonra tek bir bit dahi değişmediğini ispatlamak. Verinin tek bir biti değişse hash tamamen farklı olur (avalanche effect).
2. **Kimlik (identification):** Bilinen dosyaları (kötü amaçlı yazılım, yasa dışı içerik) hash veritabanlarıyla eşleştirmek; bilinen sistem dosyalarını eleyerek (known-good filtering) analiz yükünü azaltmak.

### MD5, SHA-1 ve SHA-256

Adli pratikte sık kullanılan algoritmalar MD5, SHA-1 ve SHA-256'dır. MD5 ve SHA-1 kriptografik olarak **çakışmaya (collision) karşı zayıflamıştır**; yani teorik olarak farklı iki veri aynı hash'i üretecek şekilde kasıtlı üretilebilir. Bu nedenle güvenlik-kritik bağlamlarda SHA-256 tercih edilir.

Ancak adli bilişimde önemli bir nüans vardır: MD5, bir saldırganın delili değiştirmesi senaryosunda zayıf olsa da, imaj bütünlüğünü **kaza eseri bozulmalara (bit rot, kopyalama hatası)** karşı doğrulama amacıyla hâlâ yaygın kullanılır. Modern en iyi pratik, birden fazla algoritmayı (örneğin MD5 + SHA-256) birlikte hesaplamaktır; ikisinin aynı anda çakışacak şekilde kırılması pratikte olanaksızdır. Rapor yazarken hangi algoritmanın hangi amaçla kullanıldığını belirtmek profesyonel bir alışkanlıktır.

### Örnek Akış

1. İmaj alınır; araç kaynak diskin SHA-256 değerini `A1B2...` olarak hesaplar.
2. Yazılan imajın SHA-256 değeri hesaplanır; `A1B2...` çıkar. **Doğrulama başarılı.**
3. Aylar sonra analiz yeniden yapılacağında imajın hash'i tekrar hesaplanır. Değer hâlâ `A1B2...` ise imajın saklama sürecinde bozulmadığı ispatlanır.

Bu üçlü kontrol, mahkemede "delil zaman içinde değişmedi" savının teknik dayanağıdır.

## Mahkemede Kabul Edilebilirlik (Admissibility)

### Tanım

**Admissibility**, bir delilin mahkeme tarafından değerlendirmeye alınıp alınmayacağıdır. Teknik olarak mükemmel bir analiz bile, delilin nasıl elde edildiği veya işlendiği hukuka veya prosedüre aykırıysa reddedilebilir.

### Kabul Edilebilirliği Belirleyen Temel İlkeler

Hukuk sistemleri arasında (örneğin common law ile kıta Avrupası hukuku) ayrıntılar farklılaşsa da, dijital delil için genel geçer beklentiler benzeşir:

- **Otantiklik (authenticity):** Delil, iddia edildiği kaynaktan geldiği ve değiştirilmediği ispatlanabilmelidir. Hash doğrulama ve chain of custody bunun temelidir.
- **Yasal edinim (lawful acquisition):** Delil, uygun yetki/izinle (arama kararı, mahkeme emri, rıza) toplanmış olmalıdır. Hukuka aykırı yolla elde edilen delil pek çok sistemde reddedilir.
- **Güvenilirlik (reliability):** Kullanılan yöntem ve araçlar bilimsel olarak kabul görmüş, tekrarlanabilir ve doğrulanabilir olmalıdır. Uzman, kullandığı aracın nasıl çalıştığını açıklayabilmelidir.
- **Bütünlük (integrity):** Delilin tüm süreç boyunca değişmediği belgelenmelidir.
- **İlgililik (relevance):** Delil, davanın konusuyla mantıksal bağ taşımalıdır.

Common law geleneğinde bilirkişi/uzman görüşünün kabulünde yöntemin bilimsel geçerliliğini sorgulayan yerleşik standartlar (örneğin uzman tanıklığının güvenilirliğine ilişkin ilkeler) vardır; ilkenin özü, kullanılan yöntemin test edilebilir ve mesleki çevrede kabul görmüş olmasıdır. Kesin dava içtihatlarının ve yerel mevzuat maddelerinin yargı yetkisine göre değiştiğini unutmayın; somut bir davada mutlaka o yargı çevresinin güncel kuralları esas alınmalıdır.

### Repeatability ve Reproducibility

Güçlü bir adli analizin ölçütü, **başka bir uzmanın aynı imaj üzerinde aynı adımları izleyerek aynı sonuca ulaşabilmesidir (reproducibility).** Bu yüzden rapor, "ne bulundum" kadar "nasıl buldum"u da içermelidir. Analiz yalnızca doğrulanmış working copy üzerinde yapılır ki orijinal, gerektiğinde bağımsız bir uzman tarafından yeniden incelenebilsin.

## Adli Rapor Yazımı (Forensic Reporting)

### Amaç ve Okuyucu Kitlesi

Adli rapor iki farklı kitleye aynı anda hitap eder: teknik detayı değerlendiren bilirkişiler ve teknik olmayan hâkim/avukat/jüri. İyi rapor bu ikisini dengeler; teknik doğruluktan ödün vermeden anlaşılır olur. Rapor **tarafsız (objective)** olmalıdır; uzmanın görevi bir tarafı savunmak değil, bulguları dürüstçe sunmaktır.

### Tipik Rapor Bölümleri

- **Özet (executive summary):** Teknik olmayan okuyucu için bulguların ve sonucun kısa özeti.
- **Görevlendirme kapsamı (scope):** Neyin incelenmesi istendiği, hangi soruların yanıtlandığı.
- **Delil listesi:** Her delilin tanımı, kaynağı, hash değerleri, edinim tarih/saati.
- **Kullanılan araç ve yöntemler:** Araç adı ve sürümü, uygulanan adımlar, write blocker kullanımı, doğrulama yöntemi.
- **Bulgular (findings):** Nesnel gözlemler; ekran görüntüleri, dosya yolları, zaman damgaları, artefaktlar. Yorum ile ham gözlem net biçimde ayrılmalıdır.
- **Analiz ve yorum:** Bulguların ne anlama geldiği; varsayımlar ve sınırlamalar açıkça belirtilir.
- **Sonuç:** Kapsam sorularına verilen cevaplar.
- **Ekler:** Chain of custody formları, hash log'ları, araç çıktıları.

### Örnek: İyi Bir Bulgu İfadesi

Zayıf ifade: "Kullanıcı dosyayı sildi." (Yorum, kesinlik iddiası.)

Güçlü ifade: "`$Recycle.Bin` içinde, `12.03.2026 14:22` (UTC+3) tarihli silme kaydına ait bir `$I` meta veri dosyası tespit edildi; bu kayıt `rapor_final.docx` adlı dosyaya işaret etmektedir. Kaydın hangi kullanıcı hesabı bağlamında oluştuğu SID `S-1-5-21-...` ile ilişkilidir." Bu ifade neyin gözlemlendiğini, kaynağını ve sınırlarını (silmenin insan eliyle mi otomatik mi olduğuna dair kesinlik iddia etmez) ortaya koyar.

## Tespit ve Savunma: Süreci Kurşun Geçirmez Yapmak

Bu konuda "savunma", bir sistemi değil **delilin ve sürecin bütünlüğünü** savunmaktır. Hem kendi delilinizi güçlendirmek hem de karşı tarafın delilini denetlemek için kontrol noktaları:

- **Write blocker doğrulaması:** İmaj alımının write blocker ile yapıldığı belgelenmiş mi? Yapılmamışsa orijinal medyanın zaman damgaları değişmiş olabilir; bu bir zayıflıktır.
- **Hash süreci denetimi:** Edinim anında ve sonraki her analizde hash hesaplandı mı, değerler eşleşiyor mu, hangi algoritma kullanıldı? Eşleşmeyen hash, bütünlük ihlali işaretidir.
- **Chain of custody boşlukları:** Kayıtta belgelenmemiş bir zaman aralığı (unaccounted time) var mı? Delilin kimin elinde olduğu bilinmeyen her boşluk, "delil kirletilmiş olabilir" itirazına kapı açar.
- **Araç güvenilirliği:** Kullanılan araç mesleki çevrede tanınıyor ve doğrulanabilir mi? Sonuçlar bağımsız bir araçla çapraz doğrulanabilir mi (tool validation)?
- **Zaman senkronizasyonu:** İncelenen sistemin saati doğru muydu, saat dilimi belgelendi mi? Yanlış zaman damgaları tüm zaman çizelgesini (timeline) çürütebilir.
- **Uçucu veri disiplini:** Bellek (RAM) gibi uçucu deliller, kalıcı disklerden **önce** ve doğru sırayla (order of volatility) toplandı mı?

## Yaygın Hatalar

- **Orijinal medya üzerinde çalışmak:** Analizi kopya yerine orijinal disk üzerinde yapmak; delili geri döndürülemez biçimde kirletir.
- **Write blocker kullanmadan bağlama:** Diski normal bir makineye takıp "sadece bakacağım" demek; işletim sistemi arka planda yazma yapar.
- **Hash almayı atlamak veya sadece bir kez almak:** Edinim anında hash alınmazsa, sonradan "değişmedi" demenin dayanağı kalmaz.
- **Zayıf algoritmaya körü körüne güvenmek:** Yalnızca MD5'e dayanıp, kasıtlı manipülasyon senaryosunun sorulabileceği bir davada ek algoritma kullanmamak.
- **Chain of custody'yi geç veya eksik doldurmak:** "Sonra yazarım" demek; belgeleme gerçek zamanlı olmalıdır.
- **Yorumu gözlemle karıştırmak:** Raporda "kullanıcı kasıtlı sildi" gibi ispatlanamayan çıkarımları nesnel bulgu gibi sunmak.
- **Saat dilimi ve zaman senkronizasyonunu belgelememek:** Timeline analizini savunulamaz hâle getirir.
- **Tek araca bağımlılık:** Kritik bir bulguyu ikinci bir araçla çapraz doğrulamamak.

## Sonuç

Adli bilişimde teknik yetkinlik gerekli ama tek başına yeterli değildir. Bir delili mahkemede ayakta tutan şey; kesintisiz **chain of custody**, write blocker ile alınmış doğrulanmış bir **forensic image**, edinimden analize kadar tutarlı **hash doğrulaması**, yasal edinim ve tekrarlanabilir yöntem üzerine kurulu **admissibility** temeli ve nesnel, izlenebilir bir **adli rapordur.** GCFE/GCFA gibi sertifikasyonların prosedürel disipline verdiği ağırlık tam da bu yüzdendir: en iyi teknik bulgu bile, süreci belgelenmemişse hukuken yok hükmündedir. Savunma tarafında bir uzmanın en güçlü silahı, hem kendi sürecini kusursuz belgelemek hem de karşı tarafın sürecindeki boşlukları görebilecek prosedürel keskinliktir.
