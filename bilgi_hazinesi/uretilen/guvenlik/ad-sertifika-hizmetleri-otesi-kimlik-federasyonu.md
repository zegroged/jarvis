# AD Sertifika Hizmetleri Ötesi Kimlik Federasyonu: PKINIT ve Smart Card / Sertifika Tabanlı Kimlik Doğrulama Zayıflıkları

## Giriş ve Kapsam

Active Directory Certificate Services (ADCS) saldırıları genellikle **ESC1-ESC8** gibi şablon (template) kötüye kullanımı listeleri üzerinden anlatılır. Ancak bu listelerin çoğu, "yanlış yapılandırılmış bir şablondan sahte sertifika nasıl alınır" sorusuna odaklanır. Bu makale bir kademe daha derine iner: **sertifikanın Kerberos kimlik doğrulamasına nasıl bağlandığı** — yani **PKINIT** (Public Key Cryptography for Initial Authentication in Kerberos) protokolünün kendisi, akıllı kart (smart card) tabanlı oturum açma mantığı ve bu protokol seviyesindeki tasarım/uygulama zayıflıkları.

Neden ayrı bir derinlik gerektiriyor? Çünkü ESC1 gibi bir bulgu "kötüye kullanılabilir bir sertifika aldım" der; asıl güç ise o sertifikanın **PKINIT üzerinden bir TGT'ye (Ticket Granting Ticket) ve dolayısıyla NTLM hash'ine kadar** dönüşebilmesinde yatar. Sertifika ile Kerberos arasındaki bu köprüyü anlamadan, ne saldırıyı ne de savunmayı tam kavrayabilirsiniz.

Bu metin **kavramsal ve savunma amaçlıdır**. Amaç mekanizmayı anlamak, tespit (detection) ve savunma (hardening) kurmaktır; operasyonel saldırı reçetesi değildir.

## PKINIT Nedir ve Neden Var?

### Klasik Kerberos'un Ön-Kimlik Doğrulaması

Standart Kerberos'ta bir kullanıcı, Key Distribution Center'a (KDC) `AS-REQ` (Authentication Service Request) gönderdiğinde, kimliğini **parolasından türetilen simetrik anahtarla** kanıtlar. Bu mekanizmaya **pre-authentication** (ön-kimlik doğrulama) denir: istemci, güncel zaman damgasını (timestamp) kullanıcının anahtarıyla şifreler (`PA-ENC-TIMESTAMP`), KDC bunu çözebiliyorsa parolayı bilen kişi olduğunuza kanaat getirir. Yani güven kökü **paylaşılan gizli (shared secret)**, yani paroladır.

### PKINIT'in Getirdiği Değişiklik

PKINIT, bu simetrik güven kökünün yerine **asimetrik kriptografiyi (public key)** koyar. Kullanıcı artık bir parola yerine, **X.509 sertifikası ve buna karşılık gelen özel anahtar (private key)** ile kimliğini kanıtlar. Akıllı kart oturum açma (smart card logon) tam olarak budur: özel anahtar akıllı kartın güvenli çipinde durur, PIN ile kilidi açılır ve ön-kimlik doğrulama bu anahtarla imzalanır.

PKINIT'in iki temel modu vardır:

- **Public key (imza) modu:** İstemci `AS-REQ` içindeki ön-kimlik doğrulama verisini özel anahtarıyla imzalar. KDC, sertifikayı doğrular, güvenilir bir zincire (trust chain) bağlıysa kabul eder.
- **Diffie-Hellman modu:** Oturum anahtarı (session key) üretimi için anonim/ephemeral DH anahtar değişimi kullanılır. Bu, "unauthenticated DH" olarak bilinen ve tarihsel olarak bazı zayıflıklara (ör. Diffie-Hellman parametre doğrulama sorunları) konu olan alandır.

### Kritik Nokta: Sertifikadan Kimliğe Eşleme (Certificate Mapping)

PKINIT'in güvenliğinin kalbi şu sorudadır: **"Bu sertifika hangi AD kimliğine (account) karşılık gelir?"** KDC, sertifikayı doğruladıktan sonra onu bir kullanıcı veya bilgisayar hesabına eşlemek zorundadır. İşte tüm sınıfın zayıflıkları büyük ölçüde bu **eşleme (mapping)** adımında ortaya çıkar.

Geleneksel olarak iki eşleme yolu vardır:

