# DCSync — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin bir saldırı reçetesi değildir; DCSync'in savunmacı gözünden **anlaşılması ve tespit edilmesi** üzerinedir. Önce tekniğin domain controller (DC) ile nasıl konuştuğunu kavramsal olarak anlayacağız, sonra bıraktığı izleri, ardından bu izlerden nasıl gerçek Sigma tespit mantığı ürettiğimizi işleyeceğiz.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

DCSync, Active Directory'nin en tehlikeli "meşru yeteneğinin kötüye kullanımıdır". Anlamak için önce normal işleyişe bakmak gerekir: Bir domain'de birden fazla domain controller olduğunda, bu DC'ler kendi aralarında sürekli veri senkronize eder. Bir kullanıcının şifresi bir DC'de değiştiğinde, bu değişikliğin diğer tüm DC'lere yayılması gerekir. Bu yayılım (replication) **MS-DRSR** (Directory Replication Service Remote Protocol) adlı protokol üzerinden gerçekleşir. İşin kritik noktası: replikasyon sırasında yalnızca metadata değil, kullanıcıların **parola hash'leri** de (NTLM hash, Kerberos anahtarları, hatta bazı durumlarda geçmiş parolalar) DC'ler arasında aktarılır. Yani MS-DRSR, tasarım gereği "bana kimlik bilgilerini ver" diyebilen bir protokoldür.

DCSync'in özü şudur: Saldırgan, **kendisini bir domain controller gibi göstererek** gerçek bir DC'ye "hey, ben de bir DC'yim, şu kullanıcının (veya krbtgt'nin, ya da tüm kullanıcıların) replikasyon verisini bana gönder" der. DC bu isteği, isteği yapan principal'ın yeterli yetkisi varsa hiç sorgulamadan yerine getirir. Yani saldırganın DC'nin diskine dokunmasına, üzerine kod çalıştırmasına, LSASS belleğini okumasına gerek yoktur. Uzaktan, sadece bir RPC çağrısıyla, herhangi bir kullanıcının parola hash'ini "resmi kanaldan" ister. Bu yüzden DCSync son derece "sessiz"dir — DC üzerinde klasik bir malware/mimikatz artefaktı bırakmaz.

**İstismar edilen şey iki katmanlıdır:**

1. **Yetki katmanı:** Bu replikasyon isteğini yapabilmek için principal'ın AD üzerinde belirli genişletilmiş haklara (extended rights) sahip olması gerekir: `DS-Replication-Get-Changes` (GUID `1131f6aa-...`), `DS-Replication-Get-Changes-All` (GUID `1131f6ad-...`) ve bazı senaryolarda `DS-Replication-Get-Changes-In-Filtered-Set`. Normalde bu haklar yalnızca Domain Admins, Enterprise Admins ve domain controller hesaplarında bulunur. Saldırgan ya bu ayrıcalıklı hesaplardan birini ele geçirmiştir ya da — daha sinsi olanı — normal bir kullanıcı/hesap nesnesine bu hakları **kalıcılık (persistence)** için arka kapı olarak eklemiştir.

2. **Protokol katmanı:** İstek `DRSGetNCChanges` adlı MS-DRSR operasyonu (opcode) üzerinden yapılır. Bu operasyon MS-DRSR interface'inin UUID'si olan `e3514235-4b06-11d1-ab04-00c04fc2dcd2` altında çağrılır.

Saldırgan açısından DCSync tipik olarak iki amaca hizmet eder: (a) **krbtgt hesabının hash'ini** çalıp Golden Ticket üretmek — bu, domain'in tam ve kalıcı kontrolü demektir; (b) yüksek değerli hesapların hash'lerini toplayıp lateral movement / pass-the-hash yapmak. DCShadow ise aynı MS-DRSR protokolünü ters yönde, yani AD'ye sahte veri **yazmak** için kullanan kardeş tekniktir; ikisi de aynı log kaynaklarında yankılanır.

Savunmacı için can alıcı kavrayış: **DCSync anomalisi "kimin, nereden, hangi protokolle replikasyon istediği" sorusunda gizlidir.** Meşru replikasyonu yapan sadece DC hesaplarıdır ve bunu yalnızca diğer DC'lerle yaparlar. Bir iş istasyonundan, bir kullanıcı hesabı adına, bir DC'ye gelen replikasyon isteği doğası gereği anormaldir.

