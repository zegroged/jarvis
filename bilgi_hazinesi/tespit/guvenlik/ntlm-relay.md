# NTLM Relay — Tespiti

> Saha notu. NTLM relay, "bir kural yaz, bitir" diye bir konu değil. Kimlik doğrulama trafiğinin doğasından beslenen, ağ mimarisiyle iç içe geçmiş bir sınıf saldırıdır. Aşağıda naif tespitten başlayıp, gerçek ortamda neyin bozulduğuna ve kıdemli bir analistin ekranda neye baktığına kadar iniyorum.

---

## 1. Özet: saldırı + naif tespit

NTLM relay, kırılamayan bir hash'i kırmaya çalışmak yerine, kimlik doğrulama akışını olduğu gibi başka bir hedefe **taşımaya** dayanır. Kurban makine (veya kullanıcı), saldırganın kontrolündeki bir dinleyiciye NTLM ile kimlik doğrulaması yapar; saldırgan bu challenge/response akışını gerçek zamanlı olarak üçüncü bir hedefe (bir SMB paylaşımı, LDAP, HTTP/ADCS web enrollment, MSSQL...) aktarır. Saldırganın parolayı bilmesine gerek yoktur — kurbanın kimliğiyle hedefte oturum açar. Klasik tetikleyici, kurbanı saldırgana doğru kimlik doğrulamaya **zorlamaktır** (coercion): PetitPotam (MS-EFSRPC), PrinterBug/SpoolSample (MS-RPRN), DFSCoerce (MS-DFSNM), ya da yeni nesil DNS/SPN spoofing tabanlı zorlamalar (CVE-2025-33073, Synacktiv'in "NTLM reflection is dead" yayınına konu olan sınıf).

Naif tespit tarafında herkesin gösterdiği yer bellidir. Windows Güvenlik günlüğünde **Event ID 4624** (başarılı oturum açma) satırlarında `Authentication Package = NTLM` ve `Logon Type = 3` (network) aramak; bir de "aynı anda çok sayıda makineden NTLM logon" veya "sunucu hesaplarının NTLM ile oturum açması" gibi geniş fırçalarla desen çıkarmak. Buna genelde 4776 (NTLM kimlik doğrulama denetimi) ve zorlama tarafında **RPC/named pipe** göstergeleri eklenir. Örneğin verilen gerçek Sigma kurallarından *HackTool - CoercedPotato Named Pipe Creation* (id `4d0083b3-580b-40da-9bba-626c19fe4033`), Sysmon **Event ID 17/18** (pipe_created) üzerinden CoercedPotato'nun bıraktığı pipe adını yakalar; *HackTool - Generic Process Access* (id `d0d2f720-d14f-448d-8242-51ff396a334e`), `process_access` kategorisinde `SourceImage` alanında `\CoercedPotato.exe`, `\Certipy.exe`, `\crackmapexec.exe` gibi araç isimlerini arar.

Bu kuralların hepsi doğru ve gereklidir. Sorun, hiçbirinin tek başına "NTLM relay oldu" demeye yetmemesidir. Naif tespit, saldırının **imzasını** arar; oysa relay bir imza değil, bir **akış**tır.

---

## 2. Naif tespit neden yetmez

**Birinci kör nokta: relay'in kendisi ağda "normal" görünür.** Aktarılan kimlik doğrulama, hedef sunucu açısından tamamen geçerli bir NTLM oturumudur. 4624'te göreceğiniz şey, gerçek kullanıcının/makinenin adı, gerçek bir NTLM paketi, geçerli bir logon type 3'tür. Hedefte hiçbir alan "sahte" değildir — çünkü saldırgan sahtecilik yapmıyor, gerçek kimliği taşıyor. Dolayısıyla "NTLM logon type 3" araması, kurumsal ortamda günde on binlerce satır üretir ve gerçek relay o denizde bir damladır.

