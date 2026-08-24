# Entra ID (Azure AD) Hibrit Kimlik ve Senkronizasyon Saldırıları

## Giriş: Neden Bu Konu Kritik?

Kurumsal saldırı yüzeyi literatüründe Kerberos ve NTLM merkezli klasik on-prem Active Directory (AD) saldırıları (Kerberoasting, Pass-the-Hash, Golden/Silver Ticket, DCSync vb.) çok iyi belgelenmiştir. Ancak modern kurumların neredeyse tamamı artık **hibrit kimlik** modelindedir: on-prem AD hâlâ "kaynak of truth" (source of truth) konumundadır, fakat kullanıcı kimlikleri Entra ID'ye (eski adıyla Azure AD) senkronize edilerek Microsoft 365, Azure kaynakları ve binlerce SaaS uygulamasına SSO ile erişim sağlanır.

Bu köprüyü kuran bileşen **Microsoft Entra Connect** (eski adıyla Azure AD Connect, daha da eskisi DirSync/AAD Sync) yazılımıdır. Buradaki kritik güvenlik gerçeği şudur: **Entra Connect sunucusu, on-prem güvenliği ile bulut güvenliği arasındaki en zayıf halka olma potansiyeline sahip tek bir makinedir.** Bu sunucuyu veya onun kullandığı senkronizasyon hesabını ele geçiren bir saldırgan, sadece on-prem AD'yi değil, aynı zamanda bulut kiracısını (tenant) da tehlikeye atabilir — çünkü senkronizasyon hesabının Entra ID tarafında kullanıcı parolalarını sıfırlayabilecek ve rol atayabilecek ayrıcalıkları vardır.

Bu makale şu üç saldırı yüzeyini derinlemesine ele alır:
1. **Entra Connect senkronizasyon hesabı (MSOL/ADSync)** ele geçirilmesi
2. **Pass-Through Authentication (PTA) ajanı** manipülasyonu
3. **Seamless SSO** için kullanılan `AZUREADSSOACC$` bilgisayar hesabının Kerberos anahtarının çalınması

Ayrıca Federasyon (AD FS) tabanlı token imzalama saldırılarına da değinilecektir. Amaç, bu mekanizmaların **neden** bu kadar yüksek riskli olduğunu ve **nasıl** tespit edip savunulacağını anlamaktır.

---

## 1. Hibrit Kimlik Mimarisine Genel Bakış

Entra Connect üç ana kimlik doğrulama modelinden birini kullanır:

- **Password Hash Synchronization (PHS)**: On-prem AD'deki parola hash'lerinin (NTLM hash'i üzerinden türetilmiş bir değer) Entra ID'ye periyodik olarak senkronize edilmesi. Kullanıcı buluta giriş yaptığında doğrulama bulutta yapılır.
- **Pass-Through Authentication (PTA)**: Parola hash'i buluta hiç gönderilmez. Bunun yerine on-prem'de kurulu bir **PTA ajanı** aracılığıyla kimlik doğrulama isteği gerçek zamanlı olarak on-prem AD'ye yönlendirilir ve doğrulama orada yapılır.
- **Federasyon (AD FS)**: Kimlik doğrulama tamamen on-prem'deki bir Federasyon Sunucusuna (AD FS) devredilir; Entra ID sadece imzalı bir token'ı (SAML/WS-Fed) kabul eder.

Her üç modelde de **Entra Connect Sync** bileşeni, dizin nesnelerini (kullanıcı, grup, cihaz) on-prem'den buluta taşımaktan sorumludur ve bunun için özel bir hizmet hesabı kullanır.

### Kök Neden: Güven Sınırının Tek Noktaya Toplanması

Bu mimarinin temel güvenlik zafiyeti şudur: normalde on-prem AD ve bulut kiracısı ayrı güven alanlarıdır (trust boundary). Ancak Entra Connect sunucusu bu iki alanı **kasıtlı olarak** birbirine bağlayan bir köprü görevi görür. Bir sistemin "iki dünyanın da anahtarlarını taşıması", onu doğal olarak en yüksek değerli hedeflerden biri hâline getirir. Saldırgan literatüründe bu tür sistemlere "Tier 0" denir — yani ele geçirilmesi tüm ortamın (hem on-prem hem bulut) tam ele geçirilmesi anlamına gelen varlıklar.

---

## 2. Entra Connect Senkronizasyon Hesabının (MSOL/ADSync) Ele Geçirilmesi

### Tanım ve Çalışma Mantığı

Entra Connect kurulumu sırasında iki önemli hesap/kimlik oluşturulur:

1. **On-prem AD tarafında bir hizmet hesabı** — genellikle `MSOL_xxxxxxxx` adlandırma kalıbıyla oluşturulur (eski sürümlerde) veya Group Managed Service Account (gMSA) olarak yapılandırılır. Bu hesabın on-prem AD'de **DCSync hakları** (Replicating Directory Changes / Replicating Directory Changes All) dâhil olmak üzere geniş okuma izinleri vardır; çünkü senkronizasyon motorunun parola hash'lerini okuyup buluta göndermesi gerekir (PHS senaryosunda).
2. **Entra ID tarafında bir bulut hesabı** — bu hesap, dizin senkronizasyonu yazma işlemlerini gerçekleştirmek için Entra ID'de yükseltilmiş dizin rollerine sahiptir (klasik olarak "Directory Synchronization Accounts" rolü).

**Neden bu kadar tehlikeli?** Çünkü bu hesap, tanımı gereği, on-prem AD'nin en hassas verisine (parola hash'leri) erişebilen VE buluta yazma/senkronize etme yetkisi olan tek hesaptır. Ayrıca konfigürasyon verileri (bu hesabın kimlik bilgileri dâhil) **Entra Connect sunucusunun yerel SQL Server (LocalDB veya tam SQL) veritabanında** ve sunucu üzerindeki DPAPI ile korunan bir bellek alanında saklanır.

