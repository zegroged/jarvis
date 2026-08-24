# Kimlik Yönetişimi ve Ayrıcalıklı Erişim Yönetimi (PAM, Tiering Model, Just-In-Time Erişim, PIM)

## Giriş: Neden Kimlik Artık Yeni Çevre (Perimeter) Sayılıyor?

Klasik ağ güvenliği anlayışında savunma "içerisi güvenli, dışarısı tehlikeli" varsayımına dayanırdı: güvenlik duvarı, DMZ, VPN. Ancak modern saldırıların ezici çoğunluğu artık ağ zafiyetiyle değil, **kimlik bilgilerinin (credential) ele geçirilmesiyle** ilerliyor. Bir saldırgan geçerli bir kullanıcı hesabı elde ettiğinde, teknik olarak "içeride" ve "meşru" görünür. Bu nedenle savunmanın ağırlık merkezi ağdan **kimliğe** kaymıştır.

Saldırı tarafında pass-the-hash, Kerberoasting, DCSync, Golden Ticket gibi teknikler yaygın biçimde anlatılır. Ancak bu tekniklerin çoğu, altta yatan tek bir yapısal soruna dayanır: **ayrıcalıklı kimlik bilgilerinin, düşük güvenlikli sistemlere sürekli ve gereksiz biçimde maruz kalması.** Bu makale, işte bu yapısal sorunu ortadan kaldırmayı hedefleyen savunma çerçevesini ele alır: Identity Governance, PAM, Tiering modeli, Privileged Access Workstation, Just-In-Time erişim ve Entra PIM.

Temel savunma tezi şudur: **Bir kimlik bilgisini çalamazsınız, eğer o kimlik bilgisi orada değilse ve o an geçerli değilse.**

---

## 1. Ayrıcalıklı Erişimin Kök Sorunu (Root Cause)

### Kredensiyel Maruziyeti (Credential Exposure)

Bir Domain Admin, bir iş istasyonunda oturum açtığında ya da bir sunucuya uzak masaüstüyle bağlandığında, o hesabın kimlik doğrulama sırları (NTLM hash, Kerberos TGT, bazı senaryolarda düz metin) o makinenin belleğinde (LSASS süreci) bir süre tutulur. Eğer o makine bir saldırgan tarafından ele geçirilmişse, saldırgan orada oturum açmış her ayrıcalıklı hesabın kimlik izlerine erişebilir.

Bunun sonucu **credential theft ve lateral movement** zinciridir:

1. Saldırgan sıradan bir kullanıcı iş istasyonunu ele geçirir (phishing vb.).
2. O makinede bir Helpdesk veya yönetici hesabı yakın zamanda oturum açmıştır.
3. Saldırgan o hesabın kimlik izini çalar ve bir üst yetki seviyesine sıçrar.
4. Bu adım tekrarlanarak sonunda Domain Admin veya Enterprise Admin yetkisine ulaşılır.

Bu zincirin adı sıklıkla **"privilege escalation path"** ya da eski deyimle **"credential theft chain"**tir.

### Sorunun özü

Sorun tek tek tekniklerde değildir; **mimaridedir.** Yüksek yetkili hesapların düşük güvenlikli makinelerde iz bırakması, tüm ortamı bir tek zayıf halka kadar güvenli hale getirir. Savunma çerçevesinin tamamı bu maruziyeti kesmeye çalışır.

---

## 2. Tiering Model (Katmanlama Modeli) ve "Kırmızı Orman"

### Tanım

Microsoft'un tarihsel olarak **Tiered Administration Model** (Katmanlı Yönetim Modeli) olarak adlandırdığı yaklaşım, ortamdaki varlıkları güvenlik hassasiyetine göre katmanlara böler ve **katmanlar arasında kimlik bilgilerinin akmasını yasaklar.**

Klasik üç katman şu şekildedir:

- **Tier 0** — Kimliğin kendisini kontrol eden sistemler: Domain Controller'lar, AD DS, ADFS/federasyon sunucuları, PKI/CA, Entra Connect sunucuları, ve Tier 0'ı yöneten hesaplar. Tier 0 ele geçerse **tüm ortam** ele geçer.
- **Tier 1** — Sunucular ve uygulamalar: veritabanları, uygulama sunucuları, iş yükleri. İş verilerini barındırır ama kimlik altyapısını kontrol etmez.
- **Tier 2** — Son kullanıcı cihazları: masaüstü/dizüstü iş istasyonları, Helpdesk yönetimi.

