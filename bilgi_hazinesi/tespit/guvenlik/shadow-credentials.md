# Shadow Credentials (msDS-KeyCredentialLink) — Tespit

## 1. Özet: saldırı + naif tespit (KISA)

Shadow Credentials, bir Active Directory nesnesinin (kullanıcı veya bilgisayar hesabı) `msDS-KeyCredentialLink` özniteliğine saldırganın kontrol ettiği bir açık anahtar sertifikasının (KeyCredential / NGC — Next Generation Credentials yapısı) yazılmasıdır. Bu öznitelik normalde Windows Hello for Business ve FIDO2 anahtarsız kimlik doğrulaması için kullanılır: cihaz üzerinde üretilen anahtar çiftinin açık kısmı DC üzerinde nesnenin bu özniteliğinde tutulur, özel kısım TPM'de kalır. Saldırgan bu mekanizmayı istismar ederek kendi ürettiği anahtar çiftinin açık kısmını hedef nesneye ekler; ardından PKINIT üzerinden Kerberos ile kimlik doğrulaması yapıp o hesabın TGT'sini ve `AS-REP` içinden NTLM hash'ini (`NTLM_SUPPLEMENTAL_CREDENTIAL`) elde eder. Sonuç: parola bilmeden, parola sıfırlamadan, kalıcı ve "meşru" görünen bir kimlik ele geçirme.

Ön koşul: hedef nesne üzerinde `GenericWrite`, `GenericAll`, `WriteProperty` veya `msDS-KeyCredentialLink` üzerinde yazma yetkisi. Yani Shadow Credentials aslında bir yetki yükseltme değil, elde edilmiş bir yazma yetkisini tam hesap ele geçirmeye çeviren bir **DACL istismarı primitifidir**. Whisker, pyWhisker, Certipy `shadow auto`, ntlmrelayx `--shadow-credentials`, DSInternals `Set-ADComputer`/`Add-ADComputerKeyCredential` benzeri araçlarla yapılır. ADCS ESC8 / RemoteKrbRelay gibi relay saldırılarıyla zincirlenmesi çok yaygındır.

Naif tespit: "Directory Service Changes ile `msDS-KeyCredentialLink` değişince alarm bas." Somut olarak **Event ID 5136** (bir dizin nesnesi değiştirildi) içinde `LDAP Display Name: msDS-KeyCredentialLink` ve `Type: Value Added`. `Possible Shadow Credentials Added` (id: f598ea0c-c25a-4f72-a219-50c44411c791) kuralının yaptığı tam olarak budur. Kulağa temiz gelir — ama sahada tek başına ya susar ya da boğar.

## 2. Naif tespit neden yetmez

**Kör nokta 1 — SACL yoksa 5136 hiç doğmaz.** Bu en büyük ve en sessiz kör noktadır. `Possible Shadow Credentials Added` kuralının kendi `definition` alanı bunu açıkça söyler: "Audit Directory Service Changes" politikası açık olmalı **ve olay yalnızca SACL'i yapılandırılmış nesneler için üretilir". Varsayılan bir AD ortamında `AdminSDHolder` altındaki korumalı hesaplar ve domain kökü haricinde çoğu OU/nesne için `msDS-KeyCredentialLink` yazmasını denetleyen bir SACL **yoktur**. Yani `AuditDirectoryServiceChanges` GPO'sunu açtınız diye 5136 gelmez; ilgili nesne sınıflarının SACL'ine "Write msDS-KeyCredentialLink — Success" ACE'sini ayrıca eklemeniz gerekir. Bunu yapmamış SOC'lerin ezici çoğunluğunda kural teknik olarak dağıtılmıştır ama **hiçbir olay görmez** — kağıt üzerinde kapsanmış, gerçekte kör.

**Kör nokta 2 — 5136 tek başına saldırıyı değil, mekanizmayı görür.** Windows Hello for Business (WHfB) devreye alındığında her kullanıcı ilk kaydolduğunda kendi cihazından `msDS-KeyCredentialLink`'e meşru bir NGC anahtarı yazar. Yani `Value Added` olayı normalde de akar. Kural "possible" der çünkü kendisi meşru ile kötüyü ayırt edemez. WHfB kullanan bir kurumda bu olay günde binlerce kez doğar; kullanmayan bir kurumda ise neredeyse hiç doğmaz — ama o kurumda da SACL kurulmadıysa saldırı da görünmez. İki uçtan biri: ya gürültü ya sessizlik.

