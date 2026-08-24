# IR Rapor ve Lessons Learned — Pratisyen Notları

> Bu metin, sahada 15+ yıl olay müdahale (IR) yürütmüş bir DFIR lead perspektifinden yazılmıştır. Amaç kitap özeti değil; gerçek bir vakada elinizi kirletirken kafanızın içinde dönen karar ağacını kağıda dökmektir. Araçlar araçtır; değer, "hangi artefaktı görünce nereye gideceğini" bilmektedir.

---

## 1. Bu iş akışı neyi hedefler ve IR sürecindeki yeri

IR süreci klasik olarak altı fazdan konuşulur: Hazırlık (Preparation), Tespit ve Analiz (Detection & Analysis), Kapsama (Containment), Kök Kazıma (Eradication), Toparlanma (Recovery) ve Olay Sonrası Değerlendirme (Post-Incident / Lessons Learned). NIST SP 800-61 bu döngüyü kurumsallaştırır, SANS PICERL kısaltmasıyla aynı şeyi anlatır.

"IR Rapor ve Lessons Learned" bu döngünün son fazı gibi görünür ama pratikte bir yalandır ki rapor en sonda yazılır. **Rapor, olayın ilk dakikasında yazılmaya başlar.** İlk triage notunuz, ilk aldığınız disk imajının hash'i, "saat 03:14'te şu IP'den şu hesaba başarılı RDP" satırı — bunların hepsi nihai raporun ham maddesidir. Sonda oturup "şimdi rapor yazalım" diyen ekip, kaçınılmaz olarak zaman çizelgesindeki boşlukları hafızadan doldurmaya çalışır ve orada uydurma başlar.

Bu iş akışının hedefi üç katmanlıdır:

1. **Teknik hakikat**: Ne oldu, nasıl girdiler, nereye kadar ilerlediler, ne aldılar/ne yaptılar, hâlâ içerideler mi? (Bu, olay müdahalesinin kendisidir.)
2. **Savunulabilir anlatı**: Bu hakikati, mahkemede, sigortada, düzenleyici kurum önünde (KVKK/Kişisel Verileri Koruma Kurulu bildirimi, GDPR 72 saat) ayakta duracak şekilde, delil zinciri kırılmadan belgelemek.
3. **Kurumsal öğrenme**: Aynı kapıdan bir daha girilmemesi için somut, sahibi ve tarihi olan aksiyonlar üretmek. "Farkındalık artırılmalı" cümlesi lessons learned değildir; çöptür.

Raporun okuyucusu tek kişi değildir. CISO özet ister, hukuk kanıt ister, sistem yöneticisi IOC ve sertleştirme adımı ister, sigortacı zaman çizelgesi ve etki ister. İyi bir rapor bu katmanları ayrı bölümlere ayırır (Executive Summary / Teknik Bulgular / Zaman Çizelgesi / IOC & TTP / Öneriler), tek bir monoblok metin sunmaz.

---

## 2. Adım-adım iş akışı ve KARAR (asıl değer)

Burası metnin kalbi. Bir olay geldiğinde profesyonel DFIR analistinin kafasındaki sıralama ve her adımda hangi artefaktın hangi karara götürdüğü.

### 2.0. Sıfırıncı adım: Scope'u daraltma ve "acele etme" refleksi

Olay bildirimi geldiğinde acemi hemen "makineye bağlanıp bakayım" der. Kıdemli önce üç soru sorar: **Hangi makine(ler)? Ne zaman fark edildi? Kim/ne fark etti?** Çünkü canlı bir saldırganla mı uğraşıyoruz yoksa üç hafta önce kapanmış bir olayın küllerini mi eşeliyoruz — bu, bütün stratejiyi belirler. Canlı saldırgan varsa gürültü (noisy) forensics saldırganı ürkütür; sessiz gözlem daha değerli olabilir. Eğer aktif fidye şifreleme sürüyorsa dakikalar önemlidir ve containment analizden önce gelir.

Karar kuralı: **Hasar hâlâ birikiyorsa önce kanamayı durdur (containment), sonra otopsi yap.** Statik/bitmiş olayda ise delil bütünlüğü önceliklidir, acele imaj alıp bozmak yerine düzgün al.

### 2.1. Order of Volatility'ye göre delil toplama

