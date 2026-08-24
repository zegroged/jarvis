# Deception Teknolojileri ve Honeypot/Honeytoken Operasyonu

## Tanım ve Konumlandırma

**Deception (aldatma) teknolojileri**, bir ağa kasıtlı olarak sahte varlıklar, sahte veriler ve sahte hesaplar yerleştirerek saldırganı bunlarla etkileşime girmeye kandıran ve bu etkileşimi *yüksek güvenilirlikli bir alarm* olarak kullanan proaktif bir savunma ve tespit disiplinidir. Temel felsefe basittir: **meşru bir kullanıcı veya süreç, kasıtlı olarak gizlenmiş bir tuzağa asla dokunmaz.** Dolayısıyla tuzağa dokunulduğu an, orada yetkisiz bir aktör vardır. Bu, geleneksel tespit yöntemlerinin en büyük derdi olan **yanlış pozitif (false positive)** sorununu neredeyse kökünden çözer.

Deception, Threat Hunting ile akrabadır ama felsefesi terstir. Threat Hunting'de avcı, gürültü içinde saldırganın izini *aktif olarak arar*. Deception'da ise savunmacı sessizce bekler ve saldırganın *kendi kendini ele vermesini* sağlayacak tuzaklar kurar. İkisi de "imza yoksa alarm da yok" sınırına takılmaz; ama deception, insan emeğini öne (kurulum) yükler ve tespit anında minimum insan müdahalesi gerektirir.

Bu yazıda kavramları savunma ve erken tespit amacıyla ele alıyoruz. Amaç bir saldırıyı yönlendirmek değil, *bir saldırganın varlığını erken ve güvenilir biçimde fark etmek* için savunma katmanı kurmaktır.

## Temel Kavramlar ve Taksonomi

Deception ekosistemi, karmaşıklık ve etkileşim derinliğine göre birkaç ana bileşene ayrılır.

### Honeytoken (bal jetonu)

Honeytoken, **etkileşime girildiğinde alarm üreten sahte bir veri parçasıdır.** Bir sunucu değil, bir *veri artefaktıdır*: sahte bir kayıt, sahte bir dosya, sahte bir kimlik bilgisi, sahte bir API anahtarı. Değeri, saldırganın onu *gerçek sanıp kullanmaya çalışmasında* yatar. Kullandığı anda savunmacıya bir sinyal düşer.

### Canary Token

**Canary token**, honeytoken'ın en pratik ve dağıtılabilir biçimidir. İsim, madenciler tarafından metan gazını erken fark etmek için maden ocaklarına götürülen kanaryalardan gelir: kanarya düşerse, tehlike var demektir. Canary token tipik olarak, *açılması/okunması/çözümlenmesi* bir web isteği tetikleyen gömülü bir işaretçidir. Örnekler:

- **Web bug / izleyici URL:** Bir Word/Excel/PDF dosyasına gömülü, dosya açıldığında sessizce bir sunucuya çağrı yapan görünmez bir kaynak (ör. bir resim referansı). Dosya açılınca çağrı düşer, savunmacı "birisi bu tuzak dosyayı açtı" bilgisini alır.
- **DNS canary:** Çözümlendiğinde (DNS lookup) alarm üreten benzersiz bir alan adı/alt alan adı. Ağ katmanında bile yakalanabildiği için güçlüdür.
- **Sahte AWS/bulut anahtarı:** Gerçek gibi görünen ama yalnızca kullanıldığında (API çağrısı denendiğinde) log üreten bir erişim anahtarı çifti. Bulut sağlayıcının denetim günlüğü (audit log), anahtarın kullanıldığını ve kaynak IP'yi raporlar.
- **QR kod, benzersiz URL, sahte veritabanı kaydı (honeyrow):** Erişilince alarm veren her tür işaretlenmiş artefakt.

Canary token'ın en güzel yanı **düşük maliyet ve dağıtılabilirlik**tir. Bir sunucu bakımı gerektirmez; bir belgeye, bir kod deposuna, bir paylaşımlı klasöre gömülüp unutulur.

### Decoy Credential (sahte kimlik bilgisi)

