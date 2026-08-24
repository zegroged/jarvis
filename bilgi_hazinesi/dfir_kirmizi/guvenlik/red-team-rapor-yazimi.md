# Kırmızı Takım Rapor Yazımı

> Çerçeve: Bu metin yetkili güvenlik testi (pentest / red team engagement) bağlamında yazılmıştır. Amaç, bir angajmanın çıktısını nasıl doğru, savunulabilir ve savunmacıya değer katacak biçimde belgeleyeceğini anlamaktır. Odak metodoloji ve yargıdır; hedef sistemlere karşı çalıştırılabilir saldırı reçetesi değil, raporun kendisini bir mühendislik ürünü gibi ele almaktır.

## 1. Bu aşama neyi hedefler, engagement'taki yeri

Rapor, angajmanın "ürünü"dür. Müşteri exploit'ini görmez, ele geçirdiğin Domain Admin oturumunu görmez, üç gece süren pivot zincirini görmez. Müşterinin eline geçen tek somut şey rapordur. Bu yüzden kıdemli operatörler arasında dolaşan acı bir gerçek vardır: **teknik olarak dünyanın en iyi angajmanını yapıp berbat bir rapor yazarsan, müşteri için berbat bir iş yapmışsındır.** Tersine, orta seviye bir teknik iş bile mükemmel yazılmış bir raporla müşteriye gerçek değer taşır.

Raporun engagement döngüsündeki yeri şudur: Kapsam belirleme (scoping) → keşif → sömürü → yanal hareket / hedefe ulaşma → **raporlama** → yeniden test (retest). Ancak burada acemilerin gözden kaçırdığı kritik nokta şu: rapor yazımı, angajmanın *sonunda başlayan* bir faaliyet değildir. Rapor, birinci günün birinci saatinde başlar. Her komut çıktısı, her ekran görüntüsü, her zaman damgası, her bulgu; yazılmadıysa var olmamıştır. Angajman biterken "şimdi rapor yazayım" diyen kişi, kanıtların yarısını hatırlamaya çalışırken kaybeder.

Raporun iki hedefi vardır ve bunlar farklı okuyuculara hitap eder:

- **Yönetici / karar verici okuyucu (executive):** Risk nedir, iş üzerindeki etkisi ne, ne kadar para ve zaman gerekir. Bu kişi CVSS skorunu değil, "saldırgan müşteri veritabanımıza erişebildi mi?" sorusunun cevabını arar.
- **Teknik / düzeltici okuyucu (remediation):** Tam olarak ne kırıldı, nasıl yeniden üretilir, neyi düzeltmem gerekir, düzelttiğimi nasıl doğrularım. Bu kişi zaman damgalarını, tam istekleri, etkilenen sunucu adlarını ister.

İyi rapor bu iki okuyucuyu aynı belgede, çelişmeden, birbirini tekrar etmeden tatmin eder. Bu bir yazma problemi olduğu kadar bir mimari problemidir. Pratikte bu, katmanlı bir yapıyla çözülür: en üstte bir sayfalık yönetici özeti (executive summary), ortada risk tablosu ve saldırı anlatısı, en altta bulgu bulgu teknik ek. Yönetici üstte durur, mühendis alta iner; ikisi de aynı belgeden farklı derinliklerde beslenir. Kıdemli operatör raporu bu üç katmanı ayrı okuyucular için ayrı ayrı test ederek yazar: "Bir CFO sadece ilk sayfayı okusa doğru kararı verir mi? Bir DevOps mühendisi sadece ilgili bulguyu okusa düzeltmeyi yapabilir mi?"

Ayrıca raporun bir üçüncü, sık unutulan okuyucusu vardır: **gelecekteki sen ve ekibin.** Retest zamanı, bir sonraki yılın angajmanı, ya da müşteriyle çıkacak bir anlaşmazlık anında rapora geri dönülür. Bu yüzden rapor sadece "bugün ikna edici" değil, "altı ay sonra da savunulabilir ve yeniden üretilebilir" olmalıdır. Bu zaman boyutu, acemi ile kıdemli rapor arasındaki en sessiz ama en belirleyici farklardan biridir.

## 2. Metodoloji ve karar ağacı (asıl değer)

### Bulgu mu, gözlem mü, yoksa gürültü mü?

