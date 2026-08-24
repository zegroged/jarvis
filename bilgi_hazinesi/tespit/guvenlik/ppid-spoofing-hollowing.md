# PPID Spoofing ve Process Hollowing — Tespiti

> Saha notu. Bu metin "event 4688 nedir" seviyesinde değil; iki tekniğin gerçek ortamda neden karıştığını, naif kuralın nerede çöktüğünü ve kıdemli bir analistin gürültüden ihlali nasıl ayırdığını anlatır.

---

## 1. Özet: saldırı + naif tespit

**PPID Spoofing (Parent Process ID Spoofing).** Windows'ta bir süreç `CreateProcess` çağrısıyla doğduğunda, çekirdek varsayılan olarak çağıran sürecin PID'ini "parent" olarak kaydeder. Fakat `CreateProcess`'in genişletilmiş biçimi `CreateProcessA/W` + `STARTUPINFOEX` + `UpdateProcThreadAttribute` ile `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS` özniteliği verilirse, saldırgan çocuğun parent'ını istediği süreç yapabilir. Klasik hamle: `explorer.exe` veya `svchost.exe`'yi sahte ebeveyn seçip, kötü niyetli çocuğun "masum bir şeyden doğmuş" gibi görünmesini sağlamak. MITRE karşılığı **T1134.004 (Access Token Manipulation: Parent PID Spoofing)**. Didier Stevens'ın **SelectMyParent** aracı bunun kanonik PoC'udur; Cobalt Strike'ın `ppid` komutu ve `spawnto` ayarı da aynı primitifi kullanır.

**Process Hollowing (Process Replacement).** Saldırgan meşru bir imzalı ikiliyi (ör. `svchost.exe`, `RegAsm.exe`, `BitLockerToGo.exe`) **suspended** durumda başlatır, `NtUnmapViewOfSection` / `ZwUnmapViewOfSection` ile disk imajının bellek kesitini boşaltır, `VirtualAllocEx` + `WriteProcessMemory` ile kendi PE'sini yazar, `SetThreadContext` ile entry point'i kaydırıp `ResumeThread` çeker. Sonuçta Görev Yöneticisi'nde masum bir isim, imzalı bir yol; ama bellekte çalışan tamamen başka bir kod. MITRE karşılığı **T1055.012 (Process Injection: Process Hollowing)**. Lumma stealer'ın `BitLockerToGo.exe`'yi, Pikabot'un `rundll32`'den doğan meşru ikilileri hedeflemesi bunun canlı örnekleridir.

**Naif tespit — herkesin bildiği kısım.** İki tarafta da "kolay" görünen kurallar var. PPID spoofing için: bilinen araç isimlerini yakala — `Image|endswith: '\SelectMyParent.exe'` veya komut satırında `ppid-spoof`, `spoof_ppid` gibi kalıplar (Sigma `52ff7941-...`). Hollowing için iki yaklaşım: (a) **Sysmon Event 25 / `process_tampering`** üzerinden "Image is replaced" tipini yakala (Sigma `c4b890e5-...`), (b) bilinen kötü ana-çocuk kombinasyonlarını yakala — `HollowReaper.exe` çalışması (`85d23b42-...`), ya da Pikabot gibi `ParentImage|endswith: '\rundll32.exe'` + belirli hedef ikili. `BitLockerToGo.exe`'nin **hiç çalışmaması** başlı başına IOC'dir (Sigma `7f2376f9-...`), çünkü kimse çıkarılabilir sürücü şifrelemeyi elle tetiklemez.

Buraya kadarı Google'da bir sayfada var. Asıl mesele bunların **gerçek bir SOC'ta çalışmadığı** yer.

---

## 2. Naif tespit neden yetmez

