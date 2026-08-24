# Business Email Compromise (BEC) Soruşturması — Pratisyen DFIR İş Akışı

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Business Email Compromise (BEC), saldırganın bir kurumsal e-posta hesabını ele geçirip (ya da hesabı taklit edip) genellikle **para transferi, fatura yönlendirme veya veri sızdırma** amacıyla bu güveni kötüye kullandığı olay sınıfıdır. Fidye yazılımının aksine BEC "gürültüsüzdür": şifreleme yok, fidye notu yok, çoğu zaman tek bir kurbanın gelen kutusundaki sessiz kurallar ve birkaç e-posta vardır. Tam da bu sessizlik, onu tespit ve soruşturma açısından zor kılar. FBI IC3 verilerinde yıllardır en yüksek doğrudan finansal kayba yol açan siber suç kategorisi BEC'tir — teknik sofistikasyon düşük, finansal etki devasadır.

Bir BEC soruşturmasının **hedefi üç sorudur:**

1. **Kapsam (scope):** Hangi hesap(lar) gerçekten ele geçirildi? Tek hesap mı, lateral hareket ile birden çok hesap mı? Sadece kimlik avı mı yoksa gerçek oturum var mı?
2. **Erişim penceresi (dwell time):** Saldırgan ne zaman girdi, ne zamana kadar erişimi vardı, hangi verilere/postalara dokundu?
3. **Etki ve süreklilik (impact & persistence):** Para gitti mi, gidiyor mu? Saldırgan hâlâ içeride mi (OAuth token, inbox rule, uygulama parolası, MFA cihazı ekledi mi)?

IR sürecindeki yeri: Bu iş akışı klasik **PICERL / NIST 800-61** döngüsünde ağırlıklı olarak **Identification (Tanımlama)** ve **Containment (Sınırlama)** aşamalarına oturur, ama BEC'in özelliği şudur: **Containment'i Investigation'dan önce yapmak zorunda kalırsınız.** Para hareket ediyorsa forensic saflık ikinci plandadır — önce oturumu öldürür, parolayı sıfırlar, transferi durdurmaya çalışırsınız. DFIR'de nadiren "önce delil sonra aksiyon" kuralının bilinçli olarak esnetildiği yer burasıdır. Bu kararı vermek kıdemli analistin işidir.

Modern BEC'in %90'ı artık **cloud identity** dünyasında geçer: Microsoft 365 (Entra ID / Exchange Online) ve Google Workspace. Dolayısıyla bu iş akışının merkezi **disk imajı değil, bulut denetim loglarıdır.** KAPE/Volatility gibi endpoint araçları burada ikincil roldedir — asıl artefakt Unified Audit Log (UAL), Entra sign-in logları ve mailbox audit'tir.

---

## 2. Adım-adım İŞ AKIŞI ve KARAR (asıl değer)

Aşağıda bir profesyonelin gerçek sırasıyla ne yaptığı ve **hangi artefaktı görünce hangi sonuca gittiği** var.

### Adım 0 — Tetik ve ilk üçgenleme (triage), aksiyona geçmeden önce 5 dakika

BEC ihbarı tipik olarak şu üç kanaldan gelir: (a) muhasebe "bu IBAN değişikliği garip" der, (b) kullanıcı "gönderdiğim maili hatırlamıyorum" der, (c) bir dış taraf "sizden gelen dolandırıcı maili aldık" der.

İlk karar: **Bu gerçek bir hesap ele geçirme (account takeover / ATO) mi, yoksa sadece display-name spoofing / lookalike domain mi?** Bu ayrım her şeyi belirler.

- E-posta gerçekten kurbanın **kendi** mailbox'ından mı gönderildi (Sent Items'ta var mı, message trace'te internal origin mi)? → Gerçek ATO, hesap ele geçirilmiş.
- Yoksa `ceo@sirket-tr.com` yerine `ceo@sirket-rt.com` gibi benzer bir domainden mi geldi? → Bu ATO değil, **impersonation**; soruşturma tamamen farklı yöne gider (mailbox forensics yerine header analizi + domain kaydı).

