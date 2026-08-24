# Active Directory Saldırı Yolu Metodolojisi (BloodHound Odaklı)

> **Çerçeve:** Bu metin yetkili bir güvenlik testi (pentest / red team engagement) bağlamında yazılmıştır. Amaç, saldırıyı savunma için anlamak ve bir profesyonelin bir Active Directory ortamına *nasıl düşünerek* yaklaştığını aktarmaktır. Metin operasyonel bir "kopyala-yapıştır saldırı reçetesi" değil; karar ağacı, yargı ve metodoloji anlatısıdır. Çalışan exploit veya izinsiz hedefe uygulanacak adım-adım komut dizisi içermez.

---

## 1. Bu aşama neyi hedefler, engagement'taki yeri

Bir Active Directory değerlendirmesinde "saldırı yolu" aşaması, dış çevre atlatıldıktan (phishing, dış servis, ya da assumed-breach başlangıç noktası) sonra başlar. Çoğu modern red team engagement zaten **assumed-breach** modelinde başlar: müşteri sana etki alanına bağlı bir makinede düşük yetkili standart bir kullanıcı verir ve soru şudur — "Bu ayak izinden Domain Admin'e veya belirtilen kritik varlığa (crown jewel) kaç adımda, hangi yolla ulaşabilirsin ve bu yolun neresinde biz sizi görebilirdik?"

Bu aşamanın engagement içindeki asıl değeri "DA aldık" demek değildir. Değer, **saldırı yolunu görünür kılmaktır**: hangi yanlış yapılandırma zinciri, hangi aşırı yetkilendirilmiş grup, hangi unutulmuş servis hesabı bir düşük yetkili kullanıcıyı etki alanı hâkimiyetine taşıyor? Olgun bir raporun çıktısı "Mimikatz çalıştırdık" değil, "şu 4 kenarı (edge) koparırsanız bu yolların %80'i ölür" cümlesidir.

Kritik zihniyet farkı: AD'de sen bir "zafiyet" (patch'lenmemiş CVE) aramıyorsun. **İlişkileri ve yanlış yapılandırmaları** arıyorsun. AD'nin kendisi bir zafiyet değil; ona verilen izinlerin toplamı saldırı yüzeyidir. Bu yüzden AD saldırı yolu analizi bir grafik (graph) problemidir — ve BloodHound tam olarak bunu çözmek için var: düğümler (kullanıcılar, gruplar, bilgisayarlar, GPO'lar, OU'lar) ve aralarındaki yetki kenarları.

---

## 2. Metodoloji ve karar ağacı (asıl değer)

### 2.1. Önce yön: "kim olduğumu" değil "neye dokunabildiğimi" sor

Acemi eline bir hesap geçince "bu hesap admin mi?" diye sorar. Profesyonel şunu sorar: **"Bu hesap, hedefe giden grafikte nerede duruyor ve hangi kenarlara sahip?"** Domain Admin olmak bir hedef değil, bir sonuçtur. Gerçek hedef genelde müşterinin tanımladığı crown jewel'dir (SWIFT sunucusu, kaynak kodu deposu, ERP DB'si). Bazen oraya DA'den geçmeden, tamamen yatay bir yoldan varılır — ve daha sessizdir.

### 2.2. Enumerasyon sırası: geniş ve pasiften, dar ve aktife

Karar ağacının kökü toplama stratejisidir. Sıralama şöyle düşünülür:

1. **Ağ ve oturum bağlamı (yerel, gürültüsüz).** Bulunduğun makinede neredesin? Hangi domain, hangi site, hangi subnet? Mevcut bağlantılar ve oturumlar ne söylüyor? (ATT&CK **T1049 – System Network Connections Discovery** buraya oturur.) Bu, "hangi DC'ler var, ben nereye yakınım" sorusuna ilk cevaptır ve tamamen normal görünen komutlarla yapılabilir.

