# SID History Injection — Tespiti

## 1. Özet: saldırı + naif tespit (kısa)

Active Directory'de her güvenlik prensibinin (kullanıcı, grup, bilgisayar) bir birincil SID'i vardır. Bunun yanında `sIDHistory` adında ikincil, çoklu-değerli bir öznitelik bulunur. Bu öznitelik meşru olarak domain/forest migration senaryoları için tasarlandı: bir hesabı A domain'inden B domain'ine taşırken, eski SID'i `sIDHistory`'ye yazarsınız ki eski kaynaklara (dosya ACL'leri, mailbox izinleri) erişim kesilmesin. Kerberos ve NTLM yetkilendirmesi sırasında bu SID'ler kullanıcının erişim token'ına **PAC** (Privilege Attribute Certificate) içinde eklenir.

Saldırganın işine gelen kısım tam da bu: `sIDHistory`'ye yazdığınız bir SID, o token'da sanki hesabın kendi grubuymuş gibi davranır. Yani sıradan bir kullanıcı hesabının `sIDHistory` özniteliğine **Domain Admins** (`S-1-5-21-<domain>-512`) veya **Enterprise Admins** (`-519`) SID'ini enjekte ederseniz, o kullanıcı hiçbir grup üyeliği görünmeden Domain Admin yetkisiyle oturum açar. `net user`, `whoami /groups`, ADUC'ta grup sekmesi — hiçbiri bu yetkiyi göstermez. Bu, **T1134.005 (SID-History Injection)** kalıcılık/yetki-yükseltme tekniğidir ve red team'in en sevdiği "gizli backdoor"lardan biridir.

Enjeksiyon yolları:
- **DCShadow / `Mimikatz` `sid::patch` + `sid::add`** — LSASS üzerinden veya sahte DC ile.
- **`DSInternals`** `Add-ADDBSidHistory` (offline `NTDS.dit` manipülasyonu) veya `Set-ADAccountControl` çevresi.
- **Golden Ticket içinde `/sids`** parametresi — burada `sIDHistory` diske hiç yazılmaz, sadece bilet içinde taşınır (bu ayrı bir kör nokta, 5. bölümde).
- **DA yetkisiyle native API** — `DsAddSidHistory` çağrısı.

Naif tespit: Sigma kuralı **`2632954e-db1c-49cb-9936-67d1ef1d17d2`** (Addition of SID History to Active Directory Object) tam olarak bunu hedefler. İki bacağı var:
- `selection1`: Security log'da **EventID 4765** (bir hesaba SID History **eklendi**) veya **4766** (SID History ekleme **başarısız**).
- `selection2 + değişiklik mantığı`: **EventID 4738** (kullanıcı hesabı değiştirildi) olayında `SidHistory` alanı `-` veya `%%1793` **dışında** bir değere sahipse ve boş değilse.

Naif kural şöyle: "4765/4766 gördüysen alarm; ya da 4738'de SidHistory dolmuşsa alarm." Kağıt üzerinde temiz. Sahada bu kural ya sessiz kalır ya da migration döneminde alarm seli üretir. Nedenine geçelim.

## 2. Naif tespit neden yetmez

### Kör nokta 1: 4765 çoğu ortamda hiç loglanmaz

**EventID 4765** ve **4766**, "SA" (Security Account Management / User Account Management) audit alt-kategorisinde üretilir, ancak asıl mesele bu event'lerin **yalnızca `DsAddSidHistory` API'si** çağrıldığında tetiklenmesidir. Saldırganların pratikte kullandığı yolların çoğu bu API'yi çağırmaz:
- `Mimikatz sid::add`, hedef özniteliği **doğrudan LDAP/DRSUAPI** üzerinden yazar — 4765 üretmez, en fazla 4738 üretir.
- `DSInternals`'ın offline `NTDS.dit` yazması **hiçbir Security event üretmez**; DC çalışırken bile `Add-ADDBSidHistory` DB katmanında çalışır.
- DCShadow, meşru DC replikasyonunu taklit ettiği için, değişiklik replike edilir ama enjeksiyon anındaki DC-side audit event'i yaratılmayabilir.

Yani 4765'e güvenen bir tespit, **gerçek saldırıların çoğunu göremez**. 4765, "birileri resmi API ile SID History ekledi" der — bu genelde meşru migration aracıdır (ADMT). Saldırgan resmi API kullanmaz.

### Kör nokta 2: 4738 ve `SidHistory` alanının yalanı

4738 (A user account was changed) daha güvenilir görünür çünkü öznitelik değiştiğinde üretilir. Ama iki büyük sorun var:

**a) `SidHistory` alanı çoğu ortamda `-` gelir.** 4738 event'i, `sIDHistory` özniteliğinin **yeni değerini metin olarak** her zaman doldurmaz. Windows'un audit motoru, bu alan için sıklıkla `-` (değişmedi/gösterilmiyor) yazar, hatta `%%1793` ("<value not set>") döndürür. Kuralın `selection3` filtresi tam bunu dışlıyor: `SidHistory` `-` veya `%%1793` ise **selection2'yi say ama selection3 olmasın** mantığıyla. Sorun şu: eğer alan `-` geliyorsa kuralın gerçek enjeksiyonu yakalayan bacağı da susar. Yani hem gürültüyü hem sinyali aynı alan belirliyor — kırılgan.

