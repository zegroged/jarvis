# Golden Ticket — Tespiti

> İlke: "Hırsızı tanımadan mücevheri koruyamazsın." Golden Ticket saldırısını önce kavramsal olarak anlıyoruz, sonra hangi izleri bıraktığını ve bu izleri gerçek Sigma tespit kurallarının mantığıyla nasıl yakaladığımızı işliyoruz. Amaç savunma ve tespit mühendisliğidir; canlı bir saldırı reçetesi vermek değildir.

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Golden Ticket, Kerberos kimlik doğrulama mimarisinin temel bir güven varsayımını istismar eder. Active Directory ortamında bir kullanıcı bir servise erişmek istediğinde şu iki aşamalı akış işler: önce Key Distribution Center (KDC) üzerindeki Authentication Service'ten bir **TGT (Ticket Granting Ticket)** alır (AS-REQ / AS-REP), ardından bu TGT'yi göstererek Ticket Granting Service'ten hedef servise özel bir **TGS (Service Ticket)** alır (TGS-REQ / TGS-REP). Buradaki kritik nokta şudur: TGT, domain'in en ayrıcalıklı hesabı olan **krbtgt** hesabının parola hash'i ile imzalanır ve şifrelenir. KDC, kendisine gelen bir TGT'yi doğrularken onu "veritabanında var mı" diye sorgulamaz; sadece **krbtgt anahtarıyla şifre çözülüp çözülemediğine** bakar. Yani güven, tamamen krbtgt anahtarının gizliliğine dayanır.