1. **Implicit (örtük) mapping:** Sertifikanın **SAN (Subject Alternative Name)** alanındaki `otherName` içinde yer alan **UPN (User Principal Name)** kullanılır. KDC, "bu UPN'e sahip hesabı bul" mantığıyla eşleme yapar. ESC1 sınıfı saldırıların özü tam buradadır: saldırgan, SAN'a **başka bir kullanıcının UPN'ini** (ör. `administrator@domain`) yazabildiği bir şablon bulursa, KDC o sertifikayı domain admin hesabına eşler.
2. **Explicit (açık) mapping:** Hesabın `altSecurityIdentities` özniteliğine sertifikanın belirli bir kimliği (issuer + serial, subject key identifier, SHA1 hash vb.) yazılır. KDC yalnızca bu tanıma uyan sertifikayı kabul eder.

## Kök Neden: Zayıf Eşleme ve Güven Modeli

Bu alandaki zayıflıkların ortak kök nedeni tek bir cümlede özetlenebilir: **Sertifikayı üreten otorite (CA) ile o sertifikayı bir kimliğe çeviren KDC arasındaki güven, aşırı geniş ve zayıf doğrulanmış bir eşlemeye dayanıyordu.**

Bunu birkaç başlıkta açalım.

### 1. UPN Tabanlı Örtük Eşlemenin Kırılganlığı

UPN, güvenlik tasarımı açısından "zayıf" bir tanımlayıcıdır çünkü **değişebilir ve tekil garanti taşımaz**. Bir kullanıcının UPN'i değişebilir; SAN'a keyfi UPN yazma imkânı veren bir şablon, kimlik taklidine (impersonation) doğrudan kapı açar. Sertifika kriptografik olarak "geçerli" olsa bile, içindeki kimlik iddiası (identity claim) yeterince sıkı doğrulanmaz.

### 2. Certifried Sınıfı: SID Doğrulamasının Eksikliği (CVE-2022-26923 bağlamı)

Tarihsel olarak önemli bir dönüm noktası, sertifika içinde **SID (Security Identifier)** doğrulamasının zorunlu olmamasıydı. **Certifried** olarak bilinen zafiyet sınıfında (Microsoft bunu 2022 yılında bir güncelleme ile ele almıştır — kavramsal referans olarak CVE-2022-26923), sorun şuydu: bir makine hesabının `dNSHostName` özniteliği ile oynanarak, düşük yetkili bir hesabın **domain controller taklidi** yapacak bir sertifika alması mümkündü. KDC, sertifikadaki kimliği yeterince katı doğrulamadığı için bu eşleme başarılı oluyordu.

Microsoft'un çözümü **iki taraflı** oldu:
- CA tarafında, sertifikaya bir uzantı (extension) ile **hesabın SID'ini gömme** (`szOID_NTDS_CA_SECURITY_EXT` olarak bilinen OID üzerinden).
- KDC tarafında, PKINIT sırasında sertifikadaki SID ile eşlenen hesabın SID'inin **uyuşmasını zorunlu kılma**.

Bu, örtük eşlemeye kriptografik olarak taşınan **güçlü bir tanımlayıcı** (SID) eklemek anlamına gelir. UPN taklit edilebilir ama SID, kaynak ormanda (forest) benzersizdir.

### 3. Güçlü Sertifika Eşleme (Strong Certificate Mapping) Zorlaması

Microsoft, bu düzeltmeyi kademeli olarak zorunlu hâle getirmek için bir uyumluluk süreci tanımladı (yaygın olarak **KB5014754** ile ilişkilendirilir). Sistem üç mantıksal aşamadan geçer:

- **Compatibility (uyumluluk) modu:** Zayıf eşleme hâlâ kabul edilir ama günlüklere (event log) uyarı yazılır.
- **Audit modu:** Zayıf eşlemeler denetlenir, olası kırılmalar loglarda görünür.
- **Full enforcement (tam zorlama) modu:** Zayıf eşleme **reddedilir**; yalnızca güçlü eşleme (strong mapping) kabul edilir.

Burada **güçlü** ile **zayıf** eşleme ayrımı hayatidir:

- **Zayıf (weak) mapping:** Yalnızca UPN veya sertifika Subject/Issuer isim eşleşmesi gibi taklit edilebilir alanlara dayanır.
- **Güçlü (strong) mapping:** SID uzantısı, sertifika seri numarası + issuer, subject key identifier veya SHA1 public key hash gibi **kriptografik/benzersiz** bağlara dayanır.