**Araç-ismi kuralları bir sonraki commit'te ölür.** `SelectMyParent.exe`'yi endswith ile yakalayan kural, saldırgan dosyayı `svc_host_helper.exe` diye rename ettiği an kördür. Bu teknik artık bir "araç" değil, birkaç satır C/C#/Nim primitifi; Cobalt Strike, Brute Ratel, Sliver ve her red team'in kendi loader'ı bunu **kendi süreç içinde** yapar — ayrı bir çalıştırılabilir yoktur. Yani `52ff7941` kuralının gerçek dünyadaki kapsamı: "aptal saldırganı ve kendi pentest ekibini yakalar". Komut satırı kalıpları (`ppid-spoof` vb.) daha da naif — spoofing bir API çağrısıdır, komut satırında iz bırakmaz. Bu string'ler sadece PoC araçlarının argümanlarıdır.

**PPID spoofing "process creation" logunda görünmez.** Kritik kör nokta: Standart Windows **Security 4688** ve hatta **Sysmon Event 1**, çocuğun bildirdiği parent alanını gösterir — ve bu alan **çekirdeğin gördüğü gerçek yaratıcı değil, sahte olandır**. Yani spoofing başarılıysa, log'unuzdaki `ParentImage`/`ParentProcessId` zaten saldırganın seçtiği yalandır. Kuralınız "explorer.exe → cmd.exe normaldir" mantığıyla çalışıyorsa, saldırgan tam olarak o normalliği taklit ediyor demektir. **Tek bir olay satırına bakarak spoofing tespit edilemez** — çünkü olayın kendisi yalan söylüyor. Bu, korelasyona neden mecbur olduğumuzun kökenidir (Bölüm 3).

**"Image is replaced" (Sysmon 25) sandığınızdan çok daha dar.** Sysmon'un process tampering tespiti (`c4b890e5` kuralının dayandığı) yalnızca belirli tampering desenlerini yakalar — klasik unmap+write hollowing'in bazı varyantlarını görür, ama **process doppelgänging**, **process ghosting**, **transacted hollowing**, **module stomping** ve **thread hijacking**'i çoğunlukla görmez. Dahası Event 25 **yüksek gürültülüdür**: kendini paketleyen/açan meşru yazılım (bazı korumalı ikililer, DRM'li oyunlar, .NET AOT, hatta Windows'un kendi `WMIADAP.exe`'si) "image replaced" üretir — kuralın koca bir `filter_main_generic` bloğunun `Program Files`, `System32\wbem` ve `WMIADAP` istisnalarıyla dolu olması tesadüf değil. Bu istisnalar tuning'in fosili: her biri birinin gecesini mahveden bir false positive'in mezar taşı.

**Bilinen-kötü kombinasyon kuralları ezberi yakalar, tekniği değil.** Pikabot kuralı (`d8937fe7`) `rundll32 → [belirli ikili]` der ve yorum satırı bile dürüsttür: *"Only add processes seen used by Pikabot to avoid collision"*. Yani bu bir davranış kuralı değil, bir imza; Pikabot yeni bir hedef ikili seçtiğinde kural sessizce boşa düşer. `BitLockerToGo.exe` kuralı (`7f2376f9`) bugün altın değerinde çünkü nadir; ama Lumma yarın `RegAsm.exe` veya `AddInProcess.exe`'ye geçtiğinde o özel kural işe yaramaz — ve bu ikililer BitLockerToGo kadar nadir değildir.

**False positive selleri.** Yukarıdakilerin toplamı: geniş bir "anormal parent" kuralı yazarsanız (ör. "System32 dışından başlayan svchost") SCCM, EDR ajanları, yedekleme yazılımı ve installer'lar sizi boğar. Dar yazarsanız her yeni malware varyantını kaçırırsınız. Naif tespitin gerçek maliyeti bu ikilemdir.

---

## 3. Korelasyon zinciri (asıl değer)

Tek başına ne "anormal parent" ne de "image replaced" olayı güvenilir bir alarmdır. Değer, bu **zayıf sinyalleri** bir zaman ve bağlam ekseninde birbirine dikmekte. İşte pratikte "yüksek güven"e çeviren desenler.

