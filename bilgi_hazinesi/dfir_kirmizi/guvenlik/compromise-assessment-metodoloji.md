# Compromise Assessment Metodolojisi

> Pratisyen notu: Bu metin, bir ortamda "sessiz bir düşman var mı?" sorusuna disiplinli bir cevap üretmek için yazıldı. Teoriden çok karar mantığına odaklanır: hangi artefaktı gördüğümde hangi sonuca giderim, neyi önce toplarım, neye güvenmem. 15 yıllık saha deneyiminin damıtılmış hâli olarak okuyun; kitaptan öğrenilen değil, gece 3'te olay masasında öğrenilen şeyler.

---

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Compromise Assessment (CA), Türkçesiyle "ele geçirilme değerlendirmesi", bir sorunun cevabını arar: **"Bu ortamda şu anda ya da yakın geçmişte tespit edilmemiş bir ihlal var mı?"** Dikkat: bu soru, klasik olay müdahalesinden (IR) farklıdır. IR'de zaten bir alarm, bir şikayet, bir fidye notu vardır; yangını bilirsin, söndürürsün. CA'da ise ortada tetikleyici bir olay **yoktur**. Bir yönetici "son 6 aydır kimse bir şey demedi ama içim rahat değil, temiz miyiz?" der ve sen boş bir sayfayla başlarsın.

Bu ayrımı içselleştirmek kritik, çünkü metodolojiyi belirler:

- **Threat Hunting** hipotez odaklıdır ve süreklidir: "Kerberoasting olsaydı nasıl görünürdü?" diye sorup o izi ararsın. CA daha geniştir, hipotez değil kapsama (coverage) odaklıdır.
- **IR** reaktiftir, bir olayın etrafında döner. CA proaktiftir, olay yokken çalışır.
- **Penetrasyon testi / Red Team** "girilebilir mi?" sorusunu sorar. CA "girilmiş mi?" sorusunu sorar. Tamamen farklı zihniyetler.

CA'nın IR sürecindeki yeri iki yerdedir. Birincisi **kapıda**: bir M&A (şirket satın alma) öncesi, yeni bir MSSP anlaşmasında ya da düzenleyici bir denetim öncesi ortamın temiz olup olmadığını doğrularsın. İkincisi **kuyrukta**: büyük bir IR'ın kapanışında "kök nedeni temizledik ama düşman başka nerede tutunmuş olabilir?" sorusuna cevap üretir. Yani hem baseline (temel çizgi) kurar, hem de eradikasyonun tamlığını doğrular.

CA'nın altın kuralı: **"Kanıt yokluğu, yokluğun kanıtı değildir."** Bir CA'nın çıktısı asla "ortam temiz" değildir. Çıktı şudur: "Uyguladığımız metodoloji ve görünürlük seviyesiyle, tanımlanan zaman aralığında ihlal göstergesi bulunamadı; şu kör noktalar mevcuttur." Bu cümleyi kuramayan analist, müşteriye yalan söylüyordur.

---

## 2. Adım-adım İŞ AKIŞI ve KARAR (asıl değer)

Gerçek bir pro DFIR analistinin CA'da izlediği sıra, "araç aç, tara" değildir. Sıra, **kapsam → görünürlük → toplama → hipotez → analiz → doğrulama** şeklinde ilerler. Şimdi her adımı, karar mantığıyla açıyorum.

### 2.0 Scoping: neyi, ne kadar geriye bakacağız

İlk karar teknik değil, kapsamsaldır. Üç soruyu netleştirmeden tek bir komut çalıştırmam:

1. **Zaman penceresi ne?** Müşteri "6 ay" diyorsa, ama Windows Security log'u 7 günde dönüyorsa (rollover), o 6 ayın çoğu kör. Bunu baştan söylerim.
2. **Kron mücevherler (crown jewels) nerede?** DC'ler (Domain Controller), sertifika otoritesi (AD CS), finans veritabanı, kaynak kod deposu, e-posta. Bir saldırgan sonunda buralara gider; CA'yı buradan geriye doğru kurgularım.
3. **Görünürlük envanteri var mı?** EDR hangi endpoint'lerde kurulu? Sysmon var mı? Log'lar SIEM'e akıyor mu, ne kadar tutuluyor? Bu envanter, raporun "kör noktalar" bölümünün ta kendisidir.

### 2.1 Order of Volatility'e göre toplama

