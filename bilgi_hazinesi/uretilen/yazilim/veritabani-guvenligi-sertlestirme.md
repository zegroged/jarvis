# Veritabanı Güvenliği Sertleştirme (DB Hardening)

## Giriş: Neden Genel "Sistem Sertleştirme" Yetmez

Çoğu güvenlik kontrol listesi "sistemi sertleştir" der ve işletim sistemi seviyesinde firewall kuralları, gereksiz servisleri kapatma, patch yönetimi gibi maddeleri sayar. Bu doğru ama eksiktir, çünkü veritabanı kendi başına ayrı bir güvenlik yüzeyidir. Bir saldırgan SQL Injection ile bir kez SQL çalıştırma yeteneği kazandığında (ya da çalınmış bir connection string ile doğrudan bağlandığında), gerçek soru şu olur: "Bu bağlantı neyi görebilir, neyi değiştirebilir, neyi silebilir ve bu iz nerede kalır?" İşte bu soruların cevabı işletim sistemi sertleştirmesinde değil, veritabanının kendi iç güvenlik mekanizmalarında yatar: rol/yetki hijyeni, satır ve sütun seviyesinde erişim kontrolü, veri şifreleme ve audit (denetim) izleri.

Bu makalenin çıkış noktası şudur: **SQL Injection (veya benzeri bir ilk erişim vektörü) "oyunun sonu" değil, "oyunun başlangıcı" olmalıdır.** İyi sertleştirilmiş bir veritabanında, bir injection açığı bulunsa bile saldırganın ulaşabileceği veri ve yapabileceği işlem, uygulamanın o an kullandığı rolün yetkileriyle sınırlı kalır. Savunma katmanlı olmalı; "girişi engelle" tek başına yeterli bir strateji değildir, çünkü giriş engelleri er ya da geç delinir.

## Kök Neden: Veritabanları Neden Özel Bir Tehdit Yüzeyi Oluşturur

Veritabanı, bir organizasyonun en yoğunlaştırılmış değerli varlığıdır: kullanıcı kimlik bilgileri, kişisel veri, finansal kayıtlar, iş sırları — hepsi tek bir yerde. Bu yoğunlaşma üç yapısal riski beraberinde getirir:

1. **Aşırı geniş yetkilendirme (over-privileged accounts):** Uygulamalar tarihsel olarak tek bir veritabanı kullanıcısıyla (genelde `admin`, `root`, `sa` gibi) çalışacak şekilde kurulur, çünkü bu geliştirme sırasında daha az sürtünme yaratır. Bu kullanıcı genellikle CREATE, DROP, ALTER gibi şema değiştirme yetkilerine de sahiptir. SQL Injection ile ele geçirilen bir bağlantı, uygulamanın normalde hiç kullanmadığı bu yetkileri de miras alır. Kök neden: **yetkilendirme, işlevsel ihtiyaca göre değil, kolaylığa göre tasarlanmıştır.**