**Zincir A — Spoofing'i türev bir çelişkiden yakala (kernel truth vs. reported parent).**
PPID spoofing 4688/Sysmon-1'de doğrudan görünmez dedik; ama **iki farklı telemetri kaynağı** çeliştiğinde görünür hale gelir. Somut örnek:
1. **Sysmon Event 1**: `notepad.exe`, `ParentImage: C:\Windows\explorer.exe`, ParentProcessId: 5120.
2. Aynı anda **Sysmon Event 10 (ProcessAccess)** ya da **Event 8 (CreateRemoteThread)**: 5120 (explorer) değil, başka bir süreç (ör. bir Office child ya da bilinmeyen bir loader) `PROCESS_CREATE_PROCESS` / `PROCESS_DUP_HANDLE` erişimiyle explorer'a dokunuyor — spoofing için gereken handle açılışı.
3. Ya da daha basiti: bildirilen parent (explorer, PID 5120) **o çocuğu yaratmış olamaz**, çünkü explorer'ın CPU/handle aktivitesi o milisaniyede yok ve çocuk explorer'ın oturumundan farklı bir integrity/session'da.

Tek başına "notepad explorer'dan doğdu" tamamen normaldir. Ama **"explorer'dan doğduğu iddia edilen çocuk + explorer'a bu doğumdan hemen önce handle açan üçüncü bir süreç"** kombinasyonu spoofing'in imzasıdır. Buradaki yargı: reported parent ile gerçek yaratıcı arasındaki çelişkiyi başka bir telemetri türünden triangüle etmek.

**Zincir B — Hollowing'i yaşam döngüsü sırasıyla dik.**
Hollowing tek olay değil, bir **API dizisidir** ve her adımı ayrı telemetri üretir:
1. **Suspended başlatma**: meşru ikili (ör. `svchost.exe`) System32 dışından **veya** anormal bir parent'tan (ör. bir Office ürünü, `wscript.exe`, kullanıcı `AppData`'sından bir exe) doğar. Sysmon 1.
2. **Bellek manipülasyonu**: aynı hedefe `VirtualAllocEx` + `WriteProcessMemory` + `SetThreadContext`. EDR bunu görür; Sysmon çıplak halde göremez ama **Event 25 (tampering)** ya da **Event 10** ipuçları verir.
3. **Ağ**: hollow'lanan `svchost` beklenmedik bir C2'ye çıkar — `svchost.exe`'nin `443`'e ham bir IP'ye gitmesi, üstelik parent'ı `services.exe` **değilse**, çok güçlü bir sinyaldir. Sysmon 3.
4. **Kalıcılık/keşif**: aynı süreç kısa süre içinde `whoami`, `nltest`, ya da bir Run key yazımı yapar.

Tek satırda "svchost 443'e çıktı" gürültüdür; svchost sürekli çıkar. Ama **"anormal parent'lı svchost" + "aynı svchost'ta image tampering" + "aynı svchost'un bilinmeyen IP'ye TLS'i"** üç zayıf sinyali çarptığında yanlış-pozitif olasılığı çöker. Korelasyon motorunda bunu `process_guid` üzerinden bağlarsınız (Sysmon'un `ProcessGuid`'i altın anahtardır — PID yeniden kullanılır, GUID kullanılmaz).

**Zincir C — Çok-hostlu / yanal-hareket bağlamı.**
En yüksek güven, teknik başka sinyallerle **farklı hostlarda** buluştuğunda gelir. Örnek gerçek ihlal deseni:
- **Host A**: phishing → Office → `rundll32`/`regsvr32` → PPID-spoof'lu bir child (initial access).
- **~dakikalar sonra Host A**: hollow'lanan bir `svchost`'tan **LSASS'a `PROCESS_VM_READ|QUERY` erişimi** (Sysmon 10, credential access).
- **~sonra Host B**: Host A'nın IP'sinden gelen `4624 Type 3` (network logon) + `services.exe`'nin `PsExec`/WMI ile bir servis kurması → **Host B'de aynı hollowing deseni**.

