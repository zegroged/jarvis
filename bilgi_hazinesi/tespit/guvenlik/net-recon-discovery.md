# Domain Recon / Discovery — Tespiti

> Saha notu. Bir kurumun Active Directory ortamında "keşif" (discovery) gürültüsünü gerçek ihlalden ayırmak, bir SOC'un olgunluğunu en net gösteren yerlerden biridir. Çünkü keşif komutları hem saldırganın ilk 30 dakikasında hem de her IT yöneticisinin sıradan gününde çalışır. Bu metin, "4769'a bak" seviyesinin ötesinde, bu ayrımı nasıl yaptığımı anlatıyor.

## 1. Özet: saldırı + naif tespit

Bir saldırgan bir uç noktada kod çalıştırma (execution) elde ettiği anda, neredeyse refleks olarak ortamı tanımaya başlar. MITRE ATT&CK'te bu, **Discovery (TA0007)** taktiği altında bir avuç tekniğe karşılık gelir: Account Discovery (T1087), Domain Trust Discovery (T1482), Permission Groups Discovery (T1069), System Network Configuration Discovery (T1016), Remote System Discovery (T1018), System Owner/User Discovery (T1033) ve Process Discovery (T1057). Amaç basittir: "Ben neredeyim, kimim, bu domain nasıl kurulmuş, Domain Admins kim, hangi makinelere gidebilirim, güven ilişkileri neler?" Bu bilgi olmadan saldırgan kör ilerler; bu bilgiyle yanal hareket (lateral movement) ve ayrıcalık yükseltme (privilege escalation) hedeflerini seçer.

Klasik yerli araçlar (living-off-the-land) burada başrolde: `net user`, `net group /domain`, `net group "Domain Admins" /domain`, `net localgroup administrators`, `nltest /domain_trusts`, `nltest /dclist:`, `dsquery`, `whoami /all`, `wmic`, `systeminfo`, `arp -a`, `ipconfig /all`, `route print`, `net view`. Bunların üzerine "framework" katmanı gelir: BloodHound'un toplayıcısı **SharpHound**, PowerView (`Get-NetGroup`, `Get-NetComputer`, `Invoke-ShareFinder`), ADRecon ve Cobalt Strike / Sliver gibi C2'lerin dahili keşif komutları. Framework'ler farkı, elle çalışan bir yöneticinin asla üretmeyeceği hacim ve sistematiktir — saniyeler içinde tüm dizini tarayan LDAP sorguları.

Naif tespit herkesin bildiği yerdir ve iki koldan gider. Birincisi **process_creation** (Sysmon Event ID 1 / Windows 4688): `Image` ya da `CommandLine` alanında `net.exe`, `nltest.exe`, `dsquery.exe`, `whoami.exe`, `net1.exe`, `\domain` veya `Domain Admins` gibi dizeleri yakalamak. Sigma tarafında bunun kanonik örneği yukarıdaki gibi **Recon Command Output Piped To Findstr.EXE** (`ccb5742c-...`, `attack.discovery`, `attack.t1057`) kuralıdır — recon çıktısını `findstr`'a boru ile aktaran cmd.exe kalıbını arar. İkincisi **kimlik/dizin katmanı**: LDAP tarafında Directory Service Access denetimi (Event 4662), Kerberos servis bileti talepleri (4769), ve DC'de anormal LDAP sorgu hacmi. Bu iki katman, "birileri keşif yapıyor" sinyalinin ham malzemesidir.

## 2. Naif tespit neden yetmez — değer burada başlar

`CommandLine|contains: 'net group'` yazan bir kural sahada üç sebepten çöker.

**Birincisi: temel oran problemi (base rate).** Keşif komutları meşru IT operasyonunun kanıdır. Bir logon script `net use` çalıştırır. Bir yardım masası teknisyeni gün boyu `net user <kullanıcı> /domain` ile hesap durumu bakar. SCCM/MECM ajanları `nltest`, `whoami`, WMI envanter sorguları üretir. Login sırasında GPO'lar `gpresult`, `systeminfo` tetikler. Bir orta ölçekli kurumda `net.exe` günde on binlerce kez çalışır. Ham dize eşleşmesi bu denizde bir alarm kanalını saniyeler içinde doldurur ve analist onu sessize alır — ölü kural (dead rule) doğar. Kural teknik olarak "çalışıyor" ama operasyonel olarak kör.

