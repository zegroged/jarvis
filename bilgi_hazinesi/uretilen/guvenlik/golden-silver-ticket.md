# Golden Ticket ve Silver Ticket Saldırıları

## Giriş ve Bağlam

Golden Ticket ve Silver Ticket, Active Directory ortamlarında Kerberos kimlik doğrulama protokolünün mimari tasarımını istismar eden iki kalıcılık (persistence) ve yetki yükseltme (privilege escalation) tekniğidir. Her ikisi de saldırganın gerçek bir parola bilmeden, sahte fakat kriptografik olarak geçerli Kerberos biletleri (ticket) üretmesine dayanır. Bu saldırılar bir yazılım açığı (vulnerability) değildir; Kerberos'un güven modelinin doğal bir sonucudur. Bu yüzden "yamalanamazlar" (unpatchable) denir. Onları durdurmak yama uygulamakla değil, gerekli anahtarların (key) ele geçirilmesini önlemek ve saldırı sonrası kanıtları tespit etmekle mümkündür.

Bu makale, iki tekniğin kök nedenini (Kerberos'un neden bu şekilde çalıştığını), somut üretim ve kullanım mantığını, hem sömürü hem de savunma perspektifini, sık yapılan hataları ve en iyi pratikleri derinlemesine ele alır.

## Kerberos'un Temel Çalışma Mantığı

Golden ve Silver Ticket'ı anlamak için önce Kerberos'un neden "bilet" temelli bir sistem olduğunu kavramak gerekir. Kerberos'un tasarım amacı, her servis erişiminde kullanıcının parolasını ağ üzerinden tekrar tekrar göndermesini önlemektir. Bunun yerine merkezi bir güven otoritesi olan KDC (Key Distribution Center) devreye girer. Domain controller (DC) üzerinde çalışan KDC iki mantıksal bileşenden oluşur: AS (Authentication Service) ve TGS (Ticket Granting Service).

Akış kabaca şöyledir:

1. Kullanıcı kimliğini kanıtlar (parolasından türetilen anahtarla şifrelenmiş bir zaman damgası göndererek). Buna **pre-authentication** denir.
2. AS, kullanıcıya bir **TGT (Ticket Granting Ticket)** verir. TGT, "bu kullanıcı kimliğini kanıtladı" diyen, KDC'nin kendisine ait gizli bir anahtarla imzalanmış/şifrelenmiş bir kimlik belgesidir.
3. Kullanıcı bir servise (örneğin bir dosya sunucusu, SQL Server, CIFS paylaşımı) erişmek istediğinde TGT'yi TGS'e sunar ve karşılığında o servise özel bir **servis bileti (Service Ticket / TGS ticket)** alır.
4. Servis, kendisine gelen bileti kendi anahtarıyla çözerek kullanıcının kimliğini ve yetkilerini doğrular.

Buradaki kritik nokta şudur: **Kerberos, güvenini şifreleme anahtarlarına dayandırır.** Bir bilet, doğru anahtarla şifrelenmişse geçerli kabul edilir. Sistem, biletin "gerçekten KDC tarafından mı üretildiğini" ayrıca bir veritabanından sorgulamaz; sadece kriptografik doğrulama yapar. İşte Golden ve Silver Ticket bu güven varsayımını tam da bu noktadan kırar.

### PAC ve yetkilendirme verisi

Biletlerin içinde **PAC (Privilege Attribute Certificate)** adı verilen bir veri yapısı bulunur. PAC, kullanıcının SID'ini, üyesi olduğu grupların SID'lerini ve diğer yetkilendirme bilgilerini taşır. Servis, "bu kullanıcı Domain Admins grubunda mı?" sorusunun cevabını PAC'tan okur. Saldırgan sahte bir bilet ürettiğinde PAC'ı da kendisi doldurur; yani "ben Domain Admins üyesiyim" yalanını doğrudan bilete yazar. PAC'ın bütünlüğü imzalarla korunur, ancak bu imzalar yine ele geçirilen anahtarlarla üretildiği için saldırgan geçerli imzalar oluşturabilir.

## krbtgt Hesabı: Golden Ticket'ın Kalbi

Golden Ticket'ın kök nedeni tek bir hesapta düğümlenir: **krbtgt**. Her Active Directory domain'inde, kurulum sırasında otomatik olarak oluşturulan `krbtgt` adlı, devre dışı bırakılmış bir servis hesabı vardır. Bu hesabın parola hash'i, KDC'nin TGT'leri şifrelemek ve imzalamak için kullandığı ana anahtardır.

Mantık şudur: KDC bir TGT ürettiğinde onu krbtgt hesabının anahtarıyla şifreler. Kullanıcı bu TGT'yi geri sunduğunda KDC yine krbtgt anahtarıyla çözer. Yani **TGT'nin geçerliliğinin tek garantisi, krbtgt anahtarının gizliliğidir.** Bu, mimarinin en zarif ve aynı zamanda en tehlikeli yanıdır: TGT geçerliliğini domain controller belleğindeki bir oturum tablosundan değil, salt kriptografiden doğrular.

Bir saldırgan krbtgt hesabının parola hash'ini (tipik olarak NTLM hash'i veya AES anahtarları) ele geçirirse, KDC'nin yerine geçebilir. Artık kendi TGT'lerini üretebilir; içine istediği kullanıcı adını, istediği grup üyeliklerini yazabilir. Bu sahte TGT'ye **Golden Ticket** denir.