**Atlatma 1 — LDAP doğrudan yazma, araç imzası yok.** `Possible Shadow Credentials Added` bir `security` (5136) kuralıdır, süreç/komut satırı görmez. Saldırgan Whisker.exe çalıştırmak zorunda değil; ham LDAP ile `ldap_modify` çağırarak (pyWhisker, Impacket, hatta kendi 30 satırlık python'u) özniteliği yazabilir. Böylece process_creation tabanlı `HackTool - RemoteKrbRelay Execution` (id: a7664b14-75fb-4a50-a223-cb9bc0afbacf) veya `DSInternals Suspicious PowerShell Cmdlets` (id: 43d91656-a9b2-4541-b7e2-6a9bd3a13f4e) kurallarının hiçbiri tetiklenmez. Geriye yalnızca dizin katmanı kalır; o da SACL yoksa kör.

**Atlatma 2 — komut satırı / dosya adı kozmetiği.** `HackTool - RemoteKrbRelay Execution` kuralı `Image|endswith: '\RemoteKrbRelay.exe'` veya `OriginalFileName: 'RemoteKrbRelay.exe'` **VE** `-clsid`, `-target`, `-victim` bayraklarının hepsine bağlıdır. Saldırgan binary'i yeniden adlandırır ve PE metadata'sını (OriginalFileName) düzenlerse img seçimi çöker; kalan tek dayanak üç bayrağın birlikte görülmesidir ki bu da `process_creation` logu (Sysmon EID 1 veya 4688 komut satırı ile) yoksa görünmez. DSInternals kuralları da benzer: modül import edilmeden reflection ile yüklenirse veya cmdlet adları takma adla çağrılırsa ScriptBlock kuralı (id: 846c7a87) zayıflar.

**False positive selleri.** WHfB yaygınlaştıkça 5136 seli akar. Ayrıca Azure AD / Entra hybrid join sırasında cihaz kaydı, Intune, `certificateEnrollment` senaryoları hep bu özniteliğe dokunur. Tek başına "msDS-KeyCredentialLink değişti" alarmı, WHfB'li bir kurumda ilk gün analiste yüzlerce ticket üretir ve iki hafta içinde susturulur (mute edilir). Susturulan kural = olmayan kural.

Özet yargı: naif tespit ya **SACL boşluğu** yüzünden hiç ateşlenmez, ya **WHfB gürültüsü** yüzünden boğulur, ya da saldırgan **ham LDAP'a** kayarak process/PowerShell katmanını tümden atlar. Değer korelasyondadır.

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek güven, Shadow Credentials'ın **sıralı doğasından** gelir: önce yazma (write), sonra kısa pencerede kimlik doğrulama (PKINIT auth), çoğu zaman öncesinde bir yetki elde etme, sonrasında hemen ele geçirme kanıtı. Bu zinciri farklı loglardan farklı bağlamlarda örelim.

**Zincirin bel kemiği — A + kısa pencere B + C:**

**A) Yazma olayı (dizin katmanı):** 5136, `msDS-KeyCredentialLink`, `Type: Value Added`, `Subject` = hesap X, hedef nesne = hesap/bilgisayar Y. Bunu tek başına "possible" olarak işaretle, alarm değil — **gözlem**.

**B) Kısa pencere, FARKLI bağlam — PKINIT ile kimlik doğrulama (4768):** Yazmadan sonra dakikalar içinde, hedef nesne Y için DC'de **Event ID 4768** (bir Kerberos TGT talep edildi) gelir; kritik ayrım şudur: `Certificate Information` alanları (Certificate Issuer Name / Serial Number / Thumbprint) **dolu**, `Pre-Authentication Type = 16` (PKINIT). Yani Y hesabı parola ile değil sertifika ile kimlik doğruladı. Bir bilgisayar hesabı veya normalde WHfB kullanmayan bir servis hesabının aniden sertifika tabanlı 4768 üretmesi, üstelik dakikalar önce onun `msDS-KeyCredentialLink`'i değiştiyse — bu **korelasyonun kalbi**dir. A'daki hedef Y = B'deki `Account Name` Y ve zaman farkı < 15 dk ise güven fırlar.