**İkincisi: kolay atlatma.** `net.exe` yerine `net1.exe` çağırmak (Windows'un kendisi bazen bunu yapar, saldırgan da bilir). `net` yerine PowerShell'in .NET API'lerini kullanmak: `([adsisearcher]"(objectClass=group)").FindAll()` ya da `Get-ADGroupMember` — hiç `net.exe` doğmaz, sadece LDAP trafiği çıkar. SharpHound zaten hiç `net.exe` kullanmaz; doğrudan LDAP ve SAMR/NetSessionEnum çağrıları yapar. Yani en tehlikeli keşif aracı, komut satırı imza kuralına hiç değmez. `whoami` yerine `%USERNAME%` ve `whoami /all` yerine token'ı doğrudan API ile okumak da mümkün. String tabanlı process kuralları, birinci sınıf tehdit aktörünün radar altından geçtiği katmandır.

**Üçüncüsü: 4769/4662'nin yorumlanamazlığı.** Kimlik katmanına inince başka bir duvar var. Event 4769 (Kerberos service ticket) her normal kaynak erişiminde üretilir — günde milyonlarca. Kerberoasting'i (ki bu Credential Access, saf discovery değil) yakalamak için 4769'a "RC4 (0x17) şifreleme + hizmet hesabı" filtresi koyabilirsin ama saf grup/hesap keşfi 4769'da neredeyse görünmez. Event 4662 (bir dizin nesnesine erişim) teorik olarak LDAP keşfini görür, ama **varsayılan olarak işe yarar biçimde loglanmaz**: SACL'ler (System Access Control List) nesnelere elle konmadıkça 4662 üretilmez ve üretilse bile GUID formatındaki `Properties` alanı ham halde okunamaz. Yani "4662'ye bak" tavsiyesi, çoğu ortamda boş bir tabloya bakmak demektir.

Değer tam burada başlıyor: tek başına hiçbir keşif sinyali güvenilir değil. İş, onları **bağlamak**.

## 3. Korelasyon zinciri — asıl değer

Keşif tek başına zayıf sinyaldir çünkü meşru trafikle ayırt edilemez. Onu yüksek-güven tespitine çeviren şey, **kim, nereden, ne kadar hızlı ve neyin ardından** sorularının aynı anda cevaplanmasıdır. Sahada güvendiğim birkaç somut zincir:

**Zincir A — Yeni süreç sülalesinden patlayan keşif.** Tek bir `net group /domain` önemsizdir. Ama şu kalıp değildir: bir **Office uygulaması** (`WINWORD.EXE`, `EXCEL.EXE`) ya da bir tarayıcı süreci ebeveyni altında doğan `cmd.exe`/`powershell.exe`, ve o çocuk sürecin **90 saniye içinde** `whoami /all` + `net group "Domain Admins" /domain` + `nltest /domain_trusts` üçlüsünü sırayla çalıştırması. Burada üç boyut birleşir: (1) anormal ebeveyn-çocuk soyu (bir belge neden AD güven ilişkisi sorar?), (2) recon komutlarının **kısa pencerede kümelenmesi**, (3) sistematik sıralama — bir insan bunları bu hızda yazmaz. Yukarıdaki Sigma **ClickOnce child process** kuralının mantığı da tam bu — şüpheli ebeveyn + `nltest.exe`/`net.exe`/`net1.exe` çocuğu. Ebeveyn imzasını değiştirin, kalıp aynı kalır.

**Zincir B — Discovery'yi credential access ve lateral movement'a bağlamak.** Gerçek ihlal, keşifte durmaz. Yüksek güven şu üçlü zamansal desende gelir: `T0`'da bir hosttan **SharpHound-benzeri LDAP patlaması** (kısa sürede yüzlerce dizin nesnesi sorgusu, tek kaynaktan) → `T+dakikalar` içinde aynı hosttan **4769 RC4 bileti talepleri** birden çok SPN'ye (Kerberoasting denemesi) → `T+onlarca dakika` içinde **farklı bir hosta** 4624 Type 3 / 4648 (explicit credentials) ile oturum. Yani: keşif (T1087/T1482) + credential harvesting (T1558.003) + lateral movement (T1021) aynı kaynaktan zincirlenmiş. Her adım tek başına gürültü; ama "aynı kaynak kimlik, 20 dakikalık pencere, keşif→credential→pivot" sırası neredeyse hiç meşru üretilmez.

**Zincir C — Coğrafya/rol tutarsızlığı.** `net group "Domain Admins" /domain` komutunun kim tarafından, nereden çalıştığı her şeyi değiştirir. Bir **workstation'dan** (sunucu değil) çalışan, **standart bir kullanıcı** bağlamındaki, IT/admin OU'suna ait olmayan bir hesabın Domain Admins üyeliğini sorması — bu, aynı komutun bir jump server'daki yönetici hesabından çalışmasından tamamen farklıdır. Korelasyon: `TargetUserName` + `SourceHostname` + "host bir sunucu mu, workstation mı" + "hesap yetkili yönetim grubunda mı". Aynı bytelar, farklı bağlam, farklı yargı.

**Zincir D — SharpHound imza-üstü davranışı.** SharpHound'u process ismiyle yakalamaya çalışmak (yeniden derlenir, adı değişir) beyhude. Onu **davranışla** yakalarsın: tek bir kaynaktan **kısa pencerede çok sayıda farklı hosta** yönelen **SMB oturum enumerasyonu** (NetSessionEnum / SrvsvcNetSessEnum) ve SAMR sorguları. Ağ tarafında bu, `445/tcp` üzerinde onlarca-yüzlerce hedefli patlama olarak görünür; kimlik tarafında ise 4624/4634 seli. "Bir host, 5 dakikada 200 farklı makineye SMB oturumu açıyor" — bu bir yönetici değildir, bir toplayıcıdır.

**Zincir E — Trust discovery'nin öncü göstergesi olması.** `nltest /domain_trusts /all_trusts` ya da LDAP'ta `trustedDomain` nesnelerinin sorgulanması, tek başına nadir ama sıradan bir yönetici işi de olabilir. Yüksek değeri, **sıralamadaki yeri** verir: bir aktör tipik olarak önce yerel bağlamı (`whoami`, `net user`), sonra domain bağlamını (`net group /domain`), en son **güven ilişkilerini** sorar — çünkü trust discovery, mevcut domain'i tükettikten sonra "nereye daha gidebilirim, hangi forest'a atlayabilirim" sorusudur. Yani trust sorgusu, çoğu zaman keşif dizisinin **sonuna** oturur. Bir hosttan aynı gün içinde önce hesap/grup keşfi sonra trust keşfi görmek, tek bir izole trust sorgusundan çok daha anlamlıdır — çünkü bu, bir kampanyanın olgunlaşan bir hattını gösterir, meraklı bir admini değil.

Bu zincirlerin ortak paydası: **tek sinyal = düşük güven, zamansal+bağlamsal kümelenme = yüksek güven.** Google'ın tek sayfada vermediği kısım budur; çünkü bu, kural değil, senin ortamının topolojisini bilmektir. Bu yüzden aynı kural seti iki farklı kurumda farklı ayarlanır: bir kurumda `nltest` günlük operasyon, diğerinde neredeyse hiç görülmeyen bir olaydır — ve o "hiç görülmeyenlik" başlı başına en değerli sinyaldir. Baseline'ı bilmeden hiçbir recon kuralı işe yaramaz.

## 4. False positive gerçeği ve triage yargısı

Bu alarmları meşru üretenlerin listesi uzun ve her ortamda farklıdır. Sahada tekrar tekrar gördüklerim:

- **SCCM / MECM ve envanter ajanları:** WMI sorguları, `nltest`, `systeminfo`, donanım/yazılım envanteri. Genellikle `SYSTEM` bağlamında, belirli ajan süreçlerinden, düzenli aralıklarla. Zamanlaması ve ebeveyni ayırt edicidir.
- **Vuln scanner'lar (Nessus/Tenable, Qualys, Rapid7):** Kimlikli tarama (authenticated scan) yaparken bir servis hesabıyla ağın büyük kısmına SMB/LDAP/WMI ile bağlanır. Bu, SharpHound'a **davranışsal olarak çok benzer** — çok sayıda hosta hızlı bağlantı. Ayrım: bilinen scanner kaynak IP'leri, bilinen servis hesabı, planlı pencere (cumartesi 02:00 gibi), ve tam ağ aralığını **sistematik/tam** taraması (saldırgan seçici olur, scanner kapsamlıdır).
- **Yedekleme ve DR yazılımı, keşif/asset-discovery araçları (Lansweeper, PDQ, Device42):** Sürekli ağ/AD envanteri. Genelde sabit birkaç kaynaktan.
- **Yönetici scriptleri ve logon script'leri:** `net use`, `net group`, `gpresult`. Kullanıcı login dalgalarında (sabah 08:00-09:30) kütlesel görünür.
- **Yardım masası ve identity yönetim araçları:** Hesap durumu bakan `net user /domain` çağrıları.
- **Güvenlik ürünlerinin kendisi:** EDR'ların ve BloodHound Enterprise / purple-team araçlarının planlı toplaması. Kendi kırmızı takımınız da FP kaynağıdır.

Kıdemli analistin gerçek/gürültü ayrımında sorduğu sorular, hep aynı sırayla:

1. **Kim?** Kaynak hesap bilinen bir servis/admin hesabı mı, yoksa bir insan son-kullanıcı hesabı mı? Servis hesabının recon yapması genelde beklenendir; bir muhasebe kullanıcısının Domain Admins sorması değildir.
2. **Nereden?** Kaynak host bir yönetim sunucusu/jump box/scanner mı, yoksa sıradan bir workstation mı? En yüksek sinyal: standart bir workstation'dan gelen dizin-geneli enumerasyon.
3. **Ebeveyn ne?** Recon sürecinin ebeveyn zinciri normal mi (`explorer.exe` → `cmd.exe`, admin oturumu) yoksa anormal mi (`WINWORD.EXE`/`mshta.exe`/`rundll32.exe` → `powershell.exe`)? Anormal soy, tek başına önceliği yükseltir.
4. **Ne kadar ve ne hızda?** Tek komut mu, yoksa kısa pencerede kümelenmiş bir dizi komut/sorgu mu? İnsan hızı mı, otomasyon hızı mı?
5. **Ardından ne geldi?** Recon'dan sonra aynı kaynaktan credential access (4769 RC4 patlaması, LSASS erişimi) veya lateral movement (yeni hosta 4624 Type 3) var mı?

Pratik bir triage kısayolu: **ilk 30 saniyede "bu host bir sunucu mu, workstation mı ve hesap yönetim grubunda mı" ikilisine bakarım.** Bu iki bit, alarmların çoğunu anında ya "muhtemel operasyon" ya da "hemen bak" kutusuna ayırır. Bir jump server'daki `svc_backup` hesabının `net view` çalıştırması ile bir kullanıcı laptopundaki `jsmith` hesabının aynısını yapması, aynı olay tipi olsa da iki farklı gerçekliktir. İkinci bit — hesabın son 24 saatte başka anormal davranışı var mı (yeni bir hosttan ilk kez oturum, çalışma saati dışı aktivite, EDR'da başka düşük-skor sinyal) — üçüncü baktığım şeydir; çünkü recon nadiren tek başına gelir, genelde daha büyük bir davranış sapmasının parçasıdır.