RFC 3227'nin klasik sıralaması hâlâ geçerli: en uçucudan en kalıcıya doğru topla.

1. **CPU register / cache** — pratikte erişilemez, geç.
2. **RAM (bellek)** — en kritik uçucu delil. Canlı makineye erişimin varsa ve makine açıksa, **bellek imajını disk imajından ÖNCE al.** Araç: Windows'ta WinPKD/DumpIt yerine kurumda standart olarak Magnet RAM Capture veya Belkasoft; Linux'ta `avml` veya LiME. Bellekte olan da diskte olmayan şey: şifre çözülmüş payload'lar, injection yapılmış process'ler, ağ bağlantıları, çözülmüş komut satırları, bazen şifreleme anahtarları.
3. **Ağ durumu / bağlantılar** — `netstat`, canlı EDR telemetrisi, firewall/proxy logları. Uçucudur; makine yeniden başlarsa gider.
4. **Çalışan process'ler, açık dosyalar, oturumlar.**
5. **Disk** — imaj. Uçucu değil ama en zengin.
6. **Uzak loglar, fiziksel konfigürasyon.**

**Kritik karar**: Makineyi kapatmalı mıyım? Fidye ya da BitLocker/şifreli disk şüphesi varsa **makineyi KAPATMA** — kapatırsan RAM'deki anahtarı ve şifresiz durumu kaybedersin. Eğer aktif veri sızması (exfiltration) sürüyorsa, kabloyu çekmek (ağdan izole) mantıklı ama gücü kesmek çoğu zaman değil. "Pull the plug mi graceful shutdown mu?" tartışmasında modern cevap genelde: **ağdan izole et, gücü koru, bellek al.**

### 2.2. Triage — geniş ağ atma (KAPE)

Tam disk imajı almak saatler sürer ve 500 makinelik bir olayda imkânsızdır. Bu yüzden **hızlı triage** yaparsın. Standart araç: **KAPE (Kroll Artifact Parser and Extractor)**. KAPE'nin Targets modülü ile sadece adli değeri yüksek artefaktları toplar (dakikalar sürer), Modules ile de Eric Zimmerman araçlarını üstünde koşturursun.

Topladığım öncelikli Windows artefaktları ve **neden**:

- **$MFT** — dosya sistemi metadata'sının omurgası. Silinmiş dosya kayıtları, oluşturma/değiştirme zamanları burada. Timestomping'i (zaman damgası oynaması) $MFT'deki $STANDARD_INFORMATION vs $FILE_NAME timestamp uyumsuzluğundan yakalarım.
- **Amcache.hve & ShimCache (AppCompatCache)** — hangi çalıştırılabilir dosya bu makinede var oldu / çalıştı. Saldırganın bıraktığı `mimikatz.exe` silinmiş olsa bile Amcache'te SHA1'iyle izi kalır. Zimmerman'ın `AmcacheParser` ve `AppCompatCacheParser`.
- **Prefetch (.pf)** — bir exe'nin çalıştırıldığının ve kaç kez, en son ne zaman çalıştığının kanıtı. `PECmd`. "Bu araç gerçekten koştu mu?" sorusuna en net cevap.
- **Event Logs (.evtx)** — özellikle Security (4624/4625 logon, 4672 special privileges, 4688 process creation), System (7045 servis kurulumu — lateral movement ve persistence'ın altın göstergesi), PowerShell/Operational (4104 script block logging), TerminalServices (RDP). Zimmerman'ın `EvtxECmd`.
- **Registry hive'ları** (SYSTEM, SOFTWARE, NTUSER.DAT, USRCLASS.DAT) — persistence (Run keys, Services), USB geçmişi, en son çalıştırılanlar (RunMRU), UserAssist. `Registry Explorer` / `RECmd`.
- **SRUM (System Resource Usage Monitor)** — hangi process ne kadar ağ trafiği üretti. Exfiltration hacmini tahmin etmek için paha biçilmez. `SrumECmd`.
- **Browser geçmişi, LNK dosyaları, JumpLists, ShellBags** — kullanıcının hangi klasörleri gezdiği, hangi dosyaları açtığı. Insider ya da phishing izini sürerken.

**Karar mantığı örneği**: ShimCache'te `C:\Users\Public\svc.exe` görüyorum, ama Prefetch'te karşılığı yok. ShimCache "var oldu"yu, Prefetch "çalıştı"yı gösterir — ShimCache'e girmesi çalıştığını garanti etmez (dokunulmuş/enumerate edilmiş olabilir). Prefetch'te de varsa **çalıştı** derim. İkisi de varsa ve 7045 event'inde aynı isimle bir servis kurulmuşsa, bu artık bir persistence mekanizması → hipotezim: saldırgan servis olarak kalıcılık kurdu, koşturdu.

### 2.3. Bellek analizi (Volatility)

RAM imajını **Volatility 3** ile parçalarım. Sırayla koştuğum ve neye baktığım pluginler:

- `windows.pslist` / `windows.psscan` / `windows.pstree` — process listesi ve ebeveyn-çocuk ilişkisi. **Anomali avı**: `winword.exe`'nin çocuğu olarak `powershell.exe` görürsem, bu makro tabanlı ilk erişim demektir. `services.exe` altında olması gereken bir process `explorer.exe` altındaysa şüphelenirim. `psscan`, `pslist`te gizlenmiş (unlinked) process'i yakalar → rootkit göstergesi.
- `windows.malfind` — process bellek alanında RWX (yazılabilir+çalıştırılabilir) sayfalar, MZ header'ları → code injection / shellcode.
- `windows.cmdline` — process'lerin komut satırı argümanları. Base64'lü, `-enc`'li, `-nop -w hidden` bayraklı PowerShell burada çıplak yakalanır.
- `windows.netscan` — bellekteki ağ bağlantıları. C2 IP'sini burada bulurum, diskte hiç log kalmamış olsa bile.
- `windows.dlllist` / `windows.ldrmodules` — DLL injection, unlinked modül.

**Karar mantığı**: `malfind` bir `explorer.exe` içinde RWX bölge + shellcode buldu, `netscan` aynı PID'in 443'ten tanımadığım bir IP'ye bağlı olduğunu gösterdi, `cmdline` boş (injection yani dosyasız). Sonuç: **fileless / process injection ile aktif C2**. Bu, diskte az iz bırakan bir tehdittir; artık disk forensics'e ek olarak ağ tarafına ve EDR telemetrisine yüklenirim.

### 2.4. Zaman çizelgesi oluşturma (Timeline — süper araç)

DFIR'da tek bir en değerli çıktı varsa o **süper zaman çizelgesidir (super timeline)**. Farklı artefaktları (MFT, event log, registry, prefetch, browser) tek bir zaman ekseninde birleştirirsin. Araçlar: **Plaso/log2timeline** ile `.plaso` üret, **Timesketch**'e yükle görselleştir; ya da Zimmerman araçlarının CSV çıktılarını **Timeline Explorer**'da aç.

Zaman çizelgesi olayı bir hikâyeye dönüştürür: 09:14 phishing eki açıldı (LNK/prefetch) → 09:15 powershell indirici koştu (4104) → 09:22 yeni yerel admin hesabı (4720) → 10:05 komşu sunucuya RDP (4624 type 10) → 02:30 arşiv oluşturuldu (MFT) → 02:45 dış IP'ye yükleme (SRUM/proxy). **İşte kök neden ve kapsam bu eksende ortaya çıkar.**

Kritik disiplin: **her zaman UTC'ye normalize et.** Sistem yerel saati, log yerel saati, farklı sunucu saat dilimleri karışırsa zaman çizelgen yalan söyler. Ayrıca saat kayması (clock skew) not edilmelidir.

### 2.5. Doğrulama ve avlanma (YARA, IOC, Velociraptor)

Bir makinede bulguyu doğrulayınca, **"bu tek makinede mi?"** sorusuna geçerim. Burada tekil forensics'ten filoya (fleet) geçiş yaparım: **Velociraptor**. Velociraptor VQL ile bütün endpoint'lerde aynı IOC'yi (dosya hash'i, registry key, çalışan process, YARA imzası) saniyeler içinde tarar. Saldırganın dosyasından çıkardığım karakteristik string'lerle bir **YARA** kuralı yazar, tüm filoda koştururum. Böylece "yanal hareket 6 makineye ulaşmış" gerçeğini masaüstü masaüstü dolaşmadan bulurum.