### krbtgt hash'i nasıl ele geçirilir

Golden Ticket bir saldırının başlangıcı değil, sonucudur. Saldırganın krbtgt hash'ine ulaşabilmesi için genellikle zaten domain üzerinde yüksek yetki elde etmiş olması gerekir. Tipik yollar:

- **DCSync**: Saldırgan, DC'nin çoğaltma (replication) protokolünü taklit ederek AD'den herhangi bir hesabın parola verisini çeker. Bunun için `Replicating Directory Changes` benzeri yetkiler gerekir; bu yetkiler normalde yalnızca domain controller'larda ve yüksek ayrıcalıklı hesaplarda bulunur.
- **DC'nin NTDS.dit dosyasına erişim**: Active Directory veritabanı olan `ntds.dit` dosyasının kopyalanması (örneğin bir yedekten veya doğrudan DC'den) tüm hesap hash'lerini, dolayısıyla krbtgt'yi de içerir.
- **DC üzerinde LSASS bellek erişimi**: Domain controller'da SYSTEM yetkisiyle bellekten anahtar çıkarımı.

Buradan çıkan kritik gerçek: **Golden Ticket üretebilen bir saldırgan çoktan domain'i ele geçirmiştir.** Golden Ticket'ın asıl değeri ilk erişimde değil, kalıcılıkta yatar.

## Golden Ticket'ın Kalıcılık Değeri

Bir savunmacı, ihlali fark edip Domain Admins parolalarını sıfırladığında, ele geçirilmiş kullanıcı hesaplarını devre dışı bıraktığında saldırganın erişimini kestiğini düşünür. Ancak Golden Ticket varsa bu yanılgıdır. Saldırgan elindeki krbtgt hash'iyle **var olmayan bir kullanıcı için bile** geçerli TGT üretebilir; PAC içine doğrudan Domain Admins ve hatta Enterprise Admins SID'lerini yazar. Sıradan bir kullanıcı hesabının parolasını değiştirmek bu bileti geçersiz kılmaz, çünkü bilet o hesabın parolasıyla değil, krbtgt anahtarıyla korunmaktadır.

Golden Ticket'ı geçersiz kılmanın tek gerçek yolu **krbtgt hesabının parolasını sıfırlamaktır** ve burada kritik bir incelik vardır: krbtgt için AD, geçerli ve önceki (N ve N-1) olmak üzere iki parola sürümünü kabul eder. Bu, çoğaltma sırasında kesintiyi önlemek içindir. Dolayısıyla parolayı yalnızca bir kez sıfırlamak yeterli değildir; saldırgan hâlâ eski hash'le üretilmiş biletleri kullanabilir. **krbtgt parolası art arda iki kez sıfırlanmalıdır** (aralarında çoğaltmanın tamamlanmasına yetecek süre bırakılarak). Bunu aceleyle iki kez üst üste yapmak, çoğaltma tamamlanmadan hem N hem N-1 sürümünün aynı anda değişmesine ve domain genelinde kimlik doğrulama arızalarına yol açabilir; bu yüzden dikkatli planlama gerektirir.

### Golden Ticket'ın tehlikeli esneklikleri