**İkinci kör nokta: en kritik ayırt edici alan çoğu ortamda boştur.** Relay'i normal NTLM'den ayıran teorik ipucu, kimlik doğrulamanın geldiği IP ile oturumu açan makinenin **uyuşmamasıdır**: makine hesabı `SRV01$` kimliğiyle bir oturum açılıyor ama kaynak IP `SRV01`'in IP'si değil, saldırgan kutunun IP'si. Ama 4624'teki `IpAddress`/`IpPort` alanları SMB relay senaryolarında güvenilir dolmaz; birçok ortamda `-` gelir, çünkü Netlogon/pass-through akışında kaynak adres kaybolur. Yani teoride "kaynak IP ile hesap adı eşleşmiyor" harika bir sinyal, pratikte log o alanı vermez.

**Üçüncü kör nokta: araç ismi tabanlı tespitler kırılgandır.** *Generic Process Access* ve *CoercedPotato pipe* kuralları, saldırganın `CoercedPotato.exe`, `Certipy.exe` isimlerini olduğu gibi kullanmasına bel bağlar. Bunları yeniden derlemek, isim değiştirmek, ntlmrelayx'i konteynerde saldırgan kutuda (kurumsal EDR görüş alanı **dışında**) çalıştırmak triviaildir. Relay'in aktif ucu genelde saldırganın Linux kutusudur — orada Sysmon yoktur, `process_access` yoktur, pipe olayı yoktur. Windows tarafında sadece **kurban** ve **hedef** görünür; saldırının motoru görünmez.

**Dördüncü kör nokta: false positive selleri.** "NTLM ile oturum açan sunucu hesapları" veya "çok sayıda makineye kısa sürede NTLM" gibi davranışsal kurallar, meşru altyapının tam da yaptığı şeydir. SCCM/ConfigMgr istemci taraması, yedekleme ajanları, vulnerability scanner'lar (Nessus/Qualys authenticated scan), DFS replikasyonu, yazıcı sunucuları — hepsi doğal olarak çok-hedefli NTLM üretir. Bu kuralı açık bırakan SOC, ilk hafta alarma boğulur, ikinci hafta kuralı susturur. Susturulan kural = olmayan kural.

Değer buradan başlıyor: relay'i tespit etmek için tek olayı değil, olaylar arasındaki **ilişkiyi** kurmak gerekir.

---

## 3. Korelasyon zinciri (asıl değer)

Relay tek başına zayıf sinyaldir; onu yüksek güvene çeviren şey, saldırının **zorunlu olarak** ürettiği çok aşamalı desendir. Saldırının doğası üç parçayı zincire dizer: (A) **zorlama** — kurbanı kimlik doğrulamaya iten tetik, (B) **aktarım** — relay'in kendisi, (C) **istismar** — hedefte kimliğin kötüye kullanımı. Bu üçünü zaman ve kimlik ekseninde bağlarsanız, tek bir 4624'ün asla veremeyeceği güveni elde edersiniz.

**Somut zincir — ADCS relay (ESC8) senaryosu, en yaygın kritik varyant:**

1. **A (zorlama):** Bir DC (`DC01$`) veya sunucu, beklenmedik bir hedefe NTLM ile kimlik doğrulamaya başlar. Kaynağı bir coercion RPC çağrısıdır — DC üzerinde MS-EFSRPC (PetitPotam) ya da MS-RPRN (PrinterBug) çağrısı. Yeni sınıfta ise verilen Sigma kurallarındaki gibi (`5588576c-...` ve `e7a21b5f-...`) DNS üzerinden SPN spoofing: DNS sorgusunda `1UWhRCAAAAA..BAAAA` gibi base64-kodlu marshaled `CREDENTIAL_TARGET_INFORMATION` imzası görünür. Bu, CVE-2025-33073 sınıfı Kerberos/NTLM coercion'ın güçlü göstergesidir.

