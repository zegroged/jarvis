# Dış Keşif ve OSINT Metodolojisi

> **Çerçeve:** Bu metin yetkili bir güvenlik testi (pentest / red team engagement) bağlamında yazılmıştır. Amaç, bir kırmızı takım operatörünün dış keşif aşamasında *nasıl düşündüğünü* aktarmak ve savunmacının bunu nasıl gördüğünü göstermektir. İçerik metodoloji ve yargı odaklıdır; canlı ya da izinsiz bir hedefe karşı çalıştırılacak adım-adım saldırı reçetesi değildir. Her operasyonun bir kapsam (scope) ve yazılı yetki (authorization / rules of engagement) belgesi vardır — bu belge yoksa keşif bile başlamaz.

---

## 1. Bu aşama neyi hedefler, engagement'taki yeri

Dış keşif, bir angajmanda daha ilk pakete dokunmadan önce başlayan aşamadır. Amacı basit görünür ama aldatıcıdır: **hedefin gerçek saldırı yüzeyini, sahibinin gördüğünden daha net görmek.** Bir kurumun kendi varlık envanteri neredeyse her zaman eksiktir — unutulmuş bir subdomain, satın alınan bir şirketten miras kalan bir IP bloğu, bir stajyerin üç yıl önce açtığı bir demo ortamı. İşte bu "bilinmeyen bilinmezler" saldırganın altın madenidir.

Keşif ikiye ayrılır ve bu ayrım metodolojik olarak kritiktir:

- **Pasif keşif:** Hedefin altyapısına hiç dokunmadan, üçüncü taraf kaynaklardan (arama motorları, sertifika şeffaflık logları, WHOIS, sosyal medya, iş ilanları, veri ihlali derlemeleri) bilgi toplamak. Hedef bunu göremez; iz bırakmaz.
- **Aktif keşif:** Hedefin sunucularına doğrudan paket göndermek — DNS sorguları, port taraması, servis parmak izi, web uygulaması tarayıcıları. Hedef bunu loglarında görebilir.

Engagement içindeki yeri şudur: keşif, sonraki her aşamanın (zafiyet analizi, ilk erişim, yanal hareket) kalitesini belirler. Kötü keşif = kör saldırı = gürültü + başarısızlık. İyi keşif, çoğu zaman testin gerçek exploit'ten *önce* kazanıldığı yerdir. Deneyimli operatörün bildiği acı gerçek: angajmanların çoğu sıfır-gün exploit ile değil, unutulmuş bir varlık üzerindeki basit bir yanlış yapılandırma ile düşer. Keşfin işi o varlığı bulmaktır.

Kapsam disiplini burada başlar. OSINT sırasında sürekli kapsam-dışı varlıklara rastlarsınız — hedefin CEO'sunun kişisel bloğu, bir tedarikçinin sistemi, benzer isimli başka bir şirket. Pro, bulguyu not eder ama kapsam dışına *dokunmaz*; kapsam belgesini müşteriyle netleştirmeden ilerlemez. Bu yasal ve etik bir sınırdır, teknik değil.

---

## 2. Metodoloji ve karar ağacı (asıl değer)

Bu bölüm işin özüdür: pro burada nasıl düşünür, hangi sırayla ilerler, bir bulguyu görünce hangi yöne gider.

### 2.1 Genelden özele, pasiften aktife

Temel prensip: **önce ucuz ve sessiz olanı tüket, sonra gürültülüye geç.** Pasif kaynaklar bedava, risksiz ve çoğu zaman şaşırtıcı derecede zengindir. Aktif tarama pahalıdır — hem tespit riski hem zaman açısından. Bu yüzden karar ağacının kökü şudur:

```
Pasif OSINT tükendi mi?
├── Hayır → devam et (henüz aktif dokunma)
└── Evet  → aktif keşfe geç, ama dar ve hedefli
```

Acemi tam tersini yapar: daha ilk gün tüm IP aralığına port taraması başlatır. Pro, o taramayı yapmadan önce zaten hangi 40 hostun gerçekten ilginç olduğunu pasif kaynaklardan çıkarmıştır.

### 2.2 Ayak izini genişletme (footprinting) döngüsü

Keşif doğrusal değil, **özyinelemeli bir döngüdür.** Her yeni bulgu yeni bir sorgu kaynağı açar:

1. **Tohum (seed):** Elinizde bir kök alan adı ve birkaç bilinen IP var. Kapsam bu.
2. **Organizasyon sınırını çiz:** WHOIS ve bölgesel internet kayıt kuruluşu (RIR) verilerinden, kuruma ait IP bloklarını (ASN) ve tescilli alan adlarını çıkar. Buradaki soru: "Bu kurum internette gerçekten *neye* sahip?"
3. **Alan adı uzayını haritala:** Sertifika şeffaflık (Certificate Transparency) logları burada en değerli tek kaynaktır. Her TLS sertifikası kamuya açık loglanır; bu yüzden `*.hedef.com` altında yayımlanmış her sertifika, size aktif tarama yapmadan subdomain listesi verir. Pasif DNS veritabanları bunu tamamlar.
4. **Genişlet:** Bulunan her subdomain'in çözümlendiği IP'ye bak. Yeni IP bir bloğa işaret ediyorsa → 2. adıma dön. Yeni bir marka adı çıktıysa → yeni WHOIS sorgusu. Döngü, yeni bilgi üretmeyi durdurana kadar sürer.

Karar mantığı: **"Bu bulgu bana yeni bir sorgu kaynağı açıyor mu?"** Açıyorsa döngüye devam. Açmıyorsa bir sonraki katmana geç.

### 2.3 İnsan katmanı: OSINT'in en verimsiz göründüğü ama en çok kazandıran yer

Teknik altyapının yanında bir de insan yüzeyi var: çalışanlar, e-posta formatı, kullanılan teknolojiler, tedarikçiler. Karar ağacı burada şu sinyallere göre dallanır:

- **İş ilanları:** Bir kurumun açtığı ilan, teknoloji yığınını fütursuzca açıklar. "5 yıl X ürünü deneyimi, Y bulut platformu, Z EDR yönetimi" ilanı size hem savunma ürünlerini hem altyapıyı söyler. Pro bunu okur çünkü bu, savunmacının kendi eliyle yayımladığı bir mimari diyagramdır.
- **E-posta adres formatı:** `ad.soyad@` mı, `asoyad@` mı? Bir tanesini doğrulamak, tüm çalışan listesi için kullanıcı adı tahmini üretir. Bu, sonraki aşamaların (parola püskürtme gibi) girdisidir — ama o aşama ayrı bir yetki ve dikkat gerektirir.
- **Veri ihlali derlemeleri:** Kurumsal e-postaların geçmiş ihlallerde açığa çıkıp çıkmadığı, parola yeniden kullanımı riskini gösterir. Bu veri hassastır ve angajmanda kullanımı yazılı olarak kapsamda olmalıdır.

### 2.4 "Şunu görünce şu yöne giderim" — pratik yargı örnekleri

Metodolojinin kalbi bu tür koşullu kararlardır:

- **Çok sayıda subdomain ama hepsi tek bir bulut sağlayıcıya işaret ediyorsa** → altyapı büyük ölçüde dışa alınmış (managed). Odak on-premise'ten bulut yanlış-yapılandırmasına, açık depolama alanlarına, kimlik yönetimine kayar.
- **Bir subdomain kurumun kendi IP bloğunda, geri kalan her şey buluttayken** → bu host bir aykırı değerdir. Genellikle eski, unutulmuş, yamalanmamış bir sistemdir. Dikkat buraya yoğunlaşır. Aykırı değer, keşifte neredeyse her zaman en değerli sinyaldir.
- **`dev.`, `test.`, `staging.`, `uat.`, `old.` gibi önekler** → üretim-dışı ortamlar sıklıkla zayıf kimlik doğrulama, varsayılan kimlik bilgileri ve daha az izleme ile gelir. Öncelik sırasında yükselir.
- **WHOIS gizliliği açıksa ama bir sertifika kayıt e-postası sızmışsa** → o e-posta yeni bir OSINT tohumudur.
- **İş ilanı belirli bir EDR/SIEM ürününü işaret ediyorsa** → sonraki aşamalarda tespit modelini ona göre şekillendirirsin; bu bir "savunmayı anlama" bulgusudur, exploit bulgusu değil.

### 2.5 Önceliklendirme: her şeyi değil, doğru şeyi enumere et