**C) Ele geçirme kanıtı — TGT'nin hemen kullanımı:** B'den saniyeler/dakikalar sonra Y hesabı için hizmet biletleri (4769 — TGS talebi), özellikle DC'ye karşı `cifs/`, `ldap/`, `host/` SPN'leri veya doğrudan DCSync belirtisi (4662, `Replicating Directory Changes` GUID'i `1131f6aa-9c07-11d1-f79f-00c04fc2dcd2`). Yani: **yazma → PKINIT auth → ayrıcalıklı erişim** üç adımı aynı hesap kimliği etrafında, dar bir zaman penceresinde toplanır.

**Somut senaryo (bir bilgisayar hesabı ele geçirme):**
1. Saldırgan `SRV-APP01$` üzerinde `GenericWrite`'a sahip düşük yetkili bir kullanıcı ele geçirdi.
2. **A:** pyWhisker ile `SRV-APP01$` nesnesinin `msDS-KeyCredentialLink`'ine anahtar ekledi → 5136 Value Added (SACL varsa).
3. **B:** Certipy `shadow auto` PKINIT ile `SRV-APP01$` olarak kimlik doğruladı → 4768, PreAuth=16, Certificate Info dolu, `Account Name: SRV-APP01$`.
4. **C:** Elde edilen TGT ile bu makinenin NTLM hash'i alındı; makine RBCD veya S4U2Self üzerinden bir yönetici olarak taklit edildi → 4769 `cifs/DC01`.
5. **Kapatma sinyali (opsiyonel ama altın):** Saldırgan izi silmek için eklediği KeyCredential'ı kaldırır → ikinci bir 5136, aynı öznitelikte `Type: Value Deleted`, dakikalar sonra. Add + kısa süre sonra Delete deseni tek başına neredeyse hiçbir meşru WHfB akışında görülmez.

**Neden bu zincir WHfB gürültüsünü yener:** Meşru WHfB'de A (yazma) bir **kullanıcı** hesabına, o kullanıcının **kendi oturumundan**, iş istasyonundan gelir ve arkasından o kullanıcının rutin PKINIT girişleri akar. Saldırıda A çoğu zaman **bilgisayar hesabına** veya bir **servis hesabına** gelir, `Subject` (yazan) ile hedef (yazılan) **farklıdır** (kullanıcı X, makine Y'ye yazıyor), ve B'deki PKINIT o nesne için **ilk kez** görülür. "Farklı özne bir başka nesnenin KeyCredential'ını yazdı + o nesne ilk kez PKINIT ile auth oldu + hemen ayrıcalıklı TGS" — bu birleşim meşru trafikte pratikte yoktur.

**İkinci korelasyon ekseni — araç + dizin:** `DSInternals Suspicious PowerShell Cmdlets` (43d91656) veya `HackTool - RemoteKrbRelay Execution` (a7664b14) process/ps_script katmanında ateşlerse ve **aynı host'tan / aynı özneden** dakikalar içinde bir 5136 `msDS-KeyCredentialLink` yazması gelirse, düşük-güvenli iki sinyal birleşerek yüksek-güvenli tek olguya dönüşür. RemoteKrbRelay özellikle önemli: `-adcs` ile relay edip sertifika alır, sonra shadow credential yazabilir — yani relay tespiti (a7664b14) Shadow Credentials'ın **ön habercisi** olarak korele edilmelidir.

## 4. False positive gerçeği ve triage yargısı

Sahada `msDS-KeyCredentialLink` yazan meşru aktörler nettir; bunları tanımak triyajın yarısıdır:

- **Windows Hello for Business kaydı:** En büyük FP kaynağı. Kullanıcı kendi hesabına, kendi oturumundan yazar. Özne = hedef, kaynak host = kullanıcının cihazı. WHfB'li kurumda bu **beklenen** akıştır.
- **Azure AD / Entra Hybrid Join & cihaz kaydı:** `AzureADSSOACC$`, cihaz nesneleri, Intune kayıt süreçleri bu özniteliğe dokunabilir.
- **SCCM / Configuration Manager, yedekleme ve DC provizyon araçları:** Bazı otomasyonlar bilgisayar nesnelerini toplu günceller; KeyCredential'a genelde dokunmasalar da toplu 5136 akışı yaratır ve gürültüye katkı verir.
- **Güvenlik tarayıcıları (BloodHound/SharpHound, ADCS denetimleri, PingCastle, Purple Team):** Bunlar okur, nadiren yazar; ama yazma testi yapan pentest pencerelerinde meşru "saldırı gibi görünen" aktivite üretirler — değişiklik/onay bileti (change ticket) ile eşleştirilmeli.