### Temel kural: Kimlik akışı yalnızca aşağıya, asla yukarıya

Katmanlama modelinin can alıcı kuralı **"control plane" ilkesidir**: Bir üst katmanın kimlik bilgisi, kendinden alt bir katmanda **asla** kullanılmamalıdır.

- Bir Tier 0 hesabı (ör. Domain Admin) Tier 1 sunucusunda veya Tier 2 iş istasyonunda **oturum açmamalıdır.**
- Bir Tier 1 hesabı Tier 2 iş istasyonunda oturum açmamalıdır.

Mantık şu: Alt katman her zaman üst katmandan daha kolay ele geçirilebilir (daha çok kullanıcı, daha çok internet teması, daha çok yazılım). Eğer bir Tier 0 kimliği bir Tier 2 makinesinde iz bırakırsa, o Tier 2 makinesini ele geçiren saldırgan Tier 0'a **anında sıçrar** ve tüm katmanlama çöker. Bu "yukarı doğru kirlenme" (upward credential contamination), modelin engellemek istediği tam senaryodur.

Bu kural iki yönlü düşünülmelidir:
- **Login restriction:** Üst katman hesabı alt katmanda oturum açamaz.
- **Yönetim yönü:** Alt katman bir makine, üst katman bir varlığı yönetemez/kontrol edemez (ör. Tier 1 bir yönetim aracı Tier 0 DC'ye erişmemeli).

### "Kırmızı Orman" (Red Forest / ESAE)

Microsoft geçmişte **ESAE (Enhanced Security Administrative Environment)** adıyla, yönetici kimliklerini ayrı bir güven ormanında (**"Red Forest"**) barındıran bir mimari önerdi. Fikir, üretim ormanı ele geçse bile yönetici kimliklerinin ayrı ve daha sıkı korunan bir ormanda durmasıydı.

Dürüst not: Microsoft bu ESAE/Red Forest yaklaşımını sonraki yıllarda **genel öneri olmaktan çıkardı** (retire etti) ve yerine **"privileged access strategy"** adı altında modern, bulut tabanlı ve JIT/PIM odaklı bir yaklaşımı öne çıkardı. Yani "Kırmızı Orman" kavramsal olarak önemlidir ve niş senaryolarda hâlâ görülebilir, ancak günümüzün varsayılan tavsiyesi değildir. Bunu bilmek, eski dokümanlarla modern rehberliği karıştırmamak için kritiktir.

---

## 3. Privileged Access Workstation (PAW)

### Tanım

Bir **Privileged Access Workstation (PAW)**, ayrıcalıklı görevlerin **yalnızca** üzerinde yapıldığı, sertleştirilmiş, adanmış bir yönetim cihazıdır. Bir yönetici, günlük e-posta/web/ofis işlerini **ayrı** bir standart cihazda yapar; Tier 0 veya hassas yönetim işlemlerini yalnızca PAW üzerinden gerçekleştirir.

### Çalışma mantığı

PAW'ın amacı, yönetici kimliğinin **temiz bir ortamda** kullanılmasını garantilemektir. Standart bir iş istasyonu e-posta ekleri, tarayıcı, üçüncü parti yazılımlar nedeniyle sürekli tehdit yüzeyine maruzdur. Ayrıcalıklı bir kimliği böyle bir makinede kullanmak, en değerli anahtarı en kirli ortamda ortaya koymaktır.

Tipik PAW ilkeleri:

- **Temiz kaynak (clean source) ilkesi:** Bir varlığın güvenliği, onu yöneten sistemin güvenliğine bağlıdır. Tier 0'ı yönetiyorsanız, yönetim cihazınız da Tier 0 güvenlik seviyesinde olmalıdır.
- **İnternet/e-posta izolasyonu:** PAW'dan genel internet gezintisi ve rastgele e-posta erişimi engellenir; yalnızca yönetim uç noktalarına izin verilir.
- **Uygulama kontrolü (application allowlisting):** Yalnızca onaylı yönetim araçları çalışır (ör. WDAC/AppLocker tabanlı politikalar).
- **Ayrı donanım/güçlü izolasyon:** İdeal olarak fiziksel ayrı cihaz; sanal ayrımda ise yönetim ortamı "üstte", kullanıcı ortamı izole edilir (tam tersi değil — çünkü daha güvenli olan alta değil üste konumlanmalı).

### "Jump server" ile karıştırılmamalı

Bir bastion/jump server yararlıdır ama **tek başına yetersizdir**: Eğer yönetici, ele geçmiş bir iş istasyonundan jump server'a bağlanıyorsa, kimlik bilgisi o kirli iş istasyonunda yine iz bırakır. PAW, zincirin **başlangıç noktasını** temizler; jump server erişimi kanalize eder. İkisi tamamlayıcıdır.

---

## 4. Privileged Access Management (PAM)

### Tanım

**PAM (Privileged Access Management)**, ayrıcalıklı hesapların, sırların ve oturumların yaşam döngüsünü yöneten disiplin ve araç kategorisidir. Tipik PAM yetenekleri:

- **Credential vaulting:** Ayrıcalıklı parolalar merkezi bir kasada tutulur; yönetici parolayı asla görmez, oturum kasadan aracılanır.
- **Password/secret rotation:** Kullanım sonrası parolalar otomatik döndürülür; çalınan bir parola kısa sürede geçersizleşir.
- **Session brokering ve kayıt:** Ayrıcalıklı oturumlar proxy üzerinden başlatılır, kaydedilir ve izlenir.
- **Onay iş akışı (approval workflow):** Yükseltilmiş erişim talep-onay sürecine bağlanır.
- **Least privilege uygulaması:** Kalıcı geniş yetki yerine dar, göreve özel yetki.

### PAM ve local admin sorunu: LAPS

Ortak bir kök zafiyet, tüm iş istasyonlarında **aynı yerel yönetici parolasının** kullanılmasıdır. Bu, bir makineyi ele geçiren saldırganın o parolayla tüm makinelere yayılmasına (lateral movement) izin verir. Microsoft'un **LAPS (Local Administrator Password Solution / Windows LAPS)** çözümü, her makineye **benzersiz ve otomatik döndürülen** yerel yönetici parolası atayarak bu yayılma yolunu keser. PAM disiplininin en temel, en yüksek getirili adımlarından biridir.

---

## 5. Just-In-Time (JIT) Erişim ve Zero Standing Privilege

### Tanım

**Just-In-Time (JIT) erişim**, bir kullanıcının ayrıcalıklı yetkiyi **yalnızca ihtiyaç duyduğu an, yalnızca gerekli süre boyunca** almasıdır. İş bittiğinde yetki otomatik geri alınır.

Bunun karşıtı **standing privilege / standing access** — bir hesabın 7/24 kalıcı olarak yüksek yetkiye sahip olmasıdır. Standing privilege, saldırgan için her zaman hazır bir hedeftir: hesabı ele geçirmesi yeterlidir, çünkü yetki zaten aktiftir.

### Zero Standing Privilege (ZSP)

Olgun hedef **Zero Standing Privilege**tir: kimsenin sürekli aktif ayrıcalığı olmaması. Yetki, yalnızca talep + onay + süre penceresi bağlamında var olur. Bu, saldırganın "ele geçirilecek aktif yönetici hesabı" bulma olasılığını dramatik biçimde düşürür.

### JIT'in bileşenleri

- **Just-in-time:** Yetki zamanla sınırlı (ör. 1–8 saat).
- **Just-enough (JEA):** Yetki kapsamla sınırlı — göreve tam yetecek kadar, ne fazla ne eksik. Windows tarafında **JEA (Just Enough Administration)** ile PowerShell üzerinden kısıtlı yönetim yüzeyleri tanımlanabilir.
- **Onay ve gerekçe:** Aktivasyon çoğu zaman onay ve iş gerekçesi (justification) gerektirir.

---

## 6. Entra PIM (Privileged Identity Management)

### Tanım

**Microsoft Entra Privileged Identity Management (PIM)** (eski adıyla Azure AD PIM), Entra ID ve Azure rolleri için **JIT erişimi operasyonel hale getiren** hizmettir. Kavramsal olarak, rol atamalarını iki türe ayırır:

- **Eligible (uygun/aday) atama:** Kullanıcı role sahip *olabilir* ama şu an aktif değildir. Kullanmak için **aktivasyon** yapması gerekir.
- **Active (aktif) atama:** Rol şu an geçerlidir (klasik kalıcı atama gibi).

PIM'in temel savunma değeri, rolleri **eligible** yaparak kalıcı ayrıcalığı ortadan kaldırmaktır. Kullanıcı ihtiyaç anında rolü **aktive eder**, süre dolunca rol otomatik olarak geri düşer.

### Tipik PIM kontrolleri

- **Zaman sınırlı aktivasyon:** Rol yalnızca belirli süre aktif kalır (ör. birkaç saat).
- **Onay gereksinimi (approval):** Kritik roller için bir onaylayıcının onayı istenebilir.
- **MFA zorunluluğu:** Aktivasyon anında güçlü kimlik doğrulama.
- **Gerekçe (justification) ve bilet no:** Neden aktive edildiği kayıt altına alınır.
- **Access review (erişim gözden geçirme):** Kimin hangi role sahip olmaya devam etmesi gerektiği periyodik olarak denetlenir.
- **Kapsamlı denetim günlüğü (audit log):** Her aktivasyon iz bırakır — bu tespit için altın değerindedir.

### Kavramsal ilişki

PIM, Identity Governance'ın (kimin neye, ne zaman, ne kadar süre erişebileceğinin yönetişimi) ayrıcalıklı roller boyutudur. Access review ve entitlement management gibi mekanizmalar "erişimin doğru kişilerde ve güncel kalması"nı; PIM ise "ayrıcalığın kalıcı olmaması"nı sağlar.

---

## 7. Tespit (Detection)

Savunma yalnızca engellemek değil, **ihlal denemesini görmektir.** Bu çerçevenin sağladığı en büyük tespit avantajı, ayrıcalıklı davranışın artık **istisnai ve gözlemlenebilir** hale gelmesidir.

Odaklanılacak tespit sinyalleri:

- **Katmanlama ihlali:** Bir Tier 0 hesabının bir Tier 2 iş istasyonunda oturum açması. Normalde bu **asla olmamalıdır**; olduğunda yüksek öncelikli alarmdır. Windows oturum açma olayları (ör. logon event'leri) hesap–makine eşleşmesiyle izlenebilir.
- **PIM aktivasyonu anomalileri:** Beklenmeyen saatte, olağandışı kullanıcıdan, alışılmadık sıklıkta rol aktivasyonu. PIM audit log bunu doğrudan sağlar.
- **Standing privilege'ın yeniden belirmesi:** Bir hesaba PIM dışında, doğrudan kalıcı yüksek yetki atanması (ör. birinin Global Administrator'ı elle kalıcı atadığı). Bu, süreç ihlali işaretidir.
- **PAW dışından yönetim:** Ayrıcalıklı bir hesabın PAW olmayan bir kaynaktan yönetim işlemi yapması.
- **LSASS erişim girişimleri:** Credential dumping tespiti için LSASS'a olağandışı erişim (EDR sinyali).
- **Sensitive group değişiklikleri:** Domain Admins, Enterprise Admins, Schema Admins gibi Tier 0 gruplarına üye eklenmesi — anlık alarm konusu olmalı.
- **Kerberos anomalileri:** Olağandışı bilet talepleri, zayıf şifreleme talebi gibi Kerberoasting/ticket kötüye kullanım işaretleri (bu makalenin savunma bağlamında: bu gruplara kimin erişebildiğini daraltmak saldırı yüzeyini küçültür).

Tespitin altın kuralı: **Ayrıcalıklı işlemler nadir ve öngörülebilir olmalı; bu sayede her sapma anlamlı bir sinyal olur.** Standing privilege ortamında ayrıcalıklı davranış "gürültü" içinde kaybolurken, JIT/PIM ortamında her aktivasyon net bir kayıttır.

---

## 8. Savunma: Uygulama Öncelik Sırası

Bu çerçeveyi kurmak isteyen bir ekip için pratik, riskten getiriye öncelik sırası:

1. **Tier 0'ı tanımla ve envanterle.** Domain Controller, AD, PKI, federasyon, Entra Connect ve bunları yöneten hesapların tam listesi çıkarılmadan hiçbir şey korunamaz. Çoğu ihlal, "hangi sistemlerin aslında Tier 0 olduğunun bilinmemesinden" beslenir (ör. Tier 0'ı yönetebilen unutulmuş bir yedekleme sunucusu).
2. **LAPS/Windows LAPS uygula.** Yerel yönetici parolalarını benzersizleştirip döndür — en hızlı, en ucuz lateral movement engeli.
3. **Ayrı yönetici hesapları.** Günlük kullanıcı hesabı ile yönetici hesabı **asla aynı** olmamalı; yönetici hesabı e-posta/internet için kullanılmamalı.
4. **Katmanlama oturum açma kısıtlamaları.** Group Policy / authentication policy ile üst katman hesaplarının alt katmanda oturum açmasını engelle (ör. "deny log on" politikaları, Authentication Policy Silos).
5. **PAW devreye al.** En azından Tier 0 yöneticileri için adanmış, sertleştirilmiş yönetim cihazları.
6. **Entra PIM ve JIT'e geç.** Kalıcı yüksek rolleri eligible'a çevir; MFA + onay + zaman sınırı ekle. Zero Standing Privilege'a doğru ilerle.
7. **Access review ve denetim.** Periyodik gözden geçirme ve merkezi audit log toplama (SIEM) ile tespit yeteneğini kur.