Sahte TGT üreten saldırgan birçok alanı serbestçe belirleyebildiği için tespit ipuçları da buradan doğar:

- **Bilet ömrü**: Meşru Kerberos politikaları TGT'ye tipik olarak 10 saatlik bir ömür ve 7 günlük yenileme sınırı verir. Saldırganlar geçmişte 10 yıl gibi absürt ömürler girerek bileti kalıcı hale getirmeye çalışmıştır. Bu anormal ömür, tespit için değerli bir işarettir.
- **Var olmayan hesaplar**: Bilet, AD'de artık silinmiş ya da hiç var olmamış bir kullanıcı adına düzenlenebilir.
- **Grup SID'leri**: PAC içine 512 (Domain Admins), 519 (Enterprise Admins) gibi güçlü grup RID'leri elle yazılabilir.

## Silver Ticket: Hedefli ve Daha Sessiz Saldırı

Silver Ticket, Golden Ticket'ın daha dar kapsamlı ama çoğu zaman daha sinsi olan kardeşidir. Farkı anlamak için ölçek sorusunu sormak gerekir: **Golden Ticket TGT'yi sahteler; Silver Ticket ise doğrudan servis biletini (TGS ticket) sahteler.**

Kerberos akışını hatırlayalım: normalde kullanıcı bir servise erişmek için önce KDC'den servis bileti almalıdır. Ancak servis, kendisine gelen bileti kendi hesabının anahtarıyla çözerek doğrular. **Servis, o biletin gerçekten KDC tarafından mı verildiğini KDC'ye sormaz.** İşte Silver Ticket bu boşluğu istismar eder.

Saldırgan, **hedef servisin hesabının parola hash'ini** ele geçirirse (KDC'nin krbtgt'sini değil), o servis için doğrudan geçerli bir servis bileti imzalayabilir. KDC hiç devreye girmez. Bu yüzden Silver Ticket:

- **Sadece belirli bir servisi** (örneğin belirli bir sunucudaki CIFS, HTTP, MSSQL, HOST servisi) hedefler.
- **KDC'de iz bırakmaz**, çünkü TGS'e hiç TGS-REQ isteği gitmez. Bu, DC log'larında Golden Ticket'a kıyasla çok daha az kanıt anlamına gelir ve tespiti zorlaştırır.

### Hangi hash gerekir

Silver Ticket için gereken hash, hedef servisin çalıştığı hesabın hash'idir:

- Bir bilgisayarın makine hesabı (`MACHINE$`) hash'i, o makinedeki CIFS, HOST, RPCSS gibi çok sayıda servisi kapsar. Yani bir makine hesabının hash'i, o makineye SMB üzerinden yönetimsel erişim gibi güçlü yeteneklere kapı açabilir.
- Bir uygulama servis hesabı (örneğin bir SQL Server servis hesabı) hash'i, yalnızca o SPN'e (Service Principal Name) ait erişim sağlar.

Bu yüzden Silver Ticket genellikle **Kerberoasting** ile birlikte anılır: Kerberoasting'de saldırgan, bir SPN'e ait servis biletini talep edip çevrimdışı olarak servis hesabının parolasını kırmaya çalışır. Zayıf parolalı bir servis hesabı kırıldığında, saldırgan artık o servis için Silver Ticket üretebilir.

### Silver Ticket'ın kalıcılık ve gizlilik avantajı

Silver Ticket'ın domain genelinde etkisi Golden Ticket kadar geniş değildir; tek bir servisle sınırlıdır. Ancak makine hesabı parolaları, varsayılan yapılandırmada belirli aralıklarla (tipik olarak yaklaşık 30 gün) otomatik değiştirilse de, bu değişim her ortamda etkin olmayabilir veya devre dışı bırakılmış olabilir. Bir servis hesabının parolası nadiren değiştiriliyorsa, o servise ait Silver Ticket uzun süre geçerli kalır. Gizliliği yüksek olduğundan hedefli casusluk ve sessiz kalıcılık için tercih edilir.

## PAC Doğrulaması: Neden Silver Ticket Bazen Çalışır