### Nasıl Çalışır (Kavramsal) ve Saldırı Yüzeyi

Entra Connect Sync motoru (`miiserver` / `Microsoft.Azure.ADSync` süreci), senkronizasyon hesabının kimlik bilgilerini kullanarak hem on-prem AD LDAP sorgularını hem de Entra ID'ye Graph/eski MSOL API çağrılarını yapar. Bu kimlik bilgileri sunucuda şifreli olarak tutulur, ancak **sunucu üzerinde yönetici (yerel Administrator) hakkına sahip biri**, çalışan sync motorunun kendisini kullanarak ya da veritabanına erişerek bu kimlik bilgilerini şifresini çözebilir.

Bunun kök nedeni, korumanın DPAPI'ye (Data Protection API) dayanmasıdır — DPAPI şifre çözme anahtarı makine bağlamına (machine key) bağlıdır. Yani "sunucuda kod çalıştırabilen yönetici" ile "şifreli kimlik bilgisini okuyabilen kişi" arasında güvenlik sınırı yoktur; ikisi aynı yetki seviyesidir. Bu, saldırı zincirinde şu adımı doğurur:

1. Saldırgan herhangi bir yolla (phishing, lateral movement, güvenlik açığı) Entra Connect sunucusunda yerel yönetici yetkisi elde eder.
2. Sunucudaki senkronizasyon veritabanına erişerek veya sync motorunun API'lerini (ör. PowerShell modülleri üzerinden) kullanarak MSOL/ADSync hesabının açık metin kimlik bilgilerini çıkarır.
3. Bu kimlik bilgileriyle iki yönde hareket edebilir:
   - **On-prem yönünde**: Hesabın DCSync haklarını kullanarak `krbtgt` dâhil tüm kullanıcıların parola hash'lerini dump eder → Golden Ticket üretimi mümkün hâle gelir.
   - **Bulut yönünde**: Hesabın Entra ID'deki senkronizasyon rolünü kullanarak dizindeki kullanıcı parolalarını (bazı senaryolarda) manipüle etmeye veya en azından dizin verisini okumaya çalışabilir.

Bu, saldırganın **on-prem'den buluta veya bulut hedefli bir ilk erişimden on-prem'e** yatay geçiş yapabileceği bir "iki yönlü köprü" oluşturur.

### Tespit