**b) 4738 domain başına DC'de yüzlerce-binlerce/gün üretilir.** `pwdLastSet`, `userAccountControl`, `lastLogonTimestamp`, LAPS parola rotasyonu, `msDS-` öznitelikleri — hepsi 4738 tetikler. `SidHistory` alanı doğru gelmezse, kuralı "4738 varsa bak" seviyesine indirmek analizi boğar.

### Kör nokta 3: Golden Ticket `/sids` — diskte hiç iz yok

En kritik atlatma: saldırgan `sIDHistory` özniteliğine **hiç dokunmadan**, aynı yetkiyi Golden Ticket içindeki **ExtraSids** alanıyla elde edebilir. `mimikatz kerberos::golden /sids:S-1-5-21-...-519` komutu, PAC'ın `SidHistory` bölümüne Enterprise Admins SID'ini yazar. Bu bilet forge edildiğinde:
- 4765 yok, 4766 yok, 4738 yok.
- AD nesnesinde `sIDHistory` özniteliği **boş kalır**.
- LDAP taraması ile bulunamaz.

Naif tespit tamamen kör. Bu yüzden nesne-tabanlı tespit (4738/4765) **tek başına asla yeterli değildir**; token/bilet-tabanlı ikinci bir katman şart (5. bölüm).

### Kör nokta 4: DSInternals'ın kendisi görünmez değil ama loglama gerektirir

Sağlanan **`43d91656-...`** (DSInternals Suspicious PowerShell Cmdlets — process_creation) ve **`846c7a87-...`** (ScriptBlock) kuralları, DSInternals modülünün *kullanımını* yakalamayı hedefler. Ama:
- process_creation kuralı **`CommandLine|contains`** ile çalışır — yani cmdlet adı komut satırında görünmeli. Saldırgan modülü `Import-Module` ile yükleyip fonksiyonu **encoded** veya değişken üzerinden çağırırsa komut satırında iz kalmaz.
- ScriptBlock kuralı **Script Block Logging (EventID 4104) açık olmalı** notunu taşır. Çoğu ortamda 4104 ya kapalı ya da sadece "suspicious" seviyede loglanıyor. Kapalıysa kural ölüdür.

Sonuç: Dört kural da tek başına delikli. Değer, bunları **birbirine bağlamaktan** ve nesne-durumuyla korele etmekten gelir.

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek-güven için çok-aşamalı, farklı bağlamdan gelen sinyalleri kısa pencerede birleştir. İşte gerçek enjeksiyonu ADMT migration'ından ayıran somut desen:

### Zincir A: DSInternals ile offline/online enjeksiyon

```
A: DSInternals yüklendi/çağrıldı
   (43d91656 process_creation VEYA 846c7a87 ScriptBlock 4104
    → CommandLine|contains: 'Add-ADDBSidHistory' / 'Set-SamAccountPasswordHash' / 'Get-ADReplAccount')
        +  [aynı host, ±10 dk]
B: NTDS.dit veya DS veritabanına erişim
   (Sysmon EventID 11 → ntds.dit dosya yazması, VEYA 4662 →
    'DS-Replication-Get-Changes-All' GUID'ine erişim)
        +  [±30 dk, FARKLI bağlam]
C: sIDHistory nesne değişikliği
   (4738 → hedef hesapta değişiklik, VEYA sonraki LDAP taramasında
    ayrıcalıklı SID sIDHistory'de belirdi)
        =  YÜKSEK GÜVEN: SID History Injection
```

