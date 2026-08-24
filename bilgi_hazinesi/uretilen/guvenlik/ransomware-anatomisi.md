# Ransomware Anatomisi

## Tanım

Ransomware (fidye yazılımı), bir sistemdeki verileri kullanıcının erişemeyeceği hâle getiren ve bu erişimi geri vermek karşılığında fidye talep eden kötücül yazılım (malware) sınıfıdır. Klasik tanım "verileri şifreler, para ister" şeklinde olsa da, modern ransomware artık tek başına bir dosya şifreleyici değil; keşif, yanal hareket (lateral movement), veri sızdırma (exfiltration), şifreleme ve pazarlık aşamalarından oluşan uçtan uca bir **saldırı operasyonudur**. Bu operasyonu çoğu zaman tek bir yazılım değil, bir insan ekibi yürütür. Bu yüzden ransomware'i "bir dosya" olarak değil, "bir iş modeli" olarak düşünmek doğru zihinsel çerçevedir.

Bu iş modelinin bugün en yaygın hâli **RaaS (Ransomware-as-a-Service)**'tir: bir çekirdek geliştirici grubu şifreleyiciyi, sızıntı sitesini ve pazarlık altyapısını geliştirir; "affiliate" denen bağlı saldırganlar bu araçları kiralar, kurbanı kendileri bulur ve elde edilen fidyeyi geliştiriciyle bölüşür. Bu ayrışma, saldırının neden bu kadar profesyonelleştiğini ve neden savunmanın tek bir imza (signature) ile durdurulamadığını anlamanın anahtarıdır.

## Kök Neden ve Çalışma Mantığı: Neden Böyle Oluyor?

Ransomware'in var olmasının teknik kökeni tek bir cümlede özetlenebilir: **güçlü kriptografi tersine çevrilemez, ama para transferi geri alınabilir olmaktan çıkmıştır.** Yani saldırgan, matematiksel olarak kırılamayacak bir şifreleme uygular ve ödemeyi kripto para ile alarak izini büyük ölçüde gizler. Bu iki koşul bir araya gelmeden ransomware ekonomik olarak anlamlı olmazdı.

### Neden şifreleme geri alınamıyor?

Modern ransomware, saf simetrik ya da saf asimetrik değil, **hibrit (hybrid) kriptografi** kullanır. Mantık şudur: simetrik şifreleme (örneğin AES) hızlıdır ve gigabaytlarca veriyi kısa sürede işleyebilir; asimetrik şifreleme (örneğin RSA veya eliptik eğri tabanlı yöntemler) yavaştır ama anahtar dağıtımı sorununu çözer. Saldırgan bu ikisini şöyle birleştirir:

1. Her dosya (veya her makine) için rastgele bir simetrik anahtar üretilir ve dosyalar bu hızlı anahtarla şifrelenir.
2. Bu simetrik anahtar, saldırganın **açık anahtarı (public key)** ile şifrelenir ve şifreli dosyanın yanına gömülür.
3. Simetrik anahtarın açık hâli bellekten silinir.

Sonuç: kurbanın diskinde şifreli veri ve şifreli anahtar vardır, ama bu anahtarı çözebilecek **özel anahtar (private key)** yalnızca saldırgandadır. Kurban ne kadar uğraşırsa uğraşsın, RSA'yı ya da AES'i "kırmak" pratikte imkânsızdır. İşte fidyenin satın aldığı şey tam olarak budur: saldırganın elindeki private key. Bu tasarım yüzünden, şifreleme kusursuz uygulandığında **decryptor yazmak mümkün olmaz**; kurtarma yalnızca yedeklerden gelir.

Buradaki kritik incelik şudur: ransomware çeteleri decryptor kurtarma araçlarının çoğu, kod hatalarından doğar; matematiksel bir zayıflıktan değil. Örneğin bazı eski aileler simetrik anahtarı zayıf bir rastgele sayı üreteci (weak PRNG) ile üretmiş, ya da anahtarı diskte bir yerde bırakmıştır. Güvenlik araştırmacıları bu **implementasyon hatalarını** yakaladığında ücretsiz decryptor çıkarabilir. Ama iyi yazılmış bir aile için bu şans yoktur.