Bu üçlü — initial access tekniği + credential access + lateral movement, **ortak bir aktör IP'si ve zaman penceresiyle** dikildiğinde — artık "belki FP" değil, gerçek kampanyadır. Detection engineering'in işi tek kuralı mükemmelleştirmek değil, bu zayıf düğümleri bir graf üzerinde birleştirecek korelasyon aramalarını (ya da risk-tabanlı alarmlamayı) yazmaktır.

**Neden korelasyon, tek sertleştirilmiş kural değil?** Şunu düşünün: "System32 dışından svchost" kuralını tek başına yüksek-güvene çekmek için o kadar çok istisna eklersiniz ki kural pratikte hiçbir şey yakalamaz hale gelir (over-tuning ölümü). Oysa aynı zayıf sinyali — düşük eşikte, alarm üretmeden — bir **risk skoru** olarak tutup, aynı `ProcessGuid`/host üzerinde ikinci ve üçüncü zayıf sinyal biriktiğinde eşiği aşırmak, hem FP'yi hem kaçırmayı (miss) aynı anda düşürür. Splunk RBA, Sentinel'de `Sentinel` analytics rules + entity behavior, Elastic'te building-block rules bu felsefeyi kodlar. Zayıf sinyaller **silinmez, biriktirilir**. Tespit mühendisinin zihinsel modeli "her kural bir alarm" değil, "her sinyal bir oy" olmalıdır — ve ihlal, oyların bir varlık (entity) etrafında yığıldığı yerdir.

---

## 4. False positive gerçeği ve triage yargısı

Bu alarmları **meşru** olarak üreten gerçek dünya aktörleri:

- **SCCM / ConfigMgr**: `ccmexec.exe` altında garip parent zincirleri, System32 dışından süreç başlatma, `WmiPrvSE`'den doğan child'lar. Kurumsal ortamda "anormal parent" alarmlarının bel kemiği budur.
- **Yedekleme yazılımı** (Veeam, Commvault, Acronis): VSS ile oynar, süreçleri suspended başlatır, bellek snapshot'ı alır — bazı hollowing-benzeri tampering sinyalleri üretebilir.
- **Vulnerability scanner'lar** (Nessus, Qualys agent, Rapid7): uzaktan süreç doğurma, garip parent, ani credential-access-benzeri LSASS okumaları (bazı kimlik denetimleri için).
- **EDR/AV'nin kendisi**: birçok EDR meşru olarak process injection ve memory scanning yapar; kendi ürününüz Sysmon 25/10'da gürültü kaynağıdır.
- **Installer / güncelleyiciler**: `msiexec` altında imzalı ama beklenmedik yollardan başlatma; Chrome/Opera/Teams gibi kendi kendini güncelleyen uygulamalar (`c4b890e5` kuralının `filter_optional_opera` istisnası tam olarak bunun içindir).
- **.NET / packer'lı meşru yazılım**: kendini bellekte açan legit ürünler "image replaced" üretir.

**Kıdemli analist gerçek/gürültü ayrımını nasıl yapar — triage sırası:**

1. **Önce parent değil, çocuğun ne yaptığına bak.** "Anormal parent'lı svchost" tek başına hiçbir şeydir. Soru: bu süreç **sonra ne yaptı?** Ağa çıktı mı? LSASS'a dokundu mu? Disk'e bir şey yazdı mı? Sonuç yoksa, muhtemelen gürültü. Davranışsal sonuç varsa yükselt.
2. **İmza ve yol tutarlılığı.** İkili imzalı mı? Yolu beklenen yerde mi (`svchost` gerçekten `System32`'de mi)? İmzalı + doğru yol + davranışsal sonuç yok = neredeyse kesin FP. İmzalı ama yanlış yol (`svchost` `AppData`'da) = kırmızı bayrak, hollowing/masquerading.
3. **Zamanlama ve önceki halka.** Alarmın parent'ının parent'ı ne? Zincir `explorer → office → macro → this` gibi phishing kokuyorsa yükselt; `services.exe → ccmexec → this` ise SCCM'dir.
4. **Yaygınlık (prevalence).** Bu (hash, yol, parent-child çifti) filoda kaç hostta var? 4000 hostta varsa yönetim yazılımıdır; **1 hostta ve ilk kez** görülüyorsa incele. Prevalence, tek başına en güçlü triage sinyalidir.
5. **Coklu alarmda önce credential-access ve C2'ye bak.** Aynı host/aktörde birden çok alarm varsa, öncelik sırası: LSASS erişimi > bilinmeyen C2 > hollowing/tampering > anormal parent. Sonuç odaklı sinyaller (çalınan kimlik, dışarı giden trafik) her zaman yapı odaklı sinyallerden (parent anomalisi) önce gelir, çünkü ihlalin **etkisini** gösterirler.