Çoklu alarm geldiğinde **önce kaynağa (host+hesap) göre gruplayıp zaman çizgisine dizerim** — tek tek alarmlara değil. On "net group" alarmı ayrı ayrı düşük önceliklidir; ama hepsi aynı hosttan, 4 dakikada, bir Office ebeveyninden ve ardından bir SMB patlamasıyla geliyorsa, bu tek bir yüksek-öncelikli olaydır. Triage'ın kalbi: **entity-centric bakış** (kaynak varlığı merkeze al), zaman-serisi kümeleme, ve "sonrasında ne oldu" penceresi. Bilinen scanner/SCCM kaynaklarını bir allowlist'e almak (kaynak IP + hesap + zaman penceresi kombinasyonuyla, sadece isimle değil) FP'nin %80'ini eritir; kalan %20 gerçek yargı ister.

## 5. Kaçınma → karşı-tespit — derin kedi-fare

Kural dokümanında yazmayan atlatma yolları ve her birine ikinci-derece tespit:

**Atlatma 1: `net.exe`'yi hiç kullanmama.** Saldırgan `net group`/`net user` yerine doğrudan LDAP kullanır: `([adsisearcher]'...').FindAll()`, `System.DirectoryServices`, veya SharpHound'un ham LDAP'ı. Process komut satırında hiçbir recon dizesi çıkmaz.
→ **Karşı-tespit:** Katmanı değiştir. Process string'ini bırak, **LDAP telemetrisine** in. Windows'ta bunun için ya DC üzerinde **AD Directory Service Access denetimi (4662)** için nesnelere SACL koymak, ya da modern yol — **Microsoft Defender for Identity** / ETW tabanlı LDAP sensörleri — SharpHound'un imza LDAP filtrelerini (ör. `(objectCategory=...)` geniş taramaları) davranışsal yakalar. Anahtar sinyal: tek kaynaktan kısa sürede **anormal hacimde ve genişlikte** LDAP sorgusu. Hacim, aracın ismini gizlemeyi anlamsız kılar.