Golden Ticket saldırısının kavramsal özü budur: Saldırgan bir şekilde **krbtgt hesabının NTLM hash'ini (veya AES anahtarını) ele geçirdiyse**, KDC'ye hiç danışmadan, tamamen offline olarak, kendi imzaladığı geçerli bir TGT üretebilir. Bu TGT'nin içine istediği kullanıcı adını, istediği domain SID'ini, istediği grup üyeliklerini (örneğin Domain Admins, Enterprise Admins RID'leri) ve istediği geçerlilik süresini (varsayılan olarak Mimikatz gibi araçlar 10 yıl gibi absürt süreler koyar) yazabilir. KDC bu bileti gördüğünde krbtgt ile çözebildiği için "bu benim imzam, geçerli" der ve içindeki iddiaları sorgusuz kabul eder.

Bu yüzden Golden Ticket bir "credential access" tekniği değil, bir **persistence ve privilege escalation** silahıdır. Saldırganın krbtgt hash'ini ele geçirmesi, tipik olarak domain'in zaten tam olarak kompromize olduğu (DCSync ile replikasyon hakları veya doğrudan bir Domain Controller üzerinden NTDS.dit'in okunması) bir noktada gerçekleşir. Golden Ticket, o kompromizi **kalıcı** hale getirir: Saldırgan artık bir daha parola çalmaya ihtiyaç duymadan, herhangi bir kimliğe bürünerek domain'e istediği zaman geri dönebilir. krbtgt parolası değiştirilmediği (ve iki kez rotate edilmediği) sürece bu biletler geçerli kalır.

Operasyonel olarak saldırgan araç zincirinin ucunda genellikle **Rubeus** veya **Mimikatz** vardır. Rubeus'un `ptt` (pass-the-ticket), `tgtdeleg`, `createnetonly`, `asktgt` gibi komutları; Mimikatz'ın `kerberos::golden` modülü bu üretimi yapar. Sahte bilet üretildikten sonra `ptt` ile mevcut oturumun bellek alanına enjekte edilir ve saldırgan artık o kimlikle domain kaynaklarına erişir. Biz savunmacı olarak tam da bu araçların ve bu davranışın bıraktığı izleri arıyoruz — çünkü biletin kendisi kriptografik olarak "geçerli" olduğu için sahteliğini KDC'nin loglarından değil, **anomalilerden** ve **araç imzalarından** anlamak zorundayız.

Golden Ticket'ı doğru konumlandırmak için onu iki "akraba" tekniğinden ayırmak gerekir. **Silver Ticket**, krbtgt hash'i yerine belirli bir servis hesabının (örneğin bir SQL veya CIFS servisi) hash'ini kullanarak yalnızca o tek servis için sahte TGS üretir; kapsamı dardır ama KDC'ye hiç dokunmadığı için 4769 bile bırakmaz — bu yüzden Silver Ticket, Golden'dan daha sinsidir. Golden Ticket ise TGT seviyesinde çalıştığı için domain'deki **her** servise erişim kapısını açar; bu, onu daha güçlü ama aynı zamanda 4769 izleri açısından biraz daha görünür kılar. Bir diğer akraba, **Diamond Ticket**'tır: Saldırgan burada tamamen sıfırdan bir TGT uydurmak yerine, KDC'den alınmış **meşru** bir TGT'yi krbtgt anahtarıyla açıp içindeki PAC (Privilege Attribute Certificate) verisini değiştirip yeniden şifreler. Diamond Ticket, gerçek bir 4768'e dayandığı için "4768 yok / 4769 var" korelasyonunu kırar ve saf Golden'a göre tespiti daha zordur. Bu nüanslar önemlidir çünkü tespit kurallarımızı hangi varsayımlara demirlediğimizi bilmemiz gerekir.

Saldırganın krbtgt anahtarını nasıl ele geçirdiği de tespit stratejimizi doğrudan etkiler. En yaygın yol **DCSync**'tir: Saldırgan, Directory Replication Service protokolünü (DRSUAPI) kullanarak kendisini bir Domain Controller gibi göstererek krbtgt dahil herhangi bir hesabın parola verisini "replikasyon" adı altında çeker. İkinci yol, doğrudan bir DC üzerinde **NTDS.dit** veritabanının ve SYSTEM hive'ının offline kopyalanmasıdır (Volume Shadow Copy, `ntdsutil` if snapshot, vb.). Her iki yol da Golden Ticket'ın **öncülüdür** ve bunlar tespit edilebilirse, saldırganı bilet üretmeden önce yakalama şansımız doğar — Golden Ticket dedektörlerimiz için en değerli erken uyarı, tam da bu krbtgt erişim anıdır.

## 2. Bıraktığı izler / artefaktlar

Golden Ticket'ın en can sıkıcı yanı, "temiz" durumda çok az iz bırakmasıdır: bilet KDC'ye danışılmadan üretildiği için AS-REQ / AS-REP (Event ID **4768**) aşaması hiç yaşanmayabilir. Saldırgan zaten geçerli bir TGT'ye "sahip" olduğu için doğrudan TGS-REQ ile servis bileti istemeye geçer. Bu, tespit için hem zorluk hem fırsattır. İzleri üç katmanda ararız:

**a) Kerberos servis log'ları (Domain Controller Security log):**
- **Event ID 4769 — "A Kerberos service ticket was requested":** Golden Ticket ile üretilmiş bir TGT kullanıldığında, servise erişim anında DC'de bir 4769 üretilir. Buradaki anomali sinyalleri: Bilette taşınan hesap adı ile 4769'da görünen alanların tutarsızlığı, hiçbir 4768 (TGT talebi) olmadan doğrudan 4769'ların belirmesi, çok uzun ömürlü biletler, ve `TicketEncryptionType` alanının anormalliği. Kerberoasting kuralında gördüğümüz gibi 4769'un `Status`, `ServiceName`, `TicketEncryptionType` alanları buradaki analizin temel yapı taşlarıdır.
- **Event ID 4768 — "A Kerberos authentication ticket (TGT) was requested":** Meşru bir TGT talebinde bu üretilir. Golden Ticket'ta bu adım genellikle **atlanır** — dolayısıyla "4768 olmadan 4769 var" korelasyonu klasik bir sinyaldir. Ayrıca eski/zayıf `TicketEncryptionType: '0x17'` (RC4-HMAC) kullanımı, modern AES-only ortamda tek başına bir kırmızı bayraktır.
- **Şifreleme türü tutarsızlıkları:** AES'in zorunlu olduğu bir domain'de aniden RC4 (`0x17`) ile imzalanmış Kerberos trafiği, saldırganın krbtgt'nin sadece NTLM (RC4) hash'ini ele geçirmiş olabileceğini gösterir; çünkü AES anahtarı olmadan üretilen Golden Ticket RC4 kullanmak zorunda kalır.

**b) Süreç oluşturma ve araç imzaları (process_creation / Sysmon Event ID 1, Security Event ID 4688):**
Golden Ticket'ı üreten ve enjekte eden araçların çalıştırılması burada yakalanır. Verilen **HackTool - Rubeus Execution** kuralı tam olarak bu artefaktı hedefler:
- `Image|endswith: '\Rubeus.exe'`, `OriginalFileName: 'Rubeus.exe'`, `Description: 'Rubeus'` gibi PE metadata izleri.
- Komut satırı desenleri: `ptt /ticket:`, `createnetonly /program:`, `dump /service:krbtgt`, `dump /luid:0x`, `/impersonateuser:`, `asktgt`, `tgtdeleg`.
- Bu araçlar `Rubeus.exe` adıyla çalışmayabilir (yeniden adlandırma veya in-memory yürütme), bu yüzden komut satırı bayraklarının kendisi ikinci bir tespit hattı oluşturur.