Keşifte üretilen varlık listesi yüzlerce satır olabilir. Pro bunu körlemesine taramaz; bir **değer-risk matrisi** ile sıralar:

- **İlginçlik:** Bu varlık kimlik doğrulama sunuyor mu? Yönetim paneli mi? Veri işliyor mu?
- **Tazelik / bakım:** Terk edilmiş mi görünüyor? (Eski sertifika, eski teknoloji imzaları terk edilmişlik sinyalidir.)
- **Gürültü maliyeti:** Bunu aktif taramak beni ne kadar görünür kılar?

Sıralama çıktığında, aktif keşif *sadece* üst dilime uygulanır. Bu, hem tespit riskini düşürür hem zamanı verimli kullanır.

---

## 3. Acemi vs pro: yaygın hatalar, gözden kaçanlar

**Hata 1 — Erken ve geniş aktif tarama.** Acemi angajmanın birinci saatinde tüm aralığa agresif tarama başlatır. Bunun üç bedeli var: savunmacıyı erken uyandırır, pasif kaynaklardan bedava gelecek bilgiyi gürültüyle boğar, ve çoğu zaman *yanlış* varlıklara zaman harcatır. Pro, aktif taramayı bir cerrahi araç gibi kullanır — dar, hedefli, gerekçeli.

**Hata 2 — Kapsam sürüklenmesi (scope creep).** OSINT ilginçtir; bir bağlantı sizi başka bir şirkete, bir yan kuruluşa, bir çalışanın kişisel varlığına götürür. Acemi bunun peşinden gider. Pro durur ve sorar: "Bu, yazılı kapsamda mı?" Kapsam dışına dokunmak yalnızca etik değil yasal bir ihlaldir ve tüm angajmanı geçersiz kılabilir.

**Hata 3 — Belge tutmamak.** Keşif çıktısı, bulguların *nereden* geldiğini kaydetmeden değersizdir. Rapor aşamasında "bu subdomain'i nasıl buldun?" sorusuna cevap veremezseniz, bulgu savunulamaz. Pro her varlığın yanına kaynağını ve zaman damgasını yazar. Bu aynı zamanda müşterinin bulguyu doğrulayıp kapatabilmesi için gereklidir.

**Hata 4 — Tek kaynağa güvenmek.** Tek bir subdomain aracının çıktısını "gerçek" sanmak. Kaynaklar eskir, yanlış pozitif üretir, birbirini tamamlar. Pro, sertifika loglarını + pasif DNS'i + arama motoru sonuçlarını çapraz doğrular. Bir varlık üç kaynakta da çıkıyorsa güven yüksektir; tek kaynakta çıkıyorsa doğrulama gerekir.

**Hata 5 — İnsan katmanını atlamak.** Acemi sadece IP ve port düşünür. En büyük saldırı yüzeyi çoğu zaman teknik değil, insanidir: e-posta formatı, sızmış kimlik bilgileri, sosyal mühendislik için açık bilgi. Bunu atlamak, angajmanın en verimli yolunu atlamaktır.

**Gözden kaçan 1 — Terk edilmiş varlıklar.** Kurumun envanterinde olmayan ama hâlâ ayakta olan sistemler. Bunlar tam da izlenmedikleri için değerlidir. Aykırı değer avı, keşfin en yüksek getirili işidir.

**Gözden kaçan 2 — Sertifika şeffaflığının gücü.** Yeni operatörler subdomain bulmak için hâlâ agresif aktif teknikler dener; oysa CT logları çoğunu sessizce, pasif olarak verir. Aktif brute-force'a geçmeden önce pasif kuyuyu tam kurutmak gerekir.

**Verimsizlik — Otomasyona kör güven.** Araç zinciri kurup çıktıyı okumadan bir sonraki araca atmak. Pro, her aşamada çıktıya *bakar*, çünkü asıl kararlar (hangi aykırı değer önemli, hangi subdomain terk edilmiş) insan yargısıyla verilir, otomatikleştirilemez.

---

## 4. Savunma köprüsü (mavi takım)

Kırmızı takımın her hareketinin bir savunma karşılığı vardır. Bu aşamada savunmacı için anlam şudur:

### 4.1 Pasif keşif neredeyse görünmezdir — ve bu bir ders