**Atlatma 2: Yavaşlatma (low and slow).** SharpHound'un `--Throttle`/`--Jitter` parametreleri toplamayı saatlere/günlere yayar; hacim tabanlı eşikler tetiklenmez.
→ **Karşı-tespit:** Sabit-pencere eşiği yerine **baseline'dan sapma**. Her hesap/host için normal LDAP sorgu profilini (tür ve hacim) öğren; günlük toplamda bile "bu hesap normalde 10 dizin nesnesi sorar, bugün 4000 sordu" sapması yakalanır. Ayrıca SharpHound'un topladığı **nesne çeşitliliği** (kullanıcılar+gruplar+bilgisayarlar+GPO'lar+güvenler+ACL'ler hepsi birden) tek bir meşru göreve nadiren uyar — çeşitlilik imzası hıza bağlı değildir.

**Atlatma 3: Encoded / obfuscated PowerShell.** `-EncodedCommand`, string birleştirme, alias'lar (`gm`, `iex`).
→ **Karşı-tespit:** **Script Block Logging (Event 4104)**. Encode edilmiş komut bile 4104'te decode edilmiş blok olarak loglanır (PowerShell v5+ ile). Burada `DirectorySearcher`, `FindAll`, `objectClass=group`, `NetSessionEnum` gibi **API-seviyesi** imzaları ararsın — komut satırında değil, çalıştırılan blokta. Ayrıca `-EncodedCommand` / `FromBase64String` kullanımının kendisi ikincil bir sinyaldir.