Bu geçiş sürecinin bir gerçek dünya yan etkisi vardır: yalnızca UPN'e dayanan meşru dağıtımlar (ör. üçüncü taraf CA'lar, eski akıllı kart altyapıları) tam zorlama moduna geçince **kimlik doğrulama kesintisi** yaşayabilir. Bu nedenle birçok ortam hâlâ compatibility/audit modunda takılıp kalmıştır — ve tam da bu durum saldırı yüzeyini açık tutar.

## Örnek Senaryo (Kavramsal)

Aşağıdaki akış, mekanizmayı anlamak için **kavramsal** olarak verilmiştir; adım adım saldırı komutları değildir.

1. **Zayıf sertifika elde etme:** Bir ortamda, kimliği doğrulanmış herhangi bir kullanıcının SAN alanına keyfi UPN yazabildiği bir sertifika şablonu (enrollment template) yanlış yapılandırılmıştır. Saldırgan, SAN'ında `administrator@kurum.local` yazan, kriptografik olarak geçerli bir sertifika elde eder.
2. **PKINIT ile TGT talebi:** Saldırgan, bu sertifikayı kullanarak KDC'ye PKINIT tabanlı `AS-REQ` gönderir. KDC sertifikayı doğrular; SID doğrulaması **zorlanmıyorsa**, SAN'daki UPN üzerinden `administrator` hesabına örtük eşleme yapar ve bir TGT verir.
3. **Kimlik yükselmesi:** Artık saldırgan, `administrator` bağlamında geçerli bir Kerberos bileti taşır.
4. **NTLM'e köprü (UnPAC-the-hash):** PKINIT'in az bilinen bir özelliği, KDC'nin döndürdüğü ayrıcalık sertifikası (PAC — Privilege Attribute Certificate) içinde, ilerideki NTLM tabanlı kimlik doğrulamaları için kullanıcının **NTLM anahtarını (hash) şifreli biçimde** taşıyabilmesidir. Bu, akıllı kart kullanıcılarının parolasız da NTLM gerektiren eski servislere bağlanabilmesi için tasarlanmıştır. Saldırı bağlamında ise, geçerli bir PKINIT TGT'sinden hedef hesabın NTLM hash'inin elde edilebilmesi demektir — buna literatürde **UnPAC-the-hash** denir. Yani bir sertifika, sonunda bir parola-eşdeğeri sırra dönüşür.

Bu zincir, "ADCS bir sertifika verdi" ile "domain admin NTLM hash'ine sahibim" arasındaki mesafenin aslında **protokol seviyesinde** ne kadar kısa olduğunu gösterir.

## Diğer Federasyon Kenarları

Bu konu yalnızca klasik akıllı kart senaryosuyla sınırlı değildir. Kurumsal ortamlarda birkaç "kenar" (edge) daha vardır:

- **Certificate-based authentication (CBA) ve bulut federasyonu:** Entra ID (eski Azure AD) gibi bulut kimlik sistemleri de sertifika tabanlı kimlik doğrulamayı destekler ve burada da **eşleme (username binding)** doğru yapılmazsa benzer taklit riskleri doğar. Zayıf bir binding (ör. yalnızca Principal Name veya RFC822 name üzerinden) ile güçlü bir binding (SKI, SHA1-PUKEY, issuer+serial) ayrımı bulutta da geçerlidir.
- **Shadow Credentials / Key Trust:** AD hesaplarının `msDS-KeyCredentialLink` özniteliği, bir hesaba **alternatif public key** (Key Trust) eklenmesine izin verir; bu, PKINIT'in NGC (Next Generation Credentials) yolunun temelidir. Bu özniteliğe yazma yetkisi olan bir saldırgan, hedef hesap için kendi anahtar çiftini ekleyerek PKINIT ile o hesap olarak kimlik doğrulayabilir. Bu, sertifika CA'sını hiç kullanmadan aynı PKINIT sonucuna ulaşmanın alternatif bir yoludur ve savunma açısından ADCS'den bağımsız izlenmelidir.
- **Cross-forest / federasyon güveni:** Sertifika güven zincirleri ormanlar arası genişletildiğinde, bir ormandaki zayıf CA konfigürasyonu diğer ormanı da etkileyebilir. NTAuth deposu (`NTAuthCertificates`) ve enterprise trust store'un ne içerdiği burada belirleyicidir.

## Tespit (Detection)