---

## 2. Bıraktığı izler / artefaktlar

DCSync "diske dokunmayan" bir teknik olduğu için klasik dosya/registry artefaktları zayıftır; asıl izler **kimlik ve ağ katmanındadır**. İzleri dört kaynakta toplayabiliriz:

### a) Directory Service erişim logları (DC üzerinde)
En doğrudan iz, replikasyon hakkının kullanılmasıdır. `Audit Directory Service Access` politikası açıkken, replikasyon extended right'ları için erişim denetim olayları üretilebilir. İzlenecek genişletilmiş hak GUID'leri:
- `DS-Replication-Get-Changes` → `1131f6aa-9c07-11d1-f79f-00c04fc2dcd2`
- `DS-Replication-Get-Changes-All` → `1131f6ad-9c07-11d1-f79f-00c04fc2dcd2`

Bu GUID'lere yapılan erişimin, DC olmayan (non-DC) bir principal tarafından gerçekleştirilmesi en güçlü sinyaldir.

### b) RPC / MS-DRSR ağ ve firewall izleri
DCSync bir uzak RPC çağrısıdır. Interface UUID `e3514235-4b06-11d1-ab04-00c04fc2dcd2` (DRSUAPI) üzerinden gelen çağrılar, özellikle "tehlikeli" opcode'lar (`DRSGetNCChanges` gibi — 0, 1 ve 12 dışındaki opcode'lar) DC olmayan kaynaklardan geldiğinde şüphelidir. Zero Networks **RPC Firewall** gibi bir enstrümantasyon kurulduğunda bu çağrılar `RPCFW` EventLog'unda, örneğin `EventID: 3` altında, `InterfaceUuid` ve kaynak IP alanlarıyla kayıt altına alınır. Bu, aşağıdaki gerçek Sigma kuralının tam olarak demirlendiği yerdir.

### c) Directory Service değişiklik logları (persistence/backdoor izi)
DCSync hakkının bir kullanıcıya **arka kapı** olarak verilmesi ayrı bir artefakttır. Birisi PowerView'ın `Add-DomainObjectAcl` cmdlet'i (veya `dsacls`, `Set-Acl`, ADSI) ile domain nesnesinin ACL'ine DCSync extended right ekliyorsa, `Audit Directory Service Changes` politikası açıkken **Security EventID 5136** (bir directory service nesnesi değiştirildi) üretilir. Bu olayda `AttributeLDAPDisplayName` = `ntSecurityDescriptor` olur ve yeni SDDL değerinde replikasyon GUID'lerini içeren bir ACE görünür. Bu, olay gerçekleşmeden **önce** yakalama şansı verdiği için son derece değerlidir.

### d) Endpoint / komut satırı ve AV izleri
Saldırı aracı iz bırakabilir:
- **Process creation (Sysmon EventID 1 / Security 4688):** `lsadump::dcsync` (mimikatz), `/domain:` ve `/user:krbtgt` parametreleri; PowerShell tarafında `Invoke-Mimikatz`, PowerView `Add-DomainObjectAcl ... -Rights DCSync` desenleri.
- **Antivirus imzaları:** Kimlik hırsızlığı araçları AV tarafından yakalandığında imza adında `DCSync`, `PWS`, `Creddump`, `DumpCreds` gibi ifadeler görülür. Bu, aracın hangi aşamada olduğunu gösterir ve göz ardı edilmemelidir.
- **Ağ:** Kaynak host ile DC arasında `TCP/135` (RPC Endpoint Mapper) ve dinamik yüksek RPC portları üzerinden DRSUAPI trafiği; kaynak DC olmayan bir sistem ise anormaldir.

**Özet artefakt tablosu:**

