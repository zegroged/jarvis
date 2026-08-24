# C2 ve Operasyonel Güvenlik (OPSEC): Bir Kırmızı Takım Operatörünün Karar Metodolojisi

> Çerçeve: Bu metin yetkili güvenlik testi (pentest / red team engagement) bağlamında yazılmıştır. Amaç, bir profesyonelin komuta-kontrol (C2) altyapısını ve operasyonel güvenliği **nasıl düşünerek** kurduğunu, hangi kararı neye göre verdiğini ve mavi takımın bunu nasıl gördüğünü aktarmaktır. Canlı veya izinsiz bir hedefe adım-adım saldırı reçetesi değildir; metodoloji, yargı ve karar ağacı sunar.

---

## 1. Bu aşama neyi hedefler, engagement'taki yeri

C2 (Command and Control), bir red team operasyonunun omurgasıdır. İlk erişim (initial access) sağlandıktan sonra operatörün ele geçirilen makineyle konuşabildiği kanal budur. Ama C2'yi "bir shell açmak" olarak görmek acemi hatasıdır. C2, engagement'ın **hayatta kalma** katmanıdır: yakalanmadan, alarm üretmeden, savunmacının incident response (IR) sürecini tetiklemeden ne kadar süre operasyonel kalabildiğinizi belirler.

Bir engagement'ın tipik yaşam döngüsünde C2 ve OPSEC şu noktalarda devreye girer:

- **Öncesinde (altyapı kurulumu):** Redirector'lar, domain'ler, sertifikalar, profiller. Bu iş engagement başlamadan **günler-haftalar önce** yapılır. Aceleye getirilen altyapı, ilk günden yanar.
- **İlk erişim anında:** Payload hangi kanala "geri arayacak" (call back)? İlk beacon'ın kendisi bir OPSEC olayıdır.
- **Post-exploitation boyunca:** Her komut, her dosya transferi, her lateral movement adımı C2 üzerinden akar ve iz bırakır.
- **Süreklilik (persistence) ve exfiltrasyon:** Kanalın uzun vadede ayakta kalması, veri çıkışının (T1041 gibi) normal trafik içinde erimesi.

OPSEC ise C2'nin üstüne oturan bir **zihniyettir**, ayrı bir araç değil. "Bu eylem beni ne kadar görünür yapar? Bu görünürlük, elde edeceğim değere değer mi?" sorusunu her adımda sormaktır. Kıdemli operatörle acemiyi ayıran şey araç bilgisi değil, işte bu maliyet-fayda muhasebesini refleks haline getirmiş olmaktır.

Red team engagement'ında amaç "her makineyi ele geçirmek" değil, **savunmanın gerçek tespit ve müdahale kabiliyetini ölçmektir**. Yani bazen kasıtlı olarak gürültü yaparsınız (savunma yakalıyor mu diye), bazen de aylarca sessiz kalırsınız. Bu ayrımı yönetmek OPSEC'in kalbidir.

---

## 2. Metodoloji ve karar ağacı (asıl değer)

### 2.1 Temel soru: "Bu ortamda normal ne?"

Her OPSEC kararı tek bir eksene indirgenir: **çevreye uyum (blend in)**. Bir profesyonel, altyapısını ve davranışını hedefin "normal"ine göre şekillendirir. Dolayısıyla ilk iş enumerasyon değil, **baseline anlamaktır**:

- Bu kurum hangi bulut sağlayıcılarını kullanıyor? (Trafik oraya giderse şaşırtıcı olmaz.)
- Çıkış (egress) trafiği nasıl? Proxy var mı, TLS inspection var mı, DNS dışarı serbest mi?
- Kullanıcılar hangi SaaS'ları kullanıyor? (Slack, Teams, Google, Dropbox...)
- Çalışma saatleri nedir? Gece 03:00'te beacon atan bir makine kaç günde fark edilir?

Bu bilgiler olmadan verilen her C2 kararı kördür. Kıdemli operatör buraya zaman ayırır; acemi doğrudan "hangi C2 framework en iyi" tartışmasına atlar.

### 2.2 Kanal seçimi karar ağacı

Kanal (protokol) seçimi, tespit yüzeyini belirleyen en büyük karardır. Mantık şöyle işler:

**"Egress kısıtlı mı?"**
- **Hayır, HTTP/HTTPS serbest →** Varsayılan tercih HTTPS. Neden? Çünkü kurumsal ağlarda en çok görülen, en az sorgulanan trafik budur. T1048.002'nin (asimetrik şifreli non-C2 protokol üzerinden exfil) mantığı da buradan gelir: TLS zaten her yerde, içine girmek "normal" görünür. Ama dikkat — TLS inspection (SSL/TLS kesme) varsa, şifreleme sizi kurtarmaz; JA3/JA4 parmak izi ve sertifika anomalisi sizi ele verir.
- **Kısmen, sadece proxy üzerinden →** C2'nin sistem proxy'sini kullanabilmesi (proxy-aware olması) şart. Aksi halde ilk beacon anında "proxy'yi baypas etmeye çalışan bir süreç" olarak yanarsınız.
- **Neredeyse kapalı, sadece DNS dışarı çıkıyor →** DNS tünelleme gündeme gelir (T1048'in bir varyantı, DNS subdomain'leriyle veri taşıma mantığı). Ama bu **son çare** düşüncesidir: DNS tünel yavaştır, yüksek hacimli sorgu üretir ve modern DNS güvenlik ürünleri (anomali tabanlı) tam da bunu arar. "DNS tünel = gizli" acemi efsanesidir; aslında gürültülüdür.