Header'a bakın: `Authentication-Results` içinde SPF/DKIM/DMARC. Kurumun kendi domain'inden geldiği iddia edilen mail DKIM `fail` veya domain uyumsuz ise → dış taklit. `pass` ise → muhtemelen gerçekten içeriden gönderildi, ATO ciddiye alınır.

### Adım 1 — Order of volatility'yi tersine çevir: önce uçucu bulut oturumu

Klasik order of volatility (RAM > disk) BEC bulutunda farklı işler. En uçucu ve en değerli delil **canlı saldırgan oturumu ve token'lardır** — bunlar dakikalar içinde yenilenir veya değişir. Dolayısıyla:

1. **Aktif oturumları ve sign-in loglarını hemen çek/dondur.** M365'te Entra ID > Sign-in logs; ele geçirilmiş hesap için son 7–30 gün. Google'da Admin Console > Reports > Login audit.
2. Sign-in loglarında aranan sinyaller:
   - **Imkânsız seyahat (impossible travel):** Kullanıcı 09:00'da İstanbul IP'sinden, 09:20'de Lagos veya bir VPS aralığından (DigitalOcean, OVH, M247 gibi hosting ASN'leri) giriş. → Güçlü ATO göstergesi.
   - **Legacy auth / non-interactive sign-in:** IMAP/POP/EWS üzerinden başarılı kimlik doğrulama, özellikle MFA'yı baypas eden eski protokoller. → Saldırgan MFA'yı legacy auth ile atlatmış olabilir.
   - **Bilinmeyen client app / user agent:** `Mozilla` yerine tuhaf bir Python/curl imzası, ya da "BAV2ROPC" gibi legacy client string'i.
   - **MFA durumu:** Girişte MFA "satisfied by claim in the token" görünüyorsa → token replay / AiTM (adversary-in-the-middle) phishing kiti (Evilginx tarzı) kullanılmış olabilir. Bu kritik bir bulgudur: parolayı sıfırlamak yeterli değildir, **oturum token'larını iptal etmek (revoke sessions)** gerekir.

> **Karar mantığı:** MFA açık ama başarılı giriş varsa, refleksif olarak "MFA vardı, güvendeyiz" DEME. AiTM phishing tam da MFA'lı oturum çerezini çalar. Sign-in log'da `MFA requirement satisfied by token` + AiTM domain'inden gelen bir tıklama görürsem, doğrudan token hırsızlığı senaryosuna giderim.

### Adım 2 — Unified Audit Log (UAL) / mailbox audit: asıl kazı

Microsoft 365'te Purview Audit (Unified Audit Log) BEC'in altın kaynağıdır. `Search-UnifiedAuditLog` (Exchange Online PowerShell) veya Purview portalından. Aranacak operasyonlar:

- **`New-InboxRule` / `Set-InboxRule` / `UpdateInboxRules`:** Saldırganın klasik ilk hamlesi. Kural genellikle: belirli anahtar kelimeler (`invoice`, `payment`, `wire`, `fatura`, `ödeme`, `IBAN`) içeren mailleri **RSS Feeds / Deleted Items / Archive** gibi kullanıcının bakmadığı bir klasöre taşır veya doğrudan siler. Amaç: kurbanın, dolandırıcılıkla ilgili yanıtları görmesini engellemek.
- **`Mailbox login` / `MailItemsAccessed`:** E5 lisansında `MailItemsAccessed` operasyonu hangi maillere erişildiğini gösterir — veri sızması kapsamı için kritik.
- **`Add-MailboxPermission` / delegation:** Saldırgan başka bir mailbox'a erişim verdi mi? Lateral hareket.
- **`Update`/`Send` operasyonları:** Kurban adına gönderilen mailler.