Kıdemli operatörün ilk kararı her tespit için verilir: bu bir **bulgu (finding)** mı, bir **gözlem (observation)** mı, yoksa rapora hiç girmeyecek **gürültü** mü?

Karar ağacı şöyle işler:

1. **Bunun gösterilebilir bir güvenlik etkisi var mı?** Yoksa, muhtemelen gözlem veya gürültüdür. "Sunucu HTTP başlığında sürüm bilgisini açığa çıkarıyor" tek başına bir bulgu değildir; bir *gözlemdir* çünkü tek başına kimseyi ele geçirmez. Onu bir bulguya dönüştüren şey, o sürümün bilinen ve sömürülebilir bir zafiyetinin olmasıdır.
2. **Bu etkiyi kanıtlayabiliyor muyum?** Kanıtlayamadığın hiçbir şeyi "yüksek risk" olarak yazamazsın. "SQL injection olabilir" ile "SQL injection var, işte veritabanı sürüm çıktısı" arasındaki fark, raporun güvenilirliğidir. Teorik risk ile ispatlanmış risk ayrı raflarda durur.
3. **Bu bulgu zaten başka bir bulgunun sonucu mu?** Beş ayrı makinede aynı zayıf yerel yönetici parolasını bulduysan bu tek bir bulgudur (parola yeniden kullanımı / zayıf kimlik yönetimi), beş bulgu değil. Acemiler bulgu sayısını şişirir; kıdemliler kök nedende birleştirir.

### Risk derecelendirmesi: sayı değil yargı

Buradaki en yaygın profesyonel hata, CVSS taban skorunu (base score) doğrudan rapora "risk" olarak yazmaktır. CVSS taban skoru *zafiyetin doğasını* ölçer; senin müşterinin *ortamındaki riski* ölçmez. Bir "kritik" RCE, internete kapalı, kimsenin erişemediği, dört yıldır kullanılmayan bir iç test sunucusundaysa gerçek riski düşüktür. Bir "orta" seviye bilgi ifşası, doğrudan yönetici parolalarını açığa çıkarıyorsa gerçek riski kritiktir.

Kıdemli operatörün risk kararı üç eksenden geçer:

- **Etki (impact):** Bu sömürülürse müşteri ne kaybeder? Veri mi, para mı, itibar mı, operasyonel süreklilik mi? İş bağlamı olmadan etki puanlanamaz. Bu yüzden scoping aşamasında "sizin için en değerli varlık nedir, en çok neyin sızmasından korkuyorsunuz?" sorusu sorulur — o cevap, rapordaki etki puanlamasının çıpasıdır.
- **Olabilirlik / erişilebilirlik (likelihood):** Saldırganın bunu bulması ve sömürmesi ne kadar kolay? Kimlik doğrulama gerekiyor mu, ağın neresinden erişiliyor, otomatik araçlar buluyor mu yoksa özel bilgi mi gerekiyor?
- **Bağlamsal düzeltmeler:** Telafi edici kontroller (compensating controls) var mı? WAF, ağ segmentasyonu, EDR, izleme? Bunlar riski düşürür ama *sıfırlamaz* ve raporda bunu dürüstçe ifade etmek gerekir: "WAF mevcut sömürüyü engelledi ancak kural setindeki küçük bir değişiklik bu korumayı devre dışı bırakır."

Kural: **Bir müşteri seni risk derecen için sıkıştırdığında, o dereceyi bir cümlede savunabiliyor olmalısın.** Savunamıyorsan, derece yanlıştır.

### Bulgu anatomisi ve yazım sırası

Her ciddi bulgu şu iskeleti taşır ve profesyonel bu iskeleti *tersinden*, yani etkiden başlayarak düşünür ama düzenli okunacak şekilde yazar:

1. **Başlık:** Zafiyet sınıfı + etkilenen varlık + sonuç. "Kimlik Doğrulamasız API Uç Noktası Üzerinden Tam Müşteri Kaydı İfşası" iyi başlıktır. "SQL Injection" kötü başlıktır — nerede, ne sonuç, belirsiz.
2. **Etki (business impact):** Önce bunu yaz. Yönetici bu paragrafı okuyup durabilmeli. Teknik jargon olmadan: saldırgan ne yapabildi, müşteri ne kaybedebilir.
3. **Teknik açıklama:** Zafiyetin kök nedeni. Neden var, hangi kod / yapılandırma / süreç hatası buna yol açtı.
4. **Kanıt (evidence / proof of concept):** Yeniden üretilebilir adımlar, temizlenmiş (redakte edilmiş) ekran görüntüleri, ilgili istek/yanıt parçaları. Burada *gerçek hassas veriyi göstermezsin* — bir müşteri kaydının tamamını değil, "işte tablo yapısı ve ilk kaydın maskelenmiş hali, bu erişimin gerçek olduğunu kanıtlıyor" dersin.
5. **Düzeltme önerisi (remediation):** Somut, uygulanabilir, önceliklendirilmiş. "Girdiyi doğrulayın" yetersizdir. "Parametreli sorgular kullanın; ORM katmanında X deseni yerine Y desenini uygulayın; bu değişiklik yaklaşık şu efor gerektirir" gerçek değerdir.
6. **Referanslar:** OWASP, CWE, satıcı dokümantasyonu. Uydurma referans vermek raporun ölüm fermanıdır — bir müşteri mühendisi tek bir sahte bağlantı bulursa tüm raporun güvenilirliğini sorgular.

### "Şu bulguyu görünce şu yöne giderim" mantığı

Raporlama açısından karar ağacı, bulguların *nasıl gruplanacağına* dair de işler:

- **Aynı kök neden, farklı belirtiler görürsem** → tek bir "sistemik" bulgu yazar, belirtileri onun altında listelerim. Örneğin on farklı yerde eksik yama görürsem, bu "yama yönetimi süreç eksikliği" başlığı altında toplanır; bu, müşterinin on ayrı yamayı kovalamak yerine süreci düzeltmesini sağlar.
- **Tekil ama zincirlenebilir zayıflıklar görürsem** → "saldırı zinciri (attack path / kill chain)" anlatısı yazarım. Tek başına düşük riskli üç bulgu (bilgi ifşası + zayıf parola politikası + aşırı yetkili servis hesabı) birleştiğinde Domain Admin'e giden bir yol oluşturuyorsa, bunu bir *anlatı* olarak sunmak, üç ayrı düşük riskli bulgudan çok daha ikna edicidir. Yöneticiler tek zayıflığa değil, hikayeye tepki verir.
- **Sömüremediğim ama güçlü şüphem olan bir şey görürsem** → bunu "gözlem" veya "kapsam/zaman kısıtı notu" olarak yazarım, asla ispatlanmış bulgu gibi göstermem. "Zaman sınırı nedeniyle tam olarak doğrulanamadı ancak şu belirtiler ileri incelemeyi hak ediyor" dürüst ve profesyoneldir.

### Anlatı akışı: kill chain'i geri çat

Kıdemli raporun kalbi çoğu zaman "Attack Narrative" veya "Path to Compromise" bölümüdür. Burada okuyucuyu ilk dış temas noktasından en kritik varlığa kadar adım adım götürürsün — ama bu bir *reçete* değil, bir *anlatıdır*. Amaç "bu komutları çalıştır" değil, "gördüğünüz gibi bu üç ayrı orta seviyeli zayıflık, savunmanızın hiçbir yerde bu zinciri kırmadığı için birleşerek felakete yol açtı" dedirtmektir. Bu bölüm savunmacıya "nerede durdurabilirdim?" diye düşündürür ki raporun asıl değeri budur.

## 3. Acemi vs pro: yaygın hatalar

**Araç çıktısını rapora yapıştırmak.** En sık ve en utanç verici hata. Nessus / Nmap / bir tarayıcı çıktısını olduğu gibi rapora koyup teslim etmek. Bu bir rapor değil, bir *çıktı dökümüdür* ve müşteri bunu senden ödeme yapmadan da alabilirdi. Pro, aracın bulduğu 400 satırlık listeyi süzer, doğrular (tarayıcılar yalan söyler — false positive), bağlamlandırır ve 12 gerçek bulguya indirger. Değer, indirgemede ve doğrulamadadır.

**Yanlış pozitifleri doğrulamadan yazmak.** Bir tarayıcı "SSL zafiyeti" dediğinde onu manuel doğrulamadan rapora yazan kişi, ilk müşteri itirazında çöker. Kıdemli kural: **rapora giren her bulgu, senin elinle doğrulanmıştır.** Doğrulayamadıysan gözlem rafına gider.

