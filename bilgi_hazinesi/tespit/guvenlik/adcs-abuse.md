# AD Certificate Services (ADCS) Abuse — Tespiti

> Saha notu: ADCS istismarı, Active Directory'nin en sinsi kalıcılık ve
> ayrıcalık yükseltme vektörlerinden biri. Sinsiliğinin sebebi teknik değil,
> *operasyonel*: sertifika altyapısı çoğu kurumda "kurulduktan sonra
> unutulan" bir bileşen, PKI ekibiyle SOC ekibi neredeyse hiç konuşmuyor ve
> sertifika tabanlı kimlik doğrulama zaten *meşru* olduğu için gürültüden
> ayırmak zor. Bu metin, "4768'e bakın" seviyesinin ötesinde, sinyalleri
> nasıl bağladığını ve tespitin gerçek ortamda neden çöktüğünü anlatır.

---

## 1. Özet: saldırı + naif tespit

ADCS (Active Directory Certificate Services), bir Windows ortamında
sertifika basan Kurumsal CA (Enterprise CA) rolüdür. Saldırı yüzeyinin özü
şu: bir sertifika, sahibinin *kim olduğunu* kanıtlayan bir kimlik belgesidir
ve PKINIT üzerinden Kerberos'a doğrudan kimlik doğrulaması yapmakta
kullanılabilir. Yani saldırgan, bir kullanıcının parolasını hiç görmeden, o
kullanıcı (veya Domain Admin, veya bir Domain Controller makine hesabı) adına
bir sertifika elde edebilirse, o kimliğe *kalıcı* olarak bürünebilir. Parola
değişikliği bu sertifikayı iptal etmez; sertifika kendi ömrü (çoğu şablonda 1
yıl, kötü yapılandırmalarda 5-10 yıl) boyunca geçerli kalır. SpecterOps'un
"Certified Pre-Owned" araştırması bu sınıfı ESC1'den ESC16'ya kadar
numaralandırdı: şablon yanlış yapılandırmaları (ESC1 — enrollee supplies
subject + client auth EKU), yanlış CA ACL'leri (ESC7), NTLM relay ile web
enrollment (ESC8), sertifika eşleme zayıflıkları (ESC9/ESC10) ve daha
fazlası.

Naif tespit herkesin bildiği yerden başlar: CA üzerinde **Event ID 4886**
(certificate request received) ve **4887** (certificate issued) loglanır;
sertifika ile kimlik doğrulanınca DC'de **Event ID 4768** (Kerberos TGT
istendi) üretilir ve PKINIT kullanıldığında bu 4768'de sertifika bilgisi
(Certificate Issuer/Serial/Thumbprint alanları) dolar. Araç tarafında ise
zincirin başındaki elde edilebilir imzalar var: `Certify.exe` ve
`Certipy.exe` çalıştırma tespiti (Sigma: *HackTool - Certify Execution*,
*HackTool - Certipy Execution*), `ADCSPwn` komut satırı (`--adcs --port`), ve
antivirüsün `PWS`/`Certify` imzalı alarmları.

Bu kadarı "bir şey oldu" der. Sorun, gerçek ortamda bu "bir şey"in ya hiç
loglanmaması, ya da günde binlerce meşru olayın içinde kaybolmasıdır. Değer,
buradan sonrası.

---

## 2. Naif tespit neden yetmez

**Birincisi, araç imzaları tek atımlık ve kırılgan.** `Certify.exe` /
`Certipy.exe` tespiti (yukarıdaki iki Sigma kuralı) `Image|endswith`,
`OriginalFileName` ve `Description|contains: 'Certify'` üzerine kuruludur.
Bunların *hepsi* saldırganın kontrolündeki metadata. Certify'ı derleyip yeniden
adlandırmak, OriginalFileName'i strip etmek, ya da doğrudan Certipy'nin Python
kaynağını çalıştırmak (`python certipy.py` — bu durumda Image `python.exe`
olur, `Certipy.exe` değil) kuralı tamamen kör eder. Certipy zaten Python; ondan
tek başına bir `.exe` beklemek yanlış varsayım. Dahası bu araçlar giderek
BOF (Beacon Object File) ve in-memory .NET olarak, `Certify.exe` diske hiç
düşmeden Cobalt Strike / Havoc içinde çalıştırılıyor — o zaman `process_creation`
tabanlı hiçbir imza ateşlemez.