**c) PowerShell Script Block Logging (ps_script — Event ID 4104):**
Saldırgan Rubeus'u bir PowerShell reflective loader ile bellekte çalıştırdığında, dosya diske hiç düşmese bile Script Block Logging etkinse komut ve bayraklar **ScriptBlockText** içinde görünür. Verilen **HackTool - Rubeus Execution - ScriptBlock** kuralı tam olarak bu izi arar: `ptt /ticket:`, `dump /service:krbtgt`, `/impersonateuser:`, `createnetonly /program:` gibi ifadelerin ScriptBlockText içinde geçmesi.

**d) Ağ ve kimlik anomalileri:**
- Daha önce hiç var olmayan veya devre dışı bir kullanıcı hesabının aniden Kerberos ile kimlik doğrulaması (Golden Ticket ile "silinmiş" bir hesap bile canlandırılabilir).
- Bir TGT'nin geçerlilik süresinin domain politikasındaki maksimum bilet ömrünü (varsayılan 10 saat / 7 gün yenileme) aşması — 4769/4768 içindeki lifetime alanlarında görünür.
- Bir workstation IP'sinden birçok farklı yüksek ayrıcalıklı servise ardışık erişim.
- 4769/4768 olaylarındaki hesap adı ile domain SID'i arasındaki tutarsızlık: Bazı Golden Ticket üretimlerinde saldırgan doğru domain SID'ini bilmez ya da hesap adı ile SID eşleşmez; bu, bilet forge işleminin bir yan izidir.

**e) DCSync / krbtgt erişimi öncül izleri (Domain Controller Security log):**
Golden Ticket'ın öncülü olan krbtgt hash çalınması, bilet üretiminden önce iz bırakır ve bu izler tespit için en değerli erken uyarıdır:
- **Event ID 4662 — "An operation was performed on an object":** DCSync sırasında replikasyon haklarının (`DS-Replication-Get-Changes`, `DS-Replication-Get-Changes-All`) kullanımı bu olayda GUID bazlı property set erişimi olarak görünür. Bir Domain Controller **hesabı olmayan** bir kullanıcının replikasyon isteği yapması güçlü bir DCSync sinyalidir.
- **Event ID 4624 (Logon) / 4672 (Special privileges):** krbtgt'ye veya DC'ye ayrıcalıklı erişim anında oluşan oturum ve ayrıcalık atama olayları, saldırının Tier-0'a ulaştığını gösteren bağlamsal sinyallerdir.
Bu öncül izler, "Golden Ticket üretildikten sonra" yakalamaya çalışmak yerine "üretilmeden önce krbtgt'nin ele geçirildiğini" yakalama fırsatı verir.

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Golden Ticket için tespiti, sağlanan gerçek Sigma kurallarının mantığına demirliyoruz. Doğrudan Golden Ticket "bilet sahteliğini" kanıtlayan tek bir log yoktur; bu yüzden strateji, **saldırıyı çevreleyen araç ve davranış izlerini** yakalamaktır.