Klasik ama hâlâ geçerli. En uçucudan en kalıcıya doğru toplarım. Bir makinede canlı şüphe varsa sırayı bozmam:

1. RAM (bellek) — çalışan process'ler, network bağlantıları, injecte edilmiş kod, şifresiz kalmış credential'lar
2. Ağ durumu — netstat, ARP, DNS önbelleği, aktif oturumlar
3. Çalışan process'ler ve handle'lar
4. Disk üzerindeki uçucu artefaktlar — geçici dosyalar, prefetch
5. Kalıcı artefaktlar — registry, event log, MFT, dosya sistemi
6. Uzak log'lar ve yedekler

**Karar:** Eğer bir endpoint aktif olarak "sıcaksa" (canlı C2 trafiği görüyorsam), önce **bellek imajını** alırım — çünkü makineyi izole ettiğim an ya da kapattığım an, en değerli delil buharlaşır. Ama makine soğuksa (haftalardır kapalı, sadece adli inceleme için geldi), belleğe uğraşmam, doğrudan diske giderim.

### 2.2 Endpoint tarafı: triage toplama

Yüzlerce makineyi tek tek imajlamak imkânsız ve gereksiz. Modern CA, **hedefli triage** ile çalışır.

- **KAPE (Kroll Artifact Parser and Extractor)** — endpoint'ten adli olarak anlamlı artefakt setini dakikalar içinde çeker. `!SANS_Triage` hedef setini kullanırım: MFT, USN Journal, event log'lar, registry hive'ları, Prefetch, Amcache, SRUM, tarayıcı geçmişi, Scheduled Tasks. Sonra KAPE'nin modülleriyle (EZ Tools sarmalayıcıları) parse ederim.
- **Velociraptor** — bir CA'nın belkemiği. Filo genelinde (fleet-wide) VQL sorguları çalıştırıp binlerce makinede aynı anda "şu autorun anahtarında şu değer olan var mı?", "şu hash'e sahip process çalışan var mı?" diye sorarım. Hunt özelliği CA için biçilmiş kaftandır. Ajan bazlı, düşük ayak izi.

**Karar mantığı — "şu artefaktı görünce şuraya giderim":**

- **Prefetch'te** bir ikili (executable) `\Temp\`, `\Users\Public\`, `\ProgramData\` gibi olağandışı bir yoldan çalışmışsa → o ikilinin hash'ini alırım, imzasına bakarım, sonra Amcache/ShimCache ile ilk görülme zamanını çıkarırım. Yeni ve imzasız + tuhaf yol = yüksek öncelik.
- **Amcache.hve** bana bir ikilinin ortamda **ilk ne zaman göründüğünü** verir. Bu, "initial access ne zaman oldu?" sorusunun altın kaynağıdır. ShimCache (AppCompatCache) ile çapraz doğrularım.
- **SRUM (System Resource Usage Monitor)** bana process bazında ne kadar **ağ verisi** gittiğini verir. Gecelik gigabaytlarca giden veri = exfiltrasyon (veri sızdırma) sinyali. Bu artefaktı acemiler kaçırır.
- **ShellBags / RecentDocs / LNK dosyaları** → saldırganın hangi klasörleri gezdiğini, hangi dosyaları açtığını gösterir. Lateral movement'ın el izidir.

### 2.3 Bellek analizi: Volatility

Bellek imajı aldıysam, **Volatility 3** ile çalışırım. Karar akışım:

- `windows.pslist` + `windows.psscan` → gizlenmiş (unlinked) process'leri yakalamak için ikisini karşılaştırırım. psscan'de görünüp pslist'te olmayan = klasik rootkit/gizlenme sinyali.
- `windows.pstree` → ebeveyn-çocuk ilişkisi. **`winword.exe`'nin çocuğu `powershell.exe`** ise, ya da `services.exe`'nin altında olmaması gereken bir process varsa alarm çalar. `lsass.exe`'nin ebeveyni `wininit.exe` değilse → sahte lsass, credential çalma girişimi.
- `windows.malfind` → process bellek alanında `RWX` izinli, PE header'lı ama diskte karşılığı olmayan bölgeler → kod enjeksiyonu.
- `windows.cmdline` ve `windows.netscan` → hangi process hangi argümanla başlamış, hangi IP'lere bağlanıyor.
- `windows.dlllist` / `ldrmodules` → DLL sideloading ve unlinked DLL tespiti.

