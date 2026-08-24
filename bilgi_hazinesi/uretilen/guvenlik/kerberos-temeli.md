# Kerberos Derinlemesine: AS/TGS Akışı, Bilet Yapısı ve Saldırı Yüzeyi

## Kerberos Nedir ve Hangi Problemi Çözer?

Kerberos, güvenilmez (untrusted) bir ağ üzerinde çalışan istemci ve sunucuların birbirini karşılıklı olarak kanıtlamasını (mutual authentication) sağlayan, simetrik anahtar (symmetric key) kriptografisine dayalı bir kimlik doğrulama protokolüdür. MIT tarafından geliştirilmiş, bugün RFC 4120 ile tanımlanan versiyonu (Kerberos v5) yaygın olarak kullanılmaktadır. Windows Active Directory ortamlarının kimlik doğrulama omurgası tam olarak budur.

Kerberos'un çözdüğü asıl problem şudur: Ağ üzerinden parolayı (password) hiçbir zaman açık metin (cleartext) olarak göndermeden, hatta çoğu adımda hiç göndermeden, bir kullanıcının bir servise erişim hakkını kanıtlayabilmek. Ayrıca merkezi bir güven otoritesi (KDC) üzerinden Single Sign-On (SSO) sağlamak: kullanıcı bir kez kimliğini kanıtlar, sonra gün boyu onlarca farklı servise tekrar parola girmeden erişir.

Protokolün ismi Yunan mitolojisindeki üç başlı köpek Kerberos'tan gelir çünkü üç aktör vardır: **istemci (client)**, **erişilmek istenen servis (server)** ve **güvenilen üçüncü taraf olan KDC (Key Distribution Center)**.

## Temel Aktörler ve Kavramlar

Anlatıyı doğru kurmak için önce oyuncuları tanımlamak gerekir:

- **KDC (Key Distribution Center):** Güvenin merkezindeki servis. İki mantıksal bileşeni vardır: **AS (Authentication Service)** ve **TGS (Ticket Granting Service)**. Windows'ta KDC rolünü Domain Controller (DC) üstlenir.
- **Principal:** Bir kimliğin benzersiz adı. Kullanıcı, bilgisayar veya servis olabilir. Örneğin `kullanici@ALAN.LOCAL` veya bir servis için `HTTP/web01.alan.local`.
- **SPN (Service Principal Name):** Bir servisi domain içinde benzersiz olarak tanımlayan isim. TGS'ten bilet isterken hangi servise erişileceğini bu SPN belirler.
- **Realm / Domain:** Güven sınırı. Tüm principal'lar bir realm'e aittir.
- **Long-term key:** Her principal'ın uzun ömürlü gizli anahtarı. Kullanıcılar için bu anahtar tipik olarak parolanın bir hash'inden (Windows'ta NTLM hash veya AES anahtarı) türetilir. KDC bu anahtarların tümünü bilir; işin sırrı budur.

Kerberos'un temel dayanağı şudur: Simetrik kriptografide, bir mesajı yalnızca doğru anahtara sahip olan taraf çözebilir. Eğer KDC, sizin long-term key'inizle şifrelenmiş bir mesajı çözebildiyseniz, demek ki gerçekten sizsiniz. Parolayı göndermeye gerek kalmaz; parolanın türevi olan anahtarla bir şeyi çözebilmek kimliğin kanıtıdır.

## AS Akışı (Authentication Service Exchange): TGT'nin Alınması

Sürecin ilk yarısı, kullanıcının kendini KDC'ye kanıtlaması ve karşılığında bir **TGT (Ticket Granting Ticket)** almasıdır. Adımları ve arkasındaki mantığı inceleyelim.

### AS-REQ (İstek)

İstemci, KDC'nin AS bileşenine bir istek gönderir. Bu istekte kim olduğunu (principal adı), hangi realm'de olduğunu ve ne istediğini belirtir. Kritik nokta **pre-authentication** kısmıdır.

Pre-authentication'da istemci, güncel zaman damgasını (timestamp) kendi long-term key'iyle şifreler ve isteğe ekler. Bu neden gereklidir? Çünkü pre-auth olmadan, herhangi biri "ben bu kullanıcıyım" diyerek AS-REQ gönderebilir ve KDC ona kullanıcının anahtarıyla şifrelenmiş bir cevap verirdi. İşte bu cevap, offline parola kırma (offline password cracking) için hediye olurdu. Pre-auth, KDC cevap üretmeden önce istemcinin gerçekten anahtarı bildiğini kanıtlamasını zorunlu kılar.

### AS-REP (Cevap)

KDC, gelen şifrelenmiş timestamp'i kullanıcının veritabanındaki long-term key'iyle çözmeye çalışır. Başarılı olursa ve timestamp güncelse (clock skew toleransı içinde, tipik olarak 5 dakika), kimlik doğrulanmış sayılır. KDC iki şey üretir:

1. **TGT (Ticket Granting Ticket):** İçinde bir **session key** (oturum anahtarı), kullanıcının kimliği, geçerlilik süresi ve yetkilendirme verileri bulunur. Kritik olan şu: TGT, **KDC'nin kendi gizli anahtarıyla (krbtgt hesabının anahtarı)** şifrelenir. Yani TGT'yi yalnızca KDC çözebilir; istemci TGT'nin içeriğini okuyamaz, sadece taşır.

2. **Session key (istemci kopyası):** Aynı session key, ayrıca kullanıcının long-term key'iyle şifrelenerek istemciye gönderilir. İstemci bunu çözer ve session key'i öğrenir.

Buradaki tasarım dehası şudur: Artık istemci ile KDC, sadece ikisinin bildiği bir session key paylaşır. İstemci long-term key'ini (yani parola türevini) her istekte tekrar kullanmak zorunda kalmaz; bunun yerine kısa ömürlü session key'i kullanır. Bu, long-term key'in ağda minimum kullanımını sağlar.

## TGS Akışı (Ticket Granting Service Exchange): Servis Biletinin Alınması

Kullanıcı artık elinde bir TGT ile dolaşır. Belirli bir servise (örneğin bir dosya sunucusu veya web uygulaması) erişmek istediğinde ikinci yarı devreye girer.

### TGS-REQ (İstek)

İstemci, TGS bileşenine şunları gönderir:

- **TGT** (AS aşamasında aldığı, krbtgt anahtarıyla şifreli olan bilet).
- **Erişmek istediği servisin SPN'i.**
- **Authenticator:** İstemcinin güncel timestamp'ini, AS aşamasında öğrendiği **session key** ile şifrelemesiyle oluşturulur.

Neden authenticator gerekli? TGT tek başına yeterli değildir çünkü TGT çalınabilir. Authenticator, biletin sahibinin gerçekten session key'i bildiğini kanıtlar. TGT "sen kimsin" sorusunun cevabı, authenticator ise "şu an bu biletin gerçek sahibi sen misin" sorusunun cevabıdır. Timestamp'in taze olması, aynı authenticator'ın tekrar oynatılmasını (replay) engeller.

### TGS-REP (Cevap)

TGS, önce TGT'yi krbtgt anahtarıyla çözer (KDC'nin kendisi olduğu için bu anahtarı bilir). İçinden session key'i çıkarır, sonra authenticator'ı bu session key'le çözer. Timestamp taze ve tutarlıysa istek meşrudur. TGS şunu üretir:

1. **Service Ticket (servis bileti):** İçinde yeni bir **service session key** ve kullanıcının kimliği bulunur. Bu bilet, **hedef servisin long-term key'iyle** şifrelenir. Yani bu bileti yalnızca hedef servis çözebilir.

2. **Service session key (istemci kopyası):** Aynı anahtar, TGT session key'iyle şifrelenerek istemciye verilir.