**İkincisi, `/vulnerable` bulmak saldırı değil.** *HackTool - Certify
Execution* kuralındaki `selection_cli_options` içinde `/vulnerable`,
`/template:`, `/altname:` var. Ama `certify.exe find /vulnerable` sadece
*keşif*tir — ortamı tarayan bir pentester veya bir kırmızı takım da aynısını
yapar. Bunu tek başına "high" seviye alarmla eşlemek, güvenlik ekibinin kendi
tarama araçlarıyla (PingCastle, BloodHound/SharpHound, Locksmith,
`Invoke-ADCSToolkit`) sürekli false positive üretir. Asıl tehlikeli olan
`/altname:` ile *başkasının* SAN'ını (Subject Alternative Name) enjekte
ederek sertifika *isteme* (ESC1) anıdır, ama naif kural bunu keşiften ayırmaz.

**Üçüncüsü ve en önemlisi: CA loglaması varsayılan olarak yeterli değil.**
Event 4886/4887'nin *değeri* isteyenin kimliği (Requester) ile sertifikanın
*konusu/SAN'ı* arasındaki uyuşmazlığı görebilmektir. Ama 4887 varsayılan
olarak SAN alanını taşımaz; SAN'ı loga düşürmek için CA üzerinde ayrı bir
audit yapılandırması (`certutil -setreg CA\AuditFilter 127` + "Issue and
manage certificate requests" başarı denetimi) *ve* SAN'ın olay içinde
görünmesi için ek yapılandırma gerekir. Yani en kritik tespit sinyali —
"Requester = dusun.kullanici ama SAN = Administrator" — pek çok kurumda
*hiç loglanmıyor*. Kör nokta burada başlar.

**Dördüncüsü, ESC8 (NTLM relay) CA'nın process/komut satırı katmanında hiç
görünmez.** ESC8'de saldırgan bir makine hesabını (örn. `PetitPotam`,
`Coercer` ile) CA'nın web enrollment endpoint'ine (`/certsrv/certfnsh.asp`)
kimlik doğrulamaya zorlar ve bu NTLM'i relay eder. CA'nın gördüğü şey mükemmel
*meşru* bir HTTP isteğidir. Endpoint'e ait IIS logu ya da 4886/4887 dışında
process_creation kuralları burada tamamen sağırdır.

---

## 3. Korelasyon zinciri (asıl değer)

ADCS istismarı tek sinyalde asla yüksek güven vermez. Yüksek güven, **farklı
katmanlardaki olayları zaman ve kimlik ekseninde bağlamaktan** doğar.
Somutlaştıralım.

### Zincir A — ESC1 (SAN enjeksiyonu ile kimliğe bürünme)

Klasik ESC1'in tam yaşam döngüsü şu olaylardan geçer:

1. **Keşif** — `certify.exe find /vulnerable` veya `certipy find
   -vulnerable`. Sinyal: araç imzası *veya* CA'ya kısa sürede gelen çok
   sayıda template okuma (LDAP `pKICertificateTemplate` nesnelerine seri
   erişim). Zayıf sinyal.
2. **İstek** — Düşük yetkili bir kullanıcı, kendi yetkisinde olmayan bir
   kimliğin SAN'ı ile sertifika ister. CA'da **4886 + 4887**. Kritik alan:
   *Requester ≠ SAN*. Örn. Requester `CORP\ayilmaz`, ama basılan
   sertifikanın SAN'ı `administrator@corp.local`.
