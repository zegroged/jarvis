# Silver Ticket — Tespiti

## 1. Özet: saldırı + naif tespit

Silver Ticket, Kerberos'un yapısal bir güven varsayımını sömüren bir saldırıdır. Kerberos'ta bir istemci bir servise (SPN'e) erişmek istediğinde KDC'den bir servis bileti (TGS — Ticket Granting Service ticket) alır. Bu biletin içindeki PAC (Privilege Attribute Certificate) ve yetki bilgileri, **servis hesabının NTLM hash'i (ya da AES anahtarı) ile şifrelenir/imzalanır**. İşte kritik nokta: servis, kendisine gelen bileti doğrularken varsayılan olarak DC'ye "bu bilet geçerli mi?" diye sormaz. Kendi anahtarıyla açabiliyorsa, biletin içindeki her şeye — kullanıcı adı, grup üyelikleri, yetki iddialarına — inanır. Golden Ticket krbtgt hesabının hash'ini gerektirirken, Silver Ticket yalnızca **tek bir servis hesabının** hash'ini gerektirir. Bu da onu daha dar kapsamlı ama çok daha sinsi yapar: saldırgan DC ile hiç konuşmadan, sadece hedef servise sahte bir bilet sunarak o servisin gözünde istediği kimliğe (çoğu zaman "Administrator" veya bir Domain Admin) bürünebilir.

Saldırganın Silver Ticket üretmesi için gereken malzeme şudur: hedef servis hesabının NTLM/AES anahtarı, domain SID'i, hedef SPN ve taklit edilecek kullanıcı adı. Bu bileşenlerin en kritiği servis hesabı hash'idir — ki bu genelde bir önceki adımda **Kerberoasting** (T1558.003) ile elde edilir. Bir servis hesabının TGS biletini KDC'den isteyip, offline olarak parolasını kırmak. İşte tam bu noktada verilen gerçek Sigma kuralları devreye girer: `Suspicious Kerberos Ticket Request via CLI` (caa9a802-8bd8-4b9e-a5cd-4d6221670219) ve `Suspicious Kerberos Ticket Request via PowerShell Script - ScriptBlock` (a861d835-af37-4930-bcd6-5b178bfb54df). Bu iki kural, `System.IdentityModel.Tokens.KerberosRequestorSecurityToken` sınıfının PowerShell veya CLI üzerinden çağrılmasını yakalar — çünkü bu .NET sınıfı, bir SPN için Kerberos bileti talep etmenin "gürültülü" ve tespit edilebilir yoludur. Kural setinin mantığı: `attack.credential-access` / `attack.t1558.003`.

Naif tespit yaklaşımı şudur: "Silver Ticket kullanılınca sahte bilet üretilir, o zaman anormal bilet aktivitesini ara." Ama burada büyük bir tuzak var — **Silver Ticket üretiminin kendisi hiçbir log üretmez.** Bilet offline, saldırganın makinesinde (genelde domain dışında, mimikatz veya Rubeus ile) forge edilir. Verilen Sigma kuralları aslında Silver Ticket'ın *forge* adımını değil, ona giden yoldaki **bilet talebi / Kerberoasting** adımını yakalar. Bu ayrımı anlamayan analist, "kural var, kapsandık" yanılgısına düşer. Gerçek tespit mühendisliği burada başlar.

## 2. Naif tespit neden yetmez

Silver Ticket tespitinin en büyük kör noktası şudur: **saldırının kalbi olan bilet üretimi ağdan ve loglardan görünmez.** Saldırgan servis hesabının hash'ine sahipse, kendi kontrolündeki bir makinede (hatta çalışma grubundaki, domaine üye olmayan bir Linux kutusunda) Rubeus veya mimikatz ile TGS'i forge eder. KDC'ye TGS-REQ gitmez, dolayısıyla DC'de **Event ID 4769** (Kerberos service ticket requested) üretilmez. Naif "4769'ları izle" yaklaşımı Silver Ticket'ın forge aşamasını tümüyle ıskalar. Sadece sahte biletin *kullanıldığı* an, yani servise erişildiği an bir iz kalır — o da servis sunucusunun kendi loglarında, ve orada bile açıkça "sahte bilet" yazmaz.

Verilen Sigma kurallarına gelince: bunlar `KerberosRequestorSecurityToken` sınıfının çağrılmasını arar. Bu son derece dar bir imzadır. Saldırgan bilet talebini bu .NET sınıfıyla değil, `Rubeus.exe kerberoast`, Impacket'in `GetUserSPNs.py`'si, ya da doğrudan `setspn` + native LDAP sorgusu ile yaparsa, PowerShell ScriptBlock veya CLI imzası hiç tetiklenmez. Kural `ps_script` logsource'una (Script Block Logging) bağımlı — eğer Script Block Logging kapalıysa (birçok ortamda varsayılan kapalı veya sadece "warning level" açık), kural kör olur. CLI varyantı ise komut satırı loglamasına (Sysmon Event ID 1 veya 4688 command line) bağımlıdır; bu da default olarak Windows'ta komut satırı argümanlarını loglamaz.

İkinci kör nokta: **PAC doğrulaması varsayılan olarak kapalıdır.** Silver Ticket'ın işe yaramasının temel sebebi, çoğu servisin PAC validation'ı KDC'ye sormamasıdır. `ValidateKdcPacSignature` / KB5008380 sonrası sıkılaştırmalar gelse de birçok legacy servis ve yanlış yapılandırılmış ortamda servis, biletin PAC imzasını DC ile teyit etmez. Yani sahte bilet, servise sunulduğunda "geçerli" görünür ve hiçbir uyarı üretmez. Bu, tespiti event tabanlı değil, **davranış ve korelasyon tabanlı** olmaya zorlar.

False positive tarafı da naif yaklaşımı boğar. `KerberosRequestorSecurityToken` sınıfı yalnızca saldırganlar tarafından değil, meşru uygulama testleri, SPN doğrulama scriptleri, bazı monitoring araçları ve geliştirici test kodları tarafından da kullanılır. Kerberoasting benzeri desenler ise SCCM, yedekleme yazılımları ve vulnerability scanner'lar tarafından **her gün** üretilir. "Bilet talebi gördüm, alarm bas" diyen bir SOC, günde yüzlerce meşru 4769 içinde boğulur ve gerçek olanı kaçırır. Naif tespitin başarısızlığının özü: sinyal tek başına düşük entropili — asıl değer sinyalleri zaman ve bağlam içinde bağlamakta.

## 3. Korelasyon zinciri (asıl değer)

Silver Ticket tek bir event'e bakarak yakalanmaz. Onu yüksek güvenli tespite çeviren şey, saldırının **öncesini, forge anını ve sonrasını** bir zincir olarak görmektir. Detection engineer'ın işi tam olarak burada başlar.

**Zincirin başı — Kerberoasting sinyali (A):** Silver Ticket için servis hesabı hash'i lazım ve bu genelde Kerberoasting ile gelir. DC'de anormal 4769 deseni: tek bir kaynak hesabın, kısa bir pencerede (örn. 60 saniye), **çok sayıda farklı SPN için** ve özellikle **RC4 şifrelemesiyle** (Ticket Encryption Type `0x17`) TGS talep etmesi. RC4 talebi kırmızı bayraktır çünkü AES yerine RC4 istemek, offline kırma için parolayı daha zayıf hash'e zorlama girişimidir. Buna verilen Sigma kurallarındaki `KerberosRequestorSecurityToken` tabanlı ps_script/CLI sinyalini de ekleyin: eğer aynı hosttan hem Script Block'ta bu .NET sınıfı çağrısı, hem de DC'de toplu RC4 4769 deseni görüyorsanız, bu artık "birileri Kerberoasting yapıyor" için yüksek güvenli bir eşleşmedir.

**Zincirin ortası — sessizlik penceresi:** Kerberoasting'ten sonra saldırgan offline kırma yapar. Bu saatler-günler sürebilir ve **hiç log üretmez.** Detection açısından bu, "aynı servis hesabı için gelecekteki anormallikleri işaretle" watchlist mantığı gerektirir. Kerberoast edilen SPN'lerin listesini bir lookup/watchlist'e koyun; o servis hesabına ait gelecekteki erişimler artık yüksek öncelikli izlemede.

**Zincirin sonu — sahte biletin kullanımı (B ve C):** Silver Ticket kullanıldığında en güçlü sinyal, servis erişim logu ile DC bilet logu arasındaki **tutarsızlıktır.** Meşru bir erişimde sıralama şudur: kullanıcı DC'den TGT alır (4768), sonra hedef SPN için TGS alır (4769), sonra servise erişir (hedef sunucuda 4624 logon, logon type 3). Silver Ticket'ta ise **ortadaki 4769 YOKTUR** — çünkü bilet forge edilmiştir, KDC'ye hiç gidilmemiştir. Yani: hedef servis sunucusunda "Kullanıcı X, Kerberos ile logon oldu" (4624, Authentication Package = Kerberos) görüyorsunuz, **ama DC tarafında o kullanıcı için o SPN'e karşılık gelen bir 4769 kaydı yok.** İşte altın korelasyon budur ve Google tek sayfada bunu vermez.

Somut zincir örneği: **A** (Host1'de Script Block'ta `KerberosRequestorSecurityToken` + DC'de MSSQLSvc hesabı için 60 saniyede 20 farklı SPN'e RC4 4769) → sessizlik penceresi (2 gün) → **B** (SQL sunucusunda 4624, Kerberos logon, kullanıcı "Administrator", kaynak IP daha önce hiç bu servise erişmemiş bir host) → **C** (aynı oturumda DC tarafında ilgili SPN için 4769 kaydının YOKLUĞU + logon'un hemen ardından hassas veri erişimi/4672 special privileges). A + B + C birleşince bu artık düşük güvenli tekil bir sinyal değil, **kanıta yakın bir ihlal** hikâyesidir.

Ek bağlayıcı sinyal: **anomalili PAC / eski parola zaman damgası.** Forge edilen biletlerde saldırgan çoğu zaman aşırı uzun bilet ömrü (default 10 saat yerine 10 yıl — mimikatz'ın klasik varsayılanı) veya tutarsız grup üyelikleri koyar. Eğer servis PAC validation yapacak şekilde yapılandırılmışsa, DC tarafında **Event ID 4769 failure** veya PAC doğrulama hatası (System log, KDC kaynağı) görülebilir. Bunu, "servise Kerberos logon oldu ama DC'de eşleşen TGS yok" sinyaliyle birleştirmek, forge tespitinin en güçlü halidir.

Zincirin özü: hiçbir tekil event Silver Ticket demez. Ama "önce Kerberoasting deseni, sonra o hesabın SPN'ine DC'de karşılığı olmayan Kerberos logon, üstüne olağandışı kaynak ve bilet metadatası" üçlüsü birleştiğinde, olasılık uzayı meşru senaryolardan kanıta doğru çöker.

## 4. False positive gerçeği ve triage yargısı

Bu alarmları meşru üreten şeyler gerçek ve boldur. Kıdemli analistin işi, gürültüyü sinyalden ayıran bağlam sorularını hızla sormaktır.

**Kerberoasting benzeri 4769 sellerini üreten meşrular:**
- **SCCM / Configuration Manager:** Site sunucusu ve client push, düzenli olarak çok sayıda SPN'e karşı bilet talep eder. Kaynak hesap genelde bir makine hesabı (`$` ile biten) veya SCCM servis hesabıdır ve bu **süreklilik** gösterir — her gün aynı saatlerde. Silver Ticket öncesi Kerberoasting ise tipik olarak **tek seferlik burst**tir.
- **Vulnerability scanner'lar (Nessus, Qualys, Tenable):** Kimlik doğrulamalı taramalar SPN enumeration yapar ve toplu bilet ister. Kaynak IP taracı appliance'ın sabit IP'sidir — bunu bir asset lookup ile hemen elersiniz.
- **Yedekleme yazılımları (Veeam, CommVault, NetBackup):** Servis hesaplarıyla geniş erişim ister; düzenli zamanlanmış işlerdir.
- **Admin scriptleri ve `KerberosRequestorSecurityToken` kullanan meşru araçlar:** SPN doğrulama, health-check scriptleri, bazı .NET uygulamalarının bağlantı testleri bu sınıfı çağırır. Geliştirme/test ortamında bu sık görülür.

**Analistin gerçek/gürültü ayrımı için sorduğu sorular:**
1. **Kaynak hesap kim?** Makine hesabı (`HOST$`) veya bilinen bir servis hesabı mı, yoksa interaktif bir kullanıcı hesabı mı? Interaktif bir kullanıcının kısa sürede 20 SPN'e RC4 ile bilet istemesi çok daha şüphelidir.
2. **Şifreleme tipi ne?** Ticket Options / Encryption Type `0x17` (RC4) modern bir AD ortamında anomalidir — çoğu meşru trafik AES (`0x12`/`0x11`) kullanır. RC4'e düşüş güçlü bir belirteçtir.
3. **Baseline'a uyuyor mu?** Bu kaynak host daha önce bu servislere erişti mi? SCCM sunucusu için "evet, her gün". Muhasebe departmanındaki bir workstation için "hayır, hiç" — ikincisi eskalasyon.
4. **Süreklilik mi burst mü?** Zamanlanmış, tekrarlı, düzenli desen = otomasyon. Tek seferlik yoğun burst + ardından sessizlik = insan operatörü / saldırgan.

**Çoklu alarmda öncelik sırası (kıdemli yargı):**
- **P1 — Hemen:** DC'de eşleşen 4769 olmadan hedef serviste "Administrator" veya Domain Admin Kerberos logon'u (Silver Ticket *kullanımı*). Bu neredeyse hiçbir zaman meşru değildir ve zincirin sonudur.
- **P2 — Yüksek:** Interaktif/olağandışı bir kaynak hesabın RC4 ile toplu SPN bilet talebi (aktif Kerberoasting). Zincirin başı — henüz ihlal değil ama forge malzemesi toplanıyor.
- **P3 — Orta/Triage:** `KerberosRequestorSecurityToken` ScriptBlock/CLI tetiklenmesi tek başına — önce asset ve kullanıcı bağlamı toplanır, bilinen scanner/SCCM ise kapatılır.

Kritik yargı kuralı: **P2/P3 alarmını tek başına kapatmayın; watchlist'e taşıyın.** Bugünkü "muhtemelen scanner" 4769'u, iki gün sonra o hesabın SPN'ine gelen açıklanamayan Kerberos logon'la birleşince retrospektif olarak ihlal zincirinin başlangıcı olabilir. İyi SOC, tekil düşük-güvenli sinyalleri silmez — bağlamla zenginleşene kadar bekletir.

## 5. Kaçınma → karşı-tespit

Saldırganın kural dokümanında yazmayan atlatma yolları ve her birine ikinci-derece tespit:

**Kaçınma 1 — Bilet talebini `KerberosRequestorSecurityToken` yerine Rubeus/Impacket ile yapmak.** Verilen Sigma kuralları yalnızca .NET sınıfı imzasını arar. Rubeus `kerberoast` veya Impacket `GetUserSPNs.py` bu imzayı hiç tetiklemez.
*Karşı-tespit:* .NET sınıfı imzasına güvenmek yerine **DC tarafı davranış tespitine** geçin: tek kaynaktan kısa pencerede çok SPN + RC4 4769 deseni, hangi araçla yapılırsa yapılsın DC'de görünür. Ayrıca Rubeus/Impacket'in kendine has network ve process artefaktları (Rubeus'un default bilet formatı, Impacket'in SMB/DCE-RPC imzaları) EDR ve Zeek/Suricata ile yakalanabilir.

**Kaçınma 2 — RC4 yerine AES istemek (downgrade tespitinden kaçış).** Analistler RC4'e odaklanınca, olgun saldırgan AES bileti ister ve "normal" görünür.
*Karşı-tespit:* Encryption type'a değil, **hacim ve çeşitliliğe** dayanan tespit yapın: tek hesabın kısa sürede olağandışı sayıda *farklı* SPN'e bilet istemesi, şifreleme tipinden bağımsız anomalidir. AES olsa bile "20 farklı SPN / 60 saniye" baseline dışıdır.

**Kaçınma 3 — Silver Ticket'ı domaine üye olmayan makinede forge edip sadece kullanmak.** Forge hiç log üretmez; saldırgan yalnızca hedef servise sahte biletle bağlanır.
*Karşı-tespit:* Burada tek şansınız **hedef servisin kendi logu** ile DC'nin **yokluk korelasyonu**dur. Hedef serviste 4624 Kerberos logon var ama DC'de o principal+SPN için 4769 yok → forge edilmiş bilet göstergesi. Bunu operasyonel hale getirmek için servis sunucularının Security loglarını DC loglarıyla aynı SIEM'de, aynı zaman ekseninde toplamak şarttır (yoksa "yokluk" sorgusu yapılamaz).

**Kaçınma 4 — Makine hesabı SPN'i yerine bilet ömrünü ve PAC'ı "makul" ayarlamak.** mimikatz default'u 10 yıllık bilet ömrü verir; olgun saldırgan bunu düzeltip 10 saatlik normal ömür ve tutarlı grup SID'leri koyar.
*Karşı-tespit:* Bilet ömrü anomalisine güvenmeyin; bunun yerine **PAC validation'ı zorunlu kılın** (mümkün olan servislerde) ve KB5008380/KB5020805 sertleştirmelerini uygulayın. PAC imza doğrulaması açıkken forge edilmiş bilet, servis DC'ye sorduğunda başarısız olur ve System log'da KDC kaynaklı doğrulama hatası üretir.

**Kaçınma 5 — Sadece "makine hesabı" servisleri hedef almak (CIFS, HOST).** Bu SPN'lerin anahtarları makine hesabı parolasıdır; ele geçirilirse geniş erişim verir ve trafik "makinenin kendi trafiği" gibi görünür.
*Karşı-tespit:* Makine hesabı Kerberos logon'larında **kaynak-hedef tutarlılığı** arayın: `WORKSTATION1$` normalde sadece kendi oturumları için bilet üretir; başka bir hostta `WORKSTATION1$` kimliğiyle beklenmedik servis erişimi anomalidir. Makine hesaplarının parola değişim döngüsü (default 30 gün) ile de çelişir — çok eski parolayla imzalanmış bilet şüphelidir.

Genel prensip: kaçınma yollarının hepsi tek bir gerçeği paylaşır — imza tabanlı (`KerberosRequestorSecurityToken`, RC4, bilet ömrü) tespitler atlatılabilir; **davranış ve yokluk korelasyonu** (DC'de karşılığı olmayan servis logon) atlatması çok daha zordur çünkü saldırının fiziksel gerçeğinden — KDC'yi baypas etmek — kaynaklanır.

## 6. SIEM / saha gerçeği

**Loglanmayan varsayılanlar — bunlar açık olmadan tespit imkânsız:**
- **Kerberos Service Ticket Operations denetimi:** 4769 için `Audit Kerberos Service Ticket Operations` (Advanced Audit Policy, Account Logon kategorisi) DC'lerde **Success** olarak açık olmalı. Birçok ortamda bu ya kapalı ya da sadece Failure loglanıyor — o zaman Kerberoasting deseni hiç görünmez.
- **Kerberos Authentication Service denetimi:** 4768 (TGT) için `Audit Kerberos Authentication Service` açık olmalı — zincirin başındaki TGT alımını görmek için.
- **Script Block Logging:** Verilen ps_script Sigma kuralının (a861d835) çalışması için `Module Logging` değil, **Script Block Logging** (Event ID 4104) açık olmalı. Grup Politikası: `Administrative Templates > Windows Components > Windows PowerShell > Turn on PowerShell Script Block Logging`. Default kapalıdır.
- **Command line auditing:** CLI Sigma kuralının (caa9a802) çalışması için ya `Include command line in process creation events` (4688) açık olmalı, ya da Sysmon Event ID 1 devrede olmalı. Ham 4688 komut satırını default loglamaz.
- **Servis sunucusu logon logları:** Silver Ticket *kullanım* tespitinin bel kemiği olan 4624 (logon type 3, Authentication Package = Kerberos) hedef sunucularda toplanmalı. Birçok ortam sadece DC loglarını toplar, member server'ları ihmal eder — bu, forge korelasyonunu imkânsız kılar.

**Sysmon config gerçeği:** Sysmon Event ID 1 komut satırını yakalar ama config'iniz PowerShell/rundll32 gibi süreçleri hariç tutuyorsa (bazı gürültü-azaltma config'leri yapar) CLI kuralı kör kalır. Event ID 10 (ProcessAccess) ile LSASS'a erişimi izlemek, hash çalma (mimikatz) adımı için tamamlayıcıdır — Silver Ticket malzemesinin nereden geldiğini gösterir.

**Field mapping tuzakları:**
- **Ticket Encryption Type** alanı 4769'da hex string olarak gelir (`0x17`, `0x12`). Splunk'ta `Ticket_Encryption_Type`, Sentinel'de `TicketEncryptionType`, Elastic ECS'te `winlog.event_data.TicketEncryptionType`. RC4 = `0x17`, AES256 = `0x12`, AES128 = `0x11`. Bu alanı string olarak değil normalize edip karşılaştırın.
- **Service Name vs Service ID:** 4769'da `Service Name` bazen SPN'in kısa adını, bazen hesap adını verir. Silver Ticket hedefini ararken `Service Name` ve `Service ID` (SID) ikisini de eşleyin — yalnızca ada güvenmek yanıltır.
- **Account Name** DC loglarında `user@DOMAIN` formatında gelebilir; member server 4624'te ise `DOMAIN\user`. Cross-log korelasyon yaparken bu normalizasyon yapılmazsa "DC'de eşleşen 4769 yok" sorgusu yanlış pozitif verir — halbuki sadece format uyuşmuyordur.
- **Ticket Options** alanı (`0x40810000` gibi) bilet forwardable/renewable bayraklarını taşır; anomali avında faydalı ama platformlar arası kodlaması farklıdır.

**Platform farkları:**
- **Splunk:** DC ve member server loglarını `EventCode=4769` ve `EventCode=4624` üzerinden `stats` / `transaction` ile korelasyonlayabilirsiniz. "Eşleşen 4769 yok" sorgusu için `join` yerine performans nedeniyle `stats values(EventCode) by user,ComputerName` deseni ve ardından filtreleme tercih edilir. Encryption type için CIM Authentication datamodel'i tutarsız mapping yapabilir — ham field'a düşmek gerekebilir.
- **Sentinel (KQL):** `SecurityEvent` tablosunda `EventID == 4769` ile Kerberoasting deseni, `summarize dcount(ServiceName) by Account, bin(TimeGenerated, 1m)` ile burst tespiti çok temiz yazılır. Yokluk korelasyonu için `SecurityEvent | where EventID == 4624` ile `leftanti join` güçlü bir desendir — Sentinel'de forge tespitinin en pratik hali. `TicketEncryptionType == '0x17'` filtresi hazır.
- **Elastic:** ECS normalizasyonu (`winlog.event_data.*`) tutarlıdır ama Kerberos alanları için custom field extraction gerekebilir. EQL sequence sorguları (`sequence by user.name with maxspan=2d`) çok-aşamalı zinciri (Kerberoast → forge kullanımı) modellemek için idealdir — A/B/C zincirini tek sorguda ifade edebilirsiniz.

**Tuning tavsiyeleri:**
- Kerberoasting 4769 kuralını **hesap tipiyle** kırın: makine hesapları (`$` ile biten) ve bilinen servis hesapları için eşiği yükseltin veya allowlist'leyin; interaktif kullanıcılar için düşük eşik + RC4 şartı koyun.
- SCCM, scanner ve backup sunucularının kaynak IP/hesaplarını bir **asset lookup**'a koyup korelasyonda otomatik zenginleştirin — analist her alarmda elle asset aramak zorunda kalmasın.
- `KerberosRequestorSecurityToken` ScriptBlock kuralını **tek başına P1 yapmayın**; bunu DC 4769 burst'üyle korelasyon şartına bağlayın, aksi halde geliştirici test scriptleri false positive seli üretir.
- En yüksek getirili yatırım: **member server Security loglarını DC loglarıyla aynı SIEM'de toplamak.** Bu olmadan Silver Ticket'ın forge/kullanım aşaması tespit edilemez; tüm imza tabanlı kurallar yalnızca "yola giden" Kerberoasting adımını yakalar, asıl saldırıyı değil. Bu tek yatırım, tüm bu bölümdeki kuralların gerçek dünyada işe yaramasının ön koşuludur.