2. **B (aktarım):** Zorlanan makine hesabı (`DC01$`), **kısa süre içinde** (saniyeler) ADCS'nin web enrollment endpoint'ine (HTTP, `certsrv`) NTLM ile kimlik doğrular. Burada anomali: bir **makine hesabının** bir CA'nın HTTP enrollment arayüzüne kimlik doğrulaması nadirdir. IIS logunda `CertSrv` altında `NTLM` auth ve `Machine$` kullanıcısı.

3. **C (istismar):** Aynı pencerede ADCS **Event ID 4886/4887** (sertifika talep edildi/verildi) — makine hesabı adına, sıklıkla **istemci kimlik doğrulaması** (Client Authentication EKU) içeren bir şablonla sertifika çıkar. Hemen ardından o sertifikayla **4768** (Kerberos TGT talebi) gelir: yeni alınan sertifikayla PKINIT üzerinden TGT, ve genelde kaynak IP yine saldırgan kutudur.

`A + kısa pencere içinde B (farklı host/bağlam) + C (aynı kimlik, sertifika→TGT)` = yüksek güvenli relay ihlali. Tek başına B'yi (makine hesabı ADCS'ye NTLM) yakalarsanız gürültü olabilir; ama coercion imzası + makine hesabının CA'ya NTLM'i + hemen ardından o hesap için sertifika/TGT üçlüsü aynı 60-120 saniyede aynı prensipal etrafında toplanırsa, bunun meşru açıklaması yoktur.

**İkinci somut zincir — LDAP relay ile RBCD (kaynak-tabanlı kısıtlı delegasyon):**

- **A:** Coercion ile bir bilgisayar hesabı zorlanır.
- **B:** O kimlik DC'ye **LDAP/LDAPS** ile relay edilir (ntlmrelayx `-t ldap://dc`).
- **C:** Kısa sürede hedef bir bilgisayar nesnesinin `msDS-AllowedToActOnBehalfOfOtherIdentity` özniteliği değişir — bu **Event ID 5136** (dizin nesnesi değiştirildi) ile loglanır, `AttributeLDAPDisplayName: msDS-AllowedToActOnBehalfOfOtherIdentity`. Bu öznitelik değişimi zaten kendi başına yüksek değerli bir alarmdır; coercion'la aynı pencerede geldiğinde relay olduğu neredeyse kesindir. Ardından saldırgan S4U2Self/S4U2Proxy ile hedefe erişir (**4769** anormal servis bileti talepleri).

Kritik nokta: 5136 üzerinde `msDS-AllowedToActOnBehalfOfOtherIdentity` değişimini **mutlaka** izleyin — bu, LDAP relay'in "istismar" ucudur ve çok daha az gürültülüdür; korelasyonun çapası olarak kullanın.

**Üçüncü somut zincir — SMB relay ile lateral hareket / DCSync provası:** Zorlanan bir yönetici veya makine kimliği, hedef bir üye sunucuya SMB ile relay edilir (`ntlmrelayx -t smb://host -c ...`). Burada zincir: coercion (A) → hedefte **4624 Logon Type 3, NTLM**, kaynak IP saldırgan kutu (B) → hemen ardından hedefte servis oluşturma (**Event 7045** / 4697) veya `ADMIN$`/`C$` üzerinden dosya yazımı ve uzak komut çalıştırma (C). Relay edilen kimlik yeterince ayrıcalıklıysa, saldırgan DC'ye yönelip **DCSync** dener; bunun imzası DC üzerinde beklenmedik bir prensipalden gelen **Event 4662** — `Properties` alanında `DS-Replication-Get-Changes` / `Get-Changes-All` GUID'leriyle dizin replikasyon erişimidir. 4662'deki bu replikasyon GUID'i, meşru olmayan bir hesaptan geldiğinde tek başına kritik alarmdır; coercion penceresiyle birleşince relay kaynaklı ayrıcalık yükseltmenin kanıtı olur. Yine desen aynı: kimliğin ait olmadığı bir kaynaktan gelip ait olmadığı bir yetkiyi kullanması.