Silver Ticket'ın çalışabilmesinin altında bir tasarım tercihi yatar. Servis, bileti çözdükten sonra PAC içindeki imzayı isteğe bağlı olarak KDC'ye doğrulatabilir (**PAC validation**). Eğer bu doğrulama yapılsaydı, servis "bu PAC'ı gerçekten sen mi imzaladın?" diye KDC'ye sorar ve sahte bilet açığa çıkardı.

Ancak pratikte performans nedenleriyle birçok servis PAC doğrulamasını her istekte yapmaz; özellikle servis SYSTEM veya yerel yönetici bağlamında çalışıyorsa bu doğrulama sıklıkla atlanır. Microsoft, PAC ile ilgili bilinen istismarları kısıtlamak için zaman içinde güncellemeler yayımlamıştır (özellikle sahte PAC imzalarını ve belirli baypasları hedefleyen sıkılaştırmalar). Burada dürüst olmak gerekirse: bu güncellemelerin kesin tarihleri ve KB numaraları zamanla değiştiği için, savunmacıların **domain controller'ları ve üyeleri güncel tutması** ve Microsoft'un yayımladığı Kerberos/PAC sıkılaştırma yönergelerini takip etmesi doğru yaklaşımdır. Genel ilke değişmez: PAC imzalarının daha güçlü doğrulanması, sahte bilet üretimini zorlaştırır.

## Somut Senaryo: Uçtan Uca Bir Saldırı Zinciri

Kavramları bir hikâyede birleştirelim.

1. **İlk erişim**: Saldırgan bir oltalama (phishing) e-postasıyla sıradan bir kullanıcının iş istasyonuna yerleşir. Bu kullanıcının hiçbir yönetici yetkisi yoktur.
2. **Keşif ve Kerberoasting**: Saldırgan domain'deki SPN'leri listeler, zayıf parolalı bir servis hesabı için servis bileti talep eder ve çevrimdışı kırarak parolayı elde eder. Artık bu servis için **Silver Ticket** üretip o servise sessizce erişebilir.
3. **Yatay hareket ve yetki yükseltme**: Saldırgan zamanla bir yöneticinin oturum açtığı bir makineye ulaşır, o oturumdan yüksek yetkili kimlik bilgilerini toplar ve nihayet bir domain controller'a yönetimsel erişim kazanır.
4. **DCSync**: DC üzerinde yeterli yetkiyle saldırgan `krbtgt` dahil tüm hesapların hash'lerini çoğaltma protokolüyle çeker.
5. **Golden Ticket ile kalıcılık**: Saldırgan krbtgt hash'iyle, gerektiğinde Domain Admins yetkisinde TGT üretebilen bir Golden Ticket hazırlar. Artık ele geçirdiği tüm parolalar sıfırlansa bile, krbtgt sıfırlanmadıkça (üstelik iki kez) geri dönebilir.

Bu zincir, iki tekniğin saldırı yaşam döngüsündeki farklı rollerini gösterir: Silver Ticket erken, sessiz ve hedefli; Golden Ticket geç, güçlü ve kalıcı.

## Savunma: Önleme Katmanı

Bu saldırılar yamalanamayacağına göre savunma stratejisi iki eksende toplanır: **anahtarların ele geçirilmesini önlemek** ve **ele geçirildikten sonra tespit edip etkisini sınırlamak.**

### krbtgt ve servis hesaplarını korumak

- **krbtgt parolasını düzenli olarak, doğru prosedürle döndürün.** Yılda en az bir veya iki kez, ve mutlaka bir ihlal şüphesinden sonra. Her döndürmede N/N-1 sürüm mantığı nedeniyle iki aşamalı yapılmalı, aralarında çoğaltmanın tamamlanması beklenmelidir. Aksi halde domain genelinde kimlik doğrulama kesintisi riski vardır.
- **Servis hesaplarında gMSA (group Managed Service Account) kullanın.** gMSA hesaplarının parolaları çok uzun (128 karakter mertebesinde), rastgele ve otomatik döndürülen anahtarlardır. Bu, hem Kerberoasting ile kırılmayı pratikte imkânsız kılar hem de Silver Ticket için gereken hash'in çalınsa bile hızla eskimesini sağlar.
- **Zayıf servis hesabı parolalarını yok edin.** Kerberoasting'in başarısı doğrudan parola zayıflığına bağlıdır. Uzun, karmaşık parolalar Silver Ticket'ın hammaddesini kurutur.