**Katman 1 — Araç yürütmesi (Rubeus process_creation).**
`HackTool - Rubeus Execution` (id: 7ec2c172-dceb-4c10-92c9-87c1881b7e18) kuralı `logsource: process_creation / windows` üzerinde çalışır. Mantığı ikili: ya PE metadata ile (`Image|endswith: '\Rubeus.exe'`, `OriginalFileName: 'Rubeus.exe'`, `Description: 'Rubeus'`), ya da komut satırı içeriği ile (`CommandLine|contains`: `dump /service:krbtgt`, `dump /luid:0x`, `createnetonly /program:`, `ptt /ticket:` vb.) eşleşir. Golden Ticket bağlamında en kritik desenler `ptt /ticket:` (üretilen sahte bileti oturuma enjekte etme) ve `createnetonly /program:` (bilet enjekte edilecek gizli bir logon session yaratma) desenleridir. Bu kuralın felsefesi: aracın adını gizlesen bile davranışsal bayraklarını gizleyemezsin.

**Katman 2 — Bellekte yürütme (Rubeus ScriptBlock).**
`HackTool - Rubeus Execution - ScriptBlock` (id: 3245cd30-e015-40ff-a31d-5cadd5f377ec) kuralı `logsource: ps_script / windows` üzerinde, Script Block Logging etkinken çalışır. `ScriptBlockText|contains` ile aynı bayrakları (`ptt /ticket:`, `dump /service:krbtgt`, `/impersonateuser:`) PowerShell bağlamında arar. Bu, diske dosya yazmayan fileless yürütmeyi yakalamak için birinci katmanı tamamlar. İkisini birlikte konuşlandırmak, "yeniden adlandırılmış EXE" ve "bellekte yükleme" kaçışlarının ikisini de kapatır.

**Katman 3 — Kerberos servis davranışı (4769 / 4768 anomalileri).**
Golden Ticket kullanımı sırasında DC'de üretilen 4769 olaylarını, Kerberoasting kuralının (`d04ae2b8-...`) kurduğu `logsource: windows / security`, `EventID: 4769`, `Status: '0x0'` (yalnızca başarılı biletler), `TicketEncryptionType` analiz iskeletiyle inceleriz. Golden Ticket'ta arayacağımız fark: Kerberoasting'de sinyal "tek host'tan çok sayıda ServiceName'e RC4 talebi" iken, Golden Ticket'ta sinyal "önünde hiçbir 4768 bulunmayan 4769", "anormal uzun bilet ömrü" ve "AES-only domain'de beliren `0x17` RC4 şifrelemesi"dir. AS-REP Roasting kuralının (`3e2f1b2c-...`) 4768 üzerindeki `TicketEncryptionType: '0x17'` ve `ServiceName: 'krbtgt'` odaklı mantığı da bize hangi alanlara bakacağımızı gösterir: krbtgt hedefli, RC4 şifrelemeli Kerberos olayları her zaman ekstra inceleme hak eder.

**Basit Sigma-benzeri tespit mantığı örneği 1 — Rubeus ile Golden/Ticket enjeksiyonu:**

```yaml
title: Golden Ticket - Rubeus ptt/createnetonly Kullanımı (davranışsal)
logsource:
    category: process_creation
    product: windows
detection:
    selection_tool:
        - Image|endswith: '\Rubeus.exe'
        - OriginalFileName: 'Rubeus.exe'
        - Description: 'Rubeus'
    selection_cmd:
        CommandLine|contains:
            - 'ptt /ticket:'
            - 'createnetonly /program:'
            - 'dump /service:krbtgt'
    condition: selection_tool or selection_cmd
falsepositives:
    - Yetkili red team / pentest çalışmaları (change ticket ile eşleştir)
level: high
```

Bu kural, verilen Rubeus kuralının mantığını Golden Ticket'a en yakın bayraklara daraltır: `ptt /ticket:` bilet enjeksiyonunu, `createnetonly /program:` gizli oturum yaratımını, `dump /service:krbtgt` ise krbtgt anahtarının çekilmesini yakalar.

**Basit Sigma-benzeri tespit mantığı örneği 2 — 4768 olmadan beliren RC4 servis bileti:**

```yaml
title: Golden Ticket Şüphesi - RC4 Servis Bileti Anomalisi
logsource:
    product: windows
    service: security
detection:
    selection:
        EventID: 4769
        Status: '0x0'
        TicketEncryptionType: '0x17'   # RC4-HMAC, AES-only domain'de anormal
    condition: selection
    # Ek korelasyon (SIEM tarafında): aynı hesap için önceki N dakikada
    # hiç EventID 4768 yoksa skoru yükselt.
falsepositives:
    - RC4'ü meşru kullanan legacy sistem/uygulamalar (baseline'a ekle)
level: medium
```