**Analistin öncelik sırası (triyaj yargısı):**

1. **Hedef nesne türü ve KTLO bağlamı.** Hedef bir **bilgisayar hesabı** veya **ayrıcalıklı/servis hesabı** mı? Evet ise öncelik yüksek — WHfB tipik olarak son-kullanıcı kullanıcı hesaplarına yazar, makine hesaplarına değil. Hedef `Domain Admins`, `krbtgt`, DC hesabı, `AdminSDHolder` korumalı hesap ise **kritik**, anında.
2. **Özne ≠ hedef mi?** Yazan hesap (Subject) ile yazılan nesne farklıysa (delegasyon zinciri) meşru WHfB olma olasılığı düşer. Aynıysa ve kullanıcı kendi cihazından yazıyorsa büyük ihtimalle WHfB.
3. **Kaynak host.** Yazma bir DC'den, bir jump host'tan, bir Kali/pentest VLAN'ından ya da beklenmedik bir sunucudan mı geliyor? Kullanıcının kendi iş istasyonundan mı? Kaynak, sınıflandırmayı hızla ikiye böler.
4. **B ekseni var mı?** Yazmadan sonra dar pencerede o nesne için sertifika tabanlı **4768 (PreAuth 16)** doğdu mu? Doğduysa "possible" anında "probable"a çıkar. Bu, tek en güçlü doğrulama adımıdır.
5. **Add→Delete deseni.** Aynı özniteliğe kısa aralıkla Value Added sonra Value Deleted geldiyse — bu neredeyse her zaman kötü niyetli iz temizlemedir, meşru WHfB anahtarları böyle kısa ömürlü olmaz.
6. **WHfB devrede mi?** Kurum WHfB kullanmıyorsa **her** `msDS-KeyCredentialLink` yazması varsayılan olarak yüksek önceliklidir — çünkü meşru zemin yoktur. Bu tek bilgi, triyaj eşiğini kökten değiştirir; bu yüzden ortam bilgisi (WHfB var/yok) alarm zenginleştirmesine gömülmelidir.

Pratik kural: WHfB'siz ortamda `msDS-KeyCredentialLink` yazması → P2/P1. WHfB'li ortamda → yalnızca (hedef makine/ayrıcalıklı) VEYA (özne≠hedef) VEYA (arkasından PKINIT 4768) varsa yükselt; aksi halde baseline'a gönder.

## 5. Kaçınma → karşı-tespit

Saldırganın belgede yazmayan, sahada işe yarayan atlatmaları ve her birine ikinci-derece tespit:

**Atlatma A — Ham LDAP ile yazma, hiçbir araç imzası bırakmama.** Whisker/DSInternals çalıştırmadan doğrudan `msDS-KeyCredentialLink`'e `ldap_modify` ile yazmak process ve ps_script kurallarını tümden atlar.
→ **Karşı-tespit:** Dizin katmanı burada tek gerçek gözdür. 5136'yı hedef nesne SACL'i ile **gerçekten** üretmek şart (bkz. §6). Ek olarak DC'ye gelen LDAP yazma trafiğini (`ldap` service) ağdan görüyorsanız, `msDS-KeyCredentialLink` yazan ham LDAP oturumlarını kaynak IP ile eşleştir. LDAP imzalama/kanal bağlama (channel binding) zorunluysa anonim/relay yazmalar da kırılır.

**Atlatma B — İz temizleme (KeyCredential silme).** Auth'tan sonra saldırgan eklediği anahtarı kaldırır, böylece bir sonraki denetimde öznitelik "temiz" görünür.
→ **Karşı-tespit:** 5136 `Value Deleted` olayını da yakala; **Add→Delete kısa-pencere desenini** ayrı bir korelasyon kuralı yap. Silme, meşru senaryoda nadir olduğu için silme olayının kendisi bir sinyaldir. Ayrıca `replPropertyMetaData` üzerinden özniteliğin değişiklik sürüm/zaman damgasını periyodik denetleyerek "silinmiş ama bir kez var olmuş" durumu tespit edilebilir.