Buradaki kritik nokta: **A tek başına** bir admin'in DSInternals ile parola denetimi yapması olabilir (meşru). **C tek başına** ADMT migration'ı olabilir (meşru). Ama **DSInternals + NTDS erişimi + ardından sıradan bir kullanıcı hesabında sIDHistory'nin ayrıcalıklı bir SID ile dolması** — bunun meşru açıklaması yoktur.

### Zincir B: Enjeksiyon sonrası "sessiz DA" tespiti — asıl değer

Enjeksiyonun kendisini kaçırsanız bile, **kullanıma** yakalayabilirsiniz. Somut:

```
A: sIDHistory'sinde ayrıcalıklı SID (-512/-519/-518/-516) taşıyan bir hesap
   (haftalık LDAP baseline taraması → beklenmedik sIDHistory değeri)
        +  [kısa pencere]
B: O hesapla ayrıcalıklı işlem
   (4672 → 'Special privileges assigned to new logon' →
    SeDebugPrivilege/SeBackupPrivilege, hesap DA grubunda DEĞİLKEN)
        +
C: Erişilen hedef ile grup üyeliği çelişkisi
   (4624 Logon → yüksek-değerli host; ama 4728/4732/4756 ile bu hesabın
    o gruba ekleniş kaydı YOK)
        =  Enjekte edilmiş SID kullanımda
```

`4672` (Special Privileges Assigned to New Logon) altın sinyaldir: kullanıcı gruplarında admin yetkisi olmadığı halde oturumunda admin ayrıcalıkları atanıyorsa, PAC'ta `sIDHistory` üzerinden gelen bir SID neredeyse kesin nedendir. Bunu "hesabın nominal grup üyeliği" ile karşılaştırın — grup yok ama ayrıcalık var = enjeksiyon imzası.

### Zincir C: Golden Ticket + ExtraSids

```
A: 4769 (Kerberos Service Ticket) → normal AS-REQ (4768) OLMADAN gelen TGS
   VEYA anormal bilet ömrü / şifreleme (RC4 downgrade)
        +
B: 4672 → ayrıcalık ataması, hesap-grup çelişkisiyle
        +
C: DC üzerinde replikasyon/DCSync imzası (4662 DS-Replication GUID'leri)
        =  Golden Ticket / ExtraSids kullanımı
```

Bu zincir, nesne-tabanlı tespitin tamamen kör olduğu senaryoyu yakalar. Kilit: **4768 olmadan 4769** — bilet DC tarafından verilmedi, forge edildi.

Korelasyonun özü: **farklı log kaynaklarından (Security, Sysmon, LDAP baseline) gelen sinyaller aynı hesap/host etrafında kısa pencerede toplanınca**, tek başına gürültü olan olaylar reddedilemez bir ihlal anlatısına dönüşür.

### Pencere seçimi — pratik detay

Korelasyon penceresini yanlış seçmek zincirleri kırar. Enjeksiyon ile *kullanım* arasında saatler, hatta günler olabilir — saldırgan backdoor'u bugün kurup iki hafta sonra kullanır. Bu yüzden:
- **A→B→C (enjeksiyon aşaması)** için pencere dar tutulur: DSInternals yüklemesi, NTDS erişimi ve nesne değişikliği tipik olarak **dakikalar-onlarca dakika** içinde olur. Burada ±30 dk makul.
- **Enjeksiyon → kullanım** için pencereyi zamanla sınırlama; bunun yerine **durum-tabanlı** yürü: "sIDHistory'de ayrıcalıklı SID taşıyan hesap listesi" bir *watchlist* olarak tutulur, o watchlist'teki her hesabın her 4672/4624'ü — pencere olmadan — incelenir. Zaman penceresiyle korelasyon burada tuzaktır; **kalıcı durum listesi** doğru araçtır. Splunk'ta bu bir `outputlookup`/`lookup`, Sentinel'de bir `watchlist`, Elastic'te bir `enrich policy`'dir.

## 4. False positive gerçeği ve triage yargısı

`sIDHistory` alanı, gerçek dünyada meşru olarak dolar. Bir detection engineer'ın FP kaynaklarını ezbere bilmesi lazım:

1. **Domain/forest migration (ADMT, Quest QMM)** — en büyük FP kaynağı. Bir birleşme/satın alma sonrası binlerce hesabın `sIDHistory`'si ADMT ile doldurulur ve **4765 event'leri yasal olarak patlar**. Kuralın `falsepositives: Migration of an account into a new domain level` notu tam bunu söylüyor. Migration penceresinde bu kural pratikte kapatılmalı ya da ADMT servis hesabı whitelist'lenmeli.

2. **Kurumsal AD birleştirmeleri / yeniden yapılandırma** — domain konsolidasyonu, SID-A'dan SID-B'ye geçiş projeleri aylarca sürebilir.

3. **Yedekleme/geri yükleme araçları (authoritative restore)** — bir DC'nin IFM backup'tan restore edilmesi, DSInternals'ın `Get-ADReplAccount` gibi cmdlet'lerini meşru olarak çalıştırabilir → DSInternals kuralları (43d91656/846c7a87) ateşlenir.

4. **SCCM / güvenlik tarayıcıları / PAM araçları** — bazı denetim ve keşif araçları `NTDS.dit` veya replikasyon API'lerine dokunur; DSInternals FP'si değil ama 4662/replikasyon-tabanlı kurallarda gürültü.

5. **PingCastle / BloodHound / Purple Knight** gibi AD hijyen tarayıcıları `sIDHistory`'yi **okur** (yazmaz) ama LDAP query pattern'leri replikasyon-benzeri görünebilir.

### Analistin öncelik sırası (triage yargısı)

Bir SID History alarmı geldiğinde, kıdemli bir analist şu sırayla eler:

1. **Enjekte edilen SID'in RID'ine bak.** `sIDHistory` değeri **-512 (Domain Admins), -519 (Enterprise Admins), -518 (Schema Admins), -516 (Domain Controllers), -500 (built-in Administrator)** gibi ayrıcalıklı bir RID mi taşıyor? Migration'da hesaplar **kendi eski normal SID'lerini** taşır — asla Domain Admins SID'i değil. **Ayrıcalıklı RID = P1, migration olamaz.** Sıradan bir user-RID (>1000) taşıyorsa P3, muhtemelen migration.

2. **Hedef hesabın niteliği.** Enjeksiyonu alan hesap yeni oluşturulmuş, düşük profilli, "servis hesabı" görünümlü bir kullanıcı mı? Saldırgan gözden uzak bir hesabı tercih eder. Migration'da ise **toplu ve tutarlı** bir set görürsünüz — tek bir garip hesap değil.

3. **Zamanlama ve kaynak.** Değişikliği yapan hesap ADMT servis hesabı mı, yoksa iş saati dışında bir workstation'dan bağlanan bir kullanıcı mı? 4738/4765'in `SubjectUserName` ve `SubjectLogonId` alanları burada belirleyici.

4. **Toplu mu tekil mi?** Migration = toplu, planlı, change-ticket'lı. Enjeksiyon = **tekil, plansız, ticket'sız**. Change management kaydıyla kesişim yoksa güven artar.

5. **`sIDHistory` sayısı ve tutarlılık.** Bir hesapta tek bir ayrıcalıklı SID belirmiş, geri kalan hiçbir hesapta yoksa — bu migration'ın istatistiksel imzasına uymaz.

Pratik yargı: **RID-tabanlı önceliklendirme her şeyin önünde.** "sIDHistory'de -512 var" ile "sIDHistory'de S-1-5-21-...-1104 var" arasındaki fark, gece 3'te uyandırılmakla sabah kahvede bakmak arasındaki farktır.

## 5. Kaçınma → karşı-tespit

Dokümanların yazmadığı atlatmalar ve bunlara karşı ikinci-derece tespit:

### Atlatma 1: Golden Ticket ExtraSids (nesneye hiç dokunma)
Yukarıda geçti — `sIDHistory` özniteliğine yazmak yerine bilet PAC'ına SID basmak. **Karşı-tespit:** Nesne tespitine güvenmeyi bırak, **PAC-token korelasyonuna** geç. `4672` ile hesabın gerçek grup üyeliği arasındaki çelişki + `4768`siz `4769`. Ayrıca DC'lerde **PAC validation** ve mümkünse Kerberos armoring/FAST devreye alınmalı.