**Zinciri kuran anahtar prensip:** Ortada bir **makine hesabının** (`$` ile biten) beklenmedik bir servise (ADCS HTTP, LDAP write, MSSQL) kimlik doğrulaması + **kısa zaman penceresi** + **kimlik istismarının artefaktı** (5136 öznitelik yazımı, 4886/4887 sertifika, anormal 4768/4769) varsa, relay'i tek olaydan değil, bu üçlüden okursunuz. SIEM tarafında bunu `transaction`/`sequence` (Splunk) veya korelasyon kuralı (Sentinel `Analytics rule`, Elastic EQL `sequence by`) ile prensipal (kullanıcı/makine adı) üzerinden bağlarsınız.

---

## 4. False positive gerçeği ve triage yargısı

Relay alarmlarının çoğu, ilk bakışta panikletir ama meşru altyapıdır. Kıdemli analistin işi, "NTLM gördüm" ile "relay oldu" arasını ayırmaktır. Gerçek ortamda bu alarmları meşru üreten başlıca kaynaklar:

- **SCCM/ConfigMgr:** İstemci envanteri ve dağıtım için doğal olarak çok-hedefli NTLM ve sistem hesabıyla erişim üretir. "Bir sunucu birçok istemciye NTLM" desenini birebir taklit eder.
- **Vulnerability scanner'lar (authenticated scan):** Nessus/Qualys/Rapid7, tarama penceresinde tek kaynaktan yüzlerce hedefe NTLM/SMB oturumu açar. Zamanlanmış tarama saatleriyle örtüşen "relay benzeri" spike'lar neredeyse her zaman budur.
- **Yedekleme yazılımları (Veeam, CommVault, NetBackup):** Servis hesaplarıyla çok sayıda sunucuya kimlik doğrular; bazıları makine/servis hesaplarıyla NTLM kullanır.
- **DFS/DFSR, yazıcı sunucuları, dosya sunucusu tarayıcıları:** MS-RPRN/MS-DFSNM RPC çağrıları PetitPotam/PrinterBug ile **aynı RPC arayüzlerini** kullanır — yani coercion tespitiniz meşru yazıcı yönetimiyle çakışır.
- **Zayıf uygulamalar / eski sistemler:** Hâlâ NTLM'e düşen legacy uygulamalar, "makine hesabı NTLM" satırlarını doğal olarak üretir.

**Kıdemli analistin triage sırası — çoklu alarmda önce neye bakar:**

1. **Kimlik + zaman penceresi çapası.** Önce "hangi prensipal, hangi 60-120 saniye" sorusuna bakar. Tek bir hesap etrafında A+B+C toplanıyor mu, yoksa dağınık, farklı hesaplar, dakikalar arası mı? Dağınıksa gürültü lehine ağır basar.
2. **İstismar artefaktı var mı?** 5136'da `msDS-AllowedToActOnBehalfOfOtherIdentity` yazımı, ya da ADCS 4887 sertifika verilişi, ya da beklenmedik bir hesap için PKINIT 4768 — bunlardan biri varsa alarm bir anda gerçek olur. Bu artefaktlar scanner/yedekleme tarafından **üretilmez**. Analist önce bu "kanıt niteliğindeki" ikincil olaya koşar.
3. **Kaynağın meşruluğu.** B'deki kaynak IP bilinen bir SCCM/scanner/yedekleme sunucusu mu? Asset envanterinde kimliği ne? Bir makine hesabı kendi IP'sinden mi geliyor yoksa bambaşka bir kutudan mı? IP-hostname eşleşmesi kopuksa relay lehine ağırlaşır.
4. **Hedefin hassasiyeti.** Hedef ADCS enrollment, DC LDAP-write ya da bir tier-0 varlık mı? Yedekleme'nin bir DC'nin `msDS-Allowed...` özniteliğini yazması için hiçbir meşru sebep yoktur. Hedef ne kadar hassassa eşik o kadar düşer.