Bu ikinci örnek, AS-REP Roasting ve Kerberoasting kurallarından ödünç alınan `EventID: 4769/4768`, `Status: '0x0'`, `TicketEncryptionType: '0x17'` alanlarını kullanır; Golden Ticket'a özgü katkı ise "önünde 4768 bulunmama" korelasyonudur. Bu korelasyon tek başına bir Sigma `detection` bloğunda ifade edilemez (durum-bilgili sorgu gerekir), bu yüzden Kerberoasting kuralının açıkça belirttiği gibi "further analysis or computation within the query is needed" — yani SIEM tarafında zaman-pencereli bir sorguyla tamamlanır.

**Katman 4 — Öncül krbtgt erişimini (DCSync) yakalama.**
En değerli erken uyarı, Golden Ticket üretilmeden önce krbtgt anahtarının çekildiği andır. Bu katman, verilen Rubeus kuralının `dump /service:krbtgt` bayrağını process_creation tarafında yakalamasını, DC tarafındaki replikasyon anomalisiyle birleştirir. Rubeus kuralı zaten `CommandLine|contains: 'dump /service:krbtgt'` ve `'dump /luid:0x'` desenlerini içerir; bunlar bir host'ta krbtgt anahtarının bellekten çekilmeye çalışıldığını gösterir. DC tarafında ise DCSync'i, DC hesabı olmayan bir principal'ın replikasyon operasyonu yapmasıyla ayırt ederiz:

```yaml
title: Golden Ticket Öncülü - DCSync Şüphesi (replikasyon anomalisi)
logsource:
    product: windows
    service: security
detection:
    selection:
        EventID: 4662
        Properties|contains:
            - 'DS-Replication-Get-Changes'
            - 'DS-Replication-Get-Changes-All'
    filter_dc:
        SubjectUserName|endswith: '$'   # meşru DC makine hesapları
    condition: selection and not filter_dc
falsepositives:
    - Azure AD Connect / dizin senkronizasyon hizmet hesapları (whitelist)
    - Yetkili yedekleme veya migration araçları
level: high
```

Bu üçüncü örnek, "bileti yakalamak" yerine "anahtarı çalmayı yakalamak" felsefesini uygular: DCSync yakalanırsa, saldırganın henüz Golden Ticket üretmeden durdurulması mümkün olur. `SubjectUserName|endswith: '$'` filtresi, meşru DC-to-DC replikasyonunu (makine hesapları `$` ile biter) elemek için kritiktir; bu filtre olmadan kural her replikasyon döngüsünde patlar.

## 4. Kaçınma ve karşı-tespit + false positive

**Saldırgan bu tespiti nasıl atlatmaya çalışır:**

1. **Araç adını gizleme:** `Rubeus.exe` dosyasını yeniden adlandırmak, `Image|endswith` bacağını atlatır. Karşı-tespit: `OriginalFileName` ve `Description` PE metadata bacakları yeniden adlandırmadan etkilenmez — çünkü bunlar derleme zamanı gömülü değerlerdir. Ayrıca komut satırı bayrağı bacağı (`ptt /ticket:`, `createnetonly /program:`) ada bağlı değildir; aracı yeniden adlandırsanız bile davranış imzası kalır.

2. **Bellekte yürütme (fileless):** Rubeus'u diske hiç yazmadan bir reflective PE loader ile çalıştırmak, process_creation kuralının dosya izini atlatır. Karşı-tespit: **Script Block Logging** (Event 4104) etkinleştirmek ve `HackTool - Rubeus Execution - ScriptBlock` kuralını konuşlandırmak; ayrıca komut satırı loglaması (4688 CommandLine yakalama, Sysmon) ve mümkünse AMSI. In-memory yürütmede bile ScriptBlockText içindeki bayraklar sızabilir.

3. **AES kullanımı:** Saldırgan krbtgt'nin AES anahtarını da ele geçirdiyse, Golden Ticket'ı RC4 yerine AES ile üretebilir. Bu, `TicketEncryptionType: '0x17'` (RC4) tabanlı anomali kuralını sessizce atlatır — bu yüzden şifreleme türü sinyali **tek başına** yeterli değildir, yalnızca destekleyici bir göstergedir. Karşı-tespit: Şifreleme türüne değil, bilet ömrü anomalisine, "4768 yok / 4769 var" korelasyonuna ve araç yürütme izlerine ağırlık vermek.