### Neden makinelerin içine bu kadar rahat girilebiliyor?

Şifreleme aşamasına gelmeden önce saldırganın sisteme girmesi ve yayılması gerekir. Bunun kök nedeni genellikle egzotik bir zero-day değil, **temel hijyen eksiklikleridir**. En sık görülen ilk erişim (initial access) yolları şunlardır:

- **Zayıf ya da tekrar kullanılan kimlik bilgileri:** İnternete açık RDP (Remote Desktop Protocol) veya VPN geçitleri, brute-force ya da daha önce sızmış parola listeleriyle (credential stuffing) ele geçirilir. MFA (çok faktörlü kimlik doğrulama) yoksa tek bir parola tüm kapıyı açar.
- **Phishing:** Zararlı bir ek ya da bağlantı, kullanıcıya bir "loader" indirtir. Bu loader başlangıçta ransomware değildir; sadece bir dayanak (foothold) kurar.
- **Yamanmamış açıklar:** İnternete bakan VPN cihazları, e-posta sunucuları, dosya transfer uygulamaları gibi çevre birimlerindeki bilinen ama yamanmamış zafiyetler doğrudan içeri sokar.

Kök neden nettir: saldırgan en zayıf ve en düşük maliyetli yolu seçer. Bu yüzden savunmanın da en çok bu üç kapıya yatırım yapması gerekir; egzotik tehditlerden önce temeller.

## Saldırının Aşamaları: Somut Bir Senaryo

Soyut kalmamak için tipik, insan güdümlü bir ransomware operasyonunu adım adım izleyelim. Bu akış, gerçek olaylardan damıtılmış temsilî bir örnektir.

**Gün 0 — İlk erişim.** Muhasebe departmanındaki bir çalışan, "ödenmemiş fatura" konulu bir e-postadaki makro içeren belgeyi açar. Belge, arka planda küçük bir loader çalıştırır. Bu loader bir C2 (command-and-control) sunucusuna bağlanır ve saldırgana bir kanal açar.

**Gün 0–2 — Keşif ve yetki yükseltme.** Saldırgan artık bir makinededir ama tek makine yeterli değildir. Ağ haritasını çıkarır: hangi sunucular var, Active Directory yapısı nasıl, yedekler nerede duruyor. Yerel yönetici parolalarını, bellekteki kimlik bilgilerini toplar; **privilege escalation** ile domain yöneticisi (Domain Admin) haklarına ulaşmayı hedefler. Bu aşamada henüz hiçbir dosya şifrelenmez; saldırgan sessizdir çünkü fark edilmek istemez.

**Gün 2–5 — Yanal hareket ve veri sızdırma.** Ele geçirilen kimlik bilgileriyle saldırgan sunucudan sunucuya atlar (lateral movement). Kritik verileri — müşteri kayıtları, finansal tablolar, fikri mülkiyet — kendi sunucularına **kopyalar (exfiltration)**. Bu, çift şantajın ilk yarısıdır ve şifrelemeden ÖNCE olur. Bu sıra çok önemlidir: veri çoktan çalınmıştır.

**Gün 5 — Savunmanın devre dışı bırakılması.** Şifrelemeden hemen önce saldırgan, tespit ve kurtarma yeteneklerini yok eder: EDR/antivirüs süreçlerini kapatmaya çalışır, gölge kopyaları (Volume Shadow Copies) siler, yedekleme ajanlarını durdurur, mümkünse yedek depolarını da şifreler ya da siler. Amaç, kurbanı yedekten dönme seçeneğinden mahrum bırakmaktır.