**Decoy credential**, saldırganın *lateral movement* (yanal hareket) ve *credential harvesting* (kimlik toplama) aşamasında yem olması için özel olarak yerleştirilen sahte kullanıcı adı/parola, token veya oturum artefaktıdır. Saldırgan bir makineyi ele geçirdiğinde ilk yaptığı iş genellikle bellekteki, kayıt defterindeki, tarayıcıdaki veya betiklerdeki kimlik bilgilerini taramaktır. Buraya bilinçli olarak konmuş sahte bir hesabın *kullanılmaya çalışılması*, ele geçirilmiş bir makinede bir saldırgan olduğunun neredeyse kesin kanıtıdır.

Yaygın decoy credential yerleşimleri:
- Belleğe/LSASS benzeri alanlara yerleştirilmiş sahte oturumlar (saldırgan bellekten kimlik kazımaya çalıştığında yem sunar).
- Group Policy, betikler, `.config` dosyaları veya "credentials.txt" gibi cazip isimli dosyalar içinde gömülü sahte parolalar.
- Dizin servisinde (Active Directory benzeri) hiç oturum açmayan, hiç kullanılmayan, ama cazip görünen (ör. "svc-backup-admin") sahte hesaplar. Bu hesaba herhangi bir oturum açma denemesi bir alarmdır.

### Honeypot (bal küpü)

**Honeypot**, saldırganı çekmek ve gözlemlemek için kasıtlı olarak konumlandırılmış, izlenen sahte bir *sistemdir* (sunucu, servis, uygulama). Honeytoken bir veriyken, honeypot çalışan bir hizmettir. Etkileşim derinliğine göre ikiye ayrılır:

- **Low-interaction honeypot:** Yalnızca belirli servisleri *taklit eder* (ör. bir SSH veya RDP oturum açma ekranı sunar ama gerçek bir kabuk vermez). Kurulumu ve bakımı kolaydır, riski düşüktür, ama saldırgan hakkında sınırlı bilgi verir. Tarama ve otomatik saldırıları yakalamakta çok iyidir.
- **High-interaction honeypot:** Gerçek bir işletim sistemi ve gerçek servisler sunar; saldırganın gerçekten etkileşime girmesine, araç indirmesine, komut çalıştırmasına izin verir. Saldırganın TTP'lerini (Tactics, Techniques, Procedures) derinlemesine gözlemlemeyi sağlar ama **çok daha risklidir**: kötü izole edilirse saldırgan onu bir sıçrama tahtası (pivot) olarak kullanabilir.

### Honeynet ve Deception Grid

**Honeynet**, birbirine bağlı birden çok honeypot'tan oluşan, gerçekçi bir sahte ağ segmentidir. Modern kurumsal ürünlerde buna bazen **deception grid / distributed deception platform (DDP)** denir: üretim ağının içine serpiştirilmiş yüzlerce sahte host, servis, paylaşım ve kimlik, saldırganın gördüğü her yönü şüpheli hale getirir. Amaç saldırganı yavaşlatmak, yanlış yönlendirmek ve her adımında yakalanma olasılığını artırmaktır.

## Kök Neden ve Çalışma Mantığı: Neden İşe Yarar?

Deception'ın işe yaramasının temeli **asimetrik bilgi** ve **saldırgan davranışının kaçınılmazlığıdır.**

**1. Saldırgan keşif yapmak zorundadır.** Bir ağa giren saldırgan, hedefin topolojisini bilmez. Nerede olduğunu, nereye gidebileceğini anlamak için *keşif (discovery)* ve *enumeration* yapmak zorundadır: ağ taraması, paylaşım listeleme, dizin sorgulama, kimlik arama. Bu zorunlu merak, tuzaklara dokunma olasılığını yaratır. Savunmacının tek işi, saldırganın bakacağı yerlere cazip yemler koymaktır.

**2. Meşru trafik tuzaklara dokunmaz.** İyi tasarlanmış bir tuzak, hiçbir iş sürecinin, hiçbir kullanıcının ve hiçbir otomasyonun *asla* erişmeyeceği biçimde konumlandırılır. Bu yüzden bir tuzak sinyali, tanımı gereği anormaldir. **Yanlış pozitif oranı teorik olarak sıfıra yakındır** — deception'ın en büyük üstünlüğü budur. Bir SIEM'de günde binlerce alarm boğulurken, bir canary alarmı neredeyse her zaman gerçek bir olaydır.

**3. Sinyal, kill chain'in erken bir aşamasında düşer.** Decoy credential veya honeypot etkileşimi, genellikle saldırgan henüz *keşif ve yanal hareket* aşamasındayken tetiklenir — yani veri sızdırma (exfiltration) veya fidye şifreleme gibi asıl hasarın *öncesinde*. Bu, savunmacıya müdahale için değerli bir zaman penceresi verir.