Bu sınıf saldırılar, doğru loglama açıksa **oldukça görünürdür**. Odaklanılması gereken alanlar:

### KDC / Domain Controller Olayları

- **Event ID 4768** (Kerberos TGT talep edildi): PKINIT ile alınan TGT'ler burada görünür. **Certificate Information** alanları (issuer name, serial number, thumbprint) dolu olan 4768 olayları, sertifika tabanlı kimlik doğrulamayı işaret eder. Beklenmedik hesaplar (ör. normalde akıllı kart kullanmayan bir servis hesabı) için PKINIT tabanlı TGT görmek güçlü bir sinyaldir.
- **Event ID 4771** (ön-kimlik doğrulama başarısız): Anomalilerin izlenmesi.
- **Güçlü/zayıf eşleme olayları:** KB5014754 ile ilişkili düzeltmeler, zayıf eşleme kullanıldığında DC üzerinde belirli uyarı olayları üretir (ör. **Event ID 39 / 40 / 41** aralığında Kerberos-Key-Distribution-Center kaynağından olaylar). Bu olayların varlığı, ortamda hâlâ zayıf eşlemeye bağımlı kimlik doğrulama olduğunu gösterir — hem bir savunma boşluğu hem de olası kötüye kullanım göstergesidir. (Not: Kesin event ID numaraları ortama ve güncelleme seviyesine göre değişebilir; ilkeyi izleyin, numarayı kendi ortamınızda doğrulayın.)

### CA (Certification Authority) Olayları

- **Event ID 4886 / 4887** (sertifika talebi alındı / verildi): Kim, hangi şablondan, hangi SAN ile sertifika aldı? SAN'ında bir hesabın kendisinden farklı bir UPN taşıyan talepler yüksek şüphe taşır.
- Kısa süre içinde **anormal enrollment** desenleri (bir hesabın normalde talep etmediği şablonlardan sertifika alması).

### Korelasyon Mantığı

En güçlü tespit, tekil olaylardan değil **korelasyondan** gelir: "Aynı sertifika seri numarası, CA loglarında X kullanıcısına verildi ama DC loglarında Y (ör. administrator) TGT'sinde göründü" örüntüsü, kimlik taklidinin neredeyse kesin işaretidir. SIEM tarafında serial number / thumbprint alanını CA ve KDC logları arasında eşleştirmek altın kuraldır.

### Shadow Credentials Tespiti

`msDS-KeyCredentialLink` özniteliğindeki değişiklikleri izleyin. Bu öznitelik üzerinde beklenmedik yazma işlemleri (özellikle ayrıcalıklı hesaplarda) Key Trust tabanlı kötüye kullanımın erken göstergesidir. AD denetim (auditing) politikasında öznitelik değişikliği loglaması açık olmalıdır.

## Savunma (Hardening)

Savunmayı katmanlı düşünün.

### 1. Güçlü Eşlemeye Geçiş

En temel önlem, **strong certificate mapping**'i tam zorlama (full enforcement) moduna almaktır. Bu, SID uzantısı olmayan veya yalnızca UPN'e dayanan sertifikaların PKINIT ile kabul edilmesini engeller. Geçiş öncesinde:

- Audit modunda logları izleyerek **hangi meşru sistemlerin zayıf eşlemeye bağımlı** olduğunu tespit edin.
- Üçüncü taraf CA'lar ve akıllı kart altyapıları için `altSecurityIdentities` üzerinden **açık ve güçlü** eşlemeler tanımlayın (issuer+serial veya SKI gibi). Zayıf `altSecurityIdentities` biçimlerinden (yalnızca subject veya yalnızca issuer) kaçının.

### 2. Sertifika Şablonlarını Sıkılaştırma

Kök neden çoğu zaman kötü şablondur:

- İstemcinin SAN'a keyfi değer yazmasına izin veren bayrağı (`CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT`) yalnızca kesinlikle gerekliyse ve sıkı yetkilendirmeyle kullanın.
- **Manager approval** (yönetici onayı) ve yetkili imza (authorized signature) gereksinimlerini hassas şablonlarda etkinleştirin.
- Enrollment yetkilerini (enroll / autoenroll) yalnızca gereken gruplara verin; `Authenticated Users` gibi geniş gruplara enrollment vermeyin.

### 3. NTAuth ve Güven Deposu Hijyeni