| Kaynak | Anahtar alan / ID | Ne gösterir |
|---|---|---|
| RPC Firewall (`RPCFW`) | `EventID 3`, `InterfaceUuid e3514235-...` | Non-DC'den MS-DRSR çağrısı |
| Security (DC) | `4662` + replikasyon GUID'leri | Replikasyon hakkı kullanıldı |
| Security (DC) | `5136` + `ntSecurityDescriptor` | DCSync hakkı ACL'e eklendi (backdoor) |
| Sysmon / Security | `1` / `4688` komut satırı | Araç çalıştırıldı |
| Antivirus | `Signature` = `*DCSync*`, `PWS*` | Kimlik dökme aracı algılandı |

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Şimdi bu artefaktları verilen **gerçek Sigma kurallarına** bağlayalım. Her kuralın mantığını Türkçe açıklayıp, sonunda basit Sigma-benzeri örnekler vereceğiz.

### 3.1 Ana kural: "Possible DCSync Attack" (id `56fda488-...`)
Bu, DCSync tespitinin çekirdeğidir. Mantığı çok net:

- **logsource:** `product: rpc_firewall`, `category: application`. Yani bu kural, RPC Firewall enstrümantasyonu kurulu ve tüm process'lere uygulanmış olmasını **gerektirir**. Bu bir ön koşuldur (`definition` alanında açıkça yazar): DRSR UUID `e3514235-4b06-11d1-ab04-00c04fc2dcd2` yalnızca "tehlikeli" opcode'lar için (0, 1 veya 12 **hariç**) ve yalnızca güvenilir IP'lerden (yani DC'lerden) izinli olacak şekilde yapılandırılır.
- **detection.selection:**
  - `EventLog: RPCFW`
  - `EventID: 3`
  - `InterfaceUuid: e3514235-4b06-11d1-ab04-00c04fc2dcd2`

Buradaki dahiyane nokta şudur: RPC Firewall zaten "sadece DC'lerin bu interface'i kullanmasına izin ver" diye yapılandırıldığından, `RPCFW EventID 3` (bloklanan/kural tetikleyen çağrı) olayı **non-DC bir host'tan** MS-DRSR çağrısı geldiğinde üretilir. Yani kuralın kendisi basit görünse de, gücü altyapı yapılandırmasından gelir: meşru replikasyon (DC→DC) izinlidir ve gürültü üretmez; sadece anormal olan (workstation → DC) yankılanır. Bu kural `attack.t1033` ve `attack.discovery` ile etiketlidir ve DCSync/DCShadow'u birlikte kapsar.

**Neye alarm verilir:** DC olmayan bir kaynaktan, DRSUAPI interface UUID'sine yapılan, tehlikeli opcode içeren tek bir RPC çağrısı bile → yüksek öncelikli alarm. Eşik pratikte "1" olabilir, çünkü bu trafiğin meşru karşılığı yoktur.

### 3.2 ACL backdoor kuralı: "Powerview Add-DomainObjectAcl DCSync AD Extend Right" (id `2c99737c-...`)
Bu kural, saldırının **hazırlık/persistence** aşamasını yakalar: Birinin normal bir kullanıcıya DCSync hakkını arka kapı olarak vermesi.

- **logsource:** `product: windows`, `service: security`. `definition` alanı kritik ön koşulu söyler: `Audit Directory Service Changes` politikası **açık** olmalı ve olaylar yalnızca SACL yapılandırılmış nesneler için üretilir. Yani domain nesnesinde uygun SACL yoksa bu olay hiç doğmaz — bu, kuralın uygulanabilirliği için savunmacının önceden yapması gereken iştir.
- **Mantık:** Bir directory service nesnesinin `ntSecurityDescriptor` özniteliği değiştirildiğinde (EventID 5136), yeni descriptor içinde replikasyon extended right GUID'lerini (`1131f6aa-...` ve `1131f6ad-...`) içeren bir ACE eklenmişse alarm üretilir. Kural `attack.privilege-escalation`, `attack.persistence`, `attack.t1098` ile etiketlidir.

**Neye alarm verilir:** Bir hesaba/nesneye replikasyon hakkı ekleyen ACL değişikliği. Bu, DCSync gerçekleşmeden önce yakalama fırsatıdır.