Dikkat edilmesi gereken kritik ve saldırı yüzeyi açısından önemli bir gerçek: **TGS, kullanıcının o servise gerçekten erişim yetkisi olup olmadığını bu aşamada kontrol etmez.** TGS sadece "kimlik geçerli mi" ve "SPN mevcut mu" sorularına bakar. Asıl yetkilendirme kararı servisin kendisine bırakılmıştır. Bu tasarım detayı, ilerideki Kerberoasting saldırısının kök nedenidir.

### AP-REQ / AP-REP (Servise Erişim)

İstemci artık service ticket'ı doğrudan hedef servise sunar, yanına yine yeni service session key ile şifrelenmiş bir authenticator ekler. Servis, kendi long-term key'iyle bileti çözer, service session key'i çıkarır, authenticator'ı doğrular. İsterse istemciye kendi kimliğini de kanıtlayabilir (mutual authentication). Böylece parola hiçbir noktada servise gitmeden erişim sağlanır.

## Bilet Yapısı: İçeride Ne Var?

Bir Kerberos biletinin (özellikle TGT'nin) içeriğini anlamak, saldırıları anlamak için şarttır. Kavramsal olarak bir bilet şunları barındırır:

- **Şifrelenmemiş kısım (unencrypted):** Realm ve servis adı gibi yönlendirme bilgileri. Biletin kime ait olduğunu KDC'nin bilebilmesi için gerekli minimum meta veri.
- **Şifrelenmiş kısım (encrypted part):** Asıl değerli veriler burada, ve bilenin sahibi tarafından **okunamaz**. İçinde şunlar bulunur:
  - **Session key:** İstemci ve KDC (veya istemci ve servis) arasında paylaşılan kısa ömürlü anahtar.
  - **Client principal:** Biletin sahibinin kimliği.
  - **Geçerlilik süreleri:** starttime, endtime, renew-till gibi zaman kısıtları.
  - **Flags:** Biletin özellikleri (forwardable, renewable, pre-authenticated vb.).

Windows dünyasında TGT'nin şifreli kısmında ayrıca **PAC (Privilege Attribute Certificate)** yer alır. PAC, kullanıcının SID'ini, üye olduğu grupları ve yetkilerini taşır. Servisler yetkilendirme kararını büyük ölçüde PAC'a bakarak verir. PAC'ın bütünlüğü KDC'nin anahtarıyla imzalandığı için, teorik olarak istemci PAC'ı değiştiremez. Bu imzanın kusurlu doğrulanması, geçmişte ciddi yetki yükseltme (privilege escalation) zafiyetlerinin temeli olmuştur; en bilineni PAC doğrulamasındaki bir mantık hatasına dayanan ve alan (domain) genelinde yetki yükseltmeye izin veren zafiyet ailesidir.

## Saldırı Yüzeyi: Sömürü Mantığı ve Savunma

Şimdi işin siber güvenlik tarafına, yani protokolün tasarım ve uygulama detaylarının nasıl istismar edildiğine gelelim. Her saldırıyı kök nedeni, sömürü mantığı ve savunmasıyla birlikte ele alacağım.

### AS-REP Roasting

**Kök neden:** Pre-authentication, kullanıcı bazında devre dışı bırakılabilen bir özelliktir. Bir hesapta "Do not require Kerberos preauthentication" ayarı açıksa, saldırgan o kullanıcı adına AS-REQ gönderdiğinde KDC, hiçbir kanıt istemeden AS-REP döner. AS-REP'in bir kısmı ise kullanıcının parola türevli anahtarıyla şifrelenmiştir.

**Sömürü mantığı:** Saldırgan, kimlik doğrulaması yapmadan bu şifrelenmiş bloğu elde eder. Bu blok aslında kullanıcının parolasına dayalı bir şifreleme olduğundan, offline olarak sözlük/brute-force saldırısıyla parola kırılmaya çalışılır. Domain'e ait düşük yetkili bir konum bile bu hesapları listelemeye yeter; bazı durumlarda kimlik doğrulaması olmadan bile denenebilir.

**Savunma:** Pre-authentication'ı zorunlu tutun; istisna yapmayın. Zorunlu olarak kapatılması gereken eski uyumluluk (legacy) durumları varsa, o hesaplara çok uzun ve rastgele parolalar atayın (tercihen gMSA gibi yönetilen hesaplar kullanın). AS-REP roasting girişimlerini tespit etmek için, aynı kaynaktan çok sayıda farklı kullanıcı için pre-auth gerektirmeyen AS-REP üretimini izleyin.

### Kerberoasting

**Kök neden:** Yukarıda vurguladığım gibi, TGS servis bileti verirken kullanıcının o servise yetkisi olup olmadığını kontrol etmez. Ayrıca service ticket, **servis hesabının long-term key'iyle** şifrelenir ve bu anahtar servis hesabının parolasından türetilir.

**Sömürü mantığı:** Domain'de kimliği doğrulanmış herhangi bir kullanıcı (yani düşük yetkili bir hesap bile), bir SPN'e sahip herhangi bir servis hesabı için TGS-REQ gönderip service ticket alabilir. Bu bileti belleğe/diske alan saldırgan, biletin servis hesabı anahtarıyla şifreli kısmını offline olarak kırmaya çalışır. Eğer servis hesabının parolası zayıfsa, açık metin parola ele geçirilir. Bilhassa insan tarafından yönetilen, zayıf parolalı, SPN atanmış servis hesapları (örneğin SQL servis hesapları) birincil hedeftir.

**Savunma:** Servis hesaplarına çok uzun (25+ karakter), rastgele parolalar verin; ideal olarak **Group Managed Service Accounts (gMSA)** kullanın, çünkü bunların parolaları otomatik olarak çok uzun ve rastgele üretilip periyodik döndürülür (rotate). Şifreleme türü olarak zayıf RC4 yerine AES kullanımını zorlayın. Gereksiz SPN'leri kaldırın. Tespit tarafında, tek bir kullanıcının kısa sürede çok sayıda farklı SPN için service ticket istemesi ve özellikle RC4 (etype 23) talep edilmesi kuvvetli bir Kerberoasting sinyalidir.

### Pass-the-Ticket (PtT)

**Kök neden:** Kerberos, biletin taşıyıcısına güvenir. Bir bilet ve ilgili session key, bir makinenin belleğinden çalınabilirse, başka bir yerde tekrar kullanılabilir. Bilet "bearer" mantığıyla çalışır: elinde geçerli bilet olan, o kimlikmiş gibi davranır.

**Sömürü mantığı:** Saldırgan bir makinede yönetici yetkisi elde ettiğinde, LSASS bellek alanından geçerli TGT veya service ticket'ları çıkarır ve kendi oturumuna enjekte eder. Böylece kurbanın kimliğiyle, parolayı hiç bilmeden, ağdaki servislere erişir.

**Savunma:** Bilet ömürlerini kısa tutun (TGT geçerlilik ve yenileme sürelerini makul minimumda bırakın). Ayrıcalıklı hesaplarla rastgele iş istasyonlarında oturum açmayın (tiered admin modeli). LSASS'ı Credential Guard gibi bellek koruma mekanizmalarıyla koruyun. Yanal hareketi (lateral movement) sınırlamak için ağ segmentasyonu uygulayın.

### Golden Ticket ve Silver Ticket

Bu ikisi, en yıkıcı saldırılardır çünkü doğrudan güvenin köküne saldırırlar.

**Golden Ticket'ın kök nedeni:** Tüm TGT'ler **krbtgt hesabının anahtarıyla** şifrelenir. Eğer saldırgan krbtgt hesabının anahtarını (hash'ini) ele geçirirse, kendi TGT'lerini üretebilir. KDC, kendi anahtarıyla üretilmiş her TGT'yi geçerli kabul eder çünkü onu ancak KDC üretebilir varsayımı vardır.

**Sömürü mantığı:** krbtgt hash'i ile saldırgan, istediği kullanıcı için, istediği gruplarla (örneğin Domain Admins) ve çok uzun geçerlilik süresiyle sahte TGT üretir. Bu TGT ile domain'de neredeyse sınırsız erişim elde edilir. Bu, tam domain ele geçirmesi (domain compromise) anlamına gelir.

**Silver Ticket'ın farkı:** Silver ticket, krbtgt yerine **belirli bir servisin** long-term key'iyle sahte **service ticket** üretmektir. Kapsamı o tek servisle sınırlıdır ama KDC ile hiç konuşulmadığı için tespiti daha zordur; çünkü TGS-REQ hiç oluşmaz.

**Savunma:** krbtgt hesabının anahtarını korumak her şeydir. krbtgt parolasını düzenli olarak, üstelik **iki kez arka arkaya** (çünkü Kerberos mevcut ve önceki anahtarı da kabul eder) döndürün; bir domain kontrolcüsü ele geçirilmesi şüphesinde bunu mutlaka yapın. Silver ticket'a karşı, servislerin PAC doğrulamasını KDC'ye teyit ettirmesini sağlayacak yapılandırmaları etkinleştirin. Genel olarak, bu saldırılar zaten "domain zaten ele geçirilmiş" seviyesini gösterdiğinden, asıl savunma DC'lerin ve ayrıcalıklı kimlik bilgilerinin en baştan korunmasıdır.

### Delegation Kötüye Kullanımı

**Kök neden:** Kerberos delegation, bir servisin kullanıcının kimliğiyle başka bir servise erişmesine izin verir (örneğin bir web sunucusunun, kullanıcı adına arka uç veritabanına erişmesi). Unconstrained delegation'da servis, kullanıcının TGT'sinin bir kopyasını tutar.

**Sömürü mantığı:** Unconstrained delegation'a sahip bir makine ele geçirilirse, oraya kimlik doğrulaması yapan tüm kullanıcıların (bir DC hesabı dahil olabilir) TGT'leri belleğe düşer ve saldırgan bunları kötüye kullanır. Constrained delegation ve resource-based constrained delegation (RBCD) yapılandırmalarındaki hatalar da, saldırganın belirli hesaplara karşı kendini başka bir kullanıcı gibi göstermesine (impersonation) yol açabilir.

**Savunma:** Unconstrained delegation'dan mümkün olduğunca kaçının. Hassas hesapları "Account is sensitive and cannot be delegated" olarak işaretleyin veya Protected Users grubuna alın. Constrained delegation kullanılıyorsa yalnızca gereken servislere izin verin. RBCD yazma yetkilerini sıkı kontrol edin; makine hesabı özniteliklerini değiştirebilen düşük yetkili kullanıcılar tehlikelidir.

## Yaygın Hatalar

Deneyimlerden süzülen, sık tekrarlanan yanlışlar şunlardır:

- **Zayıf servis hesabı parolaları:** Kerberoasting'in var olma sebebi budur. "Servis hesabı, kimse görmüyor" düşüncesiyle atanan basit parolalar, offline kırma için mükemmel hedeftir.
- **RC4 şifrelemenin hâlâ etkin bırakılması:** Eski uyumluluk gerekçesiyle açık bırakılan RC4 (etype 23), hem daha zayıf hem de Kerberoasting'i kolaylaştırır. AES tercih edilmelidir.
- **krbtgt parolasının hiç döndürülmemesi:** Birçok ortamda krbtgt parolası kurulumdan beri hiç değiştirilmemiştir. Bir kez ele geçirilirse ve döndürülmezse golden ticket süresiz geçerli kalır.
- **Pre-authentication istisnaları:** "Şu eski uygulama için pre-auth kapattık" denilip unutulan hesaplar, AS-REP roasting açar.
- **Clock skew ve zaman senkronizasyonu ihmali:** Kerberos zaman damgalarına dayanır. Makineler arası saat farkı toleransı aşarsa (tipik 5 dakika), kimlik doğrulama sessizce bozulur. Bu bir saldırı değil ama sık yaşanan operasyonel bir hatadır; NTP disiplini şarttır.
- **Ayrıcalıklı hesaplarla her yerde oturum açmak:** Domain Admin'in rastgele iş istasyonlarında oturum açması, o kimlik bilgisini Pass-the-Ticket için ortama saçar.
- **Delegation ayarlarının denetlenmemesi:** Unconstrained delegation'ın kimlerde açık olduğunu bilmeyen ortamlar, farkında olmadan büyük risk taşır.

## En İyi Pratikler

Savunmayı bütüncül bir çerçeveye oturtmak gerekirse:

- **Güçlü, yönetilen kimlik bilgileri:** Servis hesapları için gMSA kullanın; otomatik uzun ve rastgele parola ile Kerberoasting'i pratikte anlamsız kılar.
- **AES'i zorunlu, RC4'ü devre dışı bırakın:** Şifreleme türü politikalarını AES lehine sıkılaştırın.
- **krbtgt'yi düzenli döndürün:** Periyodik olarak ve şüphe anında, iki aşamalı olarak (Kerberos'un anahtar geçmişi davranışı nedeniyle) döndürün.
- **Tiered admin modeli:** Ayrıcalıklı hesapların hangi makinelerde oturum açabileceğini katmanlara ayırın; DC yönetim kimliklerini uç noktalara asla düşürmeyin.
- **Credential Guard ve Protected Users:** Bellekten kimlik bilgisi/bilet çalınmasını zorlaştıran mekanizmaları etkinleştirin.
- **Pre-authentication'ı zorunlu tutun:** İstisnasız.
- **Delegation'ı minimize edin ve denetleyin:** Unconstrained delegation'ı kaldırın; constrained/RBCD yapılandırmalarını en az yetki (least privilege) ilkesiyle sınırlayın.
- **Tespit ve izleme:** Anormal service ticket talep desenleri (tek kullanıcıdan çok sayıda SPN, RC4 talepleri), pre-auth gerektirmeyen AS-REP üretimi, olağandışı bilet ömürleri gibi telemetriyi SIEM'de izleyin. Kerberos olay kayıtları (event log) doğru toplandığında bu saldırıların çoğu erken yakalanabilir.
- **En az yetki ve saldırı yüzeyi azaltma:** SPN envanterinizi düzenli gözden geçirin, gereksiz SPN ve servis hesaplarını temizleyin.

## Kapanış

Kerberos'un zarafeti, parolayı ağda taşımadan güçlü kimlik doğrulama ve SSO sağlamasıdır; bu, simetrik kriptografinin ve güvenilen üçüncü taraf (KDC) modelinin akıllıca birleşiminden doğar. Ancak aynı tasarımın kritik varsayımları — krbtgt anahtarının gizliliği, servis hesabı parolalarının güçlü olması, biletlerin taşıyıcı (bearer) doğasına duyulan güven ve TGS'in yetkilendirmeyi servise devretmesi — istismar için birer kaldıraç oluşturur. Kerberos güvenliği, protokolü kırmaktan çok, bu varsayımları besleyen kimlik bilgilerini ve yapılandırmaları korumakla ilgilidir. Saldırıların neredeyse tamamı, kriptografinin kendisini yenmez; zayıf parola, döndürülmemiş anahtar veya gevşek delegation gibi insan ve operasyon katmanındaki boşlukları hedef alır. Dolayısıyla en güçlü savunma, güçlü kimlik hijyeni, en az yetik ilkesi ve sürekli izlemenin birleşimidir.