**"Hedefin gerçekten güvendiği bir kanal var mı?"**
- Bazı ortamlarda en zekice hamle, kurumun zaten kullandığı meşru bir bulut servisini C2 taşıyıcısı yapmaktır (domain fronting mantığı ya da meşru API'ler üzerinden haberleşme). Buradaki yargı: Trafik meşru bir hedefe (örneğin tanınmış bir CDN veya SaaS) gidiyorsa, ağ savunması onu bloklamakta tereddüt eder. Bu güçlü bir teknik ama kırılgandır — sağlayıcılar domain fronting'i büyük ölçüde kapattı, dolayısıyla "eski blog yazısında okudum, çalışır" varsayımıyla gidilmez; engagement öncesi test edilir.

### 2.3 Beacon davranışı: uyku, jitter ve sabır

Kanal kurulduktan sonra ikinci büyük karar **çağrı ritmidir (callback cadence)**. Burada operatörün karakteri belli olur.

- **Sleep (uyku) süresi:** Beacon ne sıklıkta "check-in" yapacak? Kısa uyku = hızlı etkileşim ama yüksek görünürlük (düzenli aralıklı trafik = beacon imzası). Uzun uyku = düşük görünürlük ama yavaş operasyon.
- **Jitter (sapma):** Uyku süresine rastgelelik katmak. %0 jitter ile tam 60 saniyede bir atan beacon, bir grafikte **mükemmel düz bir çizgi** oluşturur — bu, beaconing tespitinin bir numaralı sinyalidir. Kıdemli operatör jitter'ı yüksek tutar (%30-50), çünkü insan trafiği düzensizdir.

Karar mantığı: **"Bu makinede ne kadar aktif çalışmam gerekiyor?"** Aktif lateral movement yaparken kısa uyku, sadece süreklilik/nöbet tutarken uzun uyku (saatler, hatta günler). Olgun operasyonlarda "gündüz kısa, mesai dışı uzun/sessiz" gibi hedefin çalışma ritmine göre profil değiştirmek yaygındır.

En önemli yargı ise şudur: **Sabır bir silahtır.** Acemi hemen `whoami`, `ipconfig`, `net user /domain` diye ardı ardına komut yağdırır. Kıdemli operatör ilk beacon'dan sonra bazen saatlerce **hiçbir şey yapmaz** — sadece makinenin stabil olduğunu, EDR'ın uyanmadığını doğrular.

### 2.4 "İlk beacon'dan sonra ne enumere ederim?" karar sırası

İlk erişimden sonra bilgi toplama sırası kör bir checklist değildir; **risk-değer sıralamasıdır**. Mantık: önce en düşük riskli, en yüksek değerli, host-üzerinde-yerel (network'e dokunmayan) bilgiyi topla.

1. **Ben kimim ve neredeyim? (düşük risk)** Bağlam bilgisi: kullanıcı, ayrıcalık seviyesi, süreç, entegrasyon. Bunlar çoğunlukla yerel API çağrılarıdır, ağ gürültüsü yapmaz.
2. **Beni ne izliyor? (kritik — çoğu acemi atlar)** Bu makinede hangi EDR/AV var? Hangi güvenlik ajanları çalışıyor? Bu bilgi, sonraki **her** kararı belirler. Savunmayı tanımadan hamle yapmak, gözü kapalı yürümektir.
3. **Ayrıcalık durumu ve token'lar (orta risk).**
4. **Ancak bundan sonra ağ/domain enumerasyonu (yüksek risk).** Domain sorguları (LDAP, SMB taraması) gürültülüdür ve modern savunmada honeypot hesaplar / canary'ler buraya yerleştirilir.

Karar kuralı: **"Bir bilgi hem düşük riskli hem yüksek değerliyse hemen al; yüksek riskliyse önce onu meşrulaştıracak bağlamı topla."** Örneğin domain admin'leri listelemek isteyeceksen, önce bu sorgunun bu kullanıcıdan çıkmasının normal olup olmadığını değerlendirirsin.

### 2.5 Exfiltrasyon: "aynı kanaldan mı, başka kanaldan mı?"

Veri çıkışında iki temel yol vardır ve seçim ATT&CK'te net ayrılır:

- **C2 kanalı üzerinden (T1041):** Zaten var olan, meşrulaşmış kanalı kullan. Avantaj — yeni bir bağlantı açmıyorsun, ek imza yaratmıyorsun. Dezavantaj — hacim. C2 kanalı düşük hacimli komut trafiği için tasarlanmıştır; oradan gigabaytlarca veri geçirirsen, trafik hacmi anomalisi (data volume spike) alarmı çalar.
- **Alternatif protokol üzerinden (T1048):** Ayrı bir kanal aç (FTP, farklı bir HTTPS hedefi, hatta DNS). Avantaj — C2'yi koruyorsun; exfil yanarsa komuta kanalın hayatta kalır (kanal ayrıştırma / channel separation). Dezavantaj — yeni bir bağlantı, yeni bir tespit yüzeyi.

Karar ağacı:
- **Küçük, yüksek değerli veri (kimlik bilgileri, birkaç dosya) →** C2 üzerinden (T1041), sessiz ve basit.
- **Büyük hacim →** Ayrı kanal (T1048) + **staging**: veriyi hedefte topla, sıkıştır, şifrele, sonra parça parça (chunked), hedefin çalışma saatleri içinde, jitter'lı gönder. Steganografi (T1001.002) gibi teknikler tam burada, "veriyi masum görünen bir taşıyıcıya gömme" mantığıyla değerlendirilir — ama bunlar maliyetli ve kırılgandır; her zaman değil, savunmanın derin paket incelemesi yaptığı ortamlarda düşünülür.
- **Kritik yargı:** Exfil, engagement'ın **en riskli anıdır** çünkü hedef, red team'in gerçek amacına (veri) en yakın olduğu noktadır ve DLP (Data Loss Prevention) sistemleri tam buraya odaklanır. Bir profesyonel exfil'i en sona, en kontrollü ana saklar.

### 2.6 Altyapı katmanlama (redirector mantığı)

OPSEC'in fiziksel karşılığı **altyapı ayrıştırmasıdır**. Temel prensip: Hedef, gerçek C2 sunucunuzu (team server) asla doğrudan görmemelidir. Araya **redirector** katmanları girer.

Mantık: Eğer hedefin savunması bir IP'yi bloklar veya bir domain'i yakarsa, sadece **feda edilebilir bir redirector** yanar — arkadaki asıl altyapı ve o güne kadar toplanan tüm operasyon sağlam kalır. Bu, "tek yumurtayı tek sepete koyma" prensibinin operasyonel halidir.

Katmanlama kararları:
- İlk erişim (staging) altyapısı ile uzun-vadeli C2 altyapısını **ayır**. İlk erişim daha çok yanar; oraya asıl altyapıyı bağlamak amatörlüktür.
- Her ana operasyon fazı için ayrı domain/redirector düşün. Bir faz yanınca diğerini kaybetme.
- Domain'lerin "yaşı" ve kategorisi önemlidir. Yeni tescil edilmiş (newly registered) domain'ler birçok proxy'de otomatik şüphelidir; itibarlı, kategorize edilmiş domain'ler tercih edilir.

---

## 3. Acemi vs pro: yaygın hatalar ve gözden kaçanlar

**Hata 1 — Araç fetişizmi.** Acemi "en iyi C2 framework hangisi" tartışır. Pro şunu bilir: framework, imzası **en çok bilinen** şeydir. Varsayılan (out-of-the-box) profillerle çıkılan hiçbir popüler framework, ciddi bir EDR/NDR ortamında bir gün dayanmaz. Değer araçta değil, **onu ortama nasıl uyarladığında** (profil, sertifika, davranış).

**Hata 2 — Baseline'ı atlamak.** Ortamın normalini anlamadan kanal seçmek. DNS'in serbest olduğunu varsayıp DNS C2 kurmak, oysa kurum tüm DNS'i tek bir denetlenen resolver'a zorluyor — ilk sorguda yanarsın.

**Hata 3 — Sabırsızlık.** İlk shell heyecanıyla komut yağdırmak. Bir EDR için "yeni oluşan bir süreçten 10 saniye içinde art arda gelen keşif komutları" klasik bir davranışsal imzadır. Pro, komutları zaman içine yayar ve mümkünse yerleşik (built-in / living-off-the-land) araçları tercih eder.

**Hata 4 — Jitter'sız, düz beacon.** En sık ve en aptalca yakalanma. Mükemmel periyodik trafik, network savunmasının aradığı ilk şeydir. Bunu düzeltmek bir ayar meselesidir ama acemi bilmediği için yapmaz.

**Hata 5 — Kanal ayrıştırmaması.** Exfil'i, keşfi, süreklilik trafiğini hep aynı kanaldan aynı hedefe akıtmak. O tek hedef yandığında **tüm operasyon** çöker.

**Hata 6 — Log ve iz hijyeni yokluğu.** Kendi araçlarını hedefin diskine bırakıp temizlememek, geçici dosyaları unutmak. Engagement bitince rapor için değil, operasyon sırasında IR'ı beslememek için iz yönetimi gerekir.

**Hata 7 — Altyapıyı yeniden kullanmak.** Bir engagement'ta yanan bir domain/IP'yi başka bir müşteride kullanmak. Threat intel toplulukları bu göstergeleri (IOC) paylaşır; yanmış altyapı kalıcı olarak kirlidir.

**Gözden kaçanlar:**
- **Zaman dilimi tutarsızlığı:** Operatörün kendi çalışma saatleri (örneğin başka bir kıtada) beacon aktivitesine yansır; hedefin gece 04:00'ünde yoğun aktivite anomalidir.
- **Canary/honeytoken'lar:** Modern savunma sahte hesaplar, sahte dosyalar, sahte kimlik bilgileri serper. Acemi bunlara dokunur ve anında ışıldar. Pro, "fazla kolay" görünen her şeye şüpheyle yaklaşır — bal küpü (honeypot) refleksi.
- **Bağlamın değeri:** İlk beacon'da EDR envanterini çıkarmayı unutmak; sonra "neden yakalandım" diye şaşırmak.

---

## 4. Savunma köprüsü (mavi takım perspektifi)

Kırmızı takımın her OPSEC kararı, mavi takım için bir **tespit fırsatıdır**. İyi bir operatör "beni nasıl yakalarlar" diye düşünerek çalışır; iyi bir savunmacı da tam tersini yapar. Bu aşamanın savunmacıya bıraktığı izler:

**Ağ katmanında (NDR / proxy / DNS logları):**
- **Beaconing tespiti:** Düzenli aralıklı, benzer boyutlu, aynı hedefe giden bağlantılar. Jitter düşükse trafik grafiğinde ritim belli olur. Savunmacı burada bağlantı zaman serilerinin düzenliliğine (periodicity) bakar.
- **TLS parmak izi:** JA3/JA4 gibi istemci parmak izleri, sertifika anomalileri (kendinden imzalı, tuhaf CN, kısa ömürlü sertifikalar), SNI ile gerçek hedef uyumsuzluğu.
- **DNS anomalisi:** Anormal uzunlukta subdomain'ler, tek domain'e yüksek hacimli TXT/NULL sorguları, yüksek entropili isimler — DNS tünelin klasik izleri.
- **Yeni/nadir hedefler:** İlk kez görülen domain, yeni tescilli domain, tek bir host'un konuştuğu tek bir dış IP.
- **Veri hacmi anomalisi:** Bir iç host'tan dışarı olağandışı upload hacmi — exfil'in (T1041/T1048) ağ imzası. Buna DLP kuralları eşlik eder.

**Uç nokta katmanında (EDR):**
- **Süreç soyağacı (process lineage):** Bir Office uygulamasından script yorumlayıcısının doğması, oradan ağ bağlantısı çıkması — davranışsal zincir.
- **Ağ yapan beklenmedik süreçler:** Normalde dışarı konuşmaması gereken bir binary'nin egress yapması.
- **LOLBin kötüye kullanımı:** Meşru sistem araçlarının olağandışı argümanlarla, olağandışı ebeveyn süreçlerle çalışması.

**Savunmacı için pratik çıkarımlar:**
- **Baseline oluştur:** Kendi ağının "normal"ini bilmeden anomaliyi göremezsin. Kırmızı takım senin normalini öğreniyor; sen de öğrenmelisin.
- **Beaconing avı otomatikleştirilebilir:** Bağlantıların düzenliliğini, jitter'ını, boyut tutarlılığını ölçen analitikler kur.
- **Honeytoken ek:** Sahte kimlik bilgileri, canary dosyaları, sahte ayrıcalıklı hesaplar. Bunlara dokunulması **yüksek güvenilirlikli** bir alarmdır — çünkü meşru kullanıcının onlara dokunma sebebi yoktur.
- **Egress'i sıkılaştır:** DNS'i denetlenen resolver'lara zorla, TLS inspection uygula, yeni tescilli domain'lere karşı politika koy, sadece iş için gerekli çıkışa izin ver. Kırmızı takımın kanal seçim ağacındaki her "kolay" dalı kapatmış olursun.
- **Kanal ayrıştırmasını tersine çevir:** Operatör operasyonunu katmanlıyor; sen de tespitini katmanla. Ağda kaçırdığını uçta yakala, uçta kaçırdığını kimlik katmanında (anormal oturum) yakala.

Kırmızı-mavi köprüsünün özü şudur: **Bir engagement'ın gerçek çıktısı, "içeri girdik" değil, "sizi şu noktada yakalayabilirdiniz, şu noktada yakalayamadınız" haritasıdır.** OPSEC ne kadar iyiyse, savunmanın hangi katmanının kör olduğu o kadar net ortaya çıkar.

---

## 5. Araçlar ve gerçek dünya notları

Burada belirli sürüm veya sahte araç uydurmadan, **kategori ve yargı** düzeyinde konuşuyorum. Doğru soru "hangi araç" değil, "bu araç sınıfı hangi kararı destekliyor".

**C2 framework'leri (kategori olarak):** Ticari (örneğin sektörde yaygın kullanılan ödemeli framework'ler) ve açık kaynak (topluluk framework'leri) diye ikiye ayrılır. Pratik not: Popüler framework'lerin **varsayılan imzaları herkes tarafından bilinir** — savunma ürünleri bu imzaları özellikle arar. Değer, framework'ü **profillendirme** kabiliyetindedir: trafiğin nasıl göründüğünü, hangi URI'lara gittiğini, hangi başlıkları taşıdığını hedefin normaline uydurma. Malleable/özelleştirilebilir profil desteği olmayan bir araç, ciddi ortamda kısa ömürlüdür.

**Redirector ve altyapı otomasyonu:** Altyapıyı elle kurmak hem yavaş hem hata yapmaya açıktır. Altyapı-as-code (otomatik provizyon) yaklaşımı, aynı katmanlı yapıyı tekrarlanabilir ve **feda edilebilir** hale getirir. Pratik tüyo: Altyapıyı, tek bir feda edilebilir parça yandığında dakikalar içinde yenisini ayağa kaldırabileceğin şekilde kur. Kalıcılık altyapının sağlamlığından değil, **hızlı yenilenebilirliğinden** gelir.

**Trafik meşrulaştırma (redirector + web sunucusu):** Redirector'ın sadece C2 trafiğini geçirip, alakasız/tarayan istekleri masum bir yere yönlendirmesi (gerçek bir siteye redirect) önemlidir. Bir güvenlik analisti C2 domain'ini elle ziyaret ettiğinde masum bir sayfa görmeli, bir 404 ya da tuhaf bir yanıt değil.

**Sertifika ve TLS:** Ücretsiz, otomatik sertifika sağlayıcıları TLS'i kolaylaştırdı ama bu iki ucu keskin bir kılıç — savunma da bu sağlayıcıların desenlerini biliyor. İtibarlı, düzgün yapılandırılmış sertifikalar gerekli; kendinden imzalı veya varsayılan sertifikalar anında yanar.

**DNS altyapısı:** DNS C2 düşünülüyorsa, kayıtların (NS delegasyonu) düzgün kurulması ve sorgu hacminin hedefin normaline sığması gerekir. Pratik yargı: DNS tünel çoğu insanın sandığının aksine gizli değil, **yavaş ve gürültülüdür**; sadece başka çıkış olmadığında, düşük hacimli veri için düşün.

**Payload ve teslimat:** Payload'ın kendisi ayrı bir OPSEC alanı (obfuscation, EDR baypas) — bu ayrı bir konu, ama C2 ile kesişimi şudur: En sağlam C2 altyapısı bile, ilk beacon'ı düşüren payload EDR tarafından anında yakalanırsa işe yaramaz. İkisi birlikte düşünülür.

**Operasyonel disiplin araçları:** Bir operasyon günlüğü (operator log) tutmak — hangi komut ne zaman, hangi host'ta, ne sonuçla çalıştırıldı. Bu hem engagement raporu (mavi takıma "şu saatte şunu yaptık, gördünüz mü") için hem de operasyon sırasında **çift-atış** (aynı işi iki operatörün gürültülü şekilde tekrarlaması) hatasını önlemek için kritiktir. Ekipli operasyonlarda deconfliction (kim ne yapıyor koordinasyonu) OPSEC'in görünmeyen ama hayati parçasıdır.

**Gerçek dünya not — "mükemmel OPSEC diye bir şey yoktur":** Yeterince uzun süre, yeterince aktif kalırsan **bir iz bırakırsın**. Profesyonelin amacı görünmez olmak değil, **savunmanın tepki süresinden daha hızlı hedefe ulaşmak** ve bıraktığı izleri savunmanın **fark edip birleştirme** kabiliyetinin altında tutmaktır. OPSEC bir mutlak durum değil, sürekli bir maliyet-fayda muhasebesidir.

**Gerçek dünya not — kapsam ve yetki her şeyin önünde:** Yetkili bir engagement'ta, ne kadar "gerçekçi" olmak istersen iste, **Rules of Engagement (RoE)** ve kapsam (scope) sınırlarını aşamazsın. Belirli sistemler kapsam dışıysa, DoS yasaksa, belirli saatlerde işlem yasaksa — bunlar OPSEC kararlarının **üstünde** duran çerçevelerdir. Deconfliction hattı (müşteri IR ekibiyle acil temas kanalı) her ciddi red team operasyonunun ön koşuludur: Gerçek bir saldırganla karıştırılırsan, telefonun bir ucunda "bu bizdik" diyebilecek biri olmalı.

---

## Kapanış: OPSEC bir zihniyettir

C2 ve OPSEC'i özetleyen tek cümle: **"Her eylem bir görünürlük maliyeti taşır; profesyonel, her adımda o maliyeti bilinçli öder."** Acemi araç sorar, pro maliyet sorar. Acemi "nasıl girerim" der, pro "girdikten sonra nasıl hayatta kalırım, ne iz bırakırım, savunma beni nerede yakalar" diye düşünür. Ve en olgun operatör, tüm bunları öğrenirken asıl amacın **savunmayı daha iyi yapmak** olduğunu hiç unutmaz — çünkü kırmızının bildiği her yöntem, mavinin kapatabileceği bir kördür.