2. **Etki alanı grup ve yetki topolojisi.** Hangi ayrıcalıklı gruplar var, kim üye? (ATT&CK **T1069.002 – Permission Groups Discovery: Domain Groups**.) `net group /domain` gibi yerleşik araçlar veya LDAP sorguları bu resmi çıkarır. Buradaki yargı: sadece "Domain Admins" grubuna bakma. Tier-0'ı gizleyen iç içe (nested) gruplara, yardım masası gruplarına, "geçici" olarak birine verilmiş ve unutulmuş yetkilere bak.

3. **Grafik toplama (BloodHound collector).** Bu, tüm ilişkileri tek seferde çeken adımdır. Karar burada verilir: **ne kadar agresif toplayacağım?** Session toplama (kimin nerede oturum açtığı) en değerli ama en gürültülü veridir; ACL toplama daha sessizdir ama session'sız yollar eksik kalır. Pro, engagement'ın gizlilik gereksinimine göre collection method'unu ayarlar — DCOnly (sadece DC'den LDAP, session yok, çok sessiz) mi, yoksa tam toplama mı?

**Karar kuralı:** Gizlilik yüksek öncelikliyse önce DCOnly çek, grafiği çıkar, sonra sadece *ihtiyaç duyduğun* birkaç makinede hedefli session toplaması yap. Toplu, tüm ağı tarayan session collection en çok yakalatan davranıştır.

### 2.3. Grafiği okuma: "shortest path" tuzağı

BloodHound'un "Shortest Path to Domain Admins" düğmesi acemiyi yanıltır. En kısa yol her zaman **en uygulanabilir** yol değildir. Profesyonelin grafik okuma yargısı şu eksenlerde çalışır:

- **Kenarın maliyeti/riski:** Bir `CanRDP` kenarı ile bir `MemberOf` kenarı aynı değildir. Bazı kenarlar tamamen pasif kullanılabilir (grup üyeliği zaten var), bazıları aktif ve gürültülü sömürü gerektirir (ör. bir credential dump). Pro, yolları "gürültü bütçesine" göre sıralar.
- **Ön koşul zinciri:** `Hedef hesabın parolasını değiştirebilirim` kenarı (ForceChangePassword) güçlüdür ama parolayı değiştirmek gürültülüdür ve o hesabın sahibini kilitleyebilir — tespit ve iş etkisi riski. Buna karşılık `bu hesabın Kerberos biletini isteyebilirim` gibi bir yol daha sessiz olabilir.
- **Fan-in / fan-out analizi:** Hangi düğüm grafikte bir "boğaz" (chokepoint)? BloodHound'daki "en çok yola dahil olan varlıklar" bakışı, hem saldırı önceliği hem savunma tavsiyesi için altındır. Tek bir aşırı yetkili servis hesabı yüzlerce yolun kesişim noktasıysa, hem senin ilk hedefin odur hem de raporundaki bir numaralı bulgu.

### 2.4. Yola göre dallanma — "şunu görürsem şuraya giderim"

Grafik çıktıktan sonra karar ağacı şu tipik dallara ayrılır. (Aşağıdakiler *kavramsal* dallardır; her biri bir yanlış yapılandırma sınıfına karşılık gelir.)

- **Görürsem: aşırı yetkili ACL kenarı (GenericAll / WriteDacl / Owns bir kullanıcı/grup üzerinde).**
  Yargı: Bu, "hedefi ele geçirmeden hedefin üzerinde hak kazandığım" durumdur. En temiz yollardan biridir çünkü genelde exploit değil, **kötüye kullanılan meşru yetkilendirme** gerektirir. Öncelik yüksektir. Ama iş etkisine dikkat — bir grubun DACL'ini değiştirmek kalıcı iz bırakır ve geri alınması gerekir (engagement sonunda temizlik yükümlülüğü).