**Bulgu sayısıyla övünmek.** Acemi "47 bulgu buldum" der. Kıdemli bilir ki 47 bulgu, çoğu zaman 6 kök neden ve 41 belirtidir; ayrıca müşteriyi ezer, önceliklendirmeyi imkânsızlaştırır ve raporu gürültüye boğar. Değer bulgu sayısında değil, müşterinin *doğru sırayla* ne yapması gerektiğini görebilmesindedir.

**Etki yerine teknik detaya boğulmak.** Acemi, bir buffer overflow'un mekaniğini üç sayfa anlatır ama "bu sömürülürse ne olur?" sorusunu cevaplamaz. Yönetici o üç sayfayı okumaz. Etkiyi bir cümlede söyleyemiyorsan, bulguyu tam anlamamışsındır.

**Genel geçer düzeltme önerileri.** "En iyi güvenlik uygulamalarını izleyin", "girdiyi doğrulayın", "yamaları uygulayın" — bunlar öneri değil, dolgu malzemesidir. Müşteri mühendisi bunu okuyunca ne yapacağını bilmez. Pro öneri: hangi dosya, hangi ayar, hangi desen, ne kadar efor, hangi öncelik.

**Kanıtta hassas veriyi maskelemeden bırakmak.** Ekran görüntüsünde gerçek müşteri TC kimlik numaraları, gerçek parolalar, gerçek e-postalar. Bu hem etik hem yasal bir felakettir; raporun kendisi bir veri sızıntısı taşıyıcısına dönüşür. Pro her kanıtı teslimden önce maskeler ve raporu şifreli kanaldan iletir.

**Ton problemi.** Acemi ya suçlayıcı ("geliştiricileriniz temel güvenliği bilmiyor") ya da abartılı korku pazarlamacısı ("felaket kaçınılmaz!") olur. Kıdemli ton nötr, olgusal ve yapıcıdır. Rapor bir savunma değil, bir teşhistir. Karşındaki mühendis ekip, düşmanın değil, düzeltmenin ortağın.

**Angajman sırasında not tutmamak.** Belki en pahalı hata. Sömürü anında ekran görüntüsü almayan, zaman damgası kaydetmeyen operatör, rapor zamanında hafızasına güvenmek zorunda kalır — ve hafıza yalan söyler. Sonuç: yeniden üretilemeyen bulgular, eksik kanıt, müşterinin doğrulayamadığı iddialar. Pro her adımı *o an* kaydeder; rapor yazımı bu notların düzenlenmesidir, hatırlanması değil.

**Retest'i düşünmeden yazmak.** Müşteri düzeltmeyi yapıp seni yeniden test için çağıracak. Eğer bulguyu "nasıl yeniden üretilir" bilgisiyle net yazmadıysan, kendi bulgunu bile yeniden test edemezsin. Her bulgu, üç ay sonra başka bir operatörün (ya da unutmuş halinin) tekrar doğrulayabileceği kadar net olmalıdır.

## 4. Savunma köprüsü (mavi takım)

Rapor, kırmızı takımın mavi takıma en büyük hediyesidir — doğru yazılırsa. Savunmacı için raporun değeri "hangi açıklar var" listesinden çok daha derindir: **"benim tespit yeteneklerim nerede kördü?"** sorusunu cevaplar.

Bu yüzden kıdemli raporlar, salt bulgu listesine ek olarak bir **tespit ve iz analizi** boyutu taşır. Her önemli saldırı adımı için savunmacıya şunları verirsin:

- **Bu eylem hangi izleri bırakır?** Sömürü hangi loglarda görünürdü? Windows Olay Günlükleri'nde hangi olay ID'leri, hangi kimlik doğrulama anomalileri, hangi süreç oluşturma (process creation) kayıtları, hangi ağ akışları? Örneğin bir kimlik bilgisi hırsızlığı LSASS erişimi bırakır; yanal hareket anormal SMB / WMI / uzak servis oluşturma trafiği bırakır; kalıcılık zamanlanmış görev veya servis kaydı bırakır.
- **Savunmacı bunu tespit etti mi?** Angajman boyunca mavi takımın seni fark edip etmediğini not etmek raporun en değerli parçalarından biridir. "5. günde Domain Admin aldık, 11. gün rapor teslimine kadar hiçbir uyarı tetiklenmedi" cümlesi, herhangi bir CVSS skorundan daha çok bütçe hareket ettirir.
- **Nasıl tespit edilebilirdi?** Somut tespit önerileri: hangi log kaynağı toplanmalı, hangi SIEM kuralı yazılmalı, hangi eşik ayarlanmalı, hangi davranış temel çizgisinden (baseline) sapma izlenmeli. Bu, MITRE ATT&CK teknikleriyle eşlenerek verilir — böylece mavi takım her bulguyu bir tespit mühendisliği görevine dönüştürebilir.