- **Entra Connect sunucusuna erişimi izleyin**: Bu sunucuya RDP/PowerShell Remoting girişlerini SIEM'de ayrı bir kritik varlık (crown jewel) olarak etiketleyin. Beklenmeyen bir kullanıcının bu sunucuya oturum açması başlı başına yüksek öncelikli bir uyarı olmalıdır.
- **DCSync tespiti**: Domain Controller olmayan bir hesabın (özellikle MSOL/ADSync hesabının normal davranış dışı sıklıkta) `Directory Replication Service (DRS) Remote Protocol` çağrıları yapması, Event ID 4662 (belirli GUID'lerle: `Replicating Directory Changes All`) üzerinden izlenebilir.
- **Sync veritabanı erişim denetimi**: `ADSync` veritabanına (LocalDB/SQL) dosya sistemi ve süreç düzeyinde erişim denetimlerini (audit) etkinleştirin; beklenmedik `sqlservr.exe` veya doğrudan MDF/LDF dosya erişimi anormal bir sinyaldir.
- **Entra ID tarafında**: "Directory Synchronization Accounts" rolüne sahip hesabın normalde göstermediği davranışları (ör. konsoldan interaktif oturum açma, MFA olmadan giriş denemesi, farklı coğrafi konumdan erişim) izleyin — bu hesaplar tasarım gereği yalnızca senkronizasyon sunucusundan, otomatik olarak kullanılmalıdır.

### Savunma

- **Entra Connect sunucusunu Tier 0 varlık olarak izole edin**: Ayrı bir yönetim katmanına (yönetim yıldızı / Enhanced Security Admin Environment mantığı) koyun; genel amaçlı sunucu yöneticilerinin erişimini kaldırın.
- **En az ayrıcalık**: Mümkün olan en yeni Entra Connect sürümünü kullanarak hesabı **gMSA (group Managed Service Account)** olarak yapılandırın — bu, parolanın periyodik olarak otomatik döndürülmesini ve elle çıkarılamamasını sağlar.
- **Staging mode ve yedek sunucu disiplini**: Aktif olmayan (staging) ikinci bir Entra Connect sunucusu varsa, onun da aynı sıkılıkla korunduğundan emin olun — genellikle unutulan ikincil sunucular daha zayıf yamalı olur.
- **Ağ segmentasyonu**: Sunucunun sadece gerekli AD ve Entra ID uç noktalarına giden trafiğe izin verilmesi (egress filtreleme), veri sızdırma ve komuta-kontrol (C2) risklerini azaltır.
- **PAM/Tiering modeli** uygulayın: Domain Admin hesapları bu sunucuya giriş yapmamalı; sunucuya özgü, kısıtlı bir yönetim hesabı seti kullanılmalı.

### Yaygın Hatalar

- Entra Connect sunucusunu "sıradan bir uygulama sunucusu" gibi görüp genel sunucu yama/izleme politikalarına bırakmak.
- Sync hesabını gMSA'ya taşımayı ihmal etmek (eski kurulumlarda hâlâ normal hizmet hesabı olarak kalabiliyor).
- Devre dışı/eski bir Entra Connect sunucusunu (staging veya terk edilmiş eski sürüm) ağda unutulmuş bırakmak.

---

## 3. Pass-Through Authentication (PTA) Ajanı Saldırıları

### Tanım

PTA modelinde parola hash'i buluta hiç gönderilmez. Bunun yerine, on-prem'de kurulu bir veya birden fazla **Authentication Agent** (kimlik doğrulama ajanı), Entra ID ile arasında kalıcı bir dış bağlantı (outbound, genellikle Service Bus tabanlı) kurar. Kullanıcı giriş yaptığında Entra ID, kimlik doğrulama isteğini bu ajanlardan birine iletir; ajan da parolayı on-prem AD'ye karşı doğrular ve sonucu (başarılı/başarısız) buluta geri bildirir.

### Kök Neden / Çalışma Mantığı

PTA ajanının güvenlik modeli şu varsayıma dayanır: **ajan yazılımının kendisi bütünlüğü bozulmamış (tampered olmayan) orijinal Microsoft ikili dosyasıdır ve sadece "evet/hayır" (parola doğru mu) kararını iletir.** Bu varsayım kırıldığında — yani saldırgan ajanın çalıştığı süreci veya kodunu manipüle edebildiğinde — çok ciddi bir sonuç doğar:

Ajan, kimlik doğrulama isteğini işlerken **kullanıcı adını ve düz metin parolayı** (TLS üzerinden şifreli iletişim çözüldükten sonra, bellek içinde) görür. Normal işleyişte ajan bu parolayı sadece on-prem AD'ye karşı doğrulamak için kullanır ve saklamaz. Ancak sunucuda yerel yönetici yetkisi olan bir saldırgan, ajan sürecine (DLL enjeksiyonu, ajan kodunun hooklanması gibi teknikler kavramsal olarak) müdahale ederek şunları yapabilir:

1. **Parola hasadı (harvesting)**: Her başarılı/başarısız giriş denemesinde kullanıcı adı + parolayı yakalayıp saldırgana sızdırma. Bu, bulut tarafında MFA olsa bile parolanın ele geçirilmesi anlamına gelir (parola tek başına yetmese de, kimlik bilgisi doldurma / diğer sistemlerde parola tekrar kullanımı riskleri doğar).
2. **Kimlik doğrulama sonucunu sahteleştirme (backdoor)**: Daha da kritik olanı, ajanın "bu kullanıcı adı/parola kombinasyonu geçerlidir" yanıtını **on-prem AD'ye hiç sormadan, keyfi olarak "başarılı" döndürmesini** sağlamak. Bu durumda saldırgan, on-prem AD'de var olan (hatta hiç var olmayan ama Entra ID'de var olan) herhangi bir kullanıcı için, **gerçek parolayı bilmeden** bulut oturum açma işlemini geçebilir — çünkü doğrulama kararını artık saldırganın manipüle ettiği ajan veriyordur.

Bu ikinci senaryo, PTA modelinin en tehlikeli teorik zafiyetidir: **kimlik doğrulamanın "karar noktası" (decision point) saldırganın kontrolündeki bir bileşene taşınmış olur.** Bu, güvenlik mühendisliğinde klasik bir "trusted computing base" ihlalidir — güvendiğiniz karar mekanizması artık güvenilir değildir.

### Tespit

- **Ajan bütünlüğü**: PTA ajanının çalıştığı sunuculardaki süreç bütünlüğünü (code signing doğrulaması, beklenmeyen DLL yüklemeleri) EDR/XDR çözümleriyle izleyin. Ajan sürecine enjekte edilen anormal modüller kritik bir uyarı olmalı.
- **Anomali analizi — başarı oranları**: Belirli bir ajan üzerinden gelen kimlik doğrulama isteklerinin başarı oranında ani, açıklanamayan artışlar (özellikle normalde başarısız olması beklenen brute-force/spray denemelerinin başarılı dönmesi) güçlü bir gösterge olabilir. Bunu tespit etmek için on-prem AD kimlik doğrulama logları (Event ID 4625/4624) ile Entra ID oturum açma logları **çapraz karşılaştırılmalı** — PTA ajanı üzerinden buluta "başarılı" dönen ama on-prem'de karşılık gelen bir başarılı kimlik doğrulama olayı olmayan durumlar şüphelidir.
- **Ajan sunucusu erişim denetimi**: PTA ajanının kurulu olduğu tüm sunucuları envanterleyin (birden fazla olabilir, yük dengeleme için) ve bu sunuculara erişimi Entra Connect sunucusuyla aynı Tier 0 hassasiyetinde izleyin.
- **Entra ID tarafında ajan durumu**: Beklenmeyen yeni bir PTA ajanının kiracıya kaydedilmesi (yeni bir sunucuya ajan kurulumu) mutlaka onaylı bir değişiklik yönetimi süreciyle eşleşmeli; eşleşmiyorsa olay.

### Savunma

- PTA ajanı çalıştıran tüm sunucuları Entra Connect sunucusuyla **aynı güvenlik katmanında** (Tier 0) tutun; genel sunucu yönetici havuzundan izole edin.
- Uygulama beyaz listeleme (application allowlisting) ve kod imzalama doğrulaması ile ajan sürecine yabancı kod enjeksiyonunu zorlaştırın.
- Birden fazla PTA ajanı kullanıyorsanız, hepsinin aynı sıkı güvenlik standardında olduğundan emin olun — saldırganlar genellikle en zayıf/ihmal edilmiş ikincil ajanı hedefler.
- Mümkünse ek katman olarak MFA'yı (Conditional Access ile) zorunlu kılın; bu, çalınan/tahmin edilen bir parolanın tek başına yeterli olmasını engeller (ajan sahteciliği senaryosunda MFA'nın kendisi de akış içinde manipüle edilebileceği unutulmamalı, ancak savunma derinliği önemlidir).

### Yaygın Hatalar

- PTA ajan sunucularının "sadece bir arka plan servisi" olduğu düşünülüp normal iş istasyonu/sunucu yama döngüsüne bırakılması.
- Birden fazla ajanın bazılarının test/geçici amaçlı kurulup unutulması, güvenlik gözetiminin dışında kalması.

---

## 4. Seamless SSO ve `AZUREADSSOACC$` Kerberos Anahtarı Hırsızlığı

### Tanım

**Azure AD Seamless Single Sign-On (Seamless SSO)**, kullanıcıların şirket ağındaki (on-prem, domain-joined) cihazlarından Entra ID'ye bağlı uygulamalara parola girmeden otomatik giriş yapmasını sağlayan bir özelliktir. Bu, hem PHS hem de PTA ile birlikte kullanılabilir.

Mekanizma şudur: Entra Connect kurulumu sırasında on-prem AD'de **`AZUREADSSOACC$`** adında özel bir bilgisayar hesabı (computer account) oluşturulur. Bu hesap, tarayıcının arka planda kullanıcı adına Entra ID'ye bir Kerberos servis bileti (service ticket) alıp sunmasını sağlayan "sanal" bir servis prensibidir. Kullanıcının tarayıcısı, kendi Kerberos TGT'sini kullanarak bu hesap için bir servis bileti talep eder ve bu bileti Entra ID'nin giriş uç noktasına (login.microsoftonline.com veya benzeri) sunar; Entra ID de bu bileti `AZUREADSSOACC$` hesabının paylaşılan sırrı (Kerberos anahtarı) ile doğrulayıp kullanıcıyı kimliklendirir.

### Kök Neden / Neden Bu Kadar Kritik?

Bu hesabın Kerberos anahtarı (NTLM hash'inden türetilmiş), **tüm kullanıcılar için ortak bir "paylaşılan sır"** görevi görür — yani her kullanıcının SSO doğrulaması aynı hesabın anahtarına dayanır. Bu, klasik Kerberos'taki "her servis prensibinin kendi anahtarı vardır, bu anahtar sadece ilgili servis ve KDC arasında bilinir" ilkesinin, burada "servis" aslında bulut tarafında bir doğrulama mekanizması olduğu için farklı bir güven modeline dönüşmesi anlamına gelir.

**Eğer bu hesabın Kerberos anahtarı (hash'i) çalınırsa**, saldırgan artık on-prem domain'e hiç bağlı olmadan, **herhangi bir kullanıcı için kendi başına sahte bir Kerberos servis bileti üretebilir** (klasik "Silver Ticket" mantığının bu özel hesaba uygulanmış hâli). Bu sahte bileti Entra ID'nin Seamless SSO uç noktasına sunarak, o kullanıcı adına **parola bilmeden, MFA'ya bile takılmadan** (çünkü Seamless SSO akışı genellikle "güvenilir ağdan geliyor" varsayımıyla ek doğrulama istemez) oturum açabilir.

Bunun kök nedeni yine aynı temayı tekrarlar: **domain'de yerel yönetici veya Domain Admin yetkisine sahip biri, `AZUREADSSOACC$` hesabının hash'ini DCSync veya benzeri bir teknikle çıkarabilir** — çünkü bu hesap da sonuçta AD içinde saklanan sıradan bir bilgisayar hesabı nesnesidir ve AD'nin normal replikasyon/okuma mekanizmalarına tabidir.

### Nasıl Çalışır (Kavramsal)

1. Saldırgan on-prem AD'de Domain Admin (veya DCSync hakkı olan) düzeyinde bir yetkiye ulaşır — bu, senaryonun ön koşuludur.
2. `AZUREADSSOACC$` hesabının parola hash'ini (Kerberos anahtarlarını) AD replikasyon protokolü üzerinden çıkarır.
3. Bu anahtarı kullanarak, hedef kullanıcı (ör. bir Global Admin) için sahte bir Kerberos servis bileti oluşturur — bilet içinde kullanıcının SID'i ve grup üyelikleri gibi alanlar saldırgan tarafından belirlenir.
4. Bu bileti Entra ID'nin Seamless SSO doğrulama akışına sunarak, hedef kullanıcı kimliğiyle bir oturum belirteci (token) elde eder.
5. Sonuç: **on-prem'de elde edilen yetki, buluta tamamen taşınmış olur** — genellikle hiçbir bulut tarafı MFA veya Conditional Access engeliyle karşılaşmadan, çünkü Seamless SSO akışı "zaten domain'e bağlı, güvenilir cihaz" varsayımıyla tasarlanmıştır.

Bu saldırı, literatürde bazen "Golden SAML"e benzetilse de mekanik olarak farklıdır (Golden SAML, AD FS token imzalama sertifikasının çalınmasıyla ilgilidir — bkz. Bölüm 5). Buradaki saldırı, Kerberos tabanlı bir hash/anahtar hırsızlığıdır ve doğrudan `AZUREADSSOACC$` hesabına özgüdür.

### Tespit

- **Hesap parola değişikliği izleme**: `AZUREADSSOACC$` hesabının parolası Microsoft'un önerdiği periyotta (belirli aralıklarla) döndürülmelidir; bu rotasyonun gerçekleştiğini doğrulayan bir izleme kurun. Rotasyon yapılmıyorsa, çalınmış bir hash süresiz olarak geçerli kalır.
- **Anormal kimlik doğrulama desenleri**: Seamless SSO üzerinden gelen oturum açma olaylarını Entra ID oturum açma günlüklerinde inceleyin; beklenmeyen cihazlardan, beklenmeyen IP aralıklarından (özellikle "kurumsal ağdan geliyor" iddiasında olup gerçek IP aralığı uyuşmayan) gelen SSO tabanlı oturum açmalar şüpheli.
- **DCSync/hassas hesap replikasyon izleme**: `AZUREADSSOACC$` dâhil olmak üzere Tier 0 hesapların replikasyon isteklerini (Event ID 4662 + ilgili GUID'ler) izleyin; bu hesap normalde sadece Entra Connect ile ilişkili süreçlerce okunmalı, farklı bir kaynaktan replikasyon isteği anomali sayılmalı.
- **Conditional Access sinyalleri**: Cihaz uyumluluğu (device compliance) ve konum tabanlı koşullu erişim politikalarının Seamless SSO oturumlarına da uygulandığından emin olun; bu, sahte biletle elde edilen oturumun ek bir katmanda yakalanma şansını artırır.

### Savunma

- **`AZUREADSSOACC$` parolasını düzenli olarak döndürün** (Microsoft'un resmi PowerShell modülü/komutlarıyla) — genellikle önerilen periyot birkaç ayda birdir; kesin süreyi kurumun kendi Microsoft dokümantasyonundan teyit etmesi gerekir.
- **Tier 0 hesap koruması**: Bu hesabı, diğer hassas hizmet hesapları gibi (krbtgt, Entra Connect sync hesabı) en yüksek koruma seviyesinde tutun; Domain Admin yetkisini olabildiğince az kişiye, Just-In-Time (JIT) erişimle verin.
- **Conditional Access ile derinlik ekleyin**: Sadece "domain'e bağlı görünme" sinyaline güvenmek yerine, cihaz uyumluluğu, oturum riski (Identity Protection risk sinyalleri) ve konum gibi ek sinyalleri zorunlu kılın; böylece tek bir sahte Kerberos bileti tüm koruma katmanlarını aşamaz.
- **En az ayrıcalıklı erişim modeli (Tiering)** ile DCSync haklarına sahip hesap sayısını minimumda tutun; bu hem `krbtgt` hem `AZUREADSSOACC$` gibi hesapların hash çıkarma riskini azaltır.

### Yaygın Hatalar

- `AZUREADSSOACC$` parolasının hiç döndürülmemesi (kurulumdan sonra "kur ve unut" yaklaşımı).
- Seamless SSO'nun tek başına yeterli bir güvenlik sınırı olduğu yanılgısı; oysa bu özellik kullanılabilirlik/kolaylık amaçlıdır, ek Conditional Access katmanları olmadan güçlü bir güvenlik kontrolü değildir.
- DCSync haklarının kimlerde olduğunun düzenli olarak denetlenmemesi (özellikle eski, artık ihtiyaç duyulmayan hizmet hesaplarında bu hakların unutulmuş kalması).

---

## 5. Federasyon (AD FS) ve Token İmzalama Saldırıları — Kısa Değinme

PHS ve PTA'ya alternatif olarak bazı kurumlar hâlâ **AD FS (Active Directory Federation Services)** kullanır. Bu modelde Entra ID, kimlik doğrulamayı hiç kendisi yapmaz; sadece AD FS sunucusunun imzaladığı bir token'ı (SAML veya WS-Federation) kabul eder.

**Kök neden**: Güven tamamen bir **token imzalama sertifikasına/anahtarına** dayanır. AD FS sunucusunda yönetici yetkisi elde eden bir saldırgan bu imzalama anahtarını çalabilirse, **kendi başına, herhangi bir kullanıcı (hatta Global Admin) için imzalanmış geçerli bir token üretebilir** — bu senaryo literatürde "Golden SAML" olarak bilinir. Bu, `AZUREADSSOACC$` saldırısına kavramsal olarak çok benzer ama katman farklıdır: biri Kerberos anahtarı, diğeri SAML/WS-Fed imzalama sertifikasıdır.

**Tespit ve savunma özeti**: AD FS sunucularını da Tier 0 olarak koruyun; token imzalama sertifikasının rotasyonunu izleyin; AD FS token'larının olağandışı iddialarla (claims) veya beklenmeyen kaynaklardan geldiğini Entra ID oturum açma günlüklerinde arayın. Mümkünse kurumların federasyondan PHS+Seamless SSO'ya geçmesi (Microsoft'un de genel önerisi), tek bir on-prem sertifikaya bağımlılığı azaltır — ancak bu geçiş kendi başına yeni riskler (yukarıda anlatılan PHS/Seamless SSO riskleri) getirir, risk sıfırlanmaz, sadece değişir.

---

## 6. Bütünsel Savunma Stratejisi ve Kapanış

Bu üç/dört saldırı yüzeyinin (senkron hesabı, PTA ajanı, Seamless SSO hesabı, federasyon sertifikası) ortak paydası **tek bir mimari gerçektir**: hibrit kimlikte, on-prem'de yönetici yetkisi kazanan bir saldırgan, doğru hedefi bulduğunda bulutu da ele geçirebilir. Bu nedenle savunma stratejisi şu ilkeler etrafında kurulmalıdır:

- **Tier 0 tanımını genişletin**: Sadece Domain Controller'lar değil, Entra Connect sunucusu, PTA ajan sunucuları, AD FS sunucuları ve bunların yedekleri de Tier 0'dır.
- **Hesap hijyeni**: MSOL/ADSync hesabı, `AZUREADSSOACC$`, AD FS hizmet hesapları gibi özel amaçlı hesapların ayrıcalıklarını düzenli denetleyin, parolalarını/anahtarlarını rotasyona sokun.
- **Çapraz-günlük korelasyonu**: On-prem AD güvenlik günlükleri ile Entra ID oturum açma/denetim günlüklerini tek bir SIEM'de birleştirip korelasyon kurmadan bu saldırıların çoğu tespit edilemez — çünkü saldırının "on-prem ayağı" ile "bulut ayağı" ayrı sistemlerde görünür.
- **Varsayılan güveni azaltın**: Seamless SSO ve federasyon gibi "kolaylık" özellikleri, ek Conditional Access katmanlarıyla (cihaz uyumluluğu, risk tabanlı erişim, MFA) desteklenmeden tek başına güvenlik sınırı olarak görülmemelidir.
- **En az ayrıcalık ve JIT erişim**: DCSync ve replikasyon haklarına sahip hesap sayısını minimumda tutmak, bu saldırı zincirinin ilk adımını (hash/anahtar çıkarma) zorlaştırır.

Sonuç olarak, hibrit kimlik ortamında güvenlik, artık "on-prem AD güvenliği" ve "bulut güvenliği" olarak ayrı ayrı düşünülemez; ikisi tek bir sürekli güven zinciridir ve zincirin en zayıf halkası (çoğu zaman gözden kaçan Entra Connect/PTA/SSO bileşenleri) tüm zincirin dayanıklılığını belirler.