Pratik yargı: NTLM logon sayısı **asla** birincil kanıt değildir; birincil kanıt **istismarın imzasıdır** (öznitelik yazımı, sertifika, anormal bilet). Analist gürültüyü, "bu olayın meşru bir iş açıklaması var mı, ve o açıklamayı yapan asset envanterde tanımlı mı" testiyle eler. Baseline şart: SCCM/scanner/yedekleme sunucularının kimlikleri ve tarama pencereleri allowlist olarak bilinmeli; bunlar tanımlı değilken relay tespiti kurmaya çalışmak, yanlış pozitifi peşinen kabul etmektir.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Deneyimli saldırgan, yukarıdaki zincirin her halkasını kırmaya çalışır. Kural dokümanında yazmayan atlatma yolları ve her birine ikinci-derece tespit:

**Kaçınma 1 — Araç yeniden derleme / isim değişimi.** `Generic Process Access` ve `CoercedPotato pipe` kuralları isim tabanlıdır; saldırgan ikilileri yeniden adlandırıp özel pipe adı kullanır. **Karşı-tespit:** İsim yerine **davranışa** in. Pipe adına değil, pipe **oluşturan sürecin bağlamına** bak — `spoolsv.exe` veya bir servis sürecinin beklenmedik bir named pipe'ı impersonation için açması, ya da SYSTEM'e yükselen bir token manipülasyonu (Event 4673/4674 hassas ayrıcalık kullanımı). Relay'in aktif ucu Linux'ta olsa da, **potato** ailesi lokal privilege escalation için kurban Windows'ta çalışır; oradaki token impersonation + hemen ardından SYSTEM olarak network logon davranışı isimden bağımsızdır.

**Kaçınma 2 — Coercion imzasını gizleme.** DNS/SPN spoofing kuralları (`5588576c`, `e7a21b5f`) çok spesifik bir base64 imzayı (`1UWhRCAAAAA..BAAAA`) arar. Saldırgan `CREDENTIAL_TARGET_INFORMATION` yapısını farklı marshalling ile ya da farklı coercion vektörüyle (EFSRPC yerine DFSNM) üretirse imza tutmaz. **Karşı-tespit:** İmza yerine **etkiye** in — coercion'ın sonucu her zaman aynıdır: bir makine hesabının beklenmedik bir dış hedefe outbound NTLM'i. Coercion vektörünü değil, "makine hesabı → beklenmedik hedef NTLM auth" olgusunu izle. Ayrıca RPC arayüz düzeyinde: `EfsRpcOpenFileRaw`, `MS-DFSNM NetrDfsRemoveStdRoot` gibi çağrıların uzak, kimliği doğrulanmış bir kaynaktan gelmesi (RPC firewall / RPC event telemetrisi ile) — imzadan bağımsız zorlama göstergesidir.

**Kaçınma 3 — Kerberos'a kayma / relay'i "ağ dışına" alma.** "NTLM reflection is dead" sınıfı işin gösterdiği gibi, savunmalar NTLM'i kısınca saldırgan Kerberos coercion + relay varyantlarına (CVE-2025-33073) geçer. **Karşı-tespit:** Sadece NTLM'e (4776, `AuthenticationPackage=NTLM`) bağımlı kalma. Anormal Kerberos desenlerini de izle: bir makine hesabının kendisi için PKINIT ile TGT alması, `Ticket Encryption Type` anomalileri, S4U akışlarındaki (4769) beklenmedik `Transited Services`. Relay hangi protokole kayarsa kaysın, **kimliğin yanlış makinede kullanılması** artefaktı kalır.

**Kaçınma 4 — Zaman penceresini yayma.** Saldırgan A ve C arasına gecikme koyarak korelasyon penceresini (60-120 sn) delmeye çalışır. **Karşı-tespit:** Çapayı zamana değil **kimliğe** taşı. Zincirini "aynı prensipal için, aynı oturum/hedef bağlamında" kur; pencereyi geniş tut ama düşük-gürültülü çapaya (5136 öznitelik yazımı, 4887 sertifika) demirle. Nadir olayı çapa yaptığında geniş pencere false positive üretmez.