- **Görürsem: Kerberoast'lanabilir servis hesabı (SPN'i olan, yüksek yetkili bir hesap).**
  Yargı: Servis hesabının bilet parçasını isteyip çevrimdışı parola kırma denemesi, çok sessiz bir yoldur çünkü meşru bir Kerberos işlemidir. Ama **karar kriteri parolanın kırılabilirliğidir.** 25+ karakter rastgele bir gMSA (group Managed Service Account) parolasını kırmaya çalışmak zaman kaybıdır. Pro, önce hesabın ne zaman oluşturulduğuna / parola politikasına bakıp "bu kırılır mı" diye tahmin eder; her SPN'i körlemesine denemez.

- **Görürsem: DA'nın oturum açtığı bir makinede yerel yönetici hakkım var.**
  Yargı: Klasik "session → credential" yolu. Ama en riskli daldır: kimlik bilgisi çıkarma, EDR'ın en çok izlediği davranıştır. Pro buraya son çare olarak, alternatif ACL yolları tükendiğinde gider ve gitse bile en az gürültülü yöntemi seçer.

- **Görürsem: Delegasyon yanlış yapılandırması (unconstrained / constrained / resource-based).**
  Yargı: Bunlar AD'nin en güçlü ama en az anlaşılan yollarıdır. Unconstrained delegation'a sahip bir makineyi ele geçirmek, oraya kimlik doğrulayan herhangi bir yüksek yetkili biletini yakalama fırsatı verir. Karar kriteri: o makineye Tier-0 bir varlığı kimlik doğrulamaya *ikna edebilecek* bir tetikleyicin var mı? Yoksa teorik bir yoldur, uygulanamaz.

### 2.5. Zincirin sonu: etki alanı çoğaltma (DCSync) ve neden "son" olduğu

Karar ağacının çoğu dalı, yeterli hak biriktiğinde tek bir güçlü yeteneğe yakınsar: **etki alanı çoğaltma haklarına (DS-Replication-Get-Changes / -All) sahip olmak.** Bu haklar, bir DC'yi taklit ederek replikasyon isteğiyle parola verilerini çekmeyi mümkün kılar — ATT&CK'te **T1003.006 – DCSync** budur. Bu genelde Domain Admins, Enterprise Admins, Administrators üyeliği veya DC'nin kendi makine hesabıyla gelen bir yetkidir.

Neden bunu zincirin *sonuna* koyarız? Çünkü:
- Bu, ele geçirmenin **kanıtı ve kalıcılığın kaynağıdır**, keşif değil. KRBTGT hash'ini çekmek Golden Ticket kapısını açar (T1558.001), ki bu tam etki alanı hakimiyeti demektir.
- Aynı zamanda **en yüksek değerli tespit sinyalidir.** Bir DC dışı hosttan gelen replikasyon isteği neredeyse her zaman kötü niyetlidir. Yani DCSync'e ancak "artık hedefe ulaştım, bunu kanıtlıyorum" noktasında, bilinçli ve rapor için başvurulur — keşif turunda savrukça değil.

Metodolojik ilke: **DCSync bir başlangıç değil, bir kapanıştır.** Onu erken kullanmak, elindeki en gürültülü kartı en erken oynamaktır.

### 2.6. Araç transferi kararı: mümkün olduğunca "yaşayan araçlarla"

Zincirin herhangi bir yerinde ek araç gerekebilir (ATT&CK **T1105 – Ingress Tool Transfer**). Buradaki pro yargısı: **her indirilen ikili dosya bir tespit fırsatıdır.** Modern EDR, `certutil` / `bitsadmin` / PowerShell downloadString gibi indirme LOLBin'lerini yakından izler. Karar kuralı: önce hedefte zaten var olan yerleşik araçlarla (living-off-the-land) yapabiliyor musun? Yapamıyorsan, transferi C2 kanalının içinden mi yoksa ayrı bir protokolden mi yapacaksın? Ayrı, meşru görünen bir kanal (ör. iç dosya paylaşımı) genelde harici bir indirmeden daha az dikkat çeker. Pro, "gerekli mi?" sorusunu her transferden önce sorar.