**Atlatma C — Anlık kullan-at (write → auth → delete, hepsi dakikalar içinde).** Öznitelik alarmı gecikmeli işleniyorsa saldırgan pencereyi o kadar daraltır ki analist baktığında ortada kanıt kalmaz.
→ **Karşı-tespit:** Tespiti öznitelik durumuna değil **olay akışına** dayandır — silinmiş olsa bile Add olayı log'da kalır. B eksenini (4768 PreAuth 16) mutlaka koru: anahtar silinse de kimlik doğrulama olayı DC'de durur.

**Atlatma D — Relay ile ADCS'den sertifika (RemoteKrbRelay `-adcs`, ntlmrelayx ESC8).** Saldırgan bazen KeyCredential yazmak yerine relay ile doğrudan sertifika alır; ya da makine hesabını relay edip onun adına shadow credential yazar. Belge dışı incelik: RemoteKrbRelay `-laps` ile LAPS parolası da çekebilir.
→ **Karşı-tespit:** `HackTool - RemoteKrbRelay Execution` (a7664b14) img/CLI imzasına ek olarak, ADCS tarafında **4886/4887** (sertifika talebi/verilişi) olaylarını, makine hesabı adına gelen ve `SAN` (Subject Alternative Name) ile başka bir principal isteyen talepleri izle. Relay → sertifika → PKINIT → shadow zinciri aynı dar pencerede korele edilmeli.

**Atlatma E — DSInternals'ı reflection ile yükleme / cmdlet gizleme.** Modülü `Import-Module` ile değil, assembly'i bellekten reflection ile yükleyip ScriptBlock imzasını zayıflatma.
→ **Karşı-tespit:** `DSInternals ... ScriptBlock` (846c7a87) tek başına yetmeyeceğinden, .NET assembly yükleme telemetrisi (Sysmon EID 7 — Image/Module Load, `DSInternals.*.dll`), AMSI ScriptBlock ve yine dizin katmanı ile üçgenleme yap. Tek katmana asla güvenme.

Genel karşı-tespit yargısı: saldırganın atlatabildiği her katman (process, ps_script) için **dizin katmanı (5136 + 4768 PKINIT)** son savunma hattıdır; bu yüzden asıl mühendislik yatırımı SACL'i doğru kurmaya ve PKINIT auth'unu izlemeye gitmelidir, araç imzalarına değil.

## 6. SIEM / saha gerçeği

**Alan eşlemesi (field mapping) — 5136 (Directory Service Changes):**
- `LDAP Display Name` → `msDS-KeyCredentialLink` (kuralın çekirdek seçimi; `Possible Shadow Credentials Added` bunu kullanır).
- `Operation Type` / `Type` → `Value Added` (%%14674) veya `Value Deleted` (%%14675) — silme desenini de al.
- `Object DN` / `DSName` → hedef nesne (kullanıcı mı makine mi ayrımı burada).
- `Subject: Security ID / Account Name` → yazan (özne ≠ hedef testi).
- `Attribute Value` → NGC yapısının kendisi; genelde ham/uzun, içerik bazlı ayrıştırma zordur, o yüzden metadata ile karar verilir.

**Alan eşlemesi — 4768 (Kerberos TGT):**
- `Certificate Issuer Name` / `Certificate Serial Number` / `Certificate Thumbprint` → doluysa PKINIT/sertifika tabanlı auth. Boşsa parola.
- `Pre-Authentication Type` → `16` = PKINIT. Shadow Credentials sonrası auth burada görünür.
- `Account Name` → kimin TGT'si. A'daki hedef ile eşle.

**Varsayılan loglanmayan — en kritik saha gerçeği:**
1. **5136 varsayılan üretilmez.** İki katman gerekir: (a) GPO'da `Computer Configuration → Advanced Audit Policy → DS Access → Audit Directory Service Changes = Success`; (b) hedef nesne sınıflarının (User, Computer) **SACL'ine** `msDS-KeyCredentialLink` (veya "Write all properties") için `Success` denetim ACE'si. Sadece (a)'yı açmak yaygın bir yanılgıdır — o zaman kural sessizce hiçbir şey görmez. SACL'i `AdminSDHolder` ve OU seviyesinde kalıtımla yaymak gerekir; korumalı hesaplar için `AdminSDHolder` şarttır.
2. **4768 hacimlidir ve genelde yalnızca DC'lerde doğar.** Tüm DC'lerden toplanmalı; tek DC'den toplayan SOC PKINIT eksenini kaçırır. Certificate alanlarını normalize etmeyen bir parser B eksenini kör eder.
3. **Sysmon yoksa process_creation için 4688 + "Include command line" GPO'su açık olmalı;** aksi halde `HackTool - RemoteKrbRelay` ve DSInternals process kurallarının CLI seçimleri boş alanla eşleşmeye çalışır, ateşlemez.