WHOIS sorgusu, sertifika log taraması, arama motoru araştırması sizin loglarınızda *görünmez*. Bu yüzden savunmanın ilk hattı tespit değil, **maruziyet azaltmadır (attack surface reduction):**

- Kendi CT loglarınızı kendiniz izleyin. Saldırgan sertifika loglarından subdomain'lerinizi çıkarabiliyorsa, siz de aynı loglardan *beklenmedik* sertifikaları (örneğin yetkisiz yayımlanmış bir subdomain) yakalayabilirsiniz.
- Düzenli **dış varlık envanteri** çıkarın — saldırganın yaptığı keşfi kendinize karşı yapın. Attack Surface Management pratiğinin özü budur. Bulamadığınız varlığı koruyamazsınız.
- WHOIS gizliliği kullanın, kayıt e-postalarını sızdırmayın, iş ilanlarında teknoloji yığınını gereğinden fazla açık etmeyin.

### 4.2 Aktif keşif iz bırakır

Buradan itibaren tespit devreye girer. Port taraması, DNS bölge transfer denemeleri, web dizin tarayıcıları loglarda desen üretir:

- **Tek kaynaktan geniş port aralığına kısa sürede bağlantı** → tarama imzası.
- **Var olmayan subdomain'lere ardışık DNS sorguları (NXDOMAIN seli)** → subdomain brute-force sinyali.
- **Web sunucusunda kısa sürede yüzlerce 404** → dizin/dosya keşif tarayıcısı.
- **Anormal User-Agent değerleri veya bilinen tarama araçlarının imzaları.**

Savunmacının tespit mantığı, ATT&CK Keşif (Discovery) taktiği altındaki tekniklerle eşleşir. Örneğin bir host ele geçirildikten *sonraki* iç keşif, `systeminfo` (T1082 - System Information Discovery), `net user` / `net localgroup` (T1087.001 - Local Account Discovery), `net view` / `ping` (T1018 - Remote System Discovery) veya `netsh wlan show profiles` (T1016.002 - Wi-Fi Discovery) gibi yerleşik komutların anormal bağlamda çalışmasıyla kendini gösterir. Bu komutlar meşru yönetim işlerinde de kullanıldığı için, tespit "komut çalıştı mı" değil **"kim, hangi süreçten, hangi sıklıkta, hangi diziyle çalıştırdı"** sorusuna dayanır. Bir kullanıcı iş istasyonunda kısa aralıkla art arda `systeminfo`, `net user`, `net group`, `net view` çalışması klasik bir keşif zinciridir ve tek başına her komuttan çok bu *dizilim* alarm üretir.

### 4.3 Savunmacı için asıl mesaj

Dış keşif savunmacıya şunu söyler: **Saldırgan sizi sizden iyi tanıyabilir.** Bu asimetriyi kapatmanın yolu, saldırganın gördüğünü düzenli olarak kendinize karşı görmek — kendi CT loglarını izlemek, dış envanteri güncel tutmak, terk edilmiş varlıkları avlayıp kapatmak, ve iç keşif komut dizilimleri için davranışsal tespit kurmaktır. Keşif "önlenemez" ama görünürlük ve yüzey azaltma ile *değersizleştirilebilir.*

---

## 5. Araçlar ve gerçek dünya notları

Aşağıdakiler kategori ve yaklaşım düzeyinde verilmiştir; belirli sürüm veya "çalıştır-gör" reçetesi değil, hangi işin hangi araç sınıfıyla yapıldığını ve pratik yargıyı içerir.