4. **Gerçekçi bilet parametreleri:** Eski Mimikatz varsayılanı 10 yıllık bilet ömrü koyardı; olgun saldırganlar bunu domain politikasıyla uyumlu (örneğin 10 saat) hale getirerek "anormal uzun ömür" sinyalini öldürür. Karşı-tespit: Ömür anomalisine bel bağlamamak; bunun yerine krbtgt hash'inin ele geçirildiği **kök nedeni** (DCSync — anormal replikasyon, DC'de LSASS erişimi) izlemek ve krbtgt parolasını periyodik olarak (ihlal sonrası **iki kez, arayla**) rotate etmek — bu, mevcut tüm Golden Ticket'ları geçersiz kılan tek kesin savunmadır.

**Savunmacının bütünsel duruşu:** Golden Ticket için "tek atışlık" bir dedektör yoktur; katmanlı bir yaklaşım gerekir. Araç yürütme (Rubeus process_creation + ScriptBlock) ilk hattır ve en yüksek güvenilirliğe sahiptir. Kerberos davranış anomalileri (4769/4768 korelasyonu, RC4 sinyali) ikinci hat destekleyici sinyaldir. En derin savunma ise **önleme**dir: DC'lerin sıkılaştırılması, DCSync yetkilerinin izlenmesi (replikasyon olayları), Tier-0 hesaplarının izolasyonu ve krbtgt rotasyonu. Tespit, bu önleme başarısız olduğunda saldırganı yakalamak için vardır.

**Tipik false positive kaynakları ve nasıl ayıklanır:**

- **Yetkili red team / pentest çalışmaları:** Rubeus imzalarının en yaygın gerçek dünya kaynağı budur. Ayıklama: Onaylı test pencerelerini ve kaynak host'ları change management / ticket sistemiyle eşleştirip whitelist yapmak, ancak testi de bir alarm olarak loglamak (görünürlüğü kaybetmemek için).
- **Legacy RC4 kullanan sistemler:** AS-REP ve Kerberoasting kurallarının falsepositives bölümünde de belirtildiği gibi, `TicketEncryptionType: '0x17'` bazı eski uygulama ve yanlış yapılandırılmış hesaplar tarafından meşru olarak üretilir. Ayıklama: RC4 kullanan meşru servisleri baseline'a çıkarıp filtrelemek; alarmı yalnızca "AES-yetenekli olması gereken" hesaplarda tetiklemek.
- **Güvenlik araçlarının kendi tarama/telemetri trafiği:** Bazı EDR ve varlık keşif araçları Kerberos trafiği üretebilir. Ayıklama: Bilinen güvenlik ürünü hesaplarını ve host'larını kimlik bazlı istisnaya almak.
- **Adli/DFIR araç adlarının dosya adında geçmesi:** `krbtgt`, `ptt` gibi dizeleri içeren zararsız script veya dokümanların komut satırında geçmesi nadir de olsa gürültü yaratabilir. Ayıklama: Kuralları `ptt /ticket:` gibi **boşluk ve argüman yapısı dahil** dar desenlere demirlemek (verilen Rubeus kuralının tam da bu şekilde `'ptt /ticket:'` ve `'createnetonly /program:'` yazmasının nedeni budur), böylece rastgele metin eşleşmesi azalır.

Özetle: Golden Ticket, krbtgt anahtarının gizliliğine dayanan Kerberos güven modelinin istismarıdır ve kriptografik olarak "geçerli" biletler ürettiği için biletin kendisinden değil, onu üreten araçların (Rubeus/Mimikatz) yürütme izlerinden ve çevresindeki Kerberos davranış anomalilerinden yakalanır. Sağlanan gerçek Sigma kuralları bize iki sağlam demir noktası verir: process_creation ve ps_script üzerindeki Rubeus imzaları (birincil), ve 4768/4769 üzerindeki `Status`, `TicketEncryptionType`, `ServiceName` alanlarıyla kurulan davranışsal korelasyon (destekleyici). Kesin önlem ise tespitin ötesinde, krbtgt rotasyonu ve Tier-0 izolasyonundadır.