### Atlatma 2: Encoded / obfuscated DSInternals çağrısı
`43d91656` process_creation kuralı `CommandLine|contains` ile cmdlet adını arar. Saldırgan `Import-Module` sonrası fonksiyonu `& (gcm A`d`d-ADDBSidHistory)` gibi tick-obfuscation veya `-EncodedCommand` ile çağırırsa komut satırı imzası kaçar. **Karşı-tespit:** ScriptBlock logging (4104) zorunlu kıl — obfuscation deobfuscate edilmiş haliyle 4104'te görünür. Ayrıca `846c7a87` kuralını **modül-yükleme** (EventID 4103 pipeline, veya Sysmon EventID 7 → `DSInternals.dll` image load) ile destekle. Komut satırı yalan söyler, yüklenen DLL söylemez.

### Atlatma 3: DCShadow ile audit-bypass
DCShadow sahte bir DC kaydedip değişikliği replikasyonla iter; enjeksiyon anındaki DC-side 4738/4765 üretilmeyebilir. **Karşı-tespit:** DCShadow'un kendi imzası vardır — geçici olarak `nTDSDSA` nesnesi ve SPN (`GC/`, `E3514235-...`) eklenir/silinir. Bunu **4742 (computer account changed)** + anormal replikasyon kaynağı (`4662` DS-Replication, DC olmayan bir host'tan) ile yakala. Ayrıca beklenen DC listesi (baseline) dışından gelen replikasyon trafiği = kırmızı bayrak.

### Atlatma 4: `%%1793` / `-` alan boşluğunu kalkan yapmak
Saldırgan, enjeksiyonun 4738'de `SidHistory` alanının zaten `-` geleceğini bilir; kural bu boşluğu filtreliyor (`selection3`). Bu, kuralın kör noktası olarak istismar edilir. **Karşı-tespit:** 4738'in alan içeriğine güvenme; bunun yerine **periyodik LDAP baseline diff** çalıştır. `Get-ADObject -LDAPFilter '(sIDHistory=*)' -Properties sIDHistory` çıktısını dünkü baseline ile karşılaştır. Yeni beliren her `sIDHistory` değerini, özellikle ayrıcalıklı RID taşıyanları, event'ten bağımsız yakalarsın. **Nesne-durumu tespiti event tespitinden daha güvenilirdir** çünkü saldırgan durumu gizleyemez — enjeksiyon işe yaraması için nesnede kalmalıdır (Golden Ticket hariç).

### Atlatma 5: Migration penceresini kamuflaj olarak kullanma
Saldırgan, gerçek bir ADMT migration'ı sürerken enjeksiyonunu araya sıkıştırır — analistin "yine migration gürültüsü" deyip geçmesini umar. **Karşı-tespit:** Migration penceresinde kuralı kapatma; bunun yerine **ADMT servis hesabını `SubjectUserName` ile whitelist'le** ve *sadece o hesap dışından* gelen sIDHistory değişikliklerini alarm et. Ayrıca migration sırasında bile **RID filtresi açık kalsın**: ADMT ayrıcalıklı RID basmaz, o yüzden -512/-519 her koşulda P1.

## 6. SIEM/saha gerçeği

### Field mapping ve varsayılan loglanmayanlar

En sık batıran nokta: **4765/4766/4738 varsayılan olarak loglanmaz.** Bunların üretilmesi için:
- **Audit User Account Management** (Success) alt-kategorisi açık olmalı → 4738, 4765, 4766, 4720, 4722 vb.
- **Audit Directory Service Changes** açık olmalı ve DC'de **`sIDHistory` özniteliğinde SACL** ayarlanmalı → aksi halde 5136 (directory object modified) `sIDHistory` için üretilmez.
- **Script Block Logging (4104)** ayrı bir GPO/registry (`EnableScriptBlockLogging`) — DSInternals ScriptBlock kuralı (846c7a87) bunsuz ölüdür.
- **Sysmon** DLL image load (EventID 7) ve dosya yazma (EventID 11) ayrı config gerektirir.

Yani "Sigma kuralını import ettim, koruyorum" yanılgısı: **kaynak audit policy açık değilse kural hiç ateşlenmez.** Ilk iş: DC'lerde `auditpol /get /category:*` ile "DS Access" ve "Account Management" alt-kategorilerini doğrula.

### `SidHistory` alan adı platformlar arası