**Atlatma 4: LOLBIN ile dolaylı çalıştırma.** `net.exe` yerine `wmic`, `dsquery`, ya da recon'u bir imzalı ikili üzerinden proxy'lemek; ya da `findstr`'a boru yerine çıktıyı bir dosyaya/değişkene yazmak (Sigma `ccb5742c` findstr kuralını böyle atlatır).
→ **Karşı-tespit:** Findstr borusuna bağlı kalma; **çalıştırılan ikilinin kendisine + ebeveyn/soy bağlamına** odaklan. `nltest /domain_trusts`, `dsquery *`, `wmic ntdomain` gibi çağrılar çıktının nereye gittiğinden bağımsız yakalanmalı. Kritik nokta: findstr'a boru, kolaycı bir kural; gerçek tespit recon ikilisinin **anormal bağlamda** doğmasıdır.

**Atlatma 5: SAMR/NetSession yerine alternatif enum.** SharpHound `--CollectionMethod`'u değiştirip session yerine sadece ACL veya trust toplayabilir; SMB seli olmaz.
→ **Karşı-tespit:** Tek bir toplama metoduna bağlı imza kurma. Session (SMB), ACL/LDAP, ve trust (`nltest`/LDAP) her biri **ayrı** telemetri kanalında iz bırakır; bunları birleştiren **davranışsal korelasyon** (bkz. Zincir D) hangi metodun seçildiğinden bağımsız hedefe yaklaşır.

Kedi-fare'nin dersi şu: her atlatma bir katmanı kör eder ama **başka bir katmanda daha gürültülü** olur. `net.exe`'yi gizlersen LDAP'ta patlarsın; hacmi düşürürsen çeşitlilik ve süre-bazlı sapmada görünürsün; encode edersen 4104'te açılırsın. Tespit mimarisini **tek katmana** kurmamak — process + LDAP + ağ + kimlik — atlatmayı pahalılaştırır.

## 6. SIEM / saha gerçeği

**Ne varsayılan loglanmaz (ve bu her şeyi belirler):**

- **Process command line** varsayılan olarak 4688'de **yoktur**. `Administrative Templates → System → Audit Process Creation → Include command line` GPO'sunu açmadan, ya da Sysmon Event ID 1 kullanmadan, elinde sadece proses adı olur — `net.exe` görünür ama `net group "Domain Admins" /domain` görünmez. Recon tespitinin çoğu komut satırına dayandığından, bu ayar açık değilse tüm bölüm 3 çöker. **İlk kontrol edilecek şey budur.**
- **Sysmon** kurulu değilse Event 1/3/11 yok. Sysmon config'i de kritik: recon için Event ID 1 (process) şart, Event ID 3 (network) SharpHound SMB patlaması için değerli, ama agresif filtrelenmiş config'ler `net.exe`'yi "gürültü" diye eleyebilir — config'i doğrula.
- **PowerShell Script Block Logging (4104)** varsayılan kapalı. Açık değilse .NET/LDAP tabanlı keşif tamamen görünmez.
- **AD Directory Service Access (4662)** hem denetim politikası açık olmalı **hem de** nesnelerde SACL bulunmalı. İkisi olmadan LDAP keşfi DC loglarında yok. Ayrıca 4662 üretilse bile `Properties` alanı **schema GUID** formatındadır — okunması için GUID→isim eşlemesi gerekir, ki bu enrichment çoğu SIEM'de elle kurulur.
- **NetSessionEnum / SAMR** çağrıları standart Windows Security log'da düzgün görünmez; Defender for Identity gibi özel sensör ya da ETW gerektirir.