- `NTAuthCertificates` deposunda **yalnızca gerçekten güvenilmesi gereken CA'lar** bulunsun. Bu depodaki her CA, PKINIT için kimlik üretebilir; gereksiz veya eski CA'ları çıkarın.
- Ormanlar arası güven senaryolarında hangi CA'ların diğer ormana kimlik üretebildiğini denetleyin.

### 4. Ayrıcalıklı Hesap Koruması

- Ayrıcalıklı hesaplar için **"smart card required for interactive logon"** gibi kontrolleri bilinçli yönetin; bu bayrağın açılıp kapanmasının parola/hash yenilenmesiyle ilişkisini gözden geçirin.
- Tier 0 varlıklarının (DC, ADCS, PKI) yönetimini ayrı, izole yönetim düzleminde tutun. ADCS sunucusu bir Tier 0 varlığıdır ve öyle korunmalıdır.

### 5. Shadow Credentials / Key Trust Kısıtlama

- `msDS-KeyCredentialLink` üzerinde yazma yetkisini yalnızca gereken servislere (ör. Windows Hello for Business, cihaz kaydı) bırakın. Hassas hesaplarda bu öznitelik üzerindeki geniş yazma ACL'lerini denetleyin.

## Yaygın Hatalar

- **"ESC1'i kapattık, iş bitti" yanılgısı.** Şablon düzeltmek gereklidir ama yeterli değildir. Zayıf eşleme tam zorlamaya alınmadıkça, henüz keşfedilmemiş başka bir zayıf şablon veya Key Trust yolu aynı sonucu doğurur. Savunma **protokol seviyesinde** (strong mapping) de kurulmalıdır.
- **Compatibility modunda kalıcı kalmak.** Birçok ortam, kimlik doğrulama kesintisi korkusuyla audit/compatibility modunda süresiz kalır. Bu, düzeltmenin faydasını nötralize eder. Doğru yaklaşım: audit loglarıyla bağımlılıkları çözmek ve tam zorlamaya **planlı geçmek**.
- **Sadece ADCS loglarına bakmak.** Certifried veya Shadow Credentials, CA'yı hiç kullanmayabilir. Yalnızca CA enrollment loglarını izlemek, Key Trust tabanlı PKINIT kötüye kullanımını tümüyle kaçırmanıza yol açar. KDC (4768) ve öznitelik değişikliği logları da izlenmelidir.
- **PKINIT'i "sadece akıllı kart" sanmak.** PKINIT, akıllı kart olmadan (yazılım sertifikası veya Key Trust anahtarıyla) da çalışır. Fiziksel kart yoksa bile bu saldırı yüzeyi vardır.
- **UnPAC-the-hash'i göz ardı etmek.** Bir sertifikanın nihayetinde bir NTLM hash'ine dönüşebilmesi, "sertifika = düşük risk" varsayımını çürütür. Sertifika tabanlı kimlik, parola tabanlı kimlik kadar hassas korunmalıdır.
- **NTAuth deposunu unutmak.** Ortamlar CA şablonlarını sıkılaştırır ama `NTAuthCertificates` içinde gereksiz/eski/az güvenilen bir CA bırakır. O CA'dan üretilen herhangi bir sertifika PKINIT için geçerli kimlik üretebilir — tek bir zayıf CA tüm ormanı riske atar.

## Özet

PKINIT, Kerberos'un güven kökünü paroladan asimetrik anahtara taşıyan güçlü bir protokoldür; akıllı kart oturum açmanın ve modern parolasız kimliğin temelidir. Ancak gücü, aynı zamanda risk yüzeyidir: **sertifikadan kimliğe eşleme** adımı tarihsel olarak zayıftı, UPN gibi taklit edilebilir alanlara dayanıyordu ve SID doğrulaması zorunlu değildi. Certifried sınıfı zafiyetler ve Shadow Credentials gibi Key Trust yolları, bir sertifikanın (hatta yalnızca bir public key'in) domain admin bağlamına ve UnPAC-the-hash yoluyla NTLM hash'ine kadar nasıl köprülenebileceğini gösterdi.

Savunmanın özü tek cümlede: **güçlü, kriptografik olarak benzersiz eşlemeyi (SID uzantısı, strong mapping) tam zorlamaya almak; şablon ve NTAuth hijyenini sürdürmek; ve tespiti CA ile KDC logları arasında serial/thumbprint korelasyonuyla kurmak.** Bu üçlü olmadan, ADCS şablonlarını kapatmak yalnızca yüzeydeki bir bulguyu örtmüş olur; protokol seviyesindeki gerçek risk açık kalır.