---

## 3. Acemi vs pro: yaygın hatalar, gözden kaçanlar, verimsizlikler

**1. Acemi tüm ağı tarar; pro hedefli toplar.** En sık ölümcül hata, ilk gün tüm domain'e karşı agresif, tam session toplaması yapmaktır. Bu, mavi takımı ilk saatte uyandırır. Pro önce sessiz DCOnly grafiği alır, yolu planlar, sonra sadece kritik birkaç makinede hedefli aktif toplama yapar.

**2. Acemi "shortest path"e tapar; pro yolları risk/gürültüye göre sıralar.** En kısa yol bir credential dump gerektiriyor ama üç adım uzun bir yol tamamen meşru ACL kötüye kullanımıysa, uzun yol daha iyi yoldur.

**3. Acemi her Kerberoast'lanabilir hesabı kırmaya çalışır; pro kırılabilirliği önden değerlendirir.** gMSA ve makine hesabı parolaları pratikte kırılamaz. Zamanını gerçekten zayıf parolalı, insan tarafından oluşturulmuş eski servis hesaplarına harca.

**4. Nested (iç içe) grup üyeliğini gözden kaçırmak.** Bir kullanıcı doğrudan "Domain Admins"te değildir ama üç kat iç içe bir grup zinciriyle etkin olarak DA'dir. BloodHound bunu gösterir; `net group` çıktısına elle bakan acemi kaçırır. Grafik tam olarak bunun için var.