Autopsy/Sleuth Kit ise daha derin, tek disk üzerinde deleted file recovery, carving, keyword search için elimin altındadır — özellikle hukuki delil sunumu ve görsel raporlamada.

### 2.6. Raporlama ve Lessons Learned'e dönüş

Elimde: normalize zaman çizelgesi, doğrulanmış IOC listesi, MITRE ATT&CK'e eşlenmiş TTP'ler (initial access T1566, execution T1059.001, persistence T1543.003, credential access T1003, lateral movement T1021.001, exfiltration T1041), etki değerlendirmesi ve kapsam. Rapor bunları katmanlı sunar. Lessons learned bölümü (bkz. Bölüm 5) her bulguyu **sahibi ve tarihi olan** bir aksiyona çevirir.

---

## 3. Kritik dikkat noktaları

### Delil bütünlüğü (integrity) ve hash

Herhangi bir imaj (disk ya da bellek) alınır alınmaz **kriptografik hash'i (SHA-256)** alınır ve kaydedilir. Analizi **kopya üzerinde** yaparsın, aslına asla dokunmazsın. Diski **write blocker** (donanımsal ya da yazılımsal) ile mount edersin — analiz sırasında OS'in diske "last accessed" damgası basıp delili değiştirmesini engeller. İmajı `.E01` (EWF) formatında alırsın; bu format hash'i ve meta veriyi imajın içine gömer, bütünlüğü kendinden doğrular. Analiz sonunda hash'i yeniden alıp başlangıçtakiyle eşleştirirsin: **"delil analiz boyunca değişmedi" kanıtı budur.**

### Order of Volatility

Bölüm 2.1'de anlattım; tekrar vurgu: yanlış sırada toplama, üstteki (uçucu) delili yok eder. En sık hata: paniğe kapılıp makineyi reboot etmek/kapatmak ve RAM'i, aktif bağlantıları, çözülmüş anahtarları uçurmak.

### Chain of Custody (delil zinciri)

Her delil parçası için: kim topladı, ne zaman (UTC), nereden, hangi araçla, nereye teslim etti, kim erişti — kesintisiz kayıt. Mahkemede bir tek boşluk, tüm delili çürütür. Fiziksel diskler mühürlü torbada, etiketli; dijital imajlar erişim loglu depoda. **"Bu diske pazartesi ile çarşamba arası kim dokundu?" sorusuna cevabın yoksa, o delil hukuken ölmüştür.**

### Anti-forensics'e karşı

Saldırgan iz temizler. Bilmen gerekenler:
- **Log temizleme**: 1102 (Security log cleared) ve 104 (System log cleared) event'leri saldırganın kendini ele verdiği yerlerdir. Log'un "boş" olması masumiyet değil, alarm sebebidir. Bu yüzden **loglar merkezî SIEM'e akıtılmalı** — yerelde silinse bile merkezde durur.
- **Timestomping**: $STANDARD_INFORMATION zaman damgaları kolayca değiştirilir, ama $FILE_NAME (MFT içinde) çekirdek tarafından yazılır, kullanıcı modundan zor oynanır. İkisi tutmuyorsa timestomp var.
- **Secure delete / wiping**: Dosya sıfırlanmış olsa bile $MFT kaydı, Amcache, Prefetch, ShimCache, SRUM, event log gibi **ikincil artefaktlar** varlığın izini taşır. "Dosyayı silmiş" saldırganı bu ikincil izlerden yakalarım.
- **Bellekte-yaşayan (fileless)**: Diskte hiç iz yoksa RAM ve EDR telemetrisi tek şansındır — bu yüzden RAM'i erken al.

---

## 4. Gerçek dünya senaryosu

**Bağlam**: Orta ölçekli bir lojistik firması. Cuma 08:50'de muhasebe müdürü "dosyalarım açılmıyor, isimleri değişti" diyor. Helpdesk fidye şüphesiyle IR ekibini çağırıyor. Bir dosya sunucusunda `.lockedX` uzantılı dosyalar ve `HOW_TO_DECRYPT.txt` var.

**Adım 1 — Scope ve triage.** Önce soruyorum: kaç makine etkilendi, şifreleme hâlâ sürüyor mu? EDR konsolunda son 30 dakikada iki sunucuda yoğun dosya yeniden adlandırma görüyorum → **aktif.** Karar: bu iki sunucuyu ve şifrelemeyi tetikleyen kaynağı **ağdan izole et, gücü kesme** (RAM ve olası anahtar için). Şifreleme yayılmasın diye etkilenen segment VLAN'dan koparılır.