---

## 9. Yaygın Hatalar (Common Pitfalls)

- **Tier 0'ı eksik tanımlamak.** Bir yedekleme sistemi, bir EDR yönetim konsolu, bir sanallaştırma yöneticisi (hypervisor) DC'yi kontrol edebiliyorsa **o da Tier 0'dır.** Bunu kaçırmak tüm modeli boşa çıkarır. En sık ve en ölümcül hata budur.
- **JIT/PIM'i kâğıt üzerinde kurup istisnayla delmek.** "Acil durum için" birkaç hesabı kalıcı Global Admin bırakmak, tüm ZSP faydasını yok eder. Break-glass hesapları olmalıdır ama **çok az sayıda, ağır izlenen, yüksek gizlilikli** olmalı — rutin bir bypass değil.
- **PAW'ı jump server ile karıştırmak.** Kirli bir makineden temiz bir jump server'a bağlanmak, kimlik bilgisini yine kirli makinede açığa çıkarır. Zincirin başı temiz değilse gerisi anlamsızdır.
- **Yönetici hesabıyla internette gezmek/e-posta okumak.** Tek bir phishing tıklamasıyla Tier 0 kimliği ele geçer. Ayrık hesap ve ayrık cihaz pazarlık konusu değildir.
- **"Red Forest" reçetesini modern varsayılan sanmak.** ESAE artık genel öneri değildir; bulut çağında PIM/JIT temelli privileged access strategy önceliklidir. Eski dokümana körü körüne uymak, gereksiz karmaşıklık ve yanlış güvenlik hissi doğurur.
- **MFA'yı sadece son kullanıcıya uygulayıp yöneticiyi atlamak.** En yüksek yetkili hesaplar en güçlü, phishing'e dirençli (FIDO2/donanım anahtarı gibi) MFA ile korunmalıdır — tam tersi değil.
- **Denetim günlüklerini toplamadan kontrol kurmak.** PIM aktivasyonu, katman ihlali, grup değişikliği kayıtları merkezi olarak toplanmıyorsa, kontroller görünmez kalır ve ihlal fark edilmez.
- **LAPS'i unutmak.** En sofistike PIM mimarisini kurup, tüm makinelerde aynı yerel admin parolasını bırakmak, saldırgana modelin altından geçen bir tünel bırakır.

---

## Sonuç

Ayrıcalıklı erişim güvenliği, tek tek saldırı tekniklerini kovalamak yerine, o tekniklerin beslendiği **yapısal maruziyeti** ortadan kaldırma disiplinidir. Tiering modeli kimlik bilgilerinin katmanlar arası kirlenmesini yasaklar; PAW yönetimi temiz bir ortamda tutar; PAM sırları kasalar ve döndürür; JIT ve Entra PIM ise kalıcı ayrıcalığı ortadan kaldırarak "ele geçirilecek aktif hedef" bırakmaz.

Bu çerçevenin özü tek bir cümlede toplanabilir: **Çalınacak bir kimlik bilgisi yoksa, orada değilse ve o an geçerli değilse, saldırının en güçlü halkası kopar.** Savunmacı için stratejik hedef budur; tespitçi için ise bu modelin yan ürünü olan "ayrıcalıklı davranışın nadir ve gözlemlenebilir" hale gelmesidir — çünkü nadir olan her sapma, artık net bir alarm demektir.