**Karar:** malfind bir process'te enjeksiyon gösterdiğinde, o bölgeyi dump edip **YARA** kurallarıyla tararım (Cobalt Strike beacon, Meterpreter stager imzaları için). YARA burada iki yönlü çalışır: bellekte ve diskte.

### 2.4 Log ve zaman çizelgesi analizi

CA'nın kalbi burasıdır. Tek tek artefakt bakmak değil, **süper zaman çizelgesi (super timeline)** kurmaktır.

- **Plaso / log2timeline** ile MFT, event log, registry, tarayıcı, prefetch — hepsini tek bir zaman ekseninde birleştiririm.
- **Timesketch**'e yüklerim. Neden? Çünkü 20 milyon satırlık bir timeline'ı grep ile okuyamazsın. Timesketch'te "initial access şüphesi anını" işaretler, o pencerede yoğunlaşırım.

**Windows Event Log karar noktaları — pratikte baktığım şeyler:**

- **4624 (logon)** özellikle **Type 3 (network)** ve **Type 10 (RDP)** → anormal saatlerde, servis hesaplarıyla, olağandışı kaynak makinelerden gelen oturumlar. Bir servis hesabı interaktif logon (Type 2) yapıyorsa → çalınmış credential.
- **4625** yığını (failed logon) tek kaynaktan → password spraying / brute force.
- **4672 (special privileges)** → her yeni admin oturumunda düşer; kimin ne zaman yükseltilmiş yetki aldığını izlerim.
- **4688 (process creation)** — komut satırı loglama açıksa altın madeni. `encodedcommand`, `-nop -w hidden`, `IEX (New-Object Net.WebClient)` kalıpları → fileless PowerShell saldırısı.
- **7045 (yeni servis kurulumu)** → PsExec, Cobalt Strike'ın lateral movement'ı buradan geçer. Rastgele isimli, `\Temp\`'ten çalışan servis = çok yüksek öncelik.
- **4698 (scheduled task oluşturma)** → en yaygın persistence (kalıcılık) yöntemi.
- **4720 / 4728 / 4732** → yeni kullanıcı oluşturma, Domain Admins / yerel admin gruplarına ekleme. Saldırganın kendi arka kapı hesabını açması.
- **1102 (audit log temizlenmesi)** → tek başına neredeyse suçüstü. Meşru sebep nadirdir.

**Sysmon varsa** işim çok kolaylaşır: Event ID 1 (process), 3 (network), 7 (image load — DLL sideloading), 8 (CreateRemoteThread — injection), 11 (file create), 22 (DNS query). Sysmon 22 ile DGA (algoritmayla üretilmiş) domain'lere ya da bilinen C2'lere DNS sorgusu yapan process'i doğrudan yakalarım.

### 2.5 Persistence avı

Bir saldırgan mutlaka kalıcılık kurar. Sistematik olarak şu köşelere bakarım:

- **Autoruns (Sysinternals)** — Run/RunOnce anahtarları, servisler, scheduled task'lar, WMI event subscription'ları, startup klasörleri. "Verify signatures" ve "Hide Microsoft entries" açık; geriye kalan imzasız girdiler şüpheli havuzumdur.
- **WMI kalıcılığı** — `__EventFilter`, `__EventConsumer`, `__FilterToConsumerBinding`. Bu, disksiz ve loglanmayan bir persistence olduğu için acemilerin gözden kaçırdığı, ustaların ilk baktığı yerdir. Velociraptor'la filo genelinde tararım.
- **AD tarafı** — Golden/Silver Ticket izleri, DCSync hakları (anormal `Replicating Directory Changes` izni), AdminSDHolder değişiklikleri, GPO'lara enjekte edilmiş scriptler, `krbtgt` parola yaşı (2'den fazla resetlenmemişse Golden Ticket riski).

### 2.6 IOC ve YARA taraması, tehdit istihbaratı zenginleştirme

Topladığım şüpheli hash'leri, IP'leri, domain'leri tehdit istihbaratıyla zenginleştiririm (VirusTotal, internal TI). **YARA** kurallarımı hem retro (topladığım imajlar üzerinde) hem canlı (Velociraptor ile filoda) çalıştırırım. Ama tek başına IOC eşleşmesine güvenmem — modern saldırgan her ortamda hash'ini değiştirir. Bu yüzden **davranışsal** (TTP) analiz, IOC'den önce gelir. IOC "bilineni" bulur; CA'nın asıl işi "bilinmeyeni" bulmaktır.

### 2.7 Sonuçlandırma

Bulguları **MITRE ATT&CK** çatısına oturturum. Neden? Çünkü "şu 3 tuhaf şey" demek yerine, "Initial Access (T1566 phishing) → Execution (T1059 PowerShell) → Persistence (T1053 scheduled task) → Credential Access (T1003 LSASS dump) → Lateral Movement (T1021 RDP)" diye bir zincir kurarsam, hem hikâye tamamlanır hem de eksik halkayı fark ederim. Zincirde boşluk varsa, "demek ki henüz bulamadığım bir adım var" derim ve geri dönerim.

---

## 3. Kritik dikkat noktaları

### Delil bütünlüğü ve order of volatility

Delili topladığın **an**, o delili değiştirebilir. Canlı bir sistemde `dir` komutu bile son erişim zamanını (access time) günceller. Bu yüzden:

- Toplama araçlarını mümkünse **harici, salt-okunur** bir ortamdan çalıştırırım.
- Disk imajı alırken **write blocker** (yazma engelleyici) kullanırım — fiziksel disk sökülüp incelenecekse şart.
- Her imajın **hash'ini** (SHA-256) toplama anında alır, kayıt altına alırım. İnceleme kopyası üzerinde çalışır, orijinale asla dokunmam. İnceleme sonunda hash'i tekrar doğrularım — eşleşiyorsa delil bütünlüğü ispatlanmıştır.

### Order of volatility'yi ihlal etmenin bedeli

Makineyi "acaba temiz mi?" diye kapatıp açan bir sistem yöneticisi, RAM'deki tüm delili ve çoğu geçici artefaktı yok eder. CA öncesi müşteriye net talimat veririm: **"Şüpheli makineleri kapatmayın, reboot etmeyin, üzerinde 'antivirüs taraması' başlatmayın."** AV taraması dosya erişim zamanlarını topluca bozar ve timeline'ı mahveder.

### Chain of custody (delil zinciri)

Özellikle bulgu adli/hukuki sürece gidecekse, her delilin **kim tarafından, ne zaman, nasıl** toplandığı, kimden kime devredildiği belgelenmelidir. Boşluk olan bir zincir, mahkemede delili çürütür. Ben CA'da bile — hukuki olmayacağını düşünsem de — chain of custody tutarım, çünkü CA sıklıkla "aslında bir olaymış" diye tam IR'a döner ve o an geriye dönüp zinciri kuramazsın.

### Anti-forensics'e karşı

Yetkin bir saldırgan izini siler. Sen de buna göre düşünmelisin:

- **Timestomping** (zaman damgası manipülasyonu): Saldırgan bir dosyanın `$STANDARD_INFORMATION` zaman damgalarını geçmişe çeker. Ama **MFT'deki `$FILE_NAME`** damgalarını değiştirmek çok daha zordur. İkisini karşılaştırırım (`$SI` vs `$FN`); tutarsızlık → timestomping suçüstü. Ayrıca `$SI` damgasının saniye altı hassasiyeti sıfırsa (`.0000000`), bu genelde manipülasyon işaretidir.
- **Log temizleme**: 1102 event'i, ama daha önemlisi **log'daki boşluklar**. Bir makinede 3 gün boyunca hiç event yoksa ama makine açıksa → loglar silinmiş ya da durdurulmuş.
- **USN Journal ve $LogFile**: Saldırgan bir dosyayı silse bile, USN Journal'da o dosyanın **var olduğu ve silindiği** kaydı kalabilir. Silinmiş kötücül aracın adını buradan yakalarım.
- **Volume Shadow Copy (VSS)**: Geçmiş sistem durumlarının fotoğrafı. Saldırgan ana dosya sistemini temizlese de, bir hafta önceki shadow copy'de kötücül dosya hâlâ durabilir. VSS'i mount edip ayrı bir timeline çıkarırım.

Genel ilke: **Her artefakti tek başına değil, en az bir başka bağımsız kaynakla çapraz doğrularım.** Bir tanesi manipüle edilmiş olabilir; ikisinin aynı yalanı söylemesi zordur.

---

## 4. Gerçek dünya senaryosu

**Bağlam:** Orta ölçekli bir üretim firması. Alarm yok, fidye yok. CFO, bir M&A süreci öncesi "6 aydır her şey sessiz, ama emin olmak istiyorum" diyor. EDR sadece sunucuların %60'ında kurulu; Sysmon yok; Security log 14 günde dönüyor. Kör nokta baştan belli: 6 aylık pencerede canlı log'un çoğu yok, disk artefaktlarına dayanacağız.

**Adım 1 — Kapsam ve toplama.** Kron mücevherlerden başlıyorum: 2 DC, dosya sunucusu, finans uygulama sunucusu. Velociraptor ajanını filoya dağıtıyorum, KAPE ile bu dört sunucudan triage seti çekiyorum.

**Adım 2 — İlk sinyal.** Dosya sunucusunun **Amcache**'inde, `C:\ProgramData\Adobe\ARM\svchost.exe` yolundan çalışmış imzasız bir ikili görüyorum. İki şey tuhaf: (1) `svchost.exe` asla o yoldan çalışmaz, gerçek olan `System32`'dedir. (2) Amcache ilk görülme zamanı ~4 ay önce. Bu, **masquerading (T1036)** — meşru bir isimle gizlenme.

**Adım 3 — Doğrulama.** Prefetch'te aynı ikilinin defalarca çalıştığını görüyorum. Hash'ini alıp TI'da sorguluyorum: doğrudan eşleşme yok (saldırgan özelleştirmiş), ama YARA'daki genel Cobalt Strike beacon kuralım **bellekte** o process'in alanında eşleşiyor. Volatility `malfind` çıktısı: aynı PID'de RWX, PE header'lı, diskte karşılıksız bölge → enjekte edilmiş beacon. Artık şüphe değil, **teyit** var.

**Adım 4 — Zaman çizelgesi ile geriye sarma.** Plaso ile süper timeline kurup Timesketch'e yüklüyorum. Sahte `svchost.exe`'nin ilk yazıldığı ana odaklanıyorum. O andan ~10 dakika önce: bir kullanıcının Outlook geçici klasöründe bir `.iso` eki açılmış, içinden bir `.lnk` çalışmış, o da `mshta` tetiklemiş. **Initial access buldum: phishing (T1566) → mshta ile execution (T1218).**

**Adım 5 — Yayılmayı izleme.** Dosya sunucusundaki 4672/4624 kayıtlarında (14 günlük pencerede kalan kısım) bir servis hesabının — normalde sadece uygulama çalıştıran hesabın — **DC'ye Type 3 network logon** yaptığını görüyorum. DC'de karşılık: 7045, rastgele isimli servis, `\Temp\`'ten. **Lateral movement (T1021) + PsExec tarzı execution.** DC'de ayrıca 4720 — 4 ay önce oluşturulmuş `svc_backup01` adında, kimsenin oluşturduğunu hatırlamadığı bir hesap ve o hesap **Domain Admins**'te (4732). Arka kapı hesabı.

**Adım 6 — Exfiltrasyon kontrolü.** Dosya sunucusunun **SRUM** verisinde, sahte svchost process'inin gece saatlerinde onlarca GB giden trafik ürettiğini görüyorum. Firewall log'larıyla çapraz kontrol: bilinmeyen bir bulut depolama IP'sine gidiş. **Exfiltration (T1567) teyit.**

**Varılan sonuç:** Ortam **temiz değil**. Yaklaşık 4 ay önce phishing ile başlayan, DC'ye kadar ilerlemiş, Domain Admin arka kapı hesabı bırakmış ve aktif veri sızdıran bir ihlal mevcut. CA burada durur ve **tam IR'a dönüşür**: kapsama (containment), krbtgt iki kez resetleme, tüm credential rotasyonu, eradikasyon ve izlemeli kurtarma. Rapor MITRE ATT&CK zinciriyle sunulur; boşluk kalmayan bir hikâye: Initial Access → Execution → Persistence → Priv Esc → Lateral Movement → Exfiltration.

Not: Eğer sadece EDR alarmına ya da IOC taramasına güvenseydik, bunu **kaçırırdık** — çünkü ikili özelleştirilmişti, hash eşleşmiyordu ve dosya sunucusunda EDR vardı ama saldırgan enjeksiyonla gizlenmişti. Bulguyu getiren şey davranışsal artefakt analizi ve timeline oldu.

---

## 5. Yaygın tuzaklar ve pro yargısı

**1. "Tarama yaptım, temiz çıktı" demek.** Acemi bir AV/EDR taraması çalıştırır, alarm görmez, "temiz" der. Pro bilir ki modern saldırgan imzasızdır, dosyasızdır, meşru araçları (LOLBins — living off the land) kullanır. Taramanın bulmadığı = yok, değil; taramanın **göremediği** demektir.

**2. Görünürlük envanterini atlamak.** Acemi, log'un ne kadar geriye gittiğini kontrol etmeden 6 aylık analiz vaat eder. Pro, ilk iş olarak "elimizde ne var, ne kadar geriye görüyoruz?" diye sorar ve kör noktaları **raporun birinci sınıf çıktısı** yapar. Bulamadığın şeyi değil, bakamadığın yeri dürüstçe yazmak profesyonelliktir.

**3. Tek artefakta güvenmek.** Acemi, `$STANDARD_INFORMATION` zaman damgasına bakıp "bu dosya 2 yıl önce yazılmış, temiz" der — timestomping'e yem olur. Pro her zaman çapraz doğrular: `$SI` vs `$FN`, Amcache vs ShimCache vs Prefetch, event log vs SRUM.

**4. Timeline kurmadan tek tek artefakta dalmak.** Acemi bir prefetch dosyası bulur, saatlerce onu inceler, ama bağlamı kaçırır. Pro önce süper timeline kurar; çünkü bir artefaktın anlamı **ondan önce ve sonra ne olduğuyla** ortaya çıkar. İzole bulgu, bağlamsız gürültüdür.

**5. Order of volatility'yi bozmak.** Acemi, canlı ve şüpheli bir makineyi "delil almak için" kapatır ya da diskini hemen imajlar — RAM'deki beacon'ı, şifresiz credential'ları, canlı bağlantıları yok eder. Pro sıcak makinede önce belleği alır.

**6. Base rate'i (normal neye benzer) bilmemek.** Acemi her PowerShell'i, her network logon'ı alarm sanır ve yüzlerce yanlış pozitifte boğulur. Pro, ortamın **normalini** (baseline) bilir: "Bu ortamda yedekleme her gece 2'de PowerShell çalıştırır, bu normaldir; ama finans sunucusundan DC'ye giden bu servis hesabı logon'u normal değildir." Anomali, mutlak değil, **bağlamsal** bir kavramdır.

**7. IOC'ye takılıp TTP'yi kaçırmak.** Acemi IOC listesi eşleşmesi arar; saldırgan hash ve IP değiştirdiği an kör kalır. Pro davranışa bakar: "hangi hash olursa olsun, `lsass.exe`'den bellek okuyan bir process credential access yapıyordur." TTP'ler değişmez, IOC'ler ucuzdur.

**8. Anti-forensics'i hesaba katmamak.** Acemi, log'da 1102 (temizleme) görmezse "loglar temiz, sorun yok" der. Pro log'daki **boşluğu** da bir delil sayar; sessizlik bazen en yüksek sesli alarmdır. Bir makinenin açık olduğu ama hiç event üretmediği pencere, tam da saldırganın çalıştığı penceredir.

**9. WMI ve fileless persistence'ı unutmak.** Acemi Run anahtarlarına bakıp geçer. Pro WMI event subscription'larını, scheduled task'ları, GPO scriptlerini, servis binary path manipülasyonlarını da tarar — çünkü olgun saldırgan diske dokunmayan yerlerde saklanır.

**10. "Bir tane buldum, iş bitti" demek.** Acemi bir kötücül dosya bulunca durur ve temizler. Pro bilir ki bir persistence bulmak, **diğerlerinin de var olduğunu** düşündürmelidir — saldırgan asla tek yumurta bırakmaz. Bir bulgu, avın sonu değil, ATT&CK zincirinde geri kalan halkaları aramanın başlangıcıdır. Zinciri tamamlamadan CA'yı kapatmak, düşmanı ortamda bırakmaktır.

---

### Kapanış yargısı

CA'da başarı, ne kadar veri topladığınla değil, **hangi soruyu neden sorduğunla** ölçülür. Araçlar (KAPE, Velociraptor, Volatility, Plaso, Timesketch, YARA, Autopsy, EZ Tools) sadece kaldıraçtır; asıl kas, "bu artefaktı görünce aklıma hangi hipotez gelir ve onu nasıl çürütürüm ya da doğrularım?" refleksidir. Ve her CA raporu, o rahatsız edici ama dürüst cümleyle biter: *Uyguladığımız metodoloji ve mevcut görünürlükle, tanımlanan pencerede ihlal göstergesi bulundu/bulunmadı; şu kör noktalar açık kaldı.* Bu dürüstlük, aracın kendisinden daha değerlidir.