**Kaçınma 5 — `curl -u :` tarzı sessiz hash sızması.** Verilen *NTLM Hash Leak Via Curl* kuralının (id `916eb839-...`) yakaladığı gibi, saldırgan Microsoft'un SSPI destekli curl'ünü boş kimlikle (`-u :`) kullanıp mevcut oturumun NTLMv2 challenge-response'unu saldırgan sunucuya sızdırabilir — parola gerekmeden, LSASS'tan. **Karşı-tespit:** Bu davranış `curl.exe` komut satırında `--ntlm` + boş kimlik olarak process creation (**Event 4688** / Sysmon **Event 1**) telemetrisinde görünür. Ama saldırgan başka bir SSPI istemcisi kullanırsa curl imzası tutmaz; ikinci derece olarak, **iç bir hostun dış/beklenmedik bir sunucuya outbound SMB/HTTP-NTLM'i** (challenge-response'un gittiği yer) ağ tarafında yakalanmalı. Yani host imzası kaçarsa network akışı çapa olur.

**Kaçınma 6 — SMB imzalama/EPA'yı görünüşte "gerektirmeyen" hedefleri seçmek.** Savunma tarafı SMB signing, LDAP channel binding ve EPA (Extended Protection for Authentication) zorunlu kıldıkça, saldırgan relay için bu korumaların hâlâ kapalı olduğu **niş hedeflere** kayar: eski MSSQL, korumasız HTTP endpoint'ler, imzalama zorlanmamış üçüncü parti servisler. **Karşı-tespit:** Konfigürasyon zafiyetini bir **hunting** girdisi olarak kullan — hangi hedeflerde signing/EPA kapalıysa oralar relay için "sıcak nokta"dır; bu varlıklara gelen makine-hesabı NTLM'ini düşük eşikle izle. Yani tespiti sadece olaya değil, **saldırı yüzeyinin haritasına** bağla: nerede relay mümkünse, oraya bakışı sıklaştır.

Genel ilke: her atlatma bir imzayı kırar ama **saldırının değişmez etkisini** kıramaz — bir kimliğin, ait olmadığı bir kaynaktan, ait olmadığı bir hedefe kullanılması. Tespiti imzadan etkiye taşıdıkça kedi-fare senin lehine döner.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** 4624'te SMB relay için `IpAddress`/`IpPort` sık sık `-` gelir; buna "kaynak IP eşleşmesi" kuralı kurmak boşa çıkar. Makine hesaplarını ayıklarken `TargetUserName` `$` ile biter — ama bazı normalleştirme pipeline'ları `$`'ı düşürür; ham alanı koru. `AuthenticationPackageName` "NTLM" ile "NTLM V1/V2" arasında ürüne göre değişir; eşitlik yerine `contains` kullan. ADCS enrollment izlemek için IIS logları (`certsrv` sanal dizini, `cs-username`, `cs-method`) ile 4886/4887'yi birlikte çekmen gerekir — 4887 default gelmez, **CA denetim ayarlarında** "Issue and manage certificate requests" auditing'i açık olmalı.