3. **Kimlik doğrulama** — Elde edilen `.pfx` ile PKINIT: DC'de **4768**,
   `Certificate Information` alanı dolu, ve **PreAuthType = 16** (PKINIT).
   Talep edilen kullanıcı artık `Administrator`.
4. **Kullanım** — Aynı Administrator TGT'si ile kısa sürede uzak host'a
   erişim: **4624 Logon Type 3**, ardından yanal hareket (SMB/WMI/PsExec).

Tek başına 4887 gürültüdür (günde binlerce meşru sertifika). Tek başına 4768
gürültüdür. Ama **korelasyon kuralı** şudur:

> *4887'de Requester_UPN ile SubjectAltName_UPN farklı*  **VE** *aynı
> SubjectAltName_UPN 4768'de (PKINIT) 15 dakika içinde TGT alıyor* **VE** *o
> UPN yüksek ayrıcalıklı (Domain Admins / Enterprise Admins / DC makine
> hesabı)* = **kritik ihlal**, false positive'i neredeyse sıfır.

Bu bağı Google tek sayfada vermez, çünkü iki farklı log kaynağını (CA +
DC) *alan eşlemesiyle* birleştirmeyi gerektirir — Requester ile SAN aynı
olay içinde değil, SAN çoğu zaman ham istekte, Requester 4886'da.

### Zincir B — ESC8 (relay) + ESC6/ESC1 birleşimi

ESC8'de zincir tamamen farklı katmandan gelir:

1. **Coercion** — DC'ye veya bir sunucuya `PetitPotam`/`PrinterBug`. Sinyal:
   `EFSRPC` / `MS-RPRN` çağrıları, ya da kaynak makineden CA dışı bir hosta
   `4624 Logon Type 3` + makine hesabıyla (`DC01$`) anomali oturum.
2. **Relay** — Saldırgan hostu, coerce edilen makine hesabını CA web
   enrollment'a relay eder. Sinyal: CA'nın IIS logunda `/certsrv/certfnsh.asp`
   POST'u, kimlik doğrulayan hesap bir *makine hesabı* (`$` ile biten) ve
   kaynak IP *o makinenin gerçek IP'si değil* — saldırgan relay hostunun IP'si.
3. **Sertifika** — CA'da 4886/4887, Requester = `DC01$`, template genelde
   `Machine` / `DomainController`.