Kısaca yargı: **yapısal anomali alarmı tetikler, ama triage'ı davranışsal sonuç yönetir.** Tek satır asla karar verdirmez.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırganın bu tespitleri atlatmak için yaptıkları — kural dokümanında **yazmayan** yollar — ve her birine ikinci-derece cevap:

**Kaçınma 1: Araç ismini rename et / dosyasız yap.** `SelectMyParent.exe`'yi yeniden adlandır ya da primitifi loader'ın içine göm.
→ **Karşı-tespit**: İsimden vazgeç, **davranışa** geç. Sysmon Event 10'da `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS` için gereken handle açılışını ara: bir sürecin `explorer.exe`/`svchost.exe`'ye `PROCESS_CREATE_PROCESS` (0x0080) erişim maskesiyle handle açması, hemen ardından o "parent"tan bir child doğması. GrantedAccess maskesi imzadır, isim değil.

**Kaçınma 2: Sahte parent'ı gerçekten mantıklı seç.** `explorer.exe` yerine, hedef makinede gerçekten o çocuğu doğurabilecek bir parent seç (ör. bir tarayıcı, Teams). Böylece parent-child anomali kuralları susar.
→ **Karşı-tespit**: **Session ve integrity tutarlılığı.** Spoof'lanan child çoğu zaman parent'tan farklı bir `LogonId`/session'da ya da farklı integrity seviyesinde doğar. "explorer'dan doğduğu iddia edilen child ama farklı SessionId" güçlü bir çelişkidir. Ayrıca gerçek yaratıcı hâlâ Event 10/8 izinde bir yerde vardır.

**Kaçınma 3: Klasik unmap+write yerine modern varyant.** `NtUnmapViewOfSection` çağrısı Sysmon 25'i tetikliyorsa, **module stomping** (mevcut bir DLL'in .text'ini ez), **transacted hollowing** ya da **process ghosting** (silinmiş/delete-pending dosyadan image oluştur) kullan — bunlar "image replaced" üretmeyebilir.
→ **Karşı-tespit**: **Bellek anomali telemetrisi.** EDR tarafında RWX ya da private-executable bölgeler, image olmayan bellekten çalışan thread (`MEM_PRIVATE` başlangıç adresinden başlayan thread — Sysmon 8'de `StartAddress` image'a denk gelmez), ve unbacked memory'den yapılan syscall'lar. Ghosting özelinde: kısa ömürlü `DELETE`/`FILE_DELETE_ON_CLOSE` handle'ı + hemen ardından o dosyadan section oluşturma.

**Kaçınma 4: Hedef olarak nadir değil, sıradan bir ikili seç.** `BitLockerToGo.exe` nadir olduğu için yakalanıyorsa, `RegAsm.exe`, `AddInProcess.exe`, `MSBuild.exe`, `InstallUtil.exe` gibi hem imzalı hem gürültü içinde kaybolan LOLBIN'lere geç.
→ **Karşı-tespit**: Nadirlik kuralından **bağlam kuralına** geç. `RegAsm.exe` çalışması normaldir; ama `RegAsm.exe`'nin **komut satırı argümanı olmadan**, **anormal parent'tan** (Office, wscript, AppData) doğması ve ardından **ağa çıkması** anormaldir. Yani ikilinin varlığını değil, o ikilinin **beklenmedik yaşam bağlamını** yakala.