### Yönetimsel erişimi ve DCSync yolunu kısıtlamak

- **Tier modeli (katmanlı yönetim) uygulayın.** Domain controller'a erişebilen ayrıcalıklı hesapları, günlük iş istasyonlarından ve internete açık sistemlerden yalıtın. Golden Ticket'ın ön koşulu DC seviyesinde yetki olduğuna göre, bu yolu kapatmak saldırıyı kaynağında engeller.
- **Çoğaltma yetkilerini denetleyin.** `Replicating Directory Changes` benzeri hakların hangi hesaplarda olduğunu düzenli gözden geçirin; yalnızca DC'lerde ve gerekli senkronizasyon hesaplarında bulunmalıdır. Beklenmedik bir hesapta bu hak, DCSync'e açık kapıdır.
- **Kimlik bilgisi hijyeni**: LSASS bellek korumasını etkinleştirin (Credential Guard gibi mekanizmalar), yönetici oturumlarını güvenilmeyen makinelerde açmaktan kaçının, en az ayrıcalık ilkesini uygulayın.

### Kriptografiyi güçlendirmek

- **AES şifrelemesini zorunlu kılın, RC4'ü devre dışı bırakın.** Eski RC4 tabanlı Kerberos şifrelemesi, NTLM hash'iyle doğrudan bilet üretmeyi kolaylaştırır ve daha zayıftır. AES'e geçiş hem kırmayı zorlaştırır hem de yalnızca RC4 kullanan sahte biletlerin anomali olarak öne çıkmasını sağlar.

## Savunma: Tespit Katmanı

Önleme mükemmel olmadığından tespit hayatidir. Sahte biletlerin bıraktığı izler, meşru Kerberos trafiğinden sapmalarında gizlidir.

### Golden Ticket tespiti

- **Anormal bilet ömrü ve alanları**: Politikanın izin verdiğinden çok daha uzun ömürlü TGT'ler güçlü bir işarettir. Bazı sahte bilet araçları alanları eksik veya tutarsız doldurur; örneğin bilet içindeki alan değerleri gerçek KDC'nin ürettiğiyle uyuşmaz.
- **TGT olmadan servis bileti isteği**: Meşru akışta bir kullanıcı önce AS'ten TGT alır (olay kaydında AS-REQ/TGT verilişi), sonra TGS'ten servis bileti ister. Golden Ticket'ta saldırgan TGT'yi kendisi ürettiğinden, DC'de karşılık gelen bir TGT veriliş kaydı olmadan TGS istekleri görülebilir. Domain controller güvenlik günlüklerinde Kerberos ile ilgili olayları (TGT ve servis bileti verilişi) korele etmek bu uyumsuzluğu ortaya çıkarır.
- **Var olmayan veya devre dışı hesaplarla kimlik doğrulama**: AD'de bulunmayan ya da devre dışı bırakılmış bir kullanıcı adının Kerberos üzerinden geçerli sayılması ciddi bir alarmdır.
- **SID history / grup uyumsuzlukları**: Bir hesabın bilet PAC'ında, gerçek AD üyeliğiyle çelişen yüksek ayrıcalıklı grup SID'lerinin görünmesi.

### Silver Ticket tespiti

Silver Ticket tespiti daha zordur çünkü DC devreye girmez ve merkezi log üretmez. Bu nedenle tespit büyük ölçüde **hedef sunucunun kendi günlüklerine** kayar:

- **DC'de karşılığı olmayan servis oturumları**: Bir sunucuda başarılı Kerberos oturum açma olayları varken, DC'de o kullanıcıya ait ilgili bilet veriliş kaydının bulunmaması. Bu korelasyon, KDC atlanarak üretilmiş bir bilete işaret eder.
- **Anormal PAC veya şifreleme türü**: Sadece RC4 ile şifrelenmiş biletler (ortam AES'e geçmişken), tutarsız PAC imzaları.
- **PAC doğrulamasını etkinleştirmek**: Kritik servislerde PAC validation'ı zorlamak, sahte bileti doğrudan reddettirebilir; bu hem bir önleme hem de dolaylı bir tespit mekanizmasıdır.

Genel prensip: **DC ve üye sunucu günlüklerini merkezi bir SIEM'de toplayıp korele edin.** Tek başına bir sunucunun logu sahte bileti göstermeyebilir; ama "sunucuda oturum var, DC'de karşılığı yok" gibi çapraz sinyaller ortaya çıkar. Ayrıca modern EDR ve kimlik güvenliği ürünleri (örneğin AD saldırı tespitine odaklı çözümler) bu anomalileri davranışsal olarak yakalamaya çalışır.

## Yaygın Hatalar

- **"Parolaları sıfırladık, temizlendik" yanılgısı**: Bir ihlalden sonra kullanıcı ve yönetici parolaları sıfırlanır ama krbtgt unutulur. Golden Ticket bu boşlukta yaşamaya devam eder. Ihlal müdahalesinde krbtgt döndürme zorunlu bir adımdır.
- **krbtgt'yi bir kez sıfırlamak**: N/N-1 mekanizması nedeniyle tek sıfırlama eski biletleri geçersiz kılmaz. İki aşamalı yapılmalıdır.
- **krbtgt'yi çok hızlı iki kez sıfırlamak**: Çoğaltma tamamlanmadan yapılan ardışık iki sıfırlama, domain genelinde Kerberos arızalarına yol açabilir. Doğru zamanlama şarttır.
- **Servis hesaplarını ihmal etmek**: Golden Ticket'a odaklanıp Silver Ticket riskini görmezden gelmek. Zayıf parolalı, yıllardır değişmemiş servis hesapları Silver Ticket için hazır zemindir.
- **RC4'ü açık bırakmak**: Eski uyumluluk kaygısıyla RC4'ün etkin kalması hem saldırıyı kolaylaştırır hem de anomali tespitini zayıflatır.
- **Sadece DC loglarına güvenmek**: Silver Ticket DC'de iz bırakmadığından, yalnızca DC izleyen bir tespit stratejisi bu saldırıyı tümüyle kaçırır.
- **PAC doğrulamasının her yerde yapıldığını varsaymak**: Performans nedeniyle sıkça atlandığı gerçeği göz ardı edilir.

## En İyi Pratikler

- **En az ayrıcalık ve katmanlı yönetim**: Domain controller erişimini sıkı biçimde sınırlayın. Golden Ticket'ın ön koşulunu ortadan kaldırmak, en güçlü savunmadır.
- **gMSA ve güçlü servis hesabı parolaları**: Silver Ticket ve Kerberoasting'in hammaddesini yok edin.
- **Düzenli, prosedürel krbtgt döndürme**: Planlı ve iki aşamalı; ihlal sonrası mutlaka.
- **AES zorunlu, RC4 kapalı**: Kriptografik zemini güçlendirin.
- **Kapsamlı log toplama ve korelasyon**: DC ve üye sunucu Kerberos olaylarını merkezi olarak toplayın; "biletsiz servis erişimi", "anormal ömür", "var olmayan hesap" gibi kalıpları arayın.
- **Kimlik bilgisi koruma teknolojileri**: Credential Guard, LSASS koruması ve hash çalınmasını zorlaştıran mekanizmalar.
- **Sürekli güncelleme**: Microsoft'un Kerberos/PAC sıkılaştırma güncellemelerini takip edip uygulayın; bu, sahte bilet üretimini giderek zorlaştırır.
- **Varsayım ihlal (assume breach) zihniyeti**: Bu saldırılar zaten yetki elde edilmiş bir saldırganı varsaydığından, savunmayı yalnızca çevre güvenliğine değil, iç tespit ve kalıcılık avcılığına da yatırın.

## Sonuç

Golden ve Silver Ticket, Active Directory'nin en ciddi kalıcılık tehditlerindendir çünkü bir hataya değil, Kerberos'un güven modeline dayanırlar. Golden Ticket, krbtgt anahtarını ele geçiren saldırgana domain üzerinde neredeyse silinemez bir tanrı yetkisi verir; Silver Ticket ise tek bir servisi sessizce, KDC'yi atlayarak hedef alır. İkisinin de panzehiri aynı temel disiplindir: kritik anahtarları (krbtgt ve servis hesapları) korumak, yönetimsel erişimi katmanlamak, kriptografiyi güçlendirmek ve DC ile üye sunucu günlüklerini korele ederek sahte biletlerin kaçınılmaz izlerini avlamak. Yama yoktur; ama disiplinli kimlik güvenliği vardır.