> **Karar mantığı:** Gizli bir inbox rule (özellikle adı boş, tek harf veya "." olan, ve `invoice/payment` kelimelerini bir çöp klasöre yönlendiren) görürsem, bu **kanıtlanmış ATO'dur** ve niyetin finansal dolandırıcılık olduğunu söyler. Bu tek artefakt, soruşturmanın yönünü "para izini takip et" moduna çevirir. Kuralı silmeden önce ekran görüntüsü + `Get-InboxRule` çıktısını export ederim (delil).

### Adım 3 — Süreklilik (persistence) ve OAuth kötüye kullanımı

Modern saldırgan parola sıfırlamasından sağ çıkmak için **kalıcılık** kurar. Kontrol listem:

- **OAuth uygulama izinleri (illicit consent grant):** Entra ID > Enterprise Applications. Kullanıcının onayladığı, `Mail.Read`, `Mail.ReadWrite`, `offline_access` gibi geniş izinleri olan, tanımadığınız üçüncü taraf uygulamalar. Bir OAuth token parola sıfırlamasıyla iptal olmaz — ayrı revoke gerekir. Saldırganların favori kalıcılık yöntemi budur çünkü "sessiz" ve MFA'dan etkilenmez.
- **Uygulama parolaları (app passwords):** MFA'yı baypas eden legacy erişim.
- **Eklenen MFA yöntemi:** Saldırgan kendi telefonunu/authenticator'ını MFA cihazı olarak ekledi mi? Entra audit'te `Add security info` / `Register security information`. Eklendiyse, parola sıfırlansa bile saldırgan geri girebilir.
- **SMTP forwarding / mailbox forwarding kuralı:** `Set-Mailbox -ForwardingSmtpAddress`. Inbox rule'dan farklı; mailbox seviyesinde tüm postayı dışarı yönlendirir.

> **Karar mantığı:** Bir hesabı "temizledim" demeden önce şu dört şeyi kapatmadıysam iş bitmemiştir: (1) parola sıfırla, (2) **tüm oturum token'larını revoke et**, (3) şüpheli OAuth grant'larını iptal et, (4) saldırganın eklediği MFA yöntemini/forwarding'i kaldır. Sadece parola sıfırlamak acemi hatasıdır — saldırgan OAuth token veya app password ile 5 dakika sonra geri döner.

### Adım 4 — Zaman çizelgesi (timeline) ve korelasyon

Tüm bulguları tek bir zaman çizelgesinde birleştiririm. Araç olarak logları CSV export edip **Timesketch**'e yüklerim (ya da küçük vakada Excel + Eric Zimmerman `Timeline Explorer`). Timesketch'te her olayı UTC'ye normalize eder, kullanıcı davranışı ile saldırgan davranışını üst üste bindiririm:

- İlk şüpheli sign-in (initial access) → phishing mailinin geldiği/tıklandığı an ile eşleşiyor mu? (Message trace ile phishing mailini bul.)
- Inbox rule oluşturma zamanı → hangi oturumda?
- İlk dolandırıcı outbound mail → ne zaman?

Bu timeline, dwell time'ı ve "hasta sıfır" (patient zero) e-postasını verir.

### Adım 5 — Endpoint gerekli mi? Ne zaman diske inersin

BEC çoğunlukla saf-bulut olsa da, phishing mailindeki bağlantı bir bilgisayarda kimlik bilgisi çaldıysa veya token bir endpoint'ten çalındıysa, endpoint forensics devreye girer. Burada geleneksel araç seti:

- **KAPE** ile hedefli triage collection (browser history, credential artefaktları, `$MFT`, event logları) — full disk imajı yerine hızlı, cerrahi toplama.
- **Eric Zimmerman araçları:** browser history/cache için tarayıcı artefaktları, `LECmd` (LNK), `MFTECmd`, `EvtxECmd` ile Windows event log parse — özellikle 4624/4625 logon olayları ve tarayıcıdan phishing sitesine gidişin zaman damgası.
- **Velociraptor:** Filo genelinde "başka kim aynı phishing linkine tıkladı / aynı IOC'ye temas etti" sorusu için hunt. BEC'in tek kullanıcıdan filo geneline yayılıp yayılmadığını Velociraptor artefaktlarıyla tararım.
- **Volatility** ve RAM analizi: BEC'te nadiren gerekir; ama token/çerez hırsızlığı yapan bir malware (info-stealer, örn. tarayıcı çerezi çalan) şüphesi varsa, canlı makinenin RAM'inden çerez/process delili çıkarmak için kullanılır. Info-stealer + BEC kombinasyonunda değerlidir.
- **YARA:** Toplanan endpoint örneklerinde veya mail eklerinde bilinen phishing kiti / stealer imzalarını taramak için. Örn. mail ekindeki HTML smuggling payload'unu YARA kuralıyla yakalamak.