**Kaçınma 5: Sysmon'u kör et.** Config'i manipüle et, servisi durdur, ya da Sysmon'un görmediği bir teknikle çalış.
→ **Karşı-tespit**: **Telemetri sağlık izleme.** Bir hostun Sysmon Event 1 hacminde ani düşüş, `Sysmon` servisinin durması/config değişikliği (Event 4/16), ya da bir hostun aniden "sessizleşmesi" başlı başına alarmdır. "Loglama neden kesildi" sorusu, log'un içeriği kadar önemlidir.

**Kaçınma 6: Suspended başlatma sinyalini gizle.** Hollowing'in en yakalanabilir adımı, meşru ikilinin `CREATE_SUSPENDED` bayrağıyla doğup çalışmadan önce belleğinin oyulmasıdır. Olgun saldırgan bunun yerine **early bird APC injection** ya da thread'i doğal başlangıcından önce hijack ederek pencereyi milisaniyeye indirir, ya da hedefi hiç suspended başlatmadan zaten çalışan bir sürece module stomping uygular.
→ **Karşı-tespit**: Zamanlama korelasyonu. Bir sürecin doğumu (Event 1) ile ilk **anlamlı** aktivitesi (ilk ağ bağlantısı, ilk dosya yazımı, ilk child) arasındaki gecikme patolojik derecede kısa/uzunsa ya da entry point'i image'ın beklenen giriş noktasına denk gelmiyorsa şüphelidir. EDR'de `SetThreadContext` ardından `ResumeThread` API çifti, farklı bir sürecin uzak thread'i üzerinde çağrıldığında hollowing'in en spesifik davranışsal imzasıdır — isim ya da yol hiç gerekmez.