### 3.3 Destekleyici kurallar
- **"Antivirus - Password Dumper Signature" (id `78cc2dd2-...`):** `logsource: category: antivirus`. `Signature|startswith: 'PWS'` veya `Signature|contains` listesinde `'DCSync'`, `'Creddump'`, `'DumpCreds'`, `'Certify'` geçiyorsa alarm. Not olarak: AV bloklamış olsa bile "nasıl buraya geldi?" diye araştırılmalı ve gerekirse parolalar sıfırlanmalıdır. Bu, `attack.t1003` / `attack.t1003.006` ailesini destekler.
- **"Malicious PowerShell Commandlets" (id `02030f2f-...`):** Process creation logunda bilinen saldırı framework cmdlet adları (PowerView, Invoke-Mimikatz vb.). DCSync backdoor'u genellikle PowerView ile kurulduğu için bu, 3.2'yi tamamlar.
- **"Operator Bloopers Cobalt Strike Commands" (id `647c7b9e-...`):** Doğrudan DCSync değildir ama aynı operatörün C2 (Cobalt Strike) kullandığını ele veren "yanlışlıkla CMD'ye yazılmış" komutları yakalar — DCSync'in etrafındaki operasyonel gürültüyü tespit eder.

### 3.4 Basit Sigma-benzeri tespit mantığı örnekleri

**Örnek 1 — Non-DC'den MS-DRSR çağrısı (ana kurala demirli):**
```yaml
title: DCSync - Non-DC MS-DRSR RPC Call
logsource:
    product: rpc_firewall
    category: application
detection:
    selection:
        EventLog: RPCFW
        EventID: 3
        InterfaceUuid: 'e3514235-4b06-11d1-ab04-00c04fc2dcd2'
    condition: selection
level: high
# Not: RPC Firewall, DRSUAPI'yi yalnızca DC IP'lerinden izinli
# olacak şekilde yapılandırılmış olmalı. Bu olay = izinsiz kaynak.
```

**Örnek 2 — DCSync hakkının ACL'e eklenmesi (backdoor tespiti):**
```yaml
title: DCSync Right Added to Object ACL
logsource:
    product: windows
    service: security
detection:
    selection:
        EventID: 5136
        AttributeLDAPDisplayName: 'ntSecurityDescriptor'
    replication_guids:
        AttributeValue|contains:
            - '1131f6aa-9c07-11d1-f79f-00c04fc2dcd2'   # Get-Changes
            - '1131f6ad-9c07-11d1-f79f-00c04fc2dcd2'   # Get-Changes-All
    condition: selection and replication_guids
level: high
# Ön koşul: Audit Directory Service Changes açık + domain nesnesinde SACL.
```

Bu iki örnek birlikte "hazırlık" (ACL eklendi, EventID 5136) ve "icra" (replikasyon çağrısı yapıldı, RPCFW EventID 3) aşamalarını kapatır — savunmada katmanlı görünürlük budur.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırgan tespiti nasıl atlatmaya çalışır?

1. **Meşru bir DC hesabı kullanmak:** DCSync'i ele geçirilmiş bir gerçek domain controller hesabı (`MACHINE$`) üzerinden yaparsa, "non-DC'den geldi" mantığı boşa düşer, çünkü kaynak gerçekten bir DC gibi görünür.
   **Karşı-tespit:** DC hesaplarının davranış temelini (baseline) çıkarın. Bir DC'nin *hangi* diğer DC'lerle, *hangi* saatlerde replike ettiği bellidir. Beklenmedik bir DC-DC replikasyon deseni, yeni eklenmiş bir DC nesnesi (`nTDSDSA` objesi oluşumu — DCShadow habercisi), ya da replikasyon topolojisine uymayan bağlantı anomali sayılır.

2. **RPC Firewall'ın olmaması:** Ana kural (`56fda488`) RPC Firewall enstrümantasyonuna bağlıdır; birçok ortamda bu kurulu değildir.
   **Karşı-tespit:** Bu durumda tespiti **Security EventID 4662**'ye kaydırın: replikasyon GUID'lerine (`1131f6aa`, `1131f6ad`) yapılan `Object Access` olaylarını, `SubjectUserName` DC hesabı (`*$` ve bilinen DC listesinde) **olmayan** principal'larla filtreleyin. Bu, RPC Firewall gerektirmeyen yaygın alternatif tespittir.