**4. Saldırgan için bilişsel yük.** Ağın bir kısmının sahte olduğunu bilen bir saldırgan, her adımını sorgulamak zorunda kalır. Bu belirsizlik saldırıyı yavaşlatır, hata yapma olasılığını artırır ve otomatik araçların işini zorlaştırır.

## Örnek: Bir Kimlik Tuzağının Yaşam Döngüsü

Somut bir senaryo üzerinden kavramı bütünleştirelim (savunma perspektifi):

1. **Kurulum.** Savunma ekibi, dizin servisinde `svc_sql_backup` adlı, gerçek bir yedekleme hizmet hesabı gibi görünen sahte bir hesap oluşturur. Bu hesap hiçbir gerçek sisteme oturum açmaz, hiçbir zamanlanmış görevde kullanılmaz. Ayrıca birkaç iş istasyonuna, cazip dosyalar (ör. `backup_creds.xlsx`) içine bu hesabın sahte parolasını gömer ve dosyaya bir canary token yerleştirir.
2. **Baseline.** Ekip, "bu hesaba yapılan *herhangi* bir kimlik doğrulama denemesi = kritik alarm" ve "bu dosyaya yapılan *herhangi* bir erişim = alarm" kuralını SIEM'e yazar. Normal durumda bu kural asla tetiklenmez.
3. **Tetiklenme.** Bir saldırgan bir iş istasyonunu ele geçirir, kimlik arar, `backup_creds.xlsx` dosyasını bulur ve açar — canary token düşer. Saldırgan sahte parolayı deneyerek yanal hareket etmeye çalışır — dizin servisi başarısız oturum açma denemesini loglar, kritik alarm tetiklenir.
4. **Müdahale.** SOC ekibi, kaynak makineyi, hesabı ve zaman damgasını anında elde eder. Yanlış pozitif olma ihtimali yok denecek kadar düşük olduğu için müdahale kararı hızlı ve güvenle verilir.

Bu döngüde dikkat edilmesi gereken nokta: değerli olan tuzağın kendisi değil, **onun ürettiği yüksek güvenilirlikli sinyal ve bu sinyali işleyen sürecin** var olmasıdır.

## Tespit ve İzleme Katmanı

Deception yalnızca tuzak kurmakla bitmez; asıl iş **sinyali güvenilir biçimde toplamak ve işlemektir.**

- **Merkezî loglama ve SIEM entegrasyonu.** Her canary çağrısı, her honeypot etkileşimi, her decoy credential denemesi merkezî bir yere akmalı ve *en yüksek öncelikli alarm sınıfına* atanmalıdır. Deception'ın en büyük katma değeri, alarmlarının "gürültüsüz" olmasıdır; bu yüzden diğer alarmların içinde kaybolmamalıdır.
- **Kimlik katmanı izleme.** Sahte AD hesaplarına yapılan oturum açma denemeleri, Kerberos ile ilgili anormal isteklerin (ör. sahte hesap için servis bileti talebi) izlenmesi, kimlik tabanlı deception'ın kalbidir.
- **DNS ve ağ katmanı.** DNS canary'leri, saldırganın araçları çıkışa (egress) filtrelense bile içeriden bir DNS sorgusu ürettiği için değerlidir. DNS loglarının merkezî toplanması bunu görünür kılar.
- **Bulut denetim günlükleri.** Sahte bulut anahtarlarının kullanımı, bulut sağlayıcının audit log akışında yakalanır. Bu log akışının izlenmesi ve sahte anahtar tanımlayıcılarının bir izleme listesine konması gerekir.
- **Zenginleştirme.** Alarm düştüğünde kaynak IP, kullanıcı, host ve zaman otomatik olarak toplanmalı ki müdahale ekibi bağlamı hızla kursun.

## Savunma ve Sağlam Operasyon İlkeleri

Deception kurmak kolay, *doğru* kurmak zordur. Sağlam bir operasyon için:

- **Gerçekçilik şart.** Bariz biçimde sahte görünen bir tuzak (ör. `honeypot01` adlı sunucu, tarih olarak eski, hiç yaması olmayan bariz bir yem) deneyimli saldırganı kandırmaz, hatta savunmanın deception kullandığını ele verir. İsimlendirme, işletim sistemi sürümleri, sahte trafik, gerçekçi kullanıcı ve dosya artefaktları üretim ortamına *uymalıdır*.
- **Sıkı izolasyon.** Özellikle high-interaction honeypot'lar, üretim ağından ağ segmentasyonu ve çıkış filtrelemesiyle katı biçimde ayrılmalıdır. Aksi halde tuzak, saldırgan için bir sıçrama tahtasına dönüşür — deception'ın en büyük ve en tehlikeli hatası budur.
- **Envanter ve dokümantasyon.** Her tuzak nerede, ne zaman, hangi tanımlayıcıyla kuruldu kayıt altında olmalıdır. Aksi halde kendi ekibiniz kendi tuzağınıza takılır ve alarm yorgunluğu üretir; ya da bir tuzak unutulup çürür.
- **Müdahale süreci hazır olmalı.** Yüksek güvenilirlikli bir alarm, ancak arkasında tanımlı bir *playbook* varsa değerlidir. "Canary düşerse kim, ne yapar?" sorusunun cevabı önceden belli olmalıdır.
- **Yasal ve etik sınırlar.** Deception, savunmacının kendi altyapısında pasif tespit için kurulur. Saldırgana geri saldırmak (hack-back), izinsiz üçüncü taraf sistemlerine müdahale etmek yasal olarak sorunludur ve kapsam dışıdır. Ayrıca gerçek kullanıcı verisi asla yem olarak kullanılmamalı; tüm yemler sentetik olmalıdır.
- **Katmanlı kullanım.** Deception tek başına bir güvenlik stratejisi değildir; EDR, ağ segmentasyonu, kimlik yönetimi ve loglama üzerine *ek bir tespit katmanı* olarak konumlanır.

## Yaygın Hatalar

- **Tuzağı kurup unutmak.** Bir canary token kurulur ama alarm bir SIEM'e bağlanmaz, kimse izlemez. Tetiklenen ama görülmeyen bir alarmın hiç kurulmamasından farkı yoktur.
- **Zayıf izolasyon.** High-interaction bir honeypot'u üretim ağına gevşek bağlamak, saldırgana bedava bir pivot noktası hediye etmek demektir.
- **Aşırı bariz yemler.** Gerçekçi olmayan, üretim ortamına uymayan tuzaklar hem kandırmaz hem de deneyimli saldırgana savunma taktiğinizi ifşa eder.
- **Yanlış pozitif kaynağı yaratmak.** Tuzağı, meşru bir tarama aracının (ör. güvenlik açığı tarayıcısı, envanter aracı) veya bir yedekleme işinin dokunacağı bir yere koymak, deception'ın en değerli özelliği olan "sıfır yanlış pozitif" avantajını yok eder. Tuzaklar bu tür meşru otomasyonların erişim yollarının *dışında* konumlanmalı veya bu araçlar için istisna tanımlanmalıdır.
- **Ölçeklenmeyen manuel kurulum.** Elle üç beş tuzak kurmak küçük ağda işe yarar; büyük ortamlarda kapsama alanı yetersiz kalır. Otomasyon ve merkezî yönetim gerekir.
- **Gerçek veriyi yem yapmak.** Sahte olması gereken kimlik bilgilerini gerçek bir hesaptan türetmek, hem güvenlik hem gizlilik riski yaratır; her yem tamamen sentetik olmalıdır.
- **Alarmı diğer gürültüyle karıştırmak.** Deception alarmını sıradan bir alarm sınıfına koymak, en temiz sinyalinizi çöp yığınına atmaktır. Bu alarmlar ayrı, en yüksek öncelikli kanalda işlenmelidir.

## Özet

Deception teknolojileri, tespit stratejisine **düşük yanlış-pozitifli, erken tetiklenen ve saldırganın kaçınılmaz keşif davranışını kendine karşı kullanan** bir katman ekler. Canary token'lar ve honeytoken'lar düşük maliyetli dağıtılabilir sinyal üreticileridir; decoy credential'lar yanal hareketi erken yakalar; honeypot ve honeynet'ler ise saldırgan davranışını gözlemleme ve yönlendirme imkânı verir. Bu teknikler Threat Hunting'e alternatif değil, tamamlayıcıdır: avlanmak yerine, saldırganın kendini ele vermesini sağlayan sabırlı bir pusu kurar. Değer, tuzağın kendisinde değil, ürettiği temiz sinyalin gerçekçi kurulumu, sıkı izolasyonu ve arkasındaki disiplinli müdahale sürecindedir.