Buradaki genel prensip: her kaçınma, saldırganın **başka bir yerde** iz bırakmasına yol açar. Saldırgan bir telemetri kaynağını körleştirdiğinde, körleştirme eyleminin kendisi (Sysmon durdurma, config değişimi, ETW patch'leme — `EtwEventWrite` yamalamak da bir davranıştır) yeni bir sinyal doğurur. İş, tek bir tespiti derinleştirmek değil, kaçış yollarını ikinci-derece telemetriyle kuşatmaktır; saldırgana "her yol bir iz bırakır" durumunu dayatmaktır.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** Sigma kuralları `Image`, `ParentImage`, `CommandLine` gibi soyut alanlar kullanır; gerçek SIEM'de bunlar farklı isimlerdedir ve **eşleme sessizce yanlış olabilir**:
- **Splunk (Sysmon TA)**: `Image`, `ParentImage`, `ParentProcessGuid`, `OriginalFileName` genelde düz gelir; ama `process_tampering` (Event 25) TA sürümüne göre `Type` alanını farklı parse eder. `OriginalFileName` masquerading tespiti için `Image`'dan daha güvenilirdir (PE header'dan gelir, rename edilse de değişmez) — ama birçok kural bunu kullanmayı unutur.
- **Microsoft Sentinel / Defender**: `DeviceProcessEvents` tablosunda `FileName`, `InitiatingProcessFileName`, `InitiatingProcessParentFileName` kullanılır. Kritik: Defender'ın **kendi PPID'i zaten "gerçek yaratıcı"ya daha yakındır** (kernel callback'lerinden), yani spoofing'e ham Sysmon'dan daha dirençli olabilir — ama `ProcessCommandLine`'ın **truncate** edildiği (uzun komut satırları kesilir) bilinen bir gerçektir. Uzun spoofing PoC argümanları kaybolabilir.
- **Elastic**: ECS'ye map edilir — `process.name`, `process.parent.name`, `process.pe.original_file_name`, `process.entity_id` (ProcessGuid karşılığı). ECS mapping'de en yaygın hata: bazı beat/agent sürümlerinde `process.parent` alanının kısmen boş gelmesi ya da hollowing için kritik olan `process.Ext.token`/memory alanlarının yalnızca Elastic Defend (endpoint) ile gelmesi, Winlogbeat ile gelmemesi.

**Varsayılan loglanmayan şeyler — bunlar olmadan kurallar boştur:**
- **Security 4688 tek başına yetmez.** `ParentProcessName` 4688'e ancak Windows'ta *"Include command line in process creation events"* GPO'su + *Audit Process Creation* açıksa gelir. Komut satırı varsayılan **kapalıdır**. Bu olmadan `CommandLine` bazlı kuralların hepsi ölü.
- **Sysmon Event 10 (ProcessAccess) çok pahalıdır ve varsayılan config'lerde LSASS dışında dar tutulur.** PPID spoofing'i handle açılışından yakalamak için `explorer.exe`/`svchost.exe`'yi hedefleyen ProcessAccess loglaması gerekir — bu, iyi ayarlanmamışsa ya devasa gürültü ya da tamamen kör demektir. SwiftOnSecurity/Olaf config'leri bile Event 10'u agresif filtreler.
- **Sysmon Event 25 (process tampering)** yalnızca **Sysmon 13+** ile gelir. Eski ajanlarda `c4b890e5` kuralının dayandığı `process_tampering` logsource **hiç yoktur** — kural sessizce hiç tetiklenmez. Bu, "kural deployed ama telemetri yok" sınıfı sessiz başarısızlığın klasik örneğidir.
- **Sysmon Event 8 (CreateRemoteThread)** ve **thread StartAddress** memory-based tespit için şart, ama gürültülü olduğu için sık devre dışı bırakılır.

**Tuning gerçeği.** `c4b890e5` kuralının uzun istisna bloğu (Program Files, WMIADAP, Opera) size şunu söyler: bu kural **out-of-the-box deploy edilemez**; her ortam kendi meşru "image replaced" üreticilerini (EDR'i, backup'ı, packer'lı LOB uygulaması) baseline'layıp istisna eklemek zorundadır. Doğru sıra: (1) kuralı **alarm değil, sadece toplama** modunda 2-4 hafta çalıştır, (2) yaygınlık ve parent-child baseline'ı çıkar, (3) yüksek-hacimli meşru üreticileri `process.pe.original_file_name` + imzalayan + yol üçlüsüyle (isim değil!) istisnala, (4) sonra alarma al. İsimle istisnalamak yeni bir zafiyet açar — saldırgan tam o istisnalanmış ismi kullanır.

**Platform farkı özeti.** Splunk'ta güç `tstats` + risk-based alerting ile zayıf sinyalleri `process_guid` üzerinden dikmekte; Sentinel'de KQL `join`/`bin()` ile çok-tablo korelasyonda (ama komut satırı truncation'ına dikkat); Elastic'te EQL **sequence** sorguları hollowing yaşam döngüsünü (`sequence by process.entity_id [process where ...] [network where ...]`) doğal olarak ifade eder ve bu üç teknik için en zarif korelasyon dilidir. Hangi platform olursa olsun değişmeyen ilke: **tek olaya güvenme, ProcessGuid/entity_id üzerinden yaşam döngüsünü dik, ve yapısal anomaliyi davranışsal sonuçla doğrula.**

---

### Kapanış yargısı
Bu iki teknik, "log'un sana yalan söyleyebildiği" nadir alanlardan biridir — PPID alanı spoof'lanabilir, süreç ismi ve imza hollowing'de yalandır. Bu yüzden burada tek-kural düşüncesi ölümcüldür. Kıdemli işi: sinyalin **kendisine değil, çevresine** bakmak — yaratıcının gerçek kimliği (Event 10/8), sürecin sonraki davranışı (ağ, LSASS, disk), yaygınlık ve zaman penceresi. Kuralı yazmak on dakika; onu bir ortamda gürültüden ayırıp gerçekten güvenilir kılmak, sahanın asıl işidir.