**Adım 2 — Bellek + triage imaj.** Aktif sunucudan Magnet RAM Capture ile bellek, KAPE ile hedefli artefaktlar alınır. Hash'ler kaydedilir.

**Adım 3 — Bellek analizi.** Volatility `pstree`: `services.exe` altında `c:\windows\temp\a.exe` adında bir process, çocuğu `vssadmin.exe delete shadows /all /quiet` (gölge kopya silme — fidyenin klasik imzası). `cmdline` bunu doğruluyor. `netscan`: aynı ana makinenin daha önce 3389'dan (RDP) bir iç IP ile konuşmuş izleri.

**Adım 4 — Zaman çizelgesi.** KAPE çıktılarını Timeline Explorer'da birleştiriyorum, UTC'ye normalize:
- **Salı 21:10** — İnternete açık RDP sunucusunda (yanlış yapılandırılmış NAT) `Administrator` hesabına 400+ başarısız (4625), ardından bir başarılı logon (4624, type 10, dış IP). → **İlk erişim: RDP brute-force.** ATT&CK T1110 / T1133.
- **Salı 21:40** — Yeni yerel admin hesabı `svc_backup` oluşturuldu (4720, 4732). → Persistence + kamuflaj.
- **Salı 22:05** — Amcache/Prefetch: `mimikatz`-benzeri bir araç ve `PsExec.exe` koştu. → Kimlik bilgisi hırsızlığı (T1003) + yanal hareket aracı.
- **Çarşamba–Perşembe** — 4624 type 3/10 kayıtları: domain admin kimliğiyle 4 sunucuya daha erişim. → **Yanal hareket kapsamı: 5 sunucu.**
- **Cuma 08:30** — `a.exe` iki dosya sunucusunda çalıştı, `vssadmin` shadow sildi, şifreleme başladı.
- **Perşembe 02:15** — SRUM: `a.exe`'den önce, bir process 4 GB dışa trafik üretmiş; proxy loglarında bir dosya paylaşım servisine yükleme. → **Şifrelemeden ÖNCE veri sızdırılmış (double extortion).**

**Adım 5 — Filo taraması.** `svc_backup` hesabı, `a.exe`'nin SHA-256'sı ve C2 IP'siyle Velociraptor'da tüm filoyu tarıyorum. Bir YARA kuralı yazıp `a.exe`'nin string imzasını arıyorum. Sonuç: 5 sunucu + 2 iş istasyonu dokunulmuş; başka aktif şifreleme yok.

**Varılan sonuç**: Bu bir fidye olayından ibaret değil; **öncesinde veri hırsızlığı olan hedefli bir saldırı.** Kök neden: internete açık, MFA'sız RDP + zayıf Administrator parolası. Etki: 7 sistem, 4 GB veri sızıntısı → KVKK bildirim yükümlülüğü doğuyor (kişisel veri sızması olasılığı hukuka devredilir). Yedekler etkilenmemiş (offline kopya var) → toparlanma mümkün. Anahtar bulgu: gölge kopyaların silinmiş olması yerel geri dönüşü engelledi, ama offline yedek kurtardı.

Bu vaka raporunun executive summary'si üç cümledir: "Saldırgan internete açık RDP üzerinden zayıf parolayla girdi, dört gün içeride kalıp veri sızdırdı ve fidye yazılımı çalıştırdı. Offline yedeklerden toparlanma mümkün; ancak veri sızıntısı nedeniyle KVKK bildirimi gerekir. Kök neden RDP maruziyeti ve MFA eksikliğidir."

---

## 5. Yaygın tuzaklar ve pro yargısı

**Tuzak 1 — Fidye notunu görüp "olay fidye yazılımı" deyip durmak.** Acemi şifrelemeyi olayın tamamı sanır. Kıdemli bilir ki şifreleme çoğu zaman saldırının **son** adımıdır; asıl soru "şifrelemeden önce ne oldu, veri gitti mi, ne kadar içerideydiler?" Sızıntıyı ıskalayan rapor, kurumu KVKK cezasına ve dava riskine açık bırakır.