Kıdemli operatörün burada verdiği kritik yargı şudur: **bir bulgunun düzeltilmesi (remediation) ile tespit edilmesi (detection) ayrı iki savunma katmanıdır ve rapor ikisini de ele almalıdır.** Bazı zafiyetler hemen düzeltilemez (eski sistem, iş kısıtı, bütçe); o durumda tespit ve izleme önerisi, müşterinin risk düşürebileceği tek pratik yoldur. Sadece "bunu düzeltin" diyen rapor, düzeltilemeyecek bulgular karşısında müşteriyi çaresiz bırakır. "Düzeltemiyorsanız, en azından şu davranışı şu şekilde izleyin ki saldırganı fark edin" diyen rapor, gerçek dünyada işe yarar.

Pratik bir örüntü olarak, kıdemli raporlar önemli bulguların altına küçük bir "Tespit" kutusu ekler. Bu kutu üç soruyu yanıtlar: bu adım hangi telemetri kaynağında iz bıraktı, o iz normal gürültüden nasıl ayırt edilir, ve bunu yakalayacak bir tespit mantığı kavramsal olarak nasıl kurulur. Dikkat edilecek yargı: savunmacıya "şu tam kuralı yaz" demek yerine "şu davranışsal anomaliyi şu kaynaktan izle" demek daha sağlıklıdır, çünkü her ortamın gürültü tabanı farklıdır ve birebir kopyalanan kurallar ya yanlış alarm yağmuruna ya da sessiz körlüğe yol açar. Amaç savunmacıya balık vermek değil, kendi ortamında balık tutmayı öğretmektir.

Bir diğer önemli yargı, **tespit ile önlemenin (prevention) farkını raporda net tutmaktır.** Bir kontrolün saldırıyı engellemesi ile saldırıyı görmesi bambaşka şeylerdir. Bir müşteri "EDR'ımız var, koruyoruz" diyebilir; ama sen angajmanda EDR'ı atlatıp hiçbir uyarı üretmedeysen, raporun bu ikisi arasındaki boşluğu tam olarak göstermelidir: "Kontrol mevcuttu ancak ne engelledi ne de uyardı." Bu cümle, güvenlik yatırımlarının gerçek etkinliğini ölçen en dürüst araçtır.

Bir başka savunma köprüsü boyutu: raporun kendisi bir **temel çizgi (baseline)** oluşturur. Bir sonraki angajmanda müşteri "geçen sefer bulunan bulgular kapatıldı mı, tespit yeteneği gelişti mi?" diye ölçebilir. Bu yüzden bulguları izlenebilir kimliklerle (finding ID) numaralandırmak ve tutarlı bir taksonomi (ATT&CK, OWASP) kullanmak, raporu tek seferlik bir belgeden bir güvenlik olgunluk ölçüm aracına dönüştürür.

## 5. Araçlar ve gerçek dünya notları

**Not tutma / kanıt toplama.** Angajmanın en kritik "aracı" rapor yazarı değil, disiplinli not tutma alışkanlığıdır. Ekiplerde yaygın araçlar: paylaşımlı bir CherryTree / Obsidian / Joplin defteri, bir angajman wiki'si veya özel platformlar. Ekip angajmanlarında ortak bir kanıt deposu (screenshot + komut logu + zaman damgası) hayat kurtarır. Pratik tüyo: terminal oturumlarını `script` / tmux logging veya benzeri araçlarla ham olarak kaydet, ama rapora ham logu değil, ondan süzülmüş kanıtı koy. Ham log senin sigortandır, müşterinin ürünü değil.

**Rapor üretim / bulgu yönetimi.** Bulguları takip etmek ve raporu üretmek için ekipler çoğunlukla bir bulgu veritabanı + şablon sistemi kullanır. Bunun değeri: aynı bulgu türünü (ör. "eksik güvenlik başlıkları") her angajmanda sıfırdan yazmazsın, kaliteli bir kütüphaneden çeker ve bağlama uyarlarsın. Tuzak: şablonu uyarlamayı unutmak. Bir müşteriye başka müşterinin sunucu adının kaldığı bir rapor göndermek, kariyer bitiren türde bir hatadır. Teslim öncesi her rapor, başka bir çift göz tarafından "kopyala-yapıştır artığı" için taranmalıdır.