Sigma soyut alan adı `SidHistory` kullanır; gerçek log'da bu değişir:
- **Windows Security XML / EVTX:** 4738'de `Sid History` (boşluklu, `<Data Name="SidHistory">`), 4765'te `SidList` / `AccountName`.
- **Splunk (Windows TA):** `SidHistory` genelde raw'da kalır; CIM normalizasyonu bu alanı taşımaz — `| rex` ile `Message`'tan çıkarmanız gerekebilir. Öneri: `EventCode=4738 OR EventCode=4765 OR EventCode=4766` + `sourcetype=WinEventLog:Security`, sonra `Sid_History` field extraction'ı manuel tanımla.
- **Sentinel (SecurityEvent tablosu):** `EventID` int'tir; `SidHistory` alanı `SecurityEvent` şemasında **ilk-sınıf kolon değildir** — çoğunlukla `EventData` XML içinde gömülüdür. `extractjson` / `parse_xml(EventData)` ile çekmek gerekir. KQL: `SecurityEvent | where EventID in (4765,4766,4738)` + `extend sid = extractjson("$.SidHistory", EventData)`.
- **Elastic (Winlogbeat / ECS):** `winlog.event_id`, `winlog.event_data.SidHistory`. ECS'te normalize edilmez, `winlog.event_data.*` altında ham kalır. Elastic detection rule'da `winlog.event_data.SidHistory` üzerinden filtrele.

### Platform farkları — pratik sonuç

- **Splunk:** Yüksek EPS'de 4738 seli maliyetli. Öneri: 4738'i sadece `Sid_History` dolu geldiğinde indeksleme yerine, tüm 4738'i alıp **korelasyon aramasında** filtrele; ya da RID-tabanlı arama ile sadece `-512|-519|-518|-516|-500` içeren değerleri alarma bağla.
- **Sentinel:** `SecurityEvent` pahalıdır; çoğu ekip 4738'i toplamaz. Alternatif: **`IdentityDirectoryEvents`** (Defender for Identity) tablosu, "SID History modified" ve "suspicious additions to sensitive groups" için hazır sinyal üretir — buna yaslanmak `SecurityEvent` maliyetini kurtarır.
- **Elastic:** Winlogbeat'i DC'lerde 4738 için açmak volume patlatır; `event_id` bazlı filtreyi **agent tarafında** (processors) yap, indekse gelmeden azalt.

### Tuning önerileri (somut)

1. **RID allowlist'i tersine çevir.** "Tüm sIDHistory değişikliklerini alarm et" yerine "sadece ayrıcalıklı RID (`512,519,518,516,500,502,526,527`) içeren değerleri P1, diğerlerini P3 log-only" yap. Bu, migration gürültüsünü %95 keser, gerçek tehdidi kaçırmaz.
2. **ADMT/QMM servis hesaplarını `SubjectUserName` ile whitelist'le**, ama sadece non-privileged RID değişiklikleri için. Ayrıcalıklı RID her koşulda alarm.
3. **LDAP baseline diff'i günlük cron olarak koştur** — event tespitini tamamlayan, atlatmaya dayanıklı ikinci katman. Splunk'ta `| ldapsearch`, Sentinel'de Defender for Identity, saf ortamda scheduled PowerShell → CSV diff.
4. **DSInternals kurallarını DLL image-load (Sysmon EID 7 → `DSInternals`) ile güçlendir** — komut satırı obfuscation'ına karşı.
5. **4672'yi hesap-grup baseline'ı ile korele et** — "grubu yok ama ayrıcalığı var" mantığı, enjeksiyonun *kullanımını* yakalayan en dayanıklı sinyaldir ve tüm enjeksiyon yollarını (nesne + Golden Ticket) kapsar.

### Son yargı

SID History Injection tespitinde tek bir kurala güvenmek — özellikle 4765'e — sahte bir güven duygusudur; gerçek saldırıların çoğu o event'i hiç üretmez. Değer üç katmanın kesişimindedir: **(1)** olay-tabanlı (4738/4765 + RID filtresi), **(2)** nesne-durumu tabanlı (LDAP `sIDHistory` baseline diff — atlatmaya en dayanıklısı), **(3)** kullanım tabanlı (4672 + grup çelişkisi + 4768'siz 4769 — Golden Ticket'ı da kapsayan tek katman). Bir detection engineer'ın işi bu üçünü tek anlatıda birleştirmek, migration gürültüsünü RID mantığıyla susturmak ve audit policy'nin gerçekten açık olduğunu doğrulamaktır — çünkü kapalı bir SACL, dünyanın en iyi Sigma kuralını sessiz bir dosyaya çevirir.