> **Karar mantığı:** Sign-in log'da initial access AiTM proxy domain'ine işaret ediyorsa, endpoint'e inmeme genelde gerek kalmaz — çerez proxy üzerinden çalınmıştır, diskte iz olmayabilir. Ama sign-in "known device"tan geliyorsa ve MFA hiç tetiklenmediyse, o cihazda bir stealer olabilir; işte o zaman KAPE + Velociraptor ile endpoint'e inerim.

### Adım 6 — Para izi ve dış bildirim

Teknik soruşturmaya paralel: Eğer fatura/IBAN değişikliği ile para hareketi olduysa, **finans ekibine derhal banka geri çağırma (recall/SWIFT recall) talebi** yaptırılır — ilk 24–72 saat kritiktir. Bu DFIR analistinin doğrudan işi değildir ama **tetiklemesi gereken karardır**. Ayrıca yasal/uyum ekibi, gerekiyorsa kolluk (Türkiye'de USOM/CISO bildirimi, KVKK açısından veri ihlali değerlendirmesi) bilgilendirilir.

---

## 3. Kritik dikkat noktaları

**Delil bütünlüğü ve order of volatility (bulut versiyonu):** Bulut loglarının **saklama süresi (retention)** sınırlıdır. M365'te varsayılan Unified Audit Log retention lisansa bağlı olarak 90–180 gün olabilir; E5/audit add-on olmadan `MailItemsAccessed` gibi kritik operasyonlar hiç toplanmamış olabilir. Dolayısıyla **ilk iş logları export edip dondurmaktır** — analiz sonra yapılır. "Yarın bakarım" dersen retention penceresi kapanır ve delil sonsuza dek gider. Bu, disk imajını korumaktan daha aciledir çünkü bulut logu senin kontrolünde değildir.

**Chain of custody:** Export ettiğin her log CSV'sinin, ekran görüntüsünün hash'ini (SHA-256) al, kim-ne-zaman-nereden topladı kaydını tut. BEC vakaları sıkça yasal sürece (sigorta talebi, dava, kolluk) taşınır; delilin mahkemede tutunması için toplama zinciri belgelenmelidir. `Search-UnifiedAuditLog` çıktısını export ederken çekim komutunu, zamanı ve operatörü de kaydet.

**Aksiyon ve delil arasındaki gerilim:** Bir inbox rule'u silmek, bir oturumu revoke etmek delili değiştirir. Doğru sıra: **önce delili kaydet (export/screenshot/hash), sonra remediate et.** Ancak para aktif akıyorsa bu kuralı bilinçli esnetir, önce durdurur, sonra elde ne kaldıysa toplar ve bu kararı belgeleriz. Kararı ve gerekçesini yazılı olarak IR günlüğüne düşmek şarttır.

**Anti-forensics'e karşı:** BEC saldırganı iz temizler:
- **Gönderilen dolandırıcı mailleri Sent Items'tan siler** ve inbox rule ile gelen yanıtları gizler. Bu yüzden Sent Items'a değil, **message trace / transport logs**'a güvenirim — kullanıcı silse bile sunucu tarafı transport kaydı kalır (retention süresince).
- **Deleted Items'ı da boşaltabilir.** Burada `Recoverable Items` (dumpster) ve varsa litigation hold devreye girer; hold açıksa kullanıcı/saldırgan sildiği maili gerçekten yok edemez.
- **Inbox rule'u iş bitince siler.** Ama UAL'de `New-InboxRule` operasyonu, kural silinmiş olsa bile kalır — o yüzden mailbox'ın anlık haline değil, **audit log'a** bakarım.

> Genel ilke: **Kullanıcının/saldırganın değiştirebildiği yüzey artefaktına (mailbox'ın anlık hali) değil, değiştiremediği sunucu tarafı denetim/transport loguna güven.**

---

## 4. Gerçek dünya senaryosu

**Vaka:** Orta ölçekli bir ihracat firmasının muhasebe müdürü, "yurt dışı tedarikçiye 78.000 EUR ödeme yeni IBAN'a gitti ama tedarikçi parayı alamadı" diye IT'yi arar.

**Adım 0 — Triage:** Ödeme talimatı, gerçekten firmanın kendi CFO'sunun (`cfo@firma.com.tr`) mailinden mi geldi? Message trace'e bakarım. `Authentication-Results: dkim=pass; spf=pass; dmarc=pass` ve origin internal. → Bu spoofing değil, **CFO hesabı gerçekten ele geçirilmiş.** ATO onaylandı.

**Adım 1 — Sign-in log:** CFO hesabı için son 14 gün. Bulgu: 3 gün önce 02:14 UTC'de bir `M247` hosting ASN IP'sinden (Bükreş) başarılı interactive sign-in. Aynı gün 08:30'da CFO'nun normal İstanbul IP'sinden girişi de var → **impossible travel + hosting ASN** = güçlü ATO. Sign-in detayı: MFA "satisfied by token" — yani parola + oturum çerezi ele geçirilmiş, klasik **AiTM phishing**. Message trace'te 4 gün önce CFO'ya gelen "DocuSign - Fatura İmzanız Bekleniyor" konulu, `firma-secure-docs[.]com` linkli mail bulundu → phishing patient zero.

**Adım 2 — UAL:** `Search-UnifiedAuditLog` çıktısında, saldırgan girişinden 6 dakika sonra bir `New-InboxRule`: adı `.` (tek nokta), koşulu "konu veya gövdede `ödeme`, `IBAN`, `fatura`, `SWIFT`, `payment` geçerse → RSS Feeds klasörüne taşı ve okundu işaretle". → **Kanıtlanmış finansal niyet.** CFO, tedarikçinin "IBAN neden değişti?" yanıtlarını hiç görmemiş çünkü hepsi RSS Feeds'e gizlenmiş.

**Adım 3 — Persistence:** Enterprise Applications'ta, olay gününde onaylanmış `Mail.ReadWrite` + `offline_access` izinli, tanınmayan bir OAuth app ("PDF Invoice Reader") bulundu. → Saldırganın kalıcılığı bu; parola sıfırlansa bile bu token ile okumaya devam edebilirdi.

**Adım 4 — Timeline (Timesketch):** phishing maili (gün 0) → tıklama/AiTM (gün 0) → ilk hosting-IP girişi (gün 0, 02:14) → inbox rule (02:20) → OAuth grant (02:35) → tedarikçiye sahte IBAN'lı ödeme talimatı maili (gün 1) → muhasebenin ödemesi (gün 2) → ihbar (gün 3). Dwell time ~3 gün.

**Adım 5 — Endpoint:** CFO'nun laptopunda KAPE triage; tarayıcı geçmişinde `firma-secure-docs[.]com`'a gidiş var ama diskte malware yok → çerez AiTM proxy'de çalınmış, endpoint temiz. Velociraptor hunt ile firma genelinde aynı phishing domain'ine başka tıklayan yok → tek kurban, lateral yayılma yok.

**Varılan sonuç:** Tek hesaplık AiTM tabanlı BEC. Initial access = MFA baypaslı token hırsızlığı. Impact = 78.000 EUR sahte IBAN'a. Persistence = gizli inbox rule + illicit OAuth grant. **Remediation:** parola sıfırla + **tüm oturumları revoke et** + OAuth app'i kaldır + inbox rule'u (export sonrası) sil + MFA'yı phishing-resistant (FIDO2/number matching) yap + legacy auth'u kapat. **Finansal:** ilk 48 saatte banka SWIFT recall talebi başlatıldı. **Ders:** Kurum "MFA'mız var, güvendeyiz" sanıyordu — AiTM MFA'yı deldi.

---

## 5. Yaygın tuzaklar ve pro yargısı

**1. "Parolayı sıfırladım, hallettim."** En yaygın acemi hatası. AiTM/token hırsızlığında oturum çerezi hâlâ geçerlidir ve OAuth grant/app password parola değişiminden etkilenmez. Pro her zaman **revoke sessions + OAuth denetimi + MFA yöntem denetimi** yapar. Parola sıfırlamak tek başına saldırganı dışarı atmaz.

**2. Sadece ele geçirilen hesaba bakmak.** Saldırgan lateral hareket etmiş, başka mailbox'lara delegate izni almış olabilir. Tek hesaba odaklanıp kapsamı daraltmak, ikinci bir sessiz hesabın kaçmasına yol açar. Her zaman "başka kim etkilendi" (Velociraptor hunt, tenant-geneli OAuth taraması) sorulur.

**3. Mailbox'ın anlık haline güvenmek.** Acemi, inbox'a bakıp "kural yok, mail yok, temiz" der. Saldırgan kuralı silmiş, mailleri temizlemiştir. Pro **UAL/audit log ve message trace**'e bakar — kullanıcının değiştiremediği sunucu tarafı kayda.

**4. Impersonation ile ATO'yu karıştırmak.** `firma-rt.com` gibi lookalike domain'den gelen maili gerçek hesap ele geçirme sanıp mailbox forensics'e gömülmek saatler kaybettirir. Header/DKIM analizi ile daha ilk 5 dakikada ayrımı yapmak gerekir; ikisi tamamen farklı soruşturmadır.

**5. MFA'ya kör güven.** "MFA açıktı, o yüzden ele geçirme olamaz" — yanlış. AiTM phishing kitleri (Evilginx tarzı) MFA'lı oturumu proxy'leyerek çerezi çalar. Sign-in log'da "MFA satisfied by token" + hosting ASN görünce pro, MFA'nın delindiğini bilir ve phishing-resistant MFA'ya (FIDO2) geçişi önerir.

**6. Log retention penceresini ıskalamak.** Analize başlamadan export etmeyi ertelemek. UAL retention'ı dolduğunda delil kalıcı olarak yok olur. Pro'nun ilk hamlesi analiz değil, **logları dondurmak**tır. Ayrıca vaka öncesi audit/E5 lisansı yoksa `MailItemsAccessed` hiç toplanmamıştır — bunu baştan bilmek, "veri sızdı mı" sorusuna dürüst cevap verebilmek için şarttır (belki kesin cevap yoktur, bunu da söylemek gerekir).

**7. Finansal aciliyeti teknik soruşturmaya feda etmek.** Analist "önce forensic'i bitireyim" diye para geri çağırma penceresini kaçırırsa 78.000 EUR gider. Pro, teknik kazı devam ederken paralel olarak finans/banka aksiyonunu **tetikler**. İki iş aynı anda yürür.

**8. Anti-forensics'i hafife almak.** "Deleted Items boş, demek ki mail yok." Recoverable Items dumpster, message trace ve (varsa) litigation hold kontrol edilmeden hiçbir mail "yoktur" denemez. Pro, saldırganın silmiş olabileceğini varsayarak sunucu tarafı kalıntıları arar.

**Özet pro yargısı:** BEC teknik olarak basit, ama soruşturması iki noktada ustalık ister — (a) *kapsamı doğru çizmek* (tek hesap mı, kalıcılık nerede, kim daha etkilendi), (b) *doğru delile güvenmek* (mailbox anlık hali değil, sunucu tarafı denetim/transport logu). Bu ikisini doğru yapan analist, saldırganı gerçekten dışarı atar; yapmayan sadece parolayı değiştirip "temizledim" sanır ve saldırgan bir hafta sonra geri döner.