3. **ACL değişikliğini gizlemek:** Backdoor hakkını doğrudan iyi bilinen GUID yerine dolaylı yollarla (grup üyeliği, iç içe ACE'ler) vermek.
   **Karşı-tespit:** Periyodik ACL denetimi — domain nesnesi üzerinde replikasyon hakkına sahip *tüm* principal'ları düzenli listeleyip (BloodHound/`Get-ObjectAcl`) beklenen kısa listeyle (Domain Admins, Enterprise Admins, DC'ler, DPM/AD connector servis hesapları) karşılaştırın. Liste dışı her principal incelenir.

4. **"Yavaş ve az" (low & slow):** Tek bir hedef hesabı, uzun aralıklarla çekmek, eşik bazlı alarmları uyandırmamak için.
   **Karşı-tespit:** DCSync için eşik "1" olmalıdır — tek bir non-DC replikasyon çağrısı bile meşru karşılığı olmadığından anlamlıdır. Sayıya değil, *kaynağın DC olup olmamasına* dayanın.

### Tipik false positive kaynakları ve nasıl ayıklanır

- **Meşru replikasyon (DC → DC):** En büyük gürültü kaynağı. Ayıklama: `SubjectUserName`/kaynak IP'nin bilinen DC hesabı/DC IP listesinde olmasıyla whitelist. Ana Sigma kuralı bunu zaten RPC Firewall yapılandırmasıyla çözer (yalnızca güvenilir/DC IP'leri izinli).
- **Azure AD Connect / AAD Sync sunucusu:** Bu servis hesabı, dizin senkronizasyonu için `DS-Replication-Get-Changes` haklarına meşru olarak sahiptir ve replikasyon yapar. Ayıklama: AAD Connect servis hesabını ve host'unu bilinen istisna olarak belgeleyip whitelist edin — ama bu hesabı ayrı ve sıkı izleyin, çünkü değerli bir hedeftir.
- **Yedekleme / DR / izleme çözümleri:** Bazı AD yedekleme veya izleme ürünleri replikasyon API'lerini kullanır. Ayıklama: envanterleyip host+hesap bazında istisna tanımlayın; istisnayı "hesap + kaynak host + hedef DC" üçlüsüne daraltın, sadece hesaba değil.
- **AV imza kuralı gürültüsü:** `Signature contains 'DCSync'` gibi kurallar, EICAR testleri, güvenlik ekibinin kendi pentest/tatbikat aktiviteleri veya imza adı benzerliğiyle tetiklenebilir. Ayıklama: onaylı pentest pencerelerini ve host'ları bağıştan (allowlist) geçirin, ama bloklanan gerçek algıları yine de "nasıl geldi?" diye kök-neden analizine alın.
- **Yeni DC tanıtımı (dcpromo):** Yeni bir domain controller kurulurken meşru replikasyon ve ACL/topoloji değişiklikleri olur, bu da 5136 ve replikasyon olaylarını tetikler. Ayıklama: değişiklik yönetimi (change management) kayıtlarıyla korelasyon — planlı bir DC promosyonu varsa olay beklenendir; yoksa DCShadow şüphesiyle incelenir.

### Savunmacı için pratik öncelik sırası
1. **En yüksek değer, en düşük gürültü:** ACL backdoor tespiti (EventID 5136 + replikasyon GUID'leri) — nadiren meşru olur, saldırıyı erken yakalar.
2. **İcra tespiti:** RPC Firewall varsa `RPCFW EventID 3` (kural `56fda488`); yoksa `4662` + replikasyon GUID'leri + non-DC principal filtresi.
3. **Destek katmanı:** AV imza kuralı (`78cc2dd2`) ve PowerShell/PowerView cmdlet tespiti (`02030f2f`) ile aracın çalıştığını doğrulayın.
4. **Baseline & hijyen:** Replikasyon hakkına sahip principal listesini küçük ve denetlenmiş tutun; krbtgt ele geçirilmiş şüphesinde krbtgt parolasını (iki kez, replikasyon aralığıyla) sıfırlayın.

Sonuç olarak DCSync, "meşru protokolün kötüye kullanımı" sınıfının ders kitabı örneğidir: DC üzerinde iz bırakmadan en değerli sırrı (krbtgt) çalabildiği için savunma, dosya/malware izlerine değil, **kimlik ve replikasyon davranışına** dayanmalıdır. Doğru soruyu sormak yeter: "Bu replikasyonu isteyen gerçekten bir DC mi, ve bu hakka sahip olmayı hak ediyor mu?"