**5. Tier-0 sınırını anlamamak.** Acemi bir "yönetici" gördüğünde onu eşit değerde sayar. Pro, Tier-0 (DC'ler, AD'yi yöneten hesaplar/GPO'lar) ile Tier-1/2'yi ayırır. Bir workstation admin'i ile bir DC admin'i arasındaki fark, tüm yolun anlamını değiştirir.

**6. Veriyi bir kez toplayıp donduran hata.** AD canlı bir ortamdır; oturumlar dakikalar içinde değişir. Bir gün önceki session verisine göre plan yapıp "DA burada oturumda" diye gidince kimseyi bulamamak klasiktir. Pro, kritik adımdan hemen önce o makineye özel taze session bilgisi doğrular.

**7. Temizlik ve iş etkisini unutmak.** ForceChangePassword ile bir hesabın parolasını değiştirmek yolu açar ama gerçek kullanıcıyı kilitleyebilir ve engagement sonunda geri alınması gereken bir değişikliktir. Acemi "işe yaradı" der; pro değişikliği not eder, sahibini etkilemeyecek alternatifi tercih eder, temizlik listesi tutar.

**8. Kapsam ve yetki sınırını grafik heyecanına kurban etmek.** BloodHound bazen kapsam dışı bir domain trust'a giden cazip bir yol gösterir. Yetkili test, RoE (Rules of Engagement) ile sınırlıdır. Grafikte yol görünüyor olması onu yürüme iznin olduğu anlamına gelmez.

---

## 4. Savunma köprüsü (mavi takım): bu aşama savunmacı için ne demek

Kırmızının her adımı savunmacıya bir tespit ve sertleştirme fırsatı bırakır. Bu bölüm, aynı metodolojinin savunma tarafındaki yansımasıdır.

**Enumerasyon izleri (T1069.002, T1049).** Toplu LDAP sorguları — özellikle kısa sürede tüm kullanıcı/grup/ACL'i çeken bir hosttan gelenler — anormal bir tarama imzasıdır. Savunmacı için sinyal: normal iş istasyonu, DC'ye karşı tüm dizini çeken bir LDAP oturumu açmaz. Windows olay günlüklerinde dizin hizmeti erişimi (4662) ve gelişmiş LDAP loglaması bu davranışı yakalar. BloodHound benzeri toplama, tek hosttan yoğun 4662/LDAP trafiği olarak görünür. Honeypot (bal küpü) hesaplar — hiç kullanılmayan, cazip görünen "admin" hesapları — bu enumerasyonda dokunulduğunda yüksek güvenilirlikli alarm üretir; AD saldırı yolu izlemesinde en yüksek getirili tek kontroldür.

**DCSync tespiti (T1003.006) — mavi takımın en net kazancı.** Bir DC olmayan kaynaktan gelen replikasyon isteği (Event ID 4662'de DS-Replication-Get-Changes GUID'lerine erişim) neredeyse kesin kötü niyetlidir. Savunmacı için altın kural: **meşru DC'lerin listesini bil; bu listede olmayan bir hesabın/host'un replikasyon istemesi = kritik alarm.** Bu, düşük gürültülü, yüksek güvenilirlikli bir tespittir ve her AD izleme programında ilk kurulacak kuraldır. Ağ tarafında da DRSUAPI (DRSR) trafiğinin sadece DC'ler arasında görülmesi beklenir; başka bir yerde görülmesi araştırma konusudur.

**Kerberoasting izi.** Yüksek yetkili SPN hesapları için anormal miktarda hizmet bileti isteği (Event ID 4769), özellikle zayıf şifreleme türü (RC4/etype 0x17) talepleriyle birlikte, roasting sinyalidir. Savunma: gMSA'ya geçiş (kırılamaz parolalar), zayıf etype'ları devre dışı bırakmak ve SPN'i olan hesapları uzun rastgele parolalarla korumak yolu baştan öldürür.

**Kimlik bilgisi çıkarma ve lateral hareket.** LSASS'a erişim, oturum tabanlı yatay hareket ve olağandışı yönetimsel oturum açmalar (Event ID 4624 tür 3/9, 4648) EDR ve kimlik izleme için ana sinyallerdir. Tier ayrımı (Tier-0 hesaplarının asla Tier-1/2 makinelerinde oturum açmaması) bu yolların çoğunu yapısal olarak imkânsız kılar — bu bir tespit değil, bir **mimari savunmadır** ve red team raporunun bir numaralı önerisi genelde budur.

**Araç transferi izi (T1105).** `certutil`, `bitsadmin`, PowerShell indirme cmdlet'leri ve olağandışı giden bağlantılar LOLBin izleme kuralları için klasik tetikleyicilerdir. Uygulama kontrolü (WDAC/AppLocker) ve script block logging bu adımı görünür kılar.

**Savunmacının BloodHound'u kendi lehine kullanması.** En önemli köprü: BloodHound bir saldırı aracı olduğu kadar bir **savunma denetim** aracıdır. Mavi takım aynı grafiği kendi ortamına çalıştırıp "Domain Admins'e giden en kısa yolları" kendisi arar ve o kenarları koparır. "Aşağıdaki 5 aşırı yetkili ACL'i kaldırırsanız, düşük yetkili kullanıcılardan DA'ya giden yolların %X'i yok olur" cümlesi hem saldırganın hem savunmacının aynı grafikten çıkardığı ortak sonuçtur. Chokepoint analizi savunma önceliklendirmesinin en verimli yoludur — her şeyi düzeltmeye çalışmak yerine en çok yola dahil olan birkaç düğümü sertleştir.

---

## 5. Araçlar ve gerçek dünya notları

**BloodHound (ve SharpHound / AzureHound toplayıcıları).** Ekosistemin merkezi. SharpHound Windows AD verisini, AzureHound Entra ID (Azure AD) verisini toplar; BloodHound bunları Neo4j grafik veritabanında ilişki olarak modelleyip sorgulanabilir kılar. Pratik notlar:
- **Collection method seçimi kritiktir.** DCOnly en sessiz (sadece DC'ye LDAP, session yok); Session toplama en değerli ama en gürültülü. Engagement gizlilik seviyesine göre seç.
- Topladığın veri **zaman damgalıdır ve bayatlar.** Session verisi özellikle uçucudur. Planını uygulama anına yakın taze veriyle doğrula.
- **Cypher sorguları** BloodHound'un asıl gücüdür. Hazır "shortest path" düğmeleri yüzeyi gösterir; özel Cypher ile "şu kritik varlığa dokunabilen, parolası eski, SPN'i olan hesaplar" gibi hedefli sorular sorulur. Custom sorgu yazabilmek acemiyi proden ayırır.
- Community Edition ile eski legacy sürüm arasında UI/özellik farkları var; sürüm uydurmaya gerek yok — kavram aynı: topla, grafikle, en değerli chokepoint'i bul.

**LDAP / yerleşik araçlar (living-off-the-land).** `net group /domain`, LDAP sorguları, PowerShell'in dizin sorgulama yetenekleri ve standart AD modülleri. Neden önemli: harici araç indirmeden, tamamen meşru görünen trafikle çok şey enumere edilebilir (T1069.002, T1049). Pro, gürültüyü azaltmak için mümkün olduğunca bunlarla çalışır ve ağır araçları sadece gerektiğinde getirir.

**Impacket paketi.** Kerberos, SMB, DRSUAPI gibi protokolleri Python'dan konuşan araç seti; DCSync dahil birçok teknik için referans uygulama. Gerçek dünya notu: bu araçların ürettiği trafik ve isimlendirme kalıpları savunma tarafında iyi bilinir — yani "işe yarıyor" ile "tespit edilmiyor" aynı şey değildir. Bir tekniğin çalışması onu gizli yapmaz.

**Mimikatz / Rubeus sınıfı araçlar.** Kimlik bilgisi ve Kerberos bilet işlemlerinin klasik araçları. Gerçek dünya notu: bunlar EDR imzalarının en yoğun olduğu araçlardır. Modern engagement'ta çıplak çalıştırılması nadiren mantıklıdır; değer, tekniğin *ne yaptığını* anlamakta, aracın kendisinde değil. Savunma tarafı bu araçları anlamak zorundadır çünkü tespit kurallarının çoğu bunların davranışına göre yazılır.

**Pratik meta-tüyolar:**
- **Gürültü bütçesi tut.** Her aksiyona "bu ne kadar tespit riski üretiyor, bu adım için buna değer mi?" diye bak. En değerli kartları (DCSync gibi) en sona sakla.
- **Grafiği hem saldırı hem rapor için kullan.** Engagement'ın çıktısı ele geçirme değil, **koparılabilir kenarların önceliklendirilmiş listesidir.** Chokepoint'leri işaretle.
- **Değişiklikleri ve temizliği belgele.** Parola/ACL değiştiren her adım, engagement sonunda geri alınmalı ve müşteriye raporlanmalıdır.
- **RoE her şeyin üstündedir.** Grafikte cazip bir trust yolu görünmesi, o domain'e geçme yetkin olduğu anlamına gelmez. Yetki sınırı teknik olasılıktan önce gelir.
- **AD saldırı yolu analizi bir defalık iş değildir.** Ortam sürekli değişir; yeni GPO, yeni grup, yeni servis hesabı yeni yollar açar. Hem saldırı hem savunma tarafında periyodik grafik denetimi tek sürdürülebilir yaklaşımdır.

---

### Kapanış yargısı

Active Directory saldırı yolu metodolojisinin özü tek cümlede: **AD'de zafiyet aramazsın, yetki ilişkilerini haritalar ve en ucuz/sessiz yolla hedefe yakınsarsın; her adımın bir tespit izi bırakır ve olgunluk, o izleri bilerek en değerli kartı en sona saklamaktır.** Savunmacı için aynı grafik, koparılacak kenarların listesidir. İki taraf da aynı haritaya bakar — fark, birinin yol arayıp diğerinin o yolu yok etmesidir. En iyi red team raporu, mavi takıma o grafiği okumayı öğreten rapordur.