**Gün 5 — Şifreleme.** Genellikle gecenin bir yarısı, hafta sonu ya da tatilde — savunma ekibinin en zayıf olduğu anda — şifreleyici tüm ağa aynı anda dağıtılır (çoğunlukla domain'in kendi dağıtım araçları kullanılarak). Yukarıda anlatılan hibrit kripto ile dosyalar şifrelenir, her klasöre bir fidye notu bırakılır.

**Gün 5 sonrası — Pazarlık.** Fidye notu kurbanı bir iletişim kanalına yönlendirir. Talep iki yönlüdür: "dosyaları geri açmak için X, çaldığımız veriyi yayınlamamak için Y ödeyin."

## Yayılma: Neden Bir Makineden Tüm Ağa Yayılıyor?

Yayılma (propagation) ransomware'in yıkıcılığını belirleyen faktördür. Tek makineyi şifrelemek can sıkıcıdır; tüm domain'i şifrelemek ise şirketi durdurur. İki ana yayılma modeli vardır ve ayrımı anlamak savunma için kritiktir.

**İnsan güdümlü yanal hareket.** Bugün kurumsal saldırıların baskın modeli budur. Yayılma otomatik bir solucan (worm) değil, klavye başındaki bir operatörün çaldığı **geçerli kimlik bilgileriyle** meşru araçları (uzaktan yönetim, PowerShell, domain dağıtım mekanizmaları) kullanmasıdır. Bu yüzden bu tür yayılma imza tabanlı antivirüse çoğu zaman "normal yönetici aktivitesi" gibi görünür — buna **living-off-the-land** denir. Kök neden: saldırgan sistemin kendi meşru araçlarını kullanınca, kötücül olanı iyiden ayırmak davranışsal analiz gerektirir.

**Otomatik, solucan tarzı yayılma.** Bazı aileler ağ zafiyetlerini kullanarak insan müdahalesi olmadan makineden makineye atlar. Tarihteki en yıkıcı olaylardan biri, bir ağ protokolündeki zafiyeti sömüren solucan yeteneği sayesinde saatler içinde küresel ölçekte yayılmıştı. Bu modelde yamalama (patching) ve ağ segmentasyonu birinci savunma hattıdır.

Her iki modelde de ortak ders şudur: **düz (flat) ağ, ransomware'in en iyi dostudur.** Segmentasyonu olmayan bir ağda tek bir ele geçirilmiş makine, her yere köprü olur.

## Çift Şantaj (Double Extortion): Neden Yedek Artık Tek Başına Yetmiyor?

Klasik ransomware'e karşı savunmanın altın kuralı "iyi yedek al, fidye ödeme" idi. Saldırganlar bu savunmayı gördü ve iş modelini değiştirdi. **Çift şantaj** tam olarak yedek stratejisini etkisiz kılmak için icat edildi.

Mantık şudur: eğer kurbanın sağlam yedeği varsa, dosyaları şifrelemenin hiçbir kaldıraç değeri kalmaz — kurban yedekten döner, fidye ödemez. Ama saldırgan şifrelemeden **önce** veriyi çalmışsa (birinci baskı), artık ikinci bir tehdit vardır: "Ödemezsen bu hassas veriyi herkese açık sızıntı sitesinde (leak site) yayınlarız." Yedek bu tehdide karşı hiçbir şey yapamaz, çünkü sorun verinin kaybı değil, **verinin ifşasıdır**.

Bu yüzden çift şantaj çağında yedek, "kullanılabilirlik" (availability) sorununu çözer ama "gizlilik" (confidentiality) sorununu çözmez. Bir hastane yedeğinden dönüp çalışmaya devam edebilir, ama hasta kayıtları hâlâ sızdırılabilir. Bu, aynı zamanda bir **veri ihlali (data breach)** olduğu için yasal bildirim yükümlülüklerini ve düzenleyici cezaları da devreye sokar.

Saldırganlar baskıyı artırmak için modeli daha da genişletti — bazen "üçlü" veya "çoklu şantaj" denir:

- Çalınan verideki müşterilere, hastalara ya da iş ortaklarına doğrudan ulaşıp "verileriniz bizde, şirketinize baskı yapın" demek.
- Kurbanın altyapısına **DDoS** saldırısı ekleyerek pazarlık sırasında hizmeti daha da felç etmek.
- Düzenleyicilere ihbar tehdidi.

Kök neden değişmedi: saldırgan mümkün olan her kaldıracı ekleyerek ödeme olasılığını yükseltmeye çalışıyor. Savunma açısından çıkarım net: **artık sadece "geri dönebilir miyim" değil, "veri çalınırsa ne olur" sorusunu da savunma modeline koymak zorundayız.**

## İstismar/Sömürü Mantığı ile Savunmanın Birlikte Okunması

Her saldırı aşamasının bir sömürü mantığı, bir de bunu kesen savunma karşılığı vardır. İkisini yan yana koymak, savunmanın neden orada durduğunu anlaşılır kılar.

### İlk erişim

**Sömürü mantığı:** Saldırgan en ucuz kapıyı arar — açıkta duran RDP, MFA'sız VPN, phishing'e kanan kullanıcı, yamanmamış çevre cihazı. Amaç, gürültü çıkarmadan tek bir dayanak elde etmektir.

**Savunma:** İnternete bakan uzaktan erişimin tamamına MFA zorunlu kılmak; RDP'yi asla doğrudan internete açmamak, mutlaka bir VPN ya da geçit arkasına almak; çevre cihazlarını öncelikli olarak yamamak; phishing'e karşı hem e-posta filtreleme hem de kullanıcı farkındalığı. Buradaki tek en yüksek getirili tekil önlem, uzaktan erişimde **MFA**'dır — birçok saldırıyı en başta durdurur.

### Keşif, yetki yükseltme ve yanal hareket

**Sömürü mantığı:** Saldırgan bellekten kimlik bilgisi toplar, aşırı geniş yetkileri ve düz ağı kullanarak Domain Admin'e tırmanır ve meşru araçlarla yayılır (living-off-the-land).

**Savunma:** **En az yetki (least privilege)** ilkesi — kimse gündelik işini Domain Admin hesabıyla yapmamalı; yönetici hesapları ayrı ve sınırlı olmalı. Ağ segmentasyonu ile bir bölgeden diğerine geçişi zorlaştırmak. Kimlik bilgisi hırsızlığını zorlaştıran modern kimlik korumaları. En önemlisi: **davranışsal tespit (EDR/XDR)** — imza değil, "bir kullanıcı hesabının aniden onlarca makineye bağlanması", "gölge kopyaların toplu silinmesi", "yönetim aracının olağandışı kullanımı" gibi kalıpları yakalayan tespit. Çünkü saldırgan meşru araçlar kullandığında, onu ancak davranışı ele verir.

### Şifreleme ve savunmanın devre dışı bırakılması

**Sömürü mantığı:** Saldırgan tespit araçlarını kapatır, yedekleri siler, gölge kopyaları yok eder ve sonra en uygunsuz anda toplu şifreleme yapar.

**Savunma:** EDR araçlarında **tamper protection** (kurcalamaya karşı koruma) açık olmalı ki saldırgan onları kapatamasın. Yedekler **immutable (değiştirilemez)** ve **offline/air-gapped** kopyalar içermeli — saldırgan domain'i ele geçirse bile ulaşamayacağı bir kopya. Tespit-yanıt ekibinin gece/hafta sonu kapsaması olmalı, çünkü saldırgan tam o boşluğu hedefler.

### Veri sızdırma (çift şantaj bileşeni)

**Sömürü mantığı:** Şifrelemeden önce büyük hacimli veri dışarı kopyalanır.

**Savunma:** Olağandışı **giden (egress)** trafik hacmini izlemek — bir sunucudan gigabaytlarca verinin dışarıya akması güçlü bir alarmdır. Kritik veriyi sınıflandırmak ve mümkünse hareketsizken (at rest) kendi kontrolünüzdeki şifreleme ile korumak (böylece çalınsa da işe yaramasını zorlaştırmak). Veriye erişimi least privilege ile daraltmak.

## Yaygın Hatalar

Ransomware'e yenik düşen kurumlarda tekrar tekrar aynı hatalar görülür. Bunları bilmek, savunmanın nereye yoğunlaşacağını gösterir.

- **"Yedeğimiz var" yanılgısı, ama yedek çevrimiçi.** En sık ve en ölümcül hata. Yedekler ağdan erişilebilir bir paylaşımda ya da yedekleme sunucusu domain'e bağlıysa, saldırgan domain'i ele geçirdiğinde yedekleri de şifreler veya siler. Erişilemeyen (immutable/offline) kopyası olmayan yedek, ransomware karşısında yedek sayılmaz.
- **Yedeğin geri dönüşünü hiç test etmemek.** Yedek almak ile yedekten dönebilmek farklı şeylerdir. Felaket anında ilk kez denenen restore çoğu zaman başarısız olur; bozuk, eksik ya da fahiş yavaştır.
- **RDP'yi internete açık bırakmak, MFA'sız VPN.** Yıllardır en çok sömürülen tekil hata. Tek bir parola koca ağı açar.
- **Herkesin yerel yönetici / aşırı geniş yetki.** Least privilege uygulanmadığında, tek bir ele geçirilmiş kullanıcı Domain Admin'e giden yolu kısaltır.
- **Düz ağ, segmentasyon yokluğu.** Tek makineden tüm ağa geçişin önünde hiçbir duvar olmaması.
- **Yamaları geciktirmek**, özellikle internete bakan cihazlarda. Bilinen bir açık, saldırgana bedava kapı verir.
- **EDR'yi "kurdum, bitti" sanmak.** Alarmları kimse izlemiyorsa, tamper protection kapalıysa ya da gece kapsaması yoksa araç yalnızca kâğıt üzerinde koruma sağlar.
- **Olay müdahale planı olmaması.** Şifreleme gecesi "kimi arayacağız, hukuk ne diyor, iletişimi kim yönetiyor" sorularının ilk kez sorulması, krizi katbekat büyütür.
- **Fidyeyi refleksle "çözüm" sanmak.** Ödeme decryptor'un çalışacağını garanti etmez, çalınan verinin silineceğini hiç garanti etmez ve yasal/etik riskler taşır. Ödeme bir kurtarma stratejisi değildir.

## En İyi Pratikler

Aşağıdaki pratikler, saldırı zincirinin farklı halkalarını kesecek şekilde katmanlı savunma (defense in depth) mantığıyla dizilmiştir. Hiçbiri tek başına yeterli değildir; güç, üst üste binmelerindedir.

**1. Yedeklemede 3-2-1-1 kuralı.** En az üç kopya, iki farklı ortam, bir kopya tesis dışında (off-site), ve en az bir kopya **çevrimdışı ya da değiştirilemez (immutable/air-gapped)**. Yedekleme altyapısı üretim domain'inden kimlik olarak ayrılmalı ki domain düşse bile yedek ayakta kalsın. Ve restore süreci düzenli **test edilmeli** — dönebildiğinizi kanıtlamadan yedeğiniz olduğunu söyleyemezsiniz.

**2. Uzaktan erişimde MFA, her yerde.** VPN, RDP, e-posta, yönetim panelleri — istisnasız. Mümkünse phishing'e dayanıklı MFA yöntemleri (donanım anahtarı gibi) tercih edilmeli. RDP asla doğrudan internete açılmamalı.

**3. En az yetki (least privilege) ve yönetici hesaplarının ayrılması.** Gündelik iş ile yönetim hesapları ayrı olmalı; Domain Admin kullanımı olabildiğince az ve denetimli olmalı. Yerel yönetici parolaları makine başına benzersiz olmalı ki bir makinenin ele geçirilmesi hepsine yayılmasın.

**4. Ağ segmentasyonu.** Kritik sistemler, kullanıcı ağından ve birbirinden ayrılmalı. Amaç yanal hareketi yavaşlatmak ve bir ihlali tek bölgeye hapsetmek. Segmentasyon, "içeri girdi ama her yere ulaşamadı" farkını yaratır.

**5. Hızlı ve önceliklendirilmiş yamalama.** Özellikle internete bakan VPN, e-posta ve dosya transfer sistemleri. Yama yönetimi bir program olmalı, "boş vakit işi" değil.

**6. EDR/XDR ile davranışsal tespit ve izleme.** Kurulum yetmez: tamper protection açık, alarmlar 7/24 izleniyor (kendi ekibinizle ya da bir MDR hizmetiyle), ve tespit kuralları yanal hareket, kimlik bilgisi hırsızlığı ve gölge kopya silme gibi kalıpları kapsıyor olmalı. Ransomware'i şifreleme anında değil, ondan günler önce keşif aşamasında yakalamak esastır.

**7. Giden trafik (egress) izleme.** Beklenmedik büyük veri çıkışları, çift şantajın sızdırma aşamasını daha şifreleme başlamadan yakalayabilir. Bu, "veri çalınmadan" durdurma şansıdır.

**8. E-posta güvenliği ve kullanıcı farkındalığı.** Ekleri ve bağlantıları filtreleyen katmanlar, makroların varsayılan olarak engellenmesi ve düzenli, gerçekçi phishing tatbikatları. Kullanıcı, ilk erişimin en sık kapısıdır; bu kapıyı hem teknik hem eğitimle güçlendirmek gerekir.

**9. Olay müdahale (incident response) planı ve tatbikatı.** Kimin arayacağı, hangi sistemin izole edileceği, hukuk ve iletişimin rolü, yasal bildirim yükümlülükleri — hepsi önceden yazılı ve **masa başı tatbikatlarıyla (tabletop exercise)** denenmiş olmalı. Kriz anında plan aramak için çok geçtir.

**10. En az ayrıcalık yaklaşımını mimariye taşımak: sıfır güven (zero trust).** Ağ içindeki hiçbir bağlantıya "içeriden geldiği için güvenilir" muamelesi yapmamak; her erişimi kimlikle ve bağlamla doğrulamak. Bu, yanal hareketin varsayılan olarak kolay olduğu düz ağ modeline verilmiş yapısal cevaptır.

## Kapanış: Doğru Zihinsel Model

Ransomware'e karşı en büyük stratejik hata, onu "bir virüs" olarak görmek ve antivirüse güvenmektir. Doğru model şudur: ransomware, insanların yürüttüğü, aşamalı, sabırlı bir **saldırı kampanyasıdır** ve şifreleme yalnızca en son, en görünür adımdır. O gösterişli şifreleme ekranını gördüğünüz anda, saldırgan çoktan günlerdir ağınızdaydı, verinizi çoktan çalmıştı.

Bu yüzden savunma da tek noktaya değil, zincirin her halkasına dağıtılmalıdır: girişi zorlaştır (MFA, yama), yayılmayı yavaşlat (least privilege, segmentasyon), erken yakala (EDR ve davranışsal izleme), veri kaçışını fark et (egress izleme) ve en kötü durumda ayağa kalkabil (değiştirilemez, test edilmiş yedek). Çift şantaj çağında ise buna bir katman daha eklenir: yalnızca "geri dönebilir miyim" değil, "veri çalınırsa nasıl yönetirim" sorusuna da hazır olmak. Ödeme bir strateji değil, bir başarısızlık işaretidir; asıl strateji, saldırganı en son adıma varmadan durduran katmanlı ve test edilmiş bir savunmadır.