**Varsayılan loglanmayanlar — açık olması ŞART olanlar:**
- **5136** (dizin nesnesi değişimi) `msDS-AllowedToActOnBehalfOfOtherIdentity` için: DC üzerinde **Directory Service Changes** SACL'ı ilgili nesne/öznitelik üzerinde ayarlı olmalı; yoksa RBCD yazımını hiç görmezsin. Bu, LDAP relay tespitinin belkemiğidir ve default kapalıdır.
- **CoercedPotato/pipe** kuralı için Sysmon **Event ID 17/18** açık olmalı — SwiftOnSecurity/Neo23x0/olafhartong config'lerinde var ama pipe filtreleri sıkıysa düşer; kuralın çalışması config'e bağımlıdır (kuralın kendi `definition` notu da bunu söyler).
- **4688** komut satırı ile (curl NTLM tespiti için): "Include command line in process creation events" GPO'su açık olmalı; kapalıysa `-u :` argümanını göremezsin, sadece `curl.exe` çalıştığını görürsün — ki o tek başına anlamsızdır.
- ADCS **4886/4887** için CA-tarafı denetim; ve NTLM görünürlüğü için **4776** (yalnızca DC/authenticator üzerinde üretilir, üye sunucuda değil).

**Platform farkları:**
- **Splunk:** Korelasyonu `transaction principal maxspan=120s` veya daha kontrollü `| streamstats`/subsearch ile kur; `transaction`'ın pahalı olduğunu unutma, büyük ortamda hedefe (makine hesabı auth) daraltıp sonra birleştir. Data Model / CIM `Authentication` node'unda NTLM alanları normalize olur ama ham `Signature_ID`'yi kaybetme.
- **Microsoft Sentinel:** Bu iş için doğal yerdir çünkü **Defender for Identity (MDI)** zaten "Suspected NTLM relay", "Suspected DCSync", coercion ve RBCD için hazır alertler üretir; UEBA + `SecurityEvent`/`IdentityDirectoryEvents` tablolarını KQL ile birleştirip A+B+C zincirini kur. `SecurityEvent | where EventID in (4624,4768,4769,5136)` + MDI alertleriyle join, en verimli yol. Sadece MDI'ya güvenme; kendi korelasyonunu üstüne koy.
- **Elastic:** **EQL `sequence by user.name with maxspan=2m`** tam bu zincir için tasarlanmıştır: coercion/auth olayı → 5136 öznitelik yazımı → anormal Kerberos, prensipal üzerinden dizilir. ECS'de Windows event alanları `winlog.event_data.*` altında kalır; `TargetUserName` → `winlog.event_data.TargetUserName`, normalize edilmiş `user.name`'e körü körüne güvenme.

**Tuning gerçeği.** Baseline olmadan hiçbir relay kuralı ayakta kalmaz. Önce 2-4 hafta SCCM/scanner/yedekleme sunucularının kimlik ve IP'lerini, tarama pencerelerini topla; bunları allowlist yap. Coercion RPC kurallarını yazıcı/DFS sunucularının IP'leriyle çakıştığı için mutlaka bu bağlamla filtrele (meşru yazıcı yönetimi PrinterBug'la aynı arayüzü kullanır). Düşük-gürültülü çapaları (5136 `msDS-Allowed...`, ADCS 4887 anormal şablon, makine hesabı PKINIT) yüksek öncelikli ve **suppress etmeden** tut; yüksek-gürültülü davranışsal kuralları (NTLM logon sayısı) yalnızca çapa tetiklendiğinde **enrichment** olarak kullan, birincil alarm yapma. Kural olgunlaştıkça mantığı imzadan (araç adı, base64 string) etkiye (kimliğin yanlış yerde kullanımı) kaydır — imza kuralları tespit değeri için değil, hızlı triyaj etiketi için vardır.

**Son söz.** NTLM relay tespiti bir kural değil, bir **hipotezdir**: "bir kimlik, ait olmadığı bir yolla taşınıp ait olmadığı bir hedefte kullanıldı." Naif 4624 avı bu hipotezi test etmez; test eden şey, zorlama-aktarım-istismar üçlüsünü aynı kimlik etrafında demirlemek ve istismarın nadir, taklit edilemez artefaktını (öznitelik yazımı, sertifika, anormal bilet) çapa yapmaktır. Görünürlük eksikse (5136 SACL kapalı, 4688 komut satırı kapalı, MDI yok) en iyi kural bile kördür — önce telemetriyi kur, sonra korelasyonu.