**Platform farkları:**
- **Splunk:** 5136 `WinEventLog:Security` üzerinden gelir; `msDS-KeyCredentialLink` çoğu zaman `Attribute_LDAP_Display_Name` alanına düşer (TA-Windows CIM eşlemesine göre alan adı değişebilir — `props/transforms` ile teyit et). Korelasyonu `transaction` yerine `stats`/`streamstats` ile hedef nesne (`Object DN`) etrafında yap; A(5136) ve B(4768) farklı `EventCode` olduğundan `| stats ... by target` ile 15 dk pencerede birleştir. `tstats` ile hacmi düşür.
- **Microsoft Sentinel:** `SecurityEvent` tablosunda `EventID == 5136` ve `AttributeLDAPDisplayName == "msDS-KeyCredentialLink"`. Daha iyisi **`IdentityDirectoryEvents`** (Defender for Identity) — MDI'nin yerleşik "Shadow Credentials" / "Suspected DCSync" analitikleri PKINIT ve KeyCredential'ı zaten korele eder; MDI varsa ham 5136 avcılığına ek olarak onu birincil sinyal yap. KQL `join kind=inner` ile 5136 (A) ve 4768 (B) `TargetAccount` üzerinden `time window` ile birleştirilir.
- **Elastic:** `Possible Shadow Credentials Added` kuralının referansladığı Elastic Security kuralı ECS'te `winlog.event_id: 5136` ve `winlog.event_data.AttributeLDAPDisplayName: msDS-KeyCredentialLink` kullanır. EQL `sequence by winlog.event_data.ObjectDN with maxspan=15m` ile A→B zinciri doğal biçimde ifade edilir; Elastic'in dizi (sequence) motoru bu çok-aşamalı deseni Splunk'tan daha temiz kurar.

**Tuning yargısı:**
- WHfB'li ortamda 5136'yı **baskılama** (allowlist) değil **zenginleştirme** ile yönet: hedef nesne türü, özne=hedef mi, kaynak host, WHfB kayıtlı mı bilgisini alarm bağlamına ekle; kör susturma yerine önceliklendir.
- Yüksek güveni **korelasyona** rezerve et (A + 15dk pencerede B PKINIT). Tek başına 5136'yı P1 yapma (WHfB'liyse), tek başına 4768 PKINIT'i de yapma (meşru WHfB girişleri var). İkisinin dar pencerede aynı hedefte buluşması gerçek eşiktir.
- Makine hesapları ve ayrıcalıklı hesaplar için ayrı, düşük eşikli bir kural kolu tut — bunlar için tek 5136 bile yükseltmeye değer.
- `Value Deleted` ve `Add→Delete` desenini ayrı bir düşük-hacimli, yüksek-değerli kural yap; hemen hemen hiç FP üretmez.
- MDI/Defender for Identity varsa onu birincil, ham log korelasyonunu ikincil/av (hunting) katmanı yap; yoksa SACL + PKINIT izleme zorunlu, aksi halde bu teknik ortamınızda **tespit edilemez** kabul edilmelidir — bu dürüst duruş, "kural dağıttık" yanılsamasından iyidir.

Son yargı: Shadow Credentials'ın tespiti bir kural değil, bir **veri hattı meselesidir**. SACL'i kurmadıysan `Possible Shadow Credentials Added` kuralın var ama gözü yok; PKINIT 4768'i toplamıyorsan korelasyonun bel kemiği yok; process logun yoksa araç imzaları teselli ödülü. Değer, üç katmanı (dizin yazma + PKINIT auth + araç/host bağlamı) dar bir zaman penceresinde, hedef nesne kimliği etrafında birleştirmekte ve bunu WHfB gürültüsünden özne/hedef/kaynak ayrımıyla süzmektedir.