**Sertifika şeffaflık (CT) arama arayüzleri.** Pasif subdomain keşfinin bel kemiği. Aktif tarama olmadan, yayımlanmış her TLS sertifikasından alan adı çıkarır. Pratik tüyo: CT verisi bazen henüz canlı olmayan (yeni yayımlanmış, DNS'i çözülmeyen) subdomain'leri de gösterir — bunlar "yakında geliyor" sinyalidir ve terk edilmiş kadar ilginç olabilir.

**Pasif DNS veritabanları.** Bir alan adının geçmişte hangi IP'lere çözümlendiğini gösterir. Altyapı geçmişini, taşınmaları, eski hostları ortaya çıkarır. Tek başına CT'yi tamamlayan ikinci bağımsız kaynaktır — çapraz doğrulama için değerli.

**WHOIS ve RIR/ASN sorgu araçları.** Organizasyon sınırını çizmek için. Kuruma ait IP bloklarını ve ASN'i bulmak, "bu kurum neye sahip" sorusunun temel cevabıdır. Not: bulut çağında birçok varlık kuruma değil sağlayıcıya kayıtlıdır; ASN eşlemesi tek başına eksik kalır, bu yüzden alan-adı-merkezli keşifle birleştirilir.

**Arama motoru operatörleri (dork'lar).** Hedefe özgü, dizine girmiş ama unutulmuş sayfaları, açık dizinleri, sızmış belgeleri bulmak için. Tamamen pasif, tamamen iz bırakmaz. Pratik yargı: arama motoru sonuçları eskir; bir sayfa dizinde görünüyor diye hâlâ canlı olduğunu varsaymayın, doğrulayın.

**Subdomain toplama / birleştirme araçları.** Birçok pasif kaynağı (CT, pasif DNS, arama motorları) tek çıktıda birleştiren çerçeveler vardır. Değeri, çok kaynağı otomatik çapraz-referanslamaktır. Tehlikesi: çıktıya bakmadan güvenmek. Her zaman ham listeyi süzün.

**DNS çözümleme ve doğrulama.** Toplanan aday subdomain listesinin hangilerinin gerçekten çözümlendiğini görmek. Burada pasiften aktife geçiş başlar — DNS sorgusu hedefin çözümleyicisine dokunabilir, bu yüzden ölçek ve hız kararı verilir.

**İş ilanı ve sosyal ağ araştırması.** Teknoloji yığını, organizasyon şeması, e-posta formatı ve savunma ürünleri hakkında insan-kaynaklı istihbarat. Otomatikleştirilemez; deneyimli operatörün gözüyle okunur. Bir ilandaki "X EDR yönetimi" satırı, on port taramasından fazla söyler.

### Gerçek dünya notları

- **Bedava ve sessiz olanı önce tüket.** Pasif kaynakların gücünü küçümsemek en yaygın acemi hatasıdır. Angajmanların ciddi bir kısmı hiç aktif tarama yapmadan, sadece pasif OSINT ve doğru okumayla kazanılır.
- **Aykırı değeri kovala.** Herkesin buluta taşındığı bir ortamda tek başına kalmış on-prem host; herkesin `prod` olduğu yerde tek `staging`. Aykırı değer, keşifte sinyalin en yoğun olduğu yerdir.
- **Her şeyi belgele.** Bulgu + kaynak + zaman damgası. Rapor edilemeyen bulgu, yapılmamış iş sayılır; kaynağı belirsiz bulgu ise savunmacı için kapatılamaz.
- **Kapsam kutsaldır.** İlginç ama kapsam-dışı her şey not edilir, dokunulmaz. Kapsamı genişletmek müşterinin yazılı onayıyla olur.
- **Otomasyon araç, karar insan.** Araç zinciri veri toplar; hangi verinin önemli olduğuna operatör karar verir. Keşfin gerçek değeri, ham listeyi *yargıya* dönüştürmektir.

---

## Kapanış: keşif bir liste değil, bir yargı disiplinidir

Dış keşif, "olabildiğince çok veri topla" işi değildir. En iyi operatörler daha *az* ama daha *doğru* topladıkları için iyidir. Metodolojinin özü şu döngüdür: pasiften başla, genelden özele in, her bulguyu yeni bir tohum olarak değerlendir, aykırı değeri kovala, kapsamda kal, her şeyi belgele — ve aktif dokunuşu bir cerrahi araç gibi, sadece gerektiğinde, dar ve gerekçeli kullan.

Savunmacı için ders simetriktir: saldırgan sizi dışarıdan haritalayabiliyorsa, bunu ilk yapan siz olun. Kendi saldırı yüzeyinizi saldırgandan önce görmek — kendi CT loglarını izlemek, dış envanteri güncel tutmak, terk edilmiş varlıkları avlamak — bu aşamada üretilebilecek en yüksek getirili savunmadır. Keşif önlenemez; ama görünürlük ve yüzey azaltmayla değersizleştirilebilir. İki takımın da bu aşamada oynadığı oyun aynıdır: kimin envanteri daha doğru?