**Ekran görüntüsü ve redaksiyon.** Ekran görüntüsü kanıtın belkemiğidir ama iki tuzağı vardır: (1) hassas veri sızdırmak, (2) okunamaz / bağlamsız görüntü. İyi kanıt görüntüsü, iddiayı kanıtlayan minimum bilgiyi gösterir, gerisini maskeler; ve altında bir cümle bağlam taşır ("Şekil 3: kimlik doğrulaması olmadan erişilen yönetici paneli, kullanıcı listesi maskelenmiştir"). Maskelemeyi düzgün yap — siyah dikdörtgeni PDF'te üstüne koyup altındaki metni seçilebilir bırakmak klasik bir ifşa hatasıdır; veriyi gerçekten sil, üstünü örtme.

**MITRE ATT&CK eşleme.** Modern raporlarda saldırı adımlarını ATT&CK teknikleriyle eşlemek neredeyse standart oldu. Değeri: mavi takıma ortak bir dil verir, tespit boşluklarını haritalar, ve raporun bulgularını doğrudan bir tespit yol haritasına bağlar. Aşırıya kaçma tuzağı: her satıra bir teknik ID yapıştırıp raporu jargon çorbasına çevirmek. Eşleme okuyucuya hizmet etmeli, gösteriş yapmamalı.

**CVSS / puanlama araçları.** CVSS hesaplayıcıları puanı üretir ama *kararı üretmez*. Aracı kullan, sonra çıkan skoru kendi bağlamsal yargınla düzelt ve bu düzeltmeyi raporda şeffafça belgele: "CVSS taban skoru yüksek, ancak varlığın ağ izolasyonu nedeniyle ortam riskini orta olarak değerlendiriyoruz." Bu şeffaflık, seni skoru körü körüne kopyalayan bir araç operatöründen ayırıp bir danışman yapar.

**Redaksiyon ve teslim güvenliği.** Rapor, bir müşterinin bütün zayıflıklarının haritasıdır — yani sızarsa saldırgan için bir hazine. Bu yüzden teslim kanalı önemlidir: şifreli, doğrulanmış, ve erişimi sınırlı. Raporu düz e-posta ekiyle göndermek, angajman boyunca koruduğun her şeyi son adımda çöpe atmaktır. Teslim sonrası saklama süresi ve imha politikası da sözleşmede netleştirilmeli.

**Kalite kontrol / eş gözden geçirme (peer review).** Hiçbir ciddi rapor tek kişinin elinden çıkıp müşteriye gitmez. İkinci bir kıdemli operatör şunları denetler: teknik doğruluk, risk derecelerinin savunulabilirliği, dil ve ton, kopyala-yapıştır artıkları, hassas veri sızıntısı, ve "bu öneri gerçekten uygulanabilir mi?" testi. Bu adımı atlayan ekipler, güvenilirliklerini tek bir hatalı raporla kaybeder.

**Gerçek dünya notu — zamanlama.** Rapor yazımına angajman süresinin sonuna sadece küçük bir dilim ayıran ekipler sürekli acele ve kalitesiz teslim yapar. Kıdemli pratik: angajman planında raporlamaya, teknik çalışmanın yaklaşık üçte biri kadar zaman ayır. "Teknik iş bitti, artık iş bitti" düşüncesi acemiliktir; teknik iş bittiğinde işin *yarısı* bitmiştir.

---

### Kapanış yargısı

Kırmızı takım raporu, saldırının değil savunmanın belgesidir. Onu iyi yapan şey, ne kadar derin ele geçirdiğin değil, karşıdaki mühendisin raporu okuyup *ne yapacağını net olarak bilmesi* ve yöneticinin *neden umursaması gerektiğini anlaması*dır. En iyi operatörler saldırıda ne kadar iyiyse yazımda da o kadar iyidir; çünkü müşteri için değer, ele geçirilen sunucuda değil, o sayfalarda yaşar. Rapor dürüst, kanıtlı, önceliklendirilmiş ve uygulanabilir olduğunda, kırmızı takım işini yapmış olur: müşteriyi bir sonraki gerçek saldırgana karşı biraz daha güçlü bırakmak.