4. **DCSync** — `DC01$` sertifikasıyla PKINIT → DC01 kimliği → **DRSUAPI
   GetNCChanges** (DCSync). Sinyal: DC'de 4662 `Replicating Directory
   Changes` GUID'i (`1131f6aa-9c07-11d1-f79f-00c04fc2dcd2`) *bir DC olmayan*
   veya beklenmedik bir kaynaktan.

Buradaki güçlü bağ: **bir makine hesabının, kendi olmayan bir IP'den web
enrollment yapması + kısa süre sonra o makine kimliğiyle replikasyon
istenmesi.** İki sinyal ayrı ayrı açıklanabilir; birlikte, relay saldırısının
imzasıdır.

### Zincir C — Kalıcılık (Golden Certificate / THEFT)

Saldırgan CA'nın *private key*'ini çalarsa (ESC yok, doğrudan CA sunucusundan
`certutil -exportPFX` ya da DPAPI ile CA'nın kök anahtarı), artık *kendi
kendine* istediği kimlik için sertifika üretir — CA'ya hiç istek gitmez, 4886/
4887 *hiç oluşmaz*. Bu "Golden Certificate"tır. Burada CA logu tamamen kördür;
tek yakalama noktası **DC'deki 4768** — çünkü sertifika geçerli görünse de
sonunda birileri onunla kimlik doğrular. Sinyal: PKINIT 4768'de sertifikanın
Serial/Issuer'ı, CA'nın *kendi issued-certificate* veritabanında (`certutil
-view`) *yok* ise, o sertifika CA'nın dışında üretilmiştir → Golden
Certificate. Bu "CA veritabanında olmayan ama geçerli zincirli sertifikayla
kimlik doğrulama" korelasyonu, bu tekniğin gerçek tek güvenilir tespitidir ve
hiçbir tekil Sigma kuralında yoktur.

---

## 4. False positive gerçeği ve triage yargısı

ADCS alarmlarının gürültü kaynakları çok somut ve her kurumda var:

- **Otomatik enrollment (autoenrollment)** — Grup İlkesi ile makineler ve
  kullanıcılar her gün otomatik sertifika yeniler. Bu, 4886/4887'nin *devasa*
  çoğunluğudur. Bir DC'nin veya web sunucusunun kendi kimliği için sertifika
  alması normaldir. Anahtar ayrım: autoenrollment'ta **Requester = SAN**
  (makine kendi adına ister). ESC1'de **Requester ≠ SAN**. Triage'da ilk
  bakılan alan budur.
- **SCCM / MECM** — İstemci sertifikaları basar, dağıtım noktaları için
  sertifika ister. `NDES`/`SCEP` altyapısı varsa, network cihazları için
  toplu sertifika istekleri normal. SCCM sunucu hesabını ve NDES service
  account'unu whitelist referansı olarak bilmek şart.
- **Web sunucusu / yük dengeleyici ekipleri** — `WebServer` template'inden
  SAN'lı sertifika isterler; SAN'da alan adları olur, ama bunlar *kullanıcı
  UPN'i* değil DNS adıdır. ESC1 tespitinde SAN'ın *UPN türü* (kişi kimliği)
  mi yoksa *DNS türü* (sunucu) mü olduğunu ayırmak, false positive'i
  onlarca kat düşürür.
- **Zafiyet tarayıcıları ve iç kırmızı takım** — PingCastle, Locksmith,
  BloodHound/SharpHound, `Certify find /vulnerable`. Bunlar keşif imzalarını
  düzenli ateşler. Bilinen tarama hostları ve zamanlanmış pencereler
  (örn. her Pazar 02:00 PingCastle) baseline'a alınmalı.
- **VPN / 802.1x / NPS** — İstemci kimlik doğrulama sertifikaları, PKINIT
  benzeri akışlar üretir; 4768'de sertifika alanı dolu birçok *meşru*
  olay olur. "PKINIT var" tek başına şüphe değildir.

**Kıdemli analistin triage sırası** çoklu alarm geldiğinde şudur:

1. **Önce yönü belirle: Requester ↔ SAN uyuşmazlığı var mı?** Yoksa büyük
   olasılıkla autoenrollment/meşru. Bu tek soru vakaların %90'ını eler.
2. **SAN'ın türü ne?** UPN (kişi) → yüksek şüphe. DNS (sunucu) → düşük.
3. **Talep edilen kimlik ayrıcalıklı mı?** SAN = normal kullanıcı ile SAN =
   Domain Admin arasında dünya kadar fark var.
4. **Zincirin devamı var mı?** Sertifika basıldıktan sonra o kimlik *gerçekten
   kullanıldı mı* (4768 PKINIT → 4624 → yanal hareket)? Basılıp kullanılmayan
   anormal sertifika bile önemlidir ama "basıldı + 10 dk içinde DA olarak
   login" acil müdahaledir.
5. **Kaynak host güvenilir mi?** İsteği yapan makine bir admin iş
   istasyonu/PKI sunucusu mu, yoksa bir kullanıcı laptopu mu? İstek bağlamı
   (parent process, kullanıcı bağlamı) sertifikanın "nasıl" istendiğini
   söyler.

Yargının özü: **ADCS'de gürültü ile ihlali ayıran şey olayın *kendisi* değil,
olaydaki kimlikler arasındaki tutarsızlıktır.** Tek bir 4887'ye bakıp karar
verilmez; Requester, SubjectAltName ve template üçlüsü birlikte okunur.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan, yukarıdaki tespitleri bilir ve dokümanda yazmayan yollarla atlatır.
Her atlatmaya ikinci-derece bir tespit vardır.

**Kaçınma 1: Araç adını ve metadata'yı değiştirmek.** `Certify.exe` →
`svchost_helper.exe`, OriginalFileName strip, in-memory .NET yükleme.
→ **Karşı-tespit:** Process_creation imzalarını *bırak*, sonuca odaklan. Araç
ne adla çalışırsa çalışsın, sonunda CA'ya bir sertifika isteği gider (4886) ve
sonunda PKINIT olur (4768). Davranışsal zincir (Bölüm 3) araç adından
bağımsızdır. Ayrıca, `Certify` .NET içinde çalışsa bile CLR yüklenmesi (Sysmon
Event 7 — `clr.dll`/`clrjit.dll` bir .NET olmayan process'e) + LDAP template
sorguları anomalisi ikinci-derece iz bırakır.

**Kaçınma 2: Keşifi gürültüde saklamak / hiç yapmamak.** Saldırgan
`/vulnerable` taraması yapmaz — zaafiyeti önceden BloodHound verisinden bilir,
doğrudan `request` yapar. → **Karşı-tespit:** Keşif imzasına *güvenme*; asıl
tespiti *istek* aşamasına koy (Requester≠SAN). Keşifi kaçırmak zincirin geri
kalanını kaçırmaz.

**Kaçınma 3: Düşük ve yavaş (low-and-slow) SAN.** Doğrudan `Administrator`
yerine, daha az izlenen bir orta-yetki hesabının (örn. bir yardım masası
hesabı, bir servis hesabı) SAN'ını enjekte etmek — böylece "Domain Admin"
filtresine takılmaz. → **Karşı-tespit:** Ayrıcalık filtresini *statik listeyle*
değil, "Requester ≠ SAN" *mutlak* koşuluyla kur. Hedefin ayrıcalığı ne olursa
olsun, birinin başkası adına sertifika istemesi anormaldir. Ayrıcalık sadece
*önceliklendirmeyi* değiştirir, alarmı susturmaz.

**Kaçınma 4: ESC8 relay ile CA loglarını atlamak.** Requester meşru bir makine
hesabı olduğu için 4886/4887 "temiz" görünür. → **Karşı-tespit:** Kaynak IP
tutarsızlığı. Bir makine hesabının web enrollment'ı, o makinenin *gerçek
IP'sinden* gelmelidir. Relay'de kaynak IP saldırgan hostudur. IIS logunda
`certsrv` erişimi + hesabın makine hesabı olması + IP'nin DNS/DHCP'deki makine
IP'siyle çelişmesi = relay imzası. Ayrıca coercion tarafında `EFSRPC`/`MS-RPRN`
RPC anomalisi ilk-adım tespiti.

**Kaçınma 5: Golden Certificate (CA'yı hiç kullanmamak).** CA private key
çalındıktan sonra sertifikalar offline üretilir, hiç 4886/4887 yok. →
**Karşı-tespit:** Bölüm 3-C'deki "CA veritabanında bulunmayan geçerli
sertifikayla PKINIT" korelasyonu. Ek olarak, CA private key erişiminin
*kendisini* izle: CA sunucusunda `certutil -exportPFX`, DPAPI master key
erişimi, CA'nın key container'ına (`MachineKeys`) erişen olağandışı process.
Bu bir kez olur ama olduğunda bütün PKI'yi ele geçirir — CA sunucusu Tier-0
gibi izlenmeli.

**Kaçınma 6: Şablonu değil, izinleri hedef almak (ESC7 / ESC4).** Saldırgan
zafiyetli şablon istemek yerine, *kendi* yazma yetkisi olan bir şablonu
zafiyetli hale *getirir* (ESC4 — template ACL) veya CA rolünü kötüye kullanır
(ESC7). → **Karşı-tespit:** AD'de sertifika şablonu nesnelerine
(`CN=...,CN=Certificate Templates,CN=Public Key Services`) yapılan
**değişiklikler için 5136** (directory object modified). Bir template'in
`msPKI-Certificate-Name-Flag` veya `msPKI-Enrollment-Flag` ya da EKU/DACL'i
değişiyorsa bu son derece nadir, yüksek değerli bir tespittir. Template
değişikliği + hemen ardından o template'ten istek = ESC4 zinciri.

Kedi-fare özeti: **saldırgan izleri çevrede (araç, keşif, CA logu) yok
edebilir, ama zincirin iki değişmez noktasını yok edemez** — (a) sonunda
birinin sertifikayla PKINIT yapması (4768), ve (b) kimlikler arası
tutarsızlık. Tespit stratejisini bu iki değişmez etrafında kurmak, atlatmaları
sistematik olarak yakalar.

---

## 6. SIEM / saha gerçeği

**Alan eşleme (field mapping) tuzakları.** En büyük tuzak: 4887'nin SAN'ı
*taşımaması*. Ham CA olayı SAN'ı ayrı bir "Subject Alternative Name" attribute
olarak barındırır ve bu, EventData şemasında standart bir alan *değildir* —
çoğu SIEM parser'ı onu ayıklamaz. Splunk'ta Windows TA (`Splunk_TA_windows`),
Sentinel'de `SecurityEvent` tablosu ve Elastic'te Winlogbeat, 4887'yi alsa
bile SAN'ı `EventData` içinde ham XML'de bırakabilir. Çözüm: CA üzerinde
istekleri *ham* toplamak — çoğu ekip `Certificate Services Client` operational
loglarını veya doğrudan CA veritabanını (`certutil -view -restrict`) periyodik
çekerek Requester↔SAN eşlemesini SIEM dışında zenginleştirir. Alternatif:
`ESC` tespiti için özel olarak yazılmış toplayıcılar (örn. CA üzerinde bir
scheduled task ile `Get-ADCSTemplate` + issued-cert dökümü).

**Varsayılan loglanmayanlar — şart olan yapılandırma.**

- CA denetimi *varsayılan kapalı*. Açmak için: `certutil -setreg
  CA\AuditFilter 127` ve ardından CA servis restart; ayrıca Local Security
  Policy'de "Audit Certification Services" (veya gelişmiş denetimde "Object
  Access → Certification Services") başarı/başarısızlık açık olmalı. Bu
  yapılmadan 4886/4887/4899 *hiç* üretilmez.
- DC tarafında PKINIT'in 4768'de sertifika alanını doldurması için Kerberos
  denetimi (Account Logon → Kerberos Authentication Service) açık olmalı.
  Varsayılan çoğu ortamda başarı loglanır ama hacim yüzünden bazen kapatılır —
  o zaman Golden Certificate tespiti tamamen kör olur.
- **Sysmon** olmadan process katmanı zayıf. ESC izlemesi için Sysmon config'de
  Event 1 (process create — komut satırı ile), Event 7 (image/DLL load — CLR
  tespiti için `clr.dll`), Event 10 (process access — LSASS/CA key erişimi) ve
  network (Event 3, ESC8 relay için) açık olmalı. SwiftOnSecurity/Olaf
  Hartong config'leri bunları kapsar ama `certsrv` ve `MachineKeys` yollarını
  özel olarak eklemek gerekir.
- **KDC eşleme sıkılaştırması (2022+):** Microsoft'un KB5014754 sonrası
  "strong certificate mapping" değişikliği (Event **39/40/41** KDC-SVC
  kaynağında) ESC9/ESC10 tespitinde kritik. Zayıf eşleme (SID uzantısı
  olmayan sertifika) denemeleri artık DC System logunda iz bırakır — bu
  olaylar (özellikle Event 39 "certificate does not have the SID") çoğu
  ekibin haberi olmadan zaten toplanıyor olabilir; ESC9/10 avında ilk
  bakılacak yer burasıdır.

**Splunk vs Sentinel vs Elastic pratik farkları.**

- **Splunk:** İki farklı sourcetype (`WinEventLog:Security` CA'dan ve DC'den)
  arasında `transaction` veya `stats`+`eval` ile korelasyon kurmak gerekir.
  Tuzak: CA ile DC'nin saat senkronizasyonu ve olay sıralaması — `_time`
  penceresi çok dar tutulursa relay/PKINIT gecikmesi bağı kopar; 15-30 dk
  pencere makul. Requester↔SAN eşlemesi için genelde bir lookup tablosuna
  (issued cert dökümü) `lookup` ile join yapılır çünkü SAN native alanda yok.
- **Sentinel:** KQL ile `SecurityEvent`'i kendisiyle `join` etmek doğal, ama
  4887'nin `EventData`'sını `parse_xml`/`extractjson` ile açmak gerekir; SAN
  çoğu zaman `Certificate Information` içinde değil ham XML'de. Sentinel'in
  ADCS için hazır analytics kuralları (`ESC1`, `ESC8`) var ama bunlar da SAN
  parse'ına bağımlı — connector doğru kurulmazsa boş döner. UEBA ile
  "makine hesabı anormal kimlik doğrulama" davranışsal olarak yakalanabilir.
- **Elastic:** Winlogbeat/Elastic Agent ADCS'yi toplar; `winlog.event_data`
  altında alanlar iç içe. Elastic'in prebuilt detection'larında ADCS zayıf;
  çoğu ekip EQL ile sequence (`sequence by ... with maxspan=30m`) yazarak
  4887→4768 zincirini kurar. EQL'in `sequence` yapısı bu korelasyon için
  aslında en temiz araçtır ama SAN alanı yine manuel ingest pipeline (Grok/
  Painless) ile çıkarılmalı.

**Tuning gerçeği.** ADCS tespitini "aç ve unut" yapmak imkânsız. İlk 2 hafta
Requester=SAN olan tüm meşru autoenrollment/SCCM/webserver trafiğini
baseline'a alıp bir allowlist çıkarmak *şart*; yoksa Requester≠SAN kuralı bile
—çünkü bazı meşru workflow'lar (örn. bir admin'in başka kullanıcı adına
sertifika bastığı yardım masası süreçleri, "enroll on behalf of" ESC3'ün
meşru hali) tetikler— gürültü üretir. Enroll-on-behalf-of (Enrollment Agent)
akışlarını tanımak ve o service account'ları bilmek, false positive'i kabul
edilebilir seviyeye indirmenin anahtarıdır. Son olarak: **CA sunucusunu
Tier-0 olarak sınıflandırmayan bir kurumda hiçbir ADCS tespiti gerçek koruma
sağlamaz** — çünkü CA'ya local admin olan biri zaten tüm bu logları da
kapatabilir, private key'i de çalabilir. Tespit mühendisliği burada altyapı
güvenliğiyle (CA'nın izolasyonu, HSM ile key koruması, web enrollment'ın
kaldırılması / EPA zorunluluğu) el ele gitmek zorundadır.

---

### Kapanış yargısı

ADCS tespitinin özeti tek cümlede: **araç ve keşif imzaları başlangıç, ama
gerçek tespit "kim, kimin adına, sertifikayla ne yaptı" üçlüsünü CA ve DC
loglarını birleştirerek okumaktır.** Requester≠SAN mutlak koşulu, PKINIT
4768'in değişmezliği ve "CA veritabanında olmayan geçerli sertifika"
korelasyonu — bu üçü, saldırganın çevresel izleri silmesine rağmen ayakta
kalan tespit sütunlarıdır. Geri kalan her şey, bu sütunları besleyen doğru
audit policy ve doğru alan eşlemesidir.