2. **Yatay veri izolasyonunun uygulama katmanına bırakılması:** Çok kiracılı (multi-tenant) sistemlerde "kullanıcı sadece kendi verisini görsün" kuralı genellikle her sorguya elle eklenen `WHERE tenant_id = ?` koşuluyla sağlanır. Bu, bir geliştiricinin tek bir sorguyu unutmasıyla (ya da yeni bir endpoint'in bu kısıtı atlamasıyla) tüm izolasyonun çökmesi anlamına gelir. Kök neden: **erişim kontrolü mantığı, veriyi koruması gereken katmandan (veritabanı) uzakta, onu kullanan katmanda (uygulama kodu) yaşamaktadır.**

3. **"Disk çalınırsa/yedek sızarsa ne olur" sorusunun cevapsız kalması:** Şifrelenmemiş bir veritabanı dosyası veya yedek (backup), erişim kontrolü tamamen bypass edilerek doğrudan disk seviyesinde okunabilir. Uygulama katmanındaki tüm rol/yetki mimarisi, disk dosyasına doğrudan erişildiğinde anlamsızlaşır. Kök neden: **erişim kontrolü sadece "canlı bağlantı" senaryosunu düşünür, "veri istirahatte (at rest)" senaryosunu çoğu zaman göz ardı eder.**

Bu üç kök nedenin ortak paydası: güvenlik, veritabanının *dışındaki* bir katmana (uygulama kodu, ağ güvenliği, işletim sistemi) devredilmiş ve veritabanının kendi yerleşik mekanizmaları kullanılmamıştır. DB hardening'in özü, bu sorumluluğu mümkün olduğunca veritabanının kendisine, yani verinin en yakınına taşımaktır — "defense in depth" (katmanlı savunma) prensibinin somut uygulaması.

## Least-Privilege Roller ve GRANT Hijyeni

### Çalışma Mantığı

Least-privilege (en az yetki) ilkesi, her hesabın (uygulama, servis, kişi) yalnızca görevini yerine getirmek için gerekli minimum yetkiye sahip olması gerektiğini söyler. Veritabanı bağlamında bu, tek bir "uygulama kullanıcısı" yerine rol tabanlı bir hiyerarşi kurmak demektir:

- **Şema sahibi rolü (DDL yetkisi):** Tabloları oluşturan, migration çalıştıran rol. Bu rol yalnızca dağıtım (deployment) sürecinde, kısıtlı bir pencerede kullanılır; uygulamanın çalışma zamanında (runtime) bu role asla ihtiyaç yoktur.
- **Uygulama çalışma zamanı rolü (DML yetkisi):** Sadece SELECT/INSERT/UPDATE/DELETE yapabilir, hangi tablolarda gerekiyorsa sadece onlarda. Bu rolün DROP TABLE, ALTER TABLE, CREATE ROLE gibi yetkileri olmamalıdır.
- **Salt-okunur analitik/raporlama rolü:** Sadece SELECT, hatta bazı hassas sütunlara bile erişimi olmayabilir (bkz. sütun seviyesi izinler).
- **Yönetici/DBA rolü:** İnsan operatörler için, tercihen çok faktörlü kimlik doğrulama arkasında, geniş yetkili ama sıkı loglanan bir rol.

Bunun kök nedeni basit bir olasılık hesabıdır: uygulamanın SQL Injection'a açık bir noktasından geçen saldırgan sorgusu, o bağlantının rolüyle çalışır. Rol DROP/ALTER yapamıyorsa, saldırgan da yapamaz — açık hâlâ orada olsa bile, **zarar tavanı (blast radius)** düşürülmüş olur.

### Yaygın Hatalar

- **"public" veya varsayılan rolde gereksiz yetki bırakmak:** Birçok veritabanı motorunda varsayılan olarak herkese açık bir şema/rol vardır ve buraya yanlışlıkla EXECUTE veya CREATE gibi yetkiler sızabilir. Kontrol listesinde "varsayılan rolün yetkilerini gözden geçirdim mi" maddesi olmalı.
- **GRANT ... WITH GRANT OPTION'ın gelişigüzel kullanımı:** Bu, yetki alan rolün başka rollere de aynı yetkiyi devretmesine izin verir — yetki yönetimini merkezi denetimden çıkarır ve yetki artışı (privilege escalation) zincirlerine kapı açar.
- **Servis hesaplarının insan hesaplarıyla aynı şekilde yönetilmesi:** Servis hesapları rotasyona, süre sonuna (expiry) ve anomalik kullanım tespitine tabi tutulmadığında, bir kez sızan kimlik bilgisi süresiz geçerli kalır.
- **"Geçici" olarak verilen geniş yetkinin geri alınmaması:** Bir acil müdahale (incident) sırasında hızlıca verilen `GRANT ALL`, olay kapandıktan sonra genelde unutulur. Bu yüzden yetki değişikliklerinin bir bitiş tarihi veya en azından periyodik gözden geçirme (access review) süreci olmalı.

### En İyi Pratikler

- Rolleri işleve göre tanımla, kişiye/servise göre değil; kişi/servisi role ata (RBAC mantığı).
- Migration/DDL çalıştıran kimlik bilgisini uygulamanın çalışma zamanı kimlik bilgisinden fiziksel olarak ayır.
- Periyodik "kim, neye, neden erişebiliyor" denetimi (access recertification) yap — zamanla biriken yetki artığı (privilege creep) kaçınılmazdır, düzenli temizlik gerekir.
- Yetkileri şema/tablo seviyesinde değil mümkün olduğunca dar tanımla; "sadece bu view'a SELECT" gibi.

## Row-Level Security (RLS): Satır Seviyesinde Erişim Kontrolü

### Tanım ve Çalışma Mantığı

RLS, bir tabloya erişimin hangi satırlarla sınırlı olacağını uygulama koduna değil, veritabanı motorunun kendisine tanımlı bir politika (policy) ile belirleme mekanizmasıdır. Örneğin çok kiracılı bir `siparisler` tablosunda, RLS politikası "bu bağlantının oturum bağlamındaki `tenant_id` değeri, satırın `tenant_id` sütunuyla eşleşmiyorsa satır hiç görünmesin" kuralını veritabanı motoru seviyesinde zorunlu kılar. Politika bir kez tanımlandıktan sonra, o tabloya yazılan *her* sorgu (geliştiricinin `WHERE` koşulunu unuttuğu sorgu dahil) bu filtreden geçmek zorundadır.

Kök neden analizi açısından RLS'nin değeri şudur: normalde erişim kontrolü mantığı N tane farklı endpoint'te, N tane farklı geliştirici tarafından yazılan sorguda tekrar tekrar doğru uygulanmak zorundadır — tek bir zayıf halka tüm izolasyonu kırar. RLS bu mantığı **tek bir yere** (veritabanı politika tanımına) taşıyarak, "her sorguda doğru filtreyi hatırlama" yükünü ortadan kaldırır. Bu, güvenlik mühendisliğinde çok tekrarlanan bir prensibin uygulamasıdır: kritik bir kontrolü, onu unutmanın mümkün olmadığı bir katmana taşı.

### Doğru Kullanım ve Tuzaklar

- **RLS'yi "ayrıcalıklı" (bypass yetkisi olan) roller için de düşün.** Çoğu veritabanı motoru, tablo sahibi veya süper kullanıcı rollerinin RLS politikalarını varsayılan olarak atlamasına izin verir. Uygulama bağlantısı yanlışlıkla bu ayrıcalıklı rolle kurulursa, RLS sessizce devre dışı kalmış olur — hiçbir hata vermeden. Bu, "RLS açık ama işe yaramıyor" şeklindeki en sinsi yanlış yapılandırmadır.
- **Oturum bağlamının (session context) güvenilir şekilde taşınması kritik.** RLS genelde `current_setting()` benzeri bir mekanizmayla "bu bağlantı hangi tenant/kullanıcı adına konuşuyor" bilgisini okur. Bu bilgi uygulama tarafından her bağlantı/istek başında güvenilir şekilde ayarlanmalıdır; aksi halde bağlantı havuzlama (connection pooling) senaryolarında bir önceki isteğin bağlamı yanlışlıkla bir sonrakine sızabilir — bu da RLS'nin "yanlış tenant bağlamıyla doğru çalışması" (yani başka bir kiracının verisini "doğru" şekilde göstermesi) gibi tehlikeli bir sınıf hataya yol açar.
- **RLS performans maliyetini gizler.** Politika ifadesi her sorguya örtük bir `WHERE` gibi eklendiği için, politika ifadesi indekslenebilir sütunlar üzerinden yazılmazsa sorgu planlayıcısı tam tablo taraması (full scan) yapabilir. Politikayı yazarken indeks stratejisiyle birlikte düşünmek gerekir.
- **RLS, SQL Injection'ın kendisini önlemez** — enjekte edilen sorgu hâlâ çalışır. Ama enjekte edilen sorgu artık sadece o oturumun bağlamına ait satırları görebilir. Yani RLS bir *tespit/önleme* aracı değil, bir *zarar sınırlama (containment)* aracıdır. Bu ayrımı net tutmak önemli: RLS olmadan başarılı bir injection tüm tabloyu döker, RLS ile aynı injection sadece bir kiracının verisini döker.

## Sütun Seviyesinde Şifreleme ve TDE (Transparent Data Encryption)

### Tanım

İki farklı ama tamamlayıcı şifreleme yaklaşımı vardır:

- **TDE (Transparent Data Encryption):** Veritabanının disk üzerindeki fiziksel dosyalarını (data dosyaları, log dosyaları, yedekler) şifreler. "Transparent" kelimesi kilit noktadır: uygulama kodu ve SQL sorguları hiçbir değişiklik gerektirmez, şifre çözme veritabanı motoru tarafından bellek seviyesinde otomatik yapılır. TDE'nin koruduğu tehdit modeli **"veri istirahatte iken diske/yedeğe fiziksel veya dosya-sistemi seviyesinde erişim"**dir — örneğin çalınan bir disk, yanlış yapılandırılmış bir bulut depolama izniyle sızan bir yedek dosyası.
- **Sütun seviyesinde şifreleme (column-level / application-level encryption):** Belirli hassas sütunları (TC kimlik no, kredi kartı, sağlık verisi) uygulama veya veritabanı fonksiyonu seviyesinde ayrıca şifreler. Bu, aktif bir veritabanı bağlantısı olan ama o sütunun şifre çözme anahtarına erişimi olmayan bir saldırgana karşı da koruma sağlar.

### Kök Neden ve Ayrım

TDE'nin sınırını anlamak kritiktir: TDE, **canlı ve yetkilendirilmiş bir veritabanı bağlantısına** karşı hiçbir koruma sağlamaz, çünkü motor bu bağlantı için veriyi zaten şeffaf şekilde çözer. Yani bir SQL Injection ile kazanılan geçerli bir DB bağlantısı, TDE açık olsa bile şifrelenmemiş gibi veriyi düz metin (plaintext) olarak görür. TDE'nin tehdit modeli "disk/yedek çalınması", SQL Injection'ın tehdit modeli "geçerli bağlantı üzerinden sorgu" — bu ikisi kesişmez.

Bu yüzden gerçekten hassas alanlar (parola hash'i hariç — o zaten tek yönlü olmalı; ödeme verisi, kimlik numarası gibi geri döndürülebilir olması gereken hassas alanlar) için sütun seviyesinde şifreleme, anahtarın veritabanı motorunun kendisinde değil, ayrı bir anahtar yönetim sisteminde (KMS — Key Management Service) tutulmasıyla anlam kazanır. Böylece "veritabanına SQL çalıştırma yetkisi olan" ile "hassas sütunun şifresini çözebilen" iki ayrı yetki sınıfı hâline gelir — saldırganın biri olması diğerini garanti etmez.

### Yaygın Hatalar

- **TDE'yi tek başlı çözüm sanmak:** "Şifreleme var, güvenliyiz" yanılgısı; TDE canlı bağlantı senaryosunu kapsamaz, yukarıda açıklandığı gibi.
- **Şifreleme anahtarını veritabanının yanında/aynı ortamda saklamak:** Anahtar veritabanı sunucusunda veya aynı erişim sınırları içinde tutulursa, veritabanını ele geçiren saldırgan anahtarı da alır — şifreleme kağıt üzerinde kalır. Anahtar, ayrı bir güven sınırında (KMS/HSM) olmalı.
- **Aşırı geniş şifreleme kapsamı:** Her sütunu şifrelemek performans, indeksleme (şifreli sütunlarda eşitlik/aralık sorguları zorlaşır) ve operasyonel karmaşıklık maliyeti getirir. Şifrelemeyi gerçekten hassas alanlarla sınırlı tutmak, riski/maliyeti dengelemenin yoludur.
- **Yedeklerin şifreleme kapsamı dışında kalması:** TDE etkinken alınan bir yedek genelde şifreli kalır, ama yedek başka bir sisteme aktarılıp orada şifresi çözülerek saklanırsa (ör. test ortamına "gerçek veriyle" geri yükleme) koruma kaybolur. Yedek yaşam döngüsünün her adımı (alma, taşıma, saklama, geri yükleme, test ortamı) şifreleme politikasına dahil edilmeli.

## Connection String / Secrets Sızıntısı

### Kök Neden

Veritabanı bağlantı bilgisi (host, kullanıcı adı, parola) genellikle uygulamanın en kritik sırrıdır, çünkü bu bilgiyi ele geçiren biri tüm rol/RLS/GRANT mimarisini "yasal" bir bağlantı gibi görünerek by-pass eder — artık SQL Injection'a bile gerek kalmaz. Sızıntı tipik olarak şu yollarla olur: kaynak koduna (ve dolayısıyla git geçmişine) sabit kodlanmış (hardcoded) connection string; ortam değişkenlerinin (environment variables) hata/log çıktısına yanlışlıkla dökülmesi (stack trace, debug modu); yanlış yapılandırılmış CI/CD pipeline'ının secret'ı build log'una yazması; genel (public) bir konteyner imajına gömülü `.env` dosyası.

Kök neden ortak paydası: **sırrın, kod ile aynı yaşam döngüsünde (versiyon kontrolü, log, imaj) taşınmasıdır.** Sır, koddan ayrı bir kanaldan (secrets manager / vault) çalışma zamanında enjekte edilmediği sürece, kodun her kopyalandığı, log'landığı, arşivlendiği yerde sızma riski taşır.

### En İyi Pratikler

- Sırları koddan tamamen ayır: özel bir secrets manager (Vault, bulut sağlayıcının KMS/Secrets Manager hizmeti vb.) kullan, sadece çalışma zamanında ve en dar kapsamda enjekte et.
- Parolaları düzenli rotasyona tabi tut; rotasyon otomatikleştirilmediği sürece genelde hiç yapılmaz.
- Log/hata mesajlarının connection string'i veya parolayı asla içermediğinden emin ol — bu genelde varsayılan ORM/driver hata mesajlarının denetlenmesini gerektirir.
- Git geçmişine kazara commit edilen sırların, sadece dosyayı silmenin yetmediğini unutma — geçmiş temizlenmeli (history rewrite) ve **sır anında geçersiz kılınıp (revoke) rotasyona sokulmalı**, çünkü git geçmişi bir kez public olduysa (veya olma ihtimali varsa) o sır artık ele geçmiş sayılmalıdır.
- En az yetki ilkesini burada da uygula: CI/CD pipeline'ının kullandığı DB kimlik bilgisi, üretim (production) verisine tam erişim yerine sadece gerekli migration/deploy yetkisine sahip olmalı.

## Veritabanı Audit Logging (Denetim İzi)

### Çalışma Mantığı ve Neden Gerekli

Audit logging, "kim, ne zaman, hangi veriye, nasıl eriştiği/değiştirdiği" sorusuna cevap verecek bir iz bırakma mekanizmasıdır. Bunun rolü iki katmanlıdır:

1. **Tespit (detection):** Anomali — örneğin normalde raporlama amaçlı SELECT yapan bir rolün aniden büyük hacimde veri çektiği (data exfiltration belirtisi), ya da normal mesai saatleri dışında yapılan yönetici işlemleri — audit log olmadan fark edilemez.
2. **Adli analiz (forensics) ve hesap verebilirlik:** Bir olay (incident) sonrası "saldırgan tam olarak hangi tabloları, hangi satırları gördü/değiştirdi" sorusu, düzenleyici bildirim yükümlülükleri (ör. kişisel veri ihlali bildirimi) açısından kritik önemdedir. Bu bilgi olmadan kapsam belirlemesi (scoping) tahminden ibaret kalır.

Kök neden perspektifinden: erişim kontrolü (RLS, GRANT) *önleyici* kontroldür — "olmaması gerekeni engeller." Audit log ise *tespit edici* kontroldür — "önleyici kontrol delinirse bunu fark etmemizi sağlar." İkisi birbirinin yedeği değil, tamamlayıcısıdır; hiçbir önleyici kontrol %100 güvenilir olmadığı için tespit katmanı olmadan bir ihlal fark edilmeden aylarca sürebilir.

### Doğru Kullanım, Tuzaklar ve En İyi Pratikler

- **Audit log'un kendisi de bir hedeftir.** Saldırgan, veritabanına yönetici seviyesinde erişim sağladıysa genellikle önce audit log'u silmeye veya durdurmaya çalışır. Bu yüzden audit log kayıtlarının, denetlenen sistemden ayrı, salt-ekleme (append-only) ve mümkünse farklı bir yetki alanında (örn. ayrı bir log toplama sistemine anlık aktarım) tutulması gerekir — aynı DBA rolünün hem veriyi hem audit log'unu silebilmesi, audit log'u anlamsızlaştırır (görev ayrılığı / separation of duties ihlali).
- **Her şeyi loglamak da bir tuzaktır.** Aşırı ayrıntılı loglama (her SELECT'i, her sütunu) hem performansı ciddi ölçüde düşürür hem de log hacmini o kadar büyütür ki gerçek anomali gürültüde kaybolur. Odak, hassas tablolara erişim, yetki/şema değişiklikleri (DDL), yönetici işlemleri ve başarısız kimlik doğrulama denemeleri gibi yüksek sinyal olaylarına verilmeli.
- **Loglar izlenmezse var olmaları hiçbir işe yaramaz.** Audit log'un bir SIEM (Security Information and Event Management) sistemine aktarılıp otomatik kural/anomali tespitine bağlanması gerekir; aksi halde "olay olduktan aylar sonra log'a bakıp anlamak" dışında bir işlevi kalmaz — bu da tespiti değil sadece adli analizi mümkün kılar.
- **Zaman senkronizasyonu (NTP) ihmal edilmemeli.** Farklı sunuculardaki saat kaymaları, olay zaman çizelgesini (timeline) yeniden kurarken ciddi kafa karışıklığına yol açar; adli analiz saniyeler/dakikalar seviyesinde doğru sıralama gerektirir.
- **Audit log'un saklama süresi (retention) düzenleyici gereksinimlerle uyumlu olmalı** — hem çok kısa (delil kaybı) hem çok uzun (gereksiz veri birikimi, kendisi bir sızıntı riski) sorun yaratır.

## Bütüncül Bakış: Katmanların Birlikte Çalışması

Bu beş mekanizma (least-privilege roller, RLS, TDE/sütun şifreleme, secrets hijyeni, audit log) birbirinin yerini tutmaz, birbirini tamamlar. Somut bir senaryo üzerinden özetlemek gerekirse: SQL Injection açığı bulunan bir uygulamayı düşünelim.

- Uygulama en az yetkili bir rolle bağlanıyorsa, saldırgan DROP TABLE yapamaz (least-privilege).
- RLS varsa, saldırganın enjekte ettiği sorgu sadece o oturumun tenant bağlamındaki satırları görür, tüm tabloyu değil (RLS).
- Hassas sütunlar ayrıca şifreliyse, saldırgan satırları görse bile kredi kartı veya kimlik numarasını düz metin göremez (sütun şifreleme).
- Saldırgan connection string'i ayrıca ele geçirmeye çalışırsa, sır koddan/log'dan izole tutulduğu için bu ek adım da başarısız olur (secrets hijyeni).
- Ve her ihtimalde, güvenlik ekibi anormal sorgu hacmini veya erişilen tabloları audit log üzerinden fark edip müdahale edebilir (audit logging).

Tek bir katman delinse bile diğerleri zararı sınırlar — bu, "sistem sertleştirme" başlığının SQL Injection sonrası neden ayrıca ve özel olarak ele alınması gerektiğinin temel gerekçesidir: genel işletim sistemi/ağ sertleştirmesi bu beş mekanizmanın hiçbirini kapsamaz, çünkü bunların hepsi veritabanı motorunun kendi iç dünyasında yaşar.