**Field mapping tuzakları:** Sysmon `Image`/`CommandLine`/`ParentImage` ile Windows 4688 `NewProcessName`/`ParentProcessName` (ve komut satırı `ProcessCommandLine` olarak) aynı şeyi farklı adlarla taşır — normalize edilmeden ikisine birden yazılan kural birinde patlar. Sigma bunu `logsource: category: process_creation` soyutlamasıyla çözer ama backend eşlemesi (pipeline) doğru olmalı. `nltest` bazen `net1.exe` gibi kısaltmalarla veya farklı casing ile gelir; `contains` yerine `endswith: '\net.exe'` kullanmak path-spoofing'e karşı daha sağlam.

**Splunk vs Sentinel vs Elastic farkı:**
- **Splunk:** Ham log + `tstats`/data model (özellikle Endpoint ve Authentication data model'leri) recon korelasyonunun bel kemiği. Zamansal zincir için `transaction` yerine `stats ... by src_host, user` + `bin _time span=5m` ile pencereleme daha ölçeklenir. Risk-based alerting (RBA) burada çok güçlü: her zayıf recon sinyaline küçük risk skoru ver, aynı entity'de skor eşiği aşınca tek alarm üret — bölüm 4'teki entity-centric yargıyı otomatikleştirir.
- **Microsoft Sentinel:** AD/kimlik telemetrisi için doğal avantaj — **Defender for Identity** sinyalleri (SharpHound, recon, LDAP anomali) hazır gelir ve KQL ile `SecurityEvent` + `IdentityDirectoryEvents` + `DeviceProcessEvents` (MDE) join'lenir. Zamansal korelasyon için `bin(TimeGenerated, 5m)` ve entity mapping'i UEBA'ya bağlamak güçlüdür. Tuzak: MDE ve Security Event alan adları (`InitiatingProcessCommandLine` vs `ProcessCommandLine`) farklı tablolarda farklı — join yaparken karıştırılır.
- **Elastic:** ECS normalizasyonu (`process.command_line`, `process.parent.name`, `user.name`, `source.ip`) çapraz-kaynak korelasyonu kolaylaştırır ama Sysmon/Winlogbeat pipeline'ının ECS'e doğru map'lemesi şart. EQL (Event Query Language) `sequence by host.id with maxspan=5m` ile bölüm 3'teki zincirleri **doğrudan** ifade eder — recon zincirlerini yazmak için en zarif dil bu.

**Tuning gerçeği:** Recon kuralları "kur ve unut" değildir; sürekli allowlist bakımı ister. Pratik yol: kuralı önce **2-4 hafta gölge (alert-only, no-page) modda** çalıştır, kaynak host+hesap dağılımını çıkar, tepe FP üreticilerini (SCCM sunucuları, scanner hesapları, jump box'lar) kaynak+hesap+zaman kombinasyonuyla — sadece isimle değil — istisna listesine al. Ardından eşiği tek-komut yerine **kümelenme/sıralama** üzerine kaydır. Ölçmen gereken metrik alarm sayısı değil, **entity başına gerçek olay** oranıdır. İyi ayarlanmış bir recon tespiti günde 5-10 yüksek-bağlamlı olay üretir; kötü ayarlanmış olan 5000 satırlık bir gürültü akışıdır ve ikincisi hızla sessize alınıp ölür — ki bu, hiç kural olmamasından daha tehlikelidir, çünkü kağıt üstünde "kapsamımız var" der.

**Son yargı:** Domain recon tespitinde başarı, daha çok imzadan değil, **doğru katmanları loglamaktan** (command line + 4104 + LDAP/DFI + ağ) ve **entity-merkezli korelasyondan** gelir. Tek bir `net group` alarmına bakan analist yanılır; kaynağın son 20 dakikasına bakan analist ihlali görür.