**Tuzak 2 — Canlı makineyi reboot etmek/kapatmak.** "Temiz başlasın" diye makineyi kapatan yönetici, RAM'deki C2 bağlantısını, injection'ı, olası şifreleme anahtarını yok eder. Kural: **analiz etmeden önce hiçbir şeyi kapatma; önce belleği al.**

**Tuzak 3 — Tek artefakta güvenmek.** ShimCache'te bir exe görmek çalıştığını kanıtlamaz. Timestamp'e körü körüne güvenmek timestomp'a yem olmaktır. Pro **korelasyon** yapar: ShimCache + Prefetch + Amcache + event log + $MFT üçünü-dördünü çakıştırmadan "kesin" demez.

**Tuzak 4 — Zaman dilimini normalize etmemek.** Farklı sunucuların yerel saatleri, log'ların UTC/yerel karışımı zaman çizelgesini yalancı yapar. "Exfil şifrelemeden önce mi sonra mı" gibi kritik sıra buna bağlıdır. Her şeyi UTC'ye çek, clock skew'i not et.

**Tuzak 5 — Delil bütünlüğünü es geçmek.** Write blocker kullanmadan diski mount etmek, hash almadan imaj almak, chain of custody tutmamak. Teknik olarak doğru bulgu, hukuken çürük delil olur. "Doğru cevabı buldum ama mahkemede kullanılamaz" en acı sonuçtur.

**Tuzak 6 — Log'un boş olmasını iyi haber sanmak.** 1102/104 (log temizleme) event'i ya da beklenmedik boşluk, masumiyet değil bir eylemin kanıtıdır. Merkezî SIEM olmadan yerel log'a güvenmek, saldırgana silme yetkisi vermektir.

**Tuzak 7 — "Bulduk, kapattık" deyip kök kazımayı yarım bırakmak.** Tek bir C2'yi bloklamak, ikinci persistence mekanizmasını (scheduled task, WMI subscription, ikinci web shell) atlamak demek olabilir. Pro, eradication'dan önce **tüm persistence'ı** haritalar. Aksi halde bir hafta sonra saldırgan geri gelir; buna "reinfection" denir ve raporun itibarını bitirir.

**Tuzak 8 — Lessons learned'i temenniye çevirmek.** "Farkındalık artırılmalı", "güvenlik güçlendirilmeli" cümleleri işe yaramaz. Pro yargısı: her bulgu **SMART** aksiyona döner. Kötü: "RDP güvenliği artırılmalı." İyi: "31 Temmuz'a kadar tüm RDP internete kapatılacak, sadece VPN+MFA arkasından erişilecek; sorumlu: Altyapı Ekibi Lideri; doğrulama: dış tarama raporu." Sahibi ve tarihi olmayan aksiyon, aksiyon değildir.

**Tuzak 9 — Blameless kültürü unutmak.** Post-incident toplantısı "kim hata yaptı" avına dönerse, bir dahaki sefere kimse olay bildirmez, herkes iz gizler. Lessons learned süreç ve sistem hakkındadır, kişi hakkında değil. "Neden bu kişi tıkladı" değil, "neden bu ek çalışanın kutusuna kadar geldi ve neden tıklayınca kod çalışabildi" sorulur.

**Tuzak 10 — Raporu tek okuyucuya yazmak.** Salt teknik jargon dolu rapor yöneticiyi kaybeder; salt yüksek-seviye özet teknisyeni köreltir. Katmanla: yönetici özeti (risk ve karar), teknik gövde (bulgu ve delil), ek (IOC, ATT&CK haritası, zaman çizelgesi, hash'ler). Herkes kendi katmanını okusun.

---

## Kapanış: pro'nun tek cümlelik pusulası

Olay müdahalesinde değer, en pahalı araçta değil, **"bu artefaktı görünce hangi hipoteze gidiyorum ve onu hangi ikinci artefaktla doğruluyorum"** disiplinindedir. Delili bozmadan topla, zaman çizelgesinde hikâyeyi kur, tek kanıta asla güvenme, kök nedeni bul, ve öğrenmeyi sahibi-tarihi olan aksiyona çevir. Raporun ilk dakikada başladığını unutma; sonda uydurmak zorunda kalıyorsan, süreç boyunca not tutmamışsın demektir.
